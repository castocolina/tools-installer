"""Download-based executors: github_release and tarball binaries into a bin dir."""

import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from installer.assets import arch_tokens, render_asset
from installer.checksums import ChecksumMismatch, expected_sha256, sha256_file
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


@dataclass(frozen=True)
class DownloadTarget:
    """A resolved download: where to fetch, what to extract, how to verify."""

    url: str
    member: str
    asset: str  # the download's filename; names the temp file in the verified flow
    checksum: tuple[str, str] | None = None  # (checksum url, checksum filename)


def _resolve_target(method: Method, ctx: ExecContext) -> DownloadTarget:
    """Resolve the download URL, member path, and optional checksum source.

    github_release templates asset/member/checksum with the resolved tag's
    bare version and the platform arch tokens; `{asset}` in the checksum
    template expands to the already-rendered asset name. tarball is verbatim
    and does not support checksums (no registry entry needs it).
    """
    try:
        tokens = arch_tokens(ctx.platform.arch)
    except ValueError as exc:
        raise ExecutorError(f"cannot build asset name: {exc}") from exc
    raw_member = require_str(method, "member")
    checksum_template = _opt_str(method, "checksum")
    if method.kind == "github_release":
        repo = require_str(method, "repo")
        template = require_str(method, "asset")
        tag = ctx.resolve_tag(repo)
        ver = tag.removeprefix("v")  # asset/member use the bare number; the path uses the tag
        try:
            asset = render_asset(template, ver, tokens)
            member = render_asset(raw_member, ver, tokens)
        except ValueError as exc:
            raise ExecutorError(f"cannot build asset name for '{repo}': {exc}") from exc
        base = f"https://github.com/{repo}/releases/download/{tag}"
        if checksum_template is None:
            return DownloadTarget(url=f"{base}/{asset}", member=member, asset=asset)
        try:
            checksum_name = render_asset(checksum_template.replace("{asset}", asset), ver, tokens)
        except ValueError as exc:
            raise ExecutorError(f"cannot build checksum name for '{repo}': {exc}") from exc
        return DownloadTarget(
            url=f"{base}/{asset}",
            member=member,
            asset=asset,
            checksum=(f"{base}/{checksum_name}", checksum_name),
        )
    if method.kind == "tarball":
        if checksum_template is not None:
            raise ExecutorError("checksum verification is only supported for github_release")
        url = require_str(method, "url")
        return DownloadTarget(url=url, member=raw_member, asset=PurePosixPath(url).name)
    raise ExecutorError(f"no download executor for kind '{method.kind}'")


def install_download(method: Method, ctx: ExecContext) -> bool:
    """Install a release binary into ~/.local/bin (userspace, no sudo).

    Returns True when the download was sha256-verified against a published
    checksum, False otherwise. Raw single-file assets go straight into the
    bin dir; archives unpack into ~/.local/opt/<binary>/ with the binary
    symlinked into the bin dir (the PRD's opt+symlink location policy).
    """
    target = _resolve_target(method, ctx)
    binname = PurePosixPath(target.member).name
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    if target.checksum is None:
        _install_unverified(method, ctx, target, link)
        return False
    _install_verified(method, ctx, target, link, target.checksum)
    return True


def _install_unverified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path
) -> None:
    """The pre-checksum flow: curl|extract via a shell-side mktemp. Argv unchanged."""
    quoted_url = shlex.quote(target.url)
    if method.params.get("raw") is True:
        quoted_link = shlex.quote(str(link))
        ctx.runner(["sh", "-c", f"curl -fsSL -o {quoted_link} -- {quoted_url}"])
        ctx.runner(["chmod", "+x", str(link)])
        return
    strip = _opt_int(method, "strip", 0)
    try:
        opt = ensure_dir(opt_dir(link.name))
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
    binary = opt / target.member
    quoted_opt = shlex.quote(str(opt))
    quoted_member = shlex.quote(target.member)
    if _opt_str(method, "archive") == "zip":
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && unzip -q -o "$tmp" {quoted_member} -d {quoted_opt}'
        )
    else:
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && tar -xzf "$tmp" -C {quoted_opt} --strip-components={strip}'
        )
    ctx.runner(["sh", "-c", extract])
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])


def _install_verified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path, checksum: tuple[str, str]
) -> None:
    """Fetch asset + checksum file into a temp dir, verify the digest, then install.

    A missing entry for the asset is registry/upstream drift — an ordinary
    ExecutorError that falls through to the next method. A present-but-wrong
    digest is the security signal — ChecksumMismatch, which stops the ladder.
    """
    checksum_url, checksum_name = checksum
    workdir = Path(tempfile.mkdtemp(prefix="tools-installer-"))
    try:
        asset_path = workdir / target.asset
        sum_path = workdir / checksum_name
        fetch = (
            f"curl -fsSL -o {shlex.quote(str(asset_path))} -- {shlex.quote(target.url)}"
            f" && curl -fsSL -o {shlex.quote(str(sum_path))} -- {shlex.quote(checksum_url)}"
        )
        ctx.runner(["sh", "-c", fetch])
        try:
            text = sum_path.read_text()
        except OSError as exc:
            raise ExecutorError(f"cannot read checksum file '{checksum_name}': {exc}") from exc
        expected = expected_sha256(text, target.asset)
        if expected is None:
            raise ExecutorError(f"no sha256 entry for '{target.asset}' in '{checksum_name}'")
        try:
            actual = sha256_file(asset_path)
        except OSError as exc:
            raise ExecutorError(f"cannot hash downloaded asset '{target.asset}': {exc}") from exc
        if actual != expected:
            raise ChecksumMismatch(target.asset, expected, actual)
        _place_verified(method, ctx, target, link, asset_path)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _place_verified(
    method: Method, ctx: ExecContext, target: DownloadTarget, link: Path, asset_path: Path
) -> None:
    """Install a verified download from its temp path (plain argv, no shell)."""
    if method.params.get("raw") is True:
        ctx.runner(["cp", str(asset_path), str(link)])
        ctx.runner(["chmod", "+x", str(link)])
        return
    try:
        opt = ensure_dir(opt_dir(link.name))
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
    binary = opt / target.member
    if _opt_str(method, "archive") == "zip":
        ctx.runner(["unzip", "-q", "-o", str(asset_path), target.member, "-d", str(opt)])
    else:
        strip = _opt_int(method, "strip", 0)
        ctx.runner(["tar", "-xzf", str(asset_path), "-C", str(opt), f"--strip-components={strip}"])
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
