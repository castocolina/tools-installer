"""Cross-file contracts for the daily update check."""

import ast
import dataclasses
import inspect
import re
import typing
from collections.abc import Callable
from pathlib import Path

import pytest

from installer import daemon, notify, schedule_run, schedules, update_check, version_status
from installer.helper_assets import schedule_runner
from tests.update_check_doubles import (
    FakeGit,
    FakeRefresher,
    check_context,
    inert_run_deps,
    outdated_state,
    tool_named,
)

calls: list[tuple[str, str]] = []


def typed_fake(summary: str, body: str) -> str | None:
    calls.append((summary, body))
    return None


notifier: notify.Notifier = typed_fake


@pytest.mark.parametrize("platform_os", ["fedora", "macos"])
def test_every_schedule_row_has_a_runner_job_with_its_own_id(
    platform_os: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = schedules.context_for(platform_os, checkout=tmp_path / "co", read_models=lambda _a: None)
    for schedule in schedules.SCHEDULES:
        argv = schedules.runner_argv(ctx, schedule, Path("/u/uv"))
        _job, run_id, _options, _forwarded = vars(schedule_runner)["_parse"](argv[6:])
        assert run_id == schedule.id


def test_run_schedule_choices_are_the_update_and_check_rows() -> None:
    expected = tuple(
        s.id
        for s in schedules.SCHEDULES
        if s.kind in (schedules.JobKind.UPDATE, schedules.JobKind.CHECK_UPDATES)
    )
    assert set(schedules.RUN_SCHEDULE_IDS) == set(expected)
    assert tuple(sorted(schedules.RUN_SCHEDULE_IDS)) == tuple(sorted(expected))
    assert "tmp-cleanup" not in schedules.RUN_SCHEDULE_IDS
    assert "cache-cleanup" not in schedules.RUN_SCHEDULE_IDS
    assert all(s.default_interval == 24 for s in schedules.SCHEDULES if s.daily)


def test_the_contract_phase_35_inherits_is_in_place() -> None:
    assert list(inspect.signature(notify.notifier_for).parameters)[:3] == [
        "platform_os",
        "which",
        "run",
    ]
    assert list(inspect.signature(version_status.outdated_ids).parameters) == ["states"]
    assert typing.get_type_hints(version_status.outdated_ids)["return"] == frozenset[str]
    params = inspect.signature(version_status.VersionRefreshService.refresh).parameters
    assert params["stale_after"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["on_failure"].kind is inspect.Parameter.KEYWORD_ONLY
    assert {f.name: f.default for f in dataclasses.fields(schedules.Schedule)}["daily"] is False
    assert schedules.JobKind.CHECK_UPDATES.value == "check-updates"
    defaults = {f.name: f.default for f in dataclasses.fields(schedule_run.RunDeps)}
    assert defaults["notify"] is notify.no_notifier
    assert defaults["refresh"] is None
    assert defaults["git"] is None
    assert "DBUS_SESSION_BUS_ADDRESS" in vars(schedule_runner)["_PASSED_ENV"]
    assert notify.Notifier == Callable[[str, str], str | None]


def test_the_notifier_seam_accepts_a_typed_fake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls.clear()
    tools = [tool_named("a"), tool_named("b")]
    ctx = check_context(tmp_path, monkeypatch)
    refresh = FakeRefresher(tmp_path / "versions.json", {t.id: outdated_state(t) for t in tools})
    git = FakeGit(branch="feature")
    deps = inert_run_deps(tools, ctx, notify=notifier, refresh=refresh, git=git)
    assert deps.refresh is not None and deps.git is not None
    update_check.run_check(
        deps.tools, refresh=deps.refresh, notify=deps.notify, context=ctx, git=deps.git
    )
    assert calls == [("2 tool updates available", "a, b")]


def test_the_runner_environment_equals_the_unit_keys_plus_the_two_runner_only_keys() -> None:
    passed = set(vars(schedule_runner)["_PASSED_ENV"])
    expected = set(daemon.ENVIRONMENT_KEYS) | {"LANG", "DBUS_SESSION_BUS_ADDRESS"}
    assert passed == expected
    assert "DBUS_SESSION_BUS_ADDRESS" not in daemon.ENVIRONMENT_KEYS
    assert all("TOKEN" not in key for key in passed | set(daemon.ENVIRONMENT_KEYS))
    assert passed - {"HOME"} != expected
    assert passed | {"GITHUB_TOKEN"} != expected


def test_the_new_modules_hold_the_hard_rules() -> None:
    package = Path(schedules.__file__).parent
    for name in ("notify.py", "update_check.py"):
        path = package / name
        assert path.is_file()
        source = path.read_text()
        assert re.search(r"GITHUB_TOKEN|GH_TOKEN|Authorization|Bearer", source) is None
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                assert all(alias.name != "subprocess" for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module != "subprocess"
