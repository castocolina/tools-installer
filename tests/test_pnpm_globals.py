import os
import shlex
from pathlib import Path

import pytest

from installer.guards import REDIRECT_SENTINEL
from installer.model import Method, Tool, load_tools
from installer.pnpm_globals import (
    NodeGlobal,
    audit_node_globals,
    node_globals,
    reinstall_argv,
    reinstall_node_globals,
    reinstall_preview,
)
from installer.run import CommandError

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _tool(
    tool_id: str,
    *,
    cmd: str | None = None,
    methods: tuple[Method, ...] | None = None,
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="diagram",
        cmd=cmd or tool_id,
        methods=methods or (Method(kind="brew", params={"formula": tool_id}),),
    )


def _mmdc() -> Tool:
    return Tool(
        id="mmdc",
        name="Mermaid CLI",
        category="diagram",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )


def _plant_executable(directory: Path, name: str, body: str = "#!/bin/sh\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body)
    path.chmod(0o755)
    return path


def test_node_globals_empty() -> None:
    assert node_globals([]) == ()


def test_node_globals_ignores_brew_only() -> None:
    assert node_globals([_tool("rg")]) == ()


def test_node_globals_mmdc_like() -> None:
    assert node_globals([_mmdc()]) == (
        NodeGlobal(tool_id="mmdc", npm_pkg="@mermaid-js/mermaid-cli", cmd="mmdc"),
    )


def test_node_globals_skips_node_method_without_npm_pkg() -> None:
    tool = _tool(
        "broken",
        methods=(Method(kind="node", params={}),),
    )
    assert node_globals([tool]) == ()


def test_node_globals_preserves_order_one_entry_per_tool() -> None:
    first = Tool(
        id="a",
        name="a",
        category="diagram",
        cmd="a",
        methods=(
            Method(kind="node", params={"npm_pkg": "pkg-a"}),
            Method(kind="node", params={"npm_pkg": "pkg-a-second"}),
            Method(kind="brew", params={"formula": "a"}),
        ),
    )
    second = Tool(
        id="b",
        name="b",
        category="diagram",
        cmd="b",
        methods=(Method(kind="node", params={"npm_pkg": "pkg-b"}),),
    )
    entries = node_globals([_tool("rg"), first, second])
    assert [e.tool_id for e in entries] == ["a", "b"]
    assert entries[0].npm_pkg == "pkg-a"


def test_audit_lists_unresolved_commands() -> None:
    report = audit_node_globals([_mmdc()], which=lambda _n: None)
    assert report.missing == ("mmdc",)
    assert report.entries == node_globals([_mmdc()])


def test_audit_healthy_when_command_resolves() -> None:
    report = audit_node_globals([_mmdc()], which=lambda _n: "/x/mmdc")
    assert report.missing == ()


def test_reinstall_argv_one_invocation_absolute_pnpm() -> None:
    entries = node_globals([_mmdc()])
    assert reinstall_argv(entries, pnpm="/real/bin/pnpm") == [
        "/real/bin/pnpm",
        "add",
        "-g",
        "@mermaid-js/mermaid-cli",
    ]


def test_reinstall_argv_empty_raises() -> None:
    with pytest.raises(ValueError):
        reinstall_argv((), pnpm="/real/bin/pnpm")


def test_reinstall_node_globals_calls_runner_once() -> None:
    calls: list[list[str]] = []
    pkgs = reinstall_node_globals(
        [_mmdc()],
        runner=calls.append,
        resolve_pnpm=lambda: "/real/bin/pnpm",
    )
    assert pkgs == ("@mermaid-js/mermaid-cli",)
    assert calls == [reinstall_argv(node_globals([_mmdc()]), pnpm="/real/bin/pnpm")]
    assert all(call[0] != "pnpm" for call in calls)


def test_reinstall_node_globals_empty_is_noop() -> None:
    calls: list[list[str]] = []

    def never() -> str | None:
        raise AssertionError("resolver must not be called")

    assert reinstall_node_globals([], runner=calls.append, resolve_pnpm=never) == ()
    assert calls == []


def test_reinstall_node_globals_unresolvable_pnpm_raises_without_running() -> None:
    calls: list[list[str]] = []
    with pytest.raises(CommandError):
        reinstall_node_globals([_mmdc()], runner=calls.append, resolve_pnpm=lambda: None)
    assert calls == []


def test_reinstall_skips_wrapper_first_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    wrapper = _plant_executable(
        tmp_path / ".local" / "bin",
        "pnpm",
        body=f"#!/bin/sh\n{REDIRECT_SENTINEL}\n",
    )
    real = _plant_executable(tmp_path / "real", "pnpm")
    monkeypatch.setenv("PATH", f"{wrapper.parent}{os.pathsep}{real.parent}")
    calls: list[list[str]] = []
    reinstall_node_globals([_mmdc()], runner=calls.append)
    assert calls
    assert calls[0][0] == str(real)
    assert all(call[0] != "pnpm" for call in calls)


def test_reinstall_preview_empty_does_not_resolve() -> None:
    def never() -> str | None:
        raise AssertionError("resolver must not be called")

    text = reinstall_preview((), resolve_pnpm=never)
    assert "nothing pnpm-managed to reinstall" in text


def test_reinstall_preview_resolvable() -> None:
    entries = (NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),)
    text = reinstall_preview(entries, resolve_pnpm=lambda: "/real/bin/pnpm")
    assert text == shlex.join(reinstall_argv(entries, pnpm="/real/bin/pnpm"))


def test_reinstall_preview_unresolvable_is_message_not_argv() -> None:
    entries = (NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),)
    text = reinstall_preview(entries, resolve_pnpm=lambda: None)
    assert "pnpm" in text
    assert "add" not in text


def test_real_registry_residual_set_contains_mmdc() -> None:
    # Phase 5's REQ-mmdc-install-decision may move mmdc off pnpm add -g, at
    # which point this assertion — not the mechanism — changes.
    entries = node_globals(load_tools(REGISTRY))
    assert entries
    assert "mmdc" in {e.tool_id for e in entries}
