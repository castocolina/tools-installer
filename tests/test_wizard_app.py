from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from installer.app import UninstallDecision
from installer.doctor import DoctorReport
from installer.model import Method, Tool
from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.wizard_app import (
    VIEW_ORDER,
    DoctorScreen,
    FixScreen,
    NavScreen,
    PlaceholderScreen,
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


def _uninstall_inputs(
    *,
    removable: list[tuple[Tool, list[Path]]] | None = None,
    ban_names: list[str] | None = None,
    has_path_block: bool = False,
    remove: Callable[[UninstallDecision], None] = lambda _decision: None,
) -> UninstallInputs:
    return UninstallInputs(
        removable=removable if removable is not None else [],
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
    assert VIEW_ORDER == ("catalog", "doctor", "fix", "uninstall", "policies")


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
        assert app.current_view == "fix"
        await pilot.press("4")
        assert app.current_view == "uninstall"
        await pilot.press("5")
        assert app.current_view == "policies"
        await pilot.press("1")
        assert app.current_view == "catalog"


async def test_uninstall_view_is_reachable() -> None:
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
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


async def test_fix_screen_previews_then_applies_live() -> None:
    applied: list[str] = []
    app = _app(fix_preview="Will wire ~/.local/bin", fix=lambda: applied.append("ran"))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")  # fix view
        assert isinstance(app.screen, FixScreen)
        assert app.screen.applied is False
        assert applied == []  # nothing applied just by viewing
        await pilot.press("a")  # Apply
        assert applied == ["ran"]
        assert app.screen.applied is True


async def test_fix_screen_apply_is_idempotent() -> None:
    applied: list[str] = []
    app = _app(fix=lambda: applied.append("ran"))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")
        await pilot.press("a")
        await pilot.press("a")  # second press is inert once applied
        assert applied == ["ran"]


async def test_initial_view_opens_on_that_view() -> None:
    app = _app(initial_view="doctor")
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "doctor"
        assert isinstance(app.screen, DoctorScreen)


async def test_initial_view_fix_opens_on_fix() -> None:
    app = _app(initial_view="fix")
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "fix"
        assert isinstance(app.screen, FixScreen)


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


async def test_fix_screen_surfaces_apply_failure_without_crashing() -> None:
    def boom() -> None:
        raise OSError("permission denied: ~/.myshellrc")

    app = _app(fix=boom)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")  # fix view
        assert isinstance(app.screen, FixScreen)
        await pilot.press("a")  # apply fails inside the closure
        assert app.is_running  # the error was caught; no traceback tore down the app
        assert app.screen.applied is False
        assert app.screen.error is not None
        assert "permission denied" in app.screen.error
        await pilot.press("a")  # the error path allows a retry (still not applied)
        assert app.screen.applied is False


async def test_navigating_away_from_fix_without_apply_writes_nothing() -> None:
    applied: list[str] = []
    app = _app(fix=lambda: applied.append("ran"))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("3")  # fix view
        assert isinstance(app.screen, FixScreen)
        await pilot.press("1")  # back to catalog without applying
        assert app.current_view == "catalog"
        assert app.screen is app.catalog
        assert applied == []  # the fix closure was never called


async def test_uninstall_toggle_selects_highlighted_tool() -> None:
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("space")
        assert app.screen.selected == {"rg"}
        await pilot.press("space")
        assert app.screen.selected == set()


async def test_uninstall_select_all_includes_ban_and_block() -> None:
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip", "npm"],
        has_path_block=True,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")
        assert app.screen.selected == {"rg"}
        assert app.screen.remove_ban is True
        assert app.screen.remove_path_block is True
        await pilot.press("i")  # invert clears everything
        assert app.screen.selected == set()
        assert app.screen.remove_ban is False
        assert app.screen.remove_path_block is False


async def test_uninstall_apply_calls_remove_and_flips_applied() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        remove=captured.append,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")  # select rg
        await pilot.press("enter")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        assert captured[0].paths == (Path("/opt/rg"),)
        assert captured[0].remove_ban is False


async def test_uninstall_empty_selection_refuses() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])], remove=captured.append)
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")  # nothing selected
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert captured == []  # closure never called
        assert "at least one" in app.screen.status_text


async def test_uninstall_apply_error_surfaces_and_does_not_crash() -> None:
    def boom(_decision: UninstallDecision) -> None:
        raise OSError("permission denied")

    inputs = _uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])], remove=boom)
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("space")
        await pilot.press("enter")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status_text.lower()


async def test_uninstall_initial_view_opens_on_uninstall() -> None:
    app = _app(
        uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, UninstallScreen)


async def test_uninstall_empty_state_shows_nothing_line() -> None:
    app = _app(uninstall=_uninstall_inputs())  # no removable, no ban, no block
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")  # no-op
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert "Nothing to uninstall" in app.screen.status_text


async def test_ctrl_c_aborts_from_uninstall_view() -> None:
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("ctrl+c")
    assert app.return_value is None


async def test_uninstall_empty_table_toggle_noop() -> None:
    """Space on an empty uninstall table is a no-op (covers _highlighted_key row_count==0)."""
    app = _app(uninstall=_uninstall_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("space")
        assert app.screen.selected == set()
        assert app.screen.applied is False


async def test_uninstall_keys_noop_after_applied() -> None:
    """space/a/i are no-ops once applied is True."""
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        has_path_block=True,
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")  # select all
        await pilot.press("enter")  # apply → applied = True
        assert app.screen.applied is True
        selected_snapshot = set(app.screen.selected)
        ban_snapshot = app.screen.remove_ban
        block_snapshot = app.screen.remove_path_block
        # These should all be no-ops now
        await pilot.press("space")
        await pilot.press("a")
        await pilot.press("i")
        assert app.screen.applied is True
        assert app.screen.selected == selected_snapshot
        assert app.screen.remove_ban == ban_snapshot
        assert app.screen.remove_path_block == block_snapshot


async def test_uninstall_partial_selection_apply() -> None:
    """Only selected tools appear in the UninstallDecision paths (covers the
    `if tool.id in self.selected` false branch for the unselected tool)."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        removable=[
            (_tool("rg"), [Path("/opt/rg")]),
            (_tool("fd"), [Path("/opt/fd")]),
        ],
        remove=captured.append,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        # Cursor starts on row 0 (rg); space selects only that one.
        await pilot.press("space")
        assert len(app.screen.selected) == 1
        await pilot.press("enter")
    assert len(captured) == 1
    assert len(captured[0].paths) == 1
    assert Path("/opt/rg") in captured[0].paths
    assert Path("/opt/fd") not in captured[0].paths


async def test_uninstall_applied_summary_ban_and_path() -> None:
    """Status text mentions ban and PATH lines when both are selected (covers
    _applied_summary branches for remove_ban and remove_path_block)."""
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        has_path_block=True,
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")  # select all: tool + ban + path block
        await pilot.press("enter")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        assert "ban removed" in app.screen.status_text
        assert "PATH wiring removed" in app.screen.status_text


async def test_uninstall_applied_summary_omits_tool_line_when_no_tool() -> None:
    """Selecting only the ban (no tool) yields no 'Removed N tool(s).' line
    (covers the `if tool_count:` false branch of _applied_summary)."""
    inputs = _uninstall_inputs(
        removable=[(_tool("rg"), [Path("/opt/rg")])],
        ban_names=["pip"],
        remove=lambda _d: None,
    )
    app = _app(uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("down")  # move cursor off the tool row onto the ban row
        await pilot.press("space")  # select only the ban
        assert app.screen.selected == set()
        assert app.screen.remove_ban is True
        await pilot.press("enter")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        assert "tool(s)" not in app.screen.status_text
        assert "ban removed" in app.screen.status_text


async def test_uninstall_toggle_clears_stale_validation_toast() -> None:
    """A refusal toast must not linger once the selection changes (covers the
    `if self.status_text:` true branch of _clear_status)."""
    app = _app(uninstall=_uninstall_inputs(removable=[(_tool("rg"), [Path("/opt/rg")])]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")  # nothing selected → refusal toast
        assert isinstance(app.screen, UninstallScreen)
        assert "at least one" in app.screen.status_text
        await pilot.press("space")  # select rg → toast cleared
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.status_text == ""


async def test_palette_from_placeholder_navigates_without_desync() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")  # -> doctor view
        assert app.current_view == "doctor"
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        # ListView starts on catalog(0); step to policies(4): catalog,doctor,fix,uninstall,policies
        await pilot.press("down", "down", "down", "down", "enter")
        assert app.current_view == "policies"
        assert not isinstance(app.screen, NavScreen)
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_view_is_reachable() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert app.current_view == "policies"
        assert isinstance(app.screen, PoliciesScreen)


async def test_policies_reachable_via_palette() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        await pilot.press("down", "down", "down", "down", "enter")  # 5th item: policies
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
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["apply"]
        assert app.screen.active_state["ban"] is True
        assert "enabled" in app.screen.status_text
        assert "Shims:" in app.screen.status_text


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
        await pilot.press("enter")
        assert table.get_cell("ban", "state").plain == "● [on]"


async def test_policy_toggle_disables_active_policy() -> None:
    calls: list[str] = []
    policy = _fake_policy(active=True, remove=lambda: (calls.append("remove"), _ok_result())[1])
    app = _app(policies=_policy_inputs([policy]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["remove"]
        assert app.screen.active_state["ban"] is False
        assert "disabled" in app.screen.status_text


async def test_policy_toggle_error_surfaces_and_does_not_crash() -> None:
    def boom() -> PolicyResult:
        raise OSError("permission denied")

    app = _app(policies=_policy_inputs([_fake_policy(active=False, apply=boom)]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is False  # unchanged on failure
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status_text.lower()


async def test_policy_toggle_noop_on_empty_table() -> None:
    """Enter on an empty policies table is a no-op (covers _highlighted_policy
    row_count==0 and the action_toggle_policy policy-is-None guard)."""
    app = _app(policies=_policy_inputs([]))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, PoliciesScreen)
        await pilot.press("enter")
        assert app.screen.status_text == ""
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
        await pilot.press("5")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is True
        assert "pip found on PATH" in app.screen.status_text


async def test_placeholder_screen_renders_message() -> None:
    """PlaceholderScreen renders its message in the #placeholder label.
    The class is kept as a stand-in for future views; this test covers
    lines 71-72 and 75 of wizard_app.py."""
    from textual.app import App
    from textual.widgets import Label

    class _WrapApp(App[None]):
        def get_default_screen(self) -> PlaceholderScreen:
            return PlaceholderScreen("hello placeholder")

    async with _WrapApp().run_test(size=(80, 20)) as pilot:
        label = pilot.app.query_one("#placeholder", Label)
        assert "hello placeholder" in str(label.content)
