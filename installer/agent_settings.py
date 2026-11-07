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
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from installer.atomic import FileSnapshot, atomic_write_text, read_snapshot, snapshot_matches

SettingsFormat = Literal["json", "jsonc", "toml"]
KeyPath = tuple[str, ...]
FORMAT_NAMES: Final = {"json": "JSON", "jsonc": "JSONC", "toml": "TOML"}
CHANGED_WHILE_WRITING: Final = "changed while being written"
_WHITESPACE: Final = " \t\r\n"


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


def parse_settings(text: str, fmt: SettingsFormat) -> dict[str, object]:
    """The document as a dict; whitespace-only text is an empty object."""
    if fmt != "json":
        raise NotImplementedError(fmt)  # JSONC and TOML are added by the next tasks of this plan
    if not text.strip():
        return {}
    try:
        doc: object = json.loads(text)
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


def _object_open(text: str, path: KeyPath) -> int:
    """Index of the `{` of the object at path; text must already parse."""
    index = _skip_ws(text, 0)
    for key in path:
        members, _ = _members(text, index)
        index = [member for member in members if member.key == key][-1].value_start
    return index


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
    """A copy of doc with key_path set to value, or removed when value is ABSENT."""
    expected = copy.deepcopy(doc)
    node = expected
    for key in key_path[:-1]:
        node = cast(dict[str, object], node[key])
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
    """Insert one absent key by splice. The fragment is the text a later revert removes."""
    doc = parse_settings(text, fmt)
    if not text.strip():
        raise SettingsEditRefused("empty file: there is no object to insert into")
    if lookup(doc, key_path) is not ABSENT:
        raise SettingsEditRefused(f"{'.'.join(key_path)} is already set")
    parent = key_path[:-1]
    if parent and not isinstance(lookup(doc, parent), dict):
        raise SettingsEditRefused(f"{'.'.join(parent)} must be an existing object")
    obj = _object_open(text, parent)
    members, _ = _members(text, obj)
    if not members:
        raise SettingsEditRefused("empty object: inserting into it is not supported yet")
    line_start = text.rfind("\n", 0, members[0].key_start) + 1
    indent = text[line_start : members[0].key_start]
    name = json.dumps(key_path[-1], ensure_ascii=False)
    fragment = f"\n{indent}{name}: {json.dumps(value, ensure_ascii=False)},"
    new_text = text[: obj + 1] + fragment + text[obj + 1 :]
    expected = _edited(doc, key_path, value)
    return Inserted(_guarded(new_text, fmt, expected), fragment, created_parent=False)


def _cut_member(text: str, members: list[_Member], member: _Member) -> str:
    """Text without the member: its own line when it stands alone, plus the following comma
    or, for the last member, the preceding one."""
    start = member.key_start
    while start > 0 and text[start - 1] in " \t":
        start -= 1
    end = member.value_end
    after = _skip_ws(text, end)
    comma_before = -1
    if text[after] == ",":
        end = after + 1
    elif member is not members[0]:
        probe = start - 1
        while text[probe] in _WHITESPACE:
            probe -= 1
        comma_before = probe
    if start == 0 or text[start - 1] == "\n":
        probe = end
        while text[probe] in " \t":
            probe += 1
        if text[probe] == "\n":
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
    members, _ = _members(text, _object_open(text, key_path[:-1]))
    member = [m for m in members if m.key == key_path[-1]][-1]
    located = text[member.key_start : member.value_end]
    if fragment is not None and text.count(fragment) == 1 and located in fragment:
        new_text = text.replace(fragment, "", 1)
    else:
        new_text = _cut_member(text, members, member)
    return _guarded(new_text, fmt, _edited(doc, key_path, ABSENT))


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
