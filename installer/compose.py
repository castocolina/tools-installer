"""The composition root: builds the app and its services from the real environment.

`setup.py` parses arguments, owns the questionary and tty plumbing, and calls in here.
Everything in this module is strict-typed and counted by the coverage gate; it never
imports questionary or prompt_toolkit, so any prompt reaches it only as a parameter.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from installer import daemon, env_redirect, systemd_daemon
from installer.engine import InstallOutcome
from installer.locations import zshrc_path

_REGISTRY = Path(__file__).parent / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
# The generic, FOREIGN ~/.shellrc some machines carry -- NOT a second file this
# project writes freely. It is only ever read, backed up, and replaced by a stub
# during D-04 consolidation, and only when that is provably safe.
_SHELLRC = Path.home() / ".shellrc"
# $ZDOTDIR-aware, so the file the installer edits is the one zsh actually reads
# and agrees with omz_present's own environment-aware detection.
_ZSHRC = zshrc_path(Path.home(), os.environ)
_RC_PATHS = [_ZSHRC, Path.home() / ".bashrc"]
_SHELL = os.environ.get("SHELL", "")
Install = Callable[..., InstallOutcome]
# WR-05: a dedicated stderr console, separate from the monkeypatch-able
# `Console` the routes build, so headless routes can announce the settings
# warning without a test double rerouting it.
_WARN_CONSOLE = Console(stderr=True)
# The disk-pressure probe and the Doctor's timer-state cache read the tmp cleanup's own
# artifacts, computed exactly like _MYSHELLRC (Path.home()-derived at import time): the
# LaunchAgent plist and the systemd user unit search dir.
_DAEMON_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{daemon.LABEL}.plist"
_LINUX_DAEMON_UNIT_DIR = systemd_daemon.user_unit_dir(Path.home(), os.environ)
# systemd's user environment generator reads $XDG_CONFIG_HOME/environment.d,
# so this honours XDG_CONFIG_HOME exactly like _LINUX_DAEMON_UNIT_DIR (WR-04).
_ENVIRONMENT_D_DIR = env_redirect.environment_d_dir(Path.home(), os.environ)
