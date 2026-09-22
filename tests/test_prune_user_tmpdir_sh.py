"""Black-box tests for scripts/prune-user-tmpdir.sh.

15.7-07 Task 1 wrote this suite BEFORE any refactor touched the script, so it
pins the CONTRACT the Task 2 extraction (scripts/lib/prune-tmp-common.sh) was
not allowed to break: flag grammar, broad-path refusal, age validation,
target-family matching, depth-1 traversal, and the `deleted: N` summary line
`installer.daemon.last_run_summary` parses. Task 2 then extracted the shared
core and updated exactly the two assertions licensed below -- every other
assertion in this file is byte-identical to what Task 1 first pinned against
the unmodified script.

Mirrors tests/test_install_sh.py's and tests/test_prune_tmp_linux_sh.py's
subprocess-against-the-real-script convention. find/fd/rm are real (never
stubbed): every path exercised here is created fresh under tmp_path, and
--tmpdir always points inside it or at a real, pre-existing system path used
ONLY to prove the refusal guard rejects it -- no fixture ever touches the
real $TMPDIR or $HOME.

Two licensed, deliberate behavior changes are reflected in this file's
current assertions (both discovered and resolved during 15.7-07):

1. D-01f (review HIGH cycle 3): the shared core converges the fd and
   find-fallback branches onto one `-mmin`/`--changed-before Nmin` duration
   semantics, replacing the find-fallback's old `-mtime +N` day-boundary
   truncation. test_days_to_minutes_conversion_deletes_25h_and_spares_23h
   and test_47h_49h_boundary_pair_both_deleted assert the CONVERGED behavior
   in both PATH configurations.
2. A pipeline-subshell scoping bug (Rule 1, discovered live while writing
   Task 1's suite): the unmodified script's `deleted: N` line always read 0
   regardless of real work done, because it piped into a function whose
   counters ran in a subshell. test_deleted_line_reports_the_actual_count
   asserts the FIXED, accurate count.

Two further characteristics of the script are frozen (unaffected by the
extraction, still true today):

1. `--tmpdir /`: the trailing-slash strip (`TMP_ROOT="${TMP_ROOT%/}"`)
   turns "/" into an EMPTY string before the refusal case list is ever
   consulted, so it is caught by the "not a directory" check, not the
   broad-path refusal -- even though "/" is literally one of the refusal
   patterns. See test_refuses_root_via_not_a_directory_quirk.
2. The is-a-directory check runs BEFORE the refusal check, so a
   refusal-list entry that is not a real directory on the host running this
   suite (e.g. /private/var/folders on Linux, which has no such path) is
   rejected via "not a directory", not "refusing broad path". The
   parametrized refusal test below skips any entry that is not a real
   directory on the CURRENT host rather than asserting a message the script
   cannot produce here -- the same "don't fail a suite for a tool/path the
   host legitimately lacks" principle this task already applies to
   fd-presence.
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
_REFUSAL_ENTRIES = (
    "$HOME",
    "/var",
    "/private/var",
    "/var/folders",
    "/private/var/folders",
    "$HOME/Library",
)

_FAMILY_FIXTURES: dict[str, tuple[str, str]] = {
    "dylib": ("file", "orphan.dylib"),
    "node": ("file", "orphan.node"),
    "gitid-stage": ("dir", "gitid-stage-abc123"),
    "gitid-e2e": ("dir", "gitid-e2e-def456"),
    "codex": ("dir", ".com.openai.codex.xyz"),
}


def _run(*args: str, home: Path, path: str = _PATH_WITH_FD) -> "subprocess.CompletedProcess[str]":
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


@pytest.mark.parametrize("shape", ["dot", "trailing-slash", "dotdot", "symlink"])
def test_refuses_non_canonical_spellings_of_home(tmp_path: Path, shape: str) -> None:
    """WR-09: the guard was a literal string compare, so `$HOME/.` walked
    through it and `rm -rf`'d matching entries inside HOME."""
    home = tmp_path / "home"
    home.mkdir()
    victim_dir = home / "gitid-stage-important"
    _touch_dir(victim_dir, age_hours=24 * 10)
    _touch_file(victim_dir / "payload.txt", age_hours=24 * 10)
    victim_file = home / "orphan.node"
    _touch_file(victim_file, age_hours=24 * 10)

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
    assert victim_dir.is_dir()
    assert (victim_dir / "payload.txt").exists()
    assert victim_file.exists()


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


def test_deleted_line_reports_the_actual_count(tmp_path: Path) -> None:
    """15.7-07 Task 2 (Rule 1 bug fix, licensed exception #2 alongside D-01f):
    the unmodified script fed matches into `delete_stream` through a PIPE
    (`{ list_fd0 ...; } | delete_stream`, lines 244-255). Bash runs every
    pipeline stage, including the last, in its own subshell unless
    `shopt -s lastpipe` is set, which the script never did, so
    `delete_stream`'s own `deleted=$((deleted + 1))` mutated a copy that was
    discarded the instant the pipeline exited -- the deletions were real
    but the shipped `deleted: N` line always read 0 regardless of real work
    done. Task 1's frozen characterization of that bug is
    test_deleted_line_is_stuck_at_zero_due_to_a_pipeline_subshell_bug in the
    15.7-07 Task 1 commit; the extraction fixes it by redirecting the NUL
    stream into delete_stream's stdin (input redirection, not a pipe) so
    delete_stream now runs in the wrapper's own shell and its counters are
    real. This is that same scenario, now asserting the FIXED count.
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
    for p in fixtures.values():
        assert not p.exists()
    assert int(match.group(1)) == len(_FAMILY_FIXTURES)
    assert survivor.exists()


# --- Age semantics: D-01f convergence, pinned in BOTH PATH configurations ---


@pytest.mark.parametrize(
    "path_config",
    [
        pytest.param(_PATH_WITH_FD, id="with-fd"),
        pytest.param(_PATH_WITHOUT_FD, id="without-fd"),
    ],
)
def test_days_to_minutes_conversion_deletes_25h_and_spares_23h(
    tmp_path: Path, path_config: str
) -> None:
    """D-01f (review HIGH cycle 3, resolved by convergence): the shared core
    filters with `-mmin`/`--changed-before Nmin` on BOTH the fd and the
    find-fallback branch, never `-mtime`, so `--days 1` (converted to 1440
    minutes at the wrapper boundary) now means "older than 24h" identically
    whether or not `fd` is on PATH. Before the extraction this held only on
    the fd branch (test_fd_branch_deletes_25h_and_spares_23h,
    15.7-07 Task 1); the find-fallback branch used to SPARE this same 25h
    file until Task 2's `-mtime` -> `-mmin` conversion collapsed the two
    semantics into one.
    """
    if path_config is _PATH_WITH_FD and not _HAVE_FD:
        pytest.skip("fd not present on this host's real PATH")
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    old = tmpdir / "old.dylib"
    young = tmpdir / "young.dylib"
    _touch_file(old, age_hours=25)
    _touch_file(young, age_hours=23)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home, path=path_config)

    assert result.returncode == 0
    assert not old.exists()
    assert young.exists()


@pytest.mark.parametrize(
    "path_config",
    [
        pytest.param(_PATH_WITH_FD, id="with-fd"),
        pytest.param(_PATH_WITHOUT_FD, id="without-fd"),
    ],
)
def test_47h_49h_boundary_pair_both_deleted(tmp_path: Path, path_config: str) -> None:
    """Under the OLD `-mtime +1` find-fallback, a 47h-old file survived
    (only a 49h-old one was caught, due to the day-boundary truncation
    D-01f removes). Pinning this pair in BOTH configurations means a
    well-meaning "restore compatibility" edit that reintroduces `-mtime`
    into the shared core fails this test loudly rather than silently
    reopening the fd/find divergence.
    """
    if path_config is _PATH_WITH_FD and not _HAVE_FD:
        pytest.skip("fd not present on this host's real PATH")
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    at_47h = tmpdir / "at-47h.dylib"
    at_49h = tmpdir / "at-49h.dylib"
    _touch_file(at_47h, age_hours=47)
    _touch_file(at_49h, age_hours=49)

    result = _run("--tmpdir", str(tmpdir), "--days", "1", "--apply", home=home, path=path_config)

    assert result.returncode == 0
    assert not at_47h.exists()
    assert not at_49h.exists()
