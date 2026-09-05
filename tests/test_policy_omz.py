from pathlib import Path

import pytest

from installer.omz import OmzPluginsError
from installer.policy import Policy, PolicyResult, omz_plugins_policy

_ZSHRC = (
    'export ZSH="$HOME/.oh-my-zsh"\n'
    'ZSH_THEME="robbyrussell"\n'
    "plugins=(z sudo)\n"
    "source $ZSH/oh-my-zsh.sh\n"
)


def _zshrc(tmp_path: Path) -> Path:
    path = tmp_path / ".zshrc"
    path.write_text(_ZSHRC)
    return path


def test_policy_reports_missing_requires_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    policy = omz_plugins_policy(zshrc_path=_zshrc(tmp_path), present=False)
    assert isinstance(policy, Policy)
    assert policy.missing_requires == ("oh-my-zsh",)


def test_policy_clears_requires_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    policy = omz_plugins_policy(zshrc_path=_zshrc(tmp_path), present=True)
    assert policy.requires == ("oh-my-zsh",)
    assert policy.missing_requires == ()


def test_apply_and_remove_return_layered_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = _zshrc(tmp_path)
    policy = omz_plugins_policy(zshrc_path=zshrc, present=True)
    result = policy.apply()
    assert isinstance(result, PolicyResult)
    assert len(result.layers) == 1
    assert result.layers[0].name == "Oh-My-Zsh plugins"
    assert "git" in result.layers[0].detail
    assert "docker" in result.layers[0].detail
    assert "~/.zshrc" in result.layers[0].detail
    assert result.reload_hint is not None
    assert "zsh" in result.reload_hint.lower()
    assert "hash -r" not in result.reload_hint
    assert result.warning is None
    already = policy.apply()
    assert "already enabled" in already.layers[0].detail
    removed = policy.remove()
    assert removed.layers[0].name == "Oh-My-Zsh plugins"
    assert removed.reload_hint is not None
    assert "zsh" in removed.reload_hint.lower()
    assert "hash -r" not in removed.reload_hint
    already_off = policy.remove()
    assert "already disabled" in already_off.layers[0].detail


def test_apply_on_a_zshrc_without_an_array_raises_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text('ZSH_THEME="robbyrussell"\n')
    policy = omz_plugins_policy(zshrc_path=zshrc, present=True)
    try:
        policy.apply()
    except OSError as exc:
        assert isinstance(exc, OSError)
        assert isinstance(exc, OmzPluginsError)
    else:
        raise AssertionError("apply() must raise OSError when there is no array")
