# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import hashlib
import json
import tempfile
from pathlib import Path

from add import run, infer_kind, front_matter
from check import check_source, check_themes, run as check_run


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


def _msg(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    assert False, "expected SystemExit"


def test_missing_file_is_clean_exit():
    repo, data, tmp = dirs()
    m = _msg(lambda: run(_pdf_args(tmp / "nope.pdf"), repo, data))
    assert "cannot read --file" in m and str(data) not in m
    assert not (repo / "sources").exists() and not (data / "sources").exists()


def test_write_failure_cleans_up_without_absolute_path():
    import add
    repo, data, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    real = add.os.replace

    def boom(*a):
        raise PermissionError(5, "Access is denied")
    add.os.replace = boom
    try:
        m = _msg(lambda: run(_pdf_args(f), repo, data))
    finally:
        add.os.replace = real
    assert "write failed for sources/vanguard/" in m and str(data) not in m and str(repo) not in m
    assert not (repo / "sources/vanguard").exists() or not list((repo / "sources/vanguard").iterdir())
    assert not list((data / "sources/vanguard").iterdir()) if (data / "sources/vanguard").exists() else True
    run(_pdf_args(f), repo, data)  # retry is not blocked by an orphan


def test_kind_pdf_with_non_pdf_is_refused():
    repo, data, tmp = dirs()
    f = tmp / "x.html"
    f.write_bytes(b"<html></html>")
    m = _msg(lambda: run(["https://x.com/p", "--publisher", "vanguard", "--title", "T",
                          "--kind", "pdf", "--file", str(f)], repo, data))
    assert "not a PDF" in m and not (repo / "sources").exists() and not (data / "sources").exists()


def test_front_matter_is_yaml_safe():
    fm = front_matter({"id": "i", "title": 'A: B "q"', "publisher": "v",
                       "published": "2022", "url": "u"}).splitlines()
    assert 'title: ' + json.dumps('A: B "q"') in fm and 'published: "2022"' in fm
    assert "published: null" in front_matter({"id": "i", "title": "t", "publisher": "v",
                                              "published": None, "url": "u"}).splitlines()


def _fresh():
    repo, data, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    return repo, data, run(_pdf_args(f), repo, data)


def _meta(d):
    return json.loads((d / "source.json").read_text(encoding="utf-8"))


def _save(d, meta):
    (d / "source.json").write_text(json.dumps(meta), encoding="utf-8")


def test_fresh_source_only_warns_empty_body():
    repo, data, d = _fresh()
    errs, warns = check_source(d / "source.json", data)
    assert errs == [] and len(warns) == 1 and "empty transcription body" in warns[0]


def test_tampered_original_is_error():
    repo, data, d = _fresh()
    (data / _meta(d)["original"]["path"]).write_bytes(b"%PDF-1.4 evil")
    errs, _ = check_source(d / "source.json", data)
    assert len(errs) == 1 and "sha256" in errs[0]


def test_missing_original_is_error():
    repo, data, d = _fresh()
    (data / _meta(d)["original"]["path"]).unlink()
    errs, _ = check_source(d / "source.json", data)
    assert len(errs) == 1 and "original" in errs[0]


def test_front_matter_mismatch_is_error():
    repo, data, d = _fresh()
    m = _meta(d)
    m["title"] = "Other"
    _save(d, m)
    errs, _ = check_source(d / "source.json", data)
    assert len(errs) == 1 and "front-matter differs" in errs[0]


def test_id_date_mismatch_is_error():
    repo, data, d = _fresh()
    m = _meta(d)
    m["published"] = "2025"
    _save(d, m)
    (d / "transcription.md").write_text(front_matter(m), encoding="utf-8", newline="\n")
    errs, _ = check_source(d / "source.json", data)
    assert len(errs) == 1 and "date" in errs[0]


def test_body_present_no_warning():
    repo, data, d = _fresh()
    with open(d / "transcription.md", "a", encoding="utf-8", newline="\n") as f:
        f.write("\n# Heading\ntext\n")
    assert check_source(d / "source.json", data) == ([], [])


def test_non_object_sidecar_is_error():
    repo, data, d = _fresh()
    (d / "source.json").write_text("[1]", encoding="utf-8")
    errs, _ = check_source(d / "source.json", data)
    assert len(errs) == 1 and "malformed" in errs[0]


def test_original_missing_sha_is_error():
    repo, data, d = _fresh()
    m = _meta(d)
    del m["original"]["sha256"]
    _save(d, m)
    errs, _ = check_source(d / "source.json", data)
    assert len(errs) == 1 and "malformed" in errs[0]


def test_theme_link_must_resolve():
    repo, data, d = _fresh()
    t = repo / "themes" / "t"
    t.mkdir(parents=True)
    (t / "README.md").write_text(
        f"[a](../../sources/vanguard/{d.name}/transcription.md) [b](https://x) [c](../../nope.md)",
        encoding="utf-8")
    errs = check_themes(repo)
    assert len(errs) == 1 and "nope.md" in errs[0]


def test_missing_data_path_fails():
    repo, _, _ = dirs()
    assert check_run(repo, None) == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "ok")
    print("ok")
