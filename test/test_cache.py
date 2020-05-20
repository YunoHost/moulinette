import os.path


def test_open_cachefile_creates(monkeypatch, tmp_path):
    monkeypatch.setenv("MOULINETTE_CACHE_DIR", str(tmp_path))

    from moulinette.cache import open_cachefile

    handle = open_cachefile("foo.cache", mode="w")

    assert handle.mode == "w"
    assert handle.name == os.path.join(str(tmp_path), "foo.cache")
