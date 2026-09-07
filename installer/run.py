"""The command runner seam: executors build argv, the runner performs the side effect."""

import os
import subprocess
from collections.abc import Callable, Collection, Mapping
from typing import Protocol, runtime_checkable

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


def run_command(cmd: list[str]) -> None:
    """Real Runner: run argv, raise CommandError on non-zero exit."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise CommandError(cmd, exc.returncode) from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc


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
