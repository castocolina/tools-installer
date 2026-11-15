"""The in-container driver for the bun-lifecycle e2e (24.5-09, PRIO-02, PRIO-03, PRIO-06).

Run as `python -m tests.e2e_bun_driver <verb>` from the workspace: the container harness
(`scripts/container-e2e-verify.sh bun-lifecycle`) has the installer's own code install and
remove tools through bun, so nothing is hand-written. Verbs:

  install-mmdc    a catalog install of mmdc (its `requires` put bun and puppeteer first): prints
                  TRACER_BUN_VIA_HOMEBREW_*, TRACER_BUN_MANIFEST_*, TRACER_BUN_BROWSER_* and
                  TRACER_BUN_LOGIN_SHELL_*
  idempotent-mmdc the bun method again on the installed pair (TRACER_BUN_IDEMPOTENT_*), plus the
                  `INFO bun-partial-add sample=1` observation
  strict-loader   the strict `own-tree` loader on real node (TRACER_BUN_STRICT_LOADER_*)
  pi-owner        a catalog install of pi reads owner bun (TRACER_BUN_PI_OWNER_*)
  kept-peer       removing puppeteer while mmdc stays (TRACER_BUN_KEPT_PEER_*)
  remove-both     removing mmdc and puppeteer together (TRACER_BUN_REMOVE_*), plus the
                  `INFO stranded-peer` observation
  fallback        bun hidden, a provisioned pnpm takes the install (TRACER_BUN_FALLBACK_*)
  floor           a node reporting 20.0.0 (TRACER_BUN_FLOOR_*)
  trust           a user trust list without puppeteer (TRACER_BUN_TRUST_*)

Every verdict is a pure function of facts the verb gathered, so the host tests run them on
fixtures; the verbs install real tools and refuse to run outside the harness's container.
A product failure prints a named `TRACER_BUN_<STEP>_FAILED detail=...` line and exits 1; an error
prints `ERROR <first line>` and exits 1. Exit code 2: a bad verb or argument count, or not in the
container.

It imports only `installer`, `tests.e2e_landing_driver`, `rich` (an installer dependency) and the
standard library: the container runs it with `--no-dev`.
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager, suppress
from io import StringIO
from pathlib import Path
from typing import cast

from rich.console import Console

import installer
from installer import app, engine, executors, receipts
from installer import platform as host_platform
from installer.bun_globals import bun_dirs, read_bun_globals, resolve_bun, trusted_dependencies
from installer.deps import resolve_dependencies
from installer.enums import InstallStatus
from installer.legacy_guard import real_pnpm
from installer.locations import rc_paths_for_mode
from installer.model import Method, Tool, load_tools
from installer.ownership import manager_listing, read_inventory, resolve_ownership
from installer.receipts import Receipt
from installer.resolve import resolve_methods, unavailable_reason
from installer.run import CommandError, run_captured, run_command
from installer.status import is_installed
from tests.e2e_landing_driver import (
    Failed,
    Recorder,
    first_line,
    in_container,
    install_one,
    no_homebrew_platform,
    tool_by_id,
    uninstall_one,
    uninstall_tools,
    verdict,
)

_MMDC_PACKAGE = "@mermaid-js/mermaid-cli"
_PI_PACKAGE = "@earendil-works/pi-coding-agent"
_PUPPETEER_RANGE = "^25"
_BROWSER_DIRS = ("chrome", "chrome-headless-shell")
_LOGIN_SHELL_TIMEOUT = 120
_LOADER_TIMEOUT = 60
_INSTALL_FAILED = "TRACER_BUN_INSTALL_FAILED"
_FLOOR_NODE = "20.0.0"
_DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)
# bun's own default trust list holds puppeteer; a user list that omits it replaces that default.
_USER_TRUST = ["esbuild"]
_FAKE_PUPPETEER = (
    "module.exports = { launch: async () => ({ newPage: async () => ({ goto: async () => {} }),"
    " close: async () => {} }) };\n"
)
_BROKEN_PUPPETEER = "require('tools-installer-e2e-missing-module');\n"

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


def receipt_detail(receipt: Receipt | None, kind: str, package: str) -> str | None:
    """None only for a receipt of this manager kind naming this package (review R2-01): the
    Uninstall path runs a manager argv only for such a receipt, so a step checks it first."""
    if receipt is None:
        return f"precondition: no {kind} receipt for {package}"
    if receipt.method.kind != kind:
        return f"precondition: the receipt for {package} is kind {receipt.method.kind}, not {kind}"
    if receipt.package != package:
        held = receipt.package or "no package"
        return f"precondition: the {kind} receipt names {held}, not {package}"
    return None


def _entries(document: Mapping[str, object]) -> dict[str, list[object]]:
    """Each package's ranges across every dependency section of a manifest."""
    found: dict[str, list[object]] = {}
    for section in _DEPENDENCY_SECTIONS:
        raw = document.get(section)
        if isinstance(raw, dict):
            for name, spec in cast(Mapping[str, object], raw).items():
                found.setdefault(name, []).append(spec)
    return found


def idempotent_verdict(
    before: Mapping[str, object] | None, after: Mapping[str, object] | None
) -> str:
    """Re-running the bun method leaves one manifest entry per package and puppeteer's range."""
    if before is None or after is None:
        return verdict("TRACER_BUN_IDEMPOTENT_FAILED", "bun's global manifest is unreadable")
    now, earlier = _entries(after), _entries(before)
    for name in (_MMDC_PACKAGE, "puppeteer"):
        if name not in now:
            detail = f"{name} is not listed after the second run"
        elif len(now[name]) > 1:
            detail = f"{name} is listed in more than one dependency section"
        else:
            continue
        return verdict("TRACER_BUN_IDEMPOTENT_FAILED", detail)
    was = earlier.get("puppeteer", [None])[0]
    if now["puppeteer"][0] != was or was != _PUPPETEER_RANGE:
        detail = f"puppeteer's range is {now['puppeteer'][0]!r} after, {was!r} before"
        return verdict("TRACER_BUN_IDEMPOTENT_FAILED", detail)
    return "TRACER_BUN_IDEMPOTENT_OK"


def pi_owner_verdict(owner: str, current_version: str | None, installed_version: str | None) -> str:
    """pi reads owner bun with the installed package's own version (PRIO-03)."""
    if owner != "bun":
        detail = f"pi's owner is {owner}, not bun"
    elif current_version is None:
        detail = "no version reported for pi"
    elif installed_version is None:
        detail = "the installed package's version is unreadable"
    elif current_version != installed_version:
        detail = f"pi reports {current_version}, the installed package is {installed_version}"
    else:
        return f"TRACER_BUN_PI_OWNER_OK version={current_version}"
    return verdict("TRACER_BUN_PI_OWNER_FAILED", detail)


def _head(argv: Sequence[str]) -> str:
    return Path(argv[0]).name if argv else ""


def absent_detail(
    on_path: str | None, installed: bool, bun_listed: bool, pnpm_listed: bool
) -> str | None:
    """None only when mmdc is nowhere (review R1-12): a negative step on a present mmdc would
    end at ALREADY_INSTALLED and prove nothing."""
    left = [
        *([f"mmdc resolves to {on_path}"] if on_path else []),
        *(["status.is_installed reports mmdc installed"] if installed else []),
        *([f"bun lists {_MMDC_PACKAGE}"] if bun_listed else []),
        *([f"pnpm lists {_MMDC_PACKAGE}"] if pnpm_listed else []),
    ]
    return f"precondition: mmdc is still there: {'; '.join(left)}" if left else None


def fallback_verdict(
    bun_hidden: bool,
    status: InstallStatus,
    method_kind: str | None,
    argvs: Sequence[Sequence[str]],
    last_error: str | None = None,
) -> str:
    """With bun hidden, the ladder installed mmdc through a real pnpm (D-10; review R1-11): an
    INSTALLED outcome of kind node, a recorded `pnpm add -g` argv and no bun argv. A missing
    pnpm ends FAILED with its message and never passes."""
    adds_with_pnpm = any(
        _head(argv) == "pnpm" and tuple(argv[1:3]) == ("add", "-g") for argv in argvs
    )
    if not bun_hidden:
        detail = "bun was not hidden, so the fallback proves nothing"
    elif status is not InstallStatus.INSTALLED:
        detail = f"the install ended {status}" + (f": {last_error}" if last_error else "")
    elif method_kind != "node":
        detail = f"the install ended at method kind {method_kind}, not node"
    elif not adds_with_pnpm:
        detail = "no pnpm add -g argv was recorded"
    elif any(_head(argv) == "bun" for argv in argvs):
        detail = "a bun argv was recorded"
    else:
        return "TRACER_BUN_FALLBACK_OK"
    return verdict("TRACER_BUN_FALLBACK_FAILED", detail)


def floor_verdict(
    status: InstallStatus,
    errors: Sequence[str],
    argvs: Sequence[Sequence[str]],
    plan_reason: str | None,
) -> str:
    """A node reporting 20.0.0 fails the install with the executor's floor message and no
    `bun add`, and the plan-time reason names the floor (PRIO-02, D-02)."""
    floor = f"needs Node >= 22.12.0; this system has {_FLOOR_NODE}"
    if status is not InstallStatus.FAILED:
        detail = f"the install ended {status}, not FAILED"
    elif not any(
        "does not meet the required minimum 22.12.0" in error and _FLOOR_NODE in error
        for error in errors
    ):
        detail = "no error carries the executor's floor message"
    elif any(_head(argv) == "bun" and "add" in argv[1:] for argv in argvs):
        detail = "a bun add argv was recorded"
    elif plan_reason != floor:
        detail = f"the plan's reason is {plan_reason!r}, not {floor!r}"
    else:
        return "TRACER_BUN_FLOOR_OK"
    return verdict("TRACER_BUN_FLOOR_FAILED", detail)


def kept_peer_verdict(remove_failed: Sequence[tuple[str, str]], receipt_kept: bool) -> str:
    """Removing puppeteer while mmdc stays reports bun's kept line and keeps the receipt."""
    why = next((line for tool_id, line in remove_failed if tool_id == "puppeteer"), None)
    if why is None:
        detail = "the removal of puppeteer reported no kept peer"
    elif not why.startswith("bun kept puppeteer"):
        detail = f"the removal of puppeteer said {why!r}, not a bun kept line"
    elif not receipt_kept:
        detail = "puppeteer's receipt is gone"
    else:
        return "TRACER_BUN_KEPT_PEER_OK"
    return verdict("TRACER_BUN_KEPT_PEER_FAILED", detail)


def remove_verdict(
    removed: Sequence[str], remove_failed: Sequence[tuple[str, str]], in_tree: Sequence[str]
) -> str:
    """Removing mmdc and puppeteer together removes both and leaves neither under node_modules."""
    refused = {tool_id for tool_id, _why in remove_failed}
    left = [
        *(f"{tool_id}: {why}" for tool_id, why in remove_failed),
        *(
            f"{tool_id} not removed"
            for tool_id in ("mmdc", "puppeteer")
            if tool_id not in removed and tool_id not in refused
        ),
        *(f"{name} is still under node_modules" for name in in_tree),
    ]
    if left:
        return verdict("TRACER_BUN_REMOVE_FAILED", "; ".join(left))
    return "TRACER_BUN_REMOVE_OK"


def trust_verdict(
    status: InstallStatus,
    method_kind: str | None,
    last_error: str | None,
    argvs: Sequence[Sequence[str]],
    trusted_after: Sequence[str] | None,
) -> str:
    """A user trust list without puppeteer ends the ladder at the bun method naming the trust
    command, runs no pnpm command and leaves the user's list as it was (PRIO-06)."""
    command = "bun add -g --trust puppeteer@^25"
    if status is not InstallStatus.FAILED:
        detail = f"the install ended {status}, not FAILED"
    elif method_kind != "bun":
        detail = f"the ladder ended at method kind {method_kind}, not bun"
    elif last_error is None or command not in last_error:
        detail = f"the last error does not name `{command}`"
    elif not any(_head(argv) == "bun" and tuple(argv[1:3]) == ("add", "-g") for argv in argvs):
        detail = "no `bun add -g` argv was recorded, so the failure did not come from bun"
    elif any(_head(argv) == "pnpm" for argv in argvs):
        detail = "a pnpm command ran after the bun method"
    elif trusted_after != _USER_TRUST:
        detail = f"trustedDependencies is now {trusted_after!r}, not {_USER_TRUST!r}"
    else:
        return "TRACER_BUN_TRUST_OK"
    return verdict("TRACER_BUN_TRUST_FAILED", detail)


def strict_loader_verdict(
    own_rc: int,
    ancestor_rc: int,
    ancestor_stderr: str,
    unloadable_rc: int,
    plain_ancestor_rc: int,
    *,
    ancestor_path: str,
) -> str:
    """24.5-02's strict `own-tree` loader on real node (R3-01): it loads the root's own puppeteer,
    refuses an ancestor's and names it, refuses to fall through from an unloadable own copy, and
    the manager-less loader still resolves through an ancestor."""
    if own_rc != 0:
        detail = f"puppeteer in the root's own tree did not load (exit {own_rc})"
    elif ancestor_rc == 0:
        detail = "the strict loader accepted an ancestor's puppeteer"
    elif ancestor_path not in ancestor_stderr:
        detail = f"the strict loader's error does not name the ancestor path {ancestor_path}"
    elif unloadable_rc == 0:
        detail = "an unloadable own copy fell through to another tree"
    elif plain_ancestor_rc != 0:
        detail = (
            "the manager-less loader no longer resolves through an ancestor "
            f"(exit {plain_ancestor_rc})"
        )
    else:
        return "TRACER_BUN_STRICT_LOADER_OK"
    return verdict("TRACER_BUN_STRICT_LOADER_FAILED", detail)


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


def _install_closure(
    tool_id: str, catalog: list[Tool], platform: host_platform.Platform, prefix: str
) -> dict[str, engine.InstallOutcome]:
    """Install a catalog tool the way a catalog run does: its `requires` first, deps-first, each
    one that is not installed through the one-tool install path."""
    resolution = resolve_dependencies(
        [tool_by_id(tool_id)],
        catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=is_installed,
    )
    outcomes: dict[str, engine.InstallOutcome] = {}
    for tool in resolution.closure:
        if not is_installed(tool):
            outcomes[tool.id] = install_one(tool, prefix, platform=platform)
    return outcomes


def _bun_method(tool: Tool, platform: host_platform.Platform) -> Method:
    found = next((m for m in resolve_methods(tool, platform) if m.kind == "bun"), None)
    if found is None:
        raise ValueError(f"{tool.id} has no bun method on this platform")
    return found


def _install_mmdc(home: Path) -> list[str]:
    catalog = load_tools(_registry())
    platform = host_platform.detect()
    bun_before = resolve_bun() is not None
    outcomes = _install_closure("mmdc", catalog, platform, _INSTALL_FAILED)
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


def _partial_add_observation() -> str:
    """R1-05 (24.5-02's residual): one sample of one failure mode, an absent second package. It
    never proves bun cannot link a package before exiting non-zero."""
    bun = resolve_bun()
    if bun is None:
        raise Failed(
            "TRACER_BUN_IDEMPOTENT_FAILED", "bun is not resolved for the partial-add sample"
        )
    code = 0
    try:
        run_captured([bun, "add", "-g", "semver@^7", "@tools-installer-e2e/absent-package"])
    except CommandError as error:
        code = error.returncode
    listed = "semver" in (read_bun_globals() or {})
    if listed:
        run_captured([bun, "remove", "--global", "semver"])
    return f"INFO bun-partial-add sample=1 exit={code} manifest_lists_semver={str(listed).lower()}"


def _idempotent_mmdc(_home: Path) -> list[str]:
    before = _bun_manifest()
    executors.execute(_bun_method(tool_by_id("mmdc"), host_platform.detect()), run_command)
    return [idempotent_verdict(before, _bun_manifest()), _partial_add_observation()]


def _write_fake_puppeteer(package: Path, source: str) -> None:
    package.mkdir(parents=True)
    (package / "package.json").write_text(
        '{"name": "puppeteer", "version": "0.0.0", "main": "index.js"}\n', encoding="utf-8"
    )
    (package / "index.js").write_text(source, encoding="utf-8")


def _launch(args: Sequence[str], cwd: Path, node_path: Path | None = None) -> tuple[int, str]:
    """The installer's own launch script under real node, with no NODE_PATH unless one is given."""
    script = cast(str, vars(executors)["_LAUNCH_SCRIPT"])
    env = {key: value for key, value in os.environ.items() if key != "NODE_PATH"}
    if node_path is not None:
        env["NODE_PATH"] = str(node_path)
    done = subprocess.run(
        ["node", "-e", script, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=_LOADER_TIMEOUT,
        check=False,
    )
    return done.returncode, done.stderr


def _strict_loader(home: Path) -> list[str]:
    """24.5-02's real-node cases: `node` is forbidden in the unit-test sandbox, so this step is
    their only real proof."""
    base = Path(tempfile.mkdtemp(prefix="e2e-strict-loader-", dir=home)).resolve()
    try:
        own, tree, broken = base / "own", base / "tree", base / "broken"
        _write_fake_puppeteer(own / "node_modules" / "puppeteer", _FAKE_PUPPETEER)
        _write_fake_puppeteer(base / "node_modules" / "puppeteer", _FAKE_PUPPETEER)
        (tree / "node_modules" / "puppeteer").mkdir(parents=True)
        _write_fake_puppeteer(broken / "node_modules" / "puppeteer", _BROKEN_PUPPETEER)
        _write_fake_puppeteer(base / "nodepath" / "puppeteer", _FAKE_PUPPETEER)
        own_rc, _ = _launch(["own-tree", str(own)], base)
        ancestor_rc, ancestor_stderr = _launch(["own-tree", str(tree)], base)
        unloadable_rc, _ = _launch(["own-tree", str(broken)], base, base / "nodepath")
        plain_rc, _ = _launch([str(tree)], base)
        return [
            strict_loader_verdict(
                own_rc,
                ancestor_rc,
                ancestor_stderr,
                unloadable_rc,
                plain_rc,
                ancestor_path=str(base / "node_modules" / "puppeteer"),
            )
        ]
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _pi_owner(home: Path) -> list[str]:
    catalog = load_tools(_registry())
    platform = host_platform.detect()
    pi = tool_by_id("pi")
    _install_closure("pi", catalog, platform, "TRACER_BUN_PI_OWNER_FAILED")
    receipt = receipts.read("pi")
    ownership = resolve_ownership(
        pi,
        platform=platform,
        inventory=read_inventory(has_brew=platform.has_brew),
        artifacts=[artifact.path for artifact in receipt.artifacts] if receipt else [],
        managed_bin_dir=home / ".local" / "bin",
    )
    installed = (read_bun_globals() or {}).get(_PI_PACKAGE)
    return [
        pi_owner_verdict(
            ownership.owner, ownership.current_version, installed.version if installed else None
        )
    ]


def _bun_receipts_detail() -> str | None:
    """The kept-peer and remove-both precondition: both packages' bun receipts exist."""
    peer = receipt_detail(receipts.read("puppeteer"), "bun", "puppeteer")
    return peer or receipt_detail(receipts.read("mmdc"), "bun", _MMDC_PACKAGE)


def _in_bun_tree(package: str) -> bool:
    return (bun_dirs()[1] / "node_modules" / package).exists()


def _kept_peer(_home: Path) -> list[str]:
    puppeteer = tool_by_id("puppeteer")
    detail = _bun_receipts_detail()
    if detail is not None:
        return [verdict("TRACER_BUN_KEPT_PEER_FAILED", detail)]
    result = uninstall_one(puppeteer, Recorder(run_captured))
    lines = [kept_peer_verdict(result.remove_failed, receipts.read("puppeteer") is not None)]
    # A kept peer has no manifest entry: put it back so the next step starts from the declared pair.
    executors.execute(_bun_method(puppeteer, host_platform.detect()), run_command)
    return lines


def _remove_both(_home: Path) -> list[str]:
    detail = _bun_receipts_detail()
    if detail is not None:
        return [verdict("TRACER_BUN_REMOVE_FAILED", detail)]
    recorder = Recorder(run_captured)
    peer_after_mmdc: list[bool] = []

    def runner(cmd: list[str]) -> None:
        recorder(cmd)
        if "remove" in cmd and cmd[-1] == _MMDC_PACKAGE:
            peer_after_mmdc.append(_in_bun_tree("puppeteer"))

    result = uninstall_tools((tool_by_id("mmdc"), tool_by_id("puppeteer")), runner)
    in_tree = [name for name in (_MMDC_PACKAGE, "puppeteer") if _in_bun_tree(name)]
    peer = str(peer_after_mmdc[0]).lower() if peer_after_mmdc else "unknown"
    return [
        remove_verdict(result.removed, result.remove_failed, in_tree),
        f"INFO stranded-peer puppeteer_in_bun_tree_after_mmdc_removal={peer}",
    ]


@contextmanager
def _restored_env(*names: str) -> Generator[None, None, None]:
    saved = {name: os.environ.get(name) for name in names}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _absent_now(tool: Tool) -> str | None:
    """`absent_detail` over the live machine: PATH, `is_installed` and both listings."""
    return absent_detail(
        shutil.which(tool.cmd),
        is_installed(tool),
        _MMDC_PACKAGE in (read_bun_globals() or {}),
        _MMDC_PACKAGE in (manager_listing("node") or ()),
    )


def _fallback(home: Path) -> list[str]:
    """D-10's container half: bun hidden, a pnpm the step provisioned through its script route
    (a missing pnpm can never pass), mmdc installed through it, then removed again."""
    prefix = "TRACER_BUN_FALLBACK_FAILED"
    mmdc = tool_by_id("mmdc")
    detail = _absent_now(mmdc)
    if detail is not None:
        return [verdict(prefix, detail)]
    with (
        _restored_env("PATH", "BUN_INSTALL_BIN", "PNPM_HOME"),
        tempfile.TemporaryDirectory(prefix="e2e-no-bun-", dir=home) as empty,
    ):
        if real_pnpm() is None:
            # Brew-first would pick Homebrew's pnpm, whose global bin dir is unverified: take the
            # catalog's script route, the one a host without Homebrew takes.
            install_one(tool_by_id("pnpm"), prefix, platform=no_homebrew_platform())
        pnpm = real_pnpm()
        if pnpm is None:
            raise Failed(prefix, "pnpm did not resolve after its script install")
        pnpm_bin = Path(pnpm).parent
        os.environ["PATH"] = os.pathsep.join([str(pnpm_bin), "/usr/local/bin", "/usr/bin", "/bin"])
        os.environ["BUN_INSTALL_BIN"] = empty
        # What a fresh login shell exports after the script's `pnpm setup`: this process started
        # before pnpm existed.
        os.environ["PNPM_HOME"] = str(pnpm_bin.parent)
        bun_hidden = resolve_bun() is None
        recorder = Recorder(run_command)
        outcome = engine.install_tool(
            mmdc, host_platform.detect(), runner=recorder, read_inventory_fn=read_inventory
        )
        last = str(outcome.errors[-1]) if outcome.errors else None
        lines = [
            fallback_verdict(
                bun_hidden, outcome.status, outcome.method_kind, recorder.argvs(), last
            )
        ]
        held = receipt_detail(receipts.read("mmdc"), "node", _MMDC_PACKAGE)
        if held is not None:
            return [*lines, verdict(prefix, f"cleanup: {held}")]
        uninstall_one(mmdc, Recorder(run_captured))
    leftover = _absent_now(mmdc)
    if leftover is not None:
        lines.append(verdict(prefix, f"cleanup: {leftover}"))
    return lines


def _floor(home: Path) -> list[str]:
    prefix = "TRACER_BUN_FLOOR_FAILED"
    mmdc = tool_by_id("mmdc")
    platform = host_platform.detect()
    detail = _absent_now(mmdc)
    if detail is not None:
        return [verdict(prefix, detail)]
    with (
        _restored_env("PATH"),
        tempfile.TemporaryDirectory(prefix="e2e-fake-node-", dir=home) as fake,
    ):
        node = Path(fake) / "node"
        node.write_text(f"#!/bin/sh\necho v{_FLOOR_NODE}\n", encoding="utf-8")
        node.chmod(0o755)
        os.environ["PATH"] = os.pathsep.join([fake, os.environ.get("PATH", "")])
        recorder = Recorder(run_command)
        # The plan knows no node version here (detect() leaves it None), so the executor's own
        # floor check is what fails.
        outcome = engine.install_tool(
            mmdc, platform, runner=recorder, read_inventory_fn=read_inventory
        )
    reason = unavailable_reason(mmdc, dataclasses.replace(platform, node_version=_FLOOR_NODE))
    return [
        floor_verdict(
            outcome.status,
            [str(error) for error in outcome.errors],
            recorder.argvs(),
            reason.short if reason else None,
        )
    ]


def _set_trusted(value: list[str] | None) -> None:
    """Write or drop `trustedDependencies` in bun's global manifest the way a user would."""
    path = bun_dirs()[1] / "package.json"
    document = dict(_bun_manifest() or {})
    if value is None:
        document.pop("trustedDependencies", None)
    else:
        document["trustedDependencies"] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _trust(home: Path) -> list[str]:
    prefix = "TRACER_BUN_TRUST_FAILED"
    mmdc = tool_by_id("mmdc")
    detail = _absent_now(mmdc)
    listed = [name for name in (_MMDC_PACKAGE, "puppeteer") if name in (read_bun_globals() or {})]
    if detail is None and listed:
        detail = f"precondition: bun's manifest still lists {', '.join(listed)}"
    if detail is not None:
        return [verdict(prefix, detail)]
    shutil.rmtree(home / ".cache" / "puppeteer", ignore_errors=True)
    _set_trusted(_USER_TRUST)
    recorder = Recorder(run_command)
    try:
        outcome = engine.install_tool(
            mmdc, host_platform.detect(), runner=recorder, read_inventory_fn=read_inventory
        )
        last = str(outcome.errors[-1]) if outcome.errors else None
        return [
            trust_verdict(
                outcome.status, outcome.method_kind, last, recorder.argvs(), trusted_dependencies()
            )
        ]
    finally:
        # A smoke failure after `bun add` ends at MethodLeftInstalled, which writes no receipt, so
        # the Uninstall path has nothing to remove: take the packages out of bun's tree directly.
        # A failed removal must not replace the verdict above: the container is disposable.
        bun = resolve_bun()
        if bun is not None:
            with suppress(CommandError):
                run_captured([bun, "remove", "--global", _MMDC_PACKAGE, "puppeteer"])
        _set_trusted(None)


_HANDLERS: dict[str, _Handler] = {
    "install-mmdc": _install_mmdc,
    "idempotent-mmdc": _idempotent_mmdc,
    "strict-loader": _strict_loader,
    "pi-owner": _pi_owner,
    "kept-peer": _kept_peer,
    "remove-both": _remove_both,
    "fallback": _fallback,
    "floor": _floor,
    "trust": _trust,
}


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
    except (OSError, CommandError, ValueError, executors.ExecutorError) as error:
        print(f"ERROR {first_line(error) or type(error).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
