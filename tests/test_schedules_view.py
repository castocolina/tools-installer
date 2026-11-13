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
from textual.widgets import DataTable, Static

from installer import runlock, schedules, wizard_app
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.enums import DaemonState
from installer.guards import guard_status
from installer.model import Method, Tool
from installer.schedules import SCHEDULES
from installer.systemd_daemon import SCOPE_SYSTEM, CompetingUnit
from installer.ui_common import GLOBAL_NAV, VIEWS, FooterBar, WayfindingTab
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
