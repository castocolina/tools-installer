"""Cross-cutting consistency guards for terminal JSON catalog entries."""

from pathlib import Path
from typing import cast

from installer.herdr_app_keys import herdr_app_keys_path, herdr_app_owned_keys, parse_chord
from installer.iterm2_profile import OWN_ROWS, parse_keystroke, profile_path
from installer.model import load_tools
from installer.terminal_keys import TERMINAL_KEYS, OwnedKeys, OwnedRegion, WholeFile

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def test_every_terminal_row_has_its_ownership_variant() -> None:
    variants = {
        "alacritty": OwnedRegion,
        "kitty": OwnedRegion,
        "wezterm": OwnedRegion,
        "ghostty": OwnedRegion,
        "iterm2": WholeFile,
        "herdr-app": OwnedKeys,
    }
    assert set(TERMINAL_KEYS) == set(variants)
    for tool_id, variant in variants.items():
        assert isinstance(TERMINAL_KEYS[tool_id].ownership, variant)


def test_herdr_app_config_paths_cover_the_default_keys_folder(tmp_path: Path) -> None:
    app = next(tool for tool in load_tools(REGISTRY) if tool.id == "herdr-app")
    paths = {tmp_path / path.removeprefix("~/") for path in app.config_paths}
    for platform_os in ("fedora", "macos"):
        folder = herdr_app_keys_path(platform_os, tmp_path, {}).parent
        assert folder == tmp_path / ".config/herdr-app"
        assert folder in paths
        for variable in ("XDG_CONFIG_HOME", "HERDR_APP_HOME"):
            moved = herdr_app_keys_path(platform_os, tmp_path, {variable: str(tmp_path / "moved")})
            assert moved.parent != folder and moved.parent not in paths


def test_iterm2_declares_no_config_paths_and_its_profile_is_under_the_documented_folder(
    tmp_path: Path,
) -> None:
    iterm = next(tool for tool in load_tools(REGISTRY) if tool.id == "iterm2")
    assert not iterm.config_paths
    path = profile_path(tmp_path)
    assert path.parent == tmp_path / "Library/Application Support/iTerm2/DynamicProfiles"
    assert path.name == "tools-installer.json"


def test_herdr_app_paths_are_the_apps_own_files_only() -> None:
    tools = load_tools(REGISTRY)
    app = next(tool for tool in tools if tool.id == "herdr-app")
    script = next(method for method in app.methods if method.kind == "script")
    paths = script.params["paths"]
    assert paths == [
        "~/.local/share/herdr-app/",
        "~/.local/bin/herdr-app",
        "~/.local/share/applications/herdr-app.desktop",
        "~/.local/share/icons/hicolor/scalable/apps/herdr-app.svg",
    ]
    assert isinstance(paths, list)
    assert not set(cast(list[str], paths)) & {
        "~/.local/bin/",
        "~/.local/share/",
        "~/.local/share/applications/",
        "~/.local/share/icons/",
    }
    for tool in tools:
        for method in tool.methods:
            declared = method.params.get("paths", [])
            assert isinstance(declared, list)
            for path in cast(list[object], declared):
                assert isinstance(path, str)
                assert "herdr-core" not in path and not path.rstrip("/").endswith("/hc")


def test_no_owned_key_uses_the_spellings_the_app_rejects() -> None:
    for platform_os in ("fedora", "debian", "arch", "macos"):
        for (_, chord), _ in herdr_app_owned_keys(platform_os):
            assert not chord.startswith(("option-", "platform-"))
            assert parse_chord(chord, platform_os) is not None
    for name, key, action in OWN_ROWS:
        assert name and action
        assert parse_keystroke(key) is not None


def test_the_record_names_follow_the_naming_rule() -> None:
    assert TERMINAL_KEYS["iterm2"].created_record == "terminal-iterm2-created"
    assert TERMINAL_KEYS["herdr-app"].created_record == "terminal-herdr-app-created"
    for tool_id, row in TERMINAL_KEYS.items():
        assert row.created_record == f"terminal-{tool_id}-created"
