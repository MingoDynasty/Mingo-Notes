# obsidian-import

Imports the Valorant notes from a local **Obsidian vault** into this repo so
Docusaurus can build them. The vault is the source of truth; everything this
script writes under `docs/` and `static/screenshots/` is **generated output** —
don't edit it by hand, it gets overwritten on the next run.

The import is one-directional (vault → repo) and is run manually.

## What it does

Each run follows a strict order, so that nothing in the repo is mutated until
the whole import is known to be satisfiable:

1. **Renders the incoming documents** into a temp directory — rewriting Obsidian
   embeds `![[Pasted image X.png]]` into raw
   `<img src="/screenshots/X.avif" alt="X.avif" loading="lazy" />` tags,
   prepending `tags: ["valorant"]` frontmatter, and optionally running Prettier
   (`enable_markdown_auto_format`).
2. **Combines them with the site documents this run does not generate** (for
   example the Sage Ice Walls pages) and derives the complete set of screenshots
   the site will reference. The set has to come from these *prospective*
   documents: a newly added screenshot is referenced only by incoming markdown,
   never by the current contents of `docs/`.
3. **Preflights, and fails before writing anything** on a referenced screenshot
   with no vault source, two vault files reducing to the same name, or two
   outputs differing only by case. With `copy_screenshots = false` nothing will
   be converted, so it additionally requires every referenced screenshot to
   already be in the repo.
4. **Converts** every required screenshot to AVIF (when `copy_screenshots =
   true`). Originals stay PNG in the vault; only the repo copy is converted.
   A screenshot is reconverted when the vault source's **content** no longer
   matches what produced the repo copy, so an image edited in place does not go
   stale. Timestamps are deliberately not used: git does not preserve mtimes, so
   after a fresh checkout a source edited earlier would look "older" than its own
   output. The mapping lives in `screenshot_manifest.json`, which is committed
   for exactly that reason. Changing quality, subsampling or speed also
   reconverts, rather than leaving a mix of settings.
   AVIF 4:4:4 is deliberate: lossy WebP is always 4:2:0 chroma, which visibly
   desaturates the thin green crosshair at every quality level. See the module
   docstring in [`images.py`](images.py) for the measured rationale.
5. **Swaps in the documents and removes stale screenshots** — only once every
   image is in place. Deletions are guarded to stay inside the repo, and only
   image files are removed; anything else is left alone and reported.
6. **Validates both directions**: every referenced screenshot exists on disk,
   and nothing unreferenced is left behind.

> Screenshots referenced by hand-maintained pages are picked up automatically in
> step 2 — there is no list of protected files to keep in sync. A hand-written
> tag that points at a missing image fails the preflight in step 3 rather than
> 404ing silently in production.

> Raw `<img>` tags are used instead of Markdown `![](...)` on purpose: Markdown
> images get pulled through Docusaurus's webpack asset pipeline, which duplicates
> every screenshot and spikes build RAM/disk. See the docstring in
> [`utilities.py`](utilities.py) for details.

## Requirements

- **Python 3.14+** (see [`pyproject.toml`](pyproject.toml)).
- [**uv**](https://docs.astral.sh/uv/) — required, for **Pillow** (screenshot
  conversion) alongside the `mypy` and `pytest` dev dependencies.
- **Prettier** via `npx prettier`, only if `enable_markdown_auto_format = true`.
- Windows is assumed (Prettier is invoked as `npx.cmd`; example paths use `E:/`).

## Tests

```sh
uv run pytest
```

## Setup

Create your local config from the example and edit the paths to match your vault:

```sh
cp example_app.conf app.conf
```

`app.conf` is gitignored — it holds machine-specific absolute paths. Keys:

| Key | Description |
| --- | --- |
| `obsidian_screenshots_directory` | Vault attachments folder (source images) |
| `obsidian_markdown_dir` | Vault folder with the source Markdown notes |
| `git_screenshots_directory` | Target: `static/screenshots/` in this repo |
| `git_markdown_directory` | Target: the docs folder in this repo |
| `enable_markdown_auto_format` | Run Prettier on copied Markdown (`true`/`false`) |
| `copy_screenshots` | Convert/prune screenshots (`true`/`false`) |

## Usage

```sh
# from this directory (scripts/obsidian-import)
uv sync          # one-time: create the venv / install dev deps
python import_vault.py
```

Then build the site from the repo root with `npm run build` to verify, and
commit the regenerated `docs/` and `static/screenshots/` changes.
