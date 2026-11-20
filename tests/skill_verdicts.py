"""Shared skill-judge verdict checks: one parser and one grader for every skill test."""

from __future__ import annotations

import json
from typing import Any, cast

VERDICT_KEYS = frozenset(
    {
        "skill",
        "judge",
        "rubric_version",
        "spec_sha",
        "scores",
        "max",
        "total",
        "max_total",
        "percent",
        "grade",
        "findings",
    }
)
GRADE_FLOORS = ((90, "A"), (80, "B"), (70, "C"), (60, "D"))
PASS_PERCENT = 80.0
DIMENSIONS = tuple(f"D{i}" for i in range(1, 9))
RUBRIC_MAX = (20, 15, 15, 15, 15, 15, 15, 15)


def grade(percent: float) -> str:
    return next((grade for floor, grade in GRADE_FLOORS if percent >= floor), "F")


def parse_verdict(document: str, *, final: bool) -> dict[str, Any]:
    """The one verdict line of a skill-judge document; ValueError names the reason."""
    candidates: list[dict[str, Any]] = []
    for line in document.splitlines():
        try:
            obj = json.loads(line.strip())
        except ValueError:
            continue
        if isinstance(obj, dict) and "scores" in obj:
            candidates.append(cast("dict[str, Any]", obj))
    if len(candidates) != 1:
        raise ValueError(f"expected one verdict line, found {len(candidates)}")
    verdict = candidates[0]
    missing = VERDICT_KEYS - verdict.keys()
    if missing:
        raise ValueError(f"missing keys {sorted(missing)}")
    if not isinstance(verdict["scores"], dict) or not isinstance(verdict["max"], dict):
        raise ValueError("scores and max must be objects")
    scores = cast("dict[str, int]", verdict["scores"])
    maxima = cast("dict[str, int]", verdict["max"])
    if scores.keys() != maxima.keys():
        raise ValueError("scores and max name different dimensions")
    if scores.keys() != set(DIMENSIONS):
        raise ValueError("scores must name exactly D1..D8")
    for dim, score in scores.items():
        if not 0 <= score <= maxima[dim]:
            raise ValueError(f"{dim} score {score} outside 0..{maxima[dim]}")
    if verdict["total"] != sum(scores.values()):
        raise ValueError("total is not the sum of scores")
    if verdict["max_total"] != sum(maxima.values()):
        raise ValueError("max_total is not the sum of max")
    percent = round(verdict["total"] / verdict["max_total"] * 100, 1)
    if verdict["percent"] != percent:
        raise ValueError(f"percent is {verdict['percent']}, rounding gives {percent}")
    if verdict["grade"] != grade(percent):
        raise ValueError(f"grade {verdict['grade']} does not match {percent}")
    if final and percent < PASS_PERCENT:
        raise ValueError(f"final percent {percent} is below {PASS_PERCENT}")
    return verdict
