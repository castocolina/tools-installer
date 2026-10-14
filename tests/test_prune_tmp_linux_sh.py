"""Black-box tests for scripts/prune-tmp-linux.sh.

Mirrors tests/test_install_sh.py's subprocess-against-real-script convention
-- the script's own contract (broad-path refusal, age-boundary matching, the
exact "deleted: N" line installer.daemon.last_run_summary parses) can only be
proven by actually running it, not by re-deriving its regex in Python.

find/rm are real (never stubbed): every path this file exercises is created
fresh under tmp_path, and --tmpdir always points inside it, so no test here
ever touches the real machine's tmp directory or real $HOME.

15.7-07 Task 2 ADDS the cross-script assertions at the bottom of this file
(shared-core proof: one refusal guard demonstrably serving both wrappers, and
the shared library refusing to do anything when executed directly) -- every
assertion above this point is unmodified from plan 15.7-01.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prune-tmp-linux.sh"
MACOS_SCRIPT = ROOT / "scripts" / "prune-user-tmpdir.sh"
LIB_SCRIPT = ROOT / "scripts" / "lib" / "prune-tmp-common.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")

# Filenames matching the script's own target regex:
# \.[0-9a-f]{16}-[0-9]{8}\.(so|node)
_MATCH_SO = ".0123456789abcdef-12345678.so"
_MATCH_NODE = ".fedcba9876543210-87654321.node"


def _run(*args: str, home: Path, cwd: Path | None = None) -> "subprocess.CompletedProcess[str]":
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        cwd=None if cwd is None else str(cwd),
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


@pytest.mark.parametrize("shape", ["dot", "trailing-slash", "dotdot", "symlink"])
def test_refuses_non_canonical_spellings_of_home(tmp_path: Path, shape: str) -> None:
    """WR-09: the shared guard compared raw strings, so every non-canonical
    spelling of a refused directory passed straight through."""
    home = tmp_path / "home"
    home.mkdir()
    victim = home / _MATCH_SO
    _touch(victim, age_minutes=60)

    if shape == "dot":
        target = f"{home}/."
    elif shape == "trailing-slash":
        target = f"{home}/"
    elif shape == "dotdot":
        target = f"{home}/../{home.name}"
    else:
        link = tmp_path / "home-link"
        link.symlink_to(home)
        target = str(link)

    result = _run("--tmpdir", target, "--apply", home=home)

    assert result.returncode != 0
    # The wrapper strips one trailing slash before the guard runs, so the
    # message quotes that spelling rather than the raw argument.
    assert "refusing broad path" in result.stderr
    assert "deleted" not in result.stdout
    assert victim.exists()


@pytest.mark.parametrize("relative", [".", "./tmp", "tmp"])
def test_refuses_a_relative_tmpdir(tmp_path: Path, relative: str) -> None:
    """Lane-2 LOW-02: WR-09 made the broad-path guard canonicalize, but a
    relative root canonicalizes against whatever cwd the process happens to
    have. "." was therefore refused only because the cwd was $HOME, which is
    on the refusal list -- "./tmp" and a bare "tmp" resolve somewhere the
    list does not name, so the wrapper pruned the current directory's
    depth-1 matches. Reject a non-absolute root outright, BEFORE any
    canonicalization.
    """
    home = tmp_path / "home"
    home.mkdir()
    (home / "tmp").mkdir()
    victim_here = home / _MATCH_SO
    _touch(victim_here, age_minutes=60)
    victim_below = home / "tmp" / _MATCH_SO
    _touch(victim_below, age_minutes=60)

    result = _run("--tmpdir", relative, "--apply", home=home, cwd=home)

    assert result.returncode != 0
    assert f"tmpdir must be absolute: {relative}" in result.stderr
    assert "deleted" not in result.stdout
    assert victim_here.exists()
    assert victim_below.exists()


def test_refuses_a_dotdot_spelling_of_the_root_directory(tmp_path: Path) -> None:
    """`/usr/..` canonicalizes to `/` on Linux and macOS alike, and `/` is
    on the refusal list. (`/tmp/..` would be macOS-blind: there `/tmp` is a
    symlink to `/private/tmp`, so `/tmp/..` canonicalizes to `/private`,
    which the list does not name, and the refusal never fires.)"""
    home = tmp_path / "home"
    home.mkdir()
    result = _run("--tmpdir", "/usr/..", "--apply", home=home)
    assert result.returncode != 0
    assert "refusing broad path /usr/.." in result.stderr
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


# --- 15.7-07 Task 2: shared-core proof (D-01d) --------------------------------
#
# Both scripts now source scripts/lib/prune-tmp-common.sh (see the module
# docstring). These tests prove that sharing, not just assert each script's
# own behavior in isolation.


def _run_macos(*args: str, home: Path) -> "subprocess.CompletedProcess[str]":
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    return subprocess.run(
        ["bash", str(MACOS_SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_refusal_message_is_identical_in_shape_from_both_scripts(tmp_path: Path) -> None:
    """One shared `_prune_common_refuse_broad_path` guard serves both
    wrappers -- proved by running each script against the SAME broad path
    ($HOME, which is in both scripts' own refusal list, unlike "/" which
    scripts/prune-user-tmpdir.sh's own pre-existing trailing-slash-strip
    quirk routes to a different check entirely; see
    tests/test_prune_user_tmpdir_sh.py::test_refuses_root_via_not_a_directory_quirk)
    and comparing the refusal line each one prints.
    """
    home = tmp_path / "home"
    home.mkdir()

    linux_result = _run("--tmpdir", str(home), "--apply", home=home)
    macos_result = _run_macos("--tmpdir", str(home), "--apply", home=home)

    expected = f"refusing broad path {home}"
    assert linux_result.returncode != 0
    assert macos_result.returncode != 0
    assert expected in linux_result.stderr
    assert expected in macos_result.stderr


def test_shared_library_does_nothing_when_executed_directly(tmp_path: Path) -> None:
    """scripts/lib/prune-tmp-common.sh defines functions only (T-15.7-49): a
    stray direct execution must not traverse or delete anything, so it exits
    cleanly instead of running any of its own traversal/deletion logic.
    """
    result = subprocess.run(
        ["bash", str(LIB_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
