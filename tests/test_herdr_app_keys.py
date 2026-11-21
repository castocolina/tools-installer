"""Herdr app key defaults and version-gated seeding."""

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from installer import herdr_app_keys
from installer.agent_settings import insert_key, remove_key
from installer.run import CommandError
from installer.terminal_regions import TerminalShellError

_REAL_SEAM = herdr_app_keys.herdr_app_version
_DEFAULTS = Path(__file__).parent.parent / "installer/vendor_defaults/herdr-app-0.1.16"
_HASHES = {
    "keys.json": "d1831fe2e9a685abf5fd95c156f4425fcbc17f81919163955a3688a166ea269f",
    "keys.macos.json": "8728a5190aa2ef1609c08c0cb49cf31dd74ab7018944b6453d9f371570d023c0",
}


def test_the_pinned_vendor_defaults_match_their_hashes() -> None:
    assert herdr_app_keys.HERDR_APP_DEFAULTS_VERSION == "0.1.16"
    assert _DEFAULTS.name == f"herdr-app-{herdr_app_keys.HERDR_APP_DEFAULTS_VERSION}"
    assert herdr_app_keys.HERDR_APP_DEFAULTS_SHA256 == _HASHES
    for name, digest in _HASHES.items():
        data = (_DEFAULTS / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        assert isinstance(json.loads(data), dict)


@pytest.mark.parametrize(
    "platform_os,name",
    [
        ("macos", "keys.macos.json"),
        ("fedora", "keys.json"),
        ("debian", "keys.json"),
        ("arch", "keys.json"),
    ],
)
def test_the_vendor_default_for_an_os_is_the_right_file(platform_os: str, name: str) -> None:
    text = herdr_app_keys.vendor_default(platform_os)
    assert text == (_DEFAULTS / name).read_text(encoding="utf-8")
    document = cast(dict[str, dict[str, str]], json.loads(text))
    assert all("cmd-k" not in section for section in document.values())
    if platform_os == "macos":
        assert document["terminal"]["alt-left"] == "send:" + chr(27) + "b"
    else:
        assert document["global"]["ctrl-shift-k"] == "mod.open:picker"


@pytest.mark.parametrize("platform_os", ["macos", "fedora", "debian", "arch"])
def test_the_keys_path_follows_the_apps_folder_rules(platform_os: str, tmp_path: Path) -> None:
    path = herdr_app_keys.herdr_app_keys_path
    assert path(platform_os, tmp_path, {}) == tmp_path / ".config/herdr-app/keys.json"
    assert path(platform_os, tmp_path, {"XDG_CONFIG_HOME": "/x"}) == Path("/x/herdr-app/keys.json")
    assert path(platform_os, tmp_path, {"HERDR_APP_HOME": "/y", "XDG_CONFIG_HOME": "/x"}) == Path(
        "/y/keys.json"
    )
    assert path(platform_os, tmp_path, {"HERDR_APP_HOME": "", "XDG_CONFIG_HOME": "/x"}) == Path(
        "/x/herdr-app/keys.json"
    )


@pytest.mark.parametrize("platform_os,chord", [("fedora", "ctrl-shift-k"), ("macos", "cmd-k")])
def test_the_owned_keys_per_os(platform_os: str, chord: str) -> None:
    keys = herdr_app_keys.herdr_app_owned_keys(platform_os)
    assert keys == ((("terminal", chord), "send:" + chr(12)),)
    assert herdr_app_keys.clear_chord(platform_os) == keys[0][0][1]


@pytest.mark.parametrize("platform_os", ["fedora", "macos"])
def test_inserting_and_removing_the_owned_key_restores_the_vendor_default_bytes(
    platform_os: str,
) -> None:
    original = herdr_app_keys.vendor_default(platform_os)
    ((path, value),) = herdr_app_keys.herdr_app_owned_keys(platform_os)
    inserted = insert_key(original, "json", path, value).text
    assert f'"terminal": {{\n    "{path[1]}": "send:\\f",' in inserted
    assert remove_key(inserted, "json", path) == original


def test_validate_accepts_the_defaults_and_refuses_malformed_files() -> None:
    for text in (
        herdr_app_keys.vendor_default("fedora"),
        herdr_app_keys.vendor_default("macos"),
        "{}",
    ):
        herdr_app_keys.validate_herdr_app(text)
    for text, prefix in (
        ("not json", "the keys file does not parse"),
        ("[]", "the keys file must hold objects only"),
        ('{"terminal": 3}', "the keys file must hold objects only"),
    ):
        with pytest.raises(TerminalShellError) as caught:
            herdr_app_keys.validate_herdr_app(text)
        assert str(caught.value).startswith(prefix)
        assert len(str(caught.value).splitlines()) == 1


@pytest.mark.parametrize("platform_os", ["macos", "fedora"])
def test_the_seed_is_written_only_for_the_pinned_version(
    platform_os: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed: str | None = "0.1.16"

    def version(_os: str) -> str | None:
        return installed

    monkeypatch.setattr(herdr_app_keys, "herdr_app_version", version)
    assert herdr_app_keys.herdr_app_seed(platform_os) == herdr_app_keys.vendor_default(platform_os)
    for candidate, display in (("0.1.17", "0.1.17"), (None, "unknown")):
        installed = candidate
        with pytest.raises(TerminalShellError) as caught:
            herdr_app_keys.herdr_app_seed(platform_os)
        message = str(caught.value)
        assert message.startswith("partial:") and display in message and "0.1.16" in message
        assert len(message.splitlines()) == 1


def test_the_pinned_default_never_runs_the_version_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def version(platform_os: str) -> str:
        calls.append(platform_os)
        return "0.1.16"

    monkeypatch.setattr(herdr_app_keys, "herdr_app_version", version)
    for platform_os, name in (("macos", "keys.macos.json"), ("fedora", "keys.json")):
        assert herdr_app_keys.vendor_default(platform_os) == (_DEFAULTS / name).read_text(
            encoding="utf-8"
        )
    assert calls == []
    assert herdr_app_keys.herdr_app_seed("fedora") == herdr_app_keys.vendor_default("fedora")
    assert calls == ["fedora"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("herdr-app 0.1.16\n", "0.1.16"),
        ("0.1.16", "0.1.16"),
        ("herdr-app v1.20.3 (build 5)", "1.20.3"),
        ("", None),
        ("herdr-app", None),
        ("version unknown", None),
        ("1.2.3 4.5.6", "1.2.3"),
    ],
)
def test_the_app_version_parser_reads_the_first_semver(text: str, expected: str | None) -> None:
    assert herdr_app_keys.parse_app_version(text) == expected


def test_the_real_version_seam_probes_the_installed_methods_own_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    executable = tmp_path / ".local/bin/herdr-app"
    executable.parent.mkdir(parents=True)
    executable.write_text("binary", encoding="utf-8")
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "herdr-app").write_text("shadow", encoding="utf-8")
    calls: list[list[str]] = []

    def output(argv: list[str], *, timeout: float | None = None) -> str:
        assert timeout == 20
        calls.append(argv)
        return "herdr-app 0.1.16\n" if argv[0] == str(executable) else "herdr-app 9.9.9\n"

    monkeypatch.setattr(herdr_app_keys, "run_output", output)
    for path in (str(shadow) + ":" + str(executable.parent), str(shadow)):
        monkeypatch.setenv("PATH", path)
        calls.clear()
        assert _REAL_SEAM("fedora") == "0.1.16"
        assert calls == [[str(executable), "--version"]]
    executable.unlink()
    calls.clear()
    assert _REAL_SEAM("fedora") is None
    assert calls == []
    found: str | None = "/x/herdr-app"

    def which(_name: str) -> str | None:
        return found

    monkeypatch.setattr(herdr_app_keys.shutil, "which", which)
    assert _REAL_SEAM("macos") == "9.9.9"
    assert calls == [["/x/herdr-app", "--version"]]
    calls.clear()
    found = None
    assert _REAL_SEAM("macos") is None
    assert calls == []
    found = "/x/herdr-app"
    error: Exception = OSError("failed")

    def fail(argv: list[str], *, timeout: float | None = None) -> str:
        del argv, timeout
        raise error

    monkeypatch.setattr(herdr_app_keys, "run_output", fail)
    for candidate_error in (CommandError(["x", "--version"], 127, detail="x"), OSError("failed")):
        error = candidate_error
        assert _REAL_SEAM("macos") is None


@pytest.mark.parametrize(
    "text,platform_os,expected",
    [
        *(
            (text, "macos", (frozenset({"cmd"}), "k"))
            for text in ("cmd-k", "super-k", "win-k", "CMD-k", "secondary-k")
        ),
        ("CMD-K", "macos", (frozenset({"cmd", "shift"}), "k")),
        ("secondary-k", "fedora", (frozenset({"ctrl"}), "k")),
        *(
            (text, "fedora", (frozenset({"ctrl", "shift"}), "k"))
            for text in (
                "ctrl-shift-k",
                "shift-ctrl-k",
                "Ctrl-Shift-k",
                "Ctrl-Shift-K",
                "ctrl-K",
                "ctrl-shift-k x",
            )
        ),
        ("ctrl-k", "fedora", (frozenset({"ctrl"}), "k")),
        ("ctrl--", "fedora", (frozenset({"ctrl"}), "-")),
        ("-", "fedora", (frozenset[str](), "-")),
        ("f5", "fedora", (frozenset[str](), "f5")),
        ("F5", "fedora", (frozenset[str](), "f5")),
        *((text, "fedora", None) for text in ("option-k", "platform-k", "ctrl-shift-", "", "   ")),
    ],
)
def test_chords_normalize_with_the_apps_grammar(
    text: str, platform_os: str, expected: tuple[frozenset[str], str] | None
) -> None:
    assert herdr_app_keys.parse_chord(text, platform_os) == expected


@pytest.mark.parametrize(
    "platform_os,chord,value,expected",
    [
        ("fedora", "ctrl-shift-k", "mine", True),
        ("fedora", "Ctrl-Shift-K", "mine", True),
        ("fedora", "ctrl-K", "mine", True),
        ("fedora", "shift-ctrl-k", "send:" + chr(12), True),
        ("fedora", "ctrl-shift-k x", "mine", True),
        ("fedora", "ctrl-k", "mine", False),
        ("macos", "super-k", "mine", True),
    ],
)
def test_the_detector_keeps_a_user_binding_in_any_spelling(
    platform_os: str, chord: str, value: str, expected: bool
) -> None:
    key = herdr_app_keys.herdr_app_owned_keys(platform_os)[0]
    result = herdr_app_keys.herdr_app_taken(platform_os, {"terminal": {chord: value}}, key, ())
    message = "herdr-app: partial: you already bind " + key[0][1].replace("-", "+")
    assert result == (message if expected else None)


def test_the_detector_treats_a_recorded_old_value_as_ours() -> None:
    key = (("terminal", "ctrl-shift-k"), "send:" + chr(12))
    old = "send:" + chr(11)
    recorded = ((("terminal", "ctrl-shift-k"), old),)
    taken = herdr_app_keys.herdr_app_taken
    message = "herdr-app: partial: you already bind ctrl+shift+k"
    assert taken("fedora", {"terminal": {"ctrl-shift-k": old}}, key, recorded) is None
    assert taken("fedora", {"terminal": {"ctrl-shift-k": old}}, key, ()) == message
    assert taken("fedora", {"terminal": {"shift-ctrl-k": old}}, key, recorded) == message
    assert taken("fedora", {"terminal": {"ctrl-shift-k": "mine"}}, key, recorded) == message


def test_the_detector_tells_the_vendor_from_the_user_outside_the_terminal_section() -> None:
    taken = herdr_app_keys.herdr_app_taken
    linux = (("terminal", "ctrl-shift-k"), "send:" + chr(12))
    mac = (("terminal", "cmd-k"), "send:" + chr(12))
    message = "herdr-app: partial: you already bind ctrl+shift+k"
    assert taken("fedora", {"global": {"ctrl-shift-k": "mod.open:picker"}}, linux, ()) is None
    assert taken("fedora", {"global": {"shift-ctrl-k": "mod.open:picker"}}, linux, ()) is None
    assert taken("fedora", {"global": {"ctrl-shift-k": "mine"}}, linux, ()) == message
    for section in ("layout:x", "mod:x"):
        assert taken("fedora", {section: {"ctrl-shift-k": "mine"}}, linux, ()) == message
    assert taken("macos", {"global": {"cmd-k": "anything"}}, mac, ()) == (
        "herdr-app: partial: you already bind cmd+k"
    )
    assert taken("fedora", {"global": {"ctrl-shift-k": True}}, linux, ()) == message


def test_the_detector_ignores_what_is_not_a_competing_binding() -> None:
    taken = herdr_app_keys.herdr_app_taken
    key = (("terminal", "ctrl-shift-k"), "send:" + chr(12))
    for document in (
        {"terminal": {"ctrl-shift-k": "send:" + chr(12)}},
        {"terminal": {"ctrl-shift-j": "mine"}},
        {"terminal": {"option-k": "mine"}},
        {"terminal": 3},
        {},
    ):
        assert taken("fedora", document, key, ()) is None
    for platform_os in ("fedora", "macos"):
        document = cast(dict[str, object], json.loads(herdr_app_keys.vendor_default(platform_os)))
        assert (
            taken(platform_os, document, herdr_app_keys.herdr_app_owned_keys(platform_os)[0], ())
            is None
        )
