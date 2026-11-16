---
phase: 22
reviewed_at: 2026-11-04
base: 6fcaa7f
head: 67588cd
lanes:
  - deep (22-REVIEW-deep.md, CR-01..CR-17)
  - ponytail (22-REVIEW-ponytail.md, PT-01..PT-07)
  - external referee-three, narrow re-run (.review-diagnostics/20261104T085832Z-code-review-narrow/opencode-referee-three/lane.out)
external_lane_note: "referee-one failed mid-run (no executable targets), referee-three timed out; a narrow external lane is re-running"
findings:
  high: 4
  medium: 11
  low: 8
  total: 23
verdicts:
  confirmed: 23
  refuted: 0
status: issues_found
---

# Phase 22: Consolidated code review

The deep and ponytail lanes reviewed `6fcaa7f..e8c1590`. HEAD `67588cd` adds only the D-2
closure (`9cf3a69`, `8417c5e`) and ledger rows. The narrow external lane on referee-three
added C-18 and C-19. Each HIGH and MEDIUM finding was re-verified against the source at
`67588cd`; the evidence is listed below. These duplicates were merged: CR-02 ≈ PT-01 (plus
CR-04, which the same fix removes), CR-06 ≈ PT-02, and CR-17 ≈ PT-05.

## Consolidated table

| ID | Sev | Lanes | Title | Verdict | Decision |
|----|-----|-------|-------|---------|----------|
| C-01 | HIGH | deep CR-01 | A failed userspace method before a native one ends as `manual`, its error dropped, exit 0 | CONFIRMED | fix |
| C-02 | HIGH | deep CR-02, ponytail PT-01 | A manager receipt is trusted forever: an already-removed package fails every uninstall; a user reinstall is claimed | CONFIRMED | fix (inventory re-check); reinstall-after-receipt is residual |
| C-03 | HIGH | deep CR-03 | e2e gate fails: undeclared sibling launchers survive a `removed` row | CONFIRMED at e8c1590; CLOSED | closed by 9cf3a69 + 8417c5e |
| C-04 | MEDIUM | deep CR-04 | `ERR_PNPM_GLOBAL_PKG_NOT_FOUND` from any pnpm deletes the receipt | CONFIRMED | fix (folded into C-02) |
| C-05 | MEDIUM | deep CR-05 | A native method ends the ladder before a sudo-free brew method | CONFIRMED (behaviour) | by_design (ledger Q2) |
| C-06 | MEDIUM | deep CR-06, ponytail PT-02 | The pre-install inventory check misses tap-qualified formulae | CONFIRMED | fix |
| C-07 | MEDIUM | deep CR-07 | A regular-file leaf in shared `~/.local/bin` is proven by its type alone | CONFIRMED | residual (+ shortcut comment) |
| C-08 | MEDIUM | deep CR-08 | The zero-sudo guard misses the registry `remove`/`update` argv | CONFIRMED | fix |
| C-09 | MEDIUM | deep CR-09 | `config_paths` accepts shared well-known dirs | CONFIRMED | fix |
| C-10 | MEDIUM | deep CR-10 | Cask removal can elevate through Homebrew (inherited `SUDO_ASKPASS`) | CONFIRMED | fix (`HOMEBREW_NO_SUDO`, no askpass); NOPASSWD sudo in non-brew vendor scripts is residual |
| C-11 | MEDIUM | deep CR-11 | The declared `update` argv runs its first word from PATH | CONFIRMED | fix |
| C-12 | MEDIUM | deep CR-12 | e2e leftover check is blind under harness dirs and for level-`none` receipts | CONFIRMED | residual |
| C-18 | HIGH (lane: MEDIUM) | external referee-three | `brew uninstall` autoremoves unused dependency formulae machine-wide | CONFIRMED | fix |
| C-20 | MEDIUM | ponytail PT-03 | Two copies of the shared-config-path rule, for a state the registry never has | CONFIRMED (no shared entry today) | by_design |
| C-13 | LOW | deep CR-13 | The review's pnpm group warnings read live state, not the frozen decision | CONFIRMED | fix |
| C-14 | LOW | deep CR-14 | "Config kept" stats the disk on the UI thread | CONFIRMED | residual |
| C-15 | LOW | deep CR-15 | A `c` refusal during a removal is silent | CONFIRMED | fix |
| C-16 | LOW | deep CR-16 | A malformed cached `greedy` reads as "none", not unknown | CONFIRMED | fix |
| C-17 | LOW | deep CR-17, ponytail PT-05 | Two `$ZSH` resolvers with opposite precedence | CONFIRMED | fix |
| C-19 | LOW | external referee-three | A hand-edited receipt can add `/` as a tree to `drifted()`'s trees | CONFIRMED (needs local write to the receipt) | residual |
| C-21 | LOW | ponytail PT-04 | The vendor `remove` mechanism has no registry user | CONFIRMED | by_design (+ shortcut comment) |
| C-22 | LOW | ponytail PT-06 | Every manager-method install reads the whole manager inventory | CONFIRMED | residual |
| C-23 | LOW | ponytail PT-07 | `new_leftovers` expands empty arrays under `set -u` (bash 3.2) | CONFIRMED | fix |

## Evidence (HIGH and MEDIUM)

- **C-01**: `engine.install_tool` returned `MANUAL_REQUIRED` at the first native method
  without `errors` (`engine.py:245-253` at 67588cd). `session._FAILURE` does not include
  `manual`, so `exit_code` was 0. The test `test_a_native_method_after_a_failed_method_is_handed_off`
  pinned exactly this behaviour.
- **C-02**: `uninstall._manager_argv` builds the argv from the receipt alone.
  `receipts.all_gone` never retires an artifact-less receipt. `app.remove_tool` checked no
  listing, and its only "already gone" path was the pnpm string (`app.py:575-597`).
  Reinstall case: `ManagerInventory` holds name→version only, and the receipt records no
  version or install time, so the inventory cannot tell a user reinstall from our own
  install.
- **C-03**: At `e8c1590` the registry declared only the main binaries. `9cf3a69` declares
  `~/.bun/bin/bunx` (registry.toml:2170), `pn`/`pnpx`/`pnx` (:2204) and the volta shims
  (:2273), and it allowlists the runtime residue. `8417c5e` records the `make e2e` exit 0
  run: TRACER_UNINSTALL_OK, TRACER_RECEIPTS_GONE_OK count=61, TRACER_LEFTOVER_OK,
  TRACER_REINSTALL_OK.
- **C-04**: The `gone = argv[:-1] == MANAGER_UNINSTALL_ARGV["node"] and
  PNPM_GLOBAL_PKG_NOT_FOUND in exc.detail` branch deleted the receipt on the error text
  alone.
- **C-05**: The ladder does stop at the native step. RUN-LEDGER row "Q2 … DECIDED handoff
  ends the ladder … no silent switch to Homebrew" records this choice. C-01 keeps an
  earlier failure visible on that path.
- **C-06**: `_package_already_there` compared `anomalyco/tap/opencode` against the
  `brew list --versions` keys, which hold short names. `ownership.py:1096` made the same
  comparison.
- **C-07**: `receipts._leaf_matches` returns `S_ISREG` for any regular file when no
  target was recorded. The leaf `fingerprint` (`receipts.py:517-521`) records no sha256 or
  size, so no stronger proof can be tightened without a receipt-format change.
- **C-08**: `_script_token_ok("sudo")` is None. The AST test scanned only Python literals.
- **C-09**: `_config_path_flaw` checked only `~/`, depth ≥ 2 and harness markers.
  `~/.local/bin`, `~/Library/Preferences` and `~/.config/systemd` loaded.
- **C-10**: `run.run_output_with_stderr(env=None)` inherits the whole environment.
  Homebrew 7.0.12 `system_command.rb:418` adds `sudo -A` when `SUDO_ASKPASS` is set, and
  `:412-415` refuses sudo under `HOMEBREW_NO_SUDO` (`env_config.rb:653`). Both were read in
  the host's Homebrew source tree, read-only.
- **C-11**: `update._update_installer_owned` handed `["claude", "update"]` and similar
  argv to the runner as-is, so PATH chose the copy.
- **C-12**: `container-e2e-verify.sh` writes only level ≠ none receipts to
  `removable-receipts.txt`, and every harness-marker dir is an allowed prefix. The D-2
  empty-dir skip is a further shortcut, recorded in the function comment.
- **C-18**: Homebrew 7.0.12 `env_config.rb:542-546`: "`HOMEBREW_NO_AUTOREMOVE`: If set,
  calls to `brew cleanup` and `brew uninstall` will not automatically remove unused formula
  dependents". `utils/auto-update.sh:144-150` does not list `uninstall` as an auto-update
  command, so `HOMEBREW_NO_AUTO_UPDATE` has no effect on a removal.
- **C-20**: `_refuse_config_overlap` allows equal entries (`a_parts != b_parts`), and
  `wizard_app.config_split` and `app._config_step` each apply the "every owner flagged"
  rule. No two registry tools share an entry today. The rule is the recorded decision in
  RUN-LEDGER row "UI-SPEC open questions" ("Shared config paths used by a tool that stays
  installed are kept, never deleted") and the SPEC R6 shared-path edge, so it stays.

## Decisions (orchestrator, binding)

- C-05 by_design: ledger Q2.
- C-02: a fresh one-manager listing is the primary guard. The table of manager "not
  installed" strings that PT-01 suggested is not added: with the listing in place it guards
  nothing that matters. The pnpm-only string tolerance (4190481) is deleted, because a
  member that an earlier group removal took is no longer listed. Fail-closed: an unreadable
  listing runs the previewed command, and a failure keeps the receipt.
- C-07 residual: the receipt records no size/hash for leaves, so the 22-03 type-only rule
  stays. A `shortcut:` comment names the limit.
- C-21 by_design: UI-SPEC amendment 2026-11-04 keeps the mechanism. A `shortcut:` comment
  names it.

---

_Consolidated: 2026-11-04 (gsd-code-fixer)_
