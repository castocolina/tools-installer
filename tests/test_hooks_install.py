"""The `make dev-setup` hook step, driven by a fake runner and a fake git common dir under tmp_path.

No test runs real git or pre-commit, and none touches this checkout's `.git/hooks` (P5): the
installer takes an injected runner, and the shim tests run a copy under tmp_path with a fake `uv`.
"""

import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from devtools import hooks
from devtools.hooks import MARKER, SHIM, install

GIT = "/fake/bin/git"
PRE_COMMIT = "/fake/bin/pre-commit"


class FakeRunner:
    """Answers the git queries and the pre-commit call the installer makes, and records them."""

    def __init__(self, common: Path, git_dir: Path | None = None) -> None:
        self.common = common
        self.git_dir = git_dir or common
        self.calls: list[list[str]] = []

    @property
    def pre_commit_calls(self) -> list[list[str]]:
        return [call for call in self.calls if call[0] == PRE_COMMIT]

    def __call__(self, argv: Sequence[str]) -> "subprocess.CompletedProcess[str]":
        call = list(argv)
        self.calls.append(call)
        if call[0] == PRE_COMMIT:
            return subprocess.CompletedProcess(call, 0, "pre-commit installed\n", "")
        if "--git-common-dir" in call:
            return subprocess.CompletedProcess(call, 0, f"{self.common}\n", "")
        if "--git-dir" in call:
            return subprocess.CompletedProcess(call, 0, f"{self.git_dir}\n", "")
        return subprocess.CompletedProcess(call, 1, "", "")  # `git config --get`: key unset


def fake_which(name: str) -> str | None:
    return {"git": GIT, "pre-commit": PRE_COMMIT}.get(name)


def test_install_writes_both_hooks_into_the_common_dir(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 0
    assert runner.pre_commit_calls == [[PRE_COMMIT, "install", "--hook-type", "pre-commit"]]
    shim = common / "hooks" / "pre-push"
    assert shim.read_text() == SHIM
    assert stat.S_IMODE(shim.stat().st_mode) == 0o744


def test_shim_text_is_pinned() -> None:
    assert SHIM.startswith(f"#!/bin/sh\n{MARKER}\n")
    assert "command -v uv" in SHIM
    assert "exit 1" in SHIM
    assert SHIM.endswith('exec uv run python -m devtools.push_gate "$@"\n')
    assert "|| true" not in SHIM


def test_main_accepts_only_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hooks, "install", lambda: 0)
    assert hooks.main(["install"]) == 0
    with pytest.raises(SystemExit) as excinfo:
        hooks.main(["remove"])
    assert excinfo.value.code == 2
