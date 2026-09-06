from collections.abc import Mapping

import pytest

from installer.engine import ChecksumPolicy, InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.run import Runner
from installer.session import (
    Install,
    MismatchChoice,
    Summary,
    order_for_install,
    run_installs,
    summarize,
)
from installer.versions import TagResolver


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


@pytest.mark.parametrize("status", ["failed", "no-method", "checksum-mismatch"])
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
