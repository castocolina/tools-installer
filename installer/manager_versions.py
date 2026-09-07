"""One batched outdated query per manager, preserving current AND latest.

Mirrors `installer/pnpm_globals.py`'s split of a pure parser plus a thin IO
wrapper (`parse_global_packages` / `pnpm_global_packages`). `None` means
unknown, not empty: a failed or unparseable report must never look like
"nothing is outdated", because absence from a non-`None` map means up to date.

Every child process goes through `installer/run.py::run_query`. A bare `pnpm`
argv element never reaches a subprocess; `real_pnpm()` supplies an absolute
path. The `-g` flag on `pnpm outdated` is mandatory — omitting it against a
directory with no package.json fails with `ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND`.

`parse_uv_tool_outdated` is fail-closed: any unrecognized non-indented line
makes the WHOLE report `None`. A benign new line shape from a future uv makes
uv rows render `unknown` until the parser is taught about it, which is a
visible, correctable failure rather than an invisible, wrong one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from installer.guards import real_pnpm
from installer.run import CommandError, run_query

_BREW_ENV = {"HOMEBREW_NO_AUTO_UPDATE": "1", "HOMEBREW_NO_ENV_HINTS": "1"}
_UV_OUTDATED = re.compile(r"^(\S+) v(\S+) \[latest: (\S+)\]$")
_UV_NO_TOOLS = "no tools installed"


@dataclass(frozen=True)
class ManagerVersion:
    current: str | None
    latest: str


@dataclass(frozen=True)
class OutdatedReport:
    """Per-manager outdated maps. `brew` and `cask` share one query, so a
    failed brew call sets BOTH to `None`."""

    brew: Mapping[str, ManagerVersion] | None
    cask: Mapping[str, ManagerVersion] | None
    pnpm: Mapping[str, ManagerVersion] | None
    uv: Mapping[str, ManagerVersion] | None


def parse_brew_outdated_json(
    raw: str,
) -> tuple[dict[str, ManagerVersion], dict[str, ManagerVersion]] | None:
    """Parse `brew outdated --json=v2` into (formulae, casks) as two maps.

    A payload missing the `formulae` or `casks` key, or carrying a malformed
    entry, returns `None`. A present empty list is a genuine "nothing outdated"
    signal and yields `{}` for that side.
    """
    try:
        data: object = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    payload = cast(dict[str, object], data)
    if "formulae" not in payload or "casks" not in payload:
        return None
    formulae_raw = payload["formulae"]
    casks_raw = payload["casks"]
    if not isinstance(formulae_raw, list) or not isinstance(casks_raw, list):
        return None
    formulae = _parse_brew_entries(cast(list[object], formulae_raw))
    casks = _parse_brew_entries(cast(list[object], casks_raw))
    if formulae is None or casks is None:
        return None
    return formulae, casks


def _parse_brew_entries(entries: list[object]) -> dict[str, ManagerVersion] | None:
    mapping: dict[str, ManagerVersion] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        item = cast(dict[str, object], entry)
        name = item.get("name")
        latest = item.get("current_version")
        if not isinstance(name, str) or not name:
            return None
        if not isinstance(latest, str) or not latest:
            return None
        installed = item.get("installed_versions")
        current: str | None = None
        if isinstance(installed, list) and installed:
            last: object = cast(list[object], installed)[-1]
            if isinstance(last, str) and last:
                current = last
        mapping[name] = ManagerVersion(current, latest)
    return mapping


def parse_pnpm_outdated_json(raw: str) -> dict[str, ManagerVersion] | None:
    """Parse `pnpm outdated -g --json`. Empty stdout is `None`, not up to date."""
    if not raw.strip():
        return None
    try:
        data: object = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    mapping: dict[str, ManagerVersion] = {}
    for name, value in cast(dict[str, object], data).items():
        if not isinstance(value, dict):
            return None
        item = cast(dict[str, object], value)
        latest = item.get("latest")
        if not isinstance(latest, str) or not latest:
            return None
        current_raw = item.get("current")
        current = current_raw if isinstance(current_raw, str) and current_raw else None
        mapping[name] = ManagerVersion(current, latest)
    return mapping


def parse_uv_tool_outdated(raw: str) -> dict[str, ManagerVersion] | None:
    """Parse `uv tool list --outdated`. Unrecognized lines make the whole report None.

    Empty output returns `{}` because uv prints nothing and exits 0 when every
    tool is current. Absence from a non-`None` map means up to date.
    """
    mapping: dict[str, ManagerVersion] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line[:1].isspace():
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            continue
        if _UV_NO_TOOLS in stripped.lower():
            continue
        match = _UV_OUTDATED.fullmatch(stripped)
        if match is None:
            return None
        mapping[match.group(1)] = ManagerVersion(match.group(2), match.group(3))
    return mapping


def brew_outdated(
    *, query: Callable[..., str] = run_query
) -> tuple[dict[str, ManagerVersion], dict[str, ManagerVersion]] | None:
    try:
        raw = query(["brew", "outdated", "--json=v2"], env=_BREW_ENV)
    except (CommandError, OSError):
        return None
    return parse_brew_outdated_json(raw)


def pnpm_outdated_global(
    *,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
    query: Callable[..., str] = run_query,
) -> dict[str, ManagerVersion] | None:
    pnpm = resolve_pnpm()
    if pnpm is None:
        return None
    try:
        raw = query([pnpm, "outdated", "-g", "--json"], accept_codes=(0, 1))
    except (CommandError, OSError):
        return None
    return parse_pnpm_outdated_json(raw)


def uv_tool_outdated(*, query: Callable[..., str] = run_query) -> dict[str, ManagerVersion] | None:
    try:
        raw = query(["uv", "tool", "list", "--outdated"])
    except (CommandError, OSError):
        return None
    return parse_uv_tool_outdated(raw)


def read_outdated(
    *,
    has_brew: bool,
    query: Callable[..., str] = run_query,
    resolve_pnpm: Callable[[], str | None] = real_pnpm,
) -> OutdatedReport:
    brew_maps = brew_outdated(query=query) if has_brew else None
    if brew_maps is None:
        brew, cask = None, None
    else:
        brew, cask = brew_maps
    return OutdatedReport(
        brew=brew,
        cask=cask,
        pnpm=pnpm_outdated_global(resolve_pnpm=resolve_pnpm, query=query),
        uv=uv_tool_outdated(query=query),
    )
