import subprocess
import typing
from collections.abc import Callable

import pytest

from installer.model import Method, Tool
from installer.platform import Platform
from installer.session import (
    RESULT_WORDS,
    WORDS,
    Disposition,
    PlanRow,
    Result,
    build_plan,
    review_counts,
)
from installer.version_status import Health, ToolState
from tests.state_doubles import MACOS, pass_state, plan_state

_BREW = Method(kind="brew", params={"formula": "x"})


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


def _state_of(states: dict[str, ToolState]) -> Callable[[str], ToolState | None]:
    return states.get


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
