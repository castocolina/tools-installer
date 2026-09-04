from pathlib import Path

import pytest

from installer.model import Method, Tool
from installer.status import is_installed


def _tool(cmd: str) -> Tool:
    return Tool(
        id="t",
        name="t",
        category="c",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": "t"}),),
    )


def test_is_installed_true_when_cmd_on_path(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/jq" if cmd == "jq" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    assert is_installed(_tool("jq")) is True


def test_is_installed_false_when_cmd_absent(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    assert is_installed(_tool("jq")) is False


def _app_tool(app: str = "Demo.app") -> Tool:
    return Tool(
        id="d",
        name="d",
        category="editor",
        cmd="demo",
        methods=(Method(kind="app", params={"url": "https://example.test/a.zip", "app": app}),),
    )


def test_app_bundle_present_counts_as_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    (tmp_path / "Demo.app").mkdir()
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is True


def test_app_bundle_as_plain_file_is_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    (tmp_path / "Demo.app").touch()  # a file, not a bundle dir
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is False


def test_cask_app_bundle_present_counts_as_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    (tmp_path / "JetBrains Toolbox.app").mkdir()
    tool = Tool(
        id="jetbrains-toolbox",
        name="JetBrains Toolbox",
        category="editor",
        cmd="jetbrains-toolbox",
        methods=(
            Method(
                kind="cask",
                params={"cask": "jetbrains-toolbox", "app": "JetBrains Toolbox.app"},
            ),
        ),
    )
    assert is_installed(tool, app_roots=(tmp_path,)) is True


def test_app_tool_without_bundle_or_cmd_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    assert is_installed(_app_tool(), app_roots=(tmp_path,)) is False


def test_app_method_without_app_param_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    tool = Tool(
        id="d",
        name="d",
        category="editor",
        cmd="demo",
        methods=(Method(kind="app", params={"url": "https://example.test/a.zip"}),),
    )
    assert is_installed(tool, app_roots=(tmp_path,)) is False


def test_default_app_roots_include_user_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "Applications" / "Tools Installer Probe.app").mkdir(parents=True)
    assert is_installed(_app_tool("Tools Installer Probe.app")) is True


def test_cmd_on_path_still_wins_for_app_tools(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_found(cmd: str) -> str | None:
        return "/usr/local/bin/demo"

    monkeypatch.setattr(status.shutil, "which", which_found)
    assert is_installed(_app_tool()) is True


def _detect_path_tool(detect_path: str) -> Tool:
    return Tool(
        id="sdkman",
        name="SDKMAN",
        category="runtime",
        cmd="sdkman-init.sh",
        methods=(
            Method(
                kind="script",
                params={"url": "https://example.test/i.sh", "detect_path": detect_path},
            ),
        ),
    )


def test_detect_path_present_counts_as_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    marker = tmp_path / "sdkman-init.sh"
    marker.touch()  # a non-executable file — `which` could never find this
    assert is_installed(_detect_path_tool(str(marker))) is True


def test_detect_path_absent_is_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    missing = tmp_path / "sdkman-init.sh"
    assert is_installed(_detect_path_tool(str(missing))) is False
