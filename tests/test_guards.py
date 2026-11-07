import contextlib
import os
import shlex
import subprocess
import threading
from pathlib import Path

import pytest

from installer.guards import (
    BAN_BEGIN,
    BAN_END,
    BANNED,
    BOOLEAN_LONG_OPTIONS,
    BOOLEAN_SHORT_FLAGS,
    GLOBAL_REDIRECTED,
    GLOBAL_SUBCOMMANDS,
    REDIRECT_SENTINEL,
    REDIRECTED,
    SHIM_SENTINEL,
    ban_alias_block,
    ban_body,
    exec_targets,
    global_redirect_shim_script,
    guard_label,
    guard_path_warning,
    guard_redirect_warning,
    guard_status,
    guarded_names,
    install_global_redirect_shims,
    install_redirect_shims,
    install_shims,
    is_our_shim,
    look_through_shim,
    real_binary,
    real_pnpm,
    redirect_shim_script,
    remove_ban_aliases,
    remove_shims,
    rewrite_outdated_ban_aliases,
    rewrite_outdated_npx,
    shell_path,
    shim_script,
    write_ban_aliases,
)
from installer.locations import display_path


def test_shim_script_names_the_replacement_and_exits_nonzero():
    script = shim_script("pip")
    assert SHIM_SENTINEL in script
    assert "uv" in script  # the sanctioned replacement for pip
    assert "exit 127" in script


def test_shim_script_is_valid_posix_sh(tmp_path: Path):
    for name in BANNED:
        shim = tmp_path / name
        shim.write_text(shim_script(name))
        result = subprocess.run(["sh", "-n", str(shim)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_is_our_shim_detects_the_sentinel(tmp_path: Path):
    ours = tmp_path / "pip"
    ours.write_text(shim_script("pip"))
    assert is_our_shim(ours) is True


def test_is_our_shim_false_for_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    assert is_our_shim(real) is False


def test_is_our_shim_false_when_unreadable(tmp_path: Path):
    # A directory named like a tool: read_text raises OSError -> treated as not ours.
    (tmp_path / "pip").mkdir()
    assert is_our_shim(tmp_path / "pip") is False


def test_install_shims_creates_each_banned_shim(tmp_path: Path):
    actions = install_shims(tmp_path)
    assert actions == {name: "created" for name in BANNED}
    for name in BANNED:
        shim = tmp_path / name
        assert is_our_shim(shim)
        assert shim.stat().st_mode & 0o111  # executable


def test_install_shims_is_idempotent_and_reports_refreshed(tmp_path: Path):
    install_shims(tmp_path)
    actions = install_shims(tmp_path)
    assert actions == {name: "refreshed" for name in BANNED}


def test_install_shims_never_overwrites_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    actions = install_shims(tmp_path)
    assert actions["pip"] == "skipped (real binary here)"
    assert real.read_text() == "#!/bin/sh\necho real pip\n"  # untouched


def test_remove_shims_removes_only_ours(tmp_path: Path):
    install_shims(tmp_path)
    # replace our npm shim with a real one
    (tmp_path / "npm").write_text("#!/bin/sh\necho real npm\n")
    actions = remove_shims(tmp_path)
    assert actions["pip"] == "removed"
    assert actions["npm"] == "absent"  # not ours -> left alone
    assert (tmp_path / "npm").exists()
    assert not (tmp_path / "pip").exists()


def test_remove_shims_removes_npx_after_ban_and_redirect_install(tmp_path: Path):
    real_dir = tmp_path / "real"
    shim_dir = tmp_path / "shims"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)

    def lookup(name: str, _path: str) -> str | None:
        return str(pnpm) if name == "pnpm" else None

    install_shims(shim_dir)
    install_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{real_dir}",
        lookup=lookup,
    )
    actions = remove_shims(shim_dir)
    assert actions["npx"] == "removed"
    assert actions["npm"] == "removed"
    assert actions["pip"] == "removed"
    assert actions["pip3"] == "removed"
    assert not (shim_dir / "npx").exists()


def test_guard_status_reports_installed_ours(tmp_path: Path):
    install_shims(tmp_path)
    (tmp_path / "pip").unlink()
    status = guard_status(tmp_path)
    assert set(status) == set(guarded_names())
    assert all(isinstance(value, bool) for value in status.values())
    assert status["npm"] is True
    assert status["pip"] is False


def test_ban_alias_block_aliases_each_banned_command():
    block = ban_alias_block()
    assert block.startswith(BAN_BEGIN)
    assert block.rstrip().endswith(BAN_END)
    assert "alias npm=" not in block
    assert "alias pnpm=" not in block
    assert "alias pip=" in block
    assert "alias pip3=" in block
    assert not [line for line in block.splitlines() if line.startswith("alias npx=")]
    assert "banned" in block


def test_write_ban_aliases_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    write_ban_aliases(rc)
    write_ban_aliases(rc)
    text = rc.read_text()
    assert "# user content" in text
    assert text.count(BAN_BEGIN) == 1  # not duplicated


def test_remove_ban_aliases_strips_block_preserving_user_content(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    write_ban_aliases(rc)
    remove_ban_aliases(rc)
    text = rc.read_text()
    assert "# user content" in text
    assert BAN_BEGIN not in text


def test_remove_ban_aliases_missing_file_is_noop(tmp_path: Path):
    remove_ban_aliases(tmp_path / "nope")  # must not raise


def test_remove_ban_aliases_no_block_is_noop(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    remove_ban_aliases(rc)
    assert rc.read_text() == "# user content\n"


def test_ban_aliases_write_failure_leaves_the_rc_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """SAFE-04 / D-05: a failed atomic write (disk full, crash) must leave the
    original rc untouched, byte for byte, with no temp file left behind."""
    rc = tmp_path / ".zshrc"
    original = b"export PATH=$HOME/bin:$PATH\n# user bytes\r\n"
    rc.write_bytes(original)

    def boom(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError, match="disk full"):
        write_ban_aliases(rc)
    assert rc.read_bytes() == original
    assert list(tmp_path.glob("*.tools-installer.tmp")) == []


def test_ban_aliases_write_through_a_symlinked_rc(tmp_path: Path):
    """SAFE-04 / D-05: a symlinked rc (dotfiles-manager setup) stays a symlink;
    the write lands in its target and preserves the user's bytes."""
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "zshrc"
    target.write_text("# user\nexport A=1\n")
    rc = tmp_path / ".zshrc"
    rc.symlink_to(target)

    write_ban_aliases(rc)

    assert rc.is_symlink()
    new_text = target.read_text()
    assert BAN_BEGIN in new_text
    assert new_text.startswith("# user\nexport A=1\n")


def _old_ban_block() -> str:
    """The pre-phase block: the current block with the npx redirect alias before BAN_END."""
    return ban_alias_block().replace(BAN_END, f"alias npx='pnpm dlx'\n{BAN_END}")


def test_rewrite_outdated_ban_aliases_drops_the_npx_alias(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    rc.write_text(f"user1\nuser2\n{_old_ban_block()}\nuser3\nuser4\n")
    expected = f"user1\nuser2\n{ban_alias_block()}\nuser3\nuser4\n"
    message = f"Rewrote the guard aliases in {display_path(rc)}: npx now runs through its redirect."
    assert rewrite_outdated_ban_aliases([rc]) == ((message, "ok"),)
    assert rc.read_text() == expected
    assert rewrite_outdated_ban_aliases([rc]) == ()
    assert rc.read_text() == expected


def test_rewrite_outdated_ban_aliases_keeps_other_lines_byte_for_byte(tmp_path: Path):
    """C-11 (IN-03): CRLF and lone CR user lines outside the block survive the rewrite."""
    rc = tmp_path / ".myshellrc"
    head, tail = b"user1\r\nuser2\rstill2\r\n", b"\nuser3\r\n"
    rc.write_bytes(head + _old_ban_block().encode() + tail)
    ((_message, level),) = rewrite_outdated_ban_aliases([rc])
    assert level == "ok"
    assert rc.read_bytes() == head + ban_alias_block().encode() + tail


@pytest.mark.parametrize("shape", ["missing", "no_block", "orphan_begin"])
def test_rewrite_outdated_ban_aliases_never_adds_a_block(tmp_path: Path, shape: str):
    rc = tmp_path / ".myshellrc"
    texts = {"no_block": "user only\n", "orphan_begin": f"user only\n{BAN_BEGIN}\nalias pip='x'\n"}
    if shape in texts:
        rc.write_text(texts[shape])
    assert rewrite_outdated_ban_aliases([rc]) == ()
    assert rc.exists() == (shape in texts)
    if shape in texts:
        assert rc.read_text() == texts[shape]


def test_rewrite_outdated_ban_aliases_leaves_a_current_block(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    text = f"user1\n{ban_alias_block()}\nuser2\n"
    rc.write_text(text)
    assert rewrite_outdated_ban_aliases([rc]) == ()
    assert rc.read_text() == text


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_rewrite_outdated_ban_aliases_warns_when_it_cannot_write(tmp_path: Path):
    locked = tmp_path / "locked"
    locked.mkdir()
    rc = locked / ".myshellrc"
    text = f"user1\n{_old_ban_block()}\n"
    rc.write_text(text)
    locked.chmod(0o555)
    try:
        results = rewrite_outdated_ban_aliases([rc])
    finally:
        locked.chmod(0o755)
    assert len(results) == 1
    message, level = results[0]
    assert level == "warn"
    assert message.startswith("Could not rewrite the guard aliases in ")
    assert message.endswith("; fix its permissions, then relaunch.")
    assert rc.read_text() == text


def test_rewrite_outdated_ban_aliases_sanitizes_the_path(tmp_path: Path):
    odd = tmp_path / "a\x1b[31mb"
    odd.mkdir()
    rc = odd / ".myshellrc"
    rc.write_text(f"{_old_ban_block()}\n")
    ((message, level),) = rewrite_outdated_ban_aliases([rc])
    assert level == "ok"
    assert not any(ord(ch) < 32 or ord(ch) == 127 for ch in message)


def _old_npx_body(target: str = "/x/pnpm") -> str:
    """The pre-phase redirect: the sentinel, then one exec into pnpm dlx."""
    return f'#!/bin/sh\n{REDIRECT_SENTINEL}\nexec {target} dlx "$@"\n'


def test_rewrite_outdated_npx_rewrites_an_old_body(tmp_path: Path):
    npx = tmp_path / "npx"
    npx.write_text(_old_npx_body())
    message = (
        f"Rewrote the npx redirect at {display_path(npx)}: "
        "the old one could run a package's default bin."
    )
    assert rewrite_outdated_npx(tmp_path) == ((message, "ok"),)
    assert npx.read_text() == redirect_shim_script("npx", "/x/pnpm")
    assert npx.stat().st_mode & 0o777 == 0o755
    assert rewrite_outdated_npx(tmp_path) == ()
    assert npx.read_text() == redirect_shim_script("npx", "/x/pnpm")


def test_rewrite_outdated_npx_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "npx").write_text(_old_npx_body())
    calls: list[tuple[Path, str, int | None]] = []

    def spy(path: Path, text: str, *, mode: int | None = None) -> None:
        calls.append((path, text, mode))

    monkeypatch.setattr("installer.guards.atomic_write_text", spy)
    rewrite_outdated_npx(tmp_path)
    assert calls == [(tmp_path / "npx", redirect_shim_script("npx", "/x/pnpm"), 0o755)]


def _npx_snapshot(*paths: Path) -> list[tuple[Path, bytes]]:
    return [(path, path.read_bytes()) for path in paths]


@pytest.mark.parametrize("shape", ["absent", "foreign", "hard_block", "symlink", "current"])
def test_rewrite_outdated_npx_skips_what_it_does_not_own(tmp_path: Path, shape: str):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text(_old_npx_body())
    npx = bin_dir / "npx"
    bodies = {
        "foreign": "#!/bin/sh\necho mine\n",
        "hard_block": shim_script("npx"),
        "current": redirect_shim_script("npx", "/x/pnpm"),
    }
    if shape in bodies:
        npx.write_text(bodies[shape])
    if shape == "symlink":
        npx.symlink_to(elsewhere)
    before = _npx_snapshot(*(path for path in (npx, elsewhere) if path.exists()))
    assert rewrite_outdated_npx(bin_dir) == ()
    assert before == _npx_snapshot(*(path for path in (npx, elsewhere) if path.exists()))
    assert npx.is_symlink() == (shape == "symlink")
    assert npx.exists() == (shape != "absent")


def test_rewrite_outdated_npx_never_follows_a_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def boom(_path: Path) -> bool:
        raise AssertionError("is_our_shim follows symlinks")

    monkeypatch.setattr("installer.guards.is_our_shim", boom)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text(_old_npx_body())
    (bin_dir / "npx").symlink_to(elsewhere)
    assert rewrite_outdated_npx(bin_dir) == ()
    assert elsewhere.read_text() == _old_npx_body()
    assert (bin_dir / "npx").is_symlink()
    other = tmp_path / "other"
    other.mkdir()
    (other / "npx").write_text(_old_npx_body())
    assert len(rewrite_outdated_npx(other)) == 1


def test_rewrite_outdated_npx_leaves_the_npm_and_pnpm_wrappers(tmp_path: Path):
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    path_value = f"{shim_dir}{os.pathsep}{volta.parent}"
    lookup = _volta_pnpm_lookup(volta, pnpm)
    install_global_redirect_shims(shim_dir, path_value=path_value, lookup=lookup)
    wrappers = {name: (shim_dir / name).read_bytes() for name in GLOBAL_REDIRECTED}
    assert set(wrappers) == {"npm", "pnpm"}
    (shim_dir / "npx").write_text(_old_npx_body())
    assert len(rewrite_outdated_npx(shim_dir)) == 1
    assert {name: (shim_dir / name).read_bytes() for name in GLOBAL_REDIRECTED} == wrappers


def test_rewrite_outdated_npx_trailing_whitespace_is_rewritten_once(tmp_path: Path):
    npx = tmp_path / "npx"
    npx.write_text(redirect_shim_script("npx", "/x/pnpm") + " ")
    assert len(rewrite_outdated_npx(tmp_path)) == 1
    assert npx.read_text() == redirect_shim_script("npx", "/x/pnpm")
    assert rewrite_outdated_npx(tmp_path) == ()


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_rewrite_outdated_npx_warns_on_a_read_only_bin_dir(tmp_path: Path):
    locked = tmp_path / "locked"
    locked.mkdir()
    npx = locked / "npx"
    npx.write_text(_old_npx_body())
    locked.chmod(0o555)
    try:
        results = rewrite_outdated_npx(locked)
    finally:
        locked.chmod(0o755)
    assert len(results) == 1
    message, level = results[0]
    assert level == "warn"
    assert message.startswith("Could not rewrite the npx redirect at ")
    assert message.endswith("; fix the bin dir permissions, then relaunch.")
    assert npx.read_text() == _old_npx_body()


def test_rewrite_outdated_npx_never_reresolves_pnpm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PATH", "")
    npx = tmp_path / "npx"
    npx.write_text(_old_npx_body("/gone/pnpm"))
    assert len(rewrite_outdated_npx(tmp_path)) == 1
    assert npx.read_text() == redirect_shim_script("npx", "/gone/pnpm")
    assert SHIM_SENTINEL not in npx.read_text()


def test_rewrite_outdated_npx_keeps_a_hand_edited_target(tmp_path: Path):
    npx = tmp_path / "npx"
    npx.write_text(_old_npx_body("/custom/place/pnpm"))
    assert len(rewrite_outdated_npx(tmp_path)) == 1
    assert npx.read_text() == redirect_shim_script("npx", "/custom/place/pnpm")
    assert rewrite_outdated_npx(tmp_path) == ()
    assert npx.read_text() == redirect_shim_script("npx", "/custom/place/pnpm")


def test_rewrite_outdated_npx_sanitizes_the_path(tmp_path: Path):
    odd = tmp_path / "a\x1b[31mb"
    odd.mkdir()
    (odd / "npx").write_text(_old_npx_body())
    ((message, level),) = rewrite_outdated_npx(odd)
    assert level == "ok"
    assert not any(ord(ch) < 32 or ord(ch) == 127 for ch in message)


def test_guard_path_warning_when_shim_dir_not_on_path(tmp_path: Path):
    warning = guard_path_warning(tmp_path, path_value="/usr/bin:/bin", which=lambda _n: None)
    assert warning is not None
    assert str(tmp_path) in warning


def test_guard_path_warning_when_real_tool_resolves_first(tmp_path: Path):
    # shim dir is on PATH but AFTER /usr/bin, where a real pip lives.
    install_shims(tmp_path)
    path_value = f"/usr/bin:{tmp_path}"
    warning = guard_path_warning(
        tmp_path,
        path_value=path_value,
        which=lambda name: "/usr/bin/pip" if name == "pip" else None,
    )
    assert warning is not None
    assert "/usr/bin/pip" in warning


def test_guard_path_warning_none_when_shim_is_not_ours(tmp_path: Path):
    path_value = f"/usr/bin:{tmp_path}"
    warning = guard_path_warning(
        tmp_path,
        path_value=path_value,
        which=lambda name: "/usr/bin/pnpm" if name == "pnpm" else None,
    )
    assert warning is None


def test_guard_path_warning_none_when_healthy(tmp_path: Path):
    # shim dir is first; the only resolvable tool is our own shim inside it.
    install_shims(tmp_path)
    path_value = f"{tmp_path}:/usr/bin"
    warning = guard_path_warning(
        tmp_path, path_value=path_value, which=lambda name: str(tmp_path / name)
    )
    assert warning is None


def test_guard_path_warning_none_when_real_tool_not_on_path_dirs(tmp_path: Path):
    # A real binary resolves but its parent dir isn't in the path_dirs list.
    # This can happen when which finds it via a dir not listed in path_value.
    install_shims(tmp_path)
    path_value = f"{tmp_path}:/usr/bin"
    warning = guard_path_warning(
        tmp_path,
        path_value=path_value,
        which=lambda name: "/opt/local/bin/pip" if name == "pip" else str(tmp_path / name),
    )
    assert warning is None


def test_redirect_shim_script_is_posix_exec_through():
    script = redirect_shim_script("npx", "/fake/bin/pnpm")
    lines = script.splitlines()
    assert lines[0] == "#!/bin/sh"
    assert lines[1] == REDIRECT_SENTINEL
    assert lines[-1] == (f'exec {shlex.quote("/fake/bin/pnpm")} {shlex.quote("dlx")} "$@"')
    assert REDIRECTED["npx"].target == "pnpm"
    assert REDIRECTED["npx"].args == ("dlx",)


def test_redirect_shim_script_is_valid_posix_sh(tmp_path: Path):
    shim = tmp_path / "npx"
    shim.write_text(redirect_shim_script("npx", "/fake/bin/pnpm"))
    result = subprocess.run(["sh", "-n", str(shim)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


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


def test_install_redirect_shims_creates_then_refreshes(tmp_path: Path):
    real_dir = tmp_path / "real"
    shim_dir = tmp_path / "shims"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)

    def lookup(name: str, _path: str) -> str | None:
        return str(pnpm) if name == "pnpm" else None

    path_value = f"{shim_dir}{os.pathsep}{real_dir}"
    first = install_redirect_shims(shim_dir, path_value=path_value, lookup=lookup)
    assert first == {"npx": "created"}
    shim = shim_dir / "npx"
    assert shim.stat().st_mode & 0o111
    assert REDIRECT_SENTINEL in shim.read_text()
    second = install_redirect_shims(shim_dir, path_value=path_value, lookup=lookup)
    assert second == {"npx": "refreshed"}


def test_shim_script_npx_is_valid_and_exits_127(tmp_path: Path):
    shim = tmp_path / "npx"
    shim.write_text(shim_script("npx"))
    shim.chmod(0o755)
    syntax = subprocess.run(["sh", "-n", str(shim)], capture_output=True, text=True, check=False)
    assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run([str(shim)], capture_output=True, text=True, check=False)
    assert result.returncode == 127
    assert "pnpm" in result.stderr


def test_guarded_names_is_stable_and_deduplicated():
    assert guarded_names() == ("npm", "pip", "pip3", "npx", "pnpm")
    assert len(guarded_names()) == 5


def test_guard_label_distinguishes_redirect_from_block():
    assert guard_label("npx") == "redirected to pnpm dlx"
    assert guard_label("pip") == "blocked"
    assert (
        guard_label("npm") == "global installs redirected to volta install, other npm use blocked"
    )
    assert guard_label("pnpm") == "global adds redirected to volta install"


def test_guard_path_warning_when_real_npx_resolves_first(tmp_path: Path):
    install_shims(tmp_path)
    path_value = f"/usr/bin:{tmp_path}"
    warning = guard_path_warning(
        tmp_path,
        path_value=path_value,
        which=lambda name: "/usr/bin/npx" if name == "npx" else None,
    )
    assert warning is not None
    assert "/usr/bin/npx" in warning


def test_guard_redirect_warning_none_when_redirect_live(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    pnpm = tmp_path / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)
    (shim_dir / "npx").write_text(redirect_shim_script("npx", str(pnpm)))
    assert guard_redirect_warning(shim_dir) is None


def test_guard_redirect_warning_when_hard_block_fallback(tmp_path: Path):
    (tmp_path / "npx").write_text(shim_script("npx"))
    warning = guard_redirect_warning(tmp_path)
    assert warning is not None
    assert "npx" in warning
    assert "pnpm" in warning


def test_install_redirect_shims_falls_back_to_hard_block_when_pnpm_missing(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    results = install_redirect_shims(shim_dir, path_value=str(shim_dir), lookup=lambda _n, _p: None)
    assert results == {"npx": "blocked (pnpm not found)"}
    text = (shim_dir / "npx").read_text()
    assert SHIM_SENTINEL in text
    assert REDIRECT_SENTINEL not in text


def test_npx_redirect_shim_execs_into_pnpm_dlx_with_real_exit_code(tmp_path: Path):
    real_dir = tmp_path / "real"
    shim_dir = tmp_path / "shims"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text('#!/bin/sh\necho "$@"\nexit 3\n')
    pnpm.chmod(0o755)

    def lookup(name: str, _path: str) -> str | None:
        return str(pnpm) if name == "pnpm" else None

    install_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{real_dir}",
        lookup=lookup,
    )
    result = subprocess.run(
        [str(shim_dir / "npx"), "a", "b"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 3
    assert "dlx a b" in result.stdout


def _npx_with_fake_pnpm(tmp_path: Path, exit_code: int = 0) -> tuple[Path, Path]:
    """An npx redirect shim over a fake pnpm that records its argv NUL-separated."""
    record = tmp_path / "argv.bin"
    pnpm = tmp_path / "pnpm"
    pnpm.write_text(
        '#!/bin/sh\nfor a in "$@"; do printf "%s\\0" "$a"; done > '
        f"{shlex.quote(str(record))}\nexit {exit_code}\n"
    )
    pnpm.chmod(0o755)
    shim = tmp_path / "npx"
    shim.write_text(redirect_shim_script("npx", str(pnpm)))
    shim.chmod(0o755)
    return shim, record


def _run_npx(shim: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(shim), *argv],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )


def _recorded(record: Path) -> list[str]:
    return [arg.decode() for arg in record.read_bytes().split(b"\0")[:-1]]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("-y", "-p", "pkg", "bin", "a", "b"), ["dlx", "--package=pkg", "bin", "a", "b"]),
        (("--package=a", "-p", "b", "cmd"), ["dlx", "--package=a", "--package=b", "cmd"]),
        (("--package", "a", "cmd"), ["dlx", "--package=a", "cmd"]),
        (("--yes", "pkg@1", "x"), ["dlx", "pkg@1", "x"]),
        (("pkg@1", "x"), ["dlx", "pkg@1", "x"]),
        (("cmd", "-p", "x", "--yes"), ["dlx", "cmd", "-p", "x", "--yes"]),
    ],
)
def test_npx_shim_translates_package_options(
    tmp_path: Path, argv: tuple[str, ...], expected: list[str]
):
    shim, record = _npx_with_fake_pnpm(tmp_path)
    result = _run_npx(shim, *argv)
    assert result.returncode == 0, result.stderr
    assert _recorded(record) == expected


def test_npx_shim_returns_pnpm_exit_code(tmp_path: Path):
    shim, _ = _npx_with_fake_pnpm(tmp_path, exit_code=3)
    assert _run_npx(shim, "cmd").returncode == 3


def test_npx_shim_body_keeps_the_contract(tmp_path: Path):
    target = "/fake/bin/pnpm"
    body = redirect_shim_script("npx", target)
    lines = body.splitlines()
    assert lines[1] == REDIRECT_SENTINEL
    exec_lines = [line for line in lines if line.strip().startswith("exec ")]
    assert exec_lines == [f'exec {shlex.quote(target)} {shlex.quote("dlx")} "$@"']
    assert lines[-1] == exec_lines[0]
    assert exec_targets(body) == (target,)
    shim = tmp_path / "npx"
    shim.write_text(body)
    syntax = subprocess.run(["sh", "-n", str(shim)], capture_output=True, text=True, check=False)
    assert syntax.returncode == 0, syntax.stderr


def _not_supported(token: str) -> str:
    return (
        f"npx: option '{token}' is not supported by this redirect (it runs pnpm dlx); "
        "nothing was run.\n"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ("-c", "echo hi"),
        ("--call", "x"),
        ("--no", "pkg"),
        ("--no-install", "pkg"),
        ("-w", "ws", "cmd"),
        ("--workspace=ws", "cmd"),
        ("--frobnicate", "pkg"),
        ("--", "cmd"),
        ("-", "cmd"),
    ],
)
def test_npx_shim_refuses_untranslated_options(tmp_path: Path, argv: tuple[str, ...]):
    shim, record = _npx_with_fake_pnpm(tmp_path)
    result = _run_npx(shim, *argv)
    assert result.returncode == 127
    assert result.stderr == _not_supported(argv[0])
    assert not record.exists()


@pytest.mark.parametrize("argv", [(), ("-y",)])
def test_npx_shim_needs_a_command(tmp_path: Path, argv: tuple[str, ...]):
    shim, record = _npx_with_fake_pnpm(tmp_path)
    result = _run_npx(shim, *argv)
    assert result.returncode == 127
    assert result.stderr == "npx: missing command. Usage: npx [-y] [-p package]... command [args]\n"
    assert not record.exists()


@pytest.mark.parametrize(
    ("argv", "token"),
    [
        (("-p",), "-p"),
        (("--package",), "--package"),
        (("-p", "", "cmd"), "-p"),
        (("--package=", "cmd"), "--package="),
    ],
)
def test_npx_shim_needs_a_package_name(tmp_path: Path, argv: tuple[str, ...], token: str):
    shim, record = _npx_with_fake_pnpm(tmp_path)
    result = _run_npx(shim, *argv)
    assert result.returncode == 127
    assert result.stderr == f"npx: option '{token}' needs a package name; nothing was run.\n"
    assert not record.exists()


def test_npx_shim_passes_awkward_arguments_through(tmp_path: Path):
    shim, record = _npx_with_fake_pnpm(tmp_path)
    result = _run_npx(shim, "cmd", "a b", "$x", "q'uote")
    assert result.returncode == 0, result.stderr
    assert _recorded(record) == ["dlx", "cmd", "a b", "$x", "q'uote"]


@pytest.mark.parametrize("token", ["--%s%n", "--a\\nb", "--a\nb", "--$(id)"])
def test_npx_shim_prints_hostile_tokens_literally(tmp_path: Path, token: str):
    shim, record = _npx_with_fake_pnpm(tmp_path)
    result = _run_npx(shim, token, "cmd")
    assert result.returncode == 127
    assert result.stderr == _not_supported(token)
    assert not record.exists()


def test_npx_shim_messages_keep_the_ui_copy(tmp_path: Path):
    shim, _ = _npx_with_fake_pnpm(tmp_path)
    not_supported = (
        "npx: option '' is not supported by this redirect (it runs pnpm dlx); nothing was run."
    )
    missing = "npx: missing command. Usage: npx [-y] [-p package]... command [args]"
    needs_package = "npx: option '' needs a package name; nothing was run."
    assert len(not_supported) == 85
    assert len(missing) <= 78
    assert len(needs_package) <= 78
    assert _run_npx(shim, "-x", "cmd").stderr == not_supported.replace("''", "'-x'") + "\n"
    assert _run_npx(shim).stderr == missing + "\n"
    assert _run_npx(shim, "-p").stderr == needs_package.replace("''", "'-p'") + "\n"


def test_banned_npm_hint_names_volta_not_global_add():
    hint = BANNED["npm"]
    assert "volta install" in hint
    assert "add -g" not in hint


def _global_shims(tmp_path: Path) -> tuple[Path, Path]:
    volta = tmp_path / "volta"
    volta.write_text('#!/bin/sh\necho "VOLTA $@"\n')
    volta.chmod(0o755)
    pnpm = tmp_path / "pnpm"
    pnpm.write_text('#!/bin/sh\necho "PNPM $@"\n')
    pnpm.chmod(0o755)
    npm_shim = tmp_path / "npm"
    npm_shim.write_text(
        global_redirect_shim_script("npm", volta_path=str(volta), passthrough_path=None)
    )
    npm_shim.chmod(0o755)
    pnpm_shim = tmp_path / "pnpm-shim"
    pnpm_shim.write_text(
        global_redirect_shim_script("pnpm", volta_path=str(volta), passthrough_path=str(pnpm))
    )
    pnpm_shim.chmod(0o755)
    return npm_shim, pnpm_shim


def _run_shim(shim: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(shim), *argv], capture_output=True, text=True, check=False)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("install", "-g", "typescript"), "VOLTA install typescript\n"),
        (("add", "-g", "@scope/pkg"), "VOLTA install @scope/pkg\n"),
        (("i", "-g", "a", "b"), "VOLTA install a b\n"),
        # A whitelisted boolean in attached form is still droppable.
        (("install", "-g", "typescript", "--save-dev=true"), "VOLTA install typescript\n"),
        (("i", "-gD", "typescript"), "VOLTA install typescript\n"),
    ],
)
def test_npm_global_install_redirects_to_volta(
    tmp_path: Path, argv: tuple[str, ...], expected: str
):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, *argv)
    assert result.returncode == 0
    assert result.stdout == expected


@pytest.mark.parametrize(
    "argv",
    [
        ("install", "-g", "--loglevel", "warn", "typescript"),
        ("i", "-g", "--registry", "https://r.example.test", "p"),
        ("install", "--prefix", "/tmp", "-g", "typescript"),
    ],
)
def test_npm_separated_option_value_never_reaches_volta(tmp_path: Path, argv: tuple[str, ...]):
    # A separated option value is not a package name: redirecting `--loglevel
    # warn typescript` would install the real npm package `warn`.
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, *argv)
    assert result.returncode == 127
    assert result.stdout == ""
    assert "banned" in result.stderr


@pytest.mark.parametrize(
    "argv",
    [
        # An option volta cannot honour must degrade, not be dropped: volta runs
        # a real `npm install --global`, so redirecting these would run the
        # install with scripts enabled / resolution forced / the network live
        # after the user typed the option that says otherwise.
        ("i", "-g", "--ignore-scripts", "typescript"),
        ("i", "-g", "--force", "typescript"),
        ("i", "-g", "--offline", "typescript"),
        ("i", "-g", "--prefer-offline", "typescript"),
        # nopt's explicit-value form for a Boolean: `false` is the option's
        # value, so redirecting would run `volta install false typescript`.
        ("i", "-g", "--ignore-scripts", "false", "typescript"),
        ("i", "-g", "--save-dev", "true", "typescript"),
        ("i", "--global", "false", "typescript"),
    ],
)
def test_npm_unhonourable_option_never_reaches_volta(tmp_path: Path, argv: tuple[str, ...]):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, *argv)
    assert result.returncode == 127
    assert result.stdout == ""
    assert "banned" in result.stderr


@pytest.mark.parametrize(
    "argv",
    [
        # Dropping a pinned registry re-resolves the package from npmjs.com:
        # a dependency-confusion setup built by the tool meant to prevent one.
        ("i", "-g", "--registry=https://npm.internal.test", "mypkg"),
        ("i", "-g", "--prefix=/opt/x", "mypkg"),
        ("i", "-g", "--loglevel=warn", "typescript"),
        ("i", "-g", "--ignore-scripts=true", "typescript"),
        # --global's value is what decides global-ness, and the loop is only
        # allowed to read the option's name.
        ("i", "--global=true", "typescript"),
    ],
)
def test_npm_attached_option_value_is_whitelisted_by_name(tmp_path: Path, argv: tuple[str, ...]):
    # The attached --opt=value form consumes no following token, which makes it
    # parseable — not droppable. Only a whitelisted boolean name may be dropped.
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, *argv)
    assert result.returncode == 127
    assert result.stdout == ""
    assert "banned" in result.stderr


def test_pnpm_attached_registry_passes_through_with_the_registry_intact(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "-g", "--registry=https://npm.internal.test", "mypkg")
    assert result.returncode == 0
    assert result.stdout == "PNPM add -g --registry=https://npm.internal.test mypkg\n"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ("add", "-g", "--ignore-scripts", "typescript"),
            "PNPM add -g --ignore-scripts typescript\n",
        ),
        (
            ("add", "-g", "--ignore-scripts", "false", "typescript"),
            "PNPM add -g --ignore-scripts false typescript\n",
        ),
    ],
)
def test_pnpm_unhonourable_option_passes_through_unmodified(
    tmp_path: Path, argv: tuple[str, ...], expected: str
):
    # pnpm's degrade path keeps the option the user typed, under pnpm's own
    # gated-postinstall model — the safe direction in both dimensions.
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, *argv)
    assert result.returncode == 0
    assert result.stdout == expected


def test_pnpm_separated_option_value_passes_through_to_real_pnpm(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "-g", "--dir", "/tmp", "typescript")
    assert result.returncode == 0
    assert result.stdout == "PNPM add -g --dir /tmp typescript\n"


def test_pnpm_attached_short_value_carrying_g_is_not_global(tmp_path: Path):
    # -Cmy-gadget is `-C my-gadget`, not a boolean cluster: its `g` must not
    # turn a workspace-scoped add into a global install.
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "-Cmy-gadget", "add", "x")
    assert result.returncode == 0
    assert result.stdout == "PNPM -Cmy-gadget add x\n"


def test_boolean_option_whitelists_hold_only_valueless_options():
    assert "--global" in BOOLEAN_LONG_OPTIONS
    # Options that take a value must never be whitelisted, or their value is
    # forwarded to `volta install` as a package name.
    for taker in ("--loglevel", "--registry", "--prefix", "--dir", "--filter", "--workspace"):
        assert taker not in BOOLEAN_LONG_OPTIONS
    assert "g" in BOOLEAN_SHORT_FLAGS
    for taker in ("C", "F", "w"):
        assert taker not in BOOLEAN_SHORT_FLAGS


def test_boolean_option_whitelist_excludes_options_volta_cannot_honour():
    # Valueless is necessary but not sufficient: a whitelisted option is
    # DROPPED, and `volta install` runs a real `npm install --global`, so
    # dropping any of these would silently run the install under weaker rules
    # than the user typed.
    for unhonourable in ("--ignore-scripts", "--force", "--offline", "--prefer-offline"):
        assert unhonourable not in BOOLEAN_LONG_OPTIONS


def test_pnpm_add_gd_redirects_to_volta(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "-gD", "typescript")
    assert result.returncode == 0
    assert result.stdout == "VOLTA install typescript\n"


def test_npm_install_d_without_g_is_banned(tmp_path: Path):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, "install", "-D", "typescript")
    assert result.returncode == 127
    assert result.stdout == ""
    assert "banned" in result.stderr


def test_pnpm_add_d_passes_through(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "-D", "typescript")
    assert result.returncode == 0
    assert result.stdout == "PNPM add -D typescript\n"


def test_pnpm_filter_equals_g_is_not_global(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "typescript", "--filter=-g")
    assert result.returncode == 0
    assert result.stdout == "PNPM add typescript --filter=-g\n"


def test_npm_install_without_global_is_banned(tmp_path: Path):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, "install", "typescript")
    assert result.returncode == 127
    assert result.stdout == ""
    assert "banned" in result.stderr


def test_npm_ls_g_is_banned(tmp_path: Path):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, "ls", "-g")
    assert result.returncode == 127


def test_npm_install_g_without_package_names_missing_package(tmp_path: Path):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, "install", "-g")
    assert result.returncode == 127
    assert "package name" in result.stderr


def test_pnpm_add_g_redirects_to_volta(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "-g", "typescript")
    assert result.returncode == 0
    assert result.stdout == "VOLTA install typescript\n"


def test_pnpm_add_without_global_passes_through_unmodified(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "add", "typescript")
    assert result.returncode == 0
    assert result.stdout == "PNPM add typescript\n"


def test_pnpm_list_g_passes_through_unmodified(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "list", "-g")
    assert result.returncode == 0
    assert result.stdout == "PNPM list -g\n"


def test_pnpm_run_build_watch_passes_through(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "run", "build", "--watch")
    assert result.returncode == 0
    assert result.stdout == "PNPM run build --watch\n"


def test_pnpm_passthrough_preserves_real_exit_code(tmp_path: Path):
    volta = tmp_path / "volta"
    volta.write_text("#!/bin/sh\n")
    volta.chmod(0o755)
    pnpm = tmp_path / "pnpm"
    pnpm.write_text("#!/bin/sh\nexit 7\n")
    pnpm.chmod(0o755)
    shim = tmp_path / "pnpm-shim"
    shim.write_text(
        global_redirect_shim_script("pnpm", volta_path=str(volta), passthrough_path=str(pnpm))
    )
    shim.chmod(0o755)
    result = _run_shim(shim, "run", "build")
    assert result.returncode == 7


def test_global_redirect_shim_is_valid_posix_sh(tmp_path: Path):
    npm_shim, pnpm_shim = _global_shims(tmp_path)
    for shim in (npm_shim, pnpm_shim):
        syntax = subprocess.run(
            ["sh", "-n", str(shim)], capture_output=True, text=True, check=False
        )
        assert syntax.returncode == 0, syntax.stderr


def test_npm_global_fallback_matches_ban_shim_last_two_lines():
    body = global_redirect_shim_script("npm", volta_path="/v/volta", passthrough_path=None)
    assert body.splitlines()[-2:] == shim_script("npm").splitlines()[-2:]


def test_pnpm_wrapper_requires_passthrough_path():
    with pytest.raises(ValueError):
        global_redirect_shim_script("pnpm", volta_path="/v/volta", passthrough_path=None)


def test_ban_body_without_hint_raises_valueerror_not_keyerror():
    # A future GLOBAL_REDIRECTED entry with no pass-through and no BANNED hint
    # must fail with an explanation, not a bare dict miss.
    with pytest.raises(ValueError, match="BANNED hint"):
        ban_body("yarn")


def test_hard_block_fallback_reuses_the_ban_shim_body():
    body = global_redirect_shim_script("npm", volta_path="/v/volta", passthrough_path=None)
    assert body.endswith(ban_body("npm"))
    assert shim_script("npm").endswith(ban_body("npm"))


def test_global_redirect_constants():
    assert GLOBAL_SUBCOMMANDS == ("install", "add", "i")
    assert GLOBAL_REDIRECTED["npm"].passthrough is None
    assert GLOBAL_REDIRECTED["pnpm"].passthrough == "pnpm"


def test_npm_prefix_before_subcommand_fails_to_hard_block(tmp_path: Path):
    npm_shim, _pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(npm_shim, "--prefix", "/tmp", "install", "-g", "typescript")
    assert result.returncode == 127
    assert "banned" in result.stderr


def test_pnpm_filter_before_subcommand_passes_through(tmp_path: Path):
    _npm_shim, pnpm_shim = _global_shims(tmp_path)
    result = _run_shim(pnpm_shim, "--filter", "web", "add", "-g", "typescript")
    assert result.returncode == 0
    assert result.stdout == "PNPM --filter web add -g typescript\n"


def _volta_pnpm_lookup(volta: Path, pnpm: Path | None):
    def lookup(name: str, _path: str) -> str | None:
        if name == "volta":
            return str(volta)
        if name == "pnpm" and pnpm is not None:
            return str(pnpm)
        return None

    return lookup


def _plant_volta_pnpm(tmp_path: Path) -> tuple[Path, Path, Path]:
    real_dir = tmp_path / "real"
    shim_dir = tmp_path / "shims"
    real_dir.mkdir()
    volta = real_dir / "volta"
    volta.write_text("#!/bin/sh\n")
    volta.chmod(0o755)
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)
    return shim_dir, volta, pnpm


def test_install_global_redirect_shims_creates_then_refreshes(tmp_path: Path):
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    lookup = _volta_pnpm_lookup(volta, pnpm)
    path_value = f"{shim_dir}{os.pathsep}{volta.parent}"
    first = install_global_redirect_shims(shim_dir, path_value=path_value, lookup=lookup)
    assert first == {"npm": "created", "pnpm": "created"}
    for name in ("npm", "pnpm"):
        shim = shim_dir / name
        assert shim.stat().st_mode & 0o111
        assert REDIRECT_SENTINEL in shim.read_text()
    second = install_global_redirect_shims(shim_dir, path_value=path_value, lookup=lookup)
    assert second == {"npm": "refreshed", "pnpm": "refreshed"}


def test_install_global_redirect_shims_volta_missing_leaves_ban(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    install_shims(shim_dir)
    before = (shim_dir / "npm").read_text()
    results = install_global_redirect_shims(
        shim_dir, path_value=str(shim_dir), lookup=lambda _n, _p: None
    )
    assert results == {"npm": "blocked (volta not found)", "pnpm": "absent (volta not found)"}
    assert not (shim_dir / "pnpm").exists()
    assert (shim_dir / "npm").read_text() == before


def test_install_global_redirect_shims_writes_the_block_it_reports(tmp_path: Path):
    # Called on its own — no install_shims first — "blocked" must be true on disk.
    shim_dir = tmp_path / "shims"
    results = install_global_redirect_shims(
        shim_dir, path_value=str(shim_dir), lookup=lambda _n, _p: None
    )
    assert results["npm"] == "blocked (volta not found)"
    npm_shim = shim_dir / "npm"
    assert npm_shim.read_text() == shim_script("npm")
    assert npm_shim.stat().st_mode & 0o111


def test_install_global_redirect_shims_removes_pnpm_when_volta_vanishes(tmp_path: Path):
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    path_value = f"{shim_dir}{os.pathsep}{volta.parent}"
    install_global_redirect_shims(
        shim_dir, path_value=path_value, lookup=_volta_pnpm_lookup(volta, pnpm)
    )
    results = install_global_redirect_shims(
        shim_dir, path_value=path_value, lookup=lambda _n, _p: None
    )
    assert results["pnpm"] == "removed (volta not found)"
    assert not (shim_dir / "pnpm").exists()


def test_install_global_redirect_shims_skips_pnpm_when_real_pnpm_missing(tmp_path: Path):
    shim_dir, volta, _pnpm = _plant_volta_pnpm(tmp_path)
    results = install_global_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{volta.parent}",
        lookup=_volta_pnpm_lookup(volta, None),
    )
    assert results["pnpm"] == "skipped (real pnpm not found)"
    assert not (shim_dir / "pnpm").exists()


def test_install_global_redirect_shims_skips_foreign_pnpm(tmp_path: Path):
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    shim_dir.mkdir()
    foreign = shim_dir / "pnpm"
    foreign.write_text("#!/bin/sh\necho real pnpm\n")
    results = install_global_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{volta.parent}",
        lookup=_volta_pnpm_lookup(volta, pnpm),
    )
    assert results["pnpm"] == "skipped (real binary here)"
    assert foreign.read_text() == "#!/bin/sh\necho real pnpm\n"


def test_guard_status_includes_pnpm(tmp_path: Path):
    status = guard_status(tmp_path)
    assert "pnpm" in status
    assert status["pnpm"] is False


def test_guard_redirect_warning_names_npm_and_volta_when_ban_body(tmp_path: Path):
    (tmp_path / "npm").write_text(shim_script("npm"))
    warning = guard_redirect_warning(tmp_path)
    assert warning is not None
    assert "npm" in warning
    assert "volta" in warning


def test_guard_redirect_warning_blames_the_foreign_pnpm_occupying_the_shim_dir(tmp_path: Path):
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    shim_dir.mkdir()
    foreign = shim_dir / "pnpm"
    foreign.write_text("#!/bin/sh\necho real pnpm\n")
    install_global_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{volta.parent}",
        lookup=_volta_pnpm_lookup(volta, pnpm),
    )
    warning = guard_redirect_warning(shim_dir)
    assert warning is not None
    assert "non-managed 'pnpm'" in warning
    assert str(shim_dir) in warning
    # The remedy must not send the user after a pnpm that is sitting right there.
    assert "not resolvable" not in warning


def test_guard_redirect_warning_reports_a_vanished_redirect_target(tmp_path: Path):
    # is_installed is `which(cmd) is not None`, so the wrapper keeps reporting
    # pnpm as installed after the real pnpm is gone; only the baked path knows.
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    install_global_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{volta.parent}",
        lookup=_volta_pnpm_lookup(volta, pnpm),
    )
    assert guard_redirect_warning(shim_dir) is None
    pnpm.unlink()
    warning = guard_redirect_warning(shim_dir)
    assert warning is not None
    assert str(pnpm) in warning
    assert "no longer exists" in warning


def test_guard_redirect_warning_reports_a_vanished_npx_target(tmp_path: Path):
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    pnpm = tmp_path / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)
    (shim_dir / "npx").write_text(redirect_shim_script("npx", str(pnpm)))
    assert guard_redirect_warning(shim_dir) is None
    pnpm.unlink()
    warning = guard_redirect_warning(shim_dir)
    assert warning is not None
    assert "npx" in warning
    assert "no longer exists" in warning


def test_exec_targets_reads_the_baked_paths(tmp_path: Path):
    body = global_redirect_shim_script(
        "pnpm", volta_path="/v/volta", passthrough_path="/r/bin/pnpm"
    )
    assert exec_targets(body) == ("/v/volta", "/r/bin/pnpm")
    assert exec_targets(shim_script("npm")) == ()


def test_guard_redirect_warning_reports_unresolvable_pnpm_when_the_dir_is_empty(tmp_path: Path):
    # No pnpm anywhere and nothing occupying the shim dir: the remedy really is
    # "install pnpm and re-apply" (contrast the foreign-binary case above).
    shim_dir, volta, _pnpm = _plant_volta_pnpm(tmp_path)
    install_global_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{volta.parent}",
        lookup=_volta_pnpm_lookup(volta, None),
    )
    warning = guard_redirect_warning(shim_dir)
    assert warning is not None
    assert "'pnpm' is not redirected" in warning
    assert "not resolvable" in warning
    assert "non-managed" not in warning


def test_exec_targets_skips_an_unparseable_exec_line():
    assert exec_targets('exec \'/unbalanced "$@"\n') == ()


def test_shell_path_accepts_explicit_arguments():
    shim_dir = Path("/home/u/.local/bin")
    path_value = os.pathsep.join([str(shim_dir), "/usr/bin"])
    assert shell_path(shim_dir=shim_dir, path_value=path_value) == os.pathsep.join(
        ["/usr/bin", str(shim_dir)]
    )


def test_guard_redirect_warning_none_when_all_global_redirects_live(tmp_path: Path):
    shim_dir, volta, pnpm = _plant_volta_pnpm(tmp_path)
    install_global_redirect_shims(
        shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{volta.parent}",
        lookup=_volta_pnpm_lookup(volta, pnpm),
    )
    (shim_dir / "npx").write_text(redirect_shim_script("npx", str(pnpm)))
    assert guard_redirect_warning(shim_dir) is None


# -- 19-04/D-13: owner attribution looks through this installer's own shims. --


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


def test_rendered_shims_fit_under_the_size_cap():
    target = "/home/user/.local/share/pnpm/pnpm"
    texts = [shim_script(name) for name in BANNED]
    texts += [redirect_shim_script(name, target) for name in REDIRECTED]
    texts += [
        global_redirect_shim_script(name, volta_path=target, passthrough_path=target)
        for name in GLOBAL_REDIRECTED
    ]
    assert texts
    assert all(len(text.encode()) < 8192 for text in texts)
