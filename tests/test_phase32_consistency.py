"""Pin phase 32 container evidence to the shipped catalog entries."""

import re
import tomllib
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from installer import bun_globals, postinstall
from installer.model import load_tools
from tests import e2e_aws_cli_driver, e2e_playwright_mcp_driver

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _comments(tool_id: str) -> list[str]:
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    index = lines.index(f'id = "{tool_id}"')
    assert lines[index - 1] == "[[tool]]"
    comments: list[str] = []
    for line in reversed(lines[: index - 1]):
        if not line.startswith("#"):
            break
        comments.append(line)
    return list(reversed(comments))


def _paragraph(tool_id: str, start: str, block_limit: int) -> str:
    comments = _comments(tool_id)
    assert len(comments) <= block_limit
    script = start.split("scripts/", 1)[1]
    starts = [i for i, line in enumerate(comments) if f"scripts/{script}" in line]
    assert len(starts) == 1
    paragraph = comments[starts[0] :]
    assert paragraph[0].startswith(start)
    assert len(paragraph) <= 8
    return "\n".join(paragraph)


def test_the_aws_entry_records_the_container_proof() -> None:
    text = _paragraph(
        "aws-cli", "# Verified 2026-11-21: scripts/container-e2e-verify.sh aws-cli", 30
    )
    for phrase in (
        "TRACER_AWS_INSTALL_OK",
        "TRACER_AWS_RERUN_OK",
        "TRACER_AWS_REMOVE_OK",
        "TRACER_AWS_NOGPG_OK",
        "gpg",
        "byte-identical",
        "~/.aws",
        "debian",
        "Fedora",
    ):
        assert phrase in text


def test_the_playwright_entry_records_the_container_proof() -> None:
    text = _paragraph(
        "playwright-mcp",
        "# Verified 2026-11-21: scripts/container-e2e-verify.sh playwright-mcp",
        40,
    )
    for phrase in (
        "TRACER_PLAYWRIGHT_INSTALL_OK",
        "TRACER_PLAYWRIGHT_REGISTER_OK",
        "TRACER_PLAYWRIGHT_CONSENT_OK",
        "TRACER_PLAYWRIGHT_LAUNCH_OK",
        "TRACER_PLAYWRIGHT_REMOVE_OK",
        "0.0.85",
        "Chromium",
        "byte-identical",
        "Fedora",
    ):
        assert phrase in text


def test_the_bruno_entry_reports_the_verified_container_result() -> None:
    text = _paragraph(
        "bruno", "# Container check not verified: scripts/container-e2e-verify.sh bruno", 40
    )
    for phrase in ("no digest-verified record", "default"):
        assert phrase in text
    for phrase in (
        "PASS",
        "ran in a container",
        "proven",
        "TRACER_BRUNO_INSTALL_OK",
        "TRACER_BRUNO_RUN_OK",
    ):
        assert phrase not in text


def test_the_bruno_smoke_argv_matches_the_recorded_result() -> None:
    bruno = next(tool for tool in load_tools(REGISTRY) if tool.id == "bruno")
    tarballs = [method for method in bruno.methods if method.kind == "tarball"]
    assert {method.arch for method in tarballs} == {("amd64",), ("arm64",)}
    assert all("smoke_argv" not in method.params for method in tarballs)
    casks = [method for method in bruno.methods if method.kind == "cask"]
    assert len(casks) == 1
    assert "smoke_argv" not in casks[0].params


def test_the_five_entries_exist_with_their_tiers_and_methods() -> None:
    tools = {tool.id: tool for tool in load_tools(REGISTRY)}
    xcode = tools["xcode-clt"]
    assert xcode.tier == "system" and len(xcode.methods) == 1
    method = xcode.methods[0]
    assert method.kind == "script" and method.os == ("macos",)
    assert method.params.get("handoff") == "xcode-clt"
    assert not {"url", "install", "update", "remove", "paths"} & method.params.keys()
    aws = tools["aws-cli"]
    assert aws.tier == "user" and [m.kind for m in aws.methods] == ["script", "brew"]
    assert aws.methods[0].params.get("prefer") is True
    bruno = tools["bruno"]
    assert bruno.tier == "user"
    assert sorted(m.kind for m in bruno.methods) == ["cask", "tarball", "tarball"]
    gh = tools["gh-stack"]
    assert gh.tier == "user" and len(gh.methods) == 1
    assert gh.methods[0].kind == "script" and "install" in gh.methods[0].params
    playwright = tools["playwright-mcp"]
    assert playwright.tier == "ai" and [m.kind for m in playwright.methods] == ["bun"]
    assert playwright.postinstall == "playwright-mcp-register"


def test_no_phase_32_entry_carries_an_elevation_head_or_a_privileged_command_text() -> None:
    def strings(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [s for item in cast(list[object], value) for s in strings(item)]
        if isinstance(value, dict):
            return [s for item in cast(dict[str, object], value).values() for s in strings(item)]
        return []

    ids = {"xcode-clt", "aws-cli", "bruno", "gh-stack", "playwright-mcp"}
    for tool in load_tools(REGISTRY):
        if tool.id in ids:
            for method in tool.methods:
                for value in strings(method.params):
                    assert Path(value).name not in {"sudo", "pkexec", "doas"}
                    assert not value.startswith(("softwareupdate", "xcode-select"))


def test_the_playwright_pin_has_one_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = next(t for t in load_tools(REGISTRY) if t.id == "playwright-mcp")
    method = tool.methods[0]
    versions = cast(dict[str, str], method.params["versions"])
    pin = e2e_playwright_mcp_driver.PIN
    assert versions["@playwright/mcp"] == pin
    bunx = tmp_path / "bunx"
    bunx.touch()
    bunx.chmod(0o755)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(bun_globals, "resolve_bun", lambda: str(tmp_path / "bun"))
    done, warning = postinstall.POSTINSTALL_HOOKS["playwright-mcp-register"].register(
        method, lambda _argv: None, ("codex",)
    )
    assert done == ("codex",) and warning is None
    config = tomllib.loads((tmp_path / ".codex" / "config.toml").read_text())
    assert config["mcp_servers"]["playwright"]["args"] == [f"@playwright/mcp@{pin}"]


def test_every_generic_skip_id_has_its_own_verb_or_is_herdr_app() -> None:
    script = (REGISTRY.parent.parent / "scripts" / "container-e2e-verify.sh").read_text()
    lines = re.findall(r"^GENERIC_SKIP_TOOLS=(.*)$", script, re.MULTILINE)
    assert len(lines) == 1
    ids = {tool.id for tool in load_tools(REGISTRY)}
    for tool_id in lines[0].split(","):
        if tool_id == "herdr-app":
            continue
        assert tool_id in ids
        function = "cmd_" + tool_id.replace("-", "_")
        assert re.search(rf"^{function}\(\) \{{", script, re.MULTILINE)
        assert f'{tool_id}) {function} "$@" ;;' in script


def test_every_phase_32_entry_has_a_dated_verified_comment_block() -> None:
    data = tomllib.loads(REGISTRY.read_text())
    rows = {row["id"]: row for row in data["tool"]}
    for tool_id in ("xcode-clt", "aws-cli", "bruno", "gh-stack", "playwright-mcp"):
        comments = _comments(tool_id)
        assert comments
        match = re.match(r"# Verified (2026-\d\d-\d\d):", comments[0])
        assert match
        assert rows[tool_id]["verified"] >= date.fromisoformat(match[1])


def test_the_consent_hosts_are_targets_of_the_hook() -> None:
    pair = postinstall.POSTINSTALL_HOOKS["playwright-mcp-register"]
    assert pair.targets is not None
    assert pair.consent == {"claude"} and pair.consent <= pair.targets.keys()


def test_the_evidence_paragraphs_name_only_defined_verdicts() -> None:
    defined = {
        "aws-cli": e2e_aws_cli_driver.EXPECTED_LINES,
        "playwright-mcp": e2e_playwright_mcp_driver.EXPECTED_LINES,
    }
    for tool_id, expected in defined.items():
        tokens = re.findall(r"TRACER_(?:AWS|PLAYWRIGHT)_[A-Z_]+", "\n".join(_comments(tool_id)))
        assert tokens
        assert all(
            any(line.startswith(token) for lines in expected.values() for line in lines)
            for token in tokens
        )
    bruno = re.findall(r"TRACER_BRUNO_[A-Z_]+", "\n".join(_comments("bruno")))
    assert set(bruno) <= {
        "TRACER_BRUNO_INSTALL_OK",
        "TRACER_BRUNO_RUN_OK",
        "TRACER_BRUNO_RUN_UNPROVEN",
        "TRACER_BRUNO_REMOVE_OK",
    }


def test_xcode_clt_and_gh_stack_make_no_container_claim() -> None:
    for tool_id in ("xcode-clt", "gh-stack"):
        assert "container-e2e-verify" not in "\n".join(_comments(tool_id))
