"""The in-container driver for the schedules e2e (24.2-10, D-26).

Run as `python -m tests.e2e_schedules_driver <verb>` from the workspace: the container harness
(`scripts/container-e2e-verify.sh schedules`) has the real engine write and remove the units, so
no unit file is ever hand-written. Verbs:

  on <id>                   turn a schedule on; prints `ON <id> next=<iso or ->` and `WARN <text>`
  off <id>                  turn it off; prints `OFF <id>`
  retime <id> <n> <HH:MM>   change the interval and start; prints `RETIME <id> next=<iso or ->`
  cells                     one `CELL <id> <Last cell>` line per schedule
  argv <id>                 the runner command a unit executes, one argument per line

It imports only `installer` and the standard library: the container runs it with `--no-dev`.
Exit codes: 0 done, 1 an error (`ERROR <first line>`), 2 a bad verb, argument count or id.
"""

import os
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from installer import cursor_shim, daemon, schedules
from installer import platform as host_platform
from installer.run import CommandError
from installer.sanitize import sanitize_log_line

_ARITY = {"on": 1, "off": 1, "retime": 3, "cells": 0, "argv": 1}


def _context() -> schedules.ScheduleContext:
    """The shared context (24.2-01) over the real runners, keyed by the container's own OS."""
    return schedules.context_for(
        host_platform.detect().os,
        checkout=Path.cwd(),
        present=lambda tool: shutil.which(tool) is not None,
        read_models=cursor_shim.read_models,
    )


def _next(report: schedules.ApplyReport) -> str:
    return report.next_run.isoformat(timespec="minutes") if report.next_run else "-"


def _run(ctx: schedules.ScheduleContext, verb: str, args: Sequence[str]) -> None:
    if verb == "cells":
        runs = schedules.read_last_runs(ctx.log_path, ctx.lock_path)
        for schedule in schedules.SCHEDULES:
            cell = schedules.last_cell(runs.get(schedule.id), datetime.now())
            print(f"CELL {schedule.id} {cell}")
        return
    schedule_id = args[0]
    if verb == "on":
        report = schedules.turn_on(ctx, schedule_id)
        print(f"ON {schedule_id} next={_next(report)}")
        for warning in report.warnings:
            print(f"WARN {warning}")
    elif verb == "off":
        report = schedules.turn_off(ctx, schedule_id)
        print(f"OFF {schedule_id}")
        for warning in report.warnings:
            print(f"WARN {warning}")
    elif verb == "retime":
        report = schedules.retime(ctx, schedule_id, int(args[1]), args[2])
        print(f"RETIME {schedule_id} next={_next(report)}")
    else:
        found = ctx.which("uv")
        if found is None:
            raise OSError("uv was not found on PATH")
        schedule = schedules.schedule_by_id(schedule_id)
        print("\n".join(schedules.runner_argv(ctx, schedule, Path(os.path.abspath(found)))))


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in _ARITY or len(args) - 1 != _ARITY[args[0]]:
        print(f"usage: e2e_schedules_driver {' | '.join(_ARITY)}", file=sys.stderr)
        return 2
    verb, rest = args[0], args[1:]
    if rest and rest[0] not in {schedule.id for schedule in schedules.SCHEDULES}:
        print(f"unknown schedule id: {rest[0]}", file=sys.stderr)
        return 2
    try:
        _run(_context(), verb, rest)
    except (OSError, CommandError, daemon.DaemonScheduleError, ValueError) as error:
        first = (sanitize_log_line(str(error)).splitlines() or [type(error).__name__])[0]
        print(f"ERROR {first}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
