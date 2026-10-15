# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import unicodedata

STOPWORDS = {"a", "an", "the", "of", "for", "and"}
MAX_SLUG = 70
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLISHED_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def slugify(title: str) -> str:
    text = title.replace("'", "").replace("’", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    words = [w for w in text.split("-") if w and w not in STOPWORDS]
    out = []
    for w in words:
        if len("-".join(out + [w])) > MAX_SLUG:
            break
        out.append(w)
    slug = "-".join(out) or (words[0][:MAX_SLUG] if words else "")
    if not slug:
        raise ValueError(f"title yields empty slug: {title!r}")
    return slug


def date_part(published: str | None, fetch_date: str) -> str:
    if published is None:
        return fetch_date
    if not PUBLISHED_RE.match(published):
        raise ValueError(f"invalid published date: {published!r}")
    parts = published.split("-")
    return "-".join(parts + ["00"] * (3 - len(parts)))


def make_id(title: str, published: str | None, fetch_date: str) -> str:
    return f"{date_part(published, fetch_date)}-{slugify(title)}"


MIRROR_HOSTS = ("externalcrewnet.vanguard.com", "corpaemdisp.essp.c1.vanguard.com")
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
FM_FIELDS = ("id", "title", "publisher", "published", "url")
PUBLISHER_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def front_matter(meta: dict) -> str:
    body = "".join(
        f"{k}: {'null' if meta[k] is None else meta[k]}\n" for k in FM_FIELDS
    )
    return "---\n" + body + "original_prevails: true\n---\n"


def infer_kind(url: str, content_type: str, data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if urllib.parse.urlparse(url).path.lower().endswith(".pdf"):
        raise ValueError(f"expected a PDF, got {content_type}; save it in a browser and pass --file")
    if "html" in content_type:
        return "html"
    raise ValueError(f"cannot infer kind from {content_type}; pass --kind")


def _write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as t:
        t.write(data)
    os.replace(t.name, path)


def run(argv: list[str], repo_root: Path, data_root: Path) -> Path:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--publisher", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--published", default=None)
    p.add_argument("--kind", choices=["pdf", "html", "video", "summary"])
    p.add_argument("--file")
    p.add_argument("--canonical-url", default=None)
    p.add_argument("--notes", default="")
    a = p.parse_args(argv)

    if a.published is not None and not PUBLISHED_RE.match(a.published):
        sys.exit(f"invalid --published {a.published!r}; use YYYY, YYYY-MM, YYYY-MM-DD")
    if not PUBLISHER_RE.match(a.publisher):
        sys.exit(f"invalid --publisher {a.publisher!r}; use lowercase-hyphenated")
    if urllib.parse.urlparse(a.url).hostname in MIRROR_HOSTS and not a.canonical_url:
        sys.exit("fetched from a mirror; pass --canonical-url")
    if a.file and a.kind == "video":
        sys.exit("--file cannot be combined with --kind video")

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sid = make_id(a.title, a.published, fetched_at[:10])
    rel = f"sources/{a.publisher}/{sid}"
    repo_dir, data_dir = repo_root / rel, data_root / rel
    if repo_dir.exists() or data_dir.exists():
        sys.exit(f"source already exists: {sid}")

    kind, data, ext = a.kind, None, None
    if kind != "video":
        if a.file:
            try:
                data = Path(a.file).read_bytes()
            except OSError as e:
                sys.exit(f"cannot read --file: {e.strerror}")
            content_type = mimetypes.guess_type(a.file)[0] or ""
        else:
            req = urllib.request.Request(a.url, headers={"User-Agent": BROWSER_UA})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data, content_type = r.read(), r.headers.get("Content-Type", "")
            except (urllib.error.URLError, OSError) as err:  # URLError, TimeoutError, resets
                sys.exit(f"download failed ({err}); save the page in a browser and pass --file")
        try:
            kind = kind or infer_kind(a.url, content_type, data)
        except ValueError as err:
            sys.exit(str(err))
        if kind == "pdf" and not data.startswith(b"%PDF-"):
            sys.exit("--kind pdf but the data is not a PDF")
        ext = "pdf" if data.startswith(b"%PDF-") else "html"

    original = None
    if data is not None:
        original = {"path": f"{rel}/original.{ext}", "sha256": hashlib.sha256(data).hexdigest()}
    meta = {"id": sid, "title": a.title, "publisher": a.publisher, "authors": [],
            "published": a.published, "kind": kind, "url": a.url,
            "canonical_url": a.canonical_url, "fetched_at": fetched_at,
            "original": original, "notes": a.notes}
    try:
        if data is not None:
            data_dir.mkdir(parents=True)
            _write(data_dir / f"original.{ext}", data)
        repo_dir.mkdir(parents=True)
        (repo_dir / "source.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        (repo_dir / "transcription.md").write_text(
            front_matter(meta), encoding="utf-8", newline="\n")
    except OSError as e:
        for d in (data_dir, repo_dir):  # both were absent before this run
            shutil.rmtree(d, ignore_errors=True)
        sys.exit(f"write failed for {rel}: {e.strerror}")
    return repo_dir


def main() -> None:
    if not os.environ.get("DATA_PATH"):
        sys.exit("DATA_PATH is not set; run with uv run --env-file .env")
    d = run(sys.argv[1:], Path(__file__).resolve().parent.parent,
            Path(os.environ["DATA_PATH"]) / "tr-learn")
    print(d.name)


if __name__ == "__main__":
    main()
