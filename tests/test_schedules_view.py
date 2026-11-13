"""The Schedules view under Textual Pilot: keys, cells, modals, refusals and the 78-cell budget.

Every context comes from `schedules.context_for` on a scratch HOME (the engine tests' `make_env`)
with recording `systemctl` fakes and fake `which`, `present` and `read_models`; no process is
started and no real unit directory is touched.
"""

import fcntl
import os
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from rich.cells import cell_len
from rich.text import Text
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Label, OptionList, Select, Static

from installer import runlock, schedules, wizard_app
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.enums import DaemonState, Severity
from installer.guards import guard_status
from installer.model import Method, Tool
from installer.schedules import SCHEDULES
from installer.systemd_daemon import SCOPE_SYSTEM, CompetingUnit, TimerStateCache
from installer.ui_common import GLOBAL_NAV, VIEWS, FooterBar, WayfindingTab
from installer.uninstall import SweepResult
from installer.wizard_app import (
    CursorModelScreen,
    PolicyInputs,
    ScheduleInputs,
    SchedulesScreen,
    ScheduleTimeScreen,
    UnifiedApp,
    UninstallInputs,
)
from tests.screen_family import settle
from tests.test_schedules_engine import CLAUDE_BASENAME, Env, Install, make_env

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
    disk_pressure: Callable[..., DiskPressure] | None = None,
    competing: Callable[..., tuple[CompetingUnit, ...]] | None = None,
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
        schedules=ScheduleInputs(
            context=ctx,
            present=env.ctx.present,
            disk_pressure=disk_pressure,
            competing=competing,
            now=lambda: now,
        ),
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


# --- Task 2: cells, note, detail panel, refresh and the 80x20 budget ---------------------------


def with_which(env: Env, names: tuple[str, ...]) -> schedules.ScheduleContext:
    """The env's context with `which` finding only `names` (uv and systemctl stay)."""
    found = {"uv": str(env.uv), "systemctl": "/usr/bin/systemctl"}
    found.update({name: f"/usr/bin/{name}" for name in names})
    return replace(env.ctx, which=found.get)


def write_log(ctx: schedules.ScheduleContext, *lines: str) -> None:
    ctx.log_path.parent.mkdir(parents=True, exist_ok=True)
    with ctx.log_path.open("a") as handle:
        handle.writelines(f"{line}\n" for line in lines)


def hold_line(ctx: schedules.ScheduleContext, job: str) -> None:
    ctx.lock_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.lock_path.write_text(f"{job} {os.getpid()} 2026-11-13T12:00:00+00:00\n")


def table_of(app: UnifiedApp) -> DataTable[Any]:
    return screen_of(app).query_one(DataTable[Any])


async def test_cells_from_state_and_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    ctx = with_which(env, ("pnpm",))
    schedules.turn_on(ctx, "update-claude")
    schedules.turn_on(ctx, "tmp-cleanup")
    write_log(
        ctx,
        "2026-11-13T12:00:01 update-claude start",
        "2026-11-13T12:00:04 update-claude ok: up to date",
        "2026-11-13T12:00:01 update-opencode start",
        "2026-11-13T12:00:02 update-opencode skipped: pacman owns opencode",
        "2026-11-13T12:00:01 update-pi start",
        "2026-11-13T12:00:03 update-pi failed: boom",
        "2026-11-13T12:00:01 update-cursor-agent start",
        "2026-11-13T12:00:01 update-copilot start",
        "2026-11-13T12:00:00 tmp-cleanup start",
        "2026-11-13T12:00:00 tmp-cleanup ok: nothing to clean",
    )
    hold_line(ctx, "update-copilot")
    app = make_app(env, monkeypatch, context=ctx)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert [cell(app, sid, "last") for sid in IDS] == [
            "✓ 12:00",
            "never",
            "✓ 12:00",
            "– 12:00",
            "! 12:00",
            "! 12:00",
            "running",
        ]
        assert cell(app, "update-claude", "every") == "6h 00:00"
        assert cell(app, "update-claude", "next") == "18:00"
        assert cell(app, "update-pi", "next") == "–"
        assert cell(app, "tmp-cleanup", "every") == "10 min"
        assert cell(app, "tmp-cleanup", "next") == "12:10"
        assert {cell(app, sid, "script") for sid in IDS} == {"runner.py"}
        assert cell(app, "tmp-cleanup", "target") == "$TMPDIR"
        assert cell(app, "cache-cleanup", "target") == "uv pnpm"
        assert cell(app, "update-pi", "target") == "pi"

        await move_to(pilot, screen, "update-cursor-agent")
        assert "failed: interrupted" in screen.detail_text

        schedules.retime(ctx, "update-claude", 8, "01:30")
        screen.state_refreshed()
        assert cell(app, "update-claude", "every") == "8h 01:30"
        assert cell(app, "update-claude", "next") == "17:30"
        await move_to(pilot, screen, "update-claude")
        assert "times: 01:30, 09:30, 17:30 (local)" in screen.detail_text.splitlines()


async def test_a_log_that_is_not_utf8_still_renders_its_last_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    ctx = env.ctx
    ctx.log_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.log_path.write_bytes(
        b"\xff\xfe junk\n2026-11-13T12:00:04 update-claude ok: up to date\n\xff\n"
    )
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_schedules(app, pilot)
        assert cell(app, "update-claude", "last") == "\u2713 12:00"
        await move_to(pilot, screen, "update-claude")
        assert any(line.startswith("last: ") for line in screen.detail_text.splitlines())
        assert screen.status.text == ""


async def test_an_unreadable_log_blanks_the_last_cells_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    env.ctx.log_path.mkdir(parents=True)  # a directory where the log should be
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_schedules(app, pilot)
        assert {cell(app, sid, "last") for sid in IDS} == {"\u2026"}
        await move_to(pilot, screen, "update-claude")
        assert "last: could not be read" in screen.detail_text
        assert screen.status.text.startswith("Could not read the schedule log: ")
        assert screen.status.severity == Severity.ERROR


async def test_the_linux_tmp_detail_discloses_the_login_session_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    linux = (await row_details(tmp_path / "linux", monkeypatch))["tmp-cleanup"]
    text = "\n".join(linux)
    assert "The timer runs while you are logged in." in text
    assert "loginctl enable-linger $USER" in text
    assert "does not run that" in text
    assert "system-wide setting for the whole account" in text
    mac = (await row_details(tmp_path / "mac", monkeypatch, os_key="macos"))["tmp-cleanup"]
    assert "enable-linger" not in "\n".join(mac)


async def test_tmp_next_is_a_dash_before_its_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.turn_on(env.ctx, "tmp-cleanup")
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        await open_schedules(app, pilot)
        assert cell(app, "tmp-cleanup", "state") == "● [on]"
        assert cell(app, "tmp-cleanup", "next") == "–"
        assert cell(app, "cache-cleanup", "target") == "uv"
        assert cell(app, "update-claude", "next") == "–"


async def test_cache_target_reads_none_without_a_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    ctx = replace(env.ctx, which={"systemctl": "/usr/bin/systemctl"}.get)
    app = make_app(env, monkeypatch, context=ctx)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert cell(app, "cache-cleanup", "target") == "none"
        await move_to(pilot, screen, "cache-cleanup")
        assert "prunes: nothing — no uv, pnpm, brew or npm found" in screen.detail_text


async def test_unavailable_rows_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING - {"claude"})
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-claude")
        assert cell(app, "update-claude", "state") == "– [n/a]"
        assert screen.detail_text.splitlines()[0] == "unavailable: claude not installed"
        await pilot.press("space")
        await settle(app, pilot)
        assert screen.status.text == (
            "Cannot turn on claude update: unavailable: claude not installed."
        )
        assert not env.ctx.unit_dir.exists()
        assert not env.ctx.state_path.exists()


async def test_no_manager_makes_every_row_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING, systemctl=False)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert {cell(app, sid, "state") for sid in IDS} == {"– [n/a]"}
        assert screen.note_text == (
            "unavailable: no user timer manager — nothing is scheduled on this machine."
        )
        for key in ("space", "e", "m"):
            await pilot.press(key)
            await settle(app, pilot)
        assert not env.ctx.unit_dir.exists()
        assert not env.ctx.state_path.exists()
        assert env.run.calls == []


async def test_rows_read_checking_until_the_manager_probe_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    gate = threading.Event()

    def gated(cmd: list[str]) -> str:
        assert gate.wait(timeout=10)
        return env.output(cmd)

    app = make_app(env, monkeypatch, context=replace(env.ctx, read_output=gated))
    try:
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("7")
            await pilot.pause()
            screen = screen_of(app)
            assert screen.note_text == "Checking for a user timer manager…"
            assert {cell(app, sid, "state") for sid in IDS} == {"…"}
            await pilot.press("space")
            assert screen.status.text == (
                "Still checking for a user timer manager; try again in a moment."
            )
            gate.set()
            await settle(app, pilot)
            assert cell(app, "tmp-cleanup", "state") == "○ [off]"
    finally:
        gate.set()


@pytest.mark.parametrize("os_key", ["debian", "arch", "fedora"])
async def test_platform_note_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, os_key: str
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key=os_key, present=EVERYTHING)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert screen.note_text == (
            "Timers run while you are logged in; a missed run catches up once at login."
        )


async def test_platform_note_macos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="macos", present=EVERYTHING)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert screen.note_text == (
            "Missed during sleep: runs once at wake. Missed while shut down: skipped."
        )
        assert cell(app, "tmp-cleanup", "every") == f"24h {SCHEDULES[0].default_start}"


async def test_drift_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.turn_on(env.ctx, "update-claude")
    timer = env.ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"
    timer.write_text(timer.read_text() + "# edited by hand\n")
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-claude")
        assert cell(app, "update-claude", "state") == "! [drift]"
        assert screen.detail_text.splitlines()[0] == (
            "Drift: its timer files are missing or changed. space writes them again."
        )
        await pilot.press("space")
        await settle(app, pilot)
        assert cell(app, "update-claude", "state") == "● [on]"
        assert screen.status.text == "Rewrote the claude update timer files: next run at 18:00."
        assert "edited by hand" not in timer.read_text()


async def test_detail_panel_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    ctx = with_which(env, ())
    schedules.turn_on(ctx, "update-claude")
    write_log(ctx, "2026-11-13T12:00:04 update-claude ok: up to date")
    pressure = DiskPressure(
        home_free_percent=50.0,
        tmp_used_percent=42.0,
        daemon=DaemonState.ACTIVE,
        tmp_threshold=True,
    )
    units = (CompetingUnit("old-prune.timer", SCOPE_SYSTEM, "enabled"),)

    def probe_pressure(**_kw: object) -> DiskPressure:
        return pressure

    def probe_competing(**_kw: object) -> tuple[CompetingUnit, ...]:
        return units

    app = make_app(
        env,
        monkeypatch,
        context=ctx,
        disk_pressure=probe_pressure,
        competing=probe_competing,
    )
    stamp = datetime(2026, 11, 13, 12, 0, 4).astimezone().isoformat(timespec="seconds")
    runner = "~/.local/share/tools-installer/schedules/runner.py"
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-claude")
        assert screen.detail_text.splitlines() == [
            "claude update is on — runs claude's update the way the catalog's u does.",
            f"last: {stamp} ok: up to date",
            "times: 00:00, 06:00, 12:00, 18:00 (local)",
            f"runs: uv run --no-project --script {runner} update claude",
        ]
        await move_to(pilot, screen, "update-pi")
        assert screen.detail_text.splitlines()[:2] == [
            "pi update is off — runs pi's update the way the catalog's u does.",
            "last: never",
        ]
        await move_to(pilot, screen, "cache-cleanup")
        assert screen.detail_text.splitlines()[3] == "prunes: uv cache prune"
        await move_to(pilot, screen, "tmp-cleanup")
        lines = screen.detail_text.splitlines()
        assert lines[2] == "times: every 10 min, first run 2 min after login"
        assert "The timer runs while you are logged in." in screen.detail_text
        assert "Current temp-directory usage: 42.0%" in lines
        assert any(line.startswith("Also installed system-wide: old-prune.timer") for line in lines)
        assert lines[-1].startswith("runs: uv run --no-project --script")


@pytest.mark.parametrize(
    ("shim", "line"),
    [
        (None, None),
        (
            "not-listed",
            "! gpt-5.6-sol-xhigh is not in your model list; the shim passes arguments through.",
        ),
        (
            "unverified",
            "model unverified: could not read the cursor-agent model list; "
            "using gpt-5.6-sol-xhigh.",
        ),
        (
            "kept-foreign",
            "your own ~/.local/bin/cursor-agent is kept: it has no installer sentinel.",
        ),
    ],
)
async def test_cursor_detail_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shim: str | None, line: str | None
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.update_state(env.ctx.state_path, lambda s: replace(s, cursor_shim=shim))
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-cursor-agent")
        lines = screen.detail_text.splitlines()
        assert lines[3] == "model: gpt-5.6-sol-xhigh — press m to change"
        assert lines[4 : len(lines) - 1] == ([line] if line else [])


async def test_refresh_never_probes_the_flock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    write_log(env.ctx, "2026-11-13T12:00:01 update-claude start")
    hold_line(env.ctx, "update-claude")
    app = make_app(env, monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the view probed a flock")

    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        # The flock the run lock and the state file use is this one module function.
        monkeypatch.setattr(fcntl, "flock", boom)
        await move_to(pilot, screen, "update-pi")
        await pilot.press("down")
        screen.tick()
        screen.state_refreshed()
        assert cell(app, "update-claude", "last") == "running"


async def test_a_user_action_clears_the_damage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(
        tmp_path,
        monkeypatch,
        os_key="fedora",
        present=EVERYTHING,
        fail_on=frozenset({("enable", 1)}),
    )
    env.ctx.state_path.parent.mkdir(parents=True)
    env.ctx.state_path.write_text("{not json")
    damaged = schedules.damaged_path(env.ctx.state_path)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert screen.status.text.startswith("Could not read schedules.json (")
        assert damaged.exists()
        await move_to(pilot, screen, "update-claude")
        await pilot.press("space")  # the first enable fails
        await settle(app, pilot)
        assert screen.status.text.startswith("Could not turn on claude update: ")
        assert damaged.exists()
        await pilot.press("space")
        await settle(app, pilot)
        assert screen.status.text == "Turned on claude update: next run at 18:00."
        assert not damaged.exists()


async def test_refresh_every_30_seconds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.turn_on(env.ctx, "update-claude")
    monkeypatch.setitem(vars(wizard_app), "_REFRESH_SECONDS", 0.05)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        assert cell(app, "update-claude", "last") == "never"
        write_log(env.ctx, "2026-11-13T12:00:04 update-claude ok: up to date")
        for _ in range(100):
            await pilot.pause(0.05)
            if cell(app, "update-claude", "last") == "✓ 12:00":
                break
        assert cell(app, "update-claude", "last") == "✓ 12:00"

        await pilot.press("1")
        await pilot.pause()
        write_log(env.ctx, "2026-11-13T12:01:00 update-claude failed: boom")
        await pilot.pause(0.4)
        assert cell(app, "update-claude", "last") == "✓ 12:00"  # no tick off the view
        screen.tick()
        assert cell(app, "update-claude", "last") == "✓ 12:00"
        await pilot.press("7")
        await settle(app, pilot)
        assert cell(app, "update-claude", "last") == "! 12:01"


class Trap:
    """A process seam that fails the test once armed."""

    def __init__(self, inner: Callable[[list[str]], Any]) -> None:
        self.inner = inner
        self.armed = False
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> Any:
        if self.armed:
            self.calls.append(cmd)
            raise AssertionError(f"a render spawned {cmd}")
        return self.inner(cmd)


async def test_render_never_spawns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.turn_on(env.ctx, "update-claude")
    run, read_output = Trap(env.ctx.run), Trap(env.ctx.read_output)
    ctx = replace(env.ctx, run=run, read_output=read_output)
    app = make_app(env, monkeypatch, context=ctx)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        run.armed = read_output.armed = True
        for _ in IDS:
            await pilot.press("down")
        screen.tick()
        screen.state_refreshed()
        await pilot.press("1")
        await pilot.pause()
        screen.tick()
    assert run.calls == [] and read_output.calls == []


async def test_encoding_and_width(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    odd = tmp_path / "d é [red] z" / "tools-installer" / "schedules"
    ctx = replace(env.ctx, data_dir=odd)
    write_log(
        ctx,
        "2026-11-13T12:00:01 update-claude start",
        "2026-11-13T12:00:04 update-claude failed: [red]boom[/red] \x1b[31mx",
    )
    app = make_app(env, monkeypatch, context=ctx)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-claude")
        detail = screen.query_one("#schedule-detail", Static)
        content = detail.content
        assert isinstance(content, Text)
        assert str(odd / "runner.py") in content.plain
        assert "[red]boom[/red]" in content.plain
        assert "\x1b" not in content.plain
        table = table_of(app)
        widths = {key: width for key, _label, width in vars(wizard_app)["_SCHEDULE_COLUMNS"]}
        for schedule in SCHEDULES:
            for column, width in widths.items():
                assert cell_len(table.get_cell(schedule.id, column).plain) <= width
        assert sum(col.get_render_width(table) for col in table.columns.values()) == 78

        screen.status.set("one\ntwo\nthree", "warn")
        await pilot.pause()
        assert table.region.height == 8
        assert table.max_scroll_y == 0
        assert detail.region.height == 4


@pytest.mark.parametrize(
    "view", ["system", "user", "ai", "doctor", "uninstall", "policies", "schedules"]
)
async def test_tab_bar_fits_80_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, view: str
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        await app.show_view(view)
        await settle(app, pilot)
        tabs = list(app.screen.query(WayfindingTab))
        assert len(tabs) == len(VIEWS)
        assert tabs[0].region.x == 1
        for left, right in zip(tabs, tabs[1:], strict=False):
            assert right.region.x == left.region.right + 1
        assert tabs[-1].region.right == 79


# --- Task 3: the time modal and the cursor-agent model modal -----------------------------------


def timer_of(env: Env) -> Path:
    return env.ctx.unit_dir / f"{CLAUDE_BASENAME}.timer"


async def open_time_modal(
    app: UnifiedApp, pilot: Any, screen: SchedulesScreen
) -> ScheduleTimeScreen:
    await move_to(pilot, screen, "update-claude")
    await pilot.press("e")
    await pilot.pause()
    assert isinstance(app.screen, ScheduleTimeScreen)
    return app.screen


async def type_and_submit(pilot: Any, modal: ScheduleTimeScreen, start: str) -> None:
    field = modal.query_one(Input)
    field.value = start
    field.focus()
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


def blocker(gate: threading.Event) -> Callable[[], None]:
    """A `read_models` hook that waits for the test to open the gate."""

    def wait() -> None:
        gate.wait(timeout=10)

    return wait


def label_text(modal: Any, selector: str) -> str:
    return str(modal.query_one(selector, Label).content)


async def test_time_modal_saves_and_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.turn_on(env.ctx, "update-claude")
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        modal = await open_time_modal(app, pilot, screen)
        assert label_text(modal, "#time-title") == "When claude update runs"
        assert modal.query_one(Select[int]).value == 6
        assert modal.query_one(Input).value == "00:00"
        assert label_text(modal, "#time-preview") == "Runs at 00:00, 06:00, 12:00, 18:00"

        before = timer_of(env).read_bytes()
        for bad in ("24:00", "7:5", "ab:cd", ""):
            await type_and_submit(pilot, modal, bad)
            assert app.screen is modal
            assert label_text(modal, "#time-error") == schedules.START_MESSAGE
            assert timer_of(env).read_bytes() == before

        modal.query_one(Select[int]).value = 1
        modal.query_one(Input).value = "00:30"
        await pilot.pause()
        assert label_text(modal, "#time-preview") == (
            "Runs at 00:30, 01:30, 02:30 … 23:30 (24 times a day)"
        )
        modal.query_one(Select[int]).value = 8
        await type_and_submit(pilot, modal, "01:30")
        await settle(app, pilot)
        assert app.screen is screen
        assert (
            screen.status.text == "claude update now runs every 8 h from 01:30; next run at 17:30."
        )
        assert cell(app, "update-claude", "every") == "8h 01:30"
        assert "OnCalendar=*-*-* 01,09,17:30:00" in timer_of(env).read_text()

        # Unchanged values: nothing is rewritten.
        calls = len(env.run.calls)
        modal = await open_time_modal(app, pilot, screen)
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen
        modal = await open_time_modal(app, pilot, screen)
        await type_and_submit(pilot, modal, "01:30")
        await settle(app, pilot)
        assert screen.status.text == "No change: claude update already runs every 8 h from 01:30."
        assert len(env.run.calls) == calls


async def test_time_modal_on_an_off_row_only_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        modal = await open_time_modal(app, pilot, screen)
        modal.query_one(Select[int]).value = 8
        await type_and_submit(pilot, modal, "01:30")
        await settle(app, pilot)
        assert screen.status.text == (
            "Saved: claude update will run every 8 h from 01:30 once it is on."
        )
        assert unit_files(env) == []
        assert cell(app, "update-claude", "every") == "8h 01:30"
        assert cell(app, "update-claude", "state") == "○ [off]"


_UPDATE_REFUSAL = "An update is running; wait for it to finish. Navigation still works."
_REMOVAL_REFUSAL = "A removal is running; wait for it to finish. Navigation still works."


async def test_e_is_refused_before_the_modal_and_again_at_the_pick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-17 / CR-02: a running mutation refuses `e` at once, and a mutation that starts while
    the modal is open refuses at the pick; the timer is not rewritten either way."""
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    schedules.turn_on(env.ctx, "update-claude")
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-claude")
        before = timer_of(env).read_bytes()

        app.begin_mutation(wizard_app.MutationHolder.UPDATE)
        await pilot.press("e")
        await pilot.pause()
        assert app.screen is screen
        assert (screen.status.text, screen.status.severity) == (_UPDATE_REFUSAL, Severity.WARN)
        app.end_mutation()
        screen.status.clear()

        modal = await open_time_modal(app, pilot, screen)
        app.begin_mutation(wizard_app.MutationHolder.REMOVAL)
        modal.query_one(Select[int]).value = 8
        await type_and_submit(pilot, modal, "01:30")
        assert app.screen is screen
        assert (screen.status.text, screen.status.severity) == (_REMOVAL_REFUSAL, Severity.WARN)
        assert timer_of(env).read_bytes() == before
        app.end_mutation()


async def test_tmp_cleanup_time_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await pilot.press("e")
        await pilot.pause()
        assert app.screen is screen
        assert screen.status.text == (
            "Cannot edit tmp cleanup: on Linux it runs every 10 min, a fixed cadence."
        )

    mac = make_env(tmp_path / "mac", monkeypatch, os_key="macos", present=EVERYTHING)
    schedules.turn_on(mac.ctx, "tmp-cleanup")
    app = make_app(mac, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await pilot.press("e")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ScheduleTimeScreen)
        assert list(modal.query(Select[int])) == []
        assert "Daily at (HH:MM, local time)" in [
            str(label.content) for label in modal.query(Label)
        ]
        await type_and_submit(pilot, modal, "02:15")
        await settle(app, pilot)
        assert screen.status.text == "tmp cleanup now runs daily at 02:15; next run at 02:15."


async def open_model_modal(
    app: UnifiedApp, pilot: Any, screen: SchedulesScreen
) -> CursorModelScreen:
    await move_to(pilot, screen, "update-cursor-agent")
    await pilot.press("m")
    await pilot.pause()
    assert isinstance(app.screen, CursorModelScreen)
    return app.screen


def option_texts(modal: CursorModelScreen) -> list[str]:
    options = modal.query_one(OptionList)
    return [options.get_option_at_index(i).prompt.__str__() for i in range(options.option_count)]


async def test_model_modal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    Install(env.home)
    schedules.turn_on(env.ctx, "update-cursor-agent")
    gate = threading.Event()
    env.models.on_call = blocker(gate)
    app = make_app(env, monkeypatch)
    try:
        async with app.run_test(size=(80, 20)) as pilot:
            screen = await open_schedules(app, pilot)
            modal = await open_model_modal(app, pilot, screen)
            assert label_text(modal, "#model-status") == "Reading your cursor-agent models…"
            gate.set()
            await settle(app, pilot)
            assert option_texts(modal) == ["● gpt-5.6-sol-xhigh", "  gpt-5.5"]

            field = modal.query_one(Input)
            field.value = "5.5"
            await pilot.pause()
            assert option_texts(modal) == ["  gpt-5.5"]

            for bad, message in (
                ("bad id!", schedules.MODEL_CHARSET_MESSAGE),
                ("--x", schedules.MODEL_SHAPE_MESSAGE),
            ):
                field.value = bad
                field.focus()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                assert app.screen is modal
                assert label_text(modal, "#model-error") == message

            field.value = "5.5"
            await pilot.pause()
            options = modal.query_one(OptionList)
            options.focus()
            options.highlighted = 0
            await pilot.pause()
            await pilot.press("enter")
            await settle(app, pilot)
            assert app.screen is screen
            assert screen.status.text == "cursor-agent now defaults to gpt-5.5."
            assert screen.status.severity == "ok"

            await move_to(pilot, screen, "update-claude")
            await pilot.press("m")
            assert screen.status.text == (
                "m sets the cursor-agent model; move to the cursor-agent row first."
            )
    finally:
        gate.set()


async def test_model_modal_unlisted_and_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    Install(env.home)
    schedules.turn_on(env.ctx, "update-cursor-agent")
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        modal = await open_model_modal(app, pilot, screen)
        await settle(app, pilot)
        field = modal.query_one(Input)
        field.value = "gpt-9-unlisted"
        field.focus()
        await pilot.pause()
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.status.text == (
            "cursor-agent: gpt-9-unlisted is not in your model list; the shim passes through."
        )
        assert screen.status.severity == "warn"

        env.models.answer = None
        modal = await open_model_modal(app, pilot, screen)
        await settle(app, pilot)
        assert label_text(modal, "#model-status").startswith("Could not read the model list: ")
        assert label_text(modal, "#model-status").endswith(". Type a model id.")
        field = modal.query_one(Input)
        field.value = "gpt-5.5"
        field.focus()
        await pilot.pause()
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.status.text == (
            "cursor-agent now defaults to gpt-5.5; model unverified (list unreadable)."
        )


async def test_model_saved_while_off_and_a_list_after_esc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    gate = threading.Event()
    env.models.on_call = blocker(gate)
    app = make_app(env, monkeypatch)
    try:
        async with app.run_test(size=(80, 20)) as pilot:
            screen = await open_schedules(app, pilot)
            modal = await open_model_modal(app, pilot, screen)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen
            gate.set()
            await settle(app, pilot)
            assert modal.listed == ()  # the late list was dropped

            gate.set()
            modal = await open_model_modal(app, pilot, screen)
            await settle(app, pilot)
            field = modal.query_one(Input)
            field.value = "gpt-5.5"
            field.focus()
            await pilot.pause()
            await pilot.press("enter")
            await settle(app, pilot)
            assert screen.status.text == (
                "Saved: cursor-agent will default to gpt-5.5 once its schedule is on."
            )
    finally:
        gate.set()


@pytest.mark.parametrize(
    ("scenario", "line", "severity"),
    [
        (
            "plain",
            "Turned on cursor-agent update: next run at 18:00; model gpt-5.6-sol-xhigh.",
            "ok",
        ),
        (
            "foreign",
            "Turned on cursor-agent update; your own cursor-agent file was kept.",
            "warn",
        ),
        (
            "unlisted",
            "Turned on cursor-agent update; gpt-5.6-sol-xhigh is not listed, "
            "so the shim passes through.",
            "warn",
        ),
    ],
)
async def test_cursor_toggle_status_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, line: str, severity: str
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    Install(env.home, foreign=scenario == "foreign")
    if scenario == "unlisted":
        env.models.answer = ("gpt-5.5",)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-cursor-agent")
        await pilot.press("space")
        await settle(app, pilot)
        assert screen.status.text == line
        assert screen.status.severity == severity
        if scenario == "foreign":
            assert "your own ~/.local/bin/cursor-agent is kept" in screen.detail_text
        if scenario == "plain":
            await pilot.press("space")
            await settle(app, pilot)
            assert screen.status.text == (
                "Turned off cursor-agent update; cursor-agent is a plain link again."
            )


async def test_apply_failure_repaints_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(
        tmp_path,
        monkeypatch,
        os_key="fedora",
        present=EVERYTHING,
        fail_on=frozenset({("enable", 1)}),
    )
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        await move_to(pilot, screen, "update-claude")
        await pilot.press("space")
        await settle(app, pilot)
        assert screen.status.text.startswith("Could not turn on claude update: ")
        assert screen.status.severity == "error"
        assert cell(app, "update-claude", "state") == "○ [off]"


async def test_modals_fit_80x20(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    Install(env.home)
    env.models.answer = tuple(f"model-{n}" for n in range(40))
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = await open_schedules(app, pilot)
        modal = await open_time_modal(app, pilot, screen)
        box = modal.query_one(Vertical)
        assert box.region.height <= 14
        assert box.max_scroll_y == 0
        for child in box.children:
            assert box.region.contains_region(child.region), child
        await pilot.press("escape")
        await pilot.pause()

        model_modal = await open_model_modal(app, pilot, screen)
        await settle(app, pilot)
        box = model_modal.query_one(Vertical)
        assert box.region.height == 16
        assert model_modal.query_one(OptionList).max_scroll_y > 0
        for child in box.children:
            if child.display:  # the loading label is gone once the list lands
                assert box.region.contains_region(child.region), child


# --- The tmp row's live lines: temp usage and the system-wide competitor (D-21) ----------------


def pressure(*, home_free: float | None = 50.0, tmp_used: float | None = 10.0) -> DiskPressure:
    return DiskPressure(
        home_free_percent=home_free,
        tmp_used_percent=tmp_used,
        daemon=DaemonState.INACTIVE,
        tmp_threshold=True,
    )


def usage_probe(
    read: DiskPressure | Callable[[], DiskPressure], calls: list[bool] | None = None
) -> Callable[..., DiskPressure]:
    """A disk probe with the production call shape; `calls` records every `blocking` keyword."""

    def probe(*, blocking: bool = True) -> DiskPressure:
        if calls is not None:
            calls.append(blocking)
        return read() if callable(read) else read

    return probe


async def row_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    os_key: str = "fedora",
    disk_pressure: Callable[..., DiskPressure] | None = None,
    competing: Callable[..., tuple[CompetingUnit, ...]] | None = None,
) -> dict[str, list[str]]:
    """Every row's detail lines, driven through the row-highlight render path."""
    env = make_env(tmp_path, monkeypatch, os_key=os_key, present=EVERYTHING)
    app = make_app(env, monkeypatch, disk_pressure=disk_pressure, competing=competing)
    details: dict[str, list[str]] = {}
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_schedules(app, pilot)
        for schedule_id in IDS:
            await move_to(pilot, screen, schedule_id)
            details[schedule_id] = screen.detail_text.splitlines()
    return details


@pytest.mark.parametrize("os_key", ["fedora", "macos"])
async def test_tmp_detail_states_the_temp_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, os_key: str
) -> None:
    details = await row_details(
        tmp_path, monkeypatch, os_key=os_key, disk_pressure=usage_probe(pressure(tmp_used=42.25))
    )
    assert "Current temp-directory usage: 42.2%" in details["tmp-cleanup"]
    others = [lines for key, lines in details.items() if key != "tmp-cleanup"]
    assert all("temp-directory" not in line for lines in others for line in lines)
    assert all("home filesystem" not in line for lines in others for line in lines)


async def test_the_temp_usage_line_is_absent_without_a_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    details = await row_details(tmp_path, monkeypatch)
    assert not [line for line in details["tmp-cleanup"] if "usage" in line or "free space" in line]


@pytest.mark.parametrize("error", [OSError("statvfs failed"), ValueError("bad reading")])
async def test_the_temp_usage_line_survives_a_failing_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def broken() -> DiskPressure:
        raise error

    details = await row_details(tmp_path, monkeypatch, disk_pressure=usage_probe(broken))
    assert "The timer runs while you are logged in." in "\n".join(details["tmp-cleanup"])
    assert not [line for line in details["tmp-cleanup"] if "temp-directory" in line]


async def test_the_macos_row_reports_tmpdir_usage_never_the_home_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deliberately different numbers, so substituting the home filesystem's free space for the
    # temp usage cannot pass.
    probe = usage_probe(pressure(home_free=81.0, tmp_used=12.5))
    text = "\n".join(
        (await row_details(tmp_path, monkeypatch, os_key="macos", disk_pressure=probe))[
            "tmp-cleanup"
        ]
    )
    assert "Current temp-directory usage: 12.5%" in text
    assert "81.0" not in text
    assert "19.0" not in text


async def test_an_unreadable_temp_mount_falls_back_to_the_labelled_home_free_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = usage_probe(pressure(home_free=33.3, tmp_used=None))
    lines = (await row_details(tmp_path, monkeypatch, disk_pressure=probe))["tmp-cleanup"]
    assert "Current home filesystem free space: 33.3%" in lines
    assert not [line for line in lines if "temp-directory" in line]


async def test_no_usage_line_when_neither_mount_was_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = usage_probe(pressure(home_free=None, tmp_used=None))
    lines = (await row_details(tmp_path, monkeypatch, disk_pressure=probe))["tmp-cleanup"]
    assert not [line for line in lines if "temp-directory" in line or "home filesystem" in line]


async def test_row_highlight_only_ever_asks_for_the_non_blocking_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []
    await row_details(tmp_path, monkeypatch, disk_pressure=usage_probe(pressure(), calls))
    assert calls
    assert not any(calls)


def cache_backed_probe(cache: TimerStateCache) -> Callable[..., DiskPressure]:
    """The production verb split over a real TimerStateCache: read() when blocking, peek()
    otherwise, a cold peek answering UNAVAILABLE."""

    def probe(*, blocking: bool = True) -> DiskPressure:
        state = cache.read() if blocking else cache.peek()
        return DiskPressure(
            home_free_percent=50.0,
            tmp_used_percent=42.0,
            daemon=DaemonState.UNAVAILABLE if state is None else state,
            tmp_threshold=True,
        )

    return probe


async def test_row_highlight_issues_zero_systemd_queries_in_every_cache_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queries: list[str] = []
    now = [0.0]

    def is_active() -> DaemonState:
        queries.append("is-active")
        return DaemonState.INACTIVE

    cache = TimerStateCache(is_active, ttl=10.0, clock=lambda: now[0])
    cache.read()
    assert queries == ["is-active"]
    queries.clear()
    probe = cache_backed_probe(cache)
    for step, prepare in enumerate(
        (lambda: None, lambda: now.__setitem__(0, 10_000.0), cache.invalidate)
    ):
        prepare()  # warm memo, then a clock far past the TTL, then a memo just marked stale
        details = await row_details(tmp_path / str(step), monkeypatch, disk_pressure=probe)
        assert "Current temp-directory usage: 42.0%" in details["tmp-cleanup"]
    assert queries == []


async def test_a_truly_cold_cache_still_renders_the_temp_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queries: list[str] = []

    def is_active() -> DaemonState:
        queries.append("is-active")
        return DaemonState.INACTIVE

    details = await row_details(
        tmp_path, monkeypatch, disk_pressure=cache_backed_probe(TimerStateCache(is_active))
    )
    assert "Current temp-directory usage: 42.0%" in details["tmp-cleanup"]
    assert queries == []


async def test_the_tmp_row_names_a_system_scope_competitor_after_its_warm_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-10: the Schedules view warms the competitor memo off the event loop, then repaints
    the detail from the non-blocking peek."""
    warmed = [False]
    blocking_on_loop: list[bool] = []

    def competing(*, blocking: bool = True) -> tuple[CompetingUnit, ...]:
        units = (CompetingUnit("cleanup-bun-tmp-cache.timer", SCOPE_SYSTEM, "enabled"),)
        if blocking:
            blocking_on_loop.append(threading.current_thread() is threading.main_thread())
            warmed[0] = True
            return units
        return units if warmed[0] else ()

    details = await row_details(tmp_path, monkeypatch, competing=competing)
    assert any(
        line.startswith("Also installed system-wide: cleanup-bun-tmp-cache.timer")
        and "root-owned" in line
        for line in details["tmp-cleanup"]
    )
    assert blocking_on_loop == [False]


async def test_the_manager_probe_runs_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    threads: list[threading.Thread] = []

    def read_output(cmd: list[str]) -> str:
        threads.append(threading.current_thread())
        return env.output(cmd)

    app = make_app(env, monkeypatch, context=replace(env.ctx, read_output=read_output))
    async with app.run_test(size=(80, 20)) as pilot:
        await open_schedules(app, pilot)
        assert threads
        assert threading.main_thread() not in threads
        assert cell(app, "update-claude", "state") == "○ [off]"


async def test_a_log_error_keeps_its_line_and_never_overwrites_another_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR-03: an unreadable log shows its error over an empty status or its own earlier error,
    never over another writer's result."""
    env = make_env(tmp_path, monkeypatch, os_key="fedora", present=EVERYTHING)
    env.ctx.log_path.mkdir(parents=True)
    app = make_app(env, monkeypatch)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_schedules(app, pilot)
        assert screen.status.text.startswith("Could not read the schedule log:")
        screen.state_refreshed()  # the error's own re-render keeps it
        assert screen.status.text.startswith("Could not read the schedule log:")
        screen.status.set("Link mode saved: split", "ok")
        screen.state_refreshed()
        assert screen.status.text == "Link mode saved: split"
