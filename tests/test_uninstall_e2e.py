"""End-to-end uninstall: drive the real UnifiedApp through the real removal
core against a sandboxed HOME, asserting real artifacts are deleted while the
real $HOME is never touched. Saves an SVG screenshot for agent inspection."""

from pathlib import Path

import pytest

from installer.app import UninstallDecision, perform_uninstall
from installer.doctor import DoctorReport
from installer.guards import guard_status, install_shims, write_ban_aliases
from installer.model import Method, Tool
from installer.shellrc import has_managed_block, write_myshellrc
from installer.uninstall import removable_tools
from installer.wizard_app import PolicyInputs, UnifiedApp, UninstallInputs, UninstallScreen

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


def _build_real_app(home: Path) -> tuple[UnifiedApp, Path, Path, Path]:
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

    removable = removable_tools([_dl_tool()], bin_dir)

    def _remove(decision: UninstallDecision) -> None:
        perform_uninstall(decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[myshellrc])

    inputs = UninstallInputs(
        removable=removable,
        ban_names=[name for name, active in guard_status(bin_dir).items() if active],
        has_path_block=has_managed_block(myshellrc),
        remove=_remove,
    )
    app = UnifiedApp(
        [_dl_tool()],
        {"fd": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status=guard_status(bin_dir),
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        policies=PolicyInputs(policies=[]),
        initial_view="uninstall",
    )
    return app, opt, bin_dir, myshellrc


def _snapshot(app: UnifiedApp, name: str) -> None:
    _UX.mkdir(parents=True, exist_ok=True)
    (_UX / name).write_text(app.export_screenshot())


def _error_app(home: Path) -> UnifiedApp:
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").write_text("x")

    def _boom(_decision: UninstallDecision) -> None:
        raise OSError("permission denied")

    inputs = UninstallInputs(
        removable=[(_dl_tool(), [bin_dir / "fd"])],
        ban_names=[],
        has_path_block=False,
        remove=_boom,
    )
    return UnifiedApp(
        [_dl_tool()],
        {"fd": True},
        {"search": ""},
        report=DoctorReport(missing=(), broken=(), duplicated=()),
        guard_status={},
        guard_warning=None,
        fix_preview="",
        fix=lambda: None,
        uninstall=inputs,
        policies=PolicyInputs(policies=[]),
        initial_view="uninstall",
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
        await pilot.press("enter")  # apply live against the sandbox
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
        assert "at least one" in app.screen.status_text
        _snapshot(app, "02-empty-refusal.svg")
        await pilot.press("a")
        _snapshot(app, "03-selected.svg")
        await pilot.press("enter")  # apply live
        assert isinstance(app.screen, UninstallScreen)
        assert app.screen.applied is True
        _snapshot(app, "04-applied.svg")

    err = _error_app(tmp_path / "home2")
    async with err.run_test(size=(100, 30)) as pilot:
        await pilot.press("a")
        await pilot.press("enter")  # removal raises -> error must render, not crash
        assert isinstance(err.screen, UninstallScreen)
        assert err.screen.error is not None
        _snapshot(err, "05-error.svg")
