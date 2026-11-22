"""Container-only update-all instrument; verdicts describe installer-outcome evidence.

The plan-managers, seed, plan, run and again verbs are completed in the next theme.
Exit 0 means success, 1 means failed or unproven, and 2 means invalid or outside the container.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast

import installer
from installer import manager_versions, schedules, status, update_all_state
from installer import platform as host_platform
from installer.compose import _build_services
from installer.model import load_tools
from installer.run import CommandError, run_query
from installer.version_status import probed_version
from installer.versions import probe_version_output
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    no_homebrew_platform,
    tool_by_id,
    verdict,
)

UV_OLD = "0.11.0"
RUFF_OLD = "0.1.0"
UV_INSTALL_URL = f"https://astral.sh/uv/{UV_OLD}/install.sh"
RC_FILES = (".bashrc", ".bash_profile", ".profile", ".zshrc")
LAUNCH_ALLOWANCE = 600
RUN_BOUND = LAUNCH_ALLOWANCE + 10800 + 600
EVIDENCE_PATH = Path.home() / "e2e-update-all" / "first-run.json"


@dataclass(frozen=True)
class PlanLine:
    tool: str
    group: str | None
    action: Literal["update", "skip"]
    reason: str


def parse_plan(lines: Sequence[str]) -> tuple[list[PlanLine], str | None]:
    entries: list[PlanLine] = []
    summary = None
    for line in lines:
        if line.startswith("note:"):
            continue
        if line.startswith(("ok: plan ", "failed:")):
            summary = line
            continue
        update = re.fullmatch(r"([a-z0-9._-]+) \(([^()]+)\): would update", line)
        skip = re.fullmatch(r"([a-z0-9._-]+): skipped: (.+)", line)
        if update:
            entries.append(PlanLine(update[1], update[2], "update", ""))
        elif skip:
            entries.append(PlanLine(skip[1], None, "skip", skip[2]))
        else:
            raise ValueError(f"unrecognized plan line: {line}")
    return entries, summary


def _plan_verdict(
    lines: Sequence[str], before: Mapping[str, str], after: Mapping[str, str], *, seeded: bool
) -> str:
    prefix = "TRACER_UPDATE_ALL_PLAN" + ("" if seeded else "_MANAGERS")
    changed = sorted(
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
    )
    if changed:
        return verdict(f"{prefix}_FAILED", f"state changed: {','.join(changed)}")
    try:
        entries, summary = parse_plan(lines)
    except ValueError as error:
        return verdict(f"{prefix}_FAILED", str(error))
    if not summary or not summary.startswith("ok: plan ") or not entries:
        return verdict(f"{prefix}_FAILED", "missing entries or successful summary")
    expected = ["brew", "bun", "sdkman", "uv", "ruff"] if seeded else ["brew", "uv"]
    if [entry.tool for entry in entries] != expected:
        return verdict(f"{prefix}_FAILED", "missing or misordered entries")
    for entry in entries:
        original = (
            next(line for line in lines if line.startswith(f"{entry.tool}: skipped:"))
            if entry.action == "skip"
            else ""
        )
        if entry.action == "skip":
            if entry.tool == "uv":
                return f"TRACER_UPDATE_ALL_UV_UNPROVEN detail={original}"
            if entry.tool != "ruff":
                return f"TRACER_UPDATE_ALL_MANAGER_UNPROVEN id={entry.tool} detail={original}"
            return verdict(f"{prefix}_FAILED", original)
        if entry.group != ("uv" if entry.tool == "ruff" else "managers"):
            return verdict(f"{prefix}_FAILED", f"wrong group for {entry.tool}")
    if seeded:
        return f"{prefix}_OK order={','.join(expected)}"
    return f"{prefix}_OK entries={len(entries)}"


def managers_verdict(
    lines: Sequence[str], before: Mapping[str, str], after: Mapping[str, str]
) -> str:
    return _plan_verdict(lines, before, after, seeded=False)


def plan_verdict(lines: Sequence[str], before: Mapping[str, str], after: Mapping[str, str]) -> str:
    return _plan_verdict(lines, before, after, seeded=True)


def seed_verdict(
    uv_version: str, tool_list: str, ruff_receipt: str, bun_present: bool, sdkman_present: bool
) -> str:
    if not re.search(rf"^uv {re.escape(UV_OLD)}(?:\s|$)", uv_version):
        detail = "uv version"
    elif not re.search(rf"^ruff v{re.escape(RUFF_OLD)}(?:\s|$)", tool_list, re.MULTILINE):
        detail = "ruff version"
    elif not re.search(r"""specifier\s*=\s*["']>=0\.1\.0["']""", ruff_receipt) or re.search(
        r"""specifier\s*=\s*["']==0\.1\.0["']""", ruff_receipt
    ):
        detail = "ruff receipt"
    elif not bun_present:
        detail = "bun absent"
    elif not sdkman_present:
        detail = "sdkman absent"
    else:
        return "TRACER_UPDATE_ALL_SEED_OK uv=0.11.0 ruff=0.1.0 bun=yes sdkman=yes"
    return verdict("TRACER_UPDATE_ALL_SEED_FAILED", detail)


def prereq_line(tool_id: str, present_ok: bool, installed: bool) -> str:
    if not present_ok and not installed:
        raise ValueError(f"{tool_id} prerequisite not verified or installed")
    source = "present" if present_ok else "installed"
    return f"TRACER_UPDATE_ALL_SEED_PREREQ id={tool_id} source={source}"


def route_verdict(
    update_argv: Sequence[str],
    declared_leaf: str,
    leaf_kind: str,
    path_uv: str | None,
    brew_formulae: Sequence[str] | None,
) -> str:
    if list(update_argv) != ["uv", "self", "update"]:
        detail = f"argv={list(update_argv)}"
    elif leaf_kind != "file":
        detail = f"leaf kind={leaf_kind}"
    elif not declared_leaf or path_uv != declared_leaf:
        detail = f"PATH uv={path_uv} declared={declared_leaf}"
    elif brew_formulae is None:
        detail = "formula list unreadable"
    elif "uv" in brew_formulae:
        detail = "brew uv formula present"
    else:
        return f"TRACER_UPDATE_ALL_ROUTE_OK leaf={declared_leaf}"
    return f"TRACER_UPDATE_ALL_UV_UNPROVEN detail=route {detail}"


def valid_record_ids(record: Mapping[str, update_all_state.UpdatedEntry], today: date) -> set[str]:
    return {
        name for name, entry in record.items() if entry.day == today and entry.by == "update-all"
    }


def run_verdict(
    *,
    exit_code: int,
    shared_lines: Sequence[str],
    tool_lines: Sequence[tuple[str, str]],
    record_ids: Collection[str],
    uv_before: str,
    uv_after: str,
    hash_before: str,
    hash_after: str,
    ruff_before: str,
    ruff_after: str,
    launch_to_start: float,
) -> list[str]:
    results: list[str] = []
    tools = dict(tool_lines)
    uv_result = tools.get("uv", "")
    if (
        uv_result.startswith("failed:")
        or not uv_after
        or not uv_before
        or not hash_before
        or not hash_after
    ):
        results.append(
            verdict("TRACER_UPDATE_ALL_UV_SELF_UPDATE_FAILED", "uv failed or version/hash missing")
        )
    elif uv_before == uv_after or hash_before == hash_after or not uv_result.startswith("ok:"):
        results.append(
            "TRACER_UPDATE_ALL_UV_SELF_UPDATE_UNPROVEN detail=version, hash or outcome unchanged"
        )
    else:
        results.append(f"TRACER_UPDATE_ALL_UV_SELF_UPDATE_OK before={uv_before} after={uv_after}")
    ruff_result = tools.get("ruff", "")
    if ruff_result.startswith("failed:") or not ruff_after or not ruff_before:
        results.append(
            verdict("TRACER_UPDATE_ALL_DEPENDENT_FAILED", "ruff failed or version missing")
        )
    elif ruff_before == ruff_after or not ruff_result.startswith("ok: updated"):
        results.append(
            "TRACER_UPDATE_ALL_DEPENDENT_UNPROVEN id=ruff detail=version or outcome unchanged"
        )
    else:
        results.append(
            f"TRACER_UPDATE_ALL_DEPENDENT_OK id=ruff before={ruff_before} after={ruff_after}"
        )
    for name in ("bun", "sdkman"):
        if name in tools:
            results.append(f"TRACER_UPDATE_ALL_MANAGER_FINDING id={name} result={tools[name]}")
    starts = [line for line in shared_lines if line.endswith(" update-all start")]
    summaries = [
        line
        for line in shared_lines
        if " update-all ok:" in line
        or " update-all failed:" in line
        or " update-all skipped:" in line
    ]
    if exit_code != 0:
        detail = f"exit={exit_code}"
    elif len(starts) != 1 or len(summaries) != 1 or " update-all ok:" not in summaries[0]:
        detail = "shared log start or result"
    elif [name for name, _ in tool_lines] != ["brew", "bun", "sdkman", "uv", "ruff"]:
        detail = "run log tools missing or misordered"
    elif any(text.startswith("failed:") for _, text in tool_lines):
        detail = "tool failed"
    elif any(name not in record_ids for name, text in tool_lines if text.startswith("ok:")):
        detail = "record omits an ok tool"
    elif launch_to_start < 0:
        detail = "negative launch time"
    else:
        results.append(f"TRACER_UPDATE_ALL_RUN_OK exit=0 tools={len(tool_lines)}")
        return results
    results.append(verdict("TRACER_UPDATE_ALL_RUN_FAILED", detail))
    return results


Evidence = dict[str, object]


def rc_finding(before: Mapping[str, str], after: Mapping[str, str]) -> str:
    changed = sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )
    return f"TRACER_UPDATE_ALL_RC_FINDING changed={','.join(changed) or 'none'}"


def parse_evidence(text: str) -> Evidence:
    try:
        data: object = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ValueError("invalid evidence") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid evidence")
    evidence = cast(Evidence, data)
    strings = ("ruff_after", "uv_path", "uv_before", "uv_after", "hash_before", "hash_after")
    if (
        not all(isinstance(evidence.get(key), str) and evidence[key] for key in strings)
        or not isinstance(evidence.get("managers"), list)
        or not all(isinstance(item, str) for item in cast(list[object], evidence["managers"]))
        or type(evidence.get("shared_count")) is not int
        or cast(int, evidence["shared_count"]) < 0
        or not all(
            isinstance(evidence.get(key), dict) for key in ("route", "rc_before", "rc_after")
        )
        or type(evidence.get("launch_to_start")) not in (int, float)
    ):
        raise ValueError("invalid evidence")
    return evidence


def evidence_line(evidence: Evidence) -> str:
    return "UPDATE_ALL_EVIDENCE source=installer-outcome " + json.dumps(
        evidence, sort_keys=True, separators=(",", ":")
    )


def latest_version(text: str) -> str | None:
    try:
        data: object = json.loads(text)
        if isinstance(data, dict):
            info: object = cast(dict[str, object], data).get("info")
            if isinstance(info, dict):
                value: object = cast(dict[str, object], info).get("version")
                if isinstance(value, str) and value:
                    return value
    except (ValueError, RecursionError):
        pass
    return None


def again_verdict(
    exit_code: int,
    new_start_lines: Sequence[str],
    new_result_lines: Sequence[str],
    tool_lines: Sequence[tuple[str, str]],
    evidence: Evidence | None,
    ruff_now: str | None,
    outdated: Mapping[str, object] | None,
    inventory_ruff: str | None,
    ruff_latest: str | None,
) -> str:
    failed = "TRACER_UPDATE_ALL_AGAIN_FAILED"
    if evidence is None:
        return verdict(failed, "first-run evidence missing")
    if (
        exit_code != 0
        or len(new_start_lines) != 1
        or len(new_result_lines) != 1
        or not new_result_lines[0].split("update-all ")[-1].startswith("ok:")
    ):
        return verdict(failed, "exit or shared log start or result")
    tools = dict(tool_lines)
    for manager in cast(list[str], evidence["managers"]):
        if tools.get(manager) != "skipped: updated today":
            return verdict(failed, f"{manager} did not skip")
    if ruff_now != evidence["ruff_after"] or (ruff_latest is not None and ruff_latest != ruff_now):
        return verdict(failed, "ruff version changed or not latest")
    if outdated is not None and "ruff" in outdated:
        return verdict(failed, "ruff remains outdated")
    if "ruff" in tools:
        if tools["ruff"] != "skipped: updated today":
            return verdict(failed, "ruff did not skip")
    elif (
        outdated is None
        or inventory_ruff != ruff_now
        or "second refresh failed; dependents judged on the first pass" in new_result_lines[0]
    ):
        return "TRACER_UPDATE_ALL_AGAIN_UNPROVEN detail=installer evidence for ruff"
    if "ruff" not in tools:
        return "TRACER_UPDATE_ALL_AGAIN_CURRENT detail=ruff already current"
    return "TRACER_UPDATE_ALL_AGAIN_OK"


def _command(
    argv: Sequence[str], *, timeout: int = 120, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def _required(
    argv: Sequence[str], *, timeout: int = 120, env: Mapping[str, str] | None = None
) -> str:
    done = _command(argv, timeout=timeout, env=env)
    if done.returncode:
        raise ValueError(f"{argv[0]} exited {done.returncode}: {first_line(done.stderr)}")
    return done.stdout


def _snapshot(home: Path) -> dict[str, str]:
    root = home / ".local/state/tools-installer"
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): (
            "link:" + os.readlink(p)
            if p.is_symlink()
            else hashlib.sha256(p.read_bytes()).hexdigest()
        )
        for p in root.rglob("*")
        if p.is_file() or p.is_symlink()
    }


def _context() -> schedules.ScheduleContext:
    return schedules.context_for(
        host_platform.detect().os, checkout=Path.cwd(), read_models=lambda _agent: None
    )


def _environment(ctx: schedules.ScheduleContext) -> dict[str, str]:
    return cast(
        Callable[[schedules.ScheduleContext], dict[str, str]], vars(schedules)["_unit_environment"]
    )(ctx)


def _route(ctx: schedules.ScheduleContext) -> tuple[dict[str, object], str]:
    uv = next(
        t for t in load_tools(Path(installer.__file__).with_name("registry.toml")) if t.id == "uv"
    )
    method = next(m for m in uv.methods if m.kind == "script")
    argv = cast(list[str], method.params["update"])
    leaf = str(Path(cast(list[str], method.params["paths"])[0]).expanduser())
    path = shutil.which("uv", path=_environment(ctx)["PATH"])
    try:
        mode = os.lstat(leaf).st_mode
        kind = "link" if stat.S_ISLNK(mode) else "file" if stat.S_ISREG(mode) else "other"
        link = os.readlink(leaf) if kind == "link" else None
    except FileNotFoundError:
        kind, link = "missing", None
    brew = _command(["brew", "list", "--formula"])
    formulae = brew.stdout.splitlines() if brew.returncode == 0 else None
    facts: dict[str, object] = {
        "argv": argv,
        "leaf": leaf,
        "kind": kind,
        "readlink": link,
        "path_uv": path,
        "formulae": formulae,
    }
    return facts, route_verdict(argv, leaf, kind, path, formulae)


def _plan(home: Path, *, seeded: bool) -> list[str]:
    before = _snapshot(home)
    done = _command(
        [
            "uv",
            "run",
            "--isolated",
            "--no-dev",
            "setup.py",
            "--run-schedule",
            "update-all",
            "--plan",
        ],
        timeout=1800,
    )
    lines = done.stdout.splitlines()
    after = _snapshot(home)
    if done.returncode:
        return [
            verdict(
                "TRACER_UPDATE_ALL_PLAN_FAILED", f"exit={done.returncode} {first_line(done.stderr)}"
            )
        ]
    result = (
        plan_verdict(lines, before, after) if seeded else managers_verdict(lines, before, after)
    )
    if not seeded:
        return [result]
    _, route = _route(_context())
    return [*(f"UPDATE_ALL_PLAN_LINE {line}" for line in lines), route, result]


def _seed(home: Path) -> list[str]:
    lines: list[str] = []
    for name in ("zip", "unzip", "sdkman", "bun"):
        tool = tool_by_id(name)
        present = status.is_installed(tool)
        if not present:
            install_one(
                tool,
                "TRACER_UPDATE_ALL_SEED_FAILED",
                platform=no_homebrew_platform() if name == "bun" else host_platform.detect(),
            )
        lines.append(prereq_line(name, present, not present))
    env = {**os.environ, "UV_NO_MODIFY_PATH": "1"}
    _required(["sh", "-c", f"curl -LsSf {UV_INSTALL_URL} | sh"], timeout=900, env=env)
    uv = str(home / ".local/bin/uv")
    _required([uv, "tool", "install", f"ruff=={RUFF_OLD}"], timeout=900)
    directory = Path(_required([uv, "tool", "dir"]).strip())
    receipt = directory / "ruff/uv-receipt.toml"
    text, count = re.subn(
        r'(specifier\s*=\s*["\'])==0\.1\.0(["\'])',
        r"\g<1>>=0.1.0\2",
        receipt.read_text(encoding="utf-8"),
    )
    if not count:
        raise Failed("TRACER_UPDATE_ALL_SEED_FAILED", "ruff receipt has no exact pin to relax")
    receipt.write_text(text, encoding="utf-8")
    lines.append(
        seed_verdict(
            _required([uv, "--version"]),
            _required([uv, "tool", "list"]),
            text,
            (home / ".bun/bin/bun").is_file(),
            (home / ".sdkman/bin/sdkman-init.sh").is_file(),
        )
    )
    return lines


def _version(uv: str) -> str:
    text = _required([uv, "--version"]).strip()
    return text.split()[1] if len(text.split()) > 1 else ""


def _ruff(uv: str) -> str | None:
    match = re.search(r"^ruff v(\S+)", _required([uv, "tool", "list"]), re.MULTILINE)
    return match[1] if match else None


def _rc(home: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((home / name).read_bytes()).hexdigest()
        if (home / name).is_file()
        else "absent"
        for name in RC_FILES
    }


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _tools(lines: Sequence[str]) -> list[tuple[str, str]]:
    return [(parts[1], parts[2]) for line in lines if len(parts := line.split(" ", 2)) == 3]


def _chain(ctx: schedules.ScheduleContext, uv: str) -> subprocess.CompletedProcess[str]:
    return _command(
        schedules.runner_argv(ctx, schedules.schedule_by_id("update-all"), Path(uv)),
        timeout=RUN_BOUND,
        env=_environment(ctx),
    )


def _run(home: Path) -> list[str]:
    ctx = _context()
    route, route_line = _route(ctx)
    if "_UNPROVEN" in route_line:
        return [route_line]
    uv = cast(str, route["path_uv"])
    before, hash_before, ruff_before, rc_before = (
        _version(uv),
        hashlib.sha256(Path(uv).read_bytes()).hexdigest(),
        _ruff(uv) or "",
        _rc(home),
    )
    ctx.data_dir.mkdir(parents=True, exist_ok=True)
    runner = ctx.data_dir / schedules.RUNNER_NAME
    shutil.copyfile(Path(installer.__file__).parent / "helper_assets/schedule_runner.py", runner)
    runner.chmod(0o755)
    old_count = len(_lines(ctx.log_path))
    started = time.time()
    done = _chain(ctx, uv)
    shared = _lines(ctx.log_path)[old_count:]
    start_lines = [line for line in shared if line.endswith(" update-all start")]
    launch = (
        datetime.fromisoformat(start_lines[0].split(" ", 1)[0]).timestamp() - started
        if start_lines
        else -1.0
    )
    launch = max(0.0, launch) if start_lines else launch
    run_lines = _lines(schedules.update_all_log_path(ctx))
    tools = _tools(run_lines)
    record, healthy = update_all_state.read_updated(schedules.updated_today_path(ctx))
    ids: set[str] = (
        valid_record_ids(record, datetime.now().astimezone().date()) if healthy else set()
    )
    after, hash_after, ruff_after, rc_after = (
        _version(uv),
        hashlib.sha256(Path(uv).read_bytes()).hexdigest(),
        _ruff(uv) or "",
        _rc(home),
    )
    evidence: Evidence = {
        "managers": [
            name
            for name, text in tools
            if name in ("brew", "bun", "sdkman", "uv") and text.startswith("ok:")
        ],
        "shared_count": len(_lines(ctx.log_path)),
        "ruff_after": ruff_after,
        "uv_path": uv,
        "uv_before": before,
        "uv_after": after,
        "hash_before": hash_before,
        "hash_after": hash_after,
        "route": route,
        "rc_before": rc_before,
        "rc_after": rc_after,
        "launch_to_start": launch,
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence), encoding="utf-8")
    return [
        route_line,
        evidence_line(evidence),
        *(f"UPDATE_ALL_LOG {line}" for line in run_lines),
        *(f"UPDATE_ALL_SHARED_LOG {line}" for line in shared),
        *run_verdict(
            exit_code=done.returncode,
            shared_lines=shared,
            tool_lines=tools,
            record_ids=ids,
            uv_before=before,
            uv_after=after,
            hash_before=hash_before,
            hash_after=hash_after,
            ruff_before=ruff_before,
            ruff_after=ruff_after,
            launch_to_start=launch,
        ),
        rc_finding(rc_before, rc_after),
    ]


def _again(_home: Path) -> list[str]:
    try:
        evidence = parse_evidence(EVIDENCE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [verdict("TRACER_UPDATE_ALL_AGAIN_FAILED", "first-run evidence missing")]
    ctx = _context()
    uv = cast(str, evidence["uv_path"])
    done = _chain(ctx, uv)
    shared = _lines(ctx.log_path)[cast(int, evidence["shared_count"]) :]
    starts = [line for line in shared if line.endswith(" update-all start")]
    results = [
        line
        for line in shared
        if any(f" update-all {word}:" in line for word in ("ok", "skipped", "failed"))
    ]
    logs = _lines(schedules.update_all_log_path(ctx))

    def query(argv: list[str]) -> str:
        return run_query(argv, timeout=120)

    outdated = manager_versions.uv_tool_outdated(query=query)
    inventory = _ruff(uv)
    tools = load_tools(Path(installer.__file__).parent / "registry.toml")
    refresh, _updates, _policy, _install = _build_services(tools, host_platform.detect())
    ruff = tool_by_id("ruff")
    ruff_now = probed_version(ruff, refresh.resolve_owner(ruff), probe_version_output)
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/ruff/json", timeout=20) as response:
            latest = latest_version(response.read().decode("utf-8"))
    except (OSError, ValueError):
        latest = None
    return [
        *(f"UPDATE_ALL_LOG {line}" for line in logs),
        *(f"UPDATE_ALL_SHARED_LOG {line}" for line in shared),
        again_verdict(
            done.returncode,
            starts,
            results,
            _tools(logs),
            evidence,
            ruff_now,
            outdated,
            inventory,
            latest,
        ),
    ]


_HANDLERS: dict[str, Callable[[Path], list[str]]] = {
    "plan-managers": lambda home: _plan(home, seeded=False),
    "seed": _seed,
    "plan": lambda home: _plan(home, seeded=True),
    "run": _run,
    "again": _again,
}


def accepts(args: Sequence[str]) -> bool:
    return len(args) == 1 and args[0] in _HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print(f"usage: e2e_update_all_driver {' | '.join(_HANDLERS)}", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the update-all driver runs only inside the disposable container")
        return 2
    try:
        lines = _HANDLERS[args[0]](Path.home())
    except Failed as error:
        print(verdict(error.prefix, first_line(error.detail)))
        return 1
    except (OSError, CommandError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR {first_line(error) or type(error).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line or "_UNPROVEN" in line for line in lines) else 0


if __name__ == "__main__":
    raise SystemExit(main())
