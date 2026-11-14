"""Parse the Makefile and assert launcher vs quality-gate recipes stay separated."""

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"

_LAUNCHER_LINE = re.compile(
    r"^\s*uv run(\s+--?[A-Za-z][-A-Za-z]*)*\s+setup\.py\b",
)
_FORBIDDEN_RUNS = {"setup.py", "install.sh", "container-e2e-verify.sh"}
_SHELLS = {"bash", "sh", "python", "python3"}


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


def test_verify_registry_target_is_read_only_by_default() -> None:
    recipes = _recipes()
    assert "verify-registry" in recipes
    _, lines = recipes["verify-registry"]
    joined = "\n".join(lines)
    assert "uv run --isolated --no-dev python -m installer.verify_registry" in joined
    assert "$(ARGS)" in joined
    assert "--write" not in joined
    assert "--issue" not in joined
    makefile = MAKEFILE.read_text()
    assert "verify-registry" in makefile.split(".PHONY:")[1].split("\n")[0]
    assert re.search(r"^verify-registry:.*?## .+$", makefile, re.MULTILINE), (
        "verify-registry needs a ## help comment"
    )


def _invoked_names(line: str) -> list[str]:
    """Basenames a recipe line runs: the program, and the script a shell or python runs."""
    words = [word for word in line.strip().lstrip("@-").split() if not word.startswith("-")]
    if words[:2] == ["uv", "run"]:
        words = words[2:]
    names = [Path(words[0]).name] if words else []
    if names and names[0] in _SHELLS and len(words) > 1:
        names.append(Path(words[1]).name)
    return names


def test_gate_recipes_never_run_a_real_install() -> None:
    recipes = _recipes()
    for name in ("validate", "test"):
        _, lines = recipes[name]
        for line in lines:
            code = line.strip()
            if not code or code.startswith("#"):
                continue
            assert not set(_invoked_names(code)) & _FORBIDDEN_RUNS, f"{name}: {code}"


def test_e2e_script_refuses_without_a_container_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for name in ("container-e2e-verify.sh", "detect-container-runtime.sh"):
        shutil.copy2(ROOT / "scripts" / name, repo / "scripts" / name)
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    for tool in ("bash", "dirname", "uname"):
        found = shutil.which(tool)
        assert found is not None, f"{tool} is required on every supported host"
        (fakebin / tool).symlink_to(os.path.realpath(found))
    scratch = tmp_path / "home"
    scratch.mkdir()
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(
        [bash, str(repo / "scripts" / "container-e2e-verify.sh"), "all"],
        env={"PATH": str(fakebin), "HOME": str(scratch), "LANG": "C"},
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "CONTAINER_TOOL unset after detection" in result.stderr
    assert not (repo / ".e2e-artifacts").exists()


_E2E_SCRIPT = "scripts/container-e2e-verify.sh"


def test_e2e_script_appears_in_gates_only_as_a_shellcheck_argument() -> None:
    """R1-04: a lint argument is not a run; nothing else of the e2e reaches the gates."""
    recipes = _recipes()
    for name in ("validate", "test"):
        prereqs, lines = recipes[name]
        kept: list[str] = []
        for line in lines:
            if _E2E_SCRIPT in line:
                assert _invoked_names(line) == ["shellcheck"], f"{name}: {line}"
                line = line.replace(_E2E_SCRIPT, "")
            kept.append(line)
        text = "\n".join([*prereqs, *kept])
        assert "container-e2e-verify.sh" not in text, name
        assert not re.search(r"\be2e\b", text), name


def test_audit_catalog_target() -> None:
    recipes = _recipes()
    assert "audit-catalog" in recipes
    _, lines = recipes["audit-catalog"]
    joined = "\n".join(lines)
    assert "uv run --isolated --no-dev python -m installer.catalog_audit" in joined
    assert "$(ARGS)" in joined
    makefile = MAKEFILE.read_text()
    assert "audit-catalog" in makefile.split(".PHONY:")[1].split("\n")[0]
    assert re.search(r"^audit-catalog:.*?## .+$", makefile, re.MULTILINE), (
        "audit-catalog needs a ## help comment"
    )
