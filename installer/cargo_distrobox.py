"""Build a tool from a GitHub release tag in a throwaway Distrobox and place its files.

One run: resolve the tag, create a box whose HOME is a host temp dir, clone and build
inside it, stage the outputs next to their live paths, smoke the staged binary, swap them
all in. The box, the image this run pulled and the temp dir are removed on every outcome.
Imported only by `engine`, never by `executors`, so there is no import cycle.
"""

import os
import re
import secrets
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

from installer import locations, receipts
from installer.atomic import NEW_SUFFIX, OLD_SUFFIX, atomic_write_text, staged_sibling
from installer.desktop_entry import DesktopEntryError, render
from installer.download import ExecContext, artifact_paths
from installer.executors import ExecutorError, method_smoke_argv, smoke_binary, staged_member
from installer.model import Method
from installer.run import CommandError, command_error_line, run_query

# The box mounts the host /tmp and `--home` replaces the HOME mount, so a run dir under
# another $TMPDIR would be invisible inside the box.
RUN_ROOT = Path("/") / "tmp"  # built from parts: a bare "/tmp" literal trips bandit B108

# Per-step bounds in seconds. Unmeasured guesses (24-RESEARCH A5); the first `enter` also
# runs the box init and the package install, so the clone step gets the long bound.
CREATE_TIMEOUT = 900
CLONE_TIMEOUT = 900
BUILD_TIMEOUT = 1800
TIC_TIMEOUT = 60
REMOVE_TIMEOUT = 120
_IMAGE_QUERY_TIMEOUT = 20.0

# The release tag becomes a git argument inside the box: letters, digits, dot, underscore, dash,
# never a leading dash. It is also passed after `--`.
_TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def podman_image_exists(ref: str) -> bool | None:
    """True when podman has the image, False on its exit 1, None when it could not tell."""
    try:
        run_query(["podman", "image", "exists", ref], timeout=_IMAGE_QUERY_TIMEOUT)
    except CommandError as exc:
        return False if exc.returncode == 1 else None
    return True


# Module-level so a test replaces it, the `executors.launch_puppeteer` precedent.
image_exists: Callable[[str], bool | None] = podman_image_exists


def box_name(tool_id: str) -> str:
    return f"ti-cargo-{tool_id}-{os.getpid()}-{secrets.token_hex(4)}"


def _param(method: Method, key: str) -> str:
    value = method.params.get(key)
    if not isinstance(value, str) or not value:
        raise ExecutorError(f"method 'cargo_distrobox' is missing or empty required param '{key}'")
    return value


def _artifact_boxes(method: Method) -> tuple[str, ...]:
    declared = cast(list[dict[str, str]], method.params.get("artifacts", []))
    return tuple(entry["box"] for entry in declared)


class _Run:
    """The argv of one box run; every word is its own list item, no shell."""

    def __init__(self, ctx: ExecContext, name: str, tmp: Path) -> None:
        self._ctx = ctx
        self._name = name
        self.tmp = tmp

    def step(self, seconds: int, argv: list[str]) -> None:
        # XDG_CACHE_HOME keeps `distrobox enter`'s FIFO out of the real ~/.cache; the manager is
        # pinned because the image accounting and `rmi` below are podman's, whatever the user runs.
        prefix = [
            "timeout",
            "--kill-after=10",
            str(seconds),
            "env",
            f"XDG_CACHE_HOME={self.tmp / 'cache'}",
            "DBX_CONTAINER_MANAGER=podman",
        ]
        self._ctx.runner([*prefix, *argv])

    def enter(self, seconds: int, command: list[str]) -> None:
        enter = ["distrobox", "enter", "--no-tty", "--no-workdir", "--name", self._name, "--"]
        self.step(seconds, [*enter, *command])


def _build(run: _Run, method: Method, name: str, tag: str) -> None:
    tmp = run.tmp
    create = [
        "distrobox",
        "create",
        "--yes",
        "--no-entry",
        "--home",
        str(tmp),
        "--image",
        _param(method, "image"),
        "--name",
        name,
    ]
    packages = method.params.get("packages")
    if isinstance(packages, list) and packages:
        create += ["--additional-packages", " ".join(cast(list[str], packages))]
    run.step(CREATE_TIMEOUT, create)
    url = f"https://github.com/{_param(method, 'repo')}.git"
    run.enter(
        CLONE_TIMEOUT,
        ["git", "clone", "--depth", "1", "--branch", tag, "--", url] + [str(tmp / "src")],
    )
    run.enter(
        BUILD_TIMEOUT,
        ["cargo", "build", "--release", "--locked", "--manifest-path", str(tmp / "src/Cargo.toml")],
    )
    if any(box.startswith("terminfo/") for box in _artifact_boxes(method)):
        # shortcut: the terminfo names are Alacritty's, the only user of this kind;
        # lift them into a param when a second tool compiles terminfo.
        run.enter(
            TIC_TIMEOUT,
            [
                "tic",
                "-xe",
                "alacritty,alacritty-direct",
                "-o",
                str(tmp / "terminfo"),
                str(tmp / "src/extra/alacritty.info"),
            ],
        )


def _stage(method: Method, tmp: Path, staged: list[tuple[Path, Path]], notes: list[str]) -> None:
    """Copy every box output to a `.new` sibling of its live path, appending (new, live) pairs.

    The caller owns `staged`, so a failure part-way still lets it delete every `.new`. A
    non-binary path that already exists and that no receipt records is the user's own: it is
    kept as it is and named in `notes`."""
    hosts = [artifact.path for artifact in artifact_paths(method, locations.bin_dir(None))]
    boxes = _artifact_boxes(method)
    if not hosts or len(hosts) != len(boxes):
        raise ExecutorError("method 'cargo_distrobox' declares no usable artifacts")
    binary = hosts[0]
    icon = next((host for host in hosts if "/share/icons/" in host.as_posix()), None)
    proven = receipts.recorded_elsewhere("")
    for box, host in zip(boxes, hosts, strict=True):
        source = staged_member(tmp, box)
        if host != binary and os.path.lexists(host) and host not in proven:
            notes.append(f"kept your existing {locations.display_path(host)}")
            continue
        new = staged_sibling(host, NEW_SUFFIX)
        staged.append((new, host))
        host.parent.mkdir(parents=True, exist_ok=True)
        if host.suffix == ".desktop":
            text = render(source.read_text(encoding="utf-8"), binary=binary, icon=icon)
            atomic_write_text(new, text, mode=0o644)
        else:
            shutil.copyfile(source, new)
            new.chmod(0o755 if host == binary else 0o644)
        if host == binary:
            smoke_binary(new, method_smoke_argv(method))


def _swap(staged: list[tuple[Path, Path]]) -> None:
    """Move every `.new` over its live path; a failure part-way restores the earlier swaps."""
    done: list[tuple[Path, Path | None]] = []
    try:
        for new, host in staged:
            old = staged_sibling(host, OLD_SUFFIX) if os.path.lexists(host) else None
            # recorded first so an interrupt right after the move is undone. shortcut: a stale
            # `.old` from an earlier failed rollback would be restored too (it was reported).
            done.append((host, old))
            if old is not None:
                os.replace(host, old)
            os.replace(new, host)
    except BaseException as exc:
        stuck: list[str] = []
        for host, old in reversed(done):
            try:
                if old is None:
                    host.unlink(missing_ok=True)
                elif os.path.lexists(old):
                    os.replace(old, host)
            except OSError:
                stuck.append(str(old or host))
        if stuck and isinstance(exc, Exception):
            raise ExecutorError(
                f"swap failed ({exc}); rollback failed; prior files are at {', '.join(stuck)}"
            ) from exc
        raise
    for _host, old in done:
        if old is not None:
            old.unlink(missing_ok=True)


def _cleanup(run: _Run, name: str, image: str, *, pulled: bool) -> list[str]:
    """Remove the box, then the image this run pulled, then the temp dir; failures are notes."""
    notes: list[str] = []
    try:
        try:
            run.step(REMOVE_TIMEOUT, ["distrobox", "rm", "--force", "--rm-home", name])
        except CommandError:
            notes.append(
                f"could not remove the Distrobox {name}; "
                f"remove it with `distrobox rm --force --rm-home {name}`"
            )
        if pulled:
            try:
                run.step(REMOVE_TIMEOUT, ["podman", "rmi", image])
            except CommandError as exc:
                notes.append(
                    f"kept the image {image}: podman could not remove it "
                    f"({command_error_line(exc)})"
                )
    finally:
        shutil.rmtree(run.tmp, ignore_errors=True)
    if run.tmp.exists():  # `distrobox rm --rm-home` leaves the --home dir (1.8.2.5)
        notes.append(f"could not remove {run.tmp}; remove it yourself")
    return notes


def install(method: Method, ctx: ExecContext) -> tuple[str, ...]:
    """Build the latest release in a throwaway box and place its artifacts; return row notes.

    Raises `ExecutorError` (the build's first error line) after the cleanups on any failure."""
    repo = _param(method, "repo")
    image = _param(method, "image")
    tag = ctx.resolve_release(repo).tag
    if _TAG_RE.fullmatch(tag) is None:
        raise ExecutorError(f"refusing release tag {tag!r} of {repo}: not a safe git ref")
    name = box_name(repo.split("/")[-1].lower())
    state = image_exists(image)
    pulled = state is False
    notes: list[str] = []
    if state is True:
        notes.append(f"kept the existing image {image}")
    elif state is None:
        notes.append(f"kept the image {image}: could not tell whether it was already there")
    tmp = Path(tempfile.mkdtemp(prefix="tools-installer-cargo-", dir=RUN_ROOT))
    run = _Run(ctx, name, tmp)
    staged: list[tuple[Path, Path]] = []
    failure: CommandError | OSError | DesktopEntryError | ExecutorError | None = None
    cleanup_notes: list[str] = []
    try:
        (tmp / "terminfo").mkdir()
        (tmp / "cache").mkdir()
        _build(run, method, name, tag)
        _stage(method, tmp, staged, notes)
        _swap(staged)
    except (CommandError, OSError, DesktopEntryError, ExecutorError) as exc:
        failure = exc
    finally:
        leftovers: list[str] = []
        for new, _host in staged:
            try:
                new.unlink(missing_ok=True)
            except OSError:
                leftovers.append(f"could not remove {new}; delete it yourself")
        cleanup_notes = [*leftovers, *_cleanup(run, name, image, pulled=pulled)]
    if failure is not None:
        line = (
            command_error_line(failure)
            if isinstance(failure, CommandError)
            else (str(failure).splitlines() or [repr(failure)])[0]
        )
        raise ExecutorError("; ".join([line, *cleanup_notes])) from failure
    return (*notes, *cleanup_notes)
