#!/usr/bin/env python3
# tools-installer-helper: prune-daemon
#
# /// script
# requires-python = ">=3.11"
# ///
#
# The requires-python constraint above is load-bearing, not decorative: live
# Tier-3 verification on this machine (a real launchctl bootstrap + kickstart
# of this exact wrapper) proved that WITHOUT it, `uv run --no-project --script`
# resolves an entirely different interpreter depending on the caller's current
# working directory. Invoked from inside this repo (interactive testing), uv
# happily reuses this project's own 3.14 venv; invoked from any OTHER cwd --
# which is exactly what launchd does for a real scheduled run, never this
# repo's directory -- uv instead fell back to macOS's ancient Command Line
# Tools python3 (3.9.6 on this machine), which lacks `datetime.UTC` (added in
# 3.11) and crashes this module's own main() on every single real invocation.
# A PEP 723 inline requires-python constraint makes `uv run --script` honor it
# regardless of cwd, downloading/selecting a compliant interpreter from uv's
# own managed toolchain instead of falling back to whatever system Python
# happens to be first on PATH.
"""Standalone wrapper invoked by the scheduled LaunchAgent via `uv run --script`.

Runs the script named by --script with the forwarded argv, appends a single
timestamped block (stdout+stderr, plus an `(exit N)` note on a non-zero exit)
to the log file, truncates that log when it exceeds a byte cap, and always
exits 0 regardless of the wrapped script's own outcome -- launchd has no one
watching a scheduled job's exit code interactively, and a wrapper that
propagated the script's failure as its own crash would leave nothing in the
log at all for that run.

Argv contract: `--script PATH --log PATH --cap-bytes N -- <forwarded argv...>`
-- everything after the literal "--" token is passed verbatim as argv to the
script named by --script (never re-parsed or re-interpreted), exactly the
tail `uv run --script` forwards as this process's own sys.argv[1:].

Self-contained, standard-library only: this module is invoked via
`uv run --no-project --script` from ~/.local/bin, and --no-project
deliberately skips resolving this repository's own environment, so nothing
guarantees the `installer` package is importable from wherever `uv`
provisions that bare interpreter. `_truncate` therefore lives here rather
than in installer/daemon.py (11-REVIEWS.md cycle 3 finding #3) -- this
mirrors helper_assets/wait_time.py's own self-containment as this package's
other `uv run --script`-invoked helper. This plan's own tests import this
module the SAME way tests/test_wait_time.py already imports wait_time --
`from installer.helper_assets import prune_daemon_runner` -- which works
from the TEST process (running inside this project's own uv-managed venv,
where `installer` genuinely is importable) with no bearing on the wrapper's
own production invocation, which never imports `installer` at all.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

_HEADER_PREFIX = "=== "


def _parse_argv(argv: list[str]) -> tuple[Path, Path, int, list[str]]:
    """Split argv into --script/--log/--cap-bytes and the forwarded tail.

    Manual splitting on the literal "--" token, not argparse.REMAINDER --
    avoids REMAINDER's edge cases with intermixed flags.
    """
    script_path: Path | None = None
    log_path: Path | None = None
    cap_bytes: int | None = None
    forwarded: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            forwarded = argv[index + 1 :]
            break
        if arg == "--script" and index + 1 < len(argv):
            script_path = Path(argv[index + 1])
            index += 2
            continue
        if arg == "--log" and index + 1 < len(argv):
            log_path = Path(argv[index + 1])
            index += 2
            continue
        if arg == "--cap-bytes" and index + 1 < len(argv):
            cap_bytes = int(argv[index + 1])
            index += 2
            continue
        index += 1
    if script_path is None or log_path is None or cap_bytes is None:
        raise ValueError("--script, --log, and --cap-bytes are all required")
    return script_path, log_path, cap_bytes, forwarded


def _run_script(script_path: Path, forwarded: list[str]) -> str:
    """The logged block body: combined stdout+stderr, plus an (exit N) note."""
    try:
        result = subprocess.run(
            [str(script_path), *forwarded],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return f"failed to launch {script_path}: {exc}"
    body = f"{result.stdout}{result.stderr}"
    if result.returncode != 0:
        body = f"{body}\n(exit {result.returncode})" if body else f"(exit {result.returncode})"
    return body


def _truncate(log_path: Path, cap_bytes: int) -> None:
    """Keep only the trailing `cap_bytes` window, snapped to a run boundary.

    Decodes the WHOLE file once (never a raw byte-offset window) so every cut
    this function makes lands on a decoded line boundary or on the
    errors="ignore"-recovered edge of a single hard-truncated line -- never
    mid-UTF-8-sequence (11-REVIEWS.md cycle 1 finding #4). Enforces
    `cap_bytes` as a genuine hard ceiling, not merely "no crash"
    (11-REVIEWS.md cycle 3 finding #2): an already-oversized single line is
    hard-truncated to its own trailing bytes, an oversized single run is
    capped by the same backward accumulation the header-boundary snap can
    only ever shrink, and the result always ends with exactly one trailing
    newline so the wrapper's own NEXT append can never concatenate its
    header onto the truncated file's last line.
    """
    raw = log_path.read_bytes()
    if len(raw) <= cap_bytes:
        return
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    kept: list[str] = []
    size = 0
    for line in reversed(lines):
        line_size = len(line.encode("utf-8")) + 1  # +1 for its own "\n" separator
        if not kept and line_size > cap_bytes:
            # A single line already larger than cap_bytes on its own: hard-
            # truncate it in place, keeping only the most RECENT bytes, then
            # recover from any incomplete leading multi-byte sequence the
            # byte-level slice may have introduced at the cut point.
            encoded = line.encode("utf-8")
            keep_from = max(len(encoded) - (cap_bytes - 1), 0)
            kept = [encoded[keep_from:].decode("utf-8", errors="ignore")]
            break
        if kept and size + line_size > cap_bytes:
            break
        kept.insert(0, line)
        size += line_size

    for index, line in enumerate(kept):
        if line.startswith(_HEADER_PREFIX):
            kept = kept[index:]
            break

    new_content = "\n".join(kept) + "\n" if kept else ""
    log_path.write_text(new_content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    script_path, log_path, cap_bytes, forwarded = _parse_argv(args)
    body = _run_script(script_path, forwarded)
    timestamp = dt.datetime.now(dt.UTC).isoformat()
    # Defensive fallback only -- the AUTHORITATIVE creation is
    # installer.daemon.ensure_log_path, called at apply time, before
    # launchctl bootstrap ever registers this job.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{_HEADER_PREFIX}{timestamp} ===\n{body}\n")
    _truncate(log_path, cap_bytes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
