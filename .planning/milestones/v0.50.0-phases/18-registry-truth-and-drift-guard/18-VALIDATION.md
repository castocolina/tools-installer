---
phase: "18"
slug: "registry-truth-and-drift-guard"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-15"
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `18-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8 + pytest-xdist + pytest-cov + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`, `fail_under = 90`) |
| **Quick run command** | `uv run pytest tests/<file>.py -q --no-cov` |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | ~65 seconds (full suite, baseline 3572 passed at Phase 17 close) |

---

## Sampling Rate

- **After every task commit:** Run the touched test file(s) with `uv run pytest tests/<file>.py -q --no-cov`
- **After every plan wave:** Run `make validate && make test`
- **Before `/gsd-verify-work`:** Full suite must be green, `! rg -n "managed-download" installer/`, `git diff --quiet 72c9047 -- pyproject.toml uv.lock` (no new dependency), one `make e2e` after the install-pipeline plan lands, and a recorded live `make verify-registry` run
- **Max feedback latency:** 70 seconds

---

## Per-Task Verification Map

Filled by the planner per task (`<automated>` + `<fails_when>`); the requirement-level map below is the contract each plan must cover.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| REG-01 | unknown method key (e.g. `formula` on github_release) fails with tool id + key; every shipped key accepted | unit | `uv run pytest tests/test_model.py -q --no-cov -k "unknown_key or method_params"` | ❌ W0 | ⬜ pending |
| REG-01 | `cli_name` names the macOS CLI link; uninstall uses the same name | unit | `uv run pytest tests/test_apps.py tests/test_uninstall.py -q --no-cov -k cli_name` | ❌ W0 | ⬜ pending |
| REG-02 | missing / string / datetime / future `verified` rejected with tool id; shipped registry loads | unit | `uv run pytest tests/test_model.py tests/test_registry.py -q --no-cov -k verified` | ❌ W0 | ⬜ pending |
| REG-03 | pre-fix difftastic template fixture flagged (renamed asset); missing member; checksum drift; corrupt archive is drift; state keyed by tool id + extraction settings (L-18-11); only transport failures or a rate limit block a run (L-18-15); drift confirmed in an otherwise blocked run still exits 1 and reaches the issue (L-18-18); issue upsert with safe code spans; INCONCLUSIVE with no `gh` issue call | unit | `uv run pytest tests/test_verify_registry.py -q --no-cov` | ❌ W0 | ⬜ pending |
| REG-03 | workflow only `schedule` + `workflow_dispatch`, pinned `permissions`, absent from `ci.yml` | unit | `uv run pytest tests/test_verify_registry_workflow.py -q --no-cov` | ❌ W0 | ⬜ pending |
| REG-04 | digest match installs; mismatch → checksum mismatch, nothing linked; no digest → installs unverified with a reason | unit | `uv run pytest tests/test_download.py tests/test_engine.py tests/test_versions.py -q --no-cov -k "digest or release"` | ❌ W0 | ⬜ pending |
| REG-05 | fake binary exiting 127 falls through to the next method; no link left; existing good link untouched; a loader error in stderr fails the smoke on any exit (18-09); a sourced 0644 `<bin_dir>/<cmd>` is not smoked and a failed manager smoke reports its removal command (18-19, L-18-14/L-18-16) | unit | `uv run pytest tests/test_executors.py tests/test_download.py tests/test_apps.py tests/test_engine.py -q --no-cov -k "smoke or removal_command or leftover_package"` | ❌ W0 | ⬜ pending |
| REG-05 | `smoke_argv` loads on binary-installing kinds, closed shape, rejected on handoff kinds (18-20) | unit | `uv run pytest tests/test_model.py -q --no-cov -k smoke_argv` | ❌ W0 | ⬜ pending |
| REG-06 | `uv run --isolated --no-dev` on exactly the launchers and `install.sh`; absent on `validate`/`test`; e2e harness matches (CONTEXT L-18-01); an activated project venv is dropped from PATH at the setup.py entry point (review H2) | unit | `uv run pytest tests/test_makefile.py tests/test_install_sh.py tests/test_locations.py -q --no-cov` | ❌ W0 | ⬜ pending |
| REG-07 | `/usr/bin/java` stub alone → not installed with reason; `java_home` ok → installed; same for git/CLT | unit | `uv run pytest tests/test_status.py -q --no-cov -k stub` | ❌ W0 | ⬜ pending |
| REG-08 | `parse_version('-1') is None`; quoted and `version=` output parsed, never fabricated | unit | `uv run pytest tests/test_versions.py -q --no-cov -k "fabricat or observed"` | ❌ W0 | ⬜ pending |
| REG-09 | each applied audit data fix asserted; `managed-download` gone | unit + grep | `uv run pytest tests/test_registry.py tests/test_install_ownership.py -q --no-cov` and `! rg -n "managed-download" installer/` | ❌ W0 | ⬜ pending |
| REG-10 | no `drawio-cli`; `drawio-desktop` audience `both`; stale `drawio-cli` cache key ignored | unit | `uv run pytest tests/test_registry.py tests/test_version_cache.py -q --no-cov -k drawio` | ❌ W0 | ⬜ pending |
| R11 | pinned URLs use `{ver}`; loader requires `version` + `sha256`; bump writer changes only intended lines | unit | `uv run pytest tests/test_model.py tests/test_verify_registry.py tests/test_registry.py -q --no-cov -k "pin or bump"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_verify_registry.py` — REG-03, R11 (canned release JSON inline)
- [ ] `tests/test_verify_registry_workflow.py` — REG-03 prohibitions
- [ ] `tests/test_makefile.py` — REG-06
- [ ] shared executable fake-member fixture in `tests/test_download.py` — REG-04/05
- [ ] `verified` key added to inline `[[tool]]` fixtures (helper in `tests/test_model.py`) — REG-02

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ruff resolves its real owner under `make setup` | REG-06 | needs a real install | backstop: `make e2e` (container) |
| macOS stub rule on a real Mac | REG-07 | no macOS host | backstop: CI macos-latest job + fixtures |
| first real weekly workflow run | REG-03 | needs GitHub schedule/dispatch after merge | `gh workflow run verify-registry.yml` after the main push; record the run |
| live pin bump run | R11 | networked, date-dependent maintainer action | executed once by the plan executor; output recorded in the SUMMARY |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 70s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
