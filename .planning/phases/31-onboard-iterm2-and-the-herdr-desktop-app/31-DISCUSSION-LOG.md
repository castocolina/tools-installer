# Phase 31: Onboard iTerm2 and the Herdr desktop app - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 31-onboard-iterm2-and-the-herdr-desktop-app
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** JSON ownership modes; the iTerm2 entry, profile and default profile; the Herdr desktop app entry and keys; tests; the Mac UAT list

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 71 tool calls. It fetched and read the herdr-app v0.1.16 sources, the vendor `install.sh` (read, not run), the cask JSON and iTerm2's master sources into the scratchpad `p31/`; nothing ran on the host and no container was started. Every iTerm2 fact comes from master, not the 3.7.8 tag.

| Assumption | Confidence | Evidence |
|---|---|---|
| Two new ownership variants (whole file, per key) | Likely | herdr-app src/keys.rs:175-189 |
| WholeFile proof: record plus GUID | Likely | terminal_shell.py:475-506 |
| Per-key edits through the splice helpers | Likely | agent_settings.py:290-333,486-510 |
| Deleted-file meaning per variant | Unclear | 28 D-06 vs SPEC R5 |
| `placement` inside `OwnedRegion` | Likely | 29 D-11 |
| iTerm2 cask entry fields | Confident | status.py:201-210; cask 3.7.8 |
| No `config_paths` for iTerm2 | Likely | cask zap list |
| Profile file: Recycle, Cmd+K hex-code action | Likely | ITAddressBookMgr.h:54; iTermKeyBindingAction.h:51 |
| Word navigation by key-map rows, Option Normal | Unclear | VT100Output.m:58-61,246-262; 27 D-11 |
| Profile parent GUID plus merged key map | Unclear | dp37.md:64,78-80 |
| Explicit colors, separate light/dark off | Likely | DefaultBookmark.plist |
| Default profile via an injected `defaults` runner | Likely | post_install.py:142-153 |
| Herdr app id `herdr-app`; script paths | Likely / Confident | install.sh read |
| macOS cask arm64 only | Confident | cask JSON |
| `config_paths` `~/.config/herdr-app` | Likely | model.py:461-474 |
| Keys in the `terminal` section | Likely | defaults/AGENTS.md:523-525 |
| Seed vendor defaults when the file is missing | Unclear | src/keys.rs:166-189 |
| User-binding detection | Likely | defaults/AGENTS.md |
| Container target with the network | Likely | container-e2e-verify.sh:2864 |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| i1 JSON ownership modes | low 0.56; TypeSafe low 0.69 (separate_per_key_mode) | **Own reasoning:** two variants (D-01, ledger) |
| i2 iTerm2 ownership proof | low 0.56; TypeSafe low 0.49 | **Own reasoning:** record plus GUID (D-02, ledger) |
| i3 per-key editing | none_of_these 0.80 (contradicts evidence); second opinion splice_existing_helpers low 0.79 | **jev overridden / Own reasoning** (D-01, ledger) |
| i4 deleted file | low 0.38; TypeSafe choice per_mode 0.80 | D-03 |
| i5 placement | low 0.64; TypeSafe low 0.56 | **Own reasoning:** inside the region mode (D-04, ledger) |
| i6 iTerm2 config folder | low 0.46; TypeSafe choice none 0.97 | D-06 |
| i7 Cmd+K | low 0.57; TypeSafe low 0.69 (send_ctrl_l) | **Own reasoning** (D-07, ledger) |
| i8 word navigation | low 0.55; TypeSafe choice map_rows_only 0.97 | D-08 (needs confirmation) |
| i9 profile inheritance | low 0.50; TypeSafe low 0.63 | **Own reasoning:** parent plus merged keys (D-09, ledger) |
| i10 colors | low 0.36; TypeSafe low 0.55 | **Own reasoning:** core five (D-10, ledger) |
| i11 default-profile step | none_of_these 0.99 (contradicts evidence); second opinion separate_action low 0.65 | **jev overridden / Own reasoning** (D-11, ledger) |
| i12 id | low 0.47; TypeSafe choice herdr_app 0.98 | D-12 |
| i13 herdr-app config folder | low 0.45; TypeSafe choice declare 0.80 | D-13 |
| i14 Linux clear key | none_of_these 0.76 (contradicts evidence); second opinion terminal_section_override 0.95 | **jev overridden** (D-14) |
| i15 missing keys file | none_of_these 0.91 (contradicts evidence); second opinion seed_vendor_defaults 0.92 | **jev overridden** (D-15) |
| i16 user-binding detection | none_of_these 0.93 (contradicts evidence); second opinion terminal_only low 0.70 | **jev overridden / Own reasoning** (D-16, ledger) |
| i17 container proof | low 0.51; TypeSafe choice container_target_with_network 0.85 | D-17 |

## Live facts that changed the plan

- The herdr app reads one keys file and never merges defaults: per-key ownership, seeded vendor defaults, SPEC R4 and the edge row amended (D-01, D-14, D-15).
- Option as Esc+ is iTerm2's global switch and gives no word navigation: key-map rows instead; NTERM-02, SPEC R1, ROADMAP criterion 1 amended, flagged needs confirmation (D-08).
- 28's union gets two variants and `placement` moves into `OwnedRegion` (amended in 28-CONTEXT and 29-CONTEXT) (D-01, D-04).
- The vendor `install.sh` on macOS puts the app in `~/Applications` and links the command in `~/.local/bin`, which meets the phase 27 rule better than the cask: flagged for the owner (D-12).

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The Unclear items were decided by jev or own reasoning above.

## External Research

Open items are in CONTEXT deferred: iTerm2 3.7.8 behavior (analysis used master), default-profile persistence at launch, herdr-app defaults and `--version`, the owner's RGB values.
