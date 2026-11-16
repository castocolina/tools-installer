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


def recipes() -> dict[str, tuple[list[str], list[str]]]:
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


def gate_targets() -> list[str]:
    """Return the `[gate]`-marked targets in file order: the ones the commit and push hooks run."""
    targets: list[str] = []
    for line in MAKEFILE.read_text().splitlines():
        match = re.match(r"^([a-zA-Z0-9_-]+)\s*:(.*)$", line)
        if match and "## [gate] " in match.group(2):
            targets.append(match.group(1))
    return targets


def test_launch_targets_run_without_the_dev_venv() -> None:
    recipe_map = recipes()
    for name in ("run", "doctor", "fix", "uninstall"):
        _, lines = recipe_map[name]
        joined = "\n".join(lines)
        assert "uv run --isolated --no-dev setup.py" in joined, name


def test_run_launches_the_wizard_and_setup_is_gone() -> None:
    recipe_map = recipes()
    prereqs, lines = recipe_map["run"]
    assert prereqs == []
    assert "uv run --isolated --no-dev setup.py $(ARGS)" in "\n".join(lines)
    assert "setup" not in recipe_map
    phony = MAKEFILE.read_text().split(".PHONY:")[1].split("\n")[0].split()
    assert "setup" not in phony


def test_every_setup_py_recipe_uses_the_launch_form() -> None:
    launcher_targets: list[str] = []
    for name, (_, lines) in recipes().items():
        launcher_lines = [line for line in lines if _LAUNCHER_LINE.match(line)]
        if launcher_lines:
            launcher_targets.append(name)
        for line in launcher_lines:
            assert "uv run --isolated --no-dev setup.py" in line
    assert launcher_targets == ["run", "doctor", "fix", "uninstall"]


def test_retired_guard_targets_are_gone() -> None:
    makefile = MAKEFILE.read_text()
    recipe_map = recipes()
    assert "guard" not in recipe_map
    assert "unguard" not in recipe_map
    phony = makefile.split(".PHONY:")[1].split("\n")[0].split()
    assert "guard" not in phony
    assert "unguard" not in phony
    assert not [line for line in makefile.splitlines() if "##" in line and "guard" in line.lower()]


def test_gate_targets_keep_dev_dependencies() -> None:
    recipe_map = recipes()
    for name in [*gate_targets(), "validate", "dev-setup"]:
        joined = "\n".join(recipe_map[name][1])
        assert "--no-dev" not in joined
        assert "--isolated" not in joined


def test_dev_setup_installs_deps_then_the_hooks() -> None:
    prereqs, lines = recipes()["dev-setup"]
    assert prereqs == []
    assert [line.strip() for line in lines] == [
        "uv sync",
        "uv run python -m devtools.hooks install",
    ]
    makefile = MAKEFILE.read_text()
    assert "dev-setup" in makefile.split(".PHONY:")[1].split("\n")[0].split()
    assert re.search(r"^dev-setup:.*?## .+$", makefile, re.MULTILINE), (
        "dev-setup needs a ## help comment"
    )


def test_old_bootstrap_target_is_gone() -> None:
    assert "install" not in recipes()
    assert "install" not in MAKEFILE.read_text().split(".PHONY:")[1].split("\n")[0].split()


def test_verify_registry_target_is_read_only_by_default() -> None:
    recipe_map = recipes()
    assert "verify-registry" in recipe_map
    _, lines = recipe_map["verify-registry"]
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
    recipe_map = recipes()
    for name in [*gate_targets(), "validate"]:
        _, lines = recipe_map[name]
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
    recipe_map = recipes()
    for name in [*gate_targets(), "validate"]:
        prereqs, lines = recipe_map[name]
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
    recipe_map = recipes()
    assert "audit-catalog" in recipe_map
    _, lines = recipe_map["audit-catalog"]
    joined = "\n".join(lines)
    assert "uv run --isolated --no-dev python -m installer.catalog_audit" in joined
    assert "$(ARGS)" in joined
    makefile = MAKEFILE.read_text()
    assert "audit-catalog" in makefile.split(".PHONY:")[1].split("\n")[0]
    assert re.search(r"^audit-catalog:.*?## .+$", makefile, re.MULTILINE), (
        "audit-catalog needs a ## help comment"
    )


def test_gate_targets_are_phony_and_documented() -> None:
    targets = gate_targets()
    assert len(targets) >= 7
    phony = MAKEFILE.read_text().split(".PHONY:")[1].split("\n")[0].split()
    for name in targets:
        assert name in phony, name


def test_help_lists_names_with_digits() -> None:
    _, lines = recipes()["help"]
    assert "^[a-zA-Z0-9_-]+:.*?## .*$$" in "\n".join(lines)
