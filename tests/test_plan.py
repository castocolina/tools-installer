import subprocess
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import cast

import pytest

from installer.model import ConfigStep, Method, Tool
from installer.ownership import UNMANAGEABLE_OWNERS, Owner, owner_label
from installer.platform import Platform
from installer.receipts import CHANGED_SINCE_INSTALL
from installer.session import (
    RESULT_WORDS,
    WORDS,
    Disposition,
    PlanRow,
    Result,
    build_plan,
    review_counts,
)
from installer.version_status import BROKEN_SHIM_REASON, Health, ToolState, VersionStatus
from tests.state_doubles import MACOS, pass_state, plan_state

_BREW = Method(kind="brew", params={"formula": "x"})


class _PlanRowBuilder(typing.Protocol):
    def __call__(
        self,
        tool: Tool,
        state: ToolState | None,
        *,
        requester: str | None,
        direct: bool,
        platform: Platform,
        reinstall: frozenset[str],
    ) -> PlanRow: ...


_plan_row = cast(_PlanRowBuilder, import_module("installer.session")._row)


def _build_row(
    tool: Tool,
    state: ToolState | None,
    *,
    requester: str | None,
    direct: bool,
    platform: Platform,
    reinstall: frozenset[str],
) -> PlanRow:
    return _plan_row(
        tool,
        state,
        requester=requester,
        direct=direct,
        platform=platform,
        reinstall=reinstall,
    )


def _tool(
    tool_id: str,
    *,
    tier: str = "user",
    requires: tuple[str, ...] = (),
    methods: tuple[Method, ...] = (_BREW,),
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=methods,
        priority="P3",
        audience="both",
        tier=tier,
        requires=requires,
    )


def _state_of(states: Mapping[str, ToolState | None]) -> Callable[[str], ToolState | None]:
    return states.get


def test_misconfigured_direct_row_with_steps_is_will_reconfigure_listing_them():
    tool = _tool("pony")
    steps = (
        ConfigStep("install ponytail for Codex", "skill_install", "codex"),
        ConfigStep("sync terminals", "terminal_sync"),
    )
    state = plan_state(
        tool,
        health=Health.MISCONFIGURED,
        reasons=("partial: missing on Codex — details",),
        unconfigured=steps,
    )

    row = _build_row(
        tool, state, requester=None, direct=True, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason, row.steps) == (
        Disposition.RECONFIGURE,
        "partial: missing on Codex",
        steps,
    )


def test_misconfigured_direct_row_without_steps_is_blocked_with_the_reason():
    tool = _tool("pony")
    state = plan_state(
        tool, health=Health.MISCONFIGURED, reasons=("project pack: no repo detected",)
    )

    row = _build_row(
        tool, state, requester=None, direct=True, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason, row.steps) == (
        Disposition.BLOCKED,
        "project pack: no repo detected",
        (),
    )


def test_misconfigured_dragged_dependency_is_already_present_with_the_reason():
    tool = _tool("pony")
    state = plan_state(
        tool,
        health=Health.MISCONFIGURED,
        reasons=("partial: missing on Codex — details",),
        unconfigured=(ConfigStep("install ponytail for Codex", "skill_install", "codex"),),
    )

    row = _build_row(
        tool, state, requester="mmdc", direct=False, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason, row.steps) == (
        Disposition.SKIP,
        "already present; partial: missing on Codex",
        (),
    )


@pytest.mark.parametrize("owner", ("installer", "brew", "uv", "pnpm"))
def test_outdated_direct_row_is_will_update_when_the_owner_allows(owner: Owner):
    tool = _tool("jq")
    if owner == "pnpm":
        tool = _tool("jq", methods=(Method(kind="node", params={"npm_pkg": "jq"}),))
    version = VersionStatus("jq", "1.7.1", "1.8.0", True, False, "test")
    state = plan_state(
        tool,
        health=Health.OUTDATED,
        owner=owner,
        method=tool.methods[0] if owner == "pnpm" else None,
        version=version,
        reasons=("outdated",),
    )

    row = _build_row(
        tool, state, requester=None, direct=True, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason, row.ownership) == (
        Disposition.UPDATE,
        "1.7.1 -> 1.8.0",
        state.ownership,
    )


def test_outdated_direct_row_with_unreadable_versions_reads_update_available():
    tool = _tool("jq")
    version = VersionStatus("jq", None, "1.8.0", True, False, "test")
    state = plan_state(tool, health=Health.OUTDATED, version=version, reasons=("outdated",))

    row = _build_row(
        tool, state, requester=None, direct=True, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason) == (Disposition.UPDATE, "update available")


@pytest.mark.parametrize(
    ("owner", "expected"),
    (
        ("dnf", "managed by dnf"),
        ("os-package", "managed by OS package"),
        ("volta", "managed by Volta"),
        ("unknown", "no update source"),
    ),
)
def test_outdated_direct_row_is_skipped_managed_by_a_refusing_owner(owner: Owner, expected: str):
    tool = _tool("jq")
    state = plan_state(tool, health=Health.OUTDATED, owner=owner, reasons=("outdated",))

    row = _build_row(
        tool, state, requester=None, direct=True, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason) == (Disposition.SKIP, expected)


def test_outdated_dragged_dependency_is_already_present_with_the_reason():
    tool = _tool("jq")
    state = plan_state(tool, health=Health.OUTDATED, reasons=("outdated: 1 -> 2",))

    row = _build_row(
        tool, state, requester="mmdc", direct=False, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason) == (
        Disposition.SKIP,
        f"already present; {state.reasons[0].split(' — ', 1)[0]}",
    )


def test_all_current_selection_plans_only_skipped_rows():
    tools = [_tool("a"), _tool("b"), _tool("c")]
    states = {tool.id: plan_state(tool) for tool in tools}

    selected = [tool.id for tool in tools]
    first = build_plan(selected, tools, _state_of(states), MACOS, reinstall=frozenset())
    second = build_plan(selected, tools, _state_of(states), MACOS, reinstall=frozenset())

    assert first == second
    assert all(row.disposition is Disposition.SKIP for row in first)


def test_off_policy_outdated_row_with_unknown_declared_manager_names_only_the_real_owner(
    monkeypatch: pytest.MonkeyPatch,
):
    tool = _tool("jq")
    state = plan_state(
        tool,
        health=Health.OUTDATED,
        owner="brew",
        confidence="none",
        off_policy=True,
        reasons=("outdated",),
    )

    def no_declared_manager(*_args: object) -> None:
        return None

    monkeypatch.setattr("installer.session.declared_manager_label", no_declared_manager)

    row = _build_row(
        tool, state, requester=None, direct=True, platform=MACOS, reinstall=frozenset()
    )

    assert (row.disposition, row.reason) == (Disposition.SKIP, "managed by Homebrew")


def test_no_sudo_argv_on_the_plan_path():
    for path in ("installer/session.py", "installer/deps.py"):
        source = Path(path).read_text()
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        assert all(f'"{command}"' not in code for command in ("sudo", "pkexec", "doas"))


def test_broken_shim_direct_row_is_will_repair():
    rg = _tool("rg")
    state = plan_state(rg, health=Health.BROKEN, reasons=(BROKEN_SHIM_REASON,))

    row = build_plan(["rg"], [rg], _state_of({"rg": state}), MACOS, reinstall=frozenset())[0]

    assert (row.disposition, row.reason, row.health) == (
        Disposition.REPAIR,
        "shim present, package missing",
        Health.BROKEN,
    )


def test_broken_by_receipt_drift_is_will_repair_with_the_drift_reason():
    rg = _tool("rg")
    state = plan_state(rg, health=Health.BROKEN, reasons=(f"{CHANGED_SINCE_INSTALL} — edited",))

    row = build_plan(["rg"], [rg], _state_of({"rg": state}), MACOS, reinstall=frozenset())[0]

    assert (row.disposition, row.reason) == (
        Disposition.REPAIR,
        "changed since install; the file is replaced",
    )


def test_broken_dragged_dependency_is_will_repair_under_its_requester():
    node = _tool("node")
    mmdc = _tool("mmdc", requires=("node",))
    catalog = [node, mmdc]
    states = {
        "node": plan_state(node, health=Health.BROKEN, reasons=(BROKEN_SHIM_REASON,)),
        "mmdc": plan_state(mmdc, health=Health.MISSING, present=False),
    }

    rows = build_plan(["mmdc"], catalog, _state_of(states), MACOS, reinstall=frozenset())

    node_row = next(row for row in rows if row.tool_id == "node")
    assert (node_row.disposition, node_row.reason, node_row.requested_by) == (
        Disposition.REPAIR,
        "shim present, package missing; needed by mmdc",
        "mmdc",
    )
    assert [row.tool_id for row in rows].index("node") < [row.tool_id for row in rows].index("mmdc")


@pytest.mark.parametrize("owner", sorted(UNMANAGEABLE_OWNERS))
def test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired(owner: Owner):
    rg = _tool("rg")
    state = plan_state(rg, health=Health.BROKEN, owner=owner, reasons=(BROKEN_SHIM_REASON,))

    row = build_plan(["rg"], [rg], _state_of({"rg": state}), MACOS, reinstall=frozenset())[0]

    assert (row.disposition, row.reason) == (
        Disposition.BLOCKED,
        f"{owner_label(state.ownership)} owns it; repair needs sudo (never run here)",
    )


def test_dependent_of_a_plan_time_blocked_dependency_is_blocked_needs_it():
    node = _tool("node")
    mmdc = _tool("mmdc", requires=("node",))
    third = _tool("third", requires=("node",))
    b = _tool("b", requires=("node",))
    a = _tool("a", requires=("b",))
    catalog = [mmdc, third, a, b, node]
    states = {
        "node": plan_state(node, health=Health.BROKEN, owner="dnf", reasons=(BROKEN_SHIM_REASON,)),
        "mmdc": plan_state(mmdc, health=Health.MISSING, present=False),
        "third": plan_state(third),
        "b": plan_state(b, health=Health.MISSING, present=False),
        "a": plan_state(a, health=Health.MISSING, present=False),
    }

    rows = build_plan(
        ["mmdc", "third", "a"], catalog, _state_of(states), MACOS, reinstall=frozenset()
    )

    by_id = {row.tool_id: row for row in rows}
    assert (by_id["node"].disposition, by_id["node"].requested_by) == (Disposition.BLOCKED, "mmdc")
    assert by_id["node"].reason == (
        f"{owner_label(states['node'].ownership)} owns it; repair needs sudo (never run here)"
    )
    assert (by_id["mmdc"].disposition, by_id["mmdc"].reason) == (Disposition.BLOCKED, "needs node")
    assert (by_id["b"].disposition, by_id["b"].reason) == (Disposition.BLOCKED, "needs node")
    assert (by_id["a"].disposition, by_id["a"].reason) == (Disposition.BLOCKED, "needs b")
    assert (by_id["third"].disposition, by_id["third"].reason) == (
        Disposition.SKIP,
        "already current",
    )


def test_build_plan_plans_one_missing_tool_as_will_install():
    catalog = [_tool("rg")]
    state_of = _state_of({"rg": plan_state(catalog[0], health=Health.MISSING, present=False)})

    rows = build_plan(["rg"], catalog, state_of, MACOS, reinstall=frozenset())

    assert [(r.tool_id, r.disposition, r.reason, r.requested_by, r.health) for r in rows] == [
        ("rg", Disposition.INSTALL, "not installed", None, Health.MISSING)
    ]


def test_build_plan_spawns_no_subprocess(monkeypatch: pytest.MonkeyPatch):
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("build_plan must not spawn")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    catalog = [_tool("rg")]
    state_of = _state_of({"rg": plan_state(catalog[0], health=Health.MISSING, present=False)})

    rows = build_plan(["rg"], catalog, state_of, MACOS, reinstall=frozenset())

    assert [row.tool_id for row in rows] == ["rg"]


def test_words_cover_every_disposition_and_result():
    for disposition in Disposition:
        assert WORDS[disposition].review
    for disposition in Disposition:
        if disposition is Disposition.WAIT:
            assert WORDS[disposition].done is None
        else:
            assert WORDS[disposition].done
    for result in typing.get_args(Result):
        if result == "done":
            continue
        assert RESULT_WORDS[result][0]


def test_review_counts_joins_non_zero_counts_in_table_order():
    rows = [
        PlanRow("a", Disposition.INSTALL, "not installed"),
        PlanRow("b", Disposition.INSTALL, "not installed"),
        PlanRow("c", Disposition.UPDATE, "1 -> 2"),
        PlanRow("d", Disposition.SKIP, "already current"),
        PlanRow("e", Disposition.SKIP, "already current"),
        PlanRow("f", Disposition.SKIP, "already current"),
        PlanRow("g", Disposition.BLOCKED, "needs h"),
    ]

    assert review_counts(rows) == "2 will install, 1 will update, 3 skipped, 1 blocked"
    assert review_counts([]) == "nothing selected"


NO_BREW = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)


def _unavailable(tool: Tool) -> ToolState:
    """The state the refresh pass publishes for a brew-only tool on a host without brew."""
    return pass_state(tool, platform=NO_BREW, present=False)


def test_dragged_missing_dependency_is_will_install_needed_by_its_requester():
    node, mmdc = _tool("node"), _tool("mmdc", requires=("node",))
    catalog = [node, mmdc]
    state_of = _state_of(
        {
            "node": plan_state(node, health=Health.MISSING, present=False),
            "mmdc": plan_state(mmdc, health=Health.MISSING, present=False),
        }
    )

    rows = build_plan(["mmdc"], catalog, state_of, MACOS, reinstall=frozenset())

    assert [(r.tool_id, r.disposition, r.reason, r.requested_by) for r in rows] == [
        ("node", Disposition.INSTALL, "needed by mmdc", "mmdc"),
        ("mmdc", Disposition.INSTALL, "not installed", None),
    ]


def test_dragged_present_dependency_is_skipped_already_present():
    node, mmdc = _tool("node"), _tool("mmdc", requires=("node",))
    catalog = [node, mmdc]
    state_of = _state_of(
        {
            "node": plan_state(node, owner="brew"),
            "mmdc": plan_state(mmdc, health=Health.MISSING, present=False),
        }
    )

    rows = build_plan(["mmdc"], catalog, state_of, MACOS, reinstall=frozenset())

    node_row = next(r for r in rows if r.tool_id == "node")
    assert (node_row.disposition, node_row.reason, node_row.can_reinstall) == (
        Disposition.SKIP,
        "already present",
        False,
    )
    assert node_row.requested_by == "mmdc"


def test_dependency_needed_by_two_selected_tools_is_listed_once_under_the_first():
    dep = _tool("dep")
    a, b = _tool("a", requires=("dep",)), _tool("b", requires=("dep",))
    catalog = [a, b, dep]
    state_of = _state_of(
        {
            "a": plan_state(a, health=Health.MISSING, present=False),
            "b": plan_state(b, health=Health.MISSING, present=False),
            "dep": plan_state(dep, health=Health.MISSING, present=False),
        }
    )

    rows = build_plan(["b", "a"], catalog, state_of, MACOS, reinstall=frozenset())

    dep_rows = [r for r in rows if r.tool_id == "dep"]
    assert len(dep_rows) == 1
    assert dep_rows[0].requested_by == "a"


def test_selected_and_needed_tool_is_a_direct_row():
    dep = _tool("dep")
    a = _tool("a", requires=("dep",))
    catalog = [a, dep]
    state_of = _state_of(
        {
            "a": plan_state(a, health=Health.MISSING, present=False),
            "dep": plan_state(dep, health=Health.MISSING, present=False),
        }
    )

    rows = build_plan(["a", "dep"], catalog, state_of, MACOS, reinstall=frozenset())

    dep_row = next(r for r in rows if r.tool_id == "dep")
    assert (dep_row.reason, dep_row.requested_by) == ("not installed", None)


def test_unavailable_dragged_dependency_blocks_its_dependent():
    z = _tool("z")
    # `c` carries a script method, so it stays available and is blocked only by `z`.
    c = Tool(
        id="c",
        name="c",
        category="search",
        cmd="c",
        methods=(Method(kind="script", params={}),),
        priority="P3",
        audience="both",
        tier="user",
        requires=("z",),
    )
    catalog = [c, z]
    state_of = _state_of(
        {
            "c": plan_state(c, health=Health.MISSING, present=False),
            "z": _unavailable(z),
        }
    )

    rows = build_plan(["c"], catalog, state_of, NO_BREW, reinstall=frozenset())

    by_id = {r.tool_id: r for r in rows}
    assert by_id["z"].disposition is Disposition.BLOCKED
    assert by_id["z"].reason == "needs Homebrew, which is not on PATH"
    assert by_id["z"].requested_by == "c"
    assert by_id["c"].disposition is Disposition.BLOCKED
    assert by_id["c"].reason == "needs z"


@dataclass(frozen=True)
class _ProbeCase:
    selection: tuple[str, ...]
    catalog: tuple[Tool, ...]
    states: dict[str, ToolState | None]
    reinstall: frozenset[str]
    expected: tuple[tuple[str, Disposition, str, bool, str | None], ...]


def _probe_case(case: str, tier: str) -> _ProbeCase:
    if case == "A":
        dep, top = _tool("rg", tier=tier), _tool("mmdc", tier=tier, requires=("rg",))
        return _ProbeCase(
            ("mmdc",),
            (dep, top),
            {"rg": None, "mmdc": plan_state(top, health=Health.MISSING, present=False)},
            frozenset(),
            (
                ("rg", Disposition.WAIT, "", False, "mmdc"),
                ("mmdc", Disposition.INSTALL, "not installed", False, None),
            ),
        )
    if case == "B":
        tool = _tool("rg", tier=tier)
        return _ProbeCase(
            ("rg",),
            (tool,),
            {"rg": plan_state(tool)},
            frozenset(),
            (("rg", Disposition.SKIP, "already current", True, None),),
        )
    if case == "C":
        rg, fd = _tool("rg", tier=tier), _tool("fd", tier=tier)
        return _ProbeCase(
            ("rg", "fd"),
            (rg, fd),
            {"rg": plan_state(rg), "fd": plan_state(fd, health=Health.MISSING, present=False)},
            frozenset(),
            (
                ("rg", Disposition.SKIP, "already current", True, None),
                ("fd", Disposition.INSTALL, "not installed", False, None),
            ),
        )
    if case == "D":
        tool = _tool("jq", tier=tier)
        return _ProbeCase(
            ("jq",),
            (tool,),
            {"jq": plan_state(tool, health=Health.OUTDATED, owner="dnf")},
            frozenset(),
            (("jq", Disposition.SKIP, "managed by dnf", False, None),),
        )
    if case == "E":
        tool = _tool("rg", tier=tier)
        state = plan_state(tool, health=Health.BROKEN, reasons=(BROKEN_SHIM_REASON,))
        return _ProbeCase(
            ("rg",),
            (tool,),
            {"rg": state},
            frozenset(),
            (("rg", Disposition.REPAIR, "shim present, package missing", False, None),),
        )
    if case == "F":
        tool = _tool(
            "rg", tier=tier, methods=(Method(kind="github_release", params={"repo": "x/y"}),)
        )
        return _ProbeCase(
            ("rg",),
            (tool,),
            {"rg": plan_state(tool, owner="brew", off_policy=True)},
            frozenset(),
            (
                (
                    "rg",
                    Disposition.SKIP,
                    "managed by Homebrew; the catalog installs it via GitHub release",
                    False,
                    None,
                ),
            ),
        )
    if case == "G":
        tool = _tool("zsh", tier=tier)
        return _ProbeCase(
            ("zsh",),
            (tool,),
            {"zsh": plan_state(tool)},
            frozenset({"zsh"}),
            (("zsh", Disposition.REINSTALL, "reinstall requested; r again to undo", True, None),),
        )
    if case == "H":
        tool = Tool(
            id="rtk",
            name="rtk",
            category="search",
            cmd="rtk",
            methods=(_BREW,),
            priority="P3",
            audience="both",
            tier=tier,
            postinstall="test_hook",
        )
        return _ProbeCase(
            ("rtk",),
            (tool,),
            {"rtk": plan_state(tool)},
            frozenset(),
            (("rtk", Disposition.SKIP, "already current", True, None),),
        )
    tool = _tool("rg", tier=tier)
    return _ProbeCase(
        ("rg",), (tool,), {"rg": None}, frozenset(), (("rg", Disposition.WAIT, "", False, None),)
    )


@pytest.mark.parametrize(
    ("tier", "case"),
    [
        pytest.param(tier, case, id=f"{case}-{tier}")
        for tier in ("system", "user", "ai")
        for case in "ABCDEFGHI"
    ],
)
def test_g_probe_cases_on_every_tier(tier: str, case: str):
    data = _probe_case(case, tier)
    rows = build_plan(
        data.selection, data.catalog, _state_of(data.states), MACOS, reinstall=data.reinstall
    )
    actual = tuple(
        (row.tool_id, row.disposition, row.reason, row.can_reinstall, row.requested_by)
        for row in rows
    )
    assert actual == data.expected


@pytest.mark.parametrize("tier", ["system", "user", "ai"])
def test_a_tier_mixing_current_and_missing_plans_only_the_missing_as_will_install(tier: str):
    rg, fd = _tool("rg", tier=tier), _tool("fd", tier=tier)
    catalog = [rg, fd]
    state_of = _state_of(
        {
            "rg": plan_state(rg),
            "fd": plan_state(fd, health=Health.MISSING, present=False),
        }
    )

    rows = build_plan(["rg", "fd"], catalog, state_of, MACOS, reinstall=frozenset())

    by_id = {r.tool_id: r for r in rows}
    assert (by_id["fd"].disposition, by_id["fd"].reason) == (Disposition.INSTALL, "not installed")
    assert by_id["rg"].disposition is Disposition.SKIP


def test_reinstall_requires_the_id_in_the_reinstall_set():
    rg = _tool("rg")
    catalog = [rg]
    state_of = _state_of({"rg": plan_state(rg)})

    current = build_plan(["rg"], catalog, state_of, MACOS, reinstall=frozenset())[0]
    requested = build_plan(["rg"], catalog, state_of, MACOS, reinstall=frozenset({"rg"}))[0]

    assert (current.disposition, current.reason, current.can_reinstall) == (
        Disposition.SKIP,
        "already current",
        True,
    )
    assert (requested.disposition, requested.reason, requested.can_reinstall) == (
        Disposition.REINSTALL,
        "reinstall requested; r again to undo",
        True,
    )


def test_reinstall_set_is_ignored_for_a_foreign_owned_row():
    rg = _tool("rg")
    dnf = _tool(
        "dnf-tool",
        methods=(Method(kind="dnf", params={"package": "dnf-tool"}),),
    )
    catalog = [rg, dnf]
    state_of = _state_of(
        {"rg": plan_state(rg, owner="brew"), "dnf-tool": plan_state(dnf, owner="dnf")}
    )

    rows = build_plan(
        ["rg", "dnf-tool"], catalog, state_of, MACOS, reinstall=frozenset({"rg", "dnf-tool"})
    )

    by_id = {r.tool_id: r for r in rows}
    assert (by_id["rg"].disposition, by_id["rg"].reason, by_id["rg"].can_reinstall) == (
        Disposition.SKIP,
        "managed by Homebrew",
        False,
    )
    assert (
        by_id["dnf-tool"].disposition,
        by_id["dnf-tool"].reason,
        by_id["dnf-tool"].can_reinstall,
    ) == (
        Disposition.SKIP,
        "managed by dnf",
        False,
    )


def test_reinstall_set_is_ignored_for_a_dragged_row():
    node = _tool("node")
    mmdc = _tool("mmdc", requires=("node",))
    catalog = [node, mmdc]
    state_of = _state_of(
        {"node": plan_state(node), "mmdc": plan_state(mmdc, health=Health.MISSING, present=False)}
    )

    rows = build_plan(["mmdc"], catalog, state_of, MACOS, reinstall=frozenset({"node"}))

    node_row = next(r for r in rows if r.tool_id == "node")
    assert (node_row.disposition, node_row.reason, node_row.can_reinstall) == (
        Disposition.SKIP,
        "already present",
        False,
    )


def test_installer_owned_current_without_a_receipt_is_still_reinstall_eligible():
    rg = _tool("rg")
    row = build_plan(["rg"], [rg], _state_of({"rg": plan_state(rg)}), MACOS, reinstall=frozenset())[
        0
    ]

    assert row.can_reinstall is True


def test_off_policy_current_row_names_both_owners(monkeypatch: pytest.MonkeyPatch):
    import installer.session as session

    rg = _tool(
        "rg",
        methods=(
            Method(kind="github_release", params={"repo": "x/y", "asset": "x"}),
            _BREW,
        ),
    )
    state_of = _state_of({"rg": plan_state(rg, owner="brew", off_policy=True)})

    row = build_plan(["rg"], [rg], state_of, MACOS, reinstall=frozenset())[0]
    assert row.reason == "managed by Homebrew; the catalog installs it via GitHub release"

    def unknown_declared_label(_tool: Tool, _platform: Platform) -> None:
        return None

    monkeypatch.setattr(session, "declared_manager_label", unknown_declared_label)
    row = build_plan(["rg"], [rg], state_of, MACOS, reinstall=frozenset())[0]
    assert row.reason == "managed by Homebrew"


def test_current_row_with_unknown_owner():
    rg = _tool("rg")
    row = build_plan(
        ["rg"],
        [rg],
        _state_of({"rg": plan_state(rg, owner="unknown")}),
        MACOS,
        reinstall=frozenset(),
    )[0]

    assert (row.disposition, row.reason, row.can_reinstall) == (
        Disposition.SKIP,
        "already current; owner unknown",
        False,
    )


def test_pending_state_is_a_wait_row():
    rg = _tool("rg")
    row = build_plan(["rg"], [rg], _state_of({}), MACOS, reinstall=frozenset())[0]

    assert (row.disposition, row.reason, row.health) == (Disposition.WAIT, "", None)


def test_wait_rows_count_as_checking_in_review_counts():
    rows = [
        PlanRow("rg", Disposition.INSTALL, "not installed"),
        PlanRow("fd", Disposition.WAIT, ""),
    ]

    assert review_counts(rows) == "1 will install, 1 checking…"
