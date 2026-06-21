"""Declarative tool catalog: Tool/Method model, category blurbs, and tomllib loaders."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

METHOD_KINDS = (
    "script",
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


def _empty_params() -> dict[str, object]:
    return {}


@dataclass(frozen=True)
class Method:
    kind: str
    params: dict[str, object] = field(default_factory=_empty_params)
    os: tuple[str, ...] = ()
    arch: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    category: str
    cmd: str
    methods: tuple[Method, ...]
    priority: str = "P3"
    audience: str = "both"
    desc: str = ""
    # No-op dependency seam for the tool-dependencies PRD: ids this tool needs
    # at install time. Parsed and carried here; no resolution logic lives yet.
    requires: tuple[str, ...] = ()


def load_tools(manifest_path: str | Path) -> list[Tool]:
    """Parse the registry TOML into validated Tool objects."""
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    tools: list[Tool] = []
    for row in data.get("tool", []):
        raw_methods = row.get("method", [])
        if not raw_methods:
            raise ValueError(f"tool '{row['id']}' declares no install methods")
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
            methods.append(Method(kind=kind, params=params, os=os_targets, arch=arch_targets))
        tools.append(
            Tool(
                id=row["id"],
                name=row.get("name", row["id"]),
                category=row["category"],
                cmd=row.get("cmd", row["id"]),
                methods=tuple(methods),
                priority=row.get("priority", "P3"),
                audience=row.get("audience", "both"),
                desc=row.get("desc", ""),
                requires=tuple(row.get("requires", [])),
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
        desc = row.get("desc")
        if not isinstance(desc, str) or not desc:
            raise ValueError(f"category '{cat_id}' is missing a non-empty 'desc'")
        if cat_id in blurbs:
            raise ValueError(f"duplicate category id '{cat_id}'")
        blurbs[cat_id] = desc
    return blurbs
