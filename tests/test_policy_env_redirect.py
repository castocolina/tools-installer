"""cache_redirect_policy: one toggle, two platforms, honest reload wording."""

from pathlib import Path

import pytest

from installer.env_redirect import BUN_CACHE_REDIRECT
from installer.policy import PolicyResult, cache_redirect_policy

_SOURCE_BEGIN = "# >>> tools-installer source >>>"
_SOURCE_END = "# <<< tools-installer source <<<"


def _policy(
    tmp_path: Path,
    *,
    platform_os: str,
    ensure_sourced_from: tuple[Path, ...] | object = (),
):
    kwargs: dict[str, object] = {
        "platform_os": platform_os,
        "conf_dir": tmp_path / "environment.d",
        "rc_path": tmp_path / ".myshellrc",
        "home": tmp_path / "home",
    }
    if ensure_sourced_from != ():
        kwargs["ensure_sourced_from"] = ensure_sourced_from
    return cache_redirect_policy(BUN_CACHE_REDIRECT, **kwargs)  # type: ignore[arg-type]


def test_policy_id_is_namespaced_and_description_carries_the_caveat_verbatim(
    tmp_path: Path,
) -> None:
    policy = _policy(tmp_path, platform_os="linux")
    assert policy.id == "cache-redirect:bun"
    assert policy.id.startswith("cache-redirect:")
    assert "BUN_RUNTIME_TRANSPILER_CACHE_PATH" in policy.description
    assert BUN_CACHE_REDIRECT.coverage_caveat in policy.description


def test_linux_apply_writes_the_conf_and_names_the_next_login(tmp_path: Path) -> None:
    home = tmp_path / "home"
    conf_dir = tmp_path / "environment.d"
    policy = _policy(tmp_path, platform_os="linux")
    assert policy.active is False
    assert policy.is_active is not None
    assert policy.is_active() is False
    result = policy.apply()
    written = conf_dir / BUN_CACHE_REDIRECT.conf_basename
    assert written.is_file()
    assert home.joinpath(".cache", "bun", "transpiler-cache").is_dir()
    assert isinstance(result, PolicyResult)
    assert any(written.name in layer.detail for layer in result.layers)
    assert result.reload_hint is not None
    assert "next login" in result.reload_hint.lower()
    assert "shell" not in result.reload_hint.lower()
    assert "terminal" not in result.reload_hint.lower()
    assert policy.is_active() is True


def test_linux_reload_hint_does_not_claim_a_new_shell_is_enough(tmp_path: Path) -> None:
    result = _policy(tmp_path, platform_os="linux").apply()
    assert result.reload_hint is not None
    lowered = result.reload_hint.lower()
    assert "next login" in lowered
    assert "environment.d" in lowered


def test_macos_apply_writes_the_block_and_uses_the_shell_hint(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = _policy(tmp_path, platform_os="macos")
    assert policy.active is False
    result = policy.apply()
    assert 'export BUN_RUNTIME_TRANSPILER_CACHE_PATH="' in rc.read_text()
    assert result.reload_hint is not None
    assert "source ~/.myshellrc" in result.reload_hint
    assert policy.is_active is not None
    assert policy.is_active() is True


def test_macos_apply_wires_ensure_sourced_from_and_rereads_a_callable(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    seen: list[int] = []

    def sourced() -> tuple[Path, ...]:
        seen.append(1)
        return (zshrc,)

    policy = _policy(tmp_path, platform_os="macos", ensure_sourced_from=sourced)
    assert seen == []
    result = policy.apply()
    assert seen == [1]
    text = zshrc.read_text()
    assert _SOURCE_BEGIN in text
    assert _SOURCE_END in text
    assert str(rc) in text
    assert any("source" in layer.detail for layer in result.layers)


def test_remove_strips_only_the_owned_artifact_and_is_idempotent(tmp_path: Path) -> None:
    conf_dir = tmp_path / "environment.d"
    policy = _policy(tmp_path, platform_os="linux")
    policy.apply()
    first = policy.remove()
    assert not (conf_dir / BUN_CACHE_REDIRECT.conf_basename).exists()
    assert first.layers
    second = policy.remove()
    assert isinstance(second, PolicyResult)
    assert second.layers


def test_competing_conf_is_warned_about_and_left_on_disk(tmp_path: Path) -> None:
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    foreign = conf_dir / "51-bun-cache-redirect.conf"
    foreign.write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/theirs\n")
    result = _policy(tmp_path, platform_os="linux").apply()
    assert result.warning is not None
    assert foreign.name in result.warning
    assert "precedence" in result.warning.lower() or "sorts" in result.warning.lower()
    assert foreign.read_text() == "BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/theirs\n"


def test_a_competing_conf_that_sorts_later_is_reported_as_overriding_the_redirect(
    tmp_path: Path,
) -> None:
    """WR-05: 60-bun.conf sorts after 51-tools-installer-... and wins; the
    warning used to claim the opposite."""
    conf_dir = tmp_path / "environment.d"
    conf_dir.mkdir()
    later = conf_dir / "60-bun.conf"
    later.write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/tmp/theirs\n")
    result = _policy(tmp_path, platform_os="linux").apply()
    assert result.warning is not None
    assert "60-bun.conf" in result.warning
    assert "overrides this redirect" in result.warning
    assert "takes precedence" not in result.warning
    assert later.exists()


def test_a_later_sorting_system_conf_is_reported_read_only(tmp_path: Path) -> None:
    system = tmp_path / "etc-environment.d"
    system.mkdir()
    theirs = system / "99-bun.conf"
    theirs.write_text("BUN_RUNTIME_TRANSPILER_CACHE_PATH=/var/cache/bun\n")
    policy = cache_redirect_policy(
        BUN_CACHE_REDIRECT,
        platform_os="linux",
        conf_dir=tmp_path / "environment.d",
        rc_path=tmp_path / ".myshellrc",
        home=tmp_path / "home",
        system_conf_dirs=(system,),
    )
    result = policy.apply()
    assert result.warning is not None
    assert "99-bun.conf" in result.warning
    assert "overrides this redirect" in result.warning
    assert theirs.read_text() == "BUN_RUNTIME_TRANSPILER_CACHE_PATH=/var/cache/bun\n"


def test_second_apply_is_idempotent_and_warns_nothing(tmp_path: Path) -> None:
    policy = _policy(tmp_path, platform_os="linux")
    policy.apply()
    path = tmp_path / "environment.d" / BUN_CACHE_REDIRECT.conf_basename
    before = path.read_bytes()
    again = policy.apply()
    assert again.warning is None
    assert path.read_bytes() == before


def test_linux_branch_is_anything_other_than_macos(tmp_path: Path) -> None:
    policy = _policy(tmp_path, platform_os="freebsd")
    policy.apply()
    assert (tmp_path / "environment.d" / BUN_CACHE_REDIRECT.conf_basename).is_file()


@pytest.mark.parametrize("platform_os", ["linux", "macos"])
def test_is_active_reprobes_rather_than_returning_the_snapshot(
    tmp_path: Path, platform_os: str
) -> None:
    policy = _policy(tmp_path, platform_os=platform_os)
    assert policy.active is False
    policy.apply()
    assert policy.active is False
    assert policy.is_active is not None
    assert policy.is_active() is True
