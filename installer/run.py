"""The command runner seam: executors build argv, the runner performs the side effect."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections import deque
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable

from installer.sanitize import sanitize_log_line

# An executor calls a Runner with an argv list. The runner raises CommandError on failure.
Runner = Callable[[list[str]], None]
# A caller that needs to READ a command's answer rather than only run it.
OutputRunner = Callable[[list[str]], str]


@runtime_checkable
class MethodAwareRunner(Protocol):
    """Optional runner capability used to attribute method-ladder transitions."""

    def __call__(self, cmd: list[str]) -> None: ...

    def method_started(self, method: str) -> None: ...


class CommandError(RuntimeError):
    """A command exited non-zero (or could not be launched)."""

    def __init__(
        self, cmd: list[str], returncode: int, *, detail: str = "", stdout: str = ""
    ) -> None:
        self.cmd = list(cmd)
        self.returncode = returncode
        self.detail = detail
        self.stdout = stdout
        message = f"command failed ({returncode}): {' '.join(cmd)}"
        super().__init__(f"{message}\n{detail}" if detail else message)


class InteractiveTerminalUnavailable(RuntimeError):
    """An approved interactive command has no terminal from which to read."""


def run_command(cmd: list[str]) -> None:
    """Real Runner: run argv, raise CommandError on non-zero exit."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise CommandError(cmd, exc.returncode) from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc


def run_interactive_command(cmd: list[str]) -> None:
    """Run approved argv with the active terminal available for system prompts."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise InteractiveTerminalUnavailable
    run_command(cmd)


TIMEOUT_CODE = 124  # what GNU timeout(1) reports, so the number is readable


def run_output(cmd: list[str], *, timeout: float | None = None) -> str:
    """Run argv and return its stdout, raising CommandError on non-zero exit.

    The capturing counterpart of run_command, for the two cases where inherited
    stdio is wrong: reading a tool's answer, and running a child while a caller
    (the Textual app) owns the terminal. The child's stderr is folded into the
    error so a failure still says why.

    `timeout` bounds a QUERY — a command run to read an answer, where waiting
    forever is never the right behaviour. A caller that reads a tool's answer
    while a TUI owns the terminal has no recoverable input path if the child
    wedges (Textual holds the terminal in raw mode, so Ctrl+C arrives as a byte
    on a queue nobody is draining), so the bound belongs here rather than in an
    interrupt handler. It stays optional and unset by default: a side-effecting
    child (`pnpm add -g` of a Puppeteer-carrying package) legitimately takes
    minutes, and killing it half-way is worse than waiting.
    """
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CommandError(cmd, TIMEOUT_CODE, detail=f"timed out after {exc.timeout:g}s") from exc
    except subprocess.CalledProcessError as exc:
        raise CommandError(cmd, exc.returncode, detail=(exc.stderr or "").strip()) from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc
    return completed.stdout


def run_captured(cmd: list[str]) -> None:
    """Runner that keeps the child's stdio out of the caller's terminal.

    For side effects started while Textual owns the terminal: a child that
    inherits stdout/stderr writes its progress bars and postinstall output
    straight into the rendered frame.
    """
    run_output(cmd)


STREAM_DETAIL_LINES = 20

UNBUFFER_ENV_VAR = "PYTHONUNBUFFERED"
STDBUF_FLAG = "-oL"


def unbuffered_env() -> dict[str, str]:
    """Return os.environ with PYTHONUNBUFFERED set to "1".

    env is merged over os.environ (an override, never a replacement) so PATH
    and HOME survive. This unconditional rung applies to every streamed child.
    """
    return {**os.environ, UNBUFFER_ENV_VAR: "1"}


_INTERPRETER_NAME = re.compile(r"python(\d+(\.\d+)?)?")


def _is_python_child(cmd: list[str]) -> bool:
    """Return True when cmd is a Python interpreter invocation.

    Matched on the interpreter SHAPES that actually honour PYTHONUNBUFFERED:
    this process's own sys.executable, or a basename that is exactly `python`,
    `python3`, `python3.12` and nothing more. A prefix test would also exclude
    `pythonpy`, `python-lsp-server` or a wrapper script named `python-tool`
    from rung 2 — real non-Python binaries the env var does nothing for, so
    the tool this phase exists to unblock would silently keep bursting.

    The residual gap is in the safe direction, and stays best-effort: an
    interpreter this pattern misses (`uv run python ...` presents as `uv`; a
    `python3.14t` free-threaded build) is merely wrapped as well as
    env-configured, which is harmless — LD_PRELOAD survives the exec and the
    env var is set regardless. The point is to name the case rung 1 already
    covers so rung 2 does not double-wrap it, never to guess wider than that.
    """
    if not cmd:
        return False
    argv0 = cmd[0]
    return argv0 == sys.executable or _INTERPRETER_NAME.fullmatch(Path(argv0).name) is not None


def unbuffered_argv(cmd: list[str], stdbuf: str | None) -> list[str]:
    """Return cmd or a stdbuf-wrapped version if applicable.

    Return cmd unchanged when stdbuf is None or when _is_python_child(cmd) is
    True; otherwise return [stdbuf, STDBUF_FLAG, *cmd]. This never wraps a
    child the env var already covers. Only -oL is added: -eL would make
    diagnostics arrive LATER than they do today because stderr is folded into
    the same pipe by stderr=subprocess.STDOUT and C stderr is unbuffered by
    default.

    This returns a list to LAUNCH, and the caller keeps its own cmd for
    anything a human will read.
    """
    if stdbuf is None or _is_python_child(cmd):
        return cmd
    return [stdbuf, STDBUF_FLAG, *cmd]


class StreamingRunner:
    """Runner that feeds a live log widget while the child still runs.

    Exists beside run_captured rather than replacing it: the console path
    still wants a blocking, non-streaming runner. emit is a required
    constructor argument so every line is attributed to a tool (D-05.2).

    bufsize=1 line-buffers the PARENT's reads; it cannot make a child
    line-buffer its own writes. The parent also tries, best-effort, to force
    the child to line-buffer its own writes:

    - Rung 1, unconditional: PYTHONUNBUFFERED=1 in every streamed child's
      environment. Reaches any CPython child.
    - Rung 2, opt-in and availability-gated: stdbuf -oL wraps the child's
      argv when the caller asked for it and the binary is on PATH. Reaches a
      dynamically-linked stdio child, and — because stdbuf works by installing
      LD_PRELOAD — that child's own grandchildren, making it useful for a
      curl | sh installer that shells out repeatedly. Silently skipped when
      stdbuf is absent.

    What neither rung reaches: a statically-linked Go or Rust binary doing its
    own buffering, a child re-exec'd through sudo (the loader drops LD_PRELOAD
    across the setuid boundary), or any host with no stdbuf at all. A vendor
    installer that detects a non-TTY (pnpm, SDKMAN, most progress-bar-drawing
    scripts) still block-buffers on its side, so the streaming guarantee is
    still "as live as the child allows", now with the parent having done what
    it safely can. This module is never the thing that batches output.
    """

    def __init__(
        self,
        emit: Callable[[str, str], None],
        *,
        unbuffer: bool = False,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._emit = emit
        self._tool_id: str | None = None
        self._stdbuf: str | None = which("stdbuf") if unbuffer else None

    def set_tool(self, tool_id: str) -> None:
        self._tool_id = tool_id

    def _current(self) -> str:
        if self._tool_id is None:
            raise RuntimeError("StreamingRunner.set_tool must be called before running a command")
        return self._tool_id

    def method_started(self, method: str) -> None:
        self._emit(self._current(), f"-- trying {method} --")

    def __call__(self, cmd: list[str]) -> None:
        """Run argv, emit each line as it arrives, raise CommandError on failure.

        No timeout: a side-effecting install child must be allowed to take
        minutes, matching run_output. bufsize=1 line-buffers the PARENT's
        reads; the child is pushed toward line-buffering its own writes by
        unbuffered_env() and, when opted in and available, a stdbuf -oL
        prefix — see the class docstring for what each rung reaches and what
        neither does. Best-effort, not a guarantee: a child that block-buffers
        past both rungs still bursts at exit.
        """
        launch_argv = unbuffered_argv(cmd, self._stdbuf)
        env = unbuffered_env()

        def popen_with_env(argv: list[str]) -> subprocess.Popen[str]:
            return subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                # D-10: the child gets its own session, so it has no
                # controlling terminal. A vendor installer that prompts on
                # /dev/tty fails fast instead of blocking on input nobody
                # can deliver while Textual owns the terminal. Note: the
                # child no longer receives the terminal's SIGINT/SIGHUP
                # (accepted — Textual holds the terminal in raw mode).
                start_new_session=True,
            )

        try:
            proc = popen_with_env(launch_argv)
        except OSError as exc:
            # If the wrapped argv failed and it was different from the caller's
            # argv, retry once with the caller's unwrapped argv. This handles
            # the case where stdbuf was resolved at construction but vanished by
            # launch time (a brew uninstall coreutils mid-run, a PATH entry
            # unmounted). Popen raised before the target command started, so a
            # retry is safe and only here.
            if launch_argv is not cmd:
                try:
                    proc = popen_with_env(cmd)
                except OSError as retry_exc:
                    # Both attempts failed. `retry_exc.__context__` is already
                    # `exc` — Python chains implicitly for an exception raised
                    # while another is being handled — so the traceback keeps
                    # WHY the wrapper broke without assigning __context__ by
                    # hand. The detail repeats both in the text a user reads,
                    # because the traceback is not on screen and "127" alone
                    # cannot say which of the two launches is the real problem.
                    raise CommandError(
                        cmd,
                        127,
                        detail=(
                            f"wrapped launch failed: {exc}\nunwrapped retry failed: {retry_exc}"
                        ),
                    ) from retry_exc
            else:
                raise CommandError(cmd, 127) from exc

        tail: deque[str] = deque(maxlen=STREAM_DETAIL_LINES)
        stdout = proc.stdout
        try:
            if stdout is not None:
                for raw in stdout:
                    line = raw.rstrip("\n")
                    self._emit(self._current(), line)
                    tail.append(sanitize_log_line(line))
            returncode = proc.wait()
        finally:
            # Drain then reap. Read remaining stdout to EOF and wait; never
            # signal the child and never close the pipe out from under it.
            # Closing early would deliver EPIPE, which is termination by
            # another name. A raising emit leaves a live child whose unread
            # pipe (~64 KiB) fills, the child blocks in write, and a bare
            # wait never returns.
            try:
                if stdout is not None:
                    for _ in stdout:
                        pass
                    stdout.close()
            except OSError:
                pass
            proc.wait()
        if returncode != 0:
            raise CommandError(cmd, returncode, detail="\n".join(tail))


QUERY_TIMEOUT = 20.0


def run_query(
    cmd: list[str],
    *,
    timeout: float = QUERY_TIMEOUT,
    env: Mapping[str, str] | None = None,
    accept_codes: Collection[int] = (0,),
) -> str:
    """Run a bounded query and return stdout when the exit code is accepted.

    `env` is merged over `os.environ` (an override, never a replacement) so
    PATH and HOME survive. `accept_codes` lets a caller treat pnpm's
    exit-1-with-JSON as success. Every manager query in this phase goes
    through this function; nothing else calls subprocess outside this module.
    """
    merged = None if env is None else {**os.environ, **env}
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandError(cmd, TIMEOUT_CODE, detail=f"timed out after {exc.timeout:g}s") from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc
    if completed.returncode in accept_codes:
        return completed.stdout
    raise CommandError(
        cmd,
        completed.returncode,
        detail=(completed.stderr or "").strip(),
        stdout=completed.stdout,
    )
