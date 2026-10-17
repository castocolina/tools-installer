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

import os
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest

from installer import executors, locations, receipts, version_status

# Captured at conftest IMPORT time, before any test can monkeypatch $HOME, so
# this stays the developer's real home no matter what a test does later.
_REAL_HOME = Path(os.path.expanduser("~"))  # noqa: PTH111 -- must not follow a patched Path.home()

# Same trick for the puppeteer launch probe: captured before the autouse stub
# below replaces it, so the tests that ARE the probe can put it back through
# the `real_launch_probe` fixture without reaching past the module's surface.
_REAL_LAUNCH_PUPPETEER: Callable[[], str | None] = executors.launch_puppeteer
_GUARDED_DOTFILES = (".myshellrc", ".shellrc", ".bashrc", ".zshrc", ".profile")


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    """`-n auto` uses at most ~40% of the usable CPUs (24 -> 10), so the host is never starved.

    `PYTEST_XDIST_AUTO_NUM_WORKERS` still overrides this, per xdist.
    """
    if sys.platform == "linux":
        usable = len(os.sched_getaffinity(0))
    else:
        usable = os.cpu_count() or 1
    return max(1, round(usable * 0.4))


def _real_home_fingerprint() -> dict[str, tuple[int, float] | None]:
    """(size, mtime) for each guarded file in the real home, None when absent.

    Also covers `*.tools-installer.old`, the backup sibling consolidation writes:
    its mere APPEARANCE is a violation even though no guarded file changed.
    """
    fingerprint: dict[str, tuple[int, float] | None] = {}
    for name in _GUARDED_DOTFILES:
        path = _REAL_HOME / name
        try:
            stat = path.stat()
        except OSError:
            fingerprint[name] = None
        else:
            fingerprint[name] = (stat.st_size, stat.st_mtime)
    fingerprint["<backups>"] = (len(list(_REAL_HOME.glob("*.tools-installer.old"))), 0.0)
    receipts_dir = _REAL_HOME / ".local" / "state" / "tools-installer" / "receipts"
    if receipts_dir.is_dir():
        fingerprint["<receipts>"] = (
            len(list(receipts_dir.iterdir())),
            receipts_dir.stat().st_mtime,
        )
    else:
        fingerprint["<receipts>"] = None
    return fingerprint


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
    rather than trusting every present and future test to remember.
    """
    before = _real_home_fingerprint()
    yield
    after = _real_home_fingerprint()
    changed = sorted(name for name in before if before[name] != after[name])
    assert not changed, (
        f"the test suite modified real files under {_REAL_HOME}: {changed}. "
        f"A test reached a home-derived constant without redirecting it; patch it "
        f"the way tests/test_setup.py::_sandbox does."
    )


# Public name on purpose: pytest collects it by reference, so a private
# (underscore-prefixed) name reads as dead code to pyright.
@pytest.fixture(autouse=True)
def no_shell_location_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear inherited shell and location overrides so tests never follow the
    developer's real HOME.

    `$ZDOTDIR` and `$ZSH` point at the developer's shell. `PNPM_HOME`,
    `VOLTA_HOME`, `XDG_CONFIG_HOME` and `XDG_DATA_HOME` are absolute overrides
    inherited from the developer's shell that point into the real HOME (RR-05:
    `owner_dirs` reads the first two, the terminal and XDG helpers the last
    two). A test that exercises one sets it with `monkeypatch.setenv`, which
    runs after this autouse fixture.
    """
    monkeypatch.delenv("ZDOTDIR", raising=False)
    monkeypatch.delenv("ZSH", raising=False)  # omz_root falls back to $ZSH
    monkeypatch.delenv("PNPM_HOME", raising=False)
    monkeypatch.delenv("VOLTA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)


@pytest.fixture(autouse=True)
def sandboxed_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point HOME at a per-test scratch dir under pytest's base temp (P19-12, G28).

    The state doubles sandbox `skill_home` and the managed bin dir, but declared
    locations (`~/.sdkman/...`, `~/.local/opt`, `~/Applications`) are expanded
    through HOME deep in production code. `Path.home()` and `expanduser` both
    read HOME on Linux and macOS, so one assignment covers both. A test that
    sets HOME itself still overrides this.
    """
    home = tmp_path_factory.getbasetemp() / "home" / uuid.uuid4().hex
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))


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


@pytest.fixture(autouse=True)
def sandboxed_skill_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Answer `version_status.default_skill_home()` with a per-test scratch dir.

    A service built without `skill_home` would otherwise read the developer's
    real host GSD leftovers and plugin lists (checker W5). The dir is not
    created. As in `sandboxed_bin_dir`, a test that redirected HOME keeps
    reading that HOME; a test passing `skill_home` is unaffected.
    """
    original: Callable[[], Path] = version_status.default_skill_home
    scratch = tmp_path_factory.getbasetemp() / "skill-home" / uuid.uuid4().hex

    def _sandboxed() -> Path:
        if Path.home() == _REAL_HOME:
            return scratch
        return original()

    monkeypatch.setattr(version_status, "default_skill_home", _sandboxed)


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
    runs anything, which is the verdict the tests already assume. A test that
    wants a browser, or that exercises the real probe, sets its own seam with
    `monkeypatch.setattr(executors, "launch_puppeteer", ...)` — that runs after
    this autouse fixture and overrides it.
    """
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(empty_browser_cache))
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
    monkeypatch.setattr(executors, "launch_puppeteer", lambda: NO_BROWSER_DETAIL)


@pytest.fixture
def real_launch_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real puppeteer launch probe, for the tests that exercise it.

    Those still fake `executors.run_output`, the one call that would start a
    process, so the probe runs for real without touching the machine.
    """
    monkeypatch.setattr(executors, "launch_puppeteer", _REAL_LAUNCH_PUPPETEER)
