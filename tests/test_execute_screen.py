"""ExecuteScreen behaviour, plus characterisation of the worker-to-modal primitive.

The first tests pin MECHANISM=A (plan 13-01). The rest drive the in-app install
screen: a fake `install` that emits through the injected runner, never a real
package manager or shell rc file.
"""

import shutil
import sys
import threading
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, ClassVar
from weakref import WeakKeyDictionary

import pytest
from rich.cells import cell_len
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.pilot import Pilot
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Label, ListItem, ListView, OptionList, Static

import installer.execute_screen
from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import InstallStatus, Severity
from installer.execute_screen import (
    # The indicator's exact copy, imported rather than hand-written: a test
    # that constructs the message production posts must not be able to drift
    # from it silently while looser `"waiting for output" in log` substring
    # assertions elsewhere keep passing.
    _WAITING_OUTPUT,  # pyright: ignore[reportPrivateUsage]
    SILENCE_SECONDS,
    ChecksumMismatchScreen,
    ExecuteInputs,
    ExecuteScreen,
    InstallLogLine,
    InstallRunFinished,
    RowFinished,
    sanitize_log_line,
)
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool
from installer.ownership import ManagerInventory, ManagerOwnership, OwnershipCandidate
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, StreamingRunner
from installer.session import (
    Disposition,
    PlanRow,
    Result,
    RowOutcome,
    RunContext,
    SensitiveInstall,
    ran_anything,
)
from installer.uninstall import SweepResult
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import Health, ToolState, VersionRefreshService, VersionStatus
from installer.versions import TagResolver
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs
from tests.state_doubles import (
    FrozenStateService,
    HeldRefreshService,
    frozen_service,
    held_service,
    offline_service,
    pass_state,
    plan_state,
    presence_service,
    skill_pack_tool,
)


class _AskModal(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    _AskModal { align: center middle; }
    _AskModal > ListView { width: 24; height: 8; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(
            ListItem(Label("skip"), id="opt-skip"),
            ListItem(Label("replace"), id="opt-replace"),
            ListItem(Label("abort"), id="opt-abort"),
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None:
            return
        self.dismiss(item_id.removeprefix("opt-"))

    def action_cancel(self) -> None:
        self.dismiss(None)


class _WorkerAskApp(App[None]):
    """Minimal app whose thread worker asks via call_from_thread + push_screen_wait.

    This is mechanism A, the shape plan 13-05 will lift into `ask_from_worker`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.captured: str | None = None
        self.captured_set = False

    def on_mount(self) -> None:
        self.ask_worker()

    @work(thread=True, exclusive=True, group="spike")
    def ask_worker(self) -> None:
        async def coro_fn() -> str | None:
            return await self.push_screen_wait(_AskModal())

        self.captured = self.call_from_thread(coro_fn)
        self.captured_set = True


async def _settle_until_modal(app: _WorkerAskApp, pilot: Pilot[None]) -> None:
    for _ in range(400):
        if isinstance(app.screen, _AskModal):
            break
        await pilot.pause()
    await pilot.pause()


async def _settle_until_captured(app: _WorkerAskApp, pilot: Pilot[None]) -> None:
    for _ in range(400):
        if app.captured_set:
            break
        await pilot.pause()
    await pilot.pause()


async def test_a_thread_worker_receives_the_users_modal_answer() -> None:
    app = _WorkerAskApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_until_modal(app, pilot)
        await pilot.press("down", "enter")
        await _settle_until_captured(app, pilot)
    assert app.captured_set
    assert app.captured == "replace"


async def test_a_dismissed_modal_gives_the_worker_none() -> None:
    app = _WorkerAskApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_until_modal(app, pilot)
        await pilot.press("escape")
        await _settle_until_captured(app, pilot)
    assert app.captured_set
    assert app.captured is None


async def test_the_event_loop_keeps_running_while_the_worker_waits() -> None:
    app = _WorkerAskApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_until_modal(app, pilot)
        ticks = 0
        for _ in range(20):
            ticks += 1
            await pilot.pause()
            assert not app.captured_set
        assert ticks == 20
        await pilot.press("down", "enter")
        await _settle_until_captured(app, pilot)
    assert app.captured == "replace"


_PLATFORM = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
_OUTPUTS: dict[str, tuple[str, ...]] = {
    "rg": ("rg line 1", "rg line 2"),
    "fd": ("fd line 1", "fd line 2", "fd line 3\x1b[31m"),
}


def _tool(
    tool_id: str,
    *,
    requires: tuple[str, ...] = (),
    post_install: tuple[str, ...] = (),
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
        requires=requires,
        post_install=post_install,
    )


def _emit_through_runner(runner: object, tool_id: str, lines: tuple[str, ...]) -> None:
    emit = getattr(runner, "_emit", None)
    if not callable(emit):
        return
    for line in lines:
        emit(tool_id, line)


def _install_with_output(captured: list[str]) -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        captured.append(tool.id)
        _emit_through_runner(runner, tool.id, _OUTPUTS.get(tool.id, ()))
        return InstallOutcome(tool.id, "installed")

    return install


def _inputs(
    *,
    tools: list[Tool] | None = None,
    install: SensitiveInstall | None = None,
    wire_path: Callable[[], str] | None = None,
    verify: Callable[[], str] | None = None,
    present: Collection[str] = (),
    states: Iterable[ToolState] = (),
    unattended: bool = False,
    version_refresh: VersionRefreshService | None = None,
    updates: UpdateService | None = None,
    now: Callable[[], float] = time.monotonic,
) -> ExecuteInputs:
    catalog = tools if tools is not None else [_tool("rg"), _tool("fd")]
    return ExecuteInputs(
        catalog=catalog,
        platform=_PLATFORM,
        wire_path=wire_path if wire_path is not None else (lambda: "PATH wired"),
        verify=verify if verify is not None else (lambda: "PATH verified"),
        install=install if install is not None else _install_with_output([]),
        unattended=unattended,
        version_refresh=presence_service(
            catalog,
            present=present,
            states=states,
            platform=_PLATFORM,
            service=version_refresh,
        ),
        updates=updates,
        now=now,
    )


def test_execute_inputs_requires_a_version_refresh_service() -> None:
    # Built through a dict: the removed and the missing shape are exactly what
    # the type checker refuses, and the runtime error is the behaviour under test.
    base: dict[str, Any] = {
        "catalog": [],
        "platform": _PLATFORM,
        "wire_path": lambda: "",
        "verify": lambda: "",
    }
    with pytest.raises(TypeError):
        ExecuteInputs(**base)
    served: dict[str, Any] = {**base, "version_refresh": presence_service([])}
    ExecuteInputs(**served)

    def installed(_tool: Tool) -> bool:
        return False

    stale: dict[str, Any] = {**served, "installed": installed}
    with pytest.raises(TypeError):
        ExecuteInputs(**stale)
    names = {field.name: field for field in fields(ExecuteInputs)}
    assert "installed" not in names
    assert names["terminal_sync"].default is None


def test_inputs_helper_publishes_presence_into_a_frozen_service() -> None:
    inputs = _inputs(present=("rg",))
    rg = inputs.version_refresh.state_of("rg")
    fd = inputs.version_refresh.state_of("fd")
    assert rg is not None
    assert rg.present is True
    assert fd is not None
    assert fd.present is False
    assert inputs.version_refresh.is_present(_tool("rg")) is True


class _FakeClock:
    """A settable clock for D-10: timing is driven by advancing a value.

    No test in this module sleeps on the wall clock; every timing test
    advances `.value` and calls the check directly.
    """

    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _host(inputs: ExecuteInputs, tools: list[Tool] | None = None) -> UnifiedApp:
    catalog = tools if tools is not None else list(inputs.catalog)
    return UnifiedApp(
        catalog,
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=list,
            ban_names=list,
            has_path_block=lambda: False,
            remove=lambda _decision: SweepResult(),
        ),
        policies=PolicyInputs(policies=[]),
        execute=inputs,
    )


_TEST_LOG_SNAPSHOTS: WeakKeyDictionary[ExecuteScreen, str] = WeakKeyDictionary()


def _log_text(screen: ExecuteScreen) -> str:
    captured = _TEST_LOG_SNAPSHOTS.get(screen)
    if captured is not None:
        return captured
    log = screen.query_one("#execute-log")
    lines = getattr(log, "lines", ())
    parts: list[str] = []
    for strip in lines:
        text = getattr(strip, "text", None)
        parts.append(text if isinstance(text, str) else str(strip))
    return "\n".join(parts)


async def _settle_execute(screen: ExecuteScreen, pilot: Pilot[list[str] | None]) -> None:
    for _ in range(400):
        if screen.finished:
            break
        await pilot.pause()
    await pilot.pause()


def test_sanitize_log_line_drops_ascii_control_characters_except_tab() -> None:
    raw = "ok\x1b[31m\x07done\tkeep"
    cleaned = sanitize_log_line(raw)
    assert "\x1b" not in cleaned
    assert "\x07" not in cleaned
    assert "\t" in cleaned
    assert "ok" in cleaned
    assert "done" in cleaned


async def test_nothing_runs_before_the_confirm_keypress() -> None:
    captured: list[str] = []
    inputs = _inputs(install=_install_with_output(captured))
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        for _ in range(10):
            await pilot.pause()
        assert screen.started is False
        assert captured == []


async def test_streamed_lines_are_attributed_per_tool_with_section_dividers() -> None:
    captured: list[str] = []
    wire_calls: list[str] = []
    verify_calls: list[str] = []
    inputs = _inputs(
        install=_install_with_output(captured),
        wire_path=lambda: wire_calls.append("wire") or "PATH wired",
        verify=lambda: verify_calls.append("verify") or "PATH verified",
    )
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "\x1b" not in log
        assert "rg line 1" in log
        assert "rg line 2" in log
        assert "fd line 1" in log
        assert "fd line 2" in log
        assert "fd line 3" in log
        assert log.count("rg") >= 3
        assert log.count("fd") >= 4
        assert screen.finished is True
        assert wire_calls == ["wire"]
        assert verify_calls == ["verify"]
        assert "PATH wired" in log
        assert "PATH verified" in log
        assert app.screen is screen
        for _ in range(20):
            await pilot.pause()
        assert app.screen is screen
        assert app.is_running is True
        assert app.outcomes is not None
        assert app.outcomes == {o.row.tool_id: o for o in screen.outcomes or []}


async def test_escape_mid_run_does_not_pop_and_names_ctrl_c_cost() -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    inputs = _inputs(install=blocking_install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen
        assert screen.finished is False
        assert screen.status.text != ""
        text = screen.status.text.lower()
        assert "running" in text
        assert "ctrl+c" in text
        assert "half-installed" in text or "half installed" in text
        release.set()
        await _settle_execute(screen, pilot)


async def test_a_crashing_install_finishes_the_run_and_names_the_rest_not_attempted() -> None:
    def boom(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del tool, platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        raise OSError("disk full")

    inputs = _inputs(install=boom)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.finished is True
        assert _results(screen) == {"rg": "crashed", "fd": "not_attempted"}
        assert "disk full" in _log_text(screen)
        assert _not_attempted(screen) == ["fd"]


def _results(screen: ExecuteScreen) -> dict[str, str]:
    """The finished run's result per tool id, as the dismiss value carries it."""
    return {outcome.row.tool_id: outcome.result for outcome in screen.outcomes or []}


def _not_attempted(screen: ExecuteScreen) -> list[str]:
    return [
        outcome.row.tool_id
        for outcome in screen.outcomes or []
        if outcome.result == "not_attempted"
    ]


def _head_text(screen: ExecuteScreen) -> str:
    return str(screen.query_one("#execute-head", Static).render())


async def test_preflight_head_names_a_dragged_in_dependency_before_any_keypress() -> None:
    tools = [_tool("rg", requires=("fd",)), _tool("fd")]
    captured: list[str] = []
    inputs = _inputs(tools=tools, install=_install_with_output(captured))
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        head = _head_text(screen)
        assert head
        assert "2 will install" in head
        assert "Indented rows" in head
        assert "needed by rg" in _plan_prompts(screen)[1]
        assert _keys_text(screen).startswith("enter start")
        assert screen.started is False
        assert captured == []
        for _ in range(10):
            await pilot.pause()
        assert screen.started is False
        assert captured == []


async def test_unattended_renders_the_head_before_the_worker_starts() -> None:
    captured: list[str] = []
    started_with_head: list[str] = []
    original = _install_with_output(captured)

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del confirm_sensitive_action
        return original(
            tool,
            platform,
            runner,
            resolve_tag,
            checksum_policy=checksum_policy,
            tools=tools,
        )

    inputs = _inputs(install=install, unattended=True)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        for _ in range(400):
            screen = app.screen
            if isinstance(screen, ExecuteScreen) and screen.started:
                started_with_head.append(_head_text(screen))
                break
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert started_with_head
        assert started_with_head[0]
        await _settle_execute(screen, pilot)
        assert captured == ["rg"]


def _mismatch_then_ok() -> tuple[list[tuple[str, str]], SensitiveInstall]:
    seen: list[tuple[str, str]] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, tools, confirm_sensitive_action
        seen.append((tool.id, checksum_policy))
        if len([row for row in seen if row[0] == tool.id]) == 1 and checksum_policy == "fail":
            return InstallOutcome(
                tool.id,
                "checksum-mismatch",
                method_kind="github_release",
                errors=(RuntimeError("checksum mismatch"),),
            )
        return InstallOutcome(tool.id, "installed", method_kind="github_release")

    return seen, install


async def _settle_until_mismatch(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    for _ in range(400):
        if isinstance(app.screen, ChecksumMismatchScreen):
            break
        await pilot.pause()
    await pilot.pause()


def _mismatch_labels(screen: ChecksumMismatchScreen) -> str:
    parts = [str(label.render()) for label in screen.query(Label)]
    return "\n".join(parts)


async def test_checksum_mismatch_screen_shows_tool_id_and_three_options() -> None:
    captured: list[str | None] = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ChecksumMismatchScreen("rg"), captured.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChecksumMismatchScreen)
        text = _mismatch_labels(screen)
        assert "rg" in text
        assert "Checksum mismatch for rg" in text
        assert "Retry the download" in text
        assert "Skip this tool" in text
        assert "Fall back to another install method (brew/native)" in text
        await pilot.press("enter")
        await pilot.pause()
    assert captured == ["retry"]

    captured = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ChecksumMismatchScreen("rg"), captured.append)
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
    assert captured == ["skip"]

    captured = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ChecksumMismatchScreen("rg"), captured.append)
        await pilot.pause()
        await pilot.press("down", "down", "enter")
        await pilot.pause()
    assert captured == ["fallback"]

    captured = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ChecksumMismatchScreen("rg"), captured.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert captured == [None]


async def test_retrying_a_mismatch_installs_twice_and_finishes_installed() -> None:
    seen, install = _mismatch_then_ok()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert seen == [("rg", "fail"), ("rg", "fail")]
        assert _results(screen)["rg"] == "done"
        assert "mismatch" not in _results(screen).values()


async def test_skipping_a_mismatch_leaves_the_tool_in_mismatched() -> None:
    seen, install = _mismatch_then_ok()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        await pilot.press("down", "enter")
        await _settle_execute(screen, pilot)
        assert seen == [("rg", "fail")]
        assert _results(screen)["rg"] == "mismatch"
        assert "done" not in _results(screen).values()


async def test_fallback_mismatch_reinstalls_with_continue_policy() -> None:
    seen, install = _mismatch_then_ok()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        await pilot.press("down", "down", "enter")
        await _settle_execute(screen, pilot)
        assert seen == [("rg", "fail"), ("rg", "continue")]
        assert _results(screen)["rg"] == "done"


async def test_escaping_mismatch_skips_and_explains_the_dismissal() -> None:
    seen, install = _mismatch_then_ok()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        await pilot.press("escape")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "rg" in log
        assert "dismissed" in log.lower()
        assert "skip" in log.lower()
        assert screen.status.text != ""
        assert seen == [("rg", "fail")]
        assert _results(screen)["rg"] == "mismatch"


async def test_unattended_mismatch_never_opens_the_modal_and_hard_fails() -> None:
    seen, install = _mismatch_then_ok()
    inputs = _inputs(install=install, unattended=True)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        for _ in range(400):
            if screen.finished:
                break
            assert not isinstance(app.screen, ChecksumMismatchScreen)
            await pilot.pause()
        await _settle_execute(screen, pilot)
        assert not isinstance(app.screen, ChecksumMismatchScreen)
        assert seen == [("rg", "fail")]
        assert _results(screen)["rg"] == "mismatch"
        assert "done" not in _results(screen).values()


async def test_the_event_loop_keeps_running_while_the_mismatch_prompt_is_open() -> None:
    seen, install = _mismatch_then_ok()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        ticks = 0
        for _ in range(20):
            ticks += 1
            await pilot.pause()
            assert isinstance(app.screen, ChecksumMismatchScreen)
            assert screen.finished is False
        assert ticks == 20
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert seen == [("rg", "fail"), ("rg", "fail")]


def _keys_text(screen: ExecuteScreen) -> str:
    return str(screen.query_one("#execute-keys", Static).render())


def _install_second_fails(captured: list[str]) -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        captured.append(tool.id)
        if tool.id == "fd":
            return InstallOutcome(tool.id, "failed")
        return InstallOutcome(tool.id, "installed")

    return install


async def test_a_failed_tool_does_not_stop_the_batch() -> None:
    captured: list[str] = []
    tools = [_tool("rg"), _tool("fd"), _tool("bat")]
    inputs = _inputs(tools=tools, install=_install_second_fails(captured))
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd", "bat"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert captured == ["rg", "fd", "bat"]
        assert _results(screen)["fd"] == "failed"
        assert _results(screen) == {"rg": "done", "fd": "failed", "bat": "done"}


async def test_cancel_mid_run_lets_the_in_flight_tool_finish() -> None:
    rg_done = threading.Event()
    fd_started = threading.Event()
    fd_release = threading.Event()
    captured: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        captured.append(tool.id)
        if tool.id == "rg":
            rg_done.set()
            return InstallOutcome(tool.id, "installed")
        if tool.id == "fd":
            fd_started.set()
            assert fd_release.wait(timeout=5)
            return InstallOutcome(tool.id, "installed")
        return InstallOutcome(tool.id, "installed")

    tools = [_tool("rg"), _tool("fd"), _tool("bat")]
    inputs = _inputs(tools=tools, install=install)
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd", "bat"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if rg_done.is_set() and fd_started.is_set():
                break
            await pilot.pause()
        await pilot.pause()
        assert fd_started.is_set()
        await pilot.press("c")
        await pilot.pause()
        assert app.screen is screen
        assert screen.cancel_event.is_set()
        text = screen.status.text.lower()
        assert text
        assert "finish" in text
        assert "start" in text
        fd_release.set()
        await _settle_execute(screen, pilot)
        assert captured == ["rg", "fd"]
        assert _not_attempted(screen) == ["bat"]
        assert _results(screen)["rg"] == "done"
        assert _results(screen)["fd"] == "done"
        log = _log_text(screen)
        assert sum("bat" in line for line in log.splitlines()) == 1
        assert any("bat" in line and "not attempted" in line for line in log.splitlines())
        assert not any(line.startswith("Not attempted: ") for line in log.splitlines())


async def test_a_full_run_does_not_name_not_attempted_tools() -> None:
    captured: list[str] = []
    tools = [_tool("rg"), _tool("fd")]
    inputs = _inputs(tools=tools, install=_install_with_output(captured))
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen).lower()
        assert "not attempted" not in log
        assert "never attempted" not in log
        assert _not_attempted(screen) == []


async def test_cancel_before_start_and_after_finish_only_sets_status() -> None:
    captured: list[str] = []
    inputs = _inputs(install=_install_with_output(captured))
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("c")
        await pilot.pause()
        assert screen.status.text != ""
        assert screen.started is False
        assert screen.finished is False
        assert captured == []
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.finished is True
        await pilot.press("c")
        await pilot.pause()
        assert screen.status.text != ""
        assert screen.started is True
        assert screen.finished is True
        assert captured == ["rg"]


async def test_cancel_is_inert_while_the_mismatch_modal_is_open() -> None:
    fd_started = threading.Event()
    fd_release = threading.Event()
    seen, mismatch_install = _mismatch_then_ok()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del confirm_sensitive_action
        if tool.id == "rg":
            return mismatch_install(
                tool,
                platform,
                runner,
                resolve_tag,
                checksum_policy=checksum_policy,
                tools=tools,
            )
        fd_started.set()
        assert fd_release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    tools = [_tool("rg"), _tool("fd")]
    inputs = _inputs(tools=tools, install=install)
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        await pilot.press("c")
        await pilot.pause()
        assert not screen.cancel_event.is_set()
        waiting = screen.status.text.lower()
        assert waiting
        assert "prompt" in waiting or "question" in waiting or "mismatch" in waiting
        await pilot.press("down", "enter")
        for _ in range(400):
            if fd_started.is_set() and not isinstance(app.screen, ChecksumMismatchScreen):
                break
            await pilot.pause()
        assert fd_started.is_set()
        restored = screen.status.text.lower()
        assert "c" in restored or "cancel" in restored or "stop" in restored
        await pilot.press("c")
        await pilot.pause()
        assert screen.cancel_event.is_set()
        fd_release.set()
        await _settle_execute(screen, pilot)
        assert seen == [("rg", "fail")]


def _recording_sensitive_install() -> tuple[
    list[ConfirmSensitiveAction | None], list[bool], SensitiveInstall
]:
    received: list[ConfirmSensitiveAction | None] = []
    answers: list[bool] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools
        received.append(confirm_sensitive_action)
        if confirm_sensitive_action is not None:
            answers.append(confirm_sensitive_action(tool.id, "set_login_shell"))
        return InstallOutcome(tool.id, "installed")

    return received, answers, install


def _sensitive_action_screen() -> type[ModalScreen[str | None]]:
    from installer import execute_screen as execute_module

    screen_cls = getattr(execute_module, "SensitiveActionScreen", None)
    assert screen_cls is not None, "D-05 requires SensitiveActionScreen"
    return screen_cls


async def _settle_until_sensitive(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    screen_cls = _sensitive_action_screen()
    for _ in range(400):
        if isinstance(app.screen, screen_cls):
            break
        await pilot.pause()
    await pilot.pause()


def _sensitive_labels(screen: ModalScreen[object]) -> str:
    parts = [str(label.render()) for label in screen.query(Label)]
    return "\n".join(parts)


def _assert_sensitive_prompt_copy(text: str, tool_id: str) -> None:
    lowered = text.lower()
    assert tool_id in text
    assert "reviewed command" in lowered
    assert "login shell" in lowered
    assert "zsh" in lowered
    assert "after the installer" in lowered or "your own terminal" in lowered
    assert "will be changed" not in lowered


async def test_sensitive_action_screen_names_the_tool_and_the_reviewed_command() -> None:
    screen_cls = _sensitive_action_screen()
    captured: list[str | None] = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(screen_cls("oh-my-zsh"), captured.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, screen_cls)
        _assert_sensitive_prompt_copy(_sensitive_labels(screen), "oh-my-zsh")
        await pilot.press("enter")
        await pilot.pause()
    assert captured == ["yes"]

    captured = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(screen_cls("oh-my-zsh"), captured.append)
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
    assert captured == ["no"]

    captured = []
    app = _host(_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(screen_cls("oh-my-zsh"), captured.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert captured == [None]


async def test_accepting_the_login_shell_prompt_returns_true_to_the_install_seam() -> None:
    received, answers, install = _recording_sensitive_install()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_sensitive(app, pilot)
        prompt = app.screen
        assert isinstance(prompt, _sensitive_action_screen())
        _assert_sensitive_prompt_copy(_sensitive_labels(prompt), "rg")
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
    assert answers == [True]
    assert received and received[0] is not None


async def test_refusing_the_login_shell_prompt_returns_false_to_the_install_seam() -> None:
    _received, answers, install = _recording_sensitive_install()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_sensitive(app, pilot)
        await pilot.press("down", "enter")
        await _settle_execute(screen, pilot)
    assert answers == [False]


async def test_escaping_the_login_shell_prompt_returns_false_and_explains() -> None:
    _received, answers, install = _recording_sensitive_install()
    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_sensitive(app, pilot)
        await pilot.press("escape")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "rg" in log
        assert "false" in log.lower() or "no" in log.lower() or "refused" in log.lower()
    assert answers == [False]


async def test_sensitive_unattended_never_opens_the_modal_and_passes_no_confirmation() -> None:
    received, answers, install = _recording_sensitive_install()
    inputs = _inputs(install=install, unattended=True)
    app = _host(inputs)
    screen_cls = _sensitive_action_screen()
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        for _ in range(400):
            if screen.finished:
                break
            assert not isinstance(app.screen, screen_cls)
            await pilot.pause()
        await _settle_execute(screen, pilot)
        assert not isinstance(app.screen, screen_cls)
    assert answers == []
    assert received == [None]


async def test_cancel_is_inert_while_the_sensitive_prompt_is_open() -> None:
    fd_started = threading.Event()
    fd_release = threading.Event()
    _received, answers, sensitive_install = _recording_sensitive_install()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        if tool.id == "rg":
            return sensitive_install(
                tool,
                platform,
                runner,
                resolve_tag,
                checksum_policy=checksum_policy,
                tools=tools,
                confirm_sensitive_action=confirm_sensitive_action,
            )
        fd_started.set()
        assert fd_release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    tools = [_tool("rg"), _tool("fd")]
    inputs = _inputs(tools=tools, install=install)
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_sensitive(app, pilot)
        await pilot.press("c")
        await pilot.pause()
        assert not screen.cancel_event.is_set()
        waiting = screen.status.text.lower()
        assert waiting
        assert "prompt" in waiting or "question" in waiting
        await pilot.press("down", "enter")
        for _ in range(400):
            if fd_started.is_set() and not isinstance(app.screen, _sensitive_action_screen()):
                break
            await pilot.pause()
        assert fd_started.is_set()
        restored = screen.status.text.lower()
        assert "c" in restored or "cancel" in restored or "stop" in restored
        await pilot.press("c")
        await pilot.pause()
        assert screen.cancel_event.is_set()
        fd_release.set()
        await _settle_execute(screen, pilot)
    assert answers == [False]


async def test_execute_keys_name_the_idle_actions_before_a_run() -> None:
    inputs = _inputs()
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert _keys_text(screen) == "enter start · up/down move · esc cancel"


def _mixed_report_install() -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        if tool.id == "rg":
            return InstallOutcome(tool.id, "installed", method_kind="github_release", verified=True)
        if tool.id == "fd":
            return InstallOutcome(tool.id, "failed", errors=(RuntimeError("disk exploded"),))
        if tool.id == "pi":
            return InstallOutcome(
                tool.id,
                "manual-required",
                method_kind="host_setup",
                handoff=("After leaving the installer, run these Pi setup commands.",),
            )
        if tool.id == "codegraph":
            return InstallOutcome(
                tool.id,
                "installed",
                method_kind="github_release",
                postinstall_warning="codegraph MCP registration failed: exit 1",
            )
        if tool.id == "oh-my-zsh":
            return InstallOutcome(
                tool.id,
                "installed",
                method_kind="script",
                post_install_handoff=(
                    "chsh -s /bin/zsh",
                    "run this\x1b[31mred\x07 after the installer exits",
                ),
            )
        return InstallOutcome(tool.id, "installed")

    return install


async def test_post_run_log_carries_every_renderer_in_wizard_order() -> None:
    tools = [
        _tool("rg"),
        _tool("fd"),
        _tool("bat", requires=("fd",)),
        _tool("pi"),
        _tool("oh-my-zsh"),
        _tool("codegraph"),
    ]
    inputs = _inputs(
        tools=tools,
        install=_mixed_report_install(),
        wire_path=lambda: "PATH wired",
        verify=lambda: "PATH verified",
    )
    app = _host(inputs, tools)
    async with app.run_test(size=(120, 40)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd", "bat", "pi", "oh-my-zsh", "codegraph"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "disk exploded" in log
        assert "dependency failed — fd" in log
        assert "skipped — dependency failed" not in log
        assert "After leaving the installer, run these Pi setup commands." in log
        assert "chsh -s /bin/zsh" in log
        assert "oh-my-zsh" in log
        assert "after install" in log.lower()
        assert "run this" in log
        assert "red" in log
        assert "after the installer exits" in log
        assert "\x1b" not in log
        assert "\x07" not in log
        assert log.lower().count("after install") == 1
        assert "codegraph MCP registration failed: exit 1" in log
        assert "sha256" in log
        assert "PATH wired" in log
        assert "PATH verified" in log
        summary_at = log.index("Summary — ")
        fail_at = log.index("disk exploded")
        dependency_at = log.lower().index("dependency failed — fd")
        handoff_at = log.index("After leaving the installer")
        post_install_at = log.index("chsh -s /bin/zsh")
        warn_at = log.index("postinstall warning")
        verify_at = log.index("sha256")
        path_at = log.index("PATH wired")
        audit_at = log.index("PATH verified")
        assert (
            summary_at
            < fail_at
            < dependency_at
            < handoff_at
            < post_install_at
            < warn_at
            < verify_at
        )
        assert verify_at < path_at < audit_at
        assert "PATH wiring" in log
        assert "PATH audit" in log or "Read-only audit" in log
        assert screen.status.text != ""
        assert "catalog" in screen.status.text.lower()
        assert "enter" in screen.status.text.lower() or "esc" in screen.status.text.lower()


def _ansi_bomb_install() -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        error = CommandError(
            [tool.id, "--install"], 1, detail="normal output\x1b[2J\x1b[31mred\x1b]0;pwned\x07"
        )
        return InstallOutcome(tool.id, "failed", errors=(error,))

    return install


async def test_failed_install_report_never_carries_raw_escape_sequences() -> None:
    """CR-01 regression: sanitize_log_line must run on the FAILURE path too.

    Streaming output already went through sanitize_log_line
    (test_streamed_lines_are_html_escaped_and_control_stripped); this pins the
    second, previously-unsanitized route — CommandError.detail -> InstallOutcome.errors
    -> render_failure_details -> the post-run report written into the log.
    """
    tools = [_tool("fd")]
    inputs = _inputs(tools=tools, install=_ansi_bomb_install())
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "\x1b" not in log
        assert "\x07" not in log
        assert "normal output" in log
        assert "red" in log
        assert "pwned" in log


async def test_wire_path_oserror_names_the_section_and_still_finishes() -> None:
    def boom() -> str:
        raise OSError("read-only file system")

    inputs = _inputs(wire_path=boom)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "read-only file system" in log
        assert "PATH wiring" in log or "path" in log.lower()
        assert screen.finished is True
        assert screen.status.text != ""
        assert "catalog" in screen.status.text.lower()


_MANAGED = Path("/tmp/tools-installer-bin")


def _empty_inventory(**_kwargs: object) -> ManagerInventory:
    return ManagerInventory(
        brew_formulae={},
        brew_casks={},
        pnpm_globals=frozenset(),
        uv_tools={},
        brew_prefix=None,
    )


def _empty_outdated(**_kwargs: object) -> OutdatedReport:
    return OutdatedReport(brew={}, cask={}, pnpm={}, uv={})


def _brew_ownership(tool: Tool) -> ManagerOwnership:
    method = tool.methods[0] if tool.methods else None
    return ManagerOwnership(
        tool_id=tool.id,
        owner="brew",
        method=method,
        package=tool.id,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(
            OwnershipCandidate(
                owner="brew",
                method=method,
                package=tool.id,
                current_version=None,
                evidence="test",
            ),
        ),
        active_candidate="brew",
        active_path=None,
        unknown_reason=None,
    )


def _outdated_status(tool_id: str, *, outdated: bool | None) -> VersionStatus:
    return VersionStatus(
        tool_id=tool_id,
        installed="14.1.0",
        latest="14.1.1" if outdated is not False else "14.1.0",
        outdated=outdated,
        stale=False,
        source="brew",
    )


class _RecordingRefreshService(FrozenStateService):
    def __init__(self, cache_path: Path) -> None:
        super().__init__(
            platform=_PLATFORM,
            cache_path=cache_path,
            resolve_tag=lambda _repo: "v1",
            probe_output=lambda _argv: "1.0",
            managed_bin_dir=_MANAGED,
            which=lambda cmd: str(_MANAGED / cmd),
            artifacts_for=lambda tool: [_MANAGED / tool.cmd],
            read_inventory_fn=_empty_inventory,
            read_outdated_fn=_empty_outdated,
            pnpm_packages=lambda: (),
            query=lambda *_a, **_k: "",
        )
        self.asked: list[str] = []

    def refresh(self, tools: Sequence[Tool]) -> None:
        for tool in tools:
            self.asked.append(tool.id)
            _publish(self, tool, version=_outdated_status(tool.id, outdated=True))


class _RecordingUpdateService(UpdateService):
    def __init__(self) -> None:
        super().__init__(
            platform=_PLATFORM,
            runner=lambda _cmd: None,
            resolve_tag=lambda _repo: "v1",
            tools={},
            managed_packages=lambda: (),
            replay_globals=lambda packages: tuple(packages),
            reresolve_ownership=_brew_ownership,
        )
        self.recorded: list[UpdateTarget] = []

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.recorded.append(target)
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="updated",
            owner=target.ownership.owner,
        )


def _publish(
    refresh: FrozenStateService,
    tool: Tool,
    *,
    version: VersionStatus | None,
    broken: bool = False,
) -> None:
    ownership = replace(_brew_ownership(tool), broken=broken)
    refresh.publish([pass_state(tool, platform=_PLATFORM, ownership=ownership, version=version)])


def _seed_refresh(
    refresh: FrozenStateService,
    tool: Tool,
    *,
    outdated: bool | None | object = ...,
) -> None:
    version = None
    if outdated is not ...:
        version = _outdated_status(
            tool.id, outdated=outdated if isinstance(outdated, bool) or outdated is None else True
        )
    _publish(refresh, tool, version=version)


async def _run_execute(
    inputs: ExecuteInputs, ids: list[str]
) -> tuple[ExecuteScreen, _RecordingUpdateService | None]:
    # A tool the test did not publish is absent, not checking: the run reads
    # published state only, so an unseeded catalog tool is MISSING here.
    service = inputs.version_refresh
    if isinstance(service, FrozenStateService):
        unseeded = [tool for tool in inputs.catalog if service.state_of(tool.id) is None]
        service.publish([plan_state(tool, health=Health.MISSING) for tool in unseeded])
    app = _host(inputs, list(inputs.catalog))
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(ids, inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        _TEST_LOG_SNAPSHOTS[screen] = _log_text(screen)
        updates = inputs.updates
        recorded = updates if isinstance(updates, _RecordingUpdateService) else None
        return screen, recorded


async def test_outdated_installed_selected_tool_is_dispatched_through_update_service(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg", "fd"])
    assert screen.finished is True
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["rg"]
    assert captured == ["fd"]


async def test_confirmed_current_tool_is_not_dispatched_as_outdated(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=False)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg", "fd"])
    assert screen.finished is True
    assert recorded is not None
    assert recorded.recorded == []
    assert captured == ["fd"]


async def test_only_outdated_selection_still_starts_and_dispatches(tmp_path: Path) -> None:
    rg = _tool("rg")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        install=_install_with_output(captured),
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg"])
    assert screen.started is True
    assert screen.finished is True
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["rg"]
    assert captured == []


async def test_a_crash_after_a_path_wiring_failure_keeps_both_texts_in_the_log(
    tmp_path: Path,
) -> None:
    """IN-07: the crash text must be APPENDED to an earlier PATH-wiring error,
    never replace it -- the log then carries both texts."""
    rg = _tool("rg")

    def wire_fail() -> str:
        raise OSError("rc file unwritable")

    def verify_crash() -> str:
        # RuntimeError is NOT in run_live's catch list, so this is a real
        # worker crash that happens AFTER the PATH-wiring failure.
        raise RuntimeError("audit exploded")

    inputs = _inputs(
        tools=[rg],
        install=_install_with_output([]),
        wire_path=wire_fail,
        verify=verify_crash,
    )
    app = _host(inputs, list(inputs.catalog))
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        text = _log_text(screen)
        assert "rc file unwritable" in text
        assert "RuntimeError: audit exploded" in text


async def test_nothing_updates_before_the_confirm_keypress(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        for _ in range(10):
            await pilot.pause()
        assert screen.started is False
        assert updates.recorded == []


async def test_confirm_keypress_dispatches_exactly_one_outdated_update(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg"])
    assert screen.finished is True
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["rg"]


async def test_unattended_confirm_still_dispatches_outdated_update(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
        unattended=True,
    )
    app = _host(inputs, [rg])
    started_with_head: list[str] = []
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        for _ in range(400):
            screen = app.screen
            if isinstance(screen, ExecuteScreen) and screen.started:
                started_with_head.append(_head_text(screen))
                break
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert started_with_head
        assert started_with_head[0]
        await _settle_execute(screen, pilot)
        assert [target.tool.id for target in updates.recorded] == ["rg"]


async def test_undisturbed_outdated_run_dispatches_exactly_the_disclosed_update_ids(
    tmp_path: Path,
) -> None:
    """FIXTURE A — equality of disclosed and dispatched update ids."""
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        present=("rg", "fd"),
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert _head_text(screen) == "Install plan — 1 will update, 1 skipped"
        assert _plan_prompts(screen)[0].startswith("↑ rg")
        assert screen.started is False
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        dispatched = [target.tool.id for target in updates.recorded]
        assert dispatched == ["rg"]


async def test_streaming_runner_in_execute_worker_opts_in_to_unbuffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The one live streaming call site (ExecuteScreen._execute_worker) constructs
    # its StreamingRunner with unbuffer=True, verified by monkeypatching the
    # factory and recording the keyword. The factory mirrors StreamingRunner's
    # real signature rather than taking an untyped **kwargs, so the recorded
    # keyword is type-checked against the constructor it stands in for.
    captured_kwargs: list[dict[str, object]] = []
    original_streaming_runner = StreamingRunner

    def recording_factory(
        emit: Callable[[str, str], None],
        *,
        unbuffer: bool = False,
        which: Callable[[str], str | None] = shutil.which,
    ) -> StreamingRunner:
        captured_kwargs.append({"unbuffer": unbuffer, "which": which})
        return original_streaming_runner(emit, unbuffer=unbuffer, which=which)

    monkeypatch.setattr(installer.execute_screen, "StreamingRunner", recording_factory)

    captured: list[str] = []
    inputs = _inputs(install=_install_with_output(captured))
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)

    assert captured_kwargs, "StreamingRunner factory was never called"
    kwargs = captured_kwargs[0]
    assert kwargs.get("unbuffer") is True, f"unbuffer not True: {kwargs}"


def _blocking_install_emitting_one_line(
    started: threading.Event, release: threading.Event
) -> SensitiveInstall:
    """A SensitiveInstall that emits one line, then blocks until released."""

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        _emit_through_runner(runner, tool.id, (f"{tool.id} line 1",))
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    return install


async def _start_and_wait_for_first_line(
    screen: ExecuteScreen, pilot: Pilot[list[str] | None], started: threading.Event
) -> None:
    await pilot.press("enter")
    for _ in range(400):
        if started.is_set():
            break
        await pilot.pause()
    assert started.is_set()
    for _ in range(400):
        if "rg line 1" in _log_text(screen):
            break
        await pilot.pause()
    assert "rg line 1" in _log_text(screen)


async def test_below_threshold_the_indicator_never_appears() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        clock.value += 1.9
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        log = _log_text(screen)
        assert log.splitlines()[-1] == "rg │ rg line 1"
        assert "waiting for output" not in log
        release.set()
        await _settle_execute(screen, pilot)


async def test_at_threshold_the_indicator_is_the_logs_last_line() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        log = _log_text(screen)
        last_line = log.splitlines()[-1]
        assert "rg" in last_line
        assert "still running; waiting for output" in last_line
        # Only one region header for rg -- the indicator did not open a new one.
        assert log.count("── rg ──") == 1
        release.set()
        await _settle_execute(screen, pilot)


async def test_below_threshold_check_rearms_the_timer() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        clock.value += 1.9
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert screen._silence_timer is not None  # pyright: ignore[reportPrivateUsage]
        release.set()
        await _settle_execute(screen, pilot)


async def test_action_start_arms_the_real_timer_and_rearms_for_the_exact_remainder() -> None:
    recorded: list[tuple[float, Callable[[], None] | None]] = []
    original_set_timer = ExecuteScreen.set_timer

    def recording_set_timer(
        self: ExecuteScreen,
        delay: float,
        callback: Callable[[], None] | None = None,
        *,
        name: str | None = None,
        pause: bool = False,
    ) -> object:
        recorded.append((delay, callback))
        return original_set_timer(self, delay, callback, name=name, pause=pause)

    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    ExecuteScreen.set_timer = recording_set_timer  # type: ignore[method-assign]
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await _start_and_wait_for_first_line(screen, pilot, started)

            armed = [call for call in recorded if call[1] == screen._check_output_silence]  # pyright: ignore[reportPrivateUsage]
            assert armed, "action_start did not arm the timer with _check_output_silence"
            assert armed[0][0] == SILENCE_SECONDS

            before = len(
                [call for call in recorded if call[1] == screen._check_output_silence]  # pyright: ignore[reportPrivateUsage]
            )
            clock.value += 1.9
            screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
            await pilot.pause()
            after = [call for call in recorded if call[1] == screen._check_output_silence]  # pyright: ignore[reportPrivateUsage]
            assert len(after) == before + 1
            assert after[-1][0] == pytest.approx(0.1)  # pyright: ignore[reportUnknownMemberType]

            release.set()
            await _settle_execute(screen, pilot)
    finally:
        del ExecuteScreen.set_timer


async def test_arming_the_silence_timer_stops_the_one_it_replaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second arming must not orphan a live Timer nobody can stop any more.

    on_install_run_finished can only stop the NEWEST reference, so a replaced
    timer that was never stopped keeps firing _check_output_silence past the
    end of the run. Pinned on `Timer.stop` rather than on an internal flag:
    stopping is the observable obligation, and the attribute swap alone cannot
    prove it happened.
    """
    stopped: list[Timer] = []
    original_stop = Timer.stop

    def recording_stop(self: Timer) -> None:
        stopped.append(self)
        original_stop(self)

    monkeypatch.setattr(Timer, "stop", recording_stop)

    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release))
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)

        first = screen._silence_timer  # pyright: ignore[reportPrivateUsage]
        assert first is not None, "action_start did not arm a timer"
        assert first not in stopped

        screen._arm_silence_timer(SILENCE_SECONDS)  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()

        second = screen._silence_timer  # pyright: ignore[reportPrivateUsage]
        assert second is not None
        assert second is not first
        assert first in stopped, "the replaced timer was left running"

        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_generation_transient_is_dropped_without_writing_anything() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        before = _log_text(screen)
        stale = InstallLogLine("rg", _WAITING_OUTPUT, transient=True, generation=-1)
        screen.on_install_log_line(stale)
        await pilot.pause()
        assert _log_text(screen) == before
        assert "waiting for output" not in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)


def _two_stage_blocking_install(
    started1: threading.Event,
    release1: threading.Event,
    started2: threading.Event,
    release2: threading.Event,
) -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        _emit_through_runner(runner, tool.id, (f"{tool.id} line 1",))
        started1.set()
        assert release1.wait(timeout=5)
        _emit_through_runner(runner, tool.id, (f"{tool.id} line 2",))
        started2.set()
        assert release2.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    return install


async def test_second_indicator_appears_after_real_output_and_a_second_gap() -> None:
    clock = _FakeClock()
    started1 = threading.Event()
    release1 = threading.Event()
    started2 = threading.Event()
    release2 = threading.Event()
    inputs = _inputs(
        install=_two_stage_blocking_install(started1, release1, started2, release2), now=clock
    )
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started1.is_set():
                break
            await pilot.pause()
        for _ in range(400):
            if "rg line 1" in _log_text(screen):
                break
            await pilot.pause()

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert _log_text(screen).count("still running; waiting for output") == 1

        release1.set()
        for _ in range(400):
            if started2.is_set():
                break
            await pilot.pause()
        for _ in range(400):
            if "rg line 2" in _log_text(screen):
                break
            await pilot.pause()

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert _log_text(screen).count("still running; waiting for output") == 2

        release2.set()
        await _settle_execute(screen, pilot)


async def test_indicator_occurs_exactly_once_across_three_checks_in_one_gap() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        clock.value += 1.0
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        clock.value += 1.0
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert _log_text(screen).count("still running; waiting for output") == 1
        release.set()
        await _settle_execute(screen, pilot)


async def test_transient_line_does_not_reset_last_output_at_or_in_flight() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert screen._in_flight == "rg"  # pyright: ignore[reportPrivateUsage]
        assert screen._last_output_at == 0.0  # pyright: ignore[reportPrivateUsage]
        release.set()
        await _settle_execute(screen, pilot)


def _install_first_immediate_second_blocks(
    started: threading.Event, release: threading.Event
) -> SensitiveInstall:
    """rg finishes at once; fd emits one line then blocks until released."""

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        if tool.id == "rg":
            return InstallOutcome(tool.id, "installed")
        _emit_through_runner(runner, tool.id, (f"{tool.id} line 1",))
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    return install


async def test_indicator_names_the_second_tool_when_the_first_has_finished() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_install_first_immediate_second_blocks(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        for _ in range(400):
            if "fd line 1" in _log_text(screen):
                break
            await pilot.pause()
        assert screen._in_flight == "fd"  # pyright: ignore[reportPrivateUsage]
        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        last_line = _log_text(screen).splitlines()[-1]
        assert "fd" in last_line
        assert "rg" not in last_line
        assert "still running; waiting for output" in last_line
        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_terminal_message_for_another_tool_does_not_clear_in_flight() -> None:
    """Regression: a terminal message for a FINISHED tool must not suppress a
    DIFFERENT, still in-flight and silent tool's indicator (review round 2)."""
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_install_first_immediate_second_blocks(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        for _ in range(400):
            if "fd line 1" in _log_text(screen):
                break
            await pilot.pause()
        assert screen._in_flight == "fd"  # pyright: ignore[reportPrivateUsage]

        # A stale/delayed terminal message for rg -- already finished --
        # must not clear fd's silence window.
        screen.on_row_finished(
            RowFinished(RowOutcome(PlanRow("rg", Disposition.INSTALL, ""), "done"))
        )
        await pilot.pause()
        assert screen._in_flight == "fd"  # pyright: ignore[reportPrivateUsage]

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        last_line = _log_text(screen).splitlines()[-1]
        assert "fd" in last_line
        assert "still running; waiting for output" in last_line
        release.set()
        await _settle_execute(screen, pilot)


def _captured_transient(screen: ExecuteScreen, tool_id: str) -> InstallLogLine:
    """The transient the check would post right now, without posting it.

    Reaches the state where the indicator WOULD be written (in flight, not
    finished, no prompt open) by latching `_silence_noted` directly, then
    returns the identical message `_check_output_silence` would construct at
    the current generation -- the deterministic substitute for racing the
    real timer against a real invalidation.

    `_transient_is_current` ANDs five conditions, so a caller must know which
    one its own invalidation flips, or a passing assertion proves nothing
    about the rest. What each caller below invalidates:

    - `..._beaten_by_a_real_line_is_dropped`: `_note_output` clears
      `_silence_noted` AND bumps `_silence_generation` -- two at once.
    - `..._beaten_by_install_tool_finished_is_dropped`: `_clear_in_flight`
      nulls `_in_flight`, clears `_silence_noted` and bumps the generation.
    - `..._beaten_by_run_finished_is_dropped`: `self.finished` becomes True,
      plus everything `_clear_in_flight` does.
    - `test_stale_generation_alone_drops_the_transient`: the ONLY caller that
      flips exactly one condition, and therefore the only one whose result is
      attributable to the generation token.
    """
    screen._silence_noted = True  # pyright: ignore[reportPrivateUsage]
    return InstallLogLine(
        tool_id,
        _WAITING_OUTPUT,
        transient=True,
        generation=screen._silence_generation,  # pyright: ignore[reportPrivateUsage]
    )


async def test_stale_generation_alone_drops_the_transient() -> None:
    """The generation token is the REASON the drop happens, not a bystander.

    Every other race test here invalidates one of `_transient_is_current`'s
    four remaining conditions at the same time, so the comparison is never
    what makes the message stale -- deleting it from production leaves them
    all green. This one holds the in-flight tool, the prompt state, the
    finished flag and `_silence_noted` identical between two messages and
    changes nothing but the token.
    """
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release))
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)

        current = _captured_transient(screen, "rg")  # latches _silence_noted = True
        # The writable baseline: with the token matching, this message WOULD
        # be rendered. Without it the negative assertion below could not tell
        # the token apart from any other condition being false.
        assert screen._transient_is_current(current)  # pyright: ignore[reportPrivateUsage]

        assert current.generation is not None
        stale = InstallLogLine(
            "rg", _WAITING_OUTPUT, transient=True, generation=current.generation - 1
        )
        assert not screen._transient_is_current(stale)  # pyright: ignore[reportPrivateUsage]

        before = _log_text(screen)
        screen.on_install_log_line(stale)
        await pilot.pause()
        assert _log_text(screen) == before
        assert "waiting for output" not in _log_text(screen)

        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_transient_beaten_by_a_real_line_is_dropped() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        captured = _captured_transient(screen, "rg")
        screen.on_install_log_line(InstallLogLine("rg", "rg line 2"))
        await pilot.pause()
        before = _log_text(screen)
        assert "rg line 2" in before
        screen.on_install_log_line(captured)
        await pilot.pause()
        assert _log_text(screen) == before
        assert "waiting for output" not in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_transient_beaten_by_install_tool_finished_is_dropped() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        captured = _captured_transient(screen, "rg")
        screen.on_row_finished(
            RowFinished(RowOutcome(PlanRow("rg", Disposition.INSTALL, ""), "done"))
        )
        await pilot.pause()
        screen.on_install_log_line(captured)
        await pilot.pause()
        assert "waiting for output" not in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_transient_beaten_by_run_finished_is_dropped() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    inputs = _inputs(install=_blocking_install_emitting_one_line(started, release), now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await _start_and_wait_for_first_line(screen, pilot, started)
        captured = _captured_transient(screen, "rg")
        screen.on_install_run_finished(InstallRunFinished([], None, "", ""))
        await pilot.pause()
        screen.on_install_log_line(captured)
        await pilot.pause()
        assert "waiting for output" not in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)


async def test_run_finished_stops_and_drops_the_silence_timer() -> None:
    inputs = _inputs()
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.finished is True
        assert screen._silence_timer is None  # pyright: ignore[reportPrivateUsage]

        # Silent after the run, belt AND braces: a callback already dispatched
        # before the stop landed still returns harmlessly. Without this the
        # `return` under `if self.finished` was executed by no test in the
        # suite, so the guarantee was asserted only as "the timer is gone" --
        # which says nothing about a callback already in flight.
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert "waiting for output" not in _log_text(screen)
        # And it did not re-arm a timer that outlives the run.
        assert screen._silence_timer is None  # pyright: ignore[reportPrivateUsage]


async def test_silence_suppressed_while_prompt_open_and_restarts_after_close() -> None:
    clock = _FakeClock()
    seen: list[str] = []
    started = threading.Event()
    release = threading.Event()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        seen.append(tool.id)
        if len(seen) == 1:
            return InstallOutcome(
                tool.id,
                "checksum-mismatch",
                method_kind="github_release",
                errors=(RuntimeError("checksum mismatch"),),
            )
        _emit_through_runner(runner, tool.id, (f"{tool.id} line 1",))
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed", method_kind="github_release")

    inputs = _inputs(install=install, now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_until_mismatch(app, pilot)
        assert screen._waiting_prompt == "rg"  # pyright: ignore[reportPrivateUsage]
        clock.value += 5.0
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert "waiting for output" not in _log_text(screen)

        await pilot.press("enter")  # retry
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        for _ in range(400):
            if "rg line 1" in _log_text(screen):
                break
            await pilot.pause()
        assert screen._waiting_prompt is None  # pyright: ignore[reportPrivateUsage]

        # The window restarted at close, not on the stale pre-prompt timestamp.
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert "waiting for output" not in _log_text(screen)

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert "waiting for output" in _log_text(screen)

        release.set()
        await _settle_execute(screen, pilot)


async def test_install_emitting_nothing_never_shows_an_indicator() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    inputs = _inputs(install=install, now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        clock.value += 5.0
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert "waiting for output" not in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)


async def test_install_driven_through_method_started_shows_the_indicator() -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        method_started = getattr(runner, "method_started", None)
        assert callable(method_started)
        method_started("brew")
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, "installed")

    inputs = _inputs(install=install, now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        await pilot.pause()
        assert "-- trying brew --" in _log_text(screen)

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        last_line = _log_text(screen).splitlines()[-1]
        assert "rg" in last_line
        assert "still running; waiting for output" in last_line

        release.set()
        await _settle_execute(screen, pilot)


async def test_failed_install_with_real_runner_shows_child_tail_and_indicator_once() -> None:
    """Never-persisted, proved against a REAL StreamingRunner failure.

    The install closure drives the runner it was HANDED (the worker's own,
    already attributed by the worker's row callback) rather than a separately
    constructed StreamingRunner -- a fresh one would raise RuntimeError from
    _current() on its very first emitted line (installer/run.py:125-131,
    159-162), before the child's non-zero exit is ever reached.
    """
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        try:
            # The printed text is built from concatenated fragments so the
            # cmd argv itself never contains "boom one"/"boom two" as a
            # contiguous substring -- CommandError's message embeds the argv
            # verbatim, and a literal substring there would double-count
            # against the assertions below, which are about the CHILD's
            # stdout reaching the log and the report, not about its argv.
            script = "print('bo'+'om one'); print('bo'+'om two'); raise SystemExit(3)"
            runner([sys.executable, "-c", script])
        except CommandError as exc:
            started.set()
            assert release.wait(timeout=5)
            return InstallOutcome(tool.id, "failed", errors=(exc,))
        raise AssertionError("expected the child to fail")

    inputs = _inputs(install=install, now=clock)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        for _ in range(400):
            if "boom two" in _log_text(screen):
                break
            await pilot.pause()
        assert "boom one" in _log_text(screen)
        assert "boom two" in _log_text(screen)

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()

        release.set()
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert log.count("boom one") == 2  # once live, once in the report tail
        assert log.count("boom two") == 2
        assert log.count("still running; waiting for output") == 1


# Prints one line WITHOUT -u and WITHOUT flush=True -- so on a pipe it sits in
# the child's own stdio buffer unless the parent forced line buffering -- then
# refuses to print its second line or exit until sys.argv[1] exists. Its own
# ~30s ceiling means a red test can never leave a child running forever.
_SENTINEL_CHILD = """
import os, sys, time

print("child line 1")
deadline = time.monotonic() + 30.0
while not os.path.exists(sys.argv[1]) and time.monotonic() < deadline:
    time.sleep(0.02)
print("child line 2")
"""


async def test_child_output_reaches_the_widget_while_the_child_is_still_alive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The WHOLE chain, observed before the child exits (plan 01 Task 1).

    Popen env -> the child's unflushed stdout -> the parent's read -> _emit ->
    post_message -> on_install_log_line -> RichLog. The runner-level timing
    test stops at `_emit` and says nothing about the three hops after it.

    "While the child still runs" is true by CONSTRUCTION rather than by clock:
    at the moment the first line is asserted present, the child physically
    cannot have exited, because it is blocked polling for a sentinel file this
    test has not created yet -- so its second line cannot be in the log either.

    Without the PYTHONUNBUFFERED rung the RED state is a real deadlock: the
    first line stays in the child's buffer, the log never shows it, the
    sentinel is never written by the assertion path, and the bounded poll ends
    the test red.
    """
    monkeypatch.delenv("PYTHONUNBUFFERED", raising=False)
    sentinel = tmp_path / "release-the-child"

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        # The runner it was HANDED -- the worker's own StreamingRunner, already
        # set_tool-attributed by the worker's row callback. A freshly constructed one
        # would raise RuntimeError from _current() on its first emitted line.
        runner([sys.executable, "-c", _SENTINEL_CHILD, str(sentinel)])
        return InstallOutcome(tool.id, "installed")

    inputs = _inputs(install=install)
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        try:
            # A real delay per iteration, not a bare idle pause: an idle-only
            # pause returns the moment the event loop has nothing left to do,
            # so 400 of them can elapse before a freshly spawned interpreter
            # has printed anything -- which would fail on interpreter startup
            # rather than on buffering. 400 x 0.02s is ~8s of headroom.
            for _ in range(400):
                if "child line 1" in _log_text(screen):
                    break
                await pilot.pause(0.02)
            assert "child line 1" in _log_text(screen), (
                "the child's first line never reached the widget while it was still running"
            )
            # No race: the child cannot have printed this, the sentinel does
            # not exist yet.
            assert "child line 2" not in _log_text(screen)
        finally:
            sentinel.write_text("go", encoding="utf-8")

        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "child line 1" in log
        assert "child line 2" in log


def _mark_broken(refresh: FrozenStateService, tool: Tool) -> None:
    state = refresh.state_of(tool.id)
    _publish(refresh, tool, version=state.version if state else None, broken=True)


def _repair_install(calls: list[tuple[str, bool]]) -> SensitiveInstall:
    def strict(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        calls.append((tool.id, False))
        return InstallOutcome(tool.id, "installed")

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        **extra: object,
    ) -> InstallOutcome:
        if tool.id != "mmdc":
            return strict(
                tool,
                platform,
                runner,
                resolve_tag,
                checksum_policy=checksum_policy,
                tools=tools,
                confirm_sensitive_action=confirm_sensitive_action,
                **extra,
            )
        calls.append((tool.id, extra.get("repair") is True))
        return InstallOutcome(tool.id, "installed")

    return install


async def test_broken_selection_is_installed_with_repair(tmp_path: Path) -> None:
    mmdc = _tool("mmdc")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, mmdc, outdated=False)
    _mark_broken(refresh, mmdc)
    refresh.publish([plan_state(fd, health=Health.MISSING)])
    calls: list[tuple[str, bool]] = []
    inputs = _inputs(
        tools=[mmdc, fd],
        install=_repair_install(calls),
        present=("mmdc",),
        version_refresh=refresh,
        updates=_RecordingUpdateService(),
    )
    app = _host(inputs, [mmdc, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["mmdc", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert [row.disposition for row in screen._rows] == [  # pyright: ignore[reportPrivateUsage]
            Disposition.REPAIR,
            Disposition.INSTALL,
        ]
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
    assert ("mmdc", True) in calls
    assert ("fd", False) in calls


async def test_non_broken_install_omits_the_repair_kwarg(tmp_path: Path) -> None:
    mmdc = _tool("mmdc")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, mmdc, outdated=False)
    _mark_broken(refresh, mmdc)
    calls: list[tuple[str, bool]] = []
    inputs = _inputs(
        tools=[mmdc, fd],
        install=_repair_install(calls),
        present=("mmdc",),
        version_refresh=refresh,
        updates=_RecordingUpdateService(),
    )
    screen, _recorded = await _run_execute(inputs, ["mmdc", "fd"])
    assert screen.finished is True
    assert ("fd", False) in calls


def _install_raises_after_first(exception: Exception) -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        if tool.id == "first":
            return InstallOutcome(tool.id, "installed")
        raise exception

    return install


@pytest.mark.parametrize("exc", [RuntimeError("boom"), OSError("disk full")])
async def test_worker_exception_marks_the_run_failed_and_keeps_done_rows(exc: Exception) -> None:
    tools = [_tool("first"), _tool("second"), _tool("third")]
    inputs = _inputs(tools=tools, install=_install_raises_after_first(exc))
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["first", "second", "third"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.finished
        assert screen.status.text.startswith("Failed")
        assert screen.status.severity == "error"
        assert _results(screen) == {
            "first": "done",
            "second": "crashed",
            "third": "not_attempted",
        }
        assert _not_attempted(screen) == ["third"]
        crashed = [o.detail for o in screen.outcomes or [] if o.result == "crashed"]
        assert crashed == [f"{type(exc).__name__}: {exc}"]


async def test_brew_appearing_mid_session_unblocks_colima(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC AC13 (D-14): a brew that appears mid-session makes a brew-only
    dependency installable without a restart, and the install run gets the
    live platform, not the launch-time one."""
    colima = _tool("colima")
    launch = replace(_PLATFORM, has_brew=False)
    brew: list[str | None] = [None]

    def which(cmd: str) -> str | None:
        return brew[0] if cmd == "brew" else None

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: None,
        platform=launch,
        which=which,
        present=lambda _tool: False,
    )
    service.refresh([colima])
    assert service.platform.has_brew is False
    assert not resolve_methods(colima, service.platform)
    brew[0] = str(tmp_path / "homebrew" / "bin" / "brew")
    service.refresh([colima])
    assert service.platform.has_brew is True
    assert resolve_methods(colima, service.platform)
    seen: list[Platform] = []
    real_execute_plan = installer.execute_screen.execute_plan

    def recording_execute_plan(rows: Sequence[PlanRow], ctx: RunContext) -> list[RowOutcome]:
        seen.append(ctx.platform)
        return real_execute_plan(rows, ctx)

    monkeypatch.setattr(installer.execute_screen, "execute_plan", recording_execute_plan)
    inputs = replace(_inputs(tools=[colima], version_refresh=service), platform=launch)
    app = _host(inputs, [colima])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["colima"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert _plan_prompts(screen)[0].startswith("○ colima")
        assert "not available" not in _head_text(screen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
    assert [platform.has_brew for platform in seen] == [True]


async def test_broken_tool_with_no_reason_is_still_refused(tmp_path: Path) -> None:
    """A hand-built BROKEN state with no reason is refused, not crashed."""
    from installer.version_status import ToolState

    bare = _tool("bare")
    state = pass_state(bare, platform=_PLATFORM, ownership=_brew_ownership(bare), broken=("x",))
    empty = ToolState(
        tool_id=state.tool_id,
        generation=state.generation,
        seq=state.seq,
        health=state.health,
        reasons=(),
        ownership=state.ownership,
        version=state.version,
        skill_hosts=state.skill_hosts,
        receipt=state.receipt,
        removable=state.removable,
        unconfigured=state.unconfigured,
    )
    service = frozen_service(tmp_path)
    service.publish([empty])
    inputs = _inputs(
        tools=[bare],
        present=("bare",),
        version_refresh=service,
        updates=_RecordingUpdateService(),
    )
    app = _host(inputs, [bare])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["bare"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert "will repair" in _plan_prompts(screen)[0]
        assert "bare is broken:" not in _head_text(screen)


# --- Plan-driven screen (plan 20-10, Task 1) -------------------------------


def _plan_prompts(screen: ExecuteScreen) -> list[str]:
    options = screen.query_one("#plan-rows", OptionList)
    return [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]


def _recording(calls: list[str], text: str) -> Callable[[], str]:
    def run() -> str:
        calls.append(text)
        return text

    return run


def _failing_install(captured: list[str]) -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        captured.append(tool.id)
        return InstallOutcome(tool.id, InstallStatus.FAILED)

    return install


def _raising_first_install(captured: list[str]) -> SensitiveInstall:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        captured.append(tool.id)
        raise OSError("disk went away")

    return install


async def test_review_lists_every_row_with_its_disposition() -> None:
    inputs = _inputs(
        states=[
            plan_state(_tool("rg"), health=Health.MISSING),
            plan_state(_tool("fd"), health=Health.OK),
        ]
    )
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        prompts = _plan_prompts(screen)
        assert len(prompts) == 2
        assert prompts[0].startswith("○ rg")
        assert "will install — not installed" in prompts[0]
        assert prompts[1].startswith("✓ fd")
        assert "skipped — already current (r: reinstall)" in prompts[1]
        assert _head_text(screen) == "Install plan — 1 will install, 1 skipped"
        assert _keys_text(screen) == "enter start · r reinstall · up/down move · esc cancel"


async def test_enter_runs_the_plan_and_finishes_with_the_summary_head() -> None:
    captured: list[str] = []
    dismissed: list[list[RowOutcome] | None] = []
    wired: list[str] = []
    inputs = _inputs(
        install=_install_with_output(captured),
        wire_path=_recording(wired, "PATH wired"),
        states=[
            plan_state(_tool("rg"), health=Health.MISSING),
            plan_state(_tool("fd"), health=Health.OK),
        ],
    )
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert captured == ["rg"]
        assert wired == ["PATH wired"]
        assert _head_text(screen) == "Summary — 1 installed, 1 skipped"
        prompts = _plan_prompts(screen)
        assert prompts[0].startswith("✓ rg  installed")
        assert prompts[1] == "✓ fd  skipped — already current"
        assert screen.status.text == "Done. enter or esc returns to the catalog."
        assert _keys_text(screen) == "enter / esc return to catalog"
        assert "Summary — 1 installed, 1 skipped" in _log_text(screen)
        assert "PATH wired" in _log_text(screen)
        await pilot.press("enter")
        await pilot.pause()
    assert len(dismissed) == 1
    value = dismissed[0]
    assert isinstance(value, list)
    assert len(value) == 2
    assert all(isinstance(outcome, RowOutcome) for outcome in value)


async def test_r_toggles_an_installer_owned_current_row_both_ways() -> None:
    rg = _tool("rg")
    inputs = _inputs(tools=[rg], states=[plan_state(rg, health=Health.OK)])
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        options = screen.query_one("#plan-rows", OptionList)
        options.highlighted = options.get_option_index("rg")
        assert options.get_option_at_index(options.highlighted).id == "rg"

        await pilot.press("r")
        assert _plan_prompts(screen) == [
            "✓ rg  will be reinstalled — reinstall requested; r again to undo"
        ]
        assert _head_text(screen) == "Install plan — 1 will be reinstalled"
        assert options.get_option_at_index(options.highlighted).id == "rg"

        await pilot.press("r")
        assert _plan_prompts(screen) == ["✓ rg  skipped — already current (r: reinstall)"]
        assert _head_text(screen) == "Install plan — 1 skipped"
        assert options.get_option_at_index(options.highlighted).id == "rg"


async def test_r_on_an_installed_oh_my_zsh_shows_the_reviewed_chsh_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from installer import engine

    def fake_which(_cmd: str) -> str:
        return "/usr/bin/chsh"

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    omz = Tool(
        id="oh-my-zsh",
        name="Oh My Zsh",
        category="shell",
        cmd="omz",
        methods=(
            Method(
                kind="script",
                params={
                    "url": "https://example.test/install.sh",
                    "shell": "sh",
                    "refuses_existing": True,
                },
            ),
        ),
        post_install=("set_login_shell",),
    )
    calls: list[list[str]] = []

    def refuse_run(command: list[str]) -> None:
        calls.append(command)
        raise CommandError(command, 1, detail="The $ZSH folder already exists")

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        return engine.install_tool(
            tool,
            platform,
            runner=refuse_run,
            resolve_tag=resolve_tag,
            checksum_policy=checksum_policy,
            tools=tools,
            confirm_sensitive_action=confirm_sensitive_action,
            repair=repair,
            present=lambda _tool: True,
        )

    inputs = _inputs(
        tools=[omz],
        install=install,
        present=("oh-my-zsh",),
        states=[plan_state(omz, health=Health.OK)],
    )
    app = _host(inputs, [omz])
    async with app.run_test(size=(100, 30)) as pilot:
        screen_instance = ExecuteScreen(["oh-my-zsh"], inputs)
        app.push_screen(screen_instance)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        screen.query_one("#plan-rows", OptionList).highlighted = 0
        await pilot.press("r", "enter")
        for _ in range(400):
            if "SensitiveActionScreen" in type(app.screen).__name__:
                break
            await pilot.pause()
        assert "SensitiveActionScreen" in type(app.screen).__name__
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.outcomes is not None
        assert screen.outcomes[0].result == "manual"
        assert "chsh -s $(which zsh)" in _log_text(screen)
        assert (
            "its installer refuses to run over an existing install, so it was not re-run."
            in _log_text(screen)
        )
        assert ran_anything(screen.outcomes) is False
        from installer.session import retained

    assert retained(screen.outcomes) == {"oh-my-zsh"}
    assert calls == []


async def test_a_fresh_oh_my_zsh_install_in_the_review_shows_the_reviewed_chsh_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from installer import engine

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    omz = Tool(
        id="oh-my-zsh",
        name="Oh My Zsh",
        category="shell",
        cmd="omz",
        methods=(
            Method(
                kind="script",
                params={"url": "https://example.test/install.sh", "shell": "sh"},
            ),
        ),
        post_install=("set_login_shell",),
    )
    calls: list[list[str]] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        return engine.install_tool(
            tool,
            platform,
            runner=lambda command: calls.append(command),
            resolve_tag=resolve_tag,
            checksum_policy=checksum_policy,
            tools=tools,
            confirm_sensitive_action=confirm_sensitive_action,
            present=lambda _tool: False,
        )

    inputs = _inputs(
        tools=[omz],
        install=install,
        states=[plan_state(omz, health=Health.MISSING, present=False)],
    )
    app = _host(inputs, [omz])
    async with app.run_test(size=(100, 30)) as pilot:
        screen_instance = ExecuteScreen(["oh-my-zsh"], inputs)
        app.push_screen(screen_instance)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if "SensitiveActionScreen" in type(app.screen).__name__:
                break
            await pilot.pause()
        assert screen.outcomes is None or screen.outcomes[0].result == "done", _log_text(screen)
        assert "SensitiveActionScreen" in type(app.screen).__name__, _log_text(screen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.outcomes is not None
        assert screen.outcomes[0].result == "done"
        assert "chsh -s $(which zsh)" in _log_text(screen)
    assert len(calls) == 1
    assert calls[0][0:2] == ["sh", "-c"]


async def test_r_then_enter_reinstalls_with_repair() -> None:
    calls: list[tuple[str, bool]] = []
    dismissed: list[list[RowOutcome] | None] = []
    rg = _tool("rg")

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        calls.append((tool.id, repair))
        return InstallOutcome(tool.id, InstallStatus.INSTALLED)

    inputs = _inputs(tools=[rg], install=install, states=[plan_state(rg, health=Health.OK)])
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        screen.query_one("#plan-rows", OptionList).highlighted = 0
        await pilot.press("r", "enter")
        await _settle_execute(screen, pilot)
        assert calls == [("rg", True)]
        assert _head_text(screen) == "Summary — 1 reinstalled"
        await pilot.press("enter")
        await pilot.pause()

    value = dismissed[0]
    assert isinstance(value, list)
    assert ran_anything(value)


async def test_r_on_a_dnf_owned_row_changes_nothing_and_warns() -> None:
    rg = _tool("rg")
    inputs = _inputs(tools=[rg], states=[plan_state(rg, health=Health.OK, owner="dnf")])
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        options = screen.query_one("#plan-rows", OptionList)
        options.highlighted = options.get_option_index("rg")
        before = _plan_prompts(screen)
        await pilot.press("r")
        assert _plan_prompts(screen) == before == ["✓ rg  skipped — managed by dnf"]
        assert screen.status.text == "rg: r needs a current tool this installer owns."
        assert screen.status.severity == Severity.WARN


async def test_r_on_a_dragged_row_changes_nothing() -> None:
    node = _tool("node")
    mmdc = _tool("mmdc", requires=("node",))
    inputs = _inputs(
        tools=[mmdc, node],
        states=[
            plan_state(mmdc, health=Health.MISSING),
            plan_state(node, health=Health.OK),
        ],
    )
    app = _host(inputs, [mmdc, node])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["mmdc"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        options = screen.query_one("#plan-rows", OptionList)
        options.highlighted = options.get_option_index("node")
        before = _plan_prompts(screen)
        assert any("node" in prompt and "already present" in prompt for prompt in before)
        await pilot.press("r")
        assert _plan_prompts(screen) == before
        assert screen.status.text == "node: r needs a current tool this installer owns."
        assert screen.status.severity == Severity.WARN


async def test_r_is_inert_while_waiting_running_and_finished(tmp_path: Path) -> None:
    waiting_tool = _tool("rg")
    service = held_service(tmp_path / "waiting", [plan_state(waiting_tool, health=Health.MISSING)])
    waiting_inputs = _inputs(tools=[waiting_tool], version_refresh=service)
    waiting_app = _host(waiting_inputs, [waiting_tool])
    async with waiting_app.run_test(size=(80, 20)) as pilot:
        try:
            waiting_app.push_screen(ExecuteScreen(["rg"], waiting_inputs))
            await pilot.pause()
            waiting_screen = waiting_app.screen
            assert isinstance(waiting_screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            waiting_before = (
                _plan_prompts(waiting_screen),
                _head_text(waiting_screen),
                waiting_screen.status.text,
                _keys_text(waiting_screen),
            )
            await pilot.press("r")
            assert (
                _plan_prompts(waiting_screen),
                _head_text(waiting_screen),
                waiting_screen.status.text,
                _keys_text(waiting_screen),
            ) == waiting_before
        finally:
            service.release.set()

    running_started = threading.Event()
    running_release = threading.Event()
    running_calls: list[tuple[str, bool]] = []
    running_tool = _tool("rg")

    def held_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        running_calls.append((tool.id, repair))
        running_started.set()
        assert running_release.wait(timeout=5)
        return InstallOutcome(tool.id, InstallStatus.INSTALLED)

    running_inputs = _inputs(
        tools=[running_tool],
        install=held_install,
        states=[plan_state(running_tool, health=Health.MISSING)],
    )
    running_app = _host(running_inputs, [running_tool])
    async with running_app.run_test(size=(80, 20)) as pilot:
        try:
            running_app.push_screen(ExecuteScreen(["rg"], running_inputs))
            await pilot.pause()
            running_screen = running_app.screen
            assert isinstance(running_screen, ExecuteScreen)
            await pilot.press("enter")
            for _ in range(400):
                if running_started.is_set():
                    break
                await pilot.pause()
            assert running_started.is_set()
            running_before = (
                _plan_prompts(running_screen),
                _head_text(running_screen),
                running_screen.status.text,
                _keys_text(running_screen),
            )
            await pilot.press("r")
            assert (
                _plan_prompts(running_screen),
                _head_text(running_screen),
                running_screen.status.text,
                _keys_text(running_screen),
            ) == running_before
            assert running_calls == [("rg", False)]
        finally:
            running_release.set()
        await _settle_execute(running_screen, pilot)
        finished_before = (
            _plan_prompts(running_screen),
            _head_text(running_screen),
            running_screen.status.text,
            _keys_text(running_screen),
        )
        await pilot.press("r")
        assert (
            _plan_prompts(running_screen),
            _head_text(running_screen),
            running_screen.status.text,
            _keys_text(running_screen),
        ) == finished_before
        assert running_calls == [("rg", False)]


async def test_r_hint_is_omitted_from_the_keys_line_when_no_row_is_eligible() -> None:
    rg = _tool("rg")
    inputs = _inputs(tools=[rg], states=[plan_state(rg, health=Health.MISSING)])
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert _keys_text(screen) == "enter start · up/down move · esc cancel"


def _wide_plan_inputs(count: int) -> tuple[list[Tool], ExecuteInputs]:
    tools = [_tool(f"wide-{index:02d}-abcdefghijklmnop") for index in range(count)]
    long_reason = "the deliberately long reason folds at 80 columns but fits at 120 columns"
    states = [
        plan_state(
            tool,
            health=Health.BROKEN if index % 2 == 0 else Health.MISSING,
            reasons=(long_reason,) if index % 2 == 0 else (),
        )
        for index, tool in enumerate(tools)
    ]
    return tools, _inputs(tools=tools, states=states)


async def test_layout_pins_status_and_keys_to_the_last_two_rows_with_25_rows() -> None:
    tools, inputs = _wide_plan_inputs(25)
    app = _host(inputs, tools)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen([tool.id for tool in tools], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert screen.get_widget_at(2, 18)[0] is screen.status
        assert screen.get_widget_at(2, 19)[0].id == "execute-keys"
        assert screen.query_one("#plan-rows").region.height >= 15
        assert any("\n" in prompt for prompt in _plan_prompts(screen))


async def test_layout_holds_with_the_worst_case_finished_head() -> None:
    categories: tuple[tuple[Disposition, Result], ...] = (
        (Disposition.INSTALL, "done"),
        (Disposition.UPDATE, "done"),
        (Disposition.REPAIR, "done"),
        (Disposition.RECONFIGURE, "done"),
        (Disposition.REINSTALL, "done"),
        (Disposition.SKIP, "skipped"),
        (Disposition.BLOCKED, "blocked"),
        (Disposition.INSTALL, "manual"),
        (Disposition.INSTALL, "failed"),
        (Disposition.INSTALL, "mismatch"),
        (Disposition.INSTALL, "dependency_failed"),
        (Disposition.INSTALL, "not_attempted"),
        (Disposition.INSTALL, "crashed"),
    )
    tools = [_tool(f"worst-{index:03d}") for index in range(130)]
    inputs = _inputs(
        tools=tools, states=[plan_state(tool, health=Health.MISSING) for tool in tools]
    )
    app = _host(inputs, tools)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen([tool.id for tool in tools], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        outcomes = [
            RowOutcome(
                PlanRow(tools[index * 10 + item].id, disposition, ""),
                result,
            )
            for index, (disposition, result) in enumerate(categories)
            for item in range(10)
        ]
        screen.on_install_run_finished(InstallRunFinished(outcomes, None, "", ""))
        await pilot.pause()
        assert screen.query_one("#execute-head").region.height <= 3
        assert screen.get_widget_at(2, 18)[0] is screen.status
        assert screen.get_widget_at(2, 19)[0].id == "execute-keys"


async def test_running_layout_gives_the_log_at_least_six_rows() -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")

    def held_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action, repair
        started.set()
        assert release.wait(timeout=5)
        return InstallOutcome(tool.id, InstallStatus.INSTALLED)

    inputs = _inputs(
        tools=[rg], install=held_install, states=[plan_state(rg, health=Health.MISSING)]
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen([rg.id], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            for _ in range(400):
                if started.is_set():
                    break
                await pilot.pause()
            assert started.is_set()
            log = screen.query_one("#execute-log")
            rows = screen.query_one("#plan-rows", OptionList)
            assert log.region.height >= 6
            assert rows.region.height <= 8
            assert rows.can_focus is False
        finally:
            release.set()
        await _settle_execute(screen, pilot)


async def test_no_plan_row_line_exceeds_78_cells() -> None:
    tools, inputs = _wide_plan_inputs(25)
    app = _host(inputs, tools)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen([tool.id for tool in tools], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        prompts = _plan_prompts(screen)
        assert any("\n" in prompt for prompt in prompts)
        assert all(cell_len(line) <= 78 for prompt in prompts for line in prompt.splitlines())


async def test_resize_refolds_rows_and_keeps_the_cursor() -> None:
    tools, inputs = _wide_plan_inputs(3)
    target_id = tools[2].id
    app = _host(inputs, tools)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen([tool.id for tool in tools], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        options = screen.query_one("#plan-rows", OptionList)
        index = options.get_option_index(target_id)
        assert index is not None
        options.highlighted = index
        before = str(options.get_option_at_index(options.highlighted).prompt)
        assert "\n" in before

        await pilot.resize_terminal(120, 30)
        await pilot.pause()
        options = screen.query_one("#plan-rows", OptionList)
        highlighted = options.highlighted
        assert highlighted is not None
        after = str(options.get_option_at_index(highlighted).prompt)
        assert "\n" not in after
        assert options.get_option_at_index(highlighted).id == target_id

        outcomes = [
            RowOutcome(
                PlanRow(tool.id, Disposition.INSTALL, ""),
                "crashed",
                detail="the deliberately long reason folds at 80 columns but fits at 120 columns",
            )
            for tool in tools
        ]
        screen.on_install_run_finished(InstallRunFinished(outcomes, None, "", ""))
        await pilot.pause()
        options = screen.query_one("#plan-rows", OptionList)
        highlighted = options.highlighted
        assert highlighted is not None
        finished_before = str(options.get_option_at_index(highlighted).prompt)
        assert "\n" not in finished_before

        await pilot.resize_terminal(80, 20)
        await pilot.pause()
        options = screen.query_one("#plan-rows", OptionList)
        highlighted = options.highlighted
        assert highlighted is not None
        finished_after = str(options.get_option_at_index(highlighted).prompt)
        assert "\n" in finished_after
        assert options.get_option_at_index(highlighted).id == target_id


async def test_escape_before_start_dismisses_with_none() -> None:
    dismissed: list[list[RowOutcome] | None] = []
    inputs = _inputs()
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs), dismissed.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert dismissed == [None]


async def test_nothing_selected_shows_the_empty_state_and_enter_does_nothing() -> None:
    dismissed: list[list[RowOutcome] | None] = []
    inputs = _inputs()
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen([], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert _head_text(screen) == "Nothing selected."
        assert _keys_text(screen) == "esc close"
        assert _plan_prompts(screen) == []
        await pilot.press("enter")
        await pilot.pause()
        assert screen.started is False
    assert dismissed == []


async def test_only_skipped_rows_finish_immediately_without_the_engine_or_path_wiring() -> None:
    captured: list[str] = []
    wired: list[str] = []
    verified: list[str] = []
    dismissed: list[list[RowOutcome] | None] = []
    inputs = _inputs(
        install=_install_with_output(captured),
        wire_path=_recording(wired, "PATH wired"),
        verify=_recording(verified, "PATH verified"),
        states=[
            plan_state(_tool("rg"), health=Health.OK),
            plan_state(_tool("fd"), health=Health.OK),
        ],
    )
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert captured == []
        assert wired == []
        assert verified == []
        assert _head_text(screen) == "Summary — 2 skipped"
        assert screen.status.text == "Nothing ran. enter or esc returns to the catalog."
        assert screen.status.severity == Severity.OK
        await pilot.press("enter")
        await pilot.pause()
    value = dismissed[0]
    assert isinstance(value, list)
    assert [outcome.result for outcome in value] == ["skipped", "skipped"]


async def test_enter_rebuilds_the_plan_from_the_latest_publication(tmp_path: Path) -> None:
    captured: list[str] = []
    dismissed: list[list[RowOutcome] | None] = []
    rg = _tool("rg")
    service = frozen_service(tmp_path / "state")
    service.publish([plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert "will install — not installed" in _plan_prompts(screen)[0]
        service.publish([plan_state(rg, health=Health.OK)])
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert captured == []
        assert _head_text(screen) == "Summary — 1 skipped"
        assert _plan_prompts(screen)[0] == "✓ rg  skipped — already current"


async def _wait_for_refresh_calls(
    service: HeldRefreshService, pilot: Pilot[Any], count: int = 1
) -> None:
    for _ in range(40):
        if len(service.calls) >= count:
            return
        await pilot.pause()


async def _wait_for_started(screen: ExecuteScreen, pilot: Pilot[Any]) -> None:
    for _ in range(400):
        if screen.started:
            return
        await pilot.pause()


async def test_enter_with_a_held_refresh_waits_and_starts_nothing(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            assert _plan_prompts(screen) == ["… rg  checking…"]
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            assert _plan_prompts(screen) == ["… rg  checking…"]
            assert screen.status.text == (
                "Waiting for the state check; nothing starts until it finishes. esc cancels."
            )
            assert screen.status.severity == Severity.WARN
            assert _keys_text(screen) == "waiting for the state check · esc cancels the wait"
            assert screen.started is False
            assert captured == []
            assert service.calls == [frozenset({"rg"})]
            await pilot.press("enter")
            await pilot.pause()
            assert service.calls == [frozenset({"rg"})]
        finally:
            service.release.set()


async def test_releasing_the_refresh_rebuilds_the_plan_and_starts_the_run(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            assert screen.started is False
            assert captured == []
            service.release.set()
            await _wait_for_started(screen, pilot)
            assert screen.started is True
            await _settle_execute(screen, pilot)
            assert captured == ["rg"]
            assert screen.outcomes is not None
            assert screen.outcomes[0].row.disposition is Disposition.INSTALL
            assert screen.outcomes[0].row.reason == "not installed"
            assert _head_text(screen) == "Summary — 1 installed"
        finally:
            service.release.set()


async def test_mount_with_checking_rows_joins_the_flight_without_starting(tmp_path: Path) -> None:
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            assert _plan_prompts(screen) == ["… rg  checking…"]
            await _wait_for_refresh_calls(service, pilot)
            assert service.calls == [frozenset({"rg"})]
            service.release.set()
            for _ in range(400):
                if _plan_prompts(screen) == ["○ rg  will install — not installed"]:
                    break
                await pilot.pause()
            assert _plan_prompts(screen) == ["○ rg  will install — not installed"]
            assert screen.started is False
            assert _keys_text(screen) == "enter start · up/down move · esc cancel"
        finally:
            service.release.set()


async def test_unattended_auto_start_waits_like_enter(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(
        tools=[rg], install=_install_with_output(captured), unattended=True, version_refresh=service
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await _wait_for_refresh_calls(service, pilot)
            assert screen.status.text == (
                "Waiting for the state check; nothing starts until it finishes. esc cancels."
            )
            assert screen.started is False
            assert captured == []
            assert service.calls == [frozenset({"rg"})]
            service.release.set()
            await _wait_for_started(screen, pilot)
            assert screen.started is True
            await _settle_execute(screen, pilot)
            assert captured == ["rg"]
        finally:
            service.release.set()


async def test_checking_rows_render_dim_and_enter_waits(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            assert _plan_prompts(screen) == ["… rg  checking…"]
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            assert screen.started is False
            assert screen.status.text == (
                "Waiting for the state check; nothing starts until it finishes. esc cancels."
            )
            assert screen.status.severity == Severity.WARN
            assert _keys_text(screen) == "waiting for the state check · esc cancels the wait"
            service.release.set()
            for _ in range(400):
                if screen.status.text.startswith("State check failed:"):
                    break
                await pilot.pause()
            assert _plan_prompts(screen) == ["… rg  checking…"]
            assert screen.status.text == (
                "State check failed: no state for rg. enter retries · esc closes."
            )
            assert screen.started is False
        finally:
            service.release.set()
    assert captured == []


async def _wait_for_status(screen: ExecuteScreen, prefix: str, pilot: Pilot[Any]) -> None:
    for _ in range(400):
        if screen.status.text.startswith(prefix):
            return
        await pilot.pause()


async def test_esc_during_the_wait_cancels_it_and_keeps_the_selection(tmp_path: Path) -> None:
    captured: list[str] = []
    dismissed: list[list[RowOutcome] | None] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs), dismissed.append)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            before = _plan_prompts(screen)
            assert before == ["… rg  checking…"]
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen
            assert _plan_prompts(screen) == before
            assert screen.status.text == (
                "Wait cancelled; nothing started. enter waits again · esc closes."
            )
            assert screen.status.severity == Severity.WARN
            assert _keys_text(screen) == "enter continue · up/down move · esc cancel"
            assert screen.started is False
            assert captured == []
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not screen
        finally:
            service.release.set()
    assert dismissed == [None]


async def test_a_late_publication_after_esc_starts_nothing(tmp_path: Path) -> None:
    captured: list[str] = []
    dismissed: list[list[RowOutcome] | None] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs), dismissed.append)
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            await pilot.press("escape")
            assert app.screen is screen
            service.release.set()
            for _ in range(40):
                await pilot.pause()
            assert _plan_prompts(screen) == ["… rg  checking…"]
            assert screen.started is False
            assert captured == []
            service.release.clear()
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot, count=2)
            assert service.calls == [frozenset({"rg"}), frozenset({"rg"})]
            assert screen.status.text == (
                "Waiting for the state check; nothing starts until it finishes. esc cancels."
            )
            assert screen.started is False
            service.release.set()
            await _wait_for_started(screen, pilot)
            await _settle_execute(screen, pilot)
            assert screen.started is True
            assert captured == ["rg"]
            assert _head_text(screen) == "Summary — 1 installed"
        finally:
            service.release.set()
    assert dismissed == []


async def test_enter_settles_a_pack_selected_before_its_host_check(tmp_path: Path) -> None:
    captured: list[str] = []
    pack = skill_pack_tool("superpowers")
    probe_started = threading.Event()
    release_probe = threading.Event()

    def skill_probe(_argv: list[str]) -> str:
        probe_started.set()
        release_probe.wait(timeout=10)
        return "not json"

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=lambda _argv: None,
        skill_probe=skill_probe,
        present=lambda _tool: False,
    )
    inputs = _inputs(tools=[pack], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [pack])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen([pack.id], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        for _ in range(40):
            if probe_started.is_set():
                break
            await pilot.pause()
        assert probe_started.is_set()
        assert _plan_prompts(screen) == ["… superpowers  checking…"]
        await pilot.press("enter")
        release_probe.set()
        await _settle_execute(screen, pilot)
        assert "State check failed" not in screen.status.text
        assert captured == ["superpowers"]
        assert _head_text(screen).startswith("Summary —")
        assert all(outcome.result != "not_attempted" for outcome in screen.outcomes or ())


async def test_a_refresh_raising_value_error_settles_with_the_error_and_enter_retries(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    service = held_service(
        tmp_path / "state", [plan_state(rg, health=Health.MISSING)], raising=ValueError("bad cache")
    )
    inputs = _inputs(tools=[rg], version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _wait_for_refresh_calls(service, pilot)
        service.release.set()
        await _wait_for_status(screen, "State check failed:", pilot)
        assert screen.status.text == "State check failed: bad cache. enter retries · esc closes."
        assert screen.status.severity == Severity.ERROR
        assert screen.started is False
        await pilot.press("enter")
        await _wait_for_refresh_calls(service, pilot, count=2)
        assert len(service.calls) == 2
        service.release.set()


async def test_a_late_settle_never_repaints_a_finished_run(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [plan_state(rg, health=Health.MISSING)])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        service.publish([plan_state(rg, health=Health.MISSING)])
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert _head_text(screen) == "Summary — 1 installed"
        assert "✓ rg  installed" in _plan_prompts(screen)[0]
        service.release.set()
        await pilot.pause()
        assert _head_text(screen) == "Summary — 1 installed"
        keys = screen.query_one("#execute-keys", Static)
        assert keys.content == "enter / esc return to catalog"


async def test_a_multi_line_state_check_error_shows_its_first_line_only(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    service = held_service(
        tmp_path / "state",
        [plan_state(rg, health=Health.MISSING)],
        raising=OSError("line one\nline two"),
    )
    inputs = _inputs(tools=[rg], version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _wait_for_refresh_calls(service, pilot)
        service.release.set()
        await _wait_for_status(screen, "State check failed:", pilot)
        assert screen.status.text == "State check failed: line one. enter retries · esc closes."
        assert "\n" not in screen.status.text


async def test_a_failing_refresh_reports_and_enter_retries(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(
        tmp_path / "state",
        [plan_state(rg, health=Health.MISSING)],
        raising=OSError("probe failed"),
    )
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            service.release.set()
            await _wait_for_status(screen, "State check failed:", pilot)
            assert screen.status.text == (
                "State check failed: probe failed. enter retries · esc closes."
            )
            assert screen.status.severity == Severity.ERROR
            assert _plan_prompts(screen) == ["… rg  checking…"]
            assert screen.started is False
            assert captured == []
            service.raising = None
            service.release.clear()
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot, count=2)
            assert service.calls == [frozenset({"rg"}), frozenset({"rg"})]
            assert screen.started is False
            service.release.set()
            await _wait_for_started(screen, pilot)
            await _settle_execute(screen, pilot)
            assert captured == ["rg"]
            assert _head_text(screen) == "Summary — 1 installed"
        finally:
            service.release.set()


async def test_state_check_failed_status_fits_78_cells(tmp_path: Path) -> None:
    rg = _tool("rg")
    service = held_service(
        tmp_path / "state",
        [],
        raising=OSError("x" * 300),
    )
    inputs = _inputs(tools=[rg], version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            service.release.set()
            await _wait_for_status(screen, "State check failed:", pilot)
            assert cell_len(screen.status.text) <= 78
            assert screen.status.text.endswith(". enter retries · esc closes.")
        finally:
            service.release.set()


async def test_a_publication_that_leaves_a_row_unsettled_does_not_start(tmp_path: Path) -> None:
    captured: list[str] = []
    rg = _tool("rg")
    service = held_service(tmp_path / "state", [])
    inputs = _inputs(tools=[rg], install=_install_with_output(captured), version_refresh=service)
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            app.push_screen(ExecuteScreen(["rg"], inputs))
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ExecuteScreen)
            await pilot.press("enter")
            await _wait_for_refresh_calls(service, pilot)
            service.release.set()
            await _wait_for_status(screen, "State check failed:", pilot)
            assert screen.status.text == (
                "State check failed: no state for rg. enter retries · esc closes."
            )
            assert screen.started is False
            assert captured == []
        finally:
            service.release.set()


async def test_mixed_run_keeps_only_the_failing_blocked_and_manual_rows_selected() -> None:
    tools = [_tool(name) for name in ("done", "skipped", "failed", "blocked", "manual", "pending")]
    inputs = _inputs(tools=tools)
    app = _host(inputs, tools)
    async with app.run_test(size=(80, 20)) as pilot:
        app.catalog.selected.update(tool.id for tool in tools)
        app.on_catalog_screen_decided(CatalogScreen.Decided([tool.id for tool in tools]))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        outcomes = [
            RowOutcome(PlanRow("done", Disposition.INSTALL, ""), "done"),
            RowOutcome(PlanRow("skipped", Disposition.SKIP, "already current"), "skipped"),
            RowOutcome(PlanRow("failed", Disposition.INSTALL, ""), "failed"),
            RowOutcome(PlanRow("blocked", Disposition.BLOCKED, "needs dependency"), "blocked"),
            RowOutcome(PlanRow("manual", Disposition.INSTALL, ""), "manual"),
            RowOutcome(PlanRow("pending", Disposition.INSTALL, ""), "not_attempted"),
        ]
        screen.on_install_run_finished(InstallRunFinished(outcomes, None, "", ""))
        await pilot.pause()
        assert screen.status.text == (
            "Failed. Still selected: 4. enter or esc returns to the catalog."
        )
        await pilot.press("enter")
        await pilot.pause()
        assert app.catalog.selected == {"failed", "blocked", "manual", "pending"}


async def test_failed_row_is_red_still_selected_and_the_status_reads_failed() -> None:
    captured: list[str] = []
    rg = _tool("rg")
    inputs = _inputs(
        tools=[rg],
        install=_failing_install(captured),
        states=[plan_state(rg, health=Health.MISSING)],
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert captured == ["rg"]
        assert _plan_prompts(screen)[0].startswith("✖ rg  failed — ")
        assert (
            screen.status.text == "Failed. Still selected: 1. enter or esc returns to the catalog."
        )
        assert screen.status.severity == Severity.ERROR


async def test_a_worker_crash_marks_the_rest_not_attempted_and_keeps_them_selected() -> None:
    captured: list[str] = []
    dismissed: list[list[RowOutcome] | None] = []
    inputs = _inputs(install=_raising_first_install(captured))
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert captured == ["rg"]
        assert (
            screen.status.text == "Failed. Still selected: 2. enter or esc returns to the catalog."
        )
        await pilot.press("enter")
        await pilot.pause()
    value = dismissed[0]
    assert isinstance(value, list)
    assert [outcome.result for outcome in value] == ["crashed", "not_attempted"]


async def test_a_crash_outside_execute_plan_fills_every_row_as_not_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dismissed: list[list[RowOutcome] | None] = []

    def boom(*_args: object, **_kwargs: object) -> list[RowOutcome]:
        raise RuntimeError("boom")

    monkeypatch.setattr(installer.execute_screen, "execute_plan", boom)
    inputs = _inputs()
    app = _host(inputs)
    async with app.run_test(size=(80, 20)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs), dismissed.append)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert (
            screen.status.text == "Failed. Still selected: 2. enter or esc returns to the catalog."
        )
        await pilot.press("enter")
        await pilot.pause()
    value = dismissed[0]
    assert isinstance(value, list)
    assert [outcome.result for outcome in value] == ["not_attempted", "not_attempted"]
    assert [outcome.detail for outcome in value] == ["RuntimeError: boom", "RuntimeError: boom"]


class _PlanUpdateService(_RecordingUpdateService):
    """Script update outcomes while retaining UpdateService's real latch."""

    def __init__(
        self,
        *,
        outcomes: Mapping[str, UpdateOutcome] | None = None,
        errors: Mapping[str, Exception] | None = None,
        before_run: Callable[[UpdateTarget], None] | None = None,
    ) -> None:
        super().__init__()
        self.outcomes = dict(outcomes or {})
        self.errors = dict(errors or {})
        self.before_run = before_run

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.recorded.append(target)
        if self.before_run is not None:
            self.before_run(target)
        if error := self.errors.get(target.tool.id):
            raise error
        if outcome := self.outcomes.get(target.tool.id):
            return outcome
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="updated",
            owner=target.ownership.owner,
        )


def _outcomes_by_id(screen: ExecuteScreen) -> dict[str, RowOutcome]:
    assert screen.outcomes is not None
    return {outcome.row.tool_id: outcome for outcome in screen.outcomes}


async def test_failed_update_row_marks_the_run_failed(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(
        outcomes={"rg": UpdateOutcome("rg", "failed", "brew", detail="upgrade failed")}
    )
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert _outcomes_by_id(screen)["rg"].result == "failed"
    assert "✖ rg" in _log_text(screen)
    assert screen.status.text == "Failed. Still selected: 1. enter or esc returns to the catalog."
    assert screen.status.severity == "error"


async def test_raised_update_row_is_crashed_and_marks_the_run_failed(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(errors={"rg": OSError("permission denied")})
    inputs = _inputs(tools=[rg, fd], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg", "fd"])

    outcomes = _outcomes_by_id(screen)
    assert outcomes["rg"].result == "crashed"
    assert outcomes["rg"].detail == "OSError: permission denied"
    assert outcomes["fd"].result == "not_attempted"
    assert screen.status.text.startswith("Failed.")
    assert updates.in_flight is None


async def test_completed_update_survives_a_run_level_crash(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService()

    def crash_path_wiring() -> str:
        raise RuntimeError("PATH hook crashed")

    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
        wire_path=crash_path_wiring,
    )

    screen, _ = await _run_execute(inputs, ["rg"])

    assert _outcomes_by_id(screen)["rg"].result == "done"
    assert screen.status.text.startswith("Failed.")
    assert "RuntimeError: PATH hook crashed" in _log_text(screen)


async def test_update_outcome_survives_state_invalidation_without_followup_refresh(
    tmp_path: Path,
) -> None:
    class _RefreshWouldFail(_RecordingRefreshService):
        def refresh(self, tools: Sequence[Tool]) -> None:
            self.asked.extend(tool.id for tool in tools)
            raise OSError("version refresh exploded")

    rg = _tool("rg")
    refresh = _RefreshWouldFail(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)

    class _InvalidatingUpdateService(_PlanUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            outcome = super().run(target)
            refresh.invalidate(reason="updated rg")
            return outcome

    updates = _InvalidatingUpdateService()
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert _outcomes_by_id(screen)["rg"].result == "done"
    assert refresh.asked == []
    assert "Summary — 1 updated" in _log_text(screen)


async def test_cancel_mid_update_keeps_completed_rows_and_marks_the_rest_not_attempted(
    tmp_path: Path,
) -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd, outdated=True)

    def block_first(_target: UpdateTarget) -> None:
        started.set()
        assert release.wait(timeout=5)

    updates = _PlanUpdateService(before_run=block_first)
    inputs = _inputs(
        tools=[rg, fd],
        present=("rg", "fd"),
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        await pilot.press("c")
        await pilot.pause()
        release.set()
        await _settle_execute(screen, pilot)

    outcomes = _outcomes_by_id(screen)
    assert [target.tool.id for target in updates.recorded] == ["rg"]
    assert outcomes["rg"].result == "done"
    assert outcomes["fd"].result == "not_attempted"
    assert "Still selected: 1." in screen.status.text


async def test_install_crash_marks_a_later_update_not_attempted(tmp_path: Path) -> None:
    first = _tool("a-first")
    later = _tool("b-update")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, later, outdated=True)
    updates = _PlanUpdateService()

    def install_failure(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        if tool.id == "a-first":
            raise OSError("installer failed")
        return InstallOutcome(tool.id, "installed")

    inputs = _inputs(
        tools=[first, later],
        install=install_failure,
        version_refresh=refresh,
        updates=updates,
    )

    screen, _ = await _run_execute(inputs, ["a-first", "b-update"])

    outcomes = _outcomes_by_id(screen)
    assert outcomes["a-first"].result == "crashed"
    assert outcomes["b-update"].result == "not_attempted"
    assert updates.recorded == []


async def test_in_flight_update_latch_is_blocked_not_failed(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService()
    assert updates.begin("other")
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert updates.recorded == []
    assert _outcomes_by_id(screen)["rg"].result == "blocked"
    assert "update already in flight for other" in _log_text(screen)
    assert "Summary — 1 blocked" in _log_text(screen)
    assert screen.status.text == (
        "Nothing ran. Still selected: 1. enter or esc returns to the catalog."
    )
    assert screen.status.severity == "ok"
    updates.end()


async def test_latch_refusal_keeps_the_update_holder_and_reports_a_blocked_row(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService()
    assert updates.begin("other")
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert updates.in_flight == "other"
    assert _outcomes_by_id(screen)["rg"].result == "blocked"
    assert "update already in flight for other" in _log_text(screen)
    updates.end()


async def test_blocked_update_reason_reaches_finished_row_and_log(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(
        outcomes={
            "rg": UpdateOutcome(
                "rg", "unknown-owner", "unknown", detail="the brew inventory could not be read"
            )
        }
    )
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)
    app = _host(inputs, [rg])

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)

        assert _outcomes_by_id(screen)["rg"].result == "blocked"
        assert "blocked — the brew inventory could not be read" in _plan_prompts(screen)[0]
        assert "blocked — the brew inventory could not be read" in _log_text(screen)
        assert screen.status.severity == "ok"


async def test_blocked_update_reason_appears_only_when_the_row_finishes(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)

    def block(_target: UpdateTarget) -> None:
        started.set()
        assert release.wait(timeout=5)

    updates = _PlanUpdateService(
        outcomes={"rg": UpdateOutcome("rg", "unsupported", "brew", detail="inventory unreadable")},
        before_run=block,
    )
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        await pilot.pause()
        assert "inventory unreadable" not in _log_text(screen)
        assert _plan_prompts(screen)[0].startswith("> rg")
        release.set()
        await _settle_execute(screen, pilot)
        _TEST_LOG_SNAPSHOTS[screen] = _log_text(screen)

    assert "blocked — inventory unreadable" in _log_text(screen)


async def test_blocked_update_without_detail_uses_the_plan_reason(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(outcomes={"rg": UpdateOutcome("rg", "unsupported", "brew")})
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert "blocked — 14.1.0 -> 14.1.1" in _log_text(screen)
    assert "no manager claimed this tool" not in _log_text(screen)


async def test_blocked_update_does_not_trigger_a_version_refresh(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(
        outcomes={"rg": UpdateOutcome("rg", "unsupported", "brew", detail="refused")}
    )
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert refresh.asked == []
    assert _outcomes_by_id(screen)["rg"].result == "blocked"


async def test_outdated_row_without_version_status_still_dispatches_update(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = frozen_service(tmp_path)
    state = plan_state(rg, platform=_PLATFORM, health=Health.OUTDATED, owner="brew")
    refresh.publish([replace(state, version=None)])
    updates = _PlanUpdateService()
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert [target.tool.id for target in updates.recorded] == ["rg"]
    assert _outcomes_by_id(screen)["rg"].row.disposition is Disposition.UPDATE
    assert "Summary — 1 updated" in _log_text(screen)


async def test_update_target_uses_the_plan_captured_owner(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = frozen_service(tmp_path)
    state = plan_state(rg, platform=_PLATFORM, health=Health.OUTDATED, owner="brew")
    ownership = replace(state.ownership, method=None, package=None)
    refresh.publish([replace(state, ownership=ownership, version=None)])
    updates = _PlanUpdateService()
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert _outcomes_by_id(screen)["rg"].result == "done"
    assert len(updates.recorded) == 1
    assert updates.recorded[0].ownership == ownership
    assert updates.recorded[0].ownership.owner == "brew"


async def test_successful_update_is_named_in_summary_and_outcome_row(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=_PlanUpdateService(),
    )

    screen, _ = await _run_execute(inputs, ["rg"])

    assert "Summary — 1 updated" in _log_text(screen)
    assert "✓ rg  updated" in _log_text(screen)


async def test_successful_outdated_update_line_carries_outcome_extras(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(
        outcomes={
            "rg": UpdateOutcome(
                "rg",
                "updated",
                "brew",
                replayed_globals=("claude",),
                cleanup_warnings=("old binary left behind",),
                postinstall_warning="hook warned",
                detail="pnpm globals replay failed: boom",
            )
        }
    )
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)

    screen, _ = await _run_execute(inputs, ["rg"])

    assert (
        "rg updated — replayed claude; old binary left behind; hook warned; "
        "pnpm globals replay failed: boom"
    ) in _log_text(screen)


async def test_successful_update_without_a_new_version_still_reports_updated(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    refresh = frozen_service(tmp_path)
    state = plan_state(rg, platform=_PLATFORM, health=Health.OUTDATED, owner="brew")
    refresh.publish([replace(state, version=None)])
    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=_PlanUpdateService(),
    )

    screen, _ = await _run_execute(inputs, ["rg"])

    assert _outcomes_by_id(screen)["rg"].result == "done"
    assert "✓ rg  updated" in _log_text(screen)
    assert "now " not in _log_text(screen)


async def test_failed_update_does_not_stop_a_later_install_row(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService(
        outcomes={"rg": UpdateOutcome("rg", "failed", "brew", detail="upgrade failed")}
    )
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        present=("rg",),
        version_refresh=refresh,
        updates=updates,
    )

    screen, _ = await _run_execute(inputs, ["rg", "fd"])

    outcomes = _outcomes_by_id(screen)
    assert outcomes["rg"].result == "failed"
    assert outcomes["fd"].result == "done"
    assert captured == ["fd"]


async def test_update_dispatch_does_not_open_a_confirmation_prompt(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _PlanUpdateService()
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)
    app = _host(inputs, [rg])

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert app.screen is screen

    assert [target.tool.id for target in updates.recorded] == ["rg"]


async def test_update_marker_establishes_the_silence_indicator(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)

    def block(_target: UpdateTarget) -> None:
        started.set()
        assert release.wait(timeout=5)

    updates = _PlanUpdateService(before_run=block)
    inputs = _inputs(tools=[rg], present=("rg",), version_refresh=refresh, updates=updates)
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        assert "-- updating --" in _log_text(screen)
        await pilot.pause(SILENCE_SECONDS + 0.25)
        assert "still running; waiting for output" in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_finished_update_row_does_not_clear_the_next_rows_indicator(
    tmp_path: Path,
) -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd, outdated=True)

    def block_second(target: UpdateTarget) -> None:
        if target.tool.id == "fd":
            started.set()
            assert release.wait(timeout=5)

    updates = _PlanUpdateService(before_run=block_second)
    inputs = _inputs(
        tools=[rg, fd],
        present=("rg", "fd"),
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        screen.post_message(RowFinished(RowOutcome(PlanRow("rg", Disposition.UPDATE, ""), "done")))
        await pilot.pause()
        await pilot.pause(SILENCE_SECONDS + 0.25)
        assert "-- still running; waiting for output --" in _log_text(screen)
        assert "fd" in _log_text(screen).splitlines()[-1]
        release.set()
        await _settle_execute(screen, pilot)


async def test_receipt_drift_is_reviewed_as_repair_and_not_update(tmp_path: Path) -> None:
    mmdc = _tool("mmdc")
    refresh = frozen_service(tmp_path)
    state = plan_state(
        mmdc,
        platform=_PLATFORM,
        health=Health.BROKEN,
        owner="installer",
        reasons=("changed since install",),
        version=_outdated_status("mmdc", outdated=True),
    )
    refresh.publish([state])
    calls: list[tuple[str, bool]] = []
    updates = _PlanUpdateService()
    inputs = _inputs(
        tools=[mmdc],
        install=_repair_install(calls),
        present=("mmdc",),
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [mmdc])

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["mmdc"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert (
            "will repair — changed since install; the file is replaced" in _plan_prompts(screen)[0]
        )
        assert "will update" not in _head_text(screen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)

    assert ("mmdc", True) in calls
    assert updates.recorded == []
    assert _outcomes_by_id(screen)["mmdc"].row.disposition is Disposition.REPAIR


async def test_plan_head_counts_install_update_and_skip_rows(tmp_path: Path) -> None:
    install_tool = _tool("install-me")
    update_tool = _tool("update-me")
    current_tool = _tool("current")
    refresh = frozen_service(tmp_path)
    refresh.publish(
        [
            plan_state(install_tool, health=Health.MISSING),
            plan_state(update_tool, health=Health.OUTDATED, owner="brew"),
            plan_state(current_tool, health=Health.OK, owner="brew"),
        ]
    )
    inputs = _inputs(
        tools=[install_tool, update_tool, current_tool],
        version_refresh=refresh,
        updates=_PlanUpdateService(),
    )
    app = _host(inputs, list(inputs.catalog))

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["install-me", "update-me", "current"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert _head_text(screen) == "Install plan — 1 will install, 1 will update, 1 skipped"
        prompts = _plan_prompts(screen)
        assert any("install-me" in prompt and "will install" in prompt for prompt in prompts)
        assert any("update-me" in prompt and "will update" in prompt for prompt in prompts)
        assert any("current" in prompt and "skipped" in prompt for prompt in prompts)


async def test_update_row_transitions_from_review_to_running_to_finished(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)

    def block(_target: UpdateTarget) -> None:
        started.set()
        assert release.wait(timeout=5)

    inputs = _inputs(
        tools=[rg],
        present=("rg",),
        version_refresh=refresh,
        updates=_PlanUpdateService(before_run=block),
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert "will update" in _plan_prompts(screen)[0]
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        assert started.is_set()
        assert _plan_prompts(screen)[0].startswith("> rg")
        release.set()
        await _settle_execute(screen, pilot)
        _TEST_LOG_SNAPSHOTS[screen] = _log_text(screen)

    assert "✓ rg  updated" in _log_text(screen)
    assert _outcomes_by_id(screen)["rg"].result == "done"
