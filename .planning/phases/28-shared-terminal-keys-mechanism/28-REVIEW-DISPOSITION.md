---
phase: 28
review: 28-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Drift loses the keys region for good when the user binds all three chords"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The widget replaces any ^L binding the user already made"
  - id: IN-01
    severity: info
    disposition: deferred
    title: "In single-shell mode with bash, zsh never sources ~/.myshellrc, yet the zsh row reads tuned"
  - id: IN-02
    severity: info
    disposition: deferred
    title: "The created-marker filename is hardcoded in terminal_shell.py instead of using ALACRITTY_CREATED"
  - id: IN-03
    severity: info
    disposition: deferred
    title: "alacritty_keys_plan_for_text is a wrapper that adds nothing"
  - id: IN-04
    severity: info
    disposition: deferred
    title: "The drift check is duplicated in apply_terminal_keys and terminal_keys_pending"
  - id: IN-05
    severity: info
    disposition: skipped
    title: "The no-keys-row branches cover a state the completeness test already blocks at push (necessity)"
  - id: IN-06
    severity: info
    disposition: skipped
    title: "The outer command -v zsh guard is redundant with the ZSH_VERSION check (necessity)"
  - id: IN-07
    severity: info
    disposition: deferred
    title: "The Writes path, which no row uses yet, prints the keys summary when only its snippet was written and does not check the snippet for conflicts"
---

# Phase 28: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | external lane (opencode referee-one) claim 2, confirmed and reproduced by the reviewer and the orchestrator; fixed in d20fb404, re-run after the fix shows the chord managed again |
| WR-02 | warning | fixed | reviewer finding, confirmed in code and in a real zsh run; fixed in ddc89888 |
| IN-01 | info | deferred | external lane claim 1, filed as info by the reviewer: predates this phase, affects every shell-init bundle; backlog 999.28 |
| IN-02 | info | deferred | backlog 999.28: tidiness; the fix would need a new import that risks a cycle between terminal_shell and terminal_keys |
| IN-03 | info | deferred | backlog 999.28: tidiness |
| IN-04 | info | deferred | backlog 999.28: tidiness; the two copies are covered by tests that must stay in step |
| IN-05 | info | skipped | rejected: plan 28-02 asked for the runtime backstop on purpose (the completeness test blocks the state only at push) |
| IN-06 | info | skipped | rejected: plan 28-04 asked for the outer guard |
| IN-07 | info | deferred | phase 29's first Writes row exercises the path; backlog 999.28 records it |
