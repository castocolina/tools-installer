"""Container-only Ghostty lifecycle proof for scripts/container-e2e-verify.sh ghostty.

Run ``python -m tests.e2e_ghostty_driver <verb>`` with lifecycle (FUSE) or
lifecycle-extract (extract-and-run). Each prints install, sync, regions and removal
verdicts; FAILED or UNPROVEN exits 1, invalid arguments or a non-container exits 2.
"""

import os
import re
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

from installer import platform as host_platform
from installer import receipts
from installer.download import artifact_paths
from installer.model import Method
from installer.run import CommandError, run_command
from installer.terminal_regions import GHOSTTY, GHOSTTY_KEYS, ghostty_config_path, marker
from installer.terminal_shell import sync_terminal_shells
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    uninstall_one,
    verdict,
)

TOOL_ID = "ghostty"
ALLOWLIST = Path("scripts") / "e2e-residue-allowlist.txt"
RUN_SECONDS = 120.0
MOUNT_SECONDS = 15.0
# The standard data directories the menu entry and icon go into, and the installer's own state
# directory, stay as empty directories after the uninstall: a file left inside is still reported
# on its own, and 30 D-17 keeps documented config in place.
STANDARD_EMPTY_DIRS: Final = frozenset(
    {".local/share/applications/", ".local/share/icons/", ".local/share/tools-installer/"}
)


def pass_environment(mode: str, environ: Mapping[str, str]) -> dict[str, str]:
    env = dict(environ)
    if mode == "fuse":
        env.pop("APPIMAGE_EXTRACT_AND_RUN", None)
    elif mode == "extract":
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    else:
        raise ValueError(f"unknown mode: {mode}")
    return env


def _amd64_method() -> Method:
    return next(
        m for m in tool_by_id(TOOL_ID).methods if m.kind == "tarball" and m.arch == ("amd64",)
    )


def expected_receipt_paths(home: Path) -> list[str]:
    """Return artifact paths relative to home, which must equal Path.home()."""
    return [
        a.path.relative_to(home).as_posix()
        for a in artifact_paths(_amd64_method(), home / ".local/bin")
    ]


def expected_version_line() -> str:
    return f"Ghostty {_amd64_method().params['version']}"


def baseline_lookup(lookup: Callable[[str], str | None]) -> Callable[[str], str | None]:
    return lambda name: None if name == "ghostty" else lookup(name)


def run_lifecycle(
    steps: Sequence[tuple[str, Callable[[], list[str]]]], cleanup: Callable[[], list[str]]
) -> list[str]:
    lines: list[str] = []
    try:
        for prefix, step in steps:
            try:
                lines.extend(step())
            except Failed as exc:
                lines.append(verdict(exc.prefix, exc.detail))
            except (OSError, ValueError) as exc:
                lines.append(verdict(prefix, first_line(exc)))
    finally:
        try:
            lines.extend(cleanup())
        except Failed as exc:
            lines.append(verdict(exc.prefix, exc.detail))
        except (OSError, ValueError, CommandError) as exc:
            lines.append(verdict("TRACER_GHOSTTY_REMOVE_FAILED", first_line(exc)))
    return lines


def install_verdict(
    mode: str,
    method_kind: str,
    returncode: int,
    version_line: str,
    missing: Sequence[str],
    receipt_missing: Sequence[str],
    warning: str | None,
) -> str:
    problems: list[str] = []
    if method_kind != "tarball":
        problems.append(f"method {method_kind} is not tarball")
    if returncode != 0:
        problems.append(f"ghostty --version exited {returncode}")
    if version_line != expected_version_line():
        problems.append(f"ghostty --version printed {version_line or 'nothing'}")
    problems.extend(f"{path} is missing" for path in missing)
    problems.extend(f"the receipt lacks {path}" for path in receipt_missing)
    if warning is None or "community build" not in warning:
        problems.append("the install note lacks community build")
    return (
        verdict("TRACER_GHOSTTY_INSTALL_FAILED", "; ".join(problems))
        if problems
        else f"TRACER_GHOSTTY_INSTALL_OK mode={mode} method=tarball version={version_line}"
    )


def fuse_verdict(
    returncode: int, stdout: str, stderr: str, dev_fuse: bool, mounted: bool, expected_line: str
) -> str:
    problems: list[str] = []
    if "failed to utilize FUSE" in stderr:
        problems.append("the AppImage fell back to extract-and-run; FUSE was not used")
    if returncode != 0:
        problems.append(f"ghostty --version exited {returncode}")
    if first_line(stdout) != expected_line:
        problems.append(f"ghostty --version did not print {expected_line}")
    if not dev_fuse:
        problems.append("/dev/fuse is not present")
    elif not mounted:
        problems.append("no FUSE mount of the AppImage was observed")
    return (
        verdict("TRACER_GHOSTTY_FUSE_UNPROVEN", "; ".join(problems))
        if problems
        else "TRACER_GHOSTTY_FUSE_OK"
    )


def printed_mount_point(stdout: str) -> str | None:
    line = next((line.strip() for line in stdout.splitlines() if line.strip()), "")
    return line if line.startswith("/") else None


def fuse_mount_observed(mountinfo: str, mount_point: str | None) -> bool:
    if mount_point is None:
        return False
    for line in mountinfo.splitlines():
        left, separator, right = line.partition(" - ")
        fields, types = left.split(), right.split()
        if not separator or len(fields) < 5 or not types:
            continue
        path = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), fields[4])
        if path == mount_point and (types[0] == "fuse" or types[0].startswith("fuse.")):
            return True
    return False


def observe_fuse_mount(
    argv: Sequence[str], env: Mapping[str, str], read_mountinfo: Callable[[], str], seconds: float
) -> bool:
    # shortcut: reads only the first line; scan to a path if a runtime prints a banner.
    try:
        proc = subprocess.Popen(
            list(argv), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=dict(env)
        )
    except OSError:
        return False
    assert proc.stdout is not None
    try:
        ready, _, _ = select.select([proc.stdout], [], [], seconds)
        return bool(ready) and fuse_mount_observed(
            read_mountinfo(), printed_mount_point(proc.stdout.readline())
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        proc.stdout.close()


def sync_verdict(mode: str, configured: Sequence[str], warnings: Sequence[str]) -> str:
    problems = [] if "ghostty" in configured else ["ghostty was not configured"]
    problems.extend(warning for warning in warnings if warning.startswith("ghostty:"))
    return (
        verdict("TRACER_GHOSTTY_SYNC_FAILED", "; ".join(problems))
        if problems
        else f"TRACER_GHOSTTY_SYNC_OK mode={mode}"
    )


def regions_verdict(
    mode: str,
    text: str,
    zsh: str,
    show_config: str,
    show_rc: int,
    list_keybinds: str,
    keybinds_rc: int,
) -> str:
    shell, keys = marker(GHOSTTY, ">>>"), marker(GHOSTTY_KEYS, ">>>")
    problems: list[str] = []
    if shell not in text or marker(GHOSTTY, "<<<") not in text:
        problems.append("shell region missing")
    if keys not in text or marker(GHOSTTY_KEYS, "<<<") not in text:
        problems.append("keys region missing")
    if shell in text and keys in text and text.index(shell) > text.index(keys):
        problems.append("the shell region is not above the keys region")
    command = "command = " + shlex.join((zsh, "-l"))
    binding = r"keybind = ctrl+shift+k=text:\x0c"
    if show_rc != 0:
        problems.append(f"ghostty +show-config exited {show_rc}")
    if command not in (line.strip() for line in show_config.splitlines()):
        problems.append(f"ghostty +show-config lacks {command}")
    if keybinds_rc != 0:
        problems.append(f"ghostty +list-keybinds exited {keybinds_rc}")
    if binding not in (line.strip() for line in list_keybinds.splitlines()):
        problems.append(f"ghostty +list-keybinds lacks {binding}")
    return (
        verdict("TRACER_GHOSTTY_REGIONS_FAILED", "; ".join(problems))
        if problems
        else f"TRACER_GHOSTTY_REGIONS_OK mode={mode}"
    )


def leftovers(before: Sequence[str], after: Sequence[str], allowed: Sequence[str]) -> list[str]:
    return sorted(
        path
        for path in set(after) - set(before)
        if not any(
            path.rstrip("/") == entry.rstrip("/")
            or path.startswith(entry.rstrip("/") + "/")
            or entry.startswith(path.rstrip("/") + "/")
            for entry in allowed
        )
    )


def is_state_record(path: str) -> bool:
    """The tuning record and the created-file records the installer keeps for Ghostty."""
    prefix = ".local/share/tools-installer/"
    return path.startswith(
        (f"{prefix}terminal-tuning-ghostty", f"{prefix}terminal-ghostty-created")
    )


def remove_verdict(
    mode: str,
    *,
    before: Sequence[str],
    installed: Sequence[str],
    after: Sequence[str],
    allowed: Sequence[str],
    tmp_left: Sequence[str],
    receipt_left: bool,
    receipt_paths: Sequence[str],
    region_files: Sequence[str],
    seeded: Mapping[str, str],
    current: Mapping[str, str | None],
) -> str:
    expected = set(receipt_paths) | (set(region_files) - set(before))
    expected |= {path for path in set(installed) - set(before) if is_state_record(path)}
    problems = [
        f"{path} appeared after the install and is neither a receipt path nor a region file"
        for path in leftovers(before, installed, allowed)
        if path not in expected and not path.endswith("/")
    ]
    problems.extend(
        f"{path} is missing after the install" for path in sorted(expected - set(installed))
    )
    remaining = [
        path
        for path in leftovers(before, after, allowed)
        if path not in STANDARD_EMPTY_DIRS
        and not (path.endswith("/") and any(name.startswith(path) for name in seeded))
    ]
    problems.extend(f"{path} still present" for path in remaining[:10])
    if len(remaining) > 10:
        problems.append(f"and {len(remaining) - 10} more")
    problems.extend(
        f"{path} existed before the install and is gone"
        for path in sorted(set(before) - set(after))
    )
    problems.extend(
        f"{path} changed: the seeded user content is not intact"
        for path in sorted(seeded)
        if current.get(path) != seeded[path]
    )
    problems.extend(f"/tmp holds {name}" for name in sorted(tmp_left))
    if receipt_left:
        problems.append("the receipt is still present")
    return (
        verdict("TRACER_GHOSTTY_REMOVE_FAILED", "; ".join(problems))
        if problems
        else f"TRACER_GHOSTTY_REMOVE_OK mode={mode}"
    )


def home_listing(home: Path, workspace: Path) -> list[str]:
    result: list[str] = []
    for root, dirs, files in os.walk(home):
        base = Path(root)
        for name in list(dirs):
            path = base / name
            if path.is_symlink():
                result.append(path.relative_to(home).as_posix())
                dirs.remove(name)
            elif path == workspace:
                dirs.remove(name)
            else:
                result.append(path.relative_to(home).as_posix() + "/")
        result.extend((base / name).relative_to(home).as_posix() for name in files)
    return sorted(result)


def seed_user_content(home: Path) -> dict[str, str]:
    seeded = {
        ".config/ghostty/config.ghostty": "font-size = 13\n",
        ".config/ghostty/themes/user-theme": "background = 101010\n",
    }
    for name, text in seeded.items():
        path = home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return seeded


def current_content(home: Path, paths: Iterable[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in paths:
        try:
            result[name] = (home / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            result[name] = None
    return result


def allowed_prefixes(text: str) -> list[str]:
    return [value for line in text.splitlines() if (value := line.split("#", 1)[0].strip())]


def tmp_leftovers(names: Sequence[str]) -> list[str]:
    return sorted(name for name in names if name.startswith("tools-installer-"))


def inspect_tmp() -> list[str]:
    try:
        return tmp_leftovers(os.listdir("/tmp"))
    except OSError as exc:
        raise OSError(f"could not inspect /tmp: {exc}") from exc


def _ghostty_env(home: Path, scratch: Path, mode: str) -> dict[str, str]:
    return pass_environment(
        mode,
        {
            "HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "TMPDIR": str(scratch),
        },
    )


def run_ghostty(
    binary: Path, home: Path, scratch: Path, mode: str, *args: str
) -> tuple[int, str, str]:
    """Run the AppImage with its output in files: the FUSE fallback leaves a mount helper that
    keeps a pipe open after the command exits, and a pipe read would wait for it."""
    out_file = scratch / "run.out"
    err_file = scratch / "run.err"
    try:
        with out_file.open("wb") as out, err_file.open("wb") as err:
            result = subprocess.run(
                [str(binary), *args],
                stdout=out,
                stderr=err,
                timeout=RUN_SECONDS,
                check=False,
                env=_ghostty_env(home, scratch, mode),
            )
        return (
            result.returncode,
            out_file.read_text(encoding="utf-8", errors="replace"),
            err_file.read_text(encoding="utf-8", errors="replace"),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", first_line(exc)


def _lifecycle(mode: str) -> list[str]:
    """The loop needs a real container; host tests cover its verdicts and helpers."""
    env = pass_environment(mode, os.environ)
    os.environ.clear()
    os.environ.update(env)
    home = Path.home()
    ghostty = home / ".local/bin/ghostty"
    zsh = shutil.which("zsh")
    if zsh is None:
        raise Failed("TRACER_GHOSTTY_INSTALL_FAILED", "zsh is not installed in the box")
    platform = host_platform.detect()
    sync_terminal_shells(
        home=home,
        environ=dict(os.environ),
        platform=platform,
        lookup=baseline_lookup(shutil.which),
        write=True,
    )
    seeded = seed_user_content(home)
    before = home_listing(home, Path.cwd())
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        scratch = Path(directory)

        def install() -> list[str]:
            outcome = install_one(tool_by_id(TOOL_ID), "TRACER_GHOSTTY_INSTALL_FAILED")
            dev_fuse = Path("/dev/fuse").exists() if mode == "fuse" else False
            mounted = (
                observe_fuse_mount(
                    [str(ghostty), "--appimage-mount"],
                    _ghostty_env(home, scratch, mode),
                    lambda: Path("/proc/self/mountinfo").read_text(
                        encoding="utf-8", errors="replace"
                    ),
                    MOUNT_SECONDS,
                )
                if dev_fuse
                else False
            )
            rc, stdout, stderr = run_ghostty(ghostty, home, scratch, mode, "--version")
            expected = expected_receipt_paths(home)
            receipt = receipts.read(TOOL_ID)
            recorded: set[Path] = {a.path for a in receipt.artifacts} if receipt else set()
            lines = [
                install_verdict(
                    mode,
                    outcome.method_kind or "unknown",
                    rc,
                    first_line(stdout),
                    [p for p in expected if not (home / p).exists()],
                    [p for p in expected if home / p not in recorded],
                    outcome.postinstall_warning,
                )
            ]
            if mode == "fuse":
                lines.append(
                    fuse_verdict(rc, stdout, stderr, dev_fuse, mounted, expected_version_line())
                )
            return lines

        def sync() -> list[str]:
            result = sync_terminal_shells(
                home=home,
                environ=dict(os.environ),
                platform=platform,
                lookup=shutil.which,
                write=True,
            )
            return [sync_verdict(mode, result.configured, result.warnings)]

        def regions() -> list[str]:
            text = ghostty_config_path(platform.os, home, dict(os.environ)).read_text(
                encoding="utf-8"
            )
            show_rc, show, _ = run_ghostty(ghostty, home, scratch, mode, "+show-config")
            keys_rc, keys, _ = run_ghostty(ghostty, home, scratch, mode, "+list-keybinds")
            return [regions_verdict(mode, text, zsh, show, show_rc, keys, keys_rc)]

        def cleanup() -> list[str]:
            installed = home_listing(home, Path.cwd())
            uninstall_one(tool_by_id(TOOL_ID), run_command)
            after = home_listing(home, Path.cwd())
            tmp_left = inspect_tmp()
            return [
                remove_verdict(
                    mode,
                    before=before,
                    installed=installed,
                    after=after,
                    allowed=allowed_prefixes(ALLOWLIST.read_text(encoding="utf-8")),
                    tmp_left=tmp_left,
                    receipt_left=receipts.read(TOOL_ID) is not None,
                    receipt_paths=expected_receipt_paths(home),
                    region_files=[
                        ghostty_config_path(platform.os, home, dict(os.environ))
                        .relative_to(home)
                        .as_posix()
                    ],
                    seeded=seeded,
                    current=current_content(home, seeded),
                )
            ]

        return run_lifecycle(
            [
                ("TRACER_GHOSTTY_INSTALL_FAILED", install),
                ("TRACER_GHOSTTY_SYNC_FAILED", sync),
                ("TRACER_GHOSTTY_REGIONS_FAILED", regions),
            ],
            cleanup,
        )


_HANDLERS = {
    "lifecycle": lambda: _lifecycle("fuse"),
    "lifecycle-extract": lambda: _lifecycle("extract"),
}


def accepts(args: Sequence[str]) -> bool:
    return len(args) == 1 and args[0] in _HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print(f"usage: e2e_ghostty_driver {' | '.join(_HANDLERS)}", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the ghostty driver runs only inside the disposable container")
        return 2
    try:
        lines = _HANDLERS[args[0]]()
    except Failed as exc:
        print(verdict(exc.prefix, first_line(exc.detail)))
        return 1
    except (OSError, ValueError) as exc:
        print(f"ERROR {first_line(exc) or type(exc).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line or "_UNPROVEN" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
