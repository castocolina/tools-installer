import pytest

from installer.model import Method, Tool
from installer.status import is_installed


def _tool(cmd: str) -> Tool:
    return Tool(
        id="t",
        name="t",
        category="c",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": "t"}),),
    )


def test_is_installed_true_when_cmd_on_path(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/jq" if cmd == "jq" else None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    assert is_installed(_tool("jq")) is True


def test_is_installed_false_when_cmd_absent(monkeypatch: pytest.MonkeyPatch):
    import installer.status as status

    def fake_which(cmd: str) -> str | None:
        return None

    monkeypatch.setattr(status.shutil, "which", fake_which)
    assert is_installed(_tool("jq")) is False
