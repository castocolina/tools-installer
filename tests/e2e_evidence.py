"""Pure transcript-bound evidence checks shared by container targets."""

import datetime
import hashlib
import re
from collections.abc import Mapping


def transcript_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def transcript_problem(text: str, expected: Mapping[str, tuple[str, ...]]) -> str | None:
    lines = [line for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(marker in line for marker in ("_FAILED", "_UNPROVEN", "TRACER_LANDING_INFEASIBLE")):
            return f"{line} is in the transcript"
    previous = -1
    previous_prefix = ""
    for prefixes in expected.values():
        for prefix in prefixes:
            positions = [i for i, line in enumerate(lines) if line.startswith(prefix)]
            if len(positions) != 1:
                return f"{prefix} count is {len(positions)}, expected one"
            if positions[0] <= previous:
                return f"{prefix} is out of order after {previous_prefix}"
            previous, previous_prefix = positions[0], prefix
    marker = "TRACER_LANDING_TEARDOWN_OK"
    if lines.count(marker) != 1 or not lines or lines[-1] != marker:
        return f"expected exactly one {marker} as the last line"
    return None


def gate_problem(
    name: str,
    summary: str | None,
    transcript: bytes | None,
    expected: Mapping[str, tuple[str, ...]],
) -> str | None:
    if summary is None:
        return "summary is missing"
    if transcript is None:
        return "transcript is missing"
    lines = summary.splitlines()
    try:
        start = lines.index("## Orchestrator verification")
    except ValueError:
        return "verification section is missing"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    matches = [(i, line) for i, line in enumerate(lines) if line.startswith(f"{name}:")]
    if len(matches) != 1:
        return f"expected exactly one {name} line"
    index, line = matches[0]
    if not start < index < end:
        return f"{name} line is outside the verification section"
    match = re.fullmatch(
        rf"{re.escape(name)}: PASS \((\d{{4}}-\d{{2}}-\d{{2}}); "
        r"transcript ([0-9a-f]{12})(?:; ([^)]+))?\)",
        line,
    )
    if match is None:
        return f"malformed {name} line"
    date, digest, note = match.groups()
    if note and any(marker in note for marker in ("UNPROVEN", "INFEASIBLE")):
        return f"verification note contains {note}"
    try:
        if datetime.date.fromisoformat(date).isoformat() != date:
            return "invalid date"
    except ValueError:
        return "invalid date"
    problem = transcript_problem(transcript.decode("utf-8", errors="replace"), expected)
    if problem:
        return problem
    if transcript_digest(transcript) != digest:
        return "transcript digest does not match"
    return None
