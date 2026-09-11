import io
from pathlib import Path

from rich.console import Console

from installer.audit import ToolStatus
from installer.checksums import ChecksumMismatch
from installer.engine import InstallOutcome
from installer.model import Method, Tool
from installer.pnpm_globals import NodeGlobal, NodeGlobalsReport
from installer.render import (
    render_audit,
    render_dependency_notice,
    render_failure_details,
    render_guard,
    render_guard_status,
    render_handoff,
    render_node_globals,
    render_postinstall_warnings,
    render_skipped,
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


def test_render_summary_counts_and_lists_dependency_failed() -> None:
    summary = Summary(
        installed=("rg",),
        already=(),
        failed=("sdkman",),
        no_method=(),
        dependency_failed=("java", "gradle"),
    )
    console, buf = _console()
    render_summary(summary, console)
    out = buf.getvalue()
    assert "Dependency failed: 2" in out
    assert "java" in out and "gradle" in out
    assert "Installed:" in out
    assert "Failed:" in out


def test_render_summary_counts_and_lists_manual_required() -> None:
    summary = Summary(
        installed=(),
        already=(),
        failed=(),
        no_method=(),
        manual_required=("pi",),
    )
    console, buf = _console()
    render_summary(summary, console)
    out = buf.getvalue()
    assert "Manual setup required: 1" in out
    assert "pi" in out


def test_render_summary_still_reports_zero_when_nothing_was_skipped() -> None:
    console, buf = _console()
    render_summary(Summary(installed=(), already=(), failed=(), no_method=()), console)
    assert "Dependency failed: 0" in buf.getvalue()


def test_render_failure_details_prints_the_error() -> None:
    console, buf = _console()
    render_failure_details(
        [InstallOutcome("puppeteer", "failed", errors=(RuntimeError("network unreachable"),))],
        console,
    )
    out = buf.getvalue()
    assert "puppeteer failed: network unreachable" in out


def test_render_failure_details_is_silent_when_nothing_failed() -> None:
    console, buf = _console()
    render_failure_details([InstallOutcome("rg", "installed", method_kind="brew")], console)
    assert buf.getvalue() == ""


def test_render_failure_details_falls_back_without_a_captured_error() -> None:
    console, buf = _console()
    render_failure_details([InstallOutcome("puppeteer", "failed")], console)
    assert "puppeteer failed: no method succeeded" in buf.getvalue()


def test_render_skipped_names_the_tool_and_its_blockers() -> None:
    console, buf = _console()
    render_skipped(
        [
            InstallOutcome("sdkman", "failed"),
            InstallOutcome("java", "dependency-failed", blocked_by=("sdkman",)),
        ],
        console,
    )
    out = buf.getvalue()
    assert "java skipped — dependency failed: sdkman" in out
    skip_lines = [line for line in out.splitlines() if "skipped" in line]
    assert len(skip_lines) == 1
    assert "java" in skip_lines[0]


def test_render_skipped_joins_multiple_blockers() -> None:
    console, buf = _console()
    render_skipped(
        [InstallOutcome("java", "dependency-failed", blocked_by=("sdkman", "uv"))],
        console,
    )
    assert "dependency failed: sdkman, uv" in buf.getvalue()


def test_render_skipped_is_silent_when_nothing_was_skipped() -> None:
    console, buf = _console()
    render_skipped(
        [
            InstallOutcome("rg", "installed", method_kind="brew"),
            InstallOutcome("fd", "failed"),
        ],
        console,
    )
    assert buf.getvalue() == ""


def test_render_skipped_still_names_the_tool_without_blockers() -> None:
    console, buf = _console()
    render_skipped([InstallOutcome("java", "dependency-failed")], console)
    out = buf.getvalue()
    assert "java" in out
    assert "an earlier failure" in out
    assert "skipped — dependency failed: an earlier failure" in out


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


def test_render_guard_status_reports_per_command_labels():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"npx": True, "pip": True, "npm": False}, None, console)
    out = buf.getvalue()
    assert "Package manager guards active" in out
    assert "npx: redirected to pnpm dlx" in out
    assert "pip: blocked" in out


def test_render_guard_status_warning_only_no_active_shims():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": False, "npm": False}, "PATH order warning", console)
    out = buf.getvalue()
    assert "Package manager guards active" not in out
    assert "PATH order warning" in out


def test_render_guard_status_active_shims_no_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": True, "npm": False}, None, console)
    out = buf.getvalue()
    assert "Package manager guards active" in out
    assert "pip: blocked" in out
    assert "guard warning" not in out


def test_render_node_globals_silent_when_healthy() -> None:
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    entries = (NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),)
    render_node_globals(
        NodeGlobalsReport(entries=entries, missing=(), managed=("@mermaid-js/mermaid-cli",)),
        console,
    )
    assert buf.getvalue() == ""


def test_render_node_globals_prints_finding() -> None:
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    entries = (NodeGlobal("mmdc", "@mermaid-js/mermaid-cli", "mmdc"),)
    render_node_globals(
        NodeGlobalsReport(entries=entries, missing=("mmdc",), managed=("@mermaid-js/mermaid-cli",)),
        console,
    )
    out = buf.getvalue()
    assert "mmdc" in out
    assert "make setup" in out


def test_render_guard_status_includes_reload_next_step():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"npx": True}, None, console)
    out = buf.getvalue()
    assert "hash -r" in out


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


def test_render_postinstall_warnings_names_the_tool_and_the_detail() -> None:
    outcomes = [
        InstallOutcome(
            "codegraph",
            "installed",
            method_kind="github_release",
            postinstall_warning="codegraph MCP registration failed: exit 1",
        ),
        InstallOutcome("rg", "installed", method_kind="brew"),
    ]
    console, buf = _console()
    render_postinstall_warnings(outcomes, console)
    out = buf.getvalue()
    assert "codegraph" in out
    assert "codegraph MCP registration failed: exit 1" in out
    assert "rg" not in out


def test_render_postinstall_warnings_is_silent_when_nothing_warned() -> None:
    outcomes = [InstallOutcome("rg", "installed", method_kind="brew")]
    console, buf = _console()
    render_postinstall_warnings(outcomes, console)
    assert buf.getvalue().strip() == ""


def test_render_handoff_prints_instructions_for_manual_required_outcomes() -> None:
    outcomes = [
        InstallOutcome(
            "pi",
            "manual-required",
            method_kind="host_setup",
            handoff=(
                "After leaving the installer, run these Pi setup commands in a console:",
                "pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent",
                "pi",
            ),
        ),
        InstallOutcome("rg", "installed", method_kind="brew"),
    ]
    console, buf = _console()
    render_handoff(outcomes, console)
    out = buf.getvalue()
    assert "pi" in out
    assert "After leaving the installer, run these Pi setup commands in a console:" in out
    assert "pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent" in out
    assert "rg" not in out


def test_render_handoff_is_silent_when_nothing_needs_one() -> None:
    outcomes = [
        InstallOutcome("rg", "installed", method_kind="brew"),
        InstallOutcome("fd", "failed"),
    ]
    console, buf = _console()
    render_handoff(outcomes, console)
    assert buf.getvalue().strip() == ""
