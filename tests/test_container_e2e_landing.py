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

_CONSTANTS = (
    "IMAGE_FEDORA",
    "LANDING_IMAGE",
    "LANDING_CONTAINER_NAME",
    "LANDING_KEEP_IMAGE",
    "LANDING_PULLED",
)

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


def test_landing_teardown_removes_the_image_this_run_pulled(tmp_path: Path) -> None:
    script = _script(
        "landing_teardown",
        variables={"LANDING_PULLED": "1"},
        stubs=_CT_STUB + "landing_teardown",
    )
    result = _run(script, tmp_path / "removes")
    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path / "removes")
    assert "ct rm -f tools-installer-e2e-landing" in calls
    assert f"ct rmi {_constant('IMAGE_FEDORA')}" in calls
    assert "TRACER_LANDING_TEARDOWN_OK" in result.stdout


def test_landing_teardown_leaves_a_shared_base_image_it_did_not_pull(tmp_path: Path) -> None:
    """F20: `fedora:latest` is every distro run's base image; a run that found it keeps it."""
    result = _run(
        _script("landing_teardown", stubs=_CT_STUB + "landing_teardown"), tmp_path / "shared"
    )
    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path / "shared")
    assert "ct rm -f tools-installer-e2e-landing" in calls
    assert not [call for call in calls if call.startswith("ct rmi")]
    assert "TRACER_LANDING_TEARDOWN_OK" in result.stdout


@pytest.mark.parametrize(("present", "pulled"), [(True, "0"), (False, "1")])
def test_audit_landing_records_whether_it_pulled_the_image(
    tmp_path: Path, present: bool, pulled: str
) -> None:
    scratch = tmp_path / f"pulled-{pulled}"
    result = _run(
        _script(
            "landing_note_image",
            variables={"FAIL_CT": "" if present else "image inspect"},
            stubs=_CT_STUB + "landing_note_image; echo pulled=$LANDING_PULLED",
        ),
        scratch,
    )
    assert result.returncode == 0, result.stderr
    assert f"pulled={pulled}" in result.stdout
    assert f"ct image inspect {_constant('IMAGE_FEDORA')}" in _calls(scratch)
    body = _function("cmd_audit_landing")
    assert body.index("landing_note_image") < body.index("landing_bootstrap")


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


# --- the latest source ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("latest", "source", "expected"),
    [
        ("2.3.0", "npm", "TRACER_OPENCODE_LATEST_OK latest=2.3.0 source=npm"),
        ("v2.3.0", "npm", "TRACER_OPENCODE_LATEST_OK latest=2.3.0 source=npm"),
        ("v1.19.5", "npm", "1.19.5"),
        ("2.3.0", "github", "source github"),
        (None, "npm", "no latest"),
    ],
)
def test_latest_verdict(latest: str | None, source: str, expected: str) -> None:
    line = driver.latest_verdict(latest, source)
    if expected.startswith("TRACER_"):
        assert line == expected
    else:
        assert line.startswith("TRACER_OPENCODE_LATEST_FAILED detail=")
        assert expected in line


# --- removal, with and without the background service ---------------------------------------------


def _remove(
    *,
    serve_before: bool = True,
    serve_after: bool = False,
    files_left: Sequence[str] = (),
    receipt_left: bool = False,
    permissions_left: bool = False,
) -> str:
    return driver.remove_verdict(
        serve_before, serve_after, files_left, receipt_left, permissions_left
    )


def test_remove_verdict_passes_only_with_a_service_stopped_and_everything_gone() -> None:
    assert _remove() == "TRACER_OPENCODE_V2_REMOVE_OK"


@pytest.mark.parametrize(
    ("leftover", "named"),
    [
        (_remove(serve_after=True), "serve process still running"),
        (_remove(files_left=["opencode"]), "opencode still present"),
        (_remove(files_left=["opencode2"]), "opencode2 still present"),
        (_remove(receipt_left=True), "receipt still present"),
        (_remove(permissions_left=True), "permissions key still present"),
    ],
)
def test_remove_verdict_names_each_leftover(leftover: str, named: str) -> None:
    assert leftover.startswith("TRACER_OPENCODE_V2_REMOVE_FAILED detail=")
    assert named in leftover


def test_remove_verdict_never_passes_without_a_service_to_stop() -> None:
    """Review R1-06: a removal with no serve process before it proves nothing about the stop."""
    line = _remove(serve_before=False)
    assert line.startswith("TRACER_OPENCODE_V2_SERVICE_STOP_UNPROVEN reason=")
    assert "REMOVE_OK" not in line


# --- an update while the service runs (review R1-10, R2-13) ---------------------------------------

_EXE = "/home/tester/.opencode/bin/opencode"


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        ((True, "opencode v2.3.0", _EXE, "2.3.0"), "TRACER_OPENCODE_UPDATE_WHILE_RUNNING_OK"),
        ((True, None, _EXE, "2.3.0"), "FAILED detail=--version failed"),
        ((True, "2.3.0", None, None), "FAILED detail=no serve process after the restart"),
        ((True, "2.3.0", f"{_EXE} (deleted)", "2.3.0"), "FAILED detail=the restarted service"),
        ((True, "2.3.0", _EXE, "2.2.6"), "FAILED detail=the restarted service reports 2.2.6"),
        ((True, "2.3.0", _EXE, None), "FAILED detail=the restarted service reports nothing"),
        ((False, "2.3.0", _EXE, "2.3.0"), "UNPROVEN reason="),
    ],
)
def test_update_while_running_verdict(
    facts: tuple[bool, str | None, str | None, str | None], expected: str
) -> None:
    line = driver.update_while_running_verdict(*facts)
    if expected.startswith("TRACER_"):
        assert line == expected
    else:
        assert expected in line
        assert "WHILE_RUNNING_OK" not in line


# --- the OpenCode 1 install -----------------------------------------------------------------------

_V1_ARGV = [["/home/tester/.opencode/bin/opencode2", "service", "stop"]]
_NO_ARGV: list[list[str]] = []


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        ((True, False, False, _NO_ARGV), "TRACER_OPENCODE_V1_REMOVE_OK"),
        ((False, False, False, _NO_ARGV), "removal failed"),
        ((True, True, False, _NO_ARGV), "opencode still present"),
        ((True, False, True, _NO_ARGV), "receipt still present"),
        ((True, False, False, _V1_ARGV), "ran a service command"),
    ],
)
def test_v1_remove_verdict(
    facts: tuple[bool, bool, bool, Sequence[Sequence[str]]], expected: str
) -> None:
    line = driver.v1_remove_verdict(*facts)
    if expected.startswith("TRACER_"):
        assert line == expected
    else:
        assert line.startswith("TRACER_OPENCODE_V1_REMOVE_FAILED detail=")
        assert expected in line


@pytest.mark.parametrize(
    ("before", "after", "receipt", "rc_after", "expected"),
    [
        ("1.19.5", "2.3.0", _LEAVES, _RC_SAME, "TRACER_OPENCODE_V1_UPDATE_OK from=1.19.5 to=2.3.0"),
        (
            "opencode 1.19.5",
            "v2.3.0",
            _LEAVES,
            _RC_SAME,
            "TRACER_OPENCODE_V1_UPDATE_OK from=1.19.5 to=2.3.0",
        ),
        ("1.19.5", "1.19.7", _LEAVES, _RC_SAME, "still on 1.19.7"),
        ("1.19.5", "2.3.0", _LEAVES[:1], _RC_SAME, "receipt lacks opencode2"),
        ("1.19.5", "2.3.0", _LEAVES, {**_RC_SAME, ".zshrc": "dd"}, ".zshrc"),
        ("2.3.0", "2.3.0", _LEAVES, _RC_SAME, "not OpenCode 1"),
    ],
)
def test_v1_update_verdict(
    before: str, after: str, receipt: Sequence[str], rc_after: Mapping[str, str], expected: str
) -> None:
    line = driver.v1_update_verdict(before, after, receipt, _RC_SAME, rc_after)
    if expected.startswith("TRACER_"):
        assert line == expected
    else:
        assert line.startswith("TRACER_OPENCODE_V1_UPDATE_FAILED detail=")
        assert expected in line


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, "TRACER_OPENCODE_V2_STOP_IDLE_OK"),
        (1, "TRACER_OPENCODE_V2_STOP_IDLE_FAILED exit=1"),
        (None, "TRACER_OPENCODE_V2_STOP_IDLE_FAILED exit=none"),
    ],
)
def test_stop_idle_verdict(code: int | None, expected: str) -> None:
    assert driver.stop_idle_verdict(code) == expected


@pytest.mark.parametrize(
    ("cmdlines", "expected"),
    [
        ({10: ["/home/tester/.opencode/bin/opencode", "serve", "--port", "4096"]}, [10]),
        ({11: ["opencode", "serve"], 12: ["opencode2", "serve"]}, [11, 12]),
        ({13: ["/home/tester/.opencode/bin/opencode", "service", "start"]}, []),
        ({14: ["/usr/bin/python3", "-m", "http.server", "serve"]}, []),
        ({15: ["/home/tester/.opencode/bin/opencode"]}, []),
    ],
)
def test_serve_processes_are_found_by_command_line(
    cmdlines: Mapping[int, Sequence[str]], expected: list[int]
) -> None:
    assert driver.find_serve_pids(cmdlines) == expected


# --- codegraph: copilot, the Pi gate, unregistering -----------------------------------------------

_REGISTERED = {"mcpServers": {"codegraph": {"command": "codegraph"}}}


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (_REGISTERED, "TRACER_CODEGRAPH_COPILOT_OK"),
        ({"mcpServers": {}}, "TRACER_CODEGRAPH_COPILOT_FAILED detail=codegraph is not registered"),
        (None, "TRACER_CODEGRAPH_COPILOT_FAILED detail=mcp-config.json is absent"),
    ],
)
def test_copilot_verdict(config: Mapping[str, object] | None, expected: str) -> None:
    assert driver.copilot_verdict(config) == expected


@pytest.mark.parametrize(
    ("entries", "warning", "marks", "expected"),
    [
        ([], "pi was skipped: codegraph has no pi target", [], "TRACER_CODEGRAPH_PI_GATED_OK"),
        (
            [],
            "Pi skipped",
            ["codegraph is not registered for Claude"],
            "TRACER_CODEGRAPH_PI_GATED_OK",
        ),
        (["AGENTS.md"], "pi skipped", [], "TRACER_CODEGRAPH_PI_GATED_FAILED detail=~/.pi/agent"),
        ([], None, [], "FAILED detail=the hook warning does not name Pi"),
        ([], "applied", [], "FAILED detail=the hook warning does not name Pi"),
        ([], "pi skipped", ["codegraph is not registered for Pi"], "FAILED detail=a pending mark"),
    ],
)
def test_pi_gate_verdict(
    entries: list[str], warning: str | None, marks: list[str], expected: str
) -> None:
    line = driver.pi_gate_verdict(entries, warning, marks)
    if expected.startswith("TRACER_CODEGRAPH_PI_GATED_OK"):
        assert line == expected
    else:
        assert line.startswith("TRACER_CODEGRAPH_PI_GATED_FAILED")
        assert expected.removeprefix("TRACER_CODEGRAPH_PI_GATED_FAILED ") in line


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (None, "TRACER_CODEGRAPH_UNREGISTER_OK"),
        ({"mcpServers": {"other": {}}}, "TRACER_CODEGRAPH_UNREGISTER_OK"),
        (_REGISTERED, "TRACER_CODEGRAPH_UNREGISTER_FAILED detail=codegraph is still registered"),
    ],
)
def test_unregister_verdict(config: Mapping[str, object] | None, expected: str) -> None:
    assert driver.unregister_verdict(config) == expected


@pytest.mark.parametrize(
    ("config_exists", "argvs", "expected"),
    [
        (
            False,
            [["codegraph", "install", "--target", "claude"]],
            "TRACER_CODEGRAPH_COPILOT_IDE_ONLY_OK",
        ),
        (True, [], "detail=mcp-config.json was written"),
        (False, [["codegraph", "install", "--target", "claude,copilot-cli"]], "detail=copilot-cli"),
    ],
)
def test_ide_only_verdict(
    config_exists: bool, argvs: Sequence[Sequence[str]], expected: str
) -> None:
    line = driver.ide_only_verdict(config_exists, argvs)
    if expected.startswith("TRACER_"):
        assert line == expected
    else:
        assert line.startswith("TRACER_CODEGRAPH_COPILOT_IDE_ONLY_FAILED")
        assert expected in line


def test_the_driver_refuses_an_unknown_verb_and_runs_nothing_on_the_host(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert driver.main(["install", "nothing"]) == 2
    assert driver.main(["remove", "opencode", "--bogus"]) == 2
    assert driver.main(["install", "opencode", "--with-service"]) == 2
    assert driver.main([]) == 2
    assert "usage" in capsys.readouterr().err


def test_the_driver_does_not_run_outside_a_container(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(driver, "_in_container", lambda: False)
    assert driver.main(["install", "opencode"]) == 2
    assert "only inside the disposable container" in capsys.readouterr().out


def _container_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, engine: bool, marker: bool, home: Path
) -> None:
    """A container whose engine file, harness marker and HOME are as given."""
    engine_file = tmp_path / "containerenv"
    if engine:
        engine_file.write_text("", encoding="utf-8")
    marker_file = tmp_path / "landing-marker"
    if marker:
        marker_file.write_text("audit-landing\n", encoding="utf-8")
    monkeypatch.setattr(driver, "_ENGINE_FILES", (engine_file,))
    monkeypatch.setattr(driver, "LANDING_MARKER", marker_file)
    monkeypatch.setattr(driver, "_TESTER_HOME", Path("/home/tester"))
    monkeypatch.setenv("HOME", str(home))


@pytest.mark.parametrize(
    ("engine", "marker", "home", "runs"),
    [
        (True, True, "/home/tester", True),
        (False, True, "/home/tester", False),  # no container engine file
        (True, False, "/home/tester", False),  # toolbox/distrobox: engine file, no harness marker
        (True, True, "/home/someone", False),  # the real HOME is mounted
        (True, False, "/home/someone", False),
    ],
)
def test_the_driver_needs_the_container_the_marker_and_the_tester_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    engine: bool,
    marker: bool,
    home: str,
    runs: bool,
) -> None:
    """F13: `/run/.containerenv` is also in toolbox and distrobox, which mount the real HOME."""
    _container_files(monkeypatch, tmp_path, engine=engine, marker=marker, home=Path(home))
    assert vars(driver)["_in_container"]() is runs
    if not runs:
        assert driver.main(["install", "opencode"]) == 2
        assert "only inside the disposable container" in capsys.readouterr().out


def test_the_script_writes_the_marker_the_driver_requires() -> None:
    writer = _function("write_landing_marker")
    assert str(driver.LANDING_MARKER) in writer
    body = _function("landing_bootstrap")
    assert "landing_stage marker write_landing_marker" in body
    assert body.index("landing_stage start") < body.index("landing_stage marker")


# --- the step order and the shell helpers ---------------------------------------------------------

_STEP = re.compile(r"^  landing_step (\S+) (.+?) \|\| failed=1$", re.MULTILINE)
_EXPECTED_STEPS = (
    "install opencode",
    "latest opencode",
    "update opencode --with-service",
    "remove opencode --with-service",
    "install opencode",
    "remove opencode",
    "seed-v1 opencode",
    "remove-v1 opencode",
    "seed-v1 opencode",
    "update opencode",
    "codegraph copilot-and-pi",
    "codegraph unregister",
    "codegraph ide-only",
)


def test_audit_landing_runs_every_step_in_order() -> None:
    body = _function("cmd_audit_landing")
    steps = _STEP.findall(body)
    assert tuple(command for _name, command in steps) == _EXPECTED_STEPS
    names = [name for name, _command in steps]
    assert len(set(names)) == len(names), "every step has its own name"
    assert body.index("trap landing_teardown EXIT") < body.index("landing_bootstrap")
    assert body.index("landing_bootstrap") < body.index("landing_step")


def test_every_step_the_script_runs_is_accepted_by_the_driver() -> None:
    for command in _EXPECTED_STEPS:
        args = command.split()
        assert driver.accepts(args), command


_ENV_RE = re.compile(r"^LANDING_ENV_RE=.+$", re.MULTILINE)


def _helpers(scratch: Path, driver_out: str, driver_rc: int, calls: str) -> str:
    """The step helpers over a fake `landing_driver` printing `driver_out`, exiting `driver_rc`."""
    env_line = _ENV_RE.search(_text())
    assert env_line is not None
    stub = (
        f"LANDING_TRANSCRIPT={shlex.quote(str(scratch / 'transcript'))}\n"
        f"{env_line.group(0)}\n"
        f"landing_driver() {{ printf '%s\\n' {shlex.quote(driver_out)}; return {driver_rc}; }}\n"
    )
    names = ("landing_infeasible", "landing_environmental", "landing_stage", "landing_step")
    return _script(*names, stubs=stub + calls)


def test_landing_step_passes_a_clean_driver_run(tmp_path: Path) -> None:
    calls = "landing_step tuning x y; echo rc=$?"
    result = _run(
        _helpers(tmp_path / "ok", "TRACER_OPENCODE_V2_TUNING_OK", 0, calls), tmp_path / "ok"
    )
    assert result.returncode == 0, result.stderr
    assert "TRACER_OPENCODE_V2_TUNING_OK" in result.stdout
    assert "rc=0" in result.stdout
    assert "TRACER_OPENCODE_V2_TUNING_OK" in (tmp_path / "ok" / "transcript").read_text()


@pytest.mark.parametrize(
    ("out", "rc"),
    [
        ("TRACER_OPENCODE_V2_INSTALL_FAILED detail=version 1.19.5 is not OpenCode 2", 1),
        ("TRACER_OPENCODE_V2_SERVICE_STOP_UNPROVEN reason=no serve process", 0),
        ("ERROR something broke in the product", 1),
    ],
)
def test_landing_step_fails_a_named_failure_without_calling_it_infeasible(
    tmp_path: Path, out: str, rc: int
) -> None:
    scratch = tmp_path / "fail"
    result = _run(_helpers(scratch, out, rc, "landing_step install x y || echo rc=$?"), scratch)
    assert result.returncode == 0, result.stderr
    assert "rc=1" in result.stdout
    assert "INFEASIBLE" not in result.stdout


@pytest.mark.parametrize(
    "out",
    [
        "TRACER_OPENCODE_V2_SERVICE_START_FAILED detail=Connection refused 127.0.0.1:4096",
        "ERROR OpenSSL 3.2.1 is not the expected build",
        "ERROR TLS handshake log line from the product",
        "curl: (6) Could not resolve host: opencode.ai\nTRACER_OPENCODE_V2_INSTALL_FAILED x",
    ],
    ids=["refused-port", "openssl", "tls-word", "failed-line-wins"],
)
def test_a_product_failure_is_never_infeasible(tmp_path: Path, out: str) -> None:
    """F21: only an environmental emitter's line ends the run, and never after a FAILED verdict."""
    scratch = tmp_path / "product"
    result = _run(_helpers(scratch, out, 1, "landing_step s a b || echo rc=$?"), scratch)
    assert result.returncode == 0, result.stderr
    assert "INFEASIBLE" not in result.stdout
    assert "rc=1" in result.stdout


def test_landing_step_ends_the_run_on_an_environmental_failure(tmp_path: Path) -> None:
    scratch = tmp_path / "env"
    out = "curl: (6) Could not resolve host: opencode.ai"
    calls = "landing_step install-opencode install opencode; echo after"
    result = _run(_helpers(scratch, out, 1, calls), scratch)
    assert result.returncode == 2
    assert "TRACER_LANDING_INFEASIBLE step=install-opencode detail=" in result.stdout
    assert "after" not in result.stdout


def test_landing_stage_stops_at_the_first_failing_command_and_names_the_stage(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "stage"
    bad = 'bad_stage() { echo "Error: dnf could not sync"; false; echo after; }\n'
    result = _run(
        _helpers(scratch, "", 0, bad + "landing_stage prereqs bad_stage; echo done"), scratch
    )
    assert result.returncode == 2
    assert (
        "TRACER_LANDING_INFEASIBLE step=prereqs detail=Error: dnf could not sync" in result.stdout
    )
    assert "after" not in result.stdout
    assert "done" not in result.stdout


def test_landing_stage_is_silent_when_the_stage_succeeds(tmp_path: Path) -> None:
    scratch = tmp_path / "good"
    good = "good_stage() { echo fine; }\n"
    result = _run(
        _helpers(scratch, "", 0, good + "landing_stage tester good_stage; echo done"), scratch
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "done"
