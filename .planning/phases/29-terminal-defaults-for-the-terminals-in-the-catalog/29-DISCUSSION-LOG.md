# Phase 29: Terminal defaults for the terminals in the catalog - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 29-terminal-defaults-for-the-terminals-in-the-catalog
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** kitty; WezTerm; Alacritty; Konsole; herdr

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 53 tool calls. Live checks were read-only probes in a scratch HOME (kitty 0.49.2, wezterm 20240203 AppImage, herdr 0.9.5, Konsole 26.08.2 on the host) and herdr probes in disposable `fedora:44` podman containers (`--rm --network=none`); none left running. It did not install Konsole in a container, run a WezTerm GUI cwd test, or test macOS.

| Assumption | Confidence | Evidence |
|---|---|---|
| kitty `kitty-keys` region in `kitty.conf` | Confident | terminal_shell.py:954-967; 28 D-03 |
| Region at top of file plus a `map` scan (last wins) | Likely | verified live in kitty |
| Per-OS map lines with literal bytes | Likely | kitty default config dumped live |
| Install note names `scroll_line_up`; reload note | Confident | live default config |
| First-existing config path on macOS | Likely | terminal_shell.py:156-157, 914-915 |
| kitty macOS: cask only | Likely | registry.toml:3039-3062; audit kitty.md |
| WezTerm Lua region with a runtime guard | Likely | `wezterm show-keys` live |
| Exact marker-line match | Confident | terminal_shell.py:192 |
| WezTerm clear SendString `\x0c`; same-directory vendor | Likely | show-keys; cwd not verified |
| Alacritty: only the Linux clear row changes | Confident | 28 D-03, D-06 |
| Alacritty macOS row n/a | Likely | registry methods |
| Konsole stock action and override file | Likely | libkonsoleprivate strings |
| Konsole conditional write contradicts SKILL-03 | Unclear | SPEC R4 vs SKILL-03 |
| herdr does not intercept; verified in a container | Confident | live pty probe |
| herdr byte test as a container target | Likely | CI installs no herdr |
| herdr no keys row | Unclear | 28 D-06, D-11 |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| d1 kitty placement | none_of_these 0.77 (contradicts evidence); second opinion top_of_file_plus_scan 0.94 | **jev overridden** (D-01) |
| d2 bytes vs synthesized | low 0.37; TypeSafe choice literal_bytes 0.83 | D-02 |
| d3 config path | none_of_these 0.91 (contradicts evidence); second opinion first_existing_in_vendor_order 0.97 | **jev overridden** (D-04) |
| d4 kitty macOS route | low 0.49; TypeSafe choice cask_user_dir 0.97 | D-05 |
| d5 WezTerm conflicts | low 0.68; TypeSafe low 0.75 | **Own reasoning:** Lua guard plus readback (D-06, ledger) |
| d6 same-directory evidence | low 0.44; TypeSafe choice live_check_before_lock 0.95 | D-07 |
| d7 Alacritty macOS | low 0.42; TypeSafe choice not_applicable_amend_spec 0.96 | D-08 |
| d8 Konsole file confirmation | none_of_these 0.77 (contradicts evidence); second opinion container_capture low 0.79 | **jev overridden / Own reasoning** (D-09, ledger) |
| d9 Konsole restore | none_of_these 0.98 (contradicts evidence); second opinion report_only low 0.73 | **jev overridden / Own reasoning** (D-09, needs confirmation, ledger) |
| d10 herdr test location | low 0.62; TypeSafe choice container_e2e_target 0.98 | D-10 |
| d11 herdr row | low 0.57; TypeSafe low 0.45 (noop_entry) | **Own reasoning:** no row (D-10, ledger) |

## Live facts that changed the plan

- herdr 0.9.5 does not intercept the three chords (container probe): no setting, no row; SPEC boundary amended (D-10).
- Konsole: a conditional write would undo a deliberate user removal; report-only; TERM-04, SPEC R4, ROADMAP criterion 3 amended, flagged needs confirmation (D-09).
- Alacritty has no macOS method: TERM-03's macOS chord is n/a (D-08).
- kitty and WezTerm resolve a duplicate chord last-wins: kitty's region goes to the top of the file; WezTerm needs a Lua runtime guard (D-01, D-06). The phase 28 row type gains `placement` and `validate` (amended in 28-CONTEXT D-03, D-11).

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The Unclear items (Konsole write, herdr row) were decided by own reasoning above.

## External Research

Open items are in CONTEXT deferred: kitty's macOS config order, the cask's `binary` stanzas, cwd inheritance in WezTerm, Konsole's default chord and the post-removal file content, the KF6 override directory.
