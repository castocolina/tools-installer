"""The Schedules view under Textual Pilot: keys, cells, modals, refusals and the 78-cell budget.

Every context comes from `schedules.context_for` on a scratch HOME (the engine tests' `make_env`)
with recording `systemctl` fakes and fake `which`, `present` and `read_models`; no process is
started and no real unit directory is touched.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import DataTable

from installer import runlock, schedules
from installer.doctor import DoctorReport
from installer.guards import guard_status
from installer.model import Method, Tool
from installer.schedules import SCHEDULES
from installer.ui_common import GLOBAL_NAV, VIEWS, FooterBar
from installer.uninstall import SweepResult
from installer.wizard_app import (
    PolicyInputs,
    ScheduleInputs,
    SchedulesScreen,
    UnifiedApp,
    UninstallInputs,
)
from tests.screen_family import settle
from tests.test_schedules_engine import CLAUDE_BASENAME, Env, make_env

NOW = datetime(2026, 11, 13, 12, 5)
IDS = [schedule.id for schedule in SCHEDULES]
EVERYTHING = frozenset({"claude", "opencode", "pi", "cursor-agent", "copilot"})


def make_app(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: schedules.ScheduleContext | None | bool = True,
    now: datetime = NOW,
    initial_view: str = "system",
) -> UnifiedApp:
    monkeypatch.setenv("NO_COLOR", "1")
    ctx = env.ctx if context is True else context or None
    tool = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "rg"}),),
    )
    return UnifiedApp(
        [tool],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(env.home), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            ban_names=list, has_path_block=lambda: False, remove=lambda _d: SweepResult()
        ),
        policies=PolicyInputs(policies=[]),
        schedules=ScheduleInputs(context=ctx, present=env.ctx.present, now=lambda: now),
        initial_view=initial_view,
    )


def screen_of(app: UnifiedApp) -> SchedulesScreen:
    screen = app.view("schedules")
    assert isinstance(screen, SchedulesScreen)
    return screen


def cell(app: UnifiedApp, schedule_id: str, column: str) -> str:
    table = screen_of(app).query_one(DataTable[Any])
    return table.get_cell(schedule_id, column).plain


def unit_files(env: Env, basename: str = CLAUDE_BASENAME) -> list[Path]:
    return sorted(env.ctx.unit_dir.glob(f"{basename}.*")) if env.ctx.unit_dir.exists() else []


async def open_schedules(app: UnifiedApp, pilot: Any) -> SchedulesScreen:
    await pilot.press("7")
    await settle(app, pilot)
    assert isinstance(app.screen, SchedulesScreen)
    return app.screen


async def move_to(pilot: Any, screen: SchedulesScreen, schedule_id: str) -> None:
    screen.query_one(DataTable[Any]).move_cursor(row=IDS.index(schedule_id))
    await pilot.pause()


async def test_seven_opens_schedules_and_space_turns_claude_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        table = screen.query_one(DataTable[Any])
        assert [key.value for key in table.rows] == IDS
        assert cell(app, "update-claude", "state") == "○ [off]"

        await move_to(pilot, screen, "update-claude")
        await pilot.press("space")
        await settle(app, pilot)
        assert cell(app, "update-claude", "state") == "● [on]"
        assert [path.name for path in unit_files(env)] == [
            f"{CLAUDE_BASENAME}.service",
            f"{CLAUDE_BASENAME}.timer",
        ]
        assert screen.status.text == "Turned on claude update: next run at 18:00."

        await pilot.press("space")
        await settle(app, pilot)
        assert cell(app, "update-claude", "state") == "○ [off]"
        assert unit_files(env) == []
        assert screen.status.text == "Turned off claude update; its timer files are removed."


def test_views_row_and_footer() -> None:
    row = VIEWS[-1]
    assert (row.name, row.label, row.mode, row.glyph, row.style) == (
        "schedules",
        "Schedules",
        "LIVE",
        "*",
        "yellow",
    )
    assert row.palette == "Schedules - cleanup and tool updates on a timer"
    assert row.hint == "space turns a schedule on or off now; e sets when it runs"
    assert row.actions == "space toggle | e time | m model"
    assert GLOBAL_NAV == "1-7 views | ^p nav | esc back | q quit"
    assert FooterBar("schedules").render_text().plain == (
        "space toggle | e time | m model   │   1-7 views | ^p nav | esc back | q quit"
    )


async def test_toggle_takes_only_the_in_app_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    app = make_app(env, monkeypatch)
    holders: list[object] = []
    env.run.hooks["enable"] = lambda _cmd: holders.append(app.mutation_holder)
    held = runlock.try_acquire(env.ctx.lock_path, "installer")
    assert held is not None
    try:
        async with app.run_test(size=(80, 20)) as pilot:
            screen = await open_schedules(app, pilot)
            await move_to(pilot, screen, "update-claude")
            await pilot.press("space")
            await settle(app, pilot)
            assert cell(app, "update-claude", "state") == "● [on]"
            assert [str(holder) for holder in holders] == ["A schedule change"]
            assert app.mutation_holder is None
    finally:
        held.release()


async def test_an_inert_inputs_default_reads_every_row_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    app = make_app(env, monkeypatch, context=False)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert {cell(app, sid, "state") for sid in IDS} == {"– [n/a]"}
        await pilot.press("space")
        await settle(app, pilot)
        assert screen.status.text == (
            "Cannot turn on tmp cleanup: unavailable: no user timer manager."
        )
        assert not env.ctx.unit_dir.exists()
