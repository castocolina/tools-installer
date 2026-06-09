from pathlib import Path

from installer.model import Method, Tool
from installer.shellrc import (
    apply_block,
    collect_bin_dirs,
    ensure_source,
    managed_block,
    write_myshellrc,
)


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
    assert collect_bin_dirs(tools, default) == [
        Path("/home/u/.local/bin"),
        Path("/home/u/tools/bin"),
    ]


def test_collect_bin_dirs_expands_user():
    default = Path("/d")
    tools = [_tool("rg", "~/x/bin")]
    result = collect_bin_dirs(tools, default)
    assert result[0] == Path("/d")
    assert result[1] == Path.home() / "x" / "bin"


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
