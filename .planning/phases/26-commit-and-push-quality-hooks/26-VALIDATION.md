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

Filled by the planner from the final plans (2026-11-16); one row per task.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | HOOK-01 | T-26-03 | each static hook calls its make target; `make validate` is `pre-commit run --all-files`; devtools under every gate | unit (text parse) | `uv run pytest tests/test_hook_wiring.py tests/test_makefile.py tests/test_reachability.py -n auto -q --no-cov` and `make validate` | ❌ W0 | ⬜ pending |
| 26-01-02 | 01 | 1 | HOOK-02 | T-26-01, T-26-02 | `make test` push-only and last; no bypass literal (P1); no auto-fix (P3); drift guard non-vacuous | unit | `uv run pytest tests/test_hook_wiring.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-01-03 | 01 | 1 | HOOK-04 | — | `make run` is the wizard target; `setup` gone; `make help` lists names with digits | unit | `uv run pytest tests/test_makefile.py tests/test_reachability.py tests/test_hook_wiring.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-02-01 | 02 | 1 | HOOK-04 | T-26-04 | every user-visible hint names `make run` | unit | `uv run pytest tests/test_guidance.py tests/test_wizard_app.py tests/test_app.py tests/test_render.py tests/test_schedules_handover.py -n auto -q --no-cov` | ✅ edit | ⬜ pending |
| 26-02-02 | 02 | 1 | HOOK-04 | T-26-04 | docs, skill and comments name `make run`; zero old-target hits in tracked source | unit + git grep | `uv run pytest tests/test_catalog_audit_skill.py tests/test_docs.py tests/test_setup.py tests/test_tool_browser.py tests/test_wizard_app.py -n auto -q --no-cov` | ✅ edit | ⬜ pending |
| 26-03-01 | 03 | 1 | HOOK-02 | T-26-05 | settled pass count and body waits, no fixed pause | unit (pilot) | `uv run pytest tests/test_screen_family.py -n auto -q --no-cov` | ✅ edit | ⬜ pending |
| 26-03-02 | 03 | 1 | HOOK-02 | T-26-05 | 50/50 runs after the fix; full suite green | loop + suite | `make test` (plus the 50-run loop script) | ✅ | ⬜ pending |
| 26-04-01 | 04 | 2 | HOOK-02, HOOK-03 | T-26-06, T-26-10 | every ref parsed; push stage through pre-commit with the stash on; fails closed | unit (fake runner) | `uv run pytest tests/test_push_gate.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-04-02 | 04 | 2 | HOOK-03 | T-26-08 | five refusals, first match wins, sorted names, space intact | unit (fake runner) | `uv run pytest tests/test_push_gate.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-04-03 | 04 | 2 | HOOK-03 | T-26-07 | SIGINT/SIGTERM/SIGHUP forwarded once as SIGINT; signalled gate never exits 0 (P2) | Python child (real signals) | `uv run pytest tests/test_push_gate.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-05-01 | 05 | 2 | HOOK-04 | T-26-11 | `make dev-setup` writes both hooks into the common hooks dir; CI calls it | unit (fake runner) + text | `uv run pytest tests/test_hooks_install.py tests/test_makefile.py tests/test_ci_workflow.py tests/test_hook_wiring.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-05-02 | 05 | 2 | HOOK-04 | T-26-11, T-26-12, T-26-13, T-26-14, T-26-15 | skip outside git; fail on core.hooksPath; foreign pre-push refused untouched; rerun byte-identical; worktree warning; shim fails closed | unit + `sh` child | `uv run pytest tests/test_hooks_install.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-05-03 | 05 | 2 | HOOK-04 | T-26-14 | docs name `make dev-setup`; agents never run it | docs test + git grep | `uv run pytest tests/test_docs.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 26-06-01 | 06 | 3 | HOOK-01, HOOK-02 | T-26-16 | real commit runs the static gates; red push aborted, remote unmoved | e2e (real git) | `make hooks-e2e` | ❌ W0 | ⬜ pending |
| 26-06-02 | 06 | 3 | HOOK-03 | T-26-16 | real refusals; byte-identical restore on existing, new and root pushes; deletion runs nothing; fail-fast | e2e (real git) | `make hooks-e2e` | ❌ W0 | ⬜ pending |
| 26-06-03 | 06 | 3 | HOOK-03, HOOK-04 | T-26-18 | real install branches; SIGINT/SIGTERM/SIGHUP restore byte-identical | e2e (real git) | `make hooks-e2e` | ❌ W0 | ⬜ pending |
| 26-07-01 | 07 | 4 | HOOK-05 | T-26-19, T-26-21, T-26-22 | branch-push CI; fast pass gated `!= 'false'` under unchanged job names | unit | `uv run pytest tests/test_docs_only.py tests/test_ci_workflow.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-07-02 | 07 | 4 | HOOK-05 | T-26-20 | renames, odd names, git failures and empty changes run everything (P4) | unit | `uv run pytest tests/test_docs_only.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-07-03 | 07 | 4 | HOOK-05 | T-26-19 | every test `.md`/`.planning` literal classified; ledger files are test-read | unit (AST) | `uv run pytest tests/test_docs_only.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-08-01 | 08 | 5 | HOOK-06 | — | gate/target/stage table, measured timings, push-gate recovery | unit (doc pins) | `uv run pytest tests/test_docs.py tests/test_hook_wiring.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-08-02 | 08 | 5 | HOOK-05, HOOK-06 | T-26-23 | path to main; escape hatch off → on → read-back (P6) | unit (doc pins) | `uv run pytest tests/test_docs.py tests/test_hook_wiring.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-08-03 | 08 | 5 | HOOK-06 | T-26-24, T-26-25 | no stale validate wording; AGENTS gate table; D-14 todo | unit + rg | `uv run pytest tests/test_docs.py tests/test_hook_wiring.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-09-01 | 09 | 6 | HOOK-05 | T-26-26, T-26-27 | strict + `enforce_admins` read back twice; untested probe rejected | manual (orchestrator) | `gh api repos/castocolina/tools-installer/branches/main/protection --jq …` | n/a | ⬜ pending |
| 26-09-02 | 09 | 6 | HOOK-04 | — | real hook install from the main checkout, idempotent | manual (orchestrator) | `test -x .git/hooks/pre-commit && test -x .git/hooks/pre-push && grep -c 'tools-installer: pre-push gate' .git/hooks/pre-push` | n/a | ⬜ pending |
| 26-09-03 | 09 | 6 | HOOK-05 | T-26-28, T-26-29 | last change lands by branch push → green CI → fast-forward; `main` is the tested commit | manual (orchestrator) | `git fetch -q origin main && test "$(git rev-parse FETCH_HEAD)" = "$(git rev-parse HEAD)"` | n/a | ⬜ pending |

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
