"""Environment policy: PATH shims and aliases for banned and redirected commands.

Two removable, idempotent layers steer callers to the managed toolchain:
1. PATH shims in the managed bin dir (~/.local/bin) — tiny POSIX-sh executables.
   Hard-block shims print the sanctioned tool and exit non-zero. Redirect shims
   exec into the managed equivalent, preserving the real exit code and streams.
   They catch ANY caller that resolves via PATH: you, an agent, a script, a
   non-interactive shell.
2. Interactive-shell aliases — a faster path for interactive use, written as a
   marker-delimited block (reusing shellrc's block machinery). A redirect alias
   performs the redirect; a ban alias prints a message and fails.

Neither layer is hermetic: `python -m pip install` bypasses the pip shim, and a
real npm/pip earlier on PATH wins. guard_path_warning flags the PATH-order case.

pip and pip3 stay hard-blocked because `uv pip` is not an argv-compatible drop-in
for two of the six subcommands this shim would intercept — `uninstall` cascades
to transitive dependencies pip leaves in place, and `compile` requires an
explicit output file and applies a different extras-stripping default — so a
blanket redirect would change behaviour silently. See
https://docs.astral.sh/uv/pip/compatibility/ and
.planning/phases/04-package-manager-redirect-policy/04-RESEARCH.md Pitfall 1.
"""

import os
import shlex
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from installer.shellrc import apply_block, strip_block

BANNED: dict[str, str] = {
    "npm": "pnpm (pnpm add -g <pkg>)",
    "pip": "uv (uv pip install / uv add)",
    "pip3": "uv (uv pip install / uv add)",
    "npx": "pnpm (pnpm dlx <pkg>)",
}


@dataclass(frozen=True)
class Redirect:
    target: str
    args: tuple[str, ...]
    label: str


REDIRECTED: dict[str, Redirect] = {
    "npx": Redirect(target="pnpm", args=("dlx",), label="redirected to pnpm dlx"),
}
EXIT_CODE = 127  # non-zero so the caller sees a hard failure
SHIM_SENTINEL = "# tools-installer-ban-shim"
REDIRECT_SENTINEL: str = "# tools-installer-redirect-shim"
BAN_BEGIN = "# >>> tools-installer ban >>>"
BAN_END = "# <<< tools-installer ban <<<"
PathLookup = Callable[[str, str], str | None]


def shim_script(name: str) -> str:
    """A 4-line POSIX-sh shim that explains the ban and exits non-zero."""
    hint = BANNED[name]
    return (
        "#!/bin/sh\n"
        f"{SHIM_SENTINEL}\n"
        f"echo \"tools-installer: '{name}' is banned on this machine — use {hint}.\" >&2\n"
        f"exit {EXIT_CODE}\n"
    )


def redirect_shim_script(name: str, target_path: str) -> str:
    """POSIX-sh shim that execs into the redirect target, preserving exit code."""
    spec = REDIRECTED[name]
    quoted_args = " ".join(shlex.quote(arg) for arg in spec.args)
    return f'#!/bin/sh\n{REDIRECT_SENTINEL}\nexec {shlex.quote(target_path)} {quoted_args} "$@"\n'


def is_our_shim(path: Path) -> bool:
    """True only for a readable file carrying our sentinel; never a real binary."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
    return SHIM_SENTINEL in text or REDIRECT_SENTINEL in text


def which_in_path(name: str, path: str) -> str | None:
    return shutil.which(name, path=path)


def real_binary(
    name: str,
    *,
    shim_dir: Path,
    path_value: str,
    lookup: PathLookup = which_in_path,
) -> str | None:
    """Resolve `name` from PATH, never the managed shim.

    Re-resolving the target through the live PATH is how a shim finds itself
    (04-RESEARCH Pitfall 3), so the search path never contains the shim dir and
    a sentinel-carrying result is refused.
    """
    search_dirs = [
        entry for entry in path_value.split(os.pathsep) if entry and entry != str(shim_dir)
    ]
    found = lookup(name, os.pathsep.join(search_dirs))
    if found is None or is_our_shim(Path(found)):
        return None
    return found


def install_redirect_shims(
    shim_dir: Path,
    *,
    path_value: str,
    lookup: PathLookup = which_in_path,
) -> dict[str, str]:
    """Write redirect shims into shim_dir (mode 0o755). Idempotent.

    Never overwrites a real binary already living there (sentinel check).
    When the redirect target is unresolvable, writes the hard-block body
    instead of a shim that execs into a missing command.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    for name, spec in REDIRECTED.items():
        target = shim_dir / name
        if target.exists() and not is_our_shim(target):
            results[name] = "skipped (real binary here)"
            continue
        had = target.exists()
        resolved = real_binary(spec.target, shim_dir=shim_dir, path_value=path_value, lookup=lookup)
        if resolved is None:
            target.write_text(shim_script(name))
            target.chmod(0o755)
            results[name] = "blocked (pnpm not found)"
            continue
        target.write_text(redirect_shim_script(name, resolved))
        target.chmod(0o755)
        results[name] = "refreshed" if had else "created"
    return results


def install_shims(shim_dir: Path) -> dict[str, str]:
    """Write npm/pip/pip3 shims into shim_dir (mode 0o755). Idempotent.

    Never overwrites a real binary already living there (sentinel check).
    Returns {name: 'created' | 'refreshed' | 'skipped (real binary here)'}.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    for name in BANNED:
        target = shim_dir / name
        if target.exists() and not is_our_shim(target):
            results[name] = "skipped (real binary here)"
            continue
        had = target.exists()
        target.write_text(shim_script(name))
        target.chmod(0o755)
        results[name] = "refreshed" if had else "created"
    return results


def guarded_names() -> tuple[str, ...]:
    """Every command name this installer shims, ban and redirect alike.

    Deduplicated because a name may appear in both dicts (its redirect body
    supersedes its hard-block body on disk).
    """
    return tuple(dict.fromkeys((*BANNED, *REDIRECTED)))


def remove_shims(shim_dir: Path) -> dict[str, str]:
    """Remove only the shims we created. Returns {name: 'removed' | 'absent'}.

    One remover covers both bodies, so a redirect can never outlive the
    policy's teardown (SC#1).
    """
    results: dict[str, str] = {}
    for name in guarded_names():
        target = shim_dir / name
        if target.exists() and is_our_shim(target):
            target.unlink()
            results[name] = "removed"
        else:
            results[name] = "absent"
    return results


def guard_status(shim_dir: Path) -> dict[str, bool]:
    """{name: our shim is installed}."""
    return {name: is_our_shim(shim_dir / name) for name in guarded_names()}


def guard_label(name: str) -> str:
    """Per-command doctor text: redirect label, or 'blocked'."""
    if name in REDIRECTED:
        return REDIRECTED[name].label
    return "blocked"


def ban_alias_block() -> str:
    """Marker-delimited alias block (no trailing newline, like shellrc blocks).

    An interactive redirect alias must perform the redirect, not warn about it —
    a redirect is meant to be transparent. The alias names the target by PATH
    name while the installed shim bakes the real_binary-resolved absolute path,
    so in an interactive shell the alias resolves the target through the user's
    own PATH. That is intended — an alias must keep working after the target
    moves — and it stays harmless after plan 04-03 wraps pnpm, because dlx is
    not one of GLOBAL_SUBCOMMANDS and therefore never reaches the volta branch.
    """
    lines = [BAN_BEGIN]
    for name, hint in BANNED.items():
        if name in REDIRECTED:
            spec = REDIRECTED[name]
            tokens = " ".join((spec.target, *spec.args))
            lines.append(f"alias {name}='{tokens}'")
            continue
        lines.append(
            f"""alias {name}='echo "tools-installer: {name} is banned — use {hint}." >&2; false'"""
        )
    lines.append(BAN_END)
    return "\n".join(lines)


def write_ban_aliases(rc_path: Path) -> None:
    """Idempotently write the alias block into rc_path, preserving the rest."""
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, ban_alias_block(), begin=BAN_BEGIN, end=BAN_END))


def remove_ban_aliases(rc_path: Path) -> None:
    """Strip the alias block from rc_path. A missing file or absent block is a no-op."""
    if not rc_path.exists():
        return
    original = rc_path.read_text()
    stripped = strip_block(original, BAN_BEGIN, BAN_END)
    if stripped != original:
        rc_path.write_text(stripped)


def guard_path_warning(
    shim_dir: Path,
    path_value: str,
    which: Callable[[str], str | None],
) -> str | None:
    """Warn when the shims can't take effect: shim_dir missing from PATH, or a
    real npm/pip/pip3 resolving before it. Returns None when the order is sound.

    `which` is injected (shutil.which in production) so the check is testable.
    """
    target = str(shim_dir)
    path_dirs = path_value.split(os.pathsep)
    if target not in path_dirs:
        return (
            f"{target} is not on PATH — add it (early) so the ban applies to "
            "non-interactive callers."
        )
    shim_index = path_dirs.index(target)
    for name in guarded_names():
        real = which(name)
        if real and not is_our_shim(Path(real)):
            real_dir = str(Path(real).parent)
            if real_dir in path_dirs and path_dirs.index(real_dir) < shim_index:
                return (
                    f"A real '{name}' at {real} resolves before {target}; "
                    f"put {target} earlier on PATH."
                )
    return None


def guard_redirect_warning(shim_dir: Path) -> str | None:
    """Warn when a redirect name is installed as a hard block because its target
    was unresolvable at apply time. Returns None when every redirect on disk is
    live.
    """
    messages: list[str] = []
    for name, spec in REDIRECTED.items():
        path = shim_dir / name
        if not is_our_shim(path):
            continue
        if REDIRECT_SENTINEL in path.read_text():
            continue
        messages.append(
            f"'{name}' is hard-blocked because '{spec.target}' was not "
            "resolvable when the policy was applied; install "
            f"{spec.target} and re-apply."
        )
    return " ".join(messages) if messages else None
