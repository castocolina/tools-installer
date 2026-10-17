import inspect
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import installer.engine as engine
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import Runner
from installer.session import (
    Disposition,
    Install,
    MismatchChoice,
    OnMismatch,
    PlanRow,
    Result,
    RowOutcome,
    RunContext,
    Summary,
    execute_plan,
    exit_code,
    fold_run,
    order_for_install,
    ran_anything,
    retained,
    run_installs,
    summarize,
    summary_counts,
    with_sensitive_confirm,
)
from installer.update import UpdateOutcome
from installer.versions import TagResolver
from tests.state_doubles import RunRecorder


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
    should_continue: Callable[[], bool] | None = None,
    on_row_started: Callable[[PlanRow], None] | None = None,
    on_outcome: Callable[[RowOutcome], None] | None = None,
) -> RunContext:
    return RunContext(
        catalog=catalog or {},
        platform=_platform(),
        runner=recorder.runner,
        resolve_tag=lambda _repo: "1.0.0",
        install=recorder.install,
        terminal_sync=recorder.terminal_sync,
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
    assert ran_anything([outcome]) is (
        result in {"done", "failed", "mismatch", "crashed", "manual"}
    )


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


def test_order_for_install_sorts_by_priority_then_keeps_catalog_order():
    tools = [_tool("a", "P3"), _tool("b", "P0"), _tool("c", "P3"), _tool("d", "P1")]
    assert [t.id for t in order_for_install(tools)] == ["b", "d", "a", "c"]


def test_tool_rejects_unknown_priority():
    with pytest.raises(ValueError, match="unknown priority"):
        _tool("x", "P99")


def test_run_installs_calls_install_per_tool_with_injected_deps():
    tools = [_tool("rg"), _tool("jq")]
    platform = _platform()
    seen: list[tuple[str, str]] = []

    def fake_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        seen.append((tool.id, platform.os))
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    def runner(cmd: list[str]) -> None:
        return None

    def resolve_tag(repo: str) -> str:
        return "1.0.0"

    outcomes = run_installs(tools, platform, runner, resolve_tag, fake_install)
    assert seen == [("rg", "fedora"), ("jq", "fedora")]
    assert [o.tool_id for o in outcomes] == ["rg", "jq"]


def test_summarize_buckets_by_status():
    outcomes = [
        InstallOutcome("rg", "installed"),
        InstallOutcome("jq", "already-installed"),
        InstallOutcome("fd", "failed"),
        InstallOutcome("bat", "no-method"),
        InstallOutcome("uv", "installed"),
    ]
    assert summarize(outcomes) == Summary(
        installed=("rg", "uv"),
        already=("jq",),
        failed=("fd",),
        no_method=("bat",),
    )


def test_summarize_empty_is_all_empty():
    assert summarize([]) == Summary(installed=(), already=(), failed=(), no_method=())


def test_summarize_buckets_manual_required() -> None:
    outcomes = [
        InstallOutcome(
            "pi",
            "manual-required",
            method_kind="host_setup",
            handoff=("run these commands",),
        ),
        InstallOutcome("rg", "installed"),
    ]
    summary = summarize(outcomes)
    assert summary.manual_required == ("pi",)
    assert summary.installed == ("rg",)


def _mismatch_then_install() -> tuple[list[tuple[str, str]], Install]:
    """An Install fake that mismatches on the first call per tool, then installs."""
    seen: list[tuple[str, str]] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        seen.append((tool.id, checksum_policy))
        if len([s for s in seen if s[0] == tool.id]) == 1 and checksum_policy == "fail":
            return InstallOutcome(tool.id, "checksum-mismatch", method_kind="github_release")
        return InstallOutcome(tool.id, "installed", method_kind="github_release")

    return seen, install


def test_on_mismatch_retry_reinstalls_with_default_policy() -> None:
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "retry"

    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert seen == [("rg", "fail"), ("rg", "fail")]
    assert outcomes[0].status == "installed"


def test_on_mismatch_fallback_reinstalls_with_continue_policy() -> None:
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "fallback"

    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert seen == [("rg", "fail"), ("rg", "continue")]
    assert outcomes[0].status == "installed"


def test_on_mismatch_skip_keeps_the_mismatch_outcome() -> None:
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "skip"

    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert seen == [("rg", "fail")]
    assert outcomes[0].status == "checksum-mismatch"


def test_without_on_mismatch_the_outcome_stands() -> None:
    seen, install = _mismatch_then_install()
    outcomes = run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install
    )
    assert seen == [("rg", "fail")]
    assert outcomes[0].status == "checksum-mismatch"


def test_on_mismatch_is_not_consulted_for_clean_installs() -> None:
    asked: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "skip"

    run_installs(
        [_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install, on_mismatch
    )
    assert asked == []


def test_summarize_buckets_checksum_mismatch() -> None:
    outcomes = [
        InstallOutcome("rg", "installed"),
        InstallOutcome("fd", "checksum-mismatch"),
    ]
    summary = summarize(outcomes)
    assert summary.installed == ("rg",)
    assert summary.mismatched == ("fd",)


def test_dependent_is_skipped_when_its_dependency_failed() -> None:
    called: list[str] = []

    def fake_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        called.append(tool.id)
        return InstallOutcome(tool.id, "failed")

    outcomes = run_installs(
        [_tool("sdkman"), _tool("java", requires=("sdkman",))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        fake_install,
    )
    assert [(o.tool_id, str(o.status)) for o in outcomes] == [
        ("sdkman", "failed"),
        ("java", "dependency-failed"),
    ]
    assert outcomes[1].blocked_by == ("sdkman",)
    assert called == ["sdkman"]


def test_summarize_buckets_dependency_failed() -> None:
    outcomes = [
        InstallOutcome("sdkman", "failed"),
        InstallOutcome("java", "dependency-failed", blocked_by=("sdkman",)),
    ]
    summary = summarize(outcomes)
    assert summary.failed == ("sdkman",)
    assert summary.dependency_failed == ("java",)


def _failing_install(*failed_ids: str, status: str = "failed") -> tuple[list[str], Install]:
    calls: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        calls.append(tool.id)
        if tool.id in failed_ids:
            return InstallOutcome(tool.id, status)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    return calls, install


def test_dependency_failure_propagates_down_a_chain() -> None:
    calls, install = _failing_install("a")
    outcomes = run_installs(
        [_tool("a"), _tool("b", requires=("a",)), _tool("c", requires=("b",))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
    )
    assert [o.tool_id for o in outcomes] == ["a", "b", "c"]
    assert outcomes[0].status == "failed"
    assert outcomes[1].status == "dependency-failed"
    assert outcomes[2].status == "dependency-failed"
    assert outcomes[1].blocked_by == ("a",)
    assert outcomes[2].blocked_by == ("b",)
    assert calls == ["a"]


@pytest.mark.parametrize("status", ["failed", "no-method", "checksum-mismatch", "manual-required"])
def test_every_unresolved_status_blocks_a_dependent(status: str) -> None:
    calls, install = _failing_install("dep", status=status)
    outcomes = run_installs(
        [_tool("dep"), _tool("user", requires=("dep",))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
    )
    assert calls == ["dep"]
    assert outcomes[1].status == "dependency-failed"
    assert outcomes[1].blocked_by == ("dep",)


@pytest.mark.parametrize("status", ["installed", "already-installed"])
def test_successful_statuses_never_block_a_dependent(status: str) -> None:
    calls: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        calls.append(tool.id)
        return InstallOutcome(tool.id, status, method_kind="brew")

    outcomes = run_installs(
        [_tool("dep"), _tool("user", requires=("dep",))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
    )
    assert calls == ["dep", "user"]
    assert outcomes[0].status == status
    assert outcomes[1].status == status
    assert outcomes[1].blocked_by == ()


def test_an_unrelated_tool_still_installs_after_a_failure() -> None:
    calls, install = _failing_install("a")
    outcomes = run_installs(
        [_tool("a"), _tool("b", requires=("a",)), _tool("rg")],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
    )
    assert calls == ["a", "rg"]
    assert outcomes[2].status == "installed"
    assert outcomes[2].blocked_by == ()


def test_only_the_matching_requires_ids_are_reported_as_blockers() -> None:
    calls, install = _failing_install("a")
    outcomes = run_installs(
        [_tool("a"), _tool("user", requires=("a", "uv"))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
    )
    assert calls == ["a"]
    assert outcomes[1].blocked_by == ("a",)

    calls_dup, install_dup = _failing_install("a")
    outcomes_dup = run_installs(
        [_tool("a"), _tool("user", requires=("a", "a"))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install_dup,
    )
    assert calls_dup == ["a"]
    assert outcomes_dup[1].blocked_by == ("a",)


def test_a_retried_mismatch_does_not_block_its_dependents() -> None:
    seen, install = _mismatch_then_install()

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return "retry"

    outcomes = run_installs(
        [_tool("dep"), _tool("user", requires=("dep",))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
        on_mismatch,
    )
    assert [entry[0] for entry in seen] == ["dep", "dep", "user", "user"]
    assert outcomes[0].status == "installed"
    assert outcomes[1].status == "installed"
    assert outcomes[1].blocked_by == ()


def test_a_dependent_listed_before_its_dependency_is_still_attempted() -> None:
    calls, install = _failing_install("a")
    outcomes = run_installs(
        [_tool("b", requires=("a",)), _tool("a")],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
    )
    assert calls == ["b", "a"]
    assert outcomes[0].status == "installed"
    assert outcomes[1].status == "failed"
    assert outcomes[0].blocked_by == ()


def test_run_installs_threads_catalog_into_every_install_call() -> None:
    """catalog reaches install(...)'s `tools` keyword at all three call sites:
    the initial attempt, the mismatch-retry, and the mismatch-fallback."""
    seen: list[Mapping[str, Tool] | None] = []
    call_counts: dict[str, int] = {}

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        seen.append(tools)
        call_counts[tool.id] = call_counts.get(tool.id, 0) + 1
        if call_counts[tool.id] == 1:
            return InstallOutcome(tool.id, "checksum-mismatch", method_kind="github_release")
        return InstallOutcome(tool.id, "installed", method_kind="github_release")

    catalog = {"rg": _tool("rg")}
    choices: list[MismatchChoice] = ["retry", "fallback"]

    def on_mismatch(tool_id: str) -> MismatchChoice:
        return choices.pop(0)

    outcomes = run_installs(
        [_tool("retry-me"), _tool("fallback-me")],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        install,
        on_mismatch,
        catalog=catalog,
    )
    assert all(mapping is catalog for mapping in seen)
    assert len(seen) == 4  # initial + retry for retry-me, initial + fallback for fallback-me
    assert outcomes[0].status == "installed"
    assert outcomes[1].status == "installed"


def test_run_installs_catalog_defaults_to_none_for_untouched_callers() -> None:
    seen: list[Mapping[str, Tool] | None] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        seen.append(tools)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    run_installs([_tool("rg")], _platform(), lambda cmd: None, lambda repo: "1.0.0", install)
    assert seen == [None]


def test_run_installs_preexisting_parameters_stay_positional() -> None:
    params = inspect.signature(run_installs).parameters
    positional = [
        name
        for name, value in params.items()
        if value.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    assert positional == [
        "tools",
        "platform",
        "runner",
        "resolve_tag",
        "install",
        "on_mismatch",
        "catalog",
    ]
    assert params["should_continue"].kind is inspect.Parameter.KEYWORD_ONLY


def test_run_installs_should_continue_stops_between_tools() -> None:
    called: list[str] = []

    def fake_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        called.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    remaining = [True, True, False]

    def should_continue() -> bool:
        return remaining.pop(0)

    tools = [_tool("rg"), _tool("jq"), _tool("fd")]
    outcomes = run_installs(
        tools,
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        fake_install,
        should_continue=should_continue,
    )
    assert [o.tool_id for o in outcomes] == ["rg", "jq"]
    assert called == ["rg", "jq"]
    not_attempted = [tool.id for tool in tools if tool.id not in {o.tool_id for o in outcomes}]
    assert not_attempted == ["fd"]


def test_run_installs_should_continue_is_checked_before_dependency_blocked() -> None:
    called: list[str] = []

    def fake_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
    ) -> InstallOutcome:
        called.append(tool.id)
        return InstallOutcome(tool.id, "failed")

    remaining = [True, False]

    def should_continue() -> bool:
        return remaining.pop(0)

    outcomes = run_installs(
        [_tool("sdkman"), _tool("java", requires=("sdkman",))],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        fake_install,
        should_continue=should_continue,
    )
    assert [o.tool_id for o in outcomes] == ["sdkman"]
    assert outcomes[0].status == "failed"
    assert called == ["sdkman"]
    assert all(o.status != "dependency-failed" for o in outcomes)


def test_summarize_over_truncated_outcomes_still_buckets() -> None:
    summary = summarize(
        [
            InstallOutcome("rg", "installed"),
            InstallOutcome("jq", "failed"),
        ]
    )
    assert summary.installed == ("rg",)
    assert summary.failed == ("jq",)
    assert summary.already == ()
    assert summary.no_method == ()
    assert summary.mismatched == ()
    assert summary.dependency_failed == ()
    assert summary.manual_required == ()


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


def test_with_sensitive_confirm_reaches_post_install_gate(
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
    yes = with_sensitive_confirm(lambda _id, _action: True)
    no = with_sensitive_confirm(lambda _id, _action: False)
    yes_outcomes = run_installs([tool], platform, lambda cmd: None, lambda repo: "1.0.0", yes)
    no_outcomes = run_installs([tool], platform, lambda cmd: None, lambda repo: "1.0.0", no)
    assert yes_outcomes[0].post_install_handoff
    assert no_outcomes[0].post_install_handoff == ()


def test_with_sensitive_confirm_forwards_bound_confirmation_and_unchanged_kwargs() -> None:
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
    bound = with_sensitive_confirm(confirm, recording_install)
    run_installs(
        [_tool("rg")],
        _platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        bound,
        catalog=catalog,
    )
    assert seen == [("fail", catalog, confirm)]


def test_with_sensitive_confirm_none_is_callable_and_produces_no_instructions(
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
    bound = with_sensitive_confirm(None)
    outcomes = run_installs(
        [_login_shell_tool()],
        _mutable_platform(),
        lambda cmd: None,
        lambda repo: "1.0.0",
        bound,
    )
    assert outcomes[0].post_install_handoff == ()


def test_install_protocol_parameters_are_unchanged() -> None:
    params = list(inspect.signature(Install.__call__).parameters)
    assert params == [
        "self",
        "tool",
        "platform",
        "runner",
        "resolve_tag",
        "checksum_policy",
        "tools",
    ]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"failed": ("rg",)}, True),
        ({"mismatched": ("rg",)}, True),
        ({"dependency_failed": ("rg",)}, True),
        ({"not_attempted": ("rg",)}, True),
        ({"update_failed": ("rg",)}, True),
        ({"crash_error": "boom"}, True),
        ({"no_method": ("rg",)}, False),
        ({"manual_required": ("rg",)}, False),
        ({}, False),
    ],
)
def test_summary_has_failure(kwargs: dict[str, object], expected: bool) -> None:
    summary = replace(Summary(installed=(), already=(), failed=(), no_method=()), **kwargs)  # pyright: ignore[reportArgumentType]
    assert summary.has_failure is expected


def test_fold_run_records_not_attempted_update_failures_and_crash() -> None:

    summary = Summary(installed=("a",), already=(), failed=(), no_method=())
    folded = fold_run(
        summary,
        not_attempted=["b"],
        update_outcomes=[
            UpdateOutcome("u1", "failed", "brew"),
            UpdateOutcome("u2", "updated", "brew"),
            UpdateOutcome("u3", "unknown-owner", "unknown"),
        ],
        update_errors=[("u4", "boom")],
        error="crash",
    )
    assert folded.not_attempted == ("b",)
    assert folded.update_failed == ("u1", "u4")
    assert folded.crash_error == "crash"
    assert folded.installed == ("a",)
    assert folded.failed == ()
    assert folded.has_failure is True


def test_fold_run_drops_duplicate_update_failure_ids() -> None:

    summary = Summary(installed=(), already=(), failed=(), no_method=())
    folded = fold_run(
        summary,
        not_attempted=[],
        update_outcomes=[UpdateOutcome("u1", "failed", "brew")],
        update_errors=[("u1", "boom")],
        error=None,
    )
    assert folded.update_failed == ("u1",)
    assert folded.has_failure is True
