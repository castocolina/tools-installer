"""Shared test environment guards.

Tests must be deterministic and independent of the developer's shell. Every
test runs with HOME pointing at a per-test scratch dir, so `Path.home()` and
`os.path.expanduser` never read the developer's home; a test that sets HOME
itself still overrides that. `$ZDOTDIR` now steers which .zshrc the installer
writes to (installer.locations.zshrc_path), so a developer who runs the suite
from a ZDOTDIR-based zsh setup would otherwise get different paths than CI.
Clearing it by default keeps every test that does not set it explicitly on
~/.zshrc.
"""

import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from installer import app, executors, locations, post_install, postinstall, receipts
from tests.home_fingerprint import fingerprint, fingerprint_diff
from tests.sandbox import (
    HOST_ZSH_STASH,
    OVERRIDES_STASH,
    capture_home_overrides,
    env_names_to_clear,
    host_zsh_stash,
    prepare_interpreter_dir,
    sandboxed_path,
)

# Captured at conftest IMPORT time, before any test can monkeypatch $HOME, so
# this stays the developer's real home no matter what a test does later.
_REAL_HOME = Path(os.path.expanduser("~"))  # noqa: PTH111 -- must not follow a patched Path.home()
# Toolchain overrides, captured at import for the same reason (the fingerprint watches them).
# A worker reads the stash its controller wrote, since the controller has cleared the live values.
_HOME_OVERRIDES: dict[str, str | None] = capture_home_overrides(os.environ)
# The interpreter link dir this run prepends to PATH, or None when no shell needed a link.
_interpreter_dir: Path | None = None

# Same trick for the puppeteer launch probe: captured before the autouse stub
# below replaces it, so the tests that ARE the probe can put it back through
# the `real_launch_probe` fixture without reaching past the module's surface.
_REAL_LAUNCH_PUPPETEER: Callable[[], str | None] = executors.launch_puppeteer
# The same trick for the host reader, restored by `real_present_hosts`.
_REAL_PRESENT_HOSTS: Callable[[], frozenset[str]] = postinstall.present_hosts
# The node-family names answered by Volta, fnm, pnpm and bun, plus brew.
# Tests that need one plant a fake under tmp_path.
HOST_TOOLCHAIN: frozenset[str] = frozenset(
    {"node", "npm", "npx", "pnpm", "corepack", "volta", "bun", "yarn", "brew"}
)
_toolchain_allowed_root: Path | None = None


def _allowed_root() -> Path:
    if _toolchain_allowed_root is None:
        raise RuntimeError("toolchain_allowed_root did not run")
    return _toolchain_allowed_root


def assert_not_host_toolchain(
    argv: object,
    *,
    env: Mapping[str, str] | None,
    cwd: object,
    allowed_root: Path,
) -> None:
    """Refuse host toolchain executables; the net is under sandboxed_puppeteer_cache.

    A shell string and a script's own child processes are not inspected; the
    PATH strip covers bare names there. Widen when a test needs a script that
    must not reach the host toolchain.
    """
    if not isinstance(argv, (list, tuple)) or not argv or not isinstance(argv[0], str):
        return
    first = argv[0]
    name = Path(first).name
    if name not in HOST_TOOLCHAIN:
        return
    if os.sep in first:
        base = Path(cwd if isinstance(cwd, (str, Path)) else os.getcwd())
        candidate = base / first
    else:
        found = shutil.which(first, path=(env if env is not None else os.environ).get("PATH", ""))
        if found is None:
            return
        candidate = Path(found)
    resolved = candidate.resolve()
    if not resolved.exists() or resolved.is_relative_to(allowed_root):
        return
    message = (
        f"the suite tried to run the host's {name} at {resolved}; "
        "plant a fake under tmp_path instead"
    )
    raise AssertionError(message)


class GuardedPopen(subprocess.Popen[Any]):
    """Subscriptable Popen replacement, as installer/run.py annotates Popen[str]."""

    def __init__(self, args: Any, *pargs: Any, **kwargs: Any) -> None:
        assert_not_host_toolchain(
            args,
            env=kwargs.get("env"),
            cwd=kwargs.get("cwd"),
            allowed_root=_allowed_root(),
        )
        super().__init__(args, *pargs, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def toolchain_allowed_root(tmp_path_factory: pytest.TempPathFactory) -> None:
    global _toolchain_allowed_root
    _toolchain_allowed_root = tmp_path_factory.getbasetemp().resolve()


@pytest.fixture(autouse=True)
def no_host_toolchain_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every subprocess.run resolves Popen here; the guard refuses before launch."""
    monkeypatch.setattr(subprocess, "Popen", GuardedPopen)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    """`-n auto` uses at most ~40% of the usable CPUs (24 -> 10), so the host is never starved.

    `PYTEST_XDIST_AUTO_NUM_WORKERS` still overrides this, per xdist.
    """
    if sys.platform == "linux":
        usable = len(os.sched_getaffinity(0))
    else:
        usable = os.cpu_count() or 1
    return max(1, round(usable * 0.4))


@pytest.fixture(scope="session", autouse=True)
def real_home_untouched() -> "object":
    """Fail the run if any test wrote to the developer's real shell files.

    `setup.py` resolves its path constants at IMPORT time (`_MYSHELLRC`,
    `_SHELLRC`, ...), so `monkeypatch.setenv("HOME", ...)` alone does NOT
    redirect them -- each one must be patched by name. That makes isolation
    opt-in, and an opt-in guarantee is one a future test will eventually forget:
    a single un-redirected constant reaching `configure_path` would consolidate
    the developer's own ~/.shellrc and leave a backup behind.

    This is the net under that. It catches the whole class at session scope
    rather than trusting every present and future test to remember. The
    fingerprint is metadata only (tests/home_fingerprint.py) and names each
    changed path and entry (SPEC R9, D-24, D-25).
    """
    before = fingerprint(_REAL_HOME, _HOME_OVERRIDES)
    yield
    changed = fingerprint_diff(before, fingerprint(_REAL_HOME, _HOME_OVERRIDES))
    assert not changed, (
        f"the test suite modified real files under {_REAL_HOME}:\n  "
        + "\n  ".join(changed)
        + "\nA test reached a home-derived constant without redirecting it; patch it "
        "the way tests/test_setup.py::_sandbox does. If an entry was written by another "
        "program running at the same time (an agent session timer, an editor), re-run; "
        "this guard fails on any change (23.1 D-25)."
    )


def pytest_configure(config: pytest.Config) -> None:
    """Sandbox the test PATH and environment before collection (23.1 D-16, D-17).

    Runs in the controller and again in each xdist worker. The stashes make the first
    process's answers (the zsh before the strip, the link dir, the toolchain overrides) the
    ones every worker keeps, because the controller has already cleared the live values.
    """
    global _interpreter_dir
    original = os.environ.get("PATH", "")
    if HOST_ZSH_STASH not in os.environ:
        os.environ[HOST_ZSH_STASH] = host_zsh_stash(original)
    if OVERRIDES_STASH not in os.environ:
        os.environ[OVERRIDES_STASH] = json.dumps(capture_home_overrides(os.environ))
    link, made = prepare_interpreter_dir(
        os.environ,
        real_home=_REAL_HOME,
        make_dir=lambda: Path(tempfile.mkdtemp(prefix="tools-installer-interpreters-")),
    )
    if made is not None:
        config.add_cleanup(functools.partial(shutil.rmtree, made, ignore_errors=True))
    _interpreter_dir = link
    os.environ["PATH"] = sandboxed_path(original, real_home=_REAL_HOME, interpreter_dir=link)
    for name in env_names_to_clear(os.environ):
        del os.environ[name]


@pytest.fixture(autouse=True)
def no_shell_location_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear inherited agent, toolchain and shell-location variables, and re-strip PATH.

    The names (`env_names_to_clear`) cover the developer's shell files (`$ZDOTDIR`, `$ZSH`),
    absolute toolchain overrides into the real HOME (`PNPM_HOME`, `VOLTA_HOME`, the XDG
    variables), agent config and tokens, and the `UV_`, `HOMEBREW_` and `npm_config_` families.
    The PATH loses the real home, `/run/user` and linuxbrew bins, judged by resolved path
    (`/home` may symlink to `/var/home`); `sh`, `bash` and `zsh` stay runnable by name through
    the interpreter link dir. With `VOLTA_HOME` cleared, a Volta shim can reinvoke itself
    through PATH and fork without end (P3-01, 24d91d6). Tests that exercise these variables
    set them after this fixture.
    """
    for name in env_names_to_clear(os.environ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(
        "PATH",
        sandboxed_path(
            os.environ.get("PATH", ""), real_home=_REAL_HOME, interpreter_dir=_interpreter_dir
        ),
    )


@pytest.fixture(autouse=True)
def sandboxed_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point HOME at a per-test scratch dir under pytest's base temp (P19-12, G28).

    The state doubles sandbox `home` and the managed bin dir, but declared
    locations (`~/.sdkman/...`, `~/.local/opt`, `~/Applications`) are expanded
    through HOME deep in production code. `Path.home()` and `expanduser` both
    read HOME on Linux and macOS, so one assignment covers both. A test that
    sets HOME itself still overrides this.
    """
    home = tmp_path_factory.getbasetemp() / "home" / uuid.uuid4().hex
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))


def _rerooted(path: Path, real_home: Path, project: Path, scratch: Path) -> Path:
    """Move `path` from the real HOME onto `scratch`; keep paths outside HOME or in the checkout."""
    resolved = Path(os.path.realpath(path))
    if resolved.is_relative_to(project) or not resolved.is_relative_to(real_home):
        return path
    return scratch / resolved.relative_to(real_home)


# setup.py resolves its home paths at IMPORT, before any fixture runs, so HOME alone
# cannot reach them. Re-root every such attribute, generically, so a constant added
# later is covered too; `real_home_untouched` stays the net underneath (review R1-07).
@pytest.fixture(autouse=True)
def no_shell_init_sourcing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test that builds the app injects its split-mode reader; reset it per test (R1-05)."""
    monkeypatch.setattr(post_install, "_shell_init_sourced_from", lambda: ())


@pytest.fixture(autouse=True)
def sandboxed_setup_paths(sandboxed_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
    setup_module = sys.modules.get("setup")
    if setup_module is None:
        return
    real_home = Path(os.path.realpath(_REAL_HOME))
    project = Path(os.path.realpath(setup_module.__file__ or "."))
    project = project.parent if project.is_file() else project
    scratch = Path.home()
    for name, value in list(vars(setup_module).items()):
        if isinstance(value, Path):
            monkeypatch.setattr(setup_module, name, _rerooted(value, real_home, project, scratch))
        elif isinstance(value, (list, tuple)):
            items = cast(Sequence[object], value)
            if items and all(isinstance(item, Path) for item in items):
                moved = [
                    _rerooted(item, real_home, project, scratch)
                    for item in items
                    if isinstance(item, Path)
                ]
                monkeypatch.setattr(
                    setup_module, name, moved if isinstance(value, list) else tuple(moved)
                )


@pytest.fixture(autouse=True)
def sandboxed_receipts(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect the receipts dir to a per-test scratch dir under pytest's base temp.

    Every receipt write in the suite must land here, never in the developer's
    real `~/.local/state/tools-installer/receipts` (the session fingerprint is
    the net under this). The directory is NOT created: `receipts.write` makes
    it lazily, and tests assert on their own tmp_path contents.
    """
    sandbox = tmp_path_factory.getbasetemp() / "receipts" / uuid.uuid4().hex
    monkeypatch.setattr(receipts, "receipts_dir", lambda: sandbox)


@pytest.fixture(autouse=True)
def sandboxed_bin_dir(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Answer `locations.bin_dir(None)`'s default with a per-test scratch dir.

    The host's real `~/.local/bin` holds about 50 registry binaries; plan 19-02
    counts that dir as tool presence, so an un-redirected default would make
    results depend on this machine. The HOME check keeps a test that DID
    redirect HOME reading `HOME/.local/bin` as usual.
    """
    original: Callable[[str | None], Path] = locations.bin_dir
    scratch = tmp_path_factory.getbasetemp() / "bin-dir" / uuid.uuid4().hex

    def _sandboxed(declared: str | None) -> Path:
        if declared:
            return original(declared)
        if Path.home() == _REAL_HOME:
            return scratch
        return original(declared)

    monkeypatch.setattr(locations, "bin_dir", _sandboxed)


@pytest.fixture(scope="session")
def empty_browser_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One empty directory, outside any test's own `tmp_path`.

    Deliberately not built from `tmp_path`: several tests assert on the exact
    contents of their `tmp_path`, and a directory planted there by an autouse
    fixture would change what those tests see.
    """
    return tmp_path_factory.mktemp("empty-browser-cache")


# What the stubbed launch below reports. A fixed string, so a test that forgets
# its own seam gets a failing smoke check it can read rather than a mystery.
NO_BROWSER_DETAIL = "no browser in the test sandbox"


@pytest.fixture(autouse=True)
def sandboxed_puppeteer_cache(empty_browser_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the puppeteer smoke check at an empty cache nobody installed into,
    and stub the launch seam so no test can execute the host's node or browser.

    The cache env var alone is not a sandbox: the probe resolves `puppeteer`
    through the host's own toolchain and then EXECUTES whatever it finds, so a
    test that only meant to exercise group detection could spawn a real
    browser — and on this machine the node on PATH is the Volta shim, which,
    with `VOLTA_HOME` cleared above, re-invokes the node that is itself and
    forks without end.

    An empty directory plus a stubbed launch makes the check fail before it
    runs anything, which is the verdict the tests already assume. The launch
    stub is the first layer; the PATH strip plus Popen guard are the net under it.
    A test that
    wants a browser, or that exercises the real probe, sets its own seam with
    `monkeypatch.setattr(executors, "launch_puppeteer", ...)` — that runs after
    this autouse fixture and overrides it.
    """
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(empty_browser_cache))
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(executors, "launch_puppeteer", lambda: NO_BROWSER_DETAIL)


@pytest.fixture(autouse=True)
def no_host_presence(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads the developer's agent hosts: `present_hosts` answers that none is present."""
    monkeypatch.setattr(postinstall, "present_hosts", lambda: frozenset[str]())


@pytest.fixture
def real_present_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real host reader, for the tests that exercise it."""
    monkeypatch.setattr(postinstall, "present_hosts", _REAL_PRESENT_HOSTS)


@pytest.fixture(autouse=True)
def no_manager_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The remover's fresh manager listing reads as unknown, so no test queries the host's
    brew, uv or pnpm; a test that exercises the re-check sets its own listing."""

    def unknown(_kind: str) -> None:
        return None

    monkeypatch.setattr(app, "manager_listing", unknown)


@pytest.fixture
def real_launch_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real puppeteer launch probe, for the tests that exercise it.

    Those still fake `executors.run_output`, the one call that would start a
    process, so the probe runs for real without touching the machine.
    """
    monkeypatch.setattr(executors, "launch_puppeteer", _REAL_LAUNCH_PUPPETEER)
