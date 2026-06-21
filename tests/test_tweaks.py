import shutil
import subprocess
from pathlib import Path

from installer.platform import Platform
from installer.tweaks import (
    BUNDLES,
    TweakBundle,
    applicable_bundles,
    remove_tweak,
    tweak_block,
    tweak_present,
    write_tweak,
)


def _bundle(bundle_id: str) -> TweakBundle:
    return next(b for b in BUNDLES if b.id == bundle_id)


def test_four_bundles_with_stable_ids() -> None:
    assert [b.id for b in BUNDLES] == ["docker", "countdown", "claude-skip", "apt-upgrade"]


def test_block_is_marker_delimited_around_body() -> None:
    bundle = _bundle("claude-skip")
    block = tweak_block(bundle)
    assert block.startswith("# >>> tools-installer tweak:claude-skip >>>\n")
    assert block.endswith("\n# <<< tools-installer tweak:claude-skip <<<")
    assert bundle.body in block


def test_countdown_uses_printf_not_echo_ne() -> None:
    body = _bundle("countdown").body
    assert "printf" in body
    assert "echo -ne" not in body


def test_docker_body_has_all_three_helpers() -> None:
    body = _bundle("docker").body
    assert "docker-ps()" in body
    assert "alias docker-stats=" in body
    assert "alias docker-memory='docker-stats'" in body


def test_every_block_parses_in_bash(tmp_path: Path) -> None:
    # ~/.myshellrc is sourced by interactive bash/zsh, so bash is the validity
    # target — not /bin/sh: hyphenated names like docker-ps() are valid in
    # bash/zsh but not strict POSIX sh. bash is present on macOS and on CI.
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to validate tweak bodies"
    for bundle in BUNDLES:
        script = tmp_path / f"{bundle.id}.bash"
        script.write_text(bundle.body + "\n")
        result = subprocess.run([bash, "-n", str(script)], capture_output=True)
        assert result.returncode == 0, f"bash {bundle.id}: {result.stderr!r}"


def test_blocks_parse_in_bash_and_zsh_when_present(tmp_path: Path) -> None:
    for shell in ("bash", "zsh"):
        binary = shutil.which(shell)
        if binary is None:
            continue
        for bundle in BUNDLES:
            script = tmp_path / f"{bundle.id}.{shell}"
            script.write_text(bundle.body + "\n")
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
