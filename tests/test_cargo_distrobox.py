"""The `cargo_distrobox` kind: Alacritty built in a throwaway box, placed, recorded, removed."""

from collections.abc import Callable
from pathlib import Path

import pytest

import installer.engine as engine
from installer import cargo_distrobox, receipts
from installer.enums import InstallStatus
from installer.model import Tool, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.uninstall import removal_plan, remove_paths
from tests.test_desktop_entry import UPSTREAM as UPSTREAM_DESKTOP

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
IMAGE = "registry.fedoraproject.org/fedora-toolbox:44"
PREFIX_LENGTH = 5  # timeout --kill-after=10 <seconds> env XDG_CACHE_HOME=<dir>
BUILT_BINARY = "#!/bin/sh\necho 'alacritty 0.17.0'\n"
ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg"/>\n'


def alacritty_tool() -> Tool:
    return next(tool for tool in load_tools(REGISTRY) if tool.id == "alacritty")


def immutable_with_tools() -> Platform:
    return Platform(
        os="fedora",
        arch="amd64",
        immutable=True,
        has_brew=False,
        has_distrobox=True,
        has_podman=True,
    )


def inner(argv: list[str]) -> list[str]:
    """The argv with the `timeout ... env XDG_CACHE_HOME=...` prefix removed."""
    assert argv[0] == "timeout"
    assert argv[1] == "--kill-after=10"
    assert argv[3] == "env"
    assert argv[4].startswith("XDG_CACHE_HOME=")
    return argv[PREFIX_LENGTH:]


def step_of(argv: list[str]) -> str:
    words = inner(argv)
    if words[:2] == ["distrobox", "create"]:
        return "create"
    if words[:2] == ["distrobox", "rm"]:
        return "rm"
    if words[:2] == ["podman", "rmi"]:
        return "rmi"
    assert words[:2] == ["distrobox", "enter"], words
    command = words[words.index("--") + 1 :]
    return {"git": "clone", "cargo": "build", "tic": "tic"}[command[0]]


class FakeBox:
    """A recording runner standing in for distrobox and podman; it writes what the build makes."""

    def __init__(self, fail: dict[str, BaseException] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail or {}
        self.tmp: Path | None = None

    def steps(self) -> list[str]:
        return [step_of(call) for call in self.calls]

    def __call__(self, argv: list[str]) -> None:
        self.calls.append(list(argv))
        step = step_of(argv)
        if step == "create":
            words = inner(argv)
            self.tmp = Path(words[words.index("--home") + 1])
        if step in self.fail:
            raise self.fail[step]
        if step == "build":
            assert self.tmp is not None
            self._write("src/target/release/alacritty", BUILT_BINARY, 0o755)
            self._write("src/extra/linux/Alacritty.desktop", UPSTREAM_DESKTOP, 0o644)
            self._write("src/extra/logo/alacritty-term.svg", ICON_SVG, 0o644)
        if step == "tic":
            self._write("terminfo/a/alacritty", "compiled alacritty\n", 0o644)
            self._write("terminfo/a/alacritty-direct", "compiled direct\n", 0o644)

    def _write(self, relative: str, text: str, mode: int) -> None:
        assert self.tmp is not None
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)


def image_is(state: bool | None) -> Callable[[str], bool | None]:
    def exists(_ref: str) -> bool | None:
        return state

    return exists


@pytest.fixture(autouse=True)
def scratch_run_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "run-root"
    root.mkdir()
    monkeypatch.setattr(cargo_distrobox, "RUN_ROOT", root)
    monkeypatch.setattr(cargo_distrobox, "image_exists", image_is(False))
    return root


def install(runner: Callable[[list[str]], None], tag: str = "v0.17.0") -> engine.InstallOutcome:
    return engine.install_tool(
        alacritty_tool(),
        immutable_with_tools(),
        runner=runner,
        resolve_tag=lambda _repo: tag,
        present=lambda _tool: False,
    )


def host_paths() -> list[Path]:
    home = Path.home()
    return [
        home / ".local/bin/alacritty",
        home / ".local/share/applications/Alacritty.desktop",
        home / ".local/share/icons/hicolor/scalable/apps/Alacritty.svg",
        home / ".terminfo/a/alacritty",
        home / ".terminfo/a/alacritty-direct",
    ]


def test_alacritty_installs_and_uninstalls_through_the_shipped_entry(tmp_path: Path) -> None:
    tool = alacritty_tool()
    methods = resolve_methods(tool, immutable_with_tools())
    assert methods[0].kind == "cargo_distrobox"

    box = FakeBox()
    outcome = install(box)

    assert outcome.status is InstallStatus.INSTALLED
    assert outcome.method_kind == "cargo_distrobox"
    assert outcome.verified is False
    assert outcome.postinstall_warning is None
    assert outcome.handoff == ()
    assert all(path.exists() for path in host_paths())
    desktop = host_paths()[1].read_text(encoding="utf-8")
    assert f"Exec={host_paths()[0]}" in desktop.splitlines()
    assert f"Icon={host_paths()[2]}" in desktop.splitlines()

    receipt = receipts.read("alacritty")
    assert receipt is not None
    assert [(artifact.path, artifact.type) for artifact in receipt.artifacts] == [
        (host_paths()[0], "file"),
        *[(path, "leaf") for path in host_paths()[1:]],
    ]
    assert receipt.smoke == "ok"

    plan = removal_plan(tool, Path.home() / ".local/bin")
    assert plan.level == "artifacts"
    assert sorted(plan.removable) == sorted(host_paths())
    assert remove_paths([plan.artifacts[path] for path in plan.removable]) == ()
    assert not any(path.exists() for path in host_paths())
    home = Path.home()
    assert not (home / ".terminfo").exists()
    assert not (home / ".local/share/icons/hicolor").exists()
    assert (home / ".local/share/applications").is_dir()
    assert (home / ".local/share/icons").is_dir()
