import pytest

from installer.assets import ArchTokens, arch_tokens, render_asset


def test_arch_tokens_amd64():
    tokens = arch_tokens("amd64")
    assert isinstance(tokens, ArchTokens)
    assert tokens.machine == "x86_64"
    assert tokens.deb == "amd64"
    assert tokens.go == "amd64"
    assert tokens.suffix == "x86_64"


def test_arch_tokens_arm64():
    tokens = arch_tokens("arm64")
    assert tokens.machine == "aarch64"
    assert tokens.deb == "arm64"
    assert tokens.go == "arm64"
    assert tokens.suffix == "arm64"


def test_arch_tokens_unsupported_raises():
    with pytest.raises(ValueError, match="unsupported architecture"):
        arch_tokens("riscv64")


def test_render_asset_substitutes_ver_and_arch():
    out = render_asset("rg-{ver}-{arch.machine}-linux.tar.gz", "14.1.0", arch_tokens("amd64"))
    assert out == "rg-14.1.0-x86_64-linux.tar.gz"


def test_render_asset_substitutes_go_and_suffix():
    out = render_asset("tool-{arch.go}-{arch.suffix}.tgz", "1.0", arch_tokens("amd64"))
    assert out == "tool-amd64-x86_64.tgz"


def test_render_asset_supports_ver_only():
    assert render_asset("tool-{ver}.tgz", "1.2.3", arch_tokens("arm64")) == "tool-1.2.3.tgz"


def test_render_asset_bad_placeholder_raises():
    with pytest.raises(ValueError, match="bad asset template"):
        render_asset("rg-{nope}.tar.gz", "1.0", arch_tokens("amd64"))
