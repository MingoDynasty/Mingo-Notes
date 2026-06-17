# AutoUpdate - Code Review

**Date:** 2026-06-16
**Scope:** `scripts/AutoUpdate/` - `auto_update.py`, `utilities.py`, config files.
**Status:** Findings agreed; no code changes made yet. Single source of truth, consolidated
from two independent reviews (an initial pass and a Codex cross-review).

---

## 1. What the tool does

A personal sync utility that copies Valorant notes and screenshots from an Obsidian vault
into this Docusaurus repo. It:

1. Loads settings from `app.conf` (TOML).
2. Scans screenshots referenced by the Obsidian markdown vs. those on disk and warns about
   unused ones (with a hardcoded "protected" allowlist).
3. Optionally deletes + re-copies screenshots into `static/screenshots/`, stripping the
   `"Pasted image "` filename prefix.
4. Copies markdown into `docs/`, rewrites Obsidian `![[wikilink]]` embeds into Docusaurus
   `![](/screenshots/...)` links, optionally runs Prettier, and prepends
   `tags: ["valorant"]` frontmatter.

### Already good
- `app.conf` is gitignored and untracked - no secrets leak into the repo.
- An `example_app.conf` template is provided.
- The destructive `os.remove` loop is fenced to `.png` files only.
- `static/screenshots/` is git-tracked (516 files), so a wipe of the *correctly-configured*
  target is recoverable via `git restore -- static/screenshots` (if the deletion was also
  staged, use `git restore --staged --worktree --source=HEAD -- static/screenshots` to reset
  both the index and the worktree).

---

## 2. Validation performed

- `uv run mypy auto_update.py utilities.py` (Python 3.14; mypy is a declared dependency).
  Confirms the `-> set()` annotation errors (F4). Independently confirmed in the Codex
  cross-review via `.venv\Scripts\python.exe -m mypy auto_update.py utilities.py`.
- `python -m py_compile auto_update.py utilities.py` - both compile.
- Confirmed repo screenshots are stored **without** the `"Pasted image "` prefix
  (e.g. `20250518214042.png`), which is what makes F5 a real mismatch.
- Confirmed `app.conf` exists locally, is untracked, and currently has
  `copy_screenshots = true` (so the deletion path F3 is live in normal local use).
- Confirmed `static/screenshots/` is git-tracked (516 files).

---

## 3. Findings

Severity legend: 🔴 High · 🟠 Medium · 🟡 Low

### Correctness

#### 🔴 F1 - Prettier formats the Obsidian source, not the repo copy (and lags a run behind)
**Location:** `auto_update.py:142-148`
```python
shutil.copy(full_filename, dst_file)          # copies SOURCE -> repo first
...
subprocess.run(["npx", "prettier", full_filename, "--write"], shell=True, check=False)
                                    # ^ formats the SOURCE vault file, after the copy
```
**Impact:**
- Mutates the source-of-truth Obsidian vault file - a surprising side effect for a
  "copy into repo" script.
- The repo copy receives the *unformatted* version; formatting only reaches the repo on the
  *next* run, so the repo is always one sync behind.

**Fix:** Run Prettier on `dst_file` after the copy (and after link rewrite + frontmatter).
Decide explicitly whether the source vault should ever be modified (recommend: no).
*Implement together with F7 - same `subprocess.run(...)` line.*

**Provenance:** v1 + v2 agree. Most important correctness bug.

---

#### 🟠 F2 - Markdown rewrite silently drops `.png]]` lines that match neither prefix
**Location:** `auto_update.py:153-161`
```python
if line.endswith('.png]]'):
    if line.startswith('![[attachments/Pasted image '):
        ...
        print(...)
    if line.startswith('![[Pasted image '):
        ...
        print(...)
else:                      # <-- binds to the OUTER if
    print(line)
```
**Impact:** A line ending in `.png]]` that matches neither inner prefix falls through both
`if`s and is **never printed** - it is dropped from the repo copy while the Obsidian source
stays intact, so the loss is easy to miss. Examples that trigger it:
```markdown
caption text ![[Pasted image 20250518214042.png]]
![[attachments/Other image 20250518214042.png]]
```
**Severity note:** Latent. With today's standalone `![[Pasted image ...]]` embeds it likely
isn't firing, but renaming a screenshot or putting text on the same line as an embed loses
that line silently. High impact if hit; trivial fix.

**Fix:** Add a fallback `print(line)` for the unmatched case. Better: route all rewriting
through one regex substitution helper that preserves surrounding text (see section 4).

**Provenance:** v2 only. Verified here against the code.

---

#### 🟠 F3 - Screenshot deletion can wipe the wrong directory if misconfigured
**Location:** `auto_update.py:81-97`
```python
for filename in os.listdir(config['git_screenshots_directory']):
    file_path = os.path.join(config['git_screenshots_directory'], filename)
    if os.path.isfile(file_path) and filename.endswith('.png'):
        ...
        os.remove(file_path)
```
**Impact:** Removes every non-"protected" `.png` in `git_screenshots_directory`. `app.conf`
currently has `copy_screenshots = true`, so this path is active.
- **Mitigation (correctly configured):** the target is git-tracked, so a wipe is recoverable.
- **Real risk:** a typo/stale absolute path pointing *outside* the repo would delete
  unrelated `.png` files with no git safety net. This is the scenario that warrants Medium.

**Fix:** Resolve the target path and assert it is inside the expected repo screenshots
directory before deleting. A `--dry-run` option would further de-risk it.

**Provenance:** v1 (Low) + v2 (Medium). Reconciled to Medium for the misconfig case.

---

#### 🟡 F4 - `-> set()` is an invalid type annotation (Low/Medium - quality gate failure)
**Location:** `utilities.py:1`, `auto_update.py:38`
```python
def get_screenshots_used_in_markdown_file(filename) -> set():
def check_unused_files(screenshots_dir: str, md_dir: str) -> set():
```
mypy: `error: Invalid type comment or annotation [valid-type]` on both. `set()` constructs an
empty set object at def-time instead of naming a type.
**Severity:** No runtime behavior change - lower behavioral risk than F5/F8. The harm is that
it breaks the project's *declared* mypy gate. Classed as a quality-gate failure.
**Fix:** `-> set[str]`.
**Provenance:** v1 (Med) + v2 (Low); verified locally. Reconciled to Low/Medium (quality gate).

---

#### 🟠 F5 - Deletion-protection check can never match (dead code, currently harmless)
**Location:** `auto_update.py:88-93`
```python
for map_name, screenshots in protected_screenshots.items():
    if filename in screenshots:   # filename = "20250518...png" (stripped)
        ...                       # screenshots hold "Pasted image 20250518...png"
```
**Impact:** `protected_screenshots` holds names *with* the `"Pasted image "` prefix; files in
`git_screenshots_directory` are stored *stripped*. The membership test never matches, so the
"protect from deletion" branch is dead. Harmless today only because the copy loop re-adds the
files. The effective protection lives separately in `check_unused_files`.
**Fix:** Normalize to one canonical name form and compare consistently, or remove the
redundant block.
**Implementation group:** part of the *protected-screenshots design* fix - do alongside
F8 and F10 (see remediation plan).
**Provenance:** v1 only. Not in v2.

---

#### 🟠 F6 - Missing `encoding="utf-8"` on text reads/writes (Windows cp1252 risk)
**Location:** `utilities.py:4`, `auto_update.py:120` (`line_prepender`),
`auto_update.py:150` (`fileinput.input(... inplace=True)`)
**Impact:** On Windows the default text encoding is cp1252. Notes with em-dashes, smart
quotes, accents, or emoji can raise `UnicodeDecodeError` or round-trip incorrectly.
**Fix:** `encoding="utf-8"` on every text open; `fileinput.input(..., openhook=
fileinput.hook_encoded("utf-8"))` for the inplace rewrite.
**Provenance:** v1 + v2 agree.

---

### Security / robustness

#### 🟡 F7 - `subprocess.run(..., shell=True)` with a list + interpolated filename
**Location:** `auto_update.py:148`
**Impact:** `shell=True` with a list is discouraged and the filename comes from
`os.listdir`, so it is injection-shaped - but the inputs are your own local files, so the
practically relevant harms are: `check=False` silently swallows Prettier failures, and the
list+`shell=True` form is platform-sensitive/confusing. `shell=True` was likely added so
Windows resolves `npx.cmd`.
**Fix:** `shell=False` with explicit `"npx.cmd"`; log or raise on non-zero exit.
*Same line as F1 - fix both together in Commit 1; the commit message should name both the
correctness (target file) and reliability (`shell`/`check`) concerns.*
**Provenance:** v1 (injection-leaning) + v2 (reliability-leaning). Reframed as primarily
reliability/observability; Low.

---

#### 🟠 F8 - Hardcoded protected paths can crash the run before sync starts
**Location:** `auto_update.py:29-35`
```python
protected_screenshots = {
    "Breeze": get_screenshots_used_in_markdown_file(
        "E:/Obsidian/Vaults/My Vault/Gaming/Valorant Sage Walls/Breeze.md"),
    ...
}
```
**Impact:** These reads run at module load, *before* any configured sync work. A missing or
renamed file (e.g. `Breeze.md`) raises `FileNotFoundError` and aborts the entire run. Also
not config-driven, so the script is less portable.
**Fix:** Move protected sources into `app.conf`, make them optional, and warn (don't crash)
on missing files.
**Implementation group:** part of the *protected-screenshots design* fix - do alongside
F5 and F10.
**Provenance:** v1 (maintainability) + v2 (robustness). Reconciled to Low-Medium; listed
Medium to reflect the crash-before-sync behavior.

---

#### 🟡 F9 - Config loading and validation are fragile
**Location:** `auto_update.py:18` and all `config['...']` accesses
**Impact:** Assumes CWD is the script dir, that `app.conf` exists, that all keys exist, and
that all configured dirs exist. Any miss yields a raw traceback.
**Fix:** Resolve `app.conf` relative to `__file__`, validate required keys up front, emit
clear errors for missing/invalid directories.
**Provenance:** v1 + v2 agree.

---

### Maintainability

#### 🟡 F10 - Hardcoded protected list + dead commented code
**Location:** `auto_update.py:29-35`, dead comments at `auto_update.py:26-28`
Move the protected list into `app.conf`; delete the dead code.
**Implementation group:** part of the *protected-screenshots design* fix - do alongside
F5 and F8.
**Provenance:** v1.

#### 🟡 F11 - Entire pipeline runs at module level
**Location:** `auto_update.py:18` onward. `import auto_update` runs the whole pipeline; no
`main()` guard, nothing is unit-testable. **Fix:** wrap steps in functions behind
`if __name__ == "__main__":`. **Provenance:** v1 + v2.

#### 🟡 F12 - Magic slices
**Location:** `auto_update.py:110` (`screenshot[13:]`), `utilities.py:9-12`,
`auto_update.py:155-158`. `screenshot[13:]` blindly truncates 13 chars even for names not
starting with `"Pasted image "`. **Fix:** `str.removeprefix(...)` / `removesuffix(...)`.
**Provenance:** v1 + v2.

#### 🟡 F13 - Duplicated link-parsing logic
**Location:** `utilities.py` vs. inline rewrite at `auto_update.py:153-159`. Same Obsidian
embed parsing maintained in two places. **Fix:** one shared parser. **Provenance:** v1
(+ v2's parser recommendation).

#### 🟡 F14 - Inconsistent extension filtering
**Location:** `check_unused_files` counts everything in the screenshots dir, but the deletion
loop filters to `.png`. A stray non-image is reported "unused." **Fix:** filter the
unused-check to image extensions. **Provenance:** v1.

#### 🟡 F15 - Parameter shadowing
**Location:** `utilities.py:9` - the `filename` parameter is reassigned as a loop variable.
**Fix:** rename the inner variable. **Provenance:** v1.

---

## 4. Cross-cutting root cause

The rewrite at `auto_update.py:153-161` **reconstructs each line from scratch**
(`print(f"![{alt}](/screenshots/{alt})")`) instead of substituting the embed within the
existing line. That single design choice is the root of both **F2** (lines matching neither
prefix produce no output) and the **F12** magic-slice fragility. A single regex-based
substitution helper - shared with `utilities.py` (F13) - would:
- preserve any surrounding text on the line,
- eliminate the silent-drop path (F2),
- remove the magic slices (F12),
- de-duplicate parsing (F13).

Worth weighing this small refactor against four separate point-fixes.

---

## 5. Reconciled priority order

| # | ID | Sev | Issue |
|---|----|-----|-------|
| 1 | F1 | 🔴 | Prettier targets source, not repo; mutates vault; one-run lag |
| 2 | F2 | 🟠 | Markdown rewrite silently drops unmatched `.png]]` lines |
| 3 | F3 | 🟠 | Screenshot deletion can wipe a misconfigured (non-git) path |
| 4 | F6 | 🟠 | Missing UTF-8 encoding (Windows corruption risk) |
| 5 | F5 | 🟠 | Dead deletion-protection check (prefix mismatch) |
| 6 | F8 | 🟠 | Hardcoded protected paths crash before sync |
| 7 | F4 | 🟡 | `-> set()` invalid annotation (quality gate; behaviorally low) |
| 8 | F7 | 🟡 | `shell=True` + ignored Prettier failures (ship with F1) |
| 9 | F9 | 🟡 | Fragile config loading/validation |
| 10 | F11-F15 | 🟡 | Maintainability (F10 ships in Commit 2; F12/F13 resolved by the Commit 1 regex helper if taken) |

---

## 6. Remediation plan

**Status:** Commit 1 implemented on branch `fix/autoupdate-sync-correctness`. Commits 2-3 pending.

- **Commit 1 (Prettier invocation + correctness) — done:** F1 + **F7** (same `subprocess.run` line),
  plus F2, F4, F6 - the bugs that corrupt, drop, or mis-sync content. Per decision D1, F1
  runs Prettier on `dst_file` only (never the vault). Per decision D3, F2 is fixed with the
  section-4 shared regex helper, which **also resolves F12 and F13**. If that helper grows,
  split it into its own commit.
- **Commit 2 (protected-screenshots design):** F5 + F8 + F10 as one change (decision D2,
  config-driven) - normalize name handling, move the protected list into `app.conf`, make
  sources optional with warnings, drop the dead code.
- **Commit 3 (recommended hardening):** F3, F9. Not "optional" - F3 guards the active delete
  path (`copy_screenshots = true` in normal local use); F9 is the lower-priority half.
- **Remaining maintainability:** F11, F14, F15. (F12/F13 are handled in Commit 1 via the
  regex helper; F11 module-level -> `main()` restructure is deferred per decision D4.) Left
  as TODOs unless prioritized.

---

## 7. Decisions

Resolved 2026-06-16 (these were the open questions; binding for implementation):

- **D1 - Vault writes: No.** The tool must never modify the Obsidian source vault. Fix F1 by
  running Prettier on `dst_file` only.
- **D2 - Protected screenshots (F5+F8+F10): keep, config-driven.** Move the protected sources
  into `app.conf`, make them optional, and warn (don't crash) on missing files.
- **D3 - F2 fix shape: shared regex helper.** One regex substitution helper shared with
  `utilities.py`; this also resolves F12 (magic slices) and F13 (duplicated parser).
- **D4 - main() restructure (F11): deferred.** Keep the fixes targeted; leave the
  module-level -> `main()` refactor as a TODO.

---

## 8. Findings provenance

Which review surfaced each finding (kept for traceability).

| ID | Initial review | Codex cross-review | Reconciliation |
|----|----------------|--------------------|----------------|
| F1 | C1 (High) | High | Unchanged - High |
| F2 | - | Medium | Added from Codex review |
| F3 | S3 (Low) | Medium | Raised to Medium (misconfig case) |
| F4 | C3 (Med) | Low | **Low/Medium - quality gate** |
| F5 | C2 (Med) | - | Kept from initial review; grouped w/ F8+F10 |
| F6 | C4 (Med) | Medium | Unchanged - Medium |
| F7 | S1 (Low) | Low | Reliability framing; ship with F1 |
| F8 | M4 (Maint) | Medium (robustness) | Medium; grouped w/ F5+F10 |
| F9 | S2 (Low) | Low | Low |
| F10-F15 | M1-M6 | partial | Maintainability backlog |

---

## 9. Implementation handoff

Context for picking this up cold (e.g. a fresh session). Work order is in section 6;
decisions in section 7 are binding.

### Environment
- Windows; PowerShell is primary. (The Bash tool mangles `E:\...` paths - use PowerShell or
  forward-slash paths.)
- Python 3.14 via `uv`. Type check: `uv run mypy auto_update.py utilities.py`.
- Syntax check: `python -m py_compile auto_update.py utilities.py`.

### Safety - do NOT run the script blind
`auto_update.py` has destructive side effects driven by the local, untracked `app.conf`
(currently `copy_screenshots = true`):
- It overwrites markdown in `docs/` and (today) formats files in the **Obsidian vault**.
- It **deletes** `.png` files from `static/screenshots/` before re-copying.

Do not execute it just to "test" a change. `static/screenshots/` is git-tracked so a repo-side
wipe is recoverable, but **the Obsidian vault is not**. Prefer reasoning + mypy + targeted
manual checks over running the pipeline.

### Verifying changes without side effects
- The risky logic (filename normalization, the markdown rewrite) is pure string handling -
  exercise the new regex helper (D3) on sample strings directly instead of running the pipeline.
- When F11 is eventually done, add unit tests for: known embeds, unknown `.png]]` lines, names
  with/without `Pasted image `, missing protected files, and path validation before delete.
