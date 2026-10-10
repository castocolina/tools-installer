from pathlib import Path

import pytest

from installer import rcclean
from installer.rcclean import (
    PathWriterLine,
    find_duplicate_path_lines,
    group_writer_lines,
    path_writer_lines,
    scan_rc_path_writer_lines,
    strip_lines,
)
from installer.shellrc import managed_block, path_export_guard


def test_flags_literal_home_path_duplicate():
    rc = 'export PATH="$HOME/.bun/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [0]


def test_pnpm_case_guard_form_is_not_flagged():
    # pnpm setup writes a self-deduping case guard, not a plain `export PATH=`.
    # We intentionally do not strip it (its own guard already avoids duplicates).
    rc = (
        'export PNPM_HOME="$HOME/.local/share/pnpm"\n'
        'case ":$PATH:" in\n'
        '  *":$PNPM_HOME:"*) ;;\n'
        '  *) export PATH="$PNPM_HOME:$PATH" ;;\n'
        "esac\n"
    )
    managed = {Path("/home/u/.local/share/pnpm")}
    assert find_duplicate_path_lines(rc, managed, {"HOME": "/home/u"}) == []


def test_resolves_var_assigned_earlier_in_the_file():
    rc = '# bun\nexport BUN_INSTALL="$HOME/.bun"\nexport PATH="$BUN_INSTALL/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [2]


def test_resolves_pnpm_home_style():
    rc = 'export PNPM_HOME="$HOME/.local/share/pnpm"\nexport PATH="$PNPM_HOME:$PATH"\n'
    managed = {Path("/home/u/.local/share/pnpm")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [1]


def test_expands_leading_tilde():
    rc = 'export PATH="~/.bun/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [0]


def test_ignores_unmanaged_path_lines():
    rc = 'export PATH="$HOME/.cargo/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_ignores_non_path_lines():
    rc = 'alias ll="ls -la"\nexport EDITOR=vim\n'
    assert find_duplicate_path_lines(rc, {Path("/home/u/.bun/bin")}, {"HOME": "/home/u"}) == []


def test_excludes_our_own_managed_block():
    rc = (
        "# >>> tools-installer path >>>\n"
        'export PATH="/home/u/.bun/bin:$PATH"\n'
        "# <<< tools-installer path <<<\n"
    )
    managed = {Path("/home/u/.bun/bin")}
    assert find_duplicate_path_lines(rc, managed, {"HOME": "/home/u"}) == []


def test_unresolved_var_is_not_flagged():
    rc = 'export PATH="$UNKNOWN/bin:$PATH"\n'
    assert find_duplicate_path_lines(rc, {Path("/home/u/.bun/bin")}, {"HOME": "/home/u"}) == []


def test_strip_lines_removes_only_given_indices():
    text = "a\nb\nc\nd\n"
    assert strip_lines(text, [1, 3]) == "a\nc\n"


def test_strip_lines_empty_is_identity():
    assert strip_lines("a\nb\n", []) == "a\nb\n"


# Extra tests for full branch coverage


def test_expands_tilde_without_home_in_env():
    """Covers the `home` falsy fallback in _expand (no HOME in env)."""
    rc = 'export PATH="~/.bun/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    # With no HOME, tilde stays unexpanded — the expanded path won't match, so no flag.
    assert find_duplicate_path_lines(rc, managed, {}) == []


def test_single_quote_unquote():
    """Covers the single-quote branch of _unquote."""
    rc = "export PATH='~/.bun/bin:$PATH'\n"
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [0]


def test_excludes_source_managed_block():
    """Covers the source-block markers in _managed_line_indices."""
    rc = (
        "# >>> tools-installer source >>>\n"
        'export PATH="/home/u/.bun/bin:$PATH"\n'
        "# <<< tools-installer source <<<\n"
    )
    managed = {Path("/home/u/.bun/bin")}
    assert find_duplicate_path_lines(rc, managed, {"HOME": "/home/u"}) == []


def test_orphan_begin_marker_does_not_crash():
    """Covers the orphan begin (no matching end) path in _managed_line_indices."""
    rc = '# >>> tools-installer path >>>\nexport PATH="/home/u/.bun/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    # No end marker — lines inside are NOT blocked (incomplete block), so it IS flagged.
    # The important thing is no crash and the orphan begin is handled gracefully.
    result = find_duplicate_path_lines(rc, managed, {"HOME": "/home/u"})
    # The begin marker line is index 0; PATH export is index 1.
    # Because the block is never closed the blocked set stays empty.
    assert result == [1]


def test_indented_path_line_inside_if_block_is_not_flagged():
    """Regression: Fedora's default .bashrc wraps its PATH assignment in an
    `if ! [[ ... ]]; then\n    PATH=...\nfi` block. Stripping only the indented
    body line leaves an empty then-clause, a bash syntax error that breaks
    every later login shell. An indented line is never one this installer, bun,
    or fnm appended (always column 0), so it must never be a strip candidate.
    """
    rc = (
        'if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]; then\n'
        '    PATH="$HOME/.local/bin:$HOME/bin:$PATH"\n'
        "fi\n"
        "export PATH\n"
    )
    managed = {Path("/home/u/.local/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_assignment_with_unresolvable_var_is_skipped():
    """Covers line 87 False-branch: _expand returns None for an assignment line.

    When `export VAR=$UNKNOWN` appears, the assignment is skipped (var not stored),
    so a subsequent PATH that uses $VAR stays unresolved and is NOT flagged.
    """
    rc = 'export BUN_INSTALL=$UNKNOWN_BASE/.bun\nexport PATH="$BUN_INSTALL/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    # BUN_INSTALL never gets stored because $UNKNOWN_BASE can't be resolved,
    # so the PATH line also can't be resolved → not flagged.
    assert find_duplicate_path_lines(rc, managed, env) == []


# Task 1: Pin that this project's own guarded output is never flagged


def test_managed_block_own_output_is_not_flagged() -> None:
    """The real managed_block() output should never be flagged by find_duplicate_path_lines.

    This pins that the new case-guarded form emitted by managed_block() is self-deduping
    and will never be stripped by the cleanup path.
    """
    dir_a = Path("/home/u/.local/bin")
    dir_b = Path("/home/u/.bun/bin")
    rc = managed_block([dir_a, dir_b])
    managed: set[Path] = {dir_a, dir_b}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_guard_lines_are_not_flagged_outside_our_markers() -> None:
    """The guard lines alone (stripped of markers) should not match _PATH_EXPORT regex.

    This proves the regex itself recognizes the guard form as safe, not merely its
    location inside marker blocks. Tests that _managed_line_indices contributes nothing.
    """
    dir_a = Path("/home/u/.local/bin")
    dir_b = Path("/home/u/.bun/bin")
    # Get the full managed block, then strip the marker lines
    full_block = managed_block([dir_a, dir_b])
    lines = full_block.split("\n")
    # First line is the begin marker, last line is the end marker; remove both
    guard_lines = "\n".join(lines[1:-1])
    managed: set[Path] = {dir_a, dir_b}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(guard_lines, managed, env) == []


def test_indented_guard_line_is_not_flagged() -> None:
    """An indented guard line should not be flagged (neither regex nor heuristic match).

    This ensures that if a user's own if/case block indents a copied guard line,
    it stays safe from the cleanup path.
    """
    directory = Path("/home/u/.local/bin")
    guard = path_export_guard(directory)
    indented = "    " + guard
    rc = indented + "\n"
    managed: set[Path] = {directory}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_guard_line_for_an_unmanaged_dir_is_not_flagged() -> None:
    """A guard line for a directory not in managed_dirs should not be flagged.

    This confirms that self-deduping lines are never strip candidates, even if the
    directory name does not appear in our managed set (e.g., a user's own tool).
    """
    directory = Path("/opt/some/tool/bin")
    guard = path_export_guard(directory)
    rc = guard + "\n"
    # managed_dirs is empty — the directory is not ours
    managed: set[Path] = set()
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_the_two_pattern_guard_form_is_not_flagged(tmp_path: Path) -> None:
    """A guard line with two patterns (for aliased directories) should not be flagged.

    When a directory has a second spelling (e.g., /home -> /var/home on this host),
    path_export_guard emits a case pattern with two alternatives joined by |.
    This test exercises that alternation branch.
    """
    import sys

    # Create a real aliased directory under tmp_path to test the symlink branch
    real_dir = tmp_path / "real" / "bin"
    real_dir.mkdir(parents=True)
    link_dir = tmp_path / "link"
    try:
        link_dir.symlink_to(tmp_path / "real")
    except OSError:
        # Platform without symlink support; skip this test
        if sys.platform == "win32":
            pytest.skip(reason="Windows symlink not available without admin")
        raise

    # Guard the symlinked path; path_export_guard will detect the alias
    guard = path_export_guard(link_dir / "bin")
    rc = guard + "\n"

    # Both spellings are in managed_dirs
    managed: set[Path] = {link_dir / "bin", real_dir}
    env = {"HOME": str(tmp_path)}
    assert find_duplicate_path_lines(rc, managed, env) == []


# Task 2: Pin the opposite direction — other tools' plain exports are still flagged


def test_plain_export_for_a_managed_dir_is_still_flagged_alongside_our_guard() -> None:
    """After the shape change, plain exports are still flagged when mixed with guarded lines.

    This is the critical test: it proves the two shapes are distinguished, not that
    everything stopped being flagged. A file with both this project's guarded block
    and another tool's plain export should flag only the plain export.
    """
    directory = Path("/home/u/.bun/bin")

    # Build rc text as a list so we can track line indices
    lines: list[str] = []
    lines.extend(managed_block([directory]).split("\n"))
    plain_export_line_index = len(lines)
    lines.append('export PATH="/home/u/.bun/bin:$PATH"')
    rc = "\n".join(lines)

    managed: set[Path] = {directory}
    env = {"HOME": "/home/u"}
    result = find_duplicate_path_lines(rc, managed, env)

    # Should find exactly one line: the plain export
    assert result == [plain_export_line_index]


def test_pnpm_case_guard_and_our_guard_are_both_skipped_in_one_file() -> None:
    """Two independent self-deduping guard forms in one file should both be skipped.

    This confirms that pnpm's own multi-line case guard and our single-line guard
    are both recognized as self-deduping and neither is a strip candidate.
    """
    our_directory = Path("/home/u/.local/bin")

    # pnpm's multi-line guard form (from existing test)
    pnpm_guard = (
        'export PNPM_HOME="$HOME/.local/share/pnpm"\n'
        'case ":$PATH:" in\n'
        '  *":$PNPM_HOME:"*) ;;\n'
        '  *) export PATH="$PNPM_HOME:$PATH" ;;\n'
        "esac"
    )

    # Our single-line guard form
    our_guard = path_export_guard(our_directory)

    rc = pnpm_guard + "\n" + our_guard + "\n"

    managed: set[Path] = {
        Path("/home/u/.local/share/pnpm"),
        our_directory,
    }
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_unguarded_writer_is_reported_with_its_file(tmp_path: Path) -> None:
    """A plain prepend survives every new shell, so naming its file is the only
    thing that lets a user act on a duplicate PATH entry."""
    bashrc = tmp_path / ".bashrc"
    writers = group_writer_lines(
        path_writer_lines(
            {bashrc: 'export PATH="/home/u/.local/bin:$PATH"\n'},
            {Path("/home/u/.local/bin")},
            {"HOME": "/home/u"},
        )
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc,)}


def test_writer_dir_test_if_reported(tmp_path: Path) -> None:
    """An indented line inside a block whose condition does not test PATH still
    counts for REPORTING (reporting and stripping are different questions).
    Fedora's presence-guard header is the CR-01 case and is covered by
    test_writer_fedora_presence_guard_not_reported."""
    bashrc = tmp_path / ".bashrc"
    text = 'if [ -d "$HOME/.local/bin" ]; then\n    export PATH="$HOME/.local/bin:$PATH"\nfi\n'
    writers = group_writer_lines(
        path_writer_lines({bashrc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"})
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc,)}


def test_case_guarded_line_is_not_a_writer(tmp_path: Path) -> None:
    """The self-deduping form this installer emits (and pnpm's own) cannot
    duplicate, so reporting it would send the user to fix a correct line."""
    rc = tmp_path / ".myshellrc"
    text = (
        'case ":${PATH-}:" in *":/home/u/.local/bin:"*) ;; '
        '*) export PATH="/home/u/.local/bin${PATH:+:$PATH}";;esac\n'
    )
    assert (
        group_writer_lines(
            path_writer_lines({rc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"})
        )
        == {}
    )


def test_managed_block_is_not_a_writer(tmp_path: Path) -> None:
    """Our own managed block is guarded; flagging it would tell the user to edit
    the very file this installer maintains."""
    rc = tmp_path / ".bashrc"
    text = (
        "# >>> tools-installer path >>>\n"
        'export PATH="/home/u/.local/bin:$PATH"\n'
        "# <<< tools-installer path <<<\n"
    )
    assert (
        group_writer_lines(
            path_writer_lines({rc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"})
        )
        == {}
    )


def test_every_writer_of_the_same_directory_is_reported(tmp_path: Path) -> None:
    """Two files each adding the directory is exactly the structural 2x case;
    naming only the first would send the user back for a second round."""
    bashrc = tmp_path / ".bashrc"
    profile = tmp_path / ".bash_profile"
    line = 'export PATH="/home/u/.local/bin:$PATH"\n'
    writers = group_writer_lines(
        path_writer_lines(
            {bashrc: line, profile: line}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}
        )
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc, profile)}


def test_unrelated_directory_is_not_reported(tmp_path: Path) -> None:
    rc = tmp_path / ".bashrc"
    text = 'export PATH="/opt/other/bin:$PATH"\n'
    assert (
        group_writer_lines(
            path_writer_lines({rc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"})
        )
        == {}
    )


def test_writer_scan_reads_real_files_and_skips_unreadable(tmp_path: Path) -> None:
    """A Doctor that raises on an unreadable rc file is worse than one that
    reports a cause it could not determine."""
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text('export PATH="/home/u/.local/bin:$PATH"\n')
    missing = tmp_path / ".does-not-exist"
    binary = tmp_path / ".binaryrc"
    binary.write_bytes(b"\xff\xfe\x00export PATH=/home/u/.local/bin:$PATH\n")

    writers = group_writer_lines(
        scan_rc_path_writer_lines(
            [bashrc, missing, binary], {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}
        )
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc,)}


_ENV = {"HOME": "/home/u"}
_LOCAL_BIN = Path("/home/u/.local/bin")


def test_writer_guarded_if_not_reported() -> None:
    text = (
        'if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then\n'
        '    export PATH="$HOME/.local/bin:$PATH"\n'
        "fi\n"
    )
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, {_LOCAL_BIN}, _ENV)) == {}


def test_writer_fedora_presence_guard_not_reported() -> None:
    text = (
        'if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]\n'
        "then\n"
        '    PATH="$HOME/.local/bin:$HOME/bin:$PATH"\n'
        "fi\n"
    )
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, {_LOCAL_BIN}, _ENV)) == {}


def test_writer_pnpm_case_block_not_reported() -> None:
    text = (
        'export PNPM_HOME="$HOME/.local/share/pnpm"\n'
        'case ":$PATH:" in\n'
        '  *":$PNPM_HOME:"*) ;;\n'
        '  *) export PATH="$PNPM_HOME:$PATH" ;;\n'
        "esac\n"
    )
    managed = {Path("/home/u/.local/share/pnpm")}
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, managed, _ENV)) == {}


def test_path_export_guard_output_never_flagged() -> None:
    guard = path_export_guard(_LOCAL_BIN)
    managed = {_LOCAL_BIN}
    for text in (guard + "\n", "    " + guard + "\n"):
        assert group_writer_lines(path_writer_lines({Path("rc"): text}, managed, _ENV)) == {}
        assert find_duplicate_path_lines(text, managed, _ENV) == []


@pytest.mark.parametrize(
    "shape",
    ["one_line_if", "if_elif_else", "case_guard", "pnpm_case", "one_line_for"],
)
def test_writer_after_block_shape_still_reported(shape: str) -> None:
    trailing = 'export PATH="$HOME/.local/bin:$PATH"'
    prefixes = {
        "one_line_if": 'if [ -d "$HOME/bin" ]; then PATH="$HOME/bin:$PATH"; fi\n',
        "if_elif_else": (
            'if [[ ":$PATH:" != *":$HOME/other:"* ]]; then\n'
            "  :\n"
            'elif [[ ":$PATH:" == *":$HOME/other:"* ]]; then\n'
            "  :\n"
            "else\n"
            "  :\n"
            "fi\n"
        ),
        "case_guard": path_export_guard(_LOCAL_BIN) + "\n",
        "pnpm_case": (
            'export PNPM_HOME="$HOME/.local/share/pnpm"\n'
            'case ":$PATH:" in\n'
            '  *":$PNPM_HOME:"*) ;;\n'
            '  *) export PATH="$PNPM_HOME:$PATH" ;;\n'
            "esac\n"
        ),
        "one_line_for": "for d in a b; do :; done\n",
    }
    text = prefixes[shape] + trailing + "\n"
    managed = {_LOCAL_BIN}
    rc = Path("rc")
    assert group_writer_lines(path_writer_lines({rc: text}, managed, _ENV)) == {_LOCAL_BIN: (rc,)}
    assert find_duplicate_path_lines(text, managed, _ENV) == [text.split("\n").index(trailing)]


def test_trailing_slash_writer_is_normalized() -> None:
    text = 'export PATH="$HOME/.local/bin/:$PATH"\n'
    rc = Path("rc")
    assert group_writer_lines(path_writer_lines({rc: text}, {_LOCAL_BIN}, _ENV)) == {
        _LOCAL_BIN: (rc,)
    }
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == [0]


def test_double_slash_writer_is_normalized() -> None:
    text = 'export PATH="$HOME//.local/bin:$PATH"\n'
    rc = Path("rc")
    assert group_writer_lines(path_writer_lines({rc: text}, {_LOCAL_BIN}, _ENV)) == {
        _LOCAL_BIN: (rc,)
    }
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == [0]


def test_relative_or_empty_segment_never_matches() -> None:
    managed = {_LOCAL_BIN, Path("bin")}
    for text in ('export PATH="bin:$PATH"\n', 'export PATH=":$PATH"\n'):
        assert group_writer_lines(path_writer_lines({Path("rc"): text}, managed, _ENV)) == {}
        assert find_duplicate_path_lines(text, managed, _ENV) == []


@pytest.mark.parametrize("loop_header", ["for d in a b; do", "while read -r d; do"])
def test_writer_nested_loop_inside_guarded_if_not_reported(loop_header: str) -> None:
    text = (
        'if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then\n'
        f"{loop_header}\n"
        "  :\n"
        "done\n"
        'export PATH="$HOME/.local/bin:$PATH"\n'
        "fi\n"
    )
    managed = {_LOCAL_BIN}
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, managed, _ENV)) == {}
    assert find_duplicate_path_lines(text, managed, _ENV) == []


def _writer(text: str, directory: Path = _LOCAL_BIN) -> dict[Path, tuple[Path, ...]]:
    return group_writer_lines(path_writer_lines({Path("rc"): text}, {directory}, _ENV))


def test_trailing_comment_is_a_writer_not_a_strip_candidate() -> None:
    text = 'export PATH="$HOME/.local/bin:$PATH"  # added by uv\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == []


def test_semicolon_suffix_is_a_writer_not_a_strip_candidate() -> None:
    text = 'export PATH="$HOME/.local/bin:$PATH"; export X=1\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == []


def test_and_prefix_is_a_writer_not_a_strip_candidate() -> None:
    text = '[ -d "$HOME/.local/bin" ] && export PATH="$HOME/.local/bin:$PATH"\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == []


def test_or_prefix_is_a_writer() -> None:
    text = 'true || export PATH="$HOME/.local/bin:$PATH"\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == []


@pytest.mark.parametrize(
    ("text", "reported"),
    [
        ('if [ -d "$HOME/bin" ]; then PATH="$HOME/bin:$PATH"; fi\n', True),
        ('if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then PATH="$HOME/bin:$PATH"; fi\n', False),
    ],
)
def test_one_line_if_shapes(text: str, reported: bool) -> None:
    directory = Path("/home/u/bin")
    expected = {directory: (Path("rc"),)} if reported else {}
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, {directory}, _ENV)) == expected
    assert find_duplicate_path_lines(text, {directory}, _ENV) == []


@pytest.mark.parametrize(
    "idiom",
    [
        '[[ ":$PATH:" != *":$HOME/.local/bin:"* ]] && export PATH="$HOME/.local/bin:$PATH"',
        '[[ ":$PATH:" == *":$HOME/.local/bin:"* ]] || export PATH="$HOME/.local/bin:$PATH"',
    ],
)
def test_one_line_presence_idiom_is_not_a_writer(idiom: str) -> None:
    assert _writer(idiom + "\n") == {}
    text = idiom + '\nexport PATH="$HOME/.local/bin:$PATH"\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == [1]


def test_earlier_assignment_is_not_a_presence_test() -> None:
    text = '[ -d "$HOME/a" ] && PATH="$HOME/a:$PATH" && PATH="$HOME/.local/bin:$PATH"\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == []


@pytest.mark.parametrize(
    "text",
    [
        'path=("$HOME/.local/bin" $path)\n',
        'typeset -U path; path=("$HOME/.local/bin" $path)\n',
        'export path=("$HOME/.local/bin" $path)\n',
    ],
)
def test_zsh_path_array_shapes_are_writers(text: str) -> None:
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}


def test_zsh_array_line_is_not_a_strip_candidate() -> None:
    text = 'path=("$HOME/.local/bin" $path)\n'
    assert _writer(text) == {_LOCAL_BIN: (Path("rc"),)}
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == []


def test_hash_inside_quotes_is_data_not_a_comment() -> None:
    directory = Path("/opt/a#b")
    text = 'export PATH="/opt/a#b:$PATH"\n'
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, {directory}, _ENV)) == {
        directory: (Path("rc"),)
    }


def test_assignment_segment_resolves_a_later_path_segment() -> None:
    directory = Path("/home/u/.bun/bin")
    text = 'export BUN_INSTALL="$HOME/.bun"; export PATH="$BUN_INSTALL/bin:$PATH"\n'
    assert group_writer_lines(path_writer_lines({Path("rc"): text}, {directory}, _ENV)) == {
        directory: (Path("rc"),)
    }
    assert find_duplicate_path_lines(text, {directory}, _ENV) == []


def test_path_writer_lines_prepend_is_guardable() -> None:
    text = "alias ll='ls -l'\nexport PATH=\"$HOME/.local/bin:$PATH\"\necho end\n"
    rc = Path("rc")
    records = path_writer_lines({rc: text}, {_LOCAL_BIN}, _ENV)
    assert len(records) == 1
    assert records[0].index == 1
    assert records[0].rc_path == rc
    assert records[0].directory == _LOCAL_BIN
    assert records[0].guardable is True
    assert records[0].refusal is None
    assert records[0].block_owner is None


def test_path_writer_lines_zsh_array_is_not_guardable() -> None:
    text = 'path=("$HOME/.local/bin" $path)\n'
    records = path_writer_lines({Path("rc"): text}, {_LOCAL_BIN}, _ENV)
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal is not None


def _records(text: str, managed: set[Path] | None = None) -> list[PathWriterLine]:
    return path_writer_lines({Path("rc"): text}, managed or {_LOCAL_BIN}, _ENV)


def test_marker_block_kitty_names_the_owner() -> None:
    text = (
        '# >>> my-kitty PATH >>>\nexport PATH="$HOME/.local/bin:$PATH"\n# <<< my-kitty PATH <<<\n'
    )
    records = _records(text)
    assert len(records) == 1
    assert records[0].block_owner == "my-kitty PATH"
    assert records[0].guardable is False
    assert records[0].refusal == (
        "inside the 'my-kitty PATH' block another tool manages; fix it in that tool"
    )


def test_marker_block_unterminated_conda_owns_every_following_line() -> None:
    text = '# >>> conda initialize >>>\nexport PATH="$HOME/.local/bin:$PATH"\n'
    records = _records(text)
    assert len(records) == 1
    assert records[0].block_owner == "conda initialize"
    assert records[0].guardable is False


def test_marker_block_tools_installer_path_is_skipped() -> None:
    text = (
        "# >>> tools-installer path >>>\n"
        'export PATH="$HOME/.local/bin:$PATH"\n'
        "# <<< tools-installer path <<<\n"
    )
    assert _records(text) == []


def test_consolidated_shellrc_block_is_not_foreign(tmp_path: Path) -> None:
    text = (
        "# >>> tools-installer consolidated shellrc >>>\n"
        'export PATH="$HOME/.local/bin:$PATH"\n'
        "# <<< tools-installer consolidated shellrc <<<\n"
    )
    rc = tmp_path / ".myshellrc"
    records = path_writer_lines({rc: text}, {_LOCAL_BIN}, _ENV)
    assert len(records) == 1
    assert records[0].block_owner is None
    assert records[0].guardable is True


def test_marker_block_mismatched_end_closes_nothing() -> None:
    text = '# >>> conda initialize >>>\nexport PATH="$HOME/.local/bin:$PATH"\n# <<< other >>>\n'
    records = _records(text)
    assert len(records) == 1
    assert records[0].block_owner == "conda initialize"


def test_refuse_multi_directory() -> None:
    text = 'export PATH="$HOME/.local/bin:$HOME/bin:$PATH"\n'
    records = _records(text)
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal == rcclean._REFUSE_MULTI  # pyright: ignore[reportPrivateUsage]


def test_refuse_append_form() -> None:
    text = 'export PATH="$PATH:$HOME/.local/bin"\n'
    records = _records(text)
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal == rcclean._REFUSE_APPEND  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    "line",
    [
        'export PATH="$HOME/.local/bin:$PATH"; export X=1',
        'export PATH="$HOME/.local/bin:$PATH"  # added by uv',
        '[ -d "$HOME/.local/bin" ] && export PATH="$HOME/.local/bin:$PATH"',
    ],
)
def test_refuse_compound_line(line: str) -> None:
    records = _records(line + "\n")
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal == rcclean._REFUSE_COMPOUND  # pyright: ignore[reportPrivateUsage]


def test_refuse_zsh_array() -> None:
    records = _records('path=("$HOME/.local/bin" $path)\n')
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal == rcclean._REFUSE_ZSH_ARRAY  # pyright: ignore[reportPrivateUsage]


def test_refuse_unresolved_variable() -> None:
    text = 'export PATH="$FOO/bin:$HOME/.local/bin:$PATH"\n'
    records = _records(text)
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal == rcclean._REFUSE_UNRESOLVED  # pyright: ignore[reportPrivateUsage]
    assert _records('export PATH="$FOO/bin:$PATH"\n') == []


def test_indented_if_body_is_guardable() -> None:
    text = 'if [ -d "$HOME/.local/bin" ]; then\n  export PATH="$HOME/.local/bin:$PATH"\nfi\n'
    records = _records(text)
    assert len(records) == 1
    assert records[0].index == 1
    assert records[0].guardable is True
    assert records[0].block_owner is None


def test_then_prefixed_path_line_is_not_a_strip_candidate() -> None:
    text = 'if [ -d "$HOME/.local/bin" ]\nthen PATH="$HOME/.local/bin:$PATH"\nfi'
    managed = {Path("/home/u/.local/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(text, managed, env) == []
    assert strip_lines(text, find_duplicate_path_lines(text, managed, env)) == text


def test_do_prefixed_path_line_is_not_a_strip_candidate() -> None:
    text = 'until false\ndo PATH="$HOME/.local/bin:$PATH"\ndone'
    managed = {Path("/home/u/.local/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(text, managed, env) == []
    assert strip_lines(text, find_duplicate_path_lines(text, managed, env)) == text


def test_then_prefixed_path_line_is_still_reported_but_not_guardable() -> None:
    text = 'if [ -d "$HOME/.local/bin" ]\nthen PATH="$HOME/.local/bin:$PATH"\nfi'
    records = path_writer_lines(
        {Path("rc"): text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}
    )
    assert len(records) == 1
    assert records[0].guardable is False
    assert records[0].refusal == rcclean._REFUSE_COMPOUND  # pyright: ignore[reportPrivateUsage]


def test_plain_column_zero_export_is_still_a_strip_candidate() -> None:
    text = 'export PATH="$HOME/.local/bin:$PATH"'
    assert find_duplicate_path_lines(text, {_LOCAL_BIN}, _ENV) == [0]
