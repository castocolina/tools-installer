import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple, cast

import pytest

import setup
from tests.conftest import HOST_TOOLCHAIN, assert_not_host_toolchain
from tests.sandbox import (
    CHECKOUT,
    FORBIDDEN_PROGRAM_NAMES,
    LINUXBREW_PREFIX,
    OVERRIDES_STASH,
    SHELL_BUILTINS,
    UTILITY_NAMES,
    LaunchPolicy,
    build_launch_policy,
    capture_home_overrides,
    check_launch,
    env_names_to_clear,
    host_free_path,
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


def test_a_node_family_binary_outside_tmp_is_never_run(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = Path(tempfile.mkdtemp(prefix="host-node-"))
    try:
        assert not outside.resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve())
        fake = outside / "node"
        fake.write_text("#!/bin/sh\necho forked\n")
        fake.chmod(0o755)

        with pytest.raises(AssertionError, match="host's node"):
            subprocess.run([str(fake), "--version"], check=False)

        monkeypatch.setenv("PATH", str(outside))
        with pytest.raises(AssertionError, match="host's node"):
            subprocess.run(["node", "--version"], check=False)
        with pytest.raises(AssertionError, match="host's node"):
            subprocess.run(["node"], env={"PATH": str(outside)}, check=False)

        inside = tmp_path / "node"
        inside.write_text(fake.read_text())
        inside.chmod(0o755)
        result = subprocess.run([str(inside)], capture_output=True, text=True, check=False)
        assert result.stdout == "forked\n"
    finally:
        shutil.rmtree(outside)


def test_assert_not_host_toolchain_only_guards_the_named_programs(tmp_path: Path) -> None:
    assert_not_host_toolchain(["/usr/bin/true"], env=None, cwd=None, allowed_root=tmp_path)
    assert_not_host_toolchain(
        ["node", "--version"], env={"PATH": ""}, cwd=None, allowed_root=tmp_path
    )
    assert_not_host_toolchain("brew shellenv", env=None, cwd=None, allowed_root=tmp_path)
    expected = frozenset({"node", "npm", "npx", "pnpm", "corepack", "volta", "bun", "yarn", "brew"})
    assert HOST_TOOLCHAIN.issuperset(expected)
    assert expected.issuperset(HOST_TOOLCHAIN)


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
    script = CHECKOUT / "scripts" / "detect-container-runtime.sh"
    check_launch([script, "--help"], env=None, cwd=None, policy=policy)

    # D-20: .venv tools are not checkout scripts. A scratch checkout keeps this deterministic.
    repo = outside / "repo"
    ruff = _fake(repo / ".venv" / "bin", "ruff")
    _fake(repo / "scripts", "ok.sh")
    scratch = replace(policy, checkout=repo.resolve())
    with pytest.raises(AssertionError, match="host's ruff"):
        check_launch([ruff], env=None, cwd=None, policy=scratch, missing_ok=False)
    check_launch([repo / "scripts" / "ok.sh"], env=None, cwd=None, policy=scratch)


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
    shells.run("bash", "command -v uv")
    shells.run("bash", "if true; then echo y; fi")
    shells.run("bash", 'source "{FILE}" && alias x')
    shells.run("sh", f'. "{CHECKOUT / "install.sh"}"; detect_os')
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


def test_shell_scripts_refuse_a_shell_with_no_arguments(shells: _Shells) -> None:
    with pytest.raises(AssertionError):
        check_launch([shells.paths["bash"]], env=None, cwd=None, policy=shells.policy)


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
