"""Environment policy: ban the unmanaged package installers (npm/pip/pip3).

Two removable, idempotent layers steer callers to the managed toolchain:
1. PATH shims in the managed bin dir (~/.local/bin) — tiny POSIX-sh executables
   that print the sanctioned tool and exit non-zero. They catch ANY caller that
   resolves via PATH: you, an agent, a script, a non-interactive shell.
2. Interactive-shell aliases — a faster, clearer message for interactive use,
   written as a marker-delimited block (reusing shellrc's block machinery).

Neither layer is hermetic: `python -m pip install` bypasses the pip shim, and a
real npm/pip earlier on PATH wins. guard_path_warning flags the PATH-order case.
"""

from pathlib import Path

BANNED: dict[str, str] = {
    "npm": "pnpm (pnpm add -g <pkg>)",
    "pip": "uv (uv pip install / uv add)",
    "pip3": "uv (uv pip install / uv add)",
}
EXIT_CODE = 127  # non-zero so the caller sees a hard failure
SHIM_SENTINEL = "# tools-installer-ban-shim"
BAN_BEGIN = "# >>> tools-installer ban >>>"
BAN_END = "# <<< tools-installer ban <<<"


def shim_script(name: str) -> str:
    """A 4-line POSIX-sh shim that explains the ban and exits non-zero."""
    hint = BANNED[name]
    return (
        "#!/bin/sh\n"
        f"{SHIM_SENTINEL}\n"
        f"echo \"tools-installer: '{name}' is banned on this machine — use {hint}.\" >&2\n"
        f"exit {EXIT_CODE}\n"
    )


def is_our_shim(path: Path) -> bool:
    """True only for a readable file carrying our sentinel; never a real binary."""
    try:
        return SHIM_SENTINEL in path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
