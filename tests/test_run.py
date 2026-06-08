import subprocess

import pytest

from installer.run import CommandError, run_command


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
