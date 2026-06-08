from pathlib import Path

import pytest

from installer.platform import (
    Platform,
    detect,
    detect_immutable,
    detect_os,
    normalize_arch,
)


def test_normalize_arch_known():
    assert normalize_arch("x86_64") == "amd64"
    assert normalize_arch("aarch64") == "arm64"


def test_normalize_arch_passthrough():
    assert normalize_arch("riscv64") == "riscv64"


def test_detect_os_macos():
    assert detect_os("Darwin", lambda cmd: False) == "macos"


def test_detect_os_fedora_via_dnf():
    assert detect_os("Linux", lambda cmd: cmd == "dnf") == "fedora"


def test_detect_os_fedora_via_rpm_ostree():
    assert detect_os("Linux", lambda cmd: cmd == "rpm-ostree") == "fedora"


def test_detect_os_debian():
    assert detect_os("Linux", lambda cmd: cmd == "apt-get") == "debian"


def test_detect_os_arch():
    assert detect_os("Linux", lambda cmd: cmd == "pacman") == "arch"


def test_detect_os_unsupported_raises():
    with pytest.raises(RuntimeError):
        detect_os("Linux", lambda cmd: False)


def test_detect_immutable_true(tmp_path: Path):
    marker = tmp_path / "ostree-booted"
    marker.write_text("")
    assert detect_immutable(marker) is True


def test_detect_immutable_false(tmp_path: Path):
    assert detect_immutable(tmp_path / "ostree-booted") is False


def test_detect_uses_live_probes(monkeypatch: pytest.MonkeyPatch):
    import installer.platform as plat

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/x" if cmd in ("dnf", "brew") else None

    monkeypatch.setattr(plat.stdlib_platform, "system", lambda: "Linux")
    monkeypatch.setattr(plat.stdlib_platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(plat.shutil, "which", fake_which)
    monkeypatch.setattr(plat, "detect_immutable", lambda: False)

    result = detect()
    assert isinstance(result, Platform)
    assert result.os == "fedora"
    assert result.arch == "amd64"
    assert result.has_brew is True
    assert result.immutable is False
