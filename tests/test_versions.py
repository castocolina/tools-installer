import json
import urllib.request
from pathlib import Path

import pytest

from installer.versions import (
    PNPM_ALLOW_BUILD_MIN,
    PNPM_CO_INSTALL_MIN,
    VersionError,
    extract_observed_version,
    is_outdated,
    meets_minimum,
    parse_declared_version,
    parse_status_version,
    parse_version,
    probe_version,
    probe_version_output,
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


def _capture_urlopen(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    import installer.versions as versions

    seen: list[urllib.request.Request] = []

    class FakeResp:
        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> FakeResp:
        seen.append(req)
        return FakeResp()

    monkeypatch.setattr(versions.urllib.request, "urlopen", fake_urlopen)
    return seen


@pytest.mark.parametrize("var", ["GITHUB_TOKEN", "GH_TOKEN"])
def test_urlopen_fetch_sends_github_token_to_the_github_api(
    monkeypatch: pytest.MonkeyPatch, var: str
) -> None:
    import installer.versions as versions

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv(var, "tok123")
    seen = _capture_urlopen(monkeypatch)
    versions.urlopen_fetch("https://api.github.com/repos/a/b/releases/latest")
    assert seen[0].get_header("Authorization") == "Bearer tok123"


def test_urlopen_fetch_never_sends_the_token_to_another_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.versions as versions

    monkeypatch.setenv("GITHUB_TOKEN", "tok123")
    seen = _capture_urlopen(monkeypatch)
    versions.urlopen_fetch("https://api.github.com.evil.example/x")
    versions.urlopen_fetch("https://example.com/api.github.com")
    assert [r.get_header("Authorization") for r in seen] == [None, None]


def test_urlopen_fetch_without_a_token_sends_no_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.versions as versions

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    seen = _capture_urlopen(monkeypatch)
    versions.urlopen_fetch("https://api.github.com/repos/a/b/releases/latest")
    assert seen[0].get_header("Authorization") is None


def test_parse_version_strips_v_and_zero_fills() -> None:
    assert parse_version("11.9.0") == (11, 9, 0, 1)
    assert parse_version("v22.12.0") == (22, 12, 0, 1)
    assert parse_version("10.4") == (10, 4, 0, 1)


def test_parse_version_reads_shapes_a_version_line_legitimately_has() -> None:
    """Forgiving about SHAPE: a trailing note, build metadata, a fourth field."""
    assert parse_version("v24.4.0 (arm64)") == (24, 4, 0, 1)
    assert parse_version("1.2.3+build.5") == (1, 2, 3, 1)
    assert parse_version("140.0.7339.16") == (140, 0, 7339, 1)


def test_parse_version_ranks_a_prerelease_below_its_release() -> None:
    """An rc of a release has not necessarily shipped that release's features.

    Cutting the suffix off returned the bare core, which claimed the opposite.
    """
    assert parse_version("25.10.0-rc.1") == (25, 10, 0, 0)
    assert parse_version("11.0.0-beta") == (11, 0, 0, 0)
    prerelease = parse_version("11.0.0-rc.1")
    release = parse_version("11.0.0")
    assert prerelease is not None and release is not None
    assert prerelease < release


def test_parse_version_returns_none_for_unreadable_output() -> None:
    assert parse_version("") is None
    assert parse_version("   ") is None
    assert parse_version("latest") is None
    assert parse_version("not.a.version") is None


def test_parse_version_refuses_a_non_numeric_component_instead_of_zero_filling() -> None:
    """`11.bad` parsed as `(11, 0, 0)` and then SATISFIED an `11.0.0` floor.

    A component this parser cannot read is not a zero; treating it as one turned
    unreadable output into a pass, which is the one answer the fail-closed
    contract must never produce.
    """
    assert parse_version("11.bad") is None
    assert parse_version("22.12.x") is None
    assert parse_version("11.") is None


@pytest.mark.parametrize(
    "text",
    ["-1", "--1", "--2", "-v1.2.3", "a-1"],
    ids=["-1", "--1", "--2", "-v1.2.3", "a-1"],
)
def test_parse_version_never_fabricates_from_a_bare_flag(text: str) -> None:
    assert parse_version(text) is None
    assert parse_status_version(text) is None
    assert extract_observed_version(text) is None


def test_glued_name_versions_still_parse() -> None:
    assert parse_version("jq-1.8.1") == (1, 8, 1, 1)
    assert parse_version("tool-2.3.4-rc.1") == (2, 3, 4, 0)
    assert extract_observed_version("jq-1.8.1") == "jq-1.8.1"


_LAZYGIT_VERSION_LINE = (
    "commit=6b1a1a1, build date=2025-07-19T11:51:45Z, build source=binaryRelease, "
    "version=0.63.1, os=linux, arch=amd64, git version=2.47.0"
)
_PROCS_VERSION_LINE = 'procs "0.14.12 (\u2026'


@pytest.mark.parametrize(
    ("text", "parse_expected", "extract_expected"),
    [
        ("-1", None, None),
        ('"0.20.0"', (0, 20, 0, 1), "0.20.0"),
        (_PROCS_VERSION_LINE, None, "0.14.12"),
        ("'1.2.3'", (1, 2, 3, 1), "1.2.3"),
        (_LAZYGIT_VERSION_LINE, None, "0.63.1"),
        ("version=0.44.1, os=linux", (0, 44, 1, 1), "0.44.1"),
        ('version="1.2.3",', (1, 2, 3, 1), "1.2.3"),
        ("jq-1.8.1", (1, 8, 1, 1), "jq-1.8.1"),
        ("1.2.3", (1, 2, 3, 1), "1.2.3"),
    ],
    ids=[
        "bare-flag",
        "balanced-double-quotes",
        "procs-unbalanced-quote",
        "single-quotes",
        "lazygit-version-equals",
        "version-equals-comma",
        "version-equals-quoted-comma",
        "jq-glued",
        "plain-semver",
    ],
)
def test_observed_version_fixture_table(
    text: str,
    parse_expected: tuple[int, int, int, int] | None,
    extract_expected: str | None,
) -> None:
    assert parse_version(text) == parse_expected
    assert extract_observed_version(text) == extract_expected


def test_parse_status_version_reads_a_quoted_token() -> None:
    assert parse_status_version('"v1.2.3"') == parse_status_version("1.2.3")


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


def test_meets_minimum_refuses_malformed_observed_output() -> None:
    """Observed `11.bad` used to clear an `11.0.0` floor by zero-filling."""
    assert meets_minimum("11.bad", "11.0.0") is False
    assert meets_minimum("22.12.x", "22.12.0") is False


def test_meets_minimum_refuses_a_prerelease_of_the_required_release() -> None:
    """An rc of the release that introduces a feature need not have shipped it."""
    assert meets_minimum("11.0.0-rc.1", "11.0.0") is False
    assert meets_minimum("22.12.0-rc.1", "22.12.0") is False
    assert meets_minimum("11.1.0-rc.1", PNPM_CO_INSTALL_MIN) is False


def test_meets_minimum_accepts_a_prerelease_that_is_past_the_floor() -> None:
    """Ranked below its OWN release, not below every release.

    Rejecting prereleases outright would refuse a machine that is genuinely
    newer than the floor, which is a different wrong answer.
    """
    assert meets_minimum("12.0.0-rc.1", "11.1.0") is True
    assert meets_minimum("11.2.0-rc.1", PNPM_CO_INSTALL_MIN) is True


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


def test_extract_observed_version_finds_the_first_parseable_token() -> None:
    assert extract_observed_version("1.2.0") == "1.2.0"
    assert extract_observed_version("ripgrep 15.2.0") == "15.2.0"
    assert extract_observed_version("gh version 2.98.0 (2026-08-20)") == "2.98.0"
    eza = "eza eza - A modern, maintained replacement for ls\nv0.23.5 [+git]"
    assert extract_observed_version(eza) == "v0.23.5"
    assert extract_observed_version("Usage: dasel <command>") is None
    assert extract_observed_version("gron version dev") is None
    assert extract_observed_version("commit=, build date=, version=0.64.1, os=darwin") == "0.64.1"
    assert extract_observed_version("") is None


def test_parse_version_reads_a_hyphenated_name_prefix_via_fallback() -> None:
    """`jq --version` prints `jq-1.8.1` as one token: the tool's own name glued
    to its version with a hyphen and no separating whitespace. The direct
    match fails, so the fallback strips the name prefix and retries the same
    regex on the trailing, version-shaped segment.
    """
    assert parse_version("jq-1.8.1") == (1, 8, 1, 1)


def test_extract_observed_version_returns_a_name_prefixed_token_verbatim() -> None:
    """The fallback widens which tokens PARSE; the returned token is normalized
    (quotes and `version=` stripped) but a glued name prefix is never removed.
    """
    assert extract_observed_version("jq-1.8.1") == "jq-1.8.1"


def test_is_outdated_ranks_a_name_prefixed_observed_version() -> None:
    """Proves BOTH call sites were fixed, not just `parse_version`: a one-sided
    fix would leave `is_outdated` permanently unable to rank `jq`'s version
    even after `installed` started displaying correctly (Pitfall 1).
    """
    assert is_outdated("jq-1.8.1", "1.8.2") is True
    assert is_outdated("jq-1.8.1", "1.8.1") is False


def test_is_outdated_ranks_full_cores_and_distinct_prereleases() -> None:
    assert is_outdated("1.2.0", "v1.6.0") is True
    assert is_outdated("15.2.0", "15.2.0") is False
    assert is_outdated("10.4.2", "v10.5.0") is True
    assert is_outdated("dev", "v1.0.0") is None
    assert is_outdated("0.28.1-nightly", "v0.28.1") is True
    assert is_outdated("1.2.3+build9", "1.2.3+build1") is False


def test_status_parser_keeps_what_feature_floor_parser_collapses() -> None:
    four_a = parse_version("1.2.3.4")
    four_b = parse_version("1.2.3.5")
    assert four_a == four_b
    assert is_outdated("1.2.3.4", "1.2.3.5") is True
    rc_a = parse_version("1.2.3-rc.1")
    rc_b = parse_version("1.2.3-rc.2")
    assert rc_a == rc_b
    assert is_outdated("1.2.3-rc.1", "1.2.3-rc.2") is True


def test_parse_status_version_discards_build_and_keeps_every_numeric_component() -> None:
    assert parse_status_version("1.2.3.4") == ((1, 2, 3, 4), None)
    assert parse_status_version("v1.6.0") == ((1, 6, 0), None)
    assert parse_status_version("1.2.3+build9") == ((1, 2, 3), None)
    assert parse_status_version("dev") is None


def test_probe_version_output_returns_full_stdout_while_probe_version_stays_first_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.versions as versions

    def fake_output(argv: list[str], timeout: float | None = None) -> str:
        return "first line\nv0.23.5\n"

    monkeypatch.setattr(versions, "run_output", fake_output)
    assert probe_version(["eza", "--version"]) == "first line"
    assert probe_version_output(["eza", "--version"]) == "first line\nv0.23.5\n"


def test_probe_version_output_returns_none_on_error_or_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.versions as versions
    from installer.run import CommandError

    def boom(argv: list[str], timeout: float | None = None) -> str:
        raise CommandError(argv, 127)

    monkeypatch.setattr(versions, "run_output", boom)
    assert probe_version_output(["missing", "--version"]) is None

    def blank(argv: list[str], timeout: float | None = None) -> str:
        return "   \n"

    monkeypatch.setattr(versions, "run_output", blank)
    assert probe_version_output(["empty", "--version"]) is None


def test_versions_module_records_the_registry_wide_audit_finding() -> None:
    """D-04: the live audit's result is recorded in code, not dropped. Deleting
    or hollowing out the comment turns this test red — the comment is the
    mechanism, this test is what keeps it from rotting away unnoticed
    (.claude/architecture.md, "Registry-authoring guidelines").
    """
    import installer.versions as versions

    text = Path(versions.__file__).read_text(encoding="utf-8")
    assert "Verified" in text
    assert "Not covered:" in text
    assert "5.3.9(1)-release" in text
    not_covered = text.split("Not covered:", 1)[1].split("\n# Finds the LAST", 1)[0]
    assert "bash" in not_covered
    assert "procs" not in not_covered


def test_extract_observed_version_still_refuses_the_known_residual_shapes() -> None:
    """`bash`'s extra characters follow the numeric core rather than precede it,
    so no leading-prefix strip can reach them. Procs' leading quote is handled
    by `_normalize_version_token`; this test keeps the bash residual pinned.
    """
    assert extract_observed_version("GNU bash, version 5.3.9(1)-release") is None
