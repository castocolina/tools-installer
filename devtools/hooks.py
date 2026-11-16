"""The `make dev-setup` hook step: the commit hook through pre-commit, the push gate as a shim.

Both hooks land in the shared hooks directory (`git rev-parse --git-common-dir`), so every
worktree of a clone runs them. Run `python -m devtools.hooks install` from the main checkout.
"""

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

MARKER = "# tools-installer: pre-push gate (installed by make dev-setup; do not edit)"
_NO_UV = "pre-push: uv not found on PATH; install uv (see README) or push from a shell that has it"
SHIM = f"""#!/bin/sh
{MARKER}
if ! command -v uv >/dev/null 2>&1; then
    echo "{_NO_UV}" >&2
    exit 1
fi
exec uv run python -m devtools.push_gate "$@"
"""

Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


def _run(argv: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    # LC_ALL=C keeps git's messages untranslated, so one text check works in every locale.
    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )


def install(
    *,
    run: Runner | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> int:
    run = run or _run
    git = which("git")
    pre_commit = which("pre-commit")
    if git is None or pre_commit is None:
        print("dev-setup: git and pre-commit must be on PATH; run `uv sync` first", file=sys.stderr)
        return 1
    common_dir = run([git, "rev-parse", "--path-format=absolute", "--git-common-dir"])
    hooks_dir = Path(common_dir.stdout.strip()) / "hooks"
    if run([git, "config", "--get", "core.hooksPath"]).returncode == 0:
        print(
            "dev-setup: core.hooksPath is set; "
            "unset it with `git config --unset-all core.hooksPath`",
            file=sys.stderr,
        )
        return 1
    result = run([pre_commit, "install", "--hook-type", "pre-commit"])
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode
    hooks_dir.mkdir(parents=True, exist_ok=True)
    shim = hooks_dir / "pre-push"
    shim.write_text(SHIM)
    shim.chmod(0o744)
    print(f"dev-setup: commit hook and push gate installed in {hooks_dir}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m devtools.hooks")
    parser.add_argument("verb", choices=["install"])
    parser.parse_args(argv)
    return install()


if __name__ == "__main__":
    sys.exit(main())
