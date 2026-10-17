import subprocess
import typing
from collections.abc import Callable

import pytest

from installer.model import Method, Tool
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
from tests.state_doubles import MACOS, plan_state

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
