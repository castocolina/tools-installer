"""Host-side checks of the AWS container evidence."""

import re
import shlex
import subprocess
from pathlib import Path

import pytest

from tests import e2e_aws_cli_driver as d
from tests.e2e_evidence import transcript_digest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts/container-e2e-verify.sh"
PATHS = (".local/share/aws-cli", ".local/bin/aws", ".local/bin/aws_completer")
LINES = (
    "TRACER_AWS_INSTALL_OK method=script version=aws-cli/2.1",
    "TRACER_AWS_RERUN_OK",
    "TRACER_AWS_REMOVE_OK",
    "TRACER_AWS_NOGPG_OK",
    "TRACER_LANDING_TEARDOWN_OK",
)


def test_install_verdict_ok_and_each_problem() -> None:
    def check(
        rc: int = 0,
        version: str = "aws-cli/2.1",
        binary: str = ".local/bin/aws",
        paths: tuple[str, ...] = PATHS,
        log: str = "gpg --verify signature",
    ) -> str:
        return d.install_verdict("script", rc, version, binary, PATHS, paths, log)

    assert check().startswith(LINES[0])
    for line, detail in (
        (check(rc=1), "exit"),
        (check(version="aws-cli/1.0"), "version"),
        (check(binary="elsewhere"), "binary"),
        (check(paths=PATHS[:2]), "aws_completer"),
        (check(log="gpg --import"), "verify"),
        (check(log=""), "verify"),
    ):
        assert "_FAILED" in line and detail in line


def test_rerun_verdict() -> None:
    assert d.rerun_verdict(0, "tree", "tree", "config", "config") == LINES[1]
    for args, detail in (
        ((1, "a", "a", "b", "b"), "exit"),
        ((0, "a", "x", "b", "b"), "tree"),
        ((0, "a", "a", "b", "x"), ".aws"),
    ):
        line = d.rerun_verdict(*args)
        assert "_FAILED" in line and detail in line


def test_remove_verdict_ok_and_each_problem() -> None:
    seed = {".aws/config": "one", ".aws/credentials": "two"}

    def check(
        sweep: str = "",
        left: tuple[str, ...] = (),
        receipt: bool = False,
        current: dict[str, str] = seed,
        after: tuple[str, ...] = (),
    ) -> str:
        return d.remove_verdict(sweep, left, receipt, seed, current, (), after, ("allowed",))

    assert check(after=("allowed/file",)) == LINES[2]
    for line, detail in (
        (check(sweep="denied"), "denied"),
        (check(left=("aws",)), "aws"),
        (check(receipt=True), "receipt"),
        (check(current={**seed, ".aws/config": "changed"}), ".aws/config"),
        (check(current={".aws/config": "one"}), ".aws/credentials"),
        (check(after=("rogue",)), "rogue"),
    ):
        assert "_FAILED" in line and detail in line


def layout(before: str = "", script: str = "gpg not found", after: str = "") -> str:
    return (
        f"TRACER_AWS_NOGPG_BEFORE\n{before}\nTRACER_AWS_NOGPG_SCRIPT\n{script}\n"
        f"TRACER_AWS_NOGPG_AFTER\n{after}\nTRACER_AWS_NOGPG_END\n"
    )


def test_nogpg_verdict() -> None:
    assert d.nogpg_verdict(1, layout()) == LINES[3]
    assert d.nogpg_verdict(1, layout("old", after="old")) == LINES[3]
    cases = [
        (0, layout(), "exit"),
        (1, layout(script="error"), "gpg not found"),
        (1, layout(script="gpg not found; installed the CLI"), "installed"),
        (1, layout(after="/usr/local/bin/aws\n~/.local/share/aws-cli/dist"), "aws"),
        (1, layout().replace("TRACER_AWS_NOGPG_BEFORE\n", ""), "marker"),
        (
            1,
            layout().replace(
                "TRACER_AWS_NOGPG_SCRIPT\n", "TRACER_AWS_NOGPG_SCRIPT\nTRACER_AWS_NOGPG_SCRIPT\n"
            ),
            "marker",
        ),
        (1, layout().replace("TRACER_AWS_NOGPG_END", ""), "marker"),
        (
            1,
            layout()
            .replace("TRACER_AWS_NOGPG_SCRIPT", "X")
            .replace("TRACER_AWS_NOGPG_AFTER", "TRACER_AWS_NOGPG_SCRIPT")
            .replace("X", "TRACER_AWS_NOGPG_AFTER"),
            "marker",
        ),
    ]
    for rc, text, detail in cases:
        line = d.nogpg_verdict(rc, text)
        assert "_FAILED" in line and detail in line


def test_transcript_problem_reads_the_recorded_run() -> None:
    assert d.transcript_problem("\n".join(LINES)) is None
    for i in range(4):
        assert d.transcript_problem("\n".join(LINES[:i] + LINES[i + 1 :])) is not None
    for bad in ("X_FAILED", "X_UNPROVEN", "TRACER_LANDING_INFEASIBLE"):
        assert bad in str(d.transcript_problem("\n".join((bad, *LINES))))
    assert d.transcript_problem("\n".join((*LINES, "later"))) is not None


def test_transcript_problem_requires_each_verdict_once_and_in_order() -> None:
    for bad in (
        (LINES[0], LINES[0], *LINES[1:]),
        (LINES[0], LINES[1], LINES[1], *LINES[2:]),
        (LINES[0], LINES[1], LINES[3], LINES[2], LINES[4]),
        (LINES[1], LINES[0], *LINES[2:]),
        (*LINES, LINES[4]),
        ("unrelated " + LINES[0], *LINES[1:]),
    ):
        assert d.transcript_problem("\n".join(bad)) is not None
    assert d.transcript_problem("\n".join(LINES)) is None


def test_transcript_problem_requires_the_exact_teardown_line() -> None:
    for end in (LINES[-1] + " extra", " " + LINES[-1], LINES[-1] + "\nlater"):
        assert d.transcript_problem("\n".join((*LINES[:-1], end))) is not None
    for blanks in ("\n", "\n \n\t\n"):
        assert d.transcript_problem("\n".join(LINES) + blanks) is None
    assert d.transcript_problem("\n".join((LINES[0], "", *LINES[1:]))) is None


def test_gate_problem_accepts_one_pass_line_and_names_each_defect() -> None:
    transcript = ("\n".join(LINES) + "\n").encode()
    digest = transcript_digest(transcript)
    line = f"aws-container: PASS (2026-11-21; transcript {digest})"
    summary = f"## Orchestrator verification\n{line}\n## Next\n"
    assert d.gate_problem(summary, transcript) is None
    assert d.gate_problem(summary.replace(")", "; note)"), transcript) is None
    cases = [
        (None, transcript),
        (summary, None),
        (line, transcript),
        ("## Orchestrator verification\n", transcript),
        (summary.replace(line, line + "\n" + line), transcript),
        (line + "\n## Orchestrator verification\n", transcript),
        (summary.replace("PASS", "FAIL"), transcript),
        (summary.replace(line, "aws-container: not run"), transcript),
        *[
            (summary.replace("2026-11-21", date), transcript)
            for date in ("2026-02-30", "2026-99-99", "20261121")
        ],
        *[
            (summary.replace(digest, value), transcript)
            for value in (digest[:11], digest + "0", "a" * 13, digest.upper())
        ],
        *[(summary.replace(")", f"; {note})"), transcript) for note in ("UNPROVEN", "INFEASIBLE")],
        (summary, transcript + b"\n"),
    ]
    for text, data in cases:
        assert d.gate_problem(text, data) is not None


def test_the_driver_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(d, "in_container", lambda: False)
    assert d.accepts(["lifecycle"]) and d.accepts(["nogpg-verdict", "1", "path"])
    assert not any(
        d.accepts(args) for args in ([], ["other"], ["lifecycle", "x"], ["nogpg-verdict", "1"])
    )
    assert d.main(["lifecycle"]) == 2
    assert (
        "ERROR the aws-cli driver runs only inside the disposable container"
        in capsys.readouterr().out
    )
    path = tmp_path / "output"
    for text, rc in ((layout(), 0), (layout(after="new"), 1), ("nothing", 1)):
        path.write_text(text)
        assert d.main(["nogpg-verdict", "1", str(path)]) == rc
        assert ("_OK" if rc == 0 else "_FAILED") in capsys.readouterr().out
    assert d.main(["bad"]) == 2
    assert "usage:" in capsys.readouterr().err


def shell_function(name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", SCRIPT.read_text(), re.M | re.S)
    assert match is not None, name
    return match.group()


def run_shell(code: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "harness.sh"
    path.write_text(code)
    return subprocess.run(
        ["bash", str(path)], cwd=tmp_path, capture_output=True, text=True, check=False
    )


def test_aws_cli_is_registered_and_runs_the_lifecycle_and_the_nogpg_leg(tmp_path: Path) -> None:
    text = SCRIPT.read_text()
    assert 'aws-cli) cmd_aws_cli "$@" ;;' in text
    body = shell_function("cmd_aws_cli")
    script = f"""set -euo pipefail
LANDING_IMAGE=fedora:latest
REPO_ROOT={shlex.quote(str(tmp_path))}
LANDING_KEEP_IMAGE=0
{body}
ensure_phase_dir() {{ mkdir -p "$PHASE_DIR"; }}
landing_note_image() {{ echo note; }}
landing_bootstrap() {{ echo bootstrap; }}
landing_stage() {{ echo "$*"; }}
landing_step() {{ echo "$*"; }}
aws_nogpg_leg() {{ echo nogpg; }}
aws_cli_exit() {{ :; }}
die() {{ echo "$*" >&2; exit 2; }}
cmd_aws_cli
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "note",
        "bootstrap",
        "aws-cli-root aws_cli_root_setup",
        "lifecycle lifecycle",
        "nogpg",
    ]
    result = run_shell(script.replace("cmd_aws_cli\n", "cmd_aws_cli --bad\n"), tmp_path)
    assert result.returncode != 0 and "unknown aws-cli option" in result.stderr


def test_aws_cli_root_setup_installs_only_what_the_box_needs(tmp_path: Path) -> None:
    body = shell_function("aws_cli_root_setup")
    result = run_shell(
        f"""{body}
exec_root() {{ printf '%s\\n' "$*"; }}
aws_cli_root_setup
""",
        tmp_path,
    )
    assert result.returncode == 0
    assert result.stdout.count("dnf install -y unzip gnupg2") == 1
    assert all(
        x in result.stdout
        for x in (
            "/usr/local/bin/gpg",
            "/var/tmp/tools-installer-e2e-aws-gpg.log",
            '/usr/bin/gpg "$@"',
            "0755",
        )
    )


def trap_run(
    tmp_path: Path,
    status: int,
    listing: str = "",
    negative: bool = False,
    name: str = "tools-installer-e2e-aws-nogpg-4242",
    rm_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    trap = (
        shell_function("aws_cli_exit")
        if not negative
        else """aws_cli_exit() {
  local rc=$?
  aws_nogpg_cleanup
  (exit "$rc"); landing_teardown
}
"""
    )
    script = f"""set -euo pipefail
LANDING_CONTAINER_NAME=tools-installer-e2e-aws-cli-4242
AWS_NOGPG_NAME={shlex.quote(name)}
AWS_NOGPG_IMAGE=debian
AWS_NOGPG_PULLED=0
LANDING_IMAGE=fedora
LANDING_PULLED=0
LANDING_KEEP_IMAGE=0
LANDING_EXTRA_LEFT=
LANDING_TRANSCRIPT={shlex.quote(str(tmp_path / "transcript"))}
ct() {{
  echo "$*" >> {shlex.quote(str(tmp_path / "calls"))}
  if [[ "$1" == ps && "$*" == *aws-nogpg* ]]; then
    {listing or ":"}
  elif [[ "$1" == rm && "$*" == *aws-nogpg* && {int(rm_fail)} == 1 ]]; then return 1
  fi
}}
{shell_function("landing_teardown")}
{shell_function("aws_nogpg_cleanup")}
{trap}
trap aws_cli_exit EXIT
exit {status}
"""
    return run_shell(script, tmp_path)


@pytest.mark.parametrize("status", [0, 1, 3])
def test_the_exit_trap_runs_both_cleanups_under_errexit_and_keeps_the_status(
    tmp_path: Path, status: int
) -> None:
    result = trap_run(tmp_path, status)
    assert result.returncode == status
    calls = (tmp_path / "calls").read_text().splitlines()
    assert calls.index("rm -f tools-installer-e2e-aws-nogpg-4242") < calls.index(
        "rm -f tools-installer-e2e-aws-cli-4242"
    )
    assert (tmp_path / "transcript").read_text().splitlines()[-1] == "TRACER_LANDING_TEARDOWN_OK"
    (tmp_path / "calls").unlink()
    trap_run(tmp_path, 1, negative=True)
    assert "rm -f tools-installer-e2e-aws-cli-4242" not in (tmp_path / "calls").read_text()


@pytest.mark.parametrize(
    ("listing", "expected"),
    [
        ("echo tools-installer-e2e-aws-nogpg-4242", "tools-installer-e2e-aws-nogpg-4242"),
        ("return 1", "tools-installer-e2e-aws-nogpg-4242 unverified"),
    ],
)
def test_a_nogpg_box_that_is_still_listed_or_unlistable_fails_the_marker(
    tmp_path: Path, listing: str, expected: str
) -> None:
    result = trap_run(tmp_path, 0, listing)
    transcript = (tmp_path / "transcript").read_text()
    assert result.returncode != 0
    assert transcript.splitlines()[-1] == "TRACER_LANDING_TEARDOWN_LEFT container=" + expected
    assert "TRACER_LANDING_TEARDOWN_OK" not in transcript


def test_cleanup_uses_listing_as_proof_and_tolerates_no_name(tmp_path: Path) -> None:
    assert trap_run(tmp_path, 0, rm_fail=True).returncode == 0
    assert (tmp_path / "transcript").read_text().splitlines()[-1] == "TRACER_LANDING_TEARDOWN_OK"
    (tmp_path / "calls").unlink()
    assert trap_run(tmp_path, 0, name="").returncode == 0
    assert "aws-nogpg" not in (tmp_path / "calls").read_text()
    assert (tmp_path / "transcript").read_text().splitlines()[-1] == "TRACER_LANDING_TEARDOWN_OK"


def test_the_names_and_removals_are_exact() -> None:
    text = SCRIPT.read_text()
    body = shell_function("cmd_aws_cli")
    assert "tools-installer-e2e-aws-cli-$$" in body
    assert "tools-installer-e2e-aws-nogpg-$$" in body
    assert "AWS_NOGPG_IMAGE=docker.io/library/debian:stable-slim" in text
    assert "--privileged" not in shell_function("aws_nogpg_leg")
    assert not re.search(r"podman system (?:reset|prune)|image prune|container prune", text)


def test_the_nogpg_leg_runs_the_vendor_script_without_gnupg() -> None:
    body = shell_function("aws_nogpg_leg")
    for value in (
        "curl unzip ca-certificates",
        "https://awscli.amazonaws.com/v2/install.sh",
        "AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION=false",
        "aws-nogpg.out",
        "tests.e2e_aws_cli_driver",
        "nogpg-verdict",
        "landing_environmental",
        "landing_infeasible",
    ):
        assert value in body
    assert "--system" not in body
    assert body.count('find "$HOME/.local" /usr/local/bin /usr/local/aws-cli') == 2
    markers = [
        body.index(x)
        for x in (
            "TRACER_AWS_NOGPG_BEFORE",
            "TRACER_AWS_NOGPG_SCRIPT",
            "TRACER_AWS_NOGPG_AFTER",
            "TRACER_AWS_NOGPG_END",
        )
    ]
    assert markers == sorted(markers)


def test_nogpg_leg_handles_network_failure_and_records_verdict(tmp_path: Path) -> None:
    script = f"""set -euo pipefail
AWS_NOGPG_IMAGE=debian
AWS_NOGPG_NAME=box
AWS_NOGPG_PULLED=0
PHASE_DIR={shlex.quote(str(tmp_path))}
LANDING_TRANSCRIPT="$PHASE_DIR/transcript"
REPO_ROOT="$PHASE_DIR"
ct() {{
  if [[ "$1" == image ]]; then return 1; fi
  echo "${{OUTPUT}}"
  return 1
}}
landing_environmental() {{ [[ "$1" == *"curl: (6)"* ]]; }}
landing_infeasible() {{ echo "TRACER_LANDING_INFEASIBLE step=$1"; }}
uv() {{ echo "TRACER_AWS_NOGPG_OK"; }}
{shell_function("aws_nogpg_leg")}
OUTPUT="curl: (6) failed"; aws_nogpg_leg
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 2 and "TRACER_LANDING_INFEASIBLE" in result.stdout
    script = script.replace('OUTPUT="curl: (6) failed"', 'OUTPUT="gpg not found"')
    result = run_shell(script, tmp_path)
    assert result.returncode == 0 and "TRACER_AWS_NOGPG_OK" in result.stdout


def test_main_dispatches_aws_cli(tmp_path: Path) -> None:
    script = f"""set -euo pipefail
{shell_function("main")}
select_distro() {{ :; }}
cmd_aws_cli() {{ printf 'dispatched:%s\\n' "$*"; }}
main aws-cli --keep-image
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "dispatched:--keep-image\n"


@pytest.mark.parametrize("aws_pulled", [0, 1])
@pytest.mark.parametrize("fedora_pulled", [0, 1])
@pytest.mark.parametrize("keep", [0, 1])
def test_cleanup_removes_only_pulled_images(
    tmp_path: Path, aws_pulled: int, fedora_pulled: int, keep: int
) -> None:
    script = f"""set -euo pipefail
LANDING_CONTAINER_NAME=tools-installer-e2e-aws-cli-4242
AWS_NOGPG_NAME=tools-installer-e2e-aws-nogpg-4242
AWS_NOGPG_IMAGE=docker.io/library/debian:stable-slim
AWS_NOGPG_PULLED={aws_pulled}
LANDING_IMAGE=fedora:latest
LANDING_PULLED={fedora_pulled}
LANDING_KEEP_IMAGE={keep}
LANDING_EXTRA_LEFT=
LANDING_TRANSCRIPT={shlex.quote(str(tmp_path / "transcript"))}
ct() {{ printf '%s\\n' "$*" >> {shlex.quote(str(tmp_path / "calls"))}; }}
{shell_function("landing_teardown")}
{shell_function("aws_nogpg_cleanup")}
{shell_function("aws_cli_exit")}
trap aws_cli_exit EXIT
exit 0
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert [line for line in calls if line.startswith("rm ")] == [
        "rm -f tools-installer-e2e-aws-nogpg-4242",
        "rm -f tools-installer-e2e-aws-cli-4242",
    ]
    images: list[str] = []
    if aws_pulled and not keep:
        images.append("rmi docker.io/library/debian:stable-slim")
    if fedora_pulled and not keep:
        images.append("rmi fedora:latest")
    assert [line for line in calls if line.startswith("rmi ")] == images
    assert sum(line.startswith("ps -a ") for line in calls) == 2
    assert (tmp_path / "transcript").read_text().splitlines()[-1] == "TRACER_LANDING_TEARDOWN_OK"


def test_nogpg_leg_executes_complete_container_command_with_stubbed_runtime(tmp_path: Path) -> None:
    script = f'''set -euo pipefail
AWS_NOGPG_IMAGE=docker.io/library/debian:stable-slim
AWS_NOGPG_NAME=tools-installer-e2e-aws-nogpg-4242
AWS_NOGPG_PULLED=0
PHASE_DIR={shlex.quote(str(tmp_path))}
LANDING_TRANSCRIPT="$PHASE_DIR/transcript"
REPO_ROOT="$PHASE_DIR"
ct() {{
  if [[ "$1" == image ]]; then return 1; fi
  printf '%s\\n' "$1" "$2" "$3" "$4" "$5" "$6" > "$PHASE_DIR/argv"
  [[ $# == 7 && "$6" == -c ]] || return 99
  bash -c 'apt-get() {{ echo "apt-get $*" >&2; }}
    curl() {{ echo "curl $*" >&2; }}
    find() {{ echo "$*" >> "{shlex.quote(str(tmp_path))}/find-args"; printf "existing\\n"; }}
    bash() {{ echo "vendor env=$AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION args=$*" >&2
      echo "gpg not found"; return 7; }}
    '"$7"
}}
landing_environmental() {{ return 1; }}
uv() {{ printf '%s\\n' "$*" > "$PHASE_DIR/uv-args"; echo TRACER_AWS_NOGPG_OK; }}
{shell_function("aws_nogpg_leg")}
aws_nogpg_leg
'''
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "argv").read_text().splitlines() == [
        "run",
        "--name",
        "tools-installer-e2e-aws-nogpg-4242",
        "docker.io/library/debian:stable-slim",
        "sh",
        "-c",
    ]
    output = (tmp_path / "aws-nogpg.out").read_text()
    assert "apt-get install -y curl unzip ca-certificates" in output
    assert "curl -fsSL https://awscli.amazonaws.com/v2/install.sh -o /tmp/aws-install.sh" in output
    assert "vendor env=false args=/tmp/aws-install.sh" in output
    # The real run on Debian failed when the vendor script ran under dash: it must run under bash.
    assert "bash /tmp/aws-install.sh" in shell_function("aws_nogpg_leg")
    assert " sh /tmp/aws-install.sh" not in shell_function("aws_nogpg_leg")
    assert output.count("existing\n") == 2
    assert (tmp_path / "find-args").read_text().splitlines() == [
        f"{Path.home()}/.local /usr/local/bin /usr/local/aws-cli"
    ] * 2
    assert d.nogpg_verdict(7, output) == "TRACER_AWS_NOGPG_OK"
    assert "nogpg-verdict 7 " in (tmp_path / "uv-args").read_text()
    assert (tmp_path / "transcript").read_text() == "TRACER_AWS_NOGPG_OK\n"


def test_the_usage_names_every_verdict_the_driver_expects() -> None:
    usage = shell_function("usage")
    assert "aws-cli [--keep-image]" in usage and "Orchestrator only" in usage
    for prefixes in d.EXPECTED_LINES.values():
        for prefix in prefixes:
            assert prefix.split()[0] in usage


def test_the_generic_skip_list_includes_aws_cli(tmp_path: Path) -> None:
    text = SCRIPT.read_text()
    match = re.search(r"^GENERIC_SKIP_TOOLS=(.*)$", text, re.M)
    assert match is not None and {"herdr-app", "aws-cli"} <= set(match.group(1).split(","))
    assert all(
        x in " ".join(text[: match.start()].splitlines()[-5:])
        for x in ("herdr-app", "herdr-core", "target")
    )
    awk = re.search(r"^GENERIC_SKIP_AWK='\n(.*?)^'\s*$", text, re.M | re.S)
    assert awk is not None
    fixture = '# aws comment\n[[tool]]\nid = "aws-cli"\n# other comment\n[[tool]]\nid = "other"\n'
    program = tmp_path / "filter.awk"
    source = tmp_path / "registry.toml"
    program.write_text(awk.group(1))
    source.write_text(fixture)
    result = run_shell(
        f"awk -v {shlex.quote('skip=' + match.group(1))} "
        f"-f {shlex.quote(str(program))} {shlex.quote(str(source))}\n",
        tmp_path,
    )
    assert result.returncode == 0 and result.stdout == '# other comment\n[[tool]]\nid = "other"\n'
