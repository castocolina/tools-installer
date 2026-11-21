"""Host tests of the Ghostty driver; no container is started."""

import os
import re
import shlex
import shutil
import subprocess
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from installer.download import artifact_paths
from installer.terminal_regions import GHOSTTY, GHOSTTY_KEYS, marker
from tests import e2e_ghostty_driver as driver
from tests.e2e_landing_driver import Failed, tool_by_id


def test_install_verdict_ok() -> None:
    assert (
        driver.install_verdict("fuse", "tarball", 0, "Ghostty 1.4.0", [], [], "community build")
        == "TRACER_GHOSTTY_INSTALL_OK mode=fuse method=tarball version=Ghostty 1.4.0"
    )


@pytest.mark.parametrize(
    ("kind", "rc", "version", "missing", "receipt", "warning", "detail"),
    [
        ("tarball", 1, "Ghostty 1.4.0", [], [], "community build", "ghostty --version exited 1"),
        ("tarball", -1, "Ghostty 1.4.0", [], [], "community build", "ghostty --version exited -1"),
        (
            "github_release",
            0,
            "Ghostty 1.4.0",
            [],
            [],
            "community build",
            "method github_release is not tarball",
        ),
        ("tarball", 0, "", [], [], "community build", "ghostty --version printed nothing"),
        ("tarball", 0, "hello", [], [], "community build", "ghostty --version printed hello"),
        ("tarball", 0, "Ghostty 1.4.0", ["x"], [], "community build", "x is missing"),
        ("tarball", 0, "Ghostty 1.4.0", [], ["x"], "community build", "the receipt lacks x"),
        ("tarball", 0, "Ghostty 1.4.0", [], [], None, "the install note lacks community build"),
    ],
)
def test_install_verdict_names_each_problem(
    kind: str,
    rc: int,
    version: str,
    missing: list[str],
    receipt: list[str],
    warning: str | None,
    detail: str,
) -> None:
    for mode in ("fuse", "extract"):
        assert detail in driver.install_verdict(mode, kind, rc, version, missing, receipt, warning)


@pytest.mark.parametrize(
    ("rc", "out", "err", "device", "mount", "detail"),
    [
        (0, "Ghostty 1.4.0\n", "", True, True, None),
        (
            0,
            "Ghostty 1.4.0\n",
            "failed to utilize FUSE",
            True,
            True,
            "the AppImage fell back to extract-and-run; FUSE was not used",
        ),
        (1, "Ghostty 1.4.0\n", "", True, True, "ghostty --version exited 1"),
        (0, "", "", True, True, "ghostty --version did not print Ghostty 1.4.0"),
        (0, "Ghostty 1.4.0\n", "", False, False, "/dev/fuse is not present"),
        (0, "Ghostty 1.4.0\n", "", True, False, "no FUSE mount of the AppImage was observed"),
    ],
)
def test_fuse_verdict(
    rc: int, out: str, err: str, device: bool, mount: bool, detail: str | None
) -> None:
    expected = (
        "TRACER_GHOSTTY_FUSE_OK"
        if detail is None
        else f"TRACER_GHOSTTY_FUSE_UNPROVEN detail={detail}"
    )
    assert driver.fuse_verdict(rc, out, err, device, mount, "Ghostty 1.4.0") == expected


def test_printed_mount_point_takes_the_first_absolute_line() -> None:
    assert driver.printed_mount_point("\n/tmp/.mount_abc  \nmore") == "/tmp/.mount_abc"
    for text in ("", "\n", "not a path\n"):
        assert driver.printed_mount_point(text) is None


def test_fuse_mount_observed_reads_mountinfo() -> None:
    line = r"36 35 0:46 / /tmp/a\040b ro shared:99 - fuse.x /dev/fuse ro"
    assert driver.fuse_mount_observed(line, "/tmp/a b")
    assert driver.fuse_mount_observed(line.replace("fuse.x", "fuse"), "/tmp/a b")
    assert not driver.fuse_mount_observed(line.replace("fuse.x", "overlay"), "/tmp/a b")
    assert not driver.fuse_mount_observed(line, None)
    assert not driver.fuse_mount_observed("malformed", "/tmp/a b")


@pytest.mark.parametrize("kind", ["fuse.x", "overlay"])
def test_observe_fuse_mount_terminates_the_process_it_started(tmp_path: Path, kind: str) -> None:
    script, pid = tmp_path / "standin", tmp_path / "pid"
    script.write_text(
        f"#!/bin/sh\necho $$ > {pid}\necho /tmp/.mount_x\nexec sleep 30\n", encoding="utf-8"
    )
    script.chmod(0o755)
    assert driver.observe_fuse_mount(
        [str(script)],
        {"PATH": os.environ["PATH"]},
        lambda: f"1 2 0:3 / /tmp/.mount_x ro - {kind} src ro\n",
        10.0,
    ) == (kind == "fuse.x")
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)


def test_observe_fuse_mount_is_false_when_the_command_prints_nothing(tmp_path: Path) -> None:
    script = tmp_path / "empty"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    for path in (script, tmp_path / "missing"):
        assert not driver.observe_fuse_mount([str(path)], {}, lambda: "", 1.0)


def test_expected_version_line_is_the_pinned_version() -> None:
    assert driver.expected_version_line() == "Ghostty 1.4.0"


def test_baseline_lookup_hides_only_ghostty() -> None:
    lookup = driver.baseline_lookup(lambda name: f"/usr/bin/{name}")
    assert (
        lookup("ghostty") is None
        and lookup("zsh") == "/usr/bin/zsh"
        and lookup("kitty") == "/usr/bin/kitty"
    )


def test_run_lifecycle_runs_every_step_then_the_cleanup() -> None:
    assert driver.run_lifecycle([("P1", lambda: ["a"]), ("P2", lambda: ["b"])], lambda: ["c"]) == [
        "a",
        "b",
        "c",
    ]


@pytest.mark.parametrize("error", [OSError("boom"), ValueError("boom")])
def test_run_lifecycle_turns_a_step_error_into_its_failed_line_and_still_cleans_up(
    error: Exception,
) -> None:
    def fail() -> list[str]:
        raise error

    assert driver.run_lifecycle(
        [("P", lambda: ["a"]), ("TRACER_GHOSTTY_SYNC_FAILED", fail), ("P", lambda: ["c"])],
        lambda: ["z"],
    ) == ["a", "TRACER_GHOSTTY_SYNC_FAILED detail=boom", "c", "z"]
    assert driver.run_lifecycle([], fail)[-1] == "TRACER_GHOSTTY_REMOVE_FAILED detail=boom"


def test_run_lifecycle_cleans_up_when_a_step_raises_something_unexpected() -> None:
    calls: list[str] = []

    def fail() -> list[str]:
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        driver.run_lifecycle([("P", fail)], lambda: calls.append("cleanup") or [])
    assert calls == ["cleanup"]


def test_run_lifecycle_turns_a_failed_install_into_its_line_and_still_cleans_up() -> None:
    def fail() -> list[str]:
        raise Failed("TRACER_GHOSTTY_INSTALL_FAILED", "boom")

    assert driver.run_lifecycle([("other", fail), ("P", lambda: ["b"])], lambda: ["z"]) == [
        "TRACER_GHOSTTY_INSTALL_FAILED detail=boom",
        "b",
        "z",
    ]
    assert driver.run_lifecycle([], fail) == ["TRACER_GHOSTTY_INSTALL_FAILED detail=boom"]


@pytest.mark.parametrize("delete", [True, False])
def test_a_failed_install_that_already_placed_a_file_is_removed_and_diagnosed(
    tmp_path: Path, delete: bool
) -> None:
    before = driver.home_listing(tmp_path, tmp_path / "workspace")
    binary = tmp_path / ".local/bin/ghostty"

    def install() -> list[str]:
        binary.parent.mkdir(parents=True)
        binary.touch()
        raise Failed("TRACER_GHOSTTY_INSTALL_FAILED", "boom")

    def cleanup() -> list[str]:
        installed = driver.home_listing(tmp_path, tmp_path / "workspace")
        if delete:
            binary.unlink()
        return [
            driver.remove_verdict(
                "fuse",
                before=before,
                installed=installed,
                after=driver.home_listing(tmp_path, tmp_path / "workspace"),
                allowed=[],
                tmp_left=[],
                receipt_left=False,
                receipt_paths=[".local/bin/ghostty"],
                region_files=[],
                seeded={},
                current={},
            )
        ]

    lines = driver.run_lifecycle([("P", install)], cleanup)
    assert lines[0] == "TRACER_GHOSTTY_INSTALL_FAILED detail=boom"
    assert lines[-1] == (
        "TRACER_GHOSTTY_REMOVE_OK mode=fuse"
        if delete
        else "TRACER_GHOSTTY_REMOVE_FAILED detail=.local/bin/ghostty still present"
    )


def test_sync_verdict() -> None:
    assert (
        driver.sync_verdict("fuse", ["zshenv", "ghostty"], []) == "TRACER_GHOSTTY_SYNC_OK mode=fuse"
    )
    assert "ghostty was not configured" in driver.sync_verdict("fuse", [], [])
    assert "ghostty: partial" in driver.sync_verdict("fuse", ["ghostty"], ["ghostty: partial"])


def test_regions_verdict_ok_and_each_problem() -> None:
    shell = "\n".join([marker(GHOSTTY, ">>>"), marker(GHOSTTY, "<<<")])
    keys = "\n".join([marker(GHOSTTY_KEYS, ">>>"), marker(GHOSTTY_KEYS, "<<<")])
    show = "command = /usr/bin/zsh -l"
    bind = r"keybind = ctrl+shift+k=text:\x0c"

    def check(text: str, output: str = show, rc: int = 0, key: str = bind, keyrc: int = 0) -> str:
        return driver.regions_verdict("fuse", text, "/usr/bin/zsh", output, rc, key, keyrc)

    assert check(shell + "\n" + keys) == "TRACER_GHOSTTY_REGIONS_OK mode=fuse"
    for line, detail in [
        (check(keys), "shell region missing"),
        (check(shell), "keys region missing"),
        (check(keys + "\n" + shell), "the shell region is not above the keys region"),
        (check(shell + keys, ""), "ghostty +show-config lacks"),
        (check(shell + keys, rc=1), "ghostty +show-config exited 1"),
        (check(shell + keys, key=""), "ghostty +list-keybinds lacks"),
        (check(shell + keys, keyrc=-1), "ghostty +list-keybinds exited -1"),
    ]:
        assert detail in line


def test_leftovers_follow_the_bash_rule() -> None:
    assert driver.leftovers([], [".cache/uv/x", ".config/ghostty/config.ghostty"], [".cache"]) == [
        ".config/ghostty/config.ghostty"
    ]
    assert driver.leftovers([], [".local/share"], [".local/share/uv"]) == []
    assert driver.leftovers(["x"], ["x"], []) == []


def test_remove_verdict_ok_and_problems() -> None:
    before = ["config", "theme"]

    def check(
        installed: list[str],
        after: list[str],
        *,
        current: dict[str, str | None] | None = None,
        tmp_left: list[str] | None = None,
        receipt_left: bool = False,
    ) -> str:
        return driver.remove_verdict(
            "fuse",
            before=before,
            installed=installed,
            after=after,
            allowed=[],
            tmp_left=tmp_left or [],
            receipt_left=receipt_left,
            receipt_paths=["binary"],
            region_files=["config"],
            seeded={"config": "original"},
            current=current if current is not None else {"config": "original"},
        )

    assert check(before + ["binary"], before) == "TRACER_GHOSTTY_REMOVE_OK mode=fuse"
    for line, detail in [
        (check(before + ["binary", "other"], before), "other appeared"),
        (check(before, before), "binary is missing"),
        (check(before + ["binary"], before + ["binary"]), "binary still present"),
        (check(before + ["binary"], ["config"]), "theme existed before"),
        (check(before + ["binary"], before, current={"config": None}), "config changed"),
        (
            check(before + ["binary"], before, tmp_left=["tools-installer-x"]),
            "/tmp holds tools-installer-x",
        ),
        (check(before + ["binary"], before, receipt_left=True), "the receipt is still present"),
    ]:
        assert detail in line


_STATE = ".local/share/tools-installer/terminal-tuning-ghostty"


def _state_record_verdict(installed: list[str], after: list[str]) -> str:
    return driver.remove_verdict(
        "fuse",
        before=["config"],
        installed=installed,
        after=after,
        allowed=[],
        tmp_left=[],
        receipt_left=False,
        receipt_paths=["binary"],
        region_files=["config"],
        seeded={},
        current={},
    )


def test_remove_verdict_expects_the_installers_state_record_and_its_removal() -> None:
    assert (
        _state_record_verdict(["config", "binary", _STATE], ["config"])
        == "TRACER_GHOSTTY_REMOVE_OK mode=fuse"
    )
    assert "still present" in _state_record_verdict(
        ["config", "binary", _STATE], ["config", _STATE]
    )
    other = ".local/share/tools-installer/something-else"
    assert "something-else appeared" in _state_record_verdict(
        ["config", "binary", other], ["config"]
    )


def testrun_ghostty_does_not_wait_for_a_helper_that_keeps_the_output_open(
    tmp_path: Path,
) -> None:
    stand_in = tmp_path / "ghostty"
    stand_in.write_text("#!/bin/sh\n(sleep 20) &\necho Ghostty 1.4.0\n")
    stand_in.chmod(0o755)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    started = time.monotonic()
    rc, stdout, _ = driver.run_ghostty(stand_in, tmp_path, scratch, "fuse", "--version")
    assert (rc, stdout.strip()) == (0, "Ghostty 1.4.0")
    assert time.monotonic() - started < 10


def test_remove_verdict_is_independent_of_listing_order() -> None:
    def check(before: list[str], installed: list[str], after: list[str]) -> str:
        return driver.remove_verdict(
            "fuse",
            before=before,
            installed=installed,
            after=after,
            allowed=[],
            tmp_left=[],
            receipt_left=False,
            receipt_paths=["binary"],
            region_files=[],
            seeded={},
            current={},
        )

    assert check(["a", "b"], ["a", "b", "binary", "other"], ["a", "binary"]) == check(
        ["b", "a"], ["other", "binary", "b", "a"], ["binary", "a"]
    )


def test_seed_user_content_writes_a_user_line_and_a_theme_file(tmp_path: Path) -> None:
    seeded = driver.seed_user_content(tmp_path)
    assert seeded == {
        ".config/ghostty/config.ghostty": "font-size = 13\n",
        ".config/ghostty/themes/user-theme": "background = 101010\n",
    }
    assert driver.current_content(tmp_path, seeded) == seeded
    assert driver.seed_user_content(tmp_path) == seeded
    assert driver.home_listing(tmp_path, tmp_path / "none") == sorted(seeded)


def test_current_content_reads_text_or_none(tmp_path: Path) -> None:
    (tmp_path / "bad").write_bytes(b"\xff")
    (tmp_path / "dir").mkdir()
    assert driver.current_content(tmp_path, ["bad", "dir", "missing"]) == {
        "bad": None,
        "dir": None,
        "missing": None,
    }


def test_home_listing_skips_empty_dirs_and_the_workspace(tmp_path: Path) -> None:
    (tmp_path / "workspace").mkdir()
    (tmp_path / "workspace/x").touch()
    (tmp_path / "empty").mkdir()
    (tmp_path / "a").touch()
    (tmp_path / "link").symlink_to(tmp_path / "a")
    assert driver.home_listing(tmp_path, tmp_path / "workspace") == ["a", "link"]


def test_allowed_prefixes_strip_comments_and_blanks() -> None:
    assert driver.allowed_prefixes(".cache  # reason\n\n# comment\n") == [".cache"]


def test_tmp_leftovers_names_only_the_installers_own_directories() -> None:
    assert driver.tmp_leftovers(["tools-installer-abc", "appimage_extracted_1", "x"]) == [
        "tools-installer-abc"
    ]


def test_expected_receipt_paths_match_artifact_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    method = next(
        m for m in tool_by_id("ghostty").methods if m.kind == "tarball" and m.arch == ("amd64",)
    )
    assert driver.expected_receipt_paths(home) == [
        str(a.path.relative_to(home)) for a in artifact_paths(method, home / ".local/bin")
    ]


def test_pass_environment() -> None:
    assert driver.pass_environment("fuse", {"APPIMAGE_EXTRACT_AND_RUN": "1", "A": "b"}) == {
        "A": "b"
    }
    assert driver.pass_environment("extract", {}) == {"APPIMAGE_EXTRACT_AND_RUN": "1"}
    with pytest.raises(ValueError):
        driver.pass_environment("unknown", {})


def test_ghostty_driver_refuses_outside_the_container(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[object] = []

    def recording_install(*args: object) -> None:
        calls.append(args)

    monkeypatch.setattr(driver, "install_one", recording_install)
    monkeypatch.setattr(driver, "in_container", lambda: False)
    assert driver.main(["lifecycle"]) == 2
    assert "only inside the disposable container" in capsys.readouterr().out
    assert calls == []
    assert driver.main(["nothing"]) == 2 and driver.main([]) == 2
    assert "usage" in capsys.readouterr().err
    assert driver.accepts(["lifecycle"]) and driver.accepts(["lifecycle-extract"])
    assert not driver.accepts(["lifecycle", "extra"])


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "container-e2e-verify.sh"
_CONSTANTS: Final = (
    "IMAGE_FEDORA",
    "IMAGE_DEBIAN",
    "IMAGE_ARCH",
    "LANDING_IMAGE",
    "LANDING_CONTAINER_NAME",
    "LANDING_KEEP_IMAGE",
    "LANDING_PULLED",
    "TESTER_USER",
)
_CT_STUB: Final = """
ct() { printf 'ct %s\\n' "$*" >> "$CALLS"; return 0; }
"""


def _bash() -> str:
    found = shutil.which("bash")
    assert found is not None
    return found


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _constant(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)\s*$", _text(), re.MULTILINE)
    assert match is not None, f"{name} is not assigned"
    return match.group(1)


def _function(name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, f"{name}() is not defined"
    return match.group(0)


def _script(*names: str, variables: Mapping[str, str] | None = None, stubs: str = "") -> str:
    parts = ["set -uo pipefail", *(f"{name}={_constant(name)}" for name in _CONSTANTS)]
    parts.extend(_function(name) for name in names)
    parts.extend(f"{key}={shlex.quote(value)}" for key, value in (variables or {}).items())
    return "\n".join([*parts, stubs])


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
    path = scratch / "calls"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


_LIFECYCLE_FUNCTIONS: Final = (
    "die",
    "select_distro",
    "cmd_ghostty",
    "ghostty_root_setup",
    "ghostty_run_args",
    "landing_teardown",
    "landing_note_image",
    "start_container",
    "container_exists",
    "container_running",
    "exec_root",
    "exec_tester",
    "ensure_phase_dir",
)


def _lifecycle(scratch: Path, distro: str, host_fuse: Path) -> str:
    stubs = (
        _CT_STUB
        + """
landing_bootstrap() { start_container replace; exec_root true; }
landing_stage() { shift; "$@"; }
landing_step() { printf 'step %s %s\\n' "$1" "$2" >> "$CALLS"; exec_tester true; }
"""
    )
    return _script(
        *_LIFECYCLE_FUNCTIONS,
        variables={
            "REPO_ROOT": str(scratch / "repo"),
            "TESTER_HOME": "/home/tester",
            "GHOSTTY_HOST_FUSE": str(host_fuse),
        },
        stubs=stubs + f"select_distro {distro}\ncmd_ghostty\n",
    )


def test_ghostty_is_registered() -> None:
    assert re.search(r'^\s*ghostty\) cmd_ghostty "\$@" ;;$', _text(), re.MULTILINE)
    usage = _function("usage")
    assert "TRACER_GHOSTTY_" in usage.split("ghostty [--keep-image]", 1)[1]
    body = _function("cmd_ghostty")
    assert 'LANDING_CONTAINER_NAME="tools-installer-e2e-ghostty-$$"' in body
    assert "LANDING_DRIVER_MODULE=tests.e2e_ghostty_driver" in body
    assert (
        body.index("trap landing_teardown EXIT")
        < body.index("landing_note_image")
        < body.index("landing_bootstrap")
        < body.index("landing_stage ghostty-root ghostty_root_setup")
        < body.index("landing_step")
    )


def test_ghostty_runs_the_fuse_pass_then_the_extract_pass() -> None:
    steps = re.findall(
        r"^  landing_step (\S+) (\S+) \|\| failed=1$", _function("cmd_ghostty"), re.MULTILINE
    )
    assert steps == [("fuse-pass", "lifecycle"), ("extract-pass", "lifecycle-extract")]
    assert all(driver.accepts([verb]) for _, verb in steps)


@pytest.mark.parametrize("exists", [True, False])
def test_ghostty_start_passes_the_fuse_device_and_never_privileged(
    tmp_path: Path, exists: bool
) -> None:
    host = tmp_path / "fuse"
    if exists:
        host.touch()
    scratch = tmp_path / "home"
    result = _run(_lifecycle(scratch, "fedora", host), scratch)
    assert result.returncode == 0, result.stderr
    calls = _calls(scratch)
    run = next(call for call in calls if call.startswith("ct run "))
    assert "--security-opt label=disable" in run
    assert re.search(r"--name tools-installer-e2e-ghostty-\d+ fedora:latest", run)
    assert ("--device /dev/fuse" in run) == exists
    if not exists:
        assert (
            str(host) in result.stderr
            and "container starts without the FUSE device" in result.stderr
        )
        assert "TRACER_GHOSTTY_FUSE_UNPROVEN" in result.stderr
    assert [c for c in calls if c.startswith("step ")] == [
        "step fuse-pass lifecycle",
        "step extract-pass lifecycle-extract",
    ]
    assert all("--privileged" not in c and "--cap-add" not in c for c in calls)


@pytest.mark.parametrize("exists", [True, False])
def test_ghostty_run_args_include_the_fuse_device_only_when_the_host_has_it(
    tmp_path: Path, exists: bool
) -> None:
    host = tmp_path / "fuse"
    if exists:
        host.touch()
    command = (
        f"ghostty_run_args {shlex.quote(str(host))}; "
        f'ghostty_run_args {shlex.quote(str(host))}; printf "%s\\n" "${{CONTAINER_RUN_ARGS[@]}}"'
    )
    result = _run(_script("ghostty_run_args", stubs=command), tmp_path / "home")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["--security-opt", "label=disable"] + (
        ["--device", "/dev/fuse"] if exists else []
    )
    if not exists:
        assert str(host) in result.stderr and "TRACER_GHOSTTY_FUSE_UNPROVEN" in result.stderr


def test_the_default_container_start_is_unchanged(tmp_path: Path) -> None:
    script = _script(
        "start_container",
        "container_exists",
        "container_running",
        variables={"CONTAINER_NAME": "test-container", "IMAGE": "test-image"},
        stubs=_CT_STUB + "start_container\n",
    )
    result = _run(script, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "ct run -d --init --name test-container test-image sleep infinity" in _calls(tmp_path)


def test_ghostty_root_setup_installs_fuse_and_marks_the_host_immutable(tmp_path: Path) -> None:
    script = _script(
        "ghostty_root_setup",
        "exec_root",
        variables={"CONTAINER_NAME": "test-container"},
        stubs=_CT_STUB + "ghostty_root_setup\n",
    )
    result = _run(script, tmp_path)
    assert result.returncode == 0
    assert _calls(tmp_path) == [
        "ct exec test-container dnf install -y zsh fuse fuse3",
        "ct exec test-container sh -c touch /run/ostree-booted",
    ]


@pytest.mark.parametrize("distro", ["fedora", "debian", "arch"])
def test_ghostty_targets_only_its_own_container(tmp_path: Path, distro: str) -> None:
    scratch = tmp_path / "home"
    result = _run(_lifecycle(scratch, distro, tmp_path / "absent"), scratch)
    assert result.returncode == 0, result.stderr
    calls = [c for c in _calls(scratch) if c.startswith(("ct run ", "ct exec ", "ct rm "))]
    assert calls
    names: set[str] = set()
    for call in calls:
        match = re.search(r"tools-installer-e2e-ghostty-\d+", call)
        assert match and not re.search(r"tools-installer-e2e-(fedora|debian|arch)\b", call)
        names.add(match.group())
    assert len(names) == 1


@pytest.mark.parametrize("pulled", ["1", "0"])
def test_ghostty_teardown_removes_only_its_container_and_a_pulled_image(
    tmp_path: Path, pulled: str
) -> None:
    script = _script(
        "landing_teardown",
        variables={
            "LANDING_CONTAINER_NAME": "tools-installer-e2e-ghostty-4242",
            "LANDING_PULLED": pulled,
        },
        stubs=_CT_STUB + "landing_teardown\n",
    )
    result = _run(script, tmp_path)
    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path)
    assert "ct rm -f tools-installer-e2e-ghostty-4242" in calls
    assert sum(c.startswith("ct rmi fedora") for c in calls) == int(pulled)


def test_the_harness_never_prunes_or_resets() -> None:
    assert not re.search(
        r"system prune|system reset|image prune|volume prune|container prune|builder prune", _text()
    )


def test_the_ghostty_target_comment_names_the_shared_image() -> None:
    assert (
        "fedora:latest" in _text().split("# --- ghostty target", 1)[1].split("cmd_ghostty()", 1)[0]
    )
