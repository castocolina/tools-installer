import io
from pathlib import Path

import pytest
from rich.console import Console

from installer.app import run_wizard
from installer.cli import Options
from installer.engine import InstallOutcome
from installer.model import Method, Tool
from installer.platform import Platform
from installer.selection import Choice
from installer.session import Install, Summary


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
        tool: Tool, platform: Platform, runner: object, resolve_tag: object
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
        tool: Tool, platform: Platform, runner: object, resolve_tag: object
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


def test_run_doctor_reports_and_fixes(tmp_path: Path):
    from pathlib import Path as _P

    from installer.app import run_doctor

    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# zsh\n")
    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()

    def exists(path: _P) -> bool:
        return False  # nothing on disk -> broken + missing

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value="/usr/bin",
        exists=exists,
        myshellrc_path=myshellrc,
        rc_paths=[zshrc],
        fix=True,
    )

    assert bin_dir in report.missing
    assert "github.com/castocolina/tools-installer" in buf.getvalue()
    assert myshellrc.exists()  # fix=True wrote the managed block
    assert "tools-installer source" in zshrc.read_text()


def test_run_doctor_without_fix_does_not_write(tmp_path: Path):
    from pathlib import Path as _P

    from installer.app import run_doctor

    myshellrc = tmp_path / ".myshellrc"
    console, _buf = _console()

    def exists(path: _P) -> bool:
        return True

    run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / "bin",
        path_value="/usr/bin",
        exists=exists,
        myshellrc_path=myshellrc,
        rc_paths=[],
        fix=False,
    )
    assert not myshellrc.exists()  # fix=False is read-only


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


def test_run_doctor_forwards_link_mode_split_when_fixing(tmp_path: Path):
    from installer.app import run_doctor
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc = tmp_path / ".zshrc"
    run_doctor(
        [],
        console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin",
        path_value="",
        exists=lambda _p: True,
        myshellrc_path=myshellrc,
        rc_paths=[zrc],
        fix=True,
        link_mode="split",
    )
    assert not myshellrc.exists()  # split mode forwarded -> inline, no ~/.myshellrc
    assert "# >>> tools-installer path >>>" in zrc.read_text()


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
        confirm=fail_confirm,
    )
    assert removed == []
