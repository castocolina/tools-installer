import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from installer import tweaks as tweaks_module
from installer.helper_assets import wait_time
from installer.omz import plugins_owned
from installer.platform import Platform
from installer.tweaks import (
    BUNDLES,
    SHELL_INIT_TOOLS,
    TweakBundle,
    applicable_bundles,
    bundle_marker_present,
    install_tweak_executables,
    remove_tweak,
    remove_tweak_executables,
    shell_init_bundle,
    strip_legacy_aliases,
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
        "apt-upgrade",
        "starship",
        "direnv",
        "zoxide",
        "fzf",
        "fnm",
        "volta",
    ]


def test_block_is_marker_delimited_around_body() -> None:
    bundle = _bundle("docker")
    block = tweak_block(bundle)
    assert block.startswith("# >>> tools-installer tweak:docker >>>\n")
    assert block.endswith("\n# <<< tools-installer tweak:docker <<<")
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


def _plant_uv_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "uv-bin" / "uv"
    stub.parent.mkdir(exist_ok=True)
    interpreter = shlex.quote(sys.executable)
    stub.write_text(
        "#!/bin/sh\n"
        'while [ "${1:-}" != "--script" ]; do shift; done\n'
        "shift\n"
        f'exec {interpreter} "$@"\n'
    )
    stub.chmod(0o755)
    return stub.parent


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
    env = os.environ | {
        "PATH": f"{_plant_uv_stub(tmp_path)}{os.pathsep}{os.environ['PATH']}",
        "WAIT_TIME_NOW": now,
    }
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
    env = os.environ | {
        "PATH": f"{_plant_uv_stub(tmp_path)}{os.pathsep}{os.environ['PATH']}",
        "WAIT_TIME_CLOCK": clock,
    }
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
    assert tweak_executables_present(_bundle("docker"), bin_dir) is False
    assert tweak_executables_present(_bundle("docker"), tmp_path / "empty-bin") is False


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


def test_bundle_marker_present_reads_the_begin_marker(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("countdown")
    assert bundle_marker_present(bundle.id, rc) is False
    rc.write_text("# >>> tools-installer tweak:countdown >>>x\n")
    assert bundle_marker_present(bundle.id, rc) is False
    assert tweak_present(bundle, rc) is False
    rc.write_text("# >>> tools-installer tweak:countdown >>>\n")
    assert bundle_marker_present(bundle.id, rc) is True
    assert tweak_present(bundle, rc) is True


def test_bundle_marker_present_never_blocks_on_a_fifo(tmp_path: Path) -> None:
    """O-1: a FIFO at ~/.myshellrc reads as no marker instead of hanging the launch."""
    import os
    import threading

    rc = tmp_path / ".myshellrc"
    os.mkfifo(rc)
    answers: list[bool] = []
    reader = threading.Thread(
        target=lambda: answers.append(bundle_marker_present("countdown", rc)), daemon=True
    )
    reader.start()
    reader.join(timeout=5)
    if reader.is_alive():
        os.close(os.open(rc, os.O_WRONLY | os.O_NONBLOCK))  # release the blocked reader
        reader.join(timeout=5)
    assert answers == [False]


def test_re_enable_does_not_duplicate(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("docker")
    write_tweak(bundle, rc)
    write_tweak(bundle, rc)
    assert rc.read_text().count("# >>> tools-installer tweak:docker >>>") == 1


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
    assert {"docker", "countdown"} <= set(macos_ids)


def test_shell_init_bundles_sit_after_apt_upgrade_in_tool_order() -> None:
    ids = [b.id for b in BUNDLES]
    start = ids.index("apt-upgrade") + 1
    assert tuple(ids[start : start + len(SHELL_INIT_TOOLS)]) == SHELL_INIT_TOOLS


@pytest.mark.parametrize("tool", SHELL_INIT_TOOLS)
def test_each_shell_init_body_is_guarded_and_parses(tool: str) -> None:
    bundle = shell_init_bundle(tool)
    assert bundle is not None
    assert bundle.id == tool
    assert bundle.requires == (tool,)
    assert bundle.body.split("\n")[0] == f"if command -v {tool} >/dev/null; then"
    result = subprocess.run(
        ["bash", "-n", "-c", bundle.body], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is not on PATH; zsh -n not run")
@pytest.mark.parametrize("tool", SHELL_INIT_TOOLS)
def test_each_shell_init_body_parses_in_zsh(tool: str) -> None:
    bundle = shell_init_bundle(tool)
    assert bundle is not None
    result = subprocess.run(
        ["zsh", "-n", "-c", bundle.body], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def _legacy_block(alias_id: str, body: str) -> str:
    marker = f"tools-installer tweak:{alias_id}"
    return f"# >>> {marker} >>>\n{body}\n# <<< {marker} <<<\n"


_CLAUDE_ALIAS = "alias claude='claude --dangerously-skip-permissions'"
_CODEX_ALIAS = "alias codex='codex --dangerously-bypass-approvals-and-sandbox'"


def test_an_enabled_claude_skip_alias_is_stripped_and_nothing_written() -> None:
    rc = Path.home() / ".myshellrc"
    rc.write_text("export KEEP=1\n" + _legacy_block("claude-skip", _CLAUDE_ALIAS))
    report = strip_legacy_aliases(rc)
    assert report.stripped == ("claude-skip",)
    assert rc.read_text() == "export KEEP=1\n"
    assert not (Path.home() / ".claude" / "settings.json").exists()
    assert not (Path.home() / ".local" / "state" / "tools-installer" / "config").exists()
    assert report.launch_lines() == (
        ("Removed the claude-skip alias; turn on claude auto-approve in Policies.", "ok"),
    )
    again = strip_legacy_aliases(rc)
    assert again.stripped == ()
    assert again.launch_lines() == ()


def test_the_cursor_model_alias_is_removed_and_nothing_written() -> None:
    rc = Path.home() / ".myshellrc"
    rc.write_text(_legacy_block("cursor-agent-model", "function cursor-agent {\n}"))
    report = strip_legacy_aliases(rc)
    assert report.stripped == ("cursor-agent-model",)
    assert not (Path.home() / ".cursor" / "cli-config.json").exists()
    assert report.launch_lines() == (
        ("cursor-agent-model alias removed: pick the model with /model in cursor-agent.", "warn"),
    )


def test_a_block_that_cannot_be_edited_is_kept_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rc = Path.home() / ".myshellrc"
    text = _legacy_block("claude-skip", _CLAUDE_ALIAS)
    rc.write_text(text)

    def refuse(path: Path, content: str, **_: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(tweaks_module, "atomic_write_text", refuse)
    report = strip_legacy_aliases(rc)
    assert report.stripped == ()
    assert report.failed == (("claude-skip", "denied"),)
    assert rc.read_text() == text
    assert report.launch_lines() == (
        ("Could not remove the claude-skip alias from ~/.myshellrc: denied.", "warn"),
    )


def test_uninstall_line_names_every_stripped_alias() -> None:
    rc = Path.home() / ".myshellrc"
    blocks = _legacy_block("claude-skip", _CLAUDE_ALIAS) + _legacy_block("codex-skip", _CODEX_ALIAS)
    rc.write_text(blocks)
    report = strip_legacy_aliases(rc)
    assert report.uninstall_line() == (
        "Removed the claude-skip, codex-skip alias block(s) from ~/.myshellrc."
    )
    assert strip_legacy_aliases(rc).uninstall_line() is None


def test_an_unreadable_rc_is_reported_and_never_raises() -> None:
    rc = Path.home() / ".myshellrc"
    latin1 = b"# caf\xe9\n" + _legacy_block("claude-skip", _CLAUDE_ALIAS).encode()
    rc.write_bytes(latin1)
    report = strip_legacy_aliases(rc)
    assert report.stripped == ()
    assert rc.read_bytes() == latin1
    assert tweaks_module.bundle_marker_present("claude-skip", rc)
    assert report.launch_lines() == (
        (
            "Could not check ~/.myshellrc for legacy alias blocks: not valid UTF-8; "
            "nothing was changed.",
            "warn",
        ),
    )
    rc.unlink()
    rc.mkdir()
    assert not tweaks_module.bundle_marker_present("claude-skip", rc)
    assert not plugins_owned(rc)
    [(text, severity)] = strip_legacy_aliases(rc).launch_lines()
    assert severity == "warn"
    assert text.startswith("Could not check ~/.myshellrc for legacy alias blocks: ")
