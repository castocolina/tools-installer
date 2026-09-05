import os
import shlex
import subprocess
from pathlib import Path

from installer.guards import (
    BAN_BEGIN,
    BAN_END,
    BANNED,
    REDIRECT_SENTINEL,
    REDIRECTED,
    SHIM_SENTINEL,
    ban_alias_block,
    guard_path_warning,
    guard_status,
    install_redirect_shims,
    install_shims,
    is_our_shim,
    real_binary,
    redirect_shim_script,
    remove_ban_aliases,
    remove_shims,
    shim_script,
    write_ban_aliases,
)


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


def test_guard_status_reports_installed_ours(tmp_path: Path):
    install_shims(tmp_path)
    (tmp_path / "pip").unlink()
    status = guard_status(tmp_path)
    assert status["npm"] is True
    assert status["pip"] is False


def test_ban_alias_block_aliases_each_banned_command():
    block = ban_alias_block()
    assert block.startswith(BAN_BEGIN)
    assert block.rstrip().endswith(BAN_END)
    for name in BANNED:
        assert f"alias {name}=" in block


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


def test_guard_path_warning_when_shim_dir_not_on_path(tmp_path: Path):
    warning = guard_path_warning(tmp_path, path_value="/usr/bin:/bin", which=lambda _n: None)
    assert warning is not None
    assert str(tmp_path) in warning


def test_guard_path_warning_when_real_tool_resolves_first(tmp_path: Path):
    # shim dir is on PATH but AFTER /usr/bin, where a real pip lives.
    path_value = f"/usr/bin:{tmp_path}"
    warning = guard_path_warning(
        tmp_path,
        path_value=path_value,
        which=lambda name: "/usr/bin/pip" if name == "pip" else None,
    )
    assert warning is not None
    assert "/usr/bin/pip" in warning


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

    (shim_dir / "pnpm").write_text("shim\n")
    (real_dir / "pnpm").write_text("real\n")
    found = real_binary(
        "pnpm",
        shim_dir=shim_dir,
        path_value=f"{shim_dir}{os.pathsep}{real_dir}",
        lookup=lookup,
    )
    assert found == str(real_dir / "pnpm")


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
