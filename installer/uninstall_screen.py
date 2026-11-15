"""The Uninstall view: the catalog-parity browser whose Enter removes the selection."""

import asyncio
import contextlib
import shlex
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message

from installer import receipts
from installer.agent_settings import ledger_summary
from installer.app import (
    UninstallDecision,
    has_schedule_id,
    pnpm_removal_packages,
    removal_change_lines,
    removal_result_lines,
    removal_runs_line,
    schedule_phrase,
    settings_change_lines,
    unregister_runs_line,
)
from installer.catalog_tui import health_cell
from installer.enums import MutationHolder, UninstallState
from installer.locations import bin_dir, display_path
from installer.modals import (
    ConfirmUninstall,
)
from installer.model import Tool
from installer.pnpm_globals import (
    co_install_warnings,
)
from installer.postinstall import host_labels
from installer.render import outcome_detail_text, outcome_word
from installer.sanitize import sanitize_log_line
from installer.session import (
    Disposition,
    PlanRow,
    RowOutcome,
    first_line,
    summary_counts,
)
from installer.terminal_shell import terminal_sync_warning
from installer.tool_browser import BrowserAdapter, Section, ToolBrowser
from installer.ui_common import (
    AppScreen,
    mark,
    multiline_summary,
    run_live,
)
from installer.uninstall import (
    RemovalPlan,
    SweepResult,
    config_targets,
    removal_plan,
    reverse_dependencies,
)
from installer.uninstall_review import (
    BLOCK_KEY,
    ENV_KEYS,
    NOTHING_TO_UNINSTALL,
    REMOVES_CELL_MAX,
    SETTINGS_KEY,
    STATE_TITLES,
    TWEAK_KEY,
    EnvState,
    UninstallEntry,
    UninstallInputs,
    config_split,
    retired_detail,
    retired_review_lines,
    review_line,
)
from installer.version_status import (
    ToolState,
    VersionRefreshService,
    uninstall_detail,
    uninstall_group,
    uninstall_label,
)

if TYPE_CHECKING:
    from installer.wizard_app import UnifiedApp


class RemovalFinished(Message):
    """The removal worker ended. `swept` is None when the remover failed or raised
    (then `error` says why); `invalidate_error` is the post-removal cache failure."""

    def __init__(
        self,
        decision: UninstallDecision,
        swept: SweepResult | None,
        error: str | None,
        invalidate_error: str | None,
    ) -> None:
        super().__init__()
        self.decision = decision
        self.swept = swept
        self.error = error
        self.invalidate_error = invalidate_error


class UninstallScreen(AppScreen):
    """Full catalog-parity uninstall browser. Every tool is listed with its
    removability state; only removable tools (and the env rows) toggle. Enter
    removes exactly the selected artifacts + env levers, applied live."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("c", "toggle_config", "config"),
    ]

    # Narrow .app from App[Unknown] (MessagePump default) to the concrete host
    # app so push_screen() is typed without an Unknown generic param.
    # UnifiedApp is defined later in this module; the string forward reference is
    # resolved by pyright (which analyses all module-level names together).
    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    def __init__(
        self,
        inputs: UninstallInputs,
        *,
        tools: Sequence[Tool],
        version_refresh: VersionRefreshService | None = None,
    ) -> None:
        super().__init__(view="uninstall", accent="red")
        # Tool ids whose "delete config too" flag is on (D-11). Never persisted:
        # cleared on leave (`clear_transient`) and kept in step with the marks.
        self._config_on: set[str] = set()
        self._version_refresh = version_refresh
        self._tools = list(tools)
        # The catalog does not change in a session, so this is computed once.
        self._required_by = reverse_dependencies(self._tools)
        # The last entry built from a KNOWN state: a row whose state is unknown
        # again (a removal in flight) keeps its section and selectability.
        self._painted: dict[str, UninstallEntry] = {}
        self._has_path_block_of = inputs.has_path_block
        self._tweak_ids_of = inputs.tweak_ids
        self._retired_of = inputs.retired
        # Evaluated THROUGH run_live (.claude/architecture.md rule 3), not
        # bare: construction happens outside the nav path `enter_view` guards,
        # so a bare call would let an OSError from the filesystem reads escape
        # before any screen or status line exists to report it. On failure the
        # screen still constructs with no environment rows and the message
        # stashed on `self._startup_error`; the first `enter_view` surfaces it
        # as a one-time warn and re-reads, so the screen self-heals.
        env, env_error = run_live(self._env_state)
        empty_env: EnvState = (False, (), (), ())
        (
            self._has_path_block,
            self._tweak_ids,
            self._settings_files,
            self._retired,
        ) = env if env is not None else empty_env
        self._startup_error: str | None = env_error
        self._remove = inputs.remove
        self._terminal_sync = inputs.terminal_sync
        self._platform_os = inputs.platform_os
        self.applied = False
        self.error: str | None = None
        # tool id -> its last `remove_failed` outcome; kept across navigation and
        # publishes, dropped when a removal naming the tool starts or its state
        # shows nothing left (see `_with_failure`).
        self._failed_lines: dict[str, RowOutcome] = {}
        # True until a published state has been painted: the rows before it are
        # placeholders, so the cursor is not kept on one of them.
        self._placeholders = True
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser: ToolBrowser[UninstallEntry] = ToolBrowser(self._adapter())

    # -- entry construction ------------------------------------------------
    def _build_entries(self) -> list[UninstallEntry]:
        entries = [self._with_failure(self._tool_entry(tool), tool) for tool in self._tools]
        # Built from the pairs the last re-read stored, so painting never reads the filesystem.
        entries.extend(self._retired_entry(tool, plan) for tool, plan in self._retired)
        if self._has_path_block:
            entries.append(self._block_entry())
        if self._tweak_ids:
            entries.append(self._tweak_entry())
        if self._settings_files:
            entries.append(self._settings_entry())
        return entries

    def _state_of(self, tool: Tool) -> ToolState | None:
        return self._version_refresh.state_of(tool.id) if self._version_refresh else None

    def _tool_entry(self, tool: Tool) -> UninstallEntry:
        """One tool row, drawn from its published state alone (D-07)."""
        state = self._state_of(tool)
        group = uninstall_group(state)
        if state is None or group is None:
            return self._unknown_entry(tool, state)
        selectable = group is UninstallState.REMOVABLE
        style = "" if selectable else "dim"
        paths = state.removable.removable if selectable else ()
        argv = state.removable.argv if selectable else ()
        unregister = state.removable.unregister if selectable else ()
        shown = ([shlex.join(argv)] if argv else []) + [str(path) for path in paths]
        flagged = selectable and tool.id in self._config_on
        removes = Text(("config + " if flagged else "") + (", ".join(shown) or "—"), style=style)
        removes.truncate(REMOVES_CELL_MAX, overflow="ellipsis")
        config = self._config_clause(tool, state, flagged) if selectable else ""
        entry = UninstallEntry(
            key=tool.id,
            cells=[
                mark(False) if selectable else Text(""),
                Text(tool.id, style="bold" if selectable else "dim"),
                health_cell(state),
                Text(tool.category, style=style),
                Text(uninstall_label(state), style=style),
                removes,
            ],
            selectable=selectable,
            detail=sanitize_log_line(
                uninstall_detail(tool, state, self._required_by.get(tool.id, ()), config=config)
            ),
            paths=tuple(paths),
            is_path_block=False,
            tool=tool,
            group=group,
            argv=argv,
            unregister=unregister,
        )
        self._painted[tool.id] = entry
        return entry

    def _config_clause(self, tool: Tool, state: ToolState, flagged: bool) -> str:
        """The detail clause for a removable row's declared config (UI-SPEC, How a row shows it)."""
        if not tool.config_paths:
            return ""
        existing = [entry for entry, path in config_targets(tool) if path in state.removable.config]
        where = ", ".join(existing) or "none on disk"
        if flagged:
            return f"config deleted too: {where} (c keeps it)"
        return f"config kept: {where} (c deletes it too)"

    def _mark_cell(self, item_id: str, selected: bool) -> Text:
        """The sel cell: `[c]` on a marked row whose config flag is on (UI-SPEC A2)."""
        if selected and item_id in self._config_on:
            return Text("[c]", style="bold red")
        return mark(selected)

    def _with_failure(self, entry: UninstallEntry, tool: Tool) -> UninstallEntry:
        """The row of a tool whose last removal failed: the failed word and the
        reason ahead of what the state says. A tool whose state shows nothing left
        to retry or explain (gone, no `removable`, no `yourself`) drops its line."""
        outcome = self._failed_lines.get(tool.id)
        if outcome is None:
            return entry
        state = self._state_of(tool)
        gone = state is not None and uninstall_group(state) is UninstallState.ABSENT
        if (
            gone
            and state is not None
            and not (state.removable.removable or state.removable.yourself)
        ):
            del self._failed_lines[tool.id]
            return entry
        word, style = outcome_word(outcome)
        detail = f"{word} — {outcome_detail_text(outcome)}"
        if not gone:
            detail += f" · {entry.detail}"
        elif state is not None and state.removable.yourself:
            detail += (
                f" · remove it yourself: {', '.join(str(p) for p in state.removable.yourself)}"
            )
        cells = [*entry.cells]
        cells[5] = Text(word, style=style)
        return replace(entry, cells=cells, detail=sanitize_log_line(detail))

    def _unknown_entry(self, tool: Tool, state: ToolState | None) -> UninstallEntry:
        """A tool whose state is not known yet: what it was last painted with,
        its Health cell set to `…`; a row never painted before is an unselectable
        `nothing to do` row (T-21-18)."""
        painted = self._painted.get(tool.id)
        if painted is not None:
            cells = [*painted.cells]
            cells[2] = health_cell(state)
            return replace(painted, cells=cells)
        return UninstallEntry(
            key=tool.id,
            cells=[
                Text(""),
                Text(tool.id, style="dim"),
                health_cell(state),
                Text(tool.category, style="dim"),
                Text("—", style="dim"),
                Text("—", style="dim"),
            ],
            selectable=False,
            detail=uninstall_detail(tool, state),
            paths=(),
            is_path_block=False,
            tool=tool,
            group=UninstallState.ABSENT,
        )

    def _block_entry(self) -> UninstallEntry:
        return UninstallEntry(
            key=BLOCK_KEY,
            cells=[
                mark(False),
                Text("PATH wiring", style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text("managed block in ~/.myshellrc", style="dim"),
            ],
            selectable=True,
            detail="PATH wiring — the managed block in ~/.myshellrc",
            paths=(),
            is_path_block=True,
        )

    def _tweak_entry(self) -> UninstallEntry:
        # Byte-identical to today when no schedule: id is among the offered ids -- the
        # label/detail only name the background jobs when one is actually present.
        has_schedule = has_schedule_id(self._tweak_ids)
        has_redirect = any(policy_id.startswith("cache-redirect:") for policy_id in self._tweak_ids)
        label = "shell tweaks + background jobs" if has_schedule else "shell tweaks"
        detail = (
            "Disables every enabled shell tweak — the ~/.myshellrc blocks, "
            "the managed helper executables, and the Oh-My-Zsh plugin names "
            "this installer added to .zshrc (never ones you added yourself)"
        )
        if has_schedule and self._platform_os == "macos":
            detail += (
                " — and unregisters the background maintenance LaunchAgents"
                " (their plists, the runner and the schedule state)"
            )
        elif has_schedule:
            detail += (
                " — and unregisters the systemd user timers (their unit files, the runner and"
                " the schedule state)"
            )
        if has_redirect:
            detail += "; the environment cache redirect is removed too"
        return UninstallEntry(
            key=TWEAK_KEY,
            cells=[
                mark(False),
                Text(label, style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(f"blocks + helpers ({', '.join(self._tweak_ids)})", style="dim"),
            ],
            selectable=True,
            detail=detail,
            paths=(),
            is_path_block=False,
            is_tweaks=True,
        )

    def _settings_entry(self) -> UninstallEntry:
        """The agent and editor settings row (UI-SPEC section 6, O5): one revert for every key
        the ledgers record, which never touches a key the user changed since."""
        files = ", ".join(display_path(path) for path in self._settings_files)
        return UninstallEntry(
            key=SETTINGS_KEY,
            cells=[
                mark(False),
                Text("agent/editor settings", style="bold yellow"),
                Text(""),
                Text("env", style="yellow"),
                Text("shell config", style="dim"),
                Text(
                    f"keys this installer wrote in {len(self._settings_files)} file(s)", style="dim"
                ),
            ],
            selectable=True,
            detail=f"reverts only keys that still hold this installer's value: {files}",
            paths=(),
            is_path_block=False,
            is_settings=True,
        )

    def _retired_entry(self, tool: Tool, plan: RemovalPlan) -> UninstallEntry:
        """A retired receipt's row (D-09, UI-SPEC section 2): removal only, no install or update."""
        selectable = plan.level != "none"
        shown = ", ".join(str(path) for path in plan.removable) or "—"
        removes = Text(sanitize_log_line(shown))
        removes.truncate(REMOVES_CELL_MAX, overflow="ellipsis")
        name = Text(sanitize_log_line(tool.id), style="bold")
        name.append(" (retired)", style="dim")
        return UninstallEntry(
            key=tool.id,
            cells=[
                mark(False) if selectable else Text(""),
                name,
                Text(""),
                Text("retired", style="dim"),
                Text(""),
                removes,
            ],
            selectable=selectable,
            detail=sanitize_log_line(retired_detail(tool.id, plan)),
            paths=plan.removable,
            is_path_block=False,
            tool=tool,
            argv=plan.argv,
            unregister=plan.unregister,
            is_retired=True,
            retired_plan=plan,
        )

    # -- browser adapter ---------------------------------------------------
    def _adapter(self) -> BrowserAdapter[UninstallEntry]:
        return BrowserAdapter(
            items=self._entries,
            columns=(
                ("Sel", "sel"),
                ("Tool", "tool"),
                ("Health", "health"),
                ("Cat", "cat"),
                ("Installed via", "via"),
                ("What gets removed", "removes"),
            ),
            item_id=lambda entry: entry.key,
            row_cells=lambda entry: entry.cells,
            detail_text=lambda entry: entry.detail,
            groups=self._groups,
            views=(("all", "All"),),
            fit_column="removes",
            detail_is_markup=False,
            selectable=lambda entry: entry.selectable,
            mark_cell=self._mark_cell,
        )

    def _groups(self, _view: str) -> list[Section[UninstallEntry]]:
        by_title: dict[str, list[UninstallEntry]] = {}
        for state, title in STATE_TITLES:
            by_title.setdefault(title, []).extend(
                entry for entry in self._entries if entry.group is state
            )
        sections: list[Section[UninstallEntry]] = [
            (title, title, members) for title, members in by_title.items() if members
        ]
        retired = sorted(
            (entry for entry in self._entries if entry.is_retired), key=lambda entry: entry.key
        )
        if retired:
            title = "retired — no longer in the catalog"
            sections.append((title, title, retired))
        env = [
            entry
            for entry in self._entries
            if entry.is_path_block or entry.is_tweaks or entry.is_settings
        ]
        if env:
            sections.append(("environment", "shell config the installer manages", env))
        return sections

    def compose_body(self) -> ComposeResult:
        yield self._browser

    def _repaint(self) -> None:
        """Rebuild the entries from the stored values and repaint the browser."""
        # A flag follows its mark (UI-SPEC A1): every repaint drops the flags of unmarked rows.
        self._config_on.intersection_update(self._browser.selected)
        self._entries = self._build_entries()
        self._by_key = {entry.key: entry for entry in self._entries}
        self._browser.reload(self._adapter(), keep_cursor=not self._placeholders)
        if any(uninstall_group(self._state_of(tool)) is not None for tool in self._tools):
            self._placeholders = False

    def _env_state(self) -> EnvState:
        """The environment predicates another view can change while this one is
        suspended, as one tuple.

        Every one of them touches the FILESYSTEM and can therefore raise
        (CR-01, 15.4-REVIEW.md): `has_path_block` -> `shellrc.has_managed_block`
        -> `Path.read_text()`; `tweak_ids` -> `active_tweak_ids` -> the rc files
        and the managed bin dir; the settings files -> the ledgers. That is why this
        tuple is its own seam: every caller evaluates it through `run_live`, so a
        failure degrades to the last known values plus a warn rather than escaping
        the nav path.
        """
        settings_files = tuple(
            path
            for agent in receipts.CONFIG_AGENTS
            for path, _keys in ledger_summary(agent, home=Path.home())
        )
        managed = (
            self._version_refresh.managed_bin_dir
            if self._version_refresh is not None
            else bin_dir(None)
        )
        # D-09: the retired receipts re-listed live, each with the plan its row will show.
        retired = tuple((tool, removal_plan(tool, managed)) for tool in self._retired_of())
        return (
            self._has_path_block_of(),
            self._tweak_ids_of(),
            settings_files,
            retired,
        )

    def _reread_env(self) -> str | None:
        """Re-read the environment predicates and the retired receipts; the error text when that
        failed (the last values are kept). A publish can follow a mutation that changed
        them while this view is the visible one (D-06), so both `enter_view` and
        `state_refreshed` call it."""
        env, error = run_live(self._env_state)
        if env is not None:
            (
                self._has_path_block,
                self._tweak_ids,
                self._settings_files,
                self._retired,
            ) = env
        return error

    def enter_view(self) -> None:
        """Re-read the environment and repaint each time this view is opened.

        A nav entry is D-06's trigger for a same-session removal summary to stop
        being claimed once it no longer describes the screen, so `applied` is
        cleared. Over an empty line only: a warning flushed by show_view or
        written here must not be replaced by the standing text.
        """
        error = self._reread_env()
        stashed, self._startup_error = self._startup_error, None
        self.applied = False
        self._repaint()
        if error is not None:
            self.status.set(f"Could not read the uninstall state: {error}.", "warn")
        elif stashed is not None:
            self.status.set(f"Could not read the uninstall state at startup: {stashed}.", "warn")
        if not self.status.text:
            self._show_standing_status()

    def state_refreshed(self) -> None:
        """A publish landed while this view may be open (D-06): re-read the
        environment, repaint every row, and never clear or replace a status
        someone else wrote. `applied` stays, so a removal summary stands."""
        error = self._reread_env()
        self._repaint()
        if error is not None and not self.status.text:
            self.status.set(f"Could not read the uninstall state: {error}.", "warn")
        if self.is_mounted:
            self._show_standing_status()

    def clear_transient(self) -> None:
        """Leaving the view forgets every config flag: a destructive choice is never remembered."""
        super().clear_transient()
        self._config_on.clear()

    def _nothing_to_uninstall(self) -> bool:
        """True only when every tool's state is known and none is removable or
        managed, and there is no environment row (RESEARCH P7)."""
        known = all(uninstall_group(self._state_of(tool)) is not None for tool in self._tools)
        idle = all(
            entry.group in (UninstallState.ABSENT, UninstallState.UNAVAILABLE)
            for entry in self._entries
        )
        return known and idle

    def _show_standing_status(self) -> None:
        """Write the standing copy into an empty line while it is true, and
        retract it only while the line still holds exactly that copy."""
        if self._nothing_to_uninstall():
            if not self.status.text:
                self.status.set(NOTHING_TO_UNINSTALL, "ok")
        else:
            self.status.retract(NOTHING_TO_UNINSTALL)

    # -- public seams the tests assert on ----------------------------------
    @property
    def selected(self) -> set[str]:
        """Selected *tool* ids (the env pseudo-rows are reported separately)."""
        return {key for key in self._browser.selected if key not in ENV_KEYS}

    @property
    def remove_path_block(self) -> bool:
        return BLOCK_KEY in self._browser.selected

    @property
    def remove_tweaks(self) -> bool:
        return TWEAK_KEY in self._browser.selected

    @property
    def remove_settings(self) -> bool:
        return SETTINGS_KEY in self._browser.selected

    @property
    def detail_text(self) -> str:
        return self._browser.detail_text

    # -- messages from the browser -----------------------------------------
    def on_tool_browser_selection_changed(self, event: ToolBrowser.SelectionChanged) -> None:
        event.stop()
        # A mark is for the next removal; the running one keeps its status (D-05).
        if self.app.mutation_holder is not MutationHolder.REMOVAL:
            self.status.clear()
        # An unmarked row loses its flag, so its detail and cells must be repainted.
        if self._config_on - self._browser.selected:
            self._repaint()

    def on_tool_browser_accepted(self, event: ToolBrowser.Accepted) -> None:
        event.stop()
        if not any(entry.selectable for entry in self._entries):
            return
        if not event.ids:
            self.status.set("Select at least one item to remove.", "warn")
            return
        # Refuse before the modal; _apply_removal checks again, because a
        # mutation can start while the modal is open.
        if self.app.refuse_if_mutating(self):
            return
        # Built now, before the modal opens, so a publish during the confirm cannot
        # change what the user confirmed (review R1-20).
        decision, kept, flagged = self._decision(event.ids)
        self.app.push_screen(
            ConfirmUninstall(
                self._accept_summary(event.ids), self._review(decision, kept, flagged)
            ),
            self._on_confirm(decision),
        )

    def _review(
        self,
        decision: UninstallDecision,
        kept: Mapping[str, tuple[str, ...]],
        flagged: frozenset[str],
    ) -> tuple[Text, ...]:
        """Blocks 3-7 of the review (UI-SPEC, ConfirmUninstall), built from the one snapshot
        `_decision` took: the decision, the `config_split` kept map and the flagged ids. Nothing
        is recomputed after the confirm (review R1-20). Every id, command and path is data:
        it goes through `sanitize_log_line` and is appended as plain `Text`, never markup."""
        lines: list[Text] = []
        for tool in decision.tools:
            # A hook tool's undo runs first, so its line comes before its own command (A24).
            for undo in decision.unregister.get(tool.id, ()):
                lines.append(review_line(sanitize_log_line(unregister_runs_line(tool.id, undo))))
            if argv := decision.argv.get(tool.id):
                lines.append(review_line(sanitize_log_line(removal_runs_line(tool.id, argv))))
            # A retired row's facts take the same place as its runs line, in the `<id>: ...` shape.
            entry = self._by_key.get(tool.id)
            if entry is not None and entry.retired_plan is not None:
                for line in retired_review_lines(tool.id, entry.retired_plan):
                    lines.append(review_line(sanitize_log_line(line)))
        # Block 3b, what changes (UI-SPEC section 6): the same lines the CLI previews.
        changes = removal_change_lines(decision.tools, active_tweaks=self._tweak_ids)
        if decision.revert_settings:
            changes += settings_change_lines(receipts.CONFIG_AGENTS)
        lines.extend(review_line(sanitize_log_line(line)) for line in dict.fromkeys(changes))
        deleted = [
            review_line(sanitize_log_line(f"  {entry} ({tool.id})"))
            for tool in decision.tools
            for entry, path in config_targets(tool)
            if path in decision.config.get(tool.id, ())
        ]
        shared = [
            review_line(sanitize_log_line(f"  {entry} kept, also used by {', '.join(ids)}"), "dim")
            for entry, ids in kept.items()
        ]
        if deleted or shared:
            lines.append(review_line("Config deleted too:", "bold red"))
            lines.extend(deleted)
            lines.extend(shared)
        unflagged = [
            tool.id for tool in decision.tools if tool.config_paths and tool.id not in flagged
        ]
        if unflagged:
            lines.append(review_line(sanitize_log_line(f"Config kept: {', '.join(unflagged)}.")))
        # The frozen decision's argv, like the `runs` lines above (review C-13).
        packages = pnpm_removal_packages(decision.argv.values())

        def present(tool: Tool) -> bool:  # an unknown state counts as present (22-UAT F-3)
            return uninstall_group(self._state_of(tool)) is not UninstallState.ABSENT

        for warning in co_install_warnings(packages, self._tools, present=present):
            line = review_line(sanitize_log_line(warning))
            line.stylize("yellow", 0, len("Warning:"))
            lines.append(line)
        return tuple(lines)

    def _highlighted_entry(self) -> UninstallEntry | None:
        key = self._browser.highlighted_id()
        return None if key is None else self._by_key.get(key)

    def action_toggle_config(self) -> None:
        """`c`: flag a removable row's config on (marking it too) or off (D-11, UI-SPEC A1).

        A flag is not a mutation, so the lock never refuses it.
        """
        entry = self._highlighted_entry()
        if entry is None or entry.tool is None or entry.is_retired:
            self._config_refused("This row has no config to delete.")
        elif entry.group is not UninstallState.REMOVABLE:
            self._config_refused(f"{entry.key} cannot be removed here, so its config stays.")
        elif not entry.tool.config_paths:
            self._config_refused(f"{entry.key} declares no config to delete.")
        else:
            if entry.key in self._config_on:
                self._config_on.discard(entry.key)
            else:
                if entry.key not in self._browser.selected:
                    self._browser.action_toggle_selected()
                self._config_on.add(entry.key)
            self._repaint()  # the row's cells and detail bar name the flag

    def _config_refused(self, text: str) -> None:
        """A refusal is a warn line, but it never replaces `Removing…` (D-05): during a removal
        it shows in the detail bar instead, so the key never looks broken (review C-15)."""
        if self.app.mutation_holder is not MutationHolder.REMOVAL:
            self.status.set(text, "warn")
        else:
            self._browser.show_detail(text)

    def _accept_summary(self, ids: list[str]) -> str:
        tool_count = sum(1 for key in ids if key not in ENV_KEYS)
        parts: list[str] = []
        if tool_count:
            parts.append(f"{tool_count} tool(s)")
        if BLOCK_KEY in ids:
            parts.append("the PATH wiring")
        if TWEAK_KEY in ids:
            parts.append("the shell tweaks")
        if SETTINGS_KEY in ids:
            parts.append("the agent/editor settings")
        return ", ".join(parts)

    def _decision(
        self, ids: list[str]
    ) -> tuple[UninstallDecision, Mapping[str, tuple[str, ...]], frozenset[str]]:
        """The removal the selected ids name, with the config the flags agreed to delete.

        Also returns the config `config_split` kept and the flagged ids, from the same
        `config_split` call, so the review and the decision cannot disagree."""
        tools: dict[str, Tool] = {}  # by id, in selection order; env rows carry no tool
        for key in ids:
            entry = self._by_key[key]
            if entry.tool is not None:
                tools.setdefault(entry.tool.id, entry.tool)
        flagged = [tool for tool in tools.values() if tool.id in self._config_on]
        deleted, kept = config_split(flagged, self._tools, self._state_of)
        decision = UninstallDecision(
            tools=tuple(tools.values()),
            paths={tool_id: self._by_key[tool_id].paths for tool_id in tools},
            argv={tool_id: self._by_key[tool_id].argv for tool_id in tools},
            unregister={tool_id: self._by_key[tool_id].unregister for tool_id in tools},
            remove_path_block=self.remove_path_block,
            remove_tweaks=self.remove_tweaks,
            revert_settings=self.remove_settings,
            config=deleted,
        )
        return decision, kept, frozenset(tool.id for tool in flagged)

    def _on_confirm(self, decision: UninstallDecision) -> Callable[[bool | None], None]:
        # Callable[[bool | None], None] is the correct pyright-strict type:
        # ScreenResultCallbackType (textual/screen.py:83) passes Optional[ScreenResultType]
        # to the callback, i.e. bool | None for ModalScreen[bool].
        def run(confirmed: bool | None) -> None:
            if confirmed:
                self._apply_removal(decision)

        return run

    def _apply_removal(self, decision: UninstallDecision) -> None:
        if self.app.refuse_if_mutating(self, cross_process=True):
            return
        if not self.app.begin_mutation(MutationHolder.REMOVAL, screen=self):
            return
        for tool in decision.tools:
            self._failed_lines.pop(tool.id, None)
        if self._version_refresh is not None and decision.tools:
            self._version_refresh.mark_pending([tool.id for tool in decision.tools])
        self._repaint()
        self.status.set("Removing…", "warn")
        self._remove_worker(decision)

    def _config_lines(self, decision: UninstallDecision, swept: SweepResult) -> list[str]:
        """UI-SPEC Removal results: what became of each tool's config, in the order deleted,
        kept, not deleted. Kept means a removed tool whose declared config is still on disk and
        was not flagged. The check reads the disk now: the cache invalidation that follows a
        removal leaves no published state to read it from (its epoch moved on)."""
        kept = [
            tool.id
            for tool in decision.tools
            if tool.id in swept.removed
            and tool.id not in decision.config
            and any(path.is_symlink() or path.exists() for _, path in config_targets(tool))
        ]
        lines: list[str] = []
        if swept.config_deleted:
            lines.append(f"Config deleted for {', '.join(swept.config_deleted)}.")
        if kept:
            lines.append(f"Config kept for {', '.join(kept)}.")
        if swept.config_not_deleted:
            lines.append(
                f"Config not deleted for {', '.join(swept.config_not_deleted)}: the removal failed."
            )
        return [sanitize_log_line(line) for line in lines]

    def _applied_summary(self, decision: UninstallDecision, swept: SweepResult) -> str:
        parts: list[str] = []
        if decision.remove_path_block:
            parts.append("PATH wiring removed — restart your shell to drop the managed dirs.")
        if decision.remove_tweaks:
            # From the sweep's own result, never from the row's snapshot: the
            # snapshot describes what was offered, not what came off.
            if swept.swept:
                # Byte-identical to today when no schedule: id is among what was
                # actually swept. When one is present, name it explicitly and
                # append the shell-reload hint only if a real, non-schedule
                # tweak was ALSO swept -- a timer needs no shell reload
                # at all (11-REVIEWS.md cycle 2 finding #19).
                phrase = schedule_phrase(swept.swept)
                has_schedule = bool(phrase)
                has_redirect = any(sid.startswith("cache-redirect:") for sid in swept.swept)
                has_other = any(not sid.startswith("schedule:") for sid in swept.swept)
                prefix = f"shell tweaks and {phrase}" if has_schedule else "shell tweaks"
                if has_schedule and self._platform_os != "macos" and has_redirect:
                    reload_hint = " — log out and back in so the environment redirect is dropped."
                elif not has_schedule or has_other:
                    reload_hint = " — open a new shell so functions and aliases refresh."
                else:
                    reload_hint = "."
                parts.append(f"{prefix} disabled ({', '.join(swept.swept)}){reload_hint}")
            if swept.failed:
                parts.append(
                    f"could not disable {', '.join(swept.failed)} — check permissions and re-run."
                )
            if not swept.swept and not swept.failed:
                parts.append("no shell tweaks were still enabled — nothing to disable.")
        # Refused paths travel here too, so they show whatever levers were chosen.
        parts.extend(f"warning: {sanitize_log_line(warning)}." for warning in swept.warnings)
        # One line per outcome: a single joined line overflows the terminal width and
        # truncates the reload guidance, so the "needs a new shell" steps go unseen.
        return multiline_summary(parts)

    # exit_on_error=False: a crash must leave a usable app; RemovalFinished is
    # posted from `finally`, so the lock cannot stay held on any outcome. The
    # delete runs on a daemon thread this worker awaits: a forced quit (a second
    # ctrl+c, D-10) drops the wait, and the process exits without joining it.
    @work(exclusive=True, group="uninstall-removal", exit_on_error=False)
    async def _remove_worker(self, decision: UninstallDecision) -> None:
        loop = asyncio.get_running_loop()
        done: asyncio.Future[None] = loop.create_future()

        def finish() -> None:
            if not done.done():
                done.set_result(None)

        def run() -> None:
            try:
                self._run_removal(decision)
            finally:
                with contextlib.suppress(RuntimeError):  # the loop closed: a forced quit
                    loop.call_soon_threadsafe(finish)

        threading.Thread(target=run, name="uninstall-removal", daemon=True).start()
        await done

    def _run_removal(self, decision: UninstallDecision) -> None:
        swept: SweepResult | None = None
        error: str | None = "removal did not complete"
        invalidate_error: str | None = None
        try:
            try:
                swept, error = run_live(lambda: self._remove(decision))
            except Exception as exc:
                error = first_line(exc)
            # Also after a crash: only `invalidate` clears the pending ids (D-09).
            service = self._version_refresh
            if service is not None and decision.tools:
                _, cache_error = run_live(
                    lambda: service.invalidate(reason="uninstall run finished")
                )
                if cache_error is not None:
                    invalidate_error = f"version cache invalidation failed: {cache_error}"
        finally:
            self.post_message(RemovalFinished(decision, swept, error, invalidate_error))

    def on_removal_finished(self, message: RemovalFinished) -> None:
        self.app.end_mutation()
        if not self.app.is_running:  # the app is shutting down: nothing to render
            return
        swept = message.swept
        self.error = message.error
        if swept is None:
            self.app.show_result(
                self,
                f"Uninstall failed: {self.error}. Check permissions, then press enter.",
                "error",
                elsewhere=(
                    f"Uninstall failed: {self.error}."
                    " Check permissions, then open Uninstall and press enter."
                ),
            )
            self._request_pass()
            return
        self.applied = True
        # A receipt-only retirement (no path, no command) reports its own sentence, not a count.
        receipt_only = {
            tool.id
            for tool in message.decision.tools
            if tool.retired
            and not message.decision.paths.get(tool.id)
            and not message.decision.argv.get(tool.id)
        }
        outcomes = [
            RowOutcome(PlanRow(tool_id, Disposition.REMOVE, ""), "done")
            for tool_id in swept.removed
            if tool_id not in receipt_only
        ] + [
            RowOutcome(PlanRow(tool_id, Disposition.REMOVE, ""), "remove_failed", detail=line)
            for tool_id, line in swept.remove_failed
        ]
        for tool_id, line in swept.remove_failed:
            self._failed_lines[tool_id] = RowOutcome(
                PlanRow(tool_id, Disposition.REMOVE, ""), "remove_failed", detail=line
            )
        self._browser.selected -= set(swept.removed)
        self.app.unstage(swept.removed)
        self._repaint()
        summary_parts = [summary_counts(outcomes)] if outcomes else []
        summary_parts.extend(sanitize_log_line(line) for line in swept.with_group)
        summary_parts.extend(sanitize_log_line(line) for line in swept.receipt_retired)
        failed = len(swept.remove_failed)
        fix_here = f"{failed} remove failed. Fix the cause and press enter to try again."
        if failed:
            summary_parts.append(fix_here)
        summary_parts.extend(self._config_lines(message.decision, swept))
        if labels := host_labels(swept.unregistered):
            summary_parts.append(f"Unregistered from agent hosts: {labels}.")
        summary_parts.extend(removal_result_lines(swept))
        # Empty when no lever was chosen; a blank line would cost a status row.
        if applied := self._applied_summary(message.decision, swept):
            summary_parts.append(applied)
        if message.invalidate_error is not None:
            summary_parts.append(message.invalidate_error)
        # D-01/15.6-06 Task 3: called unconditionally on every successful
        # sweep (never gated on tools -- a terminal reapply/reversion is
        # warranted even when only an env lever came off, since
        # sync_terminal_shells' own no-zsh branch is exactly what a
        # zsh-removing sweep needs). WR-03/WR-04: the one shared failure
        # contract (terminal_sync_warning); a failure renders "warn", never
        # the "ok" success color, and never flips `applied`.
        terminal_warning = terminal_sync_warning(self._terminal_sync)
        if terminal_warning:
            summary_parts.append(terminal_warning)
        if swept.remove_failed or swept.config_not_deleted:
            severity = "error"
        elif terminal_warning or swept.warnings:  # a config delete warning is a warn too
            severity = "warn"
        else:
            severity = "ok"
        summary = multiline_summary(summary_parts)
        fix_elsewhere = (
            f"{failed} remove failed. Fix the cause, then open Uninstall and press enter"
            " to try again."
        )
        self.app.show_result(
            self,
            summary,
            severity,
            elsewhere=summary.replace(fix_here, fix_elsewhere) if failed else None,
        )
        self._request_pass()

    def _request_pass(self) -> None:
        """D-05: every removal, environment-only ones included, ends with one app
        pass; the publish re-renders this view. A quit in progress exits instead."""
        if not self.app.quitting:
            self.app.request_refresh()
