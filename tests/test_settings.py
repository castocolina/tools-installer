import ast
import json
from pathlib import Path

import pytest

from installer.cli import parse_args
from installer.settings import (
    DEFAULT_LINK_MODE,
    LINK_MODES,
    LoadedSettings,
    Settings,
    SettingsStore,
    default_settings_path,
    link_mode_needs_choice,
    load_settings,
    resolve_link_mode,
    save_settings,
)
from installer.version_cache import default_cache_path


def test_link_modes_and_default() -> None:
    assert LINK_MODES == ("centralized", "single", "split")
    assert DEFAULT_LINK_MODE == "centralized"


def test_link_modes_match_cli_choices_both_ways() -> None:
    for mode in LINK_MODES:
        assert parse_args(["--link-mode", mode]).link_mode == mode

    source = Path("installer/cli.py").read_text()
    tree = ast.parse(source)
    choices: object = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and first.value == "--link-mode":
            for keyword in node.keywords:
                if keyword.arg == "choices":
                    choices = ast.literal_eval(keyword.value)
    assert choices == list(LINK_MODES)


def test_settings_default_is_never_chosen() -> None:
    assert Settings().link_mode is None
    assert Settings(link_mode="centralized").link_mode == "centralized"


def test_save_then_load_round_trips_split(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(path, Settings("split"))
    raw = json.loads(path.read_text())
    assert raw == {"version": 1, "link_mode": "split"}
    assert load_settings(path).settings == Settings("split")


def test_save_empty_settings_writes_json_null(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(path, Settings())
    raw = json.loads(path.read_text())
    assert raw == {"version": 1, "link_mode": None}
    assert load_settings(path).settings.link_mode is None


def test_load_literal_null_fixture_is_never_chosen(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"version": 1, "link_mode": null}')
    loaded = load_settings(path)
    assert loaded.settings == Settings()
    assert loaded.settings.link_mode is None


def test_save_settings_creates_missing_parent(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state" / "settings.json"
    save_settings(path, Settings("single"))
    assert path.is_file()
    assert load_settings(path).settings == Settings("single")


def test_missing_file_returns_never_chosen(tmp_path: Path) -> None:
    assert load_settings(tmp_path / "missing.json").settings == Settings()


def test_load_settings_invalid_utf8_returns_defaults_and_a_warning(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b'\xff\xfe{"link_mode": "split"}')
    loaded = load_settings(path)
    assert isinstance(loaded, LoadedSettings)
    assert loaded.settings == Settings()
    assert loaded.warning is not None
    assert str(path) in loaded.warning


def test_not_json_returns_never_chosen(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not json at all")
    loaded = load_settings(path)
    assert loaded.settings == Settings()
    assert loaded.warning is not None
    assert str(path) in loaded.warning


def test_wrong_json_shapes_return_never_chosen(tmp_path: Path) -> None:
    array_path = tmp_path / "array.json"
    array_path.write_text("[1, 2]")
    assert load_settings(array_path).settings == Settings()

    string_path = tmp_path / "string.json"
    string_path.write_text('"centralized"')
    assert load_settings(string_path).settings == Settings()

    number_path = tmp_path / "number.json"
    number_path.write_text('{"link_mode": 7}')
    assert load_settings(number_path).settings == Settings()


def test_tampered_link_mode_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"version": 1, "link_mode": "../../etc"}')
    assert load_settings(path).settings == Settings()


def test_default_settings_path_shares_parent_with_version_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    expected = tmp_path / ".local" / "state" / "tools-installer" / "settings.json"
    assert default_settings_path() == expected
    assert default_settings_path().parent == default_cache_path().parent


def test_writing_twice_leaves_one_file_and_no_temp_sibling(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(path, Settings("single"))
    save_settings(path, Settings("split"))
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["settings.json"]
    assert load_settings(path).settings == Settings("split")


def test_resolve_link_mode_flag_wins_over_stored() -> None:
    assert resolve_link_mode(flag="split", stored="single") == "split"


def test_resolve_link_mode_stored_wins_over_default() -> None:
    assert resolve_link_mode(flag=None, stored="single") == "single"


def test_resolve_link_mode_falls_back_to_default() -> None:
    assert resolve_link_mode(flag=None, stored=None) == DEFAULT_LINK_MODE


def test_link_mode_needs_choice_only_when_both_absent() -> None:
    assert link_mode_needs_choice(flag=None, stored=None) is True
    assert link_mode_needs_choice(flag="split", stored=None) is False
    assert link_mode_needs_choice(flag=None, stored="single") is False
    assert link_mode_needs_choice(flag="split", stored="single") is False


def test_settings_store_construction_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path, link_mode="single")
    assert store.link_mode == "single"
    assert store.path == path
    assert not path.exists()


def test_set_link_mode_is_live_and_persisted(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path, link_mode="single")
    store.set_link_mode("split")
    assert store.link_mode == "split"
    assert load_settings(path).settings.link_mode == "split"


def test_set_link_mode_rejects_unknown_value(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path, link_mode="single")
    with pytest.raises(ValueError, match="nope"):
        store.set_link_mode("nope")
    assert store.link_mode == "single"
    assert not path.exists()


def test_set_link_mode_propagates_oserror(tmp_path: Path) -> None:
    parent = tmp_path / "not-a-dir"
    parent.write_text("blocker")
    store = SettingsStore(parent / "settings.json", link_mode="single")
    with pytest.raises(OSError):
        store.set_link_mode("split")
