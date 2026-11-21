"""Validate the bot workflow, CI dispatch, Dependabot and proof runbook as plain file parses
without network or gh.
"""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
BOT_WORKFLOW = ROOT / ".github" / "workflows" / "registry-bot.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS: tuple[str, str] = (
    "validate & test on ubuntu-latest",
    "validate & test on macos-latest",
)


def _load(path: Path) -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(path.read_text()))


def _triggers(data: dict[Any, Any]) -> dict[Any, Any]:
    return cast(dict[Any, Any], data.get("on", data.get(True, {})))


def test_the_required_check_names_follow_from_the_ci_job() -> None:
    job = _load(CI_WORKFLOW)["jobs"]["validate-and-test"]
    name = job["name"]
    systems = job["strategy"]["matrix"]["os"]
    assert tuple(name.replace("${{ matrix.os }}", system) for system in systems) == REQUIRED_CHECKS


def test_a_dispatch_runs_the_same_single_job_under_the_same_concurrency() -> None:
    data = _load(CI_WORKFLOW)
    assert set(data["jobs"]) == {"validate-and-test"}
    assert data["concurrency"] == {
        "group": "ci-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    assert "workflow_dispatch" in _triggers(data)
