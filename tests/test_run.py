import subprocess
import sys

import pytest

from installer.run import (
    TIMEOUT_CODE,
    CommandError,
    run_captured,
    run_command,
    run_output,
    run_query,
)


def test_run_command_success(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], check: bool):
        seen["cmd"] = cmd
        seen["check"] = check

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_command(["echo", "hi"])
    assert seen["cmd"] == ["echo", "hi"]
    assert seen["check"] is True


def test_run_command_raises_on_nonzero(monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd: list[str], check: bool):
        raise subprocess.CalledProcessError(returncode=2, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandError) as exc:
        run_command(["false"])
    assert exc.value.cmd == ["false"]
    assert exc.value.returncode == 2


def test_run_command_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch):
    def fake_run(cmd: list[str], check: bool):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(CommandError) as exc:
        run_command(["nope"])
    assert exc.value.returncode == 127


def test_run_output_returns_stdout() -> None:
    assert run_output([sys.executable, "-c", "print('hello')"]) == "hello\n"


def test_run_captured_keeps_child_output_out_of_the_terminal(
    capfd: pytest.CaptureFixture[str],
) -> None:
    # Textual owns the terminal while the Doctor screen runs, so an
    # inherited-stdio child writes straight into the rendered frame.
    capfd.readouterr()
    run_captured(
        [sys.executable, "-c", "import sys; print('noise'); print('warn', file=sys.stderr)"]
    )
    captured = capfd.readouterr()
    assert "noise" not in captured.out
    assert "warn" not in captured.err


def test_run_output_folds_child_stderr_into_the_error() -> None:
    script = "import sys; print('boom', file=sys.stderr); sys.exit(3)"
    with pytest.raises(CommandError) as exc:
        run_output([sys.executable, "-c", script])
    assert exc.value.returncode == 3
    assert exc.value.detail == "boom"
    assert "boom" in str(exc.value)


def test_run_output_raises_when_binary_missing() -> None:
    with pytest.raises(CommandError) as exc:
        run_output(["definitely-not-a-real-binary-xyz"])
    assert exc.value.returncode == 127


def test_run_output_unbounded_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # A side-effecting child (`pnpm add -g` of a Puppeteer-carrying package)
    # legitimately takes minutes; killing it half-way is worse than waiting.
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_output(["anything"])
    assert seen["timeout"] is None


def test_run_output_timeout_fails_fast_instead_of_hanging() -> None:
    # A query run while a TUI owns the terminal has no recoverable input path
    # if the child wedges, so the bound has to be on the call.
    with pytest.raises(CommandError) as exc:
        run_output([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2)
    assert exc.value.returncode == TIMEOUT_CODE
    assert "timed out" in str(exc.value)


def test_run_query_merges_env_over_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TI_PREEXISTING", "keep-me")
    script = (
        "import os;"
        " print(os.environ.get('TI_PREEXISTING', ''),"
        " os.environ.get('TI_OVERRIDE', ''),"
        " bool(os.environ.get('PATH')))"
    )
    out = run_query([sys.executable, "-c", script], env={"TI_OVERRIDE": "new"})
    assert "keep-me" in out
    assert "new" in out
    assert "True" in out


def test_run_query_accepts_nonzero_in_accept_codes() -> None:
    script = "import sys; print('payload'); print('err', file=sys.stderr); sys.exit(1)"
    out = run_query([sys.executable, "-c", script], accept_codes=(0, 1))
    assert "payload" in out


def test_run_query_rejected_code_carries_stdout_and_stderr() -> None:
    script = "import sys; print('payload'); print('err', file=sys.stderr); sys.exit(3)"
    with pytest.raises(CommandError) as exc:
        run_query([sys.executable, "-c", script], accept_codes=(0, 1))
    assert exc.value.returncode == 3
    assert exc.value.detail == "err"
    assert "payload" in exc.value.stdout


def test_run_query_timeout_uses_timeout_code() -> None:
    with pytest.raises(CommandError) as exc:
        run_query([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2)
    assert exc.value.returncode == TIMEOUT_CODE


def test_run_query_missing_binary_is_127() -> None:
    with pytest.raises(CommandError) as exc:
        run_query(["definitely-not-a-real-binary-xyz"])
    assert exc.value.returncode == 127
