from installer.audit import ToolStatus, audit
from installer.model import Method, Tool


def _tool(tool_id: str, cmd: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=cmd,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def test_audit_marks_each_tool_installed_or_missing():
    tools = [_tool("rg", "rg"), _tool("jq", "jq")]
    present = {"rg"}

    def installed(tool: Tool) -> bool:
        return tool.cmd in present

    result = audit(tools, installed)
    assert result == [
        ToolStatus(tool=tools[0], installed=True),
        ToolStatus(tool=tools[1], installed=False),
    ]


def test_audit_preserves_order_and_handles_empty():
    assert audit([], lambda tool: True) == []
