import json
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.model import (
    Method,
    SkillLifecycle,
    SkillOperation,
    SkillStatusProbe,
    SkillTarget,
    Tool,
)
from installer.ownership import (
    ManagerInventory,
    ManagerOwnership,
    Owner,
    OwnershipCandidate,
    resolve_ownership,
)
from installer.platform import Platform
from installer.resolve import unavailable_reason
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
    resolve_github_release_status,
    resolve_status,
    tool_state,
)
from installer.versions import Release, VersionError, resolve_github_tag

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
    statuses = service.refresh([_codegraph()])
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
    statuses = restarted.refresh([_codegraph()])
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
    statuses = service.refresh([_codegraph()])
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
    statuses = service.refresh(tools)
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
    calls: list[list[str]] = []

    def query(cmd: list[str], **_kwargs: object) -> str:
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
    statuses = service.refresh(tools)
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


def test_ownership_of_returns_last_pass_and_none_for_missing(tmp_path: Path) -> None:
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
    assert service.ownership_of("rg") is not None
    assert service.ownership_of("missing") is None


def test_ownership_of_returns_none_for_a_record_older_than_the_current_epoch(
    tmp_path: Path,
) -> None:
    """A single `invalidate` call makes every existing record report as
    unavailable until a refresh commits new ones -- the branch the Round-1
    review proved could never fire under the old two-map design, because
    `_ownership` was written only inside `refresh`'s commit block."""
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
    assert service.ownership_of("rg") is not None
    service.invalidate(reason="update")
    assert service.ownership_of("rg") is None
    service.refresh([_brew_tool()])
    assert service.ownership_of("rg") is not None


def test_a_raced_refresh_publishes_no_ownership_record_or_epoch(tmp_path: Path) -> None:
    """Round-3 review HIGH #1, asserted directly on the map's own contents
    (not only through `ownership_of`, so "published under an old tag" and
    "not published" cannot be confused): the raced branch --
    `self._epoch != started_epoch` -- writes NEITHER a record nor an epoch
    for any tool in the pass. Deterministic: the invalidate is triggered
    from inside the manager-inventory read this pass makes before its
    per-tool loop, never by sleeping."""
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
    assert service._ownership == {}  # pyright: ignore[reportPrivateUsage]
    assert service.ownership_of("rg") is None


def test_a_superseded_refresh_publishes_no_ownership_over_a_newer_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE OVERWRITE CASE (Round-3 review HIGH #1). Refresh A starts at
    epoch 0; `invalidate()` moves the service to epoch 1; refresh B starts
    and commits at epoch 1; refresh A then finishes and takes the raced
    branch. `ownership_of` still returns B's record -- A's obsolete answer
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

    assert service.ownership_of(tool.id) == b_ownership
    tag, record = service._ownership[tool.id]  # pyright: ignore[reportPrivateUsage]
    assert tag == service.epoch
    assert record == b_ownership


def test_the_service_holds_one_epoch_tagged_ownership_map_not_two(tmp_path: Path) -> None:
    """WR-02 (15.4-REVIEW.md): the DETERMINISTIC gate for Round-3 review
    HIGH #2's invariant -- one map of epoch-tagged records, never a plain
    ownership map beside a parallel `dict[str, int]` of epochs.

    This exists because the concurrency test below structurally CANNOT prove
    it: the rejected two-parallel-maps design was restored by the reviewer
    and passed that test, with the only thing in the whole suite noticing the
    revert being an incidental `TypeError` from a different test's
    private-attribute unpack -- a shape accident, not a semantic guard. The
    invariant is a property of the DATA STRUCTURE (one key lookup returns
    both halves of the pair or neither, which is atomic without a reader
    lock), so it is asserted as one, not left to timing."""
    now = datetime(2026, 9, 7, tzinfo=UTC)
    service = _installer_owned_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: "0.9.0",
        now=lambda: now,
    )
    service.refresh([_gh_tool("alpha")])
    ownership = service._ownership  # pyright: ignore[reportPrivateUsage]
    assert set(ownership) == {"alpha"}
    # The tag travels WITH the record: one lookup, one pair.
    for key, value in ownership.items():
        assert isinstance(value, tuple), (key, value)
        epoch, record = value
        assert isinstance(epoch, int), (key, value)
        assert isinstance(record, ManagerOwnership), (key, value)
    # ...and nothing else on the service is a second map keyed by the same
    # tool ids holding those epochs, which is exactly the rejected design.
    parallel: list[str] = []
    for name, value in cast("dict[str, object]", vars(service)).items():
        if name == "_ownership" or not isinstance(value, dict):
            continue
        other = cast("dict[object, object]", value)
        if not other or not set(ownership) <= set(other):
            continue
        if all(isinstance(v, int) for v in other.values()):
            parallel.append(name)
    assert parallel == [], parallel


def test_ownership_of_answers_fail_closed_across_commit_and_invalidate_boundaries(
    tmp_path: Path,
) -> None:
    """SEQUENCING case (Round-3 review HIGH #2). A reader samples
    `ownership_of` immediately after each commit and immediately after each
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

    observations: list[ManagerOwnership | None] = []
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
                    observations.append(service.ownership_of(tool.id))
                sampled.set()
                assert invalidated.wait(timeout=5)
                invalidated.clear()
                for _ in range(_READS_PER_PASS):
                    observations.append(service.ownership_of(tool.id))
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


def test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record(
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
    whole loop iterations, and therefore at least one whole `ownership_of`
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
    committed_at: dict[int, ManagerOwnership] = {}
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
        # iterations (so at least one whole `ownership_of` call starts and
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
                record = service.ownership_of(tool.id)
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
                    observed = service.ownership_of(tool.id)
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
        # the live /usr/bin/jq rather than some copy earlier in PATH.
        assert command[:2] in (["rpm", "-q"], ["rpm", "-qf"])
        return "jq\n"

    service = _native_owned_service(
        tmp_path / "versions.json",
        resolve_tag=lambda repo: "v1.0.0",
        probe_output=lambda argv: "1.8.1",
        now=lambda: now,
        native_probe=native_probe,
    )
    tool = _jq_tool()
    statuses = service.refresh([tool])

    ownership = service.ownership_of("jq")
    assert ownership is not None
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
    ownership = service.ownership_of("jq")
    assert ownership is not None
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
    status = service.skill_status_of("superpowers")
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
    assert service.skill_status_of("superpowers") is None
    assert service._skills_probed is False  # pyright: ignore[reportPrivateUsage]
    service.refresh_skills([pack])
    assert calls["n"] == 2
    assert service.skill_status_of("superpowers") is None


def test_skill_invalidate_marks_every_held_entry_stale(tmp_path: Path) -> None:
    def skill_probe(_argv: list[str]) -> str:
        return _CLAUDE_SUPERPOWERS_JSON

    service = _skill_service(tmp_path / "versions.json", skill_probe, tmp_path)
    service.refresh_skills([_claude_pack()])
    landed = service.skill_status_of("superpowers")
    assert landed is not None
    assert landed.stale is False
    service.invalidate(reason="x")
    held = service.skill_status_of("superpowers")
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
    held = service.skill_status_of("superpowers")
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
    statuses = service.refresh([alpha, beta])
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
        assert state.ownership == service.ownership_of(tool.id)
        assert state.version == service.statuses[tool.id]
        assert state.version == statuses[tool.id]
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
    statuses = service.statuses
    owners = {tool_id: service.ownership_of(tool_id) for tool_id in ("a", "b", "c")}
    hold.release.set()
    assert _join(run_a) is None
    seqs: set[int] = set()
    for tool_id, state in captured.items():
        assert state is not None
        assert service.state_of(tool_id) is state
        seqs.add(state.seq)
    assert len(seqs) == 1
    assert service.statuses == statuses
    assert {tool_id: service.ownership_of(tool_id) for tool_id in ("a", "b", "c")} == owners
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
    assert service.ownership_of("a") is None
    assert service.statuses == {}


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
    results: dict[str, dict[str, VersionStatus]] = {}

    def first() -> None:
        results["a"] = service.refresh([a, b])

    def second() -> None:
        results["b"] = service.refresh([b, a])

    run_a = _start(first)
    assert hold.holding.wait(timeout=10)
    run_b = _start(second)
    assert _still_running(run_b)
    assert hold.calls == 1
    hold.release.set()
    assert _join(run_a) is None
    assert _join(run_b) is None
    assert results["a"] == results["b"]
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
