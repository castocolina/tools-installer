"""Offline preview and run agreement."""

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

import setup
from installer import (
    receipts,
    runlock,
    schedule_run,
    schedules,
    update_all,
    update_all_state,
    update_check,
    version_cache,
)
from installer.model import Tool
from installer.ownership import ManagerOwnership, Owner
from installer.platform import Platform
from installer.run import run_captured_in_group
from installer.version_cache import (
    ManagerSnapshot,
    VersionCacheEntry,
    decode_manager_snapshot,
    save_version_cache,
)
from installer.version_status import FailureSink, ToolState, VersionRefreshService
from tests.compose_patch import patch_composition
from tests.update_all_doubles import (
    SequenceRefresher,
    SpyService,
    WindowRefresher,
    catalog_tool,
    run_deps,
    run_update_all,
    state,
)
from tests.update_check_doubles import (
    YQ_SHA,
    FakeNotifier,
    check_context,
    place_yq,
    place_yq_with_receipt,
    real_service,
    yq_tool,
)

NOW = datetime(2026, 11, 22, tzinfo=UTC)


def rig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: tuple[str, ...] = ("brew", "uv", "jq")
) -> tuple[schedule_run.RunDeps, SequenceRefresher, SpyService, FakeNotifier, dict[str, ToolState]]:
    context = check_context(tmp_path, monkeypatch)
    tools = [catalog_tool(name) for name in names]
    states = {
        t.id: state(t, "brew" if t.id == "jq" else "installer", outdated=t.id == "jq")
        for t in tools
    }
    refresh = SequenceRefresher(tmp_path / "versions", [states], clock=lambda: NOW)
    service = SpyService()
    notifier = FakeNotifier()
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={k: v.ownership for k, v in states.items()},
        refresh=refresh,
        now=lambda: NOW,
        notify=notifier,
    )
    return deps, refresh, service, notifier, states


def owners_for(states: dict[str, ToolState], tool: Tool) -> ManagerOwnership:
    return states[tool.id].ownership


def test_the_plan_prints_managers_dependents_note_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _, _, _, _ = rig(tmp_path, monkeypatch)
    assert schedule_run.plan_update_all(deps) == (
        (
            "brew (managers): would update",
            "uv (managers): would update",
            "jq (brew): would update",
            update_all.PLAN_NOTE,
            "ok: plan 3 to update, 0 skipped",
        ),
        0,
    )
    for names in (("brew",), ("jq",), ()):
        other, _, _, _, _ = rig(tmp_path, monkeypatch, names)
        lines, code = schedule_run.plan_update_all(other)
        assert code == 0 and lines[-2] == update_all.PLAN_NOTE
        if not names:
            assert lines == (update_all.PLAN_NOTE, "ok: plan 0 to update, 0 skipped")


def test_plan_equals_run_order_and_skip_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, refresh, _, _, states = rig(
        tmp_path, monkeypatch, ("brew", "uv", "jq", "ruff", "yq", "zed")
    )
    tools = {t.id: t for t in deps.tools}
    states.update(
        {
            "ruff": state(tools["ruff"], "uv", outdated=True),
            "yq": state(tools["yq"], "brew", outdated=True),
            "zed": state(tools["zed"], "pacman", outdated=True),
        }
    )
    refresh.passes = [states]
    deps = replace(deps, resolve_owner=partial(owners_for, states))
    assert deps.context is not None
    update_all_state.record_updated(
        schedules.updated_today_path(deps.context), "yq", today=NOW.date(), by="update-claude"
    )
    lines, code = schedule_run.plan_update_all(deps)
    assert code == 0
    preview = [
        (s.split(":", 1)[0], "skip", s.split("skipped: ", 1)[1])
        if ": skipped: " in s
        else (s.split(" ", 1)[0], "update", "")
        for s in lines[:-2]
    ]
    assert all("failed" not in s and "busy" not in s for s in lines)
    assert run_update_all(deps)[1] == 0
    log = schedules.update_all_log_path(deps.context).read_text().splitlines()
    actual = [
        (p[1], "skip", p[2][9:]) if p[2].startswith("skipped: ") else (p[1], "update", "")
        for line in log
        if (p := line.split(" ", 2))
    ]
    assert preview == actual


def test_plan_mode_takes_no_lock_runs_nothing_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _, service, notifier, _ = rig(tmp_path, monkeypatch)
    assert deps.context is not None
    lock = runlock.try_acquire(deps.context.lock_path, "update-claude")
    assert lock is not None
    try:
        target = tmp_path / "state-target"
        target.write_bytes(b"unchanged state")
        link = tmp_path / "state-link"
        link.symlink_to(target.name)
        before = snapshot_home(tmp_path)
        assert before["state-link"] == b"state-target"
        assert before["state-target"] == b"unchanged state"
        result = schedule_run.plan_update_all(deps)
        assert schedule_run.plan_update_all(deps) == result
        assert snapshot_home(tmp_path) == before
        assert not schedules.update_all_log_path(deps.context).exists()
        assert not schedules.updated_today_path(deps.context).exists()
        assert service.runs == [] and notifier.calls == []
    finally:
        lock.release()


def test_plan_mode_refreshes_with_the_cached_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, refresh, _, _, _ = rig(tmp_path, monkeypatch)
    assert schedule_run.plan_update_all(deps)[1] == 0
    assert [c[1] for c in refresh.calls] == [version_cache.STALE_AFTER]
    assert run_update_all(deps)[1] == 0
    assert [c[1] for c in refresh.calls[1:]] == [update_check.CHECK_STALE_AFTER] * 2


def test_a_failed_refresh_prints_failed_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, refresh, _, _, _ = rig(tmp_path, monkeypatch)
    refresh.raises_on = frozenset({0})
    assert schedule_run.plan_update_all(deps) == (("failed: refresh failed",), 1)
    assert schedule_run.plan_update_all(replace(deps, refresh=None)) == (
        ("failed: update-all is not wired",),
        2,
    )


def test_a_receipt_drift_tool_is_skipped_at_plan_time_and_the_note_covers_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, refresh, service, _, states = rig(tmp_path, monkeypatch, ("jq", "zed"))
    tools = {t.id: t for t in deps.tools}
    states["jq"] = replace(
        state(tools["jq"], "installer", outdated=True), reasons=(receipts.CHANGED_SINCE_INSTALL,)
    )
    states["zed"] = state(tools["zed"], "installer", outdated=True)
    refresh.passes = [states]
    deps = replace(deps, resolve_owner=partial(owners_for, states))
    lines, _ = schedule_run.plan_update_all(deps)
    assert "jq: skipped: jq is broken: changed since install" in lines
    assert "zed (installer): would update" in lines and lines[-2] == update_all.PLAN_NOTE
    assert "checks installed files again" in lines[-2]
    assert run_update_all(deps)[1] == 0
    assert deps.context is not None
    assert (
        "jq skipped: jq is broken: changed since install"
        in schedules.update_all_log_path(deps.context).read_text()
    )
    assert service.runs == ["zed"]


@pytest.mark.parametrize("age", [timedelta(days=2), timedelta(hours=18)])
def test_a_newer_failed_release_lookup_is_not_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, age: timedelta
) -> None:
    deps, refresh, service, _, states = rig(tmp_path, monkeypatch, ("jq",))
    tool = deps.tools[0]
    states["jq"] = state(tool, "installer", outdated=True)
    original = refresh.refresh

    def failed(
        tools: Sequence[Tool], *, stale_after: timedelta, on_failure: FailureSink | None
    ) -> tuple[dict[str, ToolState], dict[str, VersionCacheEntry], ManagerSnapshot | None]:
        result, entries, snapshot = original(tools, stale_after=stale_after, on_failure=on_failure)
        entries["jq"] = VersionCacheEntry(
            "2", (NOW - age).isoformat(), failed_at=(NOW - age / 2).isoformat()
        )
        return result, entries, snapshot

    monkeypatch.setattr(refresh, "refresh", failed)
    lines, _ = schedule_run.plan_update_all(deps)
    assert "jq: skipped: latest version not confirmed" in lines
    assert run_update_all(deps)[1] == 0
    assert deps.context is not None
    assert (
        "jq skipped: latest version not confirmed"
        in schedules.update_all_log_path(deps.context).read_text()
    )
    assert service.runs == []


@pytest.mark.parametrize("failed", [False, True])
def test_two_day_old_release_confirmation_depends_on_window_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    deps, refresh, _, _, states = rig(tmp_path, monkeypatch, ("jq",))
    states["jq"] = state(deps.tools[0], "installer", outdated=True)
    original = refresh.refresh

    def aged(
        tools: Sequence[Tool], *, stale_after: timedelta, on_failure: FailureSink | None
    ) -> tuple[dict[str, ToolState], dict[str, VersionCacheEntry], ManagerSnapshot | None]:
        result, entries, snapshot = original(tools, stale_after=stale_after, on_failure=on_failure)
        entries["jq"] = VersionCacheEntry(
            "2",
            (NOW - timedelta(days=2)).isoformat(),
            failed_at=(NOW - timedelta(days=1)).isoformat() if failed else None,
        )
        return result, entries, snapshot

    monkeypatch.setattr(refresh, "refresh", aged)
    refresh_pass = vars(schedule_run)["_refresh_pass"](deps, stale_after=version_cache.STALE_AFTER)
    confirmed = vars(schedule_run)["_confirmed"]
    assert "jq" not in confirmed(deps, refresh_pass, stale_after=update_check.CHECK_STALE_AFTER)
    preview_confirmed = confirmed(deps, refresh_pass, stale_after=version_cache.STALE_AFTER)
    assert ("jq" in preview_confirmed) is not failed
    lines, code = schedule_run.plan_update_all(deps)
    assert code == 0
    expected = (
        "jq: skipped: latest version not confirmed" if failed else "jq (installer): would update"
    )
    assert expected in lines


def test_a_failed_manager_lookup_is_not_a_would_update_in_the_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, refresh, service, _, states = rig(tmp_path, monkeypatch, ("brew", "uv", "jq", "ruff"))
    tools = {t.id: t for t in deps.tools}
    pairs: tuple[tuple[str, Owner], ...] = (("jq", "brew"), ("ruff", "uv"))
    for name, owner in pairs:
        item = state(tools[name], owner, outdated=True)
        assert item.version is not None
        states[name] = replace(item, version=replace(item.version, source=owner))
    refresh.snapshots = [
        decode_manager_snapshot(
            {
                "checked_at": NOW.isoformat(),
                "failed_at": (NOW - timedelta(hours=1)).isoformat(),
                "manager_checked_at": {
                    "brew": (NOW - timedelta(hours=2)).isoformat(),
                    "uv": NOW.isoformat(),
                },
            }
        )
    ]
    deps = replace(deps, resolve_owner=partial(owners_for, states))
    lines, _ = schedule_run.plan_update_all(deps)
    assert "jq: skipped: latest version not confirmed" in lines
    assert "ruff (uv): would update" in lines
    assert run_update_all(deps)[1] == 0
    assert deps.context is not None
    assert (
        "jq skipped: latest version not confirmed"
        in schedules.update_all_log_path(deps.context).read_text()
    )
    assert "ruff" in service.runs


@pytest.mark.parametrize("manager_present", [True, False])
def test_differing_evidence_the_preview_explains_its_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manager_present: bool
) -> None:
    names = ("brew", "jq") if manager_present else ("jq",)
    deps, _, service, _, states = rig(tmp_path, monkeypatch, names)
    jq = next(tool for tool in deps.tools if tool.id == "jq")
    owner: Owner = "brew" if manager_present else "installer"
    states["jq"] = state(jq, owner, outdated=True)
    cached = {**states, "jq": state(jq, owner, outdated=False)}
    refresh = WindowRefresher(
        tmp_path / "versions",
        [cached, states],
        clock=lambda: NOW,
        ages=[{"jq": timedelta(days=2)}, {"jq": timedelta()}],
    )
    deps = replace(deps, refresh=refresh, resolve_owner=partial(owners_for, states))
    lines, _ = schedule_run.plan_update_all(deps)
    assert not any(line.startswith("jq") for line in lines)
    if not manager_present:
        assert not any("(managers): would update" in line for line in lines)
    assert update_all.PLAN_NOTE in lines
    assert run_update_all(deps)[1] == 0 and "jq" in service.runs


def test_setup_routes_plan_mode_without_running_the_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    deps, _, _, _, _ = rig(tmp_path, monkeypatch)
    seen: list[object] = []

    def fake_deps(
        _tools: list[Tool], _platform: Platform, **kwargs: object
    ) -> schedule_run.RunDeps:
        seen.append(kwargs)
        return deps

    @contextmanager
    def closed() -> Generator[None]:
        seen.append("closed")
        yield

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected run")

    monkeypatch.setattr(setup, "_schedule_run_deps", fake_deps)
    monkeypatch.setattr(setup, "run_schedule", forbidden)
    monkeypatch.setattr(setup, "_settings_store", forbidden)
    monkeypatch.setattr(setup, "update_all_stdin_closed", closed)
    expected, _ = schedule_run.plan_update_all(deps)
    assert setup.main(["--run-schedule", "update-all", "--plan"]) == 0
    assert capsys.readouterr().out == "\n".join(expected) + "\n"
    assert seen == ["closed", {"hold_writes": True}]

    calls: list[tuple[str, bool]] = []

    def run(schedule_id: str, run_deps: schedule_run.RunDeps, **kwargs: object) -> tuple[str, int]:
        assert run_deps is deps
        calls.append((schedule_id, bool(kwargs["parent_holds_lock"])))
        return "ok: manual run", 0

    monkeypatch.setattr(setup, "run_schedule", run)

    def settings(_mode: object) -> tuple[SimpleNamespace, bool]:
        return SimpleNamespace(link_mode="copy"), False

    def ignore(_fn: object) -> None:
        pass

    monkeypatch.setattr(setup, "_settings_store", settings)
    monkeypatch.setattr(setup.post_install, "use_shell_init_sourcing", ignore)
    monkeypatch.setattr(setup.post_install, "use_git_runner", ignore)
    assert setup.main(["--run-schedule", "update-all"]) == 0
    assert capsys.readouterr().out == "ok: manual run\n"
    assert calls == [("update-all", False)]


def test_schedule_run_deps_holds_writes_only_on_request(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    class Refresh:
        def hold_writes(self) -> None:
            seen.append("held")

        def resolve_owner(self, tool: Tool) -> ManagerOwnership:
            raise AssertionError(tool.id)

    refresh = Refresh()

    def build(tools: list[Tool], platform: Platform, **kwargs: object) -> tuple[object, ...]:
        seen.append(kwargs)
        return refresh, SpyService(), None, None

    patch_composition(monkeypatch, "_build_services", build)
    from tests.update_all_doubles import FEDORA

    vars(setup)["_schedule_run_deps"]([], FEDORA, hold_writes=True)
    vars(setup)["_schedule_run_deps"]([], FEDORA)
    assert seen == [{"runner": run_captured_in_group}, "held", {"runner": run_captured_in_group}]


def real_plan_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> tuple[Path, schedule_run.RunDeps, list[str]]:
    home = tmp_path / "home"
    home.mkdir()
    context = check_context(home, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(
        receipts, "receipts_dir", lambda: home / ".local/state/tools-installer/receipts"
    )
    if scenario == "adopt":
        place_yq(home)
    else:
        placed = place_yq_with_receipt(home)
        if scenario == "retire":
            placed.unlink()
    lookups: list[str] = []

    def resolve(repo: str) -> str:
        lookups.append(repo)
        return "v5.0.0"

    refresh = real_service(home, resolve_tag=resolve, now=lambda: NOW, installed="v4.0.0")
    save_version_cache(
        refresh.cache_path,
        {
            "yq": VersionCacheEntry(
                "v5.0.0",
                (NOW - timedelta(days=0 if scenario == "adopt" else 8)).isoformat(),
                digests={"yq_linux_amd64": YQ_SHA} if scenario == "adopt" else {},
            )
        },
    )
    deps = run_deps(
        [yq_tool()], context, service=SpyService(), owners={}, refresh=refresh, now=lambda: NOW
    )
    return home, deps, lookups


def snapshot_home(home: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(home)): (str(p.readlink()).encode() if p.is_symlink() else p.read_bytes())
        for p in home.rglob("*")
        if p.is_file() or p.is_symlink()
    }


@pytest.mark.parametrize("scenario", ["plain", "adopt", "retire"])
def test_plan_mode_with_the_real_refresh_service_writes_no_installer_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    home, deps, lookups = real_plan_fixture(tmp_path, monkeypatch, scenario)
    refresh = deps.refresh
    assert isinstance(refresh, VersionRefreshService)
    target = refresh.cache_path.with_name("versions-target.json")
    if scenario == "plain":
        cache = refresh.cache_path
        cache.rename(target)
        cache.symlink_to(target.name)
    commits: list[bool] = []
    original = refresh.commit_writes

    def commit() -> list[str]:
        commits.append(True)
        return original()

    monkeypatch.setattr(refresh, "commit_writes", commit)
    refresh.hold_writes()
    before = snapshot_home(home)
    if scenario == "plain":
        cache_key = str(refresh.cache_path.relative_to(home))
        assert before[cache_key] == b"versions-target.json"
        assert before[str(target.relative_to(home))] == target.read_bytes()
    result = schedule_run.plan_update_all(deps)
    assert result[1] == 0
    assert snapshot_home(home) == before
    assert schedule_run.plan_update_all(deps) == result
    assert snapshot_home(home) == before
    assert commits == []
    if scenario in ("plain", "retire"):
        assert lookups == ["mikefarah/yq", "mikefarah/yq"]


@pytest.mark.parametrize("scenario", ["plain", "adopt", "retire"])
def test_the_same_scenarios_do_write_without_holding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    home, deps, lookups = real_plan_fixture(tmp_path, monkeypatch, scenario)
    cache = home / ".local/state/tools-installer/versions.json"
    receipt = home / ".local/state/tools-installer/receipts/yq.json"
    before_cache = cache.read_bytes()
    before_receipt = receipt.exists()
    assert schedule_run.plan_update_all(deps)[1] == 0
    if scenario == "plain":
        assert cache.read_bytes() != before_cache
    elif scenario == "adopt":
        assert not before_receipt and receipt.is_file()
    else:
        assert before_receipt and not receipt.exists()
    if scenario in ("plain", "retire"):
        assert lookups


def test_commit_writes_is_never_called_by_plan_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home, deps, _ = real_plan_fixture(tmp_path, monkeypatch, "plain")
    refresh = deps.refresh
    assert isinstance(refresh, VersionRefreshService)
    commits: list[bool] = []
    original = refresh.commit_writes

    def commit() -> list[str]:
        commits.append(True)
        return original()

    monkeypatch.setattr(refresh, "commit_writes", commit)
    refresh.hold_writes()
    before = snapshot_home(home)
    assert schedule_run.plan_update_all(deps)[1] == 0
    assert not commits and snapshot_home(home) == before

    def build(tools: list[Tool], platform: Platform, **kwargs: object) -> tuple[object, ...]:
        return refresh, SpyService(), None, None

    def load(_path: Path) -> list[Tool]:
        return [yq_tool()]

    patch_composition(monkeypatch, "_build_services", build)
    monkeypatch.setattr(setup, "load_tools", load)
    from tests.update_all_doubles import FEDORA

    monkeypatch.setattr(setup, "detect", lambda: FEDORA)
    assert setup.main(["--run-schedule", "update-all", "--plan"]) == 0
    assert "ok: plan" in capsys.readouterr().out
    assert not commits and snapshot_home(home) == before
