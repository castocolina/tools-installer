from pathlib import Path

import pytest

import installer.postinstall as pi
from installer.model import Method, Tool
from installer.run import CommandError, Runner


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
        [expected_bin, "install", "--target", "claude,cursor", "--location", "global", "--yes"]
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
