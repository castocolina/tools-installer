import pytest

from installer.versions import VersionError, resolve_github_version


def test_resolve_strips_leading_v():
    def fetch(url: str) -> bytes:
        assert url == "https://api.github.com/repos/BurntSushi/ripgrep/releases/latest"
        return b'{"tag_name": "v14.1.0"}'

    assert resolve_github_version("BurntSushi/ripgrep", fetch) == "14.1.0"


def test_resolve_without_v_prefix():
    def fetch(url: str) -> bytes:
        return b'{"tag_name": "1.2.3"}'

    assert resolve_github_version("a/b", fetch) == "1.2.3"


def test_resolve_missing_tag_raises():
    def fetch(url: str) -> bytes:
        return b"{}"

    with pytest.raises(VersionError, match="no release tag"):
        resolve_github_version("a/b", fetch)


def test_resolve_wraps_network_error():
    def fetch(url: str) -> bytes:
        raise OSError("connection refused")

    with pytest.raises(VersionError, match="failed to resolve version"):
        resolve_github_version("a/b", fetch)


def test_resolve_wraps_invalid_json():
    def fetch(url: str) -> bytes:
        return b"not json"

    with pytest.raises(VersionError, match="failed to resolve version"):
        resolve_github_version("a/b", fetch)


def test_urlopen_fetch_reads_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.versions as versions

    class FakeResp:
        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"tag_name": "v9.9.9"}'

    def fake_urlopen(url: str, timeout: int) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(versions.urllib.request, "urlopen", fake_urlopen)
    assert versions.urlopen_fetch("https://example.com") == b'{"tag_name": "v9.9.9"}'
