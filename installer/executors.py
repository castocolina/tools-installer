"""Per-method-kind executors: build an argv and hand it to the injected runner.

Only command-based kinds live here (script, node, native package managers, brew, cask).
Download-based kinds (github_release, tarball) live in `installer.download`.
"""

import shlex
from collections.abc import Callable
from typing import cast

from installer.guards import real_pnpm, shell_path
from installer.locations import applications_dir
from installer.model import Method
from installer.run import Runner


class ExecutorError(RuntimeError):
    """A method could not be turned into a runnable command."""


def _path_prefix() -> str:
    """Export a de-shimmed PATH for the whole `sh -c` script.

    The child would otherwise inherit a PATH whose first entry is the managed
    bin dir, so a vendor install script's own npm/npx call would hit this
    installer's hard-block shim (see guards.shell_path).
    """
    return f"PATH={shlex.quote(shell_path())}; export PATH; "


def require_str(method: Method, key: str) -> str:
    value = method.params.get(key)
    if not isinstance(value, str) or not value:
        raise ExecutorError(f"method '{method.kind}' is missing or empty required param '{key}'")
    return value


def _opt_pkg_list(method: Method, key: str) -> tuple[str, ...]:
    raw = method.params.get(key)
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ExecutorError(f"method '{method.kind}' param '{key}' must be a list of package names")
    items = cast(list[object], raw)
    names: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ExecutorError(
                f"method '{method.kind}' param '{key}' must be a list of package names"
            )
        names.append(item)
    return tuple(names)


def _opt_version_map(method: Method, key: str) -> dict[str, str]:
    raw = method.params.get(key)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ExecutorError(
            f"method '{method.kind}' param '{key}' must be a table of package names to ranges"
        )
    table = cast(dict[object, object], raw)
    out: dict[str, str] = {}
    for name, range_ in table.items():
        if not isinstance(name, str) or not isinstance(range_, str):
            raise ExecutorError(
                f"method '{method.kind}' param '{key}' keys and values must be strings"
            )
        out[name] = range_
    return out


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
    pipeline = f"{_path_prefix()}curl -fsSL -- {shlex.quote(url)} | {invoke}"
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
    # pnpm is invoked by absolute path because the managed bin dir may hold this
    # installer's own argv-conditional pnpm wrapper, and a global install
    # performed by this installer must reach real pnpm so its gated postinstall
    # model still applies.
    pnpm = real_pnpm()
    if pnpm is None:
        raise ExecutorError(
            "pnpm not found on PATH — install pnpm (or, if this installer's pnpm wrapper "
            "is the only pnpm on PATH, re-apply the package-manager policy)"
        )
    npm_pkg = require_str(method, "npm_pkg")
    co_install = _opt_pkg_list(method, "co_install")
    allow_build = _opt_pkg_list(method, "allow_build")
    versions = _opt_version_map(method, "versions")
    # A space-separated list would give each package its own isolated node_modules
    # and lockfile (pnpm Global Packages documentation) — which is the failure
    # mode this exists to prevent, not a stylistic difference.
    members = list(dict.fromkeys([npm_pkg, *co_install]))
    group = ",".join(f"{name}@{versions[name]}" if name in versions else name for name in members)
    # pnpm blocks a dependency's postinstall by default and reports it as a
    # warning rather than an error, so an install that needs its postinstall
    # must name it here or it succeeds while doing nothing. The same flag, per
    # pnpm's documentation, also persists the permission for future versions of
    # that package, which is why the name set is constrained at load time.
    allowances = [f"--allow-build={name}" for name in dict.fromkeys(allow_build)]
    runner([pnpm, "add", "-g", *allowances, group])


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
    pipeline = f'{_path_prefix()}. "$HOME/.sdkman/bin/sdkman-init.sh" && {shlex.join(install)}'
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
