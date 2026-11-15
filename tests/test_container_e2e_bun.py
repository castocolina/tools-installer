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
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from installer.enums import InstallStatus
from installer.receipts import Receipt, ReceiptMethod
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
    assert result.returncode != 0  # a container left behind fails the run
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


# --- Task 2: ownership, fallback, floor, removal and trust verdicts -------------------------------

_MMDC = "@mermaid-js/mermaid-cli"


def _receipt(kind: str, package: str | None) -> Receipt:
    return Receipt(
        tool="x",
        at="2026-11-14T00:00:00Z",
        method=ReceiptMethod(kind=kind, key="k"),
        package=package,
        artifacts=(),
        smoke=None,
        hooks={},
    )


@pytest.mark.parametrize(
    ("receipt", "detail"),
    [
        (_receipt("bun", "puppeteer"), None),
        (None, "precondition: no bun receipt for puppeteer"),
        (_receipt("node", "puppeteer"), "node"),
        (_receipt("bun", "other"), "other"),
        (_receipt("bun", None), "no package"),
    ],
)
def test_receipt_detail(receipt: Receipt | None, detail: str | None) -> None:
    found = driver.receipt_detail(receipt, "bun", "puppeteer")
    if detail is None:
        assert found is None
    else:
        assert found is not None
        assert found.startswith("precondition: ")
        assert detail in found


def _tree(**ranges: object) -> dict[str, object]:
    return {"dependencies": ranges}


_PAIR = {_MMDC: "^11", "puppeteer": "^25"}


@pytest.mark.parametrize(
    ("before", "after", "detail"),
    [
        (_tree(**_PAIR), _tree(**_PAIR), None),
        (_tree(**_PAIR), _tree(**{_MMDC: "^11", "puppeteer": "^26"}), "range"),
        (_tree(**_PAIR), _tree(puppeteer="^25"), _MMDC),
        (
            _tree(**_PAIR),
            {**_tree(**_PAIR), "devDependencies": {"puppeteer": "^25"}},
            "more than one",
        ),
        (None, _tree(**_PAIR), "manifest"),
    ],
)
def test_idempotent_verdict(
    before: Mapping[str, object] | None, after: Mapping[str, object], detail: str | None
) -> None:
    line = driver.idempotent_verdict(before, after)
    if detail is None:
        assert line == "TRACER_BUN_IDEMPOTENT_OK"
    else:
        assert line.startswith("TRACER_BUN_IDEMPOTENT_FAILED detail=")
        assert detail in line


@pytest.mark.parametrize(
    ("owner", "current", "installed", "detail"),
    [
        ("bun", "1.5.2", "1.5.2", None),
        ("node", "1.5.2", "1.5.2", "node"),
        ("bun", "1.5.1", "1.5.2", "1.5.1"),
        ("bun", None, "1.5.2", "no version"),
        ("bun", "1.5.2", None, "installed package"),
    ],
)
def test_pi_owner_verdict(
    owner: str, current: str | None, installed: str | None, detail: str | None
) -> None:
    line = driver.pi_owner_verdict(owner, current, installed)
    if detail is None:
        assert line == "TRACER_BUN_PI_OWNER_OK version=1.5.2"
    else:
        assert line.startswith("TRACER_BUN_PI_OWNER_FAILED detail=")
        assert detail in line


_PNPM_ADD = ("/home/tester/.local/share/pnpm/bin/pnpm", "add", "-g", "--allow-build=puppeteer", "g")
_BUN_ADD = ("/home/tester/.bun/bin/bun", "add", "-g", "x")


@pytest.mark.parametrize(
    ("hidden", "status", "kind", "argvs", "error", "detail"),
    [
        (True, InstallStatus.INSTALLED, "node", [_PNPM_ADD], None, None),
        (False, InstallStatus.INSTALLED, "node", [_PNPM_ADD], None, "bun was not hidden"),
        (True, InstallStatus.INSTALLED, "bun", [_PNPM_ADD], None, "bun"),
        (True, InstallStatus.INSTALLED, "node", [], None, "no pnpm add"),
        (True, InstallStatus.INSTALLED, "node", [("pnpm", "list", "-g")], None, "no pnpm add"),
        (True, InstallStatus.INSTALLED, "node", [_PNPM_ADD, _BUN_ADD], None, "bun argv"),
        (True, InstallStatus.FAILED, "node", [], "pnpm not found on PATH", "pnpm not found"),
    ],
)
def test_fallback_verdict(
    hidden: bool,
    status: InstallStatus,
    kind: str | None,
    argvs: Sequence[Sequence[str]],
    error: str | None,
    detail: str | None,
) -> None:
    line = driver.fallback_verdict(hidden, status, kind, argvs, error)
    if detail is None:
        assert line == "TRACER_BUN_FALLBACK_OK"
    else:
        assert line.startswith("TRACER_BUN_FALLBACK_FAILED detail=")
        assert detail in line


@pytest.mark.parametrize(
    ("on_path", "installed", "bun_listed", "pnpm_listed", "detail"),
    [
        (None, False, False, False, None),
        ("/home/tester/.bun/bin/mmdc", False, False, False, "/home/tester/.bun/bin/mmdc"),
        (None, True, False, False, "is_installed"),
        (None, False, True, False, "bun lists"),
        (None, False, False, True, "pnpm lists"),
    ],
)
def test_absent_detail(
    on_path: str | None, installed: bool, bun_listed: bool, pnpm_listed: bool, detail: str | None
) -> None:
    found = driver.absent_detail(on_path, installed, bun_listed, pnpm_listed)
    if detail is None:
        assert found is None
    else:
        assert found is not None
        assert found.startswith("precondition: ")
        assert detail in found


_FLOOR_ERROR = "node 20.0.0 does not meet the required minimum 22.12.0. Upgrade node."
_FLOOR_REASON = "needs Node >= 22.12.0; this system has 20.0.0"
_FAILED = InstallStatus.FAILED


@pytest.mark.parametrize(
    ("status", "errors", "argvs", "reason", "detail"),
    [
        (_FAILED, [_FLOOR_ERROR], [], _FLOOR_REASON, None),
        (InstallStatus.INSTALLED, [], [], _FLOOR_REASON, "FAILED"),
        (_FAILED, ["something else"], [], _FLOOR_REASON, "floor message"),
        (_FAILED, [_FLOOR_ERROR], [_BUN_ADD], _FLOOR_REASON, "bun add"),
        (_FAILED, [_FLOOR_ERROR], [], None, "plan"),
        (_FAILED, [_FLOOR_ERROR], [], "needs Node", "plan"),
    ],
)
def test_floor_verdict(
    status: InstallStatus,
    errors: Sequence[str],
    argvs: Sequence[Sequence[str]],
    reason: str | None,
    detail: str | None,
) -> None:
    line = driver.floor_verdict(status, errors, argvs, reason)
    if detail is None:
        assert line == "TRACER_BUN_FLOOR_OK"
    else:
        assert line.startswith("TRACER_BUN_FLOOR_FAILED detail=")
        assert detail in line


_KEPT = ("puppeteer", "bun kept puppeteer because another global package needs it")


@pytest.mark.parametrize(
    ("failed", "receipt", "detail"),
    [
        ([_KEPT], True, None),
        ([], True, "kept"),
        ([("puppeteer", "bun not found on PATH")], True, "kept"),
        ([("mmdc", _KEPT[1])], True, "kept"),
        ([_KEPT], False, "receipt"),
    ],
)
def test_kept_peer_verdict(
    failed: Sequence[tuple[str, str]], receipt: bool, detail: str | None
) -> None:
    line = driver.kept_peer_verdict(failed, receipt)
    if detail is None:
        assert line == "TRACER_BUN_KEPT_PEER_OK"
    else:
        assert line.startswith("TRACER_BUN_KEPT_PEER_FAILED detail=")
        assert detail in line


@pytest.mark.parametrize(
    ("removed", "failed", "in_tree", "detail"),
    [
        (["mmdc", "puppeteer"], [], [], None),
        (["mmdc"], [("puppeteer", "bun kept")], [], "puppeteer"),
        (["mmdc", "puppeteer"], [], ["puppeteer"], "node_modules"),
        ([], [], [], "mmdc"),
    ],
)
def test_remove_verdict(
    removed: Sequence[str],
    failed: Sequence[tuple[str, str]],
    in_tree: Sequence[str],
    detail: str | None,
) -> None:
    line = driver.remove_verdict(removed, failed, in_tree)
    if detail is None:
        assert line == "TRACER_BUN_REMOVE_OK"
    else:
        assert line.startswith("TRACER_BUN_REMOVE_FAILED detail=")
        assert detail in line


_TRUST_ERROR = "puppeteer could not start a browser; run `bun add -g --trust puppeteer@^25`, then"
_PNPM_AS_FALLBACK = ("/h/pnpm", "add", "-g", "x")


@pytest.mark.parametrize(
    ("status", "kind", "error", "argvs", "trusted", "detail"),
    [
        (_FAILED, "bun", _TRUST_ERROR, [_BUN_ADD], ["esbuild"], None),
        (InstallStatus.INSTALLED, "bun", None, [], ["esbuild"], "FAILED"),
        (_FAILED, "node", _TRUST_ERROR, [], ["esbuild"], "kind"),
        (_FAILED, "bun", "some other error", [], ["esbuild"], "trust"),
        (_FAILED, "bun", _TRUST_ERROR, [], ["esbuild"], "bun add -g"),
        (_FAILED, "bun", _TRUST_ERROR, [_BUN_ADD, _PNPM_AS_FALLBACK], ["esbuild"], "pnpm"),
        (_FAILED, "bun", _TRUST_ERROR, [_BUN_ADD], ["esbuild", "puppeteer"], "trustedDependencies"),
        (_FAILED, "bun", _TRUST_ERROR, [_BUN_ADD], None, "trustedDependencies"),
    ],
)
def test_trust_verdict(
    status: InstallStatus,
    kind: str | None,
    error: str | None,
    argvs: Sequence[Sequence[str]],
    trusted: Sequence[str] | None,
    detail: str | None,
) -> None:
    line = driver.trust_verdict(status, kind, error, argvs, trusted)
    if detail is None:
        assert line == "TRACER_BUN_TRUST_OK"
    else:
        assert line.startswith("TRACER_BUN_TRUST_FAILED detail=")
        assert detail in line


_ANCESTOR = "/home/tester/e2e/node_modules/puppeteer"
_ANCESTOR_STDERR = f"puppeteer resolved to {_ANCESTOR}/index.js, outside /home/tester/e2e/t/x"


@pytest.mark.parametrize(
    ("own", "ancestor", "stderr", "unloadable", "plain", "detail"),
    [
        (0, 1, _ANCESTOR_STDERR, 1, 0, None),
        (1, 1, _ANCESTOR_STDERR, 1, 0, "own tree"),
        (0, 0, "", 1, 0, "ancestor"),
        (0, 1, "something else", 1, 0, "name the ancestor"),
        (0, 1, _ANCESTOR_STDERR, 0, 0, "unloadable"),
        (0, 1, _ANCESTOR_STDERR, 1, 1, "manager-less"),
    ],
)
def test_strict_loader_verdict(
    own: int, ancestor: int, stderr: str, unloadable: int, plain: int, detail: str | None
) -> None:
    line = driver.strict_loader_verdict(
        own, ancestor, stderr, unloadable, plain, ancestor_path=_ANCESTOR
    )
    if detail is None:
        assert line == "TRACER_BUN_STRICT_LOADER_OK"
    else:
        assert line.startswith("TRACER_BUN_STRICT_LOADER_FAILED detail=")
        assert detail in line


# --- the step order -----------------------------------------------------------------------------

_STEP = re.compile(r"^  landing_step (\S+) (\S+) \|\| failed=1$", re.MULTILINE)
_EXPECTED_STEPS = (
    "install-mmdc",
    "idempotent-mmdc",
    "strict-loader",
    "pi-owner",
    "kept-peer",
    "remove-both",
    "fallback",
    "floor",
    "trust",
)


def test_bun_lifecycle_runs_every_step_in_order() -> None:
    body = _function("cmd_bun_lifecycle")
    steps = _STEP.findall(body)
    assert tuple(verb for _name, verb in steps) == _EXPECTED_STEPS
    assert [name for name, _verb in steps] == list(_EXPECTED_STEPS)
    assert body.index("landing_bootstrap") < body.index("landing_step")
    for verb in _EXPECTED_STEPS:
        assert driver.accepts([verb]), verb
    assert not driver.accepts(["install-mmdc", "extra"])
    assert not driver.accepts([])
