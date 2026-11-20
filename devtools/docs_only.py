"""The CI docs-only classifier: decide whether a branch push needs the full jobs.

Standard library only, no ``installer`` import: this runs in CI before dependencies are
installed. It errs toward a full run (P4): an empty change list, a git failure, a missing git or
an unknown path all run the full gates, so a docs-only fast pass can never hide a red check.
"""

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from fnmatch import fnmatchcase

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[bytes]]

# shortcut: only an exact lowercase ".md" counts as Markdown; widen this list if a test starts
# reading another document type (fnmatch's `*` also matches `/`).
TEST_READ: tuple[str, ...] = (
    "AGENTS.md",
    "README.md",
    ".claude/*",
    ".github/*",
    "docs/*",
    "scripts/*",
    "tests/*",
    ".planning/milestones/v0.50.0-phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*",
    ".planning/*27-SKILLJUDGE-*",
)


def is_docs_path(path: str) -> bool:
    return (path.startswith(".planning/") or path.endswith(".md")) and not any(
        fnmatchcase(path, pattern) for pattern in TEST_READ
    )


def is_docs_only(paths: Sequence[str]) -> bool:
    return bool(paths) and all(is_docs_path(path) for path in paths)


def _git_runner(git: str) -> Runner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(list(args), capture_output=True, check=False)

    return run


def changed_paths(
    base: str,
    *,
    run: Runner | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[str] | None:
    git = which("git")
    if git is None:
        return None
    argv = [git, "diff", "--name-only", "-z", "--no-renames", f"{base}...HEAD"]
    done = (run if run is not None else _git_runner(git))(argv)
    if done.returncode != 0:
        return None
    return [os.fsdecode(part) for part in done.stdout.split(b"\0") if part]


def main(
    argv: Sequence[str] | None = None,
    *,
    run: Runner | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> int:
    parser = argparse.ArgumentParser(description="Write full=true|false for a branch push.")
    parser.add_argument("--base", default="origin/main", help="merge base to diff against")
    parser.add_argument("--github-output", help="append the full=... line to this file")
    args = parser.parse_args(argv)

    paths = changed_paths(args.base, run=run, which=which)
    full = paths is None or not is_docs_only(paths)
    if paths is None:
        reason = "no change list (git failed or no merge base)"
    elif not paths:
        reason = "empty change"
    elif is_docs_only(paths):
        reason = f"docs-only: {len(paths)} paths"
    else:
        reason = f"full run: {next(path for path in paths if not is_docs_path(path))}"

    line = f"full={'true' if full else 'false'}"
    print(line)
    print(reason)
    output_path: str | None = args.github_output
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
