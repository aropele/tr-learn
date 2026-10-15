# tr-learn: investing references archive — design

Date: 2026-10-15 · Status: approved in brainstorming, pending spec review

## Goal

Archive investing references so they can be **studied** (personal study, never cited as proof) and **fed to LLM tools** (RAG, podcast, etc.). Each source keeps its original, a metadata sidecar and a curated Markdown transcription. First collection: Vanguard research on portfolio construction, taken from the Claude Doc "Costruire un portafoglio secondo Vanguard – Fonti per advisor" (https://claude.ai/code/artifact/ae1a8ac8-3a2f-4821-ad76-77022b215b7f, 2026-10-14, 26 readings).

Out of scope: ADRs, citation rigor ("coverage read" tracking), figure images, automatic transcription, search/indexing.

## Decisions

| Topic | Decision |
|---|---|
| Layers | `sources/` (what exists, one folder per document, by publisher) and `themes/` (curated study paths linking to sources, many-to-many) |
| Originals | Not in git. Stored under `$DATA_PATH/tr-learn/` (OneDrive), mirroring the repo path. `DATA_PATH` is read from `.env`, never hardcoded |
| In git | `source.json` sidecars, `transcription.md`, themes, tools, `CLAUDE.md` |
| Transcriptions | Curated by Claude from the original; clean Markdown; the original prevails on any divergence |
| Figures | No images. Each figure = caption + text description of what it shows + page reference |
| Language | Everything in English (transcriptions, repo docs, theme READMEs; the Italian artifact is translated) |

## Layout

```
tr-learn/  (git)                                   $DATA_PATH/tr-learn/  (OneDrive)
├─ sources/<publisher>/<id>/                       └─ sources/<publisher>/<id>/
│   ├─ source.json        ── original.path ──────►      original.pdf | original.html
│   └─ transcription.md
├─ themes/<theme>/README.md
├─ tools/add.py, check.py, test_ids.py
├─ CLAUDE.md
└─ .gitignore              (.env)
```

The publisher folder is the publisher of the **archived document** (a PlanSponsor summary of a Vanguard paper goes under `plansponsor/`).

## Id convention

`YYYY-MM-DD-<slug>`

- Date = publication date. Unknown month/day → `00` (`2022-00-00-…`), never an invented `01`.
- Undated document → fetch date, and `"published": null` in the sidecar.
- Slug from the full title: lowercase ASCII, non-alphanumerics → `-`, apostrophes removed (`vanguard's` → `vanguards`), stopwords `a an the of for and` dropped, collapsed hyphens, at most 70 characters cut at a word boundary.
- A new edition of the same document gets a new id; existing ids are never overwritten.

Example: `2024-09-00-vanguard-asset-allocation-model-investment-solution-active-passive-factor`.

## `source.json` (source of truth for metadata)

```json
{
  "id": "2026-09-00-vanguard-capital-markets-model",
  "title": "Vanguard Capital Markets Model",
  "publisher": "vanguard",
  "authors": [],
  "published": "2026-09",
  "kind": "pdf",
  "url": "https://corporate.vanguard.com/content/dam/corp/research/pdf/vanguard_capital_markets_model.pdf",
  "canonical_url": null,
  "fetched_at": "2026-10-15T09:30:00Z",
  "original": { "path": "sources/vanguard/2026-09-00-vanguard-capital-markets-model/original.pdf", "sha256": "…" },
  "notes": ""
}
```

- `published`: `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or `null`.
- `kind`: `pdf | html | video | summary`.
- `url`: where it was fetched from. `canonical_url`: the official URL when fetched from a mirror (`externalcrewnet.vanguard.com`, `corpaemdisp.essp.c1.vanguard.com`), else `null`.
- `original.path`: relative to `$DATA_PATH/tr-learn/`. `original` is `null` for videos.
- `notes`: free text (e.g. "summary of Vanguard paper X, original not found").

## `transcription.md`

Front-matter copied from the sidecar (written together by `add.py`, compared by `check.py`):

```markdown
---
id: 2026-09-00-vanguard-capital-markets-model
title: Vanguard Capital Markets Model
publisher: vanguard
published: 2026-09
url: https://corporate.vanguard.com/…
original_prevails: true
---
```

Body: faithful, clean Markdown of the original. It keeps the original headings and turns tables into pipe tables. Each figure is written as:

```markdown
> **Figure 3** (p. 7). Return vs. volatility for monthly / quarterly / annual / threshold rebalancing.
> Annual sits on the efficient edge; monthly adds cost with no risk reduction.
```

Videos: the published transcript if the page offers one, otherwise a short note on the content.

## Tools (Python stdlib only, run with uv)

```
uv run --env-file .env tools/add.py <url> --publisher vanguard --title "…" --published 2026-09 [--kind …] [--file <local>] [--canonical-url …]
uv run --env-file .env tools/check.py
uv run tools/test_ids.py
```

**`add.py`**
- Stops if `DATA_PATH` is unset or the id folder already exists in either tree.
- Downloads `<url>` (browser User-Agent), or ingests `--file` when the site blocks scripts or renders with JS. In that case, save the rendered DOM with chrome-devtools first.
- Infers `kind` from content-type unless given.
- Writes the original via a temp file then a move, computes sha256, and writes `source.json` and a `transcription.md` that holds only front-matter.
- `--kind video` skips the download.

**`check.py`** — for every `source.json`:
- id matches its folder name and the id rule;
- original exists under `DATA_PATH` and its sha256 matches (skipped when `original` is `null`);
- transcription front-matter equals the sidecar fields;
- empty transcription body → warning (backlog), not an error.

Exit 1 with a list of problems if any error.

**`test_ids.py`** — assert-based checks of the slug/id rules: stopwords, apostrophes, `00` padding, the 70-char cut, `null` published → fetch date.

## Theme: `themes/portfolio-construction/README.md`

- Header: "Curated reading path generated with Claude on 2026-10-14 from <artifact URL>; an index, not a source."
- Body: the artifact translated to English, with all 6 phases and their tables (#, Reading, Year, Why it matters / Key message), "Training for advisors", and "Recommended order if short on time: 1 → 5 → 6 → 12 → 13 → 14 → 18 → 24".
- Each reading links to `../../sources/<publisher>/<id>/transcription.md` and keeps its original URL.
- The reading-path widget becomes a one-line phase list.

## First batch (the 26 readings)

| Kind | Readings | Handling |
|---|---|---|
| Vanguard PDF | 1, 3, 4, 5, 6, 9, 11, 12, 13, 16, 19, 21 | `add.py <url>` |
| Vanguard HTML | 2, 7, 10, 14, 15, 18, 20, 25 | `add.py`; if the raw HTML is empty or a consent wall, use rendered DOM + `--file` |
| Video | 8, 26 | `--kind video`, no original |
| Third-party summary | 17, 22, 23 | First search for the Vanguard original. If found, archive it under `vanguard/` and mention the summary in `notes`. Otherwise archive the summary under its own publisher with `kind: summary` |

Dates and titles come from the artifact, corrected from the document itself when it shows a more precise date.

## Scope of this implementation

1. Repo skeleton: `CLAUDE.md` (conventions + transcription workflow), `.gitignore`, `tools/`.
2. `add.py`, `check.py`, `test_ids.py`.
3. Archive all 26 readings (sidecars + originals in `DATA_PATH`).
4. Theme README.
5. Transcribe the 8 priority readings: 1, 5, 6, 12, 13, 14, 18, 24.

Later, one session each: the remaining 18 transcriptions, following the `CLAUDE.md` workflow. `check.py` keeps the backlog visible.

## Success criteria

- `check.py` exits 0 with 18 empty-body warnings, and `test_ids.py` passes.
- Every theme link resolves to an existing `transcription.md`.
- No original, `.env` content or absolute OneDrive path appears in git.
