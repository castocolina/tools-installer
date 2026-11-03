"""Screen-family lifecycle pilots: launch, the one show_view order, status lifecycle."""

import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from textual.screen import ModalScreen
from textual.widgets import DataTable

from installer import receipts
from installer import uninstall as uninstall_module
from installer.app import UninstallDecision
from installer.doctor import DoctorReport
from installer.enums import Severity
from installer.model import Method, Tool
from installer.ownership import ManagerOwnership, OwnershipCandidate
from installer.session import Disposition, PlanRow, RowOutcome
from installer.ui_common import AppScreen
from installer.uninstall import SweepResult, plan_removal, remove_paths
from installer.update import UpdateOutcome
from installer.version_status import Health, VersionRefreshService, VersionStatus
from installer.wizard_app import (
    NavScreen,
    PolicyInputs,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
)
from tests.screen_family import HeldRemover, settle, wait_until
from tests.state_doubles import (
    FrozenStateService,
    HeldRefreshService,
    ScriptedUpdates,
    absent_state,
    frozen_service,
    held_service,
    offline_service,
    pass_state,
    plan_state,
    removable_state,
)

VIEW_NAMES = ["system", "user", "ai", "doctor", "uninstall", "policies"]


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


def _family_app(
    *,
    has_path_block: Callable[[], bool] = lambda: False,
    initial_view: str = "system",
    startup_warning: str | None = None,
    version_refresh: VersionRefreshService | None = None,
    updates: ScriptedUpdates | None = None,
    app_cls: type[UnifiedApp] = UnifiedApp,
    tools: Sequence[Tool] | None = None,
    uninstall: UninstallInputs | None = None,
) -> UnifiedApp:
    return app_cls(
        list(tools) if tools is not None else [_tool("rg"), _tool("fd")],
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({"pip": False, "npm": False}, None),
        fix_preview="preview",
        fix=lambda: None,
        uninstall=uninstall
        or UninstallInputs(
            ban_names=lambda: [],
            has_path_block=has_path_block,
            remove=lambda _decision: SweepResult(),
            tweak_ids=lambda: (),
        ),
        policies=PolicyInputs(policies=[]),
        initial_view=initial_view,
        startup_warning=startup_warning,
        version_refresh=version_refresh,
        updates=updates,
    )


def _view(app: UnifiedApp, name: str) -> AppScreen:
    return app.view(name)


def _spy(app: UnifiedApp, leaving: AppScreen, target: AppScreen) -> list[str]:
    events: list[str] = []

    def sync(obj: object, attr: str, tag: str) -> None:
        original: Callable[..., Any] = getattr(obj, attr)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            events.append(tag)
            return original(*args, **kwargs)

        setattr(obj, attr, wrapper)

    def asynchronous(obj: object, attr: str, tag: str) -> None:
        original: Callable[..., Any] = getattr(obj, attr)

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            events.append(tag)
            return await original(*args, **kwargs)

        setattr(obj, attr, wrapper)

    sync(leaving, "clear_transient", "clear")
    asynchronous(app, "pop_screen", "pop")
    asynchronous(app, "push_screen", "push")
    sync(target, "enter_view", "enter")
    return events


async def test_launch_shows_the_system_tier_through_show_view():
    app = _family_app()
    async with app.run_test(size=(100, 30)):
        assert app.screen is app.catalog
        assert len(app.screen_stack) == 2
        assert not isinstance(app.screen_stack[0], AppScreen)
        assert app.current_view == "system"


@pytest.mark.parametrize("name", VIEW_NAMES)
async def test_show_view_call_order(name: str):
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        start = "user" if name == "system" else "system"
        await app.show_view(start)
        await pilot.pause()
        events = _spy(app, _view(app, start), _view(app, name))
        await app.show_view(name)
        assert events == ["clear", "pop", "push", "enter"]


async def test_current_view_key_is_a_no_op():
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("down", "space")
        app.catalog.status.set("kept", "ok")
        row = app.screen.query_one(DataTable[Any]).cursor_row
        selected = set(app.catalog.selected)
        events = _spy(app, app.catalog, app.catalog)
        await pilot.press("1")
        assert events == []
        assert app.screen.query_one(DataTable[Any]).cursor_row == row
        assert set(app.catalog.selected) == selected
        assert app.catalog.status.text == "kept"


async def test_nav_burst_with_escape_keeps_depth_two():
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4", "5", "escape", "6", "1", "escape")
        assert len(app.screen_stack) == 2
        assert app.current_view == "system"
        await pilot.press("5")
        assert app.current_view == "uninstall"
        assert len(app.screen_stack) == 2


@pytest.mark.parametrize("name", VIEW_NAMES)
async def test_entry_status_survives_first_entry_and_leave_clears_it(
    name: str, monkeypatch: pytest.MonkeyPatch
):
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        target = _view(app, name)
        if name == app.current_view:
            await app.show_view("doctor")
        original = target.enter_view

        def entering() -> None:
            original()
            target.status.set("entry", "warn")

        with monkeypatch.context() as patch:
            patch.setattr(target, "enter_view", entering)
            await app.show_view(name)
            await pilot.pause()
            assert target.status.text == "entry"
            await app.show_view("doctor" if name != "doctor" else "system")
            assert target.status.text == ""
        await app.show_view(name)
        await pilot.pause()
        assert target.status.text != "entry"


async def test_leaving_a_view_with_no_status_is_a_no_op():
    app = _family_app()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.catalog.status.text == ""
        await app.show_view("doctor")
        await pilot.pause()
        assert app.catalog.status.text == ""
        assert app.catalog.status.severity is None


async def test_uninstall_startup_read_error_stays_visible_on_first_entry():
    calls: list[int] = []

    def has_path_block() -> bool:
        calls.append(1)
        if len(calls) == 1:
            raise OSError("boom")
        return False

    app = _family_app(has_path_block=has_path_block, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        status = _view(app, "uninstall").status
        assert status.text.startswith("Could not read the uninstall state at startup:")
        assert status.severity == "warn"


async def test_flushed_warning_is_not_replaced_by_the_standing_status(tmp_path: Path):
    service = frozen_service(tmp_path)
    service.publish([absent_state(_tool("rg")), absent_state(_tool("fd"))])
    app = _family_app(initial_view="uninstall", startup_warning="w", version_refresh=service)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        status = _view(app, "uninstall").status
        assert status.text == "w"
        await app.show_view("system")
        await app.show_view("uninstall")
        await pilot.pause()
        assert status.text == "Nothing to uninstall."


def _health(app: UnifiedApp, tool_id: str) -> str:
    return app.catalog.query_one(DataTable[Any]).get_cell(tool_id, "health").plain


async def test_launch_pass_renders_the_visible_tier(tmp_path: Path):
    rg = _tool("rg")
    service = HeldRefreshService(tmp_path, [])
    service.pending = (pass_state(rg, platform=service.platform, present=True),)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert _health(app, "rg") == "…"
        service.release.set()
        await settle(app, pilot)
        assert _health(app, "rg") == "✓"
        assert service.calls == [frozenset({"rg", "fd"})]


async def test_failed_pass_writes_the_retry_copy(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [], raising=OSError("disk"))
    service.release.set()
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert app.catalog.status_text == (
            "tool state check failed: disk — the next change retries it"
        )
        assert app.catalog.status.severity is Severity.WARN
        assert _health(app, "rg") == "…"


async def test_a_failed_skills_stage_writes_the_retry_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    service = frozen_service(tmp_path)

    def failing(tools: Sequence[Tool]) -> dict[str, Any]:
        del tools
        raise OSError("skills")

    monkeypatch.setattr(service, "refresh_skills", failing)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert app.catalog.status_text == (
            "tool state check failed: skills — the next change retries it"
        )
        assert app.catalog.status.severity is Severity.WARN


def _brew_owned(tool: Tool) -> ManagerOwnership:
    candidate = OwnershipCandidate(
        owner="brew", method=tool.methods[0], package=tool.id, current_version=None, evidence="t"
    )
    return ManagerOwnership(
        tool_id=tool.id,
        owner="brew",
        method=tool.methods[0],
        package=tool.id,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(candidate,),
        active_candidate="brew",
        active_path=None,
        unknown_reason=None,
        off_policy=False,
        broken=False,
    )


async def test_update_completion_requests_one_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rg = _tool("rg")
    events: list[str] = []
    service = frozen_service(tmp_path)
    refresh = service.refresh

    def logged(tools: Sequence[Tool]) -> None:
        events.append("pass")
        refresh(tools)

    monkeypatch.setattr(service, "refresh", logged)
    updates = ScriptedUpdates({"rg": UpdateOutcome("rg", "updated", "brew")})
    run = updates.run

    def run_logged(target: Any) -> UpdateOutcome:
        events.append("update")
        return run(target)

    monkeypatch.setattr(updates, "run", run_logged)
    app = _family_app(version_refresh=service, updates=updates)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        service.publish(
            [
                pass_state(
                    rg,
                    platform=service.platform,
                    ownership=_brew_owned(rg),
                    version=VersionStatus("rg", "1.0", "1.1", True, False, "brew"),
                )
            ]
        )
        table = app.catalog.query_one(DataTable[Any])
        table.move_cursor(row=table.get_row_index("rg"))
        await pilot.press("u")
        await settle(app, pilot)
        assert service.passes == 2
        assert events == ["pass", "update", "pass"]


def _outcomes(result: str) -> list[RowOutcome]:
    row = PlanRow("rg", Disposition.INSTALL, "")
    return [RowOutcome(row, "done" if result == "done" else "skipped")]


class _ClosableApp(UnifiedApp):
    def close_install(self, result: list[RowOutcome] | None) -> None:
        self._install_closed(result)


async def test_install_close_requests_a_pass_only_when_something_ran(tmp_path: Path):
    service = frozen_service(tmp_path)
    app = cast(_ClosableApp, _family_app(version_refresh=service, app_cls=_ClosableApp))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert service.passes == 1
        for result, expected in ((None, 1), (_outcomes("skipped"), 1), (_outcomes("done"), 2)):
            app.close_install(result)
            await settle(app, pilot)
            assert service.passes == expected


@pytest.mark.parametrize("name", VIEW_NAMES)
async def test_entering_a_view_starts_no_pass(tmp_path: Path, name: str):
    service = frozen_service(tmp_path)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert service.passes == 1
        other = "user" if name == "system" else "system"
        for view in (name, other, name):
            await app.show_view(view)
            await settle(app, pilot)
        assert service.passes == 1


async def test_two_requests_during_a_pass_coalesce_into_one(tmp_path: Path):
    rg = _tool("rg")
    service = HeldRefreshService(tmp_path, [])
    service.pending = (pass_state(rg, platform=service.platform, present=True),)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await wait_until(pilot, lambda: len(service.calls) == 1)
        app.request_refresh()
        app.request_refresh()
        await pilot.pause()
        assert len(service.calls) == 1
        service.release.set()
        await settle(app, pilot)
        assert len(service.calls) == 2
        assert _health(app, "rg") == "✓"


class _Covering(ModalScreen[None]):
    """A minimal modal standing in for ConfirmUninstall, ExecuteScreen or the palette."""


async def test_publish_under_a_modal_waits_for_the_next_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rg = _tool("rg")
    service = frozen_service(tmp_path)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        renders: list[str] = []
        render = app.catalog.state_refreshed

        def spy() -> None:
            renders.append("render")
            render()

        monkeypatch.setattr(app.catalog, "state_refreshed", spy)
        await app.push_screen(_Covering())
        service.queued = (pass_state(rg, platform=service.platform, present=True),)
        app.request_refresh()
        await settle(app, pilot)
        assert renders == []
        await app.pop_screen()
        await pilot.pause()
        assert _health(app, "rg") == "…"
        # show_view of the current view is a no-op, so leave and re-enter.
        await app.show_view("user")
        await app.show_view("system")
        assert _health(app, "rg") == "✓"


async def test_publish_keeps_cursor_selection_and_status(tmp_path: Path):
    fd = _tool("fd")
    service = frozen_service(tmp_path)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("down", "space")
        app.catalog.status.set("kept", "ok")
        row = app.catalog.query_one(DataTable[Any]).cursor_row
        selected = set(app.catalog.selected)
        assert selected
        service.queued = (pass_state(fd, platform=service.platform, present=True),)
        app.request_refresh()
        await settle(app, pilot)
        assert _health(app, "fd") == "✓"
        assert app.catalog.query_one(DataTable[Any]).cursor_row == row
        assert set(app.catalog.selected) == selected
        assert app.catalog.status_text == "kept"


async def test_publish_prunes_a_staged_tool_that_became_unavailable(tmp_path: Path):
    rg = _tool("rg")
    service = frozen_service(tmp_path)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("space", "down", "space")
        assert app.catalog.selected == {"rg", "fd"}
        gone = replace(pass_state(rg, platform=service.platform), health=Health.UNAVAILABLE)
        service.queued = (gone,)
        app.request_refresh()
        await settle(app, pilot)
        assert app.catalog.selected == {"fd"}
        await pilot.press("enter")
        assert app.return_value == ["fd"]


async def test_a_mutation_during_a_running_pass_supersedes_it(tmp_path: Path):
    started = threading.Event()
    release = threading.Event()
    probes: list[str] = []

    def probe(argv: list[str]) -> str | None:
        probes.append(Path(argv[0]).name)
        if not started.is_set():
            started.set()
            assert release.wait(timeout=10)
        return "1.0"

    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda _repo: "v1",
        probe_output=probe,
    )
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await wait_until(pilot, started.is_set)
        service.invalidate(reason="t")
        app.request_refresh()
        release.set()
        await settle(app, pilot)
        state = service.state_of("rg")
        assert state is not None
        assert state.generation == service.epoch
        assert probes.count("rg") >= 2


async def test_await_publication_without_a_service_answers_at_once():
    app = _family_app()
    async with app.run_test(size=(120, 30)):
        got: list[str | None] = []
        app.await_publication(got.append)
        assert got == [None]


async def test_await_publication_joins_the_running_pass(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [])
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, lambda: len(service.calls) == 1)
            got: list[str | None] = []
            app.await_publication(got.append)
            await pilot.pause()
            assert len(service.calls) == 1
            assert got == []
            service.release.set()
            await settle(app, pilot)
            assert got == [None]
            assert len(service.calls) == 1
        finally:
            service.release.set()


async def test_await_publication_starts_one_pass_when_none_runs(tmp_path: Path):
    service = frozen_service(tmp_path)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert service.passes == 1
        got: list[str | None] = []
        app.await_publication(got.append)
        await settle(app, pilot)
        assert service.passes == 2
        assert got == [None]


async def test_await_publication_waits_for_the_pending_pass(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [])
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        first = service.release
        second = threading.Event()
        try:
            await wait_until(pilot, lambda: len(service.calls) == 1)
            served: list[tuple[str | None, int]] = []
            app.await_publication(lambda error: served.append((error, len(service.calls))))
            app.request_refresh()  # queues the follow-up pass behind the running one
            service.release = second  # the follow-up pass waits on its own event
            first.set()
            await wait_until(pilot, lambda: len(service.calls) == 2)
            assert served == []
            second.set()
            await settle(app, pilot)
            assert served == [(None, 2)]
        finally:
            first.set()
            second.set()


async def test_await_publication_reports_the_pass_error(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [], raising=OSError("disk"))
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, lambda: len(service.calls) == 1)
            got: list[str | None] = []
            app.await_publication(got.append)
            service.release.set()
            await settle(app, pilot)
            assert got == ["disk"]
        finally:
            service.release.set()


async def test_await_publication_reports_an_escaping_exception(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [], raising=RuntimeError("boom\nmore"))
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, lambda: len(service.calls) == 1)
            got: list[str | None] = []
            app.await_publication(got.append)
            service.release.set()
            await settle(app, pilot)
            assert got == ["boom"]
        finally:
            service.release.set()


# -- 21-13: the removal runs on a worker under the app mutation lock --

_REFUSAL = "A removal is running; wait for it to finish. Navigation still works."


def _removal_app(
    tmp_path: Path,
    remover: HeldRemover,
    *,
    ban: bool = False,
    service: FrozenStateService | None = None,
    app_cls: type[UnifiedApp] = UnifiedApp,
) -> tuple[UnifiedApp, FrozenStateService]:
    yq, fd = _tool("yq"), _tool("fd")
    service = service if service is not None else frozen_service(tmp_path)
    service.publish(
        [removable_state(yq, [tmp_path / "yq"]), removable_state(fd, [tmp_path / "fd"])]
    )
    inputs = UninstallInputs(
        ban_names=lambda: ["pip"] if ban else [],
        has_path_block=lambda: False,
        remove=remover,
        tweak_ids=lambda: (),
    )
    app = _family_app(tools=[yq, fd], version_refresh=service, uninstall=inputs, app_cls=app_cls)
    return app, service


def _uninstall_health(app: UnifiedApp, tool_id: str) -> str:
    table = app.view("uninstall").query_one(DataTable[Any])
    return table.get_cell(tool_id, "health").plain


async def _confirm_removal(app: UnifiedApp, pilot: Any, tool_id: str) -> None:
    """Select `tool_id` on Uninstall (alone), accept, and confirm the modal."""
    table = app.view("uninstall").query_one(DataTable[Any])
    table.move_cursor(row=table.get_row_index(tool_id))
    await pilot.press("space")
    await pilot.press("enter")
    await pilot.press("enter")
    await pilot.pause()


async def test_a_held_removal_keeps_the_ui_responsive(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "yq")
            await wait_until(pilot, remover.started.is_set)
            status = app.view("uninstall").status
            assert (status.text, status.severity) == ("Removing…", Severity.WARN)
            assert _uninstall_health(app, "yq") == "…"
            assert _uninstall_health(app, "fd") != "…"
            await pilot.press("1")
            await wait_until(pilot, lambda: app.current_view == "system")
            assert _health(app, "yq") == "…"
            await pilot.press("5")
            await wait_until(pilot, lambda: app.current_view == "uninstall")
            remover.release.set()
            service.queued = (absent_state(_tool("yq")),)
            await settle(app, pilot)
            assert app.view("uninstall").status.text.startswith("1 removed")
            await pilot.press("1")
            await wait_until(pilot, lambda: app.current_view == "system")
            assert _health(app, "yq") == "○"
        finally:
            remover.release.set()


async def test_a_second_removal_is_refused_while_one_runs(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "yq")
            await wait_until(pilot, remover.started.is_set)
            await _confirm_removal(app, pilot, "fd")
            status = app.view("uninstall").status
            assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
            assert len(remover.calls) == 1
        finally:
            remover.release.set()


async def test_a_refused_removal_still_requests_one_pass(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "yq")
            await wait_until(pilot, remover.started.is_set)
            before = service.passes
            fd_before = _uninstall_health(app, "fd")
            await _confirm_removal(app, pilot, "fd")
            await wait_until(pilot, lambda: service.passes == before + 1)
            await pilot.pause()
            assert service.passes == before + 1
            assert _uninstall_health(app, "fd") == fd_before
            remover.release.set()
            await settle(app, pilot)
        finally:
            remover.release.set()


async def test_the_lock_is_released_when_the_remover_crashes(tmp_path: Path):
    remover = HeldRemover(raising=RuntimeError("boom"))
    remover.release.set()
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("uninstall")
        service.queued = (removable_state(_tool("yq"), [tmp_path / "yq"]),)
        await _confirm_removal(app, pilot, "yq")
        await settle(app, pilot)
        status = app.view("uninstall").status
        assert status.text == "Uninstall failed: boom. Check permissions, then press enter."
        assert not app.mutation_in_flight
        assert service.state_of("yq") is not None
        assert _uninstall_health(app, "yq") != "…"


async def test_removal_outcomes_do_not_change_the_exit_code(tmp_path: Path):
    remover = HeldRemover(SweepResult(remove_failed=(("yq", "denied"),)))
    remover.release.set()
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("uninstall")
        await _confirm_removal(app, pilot, "yq")
        await settle(app, pilot)
        assert app.view("uninstall").status.text.startswith("1 remove failed")
        assert app.outcomes is None


# -- 21-14: failed rows, retry, the service invalidate, one pass per removal --

_FIX_LINE = "1 remove failed. Fix the cause and press enter to try again."


def _uninstall_screen(app: UnifiedApp) -> UninstallScreen:
    screen = app.view("uninstall")
    assert isinstance(screen, UninstallScreen)
    return screen


async def _select_and_confirm(app: UnifiedApp, pilot: Any, *tool_ids: str) -> None:
    """Toggle each id on the Uninstall table, accept, and confirm the modal."""
    table = app.view("uninstall").query_one(DataTable[Any])
    for tool_id in tool_ids:
        table.move_cursor(row=table.get_row_index(tool_id))
        await pilot.press("space")
    await pilot.press("enter")
    await pilot.press("enter")
    await pilot.pause()


async def _detail_of(app: UnifiedApp, pilot: Any, tool_id: str) -> str:
    table = app.view("uninstall").query_one(DataTable[Any])
    table.move_cursor(row=table.get_row_index(tool_id))
    await pilot.pause()
    return _uninstall_screen(app).detail_text


def _row_keys(app: UnifiedApp) -> list[str]:
    table = app.view("uninstall").query_one(DataTable[Any])
    return [str(key.value) for key in table.rows]


def _section_of(app: UnifiedApp, tool_id: str) -> str:
    keys = _row_keys(app)
    return [key for key in keys[: keys.index(tool_id)] if key.startswith("#")][-1]


async def _fail_fd_and_remove_yq(
    app: UnifiedApp, pilot: Any, remover: HeldRemover, service: FrozenStateService
) -> None:
    await settle(app, pilot)
    await app.show_view("uninstall")
    service.queued = (absent_state(_tool("yq")),)
    await _select_and_confirm(app, pilot, "yq", "fd")
    await wait_until(pilot, remover.started.is_set)
    remover.release.set()
    await settle(app, pilot)


async def test_a_failed_removal_keeps_the_row_selected_with_its_reason(tmp_path: Path):
    remover = HeldRemover(
        SweepResult(removed=("yq",), remove_failed=(("fd", "permission denied"),))
    )
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _fail_fd_and_remove_yq(app, pilot, remover, service)
            screen = _uninstall_screen(app)
            table = screen.query_one(DataTable[Any])
            assert screen.selected == {"fd"}
            assert table.get_cell("fd", "removes").plain == "remove failed"
            assert (await _detail_of(app, pilot, "fd")).startswith(
                "remove failed — permission denied"
            )
            assert screen.status.text.splitlines()[:2] == ["1 removed, 1 remove failed", _FIX_LINE]
            assert screen.status.severity is Severity.ERROR
        finally:
            remover.release.set()


async def test_enter_retries_the_failed_rows(tmp_path: Path):
    remover = HeldRemover(
        SweepResult(removed=("yq",), remove_failed=(("fd", "permission denied"),))
    )
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _fail_fd_and_remove_yq(app, pilot, remover, service)
            await pilot.press("enter")
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(remover.calls) == 2)
            assert [tool.id for tool in remover.calls[1].tools] == ["fd"]
            await settle(app, pilot)
        finally:
            remover.release.set()


async def test_the_removal_invalidates_through_the_app_service(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    remover.release.set()
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("uninstall")
        before = service.passes
        await _confirm_removal(app, pilot, "yq")
        await settle(app, pilot)
        assert service.invalidations == (before,)
        assert service.passes == before + 1


async def test_an_invalidate_failure_is_reported_and_the_pass_still_runs(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    remover.release.set()
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("uninstall")
        before = service.passes
        service.invalidate_error = OSError("disk")
        await _confirm_removal(app, pilot, "yq")
        await settle(app, pilot)
        assert "version cache invalidation failed: disk" in app.view("uninstall").status.text
        assert service.passes == before + 1


async def test_an_env_only_removal_requests_a_pass_without_invalidating(tmp_path: Path):
    remover = HeldRemover(SweepResult())
    remover.release.set()
    app, service = _removal_app(tmp_path, remover, ban=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("uninstall")
        before = service.passes
        await _confirm_removal(app, pilot, "#ban")
        await settle(app, pilot)
        assert remover.calls[0].remove_ban
        assert service.invalidations == ()
        assert service.passes == before + 1


async def test_a_permission_failure_stays_selected_after_the_follow_up_pass(tmp_path: Path):
    remover = HeldRemover(SweepResult(remove_failed=(("fd", "permission denied"),)))
    fd = _tool("fd")
    service = held_service(tmp_path, [removable_state(fd, [tmp_path / "fd"])])
    service.release.set()
    app, _service = _removal_app(tmp_path, remover, service=service)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            service.release.clear()
            await _select_and_confirm(app, pilot, "fd")
            await wait_until(pilot, remover.started.is_set)
            remover.release.set()
            await wait_until(pilot, lambda: len(service.calls) == 2)
            assert _uninstall_screen(app).selected == {"fd"}
            service.release.set()
            await settle(app, pilot)
            assert _uninstall_screen(app).selected == {"fd"}
            assert _section_of(app, "fd") == "#removable here"
            assert (await _detail_of(app, pilot, "fd")).startswith(
                "remove failed — permission denied"
            )
        finally:
            remover.release.set()
            service.release.set()


async def test_a_refused_row_leaves_the_selection_when_its_proof_is_gone(tmp_path: Path):
    remover = HeldRemover(SweepResult(remove_failed=(("fd", "changed since the preview"),)))
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            service.queued = (plan_state(_tool("fd"), owner="unknown", confidence="none"),)
            await _select_and_confirm(app, pilot, "fd")
            await wait_until(pilot, remover.started.is_set)
            remover.release.set()
            await settle(app, pilot)
            assert _uninstall_screen(app).selected == set()
            assert _section_of(app, "fd") == "#managed elsewhere"
            assert (await _detail_of(app, pilot, "fd")).startswith(
                "remove failed — changed since the preview"
            )
        finally:
            remover.release.set()


async def test_a_partial_delete_keeps_its_reason_while_leftovers_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    fd = replace(
        _tool("fd"),
        methods=(
            Method(
                kind="github_release",
                params={"repo": "a/fd", "asset": "x", "member": "fd"},
            ),
        ),
    )
    plan = plan_removal([fd], bin_dir)
    assert plan.removable == (bin_dir / "fd", opt)
    link = receipts.fingerprint(bin_dir / "fd", "link")
    directory = receipts.fingerprint(opt, "dir", key="fd")
    assert link is not None and directory is not None
    real_rmtree = uninstall_module.shutil.rmtree

    def failing_rmtree(path: str | Path, *args: object, **kwargs: object) -> None:
        if Path(path).name.endswith(".tools-installer.rm"):
            raise OSError("disk gremlins")
        real_rmtree(path)

    def remove(decision: UninstallDecision) -> SweepResult:
        del decision
        try:
            remove_paths([link, directory])
        except OSError as exc:
            return SweepResult(remove_failed=(("fd", str(exc)),))
        return SweepResult(removed=("fd",))

    service = frozen_service(tmp_path)
    service.publish([plan_state(fd, removable=plan)])
    inputs = UninstallInputs(
        ban_names=lambda: [],
        has_path_block=lambda: False,
        remove=remove,
        tweak_ids=lambda: (),
    )
    app = _family_app(tools=[fd], version_refresh=service, uninstall=inputs)
    monkeypatch.setattr(uninstall_module.shutil, "rmtree", failing_rmtree)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("uninstall")
        await _select_and_confirm(app, pilot, "fd")
        await settle(app, pilot)
        remainder = plan_removal([fd], bin_dir)
        assert remainder.removable == () and opt in remainder.yourself
        service.queued = (plan_state(fd, health=Health.MISSING, removable=remainder),)
        app.request_refresh()
        await settle(app, pilot)
        assert _section_of(app, "fd") == "#nothing to do"
        detail = await _detail_of(app, pilot, "fd")
        assert detail.startswith("remove failed — disk gremlins")
        assert f" · remove it yourself: {opt}" in detail
        monkeypatch.setattr(uninstall_module.shutil, "rmtree", real_rmtree)
        real_rmtree(opt)
        service.queued = (
            plan_state(fd, health=Health.MISSING, removable=plan_removal([fd], bin_dir)),
        )
        app.request_refresh()
        await settle(app, pilot)
        assert "remove failed" not in await _detail_of(app, pilot, "fd")


async def test_a_failed_reason_survives_leaving_and_reentering_uninstall(tmp_path: Path):
    remover = HeldRemover(SweepResult(remove_failed=(("fd", "permission denied"),)))
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _select_and_confirm(app, pilot, "fd")
            await wait_until(pilot, remover.started.is_set)
            remover.release.set()
            await settle(app, pilot)
            await app.show_view("system")
            await app.show_view("uninstall")
            assert (await _detail_of(app, pilot, "fd")).startswith(
                "remove failed — permission denied"
            )
            remover.release.clear()
            remover.started.clear()
            await pilot.press("enter")
            await pilot.press("enter")
            await wait_until(pilot, remover.started.is_set)
            assert "remove failed" not in await _detail_of(app, pilot, "fd")
            assert service.passes >= 1
        finally:
            remover.release.set()


# -- 21-14: quitting waits for a running removal --

_WAITING = "Waiting for the removal to finish…"


class _PeekApp(UnifiedApp):
    def pending_warnings(self) -> list[str]:
        return list(self._pending_warnings)


async def _hold_a_removal(
    app: UnifiedApp, pilot: Any, remover: HeldRemover, tool_id: str = "yq"
) -> None:
    await settle(app, pilot)
    await app.show_view("uninstall")
    await _confirm_removal(app, pilot, tool_id)
    await wait_until(pilot, remover.started.is_set)


async def _quit_during_a_removal(tmp_path: Path, key: str) -> tuple[UnifiedApp, int, int]:
    """Hold a removal, press `key`, release; the app, passes since the removal
    started, and the remover's call count."""
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover)
            passes = service.passes
            await pilot.press(key)
            status = app.view("uninstall").status
            await wait_until(pilot, lambda: status.text == _WAITING)
            assert status.severity is Severity.WARN
            assert app.is_running
            remover.release.set()
            await wait_until(pilot, lambda: not app.is_running)
        finally:
            remover.release.set()
    return app, service.passes - passes, len(remover.calls)


async def test_quit_during_a_removal_waits_for_it(tmp_path: Path):
    app, _extra_passes, calls = await _quit_during_a_removal(tmp_path, "q")
    assert app.return_value is None
    assert calls == 1


async def test_ctrl_c_during_a_removal_waits_too(tmp_path: Path):
    app, _extra_passes, calls = await _quit_during_a_removal(tmp_path, "ctrl+c")
    assert app.return_value is None
    assert calls == 1


async def test_quit_during_a_removal_requests_no_pass(tmp_path: Path):
    _app, extra_passes, _calls = await _quit_during_a_removal(tmp_path, "q")
    assert extra_passes == 0


async def test_quit_without_a_removal_exits_at_once(tmp_path: Path):
    app, _service = _removal_app(tmp_path, HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("q")
        assert not app.is_running
    assert app.return_value is None


async def test_q_under_the_palette_during_a_removal_does_nothing(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover)
            await pilot.press("ctrl+p")
            assert isinstance(app.screen, NavScreen)
            await pilot.press("q")
            assert app.is_running
            assert isinstance(app.screen, NavScreen)
            assert not remover.release.is_set()
            remover.release.set()
            await settle(app, pilot)
            assert app.is_running
            assert app.view("uninstall").status.text.startswith("1 removed")
        finally:
            remover.release.set()


async def test_ctrl_c_under_the_palette_during_a_removal_waits(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _removal_app(tmp_path, remover, app_cls=_PeekApp)
    assert isinstance(app, _PeekApp)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover)
            await pilot.press("ctrl+p")
            assert isinstance(app.screen, NavScreen)
            await pilot.press("ctrl+c")
            await wait_until(pilot, lambda: app.pending_warnings() == [_WAITING])
            assert app.is_running
            remover.release.set()
            await wait_until(pilot, lambda: not app.is_running)
        finally:
            remover.release.set()
    assert app.return_value is None
    assert len(remover.calls) == 1
