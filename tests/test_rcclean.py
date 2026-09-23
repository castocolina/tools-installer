from pathlib import Path

import pytest

from installer.rcclean import find_duplicate_path_lines, strip_lines
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
    from installer.rcclean import unguarded_path_writers

    bashrc = tmp_path / ".bashrc"
    writers = unguarded_path_writers(
        {bashrc: 'export PATH="/home/u/.local/bin:$PATH"\n'},
        {Path("/home/u/.local/bin")},
        {"HOME": "/home/u"},
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc,)}


def test_indented_writer_still_counts_as_a_writer(tmp_path: Path) -> None:
    """Fedora's stock .bashrc wraps its prepend in an `if`, so the line is
    indented. strip_lines must never touch it (removing it would leave an empty
    then-clause), but it adds the directory on every shell all the same —
    REPORTING it and STRIPPING it are different questions."""
    from installer.rcclean import unguarded_path_writers

    bashrc = tmp_path / ".bashrc"
    text = (
        'if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]; then\n'
        '    export PATH="$HOME/.local/bin:$PATH"\n'
        "fi\n"
    )
    writers = unguarded_path_writers(
        {bashrc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc,)}


def test_case_guarded_line_is_not_a_writer(tmp_path: Path) -> None:
    """The self-deduping form this installer emits (and pnpm's own) cannot
    duplicate, so reporting it would send the user to fix a correct line."""
    from installer.rcclean import unguarded_path_writers

    rc = tmp_path / ".myshellrc"
    text = (
        'case ":${PATH-}:" in *":/home/u/.local/bin:"*) ;; '
        '*) export PATH="/home/u/.local/bin${PATH:+:$PATH}";;esac\n'
    )
    assert (
        unguarded_path_writers({rc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}) == {}
    )


def test_managed_block_is_not_a_writer(tmp_path: Path) -> None:
    """Our own managed block is guarded; flagging it would tell the user to edit
    the very file this installer maintains."""
    from installer.rcclean import unguarded_path_writers

    rc = tmp_path / ".bashrc"
    text = (
        "# >>> tools-installer path >>>\n"
        'export PATH="/home/u/.local/bin:$PATH"\n'
        "# <<< tools-installer path <<<\n"
    )
    assert (
        unguarded_path_writers({rc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}) == {}
    )


def test_every_writer_of_the_same_directory_is_reported(tmp_path: Path) -> None:
    """Two files each adding the directory is exactly the structural 2x case;
    naming only the first would send the user back for a second round."""
    from installer.rcclean import unguarded_path_writers

    bashrc = tmp_path / ".bashrc"
    profile = tmp_path / ".bash_profile"
    line = 'export PATH="/home/u/.local/bin:$PATH"\n'
    writers = unguarded_path_writers(
        {bashrc: line, profile: line}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc, profile)}


def test_unrelated_directory_is_not_reported(tmp_path: Path) -> None:
    from installer.rcclean import unguarded_path_writers

    rc = tmp_path / ".bashrc"
    text = 'export PATH="/opt/other/bin:$PATH"\n'
    assert (
        unguarded_path_writers({rc: text}, {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}) == {}
    )


def test_scan_rc_path_writers_reads_real_files_and_skips_unreadable(tmp_path: Path) -> None:
    """A Doctor that raises on an unreadable rc file is worse than one that
    reports a cause it could not determine."""
    from installer.rcclean import scan_rc_path_writers

    bashrc = tmp_path / ".bashrc"
    bashrc.write_text('export PATH="/home/u/.local/bin:$PATH"\n')
    missing = tmp_path / ".does-not-exist"
    binary = tmp_path / ".binaryrc"
    binary.write_bytes(b"\xff\xfe\x00export PATH=/home/u/.local/bin:$PATH\n")

    writers = scan_rc_path_writers(
        [bashrc, missing, binary], {Path("/home/u/.local/bin")}, {"HOME": "/home/u"}
    )
    assert writers == {Path("/home/u/.local/bin"): (bashrc,)}
