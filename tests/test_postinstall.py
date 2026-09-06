from itertools import combinations
from pathlib import Path

import pytest

import installer.postinstall as pi
from installer.model import Method, Tool
from installer.run import CommandError, Runner

_ALL_HOSTS = ("claude", "codex", "opencode", "cursor-agent")
_ALL_SUBSETS: list[tuple[str, ...]] = [
    subset for size in range(len(_ALL_HOSTS) + 1) for subset in combinations(_ALL_HOSTS, size)
]
# Mirrors installer.postinstall's own (private) _CODEGRAPH_TARGETS mapping and
# declared order, kept here rather than reaching into that private module
# symbol from the test.
_EXPECTED_TARGET_FOR = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor-agent": "cursor",
}


def _tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="ai",
        cmd=tool_id,
        methods=(Method(kind="github_release", params={}),),
        tier="ai",
    )


def _tools() -> dict[str, Tool]:
    return {t: _tool(t) for t in ("claude", "codex", "opencode", "cursor-agent")}


def test_codegraph_hook_composes_csv_from_present_hosts_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    def fake_is_installed(tool: Tool) -> bool:
        return tool.id in ("claude", "cursor-agent")

    monkeypatch.setattr(pi, "is_installed", fake_is_installed)
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("codegraph-mcp-register", method, runner, _tools())
    assert warning is None
    expected_bin = str(Path.home() / ".local" / "bin" / "codegraph")
    assert calls == [
        [
            expected_bin,
            "install",
            "--target",
            "claude,cursor",
            "--location",
            "global",
            "--yes",
            "--no-permissions",
        ]
    ]


def test_codegraph_hook_noops_when_no_host_present(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    def fake_none_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(pi, "is_installed", fake_none_installed)
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("codegraph-mcp-register", method, runner, _tools())
    assert warning is None
    assert calls == []


def _only_claude_installed(tool: Tool) -> bool:
    return tool.id == "claude"


def test_codegraph_hook_invokes_the_resolved_absolute_binary_path_not_a_bare_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("codegraph-mcp-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "codegraph")
    assert calls[0][0] == expected_bin

    calls.clear()
    custom_method = Method(kind="github_release", params={"bin_dir": "/custom/dir"})
    pi.run_postinstall(
        "codegraph-mcp-register", custom_method, lambda cmd: calls.append(cmd), _tools()
    )
    assert calls[0][0] == "/custom/dir/codegraph"


@pytest.mark.parametrize("bad_bin_dir", [True, 123])
def test_codegraph_hook_ignores_a_non_string_bin_dir_param(
    monkeypatch: pytest.MonkeyPatch, bad_bin_dir: object
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={"bin_dir": bad_bin_dir})
    pi.run_postinstall("codegraph-mcp-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "codegraph")
    assert calls[0][0] == expected_bin


def test_codegraph_hook_returns_a_warning_string_on_command_error_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)

    def failing_runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("codegraph-mcp-register", method, failing_runner, _tools())
    assert warning is not None
    assert "codegraph MCP registration failed" in warning


def test_run_postinstall_dispatches_by_name_and_forwards_method_and_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[Method, Runner, dict[str, Tool]]] = []

    def fake_hook(method: Method, runner: Runner, tools: dict[str, Tool]) -> str | None:
        seen.append((method, runner, tools))
        return None

    def unused_runner(cmd: list[str]) -> None:
        return None

    monkeypatch.setitem(pi.POSTINSTALL_HOOKS, "codegraph-mcp-register", fake_hook)
    method = Method(kind="github_release", params={})
    tools = _tools()
    result = pi.run_postinstall("codegraph-mcp-register", method, unused_runner, tools)
    assert result is None
    assert seen == [(method, unused_runner, tools)]


def test_run_postinstall_unknown_name_is_a_noop() -> None:
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    result = pi.run_postinstall("not-a-real-hook", method, lambda cmd: calls.append(cmd), {})
    assert result is None
    assert calls == []


@pytest.mark.parametrize("present_subset", _ALL_SUBSETS, ids=lambda s: ",".join(s) or "none")
def test_codegraph_hook_matches_expected_argv_for_every_host_presence_subset(
    monkeypatch: pytest.MonkeyPatch, present_subset: tuple[str, ...]
) -> None:
    """Every one of the 16 subsets of the four hosts produces either the exact
    expected argv (never "auto") or a genuine no-op — never anything else."""
    present = set(present_subset)

    def fake_is_installed(tool: Tool) -> bool:
        return tool.id in present

    monkeypatch.setattr(pi, "is_installed", fake_is_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall(
        "codegraph-mcp-register", method, lambda cmd: calls.append(cmd), _tools()
    )
    assert warning is None
    if not present_subset:
        assert calls == []
        return
    expected_csv = ",".join(
        target for tool_id, target in _EXPECTED_TARGET_FOR.items() if tool_id in present
    )
    expected_bin = str(Path.home() / ".local" / "bin" / "codegraph")
    assert calls == [
        [
            expected_bin,
            "install",
            "--target",
            expected_csv,
            "--location",
            "global",
            "--yes",
            "--no-permissions",
        ]
    ]
    for cmd in calls:
        assert "auto" not in cmd


def _all_installed(tool: Tool) -> bool:
    return True


def test_codegraph_hook_preserves_declared_host_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi, "is_installed", _all_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("codegraph-mcp-register", method, lambda cmd: calls.append(cmd), _tools())
    assert calls[0][calls[0].index("--target") + 1] == "claude,codex,opencode,cursor"


def test_codegraph_hook_maps_cursor_agent_alone_to_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    def only_cursor_agent(tool: Tool) -> bool:
        return tool.id == "cursor-agent"

    monkeypatch.setattr(pi, "is_installed", only_cursor_agent)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("codegraph-mcp-register", method, lambda cmd: calls.append(cmd), _tools())
    assert calls[0][calls[0].index("--target") + 1] == "cursor"


def test_codegraph_hook_always_passes_no_permissions(monkeypatch: pytest.MonkeyPatch) -> None:
    """codegraph's own --yes also enables a Claude auto-allow list and a
    UserPromptSubmit hook, not merely non-interactivity (dual-lane review,
    codex-sol-high second lane) -- --no-permissions keeps this call scoped to
    MCP registration only, per REQ-codegraph-mcp-postinstall's literal wording.
    """
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("codegraph-mcp-register", method, lambda cmd: calls.append(cmd), _tools())
    assert "--no-permissions" in calls[0]


def test_codegraph_hook_treats_a_missing_tool_id_as_absent_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-01 (internal dual-lane review): bare `tools[tool_id]` indexing would
    raise KeyError -- surfaced only as a confusing generic "crashed" warning --
    for any caller (or future registry rename) whose `tools` mapping omits one
    of the four hardcoded host ids. A missing id must behave exactly like an
    id present but not installed: silently excluded from the composed CSV.
    """
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    incomplete_tools = {"claude": _tool("claude")}  # codex/opencode/cursor-agent absent entirely
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall(
        "codegraph-mcp-register", method, lambda cmd: calls.append(cmd), incomplete_tools
    )
    assert warning is None
    assert calls[0][calls[0].index("--target") + 1] == "claude"
