"""Userspace install-location policy: binaries land under ~/.local/bin, no sudo."""

import os
from collections.abc import Mapping
from pathlib import Path


def zshrc_path(home: Path, environ: Mapping[str, str]) -> Path:
    """The .zshrc zsh actually reads: $ZDOTDIR/.zshrc when ZDOTDIR names an
    existing directory, else ~/.zshrc.

    Mirrors omz.omz_present's $ZSH-awareness. The two must agree: a ZDOTDIR
    setup where the detection predicate reads the environment but the write
    target does not is one that enables the Oh-My-Zsh policy and then edits a
    file zsh never sources. The is_dir() guard keeps a stale or typo'd ZDOTDIR
    from pointing writes at a directory that does not exist.
    """
    zdotdir = environ.get("ZDOTDIR")
    if zdotdir and Path(zdotdir).is_dir():
        return Path(zdotdir) / ".zshrc"
    return home / ".zshrc"


def _zshrc() -> Path:
    return zshrc_path(Path.home(), os.environ)


def xdg_config_base(home: Path, environ: Mapping[str, str]) -> Path:
    """The XDG user config base: $XDG_CONFIG_HOME when it is ABSOLUTE, else
    ``home/.config``.

    The ONE place this rule lives (lane-2 MEDIUM-01). Both
    ``systemd_daemon.user_unit_dir`` ($XDG_CONFIG_HOME/systemd/user) and
    ``env_redirect.environment_d_dir`` ($XDG_CONFIG_HOME/environment.d) used
    to carry their own copy of it, so a change to the rule could land in one
    and miss the other. Each still owns its own sub-path -- only the base is
    shared -- and this module is where path resolution already lives.

    A RELATIVE (or empty) value is IGNORED rather than honoured: the XDG
    base-directory spec says a non-absolute value must be ignored, and
    honouring one would resolve every derived path against whatever cwd the
    process happens to have (review LOW 15.7-01 / 15.7-04).
    """
    raw = environ.get("XDG_CONFIG_HOME", "")
    return Path(raw) if raw and Path(raw).is_absolute() else home / ".config"


def bin_dir(declared: str | None) -> Path:
    """Resolve a method's bin dir. Defaults to ~/.local/bin; expands a leading ~."""
    if declared:
        return Path(declared).expanduser()
    return Path.home() / ".local" / "bin"


def opt_dir(name: str) -> Path:
    """Resolve the userspace opt dir for an unpacked app: ~/.local/opt/<name>."""
    return Path.home() / ".local" / "opt" / name


def applications_dir() -> Path:
    """The userspace Applications dir for macOS GUI apps: ~/Applications."""
    return Path.home() / "Applications"


def rc_paths_for_mode(link_mode: str, shell: str) -> list[Path]:
    """The shell rc files PATH wiring writes to under `link_mode`. Centralized
    and split wire both defaults; single wires only the rc of `shell` — both
    when the shell is undetectable."""
    home = Path.home()
    both = [_zshrc(), home / ".bashrc"]
    if link_mode != "single":
        return both
    if shell.endswith("zsh"):
        return [_zshrc()]
    if shell.endswith("bash"):
        return [home / ".bashrc"]
    return both  # undetectable shell -> wire both


def ban_rc_paths(link_mode: str, shell: str) -> list[Path]:
    """Where to WRITE ban aliases, following the PATH model: centralized/single
    keep one ~/.myshellrc; split writes into each rc file directly."""
    if link_mode == "split":
        return rc_paths_for_mode(link_mode, shell)
    return [Path.home() / ".myshellrc"]


def all_ban_rc_paths() -> list[Path]:
    """Where to REMOVE aliases from: every file an install could have written to,
    across all link modes. remove_ban_aliases is a no-op where the block is
    absent, so removal needs no link-mode guess (which would otherwise strand
    aliases when the user picks a different mode than they installed with)."""
    home = Path.home()
    return [home / ".myshellrc", _zshrc(), home / ".bashrc"]


def ensure_dir(directory: Path) -> Path:
    """Create the directory (and parents) if missing. Returns it."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def prepend_path(directory: Path) -> None:
    """Put `directory` first on the process PATH, without duplicating it."""
    entry = str(directory)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    parts = [p for p in parts if p and p != entry]
    os.environ["PATH"] = os.pathsep.join([entry, *parts])


def path_scan_rc_paths() -> list[Path]:
    """Every startup file a login or interactive shell may read that could add
    to PATH. READ-ONLY: this is the diagnostic set the Doctor scans to explain a
    duplicate PATH entry, never a write target.

    It is deliberately WIDER than `all_ban_rc_paths` (the write set). Two of the
    most common duplicate sources are login files this installer never writes:
    a plain prepend in `~/.bash_profile` plus the stock Fedora `~/.bashrc`
    snippet yields exactly the structural 2x that no new terminal clears. A
    scan limited to our own write targets would find neither and would leave
    the user with a finding and no explanation. Fedora's stock .bashrc sources
    ~/.bashrc.d/*, and zsh also reads .zshenv, .zprofile and .zlogin from the
    same directory as .zshrc.
    """
    home = Path.home()
    zdir = zshrc_path(home, os.environ).parent
    bashrc_d = home / ".bashrc.d"

    def _is_file(path: Path) -> bool:
        try:
            return path.is_file()
        except OSError:
            return False

    snippets = sorted(p for p in bashrc_d.glob("*") if _is_file(p)) if bashrc_d.is_dir() else []
    return [
        home / ".myshellrc",
        home / ".shellrc",
        zdir / ".zshrc",
        zdir / ".zprofile",
        zdir / ".zshenv",
        zdir / ".zlogin",
        home / ".bashrc",
        *snippets,
        home / ".bash_profile",
        home / ".profile",
    ]
