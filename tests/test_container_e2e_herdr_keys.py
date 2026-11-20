"""Host tests of the herdr-keys target and in-container driver; no container is started."""

import re
import shlex
import shutil
import subprocess
import tomllib
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest

from installer.model import load_tools
from installer.terminal_keys import TERMINAL_KEYS
from tests import e2e_herdr_keys_driver as driver

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
    assert found is not None, "bash is required"
    return found


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _constant(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)\s*$", _text(), re.MULTILINE)
    assert match is not None, f"{name} is not assigned in the script"
    return match.group(1)


def _function(name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, f"{name}() is not defined in the script"
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


_LIFECYCLE_FUNCTIONS: Final[tuple[str, ...]] = (
    "die",
    "select_distro",
    "cmd_herdr_keys",
    "landing_teardown",
    "landing_note_image",
    "start_container",
    "container_exists",
    "container_running",
    "exec_root",
    "exec_tester",
    "ensure_phase_dir",
)
_STUB_BOOTSTRAP: Final = "landing_bootstrap() { start_container replace; exec_root true; }\n"
_STUB_STEP: Final = "landing_step() { exec_tester true; }\n"


def _lifecycle(scratch: Path, distro: str, *, bootstrap: str = _STUB_BOOTSTRAP) -> str:
    return _script(
        *_LIFECYCLE_FUNCTIONS,
        variables={"REPO_ROOT": str(scratch / "repo"), "TESTER_HOME": "/home/tester"},
        stubs=_CT_STUB + bootstrap + _STUB_STEP + f"select_distro {distro}\ncmd_herdr_keys\n",
    )


def test_herdr_keys_verdict_ok() -> None:
    assert (
        driver.herdr_keys_verdict(True, [expected for _name, _sent, expected in driver.CHORDS])
        == "TRACER_HERDR_KEYS_OK received=1b62,1b66,1b5b313b3344,1b5b313b3343,0c"
    )


@pytest.mark.parametrize("index", range(8))
def test_herdr_keys_verdict_names_each_missing_chord(index: int) -> None:
    received = [expected for _name, _sent, expected in driver.CHORDS]
    received[index] = ""
    name, sent, _expected = driver.CHORDS[index]
    line = driver.herdr_keys_verdict(True, received)
    assert line.startswith("TRACER_HERDR_KEYS_FAILED detail=")
    assert f"{name} sent {sent.hex()} received nothing" in line


def test_herdr_keys_verdict_names_a_reencoded_chord() -> None:
    received = [expected for _name, _sent, expected in driver.CHORDS]
    received[3] = "1b5b43"
    assert "alt+right sent 1b5b313b3343 received 1b5b43" in driver.herdr_keys_verdict(
        True, received
    )


def test_herdr_keys_verdict_counts_a_short_list_as_missing() -> None:
    line = driver.herdr_keys_verdict(
        True, [expected for _name, _sent, expected in driver.CHORDS[:-1]]
    )
    name, sent, _expected = driver.CHORDS[-1]
    assert f"{name} sent {sent.hex()} received nothing" in line


def test_herdr_keys_verdict_unproven_when_the_pane_never_started() -> None:
    assert driver.keys_verdict("", None, 0, []) == (
        "TRACER_HERDR_KEYS_UNPROVEN detail=the herdr pane never started the recorder"
    )


def test_herdr_keys_verdict_unproven_on_client_pty_close_before_recorder_start() -> None:
    assert driver.keys_verdict("", "EOF", 0, []) == (
        "TRACER_HERDR_KEYS_UNPROVEN detail=the herdr client closed the pty before "
        "the recorder started (EOF)"
    )
    error = "[Errno 5] Input/output error"
    assert driver.keys_verdict("", error, 0, []).endswith(f"({error})")


def test_herdr_keys_verdict_ok_when_the_client_exits_after_every_chord() -> None:
    expected = [expected for _name, _sent, expected in driver.CHORDS]
    assert driver.keys_verdict("START", "EOF", len(driver.CHORDS), expected) == (
        "TRACER_HERDR_KEYS_OK received=1b62,1b66,1b5b313b3344,1b5b313b3343,0c"
    )


def test_herdr_keys_verdict_unproven_if_client_exits_before_the_last_chord() -> None:
    assert driver.keys_verdict("START", "EOF", 1, ["1b62"]) == (
        "TRACER_HERDR_KEYS_UNPROVEN detail=the herdr client closed the pty before "
        "the last chord was sent (EOF)"
    )


def test_herdr_keys_verdict_failed_when_the_client_exits_after_the_last_send() -> None:
    received = [expected for _name, _sent, expected in driver.CHORDS[:-1]]
    line = driver.keys_verdict("START", "EOF", len(driver.CHORDS), received)
    assert line.startswith("TRACER_HERDR_KEYS_FAILED detail=")
    name, sent, _expected = driver.CHORDS[-1]
    assert f"{name} sent {sent.hex()} received nothing" in line


def test_received_per_chord_joins_split_reads() -> None:
    assert driver.received_per_chord(["START", "1b", "62", "1b66"], 1, ["1b62", "1b66"]) == [
        "1b62",
        "1b66",
    ]


def test_received_per_chord_keeps_a_delayed_write_with_its_chord() -> None:
    assert driver.received_per_chord(["START", "1b621b66"], 1, ["1b62", "1b66"]) == ["1b62", "1b66"]
    assert driver.received_per_chord(
        ["START", "1b62", "1b", "660c"], 1, ["1b62", "1b66", "0c"]
    ) == ["1b62", "1b66", "0c"]


def test_received_per_chord_ignores_input_before_the_first_send() -> None:
    assert driver.received_per_chord(["START", "1b5b49", "1b62"], 2, ["1b62"]) == ["1b62"]
    assert driver.received_per_chord(["1b62", "START"], 0, ["1b62"]) == ["1b62"]


def test_received_per_chord_missing_and_extra_bytes() -> None:
    assert driver.received_per_chord(["START"], 1, ["1b62", "1b66"]) == ["", ""]
    assert driver.received_per_chord(["START", "1b66"], 1, ["1b62", "1b66"]) == [
        "1b66",
        "",
    ]
    assert driver.received_per_chord(["START", "1b62", "1b66ff"], 1, ["1b62", "1b66"]) == [
        "1b62",
        "1b66ff",
    ]


def test_the_chord_table_sends_alt_right_and_every_expected_string() -> None:
    assert ("alt+right", b"\x1b[1;3C", "1b5b313b3343") in driver.CHORDS
    assert driver.EXPECTED == ("1b62", "1b66", "1b5b313b3344", "1b5b313b3343", "0c")
    assert set(driver.EXPECTED) == {expected for _n, _s, expected in driver.CHORDS}
    assert len({name for name, _sent, _expected in driver.CHORDS}) == len(driver.CHORDS)


def test_the_arrow_chords_are_sent_only_as_csi_1_3() -> None:
    arrows = tuple(chord for chord in driver.CHORDS if "left" in chord[0] or "right" in chord[0])
    assert arrows == (
        ("alt+left", b"\x1b[1;3D", "1b5b313b3344"),
        ("alt+right", b"\x1b[1;3C", "1b5b313b3343"),
    )
    assert all(
        not ("csi-u" in name and ("left" in name or "right" in name))
        for name, _sent, _expected in driver.CHORDS
    )
    assert {name for name, _sent, _expected in driver.CHORDS if "csi-u" in name} == {
        "alt+b csi-u",
        "alt+f csi-u",
        "ctrl+l csi-u",
    }


def test_herdr_child_environment_has_only_driver_values(tmp_path: Path) -> None:
    assert driver.child_environment(tmp_path, tmp_path / "run") == {
        "HOME": str(tmp_path),
        "XDG_RUNTIME_DIR": str(tmp_path / "run"),
        "PATH": "/usr/bin:/bin",
        "TERM": "xterm-256color",
        "LANG": "C.UTF-8",
    }


def test_herdr_config_keeps_the_proof_offline_and_quiet() -> None:
    assert tomllib.loads(driver.HERDR_CONFIG.format(shell="/tmp/hk/recshell.sh")) == {
        "onboarding": False,
        "update": {"version_check": False, "manifest_check": False},
        "terminal": {"default_shell": "/tmp/hk/recshell.sh"},
    }


def test_recorder_source_is_valid_python_that_records_raw_hex() -> None:
    compile(driver.RECORDER_SOURCE, "recorder", "exec")
    assert "tty.setraw(0)" in driver.RECORDER_SOURCE
    assert "START" in driver.RECORDER_SOURCE and ".hex()" in driver.RECORDER_SOURCE


def test_herdr_keys_driver_refuses_outside_the_container(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installed: list[object] = []

    def recording_install(*args: object, **_kwargs: object) -> None:
        installed.append(args)

    monkeypatch.setattr(driver, "install_one", recording_install)
    monkeypatch.setattr(driver, "in_container", lambda: False)
    assert driver.main(["install-herdr"]) == 2
    assert "only inside the disposable container" in capsys.readouterr().out
    assert installed == []
    assert driver.main(["nothing"]) == 2
    assert driver.main([]) == 2
    assert "usage" in capsys.readouterr().err
    assert driver.accepts(["install-herdr"]) and driver.accepts(["keys"])
    assert not driver.accepts(["keys", "extra"])


def test_herdr_keys_is_registered() -> None:
    text = _text()
    assert re.search(r'^\s*herdr-keys\) cmd_herdr_keys "\$@" ;;$', text, re.MULTILINE)
    usage = _function("usage")
    assert "herdr-keys [--keep-image]" in usage
    assert "TRACER_HERDR_" in usage.split("herdr-keys [--keep-image]", 1)[1]
    body = _function("cmd_herdr_keys")
    assert 'LANDING_CONTAINER_NAME="tools-installer-e2e-herdr-keys-$$"' in body
    assert "LANDING_DRIVER_MODULE=tests.e2e_herdr_keys_driver" in body
    assert body.index("trap landing_teardown EXIT") < body.index("landing_note_image")
    assert body.index("landing_note_image") < body.index("landing_bootstrap")
    assert body.index("landing_bootstrap") < body.index("landing_step")


def test_herdr_keys_runs_install_then_keys() -> None:
    body = _function("cmd_herdr_keys")
    steps = re.findall(r"^  landing_step (\S+) (\S+) \|\| failed=1$", body, re.MULTILINE)
    assert steps == [("install-herdr", "install-herdr"), ("keys", "keys")]
    assert all(driver.accepts([verb]) for _name, verb in steps)


@pytest.mark.parametrize("distro", ["fedora", "debian", "arch"])
def test_herdr_keys_targets_only_its_own_container(tmp_path: Path, distro: str) -> None:
    scratch = tmp_path / f"own-{distro}"
    result = _run(_lifecycle(scratch, distro), scratch)
    assert result.returncode == 0, result.stderr
    calls = _calls(scratch)
    container_calls = [call for call in calls if call.split()[1] in {"run", "exec", "rm"}]
    assert container_calls
    for call in container_calls:
        assert re.search(r"tools-installer-e2e-herdr-keys-[0-9]+", call), call
        assert not re.search(r"tools-installer-e2e-(fedora|debian|arch)\b", call), call
    run = next(call for call in container_calls if call.startswith("ct run"))
    assert _constant("IMAGE_FEDORA") in run
    matches = [
        re.search(r"tools-installer-e2e-herdr-keys-[0-9]+", call) for call in container_calls
    ]
    names = {match.group(0) for match in matches if match is not None}
    assert len(names) == 1


@pytest.mark.parametrize(("pulled", "removes_image"), [("1", True), ("0", False)])
def test_herdr_keys_teardown_removes_only_its_container_and_a_pulled_image(
    tmp_path: Path, pulled: str, removes_image: bool
) -> None:
    scratch = tmp_path / f"teardown-{pulled}"
    script = _script(
        "landing_teardown",
        variables={
            "LANDING_CONTAINER_NAME": "tools-installer-e2e-herdr-keys-4242",
            "LANDING_PULLED": pulled,
        },
        stubs=_CT_STUB + "landing_teardown",
    )
    result = _run(script, scratch)
    assert result.returncode == 0, result.stderr
    calls = _calls(scratch)
    assert "ct rm -f tools-installer-e2e-herdr-keys-4242" in calls
    assert [call.startswith("ct rmi fedora") for call in calls].count(True) == int(removes_image)


def test_the_harness_never_prunes_or_resets() -> None:
    assert not re.search(
        r"system prune|system reset|image prune|volume prune|container prune|builder prune",
        _text(),
    )


def test_herdr_has_no_keys_row_and_no_terminal_tuning() -> None:
    assert "herdr" not in TERMINAL_KEYS
    tool = next(
        tool for tool in load_tools(ROOT / "installer" / "registry.toml") if tool.id == "herdr"
    )
    assert "apply_terminal_tuning" not in tool.post_install
