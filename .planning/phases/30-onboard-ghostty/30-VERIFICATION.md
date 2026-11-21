---
phase: 30-onboard-ghostty
verified: 2026-11-20T00:00:00Z
status: human_needed
score: 8/8 automated truths verified (4 roadmap criteria, 4 SPEC prohibitions/edges folded in); 0 failed
covered_files:
  - .planning/phases/30-onboard-ghostty/30-01-PLAN.md
  - .planning/phases/30-onboard-ghostty/30-01-SUMMARY.md
  - .planning/phases/30-onboard-ghostty/30-02-PLAN.md
  - .planning/phases/30-onboard-ghostty/30-02-SUMMARY.md
  - .planning/phases/30-onboard-ghostty/30-03-PLAN.md
  - .planning/phases/30-onboard-ghostty/30-03-SUMMARY.md
  - .planning/phases/30-onboard-ghostty/30-04-PLAN.md
  - .planning/phases/30-onboard-ghostty/30-04-SUMMARY.md
  - .planning/phases/30-onboard-ghostty/30-05-PLAN.md
  - .planning/phases/30-onboard-ghostty/30-05-SUMMARY.md
  - .planning/phases/30-onboard-ghostty/30-06-PLAN.md
  - .planning/phases/30-onboard-ghostty/30-06-SUMMARY.md
  - installer/app.py
  - installer/appimage_menu.py
  - installer/engine.py
  - installer/registry.toml
  - installer/terminal_keys.py
  - installer/terminal_regions.py
  - installer/terminal_shell.py
covered_digest: "v4:sha256:c445633e87b7876576a9670b264bbd21a74d46183a6ff627a92838ed58d7971d"
behavior_unverified: 0
overrides_applied: 0
gaps: []
provisional_decisions:
  - "30 D-03: macOS cask into ~/Applications with --appdir; no CLI link promised (cask has no binary stanza, kind has no cli key); CLI stays inside the bundle"
  - "30 D-08 (narrowing): a user `command` in any default file writes no shell region (orchestrator decision); shell region at top of file"
  - "30 D-10: a user `config-file =` include is not followed; written anyway with a partial line"
  - "30 D-17 (narrowing): residue diff covers installer-owned names, not the runtime's appimage_extracted_* /tmp leftovers"
  - "30 D-18 (narrowing): FUSE pass UNPROVEN on rootless podman; extract-and-run proven"
  - "SPEC R4 amendment 2026-11-20 following 28 D-06, and 28 D-06 itself: a region deleted after a recorded install stays deleted and quiet"
  - "Accepted limits in 30-REVIEW-DISPOSITION.md: symlink swap window, WR-02 process HOME/environ scan, IN-02 reinstall overwrites an edited menu entry, lane 3 legacy-config-after-install (backlog 999.30)"
human_verification:
  - test: "macOS: install Ghostty from the cask through the installer on a real Mac"
    expected: "Ghostty.app lands in ~/Applications (--appdir); uninstall removes it; the CLI is at ~/Applications/Ghostty.app/Contents/MacOS/ghostty (no ~/.local/bin link, D-03)"
    why_human: "Needs a real Mac and Homebrew; cask routing is only covered by resolve and executor-argv tests"
  - test: "macOS: Cmd+K clears screen and scrollback; Option+Left/Right move by word (also on the Spanish layout); a new tab/window/split opens in the same directory"
    expected: "Cmd+K sends Ctrl+L via the written super+k keybind; esc:b/esc:f vendor defaults fire with macos-option-as-alt unset; inherit-working-directory vendor defaults hold with shell integration"
    why_human: "Interactive terminal behavior; same_directory and word navigation are vendor-met claims from the v1.4.0 source, not run"
  - test: "macOS: `ghostty +show-config` and `ghostty +list-keybinds` on the written file, and that Ghostty reads the file the resolver chose (App Support config.ghostty vs XDG)"
    expected: "super+k=text:\\x0c listed; no macos-option-as-alt; effective config equals the resolver's choice"
    why_human: "Effective-config resolution on macOS cannot run in a Linux container; the resolver mirrors source (terminal_regions.py:457-475) and is unit-tested on both OSes only"
  - test: "Bazzite host: launch the AppImage through the host's own FUSE 2"
    expected: "The AppImage mounts via fuse 2.9.9/fusermount (no extract-and-run fallback), `ghostty --version` prints Ghostty 1.4.0, no reboot requested"
    why_human: "Rootless podman denies FUSE (fusermount3: mount failed: Operation not permitted); container run printed FUSE_UNPROVEN by design"
  - test: "Bazzite host: open a Ghostty window from the KDE menu entry and run zsh; check TERMINFO resolves xterm-ghostty inside the AppImage window"
    expected: "Menu entry and icon present; shell is zsh; line editing works; Ctrl+Shift+K clears screen and scrollback"
    why_human: "Needs a display and the real host; deferred ideas in 30-CONTEXT.md"
  - test: "Bazzite host: status-probe timing of the 5 s timeout without FUSE (about 49 MB extraction)"
    expected: "`ghostty --version` status probe finishes inside 5 s, or the row reads a probe timeout that needs a longer limit"
    why_human: "Host-specific timing; container proof showed 0.13 s with the user-namespace mount only"
  - test: "Owner confirmation of the provisional decisions listed in frontmatter (30 D-03, D-08, D-10, D-17, D-18, SPEC R4 amendment / 28 D-06, accepted limits)"
    expected: "Each confirmed or reversed by the owner"
    why_human: "Owner decisions, marked needs-confirmation by the phase summaries"
---

# Phase 30: Onboard Ghostty Verification Report

**Phase Goal:** A user can install, use and remove Ghostty from the catalog on macOS, Linux, Bazzite and Arch, and it opens zsh with the terminal defaults.
**Verified:** 2026-11-20
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: macOS cask into a user-writable location; Linux/Bazzite digest-verified community AppImage labelled "community build"; Arch pacman | VERIFIED (macOS CLI link provisional, D-03) | `installer/registry.toml:3208-3255`: pacman method (3220), two `tarball` methods with `raw = true`, pinned `version = "1.4.0"` and 64-hex `sha256`, `os = ["debian","fedora"]`, per-arch URL, `note = "community build ..."`, `desc` contains "community build"; cask method with `app = "Ghostty.app"`, `min_os_version = "13"`. `installer/executors.py:704-707` passes `--appdir=<applications_dir()>`. `installer/engine.py:287` wires `appimage_menu.install`. Digest-mismatch refusal tested: `tests/test_ghostty_catalog.py:1187`, `tests/test_engine.py:65`. Pins confirmed by `make verify-registry` (orchestrator). No CLI link on macOS: documented gap, D-03 provisional. |
| 2 | SC2a: Linux Ghostty launches zsh through the terminal sync; Ctrl+Shift+K clears screen and scrollback | VERIFIED | `installer/terminal_shell.py:543-583` `_sync_ghostty` writes owned region `ghostty` (`command = <zsh> -l`, `Placement.TOP`), keeps a user `command` (`partial: you already set command`), strips with the tool (`_strip_ghostty_regions`, 517). Keys row `installer/terminal_keys.py:346-365` writes `keybind = ctrl+shift+k=text:\x0c`. Container run 4: real Ghostty read both regions back (30-05-SUMMARY). Row in `_TERMINAL_ROWS` (`installer/version_status.py:740`). |
| 3 | SC2b: macOS golden writes nothing where the vendor meets a rule, never writes `macos-option-as-alt`, goes to the file Ghostty reads | VERIFIED (real-Mac effective config is a human item) | `installer/terminal_regions.py:457-475` `ghostty_config_path` mirrors `preferredDefaultFilePath` with `platform_os`; no `macos-option-as-alt` anywhere under `installer/`; regression assert `tests/test_terminal_keys.py:639`; skill cell `.claude/skills/tool-onboarding/SKILL.md:214`. macOS writes only the `super+k` keybind (D-11, spec amended). |
| 4 | SC3a: new tabs/windows/splits open in the current directory | VERIFIED as vendor-met (live check is a human item) | `KeysRow.same_directory` declared `vendor` with dated note (`installer/terminal_keys.py:357`); skill row records "not checked live". |
| 5 | SC3b: drifted Ghostty keys region shows `≈ apply install tuning`; reconfigure re-applies | VERIFIED (provisional R4/28 D-06: deleted recorded region stays deleted, quiet) | Drift/reconfigure/no-op-second-run tests in `tests/test_terminal_keys.py` and `tests/test_terminal_shell.py` (targeted run: all passed, 6 files, 100%). |
| 6 | SC4: in a container, uninstall removes AppImage, keys and shell regions and receipt paths, leaving only documented config | VERIFIED | `installer/app.py:634` `strip_terminal_keys` (strips `ghostty-keys`, sibling `ghostty`, record via `sibling_regions=(GHOSTTY,)`, `terminal_keys.py:363`); `appimage_menu` receipt leaves; real run `scripts/container-e2e-verify.sh ghostty` run 4 on 63455e08: `REMOVE_OK` for FUSE and extract passes, `TRACER_LANDING_TEARDOWN_OK`; residue diff held only allowlisted paths (30-05-SUMMARY:58-63). |
| 7 | Prohibition: never place an AppImage whose sha256 differs | VERIFIED | `tests/test_ghostty_catalog.py:1187`, `tests/test_engine.py:65` (ChecksumMismatch, nothing placed). |
| 8 | Prohibitions: never write `macos-option-as-alt`; never overwrite a user keybind or shell setting | VERIFIED | `tests/test_terminal_keys.py:639`; `partial: kept yours` / `you already bind ctrl+shift+k` / `you already set command` paths (`terminal_keys.py:225-226`, `terminal_shell.py:553-554`). Judgment-tier items resolved by tests. |

**Score:** 8/8 truths verified by automated evidence or recorded live evidence; 0 present-but-behavior-unverified.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `installer/registry.toml` ghostty entry | VERIFIED | exists, substantive, loaded by registry tests |
| `installer/appimage_menu.py` | VERIFIED | wired at `engine.py:9,287` |
| `installer/terminal_regions.py` Ghostty helpers | VERIFIED | used by `terminal_keys.py` and `terminal_shell.py` |
| `installer/terminal_keys.py` ghostty row | VERIFIED | `TERMINAL_KEYS["ghostty"]` 346 |
| `installer/terminal_shell.py` `_sync_ghostty` | VERIFIED | 543 |
| skill row and `scripts/container-e2e-verify.sh ghostty` | VERIFIED | `SKILL.md:214`; `tests/test_container_e2e_ghostty.py` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Ghostty catalog, menu, keys, shell, skill, container-script tests | `uv run pytest tests/test_ghostty_catalog.py tests/test_appimage_menu.py tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_tool_onboarding_skill.py tests/test_container_e2e_ghostty.py --no-cov -q` | all passed (100%) | PASS |

### Probe Execution

SKIPPED for the verifier (no standalone probe-*.sh); the orchestrator's real container run is recorded evidence (4 runs; run 4 `INSTALL_OK`, `FUSE_UNPROVEN`, `SYNC_OK`, `REGIONS_OK`, `REMOVE_OK` for FUSE; four `_OK` for extract-and-run; `TRACER_LANDING_TEARDOWN_OK`).

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| NTERM-01 | 30-01..30-06 | SATISFIED on automated and recorded container evidence; macOS and Bazzite-host parts pending human items | Truths 1-8 |

### Anti-Patterns Found

No TBD/FIXME/XXX blockers found in the sampled phase files. Known `shortcut:` comments (`terminal_shell.py:~549`, symlink window, WR-02) are documented accepted limits, not gaps.

### Human Verification Required

See `human_verification` in the frontmatter (7 items: macOS cask install, macOS keys behavior, macOS `+show-config`/`+list-keybinds`, Bazzite host FUSE mount, Bazzite window/TERMINFO/menu entry, 5 s probe timing, owner confirmation of provisional decisions).

### Gaps Summary

No gaps. Status is `human_needed` only because the real-Mac and Bazzite-host items cannot be proven in this environment, and the provisional owner decisions await confirmation. `phase.complete` is expected to refuse until those are resolved.

---

_Verified: 2026-11-20_
_Verifier: Claude (gsd-verifier)_
