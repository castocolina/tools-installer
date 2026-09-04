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


def _tool(tool_id: str, priority: str = "P3") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        priority=priority,
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
