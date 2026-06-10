"""Download-based executors: github_release and tarball binaries into a bin dir."""

import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath

from installer.assets import arch_tokens, render_asset
from installer.executors import ExecutorError, require_str
from installer.locations import bin_dir, ensure_dir, opt_dir
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner
from installer.versions import TagResolver

DOWNLOAD_KINDS = ("github_release", "tarball")


@dataclass(frozen=True)
class ExecContext:
    runner: Runner
    platform: Platform
    resolve_tag: TagResolver


def _opt_str(method: Method, key: str) -> str | None:
    value = method.params.get(key)
    return value if isinstance(value, str) and value else None


def _opt_int(method: Method, key: str, default: int) -> int:
    value = method.params.get(key)
    # bool is an int subclass; reject it so `strip = true` can't masquerade as strip=1.
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _github_release_url(method: Method, ctx: ExecContext) -> str:
    repo = require_str(method, "repo")
    template = require_str(method, "asset")
    tag = ctx.resolve_tag(repo)
    ver = tag.removeprefix("v")  # asset filenames use the bare number; the path uses the tag
    try:
        asset = render_asset(template, ver, arch_tokens(ctx.platform.arch))
    except ValueError as exc:
        raise ExecutorError(f"cannot build asset name for '{repo}': {exc}") from exc
    return f"https://github.com/{repo}/releases/download/{tag}/{asset}"


def install_download(method: Method, ctx: ExecContext) -> None:
    """Install a release binary into ~/.local/bin (userspace, no sudo).

    Raw single-file assets are written straight into the bin dir. Archives are
    unpacked into ~/.local/opt/<binary>/ (stripping `strip` leading path
    components) and the binary is symlinked into the bin dir — the PRD's
    opt+symlink location policy, which also handles binaries nested under a
    versioned directory inside the archive.
    """
    if method.kind == "github_release":
        url = _github_release_url(method, ctx)
    elif method.kind == "tarball":
        url = require_str(method, "url")
    else:
        raise ExecutorError(f"no download executor for kind '{method.kind}'")

    member = require_str(method, "member")
    binname = PurePosixPath(member).name
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    quoted_url = shlex.quote(url)

    if method.params.get("raw") is True:
        quoted_link = shlex.quote(str(link))
        ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_link} -- {quoted_url}"])
        ctx.runner(["chmod", "+x", str(link)])
        return

    strip = _opt_int(method, "strip", 0)
    try:
        opt = ensure_dir(opt_dir(binname))
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
    binary = opt / member
    quoted_opt = shlex.quote(str(opt))
    extract = (
        "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
        f' && curl -fsSL -o "$tmp" -- {quoted_url}'
        f' && tar -xzf "$tmp" -C {quoted_opt} --strip-components={strip}'
    )
    ctx.runner(["sh", "-c", extract])
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
