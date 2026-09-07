from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

import installer.executors as executors
import installer.update as update
from installer.apps import UpdateExecResult as AppUpdateExecResult
from installer.checksums import ChecksumMismatch
from installer.download import UpdateExecResult as DownloadUpdateExecResult
from installer.executors import ExecutorError
from installer.model import Method, Tool
from installer.ownership import (
    MUTATION_GRADE,
    Confidence,
    ManagerOwnership,
    Owner,
    OwnershipCandidate,
)
from installer.platform import Platform
from installer.pnpm_globals import PnpmUnavailable
from installer.postinstall import run_postinstall
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner
from installer.update import (
    InvalidateFn,
    UpdateError,
    UpdateOutcome,
    UpdateService,
    UpdateTarget,
    perform_update,
    resolve_update_argv,
    should_replay_node_globals,
)
from installer.versions import TagResolver, VersionError


def _platform(*, os: str = "macos", has_brew: bool = True) -> Platform:
    return Platform(os=os, arch="arm64", immutable=False, has_brew=has_brew)


def _tool(
    tool_id: str,
    *methods: Method,
    cmd: str | None = None,
    postinstall: str | None = None,
) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=cmd or tool_id,
        methods=methods,
        postinstall=postinstall,
    )


def _ownership(
    tool: Tool,
    owner: Owner,
    *,
    method: Method | None = None,
    package: str | None = None,
    confidence: Confidence = "direct",
    unknown_reason: str | None = None,
) -> ManagerOwnership:
    chosen = method if method is not None else (tool.methods[0] if tool.methods else None)
    candidate = OwnershipCandidate(
        owner=owner,
        method=chosen,
        package=package,
        current_version=None,
        evidence="test",
    )
    return ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=chosen,
        package=package,
        current_version=None,
        confidence=confidence,
        shadowed=False,
        candidates=(candidate,) if owner != "unknown" else (),
        active_candidate=owner if owner != "unknown" else None,
        active_path=Path("/opt/homebrew/bin") / tool.cmd if owner != "unknown" else None,
        unknown_reason=unknown_reason,
    )


def _target(
    tool: Tool,
    owner: Owner,
    *,
    method: Method | None = None,
    package: str | None = None,
    confidence: Confidence = "direct",
    unknown_reason: str | None = None,
) -> UpdateTarget:
    return UpdateTarget(
        tool=tool,
        ownership=_ownership(
            tool,
            owner,
            method=method,
            package=package,
            confidence=confidence,
            unknown_reason=unknown_reason,
        ),
    )


def _perform(
    target: UpdateTarget,
    runner: Runner,
    *,
    platform: Platform | None = None,
    resolve_tag: TagResolver = lambda _repo: "v1.0.0",
    tools: Mapping[str, Tool] | None = None,
    postinstall: Callable[..., str | None] = run_postinstall,
) -> UpdateOutcome:
    return perform_update(
        target,
        platform=platform or _platform(),
        runner=runner,
        resolve_tag=resolve_tag,
        tools=tools if tools is not None else {},
        postinstall=postinstall,
    )


def test_rg_brew_owned_runs_brew_upgrade_not_github_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A brew-installed rg must not follow resolve_methods ranking.

    installer/registry.toml's rg entry declares github_release (rank 20) and
    brew (rank 40). Indexing resolve_methods[0] would install a second copy
    into ~/.local/bin; the update path must dispatch on ownership.owner.
    """
    github = Method(
        kind="github_release",
        params={"repo": "BurntSushi/ripgrep", "asset": "rg.tar.gz", "member": "rg"},
        os=("macos",),
    )
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", github, brew, cmd="rg")
    platform = _platform()
    assert resolve_methods(tool, platform)[0].kind == "github_release"

    download_calls: list[object] = []

    def boom_download(method: Method, ctx: object) -> DownloadUpdateExecResult:
        download_calls.append((method, ctx))
        raise AssertionError("download executor must not run for a brew-owned tool")

    monkeypatch.setattr(update.download, "update_download", boom_download)
    calls: list[list[str]] = []
    outcome = _perform(
        _target(tool, "brew", method=brew, package="ripgrep"),
        calls.append,
        platform=platform,
    )
    assert outcome.status == "updated"
    assert calls == [["brew", "upgrade", "ripgrep"]]
    assert download_calls == []


def test_unknown_owner_is_refused_with_unknown_reason_and_zero_mutations() -> None:
    tool = _tool("rg", Method(kind="brew", params={"formula": "ripgrep"}))
    reason = "the brew inventory could not be read"
    calls: list[list[str]] = []
    outcome = _perform(
        _target(tool, "unknown", unknown_reason=reason, confidence="none"),
        calls.append,
    )
    assert outcome.status == "unknown-owner"
    assert outcome.detail == reason
    assert calls == []


def test_non_mutation_grade_confidence_is_refused_even_with_a_real_owner() -> None:
    """The gate is ownership.MUTATION_GRADE, never a locally restated list."""
    assert frozenset({"direct", "by-elimination"}) == MUTATION_GRADE
    assert "none" not in MUTATION_GRADE
    tool = _tool("rg", Method(kind="brew", params={"formula": "ripgrep"}))
    reason = "the brew inventory could not be read"
    calls: list[list[str]] = []
    outcome = _perform(
        _target(
            tool,
            "brew",
            method=tool.methods[0],
            package="ripgrep",
            confidence="none",
            unknown_reason=reason,
        ),
        calls.append,
    )
    assert outcome.status == "unknown-owner"
    assert outcome.detail == reason
    assert calls == []
    source = Path(update.__file__).read_text()
    assert "MUTATION_GRADE" in source
    assert 'confidence not in ("direct"' not in source
    assert 'confidence not in ("direct", "by-elimination")' not in source


def test_sdkman_owned_is_unsupported() -> None:
    method = Method(kind="sdkman", params={"candidate": "java"})
    tool = _tool("java", method)
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "installer", method=method), calls.append)
    assert outcome.status == "unsupported"
    assert "sdk" in outcome.detail.lower()
    assert calls == []


def test_pnpm_owned_update_reuses_node_executor_invariants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """12-REVIEWS.md:350-354 — a generic `pnpm update -g` argv would lose:

    - the absolute-path pnpm (PATH wrapper interception)
    - the comma-joined co-install GROUP (space-separated is two isolated groups)
    - `--allow-build=puppeteer` (pnpm silently skips puppeteer's browser download)
    - the registry pin `puppeteer@^25` (plain update respects the declared range,
      12-RESEARCH.md:221: current == wanted == 11.9.0 while latest == 12.3.4)
    - the min_node / min_pnpm floors and the smoke check

    Dispatching executors.execute with the owning node method inherits all of
    those from _node, so they cannot drift from the install path.
    """
    method = Method(
        kind="node",
        params={
            "npm_pkg": "@mermaid-js/mermaid-cli",
            "co_install": ["puppeteer"],
            "allow_build": ["puppeteer"],
            "versions": {"puppeteer": "^25"},
            "min_node": "22.12.0",
            "smoke": "puppeteer-browser",
        },
    )
    tool = _tool("mmdc", method, cmd="mmdc")

    def _always_current(_argv: list[str]) -> str:
        return "24.0.0"

    monkeypatch.setattr(executors, "real_pnpm", lambda: "/opt/homebrew/bin/pnpm")
    monkeypatch.setattr(executors, "probe_version", _always_current)
    monkeypatch.setattr(executors, "launch_puppeteer", lambda: None)
    calls: list[list[str]] = []
    outcome = _perform(
        _target(tool, "pnpm", method=method, package="@mermaid-js/mermaid-cli"),
        calls.append,
    )
    assert outcome.status == "updated"
    assert len(calls) == 1
    argv = calls[0]
    assert argv[0] == "/opt/homebrew/bin/pnpm"
    assert "update" not in argv
    assert argv[1:3] == ["add", "-g"]
    assert "--allow-build=puppeteer" in argv
    assert "@mermaid-js/mermaid-cli,puppeteer@^25" in argv


def test_pnpm_owned_missing_pnpm_is_failed_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    tool = _tool("mmdc", method, cmd="mmdc")
    monkeypatch.setattr(executors, "real_pnpm", lambda: None)
    calls: list[list[str]] = []
    outcome = _perform(
        _target(tool, "pnpm", method=method, package="@mermaid-js/mermaid-cli"),
        calls.append,
    )
    assert outcome.status == "failed"
    assert outcome.errors
    assert isinstance(outcome.errors[0], ExecutorError)
    assert calls == []


def test_pnpm_owned_node_below_floor_never_reaches_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method = Method(
        kind="node",
        params={
            "npm_pkg": "@mermaid-js/mermaid-cli",
            "co_install": ["puppeteer"],
            "min_node": "22.12.0",
        },
    )
    tool = _tool("mmdc", method, cmd="mmdc")
    monkeypatch.setattr(executors, "real_pnpm", lambda: "/opt/homebrew/bin/pnpm")

    def probe(argv: list[str]) -> str:
        return "11.9.0" if argv[0] == "/opt/homebrew/bin/pnpm" else "v18.0.0"

    monkeypatch.setattr(executors, "probe_version", probe)
    calls: list[list[str]] = []
    outcome = _perform(
        _target(tool, "pnpm", method=method, package="@mermaid-js/mermaid-cli"),
        calls.append,
    )
    assert outcome.status == "failed"
    assert calls == []


def test_resolve_update_argv_returns_none_for_pnpm() -> None:
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    tool = _tool("mmdc", method, cmd="mmdc")
    argv = resolve_update_argv(
        _target(tool, "pnpm", method=method, package="@mermaid-js/mermaid-cli")
    )
    assert argv is None


def test_cask_argv_includes_appdir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update, "applications_dir", lambda: Path("/Users/me/Applications"))
    method = Method(kind="cask", params={"cask": "rectangle"})
    tool = _tool("rectangle", method)
    argv = resolve_update_argv(_target(tool, "cask", method=method, package="rectangle"))
    assert argv is not None
    assert argv[:3] == ["brew", "upgrade", "--cask"]
    assert "--appdir=/Users/me/Applications" in argv
    assert argv[-1] == "rectangle"


@pytest.mark.parametrize(
    "exc",
    [
        CommandError(["brew", "upgrade", "ripgrep"], 1, detail="no formula"),
        OSError("permission denied"),
        ExecutorError("no executor"),
        VersionError("no tag"),
        ChecksumMismatch("rg.tar.gz", "abc", "def"),
        UpdateError("bad owner"),
        PnpmUnavailable("pnpm missing"),
    ],
)
def test_perform_update_contains_domain_exceptions(exc: Exception) -> None:
    tool = _tool("rg", Method(kind="brew", params={"formula": "ripgrep"}))

    def exploding(_cmd: list[str]) -> None:
        raise exc

    outcome = _perform(_target(tool, "brew", package="ripgrep"), exploding)
    assert outcome.status == "failed"
    assert outcome.errors == (exc,)
    assert outcome.detail == str(exc)


def test_postinstall_dispatched_with_owning_method_after_success() -> None:
    brew = Method(kind="brew", params={"formula": "codegraph"})
    tool = _tool("codegraph", brew, postinstall="codegraph-mcp-register")
    seen: list[tuple[str, Method]] = []

    def spy(name: str, method: Method, runner: object, tools: object) -> str | None:
        seen.append((name, method))
        return None

    outcome = _perform(
        _target(tool, "brew", method=brew, package="codegraph"),
        lambda _cmd: None,
        postinstall=spy,
    )
    assert outcome.status == "updated"
    assert seen == [("codegraph-mcp-register", brew)]
    assert outcome.postinstall_warning is None


def test_postinstall_crash_is_warning_not_failure() -> None:
    brew = Method(kind="brew", params={"formula": "codegraph"})
    tool = _tool("codegraph", brew, postinstall="codegraph-mcp-register")

    def boom(name: str, method: Method, runner: object, tools: object) -> str | None:
        raise RuntimeError("hook bug")

    outcome = _perform(
        _target(tool, "brew", method=brew, package="codegraph"),
        lambda _cmd: None,
        postinstall=boom,
    )
    assert outcome.status == "updated"
    assert outcome.postinstall_warning is not None
    assert "hook bug" in outcome.postinstall_warning


def test_no_postinstall_never_calls_hook() -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    calls: list[str] = []

    def spy(name: str, method: Method, runner: object, tools: object) -> str | None:
        calls.append(name)
        return None

    outcome = _perform(
        _target(tool, "brew", method=brew, package="ripgrep"),
        lambda _cmd: None,
        postinstall=spy,
    )
    assert outcome.status == "updated"
    assert calls == []


def test_installer_download_cleanup_warnings_copied(monkeypatch: pytest.MonkeyPatch) -> None:
    method = Method(
        kind="github_release",
        params={"repo": "BurntSushi/ripgrep", "asset": "rg.tar.gz", "member": "rg"},
    )
    tool = _tool("rg", method, cmd="rg")
    warnings = ("could not remove leftover .old: permission denied",)

    def fake_update(method: Method, ctx: object) -> DownloadUpdateExecResult:
        return DownloadUpdateExecResult(verified=True, warnings=warnings)

    monkeypatch.setattr(update.download, "update_download", fake_update)
    outcome = _perform(_target(tool, "installer", method=method), lambda _cmd: None)
    assert outcome.status == "updated"
    assert outcome.cleanup_warnings == warnings


def test_installer_apps_cleanup_warnings_copied(monkeypatch: pytest.MonkeyPatch) -> None:
    method = Method(kind="app", params={"url": "https://example.com/a.zip", "app": "Foo.app"})
    tool = _tool("foo", method)
    warnings = ("leftover .old bundle",)

    def fake_update(method: Method, runner: object) -> AppUpdateExecResult:
        return AppUpdateExecResult(warnings=warnings)

    monkeypatch.setattr(update.apps, "update_app", fake_update)
    outcome = _perform(_target(tool, "installer", method=method), lambda _cmd: None)
    assert outcome.status == "updated"
    assert outcome.cleanup_warnings == warnings


def test_installer_script_cleanup_warnings_empty() -> None:
    method = Method(kind="script", params={"url": "https://get.pnpm.io/install.sh", "shell": "sh"})
    tool = _tool("pnpm", method)
    outcome = _perform(_target(tool, "installer", method=method), lambda _cmd: None)
    assert outcome.status == "updated"
    assert outcome.cleanup_warnings == ()


def test_should_replay_node_globals_only_for_pnpm_tool() -> None:
    """REQ-pnpm-global-reinstall-mitigation: replay only after pnpm itself updates.

    pnpm installs through a vendor script or brew, never a node method, so the
    trigger keys on tool.id, not on ownership.owner. Replaying after every
    node-package update would be an unrequested secondary mutation
    (12-REVIEWS.md:137).
    """
    pnpm_tool = _tool(
        "pnpm",
        Method(kind="script", params={"url": "https://get.pnpm.io/install.sh", "shell": "sh"}),
    )
    mmdc = _tool(
        "mmdc",
        Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),
        cmd="mmdc",
    )
    assert (
        should_replay_node_globals(_target(pnpm_tool, "installer", method=pnpm_tool.methods[0]))
        is True
    )
    assert (
        should_replay_node_globals(
            _target(mmdc, "pnpm", method=mmdc.methods[0], package="@mermaid-js/mermaid-cli")
        )
        is False
    )


def test_resolve_update_argv_unknown_raises() -> None:
    tool = _tool("rg", Method(kind="brew", params={"formula": "ripgrep"}))
    with pytest.raises(UpdateError):
        resolve_update_argv(
            _target(tool, "unknown", confidence="none", unknown_reason="no manager")
        )


def test_uv_argv() -> None:
    method = Method(kind="uv-tool", params={"pypi_pkg": "ruff"})
    tool = _tool("ruff", method)
    assert resolve_update_argv(_target(tool, "uv", method=method, package="ruff")) == [
        "uv",
        "tool",
        "upgrade",
        "ruff",
    ]


def test_perform_update_does_not_import_resolve_ownership_or_resolve_methods() -> None:
    import_lines = [
        line
        for line in Path(update.__file__).read_text().splitlines()
        if line.lstrip().startswith(("from ", "import "))
    ]
    joined = "\n".join(import_lines)
    assert "resolve_ownership" not in joined
    assert "installer.resolve" not in joined
    assert "installer.engine" not in joined


def _service(
    *,
    reresolve: Callable[[Tool], ManagerOwnership],
    managed: Callable[[], tuple[str, ...] | None] = lambda: (),
    replay: Callable[[Sequence[str]], tuple[str, ...]] | None = None,
    invalidate: InvalidateFn | None = None,
    runner: Callable[[list[str]], None] | None = None,
) -> UpdateService:
    from collections.abc import Sequence as Seq

    def _replay(packages: Seq[str]) -> tuple[str, ...]:
        return tuple(packages)

    return UpdateService(
        platform=_platform(),
        runner=runner or (lambda _cmd: None),
        resolve_tag=lambda _repo: "v1",
        tools={},
        managed_packages=managed,
        replay_globals=replay or _replay,
        reresolve_ownership=reresolve,
        invalidate=invalidate,
    )


def test_update_service_begin_blocks_a_second_trigger() -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep")
    )
    assert service.begin("rg") is True
    assert service.in_flight == "rg"
    assert service.begin("fd") is False
    assert service.in_flight == "rg"
    service.end()
    assert service.in_flight is None
    assert service.begin("fd") is True


def test_update_service_fresh_ownership_overrides_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    github = Method(
        kind="github_release",
        params={"repo": "BurntSushi/ripgrep", "asset": "rg.tar.gz", "member": "rg"},
    )
    tool = _tool("rg", github, brew, cmd="rg")
    cached = _target(tool, "installer", method=github)
    calls: list[list[str]] = []
    order: list[str] = []

    def reresolve(_tool: Tool) -> ManagerOwnership:
        order.append("reresolve")
        return _ownership(tool, "brew", method=brew, package="ripgrep")

    def managed() -> tuple[str, ...] | None:
        order.append("managed")
        return ("x",)

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        order.append("mutate")
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner=target.ownership.owner)

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(reresolve=reresolve, managed=managed, runner=calls.append)
    outcome = service.run(cached)
    assert outcome.status == "updated"
    assert order[0] == "reresolve"
    assert "managed" not in order


def test_update_service_fresh_unknown_refuses_despite_cached_green() -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    cached = _target(tool, "brew", method=brew, package="ripgrep")
    calls: list[list[str]] = []

    def reresolve(_tool: Tool) -> ManagerOwnership:
        return _ownership(
            tool,
            "unknown",
            confidence="none",
            unknown_reason="the brew inventory could not be read",
        )

    service = _service(reresolve=reresolve, runner=calls.append)
    outcome = service.run(cached)
    assert outcome.status == "unknown-owner"
    assert "brew inventory" in outcome.detail
    assert calls == []


def test_update_service_precaptures_pnpm_globals_before_mutate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """12-REVIEWS.md:338-342 — a post-update capture would replay an empty list."""
    method = Method(kind="script", params={"url": "https://get.pnpm.io/install.sh", "shell": "sh"})
    tool = _tool("pnpm", method)
    live: list[str] = ["@mermaid-js/mermaid-cli", "puppeteer"]
    order: list[str] = []
    replayed: list[tuple[str, ...]] = []

    def managed() -> tuple[str, ...] | None:
        order.append("managed")
        return tuple(live)

    def mutate(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        order.append("mutate")
        live.clear()
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="installer")

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        order.append("replay")
        replayed.append(tuple(packages))
        return tuple(packages)

    monkeypatch.setattr(update, "perform_update", mutate)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "installer", method=method),
        managed=managed,
        replay=replay,
    )
    outcome = service.run(_target(tool, "installer", method=method))
    assert outcome.status == "updated"
    assert order.index("managed") < order.index("mutate")
    assert order.index("mutate") < order.index("replay")
    assert replayed == [("@mermaid-js/mermaid-cli", "puppeteer")]
    assert outcome.replayed_globals == ("@mermaid-js/mermaid-cli", "puppeteer")


def test_update_service_skips_snapshot_for_non_pnpm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    tool = _tool("mmdc", method, cmd="mmdc")
    managed_calls: list[int] = []
    replay_calls: list[int] = []

    def managed() -> tuple[str, ...] | None:
        managed_calls.append(1)
        return ("x",)

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        replay_calls.append(1)
        return tuple(packages)

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="pnpm")

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(
            tool, "pnpm", method=method, package="@mermaid-js/mermaid-cli"
        ),
        managed=managed,
        replay=replay,
    )
    service.run(_target(tool, "pnpm", method=method, package="@mermaid-js/mermaid-cli"))
    assert managed_calls == []
    assert replay_calls == []


def test_update_service_none_snapshot_refuses_to_mutate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 regression (12-REVIEW.md, codex-sol-high): pnpm is the exact event
    that can lose the global set, so an unreadable pre-capture snapshot must
    refuse the mutation outright — never proceed with a warning. Zero mutation:
    `perform_update` must not even be called."""
    method = Method(kind="script", params={"url": "https://get.pnpm.io/install.sh", "shell": "sh"})
    tool = _tool("pnpm", method)
    replay_calls: list[int] = []
    perform_calls: list[int] = []

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        replay_calls.append(1)
        return tuple(packages)

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        perform_calls.append(1)
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="installer")

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "installer", method=method),
        managed=lambda: None,
        replay=replay,
    )
    outcome = service.run(_target(tool, "installer", method=method))
    assert outcome.status != "updated"
    assert outcome.status == "failed"
    assert perform_calls == []
    assert replay_calls == []
    assert "could not be verified" in outcome.detail


def test_update_service_invalidate_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    reasons: list[str] = []

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="brew")

    def record_invalidate(*, reason: str) -> int:
        reasons.append(reason)
        return 2

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep"),
        invalidate=record_invalidate,
    )
    service.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert reasons == ["updated rg"]


def test_update_service_invalidate_failure_stays_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    """W2 regression (12-REVIEW.md, codex-sol-high): the machine was already
    mutated successfully by the time cache invalidation runs, so a failure
    writing the version cache must surface as a post-update warning on a
    still-`"updated"` outcome — never propagate and get reported as a failed
    update (which `run_live` would otherwise convert into `(None, message)`,
    discarding the fact that the mutation itself succeeded)."""
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="brew")

    def failing_invalidate(*, reason: str) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep"),
        invalidate=failing_invalidate,
    )
    outcome = service.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert outcome.status == "updated"
    assert "cache invalidation failed" in outcome.detail
