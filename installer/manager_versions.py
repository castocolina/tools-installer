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
    failed brew call sets BOTH to `None`. `greedy` is the tracked casks that
    auto-update (LIFE-10); `None` when that read failed, and `cask` is then `None`."""

    brew: Mapping[str, ManagerVersion] | None
    cask: Mapping[str, ManagerVersion] | None
    pnpm: Mapping[str, ManagerVersion] | None
    uv: Mapping[str, ManagerVersion] | None
    greedy: frozenset[str] | None = frozenset()


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

    An indented entry-point line or a `- name` line is only ever valid
    immediately after a matched `name vX.Y [latest: Z]` line — one appearing
    anywhere else has no preceding match to belong to, so it is unrecognized
    structure and fails the whole report closed rather than being skipped.
    """
    mapping: dict[str, ManagerVersion] = {}
    expect_entrypoint = False
    for line in raw.splitlines():
        if not line.strip():
            continue
        stripped = line.strip()
        if not mapping and not expect_entrypoint and _UV_NO_TOOLS in stripped.lower():
            return {}
        if line[:1].isspace() or stripped.startswith("- "):
            if not expect_entrypoint:
                return None
            continue
        match = _UV_OUTDATED.fullmatch(stripped)
        if match is None:
            return None
        mapping[match.group(1)] = ManagerVersion(match.group(2), match.group(3))
        expect_entrypoint = True
    return mapping


def brew_outdated(
    *, query: Callable[..., str] = run_query
) -> tuple[dict[str, ManagerVersion], dict[str, ManagerVersion]] | None:
    try:
        raw = query(["brew", "outdated", "--json=v2"], env=_BREW_ENV)
    except (CommandError, OSError):
        return None
    return parse_brew_outdated_json(raw)


def parse_brew_cask_auto_updates(raw: str) -> frozenset[str] | None:
    """Tokens of the installed casks that declare `auto_updates: true`. Any
    malformed entry makes the whole answer `None`, never a partial set."""
    try:
        data: object = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    casks_raw = cast(dict[str, object], data).get("casks")
    if not isinstance(casks_raw, list):
        return None
    auto: set[str] = set()
    for entry in cast(list[object], casks_raw):
        if not isinstance(entry, dict):
            return None
        item = cast(dict[str, object], entry)
        token = item.get("token")
        flag = item.get("auto_updates")
        if not isinstance(token, str) or not token or not isinstance(flag, bool):
            return None
        if flag:
            auto.add(token)
    return frozenset(auto)


def brew_cask_auto_updates(*, query: Callable[..., str] = run_query) -> frozenset[str] | None:
    try:
        raw = query(["brew", "info", "--cask", "--installed", "--json=v2"], env=_BREW_ENV)
    except (CommandError, OSError):
        return None
    return parse_brew_cask_auto_updates(raw)


def brew_greedy_outdated(
    *, query: Callable[..., str] = run_query
) -> dict[str, ManagerVersion] | None:
    """Casks outdated once auto-updating casks count (`--greedy-auto-updates`, not `--greedy`)."""
    try:
        raw = query(
            ["brew", "outdated", "--cask", "--greedy-auto-updates", "--json=v2"], env=_BREW_ENV
        )
    except (CommandError, OSError):
        return None
    parsed = parse_brew_outdated_json(raw)
    return None if parsed is None else parsed[1]


def _greedy_cask_read(
    casks: frozenset[str], cask: Mapping[str, ManagerVersion], *, query: Callable[..., str]
) -> tuple[frozenset[str], Mapping[str, ManagerVersion]] | None:
    """The tracked casks that auto-update, and the cask map with their greedy
    outdated rows merged in. Greedy `brew outdated` is asked only when one of ours
    auto-updates. `None` when a read failed: the cask side is incomplete without it."""
    if not casks:
        return frozenset(), cask
    auto = brew_cask_auto_updates(query=query)
    if auto is None:
        return None
    greedy = casks & auto
    if not greedy:
        return greedy, cask
    outdated = brew_greedy_outdated(query=query)
    if outdated is None:
        return None
    return greedy, {**cask, **{t: v for t, v in outdated.items() if t in greedy}}


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
    casks: frozenset[str] = frozenset(),
) -> OutdatedReport:
    """`casks` are the tracked cask tokens; empty off macOS, so Linux asks nothing new."""
    brew_maps = brew_outdated(query=query) if has_brew else None
    brew: Mapping[str, ManagerVersion] | None = None
    cask: Mapping[str, ManagerVersion] | None = None
    greedy: frozenset[str] | None = frozenset()
    if brew_maps is not None:
        brew, cask = brew_maps
        read = _greedy_cask_read(casks, cask, query=query)
        if read is None:
            cask, greedy = None, None
        else:
            greedy, cask = read
    elif has_brew:
        greedy = None
    return OutdatedReport(
        brew=brew,
        cask=cask,
        pnpm=pnpm_outdated_global(resolve_pnpm=resolve_pnpm, query=query),
        uv=uv_tool_outdated(query=query),
        greedy=greedy,
    )
