"""The Policies view: the live toggles for shell tweaks, cache redirects and the desktop shell."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Static
from textual.widgets.data_table import ColumnKey

from installer import env_redirect
from installer.catalog_tui import RefreshRequested
from installer.diskusage import DiskPressureProbe
from installer.modals import LinkModeScreen
from installer.policy import Policy, PolicyMove, PolicyResult, lost_policy_ids, move_link_mode
from installer.systemd_daemon import CompetingProbe
from installer.ui_common import AppScreen, fit, highlighted_key, multiline_summary, run_live
from installer.uninstall import policy_owned

if TYPE_CHECKING:
    from installer.wizard_app import UnifiedApp


@dataclass(frozen=True)
class PolicyInputs:
    """The policies the PoliciesScreen renders, each carrying its own bound
    apply/remove closures. The composition root builds these from the pure core.

    `disk_pressure` is the ONE seam the route's single probe travels through:
    UnifiedApp hands it to the Doctor and the Schedules view, so no second
    field or UnifiedApp parameter carries the same closure."""

    policies: list[Policy]
    link_mode: Callable[[], str] | None = None
    set_link_mode: Callable[[str], None] | None = None
    disk_pressure: DiskPressureProbe | None = None
    # The same seam reasoning as disk_pressure -- one closure, both
    # the Doctor's durable disclosure and the Schedules detail line.
    competing: CompetingProbe | None = None


_POLICY_READ_ERROR = "Could not read the policy state: "


def _read_failure(error: str) -> str:
    """The status copy for a failed live read: the first line of the message."""
    return f"{_POLICY_READ_ERROR}{error.partition(chr(10))[0]}."


_DRIFT_DETAIL = (
    "Drift: this installer enabled it, but it is not active now. space applies it again."
)


def _read_active_owned(policy: Policy) -> tuple[tuple[bool, bool] | None, str | None]:
    """One policy's (active, owned) through run_live, or the failure text.

    `owned` is read only when the policy binds it; either read failing fails
    the pair, so a row is never half-painted from one answer.
    """
    if policy.is_active is None:
        return None, None
    active, error = run_live(policy.is_active)
    if active is None:
        return None, error
    owned = False
    if policy.owned is not None:
        read, error = run_live(policy.owned)
        if read is None:
            return None, error
        owned = read
    return (active, owned), None


class PoliciesScreen(AppScreen):
    """Toggle environment policies (shell tweaks, cache redirects, the desktop shell) on/off,
    applied live.

    Each toggle is an immediate, idempotent, reversible mutation — there is no
    select-then-commit step. `space` toggles the highlighted policy (matching the
    "act on this row" meaning of `space` in the catalog/uninstall browsers);
    `enter` is inert here because there is no staged batch to commit.
    """

    if TYPE_CHECKING:

        @property
        def app(self) -> "UnifiedApp": ...

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_policy", "toggle policy", show=True, priority=True),
        Binding("m", "pick_link_mode", "link mode", show=True),
    ]
    DEFAULT_CSS = """
    /* The rows size the table (up to 8 cells tall); the detail takes what is left, under
       the status, and scrolls. A fixed 11-row detail left one table row at 80x20. */
    PoliciesScreen DataTable { height: auto; max-height: 8; }
    PoliciesScreen #link-mode-line {
        height: auto; padding: 0 1;
    }
    PoliciesScreen #policy-detail {
        height: 1fr; min-height: 4; padding: 0 1; background: $surface; overflow-y: auto;
    }
    """

    def __init__(self, inputs: PolicyInputs) -> None:
        super().__init__(view="policies")
        self._policies = inputs.policies
        self._link_mode = inputs.link_mode
        self._set_link_mode = inputs.set_link_mode
        self.active_state: dict[str, bool] = {
            policy.id: policy.active for policy in inputs.policies
        }
        # Policies whose last read said owned-but-not-active.
        self._drift: set[str] = set()
        # Settings rows whose keys all hold our values with no record: nothing to write.
        self._yours: set[str] = set()
        # Each policy's prerequisites as last read; no entry means not (yet) readable.
        self._missing: dict[str, tuple[str, ...]] = {}
        self._read_error: str | None = None
        self.error: str | None = None
        self.detail_text = ""

    def compose_body(self) -> ComposeResult:
        yield Static("", id="link-mode-line")
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
                Text(""),
                Text(policy.label, style="bold yellow"),
                Text(""),
                Text(self._effect_text(policy), style="dim"),
                key=policy.id,
            )
        table.focus()
        self.call_after_refresh(self._fit_effect)  # the table has its width after first layout

    @staticmethod
    def _effect_text(policy: Policy) -> str:
        return f"{policy.effect_kind or 'shell config'}: {policy.description}"

    def _fit_effect(self) -> None:
        """Give the Effect column the width the others leave (less the scrollbar), its cells
        ending in `…` where cut, as the catalog tables do."""
        table = self.query_one(DataTable[Any])
        if not self.is_mounted or table.size.width == 0:
            return
        others = sum(
            table.columns[ColumnKey(key)].get_render_width(table) for key in _POLICY_FIXED_COLUMNS
        )
        column = table.columns[ColumnKey("effect")]
        column.auto_width = False
        column.width = max(table.size.width - 2 - others - 2, _POLICY_EFFECT_FLOOR)
        for policy in self._policies:
            cell = Text(fit(self._effect_text(policy), column.width), style="dim")
            table.update_cell(policy.id, "effect", cell)

    def on_resize(self) -> None:
        self._fit_effect()

    def _refresh_link_mode_line(self) -> None:
        line = self.query_one("#link-mode-line", Static)
        if self._link_mode is None:
            line.update("")
            return
        line.update(f"PATH link mode: {self._link_mode()}  (press m to change)")

    def enter_view(self) -> None:
        self.state_refreshed()

    def state_refreshed(self) -> None:
        """Render every row from a fresh read of the machine (D-04, D-12).

        `enter_view` calls this on every entry and the app calls it on every
        publish while Policies is on top.
        """
        if not self.is_mounted:
            return
        table = self.query_one(DataTable[Any])
        errors: list[str] = []
        for policy in self._policies:
            errors += filter(None, (self._read_live_state(policy), self._read_requirements(policy)))
            table.update_cell(policy.id, "state", self._state_cell(policy.id), update_width=True)
            table.update_cell(policy.id, "requires", self._requires_cell(policy), update_width=True)
        self._set_detail(self._highlighted_policy())
        self._refresh_link_mode_line()
        if errors:
            self._show_read_error(errors[0])
        elif self._read_error is not None:
            self.status.retract(self._read_error)
            self._read_error = None

    def _read_live_state(self, policy: Policy) -> str | None:
        """Re-read one policy's state; the error text when the read failed.

        A policy without is_active keeps the state its last toggle left. A failed
        read drops the remembered answer: the row is never painted from a
        previous read.
        """
        if policy.state is not None:
            state, error = run_live(policy.state)
            self._record_settings_state(policy.id, state)
            return error
        if policy.is_active is None:
            return None
        read, error = _read_active_owned(policy)
        self._record_state(policy.id, read)
        return error

    def _record_settings_state(self, policy_id: str, state: str | None) -> None:
        """A settings row's read: on, yours, off or drift. None (unreadable) drops it."""
        self._yours.discard(policy_id)
        if state is None:
            self._record_state(policy_id, None)
            return
        self._record_state(policy_id, (state == "on", state == "drift"))
        if state == "yours":
            self._yours.add(policy_id)

    def _record_state(self, policy_id: str, read: tuple[bool, bool] | None) -> None:
        """Keep one policy's (active, owned) answer; None drops it (blank cell)."""
        if read is None:
            self.active_state.pop(policy_id, None)
            self._drift.discard(policy_id)
            return
        active, owned = read
        self.active_state[policy_id] = active
        if owned and not active:
            self._drift.add(policy_id)
        else:
            self._drift.discard(policy_id)

    def _show_read_error(self, error: str) -> None:
        """Over an empty status or this screen's own earlier error only: another
        writer's result stands, the same rule as the app's state line."""
        previous, self._read_error = self._read_error, _read_failure(error)
        if not self.status.text or self.status.text == previous:
            self.status.set(self._read_error, "error")

    def _read_requirements(self, policy: Policy) -> str | None:
        missing, error = run_live(policy.missing_requirements)
        if missing is None:
            self._missing.pop(policy.id, None)
        else:
            self._missing[policy.id] = missing
        return error

    def _refuse_unreadable(self) -> None:
        """A row whose state or prerequisites could not be read is never acted
        on, never treated as OFF; the refusal still ends with one pass."""
        self.status.set(self._read_error or f"{_POLICY_READ_ERROR}not read yet.", "error")
        self.post_message(RefreshRequested())

    def _state_cell(self, policy_id: str) -> Text:
        # A ●/○ glyph carries the state independent of color: the lone row is
        # always focused, so the selection highlight flattens the green/dim cue.
        active = self.active_state.get(policy_id)
        if active is None:
            return Text("")
        if policy_id in self._yours:
            return Text("● [yours]", style="green")
        if policy_id in self._drift:
            return Text("! [drift]", style="yellow")
        label = "● [on]" if active else "○ [off]"
        return Text(label, style="green" if active else "dim")

    def _requires_cell(self, policy: Policy) -> Text:
        missing_requires = self._missing.get(policy.id)
        if missing_requires is None:
            return Text("")
        if missing_requires and policy.hard_requires:
            return Text("missing: " + ", ".join(missing_requires), style="bold yellow")
        if missing_requires:
            return Text("recommended: " + ", ".join(missing_requires), style="yellow")
        if policy.requires:
            return Text(", ".join(policy.requires), style="dim")
        return Text("none", style="dim")

    def _highlighted_policy(self) -> Policy | None:
        # highlighted_key is None on an empty table, matching no policy id.
        policy_id = highlighted_key(self.query_one(DataTable[Any]))
        return next((policy for policy in self._policies if policy.id == policy_id), None)

    def _policy_detail(self, policy: Policy) -> str:
        missing_requires = self._missing.get(policy.id)
        details = {
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
            "cache-redirect:bun": (
                f"Sets {env_redirect.BUN_CACHE_REDIRECT.variable} so Bun's transpiler cache"
                " lands in ~/.cache/bun instead of the OS temp dir.",
                "On Linux this is an environment.d file the systemd user manager reads only"
                " when it starts, so the change takes effect at the next login, not in a"
                " new terminal tab.",
                "Disabling removes the redirect but never deletes the cache directory itself.",
                env_redirect.BUN_CACHE_REDIRECT.coverage_caveat,
            ),
        }
        if policy.detail_lines is not None:
            # A settings row's own lines replace the generic drift and label lines.
            lines = list(policy.detail_lines())
        else:
            lines = [_DRIFT_DETAIL] if policy.id in self._drift else []
            lines.append(f"{policy.label} — {policy.description}")
        if missing_requires and policy.hard_requires:
            lines.append(
                "Missing required tool(s): "
                f"{', '.join(missing_requires)}. Install from Catalog before enabling."
            )
        elif missing_requires:
            lines.append(
                "Recommended tool(s): "
                f"{', '.join(missing_requires)}. Not required — apply still runs and "
                "falls back automatically."
            )
        elif policy.requires and missing_requires is not None:
            lines.append(f"Required tool(s): {', '.join(policy.requires)}.")
        if policy.detail_lines is None:
            lines.extend(details.get(policy.id, ("Space toggles this reversible shell policy.",)))
        if policy.id.startswith("tweak:") and policy.detail_lines is None:
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
        if self.app.refuse_if_mutating(self):
            return
        # Re-read at the mutation point: a prerequisite can land after the render.
        requirements_error = self._read_requirements(policy)
        active = self.active_state.get(policy.id)
        missing_requires = self._missing.get(policy.id)
        if active is None or missing_requires is None:
            if requirements_error is not None:
                self._read_error = _read_failure(requirements_error)
            self._refuse_unreadable()
            return
        if not active and missing_requires and policy.hard_requires:
            self.status.set(
                "Install required tool(s) first: "
                f"{', '.join(missing_requires)}. Open Catalog, install them, then retry.",
                "warn",
            )
            self.query_one(DataTable[Any]).update_cell(
                policy.id, "requires", self._requires_cell(policy)
            )
            self._set_detail(policy)
            return
        action = policy.remove if active else policy.apply
        result, self.error = run_live(action)
        self._finish_toggle(policy, active, result)

    def _finish_toggle(self, policy: Policy, active: bool, result: PolicyResult | None) -> None:
        if result is None:
            self.app.show_result(
                self,
                f"Policy change failed: {self.error}. Check permissions, then press space.",
                "error",
                elsewhere=(
                    f"Policy change failed: {self.error}."
                    " Check permissions, then open Policies and press space."
                ),
            )
            self.app.request_refresh()
            return
        if not result.changed:  # a refused or no-op settings write: the row keeps its state
            self.app.show_result(self, result.warning or "", "warn")
            self.app.request_refresh()
            return
        new_active = not active
        self.active_state[policy.id] = new_active
        self._drift.discard(policy.id)
        self.query_one(DataTable[Any]).update_cell(policy.id, "state", self._state_cell(policy.id))
        self._read_requirements(policy)
        self.query_one(DataTable[Any]).update_cell(
            policy.id, "requires", self._requires_cell(policy)
        )
        self._set_detail(policy)
        verb = "enabled" if new_active else "disabled"
        self.app.show_result(
            self, self._summary(policy, verb, result), "warn" if result.warning else "ok"
        )
        self.app.request_refresh()

    def _summary(self, policy: Policy, verb: str, result: PolicyResult) -> str:
        # One line per outcome: a single joined line overflows the terminal width
        # and truncates the reload guidance.
        parts = [f"{policy.label} {verb}."]
        parts.extend(f"{layer.name}: {layer.detail}" for layer in result.layers)
        if result.reload_hint:
            parts.append(result.reload_hint)
        if result.warning:
            parts.append(result.warning)
        return multiline_summary(parts)

    def action_pick_link_mode(self) -> None:
        if self._set_link_mode is None:
            self.status.set(
                "Link mode cannot be changed from this entry point.",
                "warn",
            )
            return
        if self.app.refuse_if_mutating(self):  # before the picker
            return
        self.app.push_screen(LinkModeScreen(), self._link_mode_picked)

    def _link_mode_picked(self, value: str | None) -> None:
        if value is None:
            self.status.set(
                "Link mode unchanged because the picker was cancelled.",
                "warn",
            )
            return
        setter = self._set_link_mode
        if setter is None:
            return
        # At the mutation point: the modal can outlive a
        # mutation that started after it opened.
        if self.app.refuse_if_mutating(self):
            return
        aware_active = self.link_mode_aware_active()
        old = self._link_mode() if self._link_mode is not None else "centralized"
        report, error = run_live(lambda: move_link_mode(aware_active, value, setter, old_mode=old))
        if error is not None:
            self.mark_lost_policies_off(error)
            self.status.set(error, "error")
            return
        text, severity = link_mode_status(value, report or (), old_mode=old)
        self.status.set(text, severity)
        self._refresh_link_mode_line()

    def mark_lost_policies_off(self, error: str) -> None:
        """A failed move whose error names policies gone from both
        modes flips their rows OFF, so the table never claims a policy that
        is no longer on disk."""
        for policy_id in lost_policy_ids(error):
            self.active_state[policy_id] = False

    def link_mode_aware_active(self) -> list[Policy]:
        """The active, link-mode-aware policies: the ones a mode change moves.

        The live truth is each policy's own on-disk activity, re-probed at the
        moment of the change through the same predicate the uninstall sweep
        uses (installer.uninstall.policy_owned). The
        cached active_state is only the table's last paint: another view can
        remove a policy without this screen ever hearing about it, and moving
        on a stale cache would resurrect it.
        """
        return [
            policy for policy in self._policies if policy.link_mode_aware and policy_owned(policy)
        ]


def link_mode_status(value: str, report: Sequence[PolicyMove], *, old_mode: str) -> tuple[str, str]:
    """(text, severity) both link-mode pickers show after a move: the saved
    mode, the policies moved, every failure named, and — when the move left
    split mode, whose aliases live in the rc files themselves — the exact
    action that refreshes the PATH wiring so the shells source ~/.myshellrc.
    Severity is warn when any entry failed (the mode
    itself was still saved), ok otherwise."""
    parts = [f"Link mode saved: {value}."]
    moved = [entry.policy_id for entry in report if entry.status == "moved"]
    failed = [entry for entry in report if entry.status == "failed"]
    if moved:
        parts.append(f" Moved: {', '.join(moved)}.")
    if old_mode == "split" and value != "split" and moved:
        parts.append(
            " The moved aliases now live in ~/.myshellrc, which the shells may not"
            f' source yet; refresh the PATH wiring: make fix ARGS="--link-mode {value}".'
        )
    for entry in failed:
        parts.append(f" Failed: {entry.policy_id} ({entry.detail}).")
    return "".join(parts), ("warn" if failed else "ok")


_POLICY_FIXED_COLUMNS = ("state", "policy", "requires")


_POLICY_EFFECT_FLOOR = 12
