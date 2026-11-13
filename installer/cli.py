"""Parse non-interactive CLI flags into an Options value."""

import argparse
from dataclasses import dataclass

from installer import schedules


@dataclass(frozen=True)
class Options:
    all: bool
    categories: tuple[str, ...]
    yes: bool
    doctor: bool = False
    fix: bool = False
    uninstall: bool = False
    guard: bool = False
    unguard: bool = False
    link_mode: str | None = None
    run_schedule: str | None = None
    parent_holds_run_lock: bool = False


def parse_args(argv: list[str]) -> Options:
    """Parse argv (excluding program name) into Options; exits on bad input."""
    parser = argparse.ArgumentParser(
        prog="tools-installer",
        description="Interactively install an AI dev environment.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="select every tool without category/tool prompts (add --yes to skip confirmation)",
    )
    parser.add_argument(
        "--categories",
        action="append",
        default=[],
        metavar="A,B",
        help="install only these categories (comma-separated; repeatable)",
    )
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument(
        "--doctor", action="store_true", help="audit the PATH (read-only report), then exit"
    )
    parser.add_argument(
        "--fix", action="store_true", help="wire PATH into your shell rc files, then exit"
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="remove installed userspace artifacts, then exit"
    )
    parser.add_argument(
        "--guard",
        action="store_true",
        help="install the pip/npm ban (shims + aliases steering to uv/pnpm), then exit",
    )
    parser.add_argument("--unguard", action="store_true", help="remove the pip/npm ban, then exit")
    parser.add_argument(
        "--link-mode",
        choices=["centralized", "single", "split"],
        default=None,
        help="how to wire PATH into your shells (default: ask, or centralized)",
    )
    parser.add_argument(
        "--run-schedule",
        choices=list(schedules.UPDATE_SCHEDULE_IDS),
        default=None,
        metavar="ID",
        help="run one scheduled update and print one result line (used by the schedule timers)",
    )
    parser.add_argument(
        "--parent-holds-run-lock",
        action="store_true",
        help="internal: the schedule runner already holds the run lock",
    )
    ns = parser.parse_args(argv)

    categories: list[str] = []
    raw_groups: list[str] = ns.categories
    for group in raw_groups:
        for name in group.split(","):
            trimmed = name.strip()
            if trimmed:
                categories.append(trimmed)
    return Options(
        all=ns.all,
        categories=tuple(categories),
        yes=ns.yes,
        doctor=ns.doctor,
        fix=ns.fix,
        uninstall=ns.uninstall,
        guard=ns.guard,
        unguard=ns.unguard,
        link_mode=ns.link_mode,
        run_schedule=ns.run_schedule,
        parent_holds_run_lock=ns.parent_holds_run_lock,
    )
