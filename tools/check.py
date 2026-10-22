# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import json
import re
import sys
from pathlib import Path

import store
from add import ID_RE, MAX_SLUG, ORIGINAL_KEYS, date_part, front_matter

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("id", "title", "publisher", "authors", "published", "kind", "url",
            "canonical_url", "fetched_at", "original", "notes")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def _well_formed(m) -> bool:
    if not isinstance(m, dict) or any(k not in m for k in REQUIRED):
        return False
    o = m["original"]
    return o is None or (isinstance(o, dict) and all(k in o for k in ORIGINAL_KEYS))


def check_source(sidecar: Path, remote: dict[str, str]) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    folder = sidecar.parent
    try:
        m = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{folder.name}: unreadable source.json ({e})"], warns
    if not _well_formed(m):
        return [f"{folder.name}: malformed source.json (wrong shape or missing keys)"], warns
    orig = m["original"]
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
        md5 = remote.get(orig["path"])
        if md5 is None:
            err(f"original missing: {orig['path']}")
        elif md5 != orig["md5"]:
            err(f"original md5 mismatch: {orig['path']}")
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


def run(repo_root: Path, store) -> int:
    try:
        remote = store.md5s()
    except RuntimeError as e:
        print(f"rclone failed: {e}")
        return 1
    errs, warns = check_themes(repo_root), []
    for s in sorted(repo_root.glob("sources/*/*/source.json")):
        e, w = check_source(s, remote)
        errs += e
        warns += w
    for e in errs:
        print("ERROR", e)
    for w in warns:
        print("WARN", w)
    print(f"{len(errs)} errors, {len(warns)} warnings")
    return 1 if errs else 0


def main() -> None:
    sys.exit(run(ROOT, store))


if __name__ == "__main__":
    main()
