import io
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TypedDict, cast

import pytest
from rich.console import Console

from installer import daemon, shellrc
from installer.app import UninstallDecision, run_guard, run_wizard
from installer.checksums import ChecksumMismatch
from installer.cli import Options
from installer.diskusage import DiskPressure
from installer.engine import ChecksumPolicy, InstallOutcome
from installer.enums import DaemonState
from installer.model import Method, Tool
from installer.platform import Platform
from installer.policy import Policy, daemon_policy
from installer.post_install import ConfirmSensitiveAction
from installer.render import display_order
from installer.run import CommandError, Runner
from installer.session import (
    MismatchChoice,
    SensitiveInstall,
    build_plan,
    exit_code,
)
from installer.tweaks import TweakBundle
from installer.uninstall import RemovalPlan, SweepResult
from installer.update import UpdateOutcome
from installer.version_status import Health
from installer.versions import TagResolver
from tests.state_doubles import (
    FrozenStateService,
    ScriptedUpdates,
    offline_service,
    plan_state,
    presence_service,
    skill_pack_tool,
)


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


_BATCH_QUESTION = "Run this plan?"


class FakePrompter:
    def __init__(
        self,
        confirm: bool,
        *,
        sensitive_confirm: bool | None = None,
    ) -> None:
        self._confirm = confirm
        self._sensitive_confirm = confirm if sensitive_confirm is None else sensitive_confirm
        self.confirmed = 0
        self.questions: list[str] = []

    def confirm(self, message: str, *, default: bool = True) -> bool:
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


def _runner(cmd: list[str]) -> None:
    return None


def _resolve_tag(repo: str) -> str:
    return "1.0.0"


def test_all_yes_prints_the_plan_installs_the_missing_tool_and_returns_outcomes():
    tools = [_tool("rg", "search"), _tool("fd", "search")]
    refresh = presence_service(tools, present={"fd"})
    installed, install = _recording_install()
    prompter = FakePrompter(confirm=True)
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=refresh,
        updates=ScriptedUpdates({}),
    )

    output = buf.getvalue()
    assert "Install plan — 1 will install, 1 skipped" in output
    assert "○ rg" in output and "will install — not installed" in output
    assert "✓ fd" in output and "skipped — already current" in output
    assert "(r: reinstall)" not in output
    assert "Summary — 1 installed, 1 skipped" in output
    assert installed == ["rg"]
    assert isinstance(outcomes, list) and len(outcomes) == 2
    assert prompter.confirmed == 0


def test_without_yes_the_plan_is_printed_then_confirmed():
    tools = [_tool("rg", "search")]
    refresh = presence_service(tools)
    installed, install = _recording_install()
    declined = FakePrompter(confirm=False)
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        declined,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=refresh,
        updates=ScriptedUpdates({}),
    )

    assert "Install plan — 1 will install" in buf.getvalue()
    assert declined.questions == ["Run this plan?"]
    assert "Cancelled; nothing was changed." in buf.getvalue()
    assert outcomes is None
    assert installed == []

    accepted = FakePrompter(confirm=True)
    accepted_outcomes = run_wizard(
        tools,
        accepted,
        _console()[0],
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert accepted.questions == ["Run this plan?"]
    assert installed == ["rg"]
    assert isinstance(accepted_outcomes, list)


_AUTO_APPROVE_QUESTION = "auto-approve agents — claude, codex: no permission prompts?"
_ATTRIBUTION_QUESTION = "attribution off — claude: no agent credit in commits/PRs?"
_PI_NOTE = "pi: nothing written; its approvals come only from extensions"
_NO_KEY_NOTE = "no documented key: codex, pi (nothing written for them)"
_LEFT_OFF = "Run options left off (--yes never turns them on); change them in Policies."
_ZOXIDE_QUESTION = (
    "Turn on zoxide shell init? It adds one guarded block to ~/.myshellrc that adds z, "
    "a cd that learns the directories you use. It stays off unless you choose yes; "
    "Policies can change it later."
)
_LOGIN_SHELL_QUESTION = (
    "Show a reviewed command to change the login shell to zsh for oh-my-zsh, "
    "which you run in your own terminal after the installer exits?"
)


class _ScriptedPrompter:
    """Answers from a script (an unscripted question is no) and records each question.

    Each record is (message, default, console text printed before the question).
    """

    def __init__(self, answers: Mapping[str, bool], console_buf: io.StringIO) -> None:
        self._answers = answers
        self._buf = console_buf
        self.asked: list[tuple[str, bool, str]] = []

    def confirm(self, message: str, *, default: bool = True) -> bool:
        self.asked.append((message, default, self._buf.getvalue()))
        return self._answers.get(message, False)


def _asking_install(asks: Sequence[tuple[str, str]]) -> SensitiveInstall:
    """An install that asks the sensitive questions the real post-install step would ask."""

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
        for tool_id, action in asks:
            if tool_id == tool.id and confirm_sensitive_action is not None:
                confirm_sensitive_action(tool_id, action)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    return install


def test_headless_option_questions_default_to_no():
    """D-09 / T-23-47: each run-option question defaults to no; only a yes turns one on."""
    tools = [_tool("claude", "agent"), _tool("codex", "agent"), _tool("pi", "agent")]
    _, install = _recording_install()
    console, buf = _console()
    prompter = _ScriptedPrompter({_BATCH_QUESTION: True, _AUTO_APPROVE_QUESTION: True}, buf)

    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )

    assert [(message, default) for message, default, _ in prompter.asked] == [
        (_BATCH_QUESTION, True),
        (_AUTO_APPROVE_QUESTION, False),
        (_ATTRIBUTION_QUESTION, False),
    ]
    printed = {message: text for message, _, text in prompter.asked}
    assert _PI_NOTE in printed[_AUTO_APPROVE_QUESTION]
    assert _NO_KEY_NOTE in printed[_ATTRIBUTION_QUESTION]
    assert outcomes is not None
    home = Path.home()
    assert "bypassPermissions" in (home / ".claude" / "settings.json").read_text()
    assert "approval_policy" in (home / ".codex" / "config.toml").read_text()
    assert '"attribution"' not in (home / ".claude" / "settings.json").read_text()


def test_headless_yes_asks_nothing_and_says_so():
    """A7 / T-23-48: --yes asks no run-option question, turns no option on, and says so."""
    tools = [_tool("claude", "agent"), _tool("pi", "agent"), _tool("starship", "shell")]
    _, install = _recording_install()
    console, buf = _console()
    prompter = _ScriptedPrompter({}, buf)

    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )

    output = buf.getvalue()
    assert outcomes is not None
    assert prompter.asked == []
    assert not (Path.home() / ".claude" / "settings.json").exists()
    assert output.index(_LEFT_OFF) < output.index("Summary —")
    assert "Shell init left off (--yes): starship. Turn it on in Policies." in output


def test_the_headless_shell_init_question_is_keyed_and_default_no():
    """D-11 / R1-54: shell init asks its own sentence with default no; the login shell keeps yes."""
    tools = [_tool("zoxide", "shell"), _tool("oh-my-zsh", "shell")]
    console, buf = _console()
    prompter = _ScriptedPrompter({_BATCH_QUESTION: True}, buf)

    run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=_asking_install(
            [("zoxide", "source_shell_init"), ("oh-my-zsh", "set_login_shell")]
        ),
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )

    assert len(prompter.asked) == 3
    assert {(message, default) for message, default, _ in prompter.asked} == {
        (_BATCH_QUESTION, True),
        (_ZOXIDE_QUESTION, False),
        (_LOGIN_SHELL_QUESTION, True),
    }


def test_all_yes_on_an_all_current_host_runs_nothing_and_exits_zero_shaped():
    tools = [_tool("rg", "search"), _tool("fd", "search")]
    installed, install = _recording_install()
    prompter = FakePrompter(confirm=True)
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools, present={"rg", "fd"}),
        updates=ScriptedUpdates({}),
    )

    assert "Summary — 2 skipped" in buf.getvalue()
    assert installed == []
    assert isinstance(outcomes, list) and len(outcomes) == 2
    assert all(outcome.result == "skipped" for outcome in outcomes)
    assert exit_code(outcomes) == 0
    assert prompter.confirmed == 0


def test_all_current_without_yes_prints_the_plan_and_summary_without_asking():
    class MustNotConfirm(FakePrompter):
        def confirm(self, message: str, *, default: bool = True) -> bool:
            raise AssertionError("confirm must not be called")

    tools = [_tool("rg", "search"), _tool("fd", "search")]
    installed, install = _recording_install()
    prompter = MustNotConfirm(confirm=True)
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools, present={"rg", "fd"}),
        updates=ScriptedUpdates({}),
    )

    assert "Install plan — 2 skipped" in buf.getvalue()
    assert "Summary — 2 skipped" in buf.getvalue()
    assert installed == []
    assert isinstance(outcomes, list)
    assert all(outcome.result == "skipped" for outcome in outcomes)


@pytest.mark.parametrize("scenario", ["decline", "yes", "current", "failure"])
def test_run_wizard_commits_held_writes_only_after_consent(tmp_path: Path, scenario: str) -> None:
    events: list[str] = []
    tools = [_tool("rg", "search")]

    class RecordingService(FrozenStateService):
        def hold_writes(self) -> None:
            events.append("hold")
            super().hold_writes()

        def refresh(self, tools: Sequence[Tool]) -> None:
            events.append("refresh")
            if scenario == "failure":
                raise OSError("state check failed")
            super().refresh(tools)

        def refresh_skills(self, tools: Sequence[Tool]):
            events.append("refresh_skills")
            return super().refresh_skills(tools)

        def commit_writes(self) -> list[str]:
            events.append("commit")
            return super().commit_writes()

    service = RecordingService(
        platform=_platform(),
        cache_path=tmp_path / "versions.json",
        resolve_tag=_resolve_tag,
        probe_output=lambda _argv: None,
        managed_bin_dir=tmp_path / "bin",
        which=lambda _cmd: None,
        artifacts_for=lambda _tool: [],
        present=lambda _tool: scenario != "yes",
    )
    health = Health.MISSING if scenario in {"decline", "yes"} else Health.OK
    service.publish([plan_state(tools[0], health=health)])
    installed: list[str] = []

    def install(tool: Tool, *_args: object, **_kwargs: object) -> InstallOutcome:
        events.append(f"install:{tool.id}")
        installed.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    prompter = FakePrompter(confirm=scenario != "decline")
    result = run_wizard(
        tools,
        prompter,
        _console()[0],
        Options(all=True, categories=(), yes=scenario == "yes"),
        refresh=service,
        updates=ScriptedUpdates({}),
        install=install,
    )
    if scenario == "decline":
        assert events.index("hold") < events.index("refresh")
        assert "commit" not in events
    elif scenario == "yes":
        assert events.count("commit") == 1
        assert events.index("commit") < events.index("install:rg")
    elif scenario == "current":
        assert "commit" not in events and prompter.confirmed == 0
    else:
        assert "commit" not in events
        assert isinstance(result, list)


def test_headless_uses_the_same_plan_order_as_the_tui():
    node = _tool("node", "system")
    mmdc = Tool(
        id="mmdc",
        name="mmdc",
        category="user",
        cmd="mmdc",
        methods=(Method(kind="brew", params={"formula": "mmdc"}),),
        requires=("node",),
    )
    tools = [mmdc, node]
    refresh = presence_service(tools)
    expected = [
        row.tool_id
        for row in display_order(
            build_plan(["mmdc"], tools, refresh.state_of, refresh.platform, reinstall=frozenset())
        )
    ]
    console, buf = _console()

    run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=False, categories=("user",), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=_recording_install()[1],
        refresh=refresh,
        updates=ScriptedUpdates({}),
    )

    plan_output = buf.getvalue().split("Summary —", 1)[0]
    output_rows = [
        line.split()[1]
        for line in plan_output.splitlines()
        if len(line.split()) > 1 and line.split()[1] in expected
    ]
    assert output_rows == expected


def test_headless_all_settles_skill_packs_before_planning() -> None:
    tools = [_tool("rg", "search"), skill_pack_tool("superpowers")]
    refresh = offline_service(
        Path.home() / "versions.json",
        skill_home=Path.home(),
        resolve_tag=lambda _repo: (_ for _ in ()).throw(OSError("offline")),
        probe_output=lambda _argv: None,
        skill_probe=lambda _argv: "not json",
        present=lambda _tool: False,
    )
    installed, install = _recording_install()
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=refresh,
        updates=ScriptedUpdates({}),
    )

    assert "State check failed" not in buf.getvalue()
    assert isinstance(outcomes, list)
    assert all(outcome.result != "not_attempted" for outcome in outcomes)
    assert all(row.disposition.value != "wait" for row in (outcome.row for outcome in outcomes))
    assert "rg" in installed


def test_headless_reports_a_state_check_failure_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = [_tool("rg", "search")]
    installed, install = _recording_install()
    refresh = presence_service(tools, platform=_platform())

    def fail_refresh(_tools: list[Tool]) -> None:
        raise OSError("probe failed")

    monkeypatch.setattr(refresh, "refresh", fail_refresh)
    console, buf = _console()
    failed = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=refresh,
        updates=ScriptedUpdates({}),
    )
    assert "State check failed: probe failed" in buf.getvalue()
    assert isinstance(failed, list)
    assert [(outcome.result, outcome.detail) for outcome in failed] == [
        ("not_attempted", "probe failed")
    ]
    assert exit_code(failed) == 1
    assert installed == []

    empty_service = presence_service([], platform=_platform())
    refresh_without_state = presence_service(tools, service=empty_service)
    console, buf = _console()
    unsettled = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=refresh_without_state,
        updates=ScriptedUpdates({}),
    )
    assert "State check failed: no state for rg" in buf.getvalue()
    assert isinstance(unsettled, list)
    assert [(outcome.result, outcome.detail) for outcome in unsettled] == [
        ("not_attempted", "no state for rg")
    ]
    assert exit_code(unsettled) == 1
    assert installed == []


def test_headless_reports_refresh_errors_without_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = [_tool("rg", "search")]
    installed, install = _recording_install()
    refresh = presence_service(tools, platform=_platform())

    def fail_refresh(_tools: list[Tool]) -> None:
        raise OSError()

    monkeypatch.setattr(refresh, "refresh", fail_refresh)
    console, buf = _console()
    try:
        outcomes = run_wizard(
            tools,
            FakePrompter(confirm=True),
            console,
            Options(all=True, categories=(), yes=True),
            runner=_runner,
            resolve_tag=_resolve_tag,
            install=install,
            refresh=refresh,
            updates=ScriptedUpdates({}),
        )
    except IndexError as exc:
        pytest.fail(f"empty refresh error should produce outcomes, raised {exc!r}")

    assert "State check failed: OSError" in buf.getvalue()
    assert isinstance(outcomes, list)
    assert [outcome.result for outcome in outcomes] == ["not_attempted"]
    assert exit_code(outcomes) == 1
    assert installed == []


def test_headless_report_carries_a_successful_updates_extras() -> None:
    tool = _tool("jq", "data")
    tools = [tool]
    refresh = presence_service(
        tools,
        states=[plan_state(tool, health=Health.OUTDATED, owner="brew", method=tool.methods[0])],
        platform=_platform(),
    )
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=_recording_install()[1],
        refresh=refresh,
        updates=ScriptedUpdates(
            {
                "jq": UpdateOutcome(
                    "jq", "updated", "brew", detail="pnpm globals replay failed: boom"
                )
            }
        ),
    )

    assert "Summary — 1 updated" in buf.getvalue()
    assert "jq updated — pnpm globals replay failed: boom" in buf.getvalue()
    assert isinstance(outcomes, list)


def test_all_yes_updates_an_outdated_brew_tool_and_exits_zero() -> None:
    tool = _tool("jq", "data")
    tools = [tool]
    refresh = presence_service(
        tools,
        states=[plan_state(tool, health=Health.OUTDATED, owner="brew", method=tool.methods[0])],
        platform=_platform(),
    )
    updates = ScriptedUpdates({"jq": UpdateOutcome("jq", "updated", "brew")})
    installed, install = _recording_install()
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=refresh,
        updates=updates,
    )

    assert "Summary — 1 updated" in buf.getvalue()
    assert isinstance(outcomes, list) and [outcome.result for outcome in outcomes] == ["done"]
    assert exit_code(outcomes) == 0
    assert installed == []
    assert [target.tool.id for target in updates.targets] == ["jq"]


def test_an_injected_failing_row_exits_one() -> None:
    tools = [_tool("rg", "search")]

    def fail_install(
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

    console, buf = _console()
    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=fail_install,
        refresh=presence_service(tools, platform=_platform()),
        updates=ScriptedUpdates({}),
    )

    assert isinstance(outcomes, list)
    assert exit_code(outcomes) == 1
    assert "Summary — 1 failed" in buf.getvalue()


def test_a_blocked_row_plus_a_done_row_exits_zero() -> None:
    rg = _tool("rg", "search")
    apt_tool = Tool(
        id="apt-upgrade",
        name="apt-upgrade",
        category="pkg-mgr",
        cmd="apt-upgrade",
        methods=(Method(kind="apt", params={"package": "x"}),),
    )
    tools = [rg, apt_tool]
    installed, install = _recording_install()
    console, buf = _console()

    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools, platform=_platform()),
        updates=ScriptedUpdates({}),
    )

    assert isinstance(outcomes, list)
    assert {outcome.row.tool_id: outcome.result for outcome in outcomes} == {
        "rg": "done",
        "apt-upgrade": "blocked",
    }
    assert exit_code(outcomes) == 0
    assert installed == ["rg"]
    assert "Summary — 1 installed, 1 blocked" in buf.getvalue()


def test_all_flag_installs_every_tool_without_prompting():
    tools = _catalog()
    installed, install = _recording_install()
    prompter = FakePrompter(confirm=True)
    console, _buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert installed == ["rg", "fd", "jq"]
    assert isinstance(outcomes, list)
    assert [outcome.result for outcome in outcomes] == ["done", "done", "done"]
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

    tools = [_tool("rg", "search")]
    prompter = FakePrompter(confirm=True)
    console, _buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert isinstance(outcomes, list)
    assert [(outcome.row.tool_id, outcome.result) for outcome in outcomes] == [("rg", "failed")]


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

    tools = [_tool("sdkman", "pkg-mgr"), _tool("java", "dev", requires=("sdkman",))]
    console, buf = _console()
    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert isinstance(outcomes, list)
    assert [(outcome.row.tool_id, outcome.result) for outcome in outcomes] == [
        ("sdkman", "failed"),
        ("java", "dependency_failed"),
    ]
    assert "java    dependency failed — sdkman" in buf.getvalue()
    assert "skipped — dependency failed" not in buf.getvalue()
    assert called == ["sdkman"]


def test_categories_flag_filters_tools():
    tools = _catalog()
    installed, install = _recording_install()
    prompter = FakePrompter(confirm=True)
    console, _buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=False, categories=("data",), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert installed == ["jq"]
    assert isinstance(outcomes, list)


def test_declining_confirmation_installs_nothing():
    tools = _catalog()
    installed, install = _recording_install()
    prompter = FakePrompter(confirm=False)
    console, _buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert installed == []
    assert outcomes is None
    assert prompter.questions == ["Run this plan?"]


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
    removed, _failed = run_uninstall(
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
        runner=_no_removal_runner,
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
    removed, _failed = run_uninstall(
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
        runner=_no_removal_runner,
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

    removed, _failed = run_uninstall(
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
        runner=_no_removal_runner,
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

    tools = [_tool("rg", "search")]
    console, _buf = _console()
    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        on_mismatch=on_mismatch,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert asked == ["rg"]
    assert attempts == ["fail"]  # one install call, default policy
    assert isinstance(outcomes, list)
    assert [(outcome.row.tool_id, outcome.result) for outcome in outcomes] == [("rg", "mismatch")]


def test_wizard_suppresses_on_mismatch_under_yes():
    attempts, install = _mismatching_install()
    asked: list[str] = []

    def on_mismatch(tool_id: str) -> MismatchChoice:
        asked.append(tool_id)
        return "retry"

    tools = [_tool("rg", "search")]
    console, _buf = _console()
    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        on_mismatch=on_mismatch,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert asked == []  # unattended: never prompt, hard-fail stands
    assert isinstance(outcomes, list)
    assert [(outcome.row.tool_id, outcome.result) for outcome in outcomes] == [("rg", "mismatch")]
    assert attempts == ["fail"]


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
        runner=_no_removal_runner,
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
    from tests.test_uninstall import loop_tool

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
    decision = UninstallDecision(
        tools=(loop_tool("fd"),),
        paths={"fd": (artifact, opt)},
        remove_ban=False,
        remove_path_block=False,
    )
    perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=decision.tools,
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

    decision = UninstallDecision(tools=(), paths={}, remove_ban=True, remove_path_block=True)
    perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[myshellrc],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=decision.tools,
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
    outcomes = run_wizard(
        catalog,
        FakePrompter(confirm=True),
        console,
        Options(all=False, categories=("c",), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=record_install,
        refresh=presence_service(catalog),
        updates=ScriptedUpdates({}),
    )
    assert installed_order == ["pnpm", "mmdc"]
    assert isinstance(outcomes, list)


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

    decision = UninstallDecision(tools=(), paths={}, remove_ban=True, remove_path_block=False)
    perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=myshellrc,
        rc_paths=[rc],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=decision.tools,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
            runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=True
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
        runner=_no_removal_runner,
        catalog=decision.tools,
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
        tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=False
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
        runner=_no_removal_runner,
        catalog=decision.tools,
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
        tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=False
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
        runner=_no_removal_runner,
        catalog=decision.tools,
    )
    assert result.swept == ()
    assert plist_path.exists()  # untouched: the user did not select removal
    assert daemon.decided(state_path) is True  # marker preserved: still active


def test_perform_uninstall_requires_daemon_policy() -> None:
    from installer.app import UninstallDecision, perform_uninstall

    decision = UninstallDecision(tools=(), paths={}, remove_ban=False, remove_path_block=False)
    with pytest.raises(TypeError):
        perform_uninstall(  # type: ignore[call-arg]
            decision,
            bin_dir=Path("/tmp/bin"),
            myshellrc_path=Path("/tmp/rc"),
            rc_paths=[],
            bundles=(),
            zshrc_path=Path("/tmp/.zshrc"),
            runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
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
        tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=False
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
        runner=_no_removal_runner,
        catalog=decision.tools,
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
        runner=_no_removal_runner,
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
        runner=_no_removal_runner,
    )
    perform_uninstall(
        UninstallDecision(
            tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=False
        ),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=bare,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=(),
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
        runner=_no_removal_runner,
    )
    perform_uninstall(
        UninstallDecision(
            tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=True
        ),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=state_path,
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=swept,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=(),
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
        runner=_no_removal_runner,
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
        UninstallDecision(
            tools=(), paths={}, remove_ban=False, remove_path_block=False, remove_tweaks=True
        ),
        bin_dir=tmp_path / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(again,),
        runner=_no_removal_runner,
        catalog=(),
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
            runner=_no_removal_runner,
        )
    with pytest.raises(TypeError):
        perform_uninstall(  # type: ignore[call-arg]
            UninstallDecision(tools=(), paths={}, remove_ban=False, remove_path_block=False),
            bin_dir=tmp_path / "bin",
            myshellrc_path=tmp_path / ".myshellrc",
            rc_paths=[],
            bundles=(),
            zshrc_path=tmp_path / ".zshrc",
            daemon_policy=None,
            runner=_no_removal_runner,
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

    tools = [_tool("codegraph", "dev")]
    console, buf = _console()
    outcomes = run_wizard(
        tools,
        FakePrompter(confirm=True),
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert isinstance(outcomes, list)
    out = buf.getvalue()
    assert "codegraph" in out
    assert "codegraph MCP registration failed: exit 1" in out


def test_run_wizard_install_takes_no_catalog() -> None:
    seen: dict[str, bool] = {}

    def install(
        tool: Tool,
        platform: Platform,
        runner: Runner,
        resolve_tag: TagResolver,
        *,
        checksum_policy: ChecksumPolicy = "fail",
        confirm_sensitive_action: ConfirmSensitiveAction | None = None,
    ) -> InstallOutcome:
        seen["ran"] = True
        return InstallOutcome(tool.id, "installed", method_kind="brew")

    catalog_tools = _catalog()
    run_wizard(
        catalog_tools,
        FakePrompter(confirm=True),
        _console()[0],
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        install=install,
        refresh=presence_service(catalog_tools),
        updates=ScriptedUpdates({}),
    )
    assert seen == {"ran": True}


def _login_shell_tool() -> Tool:
    return Tool(
        id="oh-my-zsh",
        name="Oh My Zsh",
        category="shell",
        cmd="omz",
        methods=(Method(kind="script", params={"url": "u"}),),
        post_install=("set_login_shell",),
    )


def _not_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import installer.engine as engine

    def fake_not_installed(tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", fake_not_installed)
    sandbox = tmp_path / "path-sandbox"
    sandbox.mkdir()
    monkeypatch.setenv("PATH", str(sandbox))


def test_run_wizard_prints_login_shell_instructions_when_sensitive_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_present(monkeypatch, tmp_path)
    prompter = FakePrompter(confirm=True)
    tools = [_login_shell_tool()]
    console, buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    out = buf.getvalue()
    assert isinstance(outcomes, list)
    assert outcomes[0].result == "done"
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
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_present(monkeypatch, tmp_path)
    prompter = FakePrompter(confirm=True, sensitive_confirm=False)
    tools = [_login_shell_tool()]
    console, buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert isinstance(outcomes, list)
    assert outcomes[0].result == "done"
    assert "chsh -s" not in buf.getvalue()


def test_run_wizard_sensitive_unattended_never_asks_and_prints_no_instructions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_which(cmd: str) -> str | None:
        return "/usr/bin/chsh" if cmd == "chsh" else None

    monkeypatch.setattr("installer.post_install.shutil.which", fake_which)
    _not_present(monkeypatch, tmp_path)
    prompter = FakePrompter(confirm=True)
    tools = [_login_shell_tool()]
    console, buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=True),
        runner=_runner,
        resolve_tag=_resolve_tag,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert isinstance(outcomes, list)
    assert outcomes[0].result == "done"
    assert prompter.questions == []
    assert "chsh -s" not in buf.getvalue()


def test_run_wizard_never_asks_sensitive_question_without_login_shell_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _not_present(monkeypatch, tmp_path)
    prompter = FakePrompter(confirm=True)
    tools = [_tool("rg", "search")]
    console, buf = _console()
    outcomes = run_wizard(
        tools,
        prompter,
        console,
        Options(all=True, categories=(), yes=False),
        runner=_runner,
        resolve_tag=_resolve_tag,
        refresh=presence_service(tools),
        updates=ScriptedUpdates({}),
    )
    assert isinstance(outcomes, list)
    assert outcomes[0].result == "done"
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
    runner: Runner


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
        "runner": _no_removal_runner,
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
    removed, _failed = run_uninstall(
        tools, console, **_uninstall_kwargs(tmp_path, bin_dir, lambda _m: True)
    )
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
    removed, _failed = run_uninstall(
        tools, console, **_uninstall_kwargs(tmp_path, bin_dir, fail_confirm)
    )
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
    first, _ = run_uninstall(tools, console, **kwargs)
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
    second, _ = run_uninstall(
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
    removed, _failed = run_uninstall(
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
    removed, _failed = run_uninstall(
        [tool],
        console,
        **_uninstall_kwargs(tmp_path, bin_dir, swap_then_confirm),
    )
    assert removed == []
    assert (bin_dir / "fd").read_text() == "foreign file"  # the replacement survives
    assert opt.exists()  # the opt dir is no longer proven either
    assert "changed since the preview" in buf.getvalue()
    assert str(bin_dir / "fd") in buf.getvalue()


def test_run_uninstall_uses_receipt_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI `--yes` path removes a receipt-proven raw download (no layout
    could prove it) and never a tampered receipt's `~/.ssh` decoy (D-10)."""
    from installer import receipts
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_raw_yq, write_receipt

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = tmp_path / ".ssh" / "id_ed25519"
    key.parent.mkdir(parents=True)
    key.write_text("PRIVATE KEY")
    yq, bin_dir = plant_raw_yq(tmp_path, with_receipt=False)
    write_receipt(yq, [(bin_dir / "yq", "file"), (key, "file")])
    console, _buf = _console()
    removed, _failed = run_uninstall(
        [yq], console, **_uninstall_kwargs(tmp_path, bin_dir, lambda _m: True)
    )
    assert removed == [bin_dir / "yq"]
    assert not (bin_dir / "yq").exists()
    assert key.read_text() == "PRIVATE KEY"
    assert receipts.read("yq") is None


def test_perform_uninstall_reproves_per_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI deletes through the same receipt-aware remover as the CLI
    (L-19-06): a receipt-proven raw yq is removed and its receipt retired; a
    drifted one is refused through SweepResult.warnings."""
    from installer import receipts
    from installer.app import UninstallDecision, perform_uninstall
    from tests.test_uninstall import plant_raw_yq

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("")

    def apply(decision: UninstallDecision) -> SweepResult:
        return perform_uninstall(
            decision,
            bin_dir=bin_dir,
            myshellrc_path=myshellrc,
            rc_paths=[],
            bundles=(),
            zshrc_path=tmp_path / ".zshrc",
            daemon_policy=None,
            extra_policies=(),
            runner=_no_removal_runner,
            catalog=decision.tools,
        )

    yq, bin_dir = plant_raw_yq(tmp_path)
    decision = UninstallDecision(
        tools=(yq,), paths={"yq": (bin_dir / "yq",)}, remove_ban=False, remove_path_block=False
    )
    assert apply(decision).warnings == ()
    assert not (bin_dir / "yq").exists()
    assert receipts.read("yq") is None

    yq, bin_dir = plant_raw_yq(tmp_path)
    (bin_dir / "yq").write_text("rewritten after install, a different size")
    result = apply(decision)
    assert result.warnings == (f"changed since the preview; not removed: {bin_dir / 'yq'}",)
    assert (bin_dir / "yq").exists()
    assert receipts.read("yq") is not None


def _sweep_two_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Callable[[UninstallDecision], SweepResult], Tool, Tool, Path]:
    """A scratch HOME holding a receipt-proven raw yq and the layout-proven fd."""
    from installer.app import perform_uninstall
    from tests.test_uninstall import plant_raw_yq, plant_removal_fixtures

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd = next(t for t in plant_removal_fixtures(tmp_path) if t.id == "fd")
    yq, bin_dir = plant_raw_yq(tmp_path)
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("")

    def apply(decision: UninstallDecision) -> SweepResult:
        return perform_uninstall(
            decision,
            bin_dir=bin_dir,
            myshellrc_path=myshellrc,
            rc_paths=[],
            bundles=(),
            zshrc_path=tmp_path / ".zshrc",
            daemon_policy=None,
            extra_policies=(),
            runner=_no_removal_runner,
            catalog=decision.tools,
        )

    return apply, yq, fd, bin_dir


def test_perform_uninstall_reports_each_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-08/D-11: each selected tool is removed on its own and named in `removed`."""
    apply, yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    decision = UninstallDecision(
        tools=(yq, fd),
        paths={"yq": (bin_dir / "yq",), "fd": (bin_dir / "fd", opt_fd)},
        remove_ban=False,
        remove_path_block=False,
    )
    result = apply(decision)
    assert result.removed == ("yq", "fd")
    assert result.remove_failed == ()
    assert result.warnings == ()
    assert not (bin_dir / "yq").exists()
    assert not (bin_dir / "fd").is_symlink()
    assert not opt_fd.exists()


def test_perform_uninstall_reports_a_refused_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool whose proof drifted is `remove_failed` with the refusal line."""
    apply, yq, _fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    (bin_dir / "yq").write_text("rewritten after install, a different size")
    decision = UninstallDecision(
        tools=(yq,), paths={"yq": (bin_dir / "yq",)}, remove_ban=False, remove_path_block=False
    )
    result = apply(decision)
    line = f"changed since the preview; not removed: {bin_dir / 'yq'}"
    assert result.remove_failed == (("yq", line),)
    assert result.removed == ()
    assert result.warnings == (line,)


def _raising_remove_proven(monkeypatch: pytest.MonkeyPatch, bad: str, error: OSError) -> None:
    """Make `installer.app.remove_proven` raise `error` for the tool `bad` only."""
    from installer import app as app_module

    real = app_module.remove_proven

    def wrapper(
        tools: list[Tool], paths: list[Path], bin_dir: Path
    ) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        if tools[0].id == bad:
            raise error
        return real(tools, paths, bin_dir)

    monkeypatch.setattr(app_module, "remove_proven", wrapper)


def test_perform_uninstall_one_failed_delete_does_not_stop_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-08: fd's delete raises; yq is still removed and the ban lever still runs."""
    apply, yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    _raising_remove_proven(monkeypatch, "fd", OSError("disk full\nsecond line"))
    from installer.guards import guard_status, install_shims

    install_shims(bin_dir)
    assert any(guard_status(bin_dir).values())
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    decision = UninstallDecision(
        tools=(yq, fd),
        paths={"yq": (bin_dir / "yq",), "fd": (bin_dir / "fd", opt_fd)},
        remove_ban=True,
        remove_path_block=False,
    )
    result = apply(decision)
    assert result.removed == ("yq",)
    assert result.remove_failed == (("fd", "disk full"),)
    assert not (bin_dir / "yq").exists()
    assert (bin_dir / "fd").is_symlink()
    assert all(active is False for active in guard_status(bin_dir).values())


def test_perform_uninstall_a_planning_error_does_not_stop_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-15: planning fd raises (a non-searchable parent); yq is still removed,
    fd is `remove_failed`, and the ban lever still runs."""
    from installer import app as app_module
    from installer.guards import guard_status, install_shims

    apply, yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    real = app_module.removal_plan

    def plan(tool: Tool, default_bin_dir: Path, *, verify: bool = False) -> RemovalPlan:
        if tool.id == "fd":
            raise PermissionError("permission denied: opt")
        return real(tool, default_bin_dir, verify=verify)

    # remove_tool plans through removal_plan (the post-confirm proof, review R1-10).
    monkeypatch.setattr(app_module, "removal_plan", plan)
    install_shims(bin_dir)
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    decision = UninstallDecision(
        tools=(fd, yq),
        paths={"fd": (bin_dir / "fd", opt_fd), "yq": (bin_dir / "yq",)},
        remove_ban=True,
        remove_path_block=False,
    )
    result = apply(decision)
    assert result.removed == ("yq",)
    assert result.remove_failed == (("fd", "permission denied: opt"),)
    assert all(active is False for active in guard_status(bin_dir).values())


def test_perform_uninstall_an_empty_error_reads_its_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply, _yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    _raising_remove_proven(monkeypatch, "fd", OSError())
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    decision = UninstallDecision(
        tools=(fd,),
        paths={"fd": (bin_dir / "fd", opt_fd)},
        remove_ban=False,
        remove_path_block=False,
    )
    assert apply(decision).remove_failed == (("fd", "OSError failed"),)


def test_perform_uninstall_a_tool_with_nothing_left_is_remove_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apply, _yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    decision = UninstallDecision(
        tools=(fd,),
        paths={"fd": (bin_dir / "fd", opt_fd)},
        remove_ban=False,
        remove_path_block=False,
    )
    (bin_dir / "fd").unlink()
    shutil.rmtree(opt_fd)
    result = apply(decision)
    assert result.remove_failed == (("fd", "changed since the preview; not removed"),)
    assert any(str(bin_dir / "fd") in w for w in result.warnings)
    assert any(str(opt_fd) in w for w in result.warnings)


def test_perform_uninstall_names_only_the_previewed_paths_that_dropped_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR-05: a whole-tool refusal names the paths that changed, not the
    unchanged ones the tool keeps."""
    apply, _yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    gone = tmp_path / ".local" / "opt" / "fd-old"
    decision = UninstallDecision(
        tools=(fd,),
        paths={"fd": (bin_dir / "fd", opt_fd, gone)},
        remove_ban=False,
        remove_path_block=False,
    )
    result = apply(decision)
    assert result.remove_failed == (("fd", "changed since the preview; not removed"),)
    assert result.warnings == (f"changed since the preview; not removed: {gone}",)
    assert (bin_dir / "fd").exists()


def test_perform_uninstall_refuses_a_plan_that_grew_since_the_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR-05: a reinstall that added a path after the preview is a change too;
    the tool is not reported removed and keeps its files."""
    apply, _yq, fd, bin_dir = _sweep_two_tools(tmp_path, monkeypatch)
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    decision = UninstallDecision(
        tools=(fd,),
        paths={"fd": (bin_dir / "fd",)},
        remove_ban=False,
        remove_path_block=False,
    )
    result = apply(decision)
    assert result.removed == ()
    assert result.remove_failed == (("fd", "changed since the preview; not removed"),)
    assert result.warnings == (f"changed since the preview; not removed: {opt_fd}",)
    assert (bin_dir / "fd").is_symlink()
    assert opt_fd.exists()


def test_perform_uninstall_refuses_paths_changed_since_the_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI apply path re-checks the same proof at deletion time (H1):
    a still-proven link is removed, a replaced one is refused with a warning."""
    from installer.app import UninstallDecision, perform_uninstall
    from tests.test_uninstall import plant_removal_fixtures

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    fd = next(t for t in plant_removal_fixtures(tmp_path) if t.id == "fd")
    bin_dir = tmp_path / ".local" / "bin"
    opt_fd = tmp_path / ".local" / "opt" / "fd"
    myshellrc = tmp_path / ".myshellrc"
    myshellrc.write_text("")

    # fd's link is swapped for a foreign file after the preview was rendered.
    (bin_dir / "fd").unlink()
    (bin_dir / "fd").write_text("foreign file")

    decision = UninstallDecision(
        tools=(fd,),
        paths={"fd": (bin_dir / "fd", opt_fd)},
        remove_ban=False,
        remove_path_block=False,
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
        runner=_no_removal_runner,
        catalog=decision.tools,
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
        tools=(fd,),
        paths={"fd": (bin_dir / "fd", opt_fd)},
        remove_ban=False,
        remove_path_block=False,
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
        runner=_no_removal_runner,
        catalog=decision.tools,
    )
    assert result.warnings == ()
    assert not (bin_dir / "fd").is_symlink()
    assert not opt_fd.exists()


def _no_removal_runner(cmd: list[str]) -> None:
    raise AssertionError(f"no removal command expected: {cmd}")


def _vend_tool(
    *,
    tool_id: str = "vend",
    paths: tuple[str, ...] = ("~/.local/bin/vend",),
    remove: tuple[str, ...] = ("vend", "uninstall", "--force"),
) -> Tool:
    """A test-local recipe: one script method with a vendor `remove` (not registry data)."""
    return Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(Method(kind="script", params={"paths": list(paths), "remove": list(remove)}),),
    )


def _vend_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, tool: Tool | None = None
) -> tuple[Tool, Path]:
    """Plant the tool's declared paths under HOME, record its receipt; return (tool, bin dir)."""
    from installer import receipts

    monkeypatch.setenv("HOME", str(tmp_path))
    tool = tool or _vend_tool()
    for entry in cast(list[str], tool.methods[0].params["paths"]):
        planted = tmp_path / str(entry).removeprefix("~/")
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(tool.id)
    receipts.record(tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset())
    return tool, tmp_path / ".local" / "bin"


def _perform(
    tool: Tool,
    home: Path,
    *,
    paths: tuple[Path, ...],
    argv: tuple[str, ...],
    runner: Runner,
) -> SweepResult:
    from installer.app import UninstallDecision, perform_uninstall

    decision = UninstallDecision(
        tools=(tool,),
        paths={tool.id: paths},
        argv={tool.id: argv},
        remove_ban=False,
        remove_path_block=False,
    )
    return perform_uninstall(
        decision,
        bin_dir=home / ".local" / "bin",
        myshellrc_path=home / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=home / ".zshrc",
        daemon_policy=None,
        runner=runner,
        catalog=(tool,),
        extra_policies=(),
    )


def test_a_recipe_tool_is_removed_by_its_vendor_command_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    binary = bin_dir / "vend"
    plan = removal_plan(tool, bin_dir)
    assert plan.level == "recipe"
    assert plan.argv == (str(binary), "uninstall", "--force")
    assert binary in plan.removable
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)  # the fake vendor command deletes nothing

    result = _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=runner)
    assert calls == [[str(binary), "uninstall", "--force"]]
    assert not binary.exists()
    assert receipts.read("vend") is None
    assert result.removed == ("vend",)


def test_the_vendor_command_runs_before_any_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(tool, bin_dir)
    seen: list[bool] = []

    def runner(_cmd: list[str]) -> None:
        seen.append((bin_dir / "vend").exists())

    _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=runner)
    assert seen == [True]


def test_a_failing_remove_deletes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(tool, bin_dir)

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="Error: vend uninstall failed")

    result = _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=runner)
    assert (bin_dir / "vend").exists()
    assert receipts.receipt_path("vend").exists()
    assert result.remove_failed == (("vend", "Error: vend uninstall failed"),)
    assert result.removed == ()


def test_a_vendor_remove_that_deleted_the_binary_is_a_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(tool, bin_dir)

    def runner(_cmd: list[str]) -> None:
        (bin_dir / "vend").unlink()

    result = _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=runner)
    assert result.removed == ("vend",)
    assert result.remove_failed == ()
    assert not receipts.receipt_path("vend").exists()


def test_a_changed_argv_is_refused_like_a_changed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(tool, bin_dir)
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    stale = ("/elsewhere/vend", "uninstall", "--force")
    result = _perform(tool, tmp_path, paths=plan.removable, argv=stale, runner=runner)
    assert calls == []
    assert (bin_dir / "vend").exists()
    assert result.remove_failed == (("vend", "changed since the preview; not removed"),)


def test_a_recipe_command_that_names_no_proven_path_has_no_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import removal_plan

    # The command's first word names no leaf the receipt proves: nothing is bound, nothing runs.
    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch, tool=_vend_tool(remove=("othercli", "x")))
    plan = removal_plan(tool, bin_dir)
    assert plan.level == "recipe"
    assert plan.argv == ()
    assert (bin_dir / "vend") in plan.removable

    # The receipt proves a leaf named `other`, but the command's first word is `vend`.
    other_tool = _vend_tool(
        tool_id="vend2", paths=("~/.local/bin/other",), remove=("vend", "uninstall")
    )
    other, _same_bin = _vend_recorded(tmp_path, monkeypatch, tool=other_tool)
    assert removal_plan(other, bin_dir).argv == ()

    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)

    _perform(tool, tmp_path, paths=plan.removable, argv=(), runner=runner)
    assert calls == []


def test_a_drifted_previewed_path_fails_the_tool_and_keeps_its_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan
    from tests.test_uninstall import plant_raw_yq

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yq, bin_dir = plant_raw_yq(tmp_path)
    previewed = (bin_dir / "yq",)
    (bin_dir / "yq").write_text("rewritten after the preview, a different size")
    result = _perform(yq, tmp_path, paths=previewed, argv=(), runner=_no_removal_runner)
    assert result.removed == ()
    assert result.remove_failed == (
        ("yq", f"changed since the preview; not removed: {bin_dir / 'yq'}"),
    )
    assert (bin_dir / "yq").exists()
    assert receipts.read("yq") is not None

    # A recipe leaf replaced after the preview: refused before the command runs. Script
    # leaves are proven by type only (ledger Q3), so the replacement is a symlink, not bytes.
    recipe, recipe_bin = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(recipe, recipe_bin)
    (recipe_bin / "vend").unlink()
    (recipe_bin / "vend").symlink_to(tmp_path / "elsewhere")
    refused = _perform(
        recipe, tmp_path, paths=plan.removable, argv=plan.argv, runner=_no_removal_runner
    )
    assert refused.removed == ()
    assert refused.remove_failed[0][0] == "vend"
    assert (recipe_bin / "vend").is_symlink()
    assert receipts.receipt_path("vend").exists()


def _manager_tool(tool_id: str, method: Method, *, requires: tuple[str, ...] = ()) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(method,),
        requires=requires,
    )


def test_a_receipt_proven_brew_package_runs_brew_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(kind="brew", params={"formula": "gh"})
    gh = _manager_tool("gh", method)
    receipts.record(gh, method, package="gh", smoke=None)
    plan = removal_plan(gh, tmp_path / ".local" / "bin")
    assert (plan.level, plan.argv) == ("manager", ("brew", "uninstall", "gh"))
    calls: list[list[str]] = []
    result = _perform(gh, tmp_path, paths=(), argv=plan.argv, runner=calls.append)
    assert calls == [["brew", "uninstall", "gh"]]
    assert result.removed == ("gh",)
    assert not receipts.receipt_path("gh").exists()


def test_a_brew_package_without_a_receipt_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    gh = _manager_tool("gh", Method(kind="brew", params={"formula": "gh"}))
    plan = removal_plan(gh, tmp_path / ".local" / "bin")
    assert (plan.level, plan.argv) == ("none", ())
    result = _perform(gh, tmp_path, paths=(), argv=(), runner=_no_removal_runner)
    assert result.removed == ()
    assert result.remove_failed == (("gh", "changed since the preview; not removed"),)


def test_a_receipt_for_another_package_is_no_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(kind="brew", params={"formula": "gh"})
    gh = _manager_tool("gh", method)
    receipts.record(gh, method, package="other", smoke=None)
    assert removal_plan(gh, tmp_path / ".local" / "bin").level == "none"


def test_cask_uv_and_pnpm_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer import app as app_module
    from installer import receipts
    from installer.model import method_package
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    cases = [
        (
            Method(kind="cask", params={"cask": "visual-studio-code"}),
            ("brew", "uninstall", "--cask", "visual-studio-code"),
        ),
        (Method(kind="uv-tool", params={"pypi_pkg": "ruff"}), ("uv", "tool", "uninstall", "ruff")),
        (
            Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"}),
            ("pnpm", "remove", "--global", "@mermaid-js/mermaid-cli"),
        ),
    ]
    for method, argv in cases:
        tool = _manager_tool(f"t-{method.kind}", method)
        receipts.record(tool, method, package=method_package(method), smoke=None)
        assert (removal_plan(tool, bin_dir).level, removal_plan(tool, bin_dir).argv) == (
            "manager",
            argv,
        )

    fake_pnpm = tmp_path / "pnpm"
    fake_pnpm.write_text("")
    monkeypatch.setattr(app_module, "real_pnpm", lambda: str(fake_pnpm))
    node = _manager_tool("t-node", cases[2][0])
    calls: list[list[str]] = []
    _perform(
        node,
        tmp_path,
        paths=(),
        argv=("pnpm", "remove", "--global", "@mermaid-js/mermaid-cli"),
        runner=calls.append,
    )
    # The bare `pnpm` in the preview becomes the executor's absolute pnpm at run time.
    assert calls == [[str(fake_pnpm), "remove", "--global", "@mermaid-js/mermaid-cli"]]

    monkeypatch.setattr(app_module, "real_pnpm", lambda: None)
    # The first removal retired the receipt; the second case starts from the same proof again.
    receipts.record(node, cases[2][0], package="@mermaid-js/mermaid-cli", smoke=None)
    refused: list[list[str]] = []
    result = _perform(
        node,
        tmp_path,
        paths=(),
        argv=("pnpm", "remove", "--global", "@mermaid-js/mermaid-cli"),
        runner=refused.append,
    )
    assert refused == []
    assert result.remove_failed == (("t-node", "pnpm not found on PATH"),)


def test_a_native_owned_tool_has_no_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    dnf = _manager_tool("jq", Method(kind="dnf", params={"package": "jq"}))
    assert (removal_plan(dnf, bin_dir).level, removal_plan(dnf, bin_dir).argv) == ("none", ())
    sdk_method = Method(kind="sdkman", params={"candidate": "java"})
    sdk = _manager_tool("sdk", sdk_method)
    receipts.record(sdk, sdk_method, package="java", smoke=None)
    plan = removal_plan(sdk, bin_dir)
    assert (plan.level, plan.argv) == ("none", ())


def test_removing_an_already_removed_script_tool_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(tool, bin_dir)
    _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=lambda _cmd: None)
    again = removal_plan(tool, bin_dir)
    assert (again.level, again.argv) == ("none", ())


def test_an_interrupt_after_the_vendor_remove_keeps_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import app as app_module
    from installer import receipts
    from installer.uninstall import removal_plan

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    plan = removal_plan(tool, bin_dir)

    def vendor(_cmd: list[str]) -> None:
        (bin_dir / "vend").unlink()  # the vendor removed the binary, then the user hit Ctrl+C

    def interrupted(_artifacts: object, **_kwargs: object) -> tuple[Path, ...]:
        raise KeyboardInterrupt

    monkeypatch.setattr(app_module, "remove_paths", interrupted)
    with pytest.raises(KeyboardInterrupt):
        _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=vendor)
    assert receipts.receipt_path("vend").exists()
    receipt = receipts.read("vend")
    assert receipt is not None
    assert receipts.broken_drift(receipt)
    after = removal_plan(tool, bin_dir)
    assert (after.level, after.argv) == ("none", ())


def test_an_old_script_receipt_lists_declared_paths_as_yours_to_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    tool = _vend_tool(remove=())
    binary = bin_dir / "vend"
    binary.write_text("vend, installed before this phase")
    # Pre-phase shape: the path existed before the install, so no proof was recorded.
    receipts.record(
        tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset({binary})
    )
    plan = removal_plan(tool, bin_dir)
    assert plan.removable == ()
    assert binary in plan.yourself
    assert (plan.level, plan.argv) == ("none", ())


def test_an_empty_legacy_script_receipt_never_runs_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    tool = _vend_tool()  # declares a vendor `remove`
    binary = bin_dir / "vend"
    binary.write_text("vend, installed before this phase")
    receipts.record(
        tool, tool.methods[0], package=None, smoke=None, preexisting=frozenset({binary})
    )
    plan = removal_plan(tool, bin_dir)
    assert (plan.level, plan.argv) == ("none", ())
    calls: list[list[str]] = []
    _perform(tool, tmp_path, paths=plan.removable, argv=plan.argv, runner=calls.append)
    assert calls == []
    assert binary.exists()


def test_removal_order_puts_dependents_first() -> None:
    from installer.app import removal_order

    uv = _manager_tool("uv", Method(kind="brew", params={"formula": "uv"}))
    ruff = _manager_tool("ruff", Method(kind="brew", params={"formula": "ruff"}), requires=("uv",))
    jq = _manager_tool("jq", Method(kind="brew", params={"formula": "jq"}))
    assert [t.id for t in removal_order([uv, ruff, jq])] == ["ruff", "uv", "jq"]
    independent = [uv, jq]
    assert [t.id for t in removal_order(independent)] == ["uv", "jq"]


def test_perform_uninstall_removes_a_dependent_before_its_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import UninstallDecision, perform_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    uv_binary = bin_dir / "uv"
    uv_binary.write_text("uv")
    uv_method = Method(kind="script", params={"paths": ["~/.local/bin/uv"]})
    uv = _manager_tool("uv", uv_method)
    receipts.record(uv, uv_method, package=None, smoke=None, preexisting=frozenset())
    ruff_method = Method(kind="uv-tool", params={"pypi_pkg": "ruff"})
    ruff = _manager_tool("ruff", ruff_method, requires=("uv",))
    receipts.record(ruff, ruff_method, package="ruff", smoke=None)
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        assert uv_binary.exists(), "the dependent ran after its manager was removed"

    decision = UninstallDecision(
        tools=(uv, ruff),
        paths={"uv": (uv_binary,), "ruff": ()},
        argv={"ruff": ("uv", "tool", "uninstall", "ruff")},
        remove_ban=False,
        remove_path_block=False,
    )
    result = perform_uninstall(
        decision,
        bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        runner=runner,
        catalog=decision.tools,
        extra_policies=(),
    )
    assert calls == [["uv", "tool", "uninstall", "ruff"]]
    assert result.removed == ("ruff", "uv")
    assert not uv_binary.exists()


def test_the_cli_previews_and_runs_the_vendor_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    binary = bin_dir / "vend"
    console, buf = _console()
    shown: list[str] = []
    calls: list[list[str]] = []

    def confirm(_message: str) -> bool:
        shown.append(buf.getvalue())  # what the user saw when asked
        return True

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        binary.unlink()  # the vendor command removes the binary

    kwargs = _uninstall_kwargs(tmp_path, bin_dir, confirm)
    kwargs["runner"] = runner
    removed, failed = run_uninstall([tool], console, **kwargs)
    assert f"vend: runs {binary} uninstall --force" in shown[0]
    assert calls == [[str(binary), "uninstall", "--force"]]
    assert removed == [binary]
    assert failed == ()
    assert not binary.exists()


def test_the_cli_declines_and_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.app import run_uninstall

    tool, bin_dir = _vend_recorded(tmp_path, monkeypatch)
    console, _buf = _console()
    calls: list[list[str]] = []
    kwargs = _uninstall_kwargs(tmp_path, bin_dir, lambda _m: False)
    kwargs["runner"] = calls.append
    assert run_uninstall([tool], console, **kwargs) == ([], ())
    assert calls == []
    assert (bin_dir / "vend").exists()
    assert receipts_exist(tool)


def receipts_exist(tool: Tool) -> bool:
    from installer import receipts

    return receipts.receipt_exists(tool.id)


def test_a_foreign_file_at_a_declared_path_survives_the_cli_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    tool = _vend_tool()
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    foreign = bin_dir / "vend"
    foreign.write_text("a file this installer never wrote")  # declared, never recorded
    console, buf = _console()
    assert run_uninstall(
        [tool], console, **_uninstall_kwargs(tmp_path, bin_dir, lambda _m: True)
    ) == (
        [],
        (),
    )
    assert foreign.read_text() == "a file this installer never wrote"
    assert str(foreign) in buf.getvalue()


def test_a_cli_tool_with_only_an_argv_is_not_nothing_to_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import run_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(kind="brew", params={"formula": "gh"})
    gh = _manager_tool("gh", method)
    receipts.record(gh, method, package="gh", smoke=None)
    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()
    kwargs = _uninstall_kwargs(tmp_path, bin_dir, lambda _m: False)
    run_uninstall([gh], console, **kwargs)
    assert "gh: runs brew uninstall gh" in buf.getvalue()


def test_the_cli_re_proves_after_the_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import run_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(kind="brew", params={"formula": "gh"})
    gh = _manager_tool("gh", method)
    receipts.record(gh, method, package="gh", smoke=None)
    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()
    calls: list[list[str]] = []

    def confirm(_message: str) -> bool:
        # The receipt is rewritten between the preview and the answer (a reinstall).
        receipts.record(gh, method, package="other", smoke=None)
        return True

    kwargs = _uninstall_kwargs(tmp_path, bin_dir, confirm)
    kwargs["runner"] = calls.append
    removed, failed = run_uninstall([gh], console, **kwargs)
    assert calls == []
    assert removed == []
    assert failed == ("gh",)
    assert "gh: remove failed — changed since the preview; not removed" in buf.getvalue()


def test_the_cli_removes_a_dependent_before_its_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import run_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    uv_binary = bin_dir / "uv"
    uv_binary.write_text("uv")
    uv_method = Method(kind="script", params={"paths": ["~/.local/bin/uv"]})
    uv = _manager_tool("uv", uv_method)
    receipts.record(uv, uv_method, package=None, smoke=None, preexisting=frozenset())
    ruff_method = Method(kind="uv-tool", params={"pypi_pkg": "ruff"})
    ruff = _manager_tool("ruff", ruff_method, requires=("uv",))
    receipts.record(ruff, ruff_method, package="ruff", smoke=None)
    console, _buf = _console()
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        assert uv_binary.exists(), "the dependent ran after its manager was removed"

    kwargs = _uninstall_kwargs(tmp_path, bin_dir, lambda _m: True)
    kwargs["runner"] = runner
    _removed, failed = run_uninstall([uv, ruff], console, **kwargs)
    assert calls == [["uv", "tool", "uninstall", "ruff"]]
    assert failed == ()
    assert not uv_binary.exists()


def test_a_failed_cli_removal_is_reported_and_keeps_its_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import run_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(kind="brew", params={"formula": "gh"})
    gh = _manager_tool("gh", method)
    receipts.record(gh, method, package="gh", smoke=None)
    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="Error: No such formula")

    kwargs = _uninstall_kwargs(tmp_path, bin_dir, lambda _m: True)
    kwargs["runner"] = runner
    removed, failed = run_uninstall([gh], console, **kwargs)
    assert removed == []
    assert failed == ("gh",)
    assert "gh: remove failed — Error: No such formula" in buf.getvalue()
    assert receipts.receipt_exists("gh")


SHARED = ("~/.config/shared",)


def _brew_config_tool(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool_id: str = "gh",
    *,
    config_paths: tuple[str, ...] = ("~/.config/gh",),
) -> Tool:
    """A brew tool whose receipt proves its package, declaring `config_paths` (LIFE-04 shape)."""
    from installer import receipts

    monkeypatch.setenv("HOME", str(home))
    method = Method(kind="brew", params={"formula": tool_id})
    tool = Tool(
        id=tool_id,
        name=tool_id,
        category="dev",
        cmd=tool_id,
        methods=(method,),
        config_paths=config_paths,
    )
    receipts.record(tool, method, package=tool_id, smoke=None)
    return tool


def _plant_config(home: Path, rel: str) -> Path:
    config = home / rel
    config.mkdir(parents=True, exist_ok=True)
    (config / "hosts.yml").write_text("token")
    return config


def _decision(
    tools: Sequence[Tool], home: Path, *, config: Mapping[str, tuple[Path, ...]] | None = None
) -> UninstallDecision:
    """The preview a user would confirm: each tool's proven paths and manager argv."""
    from installer.uninstall import removal_plan

    bin_dir = home / ".local" / "bin"
    plans = {tool.id: removal_plan(tool, bin_dir) for tool in tools}
    return UninstallDecision(
        tools=tuple(tools),
        paths={tool_id: plan.removable for tool_id, plan in plans.items()},
        argv={tool_id: plan.argv for tool_id, plan in plans.items()},
        remove_ban=False,
        remove_path_block=False,
        config=dict(config or {}),
    )


def _apply(
    decision: UninstallDecision, home: Path, *, runner: Runner, catalog: Sequence[Tool]
) -> SweepResult:
    from installer.app import perform_uninstall

    return perform_uninstall(
        decision,
        bin_dir=home / ".local" / "bin",
        myshellrc_path=home / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=home / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=runner,
        catalog=catalog,
    )


def test_toggled_config_is_deleted_after_the_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = _brew_config_tool(tmp_path, monkeypatch)
    config = _plant_config(tmp_path, ".config/gh")
    seen: list[bool] = []

    def runner(_cmd: list[str]) -> None:
        seen.append(config.exists())  # the config is still there while the removal runs

    decision = _decision([gh], tmp_path, config={"gh": (config,)})
    result = _apply(decision, tmp_path, runner=runner, catalog=[gh])
    assert seen == [True]
    assert not config.exists()
    assert result.removed == ("gh",)
    assert result.config_deleted == ("gh",)


def test_config_survives_with_the_toggle_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = _brew_config_tool(tmp_path, monkeypatch)
    config = _plant_config(tmp_path, ".config/gh")
    result = _apply(_decision([gh], tmp_path), tmp_path, runner=lambda _cmd: None, catalog=[gh])
    assert (config / "hosts.yml").exists()
    assert result.removed == ("gh",)
    assert result.config_deleted == ()


def test_a_failed_removal_keeps_the_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gh = _brew_config_tool(tmp_path, monkeypatch)
    config = _plant_config(tmp_path, ".config/gh")

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="Error: No such formula")

    decision = _decision([gh], tmp_path, config={"gh": (config,)})
    result = _apply(decision, tmp_path, runner=runner, catalog=[gh])
    assert (config / "hosts.yml").exists()
    assert result.remove_failed == (("gh", "Error: No such formula"),)
    assert result.config_not_deleted == ("gh",)
    assert result.config_deleted == ()


def test_a_refused_removal_keeps_the_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from tests.test_uninstall import plant_raw_yq

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    raw, bin_dir = plant_raw_yq(tmp_path)
    yq = Tool(
        id=raw.id,
        name=raw.name,
        category="dev",
        cmd=raw.cmd,
        methods=raw.methods,
        config_paths=("~/.config/yq",),
    )
    config = _plant_config(tmp_path, ".config/yq")
    decision = _decision([yq], tmp_path, config={"yq": (config,)})
    # Rewritten after the preview: the fresh proof refuses the whole tool (review R2-02).
    (bin_dir / "yq").write_text("rewritten after the preview, a different size")
    result = _apply(decision, tmp_path, runner=_no_removal_runner, catalog=[yq])
    assert result.removed == ()
    assert result.config_not_deleted == ("yq",)
    assert (config / "hosts.yml").exists()
    assert receipts.read("yq") is not None


def test_a_shared_config_path_needs_every_owner_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import app as app_module

    deleted: list[Path] = []
    real_delete = app_module.delete_config_path

    def spy(path: Path) -> None:
        deleted.append(path)
        real_delete(path)

    monkeypatch.setattr(app_module, "delete_config_path", spy)
    both = tmp_path / "both"
    both.mkdir()
    a = _brew_config_tool(both, monkeypatch, "a", config_paths=SHARED)
    b = _brew_config_tool(both, monkeypatch, "b", config_paths=SHARED)
    shared = _plant_config(both, ".config/shared")
    decision = _decision([a, b], both, config={"a": (shared,), "b": (shared,)})
    result = _apply(decision, both, runner=lambda _cmd: None, catalog=[a, b])
    assert deleted == [shared]  # one delete for two owners
    assert not shared.exists()
    assert sorted(result.config_deleted) == ["a", "b"]

    one = tmp_path / "one"
    one.mkdir()
    a = _brew_config_tool(one, monkeypatch, "a", config_paths=SHARED)
    b = _brew_config_tool(one, monkeypatch, "b", config_paths=SHARED)
    shared = _plant_config(one, ".config/shared")
    deleted.clear()

    def fail_b(cmd: list[str]) -> None:
        if cmd[-1] == "b":
            raise CommandError(cmd, 1, detail="Error: b failed")

    decision = _decision([a, b], one, config={"a": (shared,), "b": (shared,)})
    result = _apply(decision, one, runner=fail_b, catalog=[a, b])
    assert deleted == []
    assert (shared / "hosts.yml").exists()
    assert result.config_not_deleted == ("b",)


def test_a_shared_config_path_needs_every_catalog_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # c declares the path too but is not always selected: an unselected or flag-off owner keeps it.
    def tools(home: Path) -> tuple[Tool, Tool, Tool]:
        home.mkdir()
        a = _brew_config_tool(home, monkeypatch, "a", config_paths=SHARED)
        b = _brew_config_tool(home, monkeypatch, "b", config_paths=())
        c = _brew_config_tool(home, monkeypatch, "c", config_paths=SHARED)
        return a, b, c

    home = tmp_path / "unselected"
    a, b, c = tools(home)
    shared = _plant_config(home, ".config/shared")
    decision = _decision([a, b], home, config={"a": (shared,)})
    _apply(decision, home, runner=lambda _cmd: None, catalog=[a, b, c])
    assert (shared / "hosts.yml").exists()

    home = tmp_path / "flag-off"
    a, b, c = tools(home)
    shared = _plant_config(home, ".config/shared")
    decision = _decision([a, c], home, config={"a": (shared,)})
    _apply(decision, home, runner=lambda _cmd: None, catalog=[a, b, c])
    assert (shared / "hosts.yml").exists()

    home = tmp_path / "both-flagged"
    a, b, c = tools(home)
    shared = _plant_config(home, ".config/shared")
    decision = _decision([a, c], home, config={"a": (shared,), "c": (shared,)})
    _apply(decision, home, runner=lambda _cmd: None, catalog=[a, b, c])
    assert not shared.exists()


def test_a_config_path_already_gone_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = _brew_config_tool(tmp_path, monkeypatch)
    gone = tmp_path / ".config" / "gh"  # never created
    decision = _decision([gh], tmp_path, config={"gh": (gone,)})
    result = _apply(decision, tmp_path, runner=lambda _cmd: None, catalog=[gh])
    assert result.warnings == ()
    assert result.config_deleted == ("gh",)
    assert result.removed == ("gh",)


def test_an_undeclared_config_path_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = _brew_config_tool(tmp_path, monkeypatch)
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "id_ed25519").write_text("key")
    decision = _decision([gh], tmp_path, config={"gh": (ssh,)})
    result = _apply(decision, tmp_path, runner=lambda _cmd: None, catalog=[gh])
    assert (ssh / "id_ed25519").exists()
    assert result.warnings == (f"config {ssh} is not declared by any tool; not deleted",)


def test_a_config_delete_failure_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import app as app_module
    from installer import receipts

    gh = _brew_config_tool(tmp_path, monkeypatch)
    config = _plant_config(tmp_path, ".config/gh")

    def deny(_path: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(app_module, "delete_config_path", deny)
    decision = _decision([gh], tmp_path, config={"gh": (config,)})
    result = _apply(decision, tmp_path, runner=lambda _cmd: None, catalog=[gh])
    assert result.removed == ("gh",)
    assert not receipts.receipt_exists("gh")
    assert result.warnings == ("could not delete config ~/.config/gh — denied",)


def test_a_refused_config_parent_is_a_warning_and_the_tool_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = _brew_config_tool(tmp_path, monkeypatch)
    harness_cfg = tmp_path / ".claude" / "cfg" / "gh"
    harness_cfg.mkdir(parents=True)
    (harness_cfg / "hosts.yml").write_text("token")
    (tmp_path / ".config").symlink_to(tmp_path / ".claude" / "cfg")  # ~/.config -> a harness dir
    decision = _decision([gh], tmp_path, config={"gh": (tmp_path / ".config" / "gh",)})
    result = _apply(decision, tmp_path, runner=lambda _cmd: None, catalog=[gh])
    assert result.removed == ("gh",)
    assert (harness_cfg / "hosts.yml").exists()
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("could not delete config ~/.config/gh — ")


def test_an_interrupt_before_step_4_leaves_the_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import app as app_module

    gh = _brew_config_tool(tmp_path, monkeypatch)
    config = _plant_config(tmp_path, ".config/gh")

    def interrupted(_path: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(app_module, "delete_config_path", interrupted)
    decision = _decision([gh], tmp_path, config={"gh": (config,)})
    with pytest.raises(KeyboardInterrupt):
        _apply(decision, tmp_path, runner=lambda _cmd: None, catalog=[gh])
    assert (config / "hosts.yml").exists()


def test_the_cli_never_deletes_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.app import run_uninstall

    gh = _brew_config_tool(tmp_path, monkeypatch)
    config = _plant_config(tmp_path, ".config/gh")
    console, buf = _console()
    shown: list[str] = []
    calls: list[list[str]] = []

    def confirm(_message: str) -> bool:
        shown.append(buf.getvalue())  # what the user sees before the confirm
        return True

    kwargs = _uninstall_kwargs(tmp_path, tmp_path / ".local" / "bin", confirm)
    kwargs["runner"] = calls.append
    _removed, failed = run_uninstall([gh], console, **kwargs)
    assert calls == [["brew", "uninstall", "gh"]]
    assert failed == ()
    assert (config / "hosts.yml").exists()
    assert "Config kept; only the Uninstall view deletes config (press c on a row):\n" in shown[0]
    assert "row):\n  ~/.config/gh\n" in shown[0]


def test_the_cli_prints_no_config_block_without_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall

    gh = _brew_config_tool(tmp_path, monkeypatch)  # ~/.config/gh is never created
    console, buf = _console()
    kwargs = _uninstall_kwargs(tmp_path, tmp_path / ".local" / "bin", lambda _m: True)
    kwargs["runner"] = lambda _cmd: None
    run_uninstall([gh], console, **kwargs)
    assert "Config kept" not in buf.getvalue()


def test_the_cli_prints_the_group_warning_before_the_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import run_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(
        kind="node",
        params={"npm_pkg": "@mermaid-js/mermaid-cli", "co_install": ["puppeteer"]},
    )
    mmdc = _manager_tool("mmdc", method)
    receipts.record(mmdc, method, package="@mermaid-js/mermaid-cli", smoke=None)
    console, buf = _console()
    shown: list[str] = []
    calls: list[list[str]] = []

    def confirm(_message: str) -> bool:
        shown.append(buf.getvalue())
        return False  # declined: nothing runs

    kwargs = _uninstall_kwargs(tmp_path, tmp_path / ".local" / "bin", confirm)
    kwargs["runner"] = calls.append
    run_uninstall([mmdc], console, **kwargs)
    line = (
        "Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli removes the whole group, "
        "puppeteer included."
    )
    assert line in shown[0]
    assert calls == []


def test_the_cli_group_warning_skips_a_member_already_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """22-UAT F-3: mmdc has no receipt and is not on disk (a group removal whose listing was
    unreadable kept puppeteer's receipt), so the warning names nothing that is gone."""
    from installer import app as app_module
    from installer import receipts
    from installer.app import run_uninstall

    mmdc, puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)
    receipts.delete("mmdc")

    def on_disk(tool: Tool, **_kw: object) -> bool:
        return tool.id != "mmdc"

    monkeypatch.setattr(app_module, "is_installed", on_disk)
    console, buf = _console()
    kwargs = _uninstall_kwargs(tmp_path, tmp_path / ".local" / "bin", lambda _m: False)
    run_uninstall([mmdc, puppeteer], console, **kwargs)
    assert "puppeteer: runs pnpm remove --global puppeteer" in buf.getvalue()
    assert "Warning: pnpm group" not in buf.getvalue()


_PNPM_NOT_FOUND = (
    "Error: ERR_PNPM_GLOBAL_PKG_NOT_FOUND\n\n"
    "  \u00d7 Cannot remove '{}': not found in global packages"
)


def _pnpm_group_runner(group: set[str], calls: list[list[str]]) -> Runner:
    """Behaves like pnpm 12.16.1 (22-13 D-1, container-measured): removing any member of a
    global install group removes the whole group; a name no longer installed is not found."""

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        package = cmd[-1]
        if package not in group:
            raise CommandError(cmd, 1, detail=_PNPM_NOT_FOUND.format(package))
        group.clear()

    return runner


def _mmdc_and_puppeteer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Tool, Tool]:
    from installer import app as app_module
    from installer import receipts

    monkeypatch.setenv("HOME", str(tmp_path))
    fake_pnpm = tmp_path / "pnpm"
    fake_pnpm.write_text("")
    monkeypatch.setattr(app_module, "real_pnpm", lambda: str(fake_pnpm))
    mmdc_method = Method(
        kind="node",
        params={"npm_pkg": "@mermaid-js/mermaid-cli", "co_install": ["puppeteer"]},
    )
    puppeteer_method = Method(kind="node", params={"npm_pkg": "puppeteer"})
    mmdc = _manager_tool("mmdc", mmdc_method)
    puppeteer = _manager_tool("puppeteer", puppeteer_method)
    receipts.record(mmdc, mmdc_method, package="@mermaid-js/mermaid-cli", smoke=None)
    receipts.record(puppeteer, puppeteer_method, package="puppeteer", smoke=None)
    return mmdc, puppeteer


def test_a_group_member_pnpm_already_removed_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """22-13 D-1 / 22-UAT F-2: the first member's removal took the whole group. The fresh pnpm
    listing no longer lists the second member, so nothing runs for it, its receipt is retired
    in the same step, and it is reported as removed with the group."""
    from installer import app as app_module
    from installer import receipts
    from installer.app import run_uninstall

    mmdc, puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)
    group = {"@mermaid-js/mermaid-cli", "puppeteer"}
    monkeypatch.setattr(app_module, "manager_listing", _listing(group))
    console, buf = _console()
    calls: list[list[str]] = []
    kwargs = _uninstall_kwargs(tmp_path, tmp_path / ".local" / "bin", lambda _m: True)
    kwargs["runner"] = _pnpm_group_runner(group, calls)
    _removed, failed = run_uninstall([mmdc, puppeteer], console, **kwargs)
    assert [cmd[-1] for cmd in calls] == ["@mermaid-js/mermaid-cli"]
    assert failed == ()
    assert "puppeteer: removed with the mmdc group" in buf.getvalue()
    assert "already removed" not in buf.getvalue()
    assert receipts.read("mmdc") is None
    assert receipts.read("puppeteer") is None


def test_an_unreadable_listing_keeps_the_group_members_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """22-UAT F-2, fail closed: without a readable pnpm listing nothing proves the other member
    gone, so its receipt stays and nothing claims it went with the group."""
    from installer import receipts
    from installer.app import run_uninstall

    mmdc, _puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)  # the listing is unknown
    console, buf = _console()
    calls: list[list[str]] = []
    kwargs = _uninstall_kwargs(tmp_path, tmp_path / ".local" / "bin", lambda _m: True)
    kwargs["runner"] = _pnpm_group_runner({"@mermaid-js/mermaid-cli", "puppeteer"}, calls)
    run_uninstall([mmdc], console, **kwargs)
    assert receipts.read("mmdc") is None
    assert receipts.read("puppeteer") is not None
    assert "removed with" not in buf.getvalue()


def test_a_tui_group_removal_retires_the_unselected_members_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """22-UAT F-2: the Uninstall view removes mmdc only; pnpm took puppeteer too, so the same
    run retires puppeteer's receipt and reports it removed with the group."""
    from installer import app as app_module
    from installer import receipts

    mmdc, puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)
    group = {"@mermaid-js/mermaid-cli", "puppeteer"}
    monkeypatch.setattr(app_module, "manager_listing", _listing(group))
    calls: list[list[str]] = []
    result = _apply(
        _decision([mmdc], tmp_path),
        tmp_path,
        runner=_pnpm_group_runner(group, calls),
        catalog=[mmdc, puppeteer],
    )
    assert [cmd[-1] for cmd in calls] == ["@mermaid-js/mermaid-cli"]
    assert result.removed == ("mmdc", "puppeteer")
    assert result.with_group == ("puppeteer: removed with the mmdc group",)
    assert result.remove_failed == ()
    assert receipts.read("puppeteer") is None


def test_a_group_member_pnpm_still_lists_keeps_its_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """22-UAT F-2: a member the fresh listing still shows was not taken; its receipt stays."""
    from installer import app as app_module
    from installer import receipts

    mmdc, puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "manager_listing", _listing({"puppeteer"}))
    result = _apply(
        _decision([mmdc], tmp_path),
        tmp_path,
        runner=lambda _cmd: None,
        catalog=[mmdc, puppeteer],
    )
    assert result.removed == ("mmdc",)
    assert result.with_group == ()
    assert receipts.read("puppeteer") is not None


def test_another_pnpm_error_still_fails_the_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only pnpm's not-found code proves the package gone; any other failure keeps the receipt."""
    from installer import receipts
    from installer.app import remove_tool

    _mmdc, puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)
    argv = ("pnpm", "remove", "--global", "puppeteer")

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="Error: ERR_PNPM_EACCES\n  permission denied")

    outcome = remove_tool(
        puppeteer, paths=(), argv=argv, bin_dir=tmp_path / ".local" / "bin", runner=runner
    )
    assert (outcome.removed, outcome.detail) == (False, "Error: ERR_PNPM_EACCES")
    assert receipts.read("puppeteer") is not None


def test_a_pnpm_not_found_is_no_proof_without_a_readable_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C-02 (CR-04): pnpm's not-found may come from another pnpm's global dir, so only a
    readable listing that lacks the package retires the receipt; the error alone keeps it."""
    from installer import receipts
    from installer.app import remove_tool

    _mmdc, puppeteer = _mmdc_and_puppeteer(tmp_path, monkeypatch)

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail=_PNPM_NOT_FOUND.format("puppeteer"))

    outcome = remove_tool(
        puppeteer,
        paths=(),
        argv=("pnpm", "remove", "--global", "puppeteer"),
        bin_dir=tmp_path / ".local" / "bin",
        runner=runner,
    )
    assert outcome.removed is False
    assert receipts.read("puppeteer") is not None


def _listing(names: set[str]) -> Callable[[str], frozenset[str]]:
    """A fresh manager listing that reads `names` at call time, whatever the kind."""

    def listing(_kind: str) -> frozenset[str]:
        return frozenset(names)

    return listing


def _jq_brew_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Tool:
    from installer import receipts

    monkeypatch.setenv("HOME", str(tmp_path))
    method = Method(kind="brew", params={"formula": "jq"})
    jq = _manager_tool("jq", method)
    receipts.record(jq, method, package="jq", smoke=None)
    return jq


def test_a_manager_package_the_user_already_removed_runs_nothing_and_retires_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review C-02: a readable fresh listing without the package means it is already gone."""
    from installer import app as app_module
    from installer import receipts
    from installer.app import remove_tool

    jq = _jq_brew_receipt(tmp_path, monkeypatch)
    asked: list[str] = []

    def listing(kind: str) -> frozenset[str]:
        asked.append(kind)
        return frozenset({"git"})

    monkeypatch.setattr(app_module, "manager_listing", listing)
    calls: list[list[str]] = []
    outcome = remove_tool(
        jq,
        paths=(),
        argv=("brew", "uninstall", "jq"),
        bin_dir=tmp_path / ".local" / "bin",
        runner=calls.append,
    )
    assert (outcome.removed, outcome.detail) == (True, "already removed")
    assert asked == ["brew"]
    assert calls == []
    assert receipts.read("jq") is None


def test_a_manager_package_still_listed_runs_its_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import app as app_module
    from installer import receipts
    from installer.app import remove_tool

    jq = _jq_brew_receipt(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "manager_listing", _listing({"jq"}))
    calls: list[list[str]] = []
    outcome = remove_tool(
        jq,
        paths=(),
        argv=("brew", "uninstall", "jq"),
        bin_dir=tmp_path / ".local" / "bin",
        runner=calls.append,
    )
    assert (outcome.removed, outcome.detail) == (True, "")
    assert calls == [["brew", "uninstall", "jq"]]
    assert receipts.read("jq") is None


def test_an_unreadable_listing_runs_the_uninstall_and_a_failure_keeps_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed: no listing proves nothing, so the previewed command runs as shown."""
    from installer import receipts
    from installer.app import remove_tool

    jq = _jq_brew_receipt(tmp_path, monkeypatch)
    keg = "Error: No such keg: /opt/homebrew/Cellar/jq"

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail=keg)

    outcome = remove_tool(
        jq,
        paths=(),
        argv=("brew", "uninstall", "jq"),
        bin_dir=tmp_path / ".local" / "bin",
        runner=runner,
    )
    assert (outcome.removed, outcome.detail) == (False, keg)
    assert receipts.read("jq") is not None


def test_a_failed_unregister_stops_the_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O4 / T-23-20: a failed undo deletes nothing, keeps the receipt, and runs no other command."""
    from installer import receipts
    from installer.app import remove_tool
    from installer.uninstall import removal_plan
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("claude", "codex"))
    plan = removal_plan(tool, bin_dir, verify=True)
    calls: list[list[str]] = []

    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
        raise CommandError(cmd, 1, detail="boom")

    outcome = remove_tool(
        tool,
        paths=plan.removable,
        argv=plan.argv,
        bin_dir=bin_dir,
        runner=runner,
        unregister=plan.unregister,
    )
    assert (outcome.removed, outcome.detail) == (False, "unregister: boom")
    assert calls == [list(undo) for undo in plan.unregister]
    assert all(path.exists() or path.is_symlink() for path in plan.removable)
    assert receipts.receipt_exists("codegraph")


def test_an_unregister_that_changed_since_the_preview_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-23-21: the undo that runs is the one the user saw; a changed set refuses the whole tool."""
    from installer import receipts
    from installer.app import remove_tool
    from installer.uninstall import removal_plan
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("claude",))
    plan = removal_plan(tool, bin_dir, verify=True)
    calls: list[list[str]] = []
    outcome = remove_tool(
        tool,
        paths=plan.removable,
        argv=plan.argv,
        bin_dir=bin_dir,
        runner=calls.append,
        unregister=(),
    )
    assert (outcome.removed, outcome.detail) == (False, "changed since the preview; not removed")
    assert calls == []
    assert all(path.exists() or path.is_symlink() for path in plan.removable)
    assert receipts.receipt_exists("codegraph")


_UNREGISTER_LINE = (
    "codegraph: runs codegraph uninstall --target claude,codex --location global --yes --keep-cli"
)


def test_the_cli_prints_the_unregister_line_before_the_remove_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A24: the undo line is printed before the confirm; a declined run runs nothing."""
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    console, buf = _console()
    printed_at_confirm: list[str] = []

    def confirm(_message: str) -> bool:
        printed_at_confirm.append(buf.getvalue())
        return False

    removed, failed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=confirm,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
    )
    assert _UNREGISTER_LINE in printed_at_confirm[0]
    assert (removed, failed) == ([], ())
    assert (bin_dir / "codegraph").is_symlink()


def test_the_cli_reports_the_unregistered_hosts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    (tmp_path / ".myshellrc").write_text("")
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    calls: list[list[str]] = []
    console, buf = _console()
    _removed, failed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=lambda _message: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=calls.append,
    )
    assert failed == ()
    undo = [str(bin_dir / "codegraph"), "uninstall", "--target", "claude,codex"]
    assert calls == [[*undo, "--location", "global", "--yes", "--keep-cli"]]
    assert "Unregistered from agent hosts: claude, codex." in buf.getvalue()


def test_the_cli_reports_a_failed_unregister(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    (tmp_path / ".myshellrc").write_text("")
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    console, buf = _console()

    def runner(cmd: list[str]) -> None:
        raise CommandError(cmd, 1, detail="boom")

    _removed, failed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=lambda _message: True,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=runner,
    )
    assert failed == ("codegraph",)
    assert "codegraph: remove failed — unregister: boom" in buf.getvalue()
    assert (bin_dir / "codegraph").is_symlink()
    assert receipts.receipt_exists("codegraph")


def test_perform_uninstall_passes_the_previewed_unregister(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer import receipts
    from installer.uninstall import removal_plan
    from tests.test_uninstall import plant_codegraph

    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    plan = removal_plan(tool, bin_dir)
    decision = UninstallDecision(
        tools=(tool,),
        paths={tool.id: plan.removable},
        argv={tool.id: plan.argv},
        remove_ban=False,
        remove_path_block=False,
        unregister={tool.id: plan.unregister},
    )
    calls: list[list[str]] = []
    result = _apply(decision, tmp_path, runner=calls.append, catalog=[tool])
    assert (result.removed, result.unregistered) == (("codegraph",), ("claude", "codex"))
    assert calls == [list(undo) for undo in plan.unregister]

    # The same tool without the previewed undo is refused: nothing runs and nothing goes.
    tool = plant_codegraph(tmp_path, ("codex", "claude"))
    plan = removal_plan(tool, bin_dir)
    decision = UninstallDecision(
        tools=(tool,),
        paths={tool.id: plan.removable},
        argv={tool.id: plan.argv},
        remove_ban=False,
        remove_path_block=False,
    )
    calls.clear()
    result = _apply(decision, tmp_path, runner=calls.append, catalog=[tool])
    assert result.remove_failed == (("codegraph", "changed since the preview; not removed"),)
    assert calls == []
    assert receipts.receipt_exists("codegraph")


def test_the_cli_previews_and_reports_the_revert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.agent_settings import apply_setting
    from installer.app import run_uninstall
    from tests.test_uninstall import plant_receipted_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    (tmp_path / ".myshellrc").write_text("")
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}\n")
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os="linux")
    tool = plant_receipted_tool(tmp_path, "claude")
    console, buf = _console()
    shown_before_confirm: list[str] = []

    def confirm(_message: str) -> bool:
        shown_before_confirm.append(buf.getvalue())
        return True

    _removed, failed = run_uninstall(
        [tool],
        console,
        default_bin_dir=bin_dir,
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=confirm,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        platform_os="linux",
    )
    assert failed == ()
    assert (
        "claude: removes permissions.defaultMode, skipDangerousModePermissionPrompt "
        "from ~/.claude/settings.json" in shown_before_confirm[0]
    )
    assert "Settings reverted for claude." in buf.getvalue()


def _removal_decision(tool: Tool) -> UninstallDecision:
    from installer.uninstall import removal_plan

    plan = removal_plan(tool, Path.home() / ".local" / "bin")
    return UninstallDecision(
        tools=(tool,),
        paths={tool.id: plan.removable},
        argv={tool.id: plan.argv},
        remove_ban=False,
        remove_path_block=False,
    )


def test_removing_starship_turns_off_only_its_shell_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A26: a shell-init tool's removal turns off its own bundle, never the docker block."""
    from installer.app import perform_uninstall
    from installer.tweaks import BUNDLES, shell_init_bundle, tweak_present, write_tweak
    from tests.test_uninstall import plant_receipted_tool

    monkeypatch.setenv("HOME", str(tmp_path))
    myshellrc = tmp_path / ".myshellrc"
    docker = next(bundle for bundle in BUNDLES if bundle.id == "docker")
    starship = shell_init_bundle("starship")
    assert starship is not None
    write_tweak(docker, myshellrc)
    write_tweak(starship, myshellrc)
    tool = plant_receipted_tool(tmp_path, "starship")
    result = perform_uninstall(
        _removal_decision(tool),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[],
        bundles=BUNDLES,
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=(tool,),
    )
    assert result.removed == ("starship",)
    assert result.shell_init_off == ("starship",)
    assert tweak_present(starship, myshellrc) is False
    assert tweak_present(docker, myshellrc) is True


def test_the_cli_names_the_shell_init_it_turns_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.app import run_uninstall
    from installer.tweaks import shell_init_bundle, write_tweak
    from tests.test_uninstall import plant_receipted_tool

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    myshellrc = tmp_path / ".myshellrc"
    starship = shell_init_bundle("starship")
    assert starship is not None
    write_tweak(starship, myshellrc)
    tool = plant_receipted_tool(tmp_path, "starship")
    console, buf = _console()
    shown_before_confirm: list[str] = []

    def confirm(_message: str) -> bool:
        shown_before_confirm.append(buf.getvalue())
        return True

    run_uninstall(
        [tool],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[],
        confirm=confirm,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        platform_os="linux",
    )
    assert "starship: turns off its shell init in ~/.myshellrc" in shown_before_confirm[0]
    assert "Shell init turned off for starship." in buf.getvalue()


def test_the_settings_pseudo_row_reverts_every_written_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O5: the environment row reverts every key the ledgers record, for any agent."""
    from installer.agent_settings import apply_setting, ledger_summary
    from installer.app import perform_uninstall

    monkeypatch.setenv("HOME", str(tmp_path))
    claude = tmp_path / ".claude" / "settings.json"
    claude.parent.mkdir(parents=True)
    claude.write_text("{}\n")
    before = claude.read_bytes()
    apply_setting("claude", "auto-approve", home=tmp_path, platform_os="linux")
    apply_setting("vscode", "vscode-ai-off", home=tmp_path, platform_os="linux")
    assert len(ledger_summary("vscode", home=tmp_path, platform_os="linux")) == 1
    decision = UninstallDecision(
        tools=(),
        paths={},
        remove_ban=False,
        remove_path_block=False,
        revert_settings=True,
    )
    result = perform_uninstall(
        decision,
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        catalog=(),
        platform_os="linux",
    )
    assert result.settings_reverted == ("claude", "vscode")
    assert claude.read_bytes() == before
    assert ledger_summary("claude", home=tmp_path, platform_os="linux") == ()
    assert ledger_summary("vscode", home=tmp_path, platform_os="linux") == ()


def test_the_cli_uninstall_reverts_every_written_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O5: the CLI lists every ledgered file before the confirm and reverts it, even for an
    agent that is not itself being removed."""
    from installer.agent_settings import apply_setting
    from installer.app import run_uninstall

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".myshellrc").write_text("")
    apply_setting("codex", "auto-approve", home=tmp_path, platform_os="linux")
    console, buf = _console()
    shown_before_confirm: list[str] = []

    def confirm(_message: str) -> bool:
        shown_before_confirm.append(buf.getvalue())
        return True

    run_uninstall(
        [],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        confirm=confirm,
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(),
        runner=_no_removal_runner,
        platform_os="linux",
    )
    assert "Agent and editor settings this installer wrote (reverted):" in shown_before_confirm[0]
    assert "  ~/.codex/config.toml: approval_policy, sandbox_mode" in shown_before_confirm[0]
    assert "Settings reverted for codex." in buf.getvalue()
    # The installer created this file, so it goes once its only key is reverted.
    assert not (tmp_path / ".codex" / "config.toml").exists()


def test_no_config_agent_declares_config_paths() -> None:
    """R1-58, R1-59: the guard the per-tool revert's shortcut relies on. When a settings agent
    starts declaring config_paths, the removal must revert before it deletes."""
    from installer import receipts
    from installer.model import load_tools

    registry = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
    declared = [
        tool.id
        for tool in load_tools(registry)
        if tool.id in receipts.CONFIG_AGENTS and tool.config_paths
    ]
    assert declared == []


def test_removing_zsh_sweeps_the_desktop_shell_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1-48: zsh's removal takes the owned desktop SHELL file with it, so no login is left
    with SHELL pointing at a removed zsh."""
    from installer.app import perform_uninstall
    from installer.env_redirect import DESKTOP_SHELL_CONF
    from installer.policy import desktop_shell_policy
    from tests.test_uninstall import plant_receipted_tool

    monkeypatch.setenv("HOME", str(tmp_path))
    conf_dir = tmp_path / ".config" / "environment.d"
    desktop_shell_policy(zsh_path="/z/bin/zsh", conf_dir=conf_dir, home=tmp_path).apply()
    conf = conf_dir / DESKTOP_SHELL_CONF
    assert conf.exists()
    tool = plant_receipted_tool(tmp_path, "zsh")
    result = perform_uninstall(
        _removal_decision(tool),
        bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=tmp_path / ".myshellrc",
        rc_paths=[],
        bundles=(),
        zshrc_path=tmp_path / ".zshrc",
        daemon_policy=None,
        extra_policies=(desktop_shell_policy(zsh_path=None, conf_dir=conf_dir, home=tmp_path),),
        runner=_no_removal_runner,
        catalog=(tool,),
        platform_os="linux",
    )
    assert result.removed == ("zsh",)
    assert "desktop-shell" in result.swept
    assert not conf.exists()
