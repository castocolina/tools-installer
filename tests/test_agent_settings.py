import importlib.util
import json
import os
import re
import tomllib
from pathlib import Path

import pytest

from installer import agent_settings, receipts
from installer.agent_settings import (
    CHANGED_WHILE_WRITING,
    FileResult,
    SettingsChanged,
    SettingsEditRefused,
    SettingsParseError,
    SettingsUnreadable,
    apply_setting,
    delete_if_unchanged,
    file_problem,
    insert_key,
    ledger_summary,
    new_file_text,
    parse_settings,
    read_settings,
    remove_key,
    replace_value,
    revert_agent,
    same_value,
    setting_state,
    strip_jsonc,
    write_if_unchanged,
)
from installer.app import settings_change_lines
from installer.atomic import FileSnapshot
from installer.receipts import ConfigLedger, ConfigWrite, read_ledger, write_ledger

ROOT = Path(__file__).resolve().parent.parent

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


CODEX_CONFIG = (
    'model = "gpt"\n'
    'model_reasoning_effort = "high"\n'
    "# written by codex\n"
    "[features]\n"
    "x = true\n"
    '[projects."/home/x/repo"]\n'
    'trust_level = "trusted"\n'
)


def test_codex_toml_round_trip_inserts_before_the_first_table() -> None:
    first = insert_key(CODEX_CONFIG, "toml", ("approval_policy",), "never")
    second = insert_key(first.text, "toml", ("sandbox_mode",), "danger-full-access")

    assert second.text.index('sandbox_mode = "danger-full-access"') < second.text.index(
        "[features]"
    )
    doc = tomllib.loads(second.text)
    assert doc["approval_policy"] == "never"
    assert doc["sandbox_mode"] == "danger-full-access"
    assert doc["features"] == {"x": True}

    reverted = remove_key(second.text, "toml", ("sandbox_mode",), fragment=second.fragment)
    reverted = remove_key(reverted, "toml", ("approval_policy",), fragment=first.fragment)
    assert reverted == CODEX_CONFIG

    with pytest.raises(SettingsEditRefused):
        insert_key(CODEX_CONFIG, "toml", ("features", "x"), 1)
    with pytest.raises(SettingsEditRefused):
        insert_key(CODEX_CONFIG, "toml", ("a b",), "x")
    with pytest.raises(SettingsEditRefused):
        insert_key(CODEX_CONFIG, "toml", ("count",), 3)
    with pytest.raises(SettingsEditRefused):
        replace_value(CODEX_CONFIG, "toml", ("model",), "o3")


def test_a_toml_file_without_a_final_newline_round_trips() -> None:
    original = 'model = "gpt"'

    inserted = insert_key(original, "toml", ("approval_policy",), "never")

    assert (
        remove_key(inserted.text, "toml", ("approval_policy",), fragment=inserted.fragment)
        == original
    )


def test_a_toml_splice_never_lands_inside_an_array() -> None:
    inserted = insert_key("arr = [\n  [1, 2],\n  [3],\n]\n", "toml", ("k",), "v")
    assert inserted.text == 'arr = [\n  [1, 2],\n  [3],\n]\nk = "v"\n'


def test_an_invalid_toml_file_names_the_line() -> None:
    with pytest.raises(SettingsParseError) as at_column:
        insert_key("a = \n", "toml", ("b",), 1)
    assert at_column.value.fragment == "not valid TOML (line 1, column 5)"

    with pytest.raises(SettingsParseError) as at_end:
        insert_key('a = """\nxyz\n', "toml", ("b",), 1)
    assert at_end.value.fragment == "not valid TOML (line 2)"


def test_a_file_changed_between_read_and_write_is_not_written(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('model = "gpt"\n', encoding="utf-8")
    before = read_settings(config)
    assert before is not None
    config.write_text('model = "other"\n', encoding="utf-8")

    with pytest.raises(SettingsChanged, match="changed while being written"):
        write_if_unchanged(config, before, 'model = "gpt"\napproval_policy = "never"\n')
    assert config.read_text(encoding="utf-8") == 'model = "other"\n'

    with pytest.raises(SettingsChanged):
        delete_if_unchanged(config, before)
    assert config.read_text(encoding="utf-8") == 'model = "other"\n'

    created_later = tmp_path / "new.toml"
    assert read_settings(created_later) is None
    created_later.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SettingsChanged):
        write_if_unchanged(created_later, None, "y = 2\n")
    assert created_later.read_text(encoding="utf-8") == "x = 1\n"


def test_a_symlinked_settings_file_is_edited_through_its_target(tmp_path: Path) -> None:
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "settings.json"
    target.write_text('{\n  "model": "opus"\n}\n', encoding="utf-8")
    link = tmp_path / "settings.json"
    link.symlink_to(target)
    before = read_settings(link)
    assert before is not None

    inserted = insert_key(before.data.decode("utf-8"), "json", ("flag",), True)
    write_if_unchanged(link, before, inserted.text)

    assert link.is_symlink()
    assert json.loads(target.read_text(encoding="utf-8")) == {"model": "opus", "flag": True}


def _reverted(agent: str, *, home: Path) -> FileResult:
    """The one FileResult of reverting everything the ledger records for `agent`."""
    (result,) = revert_agent(agent, home=home, platform_os="linux")
    return result


def _claude_settings_file() -> Path:
    path = Path.home() / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_claude_auto_approve_writes_records_and_reverts_byte_identical() -> None:
    settings = _claude_settings_file()
    original = (
        json.dumps({"model": "opus", "permissions": {"allow": ["Bash(ls)"]}}, indent=2) + "\n"
    )
    settings.write_text(original, encoding="utf-8")
    home = Path.home()

    applied = apply_setting("claude", "auto-approve", home=home, platform_os="linux")

    assert applied.refused is None
    assert [(key.key, key.kind) for key in applied.keys] == [
        ("permissions.defaultMode", "wrote"),
        ("skipDangerousModePermissionPrompt", "wrote"),
    ]
    written = json.loads(settings.read_text(encoding="utf-8"))
    assert written["model"] == "opus"
    assert written["permissions"] == {"allow": ["Bash(ls)"], "defaultMode": "bypassPermissions"}
    assert written["skipDangerousModePermissionPrompt"] is True
    ledger = read_ledger("claude")
    assert ledger is not None
    assert [entry.key_path for entry in ledger.entries] == [
        ("permissions", "defaultMode"),
        ("skipDangerousModePermissionPrompt",),
    ]

    reverted = _reverted("claude", home=home)

    assert [key.kind for key in reverted.keys] == ["removed", "removed"]
    assert settings.read_text(encoding="utf-8") == original
    assert read_ledger("claude") is None


def test_a_user_accept_edits_stays_and_reads_set_by_you() -> None:
    settings = _claude_settings_file()
    settings.write_text('{"permissions": {"defaultMode": "acceptEdits"}}\n', encoding="utf-8")
    home = Path.home()

    applied = apply_setting("claude", "auto-approve", home=home, platform_os="linux")

    assert [(key.key, key.kind, key.value) for key in applied.keys] == [
        ("permissions.defaultMode", "set_by_you", '"acceptEdits"'),
        ("skipDangerousModePermissionPrompt", "wrote", "true"),
    ]
    ledger = read_ledger("claude")
    assert ledger is not None
    assert [entry.key_path for entry in ledger.entries] == [("skipDangerousModePermissionPrompt",)]

    reverted = _reverted("claude", home=home)

    assert [key.kind for key in reverted.keys] == ["removed"]
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "permissions": {"defaultMode": "acceptEdits"}
    }


def test_a_missing_settings_file_is_created_and_deleted_on_revert() -> None:
    home = Path.home()
    settings = home / ".claude" / "settings.json"
    assert not settings.exists()

    apply_setting("claude", "auto-approve", home=home, platform_os="linux")

    assert json.loads(settings.read_text(encoding="utf-8")) == {
        "permissions": {"defaultMode": "bypassPermissions"},
        "skipDangerousModePermissionPrompt": True,
    }
    ledger = read_ledger("claude")
    assert ledger is not None
    assert ledger.created_files == (str(settings),)

    _reverted("claude", home=home)

    assert not settings.exists()
    assert read_ledger("claude") is None


def test_an_invalid_settings_file_is_refused_and_byte_identical() -> None:
    settings = _claude_settings_file()
    original = '{"a": 1,,}'
    settings.write_text(original, encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as caught:
        json.loads(original)

    applied = apply_setting("claude", "auto-approve", home=Path.home(), platform_os="linux")

    assert applied.refused == (
        f"not valid JSON (line {caught.value.lineno}, column {caught.value.colno})"
    )
    assert applied.keys == ()
    assert settings.read_text(encoding="utf-8") == original
    assert read_ledger("claude") is None


def test_setting_state_reads_each_state() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    assert setting_state("claude", "auto-approve", home=home, platform_os="linux") == "off"

    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    assert setting_state("claude", "auto-approve", home=home, platform_os="linux") == "on"

    settings.write_text('{"permissions": {"defaultMode": "acceptEdits"}}\n', encoding="utf-8")
    assert setting_state("claude", "auto-approve", home=home, platform_os="linux") == "drift"

    settings.write_text(
        json.dumps(
            {
                "permissions": {"defaultMode": "bypassPermissions"},
                "skipDangerousModePermissionPrompt": True,
            }
        ),
        encoding="utf-8",
    )
    write_ledger(ConfigLedger("claude"))
    assert setting_state("claude", "auto-approve", home=home, platform_os="linux") == "yours"


def test_setting_facts_split_written_yours_already_and_drift() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    keys = ("permissions.defaultMode", "skipDangerousModePermissionPrompt")

    def facts() -> agent_settings.SettingFacts:
        return agent_settings.setting_facts(
            "claude", "auto-approve", home=home, platform_os="linux"
        )

    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    recorded = facts()
    assert (recorded.written, recorded.set_by_you, recorded.already, recorded.drifted) == (
        keys,
        (),
        (),
        (),
    )

    settings.write_text('{"permissions": {"defaultMode": "acceptEdits"}}\n', encoding="utf-8")
    drifted = facts()
    assert (drifted.written, drifted.drifted) == ((), keys)

    write_ledger(ConfigLedger("claude"))
    yours = facts()
    assert yours.set_by_you == (("permissions.defaultMode", '"acceptEdits"'),)
    assert yours.written == yours.already == yours.drifted == ()

    settings.write_text(
        json.dumps(
            {
                "permissions": {"defaultMode": "bypassPermissions"},
                "skipDangerousModePermissionPrompt": True,
            }
        ),
        encoding="utf-8",
    )
    assert facts().already == keys


def test_setting_facts_absent_lists_only_unrecorded_missing_keys_in_order() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    keys = ("permissions.defaultMode", "skipDangerousModePermissionPrompt")

    def absent() -> tuple[str, ...]:
        return agent_settings.setting_facts(
            "claude", "auto-approve", home=home, platform_os="linux"
        ).absent

    # no file and no ledger yet: both keys read absent
    assert absent() == keys

    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    assert absent() == ()

    settings.write_text("{}\n", encoding="utf-8")  # recorded then deleted: the user's choice
    assert absent() == ()

    write_ledger(ConfigLedger("claude"))  # never recorded: absent again
    assert absent() == keys

    settings.write_text('{"skipDangerousModePermissionPrompt": false}\n', encoding="utf-8")
    assert absent() == ("permissions.defaultMode",)


def test_setting_facts_treat_a_non_object_parent_as_set_by_you_not_absent() -> None:
    """C-02: the writer refuses a key under a non-object parent as `set_by_you`, so the
    facts must too, or the `≈` step it raises could never clear."""
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"permissions": "none"}\n', encoding="utf-8")

    facts = agent_settings.setting_facts("claude", "auto-approve", home=home, platform_os="linux")
    assert facts.absent == ("skipDangerousModePermissionPrompt",)
    assert [key for key, _ in facts.set_by_you] == ["permissions.defaultMode"]

    applied = apply_setting(
        "claude", "auto-approve", home=home, platform_os="linux", skip_recorded=True
    )
    assert [key.kind for key in applied.keys] == ["set_by_you", "wrote"]
    after = agent_settings.setting_facts("claude", "auto-approve", home=home, platform_os="linux")
    assert after.absent == ()


def test_apply_setting_skip_recorded_never_rewrites_a_recorded_key() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")

    skipped = apply_setting(
        "claude", "auto-approve", home=home, platform_os="linux", skip_recorded=True
    )
    assert skipped.keys == ()
    assert settings.read_text(encoding="utf-8") == '{"model": "opus"}\n'
    ledger = read_ledger("claude")
    assert ledger is not None and len(ledger.entries) == 2  # the record survives

    rewritten = apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    assert [key.kind for key in rewritten.keys] == ["wrote", "wrote"]


def test_apply_on_drift_rewrites_absent_keys_and_forgets_changed_ones() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")
    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    settings.write_text(
        '{"model": "opus", "permissions": {"defaultMode": "acceptEdits"}}\n', encoding="utf-8"
    )
    assert setting_state("claude", "auto-approve", home=home, platform_os="linux") == "drift"

    applied = apply_setting("claude", "auto-approve", home=home, platform_os="linux")

    assert [(key.key, key.kind) for key in applied.keys] == [
        ("permissions.defaultMode", "set_by_you"),
        ("skipDangerousModePermissionPrompt", "wrote"),
    ]
    ledger = read_ledger("claude")
    assert ledger is not None
    assert [entry.key_path for entry in ledger.entries] == [("skipDangerousModePermissionPrompt",)]
    assert setting_state("claude", "auto-approve", home=home, platform_os="linux") == "on"


def test_an_unparsable_file_is_unreadable_only_with_a_ledger_record() -> None:
    home = Path.home()
    codex = home / ".codex" / "config.toml"
    codex.parent.mkdir(parents=True, exist_ok=True)
    codex.write_text('approval_policy = "never"\n[features\n', encoding="utf-8")
    problem = file_problem("codex", home=home, platform_os="linux")
    assert problem is not None
    assert problem.startswith("not valid TOML (line ")
    assert setting_state("codex", "auto-approve", home=home, platform_os="linux") == "off"

    entry = ConfigWrite(
        "auto-approve", str(codex), ("approval_policy",), "never", 'approval_policy = "never"\n'
    )
    write_ledger(ConfigLedger("codex", entries=(entry,)))
    with pytest.raises(SettingsUnreadable) as caught:
        setting_state("codex", "auto-approve", home=home, platform_os="linux")
    assert (
        str(caught.value)
        == f"~/.codex/config.toml is {problem}; nothing is written until it parses"
    )


def test_a_tampered_ledger_never_removes_a_user_key() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")
    other = home / ".claude" / "other.json"
    other.write_text('{"skipDangerousModePermissionPrompt": true}\n', encoding="utf-8")
    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    ledger = read_ledger("claude")
    assert ledger is not None
    forged = (
        ConfigWrite("auto-approve", str(settings), ("model",), "opus", '\n  "model": "opus"'),
        ConfigWrite(
            "auto-approve",
            str(other),
            ("skipDangerousModePermissionPrompt",),
            True,
            '\n  "skipDangerousModePermissionPrompt": true',
        ),
    )
    write_ledger(ConfigLedger("claude", ledger.created_files, ledger.entries + forged))
    other_before = other.read_bytes()

    reverted = revert_agent("claude", home=home, platform_os="linux")

    assert {key.key for result in reverted for key in result.keys} <= {
        "permissions.defaultMode",
        "skipDangerousModePermissionPrompt",
    }
    assert json.loads(settings.read_text(encoding="utf-8")) == {"model": "opus"}
    assert other.read_bytes() == other_before


def test_a_file_that_changes_mid_write_is_retried_once_then_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")
    real_write = agent_settings.write_if_unchanged
    attempts: list[int] = []

    def changed_once(path: Path, before: FileSnapshot | None, text: str) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise SettingsChanged()
        real_write(path, before, text)

    monkeypatch.setattr(agent_settings, "write_if_unchanged", changed_once)
    applied = apply_setting("claude", "auto-approve", home=home, platform_os="linux")

    assert applied.refused is None
    assert [key.kind for key in applied.keys] == ["wrote", "wrote"]
    assert len(attempts) == 2
    assert json.loads(settings.read_text(encoding="utf-8"))["skipDangerousModePermissionPrompt"]

    other_writer = '{"model": "sonnet"}\n'
    settings.write_text(other_writer, encoding="utf-8")
    ledger_before = read_ledger("claude")

    def always_changed(path: Path, before: FileSnapshot | None, text: str) -> None:
        raise SettingsChanged()

    monkeypatch.setattr(agent_settings, "write_if_unchanged", always_changed)
    applied = apply_setting("claude", "auto-approve", home=home, platform_os="linux")

    assert applied.refused == CHANGED_WHILE_WRITING
    assert settings.read_text(encoding="utf-8") == other_writer
    assert read_ledger("claude") == ledger_before


def test_opencode_prefers_the_existing_jsonc_and_refuses_both() -> None:
    home = Path.home()
    base = home / ".config" / "opencode"
    base.mkdir(parents=True, exist_ok=True)
    jsonc = base / "opencode.jsonc"
    plain = base / "opencode.json"
    jsonc.write_text('// opencode\n{\n  /* theme */\n  "theme": "dark",\n}\n', encoding="utf-8")

    applied = apply_setting("opencode", "auto-approve", home=home, platform_os="linux")

    assert applied.refused is None
    assert applied.path == jsonc
    assert [key.kind for key in applied.keys] == ["wrote"]
    text = jsonc.read_text(encoding="utf-8")
    assert "// opencode" in text
    assert "/* theme */" in text
    assert json.loads(strip_jsonc(text)) == {"theme": "dark", "permission": "allow"}
    assert not plain.exists()

    jsonc.unlink()
    applied = apply_setting("opencode", "auto-approve", home=home, platform_os="linux")
    assert applied.path == plain
    assert json.loads(plain.read_text(encoding="utf-8")) == {"permission": "allow"}

    jsonc.write_text("{}\n", encoding="utf-8")
    plain_before = plain.read_bytes()
    jsonc_before = jsonc.read_bytes()
    applied = apply_setting("opencode", "auto-approve", home=home, platform_os="linux")
    assert applied.refused == "both opencode.json and opencode.jsonc exist"
    assert plain.read_bytes() == plain_before
    assert jsonc.read_bytes() == jsonc_before


def test_codex_auto_approve_goes_to_the_top_level() -> None:
    home = Path.home()
    codex = home / ".codex" / "config.toml"
    codex.parent.mkdir(parents=True, exist_ok=True)
    original = (
        'model = "gpt"\n\n[features]\nfoo = true\n\n[projects."/x"]\ntrust_level = "trusted"\n'
    )
    codex.write_text(original, encoding="utf-8")

    applied = apply_setting("codex", "auto-approve", home=home, platform_os="linux")

    assert [key.kind for key in applied.keys] == ["wrote", "wrote"]
    text = codex.read_text(encoding="utf-8")
    assert text.index('approval_policy = "never"') < text.index("[features]")
    assert text.index('sandbox_mode = "danger-full-access"') < text.index("[features]")
    doc = tomllib.loads(text)
    assert doc["approval_policy"] == "never"
    assert doc["sandbox_mode"] == "danger-full-access"

    _reverted("codex", home=home)

    assert codex.read_text(encoding="utf-8") == original


def test_claude_attribution_uses_empty_strings() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    original = '{"model": "opus"}\n'
    settings.write_text(original, encoding="utf-8")

    applied = apply_setting("claude", "no-attribution", home=home, platform_os="linux")

    assert [(key.key, key.kind, key.value) for key in applied.keys] == [
        ("attribution.commit", "wrote", '""'),
        ("attribution.pr", "wrote", '""'),
    ]
    assert json.loads(settings.read_text(encoding="utf-8"))["attribution"] == {
        "commit": "",
        "pr": "",
    }

    _reverted("claude", home=home)

    assert settings.read_text(encoding="utf-8") == original


def test_cursor_attribution_replaces_cli_defaults_and_restores_them() -> None:
    home = Path.home()
    cursor = home / ".cursor" / "cli-config.json"
    cursor.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(
        {
            "approvalMode": "allowlist",
            "attribution": {"attributeCommitsToAgent": True, "attributePRsToAgent": True},
        },
        indent=2,
    )
    cursor.write_text(original + "\n", encoding="utf-8")

    applied = apply_setting("cursor-agent", "no-attribution", home=home, platform_os="linux")

    assert [key.kind for key in applied.keys] == ["replaced_default", "replaced_default"]
    doc = json.loads(cursor.read_text(encoding="utf-8"))
    assert doc["attribution"] == {"attributeCommitsToAgent": False, "attributePRsToAgent": False}

    user = apply_setting("cursor-agent", "auto-approve", home=home, platform_os="linux")
    assert [(key.key, key.kind, key.value) for key in user.keys] == [
        ("approvalMode", "set_by_you", '"allowlist"')
    ]

    doc["attribution"]["attributeCommitsToAgent"] = True
    cursor.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    reverted = _reverted("cursor-agent", home=home)

    assert {(key.key, key.kind) for key in reverted.keys} == {
        ("attribution.attributePRsToAgent", "removed"),
        ("attribution.attributeCommitsToAgent", "kept_changed"),
    }
    restored = json.loads(cursor.read_text(encoding="utf-8"))
    assert restored["attribution"]["attributeCommitsToAgent"] is True
    assert restored["attribution"]["attributePRsToAgent"] is True


def test_vscode_lean_adds_only_absent_keys_and_keeps_comments() -> None:
    home = Path.home()
    vscode = home / ".config" / "Code" / "User" / "settings.json"
    vscode.parent.mkdir(parents=True, exist_ok=True)
    original = '// VS Code user settings\n{\n  /* editor */\n  "editor.minimap.enabled": true,\n}\n'
    vscode.write_text(original, encoding="utf-8")

    applied = apply_setting("vscode", "vscode-lean", home=home, platform_os="linux")

    kinds = {key.key: key.kind for key in applied.keys}
    assert kinds["editor.minimap.enabled"] == "set_by_you"
    assert kinds["terminal.integrated.defaultProfile.linux"] == "wrote"
    assert "update.mode" not in kinds
    assert {kind for key, kind in kinds.items() if key != "editor.minimap.enabled"} == {"wrote"}
    text = vscode.read_text(encoding="utf-8")
    assert "// VS Code user settings" in text
    assert "/* editor */" in text
    doc = json.loads(strip_jsonc(text))
    assert doc["editor.minimap.enabled"] is True
    assert doc["terminal.integrated.defaultProfile.linux"] == "zsh"

    _reverted("vscode", home=home)

    assert vscode.read_text(encoding="utf-8") == original


def test_vscode_lean_on_macos_sets_update_mode_and_the_osx_profile() -> None:
    home = Path.home()
    path = home / "Library" / "Application Support" / "Code" / "User" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")

    applied = apply_setting("vscode", "vscode-lean", home=home, platform_os="macos")

    assert applied.path == path
    kinds = {key.key: key.kind for key in applied.keys}
    assert kinds["update.mode"] == "wrote"
    assert kinds["terminal.integrated.defaultProfile.osx"] == "wrote"
    assert "terminal.integrated.defaultProfile.linux" not in kinds
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["update.mode"] == "none"
    assert doc["terminal.integrated.defaultProfile.osx"] == "zsh"


def test_vscode_ai_off_and_ext_updates_off_are_separate_settings() -> None:
    home = Path.home()
    path = home / ".config" / "Code" / "User" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")

    ai = apply_setting("vscode", "vscode-ai-off", home=home, platform_os="linux")
    ext = apply_setting("vscode", "vscode-ext-updates-off", home=home, platform_os="linux")

    assert [key.key for key in ai.keys] == ["chat.disableAIFeatures"]
    assert [key.key for key in ext.keys] == ["extensions.autoUpdate", "extensions.autoCheckUpdates"]
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "chat.disableAIFeatures": True,
        "extensions.autoUpdate": False,
        "extensions.autoCheckUpdates": False,
    }

    revert_agent("vscode", home=home, platform_os="linux")

    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_revert_agent_and_ledger_summary_cover_every_setting() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")
    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    apply_setting("claude", "no-attribution", home=home, platform_os="linux")

    summary = ledger_summary("claude", home=home)
    assert summary == (
        (
            settings,
            (
                "permissions.defaultMode",
                "skipDangerousModePermissionPrompt",
                "attribution.commit",
                "attribution.pr",
            ),
        ),
    )

    results = revert_agent("claude", home=home, platform_os="linux")

    assert {result.setting for result in results} == {"auto-approve", "no-attribution"}
    assert read_ledger("claude") is None
    assert json.loads(settings.read_text(encoding="utf-8")) == {"model": "opus"}


def test_vscode_lean_on_fedora_writes_the_linux_profile() -> None:
    home = Path.home()
    path = home / ".config" / "Code" / "User" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")

    applied = apply_setting("vscode", "vscode-lean", home=home, platform_os="fedora")

    assert applied.refused is None
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["terminal.integrated.defaultProfile.linux"] == "zsh"
    assert "update.mode" not in doc


def test_a_user_zero_is_not_our_false() -> None:
    home = Path.home()
    cursor = home / ".cursor" / "cli-config.json"
    cursor.parent.mkdir(parents=True, exist_ok=True)
    cursor.write_text('{"attribution": {"attributeCommitsToAgent": 0}}\n', encoding="utf-8")

    applied = apply_setting("cursor-agent", "no-attribution", home=home, platform_os="linux")

    kinds = {key.key: (key.kind, key.value) for key in applied.keys}
    assert kinds["attribution.attributeCommitsToAgent"] == ("set_by_you", "0")
    ledger = read_ledger("cursor-agent")
    assert ledger is not None
    assert all(
        entry.key_path != ("attribution", "attributeCommitsToAgent") for entry in ledger.entries
    )

    forged = ConfigWrite(
        "no-attribution",
        str(cursor),
        ("attribution", "attributeCommitsToAgent"),
        False,
        '"attributeCommitsToAgent": false',
        replaced_default=True,
    )
    write_ledger(ConfigLedger("cursor-agent", ledger.created_files, (*ledger.entries, forged)))
    reverted = _reverted("cursor-agent", home=home)

    assert {key.key: key.kind for key in reverted.keys}["attribution.attributeCommitsToAgent"] == (
        "kept_changed"
    )
    assert (
        json.loads(cursor.read_text(encoding="utf-8"))["attribution"]["attributeCommitsToAgent"]
        == 0
    )


def test_opencode_json_has_a_single_writer() -> None:
    assert importlib.util.find_spec("installer.agent_policy") is None
    assert importlib.util.find_spec("installer.agent_guidance") is None
    importers = {
        source.name
        for source in (ROOT / "installer").glob("*.py")
        if re.search(
            r"^from installer(\.agent_env| import .*\bagent_env\b)", source.read_text("utf-8"), re.M
        )
    }
    assert importers == {"agent_settings.py"}
    policy_source = (ROOT / "installer" / "policy.py").read_text(encoding="utf-8")
    for name in (
        "AgentEnvironmentPolicy",
        "agent_environment_policy",
        "compose_agent_environment_policy",
    ):
        assert f"def {name}(" not in policy_source
        assert f"class {name}" not in policy_source


def test_vscode_lean_reverts_after_vscode_appends_a_user_key() -> None:
    home = Path.home()
    path = home / ".config" / "Code" / "User" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    apply_setting("vscode", "vscode-lean", home=home, platform_os="linux")
    text = path.read_text(encoding="utf-8")
    close = text.rstrip().rfind("}")
    path.write_text(text[:close] + ',\n  "workbench.colorTheme": "x"\n' + text[close:], "utf-8")

    reverted = _reverted("vscode", home=home)

    assert reverted.refused is None
    assert {key.kind for key in reverted.keys} == {"removed"}
    assert path.read_text(encoding="utf-8") == '{\n  "workbench.colorTheme": "x"\n}\n'
    assert read_ledger("vscode") is None


def test_opencode_and_a_created_claude_parent_revert_after_a_user_key_follows() -> None:
    home = Path.home()
    opencode = home / ".config" / "opencode" / "opencode.json"
    opencode.parent.mkdir(parents=True, exist_ok=True)
    opencode.write_text("{}\n", encoding="utf-8")
    apply_setting("opencode", "auto-approve", home=home, platform_os="linux")
    opencode.write_text(
        opencode.read_text(encoding="utf-8").replace('"allow"', '"allow", "theme": "dark"'),
        "utf-8",
    )
    claude = _claude_settings_file()
    claude.write_text('{"model": "opus"}\n', encoding="utf-8")
    apply_setting("claude", "no-attribution", home=home, platform_os="linux")
    claude.write_text(
        claude.read_text(encoding="utf-8").replace('"commit": ""}', '"commit": ""}, "x": 1'),
        "utf-8",
    )

    for agent in ("opencode", "claude"):
        assert _reverted(agent, home=home).refused is None

    assert json.loads(opencode.read_text(encoding="utf-8")) == {"theme": "dark"}
    assert json.loads(claude.read_text(encoding="utf-8")) == {"x": 1, "model": "opus"}


def test_jsonc_block_comments_never_reach_across_each_other() -> None:
    assert parse_settings('{"a": 1, /* c */ "b": 2 /* d */}', "jsonc") == {"a": 1, "b": 2}
    commented_tail = '{\n  "a": 1, /* why */\n  "b": 2\n  /* "c": 3 */\n}\n'
    assert parse_settings(commented_tail, "jsonc") == {"a": 1, "b": 2}
    markers_in_strings = '{"u": "/* not */", "v": "a, */ }", /* real */ "w": [1, /* x */ 2,]}'
    assert parse_settings(markers_in_strings, "jsonc") == {
        "u": "/* not */",
        "v": "a, */ }",
        "w": [1, 2],
    }


def test_revert_follows_the_recorded_file_not_the_one_resolved_now() -> None:
    home = Path.home()
    base = home / ".config" / "opencode"
    base.mkdir(parents=True, exist_ok=True)
    plain, jsonc = base / "opencode.json", base / "opencode.jsonc"
    plain.write_text('{"theme": "dark"}\n', encoding="utf-8")
    apply_setting("opencode", "auto-approve", home=home, platform_os="linux")
    jsonc.write_text("{}\n", encoding="utf-8")  # e.g. codegraph's own registration file

    reverted = _reverted("opencode", home=home)

    assert reverted.refused is None
    assert reverted.path == plain
    assert [key.kind for key in reverted.keys] == ["removed"]
    assert plain.read_text(encoding="utf-8") == '{"theme": "dark"}\n'
    assert jsonc.read_text(encoding="utf-8") == "{}\n"
    assert read_ledger("opencode") is None


def test_a_recorded_file_that_is_gone_is_reported_and_no_other_file_is_touched() -> None:
    home = Path.home()
    base = home / ".config" / "opencode"
    base.mkdir(parents=True, exist_ok=True)
    plain, jsonc = base / "opencode.json", base / "opencode.jsonc"
    plain.write_text('{"theme": "dark"}\n', encoding="utf-8")
    apply_setting("opencode", "auto-approve", home=home, platform_os="linux")
    plain.rename(jsonc)  # the usual step to add comments
    renamed = jsonc.read_bytes()
    ledger_before = read_ledger("opencode")

    assert setting_state("opencode", "auto-approve", home=home, platform_os="linux") != "yours"
    reverted = revert_agent("opencode", home=home, platform_os="linux")

    assert [(result.path, result.refused) for result in reverted] == [
        (plain, agent_settings.RECORDED_FILE_GONE)
    ]
    assert jsonc.read_bytes() == renamed
    assert read_ledger("opencode") == ledger_before
    assert ledger_summary("opencode", home=home) == ((plain, ("permission",)),)
    assert settings_change_lines(("opencode",)) == (
        "opencode: cannot remove permission: ~/.config/opencode/opencode.json is missing",
    )


def test_an_untrusted_ledger_is_kept_aside_and_blocks_every_write() -> None:
    from installer.receipts import config_ledger_dir

    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")
    apply_setting("claude", "auto-approve", home=home, platform_os="linux")
    ledger_path = config_ledger_dir() / "claude.json"
    tampered = json.loads(ledger_path.read_text(encoding="utf-8"))
    tampered["v"] = 2  # e.g. written by a newer installer build
    ledger_path.write_text(json.dumps(tampered), encoding="utf-8")
    recorded = ledger_path.read_bytes()
    written = settings.read_bytes()

    applied = apply_setting("claude", "no-attribution", home=home, platform_os="linux")
    reverted = revert_agent("claude", home=home, platform_os="linux")

    aside = config_ledger_dir() / "claude.json.untrusted"
    assert applied.refused is not None
    assert applied.refused.startswith("blocked: the claude config ledger could not be trusted")
    assert [result.refused for result in reverted] == [applied.refused]
    assert aside.read_bytes() == recorded
    assert not ledger_path.exists()
    assert settings.read_bytes() == written
    assert apply_setting("claude", "auto-approve", home=home, platform_os="linux").refused
    assert settings.read_bytes() == written


def test_an_empty_file_a_bom_and_a_nested_toml_array_are_edited_not_refused() -> None:
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_bytes(b"")  # e.g. after `touch`
    assert apply_setting("claude", "auto-approve", home=home, platform_os="linux").refused is None
    assert json.loads(settings.read_text(encoding="utf-8"))["skipDangerousModePermissionPrompt"]

    vscode = home / ".config" / "Code" / "User" / "settings.json"
    vscode.parent.mkdir(parents=True, exist_ok=True)
    original = '﻿{\n  "editor.fontSize": 14\n}\n'.encode()
    vscode.write_bytes(original)
    assert apply_setting("vscode", "vscode-ai-off", home=home, platform_os="linux").refused is None
    assert vscode.read_bytes().startswith("﻿".encode())
    assert _reverted("vscode", home=home).refused is None
    assert vscode.read_bytes() == original

    nested = 'args = [\n  ["a"],\n]\n\n[features]\nx = true\n'
    inserted = insert_key(nested, "toml", ("approval_policy",), "never")
    assert tomllib.loads(inserted.text) == {
        "args": [["a"]],
        "approval_policy": "never",
        "features": {"x": True},
    }


def test_a_fifo_at_a_settings_path_is_refused_without_blocking() -> None:
    settings = _claude_settings_file()
    os.mkfifo(settings)  # an open without O_NONBLOCK would wait for a writer forever

    applied = apply_setting("claude", "auto-approve", home=Path.home(), platform_os="linux")

    assert applied.refused is not None
    assert "not a regular file" in applied.refused
    assert file_problem("claude", home=Path.home(), platform_os="linux") == applied.refused


def test_a_created_file_the_user_commented_is_kept_on_revert() -> None:
    home = Path.home()
    vscode = home / ".config" / "Code" / "User" / "settings.json"
    apply_setting("vscode", "vscode-ai-off", home=home, platform_os="linux")
    vscode.write_text("// mine\n" + vscode.read_text(encoding="utf-8"), encoding="utf-8")

    assert _reverted("vscode", home=home).refused is None

    assert vscode.read_text(encoding="utf-8") == "// mine\n{}\n"
    assert read_ledger("vscode") is None


def test_the_removal_preview_lists_only_keys_still_holding_our_value() -> None:
    """F-3: a key the user changed since is named as kept, never promised as removed."""
    home = Path.home()
    settings = _claude_settings_file()
    settings.write_text('{"model": "opus"}\n', encoding="utf-8")
    apply_setting("claude", "no-attribution", home=home, platform_os="linux")
    doc = json.loads(settings.read_text(encoding="utf-8"))
    doc["attribution"]["pr"] = "mine"
    settings.write_text(json.dumps(doc), encoding="utf-8")

    assert settings_change_lines(("claude",)) == (
        "claude: removes attribution.commit from ~/.claude/settings.json",
        "claude: keeps attribution.pr, changed since this installer wrote it",
    )
    results = revert_agent("claude", home=home, platform_os="linux")
    assert [(key.key, key.kind) for result in results for key in result.keys] == [
        ("attribution.pr", "kept_changed"),
        ("attribution.commit", "removed"),
    ]


def test_copilot_keys_format_groups_and_ledger_slot() -> None:
    assert agent_settings.AGENT_FORMATS["copilot"] == "jsonc"
    approve = agent_settings.setting_keys("copilot", "auto-approve", "linux")
    attribution = agent_settings.setting_keys("copilot", "no-attribution", "linux")
    assert [(key.path, key.value) for key in approve] == [(("defaultPermissionMode",), "allow-all")]
    assert [(key.path, key.value) for key in attribution] == [(("includeCoAuthoredBy",), False)]
    assert agent_settings.TUNING_GROUPS["copilot"] == ("auto-approve", "no-attribution")
    assert "copilot" in receipts.CONFIG_AGENTS


def test_copilot_writes_under_an_absolute_copilot_home_and_keeps_a_comment(tmp_path: Path) -> None:
    home = Path.home()
    ch = tmp_path / "ch"
    ch.mkdir()
    settings = ch / "settings.json"
    settings.write_text('// mine\n{"theme": "dark"}\n', encoding="utf-8")
    environ = {"COPILOT_HOME": str(ch)}

    first = apply_setting(
        "copilot", "auto-approve", home=home, platform_os="linux", environ=environ
    )
    second = apply_setting(
        "copilot", "no-attribution", home=home, platform_os="linux", environ=environ
    )

    assert first.refused is None and second.refused is None
    assert first.path == settings
    text = settings.read_text(encoding="utf-8")
    assert text.startswith("// mine\n")
    assert parse_settings(text, "jsonc") == {
        "theme": "dark",
        "defaultPermissionMode": "allow-all",
        "includeCoAuthoredBy": False,
    }
    assert not (home / ".copilot" / "settings.json").exists()


def test_copilot_revert_under_the_same_home_restores_the_file(tmp_path: Path) -> None:
    home = Path.home()
    ch = tmp_path / "ch"
    ch.mkdir()
    settings = ch / "settings.json"
    original = '// mine\n{"theme": "dark"}\n'
    settings.write_text(original, encoding="utf-8")
    environ = {"COPILOT_HOME": str(ch)}
    apply_setting("copilot", "auto-approve", home=home, platform_os="linux", environ=environ)

    results = revert_agent("copilot", home=home, platform_os="linux", environ=environ)

    assert [(r.refused, [k.kind for k in r.keys]) for r in results] == [(None, ["removed"])]
    assert settings.read_text(encoding="utf-8") == original
    assert read_ledger("copilot") is None


def test_copilot_revert_under_another_home_is_refused_and_keeps_the_record(tmp_path: Path) -> None:
    home = Path.home()
    ch = tmp_path / "ch"
    ch.mkdir()
    apply_setting(
        "copilot",
        "auto-approve",
        home=home,
        platform_os="linux",
        environ={"COPILOT_HOME": str(ch)},
    )
    written = (ch / "settings.json").read_bytes()

    results = revert_agent(
        "copilot",
        home=home,
        platform_os="linux",
        environ={"COPILOT_HOME": str(tmp_path / "other")},
    )

    assert [r.refused for r in results] == [agent_settings.NOT_A_SETTINGS_FILE]
    assert (ch / "settings.json").read_bytes() == written
    ledger = read_ledger("copilot")
    assert ledger is not None
    assert [entry.key_path for entry in ledger.entries] == [("defaultPermissionMode",)]


def test_copilot_home_outside_home_is_reverted_but_not_previewed(tmp_path: Path) -> None:
    """Accepted limit (review R1-02): the preview filters on HOME; the revert does not."""
    home = Path.home()
    ch = tmp_path / "ch"
    environ = {"COPILOT_HOME": str(ch)}
    for group in ("auto-approve", "no-attribution"):
        apply_setting("copilot", group, home=home, platform_os="linux", environ=environ)
    assert (ch / "settings.json").is_file()

    assert ledger_summary("copilot", home=home) == ()
    assert agent_settings.ledger_preview("copilot", home=home) == ()
    results = revert_agent("copilot", home=home, platform_os="linux", environ=environ)

    assert [key.kind for r in results for key in r.keys] == ["removed", "removed"]
    assert not (ch / "settings.json").exists()


def test_pending_tuning_race_never_publishes_ok_before_the_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backstop (R2 concurrency): the ledger is reserved before the file commits, so a pass
    that reads the keys as recorded never sees them pending, and one that reads them pending
    sees them before the ledger has them (never `✓` ahead of the record)."""
    home = Path.home()
    _claude_settings_file().write_text("{}\n", encoding="utf-8")
    keys = ("permissions.defaultMode", "skipDangerousModePermissionPrompt")
    seen: dict[str, tuple[str, ...]] = {}
    real_write_ledger = agent_settings.write_ledger
    real_write_if_unchanged = agent_settings.write_if_unchanged

    def absent() -> tuple[str, ...]:
        return agent_settings.setting_facts(
            "claude", "auto-approve", home=home, platform_os="linux"
        ).absent

    def ledger_spy(ledger: ConfigLedger) -> None:
        seen.setdefault("before_reservation", absent())
        real_write_ledger(ledger)

    def write_spy(path: Path, before: FileSnapshot | None, text: str) -> None:
        seen["between_reservation_and_commit"] = absent()
        real_write_if_unchanged(path, before, text)

    monkeypatch.setattr(agent_settings, "write_ledger", ledger_spy)
    monkeypatch.setattr(agent_settings, "write_if_unchanged", write_spy)

    apply_setting("claude", "auto-approve", home=home, platform_os="linux", skip_recorded=True)

    assert seen == {"before_reservation": keys, "between_reservation_and_commit": ()}
    assert absent() == ()
