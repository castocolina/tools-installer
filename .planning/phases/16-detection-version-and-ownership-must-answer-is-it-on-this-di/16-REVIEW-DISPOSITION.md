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
    disposition: open
    title: "Skill-pack matches can hit a same-named entry from another source"
  - id: IN-04
    severity: info
    disposition: open
    title: "Ownership is attributed from bare file presence at the declared `bin_dir`"
  - id: IN-05
    severity: info
    disposition: open
    title: "Keg-only brew probe stats `opt/<formula>/bin/<cmd>` for every formula"
  - id: IN-06
    severity: info
    disposition: open
    title: "`path_scan_rc_paths` can raise on an unreadable `~/.bashrc.d` entry"
  - id: IN-07
    severity: info
    disposition: open
    title: "`dangling_shim` keys on package names only"
  - id: IN-08
    severity: info
    disposition: open
    title: "Version probe still executes the resolved binary with `--version`"
  - id: IN-09
    severity: info
    disposition: open
    title: "Test-only suppressions are concentrated in TUI tests"
open: 10
total: 10
recorded: 2026-10-10T17:37:50.355Z
---

# Phase 16: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |
| IN-09 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
