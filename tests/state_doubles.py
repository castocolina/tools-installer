"""Offline tool-state services for screen tests.

Every service built here is a real `VersionRefreshService` with offline fakes.
`skill_home` is required, and the managed bin dir lives under it, so no
test-built service reads the developer's home (checker W5).
"""

from collections.abc import Callable, Collection, Sequence
from datetime import datetime
from pathlib import Path

from installer.manager_versions import OutdatedReport
from installer.model import Tool
from installer.ownership import ManagerInventory
from installer.platform import Platform
from installer.version_status import VersionRefreshService


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
    present: Callable[[Tool], bool] | None = None,
) -> VersionRefreshService:
    """A service with no first pass. By default every command resolves into
    the scratch managed bin dir, so every tool reads present and installer-owned."""
    managed = skill_home / ".local" / "bin"
    return VersionRefreshService(
        platform=platform or Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        cache_path=cache_path,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        now=now,
        managed_bin_dir=managed,
        which=which or (lambda cmd: str(managed / cmd)),
        artifacts_for=artifacts_for or (lambda tool: [managed / tool.cmd]),
        read_inventory_fn=read_inventory_fn,
        read_outdated_fn=empty_outdated,
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
    which: Callable[[str], str | None] = lambda _cmd: None,
    resolve_tag: Callable[[str], str] = _no_release,
    probe_output: Callable[[list[str]], str | None] = _no_version,
    artifacts_for: Callable[[Tool], list[Path]] = lambda _tool: [],
    read_inventory_fn: Callable[..., ManagerInventory] = empty_inventory,
    skill_probe: Callable[[list[str]], str] | None = None,
) -> VersionRefreshService:
    """A service after one completed `refresh(tools)`: the ids in `present`
    read present, nothing is on PATH unless `which` says so, and skill packs
    are probed when `skill_probe` is given."""
    ids = frozenset(present)
    service = offline_service(
        cache_path,
        skill_home=home,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        platform=platform,
        which=which,
        artifacts_for=artifacts_for,
        read_inventory_fn=read_inventory_fn,
        skill_probe=skill_probe,
        present=lambda tool: tool.id in ids,
    )
    if skill_probe is not None:
        service.refresh_skills(tools)
    service.refresh(tools)
    return service
