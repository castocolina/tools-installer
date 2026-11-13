"""The `cargo_distrobox` kind: Alacritty built in a throwaway box, placed, recorded, removed."""

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

import installer.engine as engine
from installer import cargo_distrobox, receipts
from installer.atomic import NEW_SUFFIX, OLD_SUFFIX
from installer.download import ExecContext
from installer.enums import InstallStatus
from installer.executors import ExecutorError
from installer.model import Method, Tool, load_tools
from installer.platform import Platform
from installer.resolve import resolve_methods
from installer.run import CommandError
from installer.uninstall import removal_plan, remove_paths
from installer.versions import Release
from tests.test_desktop_entry import UPSTREAM as UPSTREAM_DESKTOP

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
IMAGE = "registry.fedoraproject.org/fedora-toolbox:44"
PREFIX_LENGTH = 6  # timeout --kill-after=10 <seconds> env XDG_CACHE_HOME=<dir> DBX_..=podman
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
    assert argv[5] == "DBX_CONTAINER_MANAGER=podman"
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
        self.binary_text = BUILT_BINARY

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
            self._write("src/target/release/alacritty", self.binary_text, 0o755)
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


def alacritty_method() -> Method:
    return next(m for m in alacritty_tool().methods if m.kind == "cargo_distrobox")


def context(runner: Callable[[list[str]], None], tag: str = "v0.17.0") -> ExecContext:
    return ExecContext(
        runner=runner,
        platform=immutable_with_tools(),
        resolve_release=lambda _repo: Release(tag, {}),
    )


def run_install(box: FakeBox, tag: str = "v0.17.0") -> tuple[str, ...]:
    return cargo_distrobox.install(alacritty_method(), context(box, tag))


def failed_build(returncode: int = 101) -> dict[str, BaseException]:
    error = CommandError(["cargo", "build"], returncode, detail="error: could not compile\nmore")
    return {"build": error}


def test_argv_order_and_flags(scratch_run_root: Path) -> None:
    box = FakeBox()
    run_install(box)

    assert box.steps() == ["create", "clone", "build", "tic", "rm", "rmi"]
    assert box.tmp is not None
    tmp = box.tmp
    assert tmp.parent == scratch_run_root
    create, clone, build, tic, remove, rmi = (inner(call) for call in box.calls)
    name = create[create.index("--name") + 1]
    assert create[:2] == ["distrobox", "create"]
    for flag in ("--yes", "--no-entry"):
        assert flag in create
    assert create[create.index("--home") + 1] == str(tmp)
    assert create[create.index("--image") + 1] == IMAGE
    packages = create[create.index("--additional-packages") + 1]
    assert packages == " ".join(cast(list[str], alacritty_method().params["packages"]))
    enter = ["distrobox", "enter", "--no-tty", "--no-workdir", "--name", name, "--"]
    assert clone == [
        *enter,
        *["git", "clone", "--depth", "1", "--branch", "v0.17.0", "--"],
        "https://github.com/alacritty/alacritty.git",
        str(tmp / "src"),
    ]
    assert build == [
        *enter,
        *["cargo", "build", "--release", "--locked"],
        *["--manifest-path", str(tmp / "src/Cargo.toml")],
    ]
    assert tic == [
        *enter,
        *["tic", "-xe", "alacritty,alacritty-direct", "-o", str(tmp / "terminfo")],
        str(tmp / "src/extra/alacritty.info"),
    ]
    assert remove == ["distrobox", "rm", "--force", "--rm-home", name]
    assert rmi == ["podman", "rmi", IMAGE]
    for call in box.calls:
        assert call[call.index("env") + 1] == f"XDG_CACHE_HOME={tmp / 'cache'}"
    assert not tmp.exists()


def test_box_name_is_collision_proof() -> None:
    first, second = cargo_distrobox.box_name("alacritty"), cargo_distrobox.box_name("alacritty")
    assert first != second
    for name in (first, second):
        assert re.fullmatch(r"ti-cargo-alacritty-\d+-[0-9a-f]{8}", name)


def test_no_argv_escalates() -> None:
    box = FakeBox()
    run_install(box)
    words = {word for call in box.calls for word in call}
    assert words.isdisjoint({"sudo", "pkexec", "doas"})


def test_build_failure_still_removes_the_box_and_the_pulled_image() -> None:
    box = FakeBox(failed_build())
    with pytest.raises(ExecutorError, match="error: could not compile"):
        run_install(box)

    assert box.steps() == ["create", "clone", "build", "rm", "rmi"]
    assert "--force" in inner(box.calls[-2])
    assert "--rm-home" in inner(box.calls[-2])
    assert "--force" not in inner(box.calls[-1])
    assert box.tmp is not None
    assert not box.tmp.exists()
    assert not any(path.exists() for path in host_paths())


def test_interrupt_still_removes_the_box() -> None:
    """Backstop: a KeyboardInterrupt in the build step runs both deletions and the cleanup."""
    box = FakeBox({"build": KeyboardInterrupt()})
    with pytest.raises(KeyboardInterrupt):
        run_install(box)

    assert box.steps() == ["create", "clone", "build", "rm", "rmi"]
    assert box.tmp is not None
    assert not box.tmp.exists()


def test_existing_image_is_kept_and_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cargo_distrobox, "image_exists", image_is(True))
    box = FakeBox()
    notes = run_install(box)

    assert "rmi" not in box.steps()
    assert notes == (f"kept the existing image {IMAGE}",)


def test_unknown_image_state_keeps_the_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cargo_distrobox, "image_exists", image_is(None))
    box = FakeBox()
    notes = run_install(box)

    assert "rmi" not in box.steps()
    assert notes == (f"kept the image {IMAGE}: could not tell whether it was already there",)


@pytest.mark.parametrize(
    ("raised", "expected"),
    [(None, True), (1, False), (125, None), (124, None), (127, None)],
)
def test_image_exists_is_tri_state(
    monkeypatch: pytest.MonkeyPatch, raised: int | None, expected: bool | None
) -> None:
    def fake_query(argv: list[str], **_kwargs: object) -> str:
        assert argv == ["podman", "image", "exists", IMAGE]
        if raised is not None:
            raise CommandError(argv, raised)
        return ""

    monkeypatch.setattr(cargo_distrobox, "run_query", fake_query)
    assert cargo_distrobox.podman_image_exists(IMAGE) is expected


def test_image_in_use_is_a_warning() -> None:
    error = CommandError(["podman", "rmi"], 2, detail="image is in use by a container")
    box = FakeBox({"rmi": error})
    notes = run_install(box)

    assert len(notes) == 1
    assert IMAGE in notes[0]
    assert "kept" in notes[0]
    assert all(path.exists() for path in host_paths())


def test_a_failed_box_removal_names_the_box() -> None:
    box = FakeBox({"rm": CommandError(["distrobox", "rm"], 1, detail="no such container")})
    notes = run_install(box)

    name = inner(box.calls[0])[inner(box.calls[0]).index("--name") + 1]
    assert any(name in note and "distrobox rm --force --rm-home" in note for note in notes)
    assert box.steps()[-2:] == ["rm", "rmi"]
    assert box.tmp is not None
    assert not box.tmp.exists()


@pytest.mark.parametrize("tag", ["-x", "a b", "", "v1;rm", "--upload-pack=x"])
def test_tag_is_validated_before_any_box(tag: str, scratch_run_root: Path) -> None:
    box = FakeBox()
    with pytest.raises(ExecutorError, match="tag"):
        run_install(box, tag)

    assert box.calls == []
    assert list(scratch_run_root.iterdir()) == []


def test_a_swap_failure_restores_the_previous_files(monkeypatch: pytest.MonkeyPatch) -> None:
    first = install(FakeBox())
    assert first.status is InstallStatus.INSTALLED
    before = {path: path.read_bytes() for path in host_paths()}
    receipt_before = receipts.receipt_path("alacritty").read_bytes()
    third = host_paths()[2]
    real_replace = os.replace

    def flaky(src: str | Path, dst: str | Path) -> None:
        if Path(dst) == third and str(src).endswith(NEW_SUFFIX):
            raise OSError("disk full")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    newer = FakeBox()
    newer.binary_text = BUILT_BINARY.replace("0.17.0", "0.18.0")
    with pytest.raises(ExecutorError, match="disk full"):
        run_install(newer, "v0.18.0")

    assert {path: path.read_bytes() for path in host_paths()} == before
    assert receipts.receipt_path("alacritty").read_bytes() == receipt_before
    leftovers = [
        entry
        for path in host_paths()
        for entry in path.parent.iterdir()
        if entry.name.endswith((NEW_SUFFIX, OLD_SUFFIX))
    ]
    assert leftovers == []


def test_preexisting_terminfo_leaf_is_kept_and_named() -> None:
    mine = Path.home() / ".terminfo/a/alacritty"
    mine.parent.mkdir(parents=True)
    mine.write_text("my own entry\n", encoding="utf-8")

    outcome = install(FakeBox())

    assert outcome.status is InstallStatus.INSTALLED
    assert mine.read_text(encoding="utf-8") == "my own entry\n"
    assert outcome.postinstall_warning is not None
    assert "kept your existing ~/.terminfo/a/alacritty" in outcome.postinstall_warning
    receipt = receipts.read("alacritty")
    assert receipt is not None
    assert mine not in {artifact.path for artifact in receipt.artifacts}
    assert host_paths()[4] in {artifact.path for artifact in receipt.artifacts}


def _failing_swap(monkeypatch: pytest.MonkeyPatch, error: BaseException, *, stuck: bool) -> None:
    """Make the swap of the third artifact raise `error`; with `stuck`, rollback fails too."""
    third = host_paths()[2]
    real_replace = os.replace

    def flaky(src: str | Path, dst: str | Path) -> None:
        if Path(dst) == third and str(src).endswith(NEW_SUFFIX):
            raise error
        if stuck and str(src).endswith(OLD_SUFFIX):
            raise OSError("read-only")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)


def test_a_stuck_rollback_still_reports_the_box_that_could_not_be_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert install(FakeBox()).status is InstallStatus.INSTALLED
    _failing_swap(monkeypatch, OSError("disk full"), stuck=True)
    box = FakeBox({"rm": CommandError(["distrobox", "rm"], 1, detail="busy")})

    with pytest.raises(ExecutorError, match="rollback failed") as caught:
        run_install(box, "v0.18.0")

    assert "could not remove the Distrobox" in str(caught.value)
    assert box.steps()[-2:] == ["rm", "rmi"]


def test_an_unlinkable_staged_file_does_not_skip_the_box_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_unlink = Path.unlink

    def refusing(self: Path, missing_ok: bool = False) -> None:
        if self.name.endswith(NEW_SUFFIX):
            raise PermissionError("immutable")
        real_unlink(self, missing_ok=missing_ok)

    _failing_swap(monkeypatch, OSError("disk full"), stuck=False)
    monkeypatch.setattr(Path, "unlink", refusing)
    box = FakeBox()

    with pytest.raises(ExecutorError, match="disk full"):
        run_install(box)

    assert box.steps()[-2:] == ["rm", "rmi"]


def test_an_interrupt_between_the_two_replaces_restores_the_previous_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert install(FakeBox()).status is InstallStatus.INSTALLED
    before = {path: path.read_bytes() for path in host_paths()}
    _failing_swap(monkeypatch, KeyboardInterrupt(), stuck=False)
    newer = FakeBox()
    newer.binary_text = BUILT_BINARY.replace("0.17.0", "0.18.0")

    with pytest.raises(KeyboardInterrupt):
        run_install(newer, "v0.18.0")

    assert {path: path.read_bytes() for path in host_paths()} == before


def test_every_step_pins_the_container_manager_to_podman() -> None:
    box = FakeBox()
    run_install(box)

    assert box.calls
    for call in box.calls:
        assert "DBX_CONTAINER_MANAGER=podman" in call[:PREFIX_LENGTH]


def test_a_run_dir_that_cannot_be_removed_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def keep(_path: Path, ignore_errors: bool = False) -> None:
        pass

    monkeypatch.setattr(cargo_distrobox.shutil, "rmtree", keep)

    notes = run_install(FakeBox())

    assert any("could not remove" in note and "tools-installer-cargo-" in note for note in notes)


def test_a_partial_uninstall_still_lists_the_surviving_recorded_artifacts() -> None:
    assert install(FakeBox()).status is InstallStatus.INSTALLED
    binary, *others = host_paths()
    binary.unlink()  # a partial uninstall: the binary is gone, the rest is still there

    plan = removal_plan(alacritty_tool(), Path.home() / ".local/bin")

    assert plan.removable == ()
    assert sorted(plan.yourself) == sorted(others)


def test_a_binary_nobody_recorded_is_never_replaced() -> None:
    binary = host_paths()[0]
    binary.parent.mkdir(parents=True)
    binary.write_text("my own alacritty, not executable\n")
    binary.chmod(0o644)
    box = FakeBox()

    with pytest.raises(ExecutorError, match="existing .*alacritty"):
        run_install(box)

    assert box.calls == []  # refused before any box exists
    assert binary.read_text() == "my own alacritty, not executable\n"
