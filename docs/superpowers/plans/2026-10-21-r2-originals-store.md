# Originals on Cloudflare R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `add.py` and `check.py` read and write originals in the R2 bucket `tr-learn` through rclone instead of `$DATA_PATH/tr-learn/`, and `check.py` verifies every original by MD5/ETag without downloading.

**Architecture:** A new `tools/store.py` is the only file that calls `rclone` (`put`, `md5s`). `add.run` and `check.run` take a `store` parameter instead of `data_root`; `main()` passes the `store` module, tests pass an in-memory `FakeStore`. Sidecars gain `original.md5`, backfilled once from the local OneDrive copies by a throwaway script that is not committed.

**Tech Stack:** Python >=3.11 stdlib only (`subprocess`, `hashlib`, `json`, `tempfile`) as PEP 723 scripts run with `uv run`; rclone v1.75 with remote `r2-tr-learn`; assert-based test scripts, no pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-r2-originals-store-design.md`. Read it before any task. It supersedes only the "Originals" storage rule of `docs/superpowers/specs/2026-10-15-tr-learn-archive-design.md`.

## Global Constraints

- Originals live only in R2; git keeps sidecars and transcriptions as today.
- No secrets in the repo or `.env`: credentials stay in `rclone config`.
- `check.py` verifies every original's content against git without downloading anything, at any archive size.
- Python stdlib only; rclone is the single external binary, called from one module (`tools/store.py`).
- `REMOTE = "r2-tr-learn:tr-learn"` (constant, not a secret).
- Any rclone failure raises `RuntimeError` carrying rclone's stderr; callers turn it into one clear message and a non-zero exit.
- `original` becomes `{path, sha256, md5}` (key order as written). `path` is relative to the bucket root, the same strings as today. `original` stays `null` for videos.
- Upload = temp file + `rclone copyto` (single PUT below the 200 MiB S3 upload cutoff, so ETag = MD5). Never `rclone rcat`.
- `.env` is not edited; the OneDrive copies are not deleted; the old spec and plan stay as history.
- `.env` holds secrets: never read, cat, grep or print it; never print the value of `DATA_PATH`. Only Task 1 uses it, through `uv run --env-file .env`.
- Never call bare `python`; use `uv run`. Run every command from the repo root `/c/Users/user/home/quant2/tr/tr-learn`.
- Stage explicit paths only (no `git add -A`, `.`, or `commit -a`). Work on `main`. Commit subject `<type>(<scope>): <why>`, <=72 chars, no names, no `Co-Authored-By`, no generated-by markers.

## Current state (verified while writing this plan)

- 108 sidecars, 103 with a non-null `original`. R2 already holds 103 objects under `sources/...` (migrated by the user; this plan uploads nothing).
- Every sidecar is byte-identical to `json.dumps(meta, indent=2, ensure_ascii=False) + "\n"`, so rewriting one in that form changes only the lines the backfill touches.
- `rclone lsjson -R --files-only --hash r2-tr-learn:tr-learn/<prefix>` returns objects with `"Path"` relative to the listed prefix and `"Hashes": {"md5": ...}`; a missing prefix returns `[]` with exit 0.

## Review Focus

1. **`rclone` not installed or not on PATH.** `subprocess.run` raises `FileNotFoundError`, not a non-zero exit; the user expects `rclone failed: ...` and exit 1, not a traceback (Task 2 code step converts it; Task 3 Step 3 checks it).
2. **An id that is a prefix of an existing id** (`.../2026-09-00-foo` vs `.../2026-09-00-foo-bar`). The "exists in R2" refusal must match the folder, not a string prefix (Task 2, `test_remote_prefix_of_longer_id_is_not_a_collision`).
3. **An object with no MD5 in the listing** (multipart upload above 200 MiB has no `md5` in `Hashes`). Expect `original md5 mismatch`, never a `KeyError` (Task 2, `test_object_without_md5_is_mismatch`).
4. **`md5s(prefix)` keys** must be relative to `REMOTE`, not to the prefix, or later callers comparing with `original.path` silently miss (Task 3 Step 2 checks it against the real bucket).
5. **The backfill hitting a missing or mismatching OneDrive copy halfway.** Expect nothing written and a message that does not echo the `DATA_PATH` value (Task 1 script: validate all, then write; excepthook hides paths).

---

## File Structure

| Path | Change | Responsibility |
|---|---|---|
| `tools/store.py` | Create | the only rclone caller: `REMOTE`, `put`, `md5s` |
| `tools/add.py` | Modify | `run(argv, repo_root, store)`; md5 in sidecar; R2 existence check; upload last, rollback repo folder on failure |
| `tools/check.py` | Modify | `run(repo_root, store)`; one `store.md5s()`; md5 comparison; `DATA_PATH` removed |
| `tools/test_tools.py` | Modify | `FakeStore` replaces the temp data dir; new cases |
| `sources/*/*/source.json` | Modify (103 files) | add `original.md5` |
| `CLAUDE.md` | Modify | R2 rules replace `DATA_PATH` rules |
| scratchpad `backfill.py` | Create, never committed | one-off md5 backfill |

`tools/test_ids.py` is unchanged and must keep passing.

---

### Task 1: Backfill `original.md5` into the sidecars

Runs first: the current `check.py` ignores the extra key, so it still passes against OneDrive, and Task 2's stricter shape check finds the key already present.

**Files:**
- Create (not committed): `<your scratchpad>/backfill.py`
- Modify: the 103 `sources/*/*/source.json` with a non-null `original`

**Interfaces:**
- Produces: every non-null `original` is `{"path", "sha256", "md5"}` in that order, `md5` = lowercase hex `hashlib.md5` of the OneDrive bytes.

- [ ] **Step 1: Write the script in your scratchpad (outside the repo)**

Validate everything first, write only if all sha256 match; the excepthook keeps absolute paths (which contain the `DATA_PATH` value) out of the output.

```python
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import hashlib, json, os, sys
from pathlib import Path
sys.excepthook = lambda t, e, b: print("failed:", t.__name__, getattr(e, "strerror", None) or "")
root = Path(os.environ["DATA_PATH"]) / "tr-learn"
todo = []
for s in sorted(Path("sources").glob("*/*/source.json")):
    m = json.loads(s.read_text(encoding="utf-8"))
    o = m["original"]
    if o is None or "md5" in o:
        continue
    data = (root / o["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != o["sha256"]:
        sys.exit(f"sha256 mismatch, nothing written: {o['path']}")
    o["md5"] = hashlib.md5(data).hexdigest()
    todo.append((s, m))
for s, m in todo:
    s.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print(len(todo), "sidecars updated")
```

- [ ] **Step 2: Run it from the repo root**

Run: `uv run --env-file .env <scratchpad>/backfill.py`
Expected: `103 sidecars updated`. On `sha256 mismatch` or `failed:` stop and report to the user; do not edit sidecars by hand.

- [ ] **Step 3: Verify the diff is exactly one added key per file**

Run: `git diff --numstat -- sources | wc -l` → `103`
Run: `git diff --numstat -- sources | awk '$1!=2 || $2!=1' | wc -l` → `0` (the `sha256` line gains a comma, one `md5` line is added)

- [ ] **Step 4: Verify the old checker still passes against OneDrive**

Run: `uv run --env-file .env tools/check.py`
Expected: last line `0 errors, N warnings` (N = untranscribed backlog, unchanged from before the run).

- [ ] **Step 5: Commit**

```bash
git add -- $(git diff --name-only -- sources)
git commit -m "chore(sources): record original md5 so check.py can verify R2 ETags"
```

---

### Task 2: `store.py`, and `add.py` / `check.py` on top of it

One task because `test_tools.py` drives `check` through sources created by `add.run`: neither half passes its tests alone.

**Files:**
- Create: `tools/store.py`
- Modify: `tools/add.py` (`_write`, `run`, `main`, imports)
- Modify: `tools/check.py` (`check_source`, `run`, `main`, imports)
- Test: `tools/test_tools.py`

**Interfaces:**
- Consumes: Task 1's sidecar shape.
- Produces:
  - `store.REMOTE = "r2-tr-learn:tr-learn"`
  - `store.put(path: str, data: bytes) -> None`
  - `store.md5s(prefix: str = "") -> dict[str, str]` — keys relative to `REMOTE` (e.g. `sources/aaii/<id>/original.html`), values lowercase md5 hex
  - `add.run(argv: list[str], repo_root: Path, store) -> Path`
  - `check.check_source(sidecar: Path, remote: dict[str, str]) -> tuple[list[str], list[str]]`
  - `check.run(repo_root: Path, store) -> int`
  - Messages: `source already exists: <id>`, `rclone failed: <stderr>` (add and check), `original missing: <path>`, `original md5 mismatch: <path>`

- [ ] **Step 1: Replace the data-dir fixtures in `tools/test_tools.py` with `FakeStore`**

```python
class FakeStore:
    def __init__(self, fail_put=False, fail_list=False):
        self.objects = {}                           # path relative to REMOTE -> bytes
        self.fail_put, self.fail_list = fail_put, fail_list

    def put(self, path, data):
        if self.fail_put:
            raise RuntimeError("upload refused")
        self.objects[path] = data

    def md5s(self, prefix=""):
        if self.fail_list:
            raise RuntimeError("listing refused")
        p = prefix.rstrip("/")
        return {k: hashlib.md5(v).hexdigest() for k, v in self.objects.items()
                if not p or k.startswith(p + "/")}   # folder semantics, like rclone
```

`dirs()` returns `(repo, FakeStore(), tmp)`; every `run(..., repo, data)` becomes `run(..., repo, store)`, every `check_source(sidecar, data)` becomes `check_source(sidecar, store.md5s())`. Existing cases keep their intent, with these edits:
- `test_video_writes_sidecar_and_front_matter`: last assert becomes `assert store.objects == {}`.
- `test_file_ingest_writes_original_and_sha`: `store.objects[meta["original"]["path"]] == b"%PDF-1.4 test"`; add `assert list(meta["original"]) == ["path", "sha256", "md5"]` and `meta["original"]["md5"] == hashlib.md5(b"%PDF-1.4 test").hexdigest()`.
- `test_failed_download_leaves_nothing`, `test_missing_file_is_clean_exit`, `test_kind_pdf_with_non_pdf_is_refused`: "nothing in data" becomes `store.objects == {}`; drop `str(data) not in m`.
- `test_tampered_original_is_error`: overwrite `store.objects[path] = b"%PDF-1.4 evil"`; assert one error containing `md5 mismatch`.
- `test_missing_original_is_error`: `del store.objects[path]`; assert one error containing `original missing`.
- `test_original_missing_sha_is_error`: unchanged intent; add a sibling `test_original_missing_md5_is_error` (delete `md5`, expect one `malformed` error).
- `test_write_failure_cleans_up_without_absolute_path`: patch `add.Path.write_text` (restore in `finally`) to raise `PermissionError(5, "Access is denied")`; expect `write failed for sources/vanguard/` with no `str(repo)`, no repo folder left, `store.objects == {}`, and a retry succeeds.
- `test_missing_data_path_fails` is replaced by `test_rclone_failure_fails` below.

- [ ] **Step 2: Add the new cases**

```python
def test_failed_upload_leaves_no_repo_folder():
    repo, _, tmp = dirs()
    f = tmp / "x.pdf"; f.write_bytes(b"%PDF-1.4 test")
    m = _msg(lambda: run(_pdf_args(f), repo, FakeStore(fail_put=True)))
    assert m == "rclone failed: upload refused"
    assert not (repo / "sources/vanguard/2026-09-00-vanguard-capital-markets-model").exists()

def test_existing_remote_prefix_refuses_id():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"; f.write_bytes(b"%PDF-1.4 test")
    store.objects["sources/vanguard/2026-09-00-vanguard-capital-markets-model/original.pdf"] = b"old"
    assert "source already exists" in _msg(lambda: run(_pdf_args(f), repo, store))
    assert not (repo / "sources").exists()

def test_remote_prefix_of_longer_id_is_not_a_collision():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"; f.write_bytes(b"%PDF-1.4 test")
    store.objects["sources/vanguard/2026-09-00-vanguard-capital-markets-model-2/original.pdf"] = b"x"
    run(_pdf_args(f), repo, store)   # must not exit

def test_object_without_md5_is_mismatch():
    repo, store, d = _fresh()
    path = _meta(d)["original"]["path"]
    errs, _ = check_source(d / "source.json", {path: ""})
    assert errs == [f"{_meta(d)['id']}: original md5 mismatch: {path}"]

def test_rclone_failure_fails():
    repo, _, _ = dirs()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert check_run(repo, FakeStore(fail_list=True)) == 1
    assert "rclone failed: listing refused" in out.getvalue()
```

`_fresh()` returns `repo, store, d`. Add `import contextlib, io` to the imports.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run tools/test_tools.py`
Expected: FAIL (first failure is in an `add.run` case: the old `run` treats the `FakeStore` as `data_root`).

- [ ] **Step 4: Create `tools/store.py`**

PEP 723 header like the other scripts. Contents:
- `REMOTE = "r2-tr-learn:tr-learn"`.
- A private `_rclone(*args: str) -> str` running `["rclone", *args]` with `capture_output=True, text=True, encoding="utf-8"`; non-zero exit → `RuntimeError(stderr.strip())`; `FileNotFoundError` → `RuntimeError("rclone not found on PATH")`. Returns stdout.
- `put(path, data)`: `tempfile.NamedTemporaryFile(delete=False, suffix=Path(path).suffix)` (suffix keeps the object's MIME type as `.pdf`/`.html`), write, **close before calling rclone** (Windows cannot share an open temp file), `_rclone("copyto", tmp, f"{REMOTE}/{path}")`, unlink the temp file in `finally`.
- `md5s(prefix="")`: `p = prefix.strip("/")`; `_rclone("lsjson", "-R", "--hash", "--files-only", f"{REMOTE}/{p}" if p else REMOTE)`; return `{(f"{p}/{o['Path']}" if p else o["Path"]): (o.get("Hashes") or {}).get("md5", "") for o in json.loads(out)}`.

- [ ] **Step 5: Rewrite `add.run` and `add.main`**

- Signature `run(argv, repo_root, store)`. Remove `_write` and the `data_dir` variable; drop the now-unused `os` and `tempfile` imports; add `import store` at module level (used only by `main`).
- Existence check, where the current one is: `repo_dir.exists()` or `store.md5s(rel)` non-empty → `sys.exit(f"source already exists: {sid}")`; a `RuntimeError` there → `sys.exit(f"rclone failed: {e}")`.
- `original = {"path": ..., "sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest()}`.
- Write `source.json` and `transcription.md` exactly as today (on `OSError`: `shutil.rmtree(repo_dir, ignore_errors=True)`, `write failed for {rel}: {e.strerror}`). Then, if `data is not None`, `store.put(original["path"], data)`; on `RuntimeError`: `shutil.rmtree(repo_dir, ignore_errors=True)` and `sys.exit(f"rclone failed: {e}")`.
- `main()`: no `DATA_PATH` check; `run(sys.argv[1:], Path(__file__).resolve().parent.parent, store)`.

- [ ] **Step 6: Rewrite `check.check_source`, `check.run`, `check.main`**

- Shape check requires `"path"`, `"sha256"` and `"md5"` in a non-null `original`.
- `check_source(sidecar, remote)`: replaces the file read; `remote.get(orig["path"])` is `None` → `original missing: <path>`; `!= orig["md5"]` → `original md5 mismatch: <path>`. Drop the `original unreadable` branch and the `hashlib`/`os` imports.
- `run(repo_root, store)`: `remote = store.md5s()` once, before the loop; `RuntimeError` → `print(f"rclone failed: {e}")` and `return 1`.
- `main()`: `import store` at module level; `sys.exit(run(ROOT, store))`.

- [ ] **Step 7: Run all offline tests**

Run: `uv run tools/test_tools.py` → ends with `ok`
Run: `uv run tools/test_ids.py` → passes as before
Run: `grep -n "DATA_PATH\|env-file\|data_root" tools/*.py` → no output

- [ ] **Step 8: Commit**

```bash
git add tools/store.py tools/add.py tools/check.py tools/test_tools.py
git commit -m "feat(tools): keep originals in R2 so storage needs no local sync"
```

---

### Task 3: Verify against the real bucket and update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (lines 10, 11, 12, 14, 19, 25-26, 33, 47 of the current file)

**Interfaces:**
- Consumes: `store.md5s`, `check.run` from Task 2; sidecars from Task 1.

- [ ] **Step 1: Run the real checker against R2 (read-only, uses the rclone config credentials)**

Run: `uv run tools/check.py`
Expected: last line `0 errors, N warnings`, same N as Task 1 Step 4. Any `original md5 mismatch` or `original missing` means the R2 object differs from the OneDrive original: stop and report to the user; do not re-upload or delete anything.

- [ ] **Step 2: Check `md5s(prefix)` key form against the real bucket**

Run: `uv run python -c "import sys; sys.path.insert(0, 'tools'); import store; d = store.md5s('sources/aaii'); print(len(d), all(k.startswith('sources/aaii/') for k in d), store.md5s('sources/nope/x'))"`
Expected: `1 True {}`

- [ ] **Step 3: Check the missing-rclone message**

Run: `PATH=/nonexistent "$(command -v uv)" run tools/check.py; echo "exit=$?"`
Expected: `rclone failed: rclone not found on PATH` and `exit=1`. If `uv` itself cannot start without PATH, skip this step and say so in the report.

- [ ] **Step 4: Edit `CLAUDE.md`**

- Layout line: `tools/` holds `add.py`, `check.py`, `store.py`, tests.
- Replace the `Originals are NOT in git...` line with: `Originals are NOT in git. They live in R2 at r2-tr-learn:tr-learn/<original.path> (rclone remote; credentials stay in rclone config, never in the repo or .env). tools/store.py is the only code that calls rclone.`
- `.env` line becomes: `` `.env` holds secrets: never read, cat, grep or print it. `` (drop the `DATA_PATH` and `--env-file` parts).
- `source.json` fields: `original (`{path, sha256, md5}`, path relative to the bucket root r2-tr-learn:tr-learn/; null for videos)`.
- Python line: append `rclone is the only external binary.`
- Add-a-source commands: `uv run tools/add.py <url> ...` and `uv run tools/check.py` (no `--env-file .env`).
- Undo a bad add: `rm -r sources/<publisher>/<id>` plus `rclone purge r2-tr-learn:tr-learn/sources/<publisher>/<id>` (drop the Python one-liner and the OneDrive note).
- Transcription workflow step 1: `Copy the original to a scratch dir: rclone copyto r2-tr-learn:tr-learn/<original.path> <scratch file>.`

- [ ] **Step 5: Verify**

Run: `grep -n "DATA_PATH\|env-file" CLAUDE.md` → no output
Run: `uv run tools/test_tools.py && uv run tools/check.py` → `ok`, then `0 errors, N warnings`

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): point original handling at R2 now that DATA_PATH is unused"
```

---

## Not in this plan (by the spec)

- No upload of existing originals (already in R2), no edit to `.env`, no deletion of OneDrive copies, no edit to the 2026-10-15 spec or plan.
- `store.put` gets no unit test (spec: `store.py` is exercised by the real `check.py` run); its first real use is the next `add.py` run, and a bad upload shows up there as `original md5 mismatch` in `check.py`.
