"""Fakes for the update check; no external commands are launched."""

from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from installer import schedules
from installer.model import Method, Tool
from installer.run import CommandError
from installer.version_cache import VersionCacheEntry, save_version_cache
from installer.version_status import FailureSink, ToolState, VersionStatus
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
    return schedules.context_for(
        "fedora", checkout=tmp_path / "co", read_models=lambda _agent: None
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
    ) -> None:
        self.cache_path = cache_path
        self.states = dict(states)
        self.failures = failures
        self.raises = raises
        self.stamped = stamped
        self.corrupt_cache = corrupt_cache
        self.clock = clock
        self.calls: list[tuple[tuple[Tool, ...], timedelta, FailureSink | None]] = []

    def refresh(
        self, tools: Sequence[Tool], *, stale_after: timedelta, on_failure: FailureSink | None
    ) -> None:
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
    def __init__(self, branch: str = "main", behind: bool = True) -> None:
        self.branch = branch
        self.behind = behind
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
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return self.branch + "\n"
        if args == ("rev-parse", "HEAD"):
            return SHA_A + "\n"
        if args == ("ls-remote", "origin", "refs/heads/main"):
            return f"{SHA_B if self.behind else SHA_A}\trefs/heads/main\n"
        if args == ("cat-file", "-e", SHA_B):
            raise CommandError(argv, 1)
        if args == ("merge-base", "--is-ancestor", SHA_B, "HEAD"):
            return ""
        raise AssertionError(f"unexpected git query: {args}")
