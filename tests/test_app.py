import io
from pathlib import Path

import pytest
from rich.console import Console

from installer.app import run_guard, run_wizard
from installer.checksums import ChecksumMismatch
from installer.cli import Options
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.run import Runner
from installer.selection import Choice
from installer.session import Install, MismatchChoice, Summary
from installer.versions import TagResolver


def _tool(tool_id: str, category: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category=category,
        cmd=tool_id,
        methods=(Method(kind="brew", params={"formula": tool_id}),),
    )


def _catalog() -> list[Tool]:
    return [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]


def _platform() -> Platform:
    return Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)


def _console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, width=100, no_color=True), buf


class FakePrompter:
    def __init__(self, categories: list[str], tools: list[str], confirm: bool) -> None:
        self._categories = categories
        self._tools = tools
        self._confirm = confirm
        self.confirmed = 0

    def select_categories(self, choices: list[Choice]) -> list[str]:
        return self._categories

    def select_tools(self, choices: list[Choice]) -> list[str]:
        return self._tools

    def confirm(self, message: str) -> bool:
        self.confirmed += 1
        return self._confirm


def _recording_install() -> tuple[list[str], Install]:
    installed: list[str] = []

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
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
    )
    assert removed == []


def _mismatching_install() -> tuple[list[str], Install]:
    attempts: list[str] = []
    exc = ChecksumMismatch("a.tar.gz", "0" * 64, "f" * 64)

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
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
    assert "tools-installer ban" in rc.read_text()
    assert "Installing the pip/npm ban" in buf.getvalue()


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
    assert "tools-installer ban" not in rc.read_text()


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
    assert "pip/npm ban active" in buf.getvalue()


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
    )
    assert not (shim_dir / "pip").exists()
    assert "tools-installer ban" not in myshellrc.read_text()
    assert "tools-installer ban" not in rc.read_text()
    # With only guard artifacts (no tool paths), the preview must announce the
    # ban removal and NOT contradict itself with "nothing to uninstall".
    out = buf.getvalue()
    assert "The pip/npm ban will also be removed" in out
    assert "Nothing to uninstall" not in out


def test_perform_uninstall_removes_only_chosen_levers(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.shellrc import write_myshellrc

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    artifact = bin_dir / "fd"
    artifact.write_text("binary")
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)  # writes the managed PATH block

    # Only the artifact is selected; ban + path-block left intact.
    decision = UninstallDecision(paths=(artifact,), remove_ban=False, remove_path_block=False)
    perform_uninstall(decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[])

    assert not artifact.exists()
    assert "tools-installer path" in myshellrc.read_text()  # block preserved


def test_perform_uninstall_removes_path_block_when_chosen(tmp_path: Path) -> None:
    from installer.app import UninstallDecision, perform_uninstall
    from installer.shellrc import write_myshellrc

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    myshellrc = tmp_path / ".myshellrc"
    write_myshellrc([bin_dir], myshellrc)

    decision = UninstallDecision(paths=(), remove_ban=True, remove_path_block=True)
    perform_uninstall(decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[myshellrc])

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
    perform_uninstall(decision, bin_dir=bin_dir, myshellrc_path=myshellrc, rc_paths=[rc])

    assert all(active is False for active in guard_status(bin_dir).values())  # shims gone
    assert "alias" not in myshellrc.read_text()  # alias block stripped from myshellrc
    assert "alias" not in rc.read_text()  # ...and from each rc path
