import shutil
import subprocess
from pathlib import Path

import pytest

from installer.model import Method, Tool
from installer.platform import Platform
from installer.shellrc import (
    apply_block,
    collect_bin_dirs,
    ensure_source,
    has_managed_block,
    managed_block,
    path_export_guard,
    remove_managed_block,
    strip_block,
    write_myshellrc,
)

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")

_PLATFORM = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


def _source_n_times(  # pyright: ignore[reportUnusedFunction]
    shell: str,
    rc: Path,
    *,
    times: int = 1,
    seed: str | None = "",
    home: Path | None = None,
) -> str:
    """Source an rc file N times in a subprocess and return the resulting $PATH.

    shell: absolute path to shell binary
    rc: path to rc file to source
    times: number of times to source it
    seed: initial PATH value (empty string means empty PATH, None means no PATH key)
    home: HOME directory for the subprocess
    """
    if home is None:
        home = Path("/tmp")
    script = f". {rc}\n" * times + "echo $PATH"
    env = {"HOME": str(home)}
    if seed is not None:
        env["PATH"] = seed
    return subprocess.run(
        [shell, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    ).stdout.strip()


def _tool(tool_id: str, bin_dir: str | None) -> Tool:
    params: dict[str, object] = {"formula": tool_id}
    if bin_dir is not None:
        params = {"member": tool_id, "bin_dir": bin_dir}
    kind = "github_release" if bin_dir is not None else "brew"
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind=kind, params=params),),
    )


def test_collect_bin_dirs_defaults_first_then_declared_deduped():
    default = Path("/home/u/.local/bin")
    tools = [
        _tool("rg", "/home/u/.local/bin"),  # same as default -> deduped
        _tool("fd", "/home/u/tools/bin"),
        _tool("jq", None),  # brew, no bin_dir
    ]
    assert collect_bin_dirs(tools, _PLATFORM, default, exists=lambda _p: True) == [
        Path("/home/u/.local/bin"),
        Path("/home/u/tools/bin"),
    ]


def test_collect_bin_dirs_expands_user():
    default = Path("/d")
    tools = [_tool("rg", "~/x/bin")]
    result = collect_bin_dirs(tools, _PLATFORM, default, exists=lambda _p: True)
    assert result[0] == Path("/d")
    assert result[1] == Path.home() / "x" / "bin"


def test_collect_bin_dirs_filters_declared_dirs_missing_on_disk():
    default = Path("/home/u/.local/bin")
    on_disk = {Path("/home/u/tools/bin")}
    tools = [_tool("fd", "/home/u/tools/bin"), _tool("bun", "/home/u/.bun/bin")]
    result = collect_bin_dirs(tools, _PLATFORM, default, exists=lambda p: p in on_disk)
    # fd's dir exists -> kept; bun's does not -> filtered out.
    assert result == [Path("/home/u/.local/bin"), Path("/home/u/tools/bin")]


def test_collect_bin_dirs_always_keeps_default_even_when_missing():
    default = Path("/home/u/.local/bin")
    tools = [_tool("fd", "/home/u/tools/bin")]
    result = collect_bin_dirs(tools, _PLATFORM, default, exists=lambda _p: False)
    assert result == [default]


def test_managed_block_emits_one_guard_per_dir_between_markers():
    block = managed_block([Path("/a/bin"), Path("/b/bin")])
    lines = block.splitlines()
    assert lines[0] == "# >>> tools-installer path >>>"
    assert lines[-1] == "# <<< tools-installer path <<<"
    assert len(lines) == 4
    assert lines[1] == path_export_guard(Path("/a/bin"))
    assert lines[2] == path_export_guard(Path("/b/bin"))


def test_apply_block_appends_when_absent_and_preserves_user_content():
    out = apply_block(
        "# my rc\nalias x=y\n", "# >>> tools-installer path >>>\nX\n# <<< tools-installer path <<<"
    )
    assert out == (
        "# my rc\nalias x=y\n\n# >>> tools-installer path >>>\nX\n# <<< tools-installer path <<<\n"
    )


def test_apply_block_appends_when_begin_marker_has_no_end():
    # Malformed rc: a stray begin marker without its end -> fall through to append.
    content = "head\n# >>> tools-installer path >>>\nstray\n"
    block = "# >>> tools-installer path >>>\nX\n# <<< tools-installer path <<<"
    out = apply_block(content, block)
    assert out.endswith(block + "\n")
    assert "stray" in out
    # Re-applying must be idempotent and must NOT eat the user's "stray" content.
    assert apply_block(out, block) == out
    assert "stray" in apply_block(out, block)


def test_apply_block_replaces_existing_block_idempotently():
    block_v1 = "# >>> tools-installer path >>>\nOLD\n# <<< tools-installer path <<<"
    block_v2 = "# >>> tools-installer path >>>\nNEW\n# <<< tools-installer path <<<"
    once = apply_block("head\n" + block_v1 + "\ntail\n", block_v2)
    twice = apply_block(once, block_v2)
    assert "OLD" not in once
    assert "NEW" in once
    assert once.count("# >>> tools-installer path >>>") == 1
    assert twice == once  # idempotent


def test_write_myshellrc_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    bin_dirs = [Path("/a/bin"), Path("/b/bin")]
    write_myshellrc(bin_dirs, rc)
    first = rc.read_text()
    write_myshellrc(bin_dirs, rc)
    assert rc.read_text() == first
    assert first.count("# >>> tools-installer path >>>") == 1
    assert path_export_guard(Path("/a/bin")) in first


def test_write_myshellrc_preserves_existing_user_lines(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    write_myshellrc([Path("/a/bin")], rc)
    text = rc.read_text()
    assert "export EDITOR=vim" in text
    assert path_export_guard(Path("/a/bin")) in text


def test_ensure_source_adds_once_and_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# zsh config\n")
    myshellrc = tmp_path / ".myshellrc"
    ensure_source(rc, myshellrc)
    after_first = rc.read_text()
    ensure_source(rc, myshellrc)
    assert rc.read_text() == after_first
    assert after_first.count("# >>> tools-installer source >>>") == 1
    assert f'. "{myshellrc}"' in after_first
    assert "# zsh config" in after_first


def test_ensure_source_creates_file_when_missing(tmp_path: Path):
    rc = tmp_path / ".bashrc"  # does not exist yet
    myshellrc = tmp_path / ".myshellrc"
    ensure_source(rc, myshellrc)
    assert rc.exists()
    assert f'. "{myshellrc}"' in rc.read_text()


def test_remove_managed_block_strips_only_the_block(tmp_path: Path) -> None:
    path = tmp_path / ".myshellrc"
    path.write_text("# user line\n")
    write_myshellrc([tmp_path / "bin"], path)
    assert "tools-installer path" in path.read_text()
    remove_managed_block(path)
    text = path.read_text()
    assert "tools-installer path" not in text
    assert "# user line" in text  # user content preserved


def test_remove_managed_block_is_idempotent_and_tolerates_absence(tmp_path: Path) -> None:
    path = tmp_path / ".myshellrc"
    remove_managed_block(path)  # missing file -> no error, no file created
    assert not path.exists()
    path.write_text("# only user content\n")
    remove_managed_block(path)  # no block present -> unchanged
    assert path.read_text() == "# only user content\n"


def test_remove_managed_block_leaves_file_untouched_when_begin_has_no_end(tmp_path: Path) -> None:
    # Orphan begin marker with no matching end -> loop exhausts, file left untouched.
    path = tmp_path / ".myshellrc"
    content = "# user\n# >>> tools-installer path >>>\nstray\n"
    path.write_text(content)
    remove_managed_block(path)
    assert path.read_text() == content  # unchanged


def test_write_managed_path_inlines_block_into_rc(tmp_path: Path) -> None:
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".zshrc"
    rc.write_text("# user line\n")
    write_managed_path(rc, [tmp_path / "bin"])
    text = rc.read_text()
    assert "# >>> tools-installer path >>>" in text
    assert path_export_guard(tmp_path / "bin") in text
    assert "# user line" in text  # user content preserved


def test_write_managed_path_is_idempotent(tmp_path: Path) -> None:
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".bashrc"
    write_managed_path(rc, [tmp_path / "bin"])
    write_managed_path(rc, [tmp_path / "bin"])
    assert rc.read_text().count("# >>> tools-installer path >>>") == 1


def test_collect_bin_dirs_only_includes_platform_applicable_methods() -> None:
    mac = Method(
        kind="script",
        params={"url": "u", "bin_dir": "/opt/homebrew/bin"},
        os=("macos",),
    )
    linux = Method(
        kind="script",
        params={"url": "u", "bin_dir": "/home/linuxbrew/.linuxbrew/bin"},
        os=("debian", "arch", "fedora"),
    )
    tool = Tool(id="brew", name="Homebrew", category="pkg-mgr", cmd="brew", methods=(mac, linux))
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    dirs = collect_bin_dirs([tool], macos, Path("~/.local/bin"), exists=lambda _p: True)
    assert Path("/opt/homebrew/bin") in dirs
    assert Path("/home/linuxbrew/.linuxbrew/bin") not in dirs


def test_strip_block_removes_the_last_well_formed_block():
    begin, end = "# >>> b >>>", "# <<< b <<<"
    text = f"keep\n{begin}\ninside\n{end}\ntail"
    assert strip_block(text, begin, end) == "keep\ntail"


def test_strip_block_absent_marker_is_unchanged():
    assert strip_block("nothing here", "# >>> b >>>", "# <<< b <<<") == "nothing here"


def test_strip_block_orphan_begin_is_unchanged():
    begin, end = "# >>> b >>>", "# <<< b <<<"
    text = f"keep\n{begin}\nno end marker"
    assert strip_block(text, begin, end) == text


def test_has_managed_block_true_when_markers_present(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    write_myshellrc([tmp_path / "bin"], rc)
    assert has_managed_block(rc) is True


def test_has_managed_block_false_for_plain_or_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert has_managed_block(missing) is False
    plain = tmp_path / ".myshellrc"
    plain.write_text("export EDITOR=vim\n")
    assert has_managed_block(plain) is False


def test_path_export_guard_emits_the_case_guard_line() -> None:
    guard = path_export_guard(Path("/a/bin"))
    assert guard.startswith("case")
    assert '":${PATH-}:"' in guard
    assert ":/a/bin:" in guard
    assert 'export PATH="/a/bin${PATH:+:$PATH}"' in guard


def test_path_export_guard_line_does_not_start_with_an_assignment() -> None:
    guard = path_export_guard(Path("/a/bin"))
    assert not guard.startswith("export")
    assert guard.split()[0] == "case"


def test_path_export_guard_never_emits_a_bare_colon_join() -> None:
    directory = Path("/a/bin")
    guard = path_export_guard(directory)
    bare_bad = f'"{directory}:$PATH"'
    assert bare_bad not in guard


def test_path_export_guard_matches_an_aliased_spelling_of_the_same_directory(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real" / "bin"
    real.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "real")

    guard = path_export_guard(link / "bin")
    assert str(link / "bin") in guard
    assert str(real) in guard
    assert f'export PATH="{str(link / "bin")}' in guard


def test_path_export_guard_falls_back_to_one_pattern_when_resolution_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_oserror(self: object) -> object:
        raise OSError()

    monkeypatch.setattr("pathlib.Path.resolve", raise_oserror)
    guard = path_export_guard(Path("/a/bin"))
    assert guard.startswith("case")
    assert 'export PATH="/a/bin' in guard


def test_managed_block_is_runtime_idempotent_under_bash(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(5)]) + "\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    matching = [e for e in path_entries if e == str(bin_dir)]
    assert len(matching) == 1


def test_path_export_guard_with_space_in_directory_name(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir = tmp_path / "a bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(5)]) + "\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    matching = [e for e in path_entries if e == str(bin_dir)]
    assert len(matching) == 1


def test_empty_starting_path_becomes_exactly_the_managed_directory(
    tmp_path: Path,
) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = f". {rc}\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": "", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    actual_path = result.stdout.strip()
    assert actual_path == str(bin_dir)


def test_a_cwd_executable_is_not_reachable_through_the_emitted_block(
    tmp_path: Path,
) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    test_script = tmp_path / "hello.sh"
    test_script.write_text("#!/bin/bash\necho 'executed'\n")
    test_script.chmod(0o755)

    script = f". {rc}\nhello.sh\n"
    result = subprocess.run(
        [bash_path, "-c", script],
        cwd=str(tmp_path),
        env={"PATH": "", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode != 0
    assert "executed" not in result.stdout


def test_unset_path_under_set_u_does_not_abort_shell(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = f"set -u\n. {rc}\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert str(bin_dir) in result.stdout.strip()


def test_the_directory_as_the_only_entry_on_path_stays_unique(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(3)]) + "\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": str(bin_dir), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    matching = [e for e in path_entries if e == str(bin_dir)]
    assert len(matching) == 1


def test_an_aliased_home_spelling_on_path_is_not_duplicated(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    real_home = tmp_path / "real_home"
    real_home.mkdir()
    link_home = tmp_path / "link_home"
    link_home.symlink_to(real_home)
    bin_dir = link_home / ".local" / "bin"
    bin_dir.mkdir(parents=True)

    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(3)]) + "\necho $PATH"
    resolved_bin = real_home / ".local" / "bin"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": str(resolved_bin), "HOME": str(link_home)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    total_matches = sum(1 for e in path_entries if e == str(bin_dir) or e == str(resolved_bin))
    assert total_matches == 1


def test_the_declared_home_spelling_on_path_is_not_duplicated(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    real_home = tmp_path / "real_home"
    real_home.mkdir()
    link_home = tmp_path / "link_home"
    link_home.symlink_to(real_home)
    bin_dir = link_home / ".local" / "bin"
    bin_dir.mkdir(parents=True)

    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(3)]) + "\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": str(bin_dir), "HOME": str(link_home)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    matching = [e for e in path_entries if e == str(bin_dir)]
    assert len(matching) == 1


def test_an_aliased_home_gets_the_declared_spelling_when_path_lacks_both(
    tmp_path: Path,
) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    real_home = tmp_path / "real_home"
    real_home.mkdir()
    link_home = tmp_path / "link_home"
    link_home.symlink_to(real_home)
    bin_dir = link_home / ".local" / "bin"
    bin_dir.mkdir(parents=True)

    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = f". {rc}\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(link_home)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    declared_entries = [e for e in path_entries if e == str(bin_dir)]
    assert len(declared_entries) == 1


def test_two_managed_directories_maintain_order_under_bash(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    bin_dir_a = tmp_path / "a_bin"
    bin_dir_b = tmp_path / "b_bin"
    bin_dir_a.mkdir()
    bin_dir_b.mkdir()

    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir_a, bin_dir_b], rc)

    script = "\n".join([f". {rc}" for _ in range(3)]) + "\necho $PATH"
    result = subprocess.run(
        [bash_path, "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    a_indices = [i for i, e in enumerate(path_entries) if e == str(bin_dir_a)]
    b_indices = [i for i, e in enumerate(path_entries) if e == str(bin_dir_b)]
    assert len(a_indices) == 1
    assert len(b_indices) == 1
    assert b_indices[0] < a_indices[0]


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not on PATH")
def test_managed_block_is_runtime_idempotent_under_zsh(tmp_path: Path) -> None:
    zsh_path = shutil.which("zsh")
    if zsh_path is None:
        pytest.skip("zsh not available")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(5)]) + "\necho $PATH"
    result = subprocess.run(
        [zsh_path, "-f", "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    matching = [e for e in path_entries if e == str(bin_dir)]
    assert len(matching) == 1


def test_managed_block_is_runtime_idempotent_under_bin_sh(tmp_path: Path) -> None:
    sh_path = "/bin/sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], rc)

    script = "\n".join([f". {rc}" for _ in range(5)]) + "\necho $PATH"
    result = subprocess.run(
        [sh_path, "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    path_entries = result.stdout.strip().split(":")
    matching = [e for e in path_entries if e == str(bin_dir)]
    assert len(matching) == 1
