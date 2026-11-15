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
import re
from collections import deque
from collections.abc import Mapping
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
# Installed data files that run on the user's machine and are read by path, never imported.
_EXEMPT_DIRS: tuple[str, ...] = ("installer/helper_assets",)
_PYTHON_M = re.compile(r"python -m (installer(?:\.\w+)+)")


def _installer_modules(root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in sorted((root / "installer").rglob("*.py")):
        if _is_exempt(root, path):
            continue
        modules[_dotted(root, path)] = path
    return modules


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


def _runtime_imports(path: Path, modules: Mapping[str, Path]) -> set[str]:
    collector = _EdgeCollector(modules)
    collector.visit(_parse(path))
    return collector.names


class _EdgeCollector(ast.NodeVisitor):
    """Collects the known modules a file imports at runtime, skipping ``TYPE_CHECKING`` bodies."""

    def __init__(self, modules: Mapping[str, Path]) -> None:
        self._modules = modules
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
        if node.level:
            return
        module = node.module or ""
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
        for name in _runtime_imports(queue.popleft(), modules):
            reach(name)
    return reached


def _unreachable_modules(root: Path) -> list[str]:
    return sorted(set(_installer_modules(root)) - _reachable_modules(root))


def _python_m_modules(root: Path) -> set[str]:
    found: set[str] = set()
    for name in ("Makefile", "install.sh"):
        found.update(_PYTHON_M.findall((root / name).read_text(encoding="utf-8")))
    return found


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
