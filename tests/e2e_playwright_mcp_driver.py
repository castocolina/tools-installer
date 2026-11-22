"""Container-only Playwright MCP lifecycle; FAILED/UNPROVEN exit 1, bad invocation exits 2."""

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from installer import agent_settings, bun_globals, postinstall, receipts
from installer.run import CommandError, run_command
from tests import e2e_evidence
from tests.e2e_ghostty_driver import allowed_prefixes, home_listing, leftovers
from tests.e2e_herdr_app_driver import ALLOWLIST, STANDARD_EMPTY_DIRS, digest_path
from tests.e2e_landing_driver import (
    Failed,
    first_line,
    in_container,
    install_one,
    tool_by_id,
    uninstall_one,
    verdict,
)

TOOL_ID = "playwright-mcp"
PIN = "0.0.85"
PAGE_TITLE = "e2e-ok"
RPC_SECONDS = 120.0
# bun's global bin directory: `bun add -g` creates it and `bun remove -g` leaves it empty. It is
# bun's own working directory, not something this entry declares or can own, so an EMPTY one is not
# residue (a file left inside it is still reported on its own).
BUN_EMPTY_DIRS: Final = frozenset({".bun/bin/"})
SPEC = f"@playwright/mcp@{PIN}"
HOOK = "playwright-mcp-register"
HOSTS = ("codex", "cursor", "opencode")
EXPECTED_LINES = {
    "install": ("TRACER_PLAYWRIGHT_INSTALL_OK method=bun range=0.0.85",),
    "register": ("TRACER_PLAYWRIGHT_REGISTER_OK hosts=codex,cursor,opencode kept=copilot",),
    "consent": ("TRACER_PLAYWRIGHT_CONSENT_OK",),
    "launch": ("TRACER_PLAYWRIGHT_LAUNCH_OK tools=",),
    "remove": ("TRACER_PLAYWRIGHT_REMOVE_OK",),
}


@dataclass(frozen=True)
class RpcResult:
    started: bool
    replies: tuple[Mapping[str, object], ...]
    stderr_tail: str


def install_verdict(status: str, method: str, package_range: str | None) -> str:
    problems: list[str] = []
    if status != "installed":
        problems.append(f"outcome {status}")
    if method != "bun":
        problems.append(f"method {method}")
    if package_range != PIN:
        problems.append(f"range {package_range or 'missing'}")
    return (
        verdict("TRACER_PLAYWRIGHT_INSTALL_FAILED", "; ".join(problems))
        if problems
        else "TRACER_PLAYWRIGHT_INSTALL_OK method=bun range=0.0.85"
    )


def pinned(entry: Mapping[str, object] | None) -> bool:
    if entry is None:
        return False
    args = entry.get("args")
    command = entry.get("command")
    return args == [SPEC] or (
        isinstance(command, list)
        and len(cast(list[object], command)) == 2
        and cast(list[object], command)[1] == SPEC
    )


def register_verdict(
    entries: Mapping[str, Mapping[str, object] | None],
    copilot_seed: str,
    copilot: str,
    claude_seed: Mapping[str, str],
    claude: Mapping[str, str],
    hosts: Sequence[str],
    warning: str,
) -> str:
    problems = [
        f"{host} entry missing or wrong pin" for host in HOSTS if not pinned(entries.get(host))
    ]
    if copilot != copilot_seed or "copilot" not in warning or "left yours" not in warning:
        problems.append("copilot changed or not reported kept")
    problems.extend(
        f"claude {name} changed" for name in claude_seed if claude.get(name) != claude_seed[name]
    )
    if set(hosts) != set(HOSTS):
        problems.append(f"receipt hosts {','.join(hosts)}")
    return (
        verdict("TRACER_PLAYWRIGHT_REGISTER_FAILED", "; ".join(problems))
        if problems
        else "TRACER_PLAYWRIGHT_REGISTER_OK hosts=codex,cursor,opencode kept=copilot"
    )


def consent_verdict(
    seed: Mapping[str, str],
    late: Mapping[str, str],
    late_hosts: Sequence[str],
    warning: str,
    entry: Mapping[str, object] | None,
    settings_seed: str,
    settings: str,
    hosts: Sequence[str],
) -> str:
    problems = [
        f"claude {name} changed before consent" for name in seed if seed[name] != late.get(name)
    ]
    if "claude" in late_hosts:
        problems.append("claude recorded before consent")
    if "claude" not in warning or "appeared after you confirmed" not in warning:
        problems.append("late warning missing claude")
    if not pinned(entry):
        problems.append("claude entry missing or wrong pin")
    if settings != settings_seed:
        problems.append("claude settings changed")
    if "claude" not in hosts:
        problems.append("claude not recorded")
    return (
        verdict("TRACER_PLAYWRIGHT_CONSENT_FAILED", "; ".join(problems))
        if problems
        else "TRACER_PLAYWRIGHT_CONSENT_OK"
    )


def launch_verdict(result: RpcResult) -> str:
    if not result.started or len(result.replies) < 3:
        return verdict(
            "TRACER_PLAYWRIGHT_LAUNCH_UNPROVEN",
            first_line(result.stderr_tail) or "server timed out",
        )
    init, listing, navigate = result.replies[:3]
    init_result = init.get("result")
    list_result = listing.get("result")
    nav_result = navigate.get("result")
    if not isinstance(init_result, dict) or "serverInfo" not in init_result:
        return verdict("TRACER_PLAYWRIGHT_LAUNCH_FAILED", "initialize lacks serverInfo")
    tools = (
        cast(dict[str, object], list_result).get("tools") if isinstance(list_result, dict) else None
    )
    if not isinstance(tools, list) or not any(
        isinstance(item, dict) and cast(dict[str, object], item).get("name") == "browser_navigate"
        for item in cast(list[object], tools)
    ):
        return verdict("TRACER_PLAYWRIGHT_LAUNCH_FAILED", "tools/list lacks browser_navigate")
    if "error" in navigate or not isinstance(nav_result, dict):
        return verdict("TRACER_PLAYWRIGHT_LAUNCH_FAILED", "navigate error")
    nav = cast(dict[str, object], nav_result)
    content = nav.get("content")
    if (
        nav.get("isError") is True
        or not isinstance(content, list)
        or not any(
            isinstance(item, dict)
            and isinstance(cast(dict[str, object], item).get("text"), str)
            and PAGE_TITLE in cast(str, cast(dict[str, object], item)["text"])
            for item in cast(list[object], content)
        )
    ):
        return verdict("TRACER_PLAYWRIGHT_LAUNCH_FAILED", "navigate error or missing title")
    return f"TRACER_PLAYWRIGHT_LAUNCH_OK tools={len(cast(list[object], tools))} navigate=ok"


def remove_verdict(
    sweep: str,
    left: Sequence[str],
    seeded: Mapping[str, str],
    current: Mapping[str, str],
    created: Sequence[str],
    receipt: bool,
    package: bool,
    residue: Sequence[str],
) -> str:
    problems = [sweep] if sweep else []
    problems.extend(f"{name} entry remains" for name in left)
    problems.extend(f"{name} changed" for name in seeded if seeded[name] != current.get(name))
    problems.extend(f"{name} created file remains" for name in created)
    if receipt:
        problems.append("receipt remains")
    if package:
        problems.append("package remains")
    problems.extend(f"residue {name}" for name in residue)
    return (
        verdict("TRACER_PLAYWRIGHT_REMOVE_FAILED", "; ".join(problems))
        if problems
        else "TRACER_PLAYWRIGHT_REMOVE_OK"
    )


def transcript_problem(text: str) -> str | None:
    return e2e_evidence.transcript_problem(text, EXPECTED_LINES)


def gate_problem(summary: str | None, transcript: bytes | None) -> str | None:
    return e2e_evidence.gate_problem("playwright-container", summary, transcript, EXPECTED_LINES)


def frames() -> tuple[str, ...]:
    messages = (
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "tools-installer-e2e", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "browser_navigate",
                "arguments": {"url": "data:text/html,<title>e2e-ok</title>"},
            },
        },
    )
    return tuple(json.dumps(message) for message in messages)


def run_rpc(
    argv: Sequence[str], env: Mapping[str, str], messages: Sequence[str], seconds: float
) -> RpcResult:
    with tempfile.TemporaryDirectory() as directory:
        outpath, errpath = Path(directory) / "out", Path(directory) / "err"
        with outpath.open("wb") as out, errpath.open("wb") as err:
            try:
                process = subprocess.Popen(
                    list(argv),
                    stdin=subprocess.PIPE,
                    stdout=out,
                    stderr=err,
                    env=dict(env),
                    start_new_session=True,
                )
            except OSError as exc:
                return RpcResult(False, (), str(exc))
            replies: list[Mapping[str, object]] = []
            deadline = time.monotonic() + seconds
            offset = 0
            assert process.stdin is not None
            try:
                for message in messages:
                    frame = cast(dict[str, object], json.loads(message))
                    process.stdin.write((message + "\n").encode())
                    process.stdin.flush()
                    if "id" not in frame:
                        continue
                    found = False
                    while time.monotonic() < deadline and not found:
                        with outpath.open("rb") as stream:
                            stream.seek(offset)
                            while line := stream.readline():
                                if not line.endswith(b"\n"):
                                    break
                                offset = stream.tell()
                                try:
                                    reply: object = json.loads(line)
                                except ValueError:
                                    continue
                                if (
                                    isinstance(reply, dict)
                                    and cast(dict[str, object], reply).get("id") == frame["id"]
                                ):
                                    replies.append(cast(dict[str, object], reply))
                                    found = True
                                    break
                        if not found:
                            if process.poll() is not None:
                                break
                            time.sleep(0.02)
                    if not found:
                        break
            except (BrokenPipeError, OSError):
                pass
            finally:
                with contextlib.suppress(BrokenPipeError):
                    process.stdin.close()
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(process.pid, signal.SIGTERM)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=0.2)
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        return RpcResult(True, tuple(replies), errpath.read_text(errors="replace")[-4000:])


def host_paths(home: Path) -> dict[str, Path]:
    return {
        host: agent_settings.mcp_file(
            "cursor-agent" if host == "cursor" else host,
            home=home,
            platform_os="linux",
            environ=os.environ,
        )
        for host in (*HOSTS, "copilot", "claude")
    }


def entry_for(host: str, path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    fmt = "toml" if host == "codex" else "jsonc" if host in {"copilot", "opencode"} else "json"
    doc = agent_settings.parse_settings(path.read_text(encoding="utf-8"), fmt)
    keys = (
        ("mcp_servers", "playwright")
        if host == "codex"
        else ("mcp", "servers", "playwright")
        if host == "opencode"
        else ("mcpServers", "playwright")
    )
    value = agent_settings.lookup(doc, keys)
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def recorded() -> tuple[str, ...]:
    receipt = receipts.read(TOOL_ID)
    return receipt.hooks.get(HOOK, ()) if receipt else ()


def residue_paths(leftover: Sequence[str]) -> list[str]:
    """The leftovers that count as residue: standard empty directories and bun's own are not."""
    return [p for p in leftover if p not in STANDARD_EMPTY_DIRS and p not in BUN_EMPTY_DIRS]


def lifecycle() -> list[str]:
    home = Path.home()
    for marker in (".claude", ".codex", ".cursor", ".config/opencode", ".copilot"):
        (home / marker).mkdir(parents=True, exist_ok=True)
    paths = host_paths(home)
    seeds = {
        paths[
            "copilot"
        ]: '{"mcpServers":{"playwright":{"command":"user"},"other":{"command":"other"}}}\n',
        paths["cursor"]: '{"mcpServers":{"other":{"command":"other"}}}\n',
        home / ".claude/settings.json": '{"theme":"dark"}\n',
    }
    for path, text in seeds.items():
        path.write_text(text, encoding="utf-8")
    seed = {str(path): digest_path(path) for path in seeds}
    claude_paths = {"config": paths["claude"], "settings": home / ".claude/settings.json"}

    def claude_digests() -> dict[str, str]:
        return {name: digest_path(path) for name, path in claude_paths.items()}

    claude_seed = claude_digests()
    created = [path for path in paths.values() if not path.exists()]
    tool = tool_by_id(TOOL_ID)
    method = next(m for m in tool.methods if m.kind == "bun")
    install_one(tool_by_id("bun"), "TRACER_PLAYWRIGHT_INSTALL_FAILED")
    baseline = home_listing(home, Path.cwd())
    outcome = install_one(tool, "TRACER_PLAYWRIGHT_INSTALL_FAILED")
    globals_ = bun_globals.read_bun_globals()
    package = (globals_ or {}).get("@playwright/mcp")
    lines = [
        install_verdict(
            str(outcome.status).lower(),
            outcome.method_kind or "unknown",
            package.range if package else None,
        )
    ]
    lines.append(
        register_verdict(
            {h: entry_for(h, paths[h]) for h in HOSTS},
            seed[str(paths["copilot"])],
            digest_path(paths["copilot"]),
            claude_seed,
            claude_digests(),
            recorded(),
            outcome.postinstall_warning or "",
        )
    )
    _, warning = postinstall.register_hooks(
        tool, method, run_command, confirmed_hosts=frozenset({"cursor"})
    )
    late, late_hosts = claude_digests(), recorded()
    postinstall.register_hooks(tool, method, run_command, confirmed_hosts=frozenset({"claude"}))
    claude_entry = entry_for("claude", paths["claude"])
    settings = json.loads((home / ".claude/settings.json").read_text(encoding="utf-8"))
    lines.append(
        consent_verdict(
            claude_seed,
            late,
            late_hosts,
            warning or "",
            claude_entry,
            "dark",
            str(settings.get("theme")),
            recorded(),
        )
    )
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if chromium is None:
        lines.append(verdict("TRACER_PLAYWRIGHT_LAUNCH_UNPROVEN", "no Chromium in the box"))
    elif (
        claude_entry is None
        or not isinstance(claude_entry.get("command"), str)
        or not isinstance(claude_entry.get("args"), list)
    ):
        lines.append(verdict("TRACER_PLAYWRIGHT_LAUNCH_FAILED", "invalid registered command"))
    else:
        args = cast(list[object], claude_entry["args"])
        if not all(isinstance(arg, str) for arg in args):
            raise ValueError("invalid registered args")
        env = dict(os.environ)
        raw_env = claude_entry.get("env", {})
        if isinstance(raw_env, dict):
            env.update(
                {k: v for k, v in cast(dict[str, object], raw_env).items() if isinstance(v, str)}
            )
        env["PLAYWRIGHT_MCP_EXECUTABLE_PATH"] = chromium
        # The browser's own profile and crash reports are the smoke's side effect, not the
        # installer's residue: keep them out of HOME so the removal verdict measures only the tool.
        with tempfile.TemporaryDirectory(prefix="pw-browser-") as browser_config:
            env["XDG_CONFIG_HOME"] = browser_config
            lines.append(
                launch_verdict(
                    run_rpc(
                        [
                            cast(str, claude_entry["command"]),
                            *cast(list[str], args),
                            "--headless",
                            "--no-sandbox",
                        ],
                        env,
                        frames(),
                        RPC_SECONDS,
                    )
                )
            )
    result = uninstall_one(tool, run_command)
    sweep = "; ".join(f"{name}: {detail}" for name, detail in result.remove_failed)
    if TOOL_ID not in result.removed and not sweep:
        sweep = "tool not removed"
    globals_ = bun_globals.read_bun_globals()
    residue = residue_paths(
        leftovers(
            baseline,
            home_listing(home, Path.cwd()),
            allowed_prefixes(ALLOWLIST.read_text(encoding="utf-8")),
        )
    )
    lines.append(
        remove_verdict(
            sweep,
            [h for h in (*HOSTS, "claude") if entry_for(h, paths[h]) is not None],
            seed,
            {str(p): digest_path(p) for p in seeds},
            [str(p) for p in created if p.exists()],
            receipts.receipt_exists(TOOL_ID),
            globals_ is None or "@playwright/mcp" in globals_,
            residue,
        )
    )
    return lines


def accepts(args: Sequence[str]) -> bool:
    return len(args) == 1 and args[0] in _HANDLERS


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not accepts(args):
        print("usage: e2e_playwright_mcp_driver lifecycle", file=sys.stderr)
        return 2
    if not in_container():
        print("ERROR the playwright-mcp driver runs only inside the disposable container")
        return 2
    try:
        lines = _HANDLERS[args[0]]()
    except Failed as exc:
        print(verdict(exc.prefix, first_line(exc.detail)))
        return 1
    except (OSError, ValueError, CommandError, tomllib.TOMLDecodeError) as exc:
        print(f"ERROR {first_line(exc)}")
        return 1
    print("\n".join(lines))
    return int(any("_FAILED" in line or "_UNPROVEN" in line for line in lines))


_HANDLERS: dict[str, Callable[[], list[str]]] = {"lifecycle": lifecycle}

if __name__ == "__main__":
    raise SystemExit(main())
