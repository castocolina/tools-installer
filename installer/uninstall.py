"""Registry-driven uninstall: remove the userspace artifacts install_download
and install_app create, and — for a full uninstall — perform the symmetric
teardown of every still-enabled shell tweak, reusing the same policy remove
path the Policies view uses (CONTEXT D-04). Cask/brew/native-managed artifacts
are left alone."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from installer.apps import APP_KINDS, cli_spec
from installer.download import DOWNLOAD_KINDS
from installer.enums import UninstallState
from installer.executors import ExecutorError
from installer.locations import applications_dir, opt_dir
from installer.model import Method, Tool
from installer.platform import Platform
from installer.policy import Policy, omz_plugins_policy, tweak_policy
from installer.resolve import resolve_methods
from installer.tweaks import TweakBundle, tweak_executables_present, tweak_present

# No import cycle: installer.policy imports guards, tweaks and omz, none of
# which import uninstall.


def _exists(path: Path) -> bool:
    # is_symlink catches dangling links (exists() is False when the target is gone).
    return path.exists() or path.is_symlink()


def _plan_app(method: Method, default_bin_dir: Path, add: Callable[[Path], None]) -> None:
    """Plan the ~/Applications bundle and the cli symlink an app method created.

    Only the userspace bundle is planned — a copy in /Applications was never
    ours to manage. The cli symlink name comes from the same validator the
    installer uses (apps.cli_spec), so an invalid cli that install_app would
    have rejected — and therefore never symlinked — plans nothing.
    """
    app = method.params.get("app")
    if not isinstance(app, str) or not app:
        return
    if PurePosixPath(app).name != app or app in (".", ".."):
        return
    add(applications_dir() / app)
    try:
        spec = cli_spec(method)
    except ExecutorError:
        return
    if spec is None:
        return
    add(default_bin_dir / spec[1])


def plan_uninstall(tools: list[Tool], default_bin_dir: Path) -> list[Path]:
    """Existing artifacts the download/raw/app executors would have created.

    The registry is the manifest: every download/raw method maps to opt_dir(binname)
    and <bin_dir>/binname, where binname is the basename of the method's member;
    every app method maps to ~/Applications/<app> and <bin_dir>/<cli basename>.
    Only paths that currently exist (including dangling symlinks) are returned, in a
    stable de-duplicated order.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        if path not in seen and _exists(path):
            seen.add(path)
            found.append(path)

    for tool in tools:
        for method in tool.methods:
            if method.kind in APP_KINDS:
                _plan_app(method, default_bin_dir, add)
                continue
            if method.kind not in DOWNLOAD_KINDS:
                continue
            member = method.params.get("member")
            if not isinstance(member, str) or not member:
                continue
            binname = PurePosixPath(member).name
            if binname in ("", ".", ".."):
                # Defensive: a traversal/empty basename would resolve opt_dir/bin
                # paths up to ~/.local and risk deleting far more than one tool.
                # Members come from the trusted registry, but this code deletes files.
                continue
            declared = method.params.get("bin_dir")
            base = (
                Path(declared).expanduser()
                if isinstance(declared, str) and declared
                else default_bin_dir
            )
            add(opt_dir(binname))
            add(base / binname)
    return found


@dataclass(frozen=True, init=False)
class ToolRow:
    """A tool annotated with its removability on this machine + platform.

    States: removable (userspace artifacts on disk -> selectable, has paths),
    managed (installed but no userspace artifacts -> inert, manager hint),
    absent (resolvable here but not installed -> inert), unavailable (no method
    applies to this platform -> inert)."""

    tool: Tool
    state: UninstallState
    paths: list[Path]
    hint: str
    selectable: bool

    def __init__(
        self,
        tool: Tool,
        state: UninstallState | str,
        paths: list[Path],
        hint: str,
        selectable: bool,
    ) -> None:
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "state", UninstallState(state))
        object.__setattr__(self, "paths", paths)
        object.__setattr__(self, "hint", hint)
        object.__setattr__(self, "selectable", selectable)


def _manager_name(method: Method, param: str, fallback: str) -> str:
    # brew/cask uninstall takes the formula/cask name (in the method params),
    # NOT the runnable cmd — they differ for e.g. rg/ripgrep, code/visual-studio-code.
    value = method.params.get(param)
    return value if isinstance(value, str) and value else fallback


def _manager_hint(tool: Tool) -> str:
    for method in tool.methods:
        if method.kind == "cask":
            name = _manager_name(method, "cask", tool.cmd)
            return f"managed by Homebrew — `brew uninstall --cask {name}`"
        if method.kind == "brew":
            name = _manager_name(method, "formula", tool.cmd)
            return f"managed by Homebrew — `brew uninstall {name}`"
    return "managed outside this installer — remove with your package manager"


def _managed_hint(tool: Tool, which: Callable[[str], str | None]) -> str:
    # Surface where the tool actually resolves on PATH (e.g. /opt/homebrew/bin/rg)
    # so "managed elsewhere" is concrete: the user sees it is a real, brew/system
    # install this installer did not place and should not delete.
    hint = _manager_hint(tool)
    path = which(tool.cmd)
    return f"{hint} — found at {path}" if path else hint


def reverse_dependencies(tools: list[Tool]) -> dict[str, list[str]]:
    """Map each tool id to the ids of tools that declare it in ``requires``.

    Used by the Uninstall view to warn (but allow) when removing a tool others
    depend on — never a cascade or a block. Ids with no dependents are omitted."""
    rev: dict[str, list[str]] = {}
    for tool in tools:
        for dep_id in tool.requires:
            rev.setdefault(dep_id, []).append(tool.id)
    return rev


def classify_tools(
    tools: list[Tool],
    default_bin_dir: Path,
    *,
    installed: dict[str, bool],
    platform: Platform,
    which: Callable[[str], str | None] = shutil.which,
    reverse_deps: dict[str, list[str]] | None = None,
) -> list[ToolRow]:
    """Classify every tool by removability, one ToolRow per tool in input order.

    Reuses plan_uninstall (userspace artifacts), the installed map, the platform
    resolver, and `which` (to resolve where a managed tool lives) so the Uninstall
    view shows full catalog parity: removable-here vs managed-elsewhere vs
    not-installed vs unavailable.

    When ``reverse_deps`` is provided, any tool that other tools depend on gets a
    "required by …" note appended to its hint — warn-but-allow, no cascade or
    block."""
    rows: list[ToolRow] = []
    for tool in tools:
        paths = plan_uninstall([tool], default_bin_dir)
        if paths:
            rows.append(
                ToolRow(
                    tool,
                    UninstallState.REMOVABLE,
                    paths,
                    "installed in userspace — removable here",
                    True,
                )
            )
        elif installed.get(tool.id, False):
            rows.append(
                ToolRow(tool, UninstallState.MANAGED, [], _managed_hint(tool, which), False)
            )
        elif resolve_methods(tool, platform):
            rows.append(ToolRow(tool, UninstallState.ABSENT, [], "not installed", False))
        else:
            rows.append(
                ToolRow(
                    tool, UninstallState.UNAVAILABLE, [], f"not available on {platform.os}", False
                )
            )
    if reverse_deps:
        rows = [
            replace(
                row,
                hint=f"{row.hint} · required by {', '.join(reverse_deps[row.tool.id])}",
            )
            if reverse_deps.get(row.tool.id)
            else row
            for row in rows
        ]
    return rows


def remove_paths(paths: list[Path]) -> None:
    """Delete each path: a symlink is unlinked (target preserved), a dir is removed
    recursively, a file is unlinked."""
    for path in paths:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _omz_policy(zshrc_path: Path) -> Policy:
    # Per CONTEXT D-04/D-05/D-06: present drives missing_requires, which gates
    # ENABLING the tweak (D-05/D-06); a teardown must never be gated on it,
    # because a machine being uninstalled may have had oh-my-zsh removed already
    # and refusing to undo our own .zshrc edit would strand exactly the stray
    # state this module exists to remove (D-04's symmetric teardown). Removal is
    # total regardless -- omz.remove_plugins no-ops on a missing file or missing
    # array -- so present=True can never raise here.
    return omz_plugins_policy(zshrc_path=zshrc_path, present=True)


def active_tweak_ids(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
) -> tuple[str, ...]:
    """Ids of tweaks still present on this machine.

    A tweak is active when its rc block is present OR an owned helper
    executable is on disk. The block alone misses a helper left behind after a
    hand-edited rc file (the REQ's literal orphaned-executable case), and the
    helper alone misses every bundle that has none. This is a read-only
    predicate: it opens files but writes none.

    The None default on zshrc_path exists for unit tests and any caller working
    only with bundles; production callers MUST pass the real path, because
    omitting it silently narrows the sweep to bundles and leaves the Oh-My-Zsh
    plugins=(...) edit on the machine with nothing reporting it.
    """
    ids: list[str] = []
    for bundle in bundles:
        if tweak_present(bundle, rc_path) or tweak_executables_present(bundle, bin_dir):
            ids.append(bundle.id)
    if zshrc_path is not None:
        policy = _omz_policy(zshrc_path)
        if policy.active:
            ids.append(policy.id)
    return tuple(ids)


def sweep_tweaks(
    bundles: tuple[TweakBundle, ...],
    *,
    rc_path: Path,
    bin_dir: Path,
    zshrc_path: Path | None = None,
) -> tuple[str, ...]:
    """Disable every tweak active_tweak_ids reports, via Policy.remove.

    This is D-04's symmetric teardown: it writes no removal logic of its own,
    it calls the exact same Policy.remove closures the Policies view calls when
    the user toggles a tweak off, so "full uninstall" and "toggle off" are the
    same operation by construction. Because it reads active_tweak_ids rather
    than re-deriving, the preview a caller printed and the effect this
    performs cannot diverge. Idempotent: a second call finds nothing active
    and returns an empty tuple.

    The None default on zshrc_path exists for unit tests and any caller working
    only with bundles; production callers MUST pass the real path, because
    omitting it silently narrows the sweep to bundles and leaves the Oh-My-Zsh
    plugins=(...) edit on the machine with nothing reporting it.
    """
    ids = active_tweak_ids(bundles, rc_path=rc_path, bin_dir=bin_dir, zshrc_path=zshrc_path)
    active = set(ids)
    for bundle in bundles:
        if bundle.id in active:
            tweak_policy(bundle, rc_path=rc_path, bin_dir=bin_dir).remove()
    if zshrc_path is not None:
        policy = _omz_policy(zshrc_path)
        if policy.id in active:
            policy.remove()
    return ids
