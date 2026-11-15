import os
from pathlib import Path

import pytest

from installer.bun_globals import (
    BunGlobal,
    bun_dirs,
    bun_keeps,
    listed_versions,
    method_bin_dir,
    read_bun_globals,
    resolve_bun,
    trusted_dependencies,
)
from installer.model import Method

_BUN_VARS = ("BUN_INSTALL", "BUN_INSTALL_BIN", "BUN_INSTALL_GLOBAL_DIR")


@pytest.fixture(autouse=True)
def scratch_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in _BUN_VARS:
        monkeypatch.delenv(name, raising=False)
    return home


def _plant_bun(directory: Path, *, executable: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "bun"
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755 if executable else 0o644)
    return path


def test_bun_dirs_follow_the_bun_install_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_home: Path
) -> None:
    assert bun_dirs() == (
        scratch_home / ".bun" / "bin",
        scratch_home / ".bun" / "install" / "global",
    )
    other = tmp_path / "other"
    assert bun_dirs(home=other) == (other / ".bun" / "bin", other / ".bun" / "install" / "global")

    monkeypatch.setenv("BUN_INSTALL", "/x")
    assert bun_dirs() == (Path("/x/bin"), Path("/x/install/global"))
    assert bun_dirs(home=other) == (Path("/x/bin"), Path("/x/install/global"))

    monkeypatch.setenv("BUN_INSTALL_BIN", "/y/bin")
    assert bun_dirs() == (Path("/y/bin"), Path("/x/install/global"))
    monkeypatch.delenv("BUN_INSTALL_BIN")
    monkeypatch.setenv("BUN_INSTALL_GLOBAL_DIR", "/z/global")
    assert bun_dirs() == (Path("/x/bin"), Path("/z/global"))

    monkeypatch.setenv("BUN_INSTALL", "")
    monkeypatch.setenv("BUN_INSTALL_GLOBAL_DIR", "")
    assert bun_dirs() == (
        scratch_home / ".bun" / "bin",
        scratch_home / ".bun" / "install" / "global",
    )

    monkeypatch.setenv("BUN_INSTALL", "~/custom")
    assert bun_dirs() == (
        scratch_home / "custom" / "bin",
        scratch_home / "custom" / "install" / "global",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BUN_INSTALL", "rel")
    bin_dir, global_dir = bun_dirs()
    assert bin_dir == tmp_path / "rel" / "bin"
    assert global_dir == tmp_path / "rel" / "install" / "global"
    assert bin_dir.is_absolute()


def test_resolve_bun_prefers_path_then_the_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scratch_home: Path
) -> None:
    on_path = _plant_bun(tmp_path / "pathdir")
    in_bin = _plant_bun(scratch_home / ".bun" / "bin")
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert resolve_bun() == str(on_path)
    monkeypatch.setenv("PATH", "")
    assert resolve_bun() == str(in_bin)
    in_bin.chmod(0o644)
    assert resolve_bun() is None
    in_bin.unlink()
    assert resolve_bun() is None


def test_resolve_bun_never_returns_a_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _plant_bun(tmp_path / "rel")
    for path_value in ("rel", "rel::"):
        monkeypatch.setenv("PATH", path_value)
        assert resolve_bun() is None
    bin_dir = tmp_path / "binroot" / "bin"
    planted = _plant_bun(bin_dir)
    monkeypatch.setenv("BUN_INSTALL_BIN", str(bin_dir))
    for path_value in ("rel", "rel::"):
        monkeypatch.setenv("PATH", path_value)
        found = resolve_bun()
        assert found == str(planted)
        assert found is not None
        assert os.path.isabs(found)


def test_method_bin_dir_prefers_a_declared_dir_then_bun_then_none(scratch_home: Path) -> None:
    declared = Method("script", {"bin_dir": "~/.local/bin"})
    assert method_bin_dir(declared) == scratch_home / ".local" / "bin"
    assert method_bin_dir(Method("bun", {"npm_pkg": "x"})) == scratch_home / ".bun" / "bin"
    assert method_bin_dir(Method("node", {"npm_pkg": "x"})) is None


def _write_manifest(scratch_home: Path, content: str | bytes) -> Path:
    manifest = bun_dirs()[1] / "package.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        manifest.write_bytes(content)
    else:
        manifest.write_text(content, encoding="utf-8")
    return manifest


def test_trusted_dependencies_reads_only_a_string_list(scratch_home: Path) -> None:
    assert trusted_dependencies() is None  # no tree at all
    manifest = _write_manifest(scratch_home, '{"trustedDependencies": ["esbuild", "sharp"]}')
    assert trusted_dependencies() == ["esbuild", "sharp"]
    before = manifest.read_bytes()
    for content in (
        '{"dependencies": {}}',
        '{"trustedDependencies": "esbuild"}',
        '{"trustedDependencies": ["esbuild", 3]}',
        '["trustedDependencies"]',
        "not json",
        b"\xff\xfe",
    ):
        _write_manifest(scratch_home, content)
        assert trusted_dependencies() is None
    _write_manifest(scratch_home, before)
    assert trusted_dependencies() == ["esbuild", "sharp"]
    assert manifest.read_bytes() == before


def test_trusted_dependencies_reads_an_unreadable_manifest_as_none(
    scratch_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(scratch_home, '{"trustedDependencies": ["esbuild"]}')

    def refuse(_self: Path, *_args: object, **_kwargs: object) -> str:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", refuse)
    assert trusted_dependencies() is None
    assert read_bun_globals() is None


def _plant_member(name: str, content: str | bytes) -> Path:
    member = bun_dirs()[1] / "node_modules" / name / "package.json"
    member.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        member.write_bytes(content)
    else:
        member.write_text(content, encoding="utf-8")
    return member


def test_reader_gives_an_empty_inventory_for_no_tree_or_no_dependencies(
    scratch_home: Path,
) -> None:
    assert read_bun_globals() == {}  # no tree at all
    assert listed_versions() == {}
    bun_dirs()[1].mkdir(parents=True)
    assert read_bun_globals() == {}  # a tree with no manifest
    _write_manifest(scratch_home, '{"dependencies": {}}')
    assert read_bun_globals() == {}
    _write_manifest(scratch_home, '{"trustedDependencies": ["esbuild"]}')
    assert read_bun_globals() == {}


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        b"\xff\xfe",
        '["dependencies"]',
        '{"dependencies": ["x"]}',
        '{"dependencies": {"left-pad": 1}}',
        '{"dependencies": {"../../etc": "1.0.0"}}',
        '{"dependencies": {"left-pad": "1.0.0", "Not/Valid": "1.0.0"}}',
        '{"dependencies": {"a..b": "1.0.0"}}',
        '{"dependencies": {".hidden": "1.0.0"}}',
        '{"dependencies": {"_x": "1.0.0"}}',
        '{"dependencies": {"two words": "1.0.0"}}',
    ],
)
def test_reader_gives_none_for_an_unreadable_or_untrustworthy_manifest(
    scratch_home: Path, content: str | bytes
) -> None:
    _write_manifest(scratch_home, content)
    assert read_bun_globals() is None
    assert listed_versions() is None


def test_reader_keeps_a_legacy_uppercase_name_beside_the_catalog_packages(
    scratch_home: Path,
) -> None:
    _write_manifest(
        scratch_home,
        '{"dependencies": {"@mermaid-js/mermaid-cli": "^11.0.0", "JSONStream": "^1.3.5"}}',
    )
    _plant_member("JSONStream", '{"version": "1.3.5"}')
    assert read_bun_globals() == {
        "@mermaid-js/mermaid-cli": BunGlobal("^11.0.0", None),
        "JSONStream": BunGlobal("^1.3.5", "1.3.5"),
    }


def test_reader_takes_names_from_the_manifest_and_versions_from_the_member(
    scratch_home: Path,
) -> None:
    _write_manifest(
        scratch_home,
        '{"dependencies": {"@earendil-works/pi-coding-agent": "1.5.2", "left-pad": "^1.0.0"}}',
    )
    _plant_member("@earendil-works/pi-coding-agent", '{"version": "1.5.2"}')
    _plant_member("left-pad", '{"version": "1.3.0"}')
    assert read_bun_globals() == {
        "@earendil-works/pi-coding-agent": BunGlobal("1.5.2", "1.5.2"),
        "left-pad": BunGlobal("^1.0.0", "1.3.0"),
    }
    assert listed_versions() == {"@earendil-works/pi-coding-agent": "1.5.2", "left-pad": "1.3.0"}


@pytest.mark.parametrize(
    "member",
    [None, b"\xff\xfe", "not json", '{"version": 3}', '{"version": "1.0 && rm"}', "[]"],
)
def test_reader_keeps_a_listed_package_with_an_unverifiable_member_at_version_none(
    scratch_home: Path, member: str | bytes | None
) -> None:
    _write_manifest(scratch_home, '{"dependencies": {"left-pad": "1.0.0"}}')
    if member is not None:
        _plant_member("left-pad", member)
    assert read_bun_globals() == {"left-pad": BunGlobal("1.0.0", None)}
    assert listed_versions() == {"left-pad": None}


def test_reader_reports_the_tree_as_bun_left_it_after_an_interrupted_run(
    scratch_home: Path,
) -> None:
    _write_manifest(scratch_home, '{"dependencies": {"left-pad": "1.0.0", "right-pad": "2.0.0"}}')
    _plant_member("right-pad", '{"version": "2.0.0"}')
    _plant_member("puppeteer", '{"version": "25.0.0"}')  # a kept peer: in node_modules only
    assert listed_versions() == {"left-pad": None, "right-pad": "2.0.0"}


def test_bun_keeps_a_package_whose_directory_is_still_in_the_tree() -> None:
    _plant_member("puppeteer", '{"version": "25.0.0"}')
    assert bun_keeps("puppeteer", "puppeteer") is True
    _plant_member("@mermaid-js/mermaid-cli", '{"version": "11.0.0"}')
    assert bun_keeps("@mermaid-js/mermaid-cli", "mmdc") is True


def test_bun_keeps_a_package_whose_bin_link_remains_even_when_dangling() -> None:
    link = bun_dirs()[0] / "mmdc"
    link.parent.mkdir(parents=True)
    link.symlink_to(bun_dirs()[1] / "node_modules" / "gone" / "cli.js")
    assert bun_keeps("@mermaid-js/mermaid-cli", "mmdc") is True


def test_bun_keeps_nothing_once_the_directory_and_link_are_gone() -> None:
    assert bun_keeps("puppeteer", "puppeteer") is False
    bun_dirs()[0].mkdir(parents=True)
    assert bun_keeps("@mermaid-js/mermaid-cli", "mmdc") is False


@pytest.mark.parametrize("package", ["../../etc", "Not/Valid", "", "a b"])
def test_bun_keeps_a_name_that_is_not_an_npm_package_name(package: str) -> None:
    """A name it cannot check is never reported removed, and never reaches a path join."""
    assert bun_keeps(package, "x") is True


def test_resolve_bun_finds_the_install_root_bin_beside_a_relocated_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    planted = _plant_bun(root / "bin")
    monkeypatch.setenv("BUN_INSTALL", str(root))
    monkeypatch.setenv("BUN_INSTALL_BIN", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("PATH", "")
    assert resolve_bun() == str(planted)


_DEEP = "[" * 100_000 + "]" * 100_000


def test_a_pathologically_nested_manifest_reads_as_unknown(scratch_home: Path) -> None:
    _write_manifest(scratch_home, _DEEP)
    assert trusted_dependencies() is None
    assert read_bun_globals() is None
    assert listed_versions() is None


def test_a_pathologically_nested_member_reads_as_version_none(scratch_home: Path) -> None:
    _write_manifest(scratch_home, '{"dependencies": {"left-pad": "1.0.0"}}')
    _plant_member("left-pad", _DEEP)
    assert read_bun_globals() == {"left-pad": BunGlobal("1.0.0", None)}
