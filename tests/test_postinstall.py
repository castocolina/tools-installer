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


def test_present_agent_hosts_empty_tools_returns_empty_frozenset() -> None:
    assert pi.present_agent_hosts({}) == frozenset()


def test_present_agent_hosts_all_four_installed_returns_all_four(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _all_installed)
    assert pi.present_agent_hosts(_tools()) == frozenset(_ALL_HOSTS)


def test_present_agent_hosts_missing_id_behaves_like_present_but_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    incomplete_tools = {"claude": _tool("claude")}
    assert pi.present_agent_hosts(incomplete_tools) == frozenset({"claude"})


def test_present_agent_hosts_return_type_is_frozenset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    result = pi.present_agent_hosts(_tools())
    assert isinstance(result, frozenset)


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


def test_resolve_rtk_binary_github_release_uses_bin_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    method = Method(kind="github_release", params={})
    expected = str(Path.home() / ".local" / "bin" / "rtk")
    assert pi._resolve_rtk_binary(method) == expected  # pyright: ignore[reportPrivateUsage]


def test_resolve_rtk_binary_github_release_honors_custom_bin_dir() -> None:
    method = Method(kind="github_release", params={"bin_dir": "/custom/dir"})
    result = pi._resolve_rtk_binary(method)  # pyright: ignore[reportPrivateUsage]
    assert result == "/custom/dir/rtk"


def _fake_which_found(name: str) -> str | None:
    return "/usr/local/bin/rtk"


def _fake_which_missing(name: str) -> str | None:
    return None


def test_resolve_rtk_binary_brew_uses_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi.shutil, "which", _fake_which_found)
    method = Method(kind="brew", params={})
    result = pi._resolve_rtk_binary(method)  # pyright: ignore[reportPrivateUsage]
    assert result == "/usr/local/bin/rtk"


def test_resolve_rtk_binary_brew_falls_back_to_bin_dir_when_not_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi.shutil, "which", _fake_which_missing)
    method = Method(kind="brew", params={})
    expected = str(Path.home() / ".local" / "bin" / "rtk")
    result = pi._resolve_rtk_binary(method)  # pyright: ignore[reportPrivateUsage]
    assert result == expected


def test_rtk_hook_composes_init_argv_when_claude_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    assert warning is None
    expected_bin = str(Path.home() / ".local" / "bin" / "rtk")
    assert calls == [[expected_bin, "init", "-g", "--auto-patch"]]


def test_rtk_hook_noops_when_claude_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def none_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(pi, "is_installed", none_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    assert warning is None
    assert calls == []


def test_rtk_hook_ensures_claude_config_dir_exists_before_invoking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    ensure_dir_calls: list[Path] = []

    def fake_ensure_dir(directory: Path) -> Path:
        ensure_dir_calls.append(directory)
        return directory

    monkeypatch.setattr(pi, "ensure_dir", fake_ensure_dir)
    method = Method(kind="github_release", params={})
    pi.run_postinstall("rtk-register", method, lambda cmd: None, _tools())
    assert ensure_dir_calls == [Path.home() / ".claude"]


def test_rtk_hook_returns_warning_string_on_command_error_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)

    def failing_runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("rtk-register", method, failing_runner, _tools())
    assert warning is not None
    assert "claude" in warning


def test_rtk_hook_opencode_argv_includes_opencode_and_auto_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def only_opencode(tool: Tool) -> bool:
        return tool.id == "opencode"

    monkeypatch.setattr(pi, "is_installed", only_opencode)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "rtk")
    assert calls == [[expected_bin, "init", "-g", "--opencode", "--auto-patch"]]


def test_rtk_hook_codex_argv_never_includes_auto_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    def only_codex(tool: Tool) -> bool:
        return tool.id == "codex"

    monkeypatch.setattr(pi, "is_installed", only_codex)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "rtk")
    assert calls == [[expected_bin, "init", "-g", "--codex"]]
    assert "--auto-patch" not in calls[0]


def test_rtk_hook_cursor_agent_fires_when_claude_also_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def claude_and_cursor(tool: Tool) -> bool:
        return tool.id in ("claude", "cursor-agent")

    monkeypatch.setattr(pi, "is_installed", claude_and_cursor)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "rtk")
    assert [expected_bin, "init", "-g", "--agent", "cursor", "--auto-patch"] in calls


def test_rtk_hook_cursor_agent_never_fires_when_claude_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def only_cursor_agent(tool: Tool) -> bool:
        return tool.id == "cursor-agent"

    monkeypatch.setattr(pi, "is_installed", only_cursor_agent)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    assert warning is None
    assert calls == []


def test_rtk_hook_ensures_cursor_config_dir_only_on_the_firing_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def claude_and_cursor(tool: Tool) -> bool:
        return tool.id in ("claude", "cursor-agent")

    monkeypatch.setattr(pi, "is_installed", claude_and_cursor)
    ensure_dir_calls: list[Path] = []

    def fake_ensure_dir(directory: Path) -> Path:
        ensure_dir_calls.append(directory)
        return directory

    monkeypatch.setattr(pi, "ensure_dir", fake_ensure_dir)
    method = Method(kind="github_release", params={})
    pi.run_postinstall("rtk-register", method, lambda cmd: None, _tools())
    assert ensure_dir_calls == [Path.home() / ".claude", Path.home() / ".cursor"]


@pytest.mark.parametrize("present_subset", _ALL_SUBSETS, ids=lambda s: ",".join(s) or "none")
def test_rtk_hook_matches_expected_argv_for_every_host_presence_subset(
    monkeypatch: pytest.MonkeyPatch, present_subset: tuple[str, ...]
) -> None:
    """Every one of the 16 subsets of the four hosts produces either the exact
    expected per-host argv or a documented no-op -- never a crash, and the
    cursor-agent branch only ever fires when claude is also present."""
    present = set(present_subset)

    def fake_is_installed(tool: Tool) -> bool:
        return tool.id in present

    monkeypatch.setattr(pi, "is_installed", fake_is_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    assert warning is None
    expected_bin = str(Path.home() / ".local" / "bin" / "rtk")
    expected_calls: list[list[str]] = []
    if "claude" in present:
        expected_calls.append([expected_bin, "init", "-g", "--auto-patch"])
    if "opencode" in present:
        expected_calls.append([expected_bin, "init", "-g", "--opencode", "--auto-patch"])
    if "codex" in present:
        expected_calls.append([expected_bin, "init", "-g", "--codex"])
    if "cursor-agent" in present and "claude" in present:
        expected_calls.append([expected_bin, "init", "-g", "--agent", "cursor", "--auto-patch"])
    assert calls == expected_calls
    for cmd in calls:
        assert "--auto-patch" not in cmd or "--codex" not in cmd


def test_rtk_hook_never_invokes_the_same_host_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi, "is_installed", _all_installed)
    calls: list[list[str]] = []
    method = Method(kind="github_release", params={})
    pi.run_postinstall("rtk-register", method, lambda cmd: calls.append(cmd), _tools())
    assert len(calls) == len({tuple(c) for c in calls})


def test_rtk_hook_continues_past_a_command_error_and_captures_partial_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _all_installed)

    def failing_on_opencode(cmd: list[str]) -> None:
        if "--opencode" in cmd:
            raise CommandError(cmd, 1)

    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("rtk-register", method, failing_on_opencode, _tools())
    assert warning is not None
    assert "opencode" in warning
    assert "claude" not in warning.split(";")[0]


def test_graphify_hook_noops_when_no_host_present(monkeypatch: pytest.MonkeyPatch) -> None:
    def none_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(pi, "is_installed", none_installed)
    calls: list[list[str]] = []
    method = Method(kind="uv-tool", params={})
    warning = pi.run_postinstall(
        "graphify-register", method, lambda cmd: calls.append(cmd), _tools()
    )
    assert warning is None
    assert calls == []


def test_graphify_hook_invokes_the_resolved_absolute_binary_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)
    calls: list[list[str]] = []
    method = Method(kind="uv-tool", params={})
    pi.run_postinstall("graphify-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "graphify")
    assert calls == [[expected_bin, "claude", "install"]]

    calls.clear()
    custom_method = Method(kind="uv-tool", params={"bin_dir": "/custom/dir"})
    pi.run_postinstall("graphify-register", custom_method, lambda cmd: calls.append(cmd), _tools())
    assert calls[0][0] == "/custom/dir/graphify"


def test_graphify_hook_maps_cursor_agent_to_cursor_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def only_cursor_agent(tool: Tool) -> bool:
        return tool.id == "cursor-agent"

    monkeypatch.setattr(pi, "is_installed", only_cursor_agent)
    calls: list[list[str]] = []
    method = Method(kind="uv-tool", params={})
    pi.run_postinstall("graphify-register", method, lambda cmd: calls.append(cmd), _tools())
    expected_bin = str(Path.home() / ".local" / "bin" / "graphify")
    assert calls == [[expected_bin, "cursor", "install"]]


def test_graphify_hook_returns_warning_string_on_command_error_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _only_claude_installed)

    def failing_runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    method = Method(kind="uv-tool", params={})
    warning = pi.run_postinstall("graphify-register", method, failing_runner, _tools())
    assert warning is not None
    assert "claude" in warning


def test_graphify_hook_continues_past_a_command_error_and_captures_partial_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pi, "is_installed", _all_installed)

    def failing_on_codex(cmd: list[str]) -> None:
        if "codex" in cmd:
            raise CommandError(cmd, 1)

    method = Method(kind="uv-tool", params={})
    warning = pi.run_postinstall("graphify-register", method, failing_on_codex, _tools())
    assert warning is not None
    assert "codex" in warning


def test_graphify_hook_never_invokes_the_same_host_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pi, "is_installed", _all_installed)
    calls: list[list[str]] = []
    method = Method(kind="uv-tool", params={})
    pi.run_postinstall("graphify-register", method, lambda cmd: calls.append(cmd), _tools())
    assert len(calls) == len({tuple(c) for c in calls})


@pytest.mark.parametrize("present_subset", _ALL_SUBSETS, ids=lambda s: ",".join(s) or "none")
def test_graphify_hook_never_composes_a_multi_host_csv_call(
    monkeypatch: pytest.MonkeyPatch, present_subset: tuple[str, ...]
) -> None:
    """Pitfall 4: never a CSV, one `graphify <host> install` invocation per
    present host -- a copy-paste from codegraph's single-CSV-call shape would
    be wrong here."""
    present = set(present_subset)

    def fake_is_installed(tool: Tool) -> bool:
        return tool.id in present

    monkeypatch.setattr(pi, "is_installed", fake_is_installed)
    calls: list[list[str]] = []
    method = Method(kind="uv-tool", params={})
    warning = pi.run_postinstall(
        "graphify-register", method, lambda cmd: calls.append(cmd), _tools()
    )
    assert warning is None
    expected_bin = str(Path.home() / ".local" / "bin" / "graphify")
    declared_order = ("claude", "opencode", "codex", "cursor-agent")
    expected_calls = [
        [expected_bin, _EXPECTED_TARGET_FOR[host_id], "install"]
        for host_id in declared_order
        if host_id in present
    ]
    assert calls == expected_calls
    for cmd in calls:
        assert len(cmd) == 3
        assert "," not in cmd[1]
