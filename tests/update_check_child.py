"""Child of the fake uv: execute the real headless setup with offline seams."""

import json
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import setup
from installer import receipts
from installer.platform import Platform
from tests.update_check_doubles import FakeGit, real_service, yq_tool


def patch(module: ModuleType, name: str, value: object) -> None:
    setattr(module, name, value)


def main(config_path: str) -> int:
    config = json.loads(Path(config_path).read_text())
    home = Path(config["home"])
    git = FakeGit(branch="main", behind=False)
    runs: list[str] = []

    class UpdateSpy:
        def run(self, target: object) -> None:
            runs.append(str(target))
            raise AssertionError("unexpected update")

    try:
        patch(receipts, "receipts_dir", lambda: home / ".local/state/tools-installer/receipts")
        patch(setup, "__file__", str(Path(config["checkout"]) / "setup.py"))
        patch(
            setup,
            "detect",
            lambda: Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        )

        def load(_path: object) -> list[object]:
            return [yq_tool()]

        patch(setup, "load_tools", load)
        service = real_service(
            home,
            resolve_tag=lambda _repo: "v5.0.0",
            now=lambda: datetime.now(UTC),
            installed="v4.0.0",
        )

        def services(*_args: object, **_kwargs: object) -> tuple[object, object, None, None]:
            return service, UpdateSpy(), None, None

        patch(setup, "_build_services", services)
        patch(setup, "git_for_check", git)
        code = setup.main(["--run-schedule", "check-updates", "--parent-holds-run-lock"])
        Path(config["result"]).write_text(
            json.dumps(
                {
                    "code": code,
                    "git": git.calls,
                    "runs": runs,
                    "bytecode": os.environ.get("PYTHONDONTWRITEBYTECODE"),
                    "github_token": "GITHUB_TOKEN" in os.environ,
                    "gh_token": "GH_TOKEN" in os.environ,
                }
            )
        )
        return code
    except BaseException:
        Path(config["traceback"]).write_text(traceback.format_exc())
        raise
