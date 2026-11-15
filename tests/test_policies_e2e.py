"""End-to-end policies screen: drive the real PoliciesScreen through real policy
closures against a sandboxed HOME while the real $HOME is never touched. Saves SVG
screenshots for agent inspection."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from textual.binding import Binding
from textual.widgets import DataTable

from installer.catalog_tui import RefreshRequested
from installer.doctor import DoctorReport
from installer.enums import Severity
from installer.modals import LinkModeScreen
from installer.model import Method, Tool
from installer.policies_screen import PoliciesScreen, PolicyInputs
from installer.policy import (
    Policy,
    PolicyResult,
    omz_plugins_policy,
    tweak_policy,
)
from installer.tweaks import BUNDLES, TweakBundle, shell_init_bundle, tweak_present
from installer.ui_common import VIEW_BY_NAME, FooterBar, highlighted_key
from installer.uninstall import SweepResult
from installer.wizard_app import UnifiedApp, UninstallInputs
from tests.policy_doubles import block_policy
from tests.screen_family import settle
from tests.state_doubles import FrozenStateService, absent_state, frozen_service, plan_state

_ARTIFACTS = Path(__file__).resolve().parent.parent / ".e2e-artifacts"
_UX = _ARTIFACTS / "policies"


def _tool() -> Tool:
    return Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "rg"}),),
    )


def _build_real_app(home: Path) -> tuple[UnifiedApp, Path, Path]:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc = home / ".myshellrc"
    policy = block_policy(
        apply_rc_paths=[rc],
        remove_rc_paths=[rc],
    )
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    return app, bin_dir, rc


def _snapshot(app: UnifiedApp, name: str) -> None:
    _UX.mkdir(parents=True, exist_ok=True)
    (_UX / name).write_text(app.export_screenshot())


def _countdown() -> TweakBundle:
    return next(b for b in BUNDLES if b.id == "countdown")


async def test_policies_screen_toggles_a_tweak_bundle_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    policy = tweak_policy(
        _countdown(),
        rc_path=rc,
        bin_dir=bin_dir,
        installed_tools={"uv": True},
    )
    helper = bin_dir / "tools-installer-wait-time"
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["tweak:countdown"] is False
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["tweak:countdown"] is True
        assert "wait_time()" in rc.read_text()
        assert helper.exists()
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["tweak:countdown"] is False
        assert "wait_time()" not in rc.read_text()
        assert not helper.exists()


def test_real_home_rc_files_are_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Even constructing the sandbox app must resolve every path inside the
    # sandbox HOME, never the real one. Assert the artifacts it touches all live
    # under tmp_path -- a regression that leaked a real-home path fails here.
    monkeypatch.setenv("HOME", str(tmp_path))
    assert Path.home() == tmp_path
    _app, bin_dir, rc = _build_real_app(Path.home())
    assert bin_dir.is_relative_to(tmp_path)
    assert rc.is_relative_to(tmp_path)
    assert bin_dir.exists()  # the one on-disk write so far landed in the sandbox


_ZSHRC_OMZ = (
    'export ZSH="$HOME/.oh-my-zsh"\n'
    'ZSH_THEME="robbyrussell"\n'
    "plugins=(z sudo)\n"
    "source $ZSH/oh-my-zsh.sh\n"
)


async def test_policies_screen_toggles_omz_plugins_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(_ZSHRC_OMZ)
    (tmp_path / ".oh-my-zsh").mkdir()
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    policy = omz_plugins_policy(zshrc_path=zshrc, state_path=tmp_path / ".myshellrc", present=True)
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["omz-plugins"] is False
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["omz-plugins"] is True
        assert "plugins=(z sudo git docker)" in zshrc.read_text()
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["omz-plugins"] is False
        assert zshrc.read_text() == _ZSHRC_OMZ


def _omz_app(
    home: Path,
    *,
    present: bool | Callable[[], bool],
    zshrc_text: str,
    terminal_sync: Callable[[], str | None] | None = None,
) -> tuple[UnifiedApp, Path]:
    zshrc = home / ".zshrc"
    zshrc.write_text(zshrc_text)
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    policy = omz_plugins_policy(
        zshrc_path=zshrc,
        state_path=home / ".myshellrc",
        present=present,
        terminal_sync=terminal_sync,
    )
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    return app, zshrc


async def test_policies_screen_keeps_omz_on_when_terminal_sync_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    def sync() -> str | None:
        raise OSError("kitty configuration is user-owned")

    app, zshrc = _omz_app(
        tmp_path,
        present=True,
        zshrc_text=_ZSHRC_OMZ,
        terminal_sync=sync,
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        await pilot.press("space")
        await pilot.pause()
        assert app.screen.active_state["omz-plugins"] is True
        assert "Terminal shell synchronization failed: kitty configuration is user-owned" in (
            app.screen.status.text
        )
        assert "plugins=(z sudo git docker)" in zshrc.read_text()


async def test_policies_screen_rechecks_omz_requirement_before_toggle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    present = False
    app, zshrc = _omz_app(tmp_path, present=lambda: present, zshrc_text=_ZSHRC_OMZ)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        table = app.screen.query_one(DataTable[Any])
        assert table.get_cell("omz-plugins", "requires").plain == "missing: oh-my-zsh"
        present = True
        await pilot.press("space")
        await pilot.pause()
        assert app.screen.active_state["omz-plugins"] is True
        assert "plugins=(z sudo git docker)" in zshrc.read_text()


async def test_policies_screen_refuses_omz_toggle_without_oh_my_zsh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, zshrc = _omz_app(tmp_path, present=False, zshrc_text=_ZSHRC_OMZ)
    before = zshrc.read_text()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["omz-plugins"] is False
        assert "oh-my-zsh" in app.screen.status.text
        assert zshrc.read_text() == before


async def test_policies_screen_surfaces_an_unusable_zshrc_as_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    multi = "plugins=(\n  git\n  z\n)\nsource x\n"
    app, zshrc = _omz_app(tmp_path, present=True, zshrc_text=multi)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["omz-plugins"] is False
        assert app.screen.error is not None
        assert zshrc.read_text() == multi


async def test_policy_detail_discloses_the_partial_state_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, _zshrc = _omz_app(tmp_path, present=True, zshrc_text=_ZSHRC_OMZ)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert "Disabling removes only the names this enable actually added" in (
            app.screen.detail_text
        )
        assert "Reads ON only once this installer has enabled it" in app.screen.detail_text


async def test_every_policy_detail_fits_the_panel_at_80_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model string alone (asserted above) cannot catch a panel too short to
    show it -- 03-VERIFICATION.md's gap: `1adcfe4` raised the panel 5->7 after a
    tmux check caught this same clipping once, then `3d1ee1f` lengthened the
    omz-plugins copy with no follow-up check, silently re-clipping it. This
    checks Textual's own computed content height against the panel's real
    allocated height at the narrowest supported terminal width, for every
    policy row -- not just the one this regression happened to hit."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(_ZSHRC_OMZ)
    (tmp_path / ".oh-my-zsh").mkdir()
    policies = [
        tweak_policy(_countdown(), rc_path=rc, bin_dir=bin_dir, installed_tools={"uv": True}),
        omz_plugins_policy(zshrc_path=zshrc, state_path=rc, present=True),
    ]
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=policies),
        initial_view="policies",
    )
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        panel = screen.query_one("#policy-detail")
        for _ in policies:
            # get_content_height is Textual's own wrap calculation for this
            # exact renderable at this exact width -- the true content height,
            # independent of the box the CSS `height:` rule assigns it. This is
            # what silently clips when it exceeds panel.size.height; a plain
            # Static's `virtual_size` does NOT reflect this (confirmed: it
            # still read the assigned box height even with the old, too-short
            # `height: 7`, so it could not have caught this regression).
            needed = panel.get_content_height(
                panel.container_size, panel.container_size, panel.content_size.width
            )
            assert needed <= panel.size.height, (
                f"{screen.detail_text!r} needs {needed} rows at 80 columns, "
                f"panel only allocates {panel.size.height}"
            )
            await pilot.press("down")
            await pilot.pause()


async def test_cache_redirect_toggles_against_a_sandboxed_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.env_redirect import BUN_CACHE_REDIRECT
    from installer.policy import cache_redirect_policy

    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    conf_dir = home / ".config" / "environment.d"
    redirect = cache_redirect_policy(
        BUN_CACHE_REDIRECT,
        platform_os="linux",
        conf_dir=conf_dir,
        rc_path=home / ".myshellrc",
        home=home,
    )
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(has_path_block=lambda: False, remove=lambda _d: SweepResult()),
        policies=PolicyInputs(policies=[redirect]),
        initial_view="policies",
    )
    conf = conf_dir / BUN_CACHE_REDIRECT.conf_basename
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")
        await settle(app, pilot)
        assert conf.exists()
        assert "tools-installer: cache-redirect" in conf.read_text()
        await pilot.press("space")
        await settle(app, pilot)
        assert not conf.exists()
        assert home == tmp_path
        assert os.environ["HOME"] == str(tmp_path)
        _snapshot(app, "linux-redirect.svg")


async def test_policies_screen_link_mode_change_moves_active_policies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    mode = {"v": "centralized"}
    block = block_policy(
        apply_rc_paths=lambda: [rc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[rc, zshrc, bashrc],
    )
    bundle = next(b for b in BUNDLES if b.id == "docker")
    tweak = tweak_policy(
        bundle,
        rc_path=rc,
        installed_tools={"watch": True},
        ensure_sourced_from=lambda: (zshrc, bashrc) if mode["v"] == "split" else (),
    )
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(
            policies=[block, tweak],
            link_mode=lambda: mode["v"],
            set_link_mode=lambda value: mode.__setitem__("v", value),
        ),
        initial_view="policies",
    )
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")  # enable the block (row 0)
        await settle(app, pilot)
        await pilot.press("down", "space")  # enable the tweak (row 1)
        await settle(app, pilot)
        assert "tools-installer block" in rc.read_text()
        await pilot.press("m")
        await pilot.press("down", "down", "enter")  # pick split
        await pilot.pause()

        assert mode["v"] == "split"
        assert "tools-installer block" not in rc.read_text()
        assert "tools-installer block" in zshrc.read_text()
        assert "tools-installer block" in bashrc.read_text()
        assert "tools-installer tweak:docker" in rc.read_text()
        for split_rc in (zshrc, bashrc):
            assert f'. "{rc}"' in split_rc.read_text()
        assert "Link mode saved: split" in screen.status.text
        assert "Moved: block" in screen.status.text
        assert screen.status.severity == "ok"


def _mode_app(
    home: Path,
    mode: dict[str, str],
    policies: list[Policy],
    *,
    prompt_link_mode: bool = False,
    set_link_mode: Callable[[str], None] | None = None,
) -> UnifiedApp:
    return UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(
            policies=policies,
            link_mode=lambda: mode["v"],
            set_link_mode=(
                set_link_mode
                if set_link_mode is not None
                else (lambda value: mode.__setitem__("v", value))
            ),
        ),
        initial_view="policies",
        prompt_link_mode=prompt_link_mode,
    )


def _test_tweak(home: Path, mode: dict[str, str]) -> Policy:
    rc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    bundle = next(b for b in BUNDLES if b.id == "docker")
    return tweak_policy(
        bundle,
        rc_path=rc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if mode["v"] == "split" else (),
    )


def _test_block(home: Path, mode: dict[str, str]) -> Policy:
    rc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    return block_policy(
        apply_rc_paths=lambda: [rc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[rc, zshrc, bashrc],
    )


async def test_move_link_mode_ignores_policies_that_are_not_link_mode_aware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    calls: list[str] = []

    def recorded(name: str, fn: Callable[[], PolicyResult]) -> Callable[[], PolicyResult]:
        def wrapped() -> PolicyResult:
            calls.append(name)
            return fn()

        return wrapped

    daemon_like = Policy(
        id="daemon",
        label="Daemon",
        description="not link-mode aware",
        active=True,
        apply=recorded("daemon-apply", lambda: PolicyResult((), None, None)),
        remove=recorded("daemon-remove", lambda: PolicyResult((), None, None)),
    )
    mode = {"v": "centralized"}
    block = _test_block(home, mode)
    app = _mode_app(home, mode, [daemon_like, block])
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        screen.active_state["daemon"] = True
        await pilot.press("m", "down", "down", "enter")
        await pilot.pause()

    assert calls == []  # the daemon-like policy was never touched


async def test_first_run_link_mode_picker_moves_active_policies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    rc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    mode = {"v": "centralized"}
    block = block_policy(
        apply_rc_paths=lambda: [rc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[rc, zshrc, bashrc],
    )
    block.apply()  # active before the app is built, so active_state starts True
    block = block_policy(
        apply_rc_paths=lambda: [rc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[rc, zshrc, bashrc],
    )
    app = _mode_app(home, mode, [block], prompt_link_mode=True)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LinkModeScreen)
        await pilot.press("down", "down", "enter")  # pick split
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        assert mode["v"] == "split"
        assert "tools-installer block" not in rc.read_text()
        assert "tools-installer block" in zshrc.read_text()
        assert "tools-installer block" in bashrc.read_text()
        assert "Link mode saved: split" in screen.status.text
        assert "Moved: block" in screen.status.text


async def test_policies_screen_reports_a_failed_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    rc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    mode = {"v": "centralized"}
    block = block_policy(
        apply_rc_paths=lambda: [rc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[rc, zshrc, bashrc],
    )
    tweak = _test_tweak_with_failing_split_apply(home, mode)
    app = _mode_app(home, mode, [block, tweak])
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")
        await settle(app, pilot)
        await pilot.press("down", "space")
        await settle(app, pilot)
        await pilot.press("m", "down", "down", "enter")
        await pilot.pause()

        assert mode["v"] == "split"
        assert "Moved: block" in screen.status.text
        assert "Failed: tweak:docker" in screen.status.text
        assert "apply boom" in screen.status.text
        assert screen.status.severity == "warn"
        assert str(screen.status.severity) != "error"


def _test_tweak_with_failing_split_apply(home: Path, mode: dict[str, str]) -> Policy:
    base = _test_tweak(home, mode)
    rc = home / ".myshellrc"
    bundle = next(b for b in BUNDLES if b.id == "docker")

    def apply() -> PolicyResult:
        if mode["v"] == "split":
            raise OSError("apply boom")
        return tweak_policy(bundle, rc_path=rc).apply()

    return Policy(
        id=base.id,
        label=base.label,
        description=base.description,
        active=base.active,
        apply=apply,
        remove=base.remove,
        is_active=base.is_active,
        link_mode_aware=True,
    )


async def test_policies_screen_shows_lost_policies_off_after_a_failed_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-02: when a move ends with a policy absent from both modes, the
    screen names it in the error and flips its row OFF instead of leaving a
    checkbox that claims a policy that is no longer on disk."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    mode = {"v": "centralized"}
    saves: list[str] = []

    def set_mode(value: str) -> None:
        saves.append(value)
        if len(saves) == 2:  # the restore's set_link_mode(old_mode) save
            raise OSError("settings.json unwritable")
        mode["v"] = value

    block = _test_block(home, mode)
    tweak = _test_tweak_with_failing_split_apply(home, mode)
    app = _mode_app(home, mode, [block, tweak], set_link_mode=set_mode)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")  # enable the block (row 0)
        await settle(app, pilot)
        await pilot.press("down", "space")  # enable the tweak (row 1)
        await settle(app, pilot)
        await pilot.press("m", "down", "down", "enter")  # pick split
        await pilot.pause()

        assert "not restored: tweak:docker" in screen.status.text
        assert screen.status.severity == "error"
        assert screen.active_state["tweak:docker"] is False


async def test_link_mode_change_after_an_uninstall_does_not_resurrect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """opencode H2: the migration set is read from the policies' own on-disk
    activity at the moment of the change, so a block another view (Uninstall)
    removed is not recreated by a link-mode change."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    rc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    mode = {"v": "centralized"}
    block = _test_block(home, mode)
    app = _mode_app(home, mode, [block])
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")  # enable the block
        await settle(app, pilot)
        # what the Uninstall view's sweep leaves on disk, without touching
        # this screen's cached active_state:
        block.remove()
        await pilot.press("m", "down", "down", "enter")  # pick split
        await pilot.pause()

        assert mode["v"] == "split"
        assert "tools-installer block" not in (rc.read_text() if rc.exists() else "")
        assert "tools-installer block" not in (zshrc.read_text() if zshrc.exists() else "")
        assert "tools-installer block" not in (bashrc.read_text() if bashrc.exists() else "")
        assert "Moved" not in screen.status.text


async def test_split_to_centralized_move_reports_the_path_wiring_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """opencode M1: moving the block from split (a copy in each rc) to
    centralized (one in ~/.myshellrc) leaves the block unsourced until
    the PATH wiring is refreshed, so the report names the exact action."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    mode = {"v": "split"}
    block = _test_block(home, mode)
    app = _mode_app(home, mode, [block])
    async with app.run_test(size=(100, 30)) as pilot:
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        await pilot.press("space")  # enable the block
        await settle(app, pilot)
        await pilot.press("m", "enter")  # pick centralized
        await pilot.pause()

        assert mode["v"] == "centralized"
        assert 'make fix ARGS="--link-mode centralized"' in screen.status.text


# -- 21-17: Policies renders live state and prerequisites on every entry --


def _live_app(
    policies: list[Policy],
    *,
    service: FrozenStateService | None = None,
    tools: list[Tool] | None = None,
    uninstall: UninstallInputs | None = None,
) -> UnifiedApp:
    return UnifiedApp(
        tools if tools is not None else [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=uninstall
        or UninstallInputs(has_path_block=lambda: False, remove=lambda _d: SweepResult()),
        policies=PolicyInputs(policies=policies),
        initial_view="policies",
        version_refresh=service,
    )


def _cell(app: UnifiedApp, policy_id: str, column: str) -> str:
    return app.view("policies").query_one(DataTable[Any]).get_cell(policy_id, column).plain


async def test_installing_watch_unblocks_the_docker_tweak(tmp_path: Path) -> None:
    watch = Tool(
        id="watch",
        name="watch",
        category="search",
        cmd="watch",
        methods=(Method(kind="brew", params={"formula": "watch"}),),
    )
    service = frozen_service(tmp_path)
    service.publish([absent_state(watch)])
    docker = next(b for b in BUNDLES if b.id == "docker")
    policy = tweak_policy(
        docker,
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / "bin",
        installed_tools=service.installed_or({"watch": False}),
    )
    app = _live_app([policy], service=service, tools=[watch])
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert "missing: watch" in _cell(app, "tweak:docker", "requires")
        service.queued = (plan_state(watch),)
        app.post_message(RefreshRequested())
        await settle(app, pilot)
        assert "missing" not in _cell(app, "tweak:docker", "requires")


async def test_entering_policies_starts_no_pass(tmp_path: Path) -> None:
    service = frozen_service(tmp_path)
    app = _live_app([], service=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        before = service.passes
        for view in ("system", "policies", "system", "policies"):
            await app.show_view(view)
        await settle(app, pilot)
        assert service.passes == before


class _Read:
    """A live read that answers `value` until `fail` is set, then raises it."""

    def __init__(self, value: Any, error: Exception) -> None:
        self.value = value
        self.error = error
        self.fail = False

    def __call__(self) -> Any:
        if self.fail:
            raise self.error
        return self.value


def _fake_policy(policy_id: str, applied: list[str], **overrides: Any) -> Policy:
    result = PolicyResult(layers=(), reload_hint=None, warning=None)

    def apply() -> PolicyResult:
        applied.append("apply")
        return result

    def remove() -> PolicyResult:
        applied.append("remove")
        return result

    fields: dict[str, Any] = {
        "id": policy_id,
        "label": policy_id,
        "description": "fake",
        "active": True,
        "apply": apply,
        "remove": remove,
    }
    return Policy(**{**fields, **overrides})


async def _reenter(app: UnifiedApp) -> None:
    await app.show_view("system")
    await app.show_view("policies")


_READ_ERROR = "Could not read the policy state: "


async def test_a_failed_policy_read_shows_the_error(tmp_path: Path) -> None:
    read = _Read(True, OSError("permission denied\nsecond line"))
    flaky = _fake_policy("flaky", [], is_active=read)
    steady = _fake_policy("steady", [], is_active=lambda: False)
    app = _live_app([flaky, steady], service=frozen_service(tmp_path))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert _cell(app, "flaky", "state") == "● [on]"
        read.fail = True
        await _reenter(app)
        status = app.view("policies").status
        assert _cell(app, "flaky", "state") == ""
        assert _cell(app, "steady", "state") == "○ [off]"
        assert (status.text, status.severity) == (
            f"{_READ_ERROR}permission denied.",
            Severity.ERROR,
        )
        read.fail = False
        await _reenter(app)
        assert _cell(app, "flaky", "state") == "● [on]"
        assert app.view("policies").status.text == ""


async def test_space_on_an_unreadable_policy_applies_nothing(tmp_path: Path) -> None:
    calls: list[str] = []
    read = _Read(True, OSError("denied"))
    flaky = _fake_policy("flaky", calls, is_active=read)
    service = frozen_service(tmp_path)
    app = _live_app([flaky], service=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        read.fail = True
        await _reenter(app)
        await settle(app, pilot)
        before = service.passes
        await pilot.press("space")
        await settle(app, pilot)
        assert calls == []
        assert app.view("policies").status.text == f"{_READ_ERROR}denied."
        assert service.passes == before + 1


async def test_a_failed_requirements_read_blanks_requires_and_detail(tmp_path: Path) -> None:
    calls: list[str] = []
    needs = _Read(("watch",), OSError("denied\nmore"))
    tool = _fake_policy(
        "tweak:fake",
        calls,
        active=False,
        is_active=lambda: False,
        requires=("watch",),
        missing_requires_now=needs,
    )
    service = frozen_service(tmp_path)
    app = _live_app([tool], service=service)
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert "watch" in _cell(app, "tweak:fake", "requires")
        needs.fail = True
        await _reenter(app)
        await settle(app, pilot)
        screen = app.view("policies")
        assert isinstance(screen, PoliciesScreen)
        assert _cell(app, "tweak:fake", "requires") == ""
        assert "watch" not in screen.detail_text
        assert "Required tool(s)" not in screen.detail_text
        assert (screen.status.text, screen.status.severity) == (
            f"{_READ_ERROR}denied.",
            Severity.ERROR,
        )
        before = service.passes
        await pilot.press("space")
        await settle(app, pilot)
        assert calls == []
        assert service.passes == before + 1
        needs.fail = False
        await _reenter(app)
        assert "watch" in _cell(app, "tweak:fake", "requires")
        assert screen.status.text == ""


async def test_policies_with_no_policy_draws_its_empty_copy(tmp_path: Path) -> None:
    app = _live_app([], service=frozen_service(tmp_path))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        for _ in range(2):
            screen = app.view("policies")
            assert isinstance(screen, PoliciesScreen)
            assert screen.query_one(DataTable[Any]).row_count == 0
            assert screen.detail_text == ""
            assert screen.status.text == ""
            await _reenter(app)


_DRIFT = "Drift: this installer enabled it, but it is not active now. space applies it again."


async def test_an_owned_inactive_policy_reads_drift(tmp_path: Path) -> None:
    applied: list[str] = []
    drifted = _fake_policy(
        "drifted", applied, active=False, is_active=lambda: False, owned=lambda: True
    )
    app = _live_app([drifted], service=frozen_service(tmp_path))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        screen = app.view("policies")
        assert isinstance(screen, PoliciesScreen)
        cell = screen.query_one(DataTable[Any]).get_cell("drifted", "state")
        assert (cell.plain, str(cell.style)) == ("! [drift]", "yellow")
        assert screen.detail_text.splitlines()[0] == _DRIFT
        await pilot.press("space")
        await settle(app, pilot)
        assert applied == ["apply"]


async def test_a_policy_without_owned_never_drifts(tmp_path: Path) -> None:
    plain = _fake_policy("plain", [], active=False, is_active=lambda: False)
    app = _live_app([plain], service=frozen_service(tmp_path))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert _cell(app, "plain", "state") == "○ [off]"


async def test_a_failed_owned_read_shows_the_error(tmp_path: Path) -> None:
    owned = _Read(True, OSError("unreadable state file"))
    owned.fail = True
    broken = _fake_policy("broken", [], is_active=lambda: False, owned=owned)
    app = _live_app([broken], service=frozen_service(tmp_path))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        status = app.view("policies").status
        assert _cell(app, "broken", "state") == ""
        assert (status.text, status.severity) == (
            f"{_READ_ERROR}unreadable state file.",
            Severity.ERROR,
        )


def _settings_app(home: Path, *rows: Policy) -> UnifiedApp:
    return UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=list(rows)),
        initial_view="policies",
    )


def _policies(app: UnifiedApp) -> PoliciesScreen:
    screen = app.screen
    assert isinstance(screen, PoliciesScreen)
    return screen


async def test_a_shell_init_row_toggles_its_bundle_under_a_scratch_rc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard (written after the implementation): space writes and removes the block."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bundle = shell_init_bundle("zoxide")
    assert bundle is not None
    rc = tmp_path / ".myshellrc"
    row = tweak_policy(
        bundle,
        rc_path=rc,
        bin_dir=tmp_path / ".local" / "bin",
        installed_tools={"zoxide": True},
    )
    app = _settings_app(tmp_path, row)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert _cell(app, "tweak:zoxide", "state") == "○ [off]"
        await pilot.press("space")
        await pilot.pause()
        assert tweak_present(bundle, rc)
        assert _cell(app, "tweak:zoxide", "state") == "● [on]"
        await pilot.press("space")
        await pilot.pause()
        assert not tweak_present(bundle, rc)
        assert _cell(app, "tweak:zoxide", "state") == "○ [off]"


@pytest.mark.parametrize(
    "policy_id",
    ["tweak:claude-skip", "tweak:codex-skip", "tweak:opencode-auto", "tweak:cursor-agent-model"],
)
async def test_retired_alias_rows_show_only_the_generic_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy_id: str
) -> None:
    """Regression guard (written after the implementation): the alias copy left the screen."""
    monkeypatch.setenv("HOME", str(tmp_path))
    row = Policy(
        id=policy_id,
        label="retired alias",
        description="alias text",
        active=False,
        apply=lambda: PolicyResult(layers=(), reload_hint=None, warning=None),
        remove=lambda: PolicyResult(layers=(), reload_hint=None, warning=None),
    )
    app = _settings_app(tmp_path, row)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        detail = _policies(app).detail_text
        assert "Space toggles this reversible shell policy." in detail
        assert "dangerously-skip-permissions" not in detail
        assert "dangerously-bypass-approvals" not in detail
        assert "--model gpt-5.6-sol-high" not in detail
        assert "--auto" not in detail


async def test_policies_opens_on_the_first_remaining_row(tmp_path: Path) -> None:
    """Policies opens with the table cursor on the first policy's key."""
    rc = tmp_path / ".myshellrc"
    docker = tweak_policy(
        next(b for b in BUNDLES if b.id == "docker"), rc_path=rc, installed_tools={"watch": True}
    )
    countdown = tweak_policy(
        _countdown(), rc_path=rc, bin_dir=tmp_path / "bin", installed_tools={"uv": True}
    )
    app = _live_app([docker, countdown])
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        table = app.view("policies").query_one(DataTable[Any])
        assert highlighted_key(table) == "tweak:docker"


async def test_policies_has_no_tmp_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC R9, UI-SPEC section 9: the tmp cleanup left Policies. The view lists no such row,
    its footer names no `t` or `l` action, and pressing either on every row opens no modal and
    changes no row."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    block = block_policy(
        apply_rc_paths=[rc],
        remove_rc_paths=[rc],
    )
    tweak = tweak_policy(_countdown(), rc_path=rc, bin_dir=bin_dir, installed_tools={"uv": True})
    app = UnifiedApp(
        [_tool()],
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(has_path_block=lambda: False, remove=lambda _d: SweepResult()),
        policies=PolicyInputs(policies=[block, tweak]),
        initial_view="policies",
    )
    actions = VIEW_BY_NAME["policies"].actions
    assert "set time" not in actions
    assert "view log" not in actions
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        table = screen.query_one(DataTable[Any])
        assert not [key for key in table.rows if "tmp" in str(key.value)]
        before = dict(screen.active_state)
        for row in range(len(screen.active_state)):
            table.move_cursor(row=row)
            for key in ("t", "l"):
                await pilot.press(key)
                await pilot.pause()
                assert app.screen is screen
        assert screen.active_state == before
        assert screen.status.text == ""


def test_policies_bindings_have_no_time_or_log_keys() -> None:
    """UI-SPEC section 9: the Policies screen binds `space` and `m` only; its footer names no
    time or log action."""
    keys = {binding.key for binding in PoliciesScreen.BINDINGS if isinstance(binding, Binding)}
    assert keys == {"space", "m"}
    assert FooterBar("policies").render_text().plain.startswith("space toggle | m link mode   │")
