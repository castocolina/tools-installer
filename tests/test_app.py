import io

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
        tool: Tool, platform: Platform, runner: object, resolve_version: object
    ) -> InstallOutcome:
        installed.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    return installed, install


def _never_installed(tool: Tool) -> bool:
    return False


def _runner(cmd: list[str]) -> None:
    return None


def _resolve(repo: str) -> str:
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
        resolve_version=_resolve,
        install=install,
        installed=_never_installed,
    )
    assert installed == ["rg", "fd", "jq"]
    assert summary == Summary(installed=("rg", "fd", "jq"), already=(), failed=(), no_method=())
    assert prompter.confirmed == 0


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
        resolve_version=_resolve,
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
        resolve_version=_resolve,
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
        resolve_version=_resolve,
        install=install,
        installed=_never_installed,
    )
    assert installed == []
    assert summary is None  # None signals an aborted run, distinct from an empty Summary
    assert prompter.confirmed == 1
