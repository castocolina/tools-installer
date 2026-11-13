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
_UPDATE_TIMEOUT = 1800
_RESULT_PREFIXES = ("ok:", "skipped:", "failed:")
# Source: installer/guards.py SHIM_SENTINEL and REDIRECT_SENTINEL (this file cannot import it).
_SHIM_SENTINELS = (b"# tools-installer-ban-shim", b"# tools-installer-redirect-shim")
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


def _fit(existing: bytes, new: bytes, cap: int) -> bytes:
    """The newest whole lines of `existing` plus `new`, never more than `cap` bytes."""
    if len(new) > cap:  # one line over the cap: its newest bytes, still ending in a newline
        body = new.rstrip(b"\n")[-(cap - 1) :] if cap > 1 else b""
        return body.decode("utf-8", errors="ignore").encode("utf-8") + b"\n"
    kept: list[bytes] = []
    size = len(new)
    # Decode once, so a cut never lands inside a character; measure what is written back.
    for text in reversed(existing.decode("utf-8", errors="replace").split("\n")[:-1]):
        line = f"{text}\n".encode()
        if size + len(line) > cap:
            break
        kept.append(line)
        size += len(line)
    return b"".join(reversed(kept)) + new


def _append(log_path: Path, line: str, cap: int) -> None:
    """Append one line under the log lock; trim through a temp file when it would pass `cap`."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(f"{log_path}.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)  # blocking: held only for one short read-and-write
        new = line.encode("utf-8")
        existing = log_path.read_bytes() if log_path.exists() else b""
        if len(existing) + len(new) <= cap:
            with log_path.open("ab") as handle:
                handle.write(new)
            return
        temp = log_path.with_name(f"{log_path.name}.{os.getpid()}.tmp")
        temp.write_bytes(_fit(existing, new, cap))
        os.replace(temp, log_path)
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def _child_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ}
    env.update(_CHILD_ENV)
    return env


def _kill_group(pid: int, sig: signal.Signals) -> None:
    # A group already gone is the normal case for the SIGKILL, and still a timeout. macOS answers
    # EPERM instead of ESRCH when only zombies are left in the group.
    with contextlib.suppress(ProcessLookupError, PermissionError):
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


def _update(run_id: str, installer: str, uv: str) -> str:
    """Run the installer's own `--run-schedule` for one tool; its last result line is ours."""
    setup = Path(installer) / "setup.py"
    if not setup.is_file():
        return f"failed: installer not found at {setup}"
    if not (Path(uv).is_file() and os.access(uv, os.X_OK)):
        return f"failed: uv not found at {uv}"
    child = _run_child(
        [
            uv,
            "run",
            "--isolated",
            "--no-dev",
            "setup.py",
            "--run-schedule",
            run_id,
            "--parent-holds-run-lock",
        ],
        timeout=_UPDATE_TIMEOUT,
        cwd=Path(installer),
    )
    if child.problem == "timed out":
        return "failed: the update timed out"
    if child.problem is not None:
        return f"failed: installer {child.problem}"
    results = [
        line.strip()
        for line in child.out.decode("utf-8", errors="replace").splitlines()
        if line.strip().startswith(_RESULT_PREFIXES)
    ]
    if results and results[-1].startswith("failed:"):
        return _sanitize(results[-1])
    if child.code != 0:
        if results:
            return f'failed: installer exited {child.code} after "{_sanitize(results[-1])}"'
        stderr = child.err.decode("utf-8", errors="replace").strip().splitlines()
        reason = f": {_sanitize(stderr[-1])}" if stderr else ""
        return f"failed: installer exited {child.code}{reason}"
    return _sanitize(results[-1]) if results else "failed: no result line from the installer"


def _resolve(name: str, path_value: str) -> str | None:
    """The first real `name` on PATH: absolute entries only, never the installer's own shim.

    Like `guards.real_binary`: the sentinel, not the directory, marks a shim, so a real binary
    that lives in the managed bin dir stays resolvable.
    """
    for entry in path_value.split(os.pathsep):
        candidate = Path(entry) / name
        if not (candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK)):
            continue
        try:
            with candidate.open("rb") as handle:
                head = handle.read(4096)
        except OSError:
            continue
        if not any(sentinel in head for sentinel in _SHIM_SENTINELS):
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
            "update": lambda: _update(run_id, options["--installer"], options["--uv"]),
        }
        try:
            result = runners[job]()
        except Exception as error:  # the log must carry a result line whatever happened
            result = f"failed: {type(error).__name__}: {_sanitize(str(error))}"
        emit(result)
    return 1 if result.startswith("failed:") else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
