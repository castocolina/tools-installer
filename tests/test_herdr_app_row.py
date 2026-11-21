import json
import os
from collections.abc import Mapping
from pathlib import Path

import pytest

import installer.app as app
import installer.terminal_keys as terminal_keys
from installer import herdr_app_keys, receipts
from installer.app import UninstallDecision, perform_uninstall
from installer.atomic import FileSnapshot
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.post_install import apply_install_tuning, run_post_install
from installer.resolve import resolve_methods, unavailable_reason
from installer.terminal_keys import KEYS_PENDING, TERMINAL_KEYS, KeysRow, OwnedKeys, Vendor
from installer.uninstall import removal_plan

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"


def test_the_herdr_app_entry_records_its_facts() -> None:
    tool = next(t for t in load_tools(REGISTRY) if t.id == "herdr-app")
    assert (tool.name, tool.category, tool.tier, tool.audience, tool.priority) == (
        "Herdr desktop app",
        "terminal",
        "user",
        "human",
        "P3",
    )
    assert tool.config_paths == ("~/.config/herdr-app",)
    assert tool.post_install == ("apply_terminal_tuning",)
    script, cask = tool.methods
    assert script.kind == "script" and script.os == ("debian", "fedora", "arch")
    assert script.params == {
        "url": "https://releases.herdr.dev/app/install.sh",
        "shell": "sh",
        "bin_dir": "~/.local/bin",
        "paths": [
            "~/.local/share/herdr-app/",
            "~/.local/bin/herdr-app",
            "~/.local/share/applications/herdr-app.desktop",
            "~/.local/share/icons/hicolor/scalable/apps/herdr-app.svg",
        ],
    }
    assert script.params["bin_dir"] == herdr_app_keys.HERDR_APP_BIN_DIR
    assert cask.kind == "cask" and cask.os == ("macos",) and cask.arch == ("arm64",)
    assert cask.params == {"cask": "herdr-app", "app": "Herdr.app"}
    text = REGISTRY.read_text()
    comment = text.split('id = "herdr-app"')[0].rsplit("[[tool]]", 1)[0]
    assert "Verified 2026-11-21" in comment and "herdr-core" in comment


@pytest.mark.parametrize("platform_os", ["fedora", "debian", "arch"])
@pytest.mark.parametrize("arch", ["amd64", "arm64"])
@pytest.mark.parametrize("immutable", [False, True])
def test_herdr_app_resolves_per_platform(platform_os: str, arch: str, immutable: bool) -> None:
    tool = next(t for t in load_tools(REGISTRY) if t.id == "herdr-app")
    linux = Platform(os=platform_os, arch=arch, immutable=immutable, has_brew=False)
    assert resolve_methods(tool, linux) == [tool.methods[0]]
    mac = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")
    intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True, os_version="26.0")
    assert resolve_methods(tool, mac) == [tool.methods[1]]
    assert resolve_methods(tool, intel) == []
    assert unavailable_reason(tool, intel) is not None


def test_the_herdr_app_row_declares_its_ownership_and_directory_rule(tmp_path: Path) -> None:
    row = TERMINAL_KEYS["herdr-app"]
    assert isinstance(row.ownership, OwnedKeys)
    assert row.ownership.seed is herdr_app_keys.herdr_app_seed
    assert row.ownership.pinned is herdr_app_keys.vendor_default
    assert row.ownership.taken is herdr_app_keys.herdr_app_taken
    assert row.ownership.keys(
        "fedora", tmp_path, {"XDG_CONFIG_HOME": "elsewhere"}
    ) == herdr_app_keys.herdr_app_owned_keys("fedora")
    assert row.created_record == "terminal-herdr-app-created" and row.bind_created_path
    assert isinstance(row.same_directory, Vendor)
    assert (
        "2026-11-21" in row.same_directory.note
        and "The installer writes nothing." in row.same_directory.note
    )
    assert row.validate is herdr_app_keys.validate_herdr_app
    assert row.config_path is herdr_app_keys.herdr_app_keys_path


def test_herdr_and_herdr_app_never_collide() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    assert "herdr-app" != "herdr"
    assert "herdr" in receipts.CONFIG_AGENTS and "herdr-app" not in receipts.CONFIG_AGENTS
    assert "herdr" not in TERMINAL_KEYS and "herdr-app" in TERMINAL_KEYS
    assert tools["herdr"].config_paths == ("~/.config/herdr", "~/.local/state/herdr")
    for left in map(Path, tools["herdr"].config_paths):
        for right in map(Path, tools["herdr-app"].config_paths):
            assert left != right and left not in right.parents and right not in left.parents


def test_the_shell_sync_names_neither_new_terminal() -> None:
    root = REGISTRY.parent
    for name in ("terminal_shell.py", "version_status.py"):
        text = (root / name).read_text()
        assert "herdr-app" not in text and "iterm2" not in text


def tool() -> Tool:
    return next(t for t in load_tools(REGISTRY) if t.id == "herdr-app")


def platform(name: str = "fedora") -> Platform:
    return Platform(
        os=name,
        arch="arm64" if name == "macos" else "amd64",
        immutable=False,
        has_brew=name == "macos",
        os_version="26.0" if name == "macos" else None,
    )


def key_path() -> Path:
    return Path.home() / ".config/herdr-app/keys.json"


def records() -> tuple[Path, Path, Path]:
    base = Path.home() / ".local/share/tools-installer"
    marker = base / "terminal-herdr-app-created"
    return base / "terminal-tuning-herdr-app", marker, marker.with_name(marker.name + "-path")


def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def strip(name: str = "fedora") -> tuple[str, ...]:
    return terminal_keys.strip_terminal_keys(
        TERMINAL_KEYS["herdr-app"], "herdr-app", name, Path.home(), os.environ
    )


def pending(name: str = "fedora") -> str | None:
    return terminal_keys.terminal_keys_pending(
        TERMINAL_KEYS["herdr-app"], "herdr-app", name, Path.home(), os.environ
    )


def golden(name: str) -> str:
    chord = "cmd-k" if name == "macos" else "ctrl-shift-k"
    filename = "keys.macos.json" if name == "macos" else "keys.json"
    pinned = (REGISTRY.parent / "vendor_defaults/herdr-app-0.1.16" / filename).read_text()
    return pinned.replace('  "terminal": {', f'  "terminal": {{\n    "{chord}": "send:\\f",', 1)


def remove(name: str = "fedora", config: bool = False) -> app.SweepResult:
    home = Path.home()
    t = tool()
    preview = removal_plan(t, home / ".local/bin", verify=True)
    decision = UninstallDecision(
        tools=(t,),
        paths={t.id: preview.removable},
        argv={t.id: preview.argv},
        remove_path_block=False,
        config={t.id: (home / ".config/herdr-app",)} if config else {},
    )
    return perform_uninstall(
        decision,
        bin_dir=home / ".local/bin",
        myshellrc_path=home / ".myshellrc",
        bundles=(),
        zshrc_path=home / ".zshrc",
        runner=lambda argv: None,
        catalog=(t,),
        extra_policies=(),
        platform_os=name,
    )


def install_artifact() -> Path:
    binary = Path.home() / ".local/bin/herdr-app"
    put(binary, "app")
    receipt = receipts.record(
        tool(), tool().methods[0], package=None, smoke=None, preexisting=frozenset()
    )
    assert receipt is not None
    return binary


@pytest.mark.parametrize("name,chord", [("fedora", "ctrl-shift-k"), ("macos", "cmd-k")])
def test_the_herdr_app_keys_golden_on_linux_and_macos(name: str, chord: str) -> None:
    result = run_post_install(tool(), platform(name))
    assert result.warning is None and result.lines[0] == TERMINAL_KEYS["herdr-app"].summary
    assert ("picker" if name == "fedora" else "cmd+k") in result.lines[1]
    assert "add new vendor defaults by hand" in result.lines[2]
    path = key_path()
    assert path.read_text() == golden(name)
    assert json.loads(path.read_text())["terminal"][chord] == "send:" + chr(12)
    record, marker, sidecar = records()
    assert json.loads(record.read_text()) == {
        "deleted": [],
        "keys": [["terminal", chord, "send:" + chr(12)]],
        "path": str(path),
    }
    assert marker.exists() and sidecar.read_text() == f"{path}\n"
    assert pending(name) is None


@pytest.mark.parametrize(
    "section,chord",
    [
        ("terminal", "Ctrl-Shift-K"),
        ("terminal", "shift-ctrl-k"),
        ("terminal", "ctrl-shift-k x"),
        ("global", "ctrl-shift-k"),
    ],
)
def test_a_user_binding_is_kept_with_a_partial_line(section: str, chord: str) -> None:
    text = herdr_app_keys.vendor_default("fedora").replace(
        f'  "{section}": {{', f'  "{section}": {{\n    "{chord}": "mine",', 1
    )
    if section == "global":
        text = text.replace('    "ctrl-shift-k": "mod.open:picker",\n', "")
    put(key_path(), text)
    result = run_post_install(tool(), platform())
    assert result.lines == ("herdr-app: partial: you already bind ctrl+shift+k",)
    assert key_path().read_text() == text and pending() is None
    assert json.loads(records()[0].read_text())["keys"] == []


def test_the_vendor_picker_binding_is_displaced_not_kept() -> None:
    text = herdr_app_keys.vendor_default("fedora")
    assert json.loads(text)["global"]["ctrl-shift-k"] == "mod.open:picker"
    put(key_path(), text)
    result = run_post_install(tool(), platform())
    assert "picker" in result.lines[1]
    assert key_path().read_text() == golden("fedora")


@pytest.mark.parametrize("text", ["", "  \n", "{not json", "[1]"])
def test_a_blank_or_missing_keys_file_is_seeded_and_an_unparseable_one_is_refused(
    text: str,
) -> None:
    put(key_path(), text)
    result = run_post_install(tool(), platform())
    if not text.strip():
        assert key_path().read_text() == golden("fedora") and not records()[1].exists()
    else:
        reason = (
            "the file does not parse; left as it is"
            if text == "{not json"
            else "the keys file must hold objects only"
        )
        assert result.lines[0].startswith("Herdr desktop app keys not changed: " + reason)
        assert key_path().read_text() == text and not records()[0].exists()


def test_user_keys_beside_the_owned_key_survive_apply_and_strip_in_any_order() -> None:
    text = (
        '{\n  "layout:mine": {"z": "1"},\n  "terminal": {\n'
        '    "second": "2",\n    "first": "1"\n  },\n  "global": {}\n}\n'
    )
    put(key_path(), text)
    run_post_install(tool(), platform())
    assert strip() == () and key_path().read_text() == text


def test_reconfigure_deleted_key_changed_value_and_reinstall() -> None:
    run_post_install(tool(), platform())
    path = key_path()
    original = path.read_text()
    for flag in (True, False):
        apply_install_tuning(tool(), platform(), skip_recorded=flag)
        assert path.read_text() == original
    line = '    "ctrl-shift-k": "send:\\f",\n'
    path.write_text(original.replace(line, ""))
    assert pending() is None
    for _ in range(2):
        apply_install_tuning(tool(), platform(), skip_recorded=True)
        assert path.read_text() == original.replace(line, "")
        assert json.loads(records()[0].read_text())["deleted"] == [["terminal", "ctrl-shift-k"]]
    apply_install_tuning(tool(), platform(), skip_recorded=False)
    assert path.read_text() == original
    path.write_text(original.replace('"send:\\f"', '"mine"', 1))
    assert pending() is None
    assert apply_install_tuning(tool(), platform(), skip_recorded=True).lines == (
        "herdr-app: partial: you already bind ctrl+shift+k",
    )
    assert strip() == () and json.loads(path.read_text())["terminal"]["ctrl-shift-k"] == "mine"


def test_a_drifted_recorded_value_reads_pending_and_reconfigure_rewrites_it() -> None:
    run_post_install(tool(), platform())
    path = key_path()
    current = path.read_text()
    old = current.replace('"send:\\f"', '"old"', 1)
    path.write_text(old)
    record = records()[0]
    put(
        record,
        json.dumps(
            {"deleted": [], "keys": [["terminal", "ctrl-shift-k", "old"]], "path": str(path)}
        ),
    )
    assert pending() == KEYS_PENDING
    apply_install_tuning(tool(), platform(), skip_recorded=True)
    assert path.read_text() == current and json.loads(record.read_text())["keys"][0][
        2
    ] == "send:" + chr(12)
    apply_install_tuning(tool(), platform(), skip_recorded=True)
    assert path.read_text() == current
    path.write_text(old.replace('"old"', '"third"'))
    apply_install_tuning(tool(), platform(), skip_recorded=True)
    assert '"third"' in path.read_text()
    record.unlink()
    path.write_text(old)
    assert run_post_install(tool(), platform()).lines == (
        "herdr-app: partial: you already bind ctrl+shift+k",
    )
    assert path.read_text() == old


@pytest.mark.parametrize("name", ["fedora", "macos"])
def test_strip_deletes_a_created_file_equal_to_the_vendor_default_and_keeps_an_edited_one(
    name: str,
) -> None:
    run_post_install(tool(), platform(name))
    assert strip(name) == () and not key_path().parent.exists()
    assert not any(p.exists() for p in records())
    run_post_install(tool(), platform(name))
    path = key_path()
    path.write_text(
        path.read_text().replace('  "terminal": {', '  "terminal": {\n    "mine": "x",', 1)
    )
    assert strip(name) == () and json.loads(path.read_text())["terminal"]["mine"] == "x"
    path.write_text(herdr_app_keys.vendor_default(name))
    run_post_install(tool(), platform(name))
    assert strip(name) == () and path.read_text() == herdr_app_keys.vendor_default(name)


def test_the_created_file_is_bound_to_its_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setenv("HERDR_APP_HOME", str(a))
    run_post_install(tool(), platform())
    monkeypatch.setenv("HERDR_APP_HOME", str(b))
    assert strip() == (
        f"herdr-app: edited keys were recorded for {a / 'keys.json'}, "
        "not the file now resolved; left alone",
    )
    assert all(p.exists() for p in records()) and (a / "keys.json").exists()
    monkeypatch.setenv("HERDR_APP_HOME", str(a))
    assert strip() == () and not (a / "keys.json").exists()
    monkeypatch.delenv("HERDR_APP_HOME")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(b))
    run_post_install(tool(), platform())
    assert (b / "herdr-app/keys.json").exists()


def test_a_created_marker_for_another_file_never_authorizes_deleting_this_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    monkeypatch.setenv("HERDR_APP_HOME", str(a))
    run_post_install(tool(), platform())
    first = (a / "keys.json").read_bytes()
    monkeypatch.setenv("HERDR_APP_HOME", str(b))
    put(b / "keys.json", herdr_app_keys.vendor_default("fedora"))
    apply_install_tuning(tool(), platform(), skip_recorded=True)
    before = (b / "keys.json").read_bytes()
    assert strip() == (
        f"herdr-app: created config at {a / 'keys.json'} is not the file now resolved; left alone",
    )
    assert (b / "keys.json").read_bytes() == before and (a / "keys.json").read_bytes() == first
    assert all(p.exists() for p in records())


def test_the_herdr_multiplexers_files_are_never_touched() -> None:
    paths = (Path.home() / ".config/herdr/config.toml", Path.home() / ".local/bin/herdr")
    for p in paths:
        put(p, "sentinel")
    run_post_install(tool(), platform())
    apply_install_tuning(tool(), platform(), skip_recorded=True)
    assert strip() == () and all(p.read_text() == "sentinel" for p in paths)


def test_the_herdr_app_apply_refuses_a_file_that_changed_after_the_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    put(key_path(), herdr_app_keys.vendor_default("fedora"))
    original = terminal_keys.read_settings

    def racing(path: Path) -> FileSnapshot | None:
        snapshot = original(path)
        path.write_text("other writer")
        return snapshot

    monkeypatch.setattr(terminal_keys, "read_settings", racing)
    assert run_post_install(tool(), platform()).lines == (
        "Herdr desktop app keys not changed: changed while being written",
    )
    assert key_path().read_text() == "other writer"


@pytest.mark.parametrize("version", [None, "0.1.17"])
def test_a_version_difference_fails_closed_through_the_row(
    monkeypatch: pytest.MonkeyPatch, version: str | None
) -> None:
    def installed_version(platform_os: str) -> str | None:
        del platform_os
        return version

    monkeypatch.setattr(herdr_app_keys, "herdr_app_version", installed_version)
    result = run_post_install(tool(), platform())
    assert len(result.lines) == 1 and result.lines[0].startswith(
        "Herdr desktop app keys not changed: partial:"
    )
    assert (version or "unknown") in result.lines[0] and "0.1.16" in result.lines[0]
    assert (
        not key_path().parent.exists()
        and not any(p.exists() for p in records())
        and pending() == KEYS_PENDING
    )
    text = herdr_app_keys.vendor_default("fedora")
    put(key_path(), text)
    run_post_install(tool(), platform())
    assert key_path().read_text() == golden("fedora")


@pytest.mark.parametrize("name", ["fedora", "macos"])
@pytest.mark.parametrize("edited", [False, True])
def test_the_real_removal_route_deletes_a_created_keys_file_after_the_executable_is_gone(
    name: str, edited: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = install_artifact()

    def installed_version(platform_os: str) -> str | None:
        del platform_os
        return "0.1.16" if binary.exists() else None

    monkeypatch.setattr(herdr_app_keys, "herdr_app_version", installed_version)
    run_post_install(tool(), platform(name))
    if edited:
        put(
            key_path(),
            key_path()
            .read_text()
            .replace('  "terminal": {', '  "terminal": {\n    "mine": "x",', 1),
        )
    result = remove(name)
    assert not binary.exists() and not any(p.exists() for p in records())
    assert not any("version" in warning for warning in result.warnings)
    if edited:
        assert json.loads(key_path().read_text())["terminal"]["mine"] == "x"
    else:
        assert not key_path().parent.exists()


def test_custom_xdg_data_home_partial_receipt_removes_only_recorded_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "relocated"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    binary = data / "herdr-app/app"
    icon = data / "icons/hicolor/scalable/apps/herdr-app.svg"
    desktop = data / "applications/herdr-app.desktop"
    for path in (binary, icon, desktop):
        put(path, "vendor")
    sentinel = Path.home() / ".config/herdr/config.toml"
    put(sentinel, "herdr")
    link = Path.home() / ".local/bin/herdr-app"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(binary)
    receipt = receipts.record(
        tool(), tool().methods[0], package=None, smoke=None, preexisting=frozenset()
    )
    assert receipt is not None and tuple(a.path for a in receipt.artifacts) == (link,)
    assert removal_plan(tool(), link.parent, verify=True).removable == (link,)
    remove()
    assert not link.exists() and all(p.read_text() == "vendor" for p in (binary, icon, desktop))
    assert sentinel.read_text() == "herdr"


@pytest.mark.parametrize("delete", [False, True])
def test_the_apps_config_folder_is_kept_by_default_and_deleted_only_by_choice(
    delete: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_artifact()
    sentinel = Path.home() / ".config/herdr/config.toml"
    put(sentinel, "herdr")
    run_post_install(tool(), platform())
    put(
        key_path(),
        key_path().read_text().replace('  "terminal": {', '  "terminal": {\n    "mine": "x",', 1),
    )
    sibling = key_path().parent / "other.txt"
    put(sibling, "user")
    original = app.strip_terminal_keys
    seen: list[bool] = []

    def observing(
        row: KeysRow, tool_id: str, platform_os: str, home: Path, environ: Mapping[str, str]
    ) -> tuple[str, ...]:
        seen.append(
            key_path().exists() and "ctrl-shift-k" in json.loads(key_path().read_text())["terminal"]
        )
        return original(row, tool_id, platform_os, home, environ)

    monkeypatch.setattr(app, "strip_terminal_keys", observing)
    remove(config=delete)
    assert seen == [True] and sentinel.read_text() == "herdr"
    if delete:
        assert not key_path().parent.exists()
    else:
        assert (
            sibling.read_text() == "user"
            and json.loads(key_path().read_text())["terminal"]["mine"] == "x"
        )
        assert "ctrl-shift-k" not in json.loads(key_path().read_text())["terminal"]


@pytest.mark.parametrize("reconfigure", [False, True])
def test_a_changed_keys_folder_never_inherits_the_old_ledger_on_the_real_row(
    reconfigure: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = key_path()
    put(a, herdr_app_keys.vendor_default("fedora"))
    run_post_install(tool(), platform())
    old = a.read_bytes()
    b = tmp_path / "other/keys.json"
    put(b, golden("fedora"))
    saved = b.read_bytes()
    monkeypatch.setenv("HERDR_APP_HOME", str(b.parent))
    if reconfigure:
        for flag in (True, False):
            apply_install_tuning(tool(), platform(), skip_recorded=flag)
            assert b.read_bytes() == saved and a.read_bytes() == old
        assert json.loads(records()[0].read_text())["path"] == str(b)
    else:
        assert strip() == (
            f"herdr-app: edited keys were recorded for {a}, not the file now resolved; left alone",
        )
        assert b.read_bytes() == saved and a.read_bytes() == old and records()[0].exists()
        monkeypatch.delenv("HERDR_APP_HOME")
        assert strip() == () and a.read_text() == herdr_app_keys.vendor_default("fedora")
