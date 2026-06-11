import os
from pathlib import Path

import pytest

from installer.locations import applications_dir, bin_dir, ensure_dir, opt_dir, prepend_path


def test_bin_dir_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir(None) == tmp_path / ".local" / "bin"


def test_bin_dir_expands_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir("~/.local/bin") == tmp_path / ".local" / "bin"


def test_bin_dir_absolute_path_unchanged():
    assert bin_dir("/opt/tools/bin") == Path("/opt/tools/bin")


def test_bin_dir_bare_tilde_is_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir("~") == tmp_path


def test_ensure_dir_creates(tmp_path: Path):
    target = tmp_path / "a" / "b"
    result = ensure_dir(target)
    assert result == target
    assert target.is_dir()


def test_prepend_path_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", "/usr/bin")
    prepend_path(tmp_path)
    prepend_path(tmp_path)  # second call must not duplicate
    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0] == str(tmp_path)
    assert parts.count(str(tmp_path)) == 1


def test_prepend_path_drops_empty_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", "")
    prepend_path(tmp_path)
    assert os.environ["PATH"] == str(tmp_path)  # no trailing separator


def test_ensure_dir_idempotent(tmp_path: Path):
    target = tmp_path / "x" / "y"
    ensure_dir(target)
    assert ensure_dir(target) == target  # second call must not raise
    assert target.is_dir()


def test_opt_dir_is_under_local_opt():
    assert opt_dir("fd") == Path.home() / ".local" / "opt" / "fd"


def test_applications_dir_is_home_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert applications_dir() == tmp_path / "Applications"
