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
        "apt-upgrade",
        "apt selective upgrade",
        "alias apt-upgrade — upgrade only packages that have updates (Linux)",
        _LINUX,
        _APT_BODY,
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
