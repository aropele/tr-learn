# tr-learn

## Purpose

Archive of investing references for personal study and for feeding LLM tools. Never cited as proof.
Spec: `docs/superpowers/specs/2026-10-15-tr-learn-archive-design.md`.

## Layout and conventions

- `sources/<publisher>/<id>/` holds `source.json` + `transcription.md`; `themes/<theme>/README.md` are curated reading paths linking to sources; `tools/` holds `add.py`, `check.py`, tests.
- Originals are NOT in git. They live under `$DATA_PATH/tr-learn/`, mirroring the repo path. `DATA_PATH` comes from `.env`, never hardcoded.
- `.env` holds secrets: never read, cat, grep or print it; never print `DATA_PATH`'s value. Pass it with `uv run --env-file .env`.
- Id `YYYY-MM-DD-<slug>`. Unknown month/day is `00`, never an invented `01`. Undated: fetch date and `"published": null`. Slug: lowercase ASCII, non-alphanumerics to `-`, apostrophes removed, stopwords `a an the of for and` dropped, hyphens collapsed, at most 70 chars cut at a word boundary. Existing ids are never overwritten.
- `source.json` fields: id, title, publisher, authors, published (`YYYY`, `YYYY-MM`, `YYYY-MM-DD` or null), kind (`pdf|html|video|summary`), url, canonical_url, fetched_at, original (`{path, sha256}`, path relative to `$DATA_PATH/tr-learn/`; null for videos), notes.
- `transcription.md` starts with a front-matter block generated from the sidecar (id, title, publisher, published, url, `original_prevails: true`). Never edit it by hand; `check.py` compares it.
- The original prevails on any divergence. No images: each figure = caption + text description + page reference.
- Everything in English (the Italian artifact is translated).
- Python stdlib only, always via `uv run`, never bare `python`. Run from the repo root.
- Stage explicit paths only (no `git add -A`, `.`, or `commit -a`). Work on `main`.

## Add a source

```
uv run --env-file .env tools/add.py <url> --publisher vanguard --title "..." --published 2026-09 [--kind ...] [--file <local>] [--canonical-url ...]
uv run --env-file .env tools/check.py
uv run tools/test_ids.py
```

- Use `--file` with a rendered DOM saved via chrome-devtools-mcp (`evaluate_script` -> `document.documentElement.outerHTML`, written to a scratch file) when the site blocks scripts, renders with JS, or shows a consent wall.
- Take the date from the document itself before running `add.py`.
- Undo a bad add before commit: `rm -r sources/<publisher>/<id>` plus `uv run --env-file .env python -c "import os,shutil,sys;shutil.rmtree(os.path.join(os.environ['DATA_PATH'],'tr-learn',sys.argv[1]))" sources/<publisher>/<id>`.

## Transcription workflow

1. Copy the original to a scratch dir without printing `DATA_PATH`: `uv run --env-file .env python -c "import os,shutil,sys;shutil.copy(os.path.join(os.environ['DATA_PATH'],'tr-learn',sys.argv[1]),sys.argv[2])" <original.path> <scratch file>`.
2. Read all of it (PDF: Read tool, `pages` in chunks of <=20).
3. Write the body below the front-matter (never edited): faithful clean Markdown, original headings kept, tables as pipe tables, each figure as a blockquote:
   `> **Figure N** (p. X). Caption.` then a line describing what it shows. Videos: the published transcript or a short content note.
4. Run `check.py` (that source's warning disappears) and commit `sources/<publisher>/<id>/transcription.md`.

## Backlog

`check.py` warnings (`empty transcription body`) = untranscribed sources.
