import os
import shlex
from pathlib import Path

import pytest

from installer.executors import EXECUTORS, ExecutorError, execute
from installer.guards import REDIRECT_SENTINEL
from installer.model import Method
from installer.run import Runner


def _record() -> tuple[list[list[str]], Runner]:
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    return calls, runner


def _script_of(calls: list[list[str]], shell: str = "sh") -> str:
    """The shell script of a single `sh -c` call, minus the exported PATH prefix.

    Every shell this installer opens exports a de-shimmed PATH first (WR-06);
    the prefix is asserted on its own in the tests below, so the pipeline
    assertions stay about the pipeline.
    """
    assert len(calls) == 1
    assert calls[0][:2] == [shell, "-c"]
    prefix, separator, rest = calls[0][2].partition("; export PATH; ")
    assert prefix.startswith("PATH=") and separator
    return rest


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
    assert _script_of(calls) == "curl -fsSL -- https://astral.sh/uv/install.sh | sh"


def test_script_executor_defaults_shell_to_sh():
    calls, runner = _record()
    execute(Method(kind="script", params={"url": "https://example.com/i.sh"}), runner)
    assert _script_of(calls) == "curl -fsSL -- https://example.com/i.sh | sh"


def test_script_executor_quotes_url_with_special_chars():
    calls, runner = _record()
    execute(Method(kind="script", params={"url": "https://x.com/i.sh?a=b&c=d"}), runner)
    assert _script_of(calls) == "curl -fsSL -- 'https://x.com/i.sh?a=b&c=d' | sh"


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
    assert (
        _script_of(calls) == "curl -fsSL -- https://example.test/install.sh | NONINTERACTIVE=1 bash"
    )


def test_script_without_env_is_unchanged() -> None:
    calls, runner = _record()
    method = Method(kind="script", params={"url": "https://example.test/i.sh"})
    execute(method, runner)
    assert _script_of(calls) == "curl -fsSL -- https://example.test/i.sh | sh"


@pytest.mark.parametrize(
    ("method", "shell"),
    [
        (Method(kind="script", params={"url": "https://example.test/i.sh"}), "sh"),
        (Method(kind="sdkman", params={"candidate": "java"}), "bash"),
    ],
)
def test_spawned_shell_demotes_the_managed_shim_dir_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: Method, shell: str
):
    # A vendor install script piped to a shell inherits our PATH. With the ban
    # active its own npm/npx call would hit our hard-block shim and its
    # `pnpm add -g` would be rewritten to `volta install`.
    monkeypatch.setenv("HOME", str(tmp_path))
    shim_dir = tmp_path / ".local" / "bin"
    other = tmp_path / "usr" / "bin"
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{other}")
    calls, runner = _record()
    execute(method, runner)
    assert calls[0][0] == shell
    exported = calls[0][2].split("; export PATH; ")[0].removeprefix("PATH=")
    assert shlex.split(exported)[0].split(os.pathsep) == [str(other), str(shim_dir)]
    # Demoted, never dropped: the shim dir is also the managed bin dir, so a
    # script that legitimately needs a tool installed there must still find it.
    assert str(shim_dir) in exported


def test_spawned_shell_path_is_unchanged_without_the_shim_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", f"/usr/bin{os.pathsep}/bin")
    calls, runner = _record()
    execute(Method(kind="script", params={"url": "https://example.test/i.sh"}), runner)
    exported = calls[0][2].split("; export PATH; ")[0].removeprefix("PATH=")
    assert shlex.split(exported)[0] == f"/usr/bin{os.pathsep}/bin"


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


def _plant_executable(directory: Path, name: str, body: str = "#!/bin/sh\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body)
    path.chmod(0o755)
    return path


def test_node_runs_pnpm_add_global_never_bare_npm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    fake_pnpm = _plant_executable(tmp_path / "bin", "pnpm")
    monkeypatch.setenv("PATH", str(fake_pnpm.parent))
    calls: list[list[str]] = []
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    execute(method, calls.append)
    assert calls == [[str(fake_pnpm), "add", "-g", "@mermaid-js/mermaid-cli"]]
    assert all(call[0] != "npm" for call in calls)
    assert all(call[0] != "pnpm" for call in calls)


def test_node_raises_when_real_pnpm_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    calls: list[list[str]] = []
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    with pytest.raises(ExecutorError, match="pnpm") as exc_info:
        execute(method, calls.append)
    # The message names what the user can act on, not an internal search rule.
    assert "install pnpm" in str(exc_info.value)
    assert calls == []


def test_node_skips_wrapper_first_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    wrapper = _plant_executable(
        tmp_path / ".local" / "bin",
        "pnpm",
        body=f"#!/bin/sh\n{REDIRECT_SENTINEL}\n",
    )
    real = _plant_executable(tmp_path / "real", "pnpm")
    monkeypatch.setenv("PATH", f"{wrapper.parent}{os.pathsep}{real.parent}")
    calls: list[list[str]] = []
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    execute(method, calls.append)
    assert calls == [[str(real), "add", "-g", "@mermaid-js/mermaid-cli"]]


def test_node_without_npm_pkg_raises_executor_error():
    with pytest.raises(ExecutorError, match="npm_pkg"):
        execute(Method(kind="node", params={}), lambda _cmd: None)


def _plant_pnpm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    fake_pnpm = _plant_executable(tmp_path / "bin", "pnpm", body="#!/bin/sh\necho 11.9.0\n")
    monkeypatch.setenv("PATH", str(fake_pnpm.parent))
    return fake_pnpm


def test_node_co_install_emits_one_comma_joined_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    execute(
        Method(
            kind="node",
            params={"npm_pkg": "@mermaid-js/mermaid-cli", "co_install": ["puppeteer"]},
        ),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "@mermaid-js/mermaid-cli,puppeteer"]]


def test_node_allow_build_emits_flag_before_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    execute(
        Method(kind="node", params={"npm_pkg": "puppeteer", "allow_build": ["puppeteer"]}),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer"]]


def test_node_versions_pin_group_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    execute(
        Method(
            kind="node",
            params={
                "npm_pkg": "puppeteer",
                "allow_build": ["puppeteer"],
                "versions": {"puppeteer": "^25"},
            },
        ),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer@^25"]]


def test_node_grouped_pinned_allowed_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    execute(
        Method(
            kind="node",
            params={
                "npm_pkg": "@mermaid-js/mermaid-cli",
                "co_install": ["puppeteer"],
                "allow_build": ["puppeteer"],
                "versions": {"puppeteer": "^25"},
            },
        ),
        calls.append,
    )
    assert calls == [
        [
            str(pnpm),
            "add",
            "-g",
            "--allow-build=puppeteer",
            "@mermaid-js/mermaid-cli,puppeteer@^25",
        ]
    ]


def test_node_co_install_does_not_duplicate_own_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    execute(
        Method(kind="node", params={"npm_pkg": "puppeteer", "co_install": ["puppeteer"]}),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "puppeteer"]]


def test_node_bare_string_co_install_raises_not_iterated() -> None:
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="co_install"):
        execute(
            Method(kind="node", params={"npm_pkg": "x", "co_install": "puppeteer"}),
            calls.append,
        )
    assert calls == []


def test_node_non_string_co_install_element_raises() -> None:
    with pytest.raises(ExecutorError, match="co_install"):
        execute(Method(kind="node", params={"npm_pkg": "x", "co_install": [1]}), lambda _cmd: None)


def test_node_versions_bare_string_raises() -> None:
    with pytest.raises(ExecutorError, match="versions"):
        execute(Method(kind="node", params={"npm_pkg": "x", "versions": "nope"}), lambda _cmd: None)


def test_node_smoke_does_not_change_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    execute(
        Method(
            kind="node",
            params={
                "npm_pkg": "puppeteer",
                "allow_build": ["puppeteer"],
                "smoke": "puppeteer-browser",
            },
        ),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer"]]


def test_sdkman_sources_init_script_then_installs_candidate():
    calls, runner = _record()
    execute(Method(kind="sdkman", params={"candidate": "java"}), runner)
    assert _script_of(calls, "bash") == '. "$HOME/.sdkman/bin/sdkman-init.sh" && sdk install java'


def test_sdkman_appends_version_when_given():
    calls, runner = _record()
    execute(
        Method(kind="sdkman", params={"candidate": "java", "version": "21.0.4-tem"}),
        runner,
    )
    assert (
        _script_of(calls, "bash")
        == '. "$HOME/.sdkman/bin/sdkman-init.sh" && sdk install java 21.0.4-tem'
    )


def test_sdkman_without_candidate_raises_executor_error():
    with pytest.raises(ExecutorError, match="candidate"):
        execute(Method(kind="sdkman", params={}), lambda _cmd: None)
