"""Whether a tool is already installed, by resolving its command on PATH."""

import shutil

from installer.model import Tool


def is_installed(tool: Tool) -> bool:
    """True if the tool's command resolves on the current PATH."""
    return shutil.which(tool.cmd) is not None
