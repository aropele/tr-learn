# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import json
import os
import subprocess
import tempfile
from pathlib import Path

REMOTE = "r2-tr-learn:tr-learn"


def _rclone(*args: str) -> str:
    try:
        r = subprocess.run(["rclone", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        raise RuntimeError("rclone not found on PATH") from None
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def put(path: str, data: bytes) -> None:
    # copyto of a file below the 200 MiB upload cutoff is a single PUT, so R2's ETag is its MD5
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(path).suffix) as t:
        t.write(data)
    try:
        _rclone("copyto", t.name, f"{REMOTE}/{path}")
    finally:
        os.unlink(t.name)


def md5s(prefix: str = "") -> dict[str, str]:
    p = prefix.strip("/")
    out = _rclone("lsjson", "-R", "--hash", "--files-only", f"{REMOTE}/{p}" if p else REMOTE)
    return {(f"{p}/{o['Path']}" if p else o["Path"]): (o.get("Hashes") or {}).get("md5", "")
            for o in json.loads(out)}
