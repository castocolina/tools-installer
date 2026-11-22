"""Offline child for the scheduled update-all tracer."""

import json
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch as mock_patch

import setup
from installer import schedules, update_all
from installer.model import Tool
from installer.platform import Platform
from installer.run import CommandError
from installer.schedule_run import RunDeps, update_all_runner
from installer.update import UpdateOutcome, UpdateTarget
from tests.update_all_doubles import (
    ScriptedProbe,
    SequenceRefresher,
    SpyService,
    catalog_tool,
    run_deps,
    state,
)
from tests.update_check_child import patch
from tests.update_check_doubles import real_service


def main(config_path: str, argv: list[str]) -> int:
    config = json.loads(Path(config_path).read_text())
    home = Path(config["home"])
    runs: list[str] = []

    class UpdateSpy:
        def run(self, target: object) -> None:
            runs.append(str(target))
            raise AssertionError("unexpected update")

    try:
        patch(setup, "__file__", str(Path(config["checkout"]) / "setup.py"))
        patch(
            setup,
            "detect",
            lambda: Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        )

        def load(_path: object) -> list[object]:
            return []

        patch(setup, "load_tools", load)
        service = real_service(
            home, resolve_tag=lambda _repo: "v1", now=lambda: datetime.now(UTC), installed="v1"
        )

        def services(*_args: object, **_kwargs: object) -> tuple[object, object, None, None]:
            return service, UpdateSpy(), None, None

        patch(setup, "_build_services", services)
        scenario = config.get("scenario", "empty")
        if scenario == "hang":
            now = datetime.now(UTC)
            tool = catalog_tool("brew")
            states = {tool.id: state(tool, "installer")}
            pid_dir = Path(config["pid_dir"])
            update_all.KILL_GRACE = config["kill_grace"]

            class HangingService(SpyService):
                def run(self, target: UpdateTarget) -> UpdateOutcome:
                    script = """import os, signal, subprocess, sys, time
from pathlib import Path
p = Path(sys.argv[1])
if sys.argv[2] == '1': signal.signal(signal.SIGTERM, signal.SIG_IGN)
for name, session in [('group', False), ('escaped', True)]:
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'],
        start_new_session=session, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (p / name).write_text(str(child.pid))
(p / 'command').write_text(str(os.getpid()))
while True: time.sleep(1)
"""
                    try:
                        update_all_runner(
                            [
                                sys.executable,
                                "-c",
                                script,
                                str(pid_dir),
                                str(int(config["ignore_term"])),
                            ],
                            timeout=config["hang_timeout"],
                        )
                    except CommandError:
                        return UpdateOutcome(
                            target.tool.id, "failed", target.ownership.owner, "timeout"
                        )
                    raise AssertionError("command unexpectedly ended")

            ctx = schedules.context_for(
                "fedora", checkout=Path(config["checkout"]), read_models=lambda _a: None
            )
            deps = run_deps(
                [tool],
                ctx,
                service=HangingService(),
                owners={tool.id: states[tool.id].ownership},
                refresh=SequenceRefresher(home / "versions", [states], clock=lambda: now),
                now=lambda: now,
                probe=ScriptedProbe({tool.id: ["1"]}),
            )

            def hang_deps(*_a: object, **_k: object) -> RunDeps:
                return deps

            patch(setup, "_schedule_run_deps", hang_deps)
        if scenario in ("three", "failing"):
            now = datetime.now(UTC)
            brew, uv, ruff = (catalog_tool(name) for name in ("brew", "uv", "ruff"))
            states = {
                "brew": state(brew, "installer"),
                "uv": state(uv, "installer"),
                "ruff": state(ruff, "brew" if scenario == "failing" else "uv", outdated=True),
            }
            outcomes = (
                {"brew": UpdateOutcome("brew", "failed", "installer", "boom")}
                if scenario == "failing"
                else {}
            )
            spy = SpyService(outcomes)
            runs = spy.runs
            ctx = schedules.context_for(
                "fedora", checkout=Path(config["checkout"]), read_models=lambda _a: None
            )
            deps = run_deps(
                [brew, uv, ruff],
                ctx,
                service=spy,
                owners={key: item.ownership for key, item in states.items()},
                refresh=SequenceRefresher(home / "versions", [states], clock=lambda: now),
                now=lambda: now,
                probe=ScriptedProbe({name: ["1", "2"] for name in states}),
            )

            def build_deps(_tools: list[Tool], _platform: Platform, **_kwargs: object) -> RunDeps:
                return deps

            if config.get("notifier") == "real":
                refresh = deps.refresh
                assert isinstance(refresh, SequenceRefresher)

                def resolve(tool: Tool) -> object:
                    return states[tool.id].ownership

                def load_real(_path: object) -> list[Tool]:
                    return [brew, uv, ruff]

                def build_real(*_a: object, **_k: object) -> tuple[object, object, None, None]:
                    return refresh, spy, None, None

                def probe(*_a: object, **_k: object) -> None:
                    return None

                vars(refresh)["resolve_owner"] = resolve
                patch(setup, "load_tools", load_real)
                patch(setup, "_build_services", build_real)
                patch(setup, "probe_version_output", probe)
            else:
                patch(setup, "_schedule_run_deps", build_deps)
        with mock_patch.object(os, "geteuid", return_value=1000):
            code = setup.main(argv)
        ctx = schedules.context_for(
            "fedora", checkout=Path(config["checkout"]), read_models=lambda _a: None
        )
        Path(config["result"]).write_text(
            json.dumps(
                {
                    "code": code,
                    "runs": runs,
                    "bytecode": os.environ.get("PYTHONDONTWRITEBYTECODE"),
                    "no_sudo": os.environ.get("HOMEBREW_NO_SUDO"),
                    "lock": str(ctx.lock_path),
                }
            )
        )
        return code
    except BaseException:
        Path(config["traceback"]).write_text(traceback.format_exc())
        raise
