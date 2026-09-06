"""Per-method-kind executors: build an argv and hand it to the injected runner.

Only command-based kinds live here (script, node, native package managers, brew, cask).
Download-based kinds (github_release, tarball) live in `installer.download`.
"""

import os
import shlex
from collections.abc import Callable
from pathlib import Path
from shutil import which
from typing import cast

from installer.guards import real_pnpm, shell_path
from installer.locations import applications_dir
from installer.model import Method
from installer.run import CommandError, Runner, run_output
from installer.versions import (
    PNPM_ALLOW_BUILD_MIN,
    PNPM_CO_INSTALL_MIN,
    meets_minimum,
    probe_version,
)


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


def _opt_smoke_name(method: Method) -> str | None:
    """The declared smoke-check name, validated against the closed dispatch set.

    Validated with the other params — BEFORE the install runs — because a
    failure after `pnpm add -g` has returned leaves the package installed and
    its shim on PATH while reporting the install as failed, which is the state
    `installer/status.py::is_installed` then reads as ALREADY_INSTALLED.
    `load_tools` catches an unknown name first, but this is the last gate
    before argv and it must not be the one that runs out of order.
    """
    smoke = method.params.get("smoke")
    if smoke is None:
        return None
    if not isinstance(smoke, str) or smoke not in SMOKE_CHECKS:
        raise ExecutorError(f"method '{method.kind}' unknown smoke '{smoke}'")
    return smoke


def _require_minimum(binary: str, argv: list[str], minimum: str) -> None:
    observed = probe_version(argv)
    if observed is None or not meets_minimum(observed, minimum):
        shown = observed if observed is not None else "could not be read"
        raise ExecutorError(
            f"{binary} {shown} does not meet the required minimum {minimum}. "
            f"Upgrade {binary} to {minimum} or newer before using this install method."
        )


# The launch probe is a QUERY this installer must not wait forever on: it runs
# synchronously inside the install executor, and again inside the Doctor's audit
# thread whose result the Textual event loop is waiting on. A cold Chrome start
# is seconds; this is the bound past which the machine is telling us something
# other than "slow" is wrong.
BROWSER_LAUNCH_TIMEOUT = 60.0

# Reading pnpm's own global bin directory is a plain query.
PNPM_BIN_TIMEOUT = 5.0

# `cmd-shim` writes this trailer into every global bin script it generates, and
# it is how pnpm's `$PNPM_HOME/bin/<name>` records which file, inside which
# hash-keyed install group, it execs. That file's directory is the only place
# node can resolve `puppeteer` from under pnpm v11: the global root
# (`pnpm root -g`) has no `node_modules` of its own — each install group has one.
_SHIM_TARGET_MARKER = "# cmd-shim-target="

# Node source for the launch probe. Every decision about WHICH browser to start
# is left to puppeteer: `launch()` reads PUPPETEER_EXECUTABLE_PATH, the cache
# directory puppeteer itself resolves (including the `.puppeteerrc` this
# installer deliberately does not reimplement) and the build puppeteer would
# pick — so the thing started is the thing mmdc will start, not a file this
# project guessed at by globbing.
#
# `process.argv[1..]` are candidate resolution roots; an empty list falls back to
# node's ordinary resolution, which is what NODE_PATH and a local install give.
_LAUNCH_SCRIPT = """\
const roots = process.argv.slice(1);
function load() {
  for (const root of roots) {
    try {
      return require(require.resolve('puppeteer', { paths: [root] }));
    } catch (err) {
      if (!err || err.code !== 'MODULE_NOT_FOUND') throw err;
    }
  }
  return require('puppeteer');
}
(async () => {
  const loaded = load();
  const puppeteer = loaded && loaded.default ? loaded.default : loaded;
  const browser = await puppeteer.launch();
  try {
    const page = await browser.newPage();
    await page.goto('about:blank');
  } finally {
    await browser.close();
  }
})().then(
  () => process.exit(0),
  (err) => {
    console.error(String((err && err.message) || err));
    process.exit(1);
  },
);
"""


def _shim_target(shim: Path) -> Path | None:
    """The entry file a global bin shim runs, or None when the shim is opaque.

    pnpm writes a POSIX `cmd-shim` SCRIPT for a global bin rather than a
    symlink, and ends it with a `# cmd-shim-target=` trailer naming the file it
    execs. Older layouts symlink instead, so both are read. The symlink branch
    tests `is_symlink` rather than comparing against `realpath`, because on a
    machine whose home directory is itself reached through a symlink every path
    differs from its realpath and the trailer would never be read.
    """
    if shim.is_symlink():
        return Path(os.path.realpath(shim))
    try:
        text = shim.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(text.splitlines()):
        if line.startswith(_SHIM_TARGET_MARKER):
            target = line[len(_SHIM_TARGET_MARKER) :].strip()
            if target:
                return Path(target)
    return None


def _pnpm_global_bin() -> Path | None:
    """pnpm's own global bin directory, or None when pnpm cannot be asked.

    A second source for the shim, because `which` is PATH-based and PATH is not
    always current: a machine whose pnpm global bin directory was put on PATH
    during this same run has not inherited it into this process, and failing the
    smoke check there would report a working install as broken.
    """
    pnpm = real_pnpm()
    if pnpm is None:
        return None
    try:
        text = run_output([pnpm, "bin", "-g"], timeout=PNPM_BIN_TIMEOUT)
    except (CommandError, OSError):
        return None
    line = text.strip()
    return Path(line) if line else None


def _puppeteer_module_roots() -> list[str]:
    """Directories node should try to resolve `puppeteer` from, best first.

    pnpm v11 gives each global install invocation its own hash-keyed project
    directory, so there is no single global `node_modules` to point node at —
    `pnpm root -g` names a directory that has none. The `puppeteer` bin shim is
    the pointer that does exist: it names a file inside the group's own
    `node_modules`, from which node's ordinary upward search finds the package
    with the peer resolution that group actually has.

    An empty list is not a failure. It hands the script nothing and lets node
    resolve `puppeteer` normally, which is the right answer whenever the package
    is reachable some way this function does not model.
    """
    candidates: list[Path] = []
    on_path = which("puppeteer")
    if on_path:
        candidates.append(Path(on_path))
    bin_dir = _pnpm_global_bin()
    if bin_dir is not None:
        candidates.append(bin_dir / "puppeteer")
    roots: list[str] = []
    for shim in candidates:
        if not shim.is_file():
            continue
        target = _shim_target(shim)
        if target is not None:
            roots.append(str(target.parent))
    return list(dict.fromkeys(roots))


# This text is rendered inside a one-line Doctor warning row, and a Chrome
# launch failure can be a paragraph.
_DETAIL_LIMIT = 400


def _condensed(detail: str) -> str:
    text = " ".join(detail.split())
    return text if len(text) <= _DETAIL_LIMIT else f"{text[: _DETAIL_LIMIT - 3]}..."


def _default_launch_puppeteer() -> str | None:
    """Start and close a browser through puppeteer's own launch path.

    Returns why it failed, or None when it worked. `node` is invoked bare for
    the reason `min_node` is probed bare: this installer ships no node shim, and
    the node that matters is the one pnpm's postinstall and mmdc itself find on
    PATH.
    """
    argv = ["node", "-e", _LAUNCH_SCRIPT, *_puppeteer_module_roots()]
    try:
        run_output(argv, timeout=BROWSER_LAUNCH_TIMEOUT)
    except CommandError as exc:
        if exc.returncode == 127:
            return "node could not be started to run the launch probe"
        return _condensed(exc.detail) or f"the launch probe exited {exc.returncode}"
    return None


# The seam the tests replace. It covers the whole probe — root discovery and the
# subprocess — so no test reaches a real pnpm, a real node or a real browser.
launch_puppeteer: Callable[[], str | None] = _default_launch_puppeteer


def _smoke_puppeteer_browser() -> None:
    """Prove puppeteer can actually START a browser on this machine.

    NOT `<browser> --version`, which is what this replaced and what made the
    check hollow. `--version` prints a string and exits BEFORE browser startup,
    sandbox initialisation, profile creation and the DevTools connection — the
    four steps that fail on a machine missing Chrome's shared libraries, which
    is the only failure this check exists to catch. It was also aimed by this
    project's own glob over the puppeteer cache, picking the lexicographically
    last (later, highest-parsed-build) path rather than necessarily the browser
    puppeteer would launch, so any executable that printed something passed:
    `PUPPETEER_EXECUTABLE_PATH=/bin/echo` cleared it.

    `puppeteer.launch()` answers both halves at once. It resolves the browser
    the way puppeteer will at runtime — so PUPPETEER_EXECUTABLE_PATH, the cache
    directory and puppeteer's own configuration are honoured by puppeteer rather
    than reimplemented here — and starting it is the evidence.

    It renders no diagram. A blank page proves the browser runs; mmdc's own
    rendering is not this installer's to verify.
    """
    detail = launch_puppeteer()
    if detail is None:
        return
    raise ExecutorError(
        f"puppeteer could not start a browser: {detail}. "
        "Install the platform's headless-Chrome shared libraries, or point "
        "puppeteer at an existing browser with PUPPETEER_EXECUTABLE_PATH."
    )


SMOKE_CHECKS: dict[str, Callable[[], None]] = {
    "puppeteer-browser": _smoke_puppeteer_browser,
}


def run_smoke_check(name: str) -> str | None:
    """Run a declared smoke check; return why it failed, or None when it passed.

    The non-raising form of the dispatch above, for the Doctor's node-globals
    audit. A failing check there is a FINDING to render, not an operation to
    abort — the audit reports on a machine, it does not install anything.

    An unknown name returns None. `installer/model.py::load_tools` validates
    every `smoke` against the closed name set at load time, and an audit that
    could not interpret a name must not invent a broken tool from it — the same
    rule `NodeGlobalsReport.known` enforces for the query as a whole.
    """
    check = SMOKE_CHECKS.get(name)
    if check is None:
        return None
    try:
        check()
    except ExecutorError as exc:
        return str(exc)
    return None


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
    smoke = _opt_smoke_name(method)
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
    min_node = method.params.get("min_node")
    if co_install or allow_build:
        floor = PNPM_CO_INSTALL_MIN if co_install else PNPM_ALLOW_BUILD_MIN
        # Probe the resolved absolute path, never the bare name: a bare `pnpm`
        # would be answered by this installer's own argv-conditional wrapper.
        _require_minimum("pnpm", [pnpm, "--version"], floor)
    if isinstance(min_node, str) and min_node:
        # Probe bare `node`: this installer ships no node shim, and the node
        # that matters is exactly the one pnpm's postinstall step will find
        # on PATH.
        _require_minimum("node", ["node", "--version"], min_node)
    runner([pnpm, "add", "-g", *allowances, group])
    # This starts, navigates and closes a real browser through puppeteer's own
    # `launch()`, so it proves the browser PUPPETEER RESOLVES runs on this
    # machine. It does not render a diagram, and it is not a guarantee that
    # every later Chrome update will keep starting. An exit code from a package
    # manager is evidence that a DOWNLOAD succeeded, never evidence that the
    # thing downloaded can run.
    #
    # Accepted residual: puppeteer resolves the browser, so on a machine that
    # already had a working Chrome the check can pass on THAT browser rather
    # than on bytes this install wrote. That is the correct answer to the
    # question the tool cares about — can mmdc render here — and it is the same
    # resolution mmdc performs, so a pass here and a working mmdc do not come
    # apart.
    #
    # THIS CHECK FIRES ONCE, ON THE INSTALL PATH ONLY, AND ONLY WHEN THE
    # INSTALL PATH IS REACHED. It runs after `pnpm add -g` has already
    # returned, so a failure here leaves the packages installed and pnpm's bin
    # shim on PATH while the install reports FAILED — and nothing rolls that
    # back, because a postinstall-driven download cannot be gated before the
    # shim exists. `installer/status.py::is_installed` is PATH-presence-based,
    # so `installer/engine.py::install_tool` returns ALREADY_INSTALLED on the
    # next run and never reaches this executor again.
    #
    # The Doctor closes that gap rather than the engine:
    # `installer/pnpm_globals.py::audit_node_globals` re-runs the declared
    # check for every catalog tool pnpm still manages, so a browser broken
    # later (an OS update removing a shared library) surfaces as a WARN there.
    # Making `is_installed` itself run the check was rejected: it is called on
    # every catalog render and for every tool of every kind, and spawning a
    # browser per render to answer "is it here?" trades one wrong answer for a
    # rule that no longer describes availability. So the residual that remains
    # is narrow and known: a tool broken after install is reported by the
    # Doctor, not by the install flow, and re-running the install alone will
    # still short-circuit on ALREADY_INSTALLED.
    if smoke is not None:
        SMOKE_CHECKS[smoke]()


def _uv_tool(method: Method, runner: Runner) -> None:
    pypi_pkg = require_str(method, "pypi_pkg")
    runner(["uv", "tool", "install", pypi_pkg])


def _sdkman(method: Method, runner: Runner) -> None:
    # `sdk` is a shell function defined by sourcing sdkman-init.sh, not a PATH
    # binary — it must be sourced in the same shell invocation that calls it.
    # On a machine where THIS installer bootstrapped SDKMAN, its `?ci=true`
    # bootstrap persisted `sdkman_auto_answer=true` in ~/.sdkman/etc/config, so
    # a candidate install here does not hang on the interactive version-choice
    # prompt (see registry.toml's `sdkman`/`java` `# Verified` comments for the
    # full finding). This guarantee does NOT extend to a brownfield machine
    # with a pre-existing SDKMAN install — `is_installed`/`install_tool` skip
    # this project's own bootstrap entirely for a tool SDKMAN already provides
    # (installer/status.py, installer/engine.py), so `sdkman_auto_answer` may
    # still be `false` there and this call can reach the prompt.
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
    "uv-tool": _uv_tool,
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
