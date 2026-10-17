"""Safely synchronize the discovered zsh into Linux terminal configurations.

This module configures only marker-delimited regions in terminal-emulator files.
It never invokes a shell or changes an account login shell.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from installer.atomic import atomic_write_text, read_capped
from installer.locations import zshrc_path
from installer.omz import ensure_zshrc_template, omz_root
from installer.platform import Platform

Lookup = Callable[[str], str | None]


class TerminalShellError(OSError):
    """Terminal configuration cannot be changed without risking user data."""


_SYNC_FAILURE_PREFIX = "Terminal shell synchronization failed"


def terminal_sync_warning(sync: Callable[[], str | None] | None) -> str | None:
    """Run a terminal-synchronizer closure and reduce it to one optional warning.

    WR-03: the synchronizer itself is shared by all six lifecycle routes, but
    its failure handling used to be five independently hand-written try/except
    blocks that had already drifted on both axes a shared contract exists to
    pin -- one caught OSError + CommandError where the others caught OSError,
    and one spelled the message with a lower-case "terminal". This is that
    contract, in the one place a defect in it can be fixed once: a terminal
    synchronization is always a SECONDARY effect of an already-completed
    primary operation, so it never raises out of here and never flips that
    operation into a reported failure -- it yields a warning string or nothing.

    The catch is deliberately broad, matching the `except Exception` this
    codebase already uses for post-mutation side effects (update.py's pnpm
    replay and cache invalidation, wizard_app's uninstall invalidate). A narrow
    `except OSError` is exactly what let CR-02's UnicodeDecodeError -- a
    ValueError -- escape into a Textual screen-result callback and into
    main()'s exit path, and enumerating exception types at a seam whose whole
    purpose is "must never take the caller down" is the wrong shape of guard.
    """
    if sync is None:
        return None
    try:
        return sync()
    except Exception as exc:  # noqa: BLE001 -- secondary effect, never downgrades the primary op
        return f"{_SYNC_FAILURE_PREFIX}: {exc}"


@dataclass(frozen=True)
class TerminalShellResult:
    """Terminal synchronization outcomes, split by the action taken.

    `drifted` names the terminals whose owned region differed from what
    synchronization writes (a write run then fixes it); the refresh pass reads
    it from a dry run for `≈` (D-16).
    """

    configured: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    reverted: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    drifted: tuple[str, ...] = ()


def _marker(terminal: str, edge: str, *, comment: str = "#") -> str:
    return f"{comment} {edge} tools-installer terminal-shell {terminal} {edge}"


def _replace_owned_region(
    content: str, terminal: str, body: str | None, *, comment: str = "#"
) -> str:
    """Replace exactly one complete owned region, rejecting malformed markers."""
    begin = _marker(terminal, ">>>", comment=comment)
    end = _marker(terminal, "<<<", comment=comment)
    lines = content.splitlines(keepends=True)
    start: int | None = None
    complete: tuple[int, int] | None = None

    for index, line in enumerate(lines):
        marker = line.rstrip("\r\n")
        if marker == begin:
            if start is not None or complete is not None:
                raise TerminalShellError(f"malformed {terminal} ownership region")
            start = index
        elif marker == end:
            if start is None:
                raise TerminalShellError(f"malformed {terminal} ownership region")
            complete = (start, index)
            start = None

    if start is not None:
        raise TerminalShellError(f"malformed {terminal} ownership region")

    if body is None:
        if complete is None:
            return content
        start_index, end_index = complete
        return "".join((*lines[:start_index], *lines[end_index + 1 :]))

    region = f"{begin}\n{body}\n{end}\n"
    if complete is None:
        prefix = content if not content or content.endswith(("\n", "\r")) else f"{content}\n"
        return f"{prefix}{region}"
    start_index, end_index = complete
    return "".join((*lines[:start_index], region, *lines[end_index + 1 :]))


def _safe_executable(path: str | None) -> str | None:
    if path is None:
        return None
    if not path or not Path(path).is_absolute():
        raise TerminalShellError("discovered executable path must be absolute")
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        raise TerminalShellError("discovered executable path contains a control character")
    return path


def _xdg_config_home(home: Path, environ: Mapping[str, str]) -> Path:
    configured = environ.get("XDG_CONFIG_HOME")
    return Path(configured) if configured else home / ".config"


def _kitty_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    return _xdg_config_home(home, environ) / "kitty" / "kitty.conf"


def _xdg_data_home(home: Path, environ: Mapping[str, str]) -> Path:
    configured = environ.get("XDG_DATA_HOME")
    return Path(configured) if configured else home / ".local" / "share"


def _wezterm_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    config_home = _xdg_config_home(home, environ)
    configured = config_home / "wezterm" / "wezterm.lua"
    fallback = home / ".wezterm.lua"
    if configured.exists() or not fallback.exists():
        return configured
    return fallback


def _lua_string(value: str) -> str:
    """Encode a validated string for the narrow Lua string shape we emit."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _wezterm_content(existing: str, zsh_path: str) -> str | None:
    """Add the owned Lua region before a recognised `return config` boundary."""
    body = f'config.default_prog = {{ {_lua_string(zsh_path)}, "-l" }}'
    updated = _replace_owned_region(existing, "wezterm", body, comment="--")
    if "tools-installer terminal-shell wezterm" in existing:
        return (
            updated
            if any(line.strip() == "return config" for line in existing.splitlines())
            else None
        )

    lines = existing.splitlines(keepends=True)
    return_indices = [index for index, line in enumerate(lines) if line.strip() == "return config"]
    if len(return_indices) != 1:
        return None
    region = (
        f"{_marker('wezterm', '>>>', comment='--')}\n{body}\n"
        f"{_marker('wezterm', '<<<', comment='--')}\n"
    )
    index = return_indices[0]
    return "".join((*lines[:index], region, *lines[index:]))


def _kconfig_command(zsh_path: str) -> str:
    """Render the two login-shell argv values for Konsole's command field."""
    return shlex.join((zsh_path, "-l"))


# WR-01: KConfig's own value-decoding layer unescapes these sequences when it
# READS a value -- a separate layer from shlex's own shell-argv quoting.
# Without re-escaping after shlex.join, a zsh path containing a backslash
# round-trips wrong: shlex.quote('/opt/a\test/zsh') writes the literal text
# '/opt/a\test/zsh', and KConfig reads that back as '/opt/a<TAB>est/zsh'
# because \t is ITS OWN escape for a tab, silently corrupting the launch
# command.
_KCONFIG_ESCAPES: dict[str, str] = {"\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def _kconfig_value(value: str) -> str:
    """Encode a value for a KConfig entry, applied AFTER shell-argv quoting."""
    return "".join(_KCONFIG_ESCAPES.get(character, character) for character in value)


def _desktop_default(content: str) -> str | None:
    """Return the effective Desktop Entry default-profile value, if any."""
    in_desktop_entry = False
    found: str | None = None
    for line in content.splitlines():
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == "[Desktop Entry]"
        elif in_desktop_entry and line.startswith("DefaultProfile="):
            found = line.removeprefix("DefaultProfile=")
    return found


def _set_desktop_default(content: str, value: str | None) -> str:
    """Rewrite (or remove, when value is None) the effective DefaultProfile line.

    Mirrors _desktop_default's own last-[Desktop Entry]-group-wins traversal,
    so the exact line that function would report as effective is the one
    edited here -- never a guess at which of several [Desktop Entry] groups
    is authoritative. A no-op (returns content unchanged) when there is no
    such line to edit.
    """
    lines = content.split("\n")
    in_desktop_entry = False
    target: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == "[Desktop Entry]"
        elif in_desktop_entry and line.startswith("DefaultProfile="):
            target = index
    if target is None:
        return content
    if value:
        lines[target] = f"DefaultProfile={value}"
    else:
        del lines[target]
    return "\n".join(lines)


def _remove_if_owned(path: Path, terminal: str, *, comment: str = "#") -> bool:
    if not path.exists():
        return False
    existing = _read_text(path)
    updated = _replace_owned_region(existing, terminal, None, comment=comment)
    if updated == existing:
        return False
    _write_if_changed(path, updated)
    return True


# A terminal config is a few KiB; the cap bounds the read on the refresh worker.
_CONFIG_MAX_BYTES = 1 << 20


def _read_text(path: Path) -> str:
    """Read a terminal configuration file, refusing one this module cannot decode.

    A non-UTF-8 byte is reported as TerminalShellError -- an OSError subclass,
    like every other refusal here -- rather than the bare UnicodeDecodeError
    `bytes.decode` raises. UnicodeDecodeError is a ValueError, not an OSError,
    so it would escape the OSError handler each lifecycle call site wraps the
    synchronizer in. Refusing also leaves the file byte-identical rather than
    rewriting content this module could not read. A FIFO, a directory or an
    oversize file is refused the same way, through the non-blocking capped read,
    so the dry run on the refresh worker never stalls.
    """
    try:
        data = read_capped(path, _CONFIG_MAX_BYTES, follow_symlinks=True)
    except (FileNotFoundError, NotADirectoryError):
        return ""
    if data is None:
        raise TerminalShellError(
            f"{path} is not a regular file of at most {_CONFIG_MAX_BYTES >> 20} MiB; "
            "refusing to rewrite it"
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminalShellError(f"{path} is not valid UTF-8; refusing to rewrite it") from exc


def _write_if_changed(path: Path, content: str, *, write: bool = True) -> bool:
    """Report whether `content` differs from the file; write it only when `write`."""
    existing = _read_text(path)
    if content == existing:
        return False
    if not write:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, content)
    return True


def _sync_konsole(
    *, home: Path, environ: Mapping[str, str], zsh_path: str, lookup: Lookup, write: bool = True
) -> tuple[bool, str | None, bool]:
    """Create the dedicated Konsole profile and select it without touching user profiles.

    Returns (configured, warning, drifted); drifted means the profile or the
    konsolerc selection differed. The state file only records the prior
    default, so it is written only when `write` and never counts as drift.
    """
    if _safe_executable(lookup("konsole")) is None:
        return False, None, False

    data_home = _xdg_data_home(home, environ)
    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    state = data_home / "tools-installer" / "terminal-shell-konsole-default"
    konsolerc = _xdg_config_home(home, environ) / "konsolerc"
    profile_content = _read_text(profile)
    if profile_content and "tools-installer terminal-shell konsole-profile" not in profile_content:
        return False, "konsole: installer profile path is already user-owned", False

    original_konsolerc = _read_text(konsolerc)
    updated_profile = _replace_owned_region(
        profile_content,
        "konsole-profile",
        # CR-05: every real Konsole profile carries a Name= (confirmed
        # against this host's own /usr/share/konsole/Vapor.profile) --
        # Konsole's profile manager is documented to reject a profile with
        # no valid Name property, so a profile missing one is expected to be
        # silently rejected, making DefaultProfile= resolve to nothing and
        # Konsole fall back to its own built-in default shell regardless of
        # this module having run at all. WR-01: the Command value is
        # KConfig-escaped AFTER shlex's own shell-argv quoting -- a separate
        # decoding layer Konsole applies on read.
        "[General]\n"
        "Name=tools-installer zsh\n"
        "Parent=FALLBACK/\n"
        f"Command={_kconfig_value(_kconfig_command(zsh_path))}",
    )
    updated_konsolerc = _replace_owned_region(
        original_konsolerc,
        "konsole",
        "[Desktop Entry]\nDefaultProfile=tools-installer-zsh.profile",
    )
    if write and not state.exists():
        state.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(state, f"{_desktop_default(original_konsolerc) or ''}\n")
    profile_drifted = _write_if_changed(profile, updated_profile, write=write)
    konsolerc_drifted = _write_if_changed(konsolerc, updated_konsolerc, write=write)
    return True, None, profile_drifted or konsolerc_drifted


def _revert_konsole(*, home: Path, environ: Mapping[str, str]) -> bool:
    """Undo only the profile and selection whose ownership this module can prove.

    CR-06: konsolerc is a KConfig file Konsole itself rewrites on ordinary
    use, and KConfig's own backend does not preserve comment lines (confirmed
    against a real ~/.config/konsolerc on this host: zero `#` lines across 11
    entries) -- so the marker-comment ownership proof _remove_if_owned relies
    on can silently vanish while `DefaultProfile=tools-installer-zsh.profile`
    survives as a plain, now-unmarked entry. The state file is therefore made
    load-bearing rather than decorative: it is the one thing that can still
    prove ownership and supply the prior value to restore, independent of
    whether the marker comments survived.

    WR-02: stripping the marker-owned region (this function's first action)
    and deleting the owned profile file (its last) are both unconditionally
    ours whenever their own markers are present, regardless of whether our
    profile is still the *effective* default -- so a `DefaultProfile=` entry
    left behind in a non-effective `[Desktop Entry]` group (a later group, or
    the user having since picked a different profile by hand) is still
    cleaned up. Restoring the PRIOR default via the state file, in contrast,
    is deliberately conditioned on our profile still being effective:
    overwriting DefaultProfile with the recorded prior value would be wrong
    if the user had already chosen a different profile themselves.
    """
    data_home = _xdg_data_home(home, environ)
    profile = data_home / "konsole" / "tools-installer-zsh.profile"
    state = data_home / "tools-installer" / "terminal-shell-konsole-default"
    konsolerc = _xdg_config_home(home, environ) / "konsolerc"
    reverted = False

    # WR-02: unconditional -- ours by construction wherever the marker region
    # still exists, independent of whether it is currently effective.
    if _remove_if_owned(konsolerc, "konsole"):
        reverted = True

    # CR-06: the marker region may already be gone (a real Konsole rewrite)
    # while DefaultProfile still points at our profile as a plain, unmarked
    # entry. The state file is the one thing that can still prove ownership
    # in that case.
    if state.exists():
        prior = state.read_text().rstrip("\n")
        current_konsolerc = _read_text(konsolerc)
        if _desktop_default(current_konsolerc) == "tools-installer-zsh.profile":
            updated = _set_desktop_default(current_konsolerc, prior or None)
            if _write_if_changed(konsolerc, updated):
                reverted = True
        state.unlink()

    if profile.exists() and "tools-installer terminal-shell konsole-profile" in _read_text(profile):
        profile.unlink()
        reverted = True
    return reverted


def _revert_terminal_shells(*, home: Path, environ: Mapping[str, str]) -> TerminalShellResult:
    """Remove only complete terminal regions created by this synchronizer."""
    reverted: list[str] = []
    kitty = _kitty_config_path(home, environ)
    if _remove_if_owned(kitty, "kitty"):
        reverted.append("kitty")
    wezterm = _wezterm_config_path(home, environ)
    if _remove_if_owned(wezterm, "wezterm", comment="--"):
        reverted.append("wezterm")
    if _revert_konsole(home=home, environ=environ):
        reverted.append("konsole")
    return TerminalShellResult(reverted=tuple(reverted), skipped=("zsh unavailable",))


def sync_terminal_shells(
    *,
    home: Path,
    environ: Mapping[str, str],
    platform: Platform,
    lookup: Lookup,
    write: bool = True,
) -> TerminalShellResult:
    """Synchronize zsh into detected Linux terminal emulators.

    The caller injects every environment-dependent value so tests never consult or
    mutate the developer's actual home directory. `write=False` is a dry run
    (D-16, L-19-05): it reports `drifted` and writes, creates, renames and
    deletes nothing -- no revert, no .zshrc repair, no terminal config.
    """
    if platform.os == "macos":
        return TerminalShellResult(skipped=("macos",))

    zsh_path = _safe_executable(lookup("zsh"))
    if zsh_path is None:
        if not write:
            return TerminalShellResult(skipped=("zsh unavailable",))
        return _revert_terminal_shells(home=home, environ=environ)

    root = omz_root(home, environ)
    if write and root is not None:
        # CR-01: pass the real install directory, mirroring omz_present's own
        # $ZSH-aware check -- omz_present being true guarantees root is not
        # None, so the repair never hardcodes $HOME/.oh-my-zsh for an install
        # that actually lives elsewhere (a dotfiles-managed or XDG-relocated
        # oh-my-zsh checkout).
        # G-01: resolve the repair target through the same $ZDOTDIR-aware
        # resolver the Policies route already uses (setup.py::_ZSHRC), so the
        # repair never edits a file zsh does not source.
        ensure_zshrc_template(zshrc_path(home, environ), root)

    configured: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    drifted: list[str] = []
    if _safe_executable(lookup("kitty")) is None:
        skipped.append("kitty unavailable")
    else:
        config_path = _kitty_config_path(home, environ)
        updated = _replace_owned_region(
            _read_text(config_path), "kitty", f"shell {shlex.join((zsh_path, '-l'))}"
        )
        if _write_if_changed(config_path, updated, write=write):
            drifted.append("kitty")
        configured.append("kitty")

    if _safe_executable(lookup("wezterm")) is None:
        # CR-03: kitty (above) and Konsole (_sync_konsole) both gate on a
        # live presence check; WezTerm previously had none at all, so every
        # synchronizer run created ~/.config/wezterm/wezterm.lua -- and its
        # parent directory -- for an app that may not even be installed.
        skipped.append("wezterm unavailable")
    else:
        wezterm_path = _wezterm_config_path(home, environ)
        wezterm_existing = _read_text(wezterm_path)
        if not wezterm_existing:
            wezterm_existing = (
                'local wezterm = require "wezterm"\nlocal config = {}\nreturn config\n'
            )
        wezterm_content = _wezterm_content(wezterm_existing, zsh_path)
        if wezterm_content is None:
            warnings.append("wezterm: unsupported return shape")
        else:
            if _write_if_changed(wezterm_path, wezterm_content, write=write):
                drifted.append("wezterm")
            configured.append("wezterm")

    konsole_configured, konsole_warning, konsole_drifted = _sync_konsole(
        home=home, environ=environ, zsh_path=zsh_path, lookup=lookup, write=write
    )
    if konsole_configured:
        configured.append("konsole")
    if konsole_drifted:
        drifted.append("konsole")
    if konsole_warning is not None:
        warnings.append(konsole_warning)
    return TerminalShellResult(
        configured=tuple(configured),
        skipped=tuple(skipped),
        warnings=tuple(warnings),
        drifted=tuple(drifted),
    )
