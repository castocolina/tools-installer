from pathlib import Path

import pytest

from installer.model import Method, Tool, load_tools
from installer.status import is_default_shell, is_installed

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


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


def _uv_tool_tool() -> Tool:
    return Tool(
        id="graphify",
        name="Graphify",
        category="dev",
        cmd="graphify",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "graphifyy"}),),
    )


def test_uv_tool_status_is_detected_through_its_cli_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.status as status

    def which_graphify_only(cmd: str) -> str | None:
        return "/home/user/.local/bin/graphify" if cmd == "graphify" else None

    monkeypatch.setattr(status.shutil, "which", which_graphify_only)
    assert is_installed(_uv_tool_tool()) is True

    def which_none(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", which_none)
    assert is_installed(_uv_tool_tool()) is False


def test_gnu_bash_status_is_not_fooled_by_macos_system_bash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/bin/bash" if cmd == "bash" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    gnu_bash = next(tool for tool in load_tools(REGISTRY) if tool.id == "gnu-bash")
    swapped = tuple(
        Method(
            kind=method.kind,
            params={
                **method.params,
                "detect_path": str(tmp_path / Path(str(method.params["detect_path"])).name),
            },
            os=method.os,
            arch=method.arch,
        )
        for method in gnu_bash.methods
    )
    probed = Tool(
        id=gnu_bash.id,
        name=gnu_bash.name,
        category=gnu_bash.category,
        cmd=gnu_bash.cmd,
        methods=swapped,
        priority=gnu_bash.priority,
        audience=gnu_bash.audience,
        tier=gnu_bash.tier,
        desc=gnu_bash.desc,
    )
    assert is_installed(probed) is False


def _shell_tool(cmd: str) -> Tool:
    return Tool(
        id=cmd,
        name=cmd,
        category="shell",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": cmd}),),
    )


def test_is_default_shell_none_for_a_non_shell_category_tool() -> None:
    assert is_default_shell(_tool("zsh"), env={"SHELL": "/bin/zsh"}) is None


def test_is_default_shell_none_when_shell_env_is_unset() -> None:
    assert is_default_shell(_shell_tool("zsh"), env={}) is None


def test_is_default_shell_true_when_shell_env_basename_matches_cmd() -> None:
    assert is_default_shell(_shell_tool("zsh"), env={"SHELL": "/usr/bin/zsh"}) is True


def test_is_default_shell_false_when_shell_env_basename_differs() -> None:
    assert is_default_shell(_shell_tool("zsh"), env={"SHELL": "/bin/bash"}) is False
