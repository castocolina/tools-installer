"""The pre-push gate: refuse a push whose tested tree is not the pushed commit, then check it.

git runs this as the `pre-push` hook (`python -m devtools.push_gate`) and writes one
`<local ref> <local sha> <remote ref> <remote sha>` line per pushed ref on stdin. Standard library
only, no `installer` import: the hook must work before the project's dependencies are importable.
"""

import contextlib
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import FrameType
from typing import BinaryIO, Protocol

GitRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[bytes]]

# Both refs HEAD and no --all-files: pre-commit then sets unstaged edits aside and restores them.
PRE_PUSH_ARGS: tuple[str, ...] = (
    "run",
    "--hook-stage",
    "pre-push",
    "--fail-fast",
    "--from-ref",
    "HEAD",
    "--to-ref",
    "HEAD",
)


# Config and plugin files the gates load, plus the gated sources; each entry is an exact root name
# or starts with a literal directory, so git never walks .venv/.
GATE_READ_PATHSPECS: tuple[str, ...] = (
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


class GitQueryError(Exception):
    """A git query exited non-zero; the gate fails closed."""


@dataclass(frozen=True)
class RefUpdate:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str

    @property
    def is_deletion(self) -> bool:
        return self.local_sha != "" and set(self.local_sha) == {"0"}


def parse_updates(text: str) -> list[RefUpdate]:
    """One update per non-blank stdin line; a malformed line raises ValueError (fail closed)."""
    updates: list[RefUpdate] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split(" ")
        if len(parts) != 4:
            raise ValueError(f"malformed pre-push line: {line!r}")
        updates.append(RefUpdate(*parts))
    return updates


def git_runner(git_path: str) -> GitRunner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run([git_path, *args], capture_output=True, check=False)

    return run


def _query(git: GitRunner, args: Sequence[str]) -> bytes:
    done = git(args)
    if done.returncode != 0:
        stderr = os.fsdecode(done.stderr).strip()
        raise GitQueryError(f"git {' '.join(args)} failed: {stderr}")
    return done.stdout


def _rev(git: GitRunner, rev: str) -> str:
    return os.fsdecode(_query(git, ["rev-parse", "--verify", rev])).strip()


def _names(out: bytes) -> list[str]:
    """Split `-z` output on NUL; names stay exactly as git reported them."""
    return [os.fsdecode(part) for part in out.split(b"\0") if part]


def _part(header: str, items: Sequence[str], fix: str) -> str:
    return header + "\n" + "".join(f"  {item}\n" for item in sorted(items)) + fix


def _untracked_message(git: GitRunner) -> str | None:
    # Root configs, conftest and data files change what the gates see; only .planning/ is exempt.
    untracked = {
        name
        for name in _names(_query(git, ["ls-files", "--others", "--exclude-standard", "-z"]))
        if not name.startswith(".planning/")
    }
    # An ignored gate-read file still changes what the gates see; no exclude option, so ignored
    # and non-ignored matches both come back (D-28).
    gate_read = set(
        _names(
            _query(
                git, ["--glob-pathspecs", "ls-files", "--others", "-z", "--", *GATE_READ_PATHSPECS]
            )
        )
    )
    parts: list[str] = []
    if gate_read:
        parts.append(
            _part(
                "the gates read these untracked files, even when git ignores them:",
                list(gate_read),
                "commit them, or move them out of the repository.",
            )
        )
    if untracked - gate_read:
        parts.append(
            _part(
                "these untracked files can change what the gates see:",
                list(untracked - gate_read),
                "commit, stash, remove or ignore them (.git/info/exclude keeps a local-only file"
                " that no gate reads out of the gate).",
            )
        )
    return "\n".join(parts) if parts else None


def _hidden_edits(git: GitRunner) -> list[str]:
    """Index entries flagged skip-worktree (`S`) or assume-unchanged (lowercase) that exist on disk.

    A sparse checkout flags absent files skip-worktree on purpose; only present ones can hide edits.
    """
    entries = os.fsdecode(_query(git, ["ls-files", "-v", "-z"])).split("\0")
    return [
        entry[2:]
        for entry in entries
        if (entry[:1] == "S" or entry[:1].islower()) and os.path.lexists(entry[2:])
    ]


def refusal(git: GitRunner, updates: Sequence[RefUpdate]) -> str | None:
    """The first refusal message, or None when the tested tree is the pushed commit."""
    checks: tuple[tuple[Sequence[str], str, str], ...] = (
        (
            ["diff", "--name-only", "--diff-filter=U", "-z"],
            "unmerged paths exist:",
            "finish the merge, or abort it (git merge --abort), then push again.",
        ),
        (
            ["diff", "--cached", "--name-only", "-z"],
            "staged changes are not committed:",
            "commit them, or unstage them (git restore --staged <file>), then push again.",
        ),
        (
            # Only intent-to-add entries differ as "added" between index and worktree; pre-commit
            # un-adds them for the run, so the gates would read files that are not in HEAD.
            ["diff", "--name-only", "--diff-filter=A", "-z"],
            "intent-to-add files are not committed:",
            "commit them (git add <file>), or drop the intent (git rm --cached <file>),"
            " then push again.",
        ),
    )
    for args, header, fix in checks:
        names = _names(_query(git, args))
        if names:
            return "push refused: " + _part(header, names, fix)
    hidden = _hidden_edits(git)
    if hidden:
        return "push refused: " + _part(
            "these files are marked skip-worktree or assume-unchanged, so the gates may test"
            " edits git hides:",
            hidden,
            "clear the flag (git update-index --no-skip-worktree <file> or --no-assume-unchanged"
            " <file>), then push again.",
        )
    message = _untracked_message(git)
    if message is not None:
        return "push refused: " + message
    edited = _names(_query(git, ["diff", "--name-only", "-z", "--", ".pre-commit-config.yaml"]))
    if edited:
        return "push refused: " + _part(
            "the gate config has an unstaged edit:",
            edited,
            "commit or discard the edit (git restore .pre-commit-config.yaml), then push again.",
        )
    head = _rev(git, "HEAD")
    elsewhere: list[str] = []
    for update in updates:
        pushed = _rev(git, update.local_sha + "^{commit}")  # peel a tag to its commit
        if pushed != head:
            elsewhere.append(f"{update.remote_ref} ({pushed[:12]})")
    if elsewhere:
        return "push refused: " + _part(
            "a pushed commit is not HEAD, so the gates would test a different tree:",
            elsewhere,
            "check out that branch and push from it.",
        )
    return None


class Child(Protocol):
    pid: int

    def wait(self) -> int: ...


def _spawn(argv: Sequence[str]) -> Child:
    # Own group: pre-commit restores its stash on SIGINT only, so the gate forwards SIGINT to it.
    return subprocess.Popen(list(argv), process_group=0, stdin=subprocess.DEVNULL)


def run_forwarding_signals(
    argv: Sequence[str],
    *,
    spawn: Callable[[Sequence[str]], Child] = _spawn,
    killpg: Callable[[int, int], None] = os.killpg,
) -> int:
    """Run argv; forward the first SIGINT, SIGTERM or SIGHUP once as SIGINT, never exit 0 then."""
    child: Child | None = None
    interrupted = forwarded = False

    def forward() -> None:
        nonlocal forwarded
        if child is not None and not forwarded:
            forwarded = True
            with contextlib.suppress(ProcessLookupError):
                killpg(child.pid, signal.SIGINT)

    def on_signal(signum: int, frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True
        forward()

    signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    saved = {sig: signal.getsignal(sig) for sig in signals}
    for sig in signals:
        signal.signal(sig, on_signal)
    try:
        # No signal mask around the spawn: the child would inherit it and could not be interrupted.
        child = spawn(argv)
        if interrupted:  # the signal landed before the handle existed
            forward()
        status = child.wait()
    finally:
        for sig, old in saved.items():
            signal.signal(sig, signal.SIG_DFL if old is None else old)
    if interrupted:
        with contextlib.suppress(OSError):  # the terminal may be gone after SIGHUP
            print("push interrupted: no ref was pushed.", file=sys.stderr)
    if status < 0:
        status = 128 - status
    return 130 if interrupted and status == 0 else status


def main(
    *,
    stdin: BinaryIO | None = None,
    git: GitRunner | None = None,
    run: Callable[[Sequence[str]], int] = run_forwarding_signals,
    which: Callable[[str], str | None] = shutil.which,
) -> int:
    data = (stdin if stdin is not None else sys.stdin.buffer).read()
    try:
        updates = parse_updates(data.decode("utf-8", "surrogateescape"))
    except ValueError as exc:
        print(f"push refused: {exc}", file=sys.stderr)
        return 1
    updates = [update for update in updates if not update.is_deletion]
    if not updates:
        return 0
    git_path, pre_commit_path = which("git"), which("pre-commit")
    if git_path is None or pre_commit_path is None:
        name = "git" if git_path is None else "pre-commit"
        print(f"push refused: {name} not found on PATH; run make dev-setup", file=sys.stderr)
        return 1
    try:
        message = refusal(git or git_runner(git_path), updates)
    except GitQueryError as exc:
        print(f"push refused: {exc}", file=sys.stderr)
        return 1
    if message is not None:
        print(message, file=sys.stderr)
        return 1
    status = run([pre_commit_path, *PRE_PUSH_ARGS])
    if status != 0:
        print(
            "push refused: a gate failed. Fix the gate named on the `make <target>` line above,"
            " re-run that target, then push again.",
            file=sys.stderr,
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
