# obsidian-import

Imports the Valorant notes from a local **Obsidian vault** into this repo so
Docusaurus can build them. The vault is the source of truth; everything this
script writes under `docs/` and `static/screenshots/` is **generated output** —
don't edit it by hand, it gets overwritten on the next run.

The import is one-directional (vault → repo) and is run manually.

## What it does

For each run it:

1. **Scans for unused screenshots** — warns about images in the vault's
   attachments folder that no Markdown file references (skipping any listed in
   `protected_markdown_files`).
2. **Copies screenshots** (when `copy_screenshots = true`) from the vault into
   `static/screenshots/`, stripping the `Pasted image ` prefix. Screenshots in
   the target dir that are no longer referenced (and not protected) are deleted
   first. Deletions are guarded to stay inside the repo.
3. **Copies Markdown** from the vault into the docs dir, and for each file:
   - rewrites Obsidian embeds `![[Pasted image X.png]]` into raw
     `<img src="/screenshots/X.png" alt="X.png" />` tags,
   - prepends `tags: ["valorant"]` frontmatter,
   - optionally runs Prettier (`enable_markdown_auto_format`).

> Raw `<img>` tags are used instead of Markdown `![](...)` on purpose: Markdown
> images get pulled through Docusaurus's webpack asset pipeline, which duplicates
> every screenshot and spikes build RAM/disk. See the docstring in
> [`utilities.py`](utilities.py) for details.

## Requirements

- **Python 3.14+** (see [`pyproject.toml`](pyproject.toml)). The script itself
  uses only the standard library.
- [**uv**](https://docs.astral.sh/uv/) for the dev environment (optional — only
  needed for the `mypy` type-check dependency).
- **Prettier** via `npx prettier`, only if `enable_markdown_auto_format = true`.
- Windows is assumed (Prettier is invoked as `npx.cmd`; example paths use `E:/`).

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
| `copy_screenshots` | Copy/prune screenshots (`true`/`false`) |
| `protected_markdown_files` | *(optional)* Files whose screenshots are exempt from unused-warnings and deletion |

## Usage

```sh
# from this directory (scripts/obsidian-import)
uv sync          # one-time: create the venv / install dev deps
python import_vault.py
```

Then build the site from the repo root with `npm run build` to verify, and
commit the regenerated `docs/` and `static/screenshots/` changes.
