import ast
import os
from pathlib import Path

import pytest

from installer import env_redirect, locations, systemd_daemon
from installer.locations import (
    applications_dir,
    bin_dir,
    drop_project_venv_from_path,
    ensure_dir,
    opt_dir,
    prepend_path,
    xdg_config_base,
)
from installer.model import load_tools
from installer.ownership import ManagerInventory, owner_dirs
from installer.platform import Platform
from tests.state_doubles import seeded_service
from tests.test_registry import REGISTRY

ROOT = Path(__file__).resolve().parent.parent
SETUP_PY = ROOT / "setup.py"
# Captured at import, before the suite points HOME at a scratch dir (G28).
_REAL_HOME = Path.home()

# --- default bin dir sandbox (plan 19-01, checker W2) -------------------------


def test_suite_sandbox_redirects_the_default_bin_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without any redirect of its own, the suite's default bin dir is a scratch
    dir under pytest's base temp, never the developer's real ~/.local/bin. A
    test that redirects HOME still gets HOME/.local/bin, and a declared dir is
    never touched either way."""
    # Through the module attribute, so the conftest sandbox patch applies.
    default = locations.bin_dir(None)
    assert not default.is_relative_to(_REAL_HOME)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir(None) == tmp_path / ".local" / "bin"
    assert bin_dir("/opt/x/bin") == Path("/opt/x/bin")


def test_suite_home_is_a_per_test_scratch_dir(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Every test's HOME is a scratch dir under pytest's base temp, never the
    developer's home, whichever of the three home readers asks (G28)."""
    home = Path.home()
    assert home == Path(os.environ["HOME"]) == Path(os.path.expanduser("~"))
    assert home.is_dir()
    assert home.is_relative_to(tmp_path_factory.getbasetemp())
    assert not home.is_relative_to(_REAL_HOME)


def test_inherited_location_overrides_are_cleared(tmp_path: Path) -> None:
    """RR-05: an inherited PNPM_HOME, VOLTA_HOME, XDG_CONFIG_HOME or
    XDG_DATA_HOME from the developer's shell never reaches a test. Cleared,
    owner prefixes fall back under the scratch HOME."""
    for name in ("PNPM_HOME", "VOLTA_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        assert name not in os.environ
    dirs = owner_dirs(
        inventory=ManagerInventory(None, None, None, None, None),
        managed_bin_dir=tmp_path / "managed",
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
    )
    assert dirs["pnpm"][0].is_relative_to(Path.home())
    assert dirs["volta"][0].is_relative_to(Path.home())


def test_registry_pass_reads_declared_locations_from_the_scratch_home(tmp_path: Path) -> None:
    """A real-registry refresh expands `~/.sdkman/...` through HOME. An empty
    scratch home is not SDKMAN; a java planted there is, which is only possible
    if `~` expanded into the scratch dir and not the developer's home (G28)."""
    assert not Path.home().is_relative_to(_REAL_HOME)
    java = next(tool for tool in load_tools(REGISTRY) if tool.id == "java")
    empty = seeded_service(
        [java], cache_path=tmp_path / "before.json", home=tmp_path / "skill-home"
    )
    before = empty.state_of("java")
    assert before is not None
    assert before.ownership is not None
    assert before.ownership.owner != "sdkman"

    planted = Path.home() / ".sdkman" / "candidates" / "java" / "current" / "bin" / "java"
    planted.parent.mkdir(parents=True)
    planted.write_bytes(b"#!/bin/sh\n")
    planted.chmod(0o755)
    after_service = seeded_service(
        [java], cache_path=tmp_path / "after.json", home=tmp_path / "skill-home"
    )
    after = after_service.state_of("java")
    assert after is not None
    assert after.ownership is not None
    assert after.ownership.owner == "sdkman"
    assert "managed by SDKMAN" in after.reasons


# --- xdg_config_base (lane-2 MEDIUM-01) --------------------------------------


def test_xdg_config_base_honours_an_absolute_xdg_config_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    xdg = tmp_path / "xdgconf"
    assert xdg_config_base(home, {"XDG_CONFIG_HOME": str(xdg)}) == xdg


def test_xdg_config_base_falls_back_to_home_config_when_unset_or_empty(tmp_path: Path) -> None:
    home = tmp_path / "home"
    assert xdg_config_base(home, {}) == home / ".config"
    assert xdg_config_base(home, {"XDG_CONFIG_HOME": ""}) == home / ".config"


@pytest.mark.parametrize("raw", ["relative/config", ".config", ".", "~/config"])
def test_xdg_config_base_ignores_a_non_absolute_xdg_config_home(tmp_path: Path, raw: str) -> None:
    """The XDG base-directory spec says a non-absolute value must be ignored.
    Honouring one would resolve every derived path against whatever cwd the
    process happens to have. A leading "~" is NOT expanded here either: the
    spec has no tilde rule, and Path("~/config") is not absolute.
    """
    home = tmp_path / "home"
    assert xdg_config_base(home, {"XDG_CONFIG_HOME": raw}) == home / ".config"


def test_both_xdg_config_consumers_resolve_through_the_one_shared_base(tmp_path: Path) -> None:
    """Lane-2 MEDIUM-01: systemd_daemon.user_unit_dir and
    env_redirect.environment_d_dir each carried their own copy of the
    "absolute or fall back to ~/.config" rule. Both now derive from
    locations.xdg_config_base, so a change to the rule can never land in one
    and miss the other -- exercised for BOTH functions in one session, which
    is exactly what no test did before.
    """
    home = tmp_path / "home"
    absolute = tmp_path / "xdgconf"

    for environ in (
        {},
        {"XDG_CONFIG_HOME": ""},
        {"XDG_CONFIG_HOME": str(absolute)},
        {"XDG_CONFIG_HOME": "relative/config"},
        {"XDG_CONFIG_HOME": "."},
    ):
        base = xdg_config_base(home, environ)
        assert systemd_daemon.user_unit_dir(home, environ) == base / "systemd" / "user"
        assert env_redirect.environment_d_dir(home, environ) == base / "environment.d"

    # And the relative case really is ignored by both, not merely consistent.
    relative = {"XDG_CONFIG_HOME": "relative/config"}
    assert systemd_daemon.user_unit_dir(home, relative) == home / ".config" / "systemd" / "user"
    assert env_redirect.environment_d_dir(home, relative) == home / ".config" / "environment.d"


def test_bin_dir_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir(None) == tmp_path / ".local" / "bin"


def test_bin_dir_expands_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir("~/.local/bin") == tmp_path / ".local" / "bin"


def test_bin_dir_absolute_path_unchanged():
    assert bin_dir("/opt/tools/bin") == Path("/opt/tools/bin")


def test_bin_dir_bare_tilde_is_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert bin_dir("~") == tmp_path


def test_ensure_dir_creates(tmp_path: Path):
    target = tmp_path / "a" / "b"
    result = ensure_dir(target)
    assert result == target
    assert target.is_dir()


def test_prepend_path_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", "/usr/bin")
    prepend_path(tmp_path)
    prepend_path(tmp_path)  # second call must not duplicate
    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0] == str(tmp_path)
    assert parts.count(str(tmp_path)) == 1


def test_prepend_path_drops_empty_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", "")
    prepend_path(tmp_path)
    assert os.environ["PATH"] == str(tmp_path)  # no trailing separator


def test_ensure_dir_idempotent(tmp_path: Path):
    target = tmp_path / "x" / "y"
    ensure_dir(target)
    assert ensure_dir(target) == target  # second call must not raise
    assert target.is_dir()


def test_opt_dir_is_under_local_opt():
    assert opt_dir("fd") == Path.home() / ".local" / "opt" / "fd"


def test_applications_dir_is_home_applications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert applications_dir() == tmp_path / "Applications"


def test_rc_paths_for_mode_centralized_and_split_wire_both(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import rc_paths_for_mode

    monkeypatch.setenv("HOME", str(tmp_path))
    both = [tmp_path / ".zshrc", tmp_path / ".bashrc"]
    assert rc_paths_for_mode("centralized", "/bin/zsh") == both
    assert rc_paths_for_mode("split", "/bin/bash") == both


def test_rc_paths_for_mode_single_follows_the_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import rc_paths_for_mode

    monkeypatch.setenv("HOME", str(tmp_path))
    assert rc_paths_for_mode("single", "/bin/zsh") == [tmp_path / ".zshrc"]
    assert rc_paths_for_mode("single", "/usr/local/bin/bash") == [tmp_path / ".bashrc"]
    # undetectable shell -> wire both rather than guess wrong
    assert rc_paths_for_mode("single", "/bin/fish") == [
        tmp_path / ".zshrc",
        tmp_path / ".bashrc",
    ]


def test_ban_rc_paths_follow_the_path_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import ban_rc_paths

    monkeypatch.setenv("HOME", str(tmp_path))
    # centralized/single: aliases live in the one managed file
    assert ban_rc_paths("centralized", "/bin/zsh") == [tmp_path / ".myshellrc"]
    assert ban_rc_paths("single", "/bin/zsh") == [tmp_path / ".myshellrc"]
    # split: no ~/.myshellrc exists, write into each rc directly
    assert ban_rc_paths("split", "/bin/zsh") == [tmp_path / ".zshrc", tmp_path / ".bashrc"]


def test_all_ban_rc_paths_cover_every_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from installer.locations import all_ban_rc_paths

    monkeypatch.setenv("HOME", str(tmp_path))
    # removal sweeps every file any mode could have written to
    assert all_ban_rc_paths() == [
        tmp_path / ".myshellrc",
        tmp_path / ".zshrc",
        tmp_path / ".bashrc",
    ]


def test_zshrc_path_defaults_to_home_when_zdotdir_is_unset(tmp_path: Path) -> None:
    from installer.locations import zshrc_path

    assert zshrc_path(tmp_path, {}) == tmp_path / ".zshrc"
    assert zshrc_path(tmp_path, {"ZDOTDIR": ""}) == tmp_path / ".zshrc"


def test_zshrc_path_follows_an_existing_zdotdir(tmp_path: Path) -> None:
    from installer.locations import zshrc_path

    zdotdir = tmp_path / "config" / "zsh"
    zdotdir.mkdir(parents=True)
    assert zshrc_path(tmp_path, {"ZDOTDIR": str(zdotdir)}) == zdotdir / ".zshrc"


def test_zshrc_path_ignores_a_zdotdir_that_is_not_a_directory(tmp_path: Path) -> None:
    from installer.locations import zshrc_path

    # A stale or typo'd ZDOTDIR must not point writes at a path that does not
    # exist; fall back to the file zsh would read without it.
    assert zshrc_path(tmp_path, {"ZDOTDIR": str(tmp_path / "gone")}) == tmp_path / ".zshrc"


def test_rc_paths_and_ban_sweep_follow_zdotdir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import all_ban_rc_paths, ban_rc_paths, rc_paths_for_mode

    monkeypatch.setenv("HOME", str(tmp_path))
    zdotdir = tmp_path / "zsh"
    zdotdir.mkdir()
    monkeypatch.setenv("ZDOTDIR", str(zdotdir))
    # The ban aliases and the plugins edit must agree on which .zshrc is real.
    assert rc_paths_for_mode("centralized", "/bin/zsh") == [
        zdotdir / ".zshrc",
        tmp_path / ".bashrc",
    ]
    assert rc_paths_for_mode("single", "/bin/zsh") == [zdotdir / ".zshrc"]
    assert ban_rc_paths("split", "/bin/zsh") == [zdotdir / ".zshrc", tmp_path / ".bashrc"]
    assert all_ban_rc_paths() == [
        tmp_path / ".myshellrc",
        zdotdir / ".zshrc",
        tmp_path / ".bashrc",
    ]


def test_path_scan_covers_the_login_files_the_write_set_omits() -> None:
    """The structural duplicate the Doctor must explain lives in login files
    this installer never writes to, so the scan set must be wider than the
    write set or the finding stays unexplained."""
    from installer.locations import all_ban_rc_paths, path_scan_rc_paths

    scanned = {p.name for p in path_scan_rc_paths()}
    assert {".bash_profile", ".profile"} <= scanned
    assert {p.name for p in all_ban_rc_paths()} <= scanned


def test_path_scan_includes_zsh_startup_files_and_sorted_bashrc_d(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import path_scan_rc_paths

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ZDOTDIR", raising=False)
    snippets = tmp_path / ".bashrc.d"
    snippets.mkdir()
    (snippets / "b.sh").write_text("")
    (snippets / "a.sh").write_text("")
    (snippets / "nested").mkdir()
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    scanned = path_scan_rc_paths()
    assert tmp_path / ".zshenv" in scanned
    assert tmp_path / ".zlogin" in scanned
    assert tmp_path / ".zprofile" in scanned
    assert [p.name for p in scanned if p.parent == snippets] == ["a.sh", "b.sh"]
    assert before == sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))


def test_path_scan_missing_bashrc_d_adds_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import path_scan_rc_paths

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ZDOTDIR", raising=False)
    scanned = path_scan_rc_paths()
    assert all(".bashrc.d" not in p.parts for p in scanned)


def test_path_scan_honors_zdotdir_for_zsh_startup_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import path_scan_rc_paths

    monkeypatch.setenv("HOME", str(tmp_path))
    zdotdir = tmp_path / "zd"
    zdotdir.mkdir()
    monkeypatch.setenv("ZDOTDIR", str(zdotdir))
    scanned = path_scan_rc_paths()
    for name in (".zshrc", ".zprofile", ".zshenv", ".zlogin"):
        assert zdotdir / name in scanned
        assert tmp_path / name not in scanned


def _home_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.delenv("ZDOTDIR", raising=False)


def test_path_scan_skips_an_unreadable_bashrc_d_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import path_scan_rc_paths

    _home_is(tmp_path, monkeypatch)
    snippets = tmp_path / ".bashrc.d"
    snippets.mkdir()
    (snippets / "a.sh").write_text("")
    (snippets / "b.sh").write_text("")
    real_is_file = Path.is_file

    def raising_is_file(self: Path) -> bool:
        if self.name == "b.sh":
            raise PermissionError(self)
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", raising_is_file)
    scanned = path_scan_rc_paths()
    assert [p.name for p in scanned if p.parent == snippets] == ["a.sh"]


def test_path_scan_bashrc_d_order_unchanged_without_a_failing_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from installer.locations import path_scan_rc_paths

    _home_is(tmp_path, monkeypatch)
    snippets = tmp_path / ".bashrc.d"
    snippets.mkdir()
    (snippets / "b.sh").write_text("")
    (snippets / "a.sh").write_text("")
    (snippets / "nested").mkdir()
    scanned = path_scan_rc_paths()
    assert [p.name for p in scanned if p.parent == snippets] == ["a.sh", "b.sh"]


def test_drop_project_venv_from_path_removes_only_the_project_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    other = tmp_path / "other-project"
    root.mkdir()
    other.mkdir()
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "lib" / "x").mkdir(parents=True)
    (other / ".venv" / "bin").mkdir(parents=True)
    (root / "bin").mkdir()
    original = os.pathsep.join(
        [
            str(root / ".venv" / "bin"),
            "/usr/local/bin",
            str(root / ".venv" / "lib" / "x"),
            str(other / ".venv" / "bin"),
            str(root / "bin"),
        ]
    )
    monkeypatch.setenv("PATH", original)
    drop_project_venv_from_path(root)
    assert os.environ["PATH"] == os.pathsep.join(
        ["/usr/local/bin", str(other / ".venv" / "bin"), str(root / "bin")]
    )


def test_drop_project_venv_from_path_leaves_path_unchanged_without_a_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    original = os.pathsep.join(["", "/usr/local/bin", ""])
    monkeypatch.setenv("PATH", original)
    drop_project_venv_from_path(root)
    assert os.environ["PATH"] == original


def test_setup_entry_point_drops_the_project_venv_before_main() -> None:
    tree = ast.parse(SETUP_PY.read_text())
    main_block: ast.If | None = None
    main_func: ast.FunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Name) and left.id == "__name__":
                main_block = node
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_func = node
    assert main_block is not None
    assert main_func is not None
    first = main_block.body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
    call = first.value
    assert isinstance(call.func, ast.Name) and call.func.id == "drop_project_venv_from_path"
    assert len(call.args) == 1
    source = ast.unparse(call.args[0])
    assert "__file__" in source
    for node in ast.walk(main_func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "drop_project_venv_from_path"
