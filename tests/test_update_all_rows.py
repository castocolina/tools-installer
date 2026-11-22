"""Per-tool schedules record only evidenced mutations."""

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest

from installer import executors, schedule_run, schedules, update
from installer import update_all_state as store
from installer.model import Method, Tool
from installer.notify import no_notifier
from installer.ownership import ManagerOwnership
from installer.run import CommandError
from installer.schedule_run import RunDeps, run_schedule
from installer.update import UpdateError, UpdateOutcome, UpdateService, UpdateTarget
from tests.update_all_doubles import (
    FEDORA,
    ScriptedProbe,
    SpyService,
    catalog_tool,
    owned,
    run_deps,
)
from tests.update_check_doubles import check_context

NOW = datetime(2026, 11, 22, 12, tzinfo=UTC)


def rig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_id: str = "claude"
) -> tuple[RunDeps, SpyService]:
    ctx = check_context(tmp_path, monkeypatch)
    tool = catalog_tool(tool_id)
    service = SpyService()
    return run_deps(
        [tool], ctx, service=service, owners={tool.id: owned(tool, "installer")}, now=lambda: NOW
    ), service


def run(deps: RunDeps, name: str = "claude") -> tuple[str, int]:
    return run_schedule("update-" + name, deps, parent_holds_lock=True)


def path_for(deps: RunDeps) -> Path:
    assert deps.context is not None
    return schedules.updated_today_path(deps.context)


def test_update_all_updating_a_tool_makes_its_row_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, service = rig(tmp_path, monkeypatch)
    store.record_updated(path_for(deps), "claude", today=NOW.date(), by="update-all")
    assert run(deps) == ("skipped: updated today", 0)
    assert service.runs == []


@pytest.mark.parametrize("by", ["update-claude", "update-opencode"])
def test_a_row_runs_again_when_its_own_row_or_another_row_updated_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, by: str
) -> None:
    deps, service = rig(tmp_path, monkeypatch)
    store.record_updated(path_for(deps), "claude", today=NOW.date(), by=by)
    assert run(deps) == ("ok: updated", 0)
    assert service.runs == ["claude"]


def test_the_next_calendar_day_nothing_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, service = rig(tmp_path, monkeypatch)
    store.record_updated(path_for(deps), "claude", today=NOW.date(), by="update-all")
    assert run(deps)[0] == "skipped: updated today"
    assert run(replace(deps, now=lambda: NOW + timedelta(days=1))) == ("ok: updated", 0)
    assert service.runs == ["claude"]


@pytest.mark.parametrize(
    ("after", "line"), [("1.1", "ok: updated 1.0 → 1.1"), ("1.0", "ok: up to date")]
)
def test_a_per_tool_row_records_what_it_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after: str, line: str
) -> None:
    deps, _ = rig(tmp_path, monkeypatch)
    deps = replace(deps, probe_version=ScriptedProbe({"claude": ["1.0", after]}))
    assert run(deps) == (line, 0)
    assert store.read_updated(path_for(deps)) == (
        {"claude": store.UpdatedEntry(NOW.date(), "update-claude")},
        True,
    )


def test_a_mutation_followed_by_a_failing_probe_or_shim_is_still_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _ = rig(tmp_path, monkeypatch)
    deps = replace(deps, probe_version=ScriptedProbe({"claude": ["1", OSError("probe failed")]}))
    assert run(deps) == ("failed: probe failed", 1)
    assert store.read_updated(path_for(deps))[0]["claude"].by == "update-claude"
    cursor = catalog_tool("cursor-agent")
    assert deps.context is not None
    agent = deps.context.home / ".local/bin/agent"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text("fake")

    def fail(_ctx: schedules.ScheduleContext) -> str:
        raise OSError("shim failed")

    monkeypatch.setattr(schedule_run, "_refresh_cursor_shim", fail)

    def resolve(tool: Tool) -> ManagerOwnership:
        return owned(tool, "installer")

    deps = replace(
        deps,
        tools=[cursor],
        resolve_owner=resolve,
        probe_version=ScriptedProbe({}),
    )
    assert run(deps, "cursor-agent") == ("failed: shim failed", 1)
    assert store.read_updated(path_for(deps))[0]["cursor-agent"].by == "update-cursor-agent"


@pytest.mark.parametrize("manager", ["pnpm", "bun"])
def test_a_smoke_failure_after_the_mutation_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manager: Literal["pnpm", "bun"]
) -> None:
    ctx = check_context(tmp_path, monkeypatch)
    method = Method(
        "node" if manager == "pnpm" else "bun", {"npm_pkg": "pkg", "smoke": "puppeteer-browser"}
    )
    tool = Tool("claude", "claude", "search", "claude", (method,))
    owner = owned(tool, manager, package="pkg", method=method)
    monkeypatch.setattr(executors, "real_pnpm", lambda: "/fake/pnpm")
    monkeypatch.setattr(update, "resolve_bun", lambda: "/fake/bun")
    monkeypatch.setattr(update, "read_bun_globals", lambda: None)

    def smoke(_manager: str | None) -> None:
        raise executors.ExecutorError("smoke failed")

    monkeypatch.setitem(executors.SMOKE_CHECKS, "puppeteer-browser", smoke)
    calls: list[list[str]] = []
    service = UpdateService(
        platform=FEDORA,
        runner=calls.append,
        managed_packages=lambda: (),
        replay_globals=lambda _: (),
        reresolve_ownership=lambda _: owner,
    )
    deps = run_deps([tool], ctx, service=service, owners={tool.id: owner}, now=lambda: NOW)
    result = vars(schedule_run)["_update_tool"](tool, deps)
    assert (result.line, result.code, result.mutated) == ("failed: smoke failed", 1, True)
    assert calls[0][1:3] == (["add", "-g"] if manager == "pnpm" else ["update", "-g"])
    assert not path_for(deps).exists()
    assert run(deps) == ("failed: smoke failed", 1)
    assert store.read_updated(path_for(deps))[0]["claude"] == store.UpdatedEntry(
        NOW.date(), "update-claude"
    )
    path_for(deps).unlink()

    def fail(argv: list[str]) -> None:
        raise CommandError(argv, 1)

    failing = UpdateService(
        platform=FEDORA,
        runner=fail,
        managed_packages=lambda: (),
        replay_globals=lambda _: (),
        reresolve_ownership=lambda _: owner,
    )
    deps = replace(deps, updates=failing)
    assert vars(schedule_run)["_update_tool"](tool, deps).mutated is False
    assert run(deps)[1] == 1
    assert not path_for(deps).exists()


def test_executor_error_after_mutation_defaults_false() -> None:
    assert executors.ExecutorError("x").after_mutation is False
    assert UpdateOutcome("x", "failed", "brew").mutated is False
    tool = catalog_tool("x")
    owner = owned(tool, "brew", package="x")
    outcome = update.perform_update(
        UpdateTarget(tool, owner),
        platform=FEDORA,
        runner=lambda _: None,
        resolve_tag=lambda _: "v1",
    )
    assert outcome.mutated is True


def test_a_row_records_the_day_of_its_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, service = rig(tmp_path, monkeypatch)
    current = [NOW]
    original = service.run

    def advance(target: UpdateTarget) -> UpdateOutcome:
        current[0] += timedelta(days=1)
        return original(target)

    monkeypatch.setattr(service, "run", advance)
    assert run(replace(deps, now=lambda: current[0]))[1] == 0
    entries, healthy = store.read_updated(path_for(deps))
    assert healthy and store.updated_on(entries, NOW.date()) == {}
    assert store.updated_on(entries, current[0].date()) == {"claude": "update-claude"}


@pytest.mark.parametrize("failure", ["failed", "unsupported", "error", "probe"])
def test_a_failed_or_skipped_result_that_did_not_mutate_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    deps, service = rig(tmp_path, monkeypatch)
    if failure == "error":

        def fail(_target: UpdateTarget) -> UpdateOutcome:
            raise UpdateError("bad")

        monkeypatch.setattr(service, "run", fail)
    elif failure == "probe":
        deps = replace(deps, probe_version=ScriptedProbe({"claude": [OSError("bad")]}))
    elif failure == "failed":
        service.outcomes["claude"] = UpdateOutcome("claude", "failed", "installer", detail="bad")
    else:
        service.outcomes["claude"] = UpdateOutcome(
            "claude", "unsupported", "installer", detail="bad"
        )
    assert run(deps) == (("skipped: bad", 0) if failure == "unsupported" else ("failed: bad", 1))
    assert not path_for(deps).exists()


def test_an_unwritable_record_changes_the_line_not_the_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _ = rig(tmp_path, monkeypatch)
    path = path_for(deps)
    path.mkdir(parents=True)
    assert run(deps) == (
        "ok: updated; updated-today record unreadable; updated-today record not saved",
        0,
    )
    assert path.is_dir()


def test_a_corrupt_record_is_surfaced_and_healed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _ = rig(tmp_path, monkeypatch)
    path = path_for(deps)
    path.parent.mkdir(parents=True)
    path.write_text("bad")
    assert run(deps) == ("ok: updated; updated-today record unreadable", 0)
    assert store.read_updated(path)[1]
    assert run(deps) == ("ok: updated", 0)


def test_a_row_without_a_context_touches_no_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, service = rig(tmp_path, monkeypatch)
    assert run(replace(deps, context=None)) == ("ok: updated", 0)
    assert service.runs == ["claude"] and not path_for(deps).exists()


def test_the_clock_is_injected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, _ = rig(tmp_path, monkeypatch)
    positional = RunDeps(deps.tools, deps.updates, deps.resolve_owner, deps.probe_version, None)
    assert positional.now().utcoffset() is not None
    defaults = {field.name: field.default for field in fields(RunDeps)}
    assert (
        defaults["notify"] is no_notifier
        and defaults["refresh"] is None
        and defaults["git"] is None
    )
