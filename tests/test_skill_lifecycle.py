import json
import subprocess
from pathlib import Path
from typing import Literal

import pytest

import installer.engine as engine
from installer.engine import install_tool
from installer.model import (
    SKILL_HARNESSES,
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
    SKILL_HARNESS_LABELS,
    _install_state_status,  # pyright: ignore[reportPrivateUsage]
    inspect_skill_packs,
    inspect_status,
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
    assert outcome.instructions[2:6] == (
        "/plugin install superpowers@claude-plugins-official",
        "or, instead, from the obra marketplace:",
        "/plugin marketplace add obra/superpowers-marketplace",
        "/plugin install superpowers@superpowers-marketplace",
    )
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
    assert SkillStatusProbe("claude", "plugin-cli", "superpowers") in superpowers.status_probes
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

    result = inspect_skill_packs([superpowers, ponytail], probe, tmp_path)

    assert result["superpowers"]["pi"] == "present"
    assert result["ponytail"]["codex"] == "present"


def test_codex_not_installed_row_is_absent(tmp_path: Path) -> None:
    tool = _pack("superpowers", (SkillStatusProbe("codex", "plugin-cli", "superpowers"),))

    def probe(argv: list[str]) -> str:
        assert argv == ["codex", "plugin", "list"]
        return "superpowers@openai-curated  not installed\n"

    assert inspect_skill_packs([tool], probe, tmp_path) == {"superpowers": {"codex": "absent"}}


def test_codex_probe_failure_is_unknown_for_every_pack(tmp_path: Path) -> None:
    packs = [
        _pack("ponytail", (SkillStatusProbe("codex", "plugin-cli", "ponytail"),)),
        _pack("other", (SkillStatusProbe("codex", "plugin-cli", "other"),)),
    ]

    def probe(_argv: list[str]) -> str:
        raise RuntimeError("codex down")

    assert inspect_skill_packs(packs, probe, tmp_path) == {
        "ponytail": {"codex": "unknown"},
        "other": {"codex": "unknown"},
    }


def test_plugin_cli_without_closed_row_is_unknown_and_unprobed(tmp_path: Path) -> None:
    tool = _pack("demo", (SkillStatusProbe("opencode", "plugin-cli", "x"),))
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "x"

    assert inspect_skill_packs([tool], probe, tmp_path) == {"demo": {"opencode": "unknown"}}
    assert calls == []


def test_claude_plugin_list_marker_row_is_present(tmp_path: Path) -> None:
    tool = _pack("superpowers", (SkillStatusProbe("claude", "plugin-cli", "superpowers"),))

    def probe(argv: list[str]) -> str:
        assert argv == ["claude", "plugin", "list"]
        return "❯ superpowers@claude-plugins-official\n"

    assert inspect_skill_packs([tool], probe, tmp_path)["superpowers"]["claude"] == "present"


def test_claude_match_stops_at_name_boundary(tmp_path: Path) -> None:
    tool = _pack("superpowers", (SkillStatusProbe("claude", "plugin-cli", "superpowers"),))

    def probe(_argv: list[str]) -> str:
        return "❯ superpowers-lab@x\n"

    assert inspect_skill_packs([tool], probe, tmp_path)["superpowers"]["claude"] == "absent"


def test_empty_cli_output_is_absent(tmp_path: Path) -> None:
    tool = _pack("ponytail", (SkillStatusProbe("codex", "plugin-cli", "ponytail"),))

    assert inspect_skill_packs([tool], lambda _argv: "", tmp_path)["ponytail"]["codex"] == "absent"


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

    result = inspect_skill_packs([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "present"


def test_skills_lock_absent_when_skill_dir_missing(tmp_path: Path) -> None:
    _write_lock(
        tmp_path,
        {"skills": {"c4-architecture": {"source": "softaworks/agent-toolkit"}}},
    )

    result = inspect_skill_packs([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "absent"


def test_skills_lock_absent_when_lock_file_missing(tmp_path: Path) -> None:
    result = inspect_skill_packs([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "absent"


@pytest.mark.parametrize("payload", ("{", '{"skills": ["nope"]}'))
def test_skills_lock_malformed_or_wrong_shape_is_unknown(tmp_path: Path, payload: str) -> None:
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / ".skill-lock.json").write_text(payload, encoding="utf-8")

    result = inspect_skill_packs([_lock_pack()], lambda _argv: "", tmp_path)

    assert result["softaworks"]["claude"] == "unknown"


def test_skills_lock_ignores_traversal_skill_names(tmp_path: Path) -> None:
    _write_lock(tmp_path, {"skills": {"../evil": {"source": "softaworks/agent-toolkit"}}})
    decoy = tmp_path / ".claude" / "evil"
    decoy.parent.mkdir(parents=True)
    decoy.write_text("decoy", encoding="utf-8")

    result = inspect_skill_packs([_lock_pack()], lambda _argv: "", tmp_path)

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

    result = inspect_skill_packs([tool], lambda _argv: "", tmp_path)

    assert result["softaworks"]["muse"] == "unknown"


def test_install_state_file_is_present_and_missing_is_absent(tmp_path: Path) -> None:
    tool = _pack("opengsd", (SkillStatusProbe("claude", "install-state", "gsd-core"),))
    absent = inspect_skill_packs([tool], lambda _argv: "", tmp_path)
    state = tmp_path / ".claude" / "gsd-install-state.json"
    state.parent.mkdir()
    state.write_text("{}", encoding="utf-8")
    present = inspect_skill_packs([tool], lambda _argv: "", tmp_path)

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

    result = inspect_skill_packs([tool], lambda _argv: "", tmp_path)

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

    inspect_skill_packs(packs, lambda _argv: "", tmp_path)

    assert reads == 1


def test_one_cli_call_per_harness_across_packs(tmp_path: Path) -> None:
    packs = [
        _pack(f"pack-{index}", (SkillStatusProbe("claude", "plugin-cli", "superpowers"),))
        for index in range(3)
    ]
    calls: list[list[str]] = []

    def probe(argv: list[str]) -> str:
        calls.append(argv)
        return "❯ superpowers@claude-plugins-official\n"

    inspect_skill_packs(packs, probe, tmp_path)

    assert calls == [["claude", "plugin", "list"]]


def test_host_order_follows_skill_harnesses_not_declaration_order(tmp_path: Path) -> None:
    tool = _pack(
        "demo",
        (
            SkillStatusProbe("pi", "plugin-cli", "obra/superpowers"),
            SkillStatusProbe("claude", "plugin-cli", "superpowers"),
            SkillStatusProbe("codex", "plugin-cli", "ponytail"),
        ),
    )

    result = inspect_skill_packs([tool], lambda _argv: "", tmp_path)["demo"]

    assert list(result) == [harness for harness in SKILL_HARNESSES if harness in result]
    assert list(result) == ["claude", "codex", "pi"]


def test_empty_status_probes_map_to_empty_dict(tmp_path: Path) -> None:
    tool = _pack("demo", ())

    assert inspect_skill_packs([tool], lambda _argv: "nope", tmp_path) == {"demo": {}}


def test_inspect_skill_packs_is_idempotent(tmp_path: Path) -> None:
    tool = _pack("demo", (SkillStatusProbe("pi", "plugin-cli", "obra/superpowers"),))

    def probe(_argv: list[str]) -> str:
        return "obra/superpowers\n"

    assert inspect_skill_packs([tool], probe, tmp_path) == inspect_skill_packs(
        [tool], probe, tmp_path
    )


def test_skill_harness_labels_cover_every_harness() -> None:
    assert set(SKILL_HARNESS_LABELS) == set(SKILL_HARNESSES)
    assert all(label.isascii() and label for label in SKILL_HARNESS_LABELS.values())
    assert SKILL_HARNESS_LABELS["claude"] == "Claude Code"
    assert SKILL_HARNESS_LABELS["codex"] == "Codex"
    assert SKILL_HARNESS_LABELS["pi"] == "Pi"
    assert SKILL_HARNESS_LABELS["gemini-cli"] == "Gemini CLI"
    assert SKILL_HARNESS_LABELS["factory-droid"] == "Factory Droid"
