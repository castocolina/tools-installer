"""GUARD-02 and GUARD-03: the launch remover deletes what an earlier version wrote, nothing else."""

import contextlib
import errno
import os
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from installer import legacy_guard
from installer.atomic import FileSnapshot
from installer.legacy_guard import (
    BAN_BEGIN,
    BAN_END,
    GUARD_NAMES,
    REDIRECT_SENTINEL,
    SHIM_SENTINEL,
    is_our_shim,
    look_through_shim,
    real_binary,
    real_pnpm,
    remove_ban_blocks,
    remove_guard_shims,
    which_in_path,
)
from installer.model import Method, Tool
from installer.status import is_installed

_BLOCK = f"{BAN_BEGIN}\nalias pip='echo banned'\n{BAN_END}\n"
_BAN_SHIM = f"#!/bin/sh\n{SHIM_SENTINEL}\nexit 127\n"
_REDIRECT_SHIM = f'#!/bin/sh\n{REDIRECT_SENTINEL}\nexec /x/pnpm dlx "$@"\n'
_ROOT_SKIP = pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file")
_DENIED = PermissionError(13, "Permission denied")


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME is tmp_path so display paths read `~/...`."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def bin_dir(home: Path) -> Path:
    path = home / ".local" / "bin"
    path.mkdir(parents=True)
    return path


def _block_removed(name: str) -> tuple[str, str]:
    return (f"Removed the retired guard alias block from ~/{name}.", "ok")


def _shim_removed(name: str) -> tuple[str, str]:
    return (f"Removed the retired pip/npm guard shim ~/.local/bin/{name}.", "ok")


def _rc_not_checked(name: str, reason: str) -> tuple[str, str]:
    return (
        f"Could not check ~/{name} for the retired guard alias block: {reason}; "
        "fix its permissions, then relaunch.",
        "warn",
    )


def _shim_not_checked(name: str, reason: str) -> tuple[str, str]:
    return (
        f"Could not check ~/.local/bin/{name} for the retired pip/npm guard shim: {reason}; "
        "fix its permissions, then relaunch.",
        "warn",
    )


def _rc(home: Path, text: str | bytes, name: str = ".myshellrc") -> Path:
    path = home / name
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    return path


# -- remove_ban_blocks -------------------------------------------------------------------


def test_every_well_formed_block_goes_in_one_pass(home: Path) -> None:
    rc = _rc(home, f"user1\n{_BLOCK}user2\n{_BLOCK}user3\n")

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_text() == "user1\nuser2\nuser3\n"
    assert remove_ban_blocks([rc]) == ()
    assert rc.read_text() == "user1\nuser2\nuser3\n"


def test_crlf_and_user_aliases_outside_the_markers_stay(home: Path) -> None:
    before = b"alias npx='mine'\r\nalias npm='mine'\r\nexport A=1\r\n"
    after = b"alias pip='mine'\r\n"
    rc = _rc(home, before + _BLOCK.encode() + after)

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_bytes() == before + after


def test_an_orphan_begin_alone_leaves_the_file_byte_identical(home: Path) -> None:
    text = f"user1\n{BAN_BEGIN}\nuser2\n"
    rc = _rc(home, text)

    assert remove_ban_blocks([rc]) == ()
    assert rc.read_text() == text


def test_an_orphan_begin_before_a_block_keeps_only_the_orphan_line(home: Path) -> None:
    rc = _rc(home, f"user1\n{BAN_BEGIN}\nuser2\n{_BLOCK}user3\n")

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_text() == f"user1\n{BAN_BEGIN}\nuser2\nuser3\n"


def test_a_block_followed_by_an_orphan_begin_goes_and_the_orphan_stays(home: Path) -> None:
    rc = _rc(home, f"user1\n{_BLOCK}user2\n{BAN_BEGIN}\nuser3\n")

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_text() == f"user1\nuser2\n{BAN_BEGIN}\nuser3\n"


def test_a_crlf_block_goes_with_its_line_endings(home: Path) -> None:
    block = f"{BAN_BEGIN}\r\nalias pip='echo banned'\r\n{BAN_END}\r\n"
    rc = _rc(home, f"user1\r\n{block}user2\r\n".encode())

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_bytes() == b"user1\r\nuser2\r\n"


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_a_block_ending_the_file_without_a_newline_keeps_the_line_before_it_whole(
    home: Path, eol: str
) -> None:
    rc = _rc(home, f"user-line{eol}{BAN_BEGIN}{eol}alias pip='x'{eol}{BAN_END}".encode())

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_bytes() == f"user-line{eol}".encode()


def test_an_orphan_end_alone_stays(home: Path) -> None:
    text = f"user1\n{BAN_END}\nuser2\n"
    rc = _rc(home, text)

    assert remove_ban_blocks([rc]) == ()
    assert rc.read_text() == text


def test_neighbouring_marker_blocks_stay_byte_identical(home: Path) -> None:
    around = (
        "# >>> tools-installer path >>>\nexport PATH=/x:$PATH\n# <<< tools-installer path <<<\n"
        "# >>> tools-installer tweak:docker >>>\nexport D=1\n"
        "# <<< tools-installer tweak:docker <<<\n"
        "# tools-installer shell-init: starship\n"
        "# >>> tools-installer source >>>\nsource ~/.myshellrc\n# <<< tools-installer source <<<\n"
    )
    rc = _rc(home, f"{around}{_BLOCK}")

    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_text() == around


def _oversize() -> bytes:
    block = _BLOCK.encode()
    return block + b"#" * ((1 << 20) + 1 - len(block))


@pytest.mark.parametrize(
    "content",
    [b"\xff\n" + _BLOCK.encode(), _oversize(), None, b""],
    ids=["non-utf8", "over-1-MiB", "missing", "empty"],
)
def test_skips_rc_files_it_cannot_read_safely(home: Path, content: bytes | None) -> None:
    rc = home / ".myshellrc"
    if content is not None:
        rc.write_bytes(content)

    assert remove_ban_blocks([rc]) == ()
    if content is None:
        assert not rc.exists()
    else:
        assert rc.read_bytes() == content


@_ROOT_SKIP
def test_an_unreadable_rc_file_is_one_warn_line(home: Path) -> None:
    locked = _rc(home, f"user\n{_BLOCK}", ".myshellrc")
    other = _rc(home, f"user\n{_BLOCK}", ".bashrc")
    locked.chmod(0)
    try:
        result = remove_ban_blocks([locked, other])
    finally:
        locked.chmod(0o644)

    assert result == (_rc_not_checked(".myshellrc", "Permission denied"), _block_removed(".bashrc"))
    assert locked.read_text() == f"user\n{_BLOCK}"
    assert other.read_text() == "user\n"


def test_an_rc_edited_between_read_and_write_is_skipped(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review H1: a concurrent edit between the read and the write is never overwritten."""
    rc = _rc(home, f"user\n{_BLOCK}")
    original = legacy_guard.read_capped
    calls: list[Path] = []

    def late_edit(path: Path, cap: int, *, follow_symlinks: bool) -> bytes | None:
        calls.append(path)
        if len(calls) == 2:
            path.write_bytes(path.read_bytes() + b"export LATE=1\n")
        return original(path, cap, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(legacy_guard, "read_capped", late_edit)
    assert remove_ban_blocks([rc]) == ()
    assert rc.read_text() == f"user\n{_BLOCK}export LATE=1\n"

    monkeypatch.setattr(legacy_guard, "read_capped", original)
    assert remove_ban_blocks([rc]) == (_block_removed(".myshellrc"),)
    assert rc.read_text() == "user\nexport LATE=1\n"


def test_a_failed_rc_write_is_one_warn_line(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _rc(home, f"user\n{_BLOCK}", ".myshellrc")
    second = _rc(home, f"user\n{_BLOCK}", ".bashrc")
    original = legacy_guard.atomic_write_text

    def flaky(path: Path, text: str, *, mode: int | None = None) -> None:
        if path == first:
            raise _DENIED
        original(path, text, mode=mode)

    monkeypatch.setattr(legacy_guard, "atomic_write_text", flaky)

    assert remove_ban_blocks([first, second]) == (
        (
            "Could not remove the retired guard alias block from ~/.myshellrc: Permission denied; "
            "fix its permissions, then relaunch.",
            "warn",
        ),
        _block_removed(".bashrc"),
    )
    assert first.read_text() == f"user\n{_BLOCK}"
    assert second.read_text() == "user\n"


def test_a_symlinked_rc_is_edited_through_its_link(home: Path) -> None:
    target = home / "dotfiles" / "myshellrc"
    target.parent.mkdir()
    target.write_text(f"user\n{_BLOCK}")
    link = home / ".myshellrc"
    link.symlink_to(target)

    assert remove_ban_blocks([link]) == (_block_removed(".myshellrc"),)
    assert link.is_symlink()
    assert target.read_text() == "user\n"


def test_a_permission_failure_at_the_rc_recheck_is_silent_and_the_next_call_warns(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = _rc(home, f"user\n{_BLOCK}")
    original = legacy_guard.read_capped
    calls: list[Path] = []

    def denied_after_the_first(path: Path, cap: int, *, follow_symlinks: bool) -> bytes | None:
        calls.append(path)
        if len(calls) > 1:
            raise _DENIED
        return original(path, cap, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(legacy_guard, "read_capped", denied_after_the_first)

    assert remove_ban_blocks([rc]) == ()
    assert rc.read_text() == f"user\n{_BLOCK}"
    assert remove_ban_blocks([rc]) == (_rc_not_checked(".myshellrc", "Permission denied"),)


# -- remove_guard_shims --------------------------------------------------------------------


def test_each_marked_shim_goes_and_is_named(bin_dir: Path) -> None:
    bodies = {
        "npm": _REDIRECT_SHIM,
        "npx": _REDIRECT_SHIM,
        "pnpm": f"#!/bin/sh\n# my edit\n{SHIM_SENTINEL}\necho hi\n",
        "pip": _BAN_SHIM,
        "pip3": _BAN_SHIM,
    }
    for name, body in bodies.items():
        (bin_dir / name).write_text(body)

    assert remove_guard_shims(bin_dir) == tuple(_shim_removed(name) for name in GUARD_NAMES)
    assert list(bin_dir.iterdir()) == []


def _plant_symlink(path: Path) -> None:
    target = path.parent.parent / "elsewhere" / "npx-real"
    target.parent.mkdir()
    target.write_text(_REDIRECT_SHIM)
    path.symlink_to(target)


def _plant_unmarked(path: Path) -> None:
    path.write_bytes(b"\x7fELF real pnpm binary\x00")


def _plant_oversize(path: Path) -> None:
    path.write_text(_BAN_SHIM + "#" * (8193 - len(_BAN_SHIM)))


def _plant_non_utf8(path: Path) -> None:
    path.write_bytes(b"\xff" + _BAN_SHIM.encode())


def _plant_mention(path: Path) -> None:
    path.write_text("#!/bin/sh\n# managed by tools-installer? no, mine\nexit 0\n")


_PLANTS: dict[str, Callable[[Path], None]] = {
    "symlink": _plant_symlink,
    "unmarked": _plant_unmarked,
    "oversize": _plant_oversize,
    "fifo": os.mkfifo,
    "non-utf8": _plant_non_utf8,
    "zero-byte": Path.touch,
    "directory": Path.mkdir,
    "mention": _plant_mention,
}


@pytest.mark.parametrize("kind", list(_PLANTS))
def test_leaves_what_it_did_not_write(bin_dir: Path, kind: str) -> None:
    path = bin_dir / "npx"
    _PLANTS[kind](path)
    before = os.lstat(path)

    assert remove_guard_shims(bin_dir) == ()
    after = os.lstat(path)
    assert (after.st_mode, after.st_ino, after.st_size) == (
        before.st_mode,
        before.st_ino,
        before.st_size,
    )


def test_a_marked_shim_of_exactly_8192_bytes_goes(bin_dir: Path) -> None:
    (bin_dir / "npm").write_text(_BAN_SHIM + "#" * (8192 - len(_BAN_SHIM)))
    assert (bin_dir / "npm").stat().st_size == 8192

    assert remove_guard_shims(bin_dir) == (_shim_removed("npm"),)
    assert not (bin_dir / "npm").exists()


def test_a_file_swapped_before_the_identity_recheck_is_not_deleted(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A swap before the re-check is caught. A swap after the re-check and before the unlink is
    the documented residual (see the `shortcut:` comment in legacy_guard) and is not tested."""
    npm = bin_dir / "npm"
    npm.write_text(_BAN_SHIM)
    original = legacy_guard.snapshot_matches

    def swap_first(path: Path, snapshot: FileSnapshot) -> bool:
        other = path.with_name("incoming")
        other.write_text("#!/bin/sh\necho a real npm\n")
        os.replace(other, path)
        return original(path, snapshot)

    monkeypatch.setattr(legacy_guard, "snapshot_matches", swap_first)

    assert remove_guard_shims(bin_dir) == ()
    assert npm.read_text() == "#!/bin/sh\necho a real npm\n"


def test_a_shim_another_launch_deleted_is_silent(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    npm = bin_dir / "npm"
    npm.write_text(_BAN_SHIM)

    def deleted_by_a_rival(_path: Path, _snapshot: FileSnapshot) -> bool:
        npm.unlink()
        return True

    monkeypatch.setattr(legacy_guard, "snapshot_matches", deleted_by_a_rival)

    assert remove_guard_shims(bin_dir) == ()
    assert not npm.exists()


@_ROOT_SKIP
def test_an_unreadable_marked_shim_is_one_warn_line(bin_dir: Path) -> None:
    for name in GUARD_NAMES:
        (bin_dir / name).write_text(_BAN_SHIM)
    (bin_dir / "npm").chmod(0)
    try:
        result = remove_guard_shims(bin_dir)
    finally:
        (bin_dir / "npm").chmod(0o755)

    assert result == (
        _shim_not_checked("npm", "Permission denied"),
        *(_shim_removed(name) for name in GUARD_NAMES[1:]),
    )
    assert (bin_dir / "npm").exists()


@_ROOT_SKIP
def test_a_permission_failure_at_the_shim_recheck_is_silent_and_the_next_call_warns(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    npm = bin_dir / "npm"
    npm.write_text(_BAN_SHIM)
    original = legacy_guard.snapshot_matches

    def lock_then_check(path: Path, snapshot: FileSnapshot) -> bool:
        path.chmod(0)
        return original(path, snapshot)

    monkeypatch.setattr(legacy_guard, "snapshot_matches", lock_then_check)
    try:
        assert remove_guard_shims(bin_dir) == ()
        assert npm.exists()
        assert remove_guard_shims(bin_dir) == (_shim_not_checked("npm", "Permission denied"),)
    finally:
        npm.chmod(0o755)


@pytest.mark.parametrize("kind", ["rc", "shim"])
def test_any_other_first_read_failure_is_one_warn_line(
    home: Path, bin_dir: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    if kind == "rc":
        rc = _rc(home, f"user\n{_BLOCK}")

        def eio(_path: Path, _cap: int, *, follow_symlinks: bool) -> bytes | None:
            del follow_symlinks
            raise OSError(errno.EIO, "Input/output error")

        monkeypatch.setattr(legacy_guard, "read_capped", eio)

        assert remove_ban_blocks([rc]) == (_rc_not_checked(".myshellrc", "Input/output error"),)
        assert rc.read_text() == f"user\n{_BLOCK}"
    else:
        (bin_dir / "npm").write_text(_BAN_SHIM)

        def emfile(_path: Path) -> FileSnapshot:
            raise OSError(errno.EMFILE, "Too many open files")

        monkeypatch.setattr(legacy_guard, "read_snapshot", emfile)

        assert remove_guard_shims(bin_dir) == (_shim_not_checked("npm", "Too many open files"),)
        assert (bin_dir / "npm").exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_a_read_only_bin_dir_gives_one_warn_line_per_shim(bin_dir: Path) -> None:
    for name in GUARD_NAMES:
        (bin_dir / name).write_text(_BAN_SHIM)
    bin_dir.chmod(0o555)
    try:
        result = remove_guard_shims(bin_dir)
    finally:
        bin_dir.chmod(0o755)

    assert result == tuple(
        (
            f"Could not remove the retired pip/npm guard shim ~/.local/bin/{name}: "
            "Permission denied; delete it yourself or make its directory writable, "
            "then relaunch.",
            "warn",
        )
        for name in GUARD_NAMES
    )
    assert all((bin_dir / name).exists() for name in GUARD_NAMES)


def test_a_missing_bin_dir_is_silent(home: Path) -> None:
    assert remove_guard_shims(home / "no" / "such" / "bin") == ()


def test_notice_paths_are_sanitized(home: Path) -> None:
    odd = home / ".local" / "bin\x1b[31m"
    odd.mkdir(parents=True)
    (odd / "npm").write_text(_BAN_SHIM)

    ((message, level),) = remove_guard_shims(odd)

    assert level == "ok"
    assert "\x1b" not in message


def test_a_shim_written_after_a_launch_goes_next_launch(bin_dir: Path) -> None:
    assert remove_guard_shims(bin_dir) == ()
    (bin_dir / "pip").write_text(_BAN_SHIM)

    assert remove_guard_shims(bin_dir) == (_shim_removed("pip"),)


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_an_unremovable_pnpm_wrapper_is_never_resolved_or_present(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD-05: a wrapper the launch could not delete is neither run nor counted."""
    wrapper = bin_dir / "pnpm"
    wrapper.write_text(_REDIRECT_SHIM)
    wrapper.chmod(0o755)
    bin_dir.chmod(0o555)
    try:
        ((message, level),) = remove_guard_shims(bin_dir)
        monkeypatch.setenv("PATH", str(bin_dir))
        pnpm = Tool(
            id="pnpm",
            name="pnpm",
            category="c",
            cmd="pnpm",
            methods=(Method(kind="brew", params={"formula": "pnpm"}),),
        )

        assert level == "warn"
        assert "pnpm" in message
        assert wrapper.exists()
        assert real_pnpm(shim_dir=bin_dir, path_value=str(bin_dir)) is None
        assert is_installed(pnpm, default_bin_dir=bin_dir) is False
    finally:
        bin_dir.chmod(0o755)


def test_a_real_pnpm_elsewhere_is_resolved_and_stable(bin_dir: Path, tmp_path: Path) -> None:
    (bin_dir / "pnpm").write_text(_REDIRECT_SHIM)
    (bin_dir / "pnpm").chmod(0o755)
    real = _executable(tmp_path / "real" / "pnpm", "#!/bin/sh\n")
    path_value = f"{bin_dir}{os.pathsep}{real.parent}"

    first = real_pnpm(shim_dir=bin_dir, path_value=path_value)
    second = real_pnpm(shim_dir=bin_dir, path_value=path_value)

    assert first == second == str(real)


def test_a_leftover_removed_mid_run_still_resolves_the_real_binary(
    bin_dir: Path, tmp_path: Path
) -> None:
    """Backstop: a concurrent launch may unlink the leftover between two lookups."""
    leftover = _executable(bin_dir / "pnpm", _REDIRECT_SHIM)
    real = _executable(tmp_path / "real" / "pnpm", "#!/bin/sh\n")
    path_value = f"{bin_dir}{os.pathsep}{real.parent}"

    def resolve() -> tuple[str | None, str | None]:
        found = which_in_path("pnpm", path_value)
        return (
            real_binary("pnpm", shim_dir=bin_dir, path_value=path_value),
            look_through_shim(found, "pnpm", shim_dir=bin_dir, path_value=path_value),
        )

    assert resolve() == (str(real), str(real))
    leftover.unlink()
    assert resolve() == (str(real), str(real))


def test_is_our_shim_detects_the_sentinel(tmp_path: Path):
    ours = tmp_path / "pip"
    ours.write_text(f"#!/bin/sh\n{SHIM_SENTINEL}\nexit 127\n")
    assert is_our_shim(ours) is True


def test_is_our_shim_false_for_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    assert is_our_shim(real) is False


def test_is_our_shim_false_when_unreadable(tmp_path: Path):
    # A directory named like a tool: read_text raises OSError -> treated as not ours.
    (tmp_path / "pip").mkdir()
    assert is_our_shim(tmp_path / "pip") is False


def test_is_our_shim_true_for_redirect_sentinel_only(tmp_path: Path):
    path = tmp_path / "npx"
    path.write_text(f"{REDIRECT_SENTINEL}\n")
    assert is_our_shim(path) is True


def test_is_our_shim_true_for_ban_sentinel_only(tmp_path: Path):
    path = tmp_path / "pip"
    path.write_text(f"{SHIM_SENTINEL}\n")
    assert is_our_shim(path) is True


def test_real_binary_skips_shim_dir(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    real_dir = tmp_path / "real"
    shim_dir.mkdir()
    real_dir.mkdir()

    def lookup(name: str, path: str) -> str | None:
        for directory in path.split(os.pathsep):
            candidate = Path(directory) / name
            if candidate.exists():
                return str(candidate)
        return None

    (shim_dir / "pnpm").write_text(f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    (real_dir / "pnpm").write_text("real\n")
    found = real_binary(
        "pnpm",
        shim_dir=shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{real_dir}",
        lookup=lookup,
    )
    assert found == str(real_dir / "pnpm")


def test_real_binary_finds_a_real_binary_living_in_the_shim_dir(tmp_path: Path):
    # The shim dir IS the managed bin dir: `npm i -g pnpm --prefix ~/.local` and
    # `corepack enable --install-directory ~/.local/bin` both land pnpm there,
    # and excluding the directory made it permanently unresolvable.
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    real = shim_dir / "pnpm"
    real.write_text("#!/bin/sh\necho real pnpm\n")
    real.chmod(0o755)
    found = real_binary(
        "pnpm",
        shim_dir=shim_dir,
        path_value=str(shim_dir),
        lookup=_lookup_existing,
    )
    assert found == str(real)


def _lookup_existing(name: str, path: str) -> str | None:
    for directory in path.split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists():
            return str(candidate)
    return None


def test_real_pnpm_skips_shim_dir(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    real_dir = tmp_path / "real"
    shim_dir.mkdir()
    real_dir.mkdir()
    (shim_dir / "pnpm").write_text(f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    (real_dir / "pnpm").write_text("real\n")
    found = real_pnpm(
        shim_dir=shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{real_dir}",
        lookup=_lookup_existing,
    )
    assert found == str(real_dir / "pnpm")


def test_real_pnpm_rejects_sentinel_match(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    other = tmp_path / "other"
    shim_dir.mkdir()
    other.mkdir()
    fake = other / "pnpm"

    def lookup(_name: str, _path: str) -> str | None:
        return str(fake)

    for sentinel in (SHIM_SENTINEL, REDIRECT_SENTINEL):
        fake.write_text(f"#!/bin/sh\n{sentinel}\n")
        assert real_pnpm(shim_dir=shim_dir, path_value=str(other), lookup=lookup) is None


def test_real_pnpm_none_when_nothing_resolves(tmp_path: Path):
    assert real_pnpm(shim_dir=tmp_path, path_value="", lookup=lambda _n, _p: None) is None


def test_real_pnpm_defaults_read_home_and_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    shim_dir = tmp_path / ".local" / "bin"
    real_dir = tmp_path / "real"
    shim_dir.mkdir(parents=True)
    real_dir.mkdir()
    wrapper = shim_dir / "pnpm"
    wrapper.write_text(f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    wrapper.chmod(0o755)
    real = real_dir / "pnpm"
    real.write_text("#!/bin/sh\n")
    real.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{real_dir}")
    assert real_pnpm() == str(real)


def test_real_binary_rejects_sentinel_match(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    other = tmp_path / "other"
    shim_dir.mkdir()
    other.mkdir()
    fake = other / "pnpm"
    fake.write_text(f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")

    def lookup(_name: str, _path: str) -> str | None:
        return str(fake)

    assert (
        real_binary(
            "pnpm",
            shim_dir=shim_dir,
            path_value=str(other),
            lookup=lookup,
        )
        is None
    )


def _executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


def test_look_through_shim_finds_the_real_binary(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    shim = _executable(shim_dir / "pnpm", f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    real = _executable(tmp_path / "real" / "pnpm", "#!/bin/sh\n")
    path_value = f"{shim_dir}{os.pathsep}{real.parent}"
    found = look_through_shim(str(shim), "pnpm", shim_dir=shim_dir, path_value=path_value)
    assert found == str(real)


def test_look_through_shim_matches_the_shim_dir_by_resolved_path(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    _executable(shim_dir / "pnpm", f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    real = _executable(tmp_path / "real" / "pnpm", "#!/bin/sh\n")
    alias = tmp_path / "alias"
    alias.symlink_to(shim_dir, target_is_directory=True)
    path_value = f"{alias}/{os.pathsep}{real.parent}"
    found = f"{alias}/pnpm"

    assert look_through_shim(found, "pnpm", shim_dir=shim_dir, path_value=path_value) == str(real)


def test_real_binary_drops_every_spelling_of_the_managed_dir(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    _executable(shim_dir / "pnpm", f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    real = _executable(tmp_path / "real" / "pnpm", "#!/bin/sh\n")
    alias = tmp_path / "alias"
    alias.symlink_to(shim_dir, target_is_directory=True)
    path_value = f"{alias}/{os.pathsep}{shim_dir}{os.pathsep}{real.parent}"

    assert real_binary("pnpm", shim_dir=shim_dir, path_value=path_value) == str(real)


def test_real_binary_survives_a_looping_path_entry(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    _executable(shim_dir / "pnpm", f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    real = _executable(tmp_path / "real" / "pnpm", "#!/bin/sh\n")
    loop = tmp_path / "loopbin"
    loop.symlink_to(loop)
    path_value = os.pathsep.join([str(shim_dir), str(real.parent), str(loop)])

    assert real_binary("pnpm", shim_dir=shim_dir, path_value=path_value) == str(real)


def test_look_through_shim_keeps_a_non_shim_hit(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    corepack = _executable(shim_dir / "pnpm", "#!/bin/sh\n")
    path_value = str(shim_dir)
    found = look_through_shim(str(corepack), "pnpm", shim_dir=shim_dir, path_value=path_value)
    assert found == str(corepack)


def test_look_through_shim_ignores_shims_outside_the_managed_dir(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    other = _executable(tmp_path / "other" / "pnpm", f"#!/bin/sh\n{REDIRECT_SENTINEL}\n")
    found = look_through_shim(str(other), "pnpm", shim_dir=shim_dir, path_value=str(other.parent))
    assert found == str(other)


def test_look_through_shim_none_stays_none(tmp_path: Path):
    assert look_through_shim(None, "pnpm", shim_dir=tmp_path, path_value=str(tmp_path)) is None


def test_is_our_shim_never_reads_a_large_file(tmp_path: Path):
    big = tmp_path / "big"
    big.write_text(f"#!/bin/sh\n{REDIRECT_SENTINEL}\n" + "#" * 9 * 1024)

    assert is_our_shim(big) is False


def test_is_our_shim_never_blocks_on_a_fifo(tmp_path: Path) -> None:
    """A FIFO planted at a guarded name must not stall the refresh worker."""
    fifo = tmp_path / "pnpm"
    os.mkfifo(fifo)
    box: list[bool] = []

    def run() -> None:
        box.append(is_our_shim(fifo))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert box == [False]
    finally:
        with contextlib.suppress(OSError):
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        thread.join(timeout=5)
