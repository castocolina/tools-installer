import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar, cast

from textual.pilot import Pilot
from textual.widgets import DataTable, Static

from installer.app import UninstallDecision
from installer.doctor import DoctorReport
from installer.model import Method, Tool
from installer.pnpm_globals import NodeGlobal, NodeGlobalsReport, reinstall_preview
from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.run import CommandError
from installer.ui_common import BASE_VIEW
from installer.uninstall import SweepResult, ToolRow
from installer.wizard_app import (
    VIEW_ORDER,
    ConfirmUninstall,
    DoctorScreen,
    NavScreen,
    PoliciesScreen,
    PolicyInputs,
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
    active: bool = False,
    apply: Callable[[], PolicyResult] = _ok_result,
    remove: Callable[[], PolicyResult] = _ok_result,
) -> Policy:
    return Policy(
        id="ban",
        label="pip/npm ban",
        description="blocks bare pip/npm",
        active=active,
        apply=apply,
        remove=remove,
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
    globals_preview: Callable[[], str] | None = None,
    reinstall_globals: Callable[[], tuple[str, ...]] | None = None,
    initial_view: str = BASE_VIEW,
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
    )


async def _settle(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    """Wait for the Doctor reinstall worker, which runs off the event loop."""
    for _ in range(200):
        screen = app.screen
        if not isinstance(screen, DoctorScreen) or not screen.globals_running:
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
        globals_preview=lambda: preview,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)):
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
        globals_preview=lambda: degraded,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "pnpm-managed globals" in body
        assert degraded in body
        assert not any(line.strip().startswith("pnpm add") for line in body.splitlines())
        assert body.strip() != ""


async def test_doctor_r_reinstalls_once_and_reports_success() -> None:
    calls: list[str] = []

    def reinstall() -> tuple[str, ...]:
        calls.append("r")
        return ("@mermaid-js/mermaid-cli",)

    app = _app(
        node_globals=lambda: _mmdc_report(missing=()),
        reinstall_globals=reinstall,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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

    def slow() -> tuple[str, ...]:
        started.set()
        assert release.wait(timeout=5)
        return ("@mermaid-js/mermaid-cli",)

    app = _app(
        node_globals=lambda: _mmdc_report(missing=()),
        reinstall_globals=slow,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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


async def test_doctor_r_clears_the_stale_missing_globals_warning() -> None:
    # The globals audit is a live probe whose answer the action just changed,
    # so the screen must not render "went missing" above "reinstalled".
    missing = ["mmdc"]

    def read() -> NodeGlobalsReport:
        return _mmdc_report(missing=tuple(missing))

    def reinstall() -> tuple[str, ...]:
        missing.clear()
        return ("@mermaid-js/mermaid-cli",)

    app = _app(node_globals=read, reinstall_globals=reinstall, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
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
    def boom() -> tuple[str, ...]:
        raise CommandError(["pnpm", "add", "-g", "x"], 1)

    app = _app(
        node_globals=lambda: _mmdc_report(),
        reinstall_globals=boom,
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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
        reinstall_globals=lambda: calls.append("r") or (),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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
        globals_preview=lambda: reinstall_preview((), known=False),
        reinstall_globals=lambda: calls.append("r") or (),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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
        globals_preview=lambda: reinstall_preview(()),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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
        reinstall_globals=lambda: reinstall_calls.append("r") or ("pkg",),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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
        reinstall_globals=lambda: reinstall_calls.append("r") or ("pkg",),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
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
        assert isinstance(app.screen, DoctorScreen)
        assert all("pnpm-managed global set" not in item.title for item in app.screen.guidance)
        missing.append("mmdc")
        await pilot.press("escape")
        await pilot.press("4")
        assert isinstance(app.screen, DoctorScreen)
        assert any("pnpm-managed global set" in item.title for item in app.screen.guidance)


async def test_doctor_tui_guidance_rewrites_make_setup_prefix() -> None:
    app = _app(node_globals=lambda: _mmdc_report(), initial_view="doctor")
    async with app.run_test(size=(100, 30)):
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
