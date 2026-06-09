"""Download-based executors: github_release and tarball binaries into a bin dir."""

import shlex
from dataclasses import dataclass

from installer.assets import arch_tokens, render_asset
from installer.executors import ExecutorError, require_str
from installer.locations import bin_dir, ensure_dir
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner
from installer.versions import VersionResolver

DOWNLOAD_KINDS = ("github_release", "tarball")


@dataclass(frozen=True)
class ExecContext:
    runner: Runner
    platform: Platform
    resolve_version: VersionResolver


def _opt_str(method: Method, key: str) -> str | None:
    value = method.params.get(key)
    return value if isinstance(value, str) and value else None


def _github_release_url(method: Method, ctx: ExecContext) -> str:
    repo = require_str(method, "repo")
    template = require_str(method, "asset")
    ver = ctx.resolve_version(repo)
    try:
        asset = render_asset(template, ver, arch_tokens(ctx.platform.arch))
    except ValueError as exc:
        raise ExecutorError(f"cannot build asset name for '{repo}': {exc}") from exc
    return f"https://github.com/{repo}/releases/download/v{ver}/{asset}"


def install_download(method: Method, ctx: ExecContext) -> None:
    """Download a release archive/binary into the bin dir and make it executable."""
    if method.kind == "github_release":
        url = _github_release_url(method, ctx)
    elif method.kind == "tarball":
        url = require_str(method, "url")
    else:
        raise ExecutorError(f"no download executor for kind '{method.kind}'")

    member = require_str(method, "member")
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    target = dest / member
    quoted_url = shlex.quote(url)
    quoted_target = shlex.quote(str(target))
    quoted_dest = shlex.quote(str(dest))
    quoted_member = shlex.quote(member)
    if method.params.get("raw") is True:
        ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_target} -- {quoted_url}"])
    else:
        ctx.runner(
            [
                "sh",
                "-c",
                f"curl -fsSL -- {quoted_url} | tar -xz -C {quoted_dest} -- {quoted_member}",
            ]
        )
    ctx.runner(["chmod", "+x", str(target)])
