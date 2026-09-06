"""Declarative tool catalog: Tool/Method model, category blurbs, and tomllib loaders."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar, cast

from installer.enums import Audience, Category, Priority, Tier
from installer.versions import parse_declared_version

SMOKE_CHECK_NAMES: frozenset[str] = frozenset({"puppeteer-browser"})

METHOD_KINDS = (
    "script",
    "node",
    "uv-tool",
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


def _parse_pkg_list(raw: object, field: str, context: str) -> tuple[str, ...]:
    """Validate npm package names destined for a pnpm install-group spec.

    An empty element would produce a dangling separator in the joined spec, and a
    name that already contains a separator would silently create an install group
    nobody declared.
    """
    if not isinstance(raw, list):
        raise ValueError(f"{context}: '{field}' must be a list of package names")
    items = cast(list[object], raw)
    names: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{context}: '{field}' must be a list of package names")
        if not item or "," in item:
            raise ValueError(
                f"{context}: '{field}' contains an empty or comma-bearing package name"
            )
        names.append(item)
    return tuple(names)


def _parse_version_map(raw: object, field: str, context: str) -> dict[str, str]:
    """Validate a package-name -> semver-range table for a pnpm install group.

    Both halves end up on either side of an `@` inside a comma-joined group
    element, so an empty value or a comma would smuggle extra packages.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{context}: '{field}' must be a table of package names to version ranges")
    table = cast(dict[object, object], raw)
    out: dict[str, str] = {}
    for key, value in table.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f"{context}: '{field}' keys and values must be strings")
        if not key or not value or "," in key or "," in value:
            raise ValueError(
                f"{context}: '{field}' contains an empty or comma-bearing package name or range"
            )
        out[key] = value
    return out


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
                if "," in npm_pkg:
                    raise ValueError(
                        f"tool '{row['id']}': method 'node' 'npm_pkg' must not contain a comma"
                    )
                context = f"tool '{row['id']}'"
                co_install: tuple[str, ...] = ()
                if "co_install" in params:
                    co_install = _parse_pkg_list(params["co_install"], "co_install", context)
                install_group = {npm_pkg, *co_install}
                if "allow_build" in params:
                    allow_build = _parse_pkg_list(params["allow_build"], "allow_build", context)
                    # An allow-build entry permits arbitrary code execution during
                    # install AND, per pnpm's own add documentation, persists that
                    # permission into pnpm's build-allowance configuration so future
                    # versions of the same package run their scripts unprompted — so
                    # it may only ever name a package this very invocation installs.
                    for name in allow_build:
                        if name not in install_group:
                            raise ValueError(
                                f"{context}: allow_build names '{name}' "
                                "which is not in the install group"
                            )
                if "versions" in params:
                    versions = _parse_version_map(params["versions"], "versions", context)
                    # A version pin for a package the invocation does not install is
                    # dead data that would read as a guarantee.
                    for name in versions:
                        if name not in install_group:
                            raise ValueError(
                                f"{context}: versions names '{name}' "
                                "which is not in the install group"
                            )
                if "min_node" in params:
                    min_node = params["min_node"]
                    if not isinstance(min_node, str) or not min_node:
                        raise ValueError(f"{context}: min_node must be a non-empty string")
                    if parse_declared_version(min_node) is None:
                        raise ValueError(
                            f"{context}: min_node '{min_node}' is not a concrete version"
                        )
                if "smoke" in params:
                    smoke = params["smoke"]
                    # A registry-supplied COMMAND would be arbitrary code execution
                    # declared by data; a registry-supplied NAME selects between
                    # implementations this repository reviews and tests.
                    if not isinstance(smoke, str) or not smoke:
                        raise ValueError(f"{context}: smoke must be a non-empty string")
                    if smoke not in SMOKE_CHECK_NAMES:
                        known = ", ".join(sorted(SMOKE_CHECK_NAMES))
                        raise ValueError(
                            f"{context}: unknown smoke '{smoke}' (expected one of: {known})"
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
