import io

from rich.console import Console

from installer.audit import ToolStatus
from installer.model import Method, Tool
from installer.render import render_audit, render_summary
from installer.session import Summary


def _tool(tool_id: str, category: str = "search") -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, no_color=True), buf


def test_render_audit_lists_each_tool_and_its_state() -> None:
    statuses = [
        ToolStatus(tool=_tool("rg"), installed=True),
        ToolStatus(tool=_tool("fd"), installed=False),
    ]
    console, buf = _console()
    render_audit(statuses, console)
    out = buf.getvalue()
    assert "rg" in out and "fd" in out
    assert "installed" in out and "missing" in out


def test_render_summary_reports_counts_and_ids() -> None:
    summary = Summary(installed=("rg",), already=("jq",), failed=("fd",), no_method=())
    console, buf = _console()
    render_summary(summary, console)
    out = buf.getvalue()
    assert "Installed: 1" in out
    assert "rg" in out and "jq" in out and "fd" in out


def test_render_summary_handles_empty() -> None:
    console, buf = _console()
    render_summary(Summary(installed=(), already=(), failed=(), no_method=()), console)
    out = buf.getvalue()
    assert "Installed: 0" in out
