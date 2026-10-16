"""Download-based executors: github_release and tarball binaries into a bin dir."""

import os
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

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
from installer.executors import (
    ExecutorError,
    method_smoke_argv,
    require_str,
    smoke_binary,
    staged_member,
)
from installer.locations import applications_dir, bin_dir, ensure_dir, opt_dir
from installer.model import Method
from installer.platform import Platform
from installer.run import Runner
from installer.versions import ReleaseResolver

DOWNLOAD_KINDS = ("github_release", "tarball")

UNPINNED_REASON = "unpinned url; no sha256 to verify against"


@dataclass(frozen=True)
class UpdateExecResult:
    """Result of an update-safe download replacement.

    `verified` matches `install_download`'s return: True when a checksum file or
    API digest was checked in staging. `warnings` carries non-fatal cleanup failures (a leftover
    `.old` tree that did not fail the update) so the caller has a channel.
    """

    verified: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecContext:
    runner: Runner
    platform: Platform
    resolve_release: ReleaseResolver


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
    sha256: str | None = None
    unverified_reason: str | None = None

    @property
    def verified(self) -> bool:
        return self.checksum is not None or self.sha256 is not None


def resolve_target(method: Method, ctx: ExecContext) -> DownloadTarget:
    """Resolve the download URL, member path, and optional checksum source.

    github_release templates asset/member/checksum with the resolved tag's
    bare version and the platform arch tokens; `{asset}` in the checksum
    template expands to the already-rendered asset name. tarball renders `{ver}`
    from `version` and verifies a pinned `sha256`; only github_release supports
    a checksum file.
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
        release = ctx.resolve_release(repo)
        tag = release.tag
        ver = tag.removeprefix("v")  # asset/member use the bare number; the path uses the tag
        try:
            asset = render_asset(template, ver, tokens)
            member = render_asset(raw_member, ver, tokens)
        except ValueError as exc:
            raise ExecutorError(f"cannot build asset name for '{repo}': {exc}") from exc
        base = f"https://github.com/{repo}/releases/download/{tag}"
        sha256: str | None = None
        unverified_reason: str | None = None
        if checksum_template is None:
            sha256 = release.digests.get(asset)
            if sha256 is None:
                unverified_reason = f"no checksum file and no GitHub sha256 digest for {asset}"
            return DownloadTarget(
                url=f"{base}/{asset}",
                member=member,
                asset=asset,
                sha256=sha256,
                unverified_reason=unverified_reason,
            )
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
        url = pinned_url(method)
        sha256_pin = _opt_str(method, "sha256")
        asset = PurePosixPath(url).name
        return DownloadTarget(
            url=url,
            member=raw_member,
            asset=asset,
            sha256=sha256_pin,
            unverified_reason=None if sha256_pin else UNPINNED_REASON,
        )
    raise ExecutorError(f"no download executor for kind '{method.kind}'")


def pinned_url(method: Method) -> str:
    """Render a tarball download URL, substituting `{ver}` from `version` when present."""
    url = require_str(method, "url")
    if "{ver}" not in url:
        return url
    version = method.params.get("version")
    if not isinstance(version, str) or not version:
        raise ExecutorError("pinned tarball url contains {ver} but version is missing or empty")
    return url.replace("{ver}", version)


def link_name(method: Method, member: str) -> str:
    """The bin link name a download method creates: `bin_name` when set, else
    the basename of `member`. The one rule for install, update and uninstall,
    so the uninstaller looks for the link under the name install gave it.
    One input asymmetry to know about (17-REVIEW IN-05): install and update
    pass the RENDERED member (`target.member`, after render_asset), while
    uninstall passes the raw registry `member` template — the basenames are
    identical for every current registry entry, which is what makes the
    shared rule hold."""
    return _opt_str(method, "bin_name") or PurePosixPath(member).name


def cli_spec(method: Method) -> tuple[str, str] | None:
    """(bundle-relative CLI path, symlink name) for the optional `cli` param.

    Single source of truth for the symlink name: install_app creates it and
    uninstall planning derives the same name (or skips when this raises).
    The link name is the validated `cli_name` param when declared, otherwise
    the basename of `cli`. This function is the only reader of `cli_name`.
    Lives in download.py because apps imports download, so download could not
    import it from apps (Ledger L-19-04).
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


def _is_single_name(name: str) -> bool:
    """True only for a name that is exactly one path component.

    Applied to the FINAL name `link_name` returns, so an explicit `bin_name`
    is checked too, not only a member basename (review M2). `../x`, `a/b` and
    `/abs/x` all fail; this code deletes files, so a traversal or absolute
    name must never become an opt dir or a bin path.
    """
    return name not in ("", ".", "..") and PurePosixPath(name).name == name


@dataclass(frozen=True)
class Artifact:
    """One path a method creates, with its shape: evidence only, never the
    removal authority (D-10) — a path being listed here does not make it
    ours to delete; proof (receipt, adoption or layout) does that."""

    path: Path
    kind: Literal["dir", "link", "file"]


def artifact_paths(method: Method, default_bin_dir: Path) -> tuple[Artifact, ...]:
    """The one formula for what a method creates (D-07): install placement,
    the receipt writer and the uninstaller's evidence all read this, so they
    can never disagree about where a method's files live.

    A download kind maps to (`opt_dir(name)`, dir) and (`<bin>/name`, link)
    when it unpacks an archive, or one (`<bin>/name`, file) when it is raw;
    an app kind maps to the userspace bundle and, when `cli` is declared, the
    cli link; every other kind creates nothing this formula describes.
    `<bin>` is the method's declared `bin_dir` when set, else
    `default_bin_dir`. `bin_name` and `cli_name` are honored. A missing
    member, an unsafe final name (review M2) or an invalid app name yields no
    artifact; an invalid `cli_name` yields the bundle only (the installer
    would have refused to link).
    """
    if method.kind in DOWNLOAD_KINDS:
        member = _opt_str(method, "member")
        if member is None:
            return ()
        name = link_name(method, member)
        if not _is_single_name(name):
            return ()
        declared = _opt_str(method, "bin_dir")
        bin_base = Path(declared).expanduser() if declared else default_bin_dir
        if method.params.get("raw") is True:
            return (Artifact(bin_base / name, "file"),)
        return (Artifact(opt_dir(name), "dir"), Artifact(bin_base / name, "link"))
    if method.kind == "app":
        app = method.params.get("app")
        if (
            not isinstance(app, str)
            or not app
            or PurePosixPath(app).name != app
            or app in (".", "..")
        ):
            return ()
        bundle = Artifact(applications_dir() / app, "dir")
        try:
            spec = cli_spec(method)
        except ExecutorError:
            return (bundle,)
        if spec is None:
            return (bundle,)
        return (bundle, Artifact(default_bin_dir / spec[1], "link"))
    return ()


def is_still_proven(path: Path, root: Path | None = None) -> bool:
    """The per-link form of `plan_removal`'s proof, re-checkable at deletion time.

    A bin link is proven when it is a symlink whose target is a regular file
    inside this tool's own opt_dir(<link name>) — the same archive-layout
    proof `plan_removal` makes, evaluated NOW rather than at preview time.
    When `root` is given, containment is checked against that directory instead
    (for app bundles). Resolution is strict: a dangling or looping link raises
    (OSError/RuntimeError on 3.11+) and is unproven — never a crash (CR-01)."""
    if not path.is_symlink():
        return False
    try:
        resolved = path.resolve(strict=True)
        containment = (root if root is not None else opt_dir(path.name)).resolve(strict=True)
    except (OSError, RuntimeError):  # dangling or looping: never proof
        return False
    return resolved.is_file() and resolved.is_relative_to(containment)


def install_download(method: Method, ctx: ExecContext) -> str | None:
    """Install a release binary into ~/.local/bin (userspace, no sudo).

    Returns None when the download was sha256-verified (pinned checksum file or
    GitHub API digest). Otherwise returns the unverified reason after installing.
    Raw single-file assets go straight into the bin dir; archives unpack into
    ~/.local/opt/<binary>/ with the binary symlinked into the bin dir (the PRD's
    opt+symlink location policy).

    The symlink is named after `member`'s basename unless `bin_name` is set --
    needed when the archive's own binary name doesn't match `tool.cmd` (e.g.
    Sublime Text's Linux tarball ships only `sublime_text`, with no `subl`
    alongside it the way its macOS bundle provides one).
    """
    target = resolve_target(method, ctx)
    binname = link_name(method, target.member)
    if not _is_single_name(binname):
        raise ExecutorError(f"unsafe bin name '{binname}': must be a single file name")
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    if method.params.get("raw") is not True:
        opt = opt_dir(binname)
        if (opt.exists() or opt.is_symlink()) and not is_still_proven(link):
            raise ExecutorError(
                f"{opt} already exists but {link} is not proven to be from this "
                "installer; move it aside or remove it, then retry"
            )
    workdir = Path(tempfile.mkdtemp(prefix="tools-installer-"))
    try:
        asset_path = _fetch_verified(method, ctx, target, workdir)
        if method.params.get("raw") is True:
            _replace_raw(link, asset_path, smoke_argv=method_smoke_argv(method))
        else:
            _replace_archive(
                method,
                ctx,
                target,
                link,
                asset_path,
                verified=target.verified,
                smoke_argv=method_smoke_argv(method),
            )
        if target.verified:
            return None
        return target.unverified_reason
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
    target = resolve_target(method, ctx)
    binname = link_name(method, target.member)
    if not _is_single_name(binname):
        raise ExecutorError(f"unsafe bin name '{binname}': must be a single file name")
    try:
        dest = ensure_dir(bin_dir(_opt_str(method, "bin_dir")))
    except OSError as exc:
        raise ExecutorError(f"cannot create bin dir: {exc}") from exc
    link = dest / binname
    staging = Path(tempfile.mkdtemp(prefix="tools-installer-update-"))
    try:
        asset_path = _fetch_verified(method, ctx, target, staging)
        if method.params.get("raw") is True:
            _replace_raw(link, asset_path)
            return UpdateExecResult(verified=target.verified)
        return _replace_archive(method, ctx, target, link, asset_path, verified=target.verified)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _fetch_verified(
    method: Method, ctx: ExecContext, target: DownloadTarget, staging: Path
) -> Path:
    """Fetch the asset with plain curl argv and verify against checksum file or API digest."""
    asset_path = staging / target.asset
    ctx.runner(["curl", "-fsSL", "-o", str(asset_path), "--", target.url])
    expected: str | None = None
    if target.checksum is not None:
        checksum_url, checksum_name = target.checksum
        sum_path = staging / checksum_name
        ctx.runner(["curl", "-fsSL", "-o", str(sum_path), "--", checksum_url])
        try:
            text = sum_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ExecutorError(f"cannot read checksum file '{checksum_name}': {exc}") from exc
        expected = expected_sha256(text, target.asset)
        if expected is None:
            raise ExecutorError(f"no sha256 entry for '{target.asset}' in '{checksum_name}'")
    elif target.sha256 is not None:
        expected = target.sha256
    if expected is not None:
        try:
            actual = sha256_file(asset_path)
        except OSError as extra:
            raise ExecutorError(
                f"cannot hash downloaded asset '{target.asset}': {extra}"
            ) from extra
        if actual != expected:
            raise ChecksumMismatch(target.asset, expected, actual)
    return asset_path


def _replace_raw(link: Path, asset_path: Path, *, smoke_argv: Sequence[str] | None = None) -> None:
    new = staged_sibling(link, NEW_SUFFIX)
    try:
        shutil.copy2(asset_path, new)
        new.chmod(0o755)
        if smoke_argv is not None:
            smoke_binary(new, smoke_argv)
        os.replace(new, link)
    except Exception:
        new.unlink(missing_ok=True)
        raise


def _replace_archive(
    method: Method,
    ctx: ExecContext,
    target: DownloadTarget,
    link: Path,
    asset_path: Path,
    *,
    verified: bool,
    smoke_argv: Sequence[str] | None = None,
) -> UpdateExecResult:
    opt = opt_dir(link.name)
    new = staged_sibling(opt, NEW_SUFFIX)
    old = staged_sibling(opt, OLD_SUFFIX)
    original_target = capture_symlink_target(link)
    recover_update_remnants(opt)
    try:
        _extract_into(method, ctx, target, asset_path, new)
        binary = staged_member(new, target.member)
        try:
            binary.chmod(0o755)
        except OSError as extra:
            raise ExecutorError(f"staged binary is not executable: {extra}") from extra
        if smoke_argv is not None:
            smoke_binary(binary, smoke_argv)
    except Exception:
        shutil.rmtree(new, ignore_errors=True)
        raise
    try:
        if opt.exists():
            os.replace(opt, old)
    except OSError as extra:
        shutil.rmtree(new, ignore_errors=True)
        raise ExecutorError(f"aside-move failed; prior installation intact: {extra}") from extra
    try:
        os.replace(new, opt)
    except OSError as extra:
        try:
            if old.exists():
                os.replace(old, opt)
        except OSError as rollback_extra:
            raise ExecutorError(
                f"swap failed ({extra}); rollback failed ({rollback_extra}); "
                f"prior installation is at {old}"
            ) from extra
        raise ExecutorError(f"swap failed; prior installation restored: {extra}") from extra
    live_binary = opt / target.member
    try:
        replace_symlink(link, str(live_binary))
        if not live_binary.is_file() or not os.access(live_binary, os.X_OK):
            raise ExecutorError(f"updated binary at {live_binary} is missing or not executable")
    except (OSError, ExecutorError) as extra:
        try:
            _undo_archive_swap(opt, new, old, link, original_target)
        except OSError as rollback_extra:
            raise ExecutorError(
                f"update failed after swap ({extra}); rollback failed "
                f"({rollback_extra}); prior installation is at {old}"
            ) from extra
        raise ExecutorError(
            f"update failed after swap; prior installation restored: {extra}"
        ) from extra
    warnings: list[str] = []
    if old.exists():
        try:
            shutil.rmtree(old)
        except OSError as extra:
            warnings.append(str(extra))
    return UpdateExecResult(verified=verified, warnings=tuple(warnings))


def _extract_into(
    method: Method, ctx: ExecContext, target: DownloadTarget, asset_path: Path, dest: Path
) -> None:
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExecutorError(f"cannot create opt dir: {exc}") from exc
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
    elif link.is_symlink():
        link.unlink()
    shutil.rmtree(new, ignore_errors=True)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
