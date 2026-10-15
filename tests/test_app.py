import io
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypedDict

import pytest
from rich.console import Console

from installer import daemon, shellrc
from installer.app import run_guard, run_wizard
from installer.checksums import ChecksumMismatch
from installer.cli import Options
from installer.diskusage import DiskPressure
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import DaemonState
from installer.model import Method, Tool
from installer.platform import Platform
from installer.policy import Policy, daemon_policy
from installer.post_install import ConfirmSensitiveAction
from installer.run import CommandError, Runner
from installer.selection import Choice
from installer.session import Install, MismatchChoice, SensitiveInstall, Summary
from installer.tweaks import TweakBundle
from installer.uninstall import SweepResult
from installer.versions import TagResolver


def _tool(tool_id: str, category: str, *, requires: tuple[str, ...] = ()) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
        requires=requires,
    )


def _catalog() -> list[Tool]:
    return [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, no_color=True), buf


_BATCH_QUESTION = "Install the selected tools?"


class FakePrompter:
    def __init__(
        self,
        categories: list[str],
        tools: list[str],
        confirm: bool,
        *,
        sensitive_confirm: bool | None = None,
    ) -> None:
        self._categories = categories
        self._tools = tools
        self._confirm = confirm
        self._sensitive_confirm = confirm if sensitive_confirm is None else sensitive_confirm
        self.confirmed = 0
        self.questions: list[str] = []

    def select_categories(self, choices: list[Choice]) -> list[str]:
        return self._categories

    def select_tools(self, choices: list[Choice]) -> list[str]:
        return self._tools

    def confirm(self, message: str) -> bool:
        self.confirmed += 1
        self.questions.append(message)
        if message == _BATCH_QUESTION:
            return self._confirm
        return self._sensitive_confirm


def _recording_install() -> tuple[list[str], SensitiveInstall]:
    installed: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        installed.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    return installed, install


def _never_installed(tool: Tool) -> bool:
    return False


def _runner(cmd: list[str]) -> None:
    return None


def _resolve_tag(repo: str) -> str:
    return "1.0.0"


def test_all_flag_installs_every_tool_without_prompting():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["rg", "fd", "jq"]
    assert summary == Summary(installed=("rg", "fd", "jq"), already=(), failed=(), no_method=())
    assert prompter.confirmed == 0


def test_failed_install_surfaces_in_summary_without_crashing():
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        return InstallOutcome(tool.id, "failed")

    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        [_tool("rg", "search")],
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert summary is not None
    assert summary.failed == ("rg",)
    assert summary.installed == ()


def test_run_wizard_reports_a_skipped_dependent_with_its_reason() -> None:
    called: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        called.append(tool.id)
        if tool.id == "sdkman":
            return InstallOutcome(tool.id, "failed")
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    console, buf = _console()
    summary = run_wizard(
        [_tool("sdkman", "pkg-mgr"), _tool("java", "dev", requires=("sdkman",))],
        _platform(),
        FakePrompter(categories=[], tools=[], confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert summary is not None
    assert summary.dependency_failed == ("java",)
    assert "java skipped — dependency failed: sdkman" in buf.getvalue()
    assert called == ["sdkman"]


def test_categories_flag_filters_tools():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=("data",), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["jq"]


def test_interactive_path_selects_then_installs():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=["search"], tools=["fd"], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["fd"]
    assert summary is not None
    assert summary.installed == ("fd",)
    assert prompter.confirmed == 1


def test_declining_confirmation_installs_nothing():
    installed, install = _recording_install()
    prompter = FakePrompter(categories=["search"], tools=["fd"], confirm=False)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert installed == []
    assert summary is None  # None signals an aborted run, distinct from an empty Summary
    assert prompter.confirmed == 1


def test_configure_path_writes_myshellrc_and_wires_all_rcs(tmp_path: Path):
    from installer.app import configure_path

    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# zsh\n")
    bashrc = tmp_path / ".bashrc"  # absent -> MUST be created and wired
    console, _buf = _console()

    configure_path(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[zshrc, bashrc],
    )

    assert myshellrc.exists()
    assert "# >>> tools-installer path >>>" in myshellrc.read_text()
    assert zshrc.exists() and "tools-installer source" in zshrc.read_text()
    # Both rc files are always wired; an absent one is created.
    assert bashrc.exists() and "tools-installer source" in bashrc.read_text()
    assert "# zsh" in zshrc.read_text()  # existing content preserved


def test_run_doctor_reports_problems_and_never_writes(tmp_path: Path):
    from installer.app import run_doctor

    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value="/usr/bin",
        exists=lambda _p: False,  # default dir absent -> missing + broken
    )

    assert bin_dir in report.missing
    assert bin_dir in report.broken
    assert "make fix" in buf.getvalue()
    assert "github.com" not in buf.getvalue()
    assert list(tmp_path.iterdir()) == []  # diagnosis only: nothing written


def test_run_doctor_healthy_says_healthy(tmp_path: Path):
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    console, buf = _console()

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
    )

    assert report.missing == () and report.broken == () and report.duplicated == ()
    assert "healthy" in buf.getvalue().lower()


def test_run_doctor_names_the_injected_rc_writer() -> None:
    from installer.app import run_doctor

    console, buf = _console()
    run_doctor(
        [],
        console,
        platform=_platform(),
        default_bin_dir=Path("/x/bin"),
        path_value="/x/bin:/x/bin",
        exists=lambda _p: True,
        duplicate_writers=lambda _report: {Path("/x/bin"): (Path("/tmp/fake/.bashrc"),)},
    )
    assert "/tmp/fake/.bashrc" in buf.getvalue()


def test_writer_scan_skipped_when_nothing_is_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from installer.app import duplicate_path_writers
    from installer.doctor import DoctorReport

    calls: list[object] = []

    def counting(*_args: object, **_kwargs: object) -> dict[Path, tuple[Path, ...]]:
        calls.append(True)
        return {}

    monkeypatch.setattr("installer.app.path_writer_lines_for", counting)
    report = DoctorReport(missing=(), broken=(), duplicated=())
    assert duplicate_path_writers(report) == {}
    assert calls == []


def test_writer_scan_reads_only_the_given_files(tmp_path: Path) -> None:
    from installer.app import duplicate_path_writers
    from installer.doctor import DoctorReport

    rc = tmp_path / ".bashrc"
    rc.write_text('export PATH="/x/bin:$PATH"\n')
    other = tmp_path / ".profile"
    other.write_text('export PATH="/x/bin:$PATH"\n')
    report = DoctorReport(missing=(), broken=(), duplicated=(Path("/x/bin"),))
    writers = duplicate_path_writers(report, rc_paths=[rc], env={"HOME": str(tmp_path)})
    assert writers == {Path("/x/bin"): (rc,)}


def test_configure_path_honors_exists_filter(tmp_path: Path):
    from installer.app import configure_path

    declared = tmp_path / "tools" / "bin"  # never created on disk
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(Method(kind="github_release", params={"member": "fd", "bin_dir": str(declared)}),),
    )
    myshellrc = tmp_path / ".myshellrc"
    console, _buf = _console()

    configure_path(
        [tool],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[],
        exists=lambda _p: False,
    )

    text = myshellrc.read_text()
    assert str(declared) not in text  # not on disk -> not managed
    assert str(tmp_path / ".local" / "bin") in text  # default always managed


def test_run_uninstall_removes_when_confirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from installer.app import run_uninstall
    from installer.shellrc import write_myshellrc

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("bin")
    (bin_dir / "fd").symlink_to(opt / "fd")
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),
        ),
    )
    console, _buf = _console()
    removed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert set(removed) == {opt, bin_dir / "fd"}
    assert not opt.exists()
    assert not (bin_dir / "fd").is_symlink()  # the bin symlink is unlinked on disk
    assert "tools-installer path" not in myshellrc.read_text()


def test_run_uninstall_aborts_when_declined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from installer.app import run_uninstall

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (bin_dir / "fd").symlink_to(opt)
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),
        ),
    )
    console, _buf = _console()
    removed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=lambda _m: False,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert removed == []
    assert opt.exists()  # nothing removed


def test_configure_path_centralized_writes_myshellrc_and_sources_both(tmp_path: Path):
    from installer.app import configure_path
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc, brc = tmp_path / ".zshrc", tmp_path / ".bashrc"
    configure_path(
        [],
        console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[zrc, brc],
    )  # default link_mode="centralized"
    assert "# >>> tools-installer path >>>" in myshellrc.read_text()
    assert str(myshellrc) in zrc.read_text()
    assert str(myshellrc) in brc.read_text()


def test_configure_path_single_sources_only_the_given_rc(tmp_path: Path):
    from installer.app import configure_path
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc = tmp_path / ".zshrc"
    configure_path(
        [],
        console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[zrc],
        link_mode="single",
    )
    assert myshellrc.exists()
    assert str(myshellrc) in zrc.read_text()


def test_configure_path_split_inlines_block_and_skips_myshellrc(tmp_path: Path):
    from installer.app import configure_path
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc, brc = tmp_path / ".zshrc", tmp_path / ".bashrc"
    configure_path(
        [],
        console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[zrc, brc],
        link_mode="split",
    )
    assert not myshellrc.exists()  # no indirection file in split mode
    for rc in (zrc, brc):
        text = rc.read_text()
        assert "# >>> tools-installer path >>>" in text  # block written inline
        assert str(myshellrc) not in text  # and no source line


def test_configure_path_consolidates_a_generic_shellrc(tmp_path: Path) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    console, buffer = _console()

    outcome = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[],
    )

    assert outcome is not None and outcome.status == "consolidated"
    consolidated = myshellrc.read_text()
    assert "FOREIGN_CONTENT=present" in consolidated
    assert "# >>> tools-installer consolidated shellrc >>>" in consolidated
    assert consolidated.count("# >>> tools-installer path >>>") == 1
    assert shellrc_path.read_text().count("# >>> tools-installer shellrc stub >>>") == 1
    assert "consolidated" in buffer.getvalue().lower()


def test_configure_path_writes_the_managed_block_after_the_consolidated_content(
    tmp_path: Path,
) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[],
    )

    result = myshellrc.read_text()
    assert result.index("# >>> tools-installer consolidated shellrc >>>") < result.index(
        "# >>> tools-installer path >>>"
    )


def test_configure_path_skips_consolidation_in_split_mode(tmp_path: Path) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    original = "export FOREIGN_CONTENT=present\n"
    shellrc_path.write_text(original)
    buffer = io.StringIO()
    console = Console(file=buffer, width=1000, no_color=True)

    outcome = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[],
        link_mode="split",
    )

    assert outcome is None
    assert shellrc_path.read_text() == original
    assert not myshellrc.exists()
    assert "consolid" not in buffer.getvalue().lower()


def test_configure_path_says_nothing_when_there_is_no_generic_shellrc(tmp_path: Path) -> None:
    from installer.app import configure_path

    myshellrc = tmp_path / ".myshellrc"
    buffer = io.StringIO()
    console = Console(file=buffer, width=1000, no_color=True)

    outcome = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=tmp_path / ".shellrc",
        rc_paths=[],
    )

    assert outcome is not None and outcome.status == "absent"
    assert buffer.getvalue() == (
        f"PATH configured in {myshellrc} (restart your shell or source it).\n"
    )


def test_configure_path_without_a_shellrc_path_argument_is_unchanged(tmp_path: Path) -> None:
    from installer.app import configure_path

    myshellrc = tmp_path / ".myshellrc"
    buffer = io.StringIO()
    console = Console(file=buffer, width=1000, no_color=True)

    outcome = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[],
    )

    assert outcome is None
    assert buffer.getvalue() == (
        f"PATH configured in {myshellrc} (restart your shell or source it).\n"
    )


def test_an_rc_that_already_sources_shellrc_does_not_also_get_our_source_block(
    tmp_path: Path,
) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    original = f'export KEEP=1\nsource "{shellrc_path}"\n'
    rc_path.write_text(original)
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    assert rc_path.read_text() == original
    assert "tools-installer source" not in rc_path.read_text()


def test_a_stale_source_block_is_removed_when_the_rc_already_reaches_the_stub(
    tmp_path: Path,
) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    original = f'export KEEP=1\nsource "{shellrc_path}"\n'
    rc_path.write_text(original)
    shellrc.ensure_source(rc_path, myshellrc)
    seeded = rc_path.read_text()
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    assert "tools-installer source" not in rc_path.read_text()
    assert original in rc_path.read_text()
    assert "export KEEP=1" in seeded


def test_an_rc_that_does_not_source_shellrc_still_gets_our_source_block(tmp_path: Path) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    rc_path.write_text("export KEEP=1\n")
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    assert rc_path.read_text().count("# >>> tools-installer source >>>") == 1


def test_an_rc_with_an_unresolvable_source_command_still_gets_our_block_and_a_diagnostic(
    tmp_path: Path,
) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    rc_path.write_text('eval "$(brew shellenv)"\n. "$ZDOTDIR/extra"\n')
    buffer = io.StringIO()
    console = Console(file=buffer, width=1000, no_color=True)
    assert shellrc.sources_file(rc_path.read_text(), shellrc_path) == "unprovable"

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    assert rc_path.read_text().count("# >>> tools-installer source >>>") == 1
    assert str(rc_path) in buffer.getvalue()
    assert "source command this tool could not resolve" in " ".join(buffer.getvalue().split())


@pytest.mark.parametrize("verdict", ["yes", "no", "unprovable"])
def test_the_single_route_rule_handles_every_sources_file_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verdict: str
) -> None:
    from installer import app as app_module
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    rc_path.write_text("export KEEP=1\n")

    def fixed_verdict(_text: str, _target: Path) -> str:
        return verdict

    monkeypatch.setattr(app_module.shellrc, "sources_file", fixed_verdict)
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    has_source_block = "# >>> tools-installer source >>>" in rc_path.read_text()
    assert has_source_block is (verdict != "yes")


def test_the_single_route_rule_only_applies_once_the_stub_exists(tmp_path: Path) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    rc_path.write_text(f'source "{shellrc_path}"\n')
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    assert "# >>> tools-installer source >>>" in rc_path.read_text()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")
def test_a_consolidated_bashrc_runs_the_canonical_file_once_per_startup(tmp_path: Path) -> None:
    from installer.app import configure_path

    bash_path = shutil.which("bash")
    assert bash_path is not None
    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    bashrc = tmp_path / ".bashrc"
    managed_dir = tmp_path / ".local" / "bin"
    shellrc_path.write_text(
        "__SHELLRC_RUNS=$((${__SHELLRC_RUNS:-0}+1))\nexport __COPIED_FORWARD=yes\n"
    )
    bashrc.write_text(f'source "{shellrc_path}"\n')
    console, _buffer = _console()

    configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=managed_dir,
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[bashrc],
    )

    completed = subprocess.run(
        [
            bash_path,
            "--noprofile",
            "--norc",
            "-c",
            'source "$HOME/.bashrc"; '
            'printf \'%s\\n\' "$__SHELLRC_RUNS" "$PATH" "$__COPIED_FORWARD"',
        ],
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert lines[0] == "1"
    assert lines[2] == "yes"
    assert lines[1].split(":").count(str(managed_dir)) == 1


def test_configure_path_reports_a_consolidation_refusal(tmp_path: Path) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    rc_path = tmp_path / ".bashrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    myshellrc.write_text(f'source "{shellrc_path}"\n')
    before = shellrc_path.read_bytes()
    buffer = io.StringIO()
    console = Console(file=buffer, width=1000, no_color=True)

    outcome = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[rc_path],
    )

    assert outcome is not None and outcome.status == "refused"
    assert outcome.reason is not None
    assert outcome.reason in " ".join(buffer.getvalue().split())
    assert shellrc_path.read_bytes() == before
    assert "# >>> tools-installer path >>>" in myshellrc.read_text()


def test_configure_path_returns_the_consolidation_outcome(tmp_path: Path) -> None:
    from installer.app import configure_path

    shellrc_path = tmp_path / ".shellrc"
    myshellrc = tmp_path / ".myshellrc"
    shellrc_path.write_text("export FOREIGN_CONTENT=present\n")
    myshellrc.write_text(f'source "{shellrc_path}"\n')
    console, _buffer = _console()

    refused = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=myshellrc,
        shellrc_path=shellrc_path,
        rc_paths=[],
    )
    split = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin2",
        myshellrc_path=tmp_path / ".myshellrc2",
        shellrc_path=shellrc_path,
        rc_paths=[],
        link_mode="split",
    )
    omitted = configure_path(
        [],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin3",
        myshellrc_path=tmp_path / ".myshellrc3",
        rc_paths=[],
    )

    assert refused is not None and refused.status == "refused"
    assert refused.reason is not None
    assert split is None
    assert omitted is None


def test_consolidation_refusal_message_is_none_for_every_non_refusal_outcome() -> None:
    from installer.app import consolidation_refusal_message

    assert consolidation_refusal_message(None) is None
    for status in ("absent", "already", "consolidated"):
        assert consolidation_refusal_message(shellrc.ShellrcConsolidation(status=status)) is None


def test_consolidation_refusal_message_includes_the_mechanism_reason() -> None:
    from installer.app import consolidation_refusal_message

    outcome = shellrc.ShellrcConsolidation(status="refused", reason="the exact mechanism reason")

    message = consolidation_refusal_message(outcome)

    assert message is not None
    assert "managed path block was written" in message.lower()
    assert "~/.shellrc consolidation was refused" in message
    assert "the exact mechanism reason" in message


def test_clean_rc_duplicates_removes_after_confirm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".zshrc"
    rc.write_text(
        'export BUN_INSTALL="$HOME/.bun"\nexport PATH="$BUN_INSTALL/bin:$PATH"\nalias ll="ls -la"\n'
    )
    console, _buf = _console()
    removed = clean_rc_duplicates(
        [rc],
        {tmp_path / ".bun" / "bin"},
        {"HOME": str(tmp_path)},
        console,
        confirm=lambda _m: True,
    )
    assert removed == {rc: ['export PATH="$BUN_INSTALL/bin:$PATH"']}
    text = rc.read_text()
    assert 'export PATH="$BUN_INSTALL/bin:$PATH"' not in text
    assert 'export BUN_INSTALL="$HOME/.bun"' in text  # assignment kept
    assert 'alias ll="ls -la"' in text  # unrelated content kept


def test_clean_rc_duplicates_declined_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".zshrc"
    original = 'export PATH="$HOME/.bun/bin:$PATH"\n'
    rc.write_text(original)
    console, _buf = _console()
    removed = clean_rc_duplicates(
        [rc],
        {tmp_path / ".bun" / "bin"},
        {"HOME": str(tmp_path)},
        console,
        confirm=lambda _m: False,
    )
    assert removed == {}
    assert rc.read_text() == original


def test_clean_rc_duplicates_nothing_to_do_skips_confirm(tmp_path: Path):
    from installer.app import clean_rc_duplicates

    rc = tmp_path / ".zshrc"
    rc.write_text('alias ll="ls -la"\n')
    console, _buf = _console()

    def fail_confirm(_message: str) -> bool:
        raise AssertionError("confirm must not be called when there is nothing to remove")

    removed = clean_rc_duplicates(
        [rc], {tmp_path / ".bun" / "bin"}, {}, console, confirm=fail_confirm
    )
    assert removed == {}


def test_clean_rc_duplicates_skips_absent_rc_files(tmp_path: Path):
    from installer.app import clean_rc_duplicates

    missing = tmp_path / ".bashrc"  # never created
    console, _buf = _console()
    removed = clean_rc_duplicates(
        [missing], {tmp_path / ".bun" / "bin"}, {}, console, confirm=lambda _m: True
    )
    assert removed == {}


def _dup_rc(tmp_path: Path, name: str = ".zshrc") -> tuple[Path, str]:
    rc = tmp_path / name
    original = 'export BUN_INSTALL="$HOME/.bun"\nexport PATH="$BUN_INSTALL/bin:$PATH"\n'
    rc.write_text(original)
    return rc, original


def test_clean_rc_duplicates_refuses_a_file_edited_between_preview_and_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """D-06: the confirm recheck compares bytes; a file edited while the user
    reads the prompt is refused, left byte-identical, and absent from the
    returned removed-lines dict."""
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc, original = _dup_rc(tmp_path)
    console, buf = _console()

    def edit_then_confirm(_message: str) -> bool:
        rc.write_text(original + 'export PATH="/usr/local/bin:$PATH"\n')
        return True

    removed = clean_rc_duplicates(
        [rc],
        {tmp_path / ".bun" / "bin"},
        {"HOME": str(tmp_path)},
        console,
        confirm=edit_then_confirm,
    )
    assert rc.read_text() == original + 'export PATH="/usr/local/bin:$PATH"\n'
    assert rc not in removed
    assert "changed since the preview" in " ".join(buf.getvalue().split())
    assert "left untouched" in " ".join(buf.getvalue().split())


def test_clean_rc_duplicates_treats_a_trailing_newline_change_as_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc, original = _dup_rc(tmp_path)
    console, _buf = _console()

    def drop_final_newline(_message: str) -> bool:
        rc.write_bytes(original[:-1].encode())
        return True

    removed = clean_rc_duplicates(
        [rc],
        {tmp_path / ".bun" / "bin"},
        {"HOME": str(tmp_path)},
        console,
        confirm=drop_final_newline,
    )
    assert rc.read_bytes() == original[:-1].encode()
    assert rc not in removed


def test_clean_rc_duplicates_strips_an_unchanged_file_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc, original = _dup_rc(tmp_path)
    console, _buf = _console()

    def boom(src: object, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError, match="disk full"):
        clean_rc_duplicates(
            [rc],
            {tmp_path / ".bun" / "bin"},
            {"HOME": str(tmp_path)},
            console,
            confirm=lambda _m: True,
        )
    assert rc.read_bytes() == original.encode()
    assert list(tmp_path.glob("*.tools-installer.tmp")) == []


def test_clean_rc_duplicates_writes_through_a_symlinked_rc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "zshrc"
    _dup_rc(dotfiles, "zshrc")
    rc = tmp_path / ".zshrc"
    rc.symlink_to(target)
    console, _buf = _console()
    removed = clean_rc_duplicates(
        [rc],
        {tmp_path / ".bun" / "bin"},
        {"HOME": str(tmp_path)},
        console,
        confirm=lambda _m: True,
    )
    assert rc.is_symlink()
    stripped = target.read_text()
    assert 'export PATH="$BUN_INSTALL/bin:$PATH"' not in stripped
    assert 'export BUN_INSTALL="$HOME/.bun"' in stripped
    assert rc in removed


def test_clean_rc_duplicates_refuses_a_file_deleted_since_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Review 17-06 LOW: a file deleted between preview and confirm must be
    treated as changed (never recreated); the other files still get stripped."""
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    first, _ = _dup_rc(tmp_path, ".zshrc")
    second, _ = _dup_rc(tmp_path, ".bashrc")
    console, buf = _console()

    def delete_then_confirm(_message: str) -> bool:
        first.unlink()
        return True

    removed = clean_rc_duplicates(
        [first, second],
        {tmp_path / ".bun" / "bin"},
        {"HOME": str(tmp_path)},
        console,
        confirm=delete_then_confirm,
    )
    assert not first.exists()  # not recreated
    assert first not in removed
    assert "changed since the preview" in " ".join(buf.getvalue().split())
    assert second in removed
    assert 'export PATH="$BUN_INSTALL/bin:$PATH"' not in second.read_text()


def test_run_uninstall_nothing_to_remove_skips_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from installer.app import run_uninstall

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(kind="github_release", params={"repo": "a/fd", "asset": "x", "member": "fd"}),
        ),
    )
    console, _buf = _console()

    def fail_confirm(_message: str) -> bool:
        raise AssertionError("confirm must not be called when there is nothing to remove")

    removed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=fail_confirm,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert removed == []


def _mismatching_install() -> tuple[list[str], SensitiveInstall]:
    attempts: list[str] = []
    exc = ChecksumMismatch("a.tar.gz", "0" * 64, "f" * 64)

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        attempts.append(checksum_policy)
        return InstallOutcome(
            tool.id, "checksum-mismatch", method_kind="github_release", errors=(exc,)
        )

    return attempts, install


def test_wizard_consults_on_mismatch_when_interactive():
    attempts, install = _mismatching_install()
    asked: list[str] = []

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "skip"

    console, _buf = _console()
    summary = run_wizard(
        [_tool("rg", "search")],
        _platform(),
        FakePrompter(categories=[], tools=[], confirm=True),
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        on_mismatch=on_mismatch,
    )
    assert asked == ["rg"]
    assert attempts == ["fail"]  # one install call, default policy
    assert summary is not None
    assert summary.mismatched == ("rg",)


def test_wizard_suppresses_on_mismatch_under_yes():
    attempts, install = _mismatching_install()
    asked: list[str] = []

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "retry"

    console, _buf = _console()
    summary = run_wizard(
        [_tool("rg", "search")],
        _platform(),
        FakePrompter(categories=[], tools=[], confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        on_mismatch=on_mismatch,
    )
    assert asked == []  # unattended: never prompt, hard-fail stands
    assert summary is not None
    assert summary.mismatched == ("rg",)
    assert attempts == ["fail"]


def test_run_wizard_threads_category_blurbs_into_choices() -> None:
    seen: list[list[Choice]] = []

    class RecordingPrompter:
        def select_categories(self, choices: list[Choice]) -> list[str]:
            seen.append(choices)
            return []

        def select_tools(self, choices: list[Choice]) -> list[str]:
            return []

        def confirm(self, message: str) -> bool:
            return True

    console, _buf = _console()
    run_wizard(
        [_tool("rg", "search")],
        _platform(),
        RecordingPrompter(),
        console,
        Options(all=False, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=_recording_install()[1],
        installed=_never_installed,
        category_blurbs={"search": "Find files and code at speed"},
    )
    assert seen[0][0].description == "Find files and code at speed — rg"


def test_catalog_seam_replaces_two_step_selection():
    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=["IGNORED"], tools=["IGNORED"], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=lambda tools: ["jq"],
    )
    assert installed_ids == ["jq"]
    assert summary is not None
    assert prompter.confirmed == 1  # the confirm step still runs


def test_catalog_seam_abort_returns_none_without_confirm():
    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    summary = run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=lambda tools: None,
    )
    assert summary is None
    assert installed_ids == []
    assert prompter.confirmed == 0


def test_all_flag_bypasses_catalog_seam():
    def boom(tools: list[Tool]) -> list[str] | None:
        raise AssertionError("select_catalog must not be called under --all")

    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=boom,
    )
    assert installed_ids == ["rg", "fd", "jq"]


def test_categories_flag_bypasses_catalog_seam():
    def boom(tools: list[Tool]) -> list[str] | None:
        raise AssertionError("select_catalog must not be called under --categories")

    installed_ids, install = _recording_install()
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, _buf = _console()
    run_wizard(
        _catalog(),
        _platform(),
        prompter,
        console,
        Options(all=False, categories=("data",), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
        select_catalog=boom,
    )
    assert installed_ids == ["jq"]


def test_run_guard_install_writes_shims_and_aliases_and_returns_true(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    rc = tmp_path / ".myshellrc"
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    acted = run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[rc],
        path_value=f"{shim_dir}:/usr/bin",
        console=console,
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    assert acted is True
    assert (shim_dir / "pip").exists()
    assert (shim_dir / "npx").exists()
    assert not (shim_dir / "pnpm").exists()
    assert "tools-installer ban" in rc.read_text()
    assert "Installing the pip/npm ban" in buf.getvalue()


def test_run_guard_reports_the_redirect_degradation_not_just_path_order(tmp_path: Path):
    # A bare machine (no pnpm, no volta) degrades npx and npm to hard blocks.
    # The per-name action lines never say so, and the PATH order here is sound,
    # so without guard_state's composition the CLI user is told nothing.
    shim_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[tmp_path / ".myshellrc"],
        path_value=f"{shim_dir}:/usr/bin",
        console=console,
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    output = buf.getvalue()
    assert "hard-blocked" in output
    assert "volta" in output


def test_run_guard_states_the_volta_tradeoff_before_asking(tmp_path: Path):
    # The confirm prompt is the CLI's consent moment: it must say that
    # installing wraps npm/pnpm and gives up pnpm's gated postinstalls.
    shim_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(file=buf, width=100, no_color=True)
    asked: list[str] = []

    def confirm(message: str) -> bool:
        asked.append(buf.getvalue())
        return False

    run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[tmp_path / ".myshellrc"],
        path_value="",
        console=console,
        confirm=confirm,
        which=lambda _n: None,
    )
    assert len(asked) == 1
    shown = asked[0]
    assert "volta install" in shown
    assert "install scripts" in shown


def test_run_guard_remove_does_not_repeat_the_install_tradeoff(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(file=buf, width=100, no_color=True)
    run_guard(
        remove=True,
        shim_dir=shim_dir,
        rc_paths=[tmp_path / ".myshellrc"],
        path_value="",
        console=console,
        confirm=lambda _m: False,
        which=lambda _n: None,
    )
    assert "install scripts" not in buf.getvalue()


def test_run_guard_declined_does_nothing(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    acted = run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[tmp_path / ".myshellrc"],
        path_value="",
        console=console,
        confirm=lambda _m: False,
        which=lambda _n: None,
    )
    assert acted is False
    assert not shim_dir.exists()


def test_run_guard_remove_strips_shims_and_aliases(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    rc = tmp_path / ".myshellrc"
    console = Console(file=io.StringIO(), width=100)
    run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[rc],
        path_value=f"{shim_dir}",
        console=console,
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    run_guard(
        remove=True,
        shim_dir=shim_dir,
        rc_paths=[rc],
        path_value=f"{shim_dir}",
        console=console,
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    assert not (shim_dir / "pip").exists()
    assert not (shim_dir / "npx").exists()
    assert "tools-installer ban" not in rc.read_text()


def test_run_guard_shim_dir_matches_ban_policy_apply(tmp_path: Path) -> None:
    from installer.policy import ban_policy

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)
    policy_dir = tmp_path / "policy-bin"
    guard_dir = tmp_path / "guard-bin"
    path_value = f"{policy_dir}:{real_dir}"
    ban_policy(
        shim_dir=policy_dir,
        apply_rc_paths=[tmp_path / "policy.rc"],
        remove_rc_paths=[tmp_path / "policy.rc"],
        path_value=path_value,
        which=lambda _n: None,
    ).apply()
    run_guard(
        remove=False,
        shim_dir=guard_dir,
        rc_paths=[tmp_path / "guard.rc"],
        path_value=path_value,
        console=Console(file=io.StringIO(), width=100),
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    names = sorted(path.name for path in policy_dir.iterdir())
    assert names == sorted(path.name for path in guard_dir.iterdir())
    for name in names:
        assert (policy_dir / name).read_text() == (guard_dir / name).read_text()


def test_run_guard_with_volta_matches_ban_policy_five_shims(tmp_path: Path) -> None:
    from installer.guards import REDIRECT_SENTINEL, SHIM_SENTINEL, guard_status
    from installer.policy import ban_policy

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    for name in ("volta", "pnpm"):
        binary = real_dir / name
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
    policy_dir = tmp_path / "policy-bin"
    guard_dir = tmp_path / "guard-bin"
    ban_policy(
        shim_dir=policy_dir,
        apply_rc_paths=[tmp_path / "policy.rc"],
        remove_rc_paths=[tmp_path / "policy.rc"],
        path_value=f"{policy_dir}:{real_dir}",
        which=lambda _n: None,
    ).apply()
    run_guard(
        remove=False,
        shim_dir=guard_dir,
        rc_paths=[tmp_path / "guard.rc"],
        path_value=f"{guard_dir}:{real_dir}",
        console=Console(file=io.StringIO(), width=100),
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    for directory in (policy_dir, guard_dir):
        status = guard_status(directory)
        assert status == {"npm": True, "pip": True, "pip3": True, "npx": True, "pnpm": True}
        assert REDIRECT_SENTINEL in (directory / "npm").read_text()
        assert REDIRECT_SENTINEL in (directory / "pnpm").read_text()
        assert REDIRECT_SENTINEL in (directory / "npx").read_text()
        assert SHIM_SENTINEL in (directory / "pip").read_text()
        assert SHIM_SENTINEL in (directory / "pip3").read_text()
    names = sorted(path.name for path in policy_dir.iterdir())
    assert names == sorted(path.name for path in guard_dir.iterdir())
    for name in names:
        assert (policy_dir / name).read_text() == (guard_dir / name).read_text()


def test_guard_state_folds_redirect_warning(tmp_path: Path) -> None:
    from installer.app import guard_state
    from installer.guards import shim_script

    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    (shim_dir / "npx").write_text(shim_script("npx"))
    result = guard_state(shim_dir, str(shim_dir), lambda _n: None)
    assert isinstance(result, tuple) and len(result) == 2
    status, warning = result
    assert isinstance(status, dict)
    assert all(isinstance(value, bool) for value in status.values())
    assert warning is not None
    assert "npx" in warning
    assert "pnpm" in warning


def test_guard_state_joins_path_and_redirect_warnings(tmp_path: Path) -> None:
    from installer.app import guard_state
    from installer.guards import install_shims

    shim_dir = tmp_path / "bin"
    install_shims(shim_dir)
    result = guard_state(
        shim_dir,
        f"/usr/bin:{shim_dir}",
        lambda name: "/usr/bin/pip" if name == "pip" else None,
    )
    assert isinstance(result, tuple) and len(result) == 2
    _status, warning = result
    assert warning is not None
    assert "/usr/bin/pip" in warning
    assert "npx" in warning
    assert "pnpm" in warning


def test_run_doctor_reports_active_ban(tmp_path: Path):
    from installer.app import run_doctor
    from installer.guards import install_shims

    shim_dir = tmp_path / ".local" / "bin"
    install_shims(shim_dir)
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    run_doctor(
        [],
        console,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=shim_dir,
        path_value=str(shim_dir),
        exists=lambda _p: True,
        which=lambda name: str(shim_dir / name),
    )
    out = buf.getvalue()
    assert "Package manager guards active" in out
    assert "pip: blocked" in out


def _mmdc_tool() -> Tool:
    return Tool(
        id="mmdc",
        name="mmdc",
        category="diagram",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),),
    )


def test_run_doctor_reports_missing_pnpm_globals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_doctor

    monkeypatch.setenv("HOME", str(tmp_path))
    mmdc = _mmdc_tool()
    bin_dir = tmp_path / "bin"
    console, buf = _console()
    run_doctor(
        [mmdc],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
        which=lambda _n: None,
        managed_globals=lambda: ("@mermaid-js/mermaid-cli",),
    )
    out = buf.getvalue()
    assert "mmdc" in out
    assert "make setup" in out


def test_run_doctor_silent_when_the_catalog_tool_was_never_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The catalog DECLARES mmdc. pnpm does not manage it, so nothing was lost
    # and `make doctor` must not claim a self-update destroyed the user's globals.
    from installer.app import run_doctor

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / "bin"
    console, buf = _console()
    run_doctor(
        [_mmdc_tool()],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
        which=lambda _n: None,
        managed_globals=lambda: (),
    )
    assert "pnpm-managed global set is incomplete" not in buf.getvalue()


def test_run_doctor_silent_when_pnpm_cannot_be_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_doctor

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / "bin"
    console, buf = _console()
    run_doctor(
        [_mmdc_tool()],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
        which=lambda _n: None,
        managed_globals=lambda: None,
    )
    assert "pnpm-managed global set is incomplete" not in buf.getvalue()


def test_run_doctor_silent_on_healthy_pnpm_globals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_doctor

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / "bin"
    console, buf = _console()
    run_doctor(
        [_mmdc_tool()],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
        which=lambda name: "/x/mmdc" if name == "mmdc" else None,
        managed_globals=lambda: ("@mermaid-js/mermaid-cli",),
    )
    out = buf.getvalue()
    assert "pnpm-managed global set is incomplete" not in out


def test_run_doctor_reports_npx_redirect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.app import run_doctor
    from installer.guards import install_redirect_shims

    monkeypatch.setenv("HOME", str(tmp_path))
    shim_dir = tmp_path / ".local" / "bin"
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    pnpm = real_dir / "pnpm"
    pnpm.write_text("#!/bin/sh\n")
    pnpm.chmod(0o755)

    def lookup(name: str, _path: str) -> str | None:
        return str(pnpm) if name == "pnpm" else None

    install_redirect_shims(shim_dir, path_value=str(real_dir), lookup=lookup)
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    run_doctor(
        [],
        console,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=shim_dir,
        path_value=str(shim_dir),
        exists=lambda _p: True,
        which=lambda name: str(shim_dir / name),
    )
    assert "npx: redirected to pnpm dlx" in buf.getvalue()


def _present(_path: Path) -> bool:
    return True


def _no_binary(_name: str) -> None:
    return None


def _no_globals() -> tuple[str, ...]:
    return ()


def _healthy_doctor_kwargs(bin_dir: Path) -> dict[str, object]:
    return {
        "platform": _platform(),
        "default_bin_dir": bin_dir,
        "path_value": str(bin_dir),
        "exists": _present,
        "which": _no_binary,
        "managed_globals": _no_globals,
    }


def _pressure(
    *,
    daemon: str,
    home_free: float | None,
    tmp_used: float | None,
    tmp_threshold: bool,
) -> DiskPressure:
    return DiskPressure(
        home_free_percent=home_free,
        tmp_used_percent=tmp_used,
        daemon=DaemonState(daemon),
        tmp_threshold=tmp_threshold,
    )


def test_run_doctor_without_disk_pressure_matches_the_existing_report(tmp_path: Path) -> None:
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    without, without_buf = _console()
    with_omitted, omitted_buf = _console()
    kwargs = _healthy_doctor_kwargs(bin_dir)
    run_doctor([_tool("rg", "search")], without, **kwargs)  # type: ignore[arg-type]
    run_doctor(
        [_tool("rg", "search")],
        with_omitted,
        disk_pressure=None,
        **kwargs,  # type: ignore[arg-type]
    )
    assert omitted_buf.getvalue() == without_buf.getvalue()
    assert "Background cleanup" not in without_buf.getvalue()


def test_run_doctor_emphasised_finding_carries_bold_style(tmp_path: Path) -> None:
    from rich.console import Console

    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(
        file=buf, width=120, force_terminal=True, color_system="standard", record=True
    )
    run_doctor(
        [],
        console,
        disk_pressure=lambda: _pressure(
            daemon="inactive", home_free=10.0, tmp_used=10.0, tmp_threshold=True
        ),
        **_healthy_doctor_kwargs(bin_dir),  # type: ignore[arg-type]
    )
    rendered = console.export_text(styles=True)
    assert "Background cleanup is off" in rendered
    assert "\x1b[1;" in rendered


def test_run_doctor_healthy_disk_prints_nothing_extra(tmp_path: Path) -> None:
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    kwargs = _healthy_doctor_kwargs(bin_dir)
    baseline, baseline_buf = _console()
    extra, extra_buf = _console()
    run_doctor([], baseline, **kwargs)  # type: ignore[arg-type]
    run_doctor(
        [],
        extra,
        disk_pressure=lambda: _pressure(
            daemon="inactive", home_free=80.0, tmp_used=10.0, tmp_threshold=True
        ),
        **kwargs,  # type: ignore[arg-type]
    )
    assert extra_buf.getvalue() == baseline_buf.getvalue()


def test_run_doctor_discloses_a_system_scope_competitor(tmp_path: Path) -> None:
    """WR-10: `make doctor` never mentioned the root-owned cleanup unit
    running alongside this project's own daemon."""
    from installer.app import run_doctor
    from installer.systemd_daemon import CompetingUnit

    bin_dir = tmp_path / "bin"
    kwargs = _healthy_doctor_kwargs(bin_dir)
    console, buf = _console()
    units = (CompetingUnit(name="cleanup-bun-tmp-cache.timer", scope="system", state="enabled"),)
    run_doctor([], console, competing=lambda: units, **kwargs)  # type: ignore[arg-type]
    out = buf.getvalue()
    assert "cleanup-bun-tmp-cache.timer" in out
    assert "sudo systemctl disable --now cleanup-bun-tmp-cache.timer" in out


def test_run_doctor_without_a_competing_probe_is_byte_identical(tmp_path: Path) -> None:
    from installer.app import run_doctor
    from installer.run import CommandError

    bin_dir = tmp_path / "bin"
    kwargs = _healthy_doctor_kwargs(bin_dir)
    baseline, baseline_buf = _console()
    empty, empty_buf = _console()
    failed, failed_buf = _console()

    def boom() -> tuple[object, ...]:
        raise CommandError(["systemctl", "list-unit-files"], 1)

    run_doctor([], baseline, **kwargs)  # type: ignore[arg-type]
    run_doctor([], empty, competing=tuple, **kwargs)  # type: ignore[arg-type]
    run_doctor([], failed, competing=boom, **kwargs)  # type: ignore[arg-type]
    assert empty_buf.getvalue() == baseline_buf.getvalue()
    assert failed_buf.getvalue() == baseline_buf.getvalue()


def test_run_doctor_swallows_a_probe_oserror(tmp_path: Path) -> None:
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    kwargs = _healthy_doctor_kwargs(bin_dir)
    baseline, baseline_buf = _console()
    failed, failed_buf = _console()

    def boom() -> DiskPressure:
        raise OSError("unreadable mount")

    run_doctor([], baseline, **kwargs)  # type: ignore[arg-type]
    run_doctor([], failed, disk_pressure=boom, **kwargs)  # type: ignore[arg-type]
    assert failed_buf.getvalue() == baseline_buf.getvalue()


def test_run_doctor_macos_skips_tmp_threshold_but_keeps_the_measured_percentage(
    tmp_path: Path,
) -> None:
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    seen: list[DiskPressure] = []

    def probe() -> DiskPressure:
        pressure = _pressure(daemon="inactive", home_free=80.0, tmp_used=95.0, tmp_threshold=False)
        assert isinstance(pressure, DiskPressure)
        seen.append(pressure)
        return pressure

    console, buf = _console()
    run_doctor(
        [],
        console,
        disk_pressure=probe,
        **_healthy_doctor_kwargs(bin_dir),  # type: ignore[arg-type]
    )
    out = buf.getvalue()
    assert "Background cleanup is off" not in out
    assert "nearly full" not in out.lower()
    # The threshold is off, so nothing is printed, but the measured temp
    # percentage is still on the report the caller handed over — task 3's
    # Policies row reads that number rather than a substituted root figure.
    assert seen == [
        _pressure(daemon="inactive", home_free=80.0, tmp_used=95.0, tmp_threshold=False)
    ]


def test_run_doctor_unavailable_daemon_is_an_ordinary_warning(tmp_path: Path) -> None:
    from rich.console import Console

    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(
        file=buf, width=160, force_terminal=True, color_system="standard", record=True
    )
    run_doctor(
        [],
        console,
        disk_pressure=lambda: _pressure(
            daemon="unavailable", home_free=10.0, tmp_used=10.0, tmp_threshold=True
        ),
        **_healthy_doctor_kwargs(bin_dir),  # type: ignore[arg-type]
    )
    rendered = console.export_text(styles=True)
    plain = buf.getvalue()
    assert "Free disk space is low" in plain
    assert "\x1b[1;" not in rendered
    assert "Enable the background cleanup" not in plain
    assert "Policies" not in plain


def test_run_uninstall_also_removes_guard_artifacts(tmp_path: Path):
    from installer.app import run_uninstall
    from installer.guards import install_shims, write_ban_aliases

    shim_dir = tmp_path / ".local" / "bin"
    myshellrc = tmp_path / ".myshellrc"
    rc = tmp_path / ".zshrc"
    install_shims(shim_dir)
    write_ban_aliases(myshellrc)
    write_ban_aliases(rc)
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    run_uninstall(
        [],
        console,
        default_bin_dir=shim_dir,
        myshellrc_path=myshellrc,
        rc_paths=[rc],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert not (shim_dir / "pip").exists()
    assert "tools-installer ban" not in myshellrc.read_text()
    assert "tools-installer ban" not in rc.read_text()
    # With only guard artifacts (no tool paths), the preview must announce the
    # ban removal and NOT contradict itself with "nothing to uninstall".
    out = buf.getvalue()
    assert "The pip/npm ban will also be removed" in out
    assert "Nothing to uninstall" not in out


def test_perform_uninstall_removes_only_chosen_levers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.shellrc import write_myshellrc

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    binary = opt / "fd"
    binary.write_text("binary")
    artifact = bin_dir / "fd"
    artifact.symlink_to(binary)
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)  # writes the managed PATH block

    # Only the tool's proven pair is selected; ban + path-block left intact.
    decision = UninstallDecision(paths=(artifact, opt), remove_ban=False, remove_path_block=False)
    perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )

    assert not artifact.is_symlink()
    assert not opt.exists()
    assert "tools-installer path" in myshellrc.read_text()  # block preserved


def test_perform_uninstall_removes_path_block_when_chosen(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.shellrc import write_myshellrc

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)

    decision = UninstallDecision(paths=(), remove_ban=True, remove_path_block=True)
    perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[myshellrc],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )

    assert "tools-installer path" not in myshellrc.read_text()  # block stripped


def test_run_wizard_installs_dependencies_before_dependents() -> None:
    mmdc = Tool(
        id="mmdc",
        name="mmdc",
        category="c",
        cmd="mmdc",
        methods=(Method(kind="node", params={"npm_pkg": "@x/mmdc"}),),
        requires=("pnpm",),
    )
    pnpm = Tool(
        id="pnpm",
        name="pnpm",
        category="c",
        cmd="pnpm",
        methods=(Method(kind="node", params={"npm_pkg": "@x/pnpm"}),),
    )
    catalog = [mmdc, pnpm]
    installed_order: list[str] = []

    def record_install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        installed_order.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="node")

    console, _buf = _console()
    summary = run_wizard(
        catalog,
        Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        FakePrompter(categories=[], tools=[], confirm=True),
        console,
        Options(all=False, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=record_install,
        installed=_never_installed,
        select_catalog=lambda tools: ["mmdc"],
    )
    assert installed_order == ["pnpm", "mmdc"]
    assert summary is not None


def test_perform_uninstall_ban_lever_removes_shims_and_aliases(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.guards import guard_status, install_shims, write_ban_aliases

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    rc = tmp_path / ".zshrc"
    install_shims(bin_dir)  # plant real ban shims
    write_ban_aliases(myshellrc)  # plant the alias block in both targets
    write_ban_aliases(rc)
    assert any(guard_status(bin_dir).values())  # precondition: ban is active

    decision = UninstallDecision(paths=(), remove_ban=True, remove_path_block=False)
    perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[rc],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )

    assert all(active is False for active in guard_status(bin_dir).values())  # shims gone
    assert "alias" not in myshellrc.read_text()  # alias block stripped from myshellrc
    assert "alias" not in rc.read_text()  # ...and from each rc path


def _enable_countdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    from installer.policy import tweak_policy
    from installer.tweaks import BUNDLES

    monkeypatch.setenv("HOME", str(tmp_path))
    rc_path = tmp_path / ".myshellrc"
    bin_dir = tmp_path / ".local" / "bin"
    countdown = next(bundle for bundle in BUNDLES if bundle.id == "countdown")
    tweak_policy(countdown, rc_path=rc_path, bin_dir=bin_dir).apply()
    return rc_path, bin_dir


def test_run_uninstall_previews_and_sweeps_active_tweaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    helper = bin_dir / "tools-installer-wait-time"
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "countdown" in out
    assert "Nothing to uninstall" not in out
    assert "wait_time()" not in rc_path.read_text()
    assert not helper.exists()


def test_run_uninstall_sweeps_the_very_tweaks_it_previewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The preview and the sweep are one policy list, not two reads of it.

    Between them run_uninstall deletes artifacts, strips the managed block and
    removes shims and four alias blocks — every one writing the same
    ~/.myshellrc and bin_dir the activity predicate reads. Here a teardown step
    rewrites ~/.myshellrc wholesale and takes the helper with it, which is the
    hazard the invariant exists for: a second read reports nothing active, so
    the tweak the user was just told would be disabled is silently dropped.
    """
    from installer import app as app_module
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    helper = bin_dir / "tools-installer-wait-time"
    assert helper.exists()

    def wipe_the_rc_file(path: Path) -> None:
        # A removal step that does not respect the tweak markers. Nothing in the
        # real teardown does this today; the invariant is what keeps it from
        # becoming a silent data bug when something does.
        path.write_text("")
        helper.unlink()

    monkeypatch.setattr(app_module, "remove_managed_block", wipe_the_rc_file)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "These shell tweaks will also be disabled" in out
    assert "Shell tweaks disabled" in out
    assert "Could not disable" not in out


def test_run_uninstall_reports_nothing_to_uninstall_only_when_truly_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc_path = tmp_path / ".myshellrc"
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert "Nothing to uninstall" in buf.getvalue()

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: False,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert "Nothing to uninstall" not in buf.getvalue()
    assert "countdown" in buf.getvalue()


def test_run_uninstall_declined_removes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    helper = bin_dir / "tools-installer-wait-time"
    console, _buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: False,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert helper.exists()
    assert "wait_time()" in rc_path.read_text()


def test_run_uninstall_without_bundles_sweeps_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    helper = bin_dir / "tools-installer-wait-time"
    console, _buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert helper.exists()
    assert "wait_time()" in rc_path.read_text()


def test_run_uninstall_preview_names_the_plugins_and_the_zshrc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The .zshrc arm is the one the installer does not own, so the preview must
    say which names leave which file before the single confirm covers it."""
    from installer.app import run_uninstall
    from installer.policy import omz_plugins_policy
    from installer.tweaks import BUNDLES

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    rc_path = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("plugins=(z)\nsource $ZSH/oh-my-zsh.sh\n")
    omz_plugins_policy(zshrc_path=zshrc, state_path=rc_path, present=True).apply()

    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: False,
        bundles=BUNDLES,
        zshrc_path=zshrc,
        daemon_policy=None,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "omz-plugins" in out
    assert "git, docker" in out
    assert "~/.zshrc" in out
    # Declined: nothing was touched.
    assert zshrc.read_text().startswith("plugins=(z git docker)")


def test_run_uninstall_preview_stays_silent_about_a_zshrc_it_does_not_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    zshrc = tmp_path / ".zshrc"
    hand_written = "plugins=(git docker kubectl)\nsource $ZSH/oh-my-zsh.sh\n"
    zshrc.write_text(hand_written)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=BUNDLES,
        zshrc_path=zshrc,
        daemon_policy=None,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "countdown" in out
    assert "omz-plugins" not in out
    assert zshrc.read_text() == hand_written


def test_run_uninstall_reports_what_the_sweep_did_not_what_it_previewed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert "Shell tweaks disabled: tweak:countdown." in buf.getvalue()


def test_run_uninstall_names_the_tweaks_it_could_not_disable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import policy as policy_module
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES, TweakBundle

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)

    def boom(_bundle: TweakBundle, _path: Path) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(policy_module, "remove_tweak", boom)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "Could not disable: tweak:countdown." in out
    assert "Shell tweaks disabled" not in out


class _FakeDaemonRun:
    """Records every argv; never touches real launchctl. Can be told to fail
    the bootout call, to exercise a real removal failure during a sweep."""

    def __init__(self, *, fail_bootout: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._fail_bootout = fail_bootout

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        if self._fail_bootout and cmd[:2] == ["launchctl", "bootout"]:
            raise CommandError(cmd, 5)


def _daemon_for_uninstall(
    tmp_path: Path, *, run: Callable[[list[str]], None] | None = None, decided: bool = False
) -> tuple[Policy, Path]:
    script_path = tmp_path / "scripts" / "prune-user-tmpdir.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    state_path = tmp_path / ".myshellrc"
    policy: Policy = daemon_policy(
        plist_path=tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist",
        log_path=tmp_path / "Logs" / "prune-daemon.log",
        wrapper_bin_dir=tmp_path / ".local" / "bin",
        script_path=script_path,
        state_path=state_path,
        installed_tools={"fd": True, "rg": True},
        path_value="/usr/bin:/bin",
        tmpdir_value=str(tmp_path / "tmp"),
        home_value=str(tmp_path),
        uv_path=tmp_path / "uv",
        uid=501,
        run=run if run is not None else _FakeDaemonRun(),
    )
    if decided:
        daemon.record_decided(state_path)
    return policy, state_path


def test_run_uninstall_forwards_daemon_policy_into_the_sweep_and_clears_the_marker(
    tmp_path: Path,
) -> None:
    from installer import daemon
    from installer.app import run_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(tmp_path)
    daemon_policy_obj.apply()
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    assert plist_path.exists()
    assert daemon.decided(state_path) is True

    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    assert not plist_path.exists()
    assert daemon.decided(state_path) is False
    out = buf.getvalue()
    assert "background maintenance job" in out
    assert "daemon:prune-tmpdir" in out


def test_run_uninstall_requires_daemon_policy() -> None:
    from installer.app import run_uninstall

    console, _buf = _console()
    with pytest.raises(TypeError):
        run_uninstall(  # type: ignore[call-arg]
            [],
            console,
            default_bin_dir=Path("/tmp/bin"),
            myshellrc_path=Path("/tmp/rc"),
            rc_paths=[],
            confirm=lambda _m: True,
            bundles=(),
            zshrc_path=Path("/tmp/.zshrc"),
        )


def test_run_uninstall_clears_the_decided_marker_for_an_already_disabled_daemon(
    tmp_path: Path,
) -> None:
    """11-REVIEWS.md cycle 3 finding #13: an already-disabled daemon (nothing
    to sweep -- absent from BOTH swept and failed) still clears the marker, so
    a full uninstall+reinstall is genuinely fresh even in this case."""
    from installer import daemon
    from installer.app import run_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(tmp_path, decided=True)
    assert not (tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist").exists()
    assert daemon.decided(state_path) is True

    console, _buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    assert daemon.decided(state_path) is False


def test_run_uninstall_preserves_the_decided_marker_when_daemon_removal_fails(
    tmp_path: Path,
) -> None:
    from installer import daemon
    from installer.app import run_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(
        tmp_path, run=_FakeDaemonRun(fail_bootout=True)
    )
    daemon_policy_obj.apply()
    assert daemon.decided(state_path) is True

    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    assert daemon.decided(state_path) is True  # preserved: the removal genuinely failed
    assert "Could not disable" in buf.getvalue()


def test_perform_uninstall_forwards_daemon_policy_and_clears_the_marker(tmp_path: Path) -> None:
    from installer import daemon
    from installer.app import UninstallDecision, perform_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(tmp_path)
    daemon_policy_obj.apply()
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    assert plist_path.exists()

    decision = UninstallDecision(
        paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=True
    )
    result = perform_uninstall(
        decision,
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    assert "daemon:prune-tmpdir" in result.swept
    assert not plist_path.exists()
    assert daemon.decided(state_path) is False


def test_perform_uninstall_clears_marker_for_disabled_daemon_with_no_tweaks_row(
    tmp_path: Path,
) -> None:
    """Post-implementation review, second lane: when the daemon is already
    inactive and the TUI's Uninstall screen never offered a tweaks row to
    select (finding #4's exact scenario), decision.remove_tweaks is False --
    but the marker must still be cleared so a full uninstall+reinstall is
    genuinely fresh, mirroring run_uninstall's own "nothing to sweep" case."""
    from installer import daemon
    from installer.app import UninstallDecision, perform_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(tmp_path, decided=True)
    assert not (tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist").exists()
    assert daemon.decided(state_path) is True

    decision = UninstallDecision(
        paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=False
    )
    result = perform_uninstall(
        decision,
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    assert result.swept == ()
    assert daemon.decided(state_path) is False


def test_perform_uninstall_preserves_the_decided_marker_for_an_active_daemon_left_unselected(
    tmp_path: Path,
) -> None:
    """The other side of the same fix: an ACTIVE daemon the user deliberately
    left unselected (remove_tweaks=False while a tweaks row genuinely existed
    and was declined) must keep its marker -- the new fallback branch only
    fires when the daemon is already inactive, never when it is merely
    unselected while still running."""
    from installer import daemon
    from installer.app import UninstallDecision, perform_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(tmp_path)
    daemon_policy_obj.apply()
    plist_path = tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist"
    assert plist_path.exists()
    assert daemon.decided(state_path) is True

    decision = UninstallDecision(
        paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=False
    )
    result = perform_uninstall(
        decision,
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    assert result.swept == ()
    assert plist_path.exists()  # untouched: the user did not select removal
    assert daemon.decided(state_path) is True  # marker preserved: still active


def test_perform_uninstall_requires_daemon_policy() -> None:
    from installer.app import UninstallDecision, perform_uninstall

    decision = UninstallDecision(paths=(), remove_ban=False, remove_path_block=False)
    with pytest.raises(TypeError):
        perform_uninstall(  # type: ignore[call-arg]
            decision,
            bin_dir=Path("/tmp/bin"),
            myshellrc_path=Path("/tmp/rc"),
            rc_paths=[],
            bundles=(),
            zshrc_path=Path("/tmp/.zshrc"),
        )


def test_run_uninstall_preview_names_the_background_job_when_the_daemon_is_active(
    tmp_path: Path,
) -> None:
    from installer.app import run_uninstall

    daemon_policy_obj, state_path = _daemon_for_uninstall(tmp_path)
    daemon_policy_obj.apply()

    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: False,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=daemon_policy_obj,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "background maintenance job" in out
    assert "These shell tweaks will also be disabled" not in out  # byte-identical-when-absent proof


def test_run_uninstall_preview_stays_byte_identical_when_the_daemon_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import BUNDLES

    rc_path, bin_dir = _enable_countdown(tmp_path, monkeypatch)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=rc_path,
        rc_paths=[],
        confirm=lambda _m: False,
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert "These shell tweaks will also be disabled (tweak:countdown)." in out
    assert "background maintenance job" not in out


def _linux_daemon_for_uninstall(tmp_path: Path) -> tuple[Policy, Path]:
    from installer.policy import linux_daemon_policy

    script_path = tmp_path / "scripts" / "prune-tmp-linux.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    state_path = tmp_path / ".myshellrc"
    policy = linux_daemon_policy(
        unit_dir=tmp_path / "systemd" / "user",
        log_path=tmp_path / "Logs" / "prune-daemon.log",
        wrapper_bin_dir=tmp_path / ".local" / "bin",
        script_path=script_path,
        state_path=state_path,
        installed_tools={},
        path_value="/usr/bin:/bin",
        tmpdir_value=str(tmp_path / "tmp"),
        home_value=str(tmp_path),
        uv_path=tmp_path / "uv",
        run=lambda _cmd: None,
        read_output=lambda _cmd: "inactive",
    )
    return policy, state_path


class _SystemctlFake:
    """A user manager on disk: `enable` creates the wants symlink, `disable`
    removes it. `reachable=False` makes every mutation fail, like a
    `make uninstall` over ssh with no user bus."""

    def __init__(self, unit_dir: Path, *, reachable: bool = True) -> None:
        self.unit_dir = unit_dir
        self.reachable = reachable
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> None:
        from installer import systemd_daemon
        from installer.run import CommandError

        self.calls.append(cmd)
        if not self.reachable:
            raise CommandError(cmd, 1)
        link = systemd_daemon.wants_link_path(self.unit_dir)
        if cmd[2] == "enable":
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.is_symlink():
                link.symlink_to(self.unit_dir / systemd_daemon.TIMER_NAME)
        elif cmd[2] == "disable" and link.is_symlink():
            link.unlink()


@pytest.mark.parametrize("state", ["inactive", "unreachable"])
def test_run_uninstall_removes_an_installed_but_not_running_linux_timer(
    tmp_path: Path, state: str
) -> None:
    """CR-01: the sweep reads footprint, never runtime state. A stopped or
    unreachable timer used to be skipped while the marker was cleared and
    success was printed, so the timer restarted at the next login."""
    from installer import systemd_daemon
    from installer.app import run_uninstall
    from installer.policy import linux_daemon_policy
    from installer.run import CommandError

    script_path = tmp_path / "scripts" / "prune-tmp-linux.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    unit_dir = tmp_path / "systemd" / "user"
    bin_dir = tmp_path / ".local" / "bin"
    state_path = tmp_path / ".myshellrc"
    fake = _SystemctlFake(unit_dir)

    def read_output(cmd: list[str]) -> str:
        if not fake.reachable:
            raise CommandError(cmd, 1)
        return "inactive" if cmd[2] == "is-active" else ""

    def build() -> Policy:
        return linux_daemon_policy(
            unit_dir=unit_dir,
            log_path=tmp_path / "Logs" / "prune-daemon.log",
            wrapper_bin_dir=bin_dir,
            script_path=script_path,
            state_path=state_path,
            installed_tools={},
            path_value="/usr/bin:/bin",
            tmpdir_value=str(tmp_path / "tmp"),
            home_value=str(tmp_path),
            uv_path=tmp_path / "uv",
            run=fake,
            read_output=read_output,
        )

    build().apply()
    assert systemd_daemon.wants_link_path(unit_dir).is_symlink()
    assert systemd_daemon.decided(state_path) is True
    fake.reachable = state != "unreachable"
    policy = build()
    assert policy.active is False  # not running: the old sweep predicate
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=policy,
        extra_policies=(),
    )
    out = buf.getvalue()
    assert systemd_daemon.footprint_present(unit_dir) is False
    assert not systemd_daemon.wants_link_path(unit_dir).is_symlink()
    assert systemd_daemon.wrapper_present(bin_dir) is False
    assert "daemon:prune-tmp-linux" in out
    assert systemd_daemon.decided(state_path) is False
    if state == "unreachable":
        assert "systemctl --user daemon-reload" in out
    else:
        assert "daemon-reload" not in out


def test_run_uninstall_keeps_the_linux_marker_when_a_running_timer_cannot_be_disabled(
    tmp_path: Path,
) -> None:
    from installer import systemd_daemon
    from installer.app import run_uninstall
    from installer.policy import linux_daemon_policy
    from installer.run import CommandError

    script_path = tmp_path / "scripts" / "prune-tmp-linux.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    unit_dir = tmp_path / "systemd" / "user"
    state_path = tmp_path / ".myshellrc"
    fail_disable = False

    def run(cmd: list[str]) -> None:
        if fail_disable and cmd[2] == "disable":
            raise CommandError(cmd, 1)

    def build() -> Policy:
        return linux_daemon_policy(
            unit_dir=unit_dir,
            log_path=tmp_path / "Logs" / "prune-daemon.log",
            wrapper_bin_dir=tmp_path / ".local" / "bin",
            script_path=script_path,
            state_path=state_path,
            installed_tools={},
            path_value="/usr/bin:/bin",
            tmpdir_value=str(tmp_path / "tmp"),
            home_value=str(tmp_path),
            uv_path=tmp_path / "uv",
            run=run,
            read_output=lambda _cmd: "active",
        )

    build().apply()
    fail_disable = True
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=build(),
        extra_policies=(),
    )
    assert systemd_daemon.units_present(unit_dir) is True
    assert systemd_daemon.decided(state_path) is True
    assert "Could not disable: daemon:prune-tmp-linux" in buf.getvalue()


def test_run_uninstall_clears_the_linux_marker_and_leaves_the_macos_one(
    tmp_path: Path,
) -> None:
    from installer import daemon, systemd_daemon
    from installer.app import run_uninstall

    policy, state_path = _linux_daemon_for_uninstall(tmp_path)
    systemd_daemon.record_decided(state_path)
    daemon.record_decided(state_path)
    console, _buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=policy,
        extra_policies=(),
    )
    assert systemd_daemon.decided(state_path) is False
    assert daemon.decided(state_path) is True


def test_run_uninstall_clears_the_linux_marker_after_a_successful_sweep(
    tmp_path: Path,
) -> None:
    from installer import daemon, systemd_daemon
    from installer.app import run_uninstall

    policy, state_path = _linux_daemon_for_uninstall(tmp_path)
    systemd_daemon.record_decided(state_path)
    daemon.record_decided(state_path)

    from dataclasses import replace

    from installer.policy import PolicyResult

    def active() -> bool:
        return True

    def remove() -> PolicyResult:
        return PolicyResult(layers=(), reload_hint=None, warning=None)

    active_policy = replace(policy, active=True, is_active=active, owned=active, remove=remove)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=active_policy,
        extra_policies=(),
    )
    assert systemd_daemon.decided(state_path) is False
    assert daemon.decided(state_path) is True
    assert "daemon:prune-tmp-linux" in buf.getvalue()


def test_perform_uninstall_clears_the_linux_marker_for_an_already_inactive_daemon(
    tmp_path: Path,
) -> None:
    from installer import daemon, systemd_daemon
    from installer.app import UninstallDecision, perform_uninstall

    policy, state_path = _linux_daemon_for_uninstall(tmp_path)
    systemd_daemon.record_decided(state_path)
    daemon.record_decided(state_path)
    decision = UninstallDecision(
        paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=False
    )
    perform_uninstall(
        decision,
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=policy,
        extra_policies=(),
    )
    assert systemd_daemon.decided(state_path) is False
    assert daemon.decided(state_path) is True


def test_run_uninstall_preserves_the_linux_marker_when_removal_fails(tmp_path: Path) -> None:
    from dataclasses import replace

    from installer import systemd_daemon
    from installer.app import run_uninstall
    from installer.policy import PolicyResult
    from installer.run import CommandError

    policy, state_path = _linux_daemon_for_uninstall(tmp_path)
    systemd_daemon.record_decided(state_path)

    def active() -> bool:
        return True

    def remove() -> PolicyResult:
        raise CommandError(["systemctl", "--user", "disable"], 1)

    failed = replace(policy, active=True, is_active=active, owned=active, remove=remove)
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=failed,
        extra_policies=(),
    )
    assert systemd_daemon.decided(state_path) is True
    assert "Could not disable" in buf.getvalue()


def test_clear_decided_none_is_a_noop_at_every_uninstall_branch(tmp_path: Path) -> None:
    from dataclasses import replace

    from installer.app import UninstallDecision, perform_uninstall, run_uninstall
    from installer.policy import PolicyResult

    policy, state_path = _linux_daemon_for_uninstall(tmp_path)
    bare = replace(policy, clear_decided=None, decided=None)
    console, _buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=bare,
        extra_policies=(),
    )
    perform_uninstall(
        UninstallDecision(paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=False),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=bare,
        extra_policies=(),
    )

    def active() -> bool:
        return True

    def remove() -> PolicyResult:
        return PolicyResult(layers=(), reload_hint=None, warning=None)

    swept = replace(bare, active=True, is_active=active, remove=remove)
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=swept,
        extra_policies=(),
    )
    perform_uninstall(
        UninstallDecision(paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=True),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=swept,
        extra_policies=(),
    )


def test_run_uninstall_and_perform_uninstall_sweep_and_name_an_extra_policy(
    tmp_path: Path,
) -> None:
    from installer.app import UninstallDecision, perform_uninstall, run_uninstall
    from installer.policy import PolicyResult

    removed: list[str] = []

    def remove() -> PolicyResult:
        removed.append("cache-redirect:bun")
        return PolicyResult(layers=(), reload_hint=None, warning=None)

    extra = Policy(
        id="cache-redirect:bun",
        label="Bun cache",
        description="",
        active=True,
        apply=remove,
        remove=remove,
        is_active=lambda: "cache-redirect:bun" not in removed,
    )
    console, buf = _console()
    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=lambda _m: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(extra,),
    )
    assert "cache-redirect:bun" in buf.getvalue()
    assert removed == ["cache-redirect:bun"]

    removed.clear()
    again = Policy(
        id="cache-redirect:bun",
        label="Bun cache",
        description="",
        active=True,
        apply=remove,
        remove=remove,
        is_active=lambda: True,
    )
    result = perform_uninstall(
        UninstallDecision(paths=(), remove_ban=False, remove_path_block=False, remove_tweaks=True),
        bin_dir=tmp_path / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(again,),
    )
    assert "cache-redirect:bun" in result.swept


def test_uninstall_entry_points_require_extra_policies(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall, run_uninstall

    console, _buf = _console()
    with pytest.raises(TypeError):
        run_uninstall(  # type: ignore[call-arg]
            [],
            console,
            default_bin_dir=tmp_path / "bin",
            myshellrc_path=tmp_path / ".myshellrc",
            rc_paths=[],
            confirm=lambda _m: True,
            bundles=(),
            zshrc_path=tmp_path / ".zshrc",
            daemon_policy=None,
        )
    with pytest.raises(TypeError):
        perform_uninstall(  # type: ignore[call-arg]
            UninstallDecision(paths=(), remove_ban=False, remove_path_block=False),
            bin_dir=tmp_path / "bin",
            myshellrc_path=tmp_path / ".myshellrc",
            rc_paths=[],
            bundles=(),
            zshrc_path=tmp_path / ".zshrc",
            daemon_policy=None,
        )


def test_sweep_helpers_keep_an_empty_extra_policies_default(tmp_path: Path) -> None:
    from installer.uninstall import active_policies, active_tweak_ids, sweep_tweaks

    rc = tmp_path / ".myshellrc"
    bin_dir = tmp_path / "bin"
    assert active_policies((), rc_path=rc, bin_dir=bin_dir) == []
    assert active_tweak_ids((), rc_path=rc, bin_dir=bin_dir) == ()
    assert sweep_tweaks((), rc_path=rc, bin_dir=bin_dir) == SweepResult()


def test_run_wizard_surfaces_a_postinstall_warning_on_the_real_path() -> None:
    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        tools: Mapping[str, Tool] | None = None,
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        return InstallOutcome(
            tool.id,
            "installed",
            method_kind="github_release",
            postinstall_warning="codegraph MCP registration failed: exit 1",
        )

    console, buf = _console()
    summary = run_wizard(
        [_tool("codegraph", "dev")],
        _platform(),
        FakePrompter(categories=[], tools=[], confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert summary is not None
    out = buf.getvalue()
    assert "codegraph" in out
    assert "codegraph MCP registration failed: exit 1" in out


def test_run_wizard_passes_the_full_catalog_as_tools_by_id_into_run_installs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.app as app_module

    seen: dict[str, object] = {}

    def fake_run_installs(
        ordered: list[Tool],
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        install: Install,
        *,
        on_mismatch: object = None,
        catalog: Mapping[str, Tool] | None = None,
    ) -> list[InstallOutcome]:
        seen["catalog"] = catalog
        return [InstallOutcome(tool.id, "installed", method_kind="brew") for tool in ordered]

    monkeypatch.setattr(app_module, "run_installs", fake_run_installs)
    catalog_tools = _catalog()
    _installed, install = _recording_install()
    run_wizard(
        catalog_tools,
        _platform(),
        FakePrompter(categories=[], tools=[], confirm=True),
        _console()[0],
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        installed=_never_installed,
    )
    assert seen["catalog"] == {t.id: t for t in catalog_tools}


def _login_shell_tool() -> Tool:
    return Tool(
        id="oh-my-zsh",
        name="Oh My Zsh",
        category="shell",
        cmd="omz",
        methods=(Method(kind="script", params={"url": "u"}),),
        post_install=("set_login_shell",),
    )


def _not_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import installer.engine as engine

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)


def test_run_wizard_prints_login_shell_instructions_when_sensitive_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_present(monkeypatch)
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, buf = _console()
    summary = run_wizard(
        [_login_shell_tool()],
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        installed=_never_installed,
    )
    out = buf.getvalue()
    assert summary is not None
    assert summary.installed == ("oh-my-zsh",)
    assert "chsh -s" in out
    sensitive = [q for q in prompter.questions if q != _BATCH_QUESTION]
    assert len(sensitive) == 1
    question = sensitive[0]
    assert "oh-my-zsh" in question
    assert question != _BATCH_QUESTION
    lowered = question.lower()
    assert "command" in lowered
    assert "run" in lowered
    assert "will change" not in lowered
    assert "will be changed" not in lowered


def test_run_wizard_skips_login_shell_instructions_when_sensitive_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_present(monkeypatch)
    prompter = FakePrompter(categories=[], tools=[], confirm=True, sensitive_confirm=False)
    console, buf = _console()
    summary = run_wizard(
        [_login_shell_tool()],
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        installed=_never_installed,
    )
    assert summary is not None
    assert summary.installed == ("oh-my-zsh",)
    assert "chsh -s" not in buf.getvalue()


def test_run_wizard_sensitive_unattended_never_asks_and_prints_no_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_present(monkeypatch)
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, buf = _console()
    summary = run_wizard(
        [_login_shell_tool()],
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        installed=_never_installed,
    )
    assert summary is not None
    assert summary.installed == ("oh-my-zsh",)
    assert prompter.questions == []
    assert "chsh -s" not in buf.getvalue()


def test_run_wizard_never_asks_sensitive_question_without_login_shell_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _not_present(monkeypatch)
    prompter = FakePrompter(categories=[], tools=[], confirm=True)
    console, buf = _console()
    summary = run_wizard(
        [_tool("rg", "search")],
        _platform(),
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        installed=_never_installed,
    )
    assert summary is not None
    assert summary.installed == ("rg",)
    assert prompter.questions == [_BATCH_QUESTION]
    assert "chsh -s" not in buf.getvalue()


class _UninstallKwargs(TypedDict):
    """Keyword arguments for run_uninstall, typed so the splat checks exactly."""

    default_bin_dir: Path
    myshellrc_path: Path
    rc_paths: list[Path]
    confirm: Callable[[str], bool]
    bundles: tuple[TweakBundle, ...]
    zshrc_path: Path
    daemon_policy: Policy | None
    extra_policies: tuple[Policy, ...]


def _uninstall_kwargs(
    tmp_path: Path, bin_dir: Path, confirm: Callable[[str], bool]
) -> _UninstallKwargs:
    from installer.shellrc import write_myshellrc

    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)
    return {
        "default_bin_dir": bin_dir,
        "myshellrc_path": myshellrc,
        "rc_paths": [],
        "confirm": confirm,
        "bundles": (),
        "zshrc_path": tmp_path / ".zshrc",
        "daemon_policy": None,
        "extra_policies": (),
    }


def test_run_uninstall_deletes_only_proven_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_removal_fixtures

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()
    removed = run_uninstall(tools, console, **_uninstall_kwargs(tmp_path, bin_dir, lambda _m: True))
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    assert set(removed) == {bin_dir / "fd", opt_fd}
    assert not (bin_dir / "fd").is_symlink()
    assert not opt_fd.exists()
    # Foreign files survive byte-identical.
    assert (bin_dir / "ruff").read_text() == "uv-installed ruff"
    assert (bin_dir / "yq").read_text() == "pip-installed yq"
    assert (bin_dir / "drawio").read_text() == "shared drawio"
    text = buf.getvalue()
    assert str(bin_dir / "ruff") in text
    assert str(bin_dir / "yq") in text
    assert str(bin_dir / "drawio") in text


def test_run_uninstall_with_only_unproven_matches_still_lists_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_removal_fixtures

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = [t for t in plant_removal_fixtures(tmp_path) if t.id != "fd"]
    bin_dir = tmp_path / ".local" / "bin"

    def fail_confirm(_message: str) -> bool:
        raise AssertionError("confirm must not be called with nothing proven")

    console, buf = _console()
    removed = run_uninstall(tools, console, **_uninstall_kwargs(tmp_path, bin_dir, fail_confirm))
    assert removed == []
    text = buf.getvalue()
    assert "Nothing to uninstall" in text
    assert "remove them yourself" in text
    assert str(bin_dir / "yq") in text


def test_second_yes_run_deletes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_removal_fixtures

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    tools = plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    kwargs = _uninstall_kwargs(tmp_path, bin_dir, lambda _m: True)
    console, _buf = _console()
    first = run_uninstall(tools, console, **kwargs)
    assert first

    def snapshot() -> dict[Path, bytes]:
        return {
            p.relative_to(tmp_path): p.read_bytes()
            for p in sorted(tmp_path.rglob("*"))
            if p.is_file() and not p.is_symlink()
        }

    def link_targets() -> dict[Path, str]:
        return {
            p.relative_to(tmp_path): str(p.readlink())
            for p in sorted(tmp_path.rglob("*"))
            if p.is_symlink()
        }

    before_files, before_links = snapshot(), link_targets()
    console2, _buf2 = _console()
    second = run_uninstall(
        tools,
        console2,
        **kwargs,
    )
    assert second == []
    assert snapshot() == before_files
    assert link_targets() == before_links


def test_run_uninstall_survives_a_looping_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-01: a self-looping bin link crashes nothing -- it is unproven, so the
    run lists it for manual removal and completes."""
    from installer.app import run_uninstall
    from tests.test_uninstall import loop_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "foo").symlink_to("foo")
    tool = loop_tool("foo")
    console, buf = _console()
    removed = run_uninstall(
        [tool],
        console,
        **_uninstall_kwargs(tmp_path, bin_dir, lambda _m: True),
    )
    assert removed == []
    assert (bin_dir / "foo").is_symlink()  # untouched
    assert str(bin_dir / "foo") in buf.getvalue()


def test_run_uninstall_refuses_paths_changed_since_the_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """opencode H1: a proven link replaced by a foreign regular file between
    the preview and the confirm is refused and reported, not deleted."""
    from installer.app import run_uninstall
    from tests.test_uninstall import loop_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt = tmp_path / ".local" / "opt" / "fd"
    opt.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (opt / "fd").write_text("bin")
    (bin_dir / "fd").symlink_to(opt / "fd")
    tool = loop_tool("fd")

    def swap_then_confirm(_message: str) -> bool:
        (bin_dir / "fd").unlink()
        (bin_dir / "fd").write_text("foreign file")
        return True

    console, buf = _console()
    removed = run_uninstall(
        [tool],
        console,
        **_uninstall_kwargs(tmp_path, bin_dir, swap_then_confirm),
    )
    assert removed == []
    assert (bin_dir / "fd").read_text() == "foreign file"  # the replacement survives
    assert opt.exists()  # the opt dir is no longer proven either
    assert "changed since the preview" in buf.getvalue()
    assert str(bin_dir / "fd") in buf.getvalue()


def test_perform_uninstall_refuses_paths_changed_since_the_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI apply path re-checks the same proof at deletion time (H1):
    a still-proven link is removed, a replaced one is refused with a warning."""
    from installer.app import UninstallDecision, perform_uninstall
    from tests.test_uninstall import plant_removal_fixtures

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    plant_removal_fixtures(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("")

    # fd's link is swapped for a foreign file after the preview was rendered.
    (bin_dir / "fd").unlink()
    (bin_dir / "fd").write_text("foreign file")

    decision = UninstallDecision(
        paths=(bin_dir / "fd", opt_fd), remove_ban=False, remove_path_block=False
    )
    result = perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert (bin_dir / "fd").read_text() == "foreign file"  # the replacement survives
    assert opt_fd.exists()  # without its link, the opt dir is unproven too
    assert any("changed since the preview" in warning for warning in result.warnings)
    assert any(str(bin_dir / "fd") in warning for warning in result.warnings)

    # A still-proven link is still removed, with no refusal warning.
    (opt_fd / "fd").write_text("bin")
    (bin_dir / "fd").unlink()
    (bin_dir / "fd").symlink_to(opt_fd / "fd")
    decision = UninstallDecision(
        paths=(bin_dir / "fd", opt_fd), remove_ban=False, remove_path_block=False
    )
    result = perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
    )
    assert result.warnings == ()
    assert not (bin_dir / "fd").is_symlink()
    assert not opt_fd.exists()
