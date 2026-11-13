"""The container e2e's host-side checks for receipts and summary behavior.

The script sources the container detector at load time, so these tests never
source it and never start a container. They read the committed text and run
the extracted functions in bash with fixture transcripts and a scratch HOME.
"""

import json
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest

from installer.model import load_tools
from installer.platform import Platform
from installer.receipts import default_receipts_dir
from installer.resolve import resolve_methods
from tests.test_registry import REGISTRY

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "container-e2e-verify.sh"

PROBE_TOOL = "yq"
PROBE_CATEGORY = "data"
_FEDORA = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)

_FUNCTIONS = (
    "receipt_check_applies",
    "assert_receipt_present",
    "assert_receipt_removed",
    "assert_receipt_ready_for_removal",
)

_CONSTANTS = (
    "RECEIPT_PROBE_TOOL",
    "RECEIPT_PROBE_CATEGORY",
    "TESTER_USER",
    "TESTER_HOME",
    "TESTER_WORKSPACE",
    "BREW_BIN",
)


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None, "bash is required on every supported host"
    return found


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _constant(name: str, text: str | None = None) -> str:
    body = _script_text() if text is None else text
    match = re.search(rf"^{name}=(\S+)\s*$", body, re.MULTILINE)
    assert match is not None, f"{name} is not assigned in the script"
    return match.group(1)


def _function(name: str, text: str | None = None) -> str:
    """The function body as committed, from its header through its closing brace."""
    body = _script_text() if text is None else text
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", body, re.MULTILINE | re.DOTALL)
    assert match is not None, f"{name}() is not defined in the script"
    return match.group(0)


def _probe_tool() -> str:
    return _constant("RECEIPT_PROBE_TOOL")


def test_script_receipt_path_matches_the_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The path the script tests is the path the receipts module names."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tool = _probe_tool()
    relative = default_receipts_dir().relative_to(tmp_path)
    assert tool == PROBE_TOOL
    present = _function("assert_receipt_present")
    # The script defers `$HOME` to the shell that runs the check (the
    # container's, or the scratch-HOME stub's), the same way
    # run_setup_as_tester defers it, and names the file from the probe id.
    # Under that HOME the directory is the module's receipts dir.
    assert 'local receipt="' + chr(92) + f"$HOME/{relative}/" in present
    assert "${RECEIPT_PROBE_TOOL}.json" in present


def test_probe_tool_is_raw_download_first_on_fedora() -> None:
    """The probe is the first registry tool whose first Fedora method is a raw download."""
    tool_id = _probe_tool()
    tools = load_tools(REGISTRY)
    raw_first = [
        tool
        for tool in tools
        if (methods := resolve_methods(tool, _FEDORA))
        and methods[0].kind == "github_release"
        and methods[0].params.get("raw") is True
    ]
    assert raw_first, "no raw github_release tool applies first on fedora"
    assert raw_first[0].id == tool_id == PROBE_TOOL


def test_probe_category_matches_the_registry() -> None:
    """The category the script names is the probe tool's own registry category."""
    category = _constant("RECEIPT_PROBE_CATEGORY")
    tool = next(item for item in load_tools(REGISTRY) if item.id == _probe_tool())
    assert category == tool.category == PROBE_CATEGORY


def _harness(*names: str) -> str:
    """Extracted constants and functions, with exec_tester pinned to this HOME.

    A function that calls another extracted function pulls that one in too,
    so a caller names the function it invokes and gets its callees.
    """
    text = _script_text()
    wanted = list(names)
    for name in list(wanted):
        if name == "assert_receipt_present" and "receipt_check_applies" not in wanted:
            wanted.append("receipt_check_applies")
    parts = [f"{name}={_constant(name, text)}" for name in _CONSTANTS]
    parts.extend(_function(name, text) for name in wanted)
    parts.append('exec_tester() { HOME="$SCRATCH" bash -c "$1"; }')
    return "\n".join(parts)


def _summary_harness(*names: str) -> str:
    """Extract summary helpers and initialize isolated accumulator state."""
    text = _script_text()
    match = re.search(r"^SUMMARY_RE='([^']+)'$", text, re.MULTILINE)
    assert match is not None, "SUMMARY_RE is not assigned in the script"
    parts = [f"SUMMARY_RE={shlex.quote(match.group(1))}"]
    wanted = list(names)
    if "accumulate_summaries" in wanted and "parse_summary_line" not in wanted:
        wanted.insert(0, "parse_summary_line")
    parts.extend(_function(name, text) for name in wanted)
    parts.append(
        'ACC_DEP_LINES_FILE="$SCRATCH/dependency-lines"\n'
        'ACC_MANUAL_NAMES_FILE="$SCRATCH/manual-names"\n'
        ': > "$ACC_DEP_LINES_FILE"\n: > "$ACC_MANUAL_NAMES_FILE"\n'
        "ACC_RUNS=0; ACC_SUMMARIES=0; ACC_NOT_ATTEMPTED=0; ACC_CRASHED=0\n"
        "ACC_INSTALLED=0; ACC_UPDATED=0; ACC_SKIPPED=0; ACC_FAILED=0\n"
        "ACC_DEP_FAILED=0; ACC_MISMATCHED=0; ACC_BLOCKED=0; ACC_MANUAL=0\n"
        "ACC_POST_RUN_ERRORS=0\n"
        "ACC_REPAIRED=0; ACC_RECONFIGURED=0; ACC_REINSTALLED=0\n"
    )
    return "\n".join(parts)


def _summary_run(
    script: str, scratch: Path, transcript: str, command: str
) -> subprocess.CompletedProcess[str]:
    fixture = scratch / "transcript.txt"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(transcript, encoding="utf-8")
    state = (
        'status=$?; printf "ACC_NOT_ATTEMPTED=%s ACC_CRASHED=%s ACC_INSTALLED=%s '
        'ACC_RUNS=%s ACC_SUMMARIES=%s\\n" "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" '
        '"$ACC_INSTALLED" "$ACC_RUNS" "$ACC_SUMMARIES"; exit "$status"'
    )
    invocation = command.replace("$TRANSCRIPT", '"$SCRATCH/transcript.txt"')
    if invocation == "accumulate_summaries":
        invocation += ' "$SCRATCH/transcript.txt"'
    invocation += "; result=$?; (( result == 0 ))"
    return _run(script + f"\n{invocation}\n{state}\n", scratch)


def _run(
    script: str, scratch: Path, *, path: str = "/usr/bin:/bin"
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": path,
        "HOME": str(scratch),
        "SCRATCH": str(scratch),
        "CALLS": str(scratch / "calls"),
        "LANG": "C",
    }
    # D-18: run the script as a file, not a `-c` string, so extracted bodies that a
    # `-c` parser refuses still run. The file sits beside the scratch HOME, never in it.
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


def test_assert_receipt_functions_in_bash(tmp_path: Path) -> None:
    """Present, absent, removed and leftover each print their own tracer line."""
    scratch = tmp_path / "home"
    receipt = scratch / ".local" / "state" / "tools-installer" / "receipts" / f"{PROBE_TOOL}.json"
    binary = scratch / ".local" / "bin" / PROBE_TOOL
    receipt.parent.mkdir(parents=True)
    binary.parent.mkdir(parents=True)
    receipt.write_text("{}\n", encoding="utf-8")
    binary.write_bytes(b"yq")

    present = _run(_harness("assert_receipt_present") + '\nassert_receipt_present ""\n', scratch)
    assert present.returncode == 0, present.stderr
    assert f"TRACER_RECEIPT_OK tool={PROBE_TOOL}" in present.stdout

    receipt.unlink()
    missing = _run(_harness("assert_receipt_present") + '\nassert_receipt_present ""\n', scratch)
    assert missing.returncode != 0
    assert f"TRACER_RECEIPT_MISSING tool={PROBE_TOOL}" in missing.stdout

    binary.unlink()
    removed = _run(_harness("assert_receipt_removed") + "\nassert_receipt_removed\n", scratch)
    assert removed.returncode == 0, removed.stderr
    assert "TRACER_RECEIPT_REMOVAL_OK" in removed.stdout

    binary.write_bytes(b"left behind")
    leftover = _run(_harness("assert_receipt_removed") + "\nassert_receipt_removed\n", scratch)
    assert leftover.returncode != 0
    assert "TRACER_RECEIPT_REMOVAL_INCOMPLETE" in leftover.stdout
    assert f"binary=$HOME/.local/bin/{PROBE_TOOL}" in leftover.stdout


def test_accumulate_counts_not_attempted_and_crashed(tmp_path: Path) -> None:
    harness = _summary_harness("accumulate_summaries")
    first = _summary_run(
        harness,
        tmp_path / "one",
        "State check failed: no state for ponytail\nSummary — 89 not attempted\n",
        "accumulate_summaries",
    )
    assert first.returncode == 0, first.stderr
    assert "ACC_NOT_ATTEMPTED=89" in first.stdout
    assert "ACC_RUNS=1" in first.stdout
    assert "ACC_SUMMARIES=1" in first.stdout

    second = _summary_run(
        harness,
        tmp_path / "two",
        "Summary — 4 installed, 1 crashed, 3 not attempted\n",
        "accumulate_summaries",
    )
    assert second.returncode == 0, second.stderr
    assert "ACC_CRASHED=1" in second.stdout
    assert "ACC_INSTALLED=4" in second.stdout


@pytest.mark.parametrize(
    ("transcript", "setup_exit", "dependency_row", "manual_row", "expected"),
    [
        ("Summary — 3 installed, 2 skipped", 0, "", "", 0),
        ("Summary — 89 not attempted", 1, "", "", 1),
        ("Summary — 4 installed, 1 crashed, 3 not attempted", 1, "", "", 1),
        ("Traceback: failed", 1, "", "", 1),
        ("Summary — 3 installed", 2, "", "", 1),
        ("Summary — 3 installed", 1, "", "", 1),
        (
            "Summary — 5 installed, 1 manual, 1 dependency failed",
            1,
            "✖ mmdc  dependency failed — pi",
            "○ pi  manual — see the setup steps in the log",
            0,
        ),
        (
            "Summary — 5 installed, 1 manual, 1 dependency failed",
            1,
            "✖ mmdc  dependency failed — pi",
            (
                "○ pi  manual — see the setup steps in the log\n"
                "PATH wiring could not be completed: [Errno 30] Read-only file system: "
                "'/home/tester/.bashrc'"
            ),
            1,
        ),
        (
            "Summary — 5 installed, 1 manual, 1 dependency failed",
            1,
            "✖ mmdc  dependency failed — pi",
            (
                "○ pi  manual — see the setup steps in the log\n"
                "PATH audit could not be completed: audit failed"
            ),
            1,
        ),
        (
            "Summary — 5 installed, 1 manual, 1 dependency failed",
            1,
            "✖ mmdc  dependency failed — pi",
            "",
            1,
        ),
    ],
)
def test_install_step_gate(
    tmp_path: Path,
    transcript: str,
    setup_exit: int,
    dependency_row: str,
    manual_row: str,
    expected: int,
) -> None:
    harness = _summary_harness(
        "parse_summary_line",
        "accumulate_summaries",
        "dependency_failures_explained",
        "install_step_ok",
    )
    content = "\n".join(line for line in (transcript, dependency_row, manual_row) if line)
    result = _summary_run(
        harness,
        tmp_path,
        content,
        f"accumulate_summaries $TRANSCRIPT; install_step_ok {setup_exit}",
    )
    assert result.returncode == expected, result.stdout + result.stderr


def test_parse_summary_line_needs_no_external_tool(tmp_path: Path) -> None:
    harness = _summary_harness("parse_summary_line")
    names = (
        "INSTALLED",
        "UPDATED",
        "REPAIRED",
        "RECONFIGURED",
        "REINSTALLED",
        "SKIPPED",
        "BLOCKED",
        "MANUAL",
        "FAILED",
        "MISMATCHED",
        "DEP_FAILED",
        "NOT_ATTEMPTED",
        "CRASHED",
    )
    variables = " ".join(f'"$PARSE_{name}"' for name in names)
    categories = (
        "1 installed, 2 updated, 3 repaired, 4 reconfigured, 5 reinstalled, "
        "6 skipped, 7 blocked, 8 manual, 9 failed, 10 checksum mismatch, "
        "11 dependency failed, 12 not attempted, 13 crashed"
    )
    format_string = " ".join(["%s"] * len(names)) + "\\n"
    command = (
        f'parse_summary_line "Summary — {categories}"; printf "{format_string}" {variables}; '
        f'parse_summary_line "Summary — nothing selected"; printf "{format_string}" {variables}'
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    result = _run(harness + "\n" + command, tmp_path, path="")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "1 2 3 4 5 6 7 8 9 10 11 12 13",
        "0 0 0 0 0 0 0 0 0 0 0 0 0",
    ]


def test_a_folded_dependency_failed_row_is_read_whole(tmp_path: Path) -> None:
    harness = _summary_harness(
        "parse_summary_line",
        "accumulate_summaries",
        "dependency_failures_explained",
        "install_step_ok",
    )
    transcript = "\n".join(
        (
            "Summary — 1 installed, 3 manual, 1 dependency failed",
            "✖ mmdc  dependency failed — pi, node,",
            "                         java",
            "○ pi  manual — see the setup steps in the log",
            "○ node  manual — see the setup steps in the log",
            "○ java  manual — see the setup steps in the log",
        )
    )
    result = _summary_run(
        harness,
        tmp_path,
        transcript,
        "accumulate_summaries $TRANSCRIPT; install_step_ok 1",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "dependency-lines").read_text(encoding="utf-8") == (
        "✖ mmdc  dependency failed — pi, node, java\n"
    )


def test_a_two_space_report_line_is_not_joined_to_a_row(tmp_path: Path) -> None:
    harness = _summary_harness(
        "parse_summary_line",
        "accumulate_summaries",
        "dependency_failures_explained",
        "install_step_ok",
    )
    transcript = "\n".join(
        (
            "Summary — 1 installed, 1 manual, 1 dependency failed",
            "✖ x  dependency failed — pi",
            "  rg: sha256 ✓",
            "○ pi  manual — see the setup steps in the log",
        )
    )
    result = _summary_run(
        harness,
        tmp_path,
        transcript,
        "accumulate_summaries $TRANSCRIPT; install_step_ok 1",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_manual_name_parser_reads_you_run_rows(tmp_path: Path) -> None:
    """A native handoff row (`manual — you run:`) counts as an explained blocker too."""
    harness = _summary_harness(
        "parse_summary_line",
        "accumulate_summaries",
        "dependency_failures_explained",
        "install_step_ok",
    )
    transcript = "\n".join(
        (
            "Summary — 2 installed, 2 manual, 1 dependency failed",
            "✖ mmdc  dependency failed — zsh",
            "○ zsh  manual — you run: `sudo dnf install zsh`",
            "○ pi  manual — see the setup steps in the log",
        )
    )
    result = _summary_run(
        harness,
        tmp_path,
        transcript,
        "accumulate_summaries $TRANSCRIPT; install_step_ok 1",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    names = (tmp_path / "manual-names").read_text(encoding="utf-8")
    assert names.splitlines() == ["zsh", "pi"]


def test_the_gate_reads_the_post_run_lines_setup_prints() -> None:
    setup = (ROOT / "setup.py").read_text(encoding="utf-8")
    accumulate = _function("accumulate_summaries")
    for prefix in (
        "PATH wiring could not be completed: ",
        "PATH audit could not be completed: ",
    ):
        assert prefix in setup
        assert prefix in accumulate


def test_every_install_step_uses_the_one_gate() -> None:
    text = _script_text()
    assert _function("install_step_ok", text)
    assert _function("cmd_pass1", text).count("install_step_ok ") == 1
    assert _function("cmd_pass2", text).count("install_step_ok ") == 2


def test_receipt_checks_are_wired_into_the_passes() -> None:
    """pass1 checks the receipt; pass2 proves it existed, then proves it is gone."""
    text = _script_text()
    pass1 = _function("cmd_pass1", text)
    pass2 = _function("cmd_pass2", text)
    assert 'assert_receipt_present "$categories" || return 1' in pass1
    ready = pass2.index("assert_receipt_ready_for_removal")
    rerun = pass2.index("TRACER_RERUN_OK")
    uninstall = pass2.index('run_pass2_step "--uninstall --yes"')
    removed = pass2.index("assert_receipt_removed")
    assert rerun < ready < uninstall < removed


@pytest.mark.parametrize(
    ("planted", "clean", "present"),
    [
        pytest.param([], True, [], id="no-claude-dir"),
        pytest.param([("dir", ".claude")], True, [], id="empty-claude-dir"),
        pytest.param([("dir", ".claude/gsd-core")], False, [".claude/gsd-core"], id="gsd-core-dir"),
        pytest.param(
            [("file", ".claude/.gsd-source")], False, [".claude/.gsd-source"], id="gsd-source-file"
        ),
        pytest.param(
            [("link", ".claude/gsd-core")], False, [".claude/gsd-core"], id="dangling-gsd-core-link"
        ),
        pytest.param(
            [("dir", ".claude/gsd-core"), ("file", ".claude/.gsd-source")],
            False,
            [".claude/gsd-core", ".claude/.gsd-source"],
            id="both",
        ),
        pytest.param(
            [("file", ".claude/gsd-file-manifest.json")],
            False,
            [".claude/gsd-file-manifest.json"],
            id="gsd-manifest",
        ),
        pytest.param([("dir", ".gsd")], False, [".gsd"], id="dot-gsd"),
    ],
)
def test_assert_gsd_absent_in_bash(
    tmp_path: Path, planted: list[tuple[str, str]], clean: bool, present: list[str]
) -> None:
    """No GSD tree in the tester's home passes; each planted one fails and is named."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    for kind, relative in planted:
        path = scratch / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "dir":
            path.mkdir()
        elif kind == "file":
            path.write_text("", encoding="utf-8")
        else:
            path.symlink_to(scratch / "missing")
    result = _run(_harness("assert_gsd_absent") + "\nassert_gsd_absent install\n", scratch)
    if clean:
        assert result.returncode == 0, result.stderr
        assert "TRACER_GSD_ABSENT_OK pass=install" in result.stdout
    else:
        assert result.returncode != 0
        assert "TRACER_GSD_ABSENT_OK" not in result.stdout
    for relative in present:
        assert f"TRACER_GSD_PRESENT path={scratch}/{relative}" in result.stdout
    assert result.stdout.count("TRACER_GSD_PRESENT") == len(present)


@pytest.mark.parametrize(
    "probe",
    ["exec_tester() { return 125; }", "exec_tester() { :; }", "exec_tester() { echo PRESENT; }"],
    ids=["exec-fails", "no-completion-token", "token-missing-after-output"],
)
def test_assert_gsd_absent_fails_when_the_probe_did_not_run(tmp_path: Path, probe: str) -> None:
    """C-10 (WR-09, PT-04): only a probe that ran to its token inside the container counts."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    script = _harness("assert_gsd_absent") + f"\n{probe}\nassert_gsd_absent install\n"
    result = _run(script, scratch)
    assert result.returncode != 0
    assert "TRACER_GSD_ABSENT_OK" not in result.stdout
    assert "TRACER_GSD_PROBE_FAILED pass=install" in result.stdout


def test_gsd_checks_are_wired_after_each_pass() -> None:
    """Install, uninstall and reinstall each prove the GSD tree is absent, in pass order."""
    text = _script_text()
    pass1 = _function("cmd_pass1", text)
    pass2 = _function("cmd_pass2", text)
    assert "assert_gsd_absent install || return 1" in pass1
    assert pass1.index('assert_receipt_present "$categories" || return 1') < pass1.index(
        "assert_gsd_absent install || return 1"
    )
    assert "assert_gsd_absent uninstall" in pass2
    assert "assert_gsd_absent reinstall" in pass2
    settled = pass2.index("settings_probe_revert")
    uninstall = pass2.index("assert_gsd_absent uninstall")
    reinstall_run = pass2.index('run_pass2_step "--all --yes"', uninstall)
    reinstalled = pass2.index("TRACER_REINSTALL_OK")
    reinstall = pass2.index("assert_gsd_absent reinstall")
    teardown = pass2.index("TRACER_CONTAINER_TEARDOWN_OK")
    assert settled < uninstall < reinstall_run < reinstalled < reinstall < teardown


def test_receipt_check_is_skipped_for_other_categories(tmp_path: Path) -> None:
    """A chunked run without the probe category skips; it never calls exec_tester."""
    applies = _function("receipt_check_applies")
    present = _function("assert_receipt_present")
    constants = "\n".join(f"{name}={_constant(name)}" for name in _CONSTANTS)
    cases = [
        ("", "yes"),
        ("core,data", "yes"),
        ("core, data", "yes"),
        ("core,shell", "no"),
        ("database", "no"),
    ]
    questions = "\n".join(
        f'if receipt_check_applies "{value}"; then echo "[{value}]=yes"; '
        f'else echo "[{value}]=no"; fi'
        for value, _answer in cases
    )
    calls = tmp_path / "calls"
    script = "\n".join(
        [
            constants,
            applies,
            present,
            f'exec_tester() {{ printf "%s\\n" "$1" >> {calls}; return 1; }}',
            questions,
            'assert_receipt_present "core,shell"',
        ]
    )
    result = _run(script, tmp_path / "home")
    assert result.returncode == 0, result.stderr
    for value, answer in cases:
        assert f"[{value}]={answer}" in result.stdout
    assert f"TRACER_RECEIPT_SKIPPED tool={PROBE_TOOL} category={PROBE_CATEGORY}" in result.stdout
    assert not calls.exists()


def _assign(name: str, value: str) -> str:
    """A shell assignment whose value survives spaces and shell metacharacters."""
    return f"{name}={shlex.quote(value)}"


def test_uv_stub_survives_a_spaced_interpreter_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout path with a space must not split the interpreter into words (G19)."""
    link = tmp_path / "py dir" / "python"
    link.parent.mkdir()
    link.symlink_to(sys.executable)
    monkeypatch.setattr(sys, "executable", str(link))
    result = _run(_uv_stub() + 'uv run python -c "print(42)"\n', tmp_path / "home")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "42"


def test_assignment_survives_a_spaced_workspace(tmp_path: Path) -> None:
    """A workspace path with a space stays one word in a generated assignment (G19)."""
    result = _run(
        _assign("TESTER_WORKSPACE", "/a b/c") + '\nprintf "%s" "$TESTER_WORKSPACE"\n',
        tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "/a b/c"


def _brew_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "linuxbrew" / "bin" / "brew"
    stub.parent.mkdir(parents=True)
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    return stub


def test_extracted_functions_never_name_the_host_brew() -> None:
    for name in ("assert_receipt_ready_for_removal", "run_setup_as_tester", "write_tester_path"):
        text = _function(name)
        assert "/home/linuxbrew" not in text
        assert "${BREW_BIN} shellenv" in text
    assert _constant("BREW_BIN") == "/home/linuxbrew/.linuxbrew/bin/brew"


def test_write_tester_path_hands_the_selected_brew_to_the_tester_shell(
    tmp_path: Path,
) -> None:
    scratch = tmp_path / "home"
    scratch.mkdir()
    stub = _brew_stub(tmp_path)
    script = "\n".join(
        [
            _assign("BREW_BIN", str(stub)),
            _function("write_tester_path"),
            'exec_tester() { HOME="$SCRATCH" bash -c "$1"; }',
            "write_tester_path",
            "write_tester_path",
        ]
    )
    result = _run(script, scratch)
    assert result.returncode == 0
    for rc in (scratch / ".bash_profile", scratch / ".bashrc"):
        lines = rc.read_text(encoding="utf-8").splitlines()
        assert lines.count(f'eval "$({stub} shellenv)"') == 1
        assert not any("$( shellenv)" in line for line in lines)
    assert result.stderr == ""


def _uv_stub() -> str:
    """Drop argv through `python` and run the rest with this interpreter."""
    exe = shlex.quote(sys.executable)
    return (
        "uv() {\n"
        "  local arg\n"
        '  while [[ $# -gt 0 && "$1" != python ]]; do shift; done\n'
        '  [[ "${1:-}" == python ]] || return 127\n'
        "  shift\n"
        # No exec: a probe that prints a closing marker after `uv run` must still reach it.
        f'  {exe} "$@"\n'
        "}\n"
        "export -f uv\n"
    )


def test_pre_uninstall_check_requires_binary_and_valid_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The parser, not a text match, decides the receipt is removable."""
    from installer import receipts
    from installer.receipts import Receipt, ReceiptArtifact, ReceiptMethod

    scratch = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: scratch)
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    binary = scratch / ".local" / "bin" / PROBE_TOOL
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"yq-bytes")
    target = scratch / "payload"
    target.write_bytes(b"payload")
    receipt = Receipt(
        tool=PROBE_TOOL,
        at="2026-10-16T12:00:00+00:00",
        method=ReceiptMethod(kind="github_release", key="a" * 64),
        package=None,
        artifacts=(
            ReceiptArtifact(
                path=target.resolve(), type="file", sha256="b" * 64, size=7, mtime_ns=1
            ),
        ),
        smoke=None,
        hooks={},
    )
    receipts.write(receipt)
    receipt_file = receipts.default_receipts_dir() / f"{PROBE_TOOL}.json"

    script = "\n".join(
        [
            _assign("TESTER_WORKSPACE", str(ROOT)),
            f"RECEIPT_PROBE_TOOL={_constant('RECEIPT_PROBE_TOOL')}",
            f"RECEIPT_PROBE_CATEGORY={_constant('RECEIPT_PROBE_CATEGORY')}",
            _assign("BREW_BIN", str(_brew_stub(tmp_path))),
            _function("assert_receipt_ready_for_removal"),
            'exec_tester() { HOME="$SCRATCH" bash -c "$1"; }',
            _uv_stub(),
            "assert_receipt_ready_for_removal",
        ]
    )
    ok = _run(script, scratch)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert f"TRACER_RECEIPT_PRE_UNINSTALL_OK tool={PROBE_TOOL}" in ok.stdout

    binary.unlink()
    no_binary = _run(script, scratch)
    assert no_binary.returncode != 0
    assert "TRACER_RECEIPT_PRE_UNINSTALL_MISSING" in no_binary.stdout
    assert f".local/bin/{PROBE_TOOL}" in no_binary.stdout

    binary.write_bytes(b"yq-bytes")
    receipt_file.unlink()
    no_receipt = _run(script, scratch)
    assert no_receipt.returncode != 0
    assert "TRACER_RECEIPT_PRE_UNINSTALL_MISSING" in no_receipt.stdout
    assert f"receipts/{PROBE_TOOL}.json" in no_receipt.stdout

    receipt_file.write_text("{\n", encoding="utf-8")
    brace = _run(script, scratch)
    assert brace.returncode != 0
    assert "TRACER_RECEIPT_PRE_UNINSTALL_MISSING" in brace.stdout
    assert "valid receipt" in brace.stdout

    receipt_file.write_text('{"v": 1, "tool": "yq"}\n', encoding="utf-8")
    strings_only = _run(script, scratch)
    assert strings_only.returncode != 0
    assert "TRACER_RECEIPT_PRE_UNINSTALL_MISSING" in strings_only.stdout
    assert "valid receipt" in strings_only.stdout


def _phase_harness(*names: str) -> str:
    """`_harness` plus the phase dir and repo root the leftover functions read."""
    return "\n".join(
        (
            'PHASE_DIR="$SCRATCH/phase"',
            f"REPO_ROOT={shlex.quote(str(ROOT))}",
            _harness(*names),
        )
    )


def _write_listing(path: Path, lines: Sequence[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return str(path)


def _leftovers(
    scratch: Path,
    *,
    before: Sequence[str],
    after: Sequence[str],
    allowed: Sequence[str] = (),
    must_clear: Sequence[str] = (),
    recorded: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    """new_leftovers over fixture listings: the pure check, no probes, no container."""
    files = [
        _write_listing(scratch / f"{name}.txt", lines)
        for name, lines in (
            ("before", before),
            ("after", after),
            ("allowed", allowed),
            ("must-clear", must_clear),
            ("recorded", recorded),
        )
    ]
    command = "new_leftovers " + " ".join(shlex.quote(path) for path in files)
    return _run(_harness("new_leftovers") + "\n" + command + "\n", scratch)


def _no_leftovers(
    scratch: Path,
    *,
    after: Sequence[str],
    before: Sequence[str] | None = (".bashrc",),
    allowed: Sequence[str] = (),
    must_clear: Sequence[str] = (),
    recorded: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    """assert_no_leftovers over fixture listings, the listing and both host probes stubbed."""
    phase = scratch / "phase"
    if before is not None:
        _write_listing(phase / "home-before.txt", before)
    _write_listing(phase / "receipt-paths.txt", recorded)
    listing = _write_listing(scratch / "listing.txt", after)
    allowed_file = _write_listing(scratch / "allowed.txt", allowed)
    must_file = _write_listing(scratch / "must-clear.txt", must_clear)
    stubs = (
        f"home_listing() {{ cat {shlex.quote(listing)}; }}\n"
        f"allowed_prefixes() {{ cat {shlex.quote(allowed_file)}; }}\n"
        f"must_clear_paths() {{ cat {shlex.quote(must_file)}; }}\n"
    )
    script = _phase_harness("assert_no_leftovers", "new_leftovers") + "\n"
    return _run(script + stubs + "assert_no_leftovers\n", scratch)


def test_a_planted_leftover_fails_the_check(tmp_path: Path) -> None:
    """A planted file fails the check, and the report names its top-most new root."""
    after = [".bashrc", ".local", ".local/share", ".local/share/planted-leftover"]
    pure = _leftovers(tmp_path / "pure", before=[".bashrc"], after=after)
    assert pure.returncode != 0
    assert pure.stdout.splitlines() == [".local"]
    report = _no_leftovers(tmp_path / "report", after=after)
    assert report.returncode != 0
    assert report.stdout.splitlines() == ["TRACER_LEFTOVER path=.local"]


def test_a_clean_run_passes(tmp_path: Path) -> None:
    """Declared config, the cache root and the parent of an allowed dir are not leftovers."""
    after = [
        ".bashrc",
        ".cache",
        ".cache/uv",
        ".cache/uv/x",
        ".config",
        ".config/gh",
        ".config/gh/hosts.yml",
    ]
    allowed = [".config/gh", ".cache"]
    pure = _leftovers(tmp_path / "pure", before=[".bashrc"], after=after, allowed=allowed)
    assert pure.returncode == 0, pure.stdout
    assert pure.stdout == ""
    report = _no_leftovers(tmp_path / "report", after=after, allowed=allowed)
    assert report.returncode == 0, report.stderr
    assert report.stdout.splitlines() == ["TRACER_LEFTOVER_OK"]


def test_leftovers_are_reported_as_roots(tmp_path: Path) -> None:
    result = _leftovers(tmp_path, before=(), after=[".foo", ".foo/a", ".foo/b/c"])
    assert result.returncode != 0
    assert result.stdout.splitlines() == [".foo"]


def test_a_leftover_install_path_under_a_harness_dir_fails(tmp_path: Path) -> None:
    """A declared install path under a marker dir fails; the emptied dir and config do not."""
    allowed = [".opencode", ".local/share/cursor-agent"]
    must_clear = [".opencode/bin/opencode", ".local/share/cursor-agent"]
    binary = _leftovers(
        tmp_path / "binary",
        before=[".bashrc"],
        after=[".bashrc", ".opencode/bin", ".opencode/bin/opencode"],
        allowed=allowed,
        must_clear=must_clear,
    )
    assert binary.returncode != 0
    assert binary.stdout.splitlines() == [".opencode/bin/opencode"]
    tree = _leftovers(
        tmp_path / "tree",
        before=[".bashrc"],
        after=[
            ".bashrc",
            ".local/share/cursor-agent",
            ".local/share/cursor-agent/versions",
            ".local/share/cursor-agent/versions/x",
        ],
        allowed=allowed,
        must_clear=must_clear,
    )
    assert tree.returncode != 0
    assert tree.stdout.splitlines() == [".local/share/cursor-agent"]
    emptied = _leftovers(
        tmp_path / "emptied",
        before=[".bashrc"],
        after=[".bashrc", ".opencode/bin", ".opencode/opencode.json"],
        allowed=allowed,
        must_clear=must_clear,
    )
    assert emptied.returncode == 0, emptied.stdout
    assert emptied.stdout == ""


def test_an_allowlist_entry_never_exempts_a_must_clear_path(tmp_path: Path) -> None:
    result = _leftovers(
        tmp_path,
        before=[".bashrc"],
        after=[".bashrc", ".opencode/bin", ".opencode/bin/opencode"],
        allowed=[".opencode/bin"],
        must_clear=[".opencode/bin/opencode"],
    )
    assert result.returncode != 0
    assert result.stdout.splitlines() == [".opencode/bin/opencode"]


def test_a_missing_baseline_fails(tmp_path: Path) -> None:
    result = _no_leftovers(tmp_path, before=None, after=[".bashrc"])
    assert result.returncode != 0
    assert result.stdout.splitlines() == ["TRACER_LEFTOVER_NO_BASELINE"]


def test_a_receipt_path_in_the_baseline_is_still_checked(tmp_path: Path) -> None:
    """A recorded path is a leftover even when the baseline holds it; a declared-only one is not."""
    listing = [".local", ".local/bin", ".local/bin/t"]
    recorded = _leftovers(
        tmp_path / "recorded", before=listing, after=listing, recorded=[".local/bin/t"]
    )
    assert recorded.returncode != 0
    assert recorded.stdout.splitlines() == [".local/bin/t"]
    declared = _leftovers(
        tmp_path / "declared", before=listing, after=listing, must_clear=[".local/bin/t"]
    )
    assert declared.returncode == 0
    assert declared.stdout == ""


def test_a_left_manager_receipt_fails_the_check(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    phase = scratch / "phase"
    receipts = scratch / ".local" / "state" / "tools-installer" / "receipts"
    phase.mkdir(parents=True)
    receipts.mkdir(parents=True)
    (phase / "removable-receipts.txt").write_text("gh\nuv\n", encoding="utf-8")
    (receipts / "gh.json").write_text("{}\n", encoding="utf-8")
    script = _phase_harness("assert_removed_receipts_gone") + "\nassert_removed_receipts_gone\n"
    left = _run(script, scratch)
    assert left.returncode != 0
    assert "TRACER_RECEIPT_LEFT id=gh" in left.stdout
    (receipts / "gh.json").unlink()
    gone = _run(script, scratch)
    assert gone.returncode == 0, gone.stdout
    assert "TRACER_RECEIPTS_GONE_OK count=2" in gone.stdout
    (phase / "removable-receipts.txt").unlink()
    unknown = _run(script, scratch)
    assert unknown.returncode != 0
    assert "TRACER_RECEIPTS_UNKNOWN" in unknown.stdout


def test_the_allowlist_gives_every_entry_a_reason() -> None:
    lines = (ROOT / "scripts" / "e2e-residue-allowlist.txt").read_text(encoding="utf-8")
    entries = [
        line for line in lines.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    assert entries
    for line in entries:
        assert re.match(r"^\S+  # \S", line), line


def test_the_leftover_check_is_wired_after_the_uninstall_step() -> None:
    text = _script_text()
    bootstrap = _function("cmd_bootstrap", text)
    assert bootstrap.index("home_listing") < bootstrap.index("print_harness_ready")
    pass2 = _function("cmd_pass2", text)
    uninstall = pass2.index('run_pass2_step "--uninstall --yes"')
    assert pass2.index("receipt_paths") < uninstall
    done = pass2.index("TRACER_UNINSTALL_OK")
    reinstall = pass2.rindex('run_pass2_step "--all --yes"')
    for check in ("assert_removed_receipts_gone", "assert_no_leftovers"):
        assert done < pass2.index(check) < reinstall


def test_home_listing_prunes_the_workspace(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    (scratch / "workspace" / ".venv").mkdir(parents=True)
    (scratch / ".config" / "gh").mkdir(parents=True)
    (scratch / ".config" / "gh" / "hosts.yml").write_text("", encoding="utf-8")
    (scratch / ".bashrc").write_text("", encoding="utf-8")
    result = _run(_harness("home_listing") + "\nhome_listing\n", scratch)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        ".bashrc",
        ".config",
        ".config/gh",
        ".config/gh/hosts.yml",
    ]


def test_home_listing_skips_empty_directories(tmp_path: Path) -> None:
    """An emptied directory holds no artifact, so it is not listed; a file beside it is."""
    scratch = tmp_path / "home"
    (scratch / ".local" / "bin").mkdir(parents=True)
    (scratch / ".local" / "bin" / "tool").write_text("", encoding="utf-8")
    (scratch / ".local" / "opt").mkdir()
    result = _run(_harness("home_listing") + "\nhome_listing\n", scratch)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [".local", ".local/bin", ".local/bin/tool"]


def test_receipt_paths_records_the_home_relative_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only artifacts under HOME are recorded, relative to it; outside paths are dropped."""
    from installer import receipts
    from installer.receipts import Receipt, ReceiptArtifact, ReceiptMethod

    scratch = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: scratch)
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    inside = scratch / "payload"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"payload")
    outside = tmp_path / "elsewhere"
    outside.write_bytes(b"x")
    artifacts = tuple(
        ReceiptArtifact(path=path.resolve(), type="file", sha256="b" * 64, size=7, mtime_ns=1)
        for path in (inside, outside)
    )
    receipts.write(
        Receipt(
            tool=PROBE_TOOL,
            at="2026-10-16T12:00:00+00:00",
            method=ReceiptMethod(kind="github_release", key="a" * 64),
            package=None,
            artifacts=artifacts,
            smoke=None,
            hooks={},
        )
    )
    phase = scratch / "phase"
    phase.mkdir()
    script = "\n".join(
        [
            _phase_harness("receipt_paths"),
            _assign("TESTER_WORKSPACE", str(ROOT)),
            _assign("BREW_BIN", str(_brew_stub(tmp_path))),
            _uv_stub(),
            "receipt_paths",
        ]
    )
    result = _run(script, scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    recorded = (phase / "receipt-paths.txt").read_text(encoding="utf-8")
    assert recorded.splitlines() == ["payload"]
    assert (phase / "removable-receipts.txt").exists()


def test_the_host_probe_lists_config_harness_and_script_paths(tmp_path: Path) -> None:
    """The registry's config dirs, harness markers and script paths reach the two lists."""
    script = "\n".join(
        [
            _phase_harness("allowed_prefixes", "must_clear_paths", "registry_probe"),
            _uv_stub(),
            "allowed_prefixes",
            "printf '%s\\n' ---",
            "must_clear_paths",
        ]
    )
    result = _run(script, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    allowed, _sep, must_clear = result.stdout.partition("---\n")
    allowed_lines = allowed.splitlines()
    clear_lines = must_clear.splitlines()
    for entry in (".config/uv", ".claude", ".local/state/tools-installer", ".local/share/uv"):
        assert entry in allowed_lines, result.stderr
    for entry in (".opencode/bin/opencode", ".local/share/claude", ".local/bin/claude"):
        assert entry in clear_lines, result.stderr


def test_pre_uninstall_check_survives_a_spaced_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workspace path with a space stays one word for the nested cd (RR-06)."""
    from installer import receipts
    from installer.receipts import Receipt, ReceiptArtifact, ReceiptMethod

    scratch = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: scratch)
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    binary = scratch / ".local" / "bin" / PROBE_TOOL
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"yq-bytes")
    target = scratch / "payload"
    target.write_bytes(b"payload")
    receipt = Receipt(
        tool=PROBE_TOOL,
        at="2026-10-16T12:00:00+00:00",
        method=ReceiptMethod(kind="github_release", key="a" * 64),
        package=None,
        artifacts=(
            ReceiptArtifact(
                path=target.resolve(), type="file", sha256="b" * 64, size=7, mtime_ns=1
            ),
        ),
        smoke=None,
        hooks={},
    )
    receipts.write(receipt)
    workspace = tmp_path / "work space"
    workspace.symlink_to(ROOT, target_is_directory=True)
    script = "\n".join(
        [
            _assign("TESTER_WORKSPACE", str(workspace)),
            f"RECEIPT_PROBE_TOOL={_constant('RECEIPT_PROBE_TOOL')}",
            f"RECEIPT_PROBE_CATEGORY={_constant('RECEIPT_PROBE_CATEGORY')}",
            _assign("BREW_BIN", str(_brew_stub(tmp_path))),
            _function("assert_receipt_ready_for_removal"),
            'exec_tester() { HOME="$SCRATCH" bash -c "$1"; }',
            _uv_stub(),
            "assert_receipt_ready_for_removal",
        ]
    )
    ok = _run(script, scratch)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert f"TRACER_RECEIPT_PRE_UNINSTALL_OK tool={PROBE_TOOL}" in ok.stdout


def test_every_array_expansion_survives_bash_3_2_under_set_u() -> None:
    """Review PT-07: bash < 4.4 aborts on `"${arr[@]}"` of an empty array under `set -u`,
    and a macOS host's /bin/bash is 3.2; every expansion uses the `${arr[@]+...}` guard."""
    text = SCRIPT.read_text(encoding="utf-8")
    bare = re.findall(r'"\$\{(\w+)\[@\]\}"', text)
    guarded = re.findall(r'\$\{(\w+)\[@\]\+"\$\{\1\[@\]\}"\}', text)
    assert sorted(bare) == sorted(guarded)


def test_hook_probe_after_reports_a_file_still_naming_codegraph(tmp_path: Path) -> None:
    """A recorded file that still names codegraph after the uninstall fails the probe."""
    scratch = tmp_path / "home"
    phase = scratch / "phase"
    phase.mkdir(parents=True)
    _write_listing(phase / "hook-hosts.txt", ["claude", "codex"])
    _write_listing(
        phase / "hook-files.txt", [".claude.json", ".codex/config.toml", ".claude/CLAUDE.md"]
    )
    (scratch / ".claude.json").write_text('{"mcpServers": {"codegraph": {}}}', encoding="utf-8")
    (scratch / ".codex").mkdir()
    (scratch / ".codex" / "config.toml").write_text("model = 'gpt'\n", encoding="utf-8")
    script = _phase_harness("hook_probe_after") + "\nhook_probe_after\n"
    left = _run(script, scratch)
    assert left.returncode != 0
    assert left.stdout.splitlines() == ["TRACER_HOOK_LEFT path=.claude.json"]
    (scratch / ".claude.json").write_text("{}\n", encoding="utf-8")
    clean = _run(script, scratch)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.splitlines() == ["TRACER_HOOKS_UNREGISTERED_OK count=3"]
    _write_listing(phase / "hook-hosts.txt", [])
    nothing = _run(script, scratch)
    assert nothing.returncode != 0  # nothing registered is a failure, never a skip (CR-13)
    assert nothing.stdout.splitlines() == ["TRACER_HOOKS_NOT_RECORDED"]


def test_hook_probe_before_requires_config_for_recorded_hosts(tmp_path: Path) -> None:
    """Recorded hosts need a config file on disk; no receipt or no host fails the probe."""
    scratch = tmp_path / "home"
    phase = scratch / "phase"
    phase.mkdir(parents=True)

    def probe(*reader_lines: str) -> subprocess.CompletedProcess[str]:
        stub = _assign("STUB_OUTPUT", "\n".join(reader_lines))
        override = 'exec_tester() { printf "%s\\n" "$STUB_OUTPUT"; }'
        return _run(
            "\n".join([_phase_harness("hook_probe_before"), stub, override, "hook_probe_before"]),
            scratch,
        )

    none = probe("N")
    assert none.returncode != 0
    assert none.stdout.splitlines() == ["TRACER_HOOKS_NOT_RECORDED reason=no-receipt"]
    orphan = probe("H claude")
    assert orphan.returncode != 0
    assert orphan.stdout.splitlines() == ["TRACER_HOOK_FILES_MISSING hosts=claude"]
    found = probe("H claude", "F .claude.json")
    assert found.returncode == 0, found.stderr
    assert found.stdout.splitlines() == ["TRACER_HOOKS_RECORDED hosts=claude files=1"]
    assert (phase / "hook-hosts.txt").read_text(encoding="utf-8") == "claude\n"
    assert (phase / "hook-files.txt").read_text(encoding="utf-8") == ".claude.json\n"
    no_host = probe("F .claude.json")
    assert no_host.returncode != 0
    assert no_host.stdout.splitlines() == ["TRACER_HOOKS_NOT_RECORDED reason=no-hosts"]


def test_the_hook_probes_are_wired_around_the_uninstall_step() -> None:
    pass2 = _function("cmd_pass2")
    uninstall = pass2.index('run_pass2_step "--uninstall --yes"')
    reinstall = pass2.rindex('run_pass2_step "--all --yes"')
    assert pass2.index("receipt_paths") < pass2.index("hook_probe_before") < uninstall
    assert pass2.index("assert_no_leftovers") < pass2.index("hook_probe_after") < reinstall


def test_hook_probe_before_reads_the_real_codegraph_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader and the grep run for real: a recorded host and its config file are found."""
    from installer import receipts
    from installer.receipts import Receipt, ReceiptMethod

    scratch = tmp_path / "home"
    scratch.mkdir()
    monkeypatch.setattr(Path, "home", lambda: scratch)
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    receipts.write(
        Receipt(
            tool="codegraph",
            at="2026-10-16T12:00:00+00:00",
            method=ReceiptMethod(kind="github_release", key="a" * 64),
            package=None,
            artifacts=(),
            smoke=None,
            hooks={"codegraph-mcp-register": ("claude",)},
        )
    )
    (scratch / ".claude.json").write_text('{"mcpServers": {"codegraph": {}}}', encoding="utf-8")
    # The Claude CLI's own backup of .claude.json is not the installer's file to clean.
    (scratch / ".claude" / "backups").mkdir(parents=True)
    backup = scratch / ".claude" / "backups" / ".claude.json.backup.1"
    backup.write_text('{"mcpServers": {"codegraph": {}}}', encoding="utf-8")
    (scratch / "phase").mkdir()
    script = "\n".join(
        [
            f"export PYTHONPATH={shlex.quote(str(ROOT))}",
            _phase_harness("hook_probe_before"),
            _assign("TESTER_WORKSPACE", str(tmp_path)),
            _assign("BREW_BIN", str(_brew_stub(tmp_path))),
            _uv_stub(),
            "hook_probe_before",
        ]
    )
    result = _run(script, scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["TRACER_HOOKS_RECORDED hosts=claude files=1"]
    assert (scratch / "phase" / "hook-files.txt").read_text(encoding="utf-8") == ".claude.json\n"


_REQUIRED_TUNED = ("claude", "codex", "copilot")
_VERSION_LINE = "GitHub Copilot CLI 1.0.107."


def _tuned_keys(agents: Sequence[str]) -> int:
    """How many keys the installer writes for these agents, from its own tables."""
    from installer import agent_settings

    return sum(
        len(agent_settings.setting_keys(agent, group, "linux"))
        for agent in agents
        for group in agent_settings.TUNING_GROUPS[agent]
    )


class _TunedHome:
    """A scratch HOME and workspace whose agent settings the installer's own writer filled."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.scratch = tmp_path / "home"
        self.workspace = tmp_path / "workspace"
        self.path = tmp_path / "path"
        for directory in (self.scratch, self.workspace, self.path):
            directory.mkdir(parents=True)
        (self.path / "bash").symlink_to(_bash())
        monkeypatch.setattr(Path, "home", lambda: self.scratch)
        self.script = "\n".join(
            [
                f"export PYTHONPATH={shlex.quote(str(ROOT))}",
                _harness("settings_probe_installed", "settings_probe_revert"),
                _assign("TESTER_WORKSPACE", str(self.workspace)),
                _assign("BREW_BIN", str(_brew_stub(tmp_path))),
                _uv_stub(),
            ]
        )

    def plant(self, command: str, *, version_exit: int = 0) -> Path:
        """A fake agent command under ~/.local/bin; copilot's answers --version."""
        stub = self.scratch / ".local" / "bin" / command
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(
            f'#!/bin/sh\necho "{_VERSION_LINE}"\nexit {version_exit}\n', encoding="utf-8"
        )
        stub.chmod(0o755)
        return stub

    def tune(self, agent: str, groups: Sequence[str] | None = None) -> None:
        from installer import agent_settings

        for group in groups or agent_settings.TUNING_GROUPS[agent]:
            result = agent_settings.apply_setting(
                agent, group, home=self.scratch, platform_os="linux"
            )
            assert result.refused is None

    def run(self, function: str) -> subprocess.CompletedProcess[str]:
        return _run(f"{self.script}\n{function}\n", self.scratch, path=str(self.path))


def _tuned_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agents: Sequence[str] = _REQUIRED_TUNED,
    *,
    version_exit: int = 0,
) -> _TunedHome:
    home = _TunedHome(tmp_path, monkeypatch)
    for agent in agents:
        home.plant(agent, version_exit=version_exit)
        home.tune(agent)
    return home


def test_settings_probe_installed_passes_when_install_wrote_every_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _tuned_home(tmp_path, monkeypatch)
    result = home.run("settings_probe_installed")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        f"TRACER_SETTINGS_INSTALLED_OK agents=3 keys={_tuned_keys(_REQUIRED_TUNED)}",
        "TRACER_COPILOT_VERSION_OK",
    ]


def test_settings_probe_installed_flags_a_missing_key_agent_or_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_key = _tuned_home(tmp_path / "key", monkeypatch, ("codex", "copilot"))
    missing_key.plant("claude")
    missing_key.tune("claude", ("auto-approve",))
    keyed = missing_key.run("settings_probe_installed")
    assert keyed.returncode != 0
    assert "TRACER_SETTINGS_INSTALLED_MISSING agent=claude key=attribution.commit" in keyed.stdout
    assert "TRACER_SETTINGS_INSTALLED_OK" not in keyed.stdout

    for absent in _REQUIRED_TUNED:
        others = tuple(agent for agent in _REQUIRED_TUNED if agent != absent)
        gone = _tuned_home(tmp_path / f"no-{absent}", monkeypatch, others)
        result = gone.run("settings_probe_installed")
        assert result.returncode != 0, absent
        assert f"TRACER_SETTINGS_AGENT_MISSING agent={absent}" in result.stdout
        assert "TRACER_SETTINGS_INSTALLED_OK" not in result.stdout

    failing = _tuned_home(tmp_path / "version", monkeypatch, version_exit=3)
    result = failing.run("settings_probe_installed")
    assert result.returncode != 0
    assert "TRACER_COPILOT_VERSION_FAILED" in result.stdout
    assert "TRACER_COPILOT_VERSION_OK" not in result.stdout


def test_settings_probe_installed_persists_the_checked_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review R1-04: the revert probe needs the agents the install probe saw, not a PATH lookup.
    It also needs which settings files the installer created (23.2 e2e #6)."""
    from installer import agent_settings

    home = _tuned_home(tmp_path, monkeypatch)
    assert home.run("settings_probe_installed").returncode == 0
    persisted = json.loads((home.workspace / ".e2e-tuned-agents.json").read_text(encoding="utf-8"))
    assert sorted(persisted["agents"]) == sorted(_REQUIRED_TUNED)
    # Each tuned file was absent before the tuning, so the ledger lists it as installer-created.
    assert persisted["created"] == {
        agent: [str(agent_settings.settings_file(agent, home=home.scratch, platform_os="linux"))]
        for agent in persisted["agents"]
    }


def test_settings_probe_revert_flags_a_key_ledger_or_copilot_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import agent_settings

    home = _tuned_home(tmp_path, monkeypatch)
    assert home.run("settings_probe_installed").returncode == 0
    link = home.scratch / ".local" / "bin" / "copilot"

    left = home.run("settings_probe_revert")
    assert left.returncode != 0
    assert "TRACER_SETTINGS_REVERT_DIFF agent=claude key=permissions.defaultMode" in left.stdout
    assert "TRACER_SETTINGS_REVERT_DIFF agent=copilot key=defaultPermissionMode" in left.stdout
    assert "TRACER_SETTINGS_LEDGER_LEFT agent=codex" in left.stdout
    assert "TRACER_COPILOT_LEFT path=.local/bin/copilot" in left.stdout
    assert "TRACER_SETTINGS_REVERT_OK" not in left.stdout

    for agent in _REQUIRED_TUNED:
        for result in agent_settings.revert_agent(agent, home=home.scratch, platform_os="linux"):
            assert result.refused is None
    still_linked = home.run("settings_probe_revert")
    assert still_linked.returncode != 0
    assert still_linked.stdout.splitlines() == ["TRACER_COPILOT_LEFT path=.local/bin/copilot"]

    link.unlink()
    clean = home.run("settings_probe_revert")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.splitlines() == [
        f"TRACER_SETTINGS_REVERT_OK keys={_tuned_keys(_REQUIRED_TUNED)}"
    ]


def test_settings_probe_revert_flags_a_settings_file_that_outlived_the_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-09: the container starts with no settings files, so a file left behind (even a bare
    `{}`) means the revert did not return it byte-identical or delete it."""
    from installer import agent_settings

    home = _tuned_home(tmp_path, monkeypatch)
    assert home.run("settings_probe_installed").returncode == 0
    for agent in _REQUIRED_TUNED:
        agent_settings.revert_agent(agent, home=home.scratch, platform_os="linux")
    (home.scratch / ".local" / "bin" / "copilot").unlink()
    leftover = agent_settings.settings_file("claude", home=home.scratch, platform_os="linux")
    assert not leftover.parent.exists()  # the revert removed the directory it created
    leftover.parent.mkdir()
    leftover.write_text("{\n}\n", encoding="utf-8")

    result = home.run("settings_probe_revert")

    assert result.returncode != 0
    assert result.stdout.splitlines() == ["TRACER_SETTINGS_FILE_LEFT agent=claude residue={}"]


def test_settings_probe_revert_lets_a_file_the_install_did_not_create_stay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """23.2 e2e #6: another owner (the agent's own installer, hook registration) made the file
    first, so it outlives the uninstall once none of our keys are left in it."""
    from installer import agent_settings

    home = _TunedHome(tmp_path, monkeypatch)
    foreign = agent_settings.settings_file("claude", home=home.scratch, platform_os="linux")
    foreign.parent.mkdir(parents=True)
    foreign.write_text("{}\n", encoding="utf-8")
    for agent in _REQUIRED_TUNED:
        home.plant(agent)
        home.tune(agent)
    assert home.run("settings_probe_installed").returncode == 0
    persisted = json.loads((home.workspace / ".e2e-tuned-agents.json").read_text(encoding="utf-8"))
    assert persisted["created"]["claude"] == []
    for agent in _REQUIRED_TUNED:
        agent_settings.revert_agent(agent, home=home.scratch, platform_os="linux")
    (home.scratch / ".local" / "bin" / "copilot").unlink()
    assert foreign.exists()

    result = home.run("settings_probe_revert")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        f"TRACER_SETTINGS_REVERT_OK keys={_tuned_keys(_REQUIRED_TUNED)}"
    ]


def test_settings_probe_revert_reads_the_persisted_agents_not_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review R1-04: the uninstall removed copilot's link, yet its leftover key is still found."""
    home = _tuned_home(tmp_path, monkeypatch, ("copilot",))
    assert home.run("settings_probe_installed").returncode != 0  # claude and codex are absent
    (home.scratch / ".local" / "bin" / "copilot").unlink()
    persisted = home.workspace / ".e2e-tuned-agents.json"
    assert json.loads(persisted.read_text(encoding="utf-8"))["agents"] == ["copilot"]
    left = home.run("settings_probe_revert")
    assert left.returncode != 0
    assert "TRACER_SETTINGS_REVERT_DIFF agent=copilot key=defaultPermissionMode" in left.stdout

    persisted.unlink()
    unreadable = home.run("settings_probe_revert")
    assert unreadable.returncode != 0
    assert unreadable.stdout.splitlines() == ["TRACER_SETTINGS_REVERT_PROBE_FAILED"]


def test_settings_probe_revert_accepts_a_key_restored_to_the_cli_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cursor-agent's revert restores the CLI's own default instead of removing the key."""
    from installer import agent_settings

    home = _tuned_home(tmp_path, monkeypatch, ())
    path = agent_settings.settings_file("cursor-agent", home=home.scratch, platform_os="linux")
    (home.workspace / ".e2e-tuned-agents.json").write_text(
        json.dumps({"agents": ["cursor-agent"], "created": {"cursor-agent": [str(path)]}}),
        encoding="utf-8",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"attribution": {"attributeCommitsToAgent": true, "attributePRsToAgent": true}}',
        encoding="utf-8",
    )
    restored = home.run("settings_probe_revert")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert restored.stdout.splitlines() == [
        f"TRACER_SETTINGS_REVERT_OK keys={_tuned_keys(['cursor-agent'])}"
    ]
    path.write_text('{"attribution": {"attributeCommitsToAgent": false}}', encoding="utf-8")
    kept = home.run("settings_probe_revert")
    assert kept.returncode != 0
    assert kept.stdout.splitlines() == [
        "TRACER_SETTINGS_REVERT_DIFF agent=cursor-agent key=attribution.attributeCommitsToAgent",
        "TRACER_SETTINGS_FILE_LEFT agent=cursor-agent"
        ' residue={"attribution":{"attributeCommitsToAgent":false}}',
    ]


def test_the_settings_probes_are_wired_around_the_uninstall_step() -> None:
    pass2 = _function("cmd_pass2")
    uninstall = pass2.index('run_pass2_step "--uninstall --yes"')
    reinstall = pass2.rindex('run_pass2_step "--all --yes"')
    assert pass2.index("hook_probe_before") < pass2.index("settings_probe_installed") < uninstall
    assert pass2.index("hook_probe_after") < pass2.index("settings_probe_revert") < reinstall
    assert "settings_probe_write" not in _script_text()
    assert "TESTER_WORKSPACE" in _function("settings_probe_installed")


# --- Phase 24-04: one table, three distros ---------------------------------

_DISTROS = ("fedora", "debian", "arch")
_IMAGES = {
    "fedora": "fedora:latest",
    "debian": "docker.io/library/debian:trixie",
    "arch": "docker.io/library/archlinux:latest",
}
_RELEASE_FIXTURES = {
    "fedora": ("/etc/fedora-release", "Fedora release 44", "Fedora release 44"),
    "debian": ("/etc/debian_version", "13.1", "13.1"),
    "arch": ("/etc/os-release", 'NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"', "Arch Linux"),
}


def _distro_stub_ct() -> str:
    """A `ct` that records its argv and answers the release files with fixture text."""
    answers = "\n".join(
        f'    "exec $CONTAINER_NAME cat {path}") printf "%s\\n" {shlex.quote(text)} ;;'
        for path, text, _expected in _RELEASE_FIXTURES.values()
    )
    return (
        "ct() {\n"
        '  printf "%s\\n" "$*" >> "$CALLS"\n'
        '  case "$*" in\n'
        f"{answers}\n"
        '    "exec $CONTAINER_NAME id tester") return 1 ;;\n'
        '    "ps "*) return 0 ;;\n'
        "  esac\n"
        "}\n"
    )


def _distro_harness() -> str:
    """The distro table and the ct-bound functions, with `ct` recording and nothing else real."""
    text = _script_text()
    names = (
        "usage",
        "select_distro",
        "exec_root",
        "exec_tester",
        "container_running",
        "container_exists",
        "start_container",
        "distro_release_record",
        "install_root_prereqs",
        "create_tester",
        "ensure_phase_dir",
        "main",
        "cmd_all",
    )
    parts = [
        'REPO_ROOT="$SCRATCH/repo"',
        *(f"IMAGE_{name.upper()}={_constant(f'IMAGE_{name.upper()}', text)}" for name in _DISTROS),
        *(f"{name}={_constant(name, text)}" for name in ("TESTER_USER", "TESTER_HOME")),
        'TESTER_WORKSPACE="$TESTER_HOME/workspace"',
        _assign("BREW_BIN", "/nonexistent/brew"),
        "set -euo pipefail",
        *(_function(name, text) for name in names),
        _distro_stub_ct(),
        "select_distro fedora",
    ]
    return "\n".join(parts)


def _calls(scratch: Path) -> list[str]:
    path = scratch / "calls"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


_STAGE_STUBS = (
    'report() { printf "%s %s %s %s %s\\n" "$1" "$DISTRO" "$IMAGE" "$CONTAINER_NAME" '
    '"$PHASE_DIR"; }\n'
    'cmd_bootstrap() { report BOOT; mkdir -p "$PHASE_DIR"; }\n'
    "cmd_pass1() { report PASS1; }\n"
    'cmd_pass2() { report PASS2; printf "p2\\n" > "$PHASE_DIR/pass2-transcript.log"; }\n'
)


def test_distro_is_threaded_through_every_command(tmp_path: Path) -> None:
    """R1-20: `main all --distro debian` selects one table entry and every stage reads it."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    result = _run(_distro_harness() + "\n" + _STAGE_STUBS + "main all --distro debian\n", scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    phase = str(scratch / "repo" / ".e2e-artifacts" / "container-debian")
    for stage in ("BOOT", "PASS1", "PASS2"):
        assert (
            f"{stage} debian docker.io/library/debian:trixie tools-installer-e2e-debian {phase}"
            in result.stdout
        )

    for distro in _DISTROS:
        direct = tmp_path / f"direct-{distro}"
        direct.mkdir()
        script = (
            _distro_harness() + f"\nselect_distro {distro}\nstart_container\ninstall_root_prereqs\n"
            "create_tester\ndistro_release_record\n"
        )
        run = _run(script, direct)
        assert run.returncode == 0, run.stdout + run.stderr
        name = f"tools-installer-e2e-{distro}"
        assert f"run -d --name {name} {_IMAGES[distro]} sleep infinity" in _calls(direct)
        expected = _RELEASE_FIXTURES[distro][2]
        assert f"DISTRO_RELEASE={distro}:{expected}" in run.stdout

    debian_calls = _calls(tmp_path / "direct-debian")
    assert any(
        "env DEBIAN_FRONTEND=noninteractive apt-get install" in call and " npm" in call
        for call in debian_calls
    )
    assert any(call.endswith("apt-get update") for call in debian_calls)
    arch_calls = _calls(tmp_path / "direct-arch")
    assert any("pacman -Syu --noconfirm --needed" in call and " npm" in call for call in arch_calls)
    fedora_calls = _calls(tmp_path / "direct-fedora")
    assert any("dnf install -y" in call for call in fedora_calls)


def test_unknown_distro_exits_2(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    scratch.mkdir()
    result = _run(_distro_harness() + "\n" + _STAGE_STUBS + "main all --distro gentoo\n", scratch)
    assert result.returncode == 2
    assert "unknown distro: gentoo" in result.stderr
    assert "Usage: container-e2e-verify.sh" in result.stderr
    assert "BOOT" not in result.stdout


def test_distro_artifact_dirs_differ(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    scratch.mkdir()
    script = _distro_harness() + (
        '\nselect_distro debian; printf "%s\\n" "$PHASE_DIR"\n'
        'select_distro fedora; printf "%s\\n" "$PHASE_DIR"\n'
        'select_distro arch; printf "%s\\n" "$PHASE_DIR" "$CONTAINER_NAME"\n'
    )
    result = _run(script, scratch)
    assert result.returncode == 0, result.stderr
    debian, fedora, arch, arch_name = result.stdout.splitlines()
    assert debian.endswith("/.e2e-artifacts/container-debian")
    assert fedora.endswith("/.e2e-artifacts/container-fedora")
    assert arch.endswith("/.e2e-artifacts/container-arch")
    assert arch_name == "tools-installer-e2e-arch"
    assert len({debian, fedora, arch}) == 3


@pytest.mark.parametrize("distro", _DISTROS)
def test_every_distro_prereq_line_names_the_shared_set(tmp_path: Path, distro: str) -> None:
    """R1-19: the shared set on every distro, and never zsh."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    result = _run(_distro_harness() + f"\nselect_distro {distro}\ninstall_root_prereqs\n", scratch)
    assert result.returncode == 0, result.stderr
    installed = " ".join(_calls(scratch)).split()
    # Arch names Python's package `python`; the other two ship `python3`.
    python = "python" if distro == "arch" else "python3"
    for word in ("sudo", "git", python, "nodejs", "chromium", "curl", "file"):
        assert word in installed, (distro, word)
    assert "zsh" not in installed


@pytest.mark.parametrize("distro", _DISTROS)
def test_tester_is_created_with_bash(tmp_path: Path, distro: str) -> None:
    """R1-03: Debian's useradd defaults to /bin/sh, where the probes' `[[` and pipefail fail."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    result = _run(_distro_harness() + f"\nselect_distro {distro}\ncreate_tester\n", scratch)
    assert result.returncode == 0, result.stderr
    assert f"exec tools-installer-e2e-{distro} useradd -m -s /bin/bash tester" in _calls(scratch)


def test_harness_never_runs_setup_outside_a_container() -> None:
    """Every `setup.py` invocation sits inside the one tester-exec helper, never on the host."""
    text = _script_text()
    runner = _function("run_setup_as_tester", text)
    code = text.replace(_function("usage", text), "")
    invoking = re.compile(r"\b(uv run|python3?)\b.*\bsetup\.py\b|\./setup\.py")
    for line in code.splitlines():
        if invoking.search(line) and not line.lstrip().startswith("#"):
            assert line in runner, line


# --- Phase 24-04 task 2: the rerun gate, the blocked listing, the herdr probes ----------

_UNEXPECTED_KINDS = {
    "installed": "installed",
    "updated": "updated",
    "repaired": "repaired",
    "reconfigured": "reconfigured",
    "reinstalled": "reinstalled",
    "failed": "failed",
    "mismatched": "checksum mismatch",
    "dependency_failed": "dependency failed",
}
_MANUAL_PI = "○ pi  manual — see the setup steps in the log"
_MANUAL_ZSH = "○ zsh  manual — you run: `sudo dnf install zsh`"


def _rerun_harness() -> str:
    names = (
        "parse_summary_line",
        "accumulate_summaries",
        "dependency_failures_explained",
        "install_step_ok",
        "rerun_step_ok",
    )
    return 'PHASE_DIR="$SCRATCH/phase"\n' + _summary_harness(*names)


def _rerun(
    scratch: Path, transcript: str, baseline: Sequence[str] | None, command: str | None = None
) -> subprocess.CompletedProcess[str]:
    phase = scratch / "phase"
    phase.mkdir(parents=True, exist_ok=True)
    if baseline is not None:
        _write_listing(phase / "pass1-manual.txt", baseline)
    return _summary_run(
        _rerun_harness(),
        scratch,
        transcript,
        command or "accumulate_summaries $TRANSCRIPT; rerun_step_ok",
    )


def test_rerun_with_only_skipped_rows_passes(tmp_path: Path) -> None:
    result = _rerun(tmp_path, "Summary — 5 skipped, 2 blocked\n", [])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TRACER_RERUN_UNEXPECTED" not in result.stdout


def test_rerun_with_the_same_manual_set_passes(tmp_path: Path) -> None:
    transcript = f"Summary — 5 skipped, 2 manual\n{_MANUAL_PI}\n{_MANUAL_ZSH}\n"
    result = _rerun(tmp_path, transcript, ["pi", "zsh"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_rerun_with_a_new_manual_row_fails(tmp_path: Path) -> None:
    transcript = f"Summary — 5 skipped, 2 manual\n{_MANUAL_PI}\n{_MANUAL_ZSH}\n"
    added = _rerun(tmp_path / "added", transcript, ["pi"])
    assert added.returncode != 0
    assert "TRACER_RERUN_UNEXPECTED" in added.stdout
    assert "manual_added=zsh" in added.stdout
    missing = _rerun(
        tmp_path / "missing", f"Summary — 5 skipped, 1 manual\n{_MANUAL_PI}\n", ["pi", "zsh"]
    )
    assert missing.returncode != 0
    assert "manual_missing=zsh" in missing.stdout


def test_rerun_without_a_pass1_manual_baseline_fails(tmp_path: Path) -> None:
    result = _rerun(tmp_path, "Summary — 5 skipped\n", None)
    assert result.returncode != 0
    assert "TRACER_RERUN_UNEXPECTED" in result.stdout


@pytest.mark.parametrize("kind", sorted(_UNEXPECTED_KINDS))
def test_rerun_with_an_unexpected_row_fails(tmp_path: Path, kind: str) -> None:
    result = _rerun(tmp_path, f"Summary — 4 skipped, 1 {_UNEXPECTED_KINDS[kind]}\n", [])
    assert result.returncode != 0
    assert "TRACER_RERUN_UNEXPECTED" in result.stdout
    assert f"{kind}=1" in result.stdout


def test_rerun_with_an_explained_dependency_failure_fails(tmp_path: Path) -> None:
    """R2-10: pass 1 would accept this transcript; the rerun must not."""
    transcript = "\n".join(
        (
            "Summary — 5 skipped, 1 manual, 1 dependency failed",
            "✖ mmdc  dependency failed — pi",
            _MANUAL_PI,
        )
    )
    both = "accumulate_summaries $TRANSCRIPT; install_step_ok 1"
    assert _rerun(tmp_path / "gate", transcript, ["pi"], both).returncode == 0
    result = _rerun(tmp_path / "rerun", transcript, ["pi"])
    assert result.returncode != 0
    assert "dependency_failed=1" in result.stdout
    assert "TRACER_RERUN_UNEXPECTED" in result.stdout


def _pass1_script(scratch: Path, transcript: str, call: str) -> str:
    """cmd_pass1 with the container-bound helpers stubbed and a fixed transcript per run."""
    fixture = scratch / "pass1-transcript.txt"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(transcript, encoding="utf-8")
    names = (
        "parse_summary_line",
        "accumulate_summaries",
        "dependency_failures_explained",
        "install_step_ok",
        "list_blocked_rows",
        "ensure_phase_dir",
        "die",
        "cmd_pass1",
    )
    stubs = (
        "container_running() { return 0; }\n"
        f"run_setup_as_tester() {{ cat {shlex.quote(str(fixture))}; }}\n"
        "assert_receipt_present() { return 0; }\n"
        "assert_gsd_absent() { return 0; }\n"
    )
    return (
        'PHASE_DIR="$SCRATCH/phase"\nDISTRO=debian\n'
        + _summary_harness(*names)
        + "\n"
        + stubs
        + call
        + "\n"
    )


def test_pass1_manual_set_is_persisted_sorted_unique(tmp_path: Path) -> None:
    transcript = f"Summary — 2 installed, 2 manual\n{_MANUAL_ZSH}\n{_MANUAL_PI}\n"
    result = _run(_pass1_script(tmp_path, transcript, "cmd_pass1 --categories a,b"), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    saved = (tmp_path / "phase" / "pass1-manual.txt").read_text(encoding="utf-8")
    assert saved == "pi\nzsh\n"


def test_blocked_rows_are_listed_once_with_their_reason(tmp_path: Path) -> None:
    """R1-23: a plan row and an outcome row for one tool print one line, and the step passes."""
    rows = (
        "✖ mmdc  blocked — needs Node 20 or newer",
        "✖ puppeteer  blocked — needs Node 22 or newer",
    )
    transcript = "\n".join(
        ("Install plan — 3 install, 2 blocked", *rows, "Summary — 3 installed, 2 blocked", *rows)
    )
    result = _run(_pass1_script(tmp_path, transcript, "cmd_pass1"), tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    listed = [
        line for line in result.stdout.splitlines() if line.startswith("TRACER_DISTRO_BLOCKED")
    ]
    assert listed == [
        "TRACER_DISTRO_BLOCKED distro=debian tool=mmdc reason=needs Node 20 or newer",
        "TRACER_DISTRO_BLOCKED distro=debian tool=puppeteer reason=needs Node 22 or newer",
    ]
    assert "TRACER_CLEAN_INSTALL_OK" in result.stdout


def test_a_pass_that_installs_nothing_is_misconfigured(tmp_path: Path) -> None:
    result = _run(_pass1_script(tmp_path, "Summary — 3 skipped\n", "cmd_pass1"), tmp_path)
    assert result.returncode != 0
    assert "TRACER_DISTRO_MISCONFIGURED distro=debian" in result.stdout
    assert "TRACER_CLEAN_INSTALL_OK" not in result.stdout


def test_rerun_gate_is_wired_into_pass2() -> None:
    pass2 = _function("cmd_pass2")
    gate = pass2.index("install_step_ok ")
    rerun = pass2.index("rerun_step_ok")
    assert gate < rerun < pass2.index("TRACER_RERUN_OK")
    assert "ACC_REPAIRED=0" in pass2
    assert "ACC_REINSTALLED=0" in _function("cmd_pass1")


def test_the_herdr_probes_are_wired_around_the_uninstall_step() -> None:
    pass2 = _function("cmd_pass2")
    first_run = pass2.index('run_pass2_step "--all --yes"')
    uninstall = pass2.index('run_pass2_step "--uninstall --yes"')
    reinstall = pass2.rindex('run_pass2_step "--all --yes"')
    assert pass2.index("herdr_probe_installed") < first_run < uninstall
    assert pass2.index("settings_probe_revert") < pass2.index("herdr_probe_after") < reinstall


# --- herdr -------------------------------------------------------------------------------


def _herdr_script(*extra: str) -> str:
    text = _script_text()
    names = (
        "ensure_phase_dir",
        "herdr_sidebar_keys",
        "herdr_status_parse",
        "herdr_status_clean",
        "herdr_installed_verdict",
        "herdr_removed_verdict",
        "herdr_probe_installed",
        "herdr_probe_after",
    )
    parts = [
        f"HERDR_PLUGIN_ID={_constant('HERDR_PLUGIN_ID', text)}",
        'HERDR_PROBE_COPY="$SCRATCH/herdr-probe"',
        'PHASE_DIR="$SCRATCH/phase"',
        *(_function(name, text) for name in names),
        *extra,
    ]
    return "\n".join(parts)


_STATUS_CLEAN = (
    "claude: not installed (/x)\nletta (experimental): not installed (/y)\npi: not installed"
)


def test_herdr_status_parse(tmp_path: Path) -> None:
    fixture = tmp_path / "status.txt"

    def parse(text: str, command: str = "herdr_status_parse") -> subprocess.CompletedProcess[str]:
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(text, encoding="utf-8")
        return _run(
            _herdr_script() + f'\n{command} < "{fixture}"\n', tmp_path, path="/usr/bin:/bin"
        )

    parsed = parse(_STATUS_CLEAN + "\n")
    assert parsed.stdout.splitlines() == [
        "claude|not installed",
        "letta|not installed",
        "pi|not installed",
    ]
    clean = parse(_STATUS_CLEAN + "\n", "herdr_status_clean")
    assert clean.returncode == 0, clean.stdout
    dirty = parse(
        "claude: current (v10) (/x)\nopencode: needs repair (v13) (/y)\npi: not installed\n",
        "herdr_status_clean",
    )
    assert dirty.returncode != 0
    assert dirty.stdout.splitlines() == [
        "TRACER_HERDR_NOT_CURRENT target=claude",
        "TRACER_HERDR_NOT_CURRENT target=opencode",
    ]
    unreadable = parse("error: no server\n", "herdr_status_clean")
    assert unreadable.returncode != 0
    assert "TRACER_HERDR_STATUS_UNREADABLE" in unreadable.stdout


def _facts(*lines: str, done: bool = True) -> str:
    return "\n".join([*lines, *(["D"] if done else [])]) + "\n"


_GOOD_FACTS = (
    "H claude",
    "H sidebar-markers",
    "S claude: current (v10) (/x)",
    "S pi: not installed",
    'Y [{"id": "herdr-setup.markers"}]',
    "C ui.sidebar.agents.rows",
    "C ui.sidebar.agents.row_gap",
    "C ui.sidebar.spaces.rows",
    "E sidebar ui.sidebar.agents.rows []",
)


def _verdict(tmp_path: Path, facts: str) -> subprocess.CompletedProcess[str]:
    fixture = tmp_path / "facts.txt"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(facts, encoding="utf-8")
    return _run(
        _herdr_script() + f'\nherdr_installed_verdict < "{fixture}"\n',
        tmp_path,
        path="/usr/bin:/bin",
    )


def test_herdr_installed_probe_requires_every_piece(tmp_path: Path) -> None:
    ok = _verdict(tmp_path / "ok", _facts(*_GOOD_FACTS))
    assert ok.returncode == 0, ok.stdout
    assert ok.stdout.splitlines() == ["TRACER_HERDR_INSTALLED_OK hosts=claude"]

    def drop(prefix: str) -> tuple[str, ...]:
        return tuple(line for line in _GOOD_FACTS if not line.startswith(prefix))

    cases = {
        "no-receipt": (("N",), "TRACER_HERDR_NOT_RECORDED reason=no-receipt"),
        "no-sidebar": (drop("H sidebar"), "TRACER_HERDR_NOT_RECORDED reason=no-sidebar"),
        "no-hosts": (drop("H claude"), "TRACER_HERDR_NOT_RECORDED reason=no-hosts"),
        "not-current": (
            (*drop("S claude"), "S claude: needs repair (v9) (/x)"),
            "TRACER_HERDR_NOT_CURRENT target=claude",
        ),
        "no-status-line": (drop("S claude"), "TRACER_HERDR_NOT_CURRENT target=claude"),
        "no-plugin": (drop("Y "), "TRACER_HERDR_PLUGIN_MISSING"),
        "no-key": (
            drop("C ui.sidebar.spaces.rows"),
            "TRACER_HERDR_KEY_MISSING key=ui.sidebar.spaces.rows",
        ),
        "skill": (
            (*_GOOD_FACTS, "W /home/tester/.claude/skills/herdr"),
            "TRACER_HERDR_SKILL_FOUND path=/home/tester/.claude/skills/herdr",
        ),
    }
    for name, (lines, expected) in cases.items():
        result = _verdict(tmp_path / name, _facts(*lines))
        assert result.returncode != 0, name
        assert expected in result.stdout.splitlines(), (name, result.stdout)
        assert not any(
            line.startswith("TRACER_HERDR_INSTALLED_OK") for line in result.stdout.splitlines()
        )
    cut = _verdict(tmp_path / "cut", _facts(*_GOOD_FACTS, done=False))
    assert cut.returncode != 0
    assert "TRACER_HERDR_PROBE_FAILED" in cut.stdout


def test_herdr_probe_expects_no_default_shell_without_zsh(tmp_path: Path) -> None:
    """R1-19: these containers carry no zsh, so no default_shell may be written."""
    for name, extra, found in (
        ("config", "DS /usr/bin/zsh", "/usr/bin/zsh"),
        ("ledger", 'E default-shell terminal.default_shell "/bin/zsh"', '"/bin/zsh"'),
    ):
        result = _verdict(tmp_path / name, _facts(*_GOOD_FACTS, extra))
        assert result.returncode != 0
        assert f"TRACER_HERDR_SHELL_SET found={found}" in result.stdout.splitlines()
    assert _verdict(tmp_path / "none", _facts(*_GOOD_FACTS)).returncode == 0


def _herdr_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, status_exit: int = 0) -> Path:
    """A scratch HOME with a fake herdr, its receipt, ledger, plugin answer and config.toml."""
    from installer import receipts
    from installer.receipts import Receipt, ReceiptMethod

    scratch = tmp_path / "home"
    (scratch / "phase").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: scratch)
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    receipts.write(
        Receipt(
            tool="herdr",
            at="2026-11-12T12:00:00+00:00",
            method=ReceiptMethod(kind="github_release", key="a" * 64),
            package=None,
            artifacts=(),
            smoke=None,
            hooks={"herdr-integration": ("claude", "sidebar-markers")},
        )
    )
    binary = scratch / ".local" / "bin" / "herdr"
    binary.parent.mkdir(parents=True)
    binary.write_text(
        "#!/bin/sh\n"
        'case "$1 $2" in\n'
        '  "integration status")\n'
        '    printf "claude: current (v10) (/x)\\npi: not installed (/y)\\n"\n'
        f"    exit {status_exit} ;;\n"
        '  "plugin list") printf \'[{"id": "herdr-setup.markers"}]\\n\' ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    config = scratch / ".config" / "herdr" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        '[ui.sidebar.agents]\nrows = [["agent"]]\nrow_gap = 1\n\n[ui.sidebar.spaces]\nrows = []\n',
        encoding="utf-8",
    )
    ledger = receipts.config_ledger_dir() / "herdr.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"setting": "sidebar", "key_path": ["ui", "sidebar", "agents", "rows"], "value": []},
        {"setting": "sidebar", "key_path": ["ui", "sidebar", "agents", "row_gap"], "value": 1},
        {"setting": "sidebar", "key_path": ["ui", "sidebar", "spaces", "rows"], "value": []},
    ]
    ledger.write_text(json.dumps({"v": 1, "agent": "herdr", "entries": entries}), encoding="utf-8")
    return scratch


def _herdr_probe_script(tmp_path: Path, call: str) -> str:
    brew = tmp_path / "linuxbrew" / "bin" / "brew"
    return _herdr_script(
        f"export PYTHONPATH={shlex.quote(str(ROOT))}",
        _assign("TESTER_WORKSPACE", str(tmp_path)),
        _assign("BREW_BIN", str(brew if brew.exists() else _brew_stub(tmp_path))),
        'exec_tester() { HOME="$SCRATCH" bash -c "$1"; }',
        _uv_stub(),
        call,
    )


def test_herdr_reload_failure_is_not_a_probe_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1-28: no herdr server runs in a container, and `integration status` may exit non-zero."""
    scratch = _herdr_home(tmp_path, monkeypatch, status_exit=3)
    log = scratch / "phase" / "pass1-transcript.log"
    log.write_text("note: herdr server reload-config failed: no server running\n", encoding="utf-8")
    result = _run(_herdr_probe_script(tmp_path, "herdr_probe_installed"), scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["TRACER_HERDR_INSTALLED_OK hosts=claude"]
    keys = (scratch / "phase" / "herdr-ledger-keys.txt").read_text(encoding="utf-8").split()
    assert keys == [
        "ui.sidebar.agents.rows",
        "ui.sidebar.agents.row_gap",
        "ui.sidebar.spaces.rows",
    ]
    assert (scratch / "herdr-probe").exists()


def test_herdr_probe_after_proves_status_plugin_and_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = _herdr_home(tmp_path, monkeypatch)
    assert _run(_herdr_probe_script(tmp_path, "herdr_probe_installed"), scratch).returncode == 0
    after = _herdr_probe_script(tmp_path, "herdr_probe_after")
    # The fake herdr still reports claude current and the plugin listed, and the keys remain.
    dirty = _run(after, scratch)
    assert dirty.returncode != 0
    lines = dirty.stdout.splitlines()
    assert "TRACER_HERDR_NOT_CURRENT target=claude" in lines
    assert "TRACER_HERDR_PLUGIN_LEFT" in lines
    assert "TRACER_HERDR_KEY_LEFT key=ui.sidebar.agents.row_gap" in lines
    # After the uninstall: every target not installed, no plugin, config.toml without our keys.
    (scratch / ".config" / "herdr" / "config.toml").write_text("onboarding = false\n")
    (scratch / "herdr-probe").write_text(
        '#!/bin/sh\ncase "$1 $2" in\n  "integration status") echo "claude: not installed (/x)" ;;\n'
        '  "plugin list") echo "[]" ;;\nesac\n',
        encoding="utf-8",
    )
    clean = _run(after, scratch)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.splitlines() == [
        "TRACER_HERDR_STATUS_CLEAN_OK",
        "TRACER_HERDR_REVERT_OK",
    ]
    (scratch / "phase" / "herdr-ledger-keys.txt").unlink()
    unknown = _run(after, scratch)
    assert unknown.returncode != 0
    assert "TRACER_HERDR_REVERT_UNKNOWN" in unknown.stdout


def _revert_with_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent: str,
    text: str,
    *,
    created: bool,
) -> subprocess.CompletedProcess[str]:
    from installer import agent_settings

    home = _TunedHome(tmp_path, monkeypatch)
    path = agent_settings.settings_file(agent, home=home.scratch, platform_os="linux")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    (home.workspace / ".e2e-tuned-agents.json").write_text(
        json.dumps({"agents": [agent], "created": {agent: [str(path)] if created else []}}),
        encoding="utf-8",
    )
    return home.run("settings_probe_revert")


def test_settings_revert_tolerates_herdr_residue_only_in_created_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1-22: empty containers and codex's `features.hooks` are herdr's residue, if we made it."""
    empty = _revert_with_file(
        tmp_path / "empty", monkeypatch, "claude", '{"hooks": {}}', created=True
    )
    assert empty.returncode == 0, empty.stdout + empty.stderr
    assert empty.stdout.splitlines() == [
        f"TRACER_SETTINGS_REVERT_OK keys={_tuned_keys(['claude'])}"
    ]

    marked = _revert_with_file(
        tmp_path / "marked", monkeypatch, "claude", '{"herdr-agent-state": {}}', created=True
    )
    assert marked.returncode != 0
    assert marked.stdout.splitlines() == [
        'TRACER_SETTINGS_FILE_LEFT agent=claude residue={"herdr-agent-state":{}}'
    ]

    codex = _revert_with_file(
        tmp_path / "codex", monkeypatch, "codex", "[features]\nhooks = true\n", created=True
    )
    assert codex.returncode == 0, codex.stdout + codex.stderr
    assert codex.stdout.splitlines() == [
        "TRACER_HERDR_RESIDUE agent=codex key=features.hooks",
        f"TRACER_SETTINGS_REVERT_OK keys={_tuned_keys(['codex'])}",
    ]

    other = _revert_with_file(
        tmp_path / "other",
        monkeypatch,
        "codex",
        '[features]\nhooks = true\nmore = "x"\n',
        created=True,
    )
    assert other.returncode != 0
    assert other.stdout.startswith("TRACER_SETTINGS_FILE_LEFT agent=codex")

    foreign = _revert_with_file(
        tmp_path / "foreign",
        monkeypatch,
        "claude",
        '{"hooks": {"Stop": []}, "mine": 1}',
        created=False,
    )
    assert foreign.returncode == 0, foreign.stdout + foreign.stderr


# --- Phase 24-04 task 3: tester user parameters and the nested-podman target ----------------

_TESTER_NAMES = ("exec_tester", "stream_worktree", "copy_workspace", "run_setup_as_tester")
_NESTED_OVERRIDE = (
    "TESTER_USER=podman\nTESTER_HOME=/home/podman\nTESTER_WORKSPACE=/home/podman/workspace\n"
    "CONTAINER_NAME=tools-installer-e2e-nested\n"
)


def _tester_script(scratch: Path, override: str = "") -> str:
    """The tester helpers over a recording `ct`; git and tar are stubbed (R1-20)."""
    text = _script_text()
    parts = [
        _distro_harness(),
        *(_function(name, text) for name in _TESTER_NAMES[1:]),
        "git() { :; }",
        "tar() { :; }",
        override,
    ]
    return "\n".join(parts)


def test_default_tester_argv_is_unchanged(tmp_path: Path) -> None:
    """R1-21: with the defaults every recorded argv is today's; the nested user changes it."""
    default = tmp_path / "default"
    default.mkdir()
    script = (
        _tester_script(default) + "\nexec_tester x\nstream_worktree\nrun_setup_as_tester '--x'\n"
    )
    result = _run(script, default)
    assert result.returncode == 0, result.stdout + result.stderr
    calls = (default / "calls").read_text(encoding="utf-8")
    assert "exec tools-installer-e2e-fedora su - tester -c x\n" in calls
    assert (
        "exec -i tools-installer-e2e-fedora su - tester -c "
        "mkdir -p /home/tester/workspace && tar -C /home/tester/workspace -xf -\n"
    ) in calls
    assert "cd /home/tester/workspace\n" in calls

    nested = tmp_path / "nested"
    nested.mkdir()
    script = (
        _tester_script(nested, _NESTED_OVERRIDE)
        + "\nexec_tester x\nstream_worktree\nrun_setup_as_tester '--x'\n"
    )
    result = _run(script, nested)
    assert result.returncode == 0, result.stdout + result.stderr
    calls = (nested / "calls").read_text(encoding="utf-8")
    assert "exec tools-installer-e2e-nested su - podman -c x\n" in calls
    assert (
        "exec -i tools-installer-e2e-nested su - podman -c "
        "mkdir -p /home/podman/workspace && tar -C /home/podman/workspace -xf -\n"
    ) in calls
    assert "cd /home/podman/workspace\n" in calls
    assert "/home/tester" not in calls


def test_create_tester_follows_the_tester_user(tmp_path: Path) -> None:
    """The sudoers file and the brew chown name the parameterized user; defaults are unchanged."""
    default = tmp_path / "default"
    default.mkdir()
    run = _run(_tester_script(default) + "\ncreate_tester\n", default)
    assert run.returncode == 0, run.stderr
    calls = (default / "calls").read_text(encoding="utf-8")
    assert "tester ALL=(ALL) NOPASSWD:ALL" in calls
    assert "/etc/sudoers.d/tester && chmod 440 /etc/sudoers.d/tester" in calls
    assert "chown -R tester:tester /home/linuxbrew" in calls


_NESTED_CONSTANTS = ("NESTED_IMAGE", "NESTED_CONTAINER_NAME", "NESTED_USER", "NESTED_PROBE_IMAGE")
_NESTED_STEPS = (
    "nested_start",
    "nested_prepare",
    "nested_probe_podman",
    "nested_install",
    "nested_artifacts_ok",
    "nested_herdr_shell_ok",
    "nested_uninstall_run",
    "nested_uninstall_ok",
    "nested_herdr_revert_ok",
)


def test_nested_prepare_installs_su_for_the_tester_helpers() -> None:
    """24-08 nested run #1: quay.io/podman/stable has no `su`, which exec_tester runs through."""
    assert "su - " in _function("exec_tester")
    assert "util-linux" in _function("nested_prepare")


def _nested_script(call: str, *, real: Sequence[str] = (), stubs: str = "") -> str:
    """cmd_nested's helpers over a recording `ct`; a step not named in `real` prints its name."""
    text = _script_text()
    names = (
        "nested_teardown",
        "nested_infeasible",
        "nested_alacritty_paths",
        "nested_herdr_facts",
        "cmd_nested",
        *real,
    )
    steps = "\n".join(
        f'{name}() {{ printf "STEP {name}\\n"; }}' for name in _NESTED_STEPS if name not in real
    )
    parts = [
        _distro_harness(),
        *(f"{name}={_constant(name, text)}" for name in _NESTED_CONSTANTS),
        *(_function(name, text) for name in dict.fromkeys(names)),
        steps,
        stubs,
        call,
    ]
    return "\n".join(parts)


def test_nested_outer_container_flags(tmp_path: Path) -> None:
    """D-18: the outer box gets /dev/fuse and label=disable, never a privileged flag."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    result = _run(_nested_script("nested_start", real=("nested_start",)), scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    run_lines = [call for call in _calls(scratch) if call.startswith("run ")]
    assert run_lines == [
        "run -d --name tools-installer-e2e-nested --device /dev/fuse "
        "--security-opt label=disable quay.io/podman/stable:latest sleep infinity"
    ]
    assert "privileged" not in " ".join(_calls(scratch))


def test_nested_teardown_runs_on_failure(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    scratch.mkdir()
    script = _nested_script("cmd_nested || true", stubs="nested_install() { return 1; }")
    result = _run(script, scratch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rm -f tools-installer-e2e-nested" in _calls(scratch)
    assert "TRACER_NESTED_TEARDOWN_OK" in result.stdout
    # The nested run is told apart from a distro run by its own container, user and artifact dir.
    assert "STEP nested_start" in result.stdout


def test_nested_cmd_fails_when_a_step_fails(tmp_path: Path) -> None:
    scratch = tmp_path / "home"
    scratch.mkdir()
    script = _nested_script(
        'rc=0; cmd_nested || rc=$?; printf "RC=%s\\n" "$rc"', stubs="nested_install() { return 1; }"
    )
    failing = _run(script, scratch)
    assert "RC=1" in failing.stdout
    assert "STEP nested_artifacts_ok" not in failing.stdout
    passing = _run(
        _nested_script('rc=0; cmd_nested || rc=$?; printf "RC=%s\\n" "$rc"'), tmp_path / "ok"
    )
    assert "RC=0" in passing.stdout
    steps = [line for line in passing.stdout.splitlines() if line.startswith("STEP ")]
    assert steps == [
        "STEP nested_start",
        "STEP nested_prepare",
        "STEP nested_probe_podman",
        "STEP nested_install",
        "STEP nested_artifacts_ok",
        "STEP nested_herdr_shell_ok",
        "STEP nested_uninstall_run",
        "STEP nested_uninstall_ok",
        "STEP nested_herdr_revert_ok",
    ]


_ALACRITTY_PATHS = (
    ".local/bin/alacritty",
    ".local/share/applications/Alacritty.desktop",
    ".local/share/icons/hicolor/scalable/apps/Alacritty.svg",
    ".terminfo/a/alacritty",
    ".terminfo/a/alacritty-direct",
)
_ARTIFACT_FACTS = (*(f"P {path}" for path in _ALACRITTY_PATHS), "V ok", "T1 ok", "T2 ok")


def _fact_stub(*lines: str) -> str:
    return _assign("FACTS", "\n".join(lines)) + '\nexec_tester() { printf "%s\\n" "$FACTS"; }\n'


def test_nested_artifact_check(tmp_path: Path) -> None:
    def check(name: str, *lines: str) -> subprocess.CompletedProcess[str]:
        scratch = tmp_path / name
        scratch.mkdir()
        script = _nested_script(
            "nested_artifacts_ok", real=("nested_artifacts_ok",), stubs=_fact_stub(*lines, "D")
        )
        return _run(script, scratch)

    ok = check("ok", *_ARTIFACT_FACTS)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert ok.stdout.splitlines() == ["TRACER_NESTED_BUILD_OK"]
    image = check("image", *_ARTIFACT_FACTS, "M sha256abc")
    assert image.returncode != 0
    assert image.stdout.splitlines() == ["TRACER_NESTED_IMAGE_LEFT id=sha256abc"]
    box = check("box", *_ARTIFACT_FACTS, "C abc123")
    assert box.returncode != 0
    assert "TRACER_NESTED_CONTAINER_LEFT id=abc123" in box.stdout
    leaf = check(
        "leaf", *(fact for fact in _ARTIFACT_FACTS if not fact.endswith("alacritty-direct"))
    )
    assert leaf.returncode != 0
    assert leaf.stdout.splitlines() == [
        "TRACER_NESTED_ARTIFACT_MISSING path=.terminfo/a/alacritty-direct"
    ]
    for failing, expected in (
        ("V fail", "TRACER_NESTED_DESKTOP_INVALID"),
        ("T1 fail", "TRACER_NESTED_TERMINFO_FAILED step=infocmp-A"),
        ("T2 fail", "TRACER_NESTED_TERMINFO_FAILED step=infocmp-env"),
    ):
        facts = tuple(f for f in _ARTIFACT_FACTS if f[:2] != failing[:2])
        result = check(failing.replace(" ", "-"), *facts, failing)
        assert result.returncode != 0
        assert expected in result.stdout.splitlines()
    cut = _run(
        _nested_script(
            "nested_artifacts_ok", real=("nested_artifacts_ok",), stubs=_fact_stub(*_ARTIFACT_FACTS)
        ),
        tmp_path / "cut",
    )
    assert cut.returncode != 0
    assert "TRACER_NESTED_PROBE_FAILED" in cut.stdout


def test_nested_infeasible_is_distinct(tmp_path: Path) -> None:
    """An inner podman that cannot run is infeasibility, not a product failure; the run goes on."""
    scratch = tmp_path / "home"
    scratch.mkdir()
    stubs = (
        "exec_tester() { case \"$1\" in *'podman info'*) "
        "printf 'Error: no newuidmap\\nsecond line\\n'; return 1 ;; esac; }\n"
        'nested_install() { printf "INSTALLER_RAN\\n"; }\n'
    )
    script = _nested_script("cmd_nested || true", real=("nested_probe_podman",), stubs=stubs)
    result = _run(script, scratch)
    lines = result.stdout.splitlines()
    assert "TRACER_NESTED_INFEASIBLE step=podman-info detail=Error: no newuidmap" in lines
    assert not any("TRACER_NESTED_BUILD_FAILED" in line for line in lines)
    assert "TRACER_NESTED_PODMAN_OK" not in lines
    assert lines.index("INSTALLER_RAN") > lines.index(
        "TRACER_NESTED_INFEASIBLE step=podman-info detail=Error: no newuidmap"
    )
    ok = _run(
        _nested_script(
            "nested_probe_podman",
            real=("nested_probe_podman",),
            stubs="exec_tester() { return 0; }\n",
        ),
        tmp_path / "ok",
    )
    assert ok.stdout.splitlines() == ["TRACER_NESTED_PODMAN_OK"]
    run_step = _run(
        _nested_script(
            "nested_probe_podman",
            real=("nested_probe_podman",),
            stubs=(
                "exec_tester() { case \"$1\" in *'podman run'*) "
                "echo 'pull failed'; return 1;; esac; }\n"
            ),
        ),
        tmp_path / "run",
    )
    assert run_step.stdout.splitlines() == [
        "TRACER_NESTED_INFEASIBLE step=podman-run detail=pull failed"
    ]


def test_nested_alacritty_row_classification(tmp_path: Path) -> None:
    def classify(name: str, row: str) -> subprocess.CompletedProcess[str]:
        scratch = tmp_path / name
        scratch.mkdir()
        fixture = scratch / "install.txt"
        fixture.write_text(f"Install plan — 1 install\n○ alacritty  will install\n{row}\n")
        script = _nested_script(
            f"nested_classify_alacritty {shlex.quote(str(fixture))}",
            real=("nested_classify_alacritty", "nested_infeasible"),
        )
        return _run(script, scratch)

    done = classify("done", "✓ alacritty  installed")
    assert done.returncode == 0, done.stdout
    cannot = classify("cannot", "✖ alacritty  failed — distrobox create: cannot reach the engine")
    assert cannot.returncode == 2
    assert cannot.stdout.splitlines() == [
        "TRACER_NESTED_INFEASIBLE step=distrobox-create "
        "detail=distrobox create: cannot reach the engine"
    ]
    broken = classify("broken", "✖ alacritty  failed — cargo build: exit 101")
    assert broken.returncode == 1
    assert broken.stdout.splitlines() == [
        "TRACER_NESTED_BUILD_FAILED detail=failed — cargo build: exit 101"
    ]
    (tmp_path / "absent").mkdir()
    absent = _run(
        _nested_script(
            'printf "Summary — 1 installed\\n" > "$SCRATCH/none.txt"; '
            'nested_classify_alacritty "$SCRATCH/none.txt"',
            real=("nested_classify_alacritty", "nested_infeasible"),
        ),
        tmp_path / "absent",
    )
    assert absent.returncode == 1
    assert "TRACER_NESTED_BUILD_FAILED" in absent.stdout


def test_nested_herdr_shell_check(tmp_path: Path) -> None:
    def check(name: str, call: str, *lines: str) -> subprocess.CompletedProcess[str]:
        scratch = tmp_path / name
        scratch.mkdir()
        real = ("nested_herdr_shell_ok", "nested_herdr_revert_ok")
        return _run(_nested_script(call, real=real, stubs=_fact_stub(*lines, "D")), scratch)

    good = ("DS /usr/bin/zsh", "L /usr/bin/zsh", "W /usr/bin/zsh")
    ok = check("ok", "nested_herdr_shell_ok", *good)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert ok.stdout.splitlines() == ["TRACER_NESTED_HERDR_SHELL_OK"]
    other = check("other", "nested_herdr_shell_ok", "DS /bin/fish", "L /bin/fish", "W /usr/bin/zsh")
    assert other.returncode != 0
    assert other.stdout.splitlines() == [
        "TRACER_NESTED_HERDR_SHELL_MISMATCH found=/bin/fish expected=/usr/bin/zsh"
    ]
    unrecorded = check("unrecorded", "nested_herdr_shell_ok", "DS /usr/bin/zsh", "W /usr/bin/zsh")
    assert unrecorded.returncode != 0
    assert unrecorded.stdout.splitlines() == [
        "TRACER_NESTED_HERDR_SHELL_UNRECORDED expected=/usr/bin/zsh"
    ]
    none = check("none", "nested_herdr_shell_ok", "W /usr/bin/zsh")
    assert none.returncode != 0
    assert "found=none expected=/usr/bin/zsh" in none.stdout
    reverted = check("reverted", "nested_herdr_revert_ok")
    assert reverted.returncode == 0
    assert reverted.stdout.splitlines() == ["TRACER_NESTED_HERDR_REVERT_OK"]
    kept = check("kept", "nested_herdr_revert_ok", "DS /usr/bin/zsh")
    assert kept.returncode != 0
    assert kept.stdout.splitlines() == ["TRACER_NESTED_HERDR_REVERT_LEFT found=/usr/bin/zsh"]


def test_nested_uninstall_check(tmp_path: Path) -> None:
    def check(name: str, *lines: str) -> subprocess.CompletedProcess[str]:
        scratch = tmp_path / name
        scratch.mkdir()
        script = _nested_script(
            "nested_uninstall_ok", real=("nested_uninstall_ok",), stubs=_fact_stub(*lines, "D")
        )
        return _run(script, scratch)

    clean = check("clean")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert clean.stdout.splitlines() == ["TRACER_NESTED_UNINSTALL_OK"]
    left = check("left", "L .terminfo/a", "L .local/bin/alacritty")
    assert left.returncode != 0
    assert left.stdout.splitlines() == [
        "TRACER_NESTED_UNINSTALL_LEFT path=.terminfo/a",
        "TRACER_NESTED_UNINSTALL_LEFT path=.local/bin/alacritty",
    ]


def test_nested_is_wired_into_main_and_usage() -> None:
    assert "nested) cmd_nested" in _function("main")
    assert "nested" in _function("usage")
    assert "--privileged" not in "\n".join(
        line for line in _script_text().splitlines() if not line.lstrip().startswith("#")
    )


def _stub_bin(directory: Path, bodies: dict[str, str]) -> Path:
    """Executable shell stubs named after the container programs a probe runs."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in bodies.items():
        stub = directory / name
        stub.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        stub.chmod(0o755)
    return directory


def test_nested_gathers_run_for_real_over_a_scratch_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The python and shell the nested probes send to the container run, with stub programs."""
    from installer import receipts
    from installer.receipts import Receipt, ReceiptArtifact, ReceiptMethod

    scratch = tmp_path / "home"
    scratch.mkdir()
    monkeypatch.setattr(Path, "home", lambda: scratch)
    monkeypatch.setattr(receipts, "receipts_dir", receipts.default_receipts_dir)
    receipts.write(
        Receipt(
            tool="alacritty",
            at="2026-11-12T12:00:00+00:00",
            method=ReceiptMethod(kind="cargo_distrobox", key="a" * 64),
            package=None,
            artifacts=tuple(
                ReceiptArtifact(path=scratch / path, type="leaf") for path in _ALACRITTY_PATHS
            ),
            smoke=None,
            hooks={},
        )
    )
    config = scratch / ".config" / "herdr" / "config.toml"
    config.parent.mkdir(parents=True)
    zsh_path = str(tmp_path / "bin" / "zsh")
    config.write_text(f'[terminal]\ndefault_shell = "{zsh_path}"\n', encoding="utf-8")
    ledger = receipts.config_ledger_dir() / "herdr.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    entry = {"setting": "default-shell", "key_path": ["terminal", "default_shell"]}
    ledger.write_text(
        json.dumps({"v": 1, "agent": "herdr", "entries": [{**entry, "value": zsh_path}]}),
        encoding="utf-8",
    )
    bins = _stub_bin(
        tmp_path / "bin",
        {
            "desktop-file-validate": "exit 0",
            "infocmp": "exit 0",
            "podman": "exit 0",
            "zsh": "exit 0",
        },
    )
    (bins / "bash").symlink_to(_bash())
    env_path = f"{bins}:/usr/bin:/bin"
    base = _nested_script(
        "",
        real=("nested_artifacts_ok", "nested_herdr_shell_ok", "nested_herdr_revert_ok"),
        stubs="\n".join(
            [
                f"export PYTHONPATH={shlex.quote(str(ROOT))}",
                _assign("TESTER_WORKSPACE", str(tmp_path)),
                _assign("BREW_BIN", str(_brew_stub(tmp_path))),
                'exec_tester() { HOME="$SCRATCH" bash -c "$1"; }',
                _uv_stub(),
            ]
        ),
    )
    artifacts = _run(base + "\nnested_artifacts_ok\n", scratch, path=env_path)
    assert artifacts.returncode == 0, artifacts.stdout + artifacts.stderr
    assert artifacts.stdout.splitlines() == ["TRACER_NESTED_BUILD_OK"]
    # `which_with_brew("zsh")` answers the stub, which is also what the config and ledger hold.
    shell = _run(base + "\nnested_herdr_shell_ok\n", scratch, path=env_path)
    assert shell.returncode == 0, shell.stdout + shell.stderr
    assert shell.stdout.splitlines() == ["TRACER_NESTED_HERDR_SHELL_OK"]
    config.write_text("onboarding = false\n", encoding="utf-8")
    reverted = _run(base + "\nnested_herdr_revert_ok\n", scratch, path=env_path)
    assert reverted.returncode == 0, reverted.stdout + reverted.stderr
    assert reverted.stdout.splitlines() == ["TRACER_NESTED_HERDR_REVERT_OK"]
