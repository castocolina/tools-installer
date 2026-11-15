"""The app's modal screens: each one is pushed over a view and dismisses with its answer.

The two names they share with the schedules view live in ui_common as `sentence` and
`TIMES_LISTED`.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, OptionList, Select, Static
from textual.widgets.option_list import Option

from installer import daemon, schedules
from installer.rcclean import PathWriterLine
from installer.sanitize import sanitize_log_line
from installer.shellrc import path_export_guard
from installer.ui_common import TIMES_LISTED, VIEWS, run_live, sentence


class ConfirmGuardFile(ModalScreen[bool]):
    """Confirm one foreign rc file before rewriting its PATH lines in place.

    enter/y guard this file; escape/n skip it and leave the file untouched.
    One file per modal: declining one never edits it and never cancels the rest.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "guard", "guard", show=True, priority=True),
        Binding("y", "guard", "guard", show=False),
        Binding("escape", "skip", "skip", show=True),
        Binding("n", "skip", "skip", show=False),
    ]
    DEFAULT_CSS = """
    ConfirmGuardFile { align: center middle; }
    ConfirmGuardFile > Static { width: 76; height: auto; border: round yellow; padding: 1 2; }
    """

    def __init__(self, path: Path, records: Sequence[PathWriterLine]) -> None:
        super().__init__()
        lines = [f"Guard PATH lines in {path}?"]
        for index, record in enumerate(records):
            after = path_export_guard(record.directory)
            lines.append(f"  {index + 1}: {record.text}  ->  {after}")
        lines.append(
            f"A backup of the original is saved as {path}.tools-installer.old first. "
            "Nothing is deleted."
        )
        self.summary = "\n".join(lines)

    def compose(self) -> ComposeResult:
        # File text is untrusted; Text() does not parse markup.
        yield Static(Text(self.summary))

    def action_guard(self) -> None:
        self.dismiss(True)

    def action_skip(self) -> None:
        self.dismiss(False)


class ConfirmUninstall(ModalScreen[bool]):
    """Confirm the one destructive, hard-to-reverse commit: deleting installed
    artifacts. enter/y confirm; escape/n cancel. Reversible actions (policies)
    deliberately get no modal — over-confirming trains click-through."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "confirm", "remove", show=True, priority=True),
        Binding("y", "confirm", "remove", show=False),
        Binding("escape", "cancel", "cancel", show=True),
        Binding("n", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    ConfirmUninstall { align: center middle; }
    ConfirmUninstall > Vertical {
        width: 60; height: auto; max-height: 18; border: round red; padding: 1 2;
    }
    ConfirmUninstall #confirm-body { height: auto; max-height: 13; }
    """

    def __init__(self, summary: str, review: Sequence[Text] = ()) -> None:
        super().__init__()
        self.summary = summary  # public test seam
        self.review = tuple(review)  # public test seam: blocks 3-7, each folded `Text`

    def compose(self) -> ComposeResult:
        body = Text("\n").join(
            [
                Text(f"Remove {self.summary}?", style="bold red"),
                Text(""),
                Text("This deletes installed artifacts and is not undoable."),
                *self.review,
            ]
        )
        with Vertical(id="confirm-box"):
            with VerticalScroll(id="confirm-body"):
                yield Static(body)
            yield Static(Text("enter remove · esc cancel", style="dim"), id="confirm-keys")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class NavScreen(ModalScreen[str | None]):
    """Our command palette: a modal list of views, dismissing the chosen one.

    Replaces Textual's default palette (disabled on the app), whose options
    dead-end by closing the screen. Selecting an item dismisses with the view
    name; Escape dismisses with None (no navigation).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    NavScreen { align: center middle; }
    NavScreen > ListView { width: 60; height: auto; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(*[ListItem(Label(view.palette), id=view.name) for view in VIEWS])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class LinkModeScreen(ModalScreen[str | None]):
    """Three-option PATH link-mode picker. Labels are the wording the retired
    pre-TUI questionary prompt used, so moving the question into the app is a
    UI relocation, not a behaviour change.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "close", show=False),
    ]
    DEFAULT_CSS = """
    LinkModeScreen { align: center middle; }
    LinkModeScreen > ListView { width: 80; height: 8; border: round $accent; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(
            ListItem(
                Label("Centralized: one ~/.myshellrc, sourced from .zshrc and .bashrc"),
                id="link-centralized",
            ),
            ListItem(
                Label("Single shell: source ~/.myshellrc from your current shell only"),
                id="link-single",
            ),
            ListItem(
                Label("Split: write PATH directly into each rc file (no ~/.myshellrc)"),
                id="link-split",
            ),
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None:  # unreachable: every item above is constructed with one
            return
        self.dismiss(item_id.removeprefix("link-"))

    def action_cancel(self) -> None:
        self.dismiss(None)


class ScheduleTimeScreen(ModalScreen[tuple[int, str] | None]):
    """When a schedule runs: an interval (one of eight) and a start time, validated in place.

    A rejected value keeps the modal open with the validator's message and nothing leaves it
    (P6); `escape` returns None. macOS tmp cleanup passes `interval=None`: a daily time only.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    ScheduleTimeScreen { align: center middle; }
    ScheduleTimeScreen > Vertical {
        width: 60; height: auto; border: round $accent; padding: 0 1; background: $surface;
    }
    ScheduleTimeScreen Label { height: 1; }
    """

    def __init__(self, title: str, interval: int | None, start: str) -> None:
        super().__init__()
        self._title = title
        self._interval = interval
        self._start = start

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text(self._title, style="bold"), id="time-title")
            if self._interval is not None:
                yield Label("Every")
                yield Select[int](
                    [(f"{hours} h", hours) for hours in schedules.INTERVALS],
                    value=self._interval,
                    allow_blank=False,
                    id="time-interval",
                )
            label = "Starting at" if self._interval is not None else "Daily at"
            yield Label(f"{label} (HH:MM, local time)")
            yield Input(self._start, placeholder="00:00", max_length=5, id="time-start")
            yield Label("", id="time-preview")
            yield Label("", id="time-error")
            yield Label(Text("enter save | esc cancel", style="dim"), id="time-keys")

    def on_mount(self) -> None:
        self._refresh_preview()

    def _chosen_interval(self) -> int | None:
        if self._interval is None:
            return 24
        value = self.query_one(Select[int]).value
        return value if isinstance(value, int) else None

    def _refresh_preview(self) -> None:
        start = self.query_one(Input).value
        interval = self._chosen_interval()
        try:
            grid = schedules.slots(interval if interval is not None else 0, start)
        except daemon.DaemonScheduleError:
            text = "Runs at: enter a time as HH:MM"
        else:
            names = [f"{hour:02d}:{minute:02d}" for hour, minute in grid]
            if self._interval is None:
                text = f"Runs daily at {names[0]}"
            elif len(names) <= TIMES_LISTED:
                text = f"Runs at {', '.join(names)}"
            else:
                text = f"Runs at {', '.join(names[:3])} … {names[-1]} ({len(names)} times a day)"
        self.query_one("#time-preview", Label).update(Text(text, style="dim"))

    def on_select_changed(self, event: Select.Changed) -> None:
        del event
        self._refresh_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        del event
        self._refresh_preview()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        start = self.query_one(Input).value
        interval = self._chosen_interval()
        try:
            hours = schedules.validate_interval(interval if interval is not None else 0)
            schedules.validate_start(start)
        except daemon.DaemonScheduleError as exc:
            self.query_one("#time-error", Label).update(Text(str(exc), style="red"))
            return
        self.dismiss((hours, start))

    def action_cancel(self) -> None:
        self.dismiss(None)


class CursorModelsRead(Message):
    """The threaded `cursor-agent --list-models` read finished; `models` is None on failure."""

    def __init__(self, models: tuple[str, ...] | None, error: str | None) -> None:
        self.models = models
        self.error = error
        super().__init__()


class CursorModelScreen(ModalScreen[str | None]):
    """The cursor-agent default model: a filter field over the listed ids, or free text.

    The list is read on a thread worker when the modal opens; an answer that lands after the
    modal closed is dropped. An unlisted but well-formed id is accepted (D-18, offline edits).
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "cancel", show=False),
    ]
    DEFAULT_CSS = """
    CursorModelScreen { align: center middle; }
    CursorModelScreen > Vertical {
        width: 64; height: 16; border: round $accent; padding: 0 1; background: $surface;
    }
    CursorModelScreen Label { height: 1; }
    CursorModelScreen OptionList { height: 1fr; }
    """

    def __init__(self, current: str, read_models: Callable[[], tuple[str, ...] | None]) -> None:
        super().__init__()
        self._current = current
        self._read_models = read_models
        self._dismissed = False
        # The ids the worker read, in list order; empty until the list lands.
        self.listed: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                Text("Model cursor-agent uses when no --model is given", style="bold"),
                id="model-title",
            )
            yield Input(self._current, id="model-input")
            yield Label(Text("Reading your cursor-agent models…", style="dim"), id="model-status")
            yield OptionList(id="model-list")
            yield Label("", id="model-error")
            yield Label(Text("enter use | esc cancel", style="dim"), id="model-keys")

    def on_mount(self) -> None:
        self.query_one(OptionList).display = False
        self._read_worker()

    @work(thread=True, exclusive=True, group="schedule-models", exit_on_error=False)
    def _read_worker(self) -> None:
        models: tuple[str, ...] | None = None
        error: str | None = "the model list did not load"
        try:
            models, error = run_live(self._read_models)
            if models is None and error is None:
                error = "cursor-agent --list-models gave no list"
        finally:
            self.post_message(CursorModelsRead(models, error))

    def on_cursor_models_read(self, message: CursorModelsRead) -> None:
        if self._dismissed:
            return
        status = self.query_one("#model-status", Label)
        if message.models is None:
            reason = sentence(message.error or "unknown error")
            status.update(
                Text(f"Could not read the model list: {reason} Type a model id.", "yellow")
            )
            return
        self.listed = tuple(dict.fromkeys(message.models))
        status.display = False
        self.query_one(OptionList).display = True
        self._fill()

    def _fill(self) -> None:
        typed = self.query_one(Input).value
        needle = "" if typed == self._current else typed.lower()
        options = self.query_one(OptionList)
        options.clear_options()
        options.add_options(
            Option(
                Text(f"{'● ' if model == self._current else '  '}{sanitize_log_line(model)}"),
                id=model,
            )
            for model in self.listed
            if needle in model.lower()
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        del event
        if self.listed:
            self._fill()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._use(self.query_one(Input).value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id is not None:  # every option is built with its model id
            self._use(event.option.id)

    def _use(self, model: str) -> None:
        try:
            schedules.validate_model_id(model)
        except daemon.DaemonScheduleError as exc:
            self.query_one("#model-error", Label).update(Text(str(exc), style="red"))
            return
        self._dismissed = True
        self.dismiss(model)

    def action_cancel(self) -> None:
        self._dismissed = True
        self.dismiss(None)
