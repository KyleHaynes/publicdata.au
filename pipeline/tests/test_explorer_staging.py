import hashlib
import io
import threading

from publicdata import explorer


def _together(fn, n=4):
    barrier, errors, results = threading.Barrier(n, timeout=30), [], []

    def run(i):
        try:
            barrier.wait()
            results.append(fn(i))
        except BaseException as e:  # noqa: BLE001 - a thread's error is reported by the test
            errors.append(e)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    return results


def test_builds_staging_the_same_libraries_at_once_all_get_them(tmp_path, monkeypatch):
    monkeypatch.setattr(explorer, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(explorer, "_need_node_modules", lambda: None)
    staging = threading.Barrier(4, timeout=30)

    def stage(dest):
        (dest / "lib").mkdir(parents=True)
        staging.wait()  # every build is mid-stage before any finishes
        (dest / "lib" / "a.js").write_text("a", encoding="utf-8")

    monkeypatch.setattr(explorer, "_stage", stage)
    paths = _together(lambda i: explorer.vendor(tmp_path / f"out{i}"))
    assert len(set(paths)) == 1
    for i in range(4):
        assert (tmp_path / f"out{i}" / paths[0].strip("/") / "lib" / "a.js").read_text() == "a"
    # One staged folder is left, and no build's temporary one.
    assert len(list((tmp_path / "cache" / "vendor").iterdir())) == 1


def test_builds_fetching_the_same_extension_at_once_all_read_it_whole(tmp_path, monkeypatch):
    data = b"wasm" * 100_000
    sha = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(explorer, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(explorer.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(data))
    assert _together(lambda i: explorer._extension("parquet", sha)) == [data] * 4
    folder = tmp_path / "cache" / "extensions" / explorer.DUCKDB_VERSION
    assert [p.name for p in folder.iterdir()] == ["parquet.duckdb_extension.wasm"]
