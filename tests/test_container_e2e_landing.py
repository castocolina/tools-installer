"""Host tests of the audit-landing target and its in-container driver (24.3-09, SPEC R5).

The harness sources the container detector at load time, so these tests never source it and
never start a container: they read the committed script text and run extracted bash functions
with a stubbed `ct`. The driver is imported for its pure verdict functions only; its verbs
start vendor installers and run only in the disposable container, under the orchestrator
(24.3-11 Task 2).
"""

import re
import shlex
import shutil
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from installer import agent_settings
from tests import e2e_landing_driver as driver

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "container-e2e-verify.sh"

_CONSTANTS = ("IMAGE_FEDORA", "LANDING_IMAGE", "LANDING_CONTAINER_NAME", "LANDING_KEEP_IMAGE")

# One CALLS line per container call; a case fails a call by naming a fragment of its arguments.
_CT_STUB = r"""
ct() {
  printf 'ct %s\n' "$*" >> "$CALLS"
  if [ -n "${FAIL_CT:-}" ] && [[ "$*" == *"$FAIL_CT"* ]]; then
    return 125
  fi
  return 0
}
"""


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None, "bash is required on every supported host"
    return found


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _constant(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)\s*$", _text(), re.MULTILINE)
    assert match is not None, f"{name} is not assigned in the script"
    return match.group(1)


def _function(name: str) -> str:
    """The function body as committed, from its header through its closing brace."""
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, f"{name}() is not defined in the script"
    return match.group(0)


def _script(*names: str, variables: Mapping[str, str] | None = None, stubs: str = "") -> str:
    """Extracted constants and functions, then the case's variables, then its stubs."""
    parts = ["set -uo pipefail"]
    parts.extend(f"{name}={_constant(name)}" for name in _CONSTANTS)
    parts.extend(_function(name) for name in names)
    parts.extend(f"{key}={shlex.quote(value)}" for key, value in (variables or {}).items())
    parts.append(stubs)
    return "\n".join(parts)


def _run(script: str, scratch: Path) -> subprocess.CompletedProcess[str]:
    scratch.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(scratch),
        "CALLS": str(scratch / "calls"),
        "LANG": "C",
    }
    script_file = scratch.parent / f"harness-{uuid.uuid4().hex}.sh"
    script_file.write_text(script, encoding="utf-8")
    try:
        return subprocess.run(
            [_bash(), str(script_file)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    finally:
        script_file.unlink()


def _calls(scratch: Path) -> list[str]:
    calls = scratch / "calls"
    return calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []


# --- the target is registered -------------------------------------------------------------------


def test_audit_landing_is_registered() -> None:
    text = _text()
    assert re.search(r"^\s*audit-landing\) cmd_audit_landing \"\$@\" ;;$", text, re.MULTILINE)
    assert _constant("LANDING_CONTAINER_NAME") == "tools-installer-e2e-landing"
    usage = _function("usage")
    assert "audit-landing [--keep-image]" in usage
    assert "Orchestrator only" in usage.split("audit-landing [--keep-image]", 1)[1]
    assert "trap landing_teardown EXIT" in _function("cmd_audit_landing")


# --- the install verdict ------------------------------------------------------------------------

_LEAVES = ("/home/tester/.opencode/bin/opencode", "/home/tester/.opencode/bin/opencode2")
_RC_SAME = {".bashrc": "aa", ".bash_profile": "bb", ".profile": "absent", ".zshrc": "absent"}


@pytest.mark.parametrize(
    ("version", "receipt", "rc_after", "expected"),
    [
        ("opencode v2.3.0", _LEAVES, _RC_SAME, "TRACER_OPENCODE_V2_INSTALL_OK version=2.3.0"),
        ("2.3.0\n", _LEAVES, _RC_SAME, "TRACER_OPENCODE_V2_INSTALL_OK version=2.3.0"),
        ("1.19.5", _LEAVES, _RC_SAME, "version"),
        (None, _LEAVES, _RC_SAME, "version"),
        ("opencode v2.3.0", _LEAVES[:1], _RC_SAME, "opencode2"),
        ("opencode v2.3.0", _LEAVES[1:], _RC_SAME, "lacks opencode"),
        ("opencode v2.3.0", _LEAVES, {**_RC_SAME, ".bashrc": "cc"}, ".bashrc"),
    ],
)
def test_install_verdict(
    version: str | None, receipt: Sequence[str], rc_after: Mapping[str, str], expected: str
) -> None:
    line = driver.install_verdict(version, receipt, _RC_SAME, rc_after)
    if expected.startswith("TRACER_"):
        assert line == expected
    else:
        assert line.startswith("TRACER_OPENCODE_V2_INSTALL_FAILED detail=")
        assert expected in line


# --- the tuning verdict -------------------------------------------------------------------------

_ALLOW = [{"action": "*", "resource": "*", "effect": "allow"}]


@pytest.mark.parametrize(
    ("document", "detail"),
    [
        ({"permissions": _ALLOW}, None),
        ({"permissions": _ALLOW, "theme": "SECRET-VALUE"}, None),
        ({}, "permissions"),
        ({"permissions": [{"action": "SECRET-VALUE"}]}, "permissions"),
        ({"permissions": _ALLOW, "permission": "SECRET-VALUE"}, "permission "),
    ],
)
def test_tuning_verdict(document: Mapping[str, object], detail: str | None) -> None:
    line = driver.tuning_verdict(document)
    if detail is None:
        assert line == "TRACER_OPENCODE_V2_TUNING_OK"
    else:
        assert line.startswith("TRACER_OPENCODE_V2_TUNING_FAILED detail=")
        assert detail in line
    assert "SECRET-VALUE" not in line


def test_tuning_reads_the_file_the_writer_chose(tmp_path: Path) -> None:
    """Review R1-07: opencode.json by default, opencode.jsonc once that file exists."""
    plain = tmp_path / ".config" / "opencode" / "opencode.json"
    commented = plain.with_name("opencode.jsonc")
    expected = agent_settings.settings_file(
        "opencode", home=tmp_path, platform_os="linux", environ={}
    )
    assert driver.opencode_settings_path(tmp_path, "linux", {}) == expected == plain
    plain.parent.mkdir(parents=True)
    commented.write_text('// ours\n{"permissions": []}\n', encoding="utf-8")
    assert driver.opencode_settings_path(tmp_path, "linux", {}) == commented
    assert driver.opencode_document(tmp_path, "linux", {}) == {"permissions": []}


def test_a_missing_settings_file_reads_as_an_empty_document(tmp_path: Path) -> None:
    assert driver.opencode_document(tmp_path, "linux", {}) == {}


# --- teardown -----------------------------------------------------------------------------------


def test_landing_teardown_removes_container_and_image(tmp_path: Path) -> None:
    result = _run(
        _script("landing_teardown", stubs=_CT_STUB + "landing_teardown"), tmp_path / "removes"
    )
    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path / "removes")
    assert "ct rm -f tools-installer-e2e-landing" in calls
    assert f"ct rmi {_constant('IMAGE_FEDORA')}" in calls
    assert "TRACER_LANDING_TEARDOWN_OK" in result.stdout


def test_landing_teardown_keeps_the_image_on_request(tmp_path: Path) -> None:
    script = _script(
        "landing_teardown",
        variables={"LANDING_KEEP_IMAGE": "1"},
        stubs=_CT_STUB + "landing_teardown",
    )
    result = _run(script, tmp_path / "keeps")
    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path / "keeps")
    assert "ct rm -f tools-installer-e2e-landing" in calls
    assert not [call for call in calls if call.startswith("ct rmi")]
    assert "TRACER_LANDING_TEARDOWN_OK" in result.stdout
