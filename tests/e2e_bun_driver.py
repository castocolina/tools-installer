"""The in-container driver for the bun-lifecycle e2e (24.5-09, PRIO-02, PRIO-03, PRIO-06).

Run as `python -m tests.e2e_bun_driver <verb>` from the workspace: the container harness
(`scripts/container-e2e-verify.sh bun-lifecycle`) has the installer's own code install and
remove tools through bun, so nothing is hand-written. Verbs:

  install-mmdc    a catalog install of mmdc (its `requires` put bun and puppeteer first): prints
                  TRACER_BUN_VIA_HOMEBREW_*, TRACER_BUN_MANIFEST_*, TRACER_BUN_BROWSER_* and
                  TRACER_BUN_LOGIN_SHELL_*

Every verdict is a pure function of facts the verb gathered, so the host tests run them on
fixtures; the verbs install real tools and refuse to run outside the harness's container.
A product failure prints a named `TRACER_BUN_<STEP>_FAILED detail=...` line and exits 1; an error
prints `ERROR <first line>` and exits 1. Exit code 2: a bad verb or argument count, or not in the
container.

It imports only `installer`, `tests.e2e_landing_driver`, `rich` (an installer dependency) and the
standard library: the container runs it with `--no-dev`.
"""

import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import cast

from rich.console import Console

import installer
from installer import app, engine, executors
from installer import platform as host_platform
from installer.bun_globals import bun_dirs, resolve_bun
from installer.deps import resolve_dependencies
from installer.locations import rc_paths_for_mode
from installer.model import load_tools
from installer.resolve import resolve_methods
from installer.run import CommandError
from installer.status import is_installed
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    verdict,
)

_MMDC_PACKAGE = "@mermaid-js/mermaid-cli"
_PUPPETEER_RANGE = "^25"
_BROWSER_DIRS = ("chrome", "chrome-headless-shell")
_LOGIN_SHELL_TIMEOUT = 120
_INSTALL_FAILED = "TRACER_BUN_INSTALL_FAILED"

# --- pure verdicts --------------------------------------------------------------------------


def brew_bun_verdict(
    bun_present_before: bool,
    method_kind: str | None,
    bun_path: str | None,
    brew_prefix: str | None,
) -> str:
    """bun came from Homebrew's `brew` method (review R1-27): the registry also has a bun script
    stanza, so only this proves the Homebrew-installed-bun case of SPEC's R2 adjacency edge."""
    if bun_present_before:
        detail = "bun was already installed before the install"
    elif method_kind is None:
        detail = "no install outcome for bun"
    elif method_kind != "brew":
        detail = f"bun was installed by its {method_kind} method, not brew"
    elif bun_path is None:
        detail = "bun is not resolved after the install"
    elif brew_prefix is None:
        detail = "the Homebrew prefix is unknown"
    elif not Path(bun_path).is_relative_to(brew_prefix):
        detail = f"bun resolves to {bun_path}, outside the Homebrew prefix {brew_prefix}"
    else:
        return "TRACER_BUN_VIA_HOMEBREW_OK"
    return verdict("TRACER_BUN_VIA_HOMEBREW_FAILED", detail)


def manifest_verdict(document: Mapping[str, object] | None) -> str:
    """bun's global manifest names mmdc and puppeteer `^25` and never gained a trust list."""
    if document is None:
        detail = "bun's global manifest is missing or unreadable"
    else:
        raw = document.get("dependencies")
        dependencies = cast(Mapping[str, object], raw) if isinstance(raw, dict) else None
        if dependencies is None:
            detail = "the manifest's dependencies is not an object"
        elif _MMDC_PACKAGE not in dependencies:
            detail = f"{_MMDC_PACKAGE} is not listed"
        elif "puppeteer" not in dependencies:
            detail = "puppeteer is not listed"
        elif dependencies["puppeteer"] != _PUPPETEER_RANGE:
            detail = f"puppeteer's range is {dependencies['puppeteer']!r}, not {_PUPPETEER_RANGE}"
        elif "trustedDependencies" in document:
            detail = "the manifest gained a trustedDependencies key"
        else:
            return "TRACER_BUN_MANIFEST_OK"
    return verdict("TRACER_BUN_MANIFEST_FAILED", detail)


def browser_verdict(cache_has_browser: bool, smoke_reason: str | None) -> str:
    """A browser sits in puppeteer's cache and puppeteer starts it through bun's tree."""
    if not cache_has_browser:
        detail = "no browser in puppeteer's cache"
    elif smoke_reason is not None:
        detail = f"smoke: {smoke_reason}"
    else:
        return "TRACER_BUN_BROWSER_OK"
    return verdict("TRACER_BUN_BROWSER_FAILED", detail)


def login_shell_verdict(exit_code: int | None) -> str:
    """`mmdc --version` ran from a fresh interactive login shell that inherited nothing."""
    if exit_code == 0:
        return "TRACER_BUN_LOGIN_SHELL_OK"
    shown = "no exit code" if exit_code is None else f"exit {exit_code}"
    return verdict("TRACER_BUN_LOGIN_SHELL_FAILED", f"mmdc --version in a login shell: {shown}")


# --- facts the verbs gather -----------------------------------------------------------------


def _registry() -> Path:
    return Path(installer.__file__).with_name("registry.toml")


def _brew_prefix() -> str | None:
    try:
        done = subprocess.run(
            ["brew", "--prefix"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def _bun_manifest() -> Mapping[str, object] | None:
    try:
        document: object = json.loads((bun_dirs()[1] / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cast(dict[str, object], document) if isinstance(document, dict) else None


def _cache_has_browser(home: Path) -> bool:
    cache = home / ".cache" / "puppeteer"
    return any((cache / name).is_dir() and any((cache / name).iterdir()) for name in _BROWSER_DIRS)


def _login_shell_exit(home: Path, command: str) -> int | None:
    """The exit code of `command` in an interactive login shell that inherits no PATH: whatever
    it finds, the installer's rc wiring put there. None when the shell could not run."""
    env = {
        "HOME": str(home),
        "USER": home.name,
        "LOGNAME": home.name,
        "SHELL": "/bin/bash",
        "TERM": "dumb",
    }
    try:
        return subprocess.run(
            ["bash", "-lic", command],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=_LOGIN_SHELL_TIMEOUT,
            check=False,
        ).returncode
    except (OSError, subprocess.SubprocessError):
        return None


# --- verbs ----------------------------------------------------------------------------------

_Handler = Callable[[Path], list[str]]


def _install_mmdc(home: Path) -> list[str]:
    catalog = load_tools(_registry())
    platform = host_platform.detect()
    bun_before = resolve_bun() is not None
    resolution = resolve_dependencies(
        [tool_by_id("mmdc")],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=is_installed,
    )
    outcomes: dict[str, engine.InstallOutcome] = {}
    for tool in resolution.closure:
        if not is_installed(tool):
            outcomes[tool.id] = install_one(tool, _INSTALL_FAILED, platform=platform)
    bun_outcome = outcomes.get("bun")
    lines = [
        brew_bun_verdict(
            bun_before,
            bun_outcome.method_kind if bun_outcome is not None else None,
            resolve_bun(),
            _brew_prefix(),
        )
    ]
    app.configure_path(
        catalog,
        Console(file=StringIO()),
        platform=platform,
        default_bin_dir=home / ".local" / "bin",
        myshellrc_path=home / ".myshellrc",
        rc_paths=rc_paths_for_mode("centralized", "bash"),
    )
    lines.append(manifest_verdict(_bun_manifest()))
    lines.append(
        browser_verdict(
            _cache_has_browser(home), executors.run_smoke_check("puppeteer-browser", "bun")
        )
    )
    lines.append(login_shell_verdict(_login_shell_exit(home, "mmdc --version")))
    return lines


_HANDLERS: dict[str, _Handler] = {"install-mmdc": _install_mmdc}


def accepts(args: Sequence[str]) -> bool:
    """Whether the driver accepts this command line (the harness script's steps are checked)."""
    return len(args) == 1 and args[0] in _HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print(f"usage: e2e_bun_driver {' | '.join(_HANDLERS)}", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the bun driver runs only inside the disposable container")
        return 2
    try:
        lines = _HANDLERS[args[0]](Path.home())
    except Failed as failed:
        print(verdict(failed.prefix, first_line(failed.detail)))
        return 1
    except (OSError, CommandError, ValueError) as error:
        print(f"ERROR {first_line(error) or type(error).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
