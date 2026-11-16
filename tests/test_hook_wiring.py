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
# The hook-skipping git flag and the SKIP variable (P1): no gate file may offer either.
_BYPASS = re.compile(r"--no-verify|(?<![A-Za-z0-9_])SKIP=")


def _config() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(PRE_COMMIT_CONFIG.read_text()))


def _hooks() -> list[dict[Any, Any]]:
    hooks: list[dict[Any, Any]] = []
    for repo in _config()["repos"]:
        hooks.extend(repo["hooks"])
    return hooks


def _commit_hooks(hooks: list[dict[Any, Any]]) -> list[dict[Any, Any]]:
    """Hooks that run at the commit stage; a hook with no `stages` key runs at commit."""
    return [hook for hook in hooks if "pre-commit" in hook.get("stages", ["pre-commit"])]


def _target(entry: str) -> str:
    return entry.removeprefix("make ")


def wiring_errors(
    hooks: list[dict[Any, Any]],
    recipe_map: dict[str, tuple[list[str], list[str]]],
    gates: set[str],
) -> list[str]:
    """Every way the hooks drift from the gate targets; an empty list means they are wired."""
    errors: list[str] = []
    if not gates:
        errors.append("no [gate]-marked target in the Makefile")
    commit = _commit_hooks(hooks)
    if not commit:
        errors.append("no commit-stage hook")
    commit_targets: list[str] = []
    for hook in commit:
        hook_id = str(hook.get("id"))
        entry = str(hook.get("entry"))
        match = re.fullmatch(r"make ([a-z-]+)", entry)
        if match is None:
            errors.append(f"{hook_id}: entry must be exactly `make <target>`, got {entry!r}")
            continue
        target = match.group(1)
        commit_targets.append(target)
        if target not in recipe_map:
            errors.append(f"{hook_id}: no make target named {target}")
        if target == "test":
            errors.append(f"{hook_id}: make test runs at the push stage only")
        if hook.get("name") != entry:
            errors.append(f"{hook_id}: name must equal entry {entry!r}")
        if hook.get("stages") != ["pre-commit", "pre-push"]:
            errors.append(f"{hook_id}: stages must be [pre-commit, pre-push]")
        if (
            hook.get("language") != "system"
            or hook.get("pass_filenames") is not False
            or hook.get("always_run") is not True
        ):
            errors.append(f"{hook_id}: needs language system, pass_filenames and always_run")
    for target in sorted(set(commit_targets) - gates):
        errors.append(f"commit-stage hook calls {target}, which is not a [gate] target")
    for target in sorted((gates - {"test"}) - set(commit_targets)):
        errors.append(f"gate target {target} has no commit-stage hook")
    push_targets = [
        _target(str(hook.get("entry"))) for hook in hooks if "pre-push" in hook.get("stages", [])
    ]
    if push_targets[-1:] != ["test"] or set(push_targets[:-1]) != gates - {"test"}:
        errors.append("the push stage must run every gate, then make test last")
    if [i for i, hook in enumerate(hooks) if hook.get("entry") == "make test"] != [len(hooks) - 1]:
        errors.append("make test must be the single hook, and the last one in the file")
    return errors


def _real_inputs() -> tuple[list[dict[Any, Any]], dict[str, tuple[list[str], list[str]]], set[str]]:
    return _hooks(), recipes(), set(gate_targets())


def _edited(hooks: list[dict[Any, Any]], entry: str, new_entry: str) -> list[dict[Any, Any]]:
    edited = [dict(hook) for hook in hooks]
    for hook in edited:
        if hook.get("entry") == entry:
            hook["entry"] = new_entry
    return edited


def _gate_files() -> list[Path]:
    files = [ROOT / "Makefile", PRE_COMMIT_CONFIG, ROOT / "AGENTS.md"]
    for folder in (ROOT / ".github", ROOT / "scripts"):
        files.extend(path for path in sorted(folder.rglob("*")) if path.is_file())
    files.extend(sorted((ROOT / "devtools").rglob("*.py")))
    files.extend(sorted((ROOT / ".claude").glob("*.md")))
    files.extend(sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")))
    return files


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


def test_the_test_hook_is_push_only_and_last() -> None:
    hooks = _hooks()
    test_hooks = [hook for hook in hooks if hook.get("entry") == "make test"]
    assert len(test_hooks) == 1
    hook = test_hooks[0]
    assert hook.get("id") == "tests"
    assert hook.get("name") == "make test"
    assert hook.get("stages") == ["pre-push"]
    assert hook.get("always_run") is True
    assert hook.get("pass_filenames") is False
    assert hooks[-1] is hook
    recipe_map = recipes()
    for commit_hook in _commit_hooks(hooks):
        _, lines = recipe_map[_target(str(commit_hook.get("entry")))]
        assert not any("pytest" in line for line in lines), commit_hook.get("id")


def test_push_stage_runs_every_gate_then_test() -> None:
    push_targets = [
        _target(str(hook.get("entry"))) for hook in _hooks() if "pre-push" in hook.get("stages", [])
    ]
    assert push_targets[-1:] == ["test"]
    assert set(push_targets[:-1]) == set(gate_targets()) - {"test"}


def test_pre_commit_installs_only_the_commit_hook() -> None:
    config = _config()
    assert config.get("default_install_hook_types") == ["pre-commit"]
    assert "fail_fast" not in config


def test_no_hook_auto_fixes_files() -> None:
    """P3 (pin): each hook's recipe is followed; none fixes files or formats without --check."""
    recipe_map = recipes()
    for hook in _hooks():
        entry = str(hook.get("entry"))
        assert "--fix" not in entry, hook.get("id")
        _, lines = recipe_map[_target(entry)]
        for line in lines:
            assert "--fix" not in line, f"{hook.get('id')}: {line}"
            if "ruff format" in line:
                assert "--check" in line, f"{hook.get('id')}: {line}"


def test_no_gate_file_offers_a_hook_bypass() -> None:
    """P1 (pin): no gate file, script or rule doc offers a way past the hooks."""
    files = _gate_files()
    assert files, "the bypass scan found no gate files"
    scanned = ", ".join(str(path.relative_to(ROOT)) for path in files)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert not _BYPASS.search(text), f"{path.relative_to(ROOT)} offers a hook bypass; {scanned}"


def test_wiring_errors_is_empty_for_the_real_files() -> None:
    hooks, recipe_map, gates = _real_inputs()
    assert wiring_errors(hooks, recipe_map, gates) == []


def test_wiring_errors_flags_zero_checks_on_either_side() -> None:
    hooks, recipe_map, gates = _real_inputs()
    no_hooks = wiring_errors([], recipe_map, gates)
    assert any("no commit-stage hook" in error for error in no_hooks)
    no_gates = wiring_errors(hooks, recipe_map, set())
    assert any("no [gate]-marked target" in error for error in no_gates)


def test_wiring_errors_flags_an_entry_with_an_extra_argument() -> None:
    hooks, recipe_map, gates = _real_inputs()
    edited = _edited(hooks, "make lint", "make lint --quiet")
    errors = wiring_errors(edited, recipe_map, gates)
    assert any("must be exactly `make <target>`" in error for error in errors)


def test_wiring_errors_flags_a_hook_calling_a_missing_target() -> None:
    hooks, recipe_map, gates = _real_inputs()
    edited = _edited(hooks, "make lint", "make nosuch")
    errors = wiring_errors(edited, recipe_map, gates)
    assert any("no make target named nosuch" in error for error in errors)


def test_wiring_errors_flags_a_gate_with_no_commit_hook() -> None:
    hooks, recipe_map, gates = _real_inputs()
    unhooked = [hook for hook in hooks if hook.get("entry") != "make lint"]
    errors = wiring_errors(unhooked, recipe_map, gates)
    assert "gate target lint has no commit-stage hook" in errors


def test_wiring_errors_flags_a_new_gate_target_with_no_hook() -> None:
    hooks, recipe_map, gates = _real_inputs()
    new_gate: tuple[list[str], list[str]] = ([], ["\tuv run vulture"])
    grown_map = {**recipe_map, "complexity": new_gate}
    errors = wiring_errors(hooks, grown_map, gates | {"complexity"})
    assert "gate target complexity has no commit-stage hook" in errors


def test_wiring_errors_flags_make_test_before_a_static_hook() -> None:
    hooks, recipe_map, gates = _real_inputs()
    test_hooks = [hook for hook in hooks if hook.get("entry") == "make test"]
    static = [hook for hook in hooks if hook.get("entry") != "make test"]
    errors = wiring_errors(test_hooks + static, recipe_map, gates)
    assert any("the last one in the file" in error for error in errors)


def test_wiring_errors_accepts_reordered_static_hooks() -> None:
    hooks, recipe_map, gates = _real_inputs()
    test_hooks = [hook for hook in hooks if hook.get("entry") == "make test"]
    static = [hook for hook in hooks if hook.get("entry") != "make test"]
    assert wiring_errors([*reversed(static), *test_hooks], recipe_map, gates) == []
