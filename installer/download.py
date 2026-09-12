"""Download-based executors: github_release and tarball binaries into a bin dir."""

import os
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from installer.assets import arch_tokens, render_asset
from installer.atomic import (
    NEW_SUFFIX,
    OLD_SUFFIX,
    capture_symlink_target,
    recover_update_remnants,
    replace_symlink,
    staged_sibling,
)
from installer.checksums import ChecksumMismatch, expected_sha256, sha256_file
from installer.executors import ExecutorError, require_str
from installer.locations import bin_dir, ensure_dir, opt_dir
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner
from installer.versions import TagResolver

DOWNLOAD_KINDS = ("github_release", "tarball")


@dataclass(frozen=True)
class UpdateExecResult:
    """Result of an update-safe download replacement.

    `verified` matches `install_download`'s return: True when a checksum was
    checked in staging. `warnings` carries non-fatal cleanup failures (a leftover
    `.old` tree that did not fail the update) so the caller has a channel.
    """

    verified: bool
    warnings: tuple[str, ...] = ()


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


def _tar_flag(method: Method) -> str:
    """tar's decompression flag for this method's `archive` param.

    Registry-driven, not sniffed from the URL: `archive = "zip"` routes to
    unzip entirely (never reaches this), so this only distinguishes gzip
    (the long-standing default, still unset in every existing registry entry)
    from xz -- needed for vendors that only ship `.tar.xz` (e.g. Sublime
    Text's official Linux build; there's no `.tar.gz` alternative upstream).
    """
    return "J" if _opt_str(method, "archive") == "xz" else "z"


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

    The symlink is named after `member`'s basename unless `bin_name` is set --
    needed when the archive's own binary name doesn't match `tool.cmd` (e.g.
    Sublime Text's Linux tarball ships only `sublime_text`, with no `subl`
    alongside it the way its macOS bundle provides one).
    """
    target = _resolve_target(method, ctx)
    binname = _opt_str(method, "bin_name") or PurePosixPath(target.member).name
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
            f' && tar -x{_tar_flag(method)}f "$tmp" -C {quoted_opt}'
            f" --strip-components={strip}"
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


def update_download(method: Method, ctx: ExecContext) -> UpdateExecResult:
    """Stage a new copy, validate it, then atomically replace the live install.

    Fetch always lands in a fresh staging directory. A checksum mismatch
    raises before anything live is touched. Raw files replace via
    `os.replace` of a sibling `.new`. Archives run one rollback state
    machine: capture the original symlink target, recover remnants, extract
    into `.new`, aside-move the live tree, swap, recreate the symlink via
    `os.symlink`+`os.replace`, validate, then remove `.old`. A failure at
    any of those steps restores the prior tree AND the captured symlink.
    """
    target = _resolve_target(method, ctx)
    binname = _opt_str(method, "bin_name") or PurePosixPath(target.member).name
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    staging = Path(tempfile.mkdtemp(prefix="tools-installer-update-"))
    try:
        asset_path = _fetch_update_asset(method, ctx, target, staging)
        if method.params.get("raw") is True:
            _replace_raw(link, asset_path)
            return UpdateExecResult(verified=target.checksum is not None)
        return _replace_archive(method, ctx, target, link, asset_path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _fetch_update_asset(
    method: Method, ctx: ExecContext, target: DownloadTarget, staging: Path
) -> Path:
    asset_path = staging / target.asset
    ctx.runner(["curl", "-fsSL", "-o", str(asset_path), "--", target.url])
    if target.checksum is None:
        return asset_path
    checksum_url, checksum_name = target.checksum
    sum_path = staging / checksum_name
    ctx.runner(["curl", "-fsSL", "-o", str(sum_path), "--", checksum_url])
    try:
        text = sum_path.read_text()
    except OSError as exc:
        raise ExecutorError(f"cannot read checksum file '{checksum_name}': {exc}") from exc
    expected = expected_sha256(text, target.asset)
    if expected is None:
        raise ExecutorError(f"no sha256 entry for '{target.asset}' in '{checksum_name}'")
    try:
        actual = sha256_file(asset_path)
    except OSError as extra:
        raise ExecutorError(f"cannot hash downloaded asset '{target.asset}': {extra}") from extra
    if actual != expected:
        raise ChecksumMismatch(target.asset, expected, actual)
    return asset_path


def _replace_raw(link: Path, asset_path: Path) -> None:
    new = staged_sibling(link, NEW_SUFFIX)
    shutil.copy2(asset_path, new)
    new.chmod(0o755)
    os.replace(new, link)


def _replace_archive(
    method: Method,
    ctx: ExecContext,
    target: DownloadTarget,
    link: Path,
    asset_path: Path,
) -> UpdateExecResult:
    opt = opt_dir(link.name)
    new = staged_sibling(opt, NEW_SUFFIX)
    old = staged_sibling(opt, OLD_SUFFIX)
    original_target = capture_symlink_target(link)
    recover_update_remnants(opt)
    _extract_into(method, ctx, target, asset_path, new)
    binary = new / target.member
    try:
        binary.chmod(0o755)
    except OSError as extra:
        shutil.rmtree(new, ignore_errors=True)
        raise ExecutorError(f"staged binary is not executable: {extra}") from extra
    try:
        if opt.exists():
            os.replace(opt, old)
    except OSError as extra:
        shutil.rmtree(new, ignore_errors=True)
        raise ExecutorError(f"aside-move failed; prior installation intact: {extra}") from extra
    try:
        os.replace(new, opt)
    except OSError as extra:
        if old.exists():
            os.replace(old, opt)
        raise ExecutorError(f"swap failed; prior installation restored: {extra}") from extra
    live_binary = opt / target.member
    try:
        replace_symlink(link, str(live_binary))
        if not live_binary.exists() or not os.access(live_binary, os.X_OK):
            raise ExecutorError(f"updated binary at {live_binary} is missing or not executable")
    except (OSError, ExecutorError) as extra:
        _undo_archive_swap(opt, new, old, link, original_target)
        raise ExecutorError(
            f"update failed after swap; prior installation restored: {extra}"
        ) from extra
    warnings: list[str] = []
    if old.exists():
        try:
            shutil.rmtree(old)
        except OSError as extra:
            warnings.append(str(extra))
    return UpdateExecResult(verified=target.checksum is not None, warnings=tuple(warnings))


def _extract_into(
    method: Method, ctx: ExecContext, target: DownloadTarget, asset_path: Path, dest: Path
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if _opt_str(method, "archive") == "zip":
        ctx.runner(["unzip", "-q", "-o", str(asset_path), target.member, "-d", str(dest)])
        return
    strip = _opt_int(method, "strip", 0)
    ctx.runner(
        [
            "tar",
            f"-x{_tar_flag(method)}f",
            str(asset_path),
            "-C",
            str(dest),
            f"--strip-components={strip}",
        ]
    )


def _undo_archive_swap(
    opt: Path, new: Path, old: Path, link: Path, original_target: str | None
) -> None:
    if opt.exists():
        os.replace(opt, new)
    if old.exists():
        os.replace(old, opt)
    if original_target is not None:
        replace_symlink(link, original_target)
    shutil.rmtree(new, ignore_errors=True)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)


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
        ctx.runner(
            [
                "tar",
                f"-x{_tar_flag(method)}f",
                str(asset_path),
                "-C",
                str(opt),
                f"--strip-components={strip}",
            ]
        )
    ctx.runner(["chmod", "+x", str(binary)])
    ctx.runner(["ln", "-sf", str(binary), str(link)])
