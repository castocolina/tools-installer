import json

import pytest

from installer.versions import (
    VersionError,
    meets_minimum,
    parse_declared_version,
    parse_version,
    resolve_github_tag,
)


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


def test_parse_version_strips_v_and_zero_fills() -> None:
    assert parse_version("11.9.0") == (11, 9, 0)
    assert parse_version("v22.12.0") == (22, 12, 0)
    assert parse_version("10.4") == (10, 4, 0)


def test_parse_version_cuts_prerelease_and_whitespace_suffix() -> None:
    assert parse_version("25.10.0-rc.1") == (25, 10, 0)
    assert parse_version("v24.4.0 (arm64)") == (24, 4, 0)


def test_parse_version_returns_none_for_unreadable_output() -> None:
    assert parse_version("") is None
    assert parse_version("latest") is None
    assert parse_version("not.a.version") is None


def test_parse_declared_version_accepts_one_to_three_numeric_groups() -> None:
    assert parse_declared_version("22.12.0") == (22, 12, 0)
    assert parse_declared_version("v22.12.0") == (22, 12, 0)
    assert parse_declared_version("22.12") == (22, 12, 0)
    assert parse_declared_version("22") == (22, 0, 0)


def test_parse_declared_version_rejects_garbage_and_ranges() -> None:
    assert parse_declared_version("22.bad") is None
    assert parse_declared_version("22.") is None
    assert parse_declared_version("^25") is None
    assert parse_declared_version("25.10.0-rc.1") is None
    assert parse_declared_version("latest") is None
    assert parse_declared_version("") is None


def test_meets_minimum_compares_tuples() -> None:
    assert meets_minimum("11.9.0", "11.0.0") is True
    assert meets_minimum("10.4.0", "10.4.0") is True
    assert meets_minimum("10.3.9", "10.4.0") is False
    assert meets_minimum("22.9.0", "22.12.0") is False


def test_meets_minimum_is_fail_closed_on_either_side() -> None:
    assert meets_minimum("latest", "11.0.0") is False
    assert meets_minimum("99.0.0", "22.bad") is False
