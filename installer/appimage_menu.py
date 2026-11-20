"""Place a verified AppImage's menu entry and icon.

Imported by engine, never download: receipts depends on download.
Failures are notes and do not fail the install.
"""

import contextlib
import os
import shutil
import tempfile
from pathlib import Path

from installer import locations
from installer.agent_settings import missing_dirs, remove_created_dirs
from installer.atomic import atomic_write_bytes, read_capped
from installer.desktop_entry import DesktopEntryError, render
from installer.download import ExecContext, artifact_paths
from installer.executors import ExecutorError, staged_member
from installer.model import Method
from installer.receipts import Receipt
from installer.run import CommandError
from installer.sanitize import sanitize_log_line


def install(method: Method, ctx: ExecContext, previous: Receipt | None) -> tuple[str, ...]:
    """Place menu files owned by this tool, returning nonfatal notes."""
    # shortcut: updates do not re-extract icons; call this from the update route to refresh them.
    desktop_id = method.params.get("desktop")
    if not isinstance(desktop_id, str):
        return ()
    notes: list[str] = []
    work: Path | None = None
    backups: dict[Path, bytes | None] = {}
    done: list[Path] = []
    made_dirs: list[str] = []
    try:
        hosts = [a.path for a in artifact_paths(method, locations.bin_dir(None))]
        if len(hosts) < 3:
            return ()
        binary, desktop_host, icon_host = hosts[:3]
        proven: set[Path] = (
            {a.path for a in previous.artifacts if a.type == "leaf"} if previous else set()
        )
        writable: list[Path] = []
        for host in (icon_host, desktop_host):
            if os.path.lexists(host) and host not in proven:
                notes.append(f"kept your existing {locations.display_path(host)}")
            else:
                writable.append(host)
        if not writable:
            return tuple(notes)
        work = Path(tempfile.mkdtemp(prefix="tools-installer-"))
        names = (f"{desktop_id}.desktop", f"{desktop_id}.png")
        for name in names:
            ctx.runner(
                [
                    "env",
                    f"--chdir={work}",
                    f"TMPDIR={work}",
                    str(binary),
                    "--appimage-extract",
                    name,
                ]
            )
        contents: list[bytes] = []
        for name in names:
            data = read_capped(staged_member(work / "AppDir", name), 1 << 20, follow_symlinks=False)
            if data is None:
                raise ExecutorError(f"cannot read extracted {name}")
            contents.append(data)
        text = render(
            contents[0].decode("utf-8"), binary=binary, icon=icon_host, drop=("X-KDE-Shortcuts",)
        )
        writes = [
            (host, data)
            for host, data in ((icon_host, contents[1]), (desktop_host, text.encode("utf-8")))
            if host in writable
        ]
        for host, _data in writes:
            if os.path.lexists(host):
                backup = read_capped(host, 1 << 20, follow_symlinks=False)
                if backup is None:
                    raise ExecutorError(f"cannot keep a copy of {locations.display_path(host)}")
                backups[host] = backup
            else:
                backups[host] = None
        for host, data in writes:
            made_dirs.extend(d for d in missing_dirs(host, Path.home()) if d not in made_dirs)
            host.parent.mkdir(parents=True, exist_ok=True)
            # shortcut: regular-file swaps go undetected; compare backups to upgrade.
            if os.path.islink(host):
                raise ExecutorError(
                    f"{locations.display_path(host)} is a symlink; not writing through it"
                )
            atomic_write_bytes(host, data, mode=0o644)
            done.append(host)
    except (
        CommandError,
        ExecutorError,
        DesktopEntryError,
        OSError,
        RuntimeError,
        UnicodeDecodeError,
    ) as exc:
        for host in reversed(done):
            try:
                backup = backups[host]
                if backup is None:
                    host.unlink(missing_ok=True)
                else:
                    atomic_write_bytes(host, backup, mode=0o644)
            except OSError:
                notes.append(
                    f"could not restore {locations.display_path(host)}: "
                    "left as this install wrote it"
                )
        with contextlib.suppress(OSError, RuntimeError):
            remove_created_dirs(tuple(made_dirs), Path.home())
        line = (str(exc).splitlines() or [repr(exc)])[0]
        notes.append(f"could not add the application menu entry: {sanitize_log_line(line)}")
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
    return tuple(notes)
