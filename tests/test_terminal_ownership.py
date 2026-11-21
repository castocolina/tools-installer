"""Whole-file terminal ownership through the public lifecycle."""

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast, get_args

import pytest

import installer.terminal_keys as terminal_keys
from installer.atomic import FileSnapshot
from installer.terminal_keys import (
    KEYS_PENDING,
    TERMINAL_KEYS,
    DefaultProfile,
    KeysRow,
    OwnedKeys,
    OwnedRegion,
    Ownership,
    Vendor,
    WholeFile,
    apply_terminal_keys,
    before_removal_terminal_keys,
    strip_terminal_keys,
    terminal_keys_pending,
    variant_plan,
)
from installer.terminal_regions import KeysPlan, Restored

BODY = '{\n  "Guid": "FIXTURE-GUID",\n  "Value": 1\n}\n'
ID = "fixture-whole"


def path_for(platform: str, home: Path, environ: Mapping[str, str]) -> Path:
    del platform, environ
    return home / "fixture" / "whole.json"


def proof(text: str) -> bool:
    try:
        return json.loads(text).get("Guid") == "FIXTURE-GUID"
    except (ValueError, AttributeError):
        return False


def validate(text: str) -> None:
    json.loads(text)


def row(hook: DefaultProfile | None = None) -> KeysRow:
    def plan(
        platform: str, text: str, path: Path, home: Path, environ: Mapping[str, str]
    ) -> KeysPlan:
        del platform, text, path, home, environ
        return KeysPlan(BODY, notes=("fixture note",))

    return KeysRow(
        WholeFile(proof, plan, hook),
        path_for,
        variant_plan,
        validate,
        "Fixture whole file.",
        "terminal-fixture-whole-created",
        Vendor("fixture"),
        bind_created_path=True,
    )


def apply(r: KeysRow, home: Path, *, recorded: bool = False) -> tuple[tuple[str, ...], str | None]:
    return apply_terminal_keys(r, ID, "macos", home, {}, skip_recorded=recorded)


def pending(r: KeysRow, home: Path) -> str | None:
    return terminal_keys_pending(r, ID, "macos", home, {})


def strip(r: KeysRow, home: Path) -> tuple[str, ...]:
    return strip_terminal_keys(r, ID, "macos", home, {})


def records(home: Path) -> tuple[Path, Path, Path]:
    base = home / ".local/share/tools-installer"
    marker = base / "terminal-fixture-whole-created"
    return base / f"terminal-tuning-{ID}", marker, marker.with_name(marker.name + "-path")


def test_a_whole_file_row_applies_reports_drift_and_strips(tmp_path: Path) -> None:
    r = row()
    path = path_for("macos", tmp_path, {})
    assert apply(r, tmp_path) == (("Fixture whole file.", "fixture note"), None)
    assert path.read_text() == BODY
    record, marker, sidecar = records(tmp_path)
    assert record.read_text() == "written\n"
    assert marker.read_text().splitlines() == ["created", str(path.parent)]
    assert sidecar.read_text() == f"{path}\n"
    assert pending(r, tmp_path) is None
    path.write_text('{"Guid":"FIXTURE-GUID", "Value":2}')
    assert pending(r, tmp_path) == KEYS_PENDING
    assert apply(r, tmp_path, recorded=True)[1] is None
    assert path.read_text() == BODY
    assert pending(r, tmp_path) is None
    assert strip(r, tmp_path) == ()
    assert not path.parent.exists()
    assert not any(p.exists() for p in (record, marker, sidecar))
    assert strip(r, tmp_path) == ()


def test_a_second_apply_changes_no_byte(tmp_path: Path) -> None:
    r = row()
    apply(r, tmp_path)
    assert apply(r, tmp_path, recorded=True) == ((), None)
    apply(r, tmp_path)
    assert path_for("", tmp_path, {}).read_text() == BODY


@pytest.mark.parametrize("text,marked", [("foreign", False), (BODY, False), ("foreign", True)])
def test_a_foreign_whole_file_is_refused_and_never_overwritten(
    tmp_path: Path, text: str, marked: bool
) -> None:
    r = row()
    path = path_for("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(text)
    record, marker, _ = records(tmp_path)
    if marked:
        marker.parent.mkdir(parents=True)
        marker.write_text("created\n")
    reason = "whole.json is not the installer's; left as it is"
    assert apply(r, tmp_path) == ((), reason)
    assert pending(r, tmp_path) == reason
    assert not record.exists()
    assert "not the installer's" in strip(r, tmp_path)[0]
    assert path.read_text() == text
    assert not marker.exists()


@pytest.mark.parametrize(
    "text,marked,owned",
    [
        ("foreign", False, False),
        (BODY, False, False),
        ("foreign", True, False),
        ('{"Guid":"FIXTURE-GUID","Value":2}', True, True),
    ],
)
def test_strip_deletes_a_whole_file_only_with_marker_and_proof(
    tmp_path: Path, text: str, marked: bool, owned: bool
) -> None:
    path = path_for("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(text)
    _, marker, _ = records(tmp_path)
    if marked:
        marker.parent.mkdir(parents=True)
        marker.write_text("created\n")
    result = strip(row(), tmp_path)
    if owned:
        assert result == () and not path.exists()
    else:
        assert "not the installer's" in result[0] and path.read_text() == text


def test_a_symlink_at_the_whole_file_path_is_refused(tmp_path: Path) -> None:
    path = path_for("", tmp_path, {})
    path.parent.mkdir()
    target = tmp_path / "target"
    target.write_text("foreign")
    path.symlink_to(target)
    reason = "whole.json is a symlink; left as it is"
    assert apply(row(), tmp_path) == ((), reason)
    assert pending(row(), tmp_path) == reason
    assert "symlink" in strip(row(), tmp_path)[0]
    assert path.is_symlink() and target.read_text() == "foreign"


def hook(
    events: list[tuple[str, bool, bool]],
    home: Path,
    *,
    named: bool = True,
    switching: bool = False,
    confirmed: bool = True,
) -> DefaultProfile:
    def before(platform: str, h: Path, env: Mapping[str, str], flag: bool) -> tuple[str, ...]:
        del platform, env
        events.append(("before", flag, path_for("", h, {}).exists()))
        return ("before",)

    def after(platform: str, h: Path, env: Mapping[str, str], flag: bool) -> tuple[str, ...]:
        del platform, env
        events.append(("after", flag, path_for("", h, {}).exists()))
        return ("after",)

    def restore(platform: str, h: Path, env: Mapping[str, str], flag: bool) -> Restored:
        del platform, env
        events.append(("restore", flag, path_for("", h, {}).exists()))
        return Restored(() if confirmed else ("hook: could not restore",), confirmed)

    def still(platform: str, h: Path, env: Mapping[str, str]) -> bool:
        del platform, h, env
        return named

    def switch(platform: str, h: Path, env: Mapping[str, str]) -> bool:
        del platform, h, env
        return switching

    del home
    return DefaultProfile(before, after, restore, still, switch)


def test_a_deleted_whole_file_stays_deleted_without_a_hook_and_returns_with_one(
    tmp_path: Path,
) -> None:
    r = row()
    apply(r, tmp_path)
    path = path_for("", tmp_path, {})
    path.unlink()
    assert pending(r, tmp_path) is None
    assert apply(r, tmp_path, recorded=True) == ((), None)
    assert not path.exists()
    apply(r, tmp_path)
    path.unlink()
    r = row(hook([], tmp_path))
    assert pending(r, tmp_path) == KEYS_PENDING
    apply(r, tmp_path, recorded=True)
    assert path.exists()
    path.unlink()
    r = row(hook([], tmp_path, named=False))
    assert pending(r, tmp_path) is None
    apply(r, tmp_path, recorded=True)
    assert not path.exists()


def test_the_default_profile_hook_runs_around_the_write(tmp_path: Path) -> None:
    events: list[tuple[str, bool, bool]] = []
    r = row(hook(events, tmp_path, switching=True))
    assert apply(r, tmp_path) == (("Fixture whole file.", "fixture note", "before", "after"), None)
    assert events == [("before", False, False), ("after", False, True)]
    events.clear()
    assert apply(r, tmp_path, recorded=True) == (("before", "after"), None)
    assert events == [("before", True, True), ("after", True, True)]
    assert pending(r, tmp_path) == KEYS_PENDING
    assert pending(row(hook(events, tmp_path)), tmp_path) is None
    path_for("", tmp_path, {}).write_text('{"Guid":"FIXTURE-GUID","Value":2}')
    events.clear()
    assert apply(r, tmp_path, recorded=True)[0] == (
        "Fixture whole file.",
        "fixture note",
        "before",
        "after",
    )
    assert events == [("before", True, True), ("after", True, True)]
    events.clear()
    assert strip(r, tmp_path) == ()
    assert events == [("restore", True, True)]


def test_a_strip_whose_restore_is_not_confirmed_keeps_the_file_and_every_record(
    tmp_path: Path,
) -> None:
    events: list[tuple[str, bool, bool]] = []
    r = row(hook(events, tmp_path, confirmed=False))
    apply(r, tmp_path)
    result = strip(r, tmp_path)
    assert result[0] == "hook: could not restore"
    assert "kept because the default profile was not restored" in result[1]
    assert path_for("", tmp_path, {}).exists() and all(p.exists() for p in records(tmp_path))
    assert strip(row(hook(events, tmp_path)), tmp_path) == ()
    assert not any(p.exists() for p in records(tmp_path))


def test_before_removal_runs_only_the_restore_with_final_false(tmp_path: Path) -> None:
    events: list[tuple[str, bool, bool]] = []
    r = row(hook(events, tmp_path, confirmed=False))
    apply(r, tmp_path)
    events.clear()
    assert before_removal_terminal_keys(r, ID, "macos", tmp_path, {}) == Restored(
        ("hook: could not restore",), False
    )
    assert events == [("restore", False, True)]
    assert all(p.exists() for p in records(tmp_path))
    for candidate in (row(), TERMINAL_KEYS["kitty"]):
        assert before_removal_terminal_keys(candidate, ID, "macos", tmp_path, {}) == Restored(
            (), True
        )


@pytest.mark.parametrize("recorded", [False, True])
def test_the_whole_file_write_refuses_a_file_that_changed_after_the_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recorded: bool
) -> None:
    events: list[tuple[str, bool, bool]] = []
    r = row(hook(events, tmp_path))
    apply(r, tmp_path)
    path = path_for("", tmp_path, {})
    path.write_text('{"Guid":"FIXTURE-GUID","Value":2}')
    original = terminal_keys.read_settings

    def racing(p: Path) -> FileSnapshot | None:
        snapshot = original(p)
        p.write_text("other writer")
        return snapshot

    monkeypatch.setattr(terminal_keys, "read_settings", racing)
    events.clear()
    assert apply(r, tmp_path, recorded=recorded) == ((), "changed while being written")
    assert path.read_text() == "other writer"
    assert all(e[0] != "after" for e in events)
    assert records(tmp_path)[0].read_text() == "written\n"


def test_a_read_error_is_silent_for_a_recorded_row_and_reported_otherwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = row()
    apply(r, tmp_path)

    def broken(path: Path) -> FileSnapshot | None:
        del path
        raise OSError("boom")

    monkeypatch.setattr(terminal_keys, "read_settings", broken)
    assert apply(r, tmp_path, recorded=True) == ((), None)
    assert apply(r, tmp_path) == ((), "boom")
    assert pending(r, tmp_path) is None
    records(tmp_path)[0].unlink()
    assert pending(r, tmp_path) == "boom"


def test_the_variant_callables_receive_the_explicit_home_and_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[tuple[Path, Mapping[str, str]]] = []

    def plan(platform: str, text: str, path: Path, home: Path, env: Mapping[str, str]) -> KeysPlan:
        del platform, text, path
        received.append((home, env))
        return KeysPlan(BODY)

    r = replace(row(), ownership=WholeFile(proof, plan))
    other = tmp_path / "other"
    monkeypatch.setattr(Path, "home", lambda: other)
    monkeypatch.setenv("XDG_DATA_HOME", str(other))
    env = {"XDG_DATA_HOME": str(tmp_path / "data")}
    apply_terminal_keys(r, ID, "macos", tmp_path, env, skip_recorded=False)
    terminal_keys_pending(r, ID, "macos", tmp_path, env)
    strip_terminal_keys(r, ID, "macos", tmp_path, env)
    assert received and all(pair == (tmp_path, env) for pair in received)
    assert (tmp_path / "data/tools-installer").exists()
    assert not other.exists()


def test_the_four_registry_region_rows_stay_region_rows() -> None:
    for tool_id in ("alacritty", "kitty", "wezterm", "ghostty"):
        assert isinstance(TERMINAL_KEYS[tool_id].ownership, OwnedRegion)


SEED = '{\n  "global": {\n    "a": "b"\n  },\n  "terminal": {\n    "keep": "x"\n  }\n}\n'
KID = "fixture-keys"


def keys_path(platform: str, home: Path, env: Mapping[str, str]) -> Path:
    del platform
    return Path(env["FIXTURE_KEYS"]) if "FIXTURE_KEYS" in env else home / "fixture/keys.json"


def keys_row(value: str = "send:\x0c") -> KeysRow:
    def seed(platform: str) -> str:
        del platform
        return SEED

    def keys(
        platform: str, home: Path, env: Mapping[str, str]
    ) -> tuple[tuple[tuple[str, str], str], ...]:
        del platform, home, env
        return ((("terminal", "k-chord"), value),)

    def taken(
        platform: str,
        doc: Mapping[str, object],
        key: tuple[tuple[str, str], str],
        held: tuple[tuple[tuple[str, str], str], ...],
    ) -> str | None:
        del platform, held
        section, chord = key[0]
        for name, entries in doc.items():
            if (
                isinstance(entries, dict)
                and chord in entries
                and (name != section or entries[chord] != key[1])
            ):
                return "fixture: partial: you already bind k-chord"
        return None

    def validate_keys(text: str) -> None:
        document: object = json.loads(text)
        if not isinstance(document, dict) or not all(
            isinstance(v, dict) for v in cast(dict[str, object], document).values()
        ):
            raise terminal_keys.TerminalShellError("invalid sections")

    def plan(platform: str, text: str, path: Path) -> KeysPlan:
        del platform, text, path
        return KeysPlan(None, notes=("fixture keys note",))

    return KeysRow(
        OwnedKeys(seed, seed, keys, taken),
        keys_path,
        plan,
        validate_keys,
        "Fixture owned keys.",
        "terminal-fixture-keys-created",
        Vendor("fixture"),
        bind_created_path=True,
    )


def keys_apply(
    r: KeysRow, home: Path, env: Mapping[str, str] | None = None, *, recorded: bool = False
) -> tuple[tuple[str, ...], str | None]:
    return apply_terminal_keys(r, KID, "linux", home, env or {}, skip_recorded=recorded)


def keys_strip(r: KeysRow, home: Path, env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    return strip_terminal_keys(r, KID, "linux", home, env or {})


def keys_pending(r: KeysRow, home: Path, env: Mapping[str, str] | None = None) -> str | None:
    return terminal_keys_pending(r, KID, "linux", home, env or {})


def test_a_missing_keys_file_is_seeded_with_the_vendor_default_plus_the_owned_key(
    tmp_path: Path,
) -> None:
    r = keys_row()
    path = keys_path("", tmp_path, {})
    assert keys_apply(r, tmp_path) == (("Fixture owned keys.", "fixture keys note"), None)
    assert path.read_text() == SEED.replace('    "keep"', '    "k-chord": "send:\\f",\n    "keep"')
    record = tmp_path / ".local/share/tools-installer/terminal-tuning-fixture-keys"
    assert json.loads(record.read_text()) == {
        "deleted": [],
        "keys": [["terminal", "k-chord", "send:\x0c"]],
        "path": str(path),
    }
    record, marker, sidecar = keys_records(tmp_path)
    assert marker.exists() and sidecar.read_text() == f"{path}\n"
    assert json.loads(path.read_text())["terminal"]["k-chord"] == "send:\x0c"
    assert keys_pending(r, tmp_path) is None
    assert keys_strip(r, tmp_path) == ()
    assert not path.parent.exists() and not any(p.exists() for p in (record, marker, sidecar))


def test_a_changed_keys_path_never_inherits_the_old_ledger(tmp_path: Path) -> None:
    r = keys_row()
    path = keys_path("", tmp_path, {})
    keys_apply(r, tmp_path)
    old = path.read_text()
    other = tmp_path / "other.json"
    other.write_text(SEED)
    env = {"FIXTURE_KEYS": str(other)}
    assert keys_pending(r, tmp_path, env) == KEYS_PENDING
    assert "not the file now resolved" in keys_strip(r, tmp_path, env)[0]
    assert path.read_text() == old and other.read_text() == SEED
    assert keys_strip(r, tmp_path) == ()


def test_a_symlink_at_the_keys_path_fails_closed(tmp_path: Path) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    text = path.read_text()
    path.unlink()
    target = tmp_path / "target"
    target.write_text(text)
    path.symlink_to(target)
    saved = {p: p.read_bytes() for p in keys_records(tmp_path)}
    assert keys_apply(r, tmp_path) == ((), "keys.json is a symlink; left as it is")
    assert keys_apply(r, tmp_path, recorded=True) == ((), None)
    assert keys_pending(r, tmp_path) is None
    assert keys_strip(r, tmp_path) == ("fixture-keys: keys.json is a symlink; left as it is",)
    assert path.is_symlink() and target.read_text() == text
    assert all(p.read_bytes() == data for p, data in saved.items())
    keys_records(tmp_path)[0].unlink()
    assert keys_pending(r, tmp_path) == "keys.json is a symlink; left as it is"


def test_a_created_marker_bound_to_another_path_leaves_the_file_and_the_records_untouched(
    tmp_path: Path,
) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    text = path.read_text()
    sidecar = tmp_path / ".local/share/tools-installer/terminal-fixture-keys-created-path"
    sidecar.write_text("elsewhere\n")
    assert keys_strip(r, tmp_path) == (
        "fixture-keys: created config at elsewhere is not the file now resolved; left alone",
    )
    assert path.read_text() == text


def test_deleted_keys_stay_deleted_until_reinstall(tmp_path: Path) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    path.write_text(SEED)
    assert keys_apply(r, tmp_path, recorded=True) == ((), None)
    assert keys_apply(r, tmp_path, recorded=True) == ((), None)
    assert path.read_text() == SEED and keys_pending(r, tmp_path) is None
    assert keys_apply(r, tmp_path)[1] is None
    assert json.loads(path.read_text())["terminal"]["k-chord"] == "send:\x0c"


@pytest.mark.parametrize("blank", ["", "  \n"])
def test_blank_keys_file_is_seeded_without_created_marker(tmp_path: Path, blank: str) -> None:
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(blank)
    r = keys_row()
    assert keys_apply(r, tmp_path)[1] is None
    assert not keys_records(tmp_path)[1].exists()
    assert keys_strip(r, tmp_path) == ()
    assert path.read_text() == SEED


def test_owned_key_drift_and_user_change(tmp_path: Path) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    changed = keys_row("new")
    assert keys_pending(changed, tmp_path) == KEYS_PENDING
    assert keys_apply(changed, tmp_path, recorded=True)[1] is None
    path = keys_path("", tmp_path, {})
    path.write_text(path.read_text().replace('"new"', '"user"'))
    assert keys_apply(changed, tmp_path, recorded=True) == (
        ("fixture: partial: you already bind k-chord",),
        None,
    )
    assert keys_strip(changed, tmp_path) == ()
    assert json.loads(path.read_text())["terminal"]["k-chord"] == "user"


@pytest.mark.parametrize(
    "text,reason",
    [
        ("{not json", "the file does not parse; left as it is"),
        ("[]", "the file does not parse; left as it is"),
        ('{"terminal": 3}', "invalid sections"),
    ],
)
def test_bad_keys_file_is_refused(tmp_path: Path, text: str, reason: str) -> None:
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(text)
    assert keys_apply(keys_row(), tmp_path) == ((), reason)
    assert keys_pending(keys_row(), tmp_path) == reason
    assert path.read_text() == text and not keys_records(tmp_path)[0].exists()


def test_owned_keys_write_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(SEED)
    original = terminal_keys.read_settings

    def racing(p: Path) -> FileSnapshot | None:
        snapshot = original(p)
        p.write_text("other writer")
        return snapshot

    monkeypatch.setattr(terminal_keys, "read_settings", racing)
    assert keys_apply(keys_row(), tmp_path) == ((), "changed while being written")
    assert path.read_text() == "other writer"


def test_user_binding_is_kept(tmp_path: Path) -> None:
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    text = SEED.replace('"keep": "x"', '"k-chord": "user", "keep": "x"')
    path.write_text(text)
    r = keys_row()
    assert keys_apply(r, tmp_path) == (("fixture: partial: you already bind k-chord",), None)
    assert path.read_text() == text
    assert json.loads(keys_records(tmp_path)[0].read_text()) == {
        "deleted": [],
        "keys": [],
        "path": str(path),
    }
    assert keys_pending(r, tmp_path) is None
    assert keys_strip(r, tmp_path) == ()
    assert path.read_text() == text


def keys_records(home: Path) -> tuple[Path, Path, Path]:
    base = home / ".local/share/tools-installer"
    marker = base / "terminal-fixture-keys-created"
    return base / "terminal-tuning-fixture-keys", marker, marker.with_name(marker.name + "-path")


@pytest.mark.parametrize("reinstall", [False, True])
def test_tombstone_survives_two_reconfigures_and_strip_or_reinstall(
    tmp_path: Path, reinstall: bool
) -> None:
    r = keys_row()
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(SEED)
    keys_apply(r, tmp_path)
    path.write_text(SEED)
    record = keys_records(tmp_path)[0]
    for _ in range(2):
        assert keys_apply(r, tmp_path, recorded=True) == ((), None)
        assert path.read_text() == SEED
        assert json.loads(record.read_text()) == {
            "deleted": [["terminal", "k-chord"]],
            "keys": [],
            "path": str(path),
        }
        assert keys_pending(r, tmp_path) is None
    if reinstall:
        assert keys_apply(r, tmp_path)[1] is None
        assert json.loads(record.read_text())["deleted"] == []
        assert json.loads(record.read_text())["keys"] == [["terminal", "k-chord", "send:\x0c"]]
        assert json.loads(path.read_text())["terminal"]["k-chord"] == "send:\x0c"
    else:
        assert keys_strip(r, tmp_path) == ()
        assert path.read_text() == SEED and not record.exists()


def test_recorded_ownership_precedes_naive_user_binding_detection(tmp_path: Path) -> None:
    first = keys_row("old")
    keys_apply(first, tmp_path)
    path = keys_path("", tmp_path, {})
    original = path.read_text()
    second = keys_row("new")
    assert keys_pending(second, tmp_path) == KEYS_PENDING
    assert keys_apply(second, tmp_path, recorded=True)[1] is None
    assert path.read_text() == original.replace('"old"', '"new"')
    assert json.loads(keys_records(tmp_path)[0].read_text())["keys"] == [
        ["terminal", "k-chord", "new"]
    ]
    user = path.read_text().replace('"new"', '"user"')
    path.write_text(user)
    assert keys_apply(second, tmp_path, recorded=True) == (
        ("fixture: partial: you already bind k-chord",),
        None,
    )
    assert path.read_text() == user and keys_pending(second, tmp_path) is None
    assert json.loads(keys_records(tmp_path)[0].read_text())["keys"] == []
    assert keys_strip(second, tmp_path) == () and path.read_text() == user


def test_record_aware_detector_allows_drift_and_keeps_user_change(tmp_path: Path) -> None:
    keys_apply(keys_row("old"), tmp_path)
    r = keys_row("new")
    owned = r.ownership
    assert isinstance(owned, OwnedKeys)

    def taken(
        platform: str,
        doc: Mapping[str, object],
        key: terminal_keys.OwnedKey,
        held: tuple[terminal_keys.OwnedKey, ...],
    ) -> str | None:
        del platform
        section = doc.get(key[0][0])
        if isinstance(section, dict):
            current: object = cast(dict[str, object], section).get(key[0][1])
            if current not in (key[1], dict(held).get(key[0]), None):
                return "fixture: partial: you already bind k-chord"
        return None

    r = replace(r, ownership=replace(owned, taken=taken))
    path = keys_path("", tmp_path, {})
    original = path.read_text()
    assert keys_pending(r, tmp_path) == KEYS_PENDING
    assert keys_apply(r, tmp_path, recorded=True)[1] is None
    assert path.read_text() == original.replace('"old"', '"new"')
    assert json.loads(keys_records(tmp_path)[0].read_text())["keys"] == [
        ["terminal", "k-chord", "new"]
    ]
    user = path.read_text().replace('"new"', '"user"')
    path.write_text(user)
    assert keys_apply(r, tmp_path, recorded=True) == (
        ("fixture: partial: you already bind k-chord",),
        None,
    )
    assert path.read_text() == user and keys_pending(r, tmp_path) is None
    assert keys_strip(r, tmp_path) == () and path.read_text() == user


@pytest.mark.parametrize("matches", [True, False])
def test_strip_uses_pinned_default_never_seed(tmp_path: Path, matches: bool) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    owned = r.ownership
    assert isinstance(owned, OwnedKeys)
    calls: list[str] = []

    def unavailable(platform: str) -> str:
        del platform
        raise terminal_keys.TerminalShellError("seed refused")

    def pinned(platform: str) -> str:
        calls.append(platform)
        return SEED if matches else "different"

    r = replace(r, ownership=replace(owned, seed=unavailable, pinned=pinned))
    assert keys_strip(r, tmp_path) == ()
    assert calls == ["linux"]
    path = keys_path("", tmp_path, {})
    if matches:
        assert not path.exists() and not path.parent.exists()
    else:
        assert path.read_text() == SEED
    assert not any(p.exists() for p in keys_records(tmp_path))


@pytest.mark.parametrize("user_key", [False, True])
def test_strip_removes_only_an_empty_section_after_its_owned_key(
    tmp_path: Path, user_key: bool
) -> None:
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text('{"global": {}, "terminal": {"mine": "x"}}' if user_key else '{"global": {}}')
    r = keys_row()
    assert keys_apply(r, tmp_path)[1] is None
    assert keys_strip(r, tmp_path) == ()
    assert json.loads(path.read_text()) == (
        {"global": {}, "terminal": {"mine": "x"}} if user_key else {"global": {}}
    )


@pytest.mark.parametrize(
    "garbage", ["not json", "{}", "[]", '{"keys": [], "deleted": [], "path": 3}']
)
def test_invalid_ownership_record_blocks_apply_and_strip(tmp_path: Path, garbage: str) -> None:
    r = keys_row()
    assert keys_apply(r, tmp_path)[1] is None
    path = keys_path("", tmp_path, {})
    record, marker, sidecar = keys_records(tmp_path)
    record.write_text(garbage)
    saved = {p: p.read_bytes() for p in (path, record, marker, sidecar)}
    for recorded in (False, True):
        assert keys_apply(r, tmp_path, recorded=recorded) == (
            ("fixture-keys: the ownership record is unreadable; left as it is",),
            None,
        )
    assert keys_strip(r, tmp_path) == (
        "fixture-keys: the ownership record is unreadable; left as it is",
    )
    assert all(p.read_bytes() == content for p, content in saved.items())


def test_unreadable_ownership_record_blocks_apply_and_strip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    record = keys_records(tmp_path)[0]
    saved = {p: p.read_bytes() for p in (keys_path("", tmp_path, {}), *keys_records(tmp_path))}
    read = Path.read_text

    def unreadable(path: Path, *args: object, **kwargs: object) -> str:
        if path == record:
            raise PermissionError("unreadable")
        del args, kwargs
        return read(path)

    monkeypatch.setattr(Path, "read_text", unreadable)
    message = "fixture-keys: the ownership record is unreadable; left as it is"
    assert keys_apply(r, tmp_path) == ((message,), None)
    assert keys_apply(r, tmp_path, recorded=True) == ((message,), None)
    assert keys_strip(r, tmp_path) == (message,)
    assert all(p.read_bytes() == content for p, content in saved.items())


def test_missing_ownership_record_still_allows_apply_and_strip(tmp_path: Path) -> None:
    r = keys_row()
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(SEED)
    assert keys_strip(r, tmp_path) == ()
    assert path.read_text() == SEED
    assert keys_apply(r, tmp_path, recorded=True)[1] is None
    assert keys_records(tmp_path)[0].exists()
    assert keys_strip(r, tmp_path) == () and path.read_text() == SEED


def test_user_sections_survive_apply_and_strip_in_shuffled_order(tmp_path: Path) -> None:
    text = (
        '{\n  "other": {"z": "1", "a": "2"},\n'
        '  "terminal": {\n    "second": "2",\n    "first": "1"\n  },\n'
        '  "global": {"y": "3", "x": "4"}\n}\n'
    )
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(text)
    r = keys_row()
    assert keys_apply(r, tmp_path)[1] is None
    assert path.read_text() == text.replace(
        '    "second"', '    "k-chord": "send:\\f",\n    "second"'
    )
    assert keys_strip(r, tmp_path) == () and path.read_text() == text


def test_second_owned_keys_apply_and_reinstall_are_byte_identical(tmp_path: Path) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    text = path.read_bytes()
    record = keys_records(tmp_path)[0].read_bytes()
    assert keys_apply(r, tmp_path, recorded=True) == ((), None)
    assert path.read_bytes() == text and keys_records(tmp_path)[0].read_bytes() == record
    assert keys_apply(r, tmp_path) == ((), None)
    assert path.read_bytes() == text and keys_records(tmp_path)[0].read_bytes() == record


def test_owned_keys_receive_explicit_home_and_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = keys_row()
    owned = r.ownership
    assert isinstance(owned, OwnedKeys)
    received: list[tuple[Path, Mapping[str, str]]] = []

    def keys(
        platform: str, home: Path, env: Mapping[str, str]
    ) -> tuple[terminal_keys.OwnedKey, ...]:
        received.append((home, env))
        return owned.keys(platform, home, env)

    r = replace(r, ownership=replace(owned, keys=keys))
    other = tmp_path / "process-home"
    monkeypatch.setattr(Path, "home", lambda: other)
    monkeypatch.setenv("XDG_DATA_HOME", str(other))
    env = {"XDG_DATA_HOME": str(tmp_path / "data")}
    assert keys_apply(r, tmp_path, env)[1] is None
    assert keys_pending(keys_row("drift"), tmp_path, env) == KEYS_PENDING
    assert received == [(tmp_path, env)]
    assert (tmp_path / "data/tools-installer/terminal-tuning-fixture-keys").exists()
    assert keys_strip(r, tmp_path, env) == ()
    assert not other.exists()


@pytest.mark.parametrize("blank", [None, "", "  \n"])
def test_owned_keys_pending_before_apply_and_before_removal(
    tmp_path: Path, blank: str | None
) -> None:
    r = keys_row()
    path = keys_path("", tmp_path, {})
    if blank is not None:
        path.parent.mkdir()
        path.write_text(blank)
    assert keys_pending(r, tmp_path) == KEYS_PENDING
    assert before_removal_terminal_keys(r, KID, "linux", tmp_path, {}) == Restored((), True)
    assert (path.read_text() == blank) if blank is not None else not path.exists()
    assert not any(p.exists() for p in keys_records(tmp_path))


def test_ownership_union_names_three_variants() -> None:
    assert get_args(Ownership) == (OwnedRegion, WholeFile, OwnedKeys)


@pytest.mark.parametrize("blank", [None, "", "  \n"])
def test_seed_refusal_leaves_missing_or_blank_file_untouched(
    tmp_path: Path, blank: str | None
) -> None:
    r = keys_row()
    owned = r.ownership
    assert isinstance(owned, OwnedKeys)

    def refuse(platform: str) -> str:
        del platform
        raise terminal_keys.TerminalShellError("seed refused")

    r = replace(r, ownership=replace(owned, seed=refuse))
    path = keys_path("", tmp_path, {})
    if blank is not None:
        path.parent.mkdir()
        path.write_text(blank)
    assert keys_apply(r, tmp_path) == ((), "seed refused")
    assert (path.read_text() == blank) if blank is not None else not path.exists()
    assert not any(p.exists() for p in keys_records(tmp_path))
    record = keys_records(tmp_path)[0]
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"keys": [], "deleted": [], "path": str(path)}))
    assert keys_apply(r, tmp_path, recorded=True) == ((), None)
    assert (path.read_text() == blank) if blank is not None else not path.exists()


def test_created_keys_with_user_addition_are_kept(tmp_path: Path) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    path.write_text(
        path.read_text().replace('    "keep": "x"', '    "mine": "y",\n    "keep": "x"')
    )
    assert keys_strip(r, tmp_path) == ()
    assert path.read_text() == SEED.replace('    "keep": "x"', '    "mine": "y",\n    "keep": "x"')
    assert not any(p.exists() for p in keys_records(tmp_path))


@pytest.mark.parametrize("recorded", [False, True])
def test_owned_keys_write_race_for_first_and_recorded_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recorded: bool
) -> None:
    r = keys_row("old")
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    original = terminal_keys.read_settings

    def racing(p: Path) -> FileSnapshot | None:
        snapshot = original(p)
        p.write_text("other writer")
        return snapshot

    monkeypatch.setattr(terminal_keys, "read_settings", racing)
    assert keys_apply(keys_row("new"), tmp_path, recorded=recorded) == (
        (),
        "changed while being written",
    )
    assert path.read_text() == "other writer"


def test_owned_keys_read_error_recorded_is_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)

    def broken(path: Path) -> FileSnapshot | None:
        del path
        raise OSError("boom")

    monkeypatch.setattr(terminal_keys, "read_settings", broken)
    assert keys_apply(r, tmp_path, recorded=True) == ((), None)
    assert keys_apply(r, tmp_path) == ((), "boom")
    assert keys_pending(r, tmp_path) is None
    keys_records(tmp_path)[0].unlink()
    assert keys_pending(r, tmp_path) == "boom"


@pytest.mark.parametrize("created", [False, True])
def test_path_mismatch_leaves_both_files_and_all_records(tmp_path: Path, created: bool) -> None:
    r = keys_row()
    path = keys_path("", tmp_path, {})
    if not created:
        path.parent.mkdir()
        path.write_text(SEED)
    keys_apply(r, tmp_path)
    old = path.read_bytes()
    other = tmp_path / "other.json"
    other.write_text(SEED)
    saved = {p: p.read_bytes() for p in keys_records(tmp_path) if p.exists()}
    env = {"FIXTURE_KEYS": str(other)}
    assert keys_pending(r, tmp_path, env) == KEYS_PENDING
    assert keys_strip(r, tmp_path, env) == (
        f"fixture-keys: edited keys were recorded for {path}, "
        "not the file now resolved; left alone",
    )
    assert path.read_bytes() == old and other.read_text() == SEED
    assert all(p.read_bytes() == data for p, data in saved.items())
    assert keys_strip(r, tmp_path) == ()
    if not created:
        assert path.read_text() == SEED


@pytest.mark.parametrize("recorded", [False, True])
@pytest.mark.parametrize("wanted", ["old", "new"])
def test_path_change_never_claims_equal_or_old_value(
    tmp_path: Path, recorded: bool, wanted: str
) -> None:
    path = keys_path("", tmp_path, {})
    path.parent.mkdir()
    path.write_text(SEED)
    keys_apply(keys_row("old"), tmp_path)
    old = path.read_bytes()
    other = tmp_path / "other.json"
    text = SEED.replace('    "keep"', '    "k-chord": "old",\n    "keep"')
    other.write_text(text)
    env = {"FIXTURE_KEYS": str(other)}
    result = keys_apply(keys_row(wanted), tmp_path, env, recorded=recorded)
    expected = () if wanted == "old" else ("fixture: partial: you already bind k-chord",)
    assert result == (expected, None)
    assert other.read_text() == text and path.read_bytes() == old
    assert json.loads(keys_records(tmp_path)[0].read_text()) == {
        "deleted": [],
        "keys": [],
        "path": str(other),
    }
    assert keys_strip(keys_row(wanted), tmp_path, env) == ()
    assert other.read_text() == text and path.read_bytes() == old


@pytest.mark.parametrize("missing", [False, True])
def test_mismatched_or_missing_created_sidecar_preserves_every_record(
    tmp_path: Path, missing: bool
) -> None:
    r = keys_row()
    keys_apply(r, tmp_path)
    path = keys_path("", tmp_path, {})
    record, marker, sidecar = keys_records(tmp_path)
    if missing:
        sidecar.unlink()
    else:
        sidecar.write_text("elsewhere\n")
    saved = {p: p.read_bytes() for p in (path, record, marker, sidecar) if p.exists()}
    shown = "an unrecorded path" if missing else "elsewhere"
    assert keys_strip(r, tmp_path) == (
        f"fixture-keys: created config at {shown} is not the file now resolved; left alone",
    )
    assert all(p.read_bytes() == data for p, data in saved.items())
    assert sidecar.exists() is not missing
