"""Validate the CI workflow stays wired to the real quality gates.

GitHub Actions can't be run locally, so this test parses .github/workflows/ci.yml and asserts the
invariants we care about. CI runs on a push to every branch except ``main`` (the commit that
reaches ``main`` was already tested there). A fast-pass classifier skips the full steps for a
docs-only change while keeping the required check names byte-identical: ``make dev-setup``,
``make validate``, ``make test`` and ``make hooks-e2e`` run behind a fail-closed condition.
The matrix covers Linux and macOS. A malformed or gutted workflow fails this test before it is
pushed, where the only other feedback is a failed Actions run after the fact.
"""

import re
from pathlib import Path
from typing import Any, cast

import yaml

from tests.test_makefile import recipes

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(CI_WORKFLOW.read_text()))


def _steps() -> list[dict[Any, Any]]:
    return _load_ci()["jobs"]["validate-and-test"]["steps"]


def _step(name: str) -> dict[Any, Any]:
    return next(step for step in _steps() if step["name"] == name)


def test_ci_triggers_on_branch_pushes_except_main() -> None:
    # PyYAML parses the bare `on:` key as the boolean True (YAML 1.1), not "on".
    # The fallback to the "on" string also covers a future quoted "on": key.
    data = _load_ci()
    triggers = data.get("on", data.get(True, {}))
    assert set(triggers) == {"push"}
    assert triggers["push"] == {"branches-ignore": ["main"]}


def test_job_id_and_name_are_the_required_contexts() -> None:
    job = _load_ci()["jobs"]["validate-and-test"]
    assert job["name"] == "validate & test on ${{ matrix.os }}"
    assert job["strategy"]["matrix"]["os"] == ["ubuntu-latest", "macos-latest"]


def test_checkout_fetches_full_history() -> None:
    checkout = next(step for step in _steps() if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["fetch-depth"] == 0


def test_classify_runs_after_uv_and_before_install() -> None:
    names = [step["name"] for step in _steps()]
    assert (
        names.index("Set up uv")
        < names.index("Classify the change")
        < names.index("Install dependencies")
    )
    scope = next(step for step in _steps() if step.get("id") == "scope")
    assert "devtools.docs_only" in scope["run"]


def test_every_full_step_is_gated_fail_closed() -> None:
    for name in ("Install dependencies", "Validate", "Test", "Hook e2e"):
        assert _step(name)["if"] == "steps.scope.outputs.full != 'false'"


def test_ci_runs_hooks_e2e_after_test() -> None:
    names = [step["name"] for step in _steps()]
    assert names.index("Hook e2e") > names.index("Test")
    assert "make hooks-e2e" in _step("Hook e2e")["run"]


def test_no_run_step_interpolates_an_expression() -> None:
    for step in _steps():
        assert "${{" not in step.get("run", ""), step["name"]


def test_timeouts_are_unchanged() -> None:
    job = _load_ci()["jobs"]["validate-and-test"]
    assert job["timeout-minutes"] == 25
    assert _step("Test")["timeout-minutes"] == 20
    assert _step("Hook e2e")["timeout-minutes"] == 10


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


def test_ci_installs_with_dev_setup() -> None:
    assert "make dev-setup" in [step.get("run", "") for step in _steps()]


def test_ci_names_only_existing_make_targets() -> None:
    targets = recipes()
    for step in _steps():
        for name in re.findall(r"\bmake ([a-zA-Z0-9_-]+)", step.get("run", "")):
            assert name in targets, f"ci.yml runs `make {name}`, which the Makefile does not define"
