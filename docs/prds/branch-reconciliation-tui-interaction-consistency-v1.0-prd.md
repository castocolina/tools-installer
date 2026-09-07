# Branch Reconciliation: `feat/tui-interaction-consistency` — Product Requirements Document

## Requirements Description

### Background

On 2026-09-06, `origin/feat/tui-interaction-consistency` was found diverged from
this machine's local branch of the same name: **ahead 5, behind 83** relative to
each other. Investigation (`git merge-base`, ancestry checks, and reading
`origin`'s own `.claude/handoffs/2026-09-03-tui-consistency-recovery.md`) showed
this is not a squash or rebase artifact — it is an **accidental force-push**:

- Another machine's session lost its prior conversation history, found a stale
  checkout at commit `3e3cdc8` (2026-06-21) with ~1200 uncommitted lines on top
  of it, committed that work as 5 commits, and pushed — overwriting the real,
  already-published history between `3e3cdc8` and this machine's `75fa80b`
  (2026-07-28), 83 commits deep.
- That overwritten history already contains the *same* feature the 5 origin
  commits re-implement from scratch: the numbered wayfinding nav, per-view mode
  badges, the two-zone footer, the uninstall confirm modal, and the
  doctor/catalog refresh (PRD `ui-doctor-catalog-refresh-v1.0-prd.md`). Local's
  version is the one that was actually reviewed and pushed first; origin's is a
  stale re-derivation.
- Local commits `56d6b36` (`chore(repo): remove tracked SDD artifacts`) and
  `384be47` (`chore(repo): remove tracked review artifact`) deliberately
  untracked GSD/superpowers working files. Origin's stale branch re-adds
  `.planning/config.json` and `.superpowers/sdd/task-{1,3,4}-report.md` —
  a direct violation of that convention, consistent with the other machine
  currently running a GSD-based workflow.

The other machine is still actively working a **12-phase GSD workflow** on this
same branch. Reconciling now would either discard in-progress remote work or
require the other session to rebase mid-flight. **Decision: wait until all 12
phases are pushed to `origin`, then re-run this analysis once, deliberately,
against the full result** — not phase-by-phase, since the divergence shape can
still change until the last phase lands.

### Goals

- Preserve 100% of local's 83-commit history as the canonical line for
  `feat/tui-interaction-consistency` — it is the complete, already-reviewed
  implementation.
- Do not lose the small set of genuinely new, non-duplicate pieces that exist
  only on the stale `origin` branch.
- Do not reintroduce GSD/superpowers scratch artifacts that the project has
  already decided not to track.
- Keep a safety net (backup branches) until reconciliation is confirmed
  complete and origin has been repointed.

### Non-goals

- Not attempting to merge the two histories commit-by-commit — the 5 origin
  commits duplicate architecture already on local; a textual merge would
  produce duplicate/conflicting implementations of the same feature even where
  Git reports no conflict markers.
- Not deciding *now* how the other machine's still-in-progress GSD work will be
  folded in — that depends on what it produces and is out of scope until it
  lands.

## Investigation Findings

### Backups taken (2026-09-06, local only, not pushed)

- `backup/feat-tui-interaction-consistency-2026-09-06` = local HEAD (`75fa80b`)
  at time of investigation.
- `backup/origin-feat-tui-interaction-consistency-2026-09-06` = `origin`'s tip
  (`581c097`) at time of investigation.

### Rescue / drop catalog (origin-only files, as of `581c097`)

| Item | Verdict | Why |
|---|---|---|
| `installer/enums.py` (StrEnum: Priority/Audience/Category/InstallStatus/UninstallState/Severity) | **Rescue** | Local has no StrEnum-based state classes yet; still loose string/TOML literals. Genuine quality improvement, not a duplicate. |
| `installer/helper_assets/wait_time.py` + `tests/test_wait_time.py` | **Rescue** | Replaces the raw bash busy-loop countdown in local's `installer/tweaks.py` (`_COUNTDOWN_BODY`) with a tested Python helper. |
| `scripts/prune-user-tmpdir.sh` | **Rescue** | Standalone utility, no local equivalent, low risk to adopt as-is. |
| `.planning/config.json` | **Policy violation** | GSD scaffold file; project already excludes this class of artifact. |
| `.superpowers/sdd/task-1-report.md`, `task-3-report.md`, `task-4-report.md` | **Policy violation** | Matches `.gitignore` exclusion and commits `56d6b36`/`384be47` intent. |
| The 5 "feat" commits' architecture (nav registry, `run_live`, wayfinding header/tabs, bracketed-digit nav, mode badges, doctor/catalog refresh) | **Drop** | Confirmed already present, and further along, in local's `installer/ui_common.py` / `catalog_tui.py` / `status.py` history. |
| `.claude/handoffs/2026-09-03-tui-consistency-recovery.md` | **Drop (keep as reference only)** | Historical session artifact; useful context, not something to merge into the working tree. |
| `AGENTS.md` (repo-root Codex/CLAUDE.md mirror) | **Drop** | Local relies on the shared global `~/.agents/AGENTS-TOOLING.md` instead. Also see Backlog below — that global file is itself slated for retirement. |
| `docs/superpowers/2026-06-23-tui-consistency-status.md` | **Drop** | Status doc for work already superseded by local's real, further-along implementation. |

## Reconciliation Plan (deferred until the other machine's 12-phase GSD work lands)

1. **Wait** for all 12 phases of the other machine's GSD workflow to complete
   and push to `origin` — do not start reconciliation mid-way through the
   phases.
2. **Re-diff** `origin` against local `HEAD` at that point — the divergence
   shape may change once 12 phases of new commits land on top of the stale
   base, and the rescue/drop catalog above must be re-verified, not assumed.
3. **Cherry-pick, not merge**, the three rescue items (`installer/enums.py`,
   `helper_assets/wait_time.py` + test, `scripts/prune-user-tmpdir.sh`) onto
   local's line, adapting them to local's current module layout since two
   months of local refactors (one-registry architecture, receipts, SDKMAN
   work) have moved code around since the stale base.
4. **Verify** `make validate && make test` green after the cherry-picks.
5. **Force-push** local's reconciled branch to `origin`, overwriting the stale
   line — only after confirming with the other machine's owner that its
   in-progress work is either captured in the re-diff or intentionally
   superseded.
6. **Delete** the two backup branches once the force-push is confirmed correct
   and pulled cleanly on both machines.

## Backlog (not in scope for this reconciliation)

- Retire the shared global `~/.agents/AGENTS-TOOLING.md` guidance from this
  repo's CLAUDE.md include chain once that responsibility moves to
  `../ai-kit`. Track separately; do not fold into this reconciliation.

## Open Questions

1. Does the other machine's current GSD-based session know it force-pushed
   over 83 commits? If not, it should be told before it pushes again.
2. Should the three rescue items get their own small feature branch/PR, or
   land as a single `chore` commit on `feat/tui-interaction-consistency`
   after reconciliation?

---

**Document Version:** 1.0
**Created:** 2026-09-06
**Status:** Investigation complete. Reconciliation deliberately deferred —
waiting on the other machine's in-progress 12-phase GSD workflow before
touching `origin`. No destructive git operations have been performed; two
local-only backup branches exist as a safety net. **Next action trigger:**
re-open this PRD and redo the divergence analysis once all 12 phases are
pushed to `origin/feat/tui-interaction-consistency`.
