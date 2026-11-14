"""The in-container driver for the audit-landing e2e (24.3-09, SPEC R5, R6, R8, R9).

Run as `python -m tests.e2e_landing_driver <verb>` from the workspace: the container harness
(`scripts/container-e2e-verify.sh audit-landing`) has the installer's own code install, tune,
update and remove tools, so nothing is hand-written. Verbs:

  install opencode                  install the shipped OpenCode 2 entry; prints the install and
                                    tuning verdicts (TRACER_OPENCODE_V2_INSTALL_*, _TUNING_*)
  latest opencode                   the latest version the status pass resolves
                                    (TRACER_OPENCODE_LATEST_*)
  update opencode [--with-service]  the installer-owned update; with the flag, while the background
                                    service runs (TRACER_OPENCODE_UPDATE_WHILE_RUNNING_*); without
                                    it, over a v1 install (TRACER_OPENCODE_V1_UPDATE_*)
  remove opencode [--with-service]  removal through `app.perform_uninstall`; with the flag, a serve
                                    process must run before it (TRACER_OPENCODE_V2_REMOVE_*,
                                    _SERVICE_STOP_UNPROVEN); without it, the recipe's exit code
                                    when nothing runs (TRACER_OPENCODE_V2_STOP_IDLE_*)
  seed-v1 opencode                  install OpenCode 1 the way a pre-24.3 installer did
  remove-v1 opencode                remove that install (TRACER_OPENCODE_V1_REMOVE_*)
  codegraph copilot-and-pi          install codegraph with a copilot footprint and ~/.pi present
                                    (TRACER_CODEGRAPH_COPILOT_*, _PI_GATED_*)
  codegraph unregister              remove codegraph (TRACER_CODEGRAPH_UNREGISTER_*)
  codegraph ide-only                install it again with only ~/.copilot/ide
                                    (TRACER_CODEGRAPH_COPILOT_IDE_ONLY_*)

Every verdict is a pure function of facts the verb gathered, so the host tests run them on
fixtures; the verbs themselves start vendor installers and refuse to run outside a container.
A product failure prints a named `TRACER_<STEP>_FAILED detail=...` line and exits 1; an error
prints `ERROR <first line>` and exits 1. Exit code 2: a bad verb or argument count, or not in a
container.

It imports only `installer` and the standard library: the container runs it with `--no-dev`.
"""

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import installer
from installer import (
    agent_settings,
    app,
    engine,
    postinstall,
    receipts,
    uninstall,
    version_status,
    versions,
)
from installer import platform as host_platform
from installer.enums import InstallStatus
from installer.manager_versions import OutdatedReport
from installer.model import Method, Tool, load_tools
from installer.ownership import ManagerOwnership
from installer.resolve import resolve_methods
from installer.run import CommandError, Runner, run_captured, run_command
from installer.sanitize import sanitize_log_line
from installer.update import UpdateTarget, perform_update

_RC_FILES = (".bashrc", ".bash_profile", ".profile", ".zshrc")
_ALLOW_ALL: list[object] = [{"action": "*", "resource": "*", "effect": "allow"}]
_SEMVER = re.compile(r"\d+\.\d+\.\d+")
_PI = re.compile(r"\bpi\b", re.IGNORECASE)
_LEAVES = ("opencode", "opencode2")
# What a running service's command line looks like: `<opencode binary> serve ...`.
_SERVE_NAMES = frozenset(_LEAVES)
_V1_URL = "https://opencode.ai/install"
_INSTALL_FAILED = "TRACER_OPENCODE_V2_INSTALL_FAILED"
_V1_SEED_FAILED = "TRACER_OPENCODE_V1_SEED_FAILED"
_V1_UPDATE_FAILED = "TRACER_OPENCODE_V1_UPDATE_FAILED"
_RUNNING_FAILED = "TRACER_OPENCODE_UPDATE_WHILE_RUNNING_FAILED"
_REMOVE_FAILED = "TRACER_OPENCODE_V2_REMOVE_FAILED"
_SERVICE_TIMEOUT = 60
_POLL_ATTEMPTS = 20
_POLL_STEP = 0.5


class _Failed(Exception):
    """A product failure: the named FAILED line's prefix and its one-line detail."""

    def __init__(self, prefix: str, detail: str) -> None:
        super().__init__(detail)
        self.prefix = prefix
        self.detail = detail


def _semver(text: str | None) -> str | None:
    found = _SEMVER.search(text or "")
    return found.group(0) if found else None


def _rc_changes(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    return sorted(name for name in {*before, *after} if before.get(name) != after.get(name))


def _verdict(prefix: str, detail: str) -> str:
    return f"{prefix} detail={detail}"


def _lacks(receipt_paths: Sequence[str]) -> list[str]:
    names = {Path(path).name for path in receipt_paths}
    return [leaf for leaf in _LEAVES if leaf not in names]


# --- pure verdicts --------------------------------------------------------------------------


def install_verdict(
    version_output: str | None,
    receipt_paths: Sequence[str],
    rc_before: Mapping[str, str],
    rc_after: Mapping[str, str],
) -> str:
    """OpenCode 2 installed: a 2.x version, both leaves in the receipt, no shell rc touched."""
    version = _semver(version_output)
    missing = _lacks(receipt_paths)
    changed = _rc_changes(rc_before, rc_after)
    if version is None:
        detail = "version unreadable"
    elif not version.startswith("2."):
        detail = f"version {version} is not OpenCode 2"
    elif missing:
        detail = f"receipt lacks {', '.join(missing)}"
    elif changed:
        detail = f"shell rc changed: {', '.join(changed)}"
    else:
        return f"TRACER_OPENCODE_V2_INSTALL_OK version={version}"
    return _verdict(_INSTALL_FAILED, detail)


def tuning_verdict(document: Mapping[str, object]) -> str:
    """The `permissions` allow-all rule and no deprecated `permission`; names keys, never values."""
    if "permission" in document:
        detail = "permission key present (the deprecated one)"
    elif "permissions" not in document:
        detail = "permissions key missing"
    elif document["permissions"] != _ALLOW_ALL:
        detail = "permissions differs from the allow-all rule"
    else:
        return "TRACER_OPENCODE_V2_TUNING_OK"
    return _verdict("TRACER_OPENCODE_V2_TUNING_FAILED", detail)


def latest_verdict(latest: str | None, source: str | None) -> str:
    """The latest version is OpenCode 2's and came from npm, never from GitHub."""
    version = _semver(latest)
    if version is None:
        detail = "no latest version resolved"
    elif not version.startswith("2."):
        detail = f"latest {version} is not OpenCode 2"
    elif source != "npm":
        detail = f"source {source} is not npm"
    else:
        return f"TRACER_OPENCODE_LATEST_OK latest={version} source=npm"
    return _verdict("TRACER_OPENCODE_LATEST_FAILED", detail)


def _leftovers(
    serve_after: bool, files_left: Sequence[str], receipt_left: bool, permissions_left: bool
) -> list[str]:
    return [
        *(["serve process still running"] if serve_after else []),
        *(f"{name} still present" for name in files_left),
        *(["receipt still present"] if receipt_left else []),
        *(["permissions key still present"] if permissions_left else []),
    ]


def remove_verdict(
    serve_before: bool,
    serve_after: bool,
    files_left: Sequence[str],
    receipt_left: bool,
    permissions_left: bool,
) -> str:
    """Removal with a service running: it stopped, both files, the receipt and the tuning went.

    No serve process before the removal proves nothing about the stop (review R1-06), so that is
    never a pass."""
    left = _leftovers(serve_after, files_left, receipt_left, permissions_left)
    if left:
        return _verdict(_REMOVE_FAILED, "; ".join(left))
    if not serve_before:
        return (
            "TRACER_OPENCODE_V2_SERVICE_STOP_UNPROVEN "
            "reason=no serve process ran before the removal"
        )
    return "TRACER_OPENCODE_V2_REMOVE_OK"


def update_while_running_verdict(
    serve_before: bool,
    version_after: str | None,
    restarted_exe: str | None,
    restarted_version: str | None,
) -> str:
    """An update under a running service leaves a working binary, and a restart runs the new one
    (review R1-10, R2-13)."""
    if not serve_before:
        return (
            "TRACER_OPENCODE_UPDATE_WHILE_RUNNING_UNPROVEN "
            "reason=no serve process ran before the update"
        )
    after, restarted = _semver(version_after), _semver(restarted_version)
    if after is None:
        detail = "--version failed after the update"
    elif restarted_exe is None:
        detail = "no serve process after the restart"
    elif restarted_exe.endswith("(deleted)"):
        detail = "the restarted service still runs the deleted binary"
    elif restarted is None:
        detail = "the restarted service reports nothing"
    elif restarted != after:
        detail = f"the restarted service reports {restarted}, the update left {after}"
    else:
        return "TRACER_OPENCODE_UPDATE_WHILE_RUNNING_OK"
    return _verdict(_RUNNING_FAILED, detail)


def stop_idle_verdict(exit_code: int | None) -> str:
    """The `service stop` recipe exits 0 with no service to stop (D-08's open question)."""
    if exit_code == 0:
        return "TRACER_OPENCODE_V2_STOP_IDLE_OK"
    return f"TRACER_OPENCODE_V2_STOP_IDLE_FAILED exit={'none' if exit_code is None else exit_code}"


def v1_remove_verdict(
    removed: bool, binary_left: bool, receipt_left: bool, argvs: Sequence[Sequence[str]]
) -> str:
    """A pre-24.3 install removes cleanly: the recipe is skipped, the binary and receipt go."""
    if not removed:
        detail = "removal failed"
    elif binary_left:
        detail = "opencode still present"
    elif receipt_left:
        detail = "receipt still present"
    elif any("service" in argv for argv in argvs):
        detail = "removal ran a service command, which OpenCode 1 does not have"
    else:
        return "TRACER_OPENCODE_V1_REMOVE_OK"
    return _verdict("TRACER_OPENCODE_V1_REMOVE_FAILED", detail)


def v1_update_verdict(
    before: str | None,
    after: str | None,
    receipt_paths: Sequence[str],
    rc_before: Mapping[str, str],
    rc_after: Mapping[str, str],
) -> str:
    """The installer moves a v1 install to v2: both leaves in the new receipt, no rc change."""
    old, new = _semver(before), _semver(after)
    missing = _lacks(receipt_paths)
    changed = _rc_changes(rc_before, rc_after)
    if old is None or not old.startswith("1."):
        detail = f"the seeded install is not OpenCode 1 ({old})"
    elif new is None or not new.startswith("2."):
        detail = f"still on {new}"
    elif missing:
        detail = f"receipt lacks {', '.join(missing)}"
    elif changed:
        detail = f"shell rc changed: {', '.join(changed)}"
    else:
        return f"TRACER_OPENCODE_V1_UPDATE_OK from={old} to={new}"
    return _verdict(_V1_UPDATE_FAILED, detail)


def _registers_codegraph(config: Mapping[str, object] | None) -> bool:
    """Whether any server table of a copilot `mcp-config.json` names codegraph."""
    tables = [config] if config is not None else []
    tables += [value for value in (config or {}).values() if isinstance(value, dict)]
    return any("codegraph" in table for table in tables)


def copilot_verdict(config: Mapping[str, object] | None) -> str:
    """After an install with a copilot footprint, copilot's MCP config holds codegraph."""
    if config is None:
        detail = "mcp-config.json is absent"
    elif not _registers_codegraph(config):
        detail = "codegraph is not registered"
    else:
        return "TRACER_CODEGRAPH_COPILOT_OK"
    return _verdict("TRACER_CODEGRAPH_COPILOT_FAILED", detail)


def pi_gate_verdict(pi_entries: Sequence[str], warning: str | None, marks: Sequence[str]) -> str:
    """The released codegraph has no Pi target: nothing under ~/.pi/agent, the hook warning says
    why, and no pending mark (`≈`) names Pi."""
    if pi_entries:
        detail = f"~/.pi/agent holds {len(pi_entries)} entries"
    elif warning is None or _PI.search(warning) is None:
        detail = "the hook warning does not name Pi"
    elif any(_PI.search(mark) for mark in marks):
        detail = "a pending mark names Pi"
    else:
        return "TRACER_CODEGRAPH_PI_GATED_OK"
    return _verdict("TRACER_CODEGRAPH_PI_GATED_FAILED", detail)


def unregister_verdict(config: Mapping[str, object] | None) -> str:
    """After removal, copilot's MCP config no longer holds codegraph."""
    if _registers_codegraph(config):
        return _verdict("TRACER_CODEGRAPH_UNREGISTER_FAILED", "codegraph is still registered")
    return "TRACER_CODEGRAPH_UNREGISTER_OK"


def ide_only_verdict(config_exists: bool, argvs: Sequence[Sequence[str]]) -> str:
    """A `~/.copilot` holding only `ide/` is the VS Code extension's: no copilot-cli target."""
    if config_exists:
        detail = "mcp-config.json was written"
    elif any("copilot-cli" in token for argv in argvs for token in argv):
        detail = "copilot-cli appears in a command"
    else:
        return "TRACER_CODEGRAPH_COPILOT_IDE_ONLY_OK"
    return _verdict("TRACER_CODEGRAPH_COPILOT_IDE_ONLY_FAILED", detail)


def find_serve_pids(cmdlines: Mapping[int, Sequence[str]]) -> list[int]:
    """The processes running `<opencode binary> serve`, from their command lines."""
    return sorted(
        pid
        for pid, argv in cmdlines.items()
        if argv and Path(argv[0]).name in _SERVE_NAMES and "serve" in argv[1:]
    )


# --- the settings file the writer chose -----------------------------------------------------


def opencode_settings_path(home: Path, platform_os: str, environ: Mapping[str, str]) -> Path:
    """The file `agent_settings` writes opencode's tuning to (review R1-07), never a guess."""
    return agent_settings.settings_file(
        "opencode", home=home, platform_os=platform_os, environ=environ
    )


def opencode_document(
    home: Path, platform_os: str, environ: Mapping[str, str]
) -> dict[str, object]:
    """That file parsed with the installer's own reader; an absent file is an empty document."""
    snapshot = agent_settings.read_settings(opencode_settings_path(home, platform_os, environ))
    if snapshot is None:
        return {}
    text = snapshot.data.decode("utf-8")
    return agent_settings.parse_settings(text, agent_settings.AGENT_FORMATS["opencode"])


# --- facts the verbs gather -----------------------------------------------------------------


def _digests(home: Path) -> dict[str, str]:
    """sha256 of each shell rc file; an absent file counts as a value of its own."""
    return {
        name: hashlib.sha256((home / name).read_bytes()).hexdigest()
        if (home / name).is_file()
        else "absent"
        for name in _RC_FILES
    }


def _tool(tool_id: str) -> Tool:
    catalog = load_tools(Path(installer.__file__).with_name("registry.toml"))
    found = next((tool for tool in catalog if tool.id == tool_id), None)
    if found is None:
        raise ValueError(f"{tool_id} is not in the catalog")
    return found


def _first_line(text: object) -> str:
    return (sanitize_log_line(str(text)).splitlines() or [""])[0]


@dataclass
class _Recorder:
    """A runner that records each command and its exit code, then behaves like `inner`."""

    inner: Runner
    calls: list[tuple[tuple[str, ...], int]] = field(
        default_factory=list[tuple[tuple[str, ...], int]]
    )

    def __call__(self, cmd: list[str]) -> None:
        try:
            self.inner(cmd)
        except CommandError as error:
            self.calls.append((tuple(cmd), error.returncode))
            raise
        self.calls.append((tuple(cmd), 0))

    def argvs(self) -> list[tuple[str, ...]]:
        return [argv for argv, _code in self.calls]


def _install(tool: Tool, prefix: str, runner: Runner = run_command) -> engine.InstallOutcome:
    """The one-tool install path `make setup` runs for a selected row, hooks and tuning included."""
    outcome = engine.install_tool(tool, host_platform.detect(), runner)
    if outcome.status is not InstallStatus.INSTALLED:
        reason = _first_line(outcome.errors[0]) if outcome.errors else ""
        raise _Failed(prefix, f"{tool.id} install ended {outcome.status}: {reason}".rstrip(": "))
    return outcome


def _script_method(tool: Tool) -> Method:
    method = next(
        (m for m in resolve_methods(tool, host_platform.detect()) if m.kind == "script"), None
    )
    if method is None:
        raise ValueError(f"{tool.id} has no script method on this platform")
    return method


def _update(tool: Tool, prefix: str) -> None:
    """The installer-owned update the status pass would offer for a tool the installer put there."""
    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner="installer",
        method=_script_method(tool),
        package=None,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    outcome = perform_update(
        UpdateTarget(tool, ownership),
        platform=host_platform.detect(),
        runner=run_command,
        resolve_tag=versions.resolve_github_tag,
    )
    if outcome.status != "updated":
        raise _Failed(prefix, f"update ended {outcome.status}: {_first_line(outcome.detail)}")


def _uninstall(tool: Tool, runner: Runner) -> uninstall.SweepResult:
    """Remove one tool the way the Uninstall view does: through `app.perform_uninstall`, with a
    one-tool decision built from the fresh plan (review R1-09, R2-09)."""
    home = Path.home()
    bin_dir = home / ".local" / "bin"
    plan = uninstall.removal_plan(tool, bin_dir, verify=True)
    decision = app.UninstallDecision(
        tools=(tool,),
        paths={tool.id: plan.removable},
        argv={tool.id: plan.argv},
        unregister={tool.id: plan.unregister},
        remove_ban=False,
        remove_path_block=False,
    )
    return app.perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=home / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=home / ".zshrc",
        extra_policies=(),
        runner=runner,
        catalog=load_tools(Path(installer.__file__).with_name("registry.toml")),
        platform_os=app.HOST_SETTINGS_OS,
    )


def _removal_line(tool: Tool, result: uninstall.SweepResult) -> str:
    failed = "; ".join(f"{tool_id}: {_first_line(why)}" for tool_id, why in result.remove_failed)
    removed = ",".join(result.removed) or "-"
    return f"INFO removal of {tool.id}: removed={removed} failed={failed or '-'}"


def _leaf(home: Path, name: str) -> Path:
    """The receipt-proven path of one opencode leaf; the installer's own default when none."""
    receipt = receipts.read("opencode")
    for artifact in receipt.artifacts if receipt else ():
        if artifact.path.name == name:
            return artifact.path
    return home / ".opencode" / "bin" / name


def _proven_leaf(home: Path, name: str, prefix: str) -> Path:
    """The same, but only a receipt proves it: a service command never runs a guessed path."""
    receipt = receipts.read("opencode")
    if receipt is None or all(artifact.path.name != name for artifact in receipt.artifacts):
        raise _Failed(prefix, f"no receipt proves the {name} binary")
    return _leaf(home, name)


def _present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _version(binary: Path) -> str | None:
    return versions.probe_version_output([str(binary), "--version"])


def _receipt_paths() -> list[str]:
    receipt = receipts.read("opencode")
    return [str(artifact.path) for artifact in receipt.artifacts] if receipt else []


def _read_json(path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return cast(dict[str, object], document)


# --- the background service ---------------------------------------------------------------------


def _cmdlines() -> dict[int, list[str]]:
    found: dict[int, list[str]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:  # the process ended while the listing ran
            continue
        found[int(entry.name)] = [
            part.decode(errors="replace") for part in raw.split(b"\0") if part
        ]
    return found


def _serving() -> list[int]:
    return find_serve_pids(_cmdlines())


def _await(wanted: bool) -> list[int]:
    """The serve processes once there is one (`wanted`) or none, polled for a short while."""
    found = _serving()
    for _attempt in range(_POLL_ATTEMPTS):
        if bool(found) == wanted:
            break
        time.sleep(_POLL_STEP)
        found = _serving()
    return found


def _service(binary: Path, action: str) -> int:
    """`<binary> service <action>` with every stream closed: a daemon it starts must not keep our
    pipes open. A hang past the timeout reads as exit 124."""
    try:
        return subprocess.run(
            [str(binary), "service", action],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_SERVICE_TIMEOUT,
            start_new_session=True,
            check=False,
        ).returncode
    except subprocess.TimeoutExpired:
        return 124


def _ensure_service(binary: Path) -> tuple[bool, str]:
    """Whether a serve process runs, starting the service when none does, and the start's note."""
    if _serving():
        return True, "service already running"
    code = _service(binary, "start")
    return bool(_await(True)), f"service start exit={code}"


# --- verbs ----------------------------------------------------------------------------------

_Handler = Callable[[Path, bool], list[str]]


def _install_opencode(home: Path, _with_service: bool) -> list[str]:
    before = _digests(home)
    _install(_tool("opencode"), _INSTALL_FAILED)
    return [
        install_verdict(
            _version(_leaf(home, "opencode")), _receipt_paths(), before, _digests(home)
        ),
        tuning_verdict(opencode_document(home, app.HOST_SETTINGS_OS, os.environ)),
    ]


def _latest_opencode(_home: Path, _with_service: bool) -> list[str]:
    tool = _tool("opencode")

    def no_github(tag: str) -> str:
        raise versions.VersionError(f"GitHub was asked for opencode's latest ({tag})")

    ownership = ManagerOwnership(
        tool_id=tool.id,
        owner="installer",
        method=_script_method(tool),
        package=None,
        current_version=None,
        confidence="direct",
        shadowed=False,
        candidates=(),
        active_candidate=None,
        active_path=None,
        unknown_reason=None,
    )
    status, _entry = version_status.resolve_status(
        tool,
        ownership=ownership,
        outdated=OutdatedReport(brew={}, cask={}, pnpm={}, uv={}),
        entry=None,
        now=datetime.now(UTC),
        probe_output=versions.probe_version_output,
        resolve_tag=no_github,
        platform=host_platform.detect(),
    )
    return [latest_verdict(status.latest, status.source)]


def _update_opencode(home: Path, with_service: bool) -> list[str]:
    tool = _tool("opencode")
    if not with_service:
        before, digests = _version(_leaf(home, "opencode")), _digests(home)
        _update(tool, _V1_UPDATE_FAILED)
        return [
            v1_update_verdict(
                before,
                _version(_leaf(home, "opencode")),
                _receipt_paths(),
                digests,
                _digests(home),
            )
        ]
    binary = _proven_leaf(home, "opencode", _RUNNING_FAILED)
    running, note = _ensure_service(binary)
    lines = [f"INFO {note}"]
    if not running:
        return [*lines, update_while_running_verdict(False, None, None, None)]
    _update(tool, _RUNNING_FAILED)
    after = _version(binary)
    restart_code = _service(binary, "restart")
    pids = _await(True)
    exe: str | None = None
    restarted: str | None = None
    if pids:
        try:
            exe = os.readlink(f"/proc/{pids[0]}/exe")
        except OSError:
            exe = None
    if exe is not None and not exe.endswith("(deleted)"):
        restarted = versions.probe_version_output([exe, "--version"])
    return [
        *lines,
        f"INFO service restart exit={restart_code}",
        update_while_running_verdict(True, after, exe, restarted),
    ]


def _remove_opencode(home: Path, with_service: bool) -> list[str]:
    tool = _tool("opencode")
    lines: list[str] = []
    serve_before = False
    if with_service:
        serve_before, note = _ensure_service(_proven_leaf(home, "opencode", _REMOVE_FAILED))
        lines.append(f"INFO {note}")
    leaves = [_leaf(home, name) for name in _LEAVES]
    recorder = _Recorder(run_captured)
    result = _uninstall(tool, recorder)
    lines.append(_removal_line(tool, result))
    files_left = [leaf.name for leaf in leaves if _present(leaf)]
    receipt_left = receipts.read("opencode") is not None
    permissions_left = "permissions" in opencode_document(home, app.HOST_SETTINGS_OS, os.environ)
    serve_after = bool(_await(False))
    if with_service:
        return [
            *lines,
            remove_verdict(serve_before, serve_after, files_left, receipt_left, permissions_left),
        ]
    recipe = next((code for argv, code in recorder.calls if "service" in argv), None)
    left = _leftovers(serve_after, files_left, receipt_left, permissions_left)
    return [
        *lines,
        stop_idle_verdict(recipe),
        *([_verdict(_REMOVE_FAILED, "; ".join(left))] if left else []),
    ]


def _seed_v1(home: Path, _with_service: bool) -> list[str]:
    """OpenCode 1 as a pre-24.3 installer left it: the v1 script method, a receipt proving only
    `opencode`, and none of the v2 tuning."""
    shipped = _tool("opencode")
    method = _script_method(shipped)
    kept = {k: v for k, v in method.params.items() if k not in {"remove", "latest_npm", "update"}}
    params = {
        **kept,
        "url": _V1_URL,
        "paths": ["~/.opencode/bin/opencode"],
        "update": ["opencode", "upgrade"],
    }
    seeded = dataclasses.replace(
        shipped,
        methods=(dataclasses.replace(method, params=params),),
        post_install=(),
    )
    _install(seeded, _V1_SEED_FAILED)
    version = _semver(_version(_leaf(home, "opencode")))
    if version is None or not version.startswith("1."):
        raise _Failed(_V1_SEED_FAILED, f"the seeded install reports {version}, not OpenCode 1")
    return [f"TRACER_OPENCODE_V1_SEEDED version={version}"]


def _remove_v1(home: Path, _with_service: bool) -> list[str]:
    tool = _tool("opencode")
    binary = _leaf(home, "opencode")
    recorder = _Recorder(run_captured)
    result = _uninstall(tool, recorder)
    return [
        _removal_line(tool, result),
        v1_remove_verdict(
            tool.id in result.removed,
            _present(binary),
            receipts.read("opencode") is not None,
            recorder.argvs(),
        ),
    ]


def _copilot_config(home: Path) -> Mapping[str, object] | None:
    return _read_json(home / ".copilot" / "mcp-config.json")


def _pending_marks(tool: Tool) -> list[str]:
    """The `≈` reasons and steps the status pass would show for the tool's hook (24.3-08)."""
    hook_fact = cast(Callable[..., object], vars(version_status)["_hook_fact"])
    fact = hook_fact(
        tool,
        receipts.read(tool.id),
        postinstall.present_hosts(),
        None,
        shutil.which(tool.cmd),
        versions.probe_version_output,
    )
    reasons = cast(Sequence[str], getattr(fact, "misconfigured", ()))
    steps = cast(Sequence[object], getattr(fact, "steps", ()))
    return [*reasons, *(str(getattr(step, "text", "")) for step in steps)]


def _codegraph_copilot_and_pi(home: Path, _with_service: bool) -> list[str]:
    (home / ".copilot").mkdir(parents=True, exist_ok=True)
    (home / ".copilot" / "settings.json").write_text("{}\n", encoding="utf-8")
    (home / ".pi").mkdir(exist_ok=True)
    tool = _tool("codegraph")
    outcome = _install(tool, "TRACER_CODEGRAPH_COPILOT_FAILED")
    agent = home / ".pi" / "agent"
    entries = sorted(entry.name for entry in agent.iterdir()) if agent.is_dir() else []
    return [
        copilot_verdict(_copilot_config(home)),
        pi_gate_verdict(entries, outcome.postinstall_warning, _pending_marks(tool)),
    ]


def _codegraph_unregister(home: Path, _with_service: bool) -> list[str]:
    tool = _tool("codegraph")
    result = _uninstall(tool, _Recorder(run_captured))
    if tool.id not in result.removed:
        return [_verdict("TRACER_CODEGRAPH_UNREGISTER_FAILED", _removal_line(tool, result))]
    return [unregister_verdict(_copilot_config(home))]


def _codegraph_ide_only(home: Path, _with_service: bool) -> list[str]:
    shutil.rmtree(home / ".copilot", ignore_errors=True)
    (home / ".copilot" / "ide").mkdir(parents=True)
    recorder = _Recorder(run_command)
    _install(_tool("codegraph"), "TRACER_CODEGRAPH_COPILOT_IDE_ONLY_FAILED", recorder)
    return [ide_only_verdict((home / ".copilot" / "mcp-config.json").exists(), recorder.argvs())]


_HANDLERS: dict[tuple[str, str], _Handler] = {
    ("install", "opencode"): _install_opencode,
    ("latest", "opencode"): _latest_opencode,
    ("update", "opencode"): _update_opencode,
    ("remove", "opencode"): _remove_opencode,
    ("seed-v1", "opencode"): _seed_v1,
    ("remove-v1", "opencode"): _remove_v1,
    ("codegraph", "copilot-and-pi"): _codegraph_copilot_and_pi,
    ("codegraph", "unregister"): _codegraph_unregister,
    ("codegraph", "ide-only"): _codegraph_ide_only,
}
_SERVICE_VERBS = frozenset({"update", "remove"})


def _parse(args: Sequence[str]) -> tuple[_Handler, bool] | None:
    """The handler for a command line and whether `--with-service` was given, or None."""
    with_service = len(args) == 3 and args[0] in _SERVICE_VERBS and args[2] == "--with-service"
    words = args[:2] if with_service else args
    handler = _HANDLERS.get((words[0], words[1])) if len(words) == 2 else None
    return None if handler is None else (handler, with_service)


def accepts(args: Sequence[str]) -> bool:
    """Whether the driver accepts this command line (the harness script's steps are checked)."""
    return _parse(args) is not None


def _in_container() -> bool:
    """The driver installs and removes real tools: it runs in a container or not at all."""
    return Path("/run/.containerenv").exists() or Path("/.dockerenv").exists()


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = _parse(args)
    if parsed is None:
        known = " | ".join(" ".join(key) for key in _HANDLERS)
        print(
            f"usage: e2e_landing_driver {known} (update, remove: [--with-service])", file=sys.stderr
        )
        return 2
    if not _in_container():
        print("ERROR the landing driver runs only inside the disposable container")
        return 2
    handler, with_service = parsed
    try:
        lines = handler(Path.home(), with_service)
    except _Failed as failed:
        print(_verdict(failed.prefix, _first_line(failed.detail)))
        return 1
    except (OSError, CommandError, ValueError, versions.VersionError) as error:
        print(f"ERROR {_first_line(error) or type(error).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
