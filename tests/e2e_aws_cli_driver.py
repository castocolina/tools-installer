"""AWS lifecycle in the disposable container; nogpg-verdict reads host evidence.

FAILED exits 1; invalid arguments or lifecycle outside the container exit 2.
"""

import re
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from installer import executors, receipts
from installer.run import CommandError, run_command
from tests import e2e_evidence
from tests.e2e_ghostty_driver import allowed_prefixes, home_listing, leftovers
from tests.e2e_herdr_app_driver import ALLOWLIST, STANDARD_EMPTY_DIRS, digest_path, run_version
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    uninstall_one,
    verdict,
)

TOOL_ID = "aws-cli"
GPG_LOG = Path("/var/tmp/tools-installer-e2e-aws-gpg.log")
NOGPG_BEFORE = "TRACER_AWS_NOGPG_BEFORE"
NOGPG_SCRIPT = "TRACER_AWS_NOGPG_SCRIPT"
NOGPG_AFTER = "TRACER_AWS_NOGPG_AFTER"
NOGPG_END = "TRACER_AWS_NOGPG_END"
SEED = {
    ".aws/config": "[default]\nregion = eu-west-1\n",
    ".aws/credentials": "[default]\naws_access_key_id = AKIAEXAMPLEFAKE\n",
}
EXPECTED_LINES = {
    "install": ("TRACER_AWS_INSTALL_OK method=script version=aws-cli/2.",),
    "rerun": ("TRACER_AWS_RERUN_OK",),
    "remove": ("TRACER_AWS_REMOVE_OK",),
    "nogpg": ("TRACER_AWS_NOGPG_OK",),
}


def install_verdict(
    method: str,
    returncode: int,
    version: str,
    binary: str,
    declared: Sequence[str],
    recorded: Sequence[str],
    log: str,
) -> str:
    problems: list[str] = []
    if method != "script":
        problems.append(f"method {method} is not script")
    if returncode:
        problems.append(f"version exited {returncode}")
    if not re.match(r"aws-cli/2\.\d", version):
        problems.append(f"invalid version {version}")
    if binary != ".local/bin/aws":
        problems.append(f"binary is {binary}, not .local/bin/aws")
    problems.extend(
        f"receipt lacks {p}"
        for p in declared
        if p.rstrip("/") not in {r.rstrip("/") for r in recorded}
    )
    if not re.search(r"(?:^|\s)--verify(?:\s|$)", log):
        problems.append("gpg --verify not observed")
    return (
        verdict("TRACER_AWS_INSTALL_FAILED", "; ".join(problems))
        if problems
        else f"TRACER_AWS_INSTALL_OK method=script version={version}"
    )


def rerun_verdict(
    returncode: int, before_tree: str, after_tree: str, before_aws: str, after_aws: str
) -> str:
    problems: list[str] = []
    if returncode:
        problems.append(f"rerun exited {returncode}")
    if before_tree != after_tree:
        problems.append("install tree changed")
    if before_aws != after_aws:
        problems.append("~/.aws changed")
    return (
        verdict("TRACER_AWS_RERUN_FAILED", "; ".join(problems))
        if problems
        else "TRACER_AWS_RERUN_OK"
    )


def remove_verdict(
    sweep: str,
    left: Sequence[str],
    receipt: bool,
    seeded: Mapping[str, str],
    current: Mapping[str, str],
    before: Sequence[str],
    after: Sequence[str],
    allowed: Sequence[str],
) -> str:
    problems = [sweep] if sweep else []
    problems.extend(f"{p} still present" for p in left)
    if receipt:
        problems.append("receipt still present")
    problems.extend(f"{p} changed or missing" for p in seeded if current.get(p) != seeded[p])
    problems.extend(
        f"{p} still present"
        for p in leftovers(before, after, allowed)
        if p not in STANDARD_EMPTY_DIRS
    )
    return (
        verdict("TRACER_AWS_REMOVE_FAILED", "; ".join(problems))
        if problems
        else "TRACER_AWS_REMOVE_OK"
    )


def nogpg_verdict(returncode: int, output: str) -> str:
    lines = output.splitlines()
    markers = (NOGPG_BEFORE, NOGPG_SCRIPT, NOGPG_AFTER, NOGPG_END)
    if any(lines.count(marker) != 1 for marker in markers):
        return verdict("TRACER_AWS_NOGPG_FAILED", "missing or duplicated marker")
    positions = [lines.index(marker) for marker in markers]
    if positions != sorted(positions):
        return verdict("TRACER_AWS_NOGPG_FAILED", "marker order")
    a, b, c, end = positions
    before = [line for line in lines[a + 1 : b] if line.strip()]
    script = "\n".join(lines[b + 1 : c])
    after = [line for line in lines[c + 1 : end] if line.strip()]
    problems: list[str] = []
    if returncode == 0:
        problems.append("script exit was zero")
    if "gpg not found" not in script:
        problems.append("script lacks gpg not found")
    if re.search(r"\binstalled\b", script, re.IGNORECASE):
        problems.append("script says installed")
    if before != after:
        added = sorted(set(after) - set(before))
        problems.append("install listing changed: " + ", ".join(added[:3]))
    return (
        verdict("TRACER_AWS_NOGPG_FAILED", "; ".join(problems))
        if problems
        else "TRACER_AWS_NOGPG_OK"
    )


def transcript_problem(text: str) -> str | None:
    return e2e_evidence.transcript_problem(text, EXPECTED_LINES)


def gate_problem(summary: str | None, transcript: bytes | None) -> str | None:
    return e2e_evidence.gate_problem("aws-container", summary, transcript, EXPECTED_LINES)


def lifecycle() -> list[str]:
    home = Path.home()
    if shutil.which("gpg") != "/usr/local/bin/gpg" or shutil.which("aws") is not None:
        raise Failed("TRACER_AWS_INSTALL_FAILED", "gpg shim missing or aws already present")
    tool = tool_by_id(TOOL_ID)
    method = next(m for m in tool.methods if m.kind == "script")
    raw = method.params["paths"]
    if not isinstance(raw, list) or not all(isinstance(p, str) for p in cast(list[object], raw)):
        raise ValueError("invalid declared paths")
    declared = tuple(p.removeprefix("~/").rstrip("/") for p in cast(list[str], raw))
    for name, text in SEED.items():
        path = home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    seeded = {name: digest_path(home / name) for name in SEED}
    baseline = home_listing(home, Path.cwd())
    outcome = install_one(tool, "TRACER_AWS_INSTALL_FAILED")
    binary = home / ".local/bin/aws"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        rc, version, error = run_version(binary, Path(directory))
    version = version or first_line(error)
    receipt = receipts.read(TOOL_ID)
    recorded = [a.path.relative_to(home).as_posix() for a in receipt.artifacts] if receipt else []
    lines = [
        install_verdict(
            outcome.method_kind or "unknown",
            rc,
            version,
            binary.relative_to(home).as_posix() if binary.exists() else "missing",
            declared,
            recorded,
            GPG_LOG.read_text(encoding="utf-8") if GPG_LOG.exists() else "",
        )
    ]
    tree = home / ".local/share/aws-cli"
    before_tree, before_aws = digest_path(tree), digest_path(home / ".aws")
    try:
        executors.execute(method, run_command)
        rerun_rc = 0
    except CommandError as exc:
        rerun_rc = exc.returncode
    lines.append(
        rerun_verdict(
            rerun_rc, before_tree, digest_path(tree), before_aws, digest_path(home / ".aws")
        )
    )
    result = uninstall_one(tool, run_command)
    sweep = "; ".join(f"{name}: {detail}" for name, detail in result.remove_failed)
    if TOOL_ID not in result.removed and not sweep:
        sweep = "aws-cli was not removed"
    left = [p for p in declared if (home / p).exists() or (home / p).is_symlink()]
    current = {name: digest_path(home / name) for name in SEED}
    lines.append(
        remove_verdict(
            sweep,
            left,
            receipts.receipt_exists(TOOL_ID),
            seeded,
            current,
            baseline,
            home_listing(home, Path.cwd()),
            allowed_prefixes(ALLOWLIST.read_text(encoding="utf-8")),
        )
    )
    return lines


def accepts(args: Sequence[str]) -> bool:
    return list(args) == ["lifecycle"] or (len(args) == 3 and args[0] == "nogpg-verdict")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print("usage: e2e_aws_cli_driver lifecycle | nogpg-verdict <rc> <path>", file=sys.stderr)
        return 2
    if args[0] == "lifecycle" and not in_container():
        print("ERROR the aws-cli driver runs only inside the disposable container")
        return 2
    try:
        lines = (
            lifecycle()
            if args[0] == "lifecycle"
            else [
                nogpg_verdict(
                    int(args[1]), Path(args[2]).read_text(encoding="utf-8", errors="replace")
                )
            ]
        )
    except Failed as exc:
        print(verdict(exc.prefix, first_line(exc.detail)))
        return 1
    except (OSError, ValueError, CommandError) as exc:
        print(f"ERROR {first_line(exc)}")
        return 1
    print("\n".join(lines))
    return int(any("_FAILED" in line or "_UNPROVEN" in line for line in lines))


if __name__ == "__main__":
    raise SystemExit(main())
