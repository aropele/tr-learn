# tr-learn Investing References Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A git archive of investing references (sidecar + curated transcription per source, originals on OneDrive), seeded with the 26 Vanguard portfolio-construction readings, 8 of them transcribed.

**Architecture:** Two stdlib Python scripts: `tools/add.py` ingests one source (originals go to `$DATA_PATH/tr-learn/`, metadata goes to the repo), and `tools/check.py` checks the archive's integrity. One theme README turns the Claude Doc artifact into an English reading path linking to the sources. Transcriptions are written by hand (by Claude) under front-matter that `add.py` generates.

**Tech Stack:** Python >=3.11 stdlib only (`urllib`, `hashlib`, `json`, `re`, `unicodedata`, `mimetypes`, `tempfile`), run with `uv run` as PEP 723 scripts (no `pyproject.toml`). Assert-based test scripts, no pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-tr-learn-archive-design.md`. Read it before any task.

## Global Constraints

- Originals are not in git. They go under `$DATA_PATH/tr-learn/` (OneDrive), mirroring the repo path. `DATA_PATH` is read from `.env`, never hardcoded.
- In git: `source.json` sidecars, `transcription.md`, themes, tools, `CLAUDE.md`.
- The original prevails on any divergence. No images: each figure = caption + text description of what it shows + page reference.
- Everything in English (transcriptions, repo docs, theme READMEs; the Italian artifact is translated).
- Id `YYYY-MM-DD-<slug>`. Unknown month/day → `00`, never an invented `01`. Undated → fetch date, and `"published": null`. Slug: lowercase ASCII, non-alphanumerics → `-`, apostrophes removed, stopwords `a an the of for and` dropped, collapsed hyphens, at most 70 characters cut at a word boundary. Existing ids are never overwritten.
- `published`: `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or `null`. `kind`: `pdf | html | video | summary`. `original.path` is relative to `$DATA_PATH/tr-learn/`. `original` is `null` for videos.
- Python stdlib only, run with uv. Never call bare `python`; inline snippets use `uv run python -c "..."`.
- Run every command from the repo root `C:\Users\user\home\quant2\tr\tr-learn` (Git Bash: `/c/Users/user/home/quant2/tr/tr-learn`).
- `.env` holds secrets: never read, cat, grep or print it; never print the value of `DATA_PATH`. Pass it to scripts with `uv run --env-file .env`.
- Stage explicit paths only. Never `git add -A`, `git add .` or `git commit -a`.
- Commit messages: `<type>(<scope>): <why>`, subject <=72 chars, no `Co-Authored-By`, no names, no generated-by markers.
- Work in place on branch `main`.

## Review Focus

1. **A PDF URL that answers 200 with an HTML block or consent page.** `add.py` must refuse rather than archive a fake PDF (Task 2, `test_pdf_url_returning_html_is_refused`).
2. **A download that fails halfway (HTTP 403, timeout).** No folder may be left in either tree, or the re-run is blocked by "id exists" (Task 2, `test_failed_download_leaves_nothing`).
3. **Typographic apostrophes, accents and dashes in real titles** (`Vanguard’s`, `—`, `é`). The slug must still follow the rule (Task 1, `test_unicode_title`).
4. **A mirror URL ingested without `--canonical-url`.** `add.py` must refuse, so a mirror never becomes the only URL on record (Task 2, `test_mirror_without_canonical_is_refused`).
5. **A date corrected in `source.json` after ingestion, or `check.py` run without `DATA_PATH`.** `check.py` must report the id/date mismatch, and must fail with one clear message instead of reporting 26 missing originals (Task 3, `test_id_date_mismatch_is_error`, `test_missing_data_path_fails`).

---

## File Structure

| Path | Responsibility |
|---|---|
| `.gitignore` | `.env`, `__pycache__/` |
| `tools/add.py` | id/slug rules + ingestion of one source |
| `tools/check.py` | integrity check of all sidecars, transcriptions, theme links |
| `tools/test_ids.py` | assert-based slug/id rule checks (spec) |
| `tools/test_tools.py` | assert-based offline checks of `add.run` and `check.py` (added by this plan: the spec names no test for them) |
| `CLAUDE.md` | conventions + add-a-source workflow + transcription workflow |
| `themes/portfolio-construction/README.md` | English reading path, links to sources |
| `sources/<publisher>/<id>/source.json`, `transcription.md` | one per reading |

`check.py` imports from `add.py` (`from add import ...`). This works because `uv run tools/x.py` puts `tools/` on `sys.path`. Every script starts with this PEP 723 header:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
```

---

### Task 1: Repo ignore rules and id/slug rules

**Files:**
- Create: `.gitignore`
- Create: `tools/add.py` (helpers only, in this task)
- Test: `tools/test_ids.py`

**Interfaces:**
- Produces (in `tools/add.py`):
  - `STOPWORDS = {"a", "an", "the", "of", "for", "and"}`, `MAX_SLUG = 70`
  - `ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")`
  - `PUBLISHED_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")`
  - `slugify(title: str) -> str`. Raises `ValueError` when the result is empty.
  - `date_part(published: str | None, fetch_date: str) -> str`. `fetch_date` is `YYYY-MM-DD`. Raises `ValueError` if `published` is not `None` and fails `PUBLISHED_RE`.
  - `make_id(title: str, published: str | None, fetch_date: str) -> str` = `f"{date_part(...)}-{slugify(title)}"`

- [ ] **Step 1: Write `.gitignore`**

```
.env
__pycache__/
```

Verify: `git check-ignore .env` prints `.env`.

- [ ] **Step 2: Write the failing tests in `tools/test_ids.py`**

Plain functions named `test_*`, plus a `__main__` block that calls each one and prints `ok`. Assertions:

```python
from add import slugify, date_part, make_id, ID_RE, MAX_SLUG

def test_stopwords():
    assert slugify("The Case for Index-Fund Investing") == "case-index-fund-investing"
    assert slugify("A  Guide -- of  the   Things") == "guide-things"

def test_apostrophes():
    assert slugify("Vanguard's Principles for Investing Success") == "vanguards-principles-investing-success"

def test_unicode_title():
    assert slugify("Vanguard\u2019s Principles for Investing Success") == "vanguards-principles-investing-success"
    assert slugify("Risk\u2014return in Z\u00fcrich") == "risk-return-in-zurich"

def test_70_char_cut():
    s = slugify("Vanguard Asset Allocation Model: An investment solution for active, passive, and factor portfolios")
    assert s == "vanguard-asset-allocation-model-investment-solution-active-passive"
    assert len(s) <= MAX_SLUG
    assert len(slugify("x" * 80)) == 70          # single over-long word: hard cut

def test_00_padding():
    assert date_part("2022", "2026-10-15") == "2022-00-00"
    assert date_part("2026-09", "2026-10-15") == "2026-09-00"
    assert date_part("2024-03-05", "2026-10-15") == "2024-03-05"
    assert make_id("Vanguard Capital Markets Model", "2026-09", "2026-10-15") == "2026-09-00-vanguard-capital-markets-model"

def test_null_published_uses_fetch_date():
    assert date_part(None, "2026-10-15") == "2026-10-15"
    assert make_id("Some Page", None, "2026-10-15") == "2026-10-15-some-page"

def test_invalid_input_rejected():
    for bad in ("2026-9", "Sept 2026", "2026-09-1"):
        try: date_part(bad, "2026-10-15"); assert False, bad
        except ValueError: pass
    try: slugify("The of a"); assert False
    except ValueError: pass

def test_ids_match_rule():
    assert ID_RE.match(make_id("Vanguard's Principles", "2022", "2026-10-15"))
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run tools/test_ids.py`
Expected: `ModuleNotFoundError: No module named 'add'` (or ImportError).

- [ ] **Step 4: Implement the helpers in `tools/add.py`**

`slugify` order matters. Remove `'` and `\u2019` first. Then NFKD-normalize, drop `unicodedata.combining` chars, lowercase, and `re.sub(r"[^a-z0-9]+", "-", ...)`. Split on `-` and drop empties and stopwords. Then cut:

```python
out = []
for w in words:
    if len("-".join(out + [w])) > MAX_SLUG:
        break
    out.append(w)
slug = "-".join(out) or (words[0][:MAX_SLUG] if words else "")
```

Note: the spec's example id (`…-active-passive-factor`) has a 73-char slug. This plan follows the 70-char rule, not the example.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run tools/test_ids.py`
Expected: `ok`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add .gitignore tools/add.py tools/test_ids.py
git commit -m "feat(tools): pin id/slug rules so ids never need renaming"
```

---

### Task 2: `add.py` ingestion

**Files:**
- Modify: `tools/add.py`
- Test: `tools/test_tools.py`

**Interfaces:**
- Consumes: `make_id`, `PUBLISHED_RE` from Task 1.
- Produces (in `tools/add.py`):
  - `MIRROR_HOSTS = ("externalcrewnet.vanguard.com", "corpaemdisp.essp.c1.vanguard.com")`
  - `BROWSER_UA` = a current desktop Chrome User-Agent string.
  - `FM_FIELDS = ("id", "title", "publisher", "published", "url")`
  - `front_matter(meta: dict) -> str`. Returns exactly `"---\n" + "".join(f"{k}: {v}\n")` for each `FM_FIELDS` key (`None` rendered as `null`) `+ "original_prevails: true\n---\n"`.
  - `infer_kind(url: str, content_type: str, data: bytes) -> str`. Returns `"pdf"` if `data` starts with `b"%PDF-"`. Raises `ValueError` if the URL path ends in `.pdf` but the data is not a PDF ("expected a PDF, got <content_type>; save it in a browser and pass --file"). Returns `"html"` if `content_type` contains `html`. Otherwise raises `ValueError` ("cannot infer kind from <content_type>; pass --kind").
  - `run(argv: list[str], repo_root: Path, data_root: Path) -> Path`. Parses args, ingests, returns the repo source dir. `data_root` is `$DATA_PATH/tr-learn`. Any refusal is `sys.exit("<message>")`.
  - `main() -> None`: `sys.exit("DATA_PATH is not set; run with uv run --env-file .env")` if unset. Otherwise `run(sys.argv[1:], Path(__file__).resolve().parent.parent, Path(os.environ["DATA_PATH"]) / "tr-learn")`, then print the id.
- CLI (argparse): positional `url`; `--publisher` (required, must match `^[a-z0-9]+(-[a-z0-9]+)*$`), `--title` (required), `--published` (optional, default `None`), `--kind {pdf,html,video,summary}`, `--file PATH`, `--canonical-url`, `--notes` (default `""`; the spec needs notes for summaries but has no flag for them).

`run` order (fetch everything before creating anything, so a failure leaves no folder):
1. Validate `--published` and `--publisher`. Refuse if the URL host is in `MIRROR_HOSTS` and `--canonical-url` is missing ("fetched from a mirror; pass --canonical-url"). Refuse `--file` together with `--kind video`.
2. `fetched_at` = UTC now as `%Y-%m-%dT%H:%M:%SZ`. `id = make_id(title, published, fetched_at[:10])`.
3. Refuse if `repo_root/sources/<publisher>/<id>` or `data_root/sources/<publisher>/<id>` exists.
4. If not video: get `data` + `content_type`. With `--file`: read bytes, `mimetypes.guess_type`. Otherwise: `urllib.request` with `BROWSER_UA`, timeout 60. Turn `HTTPError`/`URLError` into `sys.exit(f"download failed ({err}); save the page in a browser and pass --file")`. `kind = args.kind or infer_kind(...)`. `ext = "pdf" if data.startswith(b"%PDF-") else "html"`.
5. Write `data_root/sources/<publisher>/<id>/original.<ext>`: `tempfile.NamedTemporaryFile(dir=<that dir>, delete=False)`, then `os.replace`. Take `sha256` of `data`.
6. Write `source.json` with the spec's key order: `id, title, publisher, authors=[], published, kind, url, canonical_url, fetched_at, original={"path": "sources/<publisher>/<id>/original.<ext>", "sha256": …} or None, notes`. Use `json.dumps(indent=2, ensure_ascii=False) + "\n"`. Write `transcription.md` = `front_matter(sidecar)`. Both with `encoding="utf-8", newline="\n"`. `original.path` always uses `/`.

- [ ] **Step 1: Write the failing tests in `tools/test_tools.py`**

Same assert-script style as `test_ids.py`. Each test builds `repo, data = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())`.

```python
from add import run, infer_kind, front_matter

def test_video_writes_sidecar_and_front_matter():
    d = run(["https://www.youtube.com/watch?v=x", "--publisher", "vanguard",
             "--title", "Some Video", "--kind", "video"], repo, data)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert d == repo / "sources/vanguard" / meta["id"] and meta["original"] is None
    assert meta["published"] is None and meta["id"].startswith(meta["fetched_at"][:10])
    assert list(meta) == ["id","title","publisher","authors","published","kind","url",
                          "canonical_url","fetched_at","original","notes"]
    assert (d / "transcription.md").read_text(encoding="utf-8") == front_matter(meta)
    assert not (data / "sources").exists()

def test_file_ingest_writes_original_and_sha():
    f = tmp / "x.pdf"; f.write_bytes(b"%PDF-1.4 test")
    d = run(["https://corporate.vanguard.com/x.pdf", "--publisher", "vanguard", "--title",
             "Vanguard Capital Markets Model", "--published", "2026-09", "--file", str(f)], repo, data)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert meta["id"] == "2026-09-00-vanguard-capital-markets-model" and meta["kind"] == "pdf"
    assert meta["original"]["path"] == "sources/vanguard/2026-09-00-vanguard-capital-markets-model/original.pdf"
    assert (data / meta["original"]["path"]).read_bytes() == b"%PDF-1.4 test"
    assert meta["original"]["sha256"] == hashlib.sha256(b"%PDF-1.4 test").hexdigest()

def test_existing_id_is_refused():      # second identical file ingest -> SystemExit, first untouched
def test_pdf_url_returning_html_is_refused():
    try: infer_kind("https://x.com/a.pdf", "text/html", b"<html>cookies</html>"); assert False
    except ValueError: pass
    assert infer_kind("https://x.com/page", "text/html; charset=utf-8", b"<html>") == "html"
def test_failed_download_leaves_nothing():
    # run([...'http://127.0.0.1:9/x.pdf'...]) raises SystemExit; neither repo/sources nor data/sources exists
def test_mirror_without_canonical_is_refused():
    # run(['https://externalcrewnet.vanguard.com/x', ..., '--kind', 'video']) raises SystemExit
def test_bad_published_is_refused():    # '--published', '2026-9' -> SystemExit
```

Write out the three commented tests in full. Each asserts `SystemExit` is raised and that the state named in its comment holds.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run tools/test_tools.py`
Expected: ImportError on `run` / `infer_kind` / `front_matter`.

- [ ] **Step 3: Implement `front_matter`, `infer_kind`, `run`, `main` in `tools/add.py`** as specified in the Interfaces block. Add `if __name__ == "__main__": main()`.

- [ ] **Step 4: Run both test scripts**

Run: `uv run tools/test_tools.py && uv run tools/test_ids.py`
Expected: `ok` twice, exit 0.

- [ ] **Step 5: Smoke-test the unset-env guard**

Run: `uv run tools/add.py https://x --publisher vanguard --title T`
Expected: `DATA_PATH is not set; …`, exit 1.

- [ ] **Step 6: Commit**

```bash
git add tools/add.py tools/test_tools.py
git commit -m "feat(tools): ingest a source without leaving partial folders"
```

---

### Task 3: `check.py` and `CLAUDE.md`

**Files:**
- Create: `tools/check.py`
- Modify: `tools/test_tools.py`
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: `ID_RE`, `MAX_SLUG`, `date_part`, `front_matter` from `add.py`.
- Produces (in `tools/check.py`):
  - `check_source(sidecar: Path, data_root: Path) -> tuple[list[str], list[str]]`, returning `(errors, warnings)`, each message prefixed with the id or folder. Checks:
    - `id == sidecar.parent.name`
    - `publisher == sidecar.parent.parent.name`
    - `ID_RE` matches, and slug length (`id[11:]`) `<= MAX_SLUG`
    - `id[:10] == date_part(published, fetched_at[:10])`
    - if `original` is not null: `data_root / original.path` exists and its sha256 matches
    - `transcription.md` exists and its text starts with `front_matter(sidecar)`, else error `front-matter differs from source.json`
    - remaining body `.strip()` empty → warning `empty transcription body`
  - `check_themes(repo_root: Path) -> list[str]`: for each `themes/*/README.md`, every markdown link target `\]\(([^)\s]+)\)` that does not start with `http://`, `https://` or `#` must resolve (relative to the README's folder) to an existing file.
  - `run(repo_root: Path, data_root: Path | None) -> int`. If `data_root` is `None`, prints `DATA_PATH is not set; run with uv run --env-file .env` and returns 1. Otherwise checks every `repo_root/sources/*/*/source.json` and the themes. Prints `ERROR …` / `WARN …` lines, then `<n> errors, <m> warnings`. Returns 1 if there are any errors, else 0.
  - `main()`: `sys.exit(run(ROOT, Path(os.environ["DATA_PATH"]) / "tr-learn" if os.environ.get("DATA_PATH") else None))`.

- [ ] **Step 1: Add failing tests to `tools/test_tools.py`**

Build fixtures with `add.run(... --file <tmp pdf> ...)` from Task 2, then mutate them:

```python
from check import check_source, check_themes, run as check_run

def test_fresh_source_only_warns_empty_body():
    errs, warns = check_source(d / "source.json", data)
    assert errs == [] and len(warns) == 1 and "empty transcription body" in warns[0]

def test_tampered_original_is_error():      # overwrite original bytes -> an error mentioning sha256
def test_missing_original_is_error():       # delete original -> error
def test_front_matter_mismatch_is_error():  # edit title in source.json only -> 'front-matter differs'
def test_id_date_mismatch_is_error():       # set published '2025' in source.json AND rewrite transcription
                                            # front-matter to match -> exactly one error, about id/date
def test_body_present_no_warning():         # append '\n# Heading\ntext\n' to transcription -> ([], [])
def test_theme_link_must_resolve():
    # themes/t/README.md with '[a](../../sources/vanguard/<id>/transcription.md) [b](https://x) [c](../../nope.md)'
    # -> exactly one error, mentioning 'nope.md'
def test_missing_data_path_fails():
    assert check_run(repo, None) == 1
```

Write the commented tests in full.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run tools/test_tools.py`
Expected: ImportError on `check`.

- [ ] **Step 3: Implement `tools/check.py`** as specified in the Interfaces block. Read files with `encoding="utf-8"` in text mode, so CRLF checkouts still compare equal.

- [ ] **Step 4: Run all tests and the real check on the empty archive**

Run: `uv run tools/test_tools.py && uv run tools/test_ids.py && uv run --env-file .env tools/check.py`
Expected: `ok`, `ok`, then `0 errors, 0 warnings`, exit 0. If the last command prints `DATA_PATH is not set`, stop and report: `.env` lacks `DATA_PATH`. Do not open `.env`.

- [ ] **Step 5: Write `CLAUDE.md`**

At most about 80 lines, in English, with these sections:
- **Purpose:** study + LLM feeding, never cited as proof. Spec path.
- **Layout + conventions:** a condensed copy of the Global Constraints above (id rule, sidecar fields, front-matter, figures rule, English, originals only in `DATA_PATH`, `.env` never read/printed, explicit `git add` paths).
- **Add a source:** the three `uv run` commands from the spec. Then:
  - Use `--file` with a rendered DOM saved via chrome-devtools-mcp (`evaluate_script` → `document.documentElement.outerHTML`, written to a scratch file) when the site blocks scripts, renders with JS, or shows a consent wall.
  - Take the date from the document itself before running `add.py`.
  - Undo a bad add before commit: `rm -r sources/<publisher>/<id>` plus `uv run --env-file .env python -c "import os,shutil,sys;shutil.rmtree(os.path.join(os.environ['DATA_PATH'],'tr-learn',sys.argv[1]))" sources/<publisher>/<id>`.
- **Transcription workflow:**
  1. Copy the original to a scratch dir without printing `DATA_PATH`: `uv run --env-file .env python -c "import os,shutil,sys;shutil.copy(os.path.join(os.environ['DATA_PATH'],'tr-learn',sys.argv[1]),sys.argv[2])" <original.path> <scratch file>`.
  2. Read all of it (PDF: Read tool, `pages` in chunks of <=20).
  3. Write the body below the front-matter, which is never edited: faithful clean Markdown, original headings kept, tables as pipe tables, each figure in the spec's `> **Figure N** (p. X). Caption.` + description blockquote format, videos = published transcript or a short content note.
  4. Run `check.py` (that source's warning disappears) and commit `sources/<publisher>/<id>/transcription.md`.
- **Backlog:** `check.py` warnings = untranscribed sources.

- [ ] **Step 6: Commit**

```bash
git add tools/check.py tools/test_tools.py CLAUDE.md
git commit -m "feat(tools): make archive drift and transcription backlog visible"
```

---

### Task 4: Theme README from the artifact (no source links yet)

**Files:**
- Create: `themes/portfolio-construction/README.md`

**Interfaces:**
- Consumes: the Claude Doc artifact `https://claude.ai/code/artifact/ae1a8ac8-3a2f-4821-ad76-77022b215b7f`. It is a Claude Doc: load the `anthropic-skills:docs` skill and read it through the Claude Docs connector. Never web-fetch it. If the connector is unavailable, stop and report BLOCKED.
- Produces: the reading table that Tasks 5–7 consume. One row per reading (26), Reading cell format `<Title> · [original](<artifact URL for that reading>)`. Tasks 5–7 rewrite it to `[<Title>](../../sources/<publisher>/<id>/transcription.md) · [original](<url>)`.

- [ ] **Step 1: Read the whole artifact** and list its 26 readings (number, title, year, URL, phase).

- [ ] **Step 2: Write `themes/portfolio-construction/README.md` in English**, structured as:
  - `# Portfolio construction according to Vanguard`
  - Header line, verbatim: `Curated reading path generated with Claude on 2026-10-14 from https://claude.ai/code/artifact/ae1a8ac8-3a2f-4821-ad76-77022b215b7f; an index, not a source.`
  - The reading-path widget as one line: `Phases: 1 <name> → 2 <name> → … → 6 <name>`
  - All 6 phases as `## Phase N — <name>`, each with the artifact's intro text translated and its table `| # | Reading | Year | Why it matters |`. Use `Key message` instead where the artifact's column means that.
  - `## Training for advisors`, translated.
  - Line verbatim: `Recommended order if short on time: 1 → 5 → 6 → 12 → 13 → 14 → 18 → 24`

- [ ] **Step 3: Verify**

Run: `uv run --env-file .env tools/check.py`
Expected: `0 errors, 0 warnings` (no relative links yet).
Run: `grep -c '\[original\](http' themes/portfolio-construction/README.md`
Expected: `26`.

- [ ] **Step 4: Commit**

```bash
git add themes/portfolio-construction/README.md
git commit -m "docs(themes): translate the Vanguard reading path as the batch index"
```

---

### Tasks 5–7: archive the 26 readings — shared procedure

Apply this procedure to every reading in Tasks 5–7. Read the readings from `themes/portfolio-construction/README.md`:

1. Open the URL (or the downloaded document). Take the full title and the most precise publication date the document shows. Fall back to the README's year when it shows none (`--published YYYY`). Omit `--published` only when the document is truly undated.
2. If the URL host is `externalcrewnet.vanguard.com` or `corpaemdisp.essp.c1.vanguard.com`, find the official URL and pass `--canonical-url`.
3. Run: `uv run --env-file .env tools/add.py <url> --publisher <p> --title "<full title>" [--published …] [--kind …] [--file …] [--canonical-url …] [--notes "…"]`. It prints the id.
4. HTML only: copy the original to scratch (CLAUDE.md one-liner) and confirm it holds the article body (title text and body paragraphs), not a consent wall or an empty JS shell. If it does not, undo the add (CLAUDE.md), save the rendered DOM with chrome-devtools-mcp, and re-add with `--file <scratch>.html --kind html`.
5. Rewrite that reading's README cell to `[<Title>](../../sources/<publisher>/<id>/transcription.md) · [original](<url>)`.
6. After the batch: `uv run --env-file .env tools/check.py` → `0 errors, <archived so far> warnings`.

If a reading cannot be archived (dead URL, no copy obtainable), stop that task and report BLOCKED with the reading number and URL. Do not invent metadata.

### Task 5: Archive the Vanguard PDFs (readings 1, 3, 4, 5, 6, 9, 11, 12, 13, 16, 19, 21)

**Files:**
- Create: `sources/vanguard/<id>/source.json`, `sources/vanguard/<id>/transcription.md` ×12
- Modify: `themes/portfolio-construction/README.md`

**Interfaces:** Consumes `add.py` CLI (Task 2), `check.py` (Task 3), README rows (Task 4).

- [ ] **Step 1: Preflight** — Run: `uv run --env-file .env tools/check.py` → exit 0.
- [ ] **Step 2: Archive the 12 readings** with the shared procedure (`--publisher vanguard`, kind inferred).
- [ ] **Step 3: Verify** — `check.py` → `0 errors, 12 warnings`. `git status --porcelain` lists only `sources/vanguard/…` and the README (plus the pre-existing untracked `.env`, never staged).
- [ ] **Step 4: Commit**

```bash
git add sources/vanguard themes/portfolio-construction/README.md
git commit -m "feat(sources): archive Vanguard PDFs so they can be transcribed"
```

### Task 6: Archive the Vanguard HTML pages (readings 2, 7, 10, 14, 15, 18, 20, 25)

**Files:** as Task 5 (×8).

- [ ] **Step 1: Archive the 8 readings** with the shared procedure, including the step-4 content check on every one.
- [ ] **Step 2: Verify** — `check.py` → `0 errors, 20 warnings`.
- [ ] **Step 3: Commit**

```bash
git add sources/vanguard themes/portfolio-construction/README.md
git commit -m "feat(sources): archive Vanguard web articles with their rendered body"
```

### Task 7: Archive videos, third-party summaries and reading 24

**Files:** `sources/<publisher>/<id>/…` ×6, README.

The spec's First batch table leaves reading 24 unclassified. Classify it from its URL and response, then apply that row's handling. Reading 24 is a priority transcription (Task 11), so it needs a usable original or transcript.

- [ ] **Step 1: Videos 8, 26:** `--kind video` (no original).
- [ ] **Step 2: Summaries 17, 22, 23:** search the web for the Vanguard original of each.
  - Found: archive the original with `--publisher vanguard`, and pass `--notes "Summary by <publisher>: <summary url>"`.
  - Not found: archive the summary with `--publisher <summary publisher slug, e.g. plansponsor>`, `--kind summary` and `--notes "Summary of Vanguard paper <title>; original not found"`.
  - The README link points at whichever source was archived. The `[original]` URL stays the artifact's.
- [ ] **Step 3: Reading 24** per its classification.
- [ ] **Step 4: Verify**
  - `check.py` → `0 errors, 26 warnings`.
  - `grep -o '](\.\./\.\./sources/[^)]*)' themes/portfolio-construction/README.md | wc -l` → `26`.
  - `git ls-files | grep -Ei '\.(pdf|html?)$'` → nothing.
- [ ] **Step 5: Commit** with explicit paths: `git add sources/vanguard sources/<each other publisher dir> themes/portfolio-construction/README.md`, then `git commit -m "feat(sources): complete the 26-reading batch with videos and summaries"`.

---

### Tasks 8–11: transcribe the 8 priority readings

Each task follows the CLAUDE.md transcription workflow for its two readings (ids from the README links). Files: `Modify: sources/<publisher>/<id>/transcription.md` ×2. Each task's verification: `check.py` → `0 errors, <26 − transcribed so far> warnings`, and `git diff` shows the front-matter lines unchanged. Each task's commit stages only those two files, e.g. `git add sources/vanguard/<id1>/transcription.md sources/vanguard/<id2>/transcription.md` and `git commit -m "docs(sources): transcribe readings <a> and <b> for study"`.

Review gate for each transcription: compare 2 random sections and every figure against the original copy in scratch. Headings must match the original, tables must be pipe tables, every figure must be in the blockquote format with a page reference, there must be no images, and nothing may be summarized away.

### Task 8: Transcribe readings 1 and 5
- [ ] **Step 1:** Transcribe reading 1. **Step 2:** Transcribe reading 5. **Step 3:** Verify → `0 errors, 24 warnings`. **Step 4:** Commit.

### Task 9: Transcribe readings 6 and 12
- [ ] **Step 1:** Transcribe reading 6. **Step 2:** Transcribe reading 12. **Step 3:** Verify → `0 errors, 22 warnings`. **Step 4:** Commit.

### Task 10: Transcribe readings 13 and 14
- [ ] **Step 1:** Transcribe reading 13. **Step 2:** Transcribe reading 14. **Step 3:** Verify → `0 errors, 20 warnings`. **Step 4:** Commit.

### Task 11: Transcribe readings 18 and 24, then verify the success criteria
- [ ] **Step 1:** Transcribe reading 18. **Step 2:** Transcribe reading 24.
- [ ] **Step 3: Success criteria**
  - `uv run tools/test_ids.py && uv run tools/test_tools.py` → `ok`, `ok`.
  - `uv run --env-file .env tools/check.py` → `0 errors, 18 warnings`, exit 0. All 18 warnings are `empty transcription body`, and none is for 1, 5, 6, 12, 13, 14, 18, 24.
  - `git ls-files | grep -Ei '\.(pdf|html?)$|(^|/)\.env$'` → nothing.
  - `uv run --env-file .env python -c "import os,subprocess;r=subprocess.run(['git','grep','-F','-l','-i',os.environ['DATA_PATH']],capture_output=True);print('leak' if r.stdout else 'clean')"` → `clean`.
  - `git grep -i -l onedrive` → no hits outside `CLAUDE.md`/`docs/` prose (and no absolute paths).
- [ ] **Step 4: Commit** the two transcriptions (as above).
