"""Pin the wiring between .pre-commit-config.yaml, the Makefile gate targets and pyproject.toml."""

import re
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

from tests.test_makefile import gate_targets, recipes

ROOT = Path(__file__).resolve().parent.parent
PRE_COMMIT_CONFIG = ROOT / ".pre-commit-config.yaml"
PYPROJECT = ROOT / "pyproject.toml"
DEVTOOLS_INIT = ROOT / "devtools" / "__init__.py"


def _hooks() -> list[dict[Any, Any]]:
    config = cast(dict[Any, Any], yaml.safe_load(PRE_COMMIT_CONFIG.read_text()))
    hooks: list[dict[Any, Any]] = []
    for repo in config["repos"]:
        hooks.extend(repo["hooks"])
    return hooks


def _commit_hooks(hooks: list[dict[Any, Any]]) -> list[dict[Any, Any]]:
    """Hooks that run at the commit stage; a hook with no `stages` key runs at commit."""
    return [hook for hook in hooks if "pre-commit" in hook.get("stages", ["pre-commit"])]


def _target(entry: str) -> str:
    return entry.removeprefix("make ")


def test_gate_targets_come_from_the_makefile_marker() -> None:
    targets = gate_targets()
    assert targets, "no [gate]-marked target in the Makefile"
    assert "test" in targets


def test_every_commit_hook_calls_an_existing_gate_target() -> None:
    targets = recipes()
    hooks = _commit_hooks(_hooks())
    assert hooks, "no commit-stage hooks"
    for hook in hooks:
        entry = str(hook.get("entry"))
        match = re.fullmatch(r"make ([a-z-]+)", entry)
        assert match is not None, f"{hook.get('id')}: entry is not `make <target>`: {entry}"
        assert match.group(1) in targets, hook.get("id")
        assert hook.get("language") == "system", hook.get("id")
        assert hook.get("pass_filenames") is False, hook.get("id")
        assert hook.get("always_run") is True, hook.get("id")


def test_commit_stage_targets_equal_the_gate_targets_as_a_set() -> None:
    hooks = _commit_hooks(_hooks())
    commit_targets = {_target(str(hook.get("entry"))) for hook in hooks}
    assert commit_targets == set(gate_targets()) - {"test"}
    for hook in hooks:
        assert hook.get("stages") == ["pre-commit", "pre-push"], hook.get("id")
        assert hook.get("name") == hook.get("entry"), hook.get("id")


def test_validate_is_exactly_pre_commit_run_all_files() -> None:
    _, lines = recipes()["validate"]
    commands = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    assert commands == ["uv run pre-commit run --all-files"]


def test_devtools_joins_every_gate() -> None:
    pyproject = tomllib.loads(PYPROJECT.read_text())
    assert "devtools" in pyproject["tool"]["pyright"]["include"]
    assert "devtools" in pyproject["tool"]["coverage"]["run"]["source"]
    assert "devtools" in pyproject["tool"]["vulture"]["paths"]
    assert DEVTOOLS_INIT.is_file()
    for name in ("lint", "format-check", "security"):
        _, lines = recipes().get(name, ([], []))
        assert "devtools" in "\n".join(lines), name
