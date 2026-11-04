"""End-to-end uninstall: drive the real UnifiedApp through the real removal
core against a sandboxed HOME, asserting real artifacts are deleted while the
real $HOME is never touched. Saves an SVG screenshot for agent inspection."""

from dataclasses import replace
from pathlib import Path

import pytest

from installer.app import UninstallDecision, perform_uninstall
from installer.doctor import DoctorReport
from installer.guards import guard_status, install_shims, write_ban_aliases
from installer.model import Method, Tool
from installer.platform import Platform
from installer.policy import omz_plugins_policy, tweak_policy
from installer.shellrc import has_managed_block, write_myshellrc
from installer.tweaks import BUNDLES
from installer.uninstall import SweepResult, active_tweak_ids, plan_removal
from installer.version_status import VersionRefreshService
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs, UninstallScreen
from tests.screen_family import settle
from tests.state_doubles import frozen_service, pass_state, removable_state


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
