"""Import-reachability guard for ``installer/`` (phase 25, D-01).

Module-level reachability from the production entry points: ``setup.py``, every
``installer`` module with a top-level ``if __name__ == "__main__"`` guard, and
``installer/__main__.py`` when it exists. The walk follows function-level imports
and skips ``if TYPE_CHECKING:`` bodies, so only runtime imports make a module
reachable. String-keyed dispatch tables are listed in ``_DISPATCH_TABLES``; their
targets are plain callables imported by the table's own module, so the module
graph already reaches them and the dispatch test only proves it.

Symbol-level dead code stays with vulture. Do not weaken this guard to a name
grep: a name that appears in a comment is not an import, and a module reached
only through a string table is still reached through the table's module.
"""

import ast
import dataclasses
import functools
import importlib
import inspect
import re
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# Installed data files that run on the user's machine and are read by path, never imported.
_EXEMPT_DIRS: tuple[str, ...] = ("installer/helper_assets",)
_PYTHON_M = re.compile(r"python -m (installer(?:\.\w+)+)")
# The string-keyed callable dispatch tables at HEAD, as (module, attribute). The inventory
# test fails on any unlisted table, and the dispatch test fails on a stale entry.
_DISPATCH_TABLES: tuple[tuple[str, str], ...] = (
    ("installer.app", "_RECIPE_SERVICE_PID"),
    ("installer.app", "_RECIPE_SERVICE_FILE"),
    ("installer.catalog_audit", "_NAMED_READERS"),
    ("installer.download", "SCRIPT_ROOT_RESOLVERS"),
    ("installer.executors", "EXECUTORS"),
    ("installer.executors", "SMOKE_CHECKS"),
    ("installer.install_ownership", "_PROBES"),
    ("installer.install_ownership", "_OWNER_QUERIES"),
    ("installer.install_ownership", "_PATH_QUERIES"),
    ("installer.install_ownership", "_BATCHES"),
    ("installer.post_install", "POST_INSTALL_HOOKS"),
    ("installer.postinstall", "POSTINSTALL_HOOKS"),
)

# What composition lives in installer/compose.py (plan 25-05): setup.py may import these back
# but must not define them.
_COMPOSITION_NAMES: tuple[str, ...] = (
    "_REGISTRY",
    "_DEFAULT_BIN_DIR",
    "_MYSHELLRC",
    "_SHELLRC",
    "_ZSHRC",
    "_RC_PATHS",
    "_SHELL",
    "Install",
    "_WARN_CONSOLE",
    "_DAEMON_PLIST_PATH",
    "_LINUX_DAEMON_UNIT_DIR",
    "_ENVIRONMENT_D_DIR",
    "_build_app",
    "_execute_inputs",
    "_timer_state_cache",
    "_CompetitorProbe",
    "_competitor_probe",
    "_DiskProbe",
    "_disk_pressure_probe",
    "_cache_redirect_policies",
    "_sync_terminals",
    "_sync_terminals_and_report",
    "_build_services",
    "_split_sourced_from",
    "_desktop_shell_policies",
    "_launch_repairs",
    "_schedule_context",
    "_invalidating",
    "_schedule_removed_lines",
    "_reconcile_headless",
)


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


def _entry_points(root: Path) -> list[Path]:
    found = {path for path in _installer_modules(root).values() if _has_main_guard(path)}
    main = root / "installer" / "__main__.py"
    if main.is_file():
        found.add(main)
    return [root / "setup.py", *sorted(found)]


def _entry_modules(root: Path) -> set[str]:
    entry = set(_entry_points(root))
    return {name for name, path in _installer_modules(root).items() if path in entry}


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
    found: set[str] = set()
    for name in ("Makefile", "install.sh"):
        found.update(_PYTHON_M.findall((root / name).read_text(encoding="utf-8")))
    return found


def _installer_owner(fn: Callable[..., object]) -> str | None:
    module = getattr(fn, "__module__", None)
    if isinstance(module, str) and (module == "installer" or module.startswith("installer.")):
        return module
    return None


def _callables(value: object) -> list[Callable[..., object]]:
    if inspect.isfunction(value):
        return [value]
    if isinstance(value, functools.partial):
        return [cast(functools.partial[object], value).func]
    if isinstance(value, tuple):
        return [fn for member in cast(tuple[object, ...], value) for fn in _callables(member)]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [
            fn
            for field in dataclasses.fields(value)
            for fn in _callables(getattr(value, field.name))
        ]
    return []


def _is_callable_table(value: object) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    table = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in table):
        return False
    return any(
        _installer_owner(fn) is not None for member in table.values() for fn in _callables(member)
    )


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


def test_makefile_and_install_sh_name_only_discovered_entry_points() -> None:
    named = _python_m_modules(_ROOT)
    assert named, "the Makefile names no installer entry module"
    assert named <= _entry_modules(_ROOT)
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


def test_dispatch_table_targets_live_in_reachable_modules() -> None:
    reachable = _reachable_modules(_ROOT)
    for module_name, attribute in _DISPATCH_TABLES:
        module_vars = vars(importlib.import_module(module_name))
        assert attribute in module_vars, f"{module_name}.{attribute} is gone; drop it from the list"
        table: object = module_vars[attribute]
        assert isinstance(table, dict), f"{module_name}.{attribute} is not a dict"
        owners = {
            owner
            for member in cast(dict[object, object], table).values()
            for fn in _callables(member)
            if (owner := _installer_owner(fn)) is not None
        }
        assert owners, f"{module_name}.{attribute} has no installer callable target"
        assert owners <= reachable, (
            f"{module_name}.{attribute} targets {sorted(owners - reachable)}"
        )


def test_every_string_keyed_callable_table_is_listed() -> None:
    modules = _installer_modules(_ROOT)
    found: set[tuple[str, str]] = set()
    for name in _reachable_modules(_ROOT):
        module_vars = vars(importlib.import_module(name))
        for attribute in _top_level_assigned(_parse(modules[name])):
            if _is_callable_table(module_vars.get(attribute)):
                found.add((name, attribute))
    assert sorted(found) == sorted(_DISPATCH_TABLES)


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


def test_composition_lives_in_compose_not_setup() -> None:
    setup_tree = _parse(_ROOT / "setup.py")
    compose_tree = _parse(_ROOT / "installer" / "compose.py")
    assert sorted(set(_COMPOSITION_NAMES) & _defined_top_level(setup_tree)) == []
    assert {"_build_app", "_execute_inputs"} <= _defined_top_level(compose_tree)
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
