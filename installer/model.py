"""Declarative tool catalog: Tool/Method model, category blurbs, and tomllib loaders."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeVar, cast

from installer.enums import Audience, Category, Priority, Tier
from installer.host_setup import HOST_SETUP_IDS
from installer.versions import parse_declared_version

SMOKE_CHECK_NAMES: frozenset[str] = frozenset({"puppeteer-browser"})

# Duplicated (not imported) from installer/postinstall.py::POSTINSTALL_HOOKS's
# keys, for the same layering reason SMOKE_CHECK_NAMES is duplicated from
# installer/executors.py::SMOKE_CHECKS rather than imported: this module
# stays a pure data/validation layer with no dependency on the heavier
# installer.postinstall module.
POSTINSTALL_HOOK_NAMES: frozenset[str] = frozenset({"codegraph-mcp-register", "rtk-register"})

METHOD_KINDS = (
    "script",
    "node",
    "uv-tool",
    "sdkman",
    "host_setup",
    "skill_pack",
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

# Multi-hook post-install action names. Distinct from `Tool.postinstall` above:
# `postinstall` selects a single hook from POSTINSTALL_HOOK_NAMES by name for a
# package-owned side effect (e.g. registering an MCP server); `post_install`
# lists zero or more of these reviewed shell/environment actions run once per
# tool.
POST_INSTALL_ACTIONS = (
    "configure_path",
    "source_shell_init",
    "set_login_shell",
    "enable_corepack",
    "pnpm_setup",
    "write_agent_reference",
)
SENSITIVE_POST_INSTALL_ACTIONS = ("set_login_shell",)
OWNER_PROBES = (
    "managed-download",
    "host-setup",
    "brew",
    "apt",
    "dnf",
    "pacman",
    "pnpm",
    "sdkman",
)
SKILL_HARNESSES = (
    "antigravity",
    "claude",
    "codex",
    "copilot",
    "cursor",
    "kilo",
    "kimi",
    "opencode",
    "pi",
    "windsurf",
)
SKILL_REVISION_POLICIES = (
    "host-marketplace-current",
    "package-manager-latest",
    "upstream-default-branch",
    "upstream-latest",
)
SKILL_TARGET_SCOPES = ("global", "harness", "project")
SKILL_OPERATION_MODES = ("command", "manual-required")
SKILL_OPERATION_IDS = ("codex_plugin_status", "pi_package_status")

EnumValue = TypeVar("EnumValue", Audience, Category, Priority, Tier)


def _parse_closed_string_list(
    raw: object, *, tool_id: object, field: str, allowed: tuple[str, ...], label: str
) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"tool '{tool_id}': '{field}' must be a list")
    values_as_objects = cast(list[object], raw)
    if not all(isinstance(value, str) for value in values_as_objects):
        raise ValueError(f"tool '{tool_id}': '{field}' must contain only strings")
    values = cast(list[str], values_as_objects)
    unknown_values = set(values).difference(allowed)
    if unknown_values:
        raise ValueError(f"tool '{tool_id}': unknown {label} '{next(iter(unknown_values))}'")
    return tuple(values)


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


@dataclass(frozen=True)
class SkillTarget:
    scope: Literal["global", "harness", "project"]
    path: str


@dataclass(frozen=True)
class CodexPluginStatusArgs:
    plugin: str


@dataclass(frozen=True)
class PiPackageStatusArgs:
    package: str


SkillOperationArgs = CodexPluginStatusArgs | PiPackageStatusArgs


@dataclass(frozen=True)
class SkillOperation:
    mode: Literal["command", "manual-required"]
    operation_id: Literal["codex_plugin_status", "pi_package_status"] | None = None
    args: SkillOperationArgs | None = None
    instructions: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillLifecycle:
    source: str
    owner: str
    supported_harnesses: tuple[str, ...]
    revision_policy: Literal[
        "host-marketplace-current",
        "package-manager-latest",
        "upstream-default-branch",
        "upstream-latest",
    ]
    targets: tuple[SkillTarget, ...]
    install: SkillOperation
    status: SkillOperation
    update: SkillOperation
    removal: SkillOperation
    approval_disclosures: tuple[str, ...] = ()


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
    # Names a hook in installer/postinstall.py's closed POSTINSTALL_HOOKS
    # table -- never a literal shell command -- mirroring this file's own
    # `smoke` param: the registry selects an action by NAME from a closed,
    # code-owned set, so a registry edit alone can never introduce arbitrary
    # post-install execution.
    postinstall: str | None = None
    # Multi-hook post-install list (see POST_INSTALL_ACTIONS above) --
    # distinct from `postinstall` above.
    post_install: tuple[str, ...] = ()
    default_enabled_sensitive_actions: tuple[str, ...] = ()
    # Ownership/skill-lifecycle attribution, dispatched by
    # installer/install_ownership.py and installer/skill_lifecycle.py.
    owner_probes: tuple[str, ...] = ()
    source: str = ""
    owner: str = ""
    uninstall: str = ""
    skill_lifecycle: "SkillLifecycle | None" = None

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
        postinstall: str | None = None,
        post_install: tuple[str, ...] = (),
        default_enabled_sensitive_actions: tuple[str, ...] = (),
        owner_probes: tuple[str, ...] = (),
        source: str = "",
        owner: str = "",
        uninstall: str = "",
        skill_lifecycle: "SkillLifecycle | None" = None,
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
        object.__setattr__(self, "postinstall", postinstall)
        object.__setattr__(self, "post_install", post_install)
        object.__setattr__(
            self, "default_enabled_sensitive_actions", default_enabled_sensitive_actions
        )
        object.__setattr__(self, "owner_probes", owner_probes)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "uninstall", uninstall)
        object.__setattr__(self, "skill_lifecycle", skill_lifecycle)


def _required_skill_string(raw: dict[str, object], field: str, *, tool_id: object) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"tool '{tool_id}': skill_lifecycle '{field}' must be non-empty")
    return value


def _skill_string_tuple(raw: object, *, tool_id: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"tool '{tool_id}': skill_lifecycle '{field}' must be a non-empty list")
    values = cast(list[object], raw)
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle '{field}' must contain non-empty strings"
        )
    return tuple(cast(list[str], values))


def _skill_operation_arg(
    raw: dict[str, object], field: str, *, tool_id: object, operation: str
) -> str:
    if unknown := set(raw).difference({field}):
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle '{operation}' has unknown argument "
            f"'{sorted(unknown)[0]}'"
        )
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle '{operation}.{field}' must be a non-empty string"
        )
    return value


def _parse_skill_operation_args(
    raw: object, *, tool_id: object, operation: str, operation_id: object
) -> SkillOperationArgs:
    if not isinstance(raw, dict):
        raise ValueError(f"tool '{tool_id}': skill_lifecycle '{operation}.args' must be a table")
    args = cast(dict[str, object], raw)
    if operation_id == "codex_plugin_status":
        return CodexPluginStatusArgs(
            plugin=_skill_operation_arg(args, "plugin", tool_id=tool_id, operation=operation)
        )
    if operation_id == "pi_package_status":
        return PiPackageStatusArgs(
            package=_skill_operation_arg(args, "package", tool_id=tool_id, operation=operation)
        )
    raise ValueError(
        f"tool '{tool_id}': skill_lifecycle '{operation}' has unknown operation_id '{operation_id}'"
    )


def _parse_skill_operation(raw: object, *, tool_id: object, operation: str) -> SkillOperation:
    if not isinstance(raw, dict):
        raise ValueError(f"tool '{tool_id}': skill_lifecycle '{operation}' must be declared")
    row = cast(dict[str, object], raw)
    if unknown := set(row).difference({"mode", "operation_id", "args", "instructions"}):
        raise ValueError(f"tool '{tool_id}': unknown {operation} field '{sorted(unknown)[0]}'")
    mode = row.get("mode")
    if mode not in SKILL_OPERATION_MODES:
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle '{operation}' has unknown mode '{mode}'"
        )
    instructions_raw = row.get("instructions", [])
    instructions = (
        _skill_string_tuple(
            instructions_raw,
            tool_id=tool_id,
            field=f"{operation}.instructions",
        )
        if instructions_raw
        else ()
    )
    operation_id = row.get("operation_id")
    args_raw = row.get("args")
    if mode == "manual-required":
        if operation_id is not None or args_raw is not None:
            raise ValueError(
                f"tool '{tool_id}': manual skill_lifecycle '{operation}' "
                "cannot declare an executable operation"
            )
        if not instructions:
            raise ValueError(
                f"tool '{tool_id}': skill_lifecycle '{operation}.instructions' must be non-empty"
            )
        return SkillOperation(mode="manual-required", instructions=instructions)
    if instructions:
        raise ValueError(
            f"tool '{tool_id}': command skill_lifecycle '{operation}' "
            "cannot declare manual instructions"
        )
    if operation != "status":
        raise ValueError(
            f"tool '{tool_id}': no reviewed command operation is available for '{operation}'"
        )
    if operation_id not in SKILL_OPERATION_IDS:
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle '{operation}' has unknown operation_id "
            f"'{operation_id}'"
        )
    args = _parse_skill_operation_args(
        args_raw,
        tool_id=tool_id,
        operation=operation,
        operation_id=operation_id,
    )
    return SkillOperation(
        mode="command",
        operation_id=operation_id,
        args=args,
    )


def _parse_skill_lifecycle(raw: object, *, tool_id: object) -> SkillLifecycle:
    if not isinstance(raw, dict):
        raise ValueError(f"tool '{tool_id}': skill_lifecycle must be declared")
    row = cast(dict[str, object], raw)
    allowed_fields = {
        "source",
        "owner",
        "supported_harnesses",
        "revision_policy",
        "targets",
        "install",
        "status",
        "update",
        "removal",
        "approval_disclosures",
    }
    if unknown := set(row).difference(allowed_fields):
        raise ValueError(f"tool '{tool_id}': unknown skill_lifecycle field '{sorted(unknown)[0]}'")
    source = _required_skill_string(row, "source", tool_id=tool_id)
    if not source.startswith("https://"):
        raise ValueError(f"tool '{tool_id}': skill_lifecycle 'source' must be an HTTPS URL")
    owner = _required_skill_string(row, "owner", tool_id=tool_id)
    supported_harnesses = _skill_string_tuple(
        row.get("supported_harnesses"),
        tool_id=tool_id,
        field="supported_harnesses",
    )
    if unknown := set(supported_harnesses).difference(SKILL_HARNESSES):
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle has unknown harness '{next(iter(unknown))}'"
        )
    revision_policy = row.get("revision_policy")
    if revision_policy not in SKILL_REVISION_POLICIES:
        raise ValueError(
            f"tool '{tool_id}': skill_lifecycle has unknown revision_policy '{revision_policy}'"
        )
    raw_targets = row.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ValueError(f"tool '{tool_id}': skill_lifecycle 'targets' must be a non-empty list")
    targets: list[SkillTarget] = []
    for raw_target in cast(list[object], raw_targets):
        if not isinstance(raw_target, dict):
            raise ValueError(f"tool '{tool_id}': skill_lifecycle target must be a table")
        target = cast(dict[str, object], raw_target)
        if unknown := set(target).difference({"scope", "path"}):
            raise ValueError(f"tool '{tool_id}': unknown target field '{sorted(unknown)[0]}'")
        scope = target.get("scope")
        if scope not in SKILL_TARGET_SCOPES:
            raise ValueError(
                f"tool '{tool_id}': skill_lifecycle has unknown target scope '{scope}'"
            )
        targets.append(
            SkillTarget(
                scope=scope,
                path=_required_skill_string(target, "path", tool_id=tool_id),
            )
        )
    disclosures_raw = row.get("approval_disclosures", [])
    approval_disclosures = (
        _skill_string_tuple(
            disclosures_raw,
            tool_id=tool_id,
            field="approval_disclosures",
        )
        if disclosures_raw
        else ()
    )
    return SkillLifecycle(
        source=source,
        owner=owner,
        supported_harnesses=supported_harnesses,
        revision_policy=revision_policy,
        targets=tuple(targets),
        install=_parse_skill_operation(row.get("install"), tool_id=tool_id, operation="install"),
        status=_parse_skill_operation(row.get("status"), tool_id=tool_id, operation="status"),
        update=_parse_skill_operation(row.get("update"), tool_id=tool_id, operation="update"),
        removal=_parse_skill_operation(row.get("removal"), tool_id=tool_id, operation="removal"),
        approval_disclosures=approval_disclosures,
    )


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
            if kind == "host_setup":
                setup_id = params.get("setup_id")
                if not isinstance(setup_id, str) or setup_id not in HOST_SETUP_IDS:
                    raise ValueError(f"tool '{row['id']}': unknown host setup '{setup_id}'")
            if kind == "skill_pack" and len(entry) != 1:
                raise ValueError(
                    f"tool '{row['id']}': skill_pack method accepts no unreviewed parameters"
                )
            methods.append(Method(kind=kind, params=params, os=os_targets, arch=arch_targets))
        context = f"tool '{row['id']}'"
        requires = _parse_id_list(row.get("requires", []), "requires", context)
        recommends = _parse_id_list(row.get("recommends", []), "recommends", context)
        postinstall = row.get("postinstall")
        if postinstall is not None:
            if not isinstance(postinstall, str) or not postinstall:
                raise ValueError(f"{context}: 'postinstall' must be a non-empty string")
            if postinstall not in POSTINSTALL_HOOK_NAMES:
                known = ", ".join(sorted(POSTINSTALL_HOOK_NAMES))
                raise ValueError(
                    f"{context}: unknown postinstall '{postinstall}' (expected one of: {known})"
                )
        post_install = _parse_closed_string_list(
            row.get("post_install", []),
            tool_id=row["id"],
            field="post_install",
            allowed=POST_INSTALL_ACTIONS,
            label="post-install action",
        )
        default_enabled_sensitive_actions = _parse_closed_string_list(
            row.get("default_enabled_sensitive_actions", []),
            tool_id=row["id"],
            field="default_enabled_sensitive_actions",
            allowed=SENSITIVE_POST_INSTALL_ACTIONS,
            label="sensitive post-install action",
        )
        if undeclared := set(default_enabled_sensitive_actions).difference(post_install):
            raise ValueError(
                f"tool '{row['id']}': default-enabled sensitive action "
                f"'{next(iter(undeclared))}' is not declared in 'post_install'"
            )
        owner_probes = _parse_closed_string_list(
            row.get("owner_probes", []),
            tool_id=row["id"],
            field="owner_probes",
            allowed=OWNER_PROBES,
            label="owner probe",
        )
        has_skill_method = any(method.kind == "skill_pack" for method in methods)
        raw_skill_lifecycle = row.get("skill_lifecycle")
        if raw_skill_lifecycle is not None and not has_skill_method:
            raise ValueError(f"tool '{row['id']}': skill_lifecycle requires a skill_pack method")
        skill_lifecycle = (
            _parse_skill_lifecycle(raw_skill_lifecycle, tool_id=row["id"])
            if has_skill_method
            else None
        )
        if skill_lifecycle is not None and len(methods) != 1:
            raise ValueError(
                f"tool '{row['id']}': skill_pack cannot declare fallback install methods"
            )
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
                postinstall=postinstall,
                post_install=post_install,
                default_enabled_sensitive_actions=default_enabled_sensitive_actions,
                owner_probes=owner_probes,
                source=(
                    skill_lifecycle.source if skill_lifecycle is not None else row.get("source", "")
                ),
                owner=(
                    skill_lifecycle.owner if skill_lifecycle is not None else row.get("owner", "")
                ),
                uninstall=(
                    skill_lifecycle.removal.instructions[-1]
                    if skill_lifecycle is not None
                    else row.get("uninstall", "")
                ),
                skill_lifecycle=skill_lifecycle,
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
