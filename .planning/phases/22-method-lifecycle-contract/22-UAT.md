---
phase: 22-method-lifecycle-contract
status: issues_found
tested_at: 2026-11-04T10:36:00Z
environment: >-
  Disposable podman container ti-uat-22 (registry.fedoraproject.org/fedora:latest, Fedora 44, amd64),
  built like scripts/container-e2e-verify.sh bootstrap (dnf prereqs + tmux, user tester with the
  e2e sudoers entry, Homebrew-on-Linux + uv bootstrapped, host gh token as GITHUB_TOKEN),
  repo copied with `git archive HEAD` (4727d2f), scratch HOME /home/tester. TUI driven with tmux
  at 80x20 with NO_COLOR=1; evidence is `tmux capture-pane -p`. Container removed with
  `podman rm -f ti-uat-22`; `podman ps -a` afterwards listed only unrelated containers and the
  parallel tools-installer-e2e one. Nothing ran on the developer host.
source: [22-UI-SPEC.md, 22-SPEC.md, 22-REVIEWS.md (C-02)]
---

# Phase 22 — Container UAT

All six user-facing behaviours pass. Three low-severity findings are recorded below; none blocks
the phase, so they are returned for triage, not fixed here.

## Setup

- Headless installs: `setup.py --categories data,view --yes` (yq, glow, eza, … via GitHub release;
  jq planned `manual`), `--categories git,pkg-mgr --yes` (gh, delta, …; pnpm and volta scripts;
  glab planned `manual`), both exit 0.
- TUI install (User/AI tabs, space + enter): graphify (uv-tool, L1 uv), mmdc + puppeteer (pnpm,
  L1 pnpm), sublime (pinned tarball). `Summary — 4 installed, 2 skipped`, `Done.`
- Config dirs created by hand: `~/.config/gh/config.yml`, `~/.config/glow/glow.yml`.

## Results

| # | Test | Result |
|---|------|--------|
| 1 | Uninstall rows by removal level; native-owned row shows the package hint, no command | PASS |
| 2 | `c` toggle: `[c]` + `config + ` + detail sentence; refusal on a tool without `config_paths` and on a managed-elsewhere row | PASS |
| 3 | ConfirmUninstall review (`runs …`, `Config deleted too:`, `Config kept:`, pnpm group warning); esc removes nothing; enter removes; flagged config gone, unflagged config kept | PASS |
| 4 | CLI `--uninstall --yes`: `Config kept` block, config never deleted, exit 0; hand-removed uv tool reported `already removed`, exit 0 (C-02) | PASS |
| 5 | Native-only install → `manual — you run: …` with the exact command; nothing runs | PASS |
| 6 | `u` on a pinned app (sublime) refuses with the pinned message | PASS |

## Evidence

### 1. Removal level copy (80x20; the full `What gets removed` text read once at 200 cols)

```
 Sel  Tool                       Health  Cat       Installed via  What gets removed
 [ ]  yq                         ✓       data      installer      /home/tester/.local/bin/yq
 [ ]  graphify                   ✓       dev       uv             uv tool uninstall graphifyy
 [ ]  mmdc                       ✓       diagram   pnpm           pnpm remove --global @mermaid-js/mermai…
 [ ]  puppeteer                  ✓       dev       pnpm           pnpm remove --global puppeteer
      watch                      ✓       shell     dnf            —
```

Detail bar per row:

```
installed by this installer: receipt matches                                   (yq, L2)
installed by this installer through uv: receipt matches — runs `uv tool uninstall graphifyy`
installed by this installer through pnpm: receipt matches — runs `pnpm remove --global @mermaid-js/mermaid-cli`
installed by this installer through pnpm: receipt matches — runs `pnpm remove --global puppeteer` · required by mmdc
installed by this installer: receipt matches · config kept: none on disk (c deletes it too) · required by mmdc, puppeteer, pi, openspec   (pnpm)
managed by dnf — this installer will not remove the package procps-ng — found at /usr/bin/watch
managed by OS package — this installer will not remove the package git-core — found at /usr/bin/git · required by oh-my-zsh
```

The native rows (`watch`, `git`, `bat`) name the package and carry no command, backtick or argv.

### 2. `c` toggle

gh before / after `c` (80x20):

```
 [ ]  gh                         ✓       git       installer      /home/tester
 installed by this installer: receipt matches · config kept: ~/.config/gh (c
 deletes it too)
---
 [c]  gh                         ✓       git       installer      config + /ho
 installed by this installer: receipt matches · config deleted too:
 ~/.config/gh (c keeps it)
```

glow marked with space only: `… · config kept: ~/.config/glow (c deletes it too)`.
Refusals (status line, nothing changed):

```
 yq declares no config to delete.
 brew cannot be removed here, so its config stays.
```

### 3. ConfirmUninstall (gh `[c]`, glow `[x]`, yq `[x]`, mmdc `[x]`)

```
          │  Remove 4 tool(s)?                                       │
          │  This deletes installed artifacts and is not undoable.   │
          │  mmdc: runs pnpm remove --global                         │
          │    @mermaid-js/mermaid-cli                               │
          │  Config deleted too:                                     │
          │    ~/.config/gh (gh)                                     │
          │  Config kept: glow.                                      │
          │  Warning: pnpm group mmdc: removing                      │
          │    @mermaid-js/mermaid-cli removes the whole group,      │
          │    puppeteer included.                                   │
          │  enter remove · esc cancel                               │
```

After `esc`: receipts `gh.json glow.json mmdc.json yq.json` present, binaries present,
`~/.config/gh/config.yml` and `~/.config/glow/glow.yml` present.
After `enter`, `enter`:

```
 4 removed
 Config deleted for gh.
 Config kept for glow.
```

Disk: receipts gh/yq/glow/mmdc gone; `~/.local/bin/{gh,yq,glow}`, `~/.local/opt/{gh,glow}` and
`~/.local/share/pnpm/bin/mmdc` gone; `~/.config/gh` gone; `~/.config/glow/glow.yml` kept;
`pnpm list -g` shows only pnpm (the whole mmdc group went, as warned).

### 4. CLI `--uninstall --yes`

glow reinstalled headless first (its config still on disk), then `uv tool uninstall graphifyy`
by hand (`Uninstalled 2 executables: graphify, graphify-mcp`), then:

```
The following will be removed:
  /home/tester/.local/opt/delta
  … (37 proven paths)
graphify: runs uv tool uninstall graphifyy
puppeteer: runs pnpm remove --global puppeteer
Warning: pnpm group mmdc: removing puppeteer removes the whole group, @mermaid-js/mermaid-cli included.
Not removed (tools-installer cannot prove it installed these); remove them
yourself if you want them gone:
  /home/tester/.local/bin/uv
  /home/tester/.local/bin/uvx
Config kept; only the Uninstall view deletes config (press c on a row):
  ~/.config/glow
graphify: already removed
puppeteer: already removed
EXIT=0
```

Afterwards the receipts directory is empty, `~/.local/opt` is empty, `~/.local/bin` holds only
the hand-installed uv/uvx, and `~/.config/glow/glow.yml` is still there.

### 5. Native-only → MANUAL

```
Install plan — 9 will install, 1 skipped, 1 manual
○ jq      manual — needs sudo (never run here); you run: `sudo dnf install jq`
Summary — 9 installed, 1 skipped, 1 manual
○ jq      manual — you run: `sudo dnf install jq`
jq — manual setup required:
  sudo dnf install jq
EXIT=0
```

Same for glab (`○ glab        manual — you run: `sudo dnf install glab``). `rpm -q jq glab`:
`package jq is not installed`, `package glab is not installed` — nothing ran, although the
container user has passwordless sudo.

### 6. `u` on pinned sublime (User tab, 80x20)

```
 [ ]  P3   sublime            editor    human  ✓       4215    tarball downloa
 cannot update sublime: pinned; update outside or re-pin
```

`~/.local/opt/subl` mtime unchanged (install time), so nothing was downloaded.

## Findings (not fixed; for triage)

**F-1 (low, copy) — pinned tool's detail contradicts the `u` refusal.**
Steps: install sublime, open User, cursor on sublime. Expected: the detail does not promise an
update path that `u` refuses (SPEC R7, UI-SPEC "`u` outcomes"). Actual detail:
`✓ ok — installed via tarball download · no latest version to compare against · latest version
cannot be determined for this install method — pressing u re-runs the same install path this
tool was originally installed with`, while `u` then prints `cannot update sublime: pinned; update
outside or re-pin`. Source: `version_notes` in `installer/version_status.py:933-937` adds the
sentence for every installer-owned tool with no latest, without checking `download.pinned_method`.

**F-2 (low) — a group co-member's receipt outlives a TUI group removal.**
Steps: install mmdc (pnpm group with puppeteer), remove only mmdc in Uninstall (the review warns
the whole group goes). Expected: after the removal, puppeteer is either retired with the group or
still offered as removable so its receipt can be retired. Actual: `puppeteer.json` stays in the
receipts directory, and the puppeteer row moves to `nothing to do` (`○`), so the TUI never offers
to retire it; only the CLI `--uninstall` later retires it (`puppeteer: already removed`).

**F-3 (low, copy) — the CLI pnpm group warning names a member that is already gone.**
Same state as F-2, then `--uninstall --yes`. Actual:
`Warning: pnpm group mmdc: removing puppeteer removes the whole group, @mermaid-js/mermaid-cli
included.` although mmdc and its package were removed earlier. `co_install_warnings`
(`installer/pnpm_globals.py:282`) reads only the catalog groups by design (no live pnpm query),
so the warning is stale whenever another group member is already removed.

**Observation (Phase 21 layout, not a Phase 22 change):** at 80x20 the Uninstall table is wider
than the pane: the header reads `What gets re` and cells are clipped at the pane edge without
`…` (`/home/tester`, `config + /ho`). The `[c]` cell and the `config + ` prefix are still visible,
and the detail bar carries the full sentence, so test 2 passes.

## Human-only

- True-colour look: `[c]` and `Config deleted too:` in bold red, `Warning:` and `manual` in
  yellow, the red modal border — this run used NO_COLOR=1, so only the words were checked.
- Copy-paste: one terminal selection of the run-report command line (`  sudo dnf install jq`)
  copies exactly the command, in a real terminal emulator with mouse selection.
- The Uninstall table at 80 columns in a real terminal (the clipped `What gets removed` column
  above) and how it reads at the user's usual width.
- macOS: `--greedy` cask update on `u`, brew L1 rows (`Homebrew` / `brew uninstall …`), the
  drawio-desktop pinned `u` refusal, `~/Library/Preferences/pnpm` config path.
- A real rpm-ostree / Bazzite host: the `rpm-ostree install …` MANUAL reason, and a
  non-writable brew prefix (`… is not writable by you; you run: …`).
- SDKMAN / Oh-My-Zsh vendor updaters on `u` (`updated oh-my-zsh`, `updated sdkman`) and the
  SDKMAN candidate hints, not exercised here.

## UAT fixes

Fixed after triage on `main` (from 83cb0dc). Each commit carries its tests, and
`make validate && make test` exit 0 on each one. The container behaviour is not re-run here;
the next `make e2e` / UAT run is its proof.

| Finding | Commit | Tests (RED before the fix → GREEN) |
|---------|--------|-------------------------------------|
| F-2 | eb14872 | `test_app::test_a_group_member_pnpm_already_removed_is_removed` (rewritten: printed `puppeteer: already removed`, now `puppeteer: removed with the mmdc group`), `test_app::test_a_tui_group_removal_retires_the_unselected_members_receipt` and `…_group_member_pnpm_still_lists_keeps_its_receipt` (RED: `SweepResult` had no `with_group`), `test_app::test_an_unreadable_listing_keeps_the_group_members_receipt` (fail-closed guard, green before and after), `test_wizard_app::test_a_member_removed_with_its_group_is_reported_after_the_counts` (RED: the status was not `2 removed` + the group line) |
| F-3 | dd73476 | `test_pnpm_globals::test_a_member_known_gone_is_not_named` (RED: no `present` parameter), `test_app::test_the_cli_group_warning_skips_a_member_already_gone`, `test_wizard_app::test_the_group_warning_skips_a_member_shown_absent` (RED: the review still showed `… @mermaid-js/mermaid-cli included.` for an absent mmdc) |
| F-1 | cae8aa5 | `test_version_status::test_a_pinned_install_note_matches_the_u_refusal` (RED: the note read `pressing u re-runs the same install path …`) |

- **F-2:** after a pnpm removal ran, the same run (`run_uninstall` and `perform_uninstall`)
  retires the receipt of every other declared group member that a fresh pnpm listing (the
  C-02 `manager_listing("node")` reader) no longer shows, and reports
  `<id>: removed with the <group> group` (CLI line; the Uninstall view adds it after the
  counts and counts the member as removed). An unreadable listing or a failed receipt delete
  retires nothing. A member retired this way is not removed again later in the run.
- **F-3:** after F-2 the stale state still arises from the product's own removal when the
  listing is unreadable at retirement time (fail closed keeps the member's receipt) or the
  receipt delete fails, so the restriction was applied. `co_install_warnings` takes a
  `present` predicate from the caller's frozen state: the CLI counts a receipt or the
  registry detection (`is_installed`), the Uninstall view its published row state (an unknown
  state counts as present). A member no catalog tool declares is still named; no live pnpm
  query is added.
- **F-1:** `version_notes` consults `update.update_refusal` (which checks
  `download.pinned_method`); a refused tool reads `… — u does not update it: pinned; update
  outside or re-pin`, matching the `u` refusal.
