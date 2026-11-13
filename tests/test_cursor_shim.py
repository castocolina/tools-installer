"""The cursor-agent model shim: replace the link, keep the launcher, inject the model (SPEC R7)."""

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from installer import run
from installer.cursor_shim import (
    SHIM_SENTINEL,
    is_our_shim,
    parse_models,
    read_models,
    refresh_shim,
    remove_shim,
    render_shim,
    restore_link,
)
from installer.daemon import DaemonScheduleError

MODEL = "gpt-5.6-sol-xhigh"


@dataclass(frozen=True)
class Install:
    """A scratch cursor-agent install: a fake launcher and the two vendor links to it."""

    home: Path
    launcher: Path
    agent: Path
    link: Path
    record: Path


def add_launcher(home: Path, version: str, record: Path) -> Path:
    """A fake release launcher that records `$0` and its arguments, one per line."""
    launcher = home / ".local" / "share" / "cursor-agent" / "versions" / version / "cursor-agent"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        f'#!/bin/bash\n{{ printf "%s\\n" "$0"; printf "%s\\n" "$@"; }} > \'{record}\'\n'
    )
    launcher.chmod(0o755)
    return launcher


@pytest.fixture
def install(tmp_path: Path) -> Install:
    home = tmp_path / "home"
    record = tmp_path / "record.txt"
    launcher = add_launcher(home, "v1", record)
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    agent = bin_dir / "agent"
    link = bin_dir / "cursor-agent"
    agent.symlink_to(launcher)
    link.symlink_to(launcher)
    return Install(home, launcher, agent, link, record)


def run_shim(shim: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(shim), *args], capture_output=True, text=True, check=False)


def recorded(install: Install) -> list[str]:
    return install.record.read_text().splitlines()


def test_the_shim_replaces_the_link_and_keeps_the_launcher(install: Install) -> None:
    launcher_bytes = install.launcher.read_bytes()
    agent_target = os.readlink(install.agent)

    report = refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))

    assert (report.write, report.check, report.model) == ("written", "listed", MODEL)
    assert install.launcher.read_bytes() == launcher_bytes
    assert os.readlink(install.agent) == agent_target
    assert not install.link.is_symlink()
    assert install.link.stat().st_mode & 0o777 == 0o755
    assert install.link.read_text().splitlines()[1] == SHIM_SENTINEL
    assert run_shim(install.link, "-p", "hi").returncode == 0
    assert recorded(install) == [str(install.launcher), "--model", MODEL, "-p", "hi"]


def test_shim_text_is_safe(install: Install) -> None:
    text = render_shim(install.agent, MODEL)
    assert f"'{MODEL}'" in text
    assert f"agent='{install.agent}'" in text
    assert "exec -a" not in text
    with pytest.raises(DaemonScheduleError):
        render_shim(install.agent, "--x")
    with pytest.raises(DaemonScheduleError):
        render_shim(install.agent.with_name("it's"), MODEL)


DISPATCH = [
    (("-p", "hi"), ["--model", MODEL, "-p", "hi"]),
    (("--model", "sonnet", "-p", "hi"), ["--model", "sonnet", "-p", "hi"]),
    (("--model=sonnet", "-p", "hi"), ["--model=sonnet", "-p", "hi"]),
    (("-p", "hi", "--model", "sonnet"), ["-p", "hi", "--model", "sonnet"]),
    (("update",), ["--model", MODEL, "update"]),
    (("-p", "two words", "it's"), ["--model", MODEL, "-p", "two words", "it's"]),
]


@pytest.mark.parametrize(("args", "injected"), DISPATCH)
def test_dispatch_matrix(install: Install, args: tuple[str, ...], injected: list[str]) -> None:
    refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    assert run_shim(install.link, *args).returncode == 0
    assert recorded(install) == [str(install.launcher), *injected]

    refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=())
    assert run_shim(install.link, *args).returncode == 0
    assert recorded(install) == [str(install.launcher), *args]


def test_relinked_agent_is_followed(install: Install, tmp_path: Path) -> None:
    refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    shim_bytes = install.link.read_bytes()
    v2 = add_launcher(install.home, "v2", install.record)
    install.agent.unlink()
    install.agent.symlink_to(v2)

    assert run_shim(install.link, "-p", "hi").returncode == 0
    assert recorded(install)[0] == str(v2)
    assert install.link.read_bytes() == shim_bytes


def test_dangling_agent_fails_with_a_message(install: Install) -> None:
    refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    shim_bytes = install.link.read_bytes()
    install.launcher.unlink()

    result = run_shim(install.link, "-p", "hi")
    assert result.returncode == 127
    assert str(install.agent) in result.stderr

    install.agent.unlink()
    with pytest.raises(OSError, match="agent"):
        refresh_shim(link=install.link, agent=install.agent, model="other", models=("other",))
    assert install.link.read_bytes() == shim_bytes


def test_foreign_cursor_agent_survives_byte_for_byte(install: Install) -> None:
    install.link.unlink()
    foreign = b"#!/bin/sh\necho mine\n"
    install.link.write_bytes(foreign)
    os.utime(install.link, ns=(1_000_000_000, 1_000_000_000))
    before = install.link.stat().st_mtime_ns

    report = refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    assert report.write == "kept-foreign"
    assert install.link.read_bytes() == foreign
    assert install.link.stat().st_mtime_ns == before

    late = b"#!/bin/sh\n" + b"#\n" * 3000 + SHIM_SENTINEL.encode() + b"\n"
    install.link.write_bytes(late)
    assert not is_our_shim(install.link)
    assert (
        refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,)).write
        == "kept-foreign"
    )
    assert install.link.read_bytes() == late


def test_a_symlink_to_a_file_with_the_sentinel_is_not_ours(
    install: Install, tmp_path: Path
) -> None:
    holder = tmp_path / "holder"
    holder.write_text(f"#!/bin/sh\n{SHIM_SENTINEL}\n")
    install.link.unlink()
    install.link.symlink_to(holder)
    assert not is_our_shim(install.link)
    assert not remove_shim(install.link)
    assert install.link.is_symlink()


def test_refresh_is_idempotent(install: Install) -> None:
    first = refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    os.utime(install.link, ns=(1_000_000_000, 1_000_000_000))
    again = refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    assert (first.write, again.write) == ("written", "unchanged")
    assert install.link.stat().st_mtime_ns == 1_000_000_000

    other = refresh_shim(link=install.link, agent=install.agent, model="other", models=("other",))
    assert other.write == "written"
    assert "'other'" in install.link.read_text()


def test_model_check_decides_the_shim(install: Install) -> None:
    unlisted = refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=("auto",))
    assert (unlisted.write, unlisted.check) == ("written", "not-listed")
    assert "--model" not in install.link.read_text().replace("--model|--model=*", "")

    unknown = refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=None)
    assert (unknown.write, unknown.check) == ("written", "unverified")
    assert f"'{MODEL}'" in install.link.read_text()

    override = "claude-opus-4-8[context=1m,effort=high,fast=false]"
    listed = refresh_shim(
        link=install.link, agent=install.agent, model=override, models=("claude-opus-4-8",)
    )
    assert listed.check == "listed"
    assert run_shim(install.link, "-p", "hi").returncode == 0
    assert recorded(install) == [str(install.launcher), "--model", override, "-p", "hi"]

    missing = refresh_shim(link=install.link, agent=install.agent, model=override, models=("auto",))
    assert missing.check == "not-listed"
    assert override not in install.link.read_text()


@pytest.mark.parametrize("relative", [False, True])
def test_restore_link(install: Install, relative: bool) -> None:
    if relative:
        install.agent.unlink()
        install.agent.symlink_to(os.path.relpath(install.launcher, install.agent.parent))
    refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))

    assert restore_link(link=install.link, agent=install.agent)
    assert install.link.is_symlink()
    assert os.readlink(install.link) == os.readlink(install.agent)
    assert install.link.resolve() == install.launcher.resolve()


def test_restore_link_leaves_a_foreign_file(install: Install) -> None:
    install.link.unlink()
    install.link.write_bytes(b"mine")
    assert not restore_link(link=install.link, agent=install.agent)
    assert install.link.read_bytes() == b"mine"


def test_remove_shim(install: Install, tmp_path: Path) -> None:
    refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
    assert remove_shim(install.link)
    assert not install.link.exists()
    assert not remove_shim(install.link)

    install.link.write_bytes(b"mine")
    assert not remove_shim(install.link)
    assert install.link.read_bytes() == b"mine"

    install.link.unlink()
    install.link.symlink_to(install.launcher)
    assert not remove_shim(install.link)
    assert install.link.is_symlink()


LIST_MODELS = (
    "Available models\n\n"
    "auto - Auto (default)\n"
    f"{MODEL} - GPT-5.6 Sol 1M Extra High\u200b\u200b\n"
    "composer-2.5 - Composer 2.5 (current)\n"
    "\n"
    "Tip: use --model <id> (or /model <id> in interactive mode) to switch.\n"
)


def test_parse_models() -> None:
    assert parse_models(LIST_MODELS) == ("auto", MODEL, "composer-2.5")
    assert parse_models("") == ()
    assert parse_models("Tip: nothing - here\n-bad - x\n") == ()


def test_read_models(install: Install, monkeypatch: pytest.MonkeyPatch) -> None:
    assert read_models(install.agent, run_output=lambda cmd: LIST_MODELS) == (
        "auto",
        MODEL,
        "composer-2.5",
    )

    def boom(cmd: list[str]) -> str:
        raise run.CommandError(cmd, 1, detail="exit 1")

    assert read_models(install.agent, run_output=boom) is None
    assert read_models(install.agent, run_output=lambda cmd: "Available models\n") is None

    calls: list[tuple[list[str], float | None]] = []

    def fake(cmd: list[str], *, timeout: float | None = None) -> str:
        calls.append((cmd, timeout))
        return LIST_MODELS

    monkeypatch.setattr(run, "run_output", fake)
    assert read_models(install.agent) == ("auto", MODEL, "composer-2.5")
    assert calls == [([str(install.agent), "--list-models"], 40)]


def test_concurrent_reader_sees_whole_files(install: Install) -> None:
    launcher_bytes = install.launcher.read_bytes()
    shim = render_shim(install.agent, MODEL).encode()
    target = os.readlink(install.link)
    stop = threading.Event()
    bad: list[object] = []

    def reader() -> None:
        while not stop.is_set():
            try:
                seen: object = os.readlink(install.link)
            except OSError:
                seen = install.link.read_bytes()
            if seen not in (target, launcher_bytes, shim):
                bad.append(seen)

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for _ in range(50):
            refresh_shim(link=install.link, agent=install.agent, model=MODEL, models=(MODEL,))
            restore_link(link=install.link, agent=install.agent)
    finally:
        stop.set()
        thread.join()
    assert bad == []
