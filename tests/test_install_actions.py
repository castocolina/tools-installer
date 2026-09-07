from dataclasses import replace
from pathlib import Path

import pytest

import installer.run as command_run
from installer.model import Method, Tool
from installer.platform import Platform
from installer.install_actions import ActionContext, ActionResult, apply_actions, set_login_shell
from installer.run import Runner


def _tool(*, post_install: tuple[str, ...]) -> Tool:
    return Tool(
        id="tool",
        name="Tool",
        category="test",
        cmd="tool",
        methods=(
            Method(
                kind="github_release",
                params={"member": "tool", "bin_dir": "/opt/tool/bin"},
            ),
        ),
        post_install=post_install,
    )


def _context(
    tmp_path: Path,
    *,
    runner: Runner | None = None,
    current_shell: str = "/bin/bash",
    zsh_path: str | None = "/bin/zsh",
    approved_actions: frozenset[tuple[str, str]] = frozenset(),
) -> ActionContext:
    def noop(_cmd: list[str]) -> None:
        return None

    run = runner or noop
    shells_file = tmp_path / "shells"
    shells_file.write_text("/bin/bash\n/bin/zsh\n")
    return ActionContext(
        home=tmp_path,
        myshellrc=tmp_path / ".myshellrc",
        rc_paths=(tmp_path / ".zshrc", tmp_path / ".bashrc"),
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=True),
        runner=run,
        interactive_runner=run,
        which=lambda command: zsh_path if command == "zsh" else None,
        shells_file=shells_file,
        current_shell=current_shell,
        agent_reference_paths=(tmp_path / "AGENTS.md",),
        exists=lambda _path: True,
        approved_actions=approved_actions,
    )


def test_pnpm_setup_uses_managed_path_block_without_duplicate_lines(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    context = _context(
        tmp_path,
        runner=commands.append,
        approved_actions=frozenset({("tool", "pnpm_setup")}),
    )

    first = apply_actions(_tool(post_install=("pnpm_setup",)), context)
    second = apply_actions(_tool(post_install=("pnpm_setup",)), context)

    assert first[0].status == "applied"
    assert second[0].status == "already-applied"
    assert context.myshellrc.read_text().count("PNPM_HOME") == 1
    assert commands == []


@pytest.mark.parametrize(
    ("platform_os", "expected_home"),
    [
        ("fedora", ".local/share/pnpm"),
        ("macos", "Library/pnpm"),
    ],
)
def test_pnpm_setup_uses_the_platform_home_without_running_upstream_setup(
    tmp_path: Path,
    platform_os: str,
    expected_home: str,
) -> None:
    commands: list[list[str]] = []
    context = replace(
        _context(
            tmp_path,
            runner=commands.append,
            approved_actions=frozenset({("tool", "pnpm_setup")}),
        ),
        platform=Platform(
            os=platform_os,
            arch="arm64",
            immutable=False,
            has_brew=True,
        ),
    )

    result = apply_actions(_tool(post_install=("pnpm_setup",)), context)

    assert result == (ActionResult("pnpm_setup", "applied", "pnpm home added to managed PATH"),)
    managed = context.myshellrc.read_text()
    assert f'export PNPM_HOME="{tmp_path / expected_home}"' in managed
    assert managed.count("PNPM_HOME") == 1
    assert commands == []


def test_unknown_action_is_rejected_before_execution(tmp_path: Path) -> None:
    context = _context(
        tmp_path,
        approved_actions=frozenset({("tool", "pnpm_setup")}),
    )

    with pytest.raises(ValueError, match="unknown post-install action"):
        apply_actions(_tool(post_install=("pnpm_setup", "shell text")), context)

    assert not context.myshellrc.exists()


def test_configure_path_and_source_shell_init_are_idempotent(tmp_path: Path) -> None:
    context = _context(
        tmp_path,
        approved_actions=frozenset(
            {
                ("tool", "configure_path"),
                ("tool", "source_shell_init"),
            }
        ),
    )
    tool = _tool(post_install=("configure_path", "source_shell_init"))

    first = apply_actions(tool, context)
    second = apply_actions(tool, context)

    assert [result.status for result in first] == ["applied", "applied"]
    assert [result.status for result in second] == ["already-applied", "already-applied"]
    assert context.myshellrc.read_text().count("/opt/tool/bin") == 1
    for rc_path in context.rc_paths:
        assert rc_path.read_text().count("tools-installer source") == 2


def test_enable_corepack_runs_only_the_reviewed_argv(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    result = apply_actions(
        _tool(post_install=("enable_corepack",)),
        _context(
            tmp_path,
            runner=commands.append,
            approved_actions=frozenset({("tool", "enable_corepack")}),
        ),
    )

    assert result == (ActionResult("enable_corepack", "applied", "corepack enabled"),)
    assert commands == [["corepack", "enable"]]


def test_set_login_shell_requires_manual_step_when_zsh_is_not_approved_by_system(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    context = _context(
        tmp_path,
        runner=commands.append,
        approved_actions=frozenset({("tool", "set_login_shell")}),
    )
    context.shells_file.write_text("/bin/bash\n")

    result = apply_actions(_tool(post_install=("set_login_shell",)), context)

    assert result[0].status == "manual-required"
    assert "administrator" in result[0].detail
    assert "/bin/zsh" in result[0].detail
    assert context.shells_file.read_text() == "/bin/bash\n"
    assert commands == []


def test_set_login_shell_runs_injected_chsh_only_for_the_approved_action(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    result = apply_actions(
        _tool(post_install=("set_login_shell",)),
        _context(
            tmp_path,
            runner=commands.append,
            approved_actions=frozenset({("tool", "set_login_shell")}),
        ),
    )

    assert result[0].status == "applied"
    assert commands == [["chsh", "-s", "/bin/zsh"]]


def test_set_login_shell_does_not_run_without_specific_action_approval(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    result = apply_actions(
        _tool(post_install=("set_login_shell",)),
        _context(tmp_path, runner=commands.append),
    )

    assert result[0].status == "manual-required"
    assert "not approved" in result[0].detail
    assert commands == []


def test_set_login_shell_does_not_accept_another_tools_action_approval(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    result = apply_actions(
        _tool(post_install=("set_login_shell",)),
        _context(
            tmp_path,
            runner=commands.append,
            approved_actions=frozenset({("other", "set_login_shell")}),
        ),
    )

    assert result[0].status == "manual-required"
    assert commands == []


def test_exported_set_login_shell_handler_guards_unapproved_api_calls(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    tool = _tool(post_install=("set_login_shell",))

    result = set_login_shell(tool, _context(tmp_path, runner=commands.append))

    assert result.status == "manual-required"
    assert commands == []


def test_exported_set_login_shell_handler_rejects_approval_for_undeclared_action(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    tool = _tool(post_install=())
    context = _context(
        tmp_path,
        runner=commands.append,
        approved_actions=frozenset({("tool", "set_login_shell")}),
    )

    result = set_login_shell(tool, context)

    assert result.status == "manual-required"
    assert commands == []


def test_set_login_shell_is_already_applied_without_running_chsh(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    result = apply_actions(
        _tool(post_install=("set_login_shell",)),
        _context(
            tmp_path,
            runner=commands.append,
            current_shell="/bin/zsh",
            approved_actions=frozenset({("tool", "set_login_shell")}),
        ),
    )

    assert result[0].status == "already-applied"
    assert commands == []


def test_set_login_shell_returns_manual_command_without_an_interactive_terminal(
    tmp_path: Path,
) -> None:
    def no_terminal(_cmd: list[str]) -> None:
        raise command_run.InteractiveTerminalUnavailable

    context = _context(
        tmp_path,
        approved_actions=frozenset({("tool", "set_login_shell")}),
    )
    context = replace(context, interactive_runner=no_terminal)

    result = apply_actions(_tool(post_install=("set_login_shell",)), context)

    assert result == (
        ActionResult(
            "set_login_shell",
            "manual-required",
            "no interactive terminal is available; run `chsh -s /bin/zsh` in a terminal",
        ),
    )


def test_write_agent_reference_preserves_user_text_and_is_idempotent(tmp_path: Path) -> None:
    context = _context(
        tmp_path,
        approved_actions=frozenset({("tool", "write_agent_reference")}),
    )
    reference = context.agent_reference_paths[0]
    reference.write_text("# User instructions\n")

    first = apply_actions(_tool(post_install=("write_agent_reference",)), context)
    second = apply_actions(_tool(post_install=("write_agent_reference",)), context)

    assert first[0].status == "applied"
    assert second[0].status == "already-applied"
    assert reference.read_text().count("AGENTS-TOOLING.md") == 1
    assert "# User instructions" in reference.read_text()


def test_configure_path_resolves_registry_tilde_inside_context_home(tmp_path: Path) -> None:
    tool = _tool(post_install=("configure_path",))
    tool = replace(
        tool,
        methods=(
            Method(
                kind="github_release",
                params={"member": "tool", "bin_dir": "~/.sdkman/bin"},
            ),
        ),
    )
    seen: list[Path] = []
    context = _context(
        tmp_path,
        approved_actions=frozenset({("tool", "configure_path")}),
    )

    def exists(path: Path) -> bool:
        seen.append(path)
        return True

    context = replace(context, exists=exists)

    apply_actions(tool, context)

    assert tmp_path / ".sdkman" / "bin" in seen
    assert Path.home() / ".sdkman" / "bin" not in seen
    assert str(tmp_path / ".sdkman" / "bin") in context.myshellrc.read_text()
