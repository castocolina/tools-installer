"""Per-method-kind executors: build an argv and hand it to the injected runner.

Only command-based kinds live here (script, native package managers, brew).
Download-based kinds (github_release, tarball) are implemented in a later plan.
"""

import shlex
from collections.abc import Callable

from installer.model import Method
from installer.run import Runner


class ExecutorError(RuntimeError):
    """A method could not be turned into a runnable command."""


def _require(method: Method, key: str) -> str:
    value = method.params.get(key)
    if not isinstance(value, str) or not value:
        raise ExecutorError(f"method '{method.kind}' is missing or empty required param '{key}'")
    return value


def _script(method: Method, runner: Runner) -> None:
    url = _require(method, "url")
    shell = method.params.get("shell")
    shell = shell if isinstance(shell, str) and shell else "sh"
    runner(["sh", "-c", f"curl -fsSL -- {shlex.quote(url)} | {shlex.quote(shell)}"])


def _dnf(method: Method, runner: Runner) -> None:
    runner(["sudo", "dnf", "install", "-y", _require(method, "package")])


def _apt(method: Method, runner: Runner) -> None:
    runner(["sudo", "apt-get", "install", "-y", _require(method, "package")])


def _pacman(method: Method, runner: Runner) -> None:
    runner(["sudo", "pacman", "-S", "--noconfirm", "--needed", _require(method, "package")])


def _brew(method: Method, runner: Runner) -> None:
    runner(["brew", "install", _require(method, "formula")])


EXECUTORS: dict[str, Callable[[Method, Runner], None]] = {
    "script": _script,
    "dnf": _dnf,
    "apt": _apt,
    "pacman": _pacman,
    "brew": _brew,
}


def execute(method: Method, runner: Runner) -> None:
    """Run the executor for `method.kind`, or raise ExecutorError if unsupported."""
    executor = EXECUTORS.get(method.kind)
    if executor is None:
        raise ExecutorError(f"no executor for method kind '{method.kind}'")
    executor(method, runner)
