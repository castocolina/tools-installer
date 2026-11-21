import json
import tomllib
from pathlib import Path

import pytest

from installer import bun_globals, executors, postinstall, receipts, update, version_status
from installer.model import Tool, load_tools
from installer.ownership import ManagerOwnership

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
HOOK = "playwright-mcp-register"


def shipped_tool() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "playwright-mcp")


def test_playwright_mcp_entry_shape() -> None:
    tool = shipped_tool()
    assert (tool.tier, tool.audience, tool.category, tool.cmd) == (
        "ai",
        "ai",
        "ai",
        "playwright-mcp",
    )
    assert tool.requires == ("bun",)
    assert tool.postinstall == HOOK
    assert len(tool.methods) == 1
    method = tool.methods[0]
    assert method.kind == "bun"
    assert method.params == {
        "npm_pkg": "@playwright/mcp",
        "versions": {"@playwright/mcp": "0.0.85"},
        "min_node": "18.0.0",
    }
    assert "latest" not in str(method.params)


def test_the_server_pin_is_the_methods_pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    method = shipped_tool().methods[0]
    bun = tmp_path / "bun"
    bunx = tmp_path / "bunx"
    bunx.touch()
    bunx.chmod(0o755)
    monkeypatch.setattr(bun_globals, "resolve_bun", lambda: str(bun))
    monkeypatch.setattr(executors, "resolve_bun", lambda: str(bun))

    def probe(_argv: list[str]) -> str:
        return "v22.0.0"

    monkeypatch.setattr(executors, "probe_version", probe)
    calls: list[list[str]] = []
    executors.execute(method, calls.append)
    assert calls == [[str(bun), "add", "-g", "@playwright/mcp@0.0.85"]]
    done, warning = postinstall.POSTINSTALL_HOOKS[HOOK].register(method, calls.append, ("codex",))
    assert done == ("codex",) and warning is None
    config = tomllib.loads((Path.home() / ".codex" / "config.toml").read_text())
    assert config["mcp_servers"]["playwright"]["command"] == str(bunx)
    assert config["mcp_servers"]["playwright"]["args"] == ["@playwright/mcp@0.0.85"]


def test_a_kept_entry_reads_settled_and_a_missing_one_reads_pending() -> None:
    tool = shipped_tool()
    receipt = receipts.Receipt(
        tool=tool.id,
        at="2026-11-21T00:00:00+00:00",
        method=receipts.ReceiptMethod(kind="bun", key="test"),
        package=None,
        artifacts=(),
        smoke=None,
        hooks={HOOK: ()},
    )
    fact_name = "_hook_fact"
    field_name = "misconfigured"
    fact = getattr(version_status, fact_name)

    def probe(_argv: list[str]) -> str | None:
        return None

    def read_fact() -> object:
        return fact(tool, receipt, frozenset({"codex", "pi"}), None, "/bin/playwright-mcp", probe)

    pending = read_fact()
    assert getattr(pending, field_name) == ("playwright-mcp is not registered for codex",)
    path = Path.home() / ".codex" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text('[mcp_servers.playwright]\ncommand = "mine"\n')
    assert getattr(read_fact(), field_name) == ()


def test_update_is_refused_by_design_for_the_exact_pin(tmp_path: Path) -> None:
    tool = shipped_tool()
    manifest = Path.home() / ".bun" / "install" / "global" / "package.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"dependencies": {"@playwright/mcp": "0.0.85"}}))
    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner="bun",
        method=tool.methods[0],
        package="@playwright/mcp",
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate="bun",
        active_path=tmp_path / "playwright-mcp",
        unknown_reason=None,
    )
    result = update.update_refusal(tool, ownership)
    assert result is not None and result.status == "unsupported"
    assert "0.0.85" in result.detail and "change the pin" in result.detail
