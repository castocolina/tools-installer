import hashlib
import json
import os
import typing
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

import installer.executors as executors
import installer.update as update
from installer import receipts
from installer.apps import UpdateExecResult as AppUpdateExecResult
from installer.checksums import ChecksumMismatch
from installer.download import ExecContext
from installer.download import UpdateExecResult as DownloadUpdateExecResult
from installer.executors import ExecutorError
from installer.model import Method, Tool
from installer.ownership import (
    MUTATION_GRADE,
    NATIVE_OWNERS,
    OS_PACKAGE_OWNER,
    UNMANAGEABLE_OWNERS,
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
from installer.versions import TagResolver, VersionError, release_resolver, resolve_github_tag
from tests.test_download import fixture_runner


def _plant_rg_install(tmp_path: Path) -> tuple[Path, Path]:
    opt = tmp_path / ".local" / "opt" / "rg"
    opt.mkdir(parents=True)
    binary = opt / "rg"
    binary.write_bytes(b"old-binary")
    binary.chmod(0o755)
    (opt / "marker").write_text("original")
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    link = bindir / "rg"
    os.symlink(str(binary), link)
    return opt, link


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
    outcome = _perform(_target(tool, "sdkman", method=method, package="java"), calls.append)
    assert outcome.status == "unsupported"
    assert "sdk" in outcome.detail.lower()
    assert calls == []


def test_sdkman_owned_update_refuses_with_real_command() -> None:
    method = Method(kind="sdkman", params={"candidate": "groovy"})
    tool = _tool("groovy", method)
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "sdkman", method=method, package="groovy"), calls.append)
    assert outcome.status == "unsupported"
    assert "sdk upgrade groovy" in outcome.detail
    assert "not attributable" not in outcome.detail
    assert "this phase does not implement" not in outcome.detail
    assert calls == []


# -- D-05/T-15-15: a native-owned tool now clears MUTATION_GRADE (`direct` is
# a member), so `_perform` needs an explicit refusal BEFORE the owner-dispatch
# ladder or it hits `else: raise UpdateError(f"unsupported owner ...")`. ----


@pytest.mark.parametrize("native_owner", NATIVE_OWNERS)
def test_native_owner_is_refused_with_concrete_manager_named(native_owner: Owner) -> None:
    """Parameterized over all four owners, not one representative: the
    failure this guards against is a branch condition that enumerates three
    of the four, leaving the omitted one reaching the ladder's final `else`."""
    tool = _tool("jq", Method(kind="dnf", params={"package": "jq"}))
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, native_owner), calls.append)
    assert outcome.status == "unsupported"
    assert native_owner in outcome.detail
    assert calls == []


def test_native_owners_tuple_is_exactly_the_four_widened_values() -> None:
    """The membership decision is written once, as ownership.py's
    NATIVE_OWNERS, and this module reaches it by import rather than
    restating the names -- so a fifth owner is refused automatically."""
    assert set(NATIVE_OWNERS) == {"dnf", "apt", "pacman", "rpm-ostree"}
    assert len(NATIVE_OWNERS) == 4
    assert set(NATIVE_OWNERS) <= set(typing.get_args(Owner))


# -- 15.4-01/D-01/T2: os-package widens the refusal, never the attribution --
# set. `direct` is in MUTATION_GRADE, so this owner now clears the gate too
# and needs the same explicit pre-ladder refusal the four native owners get.


def test_os_package_owner_is_refused_with_the_real_package_named() -> None:
    tool = _tool("git", Method(kind="dnf", params={"package": "git"}))
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "os-package", package="git-core"), calls.append)
    assert outcome.status == "unsupported"
    assert outcome.owner == "os-package"
    assert "git-core" in outcome.detail
    assert calls == []


@pytest.mark.parametrize("owner", sorted(UNMANAGEABLE_OWNERS))
def test_every_unmanageable_owner_returns_a_clean_unsupported_outcome_not_a_raise(
    owner: Owner,
) -> None:
    """Ordering proof, not a source-index gate (Round-1 review 15.4-01 LOW):
    the owner-dispatch ladder has no arm for ANY of these owners, so a
    refusal placed AFTER the ladder would hit its terminal `else: raise
    UpdateError(...)` instead of returning cleanly. This is a complete
    detector for the ordering and survives a refactor that hoists the whole
    gate into a helper."""
    tool = _tool("jq", Method(kind="dnf", params={"package": "jq"}))
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, owner, package="jq"), calls.append)
    assert outcome.status == "unsupported"
    assert calls == []


def test_unmanageable_owners_is_the_set_update_py_actually_reads() -> None:
    assert frozenset({*NATIVE_OWNERS, OS_PACKAGE_OWNER}) == UNMANAGEABLE_OWNERS
    assert set(typing.get_args(Owner)) >= UNMANAGEABLE_OWNERS
    source = Path(update.__file__).read_text()
    assert "UNMANAGEABLE_OWNERS" in source


def test_os_package_detail_template_names_a_package_placeholder() -> None:
    assert isinstance(update._OS_PACKAGE_DETAIL, str)  # pyright: ignore[reportPrivateUsage]
    assert "{package}" in update._OS_PACKAGE_DETAIL  # pyright: ignore[reportPrivateUsage]


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


def test_installer_owned_update_passes_the_release_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[TagResolver] = []
    real = release_resolver

    def recording_resolver(resolve_tag: TagResolver):
        recorded.append(resolve_tag)
        return real(resolve_tag)

    monkeypatch.setattr(update, "release_resolver", recording_resolver)
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz",
            "member": "rg",
            "strip": 1,
        },
    )
    tool = _tool("rg", method, cmd="rg")

    def fake_update(method: Method, ctx: ExecContext) -> DownloadUpdateExecResult:
        return DownloadUpdateExecResult(verified=True)

    monkeypatch.setattr(update.download, "update_download", fake_update)

    def tag(_repo: str) -> str:
        return "v15.1.0"

    _perform(_target(tool, "installer", method=method), lambda _cmd: None, resolve_tag=tag)
    assert recorded == [tag]


def test_installer_owned_update_rejects_a_wrong_api_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workdir = tmp_path / "update-staging"
    workdir.mkdir()

    def fake_mkdtemp(prefix: str) -> str:
        return str(workdir)

    monkeypatch.setattr(update.download.tempfile, "mkdtemp", fake_mkdtemp)
    asset = "ripgrep-15.1.0-x86_64-unknown-linux-musl.tar.gz"
    payload = b"fresh-archive-bytes"
    api_digest = "f" * 64
    opt, link = _plant_rg_install(tmp_path)
    before_opt = (opt / "marker").read_text()
    before_binary = (opt / "rg").read_bytes()
    before_link = os.readlink(link)

    release_json = json.dumps(
        {
            "tag_name": "15.1.0",
            "assets": [{"name": asset, "digest": f"sha256:{api_digest}"}],
        }
    ).encode()

    class _FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    def fake_urlopen(req: object, timeout: float = 10) -> _FakeResponse:
        return _FakeResponse(release_json)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    calls, runner = fixture_runner(workdir, {asset: payload}, member=opt / "rg")
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "ripgrep-{ver}-{arch.machine}-unknown-linux-musl.tar.gz",
            "member": "rg",
            "strip": 1,
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    tool = _tool("rg", method, cmd="rg")
    outcome = _perform(
        _target(tool, "installer", method=method),
        runner,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        resolve_tag=resolve_github_tag,
    )
    assert outcome.status == "failed"
    assert outcome.errors
    assert isinstance(outcome.errors[0], ChecksumMismatch)
    assert (opt / "marker").read_text() == before_opt
    assert (opt / "rg").read_bytes() == before_binary
    assert os.readlink(link) == before_link
    assert calls  # runner saw the staged fetch


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
    terminal_follow_up: Callable[[], str | None] | None = None,
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
        terminal_follow_up=terminal_follow_up,
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


# -- 15.6-05/D-01: the same terminal synchronizer Plan 04 wired for Policies,
# reached from a successful direct `u` update through UpdateService.run. -----


def test_update_service_calls_terminal_follow_up_after_a_successful_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    calls: list[int] = []

    def follow_up() -> str | None:
        calls.append(1)
        return None

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="brew")

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep"),
        terminal_follow_up=follow_up,
    )
    outcome = service.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert outcome.status == "updated"
    assert calls == [1]


def test_update_service_terminal_follow_up_oserror_appends_warning_without_downgrading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminal synchronization failure must stay visible beside the
    successful update — never flip `status` away from `"updated"`."""
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")

    def failing_follow_up() -> str | None:
        raise OSError("konsole profile is not writable")

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="brew")

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep"),
        terminal_follow_up=failing_follow_up,
    )
    outcome = service.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert outcome.status == "updated"
    assert "konsole profile is not writable" in outcome.detail


@pytest.mark.parametrize("status", ["failed", "unsupported"])
def test_update_service_terminal_follow_up_skipped_for_non_updated_outcomes(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    calls: list[int] = []

    def follow_up() -> str | None:
        calls.append(1)
        return None

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status=status, owner="brew")  # type: ignore[arg-type]

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep"),
        terminal_follow_up=follow_up,
    )
    outcome = service.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert outcome.status == status
    assert calls == []


def test_update_service_terminal_follow_up_skipped_for_refused_unknown_owner() -> None:
    tool = _tool("rg", Method(kind="brew", params={"formula": "ripgrep"}))
    calls: list[int] = []

    def follow_up() -> str | None:
        calls.append(1)
        return None

    def reresolve(_tool: Tool) -> ManagerOwnership:
        return _ownership(tool, "unknown", confidence="none", unknown_reason="no manager")

    service = _service(reresolve=reresolve, terminal_follow_up=follow_up)
    outcome = service.run(_target(tool, "brew", package="ripgrep"))
    assert outcome.status == "unknown-owner"
    assert calls == []


def test_update_service_terminal_follow_up_runs_after_pnpm_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method = Method(kind="script", params={"url": "https://get.pnpm.io/install.sh", "shell": "sh"})
    tool = _tool("pnpm", method)
    order: list[str] = []

    def managed() -> tuple[str, ...] | None:
        order.append("managed")
        return ("x",)

    def mutate(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        order.append("mutate")
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="installer")

    def replay(packages: Sequence[str]) -> tuple[str, ...]:
        order.append("replay")
        return tuple(packages)

    def follow_up() -> str | None:
        order.append("terminal_follow_up")
        return None

    monkeypatch.setattr(update, "perform_update", mutate)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "installer", method=method),
        managed=managed,
        replay=replay,
        terminal_follow_up=follow_up,
    )
    outcome = service.run(_target(tool, "installer", method=method))
    assert outcome.status == "updated"
    assert order == ["managed", "mutate", "replay", "terminal_follow_up"]


def test_update_service_terminal_follow_up_runs_before_invalidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    order: list[str] = []

    def fake_perform(target: UpdateTarget, **_kwargs: object) -> UpdateOutcome:
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner="brew")

    def follow_up() -> str | None:
        order.append("terminal_follow_up")
        return None

    def invalidate(*, reason: str) -> int:
        order.append("invalidate")
        return 1

    monkeypatch.setattr(update, "perform_update", fake_perform)
    service = _service(
        reresolve=lambda _tool: _ownership(tool, "brew", method=brew, package="ripgrep"),
        terminal_follow_up=follow_up,
        invalidate=invalidate,
    )
    service.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert order == ["terminal_follow_up", "invalidate"]


def test_off_policy_brew_update_names_the_declared_manager() -> None:
    method = Method(kind="sdkman", params={"candidate": "groovy"})
    tool = _tool("groovy", method)
    ownership = replace(
        _ownership(tool, "brew", method=method, package="groovy"),
        method=None,
        off_policy=True,
    )
    calls: list[list[str]] = []
    outcome = _perform(UpdateTarget(tool=tool, ownership=ownership), calls.append)
    assert outcome.status == "updated"
    assert calls == [["brew", "upgrade", "groovy"]]
    assert outcome.detail == (
        "Homebrew owns this copy; the catalog installs groovy via SDKMAN "
        "— moving it there is not available yet, so it was updated through Homebrew"
    )


def test_on_policy_brew_update_keeps_empty_detail() -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew)
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "brew", method=brew, package="ripgrep"), calls.append)
    assert outcome.status == "updated"
    assert outcome.detail == ""
    assert calls == [["brew", "upgrade", "ripgrep"]]


def test_update_service_fresh_unknown_overrides_cached_off_policy_brew() -> None:
    method = Method(kind="sdkman", params={"candidate": "groovy"})
    tool = _tool("groovy", method)
    cached = UpdateTarget(
        tool=tool,
        ownership=replace(
            _ownership(tool, "brew", method=method, package="groovy"),
            method=None,
            off_policy=True,
        ),
    )
    calls: list[list[str]] = []

    def reresolve(_ignored: Tool) -> ManagerOwnership:
        return _ownership(
            tool,
            "unknown",
            confidence="none",
            unknown_reason="no manager claimed the tool",
        )

    service = _service(reresolve=reresolve, runner=calls.append)
    outcome = service.run(cached)
    assert outcome.status == "unknown-owner"
    assert calls == []


def test_updating_graphify_runs_no_host_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Phase 17 SAFE-02/D-03: the update path (update.py's _run_postinstall)
    runs no graphify host-registration hook either, because the registry key
    is gone -- the runner sees exactly `uv tool upgrade graphifyy` and the
    working directory stays empty (SPEC R2 acceptance)."""
    import installer.postinstall as pi
    from installer.model import load_tools

    registry = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
    tools = {t.id: t for t in load_tools(registry)}
    graphify = tools["graphify"]

    def all_installed(_tool: Tool) -> bool:
        return True

    def fake_resolve_tag(*_argv: str, **_kwargs: str) -> str:
        return "v0"

    monkeypatch.setattr(pi, "is_installed", all_installed)
    home = tmp_path / "home"
    home.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(cwd)
    calls: list[list[str]] = []
    outcome = perform_update(
        _target(graphify, "uv", method=graphify.methods[0], package="graphifyy"),
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=calls.append,
        resolve_tag=fake_resolve_tag,
        tools=tools,
    )
    assert outcome.status == "updated"
    assert outcome.postinstall_warning is None
    assert calls == [["uv", "tool", "upgrade", "graphifyy"]]
    assert list(cwd.iterdir()) == []


def test_update_refuses_volta_cleanly() -> None:
    tool = _tool("pnpm", Method(kind="script", params={"url": "u"}))
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "volta", package="pnpm"), calls.append)
    assert outcome.status == "unsupported"
    assert outcome.owner == "volta"
    assert "volta install pnpm" in outcome.detail
    assert calls == []


def test_update_refuses_host_setup_pnpm_cleanly() -> None:
    # No methods on the tool: the `_target` helper would otherwise fill one in.
    tool = _tool("pi")
    target = _target(tool, "pnpm", package="@earendil-works/pi-coding-agent")
    assert target.ownership.method is None
    calls: list[list[str]] = []
    outcome = _perform(target, calls.append)
    assert outcome.status == "unsupported"
    assert outcome.owner == "pnpm"
    assert "pnpm add --global --ignore-scripts @earendil-works/pi-coding-agent" in outcome.detail
    assert calls == []


# --- Plan 19-09: updates rewrite the receipt through the same writer ----------


def _raw_yq(bin_dir: Path) -> Method:
    return Method(
        kind="github_release",
        params={
            "repo": "mikefarah/yq",
            "asset": "yq_linux_{arch.deb}",
            "member": "yq_linux_amd64",
            "bin_name": "yq",
            "raw": True,
            "bin_dir": str(bin_dir),
        },
    )


def _fake_download_update(monkeypatch: pytest.MonkeyPatch, placed: Path, payload: bytes) -> None:
    def fake_update(_method: Method, _ctx: object) -> DownloadUpdateExecResult:
        placed.write_bytes(payload)
        return DownloadUpdateExecResult(verified=True, warnings=())

    monkeypatch.setattr(update.download, "update_download", fake_update)


def _yq_with_old_bytes(tmp_path: Path) -> tuple[Tool, Method, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    placed = bin_dir / "yq"
    placed.write_bytes(b"old-yq")
    method = _raw_yq(bin_dir)
    return _tool("yq", method), method, placed


def _later(after: str, before: str) -> bool:
    from datetime import datetime

    return datetime.fromisoformat(after) > datetime.fromisoformat(before)


def test_installer_owned_update_rewrites_the_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool, method, placed = _yq_with_old_bytes(tmp_path)
    before = receipts.record(tool, method, package=None, smoke="ok")
    assert before is not None
    _fake_download_update(monkeypatch, placed, b"new-yq-bytes")
    outcome = _perform(_target(tool, "installer", method=method), lambda _cmd: None)
    assert outcome.status == "updated"
    after = receipts.read("yq")
    assert after is not None
    assert after.artifacts[0].sha256 == hashlib.sha256(b"new-yq-bytes").hexdigest()
    assert after.artifacts[0].size == len(b"new-yq-bytes")
    assert _later(after.at, before.at)
    assert after.smoke is None


def test_installer_owned_update_without_receipt_writes_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool, method, placed = _yq_with_old_bytes(tmp_path)
    assert receipts.read("yq") is None
    _fake_download_update(monkeypatch, placed, b"new-yq-bytes")
    outcome = _perform(_target(tool, "installer", method=method), lambda _cmd: None)
    assert outcome.status == "updated"
    after = receipts.read("yq")
    assert after is not None
    assert after.artifacts == (receipts.fingerprint(placed, "file"),)


@pytest.mark.parametrize("had_receipt", [True, False])
def test_brew_update_rewrites_only_an_existing_receipt(had_receipt: bool) -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    before = receipts.record(tool, brew, package="ripgrep", smoke="ok") if had_receipt else None
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "brew", method=brew, package="ripgrep"), calls.append)
    assert outcome.status == "updated"
    assert calls == [["brew", "upgrade", "ripgrep"]]
    after = receipts.read("rg")
    if before is None:
        assert after is None
    else:
        assert after is not None
        assert after.package == "ripgrep"
        assert after.method.kind == "brew"
        assert _later(after.at, before.at)


def test_failed_update_keeps_the_old_receipt() -> None:
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    receipts.record(tool, brew, package="ripgrep", smoke="ok")
    path = receipts.receipt_path("rg")
    old_bytes = path.read_bytes()

    def failing(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    outcome = _perform(_target(tool, "brew", method=brew, package="ripgrep"), failing)
    assert outcome.status == "failed"
    assert path.read_bytes() == old_bytes


def test_update_receipt_write_failure_is_a_detail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool, method, placed = _yq_with_old_bytes(tmp_path)
    receipts.record(tool, method, package=None, smoke="ok")
    _fake_download_update(monkeypatch, placed, b"new-yq-bytes")

    def read_only(_receipt: receipts.Receipt) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(receipts, "write", read_only)
    outcome = _perform(_target(tool, "installer", method=method), lambda _cmd: None)
    assert outcome.status == "updated"
    assert "install receipt not written" in outcome.detail
    assert "the previous receipt was removed" in outcome.detail
    assert receipts.read("yq") is None


@pytest.mark.parametrize("owner", ["unknown", "sdkman", "dnf", "volta"])
def test_unknown_and_refused_updates_write_nothing(owner: Owner) -> None:
    if owner == "sdkman":
        method = Method(kind="sdkman", params={"candidate": "java"})
    elif owner == "dnf":
        method = Method(kind="dnf", params={"package": "java"})
    else:
        method = Method(kind="script", params={"url": "u", "shell": "sh"})
    tool = _tool("java", method)
    seeded = receipts.Receipt(
        tool="java",
        at="2026-01-01T00:00:00+00:00",
        method=receipts.ReceiptMethod(kind="script", key="k"),
        package=None,
        artifacts=(),
        smoke=None,
        hooks={},
    )
    receipts.write(seeded)
    old_bytes = receipts.receipt_path("java").read_bytes()
    target = _target(
        tool,
        owner,
        method=method,
        package="java",
        unknown_reason="no evidence" if owner == "unknown" else None,
    )
    calls: list[list[str]] = []
    outcome = _perform(target, calls.append)
    assert outcome.status in ("unknown-owner", "unsupported")
    assert calls == []
    assert receipts.receipt_path("java").read_bytes() == old_bytes
    assert [p.name for p in receipts.receipts_dir().iterdir()] == ["java.json"]


def test_host_setup_update_hint_is_the_reviewed_handoff() -> None:
    """G14: a host-setup tool's update hint quotes the reviewed handoff command."""
    from installer.host_setup import HOST_SETUPS

    tool = _tool("pi", Method(kind="host_setup", params={"setup_id": "pi"}))
    ownership = replace(
        _ownership(tool, "pnpm", package="@earendil-works/pi-coding-agent"),
        method=None,
    )
    target = UpdateTarget(tool=tool, ownership=ownership)
    assert target.ownership.method is None
    calls: list[list[str]] = []
    outcome = _perform(target, calls.append)
    assert outcome.status == "unsupported"
    assert f"`{HOST_SETUPS['pi'].handoff[1]}`" in outcome.detail
    assert calls == []


def test_update_service_reads_the_live_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-14, checker W2: `run` reads the live platform at run time, so brew
    appearing after construction reaches `perform_update`; without a provider
    the construction platform is used."""
    brew = Method(kind="brew", params={"formula": "ripgrep"})
    tool = _tool("rg", brew, cmd="rg")
    seen: list[Platform] = []

    def fake_perform(
        target: UpdateTarget, *, platform: Platform, **_kwargs: object
    ) -> UpdateOutcome:
        seen.append(platform)
        return UpdateOutcome(tool_id=target.tool.id, status="updated", owner=target.ownership.owner)

    def reresolve(_tool: Tool) -> ManagerOwnership:
        return _ownership(tool, "brew", method=brew, package="ripgrep")

    monkeypatch.setattr(update, "perform_update", fake_perform)
    current = [_platform(has_brew=False)]
    live = UpdateService(
        platform=_platform(has_brew=False),
        live_platform=lambda: current[0],
        runner=lambda _cmd: None,
        tools={},
        managed_packages=lambda: (),
        replay_globals=tuple,
        reresolve_ownership=reresolve,
    )
    current[0] = _platform(has_brew=True)
    live.run(_target(tool, "brew", method=brew, package="ripgrep"))
    fixed = _service(reresolve=reresolve)
    fixed.run(_target(tool, "brew", method=brew, package="ripgrep"))
    assert [platform.has_brew for platform in seen] == [True, True]
    assert seen[1] is fixed.platform


def test_manager_update_keeps_an_installer_receipt(tmp_path: Path) -> None:
    """G4: a brew update never rewrites an installer receipt, so the installer's
    own files stay removal-proven."""
    tool, method, _placed = _yq_with_old_bytes(tmp_path)
    receipts.record(tool, method, package=None, smoke="ok")
    receipt_bytes = receipts.receipt_path("yq").read_bytes()
    brew = Method(kind="brew", params={"formula": "yq"})
    calls: list[list[str]] = []
    outcome = _perform(_target(tool, "brew", method=brew, package="yq"), calls.append)
    assert outcome.status == "updated"
    assert calls == [["brew", "upgrade", "yq"]]
    assert receipts.receipt_path("yq").read_bytes() == receipt_bytes
    kept = receipts.read("yq")
    assert kept is not None
    assert kept.method.kind == "github_release"


def test_dir_drift_does_not_block_an_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Dir drift alone never refuses an update; the update re-records the key file."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    opt, _link = _plant_rg_install(tmp_path)
    method = Method(
        kind="github_release",
        params={
            "repo": "BurntSushi/ripgrep",
            "asset": "rg.tar.gz",
            "member": "rg",
            "bin_dir": str(tmp_path / "bin"),
        },
    )
    tool = _tool("rg", method)
    receipts.record(tool, method, package=None, smoke="ok")
    (opt / "rg").write_bytes(b"vendor-built")
    _fake_download_update(monkeypatch, opt / "rg", b"updated-binary")
    calls: list[list[str]] = []
    outcome = _service(
        reresolve=lambda _t: _ownership(tool, "installer", method=method),
        runner=calls.append,
    ).run(_target(tool, "installer", method=method))
    assert outcome.status == "updated"
    assert (opt / "rg").read_bytes() == b"updated-binary"
    reread = receipts.read("rg")
    assert reread is not None
    assert receipts.drifted(reread) == ()


def test_update_service_refuses_a_drifted_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G3: the one mutation gate refuses an installer-owned update while the
    receipt shows drift. The changed file and the receipt stay as they are."""
    tool, method, placed = _yq_with_old_bytes(tmp_path)
    receipts.record(tool, method, package=None, smoke="ok")
    receipt_bytes = receipts.receipt_path("yq").read_bytes()
    placed.write_bytes(b"a local dev build")
    downloads: list[object] = []

    def fake_update(_method: Method, _ctx: object) -> DownloadUpdateExecResult:
        downloads.append(_method)
        placed.write_bytes(b"overwritten")
        return DownloadUpdateExecResult(verified=True, warnings=())

    monkeypatch.setattr(update.download, "update_download", fake_update)
    calls: list[list[str]] = []
    outcome = _service(
        reresolve=lambda _t: _ownership(tool, "installer", method=method),
        runner=calls.append,
    ).run(_target(tool, "installer", method=method))
    assert outcome.status == "unsupported"
    assert outcome.detail == "yq is broken: changed since install"
    assert calls == []
    assert downloads == []
    assert placed.read_bytes() == b"a local dev build"
    assert receipts.receipt_path("yq").read_bytes() == receipt_bytes


def test_all_gone_receipt_does_not_block_an_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every artifact gone is not drift: the update runs and writes the file."""
    tool, method, placed = _yq_with_old_bytes(tmp_path)
    receipts.record(tool, method, package=None, smoke="ok")
    placed.unlink()
    _fake_download_update(monkeypatch, placed, b"restored-yq")
    calls: list[list[str]] = []
    outcome = _service(
        reresolve=lambda _t: _ownership(tool, "installer", method=method),
        runner=calls.append,
    ).run(_target(tool, "installer", method=method))
    assert outcome.status == "updated"
    assert placed.read_bytes() == b"restored-yq"
