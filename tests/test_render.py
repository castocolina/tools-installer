import io
from pathlib import Path

from rich.console import Console

from installer.audit import ToolStatus
from installer.checksums import ChecksumMismatch
from installer.engine import InstallOutcome
from installer.model import Method, Tool
from installer.render import (
    render_audit,
    render_dependency_notice,
    render_guard,
    render_guard_status,
    render_summary,
    render_verification,
)
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


def test_render_doctor_prints_findings_with_meaning_and_next_step() -> None:
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
    assert "not on PATH" in out  # the missing-dir guidance title
    assert "make fix" in out  # the missing-dir next step
    assert "github.com" not in out  # troubleshooting URL never printed here


def test_render_doctor_healthy_says_healthy() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    console, buf = _console()
    render_doctor(DoctorReport(missing=(), broken=(), duplicated=()), console)
    out = buf.getvalue()
    assert "healthy" in out.lower()


def test_render_troubleshooting_prints_link() -> None:
    from installer.render import render_troubleshooting

    console, buf = _console()
    render_troubleshooting(console)
    assert "github.com/castocolina/tools-installer" in buf.getvalue()


def test_render_uninstall_lists_paths() -> None:
    from installer.render import render_uninstall

    console, buf = _console()
    render_uninstall([Path("/x/opt/fd"), Path("/x/bin/fd")], console)
    text = buf.getvalue()
    assert "/x/opt/fd" in text
    assert "/x/bin/fd" in text


def test_render_uninstall_reports_nothing_to_do() -> None:
    from installer.render import render_uninstall

    console, buf = _console()
    render_uninstall([], console)
    assert "Nothing to uninstall" in buf.getvalue()


def test_render_rc_duplicates_lists_files_and_lines():
    from installer.render import render_rc_duplicates

    console = Console(record=True, width=100)
    render_rc_duplicates({Path("/h/.zshrc"): ['export PATH="$BUN_INSTALL/bin:$PATH"']}, console)
    text = console.export_text()
    assert "/h/.zshrc" in text
    assert "BUN_INSTALL" in text


def test_render_rc_duplicates_says_clean_when_empty():
    from installer.render import render_rc_duplicates

    console = Console(record=True, width=100)
    render_rc_duplicates({}, console)
    assert "No duplicate" in console.export_text()


def test_render_verification_marks_download_outcomes():
    console = Console(record=True)
    outcomes = [
        InstallOutcome("rg", "installed", method_kind="github_release", verified=True),
        InstallOutcome("fd", "installed", method_kind="github_release", verified=False),
        InstallOutcome("jq", "installed", method_kind="brew"),
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert "rg: sha256 ✓" in text
    assert "fd: unverified" in text
    assert "jq" not in text  # brew does its own integrity checks


def test_render_verification_prints_mismatch_error():
    console = Console(record=True)
    exc = ChecksumMismatch("a.tar.gz", "12345678" + "a" * 56, "fedcba98" + "b" * 56)
    outcomes = [
        InstallOutcome("rg", "checksum-mismatch", method_kind="github_release", errors=(exc,))
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert "rg" in text
    assert "12345678" in text
    assert "fedcba98" in text


def test_render_summary_includes_mismatch_bucket():
    console = Console(record=True)
    summary = Summary(installed=("rg",), already=(), failed=(), no_method=(), mismatched=("fd",))
    render_summary(summary, console)
    text = console.export_text()
    assert "Checksum mismatch: 1" in text
    assert "checksum mismatch: fd" in text


def test_render_verification_ignores_failed_download_outcome():
    # A download outcome with status "failed" should produce no output.
    console = Console(record=True)
    outcomes = [
        InstallOutcome("rg", "failed", method_kind="github_release"),
    ]
    render_verification(outcomes, console)
    assert console.export_text().strip() == ""


def test_render_guard_prints_actions_and_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard({"pip": "created", "npm": "created"}, "watch PATH order", console, removing=False)
    out = buf.getvalue()
    assert "Installing the pip/npm ban" in out
    assert "created: pip" in out
    assert "watch PATH order" in out


def test_render_guard_removing_has_no_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard({"pip": "removed"}, None, console, removing=True)
    out = buf.getvalue()
    assert "Removing the pip/npm ban" in out
    assert "removed: pip" in out


def test_render_guard_status_silent_when_inactive():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": False, "npm": False, "pip3": False}, None, console)
    assert buf.getvalue() == ""


def test_render_guard_status_reports_active_shims_and_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": True, "npm": False, "pip3": True}, "PATH order", console)
    out = buf.getvalue()
    assert "pip/npm ban active" in out
    assert "pip" in out
    assert "PATH order" in out


def test_render_guard_status_warning_only_no_active_shims():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": False, "npm": False}, "PATH order warning", console)
    out = buf.getvalue()
    assert "pip/npm ban active" not in out
    assert "PATH order warning" in out


def test_render_guard_status_active_shims_no_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": True, "npm": False}, None, console)
    out = buf.getvalue()
    assert "pip/npm ban active" in out
    assert "guard warning" not in out


def test_render_guard_status_includes_reload_next_step():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": True, "npm": False}, None, console)
    out = buf.getvalue()
    assert "pip/npm ban active" in out
    assert "hash -r" in out  # the reload next step from guard_guidance


def test_render_dependency_notice_shows_dragged_in_and_warnings() -> None:
    console, buf = _console()
    render_dependency_notice(
        ("pnpm",), ("foo is not available on this platform — skipped",), console
    )
    out = buf.getvalue()
    assert "pnpm" in out
    assert "not available" in out


def test_render_dependency_notice_silent_when_nothing_to_say() -> None:
    console, buf = _console()
    render_dependency_notice((), (), console)
    assert buf.getvalue().strip() == ""


def test_guidance_text_styles_by_severity_and_suppresses_empty_next_step() -> None:
    from installer.guidance import Guidance
    from installer.render import guidance_text

    items = [
        Guidance(title="All good", meaning="No issues.", next_step="", severity="ok"),
        Guidance(title="Bad dir", meaning="Missing.", next_step="Run make fix.", severity="warn"),
    ]
    text = guidance_text(items)
    plain = text.plain
    # Empty next_step (the ok item) renders no arrow line; the warn item does.
    assert "→" not in plain.split("Bad dir")[0]
    assert "→ Run make fix." in plain
    # Severity drives the style spans: ok->green title, warn->yellow title.
    styles = {str(span.style) for span in text.spans}
    assert "green" in styles
    assert "yellow" in styles
