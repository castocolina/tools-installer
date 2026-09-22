from pathlib import Path

import pytest

from installer.omz import plugins_owned
from installer.policy import Policy, PolicyResult, omz_plugins_policy, omz_removal_detail

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
    policy = omz_plugins_policy(
        zshrc_path=_zshrc(tmp_path), state_path=tmp_path / ".myshellrc", present=False
    )
    assert isinstance(policy, Policy)
    assert policy.missing_requires == ("oh-my-zsh",)


def test_policy_clears_requires_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    policy = omz_plugins_policy(
        zshrc_path=_zshrc(tmp_path), state_path=tmp_path / ".myshellrc", present=True
    )
    assert policy.requires == ("oh-my-zsh",)
    assert policy.missing_requires == ()


def test_apply_and_remove_return_layered_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = _zshrc(tmp_path)
    policy = omz_plugins_policy(zshrc_path=zshrc, state_path=tmp_path / ".myshellrc", present=True)
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
    assert "nothing added" in already.layers[0].detail
    removed = policy.remove()
    assert removed.layers[0].name == "Oh-My-Zsh plugins"
    assert removed.reload_hint is not None
    assert "zsh" in removed.reload_hint.lower()
    assert "hash -r" not in removed.reload_hint
    already_off = policy.remove()
    assert "nothing to remove" in already_off.layers[0].detail


def test_policy_runs_terminal_sync_after_committing_plugins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = _zshrc(tmp_path)
    calls: list[str] = []

    def sync() -> str | None:
        assert "plugins=(z sudo git docker)" in zshrc.read_text()
        assert plugins_owned(tmp_path / ".myshellrc") is True
        calls.append("synced")
        return None

    policy = omz_plugins_policy(
        zshrc_path=zshrc,
        state_path=tmp_path / ".myshellrc",
        present=True,
        terminal_sync=sync,
    )

    result = policy.apply()

    assert calls == ["synced"]
    assert result.warning is None


def test_policy_keeps_committed_plugins_when_terminal_sync_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = _zshrc(tmp_path)

    def sync() -> str | None:
        raise OSError("wezterm configuration is user-owned")

    policy = omz_plugins_policy(
        zshrc_path=zshrc,
        state_path=tmp_path / ".myshellrc",
        present=True,
        terminal_sync=sync,
    )

    result = policy.apply()

    assert "plugins=(z sudo git docker)" in zshrc.read_text()
    assert plugins_owned(tmp_path / ".myshellrc") is True
    assert result.warning == (
        "Terminal shell synchronization failed: wezterm configuration is user-owned"
    )


def test_policy_rechecks_oh_my_zsh_presence_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    present = False
    policy = omz_plugins_policy(
        zshrc_path=_zshrc(tmp_path),
        state_path=tmp_path / ".myshellrc",
        present=lambda: present,
    )

    assert policy.missing_requirements() == ("oh-my-zsh",)
    present = True
    assert policy.missing_requirements() == ()


def test_apply_on_an_inert_zshrc_repairs_the_template_then_enables_plugins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text('ZSH_THEME="robbyrussell"\n')
    policy = omz_plugins_policy(zshrc_path=zshrc, state_path=tmp_path / ".myshellrc", present=True)
    result = policy.apply()
    text = zshrc.read_text()
    assert 'ZSH_THEME="robbyrussell"' in text
    export_at = text.index('export ZSH="$HOME/.oh-my-zsh"\n')
    plugins_at = text.index("plugins=(git docker)\n")
    source_at = text.index("source $ZSH/oh-my-zsh.sh\n")
    assert export_at < plugins_at < source_at
    assert "docker" in result.layers[0].detail


def test_removal_detail_names_the_plugins_and_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A preview that says only "omz-plugins" tells the user nothing about which
    # names leave which file — the whole question for a file we do not own.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = _zshrc(tmp_path)
    state = tmp_path / ".myshellrc"
    assert omz_removal_detail(zshrc_path=zshrc, state_path=state) is None
    omz_plugins_policy(zshrc_path=zshrc, state_path=state, present=True).apply()
    detail = omz_removal_detail(zshrc_path=zshrc, state_path=state)
    assert detail is not None
    assert "git, docker" in detail
    assert "~/.zshrc" in detail
    assert "plugins=(...)" in detail


def test_policy_keeps_committed_plugins_when_terminal_sync_raises_a_non_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-02/WR-03: a UnicodeDecodeError (a ValueError) is a real failure mode
    of the synchronizer's own readers, and it used to escape this site's narrow
    `except OSError` straight out of the Policies toggle."""
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc = _zshrc(tmp_path)

    def sync() -> str | None:
        return "\xe9".encode("latin-1").decode("utf-8")

    policy = omz_plugins_policy(
        zshrc_path=zshrc,
        state_path=tmp_path / ".myshellrc",
        present=True,
        terminal_sync=sync,
    )

    result = policy.apply()

    assert "plugins=(z sudo git docker)" in zshrc.read_text()
    assert plugins_owned(tmp_path / ".myshellrc") is True
    assert result.warning is not None
    assert result.warning.startswith("Terminal shell synchronization failed: ")
