"""Parse non-interactive CLI flags into an Options value."""

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class Options:
    all: bool
    categories: tuple[str, ...]
    yes: bool
    doctor: bool = False
    uninstall: bool = False


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
    parser.add_argument("--doctor", action="store_true", help="audit and fix the PATH, then exit")
    parser.add_argument(
        "--uninstall", action="store_true", help="remove installed userspace artifacts, then exit"
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
        uninstall=ns.uninstall,
    )
