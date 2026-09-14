"""Characterisation tests of the Textual primitive the execute screen will depend on.

This file starts as a characterisation test of the Textual primitive the execute
screen will depend on. It deliberately exercises no production symbol yet (the
production `ask_from_worker` and `ChecksumMismatchScreen` arrive in plan 13-05
with their first caller, per architecture rule 5). A Textual upgrade breaking
this file is a real signal rather than test churn.
"""

from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.pilot import Pilot
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView


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
