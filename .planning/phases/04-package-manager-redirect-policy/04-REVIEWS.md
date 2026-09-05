---
phase: 4
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-05T11:59:20Z
plans_reviewed:
  - .planning/phases/04-package-manager-redirect-policy/04-01-PLAN.md
  - .planning/phases/04-package-manager-redirect-policy/04-02-PLAN.md
  - .planning/phases/04-package-manager-redirect-policy/04-03-PLAN.md
  - .planning/phases/04-package-manager-redirect-policy/04-04-PLAN.md
  - .planning/phases/04-package-manager-redirect-policy/04-05-PLAN.md
models:
  opencode-plan-review: "xai/grok-4.6"
model_sources:
  opencode-plan-review: "config"
---

# Cross-AI Plan Review — Phase 4

## OpenCode Review (opencode-plan-review)

### Status: Issues Found — fix and re-invoke

### 1. Summary

Plans 04-01, 04-02, and 04-04 are executable and well grounded: parallel `REDIRECTED` next to `BANNED`, volta as a system-tier catalog entry, doctor labels without a status-enum ripple. Plan 04-03's argv scan is safe against substring `-g`, and npx dual-registration composes if apply order is held. Two false premises collapse 04-03/04-05: (1) `subprocess.run(["pnpm", …])` **does** resolve through PATH, so the pnpm wrapper intercepts `_node` and the Doctor reinstall; (2) `CommandError` is `RuntimeError`, not `OSError`, so `run_live` will not catch a failed reinstall. R-03 also drops the requirement's automatic "after pnpm updates" trigger without saying so in REQUIREMENTS.md.

### 2. Strengths

- **D-01 held in code, not slogans.** `shim_script` at `installer/guards.py:31-39` stays the 4-line print-and-exit-127 body; `REDIRECTED` / `GLOBAL_REDIRECTED` are new structures. Fail-safe order (ban -> unconditional redirect -> argv-conditional) matches how `install_shims` already overwrites only sentinel files (`guards.py:58-66`).
- **04-01 is a real vertical slice.** Fake-pnpm subprocess with `returncode == 3` is the right proof for SC#2. `real_binary` dropping `shim_dir` is the right fix for research Pitfall 3.
- **04-02 mirrors a live entry.** pnpm at `registry.toml:1448-1471` is script-on-Linux + brew; volta's `os = ["debian","arch","fedora"]` plus brew will pass `test_every_tool_resolves_at_least_one_method_on_each_platform` (`test_registry.py:327-338`, always `has_brew=True`). Recording `run_global_install` on the entry is the right D-07 artifact.
- **04-03 skip of npm/pnpm aliases is necessary.** Today `ban_alias_block` (`guards.py:91-94`) always bans `npm` in interactive shells; leaving that alias would block `npm install -g` before the PATH shim could redirect.
- **04-04 respects D-02 and architecture rule 1.** `guard_guidance` (`guidance.py:71-102`) is the single wording source; `render_guard_status` and `DoctorScreen._refresh_guidance` already consume it. Volta note gated on `status["pnpm"]` matches the writer's "only write pnpm shim when volta resolved" rule.
- **04-05 core (if PATH is fixed) matches the live-check convention.** Snapshot = `kind=="node"` in the registry; `mmdc` at `registry.toml:1646-1658` is the residual set. Footer text belongs in `VIEWS` (`ui_common.py:134-143`, currently `"enter apply"`). `setup.py` as wiring-only matches architecture rule 4.

### 3. Concerns

#### CRITICAL

- **`_node` and the 04-05 reinstall both hit the pnpm shim.** Location: 04-03 Task 1 / 04-05 Task 1; `installer/executors.py:72-74`, `installer/run.py:19-22`. Required: both `_node` and `reinstall_node_globals` invoke pnpm via a `real_binary`-resolved absolute path (shim dir removed from PATH), or the wrapper must ignore installer-spawned `pnpm add -g`. Why: research/plans claim `runner(["pnpm","add","-g",pkg])` "never resolves through the PATH-shim layer." `run_command` is `subprocess.run(cmd)` with argv[0] `"pnpm"`, which **does** search PATH. After 04-03 the wrapper lives in `~/.local/bin`, which doctor insists is first on PATH. Catalog install of `mmdc` and Doctor `r` then become `volta install @mermaid-js/mermaid-cli`, silently dropping pnpm's gated postinstall — the property 04-05 exists to keep. Tests that fake the runner never see this. **Independently verified**: `installer/executors.py:74` reads `runner(["pnpm", "add", "-g", require_str(method, "npm_pkg")])`; `installer/run.py:19-26`'s `run_command` calls `subprocess.run(cmd, check=True)` with no absolute path — this resolves through the live PATH.

- **`run_live` does not catch `CommandError`.** Location: 04-05 Task 1 action ("Let `CommandError` propagate; it is an OSError subclass path the UI layer already handles through `run_live`"); `installer/run.py:10` (`class CommandError(RuntimeError)`), `installer/ui_common.py:40-48` (catches only `OSError`). Required: `run_live` also catches `CommandError`, or the reinstall closure raises `OSError`, or a thin translator lives in `installer/` (not a screen `try/except`). Why: a failed `pnpm add -g` will crash `DoctorScreen` instead of the "failed with the error text, screen stays usable" behavior. `action_apply` works today only because PATH fix raises `OSError` from file I/O. **Independently verified**: `installer/run.py:10` — `class CommandError(RuntimeError)`, not a subclass of `OSError`; `installer/ui_common.py:40-48`'s `run_live` catches `except OSError` only. The plan's premise is factually wrong.

#### HIGH

- **R-03 is a real cut of `REQ-pnpm-global-reinstall-mitigation`, presented as settled.** Location: 04-05 objective; `.planning/REQUIREMENTS.md:40` ("reinstall it together in one invocation **after `pnpm` itself updates**"); 04-CONTEXT.md R-03. Required: REQUIREMENTS.md and ROADMAP SC#4 should state explicitly that Phase 4 ships audit + manual `r` only, and that the automatic post-update trigger is Phase 12 — not leave the requirement reading as fully resolved. Why: the failure mode is silent loss of globals; a Doctor finding helps only after the user notices `mmdc` is gone. **Independently verified**: REQUIREMENTS.md:40's literal text names the "after pnpm itself updates" trigger as part of "the requirement's original mechanism"; 04-CONTEXT.md's R-03 resolution reframes this as "the mechanism to exist... not an automatic trigger," decided autonomously (no user available to ask) rather than explicitly re-confirmed with the user at discuss-phase, which only signed off on pulling the *mechanism* into Phase 4, not on dropping the trigger.

- **04-05 adds required kwargs to `UnifiedApp` / `DoctorScreen` but does not update every constructor site.** Location: 04-05 Task 3; `wizard_app.py:801-814, 834`. Required: give `UnifiedApp` default no-op/empty-report closures for the two new keyword arguments, or add `tests/test_catalog_tui.py`, `tests/test_uninstall_e2e.py`, and `tests/test_policies_e2e.py` to `files_modified` and update all their `UnifiedApp(...)` call sites. Why: keyword-only params without defaults raise `TypeError` at every existing call site. **Independently verified**: `grep -n "UnifiedApp("` finds construction sites at `tests/test_catalog_tui.py:27`, `tests/test_uninstall_e2e.py:68,126,160`, and `tests/test_policies_e2e.py:48,113,178,217,306` — none of these three files appear in 04-05-PLAN.md's `files_modified` list.

- **`assert all(guard_status(...).values())` breaks the moment `pnpm` joins `guarded_names`.** Location: 04-03 Task 2-3; `tests/test_policy.py:53`, `tests/test_policies_e2e.py:83`. Required: those assertions must accept `pnpm is False` when volta is absent (the e2e sandbox's `which=lambda _: None`). Why: after 04-03, `guarded_names` is five keys; a volta-less apply leaves `pnpm` unshimmed; `all()` becomes `False` even though `apply()` succeeded correctly. **Independently verified**: `tests/test_policy.py:53` reads `assert all(active for active in guard_status(shim_dir).values())`; `tests/test_policies_e2e.py:83` reads `assert all(guard_status(bin_dir).values())` — both exist exactly as cited, and neither is explicitly called out for revision in 04-03-PLAN.md's task text (only a generic "update tests for the new counts" instruction).

- **Stale `BANNED["npm"]` hint after the volta split.** Location: 04-03; `guards.py:21` (`"npm": "pnpm (pnpm add -g <pkg>)"`). Required: non-global npm's exit-127 text should point at `pnpm` for local installs and `volta install` for globals — not `pnpm add -g`, which 04-03 itself redirects. Why: 04-03 reuses those two lines verbatim as the wrapper's fallback body ("byte-identical to the last two lines of `shim_script('npm')`"), so the outdated hint ships in the fallback path users actually see.

#### MEDIUM

- **Combined short flags (`npm i -gD pkg`) never set `is_global`.** POSIX `case "$arg" in -g|--global)` is an exact-token match; `-gD` falls through to the ban/passthrough branch untriggered. Uncommon, but untested by the plan's own `<behavior>` matrix.
- **A leading option-with-value before the subcommand (e.g. `pnpm --filter <ws> add -g <pkg>`, `npm --prefix <path> install -g <pkg>`) misidentifies the subcommand.** The read-only first loop treats the option's value as the first non-flag token (`subcmd`), never seeing `add`/`install`. For npm this fails toward the *safer* direction (unexpected hard block instead of redirect); for pnpm it fails toward the *less safe* direction (original argv passes through to real pnpm unmodified, silently bypassing the volta redirect for a global install). Narrow in practice (pnpm's own `--global` semantics conflict with `--filter`), but worth a one-line note in the plan or a test proving the direction of the failure for each binary.
- **Volta has no macOS script fallback.** pnpm declares `os=["macos"]` script plus brew (`registry.toml:1463-1470`); volta is brew-only on macOS. Acceptable under the `has_brew=True` test guard, but a Mac without brew cannot install the redirect target at all.
- **`collect_bin_dirs` only wires `~/.volta/bin` once the directory exists** (`shellrc.py:38-49`, `require_exists=True`). A brew-installed volta may not create that directory until the first `volta install`, so PATH repair after catalog-installing volta could be a second, unmentioned step.
- **04-05's `next_step` names the `r` key even in the CLI doctor.** `DoctorScreen._tui_guidance` (`wizard_app.py:173-186`) only rewrites steps starting with `` Run `make fix` ``, so CLI-flavored copy can leak into the TUI and vice versa for the new reinstall guidance.
- **`guard_label("npx")` stays the static "redirected to pnpm dlx" even when the on-disk body is the ban fallback** (degraded case). The honest signal is `guard_redirect_warning`, which is a separate channel a user could miss. This is explicitly the D-02 design tradeoff, not a bug, but worth a doctor-copy cross-reference.

#### LOW

- `ban_alias_block`'s `alias npx='pnpm dlx'` resolves `pnpm` through the interactive shell's PATH, while the installed PATH shim bakes an absolute path; after 04-03 the alias also routes through the pnpm wrapper (harmless, since `dlx` is not a global-install subcommand, but it is a second code path doing the same thing two different ways).
- 04-02's registry `desc` field does not itself mention the ungated-npm-scripts finding (the TOML comment and 04-04's doctor copy do, which is the user-visible surface) — consistent with the plan's own design, flagged only for completeness.

### 4. Suggestions

- Add a task (04-03 or 04-05) making `_node` and `reinstall_argv`'s runner call resolve pnpm via `real_binary(..., shim_dir=...)` before invoking it; prove it with a `tmp_path` PATH where the wrapper is first and a recording fake real-pnpm is second.
- Extend `run_live` to also catch `CommandError` (or have the reinstall function raise `OSError`), and pin the behavior with a `DoctorScreen` test that raises `CommandError` specifically, not `OSError`.
- Give `UnifiedApp` default (no-op / empty-report) closures for the two new node-globals kwargs, or add the three omitted test files to `files_modified` and update every call site.
- Update `BANNED["npm"]`'s hint text in the same 04-03 commit that ships the wrapper.
- Revise REQUIREMENTS.md / ROADMAP.md so Phase 4's manual-only trigger is stated explicitly, with Phase 12 named as the owner of the automatic post-update trigger — do not let the requirement read as fully closed.
- Add a test for `npm i -gD` (combined short flags) and for a leading value-taking option before the subcommand, documenting which direction each binary fails in.

### 5. Risk Assessment

**HIGH.** 04-01/04-02/04-04 are LOW-MEDIUM risk and ready to ship as designed. 04-03's design (wrapping the sanctioned `pnpm` binary) is correct only if internal `pnpm add -g` calls bypass the wrapper — as currently written, they do not. 04-05 then compounds that by (a) routing its own reinstall through the same wrapper and (b) crashing the TUI on `CommandError`. Together these two faults can silently route a `kind="node"` catalog tool's installs through the volta/npm-unrestricted-postinstall path without anyone intending it, and give the Doctor view a remediation key that aborts the app on failure.

**Per plan:** 04-01 LOW-MEDIUM · 04-02 LOW · 04-03 HIGH · 04-04 LOW · 04-05 HIGH

---

### Special Questions (requested by the orchestrator)

**1. Substring `-g` / unmodified pnpm argv (04-03 safety-critical trace)**

No substring false positive; non-triggering pnpm argv is unmodified. POSIX `case` matches the whole token, not a substring — `pkg-g`, `--filter=-g`, `-global`, `-gD` do not set `is_global`. The rotate loop that rewrites `"$@"` sits inside the `is_global=1` branch matched on `subcmd`, and that branch always `exec`s or `exit`s; the first (detection) loop only reads `"$@"` and never mutates it. Confirmed: `pnpm add typescript`, `pnpm list -g`, `pnpm run build --watch` all reach the fallback with argv unchanged; only `pnpm add -g <pkg>` (exact token) triggers the rotate-and-redirect branch. The actual safety-critical gap is not substring detection — it is `_node`/the Doctor reinstall resolving `"pnpm"` through PATH and hitting this same wrapper from inside the installer (CRITICAL finding above). Combined short flags (`-gD`) are a smaller, separate miss (MEDIUM).

**2. npx in both `BANNED` and `REDIRECTED` (04-01 composability trace)**

Composes cleanly if apply order is held; no duplicate or inconsistent `guard_status` keys. `guarded_names() = tuple(dict.fromkeys((*BANNED, *REDIRECTED, *GLOBAL_REDIRECTED)))` dedupes, so `npx`/`npm` appear once and `guard_status` stays `dict[str, bool]`. `is_our_shim` widens to `SHIM_SENTINEL or REDIRECT_SENTINEL`, so `remove_shims` can tear down either body under one ownership concept. The one load-bearing fact: `install_shims` still iterates `BANNED` alone and will overwrite a live redirect npx shim with a ban body (the widened `is_our_shim` still returns True for it) — this is safe *only* because `ban_policy._apply`/`app.run_guard` always call `install_shims` before `install_redirect_shims`. Calling `install_shims` in isolation would silently regress a live npx redirect back to a hard block; this ordering dependency is documented in the plan's `key_links` but is not itself asserted by a test that calls the writers out of order. Not a key-set bug — a documented, correctly-ordered composition, with one untested inversion case.

**3. R-03 vs. "after pnpm itself updates" (04-CONTEXT.md fidelity check)**

A real scope cut, not a faithful reading — and it should be flagged in REQUIREMENTS.md/ROADMAP.md, not only in CONTEXT.md. `REQUIREMENTS.md:40`'s text for `REQ-pnpm-global-reinstall-mitigation` still says snapshot-and-reinstall "after `pnpm` itself updates." R-03's resolution moves the *mechanism* into Phase 4 and correctly avoids inventing a dependency on Phase 12's not-yet-built update-action infrastructure — that half is sound engineering judgment. But it does not replace the trigger with "the user notices and presses `r` in Doctor"; it drops the trigger has no replacement in this phase. The requirement's whole reason to exist is that pnpm's global-package loss on self-update is *silent* — a manually-invoked remediation provides no safety net unless the user already suspects something is missing. This was decided autonomously ("no user available to ask") rather than reconfirmed with the user, and the user's own discuss-phase sign-off was for pulling the mechanism into Phase 4, not for narrowing its trigger. Recommend: Phase 4 ships mechanism + audit + explicit apply; REQUIREMENTS.md and ROADMAP.md should say so explicitly, with the automatic "after pnpm updates" trigger named as Phase 12's remaining piece — so a later milestone audit does not read the requirement as fully closed.

---

## Consensus Summary

Only one reviewer lane (`opencode-plan-review`, backed by `xai/grok-4.6`) ran this cycle, cross-checked directly against the live repository by the orchestrating session (file:line verification of every CRITICAL and HIGH claim below — `installer/executors.py:72-74`, `installer/run.py:10,19-26`, `installer/ui_common.py:40-48`, `tests/test_policy.py:53`, `tests/test_policies_e2e.py:83`, `UnifiedApp(...)` call sites in `tests/test_catalog_tui.py`/`tests/test_uninstall_e2e.py`/`tests/test_policies_e2e.py`, and `.planning/REQUIREMENTS.md:40`). Every CRITICAL and HIGH concern was independently confirmed against on-disk source, not merely restated from the reviewer's own text.

### Agreed Strengths
- Plans 04-01, 04-02, and 04-04 are sound, source-grounded, and low risk: the `REDIRECTED`/`GLOBAL_REDIRECTED` mechanisms sit genuinely parallel to `BANNED` with no shape change to `shim_script`/`guard_status`, the `volta` registry entry mirrors existing `tier="system"` precedent with matching test coverage, and the doctor label rewrite honors D-02's "no new status enum" constraint end to end.
- The argv-conditional pnpm/npm wrapper's core detection logic (04-03) is safe against substring/false-positive `-g` matches, and every non-triggering pnpm invocation genuinely reaches the real binary with unmodified argv — the mechanism itself is correctly designed.

### Agreed Concerns (highest priority — block execution per ONESHOT-RULES Rule 11)
1. **The PATH-shim wrapper `pnpm` from 04-03 will intercept the installer's own internal `pnpm add -g` calls** (`installer/executors.py`'s `_node` executor and 04-05's reinstall mechanism), silently rerouting `kind="node"` catalog installs and Doctor reinstalls through `volta install` instead of real pnpm — defeating the very security property (pnpm's gated postinstall scripts) 04-05 exists to preserve for the residual set.
2. **04-05's plan text asserts `CommandError` is an `OSError` subclass that `run_live` already handles; it is a `RuntimeError` subclass and is not caught**, so a failed pnpm-global reinstall will crash the Doctor screen instead of degrading gracefully.
3. **04-05 introduces new required `UnifiedApp` constructor parameters without updating three test files** (`tests/test_catalog_tui.py`, `tests/test_uninstall_e2e.py`, `tests/test_policies_e2e.py`) that construct `UnifiedApp` directly — these are absent from the plan's `files_modified` list and will fail with `TypeError` once the change lands.
4. **Two existing test assertions** (`tests/test_policy.py:53`, `tests/test_policies_e2e.py:83`) **assume every guarded name is active and will fail** once `pnpm` joins `guarded_names()` in a volta-less sandbox — not explicitly called out for revision in 04-03's task text.
5. **R-03's manual-only scope for the pnpm-global snapshot-reinstall mechanism is a genuine reduction of `REQ-pnpm-global-reinstall-mitigation`'s literal text** (which specifies an automatic trigger "after `pnpm` itself updates"), decided autonomously and not yet reflected as a partial/deferred status in REQUIREMENTS.md or ROADMAP.md — risking the requirement being read as fully closed when the actual failure mode (silent data loss on pnpm self-update) has no automatic safety net until Phase 12.
6. **`BANNED["npm"]`'s hint text becomes stale** once 04-03 ships: it still tells a blocked non-global npm user to run `pnpm add -g <pkg>`, an invocation 04-03 itself redirects to volta.

### Divergent Views
None — single reviewer lane this cycle; no cross-reviewer disagreement to reconcile. The orchestrating session's independent source verification corroborates every CRITICAL/HIGH item rather than diverging from it.

---

# Cross-AI Plan Review — Phase 4 — Cycle 2 (post-fix verification)

**Reviewed:** 2026-09-05 · **Reviewer:** `opencode-plan-review` (opencode CLI, model `xai/grok-4.6`) · **Plans reviewed:** 04-01-PLAN.md .. 04-05-PLAN.md, post-fix revision committed at `bbd44c1` (on top of cycle-1 review commit `c3211ba`).

Cycle 1 found 2 CRITICAL and 6 HIGH concerns (see the "Cross-AI Plan Review — Phase 4" section above). A gsd-planner agent revised all 5 PLAN.md files to address each with mechanism-level changes. This cycle checks whether those fixes actually close the gaps, independently re-verified against live repo source by the orchestrating session (not just restated from the reviewer's own text).

## OpenCode Review (opencode-plan-review)

### Status: Approved — cycle-1 CRITICAL/HIGH closed; no new blockers

### Cycle-1 CRITICAL/HIGH disposition

| Finding | Verdict | Evidence |
|---|---|---|
| `_node` / 04-05 reinstall hit the pnpm wrapper via PATH | **FIXED** | 04-03 Task 1: `real_pnpm` + `_node` absolute path + `ExecutorError` on miss; 04-05 Task 1: `reinstall_argv` requires absolute `pnpm=`, default `resolve_pnpm=real_pnpm`. Live hole confirmed still present pre-fix at `installer/executors.py:74` + `installer/run.py:19-22` (`subprocess.run(cmd)`) — the only production `["pnpm", …]` call site. |
| `run_live` misses `CommandError` | **FIXED** | `CommandError` is `RuntimeError` (`installer/run.py:10-16`), not `OSError`. `run_live` today is `except OSError` only (`installer/ui_common.py:40-48`) — confirmed live. 04-05 Task 3 widens to `except (OSError, CommandError)`; the Doctor regression test is required to raise `CommandError` specifically, not `OSError`. |
| R-03 vs REQUIREMENTS.md "after pnpm updates" | **FIXED** | 04-05 Task 4 edits `REQUIREMENTS.md`'s body + Traceability row to `Partial` across Phase 4/12, and `ROADMAP.md` SC#4 states "manual trigger only" with Phase 12 named as owner of the automatic trigger. Confirmed REQUIREMENTS.md:40 still carries the un-narrowed text pre-fix (expected — task not yet executed). |
| `UnifiedApp` required kwargs break 9 existing call sites | **FIXED** | 04-05 Task 3: the two new kwargs default to `None`, substituted with an empty report / no-op; `DoctorScreen` keeps them required; the three previously-omitted test files (`tests/test_catalog_tui.py`, `tests/test_uninstall_e2e.py`, `tests/test_policies_e2e.py`) stay unedited and an acceptance criterion runs them unmodified. |
| `assert all(guard_status(...).values())` breaks once pnpm joins `guarded_names()` | **FIXED** | 04-03 Task 4 names `tests/test_policy.py:53` and `tests/test_policies_e2e.py:83` explicitly, replaces the blanket assertion with a two-sandbox (volta-present / volta-absent) case, and an acceptance criterion greps the blanket `all(...)` form out of both files. |
| Stale `BANNED["npm"]` hint recommends an invocation this phase itself intercepts | **FIXED** | 04-03 Task 2 rewrites the hint in the same task that ships the wrapper fallback body; acceptance criterion asserts `'volta install' in hint` and `'add -g' not in hint`. Confirmed live text (`installer/guards.py:21`) still carries the stale form pre-fix. |

### Mandatory focus questions

**1. Does `real_pnpm`/`_node` close the self-interception hole?** Yes, for every installer-owned `pnpm add -g` call after this phase ships. Verified: today's only production bare-name call is `installer/executors.py:74`, routed through `subprocess.run(cmd)` (`installer/run.py:19-22`), which is PATH-resolved — confirming the cycle-1 CRITICAL premise was correct. After 04-03 Task 1, `_node` resolves `argv[0]` via `real_pnpm()`, whose default `shim_dir` is `installer.locations.bin_dir(None)` (`~/.local/bin`) — excluded from the search, with sentinel-carrying results refused regardless of shim state (not-yet-installed / installed / stale all resolve to either the real binary further down PATH, or `ExecutorError`/`CommandError` — never a silent bare-name fallback). 04-05's reinstall reuses the same resolver. No other `runner(["pnpm", ...])` call site exists in `installer/`.

Caveat (MEDIUM, independently confirmed): the plan's Task 1 test-authoring instructions (04-03-PLAN.md lines 165-169) describe the wrapper-first regression case as building a `tmp_path` bin dir on `PATH`, without explicitly stating that `HOME` must also be monkeypatched so `bin_dir(None)` resolves to that same directory. Since `_node()` calls `real_pnpm()` with no explicit `shim_dir` override, a regression test that only manipulates `PATH` (without pointing `HOME` at the same tmp dir) would not actually exercise the production shim-exclusion default — the planted "wrapper" would just be found via ordinary PATH search, sentinel check never triggered. `tests/test_node_install_e2e.py:31` already monkeypatches `HOME` this way; `tests/test_executors.py`'s existing `test_node_runs_pnpm_add_global_never_bare_npm` (lines 124-128) does not. This is a test-specification ambiguity, not a mechanism defect — the design is sound, but the plan text should say explicitly to monkeypatch `HOME` for this specific regression case.

**2. Is the `run_live`/`CommandError` fix correct?** Yes. Verified hierarchy: `class CommandError(RuntimeError)` (`installer/run.py:10`); `run_command` already converts a raw `OSError` into `CommandError` (`installer/run.py:25-26`), so today's `except OSError`-only `run_live` never actually sees a failed `Runner` call surfaced as `OSError` — confirming the cycle-1 CRITICAL premise. The plan's fix (`except (OSError, CommandError)`) is correct: the PATH-repair action still raises plain `OSError` from file I/O, while a failed reinstall raises `CommandError` — both paths now degrade gracefully instead of crashing the screen. The plan's regression test is specified to raise `CommandError` specifically (not `OSError`), which is the correct proof — an `OSError`-only test would have passed even against the unfixed code and proven nothing.

**3. Does the pnpm argv-detection wrapper leave non-`-g`/`--global` invocations unmodified?** Yes for the full requested matrix, with two small, explicitly-documented and accepted gaps. POSIX `case` matching is whole-token, so `pnpm add typescript`, `pnpm add -D typescript`, `pnpm list -g`, `pnpm run build --watch`, and `pnpm add typescript --filter=-g` all pass through unmodified (no false positive on substring `-g`). `pnpm add -gD typescript` / `npm i -gD` correctly trigger the volta redirect via the added `-[!-]*` cluster-scan arm (closing the cycle-1 MEDIUM finding). Two accepted, explicitly-documented residual gaps: (a) `pnpm --filter <ws> add -g <pkg>` — a leading value-taking option before the subcommand causes a false negative (passthrough, bypassing the volta redirect) — accepted because it still keeps the install under pnpm's gated model, not a security regression; (b) any single-dash token containing the letter `g` as a substring (e.g. a hypothetical `-registry` flag) would set `is_global` via the same cluster-scan arm — a narrow false-positive surface, LOW severity, same family as the accepted leading-option gap. Neither is a HIGH-severity regression; both are pre-existing, catalogued MEDIUM/LOW items from cycle 1's own review, not new problems introduced by the fix.

**4. Does R-03's manual-only scope match D-08?** Yes, faithfully. D-08's literal "after `pnpm` itself updates" automatic trigger is explicitly deferred to Phase 12, not silently dropped: 04-05 Task 4 writes the split into `REQUIREMENTS.md` (row becomes `Partial`, spanning Phase 4 + Phase 12) and `ROADMAP.md` (Phase 4 SC#4 states "manual trigger only"; Phase 12's section is extended to name the automatic trigger it still owes). The Traceability checkbox is deliberately left unchecked. This closes the gap cycle-1 flagged (the narrowing existed only in CONTEXT.md's R-03, not in the tracked requirement text) without overstating or understating D-08's actual scope.

### Concerns

#### CRITICAL
None.

#### HIGH
None open. All six cycle-1 blocking items (2 CRITICAL + 4 HIGH... actually 2 CRITICAL + 4 HIGH per cycle-1's severity split, all 6 total) verified FIXED above.

#### MEDIUM
- **Test-authoring ambiguity for `_node`'s wrapper-first regression case (04-03 Task 1).** The plan's test-building instructions do not explicitly require monkeypatching `HOME` so the planted wrapper lands at `real_pnpm()`'s actual default `shim_dir` (`installer.locations.bin_dir(None)`). Without that, the regression test could be written in a way that never exercises the sentinel-exclusion logic it's meant to prove. Fix: state explicitly in Task 1's action text that the wrapper-first case must monkeypatch `HOME` to a `tmp_path`, mirroring `tests/test_node_install_e2e.py:31`.
- **Doctor reinstall preview when `real_pnpm()` resolves to `None` is unspecified (04-05 Task 3, `_refresh_body`).** `reinstall_argv` requires `pnpm: str` (non-optional) and only raises `ValueError` on an empty entry set; the case of a non-empty residual set with no resolvable real pnpm is handled correctly for the actual keypress (raises `CommandError`, per Task 1), but the *preview* rendering path is not specified for this state — it's unclear whether `_refresh_body` would call `reinstall_argv(entries, pnpm=None)` (a type violation) or otherwise mishandle it. Fix: `_refresh_body` should show an explicit "pnpm not resolvable" line rather than calling `reinstall_argv` with a non-string value when `real_pnpm()` returns `None`.

#### LOW
- Two stale `ROADMAP.md` sentences that Task 4 does not touch: the Phase 12 list entry still says it "unblocks Phase 5's pnpm-reinstall mitigation" (`ROADMAP.md:67`, stale since the requirement moved to Phase 4), and the Phase 5 section's note still claims `REQ-pnpm-global-reinstall-mitigation` is "resolved there via the Volta redirect" (`ROADMAP.md:163`), which overstates the actual (partial, manual-trigger-only) outcome given the residual `mmdc` set (`installer/registry.toml:1646-1658`). Neither blocks execution; both are worth a follow-up edit alongside or shortly after Task 4.
- `DoctorScreen`'s state-field naming for the reinstall action (separate `globals_done`/`globals_error` vs. reusing PATH-fix's `applied`/`error`) is under-specified; reuse would incorrectly block pressing `r` after a PATH-fix apply. Recommend explicit distinct field names in the plan text.
- The `-[!-]*`/`*g*` cluster-scan false-positive surface (e.g. a hypothetical `-registry` flag) is the same accepted-risk family as the leading-option-value gap; no action required beyond what's already documented.

### Suggestions
- In 04-03 Task 1's action text, add `monkeypatch.setenv("HOME", str(tmp_path))` to the wrapper-first regression case so it exercises `real_pnpm()`'s actual default `shim_dir`.
- In 04-05's `_refresh_body` spec, add an explicit branch for `real_pnpm() is None` with a non-empty residual set, showing a "pnpm not resolvable" line instead of calling `reinstall_argv` with a non-string value.
- Name the Doctor reinstall's screen-state fields separately from the PATH-fix's `applied`/`error` (e.g. `globals_done`/`globals_error`).
- Optionally, have Task 4 also correct the two stale `ROADMAP.md` sentences identified above while it's already editing that file.

### Risk Assessment

**LOW.** Cycle-1's HIGH overall risk was driven by the wrapper intercepting the installer's own `pnpm add -g` calls and a TUI crash on `CommandError` — both now designed against, and verified against, live source (`installer/run.py:10,19-26`, `installer/executors.py:74`, `installer/ui_common.py:40-48`). Residual risk is confined to two test/UI underspecifications (test-setup ambiguity, an unspecified preview-degradation branch) that do not reopen the security hole cycle-1 identified, plus minor stale-documentation cleanup.

**Per plan:** 04-01 LOW · 04-02 LOW · 04-03 LOW-MEDIUM · 04-04 LOW · 04-05 LOW-MEDIUM

---

## Independent Verification Notes (orchestrating session)

Every CRITICAL/HIGH disposition and both mandatory-focus-question caveats above were independently cross-checked directly against live repository source (not merely restated from the reviewer's text):
- `installer/executors.py:74` — confirmed pre-fix bare `runner(["pnpm", "add", "-g", ...])`, the sole production call site.
- `installer/run.py:10,19-26` — confirmed `CommandError(RuntimeError)` and `run_command`'s `subprocess.run`/PATH-resolution behavior, and that `run_command` converts a raw `OSError` into `CommandError` before it ever reaches `run_live`.
- `installer/ui_common.py:40-48` — confirmed `run_live` catches `OSError` only, pre-fix.
- `installer/guards.py:21` — confirmed stale `BANNED["npm"]` hint text, pre-fix.
- `installer/locations.py:28-32` — confirmed `bin_dir(None)` default (`~/.local/bin`), the basis for the MEDIUM test-ambiguity finding.
- `tests/test_executors.py:124-128` — confirmed the existing `test_node_runs_pnpm_add_global_never_bare_npm` predates the fix and does not itself monkeypatch `HOME`.
- `.planning/REQUIREMENTS.md:40` and `.planning/ROADMAP.md:67,163` — confirmed current (pre-Task-4) text, and the two stale ROADMAP sentences the LOW finding names.
- 04-03-PLAN.md and 04-05-PLAN.md task/action/acceptance-criteria text — confirmed each cycle-1 CRITICAL/HIGH finding maps to a real, specific task/test/acceptance-criterion change, not a documentation-only edit.

No CRITICAL or HIGH concern remains open. Two MEDIUM and three LOW items are genuine, independently-confirmed, actionable-but-non-blocking gaps (test-authoring ambiguity, an unspecified UI-preview branch, and stale cross-references in ROADMAP.md).

## Consensus Summary (Cycle 2)

Single reviewer lane this cycle (`opencode-plan-review`, `xai/grok-4.6`), cross-verified by the orchestrating session as detailed above. All 2 CRITICAL and 6 HIGH concerns from cycle 1 are confirmed fixed with real mechanism changes (a shim-excluding `real_pnpm` resolver reused by both the catalog installer and the Doctor reinstall; a widened `run_live` exception boundary; explicit `UnifiedApp` keyword defaults; named, individually-replaced test assertions; a rewritten stale hint; and explicit partial-status tracking in REQUIREMENTS.md/ROADMAP.md for R-03). Two new MEDIUM findings and three LOW findings surfaced during this cycle's fix-verification pass — all are test-specification or documentation-completeness gaps, none reopen a security or correctness hole.

CYCLE_SUMMARY: current_high=0 current_actionable=5
