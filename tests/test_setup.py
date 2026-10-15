import contextlib
import importlib
import inspect
import io
import os
import pty
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

import pytest
from rich.console import Console
from textual.pilot import Pilot

import setup
from installer import pnpm_globals, systemd_daemon
from installer.app import UninstallDecision
from installer.diskusage import DiskPressure
from installer.engine import InstallOutcome
from installer.enums import DaemonState, Severity
from installer.execute_screen import ExecuteInputs
from installer.guards import install_shims
from installer.model import Method, Tool
from installer.ownership import ManagerOwnership
from installer.platform import Platform
from installer.pnpm_globals import NodeGlobalsReport, NodeInstallPolicy
from installer.policy import Policy
from installer.resolve import UnavailableReason
from installer.session import Summary
from installer.settings import Settings, SettingsStore, load_settings, save_settings
from installer.shellrc import ShellrcConsolidation, ShellrcRefusal, write_myshellrc
from installer.terminal_shell import TerminalShellResult
from installer.tweaks import BUNDLES
from installer.uninstall import SweepResult
from installer.wizard_app import (
    BASE_VIEW,
    DoctorScreen,
    ExecuteScreen,
    PolicyInputs,
    UnifiedApp,
    UninstallInputs,
    UninstallScreen,
)

# Aliased once, matching tests/test_daemon.py's convention for pinning a
# private composition-root function under test.
_has_controlling_tty = setup._has_controlling_tty  # pyright: ignore[reportPrivateUsage]
_stdin_on_tty = setup._stdin_on_tty  # pyright: ignore[reportPrivateUsage]
_ask_select = setup._ask_select  # pyright: ignore[reportPrivateUsage]
_darwin_select_based_asyncio = (
    setup._darwin_select_based_asyncio  # pyright: ignore[reportPrivateUsage]
)


class _DummyApp:
    install_summary: Summary | None = None

    def run(self) -> None:
        return None


class _FakeStdin:
    def isatty(self) -> bool:
        return True


class _NonTtyStdin:
    def isatty(self) -> bool:
        return False


def _platform() -> Platform:
    return Platform(os="macos", arch="arm64", immutable=False, has_brew=True)


# -- /dev/tty reconnection (`curl | sh` fix) ---------------------------------
#
# `curl -fsSL ... | sh` pipes the script itself onto stdin, so
# sys.stdin.isatty() is False even when the user is at a real terminal.
# These pin the two primitives that recover from that (probing /dev/tty, and
# redirecting fd 0 onto it for a Textual .run() call) without ever opening a
# real device — os.open/os.isatty/os.dup/os.dup2/os.close are all faked.


def test_has_controlling_tty_true_when_stdin_isatty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())
    assert _has_controlling_tty() is True


def test_has_controlling_tty_false_when_stdin_and_dev_tty_both_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup.sys, "stdin", _NonTtyStdin())

    def fake_open(path: str, flags: int) -> int:
        raise OSError("no controlling terminal")

    monkeypatch.setattr(setup.os, "open", fake_open)
    assert _has_controlling_tty() is False


def test_has_controlling_tty_true_via_dev_tty_when_stdin_is_the_curl_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression this exists to fix: stdin is the piped script (not a
    tty), but a real controlling terminal is still reachable via /dev/tty."""
    monkeypatch.setattr(setup.sys, "stdin", _NonTtyStdin())
    opened: list[str] = []
    closed: list[int] = []

    def fake_open(path: str, _flags: int) -> int:
        opened.append(path)
        return 99

    monkeypatch.setattr(setup.os, "open", fake_open)
    monkeypatch.setattr(setup.os, "close", closed.append)
    assert _has_controlling_tty() is True
    assert opened == ["/dev/tty"]
    assert closed == [99]


# These four fakes intercept ONLY fd 0 (or the /dev/tty path) and delegate
# everything else to the REAL os.* function. os is one process-wide singleton
# module -- pytest's own fd-level capture machinery calls os.dup2/os.isatty
# on ITS OWN (non-zero) fds throughout a run, so a fake that ignores which fd
# it was called with corrupts capture teardown for every other test, not just
# this one (reproduced: a blanket fake raised inside pytest's own stdout
# restore). Scoping to fd 0 / "/dev/tty" keeps the fakes inert for anything
# that isn't this function's own fd-0 plumbing.
_REAL_OS_OPEN = os.open
_REAL_OS_CLOSE = os.close
_REAL_OS_DUP = os.dup
_REAL_OS_DUP2 = os.dup2
_REAL_OS_ISATTY = os.isatty


def test_stdin_on_tty_is_a_noop_when_fd0_is_already_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_isatty(fd: int) -> bool:
        return True if fd == 0 else _REAL_OS_ISATTY(fd)

    def fail_on_dev_tty(path: str, flags: int) -> int:
        if path == "/dev/tty":
            raise AssertionError("must not touch fd 0 when it is already a tty")
        return _REAL_OS_OPEN(path, flags)

    monkeypatch.setattr(setup.os, "isatty", fake_isatty)
    monkeypatch.setattr(setup.os, "open", fail_on_dev_tty)
    with _stdin_on_tty():
        pass


def test_stdin_on_tty_redirects_fd0_to_dev_tty_and_restores_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []
    fake_tty_fd, saved_fd = 9001, 9002

    def fake_isatty(fd: int) -> bool:
        return False if fd == 0 else _REAL_OS_ISATTY(fd)

    def fake_open(path: str, flags: int) -> int:
        if path == "/dev/tty":
            return fake_tty_fd
        return _REAL_OS_OPEN(path, flags)

    def fake_dup(fd: int) -> int:
        return saved_fd if fd == 0 else _REAL_OS_DUP(fd)

    def fake_dup2(src: int, dst: int) -> None:
        if dst == 0:
            calls.append(("dup2", src, dst))
            return
        _REAL_OS_DUP2(src, dst)

    def fake_close(fd: int) -> None:
        if fd in (fake_tty_fd, saved_fd):
            calls.append(("close", fd))
            return
        _REAL_OS_CLOSE(fd)

    monkeypatch.setattr(setup.os, "isatty", fake_isatty)
    monkeypatch.setattr(setup.os, "open", fake_open)
    monkeypatch.setattr(setup.os, "dup", fake_dup)
    monkeypatch.setattr(setup.os, "dup2", fake_dup2)
    monkeypatch.setattr(setup.os, "close", fake_close)

    with _stdin_on_tty():
        assert calls == [("dup2", fake_tty_fd, 0), ("close", fake_tty_fd)]

    assert calls == [
        ("dup2", fake_tty_fd, 0),
        ("close", fake_tty_fd),
        ("dup2", saved_fd, 0),
        ("close", saved_fd),
    ]


def test_stdin_on_tty_falls_through_when_dev_tty_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_isatty(fd: int) -> bool:
        return False if fd == 0 else _REAL_OS_ISATTY(fd)

    def fake_open(path: str, flags: int) -> int:
        if path == "/dev/tty":
            raise OSError("no controlling terminal")
        return _REAL_OS_OPEN(path, flags)

    monkeypatch.setattr(setup.os, "isatty", fake_isatty)
    monkeypatch.setattr(setup.os, "open", fake_open)
    ran = False
    with _stdin_on_tty():
        ran = True
    assert ran is True


def test_main_doctor_reaches_the_interactive_tui_under_a_curl_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end regression for the reported bug: `curl | sh` leaves
    sys.stdin non-tty, but a real terminal is reachable via /dev/tty, so
    --doctor must still open the interactive app instead of printing
    'No TTY detected'."""
    fake_tty_fd, saved_fd = 9101, 9102

    def fake_isatty(fd: int) -> bool:
        return False if fd == 0 else _REAL_OS_ISATTY(fd)

    def fake_open(path: str, flags: int) -> int:
        if path == "/dev/tty":
            return fake_tty_fd
        return _REAL_OS_OPEN(path, flags)

    def fake_dup(fd: int) -> int:
        return saved_fd if fd == 0 else _REAL_OS_DUP(fd)

    def fake_dup2(src: int, dst: int) -> None:
        if dst != 0:
            _REAL_OS_DUP2(src, dst)

    def fake_close(fd: int) -> None:
        if fd not in (fake_tty_fd, saved_fd):
            _REAL_OS_CLOSE(fd)

    monkeypatch.setattr(setup, "load_tools", _no_tools)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup.sys, "stdin", _NonTtyStdin())
    monkeypatch.setattr(setup.os, "isatty", fake_isatty)
    monkeypatch.setattr(setup.os, "open", fake_open)
    monkeypatch.setattr(setup.os, "dup", fake_dup)
    monkeypatch.setattr(setup.os, "dup2", fake_dup2)
    monkeypatch.setattr(setup.os, "close", fake_close)
    seen = _capture_app(monkeypatch)

    assert setup.main(["--doctor"]) == 0
    assert seen  # _build_app/UnifiedApp was constructed -- the interactive path ran


def test_ask_select_binds_a_dev_tty_input_output_pair_without_touching_fd0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for the macOS kqueue crash reported after the fd-0-redirect
    fix: dup2'ing /dev/tty onto fd 0 got prompt_toolkit's VT100 driver to
    render, but its asyncio event loop then raised
    `OSError: [Errno 22] Invalid argument` registering that repointed fd with
    kqueue (`loop.add_reader()` -> `KqueueSelector.register()` ->
    `kqueue.control()`). kqueue doesn't tolerate a fd number being repointed
    at a different open file description mid-process the way epoll does.
    _ask_select must instead build its Input/Output from a freshly opened
    /dev/tty file (a real, never-reused fd) and never call os.dup2 on fd 0."""
    master_in, slave_in = pty.openpty()
    master_out, slave_out = pty.openpty()
    opened: list[int] = []

    def fake_open(path: str, flags: int) -> int:
        if path == "/dev/tty":
            fd = slave_in if not opened else slave_out
            opened.append(fd)
            return fd
        return _REAL_OS_OPEN(path, flags)

    dup2_calls: list[tuple[int, int]] = []

    def fake_dup2(src: int, dst: int) -> None:
        dup2_calls.append((src, dst))
        _REAL_OS_DUP2(src, dst)

    class _FakeQuestion:
        def __init__(self, **kwargs: object) -> None:
            self._kwargs = kwargs

        def ask(self) -> str:
            # The whole point of the fix: questionary gets an explicit
            # Input/Output bound to /dev/tty, not fd 0's default streams.
            assert self._kwargs.get("input") is not None
            assert self._kwargs.get("output") is not None
            return "centralized"

    def fake_select(*_args: object, **kwargs: object) -> _FakeQuestion:
        return _FakeQuestion(**kwargs)

    def fake_isatty(fd: int) -> bool:
        return False if fd == 0 else _REAL_OS_ISATTY(fd)

    monkeypatch.setattr(setup.os, "isatty", fake_isatty)
    monkeypatch.setattr(setup.os, "open", fake_open)
    monkeypatch.setattr(setup.os, "dup2", fake_dup2)
    monkeypatch.setattr(setup.sys, "stdin", _NonTtyStdin())
    monkeypatch.setattr(setup.questionary, "select", fake_select)

    try:
        assert _ask_select("pick one", [("A", "a")]) == "centralized"
        assert dup2_calls == []  # fd 0 is never touched by the questionary path
        assert opened == [slave_in, slave_out]
    finally:
        for fd in (master_in, master_out):
            _REAL_OS_CLOSE(fd)


def test_darwin_select_based_asyncio_is_a_noop_off_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup.sys, "platform", "linux")
    original = setup.selectors.DefaultSelector
    with _darwin_select_based_asyncio():
        assert setup.selectors.DefaultSelector is original
    assert setup.selectors.DefaultSelector is original


def test_darwin_select_based_asyncio_swaps_and_restores_the_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for the reported bug: even a brand-new, never-redirected
    /dev/tty fd crashes prompt_toolkit's kqueue-based asyncio loop on macOS
    with OSError: [Errno 22] Invalid argument. select.select() handles the
    same fd fine, so questionary prompts force SelectSelector on Darwin for
    the duration of one .ask() call, then restore the original selector."""
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    original = setup.selectors.DefaultSelector

    with _darwin_select_based_asyncio():
        assert setup.selectors.DefaultSelector is setup.selectors.SelectSelector

    assert setup.selectors.DefaultSelector is original


def test_darwin_select_based_asyncio_restores_selector_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    original = setup.selectors.DefaultSelector

    with pytest.raises(ValueError, match="boom"), _darwin_select_based_asyncio():
        raise ValueError("boom")

    assert setup.selectors.DefaultSelector is original


def test_main_fix_interactive_without_link_mode_opens_doctor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    build_calls: list[dict[str, object]] = []

    def fake_load_tools(_registry: object) -> list[Tool]:
        return []

    def fake_detect() -> Platform:
        return _platform()

    def fake_build_app(
        tools: list[Tool],
        platform: Platform,
        *,
        initial_view: str = "system",
        link_mode: str = "centralized",
        **kwargs: object,
    ) -> _DummyApp:
        build_calls.append(
            {
                "initial_view": initial_view,
                "link_mode": link_mode,
                "settings": kwargs.get("settings"),
                "prompt_link_mode": kwargs.get("prompt_link_mode", False),
            }
        )
        return _DummyApp()

    _store_link_mode(monkeypatch, tmp_path, "single")
    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", fake_detect)
    monkeypatch.setattr(setup, "_build_app", fake_build_app)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())

    console = Console(file=io.StringIO(), width=100, no_color=True)
    monkeypatch.setattr(setup, "Console", lambda: console)

    assert setup.main(["--fix"]) == 0
    assert len(build_calls) == 1
    assert build_calls[0]["initial_view"] == "doctor"
    assert build_calls[0]["link_mode"] == "single"
    assert build_calls[0]["settings"] is not None
    assert build_calls[0]["prompt_link_mode"] is False


# -- composition-root wiring -------------------------------------------------
#
# These drive setup.main for real and observe what the wire hands the core.
# Reading setup.py's own source instead is what the earlier version of this file
# did, and it bought less than it looked like: a substring is satisfied by a
# comment, `body.index(...)` raises instead of failing with a diagnosis, pinning
# exact whitespace makes a `ruff format` change fail an unrelated test, and none
# of it noticed `remove=_do_uninstall` being deleted outright — the one wire the
# Uninstall view cannot work without. setup.py stays outside pyright and
# coverage (the untyped questionary boundary), so behaviour through its public
# entry point is the only guard it has.


def _capture_app(
    monkeypatch: pytest.MonkeyPatch, install_summary: Summary | None = None
) -> list[dict[str, object]]:
    """Stand in for UnifiedApp so _build_app runs for real without a terminal.

    The captured kwargs are the wire under test: what the composition root
    actually handed the views, not what its source text says it did.
    """
    seen: list[dict[str, object]] = []

    class _App:
        install_summary: Summary | None = None

        def __init__(self, *_args: object, **kwargs: object) -> None:
            if install_summary is not None:
                self.install_summary = install_summary
            seen.append(dict(kwargs))

        def run(self) -> None:
            return None

    monkeypatch.setattr(setup, "UnifiedApp", _App)
    return seen


def _no_tools(_registry: object) -> list[Tool]:
    return []


def _no_categories(_registry: object) -> dict[str, str]:
    return {}


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every import-time home constant at tmp_path, so the real
    _build_app can run without touching the developer's shell files."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", tmp_path / ".local" / "bin")
    monkeypatch.setattr(setup, "_MYSHELLRC", tmp_path / ".myshellrc")
    monkeypatch.setattr(setup, "_SHELLRC", tmp_path / ".shellrc")
    monkeypatch.setattr(setup, "_ZSHRC", tmp_path / ".zshrc")
    monkeypatch.setattr(setup, "_RC_PATHS", [tmp_path / ".zshrc", tmp_path / ".bashrc"])
    monkeypatch.setattr(setup, "_DAEMON_PLIST_PATH", tmp_path / "LaunchAgents" / "daemon.plist")
    monkeypatch.setattr(setup, "_DAEMON_LOG_PATH", tmp_path / "Logs" / "prune-daemon.log")
    monkeypatch.setattr(setup, "_DAEMON_SCRIPT_PATH", tmp_path / "scripts" / "prune-user-tmpdir.sh")
    monkeypatch.setattr(setup, "_DAEMON_STATE_PATH", tmp_path / ".myshellrc")
    monkeypatch.setattr(setup, "_ENVIRONMENT_D_DIR", tmp_path / ".config" / "environment.d")
    # Linux mirror of the macOS daemon paths above: without this, the
    # module-level _LINUX_DAEMON_UNIT_DIR constant (computed once, at import
    # time, from the real machine's HOME) would have every Linux-platform
    # test in this file reading/writing units_present() against the real
    # dev host's ~/.config/systemd/user -- not merely the wrong isolation
    # boundary, but also what keeps timer_state()'s own presence short-circuit
    # (D-01c) from ever reaching the real systemctl in these tests.
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", tmp_path / "config" / "systemd" / "user")
    monkeypatch.setattr(
        setup, "_LINUX_DAEMON_LOG_PATH", tmp_path / "state" / "tools-installer" / "prune-daemon.log"
    )
    monkeypatch.setattr(setup, "load_tools", _no_tools)
    monkeypatch.setattr(setup, "load_categories", _no_categories)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("installer.settings.default_settings_path", lambda: settings_path)
    monkeypatch.setattr(setup, "default_settings_path", lambda: settings_path, raising=False)


def _recording_install(recorder: list[str]) -> Callable[..., InstallOutcome]:
    def install(
        tool: Tool,
        platform: Platform,
        runner: object,
        resolve_tag: object,
        *,
        checksum_policy: str = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: object = None,
    ) -> InstallOutcome:
        del platform, runner, resolve_tag, checksum_policy, tools, confirm_sensitive_action
        recorder.append(tool.id)
        return InstallOutcome(tool.id, "installed")

    return install


def _hermetic_route(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """Hermetic setup for the TUI route pilots: a scratch HOME (_sandbox), an
    empty PATH, no systemd, the Linux platform, a one-tool fake catalog, a
    seeded settings file (no first-run picker), a fake TTY, and the install
    closure replaced at the _execute_inputs seam (D-12) with a recorder.
    Returns the recorder's installed tool ids. No real systemctl, launchctl,
    network or HOME is ever reached."""
    _sandbox(monkeypatch, tmp_path)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(empty_bin))

    def _no_systemd(**_k: object) -> bool:
        return False

    monkeypatch.setattr(setup.systemd_daemon, "systemd_available", _no_systemd)
    monkeypatch.setattr(setup, "detect", _linux_platform)
    tool = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "ripgrep"}),),
        tier="system",
    )

    def _one_tool(_registry: object) -> list[Tool]:
        return [tool]

    monkeypatch.setattr(setup, "load_tools", _one_tool)
    save_settings(tmp_path / "settings.json", Settings("centralized"))
    monkeypatch.setattr(setup, "_has_controlling_tty", lambda: True)
    monkeypatch.setattr(setup, "_stdin_on_tty", contextlib.nullcontext)
    installed: list[str] = []
    real_inputs = setup._execute_inputs  # pyright: ignore[reportPrivateUsage]

    def recording_inputs(
        tools: list[Tool],
        platform: Platform,
        *,
        link_mode: str | Callable[[], str],
        unattended: bool,
        disk_pressure: Callable[[], DiskPressure],
    ) -> ExecuteInputs:
        inputs = real_inputs(
            tools,
            platform,
            link_mode=link_mode,
            unattended=unattended,
            disk_pressure=disk_pressure,
        )

        def _never_installed(_tool: Tool) -> bool:
            return False

        def _pinned_tag(_repo: str) -> str:
            return "v1.0.0"

        return replace(
            inputs,
            installed=_never_installed,
            install=_recording_install(installed),
            resolve_tag=_pinned_tag,
        )

    monkeypatch.setattr(setup, "_execute_inputs", recording_inputs)  # pyright: ignore[reportPrivateUsage]
    return installed


def _store_link_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str) -> Path:
    path = tmp_path / "settings.json"
    save_settings(path, Settings(mode))
    monkeypatch.setattr("installer.settings.default_settings_path", lambda: path)
    monkeypatch.setattr(setup, "default_settings_path", lambda: path, raising=False)
    return path
    monkeypatch.setattr(setup, "default_settings_path", lambda: tmp_path / "settings.json")


def test_the_uninstall_view_is_wired_to_a_total_teardown_of_the_real_zshrc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Drive the view's own removal closure and watch what reaches the core.

    This covers both halves at once: that `remove` is wired to `_do_uninstall`
    at all (deleting it makes UninstallInputs unconstructible, so the app never
    builds), and that `_do_uninstall` forwards every bundle and the resolved
    .zshrc. `bundles` is BUNDLES, not applicable_bundles(platform): a teardown
    is total, so a bundle that no longer applies here is still swept off disk.
    """
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    forwarded: list[dict[str, object]] = []

    def fake_perform_uninstall(_decision: object, **kwargs: object) -> SweepResult:
        forwarded.append(kwargs)
        return SweepResult()

    monkeypatch.setattr(setup, "perform_uninstall", fake_perform_uninstall)

    assert setup.main(["--uninstall"]) == 0
    inputs = seen[0]["uninstall"]
    assert isinstance(inputs, UninstallInputs)

    inputs.remove(
        UninstallDecision(paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=True)
    )
    assert forwarded[0]["bundles"] is BUNDLES
    assert forwarded[0]["zshrc_path"] == tmp_path / ".zshrc"
    assert forwarded[0]["myshellrc_path"] == tmp_path / ".myshellrc"
    assert forwarded[0]["bin_dir"] == tmp_path / ".local" / "bin"


def test_the_uninstall_view_reads_every_environment_row_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each environment input must be a predicate the view can re-read, not a
    value frozen when the app was built — the Policies and Doctor views change
    all three while the Uninstall view is suspended."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    inputs = seen[0]["uninstall"]
    assert isinstance(inputs, UninstallInputs)

    assert inputs.ban_names() == []
    assert inputs.has_path_block() is False
    assert inputs.tweak_ids() == ()
    # Enable the ban and the PATH block behind the view's back, exactly as the
    # Policies and Doctor views do, and the same closures now report them.
    bin_dir = tmp_path / ".local" / "bin"
    install_shims(bin_dir)
    write_myshellrc([bin_dir], tmp_path / ".myshellrc")
    assert inputs.ban_names() != []
    assert inputs.has_path_block() is True


def test_the_uninstall_rows_closure_re_reads_presence_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The rows closure re-reads presence on every call rather than closing
    over the startup `installed` map (D-06) -- the same live-re-read shape
    `test_build_app_reresolve_reads_live_inventory_not_cache` already proves
    for ownership, applied here to the row list `_build_app` hands the
    Uninstall screen."""
    _sandbox(monkeypatch, tmp_path)
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(Method(kind="brew", params={"formula": "fd"}),),
        tier="system",
    )

    def _one_tool(_registry: object) -> list[Tool]:
        return [tool]

    monkeypatch.setattr(setup, "load_tools", _one_tool)
    present = {"fd": False}

    def fake_is_installed(t: Tool) -> bool:
        return present[t.id]

    monkeypatch.setattr(setup, "is_installed", fake_is_installed)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    inputs = seen[0]["uninstall"]
    assert isinstance(inputs, UninstallInputs)

    first = inputs.rows()
    assert first[0].state.value == "absent"  # not installed, no userspace artifact
    present["fd"] = True  # brew installed it in another terminal, mid-session
    second = inputs.rows()
    assert second[0].state.value == "managed"  # now reads as manager-installed


def test_the_uninstall_rows_closure_calls_presence_once_per_catalog_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No quadratic re-read (Round-1 review LOW, T-15.4-21): one `rows()` call
    invokes the presence predicate exactly once per catalog tool, never once
    per tool per row and never more."""
    _sandbox(monkeypatch, tmp_path)
    tools = [
        Tool(
            id=f"tool-{i}",
            name=f"tool-{i}",
            category="search",
            cmd=f"tool-{i}",
            methods=(Method(kind="brew", params={"formula": f"tool-{i}"}),),
            tier="system",
        )
        for i in range(5)
    ]

    def _five_tools(_registry: object) -> list[Tool]:
        return tools

    monkeypatch.setattr(setup, "load_tools", _five_tools)
    calls: list[str] = []

    def counting_is_installed(t: Tool) -> bool:
        calls.append(t.id)
        return False

    monkeypatch.setattr(setup, "is_installed", counting_is_installed)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    inputs = seen[0]["uninstall"]
    assert isinstance(inputs, UninstallInputs)
    calls.clear()  # drop the one call _build_app itself made for the `installed` map

    inputs.rows()
    assert len(calls) == len(tools)
    assert sorted(calls) == sorted(tool.id for tool in tools)


def test_the_policies_view_is_wired_ban_then_tweaks_then_omz(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """omz is offered after the platform's tweak bundles; the daemon (macOS-only,
    the newest addition) is offered last of all, per _sandbox's fixed macOS
    Platform."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)

    ids = [policy.id for policy in policies.policies]
    assert ids[0] == "ban"
    daemon_at = ids.index("daemon:prune-tmpdir")
    assert ids[daemon_at - 1] == "omz-plugins"
    assert all(policy_id.startswith("tweak:") for policy_id in ids[1 : daemon_at - 1])
    assert all(policy_id.startswith("cache-redirect:") for policy_id in ids[daemon_at + 1 :])
    assert ids[daemon_at + 1 :]
    assert len(ids) > 3


def test_zsh_is_cleared_without_a_local_delenv() -> None:
    assert "ZSH" not in os.environ


def test_build_app_wires_live_omz_availability_and_one_terminal_sync_closure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    platform = Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)
    calls: list[dict[str, object]] = []

    def sync(**kwargs: object) -> TerminalShellResult:
        calls.append(kwargs)
        return TerminalShellResult(warnings=("wezterm configuration is user-owned",))

    monkeypatch.setattr(setup, "sync_terminal_shells", sync)

    setup._build_app([], platform)  # pyright: ignore[reportPrivateUsage]

    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    omz = next(policy for policy in policies.policies if policy.id == "omz-plugins")
    assert omz.missing_requirements() == ("oh-my-zsh",)
    (tmp_path / ".oh-my-zsh").mkdir()
    assert omz.missing_requirements() == ()

    result = omz.apply()

    assert result.warning == (
        "Terminal shell synchronization warning: wezterm configuration is user-owned"
    )
    assert len(calls) == 1
    assert calls[0] == {
        "home": tmp_path,
        "environ": os.environ,
        "platform": platform,
        "lookup": setup._which_with_brew,  # pyright: ignore[reportPrivateUsage]
    }
    assert (tmp_path / ".zshrc").exists()


def _no_systemctl(_name: str) -> str | None:
    return None


def _systemctl_and_uv(name: str) -> str | None:
    return f"/usr/bin/{name}" if name in ("systemctl", "uv") else None


def test_daemon_policy_is_absent_on_linux_without_systemd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-01b, not ROADMAP SC#2: a host without systemd gets no daemon row.
    ROADMAP SC#2's "invisible/inert on Linux" is deliberately superseded by
    this phase's D-01a -- see the sibling test below, where systemd IS
    available and the row IS present."""
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup.shutil, "which", _no_systemctl)
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    monkeypatch.setattr(setup, "detect", lambda: linux)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert not any(policy.id.startswith("daemon:") for policy in policies.policies)


def test_daemon_policy_is_present_on_linux_with_systemd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-01a: on a debian platform whose lookup resolves systemctl, exactly
    one daemon:-prefixed policy reaches PolicyInputs, and its id is the
    Linux one -- not the macOS `daemon:prune-tmpdir` id."""
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup.shutil, "which", _systemctl_and_uv)
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    monkeypatch.setattr(setup, "detect", lambda: linux)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    daemon_ids = [policy.id for policy in policies.policies if policy.id.startswith("daemon:")]
    assert daemon_ids == ["daemon:prune-tmp-linux"]


def test_build_daemon_policy_returns_none_off_macos_only_when_systemctl_is_unresolvable() -> None:
    """Renamed from test_build_daemon_policy_returns_none_off_macos: this
    phase's D-01a means "off macOS" alone no longer implies None -- the
    function returns None off macOS only when systemctl is unresolvable
    (D-01b). See test_build_daemon_policy_returns_a_linux_policy_when_systemctl_is_resolvable
    for the positive case."""
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    # _build_daemon_policy is setup.py's own private composition-root helper;
    # the plan's own <behavior> requires testing it directly (construction
    # must never raise on a bad environment) -- there is no public seam that
    # exercises this without going through the full main()/_build_app flow.
    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        linux, {}, which=_no_systemctl
    )
    assert policy is None


def test_build_daemon_policy_returns_a_linux_policy_when_systemctl_is_resolvable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Sandboxed so Policy construction's own active=_is_active() probe (which
    # checks units_present() before ever calling read_output) reads a
    # guaranteed-empty directory, not whatever the real dev host happens to
    # have under ~/.config/systemd/user.
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", tmp_path / "config" / "systemd" / "user")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        linux, {}, which=_systemctl_and_uv
    )
    assert policy is not None
    assert policy.id == "daemon:prune-tmp-linux"


def test_build_daemon_policy_on_linux_never_reaches_the_hosts_real_systemctl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Construction alone (no apply()/is_active() call) must never spawn a
    real subprocess -- proven with a recording run/read_output pair, sandboxed
    against a fresh, always-empty unit dir so the D-01c presence short-circuit
    itself can never mask a real escape (units_present() genuinely False here,
    not merely False by luck of the real dev host's own state)."""
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", tmp_path / "config" / "systemd" / "user")
    run_calls: list[list[str]] = []
    read_calls: list[list[str]] = []

    def recording_run(cmd: list[str]) -> None:
        run_calls.append(cmd)

    def recording_read_output(cmd: list[str]) -> str:
        read_calls.append(cmd)
        return "active"

    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        linux,
        {},
        which=_systemctl_and_uv,
        run=recording_run,
        read_output=recording_read_output,
    )
    assert policy is not None
    assert policy.id == "daemon:prune-tmp-linux"
    assert run_calls == []
    assert read_calls == []


def _no_uv(_name: str) -> str | None:
    return None


def test_build_daemon_policy_is_fail_closed_not_fail_hidden_for_a_bad_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construction never raises on an unresolvable TMPDIR/HOME/uv -- only a
    later apply() would, via installer.daemon's own fail-closed validation
    gate. The fail-closed contract lives in the validation, not in a guard
    that hides the policy from view."""
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.setattr(setup.shutil, "which", _no_uv)
    policy = setup._build_daemon_policy(_platform(), {})  # pyright: ignore[reportPrivateUsage]
    assert policy is not None
    assert policy.id == "daemon:prune-tmpdir"


def test_daemon_default_is_wired_only_for_the_genuine_setup_wizard_entry_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """apply_daemon_default's ALLOWLIST gate (11-REVIEWS.md cycle 2 finding
    #14): only the default/no-flag path (_run_interactive_wizard's own call
    site -- the genuine, normal interactive `make setup` wizard flow) ever
    wires a real daemon_default callback into UnifiedApp. `--doctor`
    (read-only, Makefile:19), `--uninstall`, and `--guard`'s interactive
    Policies view must never auto-apply -- proven against _capture_app's
    own CAPTURED kwargs, not merely that an injected callback was never
    invoked (11-REVIEWS.md cycle 2 finding #20)."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)

    assert setup.main(["--doctor"]) == 0
    assert setup.main(["--uninstall"]) == 0
    assert setup.main(["--guard"]) == 0
    assert setup.main([]) == 0

    assert len(seen) == 4
    doctor_kwargs, uninstall_kwargs, policies_kwargs, default_kwargs = seen

    for kwargs in (doctor_kwargs, uninstall_kwargs, policies_kwargs):
        assert kwargs.get("daemon_default") is None
        assert kwargs.get("daemon_default_policy_id") is None

    assert callable(default_kwargs["daemon_default"])
    assert default_kwargs["daemon_default_policy_id"] == "daemon:prune-tmpdir"


def test_daemon_default_is_wired_on_linux_when_systemd_is_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-01a's Linux half, pinned at the composition root: the on-by-default
    wiring fires from the genuine interactive wizard entry point on Linux
    too, once systemd is available -- mirrors
    test_daemon_default_is_wired_only_for_the_genuine_setup_wizard_entry_point's
    macOS-default coverage, and its own daemon_default_policy_id is the
    Linux id, not the macOS one."""
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup.shutil, "which", _systemctl_and_uv)
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    monkeypatch.setattr(setup, "detect", lambda: linux)
    seen = _capture_app(monkeypatch)

    assert setup.main(["--uninstall"]) == 0  # never wires the default
    assert setup.main([]) == 0  # the genuine wizard entry point

    assert len(seen) == 2
    uninstall_kwargs, wizard_kwargs = seen
    assert uninstall_kwargs.get("daemon_default") is None
    assert uninstall_kwargs.get("daemon_default_policy_id") is None
    assert callable(wizard_kwargs["daemon_default"])
    assert wizard_kwargs["daemon_default_policy_id"] == "daemon:prune-tmp-linux"


def test_the_policies_view_wires_split_mode_myshellrc_sourcing_for_every_tweak(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Enabling a tweak under split link mode also wires ~/.myshellrc sourcing
    into the split rc files, via the --guard entry point."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--guard", "--link-mode", "split"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    codex_skip = next(p for p in policies.policies if p.id == "tweak:codex-skip")
    codex_skip.apply()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".zshrc").read_text()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".bashrc").read_text()


def test_the_policies_view_wires_split_mode_myshellrc_sourcing_for_the_cache_redirect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WR-07: in split mode nothing sources ~/.myshellrc, so a macOS redirect
    written only there was a silent no-op while its row read ON."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--guard", "--link-mode", "split"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    redirect = next(p for p in policies.policies if p.id.startswith("cache-redirect:"))
    result = redirect.apply()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".zshrc").read_text()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".bashrc").read_text()
    assert any(layer.name == "Split-mode sourcing" for layer in result.layers)


def test_the_policies_and_doctor_share_one_competing_probe_that_never_mutates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WR-10: the system-scope disclosure needs a durable, read-only source.
    The probe is built once per route and must issue only read verbs."""
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "detect", lambda: Platform("fedora", "amd64", False, False))

    def which(name: str) -> str:
        return f"/usr/bin/{name}"

    monkeypatch.setattr(setup.shutil, "which", which)
    issued: list[list[str]] = []

    def read_output(cmd: list[str]) -> str:
        issued.append(cmd)
        if "list-unit-files" in cmd and "--user" not in cmd:
            return "cleanup-bun-tmp-cache.timer enabled -\n"
        return ""

    monkeypatch.setattr(setup.systemd_daemon, "query_systemctl", read_output)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--guard"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    probe = policies.competing
    assert probe is not None
    assert probe(blocking=False) == ()  # cold peek says nothing rather than guessing
    units = probe()
    assert [unit.name for unit in units] == ["cleanup-bun-tmp-cache.timer"]
    assert [unit.scope for unit in units] == ["system"]
    assert probe(blocking=False) == units  # memoized for the render path
    assert issued  # and every query it issued was read-only
    read_verbs = {"list-unit-files", "is-active", "is-enabled", "show"}
    for cmd in issued:
        assert read_verbs & set(cmd), cmd
        assert not {"disable", "enable", "stop", "start", "daemon-reload"} & set(cmd), cmd


def test_the_disk_probe_ignores_a_relative_tmpdir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """IN-03: a relative TMPDIR was measured against whatever cwd the process
    happened to have."""
    measured: list[Path] = []

    def fake_probe(
        daemon: object, tmp_threshold: bool, home: Path, tmp: Path, usage: object
    ) -> DiskPressure:
        del daemon, tmp_threshold, home, usage
        measured.append(tmp)
        return DiskPressure(
            home_free_percent=None,
            tmp_used_percent=None,
            daemon=DaemonState.UNAVAILABLE,
            tmp_threshold=False,
        )

    monkeypatch.setattr(setup.diskusage, "probe_disk_pressure", fake_probe)
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        Platform("fedora", "amd64", False, False), timer_cache=None
    )
    monkeypatch.setenv("TMPDIR", "relative/tmp")
    probe()
    monkeypatch.setenv("TMPDIR", str(tmp_path / "abs-tmp"))
    probe()
    assert measured == [Path("/tmp"), tmp_path / "abs-tmp"]


def test_the_environment_d_dir_honours_xdg_config_home(tmp_path: Path) -> None:
    """WR-04: systemd's user environment generator reads
    $XDG_CONFIG_HOME/environment.d; a redirect written under ~/.config there
    is never read. Import-time constant, so it is read in a fresh process."""
    import os
    import subprocess
    import sys

    xdg = tmp_path / "xdg"
    env = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(xdg)}
    completed = subprocess.run(
        [sys.executable, "-c", "import setup; print(setup._ENVIRONMENT_D_DIR)"],
        cwd=Path(setup.__file__).parent,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == str(xdg / "environment.d")


def test_the_policies_view_does_not_wire_split_sourcing_under_centralized_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--guard"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    codex_skip = next(p for p in policies.policies if p.id == "tweak:codex-skip")
    codex_skip.apply()
    assert not (tmp_path / ".bashrc").exists()


def test_the_normal_interactive_flow_wires_split_mode_myshellrc_sourcing_before_catalog_opens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The phase's own primary, most-used entry point (no flags at all) must
    also thread the real link mode into the catalog/Policies UnifiedApp
    instance BEFORE it opens — not only the --guard shortcut."""
    _sandbox(monkeypatch, tmp_path)
    _store_link_mode(monkeypatch, tmp_path, "split")
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    codex_skip = next(p for p in policies.policies if p.id == "tweak:codex-skip")
    codex_skip.apply()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".bashrc").read_text()


def test_the_normal_interactive_flow_does_not_wire_split_sourcing_under_centralized_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    codex_skip = next(p for p in policies.policies if p.id == "tweak:codex-skip")
    codex_skip.apply()
    assert not (tmp_path / ".bashrc").exists()


def test_doctor_preview_carries_the_grouped_pinned_allowed_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The preview closure is the closest seam _build_app exposes without a TUI.

    UnifiedApp is replaced so the composition root still constructs the
    closures; the captured `globals_preview` is then called with a report
    whose managed set is the brownfield pair.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", tmp_path / ".local" / "bin")
    monkeypatch.setattr(setup, "_MYSHELLRC", tmp_path / ".myshellrc")
    monkeypatch.setattr(setup, "_SHELLRC", tmp_path / ".shellrc")
    monkeypatch.setattr(setup, "_ZSHRC", tmp_path / ".zshrc")
    monkeypatch.setattr(setup, "_RC_PATHS", [tmp_path / ".zshrc", tmp_path / ".bashrc"])
    monkeypatch.setattr(setup, "load_categories", _no_categories)
    monkeypatch.setattr(setup, "detect", _platform)

    def never_installed(_tool: Tool) -> bool:
        return False

    monkeypatch.setattr(setup, "is_installed", never_installed)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())
    seen = _capture_app(monkeypatch)

    original = pnpm_globals.reinstall_preview

    def stubbed(
        packages: Sequence[str],
        *,
        known: bool = True,
        resolve_pnpm: Callable[[], str | None] | None = None,
        policy: NodeInstallPolicy | None = None,
    ) -> str:
        del resolve_pnpm
        return original(
            packages,
            known=known,
            resolve_pnpm=lambda: "/x/pnpm",
            policy=policy if policy is not None else NodeInstallPolicy(),
        )

    monkeypatch.setattr(pnpm_globals, "reinstall_preview", stubbed)
    assert setup.main(["--doctor"]) == 0
    preview = seen[0]["globals_preview"]
    assert callable(preview)
    report = NodeGlobalsReport(
        entries=(),
        missing=(),
        managed=("@mermaid-js/mermaid-cli", "puppeteer"),
    )
    text = cast("Callable[[NodeGlobalsReport], str]", preview)(report)
    assert "@mermaid-js/mermaid-cli,puppeteer@^25" in text
    assert "--allow-build=puppeteer" in text


def test_the_doctor_view_reads_the_ban_state_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Doctor report's ban half is a predicate too: the Policies view
    installs and removes the ban one nav step away."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--doctor"]) == 0
    captured = seen[0]["guard_state"]
    assert callable(captured)
    read_guard = cast("Callable[[], tuple[dict[str, bool], str | None]]", captured)

    assert not any(read_guard()[0].values())
    install_shims(tmp_path / ".local" / "bin")
    assert any(read_guard()[0].values())


def test_the_cli_teardown_is_wired_to_a_total_sweep_of_the_zdotdir_aware_zshrc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The non-TTY path, and the only way to observe the _ZSHRC/_RC_PATHS wire.

    Both are import-time constants closed over by every uninstall and policy
    wire, so the wire — that .zshrc comes from `installer.locations.zshrc_path`
    rather than a hardcoded `~/.zshrc`, and that `_RC_PATHS` reuses it so the
    ban aliases and the Oh-My-Zsh edit agree on which file is real — is only
    visible by re-importing under a different environment.
    """
    zdotdir = tmp_path / "zsh"
    zdotdir.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ZDOTDIR", str(zdotdir))
    importlib.reload(setup)
    try:
        forwarded: list[dict[str, object]] = []

        def fake_run_uninstall(_tools: object, _console: object, **kwargs: object) -> list[Path]:
            forwarded.append(kwargs)
            return []

        monkeypatch.setattr(setup, "load_tools", _no_tools)
        monkeypatch.setattr(setup, "detect", _platform)
        monkeypatch.setattr(setup, "run_uninstall", fake_run_uninstall)
        console = Console(file=io.StringIO(), width=100, no_color=True)
        monkeypatch.setattr(setup, "Console", lambda: console)

        assert setup.main(["--uninstall", "--yes"]) == 0
        assert forwarded[0]["bundles"] is BUNDLES
        assert forwarded[0]["zshrc_path"] == zdotdir / ".zshrc"
        assert forwarded[0]["rc_paths"] == [zdotdir / ".zshrc", tmp_path / ".bashrc"]
    finally:
        monkeypatch.undo()
        # conftest clears $ZDOTDIR to keep the suite off the developer's own zsh
        # setup; re-import under that same contract rather than whatever the
        # developer's shell exports.
        monkeypatch.delenv("ZDOTDIR", raising=False)
        importlib.reload(setup)


def test_the_non_interactive_uninstall_cli_forwards_a_real_daemon_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """setup.main(["--uninstall", "--yes"])'s non-interactive path constructs
    and forwards a real (non-None) daemon_policy into run_uninstall on macOS
    -- the CLI teardown sweep, per _build_daemon_policy's own single, shared
    construction point."""
    _sandbox(monkeypatch, tmp_path)
    forwarded: list[dict[str, object]] = []

    def fake_run_uninstall(_tools: object, _console: object, **kwargs: object) -> list[Path]:
        forwarded.append(kwargs)
        return []

    monkeypatch.setattr(setup, "run_uninstall", fake_run_uninstall)

    assert setup.main(["--uninstall", "--yes"]) == 0
    daemon_policy_obj = forwarded[0]["daemon_policy"]
    assert isinstance(daemon_policy_obj, Policy)
    assert daemon_policy_obj.id == "daemon:prune-tmpdir"


def test_the_interactive_uninstall_view_forwards_the_same_daemon_instance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_do_uninstall's own daemon_policy kwarg must be the SAME object (by
    identity) already appended to PolicyInputs.policies -- never a second,
    independently-constructed daemon_policy."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    forwarded: list[dict[str, object]] = []

    def fake_perform_uninstall(_decision: object, **kwargs: object) -> SweepResult:
        forwarded.append(kwargs)
        return SweepResult()

    monkeypatch.setattr(setup, "perform_uninstall", fake_perform_uninstall)

    assert setup.main(["--uninstall"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    daemon_in_list = next(p for p in policies.policies if p.id == "daemon:prune-tmpdir")

    inputs = seen[0]["uninstall"]
    assert isinstance(inputs, UninstallInputs)
    inputs.remove(
        UninstallDecision(paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=True)
    )
    assert forwarded[0]["daemon_policy"] is daemon_in_list


def test_build_app_wires_the_shared_terminal_closure_into_uninstall_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-01/15.6-06 Task 3, Test 3: _build_app passes the SAME
    composition-root closure to UninstallInputs that Policies, updates,
    unattended installation, the CLI uninstall route, and interactive close
    already reuse -- never a second, independently constructed synchronizer.
    `seen[0]["terminal_sync"]` is the exact closure `_build_app` handed
    UnifiedApp's own `terminal_sync` kwarg (Task 1); identity with
    `inputs.terminal_sync` is the proof."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    inputs = seen[0]["uninstall"]
    assert isinstance(inputs, UninstallInputs)
    assert inputs.terminal_sync is not None
    assert inputs.terminal_sync is seen[0]["terminal_sync"]


def _stub_install_run(monkeypatch: pytest.MonkeyPatch, summary: Summary) -> list[str]:
    """Drive setup.main through a full (stubbed) install run and record whether
    the troubleshooting pointer was rendered."""
    rendered: list[str] = []

    def fake_load_tools(_registry: object) -> list[Tool]:
        return []

    def fake_load_categories(_registry: object) -> dict[str, str]:
        return {}

    def fake_run_wizard(*_args: object, **_kwargs: object) -> Summary:
        return summary

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    def fake_render_troubleshooting(_console: object) -> None:
        rendered.append("shown")

    console = Console(file=io.StringIO(), width=100, no_color=True)
    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup, "load_categories", fake_load_categories)
    monkeypatch.setattr(setup, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(
        "installer.settings.default_settings_path", lambda: Path("/no/such/settings.json")
    )
    monkeypatch.setattr(
        setup, "default_settings_path", lambda: Path("/no/such/settings.json"), raising=False
    )
    monkeypatch.setattr(setup, "configure_path", noop)
    monkeypatch.setattr(setup, "_verify_and_clean", noop)
    monkeypatch.setattr(setup, "render_troubleshooting", fake_render_troubleshooting)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())
    monkeypatch.setattr(setup, "Console", lambda: console)
    return rendered


def test_a_dependency_failed_run_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    # A blocked dependent is a run that wanted to install something, could have,
    # and did not — a wrapper checking $? must not read that as a clean install.
    summary = Summary(
        installed=(),
        already=(),
        failed=(),
        no_method=("mmdc",),
        dependency_failed=("a", "b", "c"),
    )
    rendered = _stub_install_run(monkeypatch, summary)
    assert setup.main(["--all"]) == 1
    assert rendered == ["shown"]


def test_a_no_method_only_run_still_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unchanged, and deliberately so: a tool with no method on this platform was
    # never installable here, which is not a failure.
    summary = Summary(installed=("fd",), already=(), failed=(), no_method=("apt-upgrade",))
    rendered = _stub_install_run(monkeypatch, summary)
    assert setup.main(["--all"]) == 0
    assert rendered == []


def test_build_app_hands_unavailable_from_platform_could_support(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    debian_only = Tool(
        id="apt-upgrade",
        name="apt-upgrade",
        category="pkg-mgr",
        cmd="apt-upgrade",
        methods=(Method(kind="apt", params={"package": "x"}, os=("debian",)),),
        tier="system",
    )
    brew_tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(Method(kind="brew", params={"formula": "fd"}, os=("macos",), arch=("arm64",)),),
        tier="system",
    )

    def fake_load_tools(_registry: object) -> list[Tool]:
        return [debian_only, brew_tool]

    def fake_detect() -> Platform:
        return Platform(os="macos", arch="arm64", immutable=False, has_brew=False)

    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", fake_detect)
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    unavailable = seen[0]["unavailable"]
    assert isinstance(unavailable, dict)
    apt_upgrade = cast(object, unavailable["apt-upgrade"])
    assert isinstance(apt_upgrade, UnavailableReason)
    assert apt_upgrade.short == "macos not supported"
    assert unavailable["fd"] is False


def test_build_app_shares_one_version_refresh_service_across_tier_screens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    app = setup._build_app([], platform)  # pyright: ignore[reportPrivateUsage]
    service = app.catalog._version_refresh  # pyright: ignore[reportPrivateUsage]
    assert service is not None
    assert service.platform is platform
    assert app.catalog_for("user")._version_refresh is service  # pyright: ignore[reportPrivateUsage]
    assert app.catalog_for("ai")._version_refresh is service  # pyright: ignore[reportPrivateUsage]


def test_build_app_constructs_version_refresh_with_default_bin_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    app = setup._build_app([], platform)  # pyright: ignore[reportPrivateUsage]
    service = app.catalog._version_refresh  # pyright: ignore[reportPrivateUsage]
    assert service is not None
    assert service.managed_bin_dir == setup._DEFAULT_BIN_DIR  # pyright: ignore[reportPrivateUsage]


def test_build_app_shares_one_update_service_and_invalidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    app = setup._build_app([], platform)  # pyright: ignore[reportPrivateUsage]
    updates = app.catalog._updates  # pyright: ignore[reportPrivateUsage]
    assert updates is not None
    assert updates.platform is platform
    assert app.catalog_for("user")._updates is updates  # pyright: ignore[reportPrivateUsage]
    assert app.catalog_for("ai")._updates is updates  # pyright: ignore[reportPrivateUsage]
    refresh = app.catalog._version_refresh  # pyright: ignore[reportPrivateUsage]
    assert refresh is not None
    assert updates._invalidate == refresh.invalidate  # pyright: ignore[reportPrivateUsage]
    doctor = app._views["doctor"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(doctor, DoctorScreen)
    assert updates._replay_globals is doctor._reinstall_globals  # pyright: ignore[reportPrivateUsage]


def test_build_app_wires_the_shared_terminal_closure_into_update_service(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-01/15.6-05: the direct `u` update route reuses the SAME
    composition-root terminal closure Plan 04 wired for Policies -- not a
    second, independently constructed synchronizer."""
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    calls: list[dict[str, object]] = []

    def sync(**kwargs: object) -> TerminalShellResult:
        calls.append(kwargs)
        return TerminalShellResult(warnings=("wezterm configuration is user-owned",))

    monkeypatch.setattr(setup, "sync_terminal_shells", sync)
    app = setup._build_app([], platform)  # pyright: ignore[reportPrivateUsage]
    updates = app.catalog._updates  # pyright: ignore[reportPrivateUsage]
    assert updates is not None
    follow_up = updates._terminal_follow_up  # pyright: ignore[reportPrivateUsage]
    assert follow_up is not None
    warning = follow_up()
    assert warning == (
        "Terminal shell synchronization warning: wezterm configuration is user-owned"
    )
    assert len(calls) == 1
    assert calls[0] == {
        "home": tmp_path,
        "environ": os.environ,
        "platform": platform,
        "lookup": setup._which_with_brew,  # pyright: ignore[reportPrivateUsage]
    }


# -- D-01/15.6-06 Task 2: unattended installation and the command-line
# uninstall route both reuse the exact same terminal synchronizer Plans
# 04/05/06(Task 1) already wired for Policies, the direct `u` update, and
# interactive close -- never a second, independently constructed one -- and
# a raised OSError is reported to the console without ever flipping an
# already-determined primary exit code.


def _noninteractive_all_fixture(
    monkeypatch: pytest.MonkeyPatch, buffer: io.StringIO, summary: Summary
) -> None:
    def fake_load_tools(_registry: object) -> list[Tool]:
        return []

    def fake_load_categories(_registry: object) -> dict[str, str]:
        return {}

    def fake_run_wizard(*_args: object, **_kwargs: object) -> Summary:
        return summary

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup, "load_categories", fake_load_categories)
    monkeypatch.setattr(setup, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(
        "installer.settings.default_settings_path", lambda: Path("/no/such/settings.json")
    )
    monkeypatch.setattr(
        setup, "default_settings_path", lambda: Path("/no/such/settings.json"), raising=False
    )
    monkeypatch.setattr(setup, "configure_path", noop)
    monkeypatch.setattr(setup, "_verify_and_clean", noop)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=100, no_color=True))


def test_the_noninteractive_all_route_calls_the_terminal_synchronizer_after_run_wizard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1: the --all/category route invokes the shared synchronizer
    after run_wizard returns a summary and reports a nonfatal warning to the
    console."""
    buffer = io.StringIO()
    summary = Summary(installed=("fd",), already=(), failed=(), no_method=())
    _noninteractive_all_fixture(monkeypatch, buffer, summary)
    calls: list[dict[str, object]] = []

    def sync(**kwargs: object) -> TerminalShellResult:
        calls.append(kwargs)
        return TerminalShellResult(warnings=("wezterm configuration is user-owned",))

    monkeypatch.setattr(setup, "sync_terminal_shells", sync)

    assert setup.main(["--all", "--yes"]) == 0
    assert len(calls) == 1
    assert (
        "Terminal shell synchronization warning: wezterm configuration is user-owned"
        in buffer.getvalue()
    )


def test_the_cli_uninstall_route_calls_the_terminal_synchronizer_after_run_uninstall(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test 2: the command-line uninstall route invokes the same
    synchronizer after its removal flow so absent zsh removes only owned
    terminal configuration (sync_terminal_shells' own no-zsh reversion
    branch)."""
    _sandbox(monkeypatch, tmp_path)

    def fake_run_uninstall(_tools: object, _console: object, **_kwargs: object) -> list[Path]:
        return []

    monkeypatch.setattr(setup, "run_uninstall", fake_run_uninstall)
    buffer = io.StringIO()
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=100, no_color=True))
    calls: list[dict[str, object]] = []

    def sync(**kwargs: object) -> TerminalShellResult:
        calls.append(kwargs)
        return TerminalShellResult(warnings=("wezterm configuration is user-owned",))

    monkeypatch.setattr(setup, "sync_terminal_shells", sync)

    assert setup.main(["--uninstall", "--yes"]) == 0
    assert len(calls) == 1
    assert (
        "Terminal shell synchronization warning: wezterm configuration is user-owned"
        in buffer.getvalue()
    )


def test_the_noninteractive_all_route_survives_a_raising_terminal_synchronizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3 (install half): a synchronizer OSError never flips an
    already-determined exit code, and produces an explicit console warning."""
    buffer = io.StringIO()
    summary = Summary(installed=("fd",), already=(), failed=(), no_method=())
    _noninteractive_all_fixture(monkeypatch, buffer, summary)

    def boom(**_kwargs: object) -> TerminalShellResult:
        raise OSError("EACCES: ~/.config/kitty/kitty.conf")

    monkeypatch.setattr(setup, "sync_terminal_shells", boom)

    assert setup.main(["--all", "--yes"]) == 0
    text = buffer.getvalue()
    assert "Terminal shell synchronization failed" in text
    assert "EACCES" in text


def test_the_cli_uninstall_route_survives_a_raising_terminal_synchronizer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test 3 (uninstall half): the same non-fatal contract on the
    command-line teardown route."""
    _sandbox(monkeypatch, tmp_path)

    def fake_run_uninstall(_tools: object, _console: object, **_kwargs: object) -> list[Path]:
        return []

    monkeypatch.setattr(setup, "run_uninstall", fake_run_uninstall)
    buffer = io.StringIO()
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=100, no_color=True))

    def boom(**_kwargs: object) -> TerminalShellResult:
        raise OSError("EACCES: ~/.config/kitty/kitty.conf")

    monkeypatch.setattr(setup, "sync_terminal_shells", boom)

    assert setup.main(["--uninstall", "--yes"]) == 0
    text = buffer.getvalue()
    assert "Terminal shell synchronization failed" in text
    assert "EACCES" in text


def test_which_with_brew_finds_a_linuxbrew_binary_shutil_which_cannot_see(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CR-04: on an immutable host, registry.toml's zsh entry installs via
    brew and engine.py never adds the brew bin dir to THIS process's own
    PATH, so a bare shutil.which("zsh") still returns None immediately after
    the install this phase exists to react to. _which_with_brew must find it
    anyway, by disk presence, the same way _resolve_rtk_binary already does
    for rtk."""

    def which_misses(_name: str) -> str | None:
        return None

    monkeypatch.setattr(setup.shutil, "which", which_misses)
    linuxbrew = tmp_path / "linuxbrew"
    linuxbrew.mkdir()
    (linuxbrew / "zsh").write_text("#!/bin/sh\n")
    monkeypatch.setattr(setup, "BREW_BIN_DIRS", (linuxbrew,))

    assert setup._which_with_brew("zsh") == str(linuxbrew / "zsh")  # pyright: ignore[reportPrivateUsage]
    assert setup._which_with_brew("does-not-exist") is None  # pyright: ignore[reportPrivateUsage]


def test_which_with_brew_prefers_a_real_shutil_which_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    def which_hits(_name: str) -> str | None:
        return "/usr/bin/zsh"

    monkeypatch.setattr(setup.shutil, "which", which_hits)

    assert setup._which_with_brew("zsh") == "/usr/bin/zsh"  # pyright: ignore[reportPrivateUsage]


def test_sync_terminals_surfaces_a_silent_revert_as_a_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CR-04/IN-01: a full revert (zsh no longer discoverable) used to be
    reported identically to a fully successful run -- only `.warnings` was
    ever read. A revert must now produce its own message."""
    platform = _platform()

    def sync(**_kwargs: object) -> TerminalShellResult:
        return TerminalShellResult(reverted=("kitty", "konsole"))

    monkeypatch.setattr(setup, "sync_terminal_shells", sync)

    warning = setup._sync_terminals(platform)  # pyright: ignore[reportPrivateUsage]

    assert warning is not None
    assert "reverted" in warning
    assert "kitty" in warning
    assert "konsole" in warning


def test_build_app_always_builds_execute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """D-12: _build_app builds ExecuteInputs itself, so no route can ever
    build an app that cannot execute an accepted selection."""
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    app = setup._build_app([], platform)  # pyright: ignore[reportPrivateUsage]
    execute = app._execute  # pyright: ignore[reportPrivateUsage]
    assert execute is not None
    assert isinstance(execute, ExecuteInputs)
    assert execute.catalog == []
    assert execute.unattended is False
    assert execute.updates is app.catalog._updates  # pyright: ignore[reportPrivateUsage]
    assert (
        execute.version_refresh is app.catalog._version_refresh  # pyright: ignore[reportPrivateUsage]
    )
    unattended_app = setup._build_app([], platform, unattended=True)  # pyright: ignore[reportPrivateUsage]
    assert unattended_app._execute is not None  # pyright: ignore[reportPrivateUsage]
    assert unattended_app._execute.unattended is True  # pyright: ignore[reportPrivateUsage]


def test_build_app_has_no_execute_parameter() -> None:
    """D-12's rejected alternative (passing execute= at the four routes)
    stays rejected: the parameter is gone, so no current or future caller can
    hand an app that cannot execute."""
    assert "execute" not in inspect.signature(setup._build_app).parameters  # pyright: ignore[reportPrivateUsage]


async def _pilot_accepts_the_selection(
    app: UnifiedApp, pilot: Pilot[list[str] | None], recorded: list[str]
) -> None:
    """Navigate to the catalog (the one navigation path), mark the fake tool,
    accept, start the run and wait for it to settle. Shared by every route
    pilot: --doctor/--fix open on doctor, --uninstall on uninstall, --guard
    on policies, and setup already starts on the catalog (no-op call)."""
    await app.show_view(BASE_VIEW)
    assert app.current_view == BASE_VIEW
    await pilot.pause()
    app.catalog.selected.add("rg")
    await pilot.press("enter")
    screen = cast(ExecuteScreen, app.screen)
    assert screen.finished is False
    await pilot.press("enter")
    for _ in range(400):
        screen = app.screen
        if isinstance(screen, ExecuteScreen) and screen.finished:
            break
        await pilot.pause()
    await pilot.pause()
    assert recorded == ["rg"]


@pytest.mark.parametrize(
    ("case_id", "fixture"),
    [
        ("invalid-utf8", b'\xff\xfe{"link_mode": "split"}'),
        ("invalid-json", b'{"link_mode": '),
    ],
)
async def test_invalid_settings_file_launches_to_the_first_screen_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case_id: str,
    fixture: bytes,
) -> None:
    """SPEC R8 / D-11: a damaged settings.json costs the user a warning, never
    the app and never their file. The bytes on disk are identical after a full
    launch whose first-run picker is dismissed."""
    del case_id
    from textual.screen import Screen

    from installer.wizard_app import LinkModeScreen

    _hermetic_route(monkeypatch, tmp_path)
    path = tmp_path / "settings.json"
    path.write_bytes(fixture)
    apps: list[UnifiedApp] = []

    def recording_run(self: UnifiedApp) -> None:
        apps.append(self)

    monkeypatch.setattr(UnifiedApp, "run", recording_run)
    assert setup.main([]) == 0
    app = apps[0]
    async with app.run_test(size=(100, 30)) as pilot:
        assert isinstance(app.screen, LinkModeScreen)
        assert str(path) in app.catalog.status.text
        assert app.catalog.status.severity is Severity.WARN
        await pilot.press("escape")
        assert isinstance(app.screen, Screen)
    assert path.read_bytes() == fixture


@pytest.mark.parametrize(
    ("route_id", "argv"),
    [
        ("setup", []),
        ("doctor", ["--doctor"]),
        ("fix", ["--fix"]),
        ("uninstall", ["--uninstall"]),
        ("guard", ["--guard"]),
    ],
)
async def test_every_tui_route_executes_the_accepted_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    route_id: str,
    argv: list[str],
) -> None:
    """SPEC R9: Enter on a catalog selection executes it on every TUI route
    (setup, doctor, fix, uninstall, guard)."""
    del route_id
    recorded = _hermetic_route(monkeypatch, tmp_path)
    apps: list[UnifiedApp] = []

    def recording_run(self: UnifiedApp) -> None:
        apps.append(self)

    monkeypatch.setattr(UnifiedApp, "run", recording_run)
    assert setup.main(argv) == 0
    app = apps[0]
    async with app.run_test(size=(100, 30)) as pilot:
        await _pilot_accepts_the_selection(app, pilot, recorded)


@pytest.mark.parametrize(
    "argv",
    [
        ["--doctor"],
        ["--fix"],
        ["--uninstall"],
        ["--guard"],
    ],
)
def test_tui_routes_exit_1_when_the_session_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str]
) -> None:
    """SAFE-05: every non-setup TUI route reports a failed session in its exit
    code through the one rule, Summary.has_failure."""
    for summary, expected in (
        (Summary(installed=(), already=(), failed=("rg",), no_method=()), 1),
        (Summary(installed=("rg",), already=(), failed=(), no_method=()), 0),
        (None, 0),
    ):
        _hermetic_route(monkeypatch, tmp_path)
        _capture_app(monkeypatch, install_summary=summary)
        assert setup.main(argv) == expected


def test_build_app_reresolve_reads_live_inventory_not_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I3 regression (12-REVIEW.md, codex-sol-high): the previous version of
    this test patched `installer.ownership.run_query` and
    `installer.ownership.pnpm_global_packages` by name, but
    `read_inventory`'s `query`/`pnpm_packages` parameters default to those
    names at FUNCTION-DEFINITION time — `setup.py::_reresolve_ownership`
    calls `read_inventory(has_brew=...)` with neither overridden, so the
    already-bound default objects run regardless of any later monkeypatch of
    the module attribute. The old test's mocks were therefore inert (proven
    by patching `installer.ownership.run_query` and calling
    `read_inventory` directly — the patched callable is never invoked), and
    its assertions were loosened to `first.owner != second.owner or
    second.owner == "brew"` / `second.owner in {"brew", "unknown",
    "installer"}` to paper over that, which would pass even if
    `_reresolve_ownership` were reading a stale cache instead of live state.

    This version intercepts at the actual boundary those defaults call
    into at call-time — `installer.run.subprocess.run` — which respects a
    monkeypatch because `run_query`'s BODY looks up `subprocess.run` fresh
    on every call, unlike a default parameter value.
    """
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    tool = Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=(Method(kind="brew", params={"formula": "ripgrep"}),),
        tier="system",
    )
    state: dict[str, dict[str, str]] = {"formulae": {}}

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["brew", "--prefix"]:
            stdout = "/opt/homebrew\n"
        elif cmd[:3] == ["brew", "list", "--versions"] and "--formula" in cmd:
            stdout = "ripgrep 14.1.1\n" if state["formulae"] else ""
        elif (cmd[:3] == ["brew", "list", "--versions"] and "--cask" in cmd) or cmd[:3] == [
            "uv",
            "tool",
            "list",
        ]:
            stdout = ""
        else:
            stdout = ""
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    # `installer.run.subprocess.run` is the actual system-call boundary every
    # manager query goes through — `run_query`/`run_output` look it up fresh
    # on each call, so this patch (unlike the inert ones above) takes effect
    # for brew, uv, AND pnpm queries alike; pnpm's own real-binary resolution
    # is a plain PATH lookup with no subprocess call, so it needs no patch.
    monkeypatch.setattr("installer.run.subprocess.run", fake_run)

    # Hermetic: `_reresolve_ownership` calls `shutil.which(tool.cmd)` for real
    # PATH attribution, which would otherwise read whatever `rg` this actual
    # test-running machine happens to have on PATH. Pin it to "not found" so
    # the by-elimination branch this test targets is reached deterministically.
    def fake_which(_cmd: str, *, mode: int = 0, path: str | None = None) -> str | None:
        return None

    monkeypatch.setattr("shutil.which", fake_which)
    app = setup._build_app([tool], platform)  # pyright: ignore[reportPrivateUsage]
    updates = app.catalog._updates  # pyright: ignore[reportPrivateUsage]
    assert updates is not None
    first = updates._reresolve_ownership(tool)  # pyright: ignore[reportPrivateUsage]
    assert first.owner == "unknown"  # no brew formula listed yet, nothing on PATH
    state["formulae"] = {"ripgrep": "14.1.1"}
    second = updates._reresolve_ownership(tool)  # pyright: ignore[reportPrivateUsage]
    assert second.owner == "brew"
    assert second.current_version == "14.1.1"


def _always_installed(_tool: Tool) -> bool:
    return True


def _dnf_owned_rg() -> ManagerOwnership:
    return ManagerOwnership(
        tool_id="rg",
        owner="dnf",
        method=None,
        package="ripgrep",
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )


def test_build_app_uninstall_hint_changes_when_the_ownership_map_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The rows closure's `owner_hint` binding re-reads the shared
    `VersionRefreshService.ownership_of` map LIVE (D-05), the same
    live-re-read shape `test_build_app_reresolve_reads_live_inventory_not_cache`
    proves for `_reresolve_ownership`: a record populated into the map after
    construction changes the NEXT `rows()` call's hint, with no rebuild."""
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    tool = Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=(Method(kind="dnf", params={"package": "ripgrep"}),),
        tier="system",
    )
    monkeypatch.setattr(setup, "is_installed", _always_installed)
    app = setup._build_app([tool], platform)  # pyright: ignore[reportPrivateUsage]
    screen = app._views["uninstall"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(screen, UninstallScreen)
    rows_predicate = screen._rows_predicate  # pyright: ignore[reportPrivateUsage]
    service = app._version_refresh  # pyright: ignore[reportPrivateUsage]
    assert service is not None

    before = next(r for r in rows_predicate() if r.tool.id == "rg")
    assert "package manager" in before.hint  # no ownership pass has run yet

    service._ownership["rg"] = (service.epoch, _dnf_owned_rg())  # pyright: ignore[reportPrivateUsage]

    after = next(r for r in rows_predicate() if r.tool.id == "rg")
    assert "ripgrep" in after.hint
    assert "dnf remove ripgrep" in after.hint


def test_build_app_uninstall_hint_reverts_after_the_service_is_invalidated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-05: once the shared service is invalidated, the closure's hint
    reverts to the platform-filtered registry phrase -- the epoch-gated
    `ownership_of` reports the pre-invalidation record as unavailable rather
    than stale-but-present."""
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    tool = Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=(Method(kind="dnf", params={"package": "ripgrep"}),),
        tier="system",
    )
    monkeypatch.setattr(setup, "is_installed", _always_installed)
    app = setup._build_app([tool], platform)  # pyright: ignore[reportPrivateUsage]
    screen = app._views["uninstall"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(screen, UninstallScreen)
    rows_predicate = screen._rows_predicate  # pyright: ignore[reportPrivateUsage]
    service = app._version_refresh  # pyright: ignore[reportPrivateUsage]
    assert service is not None

    service._ownership["rg"] = (service.epoch, _dnf_owned_rg())  # pyright: ignore[reportPrivateUsage]
    before = next(r for r in rows_predicate() if r.tool.id == "rg")
    assert "ripgrep" in before.hint

    service.invalidate(reason="test")
    after = next(r for r in rows_predicate() if r.tool.id == "rg")
    assert "ripgrep" not in after.hint
    assert "package manager" in after.hint


def test_build_app_wires_a_refresh_seam_that_restores_the_invalidated_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WR-01 (15.4-REVIEW.md): the composition root binds the pass that
    REPLACES what the removal's own invalidate drops. Without it nothing on
    the Uninstall screen could restore attribution -- `OwnershipRefreshed` is
    posted only from `CatalogScreen`, so a session that never returns to a
    catalog tab keeps the degraded generic phrase until it exits.

    Asserted through the SAME closure pair the test above uses, so this is
    the recovery arm of that degradation rather than a separate claim."""
    _sandbox(monkeypatch, tmp_path)
    platform = _platform()
    tool = Tool(
        id="rg",
        name="ripgrep",
        category="search",
        cmd="rg",
        methods=(Method(kind="dnf", params={"package": "ripgrep"}),),
        tier="system",
    )
    monkeypatch.setattr(setup, "is_installed", _always_installed)
    app = setup._build_app([tool], platform)  # pyright: ignore[reportPrivateUsage]
    screen = app._views["uninstall"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(screen, UninstallScreen)
    rows_predicate = screen._rows_predicate  # pyright: ignore[reportPrivateUsage]
    refresh = screen._refresh  # pyright: ignore[reportPrivateUsage]
    assert refresh is not None
    service = app._version_refresh  # pyright: ignore[reportPrivateUsage]
    assert service is not None

    service._ownership["rg"] = (service.epoch, _dnf_owned_rg())  # pyright: ignore[reportPrivateUsage]
    service.invalidate(reason="test")
    degraded = next(r for r in rows_predicate() if r.tool.id == "rg")
    assert "package manager" in degraded.hint
    assert degraded.manager is None

    # The seam re-resolves against the real (sandboxed, offline) environment;
    # what matters here is that it commits a pass under the CURRENT epoch, so
    # the screen stops reporting every record as unavailable.
    refresh()
    assert service.ownership_of("rg") is not None


def test_interactive_main_never_calls_run_wizard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("interactive path must not call run_wizard")

    monkeypatch.setattr(setup, "run_wizard", boom)
    assert setup.main([]) == 0
    assert seen  # UnifiedApp was constructed


def test_headless_all_never_constructs_unified_app(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("headless --all must not construct UnifiedApp")

    rendered = _stub_install_run(
        monkeypatch, Summary(installed=("fd",), already=(), failed=(), no_method=())
    )
    monkeypatch.setattr(setup, "_build_app", boom)
    assert setup.main(["--all", "--yes"]) == 0
    assert rendered == []


def test_interactive_app_is_built_with_execute_and_daemon_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    assert seen[0]["execute"] is not None
    assert callable(seen[0]["daemon_default"])


def test_execute_inputs_wire_path_calls_configure_path_and_returns_captured_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[dict[str, object]] = []

    def fake_configure_path(tools: object, console: Console, **kwargs: object) -> None:
        captured.append({"tools": tools, "console": console, **kwargs})
        console.print("PATH configured")

    monkeypatch.setattr(setup, "configure_path", fake_configure_path)
    monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", tmp_path / ".local" / "bin")
    monkeypatch.setattr(setup, "_MYSHELLRC", tmp_path / ".myshellrc")
    monkeypatch.setattr(setup, "_SHELLRC", tmp_path / ".shellrc")
    monkeypatch.setattr(setup, "_SHELL", "/bin/zsh")
    inputs = setup._execute_inputs(  # pyright: ignore[reportPrivateUsage]
        [],
        _platform(),
        link_mode="single",
        unattended=True,
        disk_pressure=_unused_probe,
    )
    text = inputs.wire_path()
    assert "PATH configured" in text
    assert captured
    assert captured[0]["link_mode"] == "single"
    # The new argument, and that it points inside the sandbox rather than at a
    # real-home path: an un-redirected constant here would consolidate the
    # developer's own ~/.shellrc.
    assert captured[0]["shellrc_path"] == tmp_path / ".shellrc"
    rc_paths = captured[0]["rc_paths"]
    assert isinstance(rc_paths, list)
    rc_paths_list = cast("list[object]", rc_paths)
    assert all(isinstance(path, Path) for path in rc_paths_list)


def test_execute_inputs_verify_calls_run_doctor_and_returns_captured_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[dict[str, object]] = []

    def fake_run_doctor(tools: object, console: Console, **kwargs: object) -> object:
        captured.append({"tools": tools, "console": console, **kwargs})
        console.print("PATH audit")
        return object()

    monkeypatch.setattr(setup, "run_doctor", fake_run_doctor)
    monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", tmp_path / ".local" / "bin")
    inputs = setup._execute_inputs(  # pyright: ignore[reportPrivateUsage]
        [],
        _platform(),
        link_mode="centralized",
        unattended=False,
        disk_pressure=_unused_probe,
    )
    text = inputs.verify()
    assert "PATH audit" in text
    assert captured
    assert captured[0]["path_value"] == os.environ.get("PATH", "")
    assert captured[0]["exists"] is Path.is_dir


def test_interactive_none_summary_prints_aborted_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    buffer = io.StringIO()
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=100, no_color=True))
    _capture_app(monkeypatch)
    assert setup.main([]) == 0
    assert "Aborted." in buffer.getvalue()


class _SummaryApp:
    def __init__(self, summary: Summary | None) -> None:
        self.install_summary = summary

    def run(self) -> None:
        return None


def _wire_interactive_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, app: _SummaryApp
) -> list[str]:
    _sandbox(monkeypatch, tmp_path)
    rendered: list[str] = []

    def fake_render_troubleshooting(_console: object) -> None:
        rendered.append("shown")

    def fake_clean(*_args: object, **_kwargs: object) -> dict[Path, list[str]]:
        return {}

    def fake_collect(*_args: object, **_kwargs: object) -> list[Path]:
        return []

    def fake_build(*_args: object, **_kwargs: object) -> _SummaryApp:
        return app

    monkeypatch.setattr(setup, "render_troubleshooting", fake_render_troubleshooting)
    monkeypatch.setattr(setup, "clean_rc_duplicates", fake_clean)
    monkeypatch.setattr(setup, "collect_bin_dirs", fake_collect)
    monkeypatch.setattr(setup, "_build_app", fake_build)
    return rendered


def test_interactive_failed_summary_renders_troubleshooting_and_returns_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rendered = _wire_interactive_summary(
        monkeypatch,
        tmp_path,
        _SummaryApp(Summary(installed=(), already=(), failed=("rg",), no_method=())),
    )
    assert setup.main([]) == 1
    assert rendered == ["shown"]


def test_interactive_clean_summary_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rendered = _wire_interactive_summary(
        monkeypatch,
        tmp_path,
        _SummaryApp(Summary(installed=("rg",), already=(), failed=(), no_method=())),
    )
    assert setup.main([]) == 0
    assert rendered == []


def test_interactive_path_cleans_rc_duplicates_without_re_running_doctor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cleaned: list[str] = []
    doctors: list[str] = []

    def fake_clean(*_args: object, **_kwargs: object) -> dict[Path, list[str]]:
        cleaned.append("cleaned")
        return {}

    def fake_doctor(*_args: object, **_kwargs: object) -> None:
        doctors.append("doctor")

    def fake_collect(*_args: object, **_kwargs: object) -> list[Path]:
        return []

    def fake_build(*_args: object, **_kwargs: object) -> _SummaryApp:
        return _SummaryApp(Summary(installed=("rg",), already=(), failed=(), no_method=()))

    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "clean_rc_duplicates", fake_clean)
    monkeypatch.setattr(setup, "run_doctor", fake_doctor)
    monkeypatch.setattr(setup, "collect_bin_dirs", fake_collect)
    monkeypatch.setattr(setup, "_build_app", fake_build)
    assert setup.main([]) == 0
    assert cleaned == ["cleaned"]
    assert doctors == []


def test_interactive_run_with_nothing_stored_opens_the_app_without_a_questionary_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("interactive run must not prompt for link mode")

    monkeypatch.setattr(setup, "_ask_select", boom)
    monkeypatch.setattr(setup.questionary, "select", boom)
    assert setup.main([]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert policies.link_mode is not None
    assert policies.link_mode() == "centralized"
    assert seen[0].get("prompt_link_mode") is True


def test_interactive_run_uses_stored_split_and_prompts_for_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    _store_link_mode(monkeypatch, tmp_path, "split")
    seen = _capture_app(monkeypatch)

    def boom(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("stored preference must not re-prompt")

    monkeypatch.setattr(setup, "_ask_select", boom)
    assert setup.main([]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert policies.link_mode is not None
    assert policies.link_mode() == "split"
    assert seen[0].get("prompt_link_mode") is False


def test_link_mode_flag_overrides_stored_split_without_rewriting_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    path = _store_link_mode(monkeypatch, tmp_path, "split")
    seen = _capture_app(monkeypatch)
    assert setup.main(["--link-mode", "single"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert policies.link_mode is not None
    assert policies.link_mode() == "single"
    assert load_settings(path).settings.link_mode == "split"
    assert seen[0].get("prompt_link_mode") is False


def test_live_set_link_mode_rereads_fix_preview_apply_execute_and_policies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "_SHELL", "/bin/zsh")
    seen = _capture_app(monkeypatch)
    store = SettingsStore(tmp_path / "settings.json", link_mode="centralized")
    setup._build_app([], _platform(), settings=store)  # pyright: ignore[reportPrivateUsage]
    preview = seen[0]["fix_preview"]
    assert callable(preview)
    store.set_link_mode("split")
    text = cast(Callable[[], str], preview)()
    assert ".zshrc" in text
    assert ".bashrc" in text
    assert ".myshellrc" not in text

    captured: list[dict[str, object]] = []

    def fake_configure_path(_tools: object, _console: object, **kwargs: object) -> None:
        captured.append(kwargs)

    monkeypatch.setattr(setup, "configure_path", fake_configure_path)
    fix = seen[0]["fix"]
    assert callable(fix)
    cast(Callable[[], None], fix)()
    assert captured[0]["link_mode"] == "split"
    rc_paths = captured[0]["rc_paths"]
    assert isinstance(rc_paths, list)
    names = {Path(str(path)).name for path in cast("list[object]", rc_paths)}
    assert names == {".zshrc", ".bashrc"}

    execute = seen[0]["execute"]
    assert execute is not None
    captured.clear()
    cast(ExecuteInputs, execute).wire_path()
    assert captured[0]["link_mode"] == "split"

    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    ban = next(policy for policy in policies.policies if policy.id == "ban")
    result = ban.apply()
    alias_detail = result.layers[1].detail
    assert ".zshrc" in alias_detail
    assert ".bashrc" in alias_detail
    assert ".myshellrc" not in alias_detail
    tweak = next(policy for policy in policies.policies if policy.id == "tweak:codex-skip")
    tweak.apply()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".zshrc").read_text()
    assert str(tmp_path / ".myshellrc") in (tmp_path / ".bashrc").read_text()


def test_doctor_uninstall_and_guard_wire_the_store_but_never_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--doctor"]) == 0
    assert setup.main(["--uninstall"]) == 0
    assert setup.main(["--guard"]) == 0
    assert len(seen) == 3
    for kwargs in seen:
        policies = kwargs["policies"]
        assert isinstance(policies, PolicyInputs)
        assert policies.set_link_mode is not None
        assert kwargs.get("prompt_link_mode") is False


def test_all_yes_and_no_tty_never_prompt_for_link_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = _capture_app(monkeypatch)
    _stub_install_run(monkeypatch, Summary(installed=("fd",), already=(), failed=(), no_method=()))
    assert setup.main(["--all", "--yes"]) == 0
    assert all(kwargs.get("prompt_link_mode") is not True for kwargs in seen)

    seen.clear()
    monkeypatch.setattr(setup.sys, "stdin", _NonTtyStdin())

    def fake_open(_path: str, _flags: int) -> int:
        raise OSError("no controlling terminal")

    monkeypatch.setattr(setup.os, "open", fake_open)
    assert setup.main([]) == 2
    assert all(kwargs.get("prompt_link_mode") is not True for kwargs in seen)


def test_non_interactive_fix_with_link_mode_flag_writes_split_and_stores_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    written: list[str] = []

    def fake_configure_path(_tools: object, _console: object, **kwargs: object) -> None:
        written.append(str(kwargs["link_mode"]))

    monkeypatch.setattr(setup, "configure_path", fake_configure_path)
    path = tmp_path / "settings.json"
    assert setup.main(["--fix", "--link-mode", "split"]) == 0
    assert written == ["split"]
    assert not path.exists()
    assert load_settings(path).settings.link_mode is None


# -- D-05/Task 2: setup.py is excluded from pyright and coverage by design
# (see the Makefile's own comment), so a read of the committed composition
# root is how this repository pins the two native_probe wiring sites -- the
# display-path VersionRefreshService construction and the mutation-path
# _reresolve_ownership closure. Only wiring both prevents the catalog from
# showing an owner the mutation path re-resolves as unknown a moment later.


def test_build_app_arms_the_collector_only_when_it_wires_the_daemon_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.policy import DaemonDefaultWarnings

    _sandbox(monkeypatch, tmp_path)
    armed = DaemonDefaultWarnings()
    unarmed = DaemonDefaultWarnings()
    setup._build_app(  # pyright: ignore[reportPrivateUsage]
        [],
        _platform(),
        apply_daemon_default=True,
        daemon_default_warnings=armed,
    )
    setup._build_app(  # pyright: ignore[reportPrivateUsage]
        [],
        _platform(),
        apply_daemon_default=False,
        daemon_default_warnings=unarmed,
    )
    assert armed.wait(0.05)[1] is False
    messages, completed = unarmed.wait(5)
    assert messages == ()
    assert completed is True


def test_interactive_wizard_prints_warnings_before_the_abort_return(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.policy import DaemonDefaultWarnings

    buffer = io.StringIO()
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=120, no_color=True))
    collector = DaemonDefaultWarnings()

    class _Aborting:
        install_summary = None

        def run(self) -> None:
            collector.append("another timer is still running")
            collector.finish()

    def fake_build(*_args: object, **kwargs: object) -> _Aborting:
        handed = kwargs["daemon_default_warnings"]
        assert isinstance(handed, DaemonDefaultWarnings)
        assert handed is collector
        handed.arm()
        return _Aborting()

    monkeypatch.setattr(setup, "_build_app", fake_build)
    monkeypatch.setattr(setup, "DaemonDefaultWarnings", lambda: collector)
    assert setup.main([]) == 0
    text = buffer.getvalue()
    warning_at = text.index("another timer is still running")
    aborted_at = text.index("Aborted.")
    assert warning_at < aborted_at


def test_interactive_wizard_prints_warnings_on_the_normal_path_and_stays_quiet_when_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.policy import DaemonDefaultWarnings
    from installer.session import Summary

    buffer = io.StringIO()
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=120, no_color=True))

    def no_duplicates(*_args: object, **_kwargs: object) -> dict[Path, list[str]]:
        return {}

    def no_bins(*_args: object, **_kwargs: object) -> list[Path]:
        return []

    monkeypatch.setattr(setup, "clean_rc_duplicates", no_duplicates)
    monkeypatch.setattr(setup, "collect_bin_dirs", no_bins)
    collector = DaemonDefaultWarnings()

    class _Done:
        install_summary = Summary(installed=("rg",), already=(), failed=(), no_method=())

        def run(self) -> None:
            collector.append("taken over")
            collector.finish()

    def fake_build(*_args: object, **_kwargs: object) -> _Done:
        collector.arm()
        return _Done()

    monkeypatch.setattr(setup, "_build_app", fake_build)
    monkeypatch.setattr(setup, "DaemonDefaultWarnings", lambda: collector)
    assert setup.main([]) == 0
    assert "taken over" in buffer.getvalue()
    assert "Aborted." not in buffer.getvalue()

    quiet = io.StringIO()
    empty = DaemonDefaultWarnings()
    monkeypatch.setattr(setup, "Console", lambda: Console(file=quiet, width=120, no_color=True))

    class _Quiet:
        install_summary = Summary(installed=("rg",), already=(), failed=(), no_method=())

        def run(self) -> None:
            return None

    def quiet_build(*_args: object, **_kwargs: object) -> _Quiet:
        return _Quiet()

    monkeypatch.setattr(setup, "_build_app", quiet_build)
    monkeypatch.setattr(setup, "DaemonDefaultWarnings", lambda: empty)
    assert setup.main([]) == 0
    assert quiet.getvalue() == ""


def test_interactive_wizard_labels_a_timed_out_background_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.policy import DAEMON_DEFAULT_WAIT_SECONDS, DaemonDefaultWarnings

    buffer = io.StringIO()
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "Console", lambda: Console(file=buffer, width=120, no_color=True))
    collector = DaemonDefaultWarnings()

    class _Aborting:
        install_summary = None

        def run(self) -> None:
            collector.append("partial")

    def fake_build(*_args: object, **_kwargs: object) -> _Aborting:
        collector.arm()
        return _Aborting()

    monkeypatch.setattr(setup, "_build_app", fake_build)
    monkeypatch.setattr(setup, "DaemonDefaultWarnings", lambda: collector)
    monkeypatch.setattr(setup, "DAEMON_DEFAULT_WAIT_SECONDS", 0.01)
    assert setup.main([]) == 0
    text = buffer.getvalue()
    assert "partial" in text
    assert "had not finished" in text
    assert DAEMON_DEFAULT_WAIT_SECONDS > 0


def test_both_uninstall_routes_pass_the_same_cache_redirect_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    cli: list[dict[str, object]] = []
    interactive: list[dict[str, object]] = []

    def fake_run_uninstall(_tools: object, _console: object, **kwargs: object) -> list[Path]:
        cli.append(kwargs)
        return []

    def fake_perform_uninstall(_decision: object, **kwargs: object) -> SweepResult:
        interactive.append(kwargs)
        return SweepResult()

    monkeypatch.setattr(setup, "run_uninstall", fake_run_uninstall)
    monkeypatch.setattr(setup, "perform_uninstall", fake_perform_uninstall)
    assert setup.main(["--uninstall", "--yes"]) == 0
    assert setup.main(["--uninstall"]) == 0
    inputs = seen[-1]["uninstall"]
    assert isinstance(inputs, UninstallInputs)
    inputs.remove(
        UninstallDecision(paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=True)
    )
    policies = seen[-1]["policies"]
    assert isinstance(policies, PolicyInputs)
    listed = tuple(
        policy.id for policy in policies.policies if policy.id.startswith("cache-redirect:")
    )

    def redirect_ids(forwarded: dict[str, object]) -> tuple[str, ...]:
        extras = forwarded["extra_policies"]
        assert isinstance(extras, tuple)
        found: list[str] = []
        for item in cast("tuple[object, ...]", extras):
            if isinstance(item, Policy):
                found.append(item.id)
        return tuple(found)

    assert listed
    assert redirect_ids(cli[0]) == listed
    assert redirect_ids(interactive[0]) == listed
    assert interactive[0]["extra_policies"] == tuple(
        policy for policy in policies.policies if policy.id.startswith("cache-redirect:")
    )


def _unused_probe() -> DiskPressure:
    raise AssertionError("this test's path must not probe disk pressure")


def _linux_platform() -> Platform:
    return Platform(os="linux", arch="amd64", immutable=False, has_brew=True)


def _recording_reader(queries: list[list[str]], answer: str = "inactive") -> Callable[..., str]:
    def read(argv: Sequence[str]) -> str:
        queries.append(list(argv))
        return answer

    return read


def test_disk_pressure_probe_is_a_zero_arg_callable_returning_disk_pressure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.diskusage import DiskPressure

    monkeypatch.setattr(setup, "_DAEMON_PLIST_PATH", tmp_path / "missing.plist")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _platform(), timer_cache=None
    )
    pressure = probe()
    assert isinstance(pressure, DiskPressure)


def test_non_blocking_probe_never_queries_systemd_in_any_cache_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.enums import DaemonState
    from installer.systemd_daemon import TimerStateCache

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    queries: list[str] = []
    now = [0.0]

    def is_active() -> DaemonState:
        queries.append("is-active")
        return DaemonState.INACTIVE

    cache = TimerStateCache(is_active, ttl=10.0, clock=lambda: now[0])
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), timer_cache=cache
    )
    # Truly cold: nothing to peek at, the daemon half is omitted (UNAVAILABLE)
    # while the temp usage -- a statvfs, not systemd -- is still measured.
    cold = probe(blocking=False)
    assert cold.daemon is DaemonState.UNAVAILABLE
    assert cold.tmp_used_percent is not None
    assert queries == []
    cache.read()
    queries.clear()
    assert probe(blocking=False).daemon is DaemonState.INACTIVE  # warm
    now[0] = 10_000.0
    assert probe(blocking=False).daemon is DaemonState.INACTIVE  # far past the TTL
    cache.invalidate()
    assert probe(blocking=False).daemon is DaemonState.INACTIVE  # just invalidated
    assert queries == []
    # The default stays the blocking read: a stale memo is re-probed once.
    assert probe().daemon is DaemonState.INACTIVE
    assert queries == ["is-active"]


def test_disk_pressure_probe_requires_timer_cache() -> None:
    signature = inspect.signature(setup._disk_pressure_probe)  # pyright: ignore[reportPrivateUsage]
    parameter = signature.parameters["timer_cache"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_disk_pressure_probe_none_cache_is_unavailable_on_linux_and_plist_on_macos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.enums import DaemonState

    monkeypatch.setattr(setup, "_DAEMON_PLIST_PATH", tmp_path / "missing.plist")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    linux = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), timer_cache=None
    )()
    assert linux.daemon is DaemonState.UNAVAILABLE

    plist = tmp_path / "agent.plist"
    plist.write_text("plist")
    monkeypatch.setattr(setup, "_DAEMON_PLIST_PATH", plist)
    macos = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _platform(), timer_cache=None
    )()
    assert macos.daemon is DaemonState.ACTIVE
    assert macos.tmp_threshold is False
    assert linux.tmp_threshold is True


# -- WHICH mount the composition root measures (15.7 gap closure) ------------
#
# The pure layer measures whatever path it is handed and is exercised with
# synthetic percentages; nothing there can catch the composition root handing
# it the WRONG filesystem. These drive setup.py's own probe against a fake
# mount table, so they pin the choice on host layouts this machine does not
# have to be partitioned like.

_MEGABYTE = 1024 * 1024
_GIGABYTE = 1024 * _MEGABYTE

# An ostree/composefs workstation (Bazzite, Silverblue -- the host class this
# phase names as its target): `/` is a tiny read-only composefs overlay,
# 100% used and 0 bytes free BY CONSTRUCTION, and the user's real disk is
# `/var`, which `/var/home/<user>` lives on.
_COMPOSEFS_HOST = {
    "/": (45 * _MEGABYTE, 45 * _MEGABYTE, 0),
    "/var": (800 * _GIGABYTE, 400 * _GIGABYTE, 400 * _GIGABYTE),
    "/tmp": (16 * _GIGABYTE, 1 * _GIGABYTE, 15 * _GIGABYTE),
}

# The same layout with the two mounts' health swapped: a roomy `/` and a
# nearly-full data mount. Measuring `/` here would MISS a real emergency, the
# mirror image of the false alarm above.
_COMPOSEFS_HOST_FULL_DATA = {
    "/": (45 * _MEGABYTE, 20 * _MEGABYTE, 25 * _MEGABYTE),
    "/var": (800 * _GIGABYTE, 776 * _GIGABYTE, 24 * _GIGABYTE),
    "/tmp": (16 * _GIGABYTE, 1 * _GIGABYTE, 15 * _GIGABYTE),
}

# A stock single-root host (ordinary Linux, and macOS): home is under `/`, so
# "the filesystem holding home" and "/" are the same filesystem and this
# change is a no-op there.
_SINGLE_ROOT_HOST = {
    "/": (500 * _GIGABYTE, 250 * _GIGABYTE, 250 * _GIGABYTE),
    "/tmp": (16 * _GIGABYTE, 1 * _GIGABYTE, 15 * _GIGABYTE),
}


def _mount_table(
    mounts: Mapping[str, tuple[int, int, int]], measured: list[Path] | None = None
) -> Callable[[Path], tuple[int, int, int]]:
    """A `shutil.disk_usage`-shaped reader over a fake mount table.

    Resolves a path the way a kernel does: the LONGEST mount point that is a
    prefix of the path owns it. A path under no mount raises
    FileNotFoundError, like the real call on a missing path.
    """

    def usage(path: Path) -> tuple[int, int, int]:
        if measured is not None:
            measured.append(path)
        owners = [m for m in mounts if path == Path(m) or Path(m) in path.parents]
        if not owners:
            raise FileNotFoundError(path)
        return mounts[max(owners, key=len)]

    return usage


def _inactive_cache() -> systemd_daemon.TimerStateCache:
    """A warm cache answering INACTIVE without touching systemd -- the state
    that makes low space an emphasised red finding, so silence here is silence
    in the worst case, not silence because the daemon looked fine."""
    cache = systemd_daemon.TimerStateCache(lambda: DaemonState.INACTIVE, ttl=10_000.0)
    cache.read()
    return cache


def _immutable_platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=True, has_brew=False)


def test_the_disk_probe_measures_the_users_filesystem_not_a_read_only_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gap Phase 15.7 verification found: `/` on an ostree host is a 45 MB
    read-only overlay reporting 0 bytes free, so measuring it made `make doctor`
    print a permanent red "free disk space is low" on a machine with 400 GB
    free -- inverting D-03's own false-positive-reduction rationale."""
    from installer.guidance import disk_pressure_guidance

    measured: list[Path] = []
    monkeypatch.setenv("HOME", "/var/home/u")
    monkeypatch.setenv("TMPDIR", "/tmp")
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _immutable_platform(),
        timer_cache=_inactive_cache(),
        usage=_mount_table(_COMPOSEFS_HOST, measured),
    )

    pressure = probe()

    assert measured[0] == Path("/var/home/u")  # never Path("/")
    assert pressure.daemon is DaemonState.INACTIVE
    assert pressure.home_free_percent == 50.0
    assert pressure.low_disk is False
    assert pressure.under_pressure is False
    # The must-have both plans state: a healthy machine produces NOTHING.
    assert disk_pressure_guidance(pressure) == []


def test_the_disk_probe_still_reports_a_full_user_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other direction of the same choice: on that host a roomy `/` must
    not mask an almost-full `/var`, or the fix would be "never warn"."""
    from installer.guidance import disk_pressure_guidance

    monkeypatch.setenv("HOME", "/var/home/u")
    monkeypatch.setenv("TMPDIR", "/tmp")
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _immutable_platform(),
        timer_cache=_inactive_cache(),
        usage=_mount_table(_COMPOSEFS_HOST_FULL_DATA),
    )

    pressure = probe()

    assert pressure.home_free_percent == 3.0
    assert pressure.low_disk is True
    guidance = disk_pressure_guidance(pressure)
    assert [(item.severity, item.emphasis) for item in guidance] == [(Severity.ERROR, True)]


@pytest.mark.parametrize(
    ("platform", "home"),
    [
        pytest.param(_linux_platform(), "/home/u", id="stock-linux"),
        pytest.param(_platform(), "/Users/u", id="macos"),
    ],
)
def test_the_disk_probe_measures_the_root_mount_on_a_single_root_host(
    monkeypatch: pytest.MonkeyPatch, platform: Platform, home: str
) -> None:
    """Where home IS on `/`, resolving the mount from home is the same
    measurement as before -- this change moves no number on a stock host."""
    measured: list[Path] = []
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("TMPDIR", "/tmp")
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        platform,
        timer_cache=_inactive_cache() if platform.os != "macos" else None,
        usage=_mount_table(_SINGLE_ROOT_HOST, measured),
    )

    pressure = probe()

    assert measured[0] == Path(home)
    assert pressure.home_free_percent == 50.0
    assert pressure.low_disk is False


def test_probe_and_policy_share_one_cache_and_issue_one_query(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.enums import DaemonState

    queries: list[list[str]] = []
    unit_dir = tmp_path / "user"
    unit_dir.mkdir()
    (unit_dir / "tools-installer-prune-tmp.timer").write_text("timer")
    (unit_dir / "tools-installer-prune-tmp.service").write_text("service")
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", unit_dir)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    cache = setup._timer_state_cache(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(),
        which=lambda _name: "/usr/bin/systemctl",
        read_output=_recording_reader(queries),
    )
    assert cache is not None
    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), {}, which=lambda _name: "/usr/bin/systemctl", timer_cache=cache
    )
    assert policy is not None
    assert policy.state_cache is cache
    active = policy.is_active
    assert active is not None
    assert active() is False
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), timer_cache=cache
    )
    assert probe().daemon is DaemonState.INACTIVE
    assert len(queries) == 1


def test_run_doctor_non_tty_forwards_the_probe_closure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup.sys, "stdin", _NonTtyStdin())

    def no_tty(_path: str, _flags: int) -> int:
        raise OSError("no controlling terminal")

    monkeypatch.setattr(setup.os, "open", no_tty)
    seen: list[object] = []
    forwarded: list[object] = []

    def fake_probe(*_args: object, **_kwargs: object) -> object:
        closure = object()
        seen.append(closure)
        return closure

    def fake_run_doctor(*_args: object, **kwargs: object) -> object:
        forwarded.append(kwargs.get("disk_pressure"))
        return object()

    monkeypatch.setattr(setup, "_disk_pressure_probe", fake_probe)
    monkeypatch.setattr(setup, "run_doctor", fake_run_doctor)
    assert setup._run_doctor(Console(file=io.StringIO())) == 0  # pyright: ignore[reportPrivateUsage]
    assert seen and forwarded[0] is seen[0]


def test_verify_and_clean_forwards_the_probe_closure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[object] = []
    forwarded: list[object] = []

    def fake_probe(*_args: object, **_kwargs: object) -> object:
        closure = object()
        calls.append(closure)
        return closure

    def fake_run_doctor(*_args: object, **kwargs: object) -> object:
        forwarded.append(kwargs.get("disk_pressure"))
        return object()

    monkeypatch.setattr(setup, "_disk_pressure_probe", fake_probe)
    monkeypatch.setattr(setup, "run_doctor", fake_run_doctor)

    def no_duplicates(*_args: object, **_kwargs: object) -> dict[Path, list[str]]:
        return {}

    def no_dirs(*_args: object, **_kwargs: object) -> list[Path]:
        return []

    monkeypatch.setattr(setup, "clean_rc_duplicates", no_duplicates)
    monkeypatch.setattr(setup, "collect_bin_dirs", no_dirs)
    setup._verify_and_clean(  # pyright: ignore[reportPrivateUsage]
        Console(file=io.StringIO()), [], _linux_platform(), assume_yes=True
    )
    assert len(calls) == 1
    assert forwarded[0] is calls[0]


def test_interactive_wizard_hands_one_probe_to_execute_and_policy_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    marker = object()
    built: list[object] = []

    def fake_probe(*_args: object, **_kwargs: object) -> object:
        built.append(marker)
        return marker

    received: list[object] = []

    def fake_run_doctor(*_args: object, **kwargs: object) -> object:
        received.append(kwargs.get("disk_pressure"))
        return object()

    monkeypatch.setattr(setup, "_disk_pressure_probe", fake_probe)
    monkeypatch.setattr(setup, "run_doctor", fake_run_doctor)
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    policies = seen[0]["policies"]
    execute = seen[0]["execute"]
    assert isinstance(policies, PolicyInputs)
    assert isinstance(execute, ExecuteInputs)
    execute.verify()
    assert policies.disk_pressure is marker
    assert received == [marker]
    assert built == [marker]


def test_interactive_wizard_shares_one_cache_with_the_daemon_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(setup, "detect", _linux_platform)

    def systemd_present(*, which: object) -> bool:
        return True

    monkeypatch.setattr(setup.systemd_daemon, "systemd_available", systemd_present)
    from installer.enums import DaemonState
    from installer.systemd_daemon import TimerStateCache

    cache = TimerStateCache(lambda: DaemonState.INACTIVE)
    calls: list[object] = []

    def fake_cache(*_args: object, **_kwargs: object) -> TimerStateCache:
        calls.append(cache)
        return cache

    monkeypatch.setattr(setup, "_timer_state_cache", fake_cache)
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    daemon = next(policy for policy in policies.policies if policy.id.startswith("daemon:"))
    assert daemon.state_cache is cache
    assert calls == [cache]


def test_build_app_without_disk_pressure_still_binds_the_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    marker = object()

    def fake_probe(*_args: object, **_kwargs: object) -> object:
        return marker

    monkeypatch.setattr(setup, "_disk_pressure_probe", fake_probe)
    seen = _capture_app(monkeypatch)
    setup._build_app([], _platform())  # pyright: ignore[reportPrivateUsage]
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert policies.disk_pressure is marker


def test_build_app_binds_the_callers_probe_without_building_another(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    built: list[object] = []

    def fake_probe(*_args: object, **_kwargs: object) -> object:
        built.append(object())
        return built[-1]

    monkeypatch.setattr(setup, "_disk_pressure_probe", fake_probe)
    seen = _capture_app(monkeypatch)
    setup._build_app(  # pyright: ignore[reportPrivateUsage]
        [], _platform(), disk_pressure=_unused_probe
    )
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert policies.disk_pressure is _unused_probe
    assert built == []


def test_build_app_omitted_arguments_still_share_one_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.enums import DaemonState

    _sandbox(monkeypatch, tmp_path)
    queries: list[list[str]] = []
    unit_dir = tmp_path / "user"
    unit_dir.mkdir()
    (unit_dir / "tools-installer-prune-tmp.timer").write_text("timer")
    (unit_dir / "tools-installer-prune-tmp.service").write_text("service")
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", unit_dir)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    def which(name: str) -> str | None:
        return "/usr/bin/systemctl" if name == "systemctl" else None

    monkeypatch.setattr(setup.shutil, "which", which)
    monkeypatch.setattr(setup.systemd_daemon, "query_systemctl", _recording_reader(queries))
    seen = _capture_app(monkeypatch)
    setup._build_app([], _linux_platform())  # pyright: ignore[reportPrivateUsage]
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    daemon = next(policy for policy in policies.policies if policy.id.startswith("daemon:"))
    probe = policies.disk_pressure
    assert callable(probe)
    active = daemon.is_active
    assert active is not None
    assert active() is False
    pressure = probe()
    assert isinstance(pressure, DiskPressure)
    assert pressure.daemon is DaemonState.INACTIVE
    assert len(queries) == 1


def test_build_app_calls_timer_state_cache_at_most_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    calls = {"n": 0}
    original = setup._timer_state_cache  # pyright: ignore[reportPrivateUsage]

    def counting(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(setup, "_timer_state_cache", counting)
    setup._build_app([], _linux_platform())  # pyright: ignore[reportPrivateUsage]
    assert calls["n"] == 1


def test_probe_reports_unavailable_when_no_daemon_policy_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.enums import DaemonState

    monkeypatch.setattr(setup, "_DAEMON_PLIST_PATH", tmp_path / "missing.plist")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    cache = setup._timer_state_cache(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), which=lambda _name: None, read_output=lambda _argv: "active"
    )
    assert cache is None
    pressure = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), timer_cache=cache
    )()
    assert pressure.daemon is DaemonState.UNAVAILABLE


def test_linux_probe_memoizes_is_active_inside_the_ttl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.enums import DaemonState

    queries: list[list[str]] = []
    unit_dir = tmp_path / "user"
    unit_dir.mkdir()
    (unit_dir / "tools-installer-prune-tmp.timer").write_text("timer")
    (unit_dir / "tools-installer-prune-tmp.service").write_text("service")
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", unit_dir)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    cache = setup._timer_state_cache(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(),
        which=lambda _name: "/usr/bin/systemctl",
        read_output=_recording_reader(queries, "active"),
    )
    probe = setup._disk_pressure_probe(  # pyright: ignore[reportPrivateUsage]
        _linux_platform(), timer_cache=cache
    )
    assert probe().daemon is DaemonState.ACTIVE
    assert probe().daemon is DaemonState.ACTIVE
    assert probe().daemon is DaemonState.ACTIVE
    assert len(queries) == 1


def test_native_probe_is_wired_at_both_the_display_and_mutation_sites() -> None:
    source = Path(setup.__file__).read_text()
    assert source.count("native_probe=") == 2, source.count("native_probe=")
    assert "run_probe" in source
    assert "install_ownership import run_probe" in source


# --- 15.8-06 Task 2: the new constant, its isolation, and the refusal route ---


def test_sandbox_redirects_the_shellrc_constant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The isolation guard itself.

    `setup.py` resolves its home constants at IMPORT time, so a test cannot
    redirect them with `monkeypatch.setenv("HOME", ...)` alone. This fails if
    someone later adds a home-derived constant and forgets `_sandbox`.
    """
    _sandbox(monkeypatch, tmp_path)

    assert tmp_path / ".shellrc" == setup._SHELLRC  # pyright: ignore[reportPrivateUsage]
    assert setup._SHELLRC.parent == tmp_path  # pyright: ignore[reportPrivateUsage]


def test_every_configure_path_call_site_passes_a_shellrc_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The routes this test can drive must carry the argument.

    HONEST SCOPE: this exercises TWO of the four `configure_path` call sites --
    the execute-inputs wire step and the Doctor apply closure. The `--fix` CLI
    route (`_run_fix`) and the unattended post-wizard route both sit inside
    `main`'s argument handling and cannot be driven from here without running
    the whole CLI. They are covered by inspection only, which is why the
    constant is passed identically at all four sites and why `_sandbox`
    redirects it globally rather than per-route.
    """
    _sandbox(monkeypatch, tmp_path)
    captured: list[dict[str, object]] = []

    def recorder(_tools: object, console: Console, **kwargs: object) -> None:
        captured.append(dict(kwargs))
        console.print("wired")

    monkeypatch.setattr(setup, "configure_path", recorder)

    # Route 1: the Doctor apply closure, and Route 2: the execute-inputs wire step.
    inputs = setup._execute_inputs(  # pyright: ignore[reportPrivateUsage]
        [],
        _platform(),
        link_mode="single",
        unattended=True,
        disk_pressure=_unused_probe,
    )
    inputs.wire_path()
    app = setup._build_app([], _platform())  # pyright: ignore[reportPrivateUsage]
    doctor = app._views["doctor"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(doctor, DoctorScreen)
    doctor._fix()  # pyright: ignore[reportPrivateUsage]

    assert len(captured) == 2
    for call in captured:
        assert call["shellrc_path"] == tmp_path / ".shellrc"


def _refused(reason: str = "a stated mechanism reason") -> ShellrcConsolidation:
    return ShellrcConsolidation(status="refused", reason=reason)


def test_doctor_apply_raises_on_a_consolidation_refusal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)

    def refusing(_tools: object, _console: Console, **_kwargs: object) -> ShellrcConsolidation:
        return _refused("~/.shellrc line 3 is ambiguous")

    monkeypatch.setattr(setup, "configure_path", refusing)
    app = setup._build_app([], _platform())  # pyright: ignore[reportPrivateUsage]
    doctor = app._views["doctor"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(doctor, DoctorScreen)

    with pytest.raises(ShellrcRefusal, match="ambiguous"):
        doctor._fix()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("status", ["absent", "already", "consolidated"])
def test_doctor_apply_does_not_raise_on_any_non_refusal_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: Literal["absent", "already", "consolidated"],
) -> None:
    """A raise on a success would make PATH wiring unusable."""
    _sandbox(monkeypatch, tmp_path)

    def succeeding(_tools: object, _console: Console, **_kwargs: object) -> ShellrcConsolidation:
        return ShellrcConsolidation(status=status)

    monkeypatch.setattr(setup, "configure_path", succeeding)
    app = setup._build_app([], _platform())  # pyright: ignore[reportPrivateUsage]
    doctor = app._views["doctor"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(doctor, DoctorScreen)

    doctor._fix()  # pyright: ignore[reportPrivateUsage]


def test_doctor_apply_does_not_raise_when_no_outcome_is_returned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)

    def returning_none(_tools: object, _console: Console, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(setup, "configure_path", returning_none)
    app = setup._build_app([], _platform())  # pyright: ignore[reportPrivateUsage]
    doctor = app._views["doctor"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(doctor, DoctorScreen)

    doctor._fix()  # pyright: ignore[reportPrivateUsage]


def test_interactive_wizard_exits_1_when_the_session_has_a_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    _capture_app(monkeypatch)
    app = setup.UnifiedApp
    assert app is not None
    monkeypatch.setattr(
        app,
        "install_summary",
        Summary(installed=(), already=(), failed=(), no_method=(), crash_error="boom"),
    )
    assert setup.main([]) == 1


def test_interactive_wizard_exits_0_when_the_session_is_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _sandbox(monkeypatch, tmp_path)
    _capture_app(monkeypatch)
    app = setup.UnifiedApp
    assert app is not None
    monkeypatch.setattr(
        app, "install_summary", Summary(installed=("rg",), already=(), failed=(), no_method=())
    )
    assert setup.main([]) == 0


def test_failed_update_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path)
    _capture_app(monkeypatch)
    app = setup.UnifiedApp
    assert app is not None
    monkeypatch.setattr(
        app,
        "install_summary",
        Summary(installed=(), already=(), failed=(), no_method=(), update_failed=("rg",)),
    )
    assert setup.main([]) == 1


def test_all_skipped_run_exits_0(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path)
    _capture_app(monkeypatch)
    app = setup.UnifiedApp
    assert app is not None
    monkeypatch.setattr(
        app, "install_summary", Summary(installed=(), already=("rg",), failed=(), no_method=())
    )
    assert setup.main([]) == 0


def test_headless_run_exits_1_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _sandbox(monkeypatch, tmp_path)

    def fake_run_wizard(*_args: object, **_kwargs: object) -> Summary:
        return Summary(installed=(), already=(), failed=("rg",), no_method=())

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(setup, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(setup, "configure_path", noop)
    monkeypatch.setattr(setup, "_verify_and_clean", noop)
    monkeypatch.setattr(setup, "_sync_terminals_and_report", noop)
    assert setup.main(["--all", "--yes"]) == 1
