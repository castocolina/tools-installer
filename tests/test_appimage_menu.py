"""AppImage menu placement and ownership."""

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from installer import appimage_menu, engine, receipts, uninstall
from installer.download import ExecContext
from installer.enums import InstallStatus
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.run import CommandError
from installer.versions import Release

ID = "com.mitchellh.ghostty"
DESKTOP = (
    "[Desktop Entry]\nName=Ghostty\nTryExec=ghostty\n"
    "Exec=ghostty --gtk-single-instance=true\nIcon=ghostty\n"
    "X-KDE-Shortcuts=Ctrl+Alt+T\n[Desktop Action new-window]\n"
    "Exec=ghostty --gtk-single-instance=true\n"
)
PNG = b"\x89PNG\r\n\x1a\nfixture"


def method() -> Method:
    return Method(
        kind="tarball",
        params={"url": "https://x/a", "member": "ghostty", "raw": True, "desktop": ID},
    )


def paths(home: Path) -> tuple[Path, Path, Path]:
    return (
        home / ".local/bin/ghostty",
        home / f".local/share/applications/{ID}.desktop",
        home / f".local/share/icons/hicolor/256x256/apps/{ID}.png",
    )


class Runner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail = False
        self.missing = False
        self.outside: Path | None = None
        self.icon = PNG

    def __call__(self, argv: list[str]) -> None:
        self.calls.append(argv)
        if self.fail:
            raise CommandError(argv, 1)
        root = Path(argv[1].removeprefix("--chdir=")) / "AppDir"
        root.mkdir(exist_ok=True)
        dest = root / argv[-1]
        if dest.suffix == ".desktop" and self.outside:
            dest.symlink_to(self.outside)
        elif not (dest.suffix == ".desktop" and self.missing):
            dest.write_bytes(DESKTOP.encode() if dest.suffix == ".desktop" else self.icon)


def context(runner: Runner) -> ExecContext:
    return ExecContext(
        runner,
        Platform(os="fedora", arch="amd64", immutable=True, has_brew=False),
        lambda _: Release("v1", {}),
    )


def previous(home: Path, *, leaves: bool = True, tool: str = "ghostty") -> receipts.Receipt:
    binary, desktop, icon = paths(home)
    artifacts = (receipts.ReceiptArtifact(binary, "file"),)
    if leaves:
        artifacts += (
            receipts.ReceiptArtifact(desktop, "leaf"),
            receipts.ReceiptArtifact(icon, "leaf"),
        )
    return receipts.Receipt(
        tool,
        "2026-11-07T00:00:00+00:00",
        receipts.ReceiptMethod("tarball", "test"),
        None,
        artifacts,
        None,
        {},
    )


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Runner, Path]:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    binary, _, _ = paths(tmp_path)
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"binary")
    work = tmp_path / "work"

    def make_work(**_kwargs: object) -> str:
        work.mkdir()
        return str(work)

    monkeypatch.setattr(appimage_menu.tempfile, "mkdtemp", make_work)
    return Runner(), work


def test_install_places_the_icon_and_a_rendered_desktop_entry(
    setup: tuple[Runner, Path], tmp_path: Path
) -> None:
    runner, work = setup
    binary, desktop, icon = paths(tmp_path)
    assert appimage_menu.install(method(), context(runner), None) == ()
    assert runner.calls == [
        [
            "env",
            f"--chdir={work}",
            f"TMPDIR={work}",
            str(binary),
            "--appimage-extract",
            f"{ID}.{suffix}",
        ]
        for suffix in ("desktop", "png")
    ]
    assert icon.read_bytes() == PNG
    text = desktop.read_text()
    assert (
        f"TryExec={binary}" in text and text.count(f"Exec={binary} --gtk-single-instance=true") == 2
    )
    assert f"Icon={icon}" in text and "X-KDE-Shortcuts" not in text
    assert desktop.stat().st_mode & 0o777 == icon.stat().st_mode & 0o777 == 0o644
    assert not work.exists()


def test_a_users_own_desktop_entry_is_kept_and_named(
    setup: tuple[Runner, Path], tmp_path: Path
) -> None:
    runner, _ = setup
    _, desktop, icon = paths(tmp_path)
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"mine")
    assert appimage_menu.install(method(), context(runner), None) == (
        f"kept your existing ~/.local/share/applications/{ID}.desktop",
    )
    assert desktop.read_bytes() == b"mine" and icon.read_bytes() == PNG


def test_a_previous_receipt_that_records_the_paths_authorizes_a_replacement(
    setup: tuple[Runner, Path], tmp_path: Path
) -> None:
    runner, _ = setup
    _, desktop, icon = paths(tmp_path)
    for path in (desktop, icon):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"old")
    assert appimage_menu.install(method(), context(runner), previous(tmp_path)) == ()
    assert icon.read_bytes() == PNG and desktop.read_bytes() != b"old"


def test_a_receipt_that_does_not_list_the_path_authorizes_nothing(
    setup: tuple[Runner, Path], tmp_path: Path
) -> None:
    runner, _ = setup
    _, desktop, _ = paths(tmp_path)
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"mine")
    receipts.write(previous(tmp_path, tool="other"))
    assert (
        "kept your existing"
        in appimage_menu.install(method(), context(runner), previous(tmp_path, leaves=False))[0]
    )
    assert desktop.read_bytes() == b"mine"


def test_nothing_is_extracted_when_both_files_are_the_users(
    setup: tuple[Runner, Path], tmp_path: Path
) -> None:
    runner, _ = setup
    for path in paths(tmp_path)[1:]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mine")
    notes = appimage_menu.install(method(), context(runner), None)
    assert len(notes) == 2 and "/icons/" in notes[0] and "/applications/" in notes[1]
    assert not runner.calls


@pytest.mark.parametrize("failure", ["command", "missing", "symlink"])
def test_extraction_failures_write_nothing(
    setup: tuple[Runner, Path], tmp_path: Path, failure: str
) -> None:
    runner, work = setup
    if failure == "command":
        runner.fail = True
    elif failure == "missing":
        runner.missing = True
    else:
        runner.outside = tmp_path / "outside"
        runner.outside.write_bytes(b"outside")
    assert appimage_menu.install(method(), context(runner), None)[0].startswith(
        "could not add the application menu entry"
    )
    assert not any(p.exists() for p in paths(tmp_path)[1:]) and not work.exists()


@pytest.mark.parametrize("index", [1, 2])
def test_a_destination_swapped_for_a_symlink_after_the_check_is_refused(
    setup: tuple[Runner, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    runner, _ = setup
    _, desktop, icon = paths(tmp_path)
    target = paths(tmp_path)[index]
    victim = tmp_path / "victim"
    victim.write_bytes(b"USER-DATA")
    real = appimage_menu.missing_dirs

    def swap(path: Path, home: Path) -> tuple[str, ...]:
        if path == target:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(victim)
        return real(path, home)

    monkeypatch.setattr(appimage_menu, "missing_dirs", swap)
    notes = appimage_menu.install(method(), context(runner), None)
    assert "symlink" in notes[-1] and victim.read_bytes() == b"USER-DATA" and target.is_symlink()
    assert not (icon if index == 1 else desktop).exists()


@pytest.mark.parametrize("existing,restore_fails", [(False, False), (True, False), (True, True)])
def test_write_failure_rolls_back_and_reports_failed_restore(
    setup: tuple[Runner, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
    restore_fails: bool,
) -> None:
    runner, _ = setup
    _, desktop, icon = paths(tmp_path)
    if existing:
        for path in (desktop, icon):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"old")
    real = appimage_menu.atomic_write_bytes
    count = 0

    def flaky(path: Path, data: bytes, *, mode: int | None = None) -> None:
        nonlocal count
        count += 1
        if path == desktop or (restore_fails and count > 1):
            raise OSError("disk full")
        real(path, data, mode=mode)

    monkeypatch.setattr(appimage_menu, "atomic_write_bytes", flaky)
    notes = appimage_menu.install(
        method(), context(runner), previous(tmp_path) if existing else None
    )
    assert notes[-1].startswith("could not add the application menu entry: disk full")
    if existing:
        assert desktop.read_bytes() == b"old"
        assert icon.read_bytes() == (PNG if restore_fails else b"old")
        if restore_fails:
            assert notes[0].startswith("could not restore ")
    else:
        assert not desktop.exists() and not icon.exists()
        assert not (tmp_path / ".local/share").exists()


def test_a_home_failure_is_a_note(
    setup: tuple[Runner, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, _ = setup

    def no_home() -> Path:
        raise RuntimeError("no home")

    monkeypatch.setattr(Path, "home", no_home)
    assert appimage_menu.install(method(), context(runner), None) == (
        "could not add the application menu entry: no home",
    )
    assert not runner.calls


def test_a_temp_dir_failure_is_a_note(
    setup: tuple[Runner, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    runner, _ = setup

    def no_space(**_kwargs: object) -> str:
        raise OSError("no space")

    monkeypatch.setattr(appimage_menu.tempfile, "mkdtemp", no_space)
    assert appimage_menu.install(method(), context(runner), None) == (
        "could not add the application menu entry: no space",
    )


def test_a_method_without_desktop_does_nothing(setup: tuple[Runner, Path]) -> None:
    runner, _ = setup
    assert appimage_menu.install(Method(kind="tarball", params={}), context(runner), None) == ()
    assert not runner.calls


PAYLOAD = b"#!/bin/sh\necho Ghostty 1.4.0\n"


def ghostty_tool() -> Tool:
    tool = next(t for t in load_tools(Path("installer/registry.toml")) if t.id == "ghostty")
    selected = next(m for m in tool.methods if m.kind == "tarball" and m.arch == ("amd64",))
    selected = replace(
        selected, params={**selected.params, "sha256": hashlib.sha256(PAYLOAD).hexdigest()}
    )
    return replace(tool, methods=(selected,))


class InstallRunner(Runner):
    def __call__(self, argv: list[str]) -> None:
        if argv[0] == "curl":
            Path(argv[argv.index("-o") + 1]).write_bytes(PAYLOAD)
        else:
            super().__call__(argv)


def run_engine(tool: Tool, runner: InstallRunner) -> engine.InstallOutcome:
    return engine.install_tool(
        tool,
        Platform(os="fedora", arch="amd64", immutable=True, has_brew=False),
        runner=runner,
        present=lambda _: False,
    )


def test_the_engine_places_the_menu_entry_and_records_three_receipt_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = ghostty_tool()
    outcome = run_engine(tool, InstallRunner())
    assert outcome.status is InstallStatus.INSTALLED
    assert outcome.postinstall_warning == tool.methods[0].params["note"]
    receipt = receipts.read("ghostty")
    assert receipt is not None
    assert [(a.path, a.type) for a in receipt.artifacts] == [
        (paths(tmp_path)[0], "file"),
        (paths(tmp_path)[1], "leaf"),
        (paths(tmp_path)[2], "leaf"),
    ]


def test_a_menu_failure_is_a_note_and_the_install_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    runner = InstallRunner()
    runner.fail = True
    outcome = run_engine(ghostty_tool(), runner)
    assert outcome.status is InstallStatus.INSTALLED and paths(tmp_path)[0].exists()
    assert (
        outcome.postinstall_warning
        and "could not add the application menu entry" in outcome.postinstall_warning
    )
    receipt = receipts.read("ghostty")
    assert receipt is not None and len(receipt.artifacts) == 1


def test_removal_covers_the_binary_and_both_leaves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = ghostty_tool()
    assert run_engine(tool, InstallRunner()).status is InstallStatus.INSTALLED
    binary, desktop, icon = paths(tmp_path)
    plan = uninstall.removal_plan(tool, binary.parent, verify=True)
    assert set(plan.removable) == {binary, desktop, icon}
    removed, refused = uninstall.remove_proven([tool], list(plan.removable), binary.parent)
    assert set(removed) == {binary, desktop, icon} and not refused
    assert not any(p.exists() for p in (binary, desktop, icon)) and receipts.read("ghostty") is None


@pytest.mark.parametrize("missing", [1, 2])
def test_missing_menu_leaf_preserves_removal_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: int
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = ghostty_tool()
    assert run_engine(tool, InstallRunner()).status is InstallStatus.INSTALLED
    binary, desktop, icon = paths(tmp_path)
    paths(tmp_path)[missing].unlink()
    receipt = receipts.read("ghostty")
    assert receipt is not None
    assert receipts.broken_drift(receipt) == ()
    assert receipts.drifted(receipt) == ()
    plan = uninstall.removal_plan(tool, binary.parent, verify=True)
    assert set(plan.removable) == ({binary, icon} if missing == 1 else {binary, desktop})
    removed, refused = uninstall.remove_proven([tool], list(plan.removable), binary.parent)
    assert set(removed) == set(plan.removable) and not refused
    assert receipts.read("ghostty") is None


def test_missing_non_menu_leaf_is_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    leaf = receipts.ReceiptArtifact(tmp_path / ".local/bin/missing", "leaf")
    receipt = replace(previous(tmp_path), artifacts=(leaf,))
    assert receipts.broken_drift(receipt) == (leaf,)
    assert receipts.drifted(receipt) == (leaf,)


@pytest.mark.parametrize("index", [1, 2])
def test_menu_leaf_replaced_by_directory_is_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = ghostty_tool()
    assert run_engine(tool, InstallRunner()).status is InstallStatus.INSTALLED
    path = paths(tmp_path)[index]
    path.unlink()
    path.mkdir()
    receipt = receipts.read("ghostty")
    assert receipt is not None
    artifact = next(a for a in receipt.artifacts if a.path == path)
    assert receipts.broken_drift(receipt) == (artifact,)
    assert receipts.drifted(receipt) == (artifact,)


def test_plan_uninstall_ignores_a_users_own_desktop_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    binary, desktop, _ = paths(tmp_path)
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"mine")
    tool = ghostty_tool()
    assert uninstall.plan_uninstall([tool], binary.parent) == []
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"binary")
    assert uninstall.plan_uninstall([tool], binary.parent) == [binary]


def test_a_reinstall_replaces_the_menu_files_through_the_own_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = ghostty_tool()
    runner = InstallRunner()
    assert run_engine(tool, runner).status is InstallStatus.INSTALLED
    runner.icon = b"new icon"
    assert run_engine(tool, runner).status is InstallStatus.INSTALLED
    assert paths(tmp_path)[2].read_bytes() == b"new icon"
    receipt = receipts.read("ghostty")
    assert receipt is not None and len(receipt.artifacts) == 3


def test_another_tools_receipt_does_not_authorize_an_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _, desktop, icon = paths(tmp_path)
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"mine")
    receipts.write(previous(tmp_path, tool="other"))
    outcome = run_engine(ghostty_tool(), InstallRunner())
    assert outcome.status is InstallStatus.INSTALLED
    assert desktop.read_bytes() == b"mine" and icon.read_bytes() == PNG
    assert outcome.postinstall_warning and "kept your existing" in outcome.postinstall_warning
    receipt = receipts.read("ghostty")
    assert receipt is not None and desktop not in {a.path for a in receipt.artifacts}
