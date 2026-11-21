"""Hermetic checks for the Playwright container evidence driver."""

import json
import os
import re
import shlex
import sys
import time
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests import e2e_evidence
from tests import e2e_playwright_mcp_driver as driver
from tests.test_container_e2e_aws_cli import run_shell, shell_function

SCRIPT = Path(__file__).resolve().parent.parent / "scripts/container-e2e-verify.sh"

ENTRY = {"command": "/bin/bunx", "args": ["@playwright/mcp@0.0.85"]}
HOSTS = ("codex", "cursor", "opencode")
CLAUDE = {"config": "absent", "settings": "seed"}


def test_playwright_mcp_is_registered_and_runs_one_lifecycle_step(tmp_path: Path) -> None:
    body = shell_function("cmd_playwright_mcp")
    script = f"""set -euo pipefail
LANDING_IMAGE=fedora:latest
LANDING_KEEP_IMAGE=0
REPO_ROOT={shlex.quote(str(tmp_path))}
{body}
ensure_phase_dir() {{ mkdir -p "$PHASE_DIR"; }}
landing_note_image() {{ echo note; }}
landing_bootstrap() {{ echo bootstrap; }}
landing_stage() {{ echo "$*"; }}
landing_step() {{ echo "$*"; }}
landing_teardown() {{ :; }}
die() {{ echo "$*" >&2; exit 2; }}
cmd_playwright_mcp
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "note",
        "bootstrap",
        "playwright-mcp-root playwright_mcp_root_setup",
        "lifecycle lifecycle",
    ]
    assert "LANDING_DRIVER_MODULE=tests.e2e_playwright_mcp_driver" in body
    result = run_shell(
        script.replace("cmd_playwright_mcp\n", "cmd_playwright_mcp --bad\n"), tmp_path
    )
    assert result.returncode != 0 and "unknown playwright-mcp option" in result.stderr
    dispatch = f"""set -euo pipefail
{shell_function("main")}
select_distro() {{ :; }}
cmd_playwright_mcp() {{ echo "dispatched:$*"; }}
main playwright-mcp --keep-image
"""
    assert run_shell(dispatch, tmp_path).stdout == "dispatched:--keep-image\n"


def test_playwright_mcp_root_setup_installs_only_chromium_and_unzip(tmp_path: Path) -> None:
    script = (
        shell_function("playwright_mcp_root_setup")
        + '\nexec_root() { echo "$*"; }\nplaywright_mcp_root_setup\n'
    )
    result = run_shell(script, tmp_path)
    assert result.returncode == 0 and result.stdout.splitlines() == [
        "dnf install -y chromium unzip"
    ]


@pytest.mark.parametrize("pulled", [0, 1])
@pytest.mark.parametrize("keep", [0, 1])
def test_the_names_and_removals_are_exact(tmp_path: Path, pulled: int, keep: int) -> None:
    text = SCRIPT.read_text()
    body = shell_function("cmd_playwright_mcp")
    assert "tools-installer-e2e-playwright-mcp-$$" in body
    assert "--privileged" not in body and "--privileged" not in shell_function("start_container")
    assert not re.search(r"podman system (?:reset|prune)|image prune|container prune", text)
    script = f"""set -euo pipefail
LANDING_CONTAINER_NAME=tools-installer-e2e-playwright-mcp-4242
LANDING_IMAGE=fedora:latest
LANDING_PULLED={pulled}
LANDING_KEEP_IMAGE={keep}
LANDING_TRANSCRIPT={shlex.quote(str(tmp_path / "transcript"))}
ct() {{ echo "$*" >> {shlex.quote(str(tmp_path / "calls"))}; }}
{shell_function("landing_teardown")}
landing_teardown
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert [c for c in calls if c.startswith("rm ")] == [
        "rm -f tools-installer-e2e-playwright-mcp-4242"
    ]
    assert [c for c in calls if c.startswith("rmi ")] == (
        ["rmi fedora:latest"] if pulled and not keep else []
    )


def test_the_usage_names_every_verdict_the_driver_expects() -> None:
    usage = (
        shell_function("usage")
        .split("playwright-mcp [--keep-image]", 1)[1]
        .split("-h, --help", 1)[0]
    )
    assert all(
        word in usage
        for word in ("Orchestrator only", "Fedora", "Chromium", "TRACER_PLAYWRIGHT_LAUNCH_UNPROVEN")
    )
    for prefixes in driver.EXPECTED_LINES.values():
        for prefix in prefixes:
            assert prefix.split()[0] in usage


def test_the_generic_skip_list_includes_playwright_mcp(tmp_path: Path) -> None:
    text = SCRIPT.read_text()
    matches = re.findall(r"^GENERIC_SKIP_TOOLS=(.*)$", text, re.M)
    assert len(matches) == 1 and {"herdr-app", "aws-cli", "bruno", "playwright-mcp"} <= set(
        matches[0].split(",")
    )
    before = text.split("GENERIC_SKIP_TOOLS=", 1)[0].splitlines()[-5:]
    assert all(word in " ".join(before) for word in ("herdr-app", "herdr-core", "target"))
    awk = re.search(r"^GENERIC_SKIP_AWK='\n(.*?)^'\s*$", text, re.M | re.S)
    assert awk is not None
    program = tmp_path / "filter.awk"
    program.write_text(awk.group(1))
    registry = tmp_path / "registry.toml"
    registry.write_text(
        '# playwright comment\n[[tool]]\nid = "playwright-mcp"\n'
        '# other comment\n[[tool]]\nid = "other"\n'
    )
    result = run_shell(
        f"awk -v {shlex.quote('skip=' + matches[0])} "
        f"-f {shlex.quote(str(program))} {shlex.quote(str(registry))}",
        tmp_path,
    )
    assert result.returncode == 0 and result.stdout == '# other comment\n[[tool]]\nid = "other"\n'


def test_install_verdict_ok_and_each_problem() -> None:
    assert (
        driver.install_verdict("installed", "bun", "0.0.85")
        == "TRACER_PLAYWRIGHT_INSTALL_OK method=bun range=0.0.85"
    )
    for status, method, version, detail in [
        ("failed", "bun", "0.0.85", "failed"),
        ("installed", "bun", None, "missing"),
        ("installed", "bun", "^0.0.85", "^0.0.85"),
        ("installed", "brew", "0.0.85", "brew"),
    ]:
        line = driver.install_verdict(status, method, version)
        assert "_FAILED" in line and detail in line


def test_register_verdict_ok_and_each_problem() -> None:
    entries: dict[str, Mapping[str, object] | None] = {h: ENTRY for h in HOSTS}

    def check(
        e: Mapping[str, Mapping[str, object] | None] = entries,
        copilot: str = "seed",
        claude: Mapping[str, str] = CLAUDE,
        hosts: tuple[str, ...] = HOSTS,
        warning: str = "copilot: left yours",
    ) -> str:
        return driver.register_verdict(e, "seed", copilot, CLAUDE, claude, hosts, warning)

    assert check() == "TRACER_PLAYWRIGHT_REGISTER_OK hosts=codex,cursor,opencode kept=copilot"
    for line, detail in [
        (check({**entries, "codex": None}), "codex"),
        (check({**entries, "cursor": {"args": ["wrong"]}}), "cursor"),
        (check(copilot="changed"), "copilot"),
        (check(claude={**CLAUDE, "settings": "changed"}), "claude"),
        (check(claude={**CLAUDE, "config": "created"}), "claude"),
        (check(hosts=(*HOSTS, "claude")), "claude"),
        (check(hosts=(*HOSTS, "copilot")), "copilot"),
        (check(warning=""), "copilot"),
    ]:
        assert "_FAILED" in line and detail in line


def test_consent_verdict_ok_and_each_problem() -> None:
    def check(
        late: Mapping[str, str] = CLAUDE,
        late_hosts: tuple[str, ...] = HOSTS,
        warning: str = "claude: appeared after you confirmed",
        entry: Mapping[str, object] | None = ENTRY,
        settings: str = "dark",
        hosts: tuple[str, ...] = (*HOSTS, "claude"),
    ) -> str:
        return driver.consent_verdict(
            CLAUDE, late, late_hosts, warning, entry, "dark", settings, hosts
        )

    assert check() == "TRACER_PLAYWRIGHT_CONSENT_OK"
    for line, detail in [
        (check(late={**CLAUDE, "config": "created"}), "claude"),
        (check(late={**CLAUDE, "settings": "changed"}), "claude"),
        (check(late_hosts=(*HOSTS, "claude")), "claude"),
        (check(warning="appeared after you confirmed"), "warning"),
        (check(entry=None), "entry"),
        (check(settings="light"), "settings"),
        (check(hosts=HOSTS), "claude"),
    ]:
        assert "_FAILED" in line and detail in line


def test_launch_verdict_ok_unproven_and_failed() -> None:
    replies: tuple[Mapping[str, object], ...] = (
        {"id": 1, "result": {"serverInfo": {"name": "test"}}},
        {"id": 2, "result": {"tools": [{"name": "browser_navigate"}]}},
        {"id": 3, "result": {"content": [{"type": "text", "text": "e2e-ok"}]}},
    )
    assert (
        driver.launch_verdict(driver.RpcResult(True, replies, ""))
        == "TRACER_PLAYWRIGHT_LAUNCH_OK tools=1 navigate=ok"
    )
    for result in (
        driver.RpcResult(False, (), "missing\nother"),
        driver.RpcResult(True, (), "timeout\nother"),
    ):
        assert "_UNPROVEN" in driver.launch_verdict(
            result
        ) and "other" not in driver.launch_verdict(result)
    empty_tools: list[object] = []
    bad_replies: tuple[tuple[Mapping[str, object], ...], ...] = (
        replies[:1] + ({"id": 2, "result": {"tools": empty_tools}},) + replies[2:],
        replies[:2] + ({"id": 3, "error": {"message": "bad"}},),
        replies[:2] + ({"id": 3, "result": {"isError": True}},),
    )
    for result in bad_replies:
        assert "_FAILED" in driver.launch_verdict(driver.RpcResult(True, result, ""))


def test_remove_verdict_ok_and_each_problem() -> None:
    def check(
        sweep: str = "",
        left: tuple[str, ...] = (),
        current: Mapping[str, str] = {"user": "seed"},
        created: tuple[str, ...] = (),
        receipt: bool = False,
        package: bool = False,
        residue: tuple[str, ...] = (),
    ) -> str:
        return driver.remove_verdict(
            sweep, left, {"user": "seed"}, current, created, receipt, package, residue
        )

    assert check() == "TRACER_PLAYWRIGHT_REMOVE_OK"
    for line, detail in [
        (check(sweep="sweep failed"), "sweep"),
        (check(left=("cursor",)), "cursor"),
        (check(current={"user": "changed"}), "user"),
        (check(created=("created",)), "created"),
        (check(receipt=True), "receipt"),
        (check(package=True), "package"),
        (check(residue=("residue",)), "residue"),
    ]:
        assert "_FAILED" in line and detail in line


def test_the_message_frames_are_the_mcp_ones() -> None:
    frames = driver.frames()
    assert all("\n" not in line for line in frames)
    init, notification, listing, call = [json.loads(line) for line in frames]
    assert init["id"] == 1 and init["method"] == "initialize"
    assert init["params"]["protocolVersion"] == "2025-03-26"
    assert init["params"]["clientInfo"]["name"] == "tools-installer-e2e"
    assert notification["method"] == "notifications/initialized" and "id" not in notification
    assert listing["id"] == 2 and listing["method"] == "tools/list"
    assert call["id"] == 3 and call["params"]["name"] == "browser_navigate"
    assert (
        call["params"]["arguments"]["url"].startswith("data:text/html,")
        and "e2e-ok" in call["params"]["arguments"]["url"]
    )


def test_the_rpc_client_talks_to_a_fake_server_through_files(tmp_path: Path) -> None:
    server = tmp_path / "server.py"
    server.write_text(
        "import json,sys\nfor line in sys.stdin:\n m=json.loads(line)\n"
        ' if "id" in m: print(json.dumps({"id":m["id"],"result":{}}),flush=True)\n'
    )
    result = driver.run_rpc([sys.executable, str(server)], os.environ, driver.frames(), 20)
    assert result.started and [r["id"] for r in result.replies] == [1, 2, 3]
    hanging = tmp_path / "hang.py"
    pidfile = tmp_path / "pid"
    hanging.write_text(
        'import subprocess,sys,time\np=subprocess.Popen([sys.executable,"-c",'
        '"import time; time.sleep(30)"])\nopen(sys.argv[1],"w").write(str(p.pid))\n'
        "for line in sys.stdin: time.sleep(30)\n"
    )
    start = time.monotonic()
    result = driver.run_rpc(
        [sys.executable, str(hanging), str(pidfile)], os.environ, driver.frames(), 3
    )
    # The deadline is a cap with room for a loaded host to start Python and write the pid file.
    assert result.started and not result.replies and time.monotonic() - start < 15
    pid = int(pidfile.read_text())
    # A killed descendant may remain a zombie until init reaps it; it cannot execute.
    stat = Path(f"/proc/{pid}/stat")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and stat.exists() and stat.read_text().split()[2] != "Z":
        time.sleep(0.05)
    assert not stat.exists() or stat.read_text().split()[2] == "Z"
    missing = driver.run_rpc([str(tmp_path / "missing")], os.environ, driver.frames(), 1)
    assert not missing.started and "missing" in missing.stderr_tail


def test_transcript_problem_and_gate_use_the_shared_functions() -> None:
    assert list(driver.EXPECTED_LINES) == ["install", "register", "consent", "launch", "remove"]
    lines = [prefix for group in driver.EXPECTED_LINES.values() for prefix in group] + [
        "TRACER_LANDING_TEARDOWN_OK"
    ]
    transcript = ("\n".join(lines) + "\n").encode()
    assert driver.transcript_problem(transcript.decode()) is None
    for broken in (
        [*lines[:-1], "TRACER_PLAYWRIGHT_LAUNCH_UNPROVEN", lines[-1]],
        [lines[0], *lines],
        [lines[0], lines[2], lines[1], *lines[3:]],
        [*lines, lines[-1]],
    ):
        assert driver.transcript_problem("\n".join(broken)) is not None
    digest = e2e_evidence.transcript_digest(transcript)
    summary = (
        "## Orchestrator verification\n"
        f"playwright-container: PASS (2026-11-21; transcript {digest})\n"
    )
    assert driver.gate_problem(summary, transcript) is None
    assert driver.gate_problem(summary.replace("playwright-container", "aws-container"), transcript)
    assert driver.gate_problem(summary.replace("2026-11-21", "2026-02-30"), transcript)
    assert driver.gate_problem(summary, transcript + b"\n")


def test_the_driver_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert driver.accepts(["lifecycle"]) and not driver.accepts([]) and not driver.accepts(["bad"])
    monkeypatch.setattr(driver, "in_container", lambda: False)
    assert driver.main(["lifecycle"]) == 2
    assert (
        "ERROR the playwright-mcp driver runs only inside the disposable container"
        in capsys.readouterr().out
    )
    assert driver.main(["bad"]) == 2 and "usage:" in capsys.readouterr().err
    monkeypatch.setattr(driver, "in_container", lambda: True)
    for line in ("X_FAILED", "X_UNPROVEN"):
        monkeypatch.setattr(driver, "_HANDLERS", {"lifecycle": lambda line=line: [line]})
        assert driver.main(["lifecycle"]) == 1


def test_bun_global_bin_dir_is_not_residue_but_a_file_inside_it_is() -> None:
    """The real run left bun's empty `.bun/bin/` after the removal; that is bun's own directory."""
    assert driver.residue_paths([".bun/bin/", ".local/share/tools-installer/"]) == []
    assert driver.residue_paths([".bun/bin/", ".bun/bin/playwright-mcp", ".config/chromium/"]) == [
        ".bun/bin/playwright-mcp",
        ".config/chromium/",
    ]
