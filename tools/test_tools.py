# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import hashlib
import json
import tempfile
from pathlib import Path

from add import run, infer_kind, front_matter


def dirs():
    return Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())


def raises_exit(fn):
    try:
        fn()
    except SystemExit:
        return
    assert False, "expected SystemExit"


def test_video_writes_sidecar_and_front_matter():
    repo, data, _ = dirs()
    d = run(["https://www.youtube.com/watch?v=x", "--publisher", "vanguard",
             "--title", "Some Video", "--kind", "video"], repo, data)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert d == repo / "sources/vanguard" / meta["id"] and meta["original"] is None
    assert meta["published"] is None and meta["id"].startswith(meta["fetched_at"][:10])
    assert list(meta) == ["id", "title", "publisher", "authors", "published", "kind", "url",
                          "canonical_url", "fetched_at", "original", "notes"]
    assert (d / "transcription.md").read_text(encoding="utf-8") == front_matter(meta)
    assert not (data / "sources").exists()


def _pdf_args(f):
    return ["https://corporate.vanguard.com/x.pdf", "--publisher", "vanguard", "--title",
            "Vanguard Capital Markets Model", "--published", "2026-09", "--file", str(f)]


def test_file_ingest_writes_original_and_sha():
    repo, data, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    d = run(_pdf_args(f), repo, data)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert meta["id"] == "2026-09-00-vanguard-capital-markets-model" and meta["kind"] == "pdf"
    assert meta["original"]["path"] == "sources/vanguard/2026-09-00-vanguard-capital-markets-model/original.pdf"
    assert (data / meta["original"]["path"]).read_bytes() == b"%PDF-1.4 test"
    assert meta["original"]["sha256"] == hashlib.sha256(b"%PDF-1.4 test").hexdigest()


def test_existing_id_is_refused():
    repo, data, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    d = run(_pdf_args(f), repo, data)
    before = (d / "source.json").read_bytes()
    raises_exit(lambda: run(_pdf_args(f), repo, data))
    assert (d / "source.json").read_bytes() == before


def test_pdf_url_returning_html_is_refused():
    try:
        infer_kind("https://x.com/a.pdf", "text/html", b"<html>cookies</html>")
        assert False
    except ValueError:
        pass
    assert infer_kind("https://x.com/page", "text/html; charset=utf-8", b"<html>") == "html"


def test_failed_download_leaves_nothing():
    repo, data, _ = dirs()
    raises_exit(lambda: run(["http://127.0.0.1:9/x.pdf", "--publisher", "vanguard",
                             "--title", "T"], repo, data))
    assert not (repo / "sources").exists() and not (data / "sources").exists()


def test_mirror_without_canonical_is_refused():
    repo, data, _ = dirs()
    raises_exit(lambda: run(["https://externalcrewnet.vanguard.com/x", "--publisher", "vanguard",
                             "--title", "T", "--kind", "video"], repo, data))
    assert not (repo / "sources").exists()


def test_bad_published_is_refused():
    repo, data, _ = dirs()
    raises_exit(lambda: run(["https://x.com/p", "--publisher", "vanguard", "--title", "T",
                             "--published", "2026-9", "--kind", "video"], repo, data))
    assert not (repo / "sources").exists()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "ok")
    print("ok")
