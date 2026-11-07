"""The launch guard for every Python child of the test suite, loaded through PYTHONPATH.

`tests/conftest.py` puts this directory on PYTHONPATH and names the base temp in
`tests.sandbox.CHILD_GUARD_ROOT_ENV`, so a `sys.executable -c ...` child faces the allowlist
its test faces (review C-07). A refusal raises AssertionError inside the child; it cannot
reach the parent's refusal registry, so the test sees it as the child's failure.

shortcut: a child started with `-I`/`-E` or with an env that drops PYTHONPATH runs unguarded;
upgrade to a wrapper interpreter if a test ever needs that shape.
"""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# tests.sandbox.CHILD_GUARD_ROOT_ENV; spelled out so a plain child imports nothing of the suite.
_ROOT_ENV = "TOOLS_INSTALLER_TEST_ALLOWED_ROOT"


def _install(root: Path) -> None:
    checkout = str(Path(__file__).resolve().parent.parent.parent)
    sys.path.insert(0, checkout)
    try:
        from tests.sandbox import (  # only a guarded child imports the suite
            GUARDED_OS_FUNCTIONS,
            build_launch_policy,
            check_launch,
            guarded_os_call,
        )
    finally:
        sys.path.remove(checkout)
    policy = build_launch_policy(root, path_value=os.environ.get("PATH", ""))

    class ChildGuardedPopen(subprocess.Popen[Any]):
        def __init__(self, args: Any, *pargs: Any, **kwargs: Any) -> None:
            check_launch(
                args,
                env=kwargs.get("env"),
                cwd=kwargs.get("cwd"),
                policy=policy,
                shell=bool(kwargs.get("shell", False)),
                executable=kwargs.get("executable", pargs[1] if len(pargs) > 1 else None),
            )
            super().__init__(args, *pargs, **kwargs)

    def check(argv: list[str], env: Mapping[str, str] | None) -> None:
        check_launch(argv, env=env, cwd=None, policy=policy)

    subprocess.Popen = ChildGuardedPopen
    for name in GUARDED_OS_FUNCTIONS:
        if hasattr(os, name):
            setattr(os, name, guarded_os_call(name, getattr(os, name), check))


if os.environ.get(_ROOT_ENV):
    _install(Path(os.environ[_ROOT_ENV]))
