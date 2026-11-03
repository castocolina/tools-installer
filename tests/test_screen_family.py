"""Screen-family lifecycle pilots: launch, the one show_view order, status lifecycle."""

import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import pytest
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from installer import receipts
from installer import uninstall as uninstall_module
from installer.app import UninstallDecision
from installer.catalog_tui import CatalogScreen
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.engine import InstallOutcome
from installer.enums import MutationHolder, Severity
from installer.execute_screen import ExecuteInputs, ExecuteScreen
from installer.model import Method, Tool
from installer.ownership import ManagerInventory, ManagerOwnership, OwnershipCandidate
from installer.platform import Platform
from installer.pnpm_globals import PNPM_SPLIT_GROUP, NodeGlobal, NodeGlobalsReport
from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.session import Disposition, PlanRow, RowOutcome
from installer.systemd_daemon import DaemonState, TimerStateCache
from installer.ui_common import AppScreen
from installer.uninstall import SweepResult, plan_removal, remove_paths
from installer.update import UpdateOutcome
from installer.version_status import (
    BROKEN_SHIM_REASON,
    Health,
    VersionRefreshService,
    VersionStatus,
)
from installer.wizard_app import (
    DaemonDefaultApplied,
    DiskPressureProbed,
    DoctorScreen,
    GlobalsReinstalled,
    JobStatesRead,
    LinkModeScreen,
    MutationLock,
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
    empty_inventory,
    frozen_service,
    held_service,
    offline_service,
    pass_state,
    plan_state,
    presence_service,
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
    execute: ExecuteInputs | None = None,
    node_globals: Callable[[], NodeGlobalsReport] | None = None,
    guard_state: Callable[[], tuple[dict[str, bool], str | None]] | None = None,
    fix_preview: str | Callable[[], str] = "preview",
    policies: PolicyInputs | None = None,
    fix: Callable[[], None] = lambda: None,
    reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
    prompt_link_mode: bool = False,
    daemon_default: Callable[[], bool] | None = None,
) -> UnifiedApp:
    return app_cls(
        list(tools) if tools is not None else [_tool("rg"), _tool("fd")],
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=guard_state or (lambda: ({"pip": False, "npm": False}, None)),
        fix_preview=fix_preview,
        fix=fix,
        node_globals=node_globals,
        reinstall_globals=reinstall_globals,
        uninstall=uninstall
        or UninstallInputs(
            ban_names=lambda: [],
            has_path_block=has_path_block,
            remove=lambda _decision: SweepResult(),
            tweak_ids=lambda: (),
        ),
        policies=policies or PolicyInputs(policies=[]),
        initial_view=initial_view,
        startup_warning=startup_warning,
        version_refresh=version_refresh,
        updates=updates,
        execute=execute,
        prompt_link_mode=prompt_link_mode,
        daemon_default=daemon_default,
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


def test_an_unreleased_held_refresh_fails_fast(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [], release_timeout=0.05)
    errors: list[TimeoutError] = []

    def run() -> None:
        try:
            service.refresh([])
        except TimeoutError as error:
            errors.append(error)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=2)
    still_waiting = worker.is_alive()
    service.release.set()
    assert not still_waiting
    assert [str(error) for error in errors] == ["HeldRefreshService was never released"]


async def test_launch_pass_renders_the_visible_tier(tmp_path: Path):
    rg = _tool("rg")
    service = HeldRefreshService(tmp_path, [])
    service.pending = (pass_state(rg, platform=service.platform, present=True),)
    app = _family_app(version_refresh=service)
    try:
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert _health(app, "rg") == "…"
            service.release.set()
            await settle(app, pilot)
            assert _health(app, "rg") == "✓"
            assert service.calls == [frozenset({"rg", "fd"})]
    finally:
        service.release.set()


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


async def test_an_unexpected_pass_failure_writes_the_retry_copy(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [], raising=RuntimeError("boom\nmore"))
    service.release.set()
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert app.catalog.status_text == (
            "tool state check failed: boom — the next change retries it"
        )
        assert app.catalog.status.severity is Severity.WARN


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
    try:
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
    finally:
        service.release.set()


async def test_a_queued_pass_does_not_start_once_quit_began(tmp_path: Path):
    service = HeldRefreshService(tmp_path, [])
    app = _family_app(version_refresh=service)
    try:
        async with app.run_test(size=(120, 30)) as pilot:
            await wait_until(pilot, lambda: len(service.calls) == 1)
            app.request_refresh()
            got: list[str | None] = []
            app.await_publication(got.append)
            # A quit during a removal sets this, then waits for the removal.
            app.quitting = True
            service.release.set()
            await settle(app, pilot)
            assert len(service.calls) == 1
            assert got == [None]
    finally:
        service.release.set()


class _Covering(ModalScreen[None]):
    """A minimal modal standing in for ConfirmUninstall, ExecuteScreen or the palette."""


async def test_publish_under_a_modal_renders_when_it_closes(
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
        # The view the modal revealed renders the published state (C-08).
        assert renders == ["render"]
        assert _health(app, "rg") == "✓"


async def test_closing_the_palette_keeps_selection_and_status(tmp_path: Path):
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
        await pilot.press("ctrl+p")
        assert isinstance(app.screen, NavScreen)
        service.queued = (pass_state(fd, platform=service.platform, present=True),)
        app.request_refresh()
        await settle(app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is app.catalog
        assert _health(app, "fd") == "✓"
        assert app.catalog.query_one(DataTable[Any]).cursor_row == row
        assert set(app.catalog.selected) == selected
        assert app.catalog.status_text == "kept"


async def test_entering_a_view_renders_it_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = frozen_service(tmp_path)
    app = _family_app(version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        renders: list[str] = []
        target = app.view("user")
        render = target.state_refreshed

        def spy() -> None:
            renders.append("render")
            render()

        monkeypatch.setattr(target, "state_refreshed", spy)
        await app.show_view("user")
        await settle(app, pilot)
        assert renders == ["render"]


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


async def test_a_removed_tool_leaves_the_tier_selection(tmp_path: Path):
    """C-16: a tool staged on a tier and then removed on Uninstall is no
    longer staged; the tier's next enter does not offer to install it."""
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, service = _removal_app(tmp_path, remover)
    remover.release.set()
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        _catalog_cursor(app, "yq")
        await pilot.press("space")
        assert app.catalog.selected == {"yq"}
        await app.show_view("uninstall")
        service.queued = (absent_state(_tool("yq")),)
        await _confirm_removal(app, pilot, "yq")
        await settle(app, pilot)
        assert app.view("uninstall").status.text.startswith("1 removed")
        assert app.catalog.selected == set()


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


async def test_uninstall_enter_is_refused_before_the_confirm_modal(tmp_path: Path):
    """C-17: while a removal runs, enter on Uninstall refuses at once on the
    view; no confirm modal opens first."""
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover)
            table = app.view("uninstall").query_one(DataTable[Any])
            table.move_cursor(row=table.get_row_index("fd"))
            await pilot.press("space")
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is app.view("uninstall")
            status = app.view("uninstall").status
            assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
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
            # One enter: the refusal comes before the confirm modal (C-17).
            table = app.view("uninstall").query_one(DataTable[Any])
            table.move_cursor(row=table.get_row_index("fd"))
            await pilot.press("space", "enter")
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


async def test_the_state_line_does_not_replace_a_removal_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    unsaved = "version cache not saved: read-only"
    monkeypatch.setattr(FrozenStateService, "warning", property(lambda _self: unsaved))
    remover = HeldRemover(
        SweepResult(removed=("yq",), remove_failed=(("fd", "permission denied"),))
    )
    app, service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _fail_fd_and_remove_yq(app, pilot, remover, service)
            screen = _uninstall_screen(app)
            assert screen.status.text.splitlines()[:2] == ["1 removed, 1 remove failed", _FIX_LINE]
            assert screen.status.severity is Severity.ERROR
            # The app's line waits for the next entry instead.
            await app.show_view("system")
            assert app.catalog.status_text.startswith(unsaved)
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


async def test_ctrl_q_during_a_removal_waits_like_q(tmp_path: Path):
    """RR-01: Textual's inherited ctrl+q goes through the same quit path as q,
    so it never abandons the daemon delete thread mid-removal."""
    app, _extra_passes, calls = await _quit_during_a_removal(tmp_path, "ctrl+q")
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


class _ExitSpyApp(UnifiedApp):
    """Records the message each exit carries (printed once the app has stopped)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.exit_messages: list[object] = []

    def exit(
        self, result: list[str] | None = None, return_code: int = 0, message: Any = None
    ) -> None:
        self.exit_messages.append(message)
        super().exit(result, return_code, message)


async def test_a_second_ctrl_c_during_a_removal_exits_at_once(tmp_path: Path):
    """C-26 (D-10 amended): the first ctrl+c waits; a second one exits without
    waiting for the remover and warns that the removal may be partial."""
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _removal_app(tmp_path, remover, app_cls=_ExitSpyApp)
    assert isinstance(app, _ExitSpyApp)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover)
            await pilot.press("ctrl+c")
            status = app.view("uninstall").status
            await wait_until(pilot, lambda: status.text == _WAITING)
            assert app.is_running
            await pilot.press("ctrl+c")
            await wait_until(pilot, lambda: not app.is_running)
            assert not remover.release.is_set()
        finally:
            remover.release.set()
    # run_test exits once more on teardown; the forced exit is the first.
    assert app.exit_messages[0] == "Quit before the removal finished; some files may remain."


async def test_a_second_q_during_a_removal_still_waits(tmp_path: Path):
    """Only ctrl+c cuts the wait; q stays the soft quit."""
    remover = HeldRemover(SweepResult(removed=("yq",)))
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover)
            await pilot.press("q")
            status = app.view("uninstall").status
            await wait_until(pilot, lambda: status.text == _WAITING)
            await pilot.press("q")
            await pilot.pause()
            assert app.is_running
            remover.release.set()
            await wait_until(pilot, lambda: not app.is_running)
        finally:
            remover.release.set()
    assert len(remover.calls) == 1


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
    service: FrozenStateService | None = None,
) -> tuple[UnifiedApp, FrozenStateService]:
    rg, fd = _tool("rg"), _tool("fd")
    service = service or frozen_service(tmp_path)
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
            # C-28: the result lands on the view the user is looking at.
            assert app.view("uninstall").status.text.startswith("job enabled.")
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


async def test_late_doctor_and_daemon_results_render_nothing_during_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The 765c0e5 shape: run_test's teardown stops the app before it prunes the
    screens, so a worker result that lands in between finds widgets gone."""
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "job")],
        remover,
        daemon_default=lambda: True,
        daemon_default_policy_id="job",
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        doctor = app.view("doctor")
        assert isinstance(doctor, DoctorScreen)
        policies = app.view("policies")
        await doctor.query_one("#doctor-body").remove()
        await policies.query_one(DataTable[Any]).remove()
        with monkeypatch.context() as patch:
            patch.setattr(UnifiedApp, "is_running", property(lambda _self: False))
            doctor.on_globals_reinstalled(GlobalsReinstalled(None))
            doctor.on_disk_pressure_probed(DiskPressureProbed())
            app.on_daemon_default_applied(DaemonDefaultApplied("job", True, True))


async def test_t_and_m_are_refused_at_their_mutation_point(tmp_path: Path):
    """A mutation that starts while a picker is open is refused at the pick."""
    scheduled: list[tuple[int, int]] = []
    modes: list[str] = []

    def set_schedule(hour: int, minute: int) -> PolicyResult:
        scheduled.append((hour, minute))
        return _policy_result()

    app, _service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "job", active=True, set_schedule=set_schedule)],
        HeldRemover(),
        set_link_mode=modes.append,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        status = app.view("policies").status
        await pilot.press("t")
        assert isinstance(app.screen, TimePickerScreen)
        app.begin_mutation(MutationHolder.REMOVAL)
        await pilot.press("down", "down", "down", "enter")
        assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
        assert scheduled == []
        app.end_mutation()
        status.clear()
        await pilot.press("m")
        assert isinstance(app.screen, LinkModeScreen)
        app.begin_mutation(MutationHolder.REMOVAL)
        await pilot.press("down", "enter")
        assert (status.text, status.severity) == (_REFUSAL, Severity.WARN)
        assert modes == []
        app.end_mutation()


@pytest.mark.parametrize("key", ["t", "m"])
async def test_t_and_m_are_refused_before_their_picker(tmp_path: Path, key: str):
    """C-17: while a mutation runs, t and m refuse at once on Policies; no
    picker opens first."""
    app, _service = _policy_app(
        tmp_path,
        [_policy(tmp_path, "job", active=True, set_schedule=lambda _h, _m: _policy_result())],
        HeldRemover(),
        set_link_mode=lambda _mode: None,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.begin_mutation(MutationHolder.UPDATE)
        await pilot.press(key)
        await pilot.pause()
        assert app.screen is app.view("policies")
        status = app.view("policies").status
        assert (status.text, status.severity) == (_UPDATE_REFUSAL, Severity.WARN)
        app.end_mutation()


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


# -- 21-16: the pnpm reinstall and the install run hold the lock --

_REINSTALL_REFUSAL = "A pnpm reinstall is running; wait for it to finish. Navigation still works."
_INSTALL_REFUSAL = "An install run is running; wait for it to finish. Navigation still works."


def _reinstall_app(
    tmp_path: Path,
    remover: HeldRemover,
    reinstall: Callable[[Sequence[str]], tuple[str, ...]],
    *,
    report: Callable[[], NodeGlobalsReport] = _managed_report,
    fix: Callable[[], None] = lambda: None,
) -> tuple[UnifiedApp, FrozenStateService]:
    return _policy_app(
        tmp_path, [], remover, node_globals=report, reinstall_globals=reinstall, fix=fix
    )


def _held_reinstall(
    started: threading.Event, release: threading.Event
) -> Callable[[Sequence[str]], tuple[str, ...]]:
    def reinstall(packages: Sequence[str]) -> tuple[str, ...]:
        del packages
        started.set()
        if not release.wait(timeout=10):
            raise TimeoutError("the reinstall was never released")
        return ()

    return reinstall


async def test_a_pnpm_reinstall_holds_the_lock(tmp_path: Path):
    started, release = threading.Event(), threading.Event()
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _reinstall_app(tmp_path, remover, _held_reinstall(started, release))
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _open_view(app, pilot, "doctor")
            await pilot.press("r")
            await wait_until(pilot, started.is_set)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "fd")
            status = app.view("uninstall").status
            assert (status.text, status.severity) == (_REINSTALL_REFUSAL, Severity.WARN)
            assert remover.calls == []
            release.set()
            await settle(app, pilot)
            assert not app.mutation_in_flight
        finally:
            release.set()


async def test_the_lock_is_released_when_the_reinstall_crashes(tmp_path: Path):
    def reinstall(packages: Sequence[str]) -> tuple[str, ...]:
        raise RuntimeError("boom")

    app, _service = _reinstall_app(tmp_path, HeldRemover(), reinstall)
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        await pilot.press("r")
        await settle(app, pilot)
        assert not app.mutation_in_flight
        assert cast(Any, app.view("doctor")).globals_error == "the reinstall did not complete"


async def test_an_install_run_holds_the_lock(tmp_path: Path):
    started, release = threading.Event(), threading.Event()
    rg = _tool("rg")
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)

    def install(tool: Tool, *_args: Any, **_kwargs: Any) -> InstallOutcome:
        started.set()
        assert release.wait(timeout=10)
        return InstallOutcome(tool.id, "installed")

    service = presence_service([rg], platform=platform)
    inputs = ExecuteInputs(
        catalog=[rg],
        platform=platform,
        wire_path=lambda: "PATH wired",
        verify=lambda: "PATH verified",
        install=install,
        version_refresh=service,
    )
    app = _family_app(tools=[rg], version_refresh=service, execute=inputs)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            _catalog_cursor(app, "rg")
            await pilot.press("space", "enter")
            await wait_until(pilot, lambda: isinstance(app.screen, ExecuteScreen))
            await pilot.press("enter")
            await wait_until(pilot, started.is_set)
            assert app.mutation_in_flight
            assert app.run_in_flight
            assert app.refuse_if_mutating(app.catalog)
            assert app.catalog.status.text == _INSTALL_REFUSAL
            release.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
            assert not app.run_in_flight
        finally:
            release.set()


_NOUNS = {
    MutationHolder.REMOVAL: _REFUSAL,
    MutationHolder.INSTALL_RUN: _INSTALL_REFUSAL,
    MutationHolder.UPDATE: _UPDATE_REFUSAL,
    MutationHolder.GLOBALS_REINSTALL: _REINSTALL_REFUSAL,
    MutationHolder.DAEMON_DEFAULT: _DAEMON_REFUSAL,
    MutationHolder.POLICY_TOGGLE: _TOGGLE_REFUSAL,
}


def test_a_held_lock_is_never_taken_twice():
    """C-30: a second begin_mutation while the lock is held fails loudly; it
    never overwrites the holder, so one end_mutation cannot release both."""
    lock = MutationLock()
    lock.begin_mutation(MutationHolder.UPDATE)
    with pytest.raises(RuntimeError, match="An update"):
        lock.begin_mutation(MutationHolder.REMOVAL)
    assert lock.mutation_in_flight


@pytest.mark.parametrize("holder", list(MutationHolder), ids=lambda holder: holder.name)
async def test_each_holder_names_itself_in_the_refusal(tmp_path: Path, holder: MutationHolder):
    assert set(_NOUNS) == set(MutationHolder)
    app, _service = _reinstall_app(tmp_path, HeldRemover(), lambda _packages: ())
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        app.begin_mutation(holder)
        await pilot.press("enter")
        status = app.view("doctor").status
        assert (status.text, status.severity) == (_NOUNS[holder], Severity.WARN)
        app.end_mutation()


_STILL_CHECKING = "Still checking pnpm's global set — press r again in a moment."
_UNREADABLE = "pnpm's global set could not be read — install or repair pnpm, then retry."
_NOTHING = "Nothing to reinstall — pnpm manages no globals here."


@pytest.mark.parametrize(
    "case",
    [
        "apply_after_applied",
        "reinstall_after_done",
        "reinstall_while_running",
        "reinstall_while_auditing",
        "reinstall_unknown_report",
        "reinstall_nothing_managed",
    ],
)
async def test_doctor_early_returns_end_with_a_pinned_pass_count(tmp_path: Path, case: str):
    fixes: list[str] = []
    reinstalls: list[str] = []
    started, release, gate = threading.Event(), threading.Event(), threading.Event()
    gate.set()
    report = {
        "reinstall_unknown_report": NodeGlobalsReport(
            entries=(), missing=(), managed=(), known=False
        ),
        "reinstall_nothing_managed": NodeGlobalsReport(entries=(), missing=(), managed=()),
    }.get(case, _managed_report())

    def audit() -> NodeGlobalsReport:
        assert gate.wait(timeout=10)
        return report

    def reinstall(packages: Sequence[str]) -> tuple[str, ...]:
        reinstalls.append("reinstall")
        if case == "reinstall_while_running":
            return _held_reinstall(started, release)(packages)
        return ()

    app, service = _reinstall_app(
        tmp_path, HeldRemover(), reinstall, report=audit, fix=lambda: fixes.append("fix")
    )
    if case == "reinstall_while_auditing":
        gate.clear()
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            doctor = cast(Any, app.view("doctor"))
            if case == "reinstall_while_auditing":
                await app.show_view("doctor")
            else:
                await _open_view(app, pilot, "doctor")
            held: str | None = None
            if case == "apply_after_applied":
                await pilot.press("enter")
                await settle(app, pilot)
            elif case == "reinstall_after_done":
                await pilot.press("r")
                await settle(app, pilot)
                assert doctor.globals_done
            elif case == "reinstall_while_running":
                await pilot.press("r")
                await wait_until(pilot, started.is_set)
                held = _REINSTALL_REFUSAL
            elif case == "reinstall_while_auditing":
                held = _STILL_CHECKING
            elif case == "reinstall_unknown_report":
                gate.clear()  # the re-audit the unknown answer starts stays held
                held = _UNREADABLE
            else:
                held = _NOTHING
            await pilot.pause()
            before = service.passes
            await pilot.press("enter" if case == "apply_after_applied" else "r")
            if held is None:
                await settle(app, pilot)
                assert service.passes == before
                assert fixes == (["fix"] if case == "apply_after_applied" else [])
                assert reinstalls == (["reinstall"] if case == "reinstall_after_done" else [])
                return
            await wait_until(pilot, lambda: service.passes == before + 1)
            await pilot.pause()
            assert service.passes == before + 1
            text = doctor.status.text if held == _REINSTALL_REFUSAL else doctor.globals_note
            assert text == held
        finally:
            gate.set()
            release.set()
        await settle(app, pilot)


# -- 21-18: the systemd-backed state is read on a worker, never on the event loop --


def _job_policy(
    tmp_path: Path, is_active: Callable[[], bool], owned: Callable[[], bool] | None = None
) -> Policy:
    cache = TimerStateCache(lambda: DaemonState.INACTIVE)
    base = _policy(tmp_path, "jobstate")
    return replace(base, is_active=is_active, owned=owned, state_cache=cache)


def _state_text(app: UnifiedApp, policy_id: str) -> str:
    return app.view("policies").query_one(DataTable[Any]).get_cell(policy_id, "state").plain


async def test_the_job_state_is_read_off_the_event_loop(tmp_path: Path):
    threads: list[threading.Thread] = []

    def is_active() -> bool:
        threads.append(threading.current_thread())
        return True

    def owned() -> bool:
        threads.append(threading.current_thread())
        return True

    app, _service = _policy_app(tmp_path, [_job_policy(tmp_path, is_active, owned)], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert len(threads) >= 2
        assert threading.main_thread() not in threads
        assert _state_text(app, "jobstate") == "● [on]"


async def test_an_unreadable_job_state_shows_the_error(tmp_path: Path):
    def is_active() -> bool:
        raise OSError("systemd user manager not reachable")

    app, _service = _policy_app(tmp_path, [_job_policy(tmp_path, is_active)], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        status = app.view("policies").status
        assert _state_text(app, "jobstate") == ""
        assert (status.text, status.severity) == (
            "Could not read the policy state: systemd user manager not reachable.",
            Severity.ERROR,
        )


async def test_an_undecodable_policy_read_shows_the_error(tmp_path: Path):
    reads = {"undecodable": False}

    def is_active() -> bool:
        if reads["undecodable"]:  # a managed rc file rewritten with invalid UTF-8
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return True

    policy = replace(_policy(tmp_path, "tweak"), is_active=is_active)
    app, _service = _policy_app(tmp_path, [policy], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        reads["undecodable"] = True
        await app.show_view("system")
        await app.show_view("policies")
        await settle(app, pilot)
        assert app.is_running
        status = app.view("policies").status
        assert _state_text(app, "tweak") == ""
        assert status.text.startswith("Could not read the policy state:")
        assert status.severity is Severity.ERROR


class _SpiedReads:
    """Records every JobStatesRead a PoliciesScreen posts, then forwards it."""

    def __init__(self, screen: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self.seen: list[JobStatesRead] = []
        forward = screen.post_message

        def spy(message: Any) -> bool:
            if isinstance(message, JobStatesRead):
                self.seen.append(message)
            return cast(bool, forward(message))

        monkeypatch.setattr(screen, "post_message", spy)


class _ArmedProbe:
    """is_active: the armed call holds on `release` and answers `first`; others answer `later`."""

    def __init__(self, first: bool, later: bool) -> None:
        self.first, self.later = first, later
        self.calls = 0
        self.armed = False
        self.held = threading.Event()
        self.release = threading.Event()
        self._lock = threading.Lock()

    def __call__(self) -> bool:
        with self._lock:
            hold = self.armed
            self.armed = False
            self.calls += 1
        if not hold:
            return self.later
        self.held.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("the job read was never released")
        return self.first


async def test_a_superseded_job_state_read_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    probe = _ArmedProbe(first=True, later=False)
    probe.armed = True
    app, _service = _policy_app(tmp_path, [_job_policy(tmp_path, probe)], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, probe.held.is_set)
            spy = _SpiedReads(app.view("policies"), monkeypatch)
            await app.show_view("system")
            await app.show_view("policies")
            await settle(app, pilot)
            assert _state_text(app, "jobstate") == "○ [off]"
            before = len(spy.seen)
            probe.release.set()
            await wait_until(pilot, lambda: len(spy.seen) > before)
            await pilot.pause()
            await settle(app, pilot)
            assert _state_text(app, "jobstate") == "○ [off]"
            assert app.view("policies").status.text == ""
        finally:
            probe.release.set()


async def test_a_publish_keeps_the_job_row_while_it_is_re_read(tmp_path: Path):
    """C-21: a publish re-reads the job row on the worker but keeps its last
    answer meanwhile; only an entry blanks it until the read answers."""
    probe = _ArmedProbe(first=True, later=True)
    app, service = _policy_app(tmp_path, [_job_policy(tmp_path, probe)], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            assert _state_text(app, "jobstate") == "● [on]"
            probe.armed = True
            before = service.passes
            app.request_refresh()
            await wait_until(pilot, probe.held.is_set)
            await wait_until(pilot, lambda: service.passes == before + 1)
            await pilot.pause()
            assert _state_text(app, "jobstate") == "● [on]"
            probe.release.set()
            await settle(app, pilot)
            probe.held.clear()
            probe.release.clear()
            probe.armed = True
            await app.show_view("system")
            await app.show_view("policies")
            await wait_until(pilot, probe.held.is_set)
            assert _state_text(app, "jobstate") == ""
        finally:
            probe.release.set()


# -- 21-18: a toggle ends with one pass; a mutation completion supersedes older reads --


async def test_a_toggle_requests_one_pass(tmp_path: Path):
    app, service = _policy_app(tmp_path, [_policy(tmp_path, "plain")], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        before = service.passes
        await pilot.press("space")
        await settle(app, pilot)
        assert service.passes == before + 1
        assert _state_text(app, "plain") == "● [on]"


async def test_a_job_toggle_requests_one_pass_after_it_lands(tmp_path: Path):
    release = threading.Event()

    def held_apply() -> PolicyResult:
        if not release.wait(timeout=10):
            raise TimeoutError("the toggle was never released")
        return _policy_result()

    app, service = _policy_app(
        tmp_path, [_policy(tmp_path, "job", apply=held_apply, background=True)], HeldRemover()
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            before = service.passes
            await pilot.press("space")
            await pilot.pause()
            assert app.mutation_in_flight
            assert service.passes == before
            release.set()
            await settle(app, pilot)
            assert service.passes == before + 1
        finally:
            release.set()


async def test_a_failed_toggle_still_requests_a_pass(tmp_path: Path):
    def denied() -> PolicyResult:
        raise OSError("denied")

    app, service = _policy_app(tmp_path, [_policy(tmp_path, "plain", apply=denied)], HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        before = service.passes
        await pilot.press("space")
        await settle(app, pilot)
        status = app.view("policies").status
        assert (status.text, status.severity) == (
            "Policy change failed: denied. Check permissions, then press space.",
            Severity.ERROR,
        )
        assert service.passes == before + 1


@pytest.mark.parametrize("mutation", ["toggle", "daemon_default"])
async def test_a_mutation_completion_supersedes_an_in_flight_job_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    # Reads answer OFF until the mutation lands, then ON; the armed read starts
    # before the mutation completes and answers OFF after it did.
    probe = _ArmedProbe(first=False, later=False)
    release_mutation = threading.Event()

    def mutate() -> None:
        if not release_mutation.wait(timeout=10):
            raise TimeoutError("the mutation was never released")
        probe.later = True

    def held_apply() -> PolicyResult:
        mutate()
        return _policy_result()

    def held_default() -> bool:
        mutate()
        return True

    policy = replace(
        _job_policy(tmp_path, probe), apply=held_apply, log_path=tmp_path / "jobstate.log"
    )
    kwargs: dict[str, Any] = {}
    service = held_service(tmp_path, [])
    if mutation == "daemon_default":
        kwargs = {"daemon_default": held_default, "daemon_default_policy_id": "jobstate"}
    else:
        service.release.set()
    app, _ = _policy_app(tmp_path, [policy], HeldRemover(), service=service, **kwargs)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, lambda: _state_text(app, "jobstate") == "○ [off]")
            if mutation == "toggle":
                await settle(app, pilot)
                service.release.clear()  # the toggle's follow-up pass stays unpublished
            spy = _SpiedReads(app.view("policies"), monkeypatch)
            if mutation == "toggle":
                await pilot.press("space")
                await wait_until(pilot, lambda: app.mutation_in_flight)
            probe.armed = True
            await app.show_view("system")
            await app.show_view("policies")
            await wait_until(pilot, probe.held.is_set)
            release_mutation.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
            await wait_until(pilot, lambda: _state_text(app, "jobstate") == "● [on]")
            probe.release.set()
            await wait_until(
                pilot, lambda: any(m.states == {"jobstate": (False, False)} for m in spy.seen)
            )
            await pilot.pause()
            assert _state_text(app, "jobstate") == "● [on]"
            service.release.set()
            await settle(app, pilot)
            assert _state_text(app, "jobstate") == "● [on]"
        finally:
            release_mutation.set()
            probe.release.set()
            service.release.set()


# -- Doctor joins the screen family (plan 21-19) --

_SMOKE = (
    "mmdc's command resolves on PATH, but the check the catalog declares for it "
    "fails right now: {reason}"
)


def _node_tool() -> Tool:
    return Tool(
        id="mmdc",
        name="mmdc",
        category="search",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
    )


def _audit(*unhealthy: tuple[str, str], known: bool = True) -> Callable[[], NodeGlobalsReport]:
    report = NodeGlobalsReport(
        entries=(NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),),
        missing=(),
        managed=("@mermaid-js/mermaid-cli",),
        known=known,
        unhealthy=unhealthy,
    )
    return lambda: report


def _doctor_text(app: UnifiedApp) -> Any:
    return app.view("doctor").query_one("#doctor-body", Static).render()


def _tier_marks(app: UnifiedApp, tool_id: str) -> list[str]:
    table = app.catalog.query_one(DataTable[Any])
    return [str(cell) for cell in table.get_row(tool_id)]


def _real_service(tmp_path: Path) -> VersionRefreshService:
    return offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: "1.0",
    )


def _count_passes(monkeypatch: pytest.MonkeyPatch, service: VersionRefreshService) -> list[int]:
    passes: list[int] = []
    original = service.refresh

    def counting(tools: Sequence[Tool]) -> Any:
        passes.append(1)
        return original(tools)

    monkeypatch.setattr(service, "refresh", counting)
    return passes


async def _reenter_doctor(app: UnifiedApp, pilot: Any) -> None:
    await app.show_view("system")
    await app.show_view("doctor")
    await settle(app, pilot)


async def test_a_smoke_failure_reaches_the_tier_and_doctor_through_the_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    service = _real_service(tmp_path)
    passes = _count_passes(monkeypatch, service)
    app = _family_app(
        tools=[_node_tool()], version_refresh=service, node_globals=_audit(("mmdc", "exit 1"))
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await wait_until(pilot, lambda: len(passes) == 2)
        await settle(app, pilot)
        state = service.state_of("mmdc")
        assert state is not None and state.health is Health.BROKEN
        assert f"mmdc: {_SMOKE.format(reason='exit 1')}" in str(_doctor_text(app))
        # The tier repaints on its next entry (D-06: only the visible view re-renders).
        await app.show_view("system")
        assert "!" in _tier_marks(app, "mmdc")


async def test_an_unchanged_audit_requests_no_pass(tmp_path: Path):
    service = frozen_service(tmp_path)
    app = _family_app(
        tools=[_node_tool()], version_refresh=service, node_globals=_audit(("mmdc", "exit 1"))
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert service.passes == 2
        await _reenter_doctor(app, pilot)
        await _reenter_doctor(app, pilot)
        assert service.passes == 2


async def test_a_dangling_pnpm_shim_reads_broken_in_doctor_and_on_the_tier(tmp_path: Path):
    tool = _node_tool()
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform, broken=(BROKEN_SHIM_REASON,))])
    app = _family_app(tools=[tool], version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert "!" in _tier_marks(app, "mmdc")
        assert f"mmdc: {BROKEN_SHIM_REASON}" in str(_doctor_text(app))


async def test_a_healthy_pnpm_owned_tool_prints_no_doctor_finding(tmp_path: Path):
    # C-10: owner and version notes are the detail bar's, not pnpm findings.
    tool = _node_tool()
    service = frozen_service(tmp_path)
    owned = replace(_brew_owned(tool), owner="pnpm", active_candidate="pnpm")
    state = pass_state(tool, platform=service.platform, ownership=owned)
    assert state.health is Health.OK and state.reasons
    service.publish([state])
    app = _family_app(tools=[tool], version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert "mmdc:" not in str(_doctor_text(app))


async def test_doctor_rerenders_when_a_pass_publishes(tmp_path: Path):
    tool = _node_tool()
    service = frozen_service(tmp_path)
    service.publish([pass_state(tool, platform=service.platform)])
    app = _family_app(tools=[tool], version_refresh=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert "a brand new finding" not in str(_doctor_text(app))
        service.queued = (
            pass_state(
                tool,
                platform=service.platform,
                broken=(_SMOKE.format(reason="a brand new finding"),),
            ),
        )
        app.request_refresh()
        await settle(app, pilot)
        assert app.current_view == "doctor"
        assert "fails right now: a brand new finding" in str(_doctor_text(app))


async def test_an_unreadable_audit_records_no_evidence(tmp_path: Path):
    service = frozen_service(tmp_path)
    app = _family_app(
        tools=[_node_tool()],
        version_refresh=service,
        node_globals=_audit(("mmdc", "exit 1"), known=False),
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert service.passes == 1
        # Nothing was stored, so storing something is still a change.
        assert service.record_evidence("mmdc", epoch=service.epoch, broken=("x",)) is True


async def test_an_audit_that_started_before_a_mutation_records_nothing(tmp_path: Path):
    # C-09: the audit read the machine before the mutation, so its finding is stale.
    service = _real_service(tmp_path)
    started, release = threading.Event(), threading.Event()
    report = _audit(("mmdc", "exit 1"))()

    def held() -> NodeGlobalsReport:
        started.set()
        if not release.wait(timeout=10):
            raise TimeoutError("the audit was never released")
        return report

    app = _family_app(tools=[_node_tool()], version_refresh=service, node_globals=held)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("doctor")
            await wait_until(pilot, started.is_set)
            service.invalidate(reason="mmdc reinstalled")
            release.set()
            doctor = cast(Any, app.view("doctor"))
            await wait_until(pilot, lambda: not doctor.globals_auditing)
            app.request_refresh()
            await settle(app, pilot)
            state = service.state_of("mmdc")
            assert state is not None and state.health is not Health.BROKEN
        finally:
            release.set()


async def test_an_unexpected_audit_error_does_not_kill_the_app():
    # C-13: an exception run_live does not map must not reach Textual.
    def audit() -> NodeGlobalsReport:
        raise ValueError("bad pnpm json")

    app = _family_app(tools=[_node_tool()], node_globals=audit)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert app.is_running
        assert not cast(Any, app.view("doctor")).globals_auditing


async def test_a_hostile_pnpm_reason_renders_literally(tmp_path: Path):
    service = _real_service(tmp_path)
    reason = "[red]x[/red]\x1b[31mboom"
    app = _family_app(
        tools=[_node_tool()], version_refresh=service, node_globals=_audit(("mmdc", reason))
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await wait_until(pilot, lambda: "boom" in str(_doctor_text(app)), tries=800)
        body = _doctor_text(app)
        assert "[red]x[/red]" in str(body)
        assert "\x1b" not in str(body)
        assert not any("red" in str(span.style) for span in body.spans)


_STATE_READ = "Could not read the doctor state: rc file locked."


@pytest.mark.parametrize("seam", ["guard_state", "fix_preview"])
async def test_a_failed_doctor_read_shows_the_error(seam: str):
    failing = {"on": False}

    def guard() -> tuple[dict[str, bool], str | None]:
        if seam == "guard_state" and failing["on"]:
            raise OSError("rc file locked\nsecond line")
        return {"pip": True, "npm": False}, None

    def preview() -> str:
        if seam == "fix_preview" and failing["on"]:
            raise OSError("rc file locked\nsecond line")
        return "WIRE-THE-RC-FILE"

    app = _family_app(guard_state=guard, fix_preview=preview)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        doctor = app.view("doctor")
        first = str(_doctor_text(app))
        assert "WIRE-THE-RC-FILE" in first
        assert "pip" in first
        assert doctor.status.text == ""
        failing["on"] = True
        await _reenter_doctor(app, pilot)
        second = str(_doctor_text(app))
        assert (doctor.status.text, doctor.status.severity) == (_STATE_READ, Severity.ERROR)
        if seam == "guard_state":
            assert "pip" not in second
        else:
            assert "WIRE-THE-RC-FILE" not in second
        failing["on"] = False
        await _reenter_doctor(app, pilot)
        assert doctor.status.text == ""
        assert "WIRE-THE-RC-FILE" in str(_doctor_text(app))


async def test_doctor_enter_does_not_apply_a_fix_it_could_not_preview():
    # C-11 (T-21-41): the user never saw what the fix would write.
    fixes: list[str] = []

    def preview() -> str:
        raise OSError("rc file locked\nsecond line")

    app = _family_app(fix_preview=preview, fix=lambda: fixes.append("fix"))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        await pilot.press("enter")
        await settle(app, pilot)
        doctor = app.view("doctor")
        assert fixes == []
        assert (doctor.status.text, doctor.status.severity) == (_STATE_READ, Severity.ERROR)
        assert "PATH wired." not in str(_doctor_text(app))


async def test_doctor_with_no_findings_draws_its_empty_copy(tmp_path: Path):
    tool = _node_tool()
    findings = {"on": True}
    at_risk = DiskPressure(
        home_free_percent=5.0,
        tmp_used_percent=10.0,
        daemon=DaemonState.INACTIVE,
        tmp_threshold=True,
    )
    healthy = DiskPressure(
        home_free_percent=90.0,
        tmp_used_percent=10.0,
        daemon=DaemonState.ACTIVE,
        tmp_threshold=False,
    )

    def probe(*, blocking: bool = True) -> DiskPressure:
        del blocking
        return at_risk if findings["on"] else healthy

    def guard() -> tuple[dict[str, bool], str | None]:
        warning = "pip shim is shadowed" if findings["on"] else None
        return {"pip": findings["on"], "npm": False}, warning

    def build(directory: Path) -> tuple[UnifiedApp, FrozenStateService]:
        service = frozen_service(directory)
        service.publish([pass_state(tool, platform=service.platform)])
        app = _family_app(
            tools=[tool],
            version_refresh=service,
            guard_state=guard,
            policies=PolicyInputs(policies=[], disk_pressure=probe),
        )
        return app, service

    app, service = build(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        await app.show_view("doctor")
        await settle(app, pilot)
        assert "pip shim is shadowed" in str(_doctor_text(app))
        stale = _SMOKE.format(reason="a stale finding")
        service.publish([pass_state(tool, platform=service.platform, broken=(stale,))])
        await _reenter_doctor(app, pilot)
        assert f"mmdc: {stale}" in str(_doctor_text(app))
        findings["on"] = False
        service.publish([pass_state(tool, platform=service.platform)])
        await _reenter_doctor(app, pilot)
        again = str(_doctor_text(app))
    fresh_app, _service = build(tmp_path / "fresh")
    async with fresh_app.run_test(size=(120, 40)) as pilot:
        await settle(fresh_app, pilot)
        await fresh_app.show_view("doctor")
        await settle(fresh_app, pilot)
        fresh = str(_doctor_text(fresh_app))
    assert again == fresh
    assert "pip shim is shadowed" not in again
    assert "a stale finding" not in again


# -- 21-20: Doctor drops its hidden key and republishes after its fixes --

_INVALIDATE_FAILED = "version cache invalidation failed: {error}"


def _record_invalidations(
    monkeypatch: pytest.MonkeyPatch, service: VersionRefreshService
) -> list[str]:
    reasons: list[str] = []
    original = service.invalidate

    def recording(*, reason: str) -> int:
        reasons.append(reason)
        return original(reason=reason)

    monkeypatch.setattr(service, "invalidate", recording)
    return reasons


async def _wait_for_passes(pilot: Any, service: FrozenStateService, expected: int) -> None:
    await wait_until(pilot, lambda: service.passes >= expected)
    await pilot.pause()
    assert service.passes == expected


async def test_reinstall_invalidates_and_requests_one_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    app, service = _reinstall_app(tmp_path, HeldRemover(), lambda _packages: ())
    reasons = _record_invalidations(monkeypatch, service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        await settle(app, pilot)
        before = service.passes
        await pilot.press("r")
        await settle(app, pilot)
        await _wait_for_passes(pilot, service, before + 1)
        assert reasons == ["pnpm globals reinstalled"]
        assert service.invalidations == (before,)


async def test_a_is_inert_on_doctor(tmp_path: Path):
    fixes: list[str] = []
    app, _service = _reinstall_app(
        tmp_path, HeldRemover(), lambda _packages: (), fix=lambda: fixes.append("fix")
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        await pilot.press("a")
        await settle(app, pilot)
        assert fixes == []
        assert app.view("doctor").status.text == ""


async def test_doctor_footer_lists_enter_and_r_only(tmp_path: Path):
    app, _service = _reinstall_app(tmp_path, HeldRemover(), lambda _packages: ())
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        doctor = app.view("doctor")
        shown = {
            key
            for key, active in doctor.active_bindings.items()
            if active.node is doctor and active.binding.show
        }
        assert shown == {"enter", "r"}
        assert "a" not in doctor.active_bindings


@pytest.mark.parametrize("fix_raises", [False, True], ids=["fix_ok", "fix_raises"])
async def test_doctor_fix_requests_one_pass(tmp_path: Path, fix_raises: bool):
    def fix() -> None:
        if fix_raises:
            raise OSError("rc is read-only")

    app, service = _reinstall_app(tmp_path, HeldRemover(), lambda _packages: (), fix=fix)
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        await settle(app, pilot)
        before = service.passes
        await pilot.press("enter")
        await settle(app, pilot)
        await _wait_for_passes(pilot, service, before + 1)


@pytest.mark.parametrize(
    ("error", "shown"),
    [
        (OSError("cache is read-only"), "cache is read-only"),
        (RuntimeError("cache is read-only"), "the cache invalidation did not complete"),
    ],
    ids=["mapped", "unmapped"],
)
async def test_a_failed_invalidate_after_a_reinstall_is_reported(
    tmp_path: Path, error: Exception, shown: str
):
    app, service = _reinstall_app(tmp_path, HeldRemover(), lambda _packages: ())
    service.invalidate_error = error
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        await settle(app, pilot)
        before = service.passes
        await pilot.press("r")
        await settle(app, pilot)
        await _wait_for_passes(pilot, service, before + 1)
        body = str(_doctor_text(app))
        assert "pnpm globals reinstalled." in body
        assert _INVALIDATE_FAILED.format(error=shown) in body
        assert not app.mutation_in_flight


@pytest.mark.parametrize(
    "invalidate_crashes", [False, True], ids=["invalidate_ok", "invalidate_crashes"]
)
async def test_a_crashed_reinstall_still_invalidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalidate_crashes: bool
):
    def reinstall(packages: Sequence[str]) -> tuple[str, ...]:
        raise RuntimeError("boom")

    app, service = _reinstall_app(tmp_path, HeldRemover(), reinstall)
    if invalidate_crashes:
        service.invalidate_error = RuntimeError("cache gone")
    reasons = _record_invalidations(monkeypatch, service)
    async with app.run_test(size=(120, 30)) as pilot:
        await _open_view(app, pilot, "doctor")
        await settle(app, pilot)
        before = service.passes
        await pilot.press("r")
        await settle(app, pilot)
        await _wait_for_passes(pilot, service, before + 1)
        body = str(_doctor_text(app))
        assert reasons == ["pnpm globals reinstalled"]
        assert "the reinstall did not complete" in body
        failed = _INVALIDATE_FAILED.format(error="the cache invalidation did not complete")
        assert (failed in body) is invalidate_crashes
        assert not app.mutation_in_flight


async def test_a_real_cache_write_failure_after_a_reinstall_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # The manager-only fact is pnpm's global inventory: A lists no package, B lists mmdc's.
    package = "@mermaid-js/mermaid-cli"
    answer = {"pnpm_globals": frozenset[str]()}
    reads: list[str] = []

    def inventory(**_kwargs: Any) -> ManagerInventory:
        reads.append("inventory")
        return replace(empty_inventory(), pnpm_globals=answer["pnpm_globals"])

    managed = tmp_path / ".local" / "bin"
    service = offline_service(
        tmp_path / "versions.json",
        skill_home=tmp_path,
        resolve_tag=lambda _repo: "v1",
        probe_output=lambda _argv: "1.0",
        which=lambda cmd: None if cmd == "brew" else str(managed / cmd),
        read_inventory_fn=inventory,
    )
    app = _family_app(
        tools=[_node_tool()],
        version_refresh=service,
        node_globals=_audit(),
        reinstall_globals=lambda _packages: (),
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await _open_view(app, pilot, "doctor")
        await settle(app, pilot)
        before = service.state_of("mmdc")
        assert before is not None
        launch_reads = len(reads)
        assert launch_reads >= 1
        app.request_refresh()
        await settle(app, pilot)
        assert len(reads) == launch_reads  # the saved snapshot is reused
        passes = _count_passes(monkeypatch, service)
        epoch = service.epoch
        answer["pnpm_globals"] = frozenset({package})

        def full(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("installer.version_status.save_version_cache", full)
        await pilot.press("r")
        await settle(app, pilot)
        await wait_until(pilot, lambda: len(passes) >= 1)
        await settle(app, pilot)
        body = str(_doctor_text(app))
        assert "pnpm globals reinstalled." in body
        assert _INVALIDATE_FAILED.format(error="disk full") in body
        assert service.epoch > epoch
        assert not app.mutation_in_flight
        assert len(passes) == 1
        assert len(reads) > launch_reads  # the managers were queried again
        state = service.state_of("mmdc")
        assert state is not None and state.generation == service.epoch
        assert state.ownership != before.ownership  # B, not the persisted A


def _first_run_doctor(mode: dict[str, str], setter: Callable[[str], None]) -> UnifiedApp:
    return _family_app(
        initial_view="doctor",
        prompt_link_mode=True,
        fix_preview=lambda: f"PREVIEW-{mode['v']}",
        policies=PolicyInputs(policies=[], link_mode=lambda: mode["v"], set_link_mode=setter),
    )


async def test_a_first_run_link_pick_rerenders_doctor():
    mode = {"v": "centralized"}

    def setter(value: str) -> None:
        mode["v"] = value

    app = _first_run_doctor(mode, setter)
    async with app.run_test(size=(120, 30)) as pilot:
        await wait_until(pilot, lambda: isinstance(app.screen, LinkModeScreen))
        assert "PREVIEW-centralized" in str(_doctor_text(app))
        await pilot.press("down", "down", "enter")  # pick split
        await settle(app, pilot)
        assert "PREVIEW-split" in str(_doctor_text(app))
        assert "Link mode saved: split" in app.view("doctor").status.text


async def test_a_failed_first_run_pick_keeps_the_error():
    mode = {"v": "centralized"}

    def setter(value: str) -> None:
        raise OSError("read-only")

    app = _first_run_doctor(mode, setter)
    async with app.run_test(size=(120, 30)) as pilot:
        await wait_until(pilot, lambda: isinstance(app.screen, LinkModeScreen))
        await pilot.press("down", "down", "enter")
        await settle(app, pilot)
        doctor = app.view("doctor")
        assert (doctor.status.text, doctor.status.severity) == ("read-only", Severity.ERROR)
        assert "PREVIEW-centralized" in str(_doctor_text(app))


async def test_a_first_run_link_pick_waits_for_the_daemon_default(
    monkeypatch: pytest.MonkeyPatch,
):
    """C-18: the launch daemon apply and a link-mode move both rewrite
    ~/.myshellrc. A pick made while the apply holds the lock is kept and moved
    once the apply is done, never beside it."""
    release = threading.Event()
    moves: list[str] = []
    mode = {"v": "centralized"}

    def setter(value: str) -> None:
        mode["v"] = value

    def spy_move(
        policies: Sequence[Policy], new_mode: str, set_mode: Callable[[str], None], *, old_mode: str
    ) -> tuple[Any, ...]:
        del policies, old_mode
        moves.append(new_mode)
        set_mode(new_mode)
        return ()

    monkeypatch.setattr("installer.wizard_app.move_link_mode", spy_move)
    app = _family_app(
        initial_view="doctor",
        prompt_link_mode=True,
        fix_preview=lambda: f"PREVIEW-{mode['v']}",
        policies=PolicyInputs(policies=[], link_mode=lambda: mode["v"], set_link_mode=setter),
        daemon_default=_held_daemon_default(release),
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await wait_until(pilot, lambda: isinstance(app.screen, LinkModeScreen))
            assert app.mutation_in_flight
            await pilot.press("down", "down", "enter")  # pick split
            await pilot.pause()
            assert moves == []
            release.set()
            await wait_until(pilot, lambda: not app.mutation_in_flight)
            await settle(app, pilot)
            assert moves == ["split"]
            assert "Link mode saved: split" in app.view("doctor").status.text
            assert "PREVIEW-split" in str(_doctor_text(app))
        finally:
            release.set()


# -- 21-21: the UI-01 matrix, every mutation source against every view --

# A pnpm finding, so Doctor prints it; a note, so the tiers stay OK.
_WITNESS_NOTE = PNPM_SPLIT_GROUP.format(names="matrix-witness, its-peer")
_TIER_WITNESS = {"system": "w-system", "user": "w-user", "ai": "w-ai"}


def _matrix_tool(tool_id: str, tier: str, *, node: bool = False) -> Tool:
    method = (
        Method(kind="node", params={"npm_pkg": f"{tool_id}-pkg"})
        if node
        else Method(kind="brew", params={"formula": tool_id})
    )
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(method,),
        priority="P1",
        audience="both",
        tier=tier,
        desc="",
    )


_MATRIX_TOOLS = [
    _matrix_tool("w-system", "system"),
    _matrix_tool("w-user", "user", node=True),
    _matrix_tool("w-ai", "ai"),
    _matrix_tool("up-system", "system"),
    _matrix_tool("up-user", "user"),
    _matrix_tool("up-ai", "ai"),
    _matrix_tool("rm", "system"),
]


@dataclass
class MatrixSeams:
    """What a matrix case acts on: the app, its service and the published witnesses."""

    app: UnifiedApp
    service: FrozenStateService
    bans: list[str]
    witnesses: tuple[Any, ...]


def matrix_app(
    tmp_path: Path,
    *,
    remover: HeldRemover | None = None,
    bans: list[str] | None = None,
    job_apply: Callable[[], PolicyResult] | None = None,
) -> MatrixSeams:
    """One catalog for every matrix case: the witnesses start MISSING, and the
    pass a source requests publishes them present and OK (`witnesses`)."""
    by_id = {tool.id: tool for tool in _MATRIX_TOOLS}
    service = frozen_service(tmp_path)
    platform = service.platform
    outdated = [
        pass_state(
            by_id[tool_id],
            platform=platform,
            ownership=_brew_owned(by_id[tool_id]),
            version=VersionStatus(tool_id, "1.0", "1.1", True, False, "brew"),
        )
        for tool_id in ("up-system", "up-user", "up-ai")
    ]
    service.publish(
        [
            *(absent_state(by_id[tool_id]) for tool_id in _TIER_WITNESS.values()),
            *outdated,
            removable_state(by_id["rm"], [tmp_path / "rm"]),
        ]
    )
    witnesses = (
        removable_state(by_id["w-system"], [tmp_path / "w-system"]),
        pass_state(by_id["w-user"], platform=platform, notes=(_WITNESS_NOTE,)),
        plan_state(by_id["w-ai"]),
    )
    ban_list = bans if bans is not None else []

    def missing_now() -> tuple[str, ...]:
        state = service.state_of("w-system")
        return () if state is not None and state.health is Health.OK else ("w-system",)

    policies = [
        _policy(tmp_path, "plain"),
        replace(
            _policy(tmp_path, "tweak"),
            requires=("w-system",),
            missing_requires=("w-system",),
            missing_requires_now=missing_now,
        ),
    ]
    if job_apply is not None:
        policies.append(_policy(tmp_path, "job", apply=job_apply, background=True))
    updates = ScriptedUpdates(
        {f"up-{tier}": UpdateOutcome(f"up-{tier}", "updated", "brew") for tier in _TIER_WITNESS}
    )
    if remover is None:
        remover = HeldRemover(SweepResult(removed=("rm",)))
        remover.release.set()

    def install(tool: Tool, *_args: Any, **_kwargs: Any) -> InstallOutcome:
        return InstallOutcome(tool.id, "installed")

    execute = ExecuteInputs(
        catalog=_MATRIX_TOOLS,
        platform=platform,
        wire_path=lambda: "PATH wired",
        verify=lambda: "PATH verified",
        install=install,
        version_refresh=service,
    )
    app = _family_app(
        tools=_MATRIX_TOOLS,
        version_refresh=service,
        updates=updates,
        uninstall=UninstallInputs(
            ban_names=lambda: list(ban_list),
            has_path_block=lambda: False,
            remove=remover,
            tweak_ids=lambda: (),
        ),
        policies=PolicyInputs(policies=policies),
        node_globals=_managed_report,
        reinstall_globals=lambda _packages: (),
        execute=execute,
    )
    return MatrixSeams(app, service, ban_list, witnesses)


def _cursor(app: UnifiedApp, view: str, key: str) -> None:
    table = app.view(view).query_one(DataTable[Any])
    table.move_cursor(row=table.get_row_index(key))


async def _install_close(seams: MatrixSeams, pilot: Any) -> None:
    app = seams.app
    await _open_view(app, pilot, "system")
    _cursor(app, "system", "w-system")
    await pilot.press("space", "enter")
    await wait_until(pilot, lambda: isinstance(app.screen, ExecuteScreen))
    await pilot.press("enter")
    await settle(app, pilot)
    await pilot.press("escape")


async def _update_on(tier: str, seams: MatrixSeams, pilot: Any) -> None:
    await _open_view(seams.app, pilot, tier)
    _cursor(seams.app, tier, f"up-{tier}")
    await pilot.press("u")


async def _remove(seams: MatrixSeams, pilot: Any) -> None:
    await _open_view(seams.app, pilot, "uninstall")
    await _confirm_removal(seams.app, pilot, "rm")


async def _toggle(seams: MatrixSeams, pilot: Any) -> None:
    await _open_view(seams.app, pilot, "policies")
    _cursor(seams.app, "policies", "plain")
    await pilot.press("space")


async def _doctor_r(seams: MatrixSeams, pilot: Any) -> None:
    await _open_view(seams.app, pilot, "doctor")
    await pilot.press("r")


# source -> (the view it acts in, its driver)
MATRIX_SOURCES: dict[str, tuple[str, Callable[[MatrixSeams, Any], Any]]] = {
    "install-close": ("system", _install_close),
    "update-system": ("system", lambda seams, pilot: _update_on("system", seams, pilot)),
    "update-user": ("user", lambda seams, pilot: _update_on("user", seams, pilot)),
    "update-ai": ("ai", lambda seams, pilot: _update_on("ai", seams, pilot)),
    "uninstall-removal": ("uninstall", _remove),
    "policies-toggle": ("policies", _toggle),
    "doctor-r": ("doctor", _doctor_r),
}


def _tier_mark(app: UnifiedApp, view: str) -> str:
    table = app.view(view).query_one(DataTable[Any])
    return table.get_cell(_TIER_WITNESS[view], "health").plain


def _requires_text(app: UnifiedApp) -> str:
    table = app.view("policies").query_one(DataTable[Any])
    return str(table.get_cell("tweak", "requires"))


def _tier_target(view: str) -> tuple[Callable[[UnifiedApp], bool], Callable[[UnifiedApp], bool]]:
    return (
        lambda app: _tier_mark(app, view) == "○",
        lambda app: _tier_mark(app, view) == "✓",
    )


# target -> (reads as before the pass, reads as after it)
MATRIX_TARGETS: dict[str, tuple[Callable[[UnifiedApp], bool], Callable[[UnifiedApp], bool]]] = {
    "system": _tier_target("system"),
    "user": _tier_target("user"),
    "ai": _tier_target("ai"),
    "uninstall": (
        lambda app: _section_of(app, "w-system") == "#nothing to do",
        lambda app: _section_of(app, "w-system") != "#nothing to do",
    ),
    "policies": (
        lambda app: _requires_text(app) == "missing: w-system",
        lambda app: _requires_text(app) == "w-system",
    ),
    "doctor": (
        lambda app: f"w-user: {_WITNESS_NOTE}" not in str(_doctor_text(app)),
        lambda app: f"w-user: {_WITNESS_NOTE}" in str(_doctor_text(app)),
    ),
}


def test_the_matrix_covers_seven_sources_and_six_targets():
    assert len(MATRIX_SOURCES) == 7
    assert len(MATRIX_TARGETS) == 6
    assert set(MATRIX_TARGETS) == set(VIEW_NAMES)


@pytest.mark.parametrize("target", list(MATRIX_TARGETS))
@pytest.mark.parametrize("source", list(MATRIX_SOURCES))
async def test_a_mutation_reaches_every_view(tmp_path: Path, source: str, target: str):
    view, drive = MATRIX_SOURCES[source]
    before, after = MATRIX_TARGETS[target]
    seams = matrix_app(tmp_path)
    app = seams.app
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await _open_view(app, pilot, target)
        assert before(app)
        await _open_view(app, pilot, view)
        seams.service.queued = seams.witnesses
        await drive(seams, pilot)
        await settle(app, pilot)
        assert seams.service.queued == ()
        if target != view:
            await _open_view(app, pilot, target)
        assert after(app)


async def test_a_held_mutation_repaints_a_view_navigated_to_before_it_finishes(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("rm",)))
    seams = matrix_app(tmp_path, remover=remover)
    app = seams.app
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await _hold_a_removal(app, pilot, remover, "rm")
            seams.service.queued = seams.witnesses
            await pilot.press("1")
            await wait_until(pilot, lambda: app.current_view == "system")
            screen = app.catalog
            assert app.screen is screen
            assert _tier_mark(app, "system") == "○"
            remover.release.set()
            await settle(app, pilot)
            assert app.screen is screen
            assert _tier_mark(app, "system") == "✓"
        finally:
            remover.release.set()


async def test_a_visible_uninstall_repaints_its_environment_rows_on_publish(tmp_path: Path):
    release = threading.Event()
    bans = ["pip"]

    def clear_the_ban() -> PolicyResult:
        if not release.wait(timeout=10):
            raise TimeoutError("the toggle was never released")
        bans.clear()
        return _policy_result()

    seams = matrix_app(tmp_path, bans=bans, job_apply=clear_the_ban)
    app = seams.app
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await _open_view(app, pilot, "policies")
            _cursor(app, "policies", "job")
            await pilot.press("space")
            assert app.mutation_in_flight
            await _open_view(app, pilot, "uninstall")
            screen = app.screen
            assert screen is app.view("uninstall")
            assert "#ban" in _row_keys(app)
            release.set()
            await settle(app, pilot)
            assert app.screen is screen
            assert "#ban" not in _row_keys(app)
            assert "wait for it to finish" not in app.view("uninstall").status.text
        finally:
            release.set()


# -- 21-21: the replaced forks stay deleted --

_REPO_ROOT = Path(__file__).resolve().parent.parent

_REPLACED_FORKS = [
    "OwnershipRefreshed",
    "_pending_status",
    "_resync",
    "classify_tools",
    "ToolRow",
    "OwnerHint",
    "OwnerLabelHint",
    "_manager_hint",
    "_managed_hint",
    "_own_script_install",
    "uninstall-ownership-refresh",
    "_refresh_ownership_worker",
    "get_default_screen",
    "_start_version_refresh",
    "_refresh_versions_worker",
    "_refresh_skills_worker",
    "VersionStatusRefreshed",
    "SkillStatusRefreshed",
    "execute-wait",
    "_wait_worker",
    "toggle_in_flight",
    "daemon_default_in_flight",
    "_TOGGLE_IN_FLIGHT_MESSAGE",
    "_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE",
    "_rows_of",
    "_live_state",
]


def _guarded_files() -> list[Path]:
    """Tracked and untracked-not-ignored files under installer/, plus setup.py."""
    names: set[str] = set()
    for argv in (
        ["git", "ls-files", "installer"],
        ["git", "ls-files", "--others", "--exclude-standard", "installer"],
    ):
        listing = subprocess.run(argv, cwd=_REPO_ROOT, check=True, capture_output=True, text=True)
        names.update(listing.stdout.splitlines())
    paths = [_REPO_ROOT / name for name in sorted(names)] + [_REPO_ROOT / "setup.py"]
    return [path for path in paths if path.is_file()]


@pytest.mark.parametrize("name", _REPLACED_FORKS)
def test_the_replaced_forks_are_gone(name: str):
    pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
    hits = [
        f"{path.relative_to(_REPO_ROOT)}:{number}"
        for path in _guarded_files()
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        )
        if pattern.search(line)
    ]
    assert hits == [], f"{name} is named again: {', '.join(hits)}"


# -- C-28: a result that lands while another view is visible goes to that view --


async def test_an_update_result_lands_on_the_visible_view(tmp_path: Path):
    updates = _HeldUpdates()
    app, _service = _update_app(tmp_path, updates, HeldRemover())
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            _catalog_cursor(app, "rg")
            await pilot.press("u")
            await wait_until(pilot, updates.started.is_set)
            await app.show_view("doctor")
            updates.release.set()
            await settle(app, pilot)
            assert app.view("doctor").status.text == "updated rg"
            await app.show_view("system")
            assert app.catalog.status_text == ""
        finally:
            updates.release.set()


async def test_a_removal_result_lands_on_the_visible_view(tmp_path: Path):
    remover = HeldRemover(SweepResult(removed=("fd",)))
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "fd")
            await wait_until(pilot, remover.started.is_set)
            await app.show_view("system")
            remover.release.set()
            await settle(app, pilot)
            assert app.catalog.status_text.startswith("1 removed")
            await app.show_view("uninstall")
            assert not app.view("uninstall").status.text.startswith("1 removed")
        finally:
            remover.release.set()


@pytest.mark.parametrize(
    ("make_remover", "expected"),
    [
        (
            lambda: HeldRemover(SweepResult(remove_failed=(("fd", "denied"),))),
            "1 remove failed. Fix the cause, then open Uninstall and press enter to try again.",
        ),
        (
            lambda: HeldRemover(raising=RuntimeError("boom")),
            "Uninstall failed: boom. Check permissions, then open Uninstall and press enter.",
        ),
    ],
    ids=["remove-failed", "worker-failed"],
)
async def test_a_removal_failure_shown_elsewhere_names_uninstall(
    tmp_path: Path, make_remover: Callable[[], HeldRemover], expected: str
):
    """C-28 follow-up: a failure that lands on another view says where enter
    retries it."""
    remover = make_remover()
    app, _service = _removal_app(tmp_path, remover)
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await app.show_view("uninstall")
            await _confirm_removal(app, pilot, "fd")
            await wait_until(pilot, remover.started.is_set)
            await app.show_view("system")
            remover.release.set()
            await settle(app, pilot)
            assert expected in app.catalog.status_text.splitlines()
        finally:
            remover.release.set()


async def test_a_failed_job_toggle_shown_elsewhere_names_policies(tmp_path: Path):
    """C-28 follow-up: a toggle failure that lands on another view says where
    space retries it."""
    release = threading.Event()

    def held_denied() -> PolicyResult:
        if not release.wait(timeout=10):
            raise TimeoutError("the toggle was never released")
        raise OSError("denied")

    app, _service = _policy_app(
        tmp_path, [_policy(tmp_path, "job", apply=held_denied, background=True)], HeldRemover()
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await pilot.press("space")
            assert app.mutation_in_flight
            await app.show_view("system")
            release.set()
            await settle(app, pilot)
            assert app.catalog.status_text == (
                "Policy change failed: denied. Check permissions, then open Policies and"
                " press space."
            )
        finally:
            release.set()


async def test_a_job_toggle_result_lands_on_the_visible_view(tmp_path: Path):
    release = threading.Event()

    def held_apply() -> PolicyResult:
        if not release.wait(timeout=10):
            raise TimeoutError("the toggle was never released")
        return _policy_result()

    app, _service = _policy_app(
        tmp_path, [_policy(tmp_path, "job", apply=held_apply, background=True)], HeldRemover()
    )
    async with app.run_test(size=(120, 30)) as pilot:
        try:
            await settle(app, pilot)
            await pilot.press("space")
            assert app.mutation_in_flight
            await app.show_view("system")
            release.set()
            await settle(app, pilot)
            assert app.catalog.status_text.startswith("job enabled.")
            await app.show_view("policies")
            assert not app.view("policies").status.text.startswith("job enabled.")
        finally:
            release.set()
