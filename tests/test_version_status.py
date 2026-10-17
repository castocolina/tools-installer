import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

import pytest

from installer import download, executors, receipts, uninstall, version_status
from installer.engine import InstallOutcome, install_tool
from installer.enums import InstallStatus
from installer.guards import REDIRECT_SENTINEL
from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.model import (
    ConfigStep,
    Method,
    SkillLifecycle,
    SkillOperation,
    SkillStatusProbe,
    SkillTarget,
    Tool,
    load_tools,
)
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    Owner,
    OwnershipCandidate,
    also_installed_note,
    declared_manager_label,
    owner_label,
    resolve_ownership,
)
from installer.platform import Platform
from installer.receipts import Receipt, ReceiptMethod
from installer.resolve import resolve_methods, unavailable_reason
from installer.skill_lifecycle import HARNESS_PRESENCE, inspect_skill_reports, inspect_status
from installer.terminal_shell import TerminalShellResult
from installer.uninstall import RemovalPlan, plan_removal
from installer.version_cache import (
    MANAGER_RETRY_BACKOFF,
    MANAGER_STALE_AFTER,
    ManagerSnapshot,
    VersionCacheEntry,
    encode_manager_snapshot,
    load_manager_snapshot,
    load_skill_statuses,
    load_version_cache,
    save_version_cache,
    should_fetch_managers,
)
from installer.version_status import (
    BROKEN_SHIM_REASON,
    MAX_FETCHES_PER_REFRESH,
    NEEDS_BREW_REASON,
    Health,
    SkillHostStatus,
    ToolState,
    VersionRefreshService,
    VersionStatus,
    ownership_notes,
    resolve_github_release_status,
    resolve_status,
    tool_state,
    version_notes,
)
from installer.versions import Release, VersionError, resolve_github_tag
from tests.test_download import fixture_runner
from tests.test_registry import REGISTRY

_MANAGED = Path("/tmp/tools-installer-bin")


def _empty_inventory(**_kwargs: object) -> ManagerInventory:
    return ManagerInventory(
        brew_formulae={},
        brew_casks={},
        pnpm_globals=frozenset(),
        uv_tools={},
        brew_prefix=None,
    )


def _empty_outdated(**_kwargs: object) -> OutdatedReport:
    return OutdatedReport(brew={}, cask={}, pnpm={}, uv={})


def _versions(service: VersionRefreshService, tools: Sequence[Tool]) -> dict[str, VersionStatus]:
    """Run one pass and read each tool's version back through `state_of` (D-03)."""
    service.refresh(tools)
    states = {tool.id: service.state_of(tool.id) for tool in tools}
    return {
        tool_id: state.version
        for tool_id, state in states.items()
        if state is not None and state.version is not None
    }


def _held_skills(service: VersionRefreshService) -> dict[str, SkillHostStatus]:
    """The held skill-host answers: `refresh_skills` over no pack probes nothing."""
    return service.refresh_skills(())


def _installer_owned_service(
    cache_path: Path,
    *,
    resolve_tag: Callable[[str], str],
    probe_output: Callable[[list[str]], str | None],
    now: Callable[[], datetime],
) -> VersionRefreshService:
    return VersionRefreshService(
        platform=_platform(),
        cache_path=cache_path,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        now=now,
        managed_bin_dir=_MANAGED,
        which=lambda cmd: str(_MANAGED / cmd),
        artifacts_for=lambda tool: [_MANAGED / tool.cmd],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        query=lambda *_args, **_kwargs: "",
    )


def _native_owned_service(
    cache_path: Path,
    *,
    resolve_tag: Callable[[str], str],
    probe_output: Callable[[list[str]], str | None],
    now: Callable[[], datetime],
    native_probe: Callable[[list[str]], str] | None,
) -> VersionRefreshService:
    return VersionRefreshService(
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        cache_path=cache_path,
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        now=now,
        managed_bin_dir=_MANAGED,
        # An unattributable live path -- THE CASE THAT MATTERS: a real
        # dnf-installed tool has a live /usr/bin/<cmd> attribute_path cannot
        # map to any tracked owner.
        which=lambda cmd: f"/usr/bin/{cmd}",
        artifacts_for=lambda tool: [],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        query=lambda *_args, **_kwargs: "",
        native_probe=native_probe,
    )


def _jq_tool() -> Tool:
    return Tool(
        id="jq",
        name="jq",
        category="data",
        cmd="jq",
        methods=(Method(kind="dnf", params={"package": "jq"}),),
        owner_probes=("dnf",),
    )


def _codegraph() -> Tool:
    return Tool(
        id="codegraph",
        name="codegraph",
        category="ai",
        cmd="codegraph",
        methods=(Method(kind="github_release", params={"repo": "colbymchenry/codegraph"}),),
        priority="P1",
        audience="ai",
        tier="ai",
    )


def _platform() -> Platform:
    return Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


def test_codegraph_status_is_outdated_and_not_stale_after_a_successful_fetch(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    calls: list[str] = []

    def resolve_tag(repo: str) -> str:
        calls.append(repo)
        return "v1.6.0"

    status, entry = resolve_github_release_status(
        _codegraph(),
        repo="colbymchenry/codegraph",
        entry=None,
        now=now,
        probe_output=lambda argv: "1.2.0",
        resolve_tag=resolve_tag,
    )
    assert calls == ["colbymchenry/codegraph"]
    assert status.installed == "1.2.0"
    assert status.latest == "v1.6.0"
    assert status.outdated is True
    assert status.stale is False
    assert status.source == "github"
    assert entry is not None
    assert entry.checked_at is not None
    assert entry.failed_at is None

    service = _installer_owned_service(
        tmp_path / "versions.json",
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "1.2.0",
        now=lambda: now,
    )
    statuses = _versions(service, [_codegraph()])
    assert statuses["codegraph"].outdated is True
    raw = json.loads((tmp_path / "versions.json").read_text())
    assert "checked_at" in raw["tools"]["codegraph"]


def test_preserved_older_latest_is_stale_after_a_failed_fetch() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    old = VersionCacheEntry(
        latest_version="v1.5.0",
        checked_at=(now - timedelta(days=8)).isoformat(),
        failed_at=None,
    )

    def resolve_tag(repo: str) -> str:
        raise VersionError("rate limited")

    status, entry = resolve_github_release_status(
        _codegraph(),
        repo="colbymchenry/codegraph",
        entry=old,
        now=now,
        probe_output=lambda argv: "1.2.0",
        resolve_tag=resolve_tag,
    )
    assert status.latest == "v1.5.0"
    assert status.stale is True
    assert entry is not None
    assert entry.latest_version == "v1.5.0"
    assert entry.checked_at == old.checked_at
    assert entry.failed_at is not None


_DIGEST_A = "a" * 64


def test_refresh_stores_digests_from_one_read(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    calls: list[str] = []

    def fake_resolver(_resolve_tag: object) -> Callable[[str], Release]:
        def resolve(repo: str) -> Release:
            calls.append(repo)
            return Release("v1.2.0", {"a.tar.gz": _DIGEST_A})

        return resolve

    monkeypatch.setattr("installer.version_status.release_resolver", fake_resolver)
    _status, entry = resolve_github_release_status(
        _codegraph(),
        repo="colbymchenry/codegraph",
        entry=None,
        now=now,
        probe_output=lambda argv: "1.2.0",
        resolve_tag=lambda repo: "v1.2.0",
    )
    assert calls == ["colbymchenry/codegraph"]
    assert entry is not None
    assert entry.latest_version == "v1.2.0"
    assert entry.digests == {"a.tar.gz": _DIGEST_A}


def test_failed_refresh_keeps_the_previous_digests(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    old = VersionCacheEntry(
        latest_version="v1.5.0",
        checked_at=(now - timedelta(days=8)).isoformat(),
        failed_at=None,
        digests={"a.tar.gz": _DIGEST_A},
    )

    def fake_resolver(_resolve_tag: object) -> Callable[[str], Release]:
        def resolve(_repo: str) -> Release:
            raise VersionError("rate limited")

        return resolve

    monkeypatch.setattr("installer.version_status.release_resolver", fake_resolver)
    _status, entry = resolve_github_release_status(
        _codegraph(),
        repo="colbymchenry/codegraph",
        entry=old,
        now=now,
        probe_output=lambda argv: "1.2.0",
        resolve_tag=lambda repo: "v9.9.9",
    )
    assert entry is not None
    assert entry.digests == {"a.tar.gz": _DIGEST_A}
    assert entry.failed_at is not None


def test_refresh_reads_tag_and_digests_from_one_api_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    calls = 0

    class FakeResp:
        def __enter__(self) -> "FakeResp":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "tag_name": "v1.2.0",
                    "assets": [{"name": "a.tar.gz", "digest": f"sha256:{_DIGEST_A}"}],
                }
            ).encode()

    def fake_urlopen(_req: urllib.request.Request, timeout: int) -> FakeResp:
        nonlocal calls
        calls += 1
        return FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    _status, entry = resolve_github_release_status(
        _codegraph(),
        repo="colbymchenry/codegraph",
        entry=None,
        now=now,
        probe_output=lambda argv: "1.2.0",
        resolve_tag=resolve_github_tag,
    )
    assert calls == 1
    assert entry is not None
    assert entry.latest_version == "v1.2.0"
    assert entry.digests == {"a.tar.gz": _DIGEST_A}


def _gh_tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind="github_release", params={"repo": f"owner/{tool_id}"}),),
        priority="P1",
        audience="both",
        tier="user",
    )


def test_fresh_cache_after_restart_reconstructs_status_without_fetching(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    save_version_cache(
        path,
        {
            "codegraph": VersionCacheEntry(
                latest_version="v1.6.0",
                checked_at=now.isoformat(),
                failed_at=None,
            )
        },
    )
    calls: list[str] = []

    def resolve_tag(repo: str) -> str:
        calls.append(repo)
        return "v9.9.9"

    restarted = _installer_owned_service(
        path,
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "1.2.0",
        now=lambda: now,
    )
    statuses = _versions(restarted, [_codegraph()])
    assert calls == []
    assert statuses["codegraph"].latest == "v1.6.0"
    assert statuses["codegraph"].stale is False


def test_version_error_preserves_latest_and_records_failed_at(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    save_version_cache(
        path,
        {
            "codegraph": VersionCacheEntry(
                latest_version="v1.5.0",
                checked_at=(now - timedelta(days=8)).isoformat(),
                failed_at=None,
            )
        },
    )

    def resolve_tag(repo: str) -> str:
        raise VersionError("offline")

    service = _installer_owned_service(
        path,
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "1.2.0",
        now=lambda: now,
    )
    statuses = _versions(service, [_codegraph()])
    assert statuses["codegraph"].latest == "v1.5.0"
    assert statuses["codegraph"].outdated is True
    cached = load_version_cache(path)["codegraph"]
    assert cached.failed_at is not None
    assert cached.latest_version == "v1.5.0"
    assert cached.checked_at is not None


def test_fetch_budget_caps_resolve_tag_calls(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    calls: list[str] = []

    def resolve_tag(repo: str) -> str:
        calls.append(repo)
        return "v1.0.0"

    tools = [_gh_tool(f"tool-{i:02d}") for i in range(25)]
    service = _installer_owned_service(
        tmp_path / "versions.json",
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "0.9.0",
        now=lambda: now,
    )
    statuses = _versions(service, tools)
    assert len(calls) == MAX_FETCHES_PER_REFRESH
    assert len(statuses) == 25
    deferred = [tool.id for tool in tools[MAX_FETCHES_PER_REFRESH:]]
    assert all(statuses[tool_id].stale is True for tool_id in deferred)


def test_one_service_two_threads_merge_both_tool_ids(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    inside = threading.Barrier(2)
    release = threading.Event()
    path = tmp_path / "versions.json"

    def resolve_tag(repo: str) -> str:
        inside.wait(timeout=5)
        release.wait(timeout=5)
        return "v1.0.0"

    service = _installer_owned_service(
        path,
        resolve_tag=resolve_tag,
        probe_output=lambda argv: "0.9.0",
        now=lambda: now,
    )
    left = [_gh_tool("alpha")]
    right = [_gh_tool("beta")]
    errors: list[BaseException] = []

    def run(tools: list[Tool]) -> None:
        try:
            service.refresh(tools)
        except BaseException as exc:  # noqa: BLE001 — collect for the join
            errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(left,)),
        threading.Thread(target=run, args=(right,)),
    ]
    for thread in threads:
        thread.start()
    release.set()
    for thread in threads:
        thread.join(timeout=5)
    assert errors == []
    cached = load_version_cache(path)
    assert set(cached) == {"alpha", "beta"}


def _brew_tool() -> Tool:
    return Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "ripgrep"}),),
    )


def _cask_tool() -> Tool:
    return Tool(
        id="rectangle",
        name="Rectangle",
        category="dev",
        cmd="rectangle",
        methods=(Method(kind="cask", params={"cask": "rectangle"}),),
    )


def _node_tool(*, pinned: bool = False) -> Tool:
    params: dict[str, object] = {"npm_pkg": "@mermaid-js/mermaid-cli"}
    if pinned:
        params["versions"] = {"puppeteer": "^25"}
    return Tool(
        id="mmdc",
        name="mmdc",
        category="diagram",
        cmd="mmdc",
        methods=(Method(kind="node", params=params),),
    )


def _uv_tool() -> Tool:
    return Tool(
        id="ruff",
        name="ruff",
        category="dev",
        cmd="ruff",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "ruff"}),),
    )


def _owned(
    tool: Tool,
    owner: Owner,
    *,
    method: Method | None = None,
    package: str | None = None,
    current_version: str | None = None,
) -> ManagerOwnership:
    chosen = method if method is not None else (tool.methods[0] if tool.methods else None)
    candidate = OwnershipCandidate(
        owner=owner,
        method=chosen,
        package=package,
        current_version=current_version,
        evidence="test",
    )
    return ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=chosen,
        package=package,
        current_version=current_version,
        confidence="direct",
        shadowed=False,
        candidates=(candidate,),
        active_candidate=owner,
        active_path=Path("/opt/homebrew/bin") / tool.cmd,
        unknown_reason=None,
    )


def _fresh_manager_snapshot(*, minutes_ago: int = 1) -> ManagerSnapshot:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    checked = (now - timedelta(minutes=minutes_ago)).isoformat()
    return ManagerSnapshot(
        inventory=ManagerInventory(
            brew_formulae={"ripgrep": "14.1.0"},
            brew_casks={"rectangle": "0.85"},
            pnpm_globals=frozenset({"@mermaid-js/mermaid-cli"}),
            uv_tools={"ruff": "0.6.0"},
            brew_prefix=Path("/opt/homebrew"),
        ),
        outdated=OutdatedReport(
            brew={"ripgrep": ManagerVersion("14.1.0", "14.1.1")},
            cask={},
            pnpm={"@mermaid-js/mermaid-cli": ManagerVersion("11.0.0", "11.1.0")},
            uv={},
        ),
        checked_at=checked,
        failed_at=None,
    )


def _count_pnpm(counter: dict[str, int]) -> Callable[[], tuple[str, ...] | None]:
    def pnpm_packages() -> tuple[str, ...] | None:
        counter["n"] += 1
        return ()

    return pnpm_packages


def _which_for_fixture(cmd: str) -> str | None:
    if cmd == "mmdc":
        return str(Path.home() / "Library" / "pnpm" / "mmdc")
    if cmd == "ruff":
        # ~/.local/bin proves no uv ownership (D-12); ruff is uv-owned by elimination.
        return None
    return f"/opt/homebrew/bin/{cmd}"


def _counting_query() -> tuple[Callable[..., str], list[list[str]]]:
    """Records the manager snapshot queries only: the per-pass `uv tool dir`
    question (L-19-01) is answered but not counted here; its own test pins
    it to one per pass."""
    calls: list[list[str]] = []

    def query(cmd: list[str], **_kwargs: object) -> str:
        if cmd == ["uv", "tool", "dir"]:
            return "/home/u/.local/share/uv/tools\n"
        calls.append(cmd)
        if cmd == ["brew", "--prefix"]:
            return "/opt/homebrew\n"
        if cmd[:3] == ["brew", "list", "--versions"]:
            if "--formula" in cmd:
                return "ripgrep 14.1.0\n"
            return "rectangle 0.85\n"
        if cmd[:3] == ["uv", "tool", "list"]:
            if "--outdated" in cmd:
                return ""
            return "ruff v0.6.0\n"
        if cmd[0] == "brew" and "outdated" in cmd:
            return '{"formulae": [], "casks": []}'
        return "{}"

    return query, calls


def test_fresh_manager_snapshot_issues_zero_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PNPM_HOME", raising=False)
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    snapshot = _fresh_manager_snapshot()
    save_version_cache(path, {}, managers=encode_manager_snapshot(snapshot))
    query, calls = _counting_query()
    pnpm_calls = {"n": 0}

    def pnpm_packages() -> tuple[str, ...] | None:
        pnpm_calls["n"] += 1
        return ("@mermaid-js/mermaid-cli",)

    inventory_calls = {"n": 0}
    outdated_calls = {"n": 0}

    def read_inv(**_kwargs: object) -> ManagerInventory:
        inventory_calls["n"] += 1
        return snapshot.inventory

    def read_out(**_kwargs: object) -> OutdatedReport:
        outdated_calls["n"] += 1
        return snapshot.outdated

    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=pnpm_packages,
        read_inventory_fn=read_inv,
        read_outdated_fn=read_out,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    tools = [_brew_tool(), _cask_tool(), _node_tool(), _uv_tool()]
    statuses = _versions(service, tools)
    assert calls == []
    assert pnpm_calls["n"] == 0
    assert inventory_calls["n"] == 0
    assert outdated_calls["n"] == 0
    assert statuses["rg"].source == "brew"
    assert statuses["rectangle"].source == "cask"
    assert statuses["mmdc"].source == "pnpm"
    assert statuses["ruff"].source == "uv"


def test_stale_manager_snapshot_requeries_seven_plus_one(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    stale_minutes = int(MANAGER_STALE_AFTER.total_seconds() / 60) + 1
    snapshot = _fresh_manager_snapshot(minutes_ago=stale_minutes)
    save_version_cache(path, {}, managers=encode_manager_snapshot(snapshot))
    query, calls = _counting_query()
    pnpm_calls = {"n": 0}

    def pnpm_packages() -> tuple[str, ...] | None:
        pnpm_calls["n"] += 1
        return ("@mermaid-js/mermaid-cli",)

    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=pnpm_packages,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    service.refresh([_brew_tool(), _cask_tool(), _node_tool(), _uv_tool()])
    assert len(calls) == 7
    assert pnpm_calls["n"] == 1
    loaded = load_manager_snapshot(path)
    assert loaded is not None
    assert loaded.checked_at is not None
    assert loaded.checked_at != snapshot.checked_at


def test_failed_at_backoff_suppresses_requery(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    snapshot = ManagerSnapshot(
        inventory=_fresh_manager_snapshot().inventory,
        outdated=_fresh_manager_snapshot().outdated,
        checked_at=(now - MANAGER_STALE_AFTER - timedelta(hours=1)).isoformat(),
        failed_at=(now - timedelta(minutes=10)).isoformat(),
    )
    save_version_cache(path, {}, managers=encode_manager_snapshot(snapshot))
    query, calls = _counting_query()
    pnpm_calls = {"n": 0}
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=_count_pnpm(pnpm_calls),
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    service.refresh([_brew_tool()])
    assert calls == []
    assert pnpm_calls["n"] == 0

    cooled = ManagerSnapshot(
        inventory=snapshot.inventory,
        outdated=snapshot.outdated,
        checked_at=snapshot.checked_at,
        failed_at=(now - MANAGER_RETRY_BACKOFF - timedelta(minutes=1)).isoformat(),
    )
    save_version_cache(path, {}, managers=encode_manager_snapshot(cooled))
    service.refresh([_brew_tool()])
    assert len(calls) == 7


def test_partial_manager_failure_is_not_cached_as_confirmed_fresh(tmp_path: Path) -> None:
    """W3 regression (12-REVIEW.md, codex-sol-high): each manager reader
    (e.g. `_query_brew_list`) swallows its own CommandError/OSError into a
    `None` field rather than raising, so a single transient brew failure
    never trips `_load_or_query_snapshot`'s `except (CommandError, OSError)`
    branch — it would otherwise be cached with `checked_at=now, failed_at=
    None`, read as a confirmed-fresh snapshot for the full 6-hour
    MANAGER_STALE_AFTER window, and could block the update-enablement gate
    on stale "unknown" ownership. A manager confirmed present (has_brew=True
    here) returning `None` must be treated the same as an outright query
    exception: `failed_at` set, so a retry is allowed well inside
    MANAGER_RETRY_BACKOFF rather than the full 6 hours."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"

    def read_inv(**_kwargs: object) -> ManagerInventory:
        return ManagerInventory(
            brew_formulae=None,  # simulated transient, swallowed brew failure
            brew_casks={},
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=Path("/opt/homebrew"),
        )

    def read_out(**_kwargs: object) -> OutdatedReport:
        return OutdatedReport(brew={}, cask={}, pnpm={}, uv={})

    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=lambda *_a, **_k: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=read_inv,
        read_outdated_fn=read_out,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    service.refresh([_brew_tool()])
    loaded = load_manager_snapshot(path)
    assert loaded is not None
    assert loaded.failed_at is not None
    soon = now + MANAGER_RETRY_BACKOFF + timedelta(minutes=1)
    assert should_fetch_managers(loaded, now=soon) is True


def test_invalidate_drops_snapshot_and_bumps_epoch(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    save_version_cache(path, {}, managers=encode_manager_snapshot(_fresh_manager_snapshot()))
    query, calls = _counting_query()
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    before = service.epoch
    after = service.invalidate(reason="update")
    assert after > before
    service.refresh([_brew_tool()])
    assert len(calls) == 7


def test_refresh_discards_snapshot_when_epoch_changes_mid_flight(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    holder: dict[str, VersionRefreshService] = {}
    inv_calls = {"n": 0}

    def read_inv(**_kwargs: object) -> ManagerInventory:
        inv_calls["n"] += 1
        if inv_calls["n"] == 1:
            holder["svc"].invalidate(reason="update")
        return _fresh_manager_snapshot().inventory

    def read_out(**_kwargs: object) -> OutdatedReport:
        return _fresh_manager_snapshot().outdated

    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=lambda *_a, **_k: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=read_inv,
        read_outdated_fn=read_out,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    holder["svc"] = service
    service.refresh([_brew_tool()])
    loaded = load_manager_snapshot(path)
    assert loaded is None or loaded.checked_at is None
    service.refresh([_brew_tool()])
    assert inv_calls["n"] == 2


def test_ordinary_refresh_persists_snapshot(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    query, _calls = _counting_query()
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    service.refresh([_brew_tool()])
    loaded = load_manager_snapshot(path)
    assert loaded is not None
    assert loaded.checked_at is not None


def test_query_count_is_independent_of_catalog_size(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)

    def run(count: int) -> int:
        path = tmp_path / f"versions-{count}.json"
        query, calls = _counting_query()
        pnpm_calls = {"n": 0}
        tools = [
            Tool(
                id=f"t{i}",
                name=f"t{i}",
                category="search",
                cmd=f"t{i}",
                methods=(Method(kind="brew", params={"formula": f"t{i}"}),),
            )
            for i in range(count)
        ]
        service = VersionRefreshService(
            platform=_platform(),
            cache_path=path,
            resolve_tag=lambda repo: "v0",
            probe_output=lambda argv: "1.0.0",
            now=lambda: now,
            managed_bin_dir=_MANAGED,
            which=_which_for_fixture,
            artifacts_for=lambda _tool: [],
            query=query,
            pnpm_packages=_count_pnpm(pnpm_calls),
            resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
        )
        service.refresh(tools)
        return len(calls) + pnpm_calls["n"]

    assert run(25) == run(50)


def test_brew_absent_from_outdated_map_is_up_to_date() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    tool = _brew_tool()
    status, _entry = resolve_status(
        tool,
        ownership=_owned(tool, "brew", package="ripgrep", current_version="14.1.0"),
        outdated=OutdatedReport(brew={}, cask={}, pnpm={}, uv={}),
        entry=None,
        now=now,
        probe_output=lambda argv: "14.1.0",
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    assert status.outdated is False
    assert status.latest == "14.1.0"


def test_brew_none_outdated_map_is_unknown() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    tool = _brew_tool()
    status, _entry = resolve_status(
        tool,
        ownership=_owned(tool, "brew", package="ripgrep", current_version="14.1.0"),
        outdated=OutdatedReport(brew=None, cask=None, pnpm={}, uv={}),
        entry=None,
        now=now,
        probe_output=lambda argv: "14.1.0",
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    assert status.outdated is None
    assert status.latest is None
    assert status.stale is True


def test_uv_none_outdated_map_from_fail_closed_parser_is_unknown() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    tool = _uv_tool()
    status, _entry = resolve_status(
        tool,
        ownership=_owned(tool, "uv", package="ruff", current_version="0.6.0"),
        outdated=OutdatedReport(brew={}, cask={}, pnpm={}, uv=None),
        entry=None,
        now=now,
        probe_output=lambda argv: "0.6.0",
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    assert status.source == "uv"
    assert status.outdated is None
    assert status.latest is None


def test_cask_without_probe_uses_inventory_current_version() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    tool = _cask_tool()
    status, _entry = resolve_status(
        tool,
        ownership=_owned(tool, "cask", package="rectangle", current_version="0.85"),
        outdated=OutdatedReport(brew={}, cask={}, pnpm={}, uv={}),
        entry=None,
        now=now,
        probe_output=lambda argv: None,
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    assert status.installed == "0.85"
    assert status.outdated is False


def test_unknown_owner_renders_unknown_regardless_of_outdated_maps() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    tool = _brew_tool()
    ownership = ManagerOwnership(
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
        unknown_reason="the brew inventory could not be read",
    )
    status, _entry = resolve_status(
        tool,
        ownership=ownership,
        outdated=OutdatedReport(
            brew={"ripgrep": ManagerVersion("14.1.0", "14.1.1")},
            cask={},
            pnpm={},
            uv={},
        ),
        entry=None,
        now=now,
        probe_output=lambda argv: "14.1.0",
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    assert status.source == "unknown"
    assert status.outdated is None
    assert status.latest is None
    assert status.stale is True


def test_pinned_spec_populated_for_registry_pin() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    pinned = _node_tool(pinned=True)
    unpinned = _node_tool(pinned=False)
    outdated = OutdatedReport(
        brew={},
        cask={},
        pnpm={"@mermaid-js/mermaid-cli": ManagerVersion("11.0.0", "11.1.0")},
        uv={},
    )
    pinned_status, _ = resolve_status(
        pinned,
        ownership=_owned(
            pinned, "pnpm", method=pinned.methods[0], package="@mermaid-js/mermaid-cli"
        ),
        outdated=outdated,
        entry=None,
        now=now,
        probe_output=lambda argv: "11.0.0",
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    unpinned_status, _ = resolve_status(
        unpinned,
        ownership=_owned(
            unpinned, "pnpm", method=unpinned.methods[0], package="@mermaid-js/mermaid-cli"
        ),
        outdated=outdated,
        entry=None,
        now=now,
        probe_output=lambda argv: "11.0.0",
        resolve_tag=lambda repo: "v0",
        platform=_platform(),
    )
    assert pinned_status.pinned_spec == "puppeteer ^25"
    assert unpinned_status.pinned_spec is None


def test_state_of_returns_last_pass_and_none_for_missing(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    query, _calls = _counting_query()
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    service.refresh([_brew_tool()])
    assert service.state_of("rg") is not None
    assert service.state_of("missing") is None


def test_state_of_returns_none_for_a_state_older_than_the_current_epoch(
    tmp_path: Path,
) -> None:
    """A single `invalidate` call makes every existing state report as
    unavailable until a refresh commits new ones."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    query, _calls = _counting_query()
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    service.refresh([_brew_tool()])
    assert service.state_of("rg") is not None
    service.invalidate(reason="update")
    assert service.state_of("rg") is None
    service.refresh([_brew_tool()])
    assert service.state_of("rg") is not None


def test_a_raced_refresh_publishes_no_state(tmp_path: Path) -> None:
    """Round-3 review HIGH #1, public reads only (checker W5): the raced
    branch -- `self._epoch != started_epoch` -- publishes no state and
    writes no cache entry for any tool in the pass. Deterministic: the
    invalidate is triggered from inside the manager-inventory read every pass
    makes before its per-tool loop, never by sleeping."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    holder: dict[str, VersionRefreshService] = {}

    def read_inv(**_kwargs: object) -> ManagerInventory:
        holder["svc"].invalidate(reason="raced")
        return _empty_inventory()

    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=lambda *_a, **_k: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=read_inv,
        read_outdated_fn=_empty_outdated,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
    )
    holder["svc"] = service
    service.refresh([_brew_tool()])
    assert service.state_of("rg") is None
    assert "rg" not in load_version_cache(path)
    assert service.epoch == 1


def test_a_superseded_refresh_publishes_no_ownership_over_a_newer_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE OVERWRITE CASE (Round-3 review HIGH #1). Refresh A starts at
    epoch 0; `invalidate()` moves the service to epoch 1; refresh B starts
    and commits at epoch 1; refresh A then finishes and takes the raced
    branch. `state_of` still returns B's state -- A's obsolete answer
    neither replaces it nor pushes it back to `None`. The interleaving is
    driven deterministically by holding A inside its own per-tool resolve
    step (an injected `resolve_tag` hold, the established shape) until B
    has fully committed -- never by sleeping."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    tool = _gh_tool("alpha")

    a_ownership = _owned(tool, "installer", current_version="1.0.0")
    b_ownership = _owned(tool, "pnpm", package="b-pkg", current_version="2.0.0")
    phase = {"value": "a"}

    def fake_resolve_ownership(_tool: Tool, **_kwargs: object) -> ManagerOwnership:
        return a_ownership if phase["value"] == "a" else b_ownership

    monkeypatch.setattr("installer.version_status.resolve_ownership", fake_resolve_ownership)

    a_holding = threading.Event()
    a_release = threading.Event()

    def resolve_tag(repo: str) -> str:
        # Only A's pass reaches this: `b_ownership.owner == "pnpm"` never
        # calls resolve_tag (resolve_status's non-installer branch reads
        # the outdated map instead), so B's refresh below runs to
        # completion synchronously without needing its own gate.
        a_holding.set()
        assert a_release.wait(timeout=5)
        return "v1.0.0"

    service = _installer_owned_service(
        path, resolve_tag=resolve_tag, probe_output=lambda argv: "0.9.0", now=lambda: now
    )
    errors: list[BaseException] = []

    def run_a() -> None:
        try:
            service.refresh([tool])
        except BaseException as exc:  # noqa: BLE001 -- collected for the join
            errors.append(exc)

    thread_a = threading.Thread(target=run_a)
    thread_a.start()
    assert a_holding.wait(timeout=5)  # A resolved `a_ownership`; now blocked before its commit

    service.invalidate(reason="update")  # epoch 0 -> 1
    phase["value"] = "b"
    service.refresh([tool])  # B: resolves + commits b_ownership synchronously, under epoch 1

    a_release.set()
    thread_a.join(timeout=5)
    assert errors == []

    state = service.state_of(tool.id)
    assert state is not None
    assert state.generation == service.epoch
    assert state.ownership == b_ownership


def test_the_service_publishes_one_snapshot_of_tool_states(tmp_path: Path) -> None:
    """D-03: after a pass, the only tool-keyed dict of `ToolState`s on the
    service is the published snapshot, each state carrying its pass's `seq`;
    the only other tool-keyed dict is the skill-probe input store, and no
    `VersionStatus` or `ManagerOwnership` map remains. Read through `vars()`,
    never a private attribute name."""
    service = _skill_state_service(tmp_path, lambda _argv: _CLAUDE_SUPERPOWERS_JSON)
    pack, alpha = _claude_pack(), _gh_tool("alpha")
    service.refresh([pack, alpha])
    service.refresh_skills([pack])
    published = {tool_id: service.state_of(tool_id) for tool_id in (pack.id, alpha.id)}
    held = cast("dict[str, object]", vars(service))
    maps = [
        cast("dict[object, object]", value) for value in held.values() if isinstance(value, dict)
    ]
    covered = {pack.id, alpha.id}
    keyed = [mapping for mapping in maps if covered & set(mapping)]
    snapshots = [m for m in keyed if all(isinstance(v, ToolState) for v in m.values())]
    assert snapshots == [published]
    for state in published.values():
        assert state is not None
        assert state.seq >= 1
    others = [m for m in keyed if m is not snapshots[0]]
    assert len(others) == 1
    assert all(isinstance(v, SkillHostStatus) for v in others[0].values())
    for mapping in maps:
        for value in mapping.values():
            parts = cast("tuple[object, ...]", value) if isinstance(value, tuple) else (value,)
            assert not any(isinstance(part, VersionStatus | ManagerOwnership) for part in parts)


def test_service_has_no_transitional_readers() -> None:
    """D-03: `state_of` is the only per-tool reader."""
    for name in ("ownership_of", "statuses", "skill_status_of"):
        assert not hasattr(VersionRefreshService, name), name


def test_no_test_file_pokes_private_service_stores() -> None:
    """Every test seeds state through the public doubles (tests/state_doubles.py),
    never by assigning a service's private ownership, status, skill or state
    store (the 19-15 scan, widened to every test file)."""
    stores = "|".join(("_own" + "ership", "_stat" + "uses", "_sta" + "tes", "_sk" + "ills"))
    poke = re.compile(r"\.(?:" + stores + r")\b(?:\[[^\]]*\])?\s*=(?!=)")
    here = Path(__file__).parent
    hits = [
        f"{source.name}:{number}: {line.strip()}"
        for source in sorted(here.glob("*.py"))
        if source.name != "state_doubles.py"
        for number, line in enumerate(source.read_text().splitlines(), 1)
        if poke.search(line)
    ]
    assert hits == []


def test_state_of_answers_fail_closed_across_commit_and_invalidate_boundaries(
    tmp_path: Path,
) -> None:
    """SEQUENCING case (Round-3 review HIGH #2). A reader samples
    `state_of` immediately after each commit and immediately after each
    invalidate, through two alternating gates that make the interleaving
    deterministic rather than racing on scheduler luck -- so a committed pass
    reads as a record and an invalidated one reads as `None`, on every pass,
    never by sleeping and hoping.

    WR-02 (15.4-REVIEW.md) renamed this: those same gates FULLY SERIALIZE the
    reader and the writer, so there is never a window in which a read
    overlaps a write and a torn read is structurally impossible to observe
    here. It was named and documented as the atomic-read proof and could not
    have been one. What it does prove -- fail-closed sequencing across both
    boundaries -- is real and worth keeping under an honest name; the
    structural gate above proves the atomicity, and the unsynchronized loop
    below exercises the overlap this one excludes by construction."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    tool = _gh_tool("alpha")
    service = _installer_owned_service(
        path, resolve_tag=lambda repo: "v1.0.0", probe_output=lambda argv: "0.9.0", now=lambda: now
    )

    observations: list[ToolState | None] = []
    errors: list[BaseException] = []
    _PASSES = 15
    _READS_PER_PASS = 20
    # Two alternating gates make the interleaving deterministic rather than
    # racing on scheduler luck (the same injected-hold principle the OVERWRITE
    # test above uses): the reader samples right after each commit AND right
    # after each invalidate, so both states are guaranteed to be observed on
    # every one of the writer's 15 passes -- never by sleeping and hoping.
    committed = threading.Event()
    invalidated = threading.Event()
    sampled = threading.Event()

    def writer() -> None:
        try:
            for _ in range(_PASSES):
                service.refresh([tool])
                committed.set()
                assert sampled.wait(timeout=5)
                sampled.clear()
                service.invalidate(reason="loop")
                invalidated.set()
                assert sampled.wait(timeout=5)
                sampled.clear()
        except BaseException as exc:  # noqa: BLE001 -- collected for the join
            errors.append(exc)

    def reader() -> None:
        try:
            for _ in range(_PASSES):
                assert committed.wait(timeout=5)
                committed.clear()
                for _ in range(_READS_PER_PASS):
                    observations.append(service.state_of(tool.id))
                sampled.set()
                assert invalidated.wait(timeout=5)
                invalidated.clear()
                for _ in range(_READS_PER_PASS):
                    observations.append(service.state_of(tool.id))
                sampled.set()
        except BaseException as exc:  # noqa: BLE001 -- collected for the join
            errors.append(exc)

    reader_thread = threading.Thread(target=reader)
    writer_thread = threading.Thread(target=writer)
    reader_thread.start()
    writer_thread.start()
    reader_thread.join(timeout=15)
    writer_thread.join(timeout=15)

    assert errors == []
    assert len(observations) == _PASSES * _READS_PER_PASS * 2
    assert any(obs is not None for obs in observations)  # the loop did observe a committed pass
    assert any(obs is None for obs in observations)  # and an invalidated gap between passes


def test_state_of_under_an_unsynchronized_reader_never_serves_a_superseded_state(
    tmp_path: Path,
) -> None:
    """WR-02 (15.4-REVIEW.md): the same reader/writer pair as the sequencing
    test above with the handshake REMOVED, so reads genuinely overlap writes
    instead of being fenced away from them.

    The assertion is the identity one the epoch tag exists to guarantee: when
    the epoch did not move across a call (sampled either side of it), a
    non-`None` answer must be the very record that epoch's own pass
    committed. A design that pairs a plain ownership map with a parallel
    epoch map can serve the PREVIOUS pass's record under the current epoch in
    the window between its two writes, and that is what this catches.

    It is a probabilistic detector, deliberately: a passing run is not proof
    the identity held under every conceivable interleaving. It can never fail
    spuriously (every branch is guarded on information the reader established
    itself), and the DETERMINISTIC proof of the same invariant is the
    structural gate at the top of this section -- not this loop.

    Overlap is by construction, not luck: the writer WAITS for the reader at
    the two points that matter, via a shared iteration counter -- after its
    commit (inside the committed window) and after its invalidate (inside the
    invalidated gap) -- so the reader is guaranteed to complete at least two
    whole loop iterations, and therefore at least one whole `state_of`
    call, inside each window. The reads themselves stay unsynchronized (no
    handshake on the read), which is exactly the race this test exists to
    catch. Bounded by iteration counts, never by wall-clock
    (.claude/testing.md)."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    tool = _gh_tool("alpha")
    service = _installer_owned_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: "0.9.0",
        now=lambda: now,
    )
    errors: list[BaseException] = []
    committed_at: dict[int, ToolState] = {}
    seen_record = False
    seen_none = False
    checked = 0
    # opencode M4: a regression that surfaces the previous record during a
    # LATER generation must be exercised, so the writer may not stop after
    # its first refresh+invalidate cycle. Two full generations are required
    # before the early exit; the reader-overlap conditions and the iteration
    # cap are unchanged.
    generations = 0
    _MIN_GENERATIONS = 2
    stop = threading.Event()
    reader_ready = threading.Event()
    _MAX_PASSES = 200
    reads = 0
    _READER_SPIN_CAP = 200_000

    def _let_reader_run() -> None:
        # Wait until the reader has completed at least two more loop
        # iterations (so at least one whole `state_of` call starts and
        # ends inside whichever window the writer is in), capping the spin.
        # A GIL-yield spin, never a wall-clock sleep: on macOS `time.sleep(0)`
        # alone hands the GIL back to the same thread, so no pass count can
        # get the reader scheduled inside a window -- only waiting for it can.
        target = reads + 2
        for _ in range(_READER_SPIN_CAP):
            if reads >= target:
                break
            time.sleep(0)

    def writer() -> None:
        nonlocal generations
        try:
            # Do not start before the reader is looping: on a slow runner a
            # head start would let every pass finish before the reader is
            # scheduled once, and the overlap this test exists to create
            # would never happen. Bounded by the event timeout, not by luck.
            assert reader_ready.wait(timeout=30)
            for _ in range(_MAX_PASSES):
                service.refresh([tool])
                # Published by `refresh` itself; this only records WHICH
                # object landed, so the reader can name the expectation.
                # The reader skips any epoch not yet recorded here.
                record = service.state_of(tool.id)
                if record is not None:
                    committed_at[service.epoch] = record
                # Wait for the reader INSIDE the committed window: the few
                # bytecodes between refresh() returning and invalidate() are
                # the only place a read can observe the record, and only a
                # writer-side wait guarantees the reader is scheduled there.
                _let_reader_run()
                service.invalidate(reason="loop")
                # Same inside the invalidated gap, so a None observation is
                # guaranteed too.
                _let_reader_run()
                generations += 1
                if generations >= _MIN_GENERATIONS and seen_record and seen_none and checked > 0:
                    break
        except BaseException as exc:  # noqa: BLE001 -- collected for the join
            errors.append(exc)
        finally:
            stop.set()

    def reader() -> None:
        nonlocal seen_record, seen_none, checked, reads
        try:
            reader_ready.set()
            while not stop.is_set():
                try:
                    before = service.epoch
                    observed = service.state_of(tool.id)
                    after = service.epoch
                    if observed is None:
                        seen_none = True
                        continue
                    seen_record = True
                    if before != after:
                        continue  # the epoch moved across the call: nothing to assert
                    expected = committed_at.get(before)
                    if expected is None:
                        continue  # that pass's commit has not been recorded yet
                    assert observed is expected, (before, observed, expected)
                    checked += 1
                finally:
                    # Count every completed iteration, `continue` paths
                    # included: the writer's `_let_reader_run` waits on this.
                    reads += 1
        except BaseException as exc:  # noqa: BLE001 -- collected for the join
            errors.append(exc)

    reader_thread = threading.Thread(target=reader)
    writer_thread = threading.Thread(target=writer)
    reader_thread.start()
    writer_thread.start()
    writer_thread.join(timeout=30)
    reader_thread.join(timeout=30)

    assert errors == []
    assert seen_record, "the unsynchronized reader never overlapped a committed pass"
    assert seen_none, "the unsynchronized reader never overlapped an invalidated gap"
    assert checked > 0, "no observation was ever in a position to be checked"


# -- D-05/Task 2: a real probe injected at the service seam reaches
# resolve_ownership for the display path, and resolve_status's untouched
# final branch is pinned field by field, not by an ownership-only proxy. ---


def test_native_probe_service_resolves_owner_and_status_stays_on_final_branch(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    probe_calls: list[list[str]] = []

    def native_probe(command: list[str]) -> str:
        probe_calls.append(command)
        # Two legitimate rpm questions reach this seam: `rpm -q` proves the
        # package is installed, and `rpm -qf` (CR-01) proves that package owns
        # the live /usr/bin/jq rather than some copy earlier in PATH -- asked
        # once per pass in its batched form (D-11).
        assert command[:2] in (["rpm", "-q"], ["rpm", "-qf"])
        if command[:4] == _RPM_BATCH:
            return "".join(f"{path}\tjq\n" for path in command[4:])
        return "jq\n"

    service = _native_owned_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: "1.8.1",
        now=lambda: now,
        native_probe=native_probe,
    )
    tool = _jq_tool()
    statuses = _versions(service, [tool])

    jq = service.state_of("jq")
    assert jq is not None
    ownership = jq.ownership
    assert ownership.owner == "dnf"
    assert ownership.confidence == "direct"
    assert probe_calls  # the injected probe was actually consulted
    # CR-01 end to end: the live-path confirmation runs on the real service
    # seam, not only in the resolver's unit tests.
    assert ["rpm", "-qf"] in [command[:2] for command in probe_calls]

    # resolve_status's FINAL branch (version_status.py:324-336), asserted
    # field by field: there is no outdated report for a native owner, and
    # this plan deliberately changes nothing about that -- but the widened
    # Owner reaches every `owner ==` ladder in this module, so it has to be
    # pinned rather than assumed. An ownership-only assertion would stay
    # green even if a branch started claiming a latest version for an owner
    # this installer cannot query.
    status = statuses["jq"]
    assert status.installed == "1.8.1"
    assert status.latest is None
    assert status.outdated is None
    assert status.stale is True
    assert status.source == "unknown"


def test_no_probe_default_never_acquires_a_native_subprocess(tmp_path: Path) -> None:
    """The default is None, deliberately breaking the surrounding
    query/which convention: a real default would put a subprocess inside
    every unit test that constructs this service."""
    now = datetime(2026, 9, 14, tzinfo=UTC)
    service = _native_owned_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: "1.8.1",
        now=lambda: now,
        native_probe=None,
    )
    tool = _jq_tool()
    service.refresh([tool])
    jq = service.state_of("jq")
    assert jq is not None
    ownership = jq.ownership
    assert ownership.owner == "unknown"


def _springboot_current(tmp: Path, target: str, *, create_target: bool) -> Path:
    root = tmp / "c" / "springboot"
    if create_target:
        version_bin = root / target / "bin"
        version_bin.mkdir(parents=True)
        (version_bin / "spring").write_text("#!/bin/sh\n")
    else:
        root.mkdir(parents=True)
    (root / "current").symlink_to(target)
    return root / "current" / "bin"


def _sdkman_springboot(bin_dir: Path) -> tuple[Tool, ManagerOwnership]:
    method = Method(
        kind="sdkman",
        params={"candidate": "springboot", "bin_dir": str(bin_dir)},
    )
    tool = Tool(
        id="springbootcli",
        name="Spring Boot CLI",
        category="runtime",
        cmd="spring",
        methods=(method,),
    )
    candidate = OwnershipCandidate(
        owner="sdkman",
        method=method,
        package="springboot",
        current_version=None,
        evidence="test",
    )
    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner="sdkman",
        method=method,
        package="springboot",
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(candidate,),
        active_candidate="sdkman",
        active_path=bin_dir / "spring",
        unknown_reason=None,
    )
    return tool, ownership


def _status_now() -> datetime:
    return datetime(2026, 9, 7, tzinfo=UTC)


def test_sdkman_current_symlink_is_the_installed_version_without_a_probe(tmp_path: Path) -> None:
    bin_dir = _springboot_current(tmp_path, "4.1.0", create_target=True)
    tool, ownership = _sdkman_springboot(bin_dir)
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "9.9.9"

    status, entry = resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=probe,
        resolve_tag=lambda _repo: "v0",
        platform=_platform(),
    )
    assert calls == []
    assert entry is None
    assert status == VersionStatus(
        tool_id="springbootcli",
        installed="4.1.0",
        latest=None,
        outdated=None,
        stale=False,
        source="sdkman",
        pinned_spec=None,
    )


def test_sdkman_dangling_current_has_no_installed_version(tmp_path: Path) -> None:
    bin_dir = _springboot_current(tmp_path, "missing", create_target=False)
    tool, ownership = _sdkman_springboot(bin_dir)
    status, _entry = resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=lambda _argv: "9.9.9",
        resolve_tag=lambda _repo: "v0",
        platform=_platform(),
    )
    assert status.installed is None
    assert status.source == "sdkman"


def test_sdkman_unparseable_current_target_has_no_installed_version(tmp_path: Path) -> None:
    bin_dir = _springboot_current(tmp_path, "not-a-version", create_target=True)
    tool, ownership = _sdkman_springboot(bin_dir)
    status, _entry = resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=lambda _argv: "9.9.9",
        resolve_tag=lambda _repo: "v0",
        platform=_platform(),
    )
    assert status.installed is None
    assert status.source == "sdkman"


def test_sdkman_version_through_real_resolve_ownership(tmp_path: Path) -> None:
    bin_dir = _springboot_current(tmp_path, "4.1.0", create_target=True)
    method = Method(
        kind="sdkman",
        params={"candidate": "springboot", "bin_dir": str(bin_dir)},
    )
    tool = Tool(
        id="springbootcli",
        name="Spring Boot CLI",
        category="runtime",
        cmd="spring",
        methods=(method,),
    )
    binary = bin_dir / "spring"
    ownership = resolve_ownership(
        tool,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        inventory=ManagerInventory(
            brew_formulae=None,
            brew_casks=None,
            pnpm_globals=None,
            uv_tools=None,
            brew_prefix=None,
        ),
        artifacts=(),
        managed_bin_dir=tmp_path / "managed",
        which=lambda _cmd: str(binary),
    )
    assert ownership.owner == "sdkman"
    assert ownership.method is not None
    assert ownership.method.params["bin_dir"] == str(bin_dir)
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "9.9.9"

    status, _entry = resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=probe,
        resolve_tag=lambda _repo: "v0",
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
    )
    assert calls == []
    assert status.installed == "4.1.0"


def _tool(cmd: str, *methods: Method) -> Tool:
    return Tool(id=cmd, name=cmd, category="dev", cmd=cmd, methods=methods)


def _probe_calls() -> tuple[list[list[str]], Callable[[list[str]], str]]:
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "9.9.9"

    return calls, probe


def test_probe_uses_resolved_active_path() -> None:
    tool = _tool("tool")
    ownership = replace(_owned(tool, "unknown"), active_path=Path("/opt/x/bin/tool"), method=None)
    calls, probe = _probe_calls()
    resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=probe,
        resolve_tag=lambda _repo: "v0",
        platform=_platform(),
    )
    assert calls == [["/opt/x/bin/tool", "--version"]]


def test_probe_uses_declared_bin_dir_when_active_path_is_absent(tmp_path: Path) -> None:
    declared = tmp_path / "declared"
    other = tmp_path / "other"
    declared.mkdir()
    other.mkdir()
    (declared / "tool").write_text("#!/bin/sh\n")
    (other / "tool").write_text("#!/bin/sh\n")
    method = Method(kind="script", params={"bin_dir": str(declared)})
    tool = _tool("tool", Method(kind="script", params={"bin_dir": str(other)}))
    ownership = replace(_owned(tool, "unknown", method=method), active_path=None)
    calls, probe = _probe_calls()
    resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=probe,
        resolve_tag=lambda _repo: "v0",
        platform=_platform(),
    )
    assert calls == [[str(declared / "tool"), "--version"]]


def test_probe_falls_back_to_bare_cmd_when_no_path_is_known() -> None:
    tool = _tool("tool")
    ownership = replace(_owned(tool, "unknown"), active_path=None, method=None)
    calls, probe = _probe_calls()
    resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=probe,
        resolve_tag=lambda _repo: "v0",
        platform=_platform(),
    )
    assert calls == [["tool", "--version"]]
    direct: list[list[str]] = []
    resolve_github_release_status(
        _codegraph(),
        repo="colbymchenry/codegraph",
        entry=None,
        now=_status_now(),
        probe_output=lambda argv: direct.append(argv) or "1.2.0",
        resolve_tag=lambda _repo: "v1.6.0",
    )
    assert direct == [["codegraph", "--version"]]


def test_version_file_is_read_without_a_subprocess_probe(tmp_path: Path) -> None:
    path = tmp_path / "version"
    method = Method(kind="script", params={"version_file": str(path)})
    tool = _tool("sdkman-init.sh", method)
    ownership = replace(
        _owned(tool, "installer", method=method),
        active_path=Path("/opt/x/bin/sdkman-init.sh"),
    )

    def installed_for(contents: str | bytes | None) -> tuple[str | None, list[list[str]]]:
        if isinstance(contents, bytes):
            path.write_bytes(contents)
            declared = path
        elif contents is None:
            declared = tmp_path / "missing"
        else:
            path.write_text(contents)
            declared = path
        record = replace(
            ownership,
            method=Method(kind="script", params={"version_file": str(declared)}),
        )
        calls, probe = _probe_calls()
        status, _entry = resolve_status(
            tool,
            ownership=record,
            outdated=_empty_outdated(),
            entry=None,
            now=_status_now(),
            probe_output=probe,
            resolve_tag=lambda _repo: "v0",
            platform=_platform(),
        )
        return status.installed, calls

    assert installed_for("5.23.0\n") == ("5.23.0", [])
    assert installed_for("garbage") == (None, [])
    assert installed_for(None) == (None, [])
    assert installed_for(b"\xff\xfe") == (None, [])
    assert installed_for("") == (None, [])


def test_github_release_probes_at_the_active_path() -> None:
    tool = _codegraph()
    ownership = replace(_owned(tool, "installer"), active_path=Path("/opt/x/bin/codegraph"))
    calls, probe = _probe_calls()
    resolve_status(
        tool,
        ownership=ownership,
        outdated=_empty_outdated(),
        entry=None,
        now=_status_now(),
        probe_output=probe,
        resolve_tag=lambda _repo: "v1.6.0",
        platform=_platform(),
    )
    assert calls == [["/opt/x/bin/codegraph", "--version"]]


def _skill_pack(tool_id: str, probes: tuple[SkillStatusProbe, ...]) -> Tool:
    manual = SkillOperation(
        mode="manual-required", instructions=("Review and run the official flow.",)
    )
    return Tool(
        id=tool_id,
        name=tool_id,
        category="ai",
        cmd=tool_id,
        methods=(Method(kind="skill_pack"),),
        tier="ai",
        skill_lifecycle=SkillLifecycle(
            source="https://github.com/example/skills",
            owner="example",
            supported_harnesses=tuple(dict.fromkeys(probe.harness for probe in probes)),
            revision_policy="upstream-latest",
            targets=(SkillTarget("harness", "<codex-plugin-dir>/demo"),),
            install=manual,
            status=manual,
            update=manual,
            removal=manual,
            status_probes=probes,
        ),
    )


_CLAUDE_SUPERPOWERS_JSON = (
    '[{"id": "superpowers@claude-plugins-official", "scope": "user", '
    '"enabled": true, "version": "6.4.1"}]'
)


def test_refresh_skills_persists_once_and_skips_the_second_call(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def skill_probe(argv: list[str]) -> str:
        calls.append(list(argv))
        if argv == ["claude", "plugin", "list", "--json"]:
            return _CLAUDE_SUPERPOWERS_JSON
        return ""

    pack = _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )
    path = tmp_path / "versions.json"
    service = VersionRefreshService(
        platform=Platform(os="linux", arch="amd64", immutable=True, has_brew=False),
        cache_path=path,
        skill_probe=skill_probe,
        skill_home=tmp_path,
        which=lambda _cmd: None,
        query=lambda *_args, **_kwargs: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
    )
    landed = service.refresh_skills([pack])
    status = _held_skills(service).get("superpowers")
    assert isinstance(status, SkillHostStatus)
    assert status.hosts == {"claude": "present"}
    assert status.stale is False
    assert landed["superpowers"].stale is False
    assert load_skill_statuses(path) == {"superpowers": {"claude": "present"}}

    calls.clear()
    service.refresh_skills([pack])
    assert calls == []


def _claude_pack() -> Tool:
    return _skill_pack(
        "superpowers",
        (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
    )


def _skill_service(
    path: Path, probe: Callable[[list[str]], str], home: Path
) -> VersionRefreshService:
    return VersionRefreshService(
        platform=Platform(os="linux", arch="amd64", immutable=True, has_brew=False),
        cache_path=path,
        skill_probe=probe,
        skill_home=home,
        which=lambda _cmd: None,
        query=lambda *_args, **_kwargs: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
    )


def test_skill_refresh_from_two_threads_probes_once(tmp_path: Path) -> None:
    calls = {"n": 0}
    release = threading.Event()
    started = threading.Event()

    def skill_probe(_argv: list[str]) -> str:
        calls["n"] += 1
        started.set()
        assert release.wait(timeout=5)
        return _CLAUDE_SUPERPOWERS_JSON

    service = _skill_service(tmp_path / "versions.json", skill_probe, tmp_path)
    pack = _claude_pack()
    results: list[dict[str, SkillHostStatus]] = []

    def caller() -> None:
        results.append(service.refresh_skills([pack]))

    first = threading.Thread(target=caller)
    second = threading.Thread(target=caller)
    first.start()
    assert started.wait(timeout=5)
    second.start()
    second.join(timeout=0.2)
    assert second.is_alive()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert calls["n"] == 1
    assert len(results) == 2
    assert all(result["superpowers"].stale is False for result in results)


def test_skill_pass_superseded_by_invalidate_stores_nothing(tmp_path: Path) -> None:
    calls = {"n": 0}
    service = _skill_service(tmp_path / "versions.json", lambda _argv: "", tmp_path)

    def skill_probe(_argv: list[str]) -> str:
        calls["n"] += 1
        service.invalidate(reason="x")
        return _CLAUDE_SUPERPOWERS_JSON

    service._skill_probe = skill_probe  # pyright: ignore[reportPrivateUsage]
    pack = _claude_pack()
    service.refresh_skills([pack])
    assert _held_skills(service).get("superpowers") is None
    assert service._skills_probed is False  # pyright: ignore[reportPrivateUsage]
    service.refresh_skills([pack])
    assert calls["n"] == 2
    assert _held_skills(service).get("superpowers") is None


def test_skill_invalidate_marks_every_held_entry_stale(tmp_path: Path) -> None:
    def skill_probe(_argv: list[str]) -> str:
        return _CLAUDE_SUPERPOWERS_JSON

    service = _skill_service(tmp_path / "versions.json", skill_probe, tmp_path)
    service.refresh_skills([_claude_pack()])
    landed = _held_skills(service).get("superpowers")
    assert landed is not None
    assert landed.stale is False
    service.invalidate(reason="x")
    held = _held_skills(service).get("superpowers")
    assert held is not None
    assert held.stale is True


def test_refresh_skills_without_packs_keeps_seeded_answers(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    path = tmp_path / "versions.json"
    save_version_cache(path, {}, skills={"superpowers": {"claude": "present"}})
    service = _skill_service(path, lambda argv: calls.append(list(argv)) or "", tmp_path)
    service.seed_skills_from_cache()
    before = path.read_text()
    landed = service.refresh_skills([_tool("rg")])
    assert calls == []
    assert landed["superpowers"].stale is True
    held = _held_skills(service).get("superpowers")
    assert held is not None
    assert held.stale is True
    assert service._skills_probed is False  # pyright: ignore[reportPrivateUsage]
    assert path.read_text() == before


def test_second_skill_caller_waits_for_in_flight_pass(tmp_path: Path) -> None:
    calls = {"n": 0}
    started = threading.Event()
    release = threading.Event()

    def skill_probe(_argv: list[str]) -> str:
        calls["n"] += 1
        started.set()
        assert release.wait(timeout=5)
        return _CLAUDE_SUPERPOWERS_JSON

    service = _skill_service(tmp_path / "versions.json", skill_probe, tmp_path)
    pack = _claude_pack()
    results: list[dict[str, SkillHostStatus]] = []

    def caller() -> None:
        results.append(service.refresh_skills([pack]))

    first = threading.Thread(target=caller)
    second = threading.Thread(target=caller)
    first.start()
    assert started.wait(timeout=5)
    second.start()
    second.join(timeout=0.2)
    assert second.is_alive()
    assert calls["n"] == 1
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert calls["n"] == 1
    assert len(results) == 2
    assert all(item["superpowers"].stale is False for item in results)


# -- 19-08 Task 1: one ToolState per tool, published in one swap (D-02, D-03). --

# Captured at import, before any test patches HOME (checker W2).
_REAL_HOME = Path.home()
_STATE_NOW = datetime(2026, 10, 16, tzinfo=UTC)


def _raw_gh_tool(tool_id: str) -> Tool:
    """A raw github_release tool with no bin_dir: its implicit artifact is
    `<managed bin dir>/<cmd>`, so presence follows the service's bin dir."""
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(
            Method(
                kind="github_release",
                params={"repo": f"owner/{tool_id}", "member": tool_id, "raw": True},
            ),
        ),
        tier="user",
    )


def _state_service(
    tmp_path: Path,
    *,
    which: Callable[[str], str | None],
    present: Callable[[Tool], bool] | None = None,
    probe_output: Callable[[list[str]], str | None] = lambda _argv: "0.9.0",
    resolve_tag: Callable[[str], str] = lambda _repo: "1.0.0",
    managed_bin_dir: Path | None = None,
    platform: Platform | None = None,
) -> VersionRefreshService:
    managed = managed_bin_dir if managed_bin_dir is not None else tmp_path / "managed"
    return VersionRefreshService(
        platform=platform if platform is not None else _platform(),
        cache_path=tmp_path / "versions.json",
        resolve_tag=resolve_tag,
        probe_output=probe_output,
        now=lambda: _STATE_NOW,
        managed_bin_dir=managed,
        which=which,
        artifacts_for=lambda tool: [managed / tool.cmd],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        query=lambda *_args, **_kwargs: "",
        present=present,
    )


def _unknown_owner(tool: Tool) -> ManagerOwnership:
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
        unknown_reason="no manager claimed the tool",
    )


_NO_REMOVAL = RemovalPlan((), ())


def test_refresh_publishes_one_tool_state_per_tool(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    alpha, beta = _gh_tool("alpha"), _gh_tool("beta")
    service = _state_service(
        tmp_path,
        which=lambda cmd: str(managed / cmd) if cmd == "alpha" else None,
    )
    service.refresh([alpha, beta])
    first = service.state_of("alpha")
    second = service.state_of("beta")
    assert first is not None
    assert second is not None
    assert first.health is Health.OUTDATED
    assert first.reasons[0] == "0.9.0 -> 1.0.0 available"
    assert second.health is Health.MISSING
    assert first.generation == service.epoch
    assert second.generation == service.epoch
    for state, tool in ((first, alpha), (second, beta)):
        assert state.tool_id == tool.id
        assert state.ownership.tool_id == tool.id
        assert state.version is not None
        assert state.version.tool_id == tool.id
        assert state.removable == plan_removal([tool], service.managed_bin_dir)


def test_nothing_is_visible_mid_pass(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    holder: dict[str, VersionRefreshService] = {}
    seen: list[ToolState | None] = []

    def probe_output(argv: list[str]) -> str:
        if Path(argv[0]).name == "beta":
            seen.append(holder["svc"].state_of("alpha"))
        return "1.0.0"

    service = _state_service(
        tmp_path, which=lambda cmd: str(managed / cmd), probe_output=probe_output
    )
    holder["svc"] = service
    service.refresh([_gh_tool("alpha"), _gh_tool("beta")])
    assert seen == [None]
    assert service.state_of("alpha") is not None


def test_state_of_is_none_after_invalidate(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    service = _state_service(tmp_path, which=lambda cmd: str(managed / cmd))
    service.refresh([_gh_tool("alpha")])
    assert service.state_of("alpha") is not None
    service.invalidate(reason="update")
    assert service.state_of("alpha") is None


def test_state_of_unknown_tool_is_none(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    service = _state_service(tmp_path, which=lambda cmd: str(managed / cmd))
    assert service.state_of("alpha") is None
    service.refresh([_gh_tool("alpha")])
    assert service.state_of("nope") is None


def test_broken_shim_state() -> None:
    tool = _node_tool()
    state = tool_state(
        tool,
        generation=0,
        platform=_platform(),
        present=True,
        ownership=replace(_owned(tool, "pnpm", package="@mermaid-js/mermaid-cli"), broken=True),
        version=None,
        removable=_NO_REMOVAL,
    )
    assert state.health is Health.BROKEN
    assert state.reasons[0] == BROKEN_SHIM_REASON
    assert BROKEN_SHIM_REASON == (
        "shim present, package missing — select it and press enter to reinstall and repair"
    )


def test_unavailable_state_uses_the_resolver_reason() -> None:
    tool = Tool(
        id="macapp",
        name="macapp",
        category="dev",
        cmd="macapp",
        methods=(Method(kind="github_release", params={"repo": "o/macapp"}, os=("macos",)),),
    )
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    reason = unavailable_reason(tool, platform)
    assert reason is not None
    state = tool_state(
        tool,
        generation=0,
        platform=platform,
        present=False,
        ownership=_unknown_owner(tool),
        version=None,
        removable=_NO_REMOVAL,
    )
    assert state.health is Health.UNAVAILABLE
    assert state.reasons[0] == reason.detail


def test_brew_only_tool_state_is_unavailable_without_brew() -> None:
    tool = _brew_tool()
    without = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
    assert unavailable_reason(tool, without) is None
    state = tool_state(
        tool,
        generation=0,
        platform=without,
        present=False,
        ownership=_unknown_owner(tool),
        version=None,
        removable=_NO_REMOVAL,
    )
    assert state.health is Health.UNAVAILABLE
    assert state.reasons[0] == NEEDS_BREW_REASON
    with_brew = tool_state(
        tool,
        generation=0,
        platform=replace(without, has_brew=True),
        present=False,
        ownership=_unknown_owner(tool),
        version=None,
        removable=_NO_REMOVAL,
    )
    assert with_brew.health is Health.MISSING


def test_tool_state_builder_is_pure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _gh_tool("alpha")
    version = VersionStatus(
        tool_id="alpha", installed="1.0.0", latest="1.0.0", outdated=False, stale=False, source="x"
    )

    def build() -> ToolState:
        return tool_state(
            tool,
            generation=3,
            platform=_platform(),
            present=True,
            ownership=_owned(tool, "installer"),
            version=version,
            removable=RemovalPlan((), ()),
        )

    first, second = build(), build()
    assert first == second
    assert first.generation == 3
    assert first.health is Health.OK
    assert list(tmp_path.iterdir()) == []


def test_tool_state_forwards_checking_facts() -> None:
    pack = _claude_pack()
    checking = tool_state(
        pack,
        generation=0,
        platform=_platform(),
        present=True,
        ownership=_unknown_owner(pack),
        version=None,
        removable=_NO_REMOVAL,
        checking=("checking which hosts have it",),
    )
    assert checking.health is Health.CHECKING
    assert checking.reasons[0] == "checking which hosts have it"
    assert checking.present is False
    settled = tool_state(
        pack,
        generation=0,
        platform=_platform(),
        present=True,
        ownership=_unknown_owner(pack),
        version=None,
        removable=_NO_REMOVAL,
    )
    assert settled.health is not Health.CHECKING
    assert settled.present is True


def test_is_present_reads_the_state_then_probes(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    calls: list[str] = []

    def present(tool: Tool) -> bool:
        calls.append(tool.id)
        return True

    tool = _gh_tool("alpha")
    service = _state_service(tmp_path, which=lambda cmd: str(managed / cmd), present=present)
    assert service.is_present(tool) is True
    assert calls == ["alpha"]
    service.refresh([tool])
    calls.clear()
    state = service.state_of("alpha")
    assert state is not None
    assert service.is_present(tool) is state.present
    assert calls == []
    service.invalidate(reason="update")
    assert service.is_present(tool) is True
    assert calls == ["alpha"]


def test_injected_present_predicate_drives_presence(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    service = _state_service(
        tmp_path, which=lambda cmd: str(managed / cmd), present=lambda t: t.id == "alpha"
    )
    service.refresh([_gh_tool("alpha"), _gh_tool("beta")])
    alpha = service.state_of("alpha")
    beta = service.state_of("beta")
    assert alpha is not None
    assert beta is not None
    assert alpha.present is True
    assert beta.health is Health.MISSING


def test_pass_implicit_presence_reads_the_managed_bin_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    managed = tmp_path / "managed"
    managed.mkdir()
    tool = _raw_gh_tool("gamma")
    (managed / "gamma").write_text("bin")
    service = _state_service(tmp_path, which=lambda _cmd: None, managed_bin_dir=managed)
    service.refresh([tool])
    state = service.state_of("gamma")
    assert state is not None
    assert state.present is True

    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    (home / ".local" / "bin" / "gamma").write_text("bin")
    monkeypatch.setenv("HOME", str(home))
    elsewhere = tmp_path / "other"
    other_managed = tmp_path / "managed-empty"
    elsewhere.mkdir()
    service = _state_service(elsewhere, which=lambda _cmd: None, managed_bin_dir=other_managed)
    service.refresh([tool])
    state = service.state_of("gamma")
    assert state is not None
    assert state.health is Health.MISSING


def test_service_default_bin_dir_is_sandboxed(tmp_path_factory: pytest.TempPathFactory) -> None:
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=tmp_path_factory.mktemp("cache") / "versions.json",
    )
    assert not service.managed_bin_dir.is_relative_to(_REAL_HOME)
    assert service.managed_bin_dir.is_relative_to(tmp_path_factory.getbasetemp())


# -- 19-08 Task 2: newest pass wins per record; overtaken passes publish nothing. --


class _Hold:
    """A `resolve_tag` that counts calls and parks the FIRST one on an Event."""

    def __init__(self, *, tag: str = "1.0.0") -> None:
        self.calls = 0
        self.holding = threading.Event()
        self.release = threading.Event()
        self.tag = tag
        self._lock = threading.Lock()

    def __call__(self, _repo: str) -> str:
        with self._lock:
            self.calls += 1
            first = self.calls == 1
            tag = self.tag
        if first:
            self.holding.set()
            assert self.release.wait(timeout=10)
        return tag


def _start(target: Callable[[], object]) -> Future[object]:
    """Run `target` on its own thread; the future carries what it raised."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(target)
    finally:
        pool.shutdown(wait=False)


def _join(run: Future[object]) -> BaseException | None:
    """Wait (bounded) for a started call and return what it raised, if anything."""
    return run.exception(timeout=10)


def _still_running(run: Future[object]) -> bool:
    return not wait([run], timeout=0.2).done


def _held_service(
    tmp_path: Path, hold: _Hold, *, present: Callable[[Tool], bool] | None = None
) -> VersionRefreshService:
    managed = tmp_path / "managed"
    return _state_service(
        tmp_path, which=lambda cmd: str(managed / cmd), resolve_tag=hold, present=present
    )


def test_overtaken_pass_publishes_nothing(tmp_path: Path) -> None:
    hold = _Hold()
    service = _held_service(tmp_path, hold)
    a, b, c = _gh_tool("a"), _gh_tool("b"), _gh_tool("c")
    run_a = _start(lambda: service.refresh([a, b]))
    assert hold.holding.wait(timeout=10)
    service.refresh([a, b, c])
    captured = {tool_id: service.state_of(tool_id) for tool_id in ("a", "b", "c")}
    hold.release.set()
    assert _join(run_a) is None
    seqs: set[int] = set()
    for tool_id, state in captured.items():
        assert state is not None
        assert service.state_of(tool_id) is state
        seqs.add(state.seq)
    assert len(seqs) == 1
    # The released pass A took a sequence BEFORE B, so B's records outrank it.
    service.refresh([_gh_tool("d")])
    later = service.state_of("d")
    assert later is not None
    assert later.seq == seqs.pop() + 1


def test_overtaken_by_invalidate_publishes_nothing(tmp_path: Path) -> None:
    holder: dict[str, VersionRefreshService] = {}

    def read_inv(**_kwargs: object) -> ManagerInventory:
        holder["svc"].invalidate(reason="raced")
        return _empty_inventory()

    managed = tmp_path / "managed"
    service = VersionRefreshService(
        platform=_platform(),
        cache_path=tmp_path / "versions.json",
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=lambda _argv: "0.9.0",
        now=lambda: _STATE_NOW,
        managed_bin_dir=managed,
        which=lambda cmd: str(managed / cmd),
        query=lambda *_a, **_k: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=read_inv,
        read_outdated_fn=_empty_outdated,
        resolve_pnpm=lambda: None,
    )
    holder["svc"] = service
    service.refresh([_gh_tool("a"), _brew_tool()])
    assert service.state_of("a") is None
    assert service.state_of("rg") is None


def test_partial_pass_merges_into_the_full_snapshot(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    service = _state_service(tmp_path, which=lambda cmd: str(managed / cmd))
    service.refresh([_gh_tool("a"), _gh_tool("b")])
    first_a = service.state_of("a")
    first_b = service.state_of("b")
    assert first_a is not None
    assert first_b is not None
    service.refresh([_gh_tool("a")])
    newer_a = service.state_of("a")
    assert service.state_of("b") is first_b
    assert newer_a is not None
    assert newer_a is not first_a
    assert newer_a.seq > first_a.seq


def test_older_full_pass_fills_tools_a_newer_partial_pass_did_not_cover(tmp_path: Path) -> None:
    hold = _Hold()
    service = _held_service(tmp_path, hold)
    a, b = _gh_tool("a"), _gh_tool("b")
    run_a = _start(lambda: service.refresh([a, b]))
    assert hold.holding.wait(timeout=10)
    service.refresh([a])
    partial = service.state_of("a")
    assert partial is not None
    assert service.state_of("b") is None
    hold.release.set()
    assert _join(run_a) is None
    assert service.state_of("a") is partial
    filled = service.state_of("b")
    assert filled is not None
    assert filled.seq < partial.seq


def test_pass_sequence_is_monotonic_across_threads(tmp_path: Path) -> None:
    """Ten passes over ten distinct sets are all in flight at once; each is
    started only after the previous one is parked, so start order is known."""
    managed = tmp_path / "managed"
    arrived = {f"t{index}": threading.Event() for index in range(10)}
    release = threading.Event()

    def resolve_tag(repo: str) -> str:
        arrived[repo.split("/")[1]].set()
        assert release.wait(timeout=10)
        return "1.0.0"

    service = _state_service(
        tmp_path, which=lambda cmd: str(managed / cmd), resolve_tag=resolve_tag
    )
    started: list[Future[object]] = []
    for index in range(10):
        tool = _gh_tool(f"t{index}")
        started.append(_start(lambda tool=tool: service.refresh([tool])))
        assert arrived[tool.id].wait(timeout=10)
    release.set()
    for run in started:
        assert _join(run) is None
    seqs: list[int] = []
    for index in range(10):
        state = service.state_of(f"t{index}")
        assert state is not None
        seqs.append(state.seq)
    assert len(set(seqs)) == 10
    assert all(left < right for left, right in zip(seqs, seqs[1:], strict=False))


def test_identical_passes_share_one_flight(tmp_path: Path) -> None:
    hold = _Hold()
    service = _held_service(tmp_path, hold)
    a, b = _gh_tool("a"), _gh_tool("b")
    finished: list[str] = []

    def first() -> None:
        service.refresh([a, b])
        finished.append("a")

    def second() -> None:
        service.refresh([b, a])
        finished.append("b")

    run_a = _start(first)
    assert hold.holding.wait(timeout=10)
    run_b = _start(second)
    assert _still_running(run_b)
    assert hold.calls == 1
    hold.release.set()
    assert _join(run_a) is None
    assert _join(run_b) is None
    assert sorted(finished) == ["a", "b"]
    assert hold.calls == 2
    state_a = service.state_of("a")
    state_b = service.state_of("b")
    assert state_a is not None
    assert state_b is not None
    assert state_a.seq == state_b.seq
    service.refresh([_gh_tool("c")])
    nxt = service.state_of("c")
    assert nxt is not None
    assert nxt.seq == state_a.seq + 1


def test_join_never_crosses_an_invalidate(tmp_path: Path) -> None:
    hold = _Hold()
    service = _held_service(tmp_path, hold)
    a = _gh_tool("a")
    run_a = _start(lambda: service.refresh([a]))
    assert hold.holding.wait(timeout=10)
    service.invalidate(reason="update")
    service.refresh([a])
    assert hold.calls == 2
    own = service.state_of("a")
    assert own is not None
    hold.release.set()
    assert _join(run_a) is None
    assert service.state_of("a") is own


def test_a_failed_shared_pass_raises_in_every_joiner(tmp_path: Path) -> None:
    boom = OSError("boom")
    failures = {"left": 1}

    def present(_tool: Tool) -> bool:
        if failures["left"]:
            failures["left"] -= 1
            raise boom
        return True

    hold = _Hold()
    service = _held_service(tmp_path, hold, present=present)
    a = _gh_tool("a")
    run_a = _start(lambda: service.refresh([a]))
    assert hold.holding.wait(timeout=10)
    run_b = _start(lambda: service.refresh([a]))
    assert _still_running(run_b)
    hold.release.set()
    assert _join(run_a) is boom
    assert _join(run_b) is boom
    assert hold.calls == 1
    service.refresh([a])
    assert hold.calls == 2
    assert service.state_of("a") is not None


def test_cache_save_failure_keeps_states_and_sets_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    managed = tmp_path / "managed"
    service = _state_service(tmp_path, which=lambda cmd: str(managed / cmd))

    failing = {"on": True}

    def full(
        path: Path,
        cache: Mapping[str, VersionCacheEntry],
        *,
        managers: Mapping[str, object] | None = None,
        skills: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        if failing["on"]:
            raise OSError("disk full")
        save_version_cache(path, cache, managers=managers, skills=skills)

    monkeypatch.setattr("installer.version_status.save_version_cache", full)
    service.refresh([_gh_tool("a")])
    assert service.state_of("a") is not None
    assert service.warning is not None
    assert "disk full" in service.warning
    failing["on"] = False
    service.refresh([_gh_tool("a")])
    assert service.warning is None


def test_skill_cache_save_failure_still_settles_the_packs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    pack = _superpowers()
    service = _pack_service(
        home, _probe_for(_listing((_SP_ID, "user", True, "6.4.1"))), harnesses=frozenset({"claude"})
    )
    service.refresh([pack])
    original = save_version_cache

    def full(
        path: Path,
        cache: Mapping[str, VersionCacheEntry],
        *,
        managers: Mapping[str, object] | None = None,
        skills: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        if skills is not None:
            raise OSError("disk full")
        original(path, cache, managers=managers, skills=skills)

    monkeypatch.setattr("installer.version_status.save_version_cache", full)
    hosts = service.refresh_skills([pack])
    assert hosts["superpowers"].stale is False
    state = service.state_of(pack.id)
    assert state is not None
    assert state.health is Health.OK
    assert service.warning == "version cache not saved: disk full"


def test_failed_invalidate_save_still_reprobes_the_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(list(argv))
        return _listing((_SP_ID, "user", True, "6.4.1"))

    pack = _superpowers()
    service = _pack_service(home, probe, harnesses=frozenset({"claude"}))
    service.refresh([pack])
    service.refresh_skills([pack])
    assert calls.count(["claude", "plugin", "list", "--json"]) == 1
    original = save_version_cache
    failing = {"on": True}

    def full(
        path: Path,
        cache: Mapping[str, VersionCacheEntry],
        *,
        managers: Mapping[str, object] | None = None,
        skills: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        if failing["on"]:
            raise OSError("disk full")
        original(path, cache, managers=managers, skills=skills)

    monkeypatch.setattr("installer.version_status.save_version_cache", full)
    with pytest.raises(OSError, match="disk full"):
        service.invalidate(reason="test")
    failing["on"] = False
    service.refresh_skills([pack])
    assert calls.count(["claude", "plugin", "list", "--json"]) == 2


def test_only_published_records_are_cached(tmp_path: Path) -> None:
    hold = _Hold(tag="9.9.9")
    service = _held_service(tmp_path, hold)
    a, b = _gh_tool("a"), _gh_tool("b")
    run_a = _start(lambda: service.refresh([a]))
    assert hold.holding.wait(timeout=10)
    # B: a different set, so it runs its own pass; its tags differ from A's.
    hold.tag = "2.0.0"
    service.refresh([a, b])
    hold.release.set()
    assert _join(run_a) is None
    cached = load_version_cache(tmp_path / "versions.json")
    assert {tool_id: entry.latest_version for tool_id, entry in cached.items()} == {
        "a": "2.0.0",
        "b": "2.0.0",
    }


# -- 19-08 Task 3: live has_brew per pass, skill packs CHECKING until probed. --

_BREW = "/home/linuxbrew/.linuxbrew/bin/brew"
_CHECKING_HOSTS = "checking which hosts have it"
_SEEDED_NOTE = "host status from the previous run, re-checking"


def _no_brew_platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


class _BrewWorld:
    """A PATH whose `brew` answer flips, plus inventory readers that record
    the `has_brew` each query was made with."""

    def __init__(self, managed: Path, *, tools: tuple[str, ...] = ()) -> None:
        self.brew = False
        self.managed = managed
        self.tools = tools
        self.inventory_calls: list[bool] = []

    def which(self, cmd: str) -> str | None:
        if cmd == "brew":
            return _BREW if self.brew else None
        return str(self.managed / cmd) if cmd in self.tools else None

    def read_inventory(self, *, has_brew: bool, **_kwargs: object) -> ManagerInventory:
        self.inventory_calls.append(has_brew)
        return ManagerInventory(
            brew_formulae={} if has_brew else None,
            brew_casks={} if has_brew else None,
            pnpm_globals=frozenset(),
            uv_tools={},
            brew_prefix=Path("/home/linuxbrew/.linuxbrew") if has_brew else None,
        )

    def read_outdated(self, *, has_brew: bool, **_kwargs: object) -> OutdatedReport:
        return OutdatedReport(
            brew={} if has_brew else None, cask={} if has_brew else None, pnpm={}, uv={}
        )

    def service(
        self, tmp_path: Path, *, resolve_tag: Callable[[str], str] = lambda _r: "1.0.0"
    ) -> VersionRefreshService:
        return VersionRefreshService(
            platform=_no_brew_platform(),
            cache_path=tmp_path / "versions.json",
            resolve_tag=resolve_tag,
            probe_output=lambda _argv: "0.9.0",
            now=lambda: _STATE_NOW,
            managed_bin_dir=self.managed,
            which=self.which,
            artifacts_for=lambda tool: [self.managed / tool.cmd],
            read_inventory_fn=self.read_inventory,
            read_outdated_fn=self.read_outdated,
            pnpm_packages=lambda: (),
            resolve_pnpm=lambda: None,
            query=lambda *_args, **_kwargs: "",
        )


@pytest.mark.parametrize("shape", ["no-snapshot", "fresh-snapshot-without-brew"])
def test_has_brew_is_reread_each_pass(tmp_path: Path, shape: str) -> None:
    world = _BrewWorld(tmp_path / "managed")
    service = world.service(tmp_path)
    tool = _brew_tool()
    service.refresh([tool])
    first = service.state_of(tool.id)
    assert first is not None
    assert first.health is Health.UNAVAILABLE
    assert first.reasons[0] == NEEDS_BREW_REASON
    assert service.platform.has_brew is False
    snapshot = load_manager_snapshot(tmp_path / "versions.json")
    assert snapshot is not None
    assert snapshot.checked_at == _STATE_NOW.isoformat()
    if shape == "no-snapshot":
        save_version_cache(tmp_path / "versions.json", {}, managers={})
    world.brew = True
    world.inventory_calls.clear()
    service.refresh([tool])
    second = service.state_of(tool.id)
    assert second is not None
    assert second.health is Health.MISSING
    assert service.platform.has_brew is True
    assert resolve_methods(tool, service.platform)
    assert world.inventory_calls == [True]


def test_manager_snapshot_query_uses_the_live_has_brew(tmp_path: Path) -> None:
    world = _BrewWorld(tmp_path / "managed")
    world.brew = True
    service = world.service(tmp_path)
    tool = _brew_tool()
    service.refresh([tool])
    assert world.inventory_calls == [True]
    # Fresh, and its brew evidence agrees with has_brew: reused.
    service.refresh([tool])
    assert world.inventory_calls == [True]
    # A failed snapshot inside its retry backoff is reused whatever its evidence.
    failed = ManagerSnapshot(
        inventory=_empty_inventory(),
        outdated=_empty_outdated(),
        checked_at=(_STATE_NOW - MANAGER_STALE_AFTER - timedelta(hours=1)).isoformat(),
        failed_at=(_STATE_NOW - timedelta(minutes=10)).isoformat(),
    )
    save_version_cache(tmp_path / "versions.json", {}, managers=encode_manager_snapshot(failed))
    service.refresh([tool])
    assert world.inventory_calls == [True]


def test_a_pass_uses_one_platform_throughout(tmp_path: Path) -> None:
    world = _BrewWorld(tmp_path / "managed", tools=("g", "y"))
    hold = _Hold()
    service = world.service(tmp_path, resolve_tag=hold)
    g, x, y = _gh_tool("g"), _brew_tool(), _gh_tool("y")
    run_a = _start(lambda: service.refresh([g, x]))
    assert hold.holding.wait(timeout=10)
    assert world.inventory_calls == [False]
    world.brew = True
    service.refresh([y])
    assert service.platform.has_brew is True
    hold.release.set()
    assert _join(run_a) is None
    state = service.state_of(x.id)
    assert state is not None
    assert state.health is Health.UNAVAILABLE
    assert world.inventory_calls == [False, True]
    assert service.platform.has_brew is True


def _skill_state_service(
    tmp_path: Path, probe: Callable[[list[str]], str] | None = None
) -> VersionRefreshService:
    managed = tmp_path / "managed"
    return VersionRefreshService(
        platform=Platform(os="linux", arch="amd64", immutable=True, has_brew=False),
        cache_path=tmp_path / "versions.json",
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=lambda _argv: "1.0.0",
        now=lambda: _STATE_NOW,
        managed_bin_dir=managed,
        skill_probe=probe,
        skill_home=tmp_path,
        which=lambda cmd: str(managed / cmd) if cmd == "alpha" else None,
        artifacts_for=lambda tool: [managed / tool.cmd],
        query=lambda *_args, **_kwargs: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        resolve_pnpm=lambda: None,
    )


def test_skill_pack_without_data_is_checking(tmp_path: Path) -> None:
    service = _skill_state_service(tmp_path)
    pack = _claude_pack()
    service.refresh([pack])
    state = service.state_of(pack.id)
    assert state is not None
    assert state.health is Health.CHECKING
    assert state.present is False
    built = tool_state(
        pack,
        generation=state.generation,
        seq=state.seq,
        platform=service.platform,
        present=True,
        ownership=state.ownership,
        version=state.version,
        removable=state.removable,
        checking=(_CHECKING_HOSTS,),
    )
    assert (state.health, state.reasons) == (built.health, built.reasons)
    assert state.reasons[0] == _CHECKING_HOSTS


def test_skill_pack_states_follow_refresh_skills(tmp_path: Path) -> None:
    service = _skill_state_service(tmp_path / "a", lambda _argv: _CLAUDE_SUPERPOWERS_JSON)
    pack, alpha = _claude_pack(), _gh_tool("alpha")
    service.refresh([pack, alpha])
    binary = service.state_of("alpha")
    checking = service.state_of(pack.id)
    assert binary is not None
    assert checking is not None
    assert checking.health is Health.CHECKING
    service.refresh_skills([pack])
    probed = service.state_of(pack.id)
    assert probed is not None
    assert probed.health is Health.OK
    assert probed.generation == checking.generation == service.epoch
    assert probed.seq == checking.seq
    assert probed.skill_hosts is not None
    assert probed.skill_hosts.hosts == {"claude": "present"}
    assert service.state_of("alpha") is binary

    absent = _skill_state_service(tmp_path / "b", lambda _argv: "[]")
    absent.refresh([pack])
    absent.refresh_skills([pack])
    missing = absent.state_of(pack.id)
    assert missing is not None
    assert missing.health is Health.MISSING


def test_refresh_skills_superseded_rebuilds_nothing(tmp_path: Path) -> None:
    holder: dict[str, VersionRefreshService] = {}

    def skill_probe(_argv: list[str]) -> str:
        holder["svc"].invalidate(reason="x")
        return _CLAUDE_SUPERPOWERS_JSON

    service = _skill_state_service(tmp_path, skill_probe)
    holder["svc"] = service
    pack, alpha = _claude_pack(), _gh_tool("alpha")
    service.refresh([pack, alpha])
    service.refresh_skills([pack])
    assert _held_skills(service).get(pack.id) is None
    assert service.state_of(pack.id) is None
    assert service.state_of("alpha") is None
    service.refresh([pack])
    fresh = service.state_of(pack.id)
    assert fresh is not None
    assert fresh.generation == service.epoch
    assert fresh.health is Health.CHECKING


def test_seeded_skill_hosts_are_a_note(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    save_version_cache(path, {}, skills={"superpowers": {"claude": "present"}})
    service = _skill_state_service(tmp_path)
    service.seed_skills_from_cache()
    pack = _claude_pack()
    service.refresh([pack])
    state = service.state_of(pack.id)
    assert state is not None
    # A cache-seeded answer is informational only (G8): CHECKING, never OK.
    assert state.health is Health.CHECKING
    assert _SEEDED_NOTE in state.reasons


def test_absent_pack_keeps_configuration_facts_as_reasons() -> None:
    pack = _claude_pack()
    fact = "disabled: superpowers@claude-plugins-official in user scope (6.4.1)"
    step = ConfigStep(
        "enable superpowers@claude-plugins-official in user scope", "plugin_enable", "claude"
    )

    def build(*, present: bool) -> ToolState:
        return tool_state(
            pack,
            generation=0,
            platform=_platform(),
            present=present,
            ownership=_unknown_owner(pack),
            version=None,
            removable=_NO_REMOVAL,
            misconfigured=(fact,),
            unconfigured=(step,),
            notes=("no manager claimed the tool",),
        )

    absent = build(present=False)
    assert absent.health is Health.MISSING
    assert absent.reasons == (fact, "no manager claimed the tool")
    assert absent.unconfigured == (step,)
    present = build(present=True)
    assert present.health is Health.MISCONFIGURED
    assert present.reasons == (fact, "no manager claimed the tool")
    assert present.unconfigured == (step,)


def test_suite_sandbox_redirects_skill_home(tmp_path_factory: pytest.TempPathFactory) -> None:
    sandbox = version_status.default_skill_home()
    assert not sandbox.is_relative_to(_REAL_HOME)
    assert sandbox.is_relative_to(tmp_path_factory.getbasetemp())
    marker = sandbox / ".claude" / "gsd-install-state.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}")
    pack = _skill_pack("opengsd", (SkillStatusProbe("claude", "install-state", "gsd-core"),))
    service = VersionRefreshService(
        platform=_no_brew_platform(),
        cache_path=tmp_path_factory.mktemp("skills") / "versions.json",
        skill_probe=lambda _argv: "",
        which=lambda _cmd: None,
        query=lambda *_args, **_kwargs: "",
        pnpm_packages=lambda: (),
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
    )
    service.refresh_skills([pack])
    status = _held_skills(service).get("opengsd")
    assert status is not None
    assert status.hosts == {"claude": "present"}


# -- 19-12 Task 1: the pass resolves uv tools by `uv tool dir` and looks
# through this installer's own shims (D-12, D-13, review M9). --


def _owner_pass_service(
    tmp_path: Path,
    *,
    which: Callable[[str], str | None],
    managed: Path,
    query: Callable[..., str] = lambda *_args, **_kwargs: "",
    inventory: ManagerInventory | None = None,
    path_value: str = "",
    native_probe: Callable[[list[str]], str] | None = None,
    platform: Platform | None = None,
    probe_output: Callable[[list[str]], str | None] = lambda _argv: "1.0.0",
    artifacts_for: Callable[[Tool], list[Path]] = lambda _tool: [],
    inventory_reads: list[dict[str, object]] | None = None,
) -> VersionRefreshService:
    held = inventory if inventory is not None else _empty_inventory()

    def read_inventory(**kwargs: object) -> ManagerInventory:
        if inventory_reads is not None:
            inventory_reads.append(kwargs)
        return held

    tmp_path.mkdir(parents=True, exist_ok=True)
    return VersionRefreshService(
        platform=platform if platform is not None else _no_brew_platform(),
        cache_path=tmp_path / "versions.json",
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=probe_output,
        now=lambda: _STATE_NOW,
        managed_bin_dir=managed,
        which=which,
        query=query,
        artifacts_for=artifacts_for,
        read_inventory_fn=read_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        native_probe=native_probe,
        path_value=lambda: path_value,
    )


def _uv_dir_query(answer: Path) -> tuple[Callable[..., str], list[list[str]]]:
    asked: list[list[str]] = []

    def query(argv: list[str], *_args: object, **_kwargs: object) -> str:
        asked.append(list(argv))
        return f"{answer}\n" if argv == ["uv", "tool", "dir"] else ""

    return query, asked


def _graphify() -> Tool:
    return Tool(
        id="graphify",
        name="graphify",
        category="dev",
        cmd="graphify",
        methods=(Method(kind="uv-tool", params={"pypi_pkg": "graphifyy"}),),
    )


def test_pass_resolves_graphify_to_uv_by_tool_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    managed = home / ".local" / "bin"
    managed.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    uv_tools = tmp_path / "uv" / "tools"
    real = uv_tools / "graphifyy" / "bin" / "graphify"
    real.parent.mkdir(parents=True)
    real.write_text("bin")
    (managed / "graphify").symlink_to(real)
    hits = {"uv": str(tmp_path / "uv" / "uv"), "graphify": str(managed / "graphify")}
    query, _asked = _uv_dir_query(uv_tools)
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: hits.get(cmd),
        managed=managed,
        query=query,
        inventory=replace(_empty_inventory(), uv_tools={"graphifyy": "0.9.53"}),
    )
    service.refresh([_graphify()])
    state = service.state_of("graphify")
    assert state is not None
    assert state.ownership.owner == "uv"
    assert state.present is True


def test_pass_queries_uv_tool_dir_once(tmp_path: Path) -> None:
    tools = [_gh_tool("alpha"), _gh_tool("beta"), _gh_tool("gamma")]
    query, asked = _uv_dir_query(tmp_path / "uv" / "tools")
    service = _owner_pass_service(
        tmp_path / "with-uv",
        which=lambda cmd: "/x/bin/uv" if cmd == "uv" else None,
        managed=tmp_path / "managed",
        query=query,
    )
    service.refresh(tools)
    assert asked.count(["uv", "tool", "dir"]) == 1

    query, asked = _uv_dir_query(tmp_path / "uv" / "tools")
    service = _owner_pass_service(
        tmp_path / "without-uv",
        which=lambda _cmd: None,
        managed=tmp_path / "managed",
        query=query,
    )
    service.refresh(tools)
    assert ["uv", "tool", "dir"] not in asked


def _redirect_shim(managed: Path) -> Path:
    managed.mkdir(parents=True, exist_ok=True)
    shim = managed / "pnpm"
    shim.write_text(f'#!/bin/sh\n{REDIRECT_SENTINEL}\nexec /nowhere/volta install "$@"\n')
    shim.chmod(0o755)
    return shim


def _pnpm_script_tool() -> Tool:
    return Tool(
        id="pnpm",
        name="pnpm",
        category="node",
        cmd="pnpm",
        methods=(Method(kind="script", params={"url": "https://get.pnpm.io/install.sh"}),),
    )


def _volta_pnpm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`<tmp>/volta/bin/pnpm` -> `volta-shim`, with VOLTA_HOME pointing there."""
    volta_bin = tmp_path / "volta" / "bin"
    volta_bin.mkdir(parents=True)
    volta_shim = volta_bin / "volta-shim"
    volta_shim.write_text("#!/bin/sh\n")
    volta_shim.chmod(0o755)
    (volta_bin / "pnpm").symlink_to(volta_shim)
    monkeypatch.setenv("VOLTA_HOME", str(tmp_path / "volta"))
    return volta_bin


def test_pass_looks_through_the_redirect_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    managed = tmp_path / "managed"
    shim = _redirect_shim(managed)
    volta_bin = _volta_pnpm(tmp_path, monkeypatch)
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(shim) if cmd == "pnpm" else None,
        managed=managed,
        path_value=os.pathsep.join((str(managed), str(volta_bin))),
    )
    service.refresh([_pnpm_script_tool()])
    state = service.state_of("pnpm")
    assert state is not None
    assert state.ownership.owner == "volta"
    assert state.present is True


def test_redirect_shim_without_a_real_binary_is_missing(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    shim = _redirect_shim(managed)
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(shim) if cmd == "pnpm" else None,
        managed=managed,
        path_value=str(managed),
    )
    service.refresh([_pnpm_script_tool()])
    state = service.state_of("pnpm")
    assert state is not None
    assert state.health is Health.MISSING


def test_shim_only_managed_bin_path_is_missing(tmp_path: Path) -> None:
    """review M9: the implicit artifact path holds only the redirect shim."""
    managed = tmp_path / "managed"
    shim = _redirect_shim(managed)
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(shim) if cmd == "pnpm" and shim.is_file() else None,
        managed=managed,
        path_value=str(managed),
    )
    tool = _raw_gh_tool("pnpm")
    service.refresh([tool])
    state = service.state_of("pnpm")
    assert state is not None
    assert state.health is Health.MISSING

    shim.write_text("real binary")
    service.refresh([tool])
    state = service.state_of("pnpm")
    assert state is not None
    assert state.present is True


# -- 19-12 Task 2: one batched native path query per pass (D-11). --

_RPM_BATCH = ["rpm", "-qf", "--qf", "[%{FILENAMES}\\t%{=NAME}\\n]"]
_RPM_PER_PATH = ["rpm", "-qf", "--qf", "%{NAME}\\n"]
_RPM_OSTREE_STATUS = ["rpm-ostree", "status", "--json"]


def _dnf_tool(cmd: str, package: str | None = None) -> Tool:
    return Tool(
        id=cmd,
        name=cmd,
        category="data",
        cmd=cmd,
        methods=(Method(kind="dnf", params={"package": package or cmd}),),
        owner_probes=("rpm-ostree", "dnf"),
    )


def _rpm_host(
    owners: Mapping[str, str], *, layered: tuple[str, ...] = ()
) -> tuple[Callable[[list[str]], str], list[list[str]]]:
    """A recording rpm database: `owners` maps a file path to its package."""
    calls: list[list[str]] = []
    installed = set(owners.values())

    def probe(command: list[str]) -> str:
        calls.append(list(command))
        if command[:4] == _RPM_BATCH:
            return "".join(f"{path}\t{owners[path]}\n" for path in command[4:] if path in owners)
        if command[:4] == _RPM_PER_PATH and command[4] in owners:
            return f"{owners[command[4]]}\n"
        if command[:2] == ["rpm", "-q"] and command[-1] in installed:
            return f"{command[-1]}\n"
        if command == _RPM_OSTREE_STATUS:
            booted = {"booted": True, "requested-packages": list(layered)}
            return json.dumps({"deployments": [booted]})
        raise subprocess.CalledProcessError(1, command, output="")

    return probe, calls


def _system_bin(tmp_path: Path) -> Path:
    system = tmp_path / "usr" / "bin"
    system.mkdir(parents=True)
    return system


def test_pass_makes_one_rpm_path_query_for_many_native_tools(tmp_path: Path) -> None:
    system = _system_bin(tmp_path)
    tools = [_dnf_tool(f"native{n}") for n in range(5)]
    probe, calls = _rpm_host({str(system / tool.cmd): tool.cmd for tool in tools})
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(system / cmd) if cmd.startswith("native") else None,
        managed=tmp_path / "managed",
        native_probe=probe,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
    )
    service.refresh(tools)
    assert [call for call in calls if call[:4] == _RPM_BATCH] == [
        [*_RPM_BATCH, *(str(system / tool.cmd) for tool in tools)]
    ]
    assert [call for call in calls if call[:4] == _RPM_PER_PATH] == []
    for tool in tools:
        state = service.state_of(tool.id)
        assert state is not None
        assert state.ownership.owner == "dnf"


def test_pass_excludes_tracked_paths_from_the_batch(tmp_path: Path) -> None:
    system = _system_bin(tmp_path)
    managed = tmp_path / "managed"
    brew_prefix = tmp_path / "brew"
    hits = {
        "native0": str(system / "native0"),
        "brewed": str(brew_prefix / "bin" / "brewed"),
        "managedtool": str(managed / "managedtool"),
    }
    probe, calls = _rpm_host({hits["native0"]: "native0"})
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: hits.get(cmd),
        managed=managed,
        native_probe=probe,
        inventory=replace(_empty_inventory(), brew_prefix=brew_prefix),
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
    )
    service.refresh([_dnf_tool(name) for name in hits])
    batches = [call for call in calls if call[:4] == _RPM_BATCH]
    assert batches == [[*_RPM_BATCH, hits["native0"]]]


def test_pass_without_native_probe_makes_no_native_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object) -> object:
        raise AssertionError("a pass without a native probe built a native index")

    monkeypatch.setattr(version_status, "native_index", refuse)
    system = _system_bin(tmp_path)
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(system / cmd),
        managed=tmp_path / "managed",
        native_probe=None,
    )
    service.refresh([_dnf_tool("native0")])
    state = service.state_of("native0")
    assert state is not None
    assert state.ownership.owner == "unknown"


def test_pass_reads_rpm_ostree_status_once(tmp_path: Path) -> None:
    system = _system_bin(tmp_path)
    tools = [_dnf_tool(f"layered{n}") for n in range(3)]
    probe, calls = _rpm_host(
        {str(system / tool.cmd): tool.cmd for tool in tools},
        layered=tuple(tool.cmd for tool in tools),
    )
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(system / cmd) if cmd.startswith("layered") else None,
        managed=tmp_path / "managed",
        native_probe=probe,
        platform=Platform(os="fedora", arch="amd64", immutable=True, has_brew=False),
    )
    service.refresh(tools)
    assert calls.count(_RPM_OSTREE_STATUS) == 1
    for tool in tools:
        state = service.state_of(tool.id)
        assert state is not None
        assert state.ownership.owner == "rpm-ostree"


def test_resolve_owner_uses_the_pass_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The update path's owner comes from a FRESH inventory read with the live
    platform, through the same evidence as the pass (review M12)."""
    home = tmp_path / "home"
    managed = home / ".local" / "bin"
    managed.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    uv_tools = tmp_path / "uv" / "tools"
    real = uv_tools / "graphifyy" / "bin" / "graphify"
    real.parent.mkdir(parents=True)
    real.write_text("bin")
    (managed / "graphify").symlink_to(real)
    hits = {
        "uv": str(tmp_path / "uv" / "uv"),
        "graphify": str(managed / "graphify"),
        "brew": str(tmp_path / "homebrew" / "bin" / "brew"),
    }
    query, asked = _uv_dir_query(uv_tools)
    reads: list[dict[str, object]] = []
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: hits.get(cmd),
        managed=managed,
        query=query,
        inventory=replace(_empty_inventory(), uv_tools={"graphifyy": "0.9.53"}),
        inventory_reads=reads,
    )
    service.refresh([_graphify()])
    state = service.state_of("graphify")
    assert state is not None
    assert len(reads) == 1
    owner = service.resolve_owner(_graphify())
    assert owner.owner == "uv"
    assert owner == state.ownership
    assert len(reads) == 2
    assert reads[1]["has_brew"] is True
    assert asked.count(["uv", "tool", "dir"]) == 2


def test_pass_still_makes_one_native_query_with_resolve_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review M12: the pass resolves owners from its batched evidence and never
    through the public one-tool operation, so it still makes one batched path
    query; a later `resolve_owner` asks on its own."""
    system = _system_bin(tmp_path)
    tools = [_dnf_tool(f"native{n}") for n in range(5)]
    probe, calls = _rpm_host({str(system / tool.cmd): tool.cmd for tool in tools})
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(system / cmd) if cmd.startswith("native") else None,
        managed=tmp_path / "managed",
        native_probe=probe,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
    )
    original = service.resolve_owner
    used: list[str] = []

    def spy(tool: Tool) -> ManagerOwnership:
        used.append(tool.id)
        return original(tool)

    monkeypatch.setattr(service, "resolve_owner", spy)
    service.refresh(tools)
    assert used == []
    batch = [[*_RPM_BATCH, *(str(system / tool.cmd) for tool in tools)]]
    assert [call for call in calls if call[:4] == _RPM_BATCH] == batch
    assert [call for call in calls if call[:4] == _RPM_PER_PATH] == []
    pass_calls = list(calls)
    owner = service.resolve_owner(tools[0])
    assert owner.owner == "dnf"
    assert calls[: len(pass_calls)] == pass_calls
    assert len(calls) > len(pass_calls)
    assert [call for call in calls if call[:4] == _RPM_BATCH] == batch


def test_pass_memoizes_declared_package_queries(tmp_path: Path) -> None:
    """checker I2: one query per distinct declared package per pass, and the
    memo never outlives the pass."""
    system = _system_bin(tmp_path)
    tools = [_dnf_tool("first", "shared"), _dnf_tool("second", "shared")]
    probe, calls = _rpm_host({str(system / "first"): "shared", str(system / "second"): "shared"})
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: str(system / cmd),
        managed=tmp_path / "managed",
        native_probe=probe,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
    )
    declared = ["rpm", "-q", "--qf", "%{NAME}\\n", "shared"]
    service.refresh(tools)
    assert calls.count(declared) == 1
    service.refresh(tools)
    assert calls.count(declared) == 2


# -- 19-12 Task 3: owner and version facts become state reasons; shim-managed
# tools probe the unresolved path (D-15, 19-RESEARCH Pitfall 6). --

_INSTALLER_NO_LATEST = (
    "latest version cannot be determined for this install method — "
    "pressing u re-runs the same install path this tool was originally installed with"
)
_STALE_NOTE = (
    "the shown latest version came from a cache entry at or past STALE_AFTER "
    "and a re-check is pending"
)


def _status(tool: Tool, **fields: object) -> VersionStatus:
    base = VersionStatus(
        tool_id=tool.id,
        installed="1.0.0",
        latest="1.0.0",
        outdated=False,
        stale=False,
        source="brew",
    )
    return replace(base, **fields)


def test_owner_notes_are_state_reasons(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    prefix = tmp_path / "brew"
    tool = _brew_tool()
    hits = {"brew": str(prefix / "bin" / "brew"), "rg": str(prefix / "bin" / "rg")}
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: hits.get(cmd),
        managed=managed,
        inventory=replace(
            _empty_inventory(), brew_formulae={"ripgrep": "14.1.0"}, brew_prefix=prefix
        ),
        artifacts_for=lambda candidate: [managed / candidate.cmd],
        platform=_platform(),
    )
    service.refresh([tool])
    state = service.state_of("rg")
    assert state is not None
    assert state.ownership.owner == "brew"
    assert state.ownership.shadowed is True
    also = also_installed_note(state.ownership)
    assert also is not None
    assert state.reasons == (
        "managed by Homebrew",
        f"{also} — live copy at {state.ownership.active_path}",
    )


def test_off_policy_note() -> None:
    tool = _codegraph()
    ownership = replace(_owned(tool, "brew", package="codegraph"), off_policy=True)
    declared = declared_manager_label(tool, _platform())
    real = owner_label(ownership)
    assert declared is not None
    assert real is not None
    sentence = f"{real} owns this copy; the catalog's policy installs {tool.id} via {declared}"
    assert ownership_notes(tool, ownership, _platform()).count(sentence) == 1


def test_unknown_owner_reason_note() -> None:
    tool = _gh_tool("alpha")
    notes = ownership_notes(tool, _unknown_owner(tool), _platform())
    assert notes == ("no manager claimed the tool",)


def test_active_path_note() -> None:
    tool = _gh_tool("alpha")
    ownership = replace(_unknown_owner(tool), active_path=Path("/opt/x/bin/alpha"))
    notes = ownership_notes(tool, ownership, _platform())
    assert notes.count("active binary resolves to /opt/x/bin/alpha") == 1
    assert notes.count("no manager claimed the tool") == 1


def test_version_notes() -> None:
    tool = _codegraph()
    installer = _owned(tool, "installer")
    no_comparison = _status(tool, latest=None, outdated=None, stale=True, source="installer")
    notes = version_notes(tool, no_comparison, installer, present=True)
    assert notes.count(_INSTALLER_NO_LATEST) == 1

    pnpm_tool = _node_tool(pinned=True)
    pinned = _status(pnpm_tool, source="pnpm", pinned_spec="puppeteer ^25")
    notes = version_notes(pnpm_tool, pinned, _owned(pnpm_tool, "pnpm"), present=True)
    assert (
        notes.count("this project pins puppeteer ^25 and constrains the version deliberately") == 1
    )

    stale = _status(tool, latest="2.0.0", outdated=True, stale=True, source="github")
    assert version_notes(tool, stale, installer, present=True).count(_STALE_NOTE) == 1


def test_version_unreadable_and_no_comparison_reasons() -> None:
    tool = _gh_tool("alpha")
    ownership = _unknown_owner(tool)
    unreadable = _status(tool, installed=None, latest=None, outdated=None, source="unknown")
    notes = version_notes(tool, unreadable, ownership, present=True)
    assert "version unreadable" in notes
    assert "no latest version to compare against" not in notes
    no_latest = _status(tool, latest=None, outdated=None, stale=True, source="unknown")
    assert "no latest version to compare against" in version_notes(
        tool, no_latest, ownership, present=True
    )
    for status in (unreadable, no_latest):
        absent = version_notes(tool, status, ownership, present=False)
        assert "version unreadable" not in absent
        assert "no latest version to compare against" not in absent


def test_skill_pack_gets_no_binary_notes(tmp_path: Path) -> None:
    pack = _skill_pack("superpowers", (SkillStatusProbe("claude", "install-state", "gsd-core"),))
    ownership = _unknown_owner(pack)
    unread = _status(pack, installed=None, latest=None, outdated=None, source="unknown")
    assert ownership_notes(pack, ownership, _platform()) == ()
    assert version_notes(pack, unread, ownership, present=True) == ()

    service = _owner_pass_service(tmp_path, which=lambda _cmd: None, managed=tmp_path / "managed")
    service.refresh([pack])
    state = service.state_of("superpowers")
    assert state is not None
    assert state.ownership.owner == "unknown"
    binary_sentences = {
        "version unreadable",
        "no latest version to compare against",
        state.ownership.unknown_reason,
    }
    assert not binary_sentences & set(state.reasons)


def _recording_probe() -> tuple[Callable[[list[str]], str | None], list[list[str]]]:
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str | None:
        calls.append(list(argv))
        return "1.2.3"

    return probe, calls


def test_volta_tool_version_probes_the_unresolved_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    volta_bin = _volta_pnpm(tmp_path, monkeypatch)
    hit = str(volta_bin / "pnpm")
    probe, calls = _recording_probe()
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: hit if cmd == "pnpm" else None,
        managed=tmp_path / "managed",
        probe_output=probe,
    )
    service.refresh([_pnpm_script_tool()])
    state = service.state_of("pnpm")
    assert state is not None
    assert state.ownership.owner == "volta"
    assert calls == [[hit, "--version"]]


def test_host_setup_tool_version_probes_the_unresolved_path(tmp_path: Path) -> None:
    launcher = tmp_path / "lib" / "pi" / "launcher.js"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("launcher")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "pi").symlink_to(launcher)
    hit = str(bin_dir / "pi")
    tool = _tool("pi", Method(kind="host_setup", params={"setup_id": "pi"}))
    probe, calls = _recording_probe()
    service = _owner_pass_service(
        tmp_path,
        which=lambda cmd: hit if cmd == "pi" else None,
        managed=tmp_path / "managed",
        probe_output=probe,
    )
    service.refresh([tool])
    state = service.state_of("pi")
    assert state is not None
    assert state.ownership.active_path == launcher
    assert calls == [[hit, "--version"]]


@pytest.mark.parametrize(
    "route", ["volta", "host_setup_installer", "host_setup_brew", "host_setup_github"]
)
def test_resolve_status_forwards_the_unresolved_path_for_volta_and_host_setup(route: str) -> None:
    """review C2-M5: every route from `resolve_status` into `_version_argv`
    carries the looked-through hit."""
    host_setup = Method(kind="host_setup", params={"setup_id": "demo"})
    if route == "volta":
        tool = _pnpm_script_tool()
        ownership = replace(_owned(tool, "volta"), method=None)
    elif route == "host_setup_github":
        tool = _tool("demo", host_setup, Method(kind="github_release", params={"repo": "o/demo"}))
        ownership = _owned(tool, "installer", method=host_setup)
    else:
        tool = _tool("demo", host_setup)
        owner: Owner = "brew" if route == "host_setup_brew" else "installer"
        ownership = _owned(tool, owner, method=host_setup)
    ownership = replace(ownership, active_path=Path(f"/resolved/{tool.cmd}"))

    def recorded(unresolved: str | None = None) -> list[list[str]]:
        calls, probe = _probe_calls()
        resolve_status(
            tool,
            ownership=ownership,
            outdated=_empty_outdated(),
            entry=None,
            now=_status_now(),
            probe_output=probe,
            resolve_tag=lambda _repo: "v1.0.0",
            platform=_platform(),
            unresolved=unresolved,
        )
        return calls

    assert recorded(unresolved=f"/x/bin/{tool.cmd}") == [[f"/x/bin/{tool.cmd}", "--version"]]
    assert recorded() == [[f"/resolved/{tool.cmd}", "--version"]]


def test_shadowed_note_variants() -> None:
    tool = _brew_tool()
    owned = replace(_owned(tool, "brew", package="ripgrep"), shadowed=True)
    other = OwnershipCandidate(
        owner="installer", method=None, package=None, current_version=None, evidence="test"
    )
    with_other = replace(owned, candidates=(*owned.candidates, other), active_path=None)
    also = also_installed_note(with_other)
    assert also is not None
    assert also in ownership_notes(tool, with_other, _platform())
    live = Path("/opt/homebrew/bin/rg")
    assert f"shadowed — live copy at {live}" in ownership_notes(tool, owned, _platform())
    alone = replace(owned, active_path=None)
    assert "shadowed" in ownership_notes(tool, alone, _platform())


# -- 19-14 Task 1: receipts are state evidence; drift is BROKEN and a corrupt
# receipt is unproven (D-08, SPEC R4). --

_LINUX = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)
_CHANGED = "changed since install"
_UNREADABLE = "install receipt unreadable — treated as unproven"
_YQ_BYTES = b"#!/bin/sh\necho yq 4.54.1\n"
_YQ_METHOD = Method(
    kind="github_release",
    params={"repo": "mikefarah/yq", "asset": "yq_linux_{arch.deb}", "member": "yq", "raw": True},
)
_RG_ASSET = "rg-14.1.0-x86_64.tar.gz"
_RG_METHOD = Method(
    kind="github_release",
    params={
        "repo": "BurntSushi/ripgrep",
        "asset": "rg-{ver}-{arch.machine}.tar.gz",
        "member": "rg-x/rg",
    },
)


def _yq() -> Tool:
    return Tool(id="yq", name="yq", category="data", cmd="yq", methods=(_YQ_METHOD,), tier="user")


def _rg_archive() -> Tool:
    return Tool(
        id="rg", name="ripgrep", category="search", cmd="rg", methods=(_RG_METHOD,), tier="user"
    )


def _scratch_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME is tmp_path; returns its `~/.local/bin` (the managed bin dir)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    return bin_dir


def _receipt_service(
    tmp_path: Path,
    bin_dir: Path,
    *,
    resolve_tag: Callable[[str], str] = lambda _repo: "v4.54.1",
    inventory: ManagerInventory | None = None,
    which: Callable[[str], str | None] | None = None,
) -> VersionRefreshService:
    def managed_which(cmd: str) -> str | None:
        hit = bin_dir / cmd
        return str(hit) if hit.exists() or hit.is_symlink() else None

    held = inventory if inventory is not None else _empty_inventory()

    def read_inventory(**_kwargs: object) -> ManagerInventory:
        return held

    return VersionRefreshService(
        platform=_LINUX,
        cache_path=tmp_path / "versions.json",
        resolve_tag=resolve_tag,
        probe_output=lambda _argv: "4.54.1",
        now=lambda: _STATE_NOW,
        managed_bin_dir=bin_dir,
        which=which if which is not None else managed_which,
        read_inventory_fn=read_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        query=lambda *_args, **_kwargs: "",
    )


def _settled(service: VersionRefreshService, tool: Tool) -> ToolState:
    service.refresh([tool])
    state = service.state_of(tool.id)
    assert state is not None
    return state


def _receipt_reasons(state: ToolState) -> list[str]:
    """The reasons this plan adds (locked 19-UI-SPEC copy), in state order."""
    return [
        r
        for r in state.reasons
        if r in (_CHANGED, _UNREADABLE) or r.startswith(("adopted: ", "not proven: "))
    ]


def _place_yq_with_receipt(bin_dir: Path) -> Path:
    placed = bin_dir / "yq"
    placed.write_bytes(_YQ_BYTES)
    assert receipts.record(_yq(), _YQ_METHOD, package=None, smoke=None, default_bin_dir=bin_dir)
    return placed


def test_state_carries_the_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    _place_yq_with_receipt(bin_dir)
    state = _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert state.receipt is not None
    assert state.receipt == receipts.read("yq")
    assert state.health is Health.OK
    assert state.removable.removable == (bin_dir / "yq",)


def test_drifted_receipt_is_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    placed = _place_yq_with_receipt(bin_dir)
    placed.write_bytes(_YQ_BYTES + b"# replaced\n")
    state = _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert state.health is Health.BROKEN
    assert state.reasons[0] == _CHANGED
    assert state.reasons.count(_CHANGED) == 1
    assert state.removable.removable == ()


def test_corrupt_receipt_is_an_unproven_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    (bin_dir / "yq").write_bytes(_YQ_BYTES)
    path = receipts.receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")
    state = _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert state.health is not Health.BROKEN
    assert _UNREADABLE in state.reasons
    assert state.receipt is None
    assert state.removable.removable == ()


def test_receiptless_kinds_have_no_receipt_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    system = tmp_path / "usr" / "bin"
    system.mkdir(parents=True)
    (system / "jq").write_bytes(b"#!/bin/sh\n")
    tool = Tool(
        id="jq",
        name="jq",
        category="data",
        cmd="jq",
        methods=(Method(kind="dnf", params={"package": "jq"}),),
        tier="user",
    )
    service = _receipt_service(
        tmp_path, bin_dir, which=lambda cmd: str(system / cmd) if cmd == "jq" else None
    )
    state = _settled(service, tool)
    assert state.receipt is None
    assert not _receipt_reasons(state)


def _pin_download_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workdir = tmp_path / "dl"
    workdir.mkdir(exist_ok=True)

    def fake_mkdtemp(prefix: str) -> str:
        del prefix
        workdir.mkdir(exist_ok=True)
        return str(workdir)

    monkeypatch.setattr(download.tempfile, "mkdtemp", fake_mkdtemp)
    return workdir


def _install(
    tool: Tool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: bytes = _YQ_BYTES,
    repair: bool = False,
) -> InstallOutcome:
    """Install `tool` (yq raw or the rg archive) through the real ladder, offline."""
    workdir = _pin_download_workdir(tmp_path, monkeypatch)
    opt = tmp_path / ".local" / "opt" / "rg"
    if tool.id == "rg":
        _calls, runner = fixture_runner(
            workdir, {_RG_ASSET: b"archive"}, member=opt / "rg-x" / "rg"
        )
        tag = "14.1.0"
    else:
        _calls, runner = fixture_runner(workdir, {"yq_linux_amd64": payload})
        tag = "v4.54.1"
    return install_tool(
        tool,
        _LINUX,
        runner=runner,
        resolve_tag=lambda _repo: tag,
        present=lambda _tool: False,
        repair=repair,
    )


def test_dir_drift_is_unproven_not_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A vendor rewrite of an archive's key file loses the proof, not the health.

    The row keeps its current-evidence health, says the unproven note once, and
    is not removable; the receipt stays (L-19-31)."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    member = tmp_path / ".local" / "opt" / "rg" / "rg-x" / "rg"
    member.parent.mkdir(parents=True)
    member.write_bytes(b"#!/bin/sh\n")
    (bin_dir / "rg").symlink_to(member)
    assert receipts.record(
        _rg_archive(), _RG_METHOD, package=None, smoke=None, default_bin_dir=bin_dir
    )
    member.write_bytes(b"#!/bin/sh\n# vendor self-update\n")
    state = _settled(_receipt_service(tmp_path, bin_dir), _rg_archive())
    assert state.health is not Health.BROKEN
    assert _CHANGED not in state.reasons
    assert state.reasons.count(_UNPROVEN) == 1
    assert state.removable.removable == ()
    assert state.receipt == receipts.read("rg")


def test_changed_link_target_is_broken_and_not_removable_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP SC3 (checker W7): install, relink, read BROKEN, refuse removal."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    rg = _rg_archive()
    outcome = _install(rg, tmp_path, monkeypatch)
    assert outcome.status == InstallStatus.INSTALLED
    link = bin_dir / "rg"
    assert receipts.read("rg") is not None
    other = tmp_path / ".local" / "opt" / "rg" / "other"
    other.write_bytes(b"#!/bin/sh\n")
    link.unlink()
    link.symlink_to(other)
    state = _settled(_receipt_service(tmp_path, bin_dir), rg)
    assert state.health is Health.BROKEN
    assert state.reasons[0] == _CHANGED
    assert state.removable.removable == ()
    removed, refused = uninstall.remove_proven([rg], [link], bin_dir)
    assert removed == ()
    assert refused == (f"changed since the preview; not removed: {link}",)
    assert link.is_symlink()
    assert receipts.receipt_path("rg").exists()


# -- 19-14 Task 2: a present raw binary with no receipt is adopted against the
# cached release digest, offline and race-safe (D-09, review H9, M10). --

_ADOPTED = "adopted: the file matches the release checksum"
_YQ_SHA = hashlib.sha256(_YQ_BYTES).hexdigest()


def _cache_digests(
    tmp_path: Path, tool_id: str, digests: Mapping[str, str], *, latest: str = "v4.54.1"
) -> None:
    """A fresh cache entry, so the pass never fetches (checked_at is now)."""
    entry = VersionCacheEntry(
        latest_version=latest, checked_at=_STATE_NOW.isoformat(), digests=dict(digests)
    )
    save_version_cache(tmp_path / "versions.json", {tool_id: entry})


def _offline(calls: list[str]) -> Callable[[str], str]:
    def resolve_tag(repo: str) -> str:
        calls.append(repo)
        raise AssertionError(f"network call for {repo}")

    return resolve_tag


def _adoption_service(
    tmp_path: Path, bin_dir: Path, digests: Mapping[str, str]
) -> tuple[VersionRefreshService, Path]:
    placed = bin_dir / "yq"
    placed.write_bytes(_YQ_BYTES)
    _cache_digests(tmp_path, "yq", digests)
    return _receipt_service(tmp_path, bin_dir, resolve_tag=_offline([])), placed


def test_pass_adopts_a_raw_binary_by_cached_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, placed = _adoption_service(tmp_path, bin_dir, {"yq_linux_amd64": _YQ_SHA})
    state = _settled(service, _yq())
    written = receipts.read("yq")
    assert written is not None
    assert written.artifacts == (receipts.fingerprint(placed, "file"),)
    assert state.receipt == written
    assert _ADOPTED in state.reasons
    assert state.removable.removable == (placed,)


def test_adoption_makes_no_network_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    (bin_dir / "yq").write_bytes(_YQ_BYTES)
    _cache_digests(tmp_path, "yq", {"yq_linux_amd64": _YQ_SHA})
    calls: list[str] = []
    state = _settled(_receipt_service(tmp_path, bin_dir, resolve_tag=_offline(calls)), _yq())
    assert calls == []
    assert _ADOPTED in state.reasons
    assert receipts.read("yq") is not None


def test_adoption_mismatch_is_hashed_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, placed = _adoption_service(tmp_path, bin_dir, {"yq_linux_amd64": "0" * 64})
    real = receipts.sha256_file
    hashed: list[Path] = []

    def counting(path: Path) -> str:
        hashed.append(path)
        return real(path)

    monkeypatch.setattr(receipts, "sha256_file", counting)
    first = _settled(service, _yq())
    second = _settled(service, _yq())
    assert hashed == [placed]
    assert not receipts.receipt_path("yq").exists()
    assert _ADOPTED not in first.reasons
    assert _ADOPTED not in second.reasons


def test_adoption_memo_is_keyed_by_the_expected_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, _placed = _adoption_service(tmp_path, bin_dir, {"yq_linux_amd64": "0" * 64})
    assert _ADOPTED not in _settled(service, _yq()).reasons
    assert not receipts.receipt_path("yq").exists()
    _cache_digests(tmp_path, "yq", {"yq_linux_amd64": _YQ_SHA})
    assert _ADOPTED in _settled(service, _yq()).reasons
    assert receipts.read("yq") is not None


def test_adoption_binds_the_digest_to_the_adopted_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, placed = _adoption_service(tmp_path, bin_dir, {"yq_linux_amd64": _YQ_SHA})
    real = receipts.fingerprint
    calls: list[Path] = []

    def replaced_after_the_first(
        path: Path, kind: Literal["dir", "link", "file"]
    ) -> receipts.ReceiptArtifact | None:
        found = real(path, kind)
        calls.append(path)
        if len(calls) == 1:
            st = path.stat()
            path.write_bytes(b"X" * st.st_size)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
        return found

    monkeypatch.setattr(receipts, "fingerprint", replaced_after_the_first)
    state = _settled(service, _yq())
    assert calls == [placed, placed]
    assert not receipts.receipt_path("yq").exists()
    assert _ADOPTED not in state.reasons


def test_no_digest_no_adoption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, _placed = _adoption_service(tmp_path, bin_dir, {})
    state = _settled(service, _yq())
    assert not receipts.receipt_path("yq").exists()
    assert _ADOPTED not in state.reasons


@pytest.mark.parametrize("shape", ["archive", "raw-tarball"])
def test_archive_and_non_raw_methods_are_never_digest_adopted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    if shape == "archive":
        tool, asset, latest = _rg_archive(), _RG_ASSET, "14.1.0"
    else:
        method = Method(
            kind="tarball", params={"url": "https://x.test/yq.tar.gz", "member": "yq", "raw": True}
        )
        tool = Tool(id="yq", name="yq", category="data", cmd="yq", methods=(method,), tier="user")
        asset, latest = "yq.tar.gz", "v4.54.1"
    placed = bin_dir / tool.cmd
    placed.write_bytes(_YQ_BYTES)
    _cache_digests(tmp_path, tool.id, {asset: _YQ_SHA}, latest=latest)
    state = _settled(_receipt_service(tmp_path, bin_dir, resolve_tag=_offline([])), tool)
    assert not receipts.receipt_path(tool.id).exists()
    assert _ADOPTED not in state.reasons


# -- 19-14 Task 3: an installer-owned tool with no proof says how to get one. --

_UNPROVEN = "not proven: reinstall with r to adopt"


def test_unproven_installer_tool_gets_the_reinstall_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    (bin_dir / "yq").write_bytes(_YQ_BYTES)
    state = _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert state.ownership.owner == "installer"
    assert state.removable.removable == ()
    assert _UNPROVEN in state.reasons
    assert state.reasons.count(_UNPROVEN) == 1


def test_layout_proven_archive_tool_has_no_unproven_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    real = tmp_path / ".local" / "opt" / "rg" / "rg-x" / "rg"
    real.parent.mkdir(parents=True)
    real.write_bytes(b"#!/bin/sh\n")
    (bin_dir / "rg").symlink_to(real)
    state = _settled(_receipt_service(tmp_path, bin_dir), _rg_archive())
    assert state.ownership.owner == "installer"
    assert state.receipt is None
    assert state.removable.removable == (bin_dir / "rg", tmp_path / ".local" / "opt" / "rg")
    assert _UNPROVEN not in state.reasons


@pytest.mark.parametrize("owner", ["brew", "uv", "dnf"])
def test_manager_owned_tool_has_no_unproven_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner: Owner
) -> None:
    """The same unproven yq file, claimed by a manager: the manager owns proof."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    (bin_dir / "yq").write_bytes(_YQ_BYTES)
    owned = _owned(_yq(), owner, package="yq")

    def claimed(_tool: Tool, **_kwargs: object) -> ManagerOwnership:
        return owned

    monkeypatch.setattr(version_status, "resolve_ownership", claimed)
    state = _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert state.ownership.owner == owner
    assert state.present
    assert _UNPROVEN not in state.reasons


def test_adopted_tool_has_no_unproven_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, _placed = _adoption_service(tmp_path, bin_dir, {"yq_linux_amd64": _YQ_SHA})
    state = _settled(service, _yq())
    assert _ADOPTED in state.reasons
    assert _UNPROVEN not in state.reasons


def _read_only_write(_receipt: receipts.Receipt) -> None:
    raise OSError("read-only")


@pytest.mark.parametrize("tool_id", ["rg", "yq"])
def test_failed_rewrite_leaves_an_archive_layout_proven_and_a_raw_binary_unproven(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool_id: str
) -> None:
    """Review C2-M2: after 19-09 removed the receipt, only the layout proves."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    tool = _rg_archive() if tool_id == "rg" else _yq()
    first = _install(tool, tmp_path, monkeypatch)
    assert first.status == InstallStatus.INSTALLED
    assert receipts.read(tool_id) is not None
    monkeypatch.setattr(receipts, "write", _read_only_write)
    again = _install(tool, tmp_path, monkeypatch, payload=_YQ_BYTES + b"# v2\n", repair=True)
    assert again.status == InstallStatus.INSTALLED
    assert again.postinstall_warning is not None
    assert "the previous receipt was removed" in again.postinstall_warning
    assert not receipts.receipt_path(tool_id).exists()
    state = _settled(_receipt_service(tmp_path, bin_dir), tool)
    assert state.receipt is None
    if tool_id == "rg":
        assert _UNPROVEN not in state.reasons
        assert state.removable.removable
    else:
        assert _UNPROVEN in state.reasons
        assert state.removable.removable == ()


# -- 19-16 Task 1: terminal drift from a dry-run sync (D-16, L-19-10, review M11) --


def _terminal_tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="terminal",
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        tier="user",
    )


def _terminals() -> list[Tool]:
    return [_terminal_tool(tool_id) for tool_id in ("kitty", "wezterm", "zsh", "jqx")]


def _drift_service(
    tmp_path: Path,
    terminal_drift: Callable[[Platform], TerminalShellResult] | None,
    *,
    present: frozenset[str] = frozenset({"kitty", "wezterm", "zsh", "jqx"}),
) -> VersionRefreshService:
    managed = tmp_path / "managed"
    return VersionRefreshService(
        platform=_LINUX,
        cache_path=tmp_path / "versions.json",
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=lambda _argv: "1.0.0",
        now=lambda: _STATE_NOW,
        managed_bin_dir=managed,
        which=lambda _cmd: None,
        artifacts_for=lambda _tool: [],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        query=lambda *_args, **_kwargs: "",
        present=lambda tool: tool.id in present,
        terminal_drift=terminal_drift,
    )


def _settled_states(service: VersionRefreshService, tools: list[Tool]) -> dict[str, ToolState]:
    service.refresh(tools)
    states: dict[str, ToolState] = {}
    for tool in tools:
        state = service.state_of(tool.id)
        assert state is not None
        states[tool.id] = state
    return states


def _drifted(*names: str) -> Callable[[Platform], TerminalShellResult]:
    return lambda _platform: TerminalShellResult(configured=names, drifted=names)


def test_kitty_drift_is_misconfigured(tmp_path: Path) -> None:
    states = _settled_states(_drift_service(tmp_path, _drifted("kitty")), _terminals())
    kitty = states["kitty"]
    assert kitty.health is Health.MISCONFIGURED
    assert kitty.reasons[0] == "Kitty does not start zsh"
    assert kitty.unconfigured == (
        ConfigStep(text="point Kitty at zsh", kind="terminal_sync", harness=None),
    )
    for other in ("wezterm", "zsh", "jqx"):
        assert states[other].health is Health.OK
        assert states[other].unconfigured == ()


def test_wezterm_drift_lands_on_its_own_row(tmp_path: Path) -> None:
    states = _settled_states(_drift_service(tmp_path, _drifted("wezterm")), _terminals())
    assert states["wezterm"].health is Health.MISCONFIGURED
    assert states["wezterm"].reasons[0] == "WezTerm does not start zsh"
    assert states["wezterm"].unconfigured == (ConfigStep("point WezTerm at zsh", "terminal_sync"),)
    assert states["kitty"].health is Health.OK


def test_konsole_drift_lands_on_zsh(tmp_path: Path) -> None:
    states = _settled_states(_drift_service(tmp_path, _drifted("konsole")), _terminals())
    zsh = states["zsh"]
    assert zsh.health is Health.MISCONFIGURED
    assert zsh.reasons[0] == "Konsole does not start zsh"
    assert zsh.unconfigured == (ConfigStep("point Konsole at zsh", "terminal_sync"),)
    for other in ("kitty", "wezterm", "jqx"):
        assert states[other].health is Health.OK
        assert not any("zsh" in reason for reason in states[other].reasons)


def test_no_terminals_no_drift(tmp_path: Path) -> None:
    states = _settled_states(_drift_service(tmp_path, _drifted()), _terminals())
    for state in states.values():
        assert state.health is Health.OK
        assert not any("does not start zsh" in reason for reason in state.reasons)
        assert state.unconfigured == ()


def test_terminal_drift_seam_runs_once_per_pass(tmp_path: Path) -> None:
    seen: list[Platform] = []

    def drift(live: Platform) -> TerminalShellResult:
        seen.append(live)
        return TerminalShellResult()

    service = _drift_service(tmp_path, drift)
    service.refresh(_terminals())
    assert seen == [service.platform]
    service.refresh(_terminals()[:1])
    assert len(seen) == 2


def test_terminal_drift_failure_is_a_not_checked_note(tmp_path: Path) -> None:
    def drift(_live: Platform) -> TerminalShellResult:
        raise OSError("boom")

    present = frozenset({"kitty", "zsh", "jqx"})
    states = _settled_states(_drift_service(tmp_path, drift, present=present), _terminals())
    note = "terminal shell not checked: boom"
    for tool_id in ("kitty", "zsh"):
        assert states[tool_id].health is Health.OK
        assert note in states[tool_id].reasons
        assert states[tool_id].unconfigured == ()
    assert states["wezterm"].present is False
    assert note not in states["wezterm"].reasons
    assert note not in states["jqx"].reasons


def _warned(*warnings: str) -> Callable[[Platform], TerminalShellResult]:
    return lambda _platform: TerminalShellResult(warnings=warnings)


def test_terminal_warning_is_a_not_checked_note(tmp_path: Path) -> None:
    """A warning the sync cannot assess lands on its row as a note (G11).

    No configuration step: the synchronizer cannot handle that shape.
    """
    states = _settled_states(
        _drift_service(tmp_path, _warned("wezterm: unsupported return shape")), _terminals()
    )
    note = "terminal shell not checked: wezterm: unsupported return shape"
    wezterm = states["wezterm"]
    assert wezterm.health is Health.OK
    assert note in wezterm.reasons
    assert wezterm.unconfigured == ()
    for other in ("kitty", "zsh", "jqx"):
        assert note not in states[other].reasons


def test_konsole_warning_lands_on_zsh(tmp_path: Path) -> None:
    """Konsole has no catalog row; its warning rides the zsh row (G11, L-19-10)."""
    warning = "konsole: installer profile path is already user-owned"
    states = _settled_states(_drift_service(tmp_path, _warned(warning)), _terminals())
    note = f"terminal shell not checked: {warning}"
    assert note in states["zsh"].reasons
    assert states["zsh"].unconfigured == ()
    for other in ("kitty", "wezterm", "jqx"):
        assert note not in states[other].reasons


def test_unknown_terminal_warning_lands_on_every_terminal_row(tmp_path: Path) -> None:
    """A warning naming no known terminal is a note on every terminal row (G11)."""
    states = _settled_states(
        _drift_service(tmp_path, _warned("sync: unexpected output")), _terminals()
    )
    note = "terminal shell not checked: sync: unexpected output"
    for tool_id in ("kitty", "wezterm", "zsh"):
        assert note in states[tool_id].reasons
        assert states[tool_id].unconfigured == ()
    assert note not in states["jqx"].reasons


def test_no_terminal_drift_seam_adds_nothing(tmp_path: Path) -> None:
    states = _settled_states(_drift_service(tmp_path, None), _terminals())
    assert all(state.health is Health.OK for state in states.values())


# -- 19-16 Task 2: incomplete pnpm co-install groups (D-19, review H10/M11, checker I6) --

_MMDC_PKG = "@mermaid-js/mermaid-cli"
_GROUP_REASON = "pnpm group incomplete: missing puppeteer"
_GROUP_STEP = ConfigStep(text="install puppeteer with pnpm", kind="pnpm_group_install", argv=())
_GROUP_UNREADABLE = "pnpm group not checked: the pnpm inventory is unreadable"


def _node_pkg_tool(tool_id: str, npm_pkg: str, *co_install: str) -> Tool:
    params: dict[str, object] = {"npm_pkg": npm_pkg}
    if co_install:
        params["co_install"] = list(co_install)
        params["allow_build"] = list(co_install)
    return Tool(
        id=tool_id,
        name=tool_id,
        category="diagram",
        cmd=tool_id,
        methods=(Method(kind="node", params=params),),
    )


def _mmdc_group(*co_install: str) -> Tool:
    return _node_pkg_tool("mmdc", _MMDC_PKG, *(co_install or ("puppeteer",)))


def _group_service(
    tmp_path: Path,
    pnpm_globals: frozenset[str] | None,
    *,
    present: frozenset[str] = frozenset({"mmdc", "puppeteer", "prettier"}),
) -> VersionRefreshService:
    def inventory(**_kwargs: object) -> ManagerInventory:
        return ManagerInventory(
            brew_formulae={},
            brew_casks={},
            pnpm_globals=pnpm_globals,
            uv_tools={},
            brew_prefix=None,
        )

    return VersionRefreshService(
        platform=_LINUX,
        cache_path=tmp_path / "versions.json",
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=lambda _argv: "1.0.0",
        now=lambda: _STATE_NOW,
        managed_bin_dir=tmp_path / "managed",
        which=lambda _cmd: None,
        artifacts_for=lambda _tool: [],
        read_inventory_fn=inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        query=lambda *_args, **_kwargs: "",
        present=lambda tool: tool.id in present,
    )


def test_incomplete_pnpm_group_is_misconfigured(tmp_path: Path) -> None:
    tools = [_mmdc_group(), _node_pkg_tool("prettier", "prettier")]
    states = _settled_states(_group_service(tmp_path, frozenset({_MMDC_PKG})), tools)
    mmdc = states["mmdc"]
    assert mmdc.health is Health.MISCONFIGURED
    assert mmdc.reasons[0] == _GROUP_REASON
    assert mmdc.unconfigured == (_GROUP_STEP,)
    assert states["prettier"].unconfigured == ()
    # Review H10: no step in the pass carries a standalone pnpm argv.
    assert all(step.argv == () for state in states.values() for step in state.unconfigured)


def test_group_step_repair_runs_the_grouped_node_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mmdc = next(tool for tool in load_tools(REGISTRY) if tool.id == "mmdc")
    method = next(m for m in mmdc.methods if m.kind == "node")
    npm_pkg = method.params["npm_pkg"]
    assert isinstance(npm_pkg, str)
    states = _settled_states(_group_service(tmp_path, frozenset({npm_pkg})), [mmdc])
    assert _GROUP_STEP in states["mmdc"].unconfigured
    co_install = cast(list[str], method.params["co_install"])
    allow_build = cast(list[str], method.params["allow_build"])
    versions = cast(dict[str, str], method.params.get("versions", {}))
    smoke = method.params["smoke"]
    assert isinstance(smoke, str)
    monkeypatch.setattr(executors, "real_pnpm", lambda: "/fake/pnpm")

    def floor_met(_binary: str, _argv: list[str], _minimum: str) -> None:
        return None

    monkeypatch.setattr(executors, "_require_minimum", floor_met)
    smoked: list[str] = []
    monkeypatch.setitem(executors.SMOKE_CHECKS, smoke, lambda: smoked.append(smoke))
    calls: list[list[str]] = []
    # The step's contract (review H10): Phase 20 runs the declaring tool's node method.
    executors.execute(method, calls.append)
    members = list(dict.fromkeys([npm_pkg, *co_install]))
    group = ",".join(f"{name}@{versions[name]}" if name in versions else name for name in members)
    allowances = [f"--allow-build={name}" for name in allow_build]
    assert calls == [["/fake/pnpm", "add", "-g", *allowances, group]]
    assert smoked == [smoke]


def test_complete_group_is_quiet(tmp_path: Path) -> None:
    service = _group_service(tmp_path, frozenset({_MMDC_PKG, "puppeteer"}))
    mmdc = _settled_states(service, [_mmdc_group()])["mmdc"]
    assert mmdc.health is Health.OK
    assert mmdc.unconfigured == ()
    assert not any("pnpm group" in reason for reason in mmdc.reasons)


def test_unreadable_pnpm_inventory_is_a_not_checked_note(tmp_path: Path) -> None:
    tools = [_mmdc_group(), _node_pkg_tool("prettier", "prettier")]
    states = _settled_states(_group_service(tmp_path, None), tools)
    assert states["mmdc"].health is Health.OK
    assert _GROUP_UNREADABLE in states["mmdc"].reasons
    assert states["mmdc"].unconfigured == ()
    assert _GROUP_UNREADABLE not in states["prettier"].reasons
    absent = _group_service(tmp_path / "absent", None, present=frozenset())
    assert _GROUP_UNREADABLE not in _settled_states(absent, tools)["mmdc"].reasons


def test_group_check_makes_no_extra_query(tmp_path: Path) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    path = tmp_path / "versions.json"
    stale_minutes = int(MANAGER_STALE_AFTER.total_seconds() / 60) + 1
    snapshot = _fresh_manager_snapshot(minutes_ago=stale_minutes)
    save_version_cache(path, {}, managers=encode_manager_snapshot(snapshot))
    query, calls = _counting_query()
    pnpm_calls = {"n": 0}

    def pnpm_packages() -> tuple[str, ...] | None:
        pnpm_calls["n"] += 1
        return (_MMDC_PKG,)

    service = VersionRefreshService(
        platform=_platform(),
        cache_path=path,
        resolve_tag=lambda repo: "v0",
        probe_output=lambda argv: "14.1.0",
        now=lambda: now,
        managed_bin_dir=_MANAGED,
        which=_which_for_fixture,
        artifacts_for=lambda _tool: [],
        query=query,
        pnpm_packages=pnpm_packages,
        resolve_pnpm=lambda: "/opt/homebrew/bin/pnpm",
        present=lambda _tool: True,
    )
    service.refresh([_brew_tool(), _cask_tool(), _mmdc_group(), _uv_tool()])
    assert len(calls) == 7
    assert pnpm_calls["n"] == 1
    mmdc = service.state_of("mmdc")
    assert mmdc is not None
    assert mmdc.reasons[0] == _GROUP_REASON


def test_group_step_rejects_unsafe_names(tmp_path: Path) -> None:
    tool = _mmdc_group("evil;rm -rf")
    mmdc = _settled_states(_group_service(tmp_path, frozenset({_MMDC_PKG})), [tool])["mmdc"]
    assert mmdc.health is Health.MISCONFIGURED
    assert mmdc.reasons[0] == "pnpm group incomplete: missing evil;rm -rf"
    assert mmdc.unconfigured == ()


def test_group_maps_to_the_declaring_tool(tmp_path: Path) -> None:
    tools = [_mmdc_group(), _node_pkg_tool("puppeteer", "puppeteer")]
    lone = _settled_states(_group_service(tmp_path / "lone", frozenset({"puppeteer"})), tools)
    for state in lone.values():
        assert not any("pnpm group" in reason for reason in state.reasons)
        assert state.unconfigured == ()
    split = _settled_states(_group_service(tmp_path / "split", frozenset({_MMDC_PKG})), tools)
    assert split["mmdc"].reasons[0] == _GROUP_REASON
    assert split["mmdc"].unconfigured == (_GROUP_STEP,)
    assert not any("pnpm group" in reason for reason in split["puppeteer"].reasons)
    assert split["puppeteer"].unconfigured == ()


# -- 19-16 Task 3: skill partial/duplicate/disabled and project-pack evidence
# (D-17, D-18, D-21, checker B1/W1/W5, review M11/C2-M3) --

_SP_ID = "superpowers@claude-plugins-official"
_SP_MARKET = "superpowers@superpowers-marketplace"
_FOUR_REASONS = (
    f"disabled: {_SP_ID} in user scope (6.4.1)",
    f"duplicate: {_SP_ID} in project scope (6.2.0)",
    f"duplicate: {_SP_MARKET} in user scope (6.2.0)",
    f"duplicate: {_SP_MARKET} in project scope (6.2.0)",
)
_SKILL_NOT_CHECKED = "skill configuration not checked: "
_LEFTOVER = "installed globally; this pack is project-local"


def _listing(*entries: tuple[str, str, bool, str]) -> str:
    return json.dumps(
        [
            {"id": plugin_id, "scope": scope, "enabled": enabled, "version": version}
            for plugin_id, scope, enabled, version in entries
        ]
    )


def _four_install_listing(home: Path) -> str:
    """The 19-07 four-install host: a disabled canonical user copy plus three copies."""
    official, market = home / "repo-official", home / "repo-market"
    official.mkdir(parents=True)
    market.mkdir()
    plugins = {
        _SP_ID: [{"scope": "project", "projectPath": str(official)}],
        _SP_MARKET: [{"scope": "project", "projectPath": str(market)}],
    }
    target = home / ".claude" / "plugins"
    target.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": 2, "plugins": plugins})
    (target / "installed_plugins.json").write_text(payload, encoding="utf-8")
    return _listing(
        (_SP_ID, "user", False, "6.4.1"),
        (_SP_ID, "project", True, "6.2.0"),
        (_SP_MARKET, "user", True, "6.2.0"),
        (_SP_MARKET, "project", True, "6.2.0"),
    )


def _superpowers(*, codex: bool = False) -> Tool:
    probes = (SkillStatusProbe("claude", "plugin-cli", _SP_ID),)
    if codex:
        probes += (SkillStatusProbe("codex", "plugin-cli", "superpowers"),)
    return _skill_pack("superpowers", probes)


def _probe_for(claude: str, codex: str = "") -> Callable[[list[str]], str]:
    def probe(argv: list[str]) -> str:
        return claude if argv[0] == "claude" else codex

    return probe


def _pack_service(
    home: Path,
    probe: Callable[[list[str]], str] | None = None,
    *,
    harnesses: frozenset[str] = frozenset(),
    which: Callable[[str], str | None] | None = None,
) -> VersionRefreshService:
    def on_path(cmd: str) -> str | None:
        return f"/usr/bin/{cmd}" if cmd in harnesses else None

    return VersionRefreshService(
        platform=_LINUX,
        cache_path=home.parent / f"{home.name}-versions.json",
        resolve_tag=lambda _repo: "1.0.0",
        probe_output=lambda _argv: "1.0.0",
        now=lambda: _STATE_NOW,
        managed_bin_dir=home.parent / f"{home.name}-managed",
        skill_probe=probe,
        skill_home=home,
        which=which if which is not None else on_path,
        artifacts_for=lambda _tool: [],
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        query=lambda *_args, **_kwargs: "",
    )


def _probed_state(service: VersionRefreshService, pack: Tool) -> ToolState:
    """The pack's state after a pass and the once-per-launch probe's rebuild."""
    service.refresh([pack])
    service.refresh_skills([pack])
    rebuilt = service.state_of(pack.id)
    assert rebuilt is not None
    # Carry-forward from 19-08: the next pass keeps what the rebuild attached.
    service.refresh([pack])
    again = service.state_of(pack.id)
    assert again is not None
    assert (again.health, again.reasons, again.unconfigured) == (
        rebuilt.health,
        rebuilt.reasons,
        rebuilt.unconfigured,
    )
    return rebuilt


def _opengsd() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "opengsd")


def _gsd_repo(home: Path, name: str = "proj") -> Path:
    repo = home / "code" / name
    (repo / ".planning").mkdir(parents=True)
    (repo / ".planning" / "config.json").write_text("{}", encoding="utf-8")
    return repo


def test_partial_skill_pack_is_misconfigured(tmp_path: Path) -> None:
    probe = _probe_for(_listing((_SP_ID, "user", True, "6.4.1")))
    service = _pack_service(tmp_path / "home", probe, harnesses=frozenset({"claude", "codex"}))
    state = _probed_state(service, _superpowers(codex=True))
    assert state.skill_hosts is not None
    assert state.skill_hosts.hosts == {"claude": "present", "codex": "absent"}
    assert state.health is Health.MISCONFIGURED
    assert state.reasons[0] == "partial: missing on Codex"
    assert state.unconfigured == (
        ConfigStep("install superpowers for Codex", "skill_install", "codex"),
    )


def test_absent_harness_gives_no_partial(tmp_path: Path) -> None:
    probe = _probe_for(_listing((_SP_ID, "user", True, "6.4.1")))
    service = _pack_service(tmp_path / "home", probe, harnesses=frozenset({"claude"}))
    state = _probed_state(service, _superpowers(codex=True))
    assert state.health is Health.OK
    assert state.unconfigured == ()
    assert not any(reason.startswith("partial:") for reason in state.reasons)


def test_claude_duplicates_reach_the_state(tmp_path: Path) -> None:
    home = tmp_path / "home"
    probe = _probe_for(_four_install_listing(home))
    pack = _superpowers()
    service = _pack_service(home, probe, harnesses=frozenset({"claude"}))
    state = _probed_state(service, pack)
    expected = inspect_skill_reports([pack], probe, home)[pack.id]
    assert state.health is Health.MISSING
    assert state.reasons[:4] == _FOUR_REASONS
    assert state.unconfigured == expected.steps
    assert state.unconfigured[0].kind == "plugin_enable"
    assert len(state.unconfigured) == 5


def test_claude_duplicates_on_a_present_pack_are_misconfigured(tmp_path: Path) -> None:
    home = tmp_path / "home"
    probe = _probe_for(_four_install_listing(home), "superpowers@openai-curated  installed\n")
    pack = _superpowers(codex=True)
    service = _pack_service(home, probe, harnesses=frozenset({"claude", "codex"}))
    state = _probed_state(service, pack)
    expected = inspect_skill_reports([pack], probe, home)[pack.id]
    assert state.skill_hosts is not None
    assert state.skill_hosts.hosts == {"claude": "absent", "codex": "present"}
    assert state.health is Health.MISCONFIGURED
    assert state.reasons[:4] == _FOUR_REASONS
    # Claude's D-18 fix already reinstates it there: no second, partial install step.
    assert state.unconfigured == expected.steps
    assert state.unconfigured[0].kind == "plugin_enable"


def test_present_harnesses_runs_once_per_pass(tmp_path: Path) -> None:
    calls: list[str] = []

    def which(cmd: str) -> str | None:
        calls.append(cmd)
        return None

    service = _pack_service(tmp_path / "home", which=which)
    service.refresh([_superpowers(), _skill_pack("ponytail", ()), _opengsd()])
    commands = {command for commands, _markers in HARNESS_PRESENCE.values() for command in commands}
    assert calls.count("claude") == 1
    assert all(calls.count(command) <= 1 for command in commands)


def _claude_gsd_install(repo: Path) -> None:
    """A real Claude GSD install in one repo: version plus a command file."""
    (repo / ".claude" / "gsd-core").mkdir(parents=True)
    (repo / ".claude" / "gsd-core" / "VERSION").write_text("1.16.0\n", encoding="utf-8")
    (repo / ".claude" / "commands").mkdir()
    (repo / ".claude" / "commands" / "gsd-plan-phase.md").write_text("x", encoding="utf-8")


def test_skill_rebuild_never_rereads_project_facts(tmp_path: Path) -> None:
    """The skill worker rebuilds with the pass's scan, never its own (G9).

    A later home change is invisible to `refresh_skills`. The next full pass
    owns those facts and reports the leftover.
    """
    home = tmp_path / "home"
    repo = _gsd_repo(home)
    _claude_gsd_install(repo)
    service = _pack_service(
        home,
        _probe_for(_listing((_SP_ID, "user", True, "6.4.1"))),
        harnesses=frozenset({"claude"}),
    )
    packs = [_opengsd(), _superpowers()]
    service.refresh(packs)
    published = service.state_of("opengsd")
    assert published is not None
    assert published.reasons[0].startswith("installed in 1 repo")

    (repo / ".claude" / "commands" / "gsd-plan-phase.md").unlink()
    (home / ".claude" / "gsd-core").mkdir(parents=True)
    service.refresh_skills(packs)
    rebuilt = service.state_of("opengsd")
    assert rebuilt is not None
    assert rebuilt.reasons == published.reasons
    assert _LEFTOVER not in rebuilt.reasons
    skills = service.state_of("superpowers")
    assert skills is not None
    assert skills.health is Health.OK

    service.refresh(packs)
    later = service.state_of("opengsd")
    assert later is not None
    assert later.reasons[0] == _LEFTOVER


def test_skill_rebuild_after_a_newer_pass_keeps_its_facts(tmp_path: Path) -> None:
    """A probe still in flight never overwrites a newer pass's facts (G9)."""
    home = tmp_path / "home"
    repo = _gsd_repo(home)
    _claude_gsd_install(repo)
    gate = threading.Event()

    def probe(argv: list[str]) -> str:
        gate.wait(timeout=5)
        return _listing((_SP_ID, "user", True, "6.4.1")) if argv[0] == "claude" else ""

    service = _pack_service(home, probe, harnesses=frozenset({"claude"}))
    packs = [_opengsd(), _superpowers()]
    service.refresh(packs)
    worker = threading.Thread(target=service.refresh_skills, args=(packs,))
    worker.start()
    (repo / ".claude" / "commands" / "gsd-plan-phase.md").unlink()
    (home / ".claude" / "gsd-core").mkdir(parents=True)
    service.refresh(packs)
    newer = service.state_of("opengsd")
    assert newer is not None
    assert newer.reasons[0] == _LEFTOVER
    gate.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    kept = service.state_of("opengsd")
    assert kept is not None
    assert kept.reasons == newer.reasons
    assert kept.seq == newer.seq
    skills = service.state_of("superpowers")
    assert skills is not None
    assert skills.health is Health.OK


def test_project_pack_present_in_repos(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = _gsd_repo(home)
    (repo / ".claude" / "gsd-core").mkdir(parents=True)
    (repo / ".claude" / "gsd-core" / "VERSION").write_text("1.16.0\n", encoding="utf-8")
    (repo / ".claude" / "commands").mkdir()
    (repo / ".claude" / "commands" / "gsd-plan.md").write_text("x", encoding="utf-8")
    service = _pack_service(home, harnesses=frozenset({"claude"}))
    state = _settled_states(service, [_opengsd()])["opengsd"]
    assert state.health is Health.OK
    assert "installed in 1 repo" in state.reasons
    assert state.unconfigured == ()


def test_project_pack_global_leftover_is_misconfigured(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude" / "gsd-core").mkdir(parents=True)
    state = _settled_states(_pack_service(home), [_opengsd()])["opengsd"]
    assert state.health is Health.MISCONFIGURED
    assert state.reasons[0] == _LEFTOVER
    assert [step.kind for step in state.unconfigured] == ["project_pack_global_uninstall"]
    assert state.unconfigured[0].harness == "claude"


def test_project_pack_empty_dirs_is_not_present(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = _gsd_repo(home)
    (repo / ".claude" / "gsd-core").mkdir(parents=True)
    (repo / ".claude" / "gsd-core" / "VERSION").write_text("1.16.0\n", encoding="utf-8")
    (repo / ".claude" / "skills").mkdir()
    service = _pack_service(home, harnesses=frozenset({"claude"}))
    state = _settled_states(service, [_opengsd()])["opengsd"]
    assert state.health is Health.MISSING
    assert "Claude Code install in proj is empty" in state.reasons
    assert not any(reason.startswith("installed in") for reason in state.reasons)
    assert [(step.kind, step.cwd) for step in state.unconfigured] == [
        ("project_pack_install", repo)
    ]
    assert state.unconfigured[0].text == "reinstall opengsd for Claude Code in proj"


def test_project_pack_not_installed_anywhere_is_missing_with_steps(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = _gsd_repo(home)
    service = _pack_service(home, harnesses=frozenset({"claude", "opencode"}))
    state = _settled_states(service, [_opengsd()])["opengsd"]
    assert state.health is Health.MISSING
    assert "not installed in proj" in state.reasons
    assert [(step.kind, step.harness, step.cwd) for step in state.unconfigured] == [
        ("project_pack_install", "claude", repo),
        ("project_pack_install", "opencode", repo),
    ]


def test_project_pack_scan_reads_only_the_skill_home(tmp_path: Path) -> None:
    (tmp_path / "elsewhere" / ".claude" / "gsd-core").mkdir(parents=True)
    service = VersionRefreshService(
        platform=_LINUX,
        cache_path=tmp_path / "versions.json",
        which=lambda _cmd: None,
        query=lambda *_args, **_kwargs: "",
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        read_inventory_fn=_empty_inventory,
        read_outdated_fn=_empty_outdated,
    )
    clean = _settled_states(service, [_opengsd()])["opengsd"]
    assert _LEFTOVER not in clean.reasons
    assert clean.health is Health.MISSING
    (version_status.default_skill_home() / ".claude" / "gsd-core").mkdir(parents=True)
    service.invalidate(reason="test")
    leftover = _settled_states(service, [_opengsd()])["opengsd"]
    assert leftover.health is Health.MISCONFIGURED
    assert leftover.reasons[0] == _LEFTOVER


def test_seeded_skill_cache_has_hosts_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "repo"
    project.mkdir(parents=True)
    service = _pack_service(
        home,
        _probe_for(_listing((_SP_ID, "user", True, "6.4.1"), (_SP_ID, "project", True, "6.2.0"))),
        harnesses=frozenset({"claude"}),
    )
    save_version_cache(
        home.parent / f"{home.name}-versions.json",
        {},
        skills={"superpowers": {"claude": "present"}},
    )
    plugins = {_SP_ID: [{"scope": "project", "projectPath": str(project)}]}
    (home / ".claude" / "plugins").mkdir(parents=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8"
    )
    service.seed_skills_from_cache()
    pack = _superpowers()
    seeded = _settled_states(service, [pack])["superpowers"]
    # A seeded present answer never settles the pack (G8).
    assert seeded.health is Health.CHECKING
    assert _SEEDED_NOTE in seeded.reasons
    assert seeded.unconfigured == ()
    service.refresh_skills([pack])
    probed = service.state_of(pack.id)
    assert probed is not None
    assert probed.health is Health.MISCONFIGURED
    assert probed.reasons[0] == f"duplicate: {_SP_ID} in project scope (6.2.0)"
    assert [step.kind for step in probed.unconfigured] == ["plugin_uninstall"]


def _raise_boom(*_args: object) -> object:
    raise OSError("boom")


@pytest.mark.parametrize("helper", ["inspect_project_pack", "partial_harnesses"])
def test_skill_helper_failure_is_a_not_checked_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helper: str
) -> None:
    home = tmp_path / "home"
    service = _pack_service(
        home,
        _probe_for(_listing((_SP_ID, "user", True, "6.4.1"))),
        harnesses=frozenset({"claude"}),
    )
    monkeypatch.setattr(version_status, helper, _raise_boom)
    packs = [_superpowers(), _opengsd(), _skill_pack("ponytail", ())]
    service.refresh(packs)
    service.refresh_skills(packs)
    note = f"{_SKILL_NOT_CHECKED}boom"
    affected = "opengsd" if helper == "inspect_project_pack" else "superpowers"
    for pack in packs:
        state = service.state_of(pack.id)
        assert state is not None
        assert (note in state.reasons) is (pack.id == affected)
    superpowers = service.state_of("superpowers")
    assert superpowers is not None
    assert superpowers.health is Health.OK


def _raise_called_process_error(argv: list[str]) -> str:
    raise subprocess.CalledProcessError(1, argv)


def _unreadable_probe(answer: str) -> Callable[[list[str]], str]:
    def probe(argv: list[str]) -> str:
        return _raise_called_process_error(argv) if answer == "raises" else "not json"

    return probe


@pytest.mark.parametrize("answer", ["not-json", "raises"])
def test_inconclusive_claude_listing_is_a_not_checked_note(tmp_path: Path, answer: str) -> None:
    note = f"{_SKILL_NOT_CHECKED}no readable answer from Claude Code"
    for on_machine in (True, False):
        home = tmp_path / f"home-{on_machine}"
        if on_machine:
            _four_install_listing(home)
        harnesses = frozenset({"claude"} if on_machine else ())
        service = _pack_service(home, _unreadable_probe(answer), harnesses=harnesses)
        state = _probed_state(service, _superpowers())
        assert state.skill_hosts is not None
        assert state.skill_hosts.hosts == {"claude": "unknown"}
        assert (note in state.reasons) is on_machine
        assert not set(_FOUR_REASONS) & set(state.reasons)
        assert state.unconfigured == ()
        # A finished all-unknown probe is MISSING, never stuck CHECKING (G8).
        assert state.health is Health.MISSING


@pytest.mark.parametrize("content", ["{", '[{"hooks": {}}]', None])
def test_inconclusive_hook_config_is_a_not_checked_note(
    tmp_path: Path, content: str | None
) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    if content is not None:
        (home / ".claude" / "settings.json").write_text(content, encoding="utf-8")
    state = _settled_states(_pack_service(home), [_opengsd()])["opengsd"]
    note = f"{_SKILL_NOT_CHECKED}cannot read ~/.claude/settings.json"
    assert (note in state.reasons) is (content is not None)


def test_stale_cached_present_is_checking_not_ok(tmp_path: Path) -> None:
    """A cache-seeded `present` never settles the pack (G8).

    CHECKING plus the seeded note until the current probe answers; OK only
    after that probe lists the canonical user entry; CHECKING again once
    `invalidate` marks those answers stale.
    """
    home = tmp_path / "home"
    service = _pack_service(
        home,
        _probe_for(_listing((_SP_ID, "user", True, "6.4.1"))),
        harnesses=frozenset({"claude"}),
    )
    save_version_cache(
        home.parent / f"{home.name}-versions.json",
        {},
        skills={"superpowers": {"claude": "present"}},
    )
    service.seed_skills_from_cache()
    pack = _superpowers()
    seeded = _settled_states(service, [pack])["superpowers"]
    assert seeded.health is Health.CHECKING
    assert _SEEDED_NOTE in seeded.reasons
    assert seeded.present is False
    assert not any(reason.startswith("partial:") for reason in seeded.reasons)
    assert seeded.unconfigured == ()

    service.refresh_skills([pack])
    probed = service.state_of(pack.id)
    assert probed is not None
    assert probed.health is Health.OK

    service.invalidate(reason="test")
    stale = _settled_states(service, [pack])["superpowers"]
    assert stale.health is Health.CHECKING
    assert _SEEDED_NOTE in stale.reasons
    service.refresh_skills([pack])
    again = service.state_of(pack.id)
    assert again is not None
    assert again.health is Health.OK


def test_all_unknown_after_the_probe_is_missing_with_a_note(tmp_path: Path) -> None:
    """A finished probe that could not read a present harness is MISSING (G8).

    The note names the harness. With no harness on the machine the same probe
    is MISSING and note-less: there is nothing to have checked.
    """
    note = f"{_SKILL_NOT_CHECKED}no readable answer from Claude Code"
    pack = _superpowers()
    present = _pack_service(
        tmp_path / "present", _unreadable_probe("raises"), harnesses=frozenset({"claude"})
    )
    state = _probed_state(present, pack)
    assert state.health is Health.MISSING
    assert note in state.reasons

    absent = _pack_service(tmp_path / "absent", _unreadable_probe("raises"), harnesses=frozenset())
    empty = _probed_state(absent, pack)
    assert empty.health is Health.MISSING
    assert note not in empty.reasons


def test_mixed_absent_and_unknown_hosts_never_settle_absent(tmp_path: Path) -> None:
    """One absent host never overrides another host's unknown answer (G24).

    A stale mixed cache stays CHECKING. Once the current probe answers, the
    pack is MISSING with the unreadable harness's note, never a note-less
    MISSING and never OK. `inspect_status` answers `unknown` for the same input.
    """
    home = tmp_path / "home"
    pack = _superpowers(codex=True)

    def probe(argv: list[str]) -> str:
        if argv[0] == "claude":
            raise subprocess.CalledProcessError(1, argv)
        return ""

    service = _pack_service(home, probe, harnesses=frozenset({"claude", "codex"}))
    save_version_cache(
        home.parent / f"{home.name}-versions.json",
        {},
        skills={"superpowers": {"claude": "unknown", "codex": "absent"}},
    )
    service.seed_skills_from_cache()
    seeded = _settled_states(service, [pack])["superpowers"]
    assert seeded.health is Health.CHECKING

    service.refresh_skills([pack])
    probed = service.state_of(pack.id)
    assert probed is not None
    assert probed.health is Health.MISSING
    assert f"{_SKILL_NOT_CHECKED}no readable answer from Claude Code" in probed.reasons
    assert probed.health is not Health.OK

    outcome = inspect_status(pack, probe, home)
    assert outcome.status == "unknown"


def test_present_harnesses_failure_is_a_not_checked_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(version_status, "present_harnesses", _raise_boom)
    packs = [_superpowers(), _opengsd()]
    service = _pack_service(tmp_path / "home")
    service.refresh(packs)
    for pack in packs:
        state = service.state_of(pack.id)
        assert state is not None
        assert f"{_SKILL_NOT_CHECKED}boom" in state.reasons


# --- 19-22 Task 2: a NUL artifact path never aborts a refresh pass (G5) ------


def test_nul_receipt_path_never_aborts_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt whose artifact path embeds a NUL is the unreadable note, not a crash."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    (bin_dir / "yq").write_bytes(_YQ_BYTES)
    path = receipts.receipt_path("yq")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "v": 1,
                "tool": "yq",
                "at": "2026-10-16T00:00:00Z",
                "method": {"kind": "github_release", "key": "k"},
                "package": None,
                "artifacts": [
                    {
                        "path": "/tmp/x\u0000y",
                        "type": "file",
                        "sha256": "b" * 64,
                        "size": 3,
                        "mtime_ns": 1,
                    }
                ],
                "smoke": None,
                "hooks": {},
            }
        ),
        encoding="utf-8",
    )
    state = _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert _UNREADABLE in state.reasons


# --- 19-29 Task 2: retire an all-gone receipt; an unreadable dir is unproven --


def test_receipt_with_every_artifact_gone_is_retired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt whose file the user deleted stops pinning a dnf copy to BROKEN."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    placed = _place_yq_with_receipt(bin_dir)
    placed.unlink()
    system = tmp_path / "usr" / "bin"
    system.mkdir(parents=True)
    (system / "yq").write_bytes(b"#!/bin/sh\necho dnf yq\n")
    service = _receipt_service(
        tmp_path, bin_dir, which=lambda cmd: str(system / cmd) if cmd == "yq" else None
    )
    state = _settled(service, _yq())
    assert state.health is not Health.BROKEN
    assert _receipt_reasons(state) == []
    assert state.receipt is None
    assert receipts.receipt_exists("yq") is False


def test_partially_gone_receipt_is_unproven_not_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gone dir loses only its proof (L-19-31), never the BROKEN mark.

    The bin link stays, so the archive still reads as present and the receipt
    is not all gone, so it is not retired. The BROKEN half of partial drift is
    pinned by `test_changed_link_target_is_broken_and_not_removable_end_to_end`."""
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    outcome = _install(_rg_archive(), tmp_path, monkeypatch)
    assert outcome.status == InstallStatus.INSTALLED
    opt = tmp_path / ".local" / "opt" / "rg"
    assert opt.is_dir() and (bin_dir / "rg").is_symlink()
    shutil.rmtree(opt)
    state = _settled(_receipt_service(tmp_path, bin_dir), _rg_archive())
    assert state.health is not Health.BROKEN
    assert _CHANGED not in state.reasons
    assert _UNPROVEN in state.reasons
    assert receipts.receipt_exists("rg") is True


def test_artifactless_receipt_is_never_retired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = _scratch_home(tmp_path, monkeypatch)
    receipts.write(
        Receipt(
            tool="yq",
            at="2026-10-16T00:00:00+00:00",
            method=ReceiptMethod(kind="github_release", key="k"),
            package=None,
            artifacts=(),
            smoke=None,
            hooks={},
        )
    )
    _settled(_receipt_service(tmp_path, bin_dir), _yq())
    assert receipts.receipt_exists("yq") is True


def test_inaccessible_receipts_dir_never_aborts_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dir that cannot be searched is the unreadable note: no adoption, no crash."""
    from tests.test_receipts import deny_receipts_dir

    bin_dir = _scratch_home(tmp_path, monkeypatch)
    service, _placed = _adoption_service(tmp_path, bin_dir, {"yq_linux_amd64": _YQ_SHA})
    deny_receipts_dir(monkeypatch)
    state = _settled(service, _yq())
    assert _UNREADABLE in state.reasons
    assert _ADOPTED not in state.reasons
    assert state.receipt is None
    assert state.removable.removable == ()
