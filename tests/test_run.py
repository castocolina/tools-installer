import subprocess
import sys

import pytest

from installer.run import CommandError, run_captured, run_command, run_output


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
