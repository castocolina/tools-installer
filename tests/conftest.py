"""Shared test environment guards.

Tests must be deterministic and independent of the developer's shell, the same
way they sandbox HOME. `$ZDOTDIR` now steers which .zshrc the installer writes
to (installer.locations.zshrc_path), so a developer who runs the suite from a
ZDOTDIR-based zsh setup would otherwise get different paths than CI. Clearing
it by default keeps every test that does not set it explicitly on ~/.zshrc.
"""

import pytest


# Public name on purpose: pytest collects it by reference, so a private
# (underscore-prefixed) name reads as dead code to pyright.
@pytest.fixture(autouse=True)
def no_zdotdir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZDOTDIR", raising=False)
