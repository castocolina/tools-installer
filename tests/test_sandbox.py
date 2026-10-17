import os
import pwd
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.conftest import HOST_TOOLCHAIN, assert_not_host_toolchain, host_free_path


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
