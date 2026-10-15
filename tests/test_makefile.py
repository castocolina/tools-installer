"""Parse the Makefile and assert launcher vs quality-gate recipes stay separated."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"

_LAUNCHER_LINE = re.compile(
    r"^\s*uv run(\s+--?[A-Za-z][-A-Za-z]*)*\s+setup\.py\b",
)


def _recipes() -> dict[str, tuple[list[str], list[str]]]:
    """Return target -> (prerequisites, recipe lines) for every make target."""
    lines = MAKEFILE.read_text().splitlines()
    result: dict[str, tuple[list[str], list[str]]] = {}
    current_target: str | None = None
    prereqs: list[str] = []
    recipe: list[str] = []

    for line in lines:
        if line.startswith("\t"):
            if current_target is not None:
                recipe.append(line)
            continue
        if current_target is not None:
            result[current_target] = (prereqs, recipe)
        match = re.match(r"^([a-zA-Z0-9_-]+)\s*:(.*)$", line)
        if match:
            current_target = match.group(1)
            tail = match.group(2).strip()
            if "##" in tail:
                tail = tail.split("##", 1)[0].strip()
            prereqs = [p.strip() for p in tail.split() if p.strip()]
            recipe = []
        else:
            current_target = None
            prereqs = []
            recipe = []

    if current_target is not None:
        result[current_target] = (prereqs, recipe)
    return result


def test_launch_targets_run_without_the_dev_venv() -> None:
    recipes = _recipes()
    for name in ("setup", "doctor", "fix", "uninstall", "guard", "unguard"):
        _, lines = recipes[name]
        joined = "\n".join(lines)
        assert "uv run --isolated --no-dev setup.py" in joined, name


def test_run_is_an_alias_of_setup() -> None:
    prereqs, recipe = _recipes()["run"]
    assert prereqs == ["setup"]
    assert recipe == []


def test_every_setup_py_recipe_uses_the_launch_form() -> None:
    launcher_lines: list[str] = []
    for _, lines in _recipes().values():
        for line in lines:
            if _LAUNCHER_LINE.match(line):
                launcher_lines.append(line)
    assert len(launcher_lines) == 6
    for line in launcher_lines:
        assert "uv run --isolated --no-dev setup.py" in line


def test_gate_targets_keep_dev_dependencies() -> None:
    recipes = _recipes()
    for name in ("validate", "test"):
        joined = "\n".join(recipes[name][1])
        assert "--no-dev" not in joined
        assert "--isolated" not in joined
