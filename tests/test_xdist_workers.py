"""The `-n auto` worker count: a 40% host cap locally, the env override on CI runners."""

from __future__ import annotations

import pytest

from tests import conftest


def test_env_override_wins_over_the_host_cap(
    monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> None:
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "3")
    assert conftest.pytest_xdist_auto_num_workers(pytestconfig) == 3


@pytest.mark.parametrize("value", ["", "0", "-2", "many"])
def test_a_bad_override_falls_back_to_the_host_cap(
    monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config, value: str
) -> None:
    monkeypatch.delenv("PYTEST_XDIST_AUTO_NUM_WORKERS", raising=False)
    capped = conftest.pytest_xdist_auto_num_workers(pytestconfig)
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", value)
    assert conftest.pytest_xdist_auto_num_workers(pytestconfig) == capped >= 1
