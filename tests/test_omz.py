from pathlib import Path

import pytest

from installer import omz
from installer.omz import (
    MANAGED_PLUGINS,
    OmzPluginsError,
    disable_plugins,
    enable_plugins,
    omz_present,
    owned_plugins,
    plugins_in,
    plugins_owned,
    remove_plugins,
    write_plugins,
)

_ZSHRC = (
    'export ZSH="$HOME/.oh-my-zsh"\n'
    'ZSH_THEME="robbyrussell"\n'
    "plugins=(z sudo)\n"
    "source $ZSH/oh-my-zsh.sh\n"
)


def _sandbox(tmp_path: Path, content: str = _ZSHRC) -> tuple[Path, Path]:
    """A .zshrc to edit and the managed rc file that holds the ownership record."""
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(content)
    return zshrc, tmp_path / ".myshellrc"


def test_enable_adds_only_the_missing_names_and_preserves_the_rest() -> None:
    out = enable_plugins(_ZSHRC)
    assert "plugins=(z sudo git docker)" in out
    assert out.replace("plugins=(z sudo git docker)", "plugins=(z sudo)") == _ZSHRC


def test_enable_is_idempotent_and_never_duplicates() -> None:
    once = enable_plugins(_ZSHRC)
    assert enable_plugins(once) == once
    from_git = enable_plugins("plugins=(git)\n")
    assert from_git == "plugins=(git docker)\n"
    assert from_git.count("git") == 1


def test_disable_removes_only_the_managed_names() -> None:
    src = (
        'export ZSH="$HOME/.oh-my-zsh"\n'
        'ZSH_THEME="robbyrussell"\n'
        "plugins=(z git sudo docker)\n"
        "source $ZSH/oh-my-zsh.sh\n"
    )
    out = disable_plugins(src)
    assert out == _ZSHRC


def test_write_and_remove_round_trip_on_a_real_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    assert plugins_owned(state) is False
    assert write_plugins(zshrc, state) == ("git", "docker")
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ("git", "docker")
    after_write = zshrc.read_text()
    assert "plugins=(z sudo git docker)" in after_write
    assert after_write.replace("plugins=(z sudo git docker)", "plugins=(z sudo)") == _ZSHRC
    assert remove_plugins(zshrc, state) == ("git", "docker")
    assert plugins_owned(state) is False
    assert zshrc.read_text() == _ZSHRC


def test_multi_line_array_is_refused_not_parsed() -> None:
    src = "plugins=(\n  git\n  z\n)\nsource x\n"
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        enable_plugins(src)
    assert disable_plugins(src) == src


def test_a_zshrc_with_no_plugins_line_raises_on_enable_and_no_ops_on_disable() -> None:
    src = 'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\n'
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        enable_plugins(src)
    assert disable_plugins(src) == src


def test_missing_file_raises_on_write_and_no_ops_on_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    missing = tmp_path / ".zshrc"
    state = tmp_path / ".myshellrc"
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        write_plugins(missing, state)
    assert not missing.exists()
    # A refused enable must not leave a claim of ownership behind.
    assert plugins_owned(state) is False
    assert remove_plugins(missing, state) == ()
    assert not missing.exists()


def test_commented_out_plugins_line_is_never_matched() -> None:
    src = "# plugins=(git)\nsource $ZSH/oh-my-zsh.sh\n"
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        enable_plugins(src)
    assert disable_plugins(src) == src


def test_last_matching_line_wins() -> None:
    src = "plugins=(a)\nZSH_THEME=x\nplugins=(b)\n"
    out = enable_plugins(src)
    assert out == "plugins=(a)\nZSH_THEME=x\nplugins=(b git docker)\n"


def test_indentation_and_trailing_comment_are_preserved() -> None:
    src = "export ZSH=x\n  plugins=(z)  # my plugins\nsource y\n"
    out = enable_plugins(src)
    assert out == "export ZSH=x\n  plugins=(z git docker)  # my plugins\nsource y\n"


def test_empty_array_and_ragged_whitespace() -> None:
    assert enable_plugins("plugins=()\n") == "plugins=(git docker)\n"
    assert enable_plugins("plugins=(  z   sudo  )\n") == "plugins=(z sudo git docker)\n"


def test_disable_on_an_array_without_the_managed_names_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    assert plugins_owned(state) is False
    assert disable_plugins(_ZSHRC) == _ZSHRC
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == _ZSHRC


def test_disable_removes_a_plugin_the_user_had_before() -> None:
    src = "plugins=(git z)\n"
    assert disable_plugins(src) == "plugins=(z)\n"


def test_plugins_in_reports_the_array_contents() -> None:
    assert plugins_in("plugins=(git)\n") == ("git",)
    assert plugins_in("plugins=(docker git)\n") == ("docker", "git")
    assert plugins_in(_ZSHRC) == ("z", "sudo")
    assert plugins_in("ZSH_THEME=x\n") == ()


def test_write_does_not_touch_the_file_when_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    assert write_plugins(zshrc, state) == ("git", "docker")
    enabled = zshrc.read_text()
    mtime = zshrc.stat().st_mtime_ns
    assert write_plugins(zshrc, state) == ()
    assert zshrc.read_text() == enabled
    assert zshrc.stat().st_mtime_ns == mtime
    # Re-applying does not widen the record beyond what was actually added.
    assert owned_plugins(state) == ("git", "docker")


def test_omz_present_detects_the_home_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert omz_present(tmp_path, {}) is False
    (tmp_path / ".oh-my-zsh").mkdir()
    assert omz_present(tmp_path, {}) is True


def test_omz_present_accepts_a_valid_zsh_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    custom = tmp_path / "custom-omz"
    custom.mkdir()
    assert omz_present(tmp_path, {"ZSH": str(custom)}) is True
    assert omz_present(tmp_path, {"ZSH": str(tmp_path / "missing")}) is False
    assert omz_present(tmp_path, {"ZSH": ""}) is False


def test_a_multi_line_array_after_a_single_line_one_is_refused_not_silently_edited() -> None:
    # zsh honors the LAST assignment. Editing the single-line array above a
    # multi-line one would report success while loading nothing.
    src = "plugins=(git)\n# later\nplugins=(\n  zsh-autosuggestions\n)\n"
    with pytest.raises(OmzPluginsError, match="multi-line"):
        enable_plugins(src)
    assert disable_plugins(src) == src
    assert plugins_in("plugins=(git docker)\n# later\nplugins=(\n  z\n)\n") == ()


def test_a_single_line_array_after_a_multi_line_one_is_still_editable() -> None:
    # The reverse order is fine: the single-line array is the final assignment.
    src = "plugins=(\n  z\n)\nplugins=(git)\n"
    assert enable_plugins(src) == "plugins=(\n  z\n)\nplugins=(git docker)\n"


def test_write_refuses_a_shadowed_array_and_leaves_the_file_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    shadowed = "plugins=(git)\nplugins=(\n  z\n)\n"
    zshrc, state = _sandbox(tmp_path, shadowed)
    with pytest.raises(OmzPluginsError, match="multi-line"):
        write_plugins(zshrc, state)
    assert zshrc.read_text() == shadowed
    assert plugins_owned(state) is False
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == shadowed


def test_a_crlf_zshrc_is_edited_and_keeps_its_line_endings() -> None:
    src = 'ZSH_THEME="robbyrussell"\r\nplugins=(z)\r\nsource $ZSH/oh-my-zsh.sh\r\n'
    out = enable_plugins(src)
    assert out == (
        'ZSH_THEME="robbyrussell"\r\nplugins=(z git docker)\r\nsource $ZSH/oh-my-zsh.sh\r\n'
    )
    assert set(MANAGED_PLUGINS) <= set(plugins_in(out))
    assert disable_plugins(out) == src


def test_a_crlf_trailing_comment_survives_the_rewrite() -> None:
    assert enable_plugins("  plugins=(z)  # mine\r\n") == "  plugins=(z git docker)  # mine\r\n"


def test_quoted_plugin_names_are_recognised_not_duplicated() -> None:
    # `plugins=("git" docker)` is unusual but legal zsh; "git" names the same
    # plugin as git, so enabling must not append a redundant second entry.
    assert enable_plugins('plugins=("git" docker)\n') == 'plugins=("git" docker)\n'
    assert plugins_in('plugins=("git" "docker")\n') == ("git", "docker")
    # A name kept is written back verbatim — quoting style is never restyled.
    assert enable_plugins('plugins=("z")\n') == 'plugins=("z" git docker)\n'
    # ...and a quoted managed name is still removable.
    assert disable_plugins('plugins=("git" z docker)\n') == "plugins=(z)\n"


def test_the_zshrc_rewrite_is_atomic_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    zshrc.chmod(0o600)
    write_plugins(zshrc, state)
    assert "plugins=(z sudo git docker)" in zshrc.read_text()
    # Mode carried over from the original, and no sibling temp file survives.
    assert zshrc.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == [".myshellrc", ".zshrc"]


def test_a_failed_rewrite_leaves_the_original_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)

    def boom(_src: object, _dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(omz.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        write_plugins(zshrc, state)
    # The whole point of the temp+replace: the user's .zshrc is never truncated,
    # and the partial temp file is cleaned up rather than left beside it.
    assert zshrc.read_text() == _ZSHRC
    assert sorted(p.name for p in tmp_path.iterdir()) == [".zshrc"]
    assert plugins_owned(state) is False


def test_a_hand_authored_array_is_never_ours_to_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The CR-01 case: `git` ships in Oh-My-Zsh's own default .zshrc and `docker`
    # is its commonest addition, so content cannot prove ownership. This user
    # never enabled the policy; a full uninstall must not touch their file.
    monkeypatch.setenv("HOME", str(tmp_path))
    hand_written = 'ZSH_THEME="robbyrussell"\nplugins=(git docker kubectl)\nsource x\n'
    zshrc, state = _sandbox(tmp_path, hand_written)
    assert plugins_owned(state) is False
    assert owned_plugins(state) == ()
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == hand_written


def test_only_the_names_this_installer_added_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The user already had `git`; only `docker` is ours, so only `docker` goes.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(git kubectl)\nsource x\n")
    assert write_plugins(zshrc, state) == ("docker",)
    assert owned_plugins(state) == ("docker",)
    assert zshrc.read_text() == "plugins=(git kubectl docker)\nsource x\n"
    assert remove_plugins(zshrc, state) == ("docker",)
    assert zshrc.read_text() == "plugins=(git kubectl)\nsource x\n"


def test_enabling_over_an_array_that_already_has_everything_owns_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Enabling is still a real state change (the row reads ON, the policy is
    # ours to switch off) but it added nothing, so it may remove nothing.
    monkeypatch.setenv("HOME", str(tmp_path))
    original = "plugins=(git docker)\nsource x\n"
    zshrc, state = _sandbox(tmp_path, original)
    assert write_plugins(zshrc, state) == ()
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ()
    assert remove_plugins(zshrc, state) == ()
    assert plugins_owned(state) is False
    assert zshrc.read_text() == original


def test_the_record_is_an_inert_comment_block_in_the_managed_rc_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # .zshrc never carries a tools-installer marker, so the record lives in the
    # rc file this installer owns — and every line of it is a comment.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    state.write_text("export EDITOR=vim\n")
    write_plugins(zshrc, state)
    body = state.read_text()
    assert "tools-installer" not in zshrc.read_text()
    assert "export EDITOR=vim" in body
    assert "# added: git docker" in body
    assert all(
        line.startswith("#") for line in body.split("\n") if line and line != "export EDITOR=vim"
    )
    remove_plugins(zshrc, state)
    # Teardown leaves the user's own rc content alone.
    assert state.read_text().strip() == "export EDITOR=vim"


def test_a_record_survives_being_read_back_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=()\nsource x\n")
    write_plugins(zshrc, state)
    assert owned_plugins(tmp_path / ".myshellrc") == ("git", "docker")
    # An unrelated rc file is not a record.
    assert plugins_owned(tmp_path / ".bashrc") is False


def test_a_recorded_name_the_user_already_deleted_is_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # We added `docker`, the user then deleted it by hand. Disabling has nothing
    # left to do, so .zshrc is not rewritten — but the record still clears.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(git)\nsource x\n")
    assert write_plugins(zshrc, state) == ("docker",)
    zshrc.write_text("plugins=(git)\nsource x\n")
    mtime = zshrc.stat().st_mtime_ns
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.stat().st_mtime_ns == mtime
    assert plugins_owned(state) is False
