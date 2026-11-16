"""Import-reachability guard for ``installer/`` (phase 25, D-01).

Module-level reachability from the production entry points: ``setup.py``,
``installer/__main__.py`` when it exists, and the ``python -m installer.<x>`` modules the
Makefile, ``install.sh`` and the GitHub workflows invoke. A ``__main__`` guard alone does not
make a module an entry point. The walk follows function-level imports
and skips ``if TYPE_CHECKING:`` bodies, so only runtime imports make a module
reachable. A string-keyed dispatch table needs no special case: its targets are
plain callables imported by the table's own module, so the module graph reaches them.

Symbol-level dead code stays with vulture. Do not weaken this guard to a name
grep: a name that appears in a comment is not an import, and a module reached
only through a string table is still reached through the table's module.
"""

import ast
import io
import re
import tokenize
from collections import deque
from collections.abc import Mapping
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# Installed data files that run on the user's machine and are read by path, never imported.
_EXEMPT_DIRS: tuple[str, ...] = ("installer/helper_assets",)
_PYTHON_M = re.compile(r"python -m (installer(?:\.\w+)+)")


def _installer_files(root: Path) -> dict[str, Path]:
    return {_dotted(root, path): path for path in sorted((root / "installer").rglob("*.py"))}


def _installer_modules(root: Path) -> dict[str, Path]:
    return {
        name: path for name, path in _installer_files(root).items() if not _is_exempt(root, path)
    }


def _exempt_modules(root: Path) -> dict[str, Path]:
    return {name: path for name, path in _installer_files(root).items() if _is_exempt(root, path)}


def _is_exempt(root: Path, path: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    return any(relative.startswith(f"{directory}/") for directory in _EXEMPT_DIRS)


def _dotted(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_main_guard(test: ast.expr) -> bool:
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _has_main_guard(path: Path) -> bool:
    return any(isinstance(node, ast.If) and _is_main_guard(node.test) for node in _parse(path).body)


def _entry_modules(root: Path) -> set[str]:
    declared = _python_m_modules(root) | {"installer.__main__"}
    return {name for name in _installer_modules(root) if name in declared}


def _with_parents(dotted: str, modules: Mapping[str, Path]) -> set[str]:
    parts = dotted.split(".")
    prefixes = {".".join(parts[:index]) for index in range(1, len(parts) + 1)}
    return {prefix for prefix in prefixes if prefix in modules}


def _runtime_imports(path: Path, modules: Mapping[str, Path], root: Path) -> set[str]:
    relative = path.relative_to(root)
    collector = _EdgeCollector(modules, relative.parts[:-1], relative.as_posix())
    collector.visit(_parse(path))
    return collector.names


def _absolute_module(node: ast.ImportFrom, package: tuple[str, ...], label: str) -> str:
    if node.level == 0:
        return node.module or ""
    if len(package) < node.level:
        raise AssertionError(
            f"{label}: relative import (level {node.level}) climbs above the top-level package"
        )
    base = package[: len(package) - (node.level - 1)]
    return ".".join([*base, *(node.module.split(".") if node.module else [])])


class _EdgeCollector(ast.NodeVisitor):
    """Collects the known modules a file imports at runtime, skipping ``TYPE_CHECKING`` bodies."""

    def __init__(self, modules: Mapping[str, Path], package: tuple[str, ...], label: str) -> None:
        self._modules = modules
        self._package = package
        self._label = label
        self.names: set[str] = set()

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking(node.test):
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = _absolute_module(node, self._package, self._label)
        self._add(module)
        for alias in node.names:
            self._add(f"{module}.{alias.name}")

    def _add(self, dotted: str) -> None:
        self.names |= _with_parents(dotted, self._modules)


def _is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _reachable_modules(root: Path) -> set[str]:
    modules = _installer_modules(root)
    reached: set[str] = set()
    queue: deque[Path] = deque([root / "setup.py"])

    def reach(dotted: str) -> None:
        for name in _with_parents(dotted, modules):
            if name not in reached:
                reached.add(name)
                queue.append(modules[name])

    for name in _entry_modules(root):
        reach(name)
    while queue:
        for name in _runtime_imports(queue.popleft(), modules, root):
            reach(name)
    return reached


def _unreachable_modules(root: Path) -> list[str]:
    return sorted(set(_installer_modules(root)) - _reachable_modules(root))


def _python_m_modules(root: Path) -> set[str]:
    launchers = [
        root / "Makefile",
        root / "install.sh",
        *(root / ".github/workflows").glob("*.yml"),
    ]
    found: set[str] = set()
    for launcher in launchers:
        if launcher.is_file():
            found.update(_PYTHON_M.findall(launcher.read_text(encoding="utf-8")))
    return found


def _top_level_assigned(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _scratch_tree(root: Path, files: Mapping[str, str]) -> Path:
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def test_every_installer_module_is_reachable_from_an_entry_point() -> None:
    assert _unreachable_modules(_ROOT) == []


def test_a_seeded_orphan_module_is_reported(tmp_path: Path) -> None:
    tree = _scratch_tree(
        tmp_path,
        {
            "setup.py": "import installer.a\n",
            "installer/__init__.py": "",
            "installer/a.py": "",
            "installer/orphan.py": "",
        },
    )
    assert _unreachable_modules(tree) == ["installer.orphan"]


def test_a_dead_module_with_a_main_guard_is_still_reported(tmp_path: Path) -> None:
    tree = _scratch_tree(
        tmp_path,
        {
            "setup.py": "import installer.a\n",
            "installer/__init__.py": "",
            "installer/a.py": "",
            "installer/dead.py": 'if __name__ == "__main__":\n    pass\n',
        },
    )
    assert _unreachable_modules(tree) == ["installer.dead"]


def test_every_main_guard_module_is_invoked_by_a_launcher() -> None:
    guarded = {n for n, p in _installer_modules(_ROOT).items() if _has_main_guard(p)}
    assert guarded == _python_m_modules(_ROOT)


def test_launchers_name_only_existing_entry_modules() -> None:
    named = _python_m_modules(_ROOT)
    assert named, "the Makefile names no installer entry module"
    for name in named:
        assert (_ROOT / Path(*name.split("."))).with_suffix(".py").is_file()
    for launcher in ("Makefile", "install.sh"):
        assert "setup.py" in (_ROOT / launcher).read_text(encoding="utf-8")


def test_a_function_level_import_is_an_edge(tmp_path: Path) -> None:
    tree = _scratch_tree(
        tmp_path,
        {
            "setup.py": "import installer.a\n",
            "installer/__init__.py": "",
            "installer/a.py": "def load() -> None:\n    from installer import lazy\n",
            "installer/lazy.py": "",
        },
    )
    assert _unreachable_modules(tree) == []


def test_a_type_checking_only_import_is_not_an_edge(tmp_path: Path) -> None:
    tree = _scratch_tree(
        tmp_path,
        {
            "setup.py": "import installer.a\n",
            "installer/__init__.py": "",
            "installer/a.py": (
                "from typing import TYPE_CHECKING\n\n"
                "if TYPE_CHECKING:\n"
                "    from installer import typing_only\n"
            ),
            "installer/typing_only.py": "",
        },
    )
    assert _unreachable_modules(tree) == ["installer.typing_only"]


def test_a_relative_import_is_an_edge(tmp_path: Path) -> None:
    siblings = _scratch_tree(
        tmp_path / "siblings",
        {
            "setup.py": "import installer.a\n",
            "installer/__init__.py": "",
            "installer/a.py": "from . import sibling\nfrom .other import value\n",
            "installer/sibling.py": "",
            "installer/other.py": "value = 1\n",
        },
    )
    assert _unreachable_modules(siblings) == []

    top_level = _scratch_tree(tmp_path / "top", {"setup.py": "from . import x\n"})
    with pytest.raises(AssertionError, match="setup.py"):
        _unreachable_modules(top_level)

    climbs = _scratch_tree(
        tmp_path / "climbs",
        {
            "setup.py": "import installer.a\n",
            "installer/__init__.py": "",
            "installer/a.py": "from .. import x\n",
        },
    )
    with pytest.raises(AssertionError, match=re.escape("installer/a.py")):
        _unreachable_modules(climbs)

    deep = _scratch_tree(
        tmp_path / "deep",
        {
            "setup.py": "import installer.sub.y\n",
            "installer/__init__.py": "",
            "installer/a.py": "",
            "installer/sub/__init__.py": "",
            "installer/sub/y.py": "from .. import a\n",
        },
    )
    assert _unreachable_modules(deep) == []


def test_the_exemptions_are_live() -> None:
    for directory in _EXEMPT_DIRS:
        path = _ROOT / directory
        assert path.is_dir(), f"{directory} is gone; drop it from _EXEMPT_DIRS"
        assert any(path.glob("*.py")), f"{directory} holds no .py file"
    exempt = _exempt_modules(_ROOT)
    assert exempt
    modules = _installer_modules(_ROOT)
    reachable_paths = [_ROOT / "setup.py", *(modules[name] for name in _reachable_modules(_ROOT))]
    for path in reachable_paths:
        assert _runtime_imports(path, exempt, _ROOT) == set(), f"{path} imports an exempt module"


def _defined_top_level(tree: ast.Module) -> set[str]:
    names = _top_level_assigned(tree)
    names.update(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    return names


def _imported_modules(tree: ast.Module) -> set[str]:
    """Every module an import node names, at any depth; `from . import x` names `x`'s package."""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
            if node.module in (None, "installer"):
                modules.update(alias.name for alias in node.names)
    return modules


def _imports_any(tree: ast.Module, libraries: tuple[str, ...]) -> bool:
    return any(module.split(".")[0] in libraries for module in _imported_modules(tree))


def test_compose_is_prompt_free_and_nothing_imports_setup() -> None:
    compose_tree = _parse(_ROOT / "installer" / "compose.py")
    # Structural, so the module docstring may still name questionary.
    assert not _imports_any(compose_tree, ("questionary", "prompt_toolkit"))
    assert _imports_any(ast.parse("import questionary.prompts"), ("questionary",))
    assert _imports_any(ast.parse("from prompt_toolkit.input import Input"), ("prompt_toolkit",))
    importers = [
        name
        for name, path in _installer_files(_ROOT).items()
        if _imports_any(_parse(path), ("setup",))
    ]
    assert importers == []


# The modules the phase 25 split created: each stays small and carries no review history.
_SPLIT_MODULES: tuple[str, ...] = (
    "installer/app_messages.py",
    "installer/doctor_messages.py",
    "installer/doctor_screen.py",
    "installer/modals.py",
    "installer/mutation_lock.py",
    "installer/policies_screen.py",
    "installer/schedules_screen.py",
    "installer/uninstall_review.py",
    "installer/uninstall_screen.py",
    "installer/wizard_app.py",
)
_SPLIT_MAX_LINES = 800
# The composition root is big on purpose (no size cap) but still carries no review history.
_REVIEW_ID_FREE: tuple[str, ...] = (*_SPLIT_MODULES, "installer/compose.py", "setup.py")
# Code the split moved into modules that already existed; only these nodes are scanned there.
_MOVED_INTO_SHARED: tuple[tuple[str, str], ...] = (
    ("installer/systemd_daemon.py", "CompetingProbe"),
    ("installer/diskusage.py", "DiskPressureProbe"),
    ("installer/ui_common.py", "fit"),
    ("installer/ui_common.py", "sentence"),
    ("installer/ui_common.py", "TIMES_LISTED"),
)
_REVIEW_ID = re.compile(r"\b(?:CR|WR|IN|RR)-\d+\b|\bR\d+-\d+\b")


def _review_ids(source: str) -> list[str]:
    """Review ids in the comments and in the docstrings of the module, classes and functions."""
    found: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            found.extend(_REVIEW_ID.findall(token.string))
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            found.extend(_REVIEW_ID.findall(ast.get_docstring(node) or ""))
    return found


def _moved_source(path: Path, name: str) -> str:
    """The source of the top-level node binding `name` plus the `#` block directly above it."""
    lines = path.read_text(encoding="utf-8").splitlines()
    node = next(
        (n for n in _parse(path).body if name in _defined_top_level(ast.Module([n], []))), None
    )
    assert node is not None, f"{path.name}: no top-level definition of {name}"
    start = node.lineno
    while start > 1 and lines[start - 2].lstrip().startswith("#"):
        start -= 1
    return "\n".join(lines[start - 1 : node.end_lineno]) + "\n"


def test_the_review_id_scan_finds_a_seeded_id() -> None:
    assert _review_ids("x = 1  # WR-03: keep\n") == ["WR-03"]
    assert _review_ids('def f():\n    """Fixed in R1-07."""\n') == ["R1-07"]
    assert _review_ids('x = 1  # a plain why\n"""A plain docstring."""\n') == []


def test_split_modules_stay_under_800_lines() -> None:
    for relative in _SPLIT_MODULES:
        path = _ROOT / relative
        assert path.is_file(), f"{relative} is listed in _SPLIT_MODULES but does not exist"
        count = len(path.read_text(encoding="utf-8").splitlines())
        assert count <= _SPLIT_MAX_LINES, (
            f"{relative} has {count} lines, the cap is {_SPLIT_MAX_LINES}"
        )


def test_split_modules_and_the_composition_root_carry_no_review_ids() -> None:
    for relative in _REVIEW_ID_FREE:
        ids = _review_ids((_ROOT / relative).read_text(encoding="utf-8"))
        assert ids == [], f"{relative} carries review ids: {ids}"


def test_split_modules_import_the_app_only_for_typing() -> None:
    modules = _installer_modules(_ROOT)
    for relative in _SPLIT_MODULES:
        if relative == "installer/wizard_app.py":
            continue
        imported = _runtime_imports(_ROOT / relative, modules, _ROOT)
        assert "installer.wizard_app" not in imported, f"{relative} imports the app at runtime"


def test_code_moved_into_shared_modules_carries_no_review_ids(tmp_path: Path) -> None:
    seeded = tmp_path / "seeded.py"
    seeded.write_text("Other = 1  # IN-09\n# WR-10: why\nProbe = int\nAfter = 2  # CR-11\n")
    assert _review_ids(_moved_source(seeded, "Probe")) == ["WR-10"]
    for relative, name in _MOVED_INTO_SHARED:
        ids = _review_ids(_moved_source(_ROOT / relative, name))
        assert ids == [], f"{relative}:{name} carries review ids: {ids}"
