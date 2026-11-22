"""Offline child for the scheduled update-all tracer."""

import json
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path

import setup
from installer import schedules
from installer.model import Tool
from installer.platform import Platform
from installer.schedule_run import RunDeps
from installer.update import UpdateOutcome
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

            def build_deps(_tools: list[Tool], _platform: Platform) -> RunDeps:
                return deps

            patch(setup, "_schedule_run_deps", build_deps)
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
