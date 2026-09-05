"""The command runner seam: executors build argv, the runner performs the side effect."""

import subprocess
from collections.abc import Callable

# An executor calls a Runner with an argv list. The runner raises CommandError on failure.
Runner = Callable[[list[str]], None]
# A caller that needs to READ a command's answer rather than only run it.
OutputRunner = Callable[[list[str]], str]


class CommandError(RuntimeError):
    """A command exited non-zero (or could not be launched)."""

    def __init__(self, cmd: list[str], returncode: int, *, detail: str = "") -> None:
        self.cmd = list(cmd)
        self.returncode = returncode
        self.detail = detail
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


def run_output(cmd: list[str]) -> str:
    """Run argv and return its stdout, raising CommandError on non-zero exit.

    The capturing counterpart of run_command, for the two cases where inherited
    stdio is wrong: reading a tool's answer, and running a child while a caller
    (the Textual app) owns the terminal. The child's stderr is folded into the
    error so a failure still says why.
    """
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
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
