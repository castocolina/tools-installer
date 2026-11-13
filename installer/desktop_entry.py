"""Render an upstream `.desktop` file so it points at the installed binary and icon.

Pure: the caller stages and places the text. A path that is relative or holds a
control character is refused, the `terminal_shell._safe_executable` posture, so
no value can end a line and inject a key.
"""

from pathlib import Path

# Desktop Entry spec, `Exec`: an argument holding one of these must be double-quoted.
_EXEC_RESERVED = frozenset(" \t\n\"'\\><~|&;$*?#()`")
# Inside the quotes these four take a backslash; the string rule doubles each backslash again.
_QUOTED_ESCAPES = {'"': '\\\\"', "`": "\\\\`", "$": "\\\\$", "\\": "\\\\\\\\"}


class DesktopEntryError(ValueError):
    """A path cannot be written into a desktop entry safely."""


def _checked(path: Path, what: str) -> str:
    text = str(path)
    if not path.is_absolute():
        raise DesktopEntryError(f"{what} path must be absolute: {text!r}")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise DesktopEntryError(f"{what} path holds a control character: {text!r}")
    return text


def _exec_program(text: str) -> str:
    text = text.replace("%", "%%")
    if not any(char in _EXEC_RESERVED for char in text):
        return text
    return '"' + "".join(_QUOTED_ESCAPES.get(char, char) for char in text) + '"'


def render(source: str, *, binary: Path, icon: Path | None) -> str:
    """`source` with TryExec, each Exec program and (when given) Icon set to absolute paths."""
    plain_binary = _checked(binary, "binary")
    program = _exec_program(plain_binary)
    plain_icon = None if icon is None else _checked(icon, "icon")
    out: list[str] = []
    for line in source.splitlines():
        if line.startswith("TryExec="):
            out.append(f"TryExec={plain_binary}")
        elif line.startswith("Exec="):
            _old_program, space, arguments = line.removeprefix("Exec=").partition(" ")
            out.append(f"Exec={program}{space}{arguments}")
        elif line.startswith("Icon=") and plain_icon is not None:
            out.append(f"Icon={plain_icon}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"
