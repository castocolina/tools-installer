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


def test_tweak_policy_inactive_then_active_after_apply(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    assert tweak_policy(_bundle("countdown"), rc_path=rc).active is False
    tweak_policy(_bundle("countdown"), rc_path=rc).apply()
    assert tweak_policy(_bundle("countdown"), rc_path=rc).active is True


def test_apply_writes_block_and_returns_result(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = tweak_policy(_bundle("countdown"), rc_path=rc).apply()
    assert isinstance(result, PolicyResult)
    assert "wait_time()" in rc.read_text()
    assert result.layers[0].name == "Countdown helper"
    assert str(rc) in result.layers[0].detail
    assert result.reload_hint is not None and "hash -r" in result.reload_hint
    assert result.warning is None


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
