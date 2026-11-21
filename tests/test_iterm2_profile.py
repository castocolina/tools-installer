"""Golden and safety tests for iTerm2 dynamic profiles."""

import json
import plistlib
from collections.abc import Sequence
from pathlib import Path

import pytest

from installer import iterm2_profile
from installer.iterm2_profile import ProfileState
from installer.run import CommandError
from installer.terminal_regions import Restored, TerminalShellError

REAL_DEFAULTS = iterm2_profile.iterm2_defaults

GUID = "AAAAAAAA-0000-4000-8000-000000000001"
ROWS: dict[str, object] = {
    "0x6b-0x100000": {"Action": 11, "Text": "0x0c"},
    "0xf702-0x280000": {"Action": 10, "Text": "b"},
    "0xf703-0x280000": {"Action": 10, "Text": "f"},
}
GOLDEN = """{
  "Profiles": [
    {
      "Background Color": {
        "Alpha Component": 1,
        "Blue Component": 0.03,
        "Color Space": "sRGB",
        "Green Component": 0.05,
        "Red Component": 0.02
      },
      "Bold Color": {
        "Alpha Component": 1,
        "Blue Component": 0.45,
        "Color Space": "sRGB",
        "Green Component": 0.8,
        "Red Component": 0.35
      },
      "Cursor Color": {
        "Alpha Component": 1,
        "Blue Component": 0.45,
        "Color Space": "sRGB",
        "Green Component": 0.8,
        "Red Component": 0.35
      },
      "Custom Directory": "Recycle",
      "Foreground Color": {
        "Alpha Component": 1,
        "Blue Component": 0.3,
        "Color Space": "sRGB",
        "Green Component": 0.62,
        "Red Component": 0.2
      },
      "Guid": "6CB8584E-9B4C-4CF6-892A-D21E8AFE908C",
      "Keyboard Map": {
        "0x6b-0x100000": {
          "Action": 11,
          "Text": "0x0c"
        },
        "0xf702-0x280000": {
          "Action": 10,
          "Text": "b"
        },
        "0xf703-0x280000": {
          "Action": 10,
          "Text": "f"
        }
      },
      "Name": "tools-installer",
      "Selection Color": {
        "Alpha Component": 1,
        "Blue Component": 0.15,
        "Color Space": "sRGB",
        "Green Component": 0.3,
        "Red Component": 0.1
      },
      "Use Separate Colors for Light and Dark Mode": false
    }
  ]
}
"""
PARENT_GOLDEN = """{
  "Profiles": [
    {
      "Background Color": {
        "Alpha Component": 1,
        "Blue Component": 0.03,
        "Color Space": "sRGB",
        "Green Component": 0.05,
        "Red Component": 0.02
      },
      "Bold Color": {
        "Alpha Component": 1,
        "Blue Component": 0.45,
        "Color Space": "sRGB",
        "Green Component": 0.8,
        "Red Component": 0.35
      },
      "Cursor Color": {
        "Alpha Component": 1,
        "Blue Component": 0.45,
        "Color Space": "sRGB",
        "Green Component": 0.8,
        "Red Component": 0.35
      },
      "Custom Directory": "Recycle",
      "Dynamic Profile Parent GUID": "AAAAAAAA-0000-4000-8000-000000000001",
      "Foreground Color": {
        "Alpha Component": 1,
        "Blue Component": 0.3,
        "Color Space": "sRGB",
        "Green Component": 0.62,
        "Red Component": 0.2
      },
      "Guid": "6CB8584E-9B4C-4CF6-892A-D21E8AFE908C",
      "Keyboard Map": {
        "0x61-0x40000": {
          "Action": 10,
          "Text": "y"
        },
        "0x6b-0x100000": {
          "Action": 11,
          "Text": "0x0c"
        },
        "0xf702-0x280000-0x7b-0x0": {
          "Action": 10,
          "Text": "x"
        },
        "0xf703-0x280000": {
          "Action": 10,
          "Text": "f"
        }
      },
      "Name": "tools-installer",
      "Selection Color": {
        "Alpha Component": 1,
        "Blue Component": 0.15,
        "Color Space": "sRGB",
        "Green Component": 0.3,
        "Red Component": 0.1
      },
      "Use Separate Colors for Light and Dark Mode": false
    }
  ]
}
"""


def test_the_profile_golden_without_a_previous_default() -> None:
    state = ProfileState(None, None, False, False, ROWS)
    text = iterm2_profile.iterm2_profile_text(state, recycle=True)
    assert text == GOLDEN
    profile = json.loads(text)["Profiles"][0]
    assert (
        not {
            "Dynamic Profile Parent GUID",
            "Rewritable",
            "Option Key Sends",
            "Right Option Key Sends",
        }
        & profile.keys()
    )


def test_the_profile_omits_custom_directory_when_the_row_does_not_write_it() -> None:
    state = ProfileState(None, None, False, False, ROWS)
    with_recycle = json.loads(iterm2_profile.iterm2_profile_text(state, recycle=True))
    without = json.loads(iterm2_profile.iterm2_profile_text(state, recycle=False))
    assert with_recycle["Profiles"][0].pop("Custom Directory") == "Recycle"
    assert with_recycle == without


def test_the_profile_golden_with_a_parent_and_a_merged_map() -> None:
    parent = {
        "0xf702-0x280000-0x7b-0x0": {"Action": 10, "Text": "x"},
        "0x61-0x40000": {"Action": 10, "Text": "y"},
    }
    rows, clashes = iterm2_profile.merge_rows(parent)
    assert clashes == ("option+left",)
    assert rows == {
        **parent,
        "0x6b-0x100000": ROWS["0x6b-0x100000"],
        "0xf703-0x280000": ROWS["0xf703-0x280000"],
    }
    assert (
        iterm2_profile.iterm2_profile_text(
            ProfileState(GUID, GUID, True, False, rows), recycle=True
        )
        == PARENT_GOLDEN
    )


def test_a_parent_row_with_the_same_action_is_not_a_clash() -> None:
    rows, clashes = iterm2_profile.merge_rows(
        {"0x6b-0x100000-0x28": {"Action": 11, "Text": "0x0c"}}
    )
    assert not clashes
    assert "0x6b-0x100000" not in rows
    assert rows["0x6b-0x100000-0x28"] == {"Action": 11, "Text": "0x0c"}


def test_keystrokes_compare_by_character_and_masked_flags() -> None:
    parse = iterm2_profile.parse_keystroke
    identity = iterm2_profile.keystroke_id
    assert parse("0x6b-0x100000") == (0x6B, 0x100000)
    assert parse("0x6b-0x100000-0x28") == parse("0x6b-0x100000-0x28-0x0") == (0x6B, 0x100000)
    assert identity("0xf702-0x80000") == identity("0xf702-0x280000")
    assert identity("0xf702-0xa0000") != identity("0xf702-0x80000")
    assert parse("badhex-0x1") is None
    assert parse("0x6b") is None


def test_parent_rows_read_the_matching_profile_from_an_exported_plist() -> None:
    xml = plistlib.dumps(
        {
            "New Bookmarks": [
                {"Guid": GUID, "Keyboard Map": {"ok": {"Action": 10}, "bytes": b"data"}},
                {"Guid": "other"},
            ]
        }
    ).decode()
    assert iterm2_profile.parent_rows(xml, GUID) == {"ok": {"Action": 10}}
    assert iterm2_profile.parent_rows(xml, "other") == {}
    assert iterm2_profile.parent_rows(xml, "missing") is None
    assert iterm2_profile.parent_rows("not xml", GUID) is None


def test_proof_and_validate() -> None:
    assert iterm2_profile.iterm2_proof(GOLDEN)
    iterm2_profile.validate_iterm2(GOLDEN)
    for text in ("not json", "{}", '{"Profiles": [{}, {}]}', '{"Profiles": [{"Guid": "other"}]}'):
        assert not iterm2_profile.iterm2_proof(text)
        with pytest.raises(TerminalShellError):
            iterm2_profile.validate_iterm2(text)


def test_the_state_record_round_trips(tmp_path: Path) -> None:
    state = ProfileState(GUID, GUID, True, False, ROWS)
    path = tmp_path / ".local/share/tools-installer/terminal-iterm2-default"
    assert iterm2_profile.read_state(tmp_path, {}) is None
    iterm2_profile.write_state(tmp_path, {}, state)
    assert json.loads(path.read_text())["rows"] == ROWS
    assert iterm2_profile.read_state(tmp_path, {}) == state
    path.write_text("garbage")
    assert iterm2_profile.read_state(tmp_path, {}) is None
    path.write_text("{}")
    assert iterm2_profile.read_state(tmp_path, {}) is None
    iterm2_profile.drop_state(tmp_path, {})
    iterm2_profile.drop_state(tmp_path, {})
    assert not path.exists()


DOMAIN = "com.googlecode.iterm2"
DEFAULT = "Default Bookmark Guid"
CUSTOM = "LoadPrefsFromCustomFolder"
OURS = iterm2_profile.ITERM2_GUID
OTHER = "BBBBBBBB-0000-4000-8000-000000000002"
READ = ("read", DOMAIN, DEFAULT)
READ_CUSTOM = ("read", DOMAIN, CUSTOM)
EXPORT = ("export", DOMAIN, "-")
WRITE_OURS = ("write", DOMAIN, DEFAULT, "-string", OURS)


class FakeDefaults:
    def __init__(self, current: str | None = GUID) -> None:
        self.prefs: dict[str, str] = {} if current is None else {DEFAULT: current}
        self.bookmarks: list[dict[str, object]] = [{"Guid": GUID, "Keyboard Map": {}}]
        self.fail_next: set[str] = set()
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> str:
        call = tuple(argv)
        self.calls.append(call)
        verb = call[0]
        if verb in self.fail_next:
            self.fail_next.remove(verb)
            raise CommandError(list(argv), 1, detail="injected")
        if verb == "read" and len(call) == 3 and call[1] == DOMAIN:
            if call[2] not in self.prefs:
                raise CommandError(list(argv), 1, detail="does not exist")
            return self.prefs[call[2]] + "\n"
        if verb == "write" and len(call) == 5 and call[1:4] == (DOMAIN, DEFAULT, "-string"):
            self.prefs[DEFAULT] = call[4]
            return ""
        if call == ("delete", DOMAIN, DEFAULT):
            self.prefs.pop(DEFAULT, None)
            return ""
        if call == EXPORT:
            return plistlib.dumps({"New Bookmarks": self.bookmarks}).decode()
        raise AssertionError(call)


def setup_fake(monkeypatch: pytest.MonkeyPatch, current: str | None = GUID) -> FakeDefaults:
    fake = FakeDefaults(current)
    monkeypatch.setattr(iterm2_profile, "iterm2_defaults", fake)
    return fake


def before(home: Path, reconfigure: bool = False) -> tuple[str, ...]:
    return iterm2_profile.hook_before_write("macos", home, {}, reconfigure)


def after(home: Path, reconfigure: bool = False) -> tuple[str, ...]:
    return iterm2_profile.hook_after_write("macos", home, {}, reconfigure)


def restore(home: Path, final: bool = True) -> Restored:
    return iterm2_profile.hook_restore("macos", home, {}, final)


def state(home: Path) -> ProfileState:
    result = iterm2_profile.read_state(home, {})
    assert result is not None
    return result


@pytest.mark.parametrize("starting", ["guid", "none", "ours", "changed"])
def test_the_default_profile_round_trips_four_starting_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, starting: str
) -> None:
    previous = None if starting == "none" else GUID
    fake = setup_fake(monkeypatch, previous)
    assert before(tmp_path) == ()
    assert fake.calls == [READ, READ_CUSTOM] + ([EXPORT] if previous else [])
    assert state(tmp_path) == ProfileState(previous, previous, True, False, ROWS)
    fake.calls.clear()
    assert after(tmp_path) == ()
    assert fake.calls == [READ, WRITE_OURS]
    assert state(tmp_path).switched
    if starting == "ours":
        saved = state(tmp_path)
        fake.calls.clear()
        assert before(tmp_path) == ()
        assert fake.calls == [READ, READ_CUSTOM]
        assert state(tmp_path) == saved
        fake.calls.clear()
        assert after(tmp_path) == ()
        assert fake.calls == []
    if starting == "changed":
        fake.prefs[DEFAULT] = OTHER
    fake.calls.clear()
    result = restore(tmp_path)
    if starting == "changed":
        assert result == Restored(
            ("iterm2: partial: you changed your default profile after the install; kept yours",),
            True,
        )
        assert fake.calls == [READ]
        assert fake.prefs[DEFAULT] == OTHER
    else:
        command = (
            ("write", DOMAIN, DEFAULT, "-string", previous)
            if previous
            else ("delete", DOMAIN, DEFAULT)
        )
        assert result == Restored((), True)
        assert fake.calls == [READ, READ_CUSTOM, command, READ]
        assert fake.prefs.get(DEFAULT) == previous
    assert iterm2_profile.read_state(tmp_path, {}) is None


@pytest.mark.parametrize("failure", ["unchanged", "read"])
def test_restore_requires_readback_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    saved = iterm2_profile.state_record(tmp_path, {}).read_bytes()

    def defaults(argv: Sequence[str]) -> str:
        if tuple(argv) == ("write", DOMAIN, DEFAULT, "-string", GUID):
            if failure == "read":
                fake.fail_next.add("read")
            return ""
        return fake(argv)

    monkeypatch.setattr(iterm2_profile, "iterm2_defaults", defaults)
    result = restore(tmp_path)
    assert not result.confirmed
    assert iterm2_profile.state_record(tmp_path, {}).read_bytes() == saved
    assert fake.prefs[DEFAULT] == OURS


@pytest.mark.parametrize("failed_key", [DEFAULT, CUSTOM])
def test_reinstall_read_failure_keeps_prior_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_key: str
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    path = iterm2_profile.state_record(tmp_path, {})
    saved = path.read_bytes()

    def defaults(argv: Sequence[str]) -> str:
        if tuple(argv) == ("read", DOMAIN, failed_key):
            raise CommandError(list(argv), 1, detail="injected")
        return fake(argv)

    monkeypatch.setattr(iterm2_profile, "iterm2_defaults", defaults)
    assert before(tmp_path)[0].startswith("iterm2: partial: could not read")
    assert path.read_bytes() == saved
    assert after(tmp_path) == ()


def test_reinstall_with_custom_folder_keeps_record_and_restores_later(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    path = iterm2_profile.state_record(tmp_path, {})
    saved = path.read_bytes()
    fake.prefs[CUSTOM] = "1"
    assert "custom folder" in before(tmp_path)[0]
    assert path.read_bytes() == saved
    assert state(tmp_path).default_set and state(tmp_path).previous == GUID
    assert after(tmp_path) == ()
    fake.prefs.pop(CUSTOM)
    assert restore(tmp_path).confirmed
    assert fake.prefs[DEFAULT] == GUID


def test_restore_is_idempotent_and_final_controls_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    assert iterm2_profile.hook_still_named("macos", tmp_path, {})
    assert restore(tmp_path, False) == Restored((), True)
    assert not state(tmp_path).switched
    assert not iterm2_profile.hook_still_named("macos", tmp_path, {})
    fake.calls.clear()
    assert restore(tmp_path, False) == Restored((), True)
    assert fake.calls == [READ]
    assert restore(tmp_path) == Restored((), True)
    assert iterm2_profile.read_state(tmp_path, {}) is None
    assert not iterm2_profile.hook_still_named("macos", tmp_path, {})


@pytest.mark.parametrize("previous,verb", [(GUID, "write"), (None, "delete")])
def test_a_failed_restore_keeps_the_previous_default_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous: str | None, verb: str
) -> None:
    fake = setup_fake(monkeypatch, previous)
    before(tmp_path)
    after(tmp_path)
    fake.fail_next.add(verb)
    result = restore(tmp_path)
    assert not result.confirmed and result.lines[0].startswith(
        "iterm2: partial: could not restore your default profile"
    )
    assert state(tmp_path).previous == previous and fake.prefs[DEFAULT] == OURS
    assert restore(tmp_path) == Restored((), True)
    assert fake.prefs.get(DEFAULT) == previous
    assert iterm2_profile.read_state(tmp_path, {}) is None


def test_restore_is_confirmed_when_the_preference_no_longer_names_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    fake.prefs[DEFAULT] = OTHER
    assert restore(tmp_path).confirmed
    assert iterm2_profile.read_state(tmp_path, {}) is None
    for current in (GUID, None):
        fake.prefs.clear()
        if current:
            fake.prefs[DEFAULT] = current
        fake.calls.clear()
        assert restore(tmp_path) == Restored((), True)
        assert fake.calls == [READ]


def test_restore_is_not_confirmed_when_it_cannot_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    fake.prefs[CUSTOM] = "1"
    assert restore(tmp_path) == Restored(
        (
            "iterm2: partial: iTerm2 loads its preferences from a custom "
            "folder; the default profile was not restored",
        ),
        False,
    )
    fake.fail_next.add("read")
    result = restore(tmp_path)
    assert not result.confirmed and result.lines[0].startswith(
        "iterm2: partial: could not read your default profile"
    )
    assert state(tmp_path).previous == GUID


@pytest.mark.parametrize("record", ["missing", "garbage", "disabled", "invalid"])
@pytest.mark.parametrize("final", [False, True])
def test_a_lost_recovery_record_is_not_a_confirmed_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record: str, final: bool
) -> None:
    fake = setup_fake(monkeypatch, OURS)
    path = iterm2_profile.state_record(tmp_path, {})
    if record == "garbage":
        path.parent.mkdir(parents=True)
        path.write_text("garbage")
    if record in ("disabled", "invalid"):
        iterm2_profile.write_state(
            tmp_path,
            {},
            ProfileState(
                None, "bad" if record == "invalid" else GUID, record == "invalid", False, ROWS
            ),
        )
    original = path.read_bytes() if path.exists() else None
    assert restore(tmp_path, final) == Restored(
        (
            "iterm2: partial: your default profile is still tools-installer "
            "and your previous default could not be recovered; choose a "
            "default profile in iTerm2 > Settings > Profiles, then uninstall "
            "again",
        ),
        False,
    )
    assert fake.calls == [READ]
    assert (path.read_bytes() if path.exists() else None) == original
    fake.prefs[DEFAULT] = OTHER
    fake.calls.clear()
    assert restore(tmp_path, final).confirmed
    assert fake.calls == [READ]


@pytest.mark.parametrize("previous", [GUID, None])
def test_a_restore_before_removal_leaves_a_retryable_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous: str | None
) -> None:
    fake = setup_fake(monkeypatch, previous)
    before(tmp_path)
    after(tmp_path)
    assert restore(tmp_path, False) == Restored((), True)
    assert fake.prefs.get(DEFAULT) == previous and not state(tmp_path).switched
    assert iterm2_profile.hook_switch_pending("macos", tmp_path, {})
    assert not iterm2_profile.hook_still_named("macos", tmp_path, {})
    fake.calls.clear()
    assert before(tmp_path, True) == () and fake.calls == []
    assert after(tmp_path, True) == (
        "iterm2: your default profile is now tools-installer (retried after an earlier failure)",
    )
    assert fake.calls == [READ, WRITE_OURS] and state(tmp_path).switched
    assert restore(tmp_path) == Restored((), True)
    assert fake.prefs.get(DEFAULT) == previous


@pytest.mark.parametrize("previous", [GUID, None])
def test_a_failed_switch_is_retried_only_while_the_default_is_still_the_previous_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous: str | None
) -> None:
    fake = setup_fake(monkeypatch, previous)
    before(tmp_path)
    fake.fail_next.add("write")
    assert after(tmp_path)[0].startswith("iterm2: partial: could not set your default profile")
    assert not state(tmp_path).switched and iterm2_profile.hook_switch_pending(
        "macos", tmp_path, {}
    )
    fake.calls.clear()
    assert before(tmp_path, True) == () and fake.calls == []
    assert after(tmp_path, True) == (
        "iterm2: your default profile is now tools-installer (retried after an earlier failure)",
    )
    assert fake.calls == [READ, WRITE_OURS]
    assert not iterm2_profile.hook_switch_pending("macos", tmp_path, {})
    fake.calls.clear()
    assert before(tmp_path, True) == after(tmp_path, True) == () and fake.calls == []


@pytest.mark.parametrize("previous", [GUID, None])
def test_the_first_switch_writes_only_while_the_default_is_still_the_previous_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous: str | None
) -> None:
    fake = setup_fake(monkeypatch, previous)
    before(tmp_path)
    fake.prefs[DEFAULT] = OTHER
    fake.calls.clear()
    assert after(tmp_path) == (
        "iterm2: partial: you changed your default profile after the "
        "install; the installer's profile was not made your default (kept yours)",
    )
    assert fake.calls == [READ] and not state(tmp_path).default_set
    assert not iterm2_profile.hook_switch_pending("macos", tmp_path, {})
    assert not iterm2_profile.hook_still_named("macos", tmp_path, {})
    fake.calls.clear()
    assert restore(tmp_path) == Restored((), True) and fake.calls == [READ]
    assert fake.prefs[DEFAULT] == OTHER


@pytest.mark.parametrize("old", [False, True])
def test_a_failed_capture_inhibits_the_switch_even_with_an_old_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, old: bool
) -> None:
    fake = setup_fake(monkeypatch)
    if old:
        iterm2_profile.write_state(tmp_path, {}, ProfileState(GUID, GUID, True, False, ROWS))
    path = iterm2_profile.state_record(tmp_path, {})
    saved = path.read_bytes() if path.exists() else None
    original = iterm2_profile.write_state

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("injected")

    monkeypatch.setattr(iterm2_profile, "write_state", fail)
    assert before(tmp_path)[-1].startswith(
        "iterm2: partial: could not record your previous default"
    )
    fake.calls.clear()
    assert after(tmp_path) == () and fake.calls == []
    assert fake.prefs[DEFAULT] == GUID and (path.read_bytes() if path.exists() else None) == saved
    monkeypatch.setattr(iterm2_profile, "write_state", original)
    before(tmp_path)
    after(tmp_path)
    assert fake.prefs[DEFAULT] == OURS


def test_fault_injection_at_each_transition_never_strands_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    original = iterm2_profile.write_state

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("injected")

    monkeypatch.setattr(iterm2_profile, "write_state", fail)
    assert after(tmp_path)[0].startswith("iterm2: partial: could not record the default switch")
    assert fake.prefs[DEFAULT] == OURS
    monkeypatch.setattr(iterm2_profile, "write_state", original)
    assert restore(tmp_path) == Restored((), True)
    assert fake.prefs[DEFAULT] == GUID
    before(tmp_path)
    after(tmp_path)
    monkeypatch.setattr(iterm2_profile, "drop_state", fail)
    result = restore(tmp_path)
    assert result.confirmed and result.lines[0].startswith("iterm2: partial:")
    assert fake.prefs[DEFAULT] == GUID


def test_a_previous_default_that_is_a_dynamic_profile_is_kept_as_the_parent_without_a_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch, OTHER)
    assert (
        "iterm2: partial: your previous default is a Dynamic Profile or "
        "could not be read; its key mappings were not merged" in before(tmp_path)
    )
    assert state(tmp_path).parent == OTHER and state(tmp_path).rows == ROWS
    after(tmp_path)
    assert restore(tmp_path).confirmed and fake.prefs[DEFAULT] == OTHER


def test_a_clash_with_a_parent_row_is_reported_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    fake.bookmarks = [{"Guid": GUID, "Keyboard Map": {"0x6b-0x100000": {"Action": 99}}}]
    assert "iterm2: partial: you already bind cmd+k" in before(tmp_path)
    assert state(tmp_path).rows["0x6b-0x100000"] == {"Action": 99}


def test_default_step_skips_custom_folder_unreadable_and_non_guid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    fake.prefs[CUSTOM] = "1"
    assert (
        "iterm2: partial: iTerm2 loads its preferences from a custom "
        "folder; the default profile was not changed" in before(tmp_path)
    )
    assert not state(tmp_path).default_set and after(tmp_path) == ()
    fake.calls.clear()
    assert restore(tmp_path).confirmed and fake.calls == [READ]
    fake.prefs.pop(CUSTOM)
    fake.fail_next.add("read")
    assert before(tmp_path)[0].startswith("iterm2: partial: could not read your default profile")
    fake.prefs[DEFAULT] = "not a guid; rm"
    assert (
        "iterm2: partial: your default profile id is not a GUID; the default was not changed"
        in before(tmp_path)
    )
    assert after(tmp_path) == ()


def test_reconfigure_with_a_settled_record_does_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    for default_set, switched in ((True, True), (False, False)):
        iterm2_profile.write_state(
            tmp_path, {}, ProfileState(GUID, GUID, default_set, switched, ROWS)
        )
        fake.calls.clear()
        assert before(tmp_path, True) == after(tmp_path, True) == () and fake.calls == []
        before(tmp_path)
        assert fake.calls[:2] == [READ, READ_CUSTOM]


@pytest.mark.parametrize("source", ["restore", "failed-switch"])
def test_retry_preserves_a_later_user_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    if source == "restore":
        after(tmp_path)
        assert restore(tmp_path, False).confirmed
    else:
        fake.fail_next.add("write")
        after(tmp_path)
    fake.prefs[DEFAULT] = OTHER
    fake.calls.clear()
    assert before(tmp_path, True) == ()
    assert after(tmp_path, True) == (
        "iterm2: partial: you changed your default profile after the "
        "install; the installer's profile was not made your default (kept yours)",
    )
    assert fake.calls == [READ] and not state(tmp_path).default_set
    assert not iterm2_profile.hook_switch_pending("macos", tmp_path, {})
    assert restore(tmp_path).confirmed and fake.prefs[DEFAULT] == OTHER


def test_failed_record_update_after_restore_refuses_removal_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch)
    before(tmp_path)
    after(tmp_path)
    original = iterm2_profile.write_state

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("injected")

    monkeypatch.setattr(iterm2_profile, "write_state", fail)
    result = restore(tmp_path, False)
    assert not result.confirmed and result.lines[0].startswith(
        "iterm2: partial: could not update your record"
    )
    assert fake.prefs[DEFAULT] == GUID and state(tmp_path).switched
    assert not iterm2_profile.hook_switch_pending("macos", tmp_path, {})
    assert not iterm2_profile.hook_still_named("macos", tmp_path, {})
    fake.calls.clear()
    assert before(tmp_path, True) == after(tmp_path, True) == () and fake.calls == []
    monkeypatch.setattr(iterm2_profile, "write_state", original)
    fake.calls.clear()
    assert restore(tmp_path, False) == Restored((), True) and fake.calls == [READ]


def test_a_tampered_record_never_reaches_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = setup_fake(monkeypatch, OURS)
    iterm2_profile.write_state(tmp_path, {}, ProfileState(None, "x; rm -rf ~", True, True, ROWS))
    assert not restore(tmp_path).confirmed and fake.calls == [READ]
    assert all("rm -rf" not in arg for call in fake.calls for arg in call)
    fake.prefs[DEFAULT] = OTHER
    assert restore(tmp_path).confirmed
    assert iterm2_profile.read_state(tmp_path, {}) is None


def test_the_command_builders_are_pure() -> None:
    assert iterm2_profile.install_commands(None, OURS) == (WRITE_OURS,)
    assert iterm2_profile.install_commands(GUID, OURS) == (WRITE_OURS,)
    assert iterm2_profile.install_commands(OURS, OURS) == ()
    assert iterm2_profile.restore_commands(GUID, OURS, OURS) == (
        ("write", DOMAIN, DEFAULT, "-string", GUID),
    )
    assert iterm2_profile.restore_commands(None, OURS, OURS) == (("delete", DOMAIN, DEFAULT),)
    assert iterm2_profile.restore_commands(GUID, OTHER, OURS) == ()
    assert iterm2_profile.valid_guid(OURS) and iterm2_profile.valid_guid(OURS.lower())
    assert all(not iterm2_profile.valid_guid(value) for value in ("", OURS + "\n", OURS[:-1]))


def test_read_default_guid_distinguishes_an_absent_key_from_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = setup_fake(monkeypatch, None)
    assert iterm2_profile.read_default_guid() is None
    fake.prefs[DEFAULT] = GUID
    assert iterm2_profile.read_default_guid() == GUID

    def fail(argv: Sequence[str]) -> str:
        raise CommandError(list(argv), 127)

    monkeypatch.setattr(iterm2_profile, "iterm2_defaults", fail)
    with pytest.raises(CommandError):
        iterm2_profile.read_default_guid()


def test_real_defaults_wrapper_uses_argv_and_propagates_command_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], int]] = []

    def run(argv: Sequence[str], *, timeout: int) -> str:
        calls.append((list(argv), timeout))
        if len(calls) == 2:
            raise CommandError(list(argv), 1, detail="does not exist")
        return "value\n"

    monkeypatch.setattr(iterm2_profile, "run_output", run)
    monkeypatch.setattr(iterm2_profile, "iterm2_defaults", REAL_DEFAULTS)
    assert iterm2_profile.read_default_guid() == "value"
    assert iterm2_profile.read_default_guid() is None
    assert calls == [(["/usr/bin/defaults", "read", DOMAIN, DEFAULT], 20)] * 2


def test_without_a_fake_every_defaults_call_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(CommandError) as exc:
        iterm2_profile.iterm2_defaults(("read", "x"))
    assert exc.value.returncode == 127
    assert before(tmp_path)[0].startswith("iterm2: partial: could not read your default profile")
    assert not state(tmp_path).default_set
