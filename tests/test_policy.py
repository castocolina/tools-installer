from collections.abc import Callable
from pathlib import Path

import pytest

from installer.guards import guard_status, install_shims
from installer.policy import Policy, PolicyLayer, PolicyResult, ban_policy


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


def test_ban_policy_inactive_on_clean_dir(tmp_path: Path) -> None:
    assert _ban(tmp_path).active is False


def test_ban_policy_active_when_shims_present(tmp_path: Path) -> None:
    shim_dir = tmp_path / ".local" / "bin"
    shim_dir.mkdir(parents=True)
    install_shims(shim_dir)
    assert _ban(tmp_path).active is True


def test_apply_writes_both_layers_and_returns_result(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = _ban(tmp_path, apply_to=[rc]).apply()
    shim_dir = tmp_path / ".local" / "bin"
    # Both layers really happened on disk.
    assert all(active for active in guard_status(shim_dir).values())
    assert "alias" in rc.read_text()
    # Structured result: two named layers + a reload hint.
    names = [layer.name for layer in result.layers]
    assert names == ["Shims", "Aliases"]
    assert "3 active" in result.layers[0].detail
    assert str(rc) in result.layers[1].detail
    assert result.reload_hint is not None and "hash -r" in result.reload_hint


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


def test_policy_layer_is_frozen() -> None:
    layer = PolicyLayer(name="Shims", detail="x")
    try:
        layer.name = "y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("PolicyLayer must be frozen")
