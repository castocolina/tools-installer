"""Offline update-all executor contract."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from installer import cursor_shim, schedule_run, schedules, update_all_state, update_check
from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.model import Method, Tool
from installer.ownership import ManagerInventory, ManagerOwnership, Owner
from installer.platform import Platform
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    decode_manager_snapshot,
    encode_manager_snapshot,
    save_version_cache,
)
from installer.version_status import VersionRefreshService
from installer.versions import VersionError
from tests.update_all_doubles import (
    FEDORA,
    ScriptedProbe,
    SequenceRefresher,
    SpyService,
    catalog_tool,
    owned,
    run_deps,
    run_update_all,
    state,
)
from tests.update_check_doubles import check_context, place_yq, real_service, yq_tool


def test_the_run_updates_managers_then_dependents_in_plan_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tools = [catalog_tool(name) for name in ("brew", "uv", "jq", "ruff")]
    brew, uv, jq, ruff = tools
    owners = {
        "brew": owned(brew, "installer"),
        "uv": owned(uv, "installer"),
        "jq": owned(jq, "brew", package="jq"),
        "ruff": owned(ruff, "uv", package="ruff"),
    }
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "jq": state(jq, "brew", outdated=True),
        "ruff": state(ruff, "uv", outdated=True),
    }
    refresh = SequenceRefresher(tmp_path / "versions.json", [states], clock=lambda: now)
    service = SpyService()
    deps = run_deps(
        tools,
        context,
        service=service,
        owners=owners,
        refresh=refresh,
        now=lambda: now,
        probe=ScriptedProbe({tool.id: ["1", "2"] for tool in tools}),
    )
    assert run_update_all(deps) == ("ok: 4 updated, 0 skipped", 0)
    assert service.runs == ["brew", "uv", "jq", "ruff"]
    assert len(refresh.calls) == 2
    assert len(schedules.update_all_log_path(context).read_text().splitlines()) == 4


def test_a_run_time_refusal_counts_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("jq")
    item = state(tool, "installer", outdated=True)
    service = SpyService({"jq": UpdateOutcome("jq", "unsupported", "installer", "refused")})
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=SequenceRefresher(tmp_path / "versions", [{tool.id: item}], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 0 updated, 1 skipped", 0)
    assert service.runs == ["jq"]
    assert "jq skipped: refused" in schedules.update_all_log_path(context).read_text()
    assert not schedules.updated_today_path(context).exists()


def test_cursor_agent_goes_through_its_shim_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    cursor, other = catalog_tool("cursor-agent"), catalog_tool("jq")
    states = {tool.id: state(tool, "installer", outdated=True) for tool in (cursor, other)}
    seen: list[str] = []
    original_tool = vars(schedule_run)["_update_tool"]

    def cursor_spy(
        row: schedules.Schedule,
        deps: schedule_run.RunDeps,
        ctx: schedules.ScheduleContext,
        *,
        guard: object = None,
    ) -> schedule_run.ToolRun:
        assert ctx == context and callable(guard)
        seen.append(row.id)
        return schedule_run.ToolRun("ok: updated", 0, False)

    def tool_spy(
        tool: Tool, deps: schedule_run.RunDeps, *, guard: object = None
    ) -> schedule_run.ToolRun:
        assert callable(guard)
        seen.append(tool.id)
        return original_tool(tool, deps, guard=guard)

    monkeypatch.setattr(schedule_run, "_update_cursor_agent", cursor_spy)
    monkeypatch.setattr(schedule_run, "_update_tool", tool_spy)
    deps = run_deps(
        [cursor, other],
        context,
        service=SpyService(),
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 2 updated, 0 skipped", 0)
    assert seen == ["update-cursor-agent", "jq"]


def test_the_dispatch_runs_update_all_through_run_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import runlock

    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("brew")
    item = state(tool, "installer")
    service = SpyService()
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=SequenceRefresher(tmp_path / "versions", [{tool.id: item}], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 1 updated, 0 skipped", 0)
    assert runlock.holder(context.lock_path) is None
    assert schedule_run.run_schedule("update-all", deps, parent_holds_lock=False) == (
        "ok: 0 updated, 1 skipped",
        0,
    )
    assert runlock.holder(context.lock_path) is None
    assert schedule_run.run_schedule("tmp-cleanup", deps, parent_holds_lock=False) == (
        "failed: tmp-cleanup is not an update schedule",
        2,
    )
    assert service.runs == ["brew"]


def test_up_to_date_results_count_as_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tools = [catalog_tool(name) for name in ("brew", "uv", "jq", "ruff")]
    brew, uv, jq, ruff = tools
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "jq": state(jq, "brew", outdated=True),
        "ruff": state(ruff, "uv", outdated=True),
    }
    owners = {key: value.ownership for key, value in states.items()}
    service = SpyService()
    deps = run_deps(
        tools,
        context,
        service=service,
        owners=owners,
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
        probe=ScriptedProbe({tool.id: ["1", "1"] for tool in tools}),
    )
    assert run_update_all(deps) == ("ok: 0 updated, 0 skipped; 4 unchanged", 0)
    from installer import update_all_state

    records, healthy = update_all_state.read_updated(schedules.updated_today_path(context))
    assert healthy and set(records) == {"brew", "uv", "jq", "ruff"}


def test_a_failing_manager_skips_each_dependent_with_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tools = [catalog_tool(name) for name in ("brew", "uv", "jq", "yq", "ruff")]
    brew, uv, jq, yq, ruff = tools
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "jq": state(jq, "brew", outdated=True),
        "yq": state(yq, "brew", outdated=True),
        "ruff": state(ruff, "uv", outdated=True),
    }
    service = SpyService({"brew": UpdateOutcome("brew", "failed", "installer", "boom")})
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("failed: 1 failed (brew), 2 updated, 2 skipped", 1)
    assert service.runs == ["brew", "uv", "ruff"]
    lines = schedules.update_all_log_path(context).read_text().splitlines()
    assert [line.split(" ", 2)[1:] for line in lines] == [
        ["brew", "failed: boom"],
        ["uv", "ok: updated"],
        ["jq", "skipped: brew failed"],
        ["yq", "skipped: brew failed"],
        ["ruff", "ok: updated"],
    ]


def test_a_manager_owned_by_a_failed_manager_and_a_requires_chain_cascade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, bun, pnpm, ruff, mmdc, shared, volta = (
        catalog_tool("brew"),
        catalog_tool("uv"),
        catalog_tool("bun"),
        catalog_tool("pnpm"),
        catalog_tool("ruff"),
        catalog_tool("mmdc", requires=("bun",)),
        catalog_tool("shared", requires=("bun",)),
        catalog_tool("volta", update=False),
    )
    tools = [brew, uv, bun, pnpm, ruff, mmdc, shared, volta]
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "brew"),
        "bun": state(bun, "installer"),
        "pnpm": state(pnpm, "installer"),
        "ruff": state(ruff, "uv", outdated=True),
        "mmdc": state(mmdc, "pnpm", outdated=True, method=mmdc.methods[0]),
        "shared": state(shared, "brew", outdated=True),
        "volta": state(volta, "installer"),
    }
    service = SpyService(
        {name: UpdateOutcome(name, "failed", "installer", "boom") for name in ("brew", "bun")}
    )
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    result = run_update_all(deps)
    assert result == ("failed: 2 failed (brew), 1 updated, 5 skipped", 1)
    assert service.runs == ["brew", "bun", "pnpm"]
    lines = schedules.update_all_log_path(context).read_text()
    assert "uv skipped: brew failed" in lines
    assert "ruff skipped: brew failed" in lines
    assert "mmdc skipped: bun failed" in lines
    assert "shared skipped: brew failed" in lines
    assert "volta skipped: no unattended update path" in lines


@pytest.mark.parametrize("brew_fails", [False, True])
def test_requires_failure_names_owner_first_only_when_both_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, brew_fails: bool
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, bun, tool = (
        catalog_tool("brew"),
        catalog_tool("bun"),
        catalog_tool("jq", requires=("bun",)),
    )
    tools = [brew, bun, tool]
    states = {
        "brew": state(brew, "installer"),
        "bun": state(bun, "installer"),
        "jq": state(tool, "brew", outdated=True),
    }
    outcomes = {"bun": UpdateOutcome("bun", "failed", "installer", "boom")}
    if brew_fails:
        outcomes["brew"] = UpdateOutcome("brew", "failed", "installer", "boom")
    service = SpyService(outcomes)
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps)[1] == 1
    assert "jq" not in service.runs
    assert (
        f"jq skipped: {'brew' if brew_fails else 'bun'} failed"
        in schedules.update_all_log_path(context).read_text()
    )


@pytest.mark.parametrize("brew_fails", [False, True])
def test_a_skipped_manager_passes_its_upstream_failure_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, brew_fails: bool
) -> None:
    from installer import update_all_state

    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, ruff = catalog_tool("brew"), catalog_tool("uv"), catalog_tool("ruff")
    tools = [brew, uv, ruff]
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "brew"),
        "ruff": state(ruff, "uv", outdated=True),
    }
    update_all_state.record_updated(
        schedules.updated_today_path(context), "uv", today=now.date(), by="update-all"
    )
    outcomes = {"brew": UpdateOutcome("brew", "failed", "installer", "boom")} if brew_fails else {}
    service = SpyService(outcomes)
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    result = run_update_all(deps)
    assert result[1] == int(brew_fails)
    assert ("ruff" in service.runs) is not brew_fails
    lines = schedules.update_all_log_path(context).read_text()
    assert "uv skipped: updated today" in lines
    if brew_fails:
        assert "ruff skipped: brew failed" in lines


@pytest.mark.parametrize("first_outdated,second_outdated", [(False, True), (True, False)])
def test_the_second_pass_judges_dependents_with_a_refreshed_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_outdated: bool, second_outdated: bool
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, jq = catalog_tool("brew"), catalog_tool("jq")
    first = {"brew": state(brew, "installer"), "jq": state(jq, "brew", outdated=first_outdated)}
    second = {"brew": first["brew"], "jq": state(jq, "brew", outdated=second_outdated)}
    service = SpyService()

    def on_call(index: int) -> None:
        if index == 1:
            assert service.runs == ["brew"]

    refresh = SequenceRefresher(
        tmp_path / "versions", [first, second], clock=lambda: now, on_call=on_call
    )
    deps = run_deps(
        [brew, jq],
        context,
        service=service,
        owners={k: s.ownership for k, s in first.items()},
        refresh=refresh,
        now=lambda: now,
    )
    assert run_update_all(deps)[1] == 0
    assert service.runs == (["brew", "jq"] if second_outdated else ["brew"])


def test_two_skipped_managers_allow_their_dependent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import update_all_state

    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, ruff = catalog_tool("brew"), catalog_tool("uv"), catalog_tool("ruff")
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "brew"),
        "ruff": state(ruff, "uv", outdated=True),
    }
    for name in ("brew", "uv"):
        update_all_state.record_updated(
            schedules.updated_today_path(context), name, today=now.date(), by="update-all"
        )
    service = SpyService()
    deps = run_deps(
        [brew, uv, ruff],
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 1 updated, 2 skipped", 0)
    assert service.runs == ["ruff"]


@pytest.mark.parametrize("still_outdated", [False, True])
def test_a_dependent_the_replay_already_updated_is_not_updated_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, still_outdated: bool
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    pnpm, mmdc = catalog_tool("pnpm"), catalog_tool("mmdc", kind="node")
    first = {
        "pnpm": state(pnpm, "installer"),
        "mmdc": state(mmdc, "pnpm", outdated=True, method=mmdc.methods[0]),
    }
    second = {
        "pnpm": first["pnpm"],
        "mmdc": state(mmdc, "pnpm", outdated=still_outdated, method=mmdc.methods[0]),
    }
    service = SpyService(
        {
            "pnpm": UpdateOutcome(
                "pnpm", "updated", "installer", replayed_globals=("mmdc",), mutated=True
            )
        }
    )
    deps = run_deps(
        [pnpm, mmdc],
        context,
        service=service,
        owners={key: item.ownership for key, item in first.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [first, second], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps)[1] == 0
    assert service.runs == (["pnpm", "mmdc"] if still_outdated else ["pnpm"])


def test_cycle_blocked_managers_do_not_authorize_dependents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, jq = catalog_tool("brew"), catalog_tool("uv"), catalog_tool("jq")
    states = {
        "brew": state(brew, "uv"),
        "uv": state(uv, "brew"),
        "jq": state(jq, "brew", outdated=True),
    }
    service = SpyService()
    deps = run_deps(
        [brew, uv, jq],
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 0 updated, 3 skipped", 0)
    assert service.runs == []
    assert (
        "jq skipped: brew did not run first" in schedules.update_all_log_path(context).read_text()
    )


def test_real_service_runs_no_dependent_argv_after_manager_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, jq = catalog_tool("brew"), catalog_tool("jq")
    states = {"brew": state(brew, "installer"), "jq": state(jq, "brew", outdated=True)}
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> None:
        calls.append(argv)
        raise OSError("boom")

    service = UpdateService(
        platform=FEDORA,
        runner=runner,
        managed_packages=lambda: (),
        replay_globals=lambda _items: (),
        reresolve_ownership=lambda tool: states[tool.id].ownership,
    )
    deps = run_deps(
        [brew, jq],
        context,
        service=service,
        owners={k: s.ownership for k, s in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("failed: 1 failed (brew), 0 updated, 1 skipped", 1)
    assert calls == [["brew", "update"]]
    assert "jq skipped: brew failed" in schedules.update_all_log_path(context).read_text()


def test_executor_refuses_a_dependent_whose_fresh_manager_did_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, ruff = (catalog_tool(name) for name in ("brew", "uv", "ruff"))
    states = {
        "brew": state(brew, "installer", present=False),
        "uv": state(uv, "installer"),
        "ruff": state(ruff, "uv", outdated=True),
    }
    service = SpyService()
    service.fresh["ruff"] = owned(ruff, "brew", package="ruff")
    deps = run_deps(
        [brew, uv, ruff],
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 1 updated, 1 skipped", 0)
    assert service.runs == ["uv"]
    assert (
        "ruff skipped: brew did not run first" in schedules.update_all_log_path(context).read_text()
    )
    records, healthy = update_all_state.read_updated(schedules.updated_today_path(context))
    assert healthy and set(records) == {"uv"}


@pytest.mark.parametrize("second_fails", [False, True])
@pytest.mark.parametrize("fresh_owner", ["brew", "uv"])
def test_evidence_owner_comes_from_the_selected_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, second_fails: bool, fresh_owner: str
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, ruff = (catalog_tool(name) for name in ("brew", "uv", "ruff"))
    first = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "ruff": state(ruff, "uv", outdated=True),
    }
    second = {**first, "ruff": state(ruff, "brew", outdated=True)}
    service = SpyService()
    service.fresh["ruff"] = owned(ruff, "brew" if fresh_owner == "brew" else "uv", package="ruff")
    deps = run_deps(
        [brew, uv, ruff],
        context,
        service=service,
        owners={key: item.ownership for key, item in first.items()},
        refresh=SequenceRefresher(
            tmp_path / "versions",
            [first, second],
            clock=lambda: now,
            raises_on=frozenset({1}) if second_fails else frozenset(),
        ),
        now=lambda: now,
    )
    line, code = run_update_all(deps)
    assert code == 0
    log = schedules.update_all_log_path(context).read_text()
    records, healthy = update_all_state.read_updated(schedules.updated_today_path(context))
    assert healthy
    allowed = fresh_owner == ("uv" if second_fails else "brew")
    expected = "ok: 3 updated, 0 skipped" if allowed else "ok: 2 updated, 1 skipped"
    if second_fails:
        expected += "; second refresh failed; dependents judged on the first pass"
    assert line == expected
    if allowed:
        assert "ruff ok: updated" in log
        assert service.runs == ["brew", "uv", "ruff"] and "ruff" in records
    else:
        assert "ruff skipped: owner changed since the evidence" in log
        assert service.runs == ["brew", "uv"] and "ruff" not in records


def test_the_guard_judges_the_fresh_ownership() -> None:
    tool = catalog_tool("ruff")
    service = SpyService()
    target = UpdateTarget(tool, owned(tool, "uv", package="ruff"))
    guard_class = vars(schedule_run)["_BatchGuard"]
    guard = guard_class(tool, "macos", {"brew": "brew"}, {"uv"}, [tool], "uv")
    service.fresh[tool.id] = owned(tool, "brew", package="ruff")
    outcome = service.run_guarded(target, guard)
    assert (outcome.status, outcome.detail, guard.root) == ("unsupported", "brew failed", "brew")
    assert service.runs == []
    service.fresh[tool.id] = owned(tool, "cask", package="ruff")
    outcome = service.run_guarded(target, guard_class(tool, "macos", {}, set(), [tool], "uv"))
    assert outcome.detail == "cask excluded"
    no_path = catalog_tool("ruff", update=False)
    service.fresh[tool.id] = owned(no_path, "installer")
    outcome = service.run_guarded(target, guard_class(tool, "fedora", {}, set(), [tool], "uv"))
    assert outcome.detail == "no unattended update path"
    service.fresh[tool.id] = owned(tool, "pacman", package="ruff")
    outcome = service.run_guarded(target, guard_class(tool, "fedora", {}, set(), [tool], "uv"))
    assert schedules.update_result_line(outcome, None, None) == ("skipped: pacman owns ruff", 0)
    service.fresh[tool.id] = owned(tool, "uv", package="ruff")
    outcome = service.run_guarded(target, guard_class(tool, "fedora", {}, {"uv"}, [tool], "uv"))
    assert outcome.status == "updated"
    assert service.runs == ["ruff"]


def test_confirmed_evidence_is_bound_to_its_owner() -> None:
    tool = catalog_tool("ruff")
    service = SpyService()
    service.fresh[tool.id] = owned(tool, "brew", package="ruff")
    target = UpdateTarget(tool, owned(tool, "uv", package="ruff"))
    guard_class = vars(schedule_run)["_BatchGuard"]
    outcome = service.run_guarded(
        target, guard_class(tool, "fedora", {}, {"brew", "uv"}, [tool], "uv")
    )
    assert outcome.detail == "owner changed since the evidence"
    outcome = service.run_guarded(
        target, guard_class(tool, "fedora", {"brew": "brew"}, {"uv"}, [tool], "uv")
    )
    assert outcome.detail == "brew failed"
    assert service.runs == []


REAL_GUARD_CASES: list[tuple[Owner, str, dict[str, str], set[str], str, str]] = [
    ("uv", "brew", {"brew": "brew"}, {"uv"}, "fedora", "brew failed"),
    ("brew", "cask", {}, {"brew"}, "macos", "cask excluded"),
    ("installer", "no-path", {}, set(), "fedora", "no unattended update path"),
    ("uv", "os-package", {}, {"uv"}, "fedora", "os-package owns ruff"),
    ("installer", "brew", {}, set(), "fedora", "brew did not run first"),
    ("uv", "brew", {}, {"uv", "brew"}, "fedora", "owner changed since the evidence"),
    ("brew", "brew", {}, {"brew"}, "fedora", ""),
]


@pytest.mark.parametrize("planned,fresh,failed,completed,platform,expected", REAL_GUARD_CASES)
def test_a_real_service_with_changed_ownership_runs_no_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    planned: Owner,
    fresh: str,
    failed: dict[str, str],
    completed: set[str],
    platform: str,
    expected: str,
) -> None:
    context = replace(check_context(tmp_path, monkeypatch), platform_os=platform)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    tool = catalog_tool("ruff")
    planned_owner = owned(tool, planned, package="ruff")
    fresh_owner = (
        owned(catalog_tool("ruff", update=False), "installer")
        if fresh == "no-path"
        else owned(tool, cast(Owner, fresh), package="ruff")
    )
    calls: list[list[str]] = []
    replays: list[object] = []
    actual_platform = (
        FEDORA
        if platform == "fedora"
        else Platform(os="macos", arch="amd64", immutable=False, has_brew=True)
    )
    service = UpdateService(
        platform=actual_platform,
        runner=lambda argv: calls.append(argv.copy()),
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda packages: replays.append(packages) or (),
        reresolve_ownership=lambda _tool: fresh_owner,
    )
    deps = run_deps([tool], context, service=service, owners={tool.id: planned_owner})
    guard = vars(schedule_run)["_BatchGuard"](tool, platform, failed, completed, [tool], planned)
    result = vars(schedule_run)["_update_tool"](tool, deps, guard=guard)
    if expected:
        assert result.line == f"skipped: {expected}"
        assert not result.mutated and calls == []
        assert not schedules.updated_today_path(context).exists()
    else:
        assert result.line.startswith("ok: updated") and result.mutated
        assert calls == [["brew", "upgrade", "ruff"]]
    assert replays == []


@pytest.mark.parametrize(
    "age,offline,confirmed,calls_expected",
    [(18, False, True, 0), (25, True, False, 1), (25, False, True, 1)],
)
def test_a_real_refresh_service_confirms_what_a_real_pass_leaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    age: int,
    offline: bool,
    confirmed: bool,
    calls_expected: int,
) -> None:
    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    place_yq(tmp_path)
    clock = [datetime(2026, 11, 22, tzinfo=UTC)]
    calls: list[str] = []

    def resolve(repo: str) -> str:
        calls.append(repo)
        if offline:
            raise VersionError("offline")
        return "v5.0.0"

    refresh = real_service(tmp_path, resolve_tag=resolve, now=lambda: clock[0], installed="v4.0.0")
    save_version_cache(
        refresh.cache_path,
        {"yq": VersionCacheEntry("v5.0.0", (clock[0] - timedelta(hours=age)).isoformat())},
    )
    tool = yq_tool()
    deps = run_deps(
        [tool],
        context,
        service=SpyService(),
        owners={tool.id: owned(tool, "installer")},
        refresh=refresh,
        now=lambda: clock[0],
    )
    first = vars(schedule_run)["_refresh_pass"](deps)
    assert ("yq" in vars(schedule_run)["_confirmed"](deps, first)) is confirmed
    assert first.states["yq"].version is not None
    assert first.states["yq"].version.stale is offline
    assert len(calls) == calls_expected
    if age == 18:
        clock[0] += timedelta(minutes=5)
        second = vars(schedule_run)["_refresh_pass"](deps)
        assert "yq" in vars(schedule_run)["_confirmed"](deps, second)
        assert calls == []


def test_real_uv_manager_refuses_a_fresh_owner_that_has_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    tool = catalog_tool("uv")
    calls: list[list[str]] = []
    service = UpdateService(
        platform=FEDORA,
        runner=lambda argv: calls.append(argv.copy()),
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda _packages: (),
        reresolve_ownership=lambda _tool: owned(tool, "pnpm", package="uv", method=tool.methods[0]),
    )
    planned = owned(tool, "installer")
    deps = run_deps([tool], context, service=service, owners={tool.id: planned})
    guard = vars(schedule_run)["_BatchGuard"](tool, "fedora", {}, set(), [tool], "installer")
    result = vars(schedule_run)["_update_tool"](tool, deps, guard=guard)
    assert result.line == "skipped: pnpm did not run first"
    assert not result.mutated and calls == []
    assert not schedules.updated_today_path(context).exists()


def test_real_service_failed_manager_blocks_a_changed_owner_in_the_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, ruff = (catalog_tool(name) for name in ("brew", "uv", "ruff"))
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "ruff": state(ruff, "uv", outdated=True),
    }
    owners = {key: item.ownership for key, item in states.items()}
    fresh = {**owners, "ruff": owned(ruff, "brew", package="ruff")}
    calls: list[list[str]] = []
    replays: list[object] = []

    def runner(argv: list[str]) -> None:
        calls.append(argv.copy())
        if argv[0] == "brew":
            raise OSError("boom")

    service = UpdateService(
        platform=FEDORA,
        runner=runner,
        resolve_tag=lambda _repo: "v1",
        managed_packages=lambda: (),
        replay_globals=lambda items: replays.append(items) or (),
        reresolve_ownership=lambda tool: fresh[tool.id],
    )
    deps = run_deps(
        [brew, uv, ruff],
        context,
        service=service,
        owners=owners,
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("failed: 1 failed (brew), 1 updated, 1 skipped", 1)
    assert calls == [["brew", "update"], ["uv", "update"]]
    assert "ruff skipped: brew failed" in schedules.update_all_log_path(context).read_text()
    records, healthy = update_all_state.read_updated(schedules.updated_today_path(context))
    assert healthy and set(records) == {"uv"} and replays == []


def test_real_refresh_partial_manager_failure_confirms_only_the_answering_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "ripgrep"}),),
    )
    uv = Tool(
        id="ruff",
        name="ruff",
        category="search",
        cmd="ruff",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "ruff"}),),
    )
    inventory = ManagerInventory(
        brew_formulae={"ripgrep": "1.0"},
        brew_casks={},
        pnpm_globals=frozenset(),
        uv_tools={"ruff": "1.0"},
        brew_prefix=tmp_path / "brew",
    )
    outdated = OutdatedReport(
        brew={"ripgrep": ManagerVersion("1.0", "2.0")},
        cask={},
        pnpm={},
        uv={"ruff": ManagerVersion("1.0", "2.0")},
    )
    stamp = (now - timedelta(hours=2)).isoformat()
    snapshot = ManagerSnapshot(
        inventory,
        outdated,
        (now - timedelta(hours=7)).isoformat(),
        manager_checked_at={"brew": stamp, "uv": stamp},
    )
    cache = tmp_path / "versions"
    save_version_cache(cache, {}, managers=encode_manager_snapshot(snapshot))

    def read_inventory(**_kwargs: object) -> ManagerInventory:
        return replace(inventory, brew_formulae=None)

    def read_outdated(**_kwargs: object) -> OutdatedReport:
        return replace(outdated, brew=None)

    service = VersionRefreshService(
        platform=Platform(os="macos", arch="amd64", immutable=False, has_brew=True),
        cache_path=cache,
        now=lambda: now,
        home=tmp_path,
        managed_bin_dir=tmp_path / "bin",
        which=lambda cmd: str(tmp_path / "brew/bin" / cmd) if cmd in ("rg", "brew") else None,
        artifacts_for=lambda _tool: [],
        read_inventory_fn=read_inventory,
        read_outdated_fn=read_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        bun_versions=lambda: {},
        query=lambda *_args, **_kwargs: "",
        probe_output=lambda _argv: "1.0",
    )
    deps = run_deps(
        [brew, uv],
        context,
        service=SpyService(),
        owners={brew.id: owned(brew, "brew"), uv.id: owned(uv, "uv")},
        refresh=service,
        now=lambda: now,
    )
    result = vars(schedule_run)["_refresh_pass"](deps)
    assert result.snapshot is not None and result.snapshot.failed_at is not None
    assert result.states["rg"].version is not None and result.states["rg"].version.source == "brew"
    assert (
        result.states["ruff"].version is not None and result.states["ruff"].version.source == "uv"
    )
    assert vars(schedule_run)["_confirmed"](deps, result) == frozenset({"ruff"})


def test_guard_precedes_receipts_capture_and_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = catalog_tool("pnpm")
    fresh = owned(tool, "installer")
    calls: list[str] = []

    def forbidden() -> tuple[str, ...]:
        calls.append("capture")
        return ()

    def invalidate(*, reason: str) -> int:
        calls.append(reason)
        return 0

    service = UpdateService(
        platform=FEDORA,
        managed_packages=forbidden,
        replay_globals=lambda _items: (),
        reresolve_ownership=lambda _tool: fresh,
        runner=lambda _argv: calls.append("run"),
        invalidate=invalidate,
    )
    refusal = UpdateOutcome(tool.id, "unsupported", "installer", "blocked")
    seen: list[object] = []

    def guard(owner: object) -> UpdateOutcome:
        seen.append(owner)
        return refusal

    assert service.run_guarded(UpdateTarget(tool, owned(tool, "brew")), guard) is refusal
    assert seen == [fresh]
    assert calls == []


def test_a_guarded_cursor_skip_touches_no_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    models: list[Path] = []
    from dataclasses import replace

    def read_models(path: Path) -> tuple[str, ...]:
        models.append(path)
        return ()

    context = replace(context, read_models=read_models)
    agent = tmp_path / ".local/bin/agent"
    agent.parent.mkdir(parents=True)
    agent.write_text("agent")
    tool = catalog_tool("cursor-agent")
    owner = owned(tool, "installer")
    service = SpyService()
    deps = run_deps([tool], context, service=service, owners={tool.id: owner})
    refusal = UpdateOutcome(tool.id, "unsupported", "installer", "blocked")
    run_cursor = vars(schedule_run)["_update_cursor_agent"]
    row = schedules.schedule_by_id("update-cursor-agent")
    link, _ = cursor_shim.shim_paths(context.home)

    def refuse(_owner: ManagerOwnership) -> UpdateOutcome:
        return refusal

    def allow(_owner: ManagerOwnership) -> None:
        return None

    result = run_cursor(row, deps, context, guard=refuse)
    assert result.line == "skipped: blocked"
    assert models == []
    assert not link.exists()
    assert not context.state_path.exists()
    result = run_cursor(row, deps, context, guard=allow)
    assert result.line.startswith("ok: updated")
    assert models == [agent]


def test_manager_not_completed_and_transitive_failure_are_guarded() -> None:
    uv = catalog_tool("uv")
    ruff = catalog_tool("ruff")
    guard_class = vars(schedule_run)["_BatchGuard"]
    guard = guard_class(uv, "fedora", {}, {"brew"}, [uv, ruff], "brew")
    outcome = guard(owned(uv, "brew"))
    assert outcome is None
    guard = guard_class(uv, "fedora", {}, set(), [uv, ruff], "brew")
    outcome = guard(owned(uv, "brew"))
    assert outcome is not None
    assert outcome.detail == "brew did not run first"
    assert guard.refused
    guard = guard_class(ruff, "fedora", {"uv": "brew"}, set(), [uv, ruff], "uv")
    outcome = guard(owned(ruff, "uv"))
    assert outcome is not None
    assert outcome.detail == "brew failed"
    assert guard.root == "brew"
    guard = guard_class(ruff, "fedora", {}, set(), [uv, ruff], "uv")
    outcome = guard(owned(ruff, "uv"))
    assert outcome is not None
    assert outcome.detail == "uv did not run first"


@pytest.mark.parametrize(
    "source,age,stale,failed_age,stamp_age,expected",
    [
        ("github", 0, True, None, None, False),
        ("github", 21, False, None, None, False),
        ("github", 18, False, None, None, True),
        ("brew", 0, False, None, 7, False),
        ("brew", 0, False, 1, 2, False),
        ("brew", 0, False, None, 2, True),
        ("uv", 0, False, 2, 2, True),
        ("brew", 0, False, 1, None, False),
    ],
)
def test_unconfirmed_evidence_never_authorizes_an_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    age: int,
    stale: bool,
    failed_age: int | None,
    stamp_age: int | None,
    expected: bool,
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("jq")
    item = state(tool, "installer", outdated=True)
    assert item.version is not None
    item = replace(item, version=replace(item.version, source=source, stale=stale))
    snapshot = decode_manager_snapshot(
        {
            "checked_at": now.isoformat(),
            "failed_at": (now - timedelta(hours=failed_age)).isoformat()
            if failed_age is not None
            else None,
            "manager_checked_at": {source: (now - timedelta(hours=stamp_age)).isoformat()}
            if stamp_age is not None
            else {},
        }
    )
    service = SpyService()
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=SequenceRefresher(
            tmp_path / "versions",
            [{tool.id: item}],
            clock=lambda: now,
            ages=[{tool.id: timedelta(hours=age)}],
            snapshots=[snapshot],
        ),
        now=lambda: now,
    )
    assert run_update_all(deps) == (
        ("ok: 1 updated, 0 skipped" if expected else "ok: 0 updated, 1 skipped"),
        0,
    )
    assert service.runs == (["jq"] if expected else [])
    if not expected:
        assert (
            "jq skipped: latest version not confirmed"
            in schedules.update_all_log_path(context).read_text()
        )
    assert vars(update_check)["_MANAGER_SOURCES"] == schedule_run.MANAGER_SOURCES


def test_the_second_pass_confirms_evidence_the_first_pass_did_not_refetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    initial = datetime(2026, 11, 22, tzinfo=UTC)
    clock = [initial]
    tool = catalog_tool("jq")
    item = state(tool, "installer", outdated=True)
    service = SpyService()

    def advance(index: int) -> None:
        if index == 1:
            clock[0] += timedelta(minutes=5)

    refresh = SequenceRefresher(
        tmp_path / "versions",
        [{tool.id: item}],
        clock=lambda: clock[0],
        ages=[{tool.id: timedelta()}, {tool.id: timedelta(minutes=5)}],
        on_call=advance,
    )
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=refresh,
        now=lambda: clock[0],
    )
    assert run_update_all(deps) == ("ok: 1 updated, 0 skipped", 0)
    assert service.runs == ["jq"]


def test_a_failed_first_refresh_ends_the_run_without_updating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("brew")
    item = state(tool, "installer")
    service = SpyService()
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=SequenceRefresher(
            tmp_path / "versions", [{tool.id: item}], clock=lambda: now, raises_on=frozenset({0})
        ),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("failed: refresh failed", 1)
    assert service.runs == []
    assert not schedules.update_all_log_path(context).exists()
    assert not schedules.updated_today_path(context).exists()


def test_a_failed_second_refresh_falls_back_to_the_first_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, jq, ruff, stale, backfill = (
        catalog_tool(name) for name in ("brew", "uv", "jq", "ruff", "stale", "backfill")
    )
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer", present=False),
        "jq": state(jq, "brew", outdated=True),
        "ruff": state(ruff, "uv", outdated=True),
        "stale": state(stale, "installer", outdated=True),
        "backfill": state(backfill, "installer", outdated=True),
    }
    for name, source in (("jq", "brew"), ("ruff", "uv"), ("backfill", "pnpm")):
        item = states[name]
        assert item.version is not None
        states[name] = replace(item, version=replace(item.version, source=source))
    snapshot = decode_manager_snapshot(
        {
            "checked_at": now.isoformat(),
            "failed_at": now.isoformat(),
            "manager_checked_at": {
                "brew": now.isoformat(),
                "uv": now.isoformat(),
                "pnpm": (now - timedelta(hours=1)).isoformat(),
            },
        }
    )
    from installer import update_all_state

    # A skipped manager is completed without mutating, allowing the fallback control to run.
    states["uv"] = state(uv, "installer")
    update_all_state.record_updated(
        schedules.updated_today_path(context), "uv", today=now.date(), by="update-all"
    )
    service = SpyService()
    deps = run_deps(
        [brew, uv, jq, ruff, stale, backfill],
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(
            tmp_path / "versions",
            [states],
            clock=lambda: now,
            ages=[{"ruff": timedelta(), "stale": timedelta(hours=21)}],
            snapshots=[snapshot],
            raises_on=frozenset({1}),
        ),
        now=lambda: now,
    )
    line, code = run_update_all(deps)
    assert code == 0
    assert (
        line
        == "ok: 2 updated, 4 skipped; second refresh failed; dependents judged on the first pass"
    )
    assert service.runs == ["brew", "ruff"]
    log = schedules.update_all_log_path(context).read_text()
    for name in ("jq", "stale", "backfill"):
        assert f"{name} skipped: latest version not confirmed" in log


def test_the_run_log_has_one_line_per_tool_in_run_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, jq, yq, zed = (catalog_tool(name) for name in ("brew", "jq", "yq", "zed"))
    states = {
        "brew": state(brew, "installer"),
        "jq": state(jq, "brew", outdated=True),
        "yq": state(yq, "brew", outdated=True),
        "zed": state(zed, "installer", outdated=True),
    }
    update_all_state.record_updated(
        schedules.updated_today_path(context), "yq", today=now.date(), by="update-claude"
    )
    service = SpyService()
    deps = run_deps(
        [brew, jq, yq, zed],
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 3 updated, 1 skipped", 0)
    path = schedules.update_all_log_path(context)
    assert path.read_text().splitlines() == [
        "2026-11-22T00:00:00+00:00 brew ok: updated",
        "2026-11-22T00:00:00+00:00 jq ok: updated",
        "2026-11-22T00:00:00+00:00 yq skipped: updated today",
        "2026-11-22T00:00:00+00:00 zed ok: updated",
    ]
    assert run_update_all(deps) == ("ok: 0 updated, 4 skipped", 0)
    assert len(path.read_text().splitlines()) == 4
    schedules.updated_today_path(context).unlink()
    empty = replace(
        deps, tools=[], refresh=SequenceRefresher(tmp_path / "versions", [{}], clock=lambda: now)
    )
    assert run_update_all(empty) == ("ok: 0 updated", 0)
    assert path.read_bytes() == b""
    assert not schedules.updated_today_path(context).exists()


def test_the_day_is_judged_at_each_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    clock = [datetime(2026, 11, 22, 23, 59, tzinfo=UTC)]
    first, second, third = (catalog_tool(name) for name in ("alpha", "beta", "gamma"))
    states = {tool.id: state(tool, "installer", outdated=True) for tool in (first, second, third)}
    store = schedules.updated_today_path(context)
    for tool in (second, third):
        update_all_state.record_updated(store, tool.id, today=clock[0].date(), by="update-claude")

    class MidnightService(SpyService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            result = super().run(target)
            if target.tool.id == "alpha":
                clock[0] += timedelta(minutes=2)
            return result

    service = MidnightService()
    deps = run_deps(
        [first, second, third],
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(
            tmp_path / "versions",
            [states],
            clock=lambda: clock[0],
            ages=[{"alpha": timedelta(), "beta": timedelta()}],
        ),
        now=lambda: clock[0],
    )
    assert run_update_all(deps) == ("ok: 2 updated, 1 skipped", 0)
    assert service.runs == ["alpha", "beta"]
    log = schedules.update_all_log_path(context).read_text()
    assert "gamma skipped: latest version not confirmed" in log
    records, healthy = update_all_state.read_updated(store)
    assert healthy and records["beta"].day == clock[0].date()
    assert run_update_all(deps) == ("ok: 0 updated, 3 skipped", 0)
    assert service.runs == ["alpha", "beta"]


def test_the_record_is_written_and_read_in_both_directions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = [datetime(2026, 11, 22, tzinfo=UTC)]
    brew, uv, jq = (catalog_tool(name) for name in ("brew", "uv", "jq"))
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "jq": state(jq, "brew", outdated=True),
    }
    store = schedules.updated_today_path(context)
    update_all_state.record_updated(store, "jq", today=now[0].date(), by="update-claude")
    service = SpyService()
    refresh = SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now[0])
    deps = run_deps(
        [brew, uv, jq],
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=refresh,
        now=lambda: now[0],
    )
    assert run_update_all(deps) == ("ok: 2 updated, 1 skipped", 0)
    records, healthy = update_all_state.read_updated(store)
    assert healthy and records["jq"].by == "update-claude"
    assert records["brew"].by == records["uv"].by == "update-all"
    assert run_update_all(deps) == ("ok: 0 updated, 3 skipped", 0)
    assert service.runs == ["brew", "uv"]
    now[0] += timedelta(days=1)
    assert run_update_all(deps) == ("ok: 3 updated, 0 skipped", 0)
    assert service.runs == ["brew", "uv", "brew", "uv", "jq"]


def test_a_mutation_followed_by_a_failing_probe_is_recorded_and_counted_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tools = [catalog_tool(name) for name in ("alpha", "beta", "gamma")]
    states = {tool.id: state(tool, "installer", outdated=True) for tool in tools}
    service = SpyService(
        {
            "beta": UpdateOutcome("beta", "failed", "installer", "smoke", mutated=True),
            "gamma": UpdateOutcome("gamma", "failed", "installer", "boom"),
        }
    )
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
        probe=ScriptedProbe({"alpha": ["1", OSError("probe")]}),
    )
    assert run_update_all(deps) == ("failed: 3 failed (alpha), 0 updated, 0 skipped", 1)
    records, healthy = update_all_state.read_updated(schedules.updated_today_path(context))
    assert healthy and set(records) == {"alpha", "beta"}
    assert all(item.by == "update-all" for item in records.values())


def test_the_record_is_written_and_read_in_the_same_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = check_context(tmp_path, monkeypatch)
    clock = [datetime(2026, 11, 22, 23, 59, tzinfo=UTC)]
    tools = [catalog_tool(name) for name in ("alpha", "beta", "gamma")]
    states = {tool.id: state(tool, "installer", outdated=True) for tool in tools}
    store = schedules.updated_today_path(context)

    class InterruptingService(SpyService):
        def run(self, target: UpdateTarget) -> UpdateOutcome:
            if target.tool.id == "gamma":
                records, healthy = update_all_state.read_updated(store)
                assert healthy and set(records) == {"beta"}
                assert records["beta"].day == clock[0].date()
                raise KeyboardInterrupt
            if target.tool.id == "beta":
                records, healthy = update_all_state.read_updated(store)
                assert healthy and records["alpha"].day == clock[0].date()
                clock[0] += timedelta(minutes=2)
            return super().run(target)

    service = InterruptingService()
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: clock[0]),
        now=lambda: clock[0],
    )
    with pytest.raises(KeyboardInterrupt):
        run_update_all(deps)
    records, healthy = update_all_state.read_updated(store)
    assert healthy and records["beta"].by == "update-all"
    assert service.runs == ["alpha", "beta"]


@pytest.mark.parametrize("broken", ["directory", "corrupt", "log"])
def test_degraded_deduplication_is_named_once_and_keeps_the_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    context = check_context(tmp_path, monkeypatch)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("brew")
    item = state(tool, "installer")
    store = schedules.updated_today_path(context)
    log = schedules.update_all_log_path(context)
    path = log if broken == "log" else store
    path.parent.mkdir(parents=True, exist_ok=True)
    if broken == "corrupt":
        path.write_text("bad")
    else:
        path.mkdir()
    service = SpyService()
    refresh = SequenceRefresher(tmp_path / "versions", [{tool.id: item}], clock=lambda: now)
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=refresh,
        now=lambda: now,
    )
    line, code = run_update_all(deps)
    assert code == 0 and service.runs == ["brew"]
    assert line.count("updated-today record unreadable") == int(broken != "log")
    assert line.count("updated-today record not saved") == int(broken == "directory")
    assert line.count("run log not saved") == int(broken == "log")
    if broken == "corrupt":
        assert update_all_state.read_updated(store)[1]
