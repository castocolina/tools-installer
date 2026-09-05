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
