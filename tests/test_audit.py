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


def test_audit_returns_the_stub_reason() -> None:
    tool = _tool("java", "java")
    result = audit([tool], lambda t: False, stub_reason=lambda t: "reason text")
    assert result == [ToolStatus(tool=tool, installed=False, reason="reason text")]


def test_audit_asks_for_a_reason_only_for_missing_rows() -> None:
    tools = [_tool("rg", "rg"), _tool("jq", "jq")]
    calls: list[str] = []

    def installed(tool: Tool) -> bool:
        return tool.id == "rg"

    def stub_reason(tool: Tool) -> str | None:
        calls.append(tool.id)
        return "missing stub"

    audit(tools, installed, stub_reason=stub_reason)
    assert calls == ["jq"]


def test_audit_without_stub_reason_has_plain_missing_status() -> None:
    tool = _tool("java", "java")
    result = audit([tool], lambda t: False, stub_reason=lambda t: None)
    assert result == [ToolStatus(tool=tool, installed=False, reason=None)]
