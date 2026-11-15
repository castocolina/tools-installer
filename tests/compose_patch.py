"""The one way a test patches a name the composition code reads."""

import pytest

import setup
from installer import compose


def patch_composition(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> None:
    """Patch `name` in every one of `installer.compose` and `setup` that binds it.

    Moved code looks a name up in its own module, so a patch must land where the code
    reads it; a name both modules bind (a constant setup imports back) is patched in
    both. Raises when neither binds it, so a typo or a stale name stays loud.
    """
    bound = [module for module in (compose, setup) if name in vars(module)]
    if not bound:
        raise AttributeError(f"neither installer.compose nor setup binds {name!r}")
    for module in bound:
        monkeypatch.setattr(module, name, value)
