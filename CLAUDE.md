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
uv run --env-file .env tools/add.py <url> --publisher vanguard --title "..." --published 2026-09 [--kind ...] [--file <local>] [--canonical-url ...] [--notes ...]
uv run --env-file .env tools/check.py
uv run tools/test_ids.py
uv run tools/test_tools.py
```

- Use `--file` with a rendered DOM saved via chrome-devtools-mcp (`evaluate_script` -> `document.documentElement.outerHTML`, written to a scratch file) when the site blocks scripts, renders with JS, or shows a consent wall.
- Take the date from the document itself before running `add.py`.
- Undo a bad add before commit: `rm -r sources/<publisher>/<id>` plus `uv run --env-file .env python -c "import os,shutil,sys;sys.excepthook=lambda t,e,b:print('failed:',getattr(e,'strerror',None));shutil.rmtree(os.path.join(os.environ['DATA_PATH'],'tr-learn',sys.argv[1]))" sources/<publisher>/<id>` (OneDrive may refuse to delete the empty folder: leave it).
- After adding, rewrite that source's theme README row to `[<Title>](../../sources/<publisher>/<id>/transcription.md) · [original](<artifact url>)`; the `[original]` link keeps the artifact URL.

## Finding a source

- Search order: another Vanguard URL > third-party copy of the same document > Wayback (`/web/<ts>id_/<url>`) > newer edition.
- Always confirm title/date/edition from the document. `--notes` names the dead artifact URL and where the copy was fetched.
- Mirror host with no official URL: `--canonical-url` = the mirror, plus a note.
- Publisher folder = publisher of the archived document (a third-party copy of a Vanguard paper is `vanguard`).
- A date that is only a site-wide page stamp means undated (`published: null`).
- Unarchived (no sidecar, so `check.py` cannot see them; theme README rows only): reading 10 "Manage risk with a global market-cap-weighted portfolio" (https://nl.vanguard/professional/insights/market-commentary/manage-risk-with-a-global-market-cap-weighted-portfolio); 11 "A case for global equity diversification" (https://www.vanguard.ca/content/dam/intl/americas/canada/en/documents/CHBP_062023_ENG_SECURED.pdf); 18 "Tuning the frequency for rebalancing" (https://externalcrewnet.vanguard.com/content/corporatesite/us/en/corp/articles/tuning-frequency-for-rebalancing.html); 25 "Celebrating Vanguard Advisor's Alpha: 25 years" (https://advisors.vanguard.com/insights/article/celebrating-25-years-of-working-to-improve-outcomes-for-you-and-your-clients).

## Transcription workflow

1. Copy the original to a scratch dir without printing `DATA_PATH`: `uv run --env-file .env python -c "import os,shutil,sys;sys.excepthook=lambda t,e,b:print('failed:',getattr(e,'strerror',None));shutil.copy(os.path.join(os.environ['DATA_PATH'],'tr-learn',sys.argv[1]),sys.argv[2])" <original.path> <scratch file>`.
2. Read all of it. PDF: extract with `PYTHONUTF8=1 uv run --with pymupdf python ...` (the Read tool's PDF mode lacks poppler here).
3. Write the body below the front-matter (never edited): faithful clean Markdown, original headings kept, tables as pipe tables, each figure as a blockquote:
   `> **Figure N** (p. X). Caption.` then a line describing what it shows. Videos: the published transcript or a short content note.
   - Values read off an unlabeled chart go only in prose marked "approx."/"about"; pipe tables only for printed numbers. Printed errors are kept and flagged in the caption.
   - Omitted legal pages: `> Pages X–Y (<what>) omitted.`
   - HTML figures use `(web)` instead of a page; describe them from the fetched image, never archive it.
4. Run `check.py` (that source's warning disappears) and commit `sources/<publisher>/<id>/transcription.md`.

## Backlog

`check.py` warnings (`empty transcription body`) = untranscribed sources.
