"""Manage ~/.myshellrc as one marker-delimited PATH block, and wire `source` into rc files.

Every write is idempotent: only the marked block is ever rewritten, user content is
preserved, and entries are never duplicated across runs. Every write in this module
goes through installer/atomic.py, because a truncated rc file is unrecoverable and
these files are edited read-modify-write.
"""

import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from installer.atomic import OLD_SUFFIX, atomic_write_bytes, atomic_write_text, staged_sibling
from installer.model import Tool
from installer.platform import Platform
from installer.resolve import resolve_methods

_PATH_BEGIN = "# >>> tools-installer path >>>"
_PATH_END = "# <<< tools-installer path <<<"
_SOURCE_BEGIN = "# >>> tools-installer source >>>"
_SOURCE_END = "# <<< tools-installer source <<<"
_SHELLRC_BEGIN = "# >>> tools-installer consolidated shellrc >>>"
_SHELLRC_END = "# <<< tools-installer consolidated shellrc <<<"
_STUB_BEGIN = "# >>> tools-installer shellrc stub >>>"
_STUB_END = "# <<< tools-installer shellrc stub <<<"


def _resolve_home(path: Path, home: Path) -> Path:
    """Resolve only the current-user tilde against an injected home directory."""
    raw = str(path)
    if raw == "~":
        return home
    if raw.startswith("~/"):
        return home / raw[2:]
    return path


def collect_bin_dirs(
    tools: list[Tool],
    platform: Platform,
    default: Path,
    exists: Callable[[Path], bool] = Path.is_dir,
    *,
    home: Path | None = None,
) -> list[Path]:
    """The default bin dir plus each platform-applicable method's existing bin_dir.

    The default is always managed. A declared bin_dir is managed only when the
    directory exists on disk: a missing dir means the tool was never installed,
    and wiring it into PATH (or reporting it broken) is noise. Disk presence —
    not PATH probing — avoids the bootstrap chicken-and-egg: right after
    installing brew, `brew` is not on PATH yet but /opt/homebrew/bin exists.

    `home`, when given, is used only to resolve a bare `~` or `~/...` default —
    letting a caller inject a non-default home for tests, while every other
    path is unaffected.
    """
    resolved_home = Path.home() if home is None else home
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path, *, require_exists: bool) -> None:
        resolved = _resolve_home(path, resolved_home)
        if resolved in seen or (require_exists and not exists(resolved)):
            return
        seen.add(resolved)
        dirs.append(resolved)

    add(default, require_exists=False)
    for tool in tools:
        for method in resolve_methods(tool, platform):
            raw = method.params.get("bin_dir")
            if isinstance(raw, str) and raw:
                add(Path(raw), require_exists=True)
    return dirs


def path_export_guard(directory: Path) -> str:
    """Emit a self-deduping PATH line that adds directory at most once per shell.

    Re-sourcing this line in a nested or child shell (or in the same shell
    multiple times) adds the directory to PATH at most once. This is achieved
    through a case-guarded self-deduping idiom that pnpm uses and that
    `installer/rcclean.py::find_duplicate_path_lines` already documents as
    safe to leave alone (the scanner does not flag lines starting with `case`).

    Paths are double-quoted but not otherwise escaped: they come only from the
    trusted registry and Path.home(), never from user input. Do not feed
    user-supplied paths here without shell-quoting first.

    When the directory has a second spelling (e.g. /home -> /var/home on
    Fedora, or /var -> /private/var on macOS), the guard matches both spellings
    to detect if the directory is already on PATH under either name. However,
    the VALUE prepended onto PATH is always the DECLARED spelling (never
    canonicalized), so that `installer/doctor.py::audit_path` and
    `installer/rcclean.py` -- which both compare raw PATH entries against
    declared directory strings -- continue to recognize what this project writes.

    The conditional expansion `${PATH:+:$PATH}` is security-critical: an empty
    PATH component (the trailing empty string after a colon-join) resolves to
    the current working directory in every POSIX shell. An empty starting PATH
    becomes exactly the managed directory with no empty component, so the
    managed shell cannot execute a same-named script out of the user's cwd.

    The guard reads PATH through `${PATH-}` (default-applying expansion), not
    bare `$PATH`, so the line does not abort a shell running under `set -u`
    with PATH unset.
    """
    declared = str(directory)
    try:
        resolved = str(directory.resolve())
    except OSError:
        resolved = declared

    if resolved == declared:
        pattern = f":{declared}:"
        guard_pattern = f'*"{pattern}"*'
    else:
        pattern1 = f":{declared}:"
        pattern2 = f":{resolved}:"
        guard_pattern = f'*"{pattern1}"*|*"{pattern2}"*'

    value = f"{declared}${{PATH:+:$PATH}}"
    return f'case ":${{PATH-}}:" in {guard_pattern}) ;; *) export PATH="{value}";;esac'


def managed_block(bin_dirs: list[Path]) -> str:
    """Marker-delimited block exporting each bin dir onto PATH.

    Each directory is emitted as a self-deduping case-guarded line through
    `path_export_guard`, so re-sourcing the block N times adds each directory
    at most once. Paths are double-quoted but not otherwise escaped: they come
    only from the trusted registry and Path.home(), never from user input. Do
    not feed user-supplied paths here without shell-quoting first.
    """
    lines = [_PATH_BEGIN]
    lines.extend(path_export_guard(directory) for directory in bin_dirs)
    lines.append(_PATH_END)
    return "\n".join(lines)


def apply_block(content: str, block: str, begin: str = _PATH_BEGIN, end: str = _PATH_END) -> str:
    """Replace an existing begin..end block in content, else append it. Idempotent.

    Pairs the LAST begin marker with the following end marker, so re-applying to a
    file that has an orphan begin (no end) replaces only the well-formed block and
    never eats user content between the orphan marker and the managed block.
    """
    lines = content.split("\n")
    if begin in lines:
        start = max(index for index, line in enumerate(lines) if line == begin)
        for stop in range(start, len(lines)):
            if lines[stop] == end:
                merged = lines[:start] + block.split("\n") + lines[stop + 1 :]
                return "\n".join(merged)
    base = content.rstrip("\n")
    if base:
        return f"{base}\n\n{block}\n"
    return f"{block}\n"


def strip_block(content: str, begin: str, end: str) -> str:
    """Return content with the last begin..end block removed; unchanged if absent.

    Mirrors apply_block's last-begin pairing, so an orphan begin (no matching
    end) is left untouched rather than eating the rest of the file.
    """
    lines = content.split("\n")
    if begin not in lines:
        return content
    start = max(index for index, line in enumerate(lines) if line == begin)
    for stop in range(start, len(lines)):
        if lines[stop] == end:
            return "\n".join(lines[:start] + lines[stop + 1 :])
    return content


def remove_managed_block(path: Path) -> None:
    """Strip the managed PATH block from `path`, preserving the rest. Idempotent.

    A missing file, or a file without the block, is left untouched.
    """
    if not path.exists():
        return
    original = path.read_text()
    stripped = strip_block(original, _PATH_BEGIN, _PATH_END)
    if stripped != original:
        atomic_write_text(path, stripped)


def remove_source_block(path: Path) -> None:
    """Strip this project's own source block from `path`, preserving the rest.

    Mirrors `remove_managed_block` exactly, down to the atomic write: a missing
    file is a no-op, a file without the block is left untouched, and the file is
    rewritten only when stripping actually changed it.

    Plan 15.8-06 calls this when an rc file already reaches ~/.myshellrc through
    the consolidated ~/.shellrc stub, so this project's own block is removed
    rather than left duplicating the route. The file is a user-owned .bashrc or
    .zshrc, which is exactly why the write goes through `atomic_write_text`: a
    truncating write there is the unrecoverable outcome `installer/atomic.py`
    exists to prevent.
    """
    if not path.exists():
        return
    original = path.read_text()
    stripped = strip_block(original, _SOURCE_BEGIN, _SOURCE_END)
    if stripped != original:
        atomic_write_text(path, stripped)


def has_managed_block(path: Path) -> bool:
    """True when `path` exists and contains the managed PATH block begin marker."""
    if not path.exists():
        return False
    lines = path.read_text().split("\n")
    return _PATH_BEGIN in lines


def write_myshellrc(bin_dirs: list[Path], path: Path) -> None:
    """Idempotently write the managed PATH block into ~/.myshellrc, preserving the rest."""
    existing = path.read_text() if path.exists() else ""
    atomic_write_text(path, apply_block(existing, managed_block(bin_dirs)))


def write_managed_path(rc_path: Path, bin_dirs: list[Path]) -> None:
    """Write the managed PATH block directly into an rc file (split-inline mode).

    Idempotent: only the marked block is rewritten, surrounding user content is
    preserved. Used when the user opts out of the ~/.myshellrc indirection.
    """
    existing = rc_path.read_text() if rc_path.exists() else ""
    atomic_write_text(rc_path, apply_block(existing, managed_block(bin_dirs)))


def ensure_source(rc_path: Path, myshellrc_path: Path) -> None:
    """Ensure rc_path sources ~/.myshellrc via a marker block, without duplicating it."""
    block = "\n".join(
        [
            _SOURCE_BEGIN,
            f'[ -f "{myshellrc_path}" ] && . "{myshellrc_path}"',
            _SOURCE_END,
        ]
    )
    existing = rc_path.read_text() if rc_path.exists() else ""
    atomic_write_text(rc_path, apply_block(existing, block, begin=_SOURCE_BEGIN, end=_SOURCE_END))


def consolidation_block(body: str) -> str:
    """The foreign shellrc content wrapped in this project's own marker pair.

    Uses its own markers, never the PATH block's, so foreign content can never
    land inside the span `write_myshellrc` rewrites, and re-applying the block
    is idempotent by construction. The provenance comment carries no timestamp,
    hostname or other varying value: a repeat run must produce a byte-identical
    block or idempotency is lost.
    """
    lines = [
        _SHELLRC_BEGIN,
        "# Content consolidated from the generic ~/.shellrc by tools-installer.",
        "# The original file now sources this file; edit the content here.",
        *body.split("\n"),
        _SHELLRC_END,
    ]
    return "\n".join(lines)


def consolidation_stub(myshellrc_path: Path) -> str:
    """The marked stub that replaces ~/.shellrc and sources ~/.myshellrc.

    Mirrors `ensure_source`'s existing `[ -f ... ] && . ...` idiom. The marker
    is what makes the stub recognizable on the next run, so a completed run is
    never re-consolidated.
    """
    return "\n".join(
        [
            _STUB_BEGIN,
            "# tools-installer consolidated this file; edit ~/.myshellrc instead.",
            f'[ -f "{myshellrc_path}" ] && . "{myshellrc_path}"',
            _STUB_END,
        ]
    )


_LineVerdict = Literal["none", "rewritable", "ambiguous"]
SourceVerdict = Literal["yes", "no", "unprovable"]
_SOURCE_COMMANDS = {".", "source"}
# A leading redirection, in two forms that must NOT be conflated: the operator
# standing alone (its target is the NEXT word) and the operator with its target
# glued on (the target is part of this word). One regex covering both consumed
# the following word in the glued case, which ate the source command itself.
_REDIRECTION_BARE = re.compile(r"\d*(?:>>|>&|>\||>|<>|<&|<)")
_REDIRECTION_GLUED = re.compile(r"\d*(?:>>|>&|>\||>|<>|<&|<)\S+")
# Reserved words and precommand modifiers that may legally precede a command and
# still let it run. `time` is the dangerous one: it is a shell KEYWORD, not an
# external binary, so `time . file` really sources the file under bash, zsh and
# sh -- verified in all three. Omitting it classified such a line as `none`, so
# consolidation copied it forward verbatim into ~/.myshellrc and produced a file
# that killed bash with SIGSEGV on every startup. `nocorrect` and `noglob` are
# zsh precommand modifiers with the same property. Note that an ESCAPED `\time`
# is a different thing entirely -- it resolves to the external binary, which
# cannot source into the parent shell -- so it is correctly not listed here.
_COMMAND_PREFIXES = {
    "if",
    "then",
    "elif",
    "else",
    "while",
    "until",
    "do",
    "!",
    "time",
    "nocorrect",
    "noglob",
}


@dataclass(frozen=True)
class _SourceInspection:
    """The conservative facts found while inspecting one physical line."""

    verdict: _LineVerdict
    has_source_command: bool
    resolves_to_target: bool
    has_unresolvable_source: bool


# The verdict for a physical line that is a CONTINUATION of the line above: the
# joined logical line already carries the real verdict on its first line.
_NO_SOURCE = _SourceInspection("none", False, False, False)


def _physical_lines(text: str) -> list[str]:
    """Split on newline ONLY, matching what a POSIX shell calls a line.

    `_physical_lines(str)` also splits on \r, \v, \f, \x1c-\x1e, \x85, U+2028 and
    U+2029. A shell treats none of those as a line separator, so using it
    normalized a CRLF file to LF and tore a single shell line in two at a form
    feed -- both of which break D-04's promise that user content is copied
    forward VERBATIM. The trailing empty element from a text ending in a newline
    is dropped, so this matches `splitlines()` exactly for newline-only text and
    every existing caller stays aligned.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _normalized_word(word: str) -> str:
    """Approximate shell quote removal for one whitespace-delimited word."""
    return word.replace("\\", "").replace('"', "").replace("'", "")


def _is_assignment_word(word: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", word) is not None


def _command_head(segment: str) -> tuple[list[str], bool, bool]:
    """Return words after simple command prefixes and source wrappers.

    This is intentionally a small collection of string rules, not a shell
    lexer. Anything that needs quote state, nesting, or expansion tracking is
    refused by the caller instead of being interpreted here.
    """
    words = segment.strip().split()
    had_prefix = False
    had_wrapper = False

    while words:
        normalized = _normalized_word(words[0])
        # A redirection may lead a command: `>/dev/null . f` and `2>/dev/null . f`
        # all really source f, under bash, sh AND zsh. Treating the redirection as
        # the command word classified the line `none`, which is the direction that
        # ships a self-sourcing file. A bare operator carries its target in the
        # next word (`> /dev/null . f`), so that word is consumed too.
        if _REDIRECTION_BARE.fullmatch(words[0]):
            had_prefix = True
            words.pop(0)
            if words:  # the operator's target is the next word
                words.pop(0)
            continue
        if _REDIRECTION_GLUED.fullmatch(words[0]):
            had_prefix = True
            words.pop(0)
            continue
        if normalized in _COMMAND_PREFIXES or _is_assignment_word(words[0]):
            had_prefix = True
            words.pop(0)
            continue
        if normalized in {"command", "builtin"}:
            had_wrapper = True
            words.pop(0)
            while words and _normalized_word(words[0]).startswith("-"):
                words.pop(0)
            continue
        break
    return words, had_prefix, had_wrapper


def _split_command_segments(line: str) -> list[str]:
    """Split at obvious command separators without attempting shell parsing.

    The `&` in a duplicating redirection (`2>&1`, `<&0`) is NOT a separator. Left
    unprotected it tore `2>&1 . f` into two segments, leaving the second starting
    with the redirection's target digit, so the source command that followed was
    never seen in command position at all.
    """
    home_sentinel = "__TOOLS_INSTALLER_HOME_EXPANSION__"
    dup_sentinel = "__TOOLS_INSTALLER_DUP_REDIRECT__"
    protected = line.replace("${HOME}", home_sentinel)
    protected = re.sub(r"([<>])&", rf"\1{dup_sentinel}", protected)
    return [
        segment.replace(dup_sentinel, "&").replace(home_sentinel, "${HOME}")
        for segment in re.split(r"&&|\|\||[;|&(){}]", protected)
    ]


def _expanded_argument(raw: str, target: Path) -> Path | None:
    """Resolve the intentionally small set of statically knowable arguments."""
    candidate = raw.replace('"', "").replace("'", "")
    if not candidate or any(character in candidate for character in "*?["):
        return None
    if "`" in candidate or "$(" in candidate:
        return None

    home = target.parent
    if candidate == "~":
        candidate = str(home)
    elif candidate.startswith("~/"):
        candidate = str(home / candidate[2:])
    elif candidate == "$HOME":
        candidate = str(home)
    elif candidate.startswith("${HOME}/"):
        candidate = str(home / candidate[len("${HOME}/") :])
    elif candidate.startswith("$HOME/"):
        candidate = str(home / candidate[len("$HOME/") :])

    if "$" in candidate or "~" in candidate or not os.path.isabs(candidate):
        return None
    return Path(candidate)


def _single_quoted_literal(raw: str) -> str | None:
    """The literal content of a fully single-quoted word, else None.

    Single quotes suppress EVERY expansion in every POSIX shell, so
    `. '$HOME/.myshellrc'` sources a file literally named `$HOME/.myshellrc`
    relative to the cwd -- not the target. Stripping quotes before expanding
    made that word look like the target and marked the line rewritable, which
    would have commented out a working command that sources a different file.
    """
    if len(raw) < 2 or raw[0] != "'" or raw[-1] != "'":
        return None
    inner = raw[1:-1]
    return None if "'" in inner else inner


def _resolves_to(raw: str | None, target: Path) -> tuple[bool, bool]:
    """Return ``(is_resolvable, is_target)`` for a candidate source argument."""
    if raw is None:
        return False, False
    literal = _single_quoted_literal(raw)
    if literal is not None:
        if not os.path.isabs(literal):
            # Statically known, and it cannot be the absolute target.
            return True, False
        return True, os.path.realpath(literal) == os.path.realpath(target)
    expanded = _expanded_argument(raw, target)
    if expanded is None:
        return False, False
    return True, os.path.realpath(expanded) == os.path.realpath(target)


def _simple_argument(raw: str) -> bool:
    """Whether ``raw`` has no quotes or one matching quote layer."""
    if not any(character in raw for character in "'\""):
        return True
    if len(raw) < 2 or raw[0] not in "'\"" or raw[-1] != raw[0]:
        return False
    return raw[1:-1].count(raw[0]) == 0


def _is_dynamic_word(word: str) -> bool:
    return "$" in word or "`" in word


def _inspect_source_line(
    line: str,
    target: Path,
    *,
    continued_before: bool = False,
) -> _SourceInspection:
    """Classify one line using conservative command-position string rules."""
    if line.lstrip().startswith("#"):
        return _SourceInspection("none", False, False, False)

    stripped = line.strip()
    if not stripped:
        return _SourceInspection("none", False, False, False)

    has_source = False
    resolves_to_target = False
    has_unresolvable = False
    rewritable = False
    segments = _split_command_segments(stripped)

    for segment in segments:
        words, had_prefix, had_wrapper = _command_head(segment)
        if not words:
            continue
        command_word = words[0]
        normalized_command = _normalized_word(command_word)
        if normalized_command == "eval":
            continue

        dynamic_command = _is_dynamic_word(command_word)
        is_source = normalized_command in _SOURCE_COMMANDS
        if not is_source and not dynamic_command:
            continue

        raw_argument = words[1] if len(words) > 1 else None
        resolvable, is_target = _resolves_to(raw_argument, target)
        if dynamic_command:
            if is_target:
                has_source = True
                resolves_to_target = True
                rewritable = False
            continue

        has_source = True
        if not resolvable:
            has_unresolvable = True
            continue
        if not is_target:
            continue

        resolves_to_target = True
        simple_line = (
            len(segments) == 1
            and not had_prefix
            and not had_wrapper
            and len(words) == 2
            and command_word == normalized_command
            and command_word in _SOURCE_COMMANDS
            and _simple_argument(raw_argument or "")
            and not stripped.endswith("\\")
            and not continued_before
        )
        rewritable = rewritable or simple_line

    if has_unresolvable or resolves_to_target and not rewritable:
        return _SourceInspection("ambiguous", has_source, resolves_to_target, has_unresolvable)
    if resolves_to_target and rewritable:
        return _SourceInspection("rewritable", has_source, True, False)
    return _SourceInspection("none", has_source, False, has_unresolvable)


def classify_source_line(line: str, target: Path) -> _SourceInspection:
    """Expose the pure line classifier for focused tests and diagnostics."""
    return _inspect_source_line(line, target)


def _classify_source_lines(text: str, target: Path) -> list[_SourceInspection]:
    """Classify every physical line without attempting to parse shell syntax.

    A backslash continuation is JOINED before classification, because the shell
    joins it too: `. ~/.mysh\\` + `ellrc` is one command sourcing one file, and
    classifying the halves separately saw neither. The joined verdict is carried
    by the FIRST physical line of the logical line and never `rewritable` when it
    spans more than one -- rewriting a multi-line command by commenting only its
    first line would leave the remainder as live shell.
    """
    if not text:
        return []
    lines = _physical_lines(text)
    inspections: list[_SourceInspection] = [_NO_SOURCE] * len(lines)
    index = 0
    while index < len(lines):
        start = index
        joined = lines[index]
        while joined.rstrip().endswith("\\") and index + 1 < len(lines):
            joined = f"{joined.rstrip()[:-1]}{lines[index + 1]}"
            index += 1
        inspection = _inspect_source_line(joined, target)
        if index > start and inspection.verdict == "rewritable":
            inspection = _SourceInspection(
                "ambiguous",
                inspection.has_source_command,
                inspection.resolves_to_target,
                inspection.has_unresolvable_source,
            )
        inspections[start] = inspection
        index += 1
    return inspections


def _has_live_eval(line: str) -> bool:
    """Return whether a simple command-position rule sees a live ``eval``."""
    if line.lstrip().startswith("#"):
        return False
    for segment in _split_command_segments(line.strip()):
        words, _had_prefix, _had_wrapper = _command_head(segment)
        if words and _normalized_word(words[0]) == "eval":
            return True
    return False


def _has_here_document_opener(line: str) -> bool:
    """Recognize common here-document openers without parsing their body."""
    if line.lstrip().startswith("#"):
        return False
    # The delimiter may be quoted in three ways, and a BACKSLASH-escaped one
    # (`<<\EOF`) is the fourth -- it is as common as the quoted forms and means
    # exactly the same thing to the shell. Missing it let the body be scanned as
    # shell, and `consolidated_body` then commented out a line inside it,
    # silently altering unmanaged content.
    #
    # The opener also need not follow whitespace or a command separator: a
    # redirection may be glued to it (`cat >f<<EOF`), so `>` and `<` join the
    # set of characters an opener may follow.
    return (
        re.search(
            # `<<` not part of a `<<<` here-string, anywhere on the line: an
            # opener may be glued to a redirection target (`cat >out<<EOF`), so
            # requiring a separator in front of it missed real openers.
            r"(?<!<)<<(?!<)-?\s*"
            r"(?:'[^']*'|\"[^\"]*\"|\\?[A-Za-z_][A-Za-z0-9_-]*)",
            line,
        )
        is not None
    )


def _source_inspection_reason(path: Path, line_number: int, line: str) -> str:
    return (
        f"{path} line {line_number} contains a source command this tool cannot prove safe: "
        f"{line!r}. Remove the construct or consolidate the file by hand."
    )


def _source_target_reason(path: Path, line_number: int, line: str) -> str:
    return (
        f"{path} line {line_number} contains an ambiguous source of the consolidation target: "
        f"{line!r}. Consolidate the file by hand."
    )


def _text_sources_target(text: str, target: Path) -> tuple[bool, int | None, bool]:
    """Return target-hit, line number, and unprovable-source presence."""
    target_line: int | None = None
    unprovable = False
    for number, inspection in enumerate(_classify_source_lines(text, target), start=1):
        if inspection.resolves_to_target and target_line is None:
            target_line = number
        if inspection.has_unresolvable_source:
            unprovable = True
    return target_line is not None, target_line, unprovable


def sources_file(text: str, target: Path) -> SourceVerdict:
    """Whether `text` live-sources `target`: ``yes``, ``no``, or ``unprovable``.

    Deliberately BROADER than the rewriter. Its caller (`configure_path`) is
    deciding whether to add a SECOND route to ~/.myshellrc, not whether it may
    edit a line, so a shape this module refuses to rewrite must still count as
    reaching the file. Answering `no` there would wire a duplicate route and run
    the canonical file twice on every shell startup.

    `unprovable` must NOT be folded into `yes` by any caller. A live source whose
    argument does not statically resolve (`source "$ZDOTDIR/foo"`) or a live
    `eval` (`eval "$(brew shellenv)"`) is ORDINARY content in a real rc file; a
    predicate that answered `yes` on those would stop this project from wiring
    PATH for most users. The correct handling is to take the ordinary route and
    SAY SO -- plan 15.8-06 prints a diagnostic naming the line.
    """
    reaches, _line_number, unprovable_argument = _text_sources_target(text, target)
    if reaches:
        return "yes"
    if unprovable_argument or any(_has_live_eval(line) for line in _physical_lines(text)):
        return "unprovable"
    return "no"


def consolidated_body(shellrc_text: str, myshellrc_path: Path) -> str:
    """Return `shellrc_text` with every rewritable self-source line disabled.

    PRECONDITION: `consolidation_refusal` has already returned None for this
    text. That is why there is no branch here for an ambiguous line -- by the
    time this runs, the only line that can resolve to `myshellrc_path` is the
    one simple shape the classifier certified as rewritable. Calling this on
    unvetted text is a programming error, not an input to defend against.

    The original text is preserved verbatim on the comment, so content is
    DISABLED, never deleted (D-04). Nothing else is altered: same line count,
    same order, same trailing whitespace on every untouched line.
    """
    lines = _physical_lines(shellrc_text)
    inspections = _classify_source_lines(shellrc_text, myshellrc_path)
    rewritten = [
        (
            f"# tools-installer disabled this line; "
            f"{myshellrc_path} is now the file it was sourcing: {line}"
        )
        if inspection.verdict == "rewritable"
        else line
        for line, inspection in zip(lines, inspections, strict=True)
    ]
    body = "\n".join(rewritten)
    if shellrc_text.endswith("\n"):
        return f"{body}\n"
    return body


def consolidation_refusal(
    shellrc_text: str,
    myshellrc_text: str,
    *,
    shellrc_path: Path,
    myshellrc_path: Path,
    rc_paths: tuple[Path, ...] = (),
) -> str | None:
    """Return a refusal reason for unsafe content, or ``None`` when safe.

    This deliberately refuses rather than guessing. Missing a source line can
    create a self-sourcing loop; commenting out a compound line or here-document
    body can silently destroy content. The fail-safe mirrors ``installer/omz.py``'s
    multi-line-array refusal and ``installer/daemon.py``'s sentinel refusal.
    """
    for number, line in enumerate(_physical_lines(shellrc_text), start=1):
        stripped = line.strip()
        if stripped.startswith("# >>> tools-installer") or stripped.startswith(
            "# <<< tools-installer"
        ):
            return (
                f"{shellrc_path} line {number} carries a tools-installer marker; remove it "
                f"or consolidate the file by hand."
            )
        if _has_here_document_opener(line):
            return (
                f"{shellrc_path} line {number} opens a here-document; this tool does not "
                f"parse its body. Remove it or consolidate the file by hand."
            )
        if _has_live_eval(line):
            return (
                f"{shellrc_path} line {number} uses eval, which can source any file; "
                f"remove it or consolidate the file by hand."
            )

    inspections = _classify_source_lines(shellrc_text, myshellrc_path)
    for number, (line, inspection) in enumerate(
        zip(_physical_lines(shellrc_text), inspections, strict=True), start=1
    ):
        if inspection.has_unresolvable_source:
            return _source_inspection_reason(shellrc_path, number, line)
        if inspection.verdict == "ambiguous":
            return _source_target_reason(shellrc_path, number, line)

    reaches_shellrc, line_number, _unprovable = _text_sources_target(myshellrc_text, shellrc_path)
    if reaches_shellrc and line_number is not None:
        return (
            f"{myshellrc_path} line {line_number} already sources {shellrc_path}; replacing "
            f"{shellrc_path} with a stub would create a sourcing loop. Consolidate by hand."
        )
    # The OTHER direction of the same cycle, and it needs no classifier hole to
    # reach. The content being copied into ~/.myshellrc may itself source an rc
    # file that the caller is about to wire back to ~/.myshellrc, closing
    # .bashrc -> .myshellrc -> .bashrc. Nothing above sees it: before the run
    # there is no loop at all, so every other check passes and consolidation
    # reports success while producing a shell that dies of stack exhaustion.
    for rc_path in rc_paths:
        reaches_rc, rc_line, _unprovable_rc = _text_sources_target(shellrc_text, rc_path)
        if reaches_rc and rc_line is not None:
            return (
                f"{shellrc_path} line {rc_line} sources {rc_path}, which this run would wire "
                f"back to {myshellrc_path}; consolidating would make the two files source each "
                f"other. Consolidate by hand."
            )
    return None


_Status = Literal["absent", "already", "refused", "consolidated"]


@dataclass(frozen=True)
class ShellrcConsolidation:
    """The outcome of one `consolidate_shellrc` call.

    `reason` is populated only by the refusal outcome. A `Literal` status keeps
    the four local values typed without adding a module-wide enum.
    """

    status: _Status
    reason: str | None = None


class ShellrcRefusal(RuntimeError):
    """A typed, catchable refusal raised by callers of `consolidate_shellrc`.

    Nothing in this module raises it: it is defined here because the reason
    strings it will carry are produced here. Plan 15.8-06 raises it from the
    Doctor apply route and widens `installer/ui_common.py::run_live` to catch
    it, so a refusal can never be reported to the user as success.
    """


@dataclass(frozen=True)
class _Snapshot:
    """One identity-bound read of ~/.shellrc.

    `data` and `(device, inode)` come from the same `O_RDONLY|O_NOFOLLOW`
    descriptor, so they describe the SAME file even if the path is replaced
    mid-call. `mode` is the `S_IMODE` the backup's own permissions copy.
    """

    data: bytes
    device: int
    inode: int
    mode: int


def consolidation_precondition(shellrc_path: Path, myshellrc_path: Path) -> str | None:
    """A refusal reason, or None, when neither path is a hazard.

    Answers exactly ONE question: could a write aimed at one of these two paths
    land on a different file? This project's atomic writer resolves a symlinked
    target rather than replacing the symlink (`installer/atomic.py:42`) -- which
    is correct for a dotfile this project owns, and destructive for a foreign
    file it is about to replace.

    The backup's usability is deliberately NOT checked here: it is a separate
    helper that runs after the owned-stub check and needs a snapshot the caller
    has not taken yet. Nothing may move it back into this function.
    """
    if shellrc_path.is_symlink():
        return (
            f"{shellrc_path} is a symlink; a stub write would follow it and replace its "
            f"target because this project's atomic writer resolves a symlinked target by "
            f"design. Remove the link or consolidate by hand."
        )
    if myshellrc_path.is_symlink():
        return (
            f"{myshellrc_path} is a symlink; writing the consolidated content through it "
            f"would replace its target. Remove the link or consolidate by hand."
        )
    # Neither path may be a non-regular file. A FIFO at either path makes the
    # snapshot's `os.open` block FOREVER with no timeout and no way for the user
    # to tell what is wrong -- the installer simply never returns. `lstat` so the
    # link itself is seen; symlinks are already refused above.
    for path in (shellrc_path, myshellrc_path):
        try:
            mode = os.lstat(path).st_mode
        except OSError:
            continue
        if not stat.S_ISREG(mode):
            return (
                f"{path} is not a regular file; refusing rather than reading something "
                f"that may never return. Remove it or consolidate by hand."
            )
    if shellrc_path.exists() and myshellrc_path.exists():
        try:
            same = shellrc_path.samefile(myshellrc_path)
        except OSError:
            # An unanswerable comparison is a refusal, never permission.
            return (
                f"{shellrc_path} and {myshellrc_path} could not be compared; refusing "
                f"rather than guessing whether they are one file."
            )
        if same:
            return (
                f"{shellrc_path} and {myshellrc_path} already refer to one file; there is "
                f"nothing to consolidate and a stub would make it source itself."
            )
    if os.path.realpath(shellrc_path) == os.path.realpath(myshellrc_path):
        return (
            f"{shellrc_path} and {myshellrc_path} resolve to one file; there is nothing "
            f"to consolidate and a stub would make it source itself."
        )
    return None


def _snapshot(path: Path) -> _Snapshot:
    """Read path through one `O_RDONLY|O_NOFOLLOW` descriptor, binding bytes to identity."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        data = b""
        while chunk := os.read(fd, 65536):
            data += chunk
    finally:
        os.close(fd)
    return _Snapshot(data=data, device=st.st_dev, inode=st.st_ino, mode=stat.S_IMODE(st.st_mode))


def _snapshot_matches(path: Path, snapshot: _Snapshot) -> bool:
    """Whether path still has the snapshot's identity AND bytes.

    Any `OSError` from the re-open (removed, or became a symlink) returns False:
    an unanswerable comparison is a refusal, never permission.
    """
    try:
        current = _snapshot(path)
    except OSError:
        return False
    return (
        current.device == snapshot.device
        and current.inode == snapshot.inode
        and (current.data == snapshot.data)
    )


def backup_precondition(shellrc_path: Path, snapshot: _Snapshot) -> str | None:
    """A refusal reason, or None, for an existing backup at OLD_SUFFIX.

    Takes the STEP-3 snapshot rather than re-reading `shellrc_path`, so the bytes
    the backup is compared against and the bytes it is written from are provably
    the same bytes. It is called only AFTER the owned-stub check, so the snapshot
    it sees is guaranteed NOT to be this project's own stub: after a successful
    run the backup holds the ORIGINAL while ~/.shellrc holds the stub, and that
    expected difference must never read as a stale backup.
    """
    backup = staged_sibling(shellrc_path, OLD_SUFFIX)
    try:
        st = os.lstat(backup)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return (
            f"{backup} is not a plain file; it must be a regular file because it is what a "
            f"restoring `mv` will move back."
        )
    try:
        fd = os.open(backup, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return f"{backup} could not be opened safely; refusing rather than guessing what it is."
    try:
        existing = b""
        while chunk := os.read(fd, 65536):
            existing += chunk
    finally:
        os.close(fd)
    if existing != snapshot.data:
        return (
            f"{backup} already holds a different original; move or remove it if you want "
            f"consolidation to proceed."
        )
    if stat.S_IMODE(st.st_mode) != snapshot.mode:
        return (
            f"{backup} has mode {stat.S_IMODE(st.st_mode):04o} but the original had mode "
            f"{snapshot.mode:04o}; a byte-and-mode restoration cannot be promised, so this "
            f"is refused."
        )
    return None


def _is_owned_stub(text: str) -> bool:
    """True when text is a WELL-FORMED stub this project wrote.

    Both markers must be present with the begin before the end. A file carrying
    only one marker is half-written or hand-edited and deliberately does NOT
    report as already consolidated.
    """
    lines = text.split("\n")
    if _STUB_BEGIN not in lines or _STUB_END not in lines:
        return False
    return lines.index(_STUB_BEGIN) < lines.index(_STUB_END)


def consolidate_shellrc(
    shellrc_path: Path,
    myshellrc_path: Path,
    rc_paths: tuple[Path, ...] = (),
) -> ShellrcConsolidation:
    """Consolidate a generic ~/.shellrc into ~/.myshellrc, leaving one canonical file.

    The CHECK order is FIXED and may not be re-ordered: (1) absence, (2) symlink
    / same-file hazards, (3) identity-bound snapshot and UTF-8 decode, (4) owned
    stub returning `already`, (5) backup validation against a snapshot guaranteed
    not to be a stub, then the writes. Validating the backup before step 4 breaks
    idempotency: after a successful run the backup holds the ORIGINAL while
    ~/.shellrc holds the stub, so a bytes comparison at that point always differs
    and every repeat run would refuse instead of returning `already`.

    The WRITE order is copy-forward, then backup, then stub. It is the inversion
    of omz.py's record-before-write and is deliberate: the only write that REMOVES
    a copy of the content is the stub, and it is last, so every intermediate crash
    state has the content in at least two places and the next run re-applies the
    same idempotent block. No rollback branch is needed for the crash case because
    the failure state is already the safe one.

    The backup makes D-04's recorded reversibility something the user can act on
    with a single `mv`: it holds the original's raw BYTES and mode, was created
    no-clobber, and a mismatching pre-existing backup refuses the whole operation
    rather than being preserved alongside a replacement the user cannot undo.

    ~/.shellrc is foreign by construction and is only ever read as opaque bytes --
    never sourced, evaluated, or executed, not even to inspect it. ~/.myshellrc is
    the only file this project owns and edits.
    """
    if not shellrc_path.exists():
        # `exists()` follows links, so a dangling link is not a file to consolidate.
        return ShellrcConsolidation(status="absent")

    hazard = consolidation_precondition(shellrc_path, myshellrc_path)
    if hazard is not None:
        return ShellrcConsolidation(status="refused", reason=hazard)

    try:
        snapshot = _snapshot(shellrc_path)
    except OSError as exc:
        return ShellrcConsolidation(
            status="refused", reason=f"{shellrc_path} could not be read: {exc}"
        )

    try:
        original_text = snapshot.data.decode("utf-8")
    except UnicodeDecodeError:
        return ShellrcConsolidation(
            status="refused",
            reason=(
                f"{shellrc_path} is not valid UTF-8; refusing to rewrite it. "
                f"Consolidate it by hand."
            ),
        )

    if _is_owned_stub(original_text):
        return ShellrcConsolidation(status="already")

    # A non-UTF-8 ~/.myshellrc is a typed refusal, exactly as a non-UTF-8
    # ~/.shellrc already is. `UnicodeDecodeError` is a ValueError, NOT an
    # OSError, so `ui_common.run_live` would not catch it and the Doctor screen
    # would take a raw traceback instead of showing a reason.
    try:
        myshellrc_text = myshellrc_path.read_text() if myshellrc_path.exists() else ""
    except UnicodeDecodeError:
        return ShellrcConsolidation(
            status="refused",
            reason=(
                f"{myshellrc_path} is not valid UTF-8; refusing to merge into it. "
                f"Consolidate it by hand."
            ),
        )
    content_conflict = consolidation_refusal(
        original_text,
        myshellrc_text,
        shellrc_path=shellrc_path,
        myshellrc_path=myshellrc_path,
        rc_paths=rc_paths,
    )
    if content_conflict is not None:
        return ShellrcConsolidation(status="refused", reason=content_conflict)

    conflict = backup_precondition(shellrc_path, snapshot)
    if conflict is not None:
        return ShellrcConsolidation(status="refused", reason=conflict)

    pre_myshellrc_bytes = myshellrc_path.read_bytes() if myshellrc_path.exists() else None
    existing = pre_myshellrc_bytes.decode("utf-8") if pre_myshellrc_bytes is not None else ""
    # The rewrite applies to the COPY only. `snapshot.data` still holds the
    # original bytes and is what the backup below is written from, so D-04's
    # one-`mv` reversibility is unaffected by anything done here.
    merged = apply_block(
        existing,
        consolidation_block(consolidated_body(original_text, myshellrc_path)),
        begin=_SHELLRC_BEGIN,
        end=_SHELLRC_END,
    )
    atomic_write_text(myshellrc_path, merged)

    backup = staged_sibling(shellrc_path, OLD_SUFFIX)
    created_backup = False
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, snapshot.data)
        finally:
            os.close(fd)
        os.chmod(backup, snapshot.mode)
        created_backup = True

    if not _snapshot_matches(shellrc_path, snapshot):
        if pre_myshellrc_bytes is None:
            myshellrc_path.unlink(missing_ok=True)
        else:
            atomic_write_bytes(myshellrc_path, pre_myshellrc_bytes)
        if created_backup:
            backup.unlink(missing_ok=True)
        return ShellrcConsolidation(
            status="refused",
            reason=(
                f"{shellrc_path} changed while it was being consolidated; nothing was "
                f"replaced. Re-run once the file is settled."
            ),
        )

    atomic_write_text(shellrc_path, consolidation_stub(myshellrc_path))
    return ShellrcConsolidation(status="consolidated")
