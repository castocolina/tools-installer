"""Neovim on the shipped catalog entry: a github_release tarball, a receipt, and its removal.

The runner is a fake that writes the files the real tar and curl would leave, so no test launches
curl, tar or git, and the release digest is pinned through `engine.release_resolver`.
"""

import hashlib
import os
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
from tests.test_post_install import use_fake_git

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


def _remove(tool: Tool, config: dict[str, tuple[Path, ...]] | None = None) -> SweepResult:
    bin_dir = Path.home() / ".local/bin"
    plan = removal_plan(tool, bin_dir)
    decision = UninstallDecision(
        tools=(tool,),
        paths={tool.id: plan.removable},
        argv={tool.id: plan.argv},
        remove_ban=False,
        remove_path_block=False,
        config=dict(config or {}),
    )
    return perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=Path.home() / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=Path.home() / ".zshrc",
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


def test_neovim_config_goes_only_with_the_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = neovim_tool()
    init = _seed_config()
    _install(FakeTarball(), monkeypatch)

    result = _remove(tool, config={"neovim": (init.parent,)})

    assert result.removed == ("neovim",)
    assert result.config_deleted == ("neovim",)
    assert not init.parent.exists()


def test_neovim_second_removal_plans_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = neovim_tool()
    _install(FakeTarball(), monkeypatch)
    _remove(tool)
    opt = Path.home() / ".local/opt/nvim"

    # A `none` plan is never sent to the sweep: the UI offers no row, and remove_tool refuses an
    # empty preview. The idempotency claim is the plan itself plus nothing left to delete.
    plan = removal_plan(tool, Path.home() / ".local/bin")

    assert plan.level == "none"
    assert plan.removable == ()
    assert not opt.exists()


def test_neovim_opt_tree_goes_whole_with_a_dropped_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins the provisional D-03 refinement (24.1, 2026-11-13, needs confirmation).

    A file dropped into the installer's own opt tree goes with the tree, as an update replaces
    it. Keeping SPEC R3's original clause (only the receipt's own paths) would need a generic
    per-member manifest instead, which is a new plan; reversing this test is the switch.
    """
    tool = neovim_tool()
    _install(FakeTarball(), monkeypatch)
    opt = Path.home() / ".local/opt/nvim"
    dropped = opt / "notes.txt"
    dropped.write_text("dropped by the user\n", encoding="utf-8")

    plan = removal_plan(tool, Path.home() / ".local/bin")

    assert opt in plan.removable
    assert plan.artifacts[opt].type == "dir"
    assert _remove(tool).removed == ("neovim",)
    assert not opt.exists()
    assert not dropped.exists()


def test_neovim_removal_while_nvim_runs_keeps_open_inodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPEC R3 concurrency backstop: a running nvim holds its runtime files open."""
    tool = neovim_tool()
    _install(FakeTarball(), monkeypatch)
    runtime_file = Path.home() / ".local/opt/nvim/share/nvim/runtime/syntax/vim.vim"

    with runtime_file.open("rb") as handle:
        result = _remove(tool)
        assert result.removed == ("neovim",)
        assert result.remove_failed == ()
        assert not runtime_file.exists()
        assert handle.read() == b'" vim syntax\n'


@pytest.mark.parametrize("payload", [b"", PAYLOAD[:-1]], ids=["empty", "one-byte-short"])
def test_truncated_neovim_archive_leaves_nothing(
    payload: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC R2 empty-archive backstop: the full payload's digest rejects a bad download."""
    runner = FakeTarball(payload=payload)

    outcome = _install(runner, monkeypatch)

    home = Path.home()
    assert outcome.status is InstallStatus.CHECKSUM_MISMATCH
    assert not any(call[0] == "tar" for call in runner.calls)
    assert not (home / ".local/opt").exists() or not any((home / ".local/opt").iterdir())
    assert not (home / ".local/bin/nvim").exists()
    assert not (home / ".local/bin/nvim").is_symlink()
    assert receipts.read("neovim") is None


def test_an_unowned_nvim_on_path_is_never_overwritten(monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEC R2 adjacency backstop: a foreign nvim on PATH is left alone, byte for byte."""
    bin_dir = Path.home() / ".local/bin"
    bin_dir.mkdir(parents=True)
    foreign = bin_dir / "nvim"
    foreign.write_bytes(b"#!/bin/sh\necho foreign\n")
    foreign.chmod(0o755)
    before = foreign.read_bytes()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    runner = FakeTarball()

    outcome = engine.install_tool(
        neovim_tool(), BAZZITE, runner=runner, resolve_tag=lambda _repo: TAG
    )

    assert outcome.status is InstallStatus.ALREADY_INSTALLED
    assert runner.calls == []
    assert foreign.read_bytes() == before
    assert receipts.read("neovim") is None


def _receipt_artifacts() -> list[tuple[Path, str]]:
    receipt = receipts.read("neovim")
    assert receipt is not None
    return [(artifact.path, artifact.type) for artifact in receipt.artifacts]


def test_a_failed_starter_clone_keeps_the_neovim_row_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_fake_git(monkeypatch, fail_at="clone")

    outcome = _install(FakeTarball(), monkeypatch)

    home = Path.home()
    assert outcome.status is InstallStatus.INSTALLED
    assert outcome.postinstall_warning is None
    assert "Starter not added: fatal: boom." in outcome.post_install_handoff
    assert any(":lsp enable <name>" in line for line in outcome.post_install_handoff)
    assert _receipt_artifacts() == [
        (home / ".local/opt/nvim", "dir"),
        (home / ".local/bin/nvim", "link"),
    ]
    assert not (home / ".config/nvim").exists()


def test_the_starter_tree_is_not_in_the_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = use_fake_git(monkeypatch)

    outcome = _install(FakeTarball(), monkeypatch)

    home = Path.home()
    assert outcome.status is InstallStatus.INSTALLED
    assert len(fake.calls) == 5
    assert (home / ".config/nvim/init.lua").is_file()
    assert _receipt_artifacts() == [
        (home / ".local/opt/nvim", "dir"),
        (home / ".local/bin/nvim", "link"),
    ]

    result = _remove(neovim_tool())

    assert result.removed == ("neovim",)
    assert (home / ".config/nvim/init.lua").is_file()  # config stays unless "delete config too"
