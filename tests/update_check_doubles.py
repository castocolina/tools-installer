"""Fakes for the update check; no external commands are launched."""

import hashlib
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from installer import receipts, schedules
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool
from installer.notify import Notifier
from installer.ownership import ManagerInventory, ManagerOwnership
from installer.platform import Platform
from installer.run import CommandError
from installer.schedule_run import RunDeps
from installer.update import UpdateService
from installer.update_check import GitRunner, Refresher
from installer.version_cache import ManagerSnapshot, VersionCacheEntry, save_version_cache
from installer.version_status import FailureSink, ToolState, VersionRefreshService, VersionStatus
from tests.state_doubles import MACOS, pass_state


def tool_named(tool_id: str) -> Tool:
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


def _state(tool: Tool, outdated: bool | None, stale: bool = False) -> ToolState:
    return pass_state(
        tool,
        platform=MACOS,
        version=VersionStatus(tool.id, "1.0", "2.0", outdated, stale, "github"),
    )


def outdated_state(tool: Tool) -> ToolState:
    return _state(tool, True)


def current_state(tool: Tool) -> ToolState:
    return _state(tool, False)


def stale_current_state(tool: Tool) -> ToolState:
    return _state(tool, False, True)


def stale_outdated_state(tool: Tool) -> ToolState:
    return _state(tool, True, True)


def unknown_state(tool: Tool) -> ToolState:
    return _state(tool, None)


def check_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> schedules.ScheduleContext:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "co").mkdir(parents=True, exist_ok=True)
    return schedules.context_for(
        "fedora", checkout=tmp_path / "co", read_models=lambda _agent: None
    )


def inert_run_deps(
    tools: Sequence[Tool],
    context: schedules.ScheduleContext,
    *,
    notify: Notifier,
    refresh: Refresher,
    git: GitRunner,
) -> RunDeps:
    def ownership(tool: Tool) -> ManagerOwnership:
        return ManagerOwnership(
            tool_id=tool.id,
            owner="unknown",
            method=tool.methods[0],
            package=None,
            current_version=None,
            confidence="direct",
            shadowed=False,
            candidates=(),
            active_candidate=None,
            active_path=None,
            unknown_reason=None,
        )

    def no_run(cmd: list[str]) -> None:
        raise AssertionError(f"unexpected command: {cmd}")

    updates = UpdateService(
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=no_run,
        resolve_tag=lambda _repo: "v1.0.0",
        managed_packages=lambda: (),
        replay_globals=lambda _packages: (),
        reresolve_ownership=ownership,
    )
    return RunDeps(
        tools=tools,
        updates=updates,
        resolve_owner=ownership,
        probe_version=lambda _tool, _own: None,
        context=context,
        notify=notify,
        refresh=refresh,
        git=git,
    )


class FakeRefresher:
    def __init__(
        self,
        cache_path: Path,
        states: Mapping[str, ToolState],
        failures: Sequence[tuple[str, str]] = (),
        raises: Exception | None = None,
        stamped: Collection[str] | None = None,
        corrupt_cache: bytes | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        seed_cache: Mapping[str, VersionCacheEntry] | bytes | None = None,
    ) -> None:
        if isinstance(seed_cache, bytes):
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(seed_cache)
        elif seed_cache is not None:
            save_version_cache(cache_path, seed_cache)
        self.cache_path = cache_path
        self.warning: str | None = None
        self.states = dict(states)
        self.failures = failures
        self.raises = raises
        self.stamped = stamped
        self.corrupt_cache = corrupt_cache
        self.clock = clock
        self.calls: list[tuple[tuple[Tool, ...], timedelta, FailureSink | None]] = []

    def refresh(
        self, tools: Sequence[Tool], *, stale_after: timedelta, on_failure: FailureSink | None
    ) -> tuple[dict[str, ToolState], dict[str, VersionCacheEntry], ManagerSnapshot | None]:
        self.calls.append((tuple(tools), stale_after, on_failure))
        if self.raises is not None:
            raise self.raises
        if on_failure is not None:
            for tool_id, reason in self.failures:
                on_failure(tool_id, reason)
        if self.corrupt_cache is not None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_bytes(self.corrupt_cache)
        else:
            stamp = self.clock().isoformat()
            ids = self.states if self.stamped is None else self.stamped
            save_version_cache(self.cache_path, {i: VersionCacheEntry("2", stamp) for i in ids})
        entries = (
            {}
            if self.corrupt_cache is not None
            else {
                i: VersionCacheEntry("2", self.clock().isoformat())
                for i in (self.states if self.stamped is None else self.stamped)
            }
        )
        return self.states.copy(), entries, None

    def state_of(self, tool_id: str) -> ToolState | None:
        return self.states.get(tool_id)


class FakeNotifier:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason
        self.calls: list[tuple[str, str]] = []

    def __call__(self, summary: str, body: str) -> str | None:
        self.calls.append((summary, body))
        return self.reason


SHA_A = "a" * 40
SHA_B = "b" * 40


class FakeGit:
    def __init__(
        self,
        branch: str = "main",
        behind: bool = True,
        toplevel: Path | None = None,
        partial: bool = False,
    ) -> None:
        self.branch = branch
        self.behind = behind
        self.toplevel = toplevel
        self.partial = partial
        self.calls: list[list[str]] = []
        self.answers: dict[tuple[str, ...], str | CommandError] = {}

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv.copy())
        args = tuple(argv[3:])
        if args in self.answers:
            answer = self.answers[args]
            if isinstance(answer, CommandError):
                raise answer
            return answer
        if args == ("symbolic-ref", "-q", "HEAD"):
            if self.branch == "HEAD":
                raise CommandError(argv, 1)
            return "refs/heads/" + self.branch + "\n"
        if args == ("rev-parse", "--show-toplevel"):
            return str(self.toplevel if self.toplevel is not None else argv[2]) + "\n"
        if args == ("config", "--get-regexp", r"^(extensions\.partialclone|remote\..*\.promisor)$"):
            if self.partial:
                return "extensions.partialclone origin\n"
            raise CommandError(argv, 1)
        if args == ("rev-parse", "HEAD"):
            return SHA_A + "\n"
        if args == ("ls-remote", "origin", "refs/heads/main"):
            return f"{SHA_B if self.behind else SHA_A}\trefs/heads/main\n"
        if args == ("cat-file", "-e", SHA_B):
            raise CommandError(argv, 1)
        if args == ("merge-base", "--is-ancestor", SHA_B, "HEAD"):
            return ""
        raise AssertionError(f"unexpected git query: {args}")


YQ_BYTES = b"#!/bin/sh\necho yq 4.54.1\n"
YQ_SHA = hashlib.sha256(YQ_BYTES).hexdigest()


def yq_tool() -> Tool:
    return Tool(
        id="yq",
        name="yq",
        category="data",
        cmd="yq",
        tier="user",
        methods=(
            Method(
                kind="github_release",
                params={
                    "repo": "mikefarah/yq",
                    "asset": "yq_linux_{arch.deb}",
                    "member": "yq",
                    "raw": True,
                },
            ),
        ),
    )


def place_yq(home: Path) -> Path:
    placed = home / ".local/bin/yq"
    placed.parent.mkdir(parents=True, exist_ok=True)
    placed.write_bytes(YQ_BYTES)
    return placed


def place_yq_with_receipt(home: Path) -> Path:
    placed = place_yq(home)
    tool = yq_tool()
    assert receipts.record(
        tool, tool.methods[0], package=None, smoke=None, default_bin_dir=placed.parent
    )
    return placed


def real_service(
    home: Path, *, resolve_tag: Callable[[str], str], now: Callable[[], datetime], installed: str
) -> VersionRefreshService:
    bin_dir = home / ".local/bin"

    def no_npm(package: str) -> str:
        raise AssertionError(f"unexpected npm query: {package}")

    def inventory(**_kwargs: object) -> ManagerInventory:
        return ManagerInventory(
            brew_formulae={}, brew_casks={}, pnpm_globals=frozenset(), uv_tools={}, brew_prefix=None
        )

    def outdated(**_kwargs: object) -> OutdatedReport:
        return OutdatedReport(brew={}, cask={}, pnpm={}, uv={})

    return VersionRefreshService(
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        cache_path=home / ".local/state/tools-installer/versions.json",
        resolve_tag=resolve_tag,
        resolve_npm=no_npm,
        now=now,
        managed_bin_dir=bin_dir,
        home=home,
        which=lambda cmd: str(bin_dir / cmd) if (bin_dir / cmd).exists() else None,
        artifacts_for=lambda tool: [bin_dir / tool.cmd],
        read_inventory_fn=inventory,
        read_outdated_fn=outdated,
        pnpm_packages=lambda: (),
        resolve_pnpm=lambda: None,
        bun_versions=lambda: {},
        query=lambda *_args, **_kwargs: "",
        probe_output=lambda _argv: installed,
    )
