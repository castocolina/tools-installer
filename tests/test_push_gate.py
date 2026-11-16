"""The push gate (devtools/push_gate.py): ref parsing, refusals, the pre-commit run.

Every git query goes through an in-process fake; the only processes started are
`sys.executable` children (tests/sandbox.py forbids real git, make, uv and pre-commit).
"""

import io
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from devtools import push_gate
from devtools.push_gate import PRE_PUSH_ARGS, RefUpdate, main, parse_updates

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


def _clean_git() -> FakeGit:
    return FakeGit(
        {
            ("rev-parse", "--verify", "HEAD"): (0, f"{HEAD}\n".encode(), b""),
            ("rev-parse", "--verify", f"{HEAD}^{{commit}}"): (0, f"{HEAD}\n".encode(), b""),
        }
    )


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
    git = FakeGit({("rev-parse", "--verify", "HEAD"): (128, b"", b"fatal: bad object\n")})
    run = Recorder()
    assert main(stdin=_stdin(_line()), git=git, run=run, which=_which) == 1
    assert run.calls == []
    err = capsys.readouterr().err
    assert "git rev-parse --verify HEAD failed:" in err and "fatal: bad object" in err


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
