"""End-to-end update-all runner and lock handoff, with an offline child."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

from installer import schedules, update_all_state
from installer.helper_assets import schedule_runner
from tests.test_update_check_job import snapshot


def make_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str = "empty"
) -> tuple[Path, Path, Path, Path]:
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    home = tmp_path / "home"
    home.mkdir()
    checkout = tmp_path / "co"
    checkout.mkdir()
    (checkout / "setup.py").write_text("scratch")
    (checkout / "other").write_text("keep")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/dummy/bus")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "scenario": scenario,
                "home": str(home),
                "checkout": str(checkout),
                "result": str(tmp_path / "result.json"),
                "traceback": str(tmp_path / "traceback"),
            }
        )
    )
    uv = bindir / "uv"
    root = Path(__file__).resolve().parent.parent
    uv.write_text(
        f"#!{sys.executable}\nimport sys; sys.path.insert(0, {str(root)!r})\n"
        "from tests.update_all_child import main\n"
        f"raise SystemExit(main({str(config)!r}, sys.argv[sys.argv.index('setup.py') + 1:]))\n"
    )
    uv.chmod(0o755)
    return home, checkout, uv, home / ".local/state/tools-installer/run.lock"


def run_job(tmp_path: Path, checkout: Path, uv: Path, lock: Path) -> tuple[int, list[str]]:
    log = tmp_path / "run/log"
    code = schedule_runner.main(
        [
            "update-all",
            "--installer",
            str(checkout),
            "--uv",
            str(uv),
            "--log",
            str(log),
            "--lock",
            str(lock),
            "--cap-bytes",
            "262144",
        ]
    )
    return code, log.read_text().splitlines()


def test_the_update_all_job_runs_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, checkout, uv, lock = make_job(tmp_path, monkeypatch)
    before = snapshot(checkout)
    code, lines = run_job(tmp_path, checkout, uv, lock)
    assert code == 0, (
        lines,
        (tmp_path / "traceback").read_text() if (tmp_path / "traceback").exists() else "",
    )
    assert len(lines) == 2 and re.fullmatch(r"\S+ update-all start", lines[0])
    assert re.fullmatch(r"\S+ update-all ok: 0 updated", lines[1])
    result = json.loads((tmp_path / "result.json").read_text())
    assert result == {"code": 0, "runs": [], "bytecode": "1", "no_sudo": "1", "lock": str(lock)}
    assert snapshot(checkout) == before


def test_three_tools_leave_three_run_log_lines_and_one_shared_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, checkout, uv, lock = make_job(tmp_path, monkeypatch, "three")
    before = snapshot(checkout)
    code, lines = run_job(tmp_path, checkout, uv, lock)
    assert code == 0, (
        lines,
        (tmp_path / "traceback").read_text() if (tmp_path / "traceback").exists() else "",
    )
    assert len(lines) == 2 and re.fullmatch(r"\S+ update-all start", lines[0])
    assert re.fullmatch(r"\S+ update-all ok: 3 updated, 0 skipped", lines[1])
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["runs"] == ["brew", "uv", "ruff"] and result["no_sudo"] == "1"
    ctx = schedules.context_for("fedora", checkout=checkout, read_models=lambda _a: None)
    log = schedules.update_all_log_path(ctx).read_text().splitlines()
    assert [line.split(" ", 2)[1] for line in log] == ["brew", "uv", "ruff"]
    records, healthy = update_all_state.read_updated(schedules.updated_today_path(ctx))
    assert healthy and set(records) == {"brew", "uv", "ruff"}
    assert all(item.by == "update-all" for item in records.values())
    assert snapshot(checkout) == before and ctx.home == home


@pytest.mark.parametrize(
    "scenario,expected_code,summary,body",
    [
        ("three", 0, "3 tools updated", "updated: brew, uv, ruff"),
        ("failing", 1, "1 tool updated, 1 failed", "updated: uv; failed: brew"),
    ],
)
def test_the_three_tool_job_notifies_once_through_the_real_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_code: int,
    summary: str,
    body: str,
) -> None:
    _home, checkout, uv, lock = make_job(tmp_path, monkeypatch, scenario)
    config_path = tmp_path / "config.json"
    config = json.loads(config_path.read_text())
    config["notifier"] = "real"
    config_path.write_text(json.dumps(config))
    recorder = uv.parent / "notify-send"
    args = tmp_path / "args"
    bus = tmp_path / "bus"
    recorder.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" >> '{args}'\n"
        f"printf '%s\\n' \"${{DBUS_SESSION_BUS_ADDRESS-unset}}\" >> '{bus}'\n"
    )
    recorder.chmod(0o755)
    code, lines = run_job(tmp_path, checkout, uv, lock)
    assert code == expected_code, (
        lines,
        (tmp_path / "traceback").read_text() if (tmp_path / "traceback").exists() else "",
    )
    assert len(lines) == 2 and "update-all start" in lines[0]
    assert args.read_text().splitlines() == [
        "--app-name=tools-installer",
        "--urgency=normal",
        "--",
        summary,
        body,
    ]
    assert bus.read_text().splitlines() == ["unix:path=/dummy/bus"]
    assert lines[1].count("update-all ") == 1


def test_a_failing_manager_through_the_runner_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, checkout, uv, lock = make_job(tmp_path, monkeypatch, "failing")
    code, lines = run_job(tmp_path, checkout, uv, lock)
    assert code == 1 and len(lines) == 2
    assert re.fullmatch(
        r"\S+ update-all failed: 1 failed \(brew\), 1 updated, 1 skipped", lines[-1]
    )
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["runs"] == ["brew", "uv"]
    ctx = schedules.context_for("fedora", checkout=checkout, read_models=lambda _a: None)
    assert "ruff skipped: brew failed" in schedules.update_all_log_path(ctx).read_text()


@pytest.mark.parametrize("text_only", [False, True])
def test_the_child_refuses_when_the_runner_lock_is_not_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text_only: bool
) -> None:
    _home, checkout, uv, lock = make_job(tmp_path, monkeypatch)
    if text_only:
        lock.parent.mkdir(parents=True)
        lock.write_text(f"update-all {os.getpid()} 2026-01-01\n")
    code, lines = run_job(tmp_path, checkout, uv, tmp_path / "foreign.lock")
    assert code == 1 and lines[-1].endswith(
        "update-all failed: update-all refuses an unverified parent run lock"
    )
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["code"] == 1 and result["runs"] == []
