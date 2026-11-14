import os
from pathlib import Path

import pytest

from installer.bun_globals import bun_dirs, method_bin_dir, resolve_bun
from installer.model import Method

_BUN_VARS = ("BUN_INSTALL", "BUN_INSTALL_BIN", "BUN_INSTALL_GLOBAL_DIR")


@pytest.fixture(autouse=True)
def scratch_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in _BUN_VARS:
        monkeypatch.delenv(name, raising=False)
    return home


def _plant_bun(directory: Path, *, executable: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "bun"
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755 if executable else 0o644)
    return path


def test_bun_dirs_follow_the_bun_install_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_home: Path
) -> None:
    assert bun_dirs() == (
        scratch_home / ".bun" / "bin",
        scratch_home / ".bun" / "install" / "global",
    )
    other = tmp_path / "other"
    assert bun_dirs(home=other) == (other / ".bun" / "bin", other / ".bun" / "install" / "global")

    monkeypatch.setenv("BUN_INSTALL", "/x")
    assert bun_dirs() == (Path("/x/bin"), Path("/x/install/global"))
    assert bun_dirs(home=other) == (Path("/x/bin"), Path("/x/install/global"))

    monkeypatch.setenv("BUN_INSTALL_BIN", "/y/bin")
    assert bun_dirs() == (Path("/y/bin"), Path("/x/install/global"))
    monkeypatch.delenv("BUN_INSTALL_BIN")
    monkeypatch.setenv("BUN_INSTALL_GLOBAL_DIR", "/z/global")
    assert bun_dirs() == (Path("/x/bin"), Path("/z/global"))

    monkeypatch.setenv("BUN_INSTALL", "")
    monkeypatch.setenv("BUN_INSTALL_GLOBAL_DIR", "")
    assert bun_dirs() == (
        scratch_home / ".bun" / "bin",
        scratch_home / ".bun" / "install" / "global",
    )

    monkeypatch.setenv("BUN_INSTALL", "~/custom")
    assert bun_dirs() == (
        scratch_home / "custom" / "bin",
        scratch_home / "custom" / "install" / "global",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BUN_INSTALL", "rel")
    bin_dir, global_dir = bun_dirs()
    assert bin_dir == tmp_path / "rel" / "bin"
    assert global_dir == tmp_path / "rel" / "install" / "global"
    assert bin_dir.is_absolute()


def test_resolve_bun_prefers_path_then_the_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_home: Path
) -> None:
    on_path = _plant_bun(tmp_path / "pathdir")
    in_bin = _plant_bun(scratch_home / ".bun" / "bin")
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert resolve_bun() == str(on_path)
    monkeypatch.setenv("PATH", "")
    assert resolve_bun() == str(in_bin)
    in_bin.chmod(0o644)
    assert resolve_bun() is None
    in_bin.unlink()
    assert resolve_bun() is None


def test_resolve_bun_never_returns_a_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _plant_bun(tmp_path / "rel")
    for path_value in ("rel", "rel::"):
        monkeypatch.setenv("PATH", path_value)
        assert resolve_bun() is None
    bin_dir = tmp_path / "binroot" / "bin"
    planted = _plant_bun(bin_dir)
    monkeypatch.setenv("BUN_INSTALL_BIN", str(bin_dir))
    for path_value in ("rel", "rel::"):
        monkeypatch.setenv("PATH", path_value)
        found = resolve_bun()
        assert found == str(planted)
        assert found is not None
        assert os.path.isabs(found)


def test_method_bin_dir_prefers_a_declared_dir_then_bun_then_none(scratch_home: Path) -> None:
    declared = Method("script", {"bin_dir": "~/.local/bin"})
    assert method_bin_dir(declared) == scratch_home / ".local" / "bin"
    assert method_bin_dir(Method("bun", {"npm_pkg": "x"})) == scratch_home / ".bun" / "bin"
    assert method_bin_dir(Method("node", {"npm_pkg": "x"})) is None
