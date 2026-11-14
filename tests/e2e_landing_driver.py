"""The in-container driver for the audit-landing e2e (24.3-09, SPEC R5, R6, R8, R9).

Run as `python -m tests.e2e_landing_driver <verb>` from the workspace: the container harness
(`scripts/container-e2e-verify.sh audit-landing`) has the installer's own code install, tune,
update and remove tools, so nothing is hand-written. Verbs:

  install opencode          install the shipped OpenCode 2 entry; prints the install and tuning
                            verdicts (TRACER_OPENCODE_V2_INSTALL_*, TRACER_OPENCODE_V2_TUNING_*)

Every verdict is a pure function of facts the verb gathered, so the host tests run them on
fixtures; the verbs themselves start vendor installers and refuse to run outside a container.
A product failure prints a named `TRACER_<STEP>_FAILED detail=...` line and exits 1; an error
prints `ERROR <first line>` and exits 1. Exit code 2: a bad verb or argument count, or not in a
container.

It imports only `installer` and the standard library: the container runs it with `--no-dev`.
"""

import hashlib
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import installer
from installer import agent_settings, engine, receipts, versions
from installer import platform as host_platform
from installer.app import HOST_SETTINGS_OS
from installer.enums import InstallStatus
from installer.model import Tool, load_tools
from installer.run import CommandError, Runner, run_command
from installer.sanitize import sanitize_log_line

_RC_FILES = (".bashrc", ".bash_profile", ".profile", ".zshrc")
_ALLOW_ALL: list[object] = [{"action": "*", "resource": "*", "effect": "allow"}]
_SEMVER = re.compile(r"\d+\.\d+\.\d+")
_INSTALL_FAILED = "TRACER_OPENCODE_V2_INSTALL_FAILED"


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


# --- pure verdicts --------------------------------------------------------------------------


def install_verdict(
    version_output: str | None,
    receipt_paths: Sequence[str],
    rc_before: Mapping[str, str],
    rc_after: Mapping[str, str],
) -> str:
    """OpenCode 2 installed: a 2.x version, both leaves in the receipt, no shell rc touched."""
    version = _semver(version_output)
    names = {Path(path).name for path in receipt_paths}
    missing = [leaf for leaf in ("opencode", "opencode2") if leaf not in names]
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
    return f"{_INSTALL_FAILED} detail={detail}"


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
    return f"TRACER_OPENCODE_V2_TUNING_FAILED detail={detail}"


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


def _install(tool: Tool, prefix: str, runner: Runner = run_command) -> engine.InstallOutcome:
    """The one-tool install path `make setup` runs for a selected row, hooks and tuning included."""
    outcome = engine.install_tool(tool, host_platform.detect(), runner)
    if outcome.status is not InstallStatus.INSTALLED:
        reason = _first_line(outcome.errors[0]) if outcome.errors else ""
        raise _Failed(prefix, f"{tool.id} install ended {outcome.status}: {reason}".rstrip(": "))
    return outcome


def _leaf(home: Path, name: str) -> Path:
    """The receipt-proven path of one opencode leaf; the installer's own default when none."""
    receipt = receipts.read("opencode")
    for artifact in receipt.artifacts if receipt else ():
        if artifact.path.name == name:
            return artifact.path
    return home / ".opencode" / "bin" / name


def _version(binary: Path) -> str | None:
    return versions.probe_version_output([str(binary), "--version"])


# --- verbs ----------------------------------------------------------------------------------

_Handler = Callable[[Path, bool], list[str]]


def _install_opencode(home: Path, _with_service: bool) -> list[str]:
    before = _digests(home)
    _install(_tool("opencode"), _INSTALL_FAILED)
    receipt = receipts.read("opencode")
    paths = [str(artifact.path) for artifact in receipt.artifacts] if receipt else []
    return [
        install_verdict(_version(_leaf(home, "opencode")), paths, before, _digests(home)),
        tuning_verdict(opencode_document(home, HOST_SETTINGS_OS, os.environ)),
    ]


_HANDLERS: dict[tuple[str, str], _Handler] = {("install", "opencode"): _install_opencode}
_SERVICE_VERBS = frozenset({"update", "remove"})


def _in_container() -> bool:
    """The driver installs and removes real tools: it runs in a container or not at all."""
    return Path("/run/.containerenv").exists() or Path("/.dockerenv").exists()


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    with_service = bool(args) and args[0] in _SERVICE_VERBS and args[-1:] == ["--with-service"]
    key = tuple(args[: len(args) - with_service])
    handler = _HANDLERS.get((key[0], key[1])) if len(key) == 2 else None
    if handler is None:
        print(
            f"usage: e2e_landing_driver {' | '.join(' '.join(k) for k in _HANDLERS)}",
            file=sys.stderr,
        )
        return 2
    if not _in_container():
        print("ERROR the landing driver runs only inside the disposable container")
        return 2
    try:
        lines = handler(Path.home(), with_service)
    except _Failed as failed:
        print(f"{failed.prefix} detail={_first_line(failed.detail)}")
        return 1
    except (OSError, CommandError, ValueError, versions.VersionError) as error:
        print(f"ERROR {_first_line(error) or type(error).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
