"""The command runner seam: executors build argv, the runner performs the side effect."""

import subprocess
from collections.abc import Callable

# An executor calls a Runner with an argv list. The runner raises CommandError on failure.
Runner = Callable[[list[str]], None]


class CommandError(RuntimeError):
    """A command exited non-zero (or could not be launched)."""

    def __init__(self, cmd: list[str], returncode: int) -> None:
        self.cmd = list(cmd)
        self.returncode = returncode
        super().__init__(f"command failed ({returncode}): {' '.join(cmd)}")


def run_command(cmd: list[str]) -> None:
    """Real Runner: run argv, raise CommandError on non-zero exit."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise CommandError(cmd, exc.returncode) from exc
    except OSError as exc:
        raise CommandError(cmd, 127) from exc
