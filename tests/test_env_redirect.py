"""D-04 cache redirect: one declaration, two platform writers, file-based applied state."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from installer import env_redirect
from installer.env_redirect import BUN_CACHE_REDIRECT, REDIRECTS

_HOME_PARTS = (".cache", "bun", "transpiler-cache")
_HAND_INSTALLED = "51-bun-cache-redirect.conf"


def _bun() -> env_redirect.CacheRedirect:
    return next(entry for entry in REDIRECTS if entry is BUN_CACHE_REDIRECT)


def test_registry_has_exactly_one_entry_and_ids_are_unique() -> None:
    assert len(REDIRECTS) == 1
    assert len({entry.id for entry in REDIRECTS}) == len(REDIRECTS)
    entry = _bun()
    assert entry.variable == "BUN_RUNTIME_TRANSPILER_CACHE_PATH"


def test_bun_target_is_exactly_home_cache_bun_transpiler_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"
    resolved = env_redirect.target_path(_bun(), home)
    assert resolved == home.joinpath(*_HOME_PARTS)
    assert _bun().target_parts == _HOME_PARTS


def test_coverage_caveat_states_inheritance_and_daemon_fallback() -> None:
    caveat = _bun().coverage_caveat
    assert caveat.strip()
    lowered = caveat.lower()
    assert "inherit" in lowered
    assert "daemon" in lowered


def test_conf_basename_sorts_after_a_hand_installed_51_file() -> None:
    basename = _bun().conf_basename
    assert "tools-installer" in basename
    assert basename > _HAND_INSTALLED


def test_render_conf_ends_with_assignment_and_explains_next_login(tmp_path: Path) -> None:
    home = tmp_path / "home"
    text = env_redirect.render_conf(_bun(), home)
    nonempty = [line for line in text.splitlines() if line.strip()]
    target = home.joinpath(*_HOME_PARTS)
    assert nonempty[-1] == f"BUN_RUNTIME_TRANSPILER_CACHE_PATH={target}"
    comments = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    assert "login" in comments.lower()
    assert env_redirect.OWNERSHIP_SENTINEL in comments


def test_write_linux_redirect_creates_conf_and_cache_dir_at_mode_644(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    written = env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    assert written == conf_dir / _bun().conf_basename
    assert written.read_text() == env_redirect.render_conf(_bun(), home)
    assert written.stat().st_mode & 0o777 == 0o644
    assert home.joinpath(*_HOME_PARTS).is_dir()


def test_write_linux_redirect_twice_is_byte_identical(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    first = env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    before = first.read_bytes()
    second = env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    assert second.read_bytes() == before


def test_remove_linux_redirect_deletes_owned_file_and_is_false_when_absent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    written = env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    assert env_redirect.remove_linux_redirect(_bun(), conf_dir) is True
    assert not written.exists()
    assert env_redirect.remove_linux_redirect(_bun(), conf_dir) is False


def test_remove_linux_redirect_refuses_a_same_named_file_without_the_sentinel(
    tmp_path: Path,
) -> None:
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    foreign = conf_dir / _bun().conf_basename
    foreign.write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/other\n")
    assert env_redirect.remove_linux_redirect(_bun(), conf_dir) is False
    assert foreign.read_text() == "BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/other\n"


def test_remove_linux_redirect_never_touches_the_target_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    cache = home.joinpath(*_HOME_PARTS)
    env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    (cache / "kept.so").write_text("artifact")
    env_redirect.remove_linux_redirect(_bun(), conf_dir)
    assert (cache / "kept.so").read_text() == "artifact"


def test_render_block_exports_the_quoted_absolute_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    target = home.joinpath(*_HOME_PARTS)
    text = env_redirect.render_block(_bun(), home)
    assignment = f'export BUN_RUNTIME_TRANSPILER_CACHE_PATH="{target}"'
    assert assignment in text.splitlines()
    assert env_redirect.RC_BEGIN in text.splitlines()
    assert env_redirect.RC_END in text.splitlines()


def test_rc_and_conf_forms_are_intentionally_asymmetric(tmp_path: Path) -> None:
    """The asymmetry is intentional: rc is shell source (export required for
    inheritance) and environment.d is systemd assignment grammar (no export)."""
    home = tmp_path / "home"
    target = home.joinpath(*_HOME_PARTS)
    conf_line = [
        line for line in env_redirect.render_conf(_bun(), home).splitlines() if line.strip()
    ][-1]
    rc_line = next(
        line for line in env_redirect.render_block(_bun(), home).splitlines() if "=" in line
    )
    assert conf_line == f"BUN_RUNTIME_TRANSPILER_CACHE_PATH={target}"
    assert not conf_line.startswith("export ")
    assert rc_line == f'export BUN_RUNTIME_TRANSPILER_CACHE_PATH="{target}"'


def test_write_rc_redirect_is_idempotent_and_preserves_user_content(tmp_path: Path) -> None:
    home = tmp_path / "home"
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    rc.chmod(0o600)
    env_redirect.write_rc_redirect(_bun(), home, rc)
    once = rc.read_bytes()
    env_redirect.write_rc_redirect(_bun(), home, rc)
    assert rc.read_bytes() == once
    text = rc.read_text()
    assert text.startswith("export EDITOR=vim\n")
    assert text.count(env_redirect.RC_BEGIN) == 1
    assert rc.stat().st_mode & 0o777 == 0o600


def test_remove_rc_redirect_strips_only_the_block(tmp_path: Path) -> None:
    home = tmp_path / "home"
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    env_redirect.write_rc_redirect(_bun(), home, rc)
    env_redirect.remove_rc_redirect(_bun(), rc)
    # apply_block separates a block from existing content with a blank line,
    # and strip_block removes only the markers, so that separator stays.
    assert rc.read_text() == "export EDITOR=vim\n\n"


def test_linux_applied_requires_sentinel_and_the_expected_variable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    assert env_redirect.linux_applied(_bun(), home, conf_dir) is False
    env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    assert env_redirect.linux_applied(_bun(), home, conf_dir) is True
    path = conf_dir / _bun().conf_basename
    path.write_text(f"{env_redirect.OWNERSHIP_SENTINEL}\nOTHER_VAR={home.joinpath(*_HOME_PARTS)}\n")
    assert env_redirect.linux_applied(_bun(), home, conf_dir) is False


def test_unowned_same_named_file_is_neither_applied_nor_removable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    foreign = conf_dir / _bun().conf_basename
    foreign.write_text(f"BUN_RUNTIME_TRANSPILER_CACHE_PATH={home.joinpath(*_HOME_PARTS)}\n")
    assert env_redirect.linux_applied(_bun(), home, conf_dir) is False
    assert env_redirect.remove_linux_redirect(_bun(), conf_dir) is False
    assert foreign.exists()


def test_competing_conf_paths_lists_other_files_assigning_the_same_variable(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    other = conf_dir / _HAND_INSTALLED
    other.write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/theirs\n")
    (conf_dir / "unrelated.conf").write_text("OTHER=1\n")
    found = env_redirect.competing_conf_paths(_bun(), home, conf_dir)
    assert found == (other,)
    assert env_redirect.competing_conf_paths(_bun(), home, tmp_path / "missing") == ()


def test_competing_conf_paths_scans_system_dirs_masks_by_name_and_sees_indentation(
    tmp_path: Path,
) -> None:
    """WR-05: systemd merges the system environment.d dirs too, a same-named
    file in a higher-priority dir masks a lower one, and systemd strips
    leading whitespace before an assignment."""
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    etc = tmp_path / "etc-environment.d"
    usr = tmp_path / "usr-environment.d"
    etc.mkdir()
    usr.mkdir()
    indented = etc / "99-system.conf"
    indented.write_text("  BUN_RUNTIME_TRANSPILER_CACHE_PATH=/var/cache/bun\n")
    (etc / "10-masker.conf").write_text("OTHER=1\n")
    (usr / "10-masker.conf").write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/masked\n")
    (usr / _bun().conf_basename).write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/masked\n")
    found = env_redirect.competing_conf_paths(_bun(), home, conf_dir, (etc, usr))
    assert found == (indented,)


def test_write_linux_redirect_refuses_an_unreadable_same_named_file(tmp_path: Path) -> None:
    """WR-06: an undecodable (or unreadable) foreign file used to be treated
    as absent and replaced by the atomic rename."""
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    foreign = conf_dir / _bun().conf_basename
    foreign.write_bytes(b"\xff\xfe not utf-8 BUN_RUNTIME_TRANSPILER_CACHE_PATH=/theirs\n")
    with pytest.raises(OSError, match="not managed by tools-installer"):
        env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    assert foreign.read_bytes().startswith(b"\xff\xfe")


def test_write_linux_redirect_refuses_a_dangling_same_named_symlink(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    link = conf_dir / _bun().conf_basename
    link.symlink_to(tmp_path / "nowhere.conf")
    with pytest.raises(OSError, match="not managed by tools-installer"):
        env_redirect.write_linux_redirect(_bun(), home, conf_dir)
    assert link.is_symlink()


def test_rc_applied_requires_a_closed_block(tmp_path: Path) -> None:
    home = tmp_path / "home"
    rc = tmp_path / ".myshellrc"
    assert env_redirect.rc_applied(_bun(), home, rc) is False
    rc.write_text(f"{env_redirect.RC_BEGIN}\nexport ORPHAN=1\n")
    assert env_redirect.rc_applied(_bun(), home, rc) is False
    env_redirect.write_rc_redirect(_bun(), home, rc)
    assert env_redirect.rc_applied(_bun(), home, rc) is True


def test_applied_predicates_ignore_the_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUN_RUNTIME_TRANSPILER_CACHE_PATH", "/tmp/live")
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    rc = tmp_path / ".myshellrc"
    assert os.environ["BUN_RUNTIME_TRANSPILER_CACHE_PATH"] == "/tmp/live"
    assert env_redirect.linux_applied(_bun(), home, conf_dir) is False
    assert env_redirect.rc_applied(_bun(), home, rc) is False


def test_project_conf_sorts_after_the_hand_installed_name() -> None:
    names = sorted([_HAND_INSTALLED, _bun().conf_basename])
    assert names[-1] == _bun().conf_basename


def test_real_environment_d_generator_prefers_the_later_file(tmp_path: Path) -> None:
    generator = shutil.which("systemd-environment-d-generator")
    if generator is None:
        pytest.skip("systemd-environment-d-generator is not resolvable")
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    target = home.joinpath(*_HOME_PARTS)
    (conf_dir / _HAND_INSTALLED).write_text(
        "BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/hand-installed\n"
    )
    (conf_dir / _bun().conf_basename).write_text(env_redirect.render_conf(_bun(), home))
    completed = subprocess.run(
        [generator, str(conf_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assignment = f"BUN_RUNTIME_TRANSPILER_CACHE_PATH={target}"
    assert assignment in completed.stdout.splitlines()
    assert (
        "BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/hand-installed" not in completed.stdout.splitlines()
    )


@pytest.mark.parametrize(
    "name",
    ["HAS SPACE", "HAS=EQUALS", "HAS#HASH", "1LEADING", "", "TRAILING\n"],
)
def test_invalid_variable_names_are_rejected_before_any_write(tmp_path: Path, name: str) -> None:
    bad = env_redirect.CacheRedirect(
        id="bad",
        label="Bad",
        variable=name,
        target_parts=_HOME_PARTS,
        reason="nope",
        coverage_caveat=_bun().coverage_caveat,
        conf_basename="99-tools-installer-bad.conf",
    )
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    with pytest.raises(ValueError):
        env_redirect.render_conf(bad, home)
    assert not conf_dir.exists()


def test_rendering_rejects_a_relative_or_injectable_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    with pytest.raises(ValueError):
        env_redirect.render_conf(_bun(), Path("relative-home"))
    dangerous = (
        "has\nnewline",
        "has\rreturn",
        'has"quote',
        "has\\backslash",
        "has`tick",
        "has$dollar",
    )
    for fragment in dangerous:
        poisoned = env_redirect.CacheRedirect(
            id="poison",
            label="Poison",
            variable="SAFE_NAME",
            target_parts=(fragment,),
            reason="nope",
            coverage_caveat=_bun().coverage_caveat,
            conf_basename="99-tools-installer-poison.conf",
        )
        with pytest.raises(ValueError):
            env_redirect.render_block(poisoned, home)


def test_environment_d_dir_ignores_a_relative_xdg_config_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    assert env_redirect.environment_d_dir(home, {}) == home / ".config" / "environment.d"
    absolute = tmp_path / "xdg"
    assert (
        env_redirect.environment_d_dir(home, {"XDG_CONFIG_HOME": str(absolute)})
        == absolute / "environment.d"
    )
    assert (
        env_redirect.environment_d_dir(home, {"XDG_CONFIG_HOME": "relative/config"})
        == home / ".config" / "environment.d"
    )
