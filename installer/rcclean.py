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
_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.+?)\s*$")
_PATH_EXPORT = re.compile(r"^\s*(?:export\s+)?PATH=(.+?)\s*$")
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_PATH_REF = re.compile(r"\$\{?PATH\b")
_WORD = re.compile(r"[A-Za-z_]\w*")
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


def _has_standalone_closer(line: str, closer: str) -> bool:
    return re.search(rf"(?:^|[;\s]|;;){re.escape(closer)}(?:$|[;\s#])", line) is not None


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


def _path_line_targets(lines: list[str], env: Mapping[str, str]) -> Iterator[_PathLine]:
    """Yield PATH assignments outside managed blocks, with guard context.

    A block whose condition references PATH is presence-guarded. A condition
    that only tests that a directory exists is not. A line whose first word is
    case is a guard header, not an assignment.
    """
    blocked = _managed_line_indices(lines)
    local: dict[str, str] = dict(env)
    stack: list[_Frame] = []
    for index, line in enumerate(lines):
        if index in blocked:
            continue
        presence_guarded = _update_block_stack(stack, line)
        if _first_word(line.strip()) == "case":
            continue
        path_match = _PATH_EXPORT.match(line)
        if path_match:
            yield _PathLine(
                index=index,
                text=line,
                targets=_expanded_segments(path_match.group(1), local),
                simple=True,
                indented=line[:1] in (" ", "\t"),
                presence_guarded=presence_guarded,
            )
            continue
        assign = _ASSIGN.match(line)
        if assign:
            expanded = _expand(_unquote(assign.group(2)), local)
            if expanded is not None:
                local[assign.group(1)] = expanded


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


def unguarded_path_writers(
    rc_texts: Mapping[Path, str], managed_dirs: set[Path], env: Mapping[str, str]
) -> dict[Path, tuple[Path, ...]]:
    """Map each managed directory to the rc files that add it UNCONDITIONALLY.

    A duplicate PATH entry has two very different causes, and the remedy is the
    opposite in each case. A nested shell re-adding an inherited entry is
    transient and really does clear in a fresh terminal. A plain unconditional
    prepend in an rc file — an assignment that puts the directory in front of
    the previous value with no test first — re-adds it on every single shell,
    so no new terminal will ever clear it and the user has to edit the line.
    Telling the second case to "open a new shell" is advice that can never
    work, so the Doctor needs to know which one it is looking at.

    (The shape itself is deliberately described rather than spelled out here:
    this repo's AST invariant forbids an accumulating PATH assignment anywhere
    under installer/, and a docstring is not exempt from it by default.)

    This differs from `find_duplicate_path_lines` in two deliberate ways,
    because REPORTING a writer and STRIPPING one are different questions:

    * Indented lines COUNT here when the enclosing condition does not test
      PATH. A directory-existence test still adds the directory on every shell
      that reaches the body, so omitting it would hide a real writer.
      `find_duplicate_path_lines` still skips indented lines, because deleting
      one would leave an empty then-clause (a bash syntax error).
    * The answer is keyed by DIRECTORY and collects EVERY file, since the
      structural case is typically one writer in `.bashrc` and another in
      `.bash_profile`; naming only one sends the user back for a second round.

    A presence-guarded block is not a writer: an if, elif, while, until, or
    case whose condition references PATH already skips a directory that is
    present. A non-PATH test such as a directory-existence check still is.
    Our own case-guarded emitter and pnpm's idiom are the same kind of guard.
    Flagging one would point the user at a correct line.
    """
    writers: dict[Path, list[Path]] = {}
    targets = {Path(directory): directory for directory in managed_dirs}
    for rc_path, rc_text in rc_texts.items():
        for record in _path_line_targets(rc_text.split("\n"), env):
            if record.presence_guarded:
                continue
            for segment in record.targets:
                directory = _directory_for(segment, targets)
                if directory is not None and rc_path not in writers.setdefault(directory, []):
                    writers[directory].append(rc_path)
    return {directory: tuple(files) for directory, files in writers.items()}


def scan_rc_path_writers(
    rc_paths: Iterable[Path], managed_dirs: set[Path], env: Mapping[str, str]
) -> dict[Path, tuple[Path, ...]]:
    """`unguarded_path_writers` over files on disk; unreadable files are skipped.

    The IO seam is deliberately this thin so the classification itself stays a
    pure function under test. A file that cannot be read yields no writers
    rather than raising: this feeds a diagnostic, and a Doctor that crashes on
    an unreadable rc file is worse than one that reports a cause it could not
    determine.
    """
    texts: dict[Path, str] = {}
    for rc_path in rc_paths:
        try:
            texts[rc_path] = rc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return unguarded_path_writers(texts, managed_dirs, env)
