import io
from collections.abc import Callable
from pathlib import Path

import pytest
from rich.cells import cell_len
from rich.console import Console

import installer.executors as executors
from installer.checksums import ChecksumMismatch
from installer.engine import InstallOutcome
from installer.executors import ExecutorError
from installer.pnpm_globals import NodeGlobal, NodeGlobalsReport
from installer.render import (
    outcome_row_text,
    render_failure_details,
    render_guard,
    render_guard_status,
    render_handoff,
    render_node_globals,
    render_post_install_handoff,
    render_postinstall_warnings,
    render_remove_yourself,
    render_run_summary,
    render_skipped,
    render_uninstall,
    render_verification,
    running_row_text,
    summary_head,
)
from installer.run import CommandError
from installer.session import WORDS, Disposition, PlanRow, Result, RowOutcome
from installer.version_status import Health


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, no_color=True), buf


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


def test_failure_report_keeps_an_earlier_smoke_reason(tmp_path: Path) -> None:
    elf = tmp_path / "bin"
    elf.parent.mkdir(parents=True, exist_ok=True)
    elf.write_bytes(b"\x7fELF" + b"\x00" * 60)
    elf.chmod(0o755)
    try:
        executors.smoke_binary(elf)
    except ExecutorError as exc:
        smoke_error = exc
    else:
        raise AssertionError("expected smoke_binary to fail on invalid ELF")
    console, buf = _console()
    render_failure_details(
        [
            InstallOutcome(
                "demo",
                "failed",
                errors=(
                    smoke_error,
                    CommandError(["brew", "install", "demo"], 1),
                ),
            )
        ],
        console,
    )
    out = buf.getvalue().replace("\n", "")
    assert "Exec format error" in out
    assert "brew install demo" in out
    assert "demo failed:" in out


def test_render_failure_details_escapes_bracketed_error_text() -> None:
    console, buf = _console()
    render_failure_details(
        [
            InstallOutcome(
                "curl-tool",
                "failed",
                errors=(RuntimeError("unexpected error [not-supported] while resolving"),),
            )
        ],
        console,
    )
    out = buf.getvalue()
    assert "[not-supported]" in out


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


@pytest.mark.parametrize(
    "render",
    [render_uninstall, render_remove_yourself],
    ids=["render_uninstall", "render_remove_yourself"],
)
def test_uninstall_path_lines_print_unwrapped_and_literal(
    render: Callable[..., None], tmp_path: Path
) -> None:
    """Paths print verbatim at any console width and with markup disabled."""
    long_path = tmp_path / ("a" * 60) / "bin" / "ruff"
    markup_path = tmp_path / "[bold]dir" / "bin" / "ruff"
    buf = io.StringIO()
    console = Console(file=buf, width=40, no_color=True)
    render([long_path, markup_path], console)
    text = buf.getvalue()
    assert str(long_path) in text
    assert str(markup_path) in text
    assert "[bold]" in text


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


def test_render_verification_prints_the_unverified_reason() -> None:
    console = Console(record=True)
    reason = "no checksum file and no GitHub sha256 digest for x.tar.gz"
    outcomes = [
        InstallOutcome(
            "rg",
            "installed",
            method_kind="github_release",
            verified=False,
            unverified_reason=reason,
        ),
        InstallOutcome("fd", "installed", method_kind="github_release", verified=True),
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert f"  rg: unverified ({reason})" in text
    assert "fd: sha256 ✓" in text


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


def test_render_verification_escapes_bracketed_mismatch_error() -> None:
    console = Console(record=True)
    outcomes = [
        InstallOutcome(
            "rg",
            "checksum-mismatch",
            method_kind="github_release",
            errors=(RuntimeError("digest mismatch [rate-limited] retry later"),),
        )
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert "[rate-limited]" in text


def test_render_verification_covers_app_outcomes() -> None:
    console = Console(record=True)
    outcomes = [
        InstallOutcome("drawio", "installed", method_kind="app", verified=True),
        InstallOutcome(
            "vscode",
            "installed",
            method_kind="app",
            verified=False,
            unverified_reason="unpinned url; no sha256 to verify against",
        ),
    ]
    render_verification(outcomes, console)
    text = console.export_text()
    assert "drawio: sha256 ✓" in text
    assert "vscode: unverified (unpinned url; no sha256 to verify against)" in text


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


def test_render_post_install_handoff_prints_heading_and_instruction_lines() -> None:
    outcomes = [
        InstallOutcome(
            "omz",
            "installed",
            post_install_handoff=("do [this]", "chsh -s x"),
        ),
        InstallOutcome("rg", "installed", method_kind="brew"),
    ]
    console, buf = _console()
    render_post_install_handoff(outcomes, console)
    out = buf.getvalue()
    assert "omz" in out
    assert "do [this]" in out
    assert "chsh -s x" in out
    heading_idx = out.index("omz")
    first_idx = out.index("do [this]")
    second_idx = out.index("chsh -s x")
    assert heading_idx < first_idx < second_idx
    assert "rg" not in out


def test_render_post_install_handoff_is_silent_for_empty_instruction_tuple() -> None:
    console, buf = _console()
    render_post_install_handoff([InstallOutcome("rg", "installed")], console)
    assert buf.getvalue() == ""


def test_render_post_install_handoff_is_silent_for_empty_outcome_list() -> None:
    console, buf = _console()
    render_post_install_handoff([], console)
    assert buf.getvalue() == ""


def test_render_post_install_handoff_prints_installed_outcomes() -> None:
    console, buf = _console()
    render_post_install_handoff(
        [InstallOutcome("omz", "installed", post_install_handoff=("chsh -s x",))],
        console,
    )
    out = buf.getvalue()
    assert "omz" in out
    assert "chsh -s x" in out


def test_render_post_install_handoff_preserves_bracketed_instruction_text() -> None:
    console, buf = _console()
    render_post_install_handoff(
        [InstallOutcome("omz", "installed", post_install_handoff=("do [this]",))],
        console,
    )
    assert "[this]" in buf.getvalue()


def test_render_disk_pressure_prints_nothing_for_an_empty_guidance_list() -> None:
    from installer.diskusage import DiskPressure
    from installer.enums import DaemonState
    from installer.render import render_disk_pressure

    console, buf = _console()
    render_disk_pressure(
        DiskPressure(
            home_free_percent=80.0,
            tmp_used_percent=10.0,
            daemon=DaemonState.INACTIVE,
            tmp_threshold=True,
        ),
        console,
    )
    assert buf.getvalue() == ""


def test_render_disk_pressure_prints_an_emphasised_item_through_guidance_text() -> None:
    from rich.console import Console

    from installer.diskusage import DiskPressure
    from installer.enums import DaemonState
    from installer.render import render_disk_pressure

    buf = io.StringIO()
    console = Console(
        file=buf, width=160, force_terminal=True, color_system="standard", record=True
    )
    render_disk_pressure(
        DiskPressure(
            home_free_percent=10.0,
            tmp_used_percent=10.0,
            daemon=DaemonState.INACTIVE,
            tmp_threshold=True,
        ),
        console,
    )
    rendered = console.export_text(styles=True)
    assert "Background cleanup is off" in rendered
    assert "\x1b[1;" in rendered


def test_guidance_text_bolds_the_style_for_an_emphasised_item() -> None:
    from installer.guidance import Guidance
    from installer.render import guidance_text

    items = [
        Guidance(title="Ordinary error", meaning="m", next_step="n", severity="error"),
        Guidance(
            title="Emphasised error",
            meaning="m2",
            next_step="n2",
            severity="error",
            emphasis=True,
        ),
    ]
    text = guidance_text(items)
    styles = [str(span.style) for span in text.spans]
    assert "red" in styles
    assert "bold red" in styles


def test_guidance_text_non_emphasised_item_renders_exactly_as_before() -> None:
    from installer.guidance import Guidance
    from installer.render import guidance_text

    item = Guidance(title="Missing dir", meaning="m", next_step="n", severity="warn")
    text = guidance_text([item])
    styles = {str(span.style) for span in text.spans}
    assert styles == {"yellow"}


def test_render_remove_yourself_lists_paths_without_escalation() -> None:
    from installer.render import render_remove_yourself

    console, buf = _console()
    render_remove_yourself([Path("/x/bin/yq"), Path("/x/bin/drawio")], console)
    text = buf.getvalue()
    assert "/x/bin/yq" in text
    assert "/x/bin/drawio" in text
    assert "remove them yourself" in text
    for banned in ("sudo", "pkexec", "doas"):
        assert banned not in text
    empty, empty_buf = _console()
    render_remove_yourself([], empty)
    assert empty_buf.getvalue() == ""


@pytest.mark.parametrize("hint", [True, False])
def test_render_plan_row_anatomy_fits_78_cells_with_a_24_char_id(hint: bool) -> None:
    from installer.render import render_plan

    row = PlanRow(
        "abcdefghijklmnopqrstuvwx",
        Disposition.SKIP,
        "already current",
        health=Health.OK,
        can_reinstall=True,
    )
    console, buf = _console()
    console.width = 80
    render_plan([row], console, hint=hint)
    line = next(line for line in buf.getvalue().splitlines() if row.tool_id in line)
    expected = "✓ abcdefghijklmnopqrstuvwx  skipped — already current"
    if hint:
        expected += " (r: reinstall)"
    assert line == expected
    assert cell_len(line) <= 78


@pytest.mark.parametrize("disposition", list(Disposition))
@pytest.mark.parametrize("tier", ["system", "user", "ai"])
def test_render_plan_words_and_marks_come_from_the_tables(
    disposition: Disposition, tier: str
) -> None:
    from installer.render import render_plan
    from installer.version_status import HEALTH_MARKS

    del tier
    health = {
        Disposition.INSTALL: Health.MISSING,
        Disposition.UPDATE: Health.OUTDATED,
        Disposition.REPAIR: Health.BROKEN,
        Disposition.RECONFIGURE: Health.MISCONFIGURED,
        Disposition.REINSTALL: Health.OK,
        Disposition.SKIP: Health.OK,
        Disposition.BLOCKED: Health.UNAVAILABLE,
        Disposition.WAIT: None,
    }[disposition]
    row = PlanRow("example", disposition, "why", health=health)
    console, buf = _console()
    render_plan([row], console)
    line = next(line for line in buf.getvalue().splitlines() if "example" in line)
    glyph = HEALTH_MARKS[health or Health.CHECKING][0]
    assert line.startswith(glyph)
    assert WORDS[disposition].review in line
    if disposition is Disposition.WAIT:
        assert " — " not in line
    colored = io.StringIO()
    color_console = Console(file=colored, width=80, force_terminal=True, color_system="standard")
    render_plan([row], color_console)
    word = WORDS[disposition].review
    color_code = {"": None, "dim": 2, "green": 32, "yellow": 33, "red": 31}[
        WORDS[disposition].style
    ]
    if color_code is None:
        assert word in colored.getvalue()
    else:
        assert f"\x1b[{color_code}m{word}\x1b[0m" in colored.getvalue()


def test_health_marks_is_the_catalog_glyph_table() -> None:
    from installer.catalog_tui import health_cell
    from installer.version_status import HEALTH_MARKS

    assert health_cell(None).plain == HEALTH_MARKS[Health.CHECKING][0]


def test_render_plan_groups_dragged_rows_under_their_first_requester() -> None:
    from installer.render import render_plan

    rows = [
        PlanRow("node", Disposition.SKIP, "already present", requested_by="mmdc", health=Health.OK),
        PlanRow("mmdc", Disposition.INSTALL, "not installed", health=Health.MISSING),
        PlanRow("jq", Disposition.UPDATE, "new version", health=Health.OUTDATED),
    ]
    console, buf = _console()
    render_plan(rows, console)
    lines = [line for line in buf.getvalue().splitlines() if line.startswith(("○", "✓", "↑"))]
    assert [line.split()[1] for line in lines] == ["mmdc", "node", "jq"]
    assert lines[0].startswith("○")
    assert lines[1].startswith("✓   node")


def test_render_plan_head_counts_review_words_and_notes_the_order_only_with_dragged_rows() -> None:
    from installer.render import plan_head

    rows = [
        PlanRow("node", Disposition.SKIP, "present", requested_by="mmdc"),
        PlanRow("mmdc", Disposition.INSTALL, "missing"),
        PlanRow("jq", Disposition.UPDATE, "old"),
    ]
    assert plan_head(rows) == (
        "Install plan — 1 will install, 1 will update, 1 skipped. "
        "Indented rows are needed by the tool above and run first."
    )
    assert plan_head(rows[1:]) == "Install plan — 1 will install, 1 will update"
    assert plan_head([]) == "Install plan — nothing selected"


def test_render_plan_lists_a_chain_once_at_one_indent_level() -> None:
    from installer.render import render_plan

    rows = [
        PlanRow("c", Disposition.SKIP, "present", requested_by="a"),
        PlanRow("a", Disposition.INSTALL, "missing"),
        PlanRow("b", Disposition.SKIP, "present", requested_by="a"),
    ]
    console, buf = _console()
    render_plan(rows, console)
    lines = [line for line in buf.getvalue().splitlines() if line.startswith(("…", "○", "✓"))]
    assert sum(line.split()[1] == "c" for line in lines) == 1
    assert sum(line.split()[1] == "b" for line in lines) == 1
    assert [line.split()[1] for line in lines] == ["a", "c", "b"]
    assert all(line.startswith(("…   ", "○   ", "✓   ")) for line in lines[1:])


def test_render_plan_keeps_a_dragged_row_under_a_blocked_requester() -> None:
    from installer.render import render_plan

    rows = [
        PlanRow("a", Disposition.BLOCKED, "needs z", health=Health.BROKEN),
        PlanRow("z", Disposition.BLOCKED, "blocked", requested_by="a", health=Health.UNAVAILABLE),
    ]
    console, buf = _console()
    render_plan(rows, console)
    lines = [line for line in buf.getvalue().splitlines() if line.startswith(("!", "–"))]
    assert len(lines) == 2
    assert lines[0].startswith("! a")
    assert lines[1].startswith("–   z")


def test_render_plan_reconfigure_row_lists_its_steps_at_the_word_column() -> None:
    from installer.model import ConfigStep
    from installer.render import plan_row_text

    row = PlanRow(
        "pony",
        Disposition.RECONFIGURE,
        "configuration missing",
        health=Health.MISCONFIGURED,
        steps=(
            ConfigStep("install ponytail for Codex", "plugin_enable"),
            ConfigStep("sync terminals", "terminal_sync"),
        ),
    )
    text = plan_row_text(row, 4, 78, hint=False).plain
    continuation = next(line for line in text.splitlines() if "to configure:" in line)
    assert continuation.lstrip() == "to configure: install ponytail for Codex; sync terminals"
    assert len(continuation) - len(continuation.lstrip()) == 8


def test_render_plan_folds_a_long_reason_with_a_hanging_indent() -> None:
    from installer.render import render_plan

    row = PlanRow("tool", Disposition.BLOCKED, "word " * 40, health=Health.BROKEN)
    console, buf = _console()
    render_plan([row], console, width=78)
    lines = [
        line
        for line in buf.getvalue().splitlines()
        if line.startswith("!") or line.startswith(" " * 8)
    ]
    assert all(cell_len(line) <= 78 for line in lines)
    assert all(line.startswith(" " * 8) for line in lines[1:])


def test_render_plan_folds_wide_unicode_reasons_within_cell_width() -> None:
    from installer.render import render_plan

    row = PlanRow("tool", Disposition.BLOCKED, "界 " * 40, health=Health.BROKEN)
    console, buf = _console()
    render_plan([row], console, width=78)
    assert all(cell_len(line) <= 78 for line in buf.getvalue().splitlines()[1:])


def test_render_plan_folds_a_400_char_reason_and_twelve_steps_within_width() -> None:
    from installer.model import ConfigStep
    from installer.render import render_plan

    steps = tuple(
        ConfigStep(f"perform step number {index}", "terminal_sync") for index in range(12)
    )
    row = PlanRow(
        "tool", Disposition.RECONFIGURE, "word " * 80, health=Health.MISCONFIGURED, steps=steps
    )
    console, buf = _console()
    render_plan([row], console, width=78)
    assert all(cell_len(line) <= 78 for line in buf.getvalue().splitlines())


def test_render_plan_renders_markup_and_escapes_in_a_reason_literally() -> None:
    from installer.render import render_plan

    row = PlanRow("safe", Disposition.INSTALL, "[red]x[/] \x1b[31mboom", health=Health.MISSING)
    console, buf = _console()
    render_plan([row], console)
    output = buf.getvalue()
    assert "[red]x[/]" in output
    assert "\x1b" not in output


def test_render_plan_sanitizes_step_text() -> None:
    from installer.model import ConfigStep
    from installer.render import render_plan

    step = ConfigStep("sync \x1b[2J terminals", "terminal_sync")
    row = PlanRow(
        "pony", Disposition.RECONFIGURE, "needed", health=Health.MISCONFIGURED, steps=(step,)
    )
    console, buf = _console()
    render_plan([row], console)
    assert "\x1b" not in buf.getvalue()
    assert "sync [2J terminals" in buf.getvalue()


def _done(tool_id: str, disposition: Disposition, *, health: Health = Health.OK) -> RowOutcome:
    return RowOutcome(PlanRow(tool_id, disposition, "needed", health=health), "done")


def test_render_run_summary_first_line_is_the_summary_head() -> None:
    outcomes = [
        _done("fd", Disposition.INSTALL),
        _done("jq", Disposition.UPDATE),
        RowOutcome(PlanRow("rg", Disposition.SKIP, "already current", health=Health.OK), "skipped"),
        RowOutcome(
            PlanRow("x", Disposition.INSTALL, "not installed", health=Health.MISSING), "failed"
        ),
    ]
    console, buf = _console()
    render_run_summary(outcomes, console)
    assert buf.getvalue().splitlines()[0] == "Summary — 1 installed, 1 updated, 1 skipped, 1 failed"
    empty, empty_buf = _console()
    render_run_summary([], empty)
    assert empty_buf.getvalue().splitlines()[0] == "Summary — nothing selected"


def test_summary_head_is_the_same_line_the_renderer_prints() -> None:
    outcomes = [_done("fd", Disposition.INSTALL)]
    assert summary_head(outcomes) == "Summary — 1 installed"
    console, buf = _console()
    render_run_summary(outcomes, console)
    assert buf.getvalue().splitlines()[0] == summary_head(outcomes)


def test_done_outcome_row_shows_the_done_word_and_a_green_check() -> None:
    outcomes = [_done("fd", Disposition.INSTALL)]
    console, buf = _console()
    render_run_summary(outcomes, console)
    row = buf.getvalue().splitlines()[1]
    assert row == "✓ fd  installed"
    colored = io.StringIO()
    render_run_summary(outcomes, Console(file=colored, width=80, force_terminal=True))
    value = colored.getvalue()
    assert "\x1b[32m✓\x1b[0m" in value
    assert "\x1b[32minstalled\x1b[0m" in value


def test_done_outcome_row_uses_the_disposition_done_word_in_green() -> None:
    outcome = _done("jq", Disposition.UPDATE)
    text = outcome_row_text(outcome, 4, 78)
    assert text.plain.splitlines()[0] == "✓ jq    updated"
    colored = io.StringIO()
    Console(file=colored, width=80, force_terminal=True).print(text, markup=False)
    assert "\x1b[32mupdated\x1b[0m" in colored.getvalue()


def test_render_run_summary_rows_follow_display_order() -> None:
    requester = PlanRow("mmdc", Disposition.INSTALL, "not installed", health=Health.MISSING)
    dragged = PlanRow(
        "node", Disposition.INSTALL, "needed by mmdc", requested_by="mmdc", health=Health.OK
    )
    outcomes = [
        RowOutcome(dragged, "done"),
        RowOutcome(requester, "done"),
    ]
    console, buf = _console()
    render_run_summary(outcomes, console)
    rows = buf.getvalue().splitlines()[1:]
    # The dragged row's 2-cell indent counts into the id budget, so idw is 6.
    assert rows == ["✓ mmdc    installed", "✓   node  installed"]


def test_outcome_row_text_folds_a_long_detail_within_the_row_budget() -> None:
    row = PlanRow("a" * 24, Disposition.INSTALL, "not installed", health=Health.MISSING)
    outcome = RowOutcome(row, "crashed", detail="RuntimeError: " + "x" * 300)
    text = outcome_row_text(outcome, 24, 78)
    assert all(cell_len(line) <= 78 for line in text.plain.splitlines())
    assert len(text.plain.splitlines()) > 1


def test_outcome_row_text_renders_markup_and_control_characters_literally() -> None:
    row = PlanRow("pony", Disposition.INSTALL, "not installed", health=Health.MISSING)
    outcome = RowOutcome(row, "crashed", detail="[red]x[/] \x1b[31mboom")
    text = outcome_row_text(outcome, 4, 78)
    assert "[red]x[/]" in text.plain
    assert "\x1b" not in text.plain
    colored = io.StringIO()
    Console(file=colored, width=100, force_terminal=True).print(text, markup=False)
    assert "\x1b[31mx\x1b[0m" not in colored.getvalue()


@pytest.mark.parametrize(
    ("result", "detail", "errors", "blocked_by", "expected", "mark"),
    [
        ("failed", "", (RuntimeError("last error"),), (), "failed — last error", "✖"),
        ("failed", "", (), (), "failed — no method succeeded", "✖"),
        ("mismatch", "", (), (), "checksum mismatch", "✖"),
        (
            "dependency_failed",
            "",
            (),
            ("node", "java"),
            "dependency failed — node, java",
            "○",
        ),
        (
            "dependency_failed",
            "",
            (),
            (),
            "dependency failed — an earlier failure",
            "○",
        ),
        ("not_attempted", "worker stopped", (), (), "not attempted", "○"),
        ("crashed", "RuntimeError: boom", (), (), "crashed — RuntimeError: boom", "✖"),
        ("manual", "", (), (), "manual — see the setup steps in the log", "○"),
        ("skipped", "", (), (), "skipped — already current", "✓"),
        (
            "skipped",
            "became present before it ran",
            (),
            (),
            "skipped — became present before it ran",
            "✓",
        ),
        ("blocked", "", (), (), "blocked — plan reason", "○"),
        (
            "blocked",
            "no install method for this platform",
            (),
            (),
            "blocked — no install method for this platform",
            "○",
        ),
    ],
)
def test_outcome_row_text_per_result(
    result: Result,
    detail: str,
    errors: tuple[Exception, ...],
    blocked_by: tuple[str, ...],
    expected: str,
    mark: str,
) -> None:
    skipped = result == "skipped"
    row = PlanRow(
        "tool",
        Disposition.INSTALL,
        "already current" if skipped else "plan reason",
        health=Health.OK if skipped else Health.MISSING,
    )
    install = (
        InstallOutcome("tool", "failed", errors=errors, blocked_by=blocked_by)
        if result in {"failed", "dependency_failed"}
        else None
    )
    outcome = RowOutcome(row, result, install=install, detail=detail)
    text = outcome_row_text(outcome, 4, 78).plain
    assert text.startswith(f"{mark} tool  ")
    assert text.split("  ", 1)[1] == expected


def test_outcome_row_error_text_is_sanitized_and_literal() -> None:
    row = PlanRow("tool", Disposition.INSTALL, "plan reason", health=Health.MISSING)
    outcome = RowOutcome(
        row,
        "failed",
        install=InstallOutcome("tool", "failed", errors=(RuntimeError("\x1b[31m[red]x[/]"),)),
    )
    text = outcome_row_text(outcome, 4, 78).plain
    assert "\x1b" not in text
    assert "[red]x[/]" in text
    console = io.StringIO()
    Console(file=console, width=80, force_terminal=True).print(
        outcome_row_text(outcome, 4, 78), markup=False
    )
    assert "\x1b[31mx\x1b[0m" not in console.getvalue()


def test_running_row_text_shows_the_in_flight_mark() -> None:
    row = PlanRow("tool", Disposition.UPDATE, "new version", health=Health.OUTDATED)
    text = running_row_text(row, 4, 78)
    assert text.plain.startswith("> tool  will update")


def test_render_run_summary_mixed_run_counts_every_category() -> None:
    outcomes = [
        _done("a", Disposition.INSTALL),
        RowOutcome(
            PlanRow("b", Disposition.UPDATE, "reason", health=Health.OUTDATED),
            "failed",
            update=None,
            detail="error",
        ),
        RowOutcome(PlanRow("c", Disposition.REPAIR, "reason", health=Health.BROKEN), "mismatch"),
        RowOutcome(
            PlanRow("d", Disposition.RECONFIGURE, "reason", health=Health.MISCONFIGURED),
            "dependency_failed",
        ),
        RowOutcome(
            PlanRow("e", Disposition.REINSTALL, "reason", health=Health.OK), "not_attempted"
        ),
        RowOutcome(
            PlanRow("f", Disposition.INSTALL, "reason", health=Health.MISSING),
            "crashed",
            detail="RuntimeError: boom",
        ),
        RowOutcome(PlanRow("g", Disposition.SKIP, "reason", health=Health.OK), "skipped"),
        RowOutcome(
            PlanRow("h", Disposition.BLOCKED, "reason", health=Health.UNAVAILABLE), "blocked"
        ),
        RowOutcome(PlanRow("i", Disposition.INSTALL, "reason", health=Health.MISSING), "manual"),
    ]
    console, buf = _console()
    render_run_summary(outcomes, console)
    assert buf.getvalue().splitlines()[0] == (
        "Summary — 1 installed, 1 skipped, 1 blocked, 1 manual, 1 failed, "
        "1 checksum mismatch, 1 dependency failed, 1 not attempted, 1 crashed"
    )
