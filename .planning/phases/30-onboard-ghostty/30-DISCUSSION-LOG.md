# Phase 30: Onboard Ghostty - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 30-onboard-ghostty
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** registry entry; shell sync; keys row; removal; tests, gates and the container plan

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 80 tool calls. It read Ghostty v1.4.0 sources (saved under the scratchpad `p30/src`, never executed), ran one disposable `fedora:44` container (removed) to re-hash the x86_64 AppImage and probe FUSE behavior, and read the registry, download, engine and test code. It did not read `uninstall.py`'s planner, the cask uninstall path or `apps.cli_spec` in depth, and did not run verify-registry or `make test`.

| Assumption | Confidence | Evidence |
|---|---|---|
| Registry entry fields, `_POST_15_3_HUMAN_TOOLS` | Confident | registry.toml:3103-3164; test_registry.py:276-285 |
| Two pinned `tarball` raw methods | Likely | model.py:69-96; download.py:116-140 |
| macOS cask, no CLI link | Likely | cask JSON; model.py:105 |
| Arch pacman; tarballs exclude Arch | Confident | archlinux.org API |
| "community build" via per-method `note` | Likely | engine.py:138-157; render.py:485-494 |
| No smoke_argv; no desktop entry | Unclear | container probe |
| `_sync_ghostty` with partial detection | Likely | terminal_shell.py:553-564 |
| Config file: Ghostty's preferred XDG path | Confident | file_load.zig |
| `config-file` includes not followed | Likely | Config.zig :2590-2604 |
| Keys row; macOS rebinds Cmd+K to Ctrl+L | Likely | Config.zig :7134-7138 |
| Normalized conflict detection | Likely | Binding.zig :3304-3345 |
| macOS file mirrors Ghostty's preferred path | Likely | Config.zig :4245-4313 |
| same_directory vendor | Confident | Config.zig :2086-2099 |
| Byte goldens through public routes | Likely | 28 D-10 |
| Removal: receipt plus both regions | Confident | download.py:311-312 |
| Residue diff vs allowlist | Likely | e2e-residue-allowlist.txt |
| Registry tests, dedicated container target | Likely/Confident | container-e2e-verify.sh:95-130 |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| g1 pin the AppImage | low 0.60; TypeSafe choice pin_in_catalog_raw_key 0.85 | D-02 |
| g2 macOS CLI link | low 0.47; TypeSafe low 0.53 (accept_and_document) | **Own reasoning** (D-03, ledger) |
| g3 community label | low 0.40; TypeSafe choice method_note_and_desc 0.98 | D-05 |
| g4 menu entry | choice add_menu_entry 0.78 | D-07 |
| g5 shell block placement | low 0.58; TypeSafe low 0.59 (top_with_report) | **Own reasoning:** top plus detection (D-08, ledger) |
| g6 config-file includes | none_of_these 0.71 (contradicts evidence); second opinion write_and_note low 0.53 | **jev overridden / Own reasoning** (D-10, ledger) |
| g7 macOS Cmd+K | none_of_these 0.81 (contradicts evidence); second opinion rebind_to_ctrl_l 0.95 | **jev overridden** (D-11) |
| g8 chord comparison | low 0.62; TypeSafe choice normalize_then_compare 0.96 | D-12 |
| g9 macOS file | low 0.53; TypeSafe choice terminals_preferred_file 0.97 | D-13 |
| g10 tests | low 0.52; TypeSafe choice byte_goldens_public_routes 0.96 | D-15 |
| g11 residue diff | installer_folders_only 0.92 (weaker than the shared check); second opinion none_of_these low 0.54 | **Own reasoning** (D-17, ledger) |
| g12 container target | choice dedicated_target 0.72 | D-18 |

## Live facts that changed the plan

- `github_release` has no `version` or `sha256`: the pins ride on `tarball` with an allowed `raw` key, shared with phase 32's Bruno; SPEC R1 amended (D-02).
- Ghostty's default Cmd+K is the native clear action (no Ctrl+L), so macOS writes one keybind; the research claim "macOS: write nothing" is overridden; SPEC R3 amended (D-11).
- The AppImage needs a menu entry to be usable from the KDE menu; SPEC in-scope amended (D-07).
- 28 D-03's `config_path` needs `platform_os` (amended in 28-CONTEXT); phases 27-29 must execute first (D-19).

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The Unclear items (smoke and menu entry) were decided by jev or own reasoning above.

## External Research

Open items are in CONTEXT deferred: TERMINFO inside the AppImage, `+show-config` flags, the Spanish-layout Option check, the status-probe timeout without FUSE.
