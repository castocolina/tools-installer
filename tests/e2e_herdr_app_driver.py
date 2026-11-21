"""Container-only herdr-app lifecycle proof for scripts/container-e2e-verify.sh herdr-app.

Run ``python -m tests.e2e_herdr_app_driver lifecycle``. Checks print verdict lines;
FAILED or UNPROVEN exits 1, invalid arguments or a non-container exits 2.
"""

import datetime
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from installer import platform as host_platform
from installer import receipts
from installer.agent_settings import insert_key
from installer.herdr_app_keys import (
    HERDR_APP_DEFAULTS_VERSION,
    herdr_app_owned_keys,
    parse_app_version,
    vendor_default,
)
from installer.receipts import ReceiptArtifact
from installer.run import CommandError, run_command
from installer.uninstall import SweepResult
from tests.e2e_ghostty_driver import allowed_prefixes as allowed_prefixes
from tests.e2e_ghostty_driver import home_listing, inspect_tmp, leftovers, tmp_leftovers
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    uninstall_one,
    verdict,
)

TOOL_ID: Final = "herdr-app"
OTHER_ID: Final = "herdr"
ALLOWLIST: Final = Path("scripts") / "e2e-residue-allowlist.txt"
# The nested core install remains by design, allowed here and never in the shared allowlist.
TARGET_ALLOWED: Final = (".local/bin/herdr-core", ".local/bin/hc")
STANDARD_EMPTY_DIRS: Final = frozenset(
    {
        ".local/share/applications/",
        ".local/share/icons/",
        ".local/share/icons/hicolor/",
        ".local/share/icons/hicolor/scalable/",
        ".local/share/icons/hicolor/scalable/apps/",
        ".local/share/tools-installer/",
    }
)
RUN_SECONDS: Final = 60.0
ORDERS: Final = ("app-first", "herdr-first")
KEYS_RELATIVE: Final = ".config/herdr-app/keys.json"
RECORD_PREFIX: Final = ".local/share/tools-installer/"
SEED_RELATIVE: Final = ".config/herdr/config.toml"
SEED_TEXT: Final = "# isolation seed\n"
EXPECTED_LINES: Final[dict[str, tuple[str, ...]]] = {
    "app-first": (
        "TRACER_HERDR_APP_INSTALL_OK order=app-first method=script version=herdr-app ",
        "TRACER_HERDR_APP_KEYS_OK order=app-first",
        "TRACER_HERDR_APP_REVERSE_OK order=app-first point=install",
        "TRACER_HERDR_APP_ISOLATION_OK order=app-first point=removal",
        "TRACER_HERDR_APP_REVERSE_OK order=app-first point=removal",
    ),
    "herdr-first": (
        "TRACER_HERDR_APP_INSTALL_OK order=herdr-first method=script version=herdr-app ",
        "TRACER_HERDR_APP_KEYS_OK order=herdr-first",
        "TRACER_HERDR_APP_ISOLATION_OK order=herdr-first point=install",
        "TRACER_HERDR_APP_ISOLATION_OK order=herdr-first point=removal",
        "TRACER_HERDR_APP_REMOVE_OK order=herdr-first",
        "TRACER_HERDR_APP_REVERSE_OK order=herdr-first point=removal",
    ),
}


def version_ok(line: str) -> bool:
    return re.fullmatch(r"herdr-app \d+\.\d+\.\d+\S*", line) is not None


def install_verdict(
    order: str,
    method_kind: str,
    returncode: int,
    version_line: str,
    missing: Sequence[str],
    receipt_missing: Sequence[str],
) -> str:
    problems: list[str] = []
    if method_kind != "script":
        problems.append(f"method {method_kind} is not script")
    if returncode:
        problems.append(f"herdr-app --version exited {returncode}")
    if not version_ok(version_line):
        problems.append(f"herdr-app --version printed {version_line or 'nothing'}")
    problems.extend(f"{p} is missing" for p in missing)
    problems.extend(f"the receipt lacks {p}" for p in receipt_missing)
    return (
        verdict(f"TRACER_HERDR_APP_INSTALL_FAILED order={order}", "; ".join(problems))
        if problems
        else f"TRACER_HERDR_APP_INSTALL_OK order={order} method=script version={version_line}"
    )


def expected_keys_text(platform_os: str) -> str:
    text = vendor_default(platform_os)
    for key, value in herdr_app_owned_keys(platform_os):
        text = insert_key(text, "json", key, value).text
    return text


def keys_verdict(order: str, text: str | None, expected: str, installed_version: str | None) -> str:
    prefix = "TRACER_HERDR_APP_KEYS"
    version = installed_version or "unknown"
    if installed_version != HERDR_APP_DEFAULTS_VERSION:
        if text is None:
            return verdict(
                f"{prefix}_UNPROVEN order={order} installed={version} "
                f"pinned={HERDR_APP_DEFAULTS_VERSION}",
                "the seeded keys were not written because the installed herdr-app differs "
                "from the pinned default; retry after a pin bump",
            )
        return verdict(
            f"{prefix}_FAILED order={order}",
            f"keys.json was written although the installed herdr-app is {version} "
            f"and the pinned default is for {HERDR_APP_DEFAULTS_VERSION}",
        )
    if text is None:
        return verdict(f"{prefix}_FAILED order={order}", "keys.json is missing")
    if text != expected:
        from itertools import zip_longest

        number = next(
            (
                i
                for i, (a, b) in enumerate(zip_longest(text.splitlines(), expected.splitlines()), 1)
                if a != b
            ),
            max(len(text.splitlines()), 1),
        )
        return verdict(
            f"{prefix}_FAILED order={order}",
            f"keys.json differs from the seeded golden at line {number}",
        )
    return f"{prefix}_OK order={order}"


def digest_path(path: Path) -> str:
    if path.is_symlink():
        return hashlib.sha256(os.readlink(path).encode()).hexdigest()
    if not path.exists():
        return "absent"
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    lines: list[str] = []
    for root, dirs, files in os.walk(path, followlinks=False):
        base = Path(root)
        for name in list(dirs):
            item = base / name
            if item.is_symlink():
                dirs.remove(name)
                lines.append(f"{item.relative_to(path).as_posix()}\t{digest_path(item)}")
            elif not any(item.iterdir()):
                lines.append(f"{item.relative_to(path).as_posix()}/")
        lines.extend(
            f"{(base / name).relative_to(path).as_posix()}\t{digest_path(base / name)}"
            for name in files
        )
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()


def digest_paths(paths: Sequence[Path]) -> str:
    return hashlib.sha256(
        "\n".join(sorted(f"{p}\t{digest_path(p)}" for p in paths)).encode()
    ).hexdigest()


def isolation_verdict(
    order: str, point: str, before: tuple[str, str], after: tuple[str, str]
) -> str:
    names = ("the herdr binary", "~/.config/herdr")
    prefix = "TRACER_HERDR_APP_ISOLATION"
    for name, value in zip(names, before, strict=True):
        if value == "absent":
            return verdict(
                f"{prefix}_UNPROVEN order={order} point={point}",
                f"{name} was absent before the app {point}; there was nothing to preserve",
            )
    changes = [f"{name} changed" for name, a, b in zip(names, before, after, strict=True) if a != b]
    return (
        verdict(
            f"{prefix}_FAILED order={order} point={point}",
            f"after the app {point}: {'; '.join(changes)}",
        )
        if changes
        else f"{prefix}_OK order={order} point={point}"
    )


def reverse_verdict(
    order: str, point: str, before: tuple[str, str, str], after: tuple[str, str, str]
) -> str:
    names = ("the herdr-app binary", "the herdr-app paths", "~/.config/herdr-app")
    prefix = "TRACER_HERDR_APP_REVERSE"
    for name, value in zip(names[:2], before[:2], strict=True):
        if value == "absent":
            return verdict(
                f"{prefix}_UNPROVEN order={order} point={point}",
                f"{name} was absent before the multiplexer {point}; there was nothing to preserve",
            )
    changes = [f"{name} changed" for name, a, b in zip(names, before, after, strict=True) if a != b]
    return (
        verdict(
            f"{prefix}_FAILED order={order} point={point}",
            f"after the multiplexer {point}: {'; '.join(changes)}",
        )
        if changes
        else f"{prefix}_OK order={order} point={point}"
    )


def removal_problem(tool_id: str, result: SweepResult) -> str | None:
    for name, detail in result.remove_failed:
        if name == tool_id:
            return f"{tool_id} removal failed: {detail}"
    return None if tool_id in result.removed else f"{tool_id} was not removed"


def is_state_record(path: str) -> bool:
    return path in {
        RECORD_PREFIX + name
        for name in (
            "terminal-tuning-herdr-app",
            "terminal-herdr-app-created",
            "terminal-herdr-app-created-path",
        )
    }


def target_leftovers(
    before: Sequence[str], after: Sequence[str], allowed: Sequence[str]
) -> list[str]:
    return [p for p in leftovers(before, after, allowed) if p.rstrip("/") not in TARGET_ALLOWED]


def remove_verdict(
    order: str,
    *,
    before: Sequence[str],
    installed: Sequence[str],
    after: Sequence[str],
    allowed: Sequence[str],
    receipt_paths: Sequence[str],
    receipt_left: bool,
    records_left: Sequence[str],
    keys_expected: bool,
) -> str:
    expected = [*receipt_paths, *([KEYS_RELATIVE] if keys_expected else [])]
    problems = [
        f"{p} is missing after the install" for p in lacking(expected, installed, descendants=True)
    ]
    remaining = [
        p for p in target_leftovers(before, after, allowed) if p not in STANDARD_EMPTY_DIRS
    ]
    problems.extend(f"{p} still present" for p in remaining[:10])
    if len(remaining) > 10:
        problems.append(f"and {len(remaining) - 10} more")
    problems.extend(f"{p} existed before the install and is gone" for p in lacking(before, after))
    if receipt_left:
        problems.append("the receipt is still present")
    problems.extend(f"{p} is still present" for p in records_left)
    return (
        verdict(f"TRACER_HERDR_APP_REMOVE_FAILED order={order}", "; ".join(problems))
        if problems
        else f"TRACER_HERDR_APP_REMOVE_OK order={order}"
    )


def transcript_problem(text: str) -> str | None:
    lines = [line for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(marker in line for marker in ("_FAILED", "_UNPROVEN", "TRACER_LANDING_INFEASIBLE")):
            return f"{line} is in the transcript"
    for prefixes in EXPECTED_LINES.values():
        for prefix in prefixes:
            if not any(line.startswith(prefix) for line in lines):
                return f"the transcript lacks {prefix}"
    if not lines or lines[-1] != "TRACER_LANDING_TEARDOWN_OK":
        return "the transcript does not end with TRACER_LANDING_TEARDOWN_OK"
    return None


def transcript_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


PASS_LINE: Final = re.compile(
    r"herdr-app-container: PASS \((\d{4}-\d{2}-\d{2}); transcript ([0-9a-f]{12})(?:; ([^)]+))?\)"
)


def gate_problem(summary: str | None, transcript: bytes | None) -> str | None:
    if summary is None:
        return "summary is missing"
    if transcript is None:
        return "transcript is missing"
    lines = summary.splitlines()
    try:
        start = lines.index("## Orchestrator verification")
    except ValueError:
        return "verification section is missing"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    matches = [(i, line) for i, line in enumerate(lines) if line.startswith("herdr-app-container:")]
    if len(matches) != 1:
        return "expected exactly one herdr-app-container line"
    index, line = matches[0]
    if not start < index < end:
        return "herdr-app-container line is outside the verification section"
    match = PASS_LINE.fullmatch(line)
    if match is None:
        return "malformed herdr-app-container line"
    date, digest, note = match.groups()
    if note and any(marker in note for marker in ("UNPROVEN", "INFEASIBLE")):
        return f"verification note contains {note}"
    try:
        if datetime.date.fromisoformat(date).isoformat() != date:
            return "invalid date"
    except ValueError:
        return "invalid date"
    problem = transcript_problem(transcript.decode("utf-8", errors="replace"))
    if problem:
        return problem
    if transcript_digest(transcript) != digest:
        return "transcript digest does not match"
    return None


def norm_path(path: str) -> str:
    return path.rstrip("/")


def declared_app_paths(entries: Sequence[str]) -> tuple[str, ...]:
    return tuple(p.removeprefix("~/") for p in entries)


def receipt_relative_paths(artifacts: Sequence[ReceiptArtifact], home: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            norm_path(
                a.path.relative_to(home).as_posix()
                if a.path.is_relative_to(home)
                else a.path.as_posix()
            )
            for a in artifacts
        )
    )


def lacking(
    declared: Sequence[str], present: Sequence[str], *, descendants: bool = False
) -> list[str]:
    found = {norm_path(p) for p in present}
    return [
        p
        for p in declared
        if not any(
            q == norm_path(p) or (descendants and q.startswith(norm_path(p) + "/")) for q in found
        )
    ]


def purge_paths(tool_id: str, declared: Sequence[str]) -> tuple[str, ...]:
    if tool_id == OTHER_ID:
        return (".local/bin/herdr",)
    if tool_id != TOOL_ID:
        raise ValueError(f"unknown tool: {tool_id}")
    return (
        *declared,
        ".config/herdr-app/",
        *(
            RECORD_PREFIX + name
            for name in (
                "terminal-tuning-herdr-app",
                "terminal-herdr-app-created",
                "terminal-herdr-app-created-path",
            )
        ),
    )


def purge_targets(
    tool_id: str, declared: Sequence[str], before: Sequence[str], after: Sequence[str]
) -> tuple[str, ...]:
    old, new = {norm_path(p) for p in before}, {norm_path(p) for p in after}
    return tuple(
        p for p in purge_paths(tool_id, declared) if norm_path(p) in new and norm_path(p) not in old
    )


def seed_multiplexer_config(home: Path) -> None:
    path = home / SEED_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SEED_TEXT, encoding="utf-8")


def clear_multiplexer_seed(home: Path) -> None:
    path = home / SEED_RELATIVE
    path.unlink(missing_ok=True)
    if path.parent.is_dir() and not any(path.parent.iterdir()):
        path.parent.rmdir()


def run_version(binary: Path, scratch: Path, seconds: float = RUN_SECONDS) -> tuple[int, str, str]:
    out_file, err_file = scratch / "version.out", scratch / "version.err"
    try:
        with out_file.open("wb") as out, err_file.open("wb") as err:
            process = subprocess.Popen(
                [str(binary), "--version"],
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        return (
            code,
            first_line(out_file.read_text(errors="replace")),
            err_file.read_text(errors="replace"),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", first_line(exc)


@dataclass(frozen=True)
class Ops:
    seed_config: Callable[[], None]
    clear_seed: Callable[[], None]
    install: Callable[[str], None]
    remove: Callable[[str], SweepResult]
    installed: Callable[[str], bool]
    multiplexer: Callable[[], tuple[str, str]]
    app: Callable[[], tuple[str, str, str]]
    listing: Callable[[], list[str]]
    version: Callable[[], tuple[int, str]]
    keys_text: Callable[[], str | None]
    receipt: Callable[[], tuple[str, tuple[str, ...]] | None]
    records_left: Callable[[], tuple[str, ...]]
    purge: Callable[[str, tuple[str, ...]], None]


def run_order(
    order: str, ops: Ops, *, expected_keys: str, declared: tuple[str, ...], allowed: Sequence[str]
) -> list[str]:
    lines: list[str] = []
    attempted: list[str] = []
    baselines: dict[str, list[str]] = {}
    current: str | None = None
    phase = "INSTALL"

    def install(tool: str) -> None:
        nonlocal current
        baselines[tool] = ops.listing()
        attempted.append(tool)
        current = tool
        ops.install(tool)
        current = None

    def remove(tool: str) -> None:
        problem = removal_problem(tool, ops.remove(tool))
        if problem:
            raise Failed("TRACER_HERDR_APP_REMOVE_FAILED", problem)

    try:
        if order not in ORDERS:
            raise ValueError(f"unknown order: {order}")
        ops.seed_config()
        m0 = ("absent", "absent")
        if order == "herdr-first":
            install(OTHER_ID)
            before_listing = ops.listing()
            m0 = ops.multiplexer()
        else:
            before_listing = []
        install(TOOL_ID)
        receipt = ops.receipt()
        kind, paths = receipt if receipt else ("unknown", ())
        rc, version = ops.version()
        lines.append(
            install_verdict(
                order,
                kind,
                rc,
                version,
                lacking(declared, ops.listing(), descendants=True),
                lacking(declared, paths),
            )
        )
        lines.append(
            keys_verdict(order, ops.keys_text(), expected_keys, parse_app_version(version))
        )
        if order == "herdr-first":
            lines.append(isolation_verdict(order, "install", m0, ops.multiplexer()))
        else:
            x0 = ops.app()
            install(OTHER_ID)
            lines.append(reverse_verdict(order, "install", x0, ops.app()))
        installed_listing = ops.listing()
        phase = "REMOVE"
        m0 = ops.multiplexer()
        remove(TOOL_ID)
        lines.append(isolation_verdict(order, "removal", m0, ops.multiplexer()))
        if order == "herdr-first":
            lines.append(
                remove_verdict(
                    order,
                    before=before_listing,
                    installed=installed_listing,
                    after=ops.listing(),
                    allowed=allowed,
                    receipt_paths=paths,
                    receipt_left=ops.receipt() is not None,
                    records_left=ops.records_left(),
                    keys_expected=parse_app_version(version) == HERDR_APP_DEFAULTS_VERSION,
                )
            )
        phase = "INSTALL"
        install(TOOL_ID)
        phase = "REVERSE"
        x0 = ops.app()
        remove(OTHER_ID)
        lines.append(reverse_verdict(order, "removal", x0, ops.app()))
    except (Failed, OSError, ValueError, CommandError) as exc:
        prefix = exc.prefix if isinstance(exc, Failed) else f"TRACER_HERDR_APP_{phase}_FAILED"
        detail = exc.detail if isinstance(exc, Failed) else first_line(exc)
        lines.append(verdict(prefix, detail))
        if current is not None and not ops.installed(current):
            stray = target_leftovers(baselines[current], ops.listing(), allowed)
            if stray:
                extra = f", and {len(stray) - 10} more" if len(stray) > 10 else ""
                lines.append(
                    verdict(
                        f"TRACER_HERDR_APP_INSTALL_FAILED order={order}",
                        f"{current} left files without a receipt: {', '.join(stray[:10])}{extra}",
                    )
                )
    finally:
        for tool in (TOOL_ID, OTHER_ID):
            try:
                if ops.installed(tool):
                    problem = removal_problem(tool, ops.remove(tool))
                    if problem:
                        lines.append(
                            verdict("TRACER_HERDR_APP_REMOVE_FAILED", f"cleanup: {problem}")
                        )
            except (Failed, OSError, ValueError, CommandError) as exc:
                lines.append(
                    verdict("TRACER_HERDR_APP_REMOVE_FAILED", f"cleanup: {first_line(exc)}")
                )
        for tool in dict.fromkeys(attempted):
            try:
                if not ops.installed(tool):
                    ops.purge(tool, purge_targets(tool, declared, baselines[tool], ops.listing()))
            except (Failed, OSError, ValueError, CommandError) as exc:
                lines.append(
                    verdict("TRACER_HERDR_APP_REMOVE_FAILED", f"cleanup: {first_line(exc)}")
                )
        ops.clear_seed()
    return lines


def _lifecycle() -> list[str]:
    """Real container wiring; host tests exercise decisions through run_order."""
    home = Path.home()
    method = next(m for m in tool_by_id(TOOL_ID).methods if m.kind == "script")
    raw_paths = method.params["paths"]
    if not isinstance(raw_paths, list):
        raise ValueError("invalid script paths")
    entries = cast(list[object], raw_paths)
    if not all(isinstance(p, str) for p in entries):
        raise ValueError("invalid script paths")
    declared = declared_app_paths(cast(list[str], entries))
    binary = home / ".local/bin/herdr-app"
    expected = expected_keys_text(host_platform.detect().os)

    def install(tool: str) -> None:
        install_one(tool_by_id(tool), "TRACER_HERDR_APP_INSTALL_FAILED")

    def receipt() -> tuple[str, tuple[str, ...]] | None:
        found = receipts.read(TOOL_ID)
        return (found.method.kind, receipt_relative_paths(found.artifacts, home)) if found else None

    def purge(tool: str, targets: tuple[str, ...]) -> None:
        del tool
        for target in targets:
            path = home / norm_path(target)
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)

    def keys() -> str | None:
        path = home / KEYS_RELATIVE
        return path.read_text(encoding="utf-8") if path.exists() else None

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:

        def version() -> tuple[int, str]:
            code, line, _ = run_version(binary, Path(directory))
            return code, line

        ops = Ops(
            lambda: seed_multiplexer_config(home),
            lambda: clear_multiplexer_seed(home),
            install,
            lambda tool: uninstall_one(tool_by_id(tool), run_command),
            lambda tool: receipts.read(tool) is not None,
            lambda: (digest_path(home / ".local/bin/herdr"), digest_path(home / ".config/herdr")),
            lambda: (
                digest_path(binary),
                digest_paths([home / norm_path(p) for p in declared]),
                digest_path(home / ".config/herdr-app"),
            ),
            lambda: home_listing(home, Path.cwd()),
            version,
            keys,
            receipt,
            lambda: tuple(p for p in home_listing(home, Path.cwd()) if is_state_record(p)),
            purge,
        )
        allowed = allowed_prefixes(ALLOWLIST.read_text(encoding="utf-8"))
        lines = [
            line
            for order in ORDERS
            for line in run_order(
                order, ops, expected_keys=expected, declared=declared, allowed=allowed
            )
        ]
        lines.extend(
            verdict("TRACER_HERDR_APP_REMOVE_FAILED", f"/tmp holds {name}")
            for name in tmp_leftovers(inspect_tmp())
        )
        return lines


def accepts(args: Sequence[str]) -> bool:
    return len(args) == 1 and args[0] in _HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print("usage: e2e_herdr_app_driver lifecycle", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the herdr-app driver runs only inside the disposable container")
        return 2
    try:
        lines = _HANDLERS[args[0]]()
    except Failed as exc:
        print(verdict(exc.prefix, first_line(exc.detail)))
        return 1
    except (OSError, ValueError) as exc:
        print(f"ERROR {first_line(exc) or type(exc).__name__}")
        return 1
    print("\n".join(lines))
    return 1 if any("_FAILED" in line or "_UNPROVEN" in line for line in lines) else 0


_HANDLERS: dict[str, Callable[[], list[str]]] = {"lifecycle": _lifecycle}


if __name__ == "__main__":
    raise SystemExit(main())
