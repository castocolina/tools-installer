"""Host-only tests for the Bruno lifecycle evidence."""

import re
import shlex
from pathlib import Path

import pytest

from tests import e2e_bruno_driver as driver
from tests.e2e_evidence import transcript_digest
from tests.e2e_landing_driver import Failed
from tests.test_container_e2e_aws_cli import run_shell, shell_function

SCRIPT = Path(__file__).resolve().parent.parent / "scripts/container-e2e-verify.sh"


def test_install_verdict_ok_and_each_problem(tmp_path: Path) -> None:
    binary = tmp_path / "bruno"
    binary.write_text("binary")
    binary.chmod(0o755)
    for arch in ("amd64", "arm64"):
        assert driver.install_verdict("INSTALLED", "tarball", binary, [binary], arch) == (
            f"TRACER_BRUNO_INSTALL_OK method=tarball version=4.3.0 arch={arch}"
        )
    for status, kind, path, receipt, arch, detail in (
        ("FAILED", "tarball", binary, [binary], "amd64", "FAILED"),
        ("INSTALLED", "cask", binary, [binary], "amd64", "cask"),
        ("INSTALLED", "tarball", tmp_path / "missing", [], "amd64", "missing"),
        ("INSTALLED", "tarball", binary, [], "amd64", "receipt"),
        ("INSTALLED", "tarball", binary, [binary], "riscv64", "riscv64"),
    ):
        line = driver.install_verdict(status, kind, path, receipt, arch)
        assert "TRACER_BRUNO_INSTALL_FAILED" in line and detail in line
    binary.chmod(0o644)
    assert "executable" in driver.install_verdict("INSTALLED", "tarball", binary, [binary], "amd64")


def test_run_verdict_reports_unproven_with_each_mode() -> None:
    attempts = [
        driver.RunAttempt("as-is", 1, "libfuse.so.2 missing"),
        driver.RunAttempt("no-sandbox", 2, "FUSE failed"),
        driver.RunAttempt("extract", None, "display absent"),
        driver.RunAttempt("extract-no-sandbox", 0, "not a version"),
    ]
    line = driver.run_verdict(attempts)
    assert line.startswith("TRACER_BRUNO_RUN_UNPROVEN detail=")
    for value in (
        "as-is",
        "1",
        "libfuse.so.2 missing",
        "no-sandbox",
        "FUSE failed",
        "extract",
        "timeout",
        "display absent",
        "extract-no-sandbox",
    ):
        assert value in line
    assert driver.run_verdict([]) == "TRACER_BRUNO_RUN_UNPROVEN detail=no mode ran"
    assert (
        driver.run_verdict(
            [driver.RunAttempt("a", 0, "Bruno 4.3.0"), driver.RunAttempt("b", 0, "4.4")]
        )
        == "TRACER_BRUNO_RUN_OK mode=a"
    )
    assert "x" * 121 not in driver.run_verdict([driver.RunAttempt("a", 1, "x" * 121)])


def test_run_modes_never_use_an_appimage_runtime_flag() -> None:
    assert [(m.name, m.env, m.args) for m in driver.MODES] == [
        ("as-is", {}, ("--version",)),
        ("no-sandbox", {}, ("--no-sandbox", "--version")),
        ("extract", {"APPIMAGE_EXTRACT_AND_RUN": "1"}, ("--version",)),
        ("extract-no-sandbox", {"APPIMAGE_EXTRACT_AND_RUN": "1"}, ("--no-sandbox", "--version")),
    ]
    assert all(not a.startswith("--" + "appimage") for m in driver.MODES for a in m.args)


def test_remove_verdict_ok_and_each_problem() -> None:
    seed = {
        "Documents/bruno/collection.json": "collection",
        ".config/bruno/preferences.json": "settings",
    }

    def check(
        sweep: str | None = None,
        paths: tuple[str, ...] = (),
        receipt: bool = False,
        after: list[str] | None = None,
        current: dict[str, str | None] | None = None,
    ) -> str:
        return driver.remove_verdict(
            sweep_problem=sweep,
            paths_left=paths,
            receipt_left=receipt,
            before=list(seed),
            after=after if after is not None else list(seed),
            allowed=[],
            seeded=seed,
            current=current if current is not None else seed,
        )

    assert check() == "TRACER_BRUNO_REMOVE_OK"
    cases = [
        (check(sweep="sweep failed"), "sweep failed"),
        (check(paths=("binary",)), "binary"),
        (check(receipt=True), "receipt"),
        (check(after=[*seed, "residue"]), "residue"),
    ]
    cases.extend(
        (check(current={**seed, name: value}), name) for name in seed for value in (None, "changed")
    )
    for line, detail in cases:
        assert "TRACER_BRUNO_REMOVE_FAILED" in line and detail in line


def test_an_engine_smoke_failure_is_unproven_and_the_removal_still_judges() -> None:
    calls: list[str] = []

    def install() -> str:
        raise Failed(
            "TRACER_BRUNO_INSTALL_FAILED",
            "bruno install ended FAILED: smoke run failed for /h/.local/bin/bruno.new (exit 127): "
            "error while loading shared libraries: libfuse.so.2: cannot open shared object file",
        )

    def run() -> list[driver.RunAttempt]:
        calls.append("run")
        return [driver.RunAttempt("as-is", 0, "4.3")]

    def remove() -> str | None:
        calls.append("remove")
        return None

    def state() -> driver.LifecycleState:
        return driver.LifecycleState(False, False, "TRACER_BRUNO_REMOVE_OK")

    lines = driver.lifecycle_steps(install, run, remove, state)
    assert lines == [
        "TRACER_BRUNO_INSTALL_UNPROVEN detail=engine-smoke-failed: "
        "error while loading shared libraries: libfuse.so.2: cannot open shared object file",
        "TRACER_BRUNO_RUN_UNPROVEN detail=no mode ran",
        "TRACER_BRUNO_REMOVE_OK",
    ]
    assert not calls
    lines = driver.lifecycle_steps(
        install,
        run,
        remove,
        lambda: driver.LifecycleState(False, False, "TRACER_BRUNO_REMOVE_FAILED detail=residue"),
    )
    assert "residue" in lines[-1]
    lines = driver.lifecycle_steps(
        install, run, remove, lambda: driver.LifecycleState(True, False, "TRACER_BRUNO_REMOVE_OK")
    )
    assert "TRACER_BRUNO_RUN_OK" in lines[1] and calls == ["run"]

    def fail() -> str:
        raise Failed("TRACER_BRUNO_INSTALL_FAILED", "checksum mismatch")

    calls.clear()
    assert driver.lifecycle_steps(fail, run, remove, state) == [
        "TRACER_BRUNO_INSTALL_FAILED detail=checksum mismatch"
    ]
    assert not calls


def transcript(mode: str = "as-is", arch: str = "amd64") -> bytes:
    return (
        f"TRACER_BRUNO_INSTALL_OK method=tarball version=4.3.0 arch={arch}\n"
        f"TRACER_BRUNO_RUN_OK mode={mode}\nTRACER_BRUNO_REMOVE_OK\nTRACER_LANDING_TEARDOWN_OK\n"
    ).encode()


def summary(data: bytes, date: str = "2026-11-21") -> str:
    return (
        f"## Orchestrator verification\nbruno-container: PASS ({date}; "
        f"transcript {transcript_digest(data)})\n"
    )


def test_recorded_smoke_mode_reads_only_a_digest_bound_pass() -> None:
    for mode in ("as-is", "no-sandbox", "extract", "extract-no-sandbox"):
        data = transcript(mode)
        assert driver.recorded_smoke_mode(summary(data), data) == mode
    data = transcript()
    good = summary(data)
    for text, payload in [
        (None, data),
        (good, None),
        (good.replace("PASS", "UNPROVEN"), data),
        (good.replace(transcript_digest(data), "0" * 12), data),
        (good.replace(transcript_digest(data), "a" * 11), data),
        (good.replace(transcript_digest(data), "a" * 13), data),
        (good, data + b"altered"),
        (summary(data, "2026-02-30"), data),
        (good + good.splitlines()[1] + "\n", data),
        (good.replace("## Orchestrator verification\n", ""), data),
        (
            good.replace("## Orchestrator verification\n", "## Other\n")
            + "## Orchestrator verification\n",
            data,
        ),
    ]:
        assert driver.recorded_smoke_mode(text, payload) is None
    for bad in (
        data.replace(
            b"TRACER_BRUNO_REMOVE_OK", b"TRACER_BRUNO_RUN_OK mode=as-is\nTRACER_BRUNO_REMOVE_OK"
        ),
        data.replace(b"RUN_OK", b"RUN_UNPROVEN"),
        transcript("unknown"),
    ):
        assert driver.recorded_smoke_mode(summary(bad), bad) is None


def test_recorded_smoke_arch_reads_only_a_verified_record() -> None:
    for arch in ("amd64", "arm64"):
        data = transcript(arch=arch)
        assert driver.recorded_smoke_arch(summary(data), data) == arch
    for data in (
        transcript(arch="riscv64"),
        transcript().replace(b" arch=amd64", b""),
        transcript().replace(
            b"TRACER_BRUNO_RUN_OK",
            b"TRACER_BRUNO_INSTALL_OK method=tarball version=4.3.0 arch=amd64\nTRACER_BRUNO_RUN_OK",
        ),
    ):
        assert driver.recorded_smoke_arch(summary(data), data) is None
    data = transcript()
    assert driver.recorded_smoke_arch(summary(data), data + b"x") is None
    assert driver.recorded_smoke_arch(None, None) is None
    assert driver.recorded_smoke_arch(summary(transcript("unknown")), transcript("unknown")) is None


def test_smoke_argv_for_applies_only_a_mode_the_shipped_smoke_reproduces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert driver.smoke_argv_for("as-is") is None
    assert driver.smoke_argv_for("no-sandbox") == ("--no-sandbox", "--version")
    assert driver.smoke_argv_for("extract") is None
    assert driver.smoke_argv_for("extract-no-sandbox") is None
    with pytest.raises(ValueError):
        driver.smoke_argv_for("unknown")
    monkeypatch.setattr(
        driver,
        "MODES",
        (
            driver.RunMode("plain", {}, ("--other",)),
            driver.RunMode("env", {"A": "1"}, ("--other",)),
        ),
    )
    result = driver.smoke_argv_for("plain")
    assert result is not None
    assert result == ("--other",) and all(re.fullmatch(r"[A-Za-z0-9=._:/+-]+", a) for a in result)
    assert driver.smoke_argv_for("env") is None


def test_the_driver_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert driver.accepts(["lifecycle"]) and not driver.accepts(["lifecycle", "extra"])
    monkeypatch.setattr(driver, "in_container", lambda: False)
    assert driver.main(["lifecycle"]) == 2
    assert (
        "ERROR the bruno driver runs only inside the disposable container"
        in capsys.readouterr().out
    )
    assert driver.main(["bad"]) == 2 and "usage" in capsys.readouterr().err
    monkeypatch.setattr(driver, "in_container", lambda: True)
    for line in ("TRACER_BRUNO_INSTALL_FAILED", "TRACER_BRUNO_RUN_UNPROVEN"):
        monkeypatch.setitem(driver.HANDLERS, "lifecycle", lambda line=line: [line])
        assert driver.main(["lifecycle"]) == 1


def test_bruno_is_registered_and_runs_one_lifecycle_step(tmp_path: Path) -> None:
    body = shell_function("cmd_bruno")
    script = f"""set -euo pipefail
LANDING_IMAGE=fedora:latest
REPO_ROOT={shlex.quote(str(tmp_path))}
LANDING_KEEP_IMAGE=0
{body}
ensure_phase_dir() {{ mkdir -p "$PHASE_DIR"; }}
bruno_run_args() {{ :; }}
landing_note_image() {{ echo note; }}
landing_bootstrap() {{ echo bootstrap; }}
landing_stage() {{ echo "$*"; }}
landing_step() {{ echo "$*"; }}
landing_teardown() {{ :; }}
die() {{ echo "$*" >&2; exit 2; }}
cmd_bruno
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "note",
        "bootstrap",
        "bruno-root bruno_root_setup",
        "lifecycle lifecycle",
    ]
    assert "LANDING_DRIVER_MODULE=tests.e2e_bruno_driver" in body
    result = run_shell(script.replace("cmd_bruno\n", "cmd_bruno --bad\n"), tmp_path)
    assert result.returncode != 0 and "unknown bruno option" in result.stderr
    dispatch = f"""set -euo pipefail
{shell_function("main")}
select_distro() {{ :; }}
cmd_bruno() {{ echo "dispatched:$*"; }}
main bruno --keep-image
"""
    assert run_shell(dispatch, tmp_path).stdout == "dispatched:--keep-image\n"


def test_bruno_root_setup_installs_only_the_libraries(tmp_path: Path) -> None:
    script = shell_function("bruno_root_setup") + '\nexec_root() { echo "$*"; }\nbruno_root_setup\n'
    result = run_shell(script, tmp_path)
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "dnf install -y fuse-libs gtk3 nss alsa-lib libXScrnSaver mesa-libgbm "
        "libdrm at-spi2-core cups-libs libxkbcommon"
    ]


@pytest.mark.parametrize("exists", [False, True])
def test_bruno_start_is_never_privileged_and_passes_fuse_only_when_present(
    tmp_path: Path, exists: bool
) -> None:
    host = tmp_path / "fuse"
    if exists:
        host.touch()
    script = f"""set -euo pipefail
BRUNO_HOST_FUSE={shlex.quote(str(host))}
{shell_function("bruno_run_args")}
bruno_run_args
printf "%s\n" "${{CONTAINER_RUN_ARGS[@]}}"
"""
    result = run_shell(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["--security-opt", "label=disable"] + (
        ["--device", "/dev/fuse"] if exists else []
    )
    assert "--privileged" not in result.stdout
    if not exists:
        assert "TRACER_BRUNO_RUN_UNPROVEN" in result.stderr and "as-is" in result.stderr


@pytest.mark.parametrize("pulled", [0, 1])
@pytest.mark.parametrize("keep", [0, 1])
def test_the_names_and_removals_are_exact(tmp_path: Path, pulled: int, keep: int) -> None:
    text = SCRIPT.read_text()
    assert "tools-installer-e2e-bruno-$$" in shell_function("cmd_bruno")
    assert not re.search(r"podman system (?:reset|prune)|image prune|container prune", text)
    script = f"""set -euo pipefail
LANDING_CONTAINER_NAME=tools-installer-e2e-bruno-4242
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
    assert [c for c in calls if c.startswith("rm ")] == ["rm -f tools-installer-e2e-bruno-4242"]
    assert [c for c in calls if c.startswith("rmi ")] == (
        ["rmi fedora:latest"] if pulled and not keep else []
    )


def test_the_usage_names_every_verdict_the_driver_prints() -> None:
    usage = shell_function("usage").split("bruno [--keep-image]", 1)[1].split("-h, --help", 1)[0]
    assert "Orchestrator only" in usage
    for name in ("INSTALL_OK", "INSTALL_UNPROVEN", "RUN_OK", "RUN_UNPROVEN", "REMOVE_OK"):
        assert "TRACER_BRUNO_" + name in usage


def test_the_generic_skip_list_includes_bruno(tmp_path: Path) -> None:
    text = SCRIPT.read_text()
    matches = re.findall(r"^GENERIC_SKIP_TOOLS=(.*)$", text, re.M)
    assert len(matches) == 1 and {"herdr-app", "aws-cli", "bruno"} <= set(matches[0].split(","))
    before = text.split("GENERIC_SKIP_TOOLS=", 1)[0].splitlines()[-5:]
    assert all(word in " ".join(before) for word in ("herdr-app", "herdr-core", "target"))
    awk = re.search(r"^GENERIC_SKIP_AWK='\n(.*?)^'\s*$", text, re.M | re.S)
    assert awk is not None
    program = tmp_path / "filter.awk"
    program.write_text(awk.group(1))
    registry = tmp_path / "registry.toml"
    registry.write_text(
        '# bruno comment\n[[tool]]\nid = "bruno"\n# other comment\n[[tool]]\nid = "other"\n'
    )
    result = run_shell(
        f"awk -v {shlex.quote('skip=' + matches[0])} "
        f"-f {shlex.quote(str(program))} {shlex.quote(str(registry))}",
        tmp_path,
    )
    assert result.returncode == 0
    assert result.stdout == '# other comment\n[[tool]]\nid = "other"\n'
