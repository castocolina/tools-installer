from installer.engine import InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.session import Summary, order_for_install, run_installs, summarize


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


def test_order_for_install_puts_unknown_priority_last():
    tools = [_tool("x", "P99"), _tool("y", "P3"), _tool("z", "P0")]
    assert [t.id for t in order_for_install(tools)] == ["z", "y", "x"]


def test_run_installs_calls_install_per_tool_with_injected_deps():
    tools = [_tool("rg"), _tool("jq")]
    platform = _platform()
    seen: list[tuple[str, str]] = []

    def fake_install(
        tool: Tool, plat: Platform, runner: object, resolve_version: object
    ) -> InstallOutcome:
        seen.append((tool.id, plat.os))
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    def runner(cmd: list[str]) -> None:
        return None

    def resolve_version(repo: str) -> str:
        return "1.0.0"

    outcomes = run_installs(tools, platform, runner, resolve_version, fake_install)
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
