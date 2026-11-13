"""Host tests of the schedules e2e target and its in-container driver (24.2-10, D-26).

The harness sources the container detector at load time, so these tests never source it and never
start a container: they extract the committed shell functions and run them in bash with stubbed
`ct`, `exec_root` and `exec_tester` (every call lands in a calls file). The driver is imported and
run in-process against a scratch HOME with recording fakes. Only the orchestrator runs the real
target (plan 24.2-13).
"""

import re
import shlex
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from installer import runlock, schedules
from installer.schedules import ApplyReport, ScheduleContext
from tests import e2e_schedules_driver as driver

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "container-e2e-verify.sh"
_REAL_CONTEXT_FOR = schedules.context_for

_CONSTANTS = (
    "SCHEDULES_BASE_IMAGE",
    "SCHEDULES_IMAGE",
    "SCHEDULES_CONTAINER_NAME",
    "SCHEDULES_LOG_REL",
    "SCHEDULES_LOCK_REL",
    "IMAGE_FEDORA",
    "TESTER_USER",
    "TESTER_HOME",
    "TESTER_WORKSPACE",
    "BREW_BIN",
)

# Stubs of the three container seams: every call is recorded, and a case fails a call by setting
# FAIL_CT or FAIL_ROOT to a fragment of its argument text.
_STUBS = r"""
ct() {
  printf 'ct %s\n' "$*" >> "$CALLS"
  if [ "${1:-}" = build ]; then cp "$5" "$SCRATCH/Containerfile.seen"; fi
  if [ -n "${FAIL_CT:-}" ] && [[ "$*" == *"$FAIL_CT"* ]]; then
    echo "Error: $FAIL_CT_MESSAGE" >&2
    return 125
  fi
  return 0
}
exec_root() {
  printf 'root %s\n' "$*" >> "$CALLS"
  if [ -n "${FAIL_ROOT:-}" ] && [[ "$*" == *"$FAIL_ROOT"* ]]; then
    echo "Error: $FAIL_ROOT broke" >&2
    return 1
  fi
  case "$1" in
    systemctl) printf '%s\n' "$BOOT_STATE" ;;
    id) echo 1000 ;;
  esac
}
"""


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None, "bash is required on every supported host"
    return found


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _constant(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)\s*$", _text(), re.MULTILINE)
    assert match is not None, f"{name} is not assigned in the script"
    return match.group(1)


def _function(name: str) -> str:
    """The function body as committed, from its header through its closing brace."""
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, f"{name}() is not defined in the script"
    return match.group(0)


def _script(*names: str, variables: dict[str, str] | None = None, stubs: str = "") -> str:
    """Extracted constants and functions, then the case's variables, then its stubs."""
    parts = ["set -uo pipefail"]
    parts.extend(f"{name}={_constant(name)}" for name in _CONSTANTS)
    parts.append("SCHEDULES_POLL_STEP=0 SCHEDULES_BOOT_ATTEMPTS=2 SCHEDULES_BUS_ATTEMPTS=2")
    parts.append("SCHEDULES_UID=1000 BOOT_STATE=degraded SCHEDULES_KEEP_IMAGE=0")
    parts.extend(_function(name) for name in names)
    parts.extend(f"{key}={shlex.quote(value)}" for key, value in (variables or {}).items())
    parts.append(stubs)
    return "\n".join(parts)


def _run(script: str, scratch: Path) -> subprocess.CompletedProcess[str]:
    scratch.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(scratch),
        "SCRATCH": str(scratch),
        "CALLS": str(scratch / "calls"),
        "LANG": "C",
    }
    script_file = scratch.parent / f"harness-{uuid.uuid4().hex}.sh"
    script_file.write_text(script, encoding="utf-8")
    try:
        return subprocess.run(
            [_bash(), str(script_file)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    finally:
        script_file.unlink()


def _calls(scratch: Path) -> list[str]:
    calls = scratch / "calls"
    return calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []


# --- the driver, in-process ------------------------------------------------------------------


def _context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScheduleContext:
    """A fedora context over the scratch HOME; `context_for` returns it to the driver."""
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(parents=True, exist_ok=True)
    uv.write_text("#!/bin/sh\n", encoding="utf-8")
    ctx = _REAL_CONTEXT_FOR(
        "fedora",
        checkout=tmp_path / "checkout",
        read_models=lambda _agent: None,
        which=lambda tool: str(uv) if tool == "uv" else None,
        present=lambda _tool: True,
        environ={},
    )

    def fake_context(*_args: object, **_kwargs: object) -> ScheduleContext:
        return ctx

    monkeypatch.setattr(schedules, "context_for", fake_context)
    return ctx


def test_driver_on_and_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _context(tmp_path, monkeypatch)
    turned_on: list[str] = []

    def fake_turn_on(_ctx: ScheduleContext, schedule_id: str) -> ApplyReport:
        turned_on.append(schedule_id)
        return ApplyReport(True, None, None, ("a warning",))

    monkeypatch.setattr(schedules, "turn_on", fake_turn_on)

    assert driver.main(["on", "cache-cleanup"]) == 0
    assert turned_on == ["cache-cleanup"]
    assert capsys.readouterr().out.splitlines() == ["ON cache-cleanup next=-", "WARN a warning"]

    assert driver.main(["cells"]) == 0
    never = {line.split(" ", 2)[1]: line for line in capsys.readouterr().out.splitlines()}
    assert list(never) == [schedule.id for schedule in schedules.SCHEDULES]
    assert all(line.endswith(" never") for line in never.values())

    now = datetime.now().isoformat(timespec="seconds")
    ctx.log_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.log_path.write_text(
        f"{now} cache-cleanup start\n{now} cache-cleanup ok: nothing to prune\n", encoding="utf-8"
    )
    assert driver.main(["cells"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(re.fullmatch(r"CELL cache-cleanup ✓ \d\d:\d\d", line) for line in lines)
    assert "CELL tmp-cleanup never" in lines


@pytest.mark.parametrize(
    "argv",
    [[], ["bogus"], ["on"], ["on", "no-such-schedule"], ["cells", "extra"], ["retime", "x", "6"]],
)
def test_driver_rejects_a_bad_verb_id_or_arity(argv: list[str]) -> None:
    assert driver.main(argv) == 2


def test_driver_reports_an_engine_error_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _context(tmp_path, monkeypatch)

    def refuse(_ctx: ScheduleContext, _schedule_id: str) -> ApplyReport:
        raise schedules.ScheduleUnavailable("unavailable: no user timer manager\nsecond line")

    monkeypatch.setattr(schedules, "turn_on", refuse)
    assert driver.main(["on", "cache-cleanup"]) == 1
    assert capsys.readouterr().out == "ERROR unavailable: no user timer manager\n"


def test_driver_off_retime_and_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _context(tmp_path, monkeypatch)
    seen: list[tuple[object, ...]] = []

    def fake_off(_ctx: ScheduleContext, schedule_id: str) -> ApplyReport:
        seen.append(("off", schedule_id))
        return ApplyReport(True)

    def fake_retime(
        _ctx: ScheduleContext, schedule_id: str, interval: int, start: str
    ) -> ApplyReport:
        seen.append(("retime", schedule_id, interval, start))
        return ApplyReport(True)

    monkeypatch.setattr(schedules, "turn_off", fake_off)
    monkeypatch.setattr(schedules, "retime", fake_retime)

    assert driver.main(["off", "update-claude"]) == 0
    assert driver.main(["retime", "cache-cleanup", "24", "10:05"]) == 0
    assert seen == [("off", "update-claude"), ("retime", "cache-cleanup", 24, "10:05")]
    assert capsys.readouterr().out.splitlines() == [
        "OFF update-claude",
        "RETIME cache-cleanup next=-",
    ]

    assert driver.main(["argv", "cache-cleanup"]) == 0
    argv = capsys.readouterr().out.splitlines()
    expected = schedules.runner_argv(
        ctx, schedules.schedule_by_id("cache-cleanup"), tmp_path / "bin" / "uv"
    )
    assert argv == expected
    assert argv[0] == str(tmp_path / "bin" / "uv")


# --- the harness functions, in bash ----------------------------------------------------------


def test_log_path_matches_the_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The log the harness reads is the one the engine names for a Linux key."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert schedules.default_log_path("fedora") == tmp_path / _constant("SCHEDULES_LOG_REL")


def _log(tmp_path: Path, *lines: str) -> Path:
    log = tmp_path / "schedules.log"
    log.write_text("".join(f"2026-11-13T10:00:0{n}+00:00 {line}\n" for n, line in enumerate(lines)))
    return log


@pytest.mark.parametrize(
    ("lines", "schedule_id", "expected", "code"),
    [
        (["cache-cleanup start", "cache-cleanup ok: nothing"], "cache-cleanup", "OK result=ok", 0),
        (
            ["update-claude start", "update-claude skipped: owned by dnf"],
            "update-claude",
            "OK result=skipped",
            0,
        ),
        (["cache-cleanup start"], "cache-cleanup", "MISSING", 1),
        (["tmp-cleanup start", "tmp-cleanup ok: ran"], "cache-cleanup", "MISSING", 1),
        (["cache-cleanup start", "cache-cleanup failed: boom"], "cache-cleanup", "FAILED", 1),
        (
            ["cache-cleanup start", "cache-cleanup ok: a", "cache-cleanup skipped: busy"],
            "cache-cleanup",
            "OK result=ok",
            0,
        ),
    ],
)
def test_schedules_run_verdict(
    tmp_path: Path, lines: list[str], schedule_id: str, expected: str, code: int
) -> None:
    log = _log(tmp_path, *lines)
    script = _script("schedules_run_verdict") + f"\nschedules_run_verdict {log} {schedule_id}\n"
    result = _run(script, tmp_path / "home")
    assert result.returncode == code, result.stderr
    word, _, rest = expected.partition(" ")
    assert f"TRACER_SCHEDULE_RUN_{word} id={schedule_id}" in result.stdout
    assert rest in result.stdout


@pytest.mark.parametrize(
    ("cells", "code", "expected"),
    [
        (
            "CELL cache-cleanup ✓ 10:00\n",
            0,
            "TRACER_SCHEDULE_CELL_OK id=cache-cleanup cell=✓ 10:00",
        ),
        ("CELL cache-cleanup never\n", 1, "TRACER_SCHEDULE_CELL_NEVER id=cache-cleanup"),
        ("CELL tmp-cleanup ✓ 10:00\n", 1, "TRACER_SCHEDULE_CELL_NEVER id=cache-cleanup"),
    ],
)
def test_schedules_cell_verdict(tmp_path: Path, cells: str, code: int, expected: str) -> None:
    file = tmp_path / "cells"
    file.write_text(cells, encoding="utf-8")
    script = _script("schedules_cell_verdict") + f"\nschedules_cell_verdict {file} cache-cleanup\n"
    result = _run(script, tmp_path / "home")
    assert result.returncode == code, result.stderr
    assert expected in result.stdout


def test_schedules_containerfile_text(tmp_path: Path) -> None:
    result = _run(
        _script("schedules_containerfile") + "\nschedules_containerfile\n", tmp_path / "home"
    )
    lines = result.stdout.splitlines()
    assert lines[0] == "FROM registry.fedoraproject.org/fedora:44"
    assert lines[1].startswith("RUN dnf install -y systemd procps-ng util-linux curl tar git")
    assert "python3 which" in lines[1]
    assert lines[-1] == 'CMD ["/sbin/init"]'


def test_schedules_start_sequence(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    script = _script(
        "schedules_containerfile",
        "schedules_infeasible",
        "schedules_wait",
        "schedules_booted",
        "schedules_bus_ready",
        "schedules_create_tester",
        "schedules_start",
        stubs=_STUBS,
    )
    result = _run(script + "\nschedules_start\n", scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    name = "tools-installer-e2e-schedules"
    image = "localhost/tools-installer-e2e-schedules:44"
    calls = _calls(scratch)
    assert calls[0] == f"ct rm -f {name}"
    assert re.fullmatch(rf"ct build -t {image} -f (\S+)/Containerfile \1", calls[1]), calls[1]
    assert calls[2:] == [
        f"ct run -d --name {name} --systemd=always {image}",
        "root systemctl is-system-running",
        "root useradd -m -s /bin/bash tester",
        "root id -u tester",
        "root loginctl enable-linger tester",
        "root test -S /run/user/1000/bus",
    ]
    seen = (scratch / "Containerfile.seen").read_text(encoding="utf-8")
    assert seen.splitlines()[0] == "FROM registry.fedoraproject.org/fedora:44"
    assert seen.rstrip().endswith('CMD ["/sbin/init"]')


@pytest.mark.parametrize(
    ("variables", "step", "detail"),
    [
        ({"FAIL_CT": "build", "FAIL_CT_MESSAGE": "no space left"}, "build", "no space left"),
        (
            {"FAIL_CT": "--systemd=always", "FAIL_CT_MESSAGE": "unknown flag: --systemd"},
            "run",
            "unknown flag: --systemd",
        ),
        ({"BOOT_STATE": "starting"}, "boot", "starting"),
        ({"FAIL_ROOT": "useradd"}, "useradd", "useradd broke"),
        ({"FAIL_ROOT": "id -u"}, "uid", "id -u broke"),
        ({"FAIL_ROOT": "enable-linger"}, "linger", "enable-linger broke"),
        ({"FAIL_ROOT": "test -S"}, "bus", "bus"),
    ],
)
def test_every_start_failure_is_infeasible(
    tmp_path: Path, variables: dict[str, str], step: str, detail: str
) -> None:
    script = _script(
        "schedules_containerfile",
        "schedules_infeasible",
        "schedules_wait",
        "schedules_booted",
        "schedules_bus_ready",
        "schedules_create_tester",
        "schedules_start",
        variables={"FAIL_CT": "", "FAIL_CT_MESSAGE": "", "FAIL_ROOT": "", **variables},
        stubs=_STUBS,
    )
    result = _run(script + "\nschedules_start\n", tmp_path / "home")
    assert result.returncode == 2, result.stdout + result.stderr
    line = next(
        line
        for line in result.stdout.splitlines()
        if line.startswith("TRACER_SCHEDULES_INFEASIBLE")
    )
    assert f"step={step} detail=" in line
    assert detail in line


def test_schedules_tester_exports_the_session_bus(tmp_path: Path) -> None:
    stubs = 'exec_tester() { printf "%s\\n" "$1" > "$SCRATCH/tester-command"; }'
    script = _script("schedules_tester", stubs=stubs) + "\nschedules_tester 'systemctl --user x'\n"
    result = _run(script, tmp_path / "home")
    assert result.returncode == 0, result.stderr
    command = (tmp_path / "home" / "tester-command").read_text(encoding="utf-8")
    assert "export XDG_RUNTIME_DIR=/run/user/1000" in command
    assert "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus" in command
    assert ".local/bin" in command
    assert "cd /home/tester/workspace" in command
    assert command.rstrip().endswith("systemctl --user x")


def test_schedules_driver_runs_the_module_through_the_tester(tmp_path: Path) -> None:
    stubs = 'schedules_tester() { printf "%s\\n" "$1" > "$SCRATCH/tester-command"; }'
    script = (
        _script("schedules_driver", stubs=stubs)
        + "\nschedules_driver retime cache-cleanup 24 10:05\n"
    )
    result = _run(script, tmp_path / "home")
    assert result.returncode == 0, result.stderr
    command = (tmp_path / "home" / "tester-command").read_text(encoding="utf-8")
    assert command.startswith("uv run --isolated --no-dev python -m tests.e2e_schedules_driver ")
    assert "retime cache-cleanup 24 10:05" in command


def test_usage_and_dispatch_list_schedules(tmp_path: Path) -> None:
    usage = _run(_script("usage") + "\nusage\n", tmp_path / "usage")
    assert "schedules [--direct] [--keep-image]" in usage.stdout
    stubs = 'select_distro() { :; }\ncmd_schedules() { echo "cmd_schedules $*"; }'
    dispatch = _run(
        _script("main", stubs=stubs) + "\nmain schedules --direct\n", tmp_path / "dispatch"
    )
    assert dispatch.returncode == 0, dispatch.stderr
    assert dispatch.stdout.strip() == "cmd_schedules --direct"


def test_the_container_is_never_privileged() -> None:
    """T-24.2-41: systemd mode comes from --systemd=always alone, never --privileged."""
    start = _function("schedules_start")
    assert "--systemd=always" in start
    assert "--privileged" not in start


# --- Task 2: every built-in, busy, calendar, catch-up and the stamp --------------------------

_TIMER_BASENAME = "tools-installer-schedule-cache-cleanup"
_BUILTINS = (
    ("tmp-cleanup", "tools-installer-prune-tmp"),
    ("cache-cleanup", _TIMER_BASENAME),
    ("update-claude", "tools-installer-schedule-update-claude"),
)

# Stubs of the tester seams: every command is recorded on one line, the schedules.log copy comes
# from $SCRATCH/log and the driver prints $SCRATCH/cells for `cells`. Cases hook in through the
# files and variables they write.
_TESTER_STUBS = r"""
schedules_tester() {
  printf 'tester %s\n' "${1//$'\n'/ ; }" >> "$CALLS"
  case "$1" in
    "date +%H:%M") echo "$CLOCK" ;;
    *"journalctl --user"*) printf 'journal line one\njournal line two\n' ;;
    *"test -e"*) [ "${STAMP:-1}" = 1 ]; return ;;
    *"stat -c"*) head -n 1 "$SCRATCH/mtimes"; sed -i 1d "$SCRATCH/mtimes" ;;
    *"touch -d"*) : ;;
    "systemctl --user start "*".timer") for _ in $(seq "${TIMER_RUNS:-0}"); do
      echo "2026-11-13T10:00:00+00:00 cache-cleanup start" >> "$SCRATCH/log"; done ;;
  esac
  return 0
}
schedules_driver() {
  printf 'driver %s\n' "$*" >> "$CALLS"
  case "$1" in
    cells) cat "$SCRATCH/cells" ;;
    retime) if [ "${FIRES:-0}" = 1 ]; then
      echo "2026-11-13T10:02:00+00:00 cache-cleanup start" >> "$SCRATCH/log"; fi ;;
  esac
}
schedules_fetch_log() { cat "$SCRATCH/log"; }
"""


def _seed(scratch: Path, *, log: str = "", cells: str = "", mtimes: str = "") -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "log").write_text(log, encoding="utf-8")
    (scratch / "cells").write_text(cells, encoding="utf-8")
    (scratch / "mtimes").write_text(mtimes, encoding="utf-8")


def _builtin_log(claude_result: str) -> str:
    stamp = "2026-11-13T10:00:00+00:00"
    return "".join(
        f"{stamp} {schedule_id} start\n{stamp} {schedule_id} {result}\n"
        for schedule_id, result in (
            ("tmp-cleanup", "ok: ran"),
            ("cache-cleanup", "ok: nothing to prune"),
            ("update-claude", claude_result),
        )
    )


@pytest.mark.parametrize("claude_result", ["ok: up to date", "skipped: no owner for claude"])
def test_each_builtin_runs_once(tmp_path: Path, claude_result: str) -> None:
    scratch = tmp_path / "home"
    cells = "".join(f"CELL {schedule_id} ✓ 10:00\n" for schedule_id, _unit in _BUILTINS)
    _seed(scratch, log=_builtin_log(claude_result), cells=cells)
    script = _script(
        "schedules_journal",
        "schedules_verdicts",
        "schedules_run_verdict",
        "schedules_cell_verdict",
        "schedules_run_one",
        "schedules_plant_claude",
        "schedules_run_all",
        stubs=_TESTER_STUBS,
    )
    result = _run(script + "\nschedules_run_all\n", scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    calls = _calls(scratch)
    assert "claude" in calls[0]
    assert "chmod" in calls[0]
    expected: list[str] = []
    for schedule_id, unit in _BUILTINS:
        expected += [f"driver on {schedule_id}", f"tester systemctl --user start {unit}.service"]
    assert [call for call in calls if "driver on" in call or "start tools" in call] == expected
    word = "skipped" if claude_result.startswith("skipped") else "ok"
    for schedule_id, _unit in _BUILTINS:
        assert f"TRACER_SCHEDULE_CELL_OK id={schedule_id} cell=✓ 10:00" in result.stdout
    assert "TRACER_SCHEDULE_RUN_OK id=update-claude result=" + word in result.stdout


def test_a_failing_run_prints_the_unit_journal(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    _seed(scratch, log="", cells="CELL cache-cleanup never\n")
    script = _script(
        "schedules_journal",
        "schedules_verdicts",
        "schedules_run_verdict",
        "schedules_cell_verdict",
        "schedules_run_one",
        stubs=_TESTER_STUBS,
    )
    result = _run(script + f"\nschedules_run_one cache-cleanup {_TIMER_BASENAME}\n", scratch)
    assert result.returncode == 1
    assert "TRACER_SCHEDULE_RUN_MISSING id=cache-cleanup" in result.stdout
    assert "TRACER_SCHEDULE_CELL_NEVER id=cache-cleanup" in result.stdout
    prefix = f"SCHEDULE_JOURNAL {_TIMER_BASENAME}.service "
    assert f"{prefix}journal line one" in result.stdout
    assert f"{prefix}journal line two" in result.stdout
    assert any(
        f"journalctl --user -u {_TIMER_BASENAME}.service -n 50 --no-pager" in call
        for call in _calls(scratch)
    )


def test_lock_path_matches_the_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert runlock.run_lock_path() == tmp_path / _constant("SCHEDULES_LOCK_REL")


@pytest.mark.parametrize(
    ("last", "expected", "code"),
    [
        ("cache-cleanup skipped: busy", "TRACER_SCHEDULE_BUSY_OK", 0),
        ("cache-cleanup ok: nothing", "TRACER_SCHEDULE_BUSY_MISSING", 1),
    ],
)
def test_busy_verdict(tmp_path: Path, last: str, expected: str, code: int) -> None:
    scratch = tmp_path / "home"
    _seed(
        scratch,
        log=f"2026-11-13T10:00:00+00:00 cache-cleanup start\n2026-11-13T10:00:01+00:00 {last}\n",
    )
    script = _script("schedules_journal", "schedules_busy_check", stubs=_TESTER_STUBS)
    result = _run(script + "\nschedules_busy_check\n", scratch)
    assert result.returncode == code, result.stdout + result.stderr
    assert expected in result.stdout
    calls = _calls(scratch)
    holder = next(i for i, call in enumerate(calls) if "flock -n" in call and "sleep 60" in call)
    start = next(i for i, call in enumerate(calls) if f"start {_TIMER_BASENAME}.service" in call)
    kill = next(i for i, call in enumerate(calls) if "pkill" in call)
    assert holder < start < kill
    assert "run.lock" in calls[holder]


@pytest.mark.parametrize(
    ("clock", "target"),
    [("10:00", "10:02"), ("23:59", "00:01"), ("00:00", "00:02"), ("22:58", "23:00")],
)
def test_plus_minutes_wraps_at_midnight(tmp_path: Path, clock: str, target: str) -> None:
    script = _script("schedules_plus_minutes") + f"\nschedules_plus_minutes {clock} 2\n"
    result = _run(script, tmp_path / "home")
    assert result.stdout.strip() == target


@pytest.mark.parametrize(
    ("fires", "expected", "code"), [("1", "CALENDAR_OK", 0), ("0", "CALENDAR_MISSING", 1)]
)
def test_calendar_trigger(tmp_path: Path, fires: str, expected: str, code: int) -> None:
    scratch = tmp_path / "home"
    _seed(scratch)
    script = _script(
        "schedules_journal",
        "schedules_plus_minutes",
        "schedules_start_count",
        "schedules_calendar_check",
        variables={"CLOCK": "23:59", "FIRES": fires},
        stubs="SCHEDULES_CALENDAR_ATTEMPTS=2 SCHEDULES_CALENDAR_STEP=0\n" + _TESTER_STUBS,
    )
    result = _run(script + "\nschedules_calendar_check\n", scratch)
    assert result.returncode == code, result.stdout + result.stderr
    assert f"TRACER_SCHEDULE_{expected}" in result.stdout
    calls = _calls(scratch)
    assert "driver retime cache-cleanup 24 00:01" in calls
    dropin = next(call for call in calls if "AccuracySec=1s" in call)
    assert f"{_TIMER_BASENAME}.timer.d" in dropin
    assert "e2e-accuracy.conf" in dropin
    assert "[Timer]" in dropin
    # The drop-in is in place before the timer is re-timed.
    assert calls.index(dropin) < calls.index("driver retime cache-cleanup 24 00:01")
    if code:
        assert f"SCHEDULE_JOURNAL {_TIMER_BASENAME}.timer journal line one" in result.stdout


def _catchup(tmp_path: Path, *, runs: int, stamp: bool) -> subprocess.CompletedProcess[str]:
    scratch = tmp_path / "home"
    _seed(scratch, log="2026-11-13T09:00:00+00:00 cache-cleanup start\n")
    script = _script(
        "schedules_journal",
        "schedules_start_count",
        "schedules_catchup_check",
        variables={"TIMER_RUNS": str(runs), "STAMP": "1" if stamp else "0"},
        stubs="SCHEDULES_CATCHUP_WAIT=0\n" + _TESTER_STUBS,
    )
    return _run(script + "\nschedules_catchup_check\n", scratch)


def test_catchup_counts_one_run(tmp_path: Path) -> None:
    result = _catchup(tmp_path, runs=1, stamp=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TRACER_SCHEDULE_CATCHUP_OK runs=1" in result.stdout
    calls = _calls(tmp_path / "home")
    stop = next(i for i, call in enumerate(calls) if "stop" in call and ".timer" in call)
    age = next(i for i, call in enumerate(calls) if "touch -d '2 days ago'" in call)
    start = next(
        i for i, call in enumerate(calls) if call.endswith(f"start {_TIMER_BASENAME}.timer")
    )
    assert stop < age < start
    assert f"stamp-{_TIMER_BASENAME}.timer" in calls[age]


@pytest.mark.parametrize("runs", [0, 2])
def test_catchup_with_another_count_fails(tmp_path: Path, runs: int) -> None:
    result = _catchup(tmp_path, runs=runs, stamp=True)
    assert result.returncode == 1
    assert f"TRACER_SCHEDULE_CATCHUP_COUNT runs={runs}" in result.stdout
    assert f"SCHEDULE_JOURNAL {_TIMER_BASENAME}.timer journal line one" in result.stdout


def test_catchup_without_a_stamp(tmp_path: Path) -> None:
    result = _catchup(tmp_path, runs=1, stamp=False)
    assert result.returncode == 1
    assert "TRACER_SCHEDULE_STAMP_MISSING" in result.stdout


@pytest.mark.parametrize(
    ("mtimes", "kept"), [("100\n200\n", "yes"), ("100\nnone\n", "no"), ("none\nnone\n", "no")]
)
def test_stamp_observation(tmp_path: Path, mtimes: str, kept: str) -> None:
    scratch = tmp_path / "home"
    _seed(scratch, mtimes=mtimes)
    script = _script("schedules_stamp_observation", stubs=_TESTER_STUBS)
    result = _run(script + "\nschedules_stamp_observation\n", scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"SCHEDULE_STAMP_KEPT={kept}" in result.stdout
    calls = _calls(scratch)
    assert any(
        "daemon-reload" in call and f"restart {_TIMER_BASENAME}.timer" in call for call in calls
    )


# --- Task 3: off, teardown on every outcome and the direct-runner fallback --------------------

_IDS = ("tmp-cleanup", "cache-cleanup", "update-claude")


@pytest.mark.parametrize(
    ("listing", "expected", "code"),
    [
        ("D", ["TRACER_SCHEDULE_OFF_OK"], 0),
        (
            "F .config/systemd/user/tools-installer-schedule-cache-cleanup.timer\nD",
            ["TRACER_SCHEDULE_OFF_LEFT path=.config/systemd/user/tools-installer-schedule-cache"],
            1,
        ),
        (
            "F .local/share/systemd/timers/stamp-tools-installer-schedule-cache-cleanup.timer\nD",
            ["TRACER_SCHEDULE_OFF_LEFT path=.local/share/systemd/timers/stamp-tools-installer"],
            1,
        ),
        (
            "T tools-installer-schedule-cache-cleanup.timer n/a\nD",
            ["TRACER_SCHEDULE_OFF_LEFT timer=tools-installer-schedule-cache-cleanup.timer"],
            1,
        ),
        ("", ["TRACER_SCHEDULE_OFF_PROBE_FAILED"], 1),
    ],
)
def test_off_removes_units_and_stamps(
    tmp_path: Path, listing: str, expected: list[str], code: int
) -> None:
    scratch = tmp_path / "home"
    scratch.mkdir()
    (scratch / "listing").write_text(listing + "\n", encoding="utf-8")
    stubs = r"""
schedules_driver() { printf 'driver %s\n' "$*" >> "$CALLS"; }
schedules_tester() {
  printf 'tester %s\n' "${1//$'\n'/ ; }" >> "$CALLS"
  case "$1" in *"echo D"*) cat "$SCRATCH/listing" ;; esac
}
"""
    result = _run(_script("schedules_off_check", stubs=stubs) + "\nschedules_off_check\n", scratch)
    assert result.returncode == code, result.stdout + result.stderr
    for line in expected:
        assert line in result.stdout
    calls = _calls(scratch)
    offs = [call for call in calls if call.startswith("driver off")]
    assert offs == [f"driver off {schedule_id}" for schedule_id in _IDS]
    # The accuracy drop-in the calendar check wrote goes first, then every unit and stamp is listed.
    dropin = next(i for i, call in enumerate(calls) if "timer.d" in call and "rm -rf" in call)
    listing_call = next(i for i, call in enumerate(calls) if "list-timers --all" in call)
    assert dropin < calls.index(offs[0]) < listing_call
    for pattern in (
        "tools-installer-schedule-",
        "tools-installer-prune-tmp",
        "stamp-tools-installer",
    ):
        assert pattern in calls[listing_call]


def _cmd_script(arguments: str, *, start: str) -> str:
    """cmd_schedules with the container seams stubbed and `schedules_start` replaced by `start`."""
    return (
        _script(
            "schedules_teardown",
            "cmd_schedules",
            variables={"REPO_ROOT": "/repo"},
            stubs=_STUBS
            + "ensure_phase_dir() { :; }\n"
            + 'die() { echo "die: $1" >&2; exit 1; }\n'
            + start,
        )
        + f"\ncmd_schedules {arguments}\n"
    )


@pytest.mark.parametrize(("arguments", "removes_image"), [("", True), ("--keep-image", False)])
def test_teardown_always_runs(tmp_path: Path, arguments: str, removes_image: bool) -> None:
    scratch = tmp_path / "home"
    start = (
        'schedules_start() { echo "TRACER_SCHEDULES_INFEASIBLE step=run detail=boom"; exit 2; }\n'
    )
    result = _run(_cmd_script(arguments, start=start), scratch)
    assert result.returncode == 2, result.stdout + result.stderr
    calls = _calls(scratch)
    assert calls[0] == "ct rm -f tools-installer-e2e-schedules"
    image = "ct rmi localhost/tools-installer-e2e-schedules:44"
    assert (image in calls) is removes_image
    assert result.stdout.splitlines()[-1] == "TRACER_SCHEDULES_TEARDOWN_OK"


def test_an_unknown_option_dies_before_anything_starts(tmp_path: Path) -> None:
    result = _run(_cmd_script("--bogus", start="schedules_start() { :; }\n"), tmp_path / "home")
    assert result.returncode == 1
    assert "unknown schedules option: --bogus" in result.stderr
    assert _calls(tmp_path / "home") == []


_DIRECT_STUBS = r"""
for name in ensure_phase_dir copy_workspace bootstrap_uv write_tester_path sync_workspace; do
  eval "$name() { echo $name >> \"\$CALLS\"; }"
done
schedules_tester() { printf 'tester %s\n' "${1//$'\n'/ ; }" >> "$CALLS"; }
schedules_driver() {
  printf 'driver %s\n' "$*" >> "$CALLS"
  if [ "$1" = argv ]; then printf '/u/uv\nrun\n--script\nrunner.py\n%s\n' "$2"; fi
}
schedules_verdicts() { printf 'verdicts %s\n' "$1"; return "${VERDICT_RC:-0}"; }
"""


@pytest.mark.parametrize("verdict_rc", ["0", "1"])
def test_direct_fallback(tmp_path: Path, verdict_rc: str) -> None:
    scratch = tmp_path / "home"
    script = _script(
        "schedules_infeasible",
        "schedules_create_tester",
        "schedules_plant_claude",
        "schedules_install_assets",
        "schedules_direct",
        "schedules_teardown",
        "cmd_schedules",
        variables={"REPO_ROOT": "/repo", "VERDICT_RC": verdict_rc},
        stubs=_STUBS + _DIRECT_STUBS,
    )
    result = _run(script + "\ncmd_schedules --direct\n", scratch)
    assert result.returncode == int(verdict_rc), result.stdout + result.stderr
    calls = _calls(scratch)
    name = "tools-installer-e2e-schedules"
    assert f"ct run -d --name {name} fedora:latest sleep infinity" in calls
    assert not any("--systemd" in call for call in calls)
    assert any(call.startswith("root dnf install -y") for call in calls)
    assert "root useradd -m -s /bin/bash tester" in calls
    assert calls.count("sync_workspace") == 1
    assets = next(call for call in calls if "schedule_runner.py" in call)
    for fragment in ("runner.py", "prune-tmp-linux.sh", "prune-user-tmpdir.sh", "lib"):
        assert fragment in assets
    assert [call for call in calls if call.startswith("driver argv")] == [
        f"driver argv {schedule_id}" for schedule_id in _IDS
    ]
    # Each row runs the command the driver printed, as the tester, one argument per word.
    ran = [call for call in calls if call.startswith("tester /u/uv run --script runner.py")]
    assert ran == [f"tester /u/uv run --script runner.py {schedule_id}" for schedule_id in _IDS]
    gap = "SCHEDULES_GAP=no-systemd units,calendar,catch-up not exercised"
    assert gap in result.stdout
    assert ("TRACER_SCHEDULES_DIRECT_OK" in result.stdout) is (verdict_rc == "0")
    assert result.stdout.splitlines()[-1] == "TRACER_SCHEDULES_TEARDOWN_OK"
