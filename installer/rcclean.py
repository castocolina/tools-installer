"""Find and strip duplicate PATH-export lines in shell rc files.

Detection resolves `export VAR=...` assignments declared earlier in the same file
(so installer lines like `$BUN_INSTALL/bin` expand), skips our own managed blocks,
and flags any PATH entry that resolves to a directory we already manage. Used to
clean the redundant lines bun/pnpm/fnm append to .bashrc/.zshrc.
"""

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

_MANAGED_BEGINS = ("# >>> tools-installer path >>>", "# >>> tools-installer source >>>")
_MANAGED_ENDS = ("# <<< tools-installer path <<<", "# <<< tools-installer source <<<")
_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.+?)\s*$")
_PATH_EXPORT = re.compile(r"^\s*(?:export\s+)?PATH=(.+?)\s*$")
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


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
    blocked = _managed_line_indices(lines)
    local: dict[str, str] = dict(env)
    targets = {str(directory) for directory in managed_dirs}
    flagged: list[int] = []
    for index, line in enumerate(lines):
        if index in blocked:
            continue
        path_match = _PATH_EXPORT.match(line)
        if path_match:
            # An indented line is never one bun/fnm/this installer appended (always
            # column 0) and is very likely the body of an if/case/for the rc file's
            # own template wraps it in (e.g. Fedora's default .bashrc). Stripping
            # such a line but leaving its block would corrupt the file (an empty
            # then-clause is a bash syntax error), so it is never a strip candidate.
            if line[:1] not in (" ", "\t"):
                value = _unquote(path_match.group(1))
                for segment in value.split(":"):
                    if segment in ("$PATH", "${PATH}"):
                        continue
                    expanded = _expand(segment, local)
                    if expanded is not None and expanded in targets:
                        flagged.append(index)
                        break
            continue
        assign = _ASSIGN.match(line)
        if assign:
            expanded = _expand(_unquote(assign.group(2)), local)
            if expanded is not None:
                local[assign.group(1)] = expanded
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

    * Indented lines COUNT here. Fedora's stock `.bashrc` wraps its prepend in
      an `if`, so the line sits at column 4. `find_duplicate_path_lines` skips
      it because deleting it would leave an empty then-clause (a bash syntax
      error) — but it still adds the directory on every shell, so a report that
      omitted it would leave the user's most common duplicate unexplained.
    * The answer is keyed by DIRECTORY and collects EVERY file, since the
      structural case is typically one writer in `.bashrc` and another in
      `.bash_profile`; naming only one sends the user back for a second round.

    Guarded forms are not writers: our own `case`-guarded emitter and pnpm's
    own idiom both skip a directory that is already present, so they cannot
    duplicate. Flagging one would point the user at a correct line.
    """
    writers: dict[Path, list[Path]] = {}
    targets = {str(directory): directory for directory in managed_dirs}
    for rc_path, rc_text in rc_texts.items():
        lines = rc_text.split("\n")
        blocked = _managed_line_indices(lines)
        local: dict[str, str] = dict(env)
        for index, line in enumerate(lines):
            if index in blocked:
                continue
            path_match = _PATH_EXPORT.match(line)
            if path_match:
                value = _unquote(path_match.group(1))
                for segment in value.split(":"):
                    if segment in ("$PATH", "${PATH}"):
                        continue
                    expanded = _expand(segment, local)
                    directory = targets.get(expanded) if expanded is not None else None
                    if directory is not None and rc_path not in writers.setdefault(directory, []):
                        writers[directory].append(rc_path)
                continue
            assign = _ASSIGN.match(line)
            if assign:
                expanded = _expand(_unquote(assign.group(2)), local)
                if expanded is not None:
                    local[assign.group(1)] = expanded
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
