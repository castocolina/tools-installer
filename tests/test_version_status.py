import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from installer.manager_versions import ManagerVersion, OutdatedReport
from installer.model import Method, Tool
from installer.ownership import ManagerInventory, ManagerOwnership, Owner, OwnershipCandidate
from installer.platform import Platform
from installer.version_cache import (
    MANAGER_RETRY_BACKOFF,
    MANAGER_STALE_AFTER,
    ManagerSnapshot,
    VersionCacheEntry,
    encode_manager_snapshot,
    load_manager_snapshot,
    load_version_cache,
    save_version_cache,
    should_fetch_managers,
)
from installer.version_status import (
    MAX_FETCHES_PER_REFRESH,
    VersionRefreshService,
    resolve_github_release_status,
    resolve_status,
)
from installer.versions import VersionError

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


def _which_for_fixture(cmd: str) -> str:
    if cmd == "mmdc":
        return str(Path.home() / "Library" / "pnpm" / "mmdc")
    if cmd == "ruff":
        return str(Path.home() / ".local" / "bin" / "ruff")
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
