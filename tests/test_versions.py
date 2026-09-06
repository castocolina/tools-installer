import json

import pytest

from installer.versions import (
    PNPM_ALLOW_BUILD_MIN,
    PNPM_CO_INSTALL_MIN,
    VersionError,
    meets_minimum,
    parse_declared_version,
    parse_version,
    probe_version,
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


def test_pnpm_floors_match_documented_feature_versions() -> None:
    assert PNPM_CO_INSTALL_MIN == "11.1.0"
    assert PNPM_ALLOW_BUILD_MIN == "10.4.0"
    assert callable(probe_version)


def test_co_install_floor_rejects_every_pnpm_11_0_patch() -> None:
    """11.0.x has the hash-keyed global layout but not the shared install group.

    The floor was 11.0.0, so a machine on 11.0.x passed the preflight and then
    ran a comma spec pnpm does not group — the exact silent misbehaviour the
    preflight is there to refuse.
    """
    assert meets_minimum("11.0.0", PNPM_CO_INSTALL_MIN) is False
    assert meets_minimum("11.0.9", PNPM_CO_INSTALL_MIN) is False


def test_co_install_floor_accepts_the_first_version_with_the_feature() -> None:
    assert meets_minimum("11.1.0", PNPM_CO_INSTALL_MIN) is True
    assert meets_minimum("11.9.0", PNPM_CO_INSTALL_MIN) is True
    assert meets_minimum("12.0.0", PNPM_CO_INSTALL_MIN) is True


def test_probe_version_returns_first_nonempty_line(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.versions as versions

    def fake_output(argv: list[str], timeout: float | None = None) -> str:
        return "\n  11.9.0\n"

    monkeypatch.setattr(versions, "run_output", fake_output)
    assert versions.probe_version(["/x/pnpm", "--version"]) == "11.9.0"


def test_probe_version_returns_none_on_command_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.versions as versions
    from installer.run import CommandError

    def boom(argv: list[str], timeout: float | None = None) -> str:
        raise CommandError(argv, 127)

    monkeypatch.setattr(versions, "run_output", boom)
    assert versions.probe_version(["/x/pnpm", "--version"]) is None


def test_each_consumer_holds_its_own_probe_version_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The patch point is the CONSUMER's name, never `installer.versions`.

    Both consumers do `from installer.versions import probe_version`, which
    binds the function object at import time, so rebinding the definition
    module leaves them untouched. The docstring on `_default_probe_version`
    once advertised the opposite; this pins the behaviour the wording now
    describes, so a future test that patches the wrong name fails here instead
    of silently probing the real machine.
    """
    import installer.executors as executors
    import installer.pnpm_globals as pnpm_globals
    import installer.versions as versions

    def sentinel(_argv: list[str]) -> str | None:
        return "0.0.0-from-the-definition-module"

    monkeypatch.setattr(versions, "probe_version", sentinel)
    assert executors.probe_version is not sentinel
    assert pnpm_globals.probe_version is not sentinel
    assert executors.probe_version is pnpm_globals.probe_version
