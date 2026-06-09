"""Validate the CI workflow stays wired to the real quality gates.

GitHub Actions can't be run locally, so this test parses .github/workflows/ci.yml
and asserts the invariants we care about: it triggers on push + pull_request, runs
`make validate` and `make test`, sets up uv via the official action, and exercises
both Linux and macOS. It catches a malformed or gutted workflow before it is
pushed (where the only other feedback is a failed Actions run after the fact).
"""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(CI_WORKFLOW.read_text()))


def _steps() -> list[dict[Any, Any]]:
    return _load_ci()["jobs"]["validate-and-test"]["steps"]


def test_ci_triggers_on_push_and_pull_request() -> None:
    # PyYAML parses the bare `on:` key as the boolean True (YAML 1.1), not "on".
    # The fallback to the "on" string also covers a future quoted "on": key.
    data = _load_ci()
    triggers = data.get("on", data.get(True, {}))
    assert "push" in triggers
    assert "pull_request" in triggers


def test_ci_runs_validate_and_test() -> None:
    run_cmds = [step.get("run", "") for step in _steps()]
    assert any("make validate" in cmd for cmd in run_cmds)
    assert any("make test" in cmd for cmd in run_cmds)


def test_ci_sets_up_uv_with_official_action() -> None:
    uses = [step.get("uses", "") for step in _steps()]
    assert any("astral-sh/setup-uv" in ref for ref in uses)


def test_ci_matrix_covers_linux_and_macos() -> None:
    matrix = _load_ci()["jobs"]["validate-and-test"]["strategy"]["matrix"]["os"]
    assert "ubuntu-latest" in matrix
    assert "macos-latest" in matrix
