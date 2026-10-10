"""Find and strip duplicate PATH-export lines in shell rc files.

Detection resolves `export VAR=...` assignments declared earlier in the same file
(so installer lines like `$BUN_INSTALL/bin` expand), skips our own managed blocks,
and flags any PATH entry that resolves to a directory we already manage. Used to
clean the redundant lines bun/pnpm/fnm append to .bashrc/.zshrc.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

_MANAGED_BEGINS = ("# >>> tools-installer path >>>", "# >>> tools-installer source >>>")
_MANAGED_ENDS = ("# <<< tools-installer path <<<", "# <<< tools-installer source <<<")
_FOREIGN_BEGIN = re.compile(r"^\s*# >>> (.+?) >>>\s*$")
_FOREIGN_END = re.compile(r"^\s*# <<< (.+?) <<<\s*$")
_REFUSE_MULTI = "adds more than one directory; edit it by hand"
_REFUSE_APPEND = "appends to PATH; guarding would change its order"
_REFUSE_COMPOUND = "shares its line with other commands or a comment; edit it by hand"
_REFUSE_ZSH_ARRAY = "zsh path array; edit it by hand"
_REFUSE_UNRESOLVED = "uses a variable this scan cannot resolve"
_REFUSE_REPLACE = "replaces PATH entirely; edit it by hand"
_OWN_MARKER_PREFIX = "tools-installer"
_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.+?)\s*$")
_PATH_EXPORT = re.compile(r"^\s*(?:export\s+)?PATH=(.+?)\s*$")
_EXPORT_WORD = re.compile(r"^\s*export\s")
_ZSH_PATH_ARRAY = re.compile(r"^\s*(?:export\s+|typeset\s+-U\s+)?path=\((.*)\)\s*$")
_LEADING_THEN_DO = re.compile(r"^\s*(?:then|do)\s+")
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_PATH_REF = re.compile(r"\$\{?PATH\b")
_WORD = re.compile(r"[A-Za-z_]\w*")
_HEREDOC_OPENER = re.compile(r"""<<-?\s*(['"]?)([A-Za-z_]\w*)\1""")
_OPENERS = {
    "if": "fi",
    "while": "done",
    "until": "done",
    "for": "done",
    "select": "done",
    "case": "esac",
}
_CLOSERS = frozenset({"fi", "esac", "done"})
_Frame = tuple[str, bool]


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _expand(value: str, env: Mapping[str, str]) -> str | None:
    """Expand $VAR/${VAR} and a leading ~ using env. Returns None if a var is unknown."""
    resolved = True

    def repl(match: re.Match[str]) -> str:
        nonlocal resolved
        name = match.group(1) or match.group(2)
        if name not in env:
            resolved = False
            return ""
        return env[name]

    expanded = _VAR.sub(repl, value)
    if not resolved:
        return None
    if expanded.startswith("~"):
        home = env.get("HOME", "")
        expanded = home + expanded[1:] if home else expanded
    return expanded


@dataclass(frozen=True)
class _PathLine:
    """One PATH assignment outside a managed block, plus how it may be used.

    targets are expanded segments other than the previous PATH value. simple is
    true only when the whole line is one plain assignment, with no comment and
    no second command. presence_guarded is true when a condition tests PATH, so
    the assignment does not re-add a directory that is already present. text is
    the raw line, kept for a later in-place rewrite.
    """

    index: int
    text: str
    targets: tuple[str, ...]
    simple: bool
    indented: bool
    presence_guarded: bool
    unresolved: bool = False


def _expanded_segments(value: str, env: Mapping[str, str]) -> tuple[str, ...]:
    found: list[str] = []
    for segment in _unquote(value).split(":"):
        if segment in ("$PATH", "${PATH}"):
            continue
        expanded = _expand(segment, env)
        if expanded is not None:
            found.append(expanded)
    return tuple(found)


def _first_word(stripped: str) -> str:
    match = _WORD.match(stripped)
    return match.group(0) if match else ""


def _code_text(line: str) -> str:
    """Length-preserving copy with quoted spans and a trailing comment blanked."""
    chars = list(line)
    in_single = False
    in_double = False
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if in_single:
            chars[index] = " "
            if char == "'":
                in_single = False
            index += 1
            continue
        if in_double:
            chars[index] = " "
            if char == "\\" and index + 1 < length:
                chars[index + 1] = " "
                index += 2
                continue
            if char == '"':
                in_double = False
            index += 1
            continue
        if char == "\\" and index + 1 < length:
            index += 2
            continue
        if char in "'\"":
            chars[index] = " "
            in_single = char == "'"
            in_double = char == '"'
            index += 1
            continue
        if char == "#" and (index == 0 or line[index - 1] in " \t;|&"):
            for rest in range(index, length):
                chars[rest] = " "
            break
        index += 1
    return "".join(chars)


def _has_standalone_closer(line: str, closer: str) -> bool:
    code = _code_text(line)
    return re.search(rf"(?:^|[;\s]|;;){re.escape(closer)}(?:$|[;\s#])", code) is not None


def _condition_references_path(keyword: str, stripped: str) -> bool:
    if keyword in ("for", "select"):
        return False
    if keyword == "case":
        # Known limit: a multi-line case whose word does not reference PATH
        # (for example case ":$PNPM_HOME:" in) leaves its rows unguarded, so
        # they are reported. The real pnpm shape tests PATH.
        match = re.search(r"\bcase\b(.*?)\bin\b", stripped)
        condition = match.group(1) if match else ""
        return _PATH_REF.search(condition) is not None
    rest = stripped[len(keyword) :].lstrip()
    cut = re.search(r";\s*(?:then|do)\b", rest)
    condition = rest[: cut.start()] if cut else rest
    return _PATH_REF.search(condition) is not None


def _pop_closer(stack: list[_Frame], closer: str) -> None:
    for index in range(len(stack) - 1, -1, -1):
        if stack[index][0] == closer:
            del stack[index:]
            return


def _replace_fi_condition(stack: list[_Frame], refs: bool) -> None:
    for index in range(len(stack) - 1, -1, -1):
        if stack[index][0] == "fi":
            stack[index] = ("fi", refs)
            return
    stack.append(("fi", refs))


def _update_block_stack(stack: list[_Frame], line: str) -> bool:
    """Apply this line's block syntax. Return whether the line is presence-guarded.

    A frame pushed here governs the following lines, not this one. A same-line
    closer is frame-neutral: the line is guarded only by its own condition or
    an outer frame.
    """
    outer = any(refs for _, refs in stack)
    stripped = line.strip()
    first = _first_word(stripped)
    own = False
    if first == "elif":
        refs = _condition_references_path("elif", stripped)
        if _has_standalone_closer(line, "fi"):
            _pop_closer(stack, "fi")
            own = refs
        else:
            _replace_fi_condition(stack, refs)
    elif first in _CLOSERS:
        _pop_closer(stack, first)
    elif first in _OPENERS:
        closer = _OPENERS[first]
        refs = _condition_references_path(first, stripped)
        if _has_standalone_closer(line, closer):
            own = refs
        else:
            stack.append((closer, refs))
    return outer or own


def _split_unquoted(line: str) -> tuple[list[tuple[str, str]], bool]:
    """Split on unquoted separators and drop an unquoted comment word.

    Returns (separator, segment) pairs. The first separator is empty; later
    ones are a semicolon, &&, or ||. A doubled semicolon stays in the segment
    so a case row is not torn apart.

    Quote-aware on purpose. installer/shellrc.py::_split_command_segments is
    quote-blind and also splits on parentheses, so it cannot parse a shell
    array or a hash that sits inside quotes.
    """
    segments: list[tuple[str, str]] = []
    buf: list[str] = []
    separator = ""
    comment_dropped = False
    in_single = False
    in_double = False
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if in_single:
            buf.append(char)
            if char == "'":
                in_single = False
            index += 1
            continue
        if char == "\\" and not in_double and index + 1 < length:
            buf.append(char)
            buf.append(line[index + 1])
            index += 2
            continue
        if in_double:
            if char == "\\" and index + 1 < length:
                buf.append(char)
                buf.append(line[index + 1])
                index += 2
                continue
            buf.append(char)
            if char == '"':
                in_double = False
            index += 1
            continue
        if char in "'\"":
            in_single = char == "'"
            in_double = char == '"'
            buf.append(char)
            index += 1
            continue
        if char == "#" and (index == 0 or line[index - 1] in " \t;|&"):
            comment_dropped = True
            break
        if line.startswith(";;", index):
            buf.append(";;")
            index += 2
            continue
        if char == ";":
            segments.append((separator, "".join(buf)))
            buf = []
            separator = ";"
            index += 1
            continue
        if line.startswith("&&", index) or line.startswith("||", index):
            segments.append((separator, "".join(buf)))
            buf = []
            separator = line[index : index + 2]
            index += 2
            continue
        buf.append(char)
        index += 1
    segments.append((separator, "".join(buf)))
    return segments, comment_dropped


def _command_text(segment: str) -> str:
    return _LEADING_THEN_DO.sub("", segment, count=1)


def _zsh_array_targets(body: str, env: Mapping[str, str]) -> tuple[str, ...]:
    # shortcut: a quoted array element containing a space mis-splits, acceptable
    # for a diagnostic because PATH dirs with spaces are rare (and the guard
    # writer in plan 16-08 refuses zsh arrays anyway).
    found: list[str] = []
    for element in body.split():
        raw = _unquote(element)
        if raw in ("$path", "${path[@]}"):
            continue
        expanded = _expand(raw, env)
        if expanded is not None:
            found.append(expanded)
    return tuple(found)


def _remember_assign(body: str, local: dict[str, str]) -> None:
    assign = _ASSIGN.match(body)
    if assign is None or assign.group(1) in ("PATH", "path"):
        return
    expanded = _expand(_unquote(assign.group(2)), local)
    if expanded is not None:
        local[assign.group(1)] = expanded


def _has_command_suffix(value: str) -> bool:
    """True when unquoted whitespace in an assignment value is followed by a command."""
    in_single = False
    in_double = False
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if in_single:
            if char == "'":
                in_single = False
            index += 1
            continue
        if in_double:
            if char == "\\" and index + 1 < length:
                index += 2
                continue
            if char == '"':
                in_double = False
            index += 1
            continue
        if char == "\\" and index + 1 < length:
            index += 2
            continue
        if char in "'\"":
            in_single = char == "'"
            in_double = char == '"'
            index += 1
            continue
        if char in " \t" and value[index + 1 :].strip():
            return True
        index += 1
    return False


def _value_has_unresolved(value: str, env: Mapping[str, str]) -> bool:
    """True when a non-PATH segment of an assignment cannot be expanded."""
    for segment in _unquote(value).split(":"):
        if segment in ("$PATH", "${PATH}"):
            continue
        if _expand(segment, env) is None:
            return True
    return False


def _judge_line(
    index: int,
    line: str,
    segments: list[tuple[str, str]],
    comment_dropped: bool,
    presence_guarded: bool,
    local: dict[str, str],
) -> _PathLine | None:
    chain_has_presence = False
    targets: list[str] = []
    matched_plain = False
    matched_any = False
    unresolved = False
    suffixed = False
    for separator, segment in segments:
        if separator in ("", ";"):
            chain_has_presence = False
        chain_guarded = separator in ("&&", "||") and chain_has_presence
        body = _command_text(segment)
        zsh = _ZSH_PATH_ARRAY.match(body)
        path = None if zsh else _PATH_EXPORT.match(body)
        if (
            path is not None
            and _has_command_suffix(path.group(1))
            and not _EXPORT_WORD.match(body)
        ):
            continue
        if zsh is not None or path is not None:
            matched_any = True
            if path is not None:
                if _EXPORT_WORD.match(body) and _has_command_suffix(path.group(1)):
                    suffixed = True
                matched_plain = True
                if _value_has_unresolved(path.group(1), local):
                    unresolved = True
            if not chain_guarded:
                if zsh is not None:
                    targets.extend(_zsh_array_targets(zsh.group(1), local))
                elif path is not None:
                    targets.extend(_expanded_segments(path.group(1), local))
        else:
            _remember_assign(body, local)
            if _PATH_REF.search(segment):
                chain_has_presence = True
    if not matched_any:
        return None
    plain_only = (
        len(segments) == 1
        and not comment_dropped
        and matched_plain
        and not suffixed
        and _ZSH_PATH_ARRAY.match(_command_text(segments[0][1])) is None
        and not any(_LEADING_THEN_DO.match(segment) for _, segment in segments)
    )
    return _PathLine(
        index=index,
        text=line,
        targets=tuple(targets),
        simple=plain_only,
        indented=line[:1] in (" ", "\t"),
        presence_guarded=presence_guarded,
        unresolved=unresolved,
    )


def _path_line_targets(lines: list[str], env: Mapping[str, str]) -> Iterator[_PathLine]:
    """Yield PATH assignments outside managed blocks, with guard context.

    A block whose condition references PATH is presence-guarded. A condition
    that only tests that a directory exists is not. An && or || segment is
    also presence-guarded when an earlier non-assignment segment of that chain
    references PATH. A line whose first segment starts with case is a guard
    header, not an assignment.
    """
    blocked = _managed_line_indices(lines)
    local: dict[str, str] = dict(env)
    stack: list[_Frame] = []
    heredoc: tuple[str, bool] | None = None
    for index, line in enumerate(lines):
        if heredoc is not None:
            delimiter, strip_tabs = heredoc
            candidate = line.lstrip("\t") if strip_tabs else line
            if candidate == delimiter:
                heredoc = None
            continue
        if index in blocked:
            continue
        # shortcut: only the first heredoc on a line is tracked, and numeric
        # delimiters (<<5), a dash-led delimiter (<< -EOF), and a quoted delimiter
        # containing a space are not recognized, upgrade if a real rc needs either.
        masked = _code_text(line)
        for match in _HEREDOC_OPENER.finditer(line):
            start = match.start()
            if masked[start : start + 2] != "<<":
                continue
            if start != 0 and masked[start - 1] == "<":
                continue
            if masked[:start].rfind("((") > masked[:start].rfind("))"):
                continue
            heredoc = (match.group(2), line.startswith("<<-", start))
            break
        presence_guarded = _update_block_stack(stack, line)
        segments, comment_dropped = _split_unquoted(line)
        if segments and _first_word(segments[0][1].lstrip()) == "case":
            continue
        record = _judge_line(index, line, segments, comment_dropped, presence_guarded, local)
        if record is not None:
            yield record


def _managed_line_indices(lines: list[str]) -> set[int]:
    """Indices inside any tools-installer managed/source block (markers included)."""
    blocked: set[int] = set()
    depth_start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in _MANAGED_BEGINS:
            depth_start = index
        elif stripped in _MANAGED_ENDS and depth_start is not None:
            blocked.update(range(depth_start, index + 1))
            depth_start = None
    return blocked


def _directory_for(expanded: str, targets: Mapping[Path, Path]) -> Path | None:
    """Return the managed dir Path(expanded) names, or None if it is not absolute.

    Matches installer/doctor.py::audit_path, which counts Path(entry) and so
    treats a trailing slash and a doubled slash as the same directory. An empty
    or relative segment is never a managed dir.
    """
    if not expanded or not Path(expanded).is_absolute():
        return None
    return targets.get(Path(expanded))


def find_duplicate_path_lines(
    rc_text: str, managed_dirs: set[Path], env: Mapping[str, str]
) -> list[int]:
    """Line indices whose PATH export adds a directory already in managed_dirs.

    Only plain `export PATH=...` lines are matched (this is what bun and fnm append).
    pnpm's `pnpm setup` instead emits a self-deduping `case`-guarded block
    (`*) export PATH="$PNPM_HOME:$PATH" ;;`), which is intentionally NOT flagged: it
    is not a plain assignment, and its own guard already skips adding a dir that is
    present — so there is nothing safe (or necessary) to strip.
    """
    lines = rc_text.split("\n")
    targets = {Path(directory): directory for directory in managed_dirs}
    flagged: list[int] = []
    for record in _path_line_targets(lines, env):
        # An indented line is never one bun/fnm/this installer appended (always
        # column 0). Stripping it and leaving its block would corrupt the file
        # (an empty then-clause is a bash syntax error), so it is never a strip
        # candidate. A presence-guarded line is not one either.
        if (
            record.simple
            and not record.indented
            and not record.presence_guarded
            and any(_directory_for(segment, targets) is not None for segment in record.targets)
        ):
            flagged.append(record.index)
    return flagged


def strip_lines(rc_text: str, indices: list[int]) -> str:
    """Return rc_text with the given line indices removed."""
    drop = set(indices)
    lines = rc_text.split("\n")
    return "\n".join(line for index, line in enumerate(lines) if index not in drop)


@dataclass(frozen=True)
class PathWriterLine:
    """One unconditional PATH writer, and whether it is safe to rewrite in place."""

    rc_path: Path
    index: int
    text: str
    directory: Path
    guardable: bool
    refusal: str | None
    block_owner: str | None


def _foreign_block_owners(lines: list[str]) -> dict[int, str]:
    """Map each index inside a non-project marker block to that block's name.

    A name starting with tools-installer is this project's own (path, source,
    consolidated shellrc, shellrc stub) and is excluded. An unterminated block
    runs to EOF. A mismatched end name closes nothing. A stack keeps a nested
    foreign block attributed to the innermost open name.
    """
    owners: dict[int, str] = {}
    stack: list[str] = []
    for index, line in enumerate(lines):
        begin = _FOREIGN_BEGIN.match(line)
        if begin is not None:
            name = begin.group(1)
            if not name.startswith(_OWN_MARKER_PREFIX):
                stack.append(name)
            if stack:
                owners[index] = stack[-1]
            continue
        end = _FOREIGN_END.match(line)
        if end is not None and stack and stack[-1] == end.group(1):
            owners[index] = stack[-1]
            stack.pop()
            continue
        if stack:
            owners[index] = stack[-1]
    return owners


def _guard_refusal(line: _PathLine) -> str | None:
    """None when the line is a single-directory prepend we can rewrite.

    A zsh array is simple==False, so it has to be recognized before the
    compound check or every array line would be reported as compound.
    Unresolved is checked before the colon split: an unknown variable makes
    the split look like several directories.
    """
    if _ZSH_PATH_ARRAY.match(line.text.strip()):
        return _REFUSE_ZSH_ARRAY
    if not line.simple:
        return _REFUSE_COMPOUND
    if line.unresolved:
        return _REFUSE_UNRESOLVED
    match = _PATH_EXPORT.match(line.text)
    if match is None:
        return _REFUSE_COMPOUND
    segments = _unquote(match.group(1)).split(":")
    if not any(segment in ("$PATH", "${PATH}") for segment in segments):
        return _REFUSE_REPLACE
    if segments and segments[0] in ("$PATH", "${PATH}"):
        return _REFUSE_APPEND
    if len(segments) == 2 and segments[1] in ("$PATH", "${PATH}"):
        return None
    return _REFUSE_MULTI


def path_writer_lines(
    rc_texts: Mapping[Path, str], managed_dirs: set[Path], env: Mapping[str, str]
) -> list[PathWriterLine]:
    """One record per writer line and each managed directory it adds.

    A duplicate PATH entry has two very different causes, and the remedy is the
    opposite in each case. A nested shell re-adding an inherited entry is
    transient and really does clear in a fresh terminal. A plain prepend in an
    rc file — an assignment that puts the directory in front of the previous
    value with no test first — re-adds it on every single shell, so no new
    terminal will ever clear it and the user has to edit the line. Telling the
    second case to "open a new shell" is advice that can never work, so the
    Doctor needs to know which one it is looking at.

    (The shape itself is deliberately described rather than spelled out here:
    this repo's AST invariant forbids an accumulating PATH assignment anywhere
    under installer/, and a docstring is not exempt from it by default.)

    This differs from `find_duplicate_path_lines` because REPORTING a writer
    and STRIPPING one are different questions. Indented lines COUNT here when
    the enclosing condition does not test PATH. A directory-existence test
    still adds the directory on every shell that reaches the body, so omitting
    it would hide a real writer. `find_duplicate_path_lines` still skips
    indented lines, because deleting one would leave an empty then-clause (a
    bash syntax error).

    A presence-guarded block is not a writer: an if, elif, while, until, or
    case whose condition references PATH already skips a directory that is
    present. A non-PATH test such as a directory-existence check still is.
    Our own case-guarded emitter and pnpm's idiom are the same kind of guard.
    Flagging one would point the user at a correct line.
    """
    records: list[PathWriterLine] = []
    targets = {Path(directory): directory for directory in managed_dirs}
    for rc_path, rc_text in rc_texts.items():
        lines = rc_text.split("\n")
        owners = _foreign_block_owners(lines)
        for record in _path_line_targets(lines, env):
            if record.presence_guarded:
                continue
            owner = owners.get(record.index)
            if owner is not None:
                refusal: str | None = (
                    f"inside the '{owner}' block another tool manages; fix it in that tool"
                )
                guardable = False
            else:
                refusal = _guard_refusal(record)
                guardable = refusal is None
            for segment in record.targets:
                directory = _directory_for(segment, targets)
                if directory is None:
                    continue
                records.append(
                    PathWriterLine(
                        rc_path=rc_path,
                        index=record.index,
                        text=record.text,
                        directory=directory,
                        guardable=guardable,
                        refusal=refusal,
                        block_owner=owner,
                    )
                )
    return records


def group_writer_lines(lines: Iterable[PathWriterLine]) -> dict[Path, tuple[Path, ...]]:
    """Map each managed directory to the rc files that write it, in first-seen order.

    The answer is keyed by directory and collects every file, since the
    structural case is typically one writer in `.bashrc` and another in
    `.bash_profile`; naming only one sends the user back for a second round.
    """
    writers: dict[Path, list[Path]] = {}
    for record in lines:
        files = writers.setdefault(record.directory, [])
        if record.rc_path not in files:
            files.append(record.rc_path)
    return {directory: tuple(files) for directory, files in writers.items()}


def _read_rc_texts(rc_paths: Iterable[Path]) -> dict[Path, str]:
    """Read each rc file as UTF-8. Unreadable files are skipped, not raised.

    A file that cannot be read yields no writers rather than raising: this
    feeds a diagnostic, and a Doctor that crashes on an unreadable rc file is
    worse than one that reports a cause it could not determine.
    """
    texts: dict[Path, str] = {}
    for rc_path in rc_paths:
        try:
            texts[rc_path] = rc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return texts


def scan_rc_path_writer_lines(
    rc_paths: Iterable[Path], managed_dirs: set[Path], env: Mapping[str, str]
) -> list[PathWriterLine]:
    """`path_writer_lines` over files on disk; unreadable files are skipped."""
    return path_writer_lines(_read_rc_texts(rc_paths), managed_dirs, env)
