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
from devtools.push_gate import (
    GATE_READ_PATHSPECS,
    PRE_PUSH_ARGS,
    RefUpdate,
    main,
    parse_updates,
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
UNTRACKED = ("ls-files", "--others", "--exclude-standard", "-z")
GATE_READ = ("--glob-pathspecs", "ls-files", "--others", "-z", "--", *GATE_READ_PATHSPECS)
CONFIG = ("diff", "--name-only", "-z", "--", ".pre-commit-config.yaml")
GATE_HEADER = "the gates read these untracked files, even when git ignores them:"
OTHER_HEADER = "these untracked files can change what the gates see:"
QUERIES = {
    "unmerged": UNMERGED,
    "staged": STAGED,
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
    assert "commit or discard the edit (git restore .pre-commit-config.yaml)" in err


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
    assert "git restore .pre-commit-config.yaml" in err


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
    )
    assert len(GATE_READ_PATHSPECS) == 27
    literal_roots = ("installer/", "tests/", "devtools/", "scripts/", "typings/")
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
