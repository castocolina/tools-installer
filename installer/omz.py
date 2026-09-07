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

Ownership is recorded, never inferred from content. `git` ships in Oh-My-Zsh's
own default .zshrc and `docker` is its most common addition, so "both names are
in the array" cannot distinguish a machine this installer edited from one the
user wrote by hand — and removing on that guess destroys configuration the
installer never created. Enabling therefore records the names it actually
added, in a marker block inside the ~/.myshellrc this installer owns (the one
place a marker may go; .zshrc never gets one), and disabling removes exactly
those. A machine with no record is a machine this module will not touch.

The record is the only thing that can distinguish the two machines, so it is
written and cleared transactionally around the .zshrc edit — reserved before an
enable and rolled back if that edit is refused, cleared only after a disable's
edit has actually landed — and both files are written atomically. Either order
of a non-transactional pair strands state: a record written after the edit can
abandon names this installer added, and a record cleared before the edit makes a
refused write permanent, since the retry the caller advertises would find
nothing left to act on.
"""

import os  # noqa: F401  # pyright: ignore[reportUnusedImport]
import re
from collections.abc import Mapping
from pathlib import Path

from installer.atomic import atomic_write_text
from installer.shellrc import apply_block, strip_block

# `import os` is the monkeypatch surface tests/test_omz.py uses (`omz.os.replace`).
# It is the same stdlib module installer.atomic imports, so those patches still
# intercept the write after this body became a delegation.

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

# The ownership record. It lives in ~/.myshellrc — a file this installer
# created — because .zshrc must never carry a tools-installer marker. The body
# is comments only, so the block is inert wherever the rc file is sourced.
_OWNED_BEGIN = "# >>> tools-installer omz-plugins >>>"
_OWNED_END = "# <<< tools-installer omz-plugins <<<"
_ADDED_PREFIX = "# added:"

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


def plugins_in(content: str) -> tuple[str, ...]:
    """The plugin names in the array zsh honors, unquoted; () when there is none.

    Content, not ownership — this reports what the array holds and says nothing
    about who put it there. `plugins_owned` answers that, and it is the
    predicate every removal path reads.
    """
    found = _locate(content.split("\n"))
    if found is None:
        return ()
    return tuple(_bare(token) for token in found[1].group("body").split())


def _atomic_write(path: Path, updated: str) -> None:
    """Replace path's content atomically, creating it when it does not exist yet.

    Both files this module writes need this. .zshrc is the one it edits that the
    installer does not own, and it keeps no backup, so a crash, a full disk, or a
    SIGKILL mid-write must never be able to leave the user with a truncated shell
    startup file. The ownership record is worse: it is the only thing that can
    tell a name this installer added from one the user wrote, and a half-written
    record is unrecoverable by design — `strip_block` refuses an orphan begin
    marker, so a truncated record would wedge the policy permanently ON with no
    way to clear it.

    Implementation lives in installer.atomic.atomic_write_text: a unique sibling
    temp, then os.replace. When path is itself a symlink (a dotfile-manager
    setup that symlinks ~/.zshrc to a repo elsewhere is common), that helper
    resolves through the link so the rename never replaces the symlink with a
    regular file.
    """
    atomic_write_text(path, updated)


def _owned_block(added: tuple[str, ...]) -> str:
    return "\n".join(
        (
            _OWNED_BEGIN,
            "# Oh-My-Zsh plugin names this installer added to .zshrc's plugins=(...)",
            "# array. Disabling removes exactly these and nothing else. Comments only:",
            "# nothing here is executed.",
            f"{_ADDED_PREFIX} {' '.join(added)}".rstrip(),
            _OWNED_END,
        )
    )


def _record(state_path: Path) -> tuple[str, ...] | None:
    """The recorded names, or None when this installer holds no record at all.

    None and () are different answers: () means "we enabled the policy and the
    array already had every name", which is still ours to switch off, while
    None means "we never touched this machine".

    Only a CLOSED begin..end block counts. An orphan begin marker — which a
    truncated write could once leave behind — must read as "no record": treating
    it as "owns nothing" would report the policy ON while `_clear_owned`'s
    `strip_block` deliberately refuses to strip an unpaired marker, leaving no
    way to ever switch it off. Last closed block wins, mirroring the same
    last-begin pairing rule apply_block/strip_block use.
    """
    if not state_path.exists():
        return None
    record: tuple[str, ...] | None = None
    names: tuple[str, ...] = ()
    inside = False
    for line in state_path.read_text().split("\n"):
        if line == _OWNED_BEGIN:
            inside, names = True, ()
        elif line == _OWNED_END and inside:
            inside, record = False, names
        elif inside and line.startswith(_ADDED_PREFIX):
            names = tuple(line[len(_ADDED_PREFIX) :].split())
    return record


def owned_plugins(state_path: Path) -> tuple[str, ...]:
    """The plugin names this installer added; () when it added none or never ran."""
    return _record(state_path) or ()


def plugins_owned(state_path: Path) -> bool:
    """True when this installer enabled the policy on this machine.

    The ownership predicate, deliberately not a content check: `git` ships in
    Oh-My-Zsh's default .zshrc and `docker` is its commonest addition, so
    reading the array would report a hand-authored `plugins=(git docker
    kubectl)` as ours and offer to strip it.
    """
    return _record(state_path) is not None


def _record_owned(state_path: Path, added: tuple[str, ...]) -> None:
    existing = state_path.read_text() if state_path.exists() else ""
    _atomic_write(
        state_path, apply_block(existing, _owned_block(added), begin=_OWNED_BEGIN, end=_OWNED_END)
    )


def _clear_owned(state_path: Path) -> None:
    if not state_path.exists():
        return
    original = state_path.read_text()
    stripped = strip_block(original, _OWNED_BEGIN, _OWNED_END)
    if stripped != original:
        _atomic_write(state_path, stripped)


def write_plugins(
    zshrc_path: Path, state_path: Path, plugins: tuple[str, ...] = MANAGED_PLUGINS
) -> tuple[str, ...]:
    """Enable managed plugins in zshrc_path, recording what was added in state_path.

    Returns the names actually added.

    The record and the .zshrc edit are transactional, in the only order that
    fails safe: `enable_plugins` raises for a refused array before anything is
    written, then the claim is RESERVED, then the edit is committed, and a
    failed edit rolls the claim back to exactly what it was. Recording after the
    edit instead would strand names on a failed record write — the installer
    would have added `docker` to the user's array while holding no record of it,
    so `plugins_owned` reads False and `remove_plugins` can never take it back
    out. An over-broad claim is recoverable (removing a name the array does not
    contain is a no-op); an absent one is not.
    """
    if not zshrc_path.exists():
        raise OmzPluginsError(_NO_ARRAY)
    original = zshrc_path.read_text()
    current = plugins_in(original)
    added = tuple(name for name in plugins if name not in current)
    updated = enable_plugins(original, plugins)
    previous = _record(state_path)
    owned = list(previous or ())
    owned.extend(name for name in added if name not in owned)
    _record_owned(state_path, tuple(owned))
    try:
        if updated != original:
            _atomic_write(zshrc_path, updated)
    except OSError:
        # Restore the record to exactly its prior state, so a refused edit
        # leaves no claim over a file this installer did not change.
        if previous is None:
            _clear_owned(state_path)
        else:
            _record_owned(state_path, previous)
        raise
    return added


def remove_plugins(zshrc_path: Path, state_path: Path) -> tuple[str, ...]:
    """Remove exactly the plugin names this installer recorded, and drop the record.

    Provenance, not content: a user who wrote `plugins=(git docker kubectl)`
    themselves has no record, so nothing is removed and .zshrc is not opened.
    Stays total against the STATE of the machine when there is nothing of ours
    left to undo — a missing record or a missing .zshrc both resolve to
    "nothing removed" rather than raising, because the full-uninstall sweep
    calls this against machines in either state.

    It is NOT total against an array this module cannot parse. `disable_plugins`
    is total on its own (it must be, since the sweep also calls it in contexts
    with no record at all), but returning content unchanged there is
    indistinguishable from "found the array, nothing in it matched" — and a
    record we hold means real names of ours may still be on disk. Clearing the
    record on that unverified "unchanged" would report success while a later
    multi-line array (oh-my-zsh's own idiom) shadows the single-line one this
    module edited, leaving `git`/`docker` in the file with no record and no way
    back. So this calls `_rewrite` directly and raises when it cannot locate an
    editable array, the same OmzPluginsError `sweep_tweaks` already catches and
    reports as a failed policy for a refused WRITE.

    The record is therefore cleared LAST, and only once the file it describes
    has actually changed (or is verifiably clean of every name it claims). A
    refused write or an unlocatable array leaves the record in place: the tool
    tells the user to fix the problem and re-run, and the re-run finds the same
    record and can still act on it.
    """
    owned = owned_plugins(state_path)
    if not owned or not zshrc_path.exists():
        # Nothing of ours is on disk to undo, so the claim may go unconditionally.
        _clear_owned(state_path)
        return ()
    original = zshrc_path.read_text()
    rewritten = _rewrite(original, owned, enable=False)
    if rewritten is None:
        # The array cannot be located (missing single-line form, or shadowed by
        # a later multi-line one) even though a record claims plugins were
        # added -- clearing the record here would report success while those
        # names are still on disk with no way back.
        raise OmzPluginsError(_refusal(original))
    current = plugins_in(original)
    removed = tuple(name for name in owned if name in current)
    if rewritten != original:
        _atomic_write(zshrc_path, rewritten)
    _clear_owned(state_path)
    return removed


def omz_present(home: Path, environ: Mapping[str, str]) -> bool:
    """True when ~/.oh-my-zsh or a $ZSH that names an existing directory is present."""
    if (home / ".oh-my-zsh").is_dir():
        return True
    zsh = environ.get("ZSH")
    return bool(zsh) and Path(zsh).is_dir()
