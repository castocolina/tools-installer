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

Filled by the planner from the final plans (2026-11-16); one row per task. Revised 2026-11-16 for review cycle 1 (`d933e9c8`) and review cycle 2 (`52b2b19f`).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | HOOK-01 | T-26-03 | each static hook calls its make target; `make validate` is `pre-commit run --all-files`; devtools under every gate; gate set read from the Makefile `[gate]` marker via `gate_targets()` (review M1) | unit (text parse) | `uv run pytest tests/test_hook_wiring.py tests/test_makefile.py tests/test_reachability.py -n auto -q --no-cov` and `make validate` | ❌ W0 | ⬜ pending |
| 26-01-02 | 01 | 1 | HOOK-02 | T-26-01, T-26-02, T-26-03 | `make test` push-only and last; no bypass literal (P1); no auto-fix (P3); drift guard non-vacuous, an unhooked `[gate]` target fails (review M1) | unit | `uv run pytest tests/test_hook_wiring.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-01-03 | 01 | 1 | HOOK-04 | — | `make run` is the wizard target; `setup` gone; `make help` lists names with digits | unit | `uv run pytest tests/test_makefile.py tests/test_reachability.py tests/test_hook_wiring.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-02-01 | 02 | 1 | HOOK-04 | T-26-04 | every user-visible hint names `make run` | unit | `uv run pytest tests/test_guidance.py tests/test_wizard_app.py tests/test_app.py tests/test_render.py tests/test_schedules_handover.py -n auto -q --no-cov` | ✅ edit | ⬜ pending |
| 26-02-02 | 02 | 1 | HOOK-04 | T-26-04 | docs, skill and comments name `make run`; zero old-target hits in tracked source | unit + git grep | `uv run pytest tests/test_catalog_audit_skill.py tests/test_docs.py tests/test_setup.py tests/test_tool_browser.py tests/test_wizard_app.py -n auto -q --no-cov` | ✅ edit | ⬜ pending |
| 26-03-01 | 03 | 1 | HOOK-02 | T-26-05 | baseline pass count read after `app.await_publication` (no pass pending; review M2); settled body waits; no fixed pause; a mitigation of the suspected window, root cause unconfirmed (A1, review C2-M1) | unit (pilot) | `uv run pytest tests/test_screen_family.py -n auto -q --no-cov` | ✅ edit | ⬜ pending |
| 26-03-02 | 03 | 1 | HOOK-02 | T-26-05 | 50/50 runs after the change; full suite green; todo closed with "the root cause stays unconfirmed" and a reopen rule (review C2-M1) | loop + suite | `make test` (plus the 50-run loop script) | ✅ | ⬜ pending |
| 26-04-01 | 04 | 2 | HOOK-02, HOOK-03 | T-26-06, T-26-10 | every ref parsed; push stage through pre-commit with the stash on; fails closed | unit (fake runner) | `uv run pytest tests/test_push_gate.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-04-02 | 04 | 2 | HOOK-03 | T-26-08, T-26-38, T-26-39 | five refusals, first match wins, sorted names, space intact; refusal 3 = any untracked non-ignored file outside `.planning/` (root `conftest.py`, root config; D-25, review H1) plus every gate-read file of `GATE_READ_PATHSPECS`, ignored or not, from one bounded `--glob-pathspecs` query; gate-read files never advised to be ignored; failing query fails closed (D-28, review C2-H1) | unit (fake runner) | `uv run pytest tests/test_push_gate.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-04-03 | 04 | 2 | HOOK-03 | T-26-07 | SIGINT/SIGTERM/SIGHUP forwarded once as SIGINT; a signal in the spawn window forwarded once after the handle exists (review M3); signalled gate never exits 0 (P2) | Python child (real signals) | `uv run pytest tests/test_push_gate.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-05-01 | 05 | 2 | HOOK-04 | T-26-11 | `make dev-setup` writes both hooks into the common hooks dir; CI calls it | unit (fake runner) + text | `uv run pytest tests/test_hooks_install.py tests/test_makefile.py tests/test_ci_workflow.py tests/test_hook_wiring.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-05-02 | 05 | 2 | HOOK-04 | T-26-11, T-26-12, T-26-13, T-26-14, T-26-15, T-26-31, T-26-32, T-26-40, T-26-41 | skip only on `not a git repository` (other rev-parse failures exit 1; review M4); fail on core.hooksPath; foreign or non-regular (symlink) pre-push refused untouched (review M5); non-regular `pre-commit`, or a foreign `pre-commit` next to an existing `pre-commit.legacy`, refused untouched before pre-commit runs (D-29, review C2-H2); rerun byte-identical; worktree warning; shim fails closed | unit + `sh` child | `uv run pytest tests/test_hooks_install.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-05-03 | 05 | 2 | HOOK-04 | T-26-14 | docs name `make dev-setup`; agents never run it, except the final owner-assigned checkpoint (D-26, review M12) | docs test + git grep | `uv run pytest tests/test_docs.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 26-06-01 | 06 | 3 | HOOK-01, HOOK-02 | T-26-16, T-26-18, T-26-37 | real commit runs the static gates; green push lands with `test.ran`; red push aborted, remote unmoved; `cleanup` trap reaps every descendant process group, the gate's pre-commit group included, before deleting the scratch dir (review C2-M2) | e2e (real git) | `make hooks-e2e` | ❌ W0 | ⬜ pending |
| 26-06-02 | 06 | 3 | HOOK-03 | T-26-16, T-26-37, T-26-38 | every gate case pushes a real update and proves the gate ran (review H4); real refusals incl. root `conftest.py`/`pytest.ini` (D-25) and an ignored root `conftest.py` and `GNUmakefile` that make a committed failing test pass (D-28, review C2-H1); expected bytes saved after the edit (review H3); restore on existing, new and root pushes and after a failed suite (review M6); deletion runs nothing; fail-fast | e2e (real git) | `make hooks-e2e` | ❌ W0 | ⬜ pending |
| 26-06-03 | 06 | 3 | HOOK-03, HOOK-04 | T-26-18, T-26-37, T-26-40 | real install branches incl. a refused `pre-push` symlink (review M5), a refused `pre-commit` symlink and a foreign `pre-commit` next to `pre-commit.legacy` left byte-identical (D-29, review C2-H2); SIGINT/SIGTERM/SIGHUP restore byte-identical, expected bytes saved after the edit; an aborted nested harness leaves no process of its two groups and no scratch dir (review C2-M2) | e2e (real git) | `make hooks-e2e` | ❌ W0 | ⬜ pending |
| 26-07-01 | 07 | 4 | HOOK-05 | T-26-19, T-26-21, T-26-22 | branch-push CI; fast pass gated `!= 'false'` under unchanged job names | unit | `uv run pytest tests/test_docs_only.py tests/test_ci_workflow.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-07-02 | 07 | 4 | HOOK-05 | T-26-20 | renames, odd names, git failures and empty changes run everything (P4) | unit | `uv run pytest tests/test_docs_only.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-07-03 | 07 | 4 | HOOK-05 | T-26-19, T-26-33 | every test `.md`/`.planning` literal classified; ledger files are test-read; runtime link targets of `LINK_CHECKED_DOCS` are test-read (D-27, review M7) | unit (AST + links) | `uv run pytest tests/test_docs_only.py tests/test_docs.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 26-08-01 | 08 | 5 | HOOK-06 | T-26-34 | gate/target/stage table, measured timings (unreadable figures marked unavailable; review L2), placeholder-free recovery whose apply runs only on the guarded line `git apply --check "$patch" && git apply "$patch"` (review M8, C2-H3); refusal 3 documented with `GATE_READ_PATHSPECS`, no ignore advice for gate-read files (D-28) | unit (doc pins) | `uv run pytest tests/test_docs.py tests/test_hook_wiring.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-08-02 | 08 | 5 | HOOK-05, HOOK-06 | T-26-23 | path to main; escape hatch off → push → on → read-back with DELETE, push and POST each guarded so the read-back always runs, plus escalation (P6, review M9, C2-M3) | unit (doc pins) | `uv run pytest tests/test_docs.py tests/test_hook_wiring.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-08-03 | 08 | 5 | HOOK-06 | T-26-24, T-26-25 | no stale validate wording; AGENTS gate table; D-14 todo | unit + rg | `uv run pytest tests/test_docs.py tests/test_hook_wiring.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ extend | ⬜ pending |
| 26-09-01 | 09 | 6 | HOOK-05 | T-26-26, T-26-27 | strict + `enforce_admins` read back twice; untested probe rejected | manual (orchestrator) | `gh api repos/castocolina/tools-installer/branches/main/protection --jq …` | n/a | ✅ green 2026-11-16: read back twice identically (`enforce_admins: true`, `strict: true`, both contexts); probe push rejected with GH006 "2 of 2 required status checks are expected" |
| 26-09-02 | 09 | 6 | HOOK-04 | — | untracked files outside `.planning/` cleared (`.graphifyignore` to `.git/info/exclude`, D-25); the gate-read query over `GATE_READ_PATHSPECS` lists nothing, anything listed is reported, never ignored (D-28); real hook install from the main checkout (D-26 exception), idempotent | manual (orchestrator) | `test -x .git/hooks/pre-commit && test -x .git/hooks/pre-push && grep -c 'tools-installer: pre-push gate' .git/hooks/pre-push` | n/a | ✅ green 2026-11-16: nothing untracked outside `.planning/` (`.graphifyignore` is committed, owner); gate-read query empty; `make dev-setup` installed both hooks, marker count 1, rerun byte-identical |
| 26-09-03 | 09 | 6 | HOOK-05 | T-26-28, T-26-29, T-26-35, T-26-36 | last change lands by branch push → green CI → fast-forward; `full=false` read from the job log (review M10); `main` is the tested commit; a fallback runs the guarded escape-hatch block, so the read-back always runs, and an unconfirmed restore stops every push (review C2-H4); a fallback landing is recorded UNRESOLVED (review M11) in a follow-up commit on the phase branch, not landed on `main` (review C2-M4) | manual (orchestrator) | `git fetch -q origin main && test "$(git rev-parse FETCH_HEAD)" = "$(git rev-parse HEAD)"` | n/a | ◆ landing in progress (this commit) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → test map (from research)

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| HOOK-01 | commit hooks are `make <target>` for existing targets; every gate target but `test` has a commit hook; `validate` is exactly `pre-commit run --all-files`; no commit hook runs tests; no `--fix` / bare `ruff format` (P3); zero-check guard; set comparison | unit (text parse) | `uv run pytest --no-cov tests/test_hook_wiring.py` |
| HOOK-02 | static hooks carry `pre-push`, the test hook is push-only and last, all `always_run`, `pass_filenames: false`; no `--no-verify` / `SKIP=` (P1) | unit | `uv run pytest --no-cov tests/test_hook_wiring.py` |
| HOOK-02/03 | refusals (staged, any untracked non-ignored file outside `.planning/` per D-25 plus every gate-read file even when ignored per D-28, unstaged config, unmerged, not-HEAD), deletion-only pass, root push keeps the stash, sorted names incl. a space, signal forwarding incl. the spawn window | fake-runner unit + Python child | `uv run pytest --no-cov tests/test_push_gate.py` |
| HOOK-02/03 (real) | red suite aborts the push and the remote ref stays; green moves it; every gate case pushes a real update and proves the gate ran; byte-identical restore (expected bytes saved after the edit) after pass / fail / SIGINT / SIGTERM / SIGHUP; new-branch first push; root `conftest.py`/`pytest.ini` refused; ignored root `conftest.py`/`GNUmakefile` refused (D-28); harness abort reaps every group | e2e script | `make hooks-e2e` |
| HOOK-04 | `dev-setup` recipe; `default_install_hook_types: [pre-commit]`; idempotent bytes; not-a-repo skip exit 0; `core.hooksPath` exit non-zero naming it; worktree uses the common hooks dir; unsafe commit-hook migration refused (D-29); no `install` / `setup` targets; `run` launches the wizard | unit (fake runner) + text parse + e2e | `uv run pytest --no-cov tests/test_hooks_install.py tests/test_makefile.py` and `make hooks-e2e` |
| HOOK-05 | `branches-ignore: [main]`; job names byte-identical; step-level `if:`; `fetch-depth: 0`; docs-only matrix (`.planning/` only fast; `.py`, `ci.yml`, a test-read `.md`, a `.py` renamed into `.planning/`, a path with a space run full); Markdown-read drift detector; runtime link-target drift detector (D-27) | unit | `uv run pytest --no-cov tests/test_docs_only.py tests/test_ci_workflow.py` |
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
