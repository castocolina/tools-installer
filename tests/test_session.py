import inspect
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast, get_args

import pytest

import installer.engine as engine
import installer.session as session_module
from installer import executors, skill_lifecycle
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import InstallStatus
from installer.model import (
    ConfigStep,
    ConfigStepKind,
    Method,
    SkillLifecycle,
    SkillOperation,
    SkillTarget,
    Tool,
)
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import CommandError, Runner
from installer.session import (
    RESULT_WORDS,
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
    order_for_install,
    ran_anything,
    retained,
    summary_counts,
)
from installer.skill_lifecycle import LifecycleOutcome, LifecycleStatus
from installer.update import UpdateOutcome
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


# argv shapes Phase 19 actually builds (skill_lifecycle enable/uninstall/project install steps).
_ENABLE = ("claude", "plugin", "enable", "-s", "user", "gsd-core")
_UNINSTALL = ("claude", "plugin", "uninstall", "-s", "project", "gsd-core@gsd")
_GSD_INSTALL = ("pnpm", "dlx", "@opengsd/gsd-core@1.16.0", "--claude", "--local")


def _run_context(
    recorder: RunRecorder,
    *,
    catalog: Mapping[str, Tool] | None = None,
    confirm_sensitive: ConfirmSensitiveAction | None = None,
    on_mismatch: OnMismatch | None = None,
    updates: ScriptedUpdates | None = None,
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

    seen: list[tuple[Tool, Platform, Runner, TagResolver, Mapping[str, Tool] | None]] = []

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
        assert checksum_policy == "fail"
        assert confirm_sensitive_action is None
        seen.append((tool, platform, runner, resolve_tag, tools))
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
    actual_tool, actual_platform, actual_runner, actual_resolve_tag, actual_catalog = seen[0]
    assert actual_tool is tool
    assert actual_platform is platform
    assert actual_runner is runner
    assert actual_resolve_tag is resolve_tag
    assert actual_catalog is catalog


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
    middle_row = (
        PlanRow("mid", disposition, "update", ownership=ownership)
        if disposition is Disposition.UPDATE
        else _reconfigure_row(
            "mid", ConfigStep("enable gsd-core in user scope", "plugin_enable", "claude", _ENABLE)
        )
    )
    outcomes = execute_plan(
        [
            PlanRow("dep", Disposition.INSTALL, "missing"),
            middle_row,
            PlanRow("leaf", Disposition.INSTALL, "missing"),
        ],
        _run_context(
            recorder,
            catalog={"dep": dependency, "mid": middle, "leaf": leaf},
            updates=updates,
        ),
    )

    assert [outcome.result for outcome in outcomes] == ["failed", "dependency_failed", "done"]
    assert outcomes[1].install is not None
    assert outcomes[1].install.blocked_by == ("dep",)
    assert updates.targets == []
    assert recorder.argv == []
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

    seen: list[tuple[ChecksumPolicy, Mapping[str, Tool] | None]] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        seen.append((checksum_policy, tools))
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
    assert [policy for policy, _mapping in seen] == policies
    assert all(mapping is catalog for _policy, mapping in seen)
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


def test_reconfigure_runs_argv_steps_in_order_and_is_done():
    """One event list pins the callback-before-the-first-step order (the TUI's set_tool seam)."""
    events: list[object] = []

    def runner(command: list[str]) -> None:
        events.append(list(command))

    recorder = RunRecorder()
    steps = (
        ConfigStep("enable gsd-core in user scope", "plugin_enable", "claude", _ENABLE),
        ConfigStep("remove gsd-core from project scope", "plugin_uninstall", "claude", _UNINSTALL),
    )
    outcomes = execute_plan(
        [_reconfigure_row("gsd", *steps)],
        _run_context(
            recorder,
            catalog={"gsd": _tool("gsd")},
            runner=runner,
            on_row_started=lambda row: events.append(row.tool_id),
        ),
    )
    assert events == ["gsd", list(_ENABLE), list(_UNINSTALL)]
    assert outcomes[0].result == "done"
    assert outcomes[0].detail == ""
    assert summary_counts(outcomes) == "1 reconfigured"


def test_reconfigure_wraps_a_step_with_cwd_in_the_portable_directory_shim(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    recorder = RunRecorder()
    step = ConfigStep(
        "install gsd-core for Claude in repo", "project_pack_install", "claude", _GSD_INSTALL, repo
    )
    outcomes = execute_plan(
        [_reconfigure_row("gsd", step)],
        _run_context(recorder, catalog={"gsd": _tool("gsd")}),
    )
    assert recorder.argv == [
        ["sh", "-c", 'cd -- "$1" && shift && exec "$@"', "sh", str(repo), *_GSD_INSTALL]
    ]
    assert outcomes[0].result == "done"


@pytest.mark.parametrize(
    "kind, refusal",
    [
        ("relative", "cwd is not absolute"),
        ("missing", "cwd does not exist"),
        ("symlink", "cwd is not a directory"),
    ],
)
def test_reconfigure_refuses_a_cwd_that_is_relative_missing_or_a_symlink(
    tmp_path: Path, kind: str, refusal: str
):
    real = tmp_path / "real"
    real.mkdir()
    if kind == "relative":
        cwd: Path = Path("repo")
    elif kind == "missing":
        cwd = tmp_path / "gone"
    else:
        cwd = tmp_path / "link"
        cwd.symlink_to(real)
    recorder = RunRecorder()
    step = ConfigStep(
        "install gsd-core for Claude in repo", "project_pack_install", "claude", _GSD_INSTALL, cwd
    )
    outcomes = execute_plan(
        [_reconfigure_row("gsd", step)],
        _run_context(recorder, catalog={"gsd": _tool("gsd")}),
    )
    assert outcomes[0].result == "failed"
    assert outcomes[0].detail == f"{step.text}: {refusal}"
    assert recorder.argv == []


def test_reconfigure_stops_at_the_first_failing_step():
    seen: list[list[str]] = []

    def runner(command: list[str]) -> None:
        seen.append(command)
        raise CommandError(command, 1)

    recorder = RunRecorder()
    steps = (
        ConfigStep("enable gsd-core in user scope", "plugin_enable", "claude", _ENABLE),
        ConfigStep("remove gsd-core from project scope", "plugin_uninstall", "claude", _UNINSTALL),
    )
    outcomes = execute_plan(
        [_reconfigure_row("gsd", *steps)],
        _run_context(recorder, catalog={"gsd": _tool("gsd")}, runner=runner),
    )
    assert outcomes[0].result == "failed"
    assert outcomes[0].detail == f"{steps[0].text}: command failed (1): {' '.join(_ENABLE)}"
    assert seen == [list(_ENABLE)]


def test_reconfigure_failure_does_not_block_a_dependent():
    def runner(command: list[str]) -> None:
        raise CommandError(command, 1)

    recorder = RunRecorder()
    step = ConfigStep("enable gsd-core in user scope", "plugin_enable", "claude", _ENABLE)
    outcomes = execute_plan(
        [_reconfigure_row("a", step), PlanRow("b", Disposition.INSTALL, "not installed")],
        _run_context(
            recorder,
            catalog={"a": _tool("a"), "b": _tool("b", requires=("a",))},
            runner=runner,
        ),
    )
    assert [outcome.result for outcome in outcomes] == ["failed", "done"]
    assert recorder.installs == [("b", False)]


def test_reconfigure_step_without_a_command_fails():
    recorder = RunRecorder()
    step = ConfigStep("enable gsd-core in user scope", "plugin_enable", "claude")
    outcomes = execute_plan(
        [_reconfigure_row("gsd", step)],
        _run_context(recorder, catalog={"gsd": _tool("gsd")}),
    )
    assert outcomes[0].result == "failed"
    assert outcomes[0].detail.endswith("step has no command")
    assert recorder.argv == []


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


def test_execute_plan_confirmation_reaches_the_post_install_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str) -> str | None:
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
    assert no_outcome is not None and no_outcome.post_install_handoff == ()


def test_execute_plan_forwards_the_confirmation_and_unchanged_kwargs() -> None:
    seen: list[tuple[ChecksumPolicy, Mapping[str, Tool] | None, ConfirmSensitiveAction | None]] = []

    def recording_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        seen.append((checksum_policy, tools, confirm_sensitive_action))
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
    assert seen == [("fail", catalog, confirm)]


def test_execute_plan_without_a_confirmation_produces_no_instructions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str) -> str | None:
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
    assert outcome is not None and outcome.post_install_handoff == ()


def test_sensitive_install_protocol_parameters_are_unchanged() -> None:
    params = list(inspect.signature(SensitiveInstall.__call__).parameters)
    assert params == [
        "self",
        "tool",
        "platform",
        "runner",
        "resolve_tag",
        "checksum_policy",
        "tools",
        "confirm_sensitive_action",
    ]


# ---------------------------------------------------------------------------
# 20-08 Task 2: the three argv-less step kinds, plus the promise that no kind is
# silently unhandled. pnpm_group_install runs the executor install and update
# already use (19 L-19-28), terminal_sync calls the bound synchronizer, and an
# argv-less skill_install is a reviewed handoff, never a command (19 L-19-07).
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


def _handoff_tool(install: SkillOperation) -> Tool:
    return Tool(
        id="superpowers",
        name="Superpowers",
        category="ai",
        cmd="superpowers",
        methods=(Method(kind="skill_pack"),),
        skill_lifecycle=SkillLifecycle(
            source="https://github.com/obra/superpowers",
            owner="obra",
            supported_harnesses=("codex", "claude"),
            revision_policy="upstream-latest",
            targets=(SkillTarget("harness", "<codex-plugin-dir>/superpowers"),),
            install=install,
            status=SkillOperation("manual-required"),
            update=SkillOperation("manual-required"),
            removal=SkillOperation("manual-required"),
        ),
    )


_ALL_KIND_STEPS: dict[ConfigStepKind, ConfigStep] = {
    "skill_install": ConfigStep(
        "install superpowers with the pack CLI",
        "skill_install",
        "claude",
        ("claude", "install", "x"),
    ),
    "plugin_enable": ConfigStep("enable superpowers", "plugin_enable", "claude", _ENABLE),
    "plugin_uninstall": ConfigStep("remove superpowers", "plugin_uninstall", "claude", _UNINSTALL),
    "marketplace_remove": ConfigStep(
        "drop the marketplace", "marketplace_remove", "claude", ("claude", "marketplace", "rm")
    ),
    "terminal_sync": ConfigStep("point iTerm2 at zsh", "terminal_sync"),
    "pnpm_group_install": ConfigStep("install @obra/superpowers with pnpm", "pnpm_group_install"),
    "project_pack_global_uninstall": ConfigStep(
        "remove the global gsd", "project_pack_global_uninstall", "claude", _UNINSTALL
    ),
    "project_pack_install": ConfigStep(
        "install gsd for Claude in repo", "project_pack_install", "claude", _GSD_INSTALL
    ),
}


def _execute_nothing(_method: Method, _runner: Runner) -> None:
    """A stand-in for `executors.execute` that runs nothing and raises nothing."""


@pytest.mark.parametrize("kind", sorted(_ALL_KIND_STEPS))
def test_each_config_step_kind_dispatches(
    monkeypatch: pytest.MonkeyPatch, kind: ConfigStepKind
) -> None:
    """Every ConfigStepKind has a branch, and the branches match the model's set.

    One test per member (the plan asks for one per kind, and eight collected
    tests are the evidence) plus the set equality, which is the guard: a ninth
    kind added to `model.ConfigStepKind` fails here rather than reaching a
    command path nobody reviewed. The node executor is stubbed because the pnpm
    group is another test's subject; here the branch only has to be reached.
    """
    monkeypatch.setattr(session_module.executors, "execute", _execute_nothing)
    declared = frozenset(get_args(ConfigStepKind))
    assert declared == getattr(session_module, "_STEP" + "_KINDS")
    assert frozenset(_ALL_KIND_STEPS) == declared

    tool = _node_tool(Method(kind="host", params={"host_setup": True}), _group_method())
    recorder = RunRecorder()
    outcomes = execute_plan(
        [_reconfigure_row("superpowers", _ALL_KIND_STEPS[kind])],
        _run_context(recorder, catalog={"superpowers": tool}),
    )
    assert outcomes[0].result == "done", kind
    assert outcomes[0].detail == "", kind
    # The two built-in kinds act through a bound seam instead of the runner,
    # so nothing is recorded as a command; the other six run exactly one argv.
    assert len(recorder.argv) == (0 if kind in {"terminal_sync", "pnpm_group_install"} else 1), kind


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
    second = _reconfigure_row(
        "b", ConfigStep("run follow-up", "skill_install", "codex", ("touch", "done"))
    )

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
    assert recorder.argv == [["touch", "done"]]


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        (
            (
                ConfigStep("run command", "skill_install", "codex", ("run",)),
                ConfigStep("handoff", "skill_install", "codex"),
            ),
            True,
        ),
        ((ConfigStep("handoff", "skill_install", "codex"),), False),
    ],
)
def test_a_manual_reconfigure_row_ran_only_when_it_had_a_command_step(
    steps: tuple[ConfigStep, ...], expected: bool
) -> None:
    outcome = RowOutcome(
        _reconfigure_row("manual", *steps),
        "manual",
        install=InstallOutcome("manual", InstallStatus.MANUAL_REQUIRED, handoff=("do it",)),
    )
    assert ran_anything([outcome]) is expected


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


def test_skill_install_without_argv_is_a_reviewed_handoff_and_manual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """19 L-19-07: a harness the installer cannot write to gets instructions.

    `partial_steps` builds this step with an empty argv because the pack is
    reviewed manual-only, so running one is never an option: the lines land on
    `RowOutcome.install.handoff` and `render_handoff` prints them unchanged.
    """
    instructions = (
        "Run each block inside the named host.",
        "Codex:",
        "  codex plugin add superpowers",
    )

    def _handoff(*_args: object) -> LifecycleOutcome:
        return LifecycleOutcome("manual-required", instructions)

    monkeypatch.setattr(session_module, "perform_action", _handoff)
    tool = _handoff_tool(SkillOperation("manual-required", by_harness=(("codex", instructions),)))
    _reasons, steps = skill_lifecycle.partial_steps(tool, ["codex"])
    assert steps[0].argv == ()

    recorder = RunRecorder()
    outcome = execute_plan(
        [_reconfigure_row("superpowers", *steps)],
        _run_context(recorder, catalog={"superpowers": tool}),
    )[0]

    assert outcome.result == "manual"
    assert outcome.install is not None
    assert outcome.install.status is InstallStatus.MANUAL_REQUIRED
    assert outcome.install.handoff == instructions
    assert recorder.argv == []

    enable = ConfigStep("enable superpowers in user scope", "plugin_enable", "claude", _ENABLE)
    mixed_recorder = RunRecorder()
    mixed = execute_plan(
        [_reconfigure_row("superpowers", enable, *steps)],
        _run_context(mixed_recorder, catalog={"superpowers": tool}),
    )[0]
    assert mixed.result == "manual"
    assert mixed_recorder.argv == [list(_ENABLE)]
    assert mixed.install is not None
    assert mixed.install.handoff == instructions


@pytest.mark.parametrize(
    "status, expected_detail",
    [
        ("completed", ""),
        ("present", ""),
        ("absent", "skill install reported absent"),
        ("unknown", "skill install reported unknown"),
    ],
)
def test_skill_install_reports_what_the_lifecycle_returned(
    monkeypatch: pytest.MonkeyPatch, status: LifecycleStatus, expected_detail: str
) -> None:
    """The step takes the lifecycle's own answer, including the two failure words."""

    def _outcome(*_args: object) -> LifecycleOutcome:
        return LifecycleOutcome(status)

    monkeypatch.setattr(session_module, "perform_action", _outcome)
    tool = _handoff_tool(SkillOperation("manual-required"))
    step = ConfigStep("install superpowers for Codex", "skill_install", "codex")

    outcome = execute_plan(
        [_reconfigure_row("superpowers", step)],
        _run_context(RunRecorder(), catalog={"superpowers": tool}),
    )[0]

    if expected_detail:
        assert outcome.result == "failed"
        assert outcome.detail == f"{step.text}: {expected_detail}"
    else:
        assert outcome.result == "done"
        assert outcome.detail == ""


def test_skill_install_with_argv_runs_it() -> None:
    """A pack the installer CAN write to runs its own reviewed argv instead."""
    recorder = RunRecorder()
    tool = _handoff_tool(SkillOperation("manual-required"))
    step = ConfigStep(
        "install superpowers for Codex", "skill_install", "codex", ("codex", "plugin", "add", "x")
    )

    outcome = execute_plan(
        [_reconfigure_row("superpowers", step)],
        _run_context(recorder, catalog={"superpowers": tool}),
    )[0]

    assert outcome.result == "done"
    assert recorder.argv == [["codex", "plugin", "add", "x"]]


def test_skill_install_without_an_executable_operation_crashes_the_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail closed: a producer that broke the partial_steps invariant is a bug.

    `perform_action` raises ValueError when the lifecycle has no reviewed
    executable operation for the action. That stays outside the per-step catch
    list, so the row takes the per-row crashed path from 20-07 (exit 1, row
    kept selected) instead of reading as a clean step failure.
    """

    def _raise(*_args: object) -> LifecycleOutcome:
        raise ValueError("no reviewed executable lifecycle operation for 'install'")

    monkeypatch.setattr(session_module, "perform_action", _raise)
    tool = _handoff_tool(SkillOperation("manual-required"))
    step = ConfigStep("install superpowers for Codex", "skill_install", "codex")
    recorder = RunRecorder()

    outcomes = execute_plan(
        [_reconfigure_row("superpowers", step)],
        _run_context(recorder, catalog={"superpowers": tool}),
    )

    assert outcomes[0].result == "crashed"
    assert outcomes[0].detail.startswith("ValueError:")
    assert recorder.argv == []
    assert exit_code(outcomes) == 1


def test_an_unknown_step_kind_fails_closed_instead_of_running_argv() -> None:
    """The guard behind `_STEP_KINDS`: a kind with no branch never executes.

    The model's literal type rejects this kind at build time; a plan built by
    an older producer, or hand-edited, can still carry one, so the dispatcher
    refuses it rather than treating its argv as just another command.
    """
    step = ConfigStep(
        "do the new thing", cast(ConfigStepKind, "brand_new_kind"), "claude", ("claude", "run", "x")
    )
    recorder = RunRecorder()

    outcome = execute_plan(
        [_reconfigure_row("gsd", step)],
        _run_context(recorder, catalog={"gsd": _tool("gsd")}),
    )[0]

    assert outcome.result == "failed"
    assert outcome.detail == f"{step.text}: step kind has no branch"
    assert recorder.argv == []


def test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next() -> None:
    """The D-18 order holds when the row starts with a kind that runs no argv.

    A built-in step can be the first failure in a row whose later steps do run
    commands; stopping there is what keeps a failed enable from being followed
    by the removal that would delete the only working copy.
    """
    sync = ConfigStep("point iTerm2 at zsh", "terminal_sync")
    enable = ConfigStep("enable gsd-core in user scope", "plugin_enable", "claude", _ENABLE)
    recorder = RunRecorder()
    unbound = replace(_run_context(recorder, catalog={"gsd": _tool("gsd")}), terminal_sync=None)

    outcome = execute_plan([_reconfigure_row("gsd", sync, enable)], unbound)[0]

    assert outcome.result == "failed"
    assert outcome.detail == f"{sync.text}: no terminal synchronizer bound"
    assert recorder.argv == []
