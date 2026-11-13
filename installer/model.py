"""Declarative tool catalog: Tool/Method model, category blurbs, and tomllib loaders."""

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
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
POSTINSTALL_HOOK_NAMES: frozenset[str] = frozenset(
    {"codegraph-mcp-register", "herdr-integration", "tealdeer-cache"}
)

METHOD_KINDS = (
    "script",
    "node",
    "uv-tool",
    "sdkman",
    "host_setup",
    "github_release",
    "tarball",
    "app",
    "cargo_distrobox",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
    "cask",
)

# Later phases extend a kind's keys by editing its entry (Phases 22 and 24).
METHOD_PARAMS: dict[str, frozenset[str]] = {
    "script": frozenset(
        {
            "url",
            "shell",
            "bin_dir",
            "env",
            "detect_path",
            "version_file",
            "args",
            "smoke_argv",
            "refuses_existing",
            "paths",
            "remove",
            "update",
            "writable_prefix",
        }
    ),
    "node": frozenset(
        {"npm_pkg", "co_install", "allow_build", "min_node", "smoke", "versions", "smoke_argv"}
    ),
    "uv-tool": frozenset({"pypi_pkg", "smoke_argv"}),
    "sdkman": frozenset({"candidate", "bin_dir", "version", "smoke_argv"}),
    "host_setup": frozenset({"setup_id"}),
    "github_release": frozenset(
        {
            "repo",
            "asset",
            "checksum",
            "member",
            "strip",
            "raw",
            "archive",
            "bin_name",
            "bin_dir",
            "smoke_argv",
        }
    ),
    "tarball": frozenset(
        {
            "url",
            "member",
            "strip",
            "bin_name",
            "archive",
            "bin_dir",
            "version",
            "sha256",
            "smoke_argv",
        }
    ),
    "app": frozenset({"url", "app", "cli", "cli_name", "version", "sha256", "smoke_argv"}),
    # A source build in a throwaway Distrobox: `repo` is the GitHub slug (version source and
    # clone URL), `artifacts` the {box, host} files it places.
    "cargo_distrobox": frozenset({"repo", "image", "packages", "artifacts", "smoke_argv"}),
    "dnf": frozenset({"package", "smoke_argv"}),
    "apt": frozenset({"package", "smoke_argv"}),
    "pacman": frozenset({"package", "smoke_argv"}),
    "rpm_ostree": frozenset({"package"}),
    "brew": frozenset({"formula", "detect_path", "min_os_version", "bin_dir", "smoke_argv"}),
    "cask": frozenset({"cask", "app", "min_os_version", "smoke_argv"}),
}
# The param that names a manager method's package, by kind (the one reader is method_package).
KIND_PACKAGE_PARAM: dict[str, str] = {
    "brew": "formula",
    "cask": "cask",
    "node": "npm_pkg",
    "uv-tool": "pypi_pkg",
    "sdkman": "candidate",
    "dnf": "package",
    "apt": "package",
    "pacman": "package",
    "rpm_ostree": "package",
}


# Named roots a script token may use as `{name}`, resolved in Python at run time, never by a shell.
SCRIPT_ROOTS: frozenset[str] = frozenset({"omz_root"})

# Multi-hook post-install action names. Distinct from `Tool.postinstall` above:
# `postinstall` selects a single hook from POSTINSTALL_HOOK_NAMES by name for a
# package-owned side effect (e.g. registering an MCP server); `post_install`
# lists zero or more of these reviewed shell/environment actions run once per
# tool.
POST_INSTALL_ACTIONS = (
    "configure_path",
    "set_login_shell",
    "source_shell_init",
    "set_omz_theme",
    "set_omz_plugins",
    "show_lean_tips",
    "apply_agent_tuning",
    "apply_terminal_tuning",
)
# Empty since 23.2 D-13: no action asks. The loader field `default_enabled_sensitive_actions`
# stays (D-14) and now rejects any value; Phase 24.1 decides its fate.
SENSITIVE_POST_INSTALL_ACTIONS: tuple[str, ...] = ()
OWNER_PROBES = (
    "host-setup",
    "brew",
    "apt",
    "dnf",
    "pacman",
    "rpm-ostree",
    "pnpm",
    "sdkman",
)
# Harness marker dirs (home-relative): read by the config_paths validator and by
# postinstall.HARNESS_PRESENCE, so one denylist governs both.
HARNESS_MARKER_DIRS: dict[str, tuple[str, ...]] = {
    "antigravity": (".gemini/antigravity",),
    "claude": (".claude",),
    "codex": (".codex",),
    "copilot": (".copilot",),
    "cursor": (".cursor", ".local/share/cursor-agent"),
    "devin": (),
    "factory-droid": (".factory",),
    "gemini-cli": (".gemini",),
    "grok": (),
    "hermes": (),
    "kilo": (".config/kilo",),
    "kimi": (".kimi-code",),
    "muse": (),
    "opencode": (".config/opencode", ".opencode"),
    "pi": (".pi",),
    "qwen": (),
    "windsurf": (".codeium/windsurf",),
}
_SCRIPT_ARG_RE = re.compile(r"^[A-Za-z0-9=._:/+-]+$")
_SCRIPT_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
_WRITABLE_PREFIX_RE = re.compile(r"^/[A-Za-z0-9._/-]+$")
_PINNED_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# cargo_distrobox: a GitHub owner/name slug, a registry-qualified image with a tag or digest,
# and a distro package name; none may start with a dash (each becomes an argv word).
_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_IMAGE_REF_RE = re.compile(
    r"^(?P<host>[A-Za-z0-9][A-Za-z0-9.-]*(?::\d+)?)/[A-Za-z0-9._/-]+"
    r"(?::[A-Za-z0-9._-]+|@sha256:[0-9a-f]{64})$"
)
_DISTRO_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]*$")
_CARGO_HOST_ROOTS = ("~/.local/", "~/.config/", "~/.terminfo/")
# A tool id names its receipt file, so it can never hold `/`, `..` or a leading `-`.
TOOL_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")

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


def method_package(method: Method) -> str | None:
    """The manager package name a method declares, or None: the one reader."""
    param = KIND_PACKAGE_PARAM.get(method.kind)
    value = method.params.get(param) if param is not None else None
    return value if isinstance(value, str) and value else None


ConfigStepKind = Literal[
    "terminal_sync",
    "pnpm_group_install",
    "hook_register",
    "zshenv_shell",
    "install_tuning",
]


@dataclass(frozen=True)
class ConfigStep:
    """One D-20 configuration step: the text shown after "to configure:" and the
    kind of fix Phase 20 RECONFIGURE runs for it; each kind has its own branch in
    `session._run_step`, and no step carries a command of its own."""

    text: str
    kind: ConfigStepKind
    # The text a successful terminal_sync step reports (its done note); a zshenv_shell
    # step's is "<zsh path>\n<the .zshenv it writes>". Empty for every other kind.
    report: str = ""


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
    # Ownership attribution, dispatched by installer/install_ownership.py.
    owner_probes: tuple[str, ...] = ()
    # Declared `~/` config paths, validated by _parse_config_paths at load.
    config_paths: tuple[str, ...] = ()
    # Synthetic tool for a receipt whose id left the catalog (receipts.scan_retired).
    retired: bool = False

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
        config_paths: tuple[str, ...] = (),
        retired: bool = False,
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
        object.__setattr__(self, "config_paths", config_paths)
        object.__setattr__(self, "retired", retired)


def _relative_parts(rest: str) -> tuple[str, ...] | None:
    """Split a home-relative path; None when a part is empty, `.`, `..` or holds a NUL."""
    parts = tuple(rest.split("/"))
    if any(part in ("", ".", "..") or "\x00" in part for part in parts):
        return None
    return parts


# Directories every tool shares (review C-09): a config entry may sit under one, never be one.
_SHARED_CONFIG_DIRS = frozenset(
    {
        (".local", "bin"),
        (".local", "share"),
        (".local", "state"),
        (".config", "systemd"),
        (".config", "autostart"),
    }
)
# Never config at all: executables and keys.
_NO_CONFIG_UNDER = ((".local", "bin"), (".ssh",), (".gnupg",))


def _config_path_flaw(entry: str, markers: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
    if not entry.startswith("~/"):
        return "must start with ~/"
    parts = _relative_parts(entry[2:])
    if parts is None:
        return "must not contain empty, . or .. parts"
    if len(parts) < 2:
        return "must be at least two levels under ~"
    if parts in _SHARED_CONFIG_DIRS or (len(parts) == 2 and parts[0] == "Library"):
        return "is a directory other tools share"
    for root in _NO_CONFIG_UNDER:
        if parts[: len(root)] == root:
            return f"is inside ~/{'/'.join(root)}, which holds no config"
    for marker, marker_parts in markers:
        if parts[: len(marker_parts)] == marker_parts:
            return f"is inside the harness directory ~/{marker}"
        if marker_parts[: len(parts)] == parts:
            return f"contains the harness directory ~/{marker}"
    return None


def _parse_config_paths(raw: object, *, tool_id: object) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(
        isinstance(item, str) for item in cast(list[object], raw)
    ):
        raise ValueError(f"tool '{tool_id}': config_paths must be a list of strings")
    entries = cast(list[str], raw)
    markers = tuple(
        (marker, tuple(marker.split("/")))
        for group in HARNESS_MARKER_DIRS.values()
        for marker in group
    )
    for entry in entries:
        if (why := _config_path_flaw(entry, markers)) is not None:
            raise ValueError(f"tool '{tool_id}': config_paths entry '{entry}' {why}")
    return tuple(entries)


def _refuse_config_overlap(tools: list[Tool]) -> None:
    """Refuse a config entry that is an ancestor of another tool's entry (equal is fine)."""
    owned = [
        (tool.id, entry, _relative_parts(entry[2:]) or ())
        for tool in tools
        for entry in tool.config_paths
    ]
    for a_id, a_entry, a_parts in owned:
        for b_id, b_entry, b_parts in owned:
            if a_id != b_id and a_parts != b_parts and b_parts[: len(a_parts)] == a_parts:
                raise ValueError(
                    f"tool '{a_id}': config_paths entry '{a_entry}' "
                    f"overlaps '{b_entry}' of tool '{b_id}'"
                )


def _script_token_ok(token: str) -> str | None:
    """Why a script token is refused (unknown placeholder or non-literal), else None."""
    for name in _SCRIPT_PLACEHOLDER_RE.findall(token):
        if name not in SCRIPT_ROOTS:
            return f"names unknown placeholder '{{{name}}}'"
    plain = _SCRIPT_PLACEHOLDER_RE.sub("x", token).removeprefix("~")
    if _SCRIPT_ARG_RE.fullmatch(plain) is None:
        return f"token '{token}' is not a literal argv element"
    return None


def _cargo_distrobox_refusal(params: dict[str, object]) -> str | None:
    """Why a cargo_distrobox method's params are refused (naming the key), else None."""
    repo = params.get("repo")
    if not isinstance(repo, str) or _REPO_SLUG_RE.fullmatch(repo) is None:
        return "key 'repo' must be a GitHub owner/name slug"
    image = params.get("image")
    match = _IMAGE_REF_RE.fullmatch(image) if isinstance(image, str) else None
    # A registry host part names a dot (a domain) or a port; a bare first word is a user name.
    qualified = match is not None and (
        any(char in match["host"] for char in ".:") or match["host"] == "localhost"
    )
    if not qualified:
        return "key 'image' must be a fully qualified reference (registry/name:tag)"
    if "packages" in params:
        packages = params["packages"]
        if not isinstance(packages, list) or not all(
            isinstance(item, str) and _DISTRO_PACKAGE_RE.fullmatch(item) is not None
            for item in cast(list[object], packages)
        ):
            return (
                "key 'packages' must be a list of package names "
                "matching ^[A-Za-z0-9][A-Za-z0-9.+_-]*$"
            )
    artifacts = params.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return "key 'artifacts' must be a non-empty list of {box, host} tables"
    hosts: list[str] = []
    for entry in cast(list[object], artifacts):
        if not isinstance(entry, dict) or set(cast(dict[str, object], entry)) != {"box", "host"}:
            return "key 'artifacts' entries must be tables with exactly 'box' and 'host'"
        box, host = cast(dict[str, object], entry)["box"], cast(dict[str, object], entry)["host"]
        if not isinstance(box, str) or not isinstance(host, str):
            return "key 'artifacts' entries must be tables with exactly 'box' and 'host'"
        if any(ord(char) < 32 or ord(char) == 127 for char in box + host):
            return "key 'artifacts' paths must not hold control characters"
        if box.startswith("/") or _relative_parts(box) is None:
            return f"key 'artifacts' box '{box}' must be relative with no empty, . or .. part"
        if not host.startswith(_CARGO_HOST_ROOTS) or _relative_parts(host[2:]) is None:
            return (
                f"key 'artifacts' host '{host}' must sit under ~/.local, ~/.config or ~/.terminfo "
                "with no empty, . or .. part"
            )
        hosts.append(host)
    if not hosts[0].startswith("~/.local/bin/"):
        return "key 'artifacts' first host (the binary) must sit under ~/.local/bin/"
    if len(set(hosts)) != len(hosts):
        return "key 'artifacts' hosts must be distinct"
    return None


def _is_argv(raw: object, token_ok: Callable[[str], bool]) -> bool:
    """A non-empty list of strings, each accepted by token_ok."""
    if not isinstance(raw, list) or not raw:
        return False
    return all(isinstance(item, str) and token_ok(item) for item in cast(list[object], raw))


# A registry argv must never start a run with one of these (SPEC R3, review C-08).
ELEVATION_COMMANDS = frozenset({"sudo", "pkexec", "doas"})


def _elevation_head(raw: object) -> str | None:
    """The argv's first word when it (or its basename) is an elevation command, else None."""
    if not isinstance(raw, list) or not raw:
        return None
    head = cast(list[object], raw)[0]
    return head if isinstance(head, str) and head.rsplit("/", 1)[-1] in ELEVATION_COMMANDS else None


def _script_refusal(raw: object) -> str:
    """Name the first refused token of a script argv value, else the shape it must have."""
    if (head := _elevation_head(raw)) is not None:
        return f"starts with the elevation command '{head}'"
    if isinstance(raw, list):
        for token in cast(list[object], raw):
            if isinstance(token, str) and (why := _script_token_ok(token)) is not None:
                return why
    return "must be a non-empty list of strings"


def _script_paths_refusal(raw: object) -> str | None:
    """Why a script `paths` value is refused; None when every entry stays under HOME or a root."""
    if not _is_argv(raw, lambda _token: True):
        return "must be a non-empty list of strings"
    roots = {f"{{{root}}}" for root in SCRIPT_ROOTS}
    for entry in cast(list[str], raw):
        head, sep, rest = entry.partition("/")
        if sep != "/" or (head != "~" and head not in roots):
            return f"entry '{entry}' must start with ~/ or a named root followed by /"
        if (why := _script_token_ok(entry)) is not None:
            return why
        if _relative_parts(rest.removesuffix("/")) is None:
            return f"entry '{entry}' must not contain empty, . or .. parts"
    return None


def load_tools(manifest_path: str | Path, *, today: date | None = None) -> list[Tool]:
    """Parse the registry TOML into validated Tool objects."""
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    tools: list[Tool] = []
    for row in data.get("tool", []):
        tool_id = row.get("id")
        if not isinstance(tool_id, str) or TOOL_ID_RE.fullmatch(tool_id) is None:
            raise ValueError(
                f"tool '{tool_id}': id must match [a-z0-9][a-z0-9._-]* (it names the receipt file)"
            )
        if "skill_lifecycle" in row:
            raise ValueError(
                f"tool '{tool_id}': skill_lifecycle was retired in 23.1; "
                "remove the [tool.skill_lifecycle] table"
            )
        raw_methods = row.get("method", [])
        if not raw_methods:
            raise ValueError(f"tool '{row['id']}' declares no install methods")
        _parse_enum(Category, row["category"], "category", f"tool '{row['id']}'")
        if "tier" not in row:
            raise ValueError(f"tool '{row['id']}': missing required 'tier'")
        verified = row.get("verified")
        if verified is None:
            raise ValueError(
                f"tool '{row['id']}': missing required 'verified' (a TOML date, YYYY-MM-DD)"
            )
        if type(verified) is not date:
            raise ValueError(f"tool '{row['id']}': 'verified' must be a TOML date (YYYY-MM-DD)")
        limit = (today or date.today()) + timedelta(days=1)
        if verified > limit:
            raise ValueError(f"tool '{row['id']}': 'verified' {verified} is in the future")
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
            unknown = set(params) - METHOD_PARAMS[kind]
            if unknown:
                key = sorted(unknown)[0]
                raise ValueError(f"tool '{row['id']}': method '{kind}' has unknown key '{key}'")
            if "refuses_existing" in params and type(params["refuses_existing"]) is not bool:
                raise ValueError(
                    f"tool '{row['id']}': method '{kind}' key 'refuses_existing' "
                    "must be true or false"
                )
            if kind in ("app", "tarball"):
                url = params.get("url")
                pinned = isinstance(url, str) and "{ver}" in url
                if pinned:
                    version = params.get("version")
                    if not isinstance(version, str) or not version:
                        raise ValueError(
                            f"tool '{row['id']}': pinned {kind} url needs a non-empty 'version'"
                        )
                    sha256 = params.get("sha256")
                    if not isinstance(sha256, str) or _PINNED_SHA256_RE.fullmatch(sha256) is None:
                        raise ValueError(
                            f"tool '{row['id']}': pinned {kind} url needs "
                            "'sha256' as 64 lowercase hex"
                        )
                else:
                    for key in ("version", "sha256"):
                        if key in params:
                            raise ValueError(
                                f"tool '{row['id']}': '{key}' needs a url templated with {{ver}}"
                            )
            if "strip" in params:
                strip = params["strip"]
                if params.get("archive") == "zip" or params.get("raw") is True:
                    raise ValueError(
                        f"tool '{row['id']}': 'strip' does not apply to a zip archive "
                        "or a raw asset"
                    )
                if isinstance(strip, bool) or not isinstance(strip, int) or strip < 0:
                    raise ValueError(f"tool '{row['id']}': 'strip' must be a non-negative integer")
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
            if kind == "script" and "args" in params:
                args = params["args"]
                if not isinstance(args, list):
                    raise ValueError(
                        f"tool '{row['id']}': script 'args' must be a list of strings "
                        "matching ^[A-Za-z0-9=._:/+-]+$"
                    )
                items = cast(list[object], args)
                if not all(isinstance(item, str) for item in items) or any(
                    _SCRIPT_ARG_RE.fullmatch(item) is None for item in cast(list[str], items)
                ):
                    raise ValueError(
                        f"tool '{row['id']}': script 'args' must be a list of strings "
                        "matching ^[A-Za-z0-9=._:/+-]+$"
                    )
            if "smoke_argv" in params and not _is_argv(
                params["smoke_argv"], lambda token: _SCRIPT_ARG_RE.fullmatch(token) is not None
            ):
                raise ValueError(
                    f"tool '{row['id']}': 'smoke_argv' must be a non-empty list of strings "
                    "matching ^[A-Za-z0-9=._:/+-]+$"
                )
            if kind == "script":
                for key in ("remove", "update"):
                    if key in params and (
                        not _is_argv(params[key], lambda token: _script_token_ok(token) is None)
                        or _elevation_head(params[key]) is not None
                    ):
                        raise ValueError(
                            f"tool '{row['id']}': method 'script' key '{key}' "
                            f"{_script_refusal(params[key])}"
                        )
                if "paths" in params and (why := _script_paths_refusal(params["paths"])):
                    raise ValueError(f"tool '{row['id']}': method 'script' key 'paths' {why}")
                if "writable_prefix" in params and not (
                    isinstance(params["writable_prefix"], str)
                    and _WRITABLE_PREFIX_RE.fullmatch(params["writable_prefix"])
                    and _relative_parts(params["writable_prefix"][1:]) is not None
                ):
                    raise ValueError(
                        f"tool '{row['id']}': method 'script' key 'writable_prefix' "
                        "must be an absolute path without . or .. parts"
                    )
            if kind == "cargo_distrobox" and (why := _cargo_distrobox_refusal(params)):
                raise ValueError(f"tool '{row['id']}': method 'cargo_distrobox' {why}")
            if kind == "host_setup":
                setup_id = params.get("setup_id")
                if not isinstance(setup_id, str) or setup_id not in HOST_SETUP_IDS:
                    raise ValueError(f"tool '{row['id']}': unknown host setup '{setup_id}'")
            methods.append(Method(kind=kind, params=params, os=os_targets, arch=arch_targets))
        context = f"tool '{row['id']}'"
        requires = _parse_id_list(row.get("requires", []), "requires", context)
        config_paths = _parse_config_paths(row.get("config_paths", []), tool_id=row["id"])
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
                config_paths=config_paths,
            )
        )
    _refuse_config_overlap(tools)
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
