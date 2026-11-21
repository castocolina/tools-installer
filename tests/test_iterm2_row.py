"""iTerm2 registry, ownership, lifecycle, and removal integration."""

import inspect
import io
import os
import plistlib
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from rich.console import Console

from installer import app, receipts
from installer import iterm2_profile as profile
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.post_install import apply_install_tuning, run_post_install
from installer.resolve import resolve_methods
from installer.run import CommandError
from installer.terminal_keys import (
    KEYS_PENDING,
    TERMINAL_KEYS,
    DefaultProfile,
    WholeFile,
    Writes,
    strip_terminal_keys,
    terminal_keys_pending,
    variant_plan,
)
from installer.uninstall import removal_plan
from tests.test_registry import REGISTRY

GUID = "AAAAAAAA-0000-4000-8000-000000000001"
OTHER = "BBBBBBBB-0000-4000-8000-000000000002"
MAC = Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0")


class FakeDefaults:
    def __init__(self, previous: str | None = None) -> None:
        self.prefs = {} if previous is None else {profile.DEFAULT_GUID_KEY: previous}
        self.calls: list[tuple[str, ...]] = []
        self.fail_read = False
        self.fail_write = False

    def __call__(self, argv: Sequence[str]) -> str:
        self.calls.append(("defaults", *argv))
        if argv[0] == "read":
            if self.fail_read:
                raise CommandError(list(argv), 127, detail="injected")
            if argv[2] not in self.prefs:
                raise CommandError(list(argv), 1, detail="does not exist")
            return self.prefs[argv[2]]
        if argv[0] == "write":
            if self.fail_write:
                raise CommandError(list(argv), 1, detail="injected write failure")
            self.prefs[argv[2]] = argv[4]
            return ""
        if argv[0] == "delete":
            self.prefs.pop(argv[2], None)
            return ""
        if argv[0] == "export":
            return plistlib.dumps({"New Bookmarks": [{"Guid": GUID, "Keyboard Map": {}}]}).decode()
        raise AssertionError(argv)


def tool() -> Tool:
    return next(t for t in load_tools(REGISTRY) if t.id == "iterm2")


def fake_defaults(monkeypatch: pytest.MonkeyPatch, previous: str | None = None) -> FakeDefaults:
    fake = FakeDefaults(previous)
    monkeypatch.setattr(profile, "iterm2_defaults", fake)
    return fake


def pending() -> str | None:
    return terminal_keys_pending(
        TERMINAL_KEYS["iterm2"], "iterm2", "macos", Path.home(), os.environ
    )


def test_the_iterm2_entry_records_its_facts() -> None:
    t = tool()
    assert (t.name, t.category, t.tier, t.audience, t.priority, t.cmd) == (
        "iTerm2",
        "terminal",
        "user",
        "human",
        "P3",
        "iterm2",
    )
    assert t.post_install == ("apply_terminal_tuning",) and not t.config_paths
    assert len(t.methods) == 1
    m = t.methods[0]
    assert (m.kind, m.os) == ("cask", ("macos",))
    assert m.params["cask"] == "iterm2" and m.params["app"] == "iTerm.app"
    assert m.params["min_os_version"] == "13"
    assert "Verified 2026-11-21" in REGISTRY.read_text().split('id = "iterm2"')[0][-1200:]


def test_iterm2_resolves_only_on_macos_13_or_later() -> None:
    t = tool()
    for arch in ("arm64", "amd64"):
        assert resolve_methods(
            t, Platform(os="macos", arch=arch, immutable=False, has_brew=True, os_version="26.0")
        ) == list(t.methods)
    assert not resolve_methods(
        t, Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="12.0")
    )
    for system in ("debian", "fedora", "arch"):
        for immutable in (False, True):
            assert not resolve_methods(
                t, Platform(os=system, arch="amd64", immutable=immutable, has_brew=True)
            )


def test_the_iterm2_row_declares_its_ownership_and_directory_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = TERMINAL_KEYS["iterm2"]
    own = row.ownership
    assert isinstance(own, WholeFile) and own.proof is profile.iterm2_proof
    hook = own.hook
    assert isinstance(hook, DefaultProfile)
    assert (
        hook.before_write,
        hook.after_write,
        hook.restore,
        hook.still_named,
        hook.switch_pending,
    ) == (
        profile.hook_before_write,
        profile.hook_after_write,
        profile.hook_restore,
        profile.hook_still_named,
        profile.hook_switch_pending,
    )
    assert row.created_record == "terminal-iterm2-created" and isinstance(
        row.same_directory, Writes
    )
    assert row.plan is variant_plan and row.validate is profile.validate_iterm2
    assert row.config_path("anything", tmp_path, {}) == profile.profile_path(tmp_path)
    rows, _ = profile.merge_rows({})
    state = profile.ProfileState(GUID, GUID, True, True, rows)
    env = {"XDG_DATA_HOME": str(tmp_path / "data")}
    profile.write_state(tmp_path, env, state)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "other")
    assert own.plan(
        "macos", "", profile.profile_path(tmp_path), tmp_path, env
    ).body == profile.iterm2_profile_text(state, recycle=True)


def test_a_fresh_iterm2_install_writes_the_golden_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = fake_defaults(monkeypatch)
    result = run_post_install(tool(), MAC)
    assert result.warning is None and result.lines[0] == TERMINAL_KEYS["iterm2"].summary
    assert result.lines[1:] == (
        "iterm2: cmd+k now sends Ctrl+L instead of the Clear Buffer menu item.",
        "iterm2: changes made in the iTerm2 settings window do not stick (a Dynamic Profile).",
        "iterm2: iTerm2 skips a Dynamic Profiles file it cannot parse and reports it.",
        "iterm2: iTerm2 quits when it is removed; uninstall it from another terminal "
        "so the profile file is deleted with it.",
    )
    rows, _ = profile.merge_rows({})
    assert profile.profile_path(Path.home()).read_text() == profile.iterm2_profile_text(
        profile.ProfileState(None, None, True, True, rows), recycle=True
    )
    assert pending() is None and fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID


def test_a_foreign_iterm2_profile_is_refused_and_left_byte_for_byte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_defaults(monkeypatch)
    path = profile.profile_path(Path.home())
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{"foreign": true}\n')
    result = run_post_install(tool(), MAC)
    reason = "tools-installer.json is not the installer's; left as it is"
    assert result.lines == (f"iTerm2 keys not changed: {reason}",)
    assert path.read_bytes() == b'{"foreign": true}\n' and not fake.calls
    assert pending() == reason


def test_a_drifted_or_deleted_iterm2_profile_reads_pending_and_reconfigure_restores_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_defaults(monkeypatch)
    run_post_install(tool(), MAC)
    path = profile.profile_path(Path.home())
    golden = path.read_bytes()
    path.write_text(path.read_text().replace('"Name": "tools-installer"', '"Name": "changed"'))
    assert pending() == KEYS_PENDING
    apply_install_tuning(tool(), MAC, skip_recorded=True)
    assert path.read_bytes() == golden and pending() is None
    path.unlink()
    assert pending() == KEYS_PENDING
    apply_install_tuning(tool(), MAC, skip_recorded=True)
    assert path.read_bytes() == golden
    path.unlink()
    fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    assert pending() is None
    apply_install_tuning(tool(), MAC, skip_recorded=True)
    assert not path.exists()


def test_an_iterm2_reconfigure_and_a_reinstall_change_no_byte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_defaults(monkeypatch)
    run_post_install(tool(), MAC)
    path = profile.profile_path(Path.home())
    golden = path.read_bytes()
    apply_install_tuning(tool(), MAC, skip_recorded=True)
    run_post_install(tool(), MAC)
    assert path.read_bytes() == golden
    assert sum(c[1] == "write" for c in fake.calls) == 1


def listing(names: set[str]) -> Callable[[str], frozenset[str]]:
    def list_names(kind: str) -> frozenset[str]:
        del kind
        return frozenset(names)

    return list_names


def setup_removal(
    monkeypatch: pytest.MonkeyPatch, previous: str | None = GUID
) -> tuple[FakeDefaults, Tool]:
    fake = fake_defaults(monkeypatch, previous)
    t = tool()
    receipts.record(t, t.methods[0], package="iterm2", smoke=None)
    monkeypatch.setattr(app, "manager_listing", listing({"iterm2"}))
    run_post_install(t, MAC)
    return fake, t


def remove(t: Tool, calls: list[tuple[str, ...]], *, fail: bool = False) -> app.ToolRemoval:
    bin_dir = Path.home() / ".local/bin"
    plan = removal_plan(t, bin_dir)

    def runner(argv: list[str]) -> None:
        calls.append(("runner", *argv))
        if fail:
            raise CommandError(argv, 1, detail="injected")

    return app.remove_tool(t, paths=plan.removable, argv=plan.argv, bin_dir=bin_dir, runner=runner)


@pytest.mark.parametrize("previous", [GUID, None])
def test_remove_tool_restores_the_default_before_the_cask_runs(
    monkeypatch: pytest.MonkeyPatch, previous: str | None
) -> None:
    fake, t = setup_removal(monkeypatch, previous)
    if previous:
        assert (
            '"Dynamic Profile Parent GUID": "' + previous + '"'
            in profile.profile_path(Path.home()).read_text()
        )
    fake.calls.clear()
    outcome = remove(t, fake.calls)
    command = (
        ("defaults", "write", profile.ITERM2_DOMAIN, profile.DEFAULT_GUID_KEY, "-string", previous)
        if previous
        else ("defaults", "delete", profile.ITERM2_DOMAIN, profile.DEFAULT_GUID_KEY)
    )
    assert fake.calls.index(command) < fake.calls.index(
        ("runner", "brew", "uninstall", "--cask", "iterm2")
    )
    assert outcome.removed and fake.prefs.get(profile.DEFAULT_GUID_KEY) == previous
    assert (
        profile.profile_path(Path.home()).exists()
        and profile.read_state(Path.home(), os.environ) is not None
    )
    count = len([c for c in fake.calls if c[1] in ("write", "delete")])
    strip_terminal_keys(TERMINAL_KEYS["iterm2"], "iterm2", "macos", Path.home(), os.environ)
    assert len([c for c in fake.calls if c[1] in ("write", "delete")]) == count
    assert fake.prefs.get(profile.DEFAULT_GUID_KEY) == previous
    assert (
        not profile.profile_path(Path.home()).exists()
        and profile.read_state(Path.home(), os.environ) is None
    )
    assert not (Path.home() / ".local/share/tools-installer/terminal-tuning-iterm2").exists()
    assert not (Path.home() / ".local/share/tools-installer/terminal-iterm2-created").exists()


@pytest.mark.parametrize("failure", ["custom", "read"])
def test_an_unconfirmed_restore_refuses_the_removal(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    fake, t = setup_removal(monkeypatch)
    if failure == "custom":
        fake.prefs[profile.CUSTOM_FOLDER_KEY] = "1"
    else:
        fake.fail_read = True
    fake.calls.clear()
    outcome = remove(t, fake.calls)
    assert not outcome.removed and "was not removed" in outcome.detail
    assert ("custom folder" if failure == "custom" else "could not read") in outcome.detail
    assert not any(c[0] == "runner" for c in fake.calls)
    assert receipts.read("iterm2") is not None and profile.profile_path(Path.home()).exists()
    assert profile.read_state(Path.home(), os.environ) is not None
    assert (Path.home() / ".local/share/tools-installer/terminal-tuning-iterm2").exists()
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID
    fake.fail_read = False
    fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    assert remove(t, fake.calls).removed


def test_the_hook_lines_reach_every_post_hook_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, t = setup_removal(monkeypatch)
    fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    monkeypatch.setattr(app, "manager_listing", listing(set()))
    outcome = remove(t, fake.calls)
    line = "iterm2: partial: you changed your default profile after the install; kept yours"
    assert outcome.removed and outcome.detail == f"already removed {line}"
    receipts.record(t, t.methods[0], package="iterm2", smoke=None)
    monkeypatch.setattr(app, "manager_listing", listing({"iterm2"}))
    outcome = remove(t, fake.calls, fail=True)
    assert not outcome.removed and "injected" in outcome.detail and line in outcome.detail
    source = inspect.getsource(app.remove_tool)
    assert source.count("_remove_tool_steps(") == 1 and source.count("dataclasses.replace(") == 1


def test_remove_tool_leaves_every_other_tool_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = fake_defaults(monkeypatch)
    t = next(t for t in load_tools(REGISTRY) if t.id == "vscode")
    method = next(m for m in t.methods if m.kind == "cask")
    receipts.record(t, method, package="visual-studio-code", smoke=None)
    monkeypatch.setattr(app, "manager_listing", listing({"visual-studio-code"}))
    calls: list[tuple[str, ...]] = []
    outcome = remove(t, calls)
    assert outcome.removed and not outcome.detail and not fake.calls


def test_app_names_no_iterm2_and_calls_the_generic_hook() -> None:
    text = inspect.getsource(app)
    assert "iterm2" not in text.lower() and text.count("before_removal_terminal_keys(") == 1
    assert "before_removal_terminal_keys(" in text.split("def _remove_tool_steps(", 1)[1]


def strip() -> tuple[str, ...]:
    return strip_terminal_keys(TERMINAL_KEYS["iterm2"], "iterm2", "macos", Path.home(), os.environ)


def records() -> tuple[Path, ...]:
    data = Path.home() / ".local/share/tools-installer"
    return (
        data / "terminal-tuning-iterm2",
        data / profile.ITERM2_CREATED,
        data / profile.STATE_RECORD,
    )


def prepare_home() -> set[Path]:
    # Receipt and tuning infrastructure keeps its shared directories after deletion.
    (Path.home() / ".local/share/tools-installer/receipts").mkdir(parents=True, exist_ok=True)
    return set(Path.home().rglob("*"))


def route(
    t: Tool,
    calls: list[tuple[str, ...]],
    *,
    cli: bool = False,
    fail: bool = False,
    config: tuple[Path, ...] = (),
) -> tuple[tuple[str, ...], str, tuple[str, ...]]:
    home = Path.home()
    plan = removal_plan(t, home / ".local/bin")

    def runner(argv: list[str]) -> None:
        calls.append(("runner", *argv))
        if fail:
            raise CommandError(argv, 1, detail="injected")

    if cli:
        output = io.StringIO()
        console = Console(file=output, width=300, force_terminal=False)
        _, failed = app.run_uninstall(
            [t],
            console,
            default_bin_dir=home / ".local/bin",
            myshellrc_path=home / ".myshellrc",
            confirm=lambda _: True,
            bundles=(),
            zshrc_path=home / ".zshrc",
            extra_policies=(),
            runner=runner,
            platform_os="macos",
        )
        return failed, output.getvalue(), ()
    decision = app.UninstallDecision(
        tools=(t,),
        paths={t.id: plan.removable},
        argv={t.id: plan.argv},
        remove_path_block=False,
        config={t.id: config},
    )
    result = app.perform_uninstall(
        decision,
        bin_dir=home / ".local/bin",
        myshellrc_path=home / ".myshellrc",
        bundles=(),
        zshrc_path=home / ".zshrc",
        extra_policies=(),
        runner=runner,
        catalog=(t,),
        platform_os="macos",
    )
    return (
        tuple(item[0] for item in result.remove_failed),
        " ".join(x[1] for x in result.remove_failed),
        result.warnings,
    )


def assert_clean(start: set[Path]) -> None:
    assert not profile.profile_path(Path.home()).exists()
    assert not any(path.exists() for path in records())
    assert set(Path.home().rglob("*")) == start


@pytest.mark.parametrize("previous", [GUID, None])
def test_the_iterm2_lifecycle_restores_the_default_and_leaves_no_trace(
    monkeypatch: pytest.MonkeyPatch,
    previous: str | None,
) -> None:
    start = prepare_home()
    fake = fake_defaults(monkeypatch, previous)
    before = dict(fake.prefs)
    run_post_install(tool(), MAC)
    assert strip() == ()
    assert fake.prefs == before
    assert_clean(start)
    assert strip() == ()
    assert fake.prefs == before
    assert_clean(start)


def test_strip_keeps_a_profile_file_that_is_not_the_installers_and_a_user_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = fake_defaults(monkeypatch, GUID)
    path = profile.profile_path(Path.home())
    path.parent.mkdir(parents=True)
    path.write_bytes(b"foreign")
    assert "not the installer's" in " ".join(strip())
    assert path.read_bytes() == b"foreign"
    path.unlink()
    run_post_install(tool(), MAC)
    fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    assert (
        "iterm2: partial: you changed your default profile after the install; kept yours" in strip()
    )
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == OTHER and not path.exists()


def test_perform_uninstall_restores_the_default_and_deletes_the_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = prepare_home()
    fake, t = setup_removal(monkeypatch)
    fake.calls.clear()
    failed, _, _ = route(t, fake.calls)
    assert not failed
    writes = [x for x in fake.calls if x[1] == "write"]
    assert writes == [
        ("defaults", "write", profile.ITERM2_DOMAIN, profile.DEFAULT_GUID_KEY, "-string", GUID)
    ]
    assert fake.calls.index(writes[0]) < fake.calls.index(
        ("runner", "brew", "uninstall", "--cask", "iterm2")
    )
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == GUID
    assert_clean(start)


def test_a_failed_strip_restore_keeps_the_profile_and_the_records_until_a_later_strip_confirms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = prepare_home()
    fake = fake_defaults(monkeypatch, GUID)
    run_post_install(tool(), MAC)
    fake.fail_write = True
    warnings = " ".join(strip())
    assert "could not restore your default profile" in warnings
    assert "kept because the default profile was not restored" in warnings
    assert profile.profile_path(Path.home()).exists() and all(p.exists() for p in records())
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID
    fake.fail_write = False
    assert strip() == ()
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == GUID
    assert_clean(start)


@pytest.mark.parametrize("cli", [False, True])
def test_an_unconfirmed_restore_blocks_the_uninstall_until_the_user_fixes_it_and_the_retry_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    cli: bool,
) -> None:
    start = prepare_home()
    fake, t = setup_removal(monkeypatch)
    fake.prefs[profile.CUSTOM_FOLDER_KEY] = "1"
    fake.calls.clear()
    failed, detail, _ = route(t, fake.calls, cli=cli)
    assert failed == ("iterm2",) and "was not removed" in detail
    if cli:
        assert "iterm2: remove failed" in detail
    assert not any(c[0] == "runner" for c in fake.calls)
    assert receipts.read("iterm2") is not None and all(p.exists() for p in records())
    assert (
        profile.profile_path(Path.home()).exists()
        and fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID
    )
    fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    failed, _, _ = route(t, fake.calls, cli=cli)
    assert not failed and fake.calls.count(("runner", "brew", "uninstall", "--cask", "iterm2")) == 1
    assert receipts.read("iterm2") is None and fake.prefs[profile.DEFAULT_GUID_KEY] == OTHER
    assert_clean(start)


@pytest.mark.parametrize(
    ("cli", "corrupt", "choose_first"),
    [(False, False, False), (False, True, False), (True, False, False), (False, False, True)],
)
def test_a_lost_state_record_refuses_the_uninstall_through_the_public_route(
    monkeypatch: pytest.MonkeyPatch,
    cli: bool,
    corrupt: bool,
    choose_first: bool,
) -> None:
    start = prepare_home()
    fake, t = setup_removal(monkeypatch)
    state = profile.state_record(Path.home(), os.environ)
    if corrupt:
        state.write_text("garbage")
    else:
        state.unlink()
    if choose_first:
        fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    fake.calls.clear()
    failed, detail, _ = route(t, fake.calls, cli=cli)
    if not choose_first:
        assert failed == ("iterm2",) and "was not removed" in detail
        assert (
            "iterm2: partial: your default profile is still tools-installer and your previous "
            "default could not be recovered; choose a default profile in iTerm2 > Settings > "
            "Profiles, then uninstall again"
        ) in detail
        assert not any(c[0] == "runner" for c in fake.calls)
        assert receipts.read("iterm2") is not None and profile.profile_path(Path.home()).exists()
        assert records()[0].exists() and fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID
        fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
        failed, _, _ = route(t, fake.calls, cli=cli)
    assert not failed and fake.calls.count(("runner", "brew", "uninstall", "--cask", "iterm2")) == 1
    assert receipts.read("iterm2") is None and fake.prefs[profile.DEFAULT_GUID_KEY] == OTHER
    assert_clean(start)


@pytest.mark.parametrize("user_changed", [False, True])
def test_a_failed_cask_command_leaves_a_retryable_switch(
    monkeypatch: pytest.MonkeyPatch,
    user_changed: bool,
) -> None:
    start = prepare_home()
    fake, t = setup_removal(monkeypatch)
    failed, _, _ = route(t, fake.calls, fail=True)
    assert failed == ("iterm2",) and fake.prefs[profile.DEFAULT_GUID_KEY] == GUID
    state = profile.read_state(Path.home(), os.environ)
    assert state is not None and not state.switched
    assert profile.profile_path(Path.home()).exists() and pending() == KEYS_PENDING
    if user_changed:
        fake.prefs[profile.DEFAULT_GUID_KEY] = OTHER
    fake.calls.clear()
    result = apply_install_tuning(t, MAC, skip_recorded=True)
    if user_changed:
        assert not any(c[1] == "write" for c in fake.calls)
        assert any("kept yours" in line for line in result.lines) and pending() is None
    else:
        assert fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID
        state = profile.read_state(Path.home(), os.environ)
        assert state is not None and state.switched
        assert (
            "iterm2: your default profile is now tools-installer (retried after an earlier failure)"
            in result.lines
        )
    assert not route(t, fake.calls)[0]
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == (OTHER if user_changed else GUID)
    assert_clean(start)


@pytest.mark.parametrize("second_failure", [False, True])
def test_a_failed_record_update_refuses_the_removal_and_both_retries_recover(
    monkeypatch: pytest.MonkeyPatch,
    second_failure: bool,
) -> None:
    start = prepare_home()
    fake, t = setup_removal(monkeypatch)
    original = profile.write_state

    def fail_state(home: Path, environ: object, state: object) -> None:
        del home, environ, state
        raise OSError("disk")

    monkeypatch.setattr(profile, "write_state", fail_state)
    fake.calls.clear()
    failed, detail, _ = route(t, fake.calls)
    assert (
        failed == ("iterm2",)
        and "could not update your record" in detail
        and "was not removed" in detail
    )
    assert not any(c[0] == "runner" for c in fake.calls)
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == GUID and receipts.read("iterm2") is not None
    assert profile.profile_path(Path.home()).exists() and all(p.exists() for p in records())
    state = profile.read_state(Path.home(), os.environ)
    assert state is not None and state.switched
    monkeypatch.setattr(profile, "write_state", original)
    fake.calls.clear()
    assert pending() is None
    apply_install_tuning(t, MAC, skip_recorded=True)
    assert not any(c[1] == "write" for c in fake.calls)
    if second_failure:
        assert route(t, fake.calls, fail=True)[0] == ("iterm2",)
        assert fake.prefs[profile.DEFAULT_GUID_KEY] == GUID and pending() is None
        fake.calls.clear()
        apply_install_tuning(t, MAC, skip_recorded=True)
        assert not any(c[1] == "write" for c in fake.calls)
        apply_install_tuning(t, MAC, skip_recorded=False)
        state = profile.read_state(Path.home(), os.environ)
        assert (
            state is not None
            and state.switched
            and fake.prefs[profile.DEFAULT_GUID_KEY] == profile.ITERM2_GUID
        )
    fake.calls.clear()
    assert not route(t, fake.calls)[0]
    if not second_failure:
        assert any(c[1] == "read" for c in fake.calls if c[0] == "defaults")
        assert not any(c[1] == "write" for c in fake.calls)
    assert fake.prefs[profile.DEFAULT_GUID_KEY] == GUID
    assert_clean(start)


def test_a_config_choice_never_deletes_the_iterm2_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, t = setup_removal(monkeypatch)
    folder = Path.home() / "Library/Application Support/iTerm2"
    other = folder / "DynamicProfiles/other.json"
    other.write_bytes(b"user profile")
    failed, _, warnings = route(t, fake.calls, config=(folder,))
    assert not failed and f"config {folder} is not declared by any tool; not deleted" in warnings
    assert folder.is_dir() and other.read_bytes() == b"user profile"
    assert not profile.profile_path(Path.home()).exists() and not any(p.exists() for p in records())
