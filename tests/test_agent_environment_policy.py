"""Tests for installer.policy's AgentEnvironmentPolicy composition (ported from local's line)."""

from pathlib import Path

from installer import policy as policy_module
from installer.agent_env import AgentAdapter, adapters
from installer.agent_policy import AgentAudit, apply_agent_permissions, audit_agent_policy
from installer.policy import PolicyLayer, PolicyResult


def _ok_policy_result() -> PolicyResult:
    return PolicyResult(
        layers=(PolicyLayer("Permissions", "configured"),),
        reload_hint=None,
        warning=None,
    )


def test_agent_environment_policy_only_binds_fixable_action(tmp_path: Path) -> None:
    adapter = AgentAdapter(
        id="opencode",
        label="OpenCode",
        config_path=tmp_path / ".config" / "opencode" / "opencode.json",
        instruction_path=tmp_path / ".config" / "opencode" / "AGENTS.md",
        permission_mode="configurable",
    )
    calls: list[tuple[AgentAdapter, Path]] = []
    audits: list[tuple[AgentAdapter, Path]] = []

    def apply_agent(adapter: AgentAdapter, home: Path) -> PolicyResult:
        calls.append((adapter, home))
        return PolicyResult(
            layers=(PolicyLayer("Permissions", "configured"),),
            reload_hint=None,
            warning=None,
        )

    def audit_agent(adapter: AgentAdapter, home: Path) -> AgentAudit:
        audits.append((adapter, home))
        return AgentAudit(adapter, "healthy", "read-only policy configured")

    fixable = policy_module.agent_environment_policy(
        AgentAudit(adapter, "fixable", "read-only policy can be applied"),
        home=tmp_path,
        audit_agent=audit_agent,
        apply_agent=apply_agent,
    )
    manual = policy_module.agent_environment_policy(
        AgentAudit(adapter, "manual-required", "manual setup required"),
        home=tmp_path,
        audit_agent=audit_agent,
        apply_agent=apply_agent,
    )

    assert fixable.apply is not None
    assert fixable.refresh is not None
    assert manual.apply is None
    fixable.apply()
    refreshed = fixable.refresh()
    assert calls == [(adapter, tmp_path)]
    assert audits == [(adapter, tmp_path)]
    assert refreshed.state == "healthy"


def test_manual_agent_binds_only_pending_guidance_action(tmp_path: Path) -> None:
    adapter = adapters(tmp_path)["claude"]
    permission_calls: list[str] = []
    guidance_calls: list[str] = []

    def apply_permissions(_adapter: AgentAdapter, _home: Path) -> PolicyResult:
        permission_calls.append("permissions")
        return _ok_policy_result()

    def apply_guidance(_adapter: AgentAdapter, _home: Path) -> PolicyResult:
        guidance_calls.append("guidance")
        return PolicyResult(
            layers=(PolicyLayer("Guidance", "managed reference"),),
            reload_hint=None,
            warning=None,
        )

    policy = policy_module.agent_environment_policy(
        AgentAudit(
            adapter,
            "manual-required",
            "audit only; persistent permission format unknown",
            guidance_pending=True,
        ),
        home=tmp_path,
        audit_agent=lambda _adapter, _home: AgentAudit(
            adapter,
            "manual-required",
            "audit only; persistent permission format unknown",
        ),
        apply_agent=apply_permissions,
        apply_guidance=apply_guidance,
    )

    assert policy.apply is not None
    result = policy.apply()

    assert guidance_calls == ["guidance"]
    assert permission_calls == []
    assert [layer.name for layer in result.layers] == ["Guidance"]


def test_supported_guidance_only_repair_skips_permission_action(tmp_path: Path) -> None:
    adapter = adapters(tmp_path)["opencode"]
    apply_agent_permissions(adapter, tmp_path)
    audit = audit_agent_policy(adapter, tmp_path)
    permission_calls: list[str] = []
    guidance_calls: list[str] = []

    def apply_permissions(_adapter: AgentAdapter, _home: Path) -> PolicyResult:
        permission_calls.append("permissions")
        return _ok_policy_result()

    def apply_guidance(_adapter: AgentAdapter, _home: Path) -> PolicyResult:
        guidance_calls.append("guidance")
        return PolicyResult(
            layers=(PolicyLayer("Guidance", "managed reference"),),
            reload_hint=None,
            warning=None,
        )

    assert audit.state == "fixable"
    assert audit.guidance_pending is True
    policy = policy_module.agent_environment_policy(
        audit,
        home=tmp_path,
        audit_agent=audit_agent_policy,
        apply_agent=apply_permissions,
        apply_guidance=apply_guidance,
    )

    assert policy.apply is not None
    policy.apply()

    assert guidance_calls == ["guidance"]
    assert permission_calls == []


def test_agent_environment_policy_isolates_audit_failure(tmp_path: Path) -> None:
    adapter = AgentAdapter(
        id="opencode",
        label="OpenCode",
        config_path=tmp_path.parent / "outside.json",
        instruction_path=None,
        permission_mode="configurable",
    )

    def audit_agent(_adapter: AgentAdapter, _home: Path) -> AgentAudit:
        raise ValueError("OpenCode adapter path is outside injected home")

    policy = policy_module.compose_agent_environment_policy(
        adapter,
        home=tmp_path,
        audit_agent=audit_agent,
        apply_agent=lambda _adapter, _home: _ok_policy_result(),
    )

    assert policy.state == "manual-required"
    assert "outside injected home" in policy.detail
    assert policy.apply is None


def test_agent_environment_policy_refresh_isolates_symlink_loop(tmp_path: Path) -> None:
    opencode = adapters(tmp_path)["opencode"]
    loop = tmp_path / ".config" / "opencode"
    loop.parent.mkdir(parents=True)
    loop.symlink_to(loop)
    policy = policy_module.agent_environment_policy(
        AgentAudit(opencode, "fixable", "read-only policy can be applied"),
        home=tmp_path,
        audit_agent=audit_agent_policy,
        apply_agent=lambda _adapter, _home: _ok_policy_result(),
    )

    assert policy.refresh is not None
    refreshed = policy.refresh()

    assert refreshed.state == "manual-required"
    # "symbolic link", not the more specific "symlink loop": the message is
    # now the kernel's own ELOOP strerror text (portable across platforms),
    # not pathlib's Python-level phrasing, which was itself inconsistent
    # across CPython versions -- see _resolved()'s docstring in agent_policy.py.
    assert "symbolic link" in refreshed.detail.lower()
    assert refreshed.apply is None
