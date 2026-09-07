# Agent Toolkits and Permission Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add researched, target-aware toolkit lifecycle adapters and reversible safe-auto/external-sandbox permission profiles.

**Architecture:** Research records establish authoritative toolkit capabilities before code. Named adapters turn verified official commands and status evidence into lifecycle operations. Permission profiles are marker-delimited launch aliases or config blocks, separate from read-only agent-environment policies.

**Tech Stack:** Python 3.12, TOML registry, JSON/TOML configuration, pytest.

## Global Constraints

- Research every current toolkit before adding an automatic adapter.
- Supported target matrix: Claude, Codex, OpenCode, Pi, Antigravity.
- Unsupported targets must remain visible as unsupported or manual-required.
- External-sandbox profiles must never be selected by default.

---

### Task 1: Produce and validate the upstream toolkit research matrix

**Files:**
- Create: `docs/research/agent-toolkit-install-matrix.md`
- Modify: `installer/registry.toml`, `installer/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Produces one record per Ponytail, OpenSpec, Superpowers, Softaworks, Matt Pocock Skills, OpenGSD, and Spec Kit with source URL, revision checked, install/status/update/remove evidence, and five-target support.

- [ ] **Step 1: Write the failing test**

```python
def test_every_skill_pack_declares_target_capability_matrix() -> None:
    expected = {"claude", "codex", "opencode", "pi", "antigravity"}
    for tool in _skill_packs():
        assert set(tool.skill_lifecycle.target_capabilities) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model.py -k target_capability_matrix -v`

Expected: FAIL because lifecycle records list only claimed supported harnesses.

- [ ] **Step 3: Write minimal implementation**

Use primary upstream documentation only. For each target set one of `automatic`, `manual-required`, or `unsupported`, and cite the evidence in the research matrix. Do not infer support from a generic Agent Skills format claim.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/research/agent-toolkit-install-matrix.md installer/registry.toml installer/model.py tests/test_model.py
git commit -m "docs: record verified agent toolkit target support"
```

### Task 2: Implement selected-target lifecycle results and detection

**Files:**
- Create: `installer/toolkit_lifecycle.py`
- Modify: `installer/skill_lifecycle.py`, `installer/status.py`, `installer/catalog_tui.py`
- Test: `tests/test_toolkit_lifecycle.py`, `tests/test_status.py`, `tests/test_catalog_tui.py`

**Interfaces:**
- Produces `TargetResult(target, state, paths, detail)` and `ToolkitStatus(selected: tuple[TargetResult, ...])`.
- Consumes a named lifecycle adapter and temporary-home target paths.

- [ ] **Step 1: Write the failing test**

```python
def test_softaworks_reports_codex_present_and_pi_unsupported(tmp_path: Path) -> None:
    status = inspect_toolkit(_softaworks(), home=tmp_path, runner=_skills_list_json)
    assert status.for_target("codex").state == "present"
    assert status.for_target("pi").state == "unsupported"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_toolkit_lifecycle.py -v`

Expected: FAIL because skill packs have only one manual/unknown status.

- [ ] **Step 3: Write minimal implementation**

Implement a Skills CLI JSON-list adapter for researched Skills-CLI targets, a Pi package-status adapter for Superpowers, and host-plugin adapters only where research documents a stable read-only query. Return manual-required rather than invoking a networked CLI merely to inspect status.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_toolkit_lifecycle.py tests/test_status.py tests/test_catalog_tui.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/toolkit_lifecycle.py installer/skill_lifecycle.py installer/status.py installer/catalog_tui.py tests/test_toolkit_lifecycle.py tests/test_status.py tests/test_catalog_tui.py
git commit -m "feat(toolkits): report per-target lifecycle state"
```

### Task 3: Add reversible permission launch profiles

**Files:**
- Create: `installer/agent_profiles.py`
- Modify: `installer/policy.py`, `installer/wizard_app.py`, `installer/tweaks.py`
- Test: `tests/test_agent_profiles.py`, `tests/test_policies_e2e.py`

**Interfaces:**
- Produces `AgentLaunchProfile(id, label, safety_level, command, apply, remove, active)`.
- Consumes a temporary shell rc/config root and marker-delimited managed blocks.

- [ ] **Step 1: Write the failing test**

```python
def test_codex_safe_auto_preserves_workspace_sandbox(tmp_path: Path) -> None:
    profile = codex_safe_auto_profile(tmp_path / ".zshrc")
    profile.apply()
    assert "codex --sandbox workspace-write --ask-for-approval never" in (tmp_path / ".zshrc").read_text()

def test_codex_yolo_is_labelled_external_sandbox_only() -> None:
    assert "External Sandbox Only" in codex_yolo_profile(Path("/tmp/rc")).label
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_profiles.py -v`

Expected: FAIL because only the Claude skip-permissions tweak exists.

- [ ] **Step 3: Write minimal implementation**

Implement safe-auto profiles for Codex, Claude, and OpenCode. Implement external-sandbox profiles only as separately named opt-in policies. Use exact documented commands and show that Codex `--yolo` removes sandboxing. Apply/remove only marker-delimited installer blocks.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_profiles.py tests/test_policies_e2e.py tests/test_policy_tweaks.py -v`

Expected: PASS using temporary homes.

- [ ] **Step 5: Commit**

```bash
git add installer/agent_profiles.py installer/policy.py installer/wizard_app.py installer/tweaks.py tests/test_agent_profiles.py tests/test_policies_e2e.py
git commit -m "feat(policies): add reversible agent launch profiles"
```

