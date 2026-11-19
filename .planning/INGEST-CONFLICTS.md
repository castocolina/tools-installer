## Conflict Detection Report

Batch 5 (update automation), merge mode. Checked against PROJECT.md, REQUIREMENTS.md, ROADMAP.md and the 24.2 SPEC and CONTEXT.

### BLOCKERS (0)

None. No ADRs in the batch, no UNKNOWN classifications, and the cross-ref graph has no cycles.

### WARNINGS (2)

[WARNING] Daily check reverses the 24.2 notification cut
  Found: .planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md adds desktop notifications (notify-send, osascript) and says it "reverses that cut"
  Impact: .planning/milestones/v0.50.0-phases/24.2-schedules-view/24.2-SPEC.md:179 and 24.2-CONTEXT.md:43 list "A desktop notification for failed runs" as out of scope. The old cut covers failed runs; the new feature covers an updates-available check. The two are close enough that the scope line needs an explicit amendment so the cut is not silently overridden. Owner request (2026-11-17) and the phase 33-35 decision (2026-11-19) authorize the change.
  → Record the reversal in the phase 34 SPEC/CONTEXT as an amendment to 24.2's out-of-scope list; settle OQ-NOTIFY-1 (this check only, or failed runs too).

[WARNING] update-all conflicts with the 24.2 default-on rule
  Found: .planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md wants an `update-all` row that is off by default (per-schedule `default_on=False`)
  Impact: 24.2-SPEC.md:61 (SCHED-01) says a schedule is on by default when its target is installed, and PROJECT.md records Schedules as a closed table seeded on. An off-by-default row is an exception to that rule. The todo acknowledges this; it is not a contradiction of a locked ADR, but the engine needs an amendment.
  → Amend SCHED-01 in the phase 35 SPEC to allow per-row `default_on=False`; keep the "user's decision is never overridden" half of the rule.

### INFO (5)

[INFO] Doctrine check: no new Policies knobs
  Note: the daily check and update-all are Schedules rows (24.2 D-01), and the bot is CI-only. The auto-update todo says outright that update-all is not a Policies row. PROJECT.md line 111 and REQUIREMENTS.md out-of-scope are respected.

[INFO] Doctrine check: zero sudo
  Note: update-all reuses `update_refusal` and `HOMEBREW_NO_SUDO` (installer/run.py:50) and children run with `stdin=DEVNULL`. Native and os-package owners are refused, not run with sudo. See AUTOUPD-04. No source proposes a sudo path.

[INFO] Doctrine check: protected main and fast-forward flow
  Note: the bot design pushes only a `bot/registry-<date>` branch and the owner lands it by fast-forward (BOT-03). Auto-land after green CI (OQ-BOT-3) would be an unreviewed push to protected main (enforce_admins) and would conflict with PROJECT.md line 158; the recommended default (owner lands) complies. Option (b), `workflow_dispatch` on `ci.yml`, touches CI outside the docs-only fast pass.

[INFO] Doctrine check: never mutate the developer host
  Note: none of the three todos asks to run on the host. Update-all e2e must run in a disposable container, which has no systemd user manager (AUTOUPD-08). The real macOS check for phases 34 and 35 is an owner-assigned checkpoint, not an agent host run.

[INFO] Order agreement and open questions
  Note: the research's suggested order (bot, daily check, auto-update) matches the owner's phase 33-35 order. Every "Owner decisions" item is recorded as an open question in .planning/intel/context.md (OQ-BOT-*, OQ-NOTIFY-*, OQ-AUTOUPD-*), not as a locked decision and not as a conflict. All four docs are type DOC (manifest-declared), so the proposed BOT/NOTIFY/AUTOUPD requirement IDs are synthesizer proposals, not PRD-sourced requirements.
