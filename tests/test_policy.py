from collections.abc import Callable
from pathlib import Path

import pytest

from installer.policy import (
    Policy,
    PolicyLayer,
    PolicyResult,
    move_link_mode,
    tweak_policy,
)
from installer.tweaks import BUNDLES, tweak_block
from tests.policy_doubles import BLOCK_BEGIN, BLOCK_END, block_policy


def test_policy_layer_is_frozen() -> None:
    layer = PolicyLayer(name="Shims", detail="x")
    try:
        layer.name = "y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("PolicyLayer must be frozen")


# --- link-mode move (17-08) -------------------------------------------------


def _mode_policies(home: Path, mode: dict[str, str]) -> tuple[Policy, Policy]:
    """A block and a tweak whose closures read the live mode from `mode["v"]`."""
    myshellrc = home / ".myshellrc"
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    block = block_policy(
        apply_rc_paths=lambda: [myshellrc] if mode["v"] == "centralized" else [zshrc, bashrc],
        remove_rc_paths=[myshellrc, zshrc, bashrc],
    )
    bundle = next(b for b in BUNDLES if b.id == "docker")
    tweak = tweak_policy(
        bundle,
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if mode["v"] == "split" else (),
    )
    return block, tweak


def _setter(mode: dict[str, str]) -> Callable[[str], None]:
    def set_mode(value: str) -> None:
        mode["v"] = value

    return set_mode


def test_move_link_mode_moves_block_and_tweak_to_split(tmp_path: Path) -> None:
    mode = {"v": "centralized"}
    block, tweak = _mode_policies(tmp_path, mode)
    block.apply()
    tweak.apply()
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"

    report = move_link_mode([block, tweak], "split", _setter(mode), old_mode="centralized")

    # block markers: gone from ~/.myshellrc, present in each rc split sources
    assert "tools-installer block" not in myshellrc.read_text()
    assert "tools-installer block" in zshrc.read_text()
    assert "tools-installer block" in bashrc.read_text()
    # tweak block stays in ~/.myshellrc, now sourced from each rc
    assert "tools-installer tweak:docker" in myshellrc.read_text()
    for rc in (zshrc, bashrc):
        assert f'. "{myshellrc}"' in rc.read_text()
    assert mode["v"] == "split"
    assert [entry.policy_id for entry in report] == ["block", "tweak:docker"]
    assert all(entry.status == "moved" for entry in report)


def test_link_mode_move_keeps_foreign_rc_bytes_identical(tmp_path: Path) -> None:
    from installer.shellrc import remove_source_block, strip_block

    mode = {"v": "centralized"}
    block, tweak = _mode_policies(tmp_path, mode)
    foreign = "export EDITOR=vi\n# my own config\n"
    for rc in (tmp_path / ".myshellrc", tmp_path / ".zshrc", tmp_path / ".bashrc"):
        rc.write_text(foreign)
    block.apply()
    tweak.apply()

    move_link_mode([block, tweak], "split", _setter(mode), old_mode="centralized")

    begin, rest = tweak_block(next(b for b in BUNDLES if b.id == "docker")).split("\n", 1)
    tweak_begin, tweak_end = begin, rest.rsplit("\n", 1)[1]
    checked = tmp_path / "check"
    checked.mkdir()
    for rc in (tmp_path / ".myshellrc", tmp_path / ".zshrc", tmp_path / ".bashrc"):
        text = rc.read_text()
        text = strip_block(text, BLOCK_BEGIN, BLOCK_END)
        text = strip_block(text, tweak_begin, tweak_end)
        copy = checked / rc.name
        copy.write_text(text)
        remove_source_block(copy)
        assert copy.read_text().rstrip("\n") == foreign.rstrip("\n")


def test_move_link_mode_restores_the_old_block_when_apply_fails(tmp_path: Path) -> None:
    mode = {"v": "centralized"}
    block, tweak = _mode_policies(tmp_path, mode)
    block.apply()
    tweak.apply()
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"

    def failing_apply() -> PolicyResult:
        if mode["v"] == "split":
            raise OSError("no space left on device")
        return tweak_policy(
            next(b for b in BUNDLES if b.id == "docker"),
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

    report = move_link_mode([block, moved_tweak], "split", _setter(mode), old_mode="centralized")

    assert mode["v"] == "split"
    statuses = {entry.policy_id: entry.status for entry in report}
    assert statuses == {"block": "moved", "tweak:docker": "failed"}
    failed = next(entry for entry in report if entry.status == "failed")
    assert "no space left on device" in failed.detail
    assert "restored" in failed.detail
    # the tweak's old block is back in the old file, the block's is gone (it moved)
    assert "tools-installer tweak:docker" in myshellrc.read_text()
    assert "tools-installer block" not in myshellrc.read_text()
    # the block still moved
    assert "tools-installer block" not in myshellrc.read_text()
    assert "tools-installer block" in zshrc.read_text()
    assert "tools-installer block" in bashrc.read_text()


def test_move_link_mode_restores_everything_when_saving_the_mode_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.settings import SettingsStore

    state_path = tmp_path / "state" / "settings.json"
    state_path.parent.mkdir(parents=True)
    store = SettingsStore(state_path, link_mode="centralized")
    block, tweak = _mode_policies(tmp_path, {"v": store.link_mode})
    # the closures must read the STORE's live mode, like setup.py's do
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"

    def apply_rc_paths() -> list[Path]:
        return [myshellrc] if store.link_mode == "centralized" else [zshrc, bashrc]

    block = block_policy(apply_rc_paths=apply_rc_paths, remove_rc_paths=[myshellrc, zshrc, bashrc])
    tweak = tweak_policy(
        next(b for b in BUNDLES if b.id == "docker"),
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if store.link_mode == "split" else (),
    )
    block.apply()
    tweak.apply()
    original_rc = myshellrc.read_text()

    def disk_full(path: Path, settings: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("installer.settings.save_settings", disk_full)
    with pytest.raises(OSError, match="disk full"):
        move_link_mode([block, tweak], "split", store.set_link_mode, old_mode="centralized")

    assert store.link_mode == "centralized"
    assert myshellrc.read_text() == original_rc
    for split_rc in (zshrc, bashrc):
        assert not split_rc.exists() or "tools-installer block" not in split_rc.read_text()


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
    bundle = next(b for b in BUNDLES if b.id == "docker")

    def apply_rc_paths() -> list[Path]:
        return [myshellrc] if store.link_mode == "centralized" else [zshrc, bashrc]

    block = block_policy(apply_rc_paths=apply_rc_paths, remove_rc_paths=[myshellrc, zshrc, bashrc])
    tweak = tweak_policy(
        bundle,
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if store.link_mode == "split" else (),
    )
    block.apply()
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
            [block, moved_tweak],
            "split",
            store.set_link_mode,
            old_mode="centralized",
        )

    assert store.link_mode == "centralized"
    assert split_saves == 2
    # both blocks are back in ~/.myshellrc; the already-moved block was taken
    # back out of the split rcs
    assert "tools-installer block" in myshellrc.read_text()
    assert "tools-installer tweak:docker" in myshellrc.read_text()
    assert "tools-installer block" not in zshrc.read_text()
    assert "tools-installer block" not in bashrc.read_text()


def test_move_link_mode_clears_a_partial_new_mode_write_before_restoring(
    tmp_path: Path,
) -> None:
    """WR-02 / ponytail #4: a new-mode apply that fails halfway (first rc
    written, second not) must not leave the partial block behind while the
    report says the old block was restored. The per-policy restore removes
    before it re-applies."""
    mode = {"v": "centralized"}
    block, _tweak = _mode_policies(tmp_path, mode)
    block.apply()
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"

    def central_apply() -> PolicyResult:
        if mode["v"] == "split":
            with zshrc.open("a") as fh:
                fh.write(f"{BLOCK_BEGIN}\n{BLOCK_END}\n")
            raise OSError("no space left on device")
        return block_policy(
            apply_rc_paths=lambda: [myshellrc], remove_rc_paths=[myshellrc, zshrc]
        ).apply()

    partial_block = Policy(
        id="block",
        label="Block",
        description="a block that half-applies",
        active=True,
        apply=central_apply,
        remove=block.remove,
        link_mode_aware=True,
    )

    report = move_link_mode([partial_block], "split", _setter(mode), old_mode="centralized")

    assert [entry.status for entry in report] == ["failed"]
    assert "no space left on device" in report[0].detail
    # the partial split write is gone from ~/.zshrc ...
    assert BLOCK_BEGIN not in zshrc.read_text()
    # ... and the old block is back in ~/.myshellrc
    assert BLOCK_BEGIN in myshellrc.read_text()


def test_move_link_mode_names_the_ids_it_could_not_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-02: the new-mode apply fails AND saving the old mode fails too, so
    the live mode stays the new one and the rollback re-apply of the failing
    policy fails again. The raised error names that id instead of dropping it
    silently."""
    from installer.settings import SettingsStore, save_settings

    state_path = tmp_path / "state" / "settings.json"
    state_path.parent.mkdir(parents=True)
    store = SettingsStore(state_path, link_mode="centralized")
    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    bashrc = tmp_path / ".bashrc"
    bundle = next(b for b in BUNDLES if b.id == "docker")

    def apply_rc_paths() -> list[Path]:
        return [myshellrc] if store.link_mode == "centralized" else [zshrc, bashrc]

    block = block_policy(apply_rc_paths=apply_rc_paths, remove_rc_paths=[myshellrc, zshrc, bashrc])
    tweak = tweak_policy(
        bundle,
        rc_path=myshellrc,
        ensure_sourced_from=lambda: (zshrc, bashrc) if store.link_mode == "split" else (),
    )
    block.apply()
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

    def flaky_save(path: Path, settings: object) -> None:
        if settings.link_mode == "centralized":  # type: ignore[union-attr]
            raise OSError("settings.json unwritable")
        real_save(path, settings)  # type: ignore[arg-type]

    monkeypatch.setattr("installer.settings.save_settings", flaky_save)
    with pytest.raises(OSError, match=r"settings\.json unwritable; not restored: tweak:docker"):
        move_link_mode([block, moved_tweak], "split", store.set_link_mode, old_mode="centralized")

    # the live mode stayed split (the failed save never assigned), so the
    # rollback left the block's block in the split rcs
    assert store.link_mode == "split"
    assert "tools-installer block" in zshrc.read_text()


def test_move_link_mode_with_the_live_mode_is_a_no_op(tmp_path: Path) -> None:
    """ponytail #5: picking the mode that is already live removes and
    re-applies nothing."""
    mode = {"v": "centralized"}
    block, tweak = _mode_policies(tmp_path, mode)
    block.apply()
    tweak.apply()
    before = {
        rc: (rc.exists() and rc.read_text() or "")
        for rc in (tmp_path / ".myshellrc", tmp_path / ".zshrc", tmp_path / ".bashrc")
    }
    calls: list[str] = []

    def recorded(name: str, fn: Callable[[], PolicyResult]) -> Callable[[], PolicyResult]:
        def wrapped() -> PolicyResult:
            calls.append(name)
            return fn()

        return wrapped

    watched = [
        Policy(
            id=policy.id,
            label=policy.label,
            description=policy.description,
            active=policy.active,
            apply=recorded(f"{policy.id}-apply", policy.apply),
            remove=recorded(f"{policy.id}-remove", policy.remove),
            link_mode_aware=True,
        )
        for policy in (block, tweak)
    ]

    report = move_link_mode(watched, "centralized", _setter(mode), old_mode="centralized")

    assert report == ()
    assert calls == []
    assert mode["v"] == "centralized"
    for rc, text in before.items():
        assert (rc.exists() and rc.read_text() or "") == text
