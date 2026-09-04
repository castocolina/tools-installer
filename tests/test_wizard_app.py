from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from textual.widgets import DataTable, Static

from installer.app import UninstallDecision
from installer.doctor import DoctorReport
from installer.model import Method, Tool
from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.uninstall import ToolRow
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
        desc="",
    )


def _removable_row(tool: Tool, paths: list[Path]) -> ToolRow:
    return ToolRow(tool, "removable", paths, "installed in userspace — removable here", True)


def _uninstall_inputs(
    *,
    rows: list[ToolRow] | None = None,
    ban_names: list[str] | None = None,
    has_path_block: bool = False,
    remove: Callable[[UninstallDecision], None] = lambda _decision: None,
) -> UninstallInputs:
    return UninstallInputs(
        rows=rows if rows is not None else [],
        ban_names=ban_names if ban_names is not None else [],
        has_path_block=has_path_block,
        remove=remove,
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
    guard_status: dict[str, bool] | None = None,
    guard_warning: str | None = None,
    fix_preview: str = "Will wire ~/.local/bin into ~/.zshrc",
    fix: Callable[[], None] = lambda: None,
    uninstall: UninstallInputs | None = None,
    policies: PolicyInputs | None = None,
    initial_view: str = "catalog",
) -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")]
    installed: Mapping[str, bool] = {"rg": True, "fd": False}
    return UnifiedApp(
        tools,
        installed,
        {"search": "find things"},
        report=report or DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status or {"pip": False, "npm": False},
        guard_warning=guard_warning,
        fix_preview=fix_preview,
        fix=fix,
        uninstall=uninstall or _uninstall_inputs(),
        policies=policies or _policy_inputs(),
        initial_view=initial_view,
    )


def test_default_palette_is_disabled() -> None:
    assert UnifiedApp.ENABLE_COMMAND_PALETTE is False


def test_view_order_lists_every_view() -> None:
    assert VIEW_ORDER == ("catalog", "doctor", "uninstall", "policies")


async def test_starts_on_the_catalog_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "catalog"


async def test_number_key_navigates_to_each_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)
        await pilot.press("3")
        assert app.current_view == "uninstall"
        await pilot.press("4")
        assert app.current_view == "policies"
        await pilot.press("1")
        assert app.current_view == "catalog"


async def test_uninstall_view_is_reachable() -> None:
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        assert app.current_view == "uninstall"
        assert isinstance(app.screen, UninstallScreen)


async def test_doctor_screen_renders_guidance() -> None:
    app = _app(report=DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=()))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
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
        await pilot.press("2")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert calls == []
        assert screen.applied is False
        assert screen.error is None


async def test_doctor_enter_applies_fix_once() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
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
        await pilot.press("2")
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
        await pilot.press("2")
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
        await pilot.press("1")  # already on catalog
        assert app.current_view == "catalog"
        assert app.is_running


async def test_palette_and_key_resolve_to_the_same_view() -> None:
    # Direct key route.
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "doctor"
    by_key = app.current_view
    # Palette route: open Ctrl+P, pick the "doctor" item.
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "enter")  # first item is catalog; second is doctor
        assert app.current_view == "doctor"
    assert app.current_view == by_key


async def test_palette_escape_does_not_navigate() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("escape")
        assert app.current_view == "catalog"
        assert not isinstance(app.screen, NavScreen)


async def test_ctrl_c_aborts_from_a_placeholder_view() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")  # navigate onto the doctor placeholder
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
        await pilot.press("2")  # must NOT navigate underneath the modal
        assert isinstance(app.screen, NavScreen)
        assert app.current_view == "catalog"
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
        await pilot.press("3")
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
        await pilot.press("3")
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
        await pilot.press("3")
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
        await pilot.press("3")
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
    app = _app(uninstall=_uninstall_inputs(rows=rows, remove=captured.append))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
        rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])], remove=captured.append
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("enter")  # nothing selected
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert captured == []  # closure never called
        assert "at least one" in app.screen.status.text


async def test_uninstall_apply_error_surfaces_and_does_not_crash() -> None:
    def boom(_decision: UninstallDecision) -> None:
        raise OSError("permission denied")

    inputs = _uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])], remove=boom)
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
        await pilot.press("3")
        await pilot.press("enter")  # no-op
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert "Nothing to uninstall" in app.screen.status.text


async def test_ctrl_c_aborts_from_uninstall_view() -> None:
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("ctrl+c")
    assert app.return_value is None


async def test_uninstall_empty_table_toggle_noop() -> None:
    """Space on an empty uninstall table is a no-op."""
    app = _app(uninstall=_uninstall_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
        remove=captured.append,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
    app = _app(uninstall=_uninstall_inputs(rows=rows, remove=captured.append))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
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
        await pilot.press("3")
        await pilot.press("space")
        await pilot.press("enter")  # accept → modal
        await pilot.pause()
        assert isinstance(app.screen, ConfirmUninstall)
        assert "1" in app.screen.summary  # one item to remove


async def test_uninstall_toggle_clears_stale_validation_toast() -> None:
    """A refusal toast must not linger once the selection changes."""
    app = _app(uninstall=_uninstall_inputs(rows=[_removable_row(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("enter")  # nothing selected → refusal toast
        assert isinstance(app.screen, UninstallScreen)
        assert "at least one" in app.screen.status.text
        await pilot.press("space")  # select rg → toast cleared
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.status.text == ""


async def test_palette_from_placeholder_navigates_without_desync() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")  # -> doctor view
        assert app.current_view == "doctor"
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        # ListView starts on catalog(0); step to policies(3): catalog,doctor,uninstall,policies
        await pilot.press("down", "down", "down", "enter")
        assert app.current_view == "policies"
        assert not isinstance(app.screen, NavScreen)
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_view_is_reachable() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_reachable_via_palette() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "down", "down", "enter")  # 4th item: policies
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
        await pilot.press("4")
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


async def test_policy_toggle_disables_active_policy() -> None:
    calls: list[str] = []
    policy = _fake_policy(active=True, remove=lambda: (calls.append("remove"), _ok_result())[1])
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
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
        await pilot.press("4")
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
        await pilot.press("4")
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
        await pilot.press("4")
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
        await pilot.press("2")
        assert isinstance(app.screen, DoctorScreen)
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("3")
        assert isinstance(app.screen, UninstallScreen)
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("4")
        assert isinstance(app.screen, PoliciesScreen)
        assert len(app.screen.query(FooterBar)) == 1


async def test_q_quits_from_every_pushed_view() -> None:
    """q must quit from any view, not just the catalog (regression: q was
    bound only on CatalogScreen, so non-catalog views had no working quit)."""
    for view in ("doctor", "uninstall", "policies"):
        app = _app(initial_view=view)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("q")
            assert not app.is_running  # quit fired while still on the sub-view
        assert app.return_value is None


async def test_esc_returns_to_catalog_from_a_pushed_view() -> None:
    """esc is the one-deep 'back': from any sub-view it pops to the catalog."""
    app = _app(initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.current_view == "doctor"
        await pilot.press("escape")
        assert app.current_view == "catalog"
        assert app.is_running  # esc goes back, does not quit


async def test_esc_on_catalog_is_inert() -> None:
    """On the base catalog there is nowhere to go back to; esc must not quit."""
    app = _app(initial_view="catalog")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("escape")
        assert app.current_view == "catalog"
        assert app.is_running


async def test_q_does_not_quit_while_nav_palette_open() -> None:
    """q is a priority App binding, so it DOES reach action_abort even with the
    Ctrl+P palette open — the _navigable() guard (palette is neither catalog nor
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
    """Rapid 1-4 presses must not corrupt the [catalog] / [catalog, <view>]
    stack invariant or wedge navigation (the 'keys stop responding' bug)."""
    from installer.catalog_tui import CatalogScreen

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2", "3", "4", "1")
        assert app.current_view == "catalog"
        assert isinstance(app.screen, CatalogScreen)
        # The catalog is the app's base screen (get_default_screen), so it is
        # never pushed or popped — it is always the permanent bottom of the stack.
        # After navigating back to "catalog", the stack is [catalog] (depth 1).
        assert len(app.screen_stack) == 1  # back to just the catalog base
        # not wedged: a subsequent press still navigates
        await pilot.press("3")
        assert app.current_view == "uninstall"
        assert len(app.screen_stack) == 2


async def test_rapid_switch_away_from_uninstall_does_not_wedge() -> None:
    """Navigating away from Uninstall before its ToolBrowser's post-mount refresh
    callback runs must not raise. The browser schedules _refresh_marks via
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
        for name in ("doctor", "uninstall", "policies", "uninstall", "catalog"):
            await app.run_action(f"show('{name}')")
        await pilot.pause()
        # Not wedged: navigation still works and no exception was stored.
        await pilot.press("3")
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
        for key in "52452152":  # ends on 2: the user's "come back to Doctor" step
            event = events.Key(key, key)
            event.set_sender(app)
            app.post_message(event)
            await asyncio.sleep(0)  # yield so the burst overlaps the transitions
        await pilot.pause()
        assert app.current_view == "doctor"
        # and the keys still work afterwards
        await pilot.press("3")
        assert app.current_view == "uninstall"
