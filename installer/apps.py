"""Executor for macOS GUI apps shipped as a zip containing a .app bundle.

The bundle lands in ~/Applications (never /Applications, zero sudo) and the
optional in-bundle CLI is symlinked into ~/.local/bin, per the PRD's location
policy. Extraction uses `ditto -x -k`, the canonical macOS extractor for .app
zips: it preserves the extended attributes and framework symlinks that
Info-ZIP `unzip` can mangle in Electron-style bundles. curl never sets
com.apple.quarantine, so installed apps launch without the Gatekeeper
"downloaded from the internet" dialog — identical to `brew install --cask`.
"""

import os
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from installer.atomic import (
    NEW_SUFFIX,
    OLD_SUFFIX,
    capture_symlink_target,
    recover_update_remnants,
    replace_symlink,
    staged_sibling,
)
from installer.executors import ExecutorError, require_str
from installer.locations import applications_dir, bin_dir, ensure_dir
from installer.model import Method
from installer.run import Runner

APP_KINDS = ("app",)


@dataclass(frozen=True)
class UpdateExecResult:
    """Result of an update-safe app-bundle replacement.

    App zips have no published checksum, so this type has no `verified` field.
    `warnings` carries non-fatal cleanup failures (a leftover `.old` bundle
    that did not fail the update).
    """

    warnings: tuple[str, ...] = ()


def cli_spec(method: Method) -> tuple[str, str] | None:
    """(bundle-relative CLI path, symlink name) for the optional `cli` param.

    Single source of truth for the symlink name: install_app creates it and
    uninstall planning derives the same name (or skips when this raises).
    """
    cli = method.params.get("cli")
    if cli is None:
        return None
    if not isinstance(cli, str) or not cli:
        raise ExecutorError("method 'app' param 'cli' must be a non-empty string")
    path = PurePosixPath(cli)
    if path.is_absolute() or ".." in path.parts:
        # An absolute or parent-traversing cli would symlink outside the bundle.
        raise ExecutorError(f"invalid cli path '{cli}'")
    name = path.name
    if name in ("", "."):
        raise ExecutorError(f"cannot derive a CLI name from '{cli}'")
    return cli, name


def install_app(method: Method, runner: Runner) -> None:
    """Download the app zip, extract in a temp dir, move the .app into place.

    Extract-then-move keeps ~/Applications free of partial bundles on any
    failure; a non-zero exit anywhere breaks the && chain (CommandError),
    which falls through to the next applicable ladder method, if any.
    """
    url = require_str(method, "url")
    app = require_str(method, "app")
    if PurePosixPath(app).name != app or app in (".", ".."):
        # A nested or traversal bundle name would move/symlink outside ~/Applications.
        raise ExecutorError(f"invalid app bundle name '{app}'")
    spec = cli_spec(method)  # validate every param before any side effect
    try:
        apps = ensure_dir(applications_dir())
    except OSError as exc:
        raise ExecutorError(f"cannot create Applications dir: {exc}") from exc
    pipeline = (
        "tmp=$(mktemp -d) && trap 'rm -rf \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp/app.zip" -- {shlex.quote(url)}'
        ' && ditto -x -k "$tmp/app.zip" "$tmp/x"'
        # Adjacent quoting: "$tmp/x/" expands in the shell, the bundle name stays literal.
        f' && mv "$tmp/x/"{shlex.quote(app)} {shlex.quote(str(apps))}/'
    )
    runner(["sh", "-c", pipeline])
    if spec is None:
        return
    cli, name = spec
    try:
        dest = ensure_dir(bin_dir(None))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    runner(["ln", "-sf", str(apps / app / cli), str(dest / name)])


def update_app(method: Method, runner: Runner) -> UpdateExecResult:
    """Stage a new bundle, then atomically replace the live one via os.replace.

    Same rollback state machine as `download.update_download`: capture the
    original CLI symlink target, recover remnants, extract into `.new`,
    aside-move the live bundle, swap, recreate the CLI symlink via
    `os.symlink`+`os.replace`, validate, then remove `.old`. Never shells
    `mv` or `ln`. `install_app`'s existing `mv` stays install-only.
    """
    url = require_str(method, "url")
    app = require_str(method, "app")
    if PurePosixPath(app).name != app or app in (".", ".."):
        raise ExecutorError(f"invalid app bundle name '{app}'")
    spec = cli_spec(method)
    try:
        apps = ensure_dir(applications_dir())
    except OSError as extra:
        raise ExecutorError(f"cannot create Applications dir: {extra}") from extra
    live = apps / app
    original_target: str | None = None
    link: Path | None = None
    if spec is not None:
        _cli, name = spec
        try:
            dest = ensure_dir(bin_dir(None))
        except OSError as extra:
            raise ExecutorError(f"cannot create bin dir: {extra}") from extra
        link = dest / name
        original_target = capture_symlink_target(link)
    recover_update_remnants(live)
    staging = Path(tempfile.mkdtemp(prefix="tools-installer-update-"))
    new = staged_sibling(live, NEW_SUFFIX)
    old = staged_sibling(live, OLD_SUFFIX)
    try:
        zip_path = staging / "app.zip"
        extract_root = staging / "x"
        runner(["curl", "-fsSL", "-o", str(zip_path), "--", url])
        extract_root.mkdir(parents=True, exist_ok=True)
        runner(["ditto", "-x", "-k", str(zip_path), str(extract_root)])
        staged_bundle = extract_root / app
        if not staged_bundle.exists():
            raise ExecutorError(f"extracted zip did not contain '{app}'")
        if new.exists():
            shutil.rmtree(new)
        os.replace(staged_bundle, new)
        try:
            if live.exists():
                os.replace(live, old)
        except OSError as extra:
            shutil.rmtree(new, ignore_errors=True)
            raise ExecutorError(f"aside-move failed; prior installation intact: {extra}") from extra
        try:
            os.replace(new, live)
        except OSError as extra:
            if old.exists():
                os.replace(old, live)
            raise ExecutorError(f"swap failed; prior installation restored: {extra}") from extra
        try:
            _relink_app_cli(spec, live, link)
            _validate_app(live, spec)
        except (OSError, ExecutorError) as extra:
            _undo_app_swap(live, new, old, link, original_target)
            raise ExecutorError(
                f"update failed after swap; prior installation restored: {extra}"
            ) from extra
        warnings: list[str] = []
        if old.exists():
            try:
                shutil.rmtree(old)
            except OSError as extra:
                warnings.append(str(extra))
        return UpdateExecResult(warnings=tuple(warnings))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _relink_app_cli(spec: tuple[str, str] | None, live: Path, link: Path | None) -> None:
    if spec is None or link is None:
        return
    cli, _name = spec
    replace_symlink(link, str(live / cli))


def _validate_app(live: Path, spec: tuple[str, str] | None) -> None:
    if not live.exists():
        raise ExecutorError(f"updated bundle at {live} is missing")
    if spec is None:
        return
    cli, _name = spec
    path = live / cli
    if not path.exists() or not os.access(path, os.X_OK):
        raise ExecutorError(f"updated CLI at {path} is missing or not executable")


def _undo_app_swap(
    live: Path, new: Path, old: Path, link: Path | None, original_target: str | None
) -> None:
    if live.exists():
        os.replace(live, new)
    if old.exists():
        os.replace(old, live)
    if link is not None and original_target is not None:
        replace_symlink(link, original_target)
    shutil.rmtree(new, ignore_errors=True)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
