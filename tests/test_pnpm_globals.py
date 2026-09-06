import os
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from installer import pnpm_globals
from installer.guards import REDIRECT_SENTINEL
from installer.model import Method, Tool, load_tools
from installer.pnpm_globals import (
    LIST_TIMEOUT_SECONDS,
    NodeGlobal,
    NodeGlobalsReport,
    NodeInstallPolicy,
    PnpmUnavailable,
    audit_node_globals,
    node_globals,
    node_install_policy,
    parse_global_groups,
    parse_global_packages,
    pnpm_global_groups,
    pnpm_global_packages,
    reinstall_argv,
    reinstall_node_globals,
    reinstall_preview,
    split_install_groups,
)
from installer.run import TIMEOUT_CODE, CommandError
from installer.ui_common import run_live

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _tool(
    tool_id: str,
    *,
    cmd: str | None = None,
    methods: tuple[Method, ...] | None = None,
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="diagram",
        cmd=cmd or tool_id,
        methods=methods or (Method(kind="brew", params={"formula": tool_id}),),
    )


def _mmdc() -> Tool:
    return Tool(
        id="mmdc",
        name="Mermaid CLI",
        category="diagram",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )


def _plant_executable(directory: Path, name: str, body: str = "#!/bin/sh\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body)
    path.chmod(0o755)
    return path


def test_node_globals_empty() -> None:
    assert node_globals([]) == ()


def test_node_globals_ignores_brew_only() -> None:
    assert node_globals([_tool("rg")]) == ()


def test_node_globals_mmdc_like() -> None:
    assert node_globals([_mmdc()]) == (
        NodeGlobal(tool_id="mmdc", npm_pkg="@mermaid-js/mermaid-cli", cmd="mmdc"),
    )


def test_node_globals_skips_node_method_without_npm_pkg() -> None:
    tool = _tool(
        "broken",
        methods=(Method(kind="node", params={}),),
    )
    assert node_globals([tool]) == ()


def test_node_globals_preserves_order_one_entry_per_tool() -> None:
    first = Tool(
        id="a",
        name="a",
        category="diagram",
        cmd="a",
        methods=(
            Method(kind="node", params={"npm_pkg": "pkg-a"}),
            Method(kind="node", params={"npm_pkg": "pkg-a-second"}),
            Method(kind="brew", params={"formula": "a"}),
        ),
    )
    second = Tool(
        id="b",
        name="b",
        category="diagram",
        cmd="b",
        methods=(Method(kind="node", params={"npm_pkg": "pkg-b"}),),
    )
    entries = node_globals([_tool("rg"), first, second])
    assert [e.tool_id for e in entries] == ["a", "b"]
    assert entries[0].npm_pkg == "pkg-a"


MMDC_PKG = "@mermaid-js/mermaid-cli"
_PNPM_LIST_JSON = """
[
  {
    "name": "global",
    "path": "/Users/x/Library/pnpm/global/5",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {"from": "@mermaid-js/mermaid-cli", "version": "10.9.1"},
      "vercel": {"from": "vercel", "version": "39.1.1"}
    }
  }
]
"""


def _managed(*packages: str) -> Callable[[], tuple[str, ...] | None]:
    def read() -> tuple[str, ...] | None:
        return packages

    return read


def test_parse_global_packages_reads_pnpm_list_json() -> None:
    assert parse_global_packages(_PNPM_LIST_JSON) == (MMDC_PKG, "vercel")


def test_parse_global_packages_handles_an_empty_global_set() -> None:
    assert parse_global_packages('[{"path": "/g", "private": true}]') == ()


def test_parse_global_packages_ignores_a_non_object_entry() -> None:
    assert parse_global_packages('["noise", {"dependencies": {"vercel": {}}}]') == ("vercel",)


def test_parse_global_packages_unreadable_output_is_unknown() -> None:
    assert parse_global_packages("not json") is None
    assert parse_global_packages('"a string"') is None


def test_pnpm_global_packages_asks_pnpm_by_absolute_path() -> None:
    calls: list[list[str]] = []

    def runner_out(cmd: list[str]) -> str:
        calls.append(cmd)
        return _PNPM_LIST_JSON

    packages = pnpm_global_packages(resolve_pnpm=lambda: "/real/bin/pnpm", runner_out=runner_out)
    assert packages == (MMDC_PKG, "vercel")
    assert calls == [["/real/bin/pnpm", "list", "-g", "--json"]]


def test_pnpm_global_packages_unknown_when_pnpm_unresolvable() -> None:
    def never(_cmd: list[str]) -> str:
        raise AssertionError("must not run a command without a resolved pnpm")

    assert pnpm_global_packages(resolve_pnpm=lambda: None, runner_out=never) is None


def test_pnpm_global_packages_unknown_when_the_query_fails() -> None:
    def boom(cmd: list[str]) -> str:
        raise CommandError(cmd, 1)

    assert pnpm_global_packages(resolve_pnpm=lambda: "/real/bin/pnpm", runner_out=boom) is None


def test_pnpm_global_packages_reads_a_timeout_as_unknown() -> None:
    def wedged(cmd: list[str]) -> str:
        raise CommandError(cmd, TIMEOUT_CODE, detail="timed out after 20s")

    assert pnpm_global_packages(resolve_pnpm=lambda: "/real/bin/pnpm", runner_out=wedged) is None


def test_the_global_set_query_is_time_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    # The one caller that matters runs inside a Textual thread worker the Doctor
    # screen is waiting on, so an unbounded `pnpm list -g --json` (pnpm can
    # block indefinitely on store-lock contention) leaves the screen checking
    # forever with no interruptible path.
    seen: list[float | None] = []

    def fake_run_output(cmd: list[str], *, timeout: float | None = None) -> str:
        assert cmd[1:] == ["list", "-g", "--json"]
        seen.append(timeout)
        return "[]"

    monkeypatch.setattr(pnpm_globals, "run_output", fake_run_output)
    assert pnpm_global_packages(resolve_pnpm=lambda: "/real/bin/pnpm") == ()
    assert seen == [LIST_TIMEOUT_SECONDS]
    assert 0 < LIST_TIMEOUT_SECONDS <= 60


def test_audit_reports_only_what_pnpm_actually_manages() -> None:
    # The catalog DECLARES mmdc; pnpm does not manage it. Reporting the catalog
    # as the installed set told every such user a self-update lost their globals.
    report = audit_node_globals([_mmdc()], which=lambda _n: None, managed=_managed("vercel"))
    assert report.entries == ()
    assert report.missing == ()
    assert report.managed == ("vercel",)


def test_audit_lists_a_tracked_global_whose_command_is_gone() -> None:
    report = audit_node_globals([_mmdc()], which=lambda _n: None, managed=_managed(MMDC_PKG))
    assert report.missing == ("mmdc",)
    assert report.entries == node_globals([_mmdc()])
    assert report.managed == (MMDC_PKG,)


def test_audit_healthy_when_command_resolves() -> None:
    report = audit_node_globals([_mmdc()], which=lambda _n: "/x/mmdc", managed=_managed(MMDC_PKG))
    assert report.missing == ()
    assert report.entries == node_globals([_mmdc()])


def test_audit_claims_nothing_when_pnpm_cannot_be_asked() -> None:
    report = audit_node_globals([_mmdc()], which=lambda _n: None, managed=lambda: None)
    assert report == NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)


def test_audit_distinguishes_unknown_from_a_genuinely_empty_global_set() -> None:
    # The two used to be byte-identical, so no consumer could tell "pnpm manages
    # nothing" from "pnpm could not be asked" — and the Doctor stated the second
    # as the first.
    unknown = audit_node_globals([_mmdc()], which=lambda _n: None, managed=lambda: None)
    empty = audit_node_globals([_mmdc()], which=lambda _n: None, managed=_managed())
    assert unknown.known is False
    assert empty.known is True
    assert unknown != empty
    assert (unknown.entries, unknown.missing, unknown.managed) == (
        empty.entries,
        empty.missing,
        empty.managed,
    )


def test_preview_of_an_unknown_set_does_not_borrow_the_empty_sets_wording() -> None:
    empty = reinstall_preview((), known=True, resolve_pnpm=lambda: "/real/bin/pnpm")
    unknown = reinstall_preview((), known=False, resolve_pnpm=lambda: "/real/bin/pnpm")
    assert empty == "nothing pnpm-managed to reinstall"
    assert unknown != empty
    assert "could not be read" in unknown


def test_audit_keeps_non_catalog_globals_in_the_managed_set() -> None:
    report = audit_node_globals(
        [_mmdc()], which=lambda _n: "/x/mmdc", managed=_managed(MMDC_PKG, "vercel")
    )
    assert report.managed == (MMDC_PKG, "vercel")
    assert [e.tool_id for e in report.entries] == ["mmdc"]


def test_reinstall_argv_one_invocation_absolute_pnpm() -> None:
    assert reinstall_argv([MMDC_PKG], pnpm="/real/bin/pnpm") == [
        "/real/bin/pnpm",
        "add",
        "-g",
        MMDC_PKG,
    ]


def test_reinstall_argv_replays_hand_installed_globals_too() -> None:
    # One `pnpm add -g` supersedes the whole global set, so an argv built from
    # the registry alone would discard everything the user added by hand.
    argv = reinstall_argv([MMDC_PKG, "vercel", "typescript"], pnpm="/real/bin/pnpm")
    assert argv[3:] == [MMDC_PKG, "vercel", "typescript"]


def test_reinstall_argv_deduplicates_preserving_order() -> None:
    argv = reinstall_argv(["a", "b", "a"], pnpm="/real/bin/pnpm")
    assert argv[3:] == ["a", "b"]


def test_reinstall_argv_empty_raises() -> None:
    with pytest.raises(ValueError):
        reinstall_argv((), pnpm="/real/bin/pnpm")


def test_reinstall_node_globals_calls_runner_once() -> None:
    calls: list[list[str]] = []
    pkgs = reinstall_node_globals(
        [MMDC_PKG, "vercel"],
        runner=calls.append,
        resolve_pnpm=lambda: "/real/bin/pnpm",
    )
    assert pkgs == (MMDC_PKG, "vercel")
    assert calls == [["/real/bin/pnpm", "add", "-g", MMDC_PKG, "vercel"]]
    assert all(call[0] != "pnpm" for call in calls)


def test_reinstall_node_globals_empty_is_noop() -> None:
    calls: list[list[str]] = []

    def never() -> str | None:
        raise AssertionError("resolver must not be called")

    assert reinstall_node_globals([], runner=calls.append, resolve_pnpm=never) == ()
    assert calls == []


def test_reinstall_node_globals_unresolvable_pnpm_raises_without_running() -> None:
    calls: list[list[str]] = []
    with pytest.raises(PnpmUnavailable) as exc_info:
        reinstall_node_globals([MMDC_PKG], runner=calls.append, resolve_pnpm=lambda: None)
    assert calls == []
    # No command ran, so the message must not claim one failed.
    message = str(exc_info.value)
    assert "command failed" not in message
    assert "install pnpm" in message


def test_pnpm_unavailable_reaches_run_live_without_a_screen_level_except() -> None:
    # Architecture rule 3: a screen supplies the closure, never its own except.
    def boom() -> tuple[str, ...]:
        return reinstall_node_globals([MMDC_PKG], resolve_pnpm=lambda: None)

    result, error = run_live(boom)
    assert result is None
    assert error is not None
    assert "install pnpm" in error


def test_reinstall_skips_wrapper_first_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    wrapper = _plant_executable(
        tmp_path / ".local" / "bin",
        "pnpm",
        body=f"#!/bin/sh\n{REDIRECT_SENTINEL}\n",
    )
    real = _plant_executable(tmp_path / "real", "pnpm")
    monkeypatch.setenv("PATH", f"{wrapper.parent}{os.pathsep}{real.parent}")
    calls: list[list[str]] = []
    reinstall_node_globals([MMDC_PKG], runner=calls.append)
    assert calls
    assert calls[0][0] == str(real)
    assert all(call[0] != "pnpm" for call in calls)


def test_reinstall_preview_empty_does_not_resolve() -> None:
    def never() -> str | None:
        raise AssertionError("resolver must not be called")

    text = reinstall_preview((), resolve_pnpm=never)
    assert "nothing pnpm-managed to reinstall" in text


def test_reinstall_preview_names_every_package_it_will_replace() -> None:
    text = reinstall_preview([MMDC_PKG, "vercel"], resolve_pnpm=lambda: "/real/bin/pnpm")
    assert text == shlex.join(reinstall_argv([MMDC_PKG, "vercel"], pnpm="/real/bin/pnpm"))
    assert "vercel" in text


def test_reinstall_preview_unresolvable_is_message_not_argv() -> None:
    text = reinstall_preview([MMDC_PKG], resolve_pnpm=lambda: None)
    assert "pnpm" in text
    assert "add" not in text


def test_real_registry_residual_set_contains_mmdc() -> None:
    # Phase 5's REQ-mmdc-install-decision may move mmdc off pnpm add -g, at
    # which point this assertion — not the mechanism — changes.
    entries = node_globals(load_tools(REGISTRY))
    assert entries
    assert "mmdc" in {e.tool_id for e in entries}


MMDC_NPM = "@mermaid-js/mermaid-cli"
_EXPLICIT_POLICY = NodeInstallPolicy(
    groups=((MMDC_NPM, "puppeteer"),),
    allow_build=("puppeteer",),
    versions=(("puppeteer", "^25"),),
)


def test_node_install_policy_empty_inputs() -> None:
    assert node_install_policy([]) == NodeInstallPolicy()
    assert NodeInstallPolicy() == NodeInstallPolicy(groups=(), allow_build=(), versions=())


def test_node_install_policy_from_shipped_registry() -> None:
    policy = node_install_policy(load_tools(REGISTRY))
    assert policy.groups == ((MMDC_NPM, "puppeteer"),)
    assert policy.allow_build == ("puppeteer",)
    assert policy.versions == (("puppeteer", "^25"),)


def test_node_install_policy_explicit_fixture_matches_shipped_shape() -> None:
    # Built by hand so a future registry edit cannot quietly turn the argv
    # cases into a tautology against whatever the catalog happens to say.
    assert _EXPLICIT_POLICY.groups == ((MMDC_NPM, "puppeteer"),)
    assert _EXPLICIT_POLICY.allow_build == ("puppeteer",)
    assert _EXPLICIT_POLICY.versions == (("puppeteer", "^25"),)


def test_shipped_registry_declares_no_conflicting_version_pins() -> None:
    seen: dict[str, str] = {}
    for tool in load_tools(REGISTRY):
        method = next((item for item in tool.methods if item.kind == "node"), None)
        if method is None:
            continue
        raw = method.params.get("versions")
        if not isinstance(raw, dict):
            continue
        table = cast(dict[object, object], raw)
        for name, range_ in table.items():
            assert isinstance(name, str) and isinstance(range_, str)
            previous = seen.get(name)
            assert previous is None or previous == range_, (
                f"conflicting pins for {name}: {previous!r} vs {range_!r}"
            )
            seen[name] = range_


def test_node_install_policy_skips_node_method_without_npm_pkg() -> None:
    tool = _tool("broken", methods=(Method(kind="node", params={}),))
    assert node_install_policy([tool]) == NodeInstallPolicy()


def test_node_install_policy_first_pin_wins() -> None:
    first = _tool(
        "a",
        methods=(
            Method(
                kind="node",
                params={"npm_pkg": "alpha", "versions": {"alpha": "^1"}},
            ),
        ),
    )
    second = _tool(
        "b",
        methods=(
            Method(
                kind="node",
                params={"npm_pkg": "beta", "versions": {"alpha": "^2", "beta": "^3"}},
            ),
        ),
    )
    policy = node_install_policy([first, second])
    assert policy.versions == (("alpha", "^1"), ("beta", "^3"))


def test_reinstall_argv_without_policy_is_byte_identical_to_today() -> None:
    assert reinstall_argv(["a", "b"], pnpm="/x/pnpm") == ["/x/pnpm", "add", "-g", "a", "b"]


def test_reinstall_argv_groups_pins_and_allows_the_declared_pair() -> None:
    argv = reinstall_argv([MMDC_NPM, "puppeteer"], pnpm="/x/pnpm", policy=_EXPLICIT_POLICY)
    assert argv == [
        "/x/pnpm",
        "add",
        "-g",
        "--allow-build=puppeteer",
        f"{MMDC_NPM},puppeteer@^25",
    ]


def test_reinstall_argv_keeps_ungrouped_packages_as_their_own_elements() -> None:
    argv = reinstall_argv(
        ["typescript", MMDC_NPM, "puppeteer"],
        pnpm="/x/pnpm",
        policy=_EXPLICIT_POLICY,
    )
    assert argv[0:4] == ["/x/pnpm", "add", "-g", "--allow-build=puppeteer"]
    assert "typescript" in argv
    assert f"{MMDC_NPM},puppeteer@^25" in argv
    assert argv.count("typescript") == 1
    assert "typescript" not in f"{MMDC_NPM},puppeteer@^25"


def test_reinstall_argv_partial_group_replays_only_what_is_present() -> None:
    argv = reinstall_argv(["puppeteer", "typescript"], pnpm="/x/pnpm", policy=_EXPLICIT_POLICY)
    joined = " ".join(argv)
    assert "mermaid" not in joined
    assert "typescript" in argv
    assert "puppeteer@^25" in argv
    assert not any("," in item for item in argv)


def test_reinstall_argv_preserves_order_and_collapses_duplicates() -> None:
    argv = reinstall_argv(
        ["typescript", "typescript", MMDC_NPM, MMDC_NPM, "puppeteer"],
        pnpm="/x/pnpm",
        policy=_EXPLICIT_POLICY,
    )
    specs = [item for item in argv[3:] if not item.startswith("--allow-build=")]
    assert specs == ["typescript", f"{MMDC_NPM},puppeteer@^25"]


def test_reinstall_preview_equals_argv_when_policy_is_supplied() -> None:
    pkgs = [MMDC_NPM, "puppeteer"]
    preview = reinstall_preview(pkgs, policy=_EXPLICIT_POLICY, resolve_pnpm=lambda: "/x/pnpm")
    assert preview == shlex.join(reinstall_argv(pkgs, pnpm="/x/pnpm", policy=_EXPLICIT_POLICY))


def test_reinstall_preview_known_false_empty_and_unresolvable_ignore_policy() -> None:
    def never() -> str | None:
        raise AssertionError("resolver must not be called")

    assert reinstall_preview((), known=False, policy=_EXPLICIT_POLICY, resolve_pnpm=never) == (
        "pnpm's global set could not be read — cannot preview the reinstall."
    )
    assert reinstall_preview((), policy=_EXPLICIT_POLICY, resolve_pnpm=never) == (
        "nothing pnpm-managed to reinstall"
    )
    text = reinstall_preview([MMDC_NPM], policy=_EXPLICIT_POLICY, resolve_pnpm=lambda: None)
    assert "pnpm" in text
    assert "add" not in text


def _const_probe(result: str | None) -> Callable[[list[str]], str | None]:
    def probe(_argv: list[str]) -> str | None:
        return result

    return probe


def test_reinstall_node_globals_returns_specs_never_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pnpm_globals, "probe_version", _const_probe("11.9.0"))
    calls: list[list[str]] = []
    got = reinstall_node_globals(
        [MMDC_NPM, "puppeteer"],
        runner=calls.append,
        resolve_pnpm=lambda: "/x/pnpm",
        policy=_EXPLICIT_POLICY,
    )
    assert got == (f"{MMDC_NPM},puppeteer@^25",)
    assert not any(item.startswith("--allow-build") for item in got)
    assert calls == [
        ["/x/pnpm", "add", "-g", "--allow-build=puppeteer", f"{MMDC_NPM},puppeteer@^25"]
    ]


def test_reinstall_node_globals_empty_policy_probes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def capture(argv: list[str]) -> str:
        seen.append(argv)
        return "1.0.0"

    monkeypatch.setattr(pnpm_globals, "probe_version", capture)
    calls: list[list[str]] = []
    got = reinstall_node_globals(
        ["a", "b"],
        runner=calls.append,
        resolve_pnpm=lambda: "/x/pnpm",
    )
    assert seen == []
    assert calls == [["/x/pnpm", "add", "-g", "a", "b"]]
    assert got == ("a", "b")


def test_reinstall_node_globals_refuses_grouped_form_on_old_pnpm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pnpm_globals, "probe_version", _const_probe("10.9.0"))
    calls: list[list[str]] = []
    with pytest.raises(PnpmUnavailable, match=r"(?s)(?=.*10[.]9[.]0)(?=.*11[.]0[.]0)"):
        reinstall_node_globals(
            [MMDC_NPM, "puppeteer"],
            runner=calls.append,
            resolve_pnpm=lambda: "/x/pnpm",
            policy=_EXPLICIT_POLICY,
        )
    assert calls == []


def test_reinstall_node_globals_allow_build_only_uses_allow_build_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = NodeInstallPolicy(allow_build=("puppeteer",), versions=(("puppeteer", "^25"),))
    monkeypatch.setattr(pnpm_globals, "probe_version", _const_probe("10.3.0"))
    calls: list[list[str]] = []
    with pytest.raises(PnpmUnavailable, match=r"(?s)(?=.*10[.]3[.]0)(?=.*10[.]4[.]0)"):
        reinstall_node_globals(
            ["puppeteer"],
            runner=calls.append,
            resolve_pnpm=lambda: "/x/pnpm",
            policy=policy,
        )
    assert calls == []
    monkeypatch.setattr(pnpm_globals, "probe_version", _const_probe("10.9.0"))
    got = reinstall_node_globals(
        ["puppeteer"],
        runner=calls.append,
        resolve_pnpm=lambda: "/x/pnpm",
        policy=policy,
    )
    assert got == ("puppeteer@^25",)
    assert calls == [["/x/pnpm", "add", "-g", "--allow-build=puppeteer", "puppeteer@^25"]]


# Captured in plan 05-01 Container C (`pnpm list -g --json` on pnpm 12.3.4).
# Membership is the per-package path hash, not multiple project objects: both
# documents are a single project object; mermaid-cli and puppeteer share a
# hash only after the grouped remedy. Host prefix trimmed; hash directories
# are verbatim.
_SPLIT_STATE_JSON = """
[
  {
    "path": "/root/.local/share/pnpm/global/v11",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {
        "from": "@mermaid-js/mermaid-cli",
        "version": "11.17.0",
        "path": "/g/v11/14f2-18d28dc072dbf202-0/node_modules/@mermaid-js/mermaid-cli"
      },
      "@pnpm/exe": {
        "from": "@pnpm/exe",
        "version": "12.3.4",
        "path": "/g/v11/14d6-18d28dbf8bf82d48-0/node_modules/@pnpm/exe"
      },
      "puppeteer": {
        "from": "puppeteer",
        "version": "25.10.0",
        "path": "/g/v11/151d-18d28dce58a8e9af-0/node_modules/puppeteer"
      }
    }
  }
]
"""
_GROUPED_STATE_JSON = """
[
  {
    "path": "/root/.local/share/pnpm/global/v11",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {
        "from": "@mermaid-js/mermaid-cli",
        "version": "11.17.0",
        "path": "/g/v11/15c0-18d28df958d4debd-0/node_modules/@mermaid-js/mermaid-cli"
      },
      "@pnpm/exe": {
        "from": "@pnpm/exe",
        "version": "12.3.4",
        "path": "/g/v11/14d6-18d28dbf8bf82d48-0/node_modules/@pnpm/exe"
      },
      "puppeteer": {
        "from": "puppeteer",
        "version": "25.10.0",
        "path": "/g/v11/15c0-18d28df958d4debd-0/node_modules/puppeteer"
      }
    }
  }
]
"""


def _group_of(live: pnpm_globals.GlobalGroups, name: str) -> tuple[str, ...]:
    for group in live.groups:
        if name in group:
            return group
    raise AssertionError(f"{name} not in {live}")


def test_parse_global_groups_split_state_holds_mmdc_and_puppeteer_apart() -> None:
    groups = parse_global_groups(_SPLIT_STATE_JSON)
    assert groups is not None
    assert _group_of(groups, MMDC_NPM) != _group_of(groups, "puppeteer")


def test_parse_global_groups_grouped_state_holds_mmdc_and_puppeteer_together() -> None:
    groups = parse_global_groups(_GROUPED_STATE_JSON)
    assert groups is not None
    assert _group_of(groups, MMDC_NPM) == _group_of(groups, "puppeteer")
    assert MMDC_NPM in _group_of(groups, "puppeteer")


def test_parse_global_groups_unreadable_output_is_unknown() -> None:
    assert parse_global_groups("not json") is None
    assert parse_global_groups('"a string"') is None


def test_split_install_groups_reports_present_members_held_apart() -> None:
    policy = _EXPLICIT_POLICY
    split = pnpm_globals.GlobalGroups(groups=((MMDC_NPM,), ("puppeteer",)))
    ok = pnpm_globals.GlobalGroups(groups=((MMDC_NPM, "puppeteer"),))
    assert split_install_groups(policy, split) == ((MMDC_NPM, "puppeteer"),)
    assert split_install_groups(policy, ok) == ()
    assert split_install_groups(policy, pnpm_globals.GlobalGroups(groups=(("puppeteer",),))) == ()
    assert split_install_groups(NodeInstallPolicy(), split) == ()


def test_audit_without_policy_skips_the_group_query_and_reports_no_split() -> None:
    grouped_calls: list[int] = []

    def grouped() -> pnpm_globals.GlobalGroups | None:
        grouped_calls.append(1)
        return pnpm_globals.GlobalGroups(groups=((MMDC_NPM,), ("puppeteer",)))

    report = audit_node_globals(
        [_mmdc()],
        which=lambda _n: "/x/mmdc",
        managed=_managed(MMDC_NPM, "puppeteer"),
        grouped=grouped,
    )
    assert grouped_calls == []
    assert report.split_groups == ()
    assert report.managed == (MMDC_NPM, "puppeteer")


def test_audit_with_policy_detects_a_split_from_the_real_document() -> None:
    policy = node_install_policy(load_tools(REGISTRY))
    report = audit_node_globals(
        load_tools(REGISTRY),
        which=lambda _n: "/x/bin",
        grouped=lambda: parse_global_groups(_SPLIT_STATE_JSON),
        policy=policy,
    )
    assert report.split_groups == ((MMDC_NPM, "puppeteer"),)
    assert MMDC_NPM in report.managed
    assert "puppeteer" in report.managed


def test_audit_with_policy_is_quiet_on_the_grouped_document() -> None:
    policy = node_install_policy(load_tools(REGISTRY))
    report = audit_node_globals(
        load_tools(REGISTRY),
        which=lambda _n: "/x/bin",
        grouped=lambda: parse_global_groups(_GROUPED_STATE_JSON),
        policy=policy,
    )
    assert report.split_groups == ()


def test_audit_with_policy_unknown_group_query_is_not_a_finding() -> None:
    policy = node_install_policy(load_tools(REGISTRY))
    report = audit_node_globals(
        load_tools(REGISTRY),
        which=lambda _n: None,
        grouped=lambda: None,
        policy=policy,
    )
    assert report == NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
    assert report.split_groups == ()


def test_pnpm_global_groups_asks_pnpm_by_absolute_path() -> None:
    calls: list[list[str]] = []

    def runner_out(cmd: list[str]) -> str:
        calls.append(cmd)
        return _SPLIT_STATE_JSON

    groups = pnpm_global_groups(resolve_pnpm=lambda: "/real/bin/pnpm", runner_out=runner_out)
    assert groups is not None
    assert _group_of(groups, MMDC_NPM) != _group_of(groups, "puppeteer")
    assert calls == [["/real/bin/pnpm", "list", "-g", "--json"]]


def test_replay_regroups_a_brownfield_split_mmdc_and_puppeteer() -> None:
    """A machine that already had a standalone mmdc never runs the catalog's
    grouped invocation, because installer/engine.py::install_tool returns
    ALREADY_INSTALLED and installer/deps.py drops installed tools from the
    order, so it ends up with the two packages in two isolated groups; this
    replay is the documented remedy, and plan 05-01's Tier-3 container
    measured it rendering successfully afterwards.
    """
    policy = node_install_policy(load_tools(REGISTRY))
    argv = reinstall_argv([MMDC_NPM, "puppeteer"], pnpm="/x/pnpm", policy=policy)
    specs = [item for item in argv[3:] if not item.startswith("--allow-build=")]
    assert specs == [f"{MMDC_NPM},puppeteer@^25"]


def test_reinstall_node_globals_refuses_when_version_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pnpm_globals, "probe_version", _const_probe(None))
    calls: list[list[str]] = []
    with pytest.raises(PnpmUnavailable, match="could not be read"):
        reinstall_node_globals(
            [MMDC_NPM, "puppeteer"],
            runner=calls.append,
            resolve_pnpm=lambda: "/x/pnpm",
            policy=_EXPLICIT_POLICY,
        )
    assert calls == []


# pnpm reported the packages but not the per-package `path`, which is the only
# membership signal `parse_global_groups` has. The module's own docstring calls
# that field version-dependent ("the project objects ARE the install groups on
# some pnpm versions"), so this is a shape the code already knows it does not
# control.
_PATHLESS_STATE_JSON = """
[
  {
    "path": "/root/.local/share/pnpm/global/v11",
    "private": true,
    "dependencies": {
      "@mermaid-js/mermaid-cli": {
        "from": "@mermaid-js/mermaid-cli",
        "version": "11.17.0"
      },
      "puppeteer": {
        "from": "puppeteer",
        "version": "25.10.0"
      }
    }
  }
]
"""


def test_unreadable_membership_is_unknown_not_a_group_of_one() -> None:
    """ "pnpm did not say" must never render as "this package is held apart".

    Same rule as NodeGlobalsReport.known one level up: an unanswered query is
    not a finding. The per-package fallback key made the two byte-identical.
    """
    live = parse_global_groups(_PATHLESS_STATE_JSON)
    assert live is not None
    assert set(live.unknown) == {MMDC_NPM, "puppeteer"}
    assert split_install_groups(_EXPLICIT_POLICY, live) == ()


def test_audit_does_not_report_a_split_it_could_not_read() -> None:
    policy = node_install_policy(load_tools(REGISTRY))
    report = audit_node_globals(
        load_tools(REGISTRY),
        which=lambda _n: "/x/bin",
        grouped=lambda: parse_global_groups(_PATHLESS_STATE_JSON),
        policy=policy,
    )
    assert report.split_groups == ()
    # The packages themselves were read fine, so they still belong in the set
    # the replay puts back — only their MEMBERSHIP was unreadable.
    assert MMDC_NPM in report.managed
    assert "puppeteer" in report.managed


def test_a_single_unreadable_member_suppresses_the_whole_group_verdict() -> None:
    """One known member and one unknown one is still not evidence of a split."""
    live = pnpm_globals.GlobalGroups(
        groups=((MMDC_NPM,), ("puppeteer",)),
        unknown=("puppeteer",),
    )
    assert split_install_groups(_EXPLICIT_POLICY, live) == ()
