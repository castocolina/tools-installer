import asyncio
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, NamedTuple, cast

import pytest
from textual.app import App

import setup
from tests.conftest import GuardedPopen, launch_policy
from tests.sandbox import (
    CHECKOUT,
    FORBIDDEN_PROGRAM_NAMES,
    INTERPRETER_DIR_STASH,
    LINUXBREW_PREFIX,
    OVERRIDES_STASH,
    SHELL_BUILTINS,
    UTILITY_NAMES,
    LaunchPolicy,
    build_launch_policy,
    capture_home_overrides,
    check_launch,
    env_names_to_clear,
    fail_on_refusals,
    guarded_os_call,
    host_free_path,
    host_zsh,
    link_interpreters,
    nodeid_of,
    prepare_interpreter_dir,
    record_refusal,
    refused,
    take_refusals,
)


def test_host_toolchain_dirs_are_off_path() -> None:
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    linuxbrew = Path(os.path.realpath(LINUXBREW_PREFIX))
    for entry in os.environ["PATH"].split(os.pathsep):
        if not entry:
            continue
        resolved = Path(os.path.realpath(entry))
        assert not resolved.is_relative_to(real_home)
        assert not resolved.is_relative_to(Path("/run/user"))
        assert not resolved.is_relative_to(linuxbrew)
    assert "VOLTA_HOME" not in os.environ
    assert env_names_to_clear(os.environ) == ()


def test_the_path_strip_survives_a_looping_entry(tmp_path: Path) -> None:
    loop = tmp_path / "loopbin"
    loop.symlink_to(loop)
    kept = host_free_path(f"{loop}{os.pathsep}/usr/bin", real_home=tmp_path / "home").split(
        os.pathsep
    )
    assert "/usr/bin" in kept


def test_host_free_path_strips_linuxbrew_home_and_run_user(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    home = root / "home"
    brew = root / "brew"
    keep = home / "link"
    (brew / "bin").mkdir(parents=True)
    keep.mkdir(parents=True)
    alias = root / "alias"
    alias.symlink_to(brew / "bin")
    path_value = os.pathsep.join(
        [
            str(brew),
            str(brew / "bin"),
            str(alias),
            "/usr/bin",
            str(home / "bin"),
            str(keep),
            "/run/user/1000/fnm",
            "/usr/local/bin",
        ]
    )
    kept = host_free_path(path_value, real_home=home, linuxbrew=brew, keep=keep)
    assert kept.split(os.pathsep) == ["/usr/bin", str(keep), "/usr/local/bin"]


def test_env_names_to_clear_matches_prefixes_exactly() -> None:
    environ: dict[str, str] = dict.fromkeys(
        (
            "npm_config_foo",
            "NPM_CONFIG_BAR",
            "UV_CACHE_DIR",
            "OPENCODE_CONFIG_DIR",
            "HOMEBREW_PREFIX",
            "GH_TOKEN",
            "CODEX_HOME",
            "MY_UV_X",
            "KEEP_ME",
        ),
        "x",
    )
    assert env_names_to_clear(environ) == (
        "CODEX_HOME",
        "GH_TOKEN",
        "HOMEBREW_PREFIX",
        "NPM_CONFIG_BAR",
        "OPENCODE_CONFIG_DIR",
        "UV_CACHE_DIR",
        "npm_config_foo",
    )


def test_home_overrides_survive_the_configure_clearing() -> None:
    stashed: dict[str, str | None] = {
        "UV_TOOL_DIR": "/stash/uv",
        "PNPM_HOME": None,
        "VOLTA_HOME": "/stash/volta",
    }
    live = {"UV_TOOL_DIR": "/live/uv", "PNPM_HOME": "/live/pnpm"}
    assert capture_home_overrides({**live, OVERRIDES_STASH: json.dumps(stashed)}) == stashed
    assert capture_home_overrides(live) == {
        "UV_TOOL_DIR": "/live/uv",
        "PNPM_HOME": "/live/pnpm",
        "VOLTA_HOME": None,
    }


def test_link_interpreters_links_only_what_the_strip_removed(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    original = root / "original"
    kept = root / "kept"
    _fake(original, "zsh")
    _fake(original, "sh")
    _fake(original, "python3")
    _fake(kept, "sh")
    original_path = os.pathsep.join([str(kept), str(original)])
    link = root / "link"
    link.mkdir()

    assert link_interpreters(link, stripped_path=str(kept), original_path=original_path) is True
    assert sorted(entry.name for entry in link.iterdir()) == ["zsh"]
    assert os.readlink(link / "zsh") == os.path.realpath(original / "zsh")

    nothing_missing = root / "nothing-missing"
    nothing_missing.mkdir()
    assert (
        link_interpreters(nothing_missing, stripped_path=original_path, original_path=original_path)
        is False
    )
    assert list(nothing_missing.iterdir()) == []


def test_zsh_resolves_when_the_host_has_one(tmp_path_factory: pytest.TempPathFactory) -> None:
    recorded = host_zsh()
    if recorded is None:
        pytest.skip("this host has no zsh at all")
    found = shutil.which("zsh")
    assert found is not None
    assert Path(os.path.realpath(found)) == recorded
    policy = build_launch_policy(
        tmp_path_factory.getbasetemp().resolve(), path_value=os.environ["PATH"]
    )
    assert recorded in policy.interpreters
    check_launch(["zsh", "-f", "-c", "true"], env=None, cwd=None, policy=policy)


def test_the_interpreter_dir_is_prepended_once() -> None:
    link = os.environ.get(INTERPRETER_DIR_STASH)
    entries = os.environ["PATH"].split(os.pathsep)
    if link is not None:
        assert entries.count(link) == 1
        assert entries[0] == link
    without_link = os.pathsep.join(entry for entry in entries if entry != link)
    if host_zsh() is not None and shutil.which("zsh", path=without_link) is None:
        assert link is not None
        found = shutil.which("zsh")
        assert found is not None
        assert Path(found).parent == Path(link)


def test_a_worker_keeps_the_inherited_interpreter_dir(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    fake_home = root / "home"
    link = fake_home / "tmp" / "link"
    link.mkdir(parents=True)
    kept = host_free_path(
        os.pathsep.join([str(link), "/usr/bin"]), real_home=fake_home, keep=link
    ).split(os.pathsep)
    assert kept[0] == str(link)
    assert "/usr/bin" in kept

    def no_new_dir() -> Path:
        raise AssertionError("a worker must reuse the controller's link dir")

    environ = {INTERPRETER_DIR_STASH: str(link)}
    assert prepare_interpreter_dir(environ, real_home=fake_home, make_dir=no_new_dir) == (
        link,
        None,
    )


def test_prepare_interpreter_dir_makes_no_dir_when_no_shell_is_missing(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    bin_dir = root / "bin"
    for name in ("sh", "bash", "zsh"):
        _fake(bin_dir, name)
    link = root / "link"

    def make_dir() -> Path:
        link.mkdir()
        return link

    environ = {"PATH": str(bin_dir)}
    assert prepare_interpreter_dir(environ, real_home=root / "home", make_dir=make_dir) == (
        None,
        None,
    )
    assert not link.exists()
    assert INTERPRETER_DIR_STASH not in environ


def test_a_node_family_binary_outside_tmp_is_never_run(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = Path(tempfile.mkdtemp(prefix="host-node-"))
    try:
        assert not outside.resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve())
        fake = outside / "node"
        fake.write_text("#!/bin/sh\necho forked\n")
        fake.chmod(0o755)

        with refused("host's node"):
            subprocess.run([str(fake), "--version"], check=False)

        monkeypatch.setenv("PATH", str(outside))
        with refused("host's node"):
            subprocess.run(["node", "--version"], check=False)
        with refused("host's node"):
            subprocess.run(["node"], env={"PATH": str(outside)}, check=False)

        inside = tmp_path / "node"
        inside.write_text(fake.read_text())
        inside.chmod(0o755)
        result = subprocess.run([str(inside)], capture_output=True, text=True, check=False)
        assert result.stdout == "forked\n"
    finally:
        shutil.rmtree(outside)


def test_no_setup_home_constant_points_at_the_real_home() -> None:
    """setup.py resolves its home paths at import; the autouse sandbox must re-root them (R1-07)."""
    real_home = Path(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))
    # The checkout may sit under HOME (package data such as _REGISTRY); only home paths count.
    project = Path(os.path.realpath(setup.__file__)).parent
    for name, value in vars(setup).items():
        items: Sequence[object] = (
            cast(Sequence[object], value) if isinstance(value, (list, tuple)) else [value]
        )
        for item in items:
            if isinstance(item, Path) and not Path(os.path.realpath(item)).is_relative_to(project):
                assert not Path(os.path.realpath(item)).is_relative_to(real_home), name
    assert vars(setup)["_MYSHELLRC"] == Path.home() / ".myshellrc"


# --- the launch allowlist (tests/sandbox.py): pure functions, nothing is launched ---


@pytest.fixture
def outside() -> Iterator[Path]:
    """A directory OUTSIDE the base temp: where a "host" program lives."""
    directory = Path(tempfile.mkdtemp(prefix="host-sandbox-")).resolve()
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


@pytest.fixture
def policy(tmp_path_factory: pytest.TempPathFactory) -> LaunchPolicy:
    return build_launch_policy(
        tmp_path_factory.getbasetemp().resolve(), path_value=os.environ["PATH"]
    )


def _fake(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    program = directory / name
    program.write_text("#!/bin/sh\nexit 0\n")
    program.chmod(0o755)
    return program


@pytest.mark.parametrize("name", ["uv", "curl"])
def test_check_launch_refuses_a_host_program(
    name: str, outside: Path, policy: LaunchPolicy
) -> None:
    _fake(outside, name)
    with pytest.raises(AssertionError, match=f"host's {name}"):
        check_launch([name, "--version"], env={"PATH": str(outside)}, cwd=None, policy=policy)
    with pytest.raises(AssertionError, match=f"host's {name}"):
        check_launch([str(outside / name)], env=None, cwd=None, policy=policy)


def test_check_launch_refuses_a_linuxbrew_binary_by_path(policy: LaunchPolicy) -> None:
    with pytest.raises(AssertionError, match="host's brew"):
        check_launch(
            [str(LINUXBREW_PREFIX / "bin" / "brew"), "--version"],
            env=None,
            cwd=None,
            policy=policy,
        )


def test_check_launch_allows_temp_fakes_and_the_interpreter(
    tmp_path: Path, outside: Path, policy: LaunchPolicy
) -> None:
    fake = _fake(tmp_path / "bin", "tool")
    check_launch([str(fake), "--x"], env=None, cwd=None, policy=policy)
    check_launch(["tool"], env={"PATH": str(fake.parent)}, cwd=None, policy=policy)
    check_launch([sys.executable, "-c", "pass"], env=None, cwd=None, policy=policy)
    script = CHECKOUT / "scripts" / "prune-tmp-linux.sh"
    check_launch([script, "--help"], env=None, cwd=None, policy=policy)

    # D-20: .venv tools are not checkout scripts. A scratch checkout keeps this deterministic.
    repo = outside / "repo"
    ruff = _fake(repo / ".venv" / "bin", "ruff")
    _fake(repo / "scripts", "prune-user-tmpdir.sh")
    scratch = replace(policy, checkout=repo.resolve())
    with pytest.raises(AssertionError, match="checkout file .venv/bin/ruff"):
        check_launch([ruff], env=None, cwd=None, policy=scratch, missing_ok=False)
    check_launch([repo / "scripts" / "prune-user-tmpdir.sh"], env=None, cwd=None, policy=scratch)


@pytest.mark.parametrize(
    "relative",
    ["setup.py", "scripts/container-e2e-verify.sh", "scripts/detect-container-runtime.sh"],
)
def test_an_unreviewed_checkout_file_is_never_launched(
    relative: str, tmp_path: Path, policy: LaunchPolicy
) -> None:
    """C-06: only the reviewed checkout files may run; the rest reach host toolchains."""
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    env = {"PATH": str(fakes)}
    with pytest.raises(AssertionError, match="checkout file"):
        check_launch([CHECKOUT / relative], env=env, cwd=None, policy=policy)
    with pytest.raises(AssertionError, match="checkout file"):
        check_launch(["/bin/sh", CHECKOUT / relative], env=env, cwd=None, policy=policy)
    with pytest.raises(AssertionError, match="checkout file"):
        check_launch(
            ["/bin/sh", "-c", f'. "{CHECKOUT / relative}"'], env=env, cwd=None, policy=policy
        )


def test_install_sh_runs_only_when_its_toolchain_is_faked(
    tmp_path: Path, outside: Path, policy: LaunchPolicy
) -> None:
    """C-06 (X-01): install.sh, run or sourced, may reach curl, wget, git and uv; each must
    resolve on the child's PATH to a fake under the base temp or to nothing."""
    install = CHECKOUT / "install.sh"
    fakes = tmp_path / "fakes"
    for name in ("curl", "git", "uv"):
        _fake(fakes, name)
    _fake(outside, "wget")
    for argv in (["/bin/sh", install], ["/bin/sh", "-c", f'. "{install}"; detect_os']):
        check_launch(argv, env={"PATH": str(fakes)}, cwd=None, policy=policy)
        with pytest.raises(AssertionError, match="host's wget"):
            check_launch(
                argv, env={"PATH": f"{fakes}{os.pathsep}{outside}"}, cwd=None, policy=policy
            )


def test_check_launch_judges_the_resolved_path(
    tmp_path: Path, outside: Path, policy: LaunchPolicy
) -> None:
    target = _fake(outside, "tool")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(AssertionError, match="host's"):
        check_launch([link], env=None, cwd=None, policy=policy)


def test_check_launch_refuses_malformed_argv(policy: LaunchPolicy) -> None:
    for argv in ([], "uv --version", [None], 7):
        with pytest.raises(AssertionError, match="the guard needs a non-empty argv list"):
            check_launch(argv, env=None, cwd=None, policy=policy)
    check_launch(("missing-tool-xyz",), env={"PATH": ""}, cwd=None, policy=policy)
    with pytest.raises(AssertionError):
        check_launch(
            ("missing-tool-xyz",), env={"PATH": ""}, cwd=None, policy=policy, missing_ok=False
        )


@pytest.mark.parametrize("env", [{"HOME": "/nonexistent-23-1"}, {}])
def test_check_launch_searches_the_path_the_child_sees(
    env: dict[str, str], policy: LaunchPolicy
) -> None:
    """An env with no PATH makes the exec layer search os.defpath, so the guard must too."""
    with pytest.raises(AssertionError, match="host's true"):
        check_launch(["true"], env=env, cwd=None, policy=policy)


def test_check_launch_resolves_an_empty_path_entry_in_the_child_cwd(
    outside: Path, policy: LaunchPolicy
) -> None:
    _fake(outside, "tool")
    with pytest.raises(AssertionError, match="host's tool"):
        check_launch(["tool"], env={"PATH": ""}, cwd=outside, policy=policy)


def test_the_guard_refuses_a_host_program_under_a_path_less_env(tmp_path: Path) -> None:
    with refused("host's true"):
        subprocess.run(["true"], env={"HOME": str(tmp_path)}, check=False)


def test_check_launch_allows_a_missing_path_only_when_missing_ok(
    tmp_path: Path, policy: LaunchPolicy
) -> None:
    gone = [str(Path("/nonexistent-23-1/tool")), str(tmp_path / "gone" / "tool")]
    for program in gone:
        check_launch([program], env=None, cwd=None, policy=policy)
        with pytest.raises(AssertionError):
            check_launch([program], env=None, cwd=None, policy=policy, missing_ok=False)
    absent = str(LINUXBREW_PREFIX / "bin" / "definitely-missing-23-1")
    with pytest.raises(AssertionError, match="host's definitely-missing-23-1"):
        check_launch([absent], env=None, cwd=None, policy=policy, missing_ok=True)


def _real(path: Path) -> Path:
    return Path(os.path.realpath(path))


_CELLAR = LINUXBREW_PREFIX / "Cellar" / "zsh-23-1" / "9.9" / "bin"


@pytest.mark.parametrize(
    "case",
    [
        "interpreter-member-through-a-link",
        "utility-member-through-a-link",
        "brew-refused",
        "non-member-under-the-prefix-refused",
        "member-script-file-refused",
    ],
)
def test_check_launch_allows_an_interpreter_under_the_linuxbrew_prefix(
    case: str, tmp_path: Path, outside: Path, policy: LaunchPolicy
) -> None:
    member = _real(_CELLAR / "zsh")
    utility = _real(_CELLAR / "systemd-environment-d-generator")
    tool = _real(_CELLAR / "zsh-tool")
    under = replace(policy, interpreters=frozenset({member}), utilities=frozenset({utility}))
    link = tmp_path / "link"
    link.mkdir()
    (link / "zsh").symlink_to(member)
    (link / "systemd-environment-d-generator").symlink_to(utility)
    (link / "zsh-tool").symlink_to(tool)
    inside_file = tmp_path / "script.zsh"
    inside_file.write_text("echo hi\n")
    outside_file = outside / "script.zsh"
    outside_file.write_text("echo hi\n")

    def run(*argv: object) -> None:
        check_launch(list(argv), env=None, cwd=None, policy=under)

    if case == "interpreter-member-through-a-link":
        run(link / "zsh", "-n", inside_file)
    elif case == "utility-member-through-a-link":
        run(link / "systemd-environment-d-generator")
    elif case == "brew-refused":
        with pytest.raises(AssertionError, match="host's brew"):
            run(LINUXBREW_PREFIX / "bin" / "brew", "--version")
    elif case == "non-member-under-the-prefix-refused":
        with pytest.raises(AssertionError, match="host's"):
            run(link / "zsh-tool")
    else:
        with pytest.raises(AssertionError):
            run(link / "zsh", outside_file)


@pytest.mark.parametrize(
    "argv_tail",
    [
        ["-oL", "uv", "--version"],
        ["--output=L", "uv"],
        ["-o", "L", "brew", "install", "rg"],
        ["-oL"],
    ],
    ids=["attached", "long-form", "production-shape", "no-command"],
)
def test_check_launch_treats_stdbuf_as_a_prefix(
    argv_tail: list[str], tmp_path: Path, outside: Path, policy: LaunchPolicy
) -> None:
    stdbuf = _fake(outside, "stdbuf")
    _fake(outside, "uv")
    _fake(outside, "brew")
    wrapped = replace(policy, utilities=frozenset({_real(stdbuf)}))
    env = {"PATH": str(outside)}
    with pytest.raises(AssertionError):
        check_launch([stdbuf, *argv_tail], env=env, cwd=None, policy=wrapped)
    fake = _fake(tmp_path / "bin", "tool")
    check_launch([stdbuf, "-oL", fake], env=env, cwd=None, policy=wrapped)
    check_launch([stdbuf, "-o", "L", "--", fake, "x"], env=env, cwd=None, policy=wrapped)


def test_build_launch_policy_resolves_interpreters_by_realpath(policy: LaunchPolicy) -> None:
    assert _real(Path(sys.executable)) in policy.interpreters
    shell = shutil.which("sh", path=os.environ["PATH"])
    assert shell is not None
    assert _real(Path(shell)) in policy.interpreters
    for member in policy.interpreters | policy.utilities:
        assert member.is_absolute()
        assert member == _real(member)


def test_the_allowlist_names_no_toolchain(policy: LaunchPolicy) -> None:
    assert FORBIDDEN_PROGRAM_NAMES.isdisjoint(UTILITY_NAMES)
    own = _real(Path(sys.executable))
    for member in (policy.interpreters | policy.utilities) - {own}:
        assert member.name not in FORBIDDEN_PROGRAM_NAMES, member


# --- shell scripts: every command word is checked (D-18) ---


class _Shells(NamedTuple):
    """The policy plus fake sh, bash and zsh under tmp_path, so no host shell is needed."""

    policy: LaunchPolicy
    paths: dict[str, Path]
    file: Path
    bindir: Path

    def run(self, shell: str, script: str, *, env: Mapping[str, str] | None = None) -> None:
        text = script.replace("{FILE}", str(self.file))
        check_launch([self.paths[shell], "-c", text], env=env, cwd=None, policy=self.policy)


@pytest.fixture
def shells(tmp_path: Path, policy: LaunchPolicy) -> _Shells:
    bindir = tmp_path / "shells"
    paths = {name: _fake(bindir, name) for name in ("sh", "bash", "zsh")}
    members = frozenset(_real(path) for path in paths.values())
    file = tmp_path / "sourced.sh"
    file.write_text("echo hi\n")
    return _Shells(replace(policy, interpreters=members), paths, file, bindir)


@pytest.mark.parametrize(
    ("shell", "script"),
    [
        ("sh", "uv --version"),
        ("bash", "true && gh --version"),
        ("bash", "echo a; uv x"),
        ("bash", "echo a | uv x"),
        ("bash", "false || uv x"),
        ("bash", "echo a\nuv x"),
        ("bash", "exec uv"),
        ("bash", "command uv"),
        ("bash", "X=1 uv"),
        ("bash", ">/dev/null uv"),
    ],
)
def test_shell_scripts_check_every_command_word(shells: _Shells, shell: str, script: str) -> None:
    with pytest.raises(AssertionError):
        shells.run(shell, script)


def test_shell_scripts_allow_builtins_functions_and_fakes(shells: _Shells) -> None:
    tool = _fake(shells.bindir, "tool")
    shells.run("bash", "echo hi; printf x")
    shells.run("bash", "X=1 echo hi")
    shells.run("bash", "f() { echo hi; }; f")
    shells.run("bash", "uv() { :; }; uv x")
    shells.run("bash", "command -v uv")
    shells.run("bash", "if true; then echo y; fi")
    shells.run("bash", 'source "{FILE}" && alias x')
    shells.run("sh", f'. "{CHECKOUT / "install.sh"}"; detect_os', env={"PATH": str(shells.bindir)})
    shells.run("zsh", "echo $SHELL")
    shells.run("bash", f"{tool} --x")
    shells.run("bash", "tool --x", env={"PATH": str(shells.bindir)})
    check_launch(
        [shells.paths["zsh"], "-f", "-c", "echo $SHELL"],
        env=None,
        cwd=None,
        policy=shells.policy,
    )


@pytest.mark.parametrize(
    "script",
    [
        "$(uv)",
        "`uv`",
        "cat <(uv)",
        "eval uv",
        "case x in x) uv;; esac",
        "echo 'unclosed",
        "",
        "   ",
        "source /etc/profile",
    ],
)
def test_shell_scripts_refuse_what_the_guard_cannot_parse(shells: _Shells, script: str) -> None:
    with pytest.raises(AssertionError):
        shells.run("bash", script)


@pytest.mark.parametrize(
    "script",
    [
        "uv --version; uv() { :; }",
        "if false; then uv() { :; }; fi; uv sync",
        "while false; do uv() { :; }; done; uv",
        "{ uv() { :; }; }; uv",
        "(uv() { :; }); uv",
        "f() { uv() { :; }; }; f; uv",
    ],
)
def test_a_function_counts_only_after_its_top_level_definition(
    shells: _Shells, script: str
) -> None:
    """WR-01: commands are checked in order, and a nested or conditional definition never counts."""
    with pytest.raises(AssertionError):
        shells.run("bash", script)


def test_shell_scripts_refuse_a_shell_with_no_arguments(shells: _Shells) -> None:
    with pytest.raises(AssertionError):
        check_launch([shells.paths["bash"]], env=None, cwd=None, policy=shells.policy)


@pytest.mark.parametrize(
    "options",
    [
        ["-s", "{FILE}"],
        ["-es", "{FILE}"],
        ["-s"],
        ["--rcfile", "{FILE}", "-c", "uv x"],
        ["--init-file", "{FILE}", "-c", "echo hi"],
        ["--rcfile={FILE}", "-c", "echo hi"],
        ["--debugger", "-c", "echo hi"],
    ],
)
def test_shell_options_that_read_an_unchecked_script_are_refused(
    shells: _Shells, options: list[str]
) -> None:
    """WR-02: `-s` reads the script from stdin and an rc or init file runs before `-c`."""
    argv = [shells.paths["bash"], *(o.replace("{FILE}", str(shells.file)) for o in options)]
    with pytest.raises(AssertionError):
        check_launch(argv, env=None, cwd=None, policy=shells.policy)


def test_known_long_shell_options_still_reach_the_script_check(shells: _Shells) -> None:
    bash = shells.paths["bash"]
    argv = [bash, "--noprofile", "--norc", "-c", "echo hi"]
    check_launch(argv, env=None, cwd=None, policy=shells.policy)
    with pytest.raises(AssertionError):
        check_launch([*argv[:-1], "uv x"], env=None, cwd=None, policy=shells.policy)


def test_shell_no_exec_and_script_files(shells: _Shells, outside: Path) -> None:
    mentions_uv = shells.file.parent / "mentions-uv.sh"
    mentions_uv.write_text("uv --version\n")
    sh, bash = shells.paths["sh"], shells.paths["bash"]
    check_launch([sh, "-n", mentions_uv], env=None, cwd=None, policy=shells.policy)
    check_launch([bash, "-n", "-c", "uv"], env=None, cwd=None, policy=shells.policy)
    check_launch([bash, shells.file], env=None, cwd=None, policy=shells.policy)
    elsewhere = outside / "run.sh"
    elsewhere.write_text("echo hi\n")
    with pytest.raises(AssertionError):
        check_launch([bash, elsewhere], env=None, cwd=None, policy=shells.policy)


@pytest.mark.parametrize(
    "script",
    ["echo a;(uv x)", "(echo a);uv x", "true&&uv x", "echo a|uv x"],
)
def test_glued_operators_are_split_before_checking_refused(shells: _Shells, script: str) -> None:
    with pytest.raises(AssertionError):
        shells.run("bash", script)


@pytest.mark.parametrize(
    "script",
    ["f(){ echo hi;};f", "f () { echo hi; }; f", "(echo a);(echo b)", "echo a>/dev/null;echo b"],
)
def test_glued_operators_are_split_before_checking_allowed(shells: _Shells, script: str) -> None:
    shells.run("bash", script)


def test_stdbuf_wraps_a_checked_shell_script(shells: _Shells, outside: Path) -> None:
    stdbuf = _fake(outside, "stdbuf")
    wrapped = replace(shells.policy, utilities=frozenset({_real(stdbuf)}))
    sh = shells.paths["sh"]
    check_launch([stdbuf, "-oL", sh, "-c", "printf x"], env=None, cwd=None, policy=wrapped)
    with pytest.raises(AssertionError):
        check_launch([stdbuf, "-oL", sh, "-c", "uv x"], env=None, cwd=None, policy=wrapped)


@pytest.mark.parametrize(
    ("shell", "script"),
    [
        ("bash", "time . {FILE}"),
        ("bash", "time -p . {FILE}"),
        ("sh", "time . {FILE}"),
        ("zsh", "noglob . {FILE}"),
        ("zsh", "nocorrect . {FILE}"),
        ("bash", "2>&1 . {FILE}"),
        ("bash", "2>/dev/null . {FILE}"),
        ("bash", "<&0 . {FILE}"),
        ("bash", "2>&1 source {FILE}"),
    ],
)
def test_precommand_words_and_fd_redirections_are_skipped_allowed(
    shells: _Shells, shell: str, script: str
) -> None:
    shells.run(shell, script)


@pytest.mark.parametrize(
    ("shell", "script"),
    [
        ("bash", "time uv x"),
        ("bash", "time -p uv x"),
        ("bash", "time -o out true"),
        ("bash", "! time uv x"),
        ("zsh", "noglob uv x"),
        ("bash", "2>&1 uv x"),
        ("bash", "2>/dev/null uv x"),
    ],
)
def test_precommand_words_and_fd_redirections_are_skipped_refused(
    shells: _Shells, shell: str, script: str
) -> None:
    with pytest.raises(AssertionError):
        shells.run(shell, script)


@pytest.mark.parametrize(("shell", "word"), [("bash", "2"), ("zsh", "noglob")])
def test_precommand_words_and_fd_redirections_are_skipped_host_program_refused(
    shells: _Shells, outside: Path, shell: str, word: str
) -> None:
    _fake(outside, word)
    script = "2>&1 . {FILE}" if word == "2" else "noglob . {FILE}"
    with pytest.raises(AssertionError, match=f"host's {word}"):
        shells.run(shell, script, env={"PATH": str(outside)})


@pytest.mark.parametrize(
    ("shell", "script"),
    [
        ("bash", "trap 'uv x' EXIT"),
        ("bash", "trap 'echo hi' EXIT"),
        ("zsh", "emulate zsh -c 'uv x'"),
        ("zsh", "autoload -U compinit"),
        ("bash", "hash -p /bin/sh x"),
        ("bash", "alias echo=uv; echo x"),
        ("bash", "alias x='echo hi'"),
    ],
)
def test_string_running_builtins_are_refused(shells: _Shells, shell: str, script: str) -> None:
    with pytest.raises(AssertionError):
        shells.run(shell, script)


@pytest.mark.parametrize("script", ["alias", "alias x", "alias -p"])
def test_string_running_builtins_are_refused_but_alias_lookups_pass(
    shells: _Shells, script: str
) -> None:
    shells.run("bash", script)


def test_shell_builtins_never_hold_a_command_runner() -> None:
    runners = {
        "time",
        "noglob",
        "nocorrect",
        "eval",
        "exec",
        "trap",
        "emulate",
        "autoload",
        "hash",
        "alias",
    }
    assert SHELL_BUILTINS.isdisjoint(runners)


@pytest.mark.parametrize(
    ("shell", "script"),
    [
        ("bash", "PATH=/x:$PATH uv x"),
        ("bash", "export PATH=/x:$PATH; uv x"),
        ("bash", "PATH=/x sh {FILE}"),
        ("bash", "PATH+=:/x; uv x"),
        ("bash", "declare -x PATH=/x; uv x"),
        ("bash", "if true; then PATH=/x; fi; uv x"),
        ("zsh", "path=(/x $path); uv x"),
    ],
)
def test_path_assignments_are_refused(shells: _Shells, shell: str, script: str) -> None:
    _fake(shells.bindir, "uv")
    with pytest.raises(AssertionError, match="assigns PATH"):
        shells.run(shell, script, env={"PATH": str(shells.bindir)})


@pytest.mark.parametrize(
    "script",
    [
        "uv x",
        "echo $PATH",
        "printf '%s' \"$PATH\"",
        "X=$PATH:/y uv x",
        "MANPATH=/x uv x",
        "export MYPATH=/x; uv x",
    ],
)
def test_path_assignments_are_refused_but_reads_and_lookalikes_pass(
    shells: _Shells, script: str
) -> None:
    _fake(shells.bindir, "uv")
    shells.run("bash", script, env={"PATH": str(shells.bindir)})


# --- the wired guard: real subprocess.run through GuardedPopen (SPEC R6) ---


def _marker_fake(directory: Path, name: str) -> Path:
    """A fake that writes `<name>.ran` beside itself when it runs."""
    directory.mkdir(parents=True, exist_ok=True)
    program = directory / name
    program.write_text(f'#!/bin/sh\necho ran > "{directory}/{name}.ran"\n')
    program.chmod(0o755)
    return program


@pytest.fixture
def host_fakes(outside: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Marker-writing `uv`, `curl` and `gh` outside the base temp, first on PATH."""
    for name in ("uv", "curl", "gh"):
        _marker_fake(outside, name)
    monkeypatch.setenv("PATH", f"{outside}{os.pathsep}{os.environ['PATH']}")
    return outside


@pytest.mark.parametrize(
    "argv",
    [
        ["uv", "--version"],
        ["curl", "-V"],
        ["sh", "-c", "uv --version"],
        ["bash", "-c", "true && gh --version"],
        [str(LINUXBREW_PREFIX / "bin" / "brew"), "--version"],
    ],
    ids=["uv", "curl", "sh-c", "bash-c-chain", "linuxbrew-binary"],
)
def test_the_guard_refuses_host_programs_before_launch(argv: list[str], host_fakes: Path) -> None:
    with refused("host's"):
        subprocess.run(argv, check=False)
    assert list(host_fakes.glob("*.ran")) == []


def test_the_guard_runs_allowed_programs(tmp_path: Path) -> None:
    fake = tmp_path / "bin" / "tool"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\necho fake-ran\n")
    fake.chmod(0o755)
    script = tmp_path / "ok.sh"
    script.write_text("true\n")

    ran = subprocess.run([str(fake)], capture_output=True, text=True, check=False)
    assert ran.stdout == "fake-ran\n"
    assert subprocess.run(["sh", "-n", str(script)], check=False).returncode == 0
    assert subprocess.run([sys.executable, "-c", "pass"], check=False).returncode == 0


def test_the_guard_judges_symlinks_by_target(tmp_path: Path, host_fakes: Path) -> None:
    link = tmp_path / "friendly-name"
    link.symlink_to(host_fakes / "uv")
    with refused(re.escape(str(host_fakes / "uv"))):
        subprocess.run([str(link)], check=False)
    assert list(host_fakes.glob("*.ran")) == []


def test_the_guard_rejects_malformed_argv(host_fakes: Path) -> None:
    for refused_call in (
        lambda: subprocess.run([], check=False),
        lambda: subprocess.run(["sh", "-c", ""], check=False),
        lambda: subprocess.run("uv --version", check=False),
        lambda: subprocess.run("uv x", shell=True, check=False),
    ):
        with refused("the guard|host's uv"):
            refused_call()
    assert list(host_fakes.glob("*.ran")) == []
    done = subprocess.run("echo hi", shell=True, capture_output=True, text=True, check=False)
    assert done.stdout == "hi\n"


@pytest.mark.parametrize("script", ["echo a; uv x", "echo a | uv x", "echo a && uv x"])
def test_the_guard_checks_every_command_of_a_script(script: str, host_fakes: Path) -> None:
    with refused("host's uv"):
        subprocess.run(["bash", "-c", script], check=False)
    assert list(host_fakes.glob("*.ran")) == []
    done = subprocess.run(
        ["bash", "-c", "echo a; echo b"], capture_output=True, text=True, check=False
    )
    assert done.stdout == "a\nb\n"


def test_each_worker_installs_the_guard(tmp_path_factory: pytest.TempPathFactory) -> None:
    # Each xdist worker runs its own session fixture: the policy lives in the worker's module.
    assert subprocess.Popen is GuardedPopen
    assert launch_policy().allowed_root == tmp_path_factory.getbasetemp().resolve()


# --- the refusal registry: a refusal the code under test catches still fails the test ---


def _probe_version(argv: list[str]) -> str | None:
    """Production-shaped: a broad catch around a launch, as installer/version_status.py has."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=False).stdout
    except Exception:
        return None


def test_a_swallowed_refusal_still_fails_the_test(host_fakes: Path) -> None:
    assert _probe_version(["uv", "--version"]) is None
    assert list(host_fakes.glob("*.ran")) == []
    with pytest.raises(pytest.fail.Exception) as failure:
        fail_on_refusals()
    message = str(failure.value)
    assert "host's uv" in message
    assert "a broad except in the code under test caught a guard refusal" in message
    assert take_refusals() == ()


def test_the_refusal_check_runs_after_every_test(request: pytest.FixtureRequest) -> None:
    assert "refusals_fail_the_test" in request.fixturenames


def test_refused_consumes_only_what_its_block_raised(host_fakes: Path) -> None:
    record_refusal("an earlier refusal")
    with refused("host's uv"):
        subprocess.run(["uv"], check=False)
    assert take_refusals() == ("an earlier refusal",)

    with pytest.raises(pytest.fail.Exception), refused("host's uv"):
        pass
    assert take_refusals() == ()


# --- the socket guard: no internet socket and no name lookup in any test (SPEC R8) ---


def _connect_loopback() -> object:
    return socket.create_connection(("127.0.0.1", 9), timeout=1)


def _open_url() -> object:
    return urllib.request.urlopen("https://example.com", timeout=1)


def _default_socket() -> object:
    return socket.socket()


def _ipv6_socket() -> object:
    return socket.socket(socket.AF_INET6, socket.SOCK_STREAM)


_SOCKET_ATTEMPTS = [_connect_loopback, _open_url, _default_socket, _ipv6_socket]


@pytest.mark.parametrize("attempt", _SOCKET_ATTEMPTS, ids=lambda attempt: attempt.__name__)
def test_internet_sockets_are_refused_naming_the_test(
    attempt: Callable[[], object], request: pytest.FixtureRequest
) -> None:
    with pytest.raises(AssertionError) as error:
        attempt()
    assert nodeid_of(request) in str(error.value)
    recorded = take_refusals()
    assert len(recorded) == 1
    assert nodeid_of(request) in recorded[0]


def _fetch_or_none(url: str) -> bytes | None:
    """Production-shaped: a broad catch around a network call."""
    try:
        return urllib.request.urlopen(url, timeout=1).read()
    except Exception:
        return None


def test_a_swallowed_socket_refusal_still_fails_the_test() -> None:
    assert _fetch_or_none("https://example.com") is None
    with pytest.raises(pytest.fail.Exception) as failure:
        fail_on_refusals()
    assert "tried to resolve" in str(failure.value)
    assert take_refusals() == ()


def test_unix_sockets_still_work() -> None:
    left, right = socket.socketpair()
    with left, right:
        left.sendall(b"x")
        assert right.recv(1) == b"x"
    with socket.socket(socket.AF_UNIX):
        pass

    async def answer() -> int:
        return 42

    assert asyncio.run(answer()) == 42


async def test_a_textual_app_still_runs_under_the_socket_guard() -> None:
    async with App[None]().run_test() as pilot:
        await pilot.press("x")


def test_the_socket_block_holds_in_threads() -> None:
    caught: list[AssertionError] = []

    def attempt() -> None:
        try:
            _connect_loopback()
        except AssertionError as error:
            caught.append(error)

    worker = threading.Thread(target=attempt)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert len(caught) == 1
    assert len(take_refusals()) == 1


# --- the os launchers: os.system, os.exec*, os.spawn*, os.posix_spawn* use the allowlist ---


def _policy_check(argv: list[str], env: Mapping[str, str] | None) -> None:
    check_launch(argv, env=env, cwd=None, policy=launch_policy())


class _Recorder:
    """Stands in for an os launcher: remembers what it was called with, launches nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> None:
        self.calls.append(args)


def _launcher(name: str) -> Callable[..., Any]:
    """An os launcher looked up at call time (the guard swaps it per test); pyright flags the
    deprecated ones when they are named directly."""
    return getattr(os, name)


_OS_LAUNCHES: dict[str, Callable[[str], object]] = {
    "system": lambda _fake: _launcher("system")("uv --version"),
    "spawnv": lambda fake: _launcher("spawnv")(os.P_WAIT, fake, [fake]),
    "spawnl": lambda fake: _launcher("spawnl")(os.P_WAIT, fake, fake),
    "spawnvp": lambda _fake: _launcher("spawnvp")(os.P_WAIT, "uv", ["uv"]),
    "posix_spawn": lambda fake: os.posix_spawn(fake, [fake], dict(os.environ)),
    "posix_spawnp": lambda _fake: os.posix_spawnp("uv", ["uv"], dict(os.environ)),
}


@pytest.mark.parametrize("launch", sorted(_OS_LAUNCHES))
def test_os_launchers_refuse_host_programs(launch: str, host_fakes: Path) -> None:
    with refused("host's uv"):
        _OS_LAUNCHES[launch](str(host_fakes / "uv"))
    assert list(host_fakes.glob("*.ran")) == []


def test_bytes_arguments_are_decoded_before_the_check(outside: Path, tmp_path: Path) -> None:
    host = _marker_fake(outside, "uv")
    fake = _fake(tmp_path / "bin", "tool")
    recorder = _Recorder()
    execv = guarded_os_call("execv", recorder, _policy_check)
    with refused("host's uv"):
        execv(os.fsencode(host), [os.fsencode(host)])
    assert recorder.calls == []
    execv(os.fsencode(fake), [os.fsencode(fake)])
    assert recorder.calls == [(os.fsencode(fake), [os.fsencode(fake)])]

    spawn = guarded_os_call("posix_spawn", recorder, _policy_check)
    with refused("host's uv"):
        spawn(host, [host], dict(os.environ))
    assert len(recorder.calls) == 1
    spawn(fake, [str(fake)], dict(os.environ))
    assert len(recorder.calls) == 2


def _quiet_system(command: str) -> int | None:
    """Production-shaped: a broad catch around a launch."""
    try:
        return _launcher("system")(command)
    except Exception:
        return None


def test_a_swallowed_os_refusal_still_fails_the_test(host_fakes: Path) -> None:
    assert _quiet_system("uv --version") is None
    assert list(host_fakes.glob("*.ran")) == []
    with pytest.raises(pytest.fail.Exception) as failure:
        fail_on_refusals()
    assert "host's uv" in str(failure.value)
    assert take_refusals() == ()


@pytest.mark.parametrize("name", ["execv", "execve", "execvp", "execvpe"])
def test_exec_family_is_checked_before_the_original_runs(
    name: str, outside: Path, tmp_path: Path
) -> None:
    def operands(program: Path) -> tuple[Any, ...]:
        base = (str(program), [str(program)])
        return (*base, dict(os.environ)) if name.endswith("e") else base

    host = _marker_fake(outside, "uv")
    fake = _fake(tmp_path / "bin", "tool")
    recorder = _Recorder()
    wrapped = guarded_os_call(name, recorder, _policy_check)
    with refused("host's uv"):
        wrapped(*operands(host))
    assert recorder.calls == []
    wrapped(*operands(fake))
    assert recorder.calls == [operands(fake)]
    # inside a test the real launchers are the wrappers; execl* reaches execv through os's globals
    assert os.execv.__qualname__.startswith("guarded_os_call.")
    assert os.execl.__globals__["execv"] is os.execv


def test_allowed_os_launches_run(tmp_path: Path) -> None:
    fake = str(_fake(tmp_path / "bin", "tool"))
    assert _launcher("system")("echo hi") == 0
    pid = os.posix_spawn(fake, [fake], dict(os.environ))
    assert os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]) == 0


def test_the_os_wrappers_are_idempotent(tmp_path: Path) -> None:
    fake = _fake(tmp_path / "bin", "tool")
    recorder = _Recorder()
    wrapped = guarded_os_call("posix_spawn", recorder, _policy_check)
    for _ in range(2):
        wrapped(str(fake), [str(fake)], dict(os.environ))
    assert len(recorder.calls) == 2
    assert subprocess.run([str(fake)], check=False).returncode == 0


def test_posix_spawn_with_an_inherited_environment_is_checked(
    outside: Path, tmp_path: Path
) -> None:
    """CPython's subprocess calls os.posix_spawn(path, argv, None) to inherit the environment
    (seen on the ubuntu CI runner): env=None is checked like any launch, never crashes."""
    host = _marker_fake(outside, "uv")
    fake = _fake(tmp_path / "bin", "tool")
    recorder = _Recorder()
    spawn = guarded_os_call("posix_spawn", recorder, _policy_check)
    with refused("host's uv"):
        spawn(str(host), [str(host)], None)
    assert recorder.calls == []
    spawn(str(fake), [str(fake)], None)
    assert recorder.calls == [(str(fake), [str(fake)], None)]
