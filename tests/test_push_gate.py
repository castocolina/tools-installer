"""The push gate (devtools/push_gate.py): ref parsing, refusals, the pre-commit run.

Every git query goes through an in-process fake; the only processes started are
`sys.executable` children (tests/sandbox.py forbids real git, make, uv and pre-commit).
"""

import contextlib
import io
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from devtools import push_gate
from devtools.push_gate import (
    GATE_READ_PATHSPECS,
    PRE_PUSH_ARGS,
    RefUpdate,
    main,
    parse_updates,
    run_forwarding_signals,
)

HEAD = "a" * 40
OTHER = "b" * 40
ZEROS = "0" * 40

_Reply = tuple[int, bytes, bytes]


class FakeGit:
    """A GitRunner answering by exact argv; any argv it was not given fails loudly."""

    def __init__(self, replies: dict[tuple[str, ...], _Reply] | None = None) -> None:
        self.replies = replies or {}
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        key = tuple(args)
        self.calls.append(key)
        assert key in self.replies, f"unexpected git call: {key}"
        code, out, err = self.replies[key]
        return subprocess.CompletedProcess(list(key), code, out, err)


class Recorder:
    """Stands in for run_forwarding_signals and remembers its argv."""

    def __init__(self, status: int = 0) -> None:
        self.status = status
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return self.status


def _which(name: str) -> str | None:
    return f"/usr/bin/{name}"


def _line(local_sha: str = HEAD, remote_sha: str = OTHER, ref: str = "refs/heads/main") -> str:
    return f"{ref} {local_sha} {ref} {remote_sha}\n"


def _stdin(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode())


UNMERGED = ("diff", "--name-only", "--diff-filter=U", "-z")
STAGED = ("diff", "--cached", "--name-only", "-z")
INTENT = ("diff", "--name-only", "--no-renames", "--diff-filter=A", "-z")
HIDDEN = ("ls-files", "-v", "-z")
UNTRACKED = ("ls-files", "--others", "--exclude-standard", "-z")
GATE_READ = ("--glob-pathspecs", "ls-files", "--others", "-z", "--", *GATE_READ_PATHSPECS)
CONFIG = ("diff", "--name-only", "-z", "--", ".pre-commit-config.yaml", "pyproject.toml", "uv.lock")
GATE_HEADER = "the gates read these untracked files, even when git ignores them:"
OTHER_HEADER = "these untracked files can change what the gates see:"
QUERIES = {
    "unmerged": UNMERGED,
    "staged": STAGED,
    "intent": INTENT,
    "hidden": HIDDEN,
    "untracked": UNTRACKED,
    "gate_read": GATE_READ,
    "config": CONFIG,
}


def _z(*names: str) -> _Reply:
    return (0, b"".join(f"{name}\0".encode() for name in names), b"")


def _git(pushed: str = HEAD, peeled: str | None = None, **replies: _Reply) -> FakeGit:
    """A clean tree with `pushed` as the pushed sha; overrides: unmerged, staged, untracked, ..."""
    table: dict[tuple[str, ...], _Reply] = {key: _z() for key in QUERIES.values()}
    table[("rev-parse", "--verify", "HEAD")] = (0, f"{HEAD}\n".encode(), b"")
    table[("rev-parse", "--verify", f"{pushed}^{{commit}}")] = (
        0,
        f"{peeled or pushed}\n".encode(),
        b"",
    )
    for name, reply in replies.items():
        table[QUERIES[name]] = reply
    return FakeGit(table)


def _clean_git() -> FakeGit:
    return _git()


def test_parse_updates_reads_every_line() -> None:
    text = (
        f"refs/heads/main {HEAD} refs/heads/main {OTHER}\n"
        f"refs/heads/new {HEAD} refs/heads/new {ZEROS}\n"
        f"(delete) {ZEROS} refs/heads/gone {OTHER}\n"
        "\n"
        f"refs/tags/v1 {OTHER} refs/tags/v1 {ZEROS}\n"
        f"HEAD {HEAD} refs/heads/feat {ZEROS}\n"
    )
    updates = parse_updates(text)
    assert [u.remote_ref for u in updates] == [
        "refs/heads/main",
        "refs/heads/new",
        "refs/heads/gone",
        "refs/tags/v1",
        "refs/heads/feat",
    ]
    assert [u.is_deletion for u in updates] == [False, False, True, False, False]
    assert updates[4] == RefUpdate("HEAD", HEAD, "refs/heads/feat", ZEROS)
    assert RefUpdate("x", "0" * 64, "y", OTHER).is_deletion  # SHA-256 repos too


def test_empty_stdin_runs_nothing() -> None:
    git, run = FakeGit(), Recorder()
    assert main(stdin=_stdin(""), git=git, run=run, which=_which) == 0
    assert git.calls == [] and run.calls == []


def test_a_deletion_only_push_runs_nothing() -> None:
    git, run = FakeGit(), Recorder()
    text = f"(delete) {ZEROS} refs/heads/gone {OTHER}\n"
    assert main(stdin=_stdin(text), git=git, run=run, which=_which) == 0
    assert git.calls == [] and run.calls == []


@pytest.mark.parametrize("status", (0, 1))
def test_a_clean_head_push_runs_the_pre_push_stage(
    status: int, capsys: pytest.CaptureFixture[str]
) -> None:
    run = Recorder(status)
    got = main(stdin=_stdin(_line()), git=_clean_git(), run=run, which=_which)
    assert got == status
    assert run.calls == [
        [
            "/usr/bin/pre-commit",
            "run",
            "--hook-stage",
            "pre-push",
            "--fail-fast",
            "--from-ref",
            "HEAD",
            "--to-ref",
            "HEAD",
        ]
    ]
    assert tuple(run.calls[0][1:]) == PRE_PUSH_ARGS
    err = capsys.readouterr().err
    assert ("make <target>" in err) == (status != 0)


@pytest.mark.parametrize("missing", ("pre-commit", "git"))
def test_a_missing_tool_fails_closed(missing: str, capsys: pytest.CaptureFixture[str]) -> None:
    run = Recorder()

    def which(name: str) -> str | None:
        return None if name == missing else _which(name)

    assert main(stdin=_stdin(_line()), git=_clean_git(), run=run, which=which) == 1
    assert run.calls == []
    err = capsys.readouterr().err
    assert missing in err and "make dev-setup" in err


def test_a_failing_git_query_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    git = _git(unmerged=(128, b"", b"fatal: bad object\n"))
    run = Recorder()
    assert main(stdin=_stdin(_line()), git=git, run=run, which=_which) == 1
    assert run.calls == []
    err = capsys.readouterr().err
    assert "git diff --name-only --diff-filter=U -z failed:" in err
    assert "fatal: bad object" in err


def test_the_module_imports_nothing_of_the_installer() -> None:
    source = Path(push_gate.__file__).read_text()
    assert "installer" not in {
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
    }


def test_a_malformed_line_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    run = Recorder()
    assert (
        main(stdin=_stdin("refs/heads/main only-two\n"), git=FakeGit(), run=run, which=_which) == 1
    )
    assert run.calls == []
    assert "malformed pre-push line" in capsys.readouterr().err


def test_the_defaultgit_runner_passes_argv_through_without_a_shell() -> None:
    done = push_gate.git_runner(sys.executable)(["-c", "print('a b')"])
    assert (done.returncode, done.stdout.strip()) == (0, b"a b")


def _refused(git: FakeGit, capsys: pytest.CaptureFixture[str], line: str | None = None) -> str:
    run = Recorder()
    assert main(stdin=_stdin(line or _line()), git=git, run=run, which=_which) == 1
    assert run.calls == []
    return capsys.readouterr().err


def test_refusal_1_unmerged_paths(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(unmerged=_z("b.py", "a.py")), capsys)
    assert err.startswith("push refused:")
    assert "\n  a.py\n  b.py\n" in err
    assert "finish the merge" in err and "abort it (git merge --abort)" in err


def test_refusal_2_staged_changes(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(staged=_z("tests/z.py", "installer/a b.py")), capsys)
    assert "\n  installer/a b.py\n  tests/z.py\n" in err
    assert "commit them, or unstage them (git restore --staged" in err


def test_refusal_2b_intent_to_add_files(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(intent=_z("installer/helper.py")), capsys)
    assert "intent-to-add files are not committed:\n  installer/helper.py\n" in err
    assert "git add <file>" in err and "git rm --cached <file>" in err


def _ls_v(*entries: str) -> _Reply:
    return (0, b"".join(f"{entry}\0".encode() for entry in entries), b"")


@pytest.mark.parametrize("tag", ("S", "h", "s"))
def test_refusal_2c_hidden_edits(
    tag: str,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "a b.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    err = _refused(_git(hidden=_ls_v("H ok.py", f"{tag} a b.py")), capsys)
    assert "skip-worktree or assume-unchanged" in err and "\n  a b.py\n" in err
    assert "ok.py" not in err
    assert "git update-index --no-skip-worktree <file>" in err and "--no-assume-unchanged" in err


def test_a_sparse_checkout_skip_worktree_entry_absent_on_disk_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run = Recorder()
    git = _git(hidden=_ls_v("H ok.py", "S docs/absent.txt"))
    assert main(stdin=_stdin(_line()), git=git, run=run, which=_which) == 0
    assert len(run.calls) == 1


def test_order_hidden_beats_untracked(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "h.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    err = _refused(_git(hidden=_ls_v("S h.py"), untracked=_z("u.py")), capsys)
    assert "h.py" in err and "u.py" not in err


def test_refusal_3_untracked_files_in_two_parts(capsys: pytest.CaptureFixture[str]) -> None:
    git = _git(
        untracked=_z(
            "tests/data.json",
            "installer/new.py",
            "tests/sub/b c.py",
            "devtools/x.py",
            "pytest.ini",
            "conftest.py",
            ".planning/notes.md",
            ".planning/debug/x.log",
        ),
        gate_read=_z(
            "tests/sub/b c.py", "pytest.ini", "installer/new.py", "devtools/x.py", "conftest.py"
        ),
    )
    err = _refused(git, capsys)
    gate_part, other_part = err.split(OTHER_HEADER)
    assert GATE_HEADER in gate_part
    assert gate_part.split(GATE_HEADER)[1].splitlines()[1:6] == [
        "  conftest.py",
        "  devtools/x.py",
        "  installer/new.py",
        "  pytest.ini",
        "  tests/sub/b c.py",
    ]
    assert "commit them, or move them out of the repository" in gate_part
    assert other_part.splitlines()[1:2] == ["  tests/data.json"]
    assert "commit, stash, remove or ignore them" in other_part
    assert ".git/info/exclude" in other_part
    assert err.count("tests/data.json") == 1 and err.count("conftest.py") == 1
    assert ".planning" not in err
    assert UNTRACKED in git.calls and GATE_READ in git.calls


def test_refusal_4_unstaged_config_edit(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(config=_z(".pre-commit-config.yaml")), capsys)
    assert "commit or discard the edit (git restore <file>)" in err


@pytest.mark.parametrize("name", ("pyproject.toml", "uv.lock"))
def test_refusal_4_unstaged_environment_edit(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(config=_z(name)), capsys)
    assert f"environment lock has an unstaged edit:\n  {name}\n" in err


def test_refusal_5_pushed_commit_is_not_head(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(pushed=OTHER), capsys, _line(OTHER, ref="refs/heads/other"))
    assert "refs/heads/other" in err and OTHER[:12] in err
    assert "check out that branch and push from it" in err


def test_order_unmerged_beats_staged(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(unmerged=_z("a.py"), staged=_z("s.py")), capsys)
    assert "a.py" in err and "s.py" not in err


def test_order_staged_beats_untracked(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(staged=_z("s.py"), untracked=_z("u.py")), capsys)
    assert "s.py" in err and "u.py" not in err


def test_order_untracked_beats_not_head(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(pushed=OTHER, untracked=_z("u.py")), capsys, _line(OTHER))
    assert "u.py" in err and "check out that branch" not in err


def test_order_config_beats_not_head(capsys: pytest.CaptureFixture[str]) -> None:
    git = _git(pushed=OTHER, config=_z(".pre-commit-config.yaml"))
    err = _refused(git, capsys, _line(OTHER))
    assert "git restore <file>" in err


@pytest.mark.parametrize("name", ("conftest.py", "tox.ini"))
def test_an_untracked_root_file_is_refused(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(untracked=_z(name), gate_read=_z(name)), capsys)
    assert f"  {name}\n" in err


def test_untracked_planning_files_do_not_refuse() -> None:
    run = Recorder()
    git = _git(untracked=_z(".planning/notes.md", ".planning/debug/x.log"))
    assert main(stdin=_stdin(_line()), git=git, run=run, which=_which) == 0
    assert len(run.calls) == 1


def test_an_ignored_root_conftest_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(gate_read=_z("conftest.py")), capsys)
    assert "  conftest.py\n" in err
    assert "info/exclude" not in err and "remove or ignore" not in err


def test_ignored_gate_read_files_are_listed_sorted(capsys: pytest.CaptureFixture[str]) -> None:
    names = ("tests/sub/conftest.py", "GNUmakefile", "pytest.ini", "installer/local.py")
    err = _refused(_git(gate_read=_z(*names)), capsys)
    listed = [line.strip() for line in err.splitlines()[1:5]]
    assert listed == ["GNUmakefile", "installer/local.py", "pytest.ini", "tests/sub/conftest.py"]


def test_a_gate_read_file_is_never_advised_to_be_ignored(
    capsys: pytest.CaptureFixture[str],
) -> None:
    only_gate = _refused(_git(gate_read=_z("conftest.py")), capsys)
    assert "info/exclude" not in only_gate
    both = _refused(
        _git(untracked=_z("conftest.py", "data.json"), gate_read=_z("conftest.py")), capsys
    )
    gate_part, other_part = both.split(OTHER_HEADER)
    assert "info/exclude" not in gate_part
    assert ".git/info/exclude" in other_part


def test_the_gate_read_pathspecs_are_pinned_and_bounded() -> None:
    assert GATE_READ_PATHSPECS == (
        "conftest.py",
        "pytest.ini",
        ".pytest.ini",
        "tox.ini",
        "setup.cfg",
        ".coveragerc",
        "pyrightconfig.json",
        "ruff.toml",
        ".ruff.toml",
        "GNUmakefile",
        "makefile",
        ".shellcheckrc",
        ".python-version",
        "uv.toml",
        "installer/**/*.py",
        "tests/**/*.py",
        "devtools/**/*.py",
        "installer/**/ruff.toml",
        "installer/**/.ruff.toml",
        "tests/**/ruff.toml",
        "tests/**/.ruff.toml",
        "devtools/**/ruff.toml",
        "devtools/**/.ruff.toml",
        "installer/**/.bandit",
        "devtools/**/.bandit",
        "scripts/**/.shellcheckrc",
        "typings/**",
        ".claude/*.md",
        ".claude/skills/**",
    )
    assert len(GATE_READ_PATHSPECS) == 29
    literal_roots = ("installer/", "tests/", "devtools/", "scripts/", "typings/", ".claude/")
    assert all("/" not in p or p.startswith(literal_roots) for p in GATE_READ_PATHSPECS)


def test_an_ignored_file_outside_the_list_does_not_refuse() -> None:
    run = Recorder()  # an ignored .venv/x.py matches no pathspec, so both queries stay empty
    assert main(stdin=_stdin(_line()), git=_git(), run=run, which=_which) == 0
    assert len(run.calls) == 1


def test_a_failing_gate_read_query_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    fatal = (
        b"fatal: global 'literal' pathspec setting is incompatible"
        b" with all other global pathspec settings\n"
    )
    err = _refused(_git(gate_read=(128, b"", fatal)), capsys)
    assert "git --glob-pathspecs ls-files" in err and fatal.decode().strip() in err


@pytest.mark.parametrize(
    ("line", "pushed", "peeled"),
    (
        (f"refs/tags/v1 {OTHER} refs/tags/v1 {ZEROS}\n", OTHER, HEAD),
        (f"HEAD {HEAD} refs/heads/feat {ZEROS}\n", HEAD, HEAD),
    ),
)
def test_a_tag_or_head_refspec_on_head_passes(line: str, pushed: str, peeled: str) -> None:
    run = Recorder()
    git = _git(pushed=pushed, peeled=peeled)
    assert main(stdin=_stdin(line), git=git, run=run, which=_which) == 0
    assert len(run.calls) == 1


def test_a_deletion_with_a_dirty_tree_still_runs_nothing() -> None:
    git, run = _git(staged=_z("s.py")), Recorder()
    text = f"(delete) {ZEROS} refs/heads/x {OTHER}\n"
    assert main(stdin=_stdin(text), git=git, run=run, which=_which) == 0
    assert git.calls == [] and run.calls == []


def test_no_message_suggests_skipping_a_hook(capsys: pytest.CaptureFixture[str]) -> None:
    main(stdin=_stdin(_line()), git=_git(), run=Recorder(1), which=_which)
    texts = [capsys.readouterr().err]
    cases: tuple[dict[str, _Reply], ...] = (
        {"unmerged": _z("a")},
        {"staged": _z("a")},
        {"intent": _z("a")},
        {"untracked": _z("a"), "gate_read": _z("b")},
        {"config": _z(".pre-commit-config.yaml")},
        {"unmerged": (128, b"", b"fatal\n")},
    )
    for replies in cases:
        fake = _git()
        for name, reply in replies.items():
            fake.replies[QUERIES[name]] = reply
        texts.append(_refused(fake, capsys))
    texts.append(_refused(_git(pushed=OTHER), capsys, _line(OTHER)))
    assert all(t and "--no-verify" not in t and "SKIP=" not in t for t in texts)


def test_a_file_name_with_a_space_is_printed_intact(capsys: pytest.CaptureFixture[str]) -> None:
    err = _refused(_git(staged=(0, b"installer/a b.py\0", b"")), capsys)
    assert "\n  installer/a b.py\n" in err


# --- signal forwarding (D-17) -------------------------------------------------------------------

SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
FAKE_PRE_COMMIT = """
import os, signal, sys, time
log, started, mode = sys.argv[1:4]


def on_sigint(signum, frame):
    with open(log, "a") as handle:
        handle.write("SIGINT\\n")
    time.sleep(0.5)  # a second forwarded signal would land here and log again
    sys.exit(0 if mode == "zero" else 130)


signal.signal(signal.SIGINT, on_sigint)
with open(started + ".tmp", "w") as handle:
    handle.write(str(os.getpid()))
os.replace(started + ".tmp", started)
for _ in range(600):
    time.sleep(0.05)
sys.exit(99)
"""
GATE_CODE = (
    "import sys; from devtools.push_gate import run_forwarding_signals; "
    "sys.exit(run_forwarding_signals([sys.executable, *sys.argv[1:]]))"
)


def _wait_for(path: Path) -> None:
    deadline = time.monotonic() + 30
    while not path.exists():
        assert time.monotonic() < deadline, f"{path.name} never appeared"
        time.sleep(0.05)


def _signal_the_gate(
    tmp_path: Path, mode: str, signals: Sequence[signal.Signals]
) -> tuple[int, str, list[str]]:
    """Run the gate in its own group around a fake pre-commit, signal it, return its result."""
    fake, log, started = tmp_path / "fake_pre_commit.py", tmp_path / "log", tmp_path / "started"
    fake.write_text(FAKE_PRE_COMMIT)
    gate = subprocess.Popen(
        [sys.executable, "-c", GATE_CODE, str(fake), str(log), str(started), mode],
        process_group=0,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for(started)
        for index, sig in enumerate(signals):
            if index:
                time.sleep(0.2)
            os.killpg(gate.pid, sig)
        _, err = gate.communicate(timeout=30)
        lines = log.read_text().splitlines() if log.exists() else []
        return gate.returncode, err, lines
    finally:
        gate.kill()
        gate.wait()
        if started.exists():  # the fake's own group: close what the test opened
            with contextlib.suppress(ProcessLookupError):
                os.killpg(int(started.read_text()), signal.SIGKILL)


@pytest.mark.parametrize("sig", SIGNALS)
def test_a_group_signal_is_forwarded_once_as_sigint(tmp_path: Path, sig: signal.Signals) -> None:
    status, err, lines = _signal_the_gate(tmp_path, "one", [sig])
    assert status == 130
    assert lines == ["SIGINT"]
    assert "push interrupted: no ref was pushed." in err


def test_a_second_signal_is_ignored(tmp_path: Path) -> None:
    status, _, lines = _signal_the_gate(tmp_path, "one", [signal.SIGTERM, signal.SIGTERM])
    assert status != 0
    assert lines == ["SIGINT"]


def test_a_signalled_gate_never_exits_zero(tmp_path: Path) -> None:
    status, _, lines = _signal_the_gate(tmp_path, "zero", [signal.SIGTERM])
    assert lines == ["SIGINT"]
    assert status == 130


class _Child:
    def __init__(self, status: int = 0) -> None:
        self.pid = 4242
        self.status = status

    def wait(self) -> int:
        return self.status


@pytest.mark.parametrize("sig", SIGNALS)
@pytest.mark.parametrize("times", (1, 2))
def test_a_signal_in_the_spawn_window_is_forwarded_once_after_the_handle_exists(
    sig: signal.Signals, times: int
) -> None:
    forwards: list[tuple[int, int]] = []
    seen_inside_spawn: list[int] = []

    def spawn(argv: Sequence[str]) -> _Child:
        handler = signal.getsignal(sig)
        assert callable(handler)
        for _ in range(times):
            handler(sig, None)
        seen_inside_spawn.append(len(forwards))
        return _Child()

    status = run_forwarding_signals(
        ["x"], spawn=spawn, killpg=lambda pid, signum: forwards.append((pid, signum))
    )
    assert seen_inside_spawn == [0]
    assert forwards == [(4242, signal.SIGINT)]
    assert status == 130


def test_a_normal_child_status_passes_through() -> None:
    before = [signal.getsignal(sig) for sig in SIGNALS]
    assert run_forwarding_signals([sys.executable, "-c", "raise SystemExit(3)"]) == 3
    assert [signal.getsignal(sig) for sig in SIGNALS] == before


def test_a_child_killed_by_a_signal_maps_to_128_plus_the_number() -> None:
    assert run_forwarding_signals(["x"], spawn=lambda argv: _Child(-9)) == 137


def test_a_vanished_child_group_is_ignored_and_a_closed_terminal_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ClosedTerminal:
        def write(self, text: str) -> int:
            raise OSError("terminal gone")

        def flush(self) -> None:
            raise OSError("terminal gone")

    def gone(pid: int, signum: int) -> None:
        raise ProcessLookupError

    def spawn(argv: Sequence[str]) -> _Child:
        handler = signal.getsignal(signal.SIGHUP)
        assert callable(handler)
        handler(signal.SIGHUP, None)
        return _Child()

    monkeypatch.setattr(sys, "stderr", ClosedTerminal())
    assert run_forwarding_signals(["x"], spawn=spawn, killpg=gone) == 130
