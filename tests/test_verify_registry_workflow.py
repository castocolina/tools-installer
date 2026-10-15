"""Validate the verify-registry workflow stays read-only and off the PR gate."""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
VERIFY_WORKFLOW = ROOT / ".github" / "workflows" / "verify-registry.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _load_verify() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(VERIFY_WORKFLOW.read_text()))


def _steps() -> list[dict[Any, Any]]:
    return _load_verify()["jobs"]["verify"]["steps"]


def _triggers() -> dict[Any, Any]:
    data = _load_verify()
    return cast(dict[Any, Any], data.get("on", data.get(True, {})))


def test_verify_registry_runs_only_on_schedule_and_dispatch() -> None:
    triggers = _triggers()
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    schedules = cast(list[dict[str, str]], triggers["schedule"])
    crons = [entry["cron"] for entry in schedules]
    assert set(crons) == {"17 5 * * 1", "47 5 * * 4"}
    for cron in crons:
        assert not cron.startswith("0 ")


def test_verify_registry_job_cannot_write_the_repo() -> None:
    data = _load_verify()
    assert data["permissions"] == {"contents": "read", "issues": "write"}
    for step in _steps():
        run = step.get("run", "")
        assert "git push" not in run
        assert "git commit" not in run
        assert "gh pr" not in run
        assert "--write" not in run


def test_verify_registry_job_keeps_the_state_after_every_run() -> None:
    steps = _steps()
    restore_idx = next(
        i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/cache/restore")
    )
    save_idx = next(
        i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/cache/save")
    )
    make_idx = next(i for i, s in enumerate(steps) if "make verify-registry" in s.get("run", ""))
    assert restore_idx < make_idx < save_idx
    restore = steps[restore_idx]
    save = steps[save_idx]
    make_step = steps[make_idx]
    assert restore["with"]["path"] == "~/.local/state/tools-installer/verify-registry.json"
    assert save["with"]["path"] == "~/.local/state/tools-installer/verify-registry.json"
    assert "verify-registry-${{ github.run_id }}" in save["with"]["key"]
    assert restore["with"]["restore-keys"].startswith("verify-registry-")
    assert save["if"] == "always()"
    assert "if" not in restore
    assert not any(s.get("uses", "").startswith("actions/cache@v4") for s in steps)
    job_timeout = _load_verify()["jobs"]["verify"]["timeout-minutes"]
    step_timeout = make_step["timeout-minutes"]
    assert isinstance(step_timeout, int)
    assert step_timeout < job_timeout
    assert make_step["if"] == (
        "github.event_name == 'workflow_dispatch' || github.event.schedule == '17 5 * * 1'"
    )


def test_verify_registry_job_reports_drift_with_the_job_token() -> None:
    env = _load_verify()["jobs"]["verify"]["env"]
    assert env["GH_TOKEN"] == "${{ github.token }}"
    runs = [step.get("run", "") for step in _steps()]
    assert any("make verify-registry" in run and "--issue" in run for run in runs)


def test_ci_workflow_never_runs_verify_registry() -> None:
    assert "verify-registry" not in CI_WORKFLOW.read_text()
