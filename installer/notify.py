"""Desktop notification seam for update checks and future updates.

Children have closed stdin and remain in the runner's process group. Callers supply plain
text; neither adapter escapes markup. Use only counts and registry ids, never free text or
remote output, unless the caller escapes it. Real desktop and Mac delivery require owner UAT.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from installer.run import TIMEOUT_CODE, CommandError, run_output
from installer.sanitize import sanitize_log_line

Notifier = Callable[[str, str], str | None]
APP_NAME = "tools-installer"
NOTIFY_TIMEOUT = 10
BUS_VARIABLE = "DBUS_SESSION_BUS_ADDRESS"
_APPLESCRIPT = (
    "on run argv",
    "display notification (item 2 of argv) with title (item 1 of argv)",
    "end run",
)


def reason_line(text: str) -> str:
    """Return the first non-empty sanitized line, bounded to 300 characters."""
    clean = "".join(ch for ch in sanitize_log_line(text) if not 128 <= ord(ch) <= 159)
    return next((line.strip() for line in clean.splitlines() if line.strip()), "")[:300]


def no_notifier(summary: str, body: str) -> str | None:
    """Default for callers without a notification adapter."""
    return "no notifier is configured"


def notify_send_argv(binary: str, summary: str, body: str) -> list[str]:
    """Build the Linux notification argv."""
    return [binary, f"--app-name={APP_NAME}", "--urgency=normal", "--", summary, body]


def osascript_argv(binary: str, summary: str, body: str) -> list[str]:
    """Keep notification data separate from constant AppleScript source."""
    return [binary, *(item for line in _APPLESCRIPT for item in ("-e", line)), summary, body]


def session_bus_environment(
    environ: Mapping[str, str], uid: int, *, is_socket: Callable[[Path], bool] = Path.is_socket
) -> dict[str, str]:
    """Copy the environment, deriving a session bus address only from an existing socket."""
    env = dict(environ)
    if env.get(BUS_VARIABLE):
        return env
    env.pop(BUS_VARIABLE, None)
    runtime = env.get("XDG_RUNTIME_DIR")
    candidates = ([Path(runtime) / "bus"] if runtime else []) + [Path(f"/run/user/{uid}/bus")]
    for path in candidates:
        try:
            if is_socket(path):
                env[BUS_VARIABLE] = f"unix:path={path}"
                break
        except OSError:
            continue
    return env


def _failure_reason(name: str, exc: CommandError) -> str:
    if exc.returncode == TIMEOUT_CODE:
        return f"{name} timed out"
    if exc.returncode == 127:
        return f"{name} could not be started"
    return f"{name} exited {exc.returncode}"


def notify_send(
    summary: str,
    body: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., str] = run_output,
    environ: Mapping[str, str] = os.environ,
    uid: int | None = None,
    is_socket: Callable[[Path], bool] = Path.is_socket,
) -> str | None:
    """Send one Linux notification or return a fixed failure reason."""
    binary = which("notify-send")
    if binary is None:
        return "notify-send not found"
    try:
        run(
            notify_send_argv(binary, summary, body),
            timeout=NOTIFY_TIMEOUT,
            env=session_bus_environment(
                environ, os.getuid() if uid is None else uid, is_socket=is_socket
            ),
            new_session=False,
        )
    except CommandError as exc:
        return _failure_reason("notify-send", exc)
    return None


def osascript(
    summary: str,
    body: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., str] = run_output,
) -> str | None:
    """Send one macOS notification or return a fixed failure reason."""
    binary = which("osascript")
    if binary is None:
        return "osascript not found"
    try:
        run(osascript_argv(binary, summary, body), timeout=NOTIFY_TIMEOUT, new_session=False)
    except CommandError as exc:
        return _failure_reason("osascript", exc)
    return None


def notifier_for(
    platform_os: str,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., str] = run_output,
    *,
    environ: Mapping[str, str] = os.environ,
    uid: int | None = None,
    is_socket: Callable[[Path], bool] = Path.is_socket,
) -> Notifier:
    """Select an adapter without probing or starting a process."""

    def notify(summary: str, body: str) -> str | None:
        if platform_os == "macos":
            return osascript(summary, body, which=which, run=run)
        return notify_send(
            summary, body, which=which, run=run, environ=environ, uid=uid, is_socket=is_socket
        )

    return notify
