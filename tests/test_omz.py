import shlex
from pathlib import Path

import pytest

from installer import omz
from installer.omz import (
    MANAGED_PLUGINS,
    OmzPluginsError,
    disable_plugins,
    enable_plugins,
    ensure_zshrc_template,
    omz_present,
    omz_root,
    owned_plugins,
    plugins_in,
    plugins_owned,
    remove_plugins,
    write_plugins,
)

_ZSHRC = (
    'export ZSH="$HOME/.oh-my-zsh"\n'
    'ZSH_THEME="robbyrussell"\n'
    "plugins=(z sudo)\n"
    "source $ZSH/oh-my-zsh.sh\n"
)


def _sandbox(tmp_path: Path, content: str = _ZSHRC) -> tuple[Path, Path]:
    """A .zshrc to edit and the managed rc file that holds the ownership record."""
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(content)
    return zshrc, tmp_path / ".myshellrc"


def test_enable_adds_only_the_missing_names_and_preserves_the_rest() -> None:
    out = enable_plugins(_ZSHRC)
    assert "plugins=(z sudo git docker)" in out
    assert out.replace("plugins=(z sudo git docker)", "plugins=(z sudo)") == _ZSHRC


def test_enable_is_idempotent_and_never_duplicates() -> None:
    once = enable_plugins(_ZSHRC)
    assert enable_plugins(once) == once
    from_git = enable_plugins("plugins=(git)\n")
    assert from_git == "plugins=(git docker)\n"
    assert from_git.count("git") == 1


def test_disable_removes_only_the_managed_names() -> None:
    src = (
        'export ZSH="$HOME/.oh-my-zsh"\n'
        'ZSH_THEME="robbyrussell"\n'
        "plugins=(z git sudo docker)\n"
        "source $ZSH/oh-my-zsh.sh\n"
    )
    out = disable_plugins(src)
    assert out == _ZSHRC


def test_write_and_remove_round_trip_on_a_real_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    assert plugins_owned(state) is False
    assert write_plugins(zshrc, state) == ("git", "docker")
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ("git", "docker")
    after_write = zshrc.read_text()
    assert "plugins=(z sudo git docker)" in after_write
    assert after_write.replace("plugins=(z sudo git docker)", "plugins=(z sudo)") == _ZSHRC
    assert remove_plugins(zshrc, state) == ("git", "docker")
    assert plugins_owned(state) is False
    assert zshrc.read_text() == _ZSHRC


def test_multi_line_array_is_refused_not_parsed() -> None:
    src = "plugins=(\n  git\n  z\n)\nsource x\n"
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        enable_plugins(src)
    assert disable_plugins(src) == src


def test_a_zshrc_with_no_plugins_line_raises_on_enable_and_no_ops_on_disable() -> None:
    src = 'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\n'
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        enable_plugins(src)
    assert disable_plugins(src) == src


def test_missing_file_gets_the_oh_my_zsh_template_then_enables_plugins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    missing = tmp_path / ".zshrc"
    state = tmp_path / ".myshellrc"
    added = write_plugins(missing, state)
    assert missing.exists()
    text = missing.read_text()
    assert "source $ZSH/oh-my-zsh.sh" in text
    assert "plugins=(git docker)" in text
    assert added == ("docker",)
    assert remove_plugins(tmp_path / "nope", state) == ()


def test_ensure_zshrc_template_is_idempotent_when_already_sourced(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(_ZSHRC)
    assert ensure_zshrc_template(zshrc) is False
    assert zshrc.read_text() == _ZSHRC


def test_ensure_zshrc_template_appends_when_zshrc_only_sources_myshellrc(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text('source "$HOME/.myshellrc"\n')
    assert ensure_zshrc_template(zshrc) is True
    text = zshrc.read_text()
    assert 'source "$HOME/.myshellrc"' in text
    assert "source $ZSH/oh-my-zsh.sh" in text
    assert "plugins=(git)" in text


def test_ensure_zshrc_template_orders_export_plugins_then_source(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    original = 'source "$HOME/.myshellrc"\n'
    zshrc.write_text(original)
    assert ensure_zshrc_template(zshrc) is True
    text = zshrc.read_text()
    assert text.startswith(original)
    assert "tools-installer" not in text
    export_at = text.index('export ZSH="$HOME/.oh-my-zsh"\n')
    plugins_at = text.index("plugins=(git)\n")
    source_at = text.index("source $ZSH/oh-my-zsh.sh\n")
    assert export_at < plugins_at < source_at


def test_ensure_zshrc_template_is_byte_stable_and_preserves_a_symlink(tmp_path: Path) -> None:
    repo_dir = tmp_path / "dotfiles"
    repo_dir.mkdir()
    real_zshrc = repo_dir / "zshrc"
    real_zshrc.write_text('source "$HOME/.myshellrc"\n')
    zshrc = tmp_path / ".zshrc"
    zshrc.symlink_to(real_zshrc)
    assert ensure_zshrc_template(zshrc) is True
    first = real_zshrc.read_text()
    assert zshrc.is_symlink()
    assert zshrc.resolve() == real_zshrc
    assert ensure_zshrc_template(zshrc) is False
    assert real_zshrc.read_text() == first
    assert zshrc.is_symlink()
    assert zshrc.resolve() == real_zshrc


def test_ensure_zshrc_template_ignores_a_commented_framework_filename(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    original = '# see oh-my-zsh.sh for the framework\nsource "$HOME/.myshellrc"\n'
    zshrc.write_text(original)
    assert ensure_zshrc_template(zshrc) is True
    text = zshrc.read_text()
    assert text.startswith(original)
    export_at = text.index('export ZSH="$HOME/.oh-my-zsh"\n')
    plugins_at = text.index("plugins=(git)\n")
    source_at = text.index("source $ZSH/oh-my-zsh.sh\n")
    assert export_at < plugins_at < source_at


def test_commented_out_plugins_line_is_never_matched() -> None:
    src = "# plugins=(git)\nsource $ZSH/oh-my-zsh.sh\n"
    with pytest.raises(OmzPluginsError, match=r"plugins=\("):
        enable_plugins(src)
    assert disable_plugins(src) == src


def test_ensure_zshrc_template_recognizes_the_guarded_source_idiom(tmp_path: Path) -> None:
    """WR-06: `[ -f "$ZSH/oh-my-zsh.sh" ] && source "$ZSH/oh-my-zsh.sh"` is a
    common, fully correct idiom -- before this fix it was classified as "not
    sourced" (the old pattern only recognized source/. at the very start of
    the line), so a fully source-correct .zshrc using it (plugins already
    evaluated BEFORE the guarded source, exactly as real oh-my-zsh requires)
    got a second, unconditional export ZSH=/source pair appended instead of
    being left alone. The module's own stated contract ("source-correct
    files are left unchanged") is what this pins."""
    zshrc = tmp_path / ".zshrc"
    original = 'plugins=(git)\n[ -f "$ZSH/oh-my-zsh.sh" ] && source "$ZSH/oh-my-zsh.sh"\n'
    zshrc.write_text(original)

    assert ensure_zshrc_template(zshrc) is False
    assert zshrc.read_text() == original


@pytest.mark.parametrize(
    "original",
    (
        '[ -f "$ZSH/oh-my-zsh.sh" ] && source "$ZSH/oh-my-zsh.sh"\nplugins=(git)\n',
        'test -f "$ZSH/oh-my-zsh.sh"; source "$ZSH/oh-my-zsh.sh"\nplugins=(git)\n',
    ),
)
def test_ensure_zshrc_template_repairs_ordering_after_a_shell_operator(
    tmp_path: Path, original: str
) -> None:
    """WR-06: both the &&-guarded and ;-separated forms are recognized as
    executable source statements a real shell would run -- not just source
    at the very start of the line -- so a plugins=(...) placed AFTER either
    form is correctly repaired (relocated before the source line, the same
    existing repair an unguarded source already gets) instead of the file
    being left as "not sourced" and a duplicate export/source pair appended
    to the end (the actual pre-fix bug, reproduced live in 15.6-REVIEW.md)."""
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(original)

    assert ensure_zshrc_template(zshrc) is True
    text = zshrc.read_text()
    assert "tools-installer" not in text
    # Exactly one source statement -- never a second, duplicate export/source
    # pair appended below the original (guarded) one.
    assert text.count("oh-my-zsh.sh") == 2  # the [ -f ... ] test target + the source target
    plugins_at = text.index("plugins=(git)")
    source_at = text.index("source ")
    assert plugins_at < source_at


def test_ensure_zshrc_template_still_ignores_a_comment_naming_the_guarded_idiom(
    tmp_path: Path,
) -> None:
    """WR-06's widened detection must not widen past "a comment never
    counts": a line that only NAMES the guarded idiom inside a comment is
    still not an executable source statement."""
    zshrc = tmp_path / ".zshrc"
    original = '# [ -f "$ZSH/oh-my-zsh.sh" ] && source "$ZSH/oh-my-zsh.sh"\n'
    zshrc.write_text(original)

    assert ensure_zshrc_template(zshrc) is True
    text = zshrc.read_text()
    assert text.startswith(original)
    assert "source $ZSH/oh-my-zsh.sh" in text


def test_repair_refuses_to_relocate_a_plugins_line_indented_inside_a_block(
    tmp_path: Path,
) -> None:
    """WR-05: `_locate`'s own regex deliberately allows leading indentation
    so an indented plugins=(...) is still recognized for enable/disable, but
    relocating it in the template repair has no awareness of the enclosing
    if/case/function block -- popping it out and reinserting it before the
    source line silently turns a conditional plugin set into an
    unconditional one and leaves the original conditional an empty no-op.
    Refused, and the file left byte-identical."""
    zshrc = tmp_path / ".zshrc"
    original = 'source $ZSH/oh-my-zsh.sh\nif [[ -n "$X" ]]; then\n  plugins=(git)\nfi\n'
    zshrc.write_text(original)

    assert ensure_zshrc_template(zshrc) is False
    assert zshrc.read_text() == original


def test_last_matching_line_wins() -> None:
    src = "plugins=(a)\nZSH_THEME=x\nplugins=(b)\n"
    out = enable_plugins(src)
    assert out == "plugins=(a)\nZSH_THEME=x\nplugins=(b git docker)\n"


def test_indentation_and_trailing_comment_are_preserved() -> None:
    src = "export ZSH=x\n  plugins=(z)  # my plugins\nsource y\n"
    out = enable_plugins(src)
    assert out == "export ZSH=x\n  plugins=(z git docker)  # my plugins\nsource y\n"


def test_empty_array_and_ragged_whitespace() -> None:
    assert enable_plugins("plugins=()\n") == "plugins=(git docker)\n"
    assert enable_plugins("plugins=(  z   sudo  )\n") == "plugins=(z sudo git docker)\n"


def test_disable_on_an_array_without_the_managed_names_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    assert plugins_owned(state) is False
    assert disable_plugins(_ZSHRC) == _ZSHRC
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == _ZSHRC


def test_disable_removes_a_plugin_the_user_had_before() -> None:
    src = "plugins=(git z)\n"
    assert disable_plugins(src) == "plugins=(z)\n"


def test_plugins_in_reports_the_array_contents() -> None:
    assert plugins_in("plugins=(git)\n") == ("git",)
    assert plugins_in("plugins=(docker git)\n") == ("docker", "git")
    assert plugins_in(_ZSHRC) == ("z", "sudo")
    assert plugins_in("ZSH_THEME=x\n") == ()


def test_write_does_not_touch_the_file_when_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    assert write_plugins(zshrc, state) == ("git", "docker")
    enabled = zshrc.read_text()
    mtime = zshrc.stat().st_mtime_ns
    assert write_plugins(zshrc, state) == ()
    assert zshrc.read_text() == enabled
    assert zshrc.stat().st_mtime_ns == mtime
    # Re-applying does not widen the record beyond what was actually added.
    assert owned_plugins(state) == ("git", "docker")


def test_omz_present_detects_the_home_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert omz_present(tmp_path, {}) is False
    (tmp_path / ".oh-my-zsh").mkdir()
    assert omz_present(tmp_path, {}) is True


def test_omz_present_accepts_a_valid_zsh_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    custom = tmp_path / "custom-omz"
    custom.mkdir()
    assert omz_present(tmp_path, {"ZSH": str(custom)}) is True
    assert omz_present(tmp_path, {"ZSH": str(tmp_path / "missing")}) is False
    assert omz_present(tmp_path, {"ZSH": ""}) is False


def test_omz_root_agrees_with_omz_present_on_every_case(tmp_path: Path) -> None:
    """CR-01: omz_present is now defined directly in terms of omz_root, so the
    two answers can never disagree -- this pins that relationship rather than
    re-testing each branch independently."""
    custom = tmp_path / "custom-omz"
    missing = tmp_path / "missing"
    for environ in ({}, {"ZSH": str(custom)}, {"ZSH": str(missing)}, {"ZSH": ""}):
        assert (omz_root(tmp_path, environ) is not None) == omz_present(tmp_path, environ)

    assert omz_root(tmp_path, {}) is None
    (tmp_path / ".oh-my-zsh").mkdir()
    assert omz_root(tmp_path, {}) == tmp_path / ".oh-my-zsh"

    custom.mkdir()
    # The conventional default takes priority when both exist, matching
    # omz_present's own preference order.
    assert omz_root(tmp_path, {"ZSH": str(custom)}) == tmp_path / ".oh-my-zsh"


def test_ensure_zshrc_template_writes_the_real_root_when_one_is_supplied(
    tmp_path: Path,
) -> None:
    """CR-01: a caller that already resolved the real oh-my-zsh directory
    (terminal_shell's synchronizer, via omz_root) must have that root land in
    the emitted export -- not the conventional ~/.oh-my-zsh default."""
    zshrc = tmp_path / ".zshrc"
    real_root = tmp_path / "dotfiles" / "custom-omz"
    assert ensure_zshrc_template(zshrc, real_root) is True
    text = zshrc.read_text()
    assert f"export ZSH={real_root}" in text
    assert "$HOME/.oh-my-zsh" not in text


def test_a_multi_line_array_after_a_single_line_one_is_refused_not_silently_edited() -> None:
    # zsh honors the LAST assignment. Editing the single-line array above a
    # multi-line one would report success while loading nothing.
    src = "plugins=(git)\n# later\nplugins=(\n  zsh-autosuggestions\n)\n"
    with pytest.raises(OmzPluginsError, match="multi-line"):
        enable_plugins(src)
    assert disable_plugins(src) == src
    assert plugins_in("plugins=(git docker)\n# later\nplugins=(\n  z\n)\n") == ()


def test_a_single_line_array_after_a_multi_line_one_is_still_editable() -> None:
    # The reverse order is fine: the single-line array is the final assignment.
    src = "plugins=(\n  z\n)\nplugins=(git)\n"
    assert enable_plugins(src) == "plugins=(\n  z\n)\nplugins=(git docker)\n"


def test_write_refuses_a_shadowed_array_and_leaves_the_file_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    shadowed = "plugins=(git)\nplugins=(\n  z\n)\n"
    zshrc, state = _sandbox(tmp_path, shadowed)
    with pytest.raises(OmzPluginsError, match="multi-line"):
        write_plugins(zshrc, state)
    assert zshrc.read_text() == shadowed
    assert plugins_owned(state) is False
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == shadowed


def test_a_crlf_zshrc_is_edited_and_keeps_its_line_endings() -> None:
    src = 'ZSH_THEME="robbyrussell"\r\nplugins=(z)\r\nsource $ZSH/oh-my-zsh.sh\r\n'
    out = enable_plugins(src)
    assert out == (
        'ZSH_THEME="robbyrussell"\r\nplugins=(z git docker)\r\nsource $ZSH/oh-my-zsh.sh\r\n'
    )
    assert set(MANAGED_PLUGINS) <= set(plugins_in(out))
    assert disable_plugins(out) == src


def test_a_crlf_trailing_comment_survives_the_rewrite() -> None:
    assert enable_plugins("  plugins=(z)  # mine\r\n") == "  plugins=(z git docker)  # mine\r\n"


def test_quoted_plugin_names_are_recognised_not_duplicated() -> None:
    # `plugins=("git" docker)` is unusual but legal zsh; "git" names the same
    # plugin as git, so enabling must not append a redundant second entry.
    assert enable_plugins('plugins=("git" docker)\n') == 'plugins=("git" docker)\n'
    assert plugins_in('plugins=("git" "docker")\n') == ("git", "docker")
    # A name kept is written back verbatim — quoting style is never restyled.
    assert enable_plugins('plugins=("z")\n') == 'plugins=("z" git docker)\n'
    # ...and a quoted managed name is still removable.
    assert disable_plugins('plugins=("git" z docker)\n') == "plugins=(z)\n"


def test_the_zshrc_rewrite_is_atomic_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    zshrc.chmod(0o600)
    write_plugins(zshrc, state)
    assert "plugins=(z sudo git docker)" in zshrc.read_text()
    # Mode carried over from the original, and no sibling temp file survives.
    assert zshrc.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == [".myshellrc", ".zshrc"]


def _fail_writes_to(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    """Make the atomic commit fail for exactly one destination file.

    This module writes two files and the ordering between them is the whole
    subject of these tests, so a blanket `os.replace` patch cannot express which
    of the two was refused — it would abort on whichever happens to be written
    first and pass for the wrong reason.
    """
    real = omz.os.replace

    def guarded(src: Path, dst: Path) -> None:
        if dst == target:
            raise OSError("disk full")
        real(src, dst)

    monkeypatch.setattr(omz.os, "replace", guarded)


def test_a_failed_rewrite_leaves_the_original_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    _fail_writes_to(monkeypatch, zshrc)
    with pytest.raises(OSError, match="disk full"):
        write_plugins(zshrc, state)
    # The whole point of the temp+replace: the user's .zshrc is never truncated,
    # and the partial temp file is cleaned up rather than left beside it.
    assert zshrc.read_text() == _ZSHRC
    assert list(tmp_path.glob("*.tools-installer.tmp")) == []
    # The reserved claim is rolled back to exactly what it was: no record.
    assert plugins_owned(state) is False


def test_a_failed_rewrite_rolls_the_claim_back_to_the_names_it_already_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Re-enabling after the user hand-deleted our name: the rollback must restore
    # the PRIOR record, not clear it — clearing would strand the names still in
    # the array from the first enable.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(git)\nsource x\n")
    assert write_plugins(zshrc, state) == ("docker",)
    zshrc.write_text("plugins=(git)\nsource x\n")
    _fail_writes_to(monkeypatch, zshrc)
    with pytest.raises(OSError, match="disk full"):
        write_plugins(zshrc, state)
    assert zshrc.read_text() == "plugins=(git)\nsource x\n"
    assert owned_plugins(state) == ("docker",)


def test_a_failed_record_write_strands_no_names_in_the_users_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The enable-path hole: the claim is reserved BEFORE the .zshrc edit, so a
    # refused record write aborts before anything is added. Recording afterwards
    # instead would leave `docker` in the user's array with nothing owning it,
    # and remove_plugins could never take it back out.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    _fail_writes_to(monkeypatch, state)
    with pytest.raises(OSError, match="disk full"):
        write_plugins(zshrc, state)
    assert zshrc.read_text() == _ZSHRC
    assert plugins_owned(state) is False
    assert list(tmp_path.glob("*.tools-installer.tmp")) == []


def test_a_failed_removal_keeps_the_record_so_the_advertised_retry_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The mirror of the enable path, and the more damaging direction. Both the
    # CLI and the TUI answer a failed sweep with "check permissions and re-run",
    # so the record must still describe reality when that re-run happens.
    # Clearing it first made that advice the one action that could not work: the
    # retry saw no record, reported nothing to uninstall, and left our names in
    # the user's .zshrc permanently.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(z kubectl)\nsource x\n")
    assert write_plugins(zshrc, state) == ("git", "docker")
    modified = zshrc.read_text()

    _fail_writes_to(monkeypatch, zshrc)
    with pytest.raises(OSError, match="disk full"):
        remove_plugins(zshrc, state)
    assert zshrc.read_text() == modified
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ("git", "docker")

    # "Permissions fixed, re-run": the retry now actually recovers.
    monkeypatch.undo()
    assert remove_plugins(zshrc, state) == ("git", "docker")
    assert zshrc.read_text() == "plugins=(z kubectl)\nsource x\n"
    assert plugins_owned(state) is False


def test_the_record_is_written_atomically_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The record is the only thing that can tell a name this installer added from
    # one the user wrote, so it gets the same temp+replace treatment as .zshrc:
    # a truncated record cannot be repaired (see the orphan-marker test below).
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    state.write_text("export EDITOR=vim\n")
    state.chmod(0o600)
    write_plugins(zshrc, state)
    assert state.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == [".myshellrc", ".zshrc"]
    remove_plugins(zshrc, state)
    assert sorted(p.name for p in tmp_path.iterdir()) == [".myshellrc", ".zshrc"]


def test_an_orphaned_begin_marker_reads_as_no_record_rather_than_wedging_the_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # What a truncated record write could leave behind. `strip_block` refuses to
    # strip an unpaired begin marker, so reading it as "owns nothing" reported
    # the policy ON with no way to ever switch it off. An unclosed block is not
    # a record, and enabling over it recovers a well-formed one.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(git)\nsource x\n")
    state.write_text("# >>> tools-installer omz-plugins >>>\n# added: docker\n")
    assert plugins_owned(state) is False
    assert owned_plugins(state) == ()
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == "plugins=(git)\nsource x\n"

    assert write_plugins(zshrc, state) == ("docker",)
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ("docker",)
    assert remove_plugins(zshrc, state) == ("docker",)
    assert plugins_owned(state) is False


def test_a_hand_authored_array_is_never_ours_to_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The CR-01 case: `git` ships in Oh-My-Zsh's own default .zshrc and `docker`
    # is its commonest addition, so content cannot prove ownership. This user
    # never enabled the policy; a full uninstall must not touch their file.
    monkeypatch.setenv("HOME", str(tmp_path))
    hand_written = 'ZSH_THEME="robbyrussell"\nplugins=(git docker kubectl)\nsource x\n'
    zshrc, state = _sandbox(tmp_path, hand_written)
    assert plugins_owned(state) is False
    assert owned_plugins(state) == ()
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.read_text() == hand_written


def test_only_the_names_this_installer_added_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The user already had `git`; only `docker` is ours, so only `docker` goes.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(git kubectl)\nsource x\n")
    assert write_plugins(zshrc, state) == ("docker",)
    assert owned_plugins(state) == ("docker",)
    assert zshrc.read_text() == "plugins=(git kubectl docker)\nsource x\n"
    assert remove_plugins(zshrc, state) == ("docker",)
    assert zshrc.read_text() == "plugins=(git kubectl)\nsource x\n"


def test_enabling_over_an_array_that_already_has_everything_owns_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Enabling is still a real state change (the row reads ON, the policy is
    # ours to switch off) but it added nothing, so it may remove nothing.
    monkeypatch.setenv("HOME", str(tmp_path))
    original = "plugins=(git docker)\nsource x\n"
    zshrc, state = _sandbox(tmp_path, original)
    assert write_plugins(zshrc, state) == ()
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ()
    assert remove_plugins(zshrc, state) == ()
    assert plugins_owned(state) is False
    assert zshrc.read_text() == original


def test_the_record_is_an_inert_comment_block_in_the_managed_rc_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # .zshrc never carries a tools-installer marker, so the record lives in the
    # rc file this installer owns — and every line of it is a comment.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path)
    state.write_text("export EDITOR=vim\n")
    write_plugins(zshrc, state)
    body = state.read_text()
    assert "tools-installer" not in zshrc.read_text()
    assert "export EDITOR=vim" in body
    assert "# added: git docker" in body
    assert all(
        line.startswith("#") for line in body.split("\n") if line and line != "export EDITOR=vim"
    )
    remove_plugins(zshrc, state)
    # Teardown leaves the user's own rc content alone.
    assert state.read_text().strip() == "export EDITOR=vim"


def test_a_record_survives_being_read_back_from_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=()\nsource x\n")
    write_plugins(zshrc, state)
    assert owned_plugins(tmp_path / ".myshellrc") == ("git", "docker")
    # An unrelated rc file is not a record.
    assert plugins_owned(tmp_path / ".bashrc") is False


def test_a_recorded_name_the_user_already_deleted_is_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # We added `docker`, the user then deleted it by hand. Disabling has nothing
    # left to do, so .zshrc is not rewritten — but the record still clears.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(git)\nsource x\n")
    assert write_plugins(zshrc, state) == ("docker",)
    zshrc.write_text("plugins=(git)\nsource x\n")
    mtime = zshrc.stat().st_mtime_ns
    assert remove_plugins(zshrc, state) == ()
    assert zshrc.stat().st_mtime_ns == mtime
    assert plugins_owned(state) is False


def test_removal_raises_rather_than_dropping_the_record_when_the_array_is_shadowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CR-01: the user enables the policy, then converts their array to the
    # multi-line form (oh-my-zsh's own idiom) -- the single-line array this
    # module edited is now dead. disable_plugins is total and reports content
    # unchanged for a shadowed array, which is indistinguishable from "found
    # the array, nothing matched" -- clearing the record on that would report
    # success while `git`/`docker` are still on disk with no record left to
    # take them back out. Removal must raise and leave the record intact.
    monkeypatch.setenv("HOME", str(tmp_path))
    zshrc, state = _sandbox(tmp_path, "plugins=(z)\nsource x\n")
    assert write_plugins(zshrc, state) == ("git", "docker")
    shadowed = "plugins=(z git docker)\nplugins=(\n  z\n)\n"
    zshrc.write_text(shadowed)
    with pytest.raises(OmzPluginsError, match="multi-line"):
        remove_plugins(zshrc, state)
    assert zshrc.read_text() == shadowed
    assert plugins_owned(state) is True
    assert owned_plugins(state) == ("git", "docker")
    # A retry after the array is fixed recovers cleanly -- the record survived.
    zshrc.write_text("plugins=(z git docker)\nsource x\n")
    assert remove_plugins(zshrc, state) == ("git", "docker")
    assert zshrc.read_text() == "plugins=(z)\nsource x\n"
    assert plugins_owned(state) is False


def test_atomic_write_replaces_a_symlinks_target_not_the_symlink_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CR-02: a dotfile-manager setup commonly symlinks ~/.zshrc into a repo
    # elsewhere. os.replace(tmp, path) renames OVER whatever `path` names --
    # if `path` is the symlink itself, that deletes the symlink and leaves a
    # plain file, silently falling out of sync with the repo it pointed at.
    monkeypatch.setenv("HOME", str(tmp_path))
    repo_dir = tmp_path / "dotfiles"
    repo_dir.mkdir()
    real_zshrc = repo_dir / "zshrc"
    real_zshrc.write_text("plugins=(z)\nsource x\n")
    zshrc = tmp_path / ".zshrc"
    zshrc.symlink_to(real_zshrc)
    state = tmp_path / ".myshellrc"

    assert write_plugins(zshrc, state) == ("git", "docker")

    assert zshrc.is_symlink()
    assert zshrc.resolve() == real_zshrc
    assert real_zshrc.read_text() == "plugins=(z git docker)\nsource x\n"


def test_write_plugins_inserts_default_array_before_a_live_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    sourced = 'export ZSH="$HOME/.oh-my-zsh"\nsource $ZSH/oh-my-zsh.sh\n'
    zshrc, state = _sandbox(tmp_path, sourced)
    assert write_plugins(zshrc, state) == ("docker",)
    text = zshrc.read_text()
    assert text.startswith('export ZSH="$HOME/.oh-my-zsh"\n')
    plugins_at = text.index("plugins=(git docker)\n")
    source_at = text.index("source $ZSH/oh-my-zsh.sh\n")
    assert plugins_at < source_at
    assert owned_plugins(state) == ("docker",)
    assert "tools-installer" not in text


def test_write_plugins_refuses_a_source_correct_multiline_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    src = 'export ZSH="$HOME/.oh-my-zsh"\nsource $ZSH/oh-my-zsh.sh\nplugins=(\n  git\n)\n'
    zshrc, state = _sandbox(tmp_path, src)
    with pytest.raises(OmzPluginsError, match="multi-line"):
        write_plugins(zshrc, state)
    assert zshrc.read_text() == src
    assert plugins_owned(state) is False


def test_write_plugins_preserves_comments_crlf_and_unrelated_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plugins line here is deliberately UNINDENTED (WR-05, 15.6-REVIEW.md):
    an indented plugins=(...) is presumed nested inside an if/case/function
    body and _repair_sourced_template now refuses to relocate it, since doing
    so would silently turn a conditional plugin set into an unconditional
    one. This test's own purpose (comment/CRLF/unrelated-source preservation
    across a repair+enable pass) is orthogonal to that safety check, so it
    keeps a top-level array -- indented-and-refused is covered separately by
    test_repair_refuses_to_relocate_a_plugins_line_indented_inside_a_block."""
    monkeypatch.setenv("HOME", str(tmp_path))
    src = (
        "# keep this comment\r\n"
        "source /etc/profile\r\n"
        'export ZSH="$HOME/.oh-my-zsh"\r\n'
        "source $ZSH/oh-my-zsh.sh\r\n"
        "plugins=(z git)  # mine\r\n"
    )
    zshrc, state = _sandbox(tmp_path, src)
    zshrc.write_bytes(src.encode())
    assert write_plugins(zshrc, state) == ("docker",)
    text = zshrc.read_bytes().decode()
    assert text.startswith("# keep this comment\r\n")
    assert "source /etc/profile\r\n" in text
    assert "plugins=(z git docker)  # mine\r\n" in text
    plugins_at = text.index("plugins=(z git docker)  # mine\r\n")
    source_at = text.index("source $ZSH/oh-my-zsh.sh\r\n")
    assert plugins_at < source_at
    assert owned_plugins(state) == ("docker",)


def test_write_plugins_repairs_source_before_plugins_and_is_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    src = 'export ZSH="$HOME/.oh-my-zsh"\nsource $ZSH/oh-my-zsh.sh\nplugins=(git)\n'
    zshrc, state = _sandbox(tmp_path, src)
    assert write_plugins(zshrc, state) == ("docker",)
    first = zshrc.read_text()
    assert first == (
        'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git docker)\n'
        'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\n'
    )
    assert owned_plugins(state) == ("docker",)
    assert write_plugins(zshrc, state) == ()
    assert zshrc.read_text() == first
    assert ensure_zshrc_template(zshrc) is False
    assert zshrc.read_text() == first


def test_non_utf8_zshrc_is_refused_as_an_oserror_without_changing_bytes(tmp_path: Path) -> None:
    """CR-02: a Latin-1 byte must not escape as a bare UnicodeDecodeError.

    UnicodeDecodeError is a ValueError, so it would slip past every caller's
    `except OSError` -- including the six terminal-sync lifecycle call sites.
    """
    zshrc = tmp_path / ".zshrc"
    original = "# caf\xe9 comment\nsource $ZSH/oh-my-zsh.sh\n".encode("latin-1")
    zshrc.write_bytes(original)

    with pytest.raises(OmzPluginsError, match="UTF-8") as caught:
        ensure_zshrc_template(zshrc)

    assert isinstance(caught.value, OSError)
    assert zshrc.read_bytes() == original


def test_write_plugins_passes_the_root_on_repair(tmp_path: Path) -> None:
    """A .zshrc with no source line gets its template from the real root, not the default."""
    zshrc, state = _sandbox(tmp_path, "export FOO=1\n")
    custom = tmp_path / "custom"
    write_plugins(zshrc, state, root=custom)
    text = zshrc.read_text()
    assert f"export ZSH={shlex.quote(str(custom))}" in text
    assert "$HOME/.oh-my-zsh" not in text


def test_write_plugins_keeps_the_default_root_without_one(tmp_path: Path) -> None:
    zshrc, state = _sandbox(tmp_path, "export FOO=1\n")
    write_plugins(zshrc, state)
    assert 'export ZSH="$HOME/.oh-my-zsh"' in zshrc.read_text()


_SOURCE_ONLY = "plugins=(git)\nsource $ZSH/oh-my-zsh.sh\n"


def test_a_zshrc_without_a_theme_gets_robbyrussell_before_the_source_line() -> None:
    content = 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git)\nsource $ZSH/oh-my-zsh.sh\nalias x=y\n'
    assert omz.set_theme(content, "robbyrussell") == (
        'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git)\n'
        'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\nalias x=y\n'
    )


def test_an_existing_theme_is_never_overwritten(tmp_path: Path) -> None:
    agnoster = 'ZSH_THEME="agnoster"\nsource $ZSH/oh-my-zsh.sh\n'
    assert omz.set_theme(agnoster, "robbyrussell") == agnoster
    assert omz.set_theme(agnoster, "", replace="robbyrussell") == agnoster
    zshrc, state = _sandbox(tmp_path, agnoster)
    assert omz.apply_theme(zshrc, state, "robbyrussell") == omz.ThemeResult("yours", "agnoster")
    assert zshrc.read_text() == agnoster
    commented = '# ZSH_THEME="agnoster"\nsource $ZSH/oh-my-zsh.sh\n'
    assert 'ZSH_THEME="robbyrussell"\nsource' in omz.set_theme(commented, "robbyrussell")


def test_no_source_line_writes_nothing(tmp_path: Path) -> None:
    zshrc, state = _sandbox(tmp_path, "plugins=(git)\nalias x=y\n")
    assert omz.apply_theme(zshrc, state, "robbyrussell") == omz.ThemeResult("no-source", None)
    assert zshrc.read_text() == "plugins=(git)\nalias x=y\n"
    assert not state.exists()


def test_starship_replaces_only_the_installer_default(tmp_path: Path) -> None:
    zshrc, state = _sandbox(tmp_path, _SOURCE_ONLY)
    assert omz.apply_theme(zshrc, state, "robbyrussell") == omz.ThemeResult("added", "robbyrussell")
    assert omz.owned_theme(state) == "robbyrussell"
    assert omz.apply_theme(zshrc, state, "") == omz.ThemeResult("replaced", "")
    assert 'ZSH_THEME=""\nsource' in zshrc.read_text()
    assert omz.owned_theme(state) == ""
    user = tmp_path / "user"
    user.mkdir()
    zshrc, state = _sandbox(user, 'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\n')
    assert omz.apply_theme(zshrc, state, "") == omz.ThemeResult("yours", "robbyrussell")
    assert zshrc.read_text() == 'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\n'


def test_the_default_is_empty_when_the_starship_block_is_present(tmp_path: Path) -> None:
    state = tmp_path / ".myshellrc"
    assert omz.default_theme(state) == "robbyrussell"
    state.write_text(
        '# >>> tools-installer tweak:starship >>>\neval "$(starship init zsh)"\n'
        "# <<< tools-installer tweak:starship <<<\n"
    )
    assert omz.default_theme(state) == ""


def test_write_plugins_adds_the_default_theme(tmp_path: Path) -> None:
    zshrc, state = _sandbox(
        tmp_path, 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(z)\nsource $ZSH/oh-my-zsh.sh\n'
    )
    write_plugins(zshrc, state)
    assert 'ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh' in zshrc.read_text()
    remove_plugins(zshrc, state)
    assert 'ZSH_THEME="robbyrussell"\n' in zshrc.read_text()
    user = tmp_path / "user"
    user.mkdir()
    zshrc, state = _sandbox(user, 'plugins=(z)\nZSH_THEME="agnoster"\nsource $ZSH/oh-my-zsh.sh\n')
    write_plugins(zshrc, state)
    assert zshrc.read_text().count("ZSH_THEME") == 1
    assert 'ZSH_THEME="agnoster"\nsource' in zshrc.read_text()


def test_an_exported_or_indented_theme_counts_as_a_theme() -> None:
    exported = 'export ZSH_THEME="agnoster"\nsource $ZSH/oh-my-zsh.sh\n'
    assert omz.set_theme(exported, "robbyrussell") == exported
    indented = 'if [ -n "$X" ]; then\n  ZSH_THEME="agnoster"\nfi\nsource $ZSH/oh-my-zsh.sh\n'
    assert omz.set_theme(indented, "robbyrussell") == indented
    commented = '# export ZSH_THEME="x"\nsource $ZSH/oh-my-zsh.sh\n'
    assert 'ZSH_THEME="robbyrussell"\nsource' in omz.set_theme(commented, "robbyrussell")
    recorded = 'export ZSH_THEME="robbyrussell"\nsource $ZSH/oh-my-zsh.sh\n'
    assert omz.set_theme(recorded, "", replace="robbyrussell") == (
        'export ZSH_THEME=""\nsource $ZSH/oh-my-zsh.sh\n'
    )


def test_a_failed_zshrc_write_leaves_the_record_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zshrc, state = _sandbox(tmp_path, _SOURCE_ONLY)
    _fail_writes_to(monkeypatch, zshrc)
    with pytest.raises(OSError, match="disk full"):
        omz.apply_theme(zshrc, state, "robbyrussell")
    assert zshrc.read_text() == _SOURCE_ONLY
    assert omz.owned_theme(state) is None


def test_a_failed_zshrc_write_keeps_the_previous_theme_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zshrc, state = _sandbox(tmp_path, _SOURCE_ONLY)
    assert omz.apply_theme(zshrc, state, "robbyrussell") == omz.ThemeResult("added", "robbyrussell")
    _fail_writes_to(monkeypatch, zshrc)
    with pytest.raises(OSError, match="disk full"):
        omz.apply_theme(zshrc, state, "")
    assert omz.owned_theme(state) == "robbyrussell"


_TUNED = 'export ZSH="$HOME/.oh-my-zsh"\nplugins=(git z)\nsource $ZSH/oh-my-zsh.sh\n'


def test_plugins_refusal_names_what_write_plugins_would_refuse(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert omz.plugins_refusal(missing) is None
    ok, _ = _sandbox(tmp_path, _TUNED)
    assert omz.plugins_refusal(ok) is None
    multi = tmp_path / "multi"
    multi.mkdir()
    zshrc, state = _sandbox(multi, "plugins=(\n  git\n)\nsource $ZSH/oh-my-zsh.sh\n")
    reason = omz.plugins_refusal(zshrc)
    assert reason is not None
    with pytest.raises(OmzPluginsError) as caught:
        write_plugins(zshrc, state)
    assert str(caught.value) == reason  # the two share one preflight
    assert omz.plugins_refusal(zshrc) == reason  # read-only: the file is unchanged
    assert zshrc.read_text() == "plugins=(\n  git\n)\nsource $ZSH/oh-my-zsh.sh\n"


def test_plugins_refusal_is_read_only_for_a_file_that_would_get_the_template(
    tmp_path: Path,
) -> None:
    zshrc, _ = _sandbox(tmp_path, "export PATH=$PATH\n")
    assert omz.plugins_refusal(zshrc) is None
    assert zshrc.read_text() == "export PATH=$PATH\n"


def test_omz_plugins_existing_list_gains_only_docker(tmp_path: Path) -> None:
    zshrc, state = _sandbox(tmp_path, _TUNED)
    assert write_plugins(zshrc, state) == ("docker",)
    assert "plugins=(git z docker)" in zshrc.read_text()
    assert owned_plugins(state) == ("docker",)  # git was the user's, never recorded as added


def test_omz_plugins_on_missing_and_empty_arrays(tmp_path: Path) -> None:
    zshrc, state = _sandbox(tmp_path, "source $ZSH/oh-my-zsh.sh\n")
    write_plugins(zshrc, state)
    assert "plugins=(git docker)\n" in zshrc.read_text()
    empty = tmp_path / "empty"
    empty.mkdir()
    zshrc, state = _sandbox(empty, "plugins=()\nsource $ZSH/oh-my-zsh.sh\n")
    assert write_plugins(zshrc, state) == ("git", "docker")
    assert "plugins=(git docker)\n" in zshrc.read_text()


def test_omz_plugins_second_install_adds_nothing(tmp_path: Path) -> None:
    zshrc, state = _sandbox(tmp_path, _TUNED)
    write_plugins(zshrc, state)
    rc_before, zshrc_before = state.read_bytes(), zshrc.read_bytes()
    assert write_plugins(zshrc, state) == ()
    assert (state.read_bytes(), zshrc.read_bytes()) == (rc_before, zshrc_before)


def test_omz_plugins_keeps_non_ascii_comments(tmp_path: Path) -> None:
    text = "# café ñandú — 日本語\nplugins=(git z)\nsource $ZSH/oh-my-zsh.sh\n# fin ✓\n"
    zshrc, state = _sandbox(tmp_path, text)
    write_plugins(zshrc, state)
    after = zshrc.read_text(encoding="utf-8")
    assert after.replace(" docker", "").replace('ZSH_THEME="robbyrussell"\n', "") == text


def _other_writer_after(monkeypatch: pytest.MonkeyPatch, name: str, zshrc: Path) -> None:
    """Make another program edit `zshrc` right after the module's read, before its commit."""
    real = getattr(omz, name)

    def wrapped(*args: object, **kwargs: object) -> object:
        result = real(*args, **kwargs)
        zshrc.write_text(zshrc.read_text() + "# another writer\n")
        return result

    monkeypatch.setattr(omz, name, wrapped)


def test_omz_plugins_refuses_a_zshrc_changed_before_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zshrc, state = _sandbox(tmp_path, _TUNED)
    _other_writer_after(monkeypatch, "_record_owned", zshrc)
    with pytest.raises(OmzPluginsError, match="changed"):
        write_plugins(zshrc, state)
    assert zshrc.read_text() == _TUNED + "# another writer\n"
    assert not state.exists() or not plugins_owned(state)


def test_omz_theme_refuses_a_zshrc_changed_before_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zshrc, state = _sandbox(tmp_path, _SOURCE_ONLY)
    _other_writer_after(monkeypatch, "_record_theme", zshrc)
    with pytest.raises(OmzPluginsError, match="changed"):
        omz.apply_theme(zshrc, state, "robbyrussell")
    assert zshrc.read_text() == _SOURCE_ONLY + "# another writer\n"
    assert omz.owned_theme(state) is None
