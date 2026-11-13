"""Safely synchronize the discovered zsh into Linux terminal configurations.

This module configures only marker-delimited regions in terminal-emulator files.
It never invokes a shell or changes an account login shell.
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from installer.agent_settings import (
    ABSENT,
    apply_value,
    parse_settings,
    read_settings,
    revert_group,
    same_value,
    settings_file,
    write_if_unchanged,
)
from installer.agent_settings import lookup as settings_lookup
from installer.atomic import FileSnapshot, atomic_write_text, read_capped
from installer.locations import display_path, zshenv_path, zshrc_path
from installer.omz import ensure_zshrc_template, omz_root
from installer.platform import Platform
from installer.receipts import read_ledger
from installer.run import CommandError, Runner
from installer.shellrc import apply_block, strip_block

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
    it from a dry run for `≈` (D-16). `zsh` is the resolved zsh path and `paths`
    maps each synchronized target (`zshenv`, `kitty`, `wezterm`, `konsole`, `alacritty`) to
    the file it wrote or checked.
    """

    configured: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    reverted: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    drifted: tuple[str, ...] = ()
    zsh: str | None = None
    paths: tuple[tuple[str, Path], ...] = ()


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
    # `or {}` keeps a user's own environment table set above the region.
    shell = _lua_string(zsh_path)
    body = "\n".join(
        (
            f'config.default_prog = {{ {shell}, "-l" }}',
            "config.set_environment_variables = config.set_environment_variables or {}",
            f"config.set_environment_variables.SHELL = {shell}",
        )
    )
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


# The owned SHELL export in the .zshenv zsh reads (CONF-05, D-15): every zsh, in a
# terminal or not, starts with the real zsh as $SHELL.
ZSHENV_BEGIN = "# >>> tools-installer shell >>>"
ZSHENV_END = "# <<< tools-installer shell <<<"


def zshenv_block(zsh_path: str) -> str:
    return f"{ZSHENV_BEGIN}\nexport SHELL={shlex.quote(zsh_path)}\n{ZSHENV_END}"


def _edit_zshenv(
    home: Path, environ: Mapping[str, str], block: str | None, *, write: bool
) -> tuple[bool, str | None]:
    """Apply `block` to the owned region of the .zshenv zsh reads, or strip it when None.

    Returns (changed, warning). An OSError (non-UTF-8, FIFO, oversize, permission)
    becomes one `zshenv:` warning, so the terminal configs still synchronize and
    this file is left as it was (review R1-21).
    """
    path = zshenv_path(home, environ)
    try:
        existing = _read_text(path)
        if block is None:
            updated = strip_block(existing, ZSHENV_BEGIN, ZSHENV_END)
        else:
            updated = apply_block(existing, block, ZSHENV_BEGIN, ZSHENV_END)
        return _write_if_changed(path, updated, write=write), None
    except OSError as exc:
        first_line = (str(exc).splitlines() or [type(exc).__name__])[0]
        return False, f"zshenv: {first_line}"


def _konsole_profile_path(home: Path, environ: Mapping[str, str]) -> Path:
    return _xdg_data_home(home, environ) / "konsole" / "tools-installer-zsh.profile"


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
    profile = _konsole_profile_path(home, environ)
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


# ---------------------------------------------------------------------------
# Alacritty (24 D-08, D-23): two owned regions in one TOML file. `alacritty` is the shell
# region (a branch of the synchronizer, follows zsh); `alacritty-keys` is install tuning
# (keybindings, written once at install, stripped with the tool). Each is guarded per part.
# ---------------------------------------------------------------------------

ALACRITTY = "alacritty"
ALACRITTY_KEYS = "alacritty-keys"
# The reason `alacritty_keys_pending` returns when only the install tuning has not run;
# version_status turns it into its `≈ apply install tuning` fact.
KEYS_PENDING = "install tuning not applied"
_KEYS_RECORD = "terminal-tuning-alacritty"
_CREATED_RECORD = "terminal-alacritty-created"
# TOML 1.0 escapes: `\u001b` is ESC. The Alt+arrow byte strings are the readline word keys.
_KEY_BINDINGS = (
    ("Left", "Alt", 'chars = "\\u001bb"'),
    ("Right", "Alt", 'chars = "\\u001bf"'),
    ("K", "Control|Shift", 'action = "ClearHistory"'),
)
_KEYS_HEADER = re.compile(r"^\s*\[\[\s*keyboard\.bindings\s*\]\]", re.MULTILINE)


def alacritty_config_path(home: Path, environ: Mapping[str, str]) -> Path:
    """The first existing of Alacritty's user config locations, in its own precedence order
    (alacritty(5): XDG alacritty/, XDG file, ~/.config/alacritty/, ~/.alacritty.toml), else the
    XDG one. The system-wide /etc/alacritty/alacritty.toml is never edited: it is not ours."""
    config_home = _xdg_config_home(home, environ)
    candidates = (
        config_home / "alacritty" / "alacritty.toml",
        config_home / "alacritty.toml",
        home / ".config" / "alacritty" / "alacritty.toml",
        home / ".alacritty.toml",
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def _keys_record(home: Path, environ: Mapping[str, str]) -> Path:
    return _xdg_data_home(home, environ) / "tools-installer" / _KEYS_RECORD


def _created_marker(home: Path, environ: Mapping[str, str]) -> Path:
    """Present while the installer itself created the Alacritty config file."""
    return _xdg_data_home(home, environ) / "tools-installer" / _CREATED_RECORD


def _first_line(exc: BaseException) -> str:
    return (str(exc).splitlines() or [type(exc).__name__])[0]


def _toml_string(value: str) -> str:
    """A TOML basic string; json.dumps escapes exactly what TOML requires."""
    return json.dumps(value)


def _snapshot_text(snapshot: FileSnapshot | None) -> str:
    if snapshot is None:
        return ""
    try:
        return snapshot.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminalShellError("the file is not valid UTF-8; refusing to rewrite it") from exc


def _user_document(text: str) -> tuple[dict[str, object], str]:
    """The parsed text outside both owned regions, and that text. Never raises a ValueError."""
    outside = _replace_owned_region(
        _replace_owned_region(text, ALACRITTY, None), ALACRITTY_KEYS, None
    )
    try:
        return tomllib.loads(outside), outside
    except tomllib.TOMLDecodeError as exc:
        raise TerminalShellError(f"the file does not parse ({exc}); left as it is") from exc


def _table(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = document.get(name)
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _shell_plan(document: Mapping[str, object], zsh_path: str) -> tuple[str | None, list[str]]:
    """The shell region body and the `partial:` warnings, decided per part (D-08)."""
    parts: list[str] = []
    warnings: list[str] = []
    if "shell" in _table(document, "terminal"):
        warnings.append("alacritty: partial: you already define terminal.shell")
    else:
        parts.append(f'[terminal.shell]\nprogram = {_toml_string(zsh_path)}\nargs = ["-l"]')
    if "env" in document:
        warnings.append("alacritty: partial: you already define env")
    else:
        parts.append(f"[env]\nSHELL = {_toml_string(zsh_path)}")
    return "\n\n".join(parts) or None, warnings


@dataclass(frozen=True)
class _KeysPlan:
    body: str | None
    conflicts: tuple[str, ...] = ()
    refusal: str | None = None


def _binding_id(key: object, mods: object) -> tuple[str, frozenset[str]]:
    """Alacritty reads key and modifier names case-insensitively, in any order."""
    names = str(mods or "").split("|")
    return str(key).lower(), frozenset(name.strip().lower() for name in names if name.strip())


def _keys_plan(document: Mapping[str, object], outside: str) -> _KeysPlan:
    bindings = _table(document, "keyboard").get("bindings")
    if bindings is not None and not _KEYS_HEADER.search(outside):
        return _KeysPlan(None, refusal="you already define keyboard.bindings inline")
    entries = cast("list[object]", bindings) if isinstance(bindings, list) else []
    taken = {
        _binding_id(entry.get("key"), entry.get("mods"))
        for entry in (cast("Mapping[str, object]", e) for e in entries if isinstance(e, dict))
    }
    blocks: list[str] = []
    conflicts: list[str] = []
    for key, mods, action in _KEY_BINDINGS:
        if _binding_id(key, mods) in taken:
            conflicts.append(f"alacritty: partial: you already bind {mods.replace('|', '+')}+{key}")
        else:
            blocks.append(f'[[keyboard.bindings]]\nkey = "{key}"\nmods = "{mods}"\n{action}')
    return _KeysPlan("\n\n".join(blocks) or None, tuple(conflicts))


def _commit_alacritty(
    path: Path,
    before: FileSnapshot | None,
    text: str,
    updated: str,
    *,
    write: bool,
    created_marker: Path,
) -> bool:
    """Report whether `updated` differs; write it only when `write`, and only after it re-parses
    and only if the file still is what was read (compare-before-commit)."""
    if updated == text:
        return False
    try:
        tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise TerminalShellError(f"the edit would not re-parse ({exc}); nothing written") from exc
    if write:
        write_if_unchanged(path, before, updated)
        if before is None:  # the file is ours: strip may delete it once nothing else is in it
            created_marker.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(created_marker, "created\n")
    return True


def _sync_alacritty(
    home: Path, environ: Mapping[str, str], zsh_path: str, *, write: bool
) -> tuple[bool, bool, tuple[str, ...]]:
    """Write or check the `alacritty` region. Returns (configured, drifted, warnings)."""
    path = alacritty_config_path(home, environ)
    try:
        before = read_settings(path)
        text = _snapshot_text(before)
        document, outside = _user_document(text)
        body, warnings = _shell_plan(document, zsh_path)
        warnings.extend(_keys_plan(document, outside).conflicts)
        updated = _replace_owned_region(text, ALACRITTY, body)
        drifted = _commit_alacritty(
            path,
            before,
            text,
            updated,
            write=write,
            created_marker=_created_marker(home, environ),
        )
    except OSError as exc:
        return False, False, (f"alacritty: {_first_line(exc)}",)
    return body is not None, drifted, tuple(warnings)


def _strip_alacritty_region(path: Path, region: str) -> bool:
    before = read_settings(path)
    if before is None:
        return False
    text = _snapshot_text(before)
    updated = _replace_owned_region(text, region, None)
    if updated == text:
        return False
    write_if_unchanged(path, before, updated)
    return True


def apply_alacritty_keys(
    home: Path, environ: Mapping[str, str], *, skip_recorded: bool
) -> tuple[tuple[str, ...], str | None]:
    """Write the `alacritty-keys` region, then its written-once record. Returns (lines, refusal).

    `skip_recorded` (RECONFIGURE) leaves a recorded install alone: a region the user deleted
    stays deleted. Nothing is written when the file cannot take the region."""
    record = _keys_record(home, environ)
    if skip_recorded and record.exists():
        return (), None
    path = alacritty_config_path(home, environ)
    try:
        before = read_settings(path)
        text = _snapshot_text(before)
        plan = _keys_plan(*_user_document(text))
        if plan.refusal is not None:
            return (), plan.refusal
        updated = _replace_owned_region(text, ALACRITTY_KEYS, plan.body)
        _commit_alacritty(
            path,
            before,
            text,
            updated,
            write=True,
            created_marker=_created_marker(home, environ),
        )
        record.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(record, "written\n")
    except OSError as exc:
        return (), _first_line(exc)
    added = (
        ("Alacritty keys: Alt+Left and Alt+Right move by word, Control+Shift+K clears history.",)
        if plan.body is not None
        else ()
    )
    return (*added, *plan.conflicts), None


def alacritty_keys_pending(home: Path, environ: Mapping[str, str]) -> str | None:
    """None when the keys region or its record exists (a hand-removed region is the user's
    choice); `KEYS_PENDING` when the install tuning has not run; else why the file cannot
    take the region."""
    if _keys_record(home, environ).exists():
        return None
    try:
        text = _snapshot_text(read_settings(alacritty_config_path(home, environ)))
        if _replace_owned_region(text, ALACRITTY_KEYS, None) != text:
            return None
        plan = _keys_plan(*_user_document(text))
    except OSError as exc:
        return _first_line(exc)
    return plan.refusal or KEYS_PENDING


def strip_alacritty(home: Path, environ: Mapping[str, str]) -> tuple[str, ...]:
    """Remove both owned regions and the record (the tool is gone); the file stays.
    Returns warnings. A region that could not be stripped keeps the record."""
    path = alacritty_config_path(home, environ)
    warnings: list[str] = []
    for region in (ALACRITTY, ALACRITTY_KEYS):
        try:
            _strip_alacritty_region(path, region)
        except OSError as exc:
            warnings.append(f"alacritty: {_first_line(exc)}")
    if not warnings:
        _keys_record(home, environ).unlink(missing_ok=True)
        warnings.extend(_drop_created_config(path, _created_marker(home, environ)))
    return tuple(warnings)


def _drop_created_config(path: Path, marker: Path) -> list[str]:
    """Delete the config file the installer created once nothing but whitespace is left."""
    if not marker.exists():
        return []
    try:
        before = read_settings(path)
        if before is None or _snapshot_text(before).strip():
            marker.unlink()  # gone, or the user's now: never ours to delete
            return []
        path.unlink(missing_ok=True)
        marker.unlink()
    except OSError as exc:
        return [f"alacritty: {_first_line(exc)}"]
    return []


# ---------------------------------------------------------------------------
# herdr (24 D-08b, D-22): `terminal.default_shell` follows zsh. Written absent-only through the
# ledgered settings writer, so a user's own value is never overwritten and the key is reverted
# only while it still holds the path written; the running server is asked to reload it.
# ---------------------------------------------------------------------------

HERDR = "herdr"
_HERDR_SHELL_KEY = ("terminal", "default_shell")
_HERDR_PARTIAL = "herdr: partial: you already set terminal.default_shell"


def _herdr_reload(herdr_path: str, runner: Runner | None) -> tuple[str, ...]:
    """Ask the running server to re-read its config; a failure is a note, never a failure."""
    if runner is None:
        return ()
    try:
        runner([herdr_path, "server", "reload-config"])
    except (CommandError, OSError) as exc:
        return (f"herdr: reload-config failed ({_first_line(exc)}); new panes read it on restart",)
    return ()


def _herdr_check(path: Path, zsh_path: str) -> tuple[bool, bool, tuple[str, ...]]:
    """The dry run: (configured, drifted, warnings) from the config as it is now."""
    try:
        snapshot = read_settings(path)
        text = snapshot.data.decode("utf-8") if snapshot is not None else ""
        document = parse_settings(text, "toml")
    except (OSError, ValueError) as exc:  # UnicodeDecodeError and SettingsParseError
        return False, False, (f"herdr: {_first_line(exc)}",)
    current = settings_lookup(document, _HERDR_SHELL_KEY)
    if current is ABSENT:
        return True, True, ()
    if same_value(current, zsh_path):
        return True, False, ()
    ledger = read_ledger(
        HERDR
    )  # a value the ledger records as ours follows zsh (the apply swaps it)
    if ledger is not None and any(
        entry.setting == "default-shell" and same_value(current, entry.value)
        for entry in ledger.entries
    ):
        return True, True, ()
    return False, False, (_HERDR_PARTIAL,)


def _sync_herdr(
    home: Path,
    environ: Mapping[str, str],
    platform: Platform,
    zsh_path: str,
    herdr_path: str,
    *,
    write: bool,
    runner: Runner | None,
) -> tuple[bool, bool, tuple[str, ...]]:
    """Point herdr at zsh. Returns (configured, drifted, warnings)."""
    path = settings_file(HERDR, home=home, platform_os=platform.os, environ=environ)
    if not write:
        return _herdr_check(path, zsh_path)
    try:
        result = apply_value(
            HERDR,
            "default-shell",
            zsh_path,
            home=home,
            platform_os=platform.os,
            environ=environ,
        )
    except OSError as exc:
        return False, False, (f"herdr: {_first_line(exc)}",)
    if result.refused is not None:
        return False, False, (f"herdr: {result.refused.splitlines()[0]}",)
    kinds = {key.kind for key in result.keys}
    if "set_by_you" in kinds:
        return False, False, (_HERDR_PARTIAL,)
    wrote = bool(kinds & {"wrote", "replaced_ours"})
    return True, wrote, _herdr_reload(herdr_path, runner) if wrote else ()


def _revert_herdr(home: Path, environ: Mapping[str, str], platform: Platform) -> tuple[bool, str]:
    """Remove the ledgered key while it still holds the written path. Returns (removed, warning);
    the reload is skipped here: panes already open keep the shell they started with."""
    try:
        results = revert_group(
            HERDR, "default-shell", home=home, platform_os=platform.os, environ=environ
        )
    except OSError as exc:
        return False, f"herdr: {_first_line(exc)}"
    removed = any(key.kind == "removed" for result in results for key in result.keys)
    refused = next((result.refused for result in results if result.refused), None)
    return removed, f"herdr: {refused.splitlines()[0]}" if refused else ""


def _revert_terminal_shells(
    *, home: Path, environ: Mapping[str, str], platform: Platform
) -> TerminalShellResult:
    """Remove only complete terminal regions created by this synchronizer."""
    reverted: list[str] = []
    zshenv_changed, zshenv_warning = _edit_zshenv(home, environ, None, write=True)
    if zshenv_warning is not None:
        # Stop like a failed unregister: the terminals keep exporting the SHELL the
        # .zshenv still names, so nothing is half-removed (X-02).
        return TerminalShellResult(
            skipped=("zsh unavailable",),
            warnings=(f"{zshenv_warning}; kitty, WezTerm and Konsole left as they are",),
        )
    if zshenv_changed:
        reverted.append("zshenv")
    kitty = _kitty_config_path(home, environ)
    if _remove_if_owned(kitty, "kitty"):
        reverted.append("kitty")
    wezterm = _wezterm_config_path(home, environ)
    if _remove_if_owned(wezterm, "wezterm", comment="--"):
        reverted.append("wezterm")
    if _revert_konsole(home=home, environ=environ):
        reverted.append("konsole")
    warnings: list[str] = []
    try:
        if _strip_alacritty_region(alacritty_config_path(home, environ), ALACRITTY):
            reverted.append("alacritty")
    except OSError as exc:
        warnings.append(f"alacritty: {_first_line(exc)}")
    herdr_removed, herdr_warning = _revert_herdr(home, environ, platform)
    if herdr_removed:
        reverted.append("herdr")
    if herdr_warning:
        warnings.append(herdr_warning)
    return TerminalShellResult(
        reverted=tuple(reverted), skipped=("zsh unavailable",), warnings=tuple(warnings)
    )


def sync_terminal_shells(
    *,
    home: Path,
    environ: Mapping[str, str],
    platform: Platform,
    lookup: Lookup,
    write: bool = True,
    strip_only: bool = False,
    runner: Runner | None = None,
) -> TerminalShellResult:
    """Synchronize zsh into detected Linux terminal emulators and the .zshenv zsh reads.

    The owned SHELL block in .zshenv (CONF-05) is kept first, then kitty, WezTerm and
    Konsole. The caller injects every environment-dependent value so tests never
    consult or mutate the developer's actual home directory. `write=False` is a dry
    run (D-16, L-19-05): it reports `drifted` and writes, creates, renames and
    deletes nothing -- no revert, no .zshrc repair, no terminal config. `strip_only`
    is the uninstall form: it only strips the owned regions once zsh is gone and
    never writes or creates one while zsh is still present (CR-09). `runner` runs herdr's
    `server reload-config` after its `default_shell` was written; a dry run never reloads.
    """
    if platform.os == "macos":
        return TerminalShellResult(skipped=("macos",))

    zsh_path = _safe_executable(lookup("zsh"))
    if zsh_path is None:
        if not write:
            return TerminalShellResult(skipped=("zsh unavailable",))
        return _revert_terminal_shells(home=home, environ=environ, platform=platform)
    if strip_only:
        return TerminalShellResult(skipped=("zsh present",), zsh=zsh_path)

    configured: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    drifted: list[str] = []
    paths: list[tuple[str, Path]] = []
    zshenv = zshenv_path(home, environ)
    zshenv_changed, zshenv_warning = _edit_zshenv(
        home, environ, zshenv_block(zsh_path), write=write
    )
    if zshenv_warning is not None:
        warnings.append(zshenv_warning)
    else:
        paths.append(("zshenv", zshenv))
        if write:
            configured.append("zshenv")
        if zshenv_changed:
            drifted.append("zshenv")

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

    if _safe_executable(lookup("kitty")) is None:
        skipped.append("kitty unavailable")
    else:
        config_path = _kitty_config_path(home, environ)
        # kitty's `env` line takes the rest of the line as the value, so the path is not quoted.
        updated = _replace_owned_region(
            _read_text(config_path),
            "kitty",
            f"shell {shlex.join((zsh_path, '-l'))}\nenv SHELL={zsh_path}",
        )
        if _write_if_changed(config_path, updated, write=write):
            drifted.append("kitty")
        configured.append("kitty")
        paths.append(("kitty", config_path))

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
            paths.append(("wezterm", wezterm_path))

    konsole_configured, konsole_warning, konsole_drifted = _sync_konsole(
        home=home, environ=environ, zsh_path=zsh_path, lookup=lookup, write=write
    )
    if konsole_configured:
        configured.append("konsole")
        paths.append(("konsole", _konsole_profile_path(home, environ)))
    if konsole_drifted:
        drifted.append("konsole")
    if konsole_warning is not None:
        warnings.append(konsole_warning)
    if _safe_executable(lookup("alacritty")) is not None:
        has_shell, shell_drifted, shell_warnings = _sync_alacritty(
            home, environ, zsh_path, write=write
        )
        if has_shell:
            configured.append("alacritty")
            paths.append(("alacritty", alacritty_config_path(home, environ)))
        if shell_drifted:
            drifted.append("alacritty")
        warnings.extend(shell_warnings)
    herdr_path = _safe_executable(lookup(HERDR))
    if herdr_path is not None:
        has_default, default_drifted, default_warnings = _sync_herdr(
            home, environ, platform, zsh_path, herdr_path, write=write, runner=runner
        )
        if has_default:
            configured.append(HERDR)
            paths.append(
                (HERDR, settings_file(HERDR, home=home, platform_os=platform.os, environ=environ))
            )
        if default_drifted:
            drifted.append(HERDR)
        warnings.extend(default_warnings)
    return TerminalShellResult(
        configured=tuple(configured),
        skipped=tuple(skipped),
        warnings=tuple(warnings),
        drifted=tuple(drifted),
        zsh=zsh_path,
        paths=tuple(paths),
    )


def sync_message(result: TerminalShellResult, *, report_changes: bool = False) -> str | None:
    """The one line a lifecycle route shows for a synchronizer run, or None. With
    `report_changes` (the post-run sync after an install, update or reconfigure) every
    file the run wrote is named as a Shell line, so a write is never silent (X-01)."""
    parts: list[str] = []
    if report_changes:
        paths = dict(result.paths)
        if "zshenv" in result.drifted and "zshenv" in paths:
            parts.append(
                f"Shell: {display_path(paths['zshenv'])} now exports SHELL={result.zsh}; "
                "new terminals start with it"
            )
        terminals = [name for name in result.drifted if name != "zshenv"]
        if terminals:
            verb = "starts" if len(terminals) == 1 else "start"
            parts.append(f"Shell: {', '.join(terminals)} now {verb} zsh")
    messages = list(result.warnings)
    if result.reverted:
        messages.append("zsh is no longer present; reverted " + ", ".join(result.reverted))
    if messages:
        parts.append("Terminal shell synchronization warning: " + "; ".join(messages))
    return "; ".join(parts) or None
