"""bun's global directories, computed from the environment, and the bun resolver.

This never calls bun's CLI: `bun pm bin -g` errors on a fresh host, before the first global
install, which is exactly when the answer is needed. Importers: engine, executors, status,
shellrc and version_status; this module imports only `installer.model` so none can cycle.
"""

import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from installer.model import Method


def _env_dir(name: str) -> Path | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    # bun resolves a relative value against its cwd, which is this process's.
    return Path(raw).expanduser().absolute()


def bun_dirs(home: Path | None = None) -> tuple[Path, Path]:
    """bun's `(global bin dir, global install dir)` for the current environment.

    `home` replaces `Path.home()` for the default tree only, so a caller with an injected
    home (shellrc.collect_bin_dirs) stays inside it.
    """
    # shortcut: bunfig global dirs are not read, upgrade when users relocate bun via bunfig
    root = _env_dir("BUN_INSTALL")
    default = (home or Path.home()) / ".bun" if root is None else root
    return (
        _env_dir("BUN_INSTALL_BIN") or default / "bin",
        _env_dir("BUN_INSTALL_GLOBAL_DIR") or default / "install" / "global",
    )


def resolve_bun() -> str | None:
    """An absolute path to bun (PATH first, then bun's bin dir), or None."""
    absolute = os.pathsep.join(
        entry for entry in os.environ.get("PATH", "").split(os.pathsep) if os.path.isabs(entry)
    )
    found = shutil.which("bun", path=absolute)
    if found is not None:
        return found
    candidate = bun_dirs()[0] / "bun"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def _load_manifest() -> Mapping[str, object] | None:
    """bun's global `package.json` as an object, `{}` when there is none, else None.

    Read-only, and never raises: a missing file or tree reads as no manifest, while any other
    `OSError`, invalid UTF-8, invalid JSON and a non-object document read as unknown (None).
    """
    try:
        document: object = json.loads((bun_dirs()[1] / "package.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return None
    return cast(dict[str, object], document) if isinstance(document, dict) else None


def trusted_dependencies() -> list[str] | None:
    """The user's `trustedDependencies` list in bun's global manifest, or None when it has none.

    None covers an absent key, a value that is not a list of strings, and an unreadable manifest.
    The installer only reads this: bun's lifecycle-script trust is the user's to widen.
    """
    raw = (_load_manifest() or {}).get("trustedDependencies")
    if not isinstance(raw, list):
        return None
    items = cast(list[object], raw)
    names = [item for item in items if isinstance(item, str)]
    return names if len(names) == len(items) else None


def method_bin_dir(method: Method) -> Path | None:
    """The directory a method's command lands in: a declared `bin_dir`, else bun's for bun."""
    declared = method.params.get("bin_dir")
    if isinstance(declared, str) and declared:
        return Path(declared).expanduser()
    if method.kind == "bun":
        return bun_dirs()[0]
    return None
