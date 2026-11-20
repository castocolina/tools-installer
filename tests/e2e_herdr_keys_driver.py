"""In-container herdr byte proof: run `python -m tests.e2e_herdr_keys_driver <verb>` via
`scripts/container-e2e-verify.sh herdr-keys`. Verbs install herdr with the installer or record pty
input as bytes; arrows have no separate CSI-u form, so only CSI 1;3 D/C is sent for arrows.
"""

import fcntl
import os
import pty
import select
import shutil
import signal
import struct
import sys
import tempfile
import termios
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Final

from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    verdict,
)

# Arrows have no separate CSI-u form: CSI 1;3 D/C are the only arrow encodings; CSI-u covers
# Alt+B, Alt+F and Ctrl+L.
CHORDS: Final[tuple[tuple[str, bytes, str], ...]] = (
    ("alt+b raw", b"\x1bb", "1b62"),
    ("alt+f raw", b"\x1bf", "1b66"),
    ("alt+left", b"\x1b[1;3D", "1b5b313b3344"),
    ("alt+right", b"\x1b[1;3C", "1b5b313b3343"),
    ("ctrl+l", b"\x0c", "0c"),
    ("alt+b csi-u", b"\x1b[98;3u", "1b62"),
    ("alt+f csi-u", b"\x1b[102;3u", "1b66"),
    ("ctrl+l csi-u", b"\x1b[108;5u", "0c"),
)
EXPECTED: Final = tuple(dict.fromkeys(expected for _name, _sent, expected in CHORDS))
HERDR_CONFIG: Final = """onboarding = false
[update]
version_check = false
manifest_check = false
[terminal]
default_shell = "{shell}"
"""
RECORDER_SOURCE: Final = """import os
import select
import sys
import time
import tty

log_path, seconds = sys.argv[1], float(sys.argv[2])
tty.setraw(0)
with open(log_path, "a", buffering=1) as log:
    log.write("START\\n")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([0], [], [], 0.2)
        if ready:
            data = os.read(0, 1024)
            if not data:
                break
            log.write(data.hex() + "\\n")
"""
STARTUP_SECONDS = 12.0
CHORD_SECONDS = 1.5
RECORD_SECONDS = 60


def received_per_chord(log_lines: Sequence[str], start: int, expected: Sequence[str]) -> list[str]:
    """Delayed or split writes stay with their chord; lost/re-encoded bytes shift later slices."""
    # shortcut: a lost chord shifts later slices; use mark-delimited slices if diagnostics need it.
    stream = "".join(line for line in log_lines[start:] if line != "START")
    result: list[str] = []
    position = 0
    for index, chord in enumerate(expected):
        end = len(stream) if index == len(expected) - 1 else position + len(chord)
        result.append(stream[position:end])
        position += len(chord)
    return result


def herdr_keys_verdict(started: bool, received: Sequence[str], closed: str | None = None) -> str:
    if not started:
        detail = (
            f"the herdr client closed the pty before the recorder started ({closed})"
            if closed is not None
            else "the herdr pane never started the recorder"
        )
        return verdict("TRACER_HERDR_KEYS_UNPROVEN", detail)
    values = [*received, *("" for _ in range(max(0, len(CHORDS) - len(received))))]
    parts = [
        f"{name} sent {sent.hex()} received {values[index] or 'nothing'}"
        for index, (name, sent, expected) in enumerate(CHORDS)
        if values[index] != expected
    ]
    return (
        verdict("TRACER_HERDR_KEYS_FAILED", "; ".join(parts))
        if parts
        else ("TRACER_HERDR_KEYS_OK received=" + ",".join(EXPECTED))
    )


def keys_verdict(log_text: str, closed: str | None, sent: int, received: Sequence[str]) -> str:
    """Pure verdict: `sent` chords were written before the client's pty closed, if it did."""
    if "START" not in log_text.splitlines():
        return herdr_keys_verdict(False, received, closed)
    if closed is not None and sent < len(CHORDS):
        detail = f"the herdr client closed the pty before the last chord was sent ({closed})"
        return verdict("TRACER_HERDR_KEYS_UNPROVEN", detail)
    return herdr_keys_verdict(True, received)


def child_environment(home: Path, runtime: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(runtime),
        "PATH": "/usr/bin:/bin",
        "TERM": "xterm-256color",
        "LANG": "C.UTF-8",
    }


def _install_herdr() -> list[str]:
    install_one(tool_by_id("herdr"), "TRACER_HERDR_INSTALL_FAILED")
    return ["TRACER_HERDR_INSTALL_OK"]


def _keys() -> list[str]:
    """Live herdr pty loop is container-only; host tests cover its pure slicing and verdict."""
    herdr = shutil.which("herdr")
    if herdr is None:
        raise Failed("TRACER_HERDR_KEYS_FAILED", "herdr is not on PATH")
    home = Path(tempfile.mkdtemp(prefix="hk", dir=os.environ.get("TMPDIR", "/tmp")))
    try:
        return _run_keys_in_home(herdr, home)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _run_keys_in_home(herdr: str, home: Path) -> list[str]:
    runtime = home / "run"
    runtime.mkdir(mode=0o700)
    recorder = home / "recorder.py"
    recorder.write_text(RECORDER_SOURCE, encoding="utf-8")
    shell = home / "recshell.sh"
    shell.write_text(
        f"#!/bin/sh\nexec {sys.executable} -I {recorder} {home / 'rec.log'} {RECORD_SECONDS}\n",
        encoding="utf-8",
    )
    shell.chmod(0o755)
    config = home / ".config" / "herdr" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(HERDR_CONFIG.format(shell=shell), encoding="utf-8")
    log_path = home / "rec.log"
    pid, fd = pty.fork()
    if pid == 0:
        env = child_environment(home, runtime)
        try:
            os.execve(herdr, [herdr], env)
        except OSError:
            os._exit(127)
    closed: str | None = None
    start = 0
    sent = 0
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))

        def pump(seconds: float) -> bool:
            nonlocal closed
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], min(0.1, deadline - time.monotonic()))
                if ready:
                    data = os.read(fd, 65536)
                    if not data:
                        closed = "EOF"
                        return False
            return True

        startup_deadline = time.monotonic() + 20
        while time.monotonic() < startup_deadline:
            if log_path.exists() and "START" in log_path.read_text(encoding="utf-8").splitlines():
                break
            if not pump(0.1):
                break
        started = log_path.exists() and "START" in log_path.read_text(encoding="utf-8").splitlines()
        if started and closed is None:
            start = len(log_path.read_text(encoding="utf-8").splitlines())
            for index, (_name, chord, _expected) in enumerate(CHORDS):
                os.write(fd, chord)
                sent = index + 1
                target = sum(len(expected) for _n, _s, expected in CHORDS[: index + 1])
                deadline = time.monotonic() + CHORD_SECONDS
                while time.monotonic() < deadline:
                    if not pump(min(0.1, deadline - time.monotonic())):
                        break
                    lines = (
                        log_path.read_text(encoding="utf-8").splitlines()
                        if log_path.exists()
                        else []
                    )
                    received = "".join(line for line in lines[start:] if line != "START")
                    if len(received) >= target:
                        break
                if closed is not None:
                    break
            if closed is None:
                pump(CHORD_SECONDS)
    except OSError as exc:
        closed = first_line(str(exc))
    finally:
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGHUP)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                waited, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break
            if waited == pid:
                break
            time.sleep(0.1)
        else:
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
            with suppress(ChildProcessError):
                os.waitpid(pid, 0)
        os.close(fd)
    lines = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    return [
        keys_verdict(
            "\n".join(lines),
            closed,
            sent,
            received_per_chord(lines, start, [expected for _n, _s, expected in CHORDS]),
        )
    ]


_HANDLERS = {"install-herdr": _install_herdr, "keys": _keys}


def accepts(args: Sequence[str]) -> bool:
    return len(args) == 1 and args[0] in _HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print(f"usage: e2e_herdr_keys_driver {' | '.join(_HANDLERS)}", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the herdr keys driver runs only inside the disposable container")
        return 2
    try:
        lines = _HANDLERS[args[0]]()
    except Failed as failed:
        print(verdict(failed.prefix, first_line(failed.detail)))
        return 1
    except (OSError, ValueError) as error:
        print(f"ERROR {first_line(error) or type(error).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line or "_UNPROVEN" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
