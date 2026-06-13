import subprocess
from pathlib import Path

from installer.guards import BANNED, SHIM_SENTINEL, is_our_shim, shim_script


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
