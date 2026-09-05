"""Declarative tool catalog: Tool/Method model, category blurbs, and tomllib loaders."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar, cast

from installer.enums import Audience, Category, Priority, Tier

METHOD_KINDS = (
    "script",
    "node",
    "sdkman",
    "github_release",
    "tarball",
    "app",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
    "cask",
)

EnumValue = TypeVar("EnumValue", Audience, Category, Priority, Tier)


def _empty_params() -> dict[str, object]:
    return {}


def _parse_enum(enum_type: type[EnumValue], value: object, field: str, context: str) -> EnumValue:
    if not isinstance(value, str):
        raise ValueError(f"{context}: '{field}' must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(
            f"{context}: unknown {field} '{value}' (expected one of: {allowed})"
        ) from exc


def _parse_id_list(raw: object, field: str, context: str) -> tuple[str, ...]:
    """Validate a registry list-of-tool-ids field and freeze it.

    Two shapes are rejected here rather than downstream: a bare string, because
    tuple("pnpm") would silently become ('p','n','p','m'), and a non-string
    element, because tomllib hands back `Any` and the declared
    `tuple[str, ...]` would otherwise be a promise nothing enforces — the
    failure would surface as a TypeError in the TUI's detail bar on an
    unrelated keypress instead of a load-time error naming the tool.
    """
    if not isinstance(raw, list):
        raise ValueError(f"{context}: '{field}' must be a list of tool ids")
    # tomllib is the untyped boundary: it hands back `Any`, so the element type
    # is typed here explicitly and then checked, rather than assumed.
    items = cast(list[object], raw)
    ids: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{context}: '{field}' must be a list of tool ids")
        ids.append(item)
    return tuple(ids)


@dataclass(frozen=True)
class Method:
    kind: str
    params: dict[str, object] = field(default_factory=_empty_params)
    os: tuple[str, ...] = ()
    arch: tuple[str, ...] = ()


@dataclass(frozen=True, init=False)
class Tool:
    id: str
    name: str
    category: str
    cmd: str
    methods: tuple[Method, ...]
    priority: Priority
    audience: Audience
    tier: Tier
    desc: str = ""
    # No-op dependency seam for the tool-dependencies PRD: ids this tool needs
    # at install time. Parsed and carried here; no resolution logic lives yet.
    requires: tuple[str, ...] = ()
    # Soft-dependency seam for REQ-recommends-soft-dependency: ids this tool
    # pairs well with but never auto-installs and never drags in, surfaced only
    # as a selection-time prompt. Distinct from `requires`, which
    # resolve_dependencies expands transitively.
    recommends: tuple[str, ...] = ()

    def __init__(
        self,
        id: str,
        name: str,
        category: str | Category,
        cmd: str,
        methods: tuple[Method, ...],
        priority: str | Priority = Priority.P3,
        audience: str | Audience = Audience.BOTH,
        tier: str | Tier = Tier.USER,
        desc: str = "",
        requires: tuple[str, ...] = (),
        recommends: tuple[str, ...] = (),
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "category", str(category))
        object.__setattr__(self, "cmd", cmd)
        object.__setattr__(self, "methods", methods)
        object.__setattr__(
            self, "priority", _parse_enum(Priority, priority, "priority", f"tool '{id}'")
        )
        object.__setattr__(
            self, "audience", _parse_enum(Audience, audience, "audience", f"tool '{id}'")
        )
        object.__setattr__(self, "tier", _parse_enum(Tier, tier, "tier", f"tool '{id}'"))
        object.__setattr__(self, "desc", desc)
        object.__setattr__(self, "requires", requires)
        object.__setattr__(self, "recommends", recommends)


def load_tools(manifest_path: str | Path) -> list[Tool]:
    """Parse the registry TOML into validated Tool objects."""
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    tools: list[Tool] = []
    for row in data.get("tool", []):
        raw_methods = row.get("method", [])
        if not raw_methods:
            raise ValueError(f"tool '{row['id']}' declares no install methods")
        _parse_enum(Category, row["category"], "category", f"tool '{row['id']}'")
        if "tier" not in row:
            raise ValueError(f"tool '{row['id']}': missing required 'tier'")
        methods: list[Method] = []
        for entry in raw_methods:
            kind = entry["kind"]
            if kind not in METHOD_KINDS:
                raise ValueError(f"tool '{row['id']}': unknown method kind '{kind}'")
            raw_os = entry.get("os", [])
            if isinstance(raw_os, str):
                # tuple("macos") would silently become ('m','a','c','o','s'); a list is required.
                raise ValueError(f"tool '{row['id']}': method 'os' must be a list of strings")
            os_targets = tuple(raw_os)
            raw_arch = entry.get("arch", [])
            if isinstance(raw_arch, str):
                # tuple("arm64") would silently become ('a','r','m','6','4'); a list is required.
                raise ValueError(f"tool '{row['id']}': method 'arch' must be a list of strings")
            arch_targets = tuple(raw_arch)
            params = {k: v for k, v in entry.items() if k not in ("kind", "os", "arch")}
            if kind == "node":
                npm_pkg = params.get("npm_pkg")
                if not isinstance(npm_pkg, str) or not npm_pkg:
                    raise ValueError(
                        f"tool '{row['id']}': method 'node' requires a non-empty 'npm_pkg'"
                    )
            if kind == "sdkman":
                candidate = params.get("candidate")
                if not isinstance(candidate, str) or not candidate:
                    raise ValueError(
                        f"tool '{row['id']}': method 'sdkman' requires a non-empty 'candidate'"
                    )
            methods.append(Method(kind=kind, params=params, os=os_targets, arch=arch_targets))
        context = f"tool '{row['id']}'"
        requires = _parse_id_list(row.get("requires", []), "requires", context)
        recommends = _parse_id_list(row.get("recommends", []), "recommends", context)
        tools.append(
            Tool(
                id=row["id"],
                name=row.get("name", row["id"]),
                category=row["category"],
                cmd=row.get("cmd", row["id"]),
                methods=tuple(methods),
                priority=row.get("priority", "P3"),
                audience=row.get("audience", "both"),
                tier=row["tier"],
                desc=row.get("desc", ""),
                requires=requires,
                recommends=recommends,
            )
        )
    return tools


def load_categories(manifest_path: str | Path) -> dict[str, str]:
    """Parse the registry's [[category]] sections into an ordered id -> desc map.

    Reads the file independently of load_tools. The sections supply hover text
    only — the wizard's menu order is derived from the tools, not from here.
    """
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    blurbs: dict[str, str] = {}
    for index, row in enumerate(data.get("category", [])):
        cat_id = row.get("id")
        if not isinstance(cat_id, str) or not cat_id:
            raise ValueError(f"category section #{index} is missing a non-empty 'id'")
        _parse_enum(Category, cat_id, "category id", f"category section #{index}")
        desc = row.get("desc")
        if not isinstance(desc, str) or not desc:
            raise ValueError(f"category '{cat_id}' is missing a non-empty 'desc'")
        if cat_id in blurbs:
            raise ValueError(f"duplicate category id '{cat_id}'")
        blurbs[cat_id] = desc
    return blurbs
