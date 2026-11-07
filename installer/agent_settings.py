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
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from installer.atomic import FileSnapshot, atomic_write_text, read_snapshot, snapshot_matches

SettingsFormat = Literal["json", "jsonc", "toml"]
KeyPath = tuple[str, ...]
FORMAT_NAMES: Final = {"json": "JSON", "jsonc": "JSONC", "toml": "TOML"}
CHANGED_WHILE_WRITING: Final = "changed while being written"
_WHITESPACE: Final = " \t\r\n"
# A string is kept so that "//" inside a URL is data; a comment and a comma that
# closes an object or array (a trailing comma) are blanked, newlines kept.
_JSONC_TOKEN: Final = re.compile(
    r'("(?:\\.|[^"\\])*")'
    r"|(//[^\n]*|/\*.*?\*/)"
    r"|(,)(?=(?:\s|//[^\n]*|/\*.*?\*/)*[}\]])",
    re.DOTALL,
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


def _toml_key(key_path: KeyPath) -> str:
    if len(key_path) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", key_path[0]):
        raise SettingsEditRefused("TOML keys are top-level bare keys")
    return key_path[0]


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _dump(value)
    raise SettingsEditRefused(
        f"TOML values here are strings or booleans, not {type(value).__name__}"
    )


def _insert_toml(text: str, doc: dict[str, object], key_path: KeyPath, value: object) -> Inserted:
    """A top-level key goes on its own line before the first table header, or at the end."""
    key = _toml_key(key_path)
    lines = text.splitlines(keepends=True)
    table = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    fragment = f"{key} = {_toml_value(value)}\n"
    if table == len(lines) and text and not text.endswith("\n"):
        fragment = "\n" + fragment
    new_text = "".join(lines[:table]) + fragment + "".join(lines[table:])
    expected = _edited(doc, key_path, value)
    return Inserted(_guarded(new_text, "toml", expected), fragment, created_parent=False)


def _toml_remove(text: str, key: str, fragment: str | None) -> str:
    """The recorded fragment when it occurs once, else the key's own top-level line."""
    if fragment is not None and text.count(fragment) == 1:
        return text.replace(fragment, "", 1)
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().startswith("["):
            break
        if re.match(rf"\s*{re.escape(key)}\s*=", line):
            return "".join(lines[:index] + lines[index + 1 :])
    raise SettingsEditRefused(f"{key} has no top-level line to remove")


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
    """Remove one set key. The recorded fragment is cut when it occurs once and holds the member;
    otherwise the located member is cut, so a vendor re-serialization still reverts."""
    doc = parse_settings(text, fmt)
    if lookup(doc, key_path) is ABSENT:
        raise SettingsEditRefused(f"{'.'.join(key_path)} is not set")
    if fmt == "toml":
        new_text = _toml_remove(text, _toml_key(key_path), fragment)
        return _guarded(new_text, fmt, _edited(doc, key_path, ABSENT))
    clean = _clean(text, fmt)
    members, member = _member_at(clean, key_path)
    located = text[member.key_start : member.value_end]
    if fragment is not None and text.count(fragment) == 1 and located in fragment:
        new_text = text.replace(fragment, "", 1)
    else:
        new_text = _cut_member(text, clean, members, member)
    return _guarded(new_text, fmt, _edited(doc, key_path, ABSENT))


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
