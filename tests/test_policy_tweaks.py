import shutil
import subprocess
from pathlib import Path

from installer.policy import Policy, PolicyResult, ban_policy, tweak_policy
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
    assert result.reload_hint is not None
    assert "source ~/.myshellrc" in result.reload_hint
    assert "hash -r" not in result.reload_hint
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


def test_codex_skip_policy_round_trips(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_bundle("codex-skip"), rc_path=rc)
    policy.apply()
    assert "dangerously-bypass-approvals-and-sandbox" in rc.read_text()
    result = policy.remove()
    assert "dangerously-bypass-approvals-and-sandbox" not in rc.read_text()
    assert "cleared" in result.layers[0].detail


def test_opencode_auto_policy_round_trips(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_bundle("opencode-auto"), rc_path=rc)
    policy.apply()
    assert "opencode --auto" in rc.read_text()
    result = policy.remove()
    assert "opencode --auto" not in rc.read_text()
    assert "cleared" in result.layers[0].detail


def test_tweak_policy_enable_hint_names_source_not_hash_r(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=tmp_path / "bin").apply()
    assert result.reload_hint is not None
    assert "source ~/.myshellrc" in result.reload_hint
    assert "hash -r" not in result.reload_hint

    ban_rc = tmp_path / "ban.myshellrc"
    ban_result = ban_policy(
        shim_dir=tmp_path / "shim",
        apply_rc_paths=[ban_rc],
        remove_rc_paths=[ban_rc],
        path_value="",
        which=lambda _name: None,
    ).apply()
    assert ban_result.reload_hint is not None and "hash -r" in ban_result.reload_hint


def test_tweak_policy_disable_hint_names_new_shell_not_source(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_bundle("countdown"), rc_path=rc, bin_dir=tmp_path / "bin")
    policy.apply()
    result = policy.remove()
    assert result.reload_hint is not None
    assert "new shell" in result.reload_hint.lower()
    assert "source ~/.myshellrc" not in result.reload_hint
    assert "hash -r" not in result.reload_hint

    ban_rc = tmp_path / "ban.myshellrc"
    ban_result = ban_policy(
        shim_dir=tmp_path / "shim",
        apply_rc_paths=[ban_rc],
        remove_rc_paths=[ban_rc],
        path_value="",
        which=lambda _name: None,
    ).remove()
    assert ban_result.reload_hint is not None and "hash -r" in ban_result.reload_hint


def test_tweak_policy_ensure_sourced_from_wires_myshellrc_into_the_given_rc_path(
    tmp_path: Path,
) -> None:
    myshellrc = tmp_path / ".myshellrc"
    split_rc = tmp_path / ".bashrc"
    other_rc = tmp_path / ".zshrc"

    tweak_policy(_bundle("codex-skip"), rc_path=myshellrc, ensure_sourced_from=(split_rc,)).apply()
    assert str(myshellrc) in split_rc.read_text()

    tweak_policy(_bundle("codex-skip"), rc_path=myshellrc).apply()
    assert not other_rc.exists()


def test_tweak_policy_split_mode_alias_resolves_in_a_fresh_shell(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if bash is None:
        return
    myshellrc = tmp_path / ".myshellrc"
    split_rc = tmp_path / ".bashrc"
    tweak_policy(_bundle("codex-skip"), rc_path=myshellrc, ensure_sourced_from=(split_rc,)).apply()
    result = subprocess.run(
        [bash, "-c", f'source "{split_rc}" && alias codex'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "dangerously-bypass-approvals-and-sandbox" in result.stdout
