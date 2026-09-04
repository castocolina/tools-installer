#!/usr/bin/env python3
# tools-installer-helper: wait_time
"""Flexible countdown helper installed by the countdown policy."""

from __future__ import annotations

import datetime as dt
import math
import os
import re
import sys
import time

ORANGE_BLINK = "\033[5;38;5;208m"
RED_FAST_BLINK = "\033[6;31m"
RESET = "\033[0m"
CLEAR_LINE = "\033[0K"


def current_time() -> dt.datetime:
    fixed = os.environ.get("WAIT_TIME_NOW")
    if fixed:
        return dt.datetime.fromisoformat(fixed)
    return dt.datetime.now()


def parse_duration(text: str) -> int | None:
    value = text.lower().strip()
    if re.fullmatch(r"\d+", value):
        return int(value)
    parts = re.findall(r"(\d+)\s*([dhms])", value)
    if not parts:
        return None
    residue = re.sub(r"(\d+)\s*([dhms])", "", value)
    if residue.strip():
        return None
    scale = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(int(amount) * scale[unit] for amount, unit in parts)


def parse_clock(text: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(
        r"(\d{1,2})(?::(\d{2})(?::(\d{2})(?:[:.](\d{1,6}))?)?)?\s*(am|pm)?",
        text.lower(),
    )
    if not match:
        raise ValueError("expected a duration or target time")
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    second = int(match.group(3) or 0)
    microsecond = int((match.group(4) or "0").ljust(6, "0"))
    meridiem = match.group(5)
    if meridiem:
        if hour < 1 or hour > 12:
            raise ValueError("12-hour times must use hours 1 through 12")
        if meridiem == "am" and hour == 12:
            hour = 0
        elif meridiem == "pm" and hour != 12:
            hour += 12
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("time is outside the valid clock range")
    return hour, minute, second, microsecond


def parse_compact_date(text: str, base: dt.datetime) -> tuple[int, int, int, bool]:
    if len(text) == 4:
        return base.year, int(text[:2]), int(text[2:]), True
    if len(text) == 6:
        return 2000 + int(text[:2]), int(text[2:4]), int(text[4:]), False
    if len(text) == 8:
        return int(text[:4]), int(text[4:6]), int(text[6:]), False
    raise ValueError("dates must be MMDD, YYMMDD, or YYYYMMDD")


def parse_target(text: str, base: dt.datetime) -> dt.datetime:
    value = text.strip()
    tomorrow = False
    if value.lower().startswith("tomorrow "):
        tomorrow = True
        value = value.split(None, 1)[1]

    date_match = re.fullmatch(r"(?:(\d{4}|\d{6}|\d{8})[- T])?(.+)", value)
    if not date_match:
        raise ValueError("expected a duration or target time")
    date_text, clock_text = date_match.groups()
    hour, minute, second, microsecond = parse_clock(clock_text.strip())

    if date_text:
        year, month, day, roll_year = parse_compact_date(date_text, base)
        target = dt.datetime(year, month, day, hour, minute, second, microsecond)
        if roll_year and target <= base:
            target = dt.datetime(year + 1, month, day, hour, minute, second, microsecond)
        return target

    target_date = base.date() + (dt.timedelta(days=1) if tomorrow else dt.timedelta())
    target = dt.datetime.combine(target_date, dt.time(hour, minute, second, microsecond))
    if not tomorrow and target <= base:
        target += dt.timedelta(days=1)
    return target


def parse_seconds(argv: list[str]) -> int:
    if not argv:
        return 0
    text = " ".join(argv).strip()
    seconds = parse_duration(text)
    if seconds is not None:
        return seconds
    base = current_time()
    target = parse_target(text, base)
    return max(0, math.ceil((target - base).total_seconds()))


def left_time(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    remaining = seconds % 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{remaining}s")
    return " ".join(parts)


def current_clock() -> str:
    return os.environ.get("WAIT_TIME_CLOCK", dt.datetime.now().strftime("%H:%M:%S"))


def style_for(current: int, initial: int) -> tuple[str, str]:
    if initial > 0 and current * 100 <= initial * 5:
        return RED_FAST_BLINK, RESET
    if initial > 0 and current * 100 < initial * 10:
        return ORANGE_BLINK, RESET
    return "", ""


def render_line(current: int, initial: int) -> str:
    style, reset = style_for(current, initial)
    return f"    {style}now {current_clock()} | left {left_time(current)}{reset}{CLEAR_LINE}"


def usage() -> None:
    print("usage: wait_time [--seconds|--preview] <seconds|1d10m15s|23h 49m|10am>")
    print("       wait_time [--seconds|--preview] <tomorrow 10am|MMDD HH:MM[:SS]>")
    print("       wait_time [--seconds|--preview] <YYMMDD-HH:MM[:SS[:ms]]>")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--help":
        usage()
        return 0
    mode = "countdown"
    if args and args[0] == "--seconds":
        mode = "seconds"
        args = args[1:]
    elif args and args[0] == "--preview":
        mode = "preview"
        args = args[1:]
    try:
        seconds = parse_seconds(args)
    except Exception as exc:
        print(f"wait_time: {exc}", file=sys.stderr)
        return 2
    if mode == "seconds":
        print(seconds)
        return 0
    initial = seconds
    if mode == "preview":
        print(render_line(seconds, initial))
        return 0
    while seconds > 0:
        print(render_line(seconds, initial), end="\r", flush=True)
        time.sleep(1)
        seconds -= 1
    print(f"{CLEAR_LINE}\r", end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
