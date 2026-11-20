---
phase: "27"
slug: "tool-onboarding-skill-terminal-defaults-as-rules"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-20"
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest through `uv run` (xdist `-n auto`, capped near 40% of host threads, `tests/conftest.py`); strict pyright, ruff, bandit, vulture (vulture covers `installer` and `devtools` only) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_catalog_audit_skill.py tests/test_docs.py tests/test_docs_only.py tests/test_hook_wiring.py -q` |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | quick about 30 seconds; full about 8 minutes |

---

## Sampling Rate

- **After every task commit:** Run the quick run command above
- **After every plan wave:** Run `make validate && make test`
- **Before `/gsd-verify-work`:** Full suite must be green, both skill-judge verdict files committed, CI `validate-and-test` green on both OSes
- **Max feedback latency:** 60 seconds for the quick run

---

## Per-Task Verification Map

Task IDs are assigned by the plans; each requirement row below must be covered by at least one task with an `<automated>` command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-02-01, 27-02-02 | 02 | 2 | SKILL-01 | T-27-04, T-27-05 | The skill never recommends the global Option-as-Alt switch | unit (text) | `uv run pytest tests/test_tool_onboarding_skill.py -k rules -q` | ❌ W0 | ⬜ pending |
| 27-01-02, 27-01-03 | 01 | 1 | SKILL-02 | T-27-03 | A missing, extra, duplicate or lookalike table row fails the test | unit | `uv run pytest tests/test_tool_onboarding_skill.py -k table -q` | ❌ W0 | ⬜ pending |
| 27-03-01 | 03 | 3 | SKILL-03 | T-27-06 | `partial: kept yours` and the displaced-default example are stated | unit (text) | `uv run pytest tests/test_tool_onboarding_skill.py -k conflicts -q` | ❌ W0 | ⬜ pending |
| 27-03-03 | 03 | 3 | SKILL-04 | T-27-07 | `~/Applications`, `~/.local/bin` and the say-why clause are stated | unit (text) | `uv run pytest tests/test_tool_onboarding_skill.py -k macos_apps -q` | ❌ W0 | ⬜ pending |
| 27-03-02 | 03 | 3 | SKILL-05 | T-27-08 | The CI job named in the skill exists in `.github/workflows/ci.yml` with `macos-latest` in its matrix and a gated `Test` step running `make test` (parsed, not grepped) | unit | `uv run pytest tests/test_tool_onboarding_skill.py -k macos_testing -q` | ❌ W0 | ⬜ pending |
| 27-01-01, 27-04-01, 27-04-03 | 01, 04 | 1, 4 | SKILL-06 | T-27-01, T-27-02, T-27-09, T-27-11, T-27-12, T-27-13, T-27-14 | Exactly two verdict files; after score is not lower; same rubric and rubric maxima; verdicts come from pre-dispatch orchestrator judge runs (bracketed by a tree snapshot diff, nothing reverted), never the executor, whose Task 1 only verifies the commit | unit | `uv run pytest tests/test_tool_onboarding_skill.py -k verdict -q` | ❌ W0 | ⬜ pending |
| 27-04-02 | 04 | 4 | SKILL-06 (D-04) | — | The shared parser refuses every malformed verdict the old private one did | existing | `uv run pytest tests/test_catalog_audit_skill.py -q` | ✅ | ⬜ pending |
| 27-02-01, 27-02-02 | 02 | 2 | SPEC R6 | T-27-05 | Step 7 pinned phrases hold; the audit skill's heading quote resolves | existing | `uv run pytest tests/test_docs.py tests/test_catalog_audit_skill.py -q` | ✅ | ⬜ pending |
| 27-01-02, 27-04-03 | 01, 04 | 1, 4 | docs-only | T-27-10 | New markdown literals are classified; ledger globs resolve; verdict files are test-read | existing | `uv run pytest tests/test_docs_only.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/skill_verdicts.py` — moved verdict helpers (the existing `tests/test_catalog_audit_skill.py` stays green with no assertion edits)
- [ ] `tests/test_tool_onboarding_skill.py` — table, rules and verdict tests with fixtures for SKILL-01..06
- [ ] `devtools/docs_only.py` `TEST_READ` entry and `tests/test_docs_only.py` `LEDGER` rows (run `tests/test_docs_only.py` for the exact pair list; prove the recursive glob on this host first)
- [ ] `27-SKILLJUDGE-before.md` produced by a fresh read-only judge on the unedited skill, committed before any edit
- [ ] One-line edit in `.claude/skills/catalog-audit/SKILL.md` (line 80) in the same commit as the step 7 heading rename

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-Mac behavior of the macOS rules | SKILL-05 | No Mac host in this run | A UAT line deferred to the owner's Mac; the skill states it as a rule, no code ships in this phase |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
