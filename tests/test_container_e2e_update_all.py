"""Host-only tests of the update-all container instrument's pure verdicts."""

import ast
import json
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from installer.helper_assets import schedule_runner
from tests import e2e_update_all_driver as driver

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "container-e2e-verify.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _function(name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", _text(), re.MULTILINE | re.DOTALL)
    assert match is not None, name
    return match.group()


def _constant(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)\s*$", _text(), re.MULTILINE)
    assert match is not None, name
    return match.group(1)


def _harness(tmp_path: Path, names: Sequence[str], stubs: str) -> subprocess.CompletedProcess[str]:
    constants = (
        "IMAGE_FEDORA",
        "IMAGE_DEBIAN",
        "IMAGE_ARCH",
        "LANDING_IMAGE",
        "LANDING_CONTAINER_NAME",
        "LANDING_KEEP_IMAGE",
        "LANDING_PULLED",
        "TESTER_USER",
    )
    script = "\n".join(
        [
            "set -uo pipefail",
            *(f"{name}={_constant(name)}" for name in constants),
            *(_function(name) for name in names),
            f"REPO_ROOT={shlex.quote(str(tmp_path / 'repo'))}",
            "TESTER_HOME=/home/tester",
            stubs,
        ]
    )
    bash = shutil.which("bash")
    assert bash is not None
    script_file = tmp_path / "harness.sh"
    script_file.write_text(script, encoding="utf-8")
    return subprocess.run(
        [bash, str(script_file)],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "CALLS": str(tmp_path / "calls"),
            "STEPS": str(tmp_path / "steps"),
            "LANG": "C",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


_FUNCTIONS = (
    "die",
    "select_distro",
    "cmd_update_all",
    "update_all_exit",
    "landing_teardown",
    "landing_note_image",
    "start_container",
    "container_exists",
    "container_running",
    "exec_root",
    "exec_tester",
    "ensure_phase_dir",
)
_CT = 'ct() { printf "ct %s\\n" "$*" >> "$CALLS"; return 0; }\n'


def _transcript(tmp_path: Path) -> list[str]:
    return (
        (
            tmp_path
            / "repo"
            / ".e2e-artifacts"
            / "container-update-all"
            / "update-all-transcript.log"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    )


def test_update_all_is_registered() -> None:
    text = _text()
    assert 'update-all) cmd_update_all "$@" ;;' in text
    usage = _function("usage").split("update-all [--keep-image]", 1)[1]
    assert "TRACER_UPDATE_ALL_" in usage
    body = _function("cmd_update_all")
    for item in (
        'LANDING_CONTAINER_NAME="tools-installer-e2e-update-all-$$"',
        "LANDING_DRIVER_MODULE=tests.e2e_update_all_driver",
        'PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-update-all"',
        "update-all-transcript.log",
        'die "unknown update-all option: $1"',
        "for step in plan-managers seed plan run again",
        'landing_step "$step" "$step" || failed=1',
    ):
        assert item in body
    assert (
        body.index("trap update_all_exit EXIT")
        < body.index("landing_note_image")
        < body.index("landing_bootstrap")
        < body.index('landing_step "$step"')
    )
    assert "ti-uat-" not in text
    assert not re.search(r"\b(sudo|pkexec|doas)\b", body)
    assert "landing_teardown" in _function("update_all_exit")


@pytest.mark.parametrize(
    ("failure", "expected", "skipped", "rc"),
    [
        ("plan-managers", ["plan-managers"], ["seed", "plan", "run", "again"], 1),
        ("plan", ["plan-managers", "seed", "plan"], ["run", "again"], 1),
        ("none", ["plan-managers", "seed", "plan", "run", "again"], [], 0),
    ],
)
def test_a_failed_step_stops_every_later_step(
    tmp_path: Path, failure: str, expected: list[str], skipped: list[str], rc: int
) -> None:
    stubs = (
        "landing_note_image() { :; }\nlanding_bootstrap() { :; }\n"
        'landing_teardown() { printf "TEARDOWN rc=%s\\n" "$?" >> "$LANDING_TRANSCRIPT"; }\n'
        'landing_step() { printf "%s\\n" "$1" >> "$STEPS"; '
        f'[[ "$1" != {shlex.quote(failure)} ]]; }}\n'
        "cmd_update_all"
    )
    result = _harness(tmp_path, _FUNCTIONS, stubs)
    assert result.returncode == rc, result.stderr
    assert (tmp_path / "steps").read_text().splitlines() == expected
    assert _transcript(tmp_path) == [
        *(f"TRACER_UPDATE_ALL_STEP_SKIPPED step={step}" for step in skipped),
        f"TEARDOWN rc={rc}",
    ]


def test_an_environmental_exit_still_marks_the_unrun_steps(tmp_path: Path) -> None:
    names = (*_FUNCTIONS, "landing_step", "landing_environmental", "landing_infeasible")
    stubs = (
        "LANDING_ENV_RE='Could not resolve host'\n"
        "landing_note_image() { :; }\nlanding_bootstrap() { :; }\n"
        'landing_teardown() { printf "TEARDOWN rc=%s\\n" "$?" >> "$LANDING_TRANSCRIPT"; }\n'
        'landing_driver() { if [[ "$1" == seed ]]; then echo "Could not resolve host"; '
        "return 1; fi; echo ok; }\n"
        "cmd_update_all"
    )
    result = _harness(tmp_path, names, stubs)
    assert result.returncode == 2, result.stderr
    lines = _transcript(tmp_path)
    assert any(line.startswith("TRACER_LANDING_INFEASIBLE step=seed ") for line in lines)
    assert lines[-4:] == [
        "TRACER_UPDATE_ALL_STEP_SKIPPED step=plan",
        "TRACER_UPDATE_ALL_STEP_SKIPPED step=run",
        "TRACER_UPDATE_ALL_STEP_SKIPPED step=again",
        "TEARDOWN rc=2",
    ]
    assert not any(
        "STEP_SKIPPED step=seed" in line or "STEP_SKIPPED step=plan-managers" in line
        for line in lines
    )


@pytest.mark.parametrize("distro", ["fedora", "debian", "arch"])
def test_the_update_all_name_is_unique_and_never_shared(tmp_path: Path, distro: str) -> None:
    stubs = (
        _CT + "landing_bootstrap() { start_container replace; exec_root true; }\n"
        "landing_step() { exec_tester true; }\n" + f"select_distro {distro}\ncmd_update_all"
    )
    result = _harness(tmp_path, _FUNCTIONS, stubs)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    container_calls = [line for line in calls if line.split()[1] in {"run", "exec", "rm"}]
    assert container_calls
    names: set[str] = set()
    for line in container_calls:
        match = re.search(r"\btools-installer-e2e-update-all-[0-9]+\b", line)
        assert match and not re.search(r"tools-installer-e2e-(fedora|debian|arch)\b", line)
        names.add(match.group())
    assert len(names) == 1
    assert _constant("IMAGE_FEDORA") in next(
        line for line in container_calls if line.startswith("ct run")
    )


@pytest.mark.parametrize(("pulled", "removes"), [("1", True), ("0", False)])
def test_update_all_teardown_removes_only_its_container_and_the_pulled_image(
    tmp_path: Path, pulled: str, removes: bool
) -> None:
    stubs = (
        _CT
        + "LANDING_CONTAINER_NAME=tools-installer-e2e-update-all-4242\n"
        + f"LANDING_PULLED={pulled}\nlanding_teardown"
    )
    result = _harness(tmp_path, _FUNCTIONS, stubs)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert [line for line in calls if line.startswith("ct rm ")] == [
        "ct rm -f tools-installer-e2e-update-all-4242"
    ]
    assert any(line.startswith("ct rmi fedora") for line in calls) is removes


def test_the_exit_trap_records_teardown_after_an_early_bootstrap_failure(tmp_path: Path) -> None:
    result = _harness(tmp_path, _FUNCTIONS, _CT + "landing_bootstrap() { exit 2; }\ncmd_update_all")
    assert result.returncode == 2, result.stderr
    assert _transcript(tmp_path)[-1] == "TRACER_LANDING_TEARDOWN_OK"
    removals = [
        line
        for line in (tmp_path / "calls").read_text().splitlines()
        if line.startswith("ct rm -f")
    ]
    assert len(removals) == 1 and re.search(r"tools-installer-e2e-update-all-[0-9]+", removals[0])


def test_parse_plan() -> None:
    entries, summary = driver.parse_plan(
        [
            "brew (managers): would update",
            "jq: skipped: updated today",
            "note: advisory",
            "ok: plan 1 to update, 1 skipped",
            "failed: later",
        ]
    )
    assert entries == [
        driver.PlanLine("brew", "managers", "update", ""),
        driver.PlanLine("jq", None, "skip", "updated today"),
    ]
    assert summary == "failed: later"
    with pytest.raises(ValueError, match="unrecognized row"):
        driver.parse_plan(["unrecognized row"])


def test_managers_verdict() -> None:
    lines = ["brew (managers): would update", "uv (managers): would update"]
    summary = "ok: plan 2 to update, 0 skipped"
    assert (
        driver.managers_verdict(lines + [summary], {}, {})
        == "TRACER_UPDATE_ALL_PLAN_MANAGERS_OK entries=2"
    )
    for index, marker in [(0, "MANAGER_UNPROVEN id=brew"), (1, "UV_UNPROVEN")]:
        changed = lines.copy()
        changed[index] = f"{('brew', 'uv')[index]}: skipped: updated today"
        result = driver.managers_verdict(changed + [summary], {}, {})
        assert marker in result and changed[index] in result
    assert "state/a" in driver.managers_verdict(
        lines + [summary], {"state/a": "a"}, {"state/a": "b"}
    )
    for invalid in [
        lines[::-1] + [summary],
        ["ruff (uv): would update", *lines, summary],
        lines,
        lines + ["failed: error"],
        [summary],
    ]:
        assert "PLAN_MANAGERS_FAILED" in driver.managers_verdict(invalid, {}, {})


def test_plan_verdict() -> None:
    lines = [f"{name} (managers): would update" for name in ("brew", "bun", "sdkman", "uv")]
    lines += ["ruff (uv): would update", "ok: plan 5 to update, 0 skipped"]
    assert (
        driver.plan_verdict(lines, {}, {})
        == "TRACER_UPDATE_ALL_PLAN_OK order=brew,bun,sdkman,uv,ruff"
    )
    for index, name in enumerate(("brew", "bun", "sdkman", "uv")):
        changed = lines.copy()
        changed[index] = f"{name}: skipped: reason"
        result = driver.plan_verdict(changed, {}, {})
        assert ("UV_UNPROVEN" if name == "uv" else f"MANAGER_UNPROVEN id={name}") in result
        assert changed[index] in result
    for invalid in [
        lines[1:],
        lines[:4] + lines[5:],
        [lines[4], *lines[:4], lines[5]],
        [*lines[:4], "ruff: skipped: reason", lines[5]],
    ]:
        assert "PLAN_FAILED" in driver.plan_verdict(invalid, {}, {})
    assert "changed" in driver.plan_verdict(lines, {"x": "1"}, {"x": "2"})


@pytest.mark.parametrize(
    ("uv", "listing", "receipt", "bun", "sdkman", "detail"),
    [
        ("uv 0.11.0 (build)", "ruff v0.1.0", 'specifier = ">=0.1.0"', True, True, None),
        ("uv 0.12.0", "ruff v0.1.0", 'specifier = ">=0.1.0"', True, True, "uv"),
        ("uv 0.11.0", "ruff v0.2.0", 'specifier = ">=0.1.0"', True, True, "ruff"),
        ("uv 0.11.0", "", 'specifier = ">=0.1.0"', True, True, "ruff"),
        ("uv 0.11.0", "other v0.1.0", 'specifier = ">=0.1.0"', True, True, "ruff"),
        ("uv 0.11.0", "ruff v0.1.0", 'specifier = "==0.1.0"', True, True, "receipt"),
        ("uv 0.11.0", "ruff v0.1.0", 'specifier = ">=0.1.0"', False, True, "bun"),
        ("uv 0.11.0", "ruff v0.1.0", 'specifier = ">=0.1.0"', True, False, "sdkman"),
    ],
)
def test_seed_verdict(
    uv: str, listing: str, receipt: str, bun: bool, sdkman: bool, detail: str | None
) -> None:
    result = driver.seed_verdict(uv, listing, receipt, bun, sdkman)
    if detail is None:
        assert result == "TRACER_UPDATE_ALL_SEED_OK uv=0.11.0 ruff=0.1.0 bun=yes sdkman=yes"
    else:
        assert result.startswith("TRACER_UPDATE_ALL_SEED_FAILED detail=") and detail in result


def test_seed_constants_and_prerequisites() -> None:
    assert driver.UV_OLD == "0.11.0"
    assert driver.UV_INSTALL_URL == "https://astral.sh/uv/0.11.0/install.sh"
    assert (
        driver.prereq_line("zip", True, False)
        == "TRACER_UPDATE_ALL_SEED_PREREQ id=zip source=present"
    )
    assert (
        driver.prereq_line("zip", False, True)
        == "TRACER_UPDATE_ALL_SEED_PREREQ id=zip source=installed"
    )
    with pytest.raises(ValueError):
        driver.prereq_line("zip", False, False)


@pytest.mark.parametrize(
    ("argv", "leaf", "kind", "path", "formulae", "detail"),
    [
        (
            ["uv", "self", "update"],
            "/home/tester/.local/bin/uv",
            "file",
            "/home/tester/.local/bin/uv",
            ["git"],
            None,
        ),
        (
            ["uv", "self", "update"],
            "/home/tester/.local/bin/uv",
            "link",
            "/home/tester/.local/bin/uv",
            [],
            "link",
        ),
        (
            ["uv", "self", "update"],
            "/home/tester/.local/bin/uv",
            "missing",
            "/home/tester/.local/bin/uv",
            [],
            "missing",
        ),
        (
            ["uv", "self", "update"],
            "/home/tester/.local/bin/uv",
            "file",
            "/home/tester/.local/bin/uv",
            ["uv"],
            "formula",
        ),
        (
            ["uv", "self", "update"],
            "/home/tester/.local/bin/uv",
            "file",
            "/brew/bin/uv",
            [],
            "PATH",
        ),
        (
            ["uv", "upgrade"],
            "/home/tester/.local/bin/uv",
            "file",
            "/home/tester/.local/bin/uv",
            [],
            "argv",
        ),
        (
            ["uv", "self", "update"],
            "/home/tester/.local/bin/uv",
            "file",
            "/home/tester/.local/bin/uv",
            None,
            "formula",
        ),
    ],
)
def test_route_verdict(
    argv: Sequence[str],
    leaf: str,
    kind: str,
    path: str,
    formulae: Sequence[str] | None,
    detail: str | None,
) -> None:
    result = driver.route_verdict(argv, leaf, kind, path, formulae)
    if detail is None:
        assert result == f"TRACER_UPDATE_ALL_ROUTE_OK leaf={leaf}"
    else:
        assert result.startswith("TRACER_UPDATE_ALL_UV_UNPROVEN detail=route ") and detail in result


def _run_facts() -> dict[str, object]:
    return {
        "exit_code": 0,
        "shared_lines": ["time update-all start", "time update-all ok: 3 updated"],
        "tool_lines": [
            ("brew", "ok: updated"),
            ("bun", "skipped: unchanged"),
            ("sdkman", "skipped: unchanged"),
            ("uv", "ok: updated"),
            ("ruff", "ok: updated"),
        ],
        "record_ids": {"brew", "uv", "ruff"},
        "uv_before": "0.11.0",
        "uv_after": "0.11.9",
        "hash_before": "old",
        "hash_after": "new",
        "ruff_before": "0.1.0",
        "ruff_after": "0.15.0",
        "launch_to_start": 1.0,
    }


def _run(facts: Mapping[str, object]) -> list[str]:
    return driver.run_verdict(
        exit_code=cast(int, facts["exit_code"]),
        shared_lines=cast(Sequence[str], facts["shared_lines"]),
        tool_lines=cast(Sequence[tuple[str, str]], facts["tool_lines"]),
        record_ids=cast(Collection[str], facts["record_ids"]),
        uv_before=cast(str, facts["uv_before"]),
        uv_after=cast(str, facts["uv_after"]),
        hash_before=cast(str, facts["hash_before"]),
        hash_after=cast(str, facts["hash_after"]),
        ruff_before=cast(str, facts["ruff_before"]),
        ruff_after=cast(str, facts["ruff_after"]),
        launch_to_start=cast(float, facts["launch_to_start"]),
    )


def test_run_verdict() -> None:
    facts = _run_facts()
    lines = _run(facts)
    assert "TRACER_UPDATE_ALL_UV_SELF_UPDATE_OK before=0.11.0 after=0.11.9" in lines
    assert "TRACER_UPDATE_ALL_DEPENDENT_OK id=ruff before=0.1.0 after=0.15.0" in lines
    for name in ("bun", "sdkman"):
        assert f"TRACER_UPDATE_ALL_MANAGER_FINDING id={name} result=skipped: unchanged" in lines
    assert "TRACER_UPDATE_ALL_RUN_OK exit=0 tools=5" in lines
    for key, value in [("uv_after", "0.11.0"), ("hash_after", "old")]:
        result = _run({**facts, key: value})
        assert any("UV_SELF_UPDATE_UNPROVEN detail=" in line for line in result)
        assert not any("UV_SELF_UPDATE_OK" in line for line in result)
    assert any("UV_SELF_UPDATE_FAILED" in line for line in _run({**facts, "uv_after": ""}))
    assert any(
        "DEPENDENT_UNPROVEN id=ruff detail=" in line
        for line in _run({**facts, "ruff_after": "0.1.0"})
    )
    tools = cast(list[tuple[str, str]], facts["tool_lines"])
    for name, marker in [
        ("uv", "UV_SELF_UPDATE_FAILED"),
        ("ruff", "DEPENDENT_FAILED"),
        ("brew", "RUN_FAILED"),
    ]:
        changed = [(tool, "failed: error" if tool == name else text) for tool, text in tools]
        result = _run({**facts, "tool_lines": changed})
        assert any(marker in line for line in result)
        if name == "uv":
            assert any("RUN_FAILED" in line for line in result)
    for changes in [
        {
            "shared_lines": [
                "time update-all start",
                "time update-all ok: x",
                "time update-all ok: x",
            ]
        },
        {"tool_lines": tools[1:]},
        {"record_ids": {"brew", "uv"}},
        {"exit_code": 1},
    ]:
        assert any("RUN_FAILED" in line for line in _run({**facts, **changes}))


def test_rc_finding() -> None:
    assert driver.rc_finding({"a": "1"}, {"a": "1"}) == "TRACER_UPDATE_ALL_RC_FINDING changed=none"
    assert driver.rc_finding({".bashrc": "a"}, {".bashrc": "b", ".zshrc": "c"}).endswith(
        "changed=.bashrc,.zshrc"
    )


def _evidence() -> dict[str, object]:
    return {
        "managers": ["brew", "uv"],
        "shared_count": 2,
        "ruff_after": "0.15.0",
        "uv_path": "/home/tester/.local/bin/uv",
        "uv_before": "0.11.0",
        "uv_after": "0.11.9",
        "hash_before": "oldhash",
        "hash_after": "newhash",
        "route": {"kind": "file", "readlink": None},
        "rc_before": {".bashrc": "oldrc"},
        "rc_after": {".bashrc": "newrc"},
        "launch_to_start": 3.0,
    }


def test_evidence_round_trip_and_the_again_verdict() -> None:
    evidence = driver.parse_evidence(json.dumps(_evidence()))
    assert evidence == _evidence()
    line = driver.evidence_line(evidence)
    assert line.startswith("UPDATE_ALL_EVIDENCE source=installer-outcome ")
    for value in (
        "brew",
        "uv",
        "0.15.0",
        "oldhash",
        "newhash",
        "oldrc",
        "newrc",
        "readlink",
        "3.0",
    ):
        assert value in line
    for text in ("", "not json", "{}", "[]"):
        with pytest.raises(ValueError):
            driver.parse_evidence(text)
    base: dict[str, object] = {
        "exit_code": 0,
        "new_start_lines": ["start"],
        "new_result_lines": ["ok: done"],
        "tool_lines": [
            ("brew", "skipped: updated today"),
            ("uv", "skipped: updated today"),
            ("ruff", "skipped: updated today"),
        ],
        "evidence": evidence,
        "ruff_now": "0.15.0",
        "outdated": {},
        "inventory_ruff": "0.15.0",
        "ruff_latest": None,
    }

    def check(**changes: object) -> str:
        facts = {**base, **changes}
        return driver.again_verdict(
            cast(int, facts["exit_code"]),
            cast(Sequence[str], facts["new_start_lines"]),
            cast(Sequence[str], facts["new_result_lines"]),
            cast(Sequence[tuple[str, str]], facts["tool_lines"]),
            cast(driver.Evidence | None, facts["evidence"]),
            cast(str | None, facts["ruff_now"]),
            cast(Mapping[str, str] | None, facts["outdated"]),
            cast(str | None, facts["inventory_ruff"]),
            cast(str | None, facts["ruff_latest"]),
        )

    assert check() == "TRACER_UPDATE_ALL_AGAIN_OK"
    absent = [("brew", "skipped: updated today"), ("uv", "skipped: updated today")]
    assert check(tool_lines=absent) == "TRACER_UPDATE_ALL_AGAIN_OK"
    for changes in (
        {"outdated": None},
        {"inventory_ruff": None},
        {"new_result_lines": ["ok: second refresh failed; dependents judged on the first pass"]},
    ):
        assert "AGAIN_UNPROVEN detail=installer evidence for ruff" in check(
            tool_lines=absent, ruff_latest="0.15.0", **changes
        )
    for changes in ({"outdated": {"ruff": "1"}}, {"ruff_latest": "0.16.0"}):
        assert "AGAIN_FAILED" in check(tool_lines=absent, **changes)
    failures: list[dict[str, object]] = [
        {"tool_lines": [("brew", "ok: updated"), ("uv", "skipped: updated today")]},
        {"new_result_lines": ["ok: a", "ok: b"]},
        {"new_start_lines": []},
        {"exit_code": 1},
        {"evidence": None},
        {"ruff_now": "0.14.0"},
    ]
    for changes in failures:
        assert "AGAIN_FAILED" in check(**changes)
    assert (
        check(
            tool_lines=[("uv", "skipped: updated today")], evidence={**evidence, "managers": ["uv"]}
        )
        == "TRACER_UPDATE_ALL_AGAIN_OK"
    )
    assert driver.latest_version('{"info":{"version":"1.2.3"}}') == "1.2.3"
    for text in ("", "{}", "[]", '{"info":{"version":5}}'):
        assert driver.latest_version(text) is None


def test_the_run_bound_outlasts_the_job() -> None:
    assert (
        driver.LAUNCH_ALLOWANCE
        + vars(schedule_runner)["_UPDATE_ALL_TIMEOUT"]
        + vars(schedule_runner)["_UPDATE_ALL_STOP_BUDGET"]
        + vars(schedule_runner)["_KILL_GRACE"]
        < driver.RUN_BOUND
    )


def test_the_driver_refuses_outside_the_container_and_a_bad_verb(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(driver, "in_container", lambda: False)

    def forbidden(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("started process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert driver.main(["plan"]) == 2
    assert "ERROR" in capsys.readouterr().out
    for args in ([], ["unknown"], ["plan", "extra"]):
        assert driver.main(args) == 2
        assert "usage" in capsys.readouterr().err
    for verb in ("plan-managers", "seed", "plan", "run", "again"):
        assert driver.accepts([verb])
    assert not driver.accepts(["bad"])


def test_the_driver_holds_the_hard_rules() -> None:
    tree = ast.parse(Path(driver.__file__).read_text(encoding="utf-8"))
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        for node in [node.body[0]]
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            assert not any(word in node.value.split() for word in ("sudo", "pkexec", "doas"))
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".")[0] in sys.stdlib_module_names or alias.name == "installer"
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            assert node.module is not None and (
                node.module.split(".")[0] in sys.stdlib_module_names
                or node.module.startswith("installer")
                or node.module == "tests.e2d_landing_driver".replace("e2d", "e2e")
            )
