"""Guarded text splice for agent and editor settings files (D-06, D-07).

A settings file is edited as text: one key is inserted or removed at a computed
position, the result is re-parsed, and it is written only when it parses to the
old document plus exactly that edit. Comments, key order and unrelated keys
survive because nothing else in the text is re-serialized. No format library is
used (18 D-09 precedent): json and tomllib parse, and the splice is ours.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal, cast

from installer.agent_env import adapters
from installer.atomic import FileSnapshot, atomic_write_text, read_snapshot, snapshot_matches
from installer.locations import display_path
from installer.receipts import (
    ConfigLedger,
    ConfigWrite,
    read_ledger,
    untrusted_ledger,
    write_ledger,
)

SettingsFormat = Literal["json", "jsonc", "toml"]
KeyPath = tuple[str, ...]
FORMAT_NAMES: Final = {"json": "JSON", "jsonc": "JSONC", "toml": "TOML"}
CHANGED_WHILE_WRITING: Final = "changed while being written"
_WHITESPACE: Final = " \t\r\n"
# A string is kept so that "//" inside a URL is data; a comment and a comma that
# closes an object or array (a trailing comma) are blanked, newlines kept. A block
# comment cannot match past its own `*/`, so two comments never merge into one.
_JSONC_TOKEN: Final = re.compile(
    r'("(?:\\.|[^"\\])*")'
    r"|(//[^\n]*|/\*(?:[^*]|\*(?!/))*\*/)"
    r"|(,)(?=(?:\s|//[^\n]*|/\*(?:[^*]|\*(?!/))*\*/)*[}\]])",
)


class SettingsParseError(ValueError):
    """The file does not parse; `fragment` names the format and the position."""

    def __init__(self, fmt: SettingsFormat, line: int, column: int | None) -> None:
        self.fmt = fmt
        self.line = line
        self.column = column
        super().__init__(self.fragment)

    @property
    def fragment(self) -> str:
        where = f"line {self.line}"
        if self.column is not None:
            where += f", column {self.column}"
        return f"not valid {FORMAT_NAMES[self.fmt]} ({where})"


class SettingsEditRefused(ValueError):
    """The splice did not produce exactly the intended document; nothing is written."""


class SettingsChanged(OSError):
    """The file changed between read and write; nothing was written."""

    def __init__(self) -> None:
        super().__init__(CHANGED_WHILE_WRITING)


class LedgerUntrusted(OSError):
    """The agent's ledger did not validate: it was kept aside and nothing is written or reverted."""

    def __init__(self, agent: str, aside: Path) -> None:
        super().__init__(
            f"blocked: the {agent} config ledger could not be trusted and was kept as "
            f"{display_path(aside)}; restore or delete it"
        )


def _ledger(agent: str) -> ConfigLedger:
    """The agent's ledger, empty when missing; LedgerUntrusted when one exists but does not
    validate, so a bad ledger is never read as empty and then overwritten."""
    aside = untrusted_ledger(agent)
    if aside is not None:
        raise LedgerUntrusted(agent, aside)
    return read_ledger(agent) or ConfigLedger(agent)


class _Absent:
    def __repr__(self) -> str:
        return "ABSENT"


ABSENT: Final = _Absent()


def _member(node: object, key: str) -> object:
    if not isinstance(node, dict):
        return ABSENT
    return cast(dict[str, object], node).get(key, ABSENT)


def lookup(doc: dict[str, object], key_path: KeyPath) -> object:
    """The value at key_path, or ABSENT when any part is missing or a parent is not an object."""
    node: object = doc
    for key in key_path:
        node = _member(node, key)
    return node


def same_value(a: object, b: object) -> bool:
    """Equal values of the same type; `1 == True` and `0 == False` never match."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        left = cast(dict[str, object], a)
        right = cast(dict[str, object], b)
        return left.keys() == right.keys() and all(same_value(left[k], right[k]) for k in left)
    if isinstance(a, list):
        left_items = cast(list[object], a)
        right_items = cast(list[object], b)
        return len(left_items) == len(right_items) and all(
            same_value(x, y) for x, y in zip(left_items, right_items, strict=True)
        )
    return a == b


def key_held(current: object, ours: object) -> bool | None:
    """Whether a recorded key still holds our value: None when it is gone, False when the
    user changed it. The one check the revert and the removal preview share (UAT F-3)."""
    return None if current is ABSENT else same_value(current, ours)


def _blank(match: re.Match[str]) -> str:
    if match.group(1) is not None:
        return match.group(1)
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_jsonc(text: str) -> str:
    """JSONC with comments and trailing commas as spaces: same length, same newlines."""
    return _JSONC_TOKEN.sub(_blank, text)


def _clean(text: str, fmt: SettingsFormat) -> str:
    """The text the scanner walks: positions match `text`, so edits are made on `text`."""
    return strip_jsonc(text) if fmt == "jsonc" else text


def parse_settings(text: str, fmt: SettingsFormat) -> dict[str, object]:
    """The document as a dict; whitespace-only text is an empty object."""
    if not text.strip():
        return {}
    if fmt == "toml":
        try:
            toml_doc: object = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            located = re.search(r"\(at line (\d+), column (\d+)\)", str(exc))
            if located is None:  # "(at end of document)": the last line, no column
                raise SettingsParseError(fmt, len(text.splitlines()), None) from exc
            raise SettingsParseError(fmt, int(located[1]), int(located[2])) from exc
        return cast(dict[str, object], toml_doc)
    try:
        doc: object = json.loads(_clean(text, fmt))
    except json.JSONDecodeError as exc:
        raise SettingsParseError(fmt, exc.lineno, exc.colno) from exc
    if not isinstance(doc, dict):
        raise SettingsParseError(fmt, 1, None)
    return cast(dict[str, object], doc)


def _skip_ws(text: str, index: int) -> int:
    while text[index] in _WHITESPACE:
        index += 1
    return index


def _end_of_string(text: str, start: int) -> int:
    index = start + 1
    while text[index] != '"':
        index += 2 if text[index] == "\\" else 1
    return index + 1


def _end_of_value(text: str, index: int) -> int:
    if text[index] == '"':
        return _end_of_string(text, index)
    if text[index] in "{[":
        depth = 0
        while True:
            char = text[index]
            if char == '"':
                index = _end_of_string(text, index)
                continue
            if char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
                if depth == 0:
                    return index + 1
            index += 1
    while index < len(text) and text[index] not in ",}] \t\r\n":
        index += 1
    return index


@dataclass(frozen=True)
class _Member:
    key: str
    key_start: int
    value_start: int
    value_end: int


def _members(text: str, open_index: int) -> tuple[list[_Member], int]:
    """Members of the object opened at open_index, and the index of its closing brace."""
    members: list[_Member] = []
    index = _skip_ws(text, open_index + 1)
    while text[index] != "}":
        key_end = _end_of_string(text, index)
        value_start = _skip_ws(text, _skip_ws(text, key_end) + 1)
        value_end = _end_of_value(text, value_start)
        key = cast(str, json.loads(text[index:key_end]))
        members.append(_Member(key, index, value_start, value_end))
        index = _skip_ws(text, value_end)
        if text[index] == ",":
            index = _skip_ws(text, index + 1)
    return members, index


def _object_open(clean: str, path: KeyPath) -> int:
    """Index of the `{` of the object at path, in cleaned text that already parses."""
    index = _skip_ws(clean, 0)
    for key in path:
        members, _ = _members(clean, index)
        index = [member for member in members if member.key == key][-1].value_start
    return index


def _member_at(clean: str, key_path: KeyPath) -> tuple[list[_Member], _Member]:
    members, _ = _members(clean, _object_open(clean, key_path[:-1]))
    return members, [member for member in members if member.key == key_path[-1]][-1]


def _leading_ws(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _guarded(new_text: str, fmt: SettingsFormat, expected: dict[str, object]) -> str:
    """Return new_text only when it parses to exactly the expected document."""
    try:
        actual = parse_settings(new_text, fmt)
    except SettingsParseError as exc:
        raise SettingsEditRefused("the edit broke the file") from exc
    if not same_value(actual, expected):
        raise SettingsEditRefused("the edit changed more than the intended key")
    return new_text


def _edited(doc: dict[str, object], key_path: KeyPath, value: object) -> dict[str, object]:
    """A copy of doc with key_path set to value (parents created), or without it for ABSENT."""
    expected = copy.deepcopy(doc)
    node = expected
    for key in key_path[:-1]:
        node = cast(dict[str, object], node.setdefault(key, {}))
    if value is ABSENT:
        del node[key_path[-1]]
    else:
        node[key_path[-1]] = value
    return expected


@dataclass(frozen=True)
class Inserted:
    text: str
    fragment: str
    created_parent: bool


def insert_key(text: str, fmt: SettingsFormat, key_path: KeyPath, value: object) -> Inserted:
    """Insert one absent key by splice. A two-part key whose parent is absent creates the parent
    as one member. The fragment is the text a later revert removes."""
    doc = parse_settings(text, fmt)
    if lookup(doc, key_path) is not ABSENT:
        raise SettingsEditRefused(f"{'.'.join(key_path)} is already set")
    if fmt == "toml":
        return _insert_toml(text, doc, key_path, value)
    if not text.strip():
        raise SettingsEditRefused("empty file: there is no object to insert into")
    if len(key_path) not in (1, 2):
        raise SettingsEditRefused("settings keys nest at most one level")
    parent = key_path[:-1]
    created_parent = len(key_path) == 2 and lookup(doc, parent) is ABSENT
    if parent and not created_parent and not isinstance(lookup(doc, parent), dict):
        raise SettingsEditRefused(f"{'.'.join(parent)} must be an existing object")
    if created_parent:
        target = key_path[:-2]
        member = f"{_dump(parent[-1])}: {{{_dump(key_path[-1])}: {_dump(value)}}}"
    else:
        target = parent
        member = f"{_dump(key_path[-1])}: {_dump(value)}"
    clean = _clean(text, fmt)
    obj = _object_open(clean, target)
    members, _ = _members(clean, obj)
    if members and "\n" not in clean[obj + 1 : members[0].key_start]:
        fragment = f"{member}, "  # one-line object: keep it on the `{` line
    elif members:
        line_start = clean.rfind("\n", 0, members[0].key_start) + 1
        fragment = f"\n{clean[line_start : members[0].key_start]}{member},"
    else:
        base = clean[clean.rfind("\n", 0, obj) + 1 : obj]
        fragment = f"\n{_leading_ws(base)}  {member}"
    new_text = text[: obj + 1] + fragment + text[obj + 1 :]
    expected = _edited(doc, key_path, value)
    return Inserted(_guarded(new_text, fmt, expected), fragment, created_parent)


_BARE_KEY: Final = re.compile(r"[A-Za-z0-9_-]+")
# A plain `[a.b]` table header line (no quoted or spaced parts, never `[[array]]`), comment allowed.
_TOML_HEADER: Final = re.compile(r"\s*\[([A-Za-z0-9_.-]+)\]\s*(?:#.*)?")
_TOML_BLOCK: Final = re.compile(r"^\s*\[[A-Za-z0-9_.-]+\]", re.MULTILINE)


def _toml_key(key_path: KeyPath) -> tuple[KeyPath, str]:
    """The table path and the leaf key; every part must be a bare key."""
    if not key_path or not all(_BARE_KEY.fullmatch(part) for part in key_path):
        raise SettingsEditRefused("TOML keys are bare keys")
    return key_path[:-1], key_path[-1]


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _dump(value)
    if isinstance(value, list):
        return f"[{', '.join(_toml_value(item) for item in cast(list[object], value))}]"
    if isinstance(value, dict):
        members = cast(dict[str, object], value)
        if not all(_BARE_KEY.fullmatch(name) for name in members):
            raise SettingsEditRefused("TOML inline-table keys here are bare keys")
        if not members:
            return "{}"
        return f"{{ {', '.join(f'{k} = {_toml_value(v)}' for k, v in members.items())} }}"
    raise SettingsEditRefused(
        f"TOML values here are strings, booleans, integers, arrays or inline tables, "
        f"not {type(value).__name__}"
    )


def _insert_toml(text: str, doc: dict[str, object], key_path: KeyPath, value: object) -> Inserted:
    """A top-level key goes on its own line before the first table header, or at the end. A
    line starting with `[` may also sit inside an array or a multi-line string, so each
    candidate is tried in order and the first one the guard accepts is the header.

    A nested key goes right after its `[table]` header (candidates tried the same way); a table
    that does not exist yet is appended at the end as one block. A table that exists but takes
    no candidate refuses: a second header for it would be invalid TOML."""
    table, key = _toml_key(key_path)
    lines = text.splitlines(keepends=True)
    expected = _edited(doc, key_path, value)
    entry = f"{key} = {_toml_value(value)}\n"
    if table:
        dotted = ".".join(table)
        for i, line in enumerate(lines):
            header = _TOML_HEADER.fullmatch(line.rstrip("\r\n"))
            if header is None or header[1] != dotted:
                continue
            fragment = entry if line.endswith("\n") else "\n" + entry
            new_text = "".join(lines[: i + 1]) + fragment + "".join(lines[i + 1 :])
            try:
                return Inserted(_guarded(new_text, "toml", expected), fragment, False)
            except SettingsEditRefused:
                continue
        if lookup(doc, table) is not ABSENT:
            raise SettingsEditRefused(f"[{dotted}] exists but takes no new key here")
        gap = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        fragment = f"{gap}[{dotted}]\n{entry}"
        return Inserted(_guarded(text + fragment, "toml", expected), fragment, True)
    candidates = [i for i, line in enumerate(lines) if line.lstrip().startswith("[")]
    for at in (*candidates, len(lines)):
        fragment = entry
        if at == len(lines) and text and not text.endswith("\n"):
            fragment = "\n" + fragment
        new_text = "".join(lines[:at]) + fragment + "".join(lines[at:])
        try:
            return Inserted(_guarded(new_text, "toml", expected), fragment, created_parent=False)
        except SettingsEditRefused:
            continue
    raise SettingsEditRefused("no place for a top-level key")


def _toml_leaf_line(lines: list[str], key_path: KeyPath) -> int:
    """The index of the key's own line inside its table."""
    table, key = _toml_key(key_path)
    dotted = ".".join(table)
    in_table = not table
    for index, line in enumerate(lines):
        if line.lstrip().startswith("["):
            header = _TOML_HEADER.fullmatch(line.rstrip("\r\n"))
            in_table = bool(table) and header is not None and header[1] == dotted
        elif in_table and re.match(rf"\s*{re.escape(key)}\s*=", line):
            return index
    raise SettingsEditRefused(f"{'.'.join(key_path)} has no line to remove")


def _toml_remove(text: str, key_path: KeyPath, fragment: str | None) -> str:
    """The recorded fragment when it occurs once, else the key's own line inside its table."""
    if fragment is not None and text.count(fragment) == 1:
        return text.replace(fragment, "", 1)
    lines = text.splitlines(keepends=True)
    index = _toml_leaf_line(lines, key_path)
    return "".join(lines[:index] + lines[index + 1 :])


def _toml_removal(
    doc: dict[str, object], text: str, key_path: KeyPath, fragment: str | None
) -> str:
    """`text` without the key (or table), guarded. Removing our own `[a.b.c]` header also removes
    the `a.b` that header implied; the expected document drops each such ancestor, deepest first,
    only while it is empty there and absent from the edited text, so a table the user defined
    (an explicit header, or any key of theirs) stays."""
    expected = _edited(doc, key_path, ABSENT)
    if (
        fragment is not None
        and _TOML_BLOCK.search(fragment)
        and not isinstance(lookup(doc, key_path), dict)
    ):
        fragment = None  # a created table's block: only this one key goes
    candidate = _toml_remove(text, key_path, fragment)
    try:
        after = parse_settings(candidate, "toml")
    except SettingsParseError as exc:
        raise SettingsEditRefused("the edit broke the file") from exc
    for depth in range(len(key_path) - 1, 0, -1):
        prefix = key_path[:depth]
        if not same_value(lookup(expected, prefix), {}) or lookup(after, prefix) is not ABSENT:
            break
        del cast(dict[str, object], lookup(expected, prefix[:-1]))[prefix[-1]]
    return _guarded(candidate, "toml", expected)


def _cut_member(text: str, clean: str, members: list[_Member], member: _Member) -> str:
    """`text` without the member. Positions and punctuation come from `clean`. The member's
    following comma (and the space after it) goes with it; the last member takes the
    preceding comma instead; a member alone on its line takes its newline."""
    start = member.key_start
    while start > 0 and clean[start - 1] in " \t":
        start -= 1
    end = member.value_end
    after = _skip_ws(clean, end)
    comma_before = -1
    if clean[after] == ",":
        end = after + 1
        while clean[end] in " \t":
            end += 1
    elif member is not members[0]:
        probe = start - 1
        while clean[probe] in _WHITESPACE:
            probe -= 1
        comma_before = probe
    if start == 0 or clean[start - 1] == "\n":
        probe = end
        while clean[probe] in " \t":
            probe += 1
        if clean[probe] == "\n":
            end = probe + 1
    head = text[:start]
    if comma_before >= 0:
        head = text[:comma_before] + text[comma_before + 1 : start]
    return head + text[end:]


def remove_key(
    text: str, fmt: SettingsFormat, key_path: KeyPath, *, fragment: str | None = None
) -> str:
    """Remove one set key. The recorded fragment is cut when it occurs once, holds the member
    and the result re-parses; otherwise the located member is cut, so a later edit around the
    member or a vendor re-serialization still reverts."""
    doc = parse_settings(text, fmt)
    if lookup(doc, key_path) is ABSENT:
        raise SettingsEditRefused(f"{'.'.join(key_path)} is not set")
    if fmt == "toml":
        return _toml_removal(doc, text, key_path, fragment)
    expected = _edited(doc, key_path, ABSENT)
    clean = _clean(text, fmt)
    members, member = _member_at(clean, key_path)
    located = text[member.key_start : member.value_end]
    if fragment is not None and text.count(fragment) == 1 and located in fragment:
        cut = text.replace(fragment, "", 1)
        # JSONC accepts a trailing comma, so the re-parse alone cannot see one the cut left.
        if _trailing_commas(cut, fmt) <= _trailing_commas(text, fmt):
            try:
                return _guarded(cut, fmt, expected)
            except SettingsEditRefused:
                pass  # e.g. a member appended after ours: its comma now belongs to the cut
    return _guarded(_cut_member(text, clean, members, member), fmt, expected)


def _trailing_commas(text: str, fmt: SettingsFormat) -> int:
    """Commas the JSONC reader blanks: trailing ones, plus any inside comments."""
    return sum(1 for raw, kept in zip(text, _clean(text, fmt), strict=True) if raw == "," != kept)


def replace_value(text: str, fmt: SettingsFormat, key_path: KeyPath, new: object) -> str:
    """Swap one set value in place; every other byte of the file stays as it was."""
    if fmt == "toml":
        raise SettingsEditRefused("TOML values are not swapped in place")
    doc = parse_settings(text, fmt)
    if lookup(doc, key_path) is ABSENT:
        raise SettingsEditRefused(f"{'.'.join(key_path)} is not set")
    _, member = _member_at(_clean(text, fmt), key_path)
    new_text = text[: member.value_start] + _dump(new) + text[member.value_end :]
    return _guarded(new_text, fmt, _edited(doc, key_path, new))


def _value_text(fmt: SettingsFormat, value: object) -> str:
    return _toml_value(value) if fmt == "toml" else _dump(value)


def swap_recorded(
    text: str, fmt: SettingsFormat, key_path: KeyPath, old: object, new: object
) -> str:
    """Replace a value the installer wrote with another. A TOML edit touches only the key's own
    line (a comment after the value stays); the result is re-parsed against the expected
    document."""
    if fmt != "toml":
        return replace_value(text, fmt, key_path, new)
    doc = parse_settings(text, fmt)
    lines = text.splitlines(keepends=True)
    index = _toml_leaf_line(lines, key_path)
    before, after = _toml_value(old), _toml_value(new)
    if lines[index].count(before) != 1:
        raise SettingsEditRefused(f"{'.'.join(key_path)} line is not the one written")
    lines[index] = lines[index].replace(before, after, 1)
    return _guarded("".join(lines), fmt, _edited(doc, key_path, new))


def new_file_text(fmt: SettingsFormat) -> str:
    """Content of a settings file the installer creates: an empty object, or empty TOML."""
    return "" if fmt == "toml" else "{}\n"


def read_settings(path: Path) -> FileSnapshot | None:
    """The file's identity-bound bytes, or None when absent. A symlink is read through."""
    target = Path(os.path.realpath(path))
    return read_snapshot(target) if target.exists() else None


def write_if_unchanged(path: Path, before: FileSnapshot | None, text: str) -> None:
    """Write text only if the file still matches `before`; None means it must still be absent."""
    target = Path(os.path.realpath(path))
    unchanged = not os.path.lexists(target) if before is None else snapshot_matches(target, before)
    if not unchanged:
        raise SettingsChanged()
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, text, mode=None if before is None else before.mode)


def delete_if_unchanged(path: Path, before: FileSnapshot) -> None:
    """Remove the file only if it still matches `before`."""
    target = Path(os.path.realpath(path))
    if not snapshot_matches(target, before):
        raise SettingsChanged()
    target.unlink()


def _below_home(directory: str | Path, home: Path) -> bool:
    return Path(os.path.realpath(home)) in Path(directory).parents


def missing_dirs(path: Path, home: Path) -> tuple[str, ...]:
    """The directories `write_if_unchanged` will create above `path`, under home, topmost first."""
    missing: list[Path] = []
    for directory in Path(os.path.realpath(path)).parents:
        if os.path.lexists(directory):
            break
        missing.append(directory)
    return tuple(str(d) for d in reversed(missing) if _below_home(d, home))


def remove_created_dirs(dirs: tuple[str, ...], home: Path) -> tuple[str, ...]:
    """rmdir the recorded directories deepest first; the ones still holding anything stay recorded.
    Never rmtree, never a directory outside home or one the ledger does not name."""
    left: list[str] = []
    for directory in reversed(dirs):
        if not _below_home(directory, home):
            continue
        try:
            os.rmdir(directory)
        except FileNotFoundError:
            pass
        except OSError:
            left.append(directory)
    return tuple(reversed(left))


KeyKind = Literal[
    "wrote", "set_by_you", "already", "replaced_default", "replaced_ours", "removed", "kept_changed"
]
AGENT_FORMATS: Final[dict[str, SettingsFormat]] = {
    "claude": "json",
    "codex": "toml",
    "opencode": "jsonc",
    "cursor-agent": "json",
    "vscode": "jsonc",
    "copilot": "jsonc",
    "herdr": "toml",
}


@dataclass(frozen=True)
class SettingKey:
    """One key the installer may write: its path, our value, and the CLI default it may replace."""

    path: KeyPath
    value: object
    cli_default: object = ABSENT


# The CONF-12 lean list. Each entry is a flat key: the dotted name is the one path part.
_VSCODE_LEAN: Final[tuple[tuple[str, object], ...]] = (
    ("telemetry.telemetryLevel", "off"),
    ("workbench.enableExperiments", False),
    ("workbench.settings.enableNaturalLanguageSearch", False),
    ("extensions.ignoreRecommendations", True),
    ("window.restoreWindows", "one"),
    ("workbench.startupEditor", "none"),
    ("editor.minimap.enabled", False),
    (
        "files.watcherExclude",
        {
            "**/node_modules/**": True,
            "**/.venv/**": True,
            "**/.git/objects/**": True,
            "**/dist/**": True,
            "**/build/**": True,
            "**/.cache/**": True,
        },
    ),
    ("search.followSymlinks", False),
    ("npm.autoDetect", "off"),
    ("task.autoDetect", "off"),
    ("typescript.disableAutomaticTypeAcquisition", True),
    ("git.autoRepositoryDetection", "openEditors"),
)


def _row_token(name: str, style: str) -> dict[str, object]:
    """A herdr sidebar row token with one style flag on."""
    return {"token": name, style: True}


_KEYS: Final[dict[tuple[str, str], tuple[SettingKey, ...]]] = {
    ("claude", "auto-approve"): (
        SettingKey(("permissions", "defaultMode"), "bypassPermissions"),
        SettingKey(("skipDangerousModePermissionPrompt",), True),
    ),
    ("claude", "no-attribution"): (
        SettingKey(("attribution", "commit"), ""),
        SettingKey(("attribution", "pr"), ""),
    ),
    ("codex", "auto-approve"): (
        SettingKey(("approval_policy",), "never"),
        SettingKey(("sandbox_mode",), "danger-full-access"),
    ),
    # OpenCode 2's schema deprecates `permission`; `permissions` is an ordered rule array.
    ("opencode", "auto-approve"): (
        SettingKey(("permissions",), [{"action": "*", "resource": "*", "effect": "allow"}]),
    ),
    # The CLI self-repairs a missing approvalMode to "allowlist" (verified 2026-11-08: fresh
    # container install and a long-lived host config), so that value is its default, not a choice.
    ("cursor-agent", "auto-approve"): (
        SettingKey(("approvalMode",), "unrestricted", cli_default="allowlist"),
    ),
    ("cursor-agent", "no-attribution"): (
        SettingKey(("attribution", "attributeCommitsToAgent"), False, cli_default=True),
        SettingKey(("attribution", "attributePRsToAgent"), False, cli_default=True),
    ),
    ("copilot", "auto-approve"): (SettingKey(("defaultPermissionMode",), "allow-all"),),
    ("copilot", "no-attribution"): (SettingKey(("includeCoAuthoredBy",), False),),
    # castocolina/herdr-setup@2b5ca2a config/config.toml, KEEP rows only (24 D-12).
    ("herdr", "sidebar"): (
        SettingKey(
            ("ui", "sidebar", "agents", "rows"),
            [
                [_row_token("$rule", "dim")],
                ["state_icon", "workspace", "tab", _row_token("$here", "bold")],
                ["agent"],
            ],
        ),
        SettingKey(("ui", "sidebar", "agents", "row_gap"), 1),
        SettingKey(
            ("ui", "sidebar", "spaces", "rows"),
            [["state_icon", "workspace", _row_token("$here", "bold")]],
        ),
    ),
    ("vscode", "vscode-ai-off"): (SettingKey(("chat.disableAIFeatures",), True),),
    ("vscode", "vscode-ext-updates-off"): (
        SettingKey(("extensions.autoUpdate",), False),
        SettingKey(("extensions.autoCheckUpdates",), False),
    ),
}


# Keys whose value only the caller knows at run time (24 D-08b): `apply_value` writes it, the
# ledger entry records it, and a revert takes the recorded value as the one to match.
DYNAMIC_KEYS: Final[dict[tuple[str, str], tuple[KeyPath, ...]]] = {
    ("herdr", "default-shell"): (("terminal", "default_shell"),),
}

# Keys an earlier release wrote: never written again, read only to revert their ledger entries
# and to recognise them in a file. Keep every key a release ever wrote.
RETIRED_KEYS: Final[dict[tuple[str, str], tuple[SettingKey, ...]]] = {
    ("opencode", "auto-approve"): (SettingKey(("permission",), "allow"),),
}

# The groups an install writes per tool: explicit because `vscode-lean` is built by
# `_vscode_lean`, not stored in `_KEYS`.
TUNING_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "claude": ("auto-approve", "no-attribution"),
    "codex": ("auto-approve",),
    "opencode": ("auto-approve",),
    "cursor-agent": ("auto-approve", "no-attribution"),
    "vscode": ("vscode-lean", "vscode-ai-off", "vscode-ext-updates-off"),
    "copilot": ("auto-approve", "no-attribution"),
}


def _vscode_lean(platform_os: str) -> tuple[SettingKey, ...]:
    """The lean list plus this OS's terminal profile; update.mode is written on macOS only."""
    macos = platform_os == "macos"
    profile = "osx" if macos else "linux"
    keys = [SettingKey((name,), value) for name, value in _VSCODE_LEAN]
    keys.append(SettingKey((f"terminal.integrated.defaultProfile.{profile}",), "zsh"))
    if macos:
        keys.append(SettingKey(("update.mode",), "none"))
    return tuple(keys)


def setting_keys(agent: str, setting: str, platform_os: str) -> tuple[SettingKey, ...]:
    """The keys one (agent, setting) pair writes on this OS; empty for an unknown pair."""
    if (agent, setting) == ("vscode", "vscode-lean"):
        return _vscode_lean(platform_os)
    return _KEYS.get((agent, setting), ())


def _format(agent: str) -> SettingsFormat:
    if agent not in AGENT_FORMATS:
        raise ValueError(f"unknown settings agent: {agent!r}")
    return AGENT_FORMATS[agent]


def settings_file(
    agent: str, *, home: Path, platform_os: str, environ: Mapping[str, str] | None = None
) -> Path:
    """The file an agent's settings live in: its adapter path; opencode prefers .jsonc."""
    _format(agent)
    path = adapters(home, platform_os=platform_os, environ=environ)[agent].config_path
    if agent == "opencode" and os.path.lexists(path.with_name("opencode.jsonc")):
        return path.with_name("opencode.jsonc")
    return path


def _conflict(
    agent: str, *, home: Path, platform_os: str, environ: Mapping[str, str] | None = None
) -> str | None:
    """The refusal when an agent's settings could live in either of two files (opencode)."""
    if agent != "opencode":
        return None
    json_path = adapters(home, platform_os=platform_os, environ=environ)[agent].config_path
    if os.path.lexists(json_path) and os.path.lexists(json_path.with_name("opencode.jsonc")):
        return "both opencode.json and opencode.jsonc exist"
    return None


@dataclass(frozen=True)
class KeyResult:
    """`key` is the dotted path; `value` is the JSON of the value it names (the user's or ours)."""

    key: str
    kind: KeyKind
    value: str


@dataclass(frozen=True)
class FileResult:
    agent: str
    setting: str
    path: Path
    fmt: SettingsFormat
    keys: tuple[KeyResult, ...] = ()
    refused: str | None = None


_BOM: Final = "\ufeff"


def _text_of(snap: FileSnapshot | None, fmt: SettingsFormat) -> str:
    """The file's text without a leading BOM (`_with_bom` puts it back); a missing or
    whitespace-only file is its new content, and non-UTF-8 bytes read as line 1."""
    if snap is None:
        return new_file_text(fmt)
    try:
        text = snap.data.decode("utf-8").removeprefix(_BOM)
    except UnicodeDecodeError as exc:
        raise SettingsParseError(fmt, 1, None) from exc
    return text if text.strip() else new_file_text(fmt)


def _with_bom(snap: FileSnapshot | None, text: str) -> str:
    """The text to write: a BOM the file started with stays."""
    return _BOM + text if snap is not None and snap.data.startswith(_BOM.encode()) else text


@dataclass(frozen=True)
class _Pass:
    """One computed edit: the new text, the per-key results, and the ledger changes it implies."""

    text: str
    keys: tuple[KeyResult, ...]
    writes: tuple[ConfigWrite, ...]
    dropped: tuple[KeyPath, ...]


def _apply_pass(
    text: str,
    fmt: SettingsFormat,
    setting: str,
    file: str,
    keys: tuple[SettingKey, ...],
    skip: frozenset[KeyPath] = frozenset(),
    ours: Mapping[KeyPath, ConfigWrite] | None = None,
) -> _Pass:
    """`skip` keys are left alone: no result, no write and no ledger change for them. `ours` holds
    the ledger entries of this setting and file: a key still holding the recorded value is ours
    and takes the new value."""
    results: list[KeyResult] = []
    writes: list[ConfigWrite] = []
    dropped: list[KeyPath] = []
    for key in keys:
        if key.path in skip:
            continue
        doc = parse_settings(text, fmt)
        name = ".".join(key.path)
        parent = lookup(doc, key.path[:-1])
        current = lookup(doc, key.path)
        if parent is not ABSENT and not isinstance(parent, dict):
            results.append(KeyResult(name, "set_by_you", _dump(parent)))
            dropped.append(key.path)
        elif current is ABSENT:
            inserted = insert_key(text, fmt, key.path, key.value)
            text = inserted.text
            writes.append(
                ConfigWrite(
                    setting, file, key.path, key.value, inserted.fragment, inserted.created_parent
                )
            )
            results.append(KeyResult(name, "wrote", _dump(key.value)))
        elif same_value(current, key.value):
            results.append(KeyResult(name, "already", _dump(key.value)))
        elif key.cli_default is not ABSENT and same_value(current, key.cli_default):
            text = replace_value(text, fmt, key.path, key.value)
            writes.append(
                ConfigWrite(setting, file, key.path, key.value, "", replaced_default=True)
            )
            results.append(KeyResult(name, "replaced_default", _dump(key.cli_default)))
        elif (old := (ours or {}).get(key.path)) is not None and same_value(current, old.value):
            try:
                text = swap_recorded(text, fmt, key.path, old.value, key.value)
            except SettingsEditRefused:
                results.append(KeyResult(name, "set_by_you", _dump(current)))
                dropped.append(key.path)
                continue
            fragment = old.fragment.replace(
                _value_text(fmt, old.value), _value_text(fmt, key.value), 1
            )
            writes.append(replace(old, value=key.value, fragment=fragment))
            results.append(KeyResult(name, "replaced_ours", _dump(current)))
        else:
            results.append(KeyResult(name, "set_by_you", _dump(current)))
            dropped.append(key.path)
    return _Pass(text, tuple(results), tuple(writes), tuple(dropped))


def _retired_block(
    agent: str, setting: str, doc: dict[str, object], ours: Mapping[KeyPath, ConfigWrite]
) -> tuple[frozenset[KeyPath], tuple[KeyResult, ...]]:
    """A retired key in the file stands for the group's current keys: the paths to skip and their
    results. The ledger recording it with the file's value makes it ours (`already`); anything
    else is the user's (`set_by_you`)."""
    skip: set[KeyPath] = set()
    results: list[KeyResult] = []
    for retired in RETIRED_KEYS.get((agent, setting), ()):
        current = lookup(doc, retired.path)
        if current is ABSENT:
            continue
        old = ours.get(retired.path)
        ours_already = old is not None and same_value(current, old.value)
        for key in _KEYS.get((agent, setting), ()):
            skip.add(key.path)
            name = ".".join(key.path)
            if ours_already:
                results.append(KeyResult(name, "already", _dump(key.value)))
            else:
                results.append(KeyResult(name, "set_by_you", _dump(current)))
    return frozenset(skip), tuple(results)


def _kept_entries(
    entries: tuple[ConfigWrite, ...], setting: str, file: str, step: _Pass
) -> tuple[ConfigWrite, ...]:
    """The ledger after a pass: entries for keys the pass wrote or dropped are replaced."""
    touched = {write.key_path for write in step.writes} | set(step.dropped)
    kept = tuple(
        entry
        for entry in entries
        if not (entry.setting == setting and entry.file == file and entry.key_path in touched)
    )
    return kept + step.writes


def _apply_once(
    agent: str,
    setting: str,
    path: Path,
    fmt: SettingsFormat,
    keys: tuple[SettingKey, ...],
    *,
    home: Path,
    skip_recorded: bool,
) -> FileResult:
    """One read, compute and reserve-then-commit write; SettingsChanged goes to the caller."""
    file = str(path)
    try:
        ledger = _ledger(agent)
        snap = read_settings(path)
        text = _text_of(snap, fmt)
        recorded = frozenset(
            entry.key_path
            for entry in ledger.entries
            if skip_recorded and entry.setting == setting and entry.file == file
        )
        ours = {
            entry.key_path: entry
            for entry in ledger.entries
            if entry.setting == setting and entry.file == file
        }
        retired_skip, retired_results = _retired_block(
            agent, setting, parse_settings(text, fmt), ours
        )
        step = _apply_pass(text, fmt, setting, file, keys, recorded | retired_skip, ours)
        keys_out = retired_results + step.keys
    except (SettingsParseError, SettingsEditRefused, OSError) as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    entries = _kept_entries(ledger.entries, setting, file, step)
    if step.text == text:
        write_ledger(replace(ledger, entries=entries))
        return FileResult(agent, setting, path, fmt, keys=keys_out)
    created = ledger.created_files
    if snap is None and file not in created:
        created = (*created, file)
    dirs = ledger.created_dirs
    if snap is None:
        dirs = (*dirs, *(d for d in missing_dirs(path, home) if d not in dirs))
    blanks = ledger.blank_files
    if snap is not None and not snap.data.strip() and file not in dict(blanks):
        blanks = (*blanks, (file, snap.data.decode("ascii")))  # restored byte for byte on revert
    try:
        # reserved before the file write
        write_ledger(
            replace(
                ledger,
                created_files=created,
                entries=entries,
                blank_files=blanks,
                created_dirs=dirs,
            )
        )
    except OSError as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    try:
        write_if_unchanged(path, snap, _with_bom(snap, step.text))
    except SettingsChanged:
        write_ledger(ledger)
        raise
    except OSError as exc:
        write_ledger(ledger)  # the write did not happen: the previous ledger stands
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    return FileResult(agent, setting, path, fmt, keys=keys_out)


def _apply_keys(
    agent: str,
    setting: str,
    keys: tuple[SettingKey, ...],
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None,
    skip_recorded: bool,
) -> FileResult:
    fmt = _format(agent)
    path = settings_file(agent, home=home, platform_os=platform_os, environ=environ)
    conflict = _conflict(agent, home=home, platform_os=platform_os, environ=environ)
    if conflict is not None:
        return FileResult(agent, setting, path, fmt, refused=conflict)
    for _attempt in range(2):
        try:
            return _apply_once(
                agent, setting, path, fmt, keys, home=home, skip_recorded=skip_recorded
            )
        except SettingsChanged:
            continue
    return FileResult(agent, setting, path, fmt, refused=CHANGED_WHILE_WRITING)


def apply_setting(
    agent: str,
    setting: str,
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None = None,
    skip_recorded: bool = False,
) -> FileResult:
    """Write each absent key of one setting and record it; a key set differently is left.

    `skip_recorded` also leaves a key the ledger records (RECONFIGURE: a recorded key the
    user deleted is their choice); an install or reinstall passes False and rewrites it.
    """
    return _apply_keys(
        agent,
        setting,
        setting_keys(agent, setting, platform_os),
        home=home,
        platform_os=platform_os,
        environ=environ,
        skip_recorded=skip_recorded,
    )


def apply_value(
    agent: str,
    setting: str,
    value: object,
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None = None,
) -> FileResult:
    """Write a dynamic setting's one key with the caller's value, absent-only like
    `apply_setting`; the ledger entry records that value, and a revert removes the key
    only while it still holds it."""
    if (agent, setting) not in DYNAMIC_KEYS:
        raise ValueError(f"{agent} {setting} is not a dynamic setting")
    (path,) = DYNAMIC_KEYS[(agent, setting)]
    return _apply_keys(
        agent,
        setting,
        (SettingKey(path, value),),
        home=home,
        platform_os=platform_os,
        environ=environ,
        skip_recorded=False,
    )


def _revert_pass(
    text: str,
    fmt: SettingsFormat,
    entries: tuple[ConfigWrite, ...],
    table: dict[KeyPath, SettingKey],
) -> tuple[str, tuple[KeyResult, ...]]:
    """Revert the entries newest first. A key whose value is no longer ours is kept and reported."""
    results: list[KeyResult] = []
    for entry in reversed(entries):
        key = table[entry.key_path]
        name = ".".join(entry.key_path)
        current = lookup(parse_settings(text, fmt), entry.key_path)
        held = key_held(current, key.value)
        if held is None:
            continue
        if not held:
            results.append(KeyResult(name, "kept_changed", _dump(current)))
        elif entry.replaced_default:
            text = replace_value(text, fmt, entry.key_path, key.cli_default)
            results.append(KeyResult(name, "removed", _dump(key.cli_default)))
        else:
            # A parent object we created that holds only our key goes with it; the guard
            # would refuse to leave an empty object behind as a child-only removal.
            parent = entry.key_path[:-1]
            if (
                entry.created_parent
                and parent
                and same_value(
                    lookup(parse_settings(text, fmt), parent), {entry.key_path[-1]: key.value}
                )
            ):
                try:
                    text = remove_key(text, fmt, parent, fragment=entry.fragment)
                except SettingsEditRefused:
                    # the user edited inside our table: remove only the owned leaf key and
                    # keep the header and their lines (still guarded by the re-parse)
                    text = remove_key(text, fmt, entry.key_path)
            else:
                text = remove_key(text, fmt, entry.key_path, fragment=entry.fragment)
            results.append(KeyResult(name, "removed", _dump(key.value)))
    return text, tuple(results)


def _empty_tree(value: object) -> bool:
    return isinstance(value, dict) and all(
        _empty_tree(v) for v in cast(dict[str, object], value).values()
    )


def _holds_no_setting(text: str, fmt: SettingsFormat) -> bool:
    """For a file the install created: True for whitespace or `{}`, and for a JSON document holding
    only empty objects and a top-level `$schema` string, what another installer-run tool leaves
    after its own uninstall (23.2 e2e #8: codegraph adds `$schema` to opencode.json and keeps it).
    A comment is content."""
    squeezed = "".join(text.split())
    if squeezed in ("", "{}"):
        return True
    if fmt == "toml" or "".join(_clean(text, fmt).split()) != squeezed:
        return False
    doc = dict(parse_settings(text, fmt))
    if isinstance(doc.get("$schema"), str):
        del doc["$schema"]
    return _empty_tree(doc)


RECORDED_FILE_GONE: Final = "missing (moved or deleted); its keys stay recorded"
NOT_A_SETTINGS_FILE: Final = "not a settings file of this agent; nothing is reverted there"


def _recorded_files(ledger: ConfigLedger, setting: str) -> tuple[str, ...]:
    """The files the ledger records this setting in, in ledger order."""
    return tuple(dict.fromkeys(e.file for e in ledger.entries if e.setting == setting))


def _revert_once(
    agent: str,
    setting: str,
    path: Path,
    fmt: SettingsFormat,
    table: dict[KeyPath, SettingKey],
    home: Path,
) -> FileResult:
    """One read, compute and write. SettingsChanged is for the caller to retry."""
    file = str(path)
    try:
        ledger = _ledger(agent)
    except LedgerUntrusted as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    if (agent, setting) in DYNAMIC_KEYS:
        # The ledger is user-writable JSON: only the allow-listed key paths enter the table.
        table = {
            entry.key_path: SettingKey(entry.key_path, entry.value)
            for entry in ledger.entries
            if entry.setting == setting
            and entry.file == file
            and entry.key_path in DYNAMIC_KEYS[(agent, setting)]
        }
    mine = tuple(
        entry
        for entry in ledger.entries
        if entry.setting == setting
        and entry.file == file
        and entry.key_path in table
        and same_value(entry.value, table[entry.key_path].value)
    )
    if not mine:
        return FileResult(agent, setting, path, fmt)
    dirs = ledger.created_dirs
    try:
        snap = read_settings(path)
        if snap is None and file not in ledger.created_files:
            # Its keys may live on under another name: never look for them in another file.
            return FileResult(agent, setting, path, fmt, refused=RECORDED_FILE_GONE)
        original = _text_of(snap, fmt)
        text, results = _revert_pass(original, fmt, mine, table)
        if text != original:
            # A created file goes only when nothing of the user's is left in it, comments too.
            bare = "".join(text.split()) in ("", "{}")
            blank = dict(ledger.blank_files).get(file)
            if snap is not None and file in ledger.created_files and _holds_no_setting(text, fmt):
                delete_if_unchanged(path, snap)
                dirs = remove_created_dirs(dirs, home)
            elif snap is not None and blank is not None and bare:
                write_if_unchanged(path, snap, blank)
            else:
                write_if_unchanged(path, snap, _with_bom(snap, text))
    except SettingsChanged:
        raise
    except (SettingsParseError, SettingsEditRefused, OSError) as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    remaining = tuple(entry for entry in ledger.entries if entry not in mine)
    # With no key of ours left in it, a created file is gone or holds only the user's content.
    released = not any(entry.file == file for entry in remaining)
    created = tuple(name for name in ledger.created_files if not (released and name == file))
    blanks = tuple(pair for pair in ledger.blank_files if not (released and pair[0] == file))
    # Directories that still hold something are only kept while another created file may use them.
    try:
        write_ledger(
            replace(
                ledger,
                created_files=created,
                entries=remaining,
                blank_files=blanks,
                created_dirs=dirs if created else (),
            )
        )
    except OSError as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    return FileResult(agent, setting, path, fmt, keys=results)


def _agent_files(
    agent: str, *, home: Path, platform_os: str, environ: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Every file this agent's settings may live in; a ledger naming another is not followed."""
    path = adapters(home, platform_os=platform_os, environ=environ)[agent].config_path
    if agent == "opencode":
        return (str(path), str(path.with_name("opencode.jsonc")))
    return (str(path),)


def _revert_file(
    agent: str,
    setting: str,
    file: str,
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None = None,
) -> FileResult:
    fmt = _format(agent)
    if file not in _agent_files(agent, home=home, platform_os=platform_os, environ=environ):
        return FileResult(agent, setting, Path(file), fmt, refused=NOT_A_SETTINGS_FILE)
    keys = (*setting_keys(agent, setting, platform_os), *RETIRED_KEYS.get((agent, setting), ()))
    table = {key.path: key for key in keys}
    for _attempt in range(2):
        try:
            return _revert_once(agent, setting, Path(file), fmt, table, home)
        except SettingsChanged:
            continue
    return FileResult(agent, setting, Path(file), fmt, refused=CHANGED_WHILE_WRITING)


def revert_group(
    agent: str,
    setting: str,
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None = None,
) -> tuple[FileResult, ...]:
    """One result per file the ledger recorded this setting in; each is reverted at the path
    that was written, never at the file the agent's settings resolve to now (CR-02)."""
    path = settings_file(agent, home=home, platform_os=platform_os, environ=environ)
    try:
        files = _recorded_files(_ledger(agent), setting)
    except LedgerUntrusted as exc:
        return (FileResult(agent, setting, path, _format(agent), refused=str(exc)),)
    if not files:
        return (FileResult(agent, setting, path, _format(agent)),)
    return tuple(
        _revert_file(agent, setting, file, home=home, platform_os=platform_os, environ=environ)
        for file in files
    )


class SettingsUnreadable(OSError):
    """A settings file the ledger manages does not parse: its state is unknown until it does."""

    def __init__(self, path: Path, fragment: str) -> None:
        super().__init__(f"{display_path(path)} is {fragment}; nothing is written until it parses")


def _read_document(
    agent: str,
    path: Path,
    fmt: SettingsFormat,
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, object] | None, str | None]:
    """The parsed document, or the fragment that says why the file cannot be read."""
    conflict = _conflict(agent, home=home, platform_os=platform_os, environ=environ)
    if conflict is not None:
        return None, conflict
    try:
        return parse_settings(_text_of(read_settings(path), fmt), fmt), None
    except (SettingsParseError, OSError) as exc:
        return None, str(exc)


def file_problem(
    agent: str, *, home: Path, platform_os: str, environ: Mapping[str, str] | None = None
) -> str | None:
    """Why the settings file cannot be read (the O7 note), or None when it reads or is missing."""
    path = settings_file(agent, home=home, platform_os=platform_os, environ=environ)
    return _read_document(
        agent, path, _format(agent), home=home, platform_os=platform_os, environ=environ
    )[1]


@dataclass(frozen=True)
class SettingFacts:
    """Where one setting stands: `path` is the file its keys live in, `absent` the keys the
    installer never recorded that the file lacks (the pending install tuning)."""

    path: Path
    absent: tuple[str, ...] = ()


def setting_facts(
    agent: str,
    setting: str,
    *,
    home: Path,
    platform_os: str,
    environ: Mapping[str, str] | None = None,
) -> SettingFacts:
    """The one classification of a setting's keys; the only place SettingsUnreadable is raised."""
    ledger = _ledger(agent)  # LedgerUntrusted is an OSError: callers read it as unreadable
    recorded_files = _recorded_files(ledger, setting)
    # The recorded file, so a written key never reads as yours after a rename (CR-02).
    path = (
        Path(recorded_files[0])
        if recorded_files
        else settings_file(agent, home=home, platform_os=platform_os, environ=environ)
    )
    in_file = tuple(
        entry for entry in ledger.entries if entry.file == str(path) and entry.setting == setting
    )
    doc, problem = _read_document(
        agent, path, _format(agent), home=home, platform_os=platform_os, environ=environ
    )
    if doc is None:
        if in_file:
            raise SettingsUnreadable(path, problem or "unreadable")
        return SettingFacts(path)  # absent stays empty: nothing is readable
    recorded = {entry.key_path for entry in in_file}
    if any(lookup(doc, key.path) is not ABSENT for key in RETIRED_KEYS.get((agent, setting), ())):
        return SettingFacts(path)  # a retired key stands for the group: ours or the user's
    absent: list[str] = []
    for key in setting_keys(agent, setting, platform_os):
        if key.path in recorded:
            continue
        parent = lookup(doc, key.path[:-1])
        if parent is not ABSENT and not isinstance(parent, dict):
            continue  # the writer reports it as set by you: never pending
        if lookup(doc, key.path) is ABSENT:
            absent.append(".".join(key.path))
    return SettingFacts(path, tuple(absent))


def revert_agent(
    agent: str, *, home: Path, platform_os: str, environ: Mapping[str, str] | None = None
) -> tuple[FileResult, ...]:
    """Revert every setting the ledger records for this agent, in ledger order."""
    try:
        ledger = _ledger(agent)
    except LedgerUntrusted as exc:
        path = settings_file(agent, home=home, platform_os=platform_os, environ=environ)
        return (FileResult(agent, "", path, _format(agent), refused=str(exc)),)
    settings = tuple(dict.fromkeys(entry.setting for entry in ledger.entries))
    return tuple(
        result
        for setting in settings
        for result in revert_group(
            agent, setting, home=home, platform_os=platform_os, environ=environ
        )
    )


def ledger_summary(agent: str, *, home: Path) -> tuple[tuple[Path, tuple[str, ...]], ...]:
    """Per settings file under home, the dotted keys the ledger records there (removal previews).
    Accepted limit: a file outside home (an absolute COPILOT_HOME) is reverted but never listed."""
    ledger = read_ledger(agent) or ConfigLedger(agent)
    keys_by_file: dict[str, list[str]] = {}
    for entry in ledger.entries:
        if Path(entry.file).is_relative_to(home):
            keys_by_file.setdefault(entry.file, []).append(".".join(entry.key_path))
    return tuple((Path(file), tuple(keys)) for file, keys in keys_by_file.items())


def ledger_preview(
    agent: str, *, home: Path
) -> tuple[tuple[Path, tuple[str, ...], tuple[str, ...]], ...]:
    """Per ledgered file under home: (path, keys a revert removes, keys the user changed since).
    A key that is gone is in neither. A missing or unreadable file lists every key as removed;
    the revert itself then reports why it cannot (removal previews)."""
    fmt = _format(agent)
    preview: list[tuple[Path, tuple[str, ...], tuple[str, ...]]] = []
    for path, names in ledger_summary(agent, home=home):
        entries = [
            e for e in (read_ledger(agent) or ConfigLedger(agent)).entries if e.file == str(path)
        ]
        try:
            snap = read_settings(path)
            doc = None if snap is None else parse_settings(_text_of(snap, fmt), fmt)
        except (SettingsParseError, OSError):
            doc = None
        if doc is None:
            preview.append((path, names, ()))
            continue
        held = [key_held(lookup(doc, e.key_path), e.value) for e in entries]
        removes = tuple(n for n, h in zip(names, held, strict=True) if h)
        kept = tuple(n for n, h in zip(names, held, strict=True) if h is False)
        preview.append((path, removes, kept))
    return tuple(preview)
