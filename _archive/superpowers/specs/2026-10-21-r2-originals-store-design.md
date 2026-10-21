# Originals on Cloudflare R2 — design

Supersedes the "Originals" storage rule of `2026-10-15-tr-learn-archive-design.md`: originals move from the OneDrive folder under `$DATA_PATH/tr-learn/` to the R2 bucket `tr-learn`, reached through the rclone remote `r2-tr-learn` (S3 protocol). Everything else in that spec stands.

## Goal

- Originals live only in R2; git keeps sidecars and transcriptions as today.
- No secrets in the repo or `.env`: credentials stay in `rclone config`.
- `check.py` verifies every original's content against git without downloading anything, at any archive size.
- Python stdlib only; rclone is the single external binary, called from one module.

## Decisions

| Question | Decision | Why |
|---|---|---|
| How code reaches R2 | Call `rclone` via `subprocess` | One config for credentials, ~25 lines, no hand-rolled SigV4 |
| Remote name | Constant `REMOTE = "r2-tr-learn:tr-learn"` | Not a secret, never changes |
| Content verification | Add `md5` to `original`; compare with R2's ETag | R2 exposes only MD5 (verified: `rclone hashsum sha256` → "hash type not supported"); the ETag is computed by R2 on the stored bytes, so no download is needed |
| `sha256` | Kept | Existing reference hash, provider-independent |
| Upload command | Temp file + `rclone copyto` | Single PUT below the S3 upload cutoff (200 MiB), so ETag = MD5. `rclone rcat` streams anything above 100 KiB as multipart, whose ETag is not an MD5 |

## Architecture

```
tools/store.py   the only file that knows about rclone
  REMOTE = "r2-tr-learn:tr-learn"
  put(path: str, data: bytes) -> None      temp file + rclone copyto REMOTE/path
  md5s(prefix: str = "") -> dict[str, str] rclone lsjson -R --hash --files-only REMOTE/prefix
                                           -> {path relative to REMOTE: md5}; a missing prefix is {}

add.py  ── put, md5s ──►  store  ◄── md5s ──  check.py
tests   ── FakeStore (in-memory dict with the same two methods)
```

- Any rclone failure raises `RuntimeError` carrying rclone's stderr; callers turn it into one clear message and a non-zero exit.
- `add.run(argv, repo_root, store)` and `check.run(repo_root, store)` take the store as a parameter (today they take `data_root`); `main()` passes the `store` module.

## Sidecar change

`original` becomes `{path, sha256, md5}` (key order as written). `path` is relative to the bucket root, the same strings as today. `original` stays `null` for videos.

## `add.py`

1. Compute `sha256` and `md5` of the bytes.
2. Refuse the id if the repo folder exists or `store.md5s(rel)` is non-empty.
3. Write `source.json` and `transcription.md` in the repo, then `store.put`. If the upload fails, remove the repo folder; nothing remains in R2 to clean up.

## `check.py`

- Calls `store.md5s()` once.
- Per sidecar with an original: `original missing: <path>` if absent; `original md5 mismatch: <path>` if different.
- Shape check requires `path`, `sha256`, `md5` in `original`.
- rclone failure prints `rclone failed: <stderr>` and exits 1.
- The `DATA_PATH` handling is removed.

## One-off backfill (not committed as code)

For each sidecar with an original: read the local OneDrive copy (via `DATA_PATH`, value never printed), verify its sha256 equals the sidecar's, write `md5` into the sidecar. Stop on any sha256 mismatch. Then `check.py` against R2 confirms that the migrated objects equal the originals, with no download.

## `CLAUDE.md`

- Drop the `DATA_PATH` and `--env-file .env` rules for originals; state that originals live in `r2-tr-learn:tr-learn/<original.path>`.
- `source.json` fields: `original` is `{path, sha256, md5}`.
- Copy an original to scratch: `rclone copyto r2-tr-learn:tr-learn/<original.path> <scratch file>`.
- Undo a bad add: `rm -r sources/<publisher>/<id>` plus `rclone purge r2-tr-learn:tr-learn/sources/<publisher>/<id>`.
- Commands become `uv run tools/add.py ...` and `uv run tools/check.py`.

## Testing

- `test_tools.py` uses `FakeStore` instead of a temp data dir; existing cases keep their intent.
- New cases: original missing in the store; md5 mismatch; failed upload leaves no repo folder; existing remote prefix refuses the id.
- `store.py` itself is exercised by the real `check.py` run after the backfill (0 errors expected), not by unit tests.

## Known limits

- An original above 200 MiB would upload as multipart; its ETag is not an MD5, so `check.py` reports a mismatch (loud, not silent).
- MD5 is not collision-resistant against a deliberate attacker; the threat model is accidental loss or overwrite.

## Out of scope

- Old spec and plan stay as history.
- `.env` is not edited; removing `DATA_PATH` is the user's call.
- The OneDrive copies are not deleted.
