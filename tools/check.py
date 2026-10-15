# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from add import ID_RE, MAX_SLUG, date_part, front_matter

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("id", "title", "publisher", "authors", "published", "kind", "url",
            "canonical_url", "fetched_at", "original", "notes")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def check_source(sidecar: Path, data_root: Path) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    folder = sidecar.parent
    try:
        m = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{folder.name}: unreadable source.json ({e})"], warns
    orig = m.get("original", 0) if isinstance(m, dict) else 0
    if (not isinstance(m, dict) or any(k not in m for k in REQUIRED)
            or not (orig is None or (isinstance(orig, dict) and "path" in orig and "sha256" in orig))):
        return [f"{folder.name}: malformed source.json (wrong shape or missing keys)"], warns
    sid = str(m.get("id"))
    err = lambda msg: errs.append(f"{sid}: {msg}")
    if sid != folder.name:
        err(f"id differs from folder name {folder.name}")
    if m.get("publisher") != folder.parent.name:
        err(f"publisher differs from folder {folder.parent.name}")
    if not ID_RE.match(sid):
        err("id does not match the id rule")
    elif len(sid[11:]) > MAX_SLUG:
        err(f"slug longer than {MAX_SLUG}")
    try:
        if sid[:10] != date_part(m.get("published"), str(m.get("fetched_at"))[:10]):
            err("id date does not match published/fetched_at")
    except ValueError as e:
        err(str(e))
    if orig is not None:
        p = data_root / orig["path"]
        try:
            if not p.is_file():
                err(f"original missing: {orig['path']}")
            elif hashlib.sha256(p.read_bytes()).hexdigest() != orig["sha256"]:
                err(f"original sha256 mismatch: {orig['path']}")
        except OSError as e:
            err(f"original unreadable: {orig['path']} ({e.strerror})")
    t = folder / "transcription.md"
    if not t.is_file():
        err("transcription.md missing")
    else:
        text, fm = t.read_text(encoding="utf-8"), front_matter(m)
        if not text.startswith(fm):
            err("front-matter differs from source.json")
        elif not text[len(fm):].strip():
            warns.append(f"{sid}: empty transcription body")
    return errs, warns


def check_themes(repo_root: Path) -> list[str]:
    errs = []
    for readme in sorted(repo_root.glob("themes/*/README.md")):
        for target in LINK_RE.findall(readme.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            if not (readme.parent / target.split("#")[0]).is_file():
                errs.append(f"{readme.parent.name}: broken link {target}")
    return errs


def run(repo_root: Path, data_root: Path | None) -> int:
    if data_root is None:
        print("DATA_PATH is not set; run with uv run --env-file .env")
        return 1
    errs, warns = check_themes(repo_root), []
    for s in sorted(repo_root.glob("sources/*/*/source.json")):
        e, w = check_source(s, data_root)
        errs += e
        warns += w
    for e in errs:
        print("ERROR", e)
    for w in warns:
        print("WARN", w)
    print(f"{len(errs)} errors, {len(warns)} warnings")
    return 1 if errs else 0


def main() -> None:
    dp = os.environ.get("DATA_PATH")
    sys.exit(run(ROOT, Path(dp) / "tr-learn" if dp else None))


if __name__ == "__main__":
    main()
