from pathlib import Path

from installer.rcclean import find_duplicate_path_lines, strip_lines


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
