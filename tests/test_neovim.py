"""Neovim on the shipped catalog entry: a github_release tarball, a receipt, and its removal.

The runner is a fake that writes the files the real tar and curl would leave, so no test launches
curl, tar or git, and the release digest is pinned through `engine.release_resolver`.
"""

import hashlib
from pathlib import Path

import pytest

import installer.engine as engine
from installer import receipts
from installer.app import UninstallDecision, perform_uninstall
from installer.download import ExecContext, resolve_target
from installer.enums import InstallStatus
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.uninstall import SweepResult, removal_plan
from installer.versions import Release, ReleaseResolver, TagResolver

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
TAG = "v0.12.6"
ASSET = "nvim-linux-x86_64.tar.gz"
PAYLOAD = b"fixture neovim tarball"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
BAZZITE = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)
SEED_INIT = b'vim.g.mapleader = " "\n'


def neovim_tool() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "neovim")


class FakeTarball:
    """Records argv; `curl -o` writes the payload and `tar -C` plants the stripped tree."""

    def __init__(self, payload: bytes = PAYLOAD) -> None:
        self.payload = payload
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> None:
        self.calls.append(list(argv))
        if argv[0] == "curl":
            Path(argv[argv.index("-o") + 1]).write_bytes(self.payload)
            return
        if argv[0] == "tar":
            _plant_tree(Path(argv[argv.index("-C") + 1]))
            return
        raise AssertionError(f"unexpected command: {argv}")


def _plant_tree(dest: Path) -> None:
    binary = dest / "bin/nvim"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\necho 'NVIM v0.12.6'\n", encoding="utf-8")
    binary.chmod(0o755)
    (dest / "lib/nvim").mkdir(parents=True, exist_ok=True)
    (dest / "lib/nvim/.keep").write_text("", encoding="utf-8")
    runtime = dest / "share/nvim/runtime/syntax"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "vim.vim").write_text('" vim syntax\n', encoding="utf-8")


def _pin_release(monkeypatch: pytest.MonkeyPatch, digest: str = DIGEST) -> None:
    release = Release(TAG, {ASSET: digest})

    def pinned(_resolve_tag: TagResolver) -> ReleaseResolver:
        return lambda _repo: release

    monkeypatch.setattr(engine, "release_resolver", pinned)


def _install(runner: FakeTarball, monkeypatch: pytest.MonkeyPatch) -> engine.InstallOutcome:
    _pin_release(monkeypatch)
    return engine.install_tool(neovim_tool(), BAZZITE, runner=runner, present=lambda _tool: False)


def _seed_config() -> Path:
    init = Path.home() / ".config/nvim/init.lua"
    init.parent.mkdir(parents=True)
    init.write_bytes(SEED_INIT)
    return init


def _remove(tool: Tool) -> SweepResult:
    bin_dir = Path.home() / ".local/bin"
    plan = removal_plan(tool, bin_dir)
    decision = UninstallDecision(
        tools=(tool,),
        paths={tool.id: plan.removable},
        argv={tool.id: plan.argv},
        remove_ban=False,
        remove_path_block=False,
        config={},
    )
    return perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=Path.home() / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=Path.home() / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=lambda _argv: None,
        catalog=[tool],
    )


def test_neovim_installs_and_uninstalls_through_the_shipped_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = neovim_tool()
    assert resolve_methods(tool, BAZZITE)[0].kind == "github_release"
    init = _seed_config()

    outcome = _install(FakeTarball(), monkeypatch)

    home = Path.home()
    opt = home / ".local/opt/nvim"
    link = home / ".local/bin/nvim"
    assert outcome.status is InstallStatus.INSTALLED
    assert outcome.method_kind == "github_release"
    assert outcome.verified is True
    assert (opt / "bin/nvim").is_file()
    assert link.resolve() == (opt / "bin/nvim").resolve()

    receipt = receipts.read("neovim")
    assert receipt is not None
    assert [(artifact.path, artifact.type) for artifact in receipt.artifacts] == [
        (opt, "dir"),
        (link, "link"),
    ]
    assert receipt.release == TAG

    plan = removal_plan(tool, home / ".local/bin")
    assert plan.level == "artifacts"
    assert sorted(plan.removable) == sorted([opt, link])
    result = _remove(tool)

    assert result.removed == ("neovim",)
    assert not opt.exists()
    assert not link.is_symlink()
    assert receipts.read("neovim") is None
    assert init.read_bytes() == SEED_INIT


def _comment_above_neovim() -> str:
    """The contiguous comment block directly above neovim's `[[tool]]` header."""
    head = REGISTRY.read_text(encoding="utf-8").split('[[tool]]\nid = "neovim"')[0]
    return head.rsplit("\n\n", 1)[-1]


def test_neovim_entry_facts() -> None:
    tool = neovim_tool()
    assert (tool.name, tool.category, tool.cmd, tool.tier, tool.audience, tool.priority) == (
        "Neovim",
        "editor",
        "nvim",
        "user",
        "human",
        "P2",
    )
    assert tool.config_paths == ("~/.config/nvim",)
    assert tool.owner_probes == ("rpm-ostree", "dnf", "apt", "pacman")
    assert tool.requires == ()
    assert tool.postinstall is None
    assert [method.kind for method in tool.methods] == [
        "github_release",
        "github_release",
        "brew",
        "dnf",
        "apt",
        "pacman",
    ]
    for method in tool.methods[:2]:
        assert method.params["repo"] == "neovim/neovim"
        assert method.params["member"] == "bin/nvim"
        assert method.params["strip"] == 1
        assert "checksum" not in method.params
    comment = _comment_above_neovim()
    for fact in ("# Verified", "v0.12.6", "checksum", "AppImage"):
        assert fact in comment, fact


@pytest.mark.parametrize(
    ("platform", "kinds"),
    [
        (
            Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
            ["github_release", "dnf", "brew"],
        ),
        (
            Platform(os="debian", arch="amd64", immutable=False, has_brew=True),
            ["github_release", "apt", "brew"],
        ),
        (
            Platform(os="arch", arch="amd64", immutable=False, has_brew=True),
            ["github_release", "pacman", "brew"],
        ),
        (BAZZITE, ["github_release", "brew"]),
        (
            Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="26.0"),
            ["github_release", "brew"],
        ),
    ],
    ids=["fedora-mutable", "debian", "arch", "bazzite-immutable", "macos-arm64"],
)
def test_neovim_resolved_method_order(platform: Platform, kinds: list[str]) -> None:
    assert [method.kind for method in resolve_methods(neovim_tool(), platform)] == kinds


@pytest.mark.parametrize(
    ("os_name", "arch", "asset"),
    [
        ("debian", "amd64", "nvim-linux-x86_64.tar.gz"),
        ("fedora", "arm64", "nvim-linux-arm64.tar.gz"),
        ("macos", "amd64", "nvim-macos-x86_64.tar.gz"),
        ("macos", "arm64", "nvim-macos-arm64.tar.gz"),
    ],
)
def test_neovim_asset_resolves_for_every_os_arch(os_name: str, arch: str, asset: str) -> None:
    platform = Platform(os=os_name, arch=arch, immutable=False, has_brew=False, os_version="26.0")
    method = resolve_methods(neovim_tool(), platform)[0]
    assert method.kind == "github_release"
    ctx = ExecContext(
        runner=lambda _cmd: None,
        platform=platform,
        resolve_release=lambda _repo: Release(TAG, {asset: DIGEST}),
    )
    target = resolve_target(method, ctx)
    assert target.asset == asset
    assert target.url == f"https://github.com/neovim/neovim/releases/download/{TAG}/{asset}"
    assert target.member == "bin/nvim"
    assert target.sha256 == DIGEST
    assert target.unverified_reason is None
