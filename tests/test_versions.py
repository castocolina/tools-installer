import json

import pytest

from installer.versions import VersionError, resolve_github_tag


def _fetch(tag: str):
    def fetch(url: str) -> bytes:
        return json.dumps({"tag_name": tag}).encode()

    return fetch


def test_resolve_returns_tag_verbatim_with_leading_v():
    assert resolve_github_tag("sharkdp/fd", _fetch("v10.4.2")) == "v10.4.2"


def test_resolve_returns_bare_tag_verbatim():
    assert resolve_github_tag("BurntSushi/ripgrep", _fetch("15.1.0")) == "15.1.0"


def test_resolve_raises_when_tag_missing():
    with pytest.raises(VersionError, match="no release tag"):
        resolve_github_tag("a/b", _fetch(""))


def test_resolve_raises_on_bad_json():
    def fetch(url: str) -> bytes:
        return b"not json"

    with pytest.raises(VersionError, match="failed to resolve tag"):
        resolve_github_tag("a/b", fetch)


def test_resolve_raises_on_network_error():
    def fetch(url: str) -> bytes:
        raise OSError("network down")

    with pytest.raises(VersionError, match="failed to resolve tag"):
        resolve_github_tag("a/b", fetch)


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
