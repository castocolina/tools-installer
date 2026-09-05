from pathlib import Path

import pytest

from installer.omz import (
    OmzPluginsError,
    disable_plugins,
    enable_plugins,
    omz_present,
    plugins_enabled,
    plugins_present,
    remove_plugins,
    write_plugins,
)

_ZSHRC = (
    'export ZSH="$HOME/.oh-my-zsh"\n'
    'ZSH_THEME="robbyrussell"\n'
    "plugins=(z sudo)\n"
    "source $ZSH/oh-my-zsh.sh\n"
)


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
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(_ZSHRC)
    assert write_plugins(zshrc) == ("git", "docker")
    assert plugins_present(zshrc) is True
    after_write = zshrc.read_text()
    assert "plugins=(z sudo git docker)" in after_write
    assert after_write.replace("plugins=(z sudo git docker)", "plugins=(z sudo)") == _ZSHRC
    assert remove_plugins(zshrc) == ("git", "docker")
    assert plugins_present(zshrc) is False
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
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        write_plugins(missing)
    assert not missing.exists()
    assert plugins_present(missing) is False
    assert remove_plugins(missing) == ()
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
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(_ZSHRC)
    assert plugins_present(zshrc) is False
    assert disable_plugins(_ZSHRC) == _ZSHRC
    assert remove_plugins(zshrc) == ()
    assert zshrc.read_text() == _ZSHRC
    assert plugins_present(zshrc) is False


def test_disable_removes_a_plugin_the_user_had_before() -> None:
    src = "plugins=(git z)\n"
    assert disable_plugins(src) == "plugins=(z)\n"


def test_plugins_enabled_requires_all_managed_names() -> None:
    assert plugins_enabled("plugins=(git)\n") is False
    assert plugins_enabled("plugins=(git docker)\n") is True
    assert plugins_enabled("plugins=(docker git)\n") is True
    assert plugins_enabled(_ZSHRC) is False
    assert plugins_enabled("ZSH_THEME=x\n") is False


def test_write_does_not_touch_the_file_when_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(_ZSHRC)
    assert write_plugins(zshrc) == ("git", "docker")
    enabled = zshrc.read_text()
    mtime = zshrc.stat().st_mtime_ns
    assert write_plugins(zshrc) == ()
    assert zshrc.read_text() == enabled
    assert zshrc.stat().st_mtime_ns == mtime


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
