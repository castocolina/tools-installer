import io
from pathlib import Path

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


def test_render_doctor_reports_problems_and_link() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    report = DoctorReport(
        missing=(Path("/a/bin"),),
        broken=(Path("/c/bin"),),
        duplicated=(Path("/b/bin"),),
    )
    console, buf = _console()
    render_doctor(report, console)
    out = buf.getvalue()
    assert "/a/bin" in out and "/c/bin" in out and "/b/bin" in out
    assert "missing from PATH" in out
    assert "github.com/castocolina/tools-installer" in out


def test_render_doctor_healthy_has_no_link() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    console, buf = _console()
    render_doctor(DoctorReport(missing=(), broken=(), duplicated=()), console)
    out = buf.getvalue()
    assert "healthy" in out.lower()
    assert "github.com" not in out


def test_render_troubleshooting_prints_link() -> None:
    from installer.render import render_troubleshooting

    console, buf = _console()
    render_troubleshooting(console)
    assert "github.com/castocolina/tools-installer" in buf.getvalue()
