---
phase: "14"
slug: "install-update-engine-correctness-default-shell-action-selec"
status: draft
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-14"
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml:46-49`), `asyncio_mode = "auto"` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`/`[tool.coverage.report]`) |
| **Quick run command** | `uv run pytest tests/test_deps.py tests/test_engine.py tests/test_execute_screen.py tests/test_catalog_tui.py -x -q` |
| **Full suite command** | `make test` |
| **Estimated runtime** | ~60-120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_deps.py tests/test_engine.py tests/test_execute_screen.py tests/test_catalog_tui.py -x -q`
- **After every plan wave:** Run `make test`
- **Before `/gsd-verify-work`:** Full suite must be green (`make validate && make test`)
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

No REQ-IDs were supplied for this phase (CONTEXT.md/ROADMAP.md describe it narratively). The map below is keyed to CONTEXT.md's D-01 through D-07 instead.

| Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|-----------|-------------------|-------------|--------|
| D-01 | Selecting an outdated, installed, selected tool via the main flow triggers `UpdateService.run` | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k outdated -x` | ❌ → created by 14-01 T1 | ⬜ pending |
| D-01 (resolver layer) | `resolve_dependencies` contract stays unchanged — new split logic lives one layer up | unit | `uv run pytest tests/test_deps.py -x` | ✅ (baseline locked by 14-01 T3) | ⬜ pending |
| D-02 | No second confirm prompt added; `enter start` remains the only gate | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k confirm -x` | ❌ → created by 14-01 T2 | ⬜ pending |
| D-03 | A blocked update surfaces in the post-run summary log with the reused `"cannot update {tool_id}: {reason}"` text | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k blocked_update -x` | ❌ → created by 14-02 T2 | ⬜ pending |
| D-04 | `set_login_shell` never offered/executed when `Platform.immutable` is `True` | unit | `uv run pytest tests/test_engine.py -k login_shell -x` or new `tests/test_post_install.py` | ❌ → created by 14-03 T1/T2 | ⬜ pending |
| D-05 | On a non-immutable host, `set_login_shell` never fires without an explicit confirm returning True | unit | same new test file | ❌ → created by 14-03 T2; entry-point coverage in 14-04 T3 (console) and 14-05 T1 (in-app) | ⬜ pending |
| D-06 | `set_login_shell` dispatches only from the `oh-my-zsh` tool's ladder, only after a successful method | unit | same new test file + `tests/test_registry.py` assertion that only `oh-my-zsh` declares `post_install = ["set_login_shell"]` | ❌ → created by 14-03 T1/T3 | ⬜ pending |
| D-07 | No generalized "future shell" parameter is introduced | code-review / registry-integrity | `uv run pytest tests/test_registry.py -x` | ✅ (one-declarer gate added by 14-03 T3) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All four are assigned to a planned task in the wave that first needs them, so no task in this phase
verifies against a test file that nobody creates.

- [x] A test asserting `resolve_dependencies` output for a *selected, installed, outdated* tool (currently no such test exists in `tests/test_deps.py`) — establishes the documented, unchanged baseline before `ExecuteScreen`'s new split logic is layered on top. → **14-01 Task 3** (wave 1), plus a structural gate keeping version/ownership state out of `installer/deps.py`.
- [x] `tests/test_execute_screen.py` fixtures for an `ExecuteInputs` that also carries `version_refresh`/`updates` (today's `_execute_inputs` helper at `tests/test_wizard_app.py:4070-4100` has no such fields). → **14-01 Task 1** (wave 1) extends the existing `_inputs` helper with optional service arguments and adds the fake refresh/update services, rather than adding a parallel fixture.
- [x] A new `tests/test_post_install.py` (or equivalent) mirroring `tests/test_postinstall.py`'s structure, for the new `post_install`/`set_login_shell` dispatch table. → **14-03 Task 1** creates it alongside the module (wave 1); **14-03 Task 2** fills in the gate matrix; **14-03 Task 3** adds the two-disjoint-tables integrity test.
- [x] A `Platform.immutable=True` fixture case proving `set_login_shell` is never offered (D-04) — reuse the existing `Platform(os=..., arch=..., immutable=True, has_brew=...)` construction pattern already used throughout `tests/test_resolve.py`/`tests/test_engine.py`. → **14-03 Task 2**, which asserts both that no instructions are produced and that the confirmation callback was never invoked (not-changed and not-asked are two different facts).

---

## Manual-Only Verifications

*All phase behaviors have automated verification (see Per-Task Verification Map). `chsh`'s real PAM-password-prompt behavior on a live atomic-distro host is not exercised automatically — see RESEARCH.md's Assumption A1 — but D-04's hard `Platform.immutable` block makes that path unreachable on the target platform, so no manual verification is required for this phase's scope.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — all 15 tasks across plans 14-01 through 14-05 carry an `<automated>` block; every MISSING reference resolves to the Wave 0 assignments above.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — each of the 15 tasks runs at least one `uv run pytest` invocation in its own gate, so the longest unsampled stretch is zero tasks.
- [x] Wave 0 covers all MISSING references — the four gaps above are each assigned to the task that first needs the fixture, in the wave that first needs it.
- [x] No watch-mode flags — every command is a single-shot `uv run pytest`/`uv run python`/`make` invocation; no `--watch`, `-f`, or interactive runner appears in any gate.
- [x] Feedback latency < 120s — per-task gates run the four pinned files (~60-120s); the two `make validate && make test` gates are end-of-plan only (14-05 Task 3), not per-task.
- [x] `nyquist_compliant: true` set in frontmatter.
- [x] Pinned `-k` selectors are claimed by a named task: `-k outdated` (14-01 T1), `-k confirm` (14-01 T2), `-k blocked_update` (14-02 T2), `-k login_shell` (14-03 T1/T2, 14-04 T3, 14-05 T1), and each owning task's `fails_when` treats pytest exit code 5 ("no tests ran") as a failure, so an unmatched selector cannot pass silently.

**Approval:** 2026-09-14 — the five plans cover all four Wave 0 gaps and every pinned selector. `status` stays `draft` until the phase actually executes; it flips later in the lifecycle, against observed runs rather than against plans.
