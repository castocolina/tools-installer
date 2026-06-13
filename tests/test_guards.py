import subprocess
from pathlib import Path

from installer.guards import (
    BAN_BEGIN,
    BAN_END,
    BANNED,
    SHIM_SENTINEL,
    ban_alias_block,
    guard_status,
    install_shims,
    is_our_shim,
    remove_ban_aliases,
    remove_shims,
    shim_script,
    write_ban_aliases,
)


def test_shim_script_names_the_replacement_and_exits_nonzero():
    script = shim_script("pip")
    assert SHIM_SENTINEL in script
    assert "uv" in script  # the sanctioned replacement for pip
    assert "exit 127" in script


def test_shim_script_is_valid_posix_sh(tmp_path: Path):
    for name in BANNED:
        shim = tmp_path / name
        shim.write_text(shim_script(name))
        result = subprocess.run(["sh", "-n", str(shim)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_is_our_shim_detects_the_sentinel(tmp_path: Path):
    ours = tmp_path / "pip"
    ours.write_text(shim_script("pip"))
    assert is_our_shim(ours) is True


def test_is_our_shim_false_for_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    assert is_our_shim(real) is False


def test_is_our_shim_false_when_unreadable(tmp_path: Path):
    # A directory named like a tool: read_text raises OSError -> treated as not ours.
    (tmp_path / "pip").mkdir()
    assert is_our_shim(tmp_path / "pip") is False


def test_install_shims_creates_each_banned_shim(tmp_path: Path):
    actions = install_shims(tmp_path)
    assert actions == {name: "created" for name in BANNED}
    for name in BANNED:
        shim = tmp_path / name
        assert is_our_shim(shim)
        assert shim.stat().st_mode & 0o111  # executable


def test_install_shims_is_idempotent_and_reports_refreshed(tmp_path: Path):
    install_shims(tmp_path)
    actions = install_shims(tmp_path)
    assert actions == {name: "refreshed" for name in BANNED}


def test_install_shims_never_overwrites_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    actions = install_shims(tmp_path)
    assert actions["pip"] == "skipped (real binary here)"
    assert real.read_text() == "#!/bin/sh\necho real pip\n"  # untouched


def test_remove_shims_removes_only_ours(tmp_path: Path):
    install_shims(tmp_path)
    # replace our npm shim with a real one
    (tmp_path / "npm").write_text("#!/bin/sh\necho real npm\n")
    actions = remove_shims(tmp_path)
    assert actions["pip"] == "removed"
    assert actions["npm"] == "absent"  # not ours -> left alone
    assert (tmp_path / "npm").exists()
    assert not (tmp_path / "pip").exists()


def test_guard_status_reports_installed_ours(tmp_path: Path):
    install_shims(tmp_path)
    (tmp_path / "pip").unlink()
    status = guard_status(tmp_path)
    assert status["npm"] is True
    assert status["pip"] is False


def test_ban_alias_block_aliases_each_banned_command():
    block = ban_alias_block()
    assert block.startswith(BAN_BEGIN)
    assert block.rstrip().endswith(BAN_END)
    for name in BANNED:
        assert f"alias {name}=" in block


def test_write_ban_aliases_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    write_ban_aliases(rc)
    write_ban_aliases(rc)
    text = rc.read_text()
    assert "# user content" in text
    assert text.count(BAN_BEGIN) == 1  # not duplicated


def test_remove_ban_aliases_strips_block_preserving_user_content(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    write_ban_aliases(rc)
    remove_ban_aliases(rc)
    text = rc.read_text()
    assert "# user content" in text
    assert BAN_BEGIN not in text


def test_remove_ban_aliases_missing_file_is_noop(tmp_path: Path):
    remove_ban_aliases(tmp_path / "nope")  # must not raise


def test_remove_ban_aliases_no_block_is_noop(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    remove_ban_aliases(rc)
    assert rc.read_text() == "# user content\n"
