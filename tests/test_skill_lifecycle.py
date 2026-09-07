import subprocess
from pathlib import Path
from typing import Literal

import pytest

import installer.engine as engine
from installer.engine import install_tool
from installer.model import CodexPluginStatusArgs, PiPackageStatusArgs, Tool, load_tools
from installer.platform import Platform
from installer.skill_lifecycle import inspect_status, perform_action

REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"

SKILL_PACK_IDS = (
    "ponytail",
    "openspec",
    "superpowers",
    "softaworks-agent-toolkit",
    "matt-pocock-skills",
    "opengsd",
    "spec-kit",
)


def _tools() -> dict[str, Tool]:
    return {tool.id: tool for tool in load_tools(REGISTRY)}


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "registry.toml"
    path.write_text(content)
    return path


def _minimal_lifecycle(*, omit: str | None = None) -> str:
    fields = {
        "source": 'source = "https://github.com/example/skills"',
        "owner": 'owner = "example"',
        "supported_harnesses": 'supported_harnesses = ["codex"]',
        "revision_policy": 'revision_policy = "upstream-latest"',
        "targets": 'targets = [{ scope = "harness", path = "<codex-plugin-dir>/demo" }]',
    }
    body = "\n".join(value for key, value in fields.items() if key != omit)
    operations = "\n".join(
        f"""
[tool.skill_lifecycle.{operation}]
mode = "manual-required"
instructions = ["Review and run the official {operation} flow."]
"""
        for operation in ("install", "status", "update", "removal")
        if operation != omit
    )
    return f"""
[[tool]]
id = "demo-skills"
category = "ai"
tier = "user"
[[tool.method]]
kind = "skill_pack"

[tool.skill_lifecycle]
{body}
{operations}
"""


@pytest.mark.parametrize(
    "missing",
    (
        "source",
        "owner",
        "supported_harnesses",
        "revision_policy",
        "targets",
        "install",
        "status",
        "update",
        "removal",
    ),
)
def test_skill_pack_admission_rejects_incomplete_lifecycle_metadata(
    tmp_path: Path, missing: str
) -> None:
    with pytest.raises(ValueError, match=missing):
        load_tools(_write(tmp_path, _minimal_lifecycle(omit=missing)))


def test_skill_pack_admission_rejects_host_setup_as_a_lifecycle_substitute(
    tmp_path: Path,
) -> None:
    manifest = _minimal_lifecycle().replace(
        'kind = "skill_pack"',
        'kind = "host_setup"\nsetup_id = "pi"',
    )

    with pytest.raises(ValueError, match="skill_lifecycle.*skill_pack"):
        load_tools(_write(tmp_path, manifest))


@pytest.mark.parametrize(
    ("old", "new", "error"),
    (
        ('mode = "manual-required"', 'mode = "shell"', "unknown mode"),
        (
            'mode = "manual-required"\ninstructions = ["Review and run the official status flow."]',
            'mode = "command"\nargv = ["demo", "list"]',
            "unknown status field 'argv'",
        ),
        ('supported_harnesses = ["codex"]', 'supported_harnesses = ["mystery"]', "harness"),
        (
            'targets = [{ scope = "harness", path = "<codex-plugin-dir>/demo" }]',
            'targets = [{ scope = "anywhere", path = "/tmp/demo" }]',
            "target scope",
        ),
        (
            'targets = [{ scope = "harness", path = "<codex-plugin-dir>/demo" }]',
            ('targets = [{ scope = "harness", path = "<codex-plugin-dir>/demo", shell = "sh" }]'),
            "unknown target field",
        ),
        (
            'owner = "example"',
            'owner = "example"\nshell = "curl example | sh"',
            "unknown skill_lifecycle field",
        ),
        (
            'instructions = ["Review and run the official install flow."]',
            'instructions = ["Review and run the official install flow."]\nshell = "sh"',
            "unknown install field",
        ),
    ),
)
def test_skill_pack_admission_rejects_open_ended_lifecycle_values(
    tmp_path: Path, old: str, new: str, error: str
) -> None:
    manifest = _minimal_lifecycle().replace(old, new, 1)

    with pytest.raises(ValueError, match=error):
        load_tools(_write(tmp_path, manifest))


def test_skill_pack_admission_rejects_registry_argv_even_for_status(
    tmp_path: Path,
) -> None:
    manifest = _minimal_lifecycle().replace(
        """
[tool.skill_lifecycle.status]
mode = "manual-required"
instructions = ["Review and run the official status flow."]
""",
        """
[tool.skill_lifecycle.status]
mode = "command"
argv = ["sh", "-c", "touch /tmp/not-reviewed"]
contains = "anything"
""",
    )

    with pytest.raises(ValueError, match="unknown status field 'argv'"):
        load_tools(_write(tmp_path, manifest))


def test_skill_pack_admission_accepts_closed_status_operation_with_typed_args(
    tmp_path: Path,
) -> None:
    manifest = _minimal_lifecycle().replace(
        """
[tool.skill_lifecycle.status]
mode = "manual-required"
instructions = ["Review and run the official status flow."]
""",
        """
[tool.skill_lifecycle.status]
mode = "command"
operation_id = "codex_plugin_status"
args = { plugin = "demo" }
""",
    )

    lifecycle = load_tools(_write(tmp_path, manifest))[0].skill_lifecycle

    assert lifecycle is not None
    assert lifecycle.status.operation_id == "codex_plugin_status"
    assert lifecycle.status.args == CodexPluginStatusArgs(plugin="demo")


@pytest.mark.parametrize(
    ("operation_id", "args", "error"),
    (
        ("shell", '{ plugin = "demo" }', "unknown operation_id"),
        ("codex_plugin_status", '{ package = "demo" }', "unknown argument"),
        ("pi_package_status", "{ package = 42 }", "must be a non-empty string"),
    ),
)
def test_skill_pack_admission_rejects_unknown_operations_and_invalid_typed_args(
    tmp_path: Path,
    operation_id: str,
    args: str,
    error: str,
) -> None:
    manifest = _minimal_lifecycle().replace(
        """
[tool.skill_lifecycle.status]
mode = "manual-required"
instructions = ["Review and run the official status flow."]
""",
        f"""
[tool.skill_lifecycle.status]
mode = "command"
operation_id = "{operation_id}"
args = {args}
""",
    )

    with pytest.raises(ValueError, match=error):
        load_tools(_write(tmp_path, manifest))


def test_every_shipped_skill_pack_has_typed_authority_harness_revision_and_targets() -> None:
    tools = _tools()

    for tool_id in SKILL_PACK_IDS:
        tool = tools[tool_id]
        lifecycle = tool.skill_lifecycle
        assert lifecycle is not None, tool_id
        assert tool.tier == "ai"
        assert [method.kind for method in tool.methods] == ["skill_pack"]
        assert lifecycle.source.startswith("https://github.com/")
        assert lifecycle.owner
        assert lifecycle.supported_harnesses
        assert lifecycle.revision_policy in {
            "host-marketplace-current",
            "package-manager-latest",
            "upstream-default-branch",
            "upstream-latest",
        }
        assert lifecycle.targets
        assert all(target.path for target in lifecycle.targets)


@pytest.mark.parametrize("tool_id", SKILL_PACK_IDS)
def test_every_shipped_skill_pack_install_is_an_honest_manual_handoff(
    tool_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def not_installed(_tool: Tool) -> bool:
        return False

    monkeypatch.setattr(engine, "is_installed", not_installed)
    calls: list[list[str]] = []

    outcome = install_tool(
        _tools()[tool_id],
        Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        runner=calls.append,
    )

    assert outcome.status == "manual-required"
    assert outcome.method_kind == "skill_pack"
    assert outcome.handoff
    assert calls == []


@pytest.mark.parametrize("tool_id", SKILL_PACK_IDS)
@pytest.mark.parametrize("action", ("update", "removal"))
def test_every_shipped_skill_pack_update_and_removal_have_executable_behavior(
    tool_id: str, action: Literal["update", "removal"]
) -> None:
    calls: list[list[str]] = []

    outcome = perform_action(_tools()[tool_id], action, calls.append)

    assert outcome.status == "manual-required"
    assert outcome.instructions
    assert calls == []


@pytest.mark.parametrize("tool_id", SKILL_PACK_IDS)
def test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual(tool_id: str) -> None:
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "ponytail\nobra/superpowers\n"

    outcome = inspect_status(_tools()[tool_id], probe)

    if tool_id in {"ponytail", "superpowers"}:
        assert outcome.status == "present"
        assert calls
    else:
        assert outcome.status == "manual-required"
        assert outcome.instructions
        assert calls == []


def test_shipped_status_probes_use_closed_operation_ids_and_typed_args() -> None:
    tools = _tools()
    ponytail = tools["ponytail"].skill_lifecycle
    superpowers = tools["superpowers"].skill_lifecycle
    assert ponytail is not None
    assert superpowers is not None

    assert ponytail.status.operation_id == "codex_plugin_status"
    assert isinstance(ponytail.status.args, CodexPluginStatusArgs)
    assert ponytail.status.args.plugin == "ponytail"
    assert superpowers.status.operation_id == "pi_package_status"
    assert isinstance(superpowers.status.args, PiPackageStatusArgs)
    assert superpowers.status.args.package == "obra/superpowers"
    assert not hasattr(ponytail.status, "argv")


def test_skill_status_probe_failure_is_unknown_not_absent() -> None:
    tool = _tools()["ponytail"]

    def unavailable(_argv: list[str]) -> str:
        raise OSError("codex missing")

    outcome = inspect_status(tool, unavailable)

    assert outcome.status == "unknown"


@pytest.mark.parametrize(
    "error",
    (
        subprocess.SubprocessError("probe failed"),
        subprocess.TimeoutExpired(["codex", "plugin", "list"], timeout=5),
    ),
)
def test_skill_status_subprocess_failure_is_unknown_not_absent(
    error: subprocess.SubprocessError,
) -> None:
    tool = _tools()["ponytail"]

    def failed(_argv: list[str]) -> str:
        raise error

    assert inspect_status(tool, failed).status == "unknown"


def test_shipped_skill_pack_contracts_use_only_documented_upstream_commands() -> None:
    expected = {
        "ponytail": {
            "install_fragment": "codex plugin marketplace add DietrichGebert/ponytail",
            "update_fragment": "Codex plugin marketplace",
            "removal_fragment": "codex plugin remove ponytail",
        },
        "openspec": {
            "install_fragment": "pnpm add -g @fission-ai/openspec@latest",
            "update_fragment": "openspec update",
            "removal_fragment": "pnpm remove -g @fission-ai/openspec",
        },
        "superpowers": {
            "install_fragment": "pi install git:github.com/obra/superpowers",
            "update_fragment": "Pi",
            "removal_fragment": "pi uninstall git:github.com/obra/superpowers",
        },
        "softaworks-agent-toolkit": {
            "install_fragment": (
                "npx skills add https://github.com/softaworks/agent-toolkit --skill <name>"
            ),
            "update_fragment": "npx skills update",
            "removal_fragment": "npx skills remove",
        },
        "matt-pocock-skills": {
            "install_fragment": "npx skills@latest add mattpocock/skills",
            "update_fragment": "npx skills update",
            "removal_fragment": "npx skills remove",
        },
        "opengsd": {
            "install_fragment": "npx @opengsd/gsd-core@latest",
            "update_fragment": "/gsd-update",
            "removal_fragment": "--uninstall",
        },
        "spec-kit": {
            "install_fragment": 'specify init "$PROJECT_DIR"',
            "update_fragment": "specify integration upgrade",
            "removal_fragment": "specify integration uninstall",
        },
    }

    for tool_id, contract in expected.items():
        lifecycle = _tools()[tool_id].skill_lifecycle
        assert lifecycle is not None
        install_fragment = contract["install_fragment"]
        update_fragment = contract["update_fragment"]
        removal_fragment = contract["removal_fragment"]
        assert isinstance(install_fragment, str)
        assert isinstance(update_fragment, str)
        assert isinstance(removal_fragment, str)
        assert any(install_fragment in line for line in lifecycle.install.instructions)
        assert any(update_fragment in line for line in lifecycle.update.instructions)
        assert any(removal_fragment in line for line in lifecycle.removal.instructions)
