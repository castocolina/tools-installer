"""End-to-end uninstall: drive the real UnifiedApp through the real removal
core against a sandboxed HOME, asserting real artifacts are deleted while the
real $HOME is never touched. Saves an SVG screenshot for agent inspection."""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from installer.agent_settings import apply_setting, ledger_summary
from installer.app import HOST_SETTINGS_OS, UninstallDecision, perform_uninstall
from installer.doctor import DoctorReport
from installer.download import artifact_paths
from installer.guards import guard_status, install_shims, write_ban_aliases
from installer.model import Method, Tool
from installer.ownership import ManagerInventory
from installer.platform import Platform
from installer.policy import omz_plugins_policy, tweak_policy
from installer.shellrc import has_managed_block, write_myshellrc
from installer.tweaks import BUNDLES
from installer.uninstall import SweepResult, active_tweak_ids, plan_removal, removal_plan
from installer.version_status import VersionRefreshService
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs, UninstallScreen
from tests.screen_family import settle
from tests.state_doubles import frozen_service, pass_state, removable_state
from tests.test_uninstall import plant_receipted_tool


def _no_removal_runner(cmd: list[str]) -> None:
    raise AssertionError(f"no removal command expected: {cmd}")


_LINUX = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)

_ARTIFACTS = Path(__file__).resolve().parent.parent / ".e2e-artifacts"
_UX = _ARTIFACTS / "ux"


def _dl_tool() -> Tool:
    return Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),
        ),
    )


def _fd_service(
    home: Path, bin_dir: Path, previewed_extra: tuple[Path, ...] = ()
) -> VersionRefreshService:
    """A service whose one published state carries the REAL removal proof over
    the tree planted under `home`, plus `previewed_extra`: paths an earlier
    plan of the tool named that its current plan no longer does."""
    tool = _dl_tool()
    plan = plan_removal([tool], bin_dir)
    plan = replace(plan, removable=plan.removable + previewed_extra)
    service = frozen_service(home)
    service.publish([pass_state(tool, platform=_LINUX, removable=plan)])
    return service


def _build_real_app(
    home: Path, previewed_extra: tuple[Path, ...] = ()
) -> tuple[UnifiedApp, Path, Path, Path]:
    bin_dir = home / ".local" / "bin"
    opt = home / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    myshellrc = home / ".myshellrc"
    install_shims(bin_dir)
    write_ban_aliases(myshellrc)
    write_myshellrc([bin_dir], myshellrc)

    service = _fd_service(home, bin_dir, previewed_extra)

    def _remove(decision: UninstallDecision) -> SweepResult:
        return perform_uninstall(
            decision,
            bin_dir=bin_dir,
            myshellrc_path=myshellrc,
            rc_paths=[myshellrc],
            bundles=(),
            zshrc_path=home / ".zshrc",
            daemon_policy=None,
            extra_policies=(),
            runner=_no_removal_runner,
            catalog=decision.tools,
        )

    inputs = UninstallInputs(
        ban_names=lambda: [name for name, active in guard_status(bin_dir).items() if active],
        has_path_block=lambda: has_managed_block(myshellrc),
        remove=_remove,
    )
    app = UnifiedApp(
        [_dl_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        policies=PolicyInputs(policies=[]),
        initial_view="uninstall",
        version_refresh=service,
    )
    return app, opt, bin_dir, myshellrc


def _build_real_app_with_tweaks(home: Path) -> tuple[UnifiedApp, Path, Path, Path, Path]:
    bin_dir = home / ".local" / "bin"
    opt = home / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("binary")
    (bin_dir / "fd").symlink_to(opt / "fd")
    myshellrc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    install_shims(bin_dir)
    write_ban_aliases(myshellrc)
    write_myshellrc([bin_dir], myshellrc)
    countdown = next(bundle for bundle in BUNDLES if bundle.id == "countdown")
    tweak_policy(countdown, rc_path=myshellrc, bin_dir=bin_dir).apply()
    # Enable the Oh-My-Zsh policy for real rather than seeding the array by
    # hand: the sweep removes what this installer recorded adding, and a
    # hand-seeded array is by definition not that (CR-01). `kubectl` is the
    # user's own and must survive; `git` was already there and is not ours.
    zshrc.write_text("plugins=(git kubectl)\nsource $ZSH/oh-my-zsh.sh\n")
    omz_plugins_policy(zshrc_path=zshrc, state_path=myshellrc, present=True).apply()

    service = _fd_service(home, bin_dir)

    def tweak_ids() -> tuple[str, ...]:
        return active_tweak_ids(BUNDLES, rc_path=myshellrc, bin_dir=bin_dir, zshrc_path=zshrc)

    def _remove(decision: UninstallDecision) -> SweepResult:
        return perform_uninstall(
            decision,
            bin_dir=bin_dir,
            myshellrc_path=myshellrc,
            rc_paths=[myshellrc],
            bundles=BUNDLES,
            zshrc_path=zshrc,
            daemon_policy=None,
            extra_policies=(),
            runner=_no_removal_runner,
            catalog=decision.tools,
        )

    inputs = UninstallInputs(
        ban_names=lambda: [name for name, active in guard_status(bin_dir).items() if active],
        has_path_block=lambda: has_managed_block(myshellrc),
        remove=_remove,
        tweak_ids=tweak_ids,
    )
    app = UnifiedApp(
        [_dl_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        policies=PolicyInputs(policies=[]),
        initial_view="uninstall",
        version_refresh=service,
    )
    return app, opt, bin_dir, myshellrc, zshrc


def _snapshot(app: UnifiedApp, name: str) -> None:
    _UX.mkdir(parents=True, exist_ok=True)
    (_UX / name).write_text(app.export_screenshot())


def _error_app(home: Path) -> UnifiedApp:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").write_text("x")

    def _boom(_decision: UninstallDecision) -> SweepResult:
        raise OSError("permission denied")

    service = frozen_service(home)
    service.publish([removable_state(_dl_tool(), [bin_dir / "fd"])])
    inputs = UninstallInputs(
        ban_names=list,
        has_path_block=lambda: False,
        remove=_boom,
    )
    return UnifiedApp(
        [_dl_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: ({}, None),
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        policies=PolicyInputs(policies=[]),
        initial_view="uninstall",
        version_refresh=service,
    )


async def test_uninstall_e2e_removes_everything_against_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sandbox HOME so installer.locations.opt_dir() resolves inside tmp_path and
    # the real $HOME is never touched. Derive home from Path.home() so the opt
    # path the removal core computes matches the one we created on disk.
    monkeypatch.setenv("HOME", str(tmp_path))
    app, opt, bin_dir, myshellrc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")  # select all: tool + ban + PATH block
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm: apply live against the sandbox
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        _ARTIFACTS.mkdir(exist_ok=True)
        (_ARTIFACTS / "uninstall.svg").write_text(app.export_screenshot())

    assert not opt.exists()
    assert not (bin_dir / "fd").exists()
    assert all(active is False for active in guard_status(bin_dir).values())
    assert has_managed_block(myshellrc) is False
    assert "alias" not in myshellrc.read_text()


async def test_uninstall_ux_journey_captures_each_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, _opt, _bin_dir, _myshellrc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        _snapshot(app, "01-open.svg")
        await pilot.press("enter")  # nothing selected -> refusal
        assert isinstance(app.screen, UninstallScreen)
        assert "at least one" in app.screen.status.text
        _snapshot(app, "02-empty-refusal.svg")
        await pilot.press("a")
        _snapshot(app, "03-selected.svg")
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.pause()
        _snapshot(app, "04-modal.svg")
        await pilot.press("enter")  # confirm: apply live
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        _snapshot(app, "05-applied.svg")

    err = _error_app(tmp_path / "home2")
    async with err.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")  # accept → confirmation modal
        await pilot.press("enter")  # confirm → removal raises -> error must render, not crash
        await settle(err, pilot)
        assert isinstance(err.screen, UninstallScreen)
        assert err.screen.error is not None
        _snapshot(err, "06-error.svg")


async def test_uninstall_e2e_also_sweeps_tweaks_against_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, opt, bin_dir, myshellrc, zshrc = _build_real_app_with_tweaks(Path.home())
    helper = bin_dir / "tools-installer-wait-time"
    assert helper.exists()
    assert "wait_time()" in myshellrc.read_text()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True

    assert not opt.exists()
    assert not (bin_dir / "fd").exists()
    assert not helper.exists()
    assert "wait_time()" not in myshellrc.read_text()
    plugins = zshrc.read_text().split("\n", 1)[0]
    # Only `docker` was ever ours; the names the user wrote are untouched.
    assert plugins == "plugins=(git kubectl)"


async def test_a_tool_whose_plan_dropped_a_previewed_path_is_not_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-14: the preview named a path the tool's plan no longer names (its
    receipt was rewritten before the confirm). The tool is `remove failed`,
    nothing of it is deleted, and the path is named on the status once."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    stale = home / ".local" / "bin" / "fd-previous"
    app, opt, bin_dir, _myshellrc = _build_real_app(home, previewed_extra=(stale,))
    stale.write_text("an older copy")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "1 remove failed" in status
        assert not status.startswith("1 removed")
        assert status.count(f"changed since the preview; not removed: {stale}") == 1
    assert stale.exists()
    assert (bin_dir / "fd").is_symlink()
    assert opt.exists()


async def test_a_tool_only_refusal_is_on_the_status_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-14: a refused path is named on the status whether or not shell
    tweaks were selected, and exactly once."""
    monkeypatch.setenv("HOME", str(tmp_path))
    app, _opt, bin_dir, _myshellrc = _build_real_app(Path.home())
    (bin_dir / "fd").unlink()
    (bin_dir / "fd").write_text("foreign file")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        status = app.screen.status.text
        assert "1 remove failed" in status
        assert status.count(f"changed since the preview; not removed: {bin_dir / 'fd'}") == 1
    assert (bin_dir / "fd").read_text() == "foreign file"


def _brew_gh() -> Tool:
    return Tool(
        id="gh",
        name="gh",
        category="dev",
        cmd="gh",
        methods=(Method(kind="brew", params={"formula": "gh"}),),
    )


def _reads(formulae: dict[str, str] | None) -> Callable[..., ManagerInventory]:
    """An inventory reader that lists `formulae` and nothing else."""

    def read(**_kw: object) -> ManagerInventory:
        return _inventory(formulae=formulae)

    return read


def _inventory(*, formulae: dict[str, str] | None) -> ManagerInventory:
    return ManagerInventory(
        brew_formulae=formulae,
        brew_casks={},
        pnpm_globals=frozenset(),
        uv_tools={},
        brew_prefix=None,
    )


_MAC_BREW = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


@pytest.mark.parametrize(
    ("repair", "present", "formulae"),
    [
        pytest.param(True, True, {"gh": "2.60.0"}, id="repair-of-a-listed-package"),
        pytest.param(False, False, {"gh": "2.60.0"}, id="presence-miss-of-a-listed-package"),
        pytest.param(False, False, None, id="presence-miss-with-an-unreadable-inventory"),
    ],
)
def test_a_package_already_in_the_manager_gets_no_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repair: bool,
    present: bool,
    formulae: dict[str, str] | None,
) -> None:
    from installer import receipts
    from installer.engine import install_tool
    from installer.enums import InstallStatus
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))  # no host gh for the smoke check
    tool = _brew_gh()
    calls: list[list[str]] = []
    outcome = install_tool(
        tool,
        _MAC_BREW,
        calls.append,
        repair=repair,
        present=lambda _tool: present,
        read_inventory_fn=_reads(formulae),
    )
    assert outcome.status is InstallStatus.INSTALLED
    assert calls == [["brew", "install", "gh"]]
    assert not receipts.receipt_exists("gh")
    plan = removal_plan(tool, tmp_path / ".local" / "bin")
    assert (plan.level, plan.argv) == ("none", ())
    result = perform_uninstall(
        UninstallDecision(tools=(tool,), paths={}, remove_ban=False, remove_path_block=False),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        runner=_no_removal_runner,
        catalog=(tool,),
        extra_policies=(),
    )
    assert "gh" not in result.removed


def test_a_repair_keeps_the_installers_own_package_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.engine import install_tool
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    tool = _brew_gh()
    install_tool(
        tool,
        _MAC_BREW,
        lambda _cmd: None,
        present=lambda _tool: False,
        read_inventory_fn=_reads({}),
    )
    first = receipts.read("gh")
    assert first is not None
    assert first.package == "gh"
    install_tool(
        tool,
        _MAC_BREW,
        lambda _cmd: None,
        repair=True,
        present=lambda _tool: True,
        read_inventory_fn=_reads({"gh": "2.60.0"}),
    )
    plan = removal_plan(tool, tmp_path / ".local" / "bin")
    assert (plan.level, plan.argv) == ("manager", ("brew", "uninstall", "gh"))


def test_a_declared_path_present_before_the_install_is_never_adopted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.engine import install_tool
    from installer.enums import InstallStatus
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    helper = bin_dir / "t-helper"
    helper.write_text("a user file, present before the install")
    method = Method(
        kind="script",
        params={
            "url": "https://example.invalid/t.sh",
            "paths": ["~/.local/bin/t", "~/.local/bin/t-helper"],
        },
    )
    tool = Tool(id="t", name="t", category="dev", cmd="t", methods=(method,))

    def vendor_install(_cmd: list[str]) -> None:
        (bin_dir / "t").write_text("t binary")

    outcome = install_tool(tool, _LINUX, vendor_install, present=lambda _tool: False)
    assert outcome.status is InstallStatus.INSTALLED
    assert receipts.read("t") is not None
    plan = removal_plan(tool, bin_dir)
    assert helper in plan.yourself
    assert helper not in plan.removable
    result = perform_uninstall(
        UninstallDecision(
            tools=(tool,),
            paths={"t": plan.removable},
            remove_ban=False,
            remove_path_block=False,
        ),
        bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        runner=_no_removal_runner,
        catalog=(tool,),
        extra_policies=(),
    )
    assert result.removed == ("t",)
    assert not (bin_dir / "t").exists()
    assert helper.read_text() == "a user file, present before the install"


def _plant(method: Method, bin_dir: Path) -> None:
    """What a successful download, app or script install leaves at its artifact paths."""
    arts = artifact_paths(method, bin_dir)
    dirs = [art.path for art in arts if art.kind == "dir"]
    for art in arts:
        if art.kind == "dir" and method.kind == "app":
            (art.path / "Contents" / "MacOS").mkdir(parents=True)
            (art.path / "Contents" / "Info.plist").write_bytes(b"<plist/>")
            (art.path / "Contents" / "MacOS" / str(method.params["cli"])).write_text("x")
        elif art.kind == "dir":
            art.path.mkdir(parents=True)
            (art.path / str(method.params["member"])).write_text("x")
        elif art.kind == "link":
            art.path.parent.mkdir(parents=True, exist_ok=True)
            target = (
                dirs[0] / "Contents" / "MacOS" / str(method.params["cli"])
                if method.kind == "app"
                else dirs[0] / str(method.params["member"])
            )
            art.path.symlink_to(target)
        else:  # a raw file or a script's leaf
            art.path.parent.mkdir(parents=True, exist_ok=True)
            art.path.write_text("x")


_KIND_METHODS = [
    pytest.param(
        Method(kind="github_release", params={"repo": "a/kt", "asset": "x", "member": "kt"}),
        id="github_release",
    ),
    pytest.param(
        Method(kind="tarball", params={"url": "https://example.invalid/kt.tgz", "member": "kt"}),
        id="tarball",
    ),
    pytest.param(
        Method(kind="app", params={"app": "Kt.app", "cli": "kt"}),
        id="app",
    ),
    pytest.param(
        Method(
            kind="script",
            params={"url": "https://example.invalid/kt.sh", "paths": ["~/.local/bin/kt-s"]},
        ),
        id="script",
    ),
    pytest.param(Method(kind="brew", params={"formula": "kt"}), id="brew"),
    pytest.param(Method(kind="cask", params={"cask": "kt-cask"}), id="cask"),
    pytest.param(Method(kind="uv-tool", params={"pypi_pkg": "kt"}), id="uv-tool"),
    pytest.param(Method(kind="node", params={"npm_pkg": "@a/kt"}), id="node"),
]


@pytest.mark.parametrize("method", _KIND_METHODS)
def test_every_receipt_kind_installs_and_removes_in_both_directions(
    method: Method, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import app as app_module
    from installer import engine, receipts
    from installer.engine import install_tool
    from installer.enums import InstallStatus
    from installer.model import method_package
    from installer.uninstall import MANAGER_UNINSTALL_ARGV, removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))  # no host binary for any smoke
    monkeypatch.setattr(app_module, "real_pnpm", lambda: "/fake/pnpm")
    bin_dir = tmp_path / ".local" / "bin"
    tool = Tool(id="kt", name="kt", category="dev", cmd="kt", methods=(method,))
    calls: list[list[str]] = []

    def fake_perform(
        _tool: Tool, _method: Method, ctx: object
    ) -> tuple[bool, str | None, tuple[str, ...]]:
        if method.kind in MANAGER_UNINSTALL_ARGV:
            # The manager's own install command, recorded, never run.
            calls.append(["install", str(method_package(method))])
        else:
            _plant(method, bin_dir)
        return False, None, ()

    monkeypatch.setattr(engine, "_perform", fake_perform)
    for _round in range(2):  # install and remove, then the same again
        outcome = install_tool(
            tool,
            _MAC_BREW,
            calls.append,
            present=lambda _tool: False,
            read_inventory_fn=_reads({}),
        )
        assert outcome.status is InstallStatus.INSTALLED
        receipt = receipts.read("kt")
        assert receipt is not None
        plan = removal_plan(tool, bin_dir)
        assert plan.level != "none"
        proven = [artifact.path for artifact in receipt.artifacts]
        result = perform_uninstall(
            UninstallDecision(
                tools=(tool,),
                paths={tool.id: plan.removable},
                argv={tool.id: plan.argv},
                remove_ban=False,
                remove_path_block=False,
            ),
            bin_dir=bin_dir,
            myshellrc_path=tmp_path / ".myshellrc",
            rc_paths=[],
            bundles=(),
            zshrc_path=tmp_path / ".zshrc",
            daemon_policy=None,
            runner=calls.append,
            catalog=(tool,),
            extra_policies=(),
        )
        assert result.removed == ("kt",)
        assert not receipts.receipt_exists("kt")
        for path in proven:
            assert not path.is_symlink() and not path.exists()
        if method.kind in MANAGER_UNINSTALL_ARGV:
            assert calls[-1][1:] == list(plan.argv[1:])


def test_removing_codegraph_unregisters_exactly_the_recorded_hosts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC R1: the undo runs first, for the recorded hosts only, while the link still exists."""
    from installer import postinstall, receipts
    from installer.app import remove_tool
    from installer.uninstall import removal_plan
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setenv("HOME", str(tmp_path))
    # opencode is present on this machine but its hook never recorded it: removal must not reach it.
    monkeypatch.setattr(
        postinstall, "present_hosts", lambda: frozenset({"claude", "codex", "opencode"})
    )
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    link = bin_dir / "codegraph"
    plan = removal_plan(tool, bin_dir, verify=True)
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        assert link.is_symlink(), "the undo must run while the proven link still exists"
        calls.append(cmd)

    outcome = remove_tool(
        tool,
        paths=plan.removable,
        argv=plan.argv,
        bin_dir=bin_dir,
        runner=runner,
        unregister=plan.unregister,
    )
    assert calls == [
        [
            str(link),
            "uninstall",
            "--target",
            "claude,codex",
            "--location",
            "global",
            "--yes",
            "--keep-cli",
        ]
    ]
    assert (outcome.removed, outcome.unregistered) == (True, ("claude", "codex"))
    for path in plan.removable:
        assert not path.is_symlink() and not path.exists()
    assert not receipts.receipt_exists("codegraph")


def _claude_settings(home: Path) -> Path:
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    return settings


def _remove_claude(home: Path, *, moved: bool = False) -> SweepResult:
    """Remove a receipt-proven claude through perform_uninstall, as the Uninstall view does.
    `moved` removes the previewed link first, so the fresh plan no longer matches the preview."""
    bin_dir = home / ".local" / "bin"
    tool = plant_receipted_tool(home, "claude")
    plan = removal_plan(tool, bin_dir)
    if moved:
        (bin_dir / "claude").unlink()
    return perform_uninstall(
        UninstallDecision(
            tools=(tool,),
            paths={tool.id: plan.removable},
            argv={tool.id: plan.argv},
            remove_ban=False,
            remove_path_block=False,
        ),
        bin_dir=bin_dir,
        myshellrc_path=home / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=home / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=(tool,),
        platform_os="linux",
    )


def test_removing_claude_reverts_its_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tracer (23-15): removing an agent takes back exactly the keys the installer wrote."""
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = _claude_settings(tmp_path)
    settings.write_bytes(b'{\n  "theme": "dark"\n}\n')
    before = settings.read_bytes()
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os="linux")
    result = _remove_claude(tmp_path)
    assert result.removed == ("claude",)
    assert settings.read_bytes() == before
    assert ledger_summary("claude", home=tmp_path, platform_os="linux") == ()
    assert result.settings_reverted == ("claude",)


def test_a_key_changed_since_is_kept_and_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key the user changed since the installer wrote it keeps the user's value and is named."""
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = _claude_settings(tmp_path)
    settings.write_text('{"theme": "dark"}\n')
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os="linux")
    changed = {
        "theme": "dark",
        "permissions": {"defaultMode": "acceptEdits"},
        "skipDangerousModePermissionPrompt": True,
    }
    settings.write_text(json.dumps(changed))
    result = _remove_claude(tmp_path)
    assert result.settings_kept == ("claude",)
    assert json.loads(settings.read_text()) == {
        "theme": "dark",
        "permissions": {"defaultMode": "acceptEdits"},
    }


def test_an_unparsable_settings_file_is_a_removal_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unparsable settings file never blocks the removal; it is left byte-identical and named."""
    from installer import receipts

    monkeypatch.setenv("HOME", str(tmp_path))
    settings = _claude_settings(tmp_path)
    settings.write_text('{"theme": "dark"}\n')
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os="linux")
    settings.write_text('{"theme": ')
    before = settings.read_bytes()
    result = _remove_claude(tmp_path)
    assert result.removed == ("claude",)
    assert not receipts.receipt_exists("claude")
    assert settings.read_bytes() == before
    assert any(
        warning.startswith("could not revert ~/.claude/settings.json — not valid JSON (line ")
        for warning in result.warnings
    )


def test_a_failed_removal_reverts_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A removal that is refused leaves the settings and the ledger exactly as they were."""
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = _claude_settings(tmp_path)
    settings.write_text('{"theme": "dark"}\n')
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os="linux")
    before = settings.read_bytes()
    result = _remove_claude(tmp_path, moved=True)
    assert result.removed == ()
    assert result.remove_failed
    assert result.settings_reverted == ()
    assert settings.read_bytes() == before
    assert ledger_summary("claude", home=tmp_path, platform_os="linux") != ()


async def test_the_settings_pseudo_row_is_selected_and_refuses_c(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O5: the environment row shows the ledgered files, refuses `c`, and reverts every key."""
    monkeypatch.setenv("HOME", str(tmp_path))
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os=HOST_SETTINGS_OS)
    apply_setting("vscode", "vscode-ai-off", home=tmp_path, platform_os=HOST_SETTINGS_OS)
    app, _opt, _bin_dir, _myshellrc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        # From the first row down: fd, the environment title, the PATH wiring row, then this row.
        await pilot.press("down", "down", "down", "down")
        assert screen.detail_text == (
            "reverts only keys that still hold this installer's value: "
            "~/.claude/settings.json, ~/.config/Code/User/settings.json"
        )
        await pilot.press("c")
        assert screen.status.text == "This row has no config to delete."
        await pilot.press("a")  # select all: the tool, the PATH block and the settings row
        await pilot.press("enter")  # accept -> confirmation modal
        await pilot.press("enter")  # confirm: apply live
        await settle(app, pilot)
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
    assert ledger_summary("claude", home=tmp_path, platform_os=HOST_SETTINGS_OS) == ()
    assert ledger_summary("vscode", home=tmp_path, platform_os=HOST_SETTINGS_OS) == ()


async def test_the_settings_row_is_absent_without_a_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, _opt, _bin_dir, _myshellrc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, UninstallScreen)
        await pilot.press("down", "down", "down", "down", "down")  # clamps at the last row
        assert "reverts only keys" not in screen.detail_text
