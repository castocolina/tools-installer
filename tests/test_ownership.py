from pathlib import Path

import pytest

from installer.model import Method, Tool
from installer.ownership import (
    MUTATION_GRADE,
    ManagerInventory,
    ManagerOwnership,
    attribute_path,
    owner_dirs,
    parse_brew_list_versions,
    parse_uv_tool_list,
    read_inventory,
    resolve_ownership,
)
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError

_MAC = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
_BREW_PREFIX = Path("/opt/homebrew")
_MANAGED = Path("/home/user/.local/bin")
_PNPM_HOME = Path("/home/user/Library/pnpm")


def _rg() -> Tool:
    return Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(
            Method(kind="github_release", params={"repo": "BurntSushi/ripgrep"}),
            Method(kind="brew", params={"formula": "ripgrep"}),
        ),
    )


def _readable(
    *,
    brew_formulae: dict[str, str] | None = None,
    brew_casks: dict[str, str] | None = None,
    pnpm_globals: frozenset[str] | None = frozenset(),
    uv_tools: dict[str, str] | None = None,
    brew_prefix: Path | None = _BREW_PREFIX,
) -> ManagerInventory:
    return ManagerInventory(
        brew_formulae={} if brew_formulae is None else brew_formulae,
        brew_casks={} if brew_casks is None else brew_casks,
        pnpm_globals=pnpm_globals,
        uv_tools={} if uv_tools is None else uv_tools,
        brew_prefix=brew_prefix,
    )


def _empty_readable() -> ManagerInventory:
    return _readable()


def _resolve(
    tool: Tool,
    *,
    inventory: ManagerInventory,
    artifacts: list[Path] | None = None,
    which: str | None = None,
    managed_bin_dir: Path = _MANAGED,
    platform: Platform = _MAC,
) -> ManagerOwnership:
    def lookup(_cmd: str) -> str | None:
        return which

    return resolve_ownership(
        tool,
        platform=platform,
        inventory=inventory,
        artifacts=artifacts or (),
        which=lookup,
        managed_bin_dir=managed_bin_dir,
    )


def test_rg_brew_owned_even_when_github_release_outranks() -> None:
    tool = _rg()
    assert resolve_methods(tool, _MAC)[0].kind == "github_release"
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={"ripgrep": "14.1.0"}),
        artifacts=[],
        which="/opt/homebrew/bin/rg",
    )
    assert result.owner == "brew"
    assert result.package == "ripgrep"
    assert result.confidence == "direct"
    assert result.active_candidate == "brew"


def test_rg_installer_owned_when_active_path_is_managed_bin() -> None:
    result = _resolve(
        _rg(),
        inventory=_readable(brew_formulae={"ripgrep": "14.1.0"}),
        artifacts=[_MANAGED / "rg"],
        which=str(_MANAGED / "rg"),
    )
    assert result.owner == "installer"
    assert result.shadowed is True
    assert result.active_candidate == "installer"
    assert result.confidence == "direct"


def test_rg_brew_owned_when_active_path_is_homebrew_even_with_artifacts() -> None:
    result = _resolve(
        _rg(),
        inventory=_readable(brew_formulae={"ripgrep": "14.1.0"}),
        artifacts=[_MANAGED / "rg"],
        which="/opt/homebrew/bin/rg",
    )
    assert result.owner == "brew"
    assert result.shadowed is True
    assert result.active_candidate == "brew"


@pytest.mark.parametrize(
    "inventory",
    [
        ManagerInventory(
            brew_formulae=None,
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=None,
        ),
        ManagerInventory(
            brew_formulae=None,
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=_BREW_PREFIX,
        ),
    ],
)
def test_stale_artifact_plus_unreadable_brew_is_unknown(inventory: ManagerInventory) -> None:
    """This is the input to a no-confirmation mutation: a guess here installs
    over a live Homebrew copy."""
    result = _resolve(
        _rg(),
        inventory=inventory,
        artifacts=[_MANAGED / "rg"],
        which="/opt/homebrew/bin/rg",
    )
    assert result.owner == "unknown"
    assert result.confidence == "none"
    assert result.unknown_reason
    assert "brew" in result.unknown_reason.lower()


def test_complete_negative_evidence_direct_when_path_is_managed() -> None:
    result = _resolve(
        _rg(),
        inventory=_empty_readable(),
        artifacts=[_MANAGED / "rg"],
        which=str(_MANAGED / "rg"),
    )
    assert result.owner == "installer"
    assert result.confidence == "direct"


def test_complete_negative_evidence_by_elimination_when_nothing_on_path() -> None:
    result = _resolve(
        _rg(),
        inventory=_empty_readable(),
        artifacts=[_MANAGED / "rg"],
        which=None,
    )
    assert result.owner == "installer"
    assert result.confidence == "by-elimination"
    assert result.active_path is None


def test_unattributable_active_binary_is_unknown() -> None:
    result = _resolve(
        _rg(),
        inventory=_empty_readable(),
        artifacts=[_MANAGED / "rg"],
        which="/usr/bin/rg",
    )
    assert result.owner == "unknown"
    assert result.confidence == "none"
    assert result.unknown_reason
    assert "/usr/bin/rg" in result.unknown_reason


def test_cask_gui_tool_reports_current_version_with_no_path() -> None:
    tool = Tool(
        id="rectangle",
        name="Rectangle",
        category="dev",
        cmd="rectangle",
        methods=(Method(kind="cask", params={"cask": "rectangle"}),),
    )
    result = _resolve(
        tool,
        inventory=_readable(brew_casks={"rectangle": "0.85"}),
        which=None,
    )
    assert result.owner == "cask"
    assert result.confidence == "by-elimination"
    assert result.current_version == "0.85"


def test_pnpm_owned_when_active_path_is_in_pnpm_bin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PNPM_HOME", str(_PNPM_HOME))
    tool = Tool(
        id="mmdc",
        name="mmdc",
        category="diagram",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )
    result = _resolve(
        tool,
        inventory=_readable(pnpm_globals=frozenset({"@mermaid-js/mermaid-cli"})),
        which=str(_PNPM_HOME / "mmdc"),
    )
    assert result.owner == "pnpm"
    assert result.confidence == "direct"


def test_shadowed_pnpm_does_not_win_when_active_path_is_brew(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PNPM_HOME", str(_PNPM_HOME))
    tool = Tool(
        id="mmdc",
        name="mmdc",
        category="diagram",
        cmd="mmdc",
        methods=(
            Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),
            Method(kind="brew", params={"formula": "mermaid-cli"}),
        ),
    )
    claimed = _resolve(
        tool,
        inventory=_readable(
            brew_formulae={"mermaid-cli": "11.0.0"},
            pnpm_globals=frozenset({"@mermaid-js/mermaid-cli"}),
        ),
        which="/opt/homebrew/bin/mmdc",
    )
    assert claimed.owner == "brew"
    unclaimed = _resolve(
        tool,
        inventory=_readable(pnpm_globals=frozenset({"@mermaid-js/mermaid-cli"})),
        which="/opt/homebrew/bin/mmdc",
    )
    assert unclaimed.owner == "unknown"


def test_uv_owned_when_bin_dir_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    uv_bin = Path("/opt/uv/bin")
    monkeypatch.setenv("UV_TOOL_BIN_DIR", str(uv_bin))
    tool = Tool(
        id="ruff",
        name="ruff",
        category="dev",
        cmd="ruff",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "ruff"}),),
    )
    result = _resolve(
        tool,
        inventory=_readable(uv_tools={"ruff": "0.6.0"}),
        which=str(uv_bin / "ruff"),
    )
    assert result.owner == "uv"
    assert result.confidence == "direct"


def test_uv_owned_by_elimination_when_default_bin_collides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)
    tool = Tool(
        id="ruff",
        name="ruff",
        category="dev",
        cmd="ruff",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "ruff"}),),
    )
    result = _resolve(
        tool,
        inventory=_readable(uv_tools={"ruff": "0.6.0"}),
        artifacts=[],
        which=None,
        managed_bin_dir=Path.home() / ".local" / "bin",
    )
    assert result.owner == "uv"
    assert result.confidence == "by-elimination"


def _pretend_installed(_tool: Tool) -> bool:
    return True


def test_script_only_installed_tool_is_installer_by_elimination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("installer.ownership.is_installed", _pretend_installed)
    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),),
    )
    result = _resolve(tool, inventory=_empty_readable(), which=None)
    assert result.owner == "installer"
    assert result.confidence == "by-elimination"


def test_script_only_with_unreadable_brew_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("installer.ownership.is_installed", _pretend_installed)
    tool = Tool(
        id="pnpm",
        name="pnpm",
        category="pkg-mgr",
        cmd="pnpm",
        methods=(
            Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),
            Method(kind="brew", params={"formula": "pnpm"}),
        ),
    )
    result = _resolve(
        tool,
        inventory=ManagerInventory(
            brew_formulae=None,
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=_BREW_PREFIX,
        ),
        which=None,
    )
    assert result.owner == "unknown"
    assert result.unknown_reason
    assert "brew" in result.unknown_reason.lower()


def test_mutation_grade_is_exactly_direct_and_by_elimination() -> None:
    assert frozenset({"direct", "by-elimination"}) == MUTATION_GRADE


@pytest.mark.parametrize("kind", ["dnf", "apt", "pacman", "rpm_ostree"])
def test_linux_system_package_manager_is_unknown_by_design(kind: str) -> None:
    """Deliberate Phase 12 scope boundary, not a defect: it renders unknown
    and Plan 12-03 refuses to update it."""
    linux = Platform(os="linux", arch="amd64", immutable=False, has_brew=False)
    if kind == "dnf":
        linux = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    elif kind == "apt":
        linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    elif kind == "pacman":
        linux = Platform(os="arch", arch="amd64", immutable=False, has_brew=False)
    elif kind == "rpm_ostree":
        linux = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    tool = Tool(
        id="jq",
        name="jq",
        category="data",
        cmd="jq",
        methods=(Method(kind=kind, params={"package": "jq"}),),
    )
    result = _resolve(tool, inventory=_empty_readable(), which=None, platform=linux)
    assert result.owner == "unknown"
    assert result.confidence == "none"
    assert result.method is None
    assert result.unknown_reason


def test_parse_brew_list_versions_takes_last_token() -> None:
    raw = "ack 3.10.0\nactionlint 1.7.12\nfoo 1.0 1.1\n"
    assert parse_brew_list_versions(raw) == {
        "ack": "3.10.0",
        "actionlint": "1.7.12",
        "foo": "1.1",
    }


def test_parse_brew_list_versions_accepts_literal_latest() -> None:
    assert parse_brew_list_versions("font-source-code-pro latest\n") == {
        "font-source-code-pro": "latest"
    }


def test_parse_brew_list_versions_empty_is_empty_map() -> None:
    assert parse_brew_list_versions("") == {}


def test_parse_brew_list_versions_malformed_line_is_none() -> None:
    assert parse_brew_list_versions("ack\n") is None


def test_parse_uv_tool_list_skips_indented_entry_points() -> None:
    raw = "graphifyy v0.9.53\n- graphify\n- graphify-mcp\npre-commit v4.6.0\n- pre-commit\n"
    assert parse_uv_tool_list(raw) == {"graphifyy": "0.9.53", "pre-commit": "4.6.0"}


def test_parse_uv_tool_list_empty_is_empty_map() -> None:
    assert parse_uv_tool_list("") == {}


def test_parse_uv_tool_list_unrecognized_line_is_none() -> None:
    raw = "warning: something changed\ngraphifyy v0.9.53\n- graphify\n"
    assert parse_uv_tool_list(raw) is None


def test_read_inventory_isolates_brew_failure() -> None:
    def query(cmd: list[str], **_kwargs: object) -> str:
        if cmd and cmd[0] == "brew":
            raise CommandError(cmd, 1, detail="no brew")
        if cmd[:3] == ["uv", "tool", "list"]:
            return "ruff v0.6.0\n"
        raise AssertionError(cmd)

    inventory = read_inventory(
        has_brew=True,
        query=query,
        pnpm_packages=lambda: ("vercel",),
    )
    assert inventory.brew_formulae is None
    assert inventory.brew_casks is None
    assert inventory.brew_prefix is None
    assert inventory.uv_tools == {"ruff": "0.6.0"}
    assert inventory.pnpm_globals == frozenset({"vercel"})


def test_read_inventory_malformed_brew_output_is_unreadable() -> None:
    def query(cmd: list[str], **_kwargs: object) -> str:
        if cmd == ["brew", "--prefix"]:
            return "/opt/homebrew\n"
        if cmd == ["brew", "list", "--versions", "--formula"]:
            return "ack\n"
        if cmd == ["brew", "list", "--versions", "--cask"]:
            return ""
        if cmd[:3] == ["uv", "tool", "list"]:
            return ""
        raise AssertionError(cmd)

    inventory = read_inventory(
        has_brew=True,
        query=query,
        pnpm_packages=lambda: (),
    )
    assert inventory.brew_formulae is None
    assert inventory.brew_casks == {}


def test_read_inventory_query_count_with_brew() -> None:
    queries: list[list[str]] = []
    pnpm_calls = {"n": 0}

    def query(cmd: list[str], **_kwargs: object) -> str:
        queries.append(cmd)
        if cmd == ["brew", "--prefix"]:
            return "/opt/homebrew\n"
        return ""

    def pnpm_packages() -> tuple[str, ...] | None:
        pnpm_calls["n"] += 1
        return ()

    read_inventory(has_brew=True, query=query, pnpm_packages=pnpm_packages)
    assert len(queries) == 4
    assert queries[0] == ["brew", "--prefix"]
    assert ["brew", "list", "--versions", "--formula"] in queries
    assert ["brew", "list", "--versions", "--cask"] in queries
    assert ["uv", "tool", "list"] in queries
    assert pnpm_calls["n"] == 1


def test_read_inventory_query_count_without_brew() -> None:
    queries: list[list[str]] = []
    pnpm_calls = {"n": 0}

    def query(cmd: list[str], **_kwargs: object) -> str:
        queries.append(cmd)
        return ""

    def pnpm_packages() -> tuple[str, ...] | None:
        pnpm_calls["n"] += 1
        return ()

    read_inventory(has_brew=False, query=query, pnpm_packages=pnpm_packages)
    assert queries == [["uv", "tool", "list"]]
    assert pnpm_calls["n"] == 1


def test_attribute_path_unit_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PNPM_HOME", str(_PNPM_HOME))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)
    inventory = _readable()
    dirs = owner_dirs(inventory=inventory, managed_bin_dir=_MANAGED, platform=_MAC)
    assert attribute_path(_BREW_PREFIX / "bin" / "rg", dirs) == frozenset({"brew", "cask"})
    colliding = owner_dirs(
        inventory=inventory,
        managed_bin_dir=Path.home() / ".local" / "bin",
        platform=_MAC,
    )
    managed = Path.home() / ".local" / "bin" / "ruff"
    assert attribute_path(managed, colliding) == frozenset({"installer", "uv"})
    assert attribute_path(_PNPM_HOME / "mmdc", dirs) == frozenset({"pnpm"})
    assert attribute_path(Path("/usr/bin/rg"), dirs) == frozenset()
    assert attribute_path(None, dirs) == frozenset()


def test_cask_installed_app_never_wins_installer_direct_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2 regression (codex-sol-high, 12-REVIEW.md): a tool declaring both an
    `app` method and a `cask` method, actually installed via Homebrew cask
    into `~/Applications` (the app-kind method was never used), must never
    resolve to owner="installer" with confidence="direct" — Homebrew casks
    install into the same `~/Applications` directory this installer's own
    `app` method uses, so directory membership alone cannot prove either one.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    bundle = tmp_path / "Applications" / "Visual Studio Code.app"
    cli = bundle / "Contents" / "Resources" / "app" / "bin" / "code"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/bin/sh\n")
    tool = Tool(
        id="vscode",
        name="Visual Studio Code",
        category="editor",
        cmd="code",
        methods=(
            Method(kind="app", params={"app": "Visual Studio Code.app", "cli": str(cli)}),
            Method(kind="cask", params={"cask": "visual-studio-code"}),
        ),
    )
    result = _resolve(
        tool,
        inventory=_readable(brew_casks={"visual-studio-code": "1.90.0"}),
        artifacts=[bundle],
        which=str(cli),
    )
    assert not (result.owner == "installer" and result.confidence == "direct")
    assert result.owner in ("cask", "unknown")


def test_parse_brew_list_versions_warning_line_fails_closed() -> None:
    """C1 regression: a warning line has 2+ whitespace tokens but is not a
    genuine `name version` pair — the whole parse must fail closed."""
    assert parse_brew_list_versions("warning: inventory format changed\n") is None


def test_parse_uv_tool_list_entrypoint_without_preceding_match_fails_closed() -> None:
    """C1 regression: an entry-point-shaped line with no preceding matched
    `name vX.Y` line has no context to belong to and must not be skipped."""
    assert parse_uv_tool_list("- graphify\n") is None


def test_abandoned_drift_helpers_are_absent() -> None:
    """Phase 12 deferred REQ-manager-drift-alerting rather than shipping a
    zero-caller helper (12-REVIEWS.md architecture-rule-5 finding).

    The abandoned 12-04 design proposed `has_declared_manager_drift` and
    `manager_drift_alert`. This test pins those two identifiers as absent
    from the two modules they would have lived in. It does NOT ban the
    substring `drift` generally: a future correctly-wired implementation
    is free to use whatever name fits it (12-REVIEWS.md:486-490). Dead-code
    detection in general is already `make validate`'s job (vulture), and
    the no-orphan-helper rule is already written in `.claude/architecture.md`.
    """
    import installer.manager_versions as manager_versions
    import installer.ownership as ownership

    for name in ("has_declared_manager_drift", "manager_drift_alert"):
        assert not hasattr(manager_versions, name)
        assert not hasattr(ownership, name)
