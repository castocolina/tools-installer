"""Redirect a tool's cache directory off the OS temp dir (D-04).

One declaration per known tool drives two deliberately different writers: a
systemd ``environment.d`` conf on Linux and an exported marker block in
``~/.myshellrc`` on macOS. The registry is this module, not a field on every
``Tool`` row, because exactly one real case exists today.

"Applied" is read from the file this project owns. A freshly written
environment.d file is not live until the next login, when the systemd user
manager's environment generator runs, so the process environment is never
consulted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from installer.atomic import atomic_write_bytes
from installer.shellrc import apply_block, strip_block

# Carried by every file and block this module writes. linux_applied and
# remove_linux_redirect share one ownership check against it, so a policy can
# never read active for an artifact its own remover would refuse to delete.
OWNERSHIP_SENTINEL = "# tools-installer: cache-redirect"

# Distinct from every marker pair in installer/shellrc.py.
RC_BEGIN = "# >>> tools-installer cache-redirect >>>"
RC_END = "# <<< tools-installer cache-redirect <<<"

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REJECTED_TARGET_CHARS = ('"', "\\", "`", "$", "\n", "\r")


@dataclass(frozen=True)
class CacheRedirect:
    """One tool's cache redirect. ``target_parts`` are joined under home."""

    id: str
    label: str
    variable: str
    target_parts: tuple[str, ...]
    reason: str
    coverage_caveat: str
    conf_basename: str


# Path recorded by the source todo
# (.planning/todos/pending/2026-09-10-unify-tmp-prune-tooling-into-an-installable-tweaks-module.md):
# the host's existing 51-bun-cache-redirect.conf points Bun here, and that is
# the configuration confirmed working. Do not retarget it.
BUN_CACHE_REDIRECT = CacheRedirect(
    id="bun",
    label="Bun transpiler cache",
    variable="BUN_RUNTIME_TRANSPILER_CACHE_PATH",
    target_parts=(".cache", "bun", "transpiler-cache"),
    reason=(
        "Keep Bun's runtime transpiler cache on a disk-backed directory instead "
        "of the OS temp dir, so a killed process does not orphan native artifacts there."
    ),
    coverage_caveat=(
        "This redirect only reaches Bun invocations that inherit the environment "
        "variable; the background cleanup daemon remains the fallback for the ones "
        "that do not."
    ),
    # environment.d is last-file-wins in lexicographic order. A tools-installer
    # component keeps the name self-identifying and sorts it after a plain
    # hand-installed 51-bun-cache-redirect.conf, so this project takes authority
    # without deleting anyone else's file.
    conf_basename="51-tools-installer-bun-cache-redirect.conf",
)

REDIRECTS: tuple[CacheRedirect, ...] = (BUN_CACHE_REDIRECT,)


def environment_d_dir(home: Path, environ: Mapping[str, str]) -> Path:
    """``$XDG_CONFIG_HOME/environment.d``, or ``home/.config/environment.d``.

    A relative ``XDG_CONFIG_HOME`` is ignored, matching
    ``systemd_daemon.user_unit_dir`` and the XDG spec.
    """
    raw = environ.get("XDG_CONFIG_HOME", "")
    base = Path(raw) if raw and Path(raw).is_absolute() else home / ".config"
    return base / "environment.d"


def _valid_name(name: str) -> None:
    """Allowlist: a legal shell/systemd identifier, not merely a safe-looking one."""
    if not _NAME_RE.fullmatch(name):
        raise ValueError(f"{name!r} is not a legal environment variable name")


def target_path(redirect: CacheRedirect, home: Path) -> Path:
    """The absolute cache directory, rejecting anything unsafe to render."""
    _valid_name(redirect.variable)
    target = home.joinpath(*redirect.target_parts)
    if not target.is_absolute():
        raise ValueError(f"cache redirect target must be absolute, got {target}")
    rendered = str(target)
    if any(char in rendered for char in _REJECTED_TARGET_CHARS):
        raise ValueError(
            f"cache redirect target contains a character that cannot be rendered: {target}"
        )
    return target


def _owned(text: str) -> bool:
    return OWNERSHIP_SENTINEL in text


def _assigns(text: str, redirect: CacheRedirect, target: Path) -> bool:
    expected = f"{redirect.variable}={target}"
    return any(line.strip() == expected for line in text.splitlines())


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def render_conf(redirect: CacheRedirect, home: Path) -> str:
    """systemd environment.d text: comments plus one bare ``KEY=VALUE`` line.

    The bare assignment is required. systemd's environment.d grammar has no
    ``export`` keyword and would reject one; do not unify this with render_block.
    """
    target = target_path(redirect, home)
    return (
        f"{OWNERSHIP_SENTINEL}\n"
        f"# {redirect.reason}\n"
        "# Takes effect at the next login, when the systemd user manager reads environment.d.\n"
        f"{redirect.variable}={target}\n"
    )


def write_linux_redirect(redirect: CacheRedirect, home: Path, conf_dir: Path) -> Path:
    """Write the conf atomically at 0o644 and create the target cache directory.

    A same-named file lacking the ownership sentinel is left untouched: this
    project does not overwrite a file its own remover would refuse to delete.
    """
    text = render_conf(redirect, home)
    conf_dir.mkdir(parents=True, exist_ok=True)
    path = conf_dir / redirect.conf_basename
    # WR-06: "exists but unreadable" (mode 000, non-UTF-8 bytes, a dangling
    # symlink) is not "absent". Ownership that cannot be proven is refused,
    # never assumed; the rename below would need only directory write access.
    if path.exists() or path.is_symlink():
        existing = _read(path)
        if existing is None or not _owned(existing):
            raise OSError(f"{path} exists and is not managed by tools-installer")
    atomic_write_bytes(path, text.encode("utf-8"), mode=0o644)
    target_path(redirect, home).mkdir(parents=True, exist_ok=True)
    return path


def remove_linux_redirect(redirect: CacheRedirect, conf_dir: Path) -> bool:
    """Delete the owned conf file. Never touches the target cache directory.

    Returns False, deleting nothing, when the file is absent or lacks the
    ownership sentinel.
    """
    path = conf_dir / redirect.conf_basename
    existing = _read(path)
    if existing is None or not _owned(existing):
        return False
    path.unlink()
    return True


def linux_applied(redirect: CacheRedirect, home: Path, conf_dir: Path) -> bool:
    """True only for an owned conf file that assigns the expected variable.

    Shares ``_owned`` with ``remove_linux_redirect``. Ignores the process
    environment: the file is the authority, not the current session.
    """
    existing = _read(conf_dir / redirect.conf_basename)
    if existing is None or not _owned(existing):
        return False
    try:
        expected = target_path(redirect, home)
    except ValueError:
        return False
    return _assigns(existing, redirect, expected)


def render_block(redirect: CacheRedirect, home: Path) -> str:
    """A marker block whose assignment is ``export KEY="VALUE"``.

    The export is load-bearing: ``~/.myshellrc`` is sourced by an interactive
    shell, and a bare assignment is not inherited by Bun's child process. This
    is shell grammar; render_conf's bare assignment is systemd grammar. The two
    must not be unified.
    """
    target = target_path(redirect, home)
    return "\n".join(
        (
            RC_BEGIN,
            OWNERSHIP_SENTINEL,
            f"# {redirect.reason}",
            f'export {redirect.variable}="{target}"',
            RC_END,
        )
    )


def write_rc_redirect(redirect: CacheRedirect, home: Path, rc_path: Path) -> None:
    """Insert the marker block through apply_block, preserving the rc file's mode."""
    block = render_block(redirect, home)
    existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    updated = apply_block(existing, block, begin=RC_BEGIN, end=RC_END)
    atomic_write_bytes(rc_path, updated.encode("utf-8"))


def remove_rc_redirect(redirect: CacheRedirect, rc_path: Path) -> None:
    """Strip only this module's block. A shared source line is not this block."""
    if not rc_path.exists():
        return
    existing = rc_path.read_text(encoding="utf-8")
    updated = strip_block(existing, RC_BEGIN, RC_END)
    if updated != existing:
        atomic_write_bytes(rc_path, updated.encode("utf-8"))


def rc_applied(redirect: CacheRedirect, home: Path, rc_path: Path) -> bool:
    """True only when a closed begin..end block contains the exported assignment."""
    existing = _read(rc_path)
    if existing is None or RC_BEGIN not in existing.splitlines():
        return False
    lines = existing.splitlines()
    start = max(index for index, line in enumerate(lines) if line == RC_BEGIN)
    for stop in range(start + 1, len(lines)):
        if lines[stop] == RC_END:
            try:
                expected = target_path(redirect, home)
            except ValueError:
                return False
            assignment = f'export {redirect.variable}="{expected}"'
            return assignment in lines[start + 1 : stop]
    return False


# The system-wide environment.d directories systemd's user environment
# generator merges after the user's own, highest priority first (see
# environment.d(5)). Read, never written: this project has no privilege to
# touch them.
SYSTEM_ENVIRONMENT_D_DIRS: tuple[Path, ...] = (
    Path("/etc/environment.d"),
    Path("/run/environment.d"),
    Path("/usr/local/lib/environment.d"),
    Path("/usr/lib/environment.d"),
)


def _assigns_variable(text: str, variable: str) -> bool:
    pattern = re.compile(rf"^\s*{re.escape(variable)}\s*=")
    return any(pattern.match(line) for line in text.splitlines())


def competing_conf_paths(
    redirect: CacheRedirect,
    home: Path,
    conf_dir: Path,
    system_dirs: tuple[Path, ...] = (),
) -> tuple[Path, ...]:
    """Other ``.conf`` files that assign the same variable, sorted by basename.

    Scans ``conf_dir`` then each of ``system_dirs`` (read-only) in systemd's
    priority order. A basename seen in an earlier directory masks the same
    basename later on, exactly as systemd merges them, so a masked file is
    not reported -- including a system file sharing this redirect's own name.
    An indented assignment counts: systemd strips the leading whitespace.
    """
    seen = {redirect.conf_basename}
    found: list[Path] = []
    for directory in (conf_dir, *system_dirs):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.conf")):
            if path.name in seen:
                continue
            seen.add(path.name)
            text = _read(path)
            if text is not None and _assigns_variable(text, redirect.variable):
                found.append(path)
    return tuple(sorted(found, key=lambda path: path.name))
