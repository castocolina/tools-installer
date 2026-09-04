from pathlib import Path

from installer.policy import Policy, PolicyResult, tweak_policy
from installer.tweaks import BUNDLES


def _bundle(bundle_id: str):
    return next(b for b in BUNDLES if b.id == bundle_id)


def test_tweak_policy_metadata_and_id_namespacing(tmp_path: Path) -> None:
    policy = tweak_policy(_bundle("docker"), rc_path=tmp_path / ".myshellrc")
    assert isinstance(policy, Policy)
    assert policy.id == "tweak:docker"
    assert policy.label == "Docker shortcuts"
    assert "docker-ps" in policy.description
    assert policy.requires == ("watch",)


def test_tweak_policy_marks_missing_required_tools(tmp_path: Path) -> None:
    policy = tweak_policy(
        _bundle("docker"),
        rc_path=tmp_path / ".myshellrc",
        installed_tools={"watch": False},
    )
    assert policy.missing_requires == ("watch",)


def test_tweak_policy_clears_requirements_when_tool_is_installed(tmp_path: Path) -> None:
    policy = tweak_policy(
        _bundle("docker"),
        rc_path=tmp_path / ".myshellrc",
        installed_tools={"watch": True},
    )
    assert policy.requires == ("watch",)
    assert policy.missing_requires == ()


def test_countdown_policy_requires_uv_runtime(tmp_path: Path) -> None:
    policy = tweak_policy(
        _bundle("countdown"),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=tmp_path / "bin",
        installed_tools={"uv": False},
    )
    assert policy.requires == ("uv",)
    assert policy.missing_requires == ("uv",)


def test_tweak_policy_inactive_then_active_after_apply(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "bin"
    assert tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=bin_dir).active is False
    tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=bin_dir).apply()
    assert tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=bin_dir).active is True


def test_apply_writes_block_and_returns_result(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "bin"
    result = tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=bin_dir).apply()
    assert isinstance(result, PolicyResult)
    assert "wait_time()" in rc.read_text()
    assert str(bin_dir / "tools-installer-wait-time") in rc.read_text()
    assert (bin_dir / "tools-installer-wait-time").exists()
    assert result.layers[0].name == "Countdown helper"
    assert str(rc) in result.layers[0].detail
    assert result.layers[1].name == "Executable"
    assert "tools-installer-wait-time" in result.layers[1].detail
    assert result.reload_hint is not None and "hash -r" in result.reload_hint
    assert result.warning is None


def test_tweak_policy_requires_bin_dir_for_managed_executables(tmp_path: Path) -> None:
    policy = tweak_policy(_bundle("countdown"), rc_path=tmp_path / ".myshellrc")
    try:
        policy.apply()
    except ValueError as exc:
        assert "requires a managed bin_dir" in str(exc)
    else:
        raise AssertionError("countdown apply should require an explicit managed bin_dir")


def test_remove_strips_block(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_bundle("claude-skip"), rc_path=rc)
    policy.apply()
    result = policy.remove()
    assert "claude --dangerously-skip-permissions" not in rc.read_text()
    assert "cleared" in result.layers[0].detail


def test_remove_is_idempotent_on_clean_machine(tmp_path: Path) -> None:
    result = tweak_policy(_bundle("docker"), rc_path=tmp_path / ".myshellrc").remove()
    assert isinstance(result, PolicyResult)


def test_remove_cleans_countdown_managed_executable(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "bin"
    policy = tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=bin_dir)
    policy.apply()
    helper = bin_dir / "tools-installer-wait-time"
    assert helper.exists()
    result = policy.remove()
    assert "wait_time()" not in rc.read_text()
    assert not helper.exists()
    assert result.layers[1].detail.startswith("1 removed")
