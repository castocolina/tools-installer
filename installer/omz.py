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

Refusal is by *final* assignment, not by "no parseable line anywhere": a
multi-line array after a single-line one is the array zsh honors, so the
single-line one above it is dead and editing it would report success while
loading nothing. That case refuses too.
"""

import os
import re
import shutil
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
# The trailer admits a trailing \r — content is split on "\n", so a CRLF .zshrc
# (a Windows-edited dotfile repo, a WSL round-trip) leaves one on every line —
# and carries it back through the rewrite, keeping the file's endings uniform.
_PLUGINS_LINE = re.compile(
    r"^(?P<indent>[ \t]*)plugins=\((?P<body>[^()\n]*)\)(?P<trailer>[ \t]*(?:#.*?)?\r?)$"
)

# Any line that OPENS a plugins array, including the multi-line form
# _PLUGINS_LINE deliberately refuses. Used to detect an assignment this module
# cannot edit but zsh still honors.
_ANY_PLUGINS_OPEN = re.compile(r"^[ \t]*plugins=\(")

_NO_ARRAY = "No single-line plugins=(...) array to edit; only the single-line form is supported"
_SHADOWED = (
    "The last plugins=(...) array in this file is the multi-line form, which would "
    "override any single-line array above it; only the single-line form is supported"
)


def _locate(lines: list[str]) -> tuple[int, re.Match[str]] | None:
    """The single-line plugins=(...) array zsh actually honors, with its match.

    Last-match-wins mirrors the documented last-begin pairing rule used for
    marker blocks, and matches zsh, where the final assignment before oh-my-zsh
    is sourced is the one that takes effect. An array this module cannot parse
    (the multi-line form) is one of those assignments, so it *invalidates* any
    single-line match above it rather than being ignored — editing a line a
    later array overwrites would report success while changing nothing zsh
    loads. Returning the match, not just the index, means callers consume a
    proven match and never re-derive one that cannot fail.
    """
    found: tuple[int, re.Match[str]] | None = None
    for i, line in enumerate(lines):
        match = _PLUGINS_LINE.match(line)
        if match is not None:
            found = (i, match)
        elif _ANY_PLUGINS_OPEN.match(line):
            found = None
    return found


def _refusal(content: str) -> str:
    """Why there is nothing editable: a shadowing multi-line array, or no array."""
    if any(_ANY_PLUGINS_OPEN.match(line) for line in content.split("\n")):
        return _SHADOWED
    return _NO_ARRAY


def _bare(token: str) -> str:
    """A plugin name with zsh's optional surrounding quotes stripped.

    `plugins=("git" docker)` is unusual but legal zsh, and `"git"` names the
    same plugin as `git`. Comparing the raw token would make the membership
    test miss it and append a redundant second `git` to the user's file.
    """
    return token.strip("\"'")


def _names_in(content: str) -> list[str] | None:
    """The plugin names in the array zsh honors, unquoted, or None if there is none."""
    found = _locate(content.split("\n"))
    if found is None:
        return None
    return [_bare(token) for token in found[1].group("body").split()]


def _rewrite(content: str, plugins: tuple[str, ...], *, enable: bool) -> str | None:
    lines = content.split("\n")
    found = _locate(lines)
    if found is None:
        return None
    index, match = found
    # Membership is tested unquoted, but every token the user already had is
    # written back verbatim — this rewrite never restyles a name it keeps.
    existing = match.group("body").split()
    if enable:
        present = {_bare(token) for token in existing}
        names = existing + [name for name in plugins if name not in present]
    else:
        skip = set(plugins)
        names = [token for token in existing if _bare(token) not in skip]
    # Internal whitespace inside the array is normalised to single spaces by this
    # rewrite; that is accepted and documented, not an oversight.
    lines[index] = f"{match.group('indent')}plugins=({' '.join(names)}){match.group('trailer')}"
    return "\n".join(lines)


def enable_plugins(content: str, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> str:
    """Add missing plugin names to the last single-line plugins=(...) array.

    Enabling and silently doing nothing would let the toggle claim success while
    nothing changed, so a missing — or shadowed — array raises rather than
    returning unchanged.
    """
    rewritten = _rewrite(content, plugins, enable=True)
    if rewritten is None:
        raise OmzPluginsError(_refusal(content))
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


def _replace_content(zshrc_path: Path, updated: str) -> None:
    """Replace an existing zshrc_path's content atomically.

    .zshrc is the one file this module edits that the installer does not own,
    and it keeps no backup, so a crash, a full disk, or a SIGKILL mid-write must
    never be able to leave the user with a truncated shell startup file. Write a
    sibling temp file (same directory, so the rename cannot cross a filesystem),
    carry the original's mode over, then os.replace — which is atomic on POSIX.
    """
    tmp = zshrc_path.with_name(f"{zshrc_path.name}.tools-installer.tmp")
    try:
        tmp.write_text(updated)
        shutil.copymode(zshrc_path, tmp)
        os.replace(tmp, zshrc_path)
    except OSError:
        # The original is still intact; drop the partial temp rather than
        # leaving a half-written file beside the user's .zshrc.
        tmp.unlink(missing_ok=True)
        raise


def write_plugins(zshrc_path: Path, plugins: tuple[str, ...] = MANAGED_PLUGINS) -> tuple[str, ...]:
    """Enable managed plugins in zshrc_path. Returns the names actually added."""
    if not zshrc_path.exists():
        raise OmzPluginsError(_NO_ARRAY)
    original = zshrc_path.read_text()
    current = _names_in(original) or []
    added = tuple(name for name in plugins if name not in current)
    updated = enable_plugins(original, plugins)
    if updated != original:
        _replace_content(zshrc_path, updated)
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
        _replace_content(zshrc_path, updated)
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
