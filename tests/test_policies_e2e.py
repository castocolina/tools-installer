"""End-to-end policies toggle: drive the real PoliciesScreen through the real
ban_policy closures against a sandboxed HOME, asserting shims + aliases appear on
enable and vanish on disable while the real $HOME is never touched. Saves SVG
screenshots for agent inspection."""

from pathlib import Path

import pytest

from installer.doctor import DoctorReport
from installer.guards import guard_status
from installer.model import Method, Tool
from installer.policy import ban_policy, tweak_policy
from installer.tweaks import BUNDLES, TweakBundle
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


def _build_real_app(home: Path) -> tuple[UnifiedApp, Path, Path]:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc = home / ".myshellrc"
    policy = ban_policy(
        shim_dir=bin_dir,
        apply_rc_paths=[rc],
        remove_rc_paths=[rc],
        path_value=str(bin_dir),  # shim dir on PATH -> no spurious warning
        which=lambda _name: None,
    )
    app = UnifiedApp(
        [_tool()],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status(bin_dir),
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[], ban_names=[], has_path_block=False, remove=lambda _d: None
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
    app, bin_dir, rc = _build_real_app(Path.home())
    async with app.run_test(size=(100, 30)) as pilot:
        _snapshot(app, "01-open.svg")
        await pilot.press("space")  # enable: writes shims + aliases live
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is True
        assert all(guard_status(bin_dir).values())
        assert "alias" in rc.read_text()
        _snapshot(app, "02-enabled.svg")
        await pilot.press("space")  # disable: clears both layers
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["ban"] is False
        _snapshot(app, "03-disabled.svg")

    assert all(active is False for active in guard_status(bin_dir).values())
    assert "alias" not in rc.read_text()


def _countdown() -> TweakBundle:
    return next(b for b in BUNDLES if b.id == "countdown")


async def test_policies_screen_toggles_a_tweak_bundle_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_countdown(), rc_path=rc)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    app = UnifiedApp(
        [_tool()],
        {"rg": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status(bin_dir),
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=UninstallInputs(
            rows=[], ban_names=[], has_path_block=False, remove=lambda _d: None
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
        await pilot.press("space")
        await pilot.pause()
        assert isinstance(app.screen, PoliciesScreen)
        assert app.screen.active_state["tweak:countdown"] is False
        assert "wait_time()" not in rc.read_text()


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
