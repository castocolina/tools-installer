"""Manage ~/.myshellrc as one marker-delimited PATH block, and wire `source` into rc files.

Every write is idempotent: only the marked block is ever rewritten, user content is
preserved, and entries are never duplicated across runs.
"""

from pathlib import Path

from installer.model import Tool

_PATH_BEGIN = "# >>> tools-installer path >>>"
_PATH_END = "# <<< tools-installer path <<<"
_SOURCE_BEGIN = "# >>> tools-installer source >>>"
_SOURCE_END = "# <<< tools-installer source <<<"


def collect_bin_dirs(tools: list[Tool], default: Path) -> list[Path]:
    """The default bin dir plus every method-declared bin_dir, expanded and deduped in order."""
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            dirs.append(resolved)

    add(default)
    for tool in tools:
        for method in tool.methods:
            raw = method.params.get("bin_dir")
            if isinstance(raw, str) and raw:
                add(Path(raw))
    return dirs


def managed_block(bin_dirs: list[Path]) -> str:
    """Marker-delimited block exporting each bin dir onto PATH."""
    lines = [_PATH_BEGIN]
    lines.extend(f'export PATH="{directory}:$PATH"' for directory in bin_dirs)
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


def write_myshellrc(bin_dirs: list[Path], path: Path) -> None:
    """Idempotently write the managed PATH block into ~/.myshellrc, preserving the rest."""
    existing = path.read_text() if path.exists() else ""
    path.write_text(apply_block(existing, managed_block(bin_dirs)))


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
    rc_path.write_text(apply_block(existing, block, begin=_SOURCE_BEGIN, end=_SOURCE_END))
