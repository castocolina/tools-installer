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
import shutil
import tempfile
from collections.abc import Sequence
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
from installer.checksums import ChecksumMismatch, sha256_file
from installer.download import pinned_url
from installer.executors import (
    ExecutorError,
    method_smoke_argv,
    require_str,
    smoke_binary,
    staged_member,
)
from installer.locations import applications_dir, bin_dir, ensure_dir
from installer.model import Method
from installer.run import Runner

APP_KINDS = ("app",)

_UNVERIFIED_REASON = "unpinned url; no sha256 to verify against"


@dataclass(frozen=True)
class UpdateExecResult:
    """Result of an update-safe app-bundle replacement.

    Pinned app zips are sha256-verified before extraction; this type carries
    only non-fatal cleanup warnings (a leftover `.old` bundle that did not
    fail the update).
    """

    warnings: tuple[str, ...] = ()


def cli_spec(method: Method) -> tuple[str, str] | None:
    """(bundle-relative CLI path, symlink name) for the optional `cli` param.

    Single source of truth for the symlink name: install_app creates it and
    uninstall planning derives the same name (or skips when this raises).
    The link name is the validated `cli_name` param when declared, otherwise
    the basename of `cli`. This function is the only reader of `cli_name`.
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
    cli_name = method.params.get("cli_name")
    if cli_name is None:
        name = path.name
    else:
        bad_name = (
            not isinstance(cli_name, str)
            or not cli_name
            or PurePosixPath(cli_name).name != cli_name
            or cli_name in (".", "..")
        )
        if bad_name:
            raise ExecutorError(f"invalid cli_name '{cli_name}'")
        name = str(cli_name)
    if name in ("", "."):
        raise ExecutorError(f"cannot derive a CLI name from '{cli}'")
    return cli, name


def _declared_sha256(method: Method) -> str | None:
    raw = method.params.get("sha256")
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw:
        raise ExecutorError("method 'app' param 'sha256' must be a non-empty string")
    return raw


def install_app(method: Method, runner: Runner) -> str | None:
    """Download the app zip, verify when pinned, stage, smoke, and install.

    Returns None when the zip was sha256-verified. Otherwise returns the
    unverified reason after a successful install.
    """
    return _stage_and_swap_app(method, runner, smoke_argv=method_smoke_argv(method))


def update_app(method: Method, runner: Runner) -> UpdateExecResult:
    """Stage a new bundle, then atomically replace the live one via os.replace.

    Same rollback state machine as `download.update_download`: capture the
    original CLI symlink target, recover remnants, extract into `.new`,
    aside-move the live bundle, swap, recreate the CLI symlink via
    `os.symlink`+`os.replace`, validate, then remove `.old`. Never shells
    `mv` or `ln`. Updates never smoke the staged CLI (D-06).
    """
    _stage_and_swap_app(method, runner, smoke_argv=None)
    app = require_str(method, "app")
    live = ensure_dir(applications_dir()) / app
    old = staged_sibling(live, OLD_SUFFIX)
    warnings: list[str] = []
    if old.exists():
        try:
            shutil.rmtree(old)
        except OSError as extra:
            warnings.append(str(extra))
    return UpdateExecResult(warnings=tuple(warnings))


def _stage_and_swap_app(
    method: Method,
    runner: Runner,
    *,
    smoke_argv: Sequence[str] | None,
) -> str | None:
    url = pinned_url(method)
    app = require_str(method, "app")
    if PurePosixPath(app).name != app or app in (".", ".."):
        raise ExecutorError(f"invalid app bundle name '{app}'")
    spec = cli_spec(method)
    expected_sha256 = _declared_sha256(method)
    try:
        apps = ensure_dir(applications_dir())
    except OSError as exc:
        raise ExecutorError(f"cannot create Applications dir: {exc}") from exc
    live = apps / app
    original_target: str | None = None
    link: Path | None = None
    if spec is not None:
        _cli, name = spec
        try:
            dest = ensure_dir(bin_dir(None))
        except OSError as exc:
            raise ExecutorError(f"cannot create bin dir: {exc}") from exc
        link = dest / name
        original_target = capture_symlink_target(link)
    recover_update_remnants(live)
    staging = Path(tempfile.mkdtemp(prefix="tools-installer-update-"))
    new = staged_sibling(live, NEW_SUFFIX)
    old = staged_sibling(live, OLD_SUFFIX)
    verified = expected_sha256 is not None
    try:
        zip_path = staging / "app.zip"
        extract_root = staging / "x"
        runner(["curl", "-fsSL", "-o", str(zip_path), "--", url])
        if expected_sha256 is not None:
            try:
                actual = sha256_file(zip_path)
            except OSError as extra:
                raise ExecutorError(
                    f"cannot hash downloaded asset '{PurePosixPath(url).name}': {extra}"
                ) from extra
            if actual != expected_sha256:
                raise ChecksumMismatch(PurePosixPath(url).name, expected_sha256, actual)
        extract_root.mkdir(parents=True, exist_ok=True)
        runner(["ditto", "-x", "-k", str(zip_path), str(extract_root)])
        staged_bundle = extract_root / app
        if not staged_bundle.exists():
            raise ExecutorError(f"extracted zip did not contain '{app}'")
        if spec is not None:
            cli, _name = spec
            cli_path = staged_member(staged_bundle, cli)
            if not os.access(cli_path, os.X_OK):
                raise ExecutorError(f"staged CLI at {cli_path} is missing or not executable")
            if smoke_argv is not None:
                smoke_binary(cli_path, smoke_argv)
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
        return None if verified else _UNVERIFIED_REASON
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
    if not path.is_file() or not os.access(path, os.X_OK):
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
    elif link is not None and link.is_symlink():
        link.unlink()
    shutil.rmtree(new, ignore_errors=True)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
