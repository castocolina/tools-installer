#!/usr/bin/env python3
# tools-installer-helper: schedule-runner
#
# /// script
# requires-python = ">=3.11"
# ///
#
# The requires-python constraint is load-bearing: `uv run --script` honors it whatever the
# caller's cwd, while a bare `python3` on macOS can be the Command Line Tools 3.9, which
# lacks the 3.11 APIs this file uses. A timer never runs from this repository's directory.
"""The program every scheduled timer runs: one job, one lock, one log.

Argv: `<job> [job args] --log PATH --lock PATH --cap-bytes N` with the jobs
`tmp-cleanup --script PATH [-- <script args>]`, `cache-cleanup` and
`update <tool> --installer CHECKOUT --uv UV`. The log id is `tmp-cleanup`,
`cache-cleanup` or `update-<tool>`.

Every run takes the cross-process run lock without blocking (a held lock is logged as
`skipped: busy` and nothing runs), appends `<iso> <id> start`, does the work, and appends
exactly one `<iso> <id> ok: ...|skipped: ...|failed: ...` line. Exit 0 for ok and skipped,
1 for failed, 2 for a usage error.

Standard library only, and it never imports `installer`: the unit starts it from a bare
interpreter, and a moved or deleted checkout must still leave a logged failure instead of a
silent timer. Tests import it in-process, which works from the test venv and has no bearing
on the production invocation.
"""

from __future__ import annotations

import contextlib
import datetime
import fcntl
import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from typing import NamedTuple

_TMP_TIMEOUT = 600
_MANAGER_TIMEOUT = 1200
# Source: installer/guards.py SHIM_SENTINEL (this file cannot import it).
_SHIM_SENTINEL = b"# tools-installer-ban-shim"
# Each manager's own prune command, in the UI's target order.
_MANAGERS = (
    ("uv", ("cache", "prune")),
    ("pnpm", ("store", "prune")),
    ("brew", ("cleanup",)),
    ("npm", ("cache", "verify")),
)
_KILL_GRACE = 10  # seconds a group gets between SIGTERM and SIGKILL, and for the last collect
# The house child policy; source: installer/run.py CHILD_ENV (this file cannot import it).
_CHILD_ENV = {"HOMEBREW_NO_SUDO": "1", "HOMEBREW_NO_AUTOREMOVE": "1"}
_TOOL_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
_DELETED = re.compile(r"^deleted: (\d+)\s*$", re.MULTILINE)
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_MAX_REASON = 300

Emit = Callable[[str], None]


class _Child(NamedTuple):
    code: int | None
    out: bytes
    err: bytes
    problem: str | None  # "timed out", or the sanitized reason the launch failed


class _UsageError(Exception):
    pass


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _sanitize(text: bytes | str) -> str:
    """One bounded line: decoded once, no ANSI, no control characters, whitespace collapsed."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    text = _CONTROLS.sub("", _ANSI.sub("", text))
    return " ".join(text.split())[:_MAX_REASON]


def _append(log_path: Path, line: str, cap: int) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as handle:
        handle.write(line.encode("utf-8"))


def _child_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ}
    env.update(_CHILD_ENV)
    return env


def _kill_group(pid: int, sig: signal.Signals) -> None:
    # A group already gone is the normal case for the SIGKILL, and still a timeout.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pid, sig)


def _run_child(argv: list[str], *, timeout: float, cwd: Path | None = None) -> _Child:
    """Run argv with no shell, in its own session; on a timeout kill the whole group."""
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_child_env(),
            cwd=cwd,
            start_new_session=True,
        )
    except OSError as error:
        return _Child(None, b"", b"", f"could not start: {_sanitize(str(error))}")
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid, signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=_KILL_GRACE)
        _kill_group(proc.pid, signal.SIGKILL)
        out = err = b""
        # A grandchild that escaped the group may still hold a pipe: bound the collect.
        try:
            out, err = proc.communicate(timeout=_KILL_GRACE)
        except subprocess.TimeoutExpired:
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()
        return _Child(None, out, err, "timed out")
    return _Child(proc.returncode, out, err, None)


@contextlib.contextmanager
def _run_lock(lock_path: Path, run_id: str) -> Generator[bool]:
    """Hold the run lock for the block; False when another run holds it."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC  # never O_TRUNC
    fd = os.open(lock_path, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        os.ftruncate(fd, 0)
        os.write(fd, f"{run_id} {os.getpid()} {_now()}\n".encode())
        try:
            yield True
        finally:
            os.ftruncate(fd, 0)
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _tmp_cleanup(script: str, forwarded: list[str]) -> str:
    name = Path(script).name
    child = _run_child([script, *forwarded], timeout=_TMP_TIMEOUT)
    if child.problem is not None:
        return f"failed: {name} {child.problem}"
    if child.code != 0:
        return f"failed: {name} exited {child.code}"
    counts = _DELETED.findall(child.out.decode("utf-8", errors="replace"))
    return f"ok: deleted {counts[-1]}" if counts else "ok: done"


def _resolve(name: str, path_value: str) -> str | None:
    """The first real `name` on PATH: absolute entries only, never the ban shim."""
    for entry in path_value.split(os.pathsep):
        candidate = Path(entry) / name
        if not (candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK)):
            continue
        try:
            with candidate.open("rb") as handle:
                head = handle.read(4096)
        except OSError:
            continue
        if _SHIM_SENTINEL not in head:
            return str(candidate)
    return None


def _cache_cleanup(emit: Emit) -> str:
    """Run each installed manager's own prune command; one failure never stops the others."""
    path_value = os.environ.get("PATH", "")
    passed: list[str] = []
    failure = ""
    for name, args in _MANAGERS:
        found = _resolve(name, path_value)
        if found is None:
            continue
        command = " ".join((name, *args))
        child = _run_child([found, *args], timeout=_MANAGER_TIMEOUT)
        if child.problem is None:
            emit(f"ran: {command} (exit {child.code})")
            reason = f"exited {child.code}"
        elif child.problem == "timed out":
            emit(f"ran: {command} (timed out)")
            reason = "timed out"
        else:
            emit(f"ran: {command} (could not start)")
            reason = "could not start"
        if child.problem is None and child.code == 0:
            passed.append(name)
        elif not failure:
            failure = f"{command} {reason}"
    if failure:
        return f"failed: {failure} ({', '.join(passed)} ok)" if passed else f"failed: {failure}"
    return f"ok: pruned {', '.join(passed)}" if passed else "ok: nothing to clean"


def _parse(argv: list[str]) -> tuple[str, str, dict[str, str], list[str]]:
    """The job, its log id, its options and the forwarded tail; _UsageError otherwise."""
    options: dict[str, str] = {}
    positional: list[str] = []
    forwarded: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            forwarded = argv[index + 1 :]
            break
        if arg.startswith("--"):
            if arg not in ("--log", "--lock", "--cap-bytes", "--script", "--installer", "--uv"):
                raise _UsageError(f"unknown option {arg}")
            if index + 1 >= len(argv):
                raise _UsageError(f"{arg} needs a value")
            options[arg] = argv[index + 1]
            index += 2
        else:
            positional.append(arg)
            index += 1
    job = positional[0] if positional else ""
    required = {
        "tmp-cleanup": ("--script",),
        "cache-cleanup": (),
        "update": ("--installer", "--uv"),
    }.get(job)
    if required is None:
        raise _UsageError(f"unknown job {job!r}")
    for name in ("--log", "--lock", "--cap-bytes", *required):
        if name not in options:
            raise _UsageError(f"{job} needs {name}")
    if not options["--cap-bytes"].isdigit() or int(options["--cap-bytes"]) < 1:
        raise _UsageError("--cap-bytes must be a positive integer")
    wanted = 2 if job == "update" else 1
    if len(positional) != wanted:
        raise _UsageError(f"{job} takes {wanted - 1} positional argument(s)")
    run_id = job
    if job == "update":
        if not _TOOL_ID.fullmatch(positional[1]):
            raise _UsageError(f"bad tool name {positional[1]!r}")
        run_id = f"update-{positional[1]}"
    return job, run_id, options, forwarded


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        job, run_id, options, forwarded = _parse(args)
    except _UsageError as error:
        print(f"schedule_runner: {error}", file=sys.stderr)
        return 2
    log_path = Path(options["--log"])
    cap = int(options["--cap-bytes"])

    def emit(text: str) -> None:
        _append(log_path, f"{_now()} {run_id} {text}\n", cap)

    with _run_lock(Path(options["--lock"]), run_id) as held:
        if not held:
            emit("skipped: busy")
            return 0
        emit("start")
        runners: dict[str, Callable[[], str]] = {
            "tmp-cleanup": lambda: _tmp_cleanup(options["--script"], forwarded),
            "cache-cleanup": lambda: _cache_cleanup(emit),
        }
        try:
            result = runners[job]()
        except Exception as error:  # the log must carry a result line whatever happened
            result = f"failed: {type(error).__name__}: {_sanitize(str(error))}"
        emit(result)
    return 1 if result.startswith("failed:") else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
