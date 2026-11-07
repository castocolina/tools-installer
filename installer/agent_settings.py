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

from installer.agent_env import adapters
from installer.atomic import FileSnapshot, atomic_write_text, read_snapshot, snapshot_matches
from installer.locations import display_path
from installer.receipts import ConfigLedger, ConfigWrite, read_ledger, write_ledger

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
    """Remove one set key. The recorded fragment is cut when it occurs once, holds the member
    and the result re-parses; otherwise the located member is cut, so a later edit around the
    member or a vendor re-serialization still reverts."""
    doc = parse_settings(text, fmt)
    if lookup(doc, key_path) is ABSENT:
        raise SettingsEditRefused(f"{'.'.join(key_path)} is not set")
    expected = _edited(doc, key_path, ABSENT)
    if fmt == "toml":
        return _guarded(_toml_remove(text, _toml_key(key_path), fragment), fmt, expected)
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


KeyKind = Literal["wrote", "set_by_you", "already", "replaced_default", "removed", "kept_changed"]
AGENT_FORMATS: Final[dict[str, SettingsFormat]] = {
    "claude": "json",
    "codex": "toml",
    "opencode": "jsonc",
    "cursor-agent": "json",
    "vscode": "jsonc",
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
    ("opencode", "auto-approve"): (SettingKey(("permission",), "allow"),),
    ("cursor-agent", "auto-approve"): (SettingKey(("approvalMode",), "unrestricted"),),
    ("cursor-agent", "no-attribution"): (
        SettingKey(("attribution", "attributeCommitsToAgent"), False, cli_default=True),
        SettingKey(("attribution", "attributePRsToAgent"), False, cli_default=True),
    ),
    ("vscode", "vscode-ai-off"): (SettingKey(("chat.disableAIFeatures",), True),),
    ("vscode", "vscode-ext-updates-off"): (
        SettingKey(("extensions.autoUpdate",), False),
        SettingKey(("extensions.autoCheckUpdates",), False),
    ),
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


def settings_file(agent: str, *, home: Path, platform_os: str) -> Path:
    """The file an agent's settings live in: its adapter path; opencode prefers .jsonc."""
    _format(agent)
    path = adapters(home, platform_os=platform_os)[agent].config_path
    if agent == "opencode" and os.path.lexists(path.with_name("opencode.jsonc")):
        return path.with_name("opencode.jsonc")
    return path


def _conflict(agent: str, *, home: Path, platform_os: str) -> str | None:
    """The refusal when an agent's settings could live in either of two files (opencode)."""
    if agent != "opencode":
        return None
    json_path = adapters(home, platform_os=platform_os)[agent].config_path
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


def _text_of(snap: FileSnapshot | None, fmt: SettingsFormat) -> str:
    """The file's text; a missing file is its new content, and non-UTF-8 bytes read as line 1."""
    if snap is None:
        return new_file_text(fmt)
    try:
        return snap.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SettingsParseError(fmt, 1, None) from exc


@dataclass(frozen=True)
class _Pass:
    """One computed edit: the new text, the per-key results, and the ledger changes it implies."""

    text: str
    keys: tuple[KeyResult, ...]
    writes: tuple[ConfigWrite, ...]
    dropped: tuple[KeyPath, ...]


def _apply_pass(
    text: str, fmt: SettingsFormat, setting: str, file: str, keys: tuple[SettingKey, ...]
) -> _Pass:
    results: list[KeyResult] = []
    writes: list[ConfigWrite] = []
    dropped: list[KeyPath] = []
    for key in keys:
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
        else:
            results.append(KeyResult(name, "set_by_you", _dump(current)))
            dropped.append(key.path)
    return _Pass(text, tuple(results), tuple(writes), tuple(dropped))


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
    agent: str, setting: str, path: Path, fmt: SettingsFormat, keys: tuple[SettingKey, ...]
) -> FileResult:
    """One read, compute and reserve-then-commit write; SettingsChanged goes to the caller."""
    file = str(path)
    ledger = read_ledger(agent) or ConfigLedger(agent)
    try:
        snap = read_settings(path)
        text = _text_of(snap, fmt)
        step = _apply_pass(text, fmt, setting, file, keys)
    except (SettingsParseError, SettingsEditRefused, OSError) as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    entries = _kept_entries(ledger.entries, setting, file, step)
    if step.text == text:
        write_ledger(ConfigLedger(agent, ledger.created_files, entries))
        return FileResult(agent, setting, path, fmt, keys=step.keys)
    created = ledger.created_files
    if snap is None and file not in created:
        created = (*created, file)
    try:
        write_ledger(ConfigLedger(agent, created, entries))  # reserved before the file write
    except OSError as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    try:
        write_if_unchanged(path, snap, step.text)
    except SettingsChanged:
        write_ledger(ledger)
        raise
    except OSError as exc:
        write_ledger(ledger)  # the write did not happen: the previous ledger stands
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    return FileResult(agent, setting, path, fmt, keys=step.keys)


def apply_setting(agent: str, setting: str, *, home: Path, platform_os: str) -> FileResult:
    """Write each absent key of one setting and record it; a key set differently is left."""
    fmt = _format(agent)
    path = settings_file(agent, home=home, platform_os=platform_os)
    conflict = _conflict(agent, home=home, platform_os=platform_os)
    if conflict is not None:
        return FileResult(agent, setting, path, fmt, refused=conflict)
    keys = setting_keys(agent, setting, platform_os)
    for _attempt in range(2):
        try:
            return _apply_once(agent, setting, path, fmt, keys)
        except SettingsChanged:
            continue
    return FileResult(agent, setting, path, fmt, refused=CHANGED_WHILE_WRITING)


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
        if current is ABSENT:
            continue
        if not same_value(current, key.value):
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
                text = remove_key(text, fmt, parent, fragment=entry.fragment)
            else:
                text = remove_key(text, fmt, entry.key_path, fragment=entry.fragment)
            results.append(KeyResult(name, "removed", _dump(key.value)))
    return text, tuple(results)


def _revert_once(
    agent: str,
    setting: str,
    path: Path,
    fmt: SettingsFormat,
    table: dict[KeyPath, SettingKey],
) -> FileResult:
    """One read, compute and write. SettingsChanged is for the caller to retry."""
    file = str(path)
    ledger = read_ledger(agent) or ConfigLedger(agent)
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
    deleted = False
    try:
        snap = read_settings(path)
        original = _text_of(snap, fmt)
        text, results = _revert_pass(original, fmt, mine, table)
        if text != original:
            if snap is not None and file in ledger.created_files and not parse_settings(text, fmt):
                delete_if_unchanged(path, snap)
                deleted = True
            else:
                write_if_unchanged(path, snap, text)
    except SettingsChanged:
        raise
    except (SettingsParseError, SettingsEditRefused, OSError) as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    gone = deleted or (snap is None and file in ledger.created_files)
    created = tuple(name for name in ledger.created_files if not (gone and name == file))
    remaining = tuple(entry for entry in ledger.entries if entry not in mine)
    try:
        write_ledger(ConfigLedger(agent, created, remaining))
    except OSError as exc:
        return FileResult(agent, setting, path, fmt, refused=str(exc))
    return FileResult(agent, setting, path, fmt, keys=results)


def revert_setting(agent: str, setting: str, *, home: Path, platform_os: str) -> FileResult:
    """Undo the ledger's keys for this setting that still hold our value; anything else is left."""
    fmt = _format(agent)
    table = {key.path: key for key in setting_keys(agent, setting, platform_os)}
    path = settings_file(agent, home=home, platform_os=platform_os)
    conflict = _conflict(agent, home=home, platform_os=platform_os)
    if conflict is not None:
        return FileResult(agent, setting, path, fmt, refused=conflict)
    for _attempt in range(2):
        try:
            return _revert_once(agent, setting, path, fmt, table)
        except SettingsChanged:
            continue
    return FileResult(agent, setting, path, fmt, refused=CHANGED_WHILE_WRITING)


SettingState = Literal["on", "yours", "off", "drift"]


class SettingsUnreadable(OSError):
    """A settings file the ledger manages does not parse: its state is unknown until it does."""

    def __init__(self, path: Path, fragment: str) -> None:
        super().__init__(f"{display_path(path)} is {fragment}; nothing is written until it parses")


def _read_document(
    agent: str, path: Path, fmt: SettingsFormat, *, home: Path, platform_os: str
) -> tuple[dict[str, object] | None, str | None]:
    """The parsed document, or the fragment that says why the file cannot be read."""
    conflict = _conflict(agent, home=home, platform_os=platform_os)
    if conflict is not None:
        return None, conflict
    try:
        return parse_settings(_text_of(read_settings(path), fmt), fmt), None
    except (SettingsParseError, OSError) as exc:
        return None, str(exc)


def file_problem(agent: str, *, home: Path, platform_os: str) -> str | None:
    """Why the settings file cannot be read (the O7 note), or None when it reads or is missing."""
    path = settings_file(agent, home=home, platform_os=platform_os)
    return _read_document(agent, path, _format(agent), home=home, platform_os=platform_os)[1]


@dataclass(frozen=True)
class SettingFacts:
    """Who put each of one setting's keys where it now is; `path` is the file they live in."""

    path: Path
    written: tuple[str, ...]  # recorded keys still holding our value
    set_by_you: tuple[tuple[str, str], ...]  # (key, JSON value): another value, no record
    already: tuple[str, ...]  # keys holding our value, no record
    drifted: tuple[str, ...]  # recorded keys that no longer hold our value


def setting_facts(agent: str, setting: str, *, home: Path, platform_os: str) -> SettingFacts:
    """The one classification of a setting's keys; the only place SettingsUnreadable is raised."""
    path = settings_file(agent, home=home, platform_os=platform_os)
    ledger = read_ledger(agent) or ConfigLedger(agent)
    in_file = tuple(
        entry for entry in ledger.entries if entry.file == str(path) and entry.setting == setting
    )
    doc, problem = _read_document(agent, path, _format(agent), home=home, platform_os=platform_os)
    if doc is None:
        if in_file:
            raise SettingsUnreadable(path, problem or "unreadable")
        return SettingFacts(path, (), (), (), ())
    holding = tuple(
        ".".join(entry.key_path)
        for entry in in_file
        if same_value(lookup(doc, entry.key_path), entry.value)
    )
    drifted = tuple(
        ".".join(entry.key_path)
        for entry in in_file
        if not same_value(lookup(doc, entry.key_path), entry.value)
    )
    recorded = {entry.key_path for entry in in_file}
    set_by_you: list[tuple[str, str]] = []
    already: list[str] = []
    for key in setting_keys(agent, setting, platform_os):
        current = lookup(doc, key.path)
        if key.path in recorded or current is ABSENT:
            continue
        if same_value(current, key.value):
            already.append(".".join(key.path))
        elif not (key.cli_default is not ABSENT and same_value(current, key.cli_default)):
            # A CLI default is replaced on apply, so it is not the user's own value.
            set_by_you.append((".".join(key.path), _dump(current)))
    return SettingFacts(path, holding, tuple(set_by_you), tuple(already), drifted)


def setting_state(agent: str, setting: str, *, home: Path, platform_os: str) -> SettingState:
    """on: a recorded key still holds ours. drift: recorded keys were all changed by someone else.
    yours: every key holds ours and nothing is recorded. off: anything else."""
    facts = setting_facts(agent, setting, home=home, platform_os=platform_os)
    if facts.written:
        return "on"
    if facts.drifted:
        return "drift"
    keys = setting_keys(agent, setting, platform_os)
    if keys and len(facts.already) == len(keys):
        return "yours"
    return "off"


def revert_agent(agent: str, *, home: Path, platform_os: str) -> tuple[FileResult, ...]:
    """Revert every setting the ledger records for this agent, in ledger order."""
    ledger = read_ledger(agent) or ConfigLedger(agent)
    settings = tuple(dict.fromkeys(entry.setting for entry in ledger.entries))
    return tuple(
        revert_setting(agent, setting, home=home, platform_os=platform_os) for setting in settings
    )


def ledger_summary(
    agent: str, *, home: Path, platform_os: str
) -> tuple[tuple[Path, tuple[str, ...]], ...]:
    """Per settings file under home, the dotted keys the ledger records there (removal previews)."""
    ledger = read_ledger(agent) or ConfigLedger(agent)
    keys_by_file: dict[str, list[str]] = {}
    for entry in ledger.entries:
        if Path(entry.file).is_relative_to(home):
            keys_by_file.setdefault(entry.file, []).append(".".join(entry.key_path))
    return tuple((Path(file), tuple(keys)) for file, keys in keys_by_file.items())
