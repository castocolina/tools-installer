"""A link-mode-aware block policy for the move_link_mode tests.

`tweak_policy` keeps its block in one fixed rc file, so it cannot express a block that
moves between rc files on a link-mode change. This double does: apply writes its marker
block into the live-mode paths, remove strips it from the union of every path it may
have written.
"""

from collections.abc import Callable
from pathlib import Path

from installer.policy import Policy, PolicyLayer, PolicyResult
from installer.shellrc import apply_block, strip_block

BLOCK_BEGIN = "# >>> tools-installer block >>>"
BLOCK_END = "# <<< tools-installer block <<<"
_BLOCK = f"{BLOCK_BEGIN}\nalias block-marker=true\n{BLOCK_END}"


def block_policy(
    *,
    apply_rc_paths: list[Path] | Callable[[], list[Path]],
    remove_rc_paths: list[Path],
    policy_id: str = "block",
) -> Policy:
    """A link-mode-aware policy whose block lands in `apply_rc_paths` (re-read on each
    apply) and is stripped from every `remove_rc_paths` file on remove."""

    def read_apply_rc_paths() -> list[Path]:
        return apply_rc_paths() if callable(apply_rc_paths) else apply_rc_paths

    def _present() -> bool:
        return any(
            path.exists() and BLOCK_BEGIN in path.read_text().split("\n")
            for path in remove_rc_paths
        )

    def _apply() -> PolicyResult:
        targets = read_apply_rc_paths()
        for path in targets:
            current = path.read_text() if path.exists() else ""
            path.write_text(apply_block(current, _BLOCK, BLOCK_BEGIN, BLOCK_END))
        detail = "written to " + ", ".join(str(p) for p in targets)
        return PolicyResult(layers=(PolicyLayer("Block", detail),), reload_hint=None, warning=None)

    def _remove() -> PolicyResult:
        for path in remove_rc_paths:
            if path.exists():
                path.write_text(strip_block(path.read_text(), BLOCK_BEGIN, BLOCK_END))
        detail = "cleared from " + ", ".join(str(p) for p in remove_rc_paths)
        return PolicyResult(layers=(PolicyLayer("Block", detail),), reload_hint=None, warning=None)

    return Policy(
        id=policy_id,
        label="Block",
        description="a marker block that follows the link mode",
        active=_present(),
        apply=_apply,
        remove=_remove,
        is_active=_present,
        link_mode_aware=True,
    )
