"""Pure batch update planning contracts."""

import ast
import copy
import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import installer.update_all as planner
from installer.deps import Resolution, resolve_dependencies
from installer.model import Method, Tool, load_tools
from installer.ownership import ManagerOwnership
from installer.update import UpdateOutcome, update_refusal
from installer.version_status import ToolState, outdated_ids
from tests.state_doubles import MACOS
from tests.update_all_doubles import (
    catalog_tool,
    confirmed_all,
    no_refusals,
    owned,
    state,
    states_of,
)


def plans(tools: list[Tool], states: dict[str, ToolState]) -> tuple[planner.PlanEntry, ...]:
    evidence = no_refusals(tools)
    return planner.plan_managers(
        tools, states, platform_os="fedora", updated_today={}, refusals=evidence
    ) + planner.plan_dependents(
        tools,
        states,
        outdated_ids(states.values()),
        confirmed=confirmed_all(states.values()),
        platform_os="fedora",
        updated_today={},
        refusals=evidence,
    )


def ids(entries: tuple[planner.PlanEntry, ...]) -> list[str]:
    return [entry.tool_id for entry in entries]


def test_managers_come_first_then_dependents_grouped_by_owner() -> None:
    brew, uv, jq, ruff = (catalog_tool(x) for x in ("brew", "uv", "jq", "ruff"))
    entries = plans(
        [ruff, jq, uv, brew],
        states_of(
            state(brew, "installer"),
            state(uv, "installer"),
            state(jq, "brew", outdated=True, package="jq"),
            state(ruff, "uv", outdated=True, package="ruff"),
        ),
    )
    assert ids(entries) == ["brew", "uv", "jq", "ruff"]
    assert [e.group for e in entries] == ["managers", "managers", "brew", "uv"]
    assert all(e.action == "update" for e in entries)


def test_bun_pnpm_sdkman_groups_follow_the_manager_order() -> None:
    bun, pnpm, sdk = (catalog_tool(x) for x in ("bun", "pnpm", "sdkman"))
    pi = catalog_tool("pi", requires=("bun",))
    mmdc = catalog_tool("mmdc", requires=("bun", "puppeteer"))
    java = catalog_tool("java", requires=("sdkman",))
    tools = [sdk, pnpm, bun, java, mmdc, pi]
    entries = plans(
        tools,
        states_of(
            state(bun, "installer"),
            state(pnpm, "installer"),
            state(sdk, "installer"),
            state(pi, "bun", outdated=True),
            state(mmdc, "pnpm", outdated=True),
            state(java, "sdkman", outdated=True),
        ),
    )
    assert ids(entries) == ["bun", "pnpm", "sdkman", "pi", "mmdc", "java"]
    assert [e.group for e in entries[3:]] == ["bun", "pnpm", "sdkman"]


def test_equal_standing_managers_and_dependents_tie_by_tool_id() -> None:
    tools = [catalog_tool(x) for x in ("volta", "brew", "bun", "z", "a", "m")]
    entries = plans(
        tools,
        states_of(
            *(
                state(t, "installer" if t.id in ("volta", "brew", "bun") else "brew", outdated=True)
                for t in tools
            )
        ),
    )
    assert ids(entries) == ["brew", "bun", "volta", "a", "m", "z"]


def test_a_manager_installed_by_another_follows_it() -> None:
    brew, bun, uv, volta = (catalog_tool(x) for x in ("brew", "bun", "uv", "volta"))
    assert ids(
        plans(
            [volta, uv, bun, brew],
            states_of(
                state(brew, "installer"),
                state(bun, "installer"),
                state(uv, "brew"),
                state(volta, "brew"),
            ),
        )
    ) == ["brew", "bun", "uv", "volta"]


def test_an_ownership_cycle_is_skipped_beside_an_independent_manager() -> None:
    brew, bun, uv, volta, pnpm, dep = (
        catalog_tool(x) for x in ("brew", "bun", "uv", "volta", "pnpm", "dep")
    )
    tools = [pnpm, volta, uv, bun, brew, dep]
    states = states_of(
        state(brew, "installer"),
        state(bun, "uv"),
        state(uv, "bun"),
        state(volta, "uv"),
        state(pnpm, "volta"),
        state(dep, "uv", outdated=True),
    )
    entries = plans(tools, states)
    assert entries == plans(tools, states)
    assert ids(entries) == ["brew", "bun", "uv", "volta", "pnpm", "dep"]
    assert [(e.action, e.reason) for e in entries] == [
        ("update", ""),
        ("skip", "manager ownership cycle"),
        ("skip", "manager ownership cycle"),
        ("skip", "owner is in a manager ownership cycle"),
        ("skip", "owner is in a manager ownership cycle"),
        ("update", ""),
    ]
    assert all(e.group == "managers" for e in entries[:5])
    assert plans([uv], states_of(state(uv, "uv")))[0].action == "update"


def test_a_requires_cycle_skips_that_group_and_nothing_else() -> None:
    brew, uv = catalog_tool("brew"), catalog_tool("uv")
    a, b, c = (
        catalog_tool("a", requires=("b",)),
        catalog_tool("b", requires=("a",)),
        catalog_tool("c"),
    )
    entries = plans(
        [a, b, c, brew, uv],
        states_of(
            state(brew, "installer"),
            state(uv, "installer"),
            state(a, "uv", outdated=True),
            state(b, "uv", outdated=True),
            state(c, "brew", outdated=True),
        ),
    )
    assert [(e.tool_id, e.action, e.reason) for e in entries[2:]] == [
        ("c", "update", ""),
        ("a", "skip", "dependency cycle"),
        ("b", "skip", "dependency cycle"),
    ]


def test_a_cask_owner_groups_with_brew() -> None:
    brew, a, z = (catalog_tool(x) for x in ("brew", "a", "z"))
    entries = plans(
        [z, a, brew],
        states_of(
            state(brew, "installer"),
            state(a, "brew", outdated=True),
            state(z, "cask", outdated=True),
        ),
    )
    assert ids(entries) == ["brew", "a", "z"]
    assert [e.group for e in entries] == ["managers", "brew", "brew"]


def test_dependents_enter_only_when_outdated() -> None:
    brew, a, b, c = (catalog_tool(x) for x in ("brew", "a", "b", "c"))
    states = states_of(
        state(brew, "installer"), state(a, "brew"), state(b, "brew", outdated=True, present=False)
    )
    assert ids(plans([brew, a, b, c], states)) == ["brew"]
    assert plans([], {}) == ()


def test_a_group_orders_by_dependencies_and_drops_outside_requires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uv, alpha, zed, unzip = (
        catalog_tool("uv"),
        catalog_tool("alpha", requires=("zed", "unzip")),
        catalog_tool("zed"),
        catalog_tool("unzip"),
    )
    calls: list[list[str]] = []

    def spy(
        selected: list[Tool],
        catalog: list[Tool],
        *,
        available: Callable[[Tool], bool],
        is_installed: Callable[[Tool], bool],
    ) -> Resolution:
        calls.append([t.id for t in selected])
        return resolve_dependencies(
            selected, catalog, available=available, is_installed=is_installed
        )

    monkeypatch.setattr(planner, "resolve_dependencies", spy)
    entries = plans(
        [uv, alpha, zed, unzip],
        states_of(
            state(uv, "installer"),
            state(alpha, "uv", outdated=True),
            state(zed, "uv", outdated=True),
            state(unzip, "installer", outdated=True),
        ),
    )
    assert ids(entries) == ["uv", "zed", "alpha", "unzip"]
    assert calls == [["alpha", "zed"], ["unzip"]]


def test_non_manager_owners_form_one_final_group() -> None:
    brew, dep, a, b, c = (catalog_tool(x) for x in ("brew", "dep", "a", "b", "c"))
    entries = plans(
        [c, b, a, dep, brew],
        states_of(
            state(brew, "installer"),
            state(dep, "brew", outdated=True),
            state(a, "installer", outdated=True),
            state(b, "os-package", outdated=True),
            state(c, "dnf", outdated=True),
        ),
    )
    assert ids(entries) == ["brew", "dep", "a", "b", "c"]
    assert [e.group for e in entries[2:]] == ["installer", "os-package", "dnf"]


def test_the_plan_is_pure_and_deterministic() -> None:
    brew, jq = catalog_tool("brew"), catalog_tool("jq")
    tools = [brew, jq]
    states = states_of(state(brew, "installer"), state(jq, "brew", outdated=True))
    evidence = no_refusals(tools)
    original = copy.deepcopy((tools, states, evidence))
    args = (tools, states)
    first = planner.plan_managers(*args, platform_os="fedora", updated_today={}, refusals=evidence)
    second = planner.plan_dependents(
        *args, {"jq"}, confirmed={"jq"}, platform_os="fedora", updated_today={}, refusals=evidence
    )
    assert first == planner.plan_managers(
        *args, platform_os="fedora", updated_today={}, refusals=evidence
    )
    assert second == planner.plan_dependents(
        *args, {"jq"}, confirmed={"jq"}, platform_os="fedora", updated_today={}, refusals=evidence
    )
    assert (tools, states, evidence) == original


def test_the_planner_module_has_no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = ast.parse(Path(planner.__file__).read_text(encoding="utf-8"))
    forbidden = {"subprocess", "os", "shutil", "pathlib", "tempfile", "glob"}
    names = {"open", "update_refusal", "read_bun_globals"}
    attrs = {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "exists",
        "is_file",
        "is_dir",
        "iterdir",
        "glob",
        "stat",
        "resolve",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.split(".")[0] in forbidden for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden
        if isinstance(node, ast.Name):
            assert node.id not in names
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in attrs

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(subprocess, "Popen", fail)
    monkeypatch.setattr(subprocess, "run", fail)
    brew = catalog_tool("brew")
    assert ids(plans([brew], states_of(state(brew, "installer")))) == ["brew"]


def test_a_second_outdated_set_changes_only_the_dependents() -> None:
    brew, a, b = (catalog_tool(x) for x in ("brew", "a", "b"))
    tools = [brew, a, b]
    states = states_of(state(brew, "installer"), state(a, "brew"), state(b, "brew"))
    evidence = no_refusals(tools)
    managers = planner.plan_managers(
        tools, states, platform_os="fedora", updated_today={}, refusals=evidence
    )
    assert managers == planner.plan_managers(
        tools, states, platform_os="fedora", updated_today={}, refusals=evidence
    )
    assert ids(
        planner.plan_dependents(
            tools,
            states,
            {"a"},
            confirmed={"a", "b"},
            platform_os="fedora",
            updated_today={},
            refusals=evidence,
        )
    ) == ["a"]
    assert ids(
        planner.plan_dependents(
            tools,
            states,
            {"b"},
            confirmed={"a", "b"},
            platform_os="fedora",
            updated_today={},
            refusals=evidence,
        )
    ) == ["b"]


def batch(
    tools: list[Tool],
    states: dict[str, ToolState],
    *,
    platform_os: str = "fedora",
    refusals: dict[str, UpdateOutcome | None] | None = None,
    updated_today: dict[str, str] | None = None,
    confirmed: set[str] | None = None,
) -> tuple[planner.PlanEntry, ...]:
    evidence = no_refusals(tools) if refusals is None else refusals
    today = {} if updated_today is None else updated_today
    return planner.plan_managers(
        tools, states, platform_os=platform_os, updated_today=today, refusals=evidence
    ) + planner.plan_dependents(
        tools,
        states,
        {t.id for t in tools},
        confirmed={t.id for t in tools} if confirmed is None else confirmed,
        platform_os=platform_os,
        updated_today=today,
        refusals=evidence,
    )


def test_a_macos_cask_is_excluded_and_a_formula_is_planned() -> None:
    cask, formula = catalog_tool("app"), catalog_tool("formula")
    states = states_of(state(cask, "cask", platform=MACOS), state(formula, "brew", platform=MACOS))
    refusal = UpdateOutcome("app", "unsupported", "cask", "refused")
    entries = batch(
        [cask, formula], states, platform_os="macos", refusals={"app": refusal, "formula": None}
    )
    assert [(e.tool_id, e.action, e.reason) for e in entries] == [
        ("app", "skip", "cask excluded"),
        ("formula", "update", ""),
    ]
    assert planner.plan_line(entries[0]) == "app: skipped: cask excluded"
    assert batch([cask], states)[0].action == "update"


def test_refusals_use_the_per_tool_row_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    jq, git, java, node, mystery, pinned = (
        catalog_tool(x) for x in ("jq", "git", "java", "node", "mystery", "pinned")
    )
    owners = [
        owned(jq, "os-package", package="jq"),
        owned(git, "dnf", package="git"),
        owned(java, "sdkman", method=Method(kind="sdkman", params={})),
        owned(node, "volta", package="node"),
        replace(
            owned(mystery, "unknown", confidence="none"),
            unknown_reason="no manager claimed this tool",
        ),
        owned(
            pinned,
            "installer",
            method=Method(
                kind="tarball",
                params={"url": "https://example.test/{ver}", "version": "1", "sha256": "abc"},
            ),
        ),
    ]
    tools = [jq, git, java, node, mystery, pinned]
    states = {
        t.id: replace(state(t, "installer"), ownership=o)
        for t, o in zip(tools, owners, strict=True)
    }
    evidence = {t.id: update_refusal(t, o) for t, o in zip(tools, owners, strict=True)}
    reasons = {e.tool_id: e.reason for e in batch(tools, states, refusals=evidence)}
    assert reasons == {
        "jq": "os-package owns jq",
        "git": "dnf owns git",
        "java": "sdkman owns java",
        "node": "managed by Volta — update it with `volta install node`",
        "mystery": "no manager claimed this tool",
        "pinned": "pinned; update outside or re-pin",
    }


def test_refusal_evidence_is_an_input_and_nothing_spawns(monkeypatch: pytest.MonkeyPatch) -> None:
    a, b, c, d = (catalog_tool(x) for x in ("a", "b", "c", "d"))
    states = states_of(state(a, "brew"), state(b, "brew"), state(c, "cask"), state(d, "installer"))
    assert all(e.action == "update" for e in batch([a, b, c, d], states))
    states["d"] = replace(states["d"], ownership=cast(ManagerOwnership, None))

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError((args, kwargs))

    monkeypatch.setattr(subprocess, "Popen", fail)
    monkeypatch.setattr(subprocess, "run", fail)
    entries = batch([a, b, c, d], states, platform_os="macos", refusals={"a": None, "d": None})
    assert {e.tool_id: (e.action, e.reason) for e in entries} == {
        "a": ("update", ""),
        "b": ("skip", "refusal not evaluated"),
        "c": ("skip", "cask excluded"),
        "d": ("skip", "refusal not evaluated"),
    }


def test_exclusion_is_one_predicate() -> None:
    tool = catalog_tool("app", update=False)
    cask, script = owned(tool, "cask"), owned(tool, "installer")
    refusal = UpdateOutcome("app", "unsupported", "installer", "handoff")
    assert planner.exclusion("macos", cask, refusal) == "cask excluded"
    assert planner.exclusion("fedora", cask, None) is None
    assert planner.exclusion("fedora", script, refusal) == "handoff"
    assert planner.exclusion("fedora", script, None) == "no unattended update path"
    assert planner.exclusion("fedora", owned(catalog_tool("ok"), "installer"), None) is None


def test_no_unattended_update_path_is_one_generic_rule() -> None:
    volta, opencode, script, release = (
        catalog_tool("volta", update=False),
        catalog_tool("opencode", update=False),
        catalog_tool("script"),
        catalog_tool("release", kind="github_release"),
    )
    tools = [volta, opencode, script, release]
    entries = batch(tools, states_of(*(state(t, "installer") for t in tools)))
    assert {e.tool_id: (e.action, e.reason) for e in entries} == {
        "volta": ("skip", "no unattended update path"),
        "opencode": ("skip", "no unattended update path"),
        "script": ("update", ""),
        "release": ("update", ""),
    }
    tree = ast.parse(Path(planner.__file__).read_text(encoding="utf-8"))
    forbidden = {"antigravity", "codex", "fnm", "herdr-app", "kitty", "opencode", "xcode-clt"}
    constants = [
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert not forbidden.intersection(constants)
    assert constants.count("volta") == 1


def test_the_eight_script_tools_without_an_update_argv_are_pinned() -> None:
    """Changing this set is an owner decision (D-09)."""
    tools = load_tools(Path("installer") / "registry.toml")
    assert {
        t.id
        for t in tools
        if any(
            m.kind == "script" and not isinstance(m.params.get("update"), list) for m in t.methods
        )
    } == {"antigravity", "codex", "fnm", "herdr-app", "kitty", "opencode", "volta", "xcode-clt"}


def test_a_handoff_tool_keeps_its_own_refusal_text() -> None:
    tool = catalog_tool("handoff", update=False)
    owner = owned(tool, "installer", method=Method(kind="script", params={"handoff": "xcode-clt"}))
    entries = batch(
        [tool],
        states_of(replace(state(tool, "installer"), ownership=owner)),
        refusals={tool.id: update_refusal(tool, owner)},
    )
    assert (
        entries[0].reason
        == "Apple's Software Update (System Settings) updates the Command Line Tools; "
        "the installer never runs it"
    )


def test_updated_today_skips_managers_and_dependents() -> None:
    brew, a, b = (catalog_tool(x) for x in ("brew", "a", "b"))
    entries = batch(
        [brew, a, b],
        states_of(state(brew, "installer"), state(a, "brew"), state(b, "brew")),
        updated_today={"brew": "job", "a": "job"},
    )
    assert [(e.tool_id, e.reason) for e in entries] == [
        ("brew", "updated today"),
        ("a", "updated today"),
        ("b", ""),
    ]


def test_unconfirmed_evidence_never_authorizes_a_dependent() -> None:
    brew, a = catalog_tool("brew"), catalog_tool("a")
    states = states_of(state(brew, "installer"), state(a, "brew"))
    assert [(e.action, e.reason) for e in batch([brew, a], states, confirmed=set())] == [
        ("update", ""),
        ("skip", "latest version not confirmed"),
    ]
    assert batch([brew, a], states, confirmed={"a"})[1].action == "update"


def test_the_skip_order() -> None:
    c, r, s, u = (
        catalog_tool("c"),
        catalog_tool("r"),
        catalog_tool("s", update=False),
        catalog_tool("u"),
    )
    tools = [c, r, s, u]
    states = states_of(state(c, "cask"), state(r, "brew"), state(s, "installer"), state(u, "brew"))
    evidence = no_refusals(tools)
    evidence["c"] = UpdateOutcome("c", "unsupported", "cask", "refused")
    evidence["r"] = UpdateOutcome("r", "unsupported", "brew", "refused")
    entries = batch(
        tools,
        states,
        platform_os="macos",
        refusals=evidence,
        updated_today={t.id: "job" for t in tools},
        confirmed=set(),
    )
    assert {e.tool_id: e.reason for e in entries} == {
        "c": "cask excluded",
        "r": "refused",
        "s": "no unattended update path",
        "u": "updated today",
    }


def test_blocking_manager() -> None:
    bun, puppet = catalog_tool("bun"), catalog_tool("puppeteer", requires=("bun",))
    tool = catalog_tool("mmdc", requires=("puppeteer",))
    catalog = [bun, puppet, tool]
    assert planner.blocking_manager(tool, "bun", {"bun": "bun"}, catalog) == "bun"
    assert planner.blocking_manager(tool, "pnpm", {"bun": "bun"}, catalog) == "bun"
    assert planner.blocking_manager(tool, "brew", {"bun": "bun", "brew": "brew"}, catalog) == "brew"
    assert planner.blocking_manager(catalog_tool("uv"), "brew", {"brew": "brew"}, catalog) == "brew"
    assert planner.blocking_manager(tool, None, {}, catalog) is None
    assert planner.blocking_manager(tool, None, {"brew": "brew"}, catalog) is None
    cycle = catalog_tool("puppeteer", requires=("mmdc",))
    assert planner.blocking_manager(tool, None, {"brew": "brew"}, [tool, cycle]) is None
    assert planner.blocking_manager(tool, "pnpm", {"bun": "brew"}, catalog) == "brew"


def test_plan_line_and_summary_strings() -> None:
    assert (
        planner.plan_line(planner.PlanEntry("brew", "managers", "update", "", None))
        == "brew (managers): would update"
    )
    assert (
        planner.plan_line(planner.PlanEntry("jq", "brew", "update", "", "brew"))
        == "jq (brew): would update"
    )
    assert (
        planner.plan_line(planner.PlanEntry("jq", "brew", "skip", "updated today", "brew"))
        == "jq: skipped: updated today"
    )
    assert planner.plan_summary(3, 2) == "ok: plan 3 to update, 2 skipped"
    assert (
        planner.PLAN_NOTE
        == "note: a real run refreshes data older than 20 hours, judges dependents again after "
        "the managers update and checks installed files again before it updates a tool"
    )
