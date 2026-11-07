# Mingo-Notes

Source for [notes.mingodynasty.com](https://notes.mingodynasty.com), a
[Docusaurus](https://docusaurus.io/) site of game notes (Street Fighter 6 and Valorant).

## Where the pages come from

- **Generated, do not hand-edit:** `docs/Valorant/Sage Ice Orbs/` and `static/screenshots/`
  (with `scripts/obsidian-import/screenshot_manifest.json`). The
  [Obsidian importer](scripts/obsidian-import/README.md) writes them from the maintainer's
  vault, and the next import overwrites any hand edit. It is run by hand; its README covers
  setup, what a run does and the checks it makes.
- **Hand-maintained:** every other page under `docs/`, which means the home page, `SF6/`,
  `Valorant/Game Sense.md`, `Valorant/Sage Ice Walls/` and the KillJoy page (PR #13).
  An import neither refreshes nor removes these, even when their text started in the vault,
  so copy later vault edits over by hand.
- The screenshots that hand-maintained pages show also live in `static/screenshots/`, and
  the importer manages them too (see its README).

## Local development

```bash
npm ci
npm run start   # dev server with live reload
npm run build   # static site into build/
npm run serve   # serve build/ locally
```

Steam holds port 8080 on the maintainer's machine. If a local server will not start or
answers 404, pick another port, for example `npm run serve -- --port 3417`.

## Before opening a pull request

Run all four gates:

```bash
npm run typecheck
npm run build                  # fails on a broken link (onBrokenLinks: "throw")
cd scripts/obsidian-import
uv run pytest
uv run mypy .
```

## Deployment

**Production is a Cloudflare Worker with static assets, not Cloudflare Pages.**
`npm run deploy` builds the site and runs `wrangler deploy`, which uploads `build/` to the
`mingo-notes` Worker on the custom domain `notes.mingodynasty.com` (see
[`wrangler.jsonc`](wrangler.jsonc)). It needs a Wrangler login to the Cloudflare account.
GitHub shows no Cloudflare build on recent commits, so a merge to `main` is not expected to
reach production until someone runs `npm run deploy`. `npm run preview` builds and runs the Worker
locally with `wrangler dev`.

**Netlify is also connected to this repository.** It is configured in Netlify's dashboard;
the repository has no `netlify.toml`. What has been observed (2026-11-07):

- Netlify posts a `netlify/mingo-notes/deploy-preview` status on pull requests, linking a
  preview at `deploy-preview-<number>--mingo-notes.netlify.app`. The preview succeeded on
  PRs #5 to #14 and failed on PRs #2 to #4; PR #1 has no status.
- A public copy of the site is served at <https://mingo-notes.netlify.app>. It served the
  same 24 routes as production, and its canonical links point at `notes.mingodynasty.com`.

Whether Netlify republishes that copy by itself when `main` changes is a Netlify setting
that this repository does not record. The copy is not the production site.
