"""The stdlib schedule runner every timer executes (24.2-02).

The runner is imported in-process; every executable a test runs is a fake planted under
`tmp_path` (tests/sandbox.py forbids the real uv, brew, npm and pnpm). Private names are read
through `vars(schedule_runner)`.
"""

import contextlib
import fcntl
import os
import re
import shutil
import signal
import threading
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from installer.helper_assets import schedule_runner
from installer.run import CHILD_ENV

_TS = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d"
_CAP = 262144


def _script(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / name
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)
    return script


def _run(
    tmp_path: Path, *job: str, forwarded: Sequence[str] = (), cap: int = _CAP
) -> tuple[int, list[str]]:
    log = tmp_path / "state" / "run.log"
    argv = [
        *job,
        "--log",
        str(log),
        "--lock",
        str(tmp_path / "state" / "run.lock"),
        "--cap-bytes",
        str(cap),
    ]
    if forwarded:
        argv += ["--", *forwarded]
    code = schedule_runner.main(argv)
    return code, (log.read_text().splitlines() if log.exists() else [])


def _gone(pid: int, deadline: float = 5.0) -> bool:
    """True once the pid no longer exists; an orphan can take a moment to be reaped."""
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def _reap(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


# --- tmp-cleanup (tracer) ---------------------------------------------------


def test_tmp_cleanup_logs_start_and_result(tmp_path: Path) -> None:
    seen = tmp_path / "seen.txt"
    script = _script(tmp_path / "bin", "prune.sh", f'echo "$@" > {seen}\necho "deleted: 3"')
    code, lines = _run(
        tmp_path,
        "tmp-cleanup",
        "--script",
        str(script),
        forwarded=["--apply", "--minutes", "10"],
    )
    assert code == 0
    assert len(lines) == 2
    assert re.fullmatch(rf"{_TS} tmp-cleanup start", lines[0])
    assert re.fullmatch(rf"{_TS} tmp-cleanup ok: deleted 3", lines[1])
    assert seen.read_text().split() == ["--apply", "--minutes", "10"]
    assert (tmp_path / "state" / "run.lock").read_bytes() == b""


def test_tmp_cleanup_failure_is_logged(tmp_path: Path) -> None:
    script = _script(tmp_path / "bin", "prune.sh", 'echo "bad news" >&2\nexit 4')
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    assert code == 1
    assert lines[-1].endswith("tmp-cleanup failed: prune.sh exited 4")
    quiet = _script(tmp_path / "bin", "quiet.sh", "exit 0")
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(quiet))
    assert code == 0
    assert lines[-1].endswith("tmp-cleanup ok: done")


def test_tmp_cleanup_a_missing_script_is_a_logged_failure(tmp_path: Path) -> None:
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(tmp_path / "nope.sh"))
    assert code == 1
    assert re.search(r"tmp-cleanup failed: .*nope\.sh", lines[-1])


_TAIL = ["--log", "LOG", "--lock", "LOCK", "--cap-bytes", "9"]


@pytest.mark.parametrize(
    "argv",
    [
        ["tmp-cleanup", "--script", "x", "--lock", "LOCK", "--cap-bytes", "9"],
        ["bogus", *_TAIL],
        ["update", "claude", "--uv", "u", *_TAIL],
        ["update", "Bad_Tool", "--installer", "i", "--uv", "u", *_TAIL],
        ["tmp-cleanup", "--script", "x", "--log", "LOG", "--lock", "LOCK", "--cap-bytes", "many"],
        ["tmp-cleanup", "--script", "x", *_TAIL, "--no"],
    ],
)
def test_usage_errors_exit_2(
    tmp_path: Path, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "run.log"
    paths = {"LOG": str(log), "LOCK": str(tmp_path / "run.lock")}
    assert schedule_runner.main([paths.get(part, part) for part in argv]) == 2
    assert capsys.readouterr().err.strip()
    assert not log.exists()


def test_tmp_cleanup_keeps_a_file_lsof_reports_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = Path(__file__).resolve().parent.parent / "scripts"
    copy = tmp_path / "copy" / "scripts"
    (copy / "lib").mkdir(parents=True)
    shutil.copy(checkout / "prune-user-tmpdir.sh", copy)
    shutil.copy(checkout / "lib" / "prune-tmp-common.sh", copy / "lib")
    home = tmp_path / "home"
    tmpdir = tmp_path / "scratch-tmp"
    home.mkdir()
    tmpdir.mkdir()
    orphan = tmpdir / "orphan.dylib"
    orphan.write_bytes(b"x")
    aged = time.time() - 10 * 86400
    os.utime(orphan, (aged, aged))
    sbin = tmp_path / "sbin"
    _script(sbin, "lsof", f'echo "n{orphan}"')
    monkeypatch.setenv("PATH", f"{sbin}:/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    code, lines = _run(
        tmp_path,
        "tmp-cleanup",
        "--script",
        str(copy / "prune-user-tmpdir.sh"),
        forwarded=["--apply", "--days", "3"],
    )
    assert code == 0
    assert lines[-1].endswith("tmp-cleanup ok: deleted 0")
    assert orphan.exists()


def _pid_script(tmp_path: Path, body: str) -> tuple[Path, Path]:
    pidfile = tmp_path / "grandchild.pid"
    return _script(tmp_path / "bin", "hang.sh", body.replace("@PID@", str(pidfile))), pidfile


def test_timeout_kills_the_process_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, pidfile = _pid_script(tmp_path, 'sleep 60 &\necho $! > "@PID@"\nsleep 60')
    monkeypatch.setitem(vars(schedule_runner), "_TMP_TIMEOUT", 1)
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    grandchild = int(pidfile.read_text())
    try:
        assert code == 1
        assert re.search(r"tmp-cleanup failed: .* timed out$", lines[-1])
        assert _gone(grandchild)
    finally:
        _reap(grandchild)


@pytest.mark.skipif(shutil.which("setsid") is None, reason="util-linux setsid is absent")
def test_timeout_with_an_escaped_pipe_holder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script, pidfile = _pid_script(tmp_path, 'setsid sleep 2 &\necho $! > "@PID@"')
    monkeypatch.setitem(vars(schedule_runner), "_TMP_TIMEOUT", 1)
    started = time.monotonic()
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    elapsed = time.monotonic() - started
    holder = int(pidfile.read_text())
    try:
        assert code == 1
        assert re.search(r"tmp-cleanup failed: .* timed out$", lines[-1])
        assert elapsed < 12
        assert _gone(holder)
    finally:
        _reap(holder)


def test_runner_never_imports_the_installer_package() -> None:
    source = Path(schedule_runner.__file__).read_text()
    lines = source.splitlines()
    assert "# tools-installer-helper: schedule-runner" in lines
    assert '# requires-python = ">=3.11"' in lines
    assert "# /// script" in lines
    for line in lines:
        assert not re.match(r"\s*(import installer|from installer)", line)


# --- cache-cleanup ----------------------------------------------------------

_SHIM_LINE = "# tools-installer-ban-shim"
_REDIRECT_LINE = "# tools-installer-redirect-shim"


def _texts(lines: list[str], run_id: str = "cache-cleanup") -> list[str]:
    """Each log line without its timestamp and id."""
    return [re.sub(rf"^{_TS} {run_id} ", "", line) for line in lines]


def _recorder(bin_dir: Path, name: str, exit_code: int = 0) -> Path:
    """A fake manager that writes its argv to `<bin>/<name>.argv`."""
    return _script(bin_dir, name, f'echo "$@" > "{bin_dir / name}.argv"\nexit {exit_code}')


def test_cache_cleanup_runs_only_installed_managers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv")
    _recorder(bin_dir, "pnpm")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines) == [
        "start",
        "ran: uv cache prune (exit 0)",
        "ran: pnpm store prune (exit 0)",
        "ok: pruned uv, pnpm",
    ]
    assert (bin_dir / "uv.argv").read_text().split() == ["cache", "prune"]
    assert (bin_dir / "pnpm.argv").read_text().split() == ["store", "prune"]


def test_cache_cleanup_with_nothing_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines) == ["start", "ok: nothing to clean"]


def test_one_failing_manager_does_not_stop_the_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv")
    _recorder(bin_dir, "pnpm")
    _recorder(bin_dir, "brew", exit_code=1)
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert _texts(lines)[1:] == [
        "ran: uv cache prune (exit 0)",
        "ran: pnpm store prune (exit 0)",
        "ran: brew cleanup (exit 1)",
        "failed: brew cleanup exited 1 (uv, pnpm ok)",
    ]


def test_a_manager_after_a_failure_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv", exit_code=3)
    _recorder(bin_dir, "pnpm")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert (bin_dir / "pnpm.argv").exists()
    assert _texts(lines)[-1] == "failed: uv cache prune exited 3 (pnpm ok)"


def test_npm_skips_the_ban_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim_dir = tmp_path / "shim"
    real_dir = tmp_path / "real"
    _script(shim_dir, "npm", f"{_SHIM_LINE}\nexit 9")
    _recorder(real_dir, "npm")
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{real_dir}")
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert (real_dir / "npm.argv").read_text().split() == ["cache", "verify"]
    assert _texts(lines)[1:] == ["ran: npm cache verify (exit 0)", "ok: pruned npm"]
    monkeypatch.setenv("PATH", str(shim_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines)[-1] == "ok: nothing to clean"


@pytest.mark.parametrize("name", ["npm", "pnpm"])
def test_managers_skip_the_redirect_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    shim_dir = tmp_path / "shim"
    real_dir = tmp_path / "real"
    _script(shim_dir, name, f"{_REDIRECT_LINE}\nexit 127")
    _recorder(real_dir, name)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{real_dir}")
    code, _lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert (real_dir / f"{name}.argv").exists()


def test_cache_cleanup_ignores_a_relative_path_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _recorder(tmp_path / "rel", "uv")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "rel")
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines)[-1] == "ok: nothing to clean"


def _snapshot(*roots: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for root in roots for path in root.rglob("*") if path.is_file()}


def test_cache_cleanup_touches_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    trees = [
        home / ".cache" / "uv",
        home / ".local" / "share" / "pnpm" / "store",
        home / ".npm" / "_cacache",
        home / ".cache" / "other",
    ]
    for tree in trees:
        (tree / "deep").mkdir(parents=True)
        (tree / "deep" / "blob").write_bytes(tree.name.encode())
        (tree / "top").write_bytes(b"top")
    bin_dir = tmp_path / "bin"
    for name in ("uv", "pnpm", "brew", "npm"):
        _recorder(bin_dir, name)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(home))
    before = _snapshot(*trees)
    assert _run(tmp_path, "cache-cleanup")[0] == 0
    assert _snapshot(*trees) == before


def test_manager_output_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    _script(bin_dir, "uv", r"printf '\033[31mred\033[0m \377\nsecond line\n' >&2; exit 2")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert len(lines) == 3
    for line in lines:
        assert "\x1b" not in line
    assert _texts(lines)[1:] == ["ran: uv cache prune (exit 2)", "failed: uv cache prune exited 2"]


def test_sanitize_strips_ansi_controls_and_bounds_the_length() -> None:
    sanitize = vars(schedule_runner)["_sanitize"]
    assert sanitize(b"\x1b[1;31mred\x1b[0m\x00 a\r\nb\t\xff") == "red a b �"
    assert sanitize("\x1b]0;title\x07x") == "x"
    assert len(sanitize("y" * 1000)) == 300


def test_manager_env_carries_the_brew_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    seen = tmp_path / "env.txt"
    # env, not the shell's set: dash and bash quote set's values differently.
    _script(bin_dir, "brew", f'/usr/bin/env > "{seen}"')
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("SUDO_ASKPASS", "/tmp/askpass")
    monkeypatch.setenv("HOMEBREW_NO_SUDO", "0")
    assert _run(tmp_path, "cache-cleanup")[0] == 0
    values = dict(line.split("=", 1) for line in seen.read_text().splitlines() if "=" in line)
    assert values["HOMEBREW_NO_SUDO"] == "1"
    assert values["HOMEBREW_NO_AUTOREMOVE"] == "1"
    assert "SUDO_ASKPASS" not in values
    assert vars(schedule_runner)["_CHILD_ENV"] == CHILD_ENV


def test_child_env_passes_the_proxy_certificate_and_pnpm_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    seen = tmp_path / "env.txt"
    _script(bin_dir, "brew", f'/usr/bin/env > "{seen}"')
    monkeypatch.setenv("PATH", str(bin_dir))
    wanted = {
        "PNPM_HOME": "/p",
        "HTTP_PROXY": "http://a",
        "HTTPS_PROXY": "http://b",
        "NO_PROXY": "x",
        "http_proxy": "http://a",
        "https_proxy": "http://b",
        "no_proxy": "x",
        "SSL_CERT_FILE": "/c.pem",
        "REQUESTS_CA_BUNDLE": "/r.pem",
        "NODE_EXTRA_CA_CERTS": "/n.pem",
    }
    for key, value in wanted.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SUDO_ASKPASS", "/tmp/askpass")
    assert _run(tmp_path, "cache-cleanup")[0] == 0
    values = dict(line.split("=", 1) for line in seen.read_text().splitlines() if "=" in line)
    assert {key: values.get(key) for key in wanted} == wanted
    assert "SUDO_ASKPASS" not in values


_UV_LOCKED = (
    "error: Timeout (5s) when waiting for lock on `/home/u/.cache/uv` at "
    "`/home/u/.cache/uv/.lock`, is another uv process running? You can set `UV_LOCK_TIMEOUT` "
    "to increase the timeout."
)


def _locked_uv(bin_dir: Path) -> Path:
    return _script(
        bin_dir,
        "uv",
        f'echo "$UV_LOCK_TIMEOUT $@" > "{bin_dir}/uv.argv"\necho "{_UV_LOCKED}" >&2\nexit 2',
    )


def test_uv_cache_prune_runs_with_a_short_lock_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _locked_uv(bin_dir)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("UV_LOCK_TIMEOUT", "300")
    _run(tmp_path, "cache-cleanup")
    argv = (bin_dir / "uv.argv").read_text().split()
    assert argv == ["5", "cache", "prune"]  # never --force


def test_a_uv_lock_timeout_is_skipped_not_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _locked_uv(bin_dir)
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines)[-1] == "skipped: uv cache in use"


def test_a_uv_lock_timeout_does_not_hide_the_other_managers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _locked_uv(bin_dir)
    _recorder(bin_dir, "pnpm")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines)[-1] == "ok: pruned pnpm (uv cache in use)"


def test_a_uv_failure_that_is_not_the_lock_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv", exit_code=2)
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert _texts(lines)[-1] == "failed: uv cache prune exited 2"


def test_manager_timeout_is_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = shutil.which("sleep")
    assert sleep is not None
    bin_dir = tmp_path / "bin"
    _script(bin_dir, "pnpm", f"{sleep} 5")
    _recorder(bin_dir, "brew")
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setitem(vars(schedule_runner), "_MANAGER_TIMEOUT", 1)
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert _texts(lines)[1:] == [
        "ran: pnpm store prune (timed out)",
        "ran: brew cleanup (exit 0)",
        "failed: pnpm store prune timed out (brew ok)",
    ]


# --- update, busy skip, capped log ------------------------------------------


def _checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "setup.py").write_text("")
    return checkout


def _update(tmp_path: Path, uv: Path | str, checkout: Path | None = None) -> tuple[int, list[str]]:
    return _run(
        tmp_path,
        "update",
        "claude",
        "--installer",
        str(checkout or _checkout(tmp_path)),
        "--uv",
        str(uv),
    )


def test_update_runs_the_installer_child(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    bin_dir = tmp_path / "bin"
    uv = _script(
        bin_dir, "uv", f'echo "$@" > "{bin_dir}/argv"\npwd > "{bin_dir}/cwd"\necho "ok: up to date"'
    )
    code, lines = _update(tmp_path, uv, checkout)
    assert code == 0
    assert (bin_dir / "argv").read_text().split() == [
        *["run", "--isolated", "--no-dev", "setup.py", "--run-schedule", "update-claude"],
        "--parent-holds-run-lock",
    ]
    assert Path((bin_dir / "cwd").read_text().strip()).resolve() == checkout.resolve()
    assert _texts(lines, "update-claude") == ["start", "ok: up to date"]


@pytest.mark.parametrize(
    ("body", "code", "result"),
    [
        ('echo "failed: boom"\nexit 1', 1, "failed: boom"),
        ("exit 3", 1, "failed: installer exited 3"),
        ('echo "oops" >&2\necho "more" >&2\nexit 3', 1, "failed: installer exited 3: more"),
        ("echo hello", 1, "failed: no result line from the installer"),
        ('echo "ok: fine"\nexit 3', 1, 'failed: installer exited 3 after "ok: fine"'),
        ('echo "ok: first"\necho noise\necho "skipped: last"\necho tail', 0, "skipped: last"),
        ('echo "failed: odd"', 1, "failed: odd"),
    ],
)
def test_update_child_failure_and_odd_output(
    tmp_path: Path, body: str, code: int, result: str
) -> None:
    uv = _script(tmp_path / "bin", "uv", body)
    got, lines = _update(tmp_path, uv)
    assert got == code
    assert _texts(lines, "update-claude")[-1] == result


def test_missing_installer_fails_loudly(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    uv = _recorder(bin_dir, "uv")
    empty = tmp_path / "empty"
    empty.mkdir()
    code, lines = _update(tmp_path, uv, empty)
    assert code == 1
    assert _texts(lines, "update-claude")[-1] == f"failed: installer not found at {empty}/setup.py"
    assert not (bin_dir / "uv.argv").exists()
    code, lines = _update(tmp_path, tmp_path / "no-uv")
    assert code == 1
    assert _texts(lines, "update-claude")[-1] == f"failed: uv not found at {tmp_path}/no-uv"


def _hanging_uv(tmp_path: Path, body: str) -> Path:
    sleep = shutil.which("sleep")
    assert sleep is not None
    return _script(tmp_path / "bin", "uv", body.replace("sleep", sleep))


def _assert_lock_released(tmp_path: Path) -> None:
    lock = tmp_path / "state" / "run.lock"
    assert lock.read_bytes() == b""
    fd = os.open(lock, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def test_update_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pidfile = tmp_path / "uv.pid"
    uv = _hanging_uv(tmp_path, f'echo $$ > "{pidfile}"\nsleep 60')
    monkeypatch.setitem(vars(schedule_runner), "_UPDATE_TIMEOUT", 1)
    code, lines = _update(tmp_path, uv)
    pid = int(pidfile.read_text())
    try:
        assert code == 1
        assert _texts(lines, "update-claude")[-1] == "failed: the update timed out"
        assert _gone(pid)
    finally:
        _reap(pid)
    _assert_lock_released(tmp_path)


def test_update_timeout_kills_the_installer_grandchild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pidfile = tmp_path / "grandchild.pid"
    uv = _hanging_uv(tmp_path, f'sleep 60 &\necho $! > "{pidfile}"\nsleep 60')
    monkeypatch.setitem(vars(schedule_runner), "_UPDATE_TIMEOUT", 1)
    code, lines = _update(tmp_path, uv)
    grandchild = int(pidfile.read_text())
    try:
        assert code == 1
        assert _texts(lines, "update-claude")[-1] == "failed: the update timed out"
        assert _gone(grandchild)
    finally:
        _reap(grandchild)


def test_busy_lock_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_BOUND", 0.3)
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_POLL", 0.05)
    state = tmp_path / "state"
    state.mkdir()
    lock = state / "run.lock"
    lock.write_text("update-claude 1 2026-11-13T00:00:00+00:00\n")
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv")
    monkeypatch.setenv("PATH", str(bin_dir))
    holder = os.open(lock, os.O_RDWR)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, lines = _run(tmp_path, "cache-cleanup")
    finally:
        os.close(holder)
    assert code == 0
    assert _texts(lines) == ["skipped: busy"]
    assert not (bin_dir / "uv.argv").exists()
    assert lock.read_text() == "update-claude 1 2026-11-13T00:00:00+00:00\n"


def test_a_running_run_writes_its_id_pid_and_time_into_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    cat = shutil.which("cat")
    assert cat is not None
    _script(bin_dir, "uv", f'{cat} "{tmp_path}/state/run.lock" > "{bin_dir}/seen"')
    monkeypatch.setenv("PATH", str(bin_dir))
    assert _run(tmp_path, "cache-cleanup")[0] == 0
    assert re.fullmatch(rf"cache-cleanup {os.getpid()} {_TS}\n", (bin_dir / "seen").read_text())


def test_log_is_trimmed_before_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    log = tmp_path / "state" / "run.log"
    log.parent.mkdir()
    old = ("x" * 49 + "\n") * 20
    log.write_text(old)
    cap = len(old.encode())
    replaced: list[tuple[str, str]] = []
    real_replace = os.replace

    def record(src: str | Path, dst: str | Path) -> None:
        replaced.append((Path(src).name, Path(dst).name))
        real_replace(src, dst)

    monkeypatch.setattr(vars(schedule_runner)["os"], "replace", record)
    code, lines = _run(tmp_path, "cache-cleanup", cap=cap)
    assert code == 0
    assert len(log.read_bytes()) <= cap
    assert log.read_text().endswith("\n")
    assert _texts(lines)[-2:] == ["start", "ok: nothing to clean"]
    assert all(line == "x" * 49 or re.match(_TS, line) for line in lines)
    assert replaced
    assert all(dst == "run.log" and src.endswith(".tmp") for src, dst in replaced)
    assert not list(log.parent.glob("*.tmp"))


def test_a_line_longer_than_the_cap_is_cut_to_its_newest_bytes(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    vars(schedule_runner)["_append"](log, "a" * 400 + "b" * 100 + "\n", 100)
    data = log.read_bytes()
    assert len(data) <= 100
    assert data.endswith(b"b" * 99 + b"\n")
    assert data.count(b"\n") == 1


def test_a_log_under_the_cap_is_appended_untouched(tmp_path: Path) -> None:
    append = vars(schedule_runner)["_append"]
    log = tmp_path / "run.log"
    append(log, "first\n", 1000)
    before = log.read_bytes()
    append(log, "second\n", 1000)
    assert log.read_bytes() == before + b"second\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_a_trim_never_splits_a_multibyte_character(tmp_path: Path) -> None:
    append = vars(schedule_runner)["_append"]
    log = tmp_path / "run.log"
    for index in range(10):
        append(log, f"run-{index:02d} \U0001f600 body \U0001f600 {index:02d}\n", 80)
    text = log.read_bytes().decode("utf-8")  # strict: a split character would raise
    assert len(log.read_bytes()) <= 80
    assert text.startswith("run-")
    assert "run-09" in text
    assert "run-00" not in text
    assert "\U0001f600" in text


def test_a_trim_recovers_from_invalid_utf8_already_in_the_log(tmp_path: Path) -> None:
    append = vars(schedule_runner)["_append"]
    log = tmp_path / "run.log"
    log.write_bytes(b"run-00 start\n" + b"\xff" * 300 + b"\n")
    append(log, "run-01 ok: done\n", 100)
    data = log.read_bytes()
    assert len(data) <= 100
    assert data.decode("utf-8").endswith("run-01 ok: done\n")  # strict decode: valid again


def test_a_multibyte_line_over_the_cap_is_cut_on_a_character_boundary(tmp_path: Path) -> None:
    append = vars(schedule_runner)["_append"]
    log = tmp_path / "run.log"
    append(log, "\U0001f600" * 200 + "\n", 101)  # 4-byte characters never fit 100 bytes evenly
    data = log.read_bytes()
    assert len(data) <= 101
    assert data.decode("utf-8").endswith("\U0001f600\n")
    assert data.count(b"\n") == 1


def test_a_trim_leaves_a_newline_so_the_next_append_starts_a_new_line(tmp_path: Path) -> None:
    append = vars(schedule_runner)["_append"]
    log = tmp_path / "run.log"
    for index in range(20):
        append(log, f"2026-11-13T10:00:00+00:00 job ok: {index:02d}\n", 200)
    append(log, "next\n", 200)
    lines = log.read_text().splitlines()
    assert lines[-1] == "next"
    assert lines[-2].startswith("2026-11-13T10:00:00+00:00 job ok: ")
    assert lines.count("next") == 1


@pytest.mark.parametrize(
    ("output", "result"),
    [
        ("deleted: 4\n", "ok: deleted 4"),
        ("deleted: 4\nmore\ndeleted: 9\n", "ok: deleted 9"),
        ("deleted: not-a-number\n", "ok: done"),
        ("nothing to say\n", "ok: done"),
    ],
)
def test_tmp_cleanup_reads_the_last_deleted_line_and_never_invents_a_count(
    tmp_path: Path, output: str, result: str
) -> None:
    script = _script(tmp_path / "bin", "prune.sh", f"printf '{output}'".replace("\n", "\\n"))
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    assert code == 0
    assert lines[-1].endswith(f"tmp-cleanup {result}")


def test_tmp_cleanup_output_that_is_not_utf8_still_logs_its_result(tmp_path: Path) -> None:
    script = _script(
        tmp_path / "bin", "prune.sh", "printf '\\377\\376 junk\\n'\nprintf 'deleted: 3\\n'"
    )
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    assert code == 0
    assert lines[-1].endswith("tmp-cleanup ok: deleted 3")


def test_two_writers_share_the_log_lock(tmp_path: Path) -> None:
    append = vars(schedule_runner)["_append"]
    log = tmp_path / "state" / "run.log"
    cap = 1000
    seen_sizes: list[int] = []

    def writer(name: str) -> None:
        for index in range(200):
            append(log, f"2026-11-13T10:00:00+00:00 {name} ok: {index}\n", cap)
            seen_sizes.append(log.stat().st_size)

    threads = [threading.Thread(target=writer, args=(name,)) for name in ("w1", "w2")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert max(seen_sizes) <= cap
    lines = log.read_text().splitlines()
    assert lines
    assert all(re.fullmatch(rf"{_TS} w[12] ok: \d+", line) for line in lines)
    assert log.read_text().endswith("\n")


@pytest.mark.parametrize("planted", ["run.log.lock", "run.log"])
def test_a_symlink_at_the_log_or_its_lock_is_never_written_through(
    tmp_path: Path, planted: str, capsys: pytest.CaptureFixture[str]
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("keep\n")
    (state / planted).symlink_to(victim)
    vars(schedule_runner)["_append"](state / "run.log", "2026-11-13T10:00:00+00:00 x ok\n", _CAP)
    assert victim.read_text() == "keep\n"
    assert "cannot write" in capsys.readouterr().err


@pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
def test_kill_group_tolerates_a_group_that_is_gone(
    monkeypatch: pytest.MonkeyPatch, error: type[OSError]
) -> None:
    # macOS answers EPERM, Linux ESRCH, when only zombies are left in the group.
    def gone(pid: int, sig: int) -> None:
        raise error

    monkeypatch.setattr(schedule_runner.os, "killpg", gone)
    vars(schedule_runner)["_kill_group"](4242, signal.SIGKILL)


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_a_signal_kills_the_child_group_logs_interrupted_and_frees_the_lock(
    tmp_path: Path, sig: signal.Signals
) -> None:
    pidfile = tmp_path / "uv.pid"
    grandchild = tmp_path / "grandchild.pid"
    uv = _hanging_uv(
        tmp_path, f'sleep 60 &\necho $! > "{grandchild}"\necho $$ > "{pidfile}"\nsleep 60'
    )
    before = signal.getsignal(sig)
    # Fire once the child is up; the handler runs in this (main) thread.
    killer = threading.Timer(
        1.0, lambda: pidfile.exists() and grandchild.exists() and os.kill(os.getpid(), sig)
    )
    killer.start()
    try:
        code, lines = _update(tmp_path, uv)
    finally:
        killer.cancel()
    pids = [int(pidfile.read_text()), int(grandchild.read_text())]
    try:
        assert code == 1
        assert _texts(lines, "update-claude")[-1] == "failed: interrupted"
        assert all(_gone(pid) for pid in pids)
    finally:
        for pid in pids:
            _reap(pid)
    _assert_lock_released(tmp_path)
    assert signal.getsignal(sig) == before


def _hold(lock: Path, line: str) -> int:
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(line)
    descriptor = os.open(lock, os.O_RDWR)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return descriptor


def test_two_runners_started_together_serialize_instead_of_skipping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_POLL", 0.05)
    bin_dir = tmp_path / "bin"
    _hanging_uv(tmp_path, "sleep 1")  # the cache job holds the lock for a second
    monkeypatch.setenv("PATH", str(bin_dir))
    cleanup = _script(tmp_path / "scripts", "clean.sh", "echo deleted: 0")
    base = ["--log", str(tmp_path / "state" / "run.log"), "--lock", str(tmp_path / "state" / "l")]
    base += ["--cap-bytes", str(_CAP)]
    jobs: list[list[str]] = [
        ["cache-cleanup", *base],
        ["tmp-cleanup", "--script", str(cleanup), *base],
    ]
    codes: list[int] = []

    def go(argv: list[str]) -> None:
        codes.append(schedule_runner.main(argv))

    threads = [threading.Thread(target=go, args=(argv,)) for argv in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    text = (tmp_path / "state" / "run.log").read_text()
    assert codes == [0, 0]
    assert "skipped: busy" not in text
    assert len(re.findall(r" ok: ", text)) == 2
    assert len(re.findall(rf"{_TS} (\S+) waited: \d+s for (cache|tmp)-cleanup\n", text)) == 1


def test_a_run_waits_only_for_a_scheduled_holder_never_the_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_BOUND", 60)
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_POLL", 0.05)
    monkeypatch.setenv("PATH", str(tmp_path))
    holder = _hold(
        tmp_path / "state" / "run.lock", f"installer {os.getpid()} 2026-11-13T00:00:00+00:00\n"
    )
    began = time.monotonic()
    try:
        code, lines = _run(tmp_path, "cache-cleanup")
    finally:
        os.close(holder)
    assert time.monotonic() - began < 5
    assert (code, _texts(lines)) == (0, ["skipped: busy"])


def test_a_signal_while_waiting_ends_the_wait_without_a_start_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_BOUND", 60)
    monkeypatch.setitem(vars(schedule_runner), "_WAIT_POLL", 0.05)
    monkeypatch.setenv("PATH", str(tmp_path))
    holder = _hold(
        tmp_path / "state" / "run.lock", f"update-claude {os.getpid()} 2026-11-13T00:00:00+00:00\n"
    )
    killer = threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGTERM))
    killer.start()
    try:
        code, lines = _run(tmp_path, "cache-cleanup")
    finally:
        killer.cancel()
        os.close(holder)
    assert (code, _texts(lines)) == (0, ["skipped: interrupted while waiting for the run lock"])
