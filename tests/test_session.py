import inspect
import io
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast, get_args

import pytest
from rich.console import Console

import installer.engine as engine
import installer.session as session_module
from installer import agent_settings, executors, postinstall, receipts
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import InstallStatus
from installer.guards import REDIRECT_SENTINEL
from installer.model import (
    ConfigStep,
    ConfigStepKind,
    Method,
    Tool,
    load_tools,
)
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.render import render_done_notes, render_run_report, render_shell_section
from installer.run import CommandError, Runner
from installer.session import (
    RESULT_WORDS,
    WORDS,
    Disposition,
    MismatchChoice,
    OnMismatch,
    PlanRow,
    Result,
    RowOutcome,
    RunContext,
    SensitiveInstall,
    execute_plan,
    exit_code,
    first_line,
    order_for_install,
    ran_anything,
    retained,
    review_counts,
    summary_counts,
)
from installer.update import UpdateOutcome, UpdateService
from installer.versions import TagResolver
from tests.state_doubles import RunRecorder, ScriptedUpdates


def _tool(tool_id: str, priority: str = "P3", *, requires: tuple[str, ...] = ()) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority=priority,
        requires=requires,
    )


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


def _run_context(
    recorder: RunRecorder,
    *,
    catalog: Mapping[str, Tool] | None = None,
    confirm_sensitive: ConfirmSensitiveAction | None = None,
    on_mismatch: OnMismatch | None = None,
    updates: UpdateService | None = None,
    runner: Runner | None = None,
    terminal_sync: Callable[[], str | None] | None = None,
    should_continue: Callable[[], bool] | None = None,
    on_row_started: Callable[[PlanRow], None] | None = None,
    on_outcome: Callable[[RowOutcome], None] | None = None,
) -> RunContext:
    return RunContext(
        catalog=catalog or {},
        platform=_platform(),
        runner=recorder.runner if runner is None else runner,
        resolve_tag=lambda _repo: "1.0.0",
        install=recorder.install,
        updates=updates,
        terminal_sync=recorder.terminal_sync if terminal_sync is None else terminal_sync,
        confirm_sensitive=confirm_sensitive,
        on_mismatch=on_mismatch,
        should_continue=should_continue,
        on_row_started=on_row_started,
        on_outcome=on_outcome,
    )


def test_execute_plan_returns_one_outcome_per_row_in_plan_order():
    recorder = RunRecorder()
    rows = [
        PlanRow("fd", Disposition.INSTALL, "not installed"),
        PlanRow("rg", Disposition.SKIP, "already current"),
        PlanRow("jq", Disposition.BLOCKED, "needs z"),
    ]
    outcomes = execute_plan(
        rows,
        _run_context(recorder, catalog={tool_id: _tool(tool_id) for tool_id in ("fd", "rg", "jq")}),
    )
    assert [outcome.result for outcome in outcomes] == ["done", "skipped", "blocked"]
    assert [outcome.row.tool_id for outcome in outcomes] == ["fd", "rg", "jq"]
    assert recorder.installs == [("fd", False)]
    assert outcomes[0].install is not None
    assert outcomes[0].install.status.value == "installed"


def test_execute_plan_rows_and_context_remain_positional():
    params = inspect.signature(execute_plan).parameters
    positional = [
        name
        for name, value in params.items()
        if value.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    assert positional == ["rows", "ctx"]


def test_execute_plan_passes_run_context_dependencies_to_install():
    tool = _tool("rg")
    catalog = {"rg": tool}
    platform = _platform()

    def runner(_command: list[str]) -> None:
        return None

    def resolve_tag(_repo: str) -> str:
        return "1.0.0"

    seen: list[tuple[Tool, Platform, Runner, TagResolver]] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        assert checksum_policy == "fail"
        assert confirm_sensitive_action is None
        seen.append((tool, platform, runner, resolve_tag))
        return InstallOutcome(tool.id, "installed")

    context = RunContext(
        catalog=catalog,
        platform=platform,
        runner=runner,
        resolve_tag=resolve_tag,
        install=install,
    )
    outcomes = execute_plan([PlanRow("rg", Disposition.INSTALL, "")], context)

    assert outcomes[0].result == "done"
    assert len(seen) == 1
    actual_tool, actual_platform, actual_runner, actual_resolve_tag = seen[0]
    assert actual_tool is tool
    assert actual_platform is platform
    assert actual_runner is runner
    assert actual_resolve_tag is resolve_tag


def test_execute_plan_refuses_a_plan_with_a_wait_row():
    recorder = RunRecorder()
    with pytest.raises(ValueError):
        execute_plan([PlanRow("rg", Disposition.WAIT, "")], _run_context(recorder))
    assert recorder.installs == []


def test_repair_and_reinstall_rows_force_repair():
    recorder = RunRecorder()
    rows = [
        PlanRow("rg", Disposition.REPAIR, "broken"),
        PlanRow("fd", Disposition.REINSTALL, "again"),
        PlanRow("jq", Disposition.INSTALL, "missing"),
    ]
    outcomes = execute_plan(
        rows,
        _run_context(recorder, catalog={tool_id: _tool(tool_id) for tool_id in ("rg", "fd", "jq")}),
    )
    assert recorder.installs == [("rg", True), ("fd", True), ("jq", False)]
    assert summary_counts(outcomes) == "1 installed, 1 repaired, 1 reinstalled"


def test_force_repair_composes_under_sensitive_confirm():
    recorder = RunRecorder()

    def confirm(_tool: str, _action: str) -> bool:
        return True

    outcomes = execute_plan(
        [
            PlanRow("rg", Disposition.REINSTALL, "again"),
            PlanRow("fd", Disposition.INSTALL, "missing"),
        ],
        _run_context(
            recorder,
            catalog={tool_id: _tool(tool_id) for tool_id in ("rg", "fd")},
            confirm_sensitive=confirm,
        ),
    )
    assert [outcome.result for outcome in outcomes] == ["done", "done"]
    assert recorder.installs == [("rg", True), ("fd", False)]
    assert recorder.confirms == [confirm, confirm]


@pytest.mark.parametrize(
    "result",
    [
        "done",
        "failed",
        "mismatch",
        "dependency_failed",
        "not_attempted",
        "crashed",
        "skipped",
        "blocked",
        "manual",
    ],
)
def test_exit_code_retained_and_ran_anything_are_pure_views_of_the_list(result: str):
    row = PlanRow("rg", Disposition.INSTALL, "")
    outcome = RowOutcome(row, cast(Result, result))
    failures = {"failed", "mismatch", "dependency_failed", "not_attempted", "crashed"}
    assert exit_code([outcome]) == (1 if result in failures else 0)
    assert retained([outcome]) == ({"rg"} if result in failures | {"blocked", "manual"} else set())
    assert ran_anything([outcome]) is (result in {"done", "failed", "mismatch", "crashed"})


def test_blocked_plus_done_exits_zero_and_failed_exits_one():
    assert (
        exit_code(
            [
                RowOutcome(PlanRow("a", Disposition.BLOCKED, ""), "blocked"),
                RowOutcome(PlanRow("b", Disposition.INSTALL, ""), "done"),
            ]
        )
        == 0
    )
    assert exit_code([RowOutcome(PlanRow("a", Disposition.INSTALL, ""), "failed")]) == 1


def test_summary_counts_fixed_order_and_nothing_selected():
    outcomes = [
        RowOutcome(PlanRow("a", Disposition.INSTALL, ""), "done"),
        RowOutcome(PlanRow("b", Disposition.INSTALL, ""), "done"),
        RowOutcome(PlanRow("c", Disposition.UPDATE, ""), "done"),
        *[RowOutcome(PlanRow(str(i), Disposition.SKIP, ""), "skipped") for i in range(3)],
        RowOutcome(PlanRow("f", Disposition.INSTALL, ""), "failed"),
    ]
    assert summary_counts(outcomes) == "2 installed, 1 updated, 3 skipped, 1 failed"
    assert summary_counts([]) == "nothing selected"


def test_update_row_runs_through_the_update_service_with_the_rows_ownership():
    from installer.ownership import ManagerOwnership

    ownership = ManagerOwnership(
        tool_id="jq",
        owner="brew",
        method=None,
        package="jq",
        current_version="1",
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    updates = ScriptedUpdates({"jq": UpdateOutcome("jq", "updated", "brew")})
    recorder = RunRecorder()
    row = PlanRow("jq", Disposition.UPDATE, "1 -> 2", ownership=ownership)
    outcomes = execute_plan(
        [row],
        _run_context(recorder, catalog={"jq": _tool("jq")}, updates=updates),
    )
    assert outcomes[0].result == "done"
    assert outcomes[0].update is not None and outcomes[0].update.status == "updated"
    assert updates.targets[0].ownership is ownership
    assert recorder.installs == []


@pytest.mark.parametrize("status", ["unknown-owner", "unsupported"])
def test_update_refused_at_run_time_is_blocked_with_the_detail(
    status: Literal["unknown-owner", "unsupported"],
):
    from installer.ownership import ManagerOwnership

    ownership = ManagerOwnership(
        tool_id="jq",
        owner="brew",
        method=None,
        package="jq",
        current_version="1",
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    expected = UpdateOutcome("jq", status, "brew", detail="refused")
    outcomes = execute_plan(
        [PlanRow("jq", Disposition.UPDATE, "", ownership=ownership)],
        _run_context(
            RunRecorder(),
            catalog={"jq": _tool("jq")},
            updates=ScriptedUpdates({"jq": expected}),
        ),
    )
    assert outcomes[0].result == "blocked"
    assert outcomes[0].detail == "refused"


def test_a_headless_update_row_on_a_pinned_app_reads_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIFE-05: the engine's pinned refusal is the headless answer; nothing is downloaded."""
    from installer.ownership import ManagerOwnership

    pinned = Method(
        kind="app",
        params={
            "app": "draw.io.app",
            "url": "https://example.test/drawio-{ver}.dmg",
            "version": "26.0.2",
            "sha256": "0" * 64,
        },
    )

    def no_download(method: object, runner: object) -> None:
        raise AssertionError("a pinned app must not be re-downloaded")

    monkeypatch.setattr("installer.apps.update_app", no_download)
    ownership = ManagerOwnership(
        tool_id="drawio-desktop",
        owner="installer",
        method=pinned,
        package=None,
        current_version="26.0.2",
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate="installer",
        active_path=None,
        unknown_reason=None,
    )
    updates = UpdateService(
        platform=_platform(),
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "1.0.0",
        managed_packages=lambda: (),
        replay_globals=lambda packages: tuple(packages),
        reresolve_ownership=lambda _tool: ownership,
    )
    outcomes = execute_plan(
        [PlanRow("drawio-desktop", Disposition.UPDATE, "", ownership=ownership)],
        _run_context(
            RunRecorder(),
            catalog={"drawio-desktop": _tool("drawio-desktop")},
            updates=updates,
        ),
    )
    assert outcomes[0].result == "blocked"
    assert outcomes[0].detail == "pinned; update outside or re-pin"


def test_update_latch_refusal_is_blocked():
    from installer.ownership import ManagerOwnership

    ownership = ManagerOwnership(
        tool_id="jq",
        owner="brew",
        method=None,
        package="jq",
        current_version="1",
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    updates = ScriptedUpdates({})
    assert updates.begin("rg")
    outcomes = execute_plan(
        [PlanRow("jq", Disposition.UPDATE, "", ownership=ownership)],
        _run_context(RunRecorder(), catalog={"jq": _tool("jq")}, updates=updates),
    )
    assert outcomes[0].result == "blocked"
    assert outcomes[0].detail == "update already in flight for rg"
    updates.end()


@pytest.mark.parametrize("disposition", [Disposition.UPDATE, Disposition.RECONFIGURE])
def test_a_failed_prerequisite_stops_a_present_dependents_update_or_reconfigure(
    disposition: Disposition,
):
    from installer.ownership import ManagerOwnership

    dependency = _tool("dep")
    middle = _tool("mid", requires=("dep",))
    leaf = _tool("leaf", requires=("mid",))
    ownership = ManagerOwnership(
        tool_id="mid",
        owner="brew",
        method=None,
        package="mid",
        current_version="1",
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    updates = ScriptedUpdates({"mid": UpdateOutcome("mid", "updated", "brew")})
    recorder = RunRecorder({"dep": InstallOutcome("dep", "failed")})
    synced: list[str] = []
    middle_row = (
        PlanRow("mid", disposition, "update", ownership=ownership)
        if disposition is Disposition.UPDATE
        else _reconfigure_row("mid", ConfigStep("sync terminals", "terminal_sync"))
    )
    outcomes = execute_plan(
        [
            PlanRow("dep", Disposition.INSTALL, "missing"),
            middle_row,
            PlanRow("leaf", Disposition.INSTALL, "missing"),
        ],
        replace(
            _run_context(
                recorder,
                catalog={"dep": dependency, "mid": middle, "leaf": leaf},
                updates=updates,
            ),
            terminal_sync=lambda: synced.append("sync"),
        ),
    )

    assert [outcome.result for outcome in outcomes] == ["failed", "dependency_failed", "done"]
    assert outcomes[1].install is not None
    assert outcomes[1].install.blocked_by == ("dep",)
    assert updates.targets == []
    assert synced == []
    assert recorder.installs == [("dep", False), ("leaf", False)]


@pytest.mark.parametrize(
    "status, expected",
    [
        (InstallStatus.MANUAL_REQUIRED, "done"),
        (InstallStatus.NO_METHOD, "done"),
        (InstallStatus.FAILED, "dependency_failed"),
        (InstallStatus.CHECKSUM_MISMATCH, "dependency_failed"),
    ],
)
def test_a_reinstall_that_changed_nothing_leaves_the_tool_resolved(
    status: InstallStatus, expected: str
):
    recorder = RunRecorder({"dep": InstallOutcome("dep", status)})
    outcomes = execute_plan(
        [
            PlanRow("dep", Disposition.REINSTALL, "reinstall"),
            PlanRow("user", Disposition.INSTALL, "missing"),
        ],
        _run_context(
            recorder,
            catalog={"dep": _tool("dep"), "user": _tool("user", requires=("dep",))},
        ),
    )

    assert outcomes[1].result == expected
    if expected == "dependency_failed":
        assert outcomes[1].install is not None
        assert outcomes[1].install.blocked_by == ("dep",)


def test_update_failure_does_not_block_a_dependent():
    from installer.ownership import ManagerOwnership

    ownership = ManagerOwnership(
        tool_id="node",
        owner="brew",
        method=None,
        package="node",
        current_version="1",
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    tools = {"node": _tool("node"), "mmdc": _tool("mmdc", requires=("node",))}
    updates = ScriptedUpdates({"node": UpdateOutcome("node", "failed", "brew", "failed")})
    recorder = RunRecorder()
    outcomes = execute_plan(
        [
            PlanRow("node", Disposition.UPDATE, "", ownership=ownership),
            PlanRow("mmdc", Disposition.INSTALL, ""),
        ],
        _run_context(recorder, catalog=tools, updates=updates),
    )
    assert [outcome.result for outcome in outcomes] == ["failed", "done"]
    assert exit_code(outcomes) == 1


def test_install_failure_blocks_dependents_but_not_unrelated_rows():
    dependency_pairs = (("a", ""), ("b", "a"), ("c", "b"))
    tools = {
        tool_id: _tool(tool_id, requires=(requires,) if requires else ())
        for tool_id, requires in dependency_pairs
    }
    tools["rg"] = _tool("rg")
    recorder = RunRecorder({"a": InstallOutcome("a", "failed")})
    outcomes = execute_plan(
        [PlanRow(tool_id, Disposition.INSTALL, "") for tool_id in ("a", "b", "c", "rg")],
        _run_context(recorder, catalog=tools),
    )
    assert [outcome.result for outcome in outcomes] == [
        "failed",
        "dependency_failed",
        "dependency_failed",
        "done",
    ]
    assert outcomes[1].install is not None and outcomes[1].install.blocked_by == ("a",)
    assert recorder.installs == [("a", False), ("rg", False)]


@pytest.mark.parametrize(
    "choice, calls, policies",
    [
        ("retry", 3, ["fail", "fail", "fail"]),
        ("skip", 1, ["fail"]),
        ("fallback", 3, ["fail", "continue", "fail"]),
    ],
)
def test_execute_plan_mismatch_retry_skip_and_fallback(
    choice: MismatchChoice, calls: int, policies: list[str]
):
    from installer.enums import InstallStatus

    seen: list[ChecksumPolicy] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        seen.append(checksum_policy)
        status = InstallStatus.CHECKSUM_MISMATCH if len(seen) == 1 else InstallStatus.INSTALLED
        return InstallOutcome(tool.id, status)

    tools = {"rg": _tool("rg")}
    catalog = {**tools, "user": _tool("user", requires=("rg",))}
    outcomes = execute_plan(
        [
            PlanRow("rg", Disposition.INSTALL, ""),
            PlanRow("user", Disposition.INSTALL, ""),
        ],
        RunContext(
            catalog=catalog,
            platform=_platform(),
            runner=lambda _cmd: None,
            resolve_tag=lambda _repo: "1",
            install=install,
            on_mismatch=lambda _id: choice,
        ),
    )
    assert len(seen) == calls
    assert seen == policies
    assert [outcome.result for outcome in outcomes] == (
        ["mismatch", "dependency_failed"] if choice == "skip" else ["done", "done"]
    )


def test_execute_plan_does_not_prompt_for_a_clean_install():
    asked: list[str] = []

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "skip"

    recorder = RunRecorder()
    outcomes = execute_plan(
        [PlanRow("rg", Disposition.INSTALL, "")],
        _run_context(recorder, catalog={"rg": _tool("rg")}, on_mismatch=on_mismatch),
    )
    assert outcomes[0].result == "done"
    assert asked == []


@pytest.mark.parametrize(
    "error, expected",
    [
        (RuntimeError("boom\nsecond line"), "RuntimeError: boom"),
        (RuntimeError(), "RuntimeError failed"),
        (RuntimeError("\nx"), "RuntimeError failed"),
    ],
)
def test_a_crash_detail_is_the_type_and_the_first_line(error: Exception, expected: str):
    recorder = RunRecorder({"a": error})
    outcomes = execute_plan(
        [PlanRow("a", Disposition.INSTALL, "missing")],
        _run_context(recorder, catalog={"a": _tool("a")}),
    )
    assert outcomes[0].result == "crashed"
    assert outcomes[0].detail == expected


def test_a_crashing_row_is_crashed_and_the_rest_not_attempted():
    recorder = RunRecorder({"a": RuntimeError("boom")})
    tools = {tool_id: _tool(tool_id) for tool_id in ("a", "b", "c")}
    outcomes = execute_plan(
        [
            PlanRow("a", Disposition.INSTALL, ""),
            PlanRow("b", Disposition.INSTALL, ""),
            PlanRow("c", Disposition.SKIP, ""),
        ],
        _run_context(recorder, catalog=tools),
    )
    assert [outcome.result for outcome in outcomes] == ["crashed", "not_attempted", "skipped"]
    assert outcomes[0].detail == "RuntimeError: boom"
    assert exit_code(outcomes) == 1
    assert retained(outcomes) == {"a", "b"}


def test_should_continue_false_marks_the_rest_not_attempted():
    checks = iter([True, False])
    recorder = RunRecorder()
    tools = {tool_id: _tool(tool_id) for tool_id in ("a", "b", "c")}
    outcomes = execute_plan(
        [PlanRow(tool_id, Disposition.INSTALL, "") for tool_id in ("a", "b", "c")],
        _run_context(recorder, catalog=tools, should_continue=lambda: next(checks)),
    )
    assert [outcome.result for outcome in outcomes] == ["done", "not_attempted", "not_attempted"]


def test_should_continue_is_checked_before_dependency_blocking():
    checks = iter([True, False])
    tools = {"dep": _tool("dep"), "user": _tool("user", requires=("dep",))}
    recorder = RunRecorder({"dep": InstallOutcome("dep", "failed")})
    outcomes = execute_plan(
        [PlanRow("dep", Disposition.INSTALL, ""), PlanRow("user", Disposition.INSTALL, "")],
        _run_context(recorder, catalog=tools, should_continue=lambda: next(checks)),
    )
    assert [outcome.result for outcome in outcomes] == ["failed", "not_attempted"]
    assert recorder.installs == [("dep", False)]


def test_on_row_started_and_on_outcome_fire_in_plan_order():
    recorder = RunRecorder()
    started: list[str] = []
    finished: list[str] = []
    tools = {tool_id: _tool(tool_id) for tool_id in ("a", "b")}
    outcomes = execute_plan(
        [PlanRow("a", Disposition.INSTALL, ""), PlanRow("b", Disposition.SKIP, "")],
        _run_context(
            recorder,
            catalog=tools,
            on_row_started=lambda row: started.append(row.tool_id),
            on_outcome=lambda outcome: finished.append(outcome.row.tool_id),
        ),
    )
    assert started == ["a"]
    assert finished == ["a", "b"]
    assert [outcome.row.tool_id for outcome in outcomes] == ["a", "b"]


def test_a_raising_on_row_started_callback_crashes_that_row_only():
    recorder = RunRecorder()
    tools = {tool_id: _tool(tool_id) for tool_id in ("a", "b")}

    def started(row: PlanRow) -> None:
        if row.tool_id == "a":
            raise RuntimeError("ui")

    outcomes = execute_plan(
        [PlanRow("a", Disposition.INSTALL, ""), PlanRow("b", Disposition.INSTALL, "")],
        _run_context(recorder, catalog=tools, on_row_started=started),
    )
    assert [outcome.result for outcome in outcomes] == ["crashed", "not_attempted"]
    assert outcomes[0].detail == "RuntimeError: ui"
    assert recorder.installs == []


def _reconfigure_row(tool_id: str, *steps: ConfigStep) -> PlanRow:
    return PlanRow(
        tool_id, Disposition.RECONFIGURE, "duplicate: gsd-core in project scope", steps=steps
    )


def test_reconfigure_runs_steps_in_order_and_is_done():
    """One event list pins the callback-before-the-first-step order (the TUI's set_tool seam)."""
    events: list[object] = []

    def sync() -> None:
        events.append("sync")

    recorder = RunRecorder()
    steps = (
        ConfigStep("sync terminals", "terminal_sync"),
        ConfigStep("sync again", "terminal_sync"),
    )
    outcomes = execute_plan(
        [_reconfigure_row("gsd", *steps)],
        replace(
            _run_context(
                recorder,
                catalog={"gsd": _tool("gsd")},
                on_row_started=lambda row: events.append(row.tool_id),
            ),
            terminal_sync=sync,
        ),
    )
    assert events == ["gsd", "sync", "sync"]
    assert outcomes[0].result == "done"
    assert outcomes[0].detail == ""
    assert summary_counts(outcomes) == "1 reconfigured"


def test_reconfigure_stops_at_the_first_failing_step():
    synced: list[str] = []

    def failing_sync() -> None:
        synced.append("sync")
        raise RuntimeError("sync refused")

    recorder = RunRecorder()
    steps = (
        ConfigStep("sync terminals", "terminal_sync"),
        ConfigStep("sync again", "terminal_sync"),
    )
    outcomes = execute_plan(
        [_reconfigure_row("gsd", *steps)],
        replace(_run_context(recorder, catalog={"gsd": _tool("gsd")}), terminal_sync=failing_sync),
    )
    assert outcomes[0].result == "failed"
    assert outcomes[0].detail.startswith(f"{steps[0].text}: ")
    assert "sync refused" in outcomes[0].detail
    assert synced == ["sync"]


def test_reconfigure_failure_does_not_block_a_dependent():
    def failing_sync() -> None:
        raise RuntimeError("sync refused")

    recorder = RunRecorder()
    step = ConfigStep("sync terminals", "terminal_sync")
    outcomes = execute_plan(
        [_reconfigure_row("a", step), PlanRow("b", Disposition.INSTALL, "not installed")],
        replace(
            _run_context(
                recorder,
                catalog={"a": _tool("a"), "b": _tool("b", requires=("a",))},
            ),
            terminal_sync=failing_sync,
        ),
    )
    assert [outcome.result for outcome in outcomes] == ["failed", "done"]
    assert recorder.installs == [("b", False)]


def _codegraph_tool() -> Tool:
    return Tool(
        id="codegraph",
        name="codegraph",
        category="ai",
        cmd="codegraph",
        methods=(Method(kind="github_release", params={}),),
        tier="ai",
        postinstall="codegraph-mcp-register",
    )


def _codegraph_receipt(hooks: Mapping[str, tuple[str, ...]]) -> None:
    receipts.write(
        receipts.Receipt(
            tool="codegraph",
            at="2026-11-07T00:00:00+00:00",
            method=receipts.ReceiptMethod(kind="github_release", key="test"),
            package=None,
            artifacts=(),
            smoke=None,
            hooks=hooks,
        )
    )


_REGISTER_CODEX = ConfigStep("register codegraph for codex", "hook_register")


def test_installing_copilot_registers_herdr_for_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-21: copilot is a herdr host, so installing it sweeps herdr's hook for copilot."""
    herdr = Tool(
        id="herdr",
        name="herdr",
        category="terminal",
        cmd="herdr",
        methods=(Method(kind="github_release", params={"bin_dir": "/b"}),),
        tier="user",
        postinstall="herdr-integration",
    )
    receipts.write(
        receipts.Receipt(
            tool="herdr",
            at="2026-11-07T00:00:00+00:00",
            method=receipts.ReceiptMethod(kind="github_release", key="test"),
            package=None,
            artifacts=(),
            smoke=None,
            hooks={"herdr-integration": ("claude", "sidebar-markers")},
        )
    )
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "copilot"}))

    def status(argv: list[str]) -> str | None:
        return "claude: current (v10) (/x)\ncopilot: not installed (/x)\n"

    monkeypatch.setattr(postinstall, "herdr_query", status)
    argvs: list[list[str]] = []
    outcomes = execute_plan(
        [PlanRow("copilot", Disposition.INSTALL, "not installed")],
        _run_context(
            RunRecorder(),
            catalog={"herdr": herdr, "copilot": _tool("copilot")},
            runner=lambda command: argvs.append(list(command)),
        ),
    )
    assert argvs == [["/b/herdr", "integration", "install", "copilot"]]
    assert outcomes[0].resynced == (("herdr", ("copilot",)),)


def test_reconfigure_registers_the_missing_host(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "codex"}))
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})
    recorder = RunRecorder()
    outcomes = execute_plan(
        [_reconfigure_row("codegraph", _REGISTER_CODEX)],
        _run_context(recorder, catalog={"codegraph": _codegraph_tool()}),
    )
    assert len(recorder.argv) == 1
    argv = recorder.argv[0]
    assert argv[argv.index("--target") + 1] == "codex"
    assert outcomes[0].result == "done"
    assert outcomes[0].detail == "registered for codex"
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks["codegraph-mcp-register"] == ("claude", "codex")


def test_a_failed_register_step_fails_the_row(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "codex"}))
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})

    def runner(command: list[str]) -> None:
        raise CommandError(command, 1, detail="boom")

    outcomes = execute_plan(
        [_reconfigure_row("codegraph", _REGISTER_CODEX)],
        _run_context(RunRecorder(), catalog={"codegraph": _codegraph_tool()}, runner=runner),
    )
    assert outcomes[0].result == "failed"
    assert outcomes[0].detail == (
        "register codegraph for codex: codegraph MCP registration failed: boom"
    )


def test_a_register_step_with_nothing_left_fails_with_a_reason(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude"}))
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})
    recorder = RunRecorder()
    outcomes = execute_plan(
        [_reconfigure_row("codegraph", _REGISTER_CODEX)],
        _run_context(recorder, catalog={"codegraph": _codegraph_tool()}),
    )
    assert recorder.argv == []
    assert outcomes[0].result == "failed"
    assert outcomes[0].detail == (
        "register codegraph for codex: no unregistered host is present any more"
    )


def test_a_zsh_reconfigure_reports_konsole_and_zshenv() -> None:
    profile = "~/.local/share/konsole/tools-installer-zsh.profile"
    konsole = ConfigStep(
        "point Konsole at zsh",
        "terminal_sync",
        report=f"Konsole now starts zsh\n  {profile}",
    )
    zshenv = ConfigStep("export SHELL=/z/bin/zsh in ~/.zshenv", "zshenv_shell", report="/z/bin/zsh")
    outcomes = execute_plan(
        [_reconfigure_row("zsh", konsole, zshenv)],
        _run_context(RunRecorder(), catalog={"zsh": _tool("zsh")}, terminal_sync=lambda: None),
    )
    assert outcomes[0].result == "done"
    buf = io.StringIO()
    render_done_notes(outcomes, Console(file=buf, width=100, no_color=True))
    assert buf.getvalue().splitlines() == [
        "zsh reconfigured — Konsole now starts zsh",
        f"  {profile}",
        "zsh reconfigured — ~/.zshenv exports SHELL",
    ]


def test_a_zshenv_step_whose_write_failed_fails_and_claims_nothing() -> None:
    zshenv = ConfigStep(
        "export SHELL=/z/bin/zsh in /zd/.zshenv", "zshenv_shell", report="/z/bin/zsh\n/zd/.zshenv"
    )

    def denied() -> str:
        return "Terminal shell synchronization warning: zshenv: Permission denied; kitty: x"

    failed = execute_plan(
        [_reconfigure_row("zsh", zshenv)],
        _run_context(RunRecorder(), catalog={"zsh": _tool("zsh")}, terminal_sync=denied),
    )
    done = execute_plan(
        [_reconfigure_row("zsh", zshenv)],
        _run_context(RunRecorder(), catalog={"zsh": _tool("zsh")}, terminal_sync=lambda: None),
    )

    assert failed[0].result == "failed"
    assert "zshenv: Permission denied" in failed[0].detail
    buf = io.StringIO()
    render_shell_section(failed, Console(file=buf, width=100, no_color=True))
    assert buf.getvalue() == ""
    assert done[0].detail == "/zd/.zshenv exports SHELL"
    render_shell_section(done, Console(file=buf, width=100, no_color=True))
    assert buf.getvalue().splitlines() == [
        "Shell",
        "/zd/.zshenv now exports SHELL; new terminals start with it.",
        "  SHELL=/z/bin/zsh",
    ]


def _install_codex_run(recorder: RunRecorder, runner: Runner) -> list[RowOutcome]:
    return execute_plan(
        [PlanRow("codex", Disposition.INSTALL, "not installed")],
        _run_context(
            recorder,
            catalog={"codegraph": _codegraph_tool(), "codex": _tool("codex")},
            runner=runner,
        ),
    )


def test_installing_codex_resyncs_codegraph_for_codex_only(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "codex"}))
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})
    argvs: list[list[str]] = []
    outcomes = _install_codex_run(RunRecorder(), lambda command: argvs.append(list(command)))
    assert len(argvs) == 1
    assert argvs[0][argvs[0].index("--target") + 1] == "codex"
    assert "claude" not in argvs[0]
    assert outcomes[0].result == "done"
    assert outcomes[0].resynced == (("codegraph", ("codex",)),)
    receipt = receipts.read("codegraph")
    assert receipt is not None
    assert receipt.hooks["codegraph-mcp-register"] == ("claude", "codex")


def test_a_run_without_a_host_install_runs_no_sweep(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def hosts() -> frozenset[str]:
        calls.append("hosts")
        return frozenset({"claude", "codex"})

    monkeypatch.setattr(postinstall, "present_hosts", hosts)
    recorder = RunRecorder()
    outcomes = execute_plan(
        [
            PlanRow("rg", Disposition.INSTALL, "not installed"),
            PlanRow("codex", Disposition.SKIP, "already current"),
        ],
        _run_context(recorder, catalog={"rg": _tool("rg"), "codex": _tool("codex")}),
    )
    assert [outcome.result for outcome in outcomes] == ["done", "skipped"]
    assert calls == []
    assert recorder.argv == []


def test_the_sweep_reads_hosts_after_the_rows(monkeypatch: pytest.MonkeyPatch):
    recorder = RunRecorder()
    installs_seen: list[int] = []

    def hosts() -> frozenset[str]:
        installs_seen.append(len(recorder.installs))
        return frozenset({"claude", "codex"})

    monkeypatch.setattr(postinstall, "present_hosts", hosts)
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})
    _install_codex_run(recorder, recorder.runner)
    assert installs_seen == [1]


def test_a_hook_tool_that_recorded_no_host_is_registered_for_the_new_host(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"codex"}))
    _codegraph_receipt({"codegraph-mcp-register": ()})
    argvs: list[list[str]] = []
    outcomes = _install_codex_run(RunRecorder(), lambda command: argvs.append(list(command)))
    assert [argv[argv.index("--target") + 1] for argv in argvs] == ["codex"]
    assert outcomes[0].resynced == (("codegraph", ("codex",)),)


@pytest.mark.parametrize("checks", [[True, False], [True, True, False]])
def test_after_stop_no_hook_sweep_runs(monkeypatch: pytest.MonkeyPatch, checks: list[bool]):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "codex"}))
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})
    answers = iter(checks)
    argvs: list[list[str]] = []
    rows = [PlanRow("codex", Disposition.INSTALL, "not installed")]
    if len(checks) == 3:
        rows.append(PlanRow("rg", Disposition.INSTALL, "not installed"))
    ctx = _run_context(
        RunRecorder(),
        catalog={"codegraph": _codegraph_tool(), "codex": _tool("codex"), "rg": _tool("rg")},
        runner=lambda command: argvs.append(list(command)),
        should_continue=lambda: next(answers),
    )

    outcomes = execute_plan(rows, ctx)

    assert outcomes[0].result == "done"
    assert outcomes[0].resynced == ()
    assert argvs == []
    assert not (Path.home() / ".codex" / "config.toml").exists()


def test_a_receipt_without_recorded_hooks_is_not_swept(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "codex"}))
    _codegraph_receipt({})
    recorder = RunRecorder()
    outcomes = _install_codex_run(recorder, recorder.runner)
    assert recorder.argv == []
    assert outcomes[0].resynced == ()


def test_a_failed_resync_is_a_warning_and_the_row_stays_done(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"claude", "codex"}))
    _codegraph_receipt({"codegraph-mcp-register": ("claude",)})

    def runner(command: list[str]) -> None:
        raise CommandError(command, 1, detail="boom")

    outcomes = _install_codex_run(RunRecorder(), runner)
    assert outcomes[0].result == "done"
    assert outcomes[0].resync_warnings == (
        ("codegraph", "codegraph MCP registration failed: boom"),
    )
    assert exit_code(outcomes) == 0


@pytest.mark.parametrize(
    "status, expected, detail",
    [
        ("installed", "done", ""),
        ("already-installed", "skipped", "became present before it ran"),
        ("failed", "failed", ""),
        ("checksum-mismatch", "mismatch", ""),
        ("dependency-failed", "dependency_failed", ""),
        ("manual-required", "manual", ""),
        ("no-method", "blocked", "no install method for this platform"),
    ],
)
def test_every_install_status_maps_to_one_result(status: str, expected: str, detail: str):
    assert set(getattr(session_module, "_INSTALL" + "_RESULT")) == set(InstallStatus)
    tool = _tool("rg")
    recorder = RunRecorder({"rg": InstallOutcome("rg", InstallStatus(status))})
    outcome = execute_plan(
        [PlanRow("rg", Disposition.INSTALL, "")],
        _run_context(recorder, catalog={"rg": tool}),
    )[0]
    assert outcome.result == expected
    assert outcome.detail == detail


def test_result_words_cover_every_non_done_result_the_engine_can_produce():
    assert set(getattr(session_module, "_INSTALL" + "_RESULT")) == set(InstallStatus)
    assert set(RESULT_WORDS) == {
        "failed",
        "mismatch",
        "dependency_failed",
        "not_attempted",
        "crashed",
        "skipped",
        "blocked",
        "manual",
        "remove_failed",
    }


@pytest.mark.parametrize(
    "status",
    [
        InstallStatus.FAILED,
        InstallStatus.NO_METHOD,
        InstallStatus.CHECKSUM_MISMATCH,
        InstallStatus.DEPENDENCY_FAILED,
        InstallStatus.MANUAL_REQUIRED,
    ],
)
def test_every_unresolved_install_status_blocks_dependents(status: InstallStatus):
    tools = {"dep": _tool("dep"), "user": _tool("user", requires=("dep",))}
    recorder = RunRecorder({"dep": InstallOutcome("dep", status)})
    outcomes = execute_plan(
        [PlanRow("dep", Disposition.INSTALL, ""), PlanRow("user", Disposition.INSTALL, "")],
        _run_context(recorder, catalog=tools),
    )
    assert outcomes[1].result == "dependency_failed"
    assert outcomes[1].install is not None and outcomes[1].install.blocked_by == ("dep",)


@pytest.mark.parametrize("status", [InstallStatus.INSTALLED, InstallStatus.ALREADY_INSTALLED])
def test_successful_install_statuses_do_not_block_dependents(status: InstallStatus):
    tools = {"dep": _tool("dep"), "user": _tool("user", requires=("dep",))}
    recorder = RunRecorder({"dep": InstallOutcome("dep", status)})
    outcomes = execute_plan(
        [PlanRow("dep", Disposition.INSTALL, ""), PlanRow("user", Disposition.INSTALL, "")],
        _run_context(recorder, catalog=tools),
    )
    assert [outcome.result for outcome in outcomes] == [
        "skipped" if status is InstallStatus.ALREADY_INSTALLED else "done",
        "done",
    ]
    assert recorder.installs == [("dep", False), ("user", False)]


def test_execute_plan_reports_only_failed_unique_dependencies():
    tools = {
        "dep": _tool("dep"),
        "user": _tool("user", requires=("dep", "missing", "dep")),
    }
    recorder = RunRecorder({"dep": InstallOutcome("dep", "failed")})
    outcomes = execute_plan(
        [PlanRow("dep", Disposition.INSTALL, ""), PlanRow("user", Disposition.INSTALL, "")],
        _run_context(recorder, catalog=tools),
    )
    assert outcomes[1].install is not None
    assert outcomes[1].install.blocked_by == ("dep",)


def test_execute_plan_does_not_reorder_rows_to_satisfy_dependencies():
    tools = {"user": _tool("user", requires=("dep",)), "dep": _tool("dep")}
    recorder = RunRecorder({"dep": InstallOutcome("dep", "failed")})
    outcomes = execute_plan(
        [PlanRow("user", Disposition.INSTALL, ""), PlanRow("dep", Disposition.INSTALL, "")],
        _run_context(recorder, catalog=tools),
    )
    assert [outcome.result for outcome in outcomes] == ["done", "failed"]
    assert recorder.installs == [("user", False), ("dep", False)]


def test_order_for_install_sorts_by_priority_then_keeps_catalog_order():
    tools = [_tool("a", "P3"), _tool("b", "P0"), _tool("c", "P3"), _tool("d", "P1")]
    assert [t.id for t in order_for_install(tools)] == ["b", "d", "a", "c"]


def test_tool_rejects_unknown_priority():
    with pytest.raises(ValueError, match="unknown priority"):
        _tool("x", "P99")


def _login_shell_tool() -> Tool:
    return Tool(
        id="oh-my-zsh",
        name="o",
        category="shell",
        cmd="omz",
        methods=(Method(kind="script", params={"url": "u"}),),
        post_install=("set_login_shell",),
    )


def _mutable_platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def test_execute_plan_prints_the_login_shell_handoff_whatever_the_confirmation_says(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str, path: str | None = None) -> str | None:
        del path
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    sandbox = tmp_path / "path-sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("PATH", str(sandbox))

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    tool = _login_shell_tool()
    platform = _mutable_platform()

    def run(confirm: ConfirmSensitiveAction) -> InstallOutcome | None:
        context = RunContext(
            catalog={tool.id: tool},
            platform=platform,
            runner=lambda _cmd: None,
            resolve_tag=lambda _repo: "1.0.0",
            install=engine.install_tool,
            confirm_sensitive=confirm,
        )
        return execute_plan([PlanRow(tool.id, Disposition.INSTALL, "")], context)[0].install

    yes_outcome = run(lambda _id, _action: True)
    no_outcome = run(lambda _id, _action: False)
    assert yes_outcome is not None and yes_outcome.post_install_handoff
    assert no_outcome is not None and no_outcome.post_install_handoff


def test_execute_plan_forwards_the_confirmation_and_unchanged_kwargs() -> None:
    seen: list[tuple[ChecksumPolicy, ConfirmSensitiveAction | None]] = []

    def recording_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        seen.append((checksum_policy, confirm_sensitive_action))
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    def confirm(tool_id: str, action: str) -> bool:
        return True

    catalog = {"rg": _tool("rg")}
    context = RunContext(
        catalog=catalog,
        platform=_platform(),
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "1.0.0",
        install=recording_install,
        confirm_sensitive=confirm,
    )
    execute_plan([PlanRow("rg", Disposition.INSTALL, "")], context)
    assert seen == [("fail", confirm)]


def test_execute_plan_without_a_confirmation_still_prints_the_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str, path: str | None = None) -> str | None:
        del path
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    sandbox = tmp_path / "path-sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("PATH", str(sandbox))

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    tool = _login_shell_tool()
    context = RunContext(
        catalog={tool.id: tool},
        platform=_mutable_platform(),
        runner=lambda _cmd: None,
        resolve_tag=lambda _repo: "1.0.0",
        install=engine.install_tool,
    )
    outcome = execute_plan([PlanRow(tool.id, Disposition.INSTALL, "")], context)[0].install
    assert outcome is not None
    assert any("chsh -s" in line for line in outcome.post_install_handoff)


def test_sensitive_install_protocol_parameters_are_unchanged() -> None:
    params = list(inspect.signature(SensitiveInstall.__call__).parameters)
    assert params == [
        "self",
        "tool",
        "platform",
        "runner",
        "resolve_tag",
        "checksum_policy",
        "confirm_sensitive_action",
    ]


# ---------------------------------------------------------------------------
# 20-08 Task 2: the argv-less step kinds, plus the promise that no kind is
# silently unhandled. pnpm_group_install runs the executor install and update
# already use (19 L-19-28), terminal_sync calls the bound synchronizer, and an
# unknown kind fails closed rather than running its argv (19 L-19-07).
# ---------------------------------------------------------------------------


def _group_method() -> Method:
    return Method(
        kind="node",
        params={
            "npm_pkg": "npm-superpowers",
            "co_install": ["@obra/superpowers"],
            "versions": {"@obra/superpowers": "^1"},
        },
    )


def _node_tool(*methods: Method) -> Tool:
    return Tool(
        id="superpowers",
        name="Superpowers",
        category="ai",
        cmd="superpowers",
        methods=methods or (_group_method(),),
    )


_ALL_KIND_STEPS: dict[ConfigStepKind, ConfigStep] = {
    "terminal_sync": ConfigStep("point iTerm2 at zsh", "terminal_sync"),
    "pnpm_group_install": ConfigStep("install @obra/superpowers with pnpm", "pnpm_group_install"),
    "hook_register": ConfigStep("register codegraph for codex", "hook_register"),
    "zshenv_shell": ConfigStep("export SHELL=/bin/zsh in ~/.zshenv", "zshenv_shell"),
    "install_tuning": ConfigStep("apply install tuning", "install_tuning"),
}

# The details a dispatched step reports as a done note; every other kind reports none.
_DISPATCH_DETAIL: dict[ConfigStepKind, str] = {
    "hook_register": "registered for codex",
    "zshenv_shell": "~/.zshenv exports SHELL",
}


def _tuned_claude() -> Tool:
    return Tool(
        id="claude",
        name="Claude Code",
        category="ai",
        cmd="claude",
        methods=(Method(kind="host", params={}),),
        post_install=("apply_agent_tuning",),
    )


def _execute_nothing(_method: Method, _runner: Runner) -> None:
    """A stand-in for `executors.execute` that runs nothing and raises nothing."""


@pytest.mark.parametrize("kind", sorted(_ALL_KIND_STEPS))
def test_each_config_step_kind_dispatches(
    monkeypatch: pytest.MonkeyPatch, kind: ConfigStepKind
) -> None:
    """Every ConfigStepKind has a branch, and the branches match the model's set.

    One test per member (the plan asks for one per kind, and one collected
    test per kind is the evidence) plus the set equality, which is the guard: a ninth
    kind added to `model.ConfigStepKind` fails here rather than reaching a
    command path nobody reviewed. The node executor is stubbed because the pnpm
    group is another test's subject; here the branch only has to be reached.
    """
    monkeypatch.setattr(session_module.executors, "execute", _execute_nothing)
    declared = frozenset(get_args(ConfigStepKind))
    assert declared == getattr(session_module, "_STEP" + "_KINDS")
    assert frozenset(_ALL_KIND_STEPS) == declared

    tool_id = "superpowers"
    tool = _node_tool(Method(kind="host", params={"host_setup": True}), _group_method())
    if kind == "hook_register":
        tool_id, tool = "codegraph", _codegraph_tool()
        monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset({"codex"}))
        _codegraph_receipt({})
    if kind == "install_tuning":
        tool_id, tool = "claude", _tuned_claude()
    recorder = RunRecorder()
    outcomes = execute_plan(
        [_reconfigure_row(tool_id, _ALL_KIND_STEPS[kind])],
        _run_context(recorder, catalog={tool_id: tool}),
    )
    assert outcomes[0].result == "done", kind
    assert outcomes[0].detail == _DISPATCH_DETAIL.get(kind, ""), kind
    # The built-in kinds act through a bound seam instead of the runner, so nothing is
    # recorded as a command for them; hook_register runs one register argv, the rest one argv.
    seam_only = {"terminal_sync", "pnpm_group_install", "zshenv_shell", "install_tuning"}
    assert len(recorder.argv) == (0 if kind in seam_only else 1), kind


def test_pnpm_group_install_runs_the_tools_first_node_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """19 L-19-28: the whole pinned group through the existing node executor.

    The step carries no argv by design (19 review H10): re-typing the pnpm argv
    here would let the reconfigure path drift from install and update, so the
    row dispatches `executors.execute` on the declaring tool's first node
    method — not the `host` method that comes first in registry order.
    """
    executed: list[Method] = []

    def _execute(method: Method, _runner: object) -> None:
        executed.append(method)

    monkeypatch.setattr(session_module.executors, "execute", _execute)
    recorder = RunRecorder()
    tool = _node_tool(Method(kind="host", params={"host_setup": True}), _group_method())
    step = _ALL_KIND_STEPS["pnpm_group_install"]

    outcome = execute_plan(
        [_reconfigure_row("superpowers", step)],
        _run_context(recorder, catalog={"superpowers": tool}),
    )[0]

    assert outcome.result == "done"
    assert executed == [_group_method()]
    assert recorder.argv == []

    no_node = _node_tool(Method(kind="host", params={"host_setup": True}))
    failed = execute_plan(
        [_reconfigure_row("superpowers", step)],
        _run_context(recorder, catalog={"superpowers": no_node}),
    )[0]
    assert failed.result == "failed"
    assert failed.detail == f"{step.text}: no node method declares the group"


def test_pnpm_group_install_reports_the_executors_own_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing or too-old pnpm is a failed step, not a crashed run.

    `executors.execute` raises `ExecutorError` for the floors it checks (real
    pnpm, min_node, min_pnpm). That is an expected refusal carrying a sentence
    the user can act on, so the row shows its first line and the run keeps
    going; the per-row `crashed` path stays for exceptions nobody predicted.
    """

    def _execute(_method: Method, _runner: object) -> None:
        raise executors.ExecutorError(
            "pnpm could not be found.\nInstall pnpm 9 or newer before using this method."
        )

    monkeypatch.setattr(session_module.executors, "execute", _execute)
    recorder = RunRecorder()
    tool = _node_tool()
    step = _ALL_KIND_STEPS["pnpm_group_install"]

    outcome = execute_plan(
        [_reconfigure_row("superpowers", step)],
        _run_context(recorder, catalog={"superpowers": tool}),
    )[0]

    assert outcome.result == "failed"
    assert outcome.detail == f"{step.text}: pnpm could not be found."
    assert recorder.argv == []

    following = execute_plan(
        [_reconfigure_row("superpowers", step), PlanRow("b", Disposition.INSTALL, "not installed")],
        _run_context(recorder, catalog={"superpowers": tool, "b": _tool("b")}),
    )
    assert [result for result in (o.result for o in following)] == ["failed", "done"]


def test_a_raising_terminal_sync_step_fails_its_row_and_the_batch_continues() -> None:
    recorder = RunRecorder()
    first = _reconfigure_row("a", ConfigStep("point iTerm2 at zsh", "terminal_sync"))
    second = PlanRow("b", Disposition.INSTALL, "not installed")

    def fail_sync() -> str | None:
        raise PermissionError(13, "Permission denied")

    outcomes = execute_plan(
        [first, second],
        replace(
            _run_context(recorder, catalog={"a": _tool("a"), "b": _tool("b")}),
            terminal_sync=fail_sync,
        ),
    )

    assert outcomes[0].result == "failed"
    assert outcomes[0].detail.startswith("point iTerm2 at zsh: ")
    assert "Permission denied" in outcomes[0].detail
    assert outcomes[1].result == "done"
    assert recorder.installs == [("b", False)]


@pytest.mark.parametrize(
    "warning, expected_detail",
    [(None, ""), ("Terminal sync needed: run iTerm2>", "Terminal sync needed: run iTerm2>")],
)
def test_terminal_sync_step_calls_the_bound_synchronizer(
    warning: str | None, expected_detail: str
) -> None:
    """The row runs the synchronizer the app bound, and keeps its warning as detail."""
    synced: list[str] = []
    step = _ALL_KIND_STEPS["terminal_sync"]

    def terminal_sync() -> str | None:
        synced.append(step.text)
        return warning

    recorder = RunRecorder()
    outcome = execute_plan(
        [_reconfigure_row("iterm2", step)],
        _run_context(recorder, catalog={"iterm2": _tool("iterm2")}, terminal_sync=terminal_sync),
    )[0]

    assert synced == [step.text]
    assert outcome.result == "done"
    assert outcome.detail == expected_detail
    assert recorder.argv == []

    unbound = replace(
        _run_context(recorder, catalog={"iterm2": _tool("iterm2")}), terminal_sync=None
    )
    missing = execute_plan([_reconfigure_row("iterm2", step)], unbound)[0]
    assert missing.result == "failed"
    assert missing.detail == f"{step.text}: no terminal synchronizer bound"


def test_an_unknown_step_kind_fails_closed_instead_of_running_argv() -> None:
    """The guard behind `_STEP_KINDS`: a kind with no branch never executes.

    The model's literal type rejects this kind at build time; a plan built by
    an older producer, or hand-edited, can still carry one, so the dispatcher
    refuses it rather than running anything for it.
    """
    step = ConfigStep("do the new thing", cast(ConfigStepKind, "brand_new_kind"))
    recorder = RunRecorder()

    outcome = execute_plan(
        [_reconfigure_row("gsd", step)],
        _run_context(recorder, catalog={"gsd": _tool("gsd")}),
    )[0]

    assert outcome.result == "failed"
    assert outcome.detail == f"{step.text}: step kind has no branch"
    assert recorder.argv == []


def test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next() -> None:
    """The D-18 order holds when the first step fails and a later step is a real action.

    Stopping at the first failure is what keeps a failed enable from being followed
    by the removal that would delete the only working copy; here the later step is a
    second synchronizer call, so the count shows whether it ran.
    """
    synced: list[str] = []

    def failing_sync() -> None:
        synced.append("sync")
        raise RuntimeError("sync refused")

    sync = ConfigStep("point iTerm2 at zsh", "terminal_sync")
    later = ConfigStep("sync again", "terminal_sync")
    recorder = RunRecorder()

    outcome = execute_plan(
        [_reconfigure_row("gsd", sync, later)],
        replace(_run_context(recorder, catalog={"gsd": _tool("gsd")}), terminal_sync=failing_sync),
    )[0]

    assert outcome.result == "failed"
    assert outcome.detail.startswith(f"{sync.text}: ")
    assert synced == ["sync"]


def _removal(tool_id: str, result: Result, detail: str = "") -> RowOutcome:
    return RowOutcome(PlanRow(tool_id, Disposition.REMOVE, ""), result, detail=detail)


def test_summary_counts_reads_removed_and_remove_failed():
    both = [_removal("rg", "done"), _removal("fd", "remove_failed", "permission denied")]
    assert summary_counts(both) == "1 removed, 1 remove failed"
    many = [_removal(t, "done") for t in ("a", "b", "c")] + [_removal("d", "remove_failed")]
    assert summary_counts(many) == "3 removed, 1 remove failed"


def test_remove_failed_is_retained_and_removed_is_not():
    outcomes = [_removal("rg", "done"), _removal("fd", "remove_failed")]
    assert retained(outcomes) == {"fd"}
    assert exit_code(outcomes) == 1


def test_remove_is_not_runnable():
    assert Disposition.REMOVE not in session_module.RUNNABLE


def test_first_line_is_the_message_or_the_type():
    assert first_line(OSError("a\nb")) == "a"
    assert first_line(OSError()) == "OSError failed"


@pytest.mark.parametrize("disposition", list(Disposition))
def test_every_disposition_has_words_and_a_review_place(disposition: Disposition):
    assert review_counts([PlanRow("x", disposition, "")]) == f"1 {WORDS[disposition].review}"


def test_every_disposition_manual_is_reviewed_right_after_blocked():
    members = list(Disposition)
    assert members.index(Disposition.MANUAL) == members.index(Disposition.BLOCKED) + 1


_AGENT_ROWS = [
    PlanRow("claude", Disposition.INSTALL, "not installed"),
    PlanRow("codex", Disposition.INSTALL, "not installed"),
]
_AGENT_CATALOG = {"claude": _tool("claude"), "codex": _tool("codex")}


def _report(outcomes: list[RowOutcome]) -> str:
    buf = io.StringIO()
    render_run_report(outcomes, Console(file=buf, width=100, no_color=True))
    return buf.getvalue()


def test_a_default_run_writes_no_setting() -> None:
    recorder = RunRecorder()
    outcomes = execute_plan(_AGENT_ROWS, _run_context(recorder, catalog=_AGENT_CATALOG))
    home = Path.home()
    assert not (home / ".claude" / "settings.json").exists()
    assert not (home / ".codex" / "config.toml").exists()
    assert not (home / ".config" / "environment.d").exists()
    assert all(outcome.settings == () for outcome in outcomes)
    assert "  wrote " not in _report(outcomes)


def test_a_failed_agent_row_writes_nothing_and_adds_no_settings_note() -> None:
    recorder = RunRecorder(outcomes={"claude": InstallOutcome("claude", InstallStatus.FAILED)})
    ctx = _run_context(recorder, catalog={"claude": _tool("claude")})
    outcomes = execute_plan([PlanRow("claude", Disposition.INSTALL, "not installed")], ctx)
    assert outcomes[0].result == "failed"
    assert not (Path.home() / ".claude" / "settings.json").exists()
    assert "Agent and editor settings" not in _report(outcomes)


def test_install_tuning_step_refusal_fails_and_carries_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-03: a write that is refused fails the step with the refusal, and the row still reports
    the FileResults the step produced, so the summary shows what was not written."""
    settings = Path.home() / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}\n", encoding="utf-8")

    def always_changed(_path: Path, _before: object, _text: str) -> None:
        raise agent_settings.SettingsChanged()

    monkeypatch.setattr(agent_settings, "write_if_unchanged", always_changed)
    row = _reconfigure_row("claude", _ALL_KIND_STEPS["install_tuning"])

    outcome = execute_plan([row], _run_context(RunRecorder(), catalog={"claude": _tuned_claude()}))[
        0
    ]

    assert outcome.result == "failed"
    assert outcome.detail == (
        f"apply install tuning: ~/.claude/settings.json: {agent_settings.CHANGED_WHILE_WRITING}"
    )
    assert {file.refused for file in outcome.settings} == {agent_settings.CHANGED_WHILE_WRITING}
    assert [file.setting for file in outcome.settings] == ["auto-approve", "no-attribution"]
    assert settings.read_text(encoding="utf-8") == "{}\n"


def test_install_tuning_step_fails_when_the_omz_plugin_write_is_refused() -> None:
    """C-06: a refused Oh-My-Zsh plugins write is a failed step, not a done row."""
    home = Path.home()
    (home / ".oh-my-zsh").mkdir()
    zshrc = home / ".zshrc"
    refused = "plugins=(\n  git\n)\nsource $ZSH/oh-my-zsh.sh\n"
    zshrc.write_text(refused, encoding="utf-8")
    catalog = {
        "oh-my-zsh": replace(_shipped_catalog()["oh-my-zsh"], post_install=("set_omz_plugins",))
    }
    row = _reconfigure_row("oh-my-zsh", _ALL_KIND_STEPS["install_tuning"])

    outcome = execute_plan([row], _run_context(RunRecorder(), catalog=catalog))[0]

    assert outcome.result == "failed"
    assert (outcome.detail or "").startswith("apply install tuning: The last plugins=(...) array")
    assert zshrc.read_text(encoding="utf-8") == refused


REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _shipped_catalog() -> dict[str, Tool]:
    return {tool.id: tool for tool in load_tools(REGISTRY)}


def _plant_command(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True)
    command = directory / name
    command.write_text("#!/bin/sh\n")
    command.chmod(0o755)
    return command


def _probe_pnpm_and_node(argv: list[str]) -> str | None:
    """Answers the version floors mmdc's node method checks: pnpm 11.9 and node 24."""
    return "v24.4.0" if argv[0] == "node" else "11.9.0"


def _install_through_node_method(
    tool: Tool,
    platform: Platform,
    runner: Runner,
    resolve_tag: TagResolver,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    confirm_sensitive_action: ConfirmSensitiveAction | None = None,
) -> InstallOutcome:
    """The node rung of a real install, without the presence check or the postinstall sweep."""
    del platform, resolve_tag, checksum_policy, confirm_sensitive_action
    for method in tool.methods:
        if method.kind == "node":
            executors.execute(method, runner)
    return InstallOutcome(tool.id, InstallStatus.INSTALLED)


def test_pnpm_off_path_skip_row_puts_its_bin_dir_on_path_for_mmdc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC R12 (UAT F-1): pnpm present at its declared bin dir but off PATH is
    SKIPped as present, and mmdc's install in the same run still runs it there."""
    monkeypatch.setenv("HOME", str(tmp_path))
    fake_pnpm = _plant_command(tmp_path / ".local" / "share" / "pnpm" / "bin", "pnpm")
    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))
    monkeypatch.setattr(executors, "probe_version", _probe_pnpm_and_node)
    monkeypatch.setattr(executors, "launch_puppeteer", lambda: None)
    calls: list[list[str]] = []
    ctx = RunContext(
        catalog=_shipped_catalog(),
        platform=_platform(),
        runner=calls.append,
        resolve_tag=lambda _repo: "1.0.0",
        install=_install_through_node_method,
    )

    outcomes = execute_plan(
        [
            PlanRow("pnpm", Disposition.SKIP, "already present"),
            PlanRow("mmdc", Disposition.INSTALL, "will install"),
        ],
        ctx,
    )

    assert [outcome.result for outcome in outcomes] == ["skipped", "done"]
    assert calls[0][:3] == [str(fake_pnpm), "add", "-g"]


def test_path_repair_ignores_the_installers_own_pnpm_redirect_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-01: the ban's pnpm redirect shim on PATH is not a real pnpm, so the real
    pnpm's declared bin dir still reaches PATH and mmdc runs the real binary."""
    monkeypatch.setenv("HOME", str(tmp_path))
    fake_pnpm = _plant_command(tmp_path / ".local" / "share" / "pnpm" / "bin", "pnpm")
    shim = _plant_command(tmp_path / ".local" / "bin", "pnpm")
    shim.write_text(f"#!/bin/sh\n{REDIRECT_SENTINEL}\nexit 1\n")
    monkeypatch.setenv("PATH", str(tmp_path / ".local" / "bin"))
    monkeypatch.setattr(executors, "probe_version", _probe_pnpm_and_node)
    monkeypatch.setattr(executors, "launch_puppeteer", lambda: None)
    calls: list[list[str]] = []
    ctx = RunContext(
        catalog=_shipped_catalog(),
        platform=_platform(),
        runner=calls.append,
        resolve_tag=lambda _repo: "1.0.0",
        install=_install_through_node_method,
    )

    execute_plan(
        [
            PlanRow("pnpm", Disposition.SKIP, "already present"),
            PlanRow("mmdc", Disposition.INSTALL, "will install"),
        ],
        ctx,
    )

    assert calls[0][:3] == [str(fake_pnpm), "add", "-g"]


def test_path_repair_never_reorders_a_path_that_already_finds_the_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-24 guard: when PATH already finds the tool, a SKIP row leaves PATH byte-identical."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _plant_command(tmp_path / ".local" / "share" / "pnpm" / "bin", "pnpm")
    on_path = tmp_path / "on-path"
    _plant_command(on_path, "pnpm")
    monkeypatch.setenv("PATH", str(on_path))
    before = os.environ["PATH"]

    execute_plan(
        [PlanRow("pnpm", Disposition.SKIP, "already present")],
        _run_context(RunRecorder(), catalog=_shipped_catalog()),
    )

    assert os.environ["PATH"] == before


def test_path_repair_also_applies_to_a_row_that_ends_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A RECONFIGURE row ends done without installing; the tool's declared bin dir
    must still reach PATH so its dependents find it in the same run."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))
    bin_dir = tmp_path / "candidates" / "bin"
    _plant_command(bin_dir, "spring")
    tool = Tool(
        id="spring",
        name="Spring",
        category="runtime",
        cmd="spring",
        methods=(
            Method(kind="sdkman", params={"candidate": "springboot", "bin_dir": str(bin_dir)}),
        ),
    )

    outcome = execute_plan(
        [PlanRow("spring", Disposition.RECONFIGURE, "apply install tuning")],
        _run_context(RunRecorder(), catalog={"spring": tool}),
    )[0]

    assert outcome.result == "done"
    assert os.environ["PATH"].split(os.pathsep)[0] == str(bin_dir)
