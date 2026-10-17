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


def _tool(tool_id: str, *, tier: str = "user", requires: tuple[str, ...] = ()) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(_BREW,),
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
