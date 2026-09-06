"""Shared test environment guards.

Tests must be deterministic and independent of the developer's shell, the same
way they sandbox HOME. `$ZDOTDIR` now steers which .zshrc the installer writes
to (installer.locations.zshrc_path), so a developer who runs the suite from a
ZDOTDIR-based zsh setup would otherwise get different paths than CI. Clearing
it by default keeps every test that does not set it explicitly on ~/.zshrc.
"""

from pathlib import Path

import pytest


# Public name on purpose: pytest collects it by reference, so a private
# (underscore-prefixed) name reads as dead code to pyright.
@pytest.fixture(autouse=True)
def no_zdotdir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZDOTDIR", raising=False)


@pytest.fixture(scope="session")
def empty_browser_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One empty directory, outside any test's own `tmp_path`.

    Deliberately not built from `tmp_path`: several tests assert on the exact
    contents of their `tmp_path`, and a directory planted there by an autouse
    fixture would change what those tests see.
    """
    return tmp_path_factory.mktemp("empty-browser-cache")


@pytest.fixture(autouse=True)
def sandboxed_puppeteer_cache(empty_browser_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the puppeteer smoke check at an empty cache nobody installed into.

    `installer/pnpm_globals.py::audit_node_globals` re-runs declared smoke
    checks, and the puppeteer one reads `PUPPETEER_CACHE_DIR` (falling back to
    `~/.cache/puppeteer`) and then EXECUTES whatever browser it finds. On a
    developer machine that really has puppeteer installed, a test that only
    meant to exercise group detection would read the real cache and spawn the
    real Chrome — the same class of "never touch this machine" violation the
    HOME sandbox exists to prevent, and a source of results that differ between
    that machine and CI.

    An empty directory makes the check fail before it runs anything. A test
    that wants a browser sets the env var to its own cache, which overrides
    this.
    """
    monkeypatch.setenv("PUPPETEER_CACHE_DIR", str(empty_browser_cache))
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)
