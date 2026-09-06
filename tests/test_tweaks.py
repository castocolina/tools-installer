import itertools
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from installer.helper_assets import wait_time
from installer.platform import Platform
from installer.tweaks import (
    BUNDLES,
    TweakBundle,
    applicable_bundles,
    install_tweak_executables,
    remove_tweak,
    remove_tweak_executables,
    tweak_block,
    tweak_executables_present,
    tweak_present,
    write_tweak,
)


def _bundle(bundle_id: str) -> TweakBundle:
    return next(b for b in BUNDLES if b.id == bundle_id)


def test_bundles_have_stable_ids_and_order() -> None:
    assert [b.id for b in BUNDLES] == [
        "docker",
        "countdown",
        "claude-skip",
        "codex-skip",
        "apt-upgrade",
        "opencode-auto",
        "cursor-agent-model",
    ]


def test_codex_skip_body_matches_the_verified_flag() -> None:
    codex = _bundle("codex-skip")
    assert codex.body == "alias codex='codex --dangerously-bypass-approvals-and-sandbox'"
    assert codex.requires == ()
    assert codex.executables == ()
    assert codex.platforms == ()


def test_opencode_auto_body_matches_the_verified_flag() -> None:
    opencode = _bundle("opencode-auto")
    assert opencode.body == "alias opencode='opencode --auto'"
    assert opencode.requires == ()
    assert opencode.executables == ()
    assert opencode.platforms == ()


def test_opencode_auto_description_states_it_is_narrower_than_a_full_bypass() -> None:
    description = _bundle("opencode-auto").description
    assert "full" in description or "deny" in description


def test_block_is_marker_delimited_around_body() -> None:
    bundle = _bundle("claude-skip")
    block = tweak_block(bundle)
    assert block.startswith("# >>> tools-installer tweak:claude-skip >>>\n")
    assert block.endswith("\n# <<< tools-installer tweak:claude-skip <<<")
    assert bundle.body in block


def test_countdown_uses_managed_helper_wrapper() -> None:
    body = _bundle("countdown").body
    assert "uv run --no-project --script" in body
    assert "tools-installer-wait-time" in body
    assert "__TOOLS_INSTALLER_BIN_DIR__" in body
    assert "import datetime" not in body
    assert "echo -ne" not in body
    assert _bundle("countdown").requires == ("uv",)


def test_countdown_helper_formats_warning_styles() -> None:
    assert wait_time.parse_seconds(["1d10m15s"]) == 87015
    assert wait_time.left_time(90061) == "1d 1h 1m 1s"
    assert wait_time.style_for(9, 100)[0] == wait_time.ORANGE_BLINK
    assert wait_time.style_for(5, 100)[0] == wait_time.RED_FAST_BLINK


def test_docker_body_has_all_three_helpers() -> None:
    body = _bundle("docker").body
    assert "docker-ps()" in body
    assert "alias docker-stats=" in body
    assert "alias docker-memory='docker-stats'" in body
    assert "watch -n 5" in body
    assert _bundle("docker").requires == ("watch",)


def _install_countdown_helper(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    written = install_tweak_executables(_bundle("countdown"), bin_dir)
    target = bin_dir / "tools-installer-wait-time"
    assert written == (target,)
    return bin_dir


def _wait_seconds(tmp_path: Path, args: list[str], now: str = "2026-07-07T10:10:00") -> str:
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to exercise wait_time"
    bin_dir = _install_countdown_helper(tmp_path)
    script = tmp_path / "countdown.bash"
    script.write_text(
        tweak_block(_bundle("countdown"), bin_dir)
        + "\n"
        + f"wait_time --seconds {shlex.join(args)}\n"
    )
    env = os.environ | {"WAIT_TIME_NOW": now}
    result = subprocess.run([bash, str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _wait_countdown(
    tmp_path: Path, args: list[str], clock: str = "10:10:00"
) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to exercise wait_time"
    bin_dir = _install_countdown_helper(tmp_path)
    script = tmp_path / "countdown-display.bash"
    script.write_text(
        tweak_block(_bundle("countdown"), bin_dir)
        + "\n"
        + f"wait_time --preview {shlex.join(args)}\n"
    )
    env = os.environ | {"WAIT_TIME_CLOCK": clock}
    return subprocess.run([bash, str(script)], env=env, capture_output=True, text=True)


def test_countdown_parses_compact_and_spaced_durations(tmp_path: Path) -> None:
    assert _wait_seconds(tmp_path, ["1d10m15s"]) == "87015"
    assert _wait_seconds(tmp_path, ["23h", "49m"]) == "85740"


def test_countdown_parses_clock_targets(tmp_path: Path) -> None:
    assert _wait_seconds(tmp_path, ["10am"], now="2026-07-07T09:00:00") == "3600"
    assert _wait_seconds(tmp_path, ["tomorrow", "10am"]) == "85800"


def test_countdown_parses_compact_dates(tmp_path: Path) -> None:
    assert _wait_seconds(tmp_path, ["0708", "10:00:00"]) == "85800"
    assert _wait_seconds(tmp_path, ["260708-10:00:00:000"]) == "85800"


def test_countdown_display_shows_current_time_and_formatted_left_time(tmp_path: Path) -> None:
    result = _wait_countdown(tmp_path, ["90061"], clock="12:34:56")
    assert result.returncode == 0, result.stderr
    assert "now 12:34:56 | left 1d 1h 1m 1s" in result.stdout


def test_countdown_installs_managed_executable(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    target = bin_dir / "tools-installer-wait-time"
    assert install_tweak_executables(_bundle("countdown"), bin_dir) == (target,)
    assert target.exists()
    assert os.access(target, os.X_OK)
    assert "tools-installer-helper: wait_time" in target.read_text()


def test_countdown_removes_only_owned_executable(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    target = bin_dir / "tools-installer-wait-time"
    install_tweak_executables(_bundle("countdown"), bin_dir)
    assert remove_tweak_executables(_bundle("countdown"), bin_dir) == (target,)
    assert not target.exists()

    target.write_text("user-owned helper")
    assert remove_tweak_executables(_bundle("countdown"), bin_dir) == ()
    assert target.exists()


def test_tweak_executables_present_detects_an_owned_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / "bin"
    countdown = _bundle("countdown")
    install_tweak_executables(countdown, bin_dir)
    assert tweak_executables_present(countdown, bin_dir) is True
    assert tweak_executables_present(countdown, tmp_path / "empty-bin") is False
    assert tweak_executables_present(_bundle("claude-skip"), bin_dir) is False
    assert tweak_executables_present(_bundle("claude-skip"), tmp_path / "empty-bin") is False


def test_tweak_executables_present_ignores_a_foreign_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "tools-installer-wait-time").write_text("user-owned helper")
    assert tweak_executables_present(_bundle("countdown"), bin_dir) is False


def test_install_executables_is_noop_for_a_bundle_without_any() -> None:
    assert install_tweak_executables(_bundle("docker"), Path("/nonexistent")) == ()


def test_install_refuses_to_overwrite_a_foreign_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target = bin_dir / "tools-installer-wait-time"
    target.write_text("not ours")
    with pytest.raises(OSError, match="not managed by tools-installer"):
        install_tweak_executables(_bundle("countdown"), bin_dir)


def test_is_our_executable_returns_false_when_unreadable(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    target = bin_dir / "tools-installer-wait-time"
    bin_dir.mkdir()
    target.mkdir()  # a directory can't be read as text -> IsADirectoryError (an OSError)
    assert remove_tweak_executables(_bundle("countdown"), bin_dir) == ()


def test_every_block_parses_in_bash(tmp_path: Path) -> None:
    # ~/.myshellrc is sourced by interactive bash/zsh, so bash is the validity
    # target — not /bin/sh: hyphenated names like docker-ps() are valid in
    # bash/zsh but not strict POSIX sh. bash is present on macOS and on CI.
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to validate tweak bodies"
    for bundle in BUNDLES:
        script = tmp_path / f"{bundle.id}.bash"
        script.write_text(tweak_block(bundle, tmp_path / "bin") + "\n")
        result = subprocess.run([bash, "-n", str(script)], capture_output=True)
        assert result.returncode == 0, f"bash {bundle.id}: {result.stderr!r}"


def test_blocks_parse_in_bash_and_zsh_when_present(tmp_path: Path) -> None:
    for shell in ("bash", "zsh"):
        binary = shutil.which(shell)
        if binary is None:
            continue
        for bundle in BUNDLES:
            script = tmp_path / f"{bundle.id}.{shell}"
            script.write_text(tweak_block(bundle, tmp_path / "bin") + "\n")
            result = subprocess.run([binary, "-n", str(script)], capture_output=True)
            assert result.returncode == 0, f"{shell} {bundle.id}: {result.stderr!r}"


_SCRIPT_COUNTER = itertools.count()


def _run_cursor_agent(
    tmp_path: Path,
    invoke: str,
    args: list[str],
    *,
    shell: str = "bash",
    preamble: str = "",
) -> str | None:
    """Source the cursor-agent-model tweak block, invoke it, and return stdout.

    A stub `cursor-agent` executable (never the real, installed CLI — ONESHOT-
    RULES Rule 5) is put on a test-controlled PATH prepended to the real PATH,
    so `command cursor-agent "$@"` resolves to the stub and echoes its argv.
    Returns None when `shell` is not installed on this machine (graceful skip).
    An explicit timeout turns a self-recursion regression into a diagnosable
    AssertionError instead of hanging the whole test suite.
    """
    binary = shutil.which(shell)
    if binary is None:
        return None
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "cursor-agent"
    if not stub.exists():
        stub.write_text('#!/bin/sh\necho "ARGV: $*"\n')
        stub.chmod(0o755)
    script = tmp_path / f"cursor-agent-{next(_SCRIPT_COUNTER)}.{shell}"
    script.write_text(
        preamble + tweak_block(_bundle("cursor-agent-model")) + "\n" + shlex.join([invoke, *args])
    )
    env = os.environ | {"PATH": f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    try:
        result = subprocess.run(
            [binary, str(script)], env=env, capture_output=True, text=True, timeout=10
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "cursor-agent invocation timed out — likely self-recursion inside "
            "cursor-agent() (a missing `command` guard)"
        ) from exc
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_cursor_agent_model_injects_default_when_no_model_flag(tmp_path: Path) -> None:
    output = _run_cursor_agent(tmp_path, "cursor-agent", ["chat", "hello"])
    assert output is not None
    assert "ARGV: --model gpt-5.6-sol-high chat hello" in output


def test_cursor_agent_model_respects_explicit_space_form_model_flag(tmp_path: Path) -> None:
    output = _run_cursor_agent(tmp_path, "cursor-agent", ["--model", "other-model", "chat"])
    assert output is not None
    assert "ARGV: --model other-model chat" in output


def test_cursor_agent_model_respects_explicit_equals_form_model_flag(tmp_path: Path) -> None:
    output = _run_cursor_agent(tmp_path, "cursor-agent", ["--model=other-model", "chat"])
    assert output is not None
    assert "ARGV: --model=other-model chat" in output


def test_cursor_delegates_to_cursor_agent_function_and_inherits_injection(
    tmp_path: Path,
) -> None:
    output = _run_cursor_agent(tmp_path, "cursor", ["chat", "hello"])
    assert output is not None
    assert "ARGV: --model gpt-5.6-sol-high chat hello" in output


def test_cursor_agent_does_not_mistake_a_quoted_substring_for_the_flag(tmp_path: Path) -> None:
    output = _run_cursor_agent(tmp_path, "cursor-agent", ["chat", "explain --model flag"])
    assert output is not None
    assert "ARGV: --model gpt-5.6-sol-high chat explain --model flag" in output


def test_cursor_agent_model_body_declares_the_correct_command_guard_invariant() -> None:
    body = _bundle("cursor-agent-model").body
    unalias_index = body.index("unalias cursor-agent cursor")
    agent_fn_index = body.index("function cursor-agent")
    cursor_fn_index = body.index("function cursor ")
    assert unalias_index < agent_fn_index
    assert unalias_index < cursor_fn_index

    agent_block = body[agent_fn_index:cursor_fn_index]
    for line in agent_block.splitlines():
        if "cursor-agent" in line and "function" not in line:
            assert "command cursor-agent" in line, line

    cursor_block = body[cursor_fn_index:]
    assert "command cursor-agent" not in cursor_block
    assert 'cursor-agent "$@"' in cursor_block
    assert cursor_block.count("cursor-agent") == 1


def test_cursor_agent_wrapper_removes_a_pre_existing_conflicting_alias(tmp_path: Path) -> None:
    preamble = (
        "shopt -s expand_aliases\n"
        "alias cursor-agent='echo PRE_EXISTING_ALIAS'\n"
        "alias cursor='echo PRE_EXISTING_ALIAS_CURSOR'\n"
    )
    output = _run_cursor_agent(tmp_path, "cursor-agent", ["chat", "hello"], preamble=preamble)
    assert output is not None
    assert "PRE_EXISTING_ALIAS" not in output
    assert "ARGV: --model gpt-5.6-sol-high chat hello" in output


def test_cursor_agent_wrapper_removes_a_pre_existing_conflicting_alias_under_zsh(
    tmp_path: Path,
) -> None:
    if shutil.which("zsh") is None:
        pytest.skip("zsh not available")
    preamble = (
        "alias cursor-agent='echo PRE_EXISTING_ALIAS'\n"
        "alias cursor='echo PRE_EXISTING_ALIAS_CURSOR'\n"
    )
    output = _run_cursor_agent(
        tmp_path, "cursor-agent", ["chat", "hello"], shell="zsh", preamble=preamble
    )
    assert output is not None
    assert "PRE_EXISTING_ALIAS" not in output
    assert "ARGV: --model gpt-5.6-sol-high chat hello" in output


def test_cursor_agent_model_behavior_under_zsh_when_available(tmp_path: Path) -> None:
    if shutil.which("zsh") is None:
        pytest.skip("zsh not available")
    default_output = _run_cursor_agent(tmp_path, "cursor-agent", ["chat", "hello"], shell="zsh")
    assert default_output is not None
    assert "ARGV: --model gpt-5.6-sol-high chat hello" in default_output

    delegate_output = _run_cursor_agent(tmp_path, "cursor", ["chat", "hello"], shell="zsh")
    assert delegate_output is not None
    assert "ARGV: --model gpt-5.6-sol-high chat hello" in delegate_output


def test_write_then_present_then_remove_roundtrip(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("countdown")
    assert tweak_present(bundle, rc) is False
    write_tweak(bundle, rc)
    assert tweak_present(bundle, rc) is True
    assert "wait_time()" in rc.read_text()
    remove_tweak(bundle, rc)
    assert tweak_present(bundle, rc) is False
    assert "wait_time()" not in rc.read_text()


def test_re_enable_does_not_duplicate(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("claude-skip")
    write_tweak(bundle, rc)
    write_tweak(bundle, rc)
    assert rc.read_text().count("# >>> tools-installer tweak:claude-skip >>>") == 1


def test_toggling_one_bundle_leaves_another_and_user_content_intact(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    write_tweak(_bundle("docker"), rc)
    write_tweak(_bundle("countdown"), rc)
    remove_tweak(_bundle("docker"), rc)
    text = rc.read_text()
    assert "export EDITOR=vim" in text
    assert "wait_time()" in text
    assert "docker-ps()" not in text


def test_remove_on_missing_file_is_noop(tmp_path: Path) -> None:
    remove_tweak(_bundle("docker"), tmp_path / "nope")


def test_remove_absent_block_leaves_file_unchanged(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    remove_tweak(_bundle("docker"), rc)
    assert rc.read_text() == "export EDITOR=vim\n"


def _platform(os_name: str) -> Platform:
    return Platform(os=os_name, arch="arm64", immutable=False, has_brew=False)


def test_apt_upgrade_offered_on_linux_absent_on_macos() -> None:
    linux_ids = [b.id for b in applicable_bundles(_platform("debian"))]
    macos_ids = [b.id for b in applicable_bundles(_platform("macos"))]
    assert "apt-upgrade" in linux_ids
    assert "apt-upgrade" not in macos_ids
    assert {"docker", "countdown", "claude-skip"} <= set(macos_ids)
