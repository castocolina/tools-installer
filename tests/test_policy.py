import os
from collections.abc import Callable
from pathlib import Path

import pytest

from installer.guards import (
    BAN_BEGIN,
    BAN_END,
    REDIRECT_SENTINEL,
    SHIM_SENTINEL,
    guard_status,
    install_shims,
)
from installer.policy import (
    Policy,
    PolicyLayer,
    PolicyResult,
    ban_policy,
    move_link_mode,
    tweak_policy,
)
from installer.tweaks import BUNDLES, tweak_block


def _ban(
    home: Path,
    *,
    apply_to: list[Path] | None = None,
    remove_from: list[Path] | None = None,
    path_value: str = "",
    which: Callable[[str], str | None] = lambda _name: None,
) -> Policy:
    shim_dir = home / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    rc = home / ".myshellrc"
    return ban_policy(
        shim_dir=shim_dir,
        apply_rc_paths=apply_to if apply_to is not None else [rc],
        remove_rc_paths=remove_from if remove_from is not None else [rc],
        path_value=path_value,
        which=which,
    )


def test_ban_policy_metadata(tmp_path: Path) -> None:
    policy = _ban(tmp_path)
    assert policy.id == "ban"
    assert policy.label == "pip/npm ban"
    assert "pip" in policy.description and "npm" in policy.description
    assert "npx" in policy.description and "pnpm dlx" in policy.description


def test_ban_policy_description_names_the_pnpm_wrap_and_volta_reroute(tmp_path: Path) -> None:
    # The user consents to this string; it described the pre-phase-4 behaviour.
    description = _ban(tmp_path).description
    assert "pnpm" in description
    assert "volta install" in description
    assert "global" in description


def test_ban_policy_inactive_on_clean_dir(tmp_path: Path) -> None:
    assert _ban(tmp_path).active is False


def test_ban_policy_active_when_shims_present(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True)
    install_shims(shim_dir)
    assert _ban(tmp_path).active is True


def _plant_volta_and_pnpm(tmp_path: Path) -> Path:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    for name in ("volta", "pnpm"):
        binary = real_dir / name
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
    return real_dir


def test_apply_writes_both_layers_and_returns_result(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = _ban(tmp_path, apply_to=[rc]).apply()
    shim_dir = tmp_path / ".local" / "bin"
    status = guard_status(shim_dir)
    assert status["npm"] is True
    assert status["pip"] is True
    assert status["pip3"] is True
    assert status["npx"] is True
    assert status["pnpm"] is False
    assert not (shim_dir / "pnpm").exists()
    assert SHIM_SENTINEL in (shim_dir / "npm").read_text()
    assert SHIM_SENTINEL in (shim_dir / "pip").read_text()
    assert SHIM_SENTINEL in (shim_dir / "pip3").read_text()
    assert SHIM_SENTINEL in (shim_dir / "npx").read_text()
    assert "alias" in rc.read_text()
    names = [layer.name for layer in result.layers]
    assert names == ["Shims", "Aliases"]
    assert "4 active" in result.layers[0].detail
    assert "blocked (volta not found)" in result.layers[0].detail
    assert "blocked (pnpm not found)" in result.layers[0].detail
    assert "absent (volta not found)" in result.layers[0].detail
    assert str(rc) in result.layers[1].detail
    assert result.reload_hint is not None and "hash -r" in result.reload_hint


def test_apply_with_volta_writes_five_shims(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    real_dir = _plant_volta_and_pnpm(tmp_path)
    shim_dir = tmp_path / ".local" / "bin"
    result = _ban(tmp_path, apply_to=[rc], path_value=f"{shim_dir}{os.pathsep}{real_dir}").apply()
    status = guard_status(shim_dir)
    assert status == {"npm": True, "pip": True, "pip3": True, "npx": True, "pnpm": True}
    assert REDIRECT_SENTINEL in (shim_dir / "npm").read_text()
    assert REDIRECT_SENTINEL in (shim_dir / "pnpm").read_text()
    assert REDIRECT_SENTINEL in (shim_dir / "npx").read_text()
    assert SHIM_SENTINEL in (shim_dir / "pip").read_text()
    assert SHIM_SENTINEL in (shim_dir / "pip3").read_text()
    assert "5 active" in result.layers[0].detail
    assert "blocked" not in result.layers[0].detail
    assert "skipped" not in result.layers[0].detail
    assert "absent" not in result.layers[0].detail


def test_apply_collapses_home_paths_to_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paths under HOME render as ~/… so the feedback stays short and reads like
    a shell path, not an alarming absolute (or pytest temp) dump."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = Path.home() / ".myshellrc"
    result = _ban(Path.home(), apply_to=[rc]).apply()
    assert "~/.local/bin" in result.layers[0].detail
    assert "~/.myshellrc" in result.layers[1].detail
    assert str(tmp_path) not in result.layers[0].detail


def test_apply_warns_when_shim_dir_absent_from_path(tmp_path: Path) -> None:
    result = _ban(tmp_path, path_value="/usr/bin").apply()
    assert result.warning is not None and "not on PATH" in result.warning


def test_apply_no_warning_when_shim_dir_on_path(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    result = _ban(tmp_path, path_value=str(shim_dir)).apply()
    assert result.warning is None


def test_apply_surfaces_skipped_real_binary(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True)
    (shim_dir / "npm").write_text("#!/bin/sh\necho real\n")  # a real binary, not our shim
    result = _ban(tmp_path).apply()
    assert "skipped" in result.layers[0].detail


def test_remove_clears_both_layers(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = _ban(tmp_path, apply_to=[rc], remove_from=[rc])
    policy.apply()
    result = policy.remove()
    shim_dir = tmp_path / ".local" / "bin"
    assert all(active is False for active in guard_status(shim_dir).values())
    for name in ("npm", "pip", "pip3", "npx", "pnpm"):
        assert not (shim_dir / name).exists()
    assert "alias" not in rc.read_text()
    assert [layer.name for layer in result.layers] == ["Shims", "Aliases"]
    assert "removed" in result.layers[0].detail
    assert result.warning is None


def test_remove_is_idempotent(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = _ban(tmp_path, remove_from=[rc])
    # Removing from a clean machine reports cleanly, never raises.
    result = policy.remove()
    assert isinstance(result, PolicyResult)
    assert result.reload_hint is not None


def test_apply_writes_npx_redirect_when_pnpm_resolves(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)
    shim_dir = tmp_path / ".local" / "bin"
    policy = _ban(tmp_path, path_value=f"{shim_dir}{os.pathsep}{real_dir}")
    policy.apply()
    text = (shim_dir / "npx").read_text()
    assert REDIRECT_SENTINEL in text
    assert SHIM_SENTINEL not in text


def test_apply_writes_npx_hard_block_when_pnpm_missing(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    _ban(tmp_path, path_value=str(shim_dir)).apply()
    text = (shim_dir / "npx").read_text()
    assert SHIM_SENTINEL in text
    assert REDIRECT_SENTINEL not in text


def test_policy_layer_is_frozen() -> None:
    layer = PolicyLayer(name="Shims", detail="x")
    try:
        layer.name = "y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("PolicyLayer must be frozen")


def test_ban_policy_apply_rereads_callable_apply_rc_paths(tmp_path: Path) -> None:
    first = tmp_path / "first.rc"
    second = tmp_path / "second.rc"
    current = [first]
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)

    def apply_rc_paths() -> list[Path]:
        return list(current)

    policy = ban_policy(
        shim_dir=shim_dir,
        apply_rc_paths=apply_rc_paths,
        remove_rc_paths=[first],
        path_value="",
        which=lambda _name: None,
    )
    policy.apply()
    assert "alias" in first.read_text()
    assert not second.exists()
    current[0] = second
    policy.apply()
    assert "alias" in second.read_text()


def test_ban_policy_still_accepts_a_plain_list(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = _ban(tmp_path, apply_to=[rc]).apply()
    assert str(rc) in result.layers[1].detail


# --- link-mode move (17-08) -------------------------------------------------


def _mode_policies(home: Path, mode: dict[str, str]) -> tuple[Policy, Policy]:
    """A ban and a tweak whose closures read the live mode from `mode["v"]`."""
    myshellrc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    shim_dir = home / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    ban = ban_policy(
        shim_dir=shim_dir,
        apply_rc_paths=lambda: [myshellrc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[myshellrc, zshrc, bashrc],
        path_value=str(shim_dir),
        which=lambda _name: None,
    )
    bundle = next(b for b in BUNDLES if b.id == "claude-skip")
    tweak = tweak_policy(
        bundle,
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if mode["v"] == "split" else (),
    )
    return ban, tweak


def _setter(mode: dict[str, str]) -> Callable[[str], None]:
    def set_mode(value: str) -> None:
        mode["v"] = value

    return set_mode


def test_move_link_mode_moves_ban_and_tweak_to_split(tmp_path: Path) -> None:
    mode = {"v": "centralized"}
    ban, tweak = _mode_policies(tmp_path, mode)
    ban.apply()
    tweak.apply()
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"

    report = move_link_mode([ban, tweak], "split", _setter(mode), old_mode="centralized")

    # ban aliases: gone from ~/.myshellrc, present in each rc split sources
    assert "tools-installer ban" not in myshellrc.read_text()
    assert "tools-installer ban" in zshrc.read_text()
    assert "tools-installer ban" in bashrc.read_text()
    # tweak block stays in ~/.myshellrc, now sourced from each rc
    assert "tools-installer tweak:claude-skip" in myshellrc.read_text()
    for rc in (zshrc, bashrc):
        assert f'. "{myshellrc}"' in rc.read_text()
    assert mode["v"] == "split"
    assert [entry.policy_id for entry in report] == ["ban", "tweak:claude-skip"]
    assert all(entry.status == "moved" for entry in report)


def test_link_mode_move_keeps_foreign_rc_bytes_identical(tmp_path: Path) -> None:
    from installer.shellrc import remove_source_block, strip_block

    mode = {"v": "centralized"}
    ban, tweak = _mode_policies(tmp_path, mode)
    foreign = "export EDITOR=vi\n# my own config\n"
    for rc in (tmp_path / ".myshellrc", tmp_path / ".zshrc", tmp_path / ".bashrc"):
        rc.write_text(foreign)
    ban.apply()
    tweak.apply()

    move_link_mode([ban, tweak], "split", _setter(mode), old_mode="centralized")

    begin, rest = tweak_block(next(b for b in BUNDLES if b.id == "claude-skip")).split("\n", 1)
    tweak_begin, tweak_end = begin, rest.rsplit("\n", 1)[1]
    checked = tmp_path / "check"
    checked.mkdir()
    for rc in (tmp_path / ".myshellrc", tmp_path / ".zshrc", tmp_path / ".bashrc"):
        text = rc.read_text()
        text = strip_block(text, BAN_BEGIN, BAN_END)
        text = strip_block(text, tweak_begin, tweak_end)
        copy = checked / rc.name
        copy.write_text(text)
        remove_source_block(copy)
        assert copy.read_text().rstrip("\n") == foreign.rstrip("\n")


def test_move_link_mode_restores_the_old_block_when_apply_fails(tmp_path: Path) -> None:
    mode = {"v": "centralized"}
    ban, tweak = _mode_policies(tmp_path, mode)
    ban.apply()
    tweak.apply()
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"

    def failing_apply() -> PolicyResult:
        if mode["v"] == "split":
            raise OSError("no space left on device")
        return tweak_policy(
            next(b for b in BUNDLES if b.id == "claude-skip"),
            rc_path=myshellrc,
        ).apply()

    moved_tweak = Policy(
        id=tweak.id,
        label=tweak.label,
        description=tweak.description,
        active=tweak.active,
        apply=failing_apply,
        remove=tweak.remove,
        link_mode_aware=True,
    )

    report = move_link_mode([ban, moved_tweak], "split", _setter(mode), old_mode="centralized")

    assert mode["v"] == "split"
    statuses = {entry.policy_id: entry.status for entry in report}
    assert statuses == {"ban": "moved", "tweak:claude-skip": "failed"}
    failed = next(entry for entry in report if entry.status == "failed")
    assert "no space left on device" in failed.detail
    assert "restored" in failed.detail
    # the tweak's old block is back in the old file, the ban's is gone (it moved)
    assert "tools-installer tweak:claude-skip" in myshellrc.read_text()
    assert "tools-installer ban" not in myshellrc.read_text()
    # the ban still moved
    assert "tools-installer ban" not in myshellrc.read_text()
    assert "tools-installer ban" in zshrc.read_text()
    assert "tools-installer ban" in bashrc.read_text()


def test_move_link_mode_restores_everything_when_saving_the_mode_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.settings import SettingsStore

    state_path = tmp_path / "state" / "settings.json"
    state_path.parent.mkdir(parents=True)
    store = SettingsStore(state_path, link_mode="centralized")
    ban, tweak = _mode_policies(tmp_path, {"v": store.link_mode})
    # the closures must read the STORE's live mode, like setup.py's do
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)

    def apply_rc_paths() -> list[Path]:
        return [myshellrc] if store.link_mode == "centralized" else [zshrc, bashrc]

    ban = ban_policy(
        shim_dir=shim_dir,
        apply_rc_paths=apply_rc_paths,
        remove_rc_paths=[myshellrc, zshrc, bashrc],
        path_value=str(shim_dir),
        which=lambda _name: None,
    )
    tweak = tweak_policy(
        next(b for b in BUNDLES if b.id == "claude-skip"),
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if store.link_mode == "split" else (),
    )
    ban.apply()
    tweak.apply()
    original_rc = myshellrc.read_text()

    def disk_full(path: Path, settings: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("installer.settings.save_settings", disk_full)
    with pytest.raises(OSError, match="disk full"):
        move_link_mode([ban, tweak], "split", store.set_link_mode, old_mode="centralized")

    assert store.link_mode == "centralized"
    assert myshellrc.read_text() == original_rc
    for split_rc in (zshrc, bashrc):
        assert not split_rc.exists() or "tools-installer ban" not in split_rc.read_text()


def test_move_link_mode_with_no_policies_only_saves_the_mode(tmp_path: Path) -> None:
    calls: list[str] = []

    def set_mode(value: str) -> None:
        calls.append(value)

    report = move_link_mode([], "split", set_mode, old_mode="centralized")

    assert report == ()
    assert calls == ["split"]
    assert not (tmp_path / ".myshellrc").exists()
    assert not (tmp_path / ".zshrc").exists()
    assert not (tmp_path / ".bashrc").exists()


def test_move_link_mode_rolls_back_when_re_saving_the_new_mode_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.settings import SettingsStore, save_settings

    state_path = tmp_path / "state" / "settings.json"
    state_path.parent.mkdir(parents=True)
    store = SettingsStore(state_path, link_mode="centralized")
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    bundle = next(b for b in BUNDLES if b.id == "claude-skip")

    def apply_rc_paths() -> list[Path]:
        return [myshellrc] if store.link_mode == "centralized" else [zshrc, bashrc]

    ban = ban_policy(
        shim_dir=shim_dir,
        apply_rc_paths=apply_rc_paths,
        remove_rc_paths=[myshellrc, zshrc, bashrc],
        path_value=str(shim_dir),
        which=lambda _name: None,
    )
    tweak = tweak_policy(
        bundle,
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if store.link_mode == "split" else (),
    )
    ban.apply()
    tweak.apply()

    def failing_apply() -> PolicyResult:
        if store.link_mode == "split":
            raise OSError("apply boom")
        return tweak_policy(bundle, rc_path=myshellrc).apply()

    moved_tweak = Policy(
        id=tweak.id,
        label=tweak.label,
        description=tweak.description,
        active=tweak.active,
        apply=failing_apply,
        remove=tweak.remove,
        link_mode_aware=True,
    )

    real_save = save_settings
    split_saves = 0

    def flaky_save(path: Path, settings: object) -> None:
        nonlocal split_saves
        if settings.link_mode == "split":  # type: ignore[union-attr]
            split_saves += 1
            if split_saves == 2:  # the re-save after the failed apply's restore
                raise OSError("disk full")
        real_save(path, settings)  # type: ignore[arg-type]

    monkeypatch.setattr("installer.settings.save_settings", flaky_save)
    with pytest.raises(OSError, match="disk full"):
        move_link_mode(
            [ban, moved_tweak],
            "split",
            store.set_link_mode,
            old_mode="centralized",
        )

    assert store.link_mode == "centralized"
    assert split_saves == 2
    # both blocks are back in ~/.myshellrc; the already-moved ban was taken
    # back out of the split rcs
    assert "tools-installer ban" in myshellrc.read_text()
    assert "tools-installer tweak:claude-skip" in myshellrc.read_text()
    assert "tools-installer ban" not in zshrc.read_text()
    assert "tools-installer ban" not in bashrc.read_text()
