"""Black-box tests for scripts/prune-tmp-linux.sh.

Mirrors tests/test_install_sh.py's subprocess-against-real-script convention
-- the script's own contract (broad-path refusal, age-boundary matching, the
exact "deleted: N" line installer.daemon.last_run_summary parses) can only be
proven by actually running it, not by re-deriving its regex in Python.

find/rm are real (never stubbed): every path this file exercises is created
fresh under tmp_path, and --tmpdir always points inside it, so no test here
ever touches the real machine's tmp directory or real $HOME.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prune-tmp-linux.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")

# Filenames matching the script's own target regex:
# \.[0-9a-f]{16}-[0-9]{8}\.(so|node)
_MATCH_SO = ".0123456789abcdef-12345678.so"
_MATCH_NODE = ".fedcba9876543210-87654321.node"


def _run(*args: str, home: Path) -> "subprocess.CompletedProcess[str]":
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _touch(path: Path, *, age_minutes: float) -> None:
    path.write_bytes(b"x")
    stamp = time.time() - age_minutes * 60
    os.utime(path, (stamp, stamp))


def test_dry_run_reports_matches_without_deleting(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    target = tmpdir / _MATCH_SO
    _touch(target, age_minutes=15)
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--minutes", "10", home=home)

    assert result.returncode == 0
    assert "mode:     dry-run" in result.stdout
    assert "matches: 1" in result.stdout
    assert "deleted: 0" in result.stdout
    assert target.exists()


def test_apply_deletes_matching_orphans_and_prints_deleted_count(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    target = tmpdir / _MATCH_NODE
    _touch(target, age_minutes=15)
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--minutes", "10", "--apply", home=home)

    assert result.returncode == 0
    assert "deleted: 1" in result.stdout
    assert not target.exists()


def test_age_boundary_only_deletes_files_older_than_minutes(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    old = tmpdir / _MATCH_SO
    young = tmpdir / _MATCH_NODE
    _touch(old, age_minutes=15)
    _touch(young, age_minutes=2)
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--minutes", "10", "--apply", home=home)

    assert result.returncode == 0
    assert "deleted: 1" in result.stdout
    assert not old.exists()
    assert young.exists()


def test_near_miss_filenames_all_survive(tmp_path: Path) -> None:
    """Wrong extension, one hex digit short, no leading dot, and one
    directory deeper than -maxdepth 1 reaches -- none of these match the
    script's own regex, so all four must survive an --apply pass."""
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    wrong_ext = tmpdir / ".0123456789abcdef-12345678.txt"
    too_few_hex = tmpdir / ".0123456789abcde-12345678.so"
    no_leading_dot = tmpdir / "0123456789abcdef-12345678.so"
    nested_dir = tmpdir / "sub"
    nested_dir.mkdir()
    nested = nested_dir / _MATCH_SO
    near_misses = (wrong_ext, too_few_hex, no_leading_dot, nested)
    for path in near_misses:
        _touch(path, age_minutes=15)
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--minutes", "10", "--apply", home=home)

    assert result.returncode == 0
    assert "deleted: 0" in result.stdout
    for path in near_misses:
        assert path.exists()


@pytest.mark.parametrize("broad", ["/", "/var", "/private/var"])
def test_refuses_broad_system_paths(tmp_path: Path, broad: str) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", broad, "--apply", home=home)

    assert result.returncode != 0
    assert f"refusing broad path {broad}" in result.stderr
    assert "deleted" not in result.stdout


def test_refuses_the_home_directory_itself(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(home), "--apply", home=home)

    assert result.returncode != 0
    assert f"refusing broad path {home}" in result.stderr
    assert "deleted" not in result.stdout


@pytest.mark.parametrize("minutes", ["0", "-5", "abc"])
def test_minutes_rejects_non_positive_or_non_numeric_values(tmp_path: Path, minutes: str) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--minutes", minutes, home=home)

    assert result.returncode != 0
    assert "minutes must be a positive integer" in result.stderr


def test_files_outside_the_named_tmpdir_are_untouched(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    outside_dir = tmp_path / "elsewhere"
    outside_dir.mkdir()
    outside_file = outside_dir / _MATCH_SO
    _touch(outside_file, age_minutes=15)
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--minutes", "10", "--apply", home=home)

    assert result.returncode == 0
    assert "deleted: 0" in result.stdout
    assert outside_file.exists()
