"""Per-method-kind executors: build an argv and hand it to the injected runner.

Only command-based kinds live here (script, node, native package managers, brew, cask).
Download-based kinds (github_release, tarball) live in `installer.download`.
"""

import shlex
from collections.abc import Callable
from typing import cast

from installer.locations import applications_dir
from installer.model import Method
from installer.run import Runner


class ExecutorError(RuntimeError):
    """A method could not be turned into a runnable command."""


def require_str(method: Method, key: str) -> str:
    value = method.params.get(key)
    if not isinstance(value, str) or not value:
        raise ExecutorError(f"method '{method.kind}' is missing or empty required param '{key}'")
    return value


def _env_prefix(method: Method) -> str:
    """Shell-quoted `KEY=value` assignments for the script shell, sorted by key.

    Keys come only from the trusted registry, so they are not shell-quoted; values
    are. The prefix attaches to the shell (the right side of the `curl | shell`
    pipe), not to curl — in POSIX sh a pipeline component's assignments are local
    to that component, so the installer would otherwise never see them.
    """
    raw = method.params.get("env")
    if not isinstance(raw, dict):
        return ""
    env = cast(dict[str, object], raw)
    parts = [
        f"{key}={shlex.quote(str(value))}"
        for key, value in sorted(env.items(), key=lambda item: item[0])
    ]
    return " ".join(parts)


def _script(method: Method, runner: Runner) -> None:
    url = require_str(method, "url")
    shell = method.params.get("shell")
    shell = shell if isinstance(shell, str) and shell else "sh"
    prefix = _env_prefix(method)
    invoke = f"{prefix} {shlex.quote(shell)}" if prefix else shlex.quote(shell)
    pipeline = f"curl -fsSL -- {shlex.quote(url)} | {invoke}"
    runner(["sh", "-c", pipeline])


def _dnf(method: Method, runner: Runner) -> None:
    runner(["sudo", "dnf", "install", "-y", require_str(method, "package")])


def _apt(method: Method, runner: Runner) -> None:
    runner(["sudo", "apt-get", "install", "-y", require_str(method, "package")])


def _pacman(method: Method, runner: Runner) -> None:
    runner(["sudo", "pacman", "-S", "--noconfirm", "--needed", require_str(method, "package")])


def _brew(method: Method, runner: Runner) -> None:
    runner(["brew", "install", require_str(method, "formula")])


def _node(method: Method, runner: Runner) -> None:
    # pnpm only — bare npm is banned. `add -g` installs the package's CLI globally.
    runner(["pnpm", "add", "-g", require_str(method, "npm_pkg")])


def _sdkman(method: Method, runner: Runner) -> None:
    # `sdk` is a shell function defined by sourcing sdkman-init.sh, not a PATH
    # binary — it must be sourced in the same shell invocation that calls it.
    # The sdkman tool's own bootstrap runs with `?ci=true`, which persists
    # `sdkman_auto_answer=true` in ~/.sdkman/etc/config, so a candidate install
    # here does not hang on an interactive version-choice prompt.
    candidate = require_str(method, "candidate")
    version = method.params.get("version")
    install = ["sdk", "install", candidate]
    if isinstance(version, str) and version:
        install.append(version)
    pipeline = f'. "$HOME/.sdkman/bin/sdkman-init.sh" && {shlex.join(install)}'
    runner(["bash", "-c", pipeline])


def _cask(method: Method, runner: Runner) -> None:
    # --appdir keeps the bundle in userspace; brew's default appdir is /Applications,
    # which the PRD forbids (corporate machines without sudo).
    runner(
        ["brew", "install", "--cask", f"--appdir={applications_dir()}", require_str(method, "cask")]
    )


EXECUTORS: dict[str, Callable[[Method, Runner], None]] = {
    "script": _script,
    "node": _node,
    "sdkman": _sdkman,
    "dnf": _dnf,
    "apt": _apt,
    "pacman": _pacman,
    "brew": _brew,
    "cask": _cask,
}


def execute(method: Method, runner: Runner) -> None:
    """Run the executor for `method.kind`, or raise ExecutorError if unsupported."""
    executor = EXECUTORS.get(method.kind)
    if executor is None:
        raise ExecutorError(f"no executor for method kind '{method.kind}'")
    executor(method, runner)
