import ast
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from installer.enums import UninstallState
from installer.model import Tool, load_tools
from installer.ownership import resolve_ownership
from installer.platform import Platform
from installer.resolve import resolve_methods, unavailable_reason
from installer.session import Disposition, PlanRow, RunContext, build_plan, execute_plan
from installer.status import is_installed
from installer.uninstall import removal_plan
from installer.update import UpdateTarget, perform_update
from installer.version_status import Health, uninstall_group
from tests.state_doubles import MACOS, RunRecorder, empty_inventory, plan_state

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "installer" / "registry.toml"


def clt() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "xcode-clt")


def local_clt(path: Path) -> Tool:
    tool = clt()
    method = tool.methods[0]
    return replace(
        tool, methods=(replace(method, params={**method.params, "detect_path": str(path)}),)
    )


def test_xcode_clt_entry_shape() -> None:
    tool = clt()
    assert (tool.tier, tool.audience, tool.cmd) == ("system", "both", "xcode-clt")
    assert not tool.requires and not tool.config_paths
    assert len(tool.methods) == 1
    method = tool.methods[0]
    assert (method.kind, method.os) == ("script", ("macos",))
    assert method.params == {
        "detect_path": "/Library/Developer/CommandLineTools/usr/bin/git",
        "writable_prefix": "/Library/Developer/CommandLineTools",
        "handoff": "xcode-clt",
    }


def test_a_missing_clt_plans_a_manual_row_with_the_exact_command(tmp_path: Path) -> None:
    marker = tmp_path / "clt" / "git"
    tool = local_clt(marker)
    recorder = RunRecorder()

    def row(present: bool, others: bool = False) -> PlanRow:
        state = plan_state(tool, health=Health.OK if present else Health.MISSING, present=present)
        companions = [t for t in load_tools(REGISTRY) if t.id in ("git", "uv")] if others else []
        states = {tool.id: state, **{t.id: plan_state(t) for t in companions}}
        rows = build_plan(
            list(states), [tool, *companions], states.get, MACOS, reinstall=frozenset()
        )
        return next(r for r in rows if r.tool_id == tool.id)

    assert not is_installed(tool, which=lambda _: None)
    missing = row(False)
    assert missing == row(False, others=True)
    assert missing.disposition is Disposition.MANUAL
    assert missing.manual_command == "xcode-select --install"
    context = RunContext(
        catalog={tool.id: tool},
        platform=MACOS,
        runner=recorder.runner,
        resolve_tag=lambda _: "",
        install=recorder.install,
    )
    assert [outcome.result for outcome in execute_plan([missing], context)] == ["manual"]
    assert recorder.argv == [] and recorder.installs == []
    marker.parent.mkdir()
    marker.touch()
    assert is_installed(tool, which=lambda _: None)
    present = row(True)
    assert present == row(True, others=True)
    assert present.disposition is Disposition.SKIP
    assert present.manual_command is None


@pytest.mark.parametrize("os", ["fedora", "debian"])
def test_a_linux_host_sees_the_row_unavailable(os: str) -> None:
    tool = clt()
    platform = Platform(os=os, arch="amd64", immutable=False, has_brew=False)
    assert resolve_methods(tool, platform) == []
    reason = unavailable_reason(tool, platform)
    assert reason is not None and reason.short == f"{os} not supported"
    state = plan_state(tool, platform=platform, health=Health.UNAVAILABLE)
    row = build_plan([tool.id], [tool], {tool.id: state}.get, platform, reinstall=frozenset())[0]
    assert row.manual_command is None


def test_update_is_refused_for_a_handoff_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "")
    marker = tmp_path / "git"
    marker.touch()
    tool = local_clt(marker)
    ownership = resolve_ownership(
        tool,
        platform=MACOS,
        inventory=empty_inventory(),
        artifacts=[],
        managed_bin_dir=tmp_path / "bin",
        which=lambda _: None,
    )
    assert (ownership.owner, ownership.confidence) == ("installer", "by-elimination")
    calls: list[list[str]] = []
    outcome = perform_update(
        UpdateTarget(tool=tool, ownership=ownership),
        platform=MACOS,
        runner=calls.append,
        resolve_tag=lambda _: "",
    )
    assert outcome.status == "unsupported"
    assert outcome.owner == "installer"
    assert "Apple's Software Update" in outcome.detail
    assert calls == []


def test_uninstall_lists_the_entry_with_no_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = clt()
    plan = removal_plan(tool, tmp_path / "bin")
    assert not plan.removable and not plan.argv
    state = plan_state(tool, removable=plan)
    assert uninstall_group(state) is UninstallState.MANAGED
    assert not state.removable.argv


def test_xcode_select_is_never_spawned() -> None:
    files = sorted((ROOT / "installer").rglob("*.py")) + [ROOT / "setup.py"]
    assert ROOT / "installer" / "status.py" in files
    offenders: list[Path] = []
    handoff_files: list[Path] = []
    for path in files:
        text = path.read_text()
        tree = ast.parse(text, filename=str(path))
        if "xcode-select --install" in text:
            handoff_files.append(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and first.value in (
                    "xcode-select",
                    "softwareupdate",
                ):
                    offenders.append(path)
            if (
                path.is_relative_to(ROOT / "installer")
                and isinstance(node, ast.Constant)
                and node.value == "softwareupdate"
            ):
                assert path == ROOT / "installer" / "model.py"  # The registry denylist.
    assert offenders == []
    assert handoff_files == [ROOT / "installer" / "executors.py"]
    for tool in load_tools(REGISTRY):
        for method in tool.methods:
            for key in ("install", "update", "remove"):
                argv = method.params.get(key)
                if isinstance(argv, list):
                    tokens = cast(list[object], argv)
                    assert all(
                        isinstance(token, str)
                        and Path(token).name not in ("xcode-select", "softwareupdate")
                        for token in tokens
                    )
