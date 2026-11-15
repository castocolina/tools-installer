"""Unified Textual shell hosting the wizard views behind one app.

The app owns navigation and the screen stack. The base view, doctor, uninstall,
and policies are all functional views. Execution stays behind the pure
`installer/` core invoked from `setup.py`, with one deliberate exception: the
doctor, uninstall, and policies views apply their changes live through
injected closures. The app's run value stays the catalog decision
(`list[str] | None`).

Textual's empty default screen is the neutral root; every view is installed
once and reached through `show_view`. Navigation is therefore a stack with the
root at the bottom: the stack is always `[root, <one view>]` once mounted.
"""

import contextlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.app import App
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import Screen
from textual.worker import Worker, WorkerCancelled, WorkerFailed

from installer import schedules
from installer.app import (
    path_writer_lines_for,
)
from installer.catalog_tui import CatalogScreen, RefreshRequested, ToolUpdated
from installer.doctor import DoctorReport
from installer.doctor_screen import DoctorScreen
from installer.enums import MutationHolder, Severity, Tier
from installer.execute_screen import (
    ExecuteInputs,
    ExecuteScreen,
    InstallRunFinished,
    InstallRunStarted,
)
from installer.modals import (
    LinkModeScreen,
    NavScreen,
)
from installer.model import Tool
from installer.mutation_lock import MutationLock
from installer.pnpm_globals import (
    NodeGlobalsReport,
    reinstall_preview,
)
from installer.policies_screen import PoliciesScreen, PolicyInputs, link_mode_status
from installer.policy import (
    move_link_mode,
)
from installer.rcclean import group_writer_lines
from installer.resolve import UnavailableReason
from installer.schedules_screen import ScheduleInputs, SchedulesScreen
from installer.session import (
    Disposition,
    PlanRow,
    RowOutcome,
    first_line,
    ran_anything,
    retained,
)
from installer.shellrc import guard_path_writers
from installer.terminal_shell import terminal_sync_warning
from installer.ui_common import (
    BASE_VIEW,
    VIEW_ORDER,
    AppScreen,
    WayfindingHeader,
    run_live,
)
from installer.uninstall_review import UninstallInputs
from installer.uninstall_screen import UninstallScreen
from installer.update import UpdateService
from installer.version_status import (
    VersionRefreshService,
)

_REMOVAL_QUIT_WAIT = "Waiting for the removal to finish…"
_REMOVAL_QUIT_CUT = "Quit before the removal finished; some files may remain."


class ScheduleDefaultsApplied(Message):
    """The threaded schedule-defaults reconcile finished; `report` is what it did (an empty
    report when it did nothing or raised).

    Posted unconditionally from UnifiedApp's own worker, in a finally block,
    regardless of outcome -- mirroring GlobalsAudited/GlobalsReinstalled's same
    thread -> post_message hand-off shape, for the identical reason: widgets
    may only be touched from the app's own thread.
    """

    def __init__(self, report: schedules.ReconcileReport) -> None:
        self.report = report
        super().__init__()


class RefreshPublished(Message):
    """The refresh worker published a pass. `error` is the pass's first error;
    a clean publication means the pass succeeded."""

    def __init__(self, error: str | None, warning: str | None) -> None:
        super().__init__()
        self.error = error
        self.warning = warning


class RefreshFinished(Message):
    """The refresh worker ended; `error` is the pass's first failure, if any."""

    def __init__(self, error: str | None) -> None:
        super().__init__()
        self.error = error


class UnifiedApp(MutationLock, App[list[str] | None]):
    """One app hosting the wizard views. run() returns the catalog selection
    (ids in catalog order) on accept, or None when aborted. `current_view` and
    `catalog` are public for headless tests."""

    ENABLE_COMMAND_PALETTE = False  # replace Textual's dead-ending default palette
    BINDINGS: ClassVar[list[BindingType]] = [
        # ctrl+c is the hard abort: unconditional, so it quits from anywhere — even on
        # top of the NavScreen modal; during a removal the first one waits and a
        # second one exits (D-10, C-26). q is the soft quit: priority so it fires on
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
        blurbs: Mapping[str, str],
        *,
        report: DoctorReport,
        fix_preview: str | Callable[[], str],
        fix: Callable[[], None],
        uninstall: UninstallInputs,
        policies: PolicyInputs,
        schedules: ScheduleInputs | None = None,
        node_globals: Callable[[], NodeGlobalsReport] | None = None,
        globals_preview: Callable[[NodeGlobalsReport], str] | None = None,
        reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
        unavailable: Mapping[str, bool | UnavailableReason] | None = None,
        initial_view: str = BASE_VIEW,
        schedule_defaults: Callable[[], schedules.ReconcileReport] | None = None,
        version_refresh: VersionRefreshService | None = None,
        updates: UpdateService | None = None,
        execute: ExecuteInputs | None = None,
        prompt_link_mode: bool = False,
        terminal_sync: Callable[[], str | None] | None = None,
        startup_warning: str | None = None,
    ) -> None:
        super().__init__()
        self._staged: set[str] = set()
        self._execute = execute
        self._prompt_link_mode = prompt_link_mode
        self._set_link_mode = policies.set_link_mode
        self._read_link_mode = policies.link_mode
        self._link_mode_prompted = False
        # A first-run pick made while the launch schedule setup held the lock;
        # on_schedule_defaults_applied moves it (C-18).
        self._deferred_link_mode: str | None = None
        # The exit code answers "did everything this session asked for succeed":
        # the latest outcome per tool id wins, so a cancel followed by a retry
        # never leaks an earlier not_attempted. None until the first run finishes.
        self.outcomes: dict[str, RowOutcome] | None = None
        # A crash or a PATH/verify failure that no row outcome carries (L-20-08).
        self.run_errors: list[str] = []
        # WR-06: set by InstallRunStarted (ExecuteScreen.action_start),
        # cleared by on_install_run_finished. A hard abort inside the window
        # exits before the finish message can arrive, so the flag is the only
        # witness that the session was interrupted mid-run -- and the exit
        # code must treat that as a failure, never a clean abort.
        self.run_in_flight: bool = False
        self._version_refresh = version_refresh
        self._updates = updates
        # D-05: one full-catalog pass at a time; a request during a pass sets
        # pending and the finish handler runs exactly one more. Both flags live
        # on the event loop (the worker thread only posts messages).
        self._tools = list(tools)
        self._refresh_running = False
        self._refresh_pending = False
        # Callbacks waiting for the next publication; served once no pass is pending.
        self._publication_waiters: list[Callable[[str | None], None]] = []
        # The app's own state line: (screen, shown text, the text a retraction
        # restores), or (None, line, "") while it waits in _pending_warnings.
        # A clean publish clears only its own line, never one a view wrote.
        self._state_line: tuple[AppScreen | None, str, str] | None = None
        # D-01/15.6-06: the SAME composition-root closure Plans 04/05 wired for
        # Policies' OMZ-plugin apply and the direct `u` update -- called from
        # _install_closed on EVERY close event, never only a selected tool id
        # or a successful outcome. None at every one of the fifteen other
        # UnifiedApp(...) construction sites outside setup.py, matching the
        # default-no-op contract every other optional closure here already has.
        self._terminal_sync = terminal_sync
        # T-15.6-13: a follow-up warning that arrived while no AppScreen was
        # resolvable (current_view names neither a tier nor a registered view)
        # is queued here rather than dropped, and flushed to the next screen
        # that becomes visible (show_view) or the next _install_closed render.
        self._pending_warnings: list[str] = []
        # D-11: a damaged settings.json reaches the first screen through the
        # SAME T-15.6-13 queue as every other warning, never a side channel.
        self._startup_warning = startup_warning
        if startup_warning is not None:
            self._pending_warnings.append(startup_warning)
        # Set by on_install_run_finished when the post-run cache invalidation
        # fails, consumed (and cleared) by the _install_closed that follows:
        # the execute screen is still on top when the failure happens, so
        # there is no catalog status line to write to yet.
        self._invalidate_warning: str | None = None
        # D-04: no tier keeps a presence copy. Each tier renders from the one
        # tool state (`state_of`); a mutation invalidates its epoch, rows read
        # `…`, and the next refresh pass repaints every tier in one swap. So an
        # install close and a view switch only re-enter (`enter_view`); nothing
        # sweeps the presence predicate over the catalog.
        self._catalogs: dict[str, CatalogScreen] = {
            tier.value: CatalogScreen(
                [tool for tool in tools if tool.tier == tier],
                blurbs,
                view=tier.value,
                catalog=list(tools),
                staged=self._staged,
                unavailable=unavailable or {},
                version_refresh=version_refresh,
                updates=updates,
            )
            for tier in Tier
        }
        # Every view, installed on mount and pushed by value (tiers first).
        self._views: dict[str, AppScreen] = dict(self._catalogs)
        # Fifteen UnifiedApp(...) constructions exist outside setup.py. Required
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
        writer_lines = path_writer_lines_for(report)
        self._views.update(
            {
                "doctor": DoctorScreen(
                    report,
                    fix_preview,
                    fix,
                    duplicate_writers=group_writer_lines(writer_lines),
                    writer_lines=writer_lines,
                    rescan_writer_lines=lambda: path_writer_lines_for(report),
                    guard_file=guard_path_writers,
                    node_globals=read_node_globals,
                    globals_preview=read_preview,
                    reinstall_globals=run_reinstall,
                    # Read off PolicyInputs rather than a new UnifiedApp
                    # parameter, on purpose: PolicyInputs already exists to
                    # carry composition-root closures to the screens, and a
                    # parallel kwarg would make every UnifiedApp(...) site in
                    # the tests grow an argument for a value with a home.
                    # PoliciesScreen reads the same field, so one closure
                    # reaches both screens.
                    disk_pressure=policies.disk_pressure,
                    competing=policies.competing,
                    tools=self._tools,
                    version_refresh=version_refresh,
                ),
                "uninstall": UninstallScreen(
                    uninstall, tools=self._tools, version_refresh=version_refresh
                ),
                "policies": PoliciesScreen(policies),
                "schedules": SchedulesScreen(schedules or ScheduleInputs(context=None)),
            }
        )
        self._initial_view = initial_view
        # "" is the root sentinel: on_mount's show_view is never an early return.
        self.current_view = ""
        self._schedule_defaults = schedule_defaults
        # Held from construction whenever a real reconcile callback was wired,
        # so there is no window between __init__ and the worker starting in
        # on_mount where a mutation could slip in (11-REVIEWS.md cycle 2
        # finding #15). on_schedule_defaults_applied releases it.
        if self._schedule_defaults is not None:
            self.begin_mutation(MutationHolder.SCHEDULE_DEFAULTS)
        # True once a quit waits on a running removal: no follow-up pass then.
        self.quitting = False

    # Textual annotates install_screen with a bare (unparameterized) Screen, which
    # pyright-strict reports as partially unknown at the call site. Re-declare it
    # precisely for type checking only — zero runtime cost, no suppression — the
    # same pattern as the UninstallScreen.app narrowing above.
    if TYPE_CHECKING:

        def install_screen(self, screen: Screen[None], name: str) -> None: ...

    async def on_mount(self) -> None:
        # Install every view: an installed screen is SUSPENDED when popped; an
        # uninstalled one is REMOVED (App._replace_screen) and re-pushing it
        # re-composes onto stale state, dropping later keys in a fast burst. The
        # empty default screen is the neutral root under all of them.
        for name, screen in self._views.items():
            self.install_screen(screen, name)
        await self.show_view(self._initial_view)
        if self._schedule_defaults is not None:
            self._apply_schedule_defaults_worker()
        # Last in on_mount so a first-run user answers exactly one question;
        # the schedule worker's completion status lands behind this picker, not
        # on top of it.
        if (
            self._prompt_link_mode
            and self._set_link_mode is not None
            and not self._link_mode_prompted
        ):
            self._link_mode_prompted = True
            self.push_screen(LinkModeScreen(), self._first_link_mode_picked)
        self.request_refresh()  # the launch pass

    def request_refresh(self) -> None:
        """Run one full-catalog refresh pass, or queue exactly one more behind
        the running one (D-05). No service: nothing to refresh."""
        if self._version_refresh is None:
            return
        if self._refresh_running:
            self._refresh_pending = True
            return
        self._refresh_running = True
        self._refresh_worker()

    def await_publication(self, callback: Callable[[str | None], None]) -> None:
        """Call `callback(error)` once a pass has finished with none pending: a
        running pass is joined, otherwise one starts. No service: answer at once."""
        if self._version_refresh is None:
            callback(None)
            return
        self._publication_waiters.append(callback)
        if not self._refresh_running:
            self.request_refresh()

    @work(thread=True, exclusive=True, group="full-catalog-refresh", exit_on_error=False)
    def _refresh_worker(self) -> None:
        service = self._version_refresh
        pass_error: str | None = "state check did not complete"
        try:
            if service is not None:
                _result, error = run_live(lambda: service.refresh(self._tools))
                self.post_message(
                    RefreshPublished(error, service.warning if error is None else None)
                )
                pass_error = error
        except Exception as exc:
            pass_error = first_line(exc)
            # The one status path: an unexpected failure shows the retry copy too.
            self.post_message(RefreshPublished(pass_error, None))
        finally:
            self.post_message(RefreshFinished(pass_error))

    def on_refresh_published(self, message: RefreshPublished) -> None:
        self._render_published()
        line: str | None = None
        if message.error is not None:
            line = f"tool state check failed: {message.error} — the next change retries it"
        elif message.warning is not None:
            line = f"{message.warning} — marks are current; the next start checks again"
        self._write_state_line(line)

    def on_refresh_finished(self, message: RefreshFinished) -> None:
        self._refresh_running = False
        pending, self._refresh_pending = self._refresh_pending, False
        # A shutdown or a quit in progress drops the queued pass; waiters still hear.
        if pending and self.is_running and not self.quitting:
            self.request_refresh()
            return
        waiters, self._publication_waiters = self._publication_waiters, []
        for waiter in waiters:
            waiter(message.error)

    def _render_published(self) -> None:
        """Re-render the visible view only (D-06); a view under a modal renders
        the published state when the modal closes (`AppScreen.on_screen_resume`)."""
        screen = self._visible_app_screen()
        if screen is not None:
            screen.state_refreshed()

    def unstage(self, ids: Iterable[str]) -> None:
        """Drop removed tools from the tiers' shared selection (in place: the
        tier browsers hold this set)."""
        self._staged.difference_update(ids)

    def show_result(
        self,
        origin: AppScreen,
        text: str,
        severity: Severity | str,
        *,
        elsewhere: str | None = None,
    ) -> None:
        """Write a mutation's result where the user is looking (C-28): on the
        current view, which is `origin` unless the user left it meanwhile.
        `elsewhere` replaces `text` on another view when `text` names a key
        only `origin` handles."""
        screen = self._views.get(self.current_view, origin)
        if elsewhere is not None and screen is not origin:
            text = elsewhere
        screen.status.set(text, severity)

    def _write_state_line(self, line: str | None) -> None:
        """Replace the app's previous state line with `line` (None: retract it).
        It is written over an empty status only; a status another writer left
        stands, and the line waits in _pending_warnings for the next entry."""
        previous, self._state_line = self._state_line, None
        if previous is not None:
            where, shown, rest = previous
            if where is None:
                if shown in self._pending_warnings:
                    self._pending_warnings.remove(shown)
            elif where.status.text == shown:
                if rest:
                    where.status.set(rest, "warn")
                else:
                    where.status.clear()
        if line is None:
            return
        screen = self._visible_app_screen()
        if screen is None or screen.status.text:
            if line not in self._pending_warnings:
                self._pending_warnings.append(line)
            self._state_line = (None, line, "")
            return
        # Plain text through StatusLine.set, never markup (T-19-40).
        screen.status.set(line, "warn")
        self._state_line = (screen, line, "")

    # exit_on_error=False (Textual's own worker.py defaults this True, which
    # calls App._handle_exception -- crashing the whole app -- on any
    # exception a threaded worker raises): an exception from the reconcile must
    # still leave a usable, running app (the finally block below already
    # guarantees the lock releases); Worker.state/.error still record
    # it for diagnosis, this only suppresses the exit-the-app side effect.
    @work(thread=True, exclusive=True, group="schedule-defaults", exit_on_error=False)
    def _apply_schedule_defaults_worker(self) -> None:
        """Turn on the schedules nobody has decided about, off the event loop.

        Mirrors DoctorScreen._audit_globals_worker/_reinstall_globals_worker's
        own thread-worker + post_message shape, for the identical reason: a
        real systemctl or launchctl call (run_captured's underlying
        subprocess.run has no timeout) must never freeze frame rendering or
        keypress handling. The body is wrapped in try/finally so the
        completion message is ALWAYS posted -- regardless of whether
        self._schedule_defaults() returns normally or raises ANYTHING -- so the
        app mutation lock the constructor (or the install run's end) took can
        never stay held (11-REVIEWS.md cycle 3 finding #15). An exception
        raised inside the try still propagates normally after the finally runs
        and is recorded on the Worker itself (state=ERROR, .error);
        exit_on_error=False is what keeps that from also crashing the app, so
        this only ever ADDS the guaranteed message post, it never swallows or
        hides a genuine bug.
        """
        report = schedules.ReconcileReport()
        try:
            if self._schedule_defaults is not None:
                report = self._schedule_defaults()
        finally:
            self.post_message(ScheduleDefaultsApplied(report))

    def on_schedule_defaults_applied(self, message: ScheduleDefaultsApplied) -> None:
        # Released FIRST, unconditionally: the worker posts this on every
        # outcome, so a crash never leaves the lock held.
        self.end_mutation()
        lines = schedules.reconcile_lines(message.report)
        if lines:
            severity = "warn" if any(kind == "warn" for _text, kind in lines) else "ok"
            self._announce_startup_line(" · ".join(text for text, _kind in lines), severity)
        # The reconcile changes the rows Schedules shows and the tweak rows the
        # Uninstall view lists: repaint whichever view is up, without a pass.
        schedules_screen = self._views.get("schedules")
        if isinstance(schedules_screen, SchedulesScreen) and schedules_screen.is_mounted:
            schedules_screen.state_refreshed()
        if self._visible_app_screen() is not schedules_screen:
            self._render_published()
        value, self._deferred_link_mode = self._deferred_link_mode, None
        if value is not None:
            self._move_first_link_mode(value, self._views.get(self.current_view, self.catalog))

    def _announce_startup_line(self, text: str, severity: Severity | str) -> None:
        """The reconcile's lines ride the startup-warning path: over an empty status of the
        visible view, else queued for the next view that becomes visible (T-15.6-13)."""
        screen = self._visible_app_screen()
        if screen is None or screen.status.text:
            self._pending_warnings.append(text)
            return
        screen.status.set(text, severity)

    @property
    def catalog(self) -> CatalogScreen:
        """The base (first-registered tier) screen."""
        return self._catalogs[BASE_VIEW]

    def catalog_for(self, view: str) -> CatalogScreen:
        """Headless-test seam for the two non-base tier screens."""
        return self._catalogs[view]

    def view(self, name: str) -> AppScreen:
        """Headless-test seam: the installed screen for any of the six views."""
        return self._views[name]

    async def show_view(self, name: str) -> None:
        # Await each stack mutation so a transition fully settles before the next
        # runs: the stack stays [root, <one view>].
        if name == self.current_view:
            return
        # This is the one navigation path (.claude/architecture.md rule 2), so it
        # is the only correct place to end the leaving view's transient state.
        leaving = self._views.get(self.current_view)
        if leaving is not None:
            leaving.clear_transient()
            await self.pop_screen()
        target = self._views[name]
        await self.push_screen(target)
        self.current_view = name
        # Flush before entry: a status written by enter_view wins over a queued
        # warning. T-15.6-13: also where an early warning is finally delivered.
        self._flush_pending_warnings(target)
        target.enter_view()

    def _flush_pending_warnings(self, screen: AppScreen, extra: Sequence[str] = ()) -> None:
        """Write the queued warnings (and `extra`) on one line of `screen`. A
        queued state line moves with them, so a clean publish still retracts it
        (RR-02), leaving the other warnings standing."""
        parts = [*self._pending_warnings, *extra]
        self._pending_warnings = []
        if not parts:
            return
        text = " · ".join(parts)
        screen.status.set(text, "warn")
        if self._state_line is not None and self._state_line[0] is None:
            line = self._state_line[1]
            if line in parts:
                rest = " · ".join(part for part in parts if part != line)
                self._state_line = (screen, text, rest)

    def _navigable(self) -> bool:
        # ctrl+p and the number keys are priority App bindings, so they fire even
        # while a NavScreen modal is open. Navigate only when a view is the active
        # screen, never on top of the palette (it would break the stack invariant).
        return self.screen in self._views.values()

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

    def _first_link_mode_picked(self, value: str | None) -> None:
        # make fix opens with initial_view="doctor", so the Doctor AppScreen is
        # on top and the catalog is hidden. Write D-05.3's explanation onto
        # the screen the user is looking at, never a hard catalog fallback:
        # if a future Textual version fired this callback while LinkModeScreen
        # were still current, self.screen would not be an AppScreen and a hard
        # catalog fallback would reintroduce the silent-dismissal defect.
        current = self.screen
        target = (
            current
            if isinstance(current, AppScreen)
            else (self._views.get(self.current_view) or self.catalog)
        )
        if value is None:
            mode = self._read_link_mode() if self._read_link_mode is not None else "centralized"
            policies_key = str(VIEW_ORDER.index("policies") + 1)
            unchanged = (
                f"Link mode unchanged; this run uses {mode}. "
                f"Press {policies_key} then m to change it later."
            )
            # D-11: dismissing the one first-run question must not erase the
            # only notice that the settings file was ignored. Same separator
            # _flush_pending_warnings uses.
            if self._startup_warning is not None:
                unchanged = f"{self._startup_warning} · {unchanged}"
            target.status.set(unchanged, "warn")
            return
        if self._set_link_mode is None:
            return
        # C-18: the launch daemon apply rewrites ~/.myshellrc as the move does,
        # so the pick waits for it instead of making the user answer again. It
        # is the only holder possible here: the picker opens at launch.
        if self.mutation_in_flight:
            self._deferred_link_mode = value
            # The move's own status replaces this line once the apply ends.
            target.status.set(
                f"Link mode {value} will be saved when the background apply finishes.", "warn"
            )
            return
        self._move_first_link_mode(value, target)

    def _move_first_link_mode(self, value: str, target: AppScreen) -> None:
        setter = self._set_link_mode
        if setter is None:
            return
        policies_screen = self._views.get("policies")
        aware_active = (
            policies_screen.link_mode_aware_active()
            if isinstance(policies_screen, PoliciesScreen)
            else []
        )
        old = self._read_link_mode() if self._read_link_mode is not None else "centralized"
        report, error = run_live(lambda: move_link_mode(aware_active, value, setter, old_mode=old))
        if error is not None:
            policies_screen = self._views.get("policies")
            if isinstance(policies_screen, PoliciesScreen):
                policies_screen.mark_lost_policies_off(error)
            target.status.set(error, "error")
            return
        text, severity = link_mode_status(value, report or (), old_mode=old)
        target.status.set(text, severity)
        if isinstance(target, DoctorScreen) and self._visible_app_screen() is target:
            target.enter_view()  # the status survives: enter_view writes none

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        if self._execute is None or message.result is None:
            self.exit(message.result)
            return
        self.push_screen(ExecuteScreen(message.result, self._execute), self._install_closed)

    def _install_closed(self, result: list[RowOutcome] | None) -> None:
        # Only the rows that still need the user stay selected (D-10, L-20-07).
        # intersection_update, never a rebind: the tier browsers hold this set.
        # None (closed before a run) leaves the selection untouched.
        if result is not None:
            self._staged.intersection_update(retained(result))
        # ExecuteScreen is modal: _navigable() returns False while it is on
        # top, so current_view still names the catalog tier the run was
        # launched from, and _catalogs has an entry for every tier including
        # the base one -- no base/non-base branch needed here, unlike
        # show_view (that method branches because it pushes/pops screens;
        # this callback does neither). Presence is re-read by the refresh pass
        # `request_refresh` starts below, never swept here (D-04, see __init__).
        warnings: list[str] = []
        # D-01/15.6-06 Task 1: the shared terminal synchronizer runs after a
        # close event that actually changed installed-tool state -- never
        # only a selected tool id (WR-07: merely opening and dismissing the
        # Execute screen with nothing selected/changed otherwise rewrote
        # kitty.conf, created a brand-new wezterm.lua (CR-03), and wrote
        # konsolerc for a session that installed nothing). The zsh-removal
        # revert case is independently covered by
        # UninstallScreen.on_removal_finished and _run_uninstall, so this gate
        # does not lose coverage for that scenario. Through run_live like
        # every other live core read this callback triggers (rule 3): an
        # OSError is a secondary, non-fatal warning and must never flip an
        # already-recorded run into a reported failure.
        # WR-03: not run_live -- terminal_sync_warning IS this seam's live
        # guard, and routing through both produced the one message whose
        # casing had already drifted from the other four call sites.
        # D-11: the gate is "a row actually ran", so an update counts too.
        if result is not None and ran_anything(result):
            sync_warning = terminal_sync_warning(self._terminal_sync)
            if sync_warning:
                warnings.append(sync_warning)
        # A .get(), not an index: _catalogs is keyed by tier only
        # (system/user/ai) while current_view ranges over all six VIEWS
        # (doctor, uninstall and policies included). Only a catalog tier
        # pushes ExecuteScreen today, but that is one call site's behaviour
        # rather than an enforced invariant -- nothing structurally stops a
        # future caller pushing it with this callback from the uninstall or
        # doctor view -- and a KeyError raised inside a Textual screen-result
        # callback takes the message pump down instead of degrading. No
        # catalog on top means the warnings go to the visible view below.
        active = self._catalogs.get(self.current_view)
        # The revealed view renders itself on resume (C-08); ask for the pass
        # that publishes what the run changed (A11: only if it ran something).
        if result is not None and ran_anything(result):
            self.request_refresh()
        # Both post-run failures land on one line, written after the re-render.
        if self._invalidate_warning is not None:
            warnings.append(self._invalidate_warning)
            self._invalidate_warning = None
        # WR-08: also checks _pending_warnings, not just this close's own
        # `warnings` -- __init__'s own documented contract is that a queued
        # warning flushes on "the next _install_closed render", but a close
        # that produces no NEW warning of its own used to return here before
        # ever reaching the drain below, so a previously-queued warning was
        # never actually delivered by this path -- only a subsequent
        # show_view navigation flushed it.
        if not warnings and not self._pending_warnings:
            return
        # T-15.6-13: render on WHICHEVER AppScreen is actually visible right
        # now -- a catalog tier (active, above) or the Doctor/Uninstall/
        # Policies screen the run was launched over -- never dropped merely
        # because current_view names a non-tier key. Only when no AppScreen
        # is resolvable at all (not reachable in the current call graph) does
        # the warning queue for the next screen that becomes visible.
        visible = active if active is not None else self._visible_app_screen()
        if visible is None:
            self._pending_warnings.extend(warnings)
            return
        self._flush_pending_warnings(visible, warnings)

    def _visible_app_screen(self) -> AppScreen | None:
        # Before mount there is no stack; during shutdown the app stops running
        # before it prunes the screens, and a late pass must not render into them.
        if not self.screen_stack or not self.is_running:
            return None
        screen = self.screen
        return screen if isinstance(screen, AppScreen) else None

    def on_install_run_started(self, message: InstallRunStarted) -> None:
        del message  # its arrival is its whole meaning
        # run_in_flight stays the exit-code witness; the lock is the mutation guard,
        # taken by ExecuteScreen._begin_run before the run starts.
        self.run_in_flight = True

    def on_install_run_finished(self, message: InstallRunFinished) -> None:
        self.end_mutation()
        self.run_in_flight = False
        # SPEC edge R3: a tool this run just installed gets its update schedule in the same
        # session. Taken after the run's own end_mutation, released by the worker's message.
        if self._schedule_defaults is not None:
            self.begin_mutation(MutationHolder.SCHEDULE_DEFAULTS)
            self._apply_schedule_defaults_worker()
        # Every mutation this app performs calls invalidate
        # (installer/version_status.py:26-30's own invariant); the install
        # path was the one mutation that skipped it, so a tool the run just
        # handed to brew/cask/pnpm/uv was resolved against a manager
        # inventory read BEFORE the run for up to MANAGER_STALE_AFTER (6h).
        # Mirrors UpdateService's own call (installer/update.py:436-443) in
        # BOTH directions, which is the whole point of the try/except: a
        # cache-write failure is a post-mutation side effect and must never
        # flip an already-recorded run into a reported failure, AND it is
        # never swallowed. UpdateService folds the failure into
        # outcome.detail; this folds it into the status line the next
        # _install_closed writes, because a silently discarded invalidate
        # means the manager-snapshot staleness this call exists to close
        # comes back for up to MANAGER_STALE_AFTER with nothing on screen.
        # It is also the only thing standing between a future signature
        # change to invalidate() and a feature that quietly stops working.
        #
        # The message is held rather than shown here: ExecuteScreen is still
        # on top at this point (InstallRunFinished is posted from
        # _execute_worker's finally, before the user closes the screen), so
        # the first moment a catalog status line is visible again is the
        # close callback.
        if self._version_refresh is not None and ran_anything(message.outcomes):
            try:
                self._version_refresh.invalidate(reason="install run finished")
            except Exception as exc:  # noqa: BLE001 -- post-mutation side effect, reported below
                self._invalidate_warning = f"version cache invalidation failed: {exc}"
        for outcome in message.outcomes:
            self._record(outcome)
        if ran_anything(message.outcomes) or message.run_error:
            self.run_errors = [
                error
                for error in (message.run_error, message.path_error, message.verify_error)
                if error
            ]

    def on_tool_updated(self, message: ToolUpdated) -> None:
        """opencode H3: a failed DIRECT update (a `u` press on the catalog)
        never reaches an ExecuteScreen, so nothing else would record it and
        the process would exit 0 after a failed update. The failure is folded
        here as a plan-shaped outcome, so _session_exit_code needs no second
        rule. Successful updates record `done`, allowing latest-wins to clear
        an earlier failure; unknown-owner/unsupported refusals record nothing."""
        self.end_mutation()
        failed = message.error is not None or (
            message.outcome is not None and message.outcome.status == "failed"
        )
        if failed:
            detail = message.error or (
                message.outcome.detail if message.outcome is not None else ""
            )
            row = PlanRow(message.tool_id, Disposition.UPDATE, "")
            self._record(RowOutcome(row, "failed", detail=detail))
        elif message.outcome is not None and message.outcome.status == "updated":
            row = PlanRow(message.tool_id, Disposition.UPDATE, "")
            self._record(RowOutcome(row, "done"))
        self._render_published()
        # An update that ran and failed may still have changed the machine.
        self.request_refresh()

    def _record(self, outcome: RowOutcome) -> None:
        """Latest outcome per tool id wins (cancel-then-retry, D-09)."""
        if self.outcomes is None:
            self.outcomes = {}
        self.outcomes[outcome.row.tool_id] = outcome

    def on_refresh_requested(self, message: RefreshRequested) -> None:
        """A refused mutation still ends with one pass (SPEC R2)."""
        del message  # payload-free
        self.request_refresh()

    def action_abort(self) -> None:
        # The soft quit (q). Guarded so a priority q binding does not quit out from
        # under the NavScreen palette; ctrl+c (action_hard_abort) stays unconditional.
        if not self._navigable():
            return
        self._quit()

    async def action_quit(self) -> None:
        # Textual's inherited ctrl+q calls exit() directly, which would abandon a
        # removal's daemon delete thread (RR-01); it is the soft quit, like q.
        self.action_abort()

    def action_hard_abort(self) -> None:
        # The hard quit (ctrl+c): exits from anywhere, including on top of the
        # palette. The first one during a removal waits for it; a second one
        # stops waiting and says the removal may be partial (D-10, C-26).
        if self.quitting and self._mutation_holder is MutationHolder.REMOVAL:
            self.exit(None, message=_REMOVAL_QUIT_CUT)
            return
        self._quit()

    def _quit(self) -> None:
        if self._mutation_holder is MutationHolder.REMOVAL:
            self._exit_after_removal()
        else:
            self.exit(None)

    def _exit_after_removal(self) -> None:
        """Never cut a delete: say so, then exit once the removal worker returns.
        With a modal on top the copy is queued for the next visible view. The wait
        runs on its own worker, so the key handler returns at once and a shutdown
        cancels the wait instead of hanging on it."""
        self.quitting = True
        screen = self._visible_app_screen()
        if screen is not None:
            screen.status.set(_REMOVAL_QUIT_WAIT, "warn")
        else:
            self._pending_warnings.append(_REMOVAL_QUIT_WAIT)
        removals = [w for w in self.workers if w.group == "uninstall-removal"]
        self.run_worker(self._exit_when_done(removals), group="quit-wait", exit_on_error=False)

    async def _exit_when_done(self, removals: Sequence[Worker[None]]) -> None:
        for worker in removals:
            with contextlib.suppress(WorkerFailed, WorkerCancelled):
                await worker.wait()
        self.exit(None)
