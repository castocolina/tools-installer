---
phase: 16
review: 16-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "A second PATH-writer guard of the same rc file is refused forever with a misleading message"
  - id: IN-01
    severity: info
    disposition: open
    title: "Heredoc body lines are treated as guardable PATH writers"
  - id: IN-02
    severity: info
    disposition: open
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
    disposition: open
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
    disposition: open
    title: "`then`/`do` body line is a strip candidate; stripping it breaks the rc file"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Skill packs with no `status_probes` (openspec, spec-kit) render as missing with an empty Ver cell"
  - id: WR-04
    severity: warning
    disposition: open
    title: "by_harness install handoff drops the framing text and ships unattributed, ambiguous lines"
  - id: IN-10
    severity: info
    disposition: open
    title: "A location-proven candidate that is not the live binary blocks native and OS-package attribution"
  - id: IN-11
    severity: info
    disposition: open
    title: "Closer word inside a trailing comment or quote makes an opener look self-closing"
  - id: IN-12
    severity: info
    disposition: open
    title: "Doctor keeps advertising an enter action that `applied` has made inert"
  - id: IN-13
    severity: info
    disposition: skipped
    title: "One-line `if/elif` consults only the `if` condition"
  - id: IN-14
    severity: info
    disposition: open
    title: "A single-directory PATH replacement is refused as 'adds more than one directory'"
  - id: IN-15
    severity: info
    disposition: open
    title: "'Already current' is stated for rows whose status is flagged stale"
  - id: IN-16
    severity: info
    disposition: open
    title: "alacritty comment says kitty has no applicable method on immutable Fedora"
  - id: IN-17
    severity: info
    disposition: open
    title: "`install-state` status probe ignores its declared `match`"
  - id: IN-18
    severity: info
    disposition: open
    title: "Duplicate-harness `status_probes` pass validation and collapse last-wins"
open: 15
skipped: 7
total: 22
recorded: 2026-10-10T17:37:50.355Z
---

# Phase 16: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | planned: 16-17 |
| IN-01 | info | open | planned: 16-17 |
| IN-02 | info | open | planned: 16-17 |
| IN-03 | info | skipped | accepted: two legitimate marketplaces per flagship pack and one probe per harness; a source-exact matcher would ship unused (16-18 ledger) |
| IN-04 | info | skipped | accepted: fails closed when two managers claim a directory; label-only harm (16-18 ledger) |
| IN-05 | info | skipped | accepted: documented shortcut in a background refresh; upgrade when profiling shows a cost (16-18 ledger) |
| IN-06 | info | open | planned: 16-17 |
| IN-07 | info | skipped | accepted: rare, repair is non-destructive (16-18 ledger) |
| IN-08 | info | skipped | accepted: bounded by run_query timeout; scope note, not a defect (16-18 ledger) |
| IN-09 | info | skipped | accepted: scoped suppressions pass the gates; a public test seam is a refactor (16-18 ledger) |
| WR-02 | warning | open | second lane (opencode-go/glm-5.2); planned: 16-17 |
| WR-03 | warning | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| WR-04 | warning | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| IN-10 | info | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| IN-11 | info | open | second lane (opencode-go/glm-5.2); planned: 16-17 |
| IN-12 | info | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| IN-13 | info | skipped | accepted: fails safe (reported and refused, edit by hand); fix needs per-clause one-line parsing (16-17 ledger) |
| IN-14 | info | open | second lane (opencode-go/glm-5.2); planned: 16-17 |
| IN-15 | info | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| IN-16 | info | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| IN-17 | info | open | second lane (opencode-go/glm-5.2); planned: 16-18 |
| IN-18 | info | open | second lane (opencode-go/glm-5.2); planned: 16-18 |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`. Triage on 2026-10-10 (gap plans 16-17, 16-18): "accepted" is recorded as `skipped` with the reason in the Source cell; `open` rows with `planned: 16-NN` become `fixed` when that plan lands.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.

## Observations (not review findings)

- `puppeteer` shows `!` and `no version` in the AI view (16-UI-CHECK.md): accepted, a true D-18 positive. The pnpm globals on this host hold only `@opengsd/gsd-browser` while `~/.local/share/pnpm/bin/puppeteer` is a leftover shim, so `dangling_shim` (installer/status.py:98) is correct. No code change (16-18 ledger).
