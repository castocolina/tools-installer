import inspect
import re
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, TypeVar, cast

import pytest
from rich.cells import cell_len
from rich.text import Text
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import DataTable, Label, ListItem, OptionList, Static

from installer import receipts
from installer.app import UninstallDecision, perform_uninstall
from installer.catalog_tui import CatalogScreen, RefreshRequested, health_cell
from installer.diskusage import DiskPressure
from installer.doctor import DoctorReport
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import DaemonState, MutationHolder, Severity
from installer.execute_screen import (
    ExecuteInputs,
    ExecuteScreen,
    InstallRunFinished,
    InstallRunStarted,
)
from installer.guidance import (
    GUARD_ENTER_HINT,
    SAFE_FIX_ENTER_HINT,
    competing_mechanism_guidance,
    disk_pressure_guidance,
    doctor_guidance,
    guard_guidance,
)
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    Owner,
    OwnershipCandidate,
)
from installer.platform import Platform
from installer.pnpm_globals import NodeGlobal, NodeGlobalsReport, reinstall_preview
from installer.policy import (
    Policy,
    PolicyLayer,
    PolicyResult,
)
from installer.post_install import ConfirmSensitiveAction
from installer.rcclean import PathWriterLine
from installer.receipts import Receipt, ReceiptMethod
from installer.run import CommandError, Runner
from installer.schedules import ReconcileReport
from installer.session import Disposition, PlanRow, Result, RowOutcome, SensitiveInstall
from installer.shellrc import PathGuardOutcome, ShellrcRefusal
from installer.systemd_daemon import CompetingUnit
from installer.ui_common import BASE_VIEW, VIEW_BY_NAME
from installer.uninstall import RemovalPlan, SweepResult
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import (
    BROKEN_REPAIR_NOTE,
    BROKEN_SHIM_REASON,
    LAYOUT_PROOF_NOTE,
    UNKNOWN_OWNER_NOTE,
    Health,
    ToolState,
    VersionRefreshService,
    VersionStatus,
    uninstall_label,
)
from installer.versions import TagResolver, VersionError
from installer.wizard_app import (
    VIEW_ORDER,
    CompetingProbe,
    ConfirmUninstall,
    DiskPressureProbe,
    DoctorScreen,
    LinkModeScreen,
    MutationLock,
    NavScreen,
    PoliciesScreen,
    PolicyInputs,
    RefreshPublished,
    SchedulesScreen,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
    config_split,
)
from tests.screen_family import HeldRemover, settle, wait_until
from tests.state_doubles import (
    FrozenStateService,
    HeldRefreshService,
    Presence,
    absent_state,
    frozen_service,
    managed_state,
    pass_state,
    plan_state,
    presence_service,
    removable_state,
    unavailable_state,
)
from tests.test_uninstall import loop_tool, plant_raw_yq, write_receipt

_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


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


_Case = tuple[Tool, ToolState]


def _removable_row(tool: Tool, paths: list[Path]) -> _Case:
    return tool, removable_state(tool, paths)


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


def _rg_rows() -> list[_Case]:
    """The one-removable-`rg` case most Uninstall tests use."""
    return [_removable_row(_tool("rg"), [Path("/opt/rg")])]


def _uninstall_inputs(
    *,
    ban_names: list[str] | Callable[[], list[str]] | None = None,
    has_path_block: bool | Callable[[], bool] = False,
    remove: Callable[[UninstallDecision], SweepResult] = lambda _decision: SweepResult(),
    tweak_ids: tuple[str, ...] | Callable[[], tuple[str, ...]] = (),
    terminal_sync: Callable[[], str | None] | None = None,
    retired: Callable[[], Sequence[Tool]] = tuple,
    platform_os: str = "",
) -> UninstallInputs:
    """The environment inputs keep the plain-value convenience: they are
    predicates, and most tests only care about one fixed reading."""
    return UninstallInputs(
        ban_names=_predicate(ban_names if ban_names is not None else []),
        has_path_block=_predicate(has_path_block),
        remove=remove,
        tweak_ids=_predicate(tweak_ids),
        terminal_sync=terminal_sync,
        retired=retired,
        platform_os=platform_os,
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
) -> Policy:
    return Policy(
        id=id,
        label="pip/npm ban",
        description="blocks bare pip/npm",
        active=active,
        apply=apply,
        remove=remove,
        log_path=log_path,
    )


def _policy_inputs(
    policies: list[Policy] | None = None,
    *,
    link_mode: Callable[[], str] | None = None,
    set_link_mode: Callable[[str], None] | None = None,
    disk_pressure: DiskPressureProbe | None = None,
    competing: CompetingProbe | None = None,
) -> PolicyInputs:
    return PolicyInputs(
        policies=policies if policies is not None else [_fake_policy()],
        link_mode=link_mode,
        set_link_mode=set_link_mode,
        disk_pressure=disk_pressure,
        competing=competing,
    )


def _pressure(
    *,
    home_free: float | None = 50.0,
    tmp_used: float | None = 10.0,
    daemon_state: DaemonState = DaemonState.INACTIVE,
    tmp_threshold: bool = True,
) -> DiskPressure:
    return DiskPressure(
        home_free_percent=home_free,
        tmp_used_percent=tmp_used,
        daemon=daemon_state,
        tmp_threshold=tmp_threshold,
    )


def _probe(
    read: DiskPressure | Callable[[], DiskPressure],
    *,
    blocking_calls: list[bool] | None = None,
) -> DiskPressureProbe:
    """A disk-pressure probe with the production closure's call shape.

    `blocking_calls`, when given, records the `blocking` keyword of every
    call, so a test can prove which cache verb a caller asked for.
    """

    def probe(*, blocking: bool = True) -> DiskPressure:
        if blocking_calls is not None:
            blocking_calls.append(blocking)
        return read() if callable(read) else read

    return probe


def _app(
    *,
    report: DoctorReport | None = None,
    guard_status: dict[str, bool] | Callable[[], dict[str, bool]] | None = None,
    guard_warning: str | None = None,
    fix_preview: str | Callable[[], str] = "Will wire ~/.local/bin into ~/.zshrc",
    fix: Callable[[], None] = lambda: None,
    uninstall: UninstallInputs | None = None,
    policies: PolicyInputs | None = None,
    node_globals: Callable[[], NodeGlobalsReport] | None = None,
    globals_preview: Callable[[NodeGlobalsReport], str] | None = None,
    reinstall_globals: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
    initial_view: str = BASE_VIEW,
    schedule_defaults: Callable[[], ReconcileReport] | None = None,
    execute: ExecuteInputs | None = None,
    prompt_link_mode: bool = False,
    terminal_sync: Callable[[], str | None] | None = None,
    startup_warning: str | None = None,
    version_refresh: VersionRefreshService | None = None,
    tools: list[Tool] | None = None,
    cases: Sequence[tuple[Tool, ToolState]] | None = None,
) -> UnifiedApp:
    """`cases` pairs each catalog tool with the state a pass published for it;
    the app then lists exactly those tools and reads them from a frozen service."""
    if cases is not None and version_refresh is None:
        version_refresh = frozen_service(Path.home())
        version_refresh.publish([state for _tool_of, state in cases])
    if cases is not None:
        tools = [tool for tool, _state in cases]
    tools = tools if tools is not None else [_tool("rg"), _tool("fd")]
    read_status = _predicate(guard_status or {"pip": False, "npm": False})
    return UnifiedApp(
        tools,
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
        schedule_defaults=schedule_defaults,
        execute=execute,
        prompt_link_mode=prompt_link_mode,
        terminal_sync=terminal_sync,
        startup_warning=startup_warning,
        version_refresh=version_refresh,
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
        if not screen.globals_running and not screen.globals_auditing and not screen.disk_probing:
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
    assert VIEW_ORDER == ("system", "user", "ai", "doctor", "uninstall", "policies", "schedules")


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
    app = _app(cases=_rg_rows(), uninstall=_uninstall_inputs())
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


async def test_doctor_tui_route_uses_duplicate_path_writers_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake(_report: DoctorReport) -> list[PathWriterLine]:
        return [
            PathWriterLine(
                rc_path=Path("/tmp/fake/.bashrc"),
                index=0,
                text='export PATH="/x/bin:$PATH"',
                directory=Path("/x/bin"),
                guardable=True,
                refusal=None,
                block_owner=None,
            )
        ]

    monkeypatch.setattr("installer.wizard_app.path_writer_lines_for", fake)
    app = _app(report=DoctorReport(missing=(), broken=(), duplicated=(Path("/x/bin"),)))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        screen = app.screen
        assert isinstance(screen, DoctorScreen)
        text = "".join(item.title + item.meaning + item.next_step for item in screen.guidance)
        assert "/tmp/fake/.bashrc" in text


def _writer_line(
    rc_path: Path,
    *,
    index: int = 0,
    text: str = 'export PATH="/opt/tools/bin:$PATH"',
    guardable: bool = True,
    refusal: str | None = None,
    block_owner: str | None = None,
) -> PathWriterLine:
    return PathWriterLine(
        rc_path=rc_path,
        index=index,
        text=text,
        directory=Path("/opt/tools/bin"),
        guardable=guardable,
        refusal=refusal,
        block_owner=block_owner,
    )


def _guard_doctor(
    *,
    report: DoctorReport | None = None,
    duplicate_writers: Mapping[Path, tuple[Path, ...]] | None = None,
    fix: Callable[[], None] | None = None,
    writer_lines: Sequence[PathWriterLine] = (),
    rescan: Callable[[], Sequence[PathWriterLine]] | None = None,
    guard_file: Callable[[Path, Sequence[PathWriterLine]], PathGuardOutcome] | None = None,
    guard_state: Callable[[], tuple[dict[str, bool], str | None]] | None = None,
) -> DoctorScreen:
    return DoctorScreen(
        report or DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state or (lambda: ({"pip": False, "npm": False}, None)),
        "preview",
        fix or (lambda: None),
        node_globals=lambda: NodeGlobalsReport(entries=(), missing=(), managed=()),
        globals_preview=lambda _report: "",
        reinstall_globals=lambda _packages: (),
        duplicate_writers=duplicate_writers,
        writer_lines=writer_lines,
        rescan_writer_lines=rescan,
        guard_file=guard_file,
    )


class _DoctorHost(MutationLock, App[None]):
    def __init__(self, screen: DoctorScreen) -> None:
        super().__init__()
        self._doctor = screen

    async def on_mount(self) -> None:
        await self.push_screen(self._doctor)
        self._doctor.enter_view()


async def _ready_doctor(app: App[None], pilot: Pilot[None]) -> DoctorScreen:
    for _ in range(400):
        screen = app.screen
        if (
            isinstance(screen, DoctorScreen)
            and not screen.globals_auditing
            and not screen.disk_probing
        ):
            break
        await pilot.pause()
    await pilot.pause()
    assert isinstance(app.screen, DoctorScreen)
    return app.screen


def _guard_modal_text(screen: object) -> str:
    from installer.wizard_app import ConfirmGuardFile

    assert isinstance(screen, ConfirmGuardFile)
    rendered = str(screen.query_one(Static).render())
    return f"{screen.summary}\n{rendered}"


async def test_doctor_guard_yes_edits_one_file_and_reports_it() -> None:
    rc = Path("tmp/.bashrc")
    record = _writer_line(rc, text='export PATH="/opt/tools/bin:$PATH"')
    scans = iter([[record], []])
    calls: list[tuple[Path, list[PathWriterLine]]] = []
    events: list[str] = []

    def fix() -> None:
        events.append("fix")

    def guard_file(path: Path, lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append((path, list(lines)))
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(
        fix=fix,
        writer_lines=[record],
        rescan=lambda: next(scans),
        guard_file=guard_file,
    )
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert events == ["fix"]
        shown = _guard_modal_text(app.screen)
        assert "tmp/.bashrc" in shown
        assert record.text in shown
        assert ".bashrc.tools-installer.old" in shown
        await pilot.press("y")
        await pilot.pause()
        doctor = await _ready_doctor(app, pilot)
        body = str(doctor.query_one("#doctor-body", Static).render())
        assert calls == [(rc, [record])]
        assert f"guarded {rc}" in body


async def test_doctor_fix_with_a_guard_file_requests_its_pass_after_the_confirmations() -> None:
    rc = Path("tmp/.bashrc")
    record = _writer_line(rc, text='export PATH="/opt/tools/bin:$PATH"')
    scans = iter([[record], []])
    calls: list[Path] = []

    def guard_file(path: Path, lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(path)
        return PathGuardOutcome("guarded")

    class _CountingHost(_DoctorHost):
        passes = 0

        def on_refresh_requested(self, _message: RefreshRequested) -> None:
            self.passes += 1

    screen = _guard_doctor(writer_lines=[record], rescan=lambda: next(scans), guard_file=guard_file)
    app = _CountingHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert _guard_modal_text(app.screen)
        assert app.passes == 0
        await pilot.press("y")
        await pilot.pause()
        assert calls == [rc]
        assert app.passes == 1


async def test_doctor_guard_chain_end_reads_the_live_state_once() -> None:
    """RR-04: the last modal's close renders Doctor once (on resume), not once
    from the callback and again from the resume."""
    rc = Path("tmp/.bashrc")
    record = _writer_line(rc)
    reads: list[int] = []

    def guard_state() -> tuple[dict[str, bool], str | None]:
        reads.append(1)
        return {"pip": False, "npm": False}, None

    screen = _guard_doctor(
        writer_lines=[record],
        rescan=lambda: [record],
        guard_file=lambda _path, _lines: PathGuardOutcome("guarded"),
        guard_state=guard_state,
    )
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert _guard_modal_text(app.screen)
        before = len(reads)
        await pilot.press("y")
        doctor = await _ready_doctor(app, pilot)
        assert f"guarded {rc}" in str(doctor.query_one("#doctor-body", Static).render())
        assert len(reads) == before + 1


async def test_doctor_guard_no_skips_without_calling_guard_file() -> None:
    rc = Path("tmp/.bashrc")
    record = _writer_line(rc)
    calls: list[Path] = []

    def guard_file(path: Path, _lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(path)
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(
        writer_lines=[record],
        rescan=lambda: [record],
        guard_file=guard_file,
    )
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert "tmp/.bashrc" in _guard_modal_text(app.screen)
        await pilot.press("n")
        await pilot.pause()
        doctor = await _ready_doctor(app, pilot)
        body = str(doctor.query_one("#doctor-body", Static).render())
        assert calls == []
        assert f"skipped {rc}" in body


async def test_doctor_guard_with_no_lines_pushes_no_modal() -> None:
    calls: list[Path] = []

    def guard_file(path: Path, _lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(path)
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(writer_lines=[], rescan=lambda: [], guard_file=guard_file)
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert calls == []
        assert "skipped" not in body
        assert "guarded" not in body


async def test_doctor_guard_queue_uses_post_fix_rescan() -> None:
    rc = Path("tmp/.bashrc")
    stale = _writer_line(rc, index=3)
    fresh = _writer_line(rc, index=7)
    scans = iter([[fresh], []])
    calls: list[list[PathWriterLine]] = []

    def guard_file(_path: Path, lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(list(lines))
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(
        writer_lines=[stale],
        rescan=lambda: next(scans),
        guard_file=guard_file,
    )
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert len(calls) == 1
        assert calls[0][0].index == 7
        assert calls[0][0] is not stale


async def test_doctor_guard_queue_falls_back_to_writer_lines_without_rescan() -> None:
    rc = Path("tmp/.bashrc")
    record = _writer_line(rc, index=3)
    calls: list[list[PathWriterLine]] = []

    def guard_file(_path: Path, lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(list(lines))
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(writer_lines=[record], guard_file=guard_file)
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert calls == [[record]]


async def test_doctor_guard_chain_confirms_files_in_record_order() -> None:
    bashrc = Path("tmp/.bashrc")
    profile = Path("tmp/.profile")
    records = [_writer_line(bashrc), _writer_line(profile)]
    calls: list[Path] = []

    def guard_file(path: Path, _lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(path)
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(writer_lines=records, rescan=lambda: records, guard_file=guard_file)
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert "tmp/.bashrc" in _guard_modal_text(app.screen)
        assert "tmp/.profile" not in _guard_modal_text(app.screen)
        await pilot.press("y")
        await pilot.pause()
        assert "tmp/.profile" in _guard_modal_text(app.screen)
        await pilot.press("n")
        await pilot.pause()
        await _ready_doctor(app, pilot)
        assert calls == [bashrc]


async def test_doctor_guard_chain_continues_after_a_refused_file() -> None:
    bashrc = Path("tmp/.bashrc")
    profile = Path("tmp/.profile")
    records = [_writer_line(bashrc), _writer_line(profile)]

    def guard_file(path: Path, _lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        if path == bashrc:
            raise OSError("read-only rc file")
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(writer_lines=records, rescan=lambda: records, guard_file=guard_file)
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert "tmp/.profile" in _guard_modal_text(app.screen)
        await pilot.press("n")
        await pilot.pause()
        doctor = await _ready_doctor(app, pilot)
        body = str(doctor.query_one("#doctor-body", Static).render())
        assert f"refused {bashrc}" in body
        assert "read-only rc file" in body


async def test_doctor_guard_chain_skips_a_file_with_no_guardable_line() -> None:
    bashrc = Path("tmp/.bashrc")
    profile = Path("tmp/.profile")
    records = [
        _writer_line(bashrc),
        _writer_line(profile, guardable=False, refusal="adds more than one directory"),
    ]
    calls: list[Path] = []

    def guard_file(path: Path, _lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(path)
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(writer_lines=records, rescan=lambda: records, guard_file=guard_file)
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert "tmp/.bashrc" in _guard_modal_text(app.screen)
        assert "tmp/.profile" not in _guard_modal_text(app.screen)
        await pilot.press("y")
        await pilot.pause()
        doctor = await _ready_doctor(app, pilot)
        assert calls == [bashrc]
        assert "tmp/.profile" not in str(doctor.query_one("#doctor-body", Static).render())


async def test_doctor_guard_chain_does_not_restart_after_apply() -> None:
    rc = Path("tmp/.bashrc")
    record = _writer_line(rc)
    calls: list[Path] = []

    def guard_file(path: Path, _lines: Sequence[PathWriterLine]) -> PathGuardOutcome:
        calls.append(path)
        return PathGuardOutcome("guarded")

    screen = _guard_doctor(writer_lines=[record], rescan=lambda: [record], guard_file=guard_file)
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await _ready_doctor(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        doctor = await _ready_doctor(app, pilot)
        assert doctor.applied is True
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DoctorScreen)
        assert calls == [rc]


_GUARD_AFTER_APPLY = "The guard is offered again after restarting the installer"
_GUARD_BACKUP_TAIL = ". A backup of the original is saved as .tools-installer.old first"


async def test_doctor_drops_inert_enter_hint_after_apply(tmp_path: Path) -> None:
    plain_dir = Path("/opt/tools/bin")
    block_dir = Path("/opt/kitty/bin")
    rc = tmp_path / ".bashrc"
    plain = _writer_line(rc)
    blocked = replace(
        _writer_line(rc, index=1, block_owner="my-kitty PATH"),
        directory=block_dir,
    )
    records = [plain, blocked]
    missing = Path("/opt/managed/bin")
    screen = _guard_doctor(
        report=DoctorReport(missing=(missing,), broken=(), duplicated=(plain_dir, block_dir)),
        duplicate_writers={plain_dir: (rc,), block_dir: (rc,)},
        writer_lines=records,
        rescan=lambda: records,
        guard_file=lambda _path, _lines: PathGuardOutcome("guarded"),
    )
    app = _DoctorHost(screen)
    async with app.run_test(size=(120, 40)) as pilot:
        doctor = await _ready_doctor(app, pilot)
        before = [item.next_step for item in doctor._tui_guidance()]  # pyright: ignore[reportPrivateUsage]
        plain_guard_before = f"{GUARD_ENTER_HINT}{_GUARD_BACKUP_TAIL}"
        block_guard_before = (
            "inside the 'my-kitty PATH' block; fix it in that tool, "
            "because that tool may regenerate the block; "
            f"{GUARD_ENTER_HINT}{_GUARD_BACKUP_TAIL}"
        )
        safe_fix_before = (
            f"{SAFE_FIX_ENTER_HINT}, then open a new terminal (or `source ~/.myshellrc`)."
        )
        assert plain_guard_before in before
        assert block_guard_before in before
        assert safe_fix_before in before
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        doctor = await _ready_doctor(app, pilot)
        assert doctor.applied is True
        after_steps = [
            item.next_step
            for item in doctor._tui_guidance()  # pyright: ignore[reportPrivateUsage]
        ]
        after = "\n".join(after_steps)
        assert "Press enter" not in after
        assert ".." not in after
        assert f"{_GUARD_AFTER_APPLY}{_GUARD_BACKUP_TAIL}" in after_steps
        assert block_guard_before.replace(GUARD_ENTER_HINT, _GUARD_AFTER_APPLY) in after_steps
        assert (
            "The safe fix was applied; open a new terminal (or `source ~/.myshellrc`)."
            in after_steps
        )
        assert "my-kitty PATH" in after


async def test_doctor_screen_guidance_names_a_foreign_block() -> None:
    directory = Path("/opt/tools/bin")
    rc = Path("tmp/.bashrc")
    record = _writer_line(
        rc,
        guardable=False,
        refusal=("inside the 'my-kitty PATH' block another tool manages; fix it in that tool"),
        block_owner="my-kitty PATH",
    )
    screen = _guard_doctor(
        report=DoctorReport(missing=(), broken=(), duplicated=(directory,)),
        duplicate_writers={directory: (rc,)},
        writer_lines=[record],
    )
    app = _DoctorHost(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        doctor = await _ready_doctor(app, pilot)
        text = "".join(item.next_step for item in doctor.guidance)
        assert "inside the 'my-kitty PATH' block" in text
        assert "fix it in that tool" in text


async def test_doctor_composition_scans_writer_lines_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def counting(_report: DoctorReport, **_kwargs: object) -> list[PathWriterLine]:
        calls.append(True)
        return []

    monkeypatch.setattr("installer.wizard_app.path_writer_lines_for", counting)
    app = _app(report=DoctorReport(missing=(), broken=(), duplicated=(Path("/x/bin"),)))
    async with app.run_test(size=(100, 30)):
        assert calls == [True]


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
        body_after_failure = str(screen.query_one("#doctor-body", Static).render())
        assert "read-only rc file" in body_after_failure
        assert "started with" not in body_after_failure  # nothing frozen yet to explain
        await pilot.press("enter")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True
        assert screen.error is None


async def test_doctor_screen_adapts_the_body_with_a_frozen_path_note_once_applied() -> None:
    """After a successful apply, the Audit block above cannot yet reflect the
    fix -- this process never re-reads its own PATH. The body must say so
    explicitly, framed as expected rather than as an error (D-02)."""
    app = _app(fix=lambda: None, initial_view="doctor")

    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, DoctorScreen)
        body_before = str(app.screen.query_one("#doctor-body", Static).render())
        assert "started with" not in body_before
        await pilot.press("enter")
        screen = app.screen
        assert isinstance(screen, DoctorScreen)
        assert screen.applied is True
        body_after = str(screen.query_one("#doctor-body", Static).render())
        assert "PATH wired." in body_after
        assert "started with" in body_after
        assert "source ~/.myshellrc" in body_after


async def test_doctor_enter_applies_fix_and_refreshes_guidance() -> None:
    """A guard reading that flips as a SIDE EFFECT of the fix must be visible in
    the same rendered frame as the success line — action_apply cannot render
    guidance it computed before the fix ran (D-01)."""
    calls: list[str] = []
    status = {"pip": False, "npm": False}

    def fix() -> None:
        calls.append("fix")
        status["pip"] = True

    app = _app(guard_status=lambda: status, fix=fix, initial_view="doctor")

    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, DoctorScreen)
        body_before = str(app.screen.query_one("#doctor-body", Static).render())
        assert "Package manager guards active" not in body_before
        await pilot.press("enter")
        assert calls == ["fix"]
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is True
        assert screen.error is None
        body_after = str(screen.query_one("#doctor-body", Static).render())
        assert "Package manager guards active" in body_after


async def test_doctor_enter_applies_failed_fix_still_refreshes_guidance() -> None:
    """The refresh is unconditional, not success-gated: a fix that moves the
    guard state and then raises must still render the moved state (D-01).
    run_live runs the callable before it maps the exception, so a failed fix
    can already have touched the machine by the time self.error is set."""
    status = {"pip": False, "npm": False}

    def fix() -> None:
        status["pip"] = True
        raise OSError("boom")

    app = _app(guard_status=lambda: status, fix=fix, initial_view="doctor")

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is False
        assert screen.error == "boom"
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "Fix failed." in body
        assert "Package manager guards active" in body


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


def _managed_row(tool: Tool) -> _Case:
    return tool, managed_state(tool)


def _absent_row(tool: Tool) -> _Case:
    return tool, absent_state(tool)


def _unavailable_row(tool: Tool) -> _Case:
    return tool, unavailable_state(tool)


async def test_uninstall_toggle_selects_highlighted_tool() -> None:
    app = _app(cases=_rg_rows(), uninstall=_uninstall_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("space")
        assert app.screen.selected == {"rg"}
        await pilot.press("space")
        assert app.screen.selected == set()


async def test_uninstall_select_all_includes_ban_and_block() -> None:
    inputs = _uninstall_inputs(
        ban_names=["pip", "npm"],
        has_path_block=True,
    )
    app = _app(cases=_rg_rows(), uninstall=inputs)
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
    inputs = _uninstall_inputs()
    app = _app(
        cases=[
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
            _managed_row(_tool("jq")),
            _absent_row(_tool("fd")),
            _unavailable_row(_tool("rect")),
        ],
        uninstall=inputs,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        table = app.screen.query_one(DataTable[Any])
        keys = {row.value for row in table.rows}
        assert {"rg", "jq", "fd", "rect"} <= keys


async def test_uninstall_non_selectable_rows_are_inert() -> None:
    """Managed/absent/unavailable rows do not toggle; space on them is inert."""
    inputs = _uninstall_inputs()
    app = _app(
        cases=[
            _managed_row(_tool("jq")),
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
        ],
        uninstall=inputs,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")  # select-all over selectable only
        assert app.screen.selected == {"rg"}  # jq never enters


async def test_uninstall_non_selectable_row_shows_hint() -> None:
    inputs = _uninstall_inputs()
    app = _app(cases=[_managed_row(_tool("jq"))], uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.pause()
        assert "brew uninstall jq" in screen.detail_text


async def test_uninstall_apply_calls_remove_and_flips_applied() -> None:
    captured: list[UninstallDecision] = []
    rows = _rg_rows()
    app = _app(cases=rows, uninstall=_uninstall_inputs(remove=_recorder(captured)))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")  # select rg
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await settle(app, pilot)
        assert len(captured) == 1
        assert screen.applied is True


async def test_uninstall_apply_invalidates_the_shared_data_once_on_success(
    tmp_path: Path,
) -> None:
    """D-05: a same-session removal falsifies the shared version/ownership
    data exactly like install and update already do -- the seam call is
    exactly once, after the sweep succeeded."""
    captured: list[UninstallDecision] = []
    service = frozen_service(tmp_path)
    app = _version_app(
        [_tool("rg")],
        service,
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.applied is True
        assert len(service.invalidations) == 1


async def test_uninstall_apply_invalidates_after_a_failed_sweep(tmp_path: Path) -> None:
    """The removal marked its tools pending (D-09) and only `invalidate` clears
    that set, so a failed `run_live` sweep still calls the seam once."""
    service = frozen_service(tmp_path)

    def boom(_decision: UninstallDecision) -> SweepResult:
        raise OSError("permission denied")

    app = _version_app(
        [_tool("rg")], service, cases=_rg_rows(), uninstall=_uninstall_inputs(remove=boom)
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert len(service.invalidations) == 1


async def test_uninstall_apply_survives_a_raising_invalidate(tmp_path: Path) -> None:
    """Mirrors on_install_run_finished's own both-directions contract: a
    raising seam never flips a completed removal into a reported failure,
    and it is never swallowed -- it is appended to the status line."""
    captured: list[UninstallDecision] = []

    service = frozen_service(tmp_path)
    service.invalidate_error = OSError("cache write refused")
    app = _version_app(
        [_tool("rg")],
        service,
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.applied is True  # the removal itself still stands
        assert len(captured) == 1
        assert "version cache invalidation failed" in screen.status.text
        assert "cache write refused" in screen.status.text


# -- D-01/15.6-06 Task 3: a successful interactive Uninstall removal
# re-synchronizes terminal configuration through the SAME shared closure
# Policies, the direct `u` update, unattended installation, the CLI
# uninstall route, and interactive close already reuse.


async def test_uninstall_apply_calls_the_terminal_synchronizer_once_on_success() -> None:
    """Test 1: a successful removal invokes the injected terminal
    synchronizer after perform_uninstall (here: `_remove`) completes, and
    the normal completed-removal summary is retained."""
    captured: list[UninstallDecision] = []
    calls: list[None] = []

    def _terminal_sync() -> str | None:
        calls.append(None)
        return None

    rows = _rg_rows()
    app = _app(
        cases=rows,
        uninstall=_uninstall_inputs(
            remove=_recorder(captured, SweepResult(removed=("rg",))), terminal_sync=_terminal_sync
        ),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.applied is True
        assert len(captured) == 1
        assert len(calls) == 1
        assert "1 removed" in screen.status.text
        assert screen.status.severity is Severity.OK


async def test_uninstall_apply_appends_a_terminal_sync_oserror_without_losing_applied() -> None:
    """Test 2: a terminal synchronizer OSError appends a visible warning to
    the successful removal result and never changes `applied` from the
    primary removal outcome. WR-04: the failure must also render with
    "warn" styling -- not "ok" -- so it is distinguishable from a clean
    success at a glance, mirroring the Policies screen and
    _install_closed's own use of "warn" for this exact class of failure."""
    captured: list[UninstallDecision] = []

    def _boom() -> str | None:
        raise OSError("EACCES: ~/.config/kitty/kitty.conf")

    rows = _rg_rows()
    app = _app(
        cases=rows, uninstall=_uninstall_inputs(remove=_recorder(captured), terminal_sync=_boom)
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.applied is True
        assert len(captured) == 1
        assert "terminal shell synchronization failed" in screen.status.text.lower()
        assert "EACCES" in screen.status.text
        assert screen.status.severity is Severity.WARN


async def test_uninstall_apply_never_calls_the_terminal_synchronizer_after_a_failed_sweep() -> None:
    """Test 2 (continued): a failed sweep must never call the synchronizer
    at all -- nothing was mutated, so there is nothing to reapply."""
    calls: list[None] = []

    def _terminal_sync() -> str | None:
        calls.append(None)
        return None

    def boom(_decision: UninstallDecision) -> SweepResult:
        raise OSError("permission denied")

    app = _app(
        cases=_rg_rows(), uninstall=_uninstall_inputs(remove=boom, terminal_sync=_terminal_sync)
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert calls == []


# -- 21-12: the environment predicates are the screen's only live reads ----------


async def test_uninstall_reentry_repaints_equal_entries() -> None:
    """Entering again with nothing changed repaints entries equal to the last."""
    app = _app(cases=_rg_rows(), initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        before_entries = screen._entries  # pyright: ignore[reportPrivateUsage]
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen._entries == before_entries  # pyright: ignore[reportPrivateUsage]


async def test_uninstall_tool_disappearing_drops_its_stale_selection(tmp_path: Path) -> None:
    rg, fd = _tool("rg"), _tool("fd")
    service = frozen_service(tmp_path)
    service.publish(
        [removable_state(rg, [Path("/opt/rg")]), removable_state(fd, [Path("/opt/fd")])]
    )
    app = _app(tools=[rg, fd], version_refresh=service, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        assert screen.selected == {"rg", "fd"}
        service.queued = (absent_state(fd),)  # fd is no longer removable
        app.request_refresh()
        await settle(app, pilot)
        assert screen.selected == {"rg"}  # the stale fd selection is not carried over


async def test_uninstall_env_failure_during_enter_view_keeps_previous_rows_and_warns() -> None:
    """When an environment predicate raises during enter_view the last
    environment rows are kept, a warn status names the failure, and the tool
    rows still repaint."""
    state = {"fail": False}

    def has_path_block() -> bool:
        if state["fail"]:
            raise OSError("disconnected network mount")
        return True

    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(has_path_block=has_path_block),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "#path-block" in _row_keys(screen)
        state["fail"] = True
        await pilot.press("escape")
        await pilot.press("5")  # must not raise out of the nav path
        assert isinstance(app.screen, UninstallScreen)
        assert app.current_view == "uninstall"
        assert app.screen.status.text == (
            "Could not read the uninstall state: disconnected network mount."
        )
        assert "rg" in _row_keys(app.screen)
        assert "#path-block" in _row_keys(app.screen)


async def test_uninstall_construction_env_failure_yields_a_usable_screen_that_self_heals() -> None:
    """Construction happens outside the nav path `enter_view` guards, so the
    initial environment read goes through `run_live`: a raising predicate must
    not take app construction down. The message is stashed, the first entry
    shows it as a warn and re-reads (self-heals)."""
    calls = {"n": 0}

    def flaky_block() -> bool:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("stale file handle")
        return True

    app = _app(
        cases=_rg_rows(), uninstall=_uninstall_inputs(has_path_block=flaky_block)
    )  # must not raise
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "stale file handle" in screen.status.text
        assert "#path-block" in _row_keys(screen)


def test_uninstall_construction_survives_a_raising_environment_predicate() -> None:
    """CR-01 (15.4-REVIEW.md): the three environment predicates are
    FILESYSTEM reads, not in-memory ones, so `__init__` must evaluate them
    through `run_live`. Bare, a raising `has_path_block` took `_build_app`
    itself down before any screen existed to report it."""

    def raising_block() -> bool:
        raise OSError("EACCES on ~/.myshellrc")

    inputs = _uninstall_inputs(has_path_block=raising_block)
    screen = UninstallScreen(inputs, tools=[_tool("rg")])  # must not raise
    assert screen.remove_path_block is False


async def test_env_predicate_failure_during_a_background_repaint_never_escapes() -> None:
    """CR-01 (15.4-REVIEW.md): `state_refreshed()` reads the environment from a
    repaint the user never initiated, so the same guard has to hold there."""
    state = {"fail": False}

    def tweak_ids() -> tuple[str, ...]:
        if state["fail"]:
            raise OSError("rc file vanished")
        return ()

    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(tweak_ids=tweak_ids),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        state["fail"] = True
        screen.state_refreshed()  # must not raise
        await pilot.pause()
        assert "rc file vanished" in screen.status.text


async def test_an_env_lever_only_sweep_does_not_invalidate_ownership(tmp_path: Path) -> None:
    """WR-01 (15.4-REVIEW.md): `_apply_removal` called `invalidate`
    unconditionally after any successful sweep -- including one that removed
    only the pip/npm ban or the PATH block and no tool at all. That degrades
    every managed row's attribution to the generic registry phrase in
    exchange for nothing: an env lever is not a mutation of any tool's
    ownership."""
    service = frozen_service(tmp_path)
    captured: list[UninstallDecision] = []
    app = _version_app(
        [],
        service,
        uninstall=_uninstall_inputs(ban_names=["pip"], remove=_recorder(captured)),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")  # the ban pseudo-row is the only entry
        await pilot.press("enter")
        await pilot.press("enter")  # confirm
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert screen.applied is True
        assert captured and captured[0].remove_ban is True
        assert service.invalidations == ()


async def _remove_rg(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> UninstallScreen:
    """Select rg on the Uninstall view and confirm its removal."""
    screen = app.screen
    assert isinstance(screen, UninstallScreen)
    await pilot.press("space")
    await pilot.press("enter")
    await pilot.press("enter")  # confirm
    await settle(app, pilot)
    assert screen.applied is True
    return screen


async def test_removal_requests_the_app_pass_after_invalidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-05/D-06: the removal asks the one app owner for its pass after the
    invalidate, and the Uninstall view re-renders on that publish."""
    service = frozen_service(tmp_path)
    published: list[int] = []
    original = UninstallScreen.state_refreshed

    def spy(self: UninstallScreen) -> None:
        published.append(service.passes)
        original(self)

    monkeypatch.setattr(UninstallScreen, "state_refreshed", spy)

    app = _version_app(
        [_tool("rg")],
        service,
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(remove=_recorder([])),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        launch_passes = service.passes
        published.clear()
        await _remove_rg(app, pilot)
        await settle(app, pilot)
        assert service.invalidations == (launch_passes,)
        assert service.passes == launch_passes + 1
        assert published and published[-1] == launch_passes + 1


async def test_uninstall_rerenders_when_a_pass_publishes(tmp_path: Path) -> None:
    """A publish re-derives the rows without clearing the standing status."""
    service = frozen_service(tmp_path)
    rg = _tool("rg")
    app = _version_app(
        [rg],
        service,
        cases=[_removable_row(rg, [Path("/opt/rg")])],
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        screen.applied = True
        screen.status.set("standing result", "ok")
        service.queued = (absent_state(rg),)
        app.request_refresh()
        await settle(app, pilot)
        assert _row_keys(screen) == ["#nothing to do", "rg"]
        assert screen.status.text == "standing result"


async def test_removal_requests_a_pass_even_when_invalidate_raises(tmp_path: Path) -> None:
    service = frozen_service(tmp_path)
    service.invalidate_error = OSError("disk full")
    app = _version_app(
        [_tool("rg")],
        service,
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(remove=_recorder([])),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        launch_passes = service.passes
        screen = await _remove_rg(app, pilot)
        await settle(app, pilot)
        assert "version cache invalidation failed: disk full" in screen.status.text
        assert service.passes == launch_passes + 1


async def test_a_removal_with_no_refresh_service_still_completes() -> None:
    """The service is optional -- the `--uninstall` direct start builds none, and
    a removal there must complete with nothing to invalidate."""
    captured: list[UninstallDecision] = []
    app = _app(
        tools=[],
        uninstall=_uninstall_inputs(ban_names=["pip"], remove=_recorder(captured)),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert screen.applied is True
        assert captured and captured[0].remove_ban is True


def test_state_refreshed_is_a_noop_on_an_unmounted_screen() -> None:
    """Safe to call regardless of mount state: `ToolBrowser.reload` no-ops
    when unmounted."""
    screen = UninstallScreen(_uninstall_inputs(), tools=[_tool("rg")])
    screen.state_refreshed()  # must not raise


async def test_state_refreshed_returns_early_through_the_unchanged_comparison() -> None:
    """Safe to call when nothing changed: the always-render rule (21-11)
    re-derives entries equal to the previous ones."""
    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        before_entries = screen._entries  # pyright: ignore[reportPrivateUsage]
        screen.state_refreshed()
        await pilot.pause()
        assert screen._entries == before_entries  # pyright: ignore[reportPrivateUsage]


async def test_uninstall_empty_selection_refuses() -> None:
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(remove=_recorder(captured))
    app = _app(cases=_rg_rows(), uninstall=inputs)
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

    inputs = _uninstall_inputs(remove=boom)
    app = _app(cases=_rg_rows(), uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space")  # select rg
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm → _apply_removal raises OSError
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert app.screen.error == "permission denied"
        assert "failed" in app.screen.status.text.lower()


async def test_uninstall_destructive_red_accent() -> None:
    """The WayfindingHeader paints the uninstall view with the destructive red accent."""
    from installer.ui_common import WayfindingHeader

    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)):
        header = app.screen.query_one(WayfindingHeader)
        assert "red" in header.render_markup()


async def test_uninstall_initial_view_opens_on_uninstall() -> None:
    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(),
        initial_view="uninstall",
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, UninstallScreen)


async def test_uninstall_empty_state_shows_nothing_line() -> None:
    app = _app(cases=[], uninstall=_uninstall_inputs())  # no tools, no ban, no block
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("enter")  # no-op
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert "Nothing to uninstall" in app.screen.status.text


async def test_ctrl_c_aborts_from_uninstall_view() -> None:
    app = _app(cases=_rg_rows(), uninstall=_uninstall_inputs())
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
        remove=_recorder(captured),
    )
    app = _app(
        cases=[
            _removable_row(_tool("rg"), [Path("/opt/rg")]),
            _removable_row(_tool("fd"), [Path("/opt/fd")]),
        ],
        uninstall=inputs,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        # Cursor starts on row 0 (rg); space selects only that one.
        await pilot.press("space")
        assert len(app.screen.selected) == 1
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].paths == {"rg": (Path("/opt/rg"),)}


async def test_uninstall_applied_summary_ban_and_path() -> None:
    """Status text mentions ban and PATH lines when both are selected.
    Also verifies that remove_ban/remove_path_block read the browser's live
    selection correctly after the modal is dismissed (the post-modal read path)."""
    inputs = _uninstall_inputs(
        ban_names=["pip"],
        has_path_block=True,
        remove=lambda _d: SweepResult(),
    )
    app = _app(cases=_rg_rows(), uninstall=inputs)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")  # select all: tool + ban + path block
        assert screen.remove_ban is True
        assert screen.remove_path_block is True
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert screen.applied is True
        assert "ban removed" in screen.status.text
        assert "PATH wiring removed" in screen.status.text


async def test_uninstall_applied_summary_omits_tool_line_when_no_tool() -> None:
    """Selecting only the ban (no tool) yields no count line."""
    inputs = _uninstall_inputs(
        ban_names=["pip"],
        remove=lambda _d: SweepResult(),
    )
    app = _app(cases=_rg_rows(), uninstall=inputs)
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
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert screen.applied is True
        assert "tool(s)" not in screen.status.text
        assert "ban removed" in screen.status.text


async def test_uninstall_cancel_modal_removes_nothing() -> None:
    captured: list[UninstallDecision] = []
    rows = _rg_rows()
    app = _app(cases=rows, uninstall=_uninstall_inputs(remove=_recorder(captured)))
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
    rows = _rg_rows()
    app = _app(cases=rows, uninstall=_uninstall_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")  # accept → modal
        await pilot.pause()
        assert isinstance(app.screen, ConfirmUninstall)
        assert "1" in app.screen.summary  # one item to remove


async def test_uninstall_screen_omits_the_tweaks_row_when_none_are_active() -> None:
    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(),
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
    app = _app(cases=[], uninstall=inputs, initial_view="uninstall")
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
    app = _app(cases=_rg_rows(), uninstall=_uninstall_inputs())
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
        await settle(app, pilot)
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


async def test_cache_redirect_detail_carries_the_declaration_caveat() -> None:
    from installer.env_redirect import BUN_CACHE_REDIRECT
    from installer.policy import cache_redirect_policy

    policy = cache_redirect_policy(
        BUN_CACHE_REDIRECT,
        platform_os="linux",
        conf_dir=Path("/tmp/environment.d"),
        rc_path=Path("/tmp/.myshellrc"),
        home=Path("/tmp/home"),
    )
    app = _app(policies=_policy_inputs([policy]), initial_view="policies")
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        detail = screen.detail_text
        assert BUN_CACHE_REDIRECT.variable in detail
        assert ".cache/bun" in detail
        assert "next login" in detail
        assert BUN_CACHE_REDIRECT.coverage_caveat in detail
        assert "never deletes the cache directory" in detail


_LINK_MODE_LABELS = (
    "Centralized: one ~/.myshellrc, sourced from .zshrc and .bashrc",
    "Single shell: source ~/.myshellrc from your current shell only",
    "Split: write PATH directly into each rc file (no ~/.myshellrc)",
)


def test_policy_inputs_link_mode_fields_default_to_none() -> None:
    inputs = PolicyInputs(policies=[_fake_policy()])
    assert inputs.link_mode is None
    assert inputs.set_link_mode is None


def test_link_mode_picker_ids_and_labels_match_the_retired_prompt() -> None:
    items = [
        ListItem(Label(label), id=item_id)
        for item_id, label in (
            ("link-centralized", _LINK_MODE_LABELS[0]),
            ("link-single", _LINK_MODE_LABELS[1]),
            ("link-split", _LINK_MODE_LABELS[2]),
        )
    ]
    assert [item.id for item in items] == ["link-centralized", "link-single", "link-split"]
    # Construction is the proof the ids are valid Textual identifiers.
    LinkModeScreen()


async def test_policies_link_mode_line_names_the_mode_when_wired() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        line = str(screen.query_one("#link-mode-line", Static).render())
        assert "centralized" in line
        assert "m" in line


async def test_policies_link_mode_line_is_empty_when_unwired() -> None:
    app = _app(policies=_policy_inputs(), initial_view="policies")
    async with app.run_test(size=(100, 30)):
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        line = str(screen.query_one("#link-mode-line", Static).render())
        assert line.strip() in ("", "''")


async def test_pressing_m_opens_link_mode_picker_with_the_three_labels() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("m")
        screen = app.screen
        assert isinstance(screen, LinkModeScreen)
        labels = [str(item.query_one(Label).render()) for item in screen.query(ListItem)]
        assert labels == list(_LINK_MODE_LABELS)


async def test_selecting_split_saves_and_sets_ok_status() -> None:
    current = ["centralized"]
    calls: list[str] = []

    def set_mode(value: str) -> None:
        calls.append(value)
        current[0] = value

    app = _app(
        policies=_policy_inputs(link_mode=lambda: current[0], set_link_mode=set_mode),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("m")
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("down", "down", "enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == ["split"]
        assert "split" in screen.status.text
        assert "saved" in screen.status.text.lower()
        assert "green" in repr(screen.status.render())
        line = str(screen.query_one("#link-mode-line", Static).render())
        assert "split" in line


async def test_link_mode_picker_escape_warns_and_does_not_call_the_setter() -> None:
    calls: list[str] = []
    app = _app(
        policies=_policy_inputs(
            link_mode=lambda: "centralized", set_link_mode=lambda value: calls.append(value)
        ),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("m")
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, PoliciesScreen)
        assert calls == []
        assert screen.status.text
        lowered = screen.status.text.lower()
        assert "unchanged" in lowered or "cancelled" in lowered


async def test_link_mode_setter_oserror_surfaces_and_leaves_the_line_unchanged() -> None:
    def boom(_value: str) -> None:
        raise OSError("boom")

    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=boom),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        before = str(screen.query_one("#link-mode-line", Static).render())
        await pilot.press("m")
        await pilot.press("enter")
        assert isinstance(app.screen, PoliciesScreen)
        assert "boom" in screen.status.text
        assert str(screen.query_one("#link-mode-line", Static).render()) == before


async def test_pressing_m_without_a_setter_explains_instead_of_opening() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized"),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("m")
        assert isinstance(app.screen, PoliciesScreen)
        assert screen.status.text


async def test_doctor_rereads_callable_fix_preview_on_enter_view() -> None:
    previews = ["first preview text"]
    app = _app(fix_preview=lambda: previews[0], initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "first preview text" in body
        previews[0] = "second preview text"
        await pilot.press("escape")
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "second preview text" in body
        assert "first preview text" not in body


async def test_first_run_picker_is_the_last_modal_even_with_schedule_defaults() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
        prompt_link_mode=True,
        schedule_defaults=ReconcileReport,
    )
    async with app.run_test(size=(100, 30)):
        assert isinstance(app.screen, LinkModeScreen)


async def test_first_run_picker_is_not_pushed_by_default() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
    )
    async with app.run_test(size=(100, 30)):
        assert not isinstance(app.screen, LinkModeScreen)


async def test_first_run_escape_explains_on_the_catalog() -> None:
    calls: list[str] = []
    app = _app(
        policies=_policy_inputs(
            link_mode=lambda: "centralized",
            set_link_mode=lambda value: calls.append(value),
        ),
        prompt_link_mode=True,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("escape")
        assert calls == []
        assert app.catalog.status.text
        assert "centralized" in app.catalog.status.text.lower()


async def test_first_run_escape_on_make_fix_explains_on_the_doctor() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
        initial_view="doctor",
        prompt_link_mode=True,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("escape")
        doctor = app.screen
        assert isinstance(doctor, DoctorScreen)
        assert doctor.status.text


async def test_first_run_selecting_split_saves_and_names_it_on_the_visible_screen() -> None:
    calls: list[str] = []
    app = _app(
        policies=_policy_inputs(
            link_mode=lambda: "centralized",
            set_link_mode=lambda value: calls.append(value),
        ),
        prompt_link_mode=True,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("down", "down", "enter")
        assert calls == ["split"]
        assert "split" in app.catalog.status.text
        assert "saved" in app.catalog.status.text.lower()


async def test_first_run_picker_is_pushed_at_most_once() -> None:
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
        prompt_link_mode=True,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("escape")
        await pilot.press("4")
        await pilot.press("escape")
        assert not isinstance(app.screen, LinkModeScreen)


async def test_dismissed_first_run_picker_persists_nothing(tmp_path: Path) -> None:
    from installer.settings import SettingsStore, load_settings

    path = tmp_path / "settings.json"
    store = SettingsStore(path, link_mode="centralized")
    app = _app(
        policies=_policy_inputs(
            link_mode=lambda: store.link_mode, set_link_mode=store.set_link_mode
        ),
        prompt_link_mode=True,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("escape")
    assert not path.exists() or load_settings(path).settings.link_mode is None


async def test_startup_warning_lands_on_a_non_base_initial_view() -> None:
    """D-11: doctor/fix/uninstall/guard open on a non-base view; show_view
    already flushes the queue there, so the warning is on that screen."""
    app = _app(initial_view="doctor", startup_warning="w")
    async with app.run_test(size=(100, 30)):
        assert app.current_view == "doctor"
        screen = app.screen
        assert isinstance(screen, DoctorScreen)
        assert screen.status.text == "w"
        assert screen.status.severity is Severity.WARN


async def test_dismissed_first_run_picker_keeps_the_startup_warning() -> None:
    """D-11: dismissing the one first-run question must not erase the only
    notice that the settings file was ignored."""
    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=lambda _mode: None),
        prompt_link_mode=True,
        startup_warning="w",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("escape")
        assert app.catalog.status.text.startswith("w · ")
        assert "Link mode unchanged" in app.catalog.status.text


async def test_first_run_setter_oserror_surfaces_on_the_visible_screen() -> None:
    def boom(_value: str) -> None:
        raise OSError("disk full")

    app = _app(
        policies=_policy_inputs(link_mode=lambda: "centralized", set_link_mode=boom),
        prompt_link_mode=True,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        assert "disk full" in app.catalog.status.text


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


def test_run_in_flight_flag_lifecycle() -> None:
    """WR-06: UnifiedApp records that a run is in flight from the moment
    ExecuteScreen starts it, and clears the flag when the run finishes."""
    app = _app()
    assert app.run_in_flight is False
    app.on_install_run_started(InstallRunStarted())
    assert app.run_in_flight is True
    app.on_install_run_finished(
        InstallRunFinished(
            [],
            None,
            "",
            "",
        )
    )
    assert app.run_in_flight is False


async def test_ctrl_c_while_a_run_is_in_flight_leaves_the_flag_set() -> None:
    """WR-06: a hard abort while a run is in flight exits before
    InstallRunFinished can arrive, so the flag stays set and every exit-code
    reader can see the run was interrupted."""
    started = threading.Event()
    release = threading.Event()

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        started.set()
        assert release.wait(10.0)
        return InstallOutcome(tool.id, "installed")

    app = _app(execute=_execute_inputs(install=install))
    async with app.run_test(size=(100, 30)) as pilot:
        app.catalog.selected.add("rg")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if app.run_in_flight:
                break
            await pilot.pause()
        assert app.run_in_flight is True
        await pilot.press("ctrl+c")
        assert not app.is_running
        assert app.outcomes is None
        assert app.run_in_flight is True
        release.set()


async def test_ctrl_c_with_no_run_in_flight_keeps_the_clean_abort() -> None:
    """WR-06 keeps today's code for an abort with no run in flight: the flag
    is False, so the wizard's 'Aborted.' path stays exit 0."""
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+c")
        assert not app.is_running
        assert app.run_in_flight is False


async def test_rapid_view_switching_keeps_stack_one_deep() -> None:
    """Rapid number-key presses must not corrupt the [base] / [base, <view>]
    stack invariant or wedge navigation (the 'keys stop responding' bug)."""
    from installer.catalog_tui import CatalogScreen

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4", "5", "6", "1")
        assert app.current_view == "system"
        assert isinstance(app.screen, CatalogScreen)
        # The empty root is the permanent bottom; one view sits on top of it.
        assert len(app.screen_stack) == 2
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
        await settle(app, pilot)
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
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert "no shell tweaks were still enabled" in app.screen.status.text


async def test_uninstall_tweak_row_names_background_jobs_when_a_schedule_id_is_offered() -> None:
    """Preview-row copy (11-REVIEWS.md cycle 2 finding #19's preview half): the
    Tool-column label and detail both name the background jobs once a
    schedule:-prefixed id is among what is offered."""
    inputs = _uninstall_inputs(tweak_ids=("tweak:countdown", "schedule:tmp-cleanup"))
    app = _app(cases=[], uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        cells = screen.query_one(DataTable[Any]).get_row("#tweaks")
        rendered = " ".join(str(cell) for cell in cells)
        assert "shell tweaks + background jobs" in rendered
        await pilot.pause()
        assert "systemd user timers" in screen.detail_text


@pytest.mark.parametrize("platform_os", ["debian", "arch", "fedora"])
async def test_uninstall_tweak_row_names_the_linux_timers_and_the_cache_redirect(
    platform_os: str,
) -> None:
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown", "schedule:tmp-cleanup", "cache-redirect:bun"),
        platform_os=platform_os,
    )
    app = _app(cases=[], uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.pause()
        detail = screen.detail_text
        assert "systemd user timers" in detail
        assert "unit files" in detail
        assert "LaunchAgent" not in detail
        assert "environment cache redirect" in detail


async def test_uninstall_tweak_row_names_the_macos_launchagents() -> None:
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown", "schedule:tmp-cleanup"), platform_os="macos"
    )
    app = _app(cases=[], uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.pause()
        assert (
            "unregisters the background maintenance LaunchAgents (their plists, the runner and "
            "the schedule state)" in screen.detail_text
        )
        assert "systemd" not in screen.detail_text
        assert "environment cache redirect" not in screen.detail_text


async def test_uninstall_applied_summary_names_a_linux_sweep_without_a_launchagent() -> None:
    inputs = _uninstall_inputs(
        tweak_ids=("schedule:tmp-cleanup", "cache-redirect:bun"),
        remove=_recorder(
            [],
            SweepResult(swept=("schedule:tmp-cleanup", "cache-redirect:bun")),
        ),
        platform_os="fedora",
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "LaunchAgent" not in status
        assert "log out and back in" in status
        assert "cache-redirect:bun" in status


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
    """The sweep swept ONLY a schedule: no shell reload is relevant, so the
    hint must not be appended (11-REVIEWS.md cycle 2 finding #19)."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("schedule:tmp-cleanup",),
        remove=_recorder(captured, SweepResult(swept=("schedule:tmp-cleanup",))),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "background maintenance job" in status
        assert "open a new" not in status.lower()


async def test_uninstall_applied_summary_names_both_when_swept_together() -> None:
    """The sweep swept a schedule AND a real shell tweak together: the
    background job is named AND the shell-reload hint is still appended,
    since a real tweak's reload is still relevant."""
    captured: list[UninstallDecision] = []
    inputs = _uninstall_inputs(
        tweak_ids=("tweak:countdown", "schedule:tmp-cleanup"),
        remove=_recorder(captured, SweepResult(swept=("tweak:countdown", "schedule:tmp-cleanup"))),
    )
    app = _app(uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
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
        await settle(app, pilot)
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


async def test_uninstall_refreshes_and_clears_applied_when_live_state_changed_after_apply() -> None:
    """D-06: a same-session removal's own effect is visible on the NEXT nav
    entry, not hidden behind the standing message forever — an entry whose
    live state genuinely changed re-derives, clears `applied`, and shows the
    ordinary standing status instead of the stale result line (PRECEDENCE
    rule 2)."""
    captured: list[UninstallDecision] = []
    live = ["tweak:countdown"]

    def tweak_ids() -> tuple[str, ...]:
        return tuple(live)

    inputs = _uninstall_inputs(
        tweak_ids=tweak_ids,
        remove=_recorder(captured, SweepResult(swept=("tweak:countdown",))),
    )
    app = _app(cases=[], uninstall=inputs, initial_view="uninstall")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        applied_status = app.screen.status.text
        live.clear()  # the sweep really did disable it
        await pilot.press("escape")
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is False
        assert app.screen.status.text != applied_status
        assert "#tweaks" not in {row.value for row in app.screen.query_one(DataTable[Any]).rows}


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
        body = str(app.screen.query_one("#doctor-body", Static).render())
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
        assert "1 package(s) in pnpm's global set" in body

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
        assert screen.globals_auditing is False
        assert screen.globals_note is None


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
        await pilot.press("r")
        await _settle(app, pilot)
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
    reads: list[int] = []

    def read() -> NodeGlobalsReport:
        reads.append(1)
        return _mmdc_report(missing=())

    app = _app(node_globals=read)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert len(reads) == 1
        await pilot.press("escape")
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert len(reads) == 2


async def test_doctor_tui_guidance_rewrites_make_setup_prefix() -> None:
    app = _app(node_globals=lambda: _mmdc_report(), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        # The console wording never reaches the TUI: pnpm findings are state reasons now.
        assert not any(
            item.next_step.startswith("Run `make setup`") for item in app.screen.guidance
        )
        body = str(app.screen.query_one("#doctor-body", Static).render())
        assert "Press r" in body
        assert "Run `make setup`" not in body


def test_unified_app_constructs_without_node_globals_closures() -> None:
    tools = [_tool("rg")]
    UnifiedApp(
        tools,
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({"pip": False}, None),
        fix_preview="preview",
        fix=lambda: None,
        uninstall=_uninstall_inputs(),
        policies=_policy_inputs(),
    )


# -- D-03 disk pressure on the Doctor screen (plan 15.7-06 task 2) --

_AT_RISK = _pressure(home_free=5.0, daemon_state=DaemonState.INACTIVE)
_HEALTHY_DOCTOR = doctor_guidance(DoctorReport(missing=(), broken=(), duplicated=()))


def _doctor_body(app: UnifiedApp) -> str:
    assert isinstance(app.screen, DoctorScreen)
    return str(app.screen.query_one("#doctor-body", Static).render())


def test_policy_inputs_disk_pressure_defaults_to_none() -> None:
    inputs = PolicyInputs(policies=[_fake_policy()])
    assert inputs.disk_pressure is None


async def test_doctor_without_disk_pressure_renders_exactly_as_today() -> None:
    report = DoctorReport(missing=(Path("/a/bin"),), broken=(), duplicated=())
    app = _app(report=report, initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert app.screen.disk_pressure is None
        assert app.screen.guidance == doctor_guidance(report) + guard_guidance(
            {"pip": False, "npm": False}, None
        )


async def test_doctor_shows_the_at_risk_disk_pressure_item() -> None:
    app = _app(policies=_policy_inputs(disk_pressure=_probe(_AT_RISK)), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [expected] = disk_pressure_guidance(_AT_RISK)
        assert expected in app.screen.guidance
        assert expected.title in _doctor_body(app)


async def test_doctor_healthy_disk_pressure_adds_nothing() -> None:
    app = _app(policies=_policy_inputs(disk_pressure=_probe(_pressure())), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert app.screen.guidance == _HEALTHY_DOCTOR + guard_guidance(
            {"pip": False, "npm": False}, None
        )


async def test_doctor_disk_item_sits_after_guard_and_before_pnpm_reasons(tmp_path: Path) -> None:
    warning = "pip shim is shadowed"
    mmdc = replace(
        _tool("mmdc"),
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )
    service = frozen_service(tmp_path)
    service.publish([pass_state(mmdc, platform=service.platform, broken=(BROKEN_SHIM_REASON,))])
    app = _app(
        guard_warning=warning,
        node_globals=lambda: _mmdc_report(),
        policies=_policy_inputs(disk_pressure=_probe(_AT_RISK)),
        initial_view="doctor",
        tools=[mmdc],
        version_refresh=service,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        guard_items = guard_guidance({"pip": False, "npm": False}, warning)
        assert guard_items
        assert app.screen.guidance == (
            _HEALTHY_DOCTOR + guard_items + disk_pressure_guidance(_AT_RISK)
        )
        body = _doctor_body(app)
        [disk_item] = disk_pressure_guidance(_AT_RISK)
        assert body.index("mmdc: ") > body.index(disk_item.title)


async def test_doctor_tui_rewrites_the_disk_pressure_next_step_to_the_schedules_row() -> None:
    app = _app(policies=_policy_inputs(disk_pressure=_probe(_AT_RISK)), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [console_item] = disk_pressure_guidance(_AT_RISK)
        [tui_item] = [
            item
            for item in app.screen._tui_guidance()  # pyright: ignore[reportPrivateUsage]
            if item.title == console_item.title
        ]
        assert tui_item.next_step != console_item.next_step
        assert tui_item.next_step.startswith(
            "Open the Schedules view and turn on the tmp cleanup row;"
        )
        assert "Schedules view" in tui_item.next_step
        assert "tmp cleanup row" in tui_item.next_step
        assert "make setup" not in tui_item.next_step
        assert tui_item == replace(console_item, next_step=tui_item.next_step)
        body = _doctor_body(app)
        assert "make setup`'s Schedules view" not in body


async def test_doctor_tui_step_keeps_the_platforms_own_prune_command() -> None:
    """WR-08: the TUI rewrite used to hardcode the macOS script, so the Linux
    finding recommended a command that exits 1 on a stock Linux host."""
    linux = _pressure(home_free=5.0, tmp_used=95.0, tmp_threshold=True)
    app = _app(policies=_policy_inputs(disk_pressure=_probe(linux)), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [console_item] = disk_pressure_guidance(linux)
        [tui_item] = [
            item
            for item in app.screen._tui_guidance()  # pyright: ignore[reportPrivateUsage]
            if item.title == console_item.title
        ]
        assert "Schedules view" in tui_item.next_step
        assert "prune-tmp-linux.sh --apply" in tui_item.next_step
        assert "prune-user-tmpdir.sh" not in tui_item.next_step


def _competing_probe(
    units: tuple[CompetingUnit, ...], *, blocking_calls: list[bool] | None = None
) -> CompetingProbe:
    """A competing-mechanism probe with the production closure's call shape:
    a blocking read answers, a peek answers only after one has run."""
    warmed = [False]

    def probe(*, blocking: bool = True) -> tuple[CompetingUnit, ...]:
        if blocking_calls is not None:
            blocking_calls.append(blocking)
        if blocking:
            warmed[0] = True
            return units
        return units if warmed[0] else ()

    return probe


_SYSTEM_COMPETITOR = (
    CompetingUnit(name="cleanup-bun-tmp-cache.timer", scope="system", state="enabled"),
)


async def test_doctor_discloses_a_system_scope_competitor_from_a_worker_read() -> None:
    """WR-10: the disclosure existed only inside the first apply's result, so
    every later run said nothing about the root-owned cleanup job."""
    calls: list[bool] = []
    app = _app(
        policies=_policy_inputs(
            disk_pressure=_probe(_pressure()),
            competing=_competing_probe(_SYSTEM_COMPETITOR, blocking_calls=calls),
        ),
        initial_view="doctor",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [item] = competing_mechanism_guidance(_SYSTEM_COMPETITOR)
        assert item in app.screen.guidance
        assert "cleanup-bun-tmp-cache.timer" in _doctor_body(app)
        # The blocking detection never runs on the event loop (WR-02).
        assert True in calls
        assert app.screen.disk_probing is False


async def test_doctor_disk_pressure_step_is_never_rewritten_into_pnpm_advice() -> None:
    # The generic `Run `make setup`` branch must not capture this item: a
    # full disk answered with "press r to reinstall pnpm globals" is exactly
    # the mis-routing the branch ordering exists to prevent.
    app = _app(policies=_policy_inputs(disk_pressure=_probe(_AT_RISK)), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [console_item] = disk_pressure_guidance(_AT_RISK)
        [tui_item] = [
            item
            for item in app.screen._tui_guidance()  # pyright: ignore[reportPrivateUsage]
            if item.title == console_item.title
        ]
        assert "pnpm" not in tui_item.next_step
        assert "Press r" not in tui_item.next_step


async def test_doctor_unavailable_daemon_step_is_not_rewritten_to_a_missing_row() -> None:
    # D-03c: a host with no managed daemon has no Policies row to point at.
    unavailable = _pressure(home_free=5.0, daemon_state=DaemonState.UNAVAILABLE)
    app = _app(policies=_policy_inputs(disk_pressure=_probe(unavailable)), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [console_item] = disk_pressure_guidance(unavailable)
        tui = app.screen._tui_guidance()  # pyright: ignore[reportPrivateUsage]
        assert console_item in tui
        assert "Policies" not in console_item.next_step


async def test_doctor_rereads_disk_pressure_on_enter_view() -> None:
    current = [_pressure()]
    calls: list[tuple[bool, bool]] = []

    def probe(*, blocking: bool = True) -> DiskPressure:
        calls.append((blocking, threading.current_thread() is threading.main_thread()))
        return current[0]

    app = _app(policies=_policy_inputs(disk_pressure=probe))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        [item] = disk_pressure_guidance(_AT_RISK)
        assert item not in app.screen.guidance
        seen = len(calls)
        current[0] = _AT_RISK
        await pilot.press("escape")
        await pilot.press("4")
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert (True, False) in calls[seen:]  # a fresh blocking read, on a worker
        assert item in app.screen.guidance
        # WR-02: the blocking read may spawn systemctl, so it never runs on the
        # event loop; the render path there only peeks.
        assert all(not on_loop for blocking, on_loop in calls if blocking)
        assert all(not blocking for blocking, on_loop in calls if on_loop)


@pytest.mark.parametrize("error", [OSError("statvfs failed"), ValueError("bad reading")])
async def test_doctor_survives_a_failing_disk_pressure_closure(error: Exception) -> None:
    def broken() -> DiskPressure:
        raise error

    app = _app(policies=_policy_inputs(disk_pressure=_probe(broken)), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert app.screen.guidance == _HEALTHY_DOCTOR + guard_guidance(
            {"pip": False, "npm": False}, None
        )
        assert "PATH Doctor" in _doctor_body(app)


async def test_unified_app_hands_the_policy_inputs_probe_to_the_doctor() -> None:
    probe = _probe(_pressure())
    app = _app(policies=_policy_inputs(disk_pressure=probe), initial_view="doctor")
    async with app.run_test(size=(100, 30)) as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, DoctorScreen)
        assert app.screen.disk_pressure is probe


# -- the disk probe travels on PolicyInputs (plan 15.7-06) --


def test_unified_app_signature_carries_no_disk_pressure_parameter() -> None:
    # The probe travels on PolicyInputs.disk_pressure; a parallel UnifiedApp
    # kwarg would make every UnifiedApp(...) construction site grow for a
    # value that already has a home (review HIGH 15.7-06).
    assert list(inspect.signature(UnifiedApp.__init__).parameters) == [
        "self",
        "tools",
        "blurbs",
        "report",
        "guard_state",
        "fix_preview",
        "fix",
        "uninstall",
        "policies",
        "schedules",
        "node_globals",
        "globals_preview",
        "reinstall_globals",
        "unavailable",
        "initial_view",
        "schedule_defaults",
        "version_refresh",
        "updates",
        "execute",
        "prompt_link_mode",
        "terminal_sync",
        "startup_warning",
    ]


# -- the schedule reconcile at mount (worker, message and lock wiring) --


def test_policy_appends_new_fields_after_every_existing_field() -> None:
    import dataclasses

    names = [field.name for field in dataclasses.fields(Policy)]
    # Later optional fields are appended after them, never inserted before.
    assert names[-5:] == [
        "owned",
        "link_mode_aware",
        "effect_kind",
        "state",
        "detail_lines",
    ]


def test_unarmed_collector_wait_returns_immediately() -> None:
    import time

    from installer.schedules import ScheduleDefaultWarnings

    collector = ScheduleDefaultWarnings()
    started = time.monotonic()
    messages, completed = collector.wait(5)
    assert time.monotonic() - started < 0.2
    assert messages == ()
    assert completed is True


def test_finished_collector_returns_its_messages() -> None:
    from installer.schedules import ScheduleDefaultWarnings

    collector = ScheduleDefaultWarnings()
    collector.arm()
    collector.append("another timer is still running")
    collector.finish()
    messages, completed = collector.wait(5)
    assert messages == ("another timer is still running",)
    assert completed is True


def test_armed_collector_times_out_when_never_finished() -> None:
    import time

    from installer.schedules import ScheduleDefaultWarnings

    collector = ScheduleDefaultWarnings()
    collector.arm()
    collector.append("partial")
    started = time.monotonic()
    messages, completed = collector.wait(0.05)
    elapsed = time.monotonic() - started
    assert 0.04 <= elapsed < 0.5
    assert messages == ("partial",)
    assert completed is False


def test_collector_finish_from_another_thread_unblocks_the_waiter() -> None:
    import time

    from installer.schedules import ScheduleDefaultWarnings

    collector = ScheduleDefaultWarnings()
    collector.arm()
    collector.append("taken over")
    observed: list[tuple[tuple[str, ...], bool]] = []

    def wait() -> None:
        observed.append(collector.wait(5))

    waiter = threading.Thread(target=wait)
    waiter.start()
    time.sleep(0.05)
    assert waiter.is_alive()
    threading.Thread(target=collector.finish).start()
    waiter.join(timeout=1)
    assert not waiter.is_alive()
    assert observed == [(("taken over",), True)]


def _reconcile_app(
    tmp_path: Path,
    *,
    policy: Policy,
    schedule_defaults: Callable[[], ReconcileReport] | None = None,
    remove: Callable[[UninstallDecision], SweepResult] = lambda _d: SweepResult(),
    tweak_ids: tuple[str, ...] | Callable[[], tuple[str, ...]] = (),
    cases: Sequence[_Case] = (),
    initial_view: str = "policies",
) -> UnifiedApp:
    service = frozen_service(Path.home())
    service.publish([state for _tool_of, state in cases])
    return UnifiedApp(
        [_tool("rg")],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=_uninstall_inputs(remove=remove, tweak_ids=tweak_ids),
        policies=PolicyInputs(policies=[policy]),
        version_refresh=service,
        initial_view=initial_view,
        schedule_defaults=schedule_defaults,
    )


_SCHEDULE_SETUP_REFUSAL = (
    "A schedule setup is running; wait for it to finish. Navigation still works."
)
_TOGGLE_REFUSAL = "A policy toggle is running; wait for it to finish. Navigation still works."
_TURNED_ON_TMP = "Turned on schedules: tmp cleanup. Change them in Schedules."


def _turned_on_tmp() -> ReconcileReport:
    return ReconcileReport(turned_on=("tmp-cleanup",))


async def test_schedule_defaults_run_at_mount_and_say_what_they_did(tmp_path: Path) -> None:
    calls: list[bool] = []

    def reconcile() -> ReconcileReport:
        calls.append(threading.current_thread() is threading.main_thread())
        return _turned_on_tmp()

    app = _reconcile_app(tmp_path, policy=_fake_policy(), schedule_defaults=reconcile)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.status.text == _TURNED_ON_TMP
        assert not app.mutation_in_flight
    assert calls == [False]  # once, off the event loop


async def test_a_reconcile_that_did_nothing_says_nothing(tmp_path: Path) -> None:
    app = _reconcile_app(
        tmp_path, policy=_fake_policy(), schedule_defaults=lambda: ReconcileReport()
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.status.text == ""
        assert not app.mutation_in_flight


async def test_reconcile_warnings_reach_the_first_status(tmp_path: Path) -> None:
    report = ReconcileReport(turned_on=("tmp-cleanup",), warnings=("another timer is running",))
    app = _reconcile_app(tmp_path, policy=_fake_policy(), schedule_defaults=lambda: report)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert screen.status.text == f"{_TURNED_ON_TMP} · another timer is running"
        assert not app.mutation_in_flight


async def test_manual_toggle_is_refused_while_the_schedule_setup_is_in_flight(
    tmp_path: Path,
) -> None:
    applies: list[str] = []

    def apply() -> PolicyResult:
        applies.append("apply")
        return _ok_result()

    release = threading.Event()

    def gated() -> ReconcileReport:
        assert release.wait(timeout=30)
        return ReconcileReport()

    app = _reconcile_app(tmp_path, policy=_fake_policy(apply=apply), schedule_defaults=gated)
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            # Hold the worker open until the refusal is proven; on a slow runner it could
            # otherwise finish first and "in flight" becomes a race.
            assert app.mutation_in_flight
            assert app.mutation_holder is MutationHolder.SCHEDULE_DEFAULTS
            await pilot.press("space")
            screen = app.screen
            assert isinstance(screen, PoliciesScreen)
            assert screen.status.text == _SCHEDULE_SETUP_REFUSAL
            release.set()
            await settle(app, pilot)
            assert not app.mutation_in_flight
            assert applies == []
    finally:
        release.set()


async def test_a_background_toggle_runs_off_the_event_loop(tmp_path: Path) -> None:
    """WR-02: a slow apply issues manager mutations; on the event loop a wedged manager froze
    the UI for the whole sequence."""
    threads: list[bool] = []

    def apply() -> PolicyResult:
        threads.append(threading.current_thread() is threading.main_thread())
        return _ok_result()

    policy = _fake_policy(apply=apply, log_path=tmp_path / "job.log")
    app = _reconcile_app(tmp_path, policy=policy)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")
        await settle(app, pilot)
        assert screen.active_state["ban"] is True
        assert "enabled" in screen.status.text
        assert threads == [False]


async def test_a_second_toggle_is_refused_while_a_background_toggle_is_in_flight(
    tmp_path: Path,
) -> None:
    release = threading.Event()
    applies: list[str] = []

    def slow_apply() -> PolicyResult:
        release.wait(timeout=5)
        applies.append("apply")
        return _ok_result()

    policy = replace(
        _fake_policy(apply=slow_apply, log_path=tmp_path / "job.log"),
        is_active=lambda: bool(applies),  # the pass the toggle requests re-reads the real state
    )
    app = _reconcile_app(tmp_path, policy=policy)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")
        assert app.mutation_in_flight
        await pilot.press("space")
        assert screen.status.text == _TOGGLE_REFUSAL
        release.set()
        await settle(app, pilot)
        assert applies == ["apply"]
        assert screen.active_state["ban"] is True


async def test_the_reconcile_repaints_the_schedules_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reconcile changes the rows Schedules shows, so its completion re-reads them."""
    repaints: list[int] = []
    original = SchedulesScreen.state_refreshed

    def counting(self: SchedulesScreen) -> None:
        repaints.append(1)
        original(self)

    monkeypatch.setattr(SchedulesScreen, "state_refreshed", counting)
    release = threading.Event()

    def gated() -> ReconcileReport:
        assert release.wait(timeout=30)
        return _turned_on_tmp()

    app = _reconcile_app(
        tmp_path, policy=_fake_policy(), schedule_defaults=gated, initial_view="schedules"
    )
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            before = len(repaints)
            release.set()
            await settle(app, pilot)
            assert len(repaints) > before
            assert app.view("schedules").status.text == _TURNED_ON_TMP
    finally:
        release.set()


async def test_schedule_defaults_run_once_per_launch(tmp_path: Path) -> None:
    calls: list[int] = []

    def reconcile() -> ReconcileReport:
        calls.append(1)
        return ReconcileReport()

    app = _reconcile_app(tmp_path, policy=_fake_policy(), schedule_defaults=reconcile)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("1")
        await settle(app, pilot)
    assert calls == [1]


async def test_schedule_defaults_lock_clears_even_on_an_unexpected_exception(
    tmp_path: Path,
) -> None:
    def boom() -> ReconcileReport:
        raise RuntimeError("boom, outside the reconcile's own error handling")

    policy = _fake_policy()
    app = _reconcile_app(tmp_path, policy=policy, schedule_defaults=boom)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert not app.mutation_in_flight


async def test_uninstall_removal_is_refused_while_the_schedule_setup_is_in_flight(
    tmp_path: Path,
) -> None:
    """The race guard blocks on the app lock alone -- never on
    whether a daemon: id happens to already be visible in _tweak_ids, which it
    is not yet during first-run auto-apply (11-REVIEWS.md cycle 3 finding
    #12)."""
    policy = _fake_policy()
    captured: list[UninstallDecision] = []
    # A release-gated callable: the guard must hold across this whole multi-keypress
    # sequence, and a near-instant reconcile could otherwise settle before the last
    # keypress lands, making the race window this test targets flaky.
    release = threading.Event()

    def slow_schedule_defaults() -> ReconcileReport:
        release.wait(timeout=5)
        return ReconcileReport()

    app = _reconcile_app(
        tmp_path,
        policy=policy,
        schedule_defaults=slow_schedule_defaults,
        remove=_recorder(captured, SweepResult()),
        tweak_ids=("tweak:countdown",),  # an unrelated, real tweak -- no daemon id present yet
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.mutation_in_flight
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
        assert screen.status.text == _SCHEDULE_SETUP_REFUSAL
        release.set()
        await settle(app, pilot)


async def test_uninstall_removal_is_refused_while_in_flight_even_with_no_tweaks_row(
    tmp_path: Path,
) -> None:
    """Post-implementation review finding: on a machine with NO other active
    tweaks, the daemon's inactive-at-construction Policy means _tweak_ids is
    empty, so _build_entries never offers a tweaks row at all -- remove_tweaks
    can then never become True through this screen, so the guard MUST fire
    directly on the app lock alone, never gated behind
    self.remove_tweaks (which the pre-fix code required, making the guard a
    no-op in exactly this scenario)."""
    policy = _fake_policy()
    captured: list[UninstallDecision] = []
    release = threading.Event()

    def slow_schedule_defaults() -> ReconcileReport:
        release.wait(timeout=5)
        return ReconcileReport()

    app = _reconcile_app(
        tmp_path,
        policy=policy,
        schedule_defaults=slow_schedule_defaults,
        remove=_recorder(captured, SweepResult()),
        tweak_ids=(),  # no other tweaks: the daemon row never appears at all
        cases=[_removable_row(_tool("rg"), [tmp_path / "rg-artifact"])],
    )
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.mutation_in_flight
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
        assert screen.status.text == _SCHEDULE_SETUP_REFUSAL
        release.set()
        await settle(app, pilot)


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
    service: VersionRefreshService,
    *,
    execute: ExecuteInputs | None = None,
    uninstall: UninstallInputs | None = None,
    initial_view: str = BASE_VIEW,
    terminal_sync: Callable[[], str | None] | None = None,
    cases: Sequence[_Case] = (),
) -> UnifiedApp:
    """`cases` are states a pass already published on the (frozen) `service`."""
    if cases:
        assert isinstance(service, FrozenStateService)
        service.publish([state for _tool_of, state in cases])
    return UnifiedApp(
        tools,
        {"search": "find things", "ai": "agents"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=uninstall if uninstall is not None else _uninstall_inputs(),
        policies=_policy_inputs(),
        version_refresh=service,
        execute=execute,
        initial_view=initial_view,
        terminal_sync=terminal_sync,
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
    present: Callable[[Tool], bool] | None = None,
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
        present=present,
    )


async def test_codegraph_ver_cell_contains_installed_and_latest_after_refresh(
    tmp_path: Path,
) -> None:
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.6.0")
    app = _version_app([_codegraph()], service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
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
    app = _version_app([_codegraph()], service)
    async with app.run_test(size=(120, 30)) as pilot:
        assert started.wait(timeout=5)
        screen = app.catalog
        table = screen.query_one(DataTable[Any])
        assert table.row_count >= 1
        assert "codegraph" in {str(key.value) for key in table.rows}
        assert screen.selected == set()
        await pilot.press("space")
        assert screen.selected == {"codegraph"}
        release.set()
        await settle(app, pilot)
        cell = table.get_cell("codegraph", "ver")
        assert "1.2.0" in cell.plain
        assert "v1.6.0" in cell.plain


async def test_version_shows_probed_install_when_latest_fetch_fails(tmp_path: Path) -> None:
    """A failed 'latest' fetch must not discard an installed version we DID
    manage to probe -- that's real information the user still wants to see."""

    def boom(repo: str) -> str:
        del repo
        raise VersionError("github unavailable")

    service = _macos_service(tmp_path, resolve_tag=boom)
    app = _version_app([_codegraph()], service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
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
    app = _version_app([_codegraph()], service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert app.is_running
        cell = app.catalog.query_one(DataTable[Any]).get_cell("codegraph", "health")
        assert cell.plain == "…"


async def test_a_clean_publish_clears_only_the_state_line_it_wrote(tmp_path: Path) -> None:
    """RESEARCH P5/O2: the app clears its own error line on a clean publish,
    and leaves a status a view wrote over it alone."""
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.6.0")
    app = _version_app([_codegraph()], service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.on_refresh_published(RefreshPublished("boom", None))
        assert app.catalog.status_text.startswith("tool state check failed: boom")
        app.on_refresh_published(RefreshPublished(None, None))
        assert app.catalog.status_text == ""
        app.on_refresh_published(RefreshPublished("boom", None))
        app.catalog.status.set("updated codegraph", "ok")
        app.on_refresh_published(RefreshPublished(None, None))
        assert app.catalog.status_text == "updated codegraph"


# -- D-01/Task 1: closing the execute screen refreshes the tier it ran from,
# end to end; that refresh pass re-reads presence into the one tool state. ----


def _tracking_install(
    on_install: Callable[[Tool], None],
) -> Callable[..., InstallOutcome]:
    """A SensitiveInstall-shaped callable that records which tool it "installed"
    (via `on_install`) and always reports success -- the seam every
    `install_closed` test uses to flip a test's own presence/probe holders."""

    def _install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        on_install(tool)
        return InstallOutcome(tool.id, "installed")

    return _install


def _install_closed_platform() -> Platform:
    return Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


async def test_install_closed_refreshes_the_ver_cell_without_navigating_away(
    tmp_path: Path,
) -> None:
    """Tracer (D-01): an already-installed row whose version changes during a
    run is visible in the SAME rendered Ver cell after the run closes -- no
    tab switch, no further keypress -- the exact deno case the user reported.

    The presence holder starts False: deliberate (it keeps the run on the plain
    install path, since CONTEXT.md puts update execution out of scope for
    this phase) and NOT coverage of a genuinely newly-installed row -- the
    fourth and fifth tests below own that, with both signals starting False
    and agreeing.
    """
    tool = _gh_tool("codegraph", tier="system")
    presence = {"codegraph": False}
    probed = {"codegraph": "1.2.0"}

    def probe_output(argv: list[str]) -> str | None:
        del argv
        return probed["codegraph"]

    def on_install(installed_tool: Tool) -> None:
        presence[installed_tool.id] = True
        probed[installed_tool.id] = "1.3.0"

    service = _macos_service(
        tmp_path,
        resolve_tag=lambda repo: "v1.3.0",
        probe_output=probe_output,
        present=lambda t: presence[t.id],
    )
    execute = _execute_inputs(
        [tool],
        present=lambda t: presence[t.id],
        install=_tracking_install(on_install),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        before = app.catalog.query_one(DataTable[Any]).get_cell("codegraph", "ver").plain
        assert before == ""
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        after = app.catalog.query_one(DataTable[Any]).get_cell("codegraph", "ver").plain
        assert after != before
        assert "1.3.0" in after
        assert "->" not in after


def _count_passes(service: VersionRefreshService, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """One entry per refresh pass the service runs."""
    passes: list[int] = []
    refresh = service.refresh

    def counting(tools: Sequence[Tool]) -> None:
        passes.append(1)
        refresh(tools)

    monkeypatch.setattr(service, "refresh", counting)
    return passes


async def test_install_closed_refreshes_the_non_base_tier_it_ran_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pitfall 1 guard: the fix must index self._catalogs (uniform across all
    three tiers), never self._views (which drops the base tier) or a
    show_view-style base/non-base branch."""
    tool = _gh_tool("user-tool", tier="user")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0", present=lambda _t: False)
    passes = _count_passes(service, monkeypatch)
    execute = _execute_inputs(
        [tool],
        present=lambda _t: False,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "user"
        user = app.catalog_for("user")
        await settle(app, pilot)
        before = len(passes)
        user.selected.add("user-tool")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert len(passes) == before + 1


async def test_install_closed_requests_no_pass_when_the_run_never_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A close that ran nothing requests no pass (A11): nothing changed."""
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.3.0")
    passes = _count_passes(service, monkeypatch)
    execute = _execute_inputs(
        [tool],
        present=lambda _t: True,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        before = len(passes)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        assert screen.started is False
        await pilot.press("escape")
        await settle(app, pilot)
        assert len(passes) == before


async def test_install_closed_marks_a_freshly_installed_row_and_keeps_an_unreadable_one(
    tmp_path: Path,
) -> None:
    """Round 1/round 2 gate: presence is re-read by the refresh pass from the
    presence predicate rather than promoted from VersionStatus.installed,
    so it is correct in BOTH directions -- a tool the run installs stops
    being suppressed (A), and a tool whose --version never answers keeps its
    mark because presence never consulted the probe (B)."""
    tool_a = _gh_tool("newly-installed", tier="system")
    tool_b = _gh_tool("stays-installed", tier="system")
    presence = {"newly-installed": False, "stays-installed": True}

    def probe_output(argv: list[str]) -> str | None:
        if Path(argv[0]).name == "newly-installed" and presence["newly-installed"]:
            return "1.0.0"
        return None

    def on_install(installed_tool: Tool) -> None:
        presence[installed_tool.id] = True

    service = _macos_service(
        tmp_path,
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=probe_output,
        present=lambda t: presence[t.id],
    )
    execute = _execute_inputs(
        [tool_a, tool_b],
        present=lambda t: presence[t.id],
        install=_tracking_install(on_install),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app(
        [tool_a, tool_b],
        service,
        execute=execute,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("newly-installed", "ver").plain == ""
        assert table.get_cell("newly-installed", "health").plain == "○"
        assert table.get_cell("stays-installed", "health").plain == "✓"
        app.catalog.selected.add("newly-installed")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        # Do not assert tool B's Ver *text* here: which dim label it lands on
        # is Task 2's contract, not Task 1's.
        assert table.get_cell("newly-installed", "ver").plain != ""
        assert "1.0.0" in table.get_cell("newly-installed", "ver").plain
        assert table.get_cell("newly-installed", "health").plain == "✓"
        assert table.get_cell("stays-installed", "health").plain == "✓"


async def test_returning_from_another_view_shows_the_state_a_pass_published(
    tmp_path: Path,
) -> None:
    """A tool removed while the user was on Uninstall must not keep its ✓ when
    they come back: the pass the removal requests publishes it, and entry
    renders that state (entry itself starts no pass, D-05)."""
    tool = _gh_tool("removable", tier="system")
    presence = {"removable": True}
    service = _macos_service(
        tmp_path, resolve_tag=lambda repo: "v1.0.0", present=lambda t: presence[t.id]
    )
    execute = _execute_inputs(
        [tool],
        present=lambda t: presence[t.id],
        install=_tracking_install(lambda installed_tool: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("5")
        assert app.current_view == "uninstall"
        presence["removable"] = False
        app.request_refresh()
        await settle(app, pilot)
        await pilot.press("1")
        await settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("removable", "health").plain == "○"


async def test_returning_to_the_base_tier_re_resolves_ownership_an_install_dropped(
    tmp_path: Path,
) -> None:
    """An install invalidates every tier's ownership records (one global epoch),
    so the base tier must re-resolve when shown again -- it is never pushed, so
    `show_view` has to call its `enter_view` itself."""
    system_tool = _gh_tool("sys-tool", tier="system")
    user_tool = _gh_tool("usr-tool", tier="user")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")
    execute = _execute_inputs(
        [system_tool, user_tool],
        present=lambda t: True,
        install=_tracking_install(lambda installed_tool: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([system_tool, user_tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("2")
        user_screen = app._catalogs["user"]  # pyright: ignore[reportPrivateUsage]
        await settle(app, pilot)
        user_screen.selected.add("usr-tool")
        await pilot.press("enter")
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert service.state_of("sys-tool") is not None
        await pilot.press("1")
        await settle(app, pilot)
        assert service.state_of("sys-tool") is not None


async def test_install_closed_marks_a_detect_path_tool_that_answers_no_version(
    tmp_path: Path,
) -> None:
    """Round 2 gate: a promotion keyed on VersionStatus.installed can never
    fire for a tool whose command is a shell function no `--version` probe
    will ever answer and whose script-kind method no manager inventory will
    ever list -- the oh-my-zsh shape (installer/registry.toml:539-555;
    SDKMAN is the same shape). Deliberately NOT an app/cask fixture: an
    inventoried cask DOES carry a version (round 3's CRITICAL), so a cask
    fixture would pin the wrong model."""
    tool = Tool(
        id="shell-fn-tool",
        name="shell-fn-tool",
        category="search",
        cmd="shell-fn-tool",
        methods=(Method(kind="script", params={"detect_path": "~/.shell-fn-tool/init.sh"}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
    )
    presence = {"shell-fn-tool": False}

    def on_install(installed_tool: Tool) -> None:
        presence[installed_tool.id] = True

    service = _macos_service(
        tmp_path,
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: None,
        present=lambda t: presence[t.id],
    )
    execute = _execute_inputs(
        [tool],
        present=lambda t: presence[t.id],
        install=_tracking_install(on_install),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("shell-fn-tool", "health").plain == "○"
        app.catalog.selected.add("shell-fn-tool")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("shell-fn-tool", "health").plain == "✓"


async def test_install_closed_refresh_requeries_the_manager_inventory_after_a_run(
    tmp_path: Path,
) -> None:
    """Round 3 HIGH: without the invalidate call, a tool the run just handed
    to brew/cask/pnpm/uv is resolved against a manager inventory read BEFORE
    the run, for up to MANAGER_STALE_AFTER. _macos_service pairs
    has_brew=True with _empty_inventory's brew_prefix=None, so every pass
    trips _partial_manager_failure and persists failed_at=now -- the next
    pass sits inside the 30-minute MANAGER_RETRY_BACKOFF and reuses the
    snapshot UNLESS invalidate ran, which drops the persisted snapshot
    outright so the reader is called again regardless of backoff."""
    calls: list[int] = []

    def counting_inventory(**kwargs: object) -> ManagerInventory:
        calls.append(1)
        return _empty_inventory(**kwargs)

    tool = _gh_tool("codegraph", tier="system")
    managed = tmp_path / "bin"
    service = VersionRefreshService(
        platform=_install_closed_platform(),
        cache_path=tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: "1.0.0",
        managed_bin_dir=managed,
        which=lambda cmd: str(managed / cmd),
        artifacts_for=lambda tool: [managed / tool.cmd],
        read_inventory_fn=counting_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        query=lambda *_a, **_k: "",
        present=lambda _tool: False,
    )
    execute = _execute_inputs(
        [tool],
        present=lambda _t: False,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        before_calls = len(calls)
        before_epoch = service.epoch
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert len(calls) > before_calls
        assert service.epoch > before_epoch


async def test_install_close_survives_a_presence_predicate_that_fails_after_the_run(
    tmp_path: Path,
) -> None:
    """The presence predicate is LIVE: it is the probe of the service that
    ExecuteInputs.version_refresh reads presence from. Closing the run never reads it (D-04: the
    catalog keeps no presence copy to re-derive; the refresh pass re-reads the
    tool state), so a predicate that starts raising after the run can neither
    take the message pump down nor put a re-check warning on the status line.

    The failure is injected after the run rather than before it: ExecuteScreen
    reads the same predicate on mount, and a predicate that failed there would
    prove nothing about the close.
    """
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")
    readable = {"ok": True}

    def _presence(_tool: Tool) -> bool:
        if not readable["ok"]:
            raise OSError("stale file handle: /Volumes/nfs/bin")
        return True

    execute = _execute_inputs(
        [tool],
        present=_presence,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        readable["ok"] = False
        await pilot.press("escape")
        await settle(app, pilot)
        assert app.is_running is True
        assert "re-check failed" not in app.catalog.status_text
        assert "stale file handle" not in app.catalog.status_text


async def test_install_closed_degrades_when_the_active_view_is_not_a_catalog_tier(
    tmp_path: Path,
) -> None:
    """_catalogs is keyed by tier only (system/user/ai) while current_view
    ranges over all six VIEWS. Only a catalog tier pushes ExecuteScreen today,
    but that is one call site's behaviour rather than an enforced invariant --
    pushing it with this callback from the uninstall or doctor view is the
    obvious future caller -- and a KeyError raised inside a Textual
    screen-result callback takes the message pump down instead of degrading.
    """
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")
    execute = _execute_inputs(
        [tool],
        present=lambda _t: True,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("4")
        await pilot.pause()
        assert app.current_view == "doctor"
        app._install_closed(None)  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        # No KeyError: the app is still up and the doctor view is untouched.
        assert app.is_running is True
        assert app.current_view == "doctor"


async def test_a_failed_post_run_cache_invalidation_is_reported_not_swallowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A discarded invalidate silently reinstates exactly the staleness the
    call exists to close -- every manager-owned tool resolved against the
    pre-run inventory for up to MANAGER_STALE_AFTER (6h), with nothing on
    screen and nothing in any log -- and hides a future signature change to
    invalidate() on top of it.

    UpdateService's own call (installer/update.py:436-443) is the precedent in
    both directions: the failure never downgrades an already-recorded
    mutation, and it is never swallowed either (it folds into outcome.detail).
    Here it folds into the catalog's status line, which is the first surface
    visible again -- InstallRunFinished arrives while ExecuteScreen is still
    on top.
    """
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(
        tmp_path, resolve_tag=lambda repo: "v1.0.0", present=lambda _tool: False
    )

    def _refuse(*, reason: str) -> int:
        raise RuntimeError(f"cache write refused ({reason})")

    monkeypatch.setattr(service, "invalidate", _refuse)
    execute = _execute_inputs(
        [tool],
        present=lambda _t: False,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        # Non-fatal: the app is still running, and the summary merge that
        # follows the invalidate call in the same handler still ran, so the
        # run is still recorded...
        assert app.is_running is True
        assert app.outcomes is not None
        # ...but the user is told, rather than left with a silently stale
        # snapshot. The cause travels with the message, not just the symptom.
        assert "version cache invalidation failed" in app.catalog.status_text
        assert "cache write refused" in app.catalog.status_text


async def test_install_closed_then_navigating_to_uninstall_shows_the_post_install_state(
    tmp_path: Path,
) -> None:
    """The Uninstall-side counterpart of the test_install_closed_* family
    above (D-06): an install run closes, the user navigates to Uninstall
    afterward, and the row for the just-installed tool reflects its
    post-install state -- through the single nav path's `enter_view` ->
    repaint, without restarting the app or `_install_closed`
    gaining any reference to the Uninstall screen."""
    tool = _gh_tool("codegraph", tier="system")
    presence = {"codegraph": False}

    def on_install(installed_tool: Tool) -> None:
        presence[installed_tool.id] = True

    service = _macos_service(
        tmp_path,
        resolve_tag=lambda repo: "v1.0.0",
        present=lambda t: presence[t.id],
    )
    execute = _execute_inputs(
        [tool],
        present=lambda t: presence[t.id],
        install=_tracking_install(on_install),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app(
        [tool],
        service,
        execute=execute,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        state = service.state_of("codegraph")
        assert state is not None and state.present
        health = app.screen.query_one(DataTable[Any]).get_cell("codegraph", "health")
        assert health.plain == health_cell(state).plain


async def test_install_closed_keeps_cross_tier_ids_in_every_installed_map(
    tmp_path: Path,
) -> None:
    """Presence after a run is read against the WHOLE catalog, not the screen's own tier.

    `deps.missing_requires` and `selection.unstaged_recommends` resolve against
    the full catalog, so a presence reading narrowed to one tier turns an
    installed cross-tier dependency into the false notice "mmdc also needs
    pnpm". The registry ships ten such pairs today (`mmdc`->`pnpm`,
    `oh-my-zsh`->`git`, `graphify`->`uv`, ...). Two tiers are the whole point
    of this test: a one-tool catalog cannot tell a narrowed reading from a full
    one.
    """
    pnpm = _gh_tool("pnpm", tier="system")
    mmdc = replace(_gh_tool("mmdc", tier="user"), requires=("pnpm",))
    presence = {"pnpm": True, "mmdc": False}
    service = _macos_service(
        tmp_path, resolve_tag=lambda repo: "v1.0.0", present=lambda t: presence[t.id]
    )
    execute = _execute_inputs(
        [pnpm, mmdc],
        present=lambda t: presence[t.id],
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([pnpm, mmdc], service, execute=execute)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("2")
        assert app.current_view == "user"
        user = app.catalog_for("user")
        await settle(app, pilot)
        user.selected.add("mmdc")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        # Enter opens the review; a second Enter runs the plan (D-14).
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        # Behavioural first: marking mmdc on the user view runs the real
        # consumer, and pnpm is installed, so nothing is announced.
        await pilot.press("space")
        await pilot.pause()
        assert user.selected == {"mmdc"}
        assert "also needs pnpm" not in user.status_text


def _sweep_app(
    tmp_path: Path, release: threading.Event
) -> tuple[UnifiedApp, list[Tool], list[str]]:
    """One tool per tier; `calls` records every read of the execute inputs'
    presence predicate, so a catalog-wide sweep shows up as one call per tool.
    The service's own presence probe is separate and uncounted: the refresh
    pass reading presence is the one legitimate reader."""
    tools = [
        _gh_tool("sys-tool", tier="system"),
        _gh_tool("user-tool", tier="user"),
        _gh_tool("ai-tool", tier="ai"),
    ]
    calls: list[str] = []

    def _predicate(tool: Tool) -> bool:
        calls.append(tool.id)
        return False

    def _service_present(tool: Tool) -> bool:
        del tool
        assert release.wait(timeout=10)
        return False

    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0", present=_service_present)
    execute = _execute_inputs(
        tools,
        present=_predicate,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    return _version_app(tools, service, execute=execute), tools, calls


async def test_install_close_reenters_without_a_presence_sweep(tmp_path: Path) -> None:
    """D-04: closing an install run re-enters the active tier through the
    refresh pass. Nothing re-reads the execute presence predicate over the
    catalog, and every row shows `…` until the pass lands."""
    release = threading.Event()
    release.set()
    app, tools, calls = _sweep_app(tmp_path, release)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("sys-tool")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        calls.clear()
        release.clear()
        await pilot.press("escape")
        await pilot.pause()
        table = app.catalog.query_one(DataTable[Any])
        assert table.get_cell("sys-tool", "health").plain == "…"
        release.set()
        await settle(app, pilot)
        assert table.get_cell("sys-tool", "health").plain != "…"
    assert calls == [], f"a presence sweep read {calls} (catalog: {[t.id for t in tools]})"


async def test_view_switch_reenters_without_a_presence_sweep(tmp_path: Path) -> None:
    """D-04/D-05: switching tiers starts no pass and never re-reads the
    execute presence predicate over the catalog."""
    release = threading.Event()
    release.set()
    app, tools, calls = _sweep_app(tmp_path, release)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        for key, view in (("2", "user"), ("3", "ai"), ("1", "system")):
            await pilot.press(key)
            assert app.current_view == view
            await settle(app, pilot)
    assert calls == [], f"a presence sweep read {calls} (catalog: {[t.id for t in tools]})"


# -- D-01/15.6-06 Task 1: every interactive close re-synchronizes terminal
# configuration through the same shared closure Plans 04/05 wired for
# Policies and the direct `u` update, and never silently drops a follow-up
# warning regardless of which AppScreen is visible when the run closes. -----


async def test_install_closed_calls_the_terminal_synchronizer_once_per_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 1: closing an interactive run from EACH catalog tier calls the
    injected synchronizer exactly once, as the close's last step, and
    the existing version-refresh behaviour (Pitfall 1: index self._catalogs
    uniformly across tiers) is unaffected."""
    calls: list[str] = []

    def _terminal_sync() -> str | None:
        calls.append("terminal-sync")
        return None

    tools = [
        _gh_tool("sys-tool", tier="system"),
        _gh_tool("user-tool", tier="user"),
        _gh_tool("ai-tool", tier="ai"),
    ]
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0", present=lambda _t: False)
    passes = _count_passes(service, monkeypatch)

    # WR-07: `installed` gates BOTH resolve_dependencies' own selection-time
    # is_installed check (ExecuteScreen.on_mount). It
    # must answer False, or the tool is treated as already present and
    # excluded from the run entirely; Summary.installed then stays empty and
    # the WR-07 gate this test exercises would never fire.
    def _installed(_t: Tool) -> bool:
        calls.append("installed-sweep")
        return False

    execute = _execute_inputs(
        tools,
        present=_installed,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app(
        tools,
        service,
        execute=execute,
        terminal_sync=_terminal_sync,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        for index, view in enumerate(("system", "user", "ai")):
            if view != "system":
                await pilot.press(str(VIEW_ORDER.index(view) + 1))
            assert app.current_view == view
            screen = app.catalog_for(view)
            await settle(app, pilot)
            before = len(passes)
            calls.clear()
            screen.selected.add(tools[index].id)
            await pilot.press("enter")
            assert isinstance(app.screen, ExecuteScreen)
            await pilot.press("enter")
            await _settle_execute_screen(app, pilot)
            await pilot.press("escape")
            await settle(app, pilot)
            assert calls.count("terminal-sync") == 1
            # The synchronizer is the last thing the close calls.
            assert calls.index("terminal-sync") == len(calls) - 1
            assert len(passes) == before + 1


async def test_install_closed_reports_a_terminal_sync_oserror_without_losing_the_summary(
    tmp_path: Path,
) -> None:
    """Test 2: a synchronization OSError leaves the completed install summary
    intact and appears on the active catalog's status line -- mirrors
    UpdateService.run's own non-fatal terminal-follow-up contract
    (installer/update.py:471-480)."""
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0", present=lambda _t: False)

    def _boom() -> str | None:
        raise OSError("EACCES: ~/.config/kitty/kitty.conf")

    execute = _execute_inputs(
        [tool],
        # WR-07: False, not True -- resolve_dependencies' own is_installed
        # gate excludes an already-True tool from the run entirely, leaving
        # Summary.installed empty and never satisfying the state-change gate
        # this test's terminal-sync assertion depends on.
        present=lambda _t: False,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute, terminal_sync=_boom)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert app.is_running is True
        assert app.outcomes is not None
        assert "terminal shell synchronization" in app.catalog.status_text.lower()
        assert "EACCES" in app.catalog.status_text


async def test_install_closed_delivers_a_terminal_sync_warning_to_the_visible_doctor_screen(
    tmp_path: Path,
) -> None:
    """Test 3: a close callback reached with Doctor (or Uninstall/Policies)
    current retains the warning until it can be rendered on THAT visible
    AppScreen -- it is never silently discarded merely because current_view
    is not a tier key (T-15.6-13)."""
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")

    def _warns() -> str | None:
        return "Terminal shell synchronization warning: wezterm configuration is user-owned"

    execute = _execute_inputs(
        [tool],
        present=lambda _t: True,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute, terminal_sync=_warns)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("4")
        await pilot.pause()
        assert app.current_view == "doctor"
        doctor_screen = app.screen
        assert isinstance(doctor_screen, DoctorScreen)
        # WR-07: this test calls _install_closed directly, bypassing the real
        # ExecuteScreen run entirely -- simulate the state-change signal
        # on_install_run_finished would otherwise have set, so the gate this
        # fix added does not mask what this test is actually about (T-15.6-13's
        # delivery-to-visible-screen contract).
        done = RowOutcome(PlanRow("codegraph", Disposition.INSTALL, ""), "done")
        app._install_closed([done])  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert app.is_running is True
        assert "wezterm configuration is user-owned" in doctor_screen.status.text


async def test_install_closed_with_no_terminal_sync_wired_is_unaffected(
    tmp_path: Path,
) -> None:
    """Test 4: existing UnifiedApp construction sites without the new closure
    (the default None) remain behaviourally compatible -- no exception, no
    status warning, and the run still closes normally."""
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")
    execute = _execute_inputs(
        [tool],
        present=lambda _t: True,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute)
    assert app._terminal_sync is None  # pyright: ignore[reportPrivateUsage]
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert app.is_running is True
        assert app.catalog.status_text == ""


async def test_install_closed_skips_the_terminal_synchronizer_when_nothing_was_installed(
    tmp_path: Path,
) -> None:
    """WR-07 (15.6-REVIEW.md): closing the Execute screen after a run that
    installed nothing (every selected tool already present, so
    resolve_dependencies excludes it and Summary.installed stays empty) must
    not re-sync terminals -- merely opening and dismissing the Execute
    screen otherwise rewrote kitty.conf, created a brand-new wezterm.lua
    (CR-03), and wrote konsolerc for a session where the user selected and
    changed nothing."""
    calls: list[str] = []

    def _terminal_sync() -> str | None:
        calls.append("terminal-sync")
        return None

    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")
    execute = _execute_inputs(
        [tool],
        # Already installed -- resolve_dependencies excludes it from the run
        # entirely, so _tracking_install is never even called.
        present=lambda _t: True,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute, terminal_sync=_terminal_sync)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert app.is_running is True
        assert app.outcomes is not None
        assert all(o.result == "skipped" for o in app.outcomes.values())
        assert calls == []


async def test_install_closed_flushes_a_previously_queued_warning_even_with_no_new_one(
    tmp_path: Path,
) -> None:
    """WR-08 (15.6-REVIEW.md): __init__'s own documented contract is that a
    queued warning flushes on "the next _install_closed render", but the
    early `if not warnings: return` used to skip that flush entirely when
    THIS close produced no new warning of its own -- only a subsequent
    show_view navigation actually delivered a previously-queued one. Confirm
    a close with a real state change but no new warning (terminal_sync
    returns None) still drains and renders a warning queued earlier."""
    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=lambda repo: "v1.0.0")
    execute = _execute_inputs(
        [tool],
        present=lambda _t: False,
        install=_tracking_install(lambda _t: None),
        platform=_install_closed_platform(),
        version_refresh=service,
    )
    app = _version_app([tool], service, execute=execute, terminal_sync=lambda: None)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        # Simulate a warning that arrived while queued (T-15.6-13) -- the
        # exact starting state a subsequent no-new-warning close must not
        # silently keep stranded.
        app._pending_warnings.append("queued: an earlier warning")  # pyright: ignore[reportPrivateUsage]
        app.catalog.selected.add("codegraph")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert app.is_running is True
        assert "queued: an earlier warning" in app.catalog.status_text
        assert app._pending_warnings == []  # pyright: ignore[reportPrivateUsage]


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
    *,
    service: VersionRefreshService,
    updates: UpdateService,
) -> UnifiedApp:
    return UnifiedApp(
        tools,
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


def _frozen_state(
    tool: Tool, platform: Platform, *, ownership: ManagerOwnership, status: VersionStatus
) -> ToolState:
    return pass_state(tool, platform=platform, ownership=ownership, version=status)


def _freeze_status(
    tmp_path: Path, tool: Tool, *, ownership: ManagerOwnership, status: VersionStatus
) -> FrozenStateService:
    """A machine frozen with `tool` present at `status` and owned per `ownership`;
    a refresh re-publishes that state and probes nothing."""
    service = frozen_service(tmp_path)
    service.publish([_frozen_state(tool, service.platform, ownership=ownership, status=status)])
    return service


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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)
    updates = UpdateService(
        platform=service.platform,
        runner=runner,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("u")
        assert started.wait(timeout=5)
        await pilot.press("u")
        assert (
            app.catalog.status_text
            == "An update is running; wait for it to finish. Navigation still works."
        )
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)

    def boom(_cmd: list[str]) -> None:
        raise VersionError("boom")

    updates = UpdateService(
        platform=service.platform,
        runner=boom,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=cached, status=stale_status)
    updates = UpdateService(
        platform=service.platform,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: fresh,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=cached, status=stale_status)
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
        managed_packages=managed,
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=reresolve,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)

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
        managed_packages=managed,
        replay_globals=replay,
        reresolve_ownership=reresolve,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)

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
        managed_packages=managed,
        replay_globals=replay,
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        replay_calls.append(1)
        return tuple(packages)

    updates = UpdateService(
        platform=service.platform,
        runner=lambda cmd: runner_calls.append(cmd),
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: None,
        replay_globals=replay,
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=pre)

    def upgrade(_cmd: list[str]) -> None:
        service.publish([_frozen_state(tool, service.platform, ownership=ownership, status=post)])

    updates = UpdateService(
        platform=service.platform,
        runner=upgrade,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=pre)

    def upgrade(_cmd: list[str]) -> None:
        service.publish([_frozen_state(tool, service.platform, ownership=ownership, status=post)])

    updates = UpdateService(
        platform=service.platform,
        runner=upgrade,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press("u")
        await _settle_update(app, pilot)
        cell = app.catalog.query_one(DataTable[Any]).get_cell("rg", "ver")
        assert "14.1.1" in cell.plain


async def test_epoch_guard_drops_stale_refresh_after_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _brew_rg()
    ownership = _owned(tool, "brew", package="ripgrep")
    started = threading.Event()
    release = threading.Event()
    pre = VersionStatus(
        tool_id="rg",
        installed="14.1.0",
        latest="14.1.1",
        outdated=True,
        stale=False,
        source="brew",
    )
    post = VersionStatus(
        tool_id="rg",
        installed="14.1.1",
        latest="14.1.1",
        outdated=False,
        stale=False,
        source="brew",
    )
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=pre)
    frozen_refresh = service.refresh

    latched: list[bool] = []

    def latched_refresh(tools: Sequence[Tool]) -> dict[str, VersionStatus]:
        del tools
        started.set()
        latched.append(release.wait(timeout=5))
        # A pass the update raced: the service discards what it saw.
        return {}

    def upgrade(_cmd: list[str]) -> None:
        service.publish([_frozen_state(tool, service.platform, ownership=ownership, status=post)])

    monkeypatch.setattr(service, "refresh", latched_refresh)
    updates = UpdateService(
        platform=service.platform,
        runner=upgrade,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        assert started.wait(timeout=5)
        monkeypatch.setattr(service, "refresh", frozen_refresh)
        published: list[str | None] = []
        frozen_publish = service.publish

        def spy_publish(states: Iterable[ToolState]) -> None:
            states = tuple(states)
            published.extend(state.version.installed for state in states if state.version)
            frozen_publish(states)

        monkeypatch.setattr(service, "publish", spy_publish)
        await pilot.press("u")
        # The update upgrades and invalidates while the launch pass is still latched.
        await wait_until(pilot, lambda: bool(service.invalidations))
        assert latched == []
        # Release the raced pass now so it ends inside the test, not on its latch timeout.
        release.set()
        await _settle_update(app, pilot)
        await settle(app, pilot)
        assert latched == [True]
        assert published and "14.1.0" not in published
        cell = app.catalog.query_one(DataTable[Any]).get_cell("rg", "ver")
        assert cell.plain == "14.1.1"


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
    service = _freeze_status(tmp_path, tool, ownership=ownership, status=stale_status)

    def runner(_cmd: list[str]) -> None:
        started.set()
        assert release.wait(timeout=5)

    updates = UpdateService(
        platform=service.platform,
        runner=runner,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
        invalidate=service.invalidate,
    )
    app = _update_app([tool], service=service, updates=updates)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
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


def _execute_inputs(
    catalog: list[Tool] | None = None,
    *,
    present: Presence = (),
    install: SensitiveInstall | None = None,
    platform: Platform | None = None,
    version_refresh: VersionRefreshService | None = None,
) -> ExecuteInputs:
    """A run over `catalog` (rg and fd by default) whose presence is `present`.

    The one place a wizard test builds its ExecuteInputs; the presence answer
    and platform reach the screen through the same frozen service.
    """
    tools = catalog if catalog is not None else [_tool("rg"), _tool("fd")]
    host = (
        platform
        if platform is not None
        else Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    )

    def _ok_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        return InstallOutcome(tool.id, "installed")

    return ExecuteInputs(
        catalog=tools,
        platform=host,
        wire_path=lambda: "",
        verify=lambda: "",
        version_refresh=(
            version_refresh
            if version_refresh is not None
            else presence_service(tools, present=present, platform=host)
        ),
        install=install if install is not None else _ok_install,
    )


async def _settle_execute_screen(app: UnifiedApp, pilot: Pilot[list[str] | None]) -> None:
    for _ in range(400):
        screen = app.screen
        if isinstance(screen, ExecuteScreen) and screen.finished:
            break
        await pilot.pause()
    await pilot.pause()


async def test_a_on_an_all_current_tier_starts_nothing_and_summarizes_n_skipped() -> None:
    tools = [_tool("rg"), _tool("fd"), _tool("bat")]
    execute = _execute_inputs(tools, present={tool.id for tool in tools})
    installs: list[str] = []
    path_wires: list[str] = []
    syncs: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        **kwargs: Any,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, kwargs
        installs.append(tool.id)
        return InstallOutcome(tool.id, "installed")

    execute = replace(execute, install=install, wire_path=lambda: path_wires.append("wire") or "")
    app = UnifiedApp(
        tools,
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=_uninstall_inputs(),
        policies=_policy_inputs(),
        execute=execute,
        terminal_sync=lambda: syncs.append("sync") or None,
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("a", "enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        assert "Summary — 3 skipped" in str(app.screen.query_one("#execute-head", Static).render())
        assert installs == []
        assert path_wires == []
        assert syncs == []
        await pilot.press("enter")
        await pilot.pause()
        assert app.catalog.selected == set()


async def test_a_and_enter_use_the_same_plan_order_as_the_headless_route() -> None:
    from installer.render import display_order
    from installer.session import build_plan
    from installer.version_status import Health

    tools = [_tool("rg"), _tool("fd")]
    unavailable = replace(
        tools[1], methods=(Method(kind="brew", params={"formula": "fd"}, os=("linux",)),)
    )
    tools[1] = unavailable
    service = presence_service(
        tools,
        present={"rg"},
        states=[plan_state(unavailable, health=Health.UNAVAILABLE, present=False)],
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
    )
    execute = replace(
        _execute_inputs(tools, present={"rg"}, version_refresh=service), platform=service.platform
    )
    app = UnifiedApp(
        tools,
        {"search": "find things"},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=_uninstall_inputs(),
        policies=_policy_inputs(),
        execute=execute,
        version_refresh=service,
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("a", "enter")
        assert isinstance(app.screen, ExecuteScreen)
        screen = app.screen
        plan = build_plan(["rg"], tools, service.state_of, service.platform, reinstall=frozenset())
        expected = [row.tool_id for row in display_order(plan)]
        options = screen.query_one("#plan-rows", OptionList)
        actual = [options.get_option_at_index(i).id for i in range(options.option_count)]
        assert actual == expected
        assert "fd" not in actual


async def test_accepting_the_catalog_with_execute_pushes_the_screen_and_keeps_running() -> None:
    app = _app(execute=_execute_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.catalog.selected.add("rg")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        assert app.is_running is True
        screen = app.screen
        assert screen.started is False


async def test_enter_with_nothing_selected_runs_nothing() -> None:
    """SPEC R9 empty edge: Enter with an empty selection warns and runs
    nothing (existing catalog_tui behaviour, test only)."""
    installed: list[str] = []

    def spy_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        installed.append(tool.id)
        return InstallOutcome(tool.id, "installed")

    app = _app(execute=_execute_inputs(install=spy_install))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.catalog.status_text == "Select at least one tool, or press q to quit."
        assert not isinstance(app.screen, ExecuteScreen)
        assert installed == []


async def test_escape_after_completion_returns_to_an_empty_catalog() -> None:
    app = _app(execute=_execute_inputs())
    async with app.run_test(size=(100, 30)) as pilot:
        app.catalog.selected.add("rg")
        await pilot.press("enter")
        screen = app.screen
        assert isinstance(screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, CatalogScreen)
        assert app.catalog.selected == set()


async def test_a_cancelled_run_then_a_successful_rerun_is_not_a_failure() -> None:
    """ponytail #6: not_attempted must not leak across runs. A run cancelled
    after its first tool reports the rest not attempted; a re-run that then
    installs those tools clears them from the session fold, so the session --
    and the process exit code -- is clean."""
    started = threading.Event()
    release = threading.Event()
    mode = {"block": True}

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        if mode["block"]:
            started.set()
            assert release.wait(10.0)
        return InstallOutcome(tool.id, "installed")

    app = _app(execute=_execute_inputs(install=install))
    async with app.run_test(size=(100, 30)) as pilot:
        app.catalog.selected.update({"rg", "fd"})
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        for _ in range(400):
            if started.is_set():
                break
            await pilot.pause()
        await pilot.press("c")  # soft cancel: stop after the current tool
        release.set()
        await _settle_execute_screen(app, pilot)
        first = app.outcomes
        assert first is not None
        assert first["fd"].result == "not_attempted"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, CatalogScreen)
        mode["block"] = False
        app.catalog.selected.add("fd")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        merged = app.outcomes
        assert merged is not None
        assert {tool_id: o.result for tool_id, o in merged.items()} == {
            "rg": "done",
            "fd": "done",
        }


async def test_two_runs_keep_the_latest_outcome_per_tool() -> None:
    """A retained tool that fails once and then succeeds on the retry reads done:
    the app keeps the latest outcome per tool id, never the first run's failure."""
    outcomes: dict[str, list[str]] = {"rg": ["failed", "installed"], "fd": ["installed"]}

    def sequenced(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        return InstallOutcome(tool.id, outcomes[tool.id].pop(0))

    app = _app(execute=_execute_inputs(install=sequenced))
    async with app.run_test(size=(100, 30)) as pilot:
        app.catalog.selected.add("rg")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        first = app.outcomes
        assert first is not None
        assert first["rg"].result == "failed"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, CatalogScreen)
        app.catalog.selected.add("fd")
        await pilot.press("enter")
        assert isinstance(app.screen, ExecuteScreen)
        await pilot.press("enter")
        await _settle_execute_screen(app, pilot)
        merged = app.outcomes
        assert merged is not None
        assert merged["rg"].result == "done"
        assert merged["fd"].result == "done"
        assert all(isinstance(o, RowOutcome) for o in merged.values())


# -- 15.4-04/Task 3: the completion signal -- an Uninstall screen entered
# before the catalog's asynchronous version/ownership refresh commits
# rebuilds in place once that refresh lands, without the user leaving and
# re-entering (Round-2 review HIGH). All three are real app-level tests: the
# ordering is controlled by holding the worker's own resolve_tag call, never
# by sleeping. ----------------------------------------------------------------


def _count_state_refreshed(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"n": 0}
    original = UninstallScreen.state_refreshed

    def spy(self: UninstallScreen) -> None:
        calls["n"] += 1
        original(self)

    monkeypatch.setattr(UninstallScreen, "state_refreshed", spy)
    return calls


async def test_state_refreshed_rebuilds_a_mounted_uninstall_screen_entered_during_an_in_flight_refresh(  # noqa: E501
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = threading.Event()
    release = threading.Event()

    def resolve_tag(repo: str) -> str:
        started.set()
        assert release.wait(timeout=5)
        return "v1.0.0"

    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=resolve_tag)
    calls = _count_state_refreshed(monkeypatch)
    app = _version_app([tool], service)
    async with app.run_test(size=(120, 30)) as pilot:
        assert started.wait(timeout=5)  # the base tier's version refresh is in flight
        await pilot.press("5")  # navigate to Uninstall BEFORE that refresh commits
        assert isinstance(app.screen, UninstallScreen)
        before = calls["n"]
        release.set()  # let the worker commit
        await settle(app, pilot)
        # The publish repaints the visible Uninstall in place, with no second
        # navigation and no user keypress.
        assert calls["n"] > before


async def test_state_refreshed_does_not_touch_a_different_current_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The nav path already re-derives every OTHER view before it is shown
    (rule 2), so a completion signal for a screen nobody is looking at buys
    nothing -- and must change nothing observable."""
    started = threading.Event()
    release = threading.Event()

    def resolve_tag(repo: str) -> str:
        started.set()
        assert release.wait(timeout=5)
        return "v1.0.0"

    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=resolve_tag)
    calls = _count_state_refreshed(monkeypatch)
    app = _version_app([tool], service)
    async with app.run_test(size=(120, 30)) as pilot:
        assert started.wait(timeout=5)
        await pilot.press("5")
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("escape")  # back to the catalog -- Uninstall no longer current
        assert app.current_view != "uninstall"
        before = calls["n"]
        release.set()
        await settle(app, pilot)
        assert calls["n"] == before


async def test_state_refreshed_preserves_a_standing_removal_summary(tmp_path: Path) -> None:
    """A publish arriving while the user is reads a removal summary repaints the
    rows and LEAVES the summary standing: the background path can never wipe the
    sentence describing what the user just did."""
    started = threading.Event()
    release = threading.Event()

    def resolve_tag(repo: str) -> str:
        started.set()
        assert release.wait(timeout=5)
        return "v1.0.0"

    tool = _gh_tool("codegraph", tier="system")
    service = _macos_service(tmp_path, resolve_tag=resolve_tag)
    captured: list[UninstallDecision] = []
    app = _version_app(
        [tool],
        service,
        uninstall=_uninstall_inputs(ban_names=["pip"], remove=_recorder(captured)),
        initial_view="uninstall",
    )
    async with app.run_test(size=(120, 30)) as pilot:
        # The system tier refreshes on entry only, so visit it and come back.
        await app.show_view("system")
        await app.show_view("uninstall")
        assert started.wait(timeout=5)
        assert isinstance(app.screen, UninstallScreen)
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        # The removal's own pass queues behind the held one: wait on the summary.
        await wait_until(pilot, lambda: screen.applied)
        applied_status = screen.status.text
        release.set()
        await settle(app, pilot)
        assert screen.applied is True
        assert screen.status.text == applied_status


def _column_offsets(table: DataTable[Any]) -> dict[str, int]:
    """Each column's start offset in the table's VIRTUAL width, by label.

    A deterministic geometry reading, never a rendered-character match:
    `get_render_width` is the same number Textual lays the columns out with,
    so this pins this project's own column budget rather than Textual's
    layout algorithm (the distinction
    `test_nine_column_table_mounts_and_renders_at_the_minimum_size` draws)."""
    offsets: dict[str, int] = {}
    total = 0
    for column in table.columns.values():
        offsets[column.label.plain] = total
        total += column.get_render_width(table)
    return offsets


async def test_removes_column_starts_inside_the_viewport_at_the_minimum_size() -> None:
    """CR-03 (15.4-REVIEW.md). Rendering `row.hint` into the "Installed via"
    cell sized that column to the longest hint in the catalog: measured at
    this project's own minimum tested terminal size (80x24), with one
    removable row carrying a `required by` suffix and one managed row
    carrying a linuxbrew cask hint plus a `found at` path, "Installed via"
    came out 120 columns wide and "What gets removed" started at x=174 --
    100 columns past the right edge.

    It was not merely truncated but UNREACHABLE: `installer/tool_browser.py`
    binds `left`/`right` to view switching with `priority=True`, so those
    keys never reach the DataTable for horizontal scrolling. On a screen
    whose Enter key deletes files, the user could not see what an entry
    would remove."""
    cases = [
        _removable_row(_tool("ripgrep"), [Path("/opt/rg")]),
        _managed_row(_tool("jetbrains-toolbox")),
        _absent_row(_tool("fd")),
    ]
    app = _app(cases=cases, initial_view="uninstall")
    async with app.run_test(size=(80, 24)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        offsets = _column_offsets(table)
        assert offsets["What gets removed"] < table.size.width, offsets


# -- 15.4-05/D-03/D-04: the "Installed via" cell renders the terse label ----


async def test_tool_entry_cell_per_state_and_removes_cell_lists_the_paths() -> None:
    """Per-state cell coverage: the "Installed via" cell is `uninstall_label`
    of the published state, and the sentence stays in `detail` (CR-03). The
    "What gets removed" cell is the proven paths for a removable row and a dash
    for every other state (21-11)."""
    rg, jq, fd, xyz = _tool("rg"), _tool("jq"), _tool("fd"), _only_on_macos("xyz")
    cases = [
        _removable_row(rg, [Path("/opt/rg")]),
        _managed_row(jq),
        _absent_row(fd),
        _unavailable_row(xyz),
    ]
    app = _app(cases=cases, initial_view="uninstall")
    async with app.run_test(size=(120, 30)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        for tool, state in cases:
            assert _uninstall_cell(table, tool.id, "via") == uninstall_label(state)
        assert _uninstall_cell(table, "jq", "via") == "Homebrew"
        assert _uninstall_cell(table, "fd", "via") == "—"
        assert _uninstall_cell(table, "rg", "removes") == "/opt/rg"
        for tool_id in ("jq", "fd", "xyz"):
            assert _uninstall_cell(table, tool_id, "removes") == "—"


# -- 21-11: the Uninstall Health column, three sections, bounded removal list --

_UNINSTALL_HEADERS = ["Sel", "Tool", "Health", "Cat", "Installed via", "What gets removed"]


def _uninstall_cell(table: DataTable[Any], key: str, column: str) -> str:
    return table.get_cell(key, column).plain


async def test_uninstall_health_column_reads_the_published_state(tmp_path: Path) -> None:
    yq, jq = _tool("yq"), _tool("jq")
    service = frozen_service(tmp_path)
    service.publish([plan_state(yq, health=Health.OK), plan_state(jq, health=Health.OUTDATED)])
    app = _app(
        tools=[yq, jq],
        uninstall=_uninstall_inputs(ban_names=["pip"]),
        initial_view="uninstall",
        version_refresh=service,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        assert [column.label.plain for column in table.columns.values()] == _UNINSTALL_HEADERS
        for tool in (yq, jq):
            state = service.state_of(tool.id)
            assert _uninstall_cell(table, tool.id, "health") == health_cell(state).plain
        ban = [_uninstall_cell(table, "#ban", key) for key in ("health", "cat", "via", "removes")]
        assert ban == ["", "env", "shell config", "shims + aliases (pip)"]


async def test_uninstall_health_repaints_when_a_pass_publishes(tmp_path: Path) -> None:
    yq = _tool("yq")
    service = frozen_service(tmp_path)
    service.publish([plan_state(yq, health=Health.OK)])
    app = _app(
        tools=[yq],
        initial_view="uninstall",
        version_refresh=service,
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        assert _uninstall_cell(table, "yq", "health") == "✓"
        screen.status.set("kept", "ok")
        service.queued = (plan_state(yq, health=Health.OUTDATED),)
        app.request_refresh()
        await settle(app, pilot)
        assert _uninstall_cell(table, "yq", "health") == "↑"
        assert screen.status.text == "kept"


async def test_uninstall_health_reads_checking_before_the_first_pass(tmp_path: Path) -> None:
    yq, jq = _tool("yq"), _tool("jq")
    service = HeldRefreshService(tmp_path, [])
    app = _app(
        tools=[yq, jq],
        initial_view="uninstall",
        version_refresh=service,
    )
    try:
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, UninstallScreen)
            table = screen.query_one(DataTable[Any])
            assert [_uninstall_cell(table, key, "health") for key in ("yq", "jq")] == ["…", "…"]
            service.release.set()
    finally:
        service.release.set()


async def test_uninstall_merges_missing_and_unavailable_under_nothing_to_do() -> None:
    rows = [_unavailable_row(_only_on_macos("xyz")), _absent_row(_tool("fd"))]
    app = _app(cases=rows, initial_view="uninstall")
    async with app.run_test(size=(120, 30)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        keys = [str(key.value) for key in screen.query_one(DataTable[Any]).rows]
        assert keys == ["#nothing to do", "fd", "xyz"]


async def test_uninstall_removes_cell_lists_the_proven_paths_within_budget() -> None:
    long_paths = [Path(f"/home/someone/.local/share/a-long-directory-name/{n}/bin") for n in "abc"]
    rows = [
        _removable_row(_tool("rg"), [Path("/opt/rg")]),
        _removable_row(_tool("bat"), long_paths),
        _managed_row(_tool("jq")),
    ]
    app = _app(cases=rows, initial_view="uninstall")
    async with app.run_test(size=(120, 30)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        assert _uninstall_cell(table, "rg", "removes") == "/opt/rg"
        long_cell = _uninstall_cell(table, "bat", "removes")
        assert long_cell.endswith("…")
        assert len(long_cell) < len(", ".join(str(path) for path in long_paths))
        assert long_cell.startswith("/home/someone")
        assert _uninstall_cell(table, "jq", "removes") == "—"


async def test_doctor_apply_surfaces_a_consolidation_refusal_instead_of_reporting_success() -> None:
    """A refused ~/.shellrc consolidation must never render as "PATH wired."

    The Doctor route runs configure_path with a quiet console so its prints
    cannot corrupt the TUI, and `action_apply` DISCARDS run_live's result. So a
    printed refusal reaches nobody and a returned one is dropped -- the only way
    the screen can learn about it is the typed raise that run_live catches.
    """
    reason = "~/.shellrc line 7 opens a here-document; consolidate it by hand"

    def fix() -> None:
        raise ShellrcRefusal(reason)

    app = _app(fix=fix)

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("4")
        await pilot.press("enter")
        assert isinstance(app.screen, DoctorScreen)
        screen = app.screen
        assert screen.applied is False
        assert screen.error is not None
        body = str(screen.query_one("#doctor-body", Static).render())
        assert "PATH wired." not in body
        assert reason in body


# -- plan 20-10 Task 2: the app keeps the retained selection and gates the sync on a ran row --


def _outcome_for(tool_id: str, result: Result) -> RowOutcome:
    return RowOutcome(PlanRow(tool_id, Disposition.INSTALL, ""), result)


async def test_install_closed_keeps_exactly_the_retained_rows_selected() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        staged = app._staged  # pyright: ignore[reportPrivateUsage]
        staged.update({"a", "b", "c", "d"})
        app._install_closed(  # pyright: ignore[reportPrivateUsage]
            [
                _outcome_for("a", "done"),
                _outcome_for("b", "failed"),
                _outcome_for("c", "skipped"),
                _outcome_for("d", "blocked"),
            ]
        )
        await pilot.pause()
        assert app._staged == {"b", "d"}  # pyright: ignore[reportPrivateUsage]
        assert app._staged is staged  # pyright: ignore[reportPrivateUsage]


async def test_install_closed_never_adds_a_dragged_in_dependency() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        app._staged.add("mmdc")  # pyright: ignore[reportPrivateUsage]
        app._install_closed(  # pyright: ignore[reportPrivateUsage]
            [_outcome_for("node", "failed"), _outcome_for("mmdc", "dependency_failed")]
        )
        await pilot.pause()
        assert app._staged == {"mmdc"}  # pyright: ignore[reportPrivateUsage]


async def test_escape_before_start_leaves_the_selection_untouched() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        app._staged.update({"rg", "fd"})  # pyright: ignore[reportPrivateUsage]
        app._install_closed(None)  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert app._staged == {"rg", "fd"}  # pyright: ignore[reportPrivateUsage]


async def test_terminal_sync_runs_only_when_a_row_ran() -> None:
    calls: list[str] = []

    def sync() -> str | None:
        calls.append("sync")
        return None

    app = _app(terminal_sync=sync)
    async with app.run_test(size=(100, 30)) as pilot:
        app._install_closed([_outcome_for("rg", "skipped")])  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert calls == []
        app._install_closed([_outcome_for("rg", "done")])  # pyright: ignore[reportPrivateUsage]
        await pilot.pause()
        assert calls == ["sync"]


async def test_a_run_that_rewires_path_replaces_an_earlier_run_error() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        app.on_install_run_finished(
            InstallRunFinished(
                [_outcome_for("rg", "done")], None, "", "", "PATH wiring failed", None
            )
        )
        assert app.run_errors == ["PATH wiring failed"]
        app.on_install_run_finished(
            InstallRunFinished([_outcome_for("fd", "done")], None, "wired", "audited")
        )
        await pilot.pause()
        assert app.run_errors == []


async def test_a_run_that_ran_nothing_keeps_an_earlier_run_error() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        app.on_install_run_finished(
            InstallRunFinished(
                [_outcome_for("rg", "done")], None, "", "", "PATH wiring failed", None
            )
        )
        app.on_install_run_finished(
            InstallRunFinished([_outcome_for("fd", "skipped")], None, "", "")
        )
        await pilot.pause()
        assert app.run_errors == ["PATH wiring failed"]


async def test_a_successful_u_after_a_failed_u_clears_the_failure() -> None:
    from installer.catalog_tui import ToolUpdated
    from installer.update import UpdateOutcome

    app = _app()
    app.on_tool_updated(ToolUpdated("rg", UpdateOutcome("rg", "failed", "brew", "failed"), None, 0))
    app.on_tool_updated(ToolUpdated("rg", UpdateOutcome("rg", "updated", "brew"), None, 0))
    assert app.outcomes is not None
    assert app.outcomes["rg"].result == "done"


async def test_a_run_where_nothing_ran_does_not_invalidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalidations: list[str] = []
    service = presence_service(
        [_tool("rg"), _tool("fd")],
        present=set(),
        platform=Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
    )

    def invalidate(**_kwargs: object) -> None:
        invalidations.append("invalidated")

    monkeypatch.setattr(service, "invalidate", invalidate)
    app = _app()
    monkeypatch.setattr(app, "_version_refresh", service)
    async with app.run_test(size=(100, 30)) as pilot:
        app.on_install_run_finished(
            InstallRunFinished([_outcome_for("rg", "skipped")], None, "", "")
        )
        await pilot.pause()
        assert invalidations == []
        app.on_install_run_finished(InstallRunFinished([_outcome_for("rg", "done")], None, "", ""))
        await pilot.pause()
        assert invalidations == ["invalidated"]


async def test_cancel_then_retry_leaves_the_latest_outcome_and_exits_clean() -> None:
    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        app.on_install_run_finished(
            InstallRunFinished([_outcome_for("rg", "not_attempted")], None, "", "")
        )
        await pilot.pause()
        app.on_install_run_finished(InstallRunFinished([_outcome_for("rg", "done")], None, "", ""))
        await pilot.pause()
        outcomes = app.outcomes
        assert outcomes is not None
        assert outcomes["rg"].result == "done"
        assert app.run_errors == []


# -- 21-12: the Uninstall view is a projection of the published state ----------

_NOTHING = "Nothing to uninstall."


def _only_on_macos(tool_id: str) -> Tool:
    """A tool with no install method on the unavailable-platform double."""
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="github_release", params={"repo": "o/x"}, os=("macos",)),),
    )


def _row_keys(screen: UninstallScreen) -> list[str]:
    return [str(row.value) for row in screen.query_one(DataTable[Any]).rows]


async def test_uninstall_draws_three_sections_from_the_published_state() -> None:
    yq, jq, fd, xyz = _tool("yq"), _tool("jq"), _tool("fd"), _only_on_macos("xyz")
    cases = [
        (yq, removable_state(yq, [Path("/opt/yq")])),
        (jq, managed_state(jq)),
        (fd, absent_state(fd)),
        (xyz, unavailable_state(xyz)),
    ]
    app = _app(cases=cases, initial_view="uninstall")
    async with app.run_test(size=(120, 30)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _row_keys(screen) == [
            "#removable here",
            "yq",
            "#managed elsewhere",
            "jq",
            "#nothing to do",
            "fd",
            "xyz",
        ]
        table = screen.query_one(DataTable[Any])
        selectable = {tool.id: _uninstall_cell(table, tool.id, "sel") != "" for tool, _ in cases}
        assert selectable == {"yq": True, "jq": False, "fd": False, "xyz": False}
        for tool, state in cases:
            assert _uninstall_cell(table, tool.id, "health") == health_cell(state).plain


async def test_uninstall_rows_change_when_a_pass_publishes(tmp_path: Path) -> None:
    yq = _tool("yq")
    service = frozen_service(tmp_path)
    service.publish([removable_state(yq, [Path("/opt/yq")])])
    app = _app(tools=[yq], version_refresh=service, initial_view="uninstall")
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _row_keys(screen) == ["#removable here", "yq"]
        service.queued = (absent_state(yq),)
        app.request_refresh()
        await settle(app, pilot)
        assert _row_keys(screen) == ["#nothing to do", "yq"]


async def test_uninstall_offers_nothing_before_the_first_pass(tmp_path: Path) -> None:
    yq, jq = _tool("yq"), _tool("jq")
    service = HeldRefreshService(tmp_path, [])
    app = _app(tools=[yq, jq], version_refresh=service, initial_view="uninstall")
    try:
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, UninstallScreen)
            assert _row_keys(screen) == ["#nothing to do", "yq", "jq"]
            table = screen.query_one(DataTable[Any])
            for key in ("yq", "jq"):
                assert _uninstall_cell(table, key, "sel") == ""
                assert _uninstall_cell(table, key, "health") == "…"
            await pilot.press("space")
            assert screen.selected == set()
            assert screen.status.text != _NOTHING
    finally:
        service.release.set()


async def test_uninstall_nothing_installed_draws_only_nothing_to_do() -> None:
    rg, fd = _tool("rg"), _tool("fd")
    app = _app(cases=[(rg, absent_state(rg)), (fd, absent_state(fd))], initial_view="uninstall")
    async with app.run_test(size=(120, 30)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert [key for key in _row_keys(screen) if key.startswith("#")] == ["#nothing to do"]
        assert (screen.status.text, screen.status.severity) == (_NOTHING, "ok")


async def test_uninstall_unpublished_row_keeps_its_painted_section(tmp_path: Path) -> None:
    yq = _tool("yq")
    service = frozen_service(tmp_path)
    service.publish([removable_state(yq, [Path("/opt/yq")])])
    app = _app(tools=[yq], version_refresh=service, initial_view="uninstall")
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        service.mark_pending({"yq"})
        screen.state_refreshed()
        await pilot.pause()
        table = screen.query_one(DataTable[Any])
        assert _row_keys(screen) == ["#removable here", "yq"]
        assert _uninstall_cell(table, "yq", "sel") != ""
        assert _uninstall_cell(table, "yq", "health") == "…"


async def _detail_of(app: UnifiedApp, pilot: Pilot[list[str] | None], key: str) -> str:
    screen = app.screen
    assert isinstance(screen, UninstallScreen)
    table = screen.query_one(DataTable[Any])
    for _ in range(len(table.rows)):
        if str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value) == key:
            break
        await pilot.press("down")
    await pilot.pause()
    return screen.detail_text


async def test_uninstall_unknown_owner_row_names_no_manager() -> None:
    jq = _tool("jq")
    app = _app(cases=[(jq, plan_state(jq, owner="unknown"))], initial_view="uninstall")
    async with app.run_test(size=(120, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _uninstall_cell(screen.query_one(DataTable[Any]), "jq", "via") == "unknown"
        assert (await _detail_of(app, pilot, "jq")).startswith(UNKNOWN_OWNER_NOTE)


async def test_uninstall_broken_row_shows_the_repair_text() -> None:
    jq = _tool("jq")
    state = plan_state(jq, health=Health.BROKEN, owner="brew", package="jq", reasons=("shim",))
    app = _app(cases=[(jq, state)], initial_view="uninstall")
    async with app.run_test(size=(120, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _row_keys(screen)[0] == "#managed elsewhere"
        assert (await _detail_of(app, pilot, "jq")).startswith(BROKEN_REPAIR_NOTE)


async def test_uninstall_detail_markup_renders_literally() -> None:
    jq = _tool("jq")
    state = plan_state(jq, owner="installer", reasons=("[red]x[/red]",))
    app = _app(cases=[(jq, state)], initial_view="uninstall")
    async with app.run_test(size=(120, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "[red]x[/red]" in await _detail_of(app, pilot, "jq")
        detail = screen.query_one("#browser-detail", Static)
        painted = " ".join("".join(seg.text for seg in detail.render_line(y)) for y in range(3))
        assert "[red]x[/red]" in painted


async def test_a_publish_rereads_the_environment_rows(tmp_path: Path) -> None:
    rg = _tool("rg")
    service = frozen_service(tmp_path)
    service.publish([removable_state(rg, [Path("/opt/rg")])])
    bans = ["pip"]
    app = _app(
        tools=[rg],
        version_refresh=service,
        uninstall=_uninstall_inputs(ban_names=lambda: list(bans)),
        initial_view="uninstall",
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "#ban" in _row_keys(screen)
        screen.status.set("kept", "ok")
        bans.clear()
        app.request_refresh()
        await settle(app, pilot)
        assert "#ban" not in _row_keys(screen)
        assert screen.status.text == "kept"


async def test_a_publish_that_adds_an_env_row_retracts_nothing_to_uninstall(
    tmp_path: Path,
) -> None:
    rg = _tool("rg")
    service = frozen_service(tmp_path)
    service.publish([absent_state(rg)])
    tweaks: list[str] = []
    app = _app(
        tools=[rg],
        version_refresh=service,
        uninstall=_uninstall_inputs(tweak_ids=lambda: tuple(tweaks)),
        initial_view="uninstall",
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert (screen.status.text, screen.status.severity) == (_NOTHING, "ok")
        tweaks.append("daemon:prune-tmp-linux")
        app.request_refresh()
        await settle(app, pilot)
        assert "#tweaks" in _row_keys(screen)
        assert screen.status.text == ""
        # A status somebody else wrote survives the same kind of publish.
        screen.status.set("someone else", "warn")
        tweaks.append("other")
        app.request_refresh()
        await settle(app, pilot)
        assert screen.status.text == "someone else"


async def test_a_failed_env_read_on_publish_keeps_rows_and_status(tmp_path: Path) -> None:
    rg = _tool("rg")
    service = frozen_service(tmp_path)
    service.publish([removable_state(rg, [Path("/opt/rg")])])
    failing = {"on": False}

    def bans() -> list[str]:
        if failing["on"]:
            raise OSError("denied")
        return ["pip"]

    app = _app(
        tools=[rg],
        version_refresh=service,
        uninstall=_uninstall_inputs(ban_names=bans),
        initial_view="uninstall",
    )
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        screen.status.set("written", "ok")
        failing["on"] = True
        app.request_refresh()
        await settle(app, pilot)
        assert "#ban" in _row_keys(screen)
        assert screen.status.text == "written"
        screen.status.clear()
        app.request_refresh()
        await settle(app, pilot)
        assert "#ban" in _row_keys(screen)
        assert (screen.status.text, screen.status.severity) == (
            "Could not read the uninstall state: denied.",
            "warn",
        )


async def test_an_l1_brew_row_is_removable_and_names_its_command() -> None:
    """22-07 tracer: a receipt-proven brew package is removable and runs its command."""
    method = Method(kind="brew", params={"formula": "gh"})
    gh = Tool(id="gh", name="gh", category="dev", cmd="gh", methods=(method,), tier="user")
    receipt = Receipt(
        tool="gh",
        at="2026-11-04T00:00:00Z",
        method=ReceiptMethod(kind="brew", key="brew"),
        package="gh",
        artifacts=(),
        smoke=None,
        hooks={},
    )
    removable = RemovalPlan((), (), level="manager", argv=("brew", "uninstall", "gh"))
    state = replace(
        plan_state(gh, owner="brew", package="gh", method=method, removable=removable),
        receipt=receipt,
    )
    captured: list[UninstallDecision] = []
    app = _app(cases=[(gh, state)], uninstall=_uninstall_inputs(remove=_recorder(captured)))
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        assert _uninstall_cell(table, "gh", "via") == "Homebrew"
        assert _uninstall_cell(table, "gh", "removes") == "brew uninstall gh"
        assert screen.detail_text == (
            "installed by this installer through Homebrew: receipt matches "
            "— runs `brew uninstall gh`"
        )
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].argv == {"gh": ("brew", "uninstall", "gh")}
    assert captured[0].paths == {"gh": ()}


async def test_an_l3_row_shows_the_vendor_command_then_the_paths() -> None:
    """22-07: an L3 row names its vendor command, then its proven paths, cut to 40 cells."""
    vend_method = Method(
        kind="script", params={"paths": ["~/.local/bin/vend"], "remove": ["vend", "uninstall"]}
    )
    vend = Tool(id="vend", name="vend", category="dev", cmd="vend", methods=(vend_method,))
    argv = ("/opt/vend/bin/vend", "uninstall", "--force")
    leaf = Path("/opt/vend/bin/vend")
    removable = RemovalPlan((leaf,), (), level="recipe", argv=argv)
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(vend, plan_state(vend, removable=removable))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        removes = _uninstall_cell(table, "vend", "removes")
        assert len(removes) == 40
        assert removes.endswith("…")
        assert "/opt/vend/bin/vend uninstall --force, /opt/vend/bin/vend".startswith(removes[:-1])
        assert _uninstall_cell(table, "vend", "via") == "installer"
        assert screen.detail_text == (
            "installed by this installer: receipt matches — runs "
            "`/opt/vend/bin/vend uninstall --force`, then deletes the proven paths"
        )
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    # The remover gets the argv the row showed, so the post-confirm proof can match it.
    assert len(captured) == 1
    assert captured[0].argv == {"vend": argv}
    assert captured[0].paths == {"vend": (leaf,)}


async def test_the_uninstall_view_decision_carries_unregister() -> None:
    """A11: the row hands the undo it previewed to the same remover the CLI uses."""
    cg_method = Method(
        kind="github_release", params={"repo": "a/codegraph", "asset": "x", "member": "codegraph"}
    )
    cg = Tool(
        id="codegraph",
        name="codegraph",
        category="dev",
        cmd="codegraph",
        methods=(cg_method,),
        postinstall="codegraph-mcp-register",
    )
    leaf = Path("/home/u/.local/bin/codegraph")
    undo = (str(leaf), "uninstall", "--target", "claude,codex", "--location", "global")
    removable = RemovalPlan(
        (leaf,), (), level="artifacts", unregister=(undo,), hook_hosts=("claude", "codex")
    )
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(cg, plan_state(cg, removable=removable))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].unregister == {"codegraph": (undo,)}


# -- 22-10: the per-row "delete config too" toggle (UI-04, D-11) --------------


def _config_tool(tool_id: str, *config_paths: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
        config_paths=config_paths,
    )


def _removable_with_config(tool: Tool, config: Sequence[Path] = ()) -> ToolState:
    """A published removable row whose declared config currently exists as `config`."""
    removable = RemovalPlan((Path(f"/opt/{tool.id}"),), (), config=tuple(config))
    return plan_state(tool, removable=removable)


async def test_c_turns_the_flag_on_and_the_removal_deletes_the_config() -> None:
    """22-10 tracer: `c` marks a removable row; the confirmed removal carries its config."""
    gh = _config_tool("gh", "~/.config/gh")
    config_dir = Path.home() / ".config" / "gh"
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(gh, _removable_with_config(gh, [config_dir]))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("c")
        assert screen.selected == {"gh"}
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {"gh": (config_dir,)}


async def test_an_unflagged_row_sends_no_config() -> None:
    """22-10: a row marked with `space` alone sends no config to the remover."""
    gh = _config_tool("gh", "~/.config/gh")
    config_dir = Path.home() / ".config" / "gh"
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(gh, _removable_with_config(gh, [config_dir]))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {}


def test_config_split_keeps_a_path_another_tool_needs() -> None:
    """22-10 (T-22-24): a shared config path is deleted only when every declarer goes."""
    a = _config_tool("a", "~/.config/shared")
    b = _config_tool("b", "~/.config/shared")
    shared = Path.home() / ".config" / "shared"
    states = {tool.id: _removable_with_config(tool, [shared]) for tool in (a, b)}
    catalog = [a, b]

    def state_of(tool: Tool) -> ToolState | None:
        return states.get(tool.id)

    assert config_split([a], catalog, state_of) == ({}, {"~/.config/shared": ("b",)})
    assert config_split([a, b], catalog, state_of) == ({"a": (shared,), "b": (shared,)}, {})
    # A path missing from the flagged tool's published state is in neither map.
    assert config_split([a], catalog, lambda tool: _removable_with_config(tool)) == ({}, {})


async def test_a_refresh_while_the_modal_is_open_keeps_the_decision(tmp_path: Path) -> None:
    """22-10 (T-22-41, review R1-20): the confirm carries the decision built before it opened."""
    gh = _config_tool("gh", "~/.config/gh")
    config_dir = Path.home() / ".config" / "gh"
    service = frozen_service(tmp_path)
    service.publish([_removable_with_config(gh)])
    captured: list[UninstallDecision] = []
    app = _app(
        tools=[gh],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
        initial_view="uninstall",
        version_refresh=service,
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        await pilot.press("c")
        await pilot.press("enter")  # the confirm opens; the decision is built here
        service.queued = (_removable_with_config(gh, [config_dir]),)
        app.request_refresh()
        await settle(app, pilot)
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {}


async def test_a_flagged_row_shows_c_config_prefix_and_suffix() -> None:
    """22-10: a flagged row reads [c], `config + ` and the deleted-too suffix."""
    gh = _config_tool("gh", "~/.config/gh")
    config_dir = Path.home() / ".config" / "gh"
    app = _app(
        cases=[(gh, _removable_with_config(gh, [config_dir]))],
        uninstall=_uninstall_inputs(remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        kept = f"{LAYOUT_PROOF_NOTE} · config kept: ~/.config/gh (c deletes it too)"
        assert screen.detail_text == kept
        await pilot.press("c")
        sel = table.get_cell("gh", "sel")
        assert (sel.plain, sel.style) == ("[c]", "bold red")
        removes = _uninstall_cell(table, "gh", "removes")
        assert removes.startswith("config + ")
        assert len(removes) <= 40
        assert screen.detail_text == (
            f"{LAYOUT_PROOF_NOTE} · config deleted too: ~/.config/gh (c keeps it)"
        )
        await pilot.press("c")
        assert _uninstall_cell(table, "gh", "sel") == "[x]"
        assert not _uninstall_cell(table, "gh", "removes").startswith("config + ")
        assert screen.detail_text == kept


async def test_declared_config_with_nothing_on_disk_reads_none_on_disk() -> None:
    """22-10 (UI-SPEC empty): the toggle is offered; the suffix reads `none on disk`."""
    gh = _config_tool("gh", "~/.config/gh")
    app = _app(cases=[(gh, _removable_with_config(gh))], uninstall=_uninstall_inputs())
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert (
            screen.detail_text
            == f"{LAYOUT_PROOF_NOTE} · config kept: none on disk (c deletes it too)"
        )
        await pilot.press("c")
        assert screen.detail_text == (
            f"{LAYOUT_PROOF_NOTE} · config deleted too: none on disk (c keeps it)"
        )


async def test_c_explains_why_it_does_nothing() -> None:
    """22-10: `c` answers why on a row it cannot apply to, and changes no mark or flag."""
    rg, yq = _tool("rg"), _tool("yq")
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(rg, removable_state(rg, [Path("/opt/rg")])), (yq, managed_state(yq))],
        uninstall=_uninstall_inputs(has_path_block=True, remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("c")  # rg is removable but declares no config
        assert (screen.status.text, screen.status.severity) == (
            "rg declares no config to delete.",
            "warn",
        )
        await pilot.press("down")  # the "managed elsewhere" section title
        await pilot.press("c")
        assert (screen.status.text, screen.status.severity) == (
            "This row has no config to delete.",
            "warn",
        )
        await pilot.press("down")  # yq, managed elsewhere
        await pilot.press("c")
        assert (screen.status.text, screen.status.severity) == (
            "yq cannot be removed here, so its config stays.",
            "warn",
        )
        await pilot.press("down", "down")  # the environment title, then PATH wiring
        await pilot.press("c")
        assert (screen.status.text, screen.status.severity) == (
            "This row has no config to delete.",
            "warn",
        )
        assert screen.selected == set()
    assert captured == []


def test_the_uninstall_footer_names_c() -> None:
    assert VIEW_BY_NAME["uninstall"].actions == (
        "space mark | enter remove | a all | i invert | c config"
    )


async def test_unmarking_clears_the_flag_and_a_never_sets_one() -> None:
    """22-10 (T-22-24): a flag follows its mark; `a` and `c` never turn a flag on by themselves."""
    gh = _config_tool("gh", "~/.config/gh")
    yq = _config_tool("yq", "~/.config/yq")
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[
            (gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"])),
            (yq, _removable_with_config(yq, [Path.home() / ".config" / "yq"])),
        ],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        await pilot.press("c")  # gh is marked and flagged
        assert _uninstall_cell(table, "gh", "sel") == "[c]"
        await pilot.press("space")  # unmarking gh clears its flag
        assert _uninstall_cell(table, "gh", "sel") == "[ ]"
        assert not _uninstall_cell(table, "gh", "removes").startswith("config + ")
        await pilot.press("a")  # select-all marks every row and sets no flag
        assert _uninstall_cell(table, "gh", "sel") == "[x]"
        assert _uninstall_cell(table, "yq", "sel") == "[x]"
        await pilot.press("c")  # gh flagged again, still marked
        assert _uninstall_cell(table, "gh", "sel") == "[c]"
        await pilot.press("i")  # invert unmarks every row, so gh's flag goes too
        assert screen.selected == set()
        assert _uninstall_cell(table, "gh", "sel") == "[ ]"
        await pilot.press("space")  # gh marked alone: no flag
        assert _uninstall_cell(table, "gh", "sel") == "[x]"
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {}


async def test_c_works_during_a_removal_and_keeps_removing_status() -> None:
    """22-10 (UI-SPEC loading): `c` flags another row while a removal runs and keeps `Removing…`."""
    gh = _config_tool("gh", "~/.config/gh")
    yq = _config_tool("yq", "~/.config/yq")
    remover = HeldRemover(SweepResult(removed=("gh",)))
    app = _app(
        cases=[
            (gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"])),
            (yq, _removable_with_config(yq, [Path.home() / ".config" / "yq"])),
        ],
        uninstall=_uninstall_inputs(remove=remover),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            await pilot.press("5")
            screen = app.screen
            assert isinstance(screen, UninstallScreen)
            table = screen.query_one(DataTable[Any])
            await pilot.press("space")  # gh alone goes to the held removal
            await pilot.press("enter")
            await pilot.press("enter")
            await wait_until(pilot, remover.started.is_set)
            assert (screen.status.text, screen.status.severity) == ("Removing…", "warn")
            await pilot.press("down")  # yq, the next removable row
            await pilot.press("c")
            assert _uninstall_cell(table, "yq", "sel") == "[c]"
            assert (screen.status.text, screen.status.severity) == ("Removing…", "warn")
        finally:
            remover.release.set()
            await settle(app, pilot)


async def test_a_c_refusal_during_a_removal_shows_in_the_detail_bar() -> None:
    """Review C-15: `Removing…` keeps the status line, so the refusal goes to the detail bar."""
    gh = _config_tool("gh", "~/.config/gh")
    rg = _tool("rg")
    plain = RemovalPlan((Path("/opt/rg"),), (), level="artifacts")
    remover = HeldRemover(SweepResult(removed=("gh",)))
    app = _app(
        cases=[
            (gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"])),
            (rg, plan_state(rg, removable=plain)),
        ],
        uninstall=_uninstall_inputs(remove=remover),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        try:
            await pilot.press("5")
            screen = app.screen
            assert isinstance(screen, UninstallScreen)
            await pilot.press("space")  # gh alone goes to the held removal
            await pilot.press("enter")
            await pilot.press("enter")
            await wait_until(pilot, remover.started.is_set)
            await pilot.press("down")  # rg declares no config
            await pilot.press("c")
            assert (screen.status.text, screen.status.severity) == ("Removing…", "warn")
            assert screen.detail_text == "rg declares no config to delete."
        finally:
            remover.release.set()
            await settle(app, pilot)


async def test_a_successful_removal_clears_the_flag_and_a_failed_one_keeps_it() -> None:
    """22-10: a removed row loses its flag with its mark; a failed row keeps both (retry)."""
    gh = _config_tool("gh", "~/.config/gh")
    yq = _config_tool("yq", "~/.config/yq")
    captured: list[UninstallDecision] = []
    result = SweepResult(removed=("gh",), remove_failed=(("yq", "boom"),))
    app = _app(
        cases=[
            (gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"])),
            (yq, _removable_with_config(yq, [Path.home() / ".config" / "yq"])),
        ],
        uninstall=_uninstall_inputs(remove=_recorder(captured, result)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        await pilot.press("c")  # gh
        await pilot.press("down")
        await pilot.press("c")  # yq
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert _uninstall_cell(table, "gh", "sel") == "[ ]"
        assert _uninstall_cell(table, "yq", "sel") == "[c]"
        await pilot.press("up")  # back on gh: its flag left with its mark, so a new mark has none
        await pilot.press("space")
        assert _uninstall_cell(table, "gh", "sel") == "[x]"
    assert len(captured) == 1
    assert set(captured[0].config) == {"gh", "yq"}


async def test_flags_start_off_on_every_visit() -> None:
    """22-10 (T-22-42, review R1-19): a modal keeps the flags; leaving the view clears them."""
    gh = _config_tool("gh", "~/.config/gh")
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"]))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        table = app.view("uninstall").query_one(DataTable[Any])
        await pilot.press("c")
        await pilot.press("ctrl+p")  # the navigation palette covers the view
        await wait_until(pilot, lambda: isinstance(app.screen, NavScreen))
        await pilot.press("escape")  # cancelled: the view is back and the flag stays
        await wait_until(pilot, lambda: not isinstance(app.screen, NavScreen))
        assert _uninstall_cell(table, "gh", "sel") == "[c]"
        await pilot.press("1")  # leaving the view through the one navigation path
        await wait_until(pilot, lambda: app.current_view == "system")
        await pilot.press("5")
        await wait_until(pilot, lambda: app.current_view == "uninstall")
        assert _uninstall_cell(table, "gh", "sel") == "[x]"  # the mark stays; the flag does not
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {}


# -- 22-11: the confirm modal is the review (UI-04, LIFE-08) ------------------


def _confirm(app: App[Any]) -> ConfirmUninstall:
    screen = app.screen
    assert isinstance(screen, ConfirmUninstall)
    return screen


async def test_the_review_lists_exactly_the_paths_the_removal_deletes() -> None:
    """22-11 tracer: the review names each command and the config it deletes, and the
    confirm hands the remover those same paths."""
    gh = _config_tool("gh", "~/.config/gh")
    gh_dir = Path.home() / ".config" / "gh"
    gh_removable = RemovalPlan(
        (Path("/opt/gh"),), (), config=(gh_dir,), level="manager", argv=("brew", "uninstall", "gh")
    )
    vend_method = Method(
        kind="script", params={"paths": ["~/.local/bin/vend"], "remove": ["vend", "uninstall"]}
    )
    vend = Tool(id="vend", name="vend", category="dev", cmd="vend", methods=(vend_method,))
    vend_removable = RemovalPlan(
        (Path("/opt/vend/bin/vend"),),
        (),
        level="recipe",
        argv=("/opt/vend/bin/vend", "uninstall", "--force"),
    )
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[
            (gh, plan_state(gh, removable=gh_removable)),
            (vend, plan_state(vend, removable=vend_removable)),
        ],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("c")  # the highlighted row is gh: flagged, so marked too
        await pilot.press("down")
        await pilot.press("space")  # vend: marked, no config
        await pilot.press("enter")  # the modal opens and shows the review
        await pilot.pause()
        # The order is the order the rows were marked: gh first, then vend.
        assert [line.plain for line in _confirm(app).review] == [
            "gh: runs brew uninstall gh",
            "vend: runs /opt/vend/bin/vend uninstall --force",
            "Config deleted too:",
            "  ~/.config/gh (gh)",
        ]
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {"gh": (gh_dir,)}


async def test_an_empty_review_reads_as_before() -> None:
    """22-11: a review with no runs, no config and no pnpm group reads as Phase 21 did."""
    app = _app(cases=_rg_rows(), uninstall=_uninstall_inputs())
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.pause()
        assert _confirm(app).review == ()
        body = app.screen.query_one("#confirm-body Static", Static)
        assert str(body.render()) == (
            "Remove 1 tool(s)?\n\nThis deletes installed artifacts and is not undoable."
        )
        keys = app.screen.query_one("#confirm-keys", Static)
        assert str(keys.render()) == "enter remove · esc cancel"


async def test_the_review_body_is_plain_text() -> None:
    """22-11 (T-22-27): a config path with markup renders literally, never as style."""
    odd = _config_tool("gh", "~/.config/[red]x[/]")
    odd_dir = Path.home() / ".config" / "[red]x[/]"
    app = _app(
        cases=[(odd, _removable_with_config(odd, [odd_dir]))],
        uninstall=_uninstall_inputs(remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("c")
        await pilot.press("enter")
        await pilot.pause()
        review = _confirm(app).review
        assert "  ~/.config/[red]x[/] (gh)" in [line.plain for line in review]
        assert "[red]x[/]" in str(app.screen.query_one("#confirm-body Static", Static).render())
        assert not any(span.style == "red" for line in review for span in line.spans)


async def _mark_rows(app: App[Any], pilot: Pilot[Any], *marks: tuple[str, bool]) -> None:
    """Mark the named rows in turn; `True` presses `c`, which marks the row and flags its config."""
    table = app.screen.query_one(DataTable[Any])
    for tool_id, flagged in marks:
        table.move_cursor(row=table.get_row_index(tool_id))
        await pilot.pause()
        await pilot.press("c" if flagged else "space")


def _flat(review: Sequence[Text]) -> list[str]:
    """Each review line on one row: a folded line joins back with single spaces."""
    return [" ".join(line.plain.split()) for line in review]


async def test_a_shared_path_is_reviewed_as_kept() -> None:
    """22-11 (UI-SPEC partial): a path another tool still uses is listed as kept, never deleted."""
    a = _config_tool("a", "~/.config/shared")
    b = _config_tool("b", "~/.config/shared")
    shared = Path.home() / ".config" / "shared"
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(a, _removable_with_config(a, [shared])), (b, _removable_with_config(b, [shared]))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("a", True))  # b stays unmarked, so it keeps the path
        await pilot.press("enter")
        await pilot.pause()
        assert [line.plain for line in _confirm(app).review] == [
            "Config deleted too:",
            "  ~/.config/shared kept, also used by b",
        ]
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {}


async def test_unflagged_config_is_reviewed_as_kept() -> None:
    """22-11 (UI-SPEC block 6): a marked tool with config and the flag off reads as kept."""
    gh = _config_tool("gh", "~/.config/gh")
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[(gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"]))],
        uninstall=_uninstall_inputs(remove=_recorder(captured)),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")  # marked, the config flag stays off
        await pilot.press("enter")
        await pilot.pause()
        assert [line.plain for line in _confirm(app).review] == ["Config kept: gh."]
        await pilot.press("enter")
        await settle(app, pilot)
    assert len(captured) == 1
    assert captured[0].config == {}


def _pnpm_tool(tool_id: str, npm_pkg: str, *co_install: str) -> Tool:
    """A tool installed as a pnpm global, optionally a member of a co-install group."""
    method = Method(kind="node", params={"npm_pkg": npm_pkg, "co_install": list(co_install)})
    return Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(method,),
        priority="P1",
        audience="both",
        tier="system",
        desc="",
    )


def _pnpm_removal(tool: Tool, package: str) -> ToolState:
    """A removable row whose only removal is `pnpm remove --global <package>`."""
    removable = RemovalPlan(
        (Path(f"/opt/{tool.id}"),),
        (),
        level="manager",
        argv=("pnpm", "remove", "--global", package),
    )
    return plan_state(tool, removable=removable)


async def test_pnpm_group_lines_in_the_review() -> None:
    """22-11 (LIFE-08, UI-SPEC block 7): one member removed names the others pnpm removes with
    it; every member removed gives one line; a package outside any group gives none."""
    mmdc = _pnpm_tool("mmdc", "@mermaid-js/mermaid-cli", "puppeteer")
    puppeteer = _pnpm_tool("puppeteer", "puppeteer")
    group = [
        (mmdc, _pnpm_removal(mmdc, "@mermaid-js/mermaid-cli")),
        (puppeteer, _pnpm_removal(puppeteer, "puppeteer")),
    ]
    # One member removed: pnpm takes the whole group, and the warning names the others.
    app = _app(cases=group, uninstall=_uninstall_inputs(remove=_recorder([])))
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("mmdc", False))
        await pilot.press("enter")
        await pilot.pause()
        review = _confirm(app).review
        assert _flat(review) == [
            "mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli",
            "Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli removes the whole "
            "group, puppeteer included.",
        ]
        assert any(
            span.style == "yellow" and (span.start, span.end) == (0, 8) for span in review[-1].spans
        )
        await pilot.press("escape")
        await pilot.pause()
    # Every member removed in this run: one line for the group.
    app = _app(cases=group, uninstall=_uninstall_inputs(remove=_recorder([])))
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("mmdc", False), ("puppeteer", False))
        await pilot.press("enter")
        await pilot.pause()
        assert _flat(_confirm(app).review)[-1] == (
            "Warning: pnpm group mmdc: all its members are removed together."
        )
        await pilot.press("escape")
        await pilot.pause()
    # A brew row is in no pnpm group: no warning line.
    rg = _tool("rg")
    brew = RemovalPlan((Path("/opt/rg"),), (), level="manager", argv=("brew", "uninstall", "rg"))
    app = _app(cases=[(rg, plan_state(rg, removable=brew))], uninstall=_uninstall_inputs())
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.pause()
        assert _flat(_confirm(app).review) == ["rg: runs brew uninstall rg"]
        await pilot.press("escape")
        await pilot.pause()


async def test_the_pnpm_group_warning_reads_the_frozen_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review C-13: the warning and the `runs` line both come from the painted decision, so a
    newer state that has not been repainted cannot drop the warning the argv still needs."""
    mmdc = _pnpm_tool("mmdc", "@mermaid-js/mermaid-cli", "puppeteer")
    puppeteer = _pnpm_tool("puppeteer", "puppeteer")
    group = [
        (mmdc, _pnpm_removal(mmdc, "@mermaid-js/mermaid-cli")),
        (puppeteer, _pnpm_removal(puppeteer, "puppeteer")),
    ]
    app = _app(cases=group, uninstall=_uninstall_inputs(remove=_recorder([])))
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("mmdc", False))

        def newer_state(_tool: Tool) -> ToolState | None:
            return None  # a publish that has not been repainted yet

        monkeypatch.setattr(app.screen, "_state_of", newer_state)
        await pilot.press("enter")
        await pilot.pause()
        assert _flat(_confirm(app).review) == [
            "mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli",
            "Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli removes the whole "
            "group, puppeteer included.",
        ]
        await pilot.press("escape")
        await pilot.pause()


async def test_the_review_blocks_come_in_order() -> None:
    """22-11 (UI-SPEC UI Considerations, populated): runs, deleted, kept, config kept, the
    pnpm warning, then the keys line below the body."""
    gh = _config_tool("gh", "~/.config/gh")
    a = _config_tool("a", "~/.config/shared")
    b = _config_tool("b", "~/.config/shared")
    k = _config_tool("k", "~/.config/k")
    mmdc = _pnpm_tool("mmdc", "@mermaid-js/mermaid-cli", "puppeteer")
    puppeteer = _pnpm_tool("puppeteer", "puppeteer")
    shared = Path.home() / ".config" / "shared"
    gh_brew = RemovalPlan(
        (Path("/opt/gh"),),
        (),
        config=(Path.home() / ".config" / "gh",),
        level="manager",
        argv=("brew", "uninstall", "gh"),
    )
    app = _app(
        cases=[
            (gh, plan_state(gh, removable=gh_brew)),
            (a, _removable_with_config(a, [shared])),
            (b, _removable_with_config(b, [shared])),
            (k, _removable_with_config(k, [Path.home() / ".config" / "k"])),
            (mmdc, _pnpm_removal(mmdc, "@mermaid-js/mermaid-cli")),
            (puppeteer, _pnpm_removal(puppeteer, "puppeteer")),
        ],
        uninstall=_uninstall_inputs(remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("gh", True), ("a", True), ("k", False), ("mmdc", False))
        await pilot.press("enter")
        await pilot.pause()
        screen = _confirm(app)
        assert _flat(screen.review) == [
            "gh: runs brew uninstall gh",
            "mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli",
            "Config deleted too:",
            "~/.config/gh (gh)",
            "~/.config/shared kept, also used by b",
            "Config kept: k.",
            "Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli removes the whole "
            "group, puppeteer included.",
        ]
        keys = screen.query_one("#confirm-keys", Static)
        assert str(keys.render()) == "enter remove · esc cancel"
        assert screen.query_one("#confirm-body").region.y < keys.region.y
        await pilot.press("escape")
        await pilot.pause()


async def test_config_result_lines_follow_the_counts() -> None:
    """22-11 (UI-SPEC Removal results): deleted and kept config lines follow the counts."""
    gh = _config_tool("gh", "~/.config/gh")
    uv = _config_tool("uv", "~/.config/uv")
    (Path.home() / ".config" / "uv").mkdir(parents=True)  # still on disk after the removal
    app = _app(
        cases=[
            (gh, _removable_with_config(gh, [Path.home() / ".config" / "gh"])),
            (uv, _removable_with_config(uv, [Path.home() / ".config" / "uv"])),
        ],
        uninstall=_uninstall_inputs(
            remove=lambda _decision: SweepResult(removed=("gh", "uv"), config_deleted=("gh",))
        ),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("gh", True), ("uv", False))  # uv keeps its config
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        screen = app.view("uninstall")
        assert isinstance(screen, UninstallScreen)
        assert screen.status.text == ("2 removed\nConfig deleted for gh.\nConfig kept for uv.")
        assert screen.status.severity is Severity.OK


async def test_the_group_warning_skips_a_member_shown_absent() -> None:
    """22-UAT F-3: the frozen state shows mmdc absent, so removing puppeteer names no one."""
    mmdc = _pnpm_tool("mmdc", "@mermaid-js/mermaid-cli", "puppeteer")
    puppeteer = _pnpm_tool("puppeteer", "puppeteer")
    app = _app(
        cases=[(mmdc, absent_state(mmdc)), (puppeteer, _pnpm_removal(puppeteer, "puppeteer"))],
        uninstall=_uninstall_inputs(remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("puppeteer", False))
        await pilot.press("enter")
        await pilot.pause()
        assert _flat(_confirm(app).review) == ["puppeteer: runs pnpm remove --global puppeteer"]
        await pilot.press("escape")
        await pilot.pause()


async def test_a_member_removed_with_its_group_is_reported_after_the_counts() -> None:
    """22-UAT F-2: removing mmdc only, the run reports puppeteer as gone with the group."""
    mmdc = _pnpm_tool("mmdc", "@mermaid-js/mermaid-cli", "puppeteer")
    puppeteer = _pnpm_tool("puppeteer", "puppeteer")
    app = _app(
        cases=[
            (mmdc, _pnpm_removal(mmdc, "@mermaid-js/mermaid-cli")),
            (puppeteer, _pnpm_removal(puppeteer, "puppeteer")),
        ],
        uninstall=_uninstall_inputs(
            remove=lambda _decision: SweepResult(
                removed=("mmdc", "puppeteer"),
                with_group=("puppeteer: removed with the mmdc group",),
            )
        ),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("mmdc", False))
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        screen = app.view("uninstall")
        assert isinstance(screen, UninstallScreen)
        assert screen.status.text == "2 removed\npuppeteer: removed with the mmdc group"
        assert screen.status.severity is Severity.OK


async def test_a_failed_vendor_remove_keeps_config_and_says_so() -> None:
    """22-11 (UI-SPEC Removal results, error): a failed removal keeps its config and says so."""
    vend = _config_tool("vend", "~/.config/vend")
    failed = SweepResult(
        remove_failed=(("vend", "Error: vend uninstall failed"),),
        config_not_deleted=("vend",),
    )
    app = _app(
        cases=[(vend, _removable_with_config(vend, [Path.home() / ".config" / "vend"]))],
        uninstall=_uninstall_inputs(remove=lambda _decision: failed),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("vend", True))
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        screen = app.view("uninstall")
        assert isinstance(screen, UninstallScreen)
        assert screen.status.severity is Severity.ERROR
        assert screen.status.text.splitlines()[-1] == (
            "Config not deleted for vend: the removal failed."
        )
        table = screen.query_one(DataTable[Any])
        assert _uninstall_cell(table, "vend", "sel") == "[c]"  # the choice survives the failure
        assert "remove failed" in _uninstall_cell(table, "vend", "removes")


async def test_a_config_delete_warning_is_shown() -> None:
    """22-11 (review R1-21): a config delete warning is a warn line, and its absence reads ok."""
    gh = _config_tool("gh", "~/.config/gh")
    gh_dir = Path.home() / ".config" / "gh"
    warned = SweepResult(
        removed=("gh",),
        config_deleted=("gh",),
        warnings=("could not delete config ~/.config/gh — denied",),
    )
    for result, severity, line in (
        (warned, Severity.WARN, "warning: could not delete config ~/.config/gh — denied."),
        (
            SweepResult(removed=("gh",), config_deleted=("gh",)),
            Severity.OK,
            "Config deleted for gh.",
        ),
    ):
        app = _app(
            cases=[(gh, _removable_with_config(gh, [gh_dir]))],
            uninstall=_uninstall_inputs(remove=lambda _decision, result=result: result),
        )
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.press("5")
            await _mark_rows(app, pilot, ("gh", True))
            await pilot.press("enter")
            await pilot.press("enter")
            await settle(app, pilot)
            screen = app.view("uninstall")
            assert isinstance(screen, UninstallScreen)
            assert screen.status.text.splitlines()[-1] == line
            assert screen.status.severity is severity


async def test_status_data_is_literal() -> None:
    """22-11 (T-22-27): a path and an error with markup or escape bytes stay literal in status."""
    odd = _config_tool("gh", "~/.config/[red]x[/]")
    odd_dir = Path.home() / ".config" / "[red]x[/]"
    warned = SweepResult(
        removed=("gh",),
        config_deleted=("gh",),
        warnings=("could not delete config ~/.config/[red]x[/] — \x1b[31mdenied",),
    )
    app = _app(
        cases=[(odd, _removable_with_config(odd, [odd_dir]))],
        uninstall=_uninstall_inputs(remove=lambda _decision: warned),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await _mark_rows(app, pilot, ("gh", True))
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        screen = app.view("uninstall")
        assert isinstance(screen, UninstallScreen)
        assert "could not delete config ~/.config/[red]x[/] — [31mdenied." in screen.status.text
        assert "\x1b" not in screen.status.text


# -- 23-15: the removal review and results (UI-SPEC section 6) -----------------


async def test_confirm_uninstall_lists_the_unregister_line_first() -> None:
    """A24: a hook tool's undo runs before its removal, so its line comes first in block 3."""
    codegraph = _tool("codegraph")
    undo = (
        "/home/u/.local/bin/codegraph",
        "uninstall",
        "--target",
        "claude,codex",
        "--location",
        "global",
        "--yes",
        "--keep-cli",
    )
    removable = RemovalPlan(
        (Path("/opt/codegraph"),), (), unregister=(undo,), hook_hosts=("claude", "codex")
    )
    app = _app(
        cases=[(codegraph, plan_state(codegraph, removable=removable))],
        uninstall=_uninstall_inputs(remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.pause()
        review = [" ".join(line.plain.split()) for line in _confirm(app).review]
        assert review[0] == (
            "codegraph: runs codegraph uninstall --target claude,codex --location global "
            "--yes --keep-cli"
        )


async def test_confirm_uninstall_lists_the_changes_block() -> None:
    """A24/A26: block 3b names the settings a removal reverts and the shell init it turns off."""
    from installer.agent_settings import apply_setting
    from installer.app import HOST_SETTINGS_OS

    apply_setting("claude", "auto-approve", home=Path.home(), platform_os=HOST_SETTINGS_OS)
    claude, starship = _tool("claude"), _tool("starship")
    app = _app(
        cases=[
            (claude, plan_state(claude, removable=RemovalPlan((Path("/opt/claude"),), ()))),
            (starship, plan_state(starship, removable=RemovalPlan((Path("/opt/starship"),), ()))),
        ],
        uninstall=_uninstall_inputs(tweak_ids=("tweak:starship",), remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space", "down", "space")
        await pilot.press("enter")
        await pilot.pause()
        # The review folds long lines with a hanging indent; compare the unfolded text.
        review = [" ".join(line.plain.split()) for line in _confirm(app).review]
        assert (
            "claude: removes permissions.defaultMode, skipDangerousModePermissionPrompt "
            "from ~/.claude/settings.json"
        ) in review
        assert "starship: turns off its shell init in ~/.myshellrc" in review


async def test_uninstall_values_render_literally(monkeypatch: pytest.MonkeyPatch) -> None:
    """A32: a ledger path or key holding markup renders as the text it is, never as style."""
    from installer import app as app_module

    odd = "[red]x[/]"

    def ledger(
        agent: str, *, home: Path
    ) -> tuple[tuple[Path, tuple[str, ...], tuple[str, ...]], ...]:
        return ((Path(f"/cfg/{odd}.json"), (odd,), ()),) if agent == "claude" else ()

    monkeypatch.setattr(app_module, "ledger_preview", ledger)
    claude = _tool("claude")
    app = _app(
        cases=[(claude, plan_state(claude, removable=RemovalPlan((Path("/opt/claude"),), ())))],
        uninstall=_uninstall_inputs(remove=_recorder([])),
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("5")
        await pilot.press("space")
        await pilot.press("enter")
        await pilot.pause()
        review = _confirm(app).review
        # /cfg does not exist, so the line is the missing-file form (CR-02).
        expected = f"claude: cannot remove {odd}: /cfg/{odd}.json"
        assert any(line.plain.startswith(expected) for line in review)
        assert all(not line.spans for line in review if odd in line.plain)


async def test_removal_results_name_unregister_revert_and_shell_init() -> None:
    """A25 (status half): each result names what happened, in the UI-SPEC section 6 wording."""
    codegraph = _tool("codegraph")
    result = SweepResult(
        removed=("codegraph",),
        unregistered=("claude", "codex"),
        settings_reverted=("claude",),
        settings_kept=("codex",),
        shell_init_off=("starship",),
        warnings=("could not revert ~/.codex/config.toml — not valid TOML (line 2)",),
    )
    app = _app(
        cases=[(codegraph, plan_state(codegraph, removable=RemovalPlan((Path("/opt/cg"),), ())))],
        uninstall=_uninstall_inputs(remove=_recorder([], result)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space", "enter", "enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        status = screen.status.text
    for line in (
        "Unregistered from agent hosts: claude, codex.",
        "Settings reverted for claude.",
        "Kept settings you changed since this installer wrote them: codex.",
        "Shell init turned off for starship.",
        "warning: could not revert ~/.codex/config.toml — not valid TOML (line 2).",
    ):
        assert line in status, line


async def test_an_unregister_failure_row_reads_remove_failed() -> None:
    """A25: a failed undo ends the row `remove failed — unregister: …` and deletes nothing."""
    codegraph = _tool("codegraph")
    result = SweepResult(remove_failed=(("codegraph", "unregister: boom"),))
    app = _app(
        cases=[(codegraph, plan_state(codegraph, removable=RemovalPlan((Path("/opt/cg"),), ())))],
        uninstall=_uninstall_inputs(remove=_recorder([], result)),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("5")
        await pilot.press("space", "enter", "enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert screen.detail_text.startswith("remove failed — unregister: boom")


# -- retired receipts in the Uninstall view (23.1-17, UI-SPEC section 2) -------


def _retired_rtk() -> tuple[Tool, Path]:
    """A retired `rtk` raw download: its bin-dir file and receipt, as the live scan lists them."""
    bin_dir = Path.home() / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    rtk = bin_dir / "rtk"
    rtk.write_text("rtk raw binary")
    write_receipt(loop_tool("rtk"), [(rtk, "file")])
    return _scanned("rtk"), rtk


def _scanned(tool_id: str) -> Tool:
    """The retired tool the live scan lists for `tool_id` (every receipt is outside the catalog)."""
    return next(tool for tool in receipts.scan_retired(set()).tools if tool.id == tool_id)


def _removing_closure(
    catalog: Sequence[Tool] = (), commands: list[list[str]] | None = None
) -> Callable[[UninstallDecision], SweepResult]:
    """The production remover (`perform_uninstall`) over the scratch HOME. A command it runs is
    appended to `commands`, so a test can assert that none ran."""
    home = Path.home()
    ran: list[list[str]] = [] if commands is None else commands

    def run(cmd: list[str]) -> None:
        ran.append(cmd)

    def remove(decision: UninstallDecision) -> SweepResult:
        return perform_uninstall(
            decision,
            bin_dir=home / ".local" / "bin",
            myshellrc_path=home / ".myshellrc",
            rc_paths=[],
            bundles=(),
            zshrc_path=home / ".zshrc",
            extra_policies=(),
            runner=run,
            catalog=catalog,
        )

    return remove


def _plant_retired(
    tool_id: str,
    artifacts: Sequence[tuple[Path, str]] = (),
    *,
    kind: str = "github_release",
    package: str | None = None,
) -> Tool:
    """A receipt for `tool_id` (outside the catalog) as the live scan lists it. A `package` makes
    a manager-kind receipt, which lists no paths."""
    if package is None:
        write_receipt(loop_tool(tool_id), list(artifacts), kind=kind)
    else:
        receipts.write(
            Receipt(
                tool=tool_id,
                at="2026-10-16T00:00:00Z",
                method=ReceiptMethod(kind=kind, key="k"),
                package=package,
                artifacts=(),
                smoke=None,
                hooks={},
            )
        )
    return _scanned(tool_id)


async def test_a_retired_receipt_shows_its_own_section() -> None:
    """Tracer: a retired receipt is a selectable row under its own heading after the catalog."""
    rtk, _rtk_bin = _retired_rtk()
    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(retired=lambda: (rtk,)),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        heading = "#retired — no longer in the catalog"
        assert _row_keys(screen) == ["#removable here", "rg", heading, "rtk"]
        table = screen.query_one(DataTable[Any])
        assert _uninstall_cell(table, heading, "tool").strip() == (
            "── retired — no longer in the catalog (1)"
        )
        assert _uninstall_cell(table, "rtk", "tool") == "rtk (retired)"
        await pilot.press("down", "down")
        assert screen.detail_text == (
            "retired: rtk is no longer in the catalog · recorded files re-checked before deletion"
        )


async def test_removing_a_retired_row_deletes_its_file_and_receipt() -> None:
    """Tracer: selecting the retired row and confirming removes its file and receipt; the
    next publish drops the row and its heading."""
    _rtk, rtk_bin = _retired_rtk()
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired(set()).tools,
            remove=_removing_closure(),
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "rtk" in _row_keys(screen)
        await pilot.press("space", "enter", "enter")
        await settle(app, pilot)
        assert not rtk_bin.exists()
        assert not receipts.receipt_exists("rtk")
        assert _row_keys(screen) == []


async def test_no_retired_receipt_means_no_section() -> None:
    """A3 (UI-SPEC E1 empty): with no retired receipt there is no heading and no retired row.

    Regression guard: it passes before the change, because nothing renders without a receipt.
    """
    app = _app(cases=_rg_rows(), uninstall=_uninstall_inputs(), initial_view="uninstall")
    async with app.run_test(size=(80, 20)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _row_keys(screen) == ["#removable here", "rg"]


_RETIRED_HEAD = "retired: rtk is no longer in the catalog"


@pytest.mark.parametrize("case", ["proven-with-stray", "drifted", "manager", "script", "empty"])
async def test_retired_detail_clauses_per_receipt_kind(case: str) -> None:
    """UI-SPEC section 2 detail bar, one clause per receipt kind and proof outcome (R1-48)."""
    home = Path.home()
    bin_file = home / ".local" / "bin" / "rtk"
    bin_file.parent.mkdir(parents=True, exist_ok=True)
    if case == "proven-with-stray":
        stray = home / ".ssh" / "id_test"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("planted key")
        bin_file.write_text("rtk raw binary")
        rtk = _plant_retired("rtk", [(bin_file, "file"), (stray, "file")])
        expected = (
            f"{_RETIRED_HEAD} · recorded files re-checked before deletion"
            f" · remove it yourself: {stray}"
        )
    elif case == "drifted":
        bin_file.write_text("rtk raw binary")
        rtk = _plant_retired("rtk", [(bin_file, "file")])
        bin_file.write_text("rtk raw binary, rewritten since the install")
        expected = f"{_RETIRED_HEAD} · remove it yourself: {bin_file}"
    elif case == "manager":
        rtk = _plant_retired("rtk", kind="brew", package="rtk")
        expected = f"{_RETIRED_HEAD} · remove it yourself: brew rtk"
    elif case == "script":
        leaf = home / ".local" / "opt" / "rtk" / "rtk"
        leaf.parent.mkdir(parents=True)
        leaf.write_text("rtk script leaf")
        rtk = _plant_retired("rtk", [(leaf, "file")], kind="script")
        expected = f"{_RETIRED_HEAD} · remove it yourself: {leaf}"
    else:
        rtk = _plant_retired("rtk")
        expected = f"{_RETIRED_HEAD} · nothing to delete; confirming retires the receipt"
    app = _app(
        cases=[], uninstall=_uninstall_inputs(retired=lambda: (rtk,)), initial_view="uninstall"
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.press("down")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert screen.detail_text == expected


async def test_confirming_a_manager_row_retires_only_the_receipt() -> None:
    """UI-SPEC results: a manager-kind receipt retires alone; its package is named, never run."""
    _plant_retired("rtk", kind="brew", package="rtk")
    commands: list[list[str]] = []
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired(set()).tools,
            remove=_removing_closure(commands=commands),
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        await pilot.press("down", "space", "enter", "enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert (screen.status.text, screen.status.severity) == (
            "Retired the rtk receipt; brew rtk stays installed — remove it yourself.",
            Severity.OK,
        )
    assert commands == []
    assert not receipts.receipt_exists("rtk")


async def test_confirming_an_empty_row_says_nothing_to_delete() -> None:
    """UI-SPEC results: a receipt with nothing recorded retires with the nothing-to-delete line."""
    _plant_retired("rtk")
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired(set()).tools,
            remove=_removing_closure(),
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        await pilot.press("down", "space", "enter", "enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert (screen.status.text, screen.status.severity) == (
            "Retired the rtk receipt; there was nothing to delete.",
            Severity.OK,
        )
    assert not receipts.receipt_exists("rtk")


async def test_a_retired_file_changed_since_the_preview_is_kept() -> None:
    """Prohibition (T-23.1-42): a file rewritten after its row was painted is refused and kept."""
    _rtk, rtk_bin = _retired_rtk()
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired(set()).tools,
            remove=_removing_closure(),
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        rtk_bin.write_text("rewritten after the row was painted")
        await pilot.press("down", "space", "enter", "enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert "changed since the preview" in screen.status.text
    assert rtk_bin.read_text() == "rewritten after the row was painted"
    assert receipts.receipt_exists("rtk")


async def test_retired_rows_offer_removal_only() -> None:
    """Prohibition (T-23.1-43): no install, update or reinstall wording in the section, the detail
    bars or the result lines."""
    _plant_retired("rtk", kind="brew", package="rtk")
    _plant_retired("zeta")
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired(set()).tools,
            remove=_removing_closure(),
        ),
        initial_view="uninstall",
    )
    shown: list[str] = []
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        shown += [str(cell) for key in _row_keys(screen) for cell in table.get_row(key)]
        for _ in range(2):
            await pilot.press("down")
            shown.append(screen.detail_text)
        await pilot.press("home", "space", "enter", "enter")
        await settle(app, pilot)
        shown.append(screen.status.text)
    text = " ".join(shown)
    assert not re.search(r"\b(install|update|reinstall)\b|pnpm dlx", text), text


async def test_a_retired_row_and_a_catalog_row_are_removed_together() -> None:
    """Review R1-57: one confirm, one removal pass and one publish remove a catalog row and a
    retired row together, and the retired heading goes with them."""
    catalog_tool, catalog_bin = plant_raw_yq(Path.home())
    catalog_file = catalog_bin / "yq"
    _rtk, rtk_bin = _retired_rtk()
    app = _app(
        cases=[(catalog_tool, removable_state(catalog_tool, [catalog_file]))],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired({"yq"}).tools,
            remove=_removing_closure(catalog=[catalog_tool]),
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        await pilot.press("space", "down", "down", "space", "enter", "enter")
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert not catalog_file.exists()
        assert not rtk_bin.exists()
        assert not receipts.receipt_exists("yq")
        assert not receipts.receipt_exists("rtk")
        assert not any(key.startswith("#retired") or key == "rtk" for key in _row_keys(screen))


# -- retired receipts: confirm lines, keys, sanitizing, refresh, order and scroll (Task 3) -----

_RETIRED_KEY = "#retired — no longer in the catalog"


async def test_c_on_a_retired_row_is_refused() -> None:
    """UI-SPEC section 2 keys: `c` on a retired row is refused with the no-config line."""
    _plant_retired("rtk", kind="brew", package="rtk")
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(retired=lambda: receipts.scan_retired(set()).tools),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        await pilot.press("down", "c")
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert (screen.status.text, screen.status.severity) == (
            "This row has no config to delete.",
            Severity.WARN,
        )
        assert screen.selected == set()


@pytest.mark.parametrize("case", ["artifact-with-stray", "manager", "nothing"])
async def test_confirm_lists_retired_lines_in_the_existing_structure(case: str) -> None:
    """A selected retired row adds lines to the review in the shape a catalog row's runs line
    already has (`<id>: ...`), and no block heading: deleted paths, kept paths and the manager
    package as `remove it yourself`, and nothing-to-delete. Orchestrator decision, 23.1-17 Task 3.
    """
    home = Path.home()
    bin_file = home / ".local" / "bin" / "rtk"
    bin_file.parent.mkdir(parents=True, exist_ok=True)
    if case == "artifact-with-stray":
        stray = home / ".ssh" / "id_test"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("planted key")
        bin_file.write_text("rtk raw binary")
        _plant_retired("rtk", [(bin_file, "file"), (stray, "file")])
        expected = [f"rtk: deletes {bin_file}", f"rtk: remove it yourself: {stray}"]
    elif case == "manager":
        _plant_retired("rtk", kind="brew", package="rtk")
        expected = ["rtk: remove it yourself: brew rtk"]
    else:
        _plant_retired("rtk")
        expected = ["rtk: nothing to delete; confirming retires the receipt"]
    captured: list[UninstallDecision] = []
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(
            retired=lambda: receipts.scan_retired(set()).tools,
            remove=_recorder(captured),
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        await pilot.press("down", "space", "enter")
        await pilot.pause()
        # The review folds long lines at its column (a long path can break mid-word), so each line
        # is compared without whitespace; the count, the order and the characters are exact.
        folded = [line.plain for line in _confirm(app).review]
        assert [re.sub(r"\s", "", line) for line in folded] == [
            re.sub(r"\s", "", line) for line in expected
        ]
        await pilot.press("escape")
        await pilot.pause()
    assert captured == []


async def test_retired_text_renders_literally() -> None:
    """T-23.1-41: receipt-derived path text with markup and an escape renders literally, the
    escape byte removed from the detail bar and every cell. (A receipt id cannot carry these:
    receipts only lists ids matching TOOL_ID_RE, so the id cell is sanitized as defense in depth.)
    """
    home = Path.home()
    bin_file = home / ".local" / "bin" / "rtk"
    bin_file.parent.mkdir(parents=True, exist_ok=True)
    bin_file.write_text("rtk raw binary")
    stray_dir = home / ".ssh"
    stray_dir.mkdir(parents=True, exist_ok=True)
    stray = stray_dir / "[red]stray\x1b[31m"
    stray.write_text("planted")
    _plant_retired("rtk", [(bin_file, "file"), (stray, "file")])
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(retired=lambda: receipts.scan_retired(set()).tools),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        assert _uninstall_cell(table, "rtk", "tool") == "rtk (retired)"
        await pilot.press("down")
        assert screen.detail_text == (
            f"{_RETIRED_HEAD} · recorded files re-checked before deletion"
            f" · remove it yourself: {stray_dir}/[red]stray[31m"
        )
        row_text = " ".join(str(cell) for cell in table.get_row("rtk"))
        assert "[red]" in screen.detail_text
        assert "\x1b" not in screen.detail_text
        assert "\x1b" not in row_text


async def test_retired_rows_follow_the_predicate_on_entry_and_publish() -> None:
    """The live predicate is re-read on entry and on every publish (D-09, UI-SPEC E2 error)."""
    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(retired=lambda: receipts.scan_retired(set()).tools),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _row_keys(screen) == ["#removable here", "rg"]
        _plant_retired("rtk")
        screen.enter_view()
        assert _row_keys(screen) == ["#removable here", "rg", _RETIRED_KEY, "rtk"]
        receipts.delete("rtk")
        screen.state_refreshed()
        assert _row_keys(screen) == ["#removable here", "rg"]


async def test_retired_rows_sort_by_id_after_the_catalog() -> None:
    """SPEC edge R3: retired rows sort by id after every catalog row and before the environment."""
    _plant_retired("zeta")
    _plant_retired("alpha")
    app = _app(
        cases=_rg_rows(),
        uninstall=_uninstall_inputs(
            ban_names=["pip"],
            retired=lambda: receipts.scan_retired(set()).tools,
        ),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)):
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        assert _row_keys(screen) == [
            "#removable here",
            "rg",
            _RETIRED_KEY,
            "alpha",
            "zeta",
            "#environment",
            "#ban",
        ]


async def test_many_retired_rows_scroll_at_80x20() -> None:
    """UI-SPEC E1 overflow: 30 retired rows at 80x20; the last row and the heading are reachable."""
    for index in range(30):
        _plant_retired(f"tool{index:02d}")
    app = _app(
        cases=[],
        uninstall=_uninstall_inputs(retired=lambda: receipts.scan_retired(set()).tools),
        initial_view="uninstall",
    )
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        table = screen.query_one(DataTable[Any])
        assert _RETIRED_KEY in _row_keys(screen)
        assert cell_len(_uninstall_cell(table, _RETIRED_KEY, "tool")) <= 78
        # The cursor starts on the first retired row; `down` reaches the last one, and the table
        # binds `end` and `home` to scrolling the viewport.
        await pilot.press(*["down"] * 29)
        assert screen.detail_text.startswith("retired: tool29 is no longer in the catalog")
        await pilot.press("end")
        assert table.scroll_y == table.max_scroll_y > 0
        # The heading is the first row of the table, above every retired row.
        assert table.get_row_index(_RETIRED_KEY) == 0
