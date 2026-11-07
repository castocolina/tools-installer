import os
import pwd
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import setup
from tests.conftest import HOST_TOOLCHAIN, assert_not_host_toolchain, host_free_path
from tests.sandbox import (
    CHECKOUT,
    FORBIDDEN_PROGRAM_NAMES,
    LINUXBREW_PREFIX,
    UTILITY_NAMES,
    LaunchPolicy,
    build_launch_policy,
    check_launch,
)


def test_host_toolchain_dirs_are_off_path() -> None:
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    for entry in os.environ["PATH"].split(os.pathsep):
        if not entry:
            continue
        resolved = Path(os.path.realpath(entry))
        assert not resolved.is_relative_to(real_home)
        assert not resolved.is_relative_to(Path("/run/user"))
    assert "VOLTA_HOME" not in os.environ


def test_the_path_strip_survives_a_looping_entry(tmp_path: Path) -> None:
    loop = tmp_path / "loopbin"
    loop.symlink_to(loop)
    kept = host_free_path(f"{loop}{os.pathsep}/usr/bin").split(os.pathsep)
    assert "/usr/bin" in kept


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
