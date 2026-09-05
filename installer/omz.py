"""Enable Oh-My-Zsh's bundled plugins by editing the single-line plugins=(...) array
in the user's .zshrc in place.

This is not installer/shellrc.py's apply_block/strip_block mechanism. That machinery
owns and rewrites a whole marker-delimited block inside ~/.myshellrc — a file this
installer created. .zshrc and its plugins line belong to the user's own oh-my-zsh
install, so exactly one line is rewritten and every other byte is copied through.

Single-line array syntax is the supported form; the multi-line form is deliberately
out of scope. The matcher refuses nested parentheses inside the array, and any array
whose parentheses span a newline. The newline exclusion is how the multi-line form
is refused rather than half-parsed. Both are deliberate: zsh plugin arrays are flat
lists of bare names, so nesting has no legitimate form to support, and a rewrite that
could match across lines is the defect most likely to corrupt a real .zshrc.
"""

import re
from collections.abc import Mapping
from pathlib import Path

# The only names this installer ever writes into a user's array. They are
# Oh-My-Zsh's own bundled plugins, requiring no download. A module constant so no
# user-supplied or registry-supplied string can ever reach the file.
MANAGED_PLUGINS: tuple[str, ...] = ("git", "docker")


class OmzPluginsError(OSError):
    """The target .zshrc has no single-line plugins=(...) array to edit.

    Raised for a missing file or the multi-line form left out of scope. Subclasses
    OSError so installer/ui_common.py::run_live — which catches OSError by design —
    surfaces it on the Policies status line without any screen learning a new
    except clause.
    """


# indent and trailer are preserved verbatim on rewrite. body excludes parentheses
# and newlines, so a multi-line array fails to match rather than being half-parsed.
# The anchored [ \t]* indent means a commented-out `# plugins=(...)` never matches.
_PLUGINS_LINE = re.compile(
    r"^(?P<indent>[ \t]*)plugins=\((?P<body>[^()\n]*)\)(?P<trailer>[ \t]*(?:#.*)?)$"
)

_NO_ARRAY = "No single-line plugins=(...) array to edit; only the single-line form is supported"


def _locate(lines: list[str]) -> int | None:
    # Last-match-wins mirrors the documented last-begin pairing rule used for
    # marker blocks, and matches zsh, where the final assignment before oh-my-zsh
    # is sourced is the one that takes effect.
    index: int | None = None
    for i, line in enumerate(lines):
        if _PLUGINS_LINE.match(line):
            index = i
    return index


def _names_in(content: str) -> list[str] | None:
    lines = content.split("\n")
    index = _locate(lines)
    if index is None:
        return None
    match = _PLUGINS_LINE.match(lines[index])
    if match is None:
        return None
    return match.group("body").split()


def _rewrite(content: str, plugins: tuple[str, ...], *, enable: bool) -> str | None:
    lines = content.split("\n")
    index = _locate(lines)
    if index is None:
        return None
    match = _PLUGINS_LINE.match(lines[index])
    if match is None:
        return None
    existing = match.group("body").split()
    if enable:
        names = existing + [name for name in plugins if name not in existing]
    else:
        skip = set(plugins)
        names = [name for name in existing if name not in skip]
    # Internal whitespace inside the array is normalised to single spaces by this
    # rewrite; that is accepted and documented, not an oversight.
    lines[index] = f"{match.group('indent')}plugins=({' '.join(names)}){match.group('trailer')}"
    return "\n".join(lines)


def enable_plugins(content: str, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> str:
    """Add missing plugin names to the last single-line plugins=(...) array.

    Enabling and silently doing nothing would let the toggle claim success while
    nothing changed, so a missing array raises rather than returning unchanged.
    """
    rewritten = _rewrite(content, plugins, enable=True)
    if rewritten is None:
        raise OmzPluginsError(_NO_ARRAY)
    return rewritten


def disable_plugins(content: str, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> str:
    """Remove managed plugin names from the last single-line plugins=(...) array.

    Disabling and doing nothing is already the correct end state, so a missing
    array returns content unchanged. Disable must stay total because the
    full-uninstall sweep calls it against machines that may have no .zshrc at all.
    """
    rewritten = _rewrite(content, plugins, enable=False)
    return content if rewritten is None else rewritten


def plugins_enabled(content: str, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> bool:
    """True when a matching array exists and contains every requested name."""
    names = _names_in(content)
    if names is None:
        return False
    present = set(names)
    return all(plugin in present for plugin in plugins)


def write_plugins(zshrc_path: Path, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> tuple[str, ...]:
    """Enable managed plugins in zshrc_path. Returns the names actually added."""
    if not zshrc_path.exists():
        raise OmzPluginsError(_NO_ARRAY)
    original = zshrc_path.read_text()
    current = _names_in(original) or []
    added = tuple(name for name in plugins if name not in current)
    updated = enable_plugins(original, plugins)
    if updated != original:
        zshrc_path.write_text(updated)
    return added


def remove_plugins(zshrc_path: Path, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> tuple[str, ...]:
    """Disable managed plugins in zshrc_path. A missing file is a no-op."""
    if not zshrc_path.exists():
        return ()
    original = zshrc_path.read_text()
    current = _names_in(original) or []
    removed = tuple(name for name in plugins if name in current)
    updated = disable_plugins(original, plugins)
    if updated != original:
        zshrc_path.write_text(updated)
    return removed


def plugins_present(zshrc_path: Path, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> bool:
    """True when zshrc_path exists and its array contains every requested name."""
    if not zshrc_path.exists():
        return False
    return plugins_enabled(zshrc_path.read_text(), plugins)


def omz_present(home: Path, environ: Mapping[str, str]) -> bool:
    """True when ~/.oh-my-zsh or a $ZSH that names an existing directory is present."""
    if (home / ".oh-my-zsh").is_dir():
        return True
    zsh = environ.get("ZSH")
    return bool(zsh) and Path(zsh).is_dir()
