import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar, cast

import pytest
from textual.pilot import Pilot
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from installer import daemon
from installer.app import UninstallDecision
from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool
from installer.ownership import ManagerInventory, ManagerOwnership, Owner, OwnershipCandidate
from installer.platform import Platform
from installer.pnpm_globals import NodeGlobal, NodeGlobalsReport, reinstall_preview
from installer.policy import (
    Policy,
    PolicyLayer,
    PolicyResult,
    daemon_policy,
    ensure_daemon_default,
    omz_plugins_policy,
)
from installer.run import CommandError
from installer.ui_common import BASE_VIEW
from installer.uninstall import SweepResult, ToolRow
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import VersionRefreshService, VersionStatus
from installer.versions import VersionError
from installer.wizard_app import (
    VIEW_ORDER,
    ConfirmUninstall,
    DoctorScreen,
    NavScreen,
    PoliciesScreen,
    PolicyInputs,
    TimePickerScreen,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
)


def _tool(tool_id: str) -> Tool:
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
    )


def _recorder(
    captured: list[UninstallDecision], result: SweepResult | None = None
) -> Callable[[UninstallDecision], SweepResult]:
    """A remove closure that records the decision and reports a sweep outcome."""

    def record(decision: UninstallDecision) -> SweepResult:
        captured.append(decision)
        return result if result is not None else SweepResult()

    return record


def _removable_row(tool: Tool, paths: list[Path]) -> ToolRow:
    return ToolRow(tool, "removable", paths, "installed in userspace — removable here", True)


_T = TypeVar("_T")


def _predicate(value: _T | Callable[[], _T]) -> Callable[[], _T]:
    """Accept a plain value or the live predicate the production wire passes.

    Every environment input on UninstallInputs is a predicate, because another
    view can change it while this screen is suspended. Most tests only care
    about one fixed reading, so they keep passing the value.
    """
    if callable(value):
        # _T is unbounded, so pyright cannot rule out a _T that is itself
        # callable; this branch is the caller's declared intent either way.
        return cast("Callable[[], _T]", value)
    frozen = value

    def read() -> _T:
        return frozen

    return read


def _uninstall_inputs(
    *,
    rows: list[ToolRow] | None = None,
    ban_names: list[str] | Callable[[], list[str]] | None = None,
    has_path_block: bool | Callable[[], bool] = False,
    remove: Callable[[UninstallDecision], SweepResult] = lambda _decision: SweepResult(),
    tweak_ids: tuple[str, ...] | Callable[[], tuple[str, ...]] = (),
) -> UninstallInputs:
    return UninstallInputs(
        rows=rows if rows is not None else [],
        ban_names=_predicate(ban_names if ban_names is not None else []),
        has_path_block=_predicate(has_path_block),
        remove=remove,
        tweak_ids=_predicate(tweak_ids),
    )


def _ok_result() -> PolicyResult:
    return PolicyResult(
        layers=(PolicyLayer("Shims", "3 active in /bin"), PolicyLayer("Aliases", "written to /rc")),
        reload_hint="Open a new shell or run `hash -r` so cached command paths refresh.",
        warning=None,
    )


def _fake_policy(
    *,
    id: str = "ban",
    active: bool = False,
    apply: Callable[[], PolicyResult] = _ok_result,
    remove: Callable[[], PolicyResult] = _ok_result,
    log_path: Path | None = None,
    set_schedule: Callable[[int, int], PolicyResult] | None = None,
    read_schedule: Callable[[], tuple[int, int] | None] | None = None,
) -> Policy:
    return Policy(
        id=id,
        label="pip/npm ban",
        description="blocks bare pip/npm",
        active=active,
        apply=apply,
        remove=remove,
        log_path=log_path,
        set_schedule=set_schedule,
        read_schedule=read_schedule,
    )


def _policy_inputs(policies: list[Policy] | None = None) -> PolicyInputs:
    return PolicyInputs(policies=policies if policies is not None else [_fake_policy()])


def _app(
    *,
    report: DoctorReport | None = None,
    guard_status: dict[str, bool] | Callable[[], dict[str, bool]] | None = None,
    guard_warning: str | None = None,
    fix_preview: str = "Will wire ~/.local/bin into ~/.zshrc",
    fix: Callable[[], None] = lambda: None,
    uninstall: UninstallInputs | None = None,
    policies: PolicyInputs | None = None,
    node_globals: Callable[[], NodeGlobalsReport] | None = None,
    globals_preview: Callable[[NodeGlobalsReport], str] | None = None,
    reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
    initial_view: str = BASE_VIEW,
    daemon_default: Callable[[], bool] | None = None,
    daemon_default_policy_id: str | None = None,
) -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")]
    installed: Mapping[str, bool] = {"rg": True, "fd": False}
    read_status = _predicate(guard_status or {"pip": False, "npm": False})
    return UnifiedApp(
        tools,
        installed,
        {"search": "find things"},
        report=report or DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (read_status(), guard_warning),
        fix_preview=fix_preview,
        fix=fix,
        uninstall=uninstall or _uninstall_inputs(),
        policies=policies or _policy_inputs(),
        node_globals=node_globals,
        globals_preview=globals_preview,
        reinstall_globals=reinstall_globals,
        initial_view=initial_view,
        daemon_default=daemon_default,
        daemon_default_policy_id=daemon_default_policy_id,
    )


async def _settle(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    """Wait for the Doctor's thread workers: the globals audit and the reinstall.

    Both run off the event loop and report back by posted message, so anything
    asserting on rendered globals state has to wait for the message rather than
    for the keypress that started the work.
    """
    for _ in range(400):
        screen = app.screen
        if not isinstance(screen, DoctorScreen):
            break
        if not screen.globals_running and not screen.globals_auditing:
            break
        await pilot.pause()
    await pilot.pause()


def _mmdc_report(*, missing: tuple[str, ...] = ("mmdc",)) -> NodeGlobalsReport:
    return NodeGlobalsReport(
        entries=(NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),),
        missing=missing,
        managed=("@mermaid-js/mermaid-cli",),
    )


def test_default_palette_is_disabled() -> None:
    assert UnifiedApp.ENABLE_COMMAND_PALETTE is False


def test_view_order_lists_every_view() -> None:
    assert VIEW_ORDER == ("system", "user", "ai", "doctor", "uninstall", "policies")


async def test_starts_on_the_system_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "system"


async def test_number_key_navigates_to_each_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "user"
        await pilot.press("3")
        assert app.current_view == "ai"
        await pilot.press("4")
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)
        await pilot.press("5")
        assert app.current_view == "uninstall"
        await pilot.press("6")
        assert app.current_view == "policies"
        await pilot.press("1")
        assert app.current_view == "system"


async def test_uninstall_view_is_reachable() -> None:
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert app.current_view == "uninstall"
        assert isinstance(app.screen, UninstallScreen)


async def test_doctor_screen_renders_guidance() -> None:
    app = _app(report=DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, DoctorScreen)
        text = "".join(g.title + g.meaning + g.next_step for g in app.screen.guidance)
        assert "/a/bin" in text
        assert "make fix" in text


async def test_doctor_screen_adapts_missing_path_guidance_for_tui() -> None:
    app = _app(
        report=DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, DoctorScreen)
        body = app.screen.query_one("#doctor-body", Static).render()
        rendered = str(body)
        assert "Press enter to wire the managed PATH into your shells." in rendered
        assert "Run `make fix`" not in rendered


def test_doctor_screen_css_centers_the_body() -> None:
    assert "DoctorScreen {" in DoctorScreen.DEFAULT_CSS
    assert "align: center top;" in DoctorScreen.DEFAULT_CSS


async def test_opening_doctor_does_not_apply_fix() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert calls == []
        assert screen.applied is False
        assert screen.error is None


async def test_doctor_enter_applies_fix_once() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")
        assert calls == ["fix"]
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True
        assert screen.error is None
        await pilot.press("enter")
        assert calls == ["fix"]


async def test_doctor_hidden_a_alias_applies_fix() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("a")
        assert calls == ["fix"]
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True


async def test_doctor_apply_failure_shows_error_and_allows_retry() -> None:
    calls = 0

    def fix() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("read-only rc file")

    app = _app(fix=fix)

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is False
        assert screen.error == "read-only rc file"
        assert "read-only rc file" in str(screen.query_one("#doctor-body", Static).render())
        await pilot.press("enter")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True
        assert screen.error is None


async def test_initial_view_opens_on_that_view() -> None:
    app = _app(initial_view="doctor")
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)


async def test_navigating_to_the_current_view_is_a_no_op() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("1")  # already on the system view
        assert app.current_view == "system"
        assert app.is_running


async def test_palette_and_key_resolve_to_the_same_view() -> None:
    # Direct key route.
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert app.current_view == "doctor"
    by_key = app.current_view
    # Palette route: open Ctrl+P, pick the "doctor" item.
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "down", "down", "enter")  # 4th item is doctor
        assert app.current_view == "doctor"
    assert app.current_view == by_key


async def test_palette_escape_does_not_navigate() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("escape")
        assert app.current_view == "system"
        assert not isinstance(app.screen, NavScreen)


async def test_ctrl_c_aborts_from_a_placeholder_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")  # navigate onto the doctor placeholder
        assert app.current_view == "doctor"
        await pilot.press("ctrl+c")  # abort must work from any view
        assert not app.is_running
    assert app.return_value is None


async def test_number_keys_are_inert_while_the_palette_is_open() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        depth = len(app.screen_stack)
        await pilot.press("4")  # must NOT navigate underneath the modal
        assert isinstance(app.screen, NavScreen)
        assert app.current_view == "system"
        assert len(app.screen_stack) == depth  # no extra push


async def test_ctrl_p_does_not_stack_a_second_palette() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        depth = len(app.screen_stack)
        await pilot.press("ctrl+p")  # second press is inert
        assert isinstance(app.screen, NavScreen)
        assert len(app.screen_stack) == depth
        await pilot.press("escape")
        assert not isinstance(app.screen, NavScreen)


def _managed_row(tool: Tool) -> ToolRow:
    return ToolRow(tool, "managed", [], "managed by Homebrew — `brew uninstall jq`", False)


def _absent_row(tool: Tool) -> ToolRow:
    return ToolRow(tool, "absent", [], "not installed", False)


def _unavailable_row(tool: Tool) -> ToolRow:
    return ToolRow(tool, "unavailable", [], "not available on debian", False)


async def test_uninstall_toggle_selects_highlighted_tool() -> None:
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("space")
        assert app.screen.selected == {"rg"}
        await pilot.press("space")
        assert app.screen.selected == set()


async def test_uninstall_select_all_includes_ban_and_block() -> None:
    inputs = _uninstall_inputs(
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip", "npm"],
        has_path_block=True,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")
        assert app.screen.selected == {"rg"}
        assert app.screen.remove_ban is True
        assert app.screen.remove_path_block is True
        await pilot.press("i")  # invert clears everything
        assert app.screen.selected == set()
        assert app.screen.remove_ban is False
        assert app.screen.remove_path_block is False


async def test_uninstall_lists_all_tools_with_their_states() -> None:
    """Catalog parity: every tool appears regardless of state."""
    inputs = _uninstall_inputs(
        rows=[
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
            _managed_row(_tool("jq")),
            _absent_row(_tool("fd")),
            _unavailable_row(_tool("rect")),
        ]
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        table = app.screen.query_one(DataTable[Any])
        keys = {row.value for row in table.rows}
        assert {"rg", "jq", "fd", "rect"} <= keys


async def test_uninstall_non_selectable_rows_are_inert() -> None:
    """Managed/absent/unavailable rows do not toggle; space on them is inert."""
    inputs = _uninstall_inputs(
        rows=[
            _managed_row(_tool("jq")),
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
        ]
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")  # select-all over selectable only
        assert app.screen.selected == {"rg"}  # jq never enters


async def test_uninstall_non_selectable_row_shows_hint() -> None:
    inputs = _uninstall_inputs(rows=[_managed_row(_tool("jq"))])
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.pause()
        assert "brew uninstall jq" in screen.detail_text


async def test_uninstall_apply_calls_remove_and_flips_applied() -> None:
    captured: list[UninstallDecision] = []
    rows = [_removable_row(_tool("rg"), [Path("/opt/rg")])]
    app = _app(uninstall=_uninstall_inputs(rows=rows, remove=_recorder(captured)))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")  # select rg
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await pilot.pause()
        assert len(captured) == 1
        assert screen.applied is True


async def test_uninstall_empty_selection_refuses() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])], remove=_recorder(captured)
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")  # nothing selected
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert captured == []  # closure never called
        assert "at least one" in app.screen.status.text


async def test_uninstall_apply_error_surfaces_and_does_not_crash() -> None:
    def boom(_decision: UninstallDecision) -> SweepResult:
        raise OSError("permission denied")

    inputs = _uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])], remove=boom)
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space")  # select rg
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm → _apply_removal raises OSError
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status.text.lower()


async def test_uninstall_destructive_red_accent() -> None:
    """The WayfindingHeader paints the uninstall view with the destructive red accent."""
    from installer.ui_common import WayfindingHeader

    app = _app(
        uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)):
        header = app.screen.query_one(WayfindingHeader)
        assert "red" in header.render_markup()


async def test_uninstall_initial_view_opens_on_uninstall() -> None:
    app = _app(
        uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, UninstallScreen)


async def test_uninstall_empty_state_shows_nothing_line() -> None:
    app = _app(uninstall=_uninstall_inputs())  # no rows, no ban, no block
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")  # no-op
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert "Nothing to uninstall" in app.screen.status.text


async def test_ctrl_c_aborts_from_uninstall_view() -> None:
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("ctrl+c")
    assert app.return_value is None


async def test_uninstall_empty_table_toggle_noop() -> None:
    """Space on an empty uninstall table is a no-op."""
    app = _app(uninstall=_uninstall_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("space")
        assert app.screen.selected == set()
        assert app.screen.applied is False


async def test_uninstall_partial_selection_apply() -> None:
    """Only selected tools appear in the UninstallDecision paths."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        rows=[
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
            _removable_row(_tool("fd"), [Path("/opt/fd")]),
        ],
        remove=_recorder(captured),
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        # Cursor starts on row 0 (rg); space selects only that one.
        await pilot.press("space")
        assert len(app.screen.selected) == 1
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await pilot.pause()  # wait for _apply_removal to complete
    assert len(captured) == 1
    assert len(captured[0].paths) == 1
    assert Path("/opt/rg") in captured[0].paths
    assert Path("/opt/fd") not in captured[0].paths


async def test_uninstall_applied_summary_ban_and_path() -> None:
    """Status text mentions ban and PATH lines when both are selected.
    Also verifies that remove_ban/remove_path_block read the browser's live
    selection correctly after the modal is dismissed (the post-modal read path)."""
    inputs = _uninstall_inputs(
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        has_path_block=True,
        remove=lambda _d: SweepResult(),
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")  # select all: tool + ban + path block
        assert screen.remove_ban is True
        assert screen.remove_path_block is True
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert screen.applied is True
        assert "ban removed" in screen.status.text
        assert "PATH wiring removed" in screen.status.text


async def test_uninstall_applied_summary_omits_tool_line_when_no_tool() -> None:
    """Selecting only the ban (no tool) yields no 'Removed N tool(s).' line."""
    inputs = _uninstall_inputs(
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        remove=lambda _d: SweepResult(),
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        # rows: [#removable, rg, #environment, #ban] — step past the section header.
        await pilot.press("down", "down")  # onto the ban row
        await pilot.press("space")  # select only the ban
        assert screen.selected == set()  # no tool ids selected
        assert screen.remove_ban is True
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert screen.applied is True
        assert "tool(s)" not in screen.status.text
        assert "ban removed" in screen.status.text


async def test_uninstall_cancel_modal_removes_nothing() -> None:
    captured: list[UninstallDecision] = []
    rows = [_removable_row(_tool("rg"), [Path("/opt/rg")])]
    app = _app(uninstall=_uninstall_inputs(rows=rows, remove=_recorder(captured)))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")
        await pilot.press("enter")  # accept → modal
        await pilot.press("escape")  # cancel
        await pilot.pause()
        assert captured == []
        assert screen.applied is False


async def test_uninstall_confirm_modal_shows_artifact_count() -> None:
    rows = [_removable_row(_tool("rg"), [Path("/opt/rg")])]
    app = _app(uninstall=_uninstall_inputs(rows=rows))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")  # accept → modal
        await pilot.pause()
        assert isinstance(app.screen, ConfirmUninstall)
        assert "1" in app.screen.summary  # one item to remove


async def test_uninstall_screen_omits_the_tweaks_row_when_none_are_active() -> None:
    app = _app(
        uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        keys = {row.value for row in table.rows}
        assert "#tweaks" not in keys
        await pilot.press("a")
        assert screen.remove_tweaks is False


async def test_uninstall_screen_reports_the_tweaks_lever_in_its_summaries() -> None:
    inputs = _uninstall_inputs(
        tweak_ids=("countdown", "omz-plugins"),
        remove=lambda _d: SweepResult(),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.pause()
        assert "shell tweak" in screen.detail_text.lower()
        await pilot.press("a")
        assert screen.remove_tweaks is True
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmUninstall)
        assert "the shell tweaks" in app.screen.summary


async def test_uninstall_toggle_clears_stale_validation_toast() -> None:
    """A refusal toast must not linger once the selection changes."""
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")  # nothing selected → refusal toast
        assert isinstance(app.screen, UninstallScreen)
        assert "at least one" in app.screen.status.text
        await pilot.press("space")  # select rg → toast cleared
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.status.text == ""


async def test_palette_from_placeholder_navigates_without_desync() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")  # -> doctor view
        assert app.current_view == "doctor"
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        # ListView starts on system(0); step to policies(5)
        await pilot.press("down", "down", "down", "down", "down", "enter")
        assert app.current_view == "policies"
        assert not isinstance(app.screen, NavScreen)
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_view_is_reachable() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)


async def test_clicking_main_header_navigates_between_views() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#nav-policies")
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)
        await pilot.click("#nav-doctor")
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)


async def test_policies_reachable_via_palette() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "down", "down", "down", "down", "enter")  # 6th item: policies
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_initial_view_opens_on_policies() -> None:
    app = _app(initial_view="policies")
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, PoliciesScreen)


async def test_policy_toggle_enables_inactive_policy() -> None:
    calls: list[str] = []
    policy = _fake_policy(active=False, apply=lambda: (calls.append("apply"), _ok_result())[1])
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        await pilot.press("space")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["apply"]
        assert app.screen.active_state["ban"] is True
        assert "enabled" in app.screen.status.text
        assert "Shims:" in app.screen.status.text


async def test_policy_state_cell_carries_glyph_for_on_and_off() -> None:
    """State must be legible without relying on color: the single row is always
    focused, so the green/dim styling collapses under the selection highlight.
    A ●/○ glyph keeps on-vs-off distinct in monochrome and on toggle."""
    from textual.widgets import DataTable

    app = _app(policies=_policy_inputs([_fake_policy(active=False)]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        table = screen.query_one(DataTable[Any])
        assert table.get_cell("ban", "state").plain == "○ [off]"
        await pilot.press("space")
        assert table.get_cell("ban", "state").plain == "● [on]"


async def test_policy_detail_panel_describes_the_ban_as_it_behaves_now() -> None:
    # Enabling the ban wraps the user's own pnpm binary and gives up pnpm's
    # gated postinstalls for global installs. The detail said none of that.
    app = _app(policies=_policy_inputs([_fake_policy()]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        assert isinstance(app.screen, PoliciesScreen)
        detail = app.screen.detail_text
        assert "volta install" in detail
        assert "pnpm" in detail
        assert "install scripts" in detail


async def test_policy_detail_panel_explains_tweak_rules() -> None:
    policies = [
        Policy(
            id="tweak:docker",
            label="Docker shortcuts",
            description="docker-ps, docker-stats, docker-memory",
            active=False,
            apply=_ok_result,
            remove=_ok_result,
            requires=("watch",),
        ),
        Policy(
            id="tweak:countdown",
            label="Countdown helper",
            description="wait_time flexible countdown",
            active=False,
            apply=_ok_result,
            remove=_ok_result,
        ),
        Policy(
            id="tweak:claude-skip",
            label="claude skip-permissions",
            description="alias claude skip permissions",
            active=False,
            apply=_ok_result,
            remove=_ok_result,
        ),
    ]
    app = _app(policies=_policy_inputs(policies), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "Required tool(s): watch" in screen.detail_text
        assert "watch-powered" in screen.detail_text
        await pilot.press("down")
        assert "1d10m15s" in screen.detail_text
        assert "--seconds" in screen.detail_text
        await pilot.press("down")
        assert "dangerously-skip-permissions" in screen.detail_text


async def test_policy_detail_panel_explains_codex_skip() -> None:
    policy = Policy(
        id="tweak:codex-skip",
        label="codex skip-permissions",
        description="alias codex codex --dangerously-bypass-approvals-and-sandbox",
        active=False,
        apply=_ok_result,
        remove=_ok_result,
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        del pilot
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "dangerously-bypass-approvals-and-sandbox" in screen.detail_text
        assert "trusted" in screen.detail_text.lower()


async def test_policy_detail_panel_explains_myshellrc_sourcing_for_every_tweak() -> None:
    policies = [
        Policy(
            id="tweak:claude-skip",
            label="claude skip-permissions",
            description="alias claude skip permissions",
            active=False,
            apply=_ok_result,
            remove=_ok_result,
        ),
        Policy(
            id="tweak:codex-skip",
            label="codex skip-permissions",
            description="alias codex codex --dangerously-bypass-approvals-and-sandbox",
            active=False,
            apply=_ok_result,
            remove=_ok_result,
        ),
    ]
    app = _app(policies=_policy_inputs(policies), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "~/.myshellrc" in screen.detail_text
        assert "split" in screen.detail_text.lower()
        await pilot.press("down")
        assert "~/.myshellrc" in screen.detail_text
        assert "split" in screen.detail_text.lower()


async def test_policy_detail_panel_explains_opencode_auto_is_narrower_than_a_full_bypass() -> None:
    policy = Policy(
        id="tweak:opencode-auto",
        label="opencode auto-approve",
        description="alias opencode opencode --auto — not a full bypass, deny rules still apply",
        active=False,
        apply=_ok_result,
        remove=_ok_result,
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        del pilot
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        detail = screen.detail_text
        assert "Space toggles this reversible shell policy." not in detail
        assert "deny" in detail.lower()


async def test_policy_detail_panel_explains_cursor_agent_model_wrapper() -> None:
    policy = Policy(
        id="tweak:cursor-agent-model",
        label="cursor-agent default model",
        description="injects --model gpt-5.6-sol-high when --model is absent",
        active=False,
        apply=_ok_result,
        remove=_ok_result,
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        del pilot
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        detail = screen.detail_text
        assert "gpt-5.6-sol-high" in detail
        assert "requests" in detail
        assert "guarantees" not in detail
        assert "verifies" not in detail
        assert "plan" in detail.lower()
        assert "alias" in detail.lower()
        assert "before" in detail.lower()


async def test_policy_missing_required_tool_blocks_enable() -> None:
    calls: list[str] = []
    policy = Policy(
        id="tweak:docker",
        label="Docker shortcuts",
        description="docker helpers",
        active=False,
        apply=lambda: (calls.append("apply"), _ok_result())[1],
        remove=_ok_result,
        requires=("watch",),
        missing_requires=("watch",),
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "Missing required tool(s): watch" in screen.detail_text
        await pilot.press("space")
        assert calls == []
        assert screen.active_state["tweak:docker"] is False
        assert "Install required tool(s) first: watch" in screen.status.text


async def test_policy_with_hard_requires_false_still_enables_when_requires_missing_with_recommended_copy() -> (  # noqa: E501
    None
):
    calls: list[str] = []
    policy = Policy(
        id="daemon:test",
        label="Background daemon",
        description="daemon helpers",
        active=False,
        apply=lambda: (calls.append("apply"), _ok_result())[1],
        remove=_ok_result,
        requires=("fd", "rg"),
        missing_requires=("fd", "rg"),
        hard_requires=False,
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "Recommended tool(s): fd, rg. Not required" in screen.detail_text
        assert "Missing required tool(s)" not in screen.detail_text
        await pilot.press("space")
        assert calls == ["apply"]
        assert screen.active_state["daemon:test"] is True
        assert "enabled" in screen.status.text
        assert "Recommended tool(s): fd, rg. Not required" in screen.detail_text
        assert "Missing required tool(s)" not in screen.detail_text
        assert "before enabling" not in screen.detail_text


async def test_existing_policies_render_byte_identical_effect_and_detail() -> None:
    """log_path is None for every existing policy: the Effect-column cell and
    _policy_detail's own output must be byte-identical before and after this
    task's changes (11-03-PLAN.md's own regression requirement)."""
    ban = _fake_policy(active=False)
    docker = Policy(
        id="tweak:docker",
        label="Docker shortcuts",
        description="docker helpers",
        active=False,
        apply=_ok_result,
        remove=_ok_result,
        requires=("watch",),
    )
    app = _app(policies=_policy_inputs([ban, docker]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        table = screen.query_one(DataTable[Any])
        assert table.get_cell("ban", "effect").plain == "shell config: blocks bare pip/npm"
        assert table.get_cell("tweak:docker", "effect").plain == "shell config: docker helpers"
        assert screen.detail_text == (
            "pip/npm ban — blocks bare pip/npm\n"
            "Blocks bare pip and pip3, redirects npx to pnpm dlx, and routes"
            " npm/pnpm global installs to volta install.\n"
            "Wraps your pnpm binary with a PATH shim: only global adds are"
            " rerouted, every other pnpm command passes straight through.\n"
            "Global installs then run npm's install scripts unrestricted, which"
            " pnpm gates — keep untrusted packages on a project-local pnpm add.\n"
            "Writes PATH shims plus interactive aliases, then asks for a shell reload.\n"
            "Use when humans or agents keep reaching for unmanaged package installers."
        )
        await pilot.press("down")
        assert "Required tool(s): watch" in screen.detail_text
        assert "watch-powered" in screen.detail_text


async def test_daemon_policy_detail_uses_accurate_daemon_copy() -> None:
    policy = Policy(
        id="daemon:prune-tmpdir",
        label="Background tmpdir cleanup",
        description="runs scripts/prune-user-tmpdir.sh daily via a macOS LaunchAgent",
        active=False,
        apply=_ok_result,
        remove=_ok_result,
        requires=("fd", "rg"),
        missing_requires=("fd", "rg"),
        hard_requires=False,
        log_path=Path("/tmp/tools-installer-test-daemon.log"),
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        table = screen.query_one(DataTable[Any])
        assert table.get_cell("daemon:prune-tmpdir", "effect").plain.startswith("scheduled job: ")
        detail = screen.detail_text
        assert "Space toggles this reversible shell policy." not in detail
        assert "LaunchAgent" in detail
        assert "find/grep" in detail


async def test_policy_with_log_path_and_no_log_file_shows_no_last_run_and_placeholder(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "prune-daemon.log"
    policy = _fake_policy(active=True, log_path=log_path)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "last run" not in screen.detail_text
        await pilot.press("l")
        assert screen.detail_text == "log file does not exist yet"
        await pilot.press("l")
        assert "last run" not in screen.detail_text


async def test_policy_with_log_file_shows_last_run_and_l_toggles_raw_content(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "prune-daemon.log"
    log_path.write_text("=== 2026-09-01T03:00:00+00:00 ===\ndeleted: 4\n\n")
    policy = _fake_policy(active=True, log_path=log_path)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "last run: 2026-09-01T03:00:00+00:00, 4 item(s) removed" in screen.detail_text
        await pilot.press("l")
        assert "=== 2026-09-01T03:00:00+00:00 ===" in screen.detail_text
        assert "deleted: 4" in screen.detail_text
        await pilot.press("l")
        assert "last run: 2026-09-01T03:00:00+00:00, 4 item(s) removed" in screen.detail_text


async def test_policy_with_read_schedule_shows_persistent_schedule_line() -> None:
    with_schedule = _fake_policy(
        active=True,
        set_schedule=lambda _h, _m: _ok_result(),
        read_schedule=lambda: (3, 30),
    )
    app = _app(policies=_policy_inputs([with_schedule]), initial_view="policies")
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "scheduled daily at 03:30" in screen.detail_text

    without_schedule = _fake_policy(
        active=True,
        set_schedule=lambda _h, _m: _ok_result(),
        read_schedule=lambda: None,
    )
    app2 = _app(policies=_policy_inputs([without_schedule]), initial_view="policies")
    async with app2.run_test(size=(100, 30)):
        screen2 = app2.screen
        assert isinstance(screen2, PoliciesScreen)
        assert "scheduled daily at" not in screen2.detail_text

    no_set_schedule = _fake_policy(active=True, read_schedule=lambda: (3, 30))
    app3 = _app(policies=_policy_inputs([no_set_schedule]), initial_view="policies")
    async with app3.run_test(size=(100, 30)):
        screen3 = app3.screen
        assert isinstance(screen3, PoliciesScreen)
        assert "scheduled daily at" not in screen3.detail_text


async def test_toggle_log_is_noop_when_policy_has_no_log_path() -> None:
    policy = _fake_policy(active=True)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        before = screen.detail_text
        await pilot.press("l")
        assert screen.detail_text == before


async def test_toggle_log_against_invalid_utf8_shows_read_failure_placeholder(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "prune-daemon.log"
    log_path.write_bytes(b"\xff\xfe not valid utf-8")
    policy = _fake_policy(active=True, log_path=log_path)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("l")
        assert screen.detail_text.startswith("log could not be read: ")


async def test_normal_detail_render_is_defensive_against_corrupt_schedule_and_log(
    tmp_path: Path,
) -> None:
    """Corrupt managed files must never crash mount/row-highlight rendering —
    only the l toggle's own read is defended by an earlier test; this proves
    the NORMAL render path is equally defended (11-REVIEWS.md cycle 2 #10)."""
    log_path = tmp_path / "prune-daemon.log"
    log_path.write_bytes(b"\xff\xfe not valid utf-8")

    def _raising_read_schedule() -> tuple[int, int] | None:
        raise ValueError("corrupt plist")

    policy = _fake_policy(
        active=True,
        log_path=log_path,
        set_schedule=lambda _h, _m: _ok_result(),
        read_schedule=_raising_read_schedule,
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        # No exception propagated out of the pilot; the two lines are omitted.
        assert "last run" not in screen.detail_text
        assert "scheduled daily at" not in screen.detail_text


async def test_normal_detail_render_defends_against_last_run_summary_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second, independent belt on top of installer.daemon.last_run_summary's
    own total/never-raising guarantee — this exercises wizard_app's own guard
    directly, since the real function never raises by construction."""

    def _raise(_log_path: Path) -> str | None:
        raise OSError("boom")

    monkeypatch.setattr(daemon, "last_run_summary", _raise)
    policy = _fake_policy(active=True, log_path=Path("/nonexistent/tools-installer-test.log"))
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "last run" not in screen.detail_text


def test_time_picker_widget_ids_are_all_valid_textual_identifiers() -> None:
    """Constructing the actual widgets is itself the test: a raw "HH:MM" id
    (e.g. "00:00") raises Textual's own BadIdentifier — live-verified against
    this project's installed Textual version — so a clean construction here
    is the proof every one of the 48 generated ids is valid."""
    items = [
        ListItem(Label(f"{hour:02d}:{minute:02d}"), id=f"time-{hour:02d}-{minute:02d}")
        for hour in range(24)
        for minute in (0, 30)
    ]
    assert len(items) == 48
    assert items[0].id == "time-00-00"
    assert items[-1].id == "time-23-30"


def test_time_picker_on_list_view_selected_is_a_noop_without_an_id() -> None:
    """Structurally unreachable in production (every real item carries an id),
    but on_list_view_selected still narrows event.item.id: str | None for
    pyright, so this proves the guard itself never raises or dismisses."""
    screen = TimePickerScreen()
    event = ListView.Selected(ListView(), ListItem(), 0)
    screen.on_list_view_selected(event)  # must not raise


async def test_time_picker_is_noop_when_policy_has_no_set_schedule() -> None:
    policy = _fake_policy(active=True)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("t")
        assert isinstance(app.screen, PoliciesScreen)  # the modal never opened


async def test_time_picker_shows_enable_first_message_for_inactive_policy() -> None:
    calls: list[tuple[int, int]] = []

    def fake_set_schedule(hour: int, minute: int) -> PolicyResult:
        calls.append((hour, minute))
        return _ok_result()

    policy = _fake_policy(active=False, set_schedule=fake_set_schedule)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("t")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == []
        assert "Enable this policy first" in screen.status.text


async def test_time_picker_selecting_a_slot_calls_set_schedule_with_parsed_hour_minute() -> None:
    calls: list[tuple[int, int]] = []

    def fake_set_schedule(hour: int, minute: int) -> PolicyResult:
        calls.append((hour, minute))
        return _ok_result()

    policy = _fake_policy(
        active=True, set_schedule=fake_set_schedule, read_schedule=lambda: (1, 30)
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("t")
        assert isinstance(app.screen, TimePickerScreen)
        # ListView starts on 00:00 (index 0); step to 01:30 (index 3).
        await pilot.press("down", "down", "down", "enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == [(1, 30)]
        assert "rescheduled" in screen.status.text
        assert "scheduled daily at 01:30" in screen.detail_text


async def test_time_picker_escape_cancels_without_calling_set_schedule() -> None:
    calls: list[tuple[int, int]] = []

    def fake_set_schedule(hour: int, minute: int) -> PolicyResult:
        calls.append((hour, minute))
        return _ok_result()

    policy = _fake_policy(active=True, set_schedule=fake_set_schedule)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("t")
        assert isinstance(app.screen, TimePickerScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == []


async def test_time_picker_list_view_does_not_overflow_smallest_tested_terminal() -> None:
    """Proves TimePickerScreen's own DEFAULT_CSS is actually applied — a bounded
    ListView height, never NavScreen's class-scoped selector or Textual's bare
    `height: auto` default, which would try to render all 48 rows at once
    (11-REVIEWS.md cycle 3 finding #10)."""
    policy = _fake_policy(active=True, set_schedule=lambda _h, _m: _ok_result())
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("t")
        screen = app.screen
        assert isinstance(screen, TimePickerScreen)
        list_view = screen.query_one(ListView)
        assert list_view.size.height <= 20


async def test_time_picker_set_schedule_failure_surfaces_on_status_line() -> None:
    def failing_set_schedule(_hour: int, _minute: int) -> PolicyResult:
        raise CommandError(["launchctl", "bootstrap"], 1)

    policy = _fake_policy(active=True, set_schedule=failing_set_schedule)
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("t")
        await pilot.press("enter")  # select the first slot, 00:00
        assert isinstance(app.screen, PoliciesScreen)
        assert "Policy change failed" in screen.status.text


async def test_policy_toggle_disables_active_policy() -> None:
    calls: list[str] = []
    policy = _fake_policy(active=True, remove=lambda: (calls.append("remove"), _ok_result())[1])
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        await pilot.press("space")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["remove"]
        assert app.screen.active_state["ban"] is False
        assert "disabled" in app.screen.status.text


async def test_policy_toggle_error_surfaces_and_does_not_crash() -> None:
    def boom() -> PolicyResult:
        raise OSError("permission denied")

    app = _app(policies=_policy_inputs([_fake_policy(active=False, apply=boom)]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        await pilot.press("space")
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is False  # unchanged on failure
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status.text.lower()


async def test_policy_toggle_noop_on_empty_table() -> None:
    """Space on an empty policies table is a no-op (covers _highlighted_policy
    row_count==0 and the action_toggle_policy policy-is-None guard)."""
    app = _app(policies=_policy_inputs([]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        assert isinstance(app.screen, PoliciesScreen)
        await pilot.press("space")
        assert app.screen.status.text == ""
        assert app.screen.error is None


async def test_policy_summary_includes_warning_when_set() -> None:
    """_summary appends the warning line when PolicyResult.warning is non-None
    (covers the `if result.warning:` branch)."""

    def apply_with_warning() -> PolicyResult:
        return PolicyResult(
            layers=(PolicyLayer("Shims", "2 active"),),
            reload_hint=None,
            warning="pip found on PATH ahead of shims — move the shim dir earlier.",
        )

    policy = _fake_policy(active=False, apply=apply_with_warning)
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("6")
        await pilot.press("space")
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is True
        assert "pip found on PATH" in app.screen.status.text


async def test_policy_enter_does_not_toggle() -> None:
    """enter is inert on the live Policies view — there is no staged batch to
    commit, so only space (toggle-this-row) acts."""
    app = _app(policies=_policy_inputs([_fake_policy(active=False)]), initial_view="policies")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("enter")
        assert screen.active_state["ban"] is False


async def test_doctor_uninstall_and_policies_render_a_footer() -> None:
    """Pushed views hide the catalog's top Tabs strip, so each MUST yield a
    FooterBar or the app-level nav keys (1-4, ctrl+p, q, esc) are invisible and
    the user is stranded (regression: pushed views shipped without a Footer)."""
    from installer.ui_common import FooterBar

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, DoctorScreen)
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("6")
        assert isinstance(app.screen, PoliciesScreen)
        assert len(app.screen.query(FooterBar)) == 1


async def test_q_quits_from_every_pushed_view() -> None:
    """q must quit from any view, not just the base view (regression: q was
    bound only on CatalogScreen, so other views had no working quit)."""
    for view in ("doctor", "uninstall", "policies"):
        app = _app(initial_view=view)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("q")
            assert not app.is_running  # quit fired while still on the sub-view
        assert app.return_value is None


async def test_esc_returns_to_system_from_a_pushed_view() -> None:
    """esc is the one-deep 'back': from any sub-view it pops to the system view."""
    app = _app(initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.current_view == "doctor"
        await pilot.press("escape")
        assert app.current_view == "system"
        assert app.is_running  # esc goes back, does not quit


async def test_esc_on_system_is_inert() -> None:
    """On the base system view there is nowhere to go back to; esc must not quit."""
    app = _app(initial_view="system")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("escape")
        assert app.current_view == "system"
        assert app.is_running


async def test_q_does_not_quit_while_nav_palette_open() -> None:
    """q is a priority App binding, so it DOES reach action_abort even with the
    Ctrl+P palette open — the _navigable() guard (palette is neither the base view nor
    a pushed view) is what makes it inert there, not the modal swallowing it."""
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("q")  # must be inert under the modal
        assert app.is_running
        assert isinstance(app.screen, NavScreen)


async def test_ctrl_c_hard_aborts_even_while_palette_open() -> None:
    """ctrl+c is the hard abort and must quit from anywhere, including from on
    top of the palette modal (unlike q, which the modal swallows)."""
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("ctrl+c")
        assert not app.is_running
    assert app.return_value is None


async def test_rapid_view_switching_keeps_stack_one_deep() -> None:
    """Rapid number-key presses must not corrupt the [base] / [base, <view>]
    stack invariant or wedge navigation (the 'keys stop responding' bug)."""
    from installer.catalog_tui import CatalogScreen

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4", "5", "6", "1")
        assert app.current_view == "system"
        assert isinstance(app.screen, CatalogScreen)
        # The system view is the app's base screen (get_default_screen), so it is
        # never pushed or popped — it is always the permanent bottom of the stack.
        # After navigating back to the system view, the stack is [base] (depth 1).
        assert len(app.screen_stack) == 1  # back to just the base screen
        # not wedged: a subsequent press still navigates
        await pilot.press("5")
        assert app.current_view == "uninstall"
        assert len(app.screen_stack) == 2


async def test_rapid_switch_away_from_uninstall_does_not_wedge() -> None:
    """Navigating away from Uninstall before its ToolBrowser's post-mount refresh
    callback runs must not raise. The browser schedules refresh_marks via
    call_after_refresh; awaiting push_screen mounts the screen but does not drain
    that callback, so a subsequent navigation can pop the Uninstall screen and
    remove its DataTable while the refresh is still pending. If the callback then
    dereferences the gone table it raises NoMatches into Textual's message loop
    and input wedges — the reported 'keys stop responding' bug. pilot.press can't
    expose this (it settles each key, draining the callback between presses), so
    we drive the nav actions back-to-back without settling, as the driver does."""
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        # uninstall is the ToolBrowser view; each following action leaves the
        # previous view before its deferred refresh has settled.
        for name in ("doctor", "uninstall", "policies", "uninstall", "system"):
            await app.run_action(f"show('{name}')")
        await pilot.pause()
        # Not wedged: navigation still works and no exception was stored.
        await pilot.press("5")
        assert app.current_view == "uninstall"


async def test_unsettled_key_burst_lands_on_the_last_key_pressed() -> None:
    """Keys delivered faster than a screen transition settles must not be dropped.

    The view screens used to be pushed uninstalled, so App._replace_screen
    REMOVED a popped screen's whole widget tree; re-pushing the same instance
    left screen.focused pointing at a detached widget, collapsing the binding
    chain to that lone widget — the App's priority number keys no longer matched
    and later keys in a fast burst were silently dropped (the reported "press 2
    for Doctor but land elsewhere" bug). pilot.press cannot expose this (it
    settles every key), so post the Key events directly and only yield between
    them, the way the real driver delivers a fast burst.
    """
    import asyncio

    from textual import events

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        for key in "74674174":  # ends on doctor
            event = events.Key(key, key)
            event.set_sender(app)
            app.post_message(event)
            await asyncio.sleep(0)  # yield so the burst overlaps the transitions
        await pilot.pause()
        assert app.current_view == "doctor"
        # and the keys still work afterwards
        await pilot.press("5")
        assert app.current_view == "uninstall"


async def test_uninstall_summary_reports_the_sweep_result_not_the_snapshot() -> None:
    """The row's tweak_ids describe what was OFFERED. Only the sweep's own
    return value knows what came off, so the summary must read that."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown", "omz-plugins"),
        remove=_recorder(
            captured, SweepResult(swept=("omz-plugins",), failed=("tweak:countdown",))
        ),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        status = app.screen.status.text
        assert "shell tweaks disabled (omz-plugins)" in status
        assert "could not disable tweak:countdown" in status


async def test_uninstall_summary_says_so_when_the_sweep_found_nothing() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown",), remove=_recorder(captured, SweepResult())
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert "no shell tweaks were still enabled" in app.screen.status.text


async def test_uninstall_tweak_row_names_background_jobs_when_a_daemon_id_is_offered() -> None:
    """Preview-row copy (11-REVIEWS.md cycle 2 finding #19's preview half): the
    Tool-column label and detail both name the background job once a
    daemon:-prefixed id is among what is offered."""
    inputs = _uninstall_inputs(tweak_ids=("tweak:countdown", "daemon:prune-tmpdir"))
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        cells = screen.query_one(DataTable[Any]).get_row("#tweaks")
        rendered = " ".join(str(cell) for cell in cells)
        assert "shell tweaks + background jobs" in rendered
        await pilot.pause()
        assert "background maintenance" in screen.detail_text.lower()


async def test_uninstall_tweak_row_stays_byte_identical_without_a_daemon_id() -> None:
    """No daemon: id offered (Linux, or the daemon never enabled) -- the row's
    label/detail must be unchanged from before this plan."""
    inputs = _uninstall_inputs(tweak_ids=("tweak:countdown",))
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        cells = screen.query_one(DataTable[Any]).get_row("#tweaks")
        rendered = " ".join(str(cell) for cell in cells)
        assert "shell tweaks" in rendered
        assert "background" not in rendered
        await pilot.pause()
        assert "background" not in screen.detail_text.lower()


async def test_uninstall_applied_summary_names_the_background_job_alone() -> None:
    """The sweep swept ONLY the daemon: no shell reload is relevant, so the
    hint must not be appended (11-REVIEWS.md cycle 2 finding #19)."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("daemon:prune-tmpdir",),
        remove=_recorder(captured, SweepResult(swept=("daemon:prune-tmpdir",))),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "background maintenance job" in status
        assert "open a new" not in status.lower()


async def test_uninstall_applied_summary_names_both_when_swept_together() -> None:
    """The sweep swept the daemon AND a real shell tweak together: the
    background job is named AND the shell-reload hint is still appended,
    since a real tweak's reload is still relevant."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown", "daemon:prune-tmpdir"),
        remove=_recorder(captured, SweepResult(swept=("tweak:countdown", "daemon:prune-tmpdir"))),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "background maintenance job" in status
        assert "open a new" in status.lower()


async def test_uninstall_applied_summary_stays_byte_identical_without_a_daemon_id() -> None:
    """No daemon: id in the sweep's own result -- the summary line must be
    unchanged from before this plan."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown",),
        remove=_recorder(captured, SweepResult(swept=("tweak:countdown",))),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "shell tweaks disabled (tweak:countdown) — open a new shell so functions" in status
        assert "background" not in status.lower()


async def test_uninstall_tweaks_row_follows_a_live_policies_toggle() -> None:
    """The Policies view and the Uninstall view are one process, one nav path.
    A tweak enabled in Policies must be reachable in Uninstall in the same
    session, and one disabled there must stop being offered."""
    live: list[str] = []

    def tweak_ids() -> tuple[str, ...]:
        return tuple(live)

    app = _app(uninstall=_uninstall_inputs(tweak_ids=tweak_ids))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")  # uninstall: nothing enabled yet
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "#tweaks" not in {row.value for row in screen.query_one(DataTable[Any]).rows}

        # The user enables a tweak over in Policies, then comes back.
        live.append("tweak:countdown")
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        keys = {row.value for row in app.screen.query_one(DataTable[Any]).rows}
        assert "#tweaks" in keys
        await pilot.press("a")
        assert app.screen.remove_tweaks is True

        # ...and disables it again: the lever must go, and the stale mark with it.
        live.clear()
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert "#tweaks" not in {row.value for row in app.screen.query_one(DataTable[Any]).rows}
        assert app.screen.remove_tweaks is False


async def test_uninstall_row_label_follows_the_live_tweak_ids() -> None:
    live = ["tweak:countdown", "omz-plugins"]

    def tweak_ids() -> tuple[str, ...]:
        return tuple(live)

    app = _app(uninstall=_uninstall_inputs(tweak_ids=tweak_ids), initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, UninstallScreen)
        live.remove("omz-plugins")
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        cells = app.screen.query_one(DataTable[Any]).get_row("#tweaks")
        rendered = " ".join(str(cell) for cell in cells)
        assert "tweak:countdown" in rendered
        assert "omz-plugins" not in rendered


async def test_uninstall_first_entry_picks_up_state_changed_before_it_was_ever_shown() -> None:
    """The screen is installed on app mount but only mounted on first push, so
    the first entry refreshes a screen whose widgets do not exist yet."""
    live: list[str] = []

    def tweak_ids() -> tuple[str, ...]:
        return tuple(live)

    app = _app(uninstall=_uninstall_inputs(tweak_ids=tweak_ids))
    async with app.run_test(size=(100, 30)) as pilot:
        live.append("tweak:countdown")  # enabled in Policies before Uninstall is opened
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert "#tweaks" in {row.value for row in app.screen.query_one(DataTable[Any]).rows}


async def test_uninstall_does_not_refresh_after_it_has_applied() -> None:
    """Once a removal has run, the standing message is that run's result — a
    re-entry must not rebuild the rows out from under it."""
    captured: list[UninstallDecision] = []
    live = ["tweak:countdown"]

    def tweak_ids() -> tuple[str, ...]:
        return tuple(live)

    inputs = _uninstall_inputs(
        tweak_ids=tweak_ids,
        remove=_recorder(captured, SweepResult(swept=("tweak:countdown",))),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        applied_status = app.screen.status.text
        live.clear()  # the sweep really did disable it
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.status.text == applied_status
        assert "#tweaks" in {row.value for row in app.screen.query_one(DataTable[Any]).rows}


async def test_uninstall_ban_row_appears_once_the_ban_is_enabled_elsewhere() -> None:
    """Enabling the ban in Policies must not leave its removal lever unreachable.

    The flagship policy starts OFF on a fresh machine, so a build-time snapshot
    shows the Uninstall view a machine with no ban on it for the rest of the
    session — however many times the user enables one.
    """
    live: list[str] = []
    app = _app(uninstall=_uninstall_inputs(ban_names=lambda: list(live)))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert "#ban" not in {row.value for row in app.screen.query_one(DataTable[Any]).rows}
        live.extend(["pip", "npm"])  # PoliciesScreen.action_toggle_policy → ban_policy.apply
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        cells = app.screen.query_one(DataTable[Any]).get_row("#ban")
        assert "pip, npm" in " ".join(str(cell) for cell in cells)


async def test_uninstall_path_block_row_appears_once_doctor_has_written_it() -> None:
    """DoctorScreen.action_apply writes the very block has_path_block detects."""
    written = [False]
    app = _app(uninstall=_uninstall_inputs(has_path_block=lambda: written[0]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert "#path-block" not in {row.value for row in app.screen.query_one(DataTable[Any]).rows}
        written[0] = True  # configure_path → write_myshellrc
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert "#path-block" in {row.value for row in app.screen.query_one(DataTable[Any]).rows}


async def test_uninstall_ban_row_disappears_once_the_ban_is_removed_elsewhere() -> None:
    """The stale-True direction: a lever that removes nothing while
    _applied_summary claims 'pip/npm ban removed' anyway."""
    live = ["pip", "npm"]
    app = _app(uninstall=_uninstall_inputs(ban_names=lambda: list(live)), initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, UninstallScreen)
        live.clear()
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert "#ban" not in {row.value for row in app.screen.query_one(DataTable[Any]).rows}


async def test_doctor_ban_report_follows_a_policies_toggle() -> None:
    """Installed screens are suspended, not unmounted, so DoctorScreen.on_mount
    fires once for the life of the app. Without enter_view the report shows the
    ban state from before the user toggled it one nav step away."""
    status = {"pip": False, "npm": False}
    app = _app(guard_status=lambda: status)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, DoctorScreen)
        assert all("ban" not in item.title.lower() for item in app.screen.guidance)
        status["pip"] = True  # PoliciesScreen.action_toggle_policy → ban_policy.apply
        await pilot.press("escape")
        await pilot.press("4")
        assert isinstance(app.screen, DoctorScreen)
        assert any("guards active" in item.title.lower() for item in app.screen.guidance)


async def test_doctor_screen_shows_npx_redirect_label() -> None:
    app = _app(guard_status={"npx": True}, initial_view="doctor")
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, DoctorScreen)
        assert any("npx: redirected to pnpm dlx" in item.meaning for item in app.screen.guidance)


async def test_doctor_screen_shows_missing_pnpm_globals_and_preview() -> None:
    preview = "/real/bin/pnpm add -g @mermaid-js/mermaid-cli"
    app = _app(
        node_globals=lambda: _mmdc_report(),
        globals_preview=lambda _report: preview,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert any("mmdc" in item.meaning for item in app.screen.guidance)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "mmdc" in body
        assert preview in body
        assert "pnpm-managed globals" in body


async def test_doctor_screen_renders_unresolvable_pnpm_preview() -> None:
    degraded = "pnpm not found on PATH - cannot preview the reinstall."
    app = _app(
        node_globals=lambda: _mmdc_report(),
        globals_preview=lambda _report: degraded,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "pnpm-managed globals" in body
        assert degraded in body
        assert not any(line.strip().startswith("pnpm add") for line in body.splitlines())
        assert body.strip() != ""


async def test_doctor_r_reinstalls_once_and_reports_success() -> None:
    calls: list[str] = []

    def reinstall(_packages: Sequence[str]) -> tuple[str, ...]:
        calls.append("r")
        return ("@mermaid-js/mermaid-cli",)

    app = _app(
        node_globals=lambda: _mmdc_report(missing=()),
        reinstall_globals=reinstall,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        await pilot.press("r")
        await _settle(app, pilot)
        assert calls == ["r"]
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.globals_done is True
        assert screen.globals_error is None
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "pnpm globals reinstalled" in body
        await pilot.press("r")
        await _settle(app, pilot)
        assert calls == ["r"]


async def test_doctor_r_runs_the_reinstall_off_the_event_loop() -> None:
    # The only subprocess a view starts. Run synchronously it froze every frame
    # for the length of a `pnpm add -g` (minutes for a Puppeteer-carrying
    # package), with no spinner and no way to cancel.
    started = threading.Event()
    release = threading.Event()

    def slow(_packages: Sequence[str]) -> tuple[str, ...]:
        started.set()
        assert release.wait(timeout=5)
        return ("@mermaid-js/mermaid-cli",)

    app = _app(
        node_globals=lambda: _mmdc_report(missing=()),
        reinstall_globals=slow,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        await pilot.press("r")
        assert started.wait(timeout=5)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.globals_running is True
        # The loop is still painting while the child runs.
        assert "Reinstalling" in str(screen.query_one("#doctor-body", Static).render())
        # A second press must not stack a concurrent install.
        await pilot.press("r")
        release.set()
        await _settle(app, pilot)
        assert screen.globals_running is False
        assert screen.globals_done is True


async def test_doctor_audit_runs_off_the_event_loop() -> None:
    # `pnpm list -g --json` is a subprocess like the reinstall is. Run
    # synchronously it blocked every Doctor render for its duration, with no
    # timeout and no interruptible path: Textual holds the terminal in raw
    # mode, so a Ctrl+C arrives as a byte on a queue the blocked loop is not
    # draining, and a pnpm stalled on store-lock contention wedged the TUI.
    started = threading.Event()
    release = threading.Event()

    def slow() -> NodeGlobalsReport:
        started.set()
        assert release.wait(timeout=5)
        return _mmdc_report(missing=())

    app = _app(node_globals=slow, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        assert started.wait(timeout=5)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.globals_auditing is True
        # The loop is still painting while the child runs...
        assert "Checking pnpm's global set" in str(
            screen.query_one("#doctor-body", Static).render()
        )
        # ...and still handling keys, rather than swallowing them until pnpm
        # answers.
        await pilot.press("r")
        assert screen.globals_note is not None
        assert "Still checking" in screen.globals_note
        release.set()
        await _settle(app, pilot)
        assert screen.globals_auditing is False
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "Checking pnpm's global set" not in body
        assert "package(s) in pnpm's global set" in body


async def test_doctor_audit_that_cannot_run_renders_as_unknown_not_as_zero() -> None:
    # run_live turns an OSError from the audit into a message; the screen then
    # knows exactly as much as it does when pnpm itself could not be asked.
    def boom() -> NodeGlobalsReport:
        raise OSError("pnpm store is locked")

    app = _app(node_globals=boom, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "could not be read" in body
        assert "0 package(s)" not in body
        # The screen is still usable, not a crashed worker.
        await pilot.press("r")
        assert app.is_running


async def test_doctor_audit_survives_a_raising_preview_closure() -> None:
    # WR-02 (cycle-3 review): self._globals_preview also resolves pnpm and
    # can raise OSError for the same reason the audit itself can (real_pnpm
    # -> Path.home()), but only the audit call was inside run_live's guard.
    # Verified live pre-fix: an OSError here was NOT caught by run_live at
    # all (only self._node_globals's call was wrapped) and crashed the
    # worker with textual.worker.WorkerFailed.
    def raising_preview(_report: NodeGlobalsReport) -> str:
        raise OSError("pnpm resolution blew up")

    app = _app(
        node_globals=lambda: _mmdc_report(missing=()),
        globals_preview=raising_preview,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert app.is_running
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "could not be read" in body


async def test_doctor_r_retries_the_audit_when_it_could_not_be_read() -> None:
    # WR-03 (cycle-3 review): a known=False report left `r` refusing forever
    # with no way back to a readable state short of leaving the screen.
    attempts = 0

    def flaky() -> NodeGlobalsReport:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("pnpm store is locked")
        return _mmdc_report(missing=())

    app = _app(node_globals=flaky, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert attempts == 1
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "could not be read" in body

        await pilot.press("r")
        await _settle(app, pilot)
        assert attempts == 2
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "could not be read" not in body
        assert "mmdc" not in body


async def test_doctor_reinstall_refuses_a_stale_report_while_reauditing() -> None:
    # A cycle-3 review finding: only the FIRST-ever audit (report is None)
    # was refused. A SUBSEQUENT audit -- triggered here by re-entering the
    # screen, the same trigger the post-reinstall re-audit uses -- left a
    # previously-landed report on screen while a fresh one was in flight, so
    # `r` pressed in that window proceeded against the report from BEFORE
    # whatever triggered the re-audit.
    call_count = 0
    second_started = threading.Event()
    release_second = threading.Event()

    def flaky() -> NodeGlobalsReport:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mmdc_report(missing=("mmdc",))
        second_started.set()
        assert release_second.wait(timeout=5)
        return _mmdc_report(missing=())

    app = _app(node_globals=flaky, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, DoctorScreen)
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "mmdc" in body

        # Re-entering starts a fresh audit (the same call `enter_view` makes
        # on every entry) while the stale "mmdc missing" report is still
        # what's rendered.
        await pilot.press("escape")
        await pilot.press("4")
        await pilot.pause()
        assert second_started.wait(timeout=5)
        assert screen.globals_auditing is True

        # This must NOT proceed using the stale report.
        await pilot.press("r")
        assert screen.globals_running is False
        assert screen.globals_note is not None
        assert "Still checking" in screen.globals_note

        release_second.set()
        await _settle(app, pilot)
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "mmdc" not in body


async def test_doctor_stale_audit_delivery_is_discarded() -> None:
    # exclusive=True cancels the OLDER Worker object, but the thread it
    # wraps is already inside subprocess.run and keeps running to
    # completion -- its post_message still arrives. Without the generation
    # check, whichever of two in-flight audits happens to land LAST would
    # win, even if it started first and is now answering a stale question.
    first_started = threading.Event()
    release_first = threading.Event()

    def slow_then_fast() -> NodeGlobalsReport:
        if not first_started.is_set():
            first_started.set()
            assert release_first.wait(timeout=5)
            return _mmdc_report(missing=("mmdc",))
        return _mmdc_report(missing=())

    app = _app(node_globals=slow_then_fast, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        assert first_started.wait(timeout=5)
        screen = app.screen
        assert isinstance(screen, DoctorScreen)
        assert screen.globals_auditing is True

        # A second, newer audit starts (re-entry) while the first is still
        # blocked.
        await pilot.press("escape")
        await pilot.press("4")
        await _settle(app, pilot)
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "mmdc" not in body

        # The stale first audit now delivers its (superseded) answer.
        release_first.set()
        await pilot.pause()
        await pilot.pause()
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "mmdc" not in body


async def test_doctor_never_asks_pnpm_from_the_main_thread() -> None:
    # Entering Doctor, re-entering it, and finishing a reinstall each re-ask
    # pnpm. Every one of those calls must land on a worker thread.
    threads: list[str] = []

    def read() -> NodeGlobalsReport:
        threads.append(threading.current_thread().name)
        return _mmdc_report(missing=())

    app = _app(
        node_globals=read,
        reinstall_globals=lambda _packages: ("pkg",),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await _settle(app, pilot)
        entered = len(threads)
        await pilot.press("escape")
        await pilot.press("4")
        await _settle(app, pilot)
        reentered = len(threads)
        await pilot.press("r")
        await _settle(app, pilot)
    assert entered >= 1  # the audit ran on entry
    assert reentered > entered  # and again on re-entry
    assert len(threads) > reentered  # and again after the reinstall
    assert threading.current_thread().name == "MainThread"
    assert "MainThread" not in threads


async def test_doctor_r_clears_the_stale_missing_globals_warning() -> None:
    # The globals audit is a live probe whose answer the action just changed,
    # so the screen must not render "went missing" above "reinstalled".
    missing = ["mmdc"]

    def read() -> NodeGlobalsReport:
        return _mmdc_report(missing=tuple(missing))

    def reinstall(_packages: Sequence[str]) -> tuple[str, ...]:
        missing.clear()
        return ("@mermaid-js/mermaid-cli",)

    app = _app(node_globals=read, reinstall_globals=reinstall, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert any("pnpm-managed global set" in item.title for item in screen.guidance)
        await pilot.press("r")
        await _settle(app, pilot)
        assert all("pnpm-managed global set" not in item.title for item in screen.guidance)
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "pnpm globals reinstalled" in body
        assert "went missing" not in body


async def test_doctor_r_commanderror_leaves_screen_usable() -> None:
    def boom(_packages: Sequence[str]) -> tuple[str, ...]:
        raise CommandError(["pnpm", "add", "-g", "x"], 1)

    app = _app(
        node_globals=lambda: _mmdc_report(),
        reinstall_globals=boom,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        await pilot.press("r")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.globals_done is False
        assert screen.globals_error
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "Reinstall failed" in body
        assert screen.globals_error in body
        await pilot.press("escape")
        assert app.is_running


async def test_doctor_r_empty_set_says_so_instead_of_swallowing_the_key() -> None:
    # The footer advertises `r`, so a keypress that changes nothing on screen
    # reads as a broken binding.
    calls: list[str] = []
    app = _app(
        reinstall_globals=lambda _packages: calls.append("r") or (),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        before = str(screen.query_one("#doctor-body", Static).render())
        assert screen.globals_note is None
        await pilot.press("r")
        await _settle(app, pilot)
        assert calls == []
        body = str(screen.query_one("#doctor-body", Static).render())
        assert body != before
        assert "Nothing to reinstall" in body
        assert "nothing pnpm-managed to reinstall" in body
        # A no-op is not a failure.
        assert screen.globals_error is None
        assert "Reinstall failed" not in body


async def test_doctor_reports_an_unreadable_global_set_as_unknown_not_as_zero() -> None:
    # `pnpm list -g --json` went unanswered: every field is empty because
    # nothing was learned. Rendering "0 package(s)" states that unknown as a
    # fact, on the machine whose pnpm has just replaced itself.
    calls: list[str] = []
    unknown = NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
    app = _app(
        node_globals=lambda: unknown,
        globals_preview=lambda _report: reinstall_preview((), known=False),
        reinstall_globals=lambda _packages: calls.append("r") or (),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "0 package(s)" not in body
        assert "could not be read" in body
        assert "nothing pnpm-managed to reinstall" not in body
        await pilot.press("r")
        await _settle(app, pilot)
        assert calls == []
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "pnpm manages no globals here" not in body
        assert "could not be read" in body
        assert screen.globals_error is None


async def test_doctor_still_reports_a_genuinely_empty_global_set_as_zero() -> None:
    empty = NodeGlobalsReport(entries=(), missing=(), managed=())
    app = _app(
        node_globals=lambda: empty,
        globals_preview=lambda _report: reinstall_preview(()),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        await pilot.press("r")
        await _settle(app, pilot)
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "0 package(s) in pnpm's global set" in body
        assert "pnpm manages no globals here" in body
        assert "could not be read" not in body


async def test_doctor_enter_then_r_both_run() -> None:
    fix_calls: list[str] = []
    reinstall_calls: list[str] = []
    app = _app(
        fix=lambda: fix_calls.append("fix"),
        node_globals=lambda: _mmdc_report(missing=()),
        reinstall_globals=lambda _packages: reinstall_calls.append("r") or ("pkg",),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        await pilot.press("enter")
        await pilot.press("r")
        await _settle(app, pilot)
        assert fix_calls == ["fix"]
        assert reinstall_calls == ["r"]
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True
        assert screen.globals_done is True
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "PATH wired" in body
        assert "pnpm globals reinstalled" in body


async def test_doctor_r_then_enter_both_run() -> None:
    fix_calls: list[str] = []
    reinstall_calls: list[str] = []
    app = _app(
        fix=lambda: fix_calls.append("fix"),
        node_globals=lambda: _mmdc_report(missing=()),
        reinstall_globals=lambda _packages: reinstall_calls.append("r") or ("pkg",),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        await pilot.press("r")
        await _settle(app, pilot)
        await pilot.press("enter")
        assert reinstall_calls == ["r"]
        assert fix_calls == ["fix"]
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True
        assert screen.globals_done is True
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "PATH wired" in body
        assert "pnpm globals reinstalled" in body


async def test_doctor_rereads_node_globals_on_enter_view() -> None:
    missing: list[str] = []

    def read() -> NodeGlobalsReport:
        return NodeGlobalsReport(
            entries=(NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),),
            missing=tuple(missing),
            managed=("@mermaid-js/mermaid-cli",),
        )

    app = _app(node_globals=read)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert all("pnpm-managed global set" not in item.title for item in app.screen.guidance)
        missing.append("mmdc")
        await pilot.press("escape")
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert any("pnpm-managed global set" in item.title for item in app.screen.guidance)


async def test_doctor_tui_guidance_rewrites_make_setup_prefix() -> None:
    app = _app(node_globals=lambda: _mmdc_report(), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert any(item.next_step.startswith("Run `make setup`") for item in app.screen.guidance)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "Press r" in body
        assert "Run `make setup`" not in body


def test_unified_app_constructs_without_node_globals_closures() -> None:
    tools = [_tool("rg")]
    UnifiedApp(
        tools,
        {"rg": False},
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({"pip": False}, None),
        fix_preview="preview",
        fix=lambda: None,
        uninstall=_uninstall_inputs(),
        policies=_policy_inputs(),
    )


# -- on-by-default (ensure_daemon_default + the worker/message/guard wiring) --


def test_ensure_daemon_default_applies_once_when_undecided(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    calls: list[str] = []
    policy = _fake_policy(active=False, apply=lambda: (calls.append("apply"), _ok_result())[1])
    assert ensure_daemon_default(policy, state_path=state_path) is True
    assert calls == ["apply"]


def test_ensure_daemon_default_is_a_noop_once_decided(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    daemon.record_decided(state_path)
    calls: list[str] = []
    policy = _fake_policy(active=False, apply=lambda: (calls.append("apply"), _ok_result())[1])
    assert ensure_daemon_default(policy, state_path=state_path) is False
    assert calls == []


def test_ensure_daemon_default_returns_false_on_a_failed_apply_without_recording(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".myshellrc"

    def boom() -> PolicyResult:
        raise CommandError(["launchctl", "bootstrap"], 5)

    policy = _fake_policy(active=False, apply=boom)
    assert ensure_daemon_default(policy, state_path=state_path) is False
    assert daemon.decided(state_path) is False


class _FakeDaemonRun:
    """Records every argv; never touches real launchctl. Can be told to fail
    the bootstrap call, to exercise a first-run auto-apply failure."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._fail = fail

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        if self._fail and cmd[:2] == ["launchctl", "bootstrap"]:
            raise CommandError(cmd, 5)


def _daemon_policy(tmp_path: Path, *, run: Callable[[list[str]], None] | None = None) -> Policy:
    """A real daemon_policy against tmp_path-scoped artifacts, with an injected
    fake run so no real launchctl call is ever made."""
    script_path = tmp_path / "scripts" / "prune-user-tmpdir.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    return daemon_policy(
        plist_path=tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist",
        log_path=tmp_path / "Logs" / "prune-daemon.log",
        wrapper_bin_dir=tmp_path / ".local" / "bin",
        script_path=script_path,
        state_path=tmp_path / ".myshellrc",
        installed_tools={"fd": True, "rg": True},
        path_value="/usr/bin:/bin",
        tmpdir_value=str(tmp_path / "tmp"),
        home_value=str(tmp_path),
        uv_path=tmp_path / "uv",
        uid=501,
        run=run if run is not None else _FakeDaemonRun(),
    )


def _daemon_app(
    tmp_path: Path,
    *,
    policy: Policy,
    daemon_default: Callable[[], bool] | None,
    remove: Callable[[UninstallDecision], SweepResult] = lambda _d: SweepResult(),
    tweak_ids: tuple[str, ...] | Callable[[], tuple[str, ...]] = (),
    rows: list[ToolRow] | None = None,
) -> UnifiedApp:
    return UnifiedApp(
        [_tool("rg")],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=_uninstall_inputs(rows=rows, remove=remove, tweak_ids=tweak_ids),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
        daemon_default=daemon_default,
        daemon_default_policy_id=policy.id,
    )


async def _settle_daemon(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    """Wait for the on-by-default worker's completion message to be handled."""
    for _ in range(400):
        if not app.daemon_default_in_flight:
            break
        await pilot.pause()
    await pilot.pause()


async def test_on_by_default_auto_applies_on_a_fresh_undecided_machine(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    policy = _daemon_policy(tmp_path)
    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=lambda: ensure_daemon_default(policy, state_path=state_path),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_daemon(app, pilot)
        assert plist_path.exists()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is True
        assert app.daemon_default_in_flight is False


async def test_on_by_default_does_not_reenable_an_explicitly_disabled_daemon(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".myshellrc"
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    daemon.record_decided(state_path)
    policy = _daemon_policy(tmp_path)
    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=lambda: ensure_daemon_default(policy, state_path=state_path),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_daemon(app, pilot)
        assert not plist_path.exists()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is False


async def test_on_by_default_never_records_a_decision_on_a_failed_apply(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    policy = _daemon_policy(tmp_path, run=_FakeDaemonRun(fail=True))
    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=lambda: ensure_daemon_default(policy, state_path=state_path),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_daemon(app, pilot)
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is False
        assert daemon.decided(state_path) is False
        assert app.daemon_default_in_flight is False


async def test_manual_toggle_of_the_daemon_is_refused_while_the_worker_is_in_flight(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / ".myshellrc"
    fake_run = _FakeDaemonRun()
    policy = _daemon_policy(tmp_path, run=fake_run)
    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=lambda: ensure_daemon_default(policy, state_path=state_path),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.daemon_default_in_flight is True
        await pilot.press("space")
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert "wait a moment" in screen.status.text.lower()
        await _settle_daemon(app, pilot)
        assert screen.active_state["daemon:prune-tmpdir"] is True
        bootstrap_calls = [c for c in fake_run.calls if c[:2] == ["launchctl", "bootstrap"]]
        assert len(bootstrap_calls) == 1


async def test_reschedule_is_refused_while_the_worker_is_in_flight(tmp_path: Path) -> None:
    """Post-implementation review finding CR-02: action_toggle_policy and
    UninstallScreen._apply_removal both guard against the on-by-default
    worker racing a manual mutation of the SAME policy, but the reschedule
    action (t) had no such guard. The scenario this closes: a plist already
    exists on disk (so the daemon reads active=True at PoliciesScreen
    construction, enabling the t binding) but daemon.decided() is still
    False -- e.g. an upgrade that registered the LaunchAgent before the
    "decided" marker existed -- so the worker calls policy.apply() for REAL
    on a background thread at the same moment a user picks a new time on the
    main thread. The guard must fire at the actual mutation point (inside the
    picker's dismiss callback), not only when the picker screen is opened,
    since the picker can stay open for as long as the user takes to choose."""
    state_path = tmp_path / ".myshellrc"
    seed = _daemon_policy(tmp_path)
    seed.apply()
    seed_bytes = (tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist").read_bytes()
    state_path.unlink()  # simulate an upgrade: plist registered, no decided marker yet
    fake_run = _FakeDaemonRun()
    policy = _daemon_policy(tmp_path, run=fake_run)
    assert policy.active is True

    release = threading.Event()

    def slow_daemon_default() -> bool:
        release.wait(timeout=5)
        return ensure_daemon_default(policy, state_path=state_path)

    app = _daemon_app(tmp_path, policy=policy, daemon_default=slow_daemon_default)
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.daemon_default_in_flight is True
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is True
        await pilot.press("t")
        assert isinstance(app.screen, TimePickerScreen)
        await pilot.press("down", "down", "down", "enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert "wait a moment" in screen.status.text.lower()
        plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
        assert plist_path.read_bytes() == seed_bytes  # untouched by the refused reschedule
        release.set()
        await _settle_daemon(app, pilot)


async def test_on_by_default_leaves_an_already_active_daemon_active(tmp_path: Path) -> None:
    """The decided-AND-active case: refresh_daemon_state must resolve via the
    policy's own is_active(), never the worker's applied=False boolean
    directly, or an ordinary already-on second run would flip to OFF."""
    state_path = tmp_path / ".myshellrc"
    seed = _daemon_policy(tmp_path)
    seed.apply()
    assert daemon.decided(state_path) is True
    # A second daemon_policy instance, freshly constructed against the SAME
    # on-disk plist: active=True is baked in at construction time.
    policy = _daemon_policy(tmp_path)
    assert policy.active is True
    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=lambda: ensure_daemon_default(policy, state_path=state_path),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is True
        await _settle_daemon(app, pilot)
        assert screen.active_state["daemon:prune-tmpdir"] is True


async def test_daemon_default_in_flight_clears_even_on_an_unexpected_exception(
    tmp_path: Path,
) -> None:
    def boom() -> bool:
        raise RuntimeError("boom, outside ensure_daemon_default's own except tuple")

    policy = _daemon_policy(tmp_path)
    app = _daemon_app(tmp_path, policy=policy, daemon_default=boom)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_daemon(app, pilot)
        assert app.daemon_default_in_flight is False


async def test_uninstall_removal_is_refused_while_the_daemon_worker_is_in_flight(
    tmp_path: Path,
) -> None:
    """The race guard blocks on daemon_default_in_flight alone -- never on
    whether a daemon: id happens to already be visible in _tweak_ids, which it
    is not yet during first-run auto-apply (11-REVIEWS.md cycle 3 finding
    #12)."""
    policy = _daemon_policy(tmp_path)
    captured: list[UninstallDecision] = []
    # A release-gated callable, not the real ensure_daemon_default: the guard
    # must hold across this whole multi-keypress sequence, and a real
    # (near-instant) fake-run apply could otherwise settle before the last
    # keypress lands, making the race window this test targets flaky.
    release = threading.Event()

    def slow_daemon_default() -> bool:
        release.wait(timeout=5)
        return False

    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=slow_daemon_default,
        remove=_recorder(captured, SweepResult()),
        tweak_ids=("tweak:countdown",),  # an unrelated, real tweak -- no daemon id present yet
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.daemon_default_in_flight is True
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        # pyright: ignore[reportPrivateUsage] -- _tweak_ids is internal UninstallScreen
        # state with no public equivalent; this test proves the pre-worker snapshot
        # genuinely lacks a daemon: id (11-REVIEWS.md cycle 3 finding #12).
        assert not any(
            tid.startswith("daemon:")
            for tid in screen._tweak_ids  # pyright: ignore[reportPrivateUsage]
        )
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        assert captured == []
        assert screen.applied is False
        assert "wait a moment" in screen.status.text.lower()
        release.set()
        await _settle_daemon(app, pilot)


async def test_uninstall_removal_is_refused_while_in_flight_even_with_no_tweaks_row(
    tmp_path: Path,
) -> None:
    """Post-implementation review finding: on a machine with NO other active
    tweaks, the daemon's inactive-at-construction Policy means _tweak_ids is
    empty, so _build_entries never offers a tweaks row at all -- remove_tweaks
    can then never become True through this screen, so the guard MUST fire
    directly on daemon_default_in_flight alone, never gated behind
    self.remove_tweaks (which the pre-fix code required, making the guard a
    no-op in exactly this scenario)."""
    policy = _daemon_policy(tmp_path)
    captured: list[UninstallDecision] = []
    release = threading.Event()

    def slow_daemon_default() -> bool:
        release.wait(timeout=5)
        return False

    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=slow_daemon_default,
        remove=_recorder(captured, SweepResult()),
        tweak_ids=(),  # no other tweaks: the daemon row never appears at all
        rows=[_removable_row(_tool("rg"), [tmp_path / "rg-artifact"])],
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.daemon_default_in_flight is True
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        # pyright: ignore[reportPrivateUsage] -- confirms the tweaks row is
        # genuinely absent, not merely lacking a daemon: id.
        assert screen._tweak_ids == ()  # pyright: ignore[reportPrivateUsage]
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        assert captured == []
        assert screen.applied is False
        assert "wait a moment" in screen.status.text.lower()
        release.set()
        await _settle_daemon(app, pilot)


async def test_on_by_default_treats_an_existing_installation_as_fresh(tmp_path: Path) -> None:
    """A pre-existing installation (other managed blocks present) with no
    daemon 'decided' marker yet is treated identically to a genuinely fresh
    HOME -- CONTEXT.md's own D-01 decision, documented and locked in
    (11-REVIEWS.md cycle 3 finding #16)."""
    state_path = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("plugins=(git)\nsource $ZSH/oh-my-zsh.sh\n")
    omz_plugins_policy(zshrc_path=zshrc, state_path=state_path, present=True).apply()
    assert daemon.decided(state_path) is False  # a pre-existing install, no daemon marker yet
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    policy = _daemon_policy(tmp_path)
    app = _daemon_app(
        tmp_path,
        policy=policy,
        daemon_default=lambda: ensure_daemon_default(policy, state_path=state_path),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_daemon(app, pilot)
        assert plist_path.exists()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is True


def _codegraph() -> Tool:
    return Tool(
        id="codegraph",
        name="codegraph",
        category="ai",
        cmd="codegraph",
        methods=(Method(kind="github_release", params={"repo": "colbymchenry/codegraph"}),),
        priority="P1",
        audience="ai",
        tier="system",
        desc="code intelligence",
    )


def _gh_tool(tool_id: str, *, tier: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search" if tier != "ai" else "ai",
        cmd=tool_id,
        methods=(Method(kind="github_release", params={"repo": f"owner/{tool_id}"}),),
        priority="P1",
        audience="both",
        tier=tier,
        desc=tool_id,
    )


def _version_app(
    tools: list[Tool],
    installed: Mapping[str, bool],
    service: VersionRefreshService,
) -> UnifiedApp:
    return UnifiedApp(
        tools,
        installed,
        {"search": "find things", "ai": "agents"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=_uninstall_inputs(),
        policies=_policy_inputs(),
        version_refresh=service,
    )


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


def _macos_service(
    tmp_path: Path,
    *,
    resolve_tag: Callable[[str], str],
    probe_output: Callable[[list[str]], str | None] = lambda argv: "1.2.0",
) -> VersionRefreshService:
    managed = tmp_path / "bin"
    return VersionRefreshService(
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        cache_path=tmp_path / "versions.json",
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        managed_bin_dir=managed,
        which=lambda cmd: str(managed / cmd),
        artifacts_for=lambda tool: [managed / tool.cmd],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        query=lambda *_a, **_k: "",
    )


async def _settle_versions(
    app: UnifiedApp,
    pilot: Pilot[list[str] | None],
    screen: CatalogScreen | None = None,
) -> None:
    """Wait for a catalog version-refresh worker to post its completion message."""
    target = app.catalog if screen is None else screen
    for _ in range(400):
        if not target.version_refreshing:
            break
        await pilot.pause()
    await pilot.pause()


async def test_codegraph_ver_cell_contains_installed_and_latest_after_refresh(
    tmp_path: Path,
) -> None:
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.6.0")
    app = _version_app([_codegraph()], {"codegraph": True}, service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _settle_versions(app, pilot)
        cell = app.catalog.query_one(DataTable[Any]).get_cell("codegraph", "ver")
        assert "1.2.0" in cell.plain
        assert "v1.6.0" in cell.plain


async def test_version_refresh_runs_off_the_event_loop(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_resolve(repo: str) -> str:
        del repo
        started.set()
        assert release.wait(timeout=5)
        return "v1.6.0"

    service = _macos_service(tmp_path, resolve_tag=slow_resolve)
    app = _version_app([_codegraph()], {"codegraph": True}, service)
    async with app.run_test(size=(120, 30)) as pilot:
        assert started.wait(timeout=5)
        screen = app.catalog
        assert screen.version_refreshing is True
        table = screen.query_one(DataTable[Any])
        assert table.row_count >= 1
        assert "codegraph" in {str(key.value) for key in table.rows}
        assert screen.selected == set()
        await pilot.press("space")
        assert screen.selected == {"codegraph"}
        release.set()
        await _settle_versions(app, pilot)
        cell = table.get_cell("codegraph", "ver")
        assert "1.2.0" in cell.plain
        assert "v1.6.0" in cell.plain
        assert screen.version_refreshing is False


async def test_version_shows_probed_install_when_latest_fetch_fails(tmp_path: Path) -> None:
    """A failed 'latest' fetch must not discard an installed version we DID
    manage to probe -- that's real information the user still wants to see."""

    def boom(repo: str) -> str:
        del repo
        raise VersionError("github unavailable")

    service = _macos_service(tmp_path, resolve_tag=boom)
    app = _version_app([_codegraph()], {"codegraph": True}, service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _settle_versions(app, pilot)
        assert app.is_running
        cell = app.catalog.query_one(DataTable[Any]).get_cell("codegraph", "ver")
        assert cell.plain == "1.2.0"
        await pilot.press("space")
        assert app.is_running
        assert app.catalog.selected == {"codegraph"}


async def test_version_worker_crash_clears_refreshing_and_renders_a_cell(
    tmp_path: Path,
) -> None:
    def boom(repo: str) -> str:
        del repo
        raise RuntimeError("unexpected domain failure")

    service = _macos_service(tmp_path, resolve_tag=boom)
    app = _version_app([_codegraph()], {"codegraph": True}, service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _settle_versions(app, pilot)
        assert app.is_running
        assert app.catalog.version_refreshing is False
        cell = app.catalog.query_one(DataTable[Any]).get_cell("codegraph", "ver")
        assert cell.plain == "unknown"
        assert cell.plain != ""


async def test_version_navigation_discards_a_superseded_generation(tmp_path: Path) -> None:
    lock = threading.Lock()
    user_calls = 0
    first_started = threading.Event()
    second_started = threading.Event()
    first_release = threading.Event()
    second_release = threading.Event()
    others_release = threading.Event()

    def resolve_tag(repo: str) -> str:
        nonlocal user_calls
        if repo.endswith("user-tool"):
            with lock:
                user_calls += 1
                n = user_calls
            if n == 1:
                first_started.set()
                assert first_release.wait(timeout=5)
                return "v1.0.0"
            second_started.set()
            assert second_release.wait(timeout=5)
            return "v2.0.0"
        assert others_release.wait(timeout=5)
        return "v9.0.0"

    tools = [
        _gh_tool("sys-tool", tier="system"),
        _gh_tool("user-tool", tier="user"),
        _gh_tool("ai-tool", tier="ai"),
    ]
    installed = {tool.id: True for tool in tools}
    service = _macos_service(tmp_path, resolve_tag=resolve_tag)
    app = _version_app(tools, installed, service)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "user"
        assert first_started.wait(timeout=5)
        user = app.catalog_for("user")
        superseded = user._version_refresh_generation  # pyright: ignore[reportPrivateUsage]
        await pilot.press("3")
        assert app.current_view == "ai"
        await pilot.press("2")
        assert app.current_view == "user"
        assert second_started.wait(timeout=5)
        current = user._version_refresh_generation  # pyright: ignore[reportPrivateUsage]
        assert current == superseded + 1
        second_release.set()
        await _settle_versions(app, pilot, user)
        cell = user.query_one(DataTable[Any]).get_cell("user-tool", "ver")
        assert "v2.0.0" in cell.plain
        assert "v1.0.0" not in cell.plain
        first_release.set()
        await _settle_versions(app, pilot, user)
        cell = user.query_one(DataTable[Any]).get_cell("user-tool", "ver")
        assert "v2.0.0" in cell.plain
        assert "v1.0.0" not in cell.plain
        assert user._version_refresh_generation == current  # pyright: ignore[reportPrivateUsage]
        others_release.set()
        await _settle_versions(app, pilot)
        await _settle_versions(app, pilot, app.catalog_for("ai"))


def _owned(
    tool: Tool,
    owner: Owner,
    *,
    confidence: str = "direct",
    package: str | None = None,
    unknown_reason: str | None = None,
) -> ManagerOwnership:
    return ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=tool.methods[0] if tool.methods else None,
        package=package,
        current_version=None,
        confidence=confidence,  # type: ignore[arg-type]
        shadowed=False,
        candidates=(
            OwnershipCandidate(
                owner=owner,
                method=tool.methods[0] if tool.methods else None,
                package=package,
                current_version=None,
                evidence="test",
            ),
        ),
        active_candidate=None if owner == "unknown" else owner,
        active_path=None,
        unknown_reason=unknown_reason,
    )


def _update_app(
    tools: list[Tool],
    installed: Mapping[str, bool],
    *,
    service: VersionRefreshService,
    updates: UpdateService,
) -> UnifiedApp:
    return UnifiedApp(
        tools,
        installed,
        {"search": "find things", "ai": "agents", "pkg-mgr": "pkg"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=_uninstall_inputs(),
        policies=_policy_inputs(),
        version_refresh=service,
        updates=updates,
    )


def _freeze_status(
    service: VersionRefreshService,
    *,
    ownership: dict[str, ManagerOwnership],
    statuses: dict[str, VersionStatus],
) -> None:
    service._ownership = ownership  # pyright: ignore[reportPrivateUsage]
    service._statuses = statuses  # pyright: ignore[reportPrivateUsage]

    def frozen(_tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        return dict(statuses)

    service.refresh = frozen  # type: ignore[method-assign]


async def _settle_update(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    for _ in range(400):
        screen = app.catalog
        updates = screen._updates  # pyright: ignore[reportPrivateUsage]
        if updates is None or updates.in_flight is None:
            break
        await pilot.pause()
    await pilot.pause()


def _brew_rg() -> Tool:
    return Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=(
            Method(
                kind="github_release",
                params={"repo": "BurntSushi/ripgrep", "asset": "rg.tar.gz", "member": "rg"},
            ),
            Method(kind="brew", params={"formula": "ripgrep"}),
        ),
        priority="P0",
        audience="ai",
        tier="system",
    )


async def test_second_u_press_while_latched_is_refused(tmp_path: Path) -> None:
    tool = _brew_rg()
    started = threading.Event()
    release = threading.Event()
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        started.set()
        assert release.wait(timeout=5)

    ownership = _owned(tool, "brew", package="ripgrep")
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": stale_status})
    updates = UpdateService(
        platform=service.platform,
        runner=runner,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        assert started.wait(timeout=5)
        await pilot.press("u")
        assert "in flight" in app.catalog.status_text
        release.set()
        await _settle_update(app, pilot)
        assert calls == [["brew", "upgrade", "ripgrep"]]


async def test_unknown_owner_row_produces_zero_runner_invocations(tmp_path: Path) -> None:
    tool = _brew_rg()
    calls: list[list[str]] = []
    ownership = _owned(
        tool, "unknown", confidence="none", unknown_reason="the brew inventory could not be read"
    )
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="unknown",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": stale_status})
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert calls == []
        assert "brew inventory" in app.catalog.status_text


async def test_non_mutation_grade_owner_produces_zero_runner_invocations(tmp_path: Path) -> None:
    tool = _brew_rg()
    calls: list[list[str]] = []
    ownership = _owned(
        tool, "brew", confidence="none", unknown_reason="the brew inventory could not be read"
    )
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": stale_status})
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert calls == []
        assert "brew inventory" in app.catalog.status_text


async def test_rg_end_to_end_delegates_to_brew(tmp_path: Path) -> None:
    tool = _brew_rg()
    calls: list[list[str]] = []
    ownership = _owned(tool, "brew", package="ripgrep")
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": stale_status})
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        depth = len(app.screen_stack)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert calls == [["brew", "upgrade", "ripgrep"]]
        assert len(app.screen_stack) == depth


async def test_update_worker_crash_still_posts_and_clears(tmp_path: Path) -> None:
    tool = _brew_rg()
    ownership = _owned(tool, "brew", package="ripgrep")
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": stale_status})

    def boom(_cmd: list[str]) -> None:
        raise VersionError("boom")

    updates = UpdateService(
        platform=service.platform,
        runner=boom,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert app.is_running
        assert updates.in_flight is None
        assert app.catalog.status_text


async def test_fresh_ownership_dispatches_on_reresolve_not_cache(tmp_path: Path) -> None:
    tool = _brew_rg()
    calls: list[list[str]] = []
    cached = _owned(tool, "installer", confidence="by-elimination")
    fresh = _owned(tool, "brew", package="ripgrep")
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="installer",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": cached}, statuses={"rg": stale_status})
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: fresh,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert calls == [["brew", "upgrade", "ripgrep"]]


async def test_fresh_unknown_overrides_cached_green_light(tmp_path: Path) -> None:
    tool = _brew_rg()
    calls: list[list[str]] = []
    cached = _owned(tool, "brew", package="ripgrep")
    fresh = _owned(
        tool, "unknown", confidence="none", unknown_reason="the brew inventory could not be read"
    )
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": cached}, statuses={"rg": stale_status})
    order: list[str] = []

    def reresolve(_tool: Tool) -> ManagerOwnership:
        order.append("reresolve")
        return fresh

    def managed() -> tuple[str, ...] | None:
        order.append("managed")
        return ("x",)

    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=managed,
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=reresolve,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert calls == []
        assert "brew inventory" in app.catalog.status_text
        assert order == ["reresolve"]


async def test_pnpm_precapture_replays_pre_update_set(tmp_path: Path) -> None:
    """12-REVIEWS.md:338-342 — a post-update capture would replay an empty list."""
    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),),
        tier="system",
    )
    ownership = _owned(tool, "installer", confidence="by-elimination")
    live: list[str] = ["@mermaid-js/mermaid-cli", "puppeteer"]
    order: list[str] = []
    replayed: list[tuple[str, ...]] = []
    stale_status = VersionStatus(
        tool_id="pnpm",
        installed="11.9.0",
        latest=None,
        outdated=None,
        stale=True,
        source="installer",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"pnpm": ownership}, statuses={"pnpm": stale_status})

    def reresolve(_tool: Tool) -> ManagerOwnership:
        order.append("reresolve")
        return ownership

    def managed() -> tuple[str, ...] | None:
        order.append("managed")
        return tuple(live)

    def runner(_cmd: list[str]) -> None:
        order.append("mutate")
        live.clear()

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        order.append("replay")
        replayed.append(tuple(packages))
        return tuple(packages)

    updates = UpdateService(
        platform=service.platform,
        runner=runner,
        resolve_tag=lambda _repo: "v1",
        tools={"pnpm": tool},
        managed_packages=managed,
        replay_globals=replay,
        reresolve_ownership=reresolve,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"pnpm": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert order.index("reresolve") < order.index("managed")
        assert order.index("managed") < order.index("mutate")
        assert order.index("mutate") < order.index("replay")
        assert replayed == [("@mermaid-js/mermaid-cli", "puppeteer")]
        assert "replayed" in app.catalog.status_text


async def test_non_pnpm_node_tool_skips_snapshot_and_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = Tool(
        id="mmdc",
        name="mmdc",
        category="ai",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
        tier="system",
    )
    ownership = _owned(tool, "pnpm", package="@mermaid-js/mermaid-cli")
    managed_calls: list[int] = []
    replay_calls: list[int] = []
    stale_status = VersionStatus(
        tool_id="mmdc",
        installed="11.9.0",
        latest="12.3.4",
        outdated=True,
        stale=False,
        source="pnpm",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"mmdc": ownership}, statuses={"mmdc": stale_status})

    def managed() -> tuple[str, ...] | None:
        managed_calls.append(1)
        return ("x",)

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        replay_calls.append(1)
        return tuple(packages)

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="pnpm")

    monkeypatch.setattr("installer.update.perform_update", fake_perform)
    updates = UpdateService(
        platform=service.platform,
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "v1",
        tools={"mmdc": tool},
        managed_packages=managed,
        replay_globals=replay,
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"mmdc": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert managed_calls == []
        assert replay_calls == []


async def test_none_package_snapshot_refuses_the_update(tmp_path: Path) -> None:
    """C3 (12-REVIEW.md, codex-sol-high): pnpm is the exact event that can
    lose the global set, so an unreadable pre-capture snapshot must refuse
    the mutation outright — zero mutation, never "proceed with a warning".
    """
    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),),
        tier="system",
    )
    ownership = _owned(tool, "installer", confidence="by-elimination")
    replay_calls: list[int] = []
    runner_calls: list[list[str]] = []
    stale_status = VersionStatus(
        tool_id="pnpm",
        installed="11.9.0",
        latest=None,
        outdated=None,
        stale=True,
        source="installer",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"pnpm": ownership}, statuses={"pnpm": stale_status})

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        replay_calls.append(1)
        return tuple(packages)

    updates = UpdateService(
        platform=service.platform,
        runner=lambda cmd: runner_calls.append(cmd),
        resolve_tag=lambda _repo: "v1",
        tools={"pnpm": tool},
        managed_packages=lambda: None,
        replay_globals=replay,
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"pnpm": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        assert replay_calls == []
        assert runner_calls == []
        assert "could not be verified" in app.catalog.status_text


async def test_post_update_status_comes_from_version_refresh(tmp_path: Path) -> None:
    tool = Tool(
        id="rectangle",
        name="Rectangle",
        category="search",
        cmd="rectangle",
        methods=(Method(kind="cask", params={"cask": "rectangle"}),),
        tier="system",
    )
    ownership = _owned(tool, "cask", package="rectangle")
    post = VersionStatus(
        tool_id="rectangle",
        installed="0.86",
        latest="0.86",
        outdated=False,
        stale=False,
        source="cask",
    )
    pre = VersionStatus(
        tool_id="rectangle",
        installed="0.85",
        latest="0.86",
        outdated=True,
        stale=False,
        source="cask",
    )
    service = _macos_service(
        tmp_path, resolve_tag=lambda repo: "v1", probe_output=lambda argv: None
    )
    _freeze_status(service, ownership={"rectangle": ownership}, statuses={"rectangle": pre})

    def fake_refresh(tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        return {tools[0].id: post}

    service.refresh = fake_refresh  # type: ignore[method-assign]
    updates = UpdateService(
        platform=service.platform,
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "v1",
        tools={"rectangle": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rectangle": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        cell = app.catalog.query_one(DataTable[Any]).get_cell("rectangle", "ver")
        assert "0.86" in cell.plain


async def test_post_update_status_for_brew_also_comes_from_refresh(tmp_path: Path) -> None:
    tool = _brew_rg()
    ownership = _owned(tool, "brew", package="ripgrep")
    post = VersionStatus(
        tool_id="rg",
        installed="14.1.1",
        latest="14.1.1",
        outdated=False,
        stale=False,
        source="brew",
    )
    pre = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": pre})

    def fake_refresh(tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        return {tools[0].id: post}

    service.refresh = fake_refresh  # type: ignore[method-assign]
    updates = UpdateService(
        platform=service.platform,
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        cell = app.catalog.query_one(DataTable[Any]).get_cell("rg", "ver")
        assert "14.1.1" in cell.plain


async def test_epoch_guard_drops_stale_refresh_after_update(tmp_path: Path) -> None:
    tool = _brew_rg()
    ownership = _owned(tool, "brew", package="ripgrep")
    started = threading.Event()
    release = threading.Event()
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    service._ownership = {"rg": ownership}  # pyright: ignore[reportPrivateUsage]
    original_refresh = service.refresh

    def latched_refresh(tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        started.set()
        assert release.wait(timeout=5)
        return original_refresh(tools)

    service.refresh = latched_refresh  # type: ignore[method-assign]
    post = VersionStatus(
        tool_id="rg",
        installed="14.1.1",
        latest="14.1.1",
        outdated=False,
        stale=False,
        source="brew",
    )

    def post_refresh(tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        return {tools[0].id: post}

    updates = UpdateService(
        platform=service.platform,
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        assert started.wait(timeout=5)
        app.catalog._version_statuses["rg"] = VersionStatus(  # pyright: ignore[reportPrivateUsage]
            tool_id="rg",
            installed="14.1.0",
            latest="14.1.1",
            outdated=True,
            stale=False,
            source="brew",
        )
        service.refresh = post_refresh  # type: ignore[method-assign]
        await pilot.press("u")
        await _settle_update(app, pilot)
        post_cell = app.catalog.query_one(DataTable[Any]).get_cell("rg", "ver")
        assert "14.1.1" in post_cell.plain or "updated" in app.catalog.status_text
        release.set()
        await _settle_versions(app, pilot)
        cell = app.catalog.query_one(DataTable[Any]).get_cell("rg", "ver")
        assert "14.1.0 ->" not in cell.plain


async def test_update_runs_off_the_event_loop_with_no_confirmation(tmp_path: Path) -> None:
    tool = _brew_rg()
    started = threading.Event()
    release = threading.Event()
    ownership = _owned(tool, "brew", package="ripgrep")
    stale_status = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1")
    _freeze_status(service, ownership={"rg": ownership}, statuses={"rg": stale_status})

    def runner(_cmd: list[str]) -> None:
        started.set()
        assert release.wait(timeout=5)

    updates = UpdateService(
        platform=service.platform,
        runner=runner,
        resolve_tag=lambda _repo: "v1",
        tools={"rg": tool},
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], {"rg": True}, service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle_versions(app, pilot)
        depth = len(app.screen_stack)
        await pilot.press("u")
        assert started.wait(timeout=5)
        assert app.catalog.selected == set()
        await pilot.press("space")
        assert app.catalog.selected == {"rg"}
        assert len(app.screen_stack) == depth
        release.set()
        await _settle_update(app, pilot)
        assert len(app.screen_stack) == depth
