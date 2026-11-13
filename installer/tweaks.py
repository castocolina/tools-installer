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

from installer.atomic import atomic_write_text, read_capped
from installer.locations import display_path, path_scan_rc_paths
from installer.platform import Platform
from installer.sanitize import sanitize_log_line
from installer.shellrc import apply_block, find_export, read_record, strip_block

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
    # Variables the user's own shell files may already export; the bundle is not written then.
    yields_to: tuple[str, ...] = ()


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

# Shell init (D-11): one bundle per tool, id = tool id, offered at install and
# default off. The `if command -v` guard picks the zsh or the bash line, which a
# bare one-line eval cannot do. No registry string reaches these bodies.
SHELL_INIT_TOOLS = ("starship", "direnv", "zoxide", "fzf", "fnm", "volta", "neovim")


def _guarded_init(tool: str, zsh_line: str, bash_line: str) -> str:
    return (
        f"if command -v {tool} >/dev/null; then\n"
        f'  if [ -n "$ZSH_VERSION" ]; then {zsh_line}\n'
        f'  elif [ -n "$BASH_VERSION" ]; then {bash_line}; fi\n'
        "fi"
    )


# Exports VOLTA_HOME only: a PATH prepend here would trip the repo's PATH-accumulation
# invariant. ~/.volta/bin reaches PATH through the managed PATH block (volta's registry
# bin_dir). shortcut: a custom VOLTA_HOME outside ~/.volta is not supported, upgrade by
# giving the managed PATH block the custom bin dir.
_VOLTA_BODY = (
    'if command -v volta >/dev/null; then\n  export VOLTA_HOME="${VOLTA_HOME:-$HOME/.volta}"\nfi'
)


# The `if` form, not `command -v nvim && export ...`, whose non-zero status would be the last
# command of the sourced block when nvim is absent.
_NVIM_EDITOR_BODY = "if command -v nvim >/dev/null; then\n  export EDITOR=nvim VISUAL=nvim\nfi"


def _shell_init(
    tool: str, description: str, body: str, *, yields_to: tuple[str, ...] = ()
) -> TweakBundle:
    return TweakBundle(
        tool, f"{tool} shell init", description, (), body, requires=(tool,), yields_to=yields_to
    )


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
        "apt-upgrade",
        "apt selective upgrade",
        "alias apt-upgrade — upgrade only packages that have updates (Linux)",
        _LINUX,
        _APT_BODY,
    ),
    _shell_init(
        "starship",
        'makes starship draw your prompt and sets ZSH_THEME="" so Oh-My-Zsh draws none',
        _guarded_init("starship", 'eval "$(starship init zsh)"', 'eval "$(starship init bash)"'),
    ),
    _shell_init(
        "direnv",
        "loads and unloads a directory's .envrc as you cd",
        _guarded_init("direnv", 'eval "$(direnv hook zsh)"', 'eval "$(direnv hook bash)"'),
    ),
    _shell_init(
        "zoxide",
        "adds z, a cd that learns the directories you use",
        _guarded_init("zoxide", 'eval "$(zoxide init zsh)"', 'eval "$(zoxide init bash)"'),
    ),
    _shell_init(
        "fzf",
        "adds ctrl+r history search, ctrl+t file picker and alt+c",
        _guarded_init("fzf", "source <(fzf --zsh)", 'eval "$(fzf --bash)"'),
    ),
    _shell_init(
        "fnm",
        "switches Node versions from .node-version or .nvmrc as you cd",
        _guarded_init(
            "fnm",
            'eval "$(fnm env --use-on-cd --shell zsh)"',
            'eval "$(fnm env --use-on-cd --shell bash)"',
        ),
    ),
    _shell_init(
        "volta",
        "exports VOLTA_HOME; its bin directory is on PATH via the PATH block",
        _VOLTA_BODY,
    ),
    _shell_init(
        "neovim",
        "sets EDITOR and VISUAL to nvim when your shell files set neither",
        _NVIM_EDITOR_BODY,
        yields_to=("EDITOR", "VISUAL"),
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
        atomic_write_text(target, source, mode=0o755)
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
    atomic_write_text(
        rc_path, apply_block(existing, tweak_block(bundle, bin_dir), begin=begin, end=end)
    )


def strip_tweak_block(bundle_id: str, rc_path: Path) -> bool:
    """Strip the block of bundle_id from rc_path. True when the file changed."""
    if not rc_path.exists():
        return False
    begin, end = _markers(bundle_id)
    original = rc_path.read_text()
    stripped = strip_block(original, begin, end)
    if stripped == original:
        return False
    atomic_write_text(rc_path, stripped)
    return True


def remove_tweak(bundle: TweakBundle, rc_path: Path) -> None:
    """Strip the bundle's block. A missing file or absent block is a no-op."""
    strip_tweak_block(bundle.id, rc_path)


# The retired alias bundles: no longer offered, only stripped from ~/.myshellrc. The value is
# the agent whose install writes the auto-approve key the launch notice names (None: cursor's).
LEGACY_ALIAS_BUNDLES: dict[str, str | None] = {
    "claude-skip": "claude",
    "codex-skip": "codex",
    "opencode-auto": "opencode",
    "cursor-agent-model": None,
}


@dataclass(frozen=True)
class LegacyStrip:
    """What strip_legacy_aliases removed from one rc file, for the launch and uninstall copy."""

    rc: str
    stripped: tuple[str, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    unreadable: str | None = None

    def launch_lines(self) -> tuple[tuple[str, str], ...]:
        # Imported here: agent_settings reaches this module through receipts and omz.
        from installer.agent_settings import setting_keys

        lines: list[tuple[str, str]] = []
        for alias_id in self.stripped:
            agent = LEGACY_ALIAS_BUNDLES[alias_id]
            if agent is None:
                text = f"{alias_id} alias removed: pick the model with /model in cursor-agent."
                lines.append((text, "warn"))
            else:
                key = ".".join(setting_keys(agent, "auto-approve", "linux")[0].path)
                text = (
                    f"Removed the {alias_id} alias; installing {agent} writes {key} "
                    "in its settings instead."
                )
                lines.append((text, "ok"))
        lines.extend((text, "warn") for text in self.failure_lines())
        return tuple(lines)

    def failure_lines(self) -> tuple[str, ...]:
        unreadable = (
            ()
            if self.unreadable is None
            else (
                f"Could not check {self.rc} for legacy alias blocks: {self.unreadable}; "
                "nothing was changed.",
            )
        )
        return unreadable + tuple(
            f"Could not remove the {alias_id} alias from {self.rc}: {reason}."
            for alias_id, reason in self.failed
        )

    def uninstall_line(self) -> str | None:
        if not self.stripped:
            return None
        return f"Removed the {', '.join(self.stripped)} alias block(s) from {self.rc}."


_RC_MAX_BYTES = 1 << 20


def strip_legacy_aliases(rc_path: Path) -> LegacyStrip:
    """Strip every legacy alias block from rc_path. Idempotent; no agent file is touched. It runs
    at every launch, so a file it cannot read is reported and never raised (CR-04)."""
    rc = display_path(rc_path)
    try:
        data = read_capped(rc_path, _RC_MAX_BYTES, follow_symlinks=True)
        if data is None:
            return LegacyStrip(rc=rc, unreadable="not a regular file of at most 1 MiB")
        lines = data.decode("utf-8").split("\n")
    except FileNotFoundError:
        return LegacyStrip(rc=rc)
    except UnicodeDecodeError:
        return LegacyStrip(rc=rc, unreadable="not valid UTF-8")
    except OSError as exc:
        return LegacyStrip(rc=rc, unreadable=exc.strerror or str(exc))
    stripped: list[str] = []
    failed: list[tuple[str, str]] = []
    for alias_id in LEGACY_ALIAS_BUNDLES:
        if _markers(alias_id)[0] not in lines:
            continue
        try:
            if strip_tweak_block(alias_id, rc_path):
                stripped.append(alias_id)
        except (OSError, ValueError) as exc:
            failed.append((alias_id, (str(exc).splitlines() or [""])[0]))
    return LegacyStrip(rc=rc, stripped=tuple(stripped), failed=tuple(failed))


def bundle_marker_present(bundle_id: str, rc_path: Path) -> bool:
    """True when rc_path exists and carries the begin marker of the bundle's block."""
    begin, _ = _markers(bundle_id)
    # Read at launch for every bundle row: an undecodable byte, a directory, a FIFO or an
    # oversize file never raises or blocks (non-blocking capped read, like the alias strip).
    try:
        data = read_capped(rc_path, _RC_MAX_BYTES, follow_symlinks=True)
    except OSError:
        return False
    return data is not None and begin in data.decode("utf-8", errors="replace").split("\n")


# The written-once record of shell init (23.2 D-08): a comment-only closed block in the managed
# rc file listing the tool ids the install tuning wrote. A block present without a record is a
# pre-23.2 Policies block, not pending.
SHELL_INIT_RECORD_BEGIN = "# >>> tools-installer shell-init >>>"
SHELL_INIT_RECORD_END = "# <<< tools-installer shell-init <<<"
_SHELL_INIT_WRITTEN = "# written:"


def shell_init_record(rc_path: Path) -> tuple[str, ...] | None:
    """The tool ids whose shell init the installer wrote; None when it never recorded any."""
    return read_record(rc_path, SHELL_INIT_RECORD_BEGIN, SHELL_INIT_RECORD_END, _SHELL_INIT_WRITTEN)


def _store_shell_init_record(rc_path: Path, ids: tuple[str, ...]) -> None:
    try:
        existing = rc_path.read_text() if rc_path.exists() else ""
    except UnicodeDecodeError as exc:  # never rewrite bytes that cannot round-trip
        raise OSError(f"{rc_path} is not valid UTF-8; shell-init record not updated") from exc
    if ids:
        body = (
            "# Shell init this installer wrote once. A block you delete is not written again.",
            "# Comments only: nothing here is executed.",
            f"{_SHELL_INIT_WRITTEN} {' '.join(ids)}",
        )
        block = "\n".join((SHELL_INIT_RECORD_BEGIN, *body, SHELL_INIT_RECORD_END))
        updated = apply_block(existing, block, SHELL_INIT_RECORD_BEGIN, SHELL_INIT_RECORD_END)
    else:
        updated = strip_block(existing, SHELL_INIT_RECORD_BEGIN, SHELL_INIT_RECORD_END)
    if updated != existing:
        atomic_write_text(rc_path, updated)


def record_shell_init(rc_path: Path, tool_id: str) -> None:
    """Record that the installer wrote this tool's shell init; once per id, in write order."""
    ids = shell_init_record(rc_path) or ()
    if tool_id not in ids:
        _store_shell_init_record(rc_path, (*ids, tool_id))


def forget_shell_init(rc_path: Path, tool_id: str) -> None:
    """Drop one id from the record (its block is gone); the block goes with the last id."""
    ids = shell_init_record(rc_path)
    if ids is not None and tool_id in ids:
        _store_shell_init_record(rc_path, tuple(i for i in ids if i != tool_id))


def clear_shell_init_record(rc_path: Path) -> None:
    """Strip the whole record block, as the full uninstall does."""
    _store_shell_init_record(rc_path, ())


def tweak_present(bundle: TweakBundle, rc_path: Path) -> bool:
    """True when rc_path exists and carries the bundle's begin marker."""
    return bundle_marker_present(bundle.id, rc_path)


def applicable_bundles(platform: Platform) -> tuple[TweakBundle, ...]:
    """Bundles offered on this platform (empty `platforms` = every platform)."""
    return tuple(b for b in BUNDLES if not b.platforms or platform.os in b.platforms)


def user_export(names: tuple[str, ...], tool_id: str) -> str | None:
    """Read-only: why `tool_id`'s bundle is not written (the user exports one of `names`, or a
    startup file cannot be read), or None when it may be written. Never reads the environment."""
    if not names:
        return None
    # zsh reads ~/.zshenv first even when ZDOTDIR points elsewhere.
    paths = [*path_scan_rc_paths(), Path.home() / ".zshenv"]
    # shortcut: ~/.config/environment.d and launchd exports are not scanned (shell files only);
    # upgrade by adding them to the scan set.
    for path in dict.fromkeys(paths):
        try:
            data = read_capped(path, _RC_MAX_BYTES, follow_symlinks=True)
            reason = "larger than 1 MiB" if data is None and path.is_file() else ""
        except FileNotFoundError:
            continue
        except OSError as exc:
            data, reason = None, exc.strerror or str(exc)
        if data is None:
            if not reason:  # a directory or a FIFO is not a startup file
                continue
            return sanitize_log_line(
                f"Could not read {display_path(path)} ({reason}), "
                f"so the {tool_id} shell init was not written."
            )
        found = find_export(data.decode("utf-8", errors="replace"), names)
        if found is not None:
            name, value = found
            return (
                f"Kept your {name}={sanitize_log_line(value)} "
                f"(the {tool_id} shell init was not written)."
            )
    return None


def shell_init_bundle(tool_id: str) -> TweakBundle | None:
    """The shell-init bundle of a tool, or None when the tool has none."""
    return next((b for b in BUNDLES if b.id == tool_id and tool_id in SHELL_INIT_TOOLS), None)
