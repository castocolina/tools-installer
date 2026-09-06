"""Unified Textual shell hosting the wizard views behind one app.

The app owns navigation and the screen stack. The base view, doctor, uninstall,
and policies are all functional views. Execution stays behind the pure
`installer/` core invoked from `setup.py`, with one deliberate exception: the
doctor, uninstall, and policies views apply their changes live through
injected closures. The app's run value stays the catalog decision
(`list[str] | None`).

The first registered view is the base screen (`get_default_screen`); it cannot
be switched out. Navigation is therefore a stack with the base view at the
bottom: the stack is always `[base]` or `[base, <one other view>]`.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from installer.app import UninstallDecision
from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.enums import Tier, UninstallState
from installer.guidance import Guidance, doctor_guidance, guard_guidance, node_globals_guidance
from installer.model import Tool
from installer.pnpm_globals import NodeGlobalsReport, reinstall_preview
from installer.policy import Policy, PolicyResult
from installer.render import guidance_text
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import (
    BASE_VIEW,
    VIEW_ORDER,
    VIEWS,
    AppScreen,
    WayfindingHeader,
    highlighted_key,
    mark,
    multiline_summary,
    run_live,
)
from installer.uninstall import SweepResult, ToolRow


@dataclass(frozen=True)
class UninstallInputs:
    """Everything the UninstallScreen needs: every classified tool (catalog
    parity, not just the removable ones), the active ban names, whether a managed
    PATH block exists, the active shell-tweak ids, and the live removal closure
    bound by the composition root.

    `rows` is a snapshot because nothing in this app installs or removes a tool
    while it runs. The other three are PREDICATES, not their results, because
    each is mutated live by another view in the same process: the Policies view
    writes the ban's shims and aliases and toggles the tweaks, and the Doctor
    view writes the very managed PATH block `has_path_block` detects. A value
    frozen at construction goes stale the moment the user does — stale-False
    leaves the lever for something they just enabled unreachable, and stale-True
    offers a lever that removes nothing while the summary claims it did.
    `UninstallScreen.enter_view` re-evaluates all three on every entry."""

    rows: list[ToolRow]
    ban_names: Callable[[], list[str]]
    has_path_block: Callable[[], bool]
    remove: Callable[[UninstallDecision], SweepResult]
    tweak_ids: Callable[[], tuple[str, ...]] = tuple


@dataclass(frozen=True)
class PolicyInputs:
    """The policies the PoliciesScreen renders, each carrying its own bound
    apply/remove closures. The composition root builds these from the pure core."""

    policies: list[Policy]


_NOTHING_TO_REINSTALL = "Nothing to reinstall — pnpm manages no globals here."
# Distinct from _NOTHING_TO_REINSTALL on purpose: an unanswered `pnpm list -g`
# is not an empty global set, and the machine whose pnpm has just replaced
# itself is exactly the one that must not be told there is nothing to restore.
_GLOBALS_UNKNOWN = "pnpm's global set could not be read — install or repair pnpm, then retry."
_GLOBALS_UNKNOWN_COUNT = "pnpm's global set could not be read (pnpm missing, or the query failed)."
_GLOBALS_CHECKING = "Checking pnpm's global set..."
_GLOBALS_UNKNOWN_YET = "Still checking pnpm's global set — press r again in a moment."
# An audit that could not run answers the same question as a pnpm that could not
# be asked: nothing was learned. One shape, so no consumer has to handle two.
_GLOBALS_UNREADABLE = NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
# A plain constant, never a second call to the injected preview closure: that
# closure is exactly what may have just raised inside the guarded audit call,
# so calling it again for the fallback path would reopen the same hazard.
_GLOBALS_UNREADABLE_PREVIEW = _GLOBALS_UNKNOWN_COUNT


class GlobalsReinstalled(Message):
    """The threaded pnpm-globals reinstall finished; `error` is None on success.

    post_message is Textual's thread-safe hand-off back to the event loop, so
    the worker never touches a widget from its own thread.
    """

    def __init__(self, error: str | None) -> None:
        self.error = error
        super().__init__()


class GlobalsAudited(Message):
    """The threaded `pnpm list -g --json` finished; the screen may now render it.

    Same hand-off as GlobalsReinstalled, for the same reason: the audit spawns a
    subprocess, so it cannot run on the event loop, and its result cannot be
    written into a widget from the worker's own thread. `preview` travels with
    the report because building it also needs to resolve pnpm.
    """

    def __init__(
        self, report: NodeGlobalsReport, preview: str, error: str | None, generation: int
    ) -> None:
        self.report = report
        self.preview = preview
        self.error = error
        # Two audit workers can be in flight at once (e.g. a stale one from
        # screen entry still running when a reinstall finishes and starts a
        # fresh one): exclusive=True only marks the older worker cancelled, it
        # cannot stop a thread already inside subprocess.run. The generation
        # lets on_globals_audited tell which post_message is the one anyone
        # asked for and discard the other, rather than whichever lands last
        # silently overwriting fresher state with stale state.
        self.generation = generation
        super().__init__()


class _BodyStatic(Static):
    """Static with a small public render seam for headless tests."""

    @property
    def renderable(self) -> Any:
        return self.render()


class DoctorScreen(AppScreen):
    """PATH audit and safe PATH repair in one view."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "apply", "apply", show=True),
        Binding("a", "apply", "apply", show=False),
        Binding("r", "reinstall_globals", "reinstall pnpm globals", show=True),
    ]
    DEFAULT_CSS = """
    DoctorScreen {
        align: center top;
    }
    DoctorScreen #doctor-body {
        width: 76;
        max-width: 90%;
        height: auto;
        margin: 2 0;
        padding: 1 2;
        border: round $accent;
    }
    """

    def __init__(
        self,
        report: DoctorReport,
        guard_state: Callable[[], tuple[dict[str, bool], str | None]],
        fix_preview: str,
        fix: Callable[[], None],
        *,
        node_globals: Callable[[], NodeGlobalsReport],
        globals_preview: Callable[[NodeGlobalsReport], str],
        reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]],
    ) -> None:
        super().__init__(view="doctor")
        self._report = report
        # A predicate, not its result: the Policies view installs and removes the
        # pip/npm ban live, one nav step away, and guard_guidance renders exactly
        # that state. The PATH audit beside it stays a snapshot on purpose — the
        # process PATH cannot change until the shell restarts.
        self._guard_state = guard_state
        self._fix_preview = fix_preview
        self._fix = fix
        # node_globals shells out to `pnpm list -g --json`, so it is NEVER
        # called from the event loop: _audit_globals_worker calls it on a thread
        # and posts GlobalsAudited back. The result is held here rather than
        # re-derived per render, which is what makes every render IO-free.
        # globals_preview takes the report for the same reason — building the
        # preview from a fresh audit would put the subprocess back on the loop.
        # reinstall_globals takes its package list for the same reason again,
        # and it removes the last shared cell two threads could race on.
        self._node_globals = node_globals
        self._globals_preview = globals_preview
        self._reinstall_globals = reinstall_globals
        # None until the first audit lands: "not asked yet" is not "pnpm manages
        # nothing" any more than "could not be asked" is (NodeGlobalsReport.known).
        self._globals_report: NodeGlobalsReport | None = None
        self._globals_preview_text = ""
        self.guidance: list[Guidance] = []
        self.applied = False
        self.error: str | None = None
        # Own flags, not a reuse of applied/error: action_apply opens with
        # `if self.applied: return`, so sharing them would make each action
        # silently suppress the other and each section render the other's outcome.
        self.globals_done = False
        self.globals_error: str | None = None
        # The reinstall is the only subprocess a view starts, and `pnpm add -g`
        # of a Puppeteer-carrying package is minutes, not seconds. It runs in a
        # thread worker so the event loop keeps painting; this flag is what the
        # body renders while it does, and what stops a second `r` stacking a
        # concurrent install.
        self.globals_running = False
        # The audit's own in-flight flag. It cannot share globals_running: the
        # two workers run for different reasons, and a render that cannot tell
        # them apart would say "Reinstalling" for a read.
        self.globals_auditing = False
        # Not globals_error: "nothing to reinstall" is not a failure, and the
        # error branch renders "Reinstall failed." in red.
        self.globals_note: str | None = None
        # Bumped every time an audit worker is actually started; carried on
        # its GlobalsAudited message so a superseded worker's result (one
        # started before a newer request, still running when the newer one
        # lands) is recognisably stale and discarded rather than clobbering
        # fresher state.
        self._globals_audit_generation = 0

    def compose_body(self) -> ComposeResult:
        yield _BodyStatic(id="doctor-body")

    def on_mount(self) -> None:
        self._refresh_guidance()
        self._refresh_body()
        self._start_globals_audit()

    def enter_view(self) -> None:
        """Re-read the ban state on every entry, and re-ask pnpm off the loop.

        Installed screens are suspended, not unmounted, so `on_mount` fires once
        for the life of the app: without this, Policies → toggle the ban →
        Doctor reports the state from before the toggle. The globals audit needs
        the same freshness but cannot be taken here synchronously, so it is
        started as a worker and rendered when it lands.

        The audit is not started on the first entry: this runs BEFORE the screen
        is pushed, and `on_mount` starts it a moment later.
        """
        self._refresh_guidance()
        if self.is_mounted:
            self._refresh_body()
            self._start_globals_audit()

    def _start_globals_audit(self) -> None:
        if self.globals_running:
            # A reinstall in flight re-audits when it finishes.
            return
        # Deliberately NOT guarded on globals_auditing: the post-reinstall
        # re-audit must always get a fresh worker, even if an older one
        # (started on screen entry) is still running. exclusive=True cancels
        # the older Worker on the Textual side, but a thread already inside
        # subprocess.run keeps running to completion regardless — its result
        # is still delivered. Bumping the generation here is what lets
        # on_globals_audited recognise that stale delivery and drop it.
        self._globals_audit_generation += 1
        self.globals_auditing = True
        self._audit_globals_worker(self._globals_audit_generation)

    def _refresh_guidance(self) -> None:
        # IO-free by construction: the globals half reads the last audited
        # report, never the closure that would spawn `pnpm list -g --json`.
        # Before the first audit lands there is nothing to say about the
        # globals, which is honest — node_globals_guidance only ever speaks
        # about a set it has seen.
        status, warning = self._guard_state()
        globals_report = self._globals_report
        self.guidance = (
            doctor_guidance(self._report)
            + guard_guidance(status, warning)
            + (node_globals_guidance(globals_report) if globals_report is not None else [])
        )

    def _refresh_body(self) -> None:
        body = self.query_one("#doctor-body", _BodyStatic)
        text = Text()
        text.append("PATH Doctor\n", style="bold")
        text.append("Audit\n", style="bold")
        text.append(guidance_text(self._tui_guidance()))
        text.append("\n\nSafe fix preview\n", style="bold")
        text.append(self._fix_preview)
        text.append("\n\nAction\n", style="bold")
        if self.applied:
            text.append("PATH wired.", style="green")
            text.append("\nRestart your shell or run `source ~/.myshellrc` to apply.")
        elif self.error is not None:
            text.append("Fix failed.", style="red")
            text.append(f"\n{self.error}")
            text.append("\nCheck the target is writable, then press enter to retry.")
        else:
            text.append("Press enter to wire the managed PATH into your shells.", style="yellow")
            text.append("\nViewing this screen did not change your shell files.")
        report = self._globals_report
        text.append("\n\npnpm-managed globals\n", style="bold")
        # Both counts come from pnpm's own global list, never from the catalog:
        # a registry entry declares that a tool CAN install this way, which is
        # not evidence that it did. A count is only printable when the list was
        # actually read: report None means the audit has not landed yet and
        # report.known False means it landed empty-handed, and "0 package(s)"
        # would state either of those unknowns as a fact.
        if report is None:
            text.append(f"{_GLOBALS_CHECKING}\n", style="yellow")
        elif report.known:
            text.append(
                f"{len(report.managed)} package(s) in pnpm's global set, "
                f"{len(report.entries)} of them catalog tool(s).\n"
            )
        else:
            text.append(f"{_GLOBALS_UNKNOWN_COUNT}\n", style="yellow")
        # Print the core's preview string verbatim, as resolved by the audit
        # worker. Do not call reinstall_argv here: a non-empty set with no
        # resolvable pnpm is a returned string, never an argv and never an
        # exception (architecture rule 3).
        # Skipped when the count line above already said the same thing: a
        # known=False preview is the identical "could not be read" sentence
        # with only the tail changed, and printing both reads like a stutter.
        if report is None or report.known:
            text.append(self._globals_preview_text)
        text.append("\n")
        if self.globals_running:
            text.append("Reinstalling the pnpm global set...", style="yellow")
            text.append("\nOutput is captured; this can take several minutes.")
        elif self.globals_done:
            text.append("pnpm globals reinstalled.", style="green")
        elif self.globals_error is not None:
            text.append("Reinstall failed.", style="red")
            text.append(f"\n{self.globals_error}")
        elif self.globals_note is not None:
            text.append(self.globals_note, style="yellow")
        else:
            text.append("Press r to reinstall the pnpm-managed global set.", style="yellow")
        body.update(text)

    def _tui_guidance(self) -> list[Guidance]:
        """Keep CLI doctor wording unchanged while the TUI points to the live apply action."""
        rewritten: list[Guidance] = []
        for item in self.guidance:
            if item.next_step.startswith("Run `make fix`"):
                rewritten.append(
                    replace(
                        item,
                        next_step=(
                            "Press enter to apply the safe fix below, then open a new terminal "
                            "(or `source ~/.myshellrc`)."
                        ),
                    )
                )
            elif item.next_step.startswith("Run `make setup`"):
                rewritten.append(
                    replace(
                        item,
                        next_step="Press r to reinstall the pnpm-managed global set.",
                    )
                )
            else:
                rewritten.append(item)
        return rewritten

    def action_apply(self) -> None:
        if self.applied:
            return
        _, self.error = run_live(self._fix)
        self.applied = self.error is None
        self._refresh_body()

    def action_reinstall_globals(self) -> None:
        # globals_done needs no message: the body already renders the success
        # line, so a repeat press is answered by what is on screen.
        if self.globals_done or self.globals_running:
            return
        if self.globals_auditing:
            # Covers both "no audit has ever landed" (self._globals_report is
            # still None: on_mount starts the first audit synchronously, so
            # that window and this flag are the same window) and "a fresher
            # audit is now re-asking pnpm" (screen entry, or a just-finished
            # reinstall) while an older report is still what's on screen.
            # Acting on that report here is exactly how a reinstall could
            # once run against a superseded package list. Refuse and let the
            # in-flight audit's own landing (on_globals_audited) answer this
            # note.
            self.globals_note = _GLOBALS_UNKNOWN_YET
            self._refresh_body()
            return
        # Not auditing, past __init__: an audit has landed and set this.
        report = self._globals_report
        if report is None:
            return  # unreachable: globals_auditing is False only once one has
        # The footer advertises `r` (ui_common.VIEWS), so a keypress that
        # changes nothing on screen reads as a broken binding. The two
        # answers are not interchangeable: one is a fact about the machine,
        # the other is an admission that the machine was not readable.
        if not report.known:
            # There is nothing to retry a fixed message against: the last
            # read simply failed, and the only screen action that changes
            # that is asking again.
            self.globals_note = _GLOBALS_UNKNOWN
            self._refresh_body()
            self._start_globals_audit()
            return
        if not report.managed:
            self.globals_note = _NOTHING_TO_REINSTALL
            self._refresh_body()
            return
        self.globals_note = None
        self.globals_running = True
        self._refresh_body()
        # The package list is passed in rather than re-derived inside the
        # worker: re-deriving would put `pnpm list -g --json` on a second
        # thread, and the set the user consented to is the one on screen.
        self._reinstall_globals_worker(report.managed)

    # Distinct groups: `exclusive` cancels within a group, so leaving both
    # workers in the default one would let a reinstall cancel an in-flight
    # audit and vice versa.
    @work(thread=True, exclusive=True, group="globals-reinstall")
    def _reinstall_globals_worker(self, packages: tuple[str, ...]) -> None:
        """Run the reinstall off the event loop, then hand the outcome back to it.

        A synchronous subprocess here would freeze every frame for the length of
        a `pnpm add -g`. Widgets may only be touched from the app's own thread,
        hence a posted message rather than a direct refresh.
        """
        _, error = run_live(lambda: self._reinstall_globals(packages))
        self.post_message(GlobalsReinstalled(error))

    @work(thread=True, exclusive=True, group="globals-audit")
    def _audit_globals_worker(self, generation: int) -> None:
        """Ask pnpm what it manages globally, off the event loop.

        `pnpm list -g --json` is a subprocess like the reinstall is, and it was
        the last one still running on the loop: on a cold cache every Doctor
        render blocked the whole UI for its duration, with no timeout and no
        interruptible path (Textual holds the terminal in raw mode, so a Ctrl+C
        arrives as a byte on a queue the blocked loop is not draining). It runs
        here for the same reason the reinstall does, and hands its result back
        the same way. `generation` travels with the result so a superseded
        worker's answer can be told apart from the one anyone is waiting on.
        """
        # Both the audit and the preview it feeds must sit inside the SAME
        # guarded call: self._globals_preview also resolves pnpm (real_pnpm ->
        # Path.home()), so it can raise for the same reasons _node_globals
        # can. Guarding only the first left the second free to turn a
        # resolver failure into an uncaught WorkerFailed that kills the app,
        # rather than the "could not be read" text this worker exists to
        # show instead.
        outcome, error = run_live(self._audit_globals)
        if outcome is None:
            report, preview = _GLOBALS_UNREADABLE, _GLOBALS_UNREADABLE_PREVIEW
        else:
            report, preview = outcome
        self.post_message(GlobalsAudited(report, preview, error, generation))

    def _audit_globals(self) -> tuple[NodeGlobalsReport, str]:
        report = self._node_globals()
        return report, self._globals_preview(report)

    def on_globals_audited(self, message: GlobalsAudited) -> None:
        if message.generation != self._globals_audit_generation:
            # A stale worker's answer, superseded by a newer audit request
            # (e.g. the post-reinstall re-audit) already in flight. The
            # current generation's own message is still coming; do not clear
            # globals_auditing or apply this outdated report over it.
            return
        self.globals_auditing = False
        self._globals_report = message.report
        self._globals_preview_text = message.preview
        # Any note naming the audit itself (waiting for it, or the previous
        # one having failed) is answered by this landing one way or another:
        # the fresh report is what the screen now shows instead. A note
        # about the REINSTALL's own outcome is a different lifecycle
        # (globals_done/globals_error), never written here, so this cannot
        # clear one of those by mistake.
        if self.globals_note in (_GLOBALS_UNKNOWN_YET, _GLOBALS_UNKNOWN):
            self.globals_note = None
        self._refresh_guidance()
        self._refresh_body()

    def on_globals_reinstalled(self, message: GlobalsReinstalled) -> None:
        self.globals_running = False
        self.globals_error = message.error
        self.globals_done = message.error is None
        self._refresh_body()
        # The globals audit is a live `shutil.which` probe whose answer this
        # action just tried to change — unlike the PATH audit, which is a
        # deliberate snapshot. Without this the screen renders "mmdc went
        # missing" directly above "pnpm globals reinstalled." Re-asking is a
        # subprocess, so it goes back through the worker rather than being
        # taken inline here, where it would block the loop twice over.
        self._start_globals_audit()


@dataclass(frozen=True)
class _UninstallEntry:
    """A browsable uninstall row: either a classified tool or an environment
    pseudo-row (the pip/npm ban, the managed PATH block, or the shell tweaks).

    `key` is the stable id (a tool id, or "#ban"/"#path-block"/"#tweaks"). `cells`
    are the pre-rendered columns. `selectable` gates toggling (removable tools and
    the env rows are selectable; managed/absent/unavailable tools are not).
    `detail` is the detail-bar line. `paths` are the tool's removable artifacts
    (empty for env rows). `is_ban`/`is_path_block`/`is_tweaks` flag the env rows
    so a selection maps back to the UninstallDecision levers."""

    key: str
    cells: list[Text]
    selectable: bool
    detail: str
    paths: tuple[Path, ...]
    is_ban: bool
    is_path_block: bool
    is_tweaks: bool = False


# Section titles per state, in display order. The "environment" section holds the
# ban/PATH pseudo-rows.
_STATE_TITLES: tuple[tuple[UninstallState, str], ...] = (
    (UninstallState.REMOVABLE, "removable here"),
    (UninstallState.MANAGED, "managed elsewhere"),
    (UninstallState.ABSENT, "not installed"),
    (UninstallState.UNAVAILABLE, "not available"),
)
_BAN_KEY = "#ban"
_BLOCK_KEY = "#path-block"
_TWEAK_KEY = "#tweaks"
_ENV_KEYS = (_BAN_KEY, _BLOCK_KEY, _TWEAK_KEY)


class UninstallScreen(AppScreen):
    """Full catalog-parity uninstall browser. Every tool is listed with its
    removability state; only removable tools (and the env rows) toggle. Enter
    removes exactly the selected artifacts + env levers, applied live."""

    # Narrow .app from App[Unknown] (MessagePump default) to the concrete host
    # app so push_screen() is typed without an Unknown generic param.
    # UnifiedApp is defined later in this module; the string forward reference is
    # resolved by pyright (which analyses all module-level names together).
    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    def __init__(self, inputs: UninstallInputs) -> None:
        super().__init__(view="uninstall", accent="red")
        self._rows = inputs.rows
        self._ban_names_of = inputs.ban_names
        self._has_path_block_of = inputs.has_path_block
        self._tweak_ids_of = inputs.tweak_ids
        self._ban_names: list[str] = self._ban_names_of()
        self._has_path_block: bool = self._has_path_block_of()
        self._tweak_ids: tuple[str, ...] = self._tweak_ids_of()
        self._remove = inputs.remove
        self.applied = False
        self.error: str | None = None
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser: ToolBrowser[_UninstallEntry] = ToolBrowser(self._adapter())

    # -- entry construction ------------------------------------------------
    def _build_entries(self) -> list[_UninstallEntry]:
        entries = [self._tool_entry(row) for row in self._rows]
        if self._ban_names:
            entries.append(self._ban_entry())
        if self._has_path_block:
            entries.append(self._block_entry())
        if self._tweak_ids:
            entries.append(self._tweak_entry())
        return entries

    def _tool_entry(self, row: ToolRow) -> _UninstallEntry:
        selectable = row.state == UninstallState.REMOVABLE
        style = "" if selectable else "dim"
        installed_via = {
            UninstallState.REMOVABLE: "userspace",
            UninstallState.MANAGED: "package manager",
            UninstallState.ABSENT: "—",
            UninstallState.UNAVAILABLE: "—",
        }[row.state]
        removes = (
            f"{len(row.paths)} artifact(s)"
            if selectable
            else {
                UninstallState.MANAGED: "nothing (managed elsewhere)",
                UninstallState.ABSENT: "nothing (not installed)",
                UninstallState.UNAVAILABLE: "nothing (unavailable)",
            }[row.state]
        )
        cells = [
            mark(False) if selectable else Text(""),
            Text(row.tool.id, style="bold" if selectable else "dim"),
            Text(row.tool.category, style=style),
            Text(installed_via, style=style),
            Text(removes, style=style),
        ]
        return _UninstallEntry(
            key=row.tool.id,
            cells=cells,
            selectable=selectable,
            detail=row.hint,
            paths=tuple(row.paths),
            is_ban=False,
            is_path_block=False,
        )

    def _ban_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BAN_KEY,
            cells=[
                mark(False),
                Text("pip/npm ban", style="bold yellow"),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(f"shims + aliases ({', '.join(self._ban_names)})", style="dim"),
            ],
            selectable=True,
            detail=f"pip/npm ban — shims + interactive aliases ({', '.join(self._ban_names)})",
            paths=(),
            is_ban=True,
            is_path_block=False,
        )

    def _block_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_BLOCK_KEY,
            cells=[
                mark(False),
                Text("PATH wiring", style="bold yellow"),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text("managed block in ~/.myshellrc", style="dim"),
            ],
            selectable=True,
            detail="PATH wiring — the managed block in ~/.myshellrc",
            paths=(),
            is_ban=False,
            is_path_block=True,
        )

    def _tweak_entry(self) -> _UninstallEntry:
        return _UninstallEntry(
            key=_TWEAK_KEY,
            cells=[
                mark(False),
                Text("shell tweaks", style="bold yellow"),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(f"blocks + helpers ({', '.join(self._tweak_ids)})", style="dim"),
            ],
            selectable=True,
            detail=(
                "Disables every enabled shell tweak — the ~/.myshellrc blocks, "
                "the managed helper executables, and the Oh-My-Zsh plugin names "
                "this installer added to .zshrc (never ones you added yourself)"
            ),
            paths=(),
            is_ban=False,
            is_path_block=False,
            is_tweaks=True,
        )

    # -- browser adapter ---------------------------------------------------
    def _adapter(self) -> BrowserAdapter[_UninstallEntry]:
        return BrowserAdapter(
            items=self._entries,
            columns=(
                ("Sel", "sel"),
                ("Tool", "tool"),
                ("Cat", "cat"),
                ("Installed via", "via"),
                ("What gets removed", "removes"),
            ),
            item_id=lambda entry: entry.key,
            row_cells=lambda entry: entry.cells,
            detail_text=lambda entry: entry.detail,
            groups=self._groups,
            views=(("all", "All"),),
            detail_is_markup=False,
            selectable=lambda entry: entry.selectable,
        )

    def _groups(self, _view: str) -> list[Section[_UninstallEntry]]:
        by_state: dict[UninstallState, list[_UninstallEntry]] = {}
        for row, entry in zip(self._rows, self._entries, strict=False):
            by_state.setdefault(row.state, []).append(entry)
        sections: list[Section[_UninstallEntry]] = [
            (title, title, by_state[state]) for state, title in _STATE_TITLES if by_state.get(state)
        ]
        env = [
            entry
            for entry in self._entries
            if entry.is_ban or entry.is_path_block or entry.is_tweaks
        ]
        if env:
            sections.append(("environment", "shell config the installer manages", env))
        return sections

    def compose_body(self) -> ComposeResult:
        yield self._browser

    def on_mount(self) -> None:
        self._show_standing_status()

    def _live_state(self) -> tuple[list[str], bool, tuple[str, ...]]:
        """Every input another view can change while this one is suspended."""
        return self._ban_names_of(), self._has_path_block_of(), self._tweak_ids_of()

    def enter_view(self) -> None:
        """Re-derive all three environment rows each time this view is opened.

        The Policies view toggles the ban and the tweaks live and the Doctor
        view writes the managed PATH block, all one nav step away, so each row's
        existence and its label must be read at entry rather than frozen in
        `__init__` — otherwise enabling something leaves its lever unreachable
        here, and disabling it leaves a lever that removes nothing while the
        summary claims it did. Skipped once the screen has applied: that run's
        result is the standing message.
        """
        if self.applied:
            return
        refreshed = self._live_state()
        if refreshed == (self._ban_names, self._has_path_block, self._tweak_ids):
            return
        self._ban_names, self._has_path_block, self._tweak_ids = refreshed
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser.reload(self._adapter())
        if self.is_mounted:
            self._show_standing_status()

    def _show_standing_status(self) -> None:
        if not self._entries:
            self.status.set("Nothing to uninstall.", "ok")
        else:
            self.status.clear()

    # -- public seams the tests assert on ----------------------------------
    @property
    def selected(self) -> set[str]:
        """Selected *tool* ids (the env pseudo-rows are reported separately)."""
        return {key for key in self._browser.selected if key not in _ENV_KEYS}

    @property
    def remove_ban(self) -> bool:
        return _BAN_KEY in self._browser.selected

    @property
    def remove_path_block(self) -> bool:
        return _BLOCK_KEY in self._browser.selected

    @property
    def remove_tweaks(self) -> bool:
        return _TWEAK_KEY in self._browser.selected

    @property
    def detail_text(self) -> str:
        return self._browser.detail_text

    # -- messages from the browser -----------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        event.stop()
        self.status.clear()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if self.applied or not self._entries:  # nothing to uninstall: keep the standing message
            return
        if not event.ids:
            self.status.set("Select at least one item to remove.", "warn")
            return
        self.app.push_screen(
            ConfirmUninstall(self._accept_summary(event.ids)),
            self._on_confirm(event.ids),
        )

    def _accept_summary(self, ids: list[str]) -> str:
        tool_count = sum(1 for key in ids if key not in _ENV_KEYS)
        parts: list[str] = []
        if tool_count:
            parts.append(f"{tool_count} tool(s)")
        if _BAN_KEY in ids:
            parts.append("the pip/npm ban")
        if _BLOCK_KEY in ids:
            parts.append("the PATH wiring")
        if _TWEAK_KEY in ids:
            parts.append("the shell tweaks")
        return ", ".join(parts)

    def _on_confirm(self, ids: list[str]) -> Callable[[bool | None], None]:
        # Callable[[bool | None], None] is the correct pyright-strict type:
        # ScreenResultCallbackType (textual/screen.py:83) passes Optional[ScreenResultType]
        # to the callback, i.e. bool | None for ModalScreen[bool].
        def run(confirmed: bool | None) -> None:
            if confirmed:
                self._apply_removal(ids)

        return run

    def _apply_removal(self, ids: list[str]) -> None:
        paths: list[Path] = []
        for key in ids:
            paths.extend(self._by_key[key].paths)
        decision = UninstallDecision(
            paths=tuple(paths),
            remove_ban=self.remove_ban,
            remove_path_block=self.remove_path_block,
            remove_tweaks=self.remove_tweaks,
        )
        swept, self.error = run_live(lambda: self._remove(decision))
        if swept is None:
            self.status.set(
                f"Uninstall failed: {self.error}. Check permissions, then press enter.",
                "error",
            )
            return
        self.applied = True
        tool_count = sum(1 for key in ids if key not in _ENV_KEYS)
        self.status.set(self._applied_summary(tool_count, swept), "ok")

    def _applied_summary(self, tool_count: int, swept: SweepResult) -> str:
        parts: list[str] = []
        if tool_count:
            parts.append(f"Removed {tool_count} tool(s).")
        if self.remove_ban:
            parts.append(
                "pip/npm ban removed — open a new shell or run `hash -r` so cached"
                " command paths refresh."
            )
        if self.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        if self.remove_tweaks:
            # From the sweep's own result, never from the row's snapshot: the
            # snapshot describes what was offered, not what came off.
            if swept.swept:
                parts.append(
                    f"shell tweaks disabled ({', '.join(swept.swept)}) — open a new "
                    "shell so functions and aliases refresh."
                )
            if swept.failed:
                parts.append(
                    f"could not disable {', '.join(swept.failed)} — check permissions and re-run."
                )
            if not swept.swept and not swept.failed:
                parts.append("no shell tweaks were still enabled — nothing to disable.")
        # One line per outcome: a single joined line overflows the terminal width and
        # truncates the reload guidance, so the "needs a new shell" steps go unseen.
        return multiline_summary(parts)


class PoliciesScreen(AppScreen):
    """Toggle environment policies (the pip/npm ban) on/off, applied live.

    Each toggle is an immediate, idempotent, reversible mutation — there is no
    select-then-commit step. `space` toggles the highlighted policy (matching the
    "act on this row" meaning of `space` in the catalog/uninstall browsers);
    `enter` is inert here because there is no staged batch to commit.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_policy", "toggle policy", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    PoliciesScreen DataTable { height: 1fr; }
    PoliciesScreen #policy-detail {
        height: 11; padding: 0 1; background: $surface; overflow-y: auto;
    }
    """

    def __init__(self, inputs: PolicyInputs) -> None:
        super().__init__(view="policies")
        self._policies = inputs.policies
        self.active_state: dict[str, bool] = {
            policy.id: policy.active for policy in inputs.policies
        }
        self.error: str | None = None
        self.detail_text = ""

    def compose_body(self) -> ComposeResult:
        yield DataTable()
        yield Static("", id="policy-detail")

    def on_mount(self) -> None:
        table = self.query_one(DataTable[Any])
        table.cursor_type = "row"
        table.add_column("State", key="state")
        table.add_column("Policy", key="policy")
        table.add_column("Requires", key="requires")
        table.add_column("Effect", key="effect")
        for policy in self._policies:
            table.add_row(
                self._state_cell(self.active_state[policy.id]),
                Text(policy.label, style="bold yellow"),
                self._requires_cell(policy),
                Text(f"shell config: {policy.description}", style="dim"),
                key=policy.id,
            )
        table.focus()
        self._set_detail(self._policies[0] if self._policies else None)

    def _state_cell(self, active: bool) -> Text:
        # A ●/○ glyph carries the state independent of color: the lone row is
        # always focused, so the selection highlight flattens the green/dim cue.
        label = "● [on]" if active else "○ [off]"
        return Text(label, style="green" if active else "dim")

    def _requires_cell(self, policy: Policy) -> Text:
        if policy.missing_requires:
            return Text("missing: " + ", ".join(policy.missing_requires), style="bold yellow")
        if policy.requires:
            return Text(", ".join(policy.requires), style="dim")
        return Text("none", style="dim")

    def _highlighted_policy(self) -> Policy | None:
        # highlighted_key is None on an empty table, matching no policy id.
        policy_id = highlighted_key(self.query_one(DataTable[Any]))
        return next((policy for policy in self._policies if policy.id == policy_id), None)

    def _policy_detail(self, policy: Policy) -> str:
        details = {
            "ban": (
                "Blocks bare pip and pip3, redirects npx to pnpm dlx, and routes"
                " npm/pnpm global installs to volta install.",
                "Wraps your pnpm binary with a PATH shim: only global adds are"
                " rerouted, every other pnpm command passes straight through.",
                "Global installs then run npm's install scripts unrestricted, which"
                " pnpm gates — keep untrusted packages on a project-local pnpm add.",
                "Writes PATH shims plus interactive aliases, then asks for a shell reload.",
                "Use when humans or agents keep reaching for unmanaged package installers.",
            ),
            "tweak:docker": (
                "Adds docker-ps, a watch-powered live table of names, status, and ports.",
                "Adds docker-stats and docker-memory for quick memory inspection.",
                "Install the catalog's watch tool first when your platform does not ship it.",
            ),
            "tweak:countdown": (
                "Adds wait_time for seconds, 1d10m15s, 23h 49m, 10am, tomorrow 10am,"
                " and compact dates.",
                "Use wait_time --seconds to preview the parsed delay without sleeping.",
                "Requires uv at runtime so the Python helper runs through the managed toolchain.",
            ),
            "tweak:claude-skip": (
                "Aliases claude to claude --dangerously-skip-permissions.",
                "Useful only in trusted, disposable workspaces where confirmation prompts are"
                " intentional noise.",
                "Disable it when you need normal Claude Code permission prompts back.",
            ),
            "tweak:codex-skip": (
                "Aliases codex to codex --dangerously-bypass-approvals-and-sandbox.",
                "Useful only in trusted, disposable workspaces where confirmation and sandbox"
                " prompts are intentional noise.",
                "Disable it when you need normal Codex confirmation/sandboxing prompts back.",
            ),
            "tweak:opencode-auto": (
                "Aliases opencode to opencode --auto.",
                "Narrower than claude-skip's/codex-skip's full bypass: explicit deny rules in"
                " your own opencode config still apply.",
                "Disable it when you want normal per-permission prompting back.",
            ),
            "tweak:cursor-agent-model": (
                "Injects --model gpt-5.6-sol-high into a bare cursor-agent/cursor call, and"
                " never overrides an already-passed --model (either --model X or --model=X).",
                "This tweak only requests, per Cursor's own headless-mode changelog fix, this"
                " model's full context — this installer does not independently verify the"
                " context window reached in a given response.",
                "Requires a Cursor plan that actually includes this model; an unsupported plan"
                " may error or silently downgrade.",
                "Enabling this tweak automatically removes (via unalias) a cursor-agent/cursor"
                " alias that is active before this block loads — not any alias anywhere in your"
                " config — so the tweak's own function takes effect over whatever was defined"
                " earlier. A same-named alias or function defined later in your own sourced"
                " files still wins, since shell source order — not unalias — controls the final"
                " definition.",
                "Disable it to keep using whatever model was last selected.",
            ),
            "tweak:apt-upgrade": (
                "Adds apt-upgrade for upgrading only packages that already have updates.",
                "Keeps the command narrower than a broad apt upgrade flow.",
                "Offered on Linux only; it is harmless until run on an apt-based distro.",
            ),
            "omz-plugins": (
                "Adds Oh-My-Zsh's bundled git and docker plugins to the"
                " plugins=(...) array in ~/.zshrc.",
                "Disabling removes only the names this enable actually added — a"
                " plugin you put in that array yourself is never touched.",
                "Needs Oh-My-Zsh installed; only the single-line plugins=(...) form is edited.",
                "Reads ON only once this installer has enabled it, so a"
                " plugins=(git docker) you wrote by hand shows OFF and is left alone.",
            ),
        }
        lines = [f"{policy.label} — {policy.description}"]
        if policy.missing_requires:
            lines.append(
                "Missing required tool(s): "
                f"{', '.join(policy.missing_requires)}. Install from Catalog before enabling."
            )
        elif policy.requires:
            lines.append(f"Required tool(s): {', '.join(policy.requires)}.")
        lines.extend(details.get(policy.id, ("Space toggles this reversible shell policy.",)))
        if policy.id.startswith("tweak:"):
            lines.append(
                "This alias/function needs ~/.myshellrc to be sourced; in split PATH mode,"
                " enabling this Policy also wires that sourcing into your rc files"
                " automatically, so it still works after your next new shell."
            )
        return "\n".join(lines)

    def _set_detail(self, policy: Policy | None) -> None:
        self.detail_text = "" if policy is None else self._policy_detail(policy)
        self.query_one("#policy-detail", Static).update(Text(self.detail_text))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        policy = next((item for item in self._policies if item.id == event.row_key.value), None)
        self._set_detail(policy)

    def action_toggle_policy(self) -> None:
        policy = self._highlighted_policy()
        if policy is None:
            return
        active = self.active_state[policy.id]
        if not active and policy.missing_requires:
            self.status.set(
                "Install required tool(s) first: "
                f"{', '.join(policy.missing_requires)}. Open Catalog, install them, then retry.",
                "warn",
            )
            self._set_detail(policy)
            return
        result, self.error = run_live(policy.remove if active else policy.apply)
        if result is None:
            self.status.set(
                f"Policy change failed: {self.error}. Check permissions, then press space.",
                "error",
            )
            return
        new_active = not active
        self.active_state[policy.id] = new_active
        self.query_one(DataTable[Any]).update_cell(policy.id, "state", self._state_cell(new_active))
        self._set_detail(policy)
        verb = "enabled" if new_active else "disabled"
        self.status.set(self._summary(policy, verb, result), "ok")

    def _summary(self, policy: Policy, verb: str, result: PolicyResult) -> str:
        # One line per outcome: a single joined line overflows the terminal width
        # and truncates the reload guidance (the Phase 3 fix).
        parts = [f"{policy.label} {verb}."]
        parts.extend(f"{layer.name}: {layer.detail}" for layer in result.layers)
        if result.reload_hint:
            parts.append(result.reload_hint)
        if result.warning:
            parts.append(result.warning)
        return multiline_summary(parts)


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
    ConfirmUninstall > Static { width: 60; border: round red; padding: 1 2; }
    """

    def __init__(self, summary: str) -> None:
        super().__init__()
        self.summary = summary  # public test seam

    def compose(self) -> ComposeResult:
        yield Static(
            Text.from_markup(
                f"[bold red]Remove {self.summary}?[/]\n\n"
                "This deletes installed artifacts and is not undoable.\n"
                "[dim]enter remove · esc cancel[/]"
            )
        )

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


class UnifiedApp(App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        # ctrl+c is the hard abort: unguarded, so it quits from anywhere — even on
        # top of the NavScreen modal. q is the soft quit: priority so it fires on
        # every view, but guarded (see action_abort) to no-op under the palette.
        Binding("ctrl+c", "hard_abort", "quit", show=False, priority=True),
        Binding("q", "abort", "quit", show=True, priority=True),
        # esc is NOT priority: NavScreen's own escape->cancel must win while the
        # palette is open; elsewhere no screen binds escape, so it bubbles to back.
        Binding("escape", "back", "back", show=True),
        Binding("ctrl+p", "open_nav", "navigate", priority=True),
        *[
            Binding(str(i + 1), f"show('{name}')", name, priority=True)
            for i, name in enumerate(VIEW_ORDER)
        ],
    ]

    def __init__(
        self,
        tools: list[Tool],
        installed: Mapping[str, bool],
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        guard_state: Callable[[], tuple[dict[str, bool], str | None]],
        fix_preview: str,
        fix: Callable[[], None],
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        node_globals: Callable[[], NodeGlobalsReport] | None = None,
        globals_preview: Callable[[NodeGlobalsReport], str] | None = None,
        reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
        unavailable: Mapping[str, bool] | None = None,
        initial_view: str = BASE_VIEW,
    ) -> None:
        super().__init__()
        self._staged: set[str] = set()
        self._catalogs: dict[str, CatalogScreen] = {
            tier.value: CatalogScreen(
                [tool for tool in tools if tool.tier == tier],
                installed,
                blurbs,
                view=tier.value,
                catalog=list(tools),
                staged=self._staged,
                unavailable=unavailable or {},
            )
            for tier in Tier
        }
        # Non-base views, installed on mount and pushed by value.
        self._views: dict[str, AppScreen] = {
            name: screen for name, screen in self._catalogs.items() if name != BASE_VIEW
        }
        # Nine UnifiedApp(...) constructions exist outside setup.py. Required
        # kwargs would TypeError at every one of them; those modules are
        # deliberately not edited here. The cost of the default is that a
        # UnifiedApp built without the closures silently reports a healthy set,
        # so setup.py wiring is what makes the feature real in production.
        read_node_globals = (
            node_globals
            if node_globals is not None
            else (lambda: NodeGlobalsReport(entries=(), missing=(), managed=()))
        )

        def _default_preview(report: NodeGlobalsReport) -> str:
            return reinstall_preview(report.managed, known=report.known)

        def _no_reinstall(_packages: Sequence[str]) -> tuple[str, ...]:
            return ()

        read_preview = globals_preview if globals_preview is not None else _default_preview
        run_reinstall = reinstall_globals if reinstall_globals is not None else _no_reinstall
        self._views.update(
            {
                "doctor": DoctorScreen(
                    report,
                    guard_state,
                    fix_preview,
                    fix,
                    node_globals=read_node_globals,
                    globals_preview=read_preview,
                    reinstall_globals=run_reinstall,
                ),
                "uninstall": UninstallScreen(uninstall),
                "policies": PoliciesScreen(policies),
            }
        )
        self._initial_view = initial_view
        self.current_view = BASE_VIEW

    # Textual annotates install_screen with a bare (unparameterized) Screen, which
    # pyright-strict reports as partially unknown at the call site. Re-declare it
    # precisely for type checking only — zero runtime cost, no suppression — the
    # same pattern as the UninstallScreen.app narrowing above.
    if TYPE_CHECKING:

        def install_screen(self, screen: Screen[None], name: str) -> None: ...

    async def on_mount(self) -> None:
        # Install every view screen: an installed screen is SUSPENDED when popped;
        # an uninstalled one is REMOVED (App._replace_screen) — its whole widget
        # tree destroyed. Re-pushing the same instance then re-composes onto stale
        # state: pending callbacks lose their widgets, and screen.focused can point
        # at a detached widget, collapsing the binding chain so the App's priority
        # number keys stop matching — later keys in a fast burst were silently
        # dropped (the "press 2 for Doctor but land elsewhere" bug). The catalog
        # needs no install: it is the base screen and is never popped.
        for name, screen in self._views.items():
            self.install_screen(screen, name)
        if self._initial_view != BASE_VIEW:
            await self.show_view(self._initial_view)

    @property
    def catalog(self) -> CatalogScreen:
        """The base (first-registered tier) screen."""
        return self._catalogs[BASE_VIEW]

    def catalog_for(self, view: str) -> CatalogScreen:
        """Headless-test seam for the two non-base tier screens."""
        return self._catalogs[view]

    def get_default_screen(self) -> CatalogScreen:
        # The first registered tier is the app's base screen, so App-level queries
        # (the tests' app.query_one) resolve against it. It reports its decision
        # via the Decided message rather than dismissing the only screen on the stack.
        return self._catalogs[BASE_VIEW]

    async def show_view(self, name: str) -> None:
        # Await each stack mutation so a transition fully settles before the next
        # runs: this prevents a queued second nav from popping/pushing onto an
        # in-flight stack and breaking the [catalog] / [catalog, <view>] invariant.
        if name == self.current_view:
            return
        # An actual view change ends the selection moment the view being left was
        # describing, so its transient prompt/notice go with it. This is the one
        # navigation path (.claude/architecture.md rule 2), which makes it the only
        # correct trigger: a screen-suspend handler would also fire for the nav
        # palette opening on top, wiping state for a view the user never left.
        leaving = self._catalogs.get(self.current_view)
        if leaving is not None:
            leaving.clear_transient()
        if self.current_view != BASE_VIEW:
            await self.pop_screen()
        if name != BASE_VIEW:
            entering = self._views[name]
            # The single navigation path is also the single refresh point: a
            # view holding state another view can change live re-derives it
            # here, before it is shown (rule 2).
            entering.enter_view()
            await self.push_screen(entering)
        self.current_view = name

    def _navigable(self) -> bool:
        # ctrl+p and the number keys are priority App bindings, so they fire even
        # while a NavScreen modal is open. Navigate only when the catalog or a
        # placeholder is the active screen — never on top of the palette, which
        # would push onto a live modal and break the [catalog] / [catalog, <view>]
        # stack invariant.
        return self.screen is self._catalogs[BASE_VIEW] or self.screen in self._views.values()

    async def action_show(self, name: str) -> None:
        if not self._navigable():
            return
        await self.show_view(name)

    async def on_wayfinding_header_navigate(self, event: WayfindingHeader.Navigate) -> None:
        event.stop()
        if self._navigable():
            await self.show_view(event.view)

    async def action_back(self) -> None:
        # One-deep stack: from a pushed view, esc goes home to the catalog; on the
        # catalog itself there is nowhere further back, so esc is inert. async to
        # match App.action_back's signature (pyright-strict rejects a sync override).
        if self._navigable() and self.current_view != BASE_VIEW:
            await self.show_view(BASE_VIEW)

    def action_open_nav(self) -> None:
        if not self._navigable():
            return
        self.push_screen(NavScreen(), self._navigate)

    async def _navigate(self, name: str | None) -> None:
        # Textual awaits async screen-result callbacks: textual/screen.py:83 defines
        # ScreenResultCallbackType as a Union including Callable[[Optional[T]], Awaitable[None]],
        # and textual/_callback.py's invoke does `if isawaitable(result): result = await result`.
        # Using async here means the pilot awaits this callback fully before resuming, so
        # palette tests asserting current_view immediately after enter do not need pilot.pause().
        if name is not None:
            await self.show_view(name)

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        self.exit(message.result)

    def action_abort(self) -> None:
        # The soft quit (q). Guarded so a priority q binding does not quit out from
        # under the NavScreen palette; ctrl+c (action_hard_abort) stays unguarded.
        if not self._navigable():
            return
        self.exit(None)

    def action_hard_abort(self) -> None:
        # The hard quit (ctrl+c): always exits, including on top of the palette.
        self.exit(None)
