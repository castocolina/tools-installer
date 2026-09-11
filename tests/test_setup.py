import importlib
import io
import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

import pytest
from rich.console import Console

import setup
from installer import pnpm_globals
from installer.app import UninstallDecision
from installer.guards import install_shims
from installer.model import Method, Tool
from installer.platform import Platform
from installer.pnpm_globals import NodeGlobalsReport, NodeInstallPolicy
from installer.policy import Policy
from installer.session import Summary
from installer.shellrc import write_myshellrc
from installer.tweaks import BUNDLES
from installer.uninstall import SweepResult
from installer.wizard_app import DoctorScreen, PolicyInputs, UninstallInputs

# Aliased once, matching tests/test_daemon.py's convention for pinning a
# private composition-root function under test.
_has_controlling_tty = setup._has_controlling_tty  # pyright: ignore[reportPrivateUsage]
_stdin_on_tty = setup._stdin_on_tty  # pyright: ignore[reportPrivateUsage]


class _DummyApp:
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


def test_main_fix_interactive_without_link_mode_opens_doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_calls: list[dict[str, str]] = []

    def fake_load_tools(_registry: object) -> list[Tool]:
        return []

    def fake_detect() -> Platform:
        return _platform()

    def fake_resolve_link_mode(_option: str | None) -> str:
        return "single"

    def fake_build_app(
        tools: list[Tool],
        platform: Platform,
        *,
        initial_view: str = "system",
        link_mode: str = "centralized",
    ) -> _DummyApp:
        build_calls.append(
            {
                "initial_view": initial_view,
                "link_mode": link_mode,
            }
        )
        return _DummyApp()

    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", fake_detect)
    monkeypatch.setattr(setup, "_resolve_link_mode", fake_resolve_link_mode)
    monkeypatch.setattr(setup, "_build_app", fake_build_app)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())

    console = Console(file=io.StringIO(), width=100, no_color=True)
    monkeypatch.setattr(setup, "Console", lambda: console)

    assert setup.main(["--fix"]) == 0
    assert build_calls == [{"initial_view": "doctor", "link_mode": "single"}]


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


def _capture_app(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Stand in for UnifiedApp so _build_app runs for real without a terminal.

    The captured kwargs are the wire under test: what the composition root
    actually handed the views, not what its source text says it did.
    """
    seen: list[dict[str, object]] = []

    class _App:
        def __init__(self, *_args: object, **kwargs: object) -> None:
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
    monkeypatch.setattr(setup, "_ZSHRC", tmp_path / ".zshrc")
    monkeypatch.setattr(setup, "_RC_PATHS", [tmp_path / ".zshrc", tmp_path / ".bashrc"])
    monkeypatch.setattr(setup, "_DAEMON_PLIST_PATH", tmp_path / "LaunchAgents" / "daemon.plist")
    monkeypatch.setattr(setup, "_DAEMON_LOG_PATH", tmp_path / "Logs" / "prune-daemon.log")
    monkeypatch.setattr(setup, "_DAEMON_SCRIPT_PATH", tmp_path / "scripts" / "prune-user-tmpdir.sh")
    monkeypatch.setattr(setup, "_DAEMON_STATE_PATH", tmp_path / ".myshellrc")
    monkeypatch.setattr(setup, "load_tools", _no_tools)
    monkeypatch.setattr(setup, "load_categories", _no_categories)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup.sys, "stdin", _FakeStdin())


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
    assert ids[-1] == "daemon:prune-tmpdir"
    assert ids[-2] == "omz-plugins"
    assert all(policy_id.startswith("tweak:") for policy_id in ids[1:-2])
    assert len(ids) > 3


def test_daemon_policy_is_absent_on_linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ROADMAP SC#2: the daemon is invisible/inert on any non-macOS platform."""
    _sandbox(monkeypatch, tmp_path)
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    monkeypatch.setattr(setup, "detect", lambda: linux)
    seen = _capture_app(monkeypatch)
    assert setup.main(["--uninstall"]) == 0
    policies = seen[0]["policies"]
    assert isinstance(policies, PolicyInputs)
    assert not any(policy.id.startswith("daemon:") for policy in policies.policies)


def test_build_daemon_policy_returns_none_off_macos() -> None:
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    # _build_daemon_policy is setup.py's own private composition-root helper;
    # the plan's own <behavior> requires testing it directly (construction
    # must never raise on a bad environment) -- there is no public seam that
    # exercises this without going through the full main()/_build_app flow.
    assert setup._build_daemon_policy(linux, {}) is None  # pyright: ignore[reportPrivateUsage]


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
    #14): only the default/no-flag path (_select_catalog's own call site --
    the genuine, normal interactive `make setup` wizard flow) ever wires a
    real daemon_default callback into UnifiedApp. `--doctor` (read-only,
    Makefile:19), `--uninstall`, and `--guard`'s interactive Policies view
    must never auto-apply -- proven against _capture_app's own CAPTURED
    kwargs, not merely that an injected callback was never invoked
    (11-REVIEWS.md cycle 2 finding #20)."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    monkeypatch.setattr(setup, "_resolve_link_mode", _fake_resolve_link_mode_centralized)

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


def _fake_resolve_link_mode_split(_option: str | None) -> str:
    return "split"


def _fake_resolve_link_mode_centralized(_option: str | None) -> str:
    return "centralized"


def test_the_normal_interactive_flow_wires_split_mode_myshellrc_sourcing_before_catalog_opens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The phase's own primary, most-used entry point (no flags at all) must
    also thread the real link mode into the catalog/Policies UnifiedApp
    instance BEFORE it opens — not only the --guard shortcut."""
    _sandbox(monkeypatch, tmp_path)
    seen = _capture_app(monkeypatch)
    monkeypatch.setattr(setup, "_resolve_link_mode", _fake_resolve_link_mode_split)
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
    monkeypatch.setattr(setup, "_resolve_link_mode", _fake_resolve_link_mode_centralized)
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

    def fake_resolve_link_mode(_option: str | None) -> str:
        return "centralized"

    def noop(*_args: object, **_kwargs: object) -> None:
        return None

    def fake_render_troubleshooting(_console: object) -> None:
        rendered.append("shown")

    console = Console(file=io.StringIO(), width=100, no_color=True)
    monkeypatch.setattr(setup, "load_tools", fake_load_tools)
    monkeypatch.setattr(setup, "detect", _platform)
    monkeypatch.setattr(setup, "load_categories", fake_load_categories)
    monkeypatch.setattr(setup, "run_wizard", fake_run_wizard)
    monkeypatch.setattr(setup, "_resolve_link_mode", fake_resolve_link_mode)
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
    monkeypatch.setattr(setup, "_resolve_link_mode", _fake_resolve_link_mode_centralized)
    seen = _capture_app(monkeypatch)
    assert setup.main([]) == 0
    unavailable = seen[0]["unavailable"]
    assert isinstance(unavailable, dict)
    assert unavailable["apt-upgrade"] is True
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
