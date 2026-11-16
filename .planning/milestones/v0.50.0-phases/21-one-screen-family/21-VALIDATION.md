---
phase: "21"
slug: "one-screen-family"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-18"
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Seeded from `21-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (`asyncio_mode = "auto"`), pytest-xdist, pytest-cov `fail_under = 90` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest -n auto tests/test_screen_family.py tests/test_tool_browser.py tests/test_uninstall.py tests/test_session.py tests/test_plan.py -q --no-cov` |
| **Screen run command** | `uv run pytest -n auto tests/test_wizard_app.py tests/test_catalog_tui.py tests/test_policies_e2e.py tests/test_layout_80x20.py tests/test_execute_screen.py -q --no-cov` |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | ~30 seconds (quick + screen), full suite several minutes |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched module (`--no-cov`)
- **After every plan wave:** Run quick + screen commands, then `make validate && make test`
- **Before `/gsd-verify-work`:** Full suite must be green, twice (order/isolation flakes)
- **Max feedback latency:** 60 seconds

---

## Per-Requirement Verification Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| UI-01 | clear -> pop -> push -> enter per view; current-key no-op | pilot | `uv run pytest -n auto tests/test_screen_family.py -k "call_order or current_view" -q --no-cov` | ❌ Wave 0 |
| UI-01 | matrix: {install close, `u` x3 tiers, removal, Policies toggle, Doctor `r`} x {system,user,ai,Uninstall,Policies,Doctor}, next entry and visible | pilot (parametrised) | `... -k matrix` | ❌ Wave 0 |
| UI-01 | entering a view starts zero passes; mutation ends with exactly one; coalescing; superseded pass discarded | unit+pilot | `... -k "no_pass_on_entry or coalesce"` | ❌ Wave 0 |
| UI-02 | first-entry status kept; leave clears; re-entry shows none; publish never clears | pilot | `... -k status_lifecycle` | ❌ Wave 0 |
| UI-03 | fixtures per group; unknown owner shows no manager/argv; BROKEN repair text; empty machine shows only `nothing to do`; `yourself` suffix kept; Health column | unit (`uninstall_group`) + pilot | `uv run pytest -n auto tests/test_uninstall.py tests/test_wizard_app.py -k "uninstall" -q --no-cov` | ✅ extend (rewrite `_uninstall_inputs`) |
| UI-05 | held remover: UI responsive, navigation works, second removal and every mutation refused, rows `…` only for removed ids, afterwards `nothing to do`, `○` on tiers, ban OFF in Policies | pilot | `uv run pytest -n auto tests/test_screen_family.py -k removal -q --no-cov` | ❌ Wave 0 |
| UI-05 | quit during removal waits; crashed remover still exits and releases the lock | pilot | `... -k "quit or crashed"` | ❌ Wave 0 |
| UI-05 | `mark_pending` vs in-flight pass | unit | `uv run pytest tests/test_version_status.py tests/test_tool_health.py -k pending -q --no-cov` | ✅ extend |
| UI-05 | `removed`/`remove failed` in `WORDS` parity; `retained` keeps failed | unit | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_render.py -q --no-cov` | ✅ extend |
| UI-06 | `watch` install unblocks docker tweak; owned+inactive shows DRIFT; macOS no plist reads OFF; no blocking probe on the loop | unit+pilot | `uv run pytest -n auto tests/test_policy_tweaks.py tests/test_policy_linux_daemon.py tests/test_policy_daemon.py tests/test_wizard_app.py tests/test_policies_e2e.py -k "policy or policies" -q --no-cov` | ✅ extend |
| UI-07 | `a` inert; dangling pnpm shim shows `!`+reason on tier and in Doctor; link pick re-renders Doctor; evidence change requests one pass, unchanged requests none | pilot | `uv run pytest -n auto tests/test_wizard_app.py tests/test_pnpm_globals.py tests/test_tool_health.py -k "doctor or pnpm or shim" -q --no-cov` | ✅ extend |
| UI-08 | selected -> unselectable pruned on reload; `selected_ids`/`Accepted` filter | unit+pilot | `uv run pytest -n auto tests/test_tool_browser.py tests/test_catalog_tui.py -k "prune or selectable" -q --no-cov` | ✅ extend |
| R9 | grep guard: none of `OwnershipRefreshed`, `_pending_status`, `_own_script_install` (and the other deleted names) in `installer/`, comments included | unit | `uv run pytest tests/test_screen_family.py -k forks -q --no-cov` | ❌ Wave 0 |
| Layout | Uninstall/Policies/status lines <= 78 cells at 80x20; status stays on its row | pilot | `uv run pytest tests/test_layout_80x20.py -q --no-cov` | ✅ extend |
| Docs | architecture.md records Phase 21 mechanisms | unit | `uv run pytest tests/test_docs.py -q --no-cov` | ✅ extend (`_PHASE_21_REQUIRED`) |


*Per-task rows are filled by the planner (each task carries an `<automated>` verify). Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements
- [ ] `tests/screen_family.py` — held remover, pass-counting `FrozenStateService`, matrix observables per target view, call-order recorder (covers UI-01, UI-02, UI-05)
- [ ] `tests/test_screen_family.py` — call order, matrix, status lifecycle, lock, quit, forks grep (covers UI-01, UI-02, UI-05, R9)
- [ ] Rewrite `_uninstall_inputs`/`_app`/`_DoctorHost` helpers in `tests/test_wizard_app.py` once (covers the 84 + 31 call sites)
- [ ] `FrozenStateService`: support `mark_pending` and evidence in the double (`tests/state_doubles.py`)
- [ ] `_PHASE_21_REQUIRED` in `tests/test_docs.py` (written with the architecture.md change)


---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `NO_COLOR` readability of `! [drift]` and the Uninstall Health column | UI-03, UI-06 | glyph/word legibility is a human judgment | Run `uv run setup.py` in tmux at 80x20 with `NO_COLOR=1`, navigate to Uninstall and Policies only (no mutating key), `capture-pane` and read |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
