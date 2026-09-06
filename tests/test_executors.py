import os
import shlex
from collections.abc import Callable
from pathlib import Path

import pytest

import installer.executors as executors
from installer.executors import EXECUTORS, SMOKE_CHECKS, ExecutorError, execute
from installer.guards import REDIRECT_SENTINEL
from installer.model import SMOKE_CHECK_NAMES, Method
from installer.run import TIMEOUT_CODE, CommandError, Runner


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


def _const_probe(result: str | None) -> Callable[[list[str]], str | None]:
    def probe(argv: list[str]) -> str | None:
        return result

    return probe


def _pnpm_or_node_probe(
    pnpm: str, when_pnpm: str, otherwise: str
) -> Callable[[list[str]], str | None]:
    def probe(argv: list[str]) -> str | None:
        return when_pnpm if argv[0] == pnpm else otherwise

    return probe


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


def _stub_launch(result: str | None) -> Callable[[], str | None]:
    def launch() -> str | None:
        return result

    return launch


def test_node_smoke_does_not_change_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(executors, "launch_puppeteer", _stub_launch(None))
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


def test_node_without_new_params_performs_zero_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    seen: list[list[str]] = []

    def recording_probe(argv: list[str]) -> str:
        seen.append(argv)
        return "99.0.0"

    monkeypatch.setattr(executors, "probe_version", recording_probe)
    calls: list[list[str]] = []
    execute(Method(kind="node", params={"npm_pkg": "rg"}), calls.append)
    assert seen == []
    assert calls == [[str(pnpm), "add", "-g", "rg"]]


def test_node_co_install_proceeds_on_pnpm_11(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe(str(pnpm), "11.9.0", "v24.4.0"),
    )
    calls: list[list[str]] = []
    execute(
        Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "a,b"]]


def test_node_co_install_refuses_pnpm_10(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe(str(pnpm), "10.9.0", "v24.4.0"),
    )
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="(?s)(?=.*10[.]9[.]0)(?=.*11[.]1[.]0)"):
        execute(
            Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}),
            calls.append,
        )
    assert calls == []


def test_node_co_install_refuses_pnpm_11_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """11.0.x accepts the comma spec and does not form a shared install group.

    The grouping semantics arrived in 11.1, so this is the machine a floor of
    11.0.0 waved through into an install that silently leaves the dependent
    unable to resolve its peer.
    """
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe(str(pnpm), "11.0.9", "v24.4.0"),
    )
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="(?s)(?=.*11[.]0[.]9)(?=.*11[.]1[.]0)"):
        execute(
            Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}),
            calls.append,
        )
    assert calls == []


def test_node_co_install_accepts_pnpm_11_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe(str(pnpm), "11.1.0", "v24.4.0"),
    )
    calls: list[list[str]] = []
    execute(Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}), calls.append)
    assert calls == [[str(pnpm), "add", "-g", "a,b"]]


def test_node_allow_build_floor_is_10_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe(str(pnpm), "10.4.0", "v24.4.0"),
    )
    calls: list[list[str]] = []
    execute(
        Method(kind="node", params={"npm_pkg": "puppeteer", "allow_build": ["puppeteer"]}),
        calls.append,
    )
    assert len(calls) == 1
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe(str(pnpm), "10.3.0", "v24.4.0"),
    )
    calls.clear()
    with pytest.raises(ExecutorError, match="(?s)(?=.*10[.]3[.]0)(?=.*10[.]4[.]0)"):
        execute(
            Method(kind="node", params={"npm_pkg": "puppeteer", "allow_build": ["puppeteer"]}),
            calls.append,
        )
    assert calls == []


def test_node_min_node_floor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(executors, "probe_version", _const_probe("v24.4.0"))
    calls: list[list[str]] = []
    execute(
        Method(kind="node", params={"npm_pkg": "puppeteer", "min_node": "22.12.0"}),
        calls.append,
    )
    assert calls == [[str(pnpm), "add", "-g", "puppeteer"]]
    monkeypatch.setattr(
        executors,
        "probe_version",
        _pnpm_or_node_probe("node", "v20.11.0", "11.9.0"),
    )
    calls.clear()
    with pytest.raises(ExecutorError, match="(?s)(?=.*20[.]11[.]0)(?=.*22[.]12[.]0)"):
        execute(
            Method(kind="node", params={"npm_pkg": "puppeteer", "min_node": "22.12.0"}),
            calls.append,
        )
    assert calls == []


def test_node_unreadable_version_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(executors, "probe_version", _const_probe(None))
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="11.1.0"):
        execute(
            Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}),
            calls.append,
        )
    assert calls == []


def test_smoke_checks_match_closed_name_set() -> None:
    assert set(SMOKE_CHECKS) == SMOKE_CHECK_NAMES == frozenset({"puppeteer-browser"})


def test_smoke_puppeteer_browser_passes_when_the_launch_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(executors, "launch_puppeteer", _stub_launch(None))
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


def test_smoke_puppeteer_browser_fails_when_the_launch_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        executors, "launch_puppeteer", _stub_launch("error while loading libnss3.so")
    )
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="PUPPETEER_EXECUTABLE_PATH") as exc_info:
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
    assert "libnss3.so" in str(exc_info.value)
    # The install already ran: a postinstall-driven download cannot be gated
    # before the shim it produces exists.
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer"]]


def test_node_without_smoke_never_launches_a_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    launches = 0

    def counting_launch() -> str | None:
        nonlocal launches
        launches += 1
        return None

    seen: list[list[str]] = []

    def fake_probe(argv: list[str]) -> str:
        seen.append(argv)
        return "v24.4.0" if argv[0] == "node" else "11.9.0"

    monkeypatch.setattr(executors, "launch_puppeteer", counting_launch)
    monkeypatch.setattr(executors, "probe_version", fake_probe)
    execute(
        Method(
            kind="node",
            params={
                "npm_pkg": "puppeteer",
                "co_install": ["x"],
                "allow_build": ["puppeteer"],
                "versions": {"puppeteer": "^25"},
                "min_node": "22.12.0",
            },
        ),
        _record()[1],
    )
    assert launches == 0
    assert any(argv[0] == str(pnpm) for argv in seen)
    assert any(argv[0] == "node" for argv in seen)


def test_node_versions_non_string_value_raises() -> None:
    with pytest.raises(ExecutorError, match="versions"):
        execute(
            Method(kind="node", params={"npm_pkg": "x", "versions": {"puppeteer": 1}}),
            _record()[1],
        )


def test_unknown_smoke_raises_before_the_install_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo in a registry `smoke` name must not cost a real global install.

    Every other `_node` param is validated before the side effect. Validating
    this one afterwards left the machine in exactly the state CR-02 describes:
    the package installed, its shim on PATH, and the install reported FAILED.
    """
    _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="smoke"):
        execute(
            Method(kind="node", params={"npm_pkg": "x", "smoke": "not-a-check"}),
            calls.append,
        )
    assert calls == []


# --- the launch probe itself -------------------------------------------------
#
# Driven through `executors.launch_puppeteer`, the module-level seam the smoke
# check calls. Root discovery and the subprocess both sit behind it, so these
# tests exercise the real discovery without reaching a real pnpm, node or
# browser — and without reaching past the module's public surface.


def _plant_shim(bin_dir: Path, target: Path) -> Path:
    """A pnpm-shaped `cmd-shim` script: a shell wrapper with a target trailer."""
    return _plant_executable(
        bin_dir,
        "puppeteer",
        body=f'#!/bin/sh\nexec node "{target}" "$@"\n# cmd-shim-target={target}\n',
    )


def _plant_package(root: Path) -> Path:
    """`<group>/node_modules/puppeteer/lib/cli.js`, the file a shim points at."""
    entry = root / "node_modules" / "puppeteer" / "lib" / "cli.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("x")
    return entry


def _which_returning(result: str | None) -> Callable[[str], str | None]:
    """A typed stand-in for `shutil.which`, which the probe uses to find the shim."""

    def which(_name: str) -> str | None:
        return result

    return which


class _FakeRun:
    """Stands in for `run_output` for both calls the probe can make.

    `pnpm bin -g` answers with `bin_dir`; anything else is the node launch and
    answers with `launch`, which is either output or an exception to raise.
    """

    def __init__(self, *, bin_dir: Path | None = None, launch: str | Exception = "") -> None:
        self.bin_dir = bin_dir
        self.launch = launch
        self.calls: list[tuple[list[str], float | None]] = []

    def __call__(self, argv: list[str], *, timeout: float | None = None) -> str:
        self.calls.append((argv, timeout))
        if argv[1:] == ["bin", "-g"]:
            return "" if self.bin_dir is None else f"{self.bin_dir}\n"
        if isinstance(self.launch, Exception):
            raise self.launch
        return self.launch

    @property
    def node_call(self) -> tuple[list[str], float | None]:
        return next(call for call in self.calls if call[0][0] == "node")


def _no_shim_anywhere(monkeypatch: pytest.MonkeyPatch, run: _FakeRun) -> None:
    monkeypatch.setattr(executors, "which", _which_returning(None))
    monkeypatch.setattr(executors, "real_pnpm", lambda: None)
    monkeypatch.setattr(executors, "run_output", run)


def test_launch_probe_defers_every_browser_choice_to_puppeteer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of H1: this project no longer picks the binary.

    A `--version` probe on a path found by globbing the cache proved neither
    that the file was the browser puppeteer would launch nor that a launch
    works, so the probe must go through `puppeteer.launch()` and must not
    reintroduce a cache search or an executable-path read of its own.
    """
    run = _FakeRun()
    _no_shim_anywhere(monkeypatch, run)
    assert executors.launch_puppeteer() is None
    argv, timeout = run.node_call
    # Bare `node` for the same reason `min_node` is probed bare: the node that
    # matters is the one pnpm's postinstall and mmdc find on PATH.
    assert argv[:2] == ["node", "-e"]
    script = argv[2]
    assert "puppeteer.launch()" in script
    assert "newPage()" in script
    assert "browser.close()" in script
    assert "--version" not in script
    assert "PUPPETEER_EXECUTABLE_PATH" not in script
    assert "chrome-headless-shell" not in script
    # Bounded: this runs inside an install and inside the Doctor's audit thread.
    assert timeout == executors.BROWSER_LAUNCH_TIMEOUT


def test_launch_probe_resolves_puppeteer_from_the_shim_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pnpm v11 has no single global node_modules, so the shim is the pointer.

    `pnpm root -g` names a directory with no `node_modules` of its own — each
    hash-keyed install group has one — so the root node must resolve from is the
    directory of the file the bin shim execs.
    """
    entry = _plant_package(tmp_path / "group")
    shim = _plant_shim(tmp_path / "bin", entry)
    run = _FakeRun()
    monkeypatch.setattr(executors, "which", _which_returning(str(shim)))
    monkeypatch.setattr(executors, "real_pnpm", lambda: None)
    monkeypatch.setattr(executors, "run_output", run)
    assert executors.launch_puppeteer() is None
    assert run.node_call[0][3:] == [str(entry.parent)]


def test_launch_probe_follows_a_symlinked_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Older layouts symlink the global bin instead of writing a cmd-shim."""
    entry = _plant_package(tmp_path / "group")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    link = bin_dir / "puppeteer"
    link.symlink_to(entry)
    run = _FakeRun()
    monkeypatch.setattr(executors, "which", _which_returning(str(link)))
    monkeypatch.setattr(executors, "real_pnpm", lambda: None)
    monkeypatch.setattr(executors, "run_output", run)
    assert executors.launch_puppeteer() is None
    assert run.node_call[0][3:] == [str(entry.parent)]


def test_launch_probe_asks_pnpm_for_its_bin_dir_when_path_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`which` is PATH-based, and PATH is not always current.

    A machine whose pnpm global bin directory was added to PATH during this same
    run has not inherited it here, and failing the smoke check there would
    report a working install as broken.
    """
    entry = _plant_package(tmp_path / "group")
    bin_dir = tmp_path / "bin"
    _plant_shim(bin_dir, entry)
    run = _FakeRun(bin_dir=bin_dir)
    monkeypatch.setattr(executors, "which", _which_returning(None))
    monkeypatch.setattr(executors, "real_pnpm", lambda: "/abs/pnpm")
    monkeypatch.setattr(executors, "run_output", run)
    assert executors.launch_puppeteer() is None
    # Absolute path, never a bare `pnpm`: a bare name would be answered by this
    # installer's own argv-conditional wrapper.
    assert run.calls[0][0] == ["/abs/pnpm", "bin", "-g"]
    assert run.node_call[0][3:] == [str(entry.parent)]


def test_launch_probe_offers_each_root_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = _plant_package(tmp_path / "group")
    bin_dir = tmp_path / "bin"
    shim = _plant_shim(bin_dir, entry)
    run = _FakeRun(bin_dir=bin_dir)
    monkeypatch.setattr(executors, "which", _which_returning(str(shim)))
    monkeypatch.setattr(executors, "real_pnpm", lambda: "/abs/pnpm")
    monkeypatch.setattr(executors, "run_output", run)
    assert executors.launch_puppeteer() is None
    assert run.node_call[0][3:] == [str(entry.parent)]


def test_launch_probe_passes_no_root_it_could_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An opaque shim, an empty trailer and an absent file all yield nothing.

    No root is not a failure: node then resolves `puppeteer` its own way.
    """
    opaque = _plant_executable(tmp_path / "a", "puppeteer", body="#!/bin/sh\nexec node x\n")
    blank = _plant_executable(tmp_path / "b", "puppeteer", body="#!/bin/sh\n# cmd-shim-target=\n")
    for shim_dir in (opaque.parent, blank.parent, tmp_path / "absent"):
        run = _FakeRun(bin_dir=shim_dir)
        monkeypatch.setattr(executors, "which", _which_returning(None))
        monkeypatch.setattr(executors, "real_pnpm", lambda: "/abs/pnpm")
        monkeypatch.setattr(executors, "run_output", run)
        assert executors.launch_puppeteer() is None
        assert run.node_call[0][3:] == []


def test_launch_probe_survives_a_shim_it_cannot_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable shim costs a root, never an OSError out of the check.

    `run_smoke_check` catches ExecutorError and nothing else, so an OSError
    escaping here would abort the Doctor's whole audit instead of reporting one
    finding — the non-raising dispatch contract CR-02 established.
    """
    entry = _plant_package(tmp_path / "group")
    shim = _plant_shim(tmp_path / "bin", entry)

    def refuse(_self: Path, *_args: object, **_kwargs: object) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", refuse)
    run = _FakeRun()
    monkeypatch.setattr(executors, "which", _which_returning(str(shim)))
    monkeypatch.setattr(executors, "real_pnpm", lambda: None)
    monkeypatch.setattr(executors, "run_output", run)
    assert executors.launch_puppeteer() is None
    assert run.node_call[0][3:] == []


def test_launch_probe_ignores_a_pnpm_that_cannot_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable bin dir costs a root, never the whole check."""

    class Refusing(_FakeRun):
        def __call__(self, argv: list[str], *, timeout: float | None = None) -> str:
            if argv[1:] == ["bin", "-g"]:
                raise CommandError(argv, 1)
            return super().__call__(argv, timeout=timeout)

    run = Refusing()
    monkeypatch.setattr(executors, "which", _which_returning(None))
    monkeypatch.setattr(executors, "real_pnpm", lambda: "/abs/pnpm")
    monkeypatch.setattr(executors, "run_output", run)
    assert executors.launch_puppeteer() is None
    assert run.node_call[0][3:] == []


def test_launch_probe_reports_the_browsers_own_error(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _FakeRun(
        launch=CommandError(
            ["node"], 1, detail="Failed to launch the browser process!\n  libnss3.so"
        )
    )
    _no_shim_anywhere(monkeypatch, run)
    assert executors.launch_puppeteer() == "Failed to launch the browser process! libnss3.so"


def test_launch_probe_names_node_when_node_cannot_run(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _FakeRun(launch=CommandError(["node"], 127))
    _no_shim_anywhere(monkeypatch, run)
    assert executors.launch_puppeteer() == "node could not be started to run the launch probe"


def test_launch_probe_falls_back_to_the_exit_code_without_a_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _FakeRun(launch=CommandError(["node"], 3))
    _no_shim_anywhere(monkeypatch, run)
    assert executors.launch_puppeteer() == "the launch probe exited 3"


def test_launch_probe_reports_a_timeout_rather_than_hanging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _FakeRun(launch=CommandError(["node"], TIMEOUT_CODE, detail="timed out after 60s"))
    _no_shim_anywhere(monkeypatch, run)
    assert executors.launch_puppeteer() == "timed out after 60s"


def test_launch_failure_detail_is_condensed_for_a_one_line_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The text lands in a Doctor warning row; a Chrome failure is a paragraph."""
    run = _FakeRun(launch=CommandError(["node"], 1, detail="a\n" + "b" * 900))
    _no_shim_anywhere(monkeypatch, run)
    detail = executors.launch_puppeteer()
    assert detail is not None
    assert len(detail) == 400
    assert detail.endswith("...")
    assert "\n" not in detail


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


def test_run_smoke_check_reports_the_failure_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise ExecutorError("browser could not be started")

    monkeypatch.setitem(executors.SMOKE_CHECKS, "puppeteer-browser", boom)
    assert executors.run_smoke_check("puppeteer-browser") == "browser could not be started"


def test_run_smoke_check_returns_none_when_the_check_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(executors.SMOKE_CHECKS, "puppeteer-browser", lambda: None)
    assert executors.run_smoke_check("puppeteer-browser") is None


def test_run_smoke_check_invents_no_failure_from_a_name_it_cannot_interpret() -> None:
    """`load_tools` is the gate for an unknown name; an audit must not guess.

    Reporting a name it could not dispatch as a broken tool would state an
    unknown as a fact, which is the rule NodeGlobalsReport.known enforces.
    """
    assert executors.run_smoke_check("not-a-check") is None
