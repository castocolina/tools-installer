---
phase: "26"
slug: "commit-and-push-quality-hooks"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-16"
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `26-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8 + pytest-xdist + pytest-asyncio; coverage `fail_under = 90` (`source` gains `devtools`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| **Quick run command** | `uv run pytest --no-cov -n auto tests/test_push_gate.py tests/test_hooks_install.py tests/test_docs_only.py tests/test_hook_wiring.py tests/test_makefile.py tests/test_ci_workflow.py tests/test_docs.py` |
| **Full suite command** | `make validate && make test` |
| **Real-git proof** | `make hooks-e2e` (scratch repos under `mktemp -d`, `env -i` allowlist, scratch `HOME`; never this checkout's `.git`) |
| **Estimated runtime** | quick ~10 s; full ~75 s (validate 12.1 s + test 62.3 s, measured 2026-11-16) |

The test sandbox (`tests/sandbox.py`) refuses real `git`, `make`, `uv` and `pre-commit` inside pytest.
Pytest tests use injected fake runners or fake tools planted under `tmp_path`; real git and pre-commit
behaviour is proven only by the e2e script. The sandbox is never widened.

---

## Sampling Rate

- **After every task commit:** the quick run command, narrowed to the test files the task touches.
- **After every plan wave:** `make validate && make test` (orchestrator, on the merged tree).
- **Before `/gsd-verify-work`:** full suite green plus `make hooks-e2e` green.
- **Max feedback latency:** 75 seconds.

---

## Per-Task Verification Map

Filled by the planner from the final plans; one row per task.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-XX-XX | XX | X | HOOK-0X | T-26-XX / — | see plan | unit | see plan `<automated>` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → test map (from research)

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| HOOK-01 | commit hooks are `make <target>` for existing targets; every gate target but `test` has a commit hook; `validate` is exactly `pre-commit run --all-files`; no commit hook runs tests; no `--fix` / bare `ruff format` (P3); zero-check guard; set comparison | unit (text parse) | `uv run pytest --no-cov tests/test_hook_wiring.py` |
| HOOK-02 | static hooks carry `pre-push`, the test hook is push-only and last, all `always_run`, `pass_filenames: false`; no `--no-verify` / `SKIP=` (P1) | unit | `uv run pytest --no-cov tests/test_hook_wiring.py` |
| HOOK-02/03 | refusals (staged, untracked `.py`, unstaged config, unmerged, not-HEAD), deletion-only pass, root push keeps the stash, sorted names incl. a space, signal forwarding | fake-runner unit + Python child | `uv run pytest --no-cov tests/test_push_gate.py` |
| HOOK-02/03 (real) | red suite aborts the push and the remote ref stays; green moves it; byte-identical restore after pass / fail / SIGINT / SIGTERM / SIGHUP; new-branch first push | e2e script | `make hooks-e2e` |
| HOOK-04 | `dev-setup` recipe; `default_install_hook_types: [pre-commit]`; idempotent bytes; not-a-repo skip exit 0; `core.hooksPath` exit non-zero naming it; worktree uses the common hooks dir; no `install` / `setup` targets; `run` launches the wizard | unit (fake runner) + text parse + e2e | `uv run pytest --no-cov tests/test_hooks_install.py tests/test_makefile.py` and `make hooks-e2e` |
| HOOK-05 | `branches-ignore: [main]`; job names byte-identical; step-level `if:`; `fetch-depth: 0`; docs-only matrix (`.planning/` only fast; `.py`, `ci.yml`, a test-read `.md`, a `.py` renamed into `.planning/`, a path with a space run full); Markdown-read drift detector | unit | `uv run pytest --no-cov tests/test_docs_only.py tests/test_ci_workflow.py` |
| HOOK-06 | gate / target / stage table with timings; branch → CI → `main` flow; off / on / read-back commands; no "runs pre-commit hooks" claim | unit (grep) | `uv run pytest --no-cov tests/test_docs.py tests/test_hook_wiring.py` |
| D-12 | flaky screen-family test stable | 50 runs under `-n auto`, before and after | shell loop (no repeat plugin in the dev deps) |

---

## Wave 0 Requirements

- [ ] `tests/test_push_gate.py` — HOOK-02/03 gate logic with a fake runner and a `sys.executable` child with fake `git` / `pre-commit` under `tmp_path`
- [ ] `tests/test_hooks_install.py` — HOOK-04 installer (fake runner)
- [ ] `tests/test_docs_only.py` — HOOK-05 rule and Markdown-read drift detector
- [ ] `tests/test_hook_wiring.py` — HOOK-01/02 wiring, P1, P3, doc claims
- [ ] `scripts/hooks-e2e.sh` + `make hooks-e2e` — real git / pre-commit scratch repos, added to the shellcheck list
- [ ] extend `tests/test_makefile.py` (gate targets, `dev-setup`, `run`, no `install` / `setup`) and `tests/test_ci_workflow.py` (triggers)
- [ ] `devtools` added to pyright `include`, coverage `source`, vulture `paths` and the ruff targets

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `enforce_admins` on, strict, both contexts required on `main` | HOOK-05 | Needs a mutating GitHub call on the real repo; executors never call mutating APIs | Orchestrator checkpoint: run the documented `gh api` commands, then the read-back GET shows `enforce_admins.enabled: true`, `strict: true`, both contexts |
| The phase's last change reaches `main` by branch push → green CI → fast-forward | HOOK-05 | Needs real pushes and real CI | Orchestrator checkpoint after every other plan |
| Hooks installed for real in this checkout | HOOK-04 | `make dev-setup` writes the shared `.git/hooks`; tests and executors never do | Orchestrator step at the end of the phase |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 75s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
