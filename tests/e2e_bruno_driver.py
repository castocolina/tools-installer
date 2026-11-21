"""Container-only Bruno lifecycle; FAILED or UNPROVEN exits 1, invalid invocation exits 2."""

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from installer import platform as host_platform
from installer import receipts
from installer.enums import InstallStatus
from installer.run import run_command
from tests.e2e_evidence import gate_problem
from tests.e2e_ghostty_driver import (
    STANDARD_EMPTY_DIRS,
    allowed_prefixes,
    current_content,
    home_listing,
    inspect_tmp,
    leftovers,
)
from tests.e2e_herdr_app_driver import removal_problem
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    uninstall_one,
    verdict,
)

TOOL_ID = "bruno"
RUN_SECONDS = 60.0
SEED: Final = {
    "Documents/bruno/collection.json": '{"name": "seed"}\n',
    ".config/bruno/preferences.json": '{"seed": true}\n',
}
EXPECTED_LINES: Final[dict[str, tuple[str, ...]]] = {
    "install": ("TRACER_BRUNO_INSTALL_OK method=tarball version=4.3.0",),
    "run": ("TRACER_BRUNO_RUN_OK mode=",),
    "remove": ("TRACER_BRUNO_REMOVE_OK",),
}


@dataclass(frozen=True)
class RunMode:
    name: str
    env: Mapping[str, str]
    args: tuple[str, ...]


MODES = (
    RunMode("as-is", {}, ("--version",)),
    RunMode("no-sandbox", {}, ("--no-sandbox", "--version")),
    RunMode("extract", {"APPIMAGE_EXTRACT_AND_RUN": "1"}, ("--version",)),
    RunMode("extract-no-sandbox", {"APPIMAGE_EXTRACT_AND_RUN": "1"}, ("--no-sandbox", "--version")),
)


@dataclass(frozen=True)
class RunAttempt:
    mode: str
    returncode: int | None
    first_line: str


def install_verdict(
    status: str, kind: str, binary: Path, receipt_paths: Sequence[Path], arch: str
) -> str:
    problems: list[str] = []
    if status != "INSTALLED":
        problems.append(f"install ended {status}")
    if kind != "tarball":
        problems.append(f"method {kind} is not tarball")
    if not binary.is_file():
        problems.append(f"{binary} is missing")
    elif not os.access(binary, os.X_OK):
        problems.append(f"{binary} is not executable")
    if binary not in receipt_paths:
        problems.append(f"receipt lacks {binary}")
    if arch not in ("amd64", "arm64"):
        problems.append(f"unknown arch {arch}")
    return (
        verdict("TRACER_BRUNO_INSTALL_FAILED", "; ".join(problems))
        if problems
        else f"TRACER_BRUNO_INSTALL_OK method=tarball version=4.3.0 arch={arch}"
    )


def run_verdict(attempts: Sequence[RunAttempt]) -> str:
    for attempt in attempts:
        if attempt.returncode == 0 and re.search(r"\d+\.\d+", attempt.first_line):
            return f"TRACER_BRUNO_RUN_OK mode={attempt.mode}"
    detail = (
        "; ".join(
            f"{a.mode} exit={a.returncode if a.returncode is not None else 'timeout'}: "
            f"{a.first_line[:120]}"
            for a in attempts
        )
        or "no mode ran"
    )
    return verdict("TRACER_BRUNO_RUN_UNPROVEN", detail)


def remove_verdict(
    *,
    sweep_problem: str | None,
    paths_left: Sequence[str],
    receipt_left: bool,
    before: Sequence[str],
    after: Sequence[str],
    allowed: Sequence[str],
    seeded: Mapping[str, str],
    current: Mapping[str, str | None],
) -> str:
    problems = [sweep_problem] if sweep_problem else []
    problems.extend(f"{p} still present" for p in paths_left)
    if receipt_left:
        problems.append("receipt still present")
    problems.extend(f"{p} changed" for p in sorted(seeded) if current.get(p) != seeded[p])
    problems.extend(f"{p} existed before and is gone" for p in sorted(set(before) - set(after)))
    problems.extend(
        f"{p} still present"
        for p in leftovers(before, after, allowed)
        if p not in STANDARD_EMPTY_DIRS
    )
    return (
        verdict("TRACER_BRUNO_REMOVE_FAILED", "; ".join(problems))
        if problems
        else "TRACER_BRUNO_REMOVE_OK"
    )


def _recorded(summary: str | None, transcript: bytes | None) -> tuple[str, list[str]] | None:
    if (
        gate_problem("bruno-container", summary, transcript, EXPECTED_LINES) is not None
        or transcript is None
    ):
        return None
    lines = transcript.decode("utf-8", errors="replace").splitlines()
    runs = [
        line.removeprefix("TRACER_BRUNO_RUN_OK mode=")
        for line in lines
        if line.startswith("TRACER_BRUNO_RUN_OK mode=")
    ]
    if len(runs) != 1 or runs[0] not in {m.name for m in MODES}:
        return None
    return runs[0], lines


def recorded_smoke_mode(summary: str | None, transcript: bytes | None) -> str | None:
    found = _recorded(summary, transcript)
    return found[0] if found else None


def recorded_smoke_arch(summary: str | None, transcript: bytes | None) -> str | None:
    found = _recorded(summary, transcript)
    if found is None:
        return None
    lines = [line for line in found[1] if line.startswith("TRACER_BRUNO_INSTALL_OK")]
    if len(lines) != 1:
        return None
    match = re.fullmatch(
        r"TRACER_BRUNO_INSTALL_OK method=tarball version=4\.3\.0 arch=(amd64|arm64)", lines[0]
    )
    return match.group(1) if match else None


def smoke_argv_for(mode: str) -> tuple[str, ...] | None:
    row = next((row for row in MODES if row.name == mode), None)
    if row is None:
        raise ValueError(f"unknown mode: {mode}")
    return row.args if not row.env and row.args != ("--version",) else None


@dataclass(frozen=True)
class LifecycleState:
    binary_exists: bool
    receipt_exists: bool
    removal_verdict: str


def lifecycle_steps(
    install: Callable[[], str],
    run_modes: Callable[[], list[RunAttempt]],
    remove: Callable[[], str | None],
    state: Callable[[], LifecycleState],
) -> list[str]:
    lines: list[str] = []
    try:
        lines.append(install())
    except Failed as exc:
        if "smoke run failed for" not in exc.detail:
            return [verdict(exc.prefix, first_line(exc.detail))]
        loader = re.search(r"error while loading shared libraries:[^\n]*", exc.detail)
        detail = loader.group(0) if loader else first_line(exc.detail)
        lines.append(
            verdict("TRACER_BRUNO_INSTALL_UNPROVEN", f"engine-smoke-failed: {detail[:120]}")
        )
    snapshot = state()
    lines.append(run_verdict(run_modes() if snapshot.binary_exists else []))
    problem = remove() if snapshot.receipt_exists else None
    removal = state().removal_verdict
    if problem:
        removal = verdict("TRACER_BRUNO_REMOVE_FAILED", problem + "; " + removal)
    lines.append(removal)
    return lines


def run_mode(binary: Path, scratch: Path, mode: RunMode) -> RunAttempt:
    env = dict(os.environ)
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "APPIMAGE_EXTRACT_AND_RUN"):
        env.pop(name, None)
    env.update(mode.env)
    env["TMPDIR"] = str(scratch)
    output = scratch / "out"
    error = scratch / "err"
    try:
        with output.open("wb") as out, error.open("wb") as err:
            process = subprocess.Popen(
                [str(binary), *mode.args],
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                env=env,
                start_new_session=True,
            )
            try:
                code: int | None = process.wait(timeout=RUN_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                code = None
        text = output.read_text(errors="replace") or error.read_text(errors="replace")
        return RunAttempt(mode.name, code, first_line(text))
    except OSError as exc:
        return RunAttempt(mode.name, -1, first_line(exc))


def _lifecycle() -> list[str]:
    home = Path.home()
    binary = home / ".local/bin/bruno"
    if binary.exists() or shutil.which(TOOL_ID) or receipts.read(TOOL_ID):
        raise Failed("TRACER_BRUNO_INSTALL_FAILED", "bruno already present")
    for name, text in SEED.items():
        path = home / name
        if path.exists():
            raise Failed("TRACER_BRUNO_INSTALL_FAILED", f"seed already exists: {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    before = home_listing(home, Path.cwd())
    tmp_before = set(inspect_tmp())
    allowed = allowed_prefixes(
        Path("scripts/e2e-residue-allowlist.txt").read_text(encoding="utf-8")
    )
    tool = tool_by_id(TOOL_ID)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        scratch = Path(directory)

        def install() -> str:
            outcome = install_one(tool, "TRACER_BRUNO_INSTALL_FAILED")
            receipt = receipts.read(TOOL_ID)
            paths = [a.path for a in receipt.artifacts] if receipt else []
            status = (
                "INSTALLED" if outcome.status is InstallStatus.INSTALLED else str(outcome.status)
            )
            return install_verdict(
                status, outcome.method_kind or "unknown", binary, paths, host_platform.detect().arch
            )

        def remove() -> str | None:
            return removal_problem(TOOL_ID, uninstall_one(tool, run_command))

        def state() -> LifecycleState:
            receipt = receipts.read(TOOL_ID)
            after = home_listing(home, Path.cwd())
            paths = [str(binary)] if binary.exists() or binary.is_symlink() else []
            paths.extend(f"/tmp/{name}" for name in sorted(set(inspect_tmp()) - tmp_before))
            line = remove_verdict(
                sweep_problem=None,
                paths_left=paths,
                receipt_left=receipt is not None,
                before=before,
                after=after,
                allowed=allowed,
                seeded=SEED,
                current=current_content(home, SEED),
            )
            return LifecycleState(binary.exists(), receipt is not None, line)

        return lifecycle_steps(
            install, lambda: [run_mode(binary, scratch, mode) for mode in MODES], remove, state
        )


def accepts(args: Sequence[str]) -> bool:
    return len(args) == 1 and args[0] in HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print("usage: e2e_bruno_driver lifecycle", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the bruno driver runs only inside the disposable container")
        return 2
    try:
        lines = HANDLERS[args[0]]()
    except Failed as exc:
        print(verdict(exc.prefix, first_line(exc.detail)))
        return 1
    except (OSError, ValueError) as exc:
        print(f"ERROR {first_line(exc) or type(exc).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line or "_UNPROVEN" in line for line in lines) else 0


HANDLERS: dict[str, Callable[[], list[str]]] = {"lifecycle": _lifecycle}

if __name__ == "__main__":
    raise SystemExit(main())
