"""Host-side proof of the container e2e's receipt checks (plan 19-19, STATE-03).

The script sources the container detector at load time, so these tests never
source it and never start a container. They read the committed text and run
the extracted functions in bash with `exec_tester` pinned to a scratch HOME.
"""

import re
import shlex
import shutil
import subprocess
import sys
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


def _run(script: str, scratch: Path) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
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
