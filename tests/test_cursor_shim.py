"""The cursor-agent model shim: replace the link, keep the launcher, inject the model (SPEC R7)."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from installer.cursor_shim import (
    SHIM_SENTINEL,
    refresh_shim,
    render_shim,
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
