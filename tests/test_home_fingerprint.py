"""The real-HOME fingerprint names each changed path and entry; tests use scratch homes only."""

import builtins
import os
import sys
import time
from pathlib import Path

import pytest

from tests.home_fingerprint import fingerprint, fingerprint_diff, watched_paths

# Spelled out here, not read from the module: a dropped entry in the module must fail this test.
# SPEC R9 (18 paths: the home-relative list plus the three toolchain defaults), the three
# installer listings, and the six rc dotfiles.
_COVERED = (
    ".claude/gsd-core",
    ".claude/.gsd-source",
    ".claude/gsd-file-manifest.json",
    ".claude/agents",
    ".claude/commands",
    ".claude/hooks",
    ".gsd",
    ".agents",
    ".codex",
    ".cursor",
    ".config/opencode",
    ".local/bin",
    ".local/opt",
    ".local/share/uv/tools",
    ".local/share/pnpm",
    ".volta/tools",
    ".config/systemd/user",
    ".oh-my-zsh",
    ".local/state/tools-installer/receipts",
    ".config/environment.d",
    ".local/state/tools-installer/config",
    ".myshellrc",
    ".shellrc",
    ".bashrc",
    ".zshrc",
    ".zshenv",
    ".profile",
)
_FILES = frozenset(
    {
        ".claude/gsd-file-manifest.json",
        ".myshellrc",
        ".shellrc",
        ".bashrc",
        ".zshrc",
        ".zshenv",
        ".profile",
    }
)


def test_creating_gsd_core_is_named(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    (home / ".claude").mkdir(parents=True)
    before = fingerprint(home, {})
    (home / ".claude" / "gsd-core").mkdir()
    assert fingerprint_diff(before, fingerprint(home, {})) == ["~/.claude/gsd-core: created"]


def test_an_unchanged_tree_has_no_diff(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    (home / ".local" / "bin").mkdir(parents=True)
    (home / ".local" / "bin" / "a").write_text("x", encoding="utf-8")
    (home / ".zshrc").write_text("x", encoding="utf-8")
    (home / ".claude" / "agents").mkdir(parents=True)
    before = fingerprint(home, {})
    assert fingerprint_diff(before, fingerprint(home, {})) == []


def test_absent_is_recorded_not_an_error(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    home.mkdir()
    state = fingerprint(home, {})
    assert state["~/.claude/gsd-core"] is None
    assert state["~/.local/bin"] is None
    assert state["~/.zshrc"] is None


def test_adding_a_file_to_local_bin_names_the_entry(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    (home / ".local" / "bin").mkdir(parents=True)
    before = fingerprint(home, {})
    (home / ".local" / "bin" / "x").write_text("x", encoding="utf-8")
    assert fingerprint_diff(before, fingerprint(home, {})) == [
        "~/.local/bin: added ['x'], removed []"
    ]


def test_touching_systemd_user_is_a_change(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    unit_dir = home / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True)
    before = fingerprint(home, {})
    later = time.time() + 1
    os.utime(unit_dir, (later, later))
    assert fingerprint_diff(before, fingerprint(home, {})) == [
        "~/.config/systemd/user: changed (mtime or size only)"
    ]


@pytest.mark.parametrize("relative", _COVERED)
def test_every_watched_location_is_covered(tmp_path: Path, relative: str) -> None:
    home = tmp_path / "realhome"
    home.mkdir()
    before = fingerprint(home, {})
    target = home / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if relative in _FILES:
        target.write_text("x", encoding="utf-8")
    else:
        target.mkdir()
    lines = fingerprint_diff(before, fingerprint(home, {}))
    assert any(line.startswith(f"~/{relative}:") for line in lines), lines


def test_overrides_pick_the_toolchain_dirs(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    overrides: dict[str, str | None] = {
        "UV_TOOL_DIR": str(tmp_path / "uv-tools"),
        "PNPM_HOME": str(tmp_path / "pnpm"),
        "VOLTA_HOME": str(tmp_path / "volta"),
    }
    overridden = set(watched_paths(home, overrides).values())
    assert {tmp_path / "uv-tools", tmp_path / "pnpm", tmp_path / "volta" / "tools"} <= overridden
    defaults = set(watched_paths(home, {}).values())
    assert {
        home / ".local" / "share" / "uv" / "tools",
        home / ".local" / "share" / "pnpm",
        home / ".volta" / "tools",
    } <= defaults


def test_a_path_watched_twice_reports_once(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    (home / ".local" / "bin").mkdir(parents=True)
    overrides: dict[str, str | None] = {"PNPM_HOME": str(home / ".local" / "bin")}
    before = fingerprint(home, overrides)
    (home / ".local" / "bin" / "x").write_text("x", encoding="utf-8")
    assert fingerprint_diff(before, fingerprint(home, overrides)) == [
        "~/.local/bin: added ['x'], removed []"
    ]


def test_listings_are_compared_as_sets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "realhome"
    (home / ".local" / "bin").mkdir(parents=True)
    (home / ".local" / "bin" / "a").write_text("x", encoding="utf-8")
    (home / ".local" / "bin" / "b").write_text("x", encoding="utf-8")
    before = fingerprint(home, {})
    real_listdir = os.listdir

    def reversed_listdir(path: str | os.PathLike[str]) -> list[str]:
        return list(reversed(real_listdir(path)))

    monkeypatch.setattr(os, "listdir", reversed_listdir)
    assert fingerprint_diff(before, fingerprint(home, {})) == []


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS filesystem rejects a non-UTF-8 name")
def test_non_utf8_names_round_trip(tmp_path: Path) -> None:
    home = tmp_path / "realhome"
    (home / ".local" / "bin").mkdir(parents=True)
    before = fingerprint(home, {})
    name = os.fsdecode(b"bad\xff")
    (home / ".local" / "bin" / name).write_text("x", encoding="utf-8")
    assert fingerprint_diff(before, fingerprint(home, {})) == [
        f"~/.local/bin: added [{name!r}], removed []"
    ]


def test_fingerprint_never_opens_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "realhome"
    (home / ".codex").mkdir(parents=True)
    secret = home / ".codex" / "auth.json"
    secret.write_text("secret", encoding="utf-8")
    secret.chmod(0)

    def refuse_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("the fingerprint opened a file")

    monkeypatch.setattr(builtins, "open", refuse_open)
    state = fingerprint(home, {})
    codex = state["~/.codex"]
    assert codex is not None
    assert codex.entries == frozenset({"auth.json"})
