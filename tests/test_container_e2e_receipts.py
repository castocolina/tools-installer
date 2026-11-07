"""The container e2e's host-side checks for receipts and summary behavior.

The script sources the container detector at load time, so these tests never
source it and never start a container. They read the committed text and run
the extracted functions in bash with fixture transcripts and a scratch HOME.
"""

import re
import shlex
import shutil
import subprocess
import sys
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
    return subprocess.run(
        [_bash(), "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


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


def test_assignment_survives_a_spaced_workspace() -> None:
    """A workspace path with a space stays one word in a generated assignment (G19)."""
    result = _run(
        _assign("TESTER_WORKSPACE", "/a b/c") + '\nprintf "%s" "$TESTER_WORKSPACE"\n',
        Path("/unused"),
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
        f'  exec {exe} "$@"\n'
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


def test_settings_probe_write_fails_on_a_refusal(tmp_path: Path) -> None:
    """One refusal fails the write probe; every written key passes it."""
    scratch = tmp_path / "home"
    scratch.mkdir()

    def probe(*lines: str) -> subprocess.CompletedProcess[str]:
        stub = _assign("STUB_OUTPUT", "\n".join(lines))
        override = 'exec_tester() { printf "%s\\n" "$STUB_OUTPUT"; }'
        script = "\n".join(
            [_harness("settings_probe_write"), stub, override, "settings_probe_write"]
        )
        return _run(script, scratch)

    refused = probe("W claude permissions.defaultMode", "E codex not valid TOML (line 2)")
    assert refused.returncode != 0
    assert refused.stdout.splitlines() == [
        "TRACER_SETTINGS_WRITE_FAILED agent=codex detail=not valid TOML (line 2)"
    ]
    wrote = probe(
        "W claude permissions.defaultMode",
        "W claude skipDangerousModePermissionPrompt",
        "W codex approval_policy",
    )
    assert wrote.returncode == 0, wrote.stderr
    assert wrote.stdout.splitlines() == ["TRACER_SETTINGS_WRITE_OK wrote=3"]


def test_settings_probe_revert_flags_a_key_or_ledger_left(tmp_path: Path) -> None:
    """A key that differs from its snapshot, or a ledger left behind, fails the revert probe."""
    scratch = tmp_path / "home"
    scratch.mkdir()

    def probe(*lines: str) -> subprocess.CompletedProcess[str]:
        stub = _assign("STUB_OUTPUT", "\n".join(lines))
        override = 'exec_tester() { printf "%s\\n" "$STUB_OUTPUT"; }'
        script = "\n".join(
            [_harness("settings_probe_revert"), stub, override, "settings_probe_revert"]
        )
        return _run(script, scratch)

    diff = probe("D claude skipDangerousModePermissionPrompt")
    assert diff.returncode != 0
    assert diff.stdout.splitlines() == [
        "TRACER_SETTINGS_REVERT_DIFF agent=claude key=skipDangerousModePermissionPrompt"
    ]
    left = probe("L codex")
    assert left.returncode != 0
    assert left.stdout.splitlines() == ["TRACER_SETTINGS_LEDGER_LEFT agent=codex"]
    clean = probe("K 4")
    assert clean.returncode == 0, clean.stderr
    assert clean.stdout.splitlines() == ["TRACER_SETTINGS_REVERT_OK keys=4"]


def test_the_settings_probes_are_wired_around_the_uninstall_step() -> None:
    pass2 = _function("cmd_pass2")
    uninstall = pass2.index('run_pass2_step "--uninstall --yes"')
    reinstall = pass2.rindex('run_pass2_step "--all --yes"')
    assert pass2.index("hook_probe_before") < pass2.index("settings_probe_write") < uninstall
    assert pass2.index("hook_probe_after") < pass2.index("settings_probe_revert") < reinstall
    assert "TESTER_WORKSPACE" in _function("settings_probe_write")


def test_the_settings_probes_drive_the_installer_and_check_the_revert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe sees an unreverted write, passes once the installer's own revert runs."""
    from installer import agent_settings

    scratch = tmp_path / "home"
    scratch.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(Path, "home", lambda: scratch)
    script = "\n".join(
        [
            f"export PYTHONPATH={shlex.quote(str(ROOT))}",
            _harness("settings_probe_write", "settings_probe_revert"),
            _assign("TESTER_WORKSPACE", str(workspace)),
            _assign("BREW_BIN", str(_brew_stub(tmp_path))),
            _uv_stub(),
        ]
    )
    written = _run(script + "\nsettings_probe_write\n", scratch)
    assert written.returncode == 0, written.stdout + written.stderr
    assert written.stdout.splitlines() == ["TRACER_SETTINGS_WRITE_OK wrote=4"]
    unreverted = _run(script + "\nsettings_probe_revert\n", scratch)
    assert unreverted.returncode != 0
    assert (
        "TRACER_SETTINGS_REVERT_DIFF agent=claude key=permissions.defaultMode" in unreverted.stdout
    )
    for agent in ("claude", "codex"):
        agent_settings.revert_setting(agent, "auto-approve", home=scratch, platform_os="linux")
    reverted = _run(script + "\nsettings_probe_revert\n", scratch)
    assert reverted.returncode == 0, reverted.stdout + reverted.stderr
    assert reverted.stdout.splitlines() == ["TRACER_SETTINGS_REVERT_OK keys=4"]
