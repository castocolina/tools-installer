"""The `make dev-setup` hook step, driven by a fake runner and a fake git common dir under tmp_path.

No test runs real git or pre-commit, and none touches this checkout's `.git/hooks` (P5): the
installer takes an injected runner, and the shim tests run a copy under tmp_path with a fake `uv`.
"""

import os
import shutil
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from devtools import hooks
from devtools.hooks import MARKER, PRE_COMMIT_HEADER, SHIM, install

GIT = "/fake/bin/git"
PRE_COMMIT = "/fake/bin/pre-commit"
PRE_COMMIT_OWN = f"#!/usr/bin/env bash\n{PRE_COMMIT_HEADER}\necho own\n"
FOREIGN = "#!/bin/sh\necho mine\n"
NOT_A_REPO = "fatal: not a git repository (or any of the parent directories): .git"


class FakeRunner:
    """Answers the git queries and the pre-commit call the installer makes, and records them."""

    def __init__(self, common: Path, git_dir: Path | None = None) -> None:
        self.common = common
        self.git_dir = git_dir or common
        self.calls: list[list[str]] = []
        self.rev_parse: tuple[int, str] = (0, "")  # (exit code, stderr) of every rev-parse
        self.hooks_path: tuple[int, str, str] = (1, "", "")  # (exit code, stdout, stderr)
        self.pre_commit_rc = 0

    @property
    def pre_commit_calls(self) -> list[list[str]]:
        return [call for call in self.calls if call[0] == PRE_COMMIT]

    def __call__(self, argv: Sequence[str]) -> "subprocess.CompletedProcess[str]":
        call = list(argv)
        self.calls.append(call)
        if call[0] == PRE_COMMIT:
            out = "pre-commit installed\n"
            return subprocess.CompletedProcess(call, self.pre_commit_rc, out, "")
        if "rev-parse" in call and self.rev_parse[0] != 0:
            return subprocess.CompletedProcess(call, self.rev_parse[0], "", self.rev_parse[1])
        if "--git-common-dir" in call:
            return subprocess.CompletedProcess(call, 0, f"{self.common}\n", "")
        if "--git-dir" in call:
            return subprocess.CompletedProcess(call, 0, f"{self.git_dir}\n", "")
        return subprocess.CompletedProcess(call, *self.hooks_path)  # `git config --get`


def fake_which(name: str) -> str | None:
    return {"git": GIT, "pre-commit": PRE_COMMIT}.get(name)


def hooks_dir(common: Path) -> Path:
    path = common / "hooks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


def assert_refused(
    capsys: pytest.CaptureFixture[str], runner: FakeRunner, common: Path, *needles: str
) -> None:
    """The step refused: pre-commit never ran, no shim was written, stderr names `needles`."""
    err = capsys.readouterr().err
    for needle in needles:
        assert needle in err
    assert runner.pre_commit_calls == []
    assert not (common / "hooks" / "pre-push").exists()


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


def test_outside_a_checkout_skips_and_succeeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    runner.rev_parse = (128, NOT_A_REPO)
    assert install(run=runner, which=fake_which) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == 1
    assert "not a git checkout" in out
    assert runner.pre_commit_calls == []
    assert not common.exists()


def test_without_git_skips_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner(Path("/nowhere/.git"))
    assert install(run=runner, which=lambda _name: None) == 0
    assert "git" in capsys.readouterr().out
    assert runner.calls == []


def test_another_rev_parse_failure_is_surfaced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    runner.rev_parse = (128, "fatal: detected dubious ownership in repository at '/x'")
    assert install(run=runner, which=fake_which) == 1
    captured = capsys.readouterr()
    assert "dev-setup: git rev-parse failed:" in captured.err
    assert "detected dubious ownership" in captured.err
    assert "not a git checkout" not in captured.out + captured.err
    assert runner.pre_commit_calls == []
    assert not common.exists()


def test_the_default_runner_forces_the_c_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def recorder(argv: Sequence[str], **kwargs: object) -> "subprocess.CompletedProcess[str]":
        seen.update(kwargs)
        return subprocess.CompletedProcess(list(argv), 0, "", "")

    monkeypatch.setattr(hooks.subprocess, "run", recorder)
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    hooks.run_command(["git", "status"])
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["LC_ALL"] == "C"


def test_missing_pre_commit_names_uv_sync(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    assert install(run=runner, which=lambda name: GIT if name == "git" else None) == 1
    assert_refused(capsys, runner, common, "uv sync")


def test_a_failing_pre_commit_is_propagated(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    runner.pre_commit_rc = 3
    assert install(run=runner, which=fake_which) == 3
    assert not (common / "hooks" / "pre-push").exists()


def test_a_symlinked_pre_push_is_refused_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    target = tmp_path / "elsewhere"
    target.write_text(f"{MARKER}\necho mine\n")
    before = snapshot(target)
    link = hooks_dir(common) / "pre-push"
    link.symlink_to(target)
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    err = capsys.readouterr().err
    assert str(link) in err
    assert "not a regular file" in err
    assert "move or delete" in err
    assert link.is_symlink()
    assert snapshot(target) == before
    assert runner.pre_commit_calls == []


def test_a_pre_push_directory_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    (hooks_dir(common) / "pre-push").mkdir()
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    assert "not a regular file" in capsys.readouterr().err
    assert runner.pre_commit_calls == []


def test_a_fifo_pre_push_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    common = tmp_path / "repo" / ".git"
    os.mkfifo(hooks_dir(common) / "pre-push")
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    assert "not a regular file" in capsys.readouterr().err
    assert runner.pre_commit_calls == []


def test_core_hooks_path_fails_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    runner.hooks_path = (0, "/some/dir\n", "")
    assert install(run=runner, which=fake_which) == 1
    assert_refused(
        capsys,
        runner,
        common,
        "core.hooksPath",
        "/some/dir",
        "git config --unset-all core.hooksPath",
    )


def test_an_unexpected_hooks_path_query_failure_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    runner.hooks_path = (2, "", "error: bad config line 3")
    assert install(run=runner, which=fake_which) == 1
    assert_refused(capsys, runner, common, "core.hooksPath", "bad config line 3")


def test_a_foreign_pre_push_is_refused_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    shim = hooks_dir(common) / "pre-push"
    shim.write_text(FOREIGN)
    before = snapshot(shim)
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    err = capsys.readouterr().err
    assert str(shim) in err
    assert "move or delete" in err
    assert snapshot(shim) == before
    assert runner.pre_commit_calls == []


def test_a_symlinked_pre_commit_is_refused_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    target = tmp_path / "elsewhere"
    target.write_text(PRE_COMMIT_OWN)
    before = snapshot(target)
    link = hooks_dir(common) / "pre-commit"
    link.symlink_to(target)
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    assert_refused(capsys, runner, common, str(link), "not a regular file", "move or delete")
    assert link.is_symlink()
    assert snapshot(target) == before


def test_a_pre_commit_directory_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    (hooks_dir(common) / "pre-commit").mkdir()
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    assert_refused(capsys, runner, common, "not a regular file")


@pytest.mark.parametrize("legacy", ["file", "dangling"])
def test_a_foreign_pre_commit_with_an_existing_legacy_is_refused_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], legacy: str
) -> None:
    common = tmp_path / "repo" / ".git"
    hook = hooks_dir(common) / "pre-commit"
    hook.write_text(FOREIGN)
    legacy_path = hook.with_name("pre-commit.legacy")
    if legacy == "file":
        legacy_path.write_text("#!/bin/sh\necho older\n")
    else:
        legacy_path.symlink_to(tmp_path / "missing")
    hook_before = snapshot(hook)
    legacy_before = snapshot(legacy_path) if legacy == "file" else None
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    assert_refused(
        capsys, runner, common, str(hook), str(legacy_path), "would replace pre-commit.legacy"
    )
    assert snapshot(hook) == hook_before
    if legacy_before is not None:
        assert snapshot(legacy_path) == legacy_before
    else:
        assert legacy_path.is_symlink()
        assert os.readlink(legacy_path) == str(tmp_path / "missing")


@pytest.mark.parametrize(
    ("name", "body"),
    [("pre-push", f"{MARKER}\necho mine\n"), ("pre-commit", PRE_COMMIT_OWN)],
)
def test_a_hard_linked_hook_is_refused_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str, body: str
) -> None:
    common = tmp_path / "repo" / ".git"
    other = tmp_path / "elsewhere"
    other.write_text(body)
    hook = hooks_dir(common) / name
    os.link(other, hook)
    before = (snapshot(hook), snapshot(other))
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 1
    err = capsys.readouterr().err
    assert str(hook) in err
    assert "hard-linked" in err
    assert runner.pre_commit_calls == []
    assert name == "pre-push" or not (hook.parent / "pre-push").exists()
    assert (snapshot(hook), snapshot(other)) == before
    assert hook.stat().st_nlink == 2


def test_a_foreign_pre_commit_without_legacy_goes_to_pre_commit(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    (hooks_dir(common) / "pre-commit").write_text(FOREIGN)
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 0
    assert runner.pre_commit_calls == [[PRE_COMMIT, "install", "--hook-type", "pre-commit"]]


def test_pre_commits_own_hook_next_to_a_legacy_file_reinstalls(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    folder = hooks_dir(common)
    (folder / "pre-commit").write_text(PRE_COMMIT_OWN)
    legacy = folder / "pre-commit.legacy"
    legacy.write_text(FOREIGN)
    before = snapshot(legacy)
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 0
    assert len(runner.pre_commit_calls) == 1
    assert snapshot(legacy) == before


def test_a_rerun_is_byte_identical(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    runner = FakeRunner(common)
    assert install(run=runner, which=fake_which) == 0
    shim = common / "hooks" / "pre-push"
    first = snapshot(shim)
    assert install(run=runner, which=fake_which) == 0
    assert snapshot(shim) == first
    assert len(runner.pre_commit_calls) == 2


def test_an_older_marked_shim_is_replaced(tmp_path: Path) -> None:
    common = tmp_path / "repo" / ".git"
    shim = hooks_dir(common) / "pre-push"
    shim.write_text(f"#!/bin/sh\n{MARKER}\nexec true\n")
    assert install(run=FakeRunner(common), which=fake_which) == 0
    assert shim.read_text() == SHIM


def test_a_worktree_installs_into_the_common_dir_and_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    common = tmp_path / "repo" / ".git"
    worktree_git_dir = common / "worktrees" / "wt"
    runner = FakeRunner(common, git_dir=worktree_git_dir)
    assert install(run=runner, which=fake_which) == 0
    assert (common / "hooks" / "pre-push").read_text() == SHIM
    assert not worktree_git_dir.exists()
    out = capsys.readouterr().out
    assert "re-run make dev-setup from the main checkout before removing this worktree" in out


def run_shim(tmp_path: Path, bin_dir: Path) -> "subprocess.CompletedProcess[str]":
    script = tmp_path / "pre-push"
    script.write_text(SHIM)
    scratch_home = tmp_path / "home"
    scratch_home.mkdir(exist_ok=True)
    sh = shutil.which("sh")
    assert sh is not None
    return subprocess.run(
        [sh, str(script), "origin", "url"],
        env={"PATH": str(bin_dir), "HOME": str(scratch_home), "LANG": "C"},
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_the_shim_execs_the_gate_through_uv(tmp_path: Path) -> None:
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    uv = fakebin / "uv"
    uv.write_text('#!/bin/sh\necho "$@"\n')
    uv.chmod(0o700)
    result = run_shim(tmp_path, fakebin)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "run python -m devtools.push_gate origin url"


def test_the_shim_fails_closed_without_uv(tmp_path: Path) -> None:
    emptybin = tmp_path / "emptybin"
    emptybin.mkdir()
    result = run_shim(tmp_path, emptybin)
    assert result.returncode == 1
    assert "uv not found" in result.stderr
