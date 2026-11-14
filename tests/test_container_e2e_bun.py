"""Host tests of the bun-lifecycle target and its in-container driver (24.5-09, PRIO-02/03/06).

Like the landing tests, these never source the container detector and never start a container:
they read the committed script text and run extracted bash functions with a stubbed `ct`. The
driver is imported for its pure verdict functions only; its verbs install real tools and run only
in the disposable container, under the orchestrator (24.5-09 Task 3).
"""

import re
import shlex
import shutil
import subprocess
import uuid
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests import e2e_bun_driver as driver

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "container-e2e-verify.sh"

_CONSTANTS = (
    "IMAGE_FEDORA",
    "IMAGE_DEBIAN",
    "IMAGE_ARCH",
    "LANDING_IMAGE",
    "LANDING_CONTAINER_NAME",
    "LANDING_KEEP_IMAGE",
    "LANDING_PULLED",
    "TESTER_USER",
)

# One CALLS line per container call.
_CT_STUB = r"""
ct() {
  printf 'ct %s\n' "$*" >> "$CALLS"
  return 0
}
"""

_BUN_NAME = re.compile(r"^tools-installer-e2e-bun-[0-9]+$")
_BUN_NAME_IN_LINE = re.compile(r"\btools-installer-e2e-bun-[0-9]+\b")


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
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, f"{name}() is not defined in the script"
    return match.group(0)


def _script(*names: str, variables: Mapping[str, str] | None = None, stubs: str = "") -> str:
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


_LIFECYCLE_FUNCTIONS = (
    "die",
    "select_distro",
    "cmd_bun_lifecycle",
    "landing_teardown",
    "landing_note_image",
    "start_container",
    "container_exists",
    "container_running",
    "exec_root",
    "exec_tester",
    "ensure_phase_dir",
)

_STUB_BOOTSTRAP = "landing_bootstrap() { start_container replace; exec_root true; }\n"
_STUB_STEP = "landing_step() { exec_tester true; }\n"


def _lifecycle(scratch: Path, distro: str, *, bootstrap: str = _STUB_BOOTSTRAP) -> str:
    return _script(
        *_LIFECYCLE_FUNCTIONS,
        variables={"REPO_ROOT": str(scratch / "repo"), "TESTER_HOME": "/home/tester"},
        stubs=_CT_STUB + bootstrap + _STUB_STEP + f"select_distro {distro}\ncmd_bun_lifecycle\n",
    )


# --- the verb is registered ---------------------------------------------------------------------


def test_bun_lifecycle_is_registered() -> None:
    text = _text()
    assert re.search(r"^\s*bun-lifecycle\) cmd_bun_lifecycle \"\$@\" ;;$", text, re.MULTILINE)
    usage = _function("usage")
    assert "bun-lifecycle [--keep-image]" in usage
    assert "TRACER_BUN_" in usage.split("bun-lifecycle [--keep-image]", 1)[1]
    body = _function("cmd_bun_lifecycle")
    assert 'LANDING_CONTAINER_NAME="tools-installer-e2e-bun-$$"' in body
    assert "ti-uat-" not in text
    assert "LANDING_DRIVER_MODULE=tests.e2e_bun_driver" in body
    assert body.index("trap landing_teardown EXIT") < body.index("landing_bootstrap")
    assert body.index("landing_note_image") < body.index("landing_bootstrap")
    assert body.index("landing_bootstrap") < body.index("landing_step install-mmdc install-mmdc")
    assert "${LANDING_DRIVER_MODULE}" in _function("landing_driver")


def test_the_unique_name_is_never_a_ti_uat_name(tmp_path: Path) -> None:
    result = _run(_lifecycle(tmp_path / "name", "fedora"), tmp_path / "name")
    assert result.returncode == 0, result.stderr
    runs = [call for call in _calls(tmp_path / "name") if call.startswith("ct run")]
    assert len(runs) == 1
    name = runs[0].split("--name ", 1)[1].split()[0]
    assert _BUN_NAME.fullmatch(name), name


# --- teardown -----------------------------------------------------------------------------------


@pytest.mark.parametrize(("pulled", "removes_image"), [("1", True), ("0", False)])
def test_bun_teardown_removes_only_this_run_s_container_and_pulled_image(
    tmp_path: Path, pulled: str, removes_image: bool
) -> None:
    scratch = tmp_path / f"teardown-{pulled}"
    script = _script(
        "landing_teardown",
        variables={
            "LANDING_CONTAINER_NAME": "tools-installer-e2e-bun-4242",
            "LANDING_PULLED": pulled,
        },
        stubs=_CT_STUB + "landing_teardown",
    )
    result = _run(script, scratch)
    assert result.returncode == 0, result.stderr
    calls = _calls(scratch)
    assert "ct rm -f tools-installer-e2e-bun-4242" in calls
    assert [call.startswith("ct rmi fedora") for call in calls].count(True) == int(removes_image)
    assert not [call for call in calls if "tools-installer-e2e-fedora" in call]


@pytest.mark.parametrize("distro", ["fedora", "debian", "arch"])
def test_bun_lifecycle_targets_only_its_own_container(tmp_path: Path, distro: str) -> None:
    """R1-10: `--distro` must never point the verb at another distro's shared container or image."""
    scratch = tmp_path / f"own-{distro}"
    result = _run(_lifecycle(scratch, distro), scratch)
    assert result.returncode == 0, result.stderr
    calls = _calls(scratch)
    container_calls = [call for call in calls if call.split()[1] in {"run", "exec", "rm"}]
    assert container_calls, calls
    for call in container_calls:
        assert _BUN_NAME_IN_LINE.search(call), call
        assert not re.search(r"tools-installer-e2e-(fedora|debian|arch)\b", call), call
    run = next(call for call in container_calls if call.startswith("ct run"))
    assert _constant("IMAGE_FEDORA") in run
    assert "debian" not in run
    assert "archlinux" not in run
    names = {
        match.group(0) for call in container_calls for match in _BUN_NAME_IN_LINE.finditer(call)
    }
    assert len(names) == 1


def test_landing_teardown_appends_its_verdict_to_the_transcript(tmp_path: Path) -> None:
    """R1-03: the phase gate reads the verdict from the transcript, not from the console."""
    ok = tmp_path / "ok"
    ok_log = ok / "transcript.log"
    result = _run(
        _script(
            "landing_teardown",
            variables={"LANDING_TRANSCRIPT": str(ok_log)},
            stubs=_CT_STUB + "landing_teardown",
        ),
        ok,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TRACER_LANDING_TEARDOWN_OK"
    assert ok_log.read_text(encoding="utf-8").splitlines() == ["TRACER_LANDING_TEARDOWN_OK"]

    left = tmp_path / "left"
    left_log = left / "transcript.log"
    listing_stub = (
        "ct() {\n"
        '  printf \'ct %s\\n\' "$*" >> "$CALLS"\n'
        '  [[ "$1" == ps ]] && printf \'%s\\n\' "$LANDING_CONTAINER_NAME"\n'
        "  return 0\n"
        "}\n"
    )
    result = _run(
        _script(
            "landing_teardown",
            variables={"LANDING_TRANSCRIPT": str(left_log)},
            stubs=listing_stub + "landing_teardown",
        ),
        left,
    )
    assert result.returncode == 0, result.stderr
    expected = f"TRACER_LANDING_TEARDOWN_LEFT container={_constant('LANDING_CONTAINER_NAME')}"
    assert result.stdout.strip() == expected
    assert left_log.read_text(encoding="utf-8").splitlines() == [expected]

    unset = tmp_path / "unset"
    result = _run(
        _script("landing_teardown", stubs=_CT_STUB + "landing_teardown"),
        unset,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TRACER_LANDING_TEARDOWN_OK"

    missing = tmp_path / "missing"
    result = _run(
        _script(
            "landing_teardown",
            variables={"LANDING_TRANSCRIPT": str(missing / "no-such-dir" / "transcript.log")},
            stubs=_CT_STUB + "landing_teardown",
        ),
        missing,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "TRACER_LANDING_TEARDOWN_OK"


def test_the_exit_trap_records_teardown_after_an_early_bootstrap_failure(tmp_path: Path) -> None:
    """R1-03: even a bootstrap that dies at once leaves a transcript ending with the verdict."""
    scratch = tmp_path / "early"
    result = _run(
        _lifecycle(scratch, "fedora", bootstrap="landing_bootstrap() { exit 2; }\n"), scratch
    )
    assert result.returncode == 2, result.stderr
    transcript = scratch / "repo" / ".e2e-artifacts" / "container-bun" / "bun-transcript.log"
    assert transcript.read_text(encoding="utf-8").splitlines()[-1] == "TRACER_LANDING_TEARDOWN_OK"
    removals = [call for call in _calls(scratch) if call.startswith("ct rm -f")]
    assert len(removals) == 1
    assert _BUN_NAME_IN_LINE.search(removals[0])


# --- the pure verdicts ----------------------------------------------------------------------------

_PREFIX = "/home/linuxbrew/.linuxbrew"


@pytest.mark.parametrize(
    ("before", "kind", "path", "detail"),
    [
        (False, "brew", f"{_PREFIX}/bin/bun", None),
        (False, "script", f"{_PREFIX}/bin/bun", "script"),
        (False, None, f"{_PREFIX}/bin/bun", "no install outcome"),
        (True, "brew", f"{_PREFIX}/bin/bun", "already"),
        (False, "brew", "/home/tester/.bun/bin/bun", "outside"),
        (False, "brew", None, "not resolved"),
        (False, "brew", f"{_PREFIX}-other/bin/bun", "outside"),
    ],
)
def test_brew_bun_verdict(
    before: bool, kind: str | None, path: str | None, detail: str | None
) -> None:
    line = driver.brew_bun_verdict(before, kind, path, _PREFIX)
    if detail is None:
        assert line == "TRACER_BUN_VIA_HOMEBREW_OK"
    else:
        assert line.startswith("TRACER_BUN_VIA_HOMEBREW_FAILED detail=")
        assert detail in line


def _manifest(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "dependencies": {"@mermaid-js/mermaid-cli": "^11.12.0", "puppeteer": "^25"}
    }
    document.update(overrides)
    return document


@pytest.mark.parametrize(
    ("document", "detail"),
    [
        (_manifest(), None),
        (None, "manifest"),
        (_manifest(dependencies={"puppeteer": "^25"}), "@mermaid-js/mermaid-cli"),
        (_manifest(dependencies={"@mermaid-js/mermaid-cli": "^11"}), "puppeteer"),
        (
            _manifest(dependencies={"@mermaid-js/mermaid-cli": "^11", "puppeteer": "^24"}),
            "^25",
        ),
        (_manifest(trustedDependencies=["puppeteer"]), "trustedDependencies"),
        (_manifest(dependencies=["puppeteer"]), "dependencies"),
    ],
)
def test_manifest_verdict(document: Mapping[str, object] | None, detail: str | None) -> None:
    line = driver.manifest_verdict(document)
    if detail is None:
        assert line == "TRACER_BUN_MANIFEST_OK"
    else:
        assert line.startswith("TRACER_BUN_MANIFEST_FAILED detail=")
        assert detail in line


@pytest.mark.parametrize(
    ("cached", "reason", "detail"),
    [
        (True, None, None),
        (False, None, "browser"),
        (True, "puppeteer could not start a browser: x", "smoke"),
    ],
)
def test_browser_verdict(cached: bool, reason: str | None, detail: str | None) -> None:
    line = driver.browser_verdict(cached, reason)
    if detail is None:
        assert line == "TRACER_BUN_BROWSER_OK"
    else:
        assert line.startswith("TRACER_BUN_BROWSER_FAILED detail=")
        assert detail in line


@pytest.mark.parametrize(("code", "ok"), [(0, True), (127, False), (1, False), (None, False)])
def test_login_shell_verdict(code: int | None, ok: bool) -> None:
    line = driver.login_shell_verdict(code)
    if ok:
        assert line == "TRACER_BUN_LOGIN_SHELL_OK"
    else:
        assert line.startswith("TRACER_BUN_LOGIN_SHELL_FAILED detail=")


# --- the driver refuses to run outside the container -----------------------------------------


def test_bun_driver_refuses_outside_the_container(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installed: list[object] = []

    def recording_install(*args: object, **_kwargs: object) -> None:
        installed.append(args)

    monkeypatch.setattr(driver, "install_one", recording_install)
    monkeypatch.setattr(driver, "in_container", lambda: False)
    assert driver.main(["install-mmdc"]) == 2
    assert "only inside the disposable container" in capsys.readouterr().out
    assert installed == []
    assert driver.main(["nothing"]) == 2
    assert driver.main([]) == 2
    assert "usage" in capsys.readouterr().err
