import ast
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from installer.atomic import OLD_SUFFIX, atomic_write_text, staged_sibling
from installer.model import Method, Tool
from installer.platform import Platform
from installer.rcclean import path_writer_lines
from installer.shellrc import (
    apply_block,
    classify_source_line,
    collect_bin_dirs,
    consolidate_shellrc,
    consolidation_refusal,
    ensure_source,
    guard_path_writers,
    has_managed_block,
    managed_block,
    path_export_guard,
    remove_managed_block,
    remove_source_block,
    sources_file,
    strip_block,
    write_myshellrc,
)

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")

_PLATFORM = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


class _ShellRun(NamedTuple):
    """One shell subprocess: what it echoed, and whether it exited cleanly."""

    stdout: str
    returncode: int


def _source_n_times(
    shell: str,
    rc: Path,
    *,
    times: int = 1,
    seed: str | None = "",
    home: Path | None = None,
    echo: str = "$PATH",
) -> _ShellRun:
    """Source an rc file N times in a subprocess and return what `echo` printed.

    shell: absolute path to shell binary
    rc: path to rc file to source
    times: number of times to source it
    seed: initial PATH value (empty string means empty PATH, None means no PATH key)
    home: HOME directory for the subprocess
    echo: the expression echoed after the sources; defaults to the resulting $PATH

    The 30s timeout is an ASSERTION, not a convenience: a consolidation that
    produced a self-sourcing file fails the suite here rather than hanging CI.
    """
    if home is None:
        home = Path("/tmp")
    script = f". {rc}\n" * times + f'echo "{echo}"'
    env = {"HOME": str(home)}
    if seed is not None:
        env["PATH"] = seed
    completed = subprocess.run(
        [shell, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return _ShellRun(completed.stdout.strip(), completed.returncode)


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


def test_write_myshellrc_migrates_an_old_plain_export_block_in_one_write(
    tmp_path: Path,
) -> None:
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "managed_bin"
    bin_dir.mkdir()

    old_block = "\n".join(
        [
            "# >>> tools-installer path >>>",
            f'export PATH="{bin_dir}:$PATH"',
            "# <<< tools-installer path <<<",
        ]
    )
    user_content_before = "export EDITOR=vim\n"
    user_content_after = "\nalias ll='ls -l'\n"

    rc.write_text(user_content_before + old_block + user_content_after)

    write_myshellrc([bin_dir], rc)
    text = rc.read_text()

    assert "export EDITOR=vim" in text
    assert "alias ll='ls -l'" in text
    assert text.count("# >>> tools-installer path >>>") == 1
    assert text.count("# <<< tools-installer path <<<") == 1
    block_content = text.split("# >>> tools-installer path >>>")[1].split(
        "# <<< tools-installer path <<<"
    )[0]
    assert path_export_guard(bin_dir) in block_content
    assert "case" in block_content


def test_write_myshellrc_is_idempotent_after_migration(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "managed_bin"
    bin_dir.mkdir()

    old_block = "\n".join(
        [
            "# >>> tools-installer path >>>",
            f'export PATH="{bin_dir}:$PATH"',
            "# <<< tools-installer path <<<",
        ]
    )
    rc.write_text("export EDITOR=vim\n" + old_block)

    write_myshellrc([bin_dir], rc)
    first = rc.read_text()

    write_myshellrc([bin_dir], rc)
    second = rc.read_text()

    assert first == second


def test_migrated_block_is_runtime_idempotent(tmp_path: Path) -> None:
    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "managed_bin"
    bin_dir.mkdir()

    old_block = "\n".join(
        [
            "# >>> tools-installer path >>>",
            f'export PATH="{bin_dir}:$PATH"',
            "# <<< tools-installer path <<<",
        ]
    )
    rc.write_text("export EDITOR=vim\n" + old_block)

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


def test_write_managed_path_emits_the_guarded_form(tmp_path: Path) -> None:
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".zshrc"
    bin_dir = tmp_path / "managed_bin"
    bin_dir.mkdir()

    write_managed_path(rc, [bin_dir])
    text = rc.read_text()

    assert "# >>> tools-installer path >>>" in text
    assert path_export_guard(bin_dir) in text


def test_write_managed_path_is_runtime_idempotent(tmp_path: Path) -> None:
    from installer.shellrc import write_managed_path

    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    rc = tmp_path / ".bashrc"
    bin_dir = tmp_path / "managed_bin"
    bin_dir.mkdir()

    write_managed_path(rc, [bin_dir])

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


class _Hit(NamedTuple):
    """A string-producing AST node that matched the accumulating PATH needle."""

    file_path: Path
    line_number: int
    enclosing_function: str | None
    is_docstring: bool
    reconstructed_text: str


def _reconstruct(node: ast.expr) -> str | None:
    """Reconstruct shell text from a string-producing expression node.

    Returns the shell text for: Constant (str), JoinedStr (f-string),
    BinOp with Add (concatenation). Everything else returns None.
    FormattedValues are replaced with a marker « » that preserves scanability.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append("«»")
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _reconstruct(node.left)
        right = _reconstruct(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    return None


def _accumulating_hits(files: list[Path]) -> list[_Hit]:
    """Scan Python files for accumulating PATH assignments.

    The needle targets assignments to PATH that reference the PATH variable
    through any parameter-expansion form: bare $PATH, ${PATH}, or any braced
    form with an operator (-, :-, +, :+, =, :=, ?, :?, #, ##, %, %%, //, /, ^^, ,,, @).
    """
    hits: list[_Hit] = []

    pattern = re.compile(
        r"(?:^|\s)(?:export\s+)?PATH="
        r"(?:.*?"
        r"(?:"
        r"\$PATH(?![A-Za-z0-9_])"
        r"|"
        r"\$\{PATH(?:[^A-Za-z0-9_]|$)"
        r")"
        r")"
    )

    for file_path in sorted(files):
        try:
            source = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            continue

        relative_path = file_path.relative_to(file_path.resolve().parent.parent)

        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        class Visitor(ast.NodeVisitor):
            def __init__(self, file_path: Path, parent_map: dict[ast.AST, ast.AST]):
                self.file_path = file_path
                # Bound explicitly rather than closed over: `parents` is rebuilt
                # per file inside the enclosing loop, and a closure would read
                # whichever map the loop happened to leave behind (ruff B023).
                self.parents = parent_map
                self.current_func: str | None = None
                self.current_func_node: (
                    ast.FunctionDef | ast.AsyncFunctionDef | ast.Module | None
                ) = None
                self.scoped_hits: list[_Hit] = []

            def visit_Module(self, node: ast.Module):
                old_func = self.current_func
                old_func_node = self.current_func_node
                self.current_func = None
                self.current_func_node = node
                self.generic_visit(node)
                self._check_scope_level_join(node)
                self.current_func = old_func
                self.current_func_node = old_func_node

            def visit_FunctionDef(self, node: ast.FunctionDef):
                old_func = self.current_func
                old_func_node = self.current_func_node
                self.current_func = node.name
                self.current_func_node = node
                self.generic_visit(node)
                self._check_scope_level_join(node)
                self.current_func = old_func
                self.current_func_node = old_func_node

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                old_func = self.current_func
                old_func_node = self.current_func_node
                self.current_func = node.name
                self.current_func_node = node
                self.generic_visit(node)
                self._check_scope_level_join(node)
                self.current_func = old_func
                self.current_func_node = old_func_node

            def _check_scope_level_join(self, scope_node: ast.AST) -> None:
                """Check scope-level join (all string nodes except docstring)."""
                parts: list[str] = []
                docstring_node = None
                if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                    if (
                        scope_node.body
                        and isinstance(scope_node.body[0], ast.Expr)
                        and isinstance(scope_node.body[0].value, ast.Constant)
                        and isinstance(scope_node.body[0].value.value, str)
                    ):
                        docstring_node = scope_node.body[0]

                    for stmt in scope_node.body:
                        if stmt is docstring_node:
                            continue
                        value = None
                        if isinstance(stmt, (ast.Expr, ast.Assign)) or (
                            isinstance(stmt, ast.Return) and stmt.value
                        ):
                            value = stmt.value
                        if value is not None:
                            rec = _reconstruct(value)
                            if rec:
                                parts.append(rec)

                    if parts:
                        joined = "".join(parts)
                        if pattern.search(joined):
                            self.scoped_hits.append(
                                _Hit(
                                    file_path=self.file_path,
                                    line_number=getattr(scope_node, "lineno", 0),
                                    enclosing_function=self.current_func,
                                    is_docstring=False,
                                    reconstructed_text=joined,
                                )
                            )

            def visit_Expr(self, node: ast.Expr):
                reconstructed = _reconstruct(node.value)
                if reconstructed and pattern.search(reconstructed):
                    is_doc = False
                    parent = self.parents.get(node)
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                        is_doc = bool(parent.body) and parent.body[0] is node

                    self.scoped_hits.append(
                        _Hit(
                            file_path=self.file_path,
                            line_number=(node.lineno if hasattr(node, "lineno") else 0),
                            enclosing_function=self.current_func,
                            is_docstring=is_doc,
                            reconstructed_text=reconstructed,
                        )
                    )
                self.generic_visit(node)

            def visit_Return(self, node: ast.Return):
                if node.value:
                    reconstructed = _reconstruct(node.value)
                    if reconstructed and pattern.search(reconstructed):
                        self.scoped_hits.append(
                            _Hit(
                                file_path=self.file_path,
                                line_number=(node.lineno if hasattr(node, "lineno") else 0),
                                enclosing_function=self.current_func,
                                is_docstring=False,
                                reconstructed_text=reconstructed,
                            )
                        )
                self.generic_visit(node)

        visitor = Visitor(relative_path, parents)
        visitor.visit(tree)
        hits.extend(visitor.scoped_hits)

    return hits


def test_no_accumulating_path_build_under_installer_or_setup() -> None:
    """Assert no plain PATH prepend in installer/ or setup.py outside one exemption.

    The accumulating PATH shape is: an assignment to PATH whose value
    references the PATH variable through ANY parameter-expansion spelling
    ($PATH, ${PATH}, ${PATH-}, ${PATH:-...}, ${PATH+...}, ${PATH:+...},
    ${PATH=...}, ${PATH:=...}, ${PATH?...}, ${PATH:?...}, ${PATH#...},
    ${PATH%...}, ${PATH//...}, etc.). This shape accumulates duplicates
    with every nested shell re-source, and is the defect this phase
    exists to kill.

    A TOTAL assignment (whose value does NOT reference $PATH) is idempotent
    by construction and cannot produce duplicates — that is not this defect.
    Such assignments are outside the needle by the shape's property.

    EXEMPTION (keyed to (relative_path, enclosing_function, is_docstring)):
    1. find_duplicate_path_lines() docstring in installer/rcclean.py — the
       documentation node that describes the old shape for reference and
       education. A non-docstring production expression anywhere in rcclean.py
       is a violation.

    There is deliberately NO exemption for path_export_guard() in
    installer/shellrc.py, even though that emitter is the one place allowed to
    build a guarded PATH line. The scan reports zero hits for it today (see the
    reconstruction-limit comment at the end of this function), so an exemption
    entry would match nothing while reading as though it were load-bearing —
    a blanket allowance covering whatever that function might later build. If a
    refactor of the emitter ever makes this test fail on path_export_guard,
    that failure is the correct outcome: re-adding the exemption is then a
    conscious decision with a live hit to point at.

    TOTAL ASSIGNMENTS OUTSIDE THE NEEDLE (reasoned exclusions, not allowlist):
    - installer/executors.py:31-38 — sh -c command prefix with complete
      shell_path() value, never re-sourced.
    - installer/systemd_daemon.py:253-265 — systemd unit Environment= line,
      total assignment, never re-sourced.

    Tests do NOT include tests/ because test fixtures legitimately construct
    the old shape for migration testing, and scanning them would turn this
    invariant into an obstacle to testing the migration it depends on.

    Liveness is carried by this module's seeded-violation tests
    (`test_scan_reports_*`), which require the scanner to flag a known-bad
    shape, and by the assertion at the end of this function that the one
    exemption really does match a node of the expected KIND. A needle narrowed
    until it matches nothing fails those, so this invariant cannot be kept
    green by gutting the scan.
    """
    repo_root = Path(__file__).resolve().parent.parent
    installer_py = list((repo_root / "installer").glob("**/*.py"))
    setup_py = [repo_root / "setup.py"]
    files = installer_py + setup_py

    hits = _accumulating_hits(files)

    exempted_triples = {
        (Path("installer/rcclean.py"), "find_duplicate_path_lines", True),
    }

    non_exempt = [
        h
        for h in hits
        if (h.file_path, h.enclosing_function, h.is_docstring) not in exempted_triples
    ]

    violation_lines = [
        f"{h.file_path}:{h.line_number} in {h.enclosing_function or 'module'}: "
        f"{h.reconstructed_text[:60]}"
        for h in non_exempt
    ]

    assert not non_exempt, (
        f"Found {len(non_exempt)} accumulating PATH assignment(s) outside "
        f"exemptions:\n" + "\n".join(violation_lines)
    )

    # Liveness is proven by the seeded-violation tests in this module
    # (test_scan_reports_*), which feed the scanner a known-bad shape and
    # require a hit. They are the positive control: a needle narrowed until it
    # matches nothing fails THEM, so this assertion cannot be kept green by
    # gutting the scanner.
    #
    # It deliberately does NOT assert a hit inside path_export_guard, and
    # carries no exemption for it either. The emitter assembles its assignment
    # through an intermediate local
    # (`value = f"{declared}${{PATH:+:$PATH}}"`, then `export PATH="{value}"`),
    # so no single reconstructed expression carries both the assignment head
    # and a `$PATH` reference, and the scan reports zero hits for that function
    # today. That is the documented reconstruction limit accepted in 15.8-03's
    # Review Dispositions Ledger (cycle-3 MEDIUM-03), not an emitter defect:
    # the runtime guarantee lives in the real-shell repeated-source tests in
    # this module and in tests/test_shell_scripts_path.py, which observe actual
    # PATH contents rather than source shape.
    #
    # An earlier revision asserted `has_guarded_implementation or
    # has_guarded_doc`, where the fallback was a substring check for
    # "case-guarded" in shellrc.py. That made the liveness half of this test
    # satisfiable by a comment, which is exactly the vacuity the assertion
    # existed to prevent. It is removed rather than weakened further: the
    # assertion that carries this test is `assert not non_exempt` above.

    # Every exemption must be live: an entry that matches no hit is a blanket
    # allowance dressed as a scoped one, and would let a future violation of
    # that exact shape land silently. Keyed on the node KIND (is_docstring), so
    # a docstring exemption cannot be satisfied by production code, nor the
    # reverse.
    matched_triples = {(h.file_path, h.enclosing_function, h.is_docstring) for h in hits}
    inert = exempted_triples - matched_triples
    assert not inert, (
        "Liveness check failed: exemption(s) matched no hit and are therefore "
        f"inert blanket allowances: {sorted(map(str, inert))}"
    )


def test_needle_matches_all_path_expansion_spellings() -> None:
    """Unit test the expansion pattern in isolation.

    Ensures the needle recognizes every PATH variable-reference spelling a
    shell accepts and does not false-positive on longer variable names.
    """
    pattern = re.compile(
        r"(?:^|\s)(?:export\s+)?PATH="
        r"(?:.*?"
        r"(?:"
        r"\$PATH(?![A-Za-z0-9_])"
        r"|"
        r"\$\{PATH(?:[^A-Za-z0-9_]|$)"
        r")"
        r")"
    )

    test_cases = [
        ('export PATH="/a:$PATH"', True),
        ('export PATH="/a:${PATH}"', True),
        ('export PATH="/a:${PATH-}"', True),
        ('export PATH="/a:${PATH:-x}"', True),
        ('export PATH="/a:${PATH+x}"', True),
        ('export PATH="/a:${PATH:+x}"', True),
        ('export PATH="/a:${PATH=x}"', True),
        ('export PATH="/a:${PATH:=x}"', True),
        ('export PATH="/a:${PATH?x}"', True),
        ('export PATH="/a:${PATH:?x}"', True),
        ('export PATH="/a:${PATH#x}"', True),
        ('export PATH="/a:${PATH##x}"', True),
        ('export PATH="/a:${PATH%x}"', True),
        ('export PATH="/a:${PATH%%x}"', True),
        ('export PATH="/a:${PATH//x/y}"', True),
        ('export PATH="/a:${PATH/x/y}"', True),
        ('export PATH="/a:${PATH^^}"', True),
        ('export PATH="/a:${PATH,,}"', True),
        ('export PATH="/a:${PATH@Q}"', True),
        ('export PATHOLOGICAL="/a:$PATHOLOGICAL"', False),
        ('export PATHOLOGICAL="/a:${PATHOLOGICAL}"', False),
    ]

    for text, should_match in test_cases:
        matches = bool(pattern.search(text))
        assert matches == should_match, (
            f"Pattern mismatch for: {text} (expected match={should_match})"
        )


def test_scan_reports_a_bare_prepend_near_an_unrelated_guard_opening(tmp_path: Path) -> None:
    """Prove the old two-line lookback exemption is gone.

    A module with an unrelated case-guard opening two lines before a bare
    prepend should still report the prepend as a violation, because the
    two-line proximity check is no longer part of the invariant.
    """
    module_code = """
def unrelated():
    return "case"

def bad():
    return 'export PATH="/x:$PATH"'
"""
    file_path = tmp_path / "bad_module.py"
    file_path.write_text(module_code)

    hits = _accumulating_hits([file_path])
    assert len(hits) > 0, "Expected at least one hit for the bare prepend"
    bad_hits = [h for h in hits if "export PATH" in h.reconstructed_text]
    assert bad_hits, "Expected to find the bare prepend line"


def test_scan_reports_a_shape_assembled_from_split_fragments(tmp_path: Path) -> None:
    """Prove the scope-level fragment join catches split construction.

    A function that assigns head and tail to different variables and
    concatenates them should still be reported, because the scan joins
    all string-producing nodes in a scope in source order.
    """
    module_code = """
def build_path():
    head = 'export PATH="/x'
    tail = ':$PATH"'
    result = head + tail
    return result
"""
    file_path = tmp_path / "split_module.py"
    file_path.write_text(module_code)

    hits = _accumulating_hits([file_path])
    assert len(hits) > 0, "Expected to find the split-fragment construction"


@pytest.mark.parametrize(
    "expansion",
    [
        "$PATH",
        "${PATH}",
        "${PATH-}",
        "${PATH:-x}",
        "${PATH+x}",
        "${PATH:+x}",
        "${PATH=x}",
        "${PATH:=x}",
        "${PATH?x}",
        "${PATH:?x}",
        "${PATH#x}",
        "${PATH##x}",
        "${PATH%x}",
        "${PATH%%x}",
        "${PATH//x/y}",
        "${PATH/x/y}",
        "${PATH^^}",
        "${PATH,,}",
        "${PATH@Q}",
    ],
)
def test_scan_reports_every_path_expansion_spelling(tmp_path: Path, expansion: str) -> None:
    """Prove every PATH expansion spelling is caught.

    Each spelling represents a different shell parameter-expansion form.
    The needle must recognize all of them, not just $PATH and ${PATH}.
    """
    module_code = f"""
def bad():
    return 'export PATH="/x:{expansion}"'
"""
    file_path = tmp_path / (
        f"expansion_"
        f"{expansion.replace('/', '_').replace('$', '_').replace('{', '_').replace('}', '_')}"
        f".py"
    )
    file_path.write_text(module_code)

    hits = _accumulating_hits([file_path])
    assert len(hits) > 0, f"Expected to find the expansion: {expansion}"


@pytest.mark.parametrize(
    "var_name",
    ["$PATHOLOGICAL", "${PATHOLOGICAL}"],
)
def test_scan_does_not_false_positive_on_longer_variable_names(
    tmp_path: Path, var_name: str
) -> None:
    """Prove longer variable names are not false positives.

    $PATHOLOGICAL and ${PATHOLOGICAL} are different variables from $PATH
    and must not trigger the needle.
    """
    module_code = f"""
def not_bad():
    return 'export PATHOLOGICAL="/x:{var_name}"'
"""
    file_path = tmp_path / (
        f"longer_{var_name.replace('/', '_').replace('$', '_').replace('{', '_').replace('}', '_')}"
        f".py"
    )
    file_path.write_text(module_code)

    hits = _accumulating_hits([file_path])
    path_like_hits = [
        h
        for h in hits
        if "PATHOLOGICAL" in h.reconstructed_text and "PATH=" in h.reconstructed_text
    ]
    assert not path_like_hits, f"False positive for {var_name}"


def test_scan_reports_a_production_expression_inside_rcclean(
    tmp_path: Path,
) -> None:
    """Prove the rcclean exemption is narrowed to the docstring node.

    A module NAMED rcclean.py with find_duplicate_path_lines() whose
    DOCSTRING contains the shape (must be exempt) and whose BODY returns it
    from a production expression (must be reported) tests both halves of the
    narrowed allowance in one fixture.
    """
    module_code = '''
def find_duplicate_path_lines():
    """This docstring describes the shape export PATH="/x:$PATH" for reference."""
    return 'export PATH="/x:$PATH"'
'''
    file_path = tmp_path / "rcclean.py"
    file_path.write_text(module_code)

    hits = _accumulating_hits([file_path])
    assert len(hits) >= 1, "Expected to find at least the production expression"
    production_hits = [
        h
        for h in hits
        if not h.is_docstring and h.enclosing_function == "find_duplicate_path_lines"
    ]
    assert production_hits, (
        "Expected the production expression (non-docstring) inside the function to be reported"
    )


def test_managed_block_output_contains_no_bare_assignment_line() -> None:
    """Assert managed_block() never emits a plain PATH assignment.

    The structural property: no line in managed_block() output starts with
    'PATH=' or 'export PATH=' (case-guard lines start with 'case').
    """
    block = managed_block([Path("/a/bin"), Path("/b/bin")])
    for line in block.splitlines():
        stripped = line.lstrip()
        assert not stripped.startswith("PATH="), f"Found plain PATH= in line: {line}"
        assert not stripped.startswith("export PATH="), f"Found plain export PATH= in line: {line}"


def test_a_failed_write_myshellrc_leaves_the_original_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write failure leaves original file untouched, no temp file left behind."""
    rc = tmp_path / ".myshellrc"
    original_bytes = b"# original content\n"
    rc.write_bytes(original_bytes)

    def raise_oserror(_self: Path, _data: bytes) -> int:
        raise OSError("no space left on device")

    monkeypatch.setattr("pathlib.Path.write_bytes", raise_oserror)

    with pytest.raises(OSError):
        write_myshellrc([tmp_path / "bin"], rc)

    assert rc.read_bytes() == original_bytes
    temp_files = list(tmp_path.glob("*.tools-installer.tmp"))
    assert len(temp_files) == 0, f"Temp files left behind: {temp_files}"


def test_a_failed_write_managed_path_leaves_the_original_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write failure in write_managed_path leaves original file untouched."""
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".zshrc"
    original_bytes = b"# original .zshrc\n"
    rc.write_bytes(original_bytes)

    def raise_oserror(_self: Path, _data: bytes) -> int:
        raise OSError("no space left on device")

    monkeypatch.setattr("pathlib.Path.write_bytes", raise_oserror)

    with pytest.raises(OSError):
        write_managed_path(rc, [tmp_path / "bin"])

    assert rc.read_bytes() == original_bytes
    temp_files = list(tmp_path.glob("*.tools-installer.tmp"))
    assert len(temp_files) == 0


def test_a_failed_ensure_source_leaves_the_original_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write failure in ensure_source leaves original file untouched."""
    rc = tmp_path / ".bashrc"
    original_bytes = b"# original .bashrc\n"
    rc.write_bytes(original_bytes)

    myshellrc = tmp_path / ".myshellrc"

    def raise_oserror(_self: Path, _data: bytes) -> int:
        raise OSError("no space left on device")

    monkeypatch.setattr("pathlib.Path.write_bytes", raise_oserror)

    with pytest.raises(OSError):
        ensure_source(rc, myshellrc)

    assert rc.read_bytes() == original_bytes
    temp_files = list(tmp_path.glob("*.tools-installer.tmp"))
    assert len(temp_files) == 0


def test_a_failed_remove_managed_block_leaves_the_original_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write failure in remove_managed_block leaves original file untouched."""
    rc = tmp_path / ".myshellrc"
    original_content = (
        "# user content\n# >>> tools-installer path >>>\nX\n# <<< tools-installer path <<<"
    )
    original_bytes = original_content.encode("utf-8")
    rc.write_bytes(original_bytes)

    def raise_oserror(_self: Path, _data: bytes) -> int:
        raise OSError("no space left on device")

    monkeypatch.setattr("pathlib.Path.write_bytes", raise_oserror)

    with pytest.raises(OSError):
        remove_managed_block(rc)

    assert rc.read_bytes() == original_bytes
    temp_files = list(tmp_path.glob("*.tools-installer.tmp"))
    assert len(temp_files) == 0


def test_the_converted_writers_preserve_a_symlinked_rc_file(tmp_path: Path) -> None:
    """Symlinked rc file survives as a symlink with its target updated."""
    real_file = tmp_path / "real_zshrc"
    real_file.write_text("# original\n")

    link = tmp_path / ".zshrc"
    link.symlink_to(real_file)

    ensure_source(link, tmp_path / ".myshellrc")

    assert link.is_symlink(), ".zshrc should still be a symlink"
    assert link.resolve() == real_file, "symlink target should be preserved"
    content = real_file.read_text()
    assert "tools-installer source" in content


def test_write_myshellrc_creates_missing_file(tmp_path: Path) -> None:
    """write_myshellrc creates file when it does not exist."""
    rc = tmp_path / ".myshellrc"
    assert not rc.exists()

    write_myshellrc([tmp_path / "bin"], rc)

    assert rc.exists()
    assert "tools-installer path" in rc.read_text()


def test_write_managed_path_creates_missing_file(tmp_path: Path) -> None:
    """write_managed_path creates file when it does not exist."""
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".zshrc"
    assert not rc.exists()

    write_managed_path(rc, [tmp_path / "bin"])

    assert rc.exists()
    assert "tools-installer path" in rc.read_text()


def test_ensure_source_creates_missing_file(tmp_path: Path) -> None:
    """ensure_source creates file when it does not exist."""
    rc = tmp_path / ".bashrc"
    assert not rc.exists()

    myshellrc = tmp_path / ".myshellrc"
    ensure_source(rc, myshellrc)

    assert rc.exists()
    assert "tools-installer source" in rc.read_text()


def _seed_consolidable_home(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Seed a tmp HOME with a generic ~/.shellrc and this project's ~/.myshellrc.

    Returns (shellrc, myshellrc, managed_bin).
    """
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text(
        "alias gs='git status'\nexport EDITOR=vim\n__SHELLRC_RUNS=$((${__SHELLRC_RUNS:-0}+1))\n"
    )
    return shellrc, myshellrc, managed_bin


def _backup_path(shellrc: Path) -> Path:
    return staged_sibling(shellrc, OLD_SUFFIX)


def _no_backup_anywhere(root: Path) -> bool:
    return not list(root.glob(f"*{OLD_SUFFIX}"))


@pytest.mark.parametrize(
    "line",
    [
        ". {target}",
        "source {target}",
        ". $HOME/.myshellrc",
        ". ${HOME}/.myshellrc",
        ". ~/.myshellrc",
        '. "$HOME/.myshellrc"',
        "  source {target}   ",
    ],
)
def test_source_classifier_marks_only_simple_target_lines_rewritable(
    tmp_path: Path, line: str
) -> None:
    target = tmp_path / ".myshellrc"
    assert (
        classify_source_line(line.replace("{target}", str(target)), target).verdict == "rewritable"
    )


@pytest.mark.parametrize(
    "line",
    [
        'export A=1; . "$HOME/.myshellrc"; export B=1',
        '[ -f "$HOME/.myshellrc" ] && . "$HOME/.myshellrc"',
        'if . "$HOME/.myshellrc"; then',
        '! source "$HOME/.myshellrc"',
        '. "$HOME/.myshellrc" \\',
        '. "$target"',
        '. "$HOME"/.myshellrc',
        'FOO=bar . "$HOME/.myshellrc"',
        '*) . "$HOME/.myshellrc" ;;',
        'root=$HOME; . "$root/.myshellrc"',
        'command source "$HOME/.myshellrc"',
        'builtin source "$HOME/.myshellrc"',
        'command . "$HOME/.myshellrc"',
        r'sour\ce "$HOME/.myshellrc"',
        "'source' \"$HOME/.myshellrc\"",
        'command -p source "$HOME/.myshellrc"',
        'cmd=source; $cmd "$HOME/.myshellrc"',
    ],
)
def test_source_classifier_marks_every_ambiguous_target_line(tmp_path: Path, line: str) -> None:
    target = tmp_path / ".myshellrc"
    inspection = classify_source_line(line, target)
    assert inspection.verdict == "ambiguous", line
    if line in {'. "$target"', 'root=$HOME; . "$root/.myshellrc"'}:
        assert inspection.has_unresolvable_source is True, line
    else:
        assert inspection.resolves_to_target is True, line


@pytest.mark.parametrize(
    "line",
    [
        "# source $HOME/.myshellrc",
        'export MYSHELLRC="$HOME/.myshellrc"',
        'echo "$HOME/.myshellrc"',
        '. "$HOME/.other.myshellrc"',
        '. "$HOME/.shellrc"',
        '. "$HOME/.cargo/env"',
        '$EDITOR "$HOME/.bashrc"',
        'command ls "$HOME"',
    ],
)
def test_source_classifier_does_not_overdetect_unrelated_lines(tmp_path: Path, line: str) -> None:
    target = tmp_path / ".myshellrc"
    assert classify_source_line(line, target).verdict == "none", line


def test_source_classifier_compares_real_paths_for_aliased_literal(tmp_path: Path) -> None:
    real_home = tmp_path / "var" / "home" / "u"
    real_home.mkdir(parents=True)
    aliased_home = tmp_path / "home" / "u"
    aliased_home.parent.mkdir()
    aliased_home.symlink_to(real_home)
    target = aliased_home / ".myshellrc"

    inspection = classify_source_line(f'. "{real_home}/.myshellrc"', target)

    assert inspection.verdict in {"rewritable", "ambiguous"}
    assert inspection.resolves_to_target is True


def _assert_content_refusal(
    tmp_path: Path,
    shellrc_text: str,
    *,
    expected_line: int = 1,
) -> None:
    shellrc = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    shellrc.write_text(shellrc_text)
    myshellrc.write_text("# owned content\n")
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert str(shellrc) in result.reason
    assert f"line {expected_line}" in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


@pytest.mark.parametrize(
    "text",
    [
        'cat <<EOF\n. "$HOME/.myshellrc"\nEOF\n',
        "cat <<-EOF\nunrelated body\nEOF\n",
        'cat <<"EOF"\nunrelated body\nEOF\n',
        "cat <<'EOF'\nunrelated body\nEOF\n",
        'eval "$(brew shellenv)"\n',
    ],
)
def test_file_level_unknown_shell_constructs_refuse_without_writing(
    tmp_path: Path, text: str
) -> None:
    _assert_content_refusal(tmp_path, text)


def test_refusal_reports_a_tools_installer_marker_without_writing(tmp_path: Path) -> None:
    _assert_content_refusal(tmp_path, "# >>> tools-installer path >>>\n")


def test_refusal_reports_a_preexisting_source_loop_without_writing(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    shellrc.write_text("export KEEP=1\n")
    myshellrc.write_text(f'. "{shellrc}"\n')
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert str(myshellrc) in result.reason
    assert "loop" in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_consolidation_refusal_is_pure_and_reports_the_offending_line(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"

    reason = consolidation_refusal(
        'export KEEP=1\n. "$target"\n',
        "# owned\n",
        shellrc_path=shellrc,
        myshellrc_path=myshellrc,
    )

    assert reason is not None
    assert str(shellrc) in reason
    assert "line 2" in reason


def test_refuses_when_shellrc_is_a_symlink_to_myshellrc(tmp_path: Path) -> None:
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("export EDITOR=vim\n")
    shellrc = tmp_path / ".shellrc"
    shellrc.symlink_to(myshellrc)

    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and "symlink" in result.reason
    assert myshellrc.read_bytes() == before_myshellrc
    assert shellrc.is_symlink()
    assert shellrc.resolve() == myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_refuses_when_myshellrc_is_a_symlink_to_shellrc(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text("alias gs='git status'\n")
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.symlink_to(shellrc)

    before_shellrc = shellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and "symlink" in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.is_symlink()
    assert myshellrc.resolve() == shellrc
    assert _no_backup_anywhere(tmp_path)


def test_refuses_when_shellrc_is_a_symlink_to_an_unrelated_file(tmp_path: Path) -> None:
    dots = tmp_path / "dots"
    dots.mkdir()
    real = dots / "shellrc"
    real.write_text("alias gs='git status'\n")

    shellrc = tmp_path / ".shellrc"
    shellrc.symlink_to(real)
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("# mine\n")

    before_real = real.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and "symlink" in result.reason
    assert real.read_bytes() == before_real
    assert myshellrc.read_bytes() == before_myshellrc
    assert shellrc.is_symlink()
    assert _no_backup_anywhere(tmp_path)


def test_refuses_a_non_utf8_shellrc_without_writing_anything(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    shellrc.write_bytes(b"alias x=1\n\xff\xfe not utf-8\n")
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("# mine\n")

    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert ".shellrc" in result.reason
    assert "UTF-8" in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_consolidation_end_to_end_leaves_one_canonical_file(tmp_path: Path) -> None:
    shellrc, myshellrc, managed_bin = _seed_consolidable_home(tmp_path)
    original_bytes = shellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "consolidated"

    merged = myshellrc.read_text()
    assert merged.count("# >>> tools-installer path >>>") == 1
    assert merged.count("# >>> tools-installer consolidated shellrc >>>") == 1
    assert "alias gs='git status'" in merged
    assert "export EDITOR=vim" in merged
    assert "__SHELLRC_RUNS=" in merged

    stub = shellrc.read_text()
    assert "# >>> tools-installer shellrc stub >>>" in stub
    assert f'[ -f "{myshellrc}" ] && . "{myshellrc}"' in stub
    assert "alias gs='git status'" not in stub

    backup = _backup_path(shellrc)
    assert backup.exists()
    assert backup.read_bytes() == original_bytes

    bash_path = shutil.which("bash")
    if bash_path is None:
        pytest.skip("bash not available")

    script = "\n".join(
        [
            ". $HOME/.shellrc",
            ". $HOME/.shellrc",
            "echo $PATH",
            "echo $EDITOR",
            "echo $__SHELLRC_RUNS",
        ]
    )
    proc = subprocess.run(
        [bash_path, "--noprofile", "--norc", "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert proc.returncode == 0
    out_lines = proc.stdout.splitlines()
    path_entries = out_lines[0].split(":")
    assert path_entries.count(str(managed_bin)) == 1
    assert out_lines[1] == "vim"
    assert out_lines[2] == "2"


# The backup is not a convenience artifact: it is the executable form of D-04's
# `Reversibility: reversible` line. Every rule below -- raw bytes, no-clobber
# creation, refuse on mismatch, resume on match, never deleted -- exists because
# some specific way of getting it wrong made that line untrue.


def test_the_original_shellrc_is_recoverable_from_the_backup(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    os.chmod(shellrc, 0o600)
    original_bytes = shellrc.read_bytes()
    original_mode = stat.S_IMODE(shellrc.stat().st_mode)

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    backup = _backup_path(shellrc)
    os.replace(backup, shellrc)

    assert shellrc.read_bytes() == original_bytes
    assert stat.S_IMODE(shellrc.stat().st_mode) == original_mode


def test_a_crlf_original_is_backed_up_byte_for_byte(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    raw = b"alias gs='git status'\r\nexport EDITOR=vim\r\nno-trailing-newline"
    shellrc.write_bytes(raw)
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("# mine\n")

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    backup = _backup_path(shellrc)
    assert backup.read_bytes() == raw
    assert b"\r\n" in backup.read_bytes()


def test_a_stale_backup_refuses_the_whole_consolidation(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    backup = _backup_path(shellrc)
    backup.write_bytes(b"# some other tool's file\n")

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and str(backup) in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert backup.read_bytes() == b"# some other tool's file\n"


def test_a_matching_backup_is_treated_as_a_resumed_run(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    os.chmod(shellrc, 0o600)
    mode = stat.S_IMODE(shellrc.stat().st_mode)
    original_bytes = shellrc.read_bytes()

    backup = _backup_path(shellrc)
    backup.write_bytes(original_bytes)
    os.chmod(backup, mode)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "consolidated"
    assert "# >>> tools-installer shellrc stub >>>" in shellrc.read_text()
    assert myshellrc.read_text().count("# >>> tools-installer consolidated shellrc >>>") == 1
    assert backup.read_bytes() == original_bytes


def test_a_symlinked_backup_refuses_even_though_its_bytes_match(tmp_path: Path) -> None:
    # Accepted as a resumed run, this backup would resolve to the stub the moment
    # the stub was written, the original bytes would be gone, and the promised
    # `mv` would point a link at itself.
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    backup = _backup_path(shellrc)
    backup.symlink_to(shellrc)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and str(backup) in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert "# >>> tools-installer shellrc stub >>>" not in shellrc.read_text()
    assert myshellrc.read_bytes() == before_myshellrc
    assert backup.is_symlink()
    assert backup.resolve() == shellrc


def test_a_backup_with_matching_bytes_but_a_different_mode_refuses(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    os.chmod(shellrc, 0o600)
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    backup = _backup_path(shellrc)
    backup.write_bytes(shellrc.read_bytes())
    os.chmod(backup, 0o644)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert "600" in result.reason and "644" in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc


def test_a_backup_that_is_a_directory_refuses(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    backup = _backup_path(shellrc)
    backup.mkdir()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and str(backup) in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert backup.is_dir()


def test_a_second_migration_with_changed_content_refuses_rather_than_reconsolidating(
    tmp_path: Path,
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    backup = _backup_path(shellrc)
    backup_before = backup.read_bytes()
    shellrc.write_text("# new content a user restored by hand\n")
    myshellrc_before = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and str(backup) in result.reason
    assert shellrc.read_text() == "# new content a user restored by hand\n"
    assert myshellrc.read_bytes() == myshellrc_before
    assert backup.read_bytes() == backup_before


def test_consolidation_is_idempotent(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"
    shellrc_after = shellrc.read_bytes()
    myshellrc_after = myshellrc.read_bytes()
    backup_after = _backup_path(shellrc).read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "already"
    assert shellrc.read_bytes() == shellrc_after
    assert myshellrc.read_bytes() == myshellrc_after
    assert _backup_path(shellrc).read_bytes() == backup_after


def test_a_second_consecutive_run_returns_already_and_writes_nothing(tmp_path: Path) -> None:
    # After a successful run the backup holds the ORIGINAL while ~/.shellrc holds
    # the STUB, so they are SUPPOSED to differ. An implementation that validates
    # the backup before recognizing its own stub reads that expected difference as
    # a stale backup and returns `refused` on this and every later run, so plan
    # 15.8-06 would add a second direct route to ~/.myshellrc each time.
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    backup = _backup_path(shellrc)
    paths = (shellrc, myshellrc, backup)
    captured = {
        path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths
    }

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "already"
    for path in paths:
        data, ino, mtime = captured[path]
        assert path.read_bytes() == data
        assert path.stat().st_ino == ino
        assert path.stat().st_mtime_ns == mtime


def test_absent_shellrc_is_a_no_op(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("# mine\n")
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "absent"
    assert not shellrc.exists()
    assert not _backup_path(shellrc).exists()
    assert myshellrc.read_bytes() == before_myshellrc


def test_absent_shellrc_and_absent_myshellrc_is_a_no_op(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "absent"
    assert not shellrc.exists()
    assert not myshellrc.exists()


def test_a_dangling_shellrc_symlink_is_absent_not_refused(tmp_path: Path) -> None:
    shellrc = tmp_path / ".shellrc"
    shellrc.symlink_to(tmp_path / "does-not-exist")
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("# mine\n")
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "absent"
    assert not _backup_path(shellrc).exists()
    assert myshellrc.read_bytes() == before_myshellrc


def _inject_edit_on_first_write(
    monkeypatch: pytest.MonkeyPatch,
    shellrc: Path,
    edit: Callable[[], None],
) -> None:
    """Wrap atomic_write_text so the FIRST call also mutates ~/.shellrc.

    The first call is the copy-forward into ~/.myshellrc; the edit therefore
    lands after the snapshot read and before the stub write.
    """
    real = atomic_write_text
    state = {"fired": False}

    def wrapper(path: Path, text: str, *, mode: int | None = None) -> None:
        real(path, text, mode=mode)
        if not state["fired"] and path != shellrc:
            state["fired"] = True
            edit()

    monkeypatch.setattr("installer.shellrc.atomic_write_text", wrapper)


def test_a_concurrent_edit_between_the_read_and_the_stub_write_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    before_myshellrc = myshellrc.read_bytes()

    def edit() -> None:
        shellrc.write_bytes(b"# concurrently edited\n")

    _inject_edit_on_first_write(monkeypatch, shellrc, edit)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert str(shellrc) in result.reason
    assert "changed" in result.reason
    assert shellrc.read_bytes() == b"# concurrently edited\n"
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_a_concurrent_replacement_of_the_file_refuses_even_with_identical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    before_bytes = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    def edit() -> None:
        shellrc.unlink()
        shellrc.write_bytes(before_bytes)

    _inject_edit_on_first_write(monkeypatch, shellrc, edit)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None and "changed" in result.reason
    assert shellrc.read_bytes() == before_bytes
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_a_concurrent_edit_leaves_a_previously_existing_backup_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    os.chmod(shellrc, 0o600)
    mode = stat.S_IMODE(shellrc.stat().st_mode)
    backup = _backup_path(shellrc)
    backup.write_bytes(shellrc.read_bytes())
    os.chmod(backup, mode)
    backup_before = backup.read_bytes()

    def edit() -> None:
        shellrc.write_bytes(b"# concurrently edited\n")

    _inject_edit_on_first_write(monkeypatch, shellrc, edit)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert backup.exists()
    assert backup.read_bytes() == backup_before


def test_a_concurrent_edit_restores_an_absent_myshellrc_by_removing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text("alias gs='git status'\n")
    myshellrc = tmp_path / ".myshellrc"
    assert not myshellrc.exists()

    def edit() -> None:
        shellrc.write_bytes(b"# concurrently edited\n")

    _inject_edit_on_first_write(monkeypatch, shellrc, edit)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert not myshellrc.exists()
    assert _no_backup_anywhere(tmp_path)


def test_the_happy_path_still_writes_the_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    calls = {"n": 0}
    real = atomic_write_text

    def counting(path: Path, text: str, *, mode: int | None = None) -> None:
        calls["n"] += 1
        real(path, text, mode=mode)

    monkeypatch.setattr("installer.shellrc.atomic_write_text", counting)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "consolidated"
    assert "# >>> tools-installer shellrc stub >>>" in shellrc.read_text()
    assert calls["n"] >= 2


def test_refuses_when_shellrc_and_myshellrc_are_the_same_file(tmp_path: Path) -> None:
    real = tmp_path / "one_file"
    real.write_text("alias gs='git status'\n")
    shellrc = tmp_path / ".shellrc"
    os.link(real, shellrc)
    myshellrc = tmp_path / ".myshellrc"
    os.link(real, myshellrc)
    before = real.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert "one file" in result.reason
    assert real.read_bytes() == before
    assert _no_backup_anywhere(tmp_path)


def test_refuses_when_the_samefile_comparison_cannot_be_answered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)

    def raise_oserror(_self: Path, _other: Path) -> bool:
        raise OSError("cannot compare")

    monkeypatch.setattr("pathlib.Path.samefile", raise_oserror)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert "could not be compared" in result.reason


def test_refuses_when_the_snapshot_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    before_myshellrc = myshellrc.read_bytes()

    def raise_oserror(_path: Path) -> object:
        raise OSError("vanished")

    monkeypatch.setattr("installer.shellrc._snapshot", raise_oserror)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


# --- Task 2: the narrow rewriter and the two helpers plan 15.8-06 consumes ---


_PROVENANCE_LINES = 2


def _consolidated_span(myshellrc: Path) -> list[str]:
    """The copied-forward body inside ~/.myshellrc, without the provenance header.

    `consolidation_block` emits BEGIN, two provenance comments, the body, END;
    the body is what these tests assert on.
    """
    lines = myshellrc.read_text().split("\n")
    start = lines.index("# >>> tools-installer consolidated shellrc >>>")
    stop = lines.index("# <<< tools-installer consolidated shellrc <<<")
    return lines[start + 1 + _PROVENANCE_LINES : stop]


def test_a_simple_line_sourcing_myshellrc_is_disabled_not_deleted(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    original_line = '. "$HOME/.myshellrc"'
    shellrc.write_text(f"export KEEP=1\n{original_line}\nexport TAIL=2\n")

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "consolidated"
    span = _consolidated_span(myshellrc)
    disabled = [line for line in span if original_line in line]
    assert len(disabled) == 1
    # The original text survives verbatim, on a comment that says why.
    assert disabled[0].lstrip().startswith("#")
    assert disabled[0].endswith(original_line)
    assert str(myshellrc) in disabled[0]
    # And no LIVE source of the target is left behind in the copied content.
    assert all(
        classify_source_line(line, myshellrc).verdict == "none"
        for line in span
        if not line.lstrip().startswith("#")
    )


def test_the_rewritten_body_changes_nothing_else(tmp_path: Path) -> None:
    shellrc, myshellrc, _managed_bin = _seed_consolidable_home(tmp_path)
    original_lines = [
        "export KEEP=1   ",
        "",
        "alias gs='git status'",
        '. "$HOME/.myshellrc"',
        "\texport INDENTED=1",
        "# a comment",
    ]
    shellrc.write_text("\n".join(original_lines) + "\n")

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    span = _consolidated_span(myshellrc)
    # `consolidation_block` splits a trailing-newline body, so the final "" is
    # the text's terminator, not an added line.
    expected = [*original_lines, ""]
    assert len(span) == len(expected)
    rewritten_index = 3
    for index, (before, after) in enumerate(zip(expected, span, strict=True)):
        if index == rewritten_index:
            assert after != before
            assert after.endswith(before)
        else:
            assert after == before


@pytest.mark.parametrize(
    "line",
    [
        '. "$HOME/.myshellrc"',
        ". ~/.myshellrc",
        "source ~/.myshellrc",
        "sour\\ce ~/.myshellrc",
        "command source ~/.myshellrc",
        "builtin source ~/.myshellrc",
        "true && . ~/.myshellrc",
        "FOO=bar . ~/.myshellrc",
        'if . "$HOME/.myshellrc"; then :; fi',
        '. "$HOME"/.myshellrc',
    ],
)
def test_sources_file_is_broader_than_the_rewriter(tmp_path: Path, line: str) -> None:
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")
    # Every rewritable AND every path-resolving ambiguous shape answers yes.
    assert classify_source_line(line, target).verdict in {"rewritable", "ambiguous"}
    assert sources_file(f"{line}\n", target) == "yes"


@pytest.mark.parametrize(
    "line",
    [
        "# . ~/.myshellrc",
        ". ~/.other",
        'export PATH="$HOME/bin:$PATH"',
        "alias ll='ls -la'",
    ],
)
def test_sources_file_answers_no_for_every_none_shape(tmp_path: Path, line: str) -> None:
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")
    assert classify_source_line(line, target).verdict == "none"
    assert sources_file(f"{line}\n", target) == "no"


@pytest.mark.parametrize(
    "text",
    ['. "$ZDOTDIR/foo"\n', 'eval "$(brew shellenv)"\n', 'source "$SOME_DIR/rc"\n'],
)
def test_sources_file_reports_unprovable_for_a_non_static_source_argument(
    tmp_path: Path, text: str
) -> None:
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")
    assert sources_file(text, target) == "unprovable"


def test_sources_file_is_not_unprovable_for_an_ordinary_rc_file(tmp_path: Path) -> None:
    """The third answer must not swallow every real user.

    If `unprovable` were the common answer, plan 15.8-06 would stop wiring PATH
    for most people, so a realistic .bashrc whose sources all resolve statically
    has to answer plainly `no`.
    """
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")
    bashrc = "\n".join(
        [
            "# .bashrc",
            '[ -z "$PS1" ] && return',
            "export EDITOR=vim",
            'export PATH="$HOME/.local/bin:$PATH"',
            "alias ll='ls -la'",
            "[ -f ~/.bash_aliases ] && . ~/.bash_aliases",
            ". /etc/profile.d/bash_completion.sh",
            'if [ -f "$HOME/.cargo/env" ]; then . "$HOME/.cargo/env"; fi',
        ]
    )

    assert sources_file(bashrc + "\n", target) == "no"


def test_sources_file_matches_an_aliased_spelling(tmp_path: Path) -> None:
    real_home = tmp_path / "var" / "home" / "u"
    real_home.mkdir(parents=True)
    target_real = real_home / ".shellrc"
    target_real.write_text("x\n")
    alias_root = tmp_path / "home"
    alias_root.symlink_to(tmp_path / "var" / "home")
    target_alias = alias_root / "u" / ".shellrc"
    assert target_alias.exists()

    # Sourced under one spelling, asked about under the other.
    assert sources_file(f'. "{target_real}"\n', target_alias) == "yes"
    assert sources_file(f'. "{target_alias}"\n', target_real) == "yes"


def test_remove_source_block_strips_only_our_own_block(tmp_path: Path) -> None:
    rc = tmp_path / ".bashrc"
    myshellrc = tmp_path / ".myshellrc"
    head = "export KEEP=1\nalias ll='ls -la'\n"
    tail = "export TAIL=2\n"
    rc.write_text(head)
    ensure_source(rc, myshellrc)
    rc.write_text(rc.read_text() + tail)
    assert "# >>> tools-installer source >>>" in rc.read_text()

    remove_source_block(rc)

    after = rc.read_text()
    assert "tools-installer source" not in after
    assert head in after
    assert tail in after


def test_remove_source_block_is_a_no_op_without_the_block(tmp_path: Path) -> None:
    rc = tmp_path / ".bashrc"
    rc.write_text("export KEEP=1\n")
    before = rc.read_bytes()

    remove_source_block(rc)

    assert rc.read_bytes() == before


def test_remove_source_block_is_a_no_op_on_a_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope"

    remove_source_block(missing)

    assert not missing.exists()


def test_a_failed_remove_source_block_leaves_the_original_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = tmp_path / ".bashrc"
    myshellrc = tmp_path / ".myshellrc"
    rc.write_text("export KEEP=1\n")
    ensure_source(rc, myshellrc)
    before = rc.read_bytes()

    def raise_oserror(_self: Path, _data: bytes) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_bytes", raise_oserror)

    with pytest.raises(OSError, match="disk full"):
        remove_source_block(rc)

    assert rc.read_bytes() == before
    assert not list(tmp_path.glob("*.tools-installer.tmp"))


# --- Task 3: real shells prove the loop cannot come back ---
#
# These tests establish the consolidation MECHANISM against synthetic fixtures
# built under tmp_path. They do NOT reproduce the real-world case: no ~/.shellrc
# exists on this host, which is why 15.8-CONTEXT.md D-04 and research A1 both
# mark that case [ASSUMED]. A fabricated HOME is the honest substitute, and the
# timeout inside `_source_n_times` is what turns "it should not loop" into a
# failure rather than a hang.

_BASH = shutil.which("bash")
_ZSH = shutil.which("zsh")


def _managed_dir_count(path_value: str, managed_bin: Path) -> int:
    return [Path(entry) for entry in path_value.split(":")].count(managed_bin)


def _seed_self_sourcing_home(tmp_path: Path, line: str) -> tuple[Path, Path, Path]:
    """A HOME whose ~/.shellrc sources ~/.myshellrc via `line`."""
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text(f"export FROM_SHELLRC=yes\n{line}\n")
    return shellrc, myshellrc, managed_bin


@pytest.mark.parametrize("shell", [_BASH, _ZSH], ids=["bash", "zsh"])
def test_consolidated_files_source_without_looping_when_the_original_sourced_myshellrc(
    tmp_path: Path, shell: str | None
) -> None:
    if shell is None:
        pytest.skip("shell not on PATH")
    shellrc, myshellrc, managed_bin = _seed_self_sourcing_home(tmp_path, '. "$HOME/.myshellrc"')

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    run = _source_n_times(shell, shellrc, times=2, home=tmp_path, echo="$FROM_SHELLRC $PATH")
    assert run.returncode == 0
    assert run.stdout.startswith("yes ")
    assert _managed_dir_count(run.stdout.split(" ", 1)[1], managed_bin) == 1


def test_sourcing_myshellrc_directly_after_consolidation_is_also_safe(tmp_path: Path) -> None:
    """Both entry points must be safe; a machine may source either."""
    if _BASH is None:
        pytest.skip("bash not on PATH")
    shellrc, myshellrc, managed_bin = _seed_self_sourcing_home(tmp_path, '. "$HOME/.myshellrc"')

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    run = _source_n_times(_BASH, myshellrc, times=2, home=tmp_path)
    assert run.returncode == 0
    assert _managed_dir_count(run.stdout, managed_bin) == 1


def test_an_ambiguous_source_line_never_reaches_a_shell(tmp_path: Path) -> None:
    """A refusal must leave the user with a WORKING file, not a broken one."""
    if _BASH is None:
        pytest.skip("bash not on PATH")
    shellrc, myshellrc, _managed_bin = _seed_self_sourcing_home(
        tmp_path, 'if . "$HOME/.myshellrc"; then :; fi'
    )
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    run = _source_n_times(_BASH, shellrc, times=2, home=tmp_path, echo="$FROM_SHELLRC")
    assert run.returncode == 0
    assert run.stdout == "yes"


# Bash only, deliberately. zsh's `command` does not run builtins, so
# `command source` and `command . ` are ERRORS there rather than sources. That a
# line's danger depends on which shell the user runs is a reason to keep
# refusing these everywhere, NOT a reason to weaken the detector -- adding a zsh
# arm here produces a failing test and then a wrong fix. The `sour\ce` form does
# execute under zsh and carries its own arm below.
@pytest.mark.parametrize(
    "form",
    [
        "command source {path}",
        "builtin source {path}",
        "sour\\ce {path}",
        "command . {path}",
        "'source' {path}",
        '"source" {path}',
        "cmd=source; $cmd {path}",
    ],
)
def test_wrapped_and_escaped_source_forms_really_execute_and_are_refused(
    tmp_path: Path, form: str
) -> None:
    if _BASH is None:
        pytest.skip("bash not on PATH")

    # 1. Prove the form really executes the file it names.
    marker = tmp_path / "marker.sh"
    marker.write_text("MARKER_RAN=1\n")
    script = form.format(path=marker) + '\necho "MARKER=${MARKER_RAN-}"'
    executed = subprocess.run(
        [_BASH, "--noprofile", "--norc", "-c", script],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert "MARKER=1" in executed.stdout, (
        f"{form!r} did not source the file; investigate the shell, never delete the detection"
    )

    # 2. Prove consolidation refuses that same form, byte for byte.
    shellrc, myshellrc, _managed_bin = _seed_self_sourcing_home(
        tmp_path, form.format(path='"$HOME/.myshellrc"')
    )
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert str(shellrc) in result.reason
    assert "line" in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_a_backslash_escaped_source_form_executes_under_zsh_too(tmp_path: Path) -> None:
    if _ZSH is None:
        pytest.skip("zsh not on PATH")
    marker = tmp_path / "marker.sh"
    marker.write_text("MARKER_RAN=1\n")

    executed = subprocess.run(
        [_ZSH, "-f", "-c", f'sour\\ce {marker}\necho "MARKER=${{MARKER_RAN-}}"'],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert "MARKER=1" in executed.stdout


# This phase's documented RESIDUAL, stated as an assertion so a later phase
# changing it must change a test rather than drift into or out of the behavior.
# D-04 promises the user's own lines are copied forward VERBATIM, so a foreign
# plain PATH export keeps its original accumulating behavior. Note the division
# of labour: this test double-sources the stub IN ONE SHELL deliberately. Plan
# 15.8-06 is what keeps a NORMAL shell startup from reaching ~/.myshellrc twice
# in the first place -- without that note the "appears twice" assertion below
# reads like nobody noticed.
def test_a_carried_forward_foreign_path_export_keeps_its_original_behavior(
    tmp_path: Path,
) -> None:
    if _BASH is None:
        pytest.skip("bash not on PATH")
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    foreign_bin = tmp_path / "foreign_bin"
    foreign_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text(f'export PATH="{foreign_bin}:$PATH"\n')

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    once = _source_n_times(_BASH, shellrc, times=1, home=tmp_path)
    assert once.returncode == 0
    assert _managed_dir_count(once.stdout, foreign_bin) == 1
    assert _managed_dir_count(once.stdout, managed_bin) == 1

    twice = _source_n_times(_BASH, shellrc, times=2, home=tmp_path)
    assert twice.returncode == 0
    # The unmanaged export accumulates; the managed block, guarded since
    # plan 15.8-01, does not.
    assert _managed_dir_count(twice.stdout, foreign_bin) == 2
    assert _managed_dir_count(twice.stdout, managed_bin) == 1


# Reserved words and precommand modifiers that let a command still run. Found by
# the phase-15.8 review sweep, not by the plans: `time` is a shell KEYWORD, not
# an external binary, so `time . file` really sources the file. Before this was
# handled the classifier answered "none", consolidation copied the line forward
# verbatim, and the resulting ~/.myshellrc killed bash with SIGSEGV on every
# startup -- the exact failure this phase exists to prevent, reached through a
# shape the wrapped/escaped sweep above did not cover.
@pytest.mark.parametrize(
    ("modifier", "shells"),
    [
        ("time", ("bash", "zsh", "sh")),
        ("nocorrect", ("zsh",)),  # zsh precommand modifiers; no-ops elsewhere
        ("noglob", ("zsh",)),
    ],
)
def test_reserved_word_prefixed_source_forms_execute_and_are_refused(
    tmp_path: Path, modifier: str, shells: tuple[str, ...]
) -> None:
    # 1. Prove the form really sources the file, in every shell that has the word.
    marker = tmp_path / "marker.sh"
    marker.write_text("MARKER_RAN=1\n")
    for name in shells:
        shell = shutil.which(name)
        if shell is None:
            continue
        executed = subprocess.run(
            [shell, "-c", f'{modifier} . {marker}\necho "MARKER=${{MARKER_RAN-}}"'],
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert "MARKER=1" in executed.stdout, (
            f"{modifier!r} did not source under {name}; investigate the shell, "
            f"never delete the detection"
        )

    # 2. Prove consolidation refuses that same form, byte for byte.
    shellrc, myshellrc, _managed_bin = _seed_self_sourcing_home(
        tmp_path, f'{modifier} . "$HOME/.myshellrc"'
    )
    before_shellrc = shellrc.read_bytes()
    before_myshellrc = myshellrc.read_bytes()

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert str(shellrc) in result.reason
    assert shellrc.read_bytes() == before_shellrc
    assert myshellrc.read_bytes() == before_myshellrc
    assert _no_backup_anywhere(tmp_path)


def test_a_reserved_word_prefix_does_not_refuse_an_unrelated_command(tmp_path: Path) -> None:
    """The mirror risk: `time` before anything else must stay invisible.

    Widening the prefix set must not turn an ordinary timed command into a
    refusal, or consolidation becomes unusable for anyone who times a build.
    """
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")

    for line in ("time make build", "time ls -la", "noglob echo *"):
        assert classify_source_line(line, target).verdict == "none"


# --- Phase 15.8 review blockers: six independently reproduced defects ---
#
# Each of these produced a real failure before it was fixed. CR-01, CR-02 and
# CR-03/04 all ended in a shell that could not start (SIGSEGV from stack
# exhaustion) or in silently altered unmanaged content.


@pytest.mark.parametrize(
    "form",
    [
        ">/dev/null . {p}",
        "2>/dev/null . {p}",
        "> /dev/null . {p}",
        "&>/dev/null . {p}",
        "2>&1 . {p}",
        ">>log . {p}",
        "<&0 . {p}",
        "2>&1 source {p}",
    ],
)
def test_a_leading_redirection_never_hides_a_source_command(tmp_path: Path, form: str) -> None:
    """CR-02: a redirection may lead a command and the command still runs.

    Treating the redirection as the command word classified these `none`, so
    consolidation copied them forward and produced a self-sourcing file. Note
    `2>&1` also required protecting the duplicating-redirection `&` from the
    segment splitter, which had been tearing the line in half.
    """
    if _BASH is None:
        pytest.skip("bash not on PATH")
    marker = tmp_path / "marker.sh"
    marker.write_text("MARKER_RAN=1\n")
    executed = subprocess.run(
        [_BASH, "--noprofile", "--norc", "-c", form.format(p=marker) + '\necho "M=${MARKER_RAN-}"'],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert "M=1" in executed.stdout, f"{form!r} did not source; investigate the shell"

    shellrc, myshellrc, _bin = _seed_self_sourcing_home(
        tmp_path, form.format(p='"$HOME/.myshellrc"')
    )
    before = (shellrc.read_bytes(), myshellrc.read_bytes())

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert (shellrc.read_bytes(), myshellrc.read_bytes()) == before
    assert _no_backup_anywhere(tmp_path)


@pytest.mark.parametrize(
    "line", ["echo hi > /tmp/x", "cat < /etc/hosts", "make 2>&1 | tee log", "ls >out 2>&1"]
)
def test_ordinary_redirections_are_not_refused(tmp_path: Path, line: str) -> None:
    """The mirror risk of CR-02: redirecting anything else stays invisible."""
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")
    assert classify_source_line(line, target).verdict == "none"


@pytest.mark.parametrize("opener", ["cat <<\\EOF", "cat >out<<EOF", "cat <<-\\EOF"])
def test_an_escaped_or_glued_heredoc_opener_refuses(tmp_path: Path, opener: str) -> None:
    """CR-03: `<<\\EOF` is as ordinary as the quoted forms.

    Missing it let the BODY be scanned as shell, and the rewriter then commented
    out a line inside it -- silently altering content the user relies on, which
    is the over-reach direction of the same defect.
    """
    shellrc, myshellrc, _bin = _seed_self_sourcing_home(tmp_path, "placeholder")
    shellrc.write_text(f'{opener}\n. "$HOME/.myshellrc"\nEOF\n')
    before = (shellrc.read_bytes(), myshellrc.read_bytes())

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert "here-document" in result.reason
    assert (shellrc.read_bytes(), myshellrc.read_bytes()) == before


def test_a_backslash_continued_source_line_is_seen_as_one_command(tmp_path: Path) -> None:
    """CR-04: the shell joins the halves, so the classifier must too.

    `. ~/.mysh\\` + `ellrc` really sources the file; classifying the halves
    separately saw neither, and the line was copied forward verbatim.
    """
    if _BASH is None:
        pytest.skip("bash not on PATH")
    marker = tmp_path / "marker.sh"
    marker.write_text("MARKER_RAN=1\n")
    head = str(marker)[:-3]
    executed = subprocess.run(
        [
            _BASH,
            "--noprofile",
            "--norc",
            "-c",
            f". {head}\\\n{str(marker)[-3:]}\necho M=${{MARKER_RAN-}}",
        ],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert "M=1" in executed.stdout

    shellrc, myshellrc, _bin = _seed_self_sourcing_home(tmp_path, "placeholder")
    target = str(myshellrc)
    shellrc.write_text(f". {target[:-3]}\\\n{target[-3:]}\n")
    before = (shellrc.read_bytes(), myshellrc.read_bytes())

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert (shellrc.read_bytes(), myshellrc.read_bytes()) == before


def test_a_non_regular_shellrc_refuses_instead_of_blocking_forever(tmp_path: Path) -> None:
    """CR-05: a FIFO made the snapshot's `os.open` block with no timeout.

    The installer simply never returned, with nothing to tell the user why.
    """
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    shellrc = tmp_path / ".shellrc"
    os.mkfifo(shellrc)

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert "regular file" in result.reason


def test_a_non_utf8_myshellrc_refuses_as_a_typed_outcome(tmp_path: Path) -> None:
    """CR-06: UnicodeDecodeError is a ValueError, which run_live does not catch.

    It would have escaped as a raw traceback instead of a stated reason.
    """
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_bytes(b"\xff\xfe not utf-8\n")
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text("export KEEP=1\n")

    result = consolidate_shellrc(shellrc, myshellrc)

    assert result.status == "refused"
    assert result.reason is not None
    assert "UTF-8" in result.reason


def _bash_n(rc: Path, home: Path) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    return subprocess.run(
        ["bash", "-n", str(rc)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_guard_in_place_rewrites_one_foreign_bashrc_line(tmp_path: Path) -> None:
    home = tmp_path / "home"
    directory = home / ".local" / "bin"
    env = {"HOME": str(home)}
    text = "alias ll='ls -l'\nexport PATH=\"$HOME/.local/bin:$PATH\"\necho end\n"
    rc = tmp_path / ".bashrc"
    rc.write_text(text)
    original = rc.read_bytes()
    original_mode = stat.S_IMODE(rc.stat().st_mode)

    records = path_writer_lines({rc: text}, {directory}, env)
    assert len(records) == 1
    assert records[0].index == 1
    assert records[0].guardable is True

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "guarded"
    lines = rc.read_text().split("\n")
    assert lines[0] == "alias ll='ls -l'"
    assert lines[1] == path_export_guard(directory)
    assert lines[2] == "echo end"
    backup = staged_sibling(rc, OLD_SUFFIX)
    assert backup.read_bytes() == original
    assert stat.S_IMODE(backup.stat().st_mode) == original_mode
    assert _bash_n(rc, home).returncode == 0

    again = path_writer_lines({rc: rc.read_text()}, {directory}, env)
    assert not any(record.guardable for record in again)
    second = guard_path_writers(rc, [])
    assert second.status == "nothing"
    assert rc.read_bytes() != original
    assert backup.read_bytes() == original


def _seed_guard_rc(tmp_path: Path) -> tuple[Path, Path, dict[str, str], str]:
    home = tmp_path / "home"
    directory = home / ".local" / "bin"
    env = {"HOME": str(home)}
    text = "alias ll='ls -l'\nexport PATH=\"$HOME/.local/bin:$PATH\"\necho end\n"
    rc = tmp_path / ".bashrc"
    rc.write_text(text)
    return rc, directory, env, text


def test_guard_refuses_when_the_file_changed_since_the_scan(tmp_path: Path) -> None:
    rc, directory, env, text = _seed_guard_rc(tmp_path)
    records = path_writer_lines({rc: text}, {directory}, env)
    edited = b"# edited after the scan\n"
    rc.write_bytes(edited)

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "refused"
    assert outcome.reason is not None and "changed since Doctor scanned it" in outcome.reason
    assert rc.read_bytes() == edited
    assert not staged_sibling(rc, OLD_SUFFIX).exists()


def test_guard_refuses_when_the_file_changes_while_it_is_being_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc, directory, env, text = _seed_guard_rc(tmp_path)
    original = rc.read_bytes()
    records = path_writer_lines({rc: text}, {directory}, env)

    def _changed(_path: Path, _snapshot: object) -> bool:
        return False

    monkeypatch.setattr("installer.shellrc._snapshot_matches", _changed)

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "refused"
    assert outcome.reason is not None and "changed while it was being guarded" in outcome.reason
    assert rc.read_bytes() == original
    assert not staged_sibling(rc, OLD_SUFFIX).exists()


def test_guard_refuses_a_preexisting_backup_with_different_bytes(tmp_path: Path) -> None:
    rc, directory, env, text = _seed_guard_rc(tmp_path)
    original = rc.read_bytes()
    records = path_writer_lines({rc: text}, {directory}, env)
    backup = staged_sibling(rc, OLD_SUFFIX)
    backup.write_bytes(b"other original\n")
    os.chmod(backup, stat.S_IMODE(rc.stat().st_mode))

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "refused"
    assert rc.read_bytes() == original
    assert backup.read_bytes() == b"other original\n"


def test_guard_accepts_a_preexisting_backup_with_identical_bytes_and_mode(tmp_path: Path) -> None:
    rc, directory, env, text = _seed_guard_rc(tmp_path)
    original = rc.read_bytes()
    records = path_writer_lines({rc: text}, {directory}, env)
    backup = staged_sibling(rc, OLD_SUFFIX)
    backup.write_bytes(original)
    os.chmod(backup, stat.S_IMODE(rc.stat().st_mode))

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "guarded"
    assert rc.read_bytes() != original
    assert backup.read_bytes() == original


def test_guard_refuses_a_symlinked_bashrc(tmp_path: Path) -> None:
    _rc, directory, env, text = _seed_guard_rc(tmp_path)
    target = tmp_path / "real.bashrc"
    target.write_text(text)
    link = tmp_path / ".bashrc-link"
    link.symlink_to(target)
    before = target.read_bytes()
    records = path_writer_lines({link: text}, {directory}, env)

    outcome = guard_path_writers(link, records)

    assert outcome.status == "refused"
    assert outcome.reason is not None and "symlink" in outcome.reason
    assert link.is_symlink()
    assert link.resolve() == target
    assert target.read_bytes() == before
    assert not staged_sibling(link, OLD_SUFFIX).exists()
    assert not staged_sibling(target, OLD_SUFFIX).exists()


def test_guard_in_place_keeps_crlf(tmp_path: Path) -> None:
    home = tmp_path / "home"
    directory = home / ".local" / "bin"
    env = {"HOME": str(home)}
    text = "alias ll='ls -l'\r\nexport PATH=\"$HOME/.local/bin:$PATH\"\r\necho end\r\n"
    rc = tmp_path / ".bashrc"
    rc.write_bytes(text.encode())
    records = path_writer_lines({rc: text}, {directory}, env)
    assert len(records) == 1
    assert records[0].text.endswith("\r")

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "guarded"
    raw = rc.read_bytes()
    parts = raw.split(b"\n")
    assert parts[0] == b"alias ll='ls -l'\r"
    assert parts[1] == (path_export_guard(directory) + "\r").encode()
    assert parts[2] == b"echo end\r"
    assert parts[3] == b""


def test_guard_refuses_a_non_utf8_file(tmp_path: Path) -> None:
    rc, directory, env, _text = _seed_guard_rc(tmp_path)
    raw = b'caf\xe9\nexport PATH="$HOME/.local/bin:$PATH"\n'
    rc.write_bytes(raw)
    records = path_writer_lines({rc: 'export PATH="$HOME/.local/bin:$PATH"\n'}, {directory}, env)

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "refused"
    assert rc.read_bytes() == raw
    assert not staged_sibling(rc, OLD_SUFFIX).exists()


def test_guard_in_place_rewrites_an_indented_if_body(tmp_path: Path) -> None:
    home = tmp_path / "home"
    directory = home / ".local" / "bin"
    env = {"HOME": str(home)}
    text = 'if [ -d "$HOME/.local/bin" ]; then\n  export PATH="$HOME/.local/bin:$PATH"\nfi\n'
    rc = tmp_path / ".bashrc"
    rc.write_text(text)
    records = path_writer_lines({rc: text}, {directory}, env)
    assert len(records) == 1
    assert records[0].guardable is True

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "guarded"
    lines = rc.read_text().split("\n")
    assert lines[1] == "  " + path_export_guard(directory)
    assert _bash_n(rc, home).returncode == 0
    zsh = shutil.which("zsh")
    if zsh is None:
        return
    parsed = subprocess.run(
        [zsh, "-n", str(rc)],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert parsed.returncode == 0


def test_guard_preserves_mode_0600_on_the_file_and_the_backup(tmp_path: Path) -> None:
    rc, directory, env, text = _seed_guard_rc(tmp_path)
    os.chmod(rc, 0o600)
    records = path_writer_lines({rc: text}, {directory}, env)

    outcome = guard_path_writers(rc, records)

    assert outcome.status == "guarded"
    backup = staged_sibling(rc, OLD_SUFFIX)
    assert stat.S_IMODE(rc.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_consolidation_refuses_when_shellrc_sources_an_rc_this_run_will_wire(
    tmp_path: Path,
) -> None:
    """CR-01: the cycle that needs no classifier hole at all.

    Before the run there is no loop, so every other check passes. But the
    content copied into ~/.myshellrc sources .bashrc, and the same run wires
    .bashrc to source ~/.myshellrc -- closing .bashrc -> .myshellrc -> .bashrc.
    """
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("export KEEP=1\n")
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text('. "$HOME/.bashrc"\n')
    before = (shellrc.read_bytes(), myshellrc.read_bytes())

    result = consolidate_shellrc(shellrc, myshellrc, (bashrc,))

    assert result.status == "refused"
    assert result.reason is not None
    assert str(bashrc) in result.reason
    assert (shellrc.read_bytes(), myshellrc.read_bytes()) == before
    assert _no_backup_anywhere(tmp_path)


def test_an_unrelated_rc_path_does_not_refuse(tmp_path: Path) -> None:
    """The mirror risk of CR-01: only a real cycle may refuse."""
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("export KEEP=1\n")
    shellrc = tmp_path / ".shellrc"
    shellrc.write_text("alias gs='git status'\n")

    assert consolidate_shellrc(shellrc, myshellrc, (bashrc,)).status == "consolidated"


def test_a_single_quoted_argument_is_not_expanded(tmp_path: Path) -> None:
    """Single quotes suppress every expansion, so this is a DIFFERENT file.

    Stripping quotes before expanding made `. '$HOME/.myshellrc'` look like the
    target and marked it rewritable -- which would have commented out a working
    command that sources some other file. A wrong verdict is content mutation
    even when it never loops.
    """
    target = tmp_path / ".myshellrc"
    target.write_text("x\n")

    assert classify_source_line(". '$HOME/.myshellrc'", target).verdict == "none"
    assert classify_source_line(". '~/.myshellrc'", target).verdict == "none"
    # An absolute single-quoted path needs no expansion, so it still matches.
    assert classify_source_line(f". '{target}'", target).verdict == "rewritable"


@pytest.mark.parametrize(
    ("label", "original"),
    [
        ("crlf", b"export A=1\r\nexport B=2\r\n"),
        ("u2028", 'export A="x y"\n'.encode()),
        ("form_feed", b"export A=1\x0cexport B=2\n"),
        ("nel", b"export A=1\xc2\x85export B=2\n"),
    ],
)
def test_copy_forward_preserves_bytes_a_shell_does_not_treat_as_newlines(
    tmp_path: Path, label: str, original: bytes
) -> None:
    """D-04 promises user content is copied forward VERBATIM.

    `str.splitlines()` splits on \\r, \\v, \\f, \\x1c-\\x1e, \\x85, U+2028 and
    U+2029 -- none of which a POSIX shell treats as a line separator. Using it
    normalized a CRLF file to LF and tore one shell line in two at a form feed,
    so the copied content was not what the user wrote.
    """
    managed_bin = tmp_path / "managed_bin"
    managed_bin.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([managed_bin], myshellrc)
    shellrc = tmp_path / ".shellrc"
    shellrc.write_bytes(original)

    assert consolidate_shellrc(shellrc, myshellrc).status == "consolidated"

    assert original.rstrip(b"\n") in myshellrc.read_bytes()
    assert _backup_path(shellrc).read_bytes() == original
