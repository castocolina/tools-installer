"""ExecuteScreen behaviour, plus characterisation of the worker-to-modal primitive.

The first tests pin MECHANISM=A (plan 13-01). The rest drive the in-app install
screen: a fake `install` that emits through the injected runner, never a real
package manager or shell rc file.
"""

import threading
from collections.abc import Callable, Mapping
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.pilot import Pilot
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from installer.doctor import DoctorReport
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.execute_screen import (
    ExecuteInputs,
    ExecuteScreen,
    sanitize_log_line,
)
from installer.model import Method, Tool
from installer.platform import Platform
from installer.run import Runner
from installer.session import Install
from installer.uninstall import SweepResult
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


def _tool(tool_id: str, *, requires: tuple[str, ...] = ()) -> Tool:
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
    )


def _emit_through_runner(runner: object, tool_id: str, lines: tuple[str, ...]) -> None:
    emit = getattr(runner, "_emit", None)
    if not callable(emit):
        return
    for line in lines:
        emit(tool_id, line)


def _install_with_output(captured: list[str]) -> Install:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        del platform, resolve_tag, checksum_policy, tools
        captured.append(tool.id)
        _emit_through_runner(runner, tool.id, _OUTPUTS.get(tool.id, ()))
        return InstallOutcome(tool.id, "installed")

    return install


def _inputs(
    *,
    tools: list[Tool] | None = None,
    install: Install | None = None,
    wire_path: Callable[[], str] | None = None,
    verify: Callable[[], str] | None = None,
    installed: Callable[[Tool], bool] | None = None,
    unattended: bool = False,
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
    )


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
            rows=[],
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
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools
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
    ) -> InstallOutcome:
        del tool, platform, runner, resolve_tag, checksum_policy, tools
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
    ) -> InstallOutcome:
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
