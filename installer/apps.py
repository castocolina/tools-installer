"""Executor for macOS GUI apps shipped as a zip containing a .app bundle.

The bundle lands in ~/Applications (never /Applications, zero sudo) and the
optional in-bundle CLI is symlinked into ~/.local/bin, per the PRD's location
policy. Extraction uses `ditto -x -k`, the canonical macOS extractor for .app
zips: it preserves the extended attributes and framework symlinks that
Info-ZIP `unzip` can mangle in Electron-style bundles. curl never sets
com.apple.quarantine, so installed apps launch without the Gatekeeper
"downloaded from the internet" dialog — identical to `brew install --cask`.
"""

import shlex
from pathlib import PurePosixPath

from installer.executors import ExecutorError, require_str
from installer.locations import applications_dir, bin_dir, ensure_dir
from installer.model import Method
from installer.run import Runner

APP_KINDS = ("app",)


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
