from pathlib import Path

from installer.model import Method, Tool
from installer.platform import Platform
from installer.shellrc import (
    apply_block,
    collect_bin_dirs,
    ensure_source,
    managed_block,
    remove_managed_block,
    strip_block,
    write_myshellrc,
)

# has_brew=True so the brew-method tools in these tests still resolve (and thus
# still contribute their bin dirs) under platform-aware collect_bin_dirs.
_PLATFORM = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


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


def test_managed_block_exports_each_dir_between_markers():
    block = managed_block([Path("/a/bin"), Path("/b/bin")])
    assert block.splitlines() == [
        "# >>> tools-installer path >>>",
        'export PATH="/a/bin:$PATH"',
        'export PATH="/b/bin:$PATH"',
        "# <<< tools-installer path <<<",
    ]


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
    assert 'export PATH="/a/bin:$PATH"' in first


def test_write_myshellrc_preserves_existing_user_lines(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    write_myshellrc([Path("/a/bin")], rc)
    text = rc.read_text()
    assert "export EDITOR=vim" in text
    assert 'export PATH="/a/bin:$PATH"' in text


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
    assert f'export PATH="{tmp_path / "bin"}:$PATH"' in text
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
