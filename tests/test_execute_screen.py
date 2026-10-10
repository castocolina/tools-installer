"""ExecuteScreen behaviour, plus characterisation of the worker-to-modal primitive.

The first tests pin MECHANISM=A (plan 13-01). The rest drive the in-app install
screen: a fake `install` that emits through the injected runner, never a real
package manager or shell rc file.
"""

import shutil
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import ClassVar

import pytest
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.pilot import Pilot
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Label, ListItem, ListView, Static

import installer.execute_screen
from installer.doctor import DoctorReport
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import InstallStatus
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
    InstallToolFinished,
    UpdateToolFinished,
    sanitize_log_line,
)
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool
from installer.ownership import ManagerInventory, ManagerOwnership, OwnershipCandidate
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import CommandError, Runner, StreamingRunner
from installer.session import SensitiveInstall, summarize
from installer.uninstall import SweepResult
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import VersionRefreshService, VersionStatus
from installer.versions import TagResolver
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs


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
    installed: Callable[[Tool], bool] | None = None,
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
        installed=installed if installed is not None else (lambda _tool: False),
        install=install if install is not None else _install_with_output([]),
        unattended=unattended,
        version_refresh=version_refresh,
        updates=updates,
        now=now,
    )


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
    installed: Mapping[str, bool] = {tool.id: False for tool in catalog}
    return UnifiedApp(
        catalog,
        installed,
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


def _log_text(screen: ExecuteScreen) -> str:
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
        assert app.install_summary == screen.summary


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


async def test_a_broken_batch_still_finishes_with_an_empty_summary() -> None:
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
        assert screen.summary is not None
        assert screen.summary.installed == ()
        assert screen.summary.failed == ()
        assert screen.summary.already == ()
        assert "disk full" in _log_text(screen)
        assert screen.not_attempted == ["rg", "fd"]


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
        assert "fd" in head
        assert "2" in head
        assert "enter" in head.lower()
        assert "esc" in head.lower()
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
        assert "enter" in started_with_head[0].lower()
        await _settle_execute(screen, pilot)


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


async def test_retrying_a_mismatch_installs_twice_and_summarizes_installed() -> None:
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
        assert screen.summary is not None
        assert screen.summary.installed == ("rg",)
        assert screen.summary.mismatched == ()


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
        assert screen.summary is not None
        assert screen.summary.mismatched == ("rg",)
        assert screen.summary.installed == ()


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
        assert screen.summary is not None
        assert screen.summary.installed == ("rg",)


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
        assert screen.summary is not None
        assert "rg" in screen.summary.mismatched


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
        assert screen.summary is not None
        assert screen.summary.mismatched == ("rg",)
        assert screen.summary.installed == ()


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


def _progress_text(screen: ExecuteScreen) -> str:
    return str(screen.query_one("#execute-progress", Static).render())


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


async def test_progress_lists_every_resolved_tool_as_pending_before_start() -> None:
    tools = [_tool("rg"), _tool("fd"), _tool("bat")]
    inputs = _inputs(tools=tools)
    app = _host(inputs, tools)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd", "bat"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        progress = _progress_text(screen)
        assert progress.index("rg") < progress.index("fd") < progress.index("bat")
        assert progress.count("○") == 3
        assert screen.started is False


async def test_progress_pending_count_falls_as_each_tool_finishes() -> None:
    rg_done = threading.Event()
    fd_started = threading.Event()
    fd_release = threading.Event()
    bat_started = threading.Event()
    bat_release = threading.Event()
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
            return InstallOutcome(tool.id, "failed")
        bat_started.set()
        assert bat_release.wait(timeout=5)
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
        assert rg_done.is_set() and fd_started.is_set()
        after_first = _progress_text(screen)
        assert after_first.count("○") == 2
        assert "●" in after_first
        fd_release.set()
        for _ in range(400):
            if bat_started.is_set():
                break
            await pilot.pause()
        await pilot.pause()
        assert bat_started.is_set()
        after_second = _progress_text(screen)
        assert after_second.count("○") == 1
        assert after_second.count("○") < after_first.count("○")
        bat_release.set()
        await _settle_execute(screen, pilot)
        final = _progress_text(screen)
        assert final.count("○") == 0
        assert captured == ["rg", "fd", "bat"]


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
        assert screen.summary is not None
        assert screen.summary.failed == ("fd",)
        assert screen.summary.installed == ("rg", "bat")


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
        assert screen.not_attempted == ["bat"]
        assert screen.summary is not None
        assert screen.summary.installed == ("rg", "fd")
        log = _log_text(screen)
        assert "bat" in log
        assert "not attempted" in log.lower() or "never attempted" in log.lower()


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
        assert screen.not_attempted == []


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


async def test_execute_keys_names_escape_c_and_ctrl_c_with_distinct_meanings() -> None:
    inputs = _inputs()
    app = _host(inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        keys = _keys_text(screen).lower()
        assert "esc" in keys
        assert (
            "c " in keys or keys.endswith(" c") or "· c " in keys or ", c " in keys or " c " in keys
        )
        assert "ctrl+c" in keys
        assert "leave" in keys or "does not" in keys
        assert "between" in keys or "in-flight" in keys or "in flight" in keys
        assert "half-installed" in keys or "half installed" in keys


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
        assert "skipped — dependency failed: fd" in log or "skipped -- dependency failed: fd" in log
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
        summary_at = log.index("Installed:")
        fail_at = log.index("disk exploded")
        skip_at = log.lower().index("skipped")
        handoff_at = log.index("After leaving the installer")
        post_install_at = log.index("chsh -s /bin/zsh")
        warn_at = log.index("postinstall warning")
        verify_at = log.index("sha256")
        path_at = log.index("PATH wired")
        audit_at = log.index("PATH verified")
        assert summary_at < fail_at < skip_at < handoff_at < post_install_at < warn_at < verify_at
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


class _RecordingRefreshService(VersionRefreshService):
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

    def refresh(self, tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        statuses: dict[str, VersionStatus] = {}
        for tool in tools:
            self.asked.append(tool.id)
            self._ownership[tool.id] = (  # pyright: ignore[reportPrivateUsage]
                self.epoch,
                _brew_ownership(tool),
            )
            status = _outdated_status(tool.id, outdated=True)
            self._statuses[tool.id] = status  # pyright: ignore[reportPrivateUsage]
            statuses[tool.id] = status
        return statuses


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


def _seed_refresh(
    refresh: VersionRefreshService,
    tool: Tool,
    *,
    outdated: bool | None | object = ...,
    ownership: bool = True,
) -> None:
    if ownership:
        refresh._ownership[tool.id] = (  # pyright: ignore[reportPrivateUsage]
            refresh.epoch,
            _brew_ownership(tool),
        )
    if outdated is not ...:
        refresh._statuses[tool.id] = _outdated_status(  # pyright: ignore[reportPrivateUsage]
            tool.id, outdated=outdated if isinstance(outdated, bool) or outdated is None else True
        )


async def _run_execute(
    inputs: ExecuteInputs, ids: list[str]
) -> tuple[ExecuteScreen, _RecordingUpdateService | None]:
    app = _host(inputs, list(inputs.catalog))
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(ids, inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
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
        installed=lambda tool: tool.id == "rg",
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
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg", "fd"])
    assert screen.finished is True
    assert recorded is not None
    assert recorded.recorded == []
    assert captured == ["fd"]


async def test_missing_version_status_still_dispatches_an_outdated_update(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, ownership=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg", "fd"])
    assert screen.finished is True
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["rg"]
    assert captured == ["fd"]


async def test_missing_ownership_snapshot_refreshes_then_dispatches_outdated_update(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    refresh._statuses[rg.id] = _outdated_status(  # pyright: ignore[reportPrivateUsage]
        rg.id, outdated=True
    )
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg", "fd"])
    assert screen.finished is True
    assert refresh.asked == ["rg", "rg"]
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["rg"]


async def test_refresh_failure_on_missing_ownership_reports_error_not_a_clean_run(
    tmp_path: Path,
) -> None:
    """The pre-dispatch blocking refresh (missing ownership snapshot) must be
    wrapped like every other worker I/O call: an OSError from it is a reported
    update error, never a silently-clean run with the update skipped."""
    rg = _tool("rg")
    captured: list[str] = []

    class _RaisingRefreshService(_RecordingRefreshService):
        def refresh(self, tools: Sequence[Tool]) -> dict[str, VersionStatus]:
            self.asked.extend(tool.id for tool in tools)
            raise OSError("disk full")

    refresh = _RaisingRefreshService(tmp_path / "versions.json")
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, list(inputs.catalog))
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert screen.finished is True
        assert refresh.asked == ["rg"]
        recorded = updates
        assert recorded is not None
        assert recorded.recorded == []
        assert "disk full" in _log_text(screen)
        assert screen.status.text != ""


async def test_only_outdated_selection_still_starts_and_dispatches(tmp_path: Path) -> None:
    rg = _tool("rg")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    screen, recorded = await _run_execute(inputs, ["rg"])
    assert screen.started is True
    assert screen.finished is True
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["rg"]
    assert captured == []


async def test_in_flight_latch_skips_outdated_update_and_keeps_the_holder(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    assert updates.begin("other") is True
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, list(inputs.catalog))
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        recorded = updates
        assert screen.finished is True
        assert recorded is not None
        assert recorded.recorded == []
        assert updates.in_flight == "other"
        assert "update already in flight for other" in _log_text(screen)
    assert captured == ["fd"]


async def test_nothing_updates_before_the_confirm_keypress(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
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
        installed=lambda tool: tool.id == "rg",
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
        installed=lambda tool: tool.id == "rg",
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


def test_update_dispatch_opens_no_confirm_prompt_of_its_own() -> None:
    import inspect

    from installer import execute_screen as execute_module

    source = Path(execute_module.__file__).read_text(encoding="utf-8")
    uncommented = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert uncommented.count("push_screen_wait(") == 1
    # Structural gate: read the method body itself, not a public wrapper.
    run_updates = inspect.getsource(
        ExecuteScreen._run_updates  # pyright: ignore[reportPrivateUsage]
    )
    assert "ask_from_worker" not in run_updates
    assert "push_screen_wait" not in run_updates


def _assert_head_hint(head: str) -> None:
    lowered = head.lower()
    assert "enter start" in lowered
    assert "esc cancel" in lowered


async def test_preflight_head_names_install_and_outdated_update_counts_before_any_keypress(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        head = _head_text(screen)
        _assert_head_hint(head)
        lowered = head.lower()
        assert "install" in lowered
        assert "update" in lowered
        assert "1" in head
        assert "Install 0" not in head
        progress = _progress_text(screen)
        assert "rg" in progress
        assert "fd" in progress
        assert "update" in progress.lower()
        assert "[pending]" in progress
        assert screen.started is False
        assert updates.recorded == []
        for _ in range(10):
            await pilot.pause()
        assert screen.started is False
        assert updates.recorded == []


async def test_update_only_outdated_preflight_does_not_read_as_zero_work(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        head = _head_text(screen)
        _assert_head_hint(head)
        assert "Install 0" not in head
        assert "0" not in head.split("?")[0]
        assert "update" in head.lower()
        progress = _progress_text(screen)
        assert "rg" in progress
        assert "update" in progress.lower()
        assert "[pending]" in progress
        assert screen.started is False
        assert updates.recorded == []


async def test_queued_outdated_update_progress_row_leaves_pending_when_update_returns(
    tmp_path: Path,
) -> None:
    first_started = threading.Event()
    first_release = threading.Event()
    second_started = threading.Event()
    second_release = threading.Event()
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd, outdated=True)

    class _GatedUpdateService(_RecordingUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            if target.tool.id == "rg":
                first_started.set()
                assert first_release.wait(timeout=5)
            else:
                second_started.set()
                assert second_release.wait(timeout=5)
            return super().run(target)

    updates = _GatedUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda _tool: True,
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        before = _progress_text(screen)
        assert before.count("[pending]") >= 2
        await pilot.press("enter")
        for _ in range(400):
            if first_started.is_set():
                break
            await pilot.pause()
        assert first_started.is_set()
        first_release.set()
        for _ in range(400):
            if second_started.is_set():
                break
            await pilot.pause()
        await pilot.pause()
        assert second_started.is_set()
        mid = _progress_text(screen)
        rg_line = next(line for line in mid.splitlines() if "rg" in line)
        fd_line = next(line for line in mid.splitlines() if "fd" in line)
        assert "[pending]" not in rg_line
        assert "[pending]" in fd_line
        second_release.set()
        await _settle_execute(screen, pilot)
        final = _progress_text(screen)
        assert "[pending]" not in final
        assert [target.tool.id for target in updates.recorded] == ["rg", "fd"]


async def test_undisturbed_outdated_run_dispatches_exactly_the_disclosed_update_ids(
    tmp_path: Path,
) -> None:
    """FIXTURE A — equality of disclosed and dispatched update ids."""
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd, ownership=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda _tool: True,
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        head = _head_text(screen)
        progress = _progress_text(screen)
        disclosed = [tool.id for tool in screen._to_update]  # pyright: ignore[reportPrivateUsage]
        assert disclosed == ["rg", "fd"]
        assert "2" in head
        assert "update" in head.lower()
        for tool_id in disclosed:
            assert tool_id in progress
            line = next(row for row in progress.splitlines() if tool_id in row)
            assert "update" in line.lower()
            assert "[pending]" in line
        assert screen.started is False
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        dispatched = [target.tool.id for target in updates.recorded]
        assert dispatched == disclosed


async def test_cancel_mid_update_tail_sweeps_unreached_outdated_row_to_skipped(
    tmp_path: Path,
) -> None:
    """FIXTURE B — skip reporting only; dispatched is a strict subset."""
    first_started = threading.Event()
    first_release = threading.Event()
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd, outdated=True)

    class _GatedUpdateService(_RecordingUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            if target.tool.id == "rg":
                first_started.set()
                assert first_release.wait(timeout=5)
            return super().run(target)

    updates = _GatedUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda _tool: True,
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        disclosed = [tool.id for tool in screen._to_update]  # pyright: ignore[reportPrivateUsage]
        await pilot.press("enter")
        for _ in range(400):
            if first_started.is_set():
                break
            await pilot.pause()
        assert first_started.is_set()
        await pilot.press("c")
        await pilot.pause()
        first_release.set()
        await _settle_execute(screen, pilot)
        dispatched = [target.tool.id for target in updates.recorded]
        assert dispatched == ["rg"]
        assert set(dispatched).issubset(set(disclosed))
        assert "fd" in screen.not_attempted
        final = _progress_text(screen)
        fd_line = next(line for line in final.splitlines() if "fd" in line)
        assert "[pending]" not in fd_line
        assert "not attempted" in fd_line
        assert "[pending]" not in final


async def test_latch_refused_outdated_update_row_is_swept_to_skipped(tmp_path: Path) -> None:
    """FIXTURE C — latch refusal skip reporting; run is never called."""
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    assert updates.begin("other") is True
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda tool: tool.id == "rg",
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
        await _settle_execute(screen, pilot)
        assert updates.recorded == []
        assert "rg" in screen.not_attempted
        final = _progress_text(screen)
        rg_line = next(line for line in final.splitlines() if "rg" in line)
        assert "[pending]" not in rg_line
        assert "not attempted" in rg_line
        assert updates.in_flight == "other"


async def test_error_before_outdated_update_tail_sweeps_pending_update_rows(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()

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

    inputs = _inputs(
        tools=[rg, fd],
        install=boom,
        installed=lambda tool: tool.id == "rg",
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
        await _settle_execute(screen, pilot)
        assert screen.finished is True
        assert updates.recorded == []
        assert "rg" in screen.not_attempted
        final = _progress_text(screen)
        assert "[pending]" not in final
        rg_line = next(line for line in final.splitlines() if "rg" in line)
        assert "not attempted" in rg_line


class _BlockedUpdateService(_RecordingUpdateService):
    def __init__(self, *, detail: str = "the brew inventory could not be read") -> None:
        super().__init__()
        self._detail = detail

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.recorded.append(target)
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="unknown-owner",
            owner="unknown",
            detail=self._detail,
        )


class _RaisingUpdateService(_RecordingUpdateService):
    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.recorded.append(target)
        raise OSError("permission denied")


async def test_blocked_update_reason_reaches_the_post_run_log(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _BlockedUpdateService(detail="the brew inventory could not be read")
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
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
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "cannot update rg: the brew inventory could not be read" in log
        assert screen.summary is not None
        assert screen.summary.failed == ()
        assert screen.summary.mismatched == ()
        assert screen.summary.dependency_failed == ()
        assert captured == ["fd"]


async def test_blocked_update_without_detail_falls_back_to_no_manager_claimed(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _BlockedUpdateService(detail="")
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "cannot update rg: no manager claimed this tool" in log


async def test_blocked_update_reason_is_absent_from_the_log_until_the_run_finishes(
    tmp_path: Path,
) -> None:
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)

    class _GatedBlocked(_BlockedUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            started.set()
            assert release.wait(timeout=5)
            return super().run(target)

    updates = _GatedBlocked()
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda tool: tool.id == "rg",
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
        await pilot.pause()
        assert "cannot update" not in _log_text(screen)
        release.set()
        await _settle_execute(screen, pilot)
        assert "cannot update rg: the brew inventory could not be read" in _log_text(screen)
        assert screen.summary is not None
        assert screen.summary.failed == ()


async def test_blocked_update_error_from_run_live_is_reported(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RaisingUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "permission denied" in log
        assert screen.summary is not None
        assert screen.summary.failed == ()
        assert screen.summary.mismatched == ()


async def test_blocked_update_latch_refusal_reuses_the_in_flight_sentence(tmp_path: Path) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _RecordingUpdateService()
    assert updates.begin("other") is True
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
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
        await _settle_execute(screen, pilot)
        assert updates.recorded == []
        log = _log_text(screen)
        assert "update already in flight for other" in log
        assert screen.summary is not None
        assert screen.summary.failed == ()
        assert captured == ["fd"]


class _SuccessUpdateService(_RecordingUpdateService):
    def __init__(
        self,
        *,
        replayed_globals: tuple[str, ...] = (),
        cleanup_warnings: tuple[str, ...] = (),
        postinstall_warning: str | None = None,
        detail: str = "",
    ) -> None:
        super().__init__()
        self._replayed_globals = replayed_globals
        self._cleanup_warnings = cleanup_warnings
        self._postinstall_warning = postinstall_warning
        self._detail = detail

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.recorded.append(target)
        return UpdateOutcome(
            tool_id=target.tool.id,
            status="updated",
            owner=target.ownership.owner,
            detail=self._detail,
            postinstall_warning=self._postinstall_warning,
            replayed_globals=self._replayed_globals,
            cleanup_warnings=self._cleanup_warnings,
        )


class _VersionedRefreshService(_RecordingRefreshService):
    def __init__(
        self,
        cache_path: Path,
        *,
        installed: str | None = "14.1.1",
        raise_error: OSError | None = None,
    ) -> None:
        super().__init__(cache_path)
        self._installed = installed
        self._raise_error = raise_error

    def refresh(self, tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        if self._raise_error is not None:
            self.asked.extend(tool.id for tool in tools)
            raise self._raise_error
        statuses: dict[str, VersionStatus] = {}
        for tool in tools:
            self.asked.append(tool.id)
            self._ownership[tool.id] = (  # pyright: ignore[reportPrivateUsage]
                self.epoch,
                _brew_ownership(tool),
            )
            status = VersionStatus(
                tool_id=tool.id,
                installed=self._installed,
                latest=self._installed,
                outdated=False,
                stale=False,
                source="brew",
            )
            self._statuses[tool.id] = status  # pyright: ignore[reportPrivateUsage]
            statuses[tool.id] = status
        return statuses


async def test_successful_outdated_update_is_named_in_the_post_run_log(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _VersionedRefreshService(tmp_path / "versions.json", installed="14.1.1")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _SuccessUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "updated rg now 14.1.1" in log
        assert refresh.asked == ["rg"]


async def test_successful_outdated_update_without_a_new_version_still_reports(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    refresh = _VersionedRefreshService(tmp_path / "versions.json", installed=None)
    _seed_refresh(refresh, rg, outdated=True)
    updates = _SuccessUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "updated rg" in log
        assert "now " not in log.split("updated rg", 1)[1].splitlines()[0]


async def test_successful_outdated_update_line_carries_outcome_extras(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _VersionedRefreshService(tmp_path / "versions.json", installed="14.1.1")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _SuccessUpdateService(
        replayed_globals=("claude", "opencode"),
        cleanup_warnings=("left leftover",),
        postinstall_warning="hook warned",
        detail="brew upgraded rg",
    )
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "updated rg now 14.1.1" in log
        assert "replayed claude, opencode" in log
        assert "left leftover" in log
        assert "hook warned" in log
        assert "brew upgraded rg" in log


async def test_blocked_update_does_not_reprobe_the_version_cache(tmp_path: Path) -> None:
    rg = _tool("rg")
    refresh = _VersionedRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    updates = _BlockedUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert refresh.asked == []
        assert "cannot update rg" in _log_text(screen)


async def test_refresh_oserror_after_outdated_update_still_produces_the_report(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    refresh = _VersionedRefreshService(
        tmp_path / "versions.json",
        raise_error=OSError("probe timed out"),
    )
    _seed_refresh(refresh, rg, outdated=True)
    updates = _SuccessUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda tool: tool.id == "rg",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [rg])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert screen.finished is True
        assert "updated rg" in log
        assert "now " not in log.split("updated rg", 1)[1].splitlines()[0]


async def test_update_section_is_silent_when_no_outdated_updates_were_queued(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    fd = _tool("fd")
    captured: list[str] = []
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=False)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[rg, fd],
        install=_install_with_output(captured),
        installed=lambda tool: tool.id == "rg",
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
        await _settle_execute(screen, pilot)
        log = _log_text(screen)
        assert "Updates" not in log
        assert "updated " not in log
        assert updates.recorded == []
        assert captured == ["fd"]


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
        screen.on_install_tool_finished(InstallToolFinished("rg", InstallStatus.INSTALLED))
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
        screen.on_install_tool_finished(InstallToolFinished("rg", InstallStatus.INSTALLED))
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
        screen.on_install_run_finished(InstallRunFinished(summarize([]), [], [], "", "", None))
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


async def test_silent_update_establishes_in_flight_tool_via_marker(tmp_path: Path) -> None:
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)

    class _BlockingUpdateService(_RecordingUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            started.set()
            assert release.wait(timeout=5)
            return super().run(target)

    updates = _BlockingUpdateService()
    inputs = _inputs(
        tools=[rg],
        installed=lambda _tool: True,
        version_refresh=refresh,
        updates=updates,
        now=clock,
    )
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
        assert "-- updating --" in _log_text(screen)

        clock.value += SILENCE_SECONDS
        screen._check_output_silence()  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        last_line = _log_text(screen).splitlines()[-1]
        assert "rg" in last_line
        assert "still running; waiting for output" in last_line

        release.set()
        await _settle_execute(screen, pilot)


async def test_stale_update_terminal_message_for_another_tool_does_not_clear_in_flight(
    tmp_path: Path,
) -> None:
    """The update half of the id guard, mirroring the install half at
    `test_stale_terminal_message_for_another_tool_does_not_clear_in_flight`.

    Plan 02's criterion is that BOTH `on_install_tool_finished` and
    `on_update_tool_finished` clear the in-flight tool only when
    `message.tool_id` is the tool currently in flight, but the regression test
    existed only for the install path -- branch coverage reported the update
    comparison as never evaluating False, so removing the `if` from
    `on_update_tool_finished` left the suite green.
    """
    clock = _FakeClock()
    started = threading.Event()
    release = threading.Event()
    rg = _tool("rg")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, fd, outdated=True)

    class _SecondUpdateBlocks(_RecordingUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            if target.tool.id == "fd":
                started.set()
                assert release.wait(timeout=5)
            return super().run(target)

    updates = _SecondUpdateBlocks()
    inputs = _inputs(
        tools=[rg, fd],
        installed=lambda _tool: True,
        version_refresh=refresh,
        updates=updates,
        now=clock,
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
        for _ in range(400):
            if screen._in_flight == "fd":  # pyright: ignore[reportPrivateUsage]
                break
            await pilot.pause()
        assert screen._in_flight == "fd"  # pyright: ignore[reportPrivateUsage]

        # A stale/delayed terminal message for rg -- whose update already
        # returned -- must not clear fd's silence window.
        screen.on_update_tool_finished(UpdateToolFinished("rg", "done"))
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
    already attributed by attributed_install) rather than a separately
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
        # set_tool-attributed by attributed_install. A freshly constructed one
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


async def test_current_only_selection_says_already_current_not_install_zero(
    tmp_path: Path,
) -> None:
    wezterm = _tool("wezterm")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, wezterm, outdated=False)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[wezterm],
        installed=lambda tool: tool.id == "wezterm",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [wezterm])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["wezterm"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        prompt = screen._preflight_prompt()  # pyright: ignore[reportPrivateUsage]
        assert "wezterm already current — nothing to do." in prompt
        assert "Install 0 tools" not in prompt
        assert "wezterm [already current]" in _progress_text(screen)


async def test_outdated_selected_tool_stays_an_update_target(tmp_path: Path) -> None:
    wezterm = _tool("wezterm")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, wezterm, outdated=True)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[wezterm],
        installed=lambda tool: tool.id == "wezterm",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [wezterm])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["wezterm"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert [tool.id for tool in screen._to_update] == ["wezterm"]  # pyright: ignore[reportPrivateUsage]
        assert screen._preflight_prompt().startswith("Update 1 tools?")  # pyright: ignore[reportPrivateUsage]


async def test_mixed_install_and_current_names_already_current(tmp_path: Path) -> None:
    wezterm = _tool("wezterm")
    fd = _tool("fd")
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, wezterm, outdated=False)
    updates = _RecordingUpdateService()
    inputs = _inputs(
        tools=[wezterm, fd],
        installed=lambda tool: tool.id == "wezterm",
        version_refresh=refresh,
        updates=updates,
    )
    app = _host(inputs, [wezterm, fd])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["wezterm", "fd"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        prompt = screen._preflight_prompt()  # pyright: ignore[reportPrivateUsage]
        assert prompt.startswith("Install 1 tools?")
        assert "Already current: wezterm." in prompt
        assert "Install 0 tools" not in prompt


def _counting_reapply(
    calls: list[str],
    confirms: list[object],
) -> Callable[..., InstallOutcome]:
    def reapply(tool: Tool, platform: Platform, confirm: object) -> InstallOutcome:
        del platform
        calls.append(tool.id)
        confirms.append(confirm)
        return InstallOutcome(
            tool.id,
            InstallStatus.ALREADY_INSTALLED,
            post_install_handoff=("reviewed step",),
        )

    return reapply


async def test_explicit_current_selection_reapplies_post_install_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shelltool = _tool("shelltool", post_install=("set_login_shell",))
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, shelltool, outdated=False)
    calls: list[str] = []
    confirms: list[object] = []
    monkeypatch.setattr(
        installer.execute_screen,
        "reapply_post_install",
        _counting_reapply(calls, confirms),
    )
    inputs = _inputs(
        tools=[shelltool],
        installed=lambda tool: tool.id == "shelltool",
        version_refresh=refresh,
        updates=_RecordingUpdateService(),
    )
    app = _host(inputs, [shelltool])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["shelltool"], inputs))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute(screen, pilot)
        assert calls == ["shelltool"]
        assert confirms[0] is not None
        assert "reviewed step" in _log_text(screen)
        assert screen.summary is not None
        assert screen.summary.already == ()


async def test_explicit_outdated_selection_reapplies_post_install_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shelltool = _tool("shelltool", post_install=("set_login_shell",))
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, shelltool, outdated=True)
    calls: list[str] = []
    monkeypatch.setattr(
        installer.execute_screen,
        "reapply_post_install",
        _counting_reapply(calls, []),
    )
    inputs = _inputs(
        tools=[shelltool],
        installed=lambda tool: tool.id == "shelltool",
        version_refresh=refresh,
        updates=_RecordingUpdateService(),
    )
    _screen, recorded = await _run_execute(inputs, ["shelltool"])
    assert recorded is not None
    assert [target.tool.id for target in recorded.recorded] == ["shelltool"]
    assert calls == ["shelltool"]


async def test_cancel_stops_reapply_before_any_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rg = _tool("rg")
    shelltool = _tool("shelltool", post_install=("set_login_shell",))
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, rg, outdated=True)
    _seed_refresh(refresh, shelltool, outdated=False)
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []
    monkeypatch.setattr(
        installer.execute_screen,
        "reapply_post_install",
        _counting_reapply(calls, []),
    )

    class _GatedUpdateService(_RecordingUpdateService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            started.set()
            assert release.wait(timeout=5)
            return super().run(target)

    inputs = _inputs(
        tools=[rg, shelltool],
        installed=lambda _tool: True,
        version_refresh=refresh,
        updates=_GatedUpdateService(),
    )
    app = _host(inputs, [rg, shelltool])
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(ExecuteScreen(["rg", "shelltool"], inputs))
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
    assert calls == []


async def test_installed_drag_in_is_not_reapplied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _tool("parent", requires=("shelltool",))
    shelltool = _tool("shelltool", post_install=("set_login_shell",))
    refresh = _RecordingRefreshService(tmp_path / "versions.json")
    _seed_refresh(refresh, shelltool, outdated=False)
    calls: list[str] = []
    monkeypatch.setattr(
        installer.execute_screen,
        "reapply_post_install",
        _counting_reapply(calls, []),
    )
    inputs = _inputs(
        tools=[parent, shelltool],
        installed=lambda tool: tool.id == "shelltool",
        version_refresh=refresh,
        updates=_RecordingUpdateService(),
    )
    screen, _recorded = await _run_execute(inputs, ["parent"])
    assert screen.finished is True
    assert calls == []


async def test_fresh_install_is_not_reapplied(monkeypatch: pytest.MonkeyPatch) -> None:
    shelltool = _tool("shelltool", post_install=("set_login_shell",))
    captured: list[str] = []
    calls: list[str] = []
    monkeypatch.setattr(
        installer.execute_screen,
        "reapply_post_install",
        _counting_reapply(calls, []),
    )
    inputs = _inputs(tools=[shelltool], install=_install_with_output(captured))
    screen, _recorded = await _run_execute(inputs, ["shelltool"])
    assert screen.finished is True
    assert captured == ["shelltool"]
    assert calls == []
