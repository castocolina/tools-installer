"""End-to-end policies toggle: drive the real PoliciesScreen through the real
ban_policy closures against a sandboxed HOME, asserting shims + aliases appear on
enable and vanish on disable while the real $HOME is never touched. Saves SVG
screenshots for agent inspection."""

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import DataTable

from installer.doctor import DoctorReport
from installer.guards import REDIRECT_SENTINEL, SHIM_SENTINEL, guard_status
from installer.model import Method, Tool
from installer.policy import ban_policy, daemon_policy, omz_plugins_policy, tweak_policy
from installer.tweaks import BUNDLES, TweakBundle
from installer.uninstall import SweepResult
from installer.wizard_app import (
    PoliciesScreen,
    PolicyInputs,
    UnifiedApp,
    UninstallInputs,
)

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


def _plant_volta_and_pnpm(home: Path) -> Path:
    real_dir = home / "real"
    real_dir.mkdir()
    for name in ("volta", "pnpm"):
        binary = real_dir / name
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
    return real_dir


def _build_real_app(home: Path, *, path_value: str | None = None) -> tuple[UnifiedApp, Path, Path]:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc = home / ".myshellrc"
    policy = ban_policy(
        shim_dir=bin_dir,
        apply_rc_paths=[rc],
        remove_rc_paths=[rc],
        path_value=path_value if path_value is not None else str(bin_dir),
        which=lambda _name: None,
    )
    app = UnifiedApp(
        [_tool()],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
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


async def test_policies_e2e_toggle_round_trip_against_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    home = Path.home()
    real_dir = _plant_volta_and_pnpm(home)
    bin_dir = home / ".local" / "bin"
    app, bin_dir, rc = _build_real_app(home, path_value=f"{bin_dir}:{real_dir}")
    async with app.run_test(size=(100, 30)) as pilot:
        _snapshot(app, "01-open.svg")
        await pilot.press("space")  # enable: writes shims + aliases live
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is True
        status = guard_status(bin_dir)
        assert status == {"npm": True, "pip": True, "pip3": True, "npx": True, "pnpm": True}
        assert REDIRECT_SENTINEL in (bin_dir / "npm").read_text()
        assert REDIRECT_SENTINEL in (bin_dir / "pnpm").read_text()
        assert REDIRECT_SENTINEL in (bin_dir / "npx").read_text()
        assert SHIM_SENTINEL in (bin_dir / "pip").read_text()
        assert SHIM_SENTINEL in (bin_dir / "pip3").read_text()
        assert "alias" in rc.read_text()
        _snapshot(app, "02-enabled.svg")
        await pilot.press("space")  # disable: clears both layers
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is False
        _snapshot(app, "03-disabled.svg")

    assert all(active is False for active in guard_status(bin_dir).values())
    assert not (bin_dir / "npx").exists()
    assert not (bin_dir / "pnpm").exists()
    assert "alias" not in rc.read_text()


async def test_policies_e2e_volta_absent_leaves_pnpm_unshimmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, bin_dir, rc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("space")
        assert isinstance(app.screen, PoliciesScreen)
        status = guard_status(bin_dir)
        assert status["npm"] is True
        assert status["pip"] is True
        assert status["pip3"] is True
        assert status["npx"] is True
        assert status["pnpm"] is False
        assert SHIM_SENTINEL in (bin_dir / "npm").read_text()
        assert not (bin_dir / "pnpm").exists()
        await pilot.press("space")

    assert all(active is False for active in guard_status(bin_dir).values())
    assert "alias" not in rc.read_text()


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
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
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
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
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


def _omz_app(home: Path, *, present: bool, zshrc_text: str) -> tuple[UnifiedApp, Path]:
    zshrc = home / ".zshrc"
    zshrc.write_text(zshrc_text)
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    policy = omz_plugins_policy(zshrc_path=zshrc, state_path=home / ".myshellrc", present=present)
    app = UnifiedApp(
        [_tool()],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    return app, zshrc


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
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
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


class _FakeDaemonRun:
    """Records every argv; never touches real launchctl."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)


def _daemon_app(home: Path, *, installed_tools: dict[str, bool]) -> tuple[UnifiedApp, Path]:
    plist_path = home / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    log_path = home / "Logs" / "prune-daemon.log"
    wrapper_bin_dir = home / ".local" / "bin"
    script_path = home / "scripts" / "prune-user-tmpdir.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    policy = daemon_policy(
        plist_path=plist_path,
        log_path=log_path,
        wrapper_bin_dir=wrapper_bin_dir,
        script_path=script_path,
        state_path=home / ".myshellrc",
        installed_tools=installed_tools,
        path_value="/usr/bin:/bin",
        tmpdir_value=str(home / "tmp"),
        home_value=str(home),
        uv_path=home / "uv",  # fake, absolute -- the fake run never executes it
        uid=501,
        run=_FakeDaemonRun(),
    )
    app = UnifiedApp(
        [_tool()],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_state=lambda: (guard_status(wrapper_bin_dir), None),
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[],
            ban_names=list,
            has_path_block=lambda: False,
            remove=lambda _d: SweepResult(),
        ),
        policies=PolicyInputs(policies=[policy]),
        initial_view="policies",
    )
    return app, plist_path


async def test_daemon_policy_toggles_on_despite_missing_fd_and_rg_with_recommended_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    app, plist_path = _daemon_app(Path.home(), installed_tools={"fd": False, "rg": False})
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PoliciesScreen)
        table = screen.query_one(DataTable[Any])
        requires_cell = table.get_cell("daemon:prune-tmpdir", "requires").plain
        assert requires_cell == "recommended: fd, rg"
        assert "Recommended tool(s): fd, rg. Not required — apply still runs and falls back" in (
            screen.detail_text
        )
        assert "missing:" not in requires_cell
        assert "Missing required tool(s)" not in screen.detail_text
        assert "before enabling" not in screen.detail_text

        await pilot.press("space")
        await pilot.pause()
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is True
        assert plist_path.exists()  # concrete proof apply() actually ran

        await pilot.press("space")
        await pilot.pause()
        assert isinstance(screen, PoliciesScreen)
        assert screen.active_state["daemon:prune-tmpdir"] is False
        assert not plist_path.exists()
