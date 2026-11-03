---
status: complete
phase: 21-one-screen-family
source: [21-VERIFICATION.md (human_verification), 21-UI-SPEC.md]
started: 2026-11-03T20:25:00Z
updated: 2026-11-03T20:40:00Z
---

<!-- Run by an agent at HEAD 68d498d in a disposable podman container (p21-uat-23394, image
     registry.fedoraproject.org/fedora:latest already present, nothing pulled), removed afterwards with
     `podman rm -f`; `podman ps -a` then listed only the unrelated containers and the parallel
     tools-installer-e2e one. Nothing ran on the developer host. Inside: dnf install tmux git python3 ...,
     unprivileged user `tester`, `git archive HEAD` streamed to ~/workspace, uv from astral's install.sh,
     `uv sync`. Every run: `tmux new-session -d -s u -x 80 -y 20`, then
     `NO_COLOR=1 TERM=xterm-256color uv run --isolated --no-dev setup.py`; evidence is `tmux capture-pane -p`.
     Runs 2-4 put a slow `systemctl` shim first on PATH (/tmp/uat-bin/systemctl, container only, per 21-21-PLAN
     T-21-56: is-active -> `inactive` exit 3, is-enabled -> exit 1, list-unit-files -> exit 0, every other verb
     sleeps 15 s and exits 0) so the on-by-default daemon apply and the daemon teardown hold the lock long enough
     to press keys. No Homebrew in the container (brew-only tools read `–`). -->

## Current Test

[testing complete]

## Tests

### 1. NO_COLOR 80x20: every view renders without colour-only cues, footer on the last row, status row above it, refusals fit one row
expected: marks/glyphs carry state (✓ ○ ✗ ↑ ≈ …, ● [on] / ○ [off] / ! [drift]); footer on row 20; status row visible above it on every view; the longest refusal fits one row; only the five known 80x20 layout items deviate (todo 2026-11-03-fix-80x20-layout-gaps-found-by-the-phase-21-tui-check).
result: issue
evidence: |
  Views 1, 2, 3, 4, 5, 6 and the ctrl+p palette all rendered. Footer was on row 20 in every capture; row 19 is the status row.
  - Tiers: legend row `✓ ok · ↑ update · ≈ config · ! broken · ○ missing · … checking · – unavailable`; rows read `○` / `–` / `✓  0.9.1  GitHub release`; detail `✓ ok — installed via GitHub release`. Every state reads from the glyph and the word.
  - Policies: `○ [off]  pip/npm ban`, `● [on]   claude skip-permissions` (after space, then re-entering the view), and `! [drift]  Background tmpdir cleanup` with the detail `Drift: this installer enabled it, but it is not active now. space applies it again.` (units on disk, shim says inactive). The State column widened to 9 cells for drift, as specified.
  - Uninstall: groups `── removable here (2)`, `── managed elsewhere (4)`, `── nothing to do (85)`, `── environment (2)`; the Health column shows `✓` / `○` / `–` / `…`.
  - ctrl+p: a palette with the six views (`System - prerequisites a fresh machine needs first` … `Policies - pip/npm ban and env tweaks`) fits inside 80 columns.
  - Refusals, each on row 19 with the footer on row 20: `A daemon apply is running; wait for it to finish. Navigation still works.` (73 cells) for `u` on System and for space on Policies, and `A removal is running; wait for it to finish. Navigation still works.` (68 cells) for `u` on User and for enter on Uninstall. The longest refusal (`A pnpm reinstall …`, 75 cells) was not triggered because pnpm is not installed in the container.
  - The five known items reproduced: tab bar `[6] Policie` (`[6] Polic` on Doctor); Doctor scrolls as one card with a scrollbar; Uninstall badge cut at `enter removes marked items (you'll`; tier columns cut (`Wha`, `What gets re`); Doctor hint text.
  NEW deviations, not in the known five:
  (a) At 80x20 the Policies table viewport shows exactly one policy row at a time (row 6; the rest only appear by scrolling with Down).
  (b) After a Policies toggle, the three-line status (`claude skip-permissions enabled.` / `…: written to ~/.myshellrc` / `Open a new shell, or run …`) pushes the table and its header off screen. The screen gains a scrollbar on the footer row (`q quit      ▇▇`), and the toggled row's `● [on]` is not visible until you leave and re-enter the view.
  (c) On Uninstall the removal summary `1 removed` rendered on row 18 with row 19 blank, so the status took two rows and the table lost one visible row.

### 2. Real removal of an installer-owned tool from Uninstall
expected: `Removing…` and pending `…` marks while it runs; count line `1 removed`; the row leaves the removable section; the tier row shows ○ after the follow-up pass; the receipt file is gone.
result: pass
evidence: |
  Installed duf and hexyl (github_release, User tier) with the real installer: `Install plan — 2 will install` → `Summary — 2 installed` (`✓ duf installed`, `✓ hexyl installed`, `hexyl: sha256 ✓`). The tier then showed `[ ]  P2   duf  sysinfo  both  ✓  0.9.1  GitHub release`, and Uninstall showed `── removable here (2)` with `[ ]  duf  ✓  sysinfo  installer  /home/tester…`.
  Marked duf, pressed enter, got the modal `Remove 1 tool(s)?` / `This deletes installed artifacts and is not undoable.` / `enter remove · esc cancel`, and confirmed with enter. Frames were captured every 50 ms:
  - frame 2 (≤100 ms): every Health cell reads `…` (duf, hexyl, uv, bat, git); status row `1 removed`.
  - frame 5: duf moved to `nothing to do` (`duf  ○  sysinfo  —  —`), detail `not installed`, without navigating. The top of Uninstall reads `── removable here (1)` / `[ ]  hexyl  ✓`.
  - Opening view 2 showed `[ ]  P2   duf  sysinfo  both  ○` and `○ not installed — no manager claimed the tool`.
  - Disk: `receipts/` held only `hexyl.json` (duf.json gone); `~/.local/bin/duf` and `~/.local/opt/duf` were gone.
  This single-tool removal finished in under 50 ms, so `Removing…` was not visible here. It was caught in the slow removals of test 3 (status row 19 `Removing…`, and the User tier showed `[ ]  P2   hexyl  view  both  …` with detail `… checking…` while hexyl was being removed).
  Observation: after the removal, every row showed `…` for one frame, not only the removed tool, because the whole cache is invalidated by the follow-up pass. It settles at once.

### 3. Quit during a removal: q waits, a second ctrl+c forces the exit, ctrl+q behaves like q
expected: `Waiting for the removal to finish…`, then the app exits when the removal ends; a second ctrl+c exits at once and prints `Quit before the removal finished; some files may remain.`; ctrl+q is the same as q.
result: pass
evidence: |
  The slow removal was hexyl plus the `shell tweaks + background jobs` env row (the daemon teardown issues two systemctl calls of 15 s each through the shim). Confirm modal: `Remove 1 tool(s), the shell tweaks?`.
  - q (run 2): status `Removing…` → q pressed at 20:33:07 → status `Waiting for the removal to finish…` (row 19, footer row 20) → the app exited about 28 s later, after the shim's `daemon-reload` (20:33:20 + 15 s) finished. Terminal: `Aborted.` / `EXIT=0`. Afterwards the units, the helper and the `daemon-linux:decided` block were all gone.
  - Second ctrl+c (run 3): `Removing…` → `u` on User → `A removal is running; …` → enter on Uninstall → same refusal → first ctrl+c → `Waiting for the removal to finish…` → second ctrl+c at 20:37:06, while `disable --now` (started 20:36:59) was still sleeping. Within 1 s the terminal showed `Quit before the removal finished; some files may remain.` / `No duplicate PATH lines found in your shell rc files.` / `EXIT=0`. What remained was the truth the message warns about: `~/.config/systemd/user/tools-installer-prune-tmp.{service,timer}` and `~/.local/bin/tools-installer-prune-daemon` were still there; hexyl's receipt and link were gone.
  - ctrl+q (run 4, tweaks row only): `Removing…` → ctrl+q at 20:38:11 → `Waiting for the removal to finish…` → the app exited about 29 s later, after `daemon-reload` finished. Terminal: `Aborted.` / `EXIT=0`. It behaves like q.

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Every view fits 80x20 with only the five known layout deviations"
  status: failed
  reason: "Three more 80x20 layout deviations: (a) Policies shows one table row at a time; (b) a three-line toggle status scrolls the Policies table off screen and puts a scrollbar on the footer row; (c) the Uninstall summary `1 removed` takes two status rows."
  severity: minor
  test: 1
- truth: "`Removing…` stays on the status line while the removal worker runs"
  status: failed
  reason: "Pressing space on Uninstall during a removal (run 2) toggled the row mark and cleared the status row. `Removing…` disappeared while the worker was still running (q pressed one second later still had to wait about 28 s)."
  severity: minor
  test: 3
- note: "A forced quit with an unfinished removal exits with code 0 (`EXIT=0`). The spec gives no exit code; this is recorded, not judged."
- not covered: "The 75-cell `A pnpm reinstall …` refusal (pnpm absent), and `Policies shows a removed ban OFF` (the pip/npm ban was not enabled, then removed, in this session)."
