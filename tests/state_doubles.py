"""Offline tool-state services for screen tests.

Every service built here is a real `VersionRefreshService` with offline fakes.
`skill_home` is required, and the managed bin dir lives under it, so no
test-built service reads the developer's home (checker W5).
"""

import threading
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import InstallStatus
from installer.manager_versions import OutdatedReport
from installer.model import ConfigStep, Method, Tool
from installer.ownership import Confidence, ManagerInventory, ManagerOwnership, Owner
from installer.platform import Platform
from installer.post_install import ConfirmSensitiveAction
from installer.run import Runner
from installer.uninstall import RemovalPlan
from installer.update import UpdateOutcome, UpdateService, UpdateTarget
from installer.version_status import (
    Health,
    SkillHostStatus,
    ToolState,
    VersionRefreshService,
    VersionStatus,
    ownership_notes,
    tool_state,
    version_notes,
)
from installer.versions import TagResolver

_MACOS = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
# Public alias for test modules that build plans on the same platform.
MACOS = _MACOS


def empty_inventory(**_kwargs: object) -> ManagerInventory:
    return ManagerInventory(
        brew_formulae={},
        brew_casks={},
        pnpm_globals=frozenset(),
        uv_tools={},
        brew_prefix=None,
    )


def empty_outdated(**_kwargs: object) -> OutdatedReport:
    return OutdatedReport(brew={}, cask={}, pnpm={}, uv={})


def _no_release(repo: str) -> str:
    raise OSError(f"offline test double: no release lookup for {repo}")


def _no_version(argv: list[str]) -> str | None:
    del argv
    return None


def offline_service(
    cache_path: Path,
    *,
    skill_home: Path,
    resolve_tag: Callable[[str], str],
    probe_output: Callable[[list[str]], str | None],
    now: Callable[[], datetime] | None = None,
    platform: Platform | None = None,
    which: Callable[[str], str | None] | None = None,
    native_probe: Callable[[list[str]], str] | None = None,
    artifacts_for: Callable[[Tool], list[Path]] | None = None,
    skill_probe: Callable[[list[str]], str] | None = None,
    read_inventory_fn: Callable[..., ManagerInventory] = empty_inventory,
    read_outdated_fn: Callable[..., OutdatedReport] = empty_outdated,
    present: Callable[[Tool], bool] | None = None,
) -> VersionRefreshService:
    """A service with no first pass. By default every command resolves into
    the scratch managed bin dir, so every tool reads present and installer-owned."""
    managed = skill_home / ".local" / "bin"
    return VersionRefreshService(
        platform=platform or _MACOS,
        cache_path=cache_path,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        now=now,
        managed_bin_dir=managed,
        which=which or (lambda cmd: str(managed / cmd)),
        artifacts_for=artifacts_for or (lambda tool: [managed / tool.cmd]),
        read_inventory_fn=read_inventory_fn,
        read_outdated_fn=read_outdated_fn,
        pnpm_packages=lambda: (),
        query=lambda *_a, **_k: "",
        native_probe=native_probe,
        skill_probe=skill_probe,
        skill_home=skill_home,
        present=present,
    )


def seeded_service(
    tools: Sequence[Tool],
    *,
    cache_path: Path,
    home: Path,
    present: Collection[str] = frozenset(),
    platform: Platform | None = None,
    which: Callable[[str], str | None] | None = None,
    resolve_tag: Callable[[str], str] = _no_release,
    probe_output: Callable[[list[str]], str | None] = _no_version,
    artifacts_for: Callable[[Tool], list[Path]] = lambda _tool: [],
    read_inventory_fn: Callable[..., ManagerInventory] = empty_inventory,
    read_outdated_fn: Callable[..., OutdatedReport] = empty_outdated,
    skill_probe: Callable[[list[str]], str] | None = None,
) -> VersionRefreshService:
    """A service after one completed `refresh(tools)`: the ids in `present`
    read present, and skill packs are probed when `skill_probe` is given. By
    default only brew is on PATH (under `home`), so brew-method tools can
    install and no tool binary is found."""
    ids = frozenset(present)
    brew = str(home / "homebrew" / "bin" / "brew")

    def brew_only(cmd: str) -> str | None:
        return brew if cmd == "brew" else None

    service = offline_service(
        cache_path,
        skill_home=home,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        platform=platform,
        which=which or brew_only,
        artifacts_for=artifacts_for,
        read_inventory_fn=read_inventory_fn,
        read_outdated_fn=read_outdated_fn,
        skill_probe=skill_probe,
        present=lambda tool: tool.id in ids,
    )
    if skill_probe is not None:
        service.refresh_skills(tools)
    service.refresh(tools)
    return service


class ScriptedUpdates(UpdateService):
    """Offline update service with the real in-flight latch and scripted outcomes."""

    def __init__(self, outcomes: Mapping[str, UpdateOutcome | Exception]) -> None:
        super().__init__(
            platform=_MACOS,
            runner=lambda _command: None,
            resolve_tag=lambda _repo: "v1",
            tools={},
            managed_packages=lambda: (),
            replay_globals=lambda packages: tuple(packages),
            reresolve_ownership=unknown_ownership,
        )
        self.outcomes = outcomes
        self.targets: list[UpdateTarget] = []

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.targets.append(target)
        outcome = self.outcomes[target.tool.id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RunRecorder:
    """Record install calls and commands without touching the host."""

    def __init__(self, outcomes: Mapping[str, InstallOutcome | Exception] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.installs: list[tuple[str, bool]] = []
        self.confirms: list[ConfirmSensitiveAction | None] = []
        self.argv: list[list[str]] = []
        self.synced = 0

    def install(
        self,
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
        repair: bool = False,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools
        self.installs.append((tool.id, repair))
        self.confirms.append(confirm_sensitive_action)
        outcome = self.outcomes.get(tool.id, InstallOutcome(tool.id, InstallStatus.INSTALLED))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def runner(self, command: list[str]) -> None:
        self.argv.append(command)

    def terminal_sync(self) -> str | None:
        self.synced += 1
        return None


class FrozenStateService(VersionRefreshService):
    """A machine that never changes: `publish` sets the states, and a refresh
    re-publishes them at the current epoch without probing anything."""

    def publish(self, states: Iterable[ToolState]) -> None:
        with self._lock:
            stamped = {state.tool_id: replace(state, generation=self._epoch) for state in states}
            self._states = {**self._states, **stamped}

    def assume_present(self, answer: Callable[[Tool], bool]) -> None:
        """Answer presence from the probe for a tool with no published state.

        A published state still wins, so a missing ownership snapshot stays
        missing (the worker refreshes it) while presence answers `answer`.
        """
        self._present = answer

    def refresh(self, tools: Sequence[Tool]) -> None:
        del tools
        self.publish(list(self._states.values()))

    def refresh_skills(self, tools: Sequence[Tool]) -> dict[str, SkillHostStatus]:
        del tools
        return {
            tool_id: state.skill_hosts
            for tool_id, state in self._states.items()
            if state.skill_hosts is not None
        }


class HeldRefreshService(FrozenStateService):
    """A frozen service whose refresh waits until the test releases it."""

    def __init__(
        self,
        home: Path,
        pending: Iterable[ToolState],
        *,
        raising: Exception | None = None,
        platform: Platform | None = None,
    ) -> None:
        super().__init__(
            platform=platform or _MACOS,
            cache_path=home / "versions.json",
            resolve_tag=_no_release,
            probe_output=_no_version,
            managed_bin_dir=home / ".local" / "bin",
            which=lambda _cmd: None,
            artifacts_for=lambda _tool: [],
            read_inventory_fn=empty_inventory,
            read_outdated_fn=empty_outdated,
            pnpm_packages=lambda: (),
            query=lambda *_a, **_k: "",
            native_probe=_probe_nothing,
            skill_probe=_probe_nothing,
            skill_home=home,
            present=lambda _tool: False,
        )
        self.pending = tuple(pending)
        self.raising = raising
        self.release = threading.Event()
        self.calls: list[frozenset[str]] = []

    def refresh(self, tools: Sequence[Tool]) -> None:
        self.calls.append(frozenset(tool.id for tool in tools))
        self.release.wait()
        error = self.raising
        if error is not None:
            raise error
        self.publish(self.pending)


def _probe_nothing(argv: list[str]) -> str:
    raise OSError(f"frozen test double: no probe for {argv}")


def frozen_service(home: Path, *, platform: Platform | None = None) -> FrozenStateService:
    """A FrozenStateService with no states yet; every probe raises."""
    return FrozenStateService(
        platform=platform or _MACOS,
        cache_path=home / "versions.json",
        resolve_tag=_no_release,
        probe_output=_no_version,
        managed_bin_dir=home / ".local" / "bin",
        which=lambda _cmd: None,
        artifacts_for=lambda _tool: [],
        read_inventory_fn=empty_inventory,
        read_outdated_fn=empty_outdated,
        pnpm_packages=lambda: (),
        query=lambda *_a, **_k: "",
        native_probe=_probe_nothing,
        skill_probe=_probe_nothing,
        skill_home=home,
        present=lambda _tool: False,
    )


def held_service(
    home: Path,
    pending: Iterable[ToolState],
    *,
    raising: Exception | None = None,
    platform: Platform | None = None,
) -> HeldRefreshService:
    return HeldRefreshService(home, pending, raising=raising, platform=platform)


def unknown_ownership(tool: Tool) -> ManagerOwnership:
    return ManagerOwnership(
        tool_id=tool.id,
        owner="unknown",
        method=None,
        package=None,
        current_version=None,
        confidence="none",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )


def pass_state(
    tool: Tool,
    *,
    platform: Platform,
    present: bool = True,
    ownership: ManagerOwnership | None = None,
    version: VersionStatus | None = None,
    skill_hosts: SkillHostStatus | None = None,
    broken: tuple[str, ...] = (),
    misconfigured: tuple[str, ...] = (),
    unconfigured: tuple[ConfigStep, ...] = (),
    notes: tuple[str, ...] = (),
) -> ToolState:
    """A state built the way the refresh pass builds one: the owner and
    version sentences come first among the notes."""
    owner = ownership if ownership is not None else unknown_ownership(tool)
    pass_notes = ownership_notes(tool, owner, platform)
    if version is not None:
        pass_notes += version_notes(tool, version, owner, present=present)
    return tool_state(
        tool,
        generation=0,
        platform=platform,
        present=present,
        ownership=owner,
        version=version,
        removable=RemovalPlan(removable=(), yourself=()),
        skill_hosts=skill_hosts,
        broken=broken,
        misconfigured=misconfigured,
        unconfigured=unconfigured,
        notes=pass_notes + notes,
    )


def plan_state(
    tool: Tool,
    *,
    platform: Platform = _MACOS,
    health: Health = Health.OK,
    owner: Owner = "installer",
    confidence: Confidence = "direct",
    off_policy: bool = False,
    reasons: tuple[str, ...] = (),
    version: VersionStatus | None = None,
    unconfigured: tuple[ConfigStep, ...] = (),
    method: Method | None = None,
    present: bool = True,
) -> ToolState:
    """A published state for one tool with the health and owner a plan test needs.

    `pass_state` never forwards a receipt, so every state built here carries
    `receipt=None`. CHECKING is not built here: a test expresses it by making
    `state_of` return None.
    """
    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=method,
        package=None,
        current_version=None,
        confidence=confidence,
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
        off_policy=off_policy,
    )
    if health is Health.OUTDATED and version is None:
        version = VersionStatus(
            tool_id=tool.id,
            installed="1.0",
            latest="2.0",
            outdated=True,
            stale=False,
            source="test",
        )
    broken = reasons if health is Health.BROKEN else ()
    misconfigured = reasons if health is Health.MISCONFIGURED else ()
    notes = reasons if health not in (Health.BROKEN, Health.MISCONFIGURED) else ()
    return pass_state(
        tool,
        platform=platform,
        present=present and health is not Health.MISSING and health is not Health.UNAVAILABLE,
        ownership=ownership,
        version=version,
        unconfigured=unconfigured,
        broken=broken,
        misconfigured=misconfigured,
        notes=notes,
    )


Presence = Collection[str] | Callable[[Tool], bool]


def presence_service(
    catalog: Iterable[Tool],
    *,
    present: Presence = (),
    states: Iterable[ToolState] = (),
    platform: Platform | None = None,
    service: VersionRefreshService | None = None,
) -> VersionRefreshService:
    """The service a screen test reads presence from.

    `present` is a set of ids or a live predicate. Ids: without a `service`, a
    frozen one under `Path.home()` (the conftest sandbox points that at a
    scratch HOME) publishes OK for each catalog tool in `present` and MISSING
    for the rest. A predicate is only probed, never published, so a test that
    flips its answer mid-run is seen at the next read. A `service` the test built
    keeps its own published states, so a deliberately missing ownership snapshot
    stays missing. Only a frozen service has a probe, so any other service
    passes through unchanged and must not be given presence.
    """
    if service is None:
        target = frozen_service(Path.home() / "state", platform=platform)
    elif isinstance(service, FrozenStateService):
        target = service
    else:
        assert not present and not states, "presence needs a FrozenStateService"
        return service
    if callable(present):
        target.assume_present(present)
        published: list[ToolState] = []
    else:
        ids = present
        target.assume_present(lambda tool: tool.id in ids)
        published = (
            []
            if service is not None
            else [
                plan_state(tool, health=Health.OK if tool.id in ids else Health.MISSING)
                for tool in catalog
            ]
        )
    target.publish([*published, *states])
    return target
