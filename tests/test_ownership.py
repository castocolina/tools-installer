import subprocess
import typing
from collections.abc import Callable
from dataclasses import replace
from itertools import product
from pathlib import Path

import pytest

import installer.install_ownership as install_ownership
import installer.ownership as ownership
import installer.resolve as resolve
from installer.model import Method, Tool, load_tools
from installer.ownership import (
    DETAIL_PHRASE_COLLISIONS,
    MUTATION_GRADE,
    NATIVE_OWNERS,
    OS_PACKAGE_OWNER,
    OWNER_DETAIL_LABELS,
    OWNER_LABELS,
    UNMANAGEABLE_OWNERS,
    ManagerInventory,
    ManagerOwnership,
    Owner,
    OwnershipCandidate,
    active_path_note,
    also_installed_note,
    attribute_path,
    declared_manager_label,
    owner_detail,
    owner_dirs,
    owner_label,
    parse_brew_list_versions,
    parse_uv_tool_list,
    read_inventory,
    removal_hint,
    removal_label,
    resolve_ownership,
)
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError
from installer.update import UpdateTarget, perform_update

_MAC = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
_BREW_PREFIX = Path("/opt/homebrew")
_MANAGED = Path("/home/user/.local/bin")
_PNPM_HOME = Path("/home/user/Library/pnpm")
_LINUX = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
_LINUXBREW_PREFIX = Path("/home/linuxbrew/.linuxbrew")
_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def _jetbrains_toolbox(*extra_methods: Method) -> Tool:
    return Tool(
        id="jetbrains-toolbox",
        name="JetBrains Toolbox",
        category="editor",
        cmd="jetbrains-toolbox",
        methods=(
            Method(kind="cask", params={"cask": "jetbrains-toolbox"}, os=("macos",)),
            *extra_methods,
        ),
    )


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
    native_probe: Callable[[list[str]], str] | None = None,
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
        native_probe=native_probe,
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


# -- D-05: install_ownership.detect_owner adapted for the four native
# package managers. -k native is 15-VALIDATION.md's pinned gate. ------------


def _dnf_tool(*, package: str = "jq", owner_probes: tuple[str, ...] = ("dnf",)) -> Tool:
    return Tool(
        id="jq",
        name="jq",
        category="data",
        cmd="jq",
        methods=(Method(kind="dnf", params={"package": package}),),
        owner_probes=owner_probes,
    )


def _verifying_dnf_probe(package: str, calls: list[list[str]]) -> Callable[[list[str]], str]:
    def probe(command: list[str]) -> str:
        calls.append(command)
        return f"{package}\n"

    return probe


def test_native_owner_resolves_from_unattributable_live_path() -> None:
    """THE CASE THAT MATTERS: a real dnf-installed tool has a live
    /usr/bin/<cmd> that attribute_path cannot attribute to any tracked
    owner, so resolve_ownership returns from this earlier unknown branch on
    a real machine -- a fallback placed only at the function's final
    `_unknown(...)` would never run for this case."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/bin/jq",
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "dnf"
    assert result.confidence == "direct"
    assert result.confidence in MUTATION_GRADE
    # Self-consistent record: the winner is present in its own candidates
    # tuple (catalog_tui.py:401-406 iterates this field) and shadowed is
    # False, because exactly one manager claims this tool.
    # package="jq": 15.4-05/Round-3 review HIGH -- `path_owner_package` has no
    # macOS entry (this test's default platform is `_MAC`), so the resolved
    # name falls back to the probe's own captured match, never `None`.
    assert result.candidates == (
        OwnershipCandidate(
            owner="dnf",
            method=None,
            package="jq",
            current_version=None,
            evidence="dnf lists jq",
        ),
    )
    assert result.package == "jq"
    assert result.shadowed is False
    assert result.active_candidate is None
    assert result.active_path == Path("/usr/bin/jq")
    assert calls  # the probe really was consulted
    # CR-01: the claim is only made after rpm confirms the declared package
    # owns the live binary, not merely that the package is installed. The
    # queried path is the RESOLVED one, so it is read back off the record
    # rather than hardcoded (a host where /home is a symlink would differ).
    assert ["rpm", "-qf", "--qf", "%{NAME}\\n", str(result.active_path)] in calls


def test_native_owner_resolves_with_no_active_path() -> None:
    """Both fallthroughs are covered by the one call site: `which` reporting
    nothing at all also reaches the native adapter."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which=None,
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "dnf"
    assert result.confidence == "direct"
    assert result.active_path is None
    assert calls


def test_native_owner_requires_complete_negative_evidence() -> None:
    """An unreadable tracked-manager inventory is incomplete negative
    evidence, not a claim -- the native probe must not even run."""
    tool = Tool(
        id="jq",
        name="jq",
        category="data",
        cmd="jq",
        methods=(
            Method(kind="dnf", params={"package": "jq"}),
            Method(kind="brew", params={"formula": "jq"}),
        ),
        owner_probes=("dnf",),
    )
    calls: list[list[str]] = []
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
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "unknown"
    assert result.unknown_reason
    assert "brew" in result.unknown_reason.lower()
    assert calls == []


def test_native_owner_suppressed_by_leftover_installer_artifact() -> None:
    """A machine holding BOTH a stale installer artifact and a live
    native-manager install resolves to unknown, on purpose, with the probe
    never run -- the candidate guard is the evidence rule failing closed.
    This is a recorded decision, not an undocumented side effect."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        artifacts=[_MANAGED / "jq"],
        which="/usr/bin/jq",
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "unknown"
    assert result.unknown_reason
    assert "/usr/bin/jq" in result.unknown_reason
    assert calls == []


def test_native_owner_never_overrides_tracked_manager_precedence() -> None:
    """A tracked manager that both claims the tool and owns the live
    executable wins outright, and the native probe is never called at all."""
    tool = Tool(
        id="jq",
        name="jq",
        category="data",
        cmd="jq",
        methods=(
            Method(kind="dnf", params={"package": "jq"}),
            Method(kind="brew", params={"formula": "jq"}),
        ),
        owner_probes=("dnf",),
    )
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={"jq": "1.7"}),
        which=str(_BREW_PREFIX / "bin" / "jq"),
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "brew"
    assert calls == []


def test_native_owner_adapter_ignores_non_native_verified_manager() -> None:
    """The adapter maps only the four native manager names and ignores
    anything else `detect_owner` can verify (Homebrew, pnpm, SDKMAN,
    managed download, host setup) -- those have their own evidence paths."""
    tool = Tool(
        id="ghost",
        name="ghost",
        category="dev",
        cmd="ghost",
        methods=(Method(kind="brew", params={"formula": "ghost"}),),
        owner_probes=("brew",),
    )

    def verifies_non_native(command: list[str]) -> str:
        assert command[0] == "brew"
        return "ghost 1.0\n"

    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={}),
        which=None,
        native_probe=verifies_non_native,
    )
    assert result.owner == "unknown"


def _shadowing_dnf_probe(package: str, calls: list[list[str]]) -> Callable[[list[str]], str]:
    """`rpm -q` confirms the package is installed; `rpm -qf` denies that it
    owns the queried file, the way rpm reports a hand-built binary."""

    def probe(command: list[str]) -> str:
        calls.append(command)
        if "-qf" in command:
            raise subprocess.CalledProcessError(1, command)
        return f"{package}\n"

    return probe


_FEDORA = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
_FEDORA_ATOMIC = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)


def test_native_owner_does_not_claim_dnf_on_an_immutable_host() -> None:
    """CR-02: on Bazzite/Silverblue the booted deployment's rpmdb answers
    `rpm -q` for every package in the base image, so a base-image `jq` used to
    resolve to `dnf` and the UI told the user to update it through dnf --
    which is not the package manager of record on an atomic host.
    `_native_owner`'s own CONFIRM probe (`_dnf`, gated by
    `_MUTABLE_HOST_ONLY_PROBES`) is never even consulted on this host, so
    `dnf` can never be the claimed owner here.

    15.4-01/D-01 changes what the HONEST answer is, not this guarantee: the
    same rpm database still answers the separate INVERSE query
    `_os_package_owner` asks (no declared candidate -- just "whatever owns
    this live path"), so a base-image package now resolves to the new
    `os-package` owner rather than `unknown` -- refused by the update action
    with a detail line naming the real package, never a suggestion to run a
    command that does not work on this host."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/bin/jq",
        platform=_FEDORA_ATOMIC,
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "os-package"
    assert result.package == "jq"
    # The dnf CONFIRM query (`rpm -q --qf ... jq`) never runs; only the
    # os-package INVERSE query (`rpm -qf --qf ... /usr/bin/jq`) does.
    assert calls == [["rpm", "-qf", "--qf", "%{NAME}\\n", "/usr/bin/jq"]]


def test_native_owner_still_claims_dnf_on_a_mutable_fedora_host() -> None:
    """The immutability gate is about the host, not the evidence: the same
    tool, probe and live path on a normal Fedora box still resolves to dnf."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/bin/jq",
        platform=_FEDORA,
        native_probe=_verifying_dnf_probe("jq", calls),
    )
    assert result.owner == "dnf"
    assert result.confidence == "direct"
    assert calls


def test_native_owner_refuses_to_claim_a_live_binary_the_package_does_not_own() -> None:
    """CR-01: the module's evidence rule says a live, unattributable active
    path forces `unknown` BEFORE by-elimination reasoning runs. The native
    adapter sits above that check by necessity (a dnf-installed tool always
    has an unattributable `/usr/bin/<cmd>`), so it has to apply the rule
    itself: a hand-built jq earlier in PATH than the dnf-installed one is
    contradictory evidence, and `rpm -qf` is what settles it. Claiming `dnf`
    here would both tell the user the wrong thing about the binary they run
    and hand a MUTATION_GRADE confidence to a package that does not own it."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/home/user/bin/jq",
        platform=_FEDORA,
        native_probe=_shadowing_dnf_probe("jq", calls),
    )
    assert result.owner == "unknown"
    assert result.confidence == "none"
    assert result.confidence not in MUTATION_GRADE
    assert result.unknown_reason
    assert ["rpm", "-qf", "--qf", "%{NAME}\\n", str(result.active_path)] in calls


def test_native_owner_path_confirmation_is_skipped_without_a_live_binary() -> None:
    """No active path is no contradiction: with nothing on PATH there is no
    file to confirm, and the package-database claim stands on its own."""
    tool = _dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which=None,
        platform=_FEDORA,
        native_probe=_shadowing_dnf_probe("jq", calls),
    )
    assert result.owner == "dnf"
    assert result.confidence == "direct"
    assert all("-qf" not in command for command in calls)


def test_native_owner_path_confirmation_covers_every_native_owner() -> None:
    """The confirmation is only as good as its coverage: a native owner with
    no declared file query would silently confirm nothing, which is the
    pre-CR-01 behavior for that manager."""
    # Deliberate private-member access: the point of this test is pinning the
    # internal query table against the public NATIVE_OWNERS tuple, mirroring
    # test_install_ownership.py's _PROBES/OWNER_PROBES drift guard.
    declared = set(install_ownership._PATH_QUERIES)  # pyright: ignore[reportPrivateUsage]
    assert set(NATIVE_OWNERS) <= declared, sorted(set(NATIVE_OWNERS) - declared)


def test_native_owners_tuple_is_the_four_widened_values() -> None:
    """The membership decision is written once: NATIVE_OWNERS is what both
    this module's adapter and update.py's refusal branch read."""
    assert set(NATIVE_OWNERS) == {"dnf", "apt", "pacman", "rpm-ostree"}
    assert len(NATIVE_OWNERS) == 4
    assert set(NATIVE_OWNERS) <= set(typing.get_args(Owner))


# -- 15.4-01/D-01: _os_package_owner -- the base-image case _native_owner
# cannot reach. git is the tracer subject: it declares package="git" while
# install_ownership.path_owner_package's real answer is "git-core"
# (15.4-RESEARCH.md Pitfall 1). -k os_package is this plan's pinned gate. ----


def _git_shaped_tool() -> Tool:
    return Tool(
        id="git",
        name="Git",
        category="git",
        cmd="git",
        methods=(
            Method(kind="dnf", params={"package": "git"}),
            Method(kind="apt", params={"package": "git"}),
            Method(kind="pacman", params={"package": "git"}),
            Method(kind="brew", params={"formula": "git"}),
        ),
        owner_probes=("rpm-ostree", "dnf", "apt", "pacman"),
    )


def _os_package_probe(package: str, calls: list[list[str]]) -> Callable[[list[str]], str]:
    """Answers every query with `package` -- including install_ownership's
    OWN rpm-ostree/dnf/apt/pacman probes, which is deliberate: those probes
    check the declared package name ("git") against this answer ("git-core"),
    never match, and so `_native_owner` correctly stands down and lets this
    adapter run -- the exact split-package case this plan exists for."""

    def probe(command: list[str]) -> str:
        calls.append(command)
        return f"{package}\n"

    return probe


@pytest.mark.parametrize("immutable", [True, False])
def test_os_package_owner_resolves_git_shaped_tool_on_fedora(immutable: bool) -> None:
    """THE CASE THAT MATTERS, parametrized over host mutability -- the
    regression detector for a later `platform.immutable` gate (Round-2 review
    MEDIUM). The evidence is identical on both: a split package's declared
    name and the database's real answer differ on a mutable Fedora box too.
    This is also the LOWER bracket on the branch's position: it fails with
    `unknown` if the call in resolve_ownership is moved after the
    active-path unknown branch, because a real git-shaped tool always has a
    live, unattributable /usr/bin/git."""
    tool = _git_shaped_tool()
    calls: list[list[str]] = []
    platform = Platform(os="fedora", arch="amd64", immutable=immutable, has_brew=False)
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/bin/git",
        platform=platform,
        native_probe=_os_package_probe("git-core", calls),
    )
    assert result.owner == "os-package"
    assert result.package == "git-core"
    assert result.confidence == "direct"
    assert result.confidence in MUTATION_GRADE
    assert result.active_path == Path("/usr/bin/git")
    assert result.candidates == (
        OwnershipCandidate(
            owner="os-package",
            method=None,
            package="git-core",
            current_version=None,
            evidence="OS package database reports git-core owns /usr/bin/git",
        ),
    )
    assert result.shadowed is False
    assert result.active_candidate is None
    assert calls  # the probe really was consulted
    # 15.4-05/Round-3 review HIGH: the resolved record's package feeds a
    # removal phrase that names the REAL package, never `git` -- and the
    # `os-package` owner never offers a backticked command regardless, since
    # the command is the host's own and differs by host.
    hint = removal_hint(result, tool.cmd)
    assert hint is not None
    assert "git-core" in hint
    assert chr(96) not in hint
    assert "git`" not in hint


def _rg_dnf_tool() -> Tool:
    """`rg`'s cmd is `rg`, but its declared dnf package is `ripgrep` -- the
    resolver-level split-package tracer (15.4-RESEARCH.md Pitfall 1's other
    half, Round-3 review HIGH)."""
    return Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=(Method(kind="dnf", params={"package": "ripgrep"}),),
        owner_probes=("dnf",),
    )


def test_native_owner_resolves_ripgrep_split_package_end_to_end() -> None:
    """Round-3 review HIGH, resolver level: `resolve_ownership` over a
    dnf-owned, `rg`-commanded, `ripgrep`-packaged tool returns a record whose
    `package` is `ripgrep`. Asserted on the resolved record's package AND on
    the `removal_hint` string built from it, because the point of the pair is
    that the second cannot be right while the first is wrong -- a command
    built from `tool.cmd` would read `dnf remove rg`, which fails outright."""
    tool = _rg_dnf_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/bin/rg",
        platform=_FEDORA,
        native_probe=_verifying_dnf_probe("ripgrep", calls),
    )
    assert result.owner == "dnf"
    assert result.package == "ripgrep"
    hint = removal_hint(result, tool.cmd)
    assert hint is not None
    assert "ripgrep" in hint
    assert "`dnf remove rg`" not in hint
    assert calls  # the probe really was consulted


def test_native_owner_removal_hint_degrades_when_no_package_is_resolvable() -> None:
    """Negative case (Round-3 review HIGH): a record that carries ownership
    but no resolvable package name degrades to a description-only phrase --
    never a guess built from the caller-supplied fallback tool identifier."""
    record = _record("dnf", package=None)
    hint = removal_hint(record, "rg")
    assert hint is not None
    assert chr(96) not in hint
    assert "rg" in hint  # the fallback TOOL identifier, in prose only


def _raising_probe(_command: list[str]) -> str:
    raise FileNotFoundError()


def test_os_package_owner_returns_unknown_when_probe_answers_nothing() -> None:
    """CR-01, pinned for this branch too: a silent probe still forces
    `unknown` with `active_path` set, never a guess."""
    tool = _git_shaped_tool()
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/bin/git",
        platform=_FEDORA,
        native_probe=_raising_probe,
    )
    assert result.owner == "unknown"
    assert result.confidence == "none"
    assert result.active_path == Path("/usr/bin/git")


def test_readable_brew_inventory_listing_git_wins_over_os_package() -> None:
    """UPPER bracket on the branch's position: this fails if the os-package
    call is moved AHEAD of the tracked-candidate active-path branch -- a
    readable inventory that lists the tool must win, and the probe below must
    never even be consulted."""
    tool = _git_shaped_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={"git": "2.44.0"}),
        which=str(_BREW_PREFIX / "bin" / "git"),
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        native_probe=_os_package_probe("git-core", calls),
    )
    assert result.owner == "brew"
    assert calls == []


def test_unreadable_brew_inventory_blocks_the_os_package_fallback() -> None:
    """Complete negative evidence means EVERY tracked manager was queried
    successfully and none claimed the tool -- an unreadable brew inventory is
    incomplete, not a claim, and the os-package probe must not even run."""
    tool = _git_shaped_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=ManagerInventory(
            brew_formulae=None,
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=_BREW_PREFIX,
        ),
        which="/usr/bin/git",
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        native_probe=_os_package_probe("git-core", calls),
    )
    assert result.owner == "unknown"
    assert result.unknown_reason
    assert "brew" in result.unknown_reason.lower()
    assert calls == []


def test_os_package_owner_never_runs_on_macos() -> None:
    """`path_owner_package` has no macOS entry -- there is no OS package
    database to ask, and Homebrew ownership is answered elsewhere."""
    tool = _git_shaped_tool()
    calls: list[list[str]] = []
    result = _resolve(
        tool,
        inventory=_empty_readable(),
        which="/usr/local/bin/git",
        platform=_MAC,
        native_probe=_os_package_probe("git-core", calls),
    )
    assert result.owner == "unknown"


def test_unmanageable_owners_is_native_owners_plus_os_package() -> None:
    """The membership decision is written once: this is the wider set
    installer/update.py's refusal branch actually reads."""
    assert frozenset({*NATIVE_OWNERS, OS_PACKAGE_OWNER}) == UNMANAGEABLE_OWNERS
    assert set(typing.get_args(Owner)) >= UNMANAGEABLE_OWNERS


# -- 15.4-01/D-01/D-02: OWNER_LABELS and owner_label -- every Owner value
# except unknown has a column label. --------------------------------------


def test_owner_labels_covers_every_non_unknown_owner_value() -> None:
    assert set(OWNER_LABELS) == set(typing.get_args(Owner)) - {"unknown"}
    assert all(OWNER_LABELS[value] for value in OWNER_LABELS)


def test_owner_labels_cask_and_brew_literals_are_pinned() -> None:
    assert OWNER_LABELS["brew"] == "Homebrew"
    assert OWNER_LABELS["cask"] == "Homebrew cask"


def test_owner_label_names_the_os_package_case() -> None:
    assert OWNER_LABELS["os-package"] == "OS package"


def _record(
    owner: Owner, *, method: Method | None = None, package: str | None = None
) -> ManagerOwnership:
    return ManagerOwnership(
        tool_id="demo",
        owner=owner,
        method=method,
        package=package,
        current_version=None,
        confidence="none" if owner == "unknown" else "direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason="no manager claimed the tool" if owner == "unknown" else None,
    )


def test_owner_label_is_none_only_for_unknown() -> None:
    assert owner_label(_record("unknown")) is None


@pytest.mark.parametrize(
    "owner", [o for o in typing.get_args(Owner) if o not in ("unknown", "installer")]
)
def test_owner_label_reads_the_column_register(owner: Owner) -> None:
    assert owner_label(_record(owner)) == OWNER_LABELS[owner]


def test_owner_label_reads_the_resolved_method_kind_for_an_installer_owned_record() -> None:
    method = Method(kind="github_release", params={"repo": "owner/demo"})
    label = owner_label(_record("installer", method=method))
    assert label == "GitHub release"
    assert label != OWNER_LABELS["installer"]


def test_owner_label_falls_back_to_the_installer_artifact_entry_with_no_method() -> None:
    assert owner_label(_record("installer", method=None)) == OWNER_LABELS["installer"]


# -- 15.4-03/D-02/D-02a: OWNER_DETAIL_LABELS (the PROSE register) and
# owner_detail -- the register split (see 15.4-03-PLAN.md's <design_note>):
# OWNER_LABELS is the terse COLUMN register asserted above, OWNER_DETAIL_LABELS
# is the full-sentence detail-bar register declared beside it. The two are
# allowed to differ; the one place they deliberately share wording
# (brew/cask) is DETAIL_PHRASE_COLLISIONS' sole member. ------------------------


def test_owner_detail_prose_register_is_exhaustive() -> None:
    assert set(OWNER_DETAIL_LABELS) == set(typing.get_args(Owner)) - {"unknown"}
    assert all(OWNER_DETAIL_LABELS[value] for value in OWNER_DETAIL_LABELS)


def test_owner_labels_column_register_values_are_pairwise_distinct() -> None:
    values = list(OWNER_LABELS.values())
    assert len(values) == len(set(values))


def test_owner_detail_is_none_only_for_unknown() -> None:
    assert owner_detail(_record("unknown")) is None


@pytest.mark.parametrize(
    ("owner", "expected"),
    [
        ("brew", "managed by Homebrew"),
        ("cask", "managed by Homebrew"),
        ("pnpm", "managed by pnpm"),
        ("uv", "managed by uv"),
        ("dnf", "managed by dnf — this installer will not update it"),
        ("apt", "managed by apt — this installer will not update it"),
        ("pacman", "managed by pacman — this installer will not update it"),
        ("rpm-ostree", "managed by rpm-ostree — this installer will not update it"),
    ],
)
def test_owner_detail_byte_identical_pre_phase_sentences(owner: Owner, expected: str) -> None:
    """These eight sentences pre-date this phase (lifted verbatim from
    catalog_tui.py's local `labels` dict). Pinned against literals written
    out here, not against the source dict, so a later edit to
    `OWNER_DETAIL_LABELS` that changes this user-visible copy is a failing
    test rather than a silent copy change."""
    assert owner_detail(_record(owner)) == expected


def test_owner_detail_os_package_names_the_package() -> None:
    detail = owner_detail(_record("os-package", package="git-core"))
    assert detail is not None
    assert "git-core" in detail
    assert "will not update it" in detail


@pytest.mark.parametrize(
    ("kind", "mechanism"),
    [
        ("github_release", "GitHub release"),
        ("tarball", "tarball download"),
        ("app", "downloaded app"),
        ("script", "own installer"),
    ],
)
def test_owner_detail_installer_names_the_placement_mechanism(kind: str, mechanism: str) -> None:
    method = Method(kind=kind, params={})
    detail = owner_detail(_record("installer", method=method))
    assert detail is not None
    assert mechanism in detail
    # D-02a: never the bare catch-all word that implies a package manager
    # exists behind it.
    assert detail != "installed by this installer"


def test_owner_detail_installer_falls_back_with_no_resolved_method() -> None:
    detail = owner_detail(_record("installer", method=None))
    assert detail is not None
    assert OWNER_LABELS["installer"] in detail


def test_owner_detail_declared_collision_is_the_only_shared_sentence() -> None:
    """The satisfiable form of "no two owner states share a detail sentence"
    (Round-1 review HIGH): sharing is legal but must be declared. Grouping
    every non-unknown owner's representative sentence must produce exactly
    one group of size > 1, and that group must be {brew, cask}."""
    method = Method(kind="github_release", params={"repo": "owner/demo"})
    groups: dict[str, set[Owner]] = {}
    for owner in typing.get_args(Owner):
        if owner == "unknown":
            continue
        record = _record(
            owner,
            method=method if owner == "installer" else None,
            package="demo-pkg" if owner == "os-package" else None,
        )
        detail = owner_detail(record)
        assert detail is not None
        groups.setdefault(detail, set()).add(owner)
    shared = [frozenset(owners) for owners in groups.values() if len(owners) > 1]
    assert shared == [frozenset({"brew", "cask"})]
    assert frozenset(shared) <= DETAIL_PHRASE_COLLISIONS
    assert frozenset({frozenset({"brew", "cask"})}) == DETAIL_PHRASE_COLLISIONS


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


# --- 15.4-02: Linux-cask ownership evidence (D-01's second dated correction) ---


def test_linux_cask_resolves_direct_owner_when_binary_under_brew_prefix() -> None:
    """The primary proving case: a linuxbrew-cask-owned tool no longer
    resolves to `unknown` just because `resolve.py`'s cask gate is macOS-only.
    Mirrors the macOS cask path exactly -- direct confidence when the live
    binary attributes to the brew prefix."""
    tool = _jetbrains_toolbox(
        Method(
            kind="cask",
            params={"cask": "jetbrains-toolbox-linux"},
            os=("debian", "arch", "fedora"),
        ),
    )
    result = _resolve(
        tool,
        inventory=_readable(
            brew_casks={"jetbrains-toolbox-linux": "2.6.2"}, brew_prefix=_LINUXBREW_PREFIX
        ),
        which=str(_LINUXBREW_PREFIX / "bin" / "jetbrains-toolbox"),
        platform=_LINUX,
    )
    assert result.owner == "cask"
    assert result.package == "jetbrains-toolbox-linux"
    assert result.confidence == "direct"
    assert result.active_candidate == "cask"
    # resolve.py is untouched: install behaviour on Linux stays no-cask.
    assert [m.kind for m in resolve_methods(tool, _LINUX)] == []


def test_linux_cask_unreadable_inventory_forces_unknown() -> None:
    """`competing_owners` must see the Linux cask candidate too, so an
    unreadable cask inventory forces `unknown` exactly like an unreadable
    brew inventory already does (T-15.4-07)."""
    tool = _jetbrains_toolbox(
        Method(
            kind="cask",
            params={"cask": "jetbrains-toolbox-linux"},
            os=("debian", "arch", "fedora"),
        ),
    )
    result = _resolve(
        tool,
        inventory=ManagerInventory(
            brew_formulae={},
            brew_casks=None,
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=_LINUXBREW_PREFIX,
        ),
        which=str(_LINUXBREW_PREFIX / "bin" / "jetbrains-toolbox"),
        platform=_LINUX,
    )
    assert result.owner == "unknown"
    assert result.confidence == "none"
    assert result.unknown_reason is not None
    assert "cask" in result.unknown_reason.lower()


def test_macos_cask_not_double_counted_by_ownership_only_path() -> None:
    """On macOS the ownership-only helper contributes nothing: the method
    sequence `_collect_candidates` sees contains each cask method exactly
    once, so no tool can ever produce two `cask` candidates."""
    tool = _jetbrains_toolbox(
        Method(
            kind="cask",
            params={"cask": "jetbrains-toolbox-linux"},
            os=("debian", "arch", "fedora"),
        ),
    )
    assert ownership._ownership_only_methods(tool, _MAC) == ()  # pyright: ignore[reportPrivateUsage]
    applicable = resolve_methods(tool, _MAC)
    assert [m.kind for m in applicable].count("cask") == 1


def test_linux_cask_no_brew_contributes_nothing() -> None:
    """No brew present means no cask inventory could have been read, so the
    ownership-only helper contributes nothing."""
    tool = _jetbrains_toolbox(
        Method(
            kind="cask",
            params={"cask": "jetbrains-toolbox-linux"},
            os=("debian", "arch", "fedora"),
        ),
    )
    linux_no_brew = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    assert (
        ownership._ownership_only_methods(tool, linux_no_brew) == ()  # pyright: ignore[reportPrivateUsage]
    )


def test_linux_cask_excluded_os_enters_neither_surface() -> None:
    """A Linux cask method whose own `os` list excludes the running platform
    enters NEITHER `candidates` NOR `competing_owners` (Round-2 review LOW)."""
    tool = _jetbrains_toolbox(
        Method(kind="cask", params={"cask": "jetbrains-toolbox-linux"}, os=("debian",)),
    )
    result = _resolve(
        tool,
        inventory=_readable(brew_casks={"jetbrains-toolbox-linux": "2.6.2"}),
        platform=_LINUX,  # fedora, not debian
    )
    assert result.candidates == ()
    assert ownership.competing_owners(tool, _LINUX) == frozenset()


def test_linux_cask_excluded_arch_enters_neither_surface() -> None:
    """A Linux cask method whose own `arch` list excludes the running
    architecture contributes nothing, on the same two surfaces."""
    tool = _jetbrains_toolbox(
        Method(
            kind="cask",
            params={"cask": "jetbrains-toolbox-linux"},
            os=("fedora",),
            arch=("arm64",),
        ),
    )
    result = _resolve(
        tool,
        inventory=_readable(brew_casks={"jetbrains-toolbox-linux": "2.6.2"}),
        platform=_LINUX,  # amd64, not arm64
    )
    assert result.candidates == ()
    assert ownership.competing_owners(tool, _LINUX) == frozenset()


def test_linux_cask_unmet_min_os_version_enters_neither_surface() -> None:
    """A Linux cask method declaring a `min_os_version` the platform does not
    meet contributes nothing -- including a platform whose `os_version` is
    `None`, which every Linux platform's is (populated only on Darwin)."""
    tool = _jetbrains_toolbox(
        Method(
            kind="cask",
            params={"cask": "jetbrains-toolbox-linux", "min_os_version": "26.0"},
            os=("fedora",),
        ),
    )
    assert _LINUX.os_version is None
    result = _resolve(
        tool,
        inventory=_readable(brew_casks={"jetbrains-toolbox-linux": "2.6.2"}),
        platform=_LINUX,
    )
    assert result.candidates == ()
    assert ownership.competing_owners(tool, _LINUX) == frozenset()


def test_ownership_only_methods_ignores_undeclared_kinds() -> None:
    """A kind absent from `_OWNERSHIP_ONLY_KINDS` never reaches the
    ownership-only path even when it targets the platform on every dimension
    that kind would have been allowed to bypass (Round-2 review MEDIUM)."""
    method = Method(kind="dnf", params={"package": "hypothetical"}, os=("fedora",), arch=("arm64",))
    tool = Tool(
        id="hypothetical",
        name="hypothetical",
        category="dev",
        cmd="hypothetical",
        methods=(method,),
    )
    # `_applies` refuses it (wrong arch), so it is not an install candidate...
    assert resolve._applies(method, _LINUX) is False  # pyright: ignore[reportPrivateUsage]
    # ...and the `os`-only reading that the `brew` row IS allowed accepts it,
    # so only the kind declaration stands between this method and the path.
    assert (
        ownership._method_targets_platform(method, _LINUX, ("os",))  # pyright: ignore[reportPrivateUsage]
        is True
    )
    assert ownership._ownership_only_methods(tool, _LINUX) == ()  # pyright: ignore[reportPrivateUsage]


def test_ownership_only_kinds_declaration_matches_helper_reach() -> None:
    """The declaration table and the helper's actual reach are the same set.

    Each DECLARED kind gets a method `resolve._applies` refuses on this
    platform but that kind's own declared dimension subset accepts -- which is
    the whole definition of an ownership-only method. Every other kind in
    `resolve._RANK` gets a method `_applies` also refuses, and must stay
    unreachable regardless."""
    assert set(ownership._OWNERSHIP_ONLY_KINDS) == {  # pyright: ignore[reportPrivateUsage]
        "cask",
        "brew",
    }
    declared = (
        # cask: refused by `_applies`'s macOS-and-brew kind-gate on Linux,
        # accepted on all three of os/arch/min_os_version.
        Method(kind="cask", params={"cask": "declared-cask"}, os=("fedora",)),
        # brew (WR-04): refused by `_applies`'s arch clause, accepted by the
        # `("os",)`-only subset the table declares for this kind.
        Method(kind="brew", params={"formula": "declared-brew"}, os=("fedora",), arch=("arm64",)),
    )
    undeclared = tuple(
        Method(kind=kind, os=("fedora",), arch=("arm64",))
        for kind in resolve._RANK  # pyright: ignore[reportPrivateUsage]
        if kind not in ownership._OWNERSHIP_ONLY_KINDS  # pyright: ignore[reportPrivateUsage]
    )
    tool = Tool(
        id="every-kind",
        name="every-kind",
        category="dev",
        cmd="every-kind",
        methods=(*declared, *undeclared),
    )
    for method in (*declared, *undeclared):
        assert resolve._applies(method, _LINUX) is False, method.kind  # pyright: ignore[reportPrivateUsage]
    reachable = {
        method.kind
        for method in ownership._ownership_only_methods(tool, _LINUX)  # pyright: ignore[reportPrivateUsage]
    }
    assert reachable == set(ownership._OWNERSHIP_ONLY_KINDS)  # pyright: ignore[reportPrivateUsage]


def test_ownership_only_methods_never_repeats_an_install_candidate() -> None:
    """The identity exclusion that replaced the blanket `os == "macos"` gate
    (WR-04): a method `resolve_methods` already returned must not also arrive
    through the ownership-only path, or `_collect_candidates` would see one
    method twice for a tool."""
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.1")
    method = Method(kind="cask", params={"cask": "visual-studio-code"}, os=("macos",))
    tool = Tool(id="code", name="code", category="editor", cmd="code", methods=(method,))
    assert resolve.resolve_methods(tool, macos) == [method]
    assert ownership._ownership_only_methods(tool, macos) == ()  # pyright: ignore[reportPrivateUsage]


def test_brew_ownership_survives_an_unmet_min_os_version_gate() -> None:
    """WR-04 (15.4-REVIEW.md), the case the registry actually carries: on a
    macOS arm64 host BELOW `container`'s `min_os_version` floor,
    `resolve_methods` returns no method at all, so a genuinely brew-installed
    `container` produced no candidate, resolved to `unknown`, and reported
    "managed outside this installer" instead of `brew uninstall container`.

    `arch`/`min_os_version` bear on INSTALLABILITY; this module answers what
    owns the installed copy, and the claim is still backed by the real
    `brew list --versions` inventory, never by the registry row alone."""
    too_old = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="15.2")
    method = Method(
        kind="brew",
        params={"formula": "container", "min_os_version": "26"},
        os=("macos",),
        arch=("arm64",),
    )
    tool = Tool(
        id="container", name="container", category="container", cmd="container", methods=(method,)
    )
    assert resolve.resolve_methods(tool, too_old) == []  # not installable here
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={"container": "0.5.0"}),
        platform=too_old,
        which="/opt/homebrew/bin/container",
    )
    assert result.owner == "brew"
    assert result.package == "container"
    assert removal_hint(result, tool.cmd) == "managed by Homebrew — `brew uninstall container`"
    assert ownership.competing_owners(tool, too_old) == frozenset({"brew"})


def test_brew_ownership_stays_unknown_when_the_inventory_does_not_claim_it() -> None:
    """The widening is evidence-gated, not a registry guess: the same
    arch/min_os_version-excluded method attributes NOTHING when the real brew
    inventory does not list the formula."""
    too_old = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="15.2")
    method = Method(
        kind="brew",
        params={"formula": "container", "min_os_version": "26"},
        os=("macos",),
        arch=("arm64",),
    )
    tool = Tool(
        id="container", name="container", category="container", cmd="container", methods=(method,)
    )
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={}),
        platform=too_old,
        which="/usr/local/bin/container",
    )
    assert result.owner == "unknown"


def test_brew_ownership_still_mirrors_the_os_dimension() -> None:
    """The `brew` row declares `("os",)`: the os dimension is still mirrored,
    so a macOS-only formula is never evidence of anything on Linux."""
    method = Method(kind="brew", params={"formula": "macos-only"}, os=("macos",))
    tool = Tool(id="mo", name="mo", category="dev", cmd="mo", methods=(method,))
    assert ownership._ownership_only_methods(tool, _LINUX) == ()  # pyright: ignore[reportPrivateUsage]
    assert ownership.competing_owners(tool, _LINUX) == frozenset()


def test_cask_kind_absent_from_installer_kinds() -> None:
    """`_collect_candidates`'s `installer_method` lookup must never pick up a
    cask method: `APP_KINDS` and `DOWNLOAD_KINDS` do not contain `cask`."""
    from installer.apps import APP_KINDS
    from installer.download import DOWNLOAD_KINDS

    assert "cask" not in APP_KINDS
    assert "cask" not in DOWNLOAD_KINDS


def test_ownership_only_methods_wired_into_both_candidate_and_competing_paths() -> None:
    """The candidate path and the competing-owner guard must read the same
    helper, or a claim and its guard could disagree."""
    import inspect

    resolve_ownership_source = inspect.getsource(ownership.resolve_ownership)
    competing_owners_source = inspect.getsource(ownership.competing_owners)
    assert "_ownership_only_methods" in resolve_ownership_source
    assert "_ownership_only_methods" in competing_owners_source
    assert "resolve_methods(tool, platform)" in resolve_ownership_source


def test_resolve_py_cask_gate_unchanged_by_ownership_only_path() -> None:
    """T-15.4-05: proves BEHAVIOURALLY, not by source-substring, that
    `resolve.py::_applies`'s cask branch still refuses every Linux platform
    and accepts only macOS with brew -- the exact verdict this plan's
    ownership-only path exists to bypass for ATTRIBUTION, never for install
    eligibility. A source-substring assertion was flagged over-rigid by
    Round-1 review; this three-point truth table also catches an inverted
    condition a substring match would happily pass."""
    method = Method(kind="cask", params={"cask": "x"})
    linux_with_brew = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
    macos_with_brew = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    macos_without_brew = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    assert resolve._applies(method, linux_with_brew) is False  # pyright: ignore[reportPrivateUsage]
    assert resolve._applies(method, macos_with_brew) is True  # pyright: ignore[reportPrivateUsage]
    assert resolve._applies(method, macos_without_brew) is False  # pyright: ignore[reportPrivateUsage]


def test_method_targets_platform_agrees_with_applies_across_dimension_product() -> None:
    """The applicability drift gate (Round-1 review MEDIUM; kept table-driven
    per Round-2 review MEDIUM). Enumerates the product of declared os/arch/
    min_os_version and platform os/arch/os_version over a `kind = "script"`
    method -- the kind `_applies` accepts unconditionally once its three
    dimension checks pass, making the two functions directly comparable --
    and asserts `_method_targets_platform` and `resolve._applies` agree on
    every cell. A future fourth dimension added to one function and
    forgotten in the other fails here."""
    platform_os_values = ("fedora", "debian", "arch", "macos")
    platform_arch_values = ("amd64", "arm64")
    platform_os_version_values = (None, "25.0", "26.1")
    method_os_values = ((), ("fedora",), ("macos", "fedora"))
    method_arch_values = ((), ("amd64",))
    method_params_values: tuple[dict[str, object], ...] = ({}, {"min_os_version": "26.0"})
    dimensions = (
        platform_os_values,
        platform_arch_values,
        platform_os_version_values,
        method_os_values,
        method_arch_values,
        method_params_values,
    )
    cases = [
        (
            Method(kind="script", params=dict(params), os=method_os, arch=method_arch),
            Platform(
                os=platform_os,
                arch=platform_arch,
                immutable=False,
                has_brew=True,
                os_version=platform_os_version,
            ),
        )
        for platform_os, platform_arch, platform_os_version, method_os, method_arch, params in (
            product(*dimensions)
        )
    ]
    assert len(cases) == 288
    mismatches: list[tuple[Method, Platform]] = []
    for method, platform in cases:
        targets = ownership._method_targets_platform(method, platform)  # pyright: ignore[reportPrivateUsage]
        applies = resolve._applies(method, platform)  # pyright: ignore[reportPrivateUsage]
        if targets != applies:
            mismatches.append((method, platform))
    assert not mismatches


def test_real_registry_jetbrains_toolbox_resolves_linux_cask_ownership() -> None:
    """15.4-02 task 2's end-to-end proof that the registry's Linux cask row
    and task 1's ownership-only helper meet: loading the REAL registry and
    resolving ownership for jetbrains-toolbox on a Linux platform, against a
    fake cask inventory listing the Linux cask name and a live binary under
    the fake brew prefix, resolves the cask owner -- exactly like the
    fake-tool unit tests above, but over the actual committed registry data."""
    tools = {tool.id: tool for tool in load_tools(_REGISTRY)}
    toolbox = tools["jetbrains-toolbox"]
    result = _resolve(
        toolbox,
        inventory=_readable(
            brew_casks={"jetbrains-toolbox-linux": "2.6.2"}, brew_prefix=_LINUXBREW_PREFIX
        ),
        which=str(_LINUXBREW_PREFIX / "bin" / "jetbrains-toolbox"),
        platform=_LINUX,
    )
    assert result.owner == "cask"
    assert result.package == "jetbrains-toolbox-linux"
    assert result.confidence == "direct"


def test_real_registry_vscode_resolves_linux_cask_ownership() -> None:
    """15.4-VERIFICATION.md gap closure: the same end-to-end proof as
    jetbrains-toolbox's, over vscode's own Linux-gated cask row -- loading
    the REAL registry and resolving ownership for vscode on a Linux platform,
    against a fake cask inventory listing the Linux cask name and a live
    binary under the fake brew prefix, resolves the cask owner."""
    tools = {tool.id: tool for tool in load_tools(_REGISTRY)}
    vscode = tools["vscode"]
    result = _resolve(
        vscode,
        inventory=_readable(
            brew_casks={"visual-studio-code-linux": "1.90.0"}, brew_prefix=_LINUXBREW_PREFIX
        ),
        which=str(_LINUXBREW_PREFIX / "bin" / "code"),
        platform=_LINUX,
    )
    assert result.owner == "cask"
    assert result.package == "visual-studio-code-linux"
    assert result.confidence == "direct"


# -- 15.4-05/D-03/D-04: removal_hint -- the Uninstall screen's per-owner
# removal phrase, built over the shared OWNER_LABELS/owner_label vocabulary.
# Round-3 review HIGH is the through-line: a command is only as truthful as
# the package name it is built from, so removal_hint structurally cannot
# emit one without a resolved package name. ---------------------------------

_REMOVAL_COMMANDS = ownership._REMOVAL_COMMANDS  # pyright: ignore[reportPrivateUsage]
_REMOVAL_DESCRIPTIONS = ownership._REMOVAL_DESCRIPTIONS  # pyright: ignore[reportPrivateUsage]
_NO_REMOVAL_HINT = ownership._NO_REMOVAL_HINT  # pyright: ignore[reportPrivateUsage]
_LABEL_AGREEMENT_EXEMPT = ownership._LABEL_AGREEMENT_EXEMPT  # pyright: ignore[reportPrivateUsage]

_COMMAND_OWNERS: tuple[Owner, ...] = tuple(
    owner for owner, command in _REMOVAL_COMMANDS.items() if command
)


def test_removal_command_and_no_hint_tables_are_exhaustive_over_owner() -> None:
    """Mirrors OWNER_LABELS'/OWNER_DETAIL_LABELS' own exhaustiveness gate
    shape: every Owner value is in exactly one of _REMOVAL_COMMANDS and
    _NO_REMOVAL_HINT, so an eleventh owner value cannot ship without a
    declared removal-hint disposition."""
    covered = set(_REMOVAL_COMMANDS) | set(_NO_REMOVAL_HINT)
    assert covered == set(typing.get_args(Owner))
    assert set(_REMOVAL_COMMANDS).isdisjoint(_NO_REMOVAL_HINT)


def test_every_removal_command_owner_also_has_a_description() -> None:
    """An owner that CAN produce a command must also be able to say something
    without one, because the package name is resolved at runtime and can be
    absent for any of them."""
    assert set(_REMOVAL_COMMANDS) <= set(_REMOVAL_DESCRIPTIONS)


def test_no_removal_hint_holds_exactly_unknown_and_installer() -> None:
    assert frozenset({"unknown", "installer"}) == _NO_REMOVAL_HINT


def test_removal_hint_is_none_for_unknown_and_installer() -> None:
    assert removal_hint(_record("unknown"), "demo") is None
    assert removal_hint(_record("installer"), "demo") is None


def test_removal_label_answers_for_exactly_the_records_removal_hint_answers_for() -> None:
    """CR-03 (15.4-REVIEW.md): the two registers are a PAIR -- the cell label
    and the detail sentence -- so a caller must never have to ask which of
    them is silent for a given record. Both answer `None` for exactly
    `_NO_REMOVAL_HINT` and a string for every other owner."""
    for owner in typing.get_args(Owner):
        record = _record(owner, package="realpkg")
        assert (removal_label(record) is None) == (removal_hint(record, "toolcmd") is None), owner


def test_removal_label_is_the_same_string_the_owner_column_renders() -> None:
    """The cell and the catalog's Owner column must name a manager with the
    identical string -- two vocabularies for one manager is how a user learns
    to distrust one of them."""
    for owner in typing.get_args(Owner):
        if owner in _NO_REMOVAL_HINT:
            continue
        record = _record(owner, package="realpkg")
        assert removal_label(record) == owner_label(record), owner


def test_removal_label_stays_inside_the_cell_width_budget() -> None:
    """CR-03: this register exists because the column has a width budget --
    rendering the SENTENCE instead measured 120 columns at 80x24 and pushed
    "What gets removed" off the viewport entirely. `OWNER_LABELS`' own module
    comment sizes the column register at ~14 characters; nothing here may
    exceed that without the layout test in `tests/test_wizard_app.py`
    (`test_removes_column_starts_inside_the_viewport_at_the_minimum_size`)
    being re-measured."""
    for owner in typing.get_args(Owner):
        label = removal_label(_record(owner, package="realpkg"))
        if label is not None:
            assert len(label) <= 14, (owner, label)


def test_removal_hint_reproduces_the_brew_sentence_byte_for_byte() -> None:
    record = _record("brew", package="ripgrep")
    assert removal_hint(record, "rg") == "managed by Homebrew — `brew uninstall ripgrep`"


def test_removal_hint_reproduces_the_cask_sentence_byte_for_byte() -> None:
    record = _record("cask", package="visual-studio-code")
    assert (
        removal_hint(record, "code")
        == "managed by Homebrew — `brew uninstall --cask visual-studio-code`"
    )


@pytest.mark.parametrize(
    ("owner", "package", "expected_fragment"),
    [
        ("pnpm", "@scope/demo", "pnpm remove --global @scope/demo"),
        ("uv", "demo-tool", "uv tool uninstall demo-tool"),
        ("dnf", "ripgrep", "dnf remove ripgrep"),
        ("apt", "ripgrep", "apt remove ripgrep"),
        ("pacman", "ripgrep", "pacman -R ripgrep"),
        ("rpm-ostree", "ripgrep", "rpm-ostree uninstall ripgrep"),
    ],
)
def test_removal_hint_names_each_managers_own_command(
    owner: Owner, package: str, expected_fragment: str
) -> None:
    hint = removal_hint(_record(owner, package=package), "rg")
    assert hint is not None
    assert f"`{expected_fragment}`" in hint


def test_removal_hint_for_os_package_names_the_package_with_no_command() -> None:
    """No command, because the command is the host's own and differs by
    host -- the package NAME is still worth naming, though."""
    hint = removal_hint(_record("os-package", package="git-core"), "git")
    assert hint is not None
    assert "git-core" in hint
    assert chr(96) not in hint


@pytest.mark.parametrize("owner", _COMMAND_OWNERS)
def test_removal_hint_carries_a_command_only_when_package_is_resolved(owner: Owner) -> None:
    with_package = removal_hint(_record(owner, package="realpkg"), "toolcmd")
    without_package = removal_hint(_record(owner, package=None), "toolcmd")
    assert with_package is not None
    assert chr(96) in with_package
    assert "realpkg" in with_package
    assert "toolcmd" not in with_package
    assert without_package is not None
    assert chr(96) not in without_package


@pytest.mark.parametrize(
    "owner",
    [
        o
        for o in typing.get_args(Owner)
        if o not in _NO_REMOVAL_HINT and o not in _LABEL_AGREEMENT_EXEMPT
    ],
)
def test_removal_hint_contains_its_owners_column_label(owner: Owner) -> None:
    """The two surfaces cannot name the same manager differently -- except
    the one declared exemption, asserted separately below."""
    record = _record(owner, package="demo-package")
    hint = removal_hint(record, "demo")
    label = owner_label(record)
    assert hint is not None
    assert label is not None
    assert label in hint


def test_removal_hint_label_agreement_exemption_is_exactly_cask() -> None:
    assert frozenset({"cask"}) == _LABEL_AGREEMENT_EXEMPT


def test_cask_removal_hint_and_label_both_name_homebrew_and_the_cask_concept() -> None:
    """Cask's bespoke assertion (Round-2 review MEDIUM): the exemption is a
    DIFFERENT assertion, not an absent one -- both surfaces still name the
    same manager and the same cask concept, they just do not share a literal
    substring."""
    record = _record("cask", package="rectangle")
    label = owner_label(record)
    hint = removal_hint(record, "rectangle")
    assert hint is not None
    assert label is not None
    assert "Homebrew" in label
    assert "Homebrew" in hint
    assert "cask" in label.lower()
    assert "--cask" in hint


def _sdkman_tool(bin_dir: str, *, cmd: str = "groovy", candidate: str = "groovy") -> Tool:
    return Tool(
        id=cmd,
        name=cmd,
        category="runtime",
        cmd=cmd,
        methods=(Method(kind="sdkman", params={"candidate": candidate, "bin_dir": bin_dir}),),
    )


def _touch_executable(bin_dir: Path, cmd: str) -> Path:
    bin_dir.mkdir(parents=True)
    path = bin_dir / cmd
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_sdkman_location_proof_resolves_direct_when_which_matches(tmp_path: Path) -> None:
    bin_dir = tmp_path / "sdk" / "candidates" / "groovy" / "current" / "bin"
    binary = _touch_executable(bin_dir, "groovy")
    result = _resolve(_sdkman_tool(str(bin_dir)), inventory=_empty_readable(), which=str(binary))
    assert result.owner == "sdkman"
    assert result.confidence == "direct"
    assert owner_label(result) == "SDKMAN"
    assert result.method is not None
    assert result.method.params["bin_dir"] == str(bin_dir)
    hint = removal_hint(result, "groovy")
    assert hint is not None
    assert "`sdk uninstall groovy <version>`" in hint


def test_sdkman_location_proof_is_by_elimination_when_not_on_path(tmp_path: Path) -> None:
    bin_dir = tmp_path / "sdk" / "candidates" / "groovy" / "current" / "bin"
    _touch_executable(bin_dir, "groovy")
    result = _resolve(_sdkman_tool(str(bin_dir)), inventory=_empty_readable(), which=None)
    assert result.owner == "sdkman"
    assert result.confidence == "by-elimination"


def test_sdkman_absent_bin_dir_file_is_unknown(tmp_path: Path) -> None:
    bin_dir = str(tmp_path / "sdk" / "candidates" / "groovy" / "current" / "bin")
    result = _resolve(_sdkman_tool(bin_dir), inventory=_empty_readable(), which=None)
    assert result.owner == "unknown"


def _bun(bin_dir: str) -> Tool:
    return Tool(
        id="bun",
        name="bun",
        category="runtime",
        cmd="bun",
        methods=(
            Method(kind="script", params={"bin_dir": bin_dir}),
            Method(kind="brew", params={"formula": "bun"}),
        ),
    )


def test_own_installer_location_proof_resolves_bun_when_brew_does_not_list_it(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / ".bun" / "bin"
    binary = _touch_executable(bin_dir, "bun")
    result = _resolve(_bun(str(bin_dir)), inventory=_readable(brew_formulae={}), which=str(binary))
    assert result.owner == "installer"
    assert result.confidence == "direct"
    assert owner_label(result) == "own installer"


def test_own_installer_location_candidate_loses_to_a_live_brew_path(tmp_path: Path) -> None:
    bin_dir = tmp_path / ".bun" / "bin"
    _touch_executable(bin_dir, "bun")
    result = _resolve(
        _bun(str(bin_dir)),
        inventory=_readable(brew_formulae={"bun": "1.1.0"}),
        which=str(_BREW_PREFIX / "bin" / "bun"),
    )
    assert result.owner == "brew"
    assert result.shadowed is True
    assert any(candidate.owner == "installer" for candidate in result.candidates)
    assert result.active_candidate == "brew"


def test_script_and_uv_attributing_the_same_live_path_stay_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = tmp_path / "bin"
    binary = _touch_executable(shared, "ruff")
    monkeypatch.setenv("UV_TOOL_BIN_DIR", str(shared))
    tool = Tool(
        id="ruff",
        name="ruff",
        category="lint",
        cmd="ruff",
        methods=(
            Method(kind="script", params={"bin_dir": str(shared)}),
            Method(kind="uv-tool", params={"pypi_pkg": "ruff"}),
        ),
    )
    result = _resolve(tool, inventory=_readable(uv_tools={"ruff": "0.6.0"}), which=str(binary))
    assert result.owner == "unknown"
    assert result.active_path is not None
    assert result.unknown_reason is not None
    assert "not attributable to any candidate" in result.unknown_reason
    assert "more than one manager" not in result.unknown_reason


def test_resolve_ownership_is_idempotent_for_identical_inputs(tmp_path: Path) -> None:
    bin_dir = tmp_path / ".bun" / "bin"
    binary = _touch_executable(bin_dir, "bun")
    tool = _bun(str(bin_dir))
    inventory = _empty_readable()
    first = _resolve(tool, inventory=inventory, which=str(binary))
    second = _resolve(tool, inventory=inventory, which=str(binary))
    assert first == second


def test_sdkman_removal_hint_degrades_without_a_package() -> None:
    without_package = removal_hint(_record("sdkman"), "groovy")
    assert without_package is not None
    assert chr(96) not in without_package


def _cellar_binary(prefix: Path, formula: str, version: str, cmd: str) -> Path:
    return _touch_executable(prefix / "Cellar" / formula / version / "bin", cmd)


def _link_cellar(prefix: Path, formula: str, version: str, cmd: str) -> tuple[Path, Path]:
    binary = _cellar_binary(prefix, formula, version, cmd)
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / cmd
    link.symlink_to(binary)
    return binary, link


def _absent_sdkman(cmd: str, candidate: str | None = None) -> Tool:
    return _sdkman_tool("/no/such/sdkman/bin", cmd=cmd, candidate=candidate or cmd)


def test_undeclared_brew_cellar_groovy(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _binary, link = _link_cellar(prefix, "groovy", "4.0.24", "groovy")
    tool = _absent_sdkman("groovy")
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={"groovy": "4.0.24"}, brew_prefix=prefix),
        which=str(link),
    )
    assert result.owner == "brew"
    assert result.package == "groovy"
    assert result.confidence == "direct"
    assert result.current_version == "4.0.24"
    assert result.off_policy is True
    calls: list[list[str]] = []
    outcome = perform_update(
        UpdateTarget(tool=tool, ownership=result),
        platform=_MAC,
        runner=calls.append,
        resolve_tag=lambda _repo: "v1.0.0",
        tools={},
    )
    assert outcome.status == "updated"
    assert calls == [["brew", "upgrade", "groovy"]]


def test_undeclared_brew_cellar_java_formula_not_tool_id(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _binary, link = _link_cellar(prefix, "openjdk", "21.0.4", "java")
    result = _resolve(
        _absent_sdkman("java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which=str(link),
    )
    assert result.owner == "brew"
    assert result.package == "openjdk"
    assert result.confidence == "direct"
    assert result.off_policy is True


def test_undeclared_brew_cellar_left_behind_not_listed(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _binary, link = _link_cellar(prefix, "groovy", "4.0.24", "groovy")
    result = _resolve(
        _absent_sdkman("groovy"),
        inventory=_readable(brew_formulae={}, brew_prefix=prefix),
        which=str(link),
    )
    assert result.owner == "unknown"
    assert all(candidate.owner != "brew" for candidate in result.candidates)


def test_undeclared_brew_unreadable_inventory_is_unknown(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _binary, link = _link_cellar(prefix, "groovy", "4.0.24", "groovy")
    result = _resolve(
        _absent_sdkman("groovy"),
        inventory=ManagerInventory(
            brew_formulae=None,
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=prefix,
        ),
        which=str(link),
    )
    assert result.owner == "unknown"
    assert all(candidate.owner != "brew" for candidate in result.candidates)


def test_undeclared_brew_bad_cellar_name(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    name = "bad;name"
    _binary, link = _link_cellar(prefix, name, "1.0", "groovy")
    result = _resolve(
        _absent_sdkman("groovy"),
        inventory=_readable(brew_formulae={name: "1.0"}, brew_prefix=prefix),
        which=str(link),
    )
    assert result.owner == "unknown"
    assert all(candidate.owner != "brew" for candidate in result.candidates)


def test_undeclared_brew_shadowed_by_sdkman(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _cellar_binary(prefix, "openjdk", "21.0.4", "java")
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java").symlink_to(prefix / "Cellar" / "openjdk" / "21.0.4" / "bin" / "java")
    sdk_bin = tmp_path / "sdk" / "candidates" / "java" / "current" / "bin"
    sdk_java = _touch_executable(sdk_bin, "java")
    result = _resolve(
        _sdkman_tool(str(sdk_bin), cmd="java", candidate="java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which=str(sdk_java),
    )
    assert result.owner == "sdkman"
    assert result.confidence == "direct"
    assert result.shadowed is True
    assert result.off_policy is False
    assert any(
        candidate.owner == "brew" and candidate.package == "openjdk"
        for candidate in result.candidates
    )


def test_undeclared_brew_shadowed_by_os_package(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _cellar_binary(prefix, "openjdk", "21.0.4", "java")
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java").symlink_to(prefix / "Cellar" / "openjdk" / "21.0.4" / "bin" / "java")
    calls: list[list[str]] = []
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    result = _resolve(
        _absent_sdkman("java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which="/usr/bin/java",
        platform=platform,
        native_probe=_os_package_probe("java-21-openjdk-headless", calls),
    )
    assert result.owner == "os-package"
    assert result.package == "java-21-openjdk-headless"
    assert result.confidence == "direct"
    assert result.off_policy is False
    assert result.shadowed is True
    assert result.candidates[0].owner == "os-package"
    assert any(
        candidate.owner == "brew" and candidate.package == "openjdk"
        for candidate in result.candidates
    )
    assert calls


def test_undeclared_brew_keg_only_shadowed_by_sdkman(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _cellar_binary(prefix, "openjdk", "21.0.4", "java")
    opt = prefix / "opt" / "openjdk"
    opt.parent.mkdir(parents=True)
    opt.symlink_to(prefix / "Cellar" / "openjdk" / "21.0.4")
    sdk_bin = tmp_path / "sdk" / "candidates" / "java" / "current" / "bin"
    sdk_java = _touch_executable(sdk_bin, "java")
    result = _resolve(
        _sdkman_tool(str(sdk_bin), cmd="java", candidate="java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which=str(sdk_java),
    )
    assert result.owner == "sdkman"
    assert result.shadowed is True
    assert result.off_policy is False
    assert any(
        candidate.owner == "brew" and candidate.package == "openjdk"
        for candidate in result.candidates
    )


def test_undeclared_brew_off_path_groovy(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _link_cellar(prefix, "groovy", "4.0.24", "groovy")
    result = _resolve(
        _absent_sdkman("groovy"),
        inventory=_readable(brew_formulae={"groovy": "4.0.24"}, brew_prefix=prefix),
        which=None,
    )
    assert result.owner == "brew"
    assert result.package == "groovy"
    assert result.confidence == "by-elimination"
    assert result.off_policy is True


def test_undeclared_brew_dangling_link(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    link = bin_dir / "groovy"
    link.symlink_to(prefix / "Cellar" / "groovy" / "4.0.24" / "bin" / "groovy")
    result = _resolve(
        _absent_sdkman("groovy"),
        inventory=_readable(brew_formulae={"groovy": "4.0.24"}, brew_prefix=prefix),
        which=str(link),
    )
    assert result.owner == "unknown"
    assert all(candidate.owner != "brew" for candidate in result.candidates)


def _candidate(
    owner: Owner, package: str | None = None, method: Method | None = None
) -> OwnershipCandidate:
    return OwnershipCandidate(
        owner=owner,
        method=method,
        package=package,
        current_version=None,
        evidence="test",
    )


def test_declared_manager_label_names_the_first_applicable_method() -> None:
    assert declared_manager_label(_sdkman_tool("/no/such/bin"), _MAC) == "SDKMAN"
    release = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="github_release", params={"repo": "BurntSushi/ripgrep"}),),
    )
    assert declared_manager_label(release, _MAC) == "GitHub release"
    skipped = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="apt", params={"package": "ripgrep"}, os=("debian",)),),
    )
    assert declared_manager_label(skipped, _MAC) is None


def test_declared_manager_label_native_kind() -> None:
    fedora = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    dnf_tool = Tool(
        id="jq",
        name="jq",
        category="search",
        cmd="jq",
        methods=(Method(kind="dnf", params={"package": "jq"}),),
    )
    assert declared_manager_label(dnf_tool, fedora) == "dnf"
    atomic = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    ostree = Tool(
        id="jq",
        name="jq",
        category="search",
        cmd="jq",
        methods=(Method(kind="rpm_ostree", params={"package": "jq"}),),
    )
    assert declared_manager_label(ostree, atomic) == "rpm-ostree"


def test_off_policy_requires_a_declared_policy(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _binary, link = _link_cellar(prefix, "demo", "1.0", "demo")
    tool = Tool(
        id="demo",
        name="demo",
        category="search",
        cmd="demo",
        methods=(Method(kind="apt", params={"package": "demo"}, os=("debian",)),),
    )
    result = _resolve(
        tool,
        inventory=_readable(brew_formulae={"demo": "1.0"}, brew_prefix=prefix),
        which=str(link),
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
    )
    assert result.owner == "brew"
    assert result.off_policy is False


def test_also_installed_note_names_the_other_manager() -> None:
    sdk = Method(kind="sdkman", params={"candidate": "java"})
    record = replace(
        _record("brew", package="openjdk"),
        candidates=(_candidate("brew", "openjdk"), _candidate("sdkman", "java", sdk)),
        shadowed=True,
    )
    assert also_installed_note(record) == "also installed via SDKMAN"
    assert also_installed_note(_record("brew")) is None


def test_also_installed_note_joins_other_owners_in_candidate_order() -> None:
    release = Method(kind="github_release", params={"repo": "o/r"})
    record = replace(
        _record("sdkman"),
        candidates=(
            _candidate("brew", "openjdk"),
            _candidate("installer", method=release),
            _candidate("sdkman", "java"),
        ),
    )
    assert also_installed_note(record) == "also installed via Homebrew, GitHub release"


def test_also_installed_note_names_homebrew_when_sdkman_is_active(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _cellar_binary(prefix, "openjdk", "21.0.4", "java")
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java").symlink_to(prefix / "Cellar" / "openjdk" / "21.0.4" / "bin" / "java")
    sdk_bin = tmp_path / "sdk" / "candidates" / "java" / "current" / "bin"
    sdk_java = _touch_executable(sdk_bin, "java")
    result = _resolve(
        _sdkman_tool(str(sdk_bin), cmd="java", candidate="java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which=str(sdk_java),
    )
    assert also_installed_note(result) == "also installed via Homebrew"


def test_also_installed_note_names_homebrew_when_os_package_is_active(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _cellar_binary(prefix, "openjdk", "21.0.4", "java")
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java").symlink_to(prefix / "Cellar" / "openjdk" / "21.0.4" / "bin" / "java")
    calls: list[list[str]] = []
    result = _resolve(
        _absent_sdkman("java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which="/usr/bin/java",
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        native_probe=_os_package_probe("java-21-openjdk-headless", calls),
    )
    assert also_installed_note(result) == "also installed via Homebrew"


def test_also_installed_note_names_homebrew_for_keg_only_shadow(tmp_path: Path) -> None:
    prefix = tmp_path / "brew"
    _cellar_binary(prefix, "openjdk", "21.0.4", "java")
    opt = prefix / "opt" / "openjdk"
    opt.parent.mkdir(parents=True)
    opt.symlink_to(prefix / "Cellar" / "openjdk" / "21.0.4")
    sdk_bin = tmp_path / "sdk" / "candidates" / "java" / "current" / "bin"
    sdk_java = _touch_executable(sdk_bin, "java")
    result = _resolve(
        _sdkman_tool(str(sdk_bin), cmd="java", candidate="java"),
        inventory=_readable(brew_formulae={"openjdk": "21.0.4"}, brew_prefix=prefix),
        which=str(sdk_java),
    )
    assert also_installed_note(result) == "also installed via Homebrew"


def test_active_path_note_names_the_resolved_path() -> None:
    path = Path("/opt/homebrew/Cellar/groovy/4.0.24/bin/groovy")
    record = replace(
        _record("unknown"),
        active_path=path,
        unknown_reason="no manager claimed the tool",
    )
    assert active_path_note(record) == f"active binary resolves to {path}"


def test_active_path_note_is_silent_when_already_named_or_known() -> None:
    path = Path("/usr/bin/java")
    named = replace(
        _record("unknown"),
        active_path=path,
        unknown_reason=f"the active binary at {path} is not attributable to any candidate",
    )
    assert active_path_note(named) is None
    assert active_path_note(_record("brew")) is None
    assert active_path_note(_record("unknown")) is None


def test_undeclared_script_only_by_elimination_unchanged(tmp_path: Path) -> None:
    tool = Tool(
        id="bun",
        name="bun",
        category="runtime",
        cmd="bun",
        methods=(Method(kind="script", params={"url": "https://example.invalid/install.sh"}),),
    )
    result = _resolve(tool, inventory=_empty_readable(), artifacts=[tmp_path / "bun"], which=None)
    assert result.owner == "installer"
    assert result.confidence == "by-elimination"
    assert result.method is None
