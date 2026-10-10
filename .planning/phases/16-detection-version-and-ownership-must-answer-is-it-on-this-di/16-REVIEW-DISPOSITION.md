---
phase: 16
review: 16-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "A second PATH-writer guard of the same rc file is refused forever with a misleading message"
  - id: IN-01
    severity: info
    disposition: fixed
    title: "Heredoc body lines are treated as guardable PATH writers"
  - id: IN-02
    severity: info
    disposition: fixed
    title: "A one-shot `PATH=... cmd` prefix is reported as a persistent writer"
  - id: IN-03
    severity: info
    disposition: skipped
    title: "Skill-pack matches can hit a same-named entry from another source"
  - id: IN-04
    severity: info
    disposition: skipped
    title: "Ownership is attributed from bare file presence at the declared `bin_dir`"
  - id: IN-05
    severity: info
    disposition: skipped
    title: "Keg-only brew probe stats `opt/<formula>/bin/<cmd>` for every formula"
  - id: IN-06
    severity: info
    disposition: fixed
    title: "`path_scan_rc_paths` can raise on an unreadable `~/.bashrc.d` entry"
  - id: IN-07
    severity: info
    disposition: skipped
    title: "`dangling_shim` keys on package names only"
  - id: IN-08
    severity: info
    disposition: skipped
    title: "Version probe still executes the resolved binary with `--version`"
  - id: IN-09
    severity: info
    disposition: skipped
    title: "Test-only suppressions are concentrated in TUI tests"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "`then`/`do` body line is a strip candidate; stripping it breaks the rc file"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "Skill packs with no `status_probes` (openspec, spec-kit) render as missing with an empty Ver cell"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "by_harness install handoff drops the framing text and ships unattributed, ambiguous lines"
  - id: IN-10
    severity: info
    disposition: fixed
    title: "A location-proven candidate that is not the live binary blocks native and OS-package attribution"
  - id: IN-11
    severity: info
    disposition: fixed
    title: "Closer word inside a trailing comment or quote makes an opener look self-closing"
  - id: IN-12
    severity: info
    disposition: fixed
    title: "Doctor keeps advertising an enter action that `applied` has made inert"
  - id: IN-13
    severity: info
    disposition: skipped
    title: "One-line `if/elif` consults only the `if` condition"
  - id: IN-14
    severity: info
    disposition: fixed
    title: "A single-directory PATH replacement is refused as 'adds more than one directory'"
  - id: IN-15
    severity: info
    disposition: fixed
    title: "'Already current' is stated for rows whose status is flagged stale"
  - id: IN-16
    severity: info
    disposition: fixed
    title: "alacritty comment says kitty has no applicable method on immutable Fedora"
  - id: IN-17
    severity: info
    disposition: fixed
    title: "`install-state` status probe ignores its declared `match`"
  - id: IN-18
    severity: info
    disposition: fixed
    title: "Duplicate-harness `status_probes` pass validation and collapse last-wins"
  - id: NR-01
    severity: info
    disposition: fixed
    title: "Post-apply doctor text is garbled after the IN-12 hint removal"
  - id: NR-02
    severity: info
    disposition: fixed
    title: "`export PATH=... FOO=1` is no longer reported as a persistent PATH writer"
  - id: NR-03
    severity: info
    disposition: skipped
    title: "Two heredocs on one rc line: only the first is tracked (documented shortcut)"
  - id: NR-04
    severity: info
    disposition: fixed
    title: "Enter-action hint strings duplicated between guidance.py and wizard_app.py"
open: 0
fixed: 18
skipped: 8
total: 26
recorded: 2026-10-10T17:37:50.355Z
---

# Phase 16: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | planned: 16-17; fixed in 79f859a, re-verified in 16-REVIEW-2.md |
| IN-01 | info | fixed | planned: 16-17; fixed in 2c92291, re-verified in 16-REVIEW-2.md |
| IN-02 | info | fixed | planned: 16-17; fixed in 1316295, re-verified in 16-REVIEW-2.md |
| IN-03 | info | skipped | accepted: two legitimate marketplaces per flagship pack and one probe per harness; a source-exact matcher would ship unused (16-18 ledger) |
| IN-04 | info | skipped | accepted: fails closed when two managers claim a directory; label-only harm (16-18 ledger) |
| IN-05 | info | skipped | accepted: documented shortcut in a background refresh; upgrade when profiling shows a cost (16-18 ledger) |
| IN-06 | info | fixed | planned: 16-17; fixed in cfd79c2, re-verified in 16-REVIEW-2.md |
| IN-07 | info | skipped | accepted: rare, repair is non-destructive (16-18 ledger) |
| IN-08 | info | skipped | accepted: bounded by run_query timeout; scope note, not a defect (16-18 ledger) |
| IN-09 | info | skipped | accepted: scoped suppressions pass the gates; a public test seam is a refactor (16-18 ledger) |
| WR-02 | warning | fixed | second lane (opencode-go/glm-5.2); planned: 16-17; fixed in a6cc70e, re-verified in 16-REVIEW-2.md |
| WR-03 | warning | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in e2d5dbc, re-verified in 16-REVIEW-2.md |
| WR-04 | warning | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in 6ae95a3, re-verified in 16-REVIEW-2.md |
| IN-10 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in 0cc67cc, re-verified in 16-REVIEW-2.md |
| IN-11 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-17; fixed in 2c92291, re-verified in 16-REVIEW-2.md |
| IN-12 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; hint removed after apply (41f99a8) but replacement text garbled (NR-01); closes with 16-19 Task 3 |
| IN-13 | info | skipped | accepted: fails safe (reported and refused, edit by hand); fix needs per-clause one-line parsing (16-17 ledger) |
| IN-14 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-17; fixed in 1316295, re-verified in 16-REVIEW-2.md |
| IN-15 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in ed990dd, re-verified in 16-REVIEW-2.md |
| IN-16 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in 71dd4ae, re-verified in 16-REVIEW-2.md |
| IN-17 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in 8bb1f9d, re-verified in 16-REVIEW-2.md |
| IN-18 | info | fixed | second lane (opencode-go/glm-5.2); planned: 16-18; fixed in 8bb1f9d, re-verified in 16-REVIEW-2.md |
| NR-01 | info | fixed | fresh review 16-REVIEW-2.md; planned: 16-19 Task 3 (closes IN-12) |
| NR-02 | info | fixed | fresh review 16-REVIEW-2.md; planned: 16-19 Task 1 (regression of the IN-02 fix) |
| NR-03 | info | skipped | accepted: documented `shortcut:` (first heredoc per line only); two heredocs on one rc line are vanishingly rare, diagnostic false positive only (16-19 ledger) |
| NR-04 | info | fixed | fresh review 16-REVIEW-2.md; planned: 16-19 Task 2 |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`. Triage on 2026-10-10 (gap plans 16-17, 16-18): "accepted" is recorded as `skipped` with the reason in the Source cell; `open` rows with `planned: 16-NN` become `fixed` when that plan lands.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.

## Observations (not review findings)

- `puppeteer` shows `!` and `no version` in the AI view (16-UI-CHECK.md): accepted, a true D-18 positive. The pnpm globals on this host hold only `@opengsd/gsd-browser` while `~/.local/share/pnpm/bin/puppeteer` is a leftover shim, so `dangling_shim` (installer/status.py:98) is correct. No code change (16-18 ledger).
