"""Black-box tests for scripts/prune-user-tmpdir.sh -- written BEFORE any
refactor touches the script (15.7-07 Task 1), so this suite documents the
CONTRACT the Task 2 extraction must not break: flag grammar, broad-path
refusal, age validation, target-family matching, depth-1 traversal, and the
`deleted: N` summary line `installer.daemon.last_run_summary` parses.

Mirrors tests/test_install_sh.py's and tests/test_prune_tmp_linux_sh.py's
subprocess-against-the-real-script convention. find/fd/rm are real (never
stubbed): every path exercised here is created fresh under tmp_path, and
--tmpdir always points inside it or at a real, pre-existing system path used
ONLY to prove the refusal guard rejects it -- no fixture ever touches the
real $TMPDIR or $HOME.

Three frozen, host-dependent or pre-existing characteristics of the
UNMODIFIED script are pinned here, not "fixed" -- Task 2 is licensed to
change exactly TWO assertions in this file, and none other:

- D-01f's find-fallback age cutoff (test_find_fallback_spares_25h_and_deletes_49h)
- the pipeline-subshell `deleted: N` counter bug (test_deleted_line_is_stuck_at_zero_due_to_a_pipeline_subshell_bug),
  discovered live while writing this suite -- see that test's own docstring.

1. `--tmpdir /`: the script's own trailing-slash strip
   (`TMP_ROOT="${TMP_ROOT%/}"`, line 66) turns "/" into an EMPTY string
   before the refusal case list is ever consulted, so it is caught by the
   "not a directory" check (line 67), not the broad-path refusal -- even
   though "/" is literally one of the case patterns (line 72). Measured live
   against the unmodified script (see the 15.7-07 execution SUMMARY). See
   test_refuses_root_via_not_a_directory_quirk.
2. The is-a-directory check runs BEFORE the refusal check (line 67 vs line
   71), so a refusal-list entry that is not a real directory on the host
   running this suite (e.g. /private/var/folders on Linux, which has no such
   path) is rejected via "not a directory", not "refusing broad path". The
   parametrized refusal test below skips any entry that is not a real
   directory on the CURRENT host rather than asserting a message the
   unmodified script cannot produce here -- the same "don't fail a suite for
   a tool/path the host legitimately lacks" principle this task already
   applies to fd-presence.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prune-user-tmpdir.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")

_HAVE_FD = shutil.which("fd") is not None

# PATH configurations: WITH_FD is this test process's own real PATH (wherever
# fd/rg actually resolve, so HAVE_FD/HAVE_RG detection inside the script is
# genuine); WITHOUT_FD is restricted to /usr/bin:/bin, where neither tool
# resolves on the host this suite was authored against (fd/rg both live under
# ~/.local/bin here, never /usr/bin or /bin).
_PATH_WITH_FD = os.environ.get("PATH", "/usr/bin:/bin")
_PATH_WITHOUT_FD = "/usr/bin:/bin"

# The six broad-path refusal entries other than "/", which has its own
# dedicated test (see module docstring point 1). $HOME and $HOME/Library are
# fixture-controlled (created under tmp_path) so they exercise the refusal
# guard on every host; the /var family are real absolute system paths this
# suite cannot fabricate, so entries that do not exist on the CURRENT host
# are skipped rather than asserted against.
_REFUSAL_ENTRIES = ("$HOME", "/var", "/private/var", "/var/folders", "/private/var/folders", "$HOME/Library")

_FAMILY_FIXTURES: dict[str, tuple[str, str]] = {
    "dylib": ("file", "orphan.dylib"),
    "node": ("file", "orphan.node"),
    "gitid-stage": ("dir", "gitid-stage-abc123"),
    "gitid-e2e": ("dir", "gitid-e2e-def456"),
    "codex": ("dir", ".com.openai.codex.xyz"),
}


def _run(
    *args: str, home: Path, path: str = _PATH_WITH_FD
) -> "subprocess.CompletedProcess[str]":
    env = {"PATH": path, "HOME": str(home)}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _touch_file(path: Path, *, age_hours: float) -> None:
    path.write_bytes(b"x")
    stamp = time.time() - age_hours * 3600
    os.utime(path, (stamp, stamp))


def _touch_dir(path: Path, *, age_hours: float) -> None:
    path.mkdir(parents=True, exist_ok=True)
    stamp = time.time() - age_hours * 3600
    os.utime(path, (stamp, stamp))


def _make_family_fixtures(tmpdir: Path, *, age_hours: float) -> dict[str, Path]:
    made: dict[str, Path] = {}
    for name, (kind, filename) in _FAMILY_FIXTURES.items():
        p = tmpdir / filename
        if kind == "file":
            _touch_file(p, age_hours=age_hours)
        else:
            _touch_dir(p, age_hours=age_hours)
        made[name] = p
    return made


# --- Invocation and flags ---------------------------------------------------


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_exits_zero_and_prints_usage_first_line(tmp_path: Path, flag: str) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _run(flag, home=home)

    assert result.returncode == 0
    assert result.stdout.splitlines()[0] == "Usage: prune-user-tmpdir.sh [options]"


def test_unknown_option_exits_2_and_prints_usage_on_stderr(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--bogus", home=home)

    assert result.returncode == 2
    assert "unknown option: --bogus" in result.stderr
    assert "Usage: prune-user-tmpdir.sh [options]" in result.stderr


def test_days_flag_accepts_space_and_equals_forms(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    for args in (("--days", "1"), ("--days=1",)):
        result = _run("--tmpdir", str(tmpdir), *args, home=home)
        assert result.returncode == 0
        assert "days:     1" in result.stdout


def test_tmpdir_flag_accepts_space_and_equals_forms(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    for args in (("--tmpdir", str(tmpdir)), (f"--tmpdir={tmpdir}",)):
        result = _run(*args, home=home)
        assert result.returncode == 0
        assert f"target:   {tmpdir}" in result.stdout


def test_dry_run_deletes_nothing(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    paths = _make_family_fixtures(tmpdir, age_hours=100)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", home=home)

    assert result.returncode == 0
    for p in paths.values():
        assert p.exists()


# --- Refusal and validation --------------------------------------------------


@pytest.mark.parametrize("entry", _REFUSAL_ENTRIES)
def test_refuses_broad_paths(tmp_path: Path, entry: str) -> None:
    home = tmp_path / "home"
    home.mkdir()

    if entry == "$HOME":
        target = home
    elif entry == "$HOME/Library":
        target = home / "Library"
        target.mkdir()
    else:
        target = Path(entry)
        if not target.is_dir():
            pytest.skip(f"{target} is not a real directory on this host (macOS-only system path)")

    result = _run("--tmpdir", str(target), "--apply", home=home)

    assert result.returncode != 0
    assert f"refusing broad path {target}" in result.stderr
    assert "deleted" not in result.stdout


def test_refuses_root_via_not_a_directory_quirk(tmp_path: Path) -> None:
    """`--tmpdir /` is one of the script's own refusal case patterns, but the
    trailing-slash strip on line 66 turns "/" into an EMPTY string before
    that case statement is ever reached, so the unmodified script rejects it
    via the "not a directory" check (line 67) rather than the refusal guard
    (line 71). This is a pre-existing quirk, not something this task
    introduces or Task 2 is licensed to change -- it still refuses to
    operate (non-zero exit, nothing deleted), which is what T-15.7-46 cares
    about; only the message text differs from the other six refusal
    entries.
    """
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", "/", "--apply", home=home)

    assert result.returncode != 0
    assert "not a directory:" in result.stderr
    assert "deleted" not in result.stdout


def test_tmpdir_not_a_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    not_a_dir = tmp_path / "a-file"
    not_a_dir.write_text("x")

    result = _run("--tmpdir", str(not_a_dir), home=home)

    assert result.returncode != 0
    assert f"not a directory: {not_a_dir}" in result.stderr


def test_empty_tmpdir_env_with_no_flag_errors(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _run(home=home)  # no --tmpdir, and TMPDIR is absent from env

    assert result.returncode != 0
    assert "empty" in result.stderr
    assert "--tmpdir" in result.stderr


def test_trailing_slash_on_tmpdir_is_stripped_before_refusal(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", f"{home}/", "--apply", home=home)

    assert result.returncode != 0
    assert f"refusing broad path {home}" in result.stderr


@pytest.mark.parametrize("days", ["0", "-1", "abc"])
def test_days_rejects_non_positive_or_non_numeric(tmp_path: Path, days: str) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    result = _run("--tmpdir", str(tmpdir), "--days", days, home=home)

    assert result.returncode != 0
    assert "--days must be a positive integer" in result.stderr


# --- Matching and deletion ----------------------------------------------------


@pytest.mark.parametrize("family", sorted(_FAMILY_FIXTURES))
def test_each_family_deleted_when_older_than_threshold(tmp_path: Path, family: str) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    kind, filename = _FAMILY_FIXTURES[family]
    target = tmpdir / filename
    if kind == "file":
        _touch_file(target, age_hours=100)
    else:
        _touch_dir(target, age_hours=100)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home)

    assert result.returncode == 0
    assert not target.exists()


def test_newer_matching_file_survives(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    target = tmpdir / "young.dylib"
    _touch_file(target, age_hours=2)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home)

    assert result.returncode == 0
    assert target.exists()


def test_non_matching_file_survives(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    target = tmpdir / "orphan.txt"
    _touch_file(target, age_hours=100)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home)

    assert result.returncode == 0
    assert target.exists()


def test_matching_file_deeper_than_depth_one_survives(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    nested = tmpdir / "sub"
    nested.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    target = nested / "nested.dylib"
    _touch_file(target, age_hours=100)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home)

    assert result.returncode == 0
    assert target.exists()


def test_matching_file_in_sibling_directory_untouched(tmp_path: Path) -> None:
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    sibling = tmp_path / "elsewhere"
    sibling.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    target = sibling / "orphan.dylib"
    _touch_file(target, age_hours=100)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home)

    assert result.returncode == 0
    assert target.exists()


def test_deleted_line_is_stuck_at_zero_due_to_a_pipeline_subshell_bug(tmp_path: Path) -> None:
    """The unmodified script's `--apply` path streams matches into
    `delete_stream` through a pipe (`{ list_fd0 ...; } | delete_stream`,
    lines 244-255). Bash runs EVERY stage of a pipeline -- including the
    last -- in its own subshell unless `shopt -s lastpipe` is set, which
    this script never does. `delete_stream`'s `deleted=$((deleted + 1))`
    (line 224) therefore mutates a copy of `deleted` that is thrown away
    the instant the pipeline exits: the deletions themselves are real
    (`rm`/`rm -rf` run for real, verified live against this fixture), but
    the final `deleted: %s` line the caller reads back is always the
    parent shell's never-incremented `deleted=0` from line 208, no matter
    how many paths were actually removed.

    This is a genuine, independent bug -- not the D-01f age-semantics
    finding -- discovered live while writing this characterization suite
    (15.7-07 Task 1). It matters here because `installer.daemon.
    last_run_summary` parses exactly this line for the Policies "last run"
    detail, which today silently always reports 0 regardless of real
    work done. Task 2 is licensed to fix it (Rule 1: auto-fix bugs) as a
    SECOND exception alongside D-01f, because the shared core's own
    traversal helpers do not stream through a lossy subshell pipe, and
    reproducing this counting bug on purpose inside code Linux also uses
    would be actively worse than the status quo. See the 15.7-07 execution
    SUMMARY's Deviations section for the fix and its rationale.
    """
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    fixtures = _make_family_fixtures(tmpdir, age_hours=100)
    survivor = tmpdir / "young.dylib"
    _touch_file(survivor, age_hours=1)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home)

    assert result.returncode == 0
    match = re.search(r"^deleted: (\d+)$", result.stdout, re.MULTILINE)
    assert match is not None
    # The real deletions happened (proves the bug is in the COUNTER, not the
    # deletion logic itself) even though the reported count is stuck at 0.
    for p in fixtures.values():
        assert not p.exists()
    assert int(match.group(1)) == 0
    assert survivor.exists()


# --- Age semantics: record the divergence, do not paper over it (D-01f) ------


def test_fd_branch_deletes_25h_and_spares_23h(tmp_path: Path) -> None:
    if not _HAVE_FD:
        pytest.skip("fd not present on this host's real PATH")
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    old = tmpdir / "old.dylib"
    young = tmpdir / "young.dylib"
    _touch_file(old, age_hours=25)
    _touch_file(young, age_hours=23)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home, path=_PATH_WITH_FD)

    assert result.returncode == 0
    assert not old.exists()
    assert young.exists()


def test_find_fallback_spares_25h_and_deletes_49h(tmp_path: Path) -> None:
    """D-01f (review HIGH cycle 3): the CURRENT find-fallback branch
    (`find -mtime +"$DAYS"`) truncates age to whole 24h periods before
    comparing, so `--days 1` actually means "older than 2 days" on this
    branch -- it SPARES a 25h-old file that the fd branch (above) deletes,
    and only catches a 49h-old file. Task 2 is licensed to change this ONE
    assertion (and only this one) in this entire suite, once the shared core
    converges both branches on `-mmin` duration semantics; every other
    assertion in this file is frozen.
    """
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    spared = tmpdir / "spared.dylib"
    deleted = tmpdir / "deleted.dylib"
    _touch_file(spared, age_hours=25)
    _touch_file(deleted, age_hours=49)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home, path=_PATH_WITHOUT_FD)

    assert result.returncode == 0
    assert spared.exists()
    assert not deleted.exists()
