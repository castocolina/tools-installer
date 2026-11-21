from dataclasses import replace
from functools import partial
from io import StringIO
from pathlib import Path
from typing import cast

import pytest
from rich.console import Console

from installer import executors, render
from installer.engine import InstallOutcome, install_tool
from installer.enums import InstallStatus
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError
from installer.session import Disposition, RunContext, build_plan, execute_plan
from installer.update import UpdateTarget, perform_update
from installer.version_status import Health
from tests.state_doubles import plan_state

REGISTRY = Path("installer/registry.toml")
FEDORA = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
DEBIAN = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)


def catalog() -> dict[str, Tool]:
    return {tool.id: tool for tool in load_tools(REGISTRY)}


def test_aws_cli_entry_shape() -> None:
    tool = catalog()["aws-cli"]
    assert (tool.cmd, tool.tier, tool.audience, tool.requires) == ("aws", "user", "both", ())
    script, brew = tool.methods
    assert (script.kind, brew.kind) == ("script", "brew")
    assert script.params == {
        "url": "https://awscli.amazonaws.com/v2/install.sh",
        "shell": "bash",
        "bin_dir": "~/.local/bin",
        "prefer": True,
        "env": {"AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION": "false"},
        "paths": ["~/.local/share/aws-cli/", "~/.local/bin/aws", "~/.local/bin/aws_completer"],
        "update": ["aws", "update"],
    }
    assert brew.params["formula"] == "awscli"
    assert all("--system" not in str(method.params) for method in tool.methods)


def test_aws_cli_never_names_the_aws_folder() -> None:
    tools = catalog()
    assert tools["aws-cli"].config_paths == ()
    for tool in tools.values():
        paths = list(tool.config_paths)
        for method in tool.methods:
            raw = method.params.get("paths", [])
            assert isinstance(raw, list)
            paths.extend(str(path) for path in cast(list[object], raw))
        assert all(path != "~/.aws" and not path.startswith("~/.aws/") for path in paths)


def test_aws_cli_prefers_the_script_before_brew() -> None:
    tool = catalog()["aws-cli"]
    platforms = [
        Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        FEDORA,
        replace(FEDORA, immutable=True),
    ]
    for platform in platforms:
        assert [m.kind for m in resolve_methods(tool, platform)] == ["script", "brew"]
        script = replace(
            tool.methods[0],
            params={k: v for k, v in tool.methods[0].params.items() if k != "prefer"},
        )
        assert [
            m.kind
            for m in resolve_methods(replace(tool, methods=(script, tool.methods[1])), platform)
        ] == ["brew", "script"]
    assert [m.kind for m in resolve_methods(tool, DEBIAN)] == ["script"]


def test_the_script_environment_pins_gpg_on() -> None:
    calls: list[list[str]] = []
    executors.execute(catalog()["aws-cli"].methods[0], calls.append)
    assert calls[0][:2] == ["sh", "-c"]
    script = calls[0][2]
    assert "AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION=false bash" in script
    assert "--system" not in script


class FailingScript:
    def __init__(
        self, detail: str = "gpg not found; cannot verify the installer signature"
    ) -> None:
        self.calls: list[list[str]] = []
        self.errors: list[CommandError] = []
        self.detail = detail

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        if cmd[:2] == ["sh", "-c"]:
            error = CommandError(cmd, 1, detail=self.detail)
            self.errors.append(error)
            raise error


def test_a_failing_script_falls_through_to_brew(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A runner image may already carry a real `aws`; the engine's smoke must not find it.
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    tool = catalog()["aws-cli"]
    runner = FailingScript()
    outcome = install_tool(tool, FEDORA, runner, present=lambda _tool: False)
    assert outcome.status is InstallStatus.INSTALLED and outcome.method_kind == "brew"
    assert runner.calls[0][:2] == ["sh", "-c"]
    assert runner.calls[1] == ["brew", "install", "awscli"]
    runner = FailingScript()
    outcome = install_tool(tool, DEBIAN, runner, present=lambda _tool: False)
    assert outcome.status is InstallStatus.FAILED
    assert outcome.errors[-1] is runner.errors[-1]
    assert "gpg not found" in str(outcome.errors[-1])


def test_the_brew_fallback_is_reachable_without_unzip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    tools = catalog()
    aws, unzip = tools["aws-cli"], tools["unzip"]
    selected = [unzip, aws]
    states = {t.id: plan_state(t, platform=FEDORA, health=Health.MISSING) for t in selected}
    rows = build_plan([aws.id], selected, states.get, FEDORA, reinstall=frozenset())
    assert [(r.tool_id, r.disposition) for r in rows] == [("aws-cli", Disposition.INSTALL)]
    runner = FailingScript()
    ctx = RunContext(
        {t.id: t for t in selected},
        FEDORA,
        runner,
        lambda _repo: "v1",
        partial(install_tool, present=lambda _tool: False),
    )
    outcome = execute_plan(rows, ctx)[0]
    assert outcome.result == "done" and outcome.install is not None
    assert outcome.install.method_kind == "brew"
    assert runner.calls[0][:2] == ["sh", "-c"]
    assert runner.calls[1:] == [["brew", "install", "awscli"]]

    dependent = replace(aws, requires=("unzip",))
    selected = [unzip, dependent]
    rows = build_plan([aws.id], selected, states.get, FEDORA, reinstall=frozenset())
    assert [(r.tool_id, r.disposition) for r in rows] == [
        ("unzip", Disposition.INSTALL),
        ("aws-cli", Disposition.INSTALL),
    ]
    calls: list[list[str]] = []

    def fail_unzip(tool: Tool, *_args: object, **_kwargs: object) -> InstallOutcome:
        assert tool.id == "unzip"
        return InstallOutcome(tool.id, InstallStatus.FAILED)

    ctx = RunContext(
        {t.id: t for t in selected}, FEDORA, calls.append, lambda _repo: "v1", fail_unzip
    )
    outcomes = execute_plan(rows, ctx)
    assert outcomes[1].result == "dependency_failed"
    assert (
        outcomes[1].install is not None
        and outcomes[1].install.status is InstallStatus.DEPENDENCY_FAILED
    )
    assert calls == []

    for detail in ("gpg not found; cannot verify the installer signature", ""):
        states = {aws.id: plan_state(aws, platform=DEBIAN, health=Health.MISSING)}
        rows = build_plan([aws.id], [aws], states.get, DEBIAN, reinstall=frozenset())
        runner = FailingScript(detail)
        ctx = RunContext(
            {aws.id: aws},
            DEBIAN,
            runner,
            lambda _repo: "v1",
            partial(install_tool, present=lambda _tool: False),
        )
        outcome = execute_plan(rows, ctx)[0]
        assert outcome.result == "failed" and outcome.install is not None
        error = outcome.install.errors[-1]
        assert error is runner.errors[-1] and isinstance(error, CommandError)
        assert error.cmd[:2] == ["sh", "-c"] and error.returncode == 1
        assert render.outcome_detail_text(outcome).startswith("command failed (1): sh -c")
        output = StringIO()
        render.render_failure_details([outcome.install], Console(file=output, width=200))
        assert "command failed (1): sh -c" in output.getvalue()
        assert ("gpg not found" in output.getvalue()) == bool(detail)


def test_the_update_runs_the_installers_own_aws(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    leaf = tmp_path / ".local/bin/aws"
    leaf.parent.mkdir(parents=True)
    leaf.write_text("binary")
    tool = catalog()["aws-cli"]
    method = tool.methods[0]
    state = plan_state(tool, method=method)
    calls: list[list[str]] = []
    outcome = perform_update(
        UpdateTarget(tool, state.ownership),
        platform=FEDORA,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1",
    )
    assert outcome.status == "updated"
    assert calls == [[str(leaf), "update"]]
