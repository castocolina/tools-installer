import contextlib
import json
import os
import shutil
import subprocess
import threading
from collections import deque
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import IO, Any, Literal

import pytest

import installer.atomic as atomic
import installer.engine as engine
import installer.skill_lifecycle as skill_lifecycle
from installer.engine import install_tool
from installer.model import (
    SKILL_HARNESSES,
    ConfigStep,
    ConfigStepKind,
    Method,
    SkillLifecycle,
    SkillOperation,
    SkillStatusProbe,
    SkillTarget,
    Tool,
    load_tools,
)
from installer.platform import Platform
from installer.skill_lifecycle import (
    INSTALL_STATE_HARNESS_DIRS,
    PROJECT_GLOBAL_MACHINERY,
    PROJECT_HOOK_CONFIGS,
    PROJECT_PACK_PACKAGES,
    SKILL_HARNESS_LABELS,
    HarnessStatus,
    ProjectPackReport,
    SkillPackReport,
    _install_state_status,  # pyright: ignore[reportPrivateUsage]
    inspect_project_pack,
    inspect_skill_reports,
    inspect_status,
    partial_harnesses,
    partial_steps,
    perform_action,
    present_harnesses,
)

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
verified = 2026-10-13
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


def test_by_harness_key_outside_supported_harnesses_names_the_tool(tmp_path: Path) -> None:
    manifest = _minimal_lifecycle().replace(
        """
[tool.skill_lifecycle.install]
mode = "manual-required"
instructions = ["Review and run the official install flow."]
""",
        """
[tool.skill_lifecycle.install]
mode = "manual-required"
instructions = ["Review and run the official install flow."]

[tool.skill_lifecycle.install.by_harness]
pi = ["pi install demo"]
""",
    )

    with pytest.raises(ValueError, match="demo-skills"):
        load_tools(_write(tmp_path, manifest))


def test_superpowers_catalog_is_multi_host_without_a_forced_pi_dependency() -> None:
    tool = _tools()["superpowers"]
    lifecycle = tool.skill_lifecycle

    assert tool.requires == ()
    assert lifecycle is not None
    assert {
        "claude",
        "codex",
        "pi",
        "cursor",
        "factory-droid",
        "gemini-cli",
    } <= set(lifecycle.supported_harnesses)


def test_superpowers_install_on_a_claude_only_host_omits_pi(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    outcome = perform_action(
        _tools()["superpowers"],
        "install",
        lambda _argv: None,
        home=tmp_path,
        which=lambda _command: None,
    )

    text = "\n".join(outcome.instructions)
    assert outcome.status == "manual-required"
    assert "/plugin install superpowers@claude-plugins-official" in text
    assert "pi install" not in text


def test_superpowers_install_with_no_host_lists_every_upstream_command(tmp_path: Path) -> None:
    outcome = perform_action(
        _tools()["superpowers"],
        "install",
        lambda _argv: None,
        home=tmp_path,
        which=lambda _command: None,
    )
    text = "\n".join(outcome.instructions)

    assert outcome.instructions[0] == (
        "No supported agent host was detected on this machine; "
        "instructions for every supported host follow."
    )
    for fragment in (
        "/plugin install superpowers@claude-plugins-official",
        "agy plugin install https://github.com/obra/superpowers",
        "/add-plugin superpowers",
        "devin plugins install obra/superpowers",
        "droid plugin install superpowers@superpowers",
        "gemini extensions install https://github.com/obra/superpowers",
        "copilot plugin install superpowers@superpowers-marketplace",
        "grok plugin install superpowers@xai-official --trust",
        "/plugins install https://github.com/obra/superpowers",
        "Fetch and follow instructions from https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.opencode/INSTALL.md",
        "pi install git:github.com/obra/superpowers",
        "qwen extensions install obra/superpowers",
        "hermes plugins install obra/superpowers --enable",
        "muse plugins install ./superpowers",
    ):
        assert fragment in text
    assert (
        "/plugins (opens the plugin browser; search for superpowers and install it)"
        in outcome.instructions
    )


_HOST_HEADER = "Run each block inside the named host."


def test_superpowers_install_on_claude_only_host_is_framed_and_labeled(tmp_path: Path) -> None:
    outcome = perform_action(
        _tools()["superpowers"],
        "install",
        lambda _argv: None,
        home=tmp_path,
        which=lambda command: "/usr/bin/claude" if command == "claude" else None,
    )

    assert outcome.instructions[0] == _HOST_HEADER
    assert outcome.instructions[1] == "Claude Code:"
    assert outcome.instructions[2] == "/plugin install superpowers@claude-plugins-official"
    assert "obra/superpowers-marketplace" not in "\n".join(outcome.instructions)
    assert "pi install" not in "\n".join(outcome.instructions)


def test_superpowers_install_on_codex_only_host_is_one_labeled_line(tmp_path: Path) -> None:
    outcome = perform_action(
        _tools()["superpowers"],
        "install",
        lambda _argv: None,
        home=tmp_path,
        which=lambda command: "/usr/bin/codex" if command == "codex" else None,
    )

    assert outcome.instructions == (
        _HOST_HEADER,
        "Codex:",
        "/plugins (opens the plugin browser; search for superpowers and install it)",
    )
    assert "superpowers" not in outcome.instructions


def test_superpowers_install_on_claude_and_codex_labels_both_in_harness_order(
    tmp_path: Path,
) -> None:
    outcome = perform_action(
        _tools()["superpowers"],
        "install",
        lambda _argv: None,
        home=tmp_path,
        which=lambda command: f"/usr/bin/{command}" if command in {"claude", "codex"} else None,
    )

    assert outcome.instructions[0] == _HOST_HEADER
    claude_at = outcome.instructions.index("Claude Code:")
    codex_at = outcome.instructions.index("Codex:")
    assert claude_at < codex_at
    assert outcome.instructions[claude_at + 1].startswith("/plugin install")
    assert outcome.instructions[codex_at + 1].startswith("/plugins")


def test_superpowers_install_with_no_host_labels_every_block(tmp_path: Path) -> None:
    outcome = perform_action(
        _tools()["superpowers"],
        "install",
        lambda _argv: None,
        home=tmp_path,
        which=lambda _command: None,
    )
    lifecycle = _tools()["superpowers"].skill_lifecycle
    assert lifecycle is not None
    assert outcome.instructions[0] == (
        "No supported agent host was detected on this machine; "
        "instructions for every supported host follow."
    )
    for harness, commands in lifecycle.install.by_harness:
        label = f"{SKILL_HARNESS_LABELS.get(harness, harness)}:"
        index = outcome.instructions.index(label)
        assert outcome.instructions[index + 1 : index + 1 + len(commands)] == commands


def test_cursor_is_present_from_disk_when_path_misses(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()

    assert "cursor" in present_harnesses(tmp_path, lambda _command: None)


def test_skill_pack_admission_accepts_status_probes(tmp_path: Path) -> None:
    manifest = _minimal_lifecycle().replace(
        'supported_harnesses = ["codex"]',
        'supported_harnesses = ["codex"]\n'
        'status_probes = [{ harness = "codex", via = "plugin-cli", match = "demo" }]',
    )

    lifecycle = load_tools(_write(tmp_path, manifest))[0].skill_lifecycle

    assert lifecycle is not None
    assert lifecycle.status_probes == (SkillStatusProbe("codex", "plugin-cli", "demo"),)
    assert lifecycle.status.mode == "manual-required"


def test_skill_pack_admission_rejects_command_status_in_favor_of_status_probes(
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
instructions = ["unused"]
""",
    )

    with pytest.raises(ValueError, match="status_probes"):
        load_tools(_write(tmp_path, manifest))


@pytest.mark.parametrize(
    ("snippet", "error"),
    (
        (
            'status_probes = [{ harness = "pi", via = "plugin-cli", match = "demo" }]',
            "supported_harnesses",
        ),
        (
            'status_probes = [{ harness = "codex", via = "shell", match = "demo" }]',
            "unknown via",
        ),
        (
            'status_probes = [{ harness = "codex", via = "plugin-cli", match = "demo;rm" }]',
            "match",
        ),
        (
            (
                'status_probes = [{ harness = "codex", via = "plugin-cli", '
                'match = "demo", argv = ["sh"] }]'
            ),
            "unknown status_probes field",
        ),
    ),
)
def test_skill_pack_admission_rejects_invalid_status_probes(
    tmp_path: Path, snippet: str, error: str
) -> None:
    manifest = _minimal_lifecycle().replace(
        'supported_harnesses = ["codex"]',
        f'supported_harnesses = ["codex"]\n{snippet}',
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
def test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual(
    tool_id: str, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        if argv[0] == "claude":
            return "[]"
        return "ponytail@ponytail  installed, enabled  5.1.0\ngit:github.com/obra/superpowers\n"

    outcome = inspect_status(_tools()[tool_id], probe, home=tmp_path)

    if tool_id in {"ponytail", "superpowers"}:
        assert outcome.status == "present"
        assert calls
    elif tool_id in {"softaworks-agent-toolkit", "matt-pocock-skills", "opengsd"}:
        assert outcome.status == "absent"
    else:
        assert outcome.status == "manual-required"
        assert outcome.instructions
        assert calls == []


def test_shipped_status_probes_select_closed_sources() -> None:
    tools = _tools()
    ponytail = tools["ponytail"].skill_lifecycle
    superpowers = tools["superpowers"].skill_lifecycle
    assert ponytail is not None
    assert superpowers is not None

    assert SkillStatusProbe("codex", "plugin-cli", "ponytail") in ponytail.status_probes
    assert SkillStatusProbe("pi", "plugin-cli", "obra/superpowers") in superpowers.status_probes
    assert (
        SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official")
        in superpowers.status_probes
    )
    assert ponytail.status.mode == "manual-required"
    assert superpowers.status.mode == "manual-required"
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
            "install_fragment": (
                "pnpm dlx @opengsd/gsd-core@1.16.0 --<runtime> --local --relative-includes"
            ),
            "update_fragment": "--local --relative-includes",
            "removal_fragment": "--local --uninstall",
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


_SUPERPOWERS_ID = "superpowers@claude-plugins-official"
_FOUR_INSTALL = (
    (_SUPERPOWERS_ID, "user", False, "6.4.1"),
    (_SUPERPOWERS_ID, "project", True, "6.2.0"),
    ("superpowers@superpowers-marketplace", "user", True, "6.2.0"),
    ("superpowers@superpowers-marketplace", "project", True, "6.2.0"),
)


_CLAUDE_SUPERPOWERS_JSON = (
    '[{"id": "superpowers@claude-plugins-official", "scope": "user", '
    '"enabled": true, "version": "6.4.1"}]'
)


def _hosts(
    tools: list[Tool], probe: Callable[[list[str]], str], home: Path
) -> dict[str, dict[str, HarnessStatus]]:
    """Host answers of `inspect_skill_reports`, the shape the deleted projection returned."""
    return {
        tool_id: report.hosts
        for tool_id, report in inspect_skill_reports(tools, probe, home).items()
    }


def _claude_json(*entries: tuple[str, str, bool, str]) -> str:
    return json.dumps(
        [
            {"id": plugin_id, "scope": scope, "enabled": enabled, "version": version}
            for plugin_id, scope, enabled, version in entries
        ]
    )


def _claude_status(tmp_path: Path, output: str, match: str = _SUPERPOWERS_ID) -> str:
    tool = _pack("superpowers", (SkillStatusProbe("claude", "plugin-cli", match),))
    return _hosts([tool], lambda _argv: output, tmp_path)["superpowers"]["claude"]


def _pack(tool_id: str, probes: tuple[SkillStatusProbe, ...]) -> Tool:
    manual = SkillOperation(
        mode="manual-required", instructions=("Review and run the official flow.",)
    )
    harnesses = tuple(dict.fromkeys(probe.harness for probe in probes)) or ("codex",)
    return Tool(
        id=tool_id,
        name=tool_id,
        category="ai",
        cmd=tool_id,
        methods=(Method(kind="skill_pack"),),
        skill_lifecycle=SkillLifecycle(
            source="https://github.com/example/skills",
            owner="example",
            supported_harnesses=harnesses,
            revision_policy="upstream-latest",
            targets=(SkillTarget("harness", "<codex-plugin-dir>/demo"),),
            install=manual,
            status=manual,
            update=manual,
            removal=manual,
            status_probes=probes,
        ),
    )


def test_shipped_packs_report_per_host_status(tmp_path: Path) -> None:
    tools = _tools()
    superpowers = tools["superpowers"]
    ponytail = tools["ponytail"]

    def probe(argv: list[str]) -> str:
        if argv == ["pi", "list"]:
            return "git:github.com/obra/superpowers\n"
        if argv == ["codex", "plugin", "list"]:
            return "ponytail@ponytail  installed, enabled  5.1.0\n"
        return ""

    result = _hosts([superpowers, ponytail], probe, tmp_path)

    assert result["superpowers"]["pi"] == "present"
    assert result["ponytail"]["codex"] == "present"


def test_codex_not_installed_row_is_absent(tmp_path: Path) -> None:
    tool = _pack("superpowers", (SkillStatusProbe("codex", "plugin-cli", "superpowers"),))

    def probe(argv: list[str]) -> str:
        assert argv == ["codex", "plugin", "list"]
        return "superpowers@openai-curated  not installed\n"

    assert _hosts([tool], probe, tmp_path) == {"superpowers": {"codex": "absent"}}


def test_codex_probe_failure_is_unknown_for_every_pack(tmp_path: Path) -> None:
    packs = [
        _pack("ponytail", (SkillStatusProbe("codex", "plugin-cli", "ponytail"),)),
        _pack("other", (SkillStatusProbe("codex", "plugin-cli", "other"),)),
    ]

    def probe(_argv: list[str]) -> str:
        raise RuntimeError("codex down")

    assert _hosts(packs, probe, tmp_path) == {
        "ponytail": {"codex": "unknown"},
        "other": {"codex": "unknown"},
    }


def test_plugin_cli_without_closed_row_is_unknown_and_unprobed(tmp_path: Path) -> None:
    tool = _pack("demo", (SkillStatusProbe("opencode", "plugin-cli", "x"),))
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "x"

    assert _hosts([tool], probe, tmp_path) == {"demo": {"opencode": "unknown"}}
    assert calls == []


def test_claude_plugin_list_marker_row_is_present(tmp_path: Path) -> None:
    tool = _pack("superpowers", (SkillStatusProbe("claude", "plugin-cli", _SUPERPOWERS_ID),))

    def probe(argv: list[str]) -> str:
        assert argv == ["claude", "plugin", "list", "--json"]
        return _claude_json((_SUPERPOWERS_ID, "user", True, "6.4.1"))

    assert _hosts([tool], probe, tmp_path)["superpowers"]["claude"] == "present"


def test_claude_match_stops_at_name_boundary(tmp_path: Path) -> None:
    listing = _claude_json(("superpowers-extra@m", "user", True, "1.0.0"))

    assert _claude_status(tmp_path, listing, "superpowers@m") == "absent"


def test_empty_cli_output_is_absent(tmp_path: Path) -> None:
    tool = _pack("ponytail", (SkillStatusProbe("codex", "plugin-cli", "ponytail"),))

    assert _hosts([tool], lambda _argv: "", tmp_path)["ponytail"]["codex"] == "absent"


def _lock_pack(tool_id: str = "softaworks") -> Tool:
    return _pack(tool_id, (SkillStatusProbe("claude", "skills-lock", "softaworks/agent-toolkit"),))


def _write_lock(home: Path, payload: object) -> None:
    agents = home / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / ".skill-lock.json").write_text(json.dumps(payload), encoding="utf-8")


def test_skills_lock_present_when_source_and_skill_dir_exist(tmp_path: Path) -> None:
    _write_lock(
        tmp_path,
        {"skills": {"c4-architecture": {"source": "softaworks/agent-toolkit"}}},
    )
    (tmp_path / ".claude" / "skills" / "c4-architecture").mkdir(parents=True)

    result = _hosts([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "present"


def test_skills_lock_absent_when_skill_dir_missing(tmp_path: Path) -> None:
    _write_lock(
        tmp_path,
        {"skills": {"c4-architecture": {"source": "softaworks/agent-toolkit"}}},
    )

    result = _hosts([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "absent"


def test_skills_lock_absent_when_lock_file_missing(tmp_path: Path) -> None:
    result = _hosts([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "absent"


@pytest.mark.parametrize("payload", ("{", '{"skills": ["nope"]}'))
def test_skills_lock_malformed_or_wrong_shape_is_unknown(tmp_path: Path, payload: str) -> None:
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / ".skill-lock.json").write_text(payload, encoding="utf-8")

    result = _hosts([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "unknown"


def test_skills_lock_ignores_traversal_skill_names(tmp_path: Path) -> None:
    _write_lock(tmp_path, {"skills": {"../evil": {"source": "softaworks/agent-toolkit"}}})
    decoy = tmp_path / ".claude" / "evil"
    decoy.parent.mkdir(parents=True)
    decoy.write_text("decoy", encoding="utf-8")

    result = _hosts([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "absent"


def test_skills_lock_unknown_harness_is_unknown(tmp_path: Path) -> None:
    tool = _pack(
        "softaworks", (SkillStatusProbe("muse", "skills-lock", "softaworks/agent-toolkit"),)
    )
    _write_lock(
        tmp_path,
        {"skills": {"c4-architecture": {"source": "softaworks/agent-toolkit"}}},
    )
    (tmp_path / ".muse" / "skills" / "c4-architecture").mkdir(parents=True)

    result = _hosts([tool], lambda _argv: "", tmp_path)

    assert result["softaworks"]["muse"] == "unknown"


def test_install_state_file_is_present_and_missing_is_absent(tmp_path: Path) -> None:
    tool = _pack("opengsd", (SkillStatusProbe("claude", "install-state", "gsd-core"),))
    absent = _hosts([tool], lambda _argv: "", tmp_path)
    state = tmp_path / ".claude" / "gsd-install-state.json"
    state.parent.mkdir()
    state.write_text("{}", encoding="utf-8")
    present = _hosts([tool], lambda _argv: "", tmp_path)

    assert absent["opengsd"]["claude"] == "absent"
    assert present["opengsd"]["claude"] == "present"


def test_install_state_probe_honors_match(tmp_path: Path) -> None:
    state = tmp_path / ".claude" / "gsd-install-state.json"
    state.parent.mkdir()
    state.write_text("{}", encoding="utf-8")

    assert (
        _install_state_status(SkillStatusProbe("claude", "install-state", "gsd-core"), tmp_path)
        == "present"
    )
    assert (
        _install_state_status(
            SkillStatusProbe("claude", "install-state", "something-else"), tmp_path
        )
        == "unknown"
    )


def test_install_state_unknown_harness_is_unknown(tmp_path: Path) -> None:
    tool = _pack("opengsd", (SkillStatusProbe("pi", "install-state", "gsd-core"),))
    (tmp_path / ".pi" / "gsd-install-state.json").parent.mkdir()
    (tmp_path / ".pi" / "gsd-install-state.json").write_text("{}", encoding="utf-8")

    result = _hosts([tool], lambda _argv: "", tmp_path)

    assert result["opengsd"]["pi"] == "unknown"


def test_skills_lock_is_read_once_per_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_lock(
        tmp_path,
        {"skills": {"c4-architecture": {"source": "softaworks/agent-toolkit"}}},
    )
    (tmp_path / ".claude" / "skills" / "c4-architecture").mkdir(parents=True)
    reads = 0
    real_loads = json.loads

    def counting(text: str) -> object:
        nonlocal reads
        reads += 1
        return real_loads(text)

    monkeypatch.setattr("installer.skill_lifecycle.json.loads", counting)
    packs = [_lock_pack("a"), _lock_pack("b")]

    _hosts(packs, lambda _argv: "", tmp_path)

    assert reads == 1


def test_one_cli_call_per_harness_across_packs(tmp_path: Path) -> None:
    packs = [
        _pack(
            f"pack-{index}",
            (SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),),
        )
        for index in range(3)
    ]
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return _CLAUDE_SUPERPOWERS_JSON

    _hosts(packs, probe, tmp_path)

    assert calls == [["claude", "plugin", "list", "--json"]]


def test_host_order_follows_skill_harnesses_not_declaration_order(tmp_path: Path) -> None:
    tool = _pack(
        "demo",
        (
            SkillStatusProbe("pi", "plugin-cli", "obra/superpowers"),
            SkillStatusProbe("claude", "plugin-cli", "superpowers@claude-plugins-official"),
            SkillStatusProbe("codex", "plugin-cli", "ponytail"),
        ),
    )

    result = _hosts([tool], lambda _argv: "", tmp_path)["demo"]

    assert list(result) == [harness for harness in SKILL_HARNESSES if harness in result]
    assert list(result) == ["claude", "codex", "pi"]


def test_empty_status_probes_map_to_empty_dict(tmp_path: Path) -> None:
    tool = _pack("demo", ())

    assert _hosts([tool], lambda _argv: "nope", tmp_path) == {"demo": {}}


def test_skill_hosts_are_idempotent(tmp_path: Path) -> None:
    tool = _pack("demo", (SkillStatusProbe("pi", "plugin-cli", "obra/superpowers"),))

    def probe(_argv: list[str]) -> str:
        return "obra/superpowers\n"

    assert _hosts([tool], probe, tmp_path) == _hosts([tool], probe, tmp_path)


def test_skill_harness_labels_cover_every_harness() -> None:
    assert set(SKILL_HARNESS_LABELS) == set(SKILL_HARNESSES)
    assert all(label.isascii() and label for label in SKILL_HARNESS_LABELS.values())
    assert SKILL_HARNESS_LABELS["claude"] == "Claude Code"
    assert SKILL_HARNESS_LABELS["codex"] == "Codex"
    assert SKILL_HARNESS_LABELS["pi"] == "Pi"
    assert SKILL_HARNESS_LABELS["gemini-cli"] == "Gemini CLI"
    assert SKILL_HARNESS_LABELS["factory-droid"] == "Factory Droid"


def test_claude_probe_uses_the_json_argv(tmp_path: Path) -> None:
    packs = [
        _pack(f"pack-{index}", (SkillStatusProbe("claude", "plugin-cli", _SUPERPOWERS_ID),))
        for index in range(3)
    ]
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return _claude_json((_SUPERPOWERS_ID, "user", True, "6.4.1"))

    result = _hosts(packs, probe, tmp_path)

    assert calls == [["claude", "plugin", "list", "--json"]]
    assert all(hosts == {"claude": "present"} for hosts in result.values())


def test_claude_enabled_user_scope_canonical_is_present(tmp_path: Path) -> None:
    listing = _claude_json((_SUPERPOWERS_ID, "user", True, "6.4.1"))

    assert _claude_status(tmp_path, listing) == "present"


def test_four_install_superpowers_state_is_not_present(tmp_path: Path) -> None:
    assert _claude_status(tmp_path, _claude_json(*_FOUR_INSTALL)) == "absent"


def test_claude_project_scope_only_is_absent(tmp_path: Path) -> None:
    listing = _claude_json((_SUPERPOWERS_ID, "project", True, "6.4.1"))

    assert _claude_status(tmp_path, listing) == "absent"


def test_claude_other_marketplace_only_is_absent(tmp_path: Path) -> None:
    listing = _claude_json(("superpowers@superpowers-marketplace", "user", True, "6.2.0"))

    assert _claude_status(tmp_path, listing) == "absent"


def test_claude_two_enabled_user_entries_for_the_canonical_id_is_absent(tmp_path: Path) -> None:
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", True, "6.4.1"), (_SUPERPOWERS_ID, "user", True, "6.2.0")
    )

    assert _claude_status(tmp_path, listing) == "absent"
    report = _superpowers_report(tmp_path, listing)
    assert report.reasons == (
        "duplicate: superpowers@claude-plugins-official in user scope (6.4.1)",
        "duplicate: superpowers@claude-plugins-official in user scope (6.2.0)",
    )
    assert report.steps == ()


def test_two_disabled_canonical_user_entries_get_no_enable_step(tmp_path: Path) -> None:
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", False, "6.4.1"), (_SUPERPOWERS_ID, "user", False, "6.2.0")
    )

    report = _superpowers_report(tmp_path, listing)

    assert report.reasons == (
        "duplicate: superpowers@claude-plugins-official in user scope (6.4.1)",
        "duplicate: superpowers@claude-plugins-official in user scope (6.2.0)",
    )
    assert not any(step.kind in {"plugin_enable", "skill_install"} for step in report.steps)


_CANONICAL_ENTRY = {"id": _SUPERPOWERS_ID, "scope": "user", "enabled": True, "version": "6.4.1"}


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        json.dumps(_CANONICAL_ENTRY),
        json.dumps([{**_CANONICAL_ENTRY, "enabled": "true"}]),
        json.dumps([_CANONICAL_ENTRY, {**_CANONICAL_ENTRY, "scope": "project", "enabled": 1}]),
        json.dumps([_CANONICAL_ENTRY, "superpowers@superpowers-marketplace"]),
        json.dumps([{**_CANONICAL_ENTRY, "version": 6}]),
        json.dumps([_CANONICAL_ENTRY]) + " " * (1 << 20),
    ],
    ids=[
        "not-json",
        "object",
        "canonical-enabled-str",
        "other-enabled-int",
        "non-object-entry",
        "version-int",
        "over-1-mib",
    ],
)
def test_claude_unparseable_json_is_unknown(tmp_path: Path, output: str) -> None:
    assert _claude_status(tmp_path, output) == "unknown"


@pytest.mark.parametrize("scope", ["global", "-s", "User"])
def test_claude_scope_outside_the_closed_set_is_unknown(tmp_path: Path, scope: str) -> None:
    listing = json.dumps(
        [
            _CANONICAL_ENTRY,
            {**_CANONICAL_ENTRY, "id": "superpowers@superpowers-marketplace", "scope": scope},
        ]
    )

    assert _claude_status(tmp_path, listing) == "unknown"


def test_registry_claude_plugin_probes_use_canonical_ids() -> None:
    checked = 0
    for tool in load_tools(REGISTRY):
        lifecycle = tool.skill_lifecycle
        if lifecycle is None:
            continue
        for probe in lifecycle.status_probes:
            if (probe.harness, probe.via) != ("claude", "plugin-cli"):
                continue
            plugin, _, marketplace = probe.match.partition("@")
            assert plugin and marketplace, tool.id
            claude_lines = dict(lifecycle.install.by_harness)["claude"]
            assert any(line.endswith(f"install {probe.match}") for line in claude_lines), tool.id
            checked += 1
    assert checked == 3


_MARKETPLACE_ID = "superpowers@superpowers-marketplace"


def _installed_plugins(home: Path, records: list[tuple[str, str, object]]) -> None:
    plugins: dict[str, list[dict[str, object]]] = {}
    for plugin_id, scope, project_path in records:
        record: dict[str, object] = {"scope": scope, "version": "6.2.0"}
        if project_path is not None:
            record["projectPath"] = project_path
        plugins.setdefault(plugin_id, []).append(record)
    target = home / ".claude" / "plugins"
    target.mkdir(parents=True, exist_ok=True)
    payload = {"version": 2, "plugins": plugins}
    (target / "installed_plugins.json").write_text(json.dumps(payload), encoding="utf-8")


def _project_dirs(home: Path) -> tuple[Path, Path]:
    official, market = home / "repo-official", home / "repo-market"
    official.mkdir()
    market.mkdir()
    return official, market


def _superpowers_report(home: Path, listing: str) -> SkillPackReport:
    tool = _pack("superpowers", (SkillStatusProbe("claude", "plugin-cli", _SUPERPOWERS_ID),))
    return inspect_skill_reports([tool], lambda _argv: listing, home)["superpowers"]


def _claude_step(
    text: str, kind: ConfigStepKind, *argv: str, cwd: Path | None = None
) -> ConfigStep:
    return ConfigStep(
        text=text,
        kind=kind,
        harness="claude",
        argv=("claude", "plugin", *argv),
        cwd=cwd,
    )


def test_four_install_state_reasons_and_ordered_steps(tmp_path: Path) -> None:
    official, market = _project_dirs(tmp_path)
    _installed_plugins(
        tmp_path,
        [
            (_SUPERPOWERS_ID, "user", None),
            (_SUPERPOWERS_ID, "project", str(official)),
            (_MARKETPLACE_ID, "user", None),
            (_MARKETPLACE_ID, "project", str(market)),
        ],
    )

    report = _superpowers_report(tmp_path, _claude_json(*_FOUR_INSTALL))

    assert report.hosts == {"claude": "absent"}
    assert report.reasons == (
        "disabled: superpowers@claude-plugins-official in user scope (6.4.1)",
        "duplicate: superpowers@claude-plugins-official in project scope (6.2.0)",
        "duplicate: superpowers@superpowers-marketplace in user scope (6.2.0)",
        "duplicate: superpowers@superpowers-marketplace in project scope (6.2.0)",
    )
    assert report.steps == (
        _claude_step(
            "enable superpowers@claude-plugins-official in user scope",
            "plugin_enable",
            *("enable", "-s", "user", _SUPERPOWERS_ID),
        ),
        _claude_step(
            "remove superpowers@claude-plugins-official from project scope",
            "plugin_uninstall",
            *("uninstall", "-s", "project", _SUPERPOWERS_ID),
            cwd=official,
        ),
        _claude_step(
            "remove superpowers@superpowers-marketplace from user scope",
            "plugin_uninstall",
            *("uninstall", "-s", "user", _MARKETPLACE_ID),
        ),
        _claude_step(
            "remove superpowers@superpowers-marketplace from project scope",
            "plugin_uninstall",
            *("uninstall", "-s", "project", _MARKETPLACE_ID),
            cwd=market,
        ),
        _claude_step(
            "remove marketplace superpowers-marketplace",
            "marketplace_remove",
            *("marketplace", "remove", "superpowers-marketplace"),
        ),
    )


def _four_install_home(tmp_path: Path, *, market_path: bool = True) -> None:
    official, market = _project_dirs(tmp_path)
    _installed_plugins(
        tmp_path,
        [
            (_SUPERPOWERS_ID, "project", str(official)),
            (_MARKETPLACE_ID, "project", str(market) if market_path else None),
        ],
    )


def test_marketplace_is_kept_while_another_plugin_uses_it(tmp_path: Path) -> None:
    _four_install_home(tmp_path)
    listing = _claude_json(*_FOUR_INSTALL, ("other@superpowers-marketplace", "user", True, "1.0"))

    report = _superpowers_report(tmp_path, listing)

    assert [step.kind for step in report.steps] == [
        "plugin_enable",
        "plugin_uninstall",
        "plugin_uninstall",
        "plugin_uninstall",
    ]


def test_missing_canonical_installs_first(tmp_path: Path) -> None:
    _four_install_home(tmp_path)

    report = _superpowers_report(tmp_path, _claude_json(*_FOUR_INSTALL[2:]))

    assert report.steps[0] == _claude_step(
        "install superpowers@claude-plugins-official in user scope",
        "skill_install",
        *("install", "-s", "user", _SUPERPOWERS_ID),
    )
    assert [step.kind for step in report.steps[1:]] == [
        "plugin_uninstall",
        "plugin_uninstall",
        "marketplace_remove",
    ]
    assert report.reasons == (
        "duplicate: superpowers@superpowers-marketplace in user scope (6.2.0)",
        "duplicate: superpowers@superpowers-marketplace in project scope (6.2.0)",
    )


@pytest.mark.parametrize("case", ["missing", "relative", "file", "nonexistent", "two-candidates"])
def test_project_copy_without_a_valid_project_path_has_no_step(tmp_path: Path, case: str) -> None:
    (tmp_path / "a-file").write_text("x", encoding="utf-8")
    (tmp_path / "repo-1").mkdir()
    (tmp_path / "repo-2").mkdir()
    paths: dict[str, list[object]] = {
        "missing": [None],
        "relative": ["repo-1"],
        "file": [str(tmp_path / "a-file")],
        "nonexistent": [str(tmp_path / "gone")],
        "two-candidates": [str(tmp_path / "repo-1"), str(tmp_path / "repo-2")],
    }
    _installed_plugins(tmp_path, [(_SUPERPOWERS_ID, "project", path) for path in paths[case]])
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", True, "6.4.1"), (_SUPERPOWERS_ID, "project", True, "6.2.0")
    )

    report = _superpowers_report(tmp_path, listing)

    assert report.hosts == {"claude": "present"}
    assert report.reasons == (
        "duplicate: superpowers@claude-plugins-official in project scope (6.2.0)",
    )
    assert report.steps == ()


@pytest.mark.parametrize("hostile", ["-s@x", "a b@c", "superpowers@claude-plugins-official;rm"])
def test_hostile_ids_never_reach_argv(tmp_path: Path, hostile: str) -> None:
    listing = _claude_json((_SUPERPOWERS_ID, "user", False, "6.4.1"), (hostile, "user", True, "1"))

    report = _superpowers_report(tmp_path, listing)

    assert report == SkillPackReport(hosts={"claude": "unknown"})
    assert (report.reasons, report.steps) == ((), ())


def test_marketplace_is_kept_when_a_copy_has_no_step(tmp_path: Path) -> None:
    _four_install_home(tmp_path, market_path=False)

    report = _superpowers_report(tmp_path, _claude_json(*_FOUR_INSTALL))

    assert len(report.reasons) == 4
    assert "duplicate: superpowers@superpowers-marketplace in project scope (6.2.0)" in (
        report.reasons
    )
    assert [(step.kind, step.argv[-1]) for step in report.steps] == [
        ("plugin_enable", _SUPERPOWERS_ID),
        ("plugin_uninstall", _SUPERPOWERS_ID),
        ("plugin_uninstall", _MARKETPLACE_ID),
    ]
    assert report.steps[2].argv[3:5] == ("-s", "user")


def _raise_called_process_error(argv: list[str]) -> str:
    raise subprocess.CalledProcessError(1, argv)


@pytest.mark.parametrize("answer", ["raises", "not-json"])
def test_four_install_pack_with_an_unreadable_listing_is_an_unknown_host(
    tmp_path: Path, answer: str
) -> None:
    _four_install_home(tmp_path)
    tool = _pack("superpowers", (SkillStatusProbe("claude", "plugin-cli", _SUPERPOWERS_ID),))

    def probe(argv: list[str]) -> str:
        assert argv == ["claude", "plugin", "list", "--json"]
        return _raise_called_process_error(argv) if answer == "raises" else "not json"

    report = inspect_skill_reports([tool], probe, tmp_path)["superpowers"]

    assert report.hosts["claude"] == "unknown"
    assert report.reasons == ()
    assert report.steps == ()


def test_clean_canonical_install_has_no_reasons_or_steps(tmp_path: Path) -> None:
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", True, "6.4.1"), ("ponytail@ponytail", "user", True, "5.1.0")
    )

    report = _superpowers_report(tmp_path, listing)

    assert report == SkillPackReport(hosts={"claude": "present"})


@pytest.mark.parametrize(
    "content",
    [
        None,
        b"x" * (64 * 1024 + 1),
        b"not json",
        b"[]",
        b'{"plugins": []}',
        b'{"plugins": {"superpowers@claude-plugins-official": {}}}',
        b'{"plugins": {"superpowers@claude-plugins-official": ["x", {"scope": 1}]}}',
    ],
    ids=["missing", "over-64-kib", "not-json", "list", "plugins-list", "records-object", "bad"],
)
def test_unreadable_installed_plugins_keeps_the_reason_without_a_step(
    tmp_path: Path, content: bytes | None
) -> None:
    if content is not None:
        target = tmp_path / ".claude" / "plugins"
        target.mkdir(parents=True)
        (target / "installed_plugins.json").write_bytes(content)
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", True, "6.4.1"), (_SUPERPOWERS_ID, "local", True, "6.2.0")
    )

    report = _superpowers_report(tmp_path, listing)

    assert report.reasons == (
        "duplicate: superpowers@claude-plugins-official in local scope (6.2.0)",
    )
    assert report.steps == ()


def test_a_tool_without_a_skill_lifecycle_reports_no_hosts(tmp_path: Path) -> None:
    tool = Tool(id="rg", name="rg", category="search", cmd="rg", methods=(Method(kind="cargo"),))

    assert inspect_skill_reports([tool], lambda _argv: "", tmp_path) == {
        "rg": SkillPackReport(hosts={})
    }


def test_partial_harnesses_lists_present_probed_absent_hosts() -> None:
    hosts: dict[str, HarnessStatus] = {"claude": "present", "codex": "absent", "pi": "absent"}

    assert partial_harnesses(hosts, ("claude", "codex", "pi"), {"claude", "codex"}) == ("codex",)


def test_partial_harnesses_needs_one_present_host() -> None:
    supported = ("claude", "codex", "pi")
    present = {"claude", "codex", "pi"}
    absent: dict[str, HarnessStatus] = {"claude": "absent", "codex": "absent"}
    unknown: dict[str, HarnessStatus] = {"claude": "present", "codex": "unknown"}

    assert partial_harnesses(absent, supported, present) == ()
    assert partial_harnesses(unknown, supported, present) == ()


def test_partial_harnesses_ignores_unsupported_hosts() -> None:
    hosts: dict[str, HarnessStatus] = {"claude": "present", "codex": "absent", "pi": "absent"}

    assert partial_harnesses(hosts, ("claude", "pi"), {"claude", "codex", "pi"}) == ("pi",)


def test_partial_steps_text() -> None:
    reasons, steps = partial_steps(_tools()["superpowers"], ("codex",))

    assert reasons == ("partial: missing on Codex",)
    assert steps == (
        ConfigStep(text="install superpowers for Codex", kind="skill_install", harness="codex"),
    )
    assert steps[0].argv == ()


_GLOBAL_REASON = "installed globally; this pack is project-local"
# One GSD 1.16.0 global leftover per harness home, each in a different kind of dir.
_GSD_HOME_LEFTOVERS = {
    "antigravity": ".gemini/config/skills/gsd-x",
    "claude": ".claude/agents/gsd-x.md",
    "codex": ".agents/skills/gsd-x",
    "copilot": ".copilot/skills/gsd-x",
    "cursor": ".cursor/gsd-core",
    "kilo": ".config/kilo/command/gsd-x.md",
    "kimi": ".kimi-code/skills/gsd-x",
    "opencode": ".config/opencode/commands/gsd-x.md",
    "windsurf": ".codeium/windsurf/hooks/gsd-check-update.js",
}


def _plant(home: Path, relative: str, content: str = "x") -> None:
    path = home / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix or path.name == "VERSION":
        path.write_text(content, encoding="utf-8")
    else:
        path.mkdir()


def _uninstall_step(harness: str) -> ConfigStep:
    runtime = "kimi-code" if harness == "kimi" else harness
    return ConfigStep(
        text=f"uninstall the global opengsd install for {SKILL_HARNESS_LABELS[harness]}",
        kind="project_pack_global_uninstall",
        harness=harness,
        argv=("pnpm", "dlx", "@opengsd/gsd-core@1.16.0", f"--{runtime}", "--global", "--uninstall"),
    )


def _home_fingerprint(home: Path) -> dict[str, tuple[bytes | None, int]]:
    paths = [home, *sorted(home.rglob("*"))]
    return {
        str(path.relative_to(home)): (
            path.read_bytes() if path.is_file() and not path.is_symlink() else None,
            path.lstat().st_mtime_ns,
        )
        for path in paths
    }


def test_registry_opengsd_is_a_pinned_project_pack() -> None:
    packs = {tool.id: tool.skill_lifecycle for tool in load_tools(REGISTRY) if tool.skill_lifecycle}
    opengsd = packs["opengsd"]

    assert (opengsd.scope, opengsd.version) == ("project", "1.16.0")
    assert opengsd.targets
    assert {target.scope for target in opengsd.targets} == {"project"}
    assert {tool_id for tool_id, pack in packs.items() if pack.scope == "user"} == (
        set(packs) - {"opengsd"}
    )
    assert {tool_id for tool_id, pack in packs.items() if pack.scope == "project"} <= set(
        PROJECT_PACK_PACKAGES
    )


def test_global_leftover_yields_the_uninstall_step(tmp_path: Path) -> None:
    _plant(tmp_path, ".claude/gsd-core/VERSION", "1.16.0\n")
    _plant(tmp_path, ".claude/commands/gsd-plan.md")

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset({"claude"}))

    assert report.reasons[0].startswith(_GLOBAL_REASON)
    assert report.reasons == (_GLOBAL_REASON,)
    assert report.leftovers == ("claude",)
    assert report.steps == (
        ConfigStep(
            text="uninstall the global opengsd install for Claude Code",
            kind="project_pack_global_uninstall",
            harness="claude",
            argv=("pnpm", "dlx", "@opengsd/gsd-core@1.16.0", "--claude", "--global", "--uninstall"),
        ),
    )


@pytest.mark.parametrize("harness", sorted(_GSD_HOME_LEFTOVERS))
def test_global_leftover_in_every_harness_home(tmp_path: Path, harness: str) -> None:
    _plant(tmp_path, _GSD_HOME_LEFTOVERS[harness])

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset({harness}))

    assert report.leftovers == (harness,)
    assert report.reasons[0] == _GLOBAL_REASON
    assert report.steps == (_uninstall_step(harness),)
    if harness == "kimi":
        assert "--kimi-code" in report.steps[0].argv


def test_global_leftover_scan_covers_install_state_harness_dirs() -> None:
    assert set(PROJECT_GLOBAL_MACHINERY) == set(INSTALL_STATE_HARNESS_DIRS)
    assert set(_GSD_HOME_LEFTOVERS) == set(INSTALL_STATE_HARNESS_DIRS)
    for harness, home_dir in INSTALL_STATE_HARNESS_DIRS.items():
        for sub in ("skills", "agents", "commands", "hooks"):
            assert f"{home_dir}/{sub}" in PROJECT_GLOBAL_MACHINERY[harness]


def test_global_leftover_detection_writes_nothing(tmp_path: Path) -> None:
    for relative in _GSD_HOME_LEFTOVERS.values():
        _plant(tmp_path, relative)
    _plant(tmp_path, ".claude/gsd-core/VERSION", "1.16.0\n")
    before = _home_fingerprint(tmp_path)

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == tuple(INSTALL_STATE_HARNESS_DIRS)
    assert _home_fingerprint(tmp_path) == before


def test_no_leftover_no_reason(tmp_path: Path) -> None:
    tool = _tools()["opengsd"]
    assert inspect_project_pack(tool, tmp_path, frozenset({"claude"})) == ProjectPackReport()

    for relative in (
        ".claude/skills/superpowers",
        ".claude/skills/my-gsd-notes",
        ".agents/skills/superpowers",
        ".codex/agents/notes-gsd-x.md",
    ):
        _plant(tmp_path, relative)

    assert inspect_project_pack(tool, tmp_path, frozenset({"claude"})) == ProjectPackReport()
    # A user-scope pack has no project-pack facts at all.
    _plant(tmp_path, ".claude/gsd-core/VERSION")
    superpowers = _tools()["superpowers"]
    assert inspect_project_pack(superpowers, tmp_path, frozenset({"claude"})) == (
        ProjectPackReport()
    )


def test_shared_agents_skills_leftover_names_the_path(tmp_path: Path) -> None:
    tool = _tools()["opengsd"]
    _plant(tmp_path, ".agents/skills/gsd-plan")

    report = inspect_project_pack(tool, tmp_path, frozenset({"codex"}))

    assert report.leftovers == ("codex",)
    assert report.steps == (_uninstall_step("codex"),)
    assert report.reasons == (
        _GLOBAL_REASON,
        "gsd-* entries in ~/.agents/skills: GSD writes there for Codex and for Kimi CLI, "
        "so the Codex uninstall may not remove them",
    )

    other = tmp_path / "other"
    _plant(other, ".codex/agents/gsd-x.md")
    only_codex_home = inspect_project_pack(tool, other, frozenset({"codex"}))
    assert only_codex_home.leftovers == ("codex",)
    assert only_codex_home.reasons == (_GLOBAL_REASON,)


def _claude_hook_settings(command: str) -> str:
    return json.dumps(
        {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}}
    )


_GSD_HOOK_COMMAND = 'node "$HOME"/.claude/hooks/gsd-check-update.js'


def _write_bytes(home: Path, relative: str, data: bytes) -> Path:
    path = home / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_claude_settings_hooks_are_a_leftover(tmp_path: Path) -> None:
    _plant(tmp_path, ".claude/settings.json", _claude_hook_settings(_GSD_HOOK_COMMAND))

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset({"claude"}))

    assert report.leftovers == ("claude",)
    assert report.reasons == (_GLOBAL_REASON,)
    assert report.steps == (_uninstall_step("claude"),)
    assert report.unchecked == ()


def test_antigravity_settings_hooks_are_a_leftover(tmp_path: Path) -> None:
    command = "node ~/.gemini/antigravity/hooks/gsd-check-update.js"
    _plant(tmp_path, ".gemini/antigravity/settings.json", _claude_hook_settings(command))

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == ("antigravity",)
    assert report.steps == (_uninstall_step("antigravity"),)


@pytest.mark.parametrize(
    ("harness", "relative", "document"),
    [
        (
            "codex",
            ".codex/hooks.json",
            {
                "hooks": {
                    "PostToolUse": [{"command": "node /h/.codex/hooks/gsd-context-monitor.js"}]
                }
            },
        ),
        (
            "cursor",
            ".cursor/hooks.json",
            {"version": 1, "hooks": {"stop": [{"command": "./hook.sh", "gsd-managed": True}]}},
        ),
        (
            "windsurf",
            ".codeium/windsurf/hooks.json",
            {"hooks": {"post_cascade_response": [{"command": "x", "gsd-managed": True}]}},
        ),
    ],
)
def test_hooks_json_surfaces(
    tmp_path: Path, harness: str, relative: str, document: dict[str, object]
) -> None:
    _plant(tmp_path, relative, json.dumps(document))

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == (harness,)
    assert report.steps == (_uninstall_step(harness),)


@pytest.mark.parametrize(
    ("harness", "relative", "block"),
    [
        (
            "kimi",
            ".kimi-code/config.toml",
            "# GSD Hooks BEGIN — managed by GSD, do not edit between these markers\n"
            '[[hooks]]\nevent = "SessionStart"\ncommand = "node gsd-check-update.js"\n'
            "# GSD Hooks END\n",
        ),
        (
            "codex",
            ".codex/config.toml",
            '# GSD Hooks\n[[hooks]]\nevent = "SessionStart"\ncommand = "node x.js"\n',
        ),
    ],
)
def test_toml_hook_blocks(tmp_path: Path, harness: str, relative: str, block: str) -> None:
    _plant(tmp_path, relative, 'model = "x"\n\n' + block)

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == (harness,)
    assert report.steps == (_uninstall_step(harness),)
    if harness == "kimi":
        assert "--kimi-code" in report.steps[0].argv


def test_user_hooks_are_not_a_leftover(tmp_path: Path) -> None:
    _plant(tmp_path, ".claude/settings.json", _claude_hook_settings("bash ~/bin/my-linter.sh"))
    _plant(
        tmp_path,
        ".gemini/antigravity/settings.json",
        json.dumps({"env": {"X": "gsd-check-update.js"}, "hooks": {}}),
    )
    _plant(
        tmp_path,
        ".cursor/hooks.json",
        json.dumps({"hooks": {"stop": [{"command": "./mine.sh", "gsd-managed": False}]}}),
    )
    _plant(tmp_path, ".kimi-code/config.toml", "# GSD Hooks notes\nmodel = 'x'\n")

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report == ProjectPackReport()


def _malformed(home: Path) -> str:
    _write_bytes(home, ".claude/settings.json", b'{"hooks": ')
    return ".claude/settings.json"


def _non_utf8(home: Path) -> str:
    _write_bytes(home, ".claude/settings.json", b'{"hooks": "\xff\xfe gsd-x.js"}')
    return ".claude/settings.json"


def _deep_nesting(home: Path) -> str:
    _write_bytes(home, ".claude/settings.json", b"[" * 60000)
    return ".claude/settings.json"


def _array_settings(home: Path) -> str:
    document = [json.loads(_claude_hook_settings("node gsd-check-update.js"))]
    _write_bytes(home, ".claude/settings.json", json.dumps(document).encode())
    return ".claude/settings.json"


def _array_hooks_json(home: Path) -> str:
    _write_bytes(home, ".cursor/hooks.json", b'[{"gsd-managed": true}]')
    return ".cursor/hooks.json"


def _directory_config(home: Path) -> str:
    (home / ".claude" / "settings.json").mkdir(parents=True)
    return ".claude/settings.json"


def _dangling_symlink(home: Path) -> str:
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").symlink_to(home / "dotfiles" / "settings.json")
    return ""


@pytest.mark.parametrize(
    "make_config",
    [
        _malformed,
        _non_utf8,
        _deep_nesting,
        _array_settings,
        _array_hooks_json,
        _directory_config,
        _dangling_symlink,
    ],
    ids=lambda make_config: make_config.__name__.lstrip("_"),
)
def test_hook_config_fails_closed(tmp_path: Path, make_config: Callable[[Path], str]) -> None:
    unchecked = make_config(tmp_path)
    _plant(tmp_path, ".codex/hooks.json", json.dumps({"hooks": {"x": [{"command": "gsd-a.sh"}]}}))

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == ("codex",)
    assert report.steps == (_uninstall_step("codex"),)
    assert report.unchecked == ((unchecked,) if unchecked else ())


def test_hook_walk_bound_is_inconclusive(tmp_path: Path) -> None:
    flat = {"hooks": [{"command": "x"} for _ in range(20000)]}
    _plant(tmp_path, ".codex/hooks.json", json.dumps(flat))

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report == ProjectPackReport(unchecked=(".codex/hooks.json",))


def test_unlistable_machinery_dir_is_unchecked_not_a_leftover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / ".claude" / "skills"
    real_scandir = skill_lifecycle.os.scandir
    tool = _tools()["opengsd"]

    assert inspect_project_pack(tool, tmp_path, frozenset()).unchecked == ()

    _plant(tmp_path, ".claude/skills/gsd-x")

    def scandir(path: Path) -> object:
        if Path(path) == blocked:
            raise PermissionError(13, "Permission denied", str(path))
        return real_scandir(path)

    monkeypatch.setattr(skill_lifecycle.os, "scandir", scandir)
    report = inspect_project_pack(tool, tmp_path, frozenset())

    assert report.leftovers == ()
    assert report.unchecked == (".claude/skills",)


def test_unreadable_gsd_core_is_unchecked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = tmp_path / ".claude" / "gsd-core"
    real_stat = Path.stat

    def stat(self: Path, *, follow_symlinks: bool = True) -> object:
        if self == blocked:
            raise PermissionError(13, "Permission denied", str(self))
        return real_stat(self, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", stat)
    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report == ProjectPackReport(unchecked=(".claude/gsd-core",))


def test_oversized_hook_config_is_never_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    _plant(tmp_path, ".claude/settings.json", _claude_hook_settings(_GSD_HOOK_COMMAND))
    with settings.open("a", encoding="utf-8") as fh:
        fh.write(" " * (257 * 1024))
    real_open = Path.open

    def guarded_open(
        self: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> IO[Any]:
        if self == settings:
            raise AssertionError("the oversized hook config was opened")
        return real_open(self, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", guarded_open)
    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == ()
    assert report.unchecked == (".claude/settings.json",)


def test_oversized_hook_config_bound_is_the_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    _plant(tmp_path, ".claude/settings.json", _claude_hook_settings(_GSD_HOOK_COMMAND))
    with settings.open("a", encoding="utf-8") as fh:
        fh.write(" " * (300 * 1024))
    reads: list[int] = []
    real_read = os.read

    def counting_read(fd: int, size: int) -> bytes:
        reads.append(size)
        return real_read(fd, size)

    monkeypatch.setattr(atomic.os, "read", counting_read)
    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == ()
    assert report.unchecked == (".claude/settings.json",)
    assert reads == [256 * 1024 + 1]


def test_harnesses_without_hook_config_read_nothing(tmp_path: Path) -> None:
    for home_dir in (".copilot", ".config/kilo", ".config/opencode"):
        _plant(tmp_path, f"{home_dir}/settings.json", _claude_hook_settings(_GSD_HOOK_COMMAND))
        _plant(tmp_path, f"{home_dir}/hooks.json", json.dumps({"x": {"gsd-managed": True}}))

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report == ProjectPackReport()
    assert not {"copilot", "kilo", "opencode"} & set(PROJECT_HOOK_CONFIGS)


def test_hook_scan_writes_nothing(tmp_path: Path) -> None:
    configs = {
        ".claude/settings.json": _claude_hook_settings(_GSD_HOOK_COMMAND),
        ".gemini/antigravity/settings.json": _claude_hook_settings(_GSD_HOOK_COMMAND),
        ".codex/hooks.json": json.dumps({"hooks": {"x": [{"command": "gsd-a.sh"}]}}),
        ".codex/config.toml": "# GSD Hooks\n",
        ".cursor/hooks.json": json.dumps({"hooks": {"x": [{"gsd-managed": True}]}}),
        ".codeium/windsurf/hooks.json": json.dumps({"hooks": {"x": [{"gsd-managed": True}]}}),
        ".kimi-code/config.toml": "# GSD Hooks BEGIN — managed by GSD\n# GSD Hooks END\n",
    }
    for relative, content in configs.items():
        _plant(tmp_path, relative, content)
    before = _home_fingerprint(tmp_path)

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.leftovers == ("antigravity", "claude", "codex", "cursor", "kimi", "windsurf")
    assert _home_fingerprint(tmp_path) == before


def _repo(home: Path, relative: str) -> Path:
    _plant(home, f"{relative}/.planning/config.json", "{}")
    return home / relative


def _gsd_install(repo: Path, runtime_dir: str) -> None:
    _plant(repo, f"{runtime_dir}/gsd-core/VERSION", "1.16.0\n")
    _plant(repo, f"{runtime_dir}/commands/gsd-plan-phase.md")


def _empty_install(repo: Path, runtime_dir: str = ".opencode") -> None:
    """The 2026-10-14 case: install state and VERSION present, every content dir empty."""
    _plant(repo, f"{runtime_dir}/gsd-install-state.json", "{}")
    _plant(repo, f"{runtime_dir}/gsd-core/VERSION", "1.16.0\n")
    for sub in ("skills", "commands", "agents"):
        _plant(repo, f"{runtime_dir}/{sub}")


def _repos(home: Path) -> dict[Path, tuple[str, ...]]:
    return dict(inspect_project_pack(_tools()["opengsd"], home, frozenset()).repos)


def _count_scandir(monkeypatch: pytest.MonkeyPatch) -> tuple[list[Path], list[Path]]:
    """Record every `os.scandir` call and every entry it yields."""
    calls: list[Path] = []
    yielded: list[Path] = []
    real_scandir = os.scandir

    @contextlib.contextmanager
    def counting(path: Path) -> Generator[Iterator[os.DirEntry[str]]]:
        calls.append(Path(path))
        with real_scandir(path) as entries:

            def counted() -> Iterator[os.DirEntry[str]]:
                for entry in entries:
                    yielded.append(Path(entry.path))
                    yield entry

            yield counted()

    monkeypatch.setattr(skill_lifecycle.os, "scandir", counting)
    return calls, yielded


def _record_deque(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Install a walk queue that records its length after every admission."""
    lengths: list[int] = []

    class RecordingDeque(deque[object]):
        def append(self, x: object, /) -> None:
            super().append(x)
            lengths.append(len(self))

    monkeypatch.setattr(skill_lifecycle, "deque", RecordingDeque)
    return lengths


def _under(paths: list[Path], root: Path) -> list[Path]:
    return [path for path in paths if path.is_relative_to(root)]


def test_repo_walk_finds_planning_configs(tmp_path: Path) -> None:
    a = _repo(tmp_path, "git/a")
    b = _repo(tmp_path, "src/org/b")
    depth_four = _repo(tmp_path, "code/1/2/3/d4")
    _repo(tmp_path, "code/1/2/3/4/d5")
    _repo(tmp_path, "git/a/nested")  # a repo is not descended
    _repo(tmp_path, "elsewhere/c")  # not a configured root

    assert _repos(tmp_path) == {a: (), b: (), depth_four: ()}


def test_repo_walk_skips_hidden_node_modules_and_venv(tmp_path: Path) -> None:
    for relative in ("git/.cache/x", "git/a/node_modules/y", "git/a/.venv/z", "dev/.hidden"):
        _repo(tmp_path, relative)

    assert _repos(tmp_path) == {}


def test_repo_walk_is_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "code"
    for index in range(6000):
        (root / f"d{index}").mkdir(parents=True)
    lengths = _record_deque(monkeypatch)
    calls, _ = _count_scandir(monkeypatch)

    assert _repos(tmp_path) == {}
    assert len(lengths) == 5000
    assert len(_under(calls, root)) <= 5000


def test_repo_walk_bounds_queue_and_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(skill_lifecycle, "_MAX_WALK_DIRS", 50)
    root = tmp_path / "home" / "code"
    for index in range(200):
        (root / f"d{index}").mkdir(parents=True)
    lengths = _record_deque(monkeypatch)
    calls, yielded = _count_scandir(monkeypatch)

    assert _repos(tmp_path / "home") == {}
    assert 0 < len(lengths) <= 50
    assert max(lengths) <= 50
    assert 0 < len(_under(calls, root)) <= 50

    monkeypatch.setattr(skill_lifecycle, "_MAX_WALK_ENTRIES", 100)
    files = tmp_path / "files" / "git"
    files.mkdir(parents=True)
    for index in range(500):
        (files / f"f{index}.txt").write_text("x")

    assert _repos(tmp_path / "files") == {}
    assert 0 < len(_under(yielded, files)) <= 100


def test_repo_walk_rejects_a_symlinked_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    _repo(outside, "a")
    home.mkdir()
    (home / "git").symlink_to(outside, target_is_directory=True)
    calls, _ = _count_scandir(monkeypatch)

    assert _repos(home) == {}
    assert _under(calls, home / "git") == []
    assert _under(calls, outside) == []


def test_repo_walk_never_follows_symlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    _repo(outside, "x")
    _plant(outside, ".planning/config.json", "{}")
    real = _repo(home, "git/real")
    (home / "git" / "link").symlink_to(outside, target_is_directory=True)
    calls, _ = _count_scandir(monkeypatch)

    assert _repos(home) == {real: ()}
    assert _under(calls, home / "git" / "link") == []
    assert _under(calls, outside) == []


def test_repo_walk_rejects_a_symlinked_planning_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    _plant(outside, ".planning/config.json", "{}")
    linked = home / "git" / "a"
    linked.mkdir(parents=True)
    (linked / ".planning").symlink_to(outside / ".planning", target_is_directory=True)
    sibling = _repo(home, "git/b")

    assert _repos(home) == {sibling: ()}


def test_real_install_counts(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _gsd_install(repo, ".claude")

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.repos == ((repo, ("claude",)),)


def test_empty_dirs_install_is_not_installed(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _empty_install(repo)

    report = inspect_project_pack(_tools()["opengsd"], tmp_path, frozenset())

    assert report.repos == ((repo, ()),)


def test_stale_version_beside_unrelated_skills_is_not_installed(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _plant(repo, ".claude/gsd-core/VERSION", "1.16.0\n")
    _plant(repo, ".claude/skills/tool-onboarding")
    _plant(repo, ".claude/skills/superpowers")

    assert _repos(tmp_path) == {repo: ()}

    _plant(repo, ".claude/commands/gsd-plan-phase.md")

    assert _repos(tmp_path) == {repo: ("claude",)}


def test_two_runtimes_in_one_repo(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _gsd_install(repo, ".opencode")
    _gsd_install(repo, ".claude")

    assert _repos(tmp_path) == {repo: ("claude", "opencode")}


def test_repo_walk_writes_nothing(tmp_path: Path) -> None:
    _gsd_install(_repo(tmp_path, "git/a"), ".claude")
    _empty_install(_repo(tmp_path, "src/b"))
    _repo(tmp_path, "work/c")
    before = _home_fingerprint(tmp_path)

    assert len(_repos(tmp_path)) == 3
    assert _home_fingerprint(tmp_path) == before


def _install_step(runtime: str, repo: Path, verb: str = "install") -> ConfigStep:
    return ConfigStep(
        text=f"{verb} opengsd for {SKILL_HARNESS_LABELS[runtime]} in {repo.name}",
        kind="project_pack_install",
        harness=runtime,
        argv=(
            "pnpm",
            "dlx",
            "@opengsd/gsd-core@1.16.0",
            f"--{runtime}",
            "--local",
            "--relative-includes",
        ),
        cwd=repo,
    )


def _gsd_pack(home: Path, present: set[str]) -> ProjectPackReport:
    return inspect_project_pack(_tools()["opengsd"], home, frozenset(present))


def test_repo_without_any_install_gets_install_steps(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")

    report = _gsd_pack(tmp_path, {"claude", "opencode"})

    assert report.repos == ((repo, ()),)
    assert report.reasons == ("not installed in app",)
    assert report.steps == (_install_step("claude", repo), _install_step("opencode", repo))
    assert report.steps[0].text == "install opengsd for Claude Code in app"


def test_empty_install_gets_a_reinstall_step(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _empty_install(repo)

    report = _gsd_pack(tmp_path, {"claude", "opencode"})

    assert report.reasons == ("OpenCode install in app is empty",)
    assert report.steps == (_install_step("opencode", repo, "reinstall"),)


def _block_scandir(monkeypatch: pytest.MonkeyPatch, blocked: set[Path]) -> None:
    """Raise PermissionError for exactly the blocked dirs; delegate otherwise."""
    real_scandir = os.scandir

    def guarded(path: Path) -> Iterator[os.DirEntry[str]]:
        if Path(path) in blocked:
            raise PermissionError(path)
        return real_scandir(path)

    monkeypatch.setattr(skill_lifecycle.os, "scandir", guarded)


def test_unreadable_install_dirs_are_not_checked_not_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, "code/proj")
    _plant(repo, ".claude/gsd-core/VERSION", "1.16.0\n")
    skills, commands = repo / ".claude/skills", repo / ".claude/commands"
    skills.mkdir()
    commands.mkdir()
    _block_scandir(monkeypatch, {skills, commands})

    report = _gsd_pack(tmp_path, {"claude", "opencode"})

    assert report.repos == ((repo, ()),)
    assert not any("is empty" in reason for reason in report.reasons)
    assert "not installed in proj" not in report.reasons
    assert not any(step.kind == "project_pack_install" for step in report.steps)
    assert "code/proj/.claude/skills" in report.unchecked
    assert "code/proj/.claude/commands" in report.unchecked


def test_conclusive_empty_install_keeps_its_reinstall_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, "code/proj")
    _plant(repo, ".claude/gsd-core/VERSION", "1.16.0\n")
    (repo / ".claude/skills").mkdir()
    (repo / ".claude/commands").mkdir()
    _block_scandir(monkeypatch, set())

    report = _gsd_pack(tmp_path, {"claude", "opencode"})

    assert "Claude Code install in proj is empty" in report.reasons
    assert [step for step in report.steps if step.kind == "project_pack_install"] == [
        _install_step("claude", repo, "reinstall")
    ]


def test_absent_runtime_gets_no_step(tmp_path: Path) -> None:
    bare = _repo(tmp_path, "git/a")
    _empty_install(_repo(tmp_path, "git/b"))

    report = _gsd_pack(tmp_path, {"claude"})

    assert report.reasons == ("not installed in a", "OpenCode install in b is empty")
    assert report.steps == (_install_step("claude", bare),)


def test_repo_with_one_real_runtime_gets_no_step_for_others(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _gsd_install(repo, ".claude")

    report = _gsd_pack(tmp_path, {"claude", "opencode"})

    assert report.repos == ((repo, ("claude",)),)
    assert (report.reasons, report.steps) == ((), ())


def test_empty_dirs_opencode_beside_real_claude_gets_the_reinstall_step(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "git/app")
    _gsd_install(repo, ".claude")
    _empty_install(repo)

    report = _gsd_pack(tmp_path, {"claude", "opencode"})

    assert report.repos == ((repo, ("claude",)),)
    assert report.reasons == ("OpenCode install in app is empty",)
    assert report.steps == (_install_step("opencode", repo, "reinstall"),)
    assert "--opencode" in report.steps[0].argv


def test_install_step_cwd_is_validated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo(tmp_path, "git/rel")
    monkeypatch.chdir(tmp_path)

    relative = inspect_project_pack(_tools()["opengsd"], Path(), frozenset({"claude"}))

    assert relative.reasons == ("not installed in rel",)
    assert relative.steps == ()

    def vanish(found: Path) -> tuple[str, ...]:
        shutil.rmtree(found)
        return ()

    monkeypatch.setattr(skill_lifecycle, "_installed_runtimes", vanish)
    report = _gsd_pack(tmp_path, {"claude"})

    assert report.reasons == ("not installed in rel",)
    assert report.steps == ()


def test_no_step_installs_globally(tmp_path: Path) -> None:
    _repo(tmp_path, "git/a")
    _empty_install(_repo(tmp_path, "git/b"))
    both = _repo(tmp_path, "git/c")
    _gsd_install(both, ".claude")
    _empty_install(both)
    _gsd_install(_repo(tmp_path, "src/d"), ".claude")
    _plant(tmp_path, ".claude/commands/gsd-plan.md")  # a global leftover beside them

    report = _gsd_pack(tmp_path, {"claude", "opencode"})
    installs = [step for step in report.steps if step.kind == "project_pack_install"]

    assert len(installs) == 4
    assert [step.kind for step in report.steps].count("project_pack_global_uninstall") == 1
    for step in installs:
        assert "--global" not in step.argv
        assert step.cwd is not None and step.cwd.is_absolute()
        assert step.cwd in dict(report.repos)


def _bounded_report(call: Callable[[], object]) -> tuple[threading.Thread, list[object]]:
    """Run a probe on a daemon thread; five seconds is the stall budget.

    A FIFO at a config used to block the skill worker while it held the
    skill-pass lock. The caller releases any reader left blocked.
    """
    box: list[object] = []

    def run() -> None:
        box.append(call())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=5)
    return thread, box


def _release_fifo(fifo: Path, thread: threading.Thread) -> None:
    with contextlib.suppress(OSError):
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
    thread.join(timeout=5)


def test_installed_plugins_fifo_never_blocks(tmp_path: Path) -> None:
    plugins = tmp_path / ".claude" / "plugins"
    plugins.mkdir(parents=True)
    fifo = plugins / "installed_plugins.json"
    os.mkfifo(fifo)
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", True, "6.4.1"), (_SUPERPOWERS_ID, "project", True, "6.2.0")
    )
    thread = threading.Thread()
    try:
        thread, box = _bounded_report(lambda: _superpowers_report(tmp_path, listing))
        assert not thread.is_alive()
        report = box[0]
        assert isinstance(report, SkillPackReport)
        assert report.reasons == (
            "duplicate: superpowers@claude-plugins-official in project scope (6.2.0)",
        )
        assert report.steps == ()
    finally:
        _release_fifo(fifo, thread)


def test_hook_config_fifo_is_not_checked(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    fifo = claude / "settings.json"
    os.mkfifo(fifo)
    thread = threading.Thread()
    try:
        thread, box = _bounded_report(lambda: _gsd_pack(tmp_path, set()))
        assert not thread.is_alive()
        report = box[0]
        assert isinstance(report, ProjectPackReport)
        assert ".claude/settings.json" in report.unchecked
    finally:
        _release_fifo(fifo, thread)


def test_capped_config_reads_use_read_capped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both configs are read through the shared helper, following a symlink."""
    _installed_plugins(tmp_path, [(_SUPERPOWERS_ID, "project", str(tmp_path))])
    _plant(tmp_path, ".claude/settings.json", "{}")
    seen: list[tuple[Path, bool]] = []
    real = skill_lifecycle.read_capped

    def recording(path: Path, cap: int, *, follow_symlinks: bool) -> bytes | None:
        seen.append((path, follow_symlinks))
        return real(path, cap, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(skill_lifecycle, "read_capped", recording)
    listing = _claude_json(
        (_SUPERPOWERS_ID, "user", True, "6.4.1"), (_SUPERPOWERS_ID, "project", True, "6.2.0")
    )
    _superpowers_report(tmp_path, listing)
    _gsd_pack(tmp_path, set())

    followed = {path: follow for path, follow in seen}
    assert followed[tmp_path / ".claude" / "plugins" / "installed_plugins.json"] is True
    assert followed[tmp_path / ".claude" / "settings.json"] is True
