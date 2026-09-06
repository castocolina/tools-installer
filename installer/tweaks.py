"""Curated, cross-shell tweak bundles written into ~/.myshellrc as marker blocks.

Mirrors installer.guards' ban exactly: each bundle is one idempotent,
marker-delimited block managed through shellrc.apply_block / strip_block. Bodies
are valid in both bash and zsh; wait_time uses printf so its escape
sequences behave the same across sh/bash/zsh. Bundles are curated in code (like
guards.BANNED), each surfaced as its own Policy via installer.policy.tweak_policy.
Every block lands in the same ~/.myshellrc the ban uses, so existing shell
sourcing covers it with no extra wiring.
"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from installer.platform import Platform
from installer.shellrc import apply_block, strip_block

_BIN_DIR_PLACEHOLDER = "__TOOLS_INSTALLER_BIN_DIR__"


@dataclass(frozen=True)
class ManagedExecutable:
    """A standalone helper copied from the package into the managed bin dir."""

    asset: str
    command: str
    sentinel: str


@dataclass(frozen=True)
class TweakBundle:
    """One curated shell snippet. `platforms` is the set of allowed Platform.os
    keys (empty = all); `body` is the snippet with no markers and no trailing
    newline (the block machinery adds them)."""

    id: str
    label: str
    description: str
    platforms: tuple[str, ...]
    body: str
    requires: tuple[str, ...] = ()
    executables: tuple[ManagedExecutable, ...] = ()


# Raw strings so backslash escapes survive verbatim into the shell file:
# the docker `\t` are Go-template tabs consumed by docker (not shell escapes),
# the sed `\.`/`\[` are regex escapes, and wait_time's `\033`/apt's `\n` must
# reach printf/tr literally.
_DOCKER_BODY = (
    "docker-ps() {\n"
    r"    watch -n 5 'docker ps --format "
    r'"table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
    r" | sed "
    r'"s/0\.0\.0\.0://g; s/\[::\]://g; s|/tcp||g; s|/udp||g"'
    "'\n"
    "}\n"
    r"alias docker-stats='docker stats --format "
    r'"table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"'
    "'\n"
    "alias docker-memory='docker-stats'"
)

_COUNTDOWN_BODY = (
    "wait_time() {\n"
    f'    uv run --no-project --script "{_BIN_DIR_PLACEHOLDER}/tools-installer-wait-time" "$@"\n'
    "}"
)

_CLAUDE_BODY = "alias claude='claude --dangerously-skip-permissions'"

# codex --help and codex exec --help both print this flag verbatim, confirmed
# live 2026-09-06 (10-RESEARCH.md Summary #1).
_CODEX_BODY = "alias codex='codex --dangerously-bypass-approvals-and-sandbox'"

# opencode --help's own text for --auto is "auto-approve permissions that are
# not explicitly denied (dangerous!)" — narrower than claude-skip/codex-skip's
# full bypass — confirmed live 2026-09-06 (10-RESEARCH.md Summary #2).
_OPENCODE_BODY = "alias opencode='opencode --auto'"

# The slug was live-confirmed via `cursor-agent models` on 2026-09-06
# (10-RESEARCH.md Summary #3); effort is baked into the slug itself (no
# separate --effort flag). Per CONTEXT.md D-01's "re-verify, don't override"
# instruction: Cursor's own CLI changelog (fetched live 2026-09-06, MEDIUM
# confidence per 10-RESEARCH.md's own confidence breakdown — an official doc,
# not an independently spent API call) documents a 2026-07-13 fix superseding
# REQUIREMENTS.md's prior "Max-Mode-only, unreachable non-interactively"
# finding, so headless --model selections requiring Max Mode now activate it
# automatically. This wrapper REQUESTS that model and never claims to
# independently verify the context window actually reached in any given
# response (10-RESEARCH.md Pitfall 4/Assumption A2) — copy in this project's
# UI must say "requests", never "guarantees" or "verifies".
_CURSOR_DEFAULT_MODEL = "gpt-5.6-sol-high"

# cursor-agent()'s own two calls to the real binary always go through
# `command cursor-agent "$@"` so the function can never recurse into itself
# (Pitfall 3). cursor() contains exactly one intentional BARE delegation to
# the cursor-agent shell FUNCTION (a different name, not itself), which is
# how it inherits the same argv-scan/injection logic. Both functions are
# preceded by `unalias cursor-agent cursor 2>/dev/null || true` so a
# pre-existing same-named alias never collides with the function definitions
# that follow — live-verified on this machine (bash 3.2.57(1)-release, zsh
# 5.9.2): a bare `name() { ... }` definition against an already-active
# same-named alias is a hard syntax error in bash 3.2 and behaves
# inconsistently in zsh 5.9 across interactive/non-interactive contexts;
# `unalias` first makes the outcome identical and correct in every
# shell/context combination. The trailing `|| true` (dual-lane review
# WR-01/codex-sol-high) is required, not cosmetic: `unalias` exits nonzero
# when neither name is currently an alias -- the common case -- and
# `2>/dev/null` alone only silences the message, not the exit status; under
# `set -e`/`setopt err_exit` that nonzero status would abort the rest of
# `~/.myshellrc` with zero diagnostic output. `local a` (dual-lane review
# WR-02) prevents the loop variable from leaking into the calling
# interactive shell's global namespace. The loop breaks at a literal `--`
# token (dual-lane review, codex-sol-high) since cursor-agent's own
# commander.js-based parser treats everything after `--` as positional
# prompt text, never as flags -- live-verified that `cursor-agent --model
# ... update`/`--version` both tolerate the injected --model ahead of a
# subcommand (exit 0, correct behavior), so no subcommand allowlist is
# needed; the sole real gap was the unbounded `--` boundary.
_CURSOR_AGENT_BODY = (
    "unalias cursor-agent cursor 2>/dev/null || true\n"
    "function cursor-agent {\n"
    "    local a\n"
    '    for a in "$@"; do\n'
    '        case "$a" in\n'
    "            --)\n"
    "                break\n"
    "                ;;\n"
    "            --model|--model=*)\n"
    '                command cursor-agent "$@"\n'
    "                return $?\n"
    "                ;;\n"
    "        esac\n"
    "    done\n"
    f'    command cursor-agent --model {_CURSOR_DEFAULT_MODEL} "$@"\n'
    "}\n"
    "function cursor {\n"
    '    cursor-agent "$@"\n'
    "}"
)

_APT_BODY = (
    "alias apt-upgrade="
    r"'sudo apt install --only-upgrade"
    r" $(apt list --upgradeable 2>/dev/null"
    r' | grep -v "Listing" | cut -d/ -f1 | tr "\n" " ")'
    "'"
)

# apt-upgrade is gated to Linux (offered on Linux, absent on macOS) per the PRD;
# the alias only errors if actually run on a non-apt distro.
_LINUX = ("debian", "arch", "fedora")

BUNDLES: tuple[TweakBundle, ...] = (
    TweakBundle(
        "docker",
        "Docker shortcuts",
        "docker-ps (live table), docker-stats, docker-memory (needs `watch`)",
        (),
        _DOCKER_BODY,
        requires=("watch",),
    ),
    TweakBundle(
        "countdown",
        "Countdown helper",
        "wait_time <duration|target> - uv-run Python countdown for seconds, "
        "1d10m15s, or a clock time",
        (),
        _COUNTDOWN_BODY,
        requires=("uv",),
        executables=(
            ManagedExecutable(
                asset="helper_assets/wait_time.py",
                command="tools-installer-wait-time",
                sentinel="tools-installer-helper: wait_time",
            ),
        ),
    ),
    TweakBundle(
        "claude-skip",
        "claude skip-permissions",
        "alias claude='claude --dangerously-skip-permissions'",
        (),
        _CLAUDE_BODY,
    ),
    TweakBundle(
        "codex-skip",
        "codex skip-permissions",
        "alias codex='codex --dangerously-bypass-approvals-and-sandbox'",
        (),
        _CODEX_BODY,
    ),
    TweakBundle(
        "apt-upgrade",
        "apt selective upgrade",
        "alias apt-upgrade — upgrade only packages that have updates (Linux)",
        _LINUX,
        _APT_BODY,
    ),
    TweakBundle(
        "opencode-auto",
        "opencode auto-approve",
        "alias opencode='opencode --auto' — auto-approves permissions not explicitly"
        " denied; not a full bypass",
        (),
        _OPENCODE_BODY,
    ),
    TweakBundle(
        "cursor-agent-model",
        "cursor-agent default model",
        f"injects --model {_CURSOR_DEFAULT_MODEL} into a bare cursor-agent/cursor call;"
        " skipped whenever --model is already present",
        (),
        _CURSOR_AGENT_BODY,
    ),
)


def _markers(bundle_id: str) -> tuple[str, str]:
    return (
        f"# >>> tools-installer tweak:{bundle_id} >>>",
        f"# <<< tools-installer tweak:{bundle_id} <<<",
    )


def _default_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def _render_body(bundle: TweakBundle, bin_dir: Path | None) -> str:
    return bundle.body.replace(_BIN_DIR_PLACEHOLDER, str(bin_dir or _default_bin_dir()))


def _is_our_executable(path: Path, sentinel: str) -> bool:
    try:
        return sentinel in path.read_text()
    except (OSError, UnicodeDecodeError):
        return False


def install_tweak_executables(bundle: TweakBundle, bin_dir: Path) -> tuple[Path, ...]:
    """Copy bundle helper executables into the managed bin dir."""
    if not bundle.executables:
        return ()
    bin_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    package_files = resources.files("installer")
    for executable in bundle.executables:
        target = bin_dir / executable.command
        if target.exists() and not _is_our_executable(target, executable.sentinel):
            raise OSError(f"{target} exists and is not managed by tools-installer")
        source = package_files.joinpath(executable.asset).read_text()
        target.write_text(source)
        target.chmod(0o755)
        written.append(target)
    return tuple(written)


def remove_tweak_executables(bundle: TweakBundle, bin_dir: Path) -> tuple[Path, ...]:
    """Remove only helper executables owned by this bundle."""
    removed: list[Path] = []
    for executable in bundle.executables:
        target = bin_dir / executable.command
        if target.exists() and _is_our_executable(target, executable.sentinel):
            target.unlink()
            removed.append(target)
    return tuple(removed)


def tweak_executables_present(bundle: TweakBundle, bin_dir: Path) -> bool:
    """True when any helper this bundle owns is on disk in bin_dir.

    Answers, for a helper, the same question tweak_present answers for the rc
    block: is this bundle's footprint on this machine. Ownership is
    sentinel-checked on purpose, so this can never promise to remove a
    same-named file that remove_tweak_executables would correctly refuse to
    delete. A bundle with no executables is always False.
    """
    for executable in bundle.executables:
        target = bin_dir / executable.command
        if target.exists() and _is_our_executable(target, executable.sentinel):
            return True
    return False


def tweak_block(bundle: TweakBundle, bin_dir: Path | None = None) -> str:
    """Marker-delimited block (no trailing newline, like shellrc/guards blocks)."""
    begin, end = _markers(bundle.id)
    return f"{begin}\n{_render_body(bundle, bin_dir)}\n{end}"


def write_tweak(bundle: TweakBundle, rc_path: Path, bin_dir: Path | None = None) -> None:
    """Idempotently write the bundle's block into rc_path, preserving the rest."""
    begin, end = _markers(bundle.id)
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, tweak_block(bundle, bin_dir), begin=begin, end=end))


def remove_tweak(bundle: TweakBundle, rc_path: Path) -> None:
    """Strip the bundle's block. A missing file or absent block is a no-op."""
    if not rc_path.exists():
        return
    begin, end = _markers(bundle.id)
    original = rc_path.read_text()
    stripped = strip_block(original, begin, end)
    if stripped != original:
        rc_path.write_text(stripped)


def tweak_present(bundle: TweakBundle, rc_path: Path) -> bool:
    """True when rc_path exists and carries the bundle's begin marker."""
    if not rc_path.exists():
        return False
    begin, _ = _markers(bundle.id)
    return begin in rc_path.read_text().split("\n")


def applicable_bundles(platform: Platform) -> tuple[TweakBundle, ...]:
    """Bundles offered on this platform (empty `platforms` = every platform)."""
    return tuple(b for b in BUNDLES if not b.platforms or platform.os in b.platforms)
