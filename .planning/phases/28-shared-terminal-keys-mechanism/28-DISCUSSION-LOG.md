# Phase 28: Shared terminal-keys mechanism - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 28-shared-terminal-keys-mechanism
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** row and table design; the zsh Ctrl+L widget; tests; Alacritty same-directory value; module split

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 32 tool calls. It captured today's Alacritty bytes in a scratch HOME, ran the widget body in zsh 5.9.2 under a pty, and read the tests and dispatch sites. It did not read `session.py`, `uninstall_screen.py`, `test_registry.py` or the full Alacritty block of `test_version_status.py`, and could not check Alacritty (not installed) or macOS. Its agent-skills wiring was not clean (jev skill skipped), which does not matter.

| Assumption | Confidence | Evidence |
|---|---|---|
| Table keyed by tool id, record names unchanged | Confident | terminal_shell.py:475-476,500-506 |
| Success and refusal text unchanged | Confident | tests/test_post_install.py:1129-1141 |
| Row fields with a typed ownership union | Likely | test_terminal_shell.py:1153-1205,1540-1595; ARCHITECTURE.md:89 |
| Dispatch sites table-driven | Confident | post_install.py:385-396; version_status.py:783; app.py:630 |
| KEYS-02 "missing shows ≈" contradicts pinned tests; drift undetected today | Unclear | terminal_shell.py:710-723; test_version_status.py:7054 |
| zsh widget as a shell-init bundle of the zsh entry | Likely | tweaks.py:90; compose.py:713 |
| Widget text with bash guard and explicit keymaps | Likely | verified live in zsh 5.9.2 |
| Two-layer widget test | Likely | ci.yml installs no zsh |
| Golden bytes before the move, public routes | Confident | live capture |
| Completeness test as a pure id-set helper | Confident | model.py:138 |
| Existing tests: import-line edits only | Likely | test_terminal_shell.py:1220,1254,1323,1648 |
| `same_directory` required, typed | Likely | SPEC R4 |
| Alacritty row declares vendor | Unclear | CHANGELOG lines 715-724 (verified here) |
| Import direction terminal_shell → terminal_keys; lower primitives module | Confident / Unclear | pyproject.toml:44 strict pyright |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| b1 ownership model | low 0.42; TypeSafe low 0.50 (flat_fields_plus_flag) | **Own reasoning:** typed union (D-03, ledger) |
| b2 drift semantics | low 0.39; TypeSafe choice drifted_rewrite 0.90 | D-06 (**needs confirmation**: narrows KEYS-02, ledger) |
| b3 widget lifecycle | low 0.40; TypeSafe choice zsh_entry_tuning 0.81 | D-07 |
| b4 widget text | low 0.34; TypeSafe low 0.62 | **Own reasoning:** explicit bytes, all keymaps (D-08, ledger) |
| b5 widget test | low 0.59; TypeSafe low 0.74 | **Own reasoning:** bytes plus optional shell (D-09, ledger) |
| b6 existing test imports | none_of_these 0.95 (contradicts evidence); second opinion update_imports low 0.67 | **jev overridden / Own reasoning** (D-12, ledger) |
| b7 same-directory declaration | none_of_these 0.71 (contradicts evidence); second opinion typed_with_setting low 0.55 | **jev overridden / Own reasoning** (D-14, ledger) |
| b8 Alacritty value | low 0.64; TypeSafe low 0.46 (unverified) | **Own reasoning:** vendor with a dated note (D-15, ledger) |
| b9 helper module | low 0.63; TypeSafe low 0.77 (third_module_aliased) | **Own reasoning:** lower module, aliased (D-05, ledger) |

## Live facts that changed the plan

- KEYS-02's "deleting the region shows `≈`" conflicts with the user-deleted doctrine and two pinned tests; SPEC R2, REQUIREMENTS KEYS-02 and ROADMAP criterion 2 amended (D-06, flagged needs confirmation); phase 29 depends on drift detection.
- `.planning/research/ARCHITECTURE.md:24,51` has the import direction inverted for this codebase (strict pyright, test assertion on the sync result): overridden (D-05).
- Alacritty's `SpawnNewInstance` uses the foreground process cwd (upstream CHANGELOG, read 2026-11-19): row declares vendor (D-15).

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

None Unclear left unresolved: the three Unclear items got jev answers or own reasoning above.

## External Research

None beyond the analyzer's live checks; open items (CI zsh presence, starship redraw, macOS scrollback on 2J) are in CONTEXT deferred.
