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
from installer.catalog_tui import CatalogScreen
from installer.doctor import DoctorReport
from installer.enums import Severity
from installer.model import Method, Tool
from installer.ownership import ManagerOwnership, OwnershipCandidate
from installer.pnpm_globals import NodeGlobalsReport
from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.session import Disposition, PlanRow, RowOutcome
from installer.ui_common import AppScreen
from installer.uninstall import SweepResult, plan_removal, remove_paths
from installer.update import UpdateOutcome
from installer.version_status import Health, VersionRefreshService, VersionStatus
from installer.wizard_app import (
    LinkModeScreen,
    NavScreen,
    PolicyInputs,
    TimePickerScreen,
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


# -- 21-15: an update holds the same app lock --

_UPDATE_REFUSAL = "An update is running; wait for it to finish. Navigation still works."


class _HeldUpdates(ScriptedUpdates):
    """A scripted update service whose run waits until the test releases it."""

    def __init__(self) -> None:
        super().__init__({"rg": UpdateOutcome("rg", "updated", "brew")})
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, target: Any) -> UpdateOutcome:
        self.started.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("_HeldUpdates was never released")
        return super().run(target)


def _rg_state(service: FrozenStateService, case: str) -> Any:
    rg = _tool("rg")
    outdated = case != "current"
    version = VersionStatus("rg", "1.0", "1.1" if outdated else "1.0", outdated, False, "brew")
    if case == "broken":
        return plan_state(rg, health=Health.BROKEN, reasons=("rg exits non-zero",))
    if case == "unknown_owner":
        return pass_state(rg, platform=service.platform, version=version)
    return pass_state(rg, platform=service.platform, ownership=_brew_owned(rg), version=version)


def _update_app(
    tmp_path: Path, updates: ScriptedUpdates, remover: HeldRemover, case: str = "outdated"
) -> tuple[UnifiedApp, FrozenStateService]:
    rg, fd = _tool("rg"), _tool("fd")
    service = frozen_service(tmp_path)
    service.publish([_rg_state(service, case), removable_state(fd, [tmp_path / "fd"])])
    inputs = UninstallInputs(
        ban_names=lambda: [],
        has_path_block=lambda: False,
        remove=remover,
        tweak_ids=lambda: (),
    )
    app = _family_app(tools=[rg, fd], version_refresh=service, uninstall=inputs, updates=updates)
    return app, service


def _catalog_cursor(app: UnifiedApp, tool_id: str) -> None:
    table = app.catalog.query_one(DataTable[Any])
    table.move_cursor(row=table.get_row_index(tool_id))


async def test_an_update_holds_the_mutation_lock(tmp_path: Path):
    updates = _HeldUpdates()
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _update_app(tmp_path, updates, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            _catalog_cursor(app, "rg")
            await pilot.press("u")
            await wait_until(pilot, updates.started.is_set)
            assert app.mutation_in_flight
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "fd")
            status = app.view("uninstall").status
            assert (status.text, status.severity) == (_UPDATE_REFUSAL, Severity.WARN)
            assert remover.calls == []
            updates.release.set()
            await settle(app, pilot)
            assert not app.mutation_in_flight
        finally:
            updates.release.set()


@pytest.mark.parametrize("case", ["outdated", "pending", "current", "broken", "unknown_owner"])
async def test_u_is_refused_during_a_removal(tmp_path: Path, case: str):
    updates = _HeldUpdates()
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, service = _update_app(
        tmp_path, updates, remover, "outdated" if case == "pending" else case
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover, "fd")
            await app.show_view("system")
            _catalog_cursor(app, "fd" if case == "pending" else "rg")
            before = service.passes
            await pilot.press("u")
            await wait_until(pilot, lambda: service.passes == before + 1)
            await pilot.pause()
            assert service.passes == before + 1
            status = app.catalog.status
            assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
            assert not updates.started.is_set()
            assert updates.targets == []
            remover.release.set()
            await settle(app, pilot)
        finally:
            remover.release.set()


async def test_the_lock_is_released_when_the_update_crashes(tmp_path: Path):
    updates = ScriptedUpdates({"rg": RuntimeError("boom")})
    app, _service = _update_app(tmp_path, updates, HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        _catalog_cursor(app, "rg")
        await pilot.press("u")
        await settle(app, pilot)
        assert not app.mutation_in_flight
        await pilot.press("u")
        await settle(app, pilot)
        assert len(updates.targets) == 2


# -- 21-15: the job toggle and the on-by-default daemon hold the same lock --

_TOGGLE_REFUSAL = "A policy toggle is running; wait for it to finish. Navigation still works."
_DAEMON_REFUSAL = "A daemon apply is running; wait for it to finish. Navigation still works."


def _policy_result() -> PolicyResult:
    return PolicyResult(layers=(PolicyLayer("Job", "registered"),), reload_hint=None, warning=None)


def _policy(
    tmp_path: Path,
    policy_id: str,
    *,
    active: bool = False,
    apply: Callable[[], PolicyResult] = _policy_result,
    background: bool = False,
    set_schedule: Callable[[int, int], PolicyResult] | None = None,
) -> Policy:
    return Policy(
        id=policy_id,
        label=policy_id,
        description="",
        active=active,
        apply=apply,
        remove=_policy_result,
        log_path=tmp_path / f"{policy_id}.log" if background else None,
        set_schedule=set_schedule,
    )


def _policy_app(
    tmp_path: Path,
    policies: list[Policy],
    remover: HeldRemover,
    *,
    daemon_default: Callable[[], bool] | None = None,
    daemon_default_policy_id: str | None = None,
    set_link_mode: Callable[[str], None] | None = None,
    tweak_ids: Callable[[], tuple[str, ...]] = lambda: (),
    states: Sequence[Any] | None = None,
    app_cls: type[UnifiedApp] = UnifiedApp,
    fix: Callable[[], None] = lambda: None,
    node_globals: Callable[[], NodeGlobalsReport] | None = None,
    reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
) -> tuple[UnifiedApp, FrozenStateService]:
    rg, fd = _tool("rg"), _tool("fd")
    service = frozen_service(tmp_path)
    service.publish(
        states if states is not None else [removable_state(fd, [tmp_path / "fd"]), absent_state(rg)]
    )
    app = app_cls(
        [rg, fd],
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({"pip": False, "npm": False}, None),
        fix_preview="preview",
        fix=fix,
        node_globals=node_globals,
        reinstall_globals=reinstall_globals,
        uninstall=UninstallInputs(
            ban_names=lambda: [],
            has_path_block=lambda: False,
            remove=remover,
            tweak_ids=tweak_ids,
        ),
        policies=PolicyInputs(
            policies=policies, link_mode=lambda: "centralized", set_link_mode=set_link_mode
        ),
        initial_view="policies",
        version_refresh=service,
        daemon_default=daemon_default,
        daemon_default_policy_id=daemon_default_policy_id,
    )
    return app, service


def _policy_cursor(app: UnifiedApp, policy_id: str) -> None:
    table = app.view("policies").query_one(DataTable[Any])
    table.move_cursor(row=table.get_row_index(policy_id))


def _held_daemon_default(release: threading.Event) -> Callable[[], bool]:
    def apply() -> bool:
        if not release.wait(timeout=10):
            raise TimeoutError("the daemon default was never released")
        return True

    return apply


async def test_a_background_job_toggle_holds_the_lock(tmp_path: Path):
    release = threading.Event()

    def held_apply() -> PolicyResult:
        if not release.wait(timeout=10):
            raise TimeoutError("the toggle was never released")
        return _policy_result()

    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _policy_app(
        tmp_path, [_policy(tmp_path, "job", apply=held_apply, background=True)], remover
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await pilot.press("space")
            assert app.mutation_in_flight
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "fd")
            status = app.view("uninstall").status
            assert (status.text, status.severity) == (_TOGGLE_REFUSAL, Severity.WARN)
            assert remover.calls == []
            release.set()
            await settle(app, pilot)
            assert not app.mutation_in_flight
            assert app.view("policies").status.text.startswith("job enabled.")
        finally:
            release.set()


async def test_the_daemon_default_holds_the_lock_from_construction(tmp_path: Path):
    release = threading.Event()
    app, _service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "daemon")],
        HeldRemover(),
        daemon_default=_held_daemon_default(release),
        daemon_default_policy_id="daemon",
    )
    assert app.mutation_in_flight
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await pilot.pause()
            assert app.mutation_in_flight
            release.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
        finally:
            release.set()


async def test_any_toggle_is_refused_while_the_daemon_default_applies(tmp_path: Path):
    release = threading.Event()
    applied: list[str] = []

    def other_apply() -> PolicyResult:
        applied.append("other")
        return _policy_result()

    app, _service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "daemon"), _policy(tmp_path, "other", apply=other_apply)],
        HeldRemover(),
        daemon_default=_held_daemon_default(release),
        daemon_default_policy_id="daemon",
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await pilot.pause()
            _policy_cursor(app, "other")
            await pilot.press("space")
            status = app.view("policies").status
            assert (status.text, status.severity) == (_DAEMON_REFUSAL, Severity.WARN)
            assert applied == []
            release.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
        finally:
            release.set()


async def test_a_daemon_default_without_a_policy_id_releases_the_lock(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("fd",)))
    remover.release.set()
    app, _service = _policy_app(
        tmp_path, [_policy(tmp_path, "job")], remover, daemon_default=lambda: True
    )
    assert app.mutation_in_flight
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert not app.mutation_in_flight
        await app.show_view("uninstall")
        await _confirm_removal(app, pilot, "fd")
        await settle(app, pilot)
        assert len(remover.calls) == 1


async def test_t_and_m_are_refused_at_their_mutation_point(tmp_path: Path):
    scheduled: list[tuple[int, int]] = []
    modes: list[str] = []

    def set_schedule(hour: int, minute: int) -> PolicyResult:
        scheduled.append((hour, minute))
        return _policy_result()

    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "job", active=True, set_schedule=set_schedule)],
        remover,
        set_link_mode=modes.append,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "fd")
            await wait_until(pilot, remover.started.is_set)
            await app.show_view("policies")
            status = app.view("policies").status
            await pilot.press("t")
            assert isinstance(app.screen, TimePickerScreen)
            await pilot.press("down", "down", "down", "enter")
            assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
            assert scheduled == []
            status.clear()
            await pilot.press("m")
            assert isinstance(app.screen, LinkModeScreen)
            await pilot.press("down", "enter")
            assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
            assert modes == []
        finally:
            remover.release.set()


async def test_the_daemon_default_apply_repaints_a_visible_uninstall(tmp_path: Path):
    release = threading.Event()
    tweaks: list[str] = []

    def daemon_default() -> bool:
        if not release.wait(timeout=10):
            raise TimeoutError("the daemon default was never released")
        tweaks.append("daemon:prune-tmp-linux")
        return True

    states = [absent_state(_tool("rg")), absent_state(_tool("fd"))]
    app, service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "job")],
        HeldRemover(),
        daemon_default=daemon_default,
        tweak_ids=lambda: tuple(tweaks),
        states=states,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, lambda: service.passes == 1)
            await app.show_view("uninstall")
            screen = app.view("uninstall")
            table = screen.query_one(DataTable[Any])
            assert "#tweaks" not in [row.value for row in table.rows]
            assert (screen.status.text, screen.status.severity) == (
                "Nothing to uninstall.",
                Severity.OK,
            )
            assert app.mutation_in_flight
            before = service.passes
            release.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
            await settle(app, pilot)
            assert app.screen is screen
            cells = " ".join(str(cell) for cell in table.get_row("#tweaks"))
            assert "shell tweaks + background jobs" in cells
            assert "daemon:prune-tmp-linux" in cells
            assert service.passes == before
            assert screen.status.text == ""
        finally:
            release.set()


# -- 21-16: every mutating key checks the lock, navigation never does --


class _DecidedApp(UnifiedApp):
    """Records the tier `enter` hand-off instead of starting an install."""

    def __init__(self, *args: Any, calls: list[str], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._calls = calls

    def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
        del message
        self._calls.append("decided")


def _managed_report() -> NodeGlobalsReport:
    return NodeGlobalsReport(entries=(), missing=(), managed=("mmdc",))


def _tag(calls: list[str], tag: str) -> Callable[[], PolicyResult]:
    def apply() -> PolicyResult:
        calls.append(tag)
        return _policy_result()

    return apply


def _matrix_app(
    tmp_path: Path, remover: HeldRemover, calls: list[str]
) -> tuple[UnifiedApp, FrozenStateService]:
    def schedule(hour: int, minute: int) -> PolicyResult:
        del hour, minute
        calls.append("schedule")
        return _policy_result()

    def reinstall(packages: Sequence[str]) -> tuple[str, ...]:
        del packages
        calls.append("reinstall")
        return ()

    class _App(_DecidedApp):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, calls=calls, **kwargs)

    return _policy_app(
        tmp_path,
        [
            _policy(tmp_path, "plain", apply=_tag(calls, "plain")),
            _policy(tmp_path, "job", apply=_tag(calls, "job"), background=True),
            _policy(tmp_path, "sched", active=True, set_schedule=schedule),
        ],
        remover,
        set_link_mode=lambda mode: calls.append("mode"),
        app_cls=_App,
        fix=lambda: calls.append("fix"),
        node_globals=_managed_report,
        reinstall_globals=reinstall,
    )


async def _open_view(app: UnifiedApp, pilot: Any, name: str) -> None:
    await app.show_view(name)
    if name == "doctor":
        doctor = cast(Any, app.view("doctor"))
        await wait_until(pilot, lambda: not doctor.globals_auditing)
    await pilot.pause()


async def _press_tier_enter(app: UnifiedApp, pilot: Any, again: bool) -> None:
    await _open_view(app, pilot, "system")
    _catalog_cursor(app, "rg")
    # space marks rg; the refused first enter leaves the mark, so a second space would clear it
    await pilot.press("enter" if again else "space", *([] if again else ["enter"]))


async def _press_doctor(key: str, app: UnifiedApp, pilot: Any, _again: bool) -> None:
    await _open_view(app, pilot, "doctor")
    await pilot.press(key)


async def _press_policy(policy_id: str, app: UnifiedApp, pilot: Any, _again: bool) -> None:
    await _open_view(app, pilot, "policies")
    _policy_cursor(app, policy_id)
    await pilot.press("space")


async def _press_t(app: UnifiedApp, pilot: Any, _again: bool) -> None:
    await _open_view(app, pilot, "policies")
    _policy_cursor(app, "sched")
    await pilot.press("t", "down", "down", "down", "enter")


async def _press_m(app: UnifiedApp, pilot: Any, _again: bool) -> None:
    await _open_view(app, pilot, "policies")
    await pilot.press("m", "down", "enter")


_MATRIX: dict[str, tuple[str, str, Callable[[UnifiedApp, Any, bool], Any]]] = {
    "tier_enter": ("system", "decided", _press_tier_enter),
    "doctor_enter": ("doctor", "fix", lambda a, p, n: _press_doctor("enter", a, p, n)),
    "doctor_r": ("doctor", "reinstall", lambda a, p, n: _press_doctor("r", a, p, n)),
    "policy_plain": ("policies", "plain", lambda a, p, n: _press_policy("plain", a, p, n)),
    "policy_job": ("policies", "job", lambda a, p, n: _press_policy("job", a, p, n)),
    "t": ("policies", "schedule", _press_t),
    "m": ("policies", "mode", _press_m),
}


@pytest.mark.parametrize("case", list(_MATRIX))
async def test_every_mutating_key_is_refused_during_a_removal(tmp_path: Path, case: str):
    view, tag, press = _MATRIX[case]
    calls: list[str] = []
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, service = _matrix_app(tmp_path, remover, calls)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover, "fd")
            before = service.passes
            await press(app, pilot, False)
            await wait_until(pilot, lambda: service.passes == before + 1)
            await pilot.pause()
            assert service.passes == before + 1
            status = app.view(view).status
            assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
            assert calls == []
            remover.release.set()
            await settle(app, pilot)
            status.clear()
            await press(app, pilot, True)
            await settle(app, pilot)
            assert calls == [tag]
        finally:
            remover.release.set()


async def test_navigation_works_during_a_removal(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _matrix_app(tmp_path, remover, [])
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover, "fd")
            for key, name in zip("123456", VIEW_NAMES, strict=True):
                await pilot.press(key)
                await wait_until(pilot, lambda name=name: app.current_view == name)
            await pilot.press("escape")
            await wait_until(pilot, lambda: app.current_view == "system")
            await pilot.press("ctrl+p")
            assert isinstance(app.screen, NavScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is app.view("system")
            for name in VIEW_NAMES:
                assert app.view(name).status.text != _REFUSAL
        finally:
            remover.release.set()
