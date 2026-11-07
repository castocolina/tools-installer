"""The real-HOME fingerprint names each changed path and entry; tests use scratch homes only."""

from pathlib import Path

from tests.home_fingerprint import fingerprint, fingerprint_diff


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
