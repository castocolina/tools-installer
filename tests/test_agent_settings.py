import json
from pathlib import Path

import pytest

from installer.agent_settings import (
    SettingsEditRefused,
    SettingsParseError,
    insert_key,
    new_file_text,
    parse_settings,
    read_settings,
    remove_key,
    replace_value,
    same_value,
    strip_jsonc,
    write_if_unchanged,
)

VSCODE_SETTINGS = (
    '// VS Code user settings\n{\n  /* editor */\n  "editor.fontSize": 14, // size\n}\n'
)

CLAUDE_SETTINGS: dict[str, object] = {
    "model": "opus",
    "permissions": {"allow": ["Bash(ls)"]},
    "env": {"A": "1"},
}


def test_claude_settings_round_trip_is_byte_identical(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(CLAUDE_SETTINGS, indent=2) + "\n", encoding="utf-8")
    original = settings.read_bytes()
    before = read_settings(settings)
    assert before is not None

    first = insert_key(
        original.decode("utf-8"), "json", ("permissions", "defaultMode"), "bypassPermissions"
    )
    second = insert_key(first.text, "json", ("skipDangerousModePermissionPrompt",), True)
    write_if_unchanged(settings, before, second.text)

    doc = json.loads(settings.read_text(encoding="utf-8"))
    assert list(doc) == ["skipDangerousModePermissionPrompt", "model", "permissions", "env"]
    assert list(doc["permissions"]) == ["defaultMode", "allow"]
    assert doc["model"] == "opus"
    assert doc["env"] == {"A": "1"}

    current = read_settings(settings)
    assert current is not None
    reverted = remove_key(
        settings.read_text(encoding="utf-8"),
        "json",
        ("skipDangerousModePermissionPrompt",),
        fragment=second.fragment,
    )
    reverted = remove_key(reverted, "json", ("permissions", "defaultMode"), fragment=first.fragment)
    write_if_unchanged(settings, current, reverted)

    assert settings.read_bytes() == original


def test_insert_keeps_the_object_indent() -> None:
    text = json.dumps(CLAUDE_SETTINGS, indent=4) + "\n"

    root = insert_key(text, "json", ("flag",), True)
    nested = insert_key(text, "json", ("permissions", "defaultMode"), "x")

    assert '\n    "flag": true,\n    "model"' in root.text
    assert '\n        "defaultMode": "x",\n        "allow"' in nested.text


def test_a_reformatted_file_still_loses_only_our_key() -> None:
    text = json.dumps(CLAUDE_SETTINGS, indent=2) + "\n"
    inserted = insert_key(text, "json", ("skipDangerousModePermissionPrompt",), True)
    reserialized = json.dumps(json.loads(inserted.text), indent=4) + "\n"

    removed = remove_key(reserialized, "json", ("skipDangerousModePermissionPrompt",))

    assert json.loads(removed) == CLAUDE_SETTINGS


def test_the_guard_refuses_an_unintended_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SettingsParseError):
        insert_key('{"a": 1}\n{"b": 2}', "json", ("c",), 1)

    text = json.dumps({"model": "opus", "permissions": {"allow": []}}, indent=2) + "\n"
    with pytest.raises(SettingsEditRefused):
        insert_key(text, "json", ("model",), "other")

    permissions_open = text.index("{", text.index('"permissions"'))

    def misplaced_object_open(_text: str, _path: tuple[str, ...]) -> int:
        return permissions_open

    monkeypatch.setattr("installer.agent_settings._object_open", misplaced_object_open)
    with pytest.raises(SettingsEditRefused):
        insert_key(text, "json", ("flag",), True)


def test_an_invalid_json_file_is_refused_and_untouched(tmp_path: Path) -> None:
    text = '{"a": 1,,}'
    settings = tmp_path / "settings.json"
    settings.write_text(text, encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as expected:
        json.loads(text)

    with pytest.raises(SettingsParseError) as refused:
        insert_key(settings.read_text(encoding="utf-8"), "json", ("b",), 2)

    assert refused.value.fragment == f"not valid JSON (line 1, column {expected.value.colno})"
    assert settings.read_text(encoding="utf-8") == text

    with pytest.raises(SettingsParseError) as not_an_object:
        insert_key("[1, 2]", "json", ("b",), 2)
    assert not_an_object.value.fragment == "not valid JSON (line 1)"


def test_same_value_is_type_strict() -> None:
    assert not same_value(0, False)
    assert not same_value(1, True)
    assert same_value({"a": [1, {"b": True}]}, {"a": [1, {"b": True}]})
    assert not same_value({"a": 1}, {"a": True})


def test_strip_jsonc_keeps_positions_and_strings() -> None:
    text = '{\n  // line\n  "url": "https://x//y", /* block */\n  "list": [1, 2,],\n}\n'

    stripped = strip_jsonc(text)

    assert len(stripped) == len(text)
    assert [i for i, c in enumerate(text) if c == "\n"] == [
        i for i, c in enumerate(stripped) if c == "\n"
    ]
    assert json.loads(stripped) == {"url": "https://x//y", "list": [1, 2]}


def test_vscode_jsonc_round_trip_keeps_comments_and_the_user_key() -> None:
    first = insert_key(VSCODE_SETTINGS, "jsonc", ("telemetry.telemetryLevel",), "off")
    second = insert_key(
        first.text, "jsonc", ("files.watcherExclude",), {"**/node_modules/**": True}
    )

    assert "// VS Code user settings" in second.text
    assert "/* editor */" in second.text
    assert "// size" in second.text
    assert parse_settings(second.text, "jsonc") == {
        "editor.fontSize": 14,
        "telemetry.telemetryLevel": "off",
        "files.watcherExclude": {"**/node_modules/**": True},
    }

    reverted = remove_key(second.text, "jsonc", ("files.watcherExclude",), fragment=second.fragment)
    reverted = remove_key(reverted, "jsonc", ("telemetry.telemetryLevel",), fragment=first.fragment)
    assert reverted == VSCODE_SETTINGS


def test_a_created_parent_round_trips() -> None:
    original = '{"model": "x"}'

    first = insert_key(original, "jsonc", ("attribution", "commit"), "")
    assert first.created_parent
    assert parse_settings(first.text, "jsonc")["attribution"] == {"commit": ""}

    second = insert_key(first.text, "jsonc", ("attribution", "pr"), "")
    assert not second.created_parent
    assert '{"pr": "", "commit": ""}' in second.text

    reverted = remove_key(second.text, "jsonc", ("attribution", "pr"), fragment=second.fragment)
    reverted = remove_key(reverted, "jsonc", ("attribution", "commit"))
    reverted = remove_key(reverted, "jsonc", ("attribution",), fragment=first.fragment)
    assert reverted == original

    with pytest.raises(SettingsEditRefused):
        insert_key(original, "jsonc", ("a", "b", "c"), 1)


def test_an_empty_object_round_trips() -> None:
    for original in ("{}", "{\n}"):
        inserted = insert_key(original, "jsonc", ("k",), 1)
        assert remove_key(inserted.text, "jsonc", ("k",), fragment=inserted.fragment) == original


def test_a_new_file_starts_from_an_empty_object() -> None:
    text = new_file_text("jsonc")
    assert text == "{}\n"

    inserted = insert_key(text, "jsonc", ("k",), 1)

    assert parse_settings(inserted.text, "jsonc") == {"k": 1}
    assert remove_key(inserted.text, "jsonc", ("k",), fragment=inserted.fragment) == "{}\n"


def test_replace_value_swaps_a_default_and_back() -> None:
    original = '{"attribution": {"attributeCommitsToAgent": true, "attributePRsToAgent": true}}'
    path = ("attribution", "attributeCommitsToAgent")

    swapped = replace_value(original, "jsonc", path, False)

    assert swapped == original.replace(
        '"attributeCommitsToAgent": true', '"attributeCommitsToAgent": false'
    )
    assert replace_value(swapped, "jsonc", path, True) == original


def test_a_member_cut_without_its_fragment_takes_its_comma_and_keeps_comments() -> None:
    text = '// header\n{\n  // c\n  "a": 1,\n  "b": 2, // tail\n}\n'

    assert remove_key(text, "jsonc", ("b",)) == '// header\n{\n  // c\n  "a": 1\n}\n'
    assert remove_key(text, "jsonc", ("a",)) == '// header\n{\n  // c\n  "b": 2, // tail\n}\n'


def test_an_invalid_jsonc_file_names_line_and_column() -> None:
    with pytest.raises(SettingsParseError) as refused:
        insert_key('{\n  "a": 1,\n  "b: 2\n}\n', "jsonc", ("c",), 3)

    assert refused.value.fragment.startswith("not valid JSONC (line 3, column")
