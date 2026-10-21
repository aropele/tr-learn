# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import contextlib
import hashlib
import io
import json
import tempfile
from pathlib import Path

from add import run, infer_kind, front_matter
from check import check_source, check_themes, run as check_run


class FakeStore:
    def __init__(self, fail_put=False, fail_list=False):
        self.objects = {}  # path relative to REMOTE -> bytes
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
                if not p or k.startswith(p + "/")}  # folder semantics, like rclone


def dirs():
    return Path(tempfile.mkdtemp()), FakeStore(), Path(tempfile.mkdtemp())


def raises_exit(fn):
    try:
        fn()
    except SystemExit:
        return
    assert False, "expected SystemExit"


def test_video_writes_sidecar_and_front_matter():
    repo, store, _ = dirs()
    d = run(["https://www.youtube.com/watch?v=x", "--publisher", "vanguard",
             "--title", "Some Video", "--kind", "video"], repo, store)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert d == repo / "sources/vanguard" / meta["id"] and meta["original"] is None
    assert meta["published"] is None and meta["id"].startswith(meta["fetched_at"][:10])
    assert list(meta) == ["id", "title", "publisher", "authors", "published", "kind", "url",
                          "canonical_url", "fetched_at", "original", "notes"]
    assert (d / "transcription.md").read_text(encoding="utf-8") == front_matter(meta)
    assert store.objects == {}


def test_popular_flag_marks_sidecar_and_front_matter():
    repo, store, _ = dirs()
    d = run(["https://ofdollarsanddata.com/x/", "--publisher", "ofdollarsanddata",
             "--title", "Some Post", "--kind", "video", "--popular"], repo, store)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    fm = (d / "transcription.md").read_text(encoding="utf-8")
    assert meta["register"] == "popular" and fm == front_matter(meta)
    assert 'register: "popular"' in fm and "professional" in fm


def _pdf_args(f):
    return ["https://corporate.vanguard.com/x.pdf", "--publisher", "vanguard", "--title",
            "Vanguard Capital Markets Model", "--published", "2026-09", "--file", str(f)]


def test_file_ingest_writes_original_and_sha():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    d = run(_pdf_args(f), repo, store)
    meta = json.loads((d / "source.json").read_text(encoding="utf-8"))
    assert meta["id"] == "2026-09-00-vanguard-capital-markets-model" and meta["kind"] == "pdf"
    assert meta["original"]["path"] == "sources/vanguard/2026-09-00-vanguard-capital-markets-model/original.pdf"
    assert store.objects[meta["original"]["path"]] == b"%PDF-1.4 test"
    assert list(meta["original"]) == ["path", "sha256", "md5"]
    assert meta["original"]["sha256"] == hashlib.sha256(b"%PDF-1.4 test").hexdigest()
    assert meta["original"]["md5"] == hashlib.md5(b"%PDF-1.4 test").hexdigest()


def test_existing_id_is_refused():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    d = run(_pdf_args(f), repo, store)
    before = (d / "source.json").read_bytes()
    raises_exit(lambda: run(_pdf_args(f), repo, store))
    assert (d / "source.json").read_bytes() == before


def test_pdf_url_returning_html_is_refused():
    try:
        infer_kind("https://x.com/a.pdf", "text/html", b"<html>cookies</html>")
        assert False
    except ValueError:
        pass
    assert infer_kind("https://x.com/page", "text/html; charset=utf-8", b"<html>") == "html"


def test_failed_download_leaves_nothing():
    repo, store, _ = dirs()
    raises_exit(lambda: run(["http://127.0.0.1:9/x.pdf", "--publisher", "vanguard",
                             "--title", "T"], repo, store))
    assert not (repo / "sources").exists() and store.objects == {}


def test_mirror_without_canonical_is_refused():
    repo, store, _ = dirs()
    raises_exit(lambda: run(["https://externalcrewnet.vanguard.com/x", "--publisher", "vanguard",
                             "--title", "T", "--kind", "video"], repo, store))
    assert not (repo / "sources").exists()


def test_bad_published_is_refused():
    repo, store, _ = dirs()
    raises_exit(lambda: run(["https://x.com/p", "--publisher", "vanguard", "--title", "T",
                             "--published", "2026-9", "--kind", "video"], repo, store))
    assert not (repo / "sources").exists()


def _msg(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    assert False, "expected SystemExit"


def test_missing_file_is_clean_exit():
    repo, store, tmp = dirs()
    m = _msg(lambda: run(_pdf_args(tmp / "nope.pdf"), repo, store))
    assert "cannot read --file" in m
    assert not (repo / "sources").exists() and store.objects == {}


def test_write_failure_cleans_up_without_absolute_path():
    import add
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    real = add.Path.write_text

    def boom(*a, **k):
        raise PermissionError(5, "Access is denied")
    add.Path.write_text = boom
    try:
        m = _msg(lambda: run(_pdf_args(f), repo, store))
    finally:
        add.Path.write_text = real
    assert "write failed for sources/vanguard/" in m and str(repo) not in m
    assert not (repo / "sources/vanguard").exists() or not list((repo / "sources/vanguard").iterdir())
    assert store.objects == {}
    run(_pdf_args(f), repo, store)  # retry is not blocked by an orphan


def test_kind_pdf_with_non_pdf_is_refused():
    repo, store, tmp = dirs()
    f = tmp / "x.html"
    f.write_bytes(b"<html></html>")
    m = _msg(lambda: run(["https://x.com/p", "--publisher", "vanguard", "--title", "T",
                          "--kind", "pdf", "--file", str(f)], repo, store))
    assert "not a PDF" in m and not (repo / "sources").exists() and store.objects == {}


def test_failed_upload_leaves_no_repo_folder():
    repo, _, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    m = _msg(lambda: run(_pdf_args(f), repo, FakeStore(fail_put=True)))
    assert m == "rclone failed: upload refused"
    assert not (repo / "sources/vanguard/2026-09-00-vanguard-capital-markets-model").exists()


def test_existing_remote_prefix_refuses_id():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    store.objects["sources/vanguard/2026-09-00-vanguard-capital-markets-model/original.pdf"] = b"old"
    assert "source already exists" in _msg(lambda: run(_pdf_args(f), repo, store))
    assert not (repo / "sources").exists()


def test_remote_prefix_of_longer_id_is_not_a_collision():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    store.objects["sources/vanguard/2026-09-00-vanguard-capital-markets-model-2/original.pdf"] = b"x"
    run(_pdf_args(f), repo, store)  # must not exit


def test_front_matter_is_yaml_safe():
    fm = front_matter({"id": "i", "title": 'A: B "q"', "publisher": "v",
                       "published": "2022", "url": "u"}).splitlines()
    assert 'title: ' + json.dumps('A: B "q"') in fm and 'published: "2022"' in fm
    assert "published: null" in front_matter({"id": "i", "title": "t", "publisher": "v",
                                              "published": None, "url": "u"}).splitlines()


def _fresh():
    repo, store, tmp = dirs()
    f = tmp / "x.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    return repo, store, run(_pdf_args(f), repo, store)


def _meta(d):
    return json.loads((d / "source.json").read_text(encoding="utf-8"))


def _save(d, meta):
    (d / "source.json").write_text(json.dumps(meta), encoding="utf-8")


def test_fresh_source_only_warns_empty_body():
    repo, store, d = _fresh()
    errs, warns = check_source(d / "source.json", store.md5s())
    assert errs == [] and len(warns) == 1 and "empty transcription body" in warns[0]


def test_tampered_original_is_error():
    repo, store, d = _fresh()
    store.objects[_meta(d)["original"]["path"]] = b"%PDF-1.4 evil"
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "md5 mismatch" in errs[0]


def test_missing_original_is_error():
    repo, store, d = _fresh()
    del store.objects[_meta(d)["original"]["path"]]
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "original missing" in errs[0]


def test_object_without_md5_is_mismatch():
    repo, store, d = _fresh()
    path = _meta(d)["original"]["path"]
    errs, _ = check_source(d / "source.json", {path: ""})
    assert errs == [f"{_meta(d)['id']}: original md5 mismatch: {path}"]


def test_front_matter_mismatch_is_error():
    repo, store, d = _fresh()
    m = _meta(d)
    m["title"] = "Other"
    _save(d, m)
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "front-matter differs" in errs[0]


def test_id_date_mismatch_is_error():
    repo, store, d = _fresh()
    m = _meta(d)
    m["published"] = "2025"
    _save(d, m)
    (d / "transcription.md").write_text(front_matter(m), encoding="utf-8", newline="\n")
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "date" in errs[0]


def test_body_present_no_warning():
    repo, store, d = _fresh()
    with open(d / "transcription.md", "a", encoding="utf-8", newline="\n") as f:
        f.write("\n# Heading\ntext\n")
    assert check_source(d / "source.json", store.md5s()) == ([], [])


def test_non_object_sidecar_is_error():
    repo, store, d = _fresh()
    (d / "source.json").write_text("[1]", encoding="utf-8")
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "malformed" in errs[0]


def test_original_missing_sha_is_error():
    repo, store, d = _fresh()
    m = _meta(d)
    del m["original"]["sha256"]
    _save(d, m)
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "malformed" in errs[0]


def test_original_missing_md5_is_error():
    repo, store, d = _fresh()
    m = _meta(d)
    del m["original"]["md5"]
    _save(d, m)
    errs, _ = check_source(d / "source.json", store.md5s())
    assert len(errs) == 1 and "malformed" in errs[0]


def test_theme_link_must_resolve():
    repo, store, d = _fresh()
    t = repo / "themes" / "t"
    t.mkdir(parents=True)
    (t / "README.md").write_text(
        f"[a](../../sources/vanguard/{d.name}/transcription.md) [b](https://x) [c](../../nope.md)",
        encoding="utf-8")
    errs = check_themes(repo)
    assert len(errs) == 1 and "nope.md" in errs[0]


def test_rclone_failure_fails():
    repo, _, _ = dirs()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert check_run(repo, FakeStore(fail_list=True)) == 1
    assert "rclone failed: listing refused" in out.getvalue()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "ok")
    print("ok")
