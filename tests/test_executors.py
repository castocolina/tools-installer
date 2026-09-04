from pathlib import Path

import pytest

from installer.executors import EXECUTORS, ExecutorError, execute
from installer.model import Method
from installer.run import Runner


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def test_dnf_executor_builds_sudo_install():
    calls, runner = _record()
    execute(Method(kind="dnf", params={"package": "jq"}), runner)
    assert calls == [["sudo", "dnf", "install", "-y", "jq"]]


def test_apt_executor_builds_sudo_install():
    calls, runner = _record()
    execute(Method(kind="apt", params={"package": "jq"}), runner)
    assert calls == [["sudo", "apt-get", "install", "-y", "jq"]]


def test_pacman_executor_builds_sudo_install():
    calls, runner = _record()
    execute(Method(kind="pacman", params={"package": "jq"}), runner)
    assert calls == [["sudo", "pacman", "-S", "--noconfirm", "--needed", "jq"]]


def test_brew_executor_builds_install():
    calls, runner = _record()
    execute(Method(kind="brew", params={"formula": "jq"}), runner)
    assert calls == [["brew", "install", "jq"]]


def test_script_executor_pipes_curl_into_shell():
    calls, runner = _record()
    execute(
        Method(kind="script", params={"url": "https://astral.sh/uv/install.sh", "shell": "sh"}),
        runner,
    )
    assert calls == [["sh", "-c", "curl -fsSL -- https://astral.sh/uv/install.sh | sh"]]


def test_script_executor_defaults_shell_to_sh():
    calls, runner = _record()
    execute(Method(kind="script", params={"url": "https://example.com/i.sh"}), runner)
    assert calls == [["sh", "-c", "curl -fsSL -- https://example.com/i.sh | sh"]]


def test_script_executor_quotes_url_with_special_chars():
    calls, runner = _record()
    execute(Method(kind="script", params={"url": "https://x.com/i.sh?a=b&c=d"}), runner)
    assert calls == [["sh", "-c", "curl -fsSL -- 'https://x.com/i.sh?a=b&c=d' | sh"]]


def test_missing_required_param_raises():
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="package"):
        execute(Method(kind="dnf", params={}), runner)
    assert calls == []


def test_unsupported_kind_raises():
    _calls, runner = _record()
    with pytest.raises(ExecutorError, match="github_release"):
        execute(Method(kind="github_release", params={"repo": "x/y"}), runner)


def test_every_command_kind_has_an_executor():
    assert set(EXECUTORS) == {"script", "node", "sdkman", "dnf", "apt", "pacman", "brew", "cask"}


def test_script_passes_env_assignments_to_the_shell() -> None:
    # The env attaches to the shell on the RIGHT of the pipe; a left-of-pipe
    # assignment would set curl's env, not the installer's.
    calls, runner = _record()
    method = Method(
        kind="script",
        params={
            "url": "https://example.test/install.sh",
            "shell": "bash",
            "env": {"NONINTERACTIVE": "1"},
        },
    )
    execute(method, runner)
    assert calls == [
        ["sh", "-c", "curl -fsSL -- https://example.test/install.sh | NONINTERACTIVE=1 bash"]
    ]


def test_script_without_env_is_unchanged() -> None:
    calls, runner = _record()
    method = Method(kind="script", params={"url": "https://example.test/i.sh"})
    execute(method, runner)
    assert calls == [["sh", "-c", "curl -fsSL -- https://example.test/i.sh | sh"]]


def test_cask_executor_installs_into_user_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    execute(Method(kind="cask", params={"cask": "sublime-text"}), runner)
    assert calls == [
        ["brew", "install", "--cask", f"--appdir={tmp_path / 'Applications'}", "sublime-text"]
    ]


def test_cask_missing_param_raises():
    calls, runner = _record()
    with pytest.raises(ExecutorError, match="cask"):
        execute(Method(kind="cask", params={}), runner)
    assert calls == []


def test_node_runs_pnpm_add_global_never_bare_npm():
    calls: list[list[str]] = []
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    execute(method, calls.append)
    assert calls == [["pnpm", "add", "-g", "@mermaid-js/mermaid-cli"]]
    assert all(call[0] != "npm" for call in calls)


def test_node_without_npm_pkg_raises_executor_error():
    with pytest.raises(ExecutorError, match="npm_pkg"):
        execute(Method(kind="node", params={}), lambda _cmd: None)


def test_sdkman_sources_init_script_then_installs_candidate():
    calls, runner = _record()
    execute(Method(kind="sdkman", params={"candidate": "java"}), runner)
    assert calls == [["bash", "-c", '. "$HOME/.sdkman/bin/sdkman-init.sh" && sdk install java']]


def test_sdkman_appends_version_when_given():
    calls, runner = _record()
    execute(
        Method(kind="sdkman", params={"candidate": "java", "version": "21.0.4-tem"}),
        runner,
    )
    assert calls == [
        [
            "bash",
            "-c",
            '. "$HOME/.sdkman/bin/sdkman-init.sh" && sdk install java 21.0.4-tem',
        ]
    ]


def test_sdkman_without_candidate_raises_executor_error():
    with pytest.raises(ExecutorError, match="candidate"):
        execute(Method(kind="sdkman", params={}), lambda _cmd: None)
