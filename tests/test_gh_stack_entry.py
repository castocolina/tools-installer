from pathlib import Path

import pytest

from installer import engine, receipts, status
from installer.enums import InstallStatus
from installer.model import Tool, load_tools
from installer.ownership import ManagerOwnership
from installer.platform import Platform
from installer.uninstall import removal_plan, remove_proven
from installer.update import UpdateTarget, perform_update

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
INSTALL = ["gh", "extension", "install", "https://github.com/github/gh-stack"]
UPGRADE = ["gh", "extension", "upgrade", "stack"]
PLATFORM = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)


def stack() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "gh-stack")


def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    return tmp_path / ".local/share/gh/extensions/gh-stack/manifest.yml"


def test_gh_stack_argv_strings_are_exact() -> None:
    tool = stack()
    assert (tool.requires, tool.cmd, tool.tier, tool.audience, tool.category) == (
        ("gh",),
        "gh-stack-extension",
        "user",
        "both",
        "git",
    )
    assert not tool.config_paths
    assert len(tool.methods) == 1
    method = tool.methods[0]
    assert method.kind == "script"
    assert method.params == {
        "install": INSTALL,
        "update": UPGRADE,
        "detect_path": "~/.local/share/gh/extensions/gh-stack/manifest.yml",
        "paths": ["~/.local/share/gh/extensions/gh-stack/"],
    }
    for token in [
        *INSTALL,
        *UPGRADE,
        "~/.local/share/gh/extensions/gh-stack/manifest.yml",
        "~/.local/share/gh/extensions/gh-stack/",
    ]:
        assert all(word not in token.lower() for word in ("auth", "login", "sudo"))


def test_an_unrelated_gh_stack_executable_on_path_does_not_read_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = sandbox(tmp_path, monkeypatch)
    binary = tmp_path / "bin/gh-stack"
    binary.parent.mkdir()
    binary.touch(mode=0o755)
    tool = stack()
    assert not status.is_installed(tool)
    calls: list[list[str]] = []
    outcome = engine.install_tool(tool, PLATFORM, runner=calls.append)
    assert outcome.status == InstallStatus.INSTALLED
    assert calls == [INSTALL]
    manifest.parent.mkdir(parents=True)
    manifest.touch()
    assert status.is_installed(tool)


def test_an_executable_named_like_the_probe_reads_present_the_recorded_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox(tmp_path, monkeypatch)
    binary = tmp_path / "bin/gh-stack-extension"
    binary.parent.mkdir()
    binary.touch(mode=0o755)
    # Recorded probe-name limit: PATH is checked before the manifest.
    assert status.is_installed(stack())


def test_gh_stack_install_runs_the_one_argv_and_a_second_run_is_a_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = sandbox(tmp_path, monkeypatch)
    sibling = manifest.parent.parent / "gh-stacks/manifest.yml"
    sibling.parent.mkdir(parents=True)
    sibling.touch()
    tool = stack()
    assert not status.is_installed(tool)
    calls: list[list[str]] = []
    assert (
        engine.install_tool(tool, PLATFORM, runner=calls.append).status == InstallStatus.INSTALLED
    )
    assert calls == [INSTALL]
    manifest.parent.mkdir()
    manifest.touch()
    calls.clear()
    assert (
        engine.install_tool(tool, PLATFORM, runner=calls.append).status
        == InstallStatus.ALREADY_INSTALLED
    )
    assert calls == []


def test_gh_stack_reads_absent_without_a_manifest_and_never_consults_gh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox(tmp_path, monkeypatch)
    probes: list[str] = []

    def lookup(name: str) -> None:
        probes.append(name)
        return None

    assert not status.is_installed(stack(), which=lookup)
    assert probes == ["gh-stack-extension"]


def test_gh_stack_update_runs_the_exact_argv_through_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox(tmp_path, monkeypatch)
    tool = stack()
    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner="installer",
        method=tool.methods[0],
        package=None,
        current_version=None,
        confidence="by-elimination",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    calls: list[list[str]] = []
    outcome = perform_update(
        UpdateTarget(tool=tool, ownership=ownership),
        platform=PLATFORM,
        runner=calls.append,
        resolve_tag=lambda _: "",
    )
    assert outcome.status == "updated"
    assert calls == [UPGRADE]


def test_gh_stack_removal_deletes_only_the_proven_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = sandbox(tmp_path, monkeypatch)
    manifest.parent.mkdir(parents=True)
    manifest.write_text("extension")
    sibling = manifest.parent.parent / "other"
    sibling.mkdir()
    config = tmp_path / ".config/gh"
    config.mkdir(parents=True)
    tool = stack()
    receipt = receipts.record(
        tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset()
    )
    assert receipt is not None
    plan = removal_plan(tool, tmp_path / "bin")
    assert plan.argv == ()
    assert plan.removable == (manifest.parent,)
    assert plan.config == ()
    removed, refused = remove_proven([tool], list(plan.removable), tmp_path / "bin")
    assert removed == (manifest.parent,) and not refused
    assert not manifest.parent.exists()
    assert sibling.is_dir() and config.is_dir()
