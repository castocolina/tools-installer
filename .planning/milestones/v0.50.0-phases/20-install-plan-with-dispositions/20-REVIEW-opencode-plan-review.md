# Phase 20 code review (opencode, router-env/my-plan-review)

## Findings

### OC-01 [HIGH] Missing native-package tools can run `sudo`
- File: `installer/session.py:637`, `installer/resolve.py:75`, `installer/executors.py:448`
- Problem: On mutable Fedora, Debian, or Arch, a missing tool with a native-package method is planned as `will install`. Execution can then reach `sudo dnf`, `sudo apt-get`, or `sudo pacman`, contrary to the phase’s zero-sudo requirement. The registry includes native-only examples such as `jq`.
- Fix: Refuse privilege-requiring methods in the install path, including fallback methods, and give the row a non-escalating disposition or handoff.

### OC-02 [HIGH] Headless runs do not settle skill-pack state
- File: `installer/app.py:118`, `installer/version_status.py:1226`, `installer/catalog_tui.py:398`
- Problem: Headless calls `refresh()` but not `refresh_skills()`. Packs with status probes remain `CHECKING`, so `--all --yes` reports a state-check failure and marks every planned row `not attempted`. The TUI starts both refresh workers.
- Fix: Complete the skill probe as well as the ordinary refresh before headless builds the plan.

### OC-03 [HIGH] Declining the headless confirmation can still write files
- File: `installer/app.py:119`, `installer/app.py:146`, `installer/version_status.py:1279`, `installer/version_status.py:1707`
- Problem: Refresh happens before “Run this plan?”. It can adopt an existing binary, retire a receipt, and save the version cache. Answering No can therefore produce “Cancelled; nothing was changed” after persistent state changed.
- Fix: Make pre-confirmation refresh read-only, deferring those writes until consent, or explicitly change the consent boundary and cancellation claim.

### OC-04 [MEDIUM] Headless post-run failures are missing from its exit rule
- File: `setup.py:1528`
- Problem: After printing row outcomes, headless performs PATH wiring and verification outside any run-error collection. If either raises, the command bypasses its outcome-based exit and troubleshooting path; the TUI records these failures separately.
- Fix: Capture and report headless run-level errors and include them in the final exit status.

### OC-05 [MEDIUM] Container e2e accepts unsuccessful summaries
- File: `scripts/container-e2e-verify.sh:372`, `scripts/container-e2e-verify.sh:478`
- Problem: The parser recognizes `crashed` and `not attempted`, but the acceptance counters omit them. A run reporting those outcomes can pass the summary gate; exit code 1 is also permitted. The pass2 gates repeat this omission at lines 525–532 and 563–571.
- Fix: Require a valid summary for each install step and fail the gate on either outcome.

### OC-06 [MEDIUM] A handoff-only row triggers post-run mutations
- File: `installer/session.py:252`, `installer/execute_screen.py:670`, `setup.py:1528`
- Problem: A `host_setup` method can return `manual` instructions without installing anything, but `manual` counts as `ran_anything`. Both routes then run PATH wiring and verification, and the TUI also triggers terminal sync on close. That contradicts “nothing ran” for a handoff-only plan.
- Fix: Track whether a row actually performed a mutation or command; do not treat every `manual` outcome as proof that it did.

### OC-07 [MEDIUM] A successful TUI retry retains an old run failure
- File: `installer/wizard_app.py:3002`, `setup.py:1302`
- Problem: Outcomes are replaced per tool on retry, but `run_errors` is only appended to. If PATH wiring fails on one run and succeeds on the next, the latest row can be `done` while the session still exits 1 for the old error.
- Fix: Replace run-level errors at the start or completion of each new run, in step with the outcome retry rule.

### OC-08 [LOW] Failed reconfiguration shows the wrong failure reason
- File: `installer/render.py:150`, `installer/session.py:446`
- Problem: A failed configuration step stores its error in `RowOutcome.detail`, but the finished-row renderer looks only for install or update exceptions. A concrete failure such as `enable plugin: permission denied` appears as `failed — no method succeeded`.
- Fix: Use `outcome.detail` when no exception is present, before the generic fallback.

## Summary

**3 HIGH, 4 MEDIUM, 1 LOW.** Fix the native-method privilege path first, then make headless settle the same state as the TUI, then move pre-confirmation writes behind consent. No files were edited or installs run. Live TUI and container runs were not checked; the e2e finding is based on its parser and acceptance conditions.
