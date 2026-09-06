import os
import shlex
from collections.abc import Callable
from pathlib import Path

import pytest

import installer.executors as executors
from installer.executors import EXECUTORS, SMOKE_CHECKS, ExecutorError, execute
from installer.guards import REDIRECT_SENTINEL
from installer.model import SMOKE_CHECK_NAMES, Method
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


def test_node_smoke_does_not_change_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    cache = tmp_path / "cache"
    browser = (
        cache
        / "chrome-headless-shell"
        / "linux-140.0.0"
        / "chrome-headless-shell-linux64"
        / "chrome-headless-shell"
    )
    browser.parent.mkdir(parents=True)
    browser.write_text("x")
    browser.chmod(0o755)
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))
    monkeypatch.setattr(executors, "probe_version", _const_probe("99.0.0"))
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
    with pytest.raises(ExecutorError, match="(?s)(?=.*10[.]9[.]0)(?=.*11[.]0[.]0)"):
        execute(
            Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}),
            calls.append,
        )
    assert calls == []


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
    with pytest.raises(ExecutorError, match="11.0.0"):
        execute(
            Method(kind="node", params={"npm_pkg": "a", "co_install": ["b"]}),
            calls.append,
        )
    assert calls == []


def test_smoke_checks_match_closed_name_set() -> None:
    assert set(SMOKE_CHECKS) == SMOKE_CHECK_NAMES == frozenset({"puppeteer-browser"})


def _plant_browser(cache: Path, version: str = "linux-140.0.0") -> Path:
    browser = (
        cache
        / "chrome-headless-shell"
        / version
        / "chrome-headless-shell-linux64"
        / "chrome-headless-shell"
    )
    browser.parent.mkdir(parents=True)
    browser.write_text("x")
    browser.chmod(0o755)
    return browser


def test_smoke_puppeteer_browser_succeeds_when_probe_returns_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    cache = tmp_path / "cache"
    _plant_browser(cache)
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))
    monkeypatch.setattr(executors, "probe_version", _const_probe("99.0.0"))
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


def test_smoke_puppeteer_browser_fails_when_browser_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    cache = tmp_path / "cache"
    browser = _plant_browser(cache)
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))

    def browser_fails(argv: list[str]) -> str | None:
        return None if "chrome" in argv[0] else "99.0.0"

    monkeypatch.setattr(executors, "probe_version", browser_fails)
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
    assert str(browser) in str(exc_info.value)
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer"]]


def test_smoke_puppeteer_browser_fails_when_cache_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    cache = tmp_path / "empty-cache"
    cache.mkdir()
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))
    monkeypatch.setattr(executors, "probe_version", _const_probe("99.0.0"))
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match=cache.as_posix()):
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


def test_smoke_honours_puppeteer_executable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    custom = tmp_path / "custom-chrome"
    custom.write_text("x")
    custom.chmod(0o755)
    monkeypatch.setenv("PUPPETEER_EXECUTABLE_PATH", str(custom))
    seen: list[list[str]] = []

    def fake_probe(argv: list[str]) -> str | None:
        seen.append(argv)
        return "99.0.0"

    monkeypatch.setattr(executors, "probe_version", fake_probe)
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
    assert [argv[0] for argv in seen if "chrome" in argv[0] or argv[0] == str(custom)]
    assert any(argv[0] == str(custom) for argv in seen)
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer"]]


@pytest.mark.parametrize(
    ("older_build", "newer_build"),
    [
        # Equal digit widths: lexicographic and numeric order coincide, so this
        # pair passed even while the code sorted whole path STRINGS.
        ("linux-140.0.0", "linux-152.0.0"),
        # Real puppeteer build numbers of unequal width. "99" sorts AFTER "140"
        # as text and BEFORE it as a number, so only a parsed comparison picks
        # the right build.
        ("linux-99.0.4844.51", "linux-140.0.7339.16"),
    ],
)
def test_smoke_prefers_headless_shell_highest_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, older_build: str, newer_build: str
) -> None:
    _plant_pnpm(tmp_path, monkeypatch)
    cache = tmp_path / "cache"
    _plant_browser(cache, older_build)
    newer = _plant_browser(cache, newer_build)
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))
    seen: list[list[str]] = []

    def fake_probe(argv: list[str]) -> str | None:
        seen.append(argv)
        return "99.0.0"

    monkeypatch.setattr(executors, "probe_version", fake_probe)
    execute(
        Method(
            kind="node",
            params={
                "npm_pkg": "puppeteer",
                "allow_build": ["puppeteer"],
                "smoke": "puppeteer-browser",
            },
        ),
        _record()[1],
    )
    browser_probes = [argv for argv in seen if argv[0].endswith("chrome-headless-shell")]
    assert browser_probes
    assert browser_probes[-1][0] == str(newer)


def test_node_without_smoke_never_probes_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    seen: list[list[str]] = []

    def fake_probe(argv: list[str]) -> str:
        seen.append(argv)
        if argv[0] == "node":
            return "v24.4.0"
        return "11.9.0"

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
    assert all("chrome" not in argv[0] for argv in seen)
    assert any(argv[0] == str(pnpm) for argv in seen)
    assert any(argv[0] == "node" for argv in seen)


def test_node_versions_non_string_value_raises() -> None:
    with pytest.raises(ExecutorError, match="versions"):
        execute(
            Method(kind="node", params={"npm_pkg": "x", "versions": {"puppeteer": 1}}),
            _record()[1],
        )


def test_smoke_falls_back_to_chrome_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    cache = tmp_path / "cache"
    chrome = cache / "chrome" / "linux-140.0.0" / "chrome-linux64" / "chrome"
    chrome.parent.mkdir(parents=True)
    chrome.write_text("x")
    chrome.chmod(0o755)
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(cache))
    seen: list[list[str]] = []

    def fake_probe(argv: list[str]) -> str:
        seen.append(argv)
        return "99.0.0"

    monkeypatch.setattr(executors, "probe_version", fake_probe)
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
    assert any(argv[0] == str(chrome) for argv in seen)
    assert calls == [[str(pnpm), "add", "-g", "--allow-build=puppeteer", "puppeteer"]]


def test_smoke_executable_path_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    custom = tmp_path / "broken-chrome"
    monkeypatch.setenv("PUPPETEER_EXECUTABLE_PATH", str(custom))

    def fake_probe(argv: list[str]) -> str | None:
        return None if argv[0] == str(custom) else "99.0.0"

    monkeypatch.setattr(executors, "probe_version", fake_probe)
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="PUPPETEER_EXECUTABLE_PATH"):
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


def test_unknown_smoke_raises_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    calls: list[list[str]] = []
    with pytest.raises(ExecutorError, match="smoke"):
        execute(
            Method(kind="node", params={"npm_pkg": "x", "smoke": "not-a-check"}),
            calls.append,
        )
    assert calls == [[str(pnpm), "add", "-g", "x"]]


def test_puppeteer_cache_dir_falls_back_to_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pnpm = _plant_pnpm(tmp_path, monkeypatch)
    monkeypatch.delenv("PUPPETEER_CACHE_DIR", raising=False)
    monkeypatch.setattr(executors, "probe_version", _const_probe("99.0.0"))
    calls: list[list[str]] = []
    expected = str(tmp_path / ".cache" / "puppeteer")
    with pytest.raises(ExecutorError, match="puppeteer") as exc_info:
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
    assert expected in str(exc_info.value)
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
