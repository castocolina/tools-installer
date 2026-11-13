---
phase: 24-onboarding-through-the-skill-and-e2e
status: pending
tested_at: not yet run
environment: >-
  The user's own Bazzite host (a real machine). The user runs this file; agents never run it.
  The container proofs are recorded in 24-08-SUMMARY.md and are not repeated here.
source: [24-SPEC.md R9 (ONB-05), 24-SPEC.md R2, R3, R6 (ONB-02, ONB-07), 24-CONTEXT.md D-17, D-18, D-19, D-29, 24-08-PLAN.md Task 1]
---

# Phase 24 - Real-host UAT

Nine tests on your real host. Run them in order, one step at a time, with no other installer process open. Each test gives the exact expected result. Mark the result and write notes in the fields below. The plan closes only after you have recorded every result in this file (ONB-05).

## Before you start

- **Ordering.** Start only after the container runs recorded in `24-08-SUMMARY.md` have passed. The automated checks come first; this UAT comes last.
- **Concurrency.** Close every other installer process: other terminals running `make setup`, the wizard, or `setup.py`. Finish each step before you start the next.
- **Launch.** Open the catalog with `make setup`. Every launch first repairs installer-owned leftovers (AGENTS.md); that is expected.
- **Image pull notice.** Test 6 builds Alacritty in a throwaway Distrobox from `registry.fedoraproject.org/fedora-toolbox:44`. If that image is not in your podman store, test 6 pulls it there (a large download). The build removes it again afterwards, because this run pulled it. An image you already had is kept and named in the row detail.
- **Copy first.** Before test 6, copy `~/.config/alacritty` somewhere safe (if it exists). Test 8 compares your own keys with that copy.
- **Scope.** This UAT runs on this host only. See "Not covered by this UAT" at the end.

## Results

| # | Test | Result |
|---|------|--------|
| 1 | Run order and concurrency | pending |
| 2 | Owner on every tier after install | pending |
| 3 | A tier with nothing installed shows `○` | pending |
| 4 | Uninstall one installer-owned tool: its row shows `○` | pending |
| 5 | herdr: `default_shell` untouched, no `≈`, no ledger entry, a new pane runs zsh | pending |
| 6 | Alacritty built on this host | pending |
| 7 | Alacritty: zsh shell, Alt+Left/Right, Ctrl+Shift+K | pending |
| 8 | Uninstall Alacritty: paths gone, your own keys kept | pending |
| 9 | D-19: keep an image you already had? | pending |

## Tests

### 1. Run order and concurrency

**Expected:** Before the first step, no other installer window is open (no other `make setup`, wizard or `setup.py`). Tests 2 to 9 run one at a time, in order, and only after the container runs in `24-08-SUMMARY.md` passed.

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 2. Owner on every tier after install

**Steps:** Install one tool in each tier you can (system, user, ai) from the catalog. Reopen `make setup` and read the Owner column.

**Expected:** Every installed row in the system, user and ai tiers shows its owner (a non-blank value). A tool owned elsewhere (for example a Homebrew or rpm-ostree tool) shows that owner, not a blank. A row that reads `owner unknown` is an issue: record it. 23.2-UAT (O-8) saw this for claude after its native installer.

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 3. A tier with nothing installed shows `○`

**Steps:** Pick a tier (system, user or ai) where nothing from the catalog is installed. If every tier has something installed, mark this test as not applicable and say so in the notes.

**Expected:** Every row in that tier shows `○` (not installed).

**Result:** [ ] pass  [ ] issue  [ ] blocked  [ ] not applicable

**Notes:**

### 4. Uninstall one installer-owned tool

**Steps:** In the Uninstall view, select one tool that test 2 showed as installed by the installer (a small one is best) and confirm.

**Expected:** The tool is removed, and its row then shows `○`.

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 5. herdr: `default_shell` untouched (D-29)

**Setup:** You have hand-installed herdr and set your own `[terminal] default_shell` in herdr's config (`~/.config/herdr/config.toml`, or `$XDG_CONFIG_HOME/herdr/config.toml` when that variable is set). Before the launch, note the current value: `grep -n default_shell <that config file>`.

**Steps:** Launch herdr (from the catalog row, or by running `herdr`). Then check the four points below.

**Expected:**
- The `default_shell` line in herdr's config holds the same value as before the launch.
- The herdr row in the catalog shows no `≈`.
- Herdr's config ledger `~/.local/state/tools-installer/config/herdr.json` is absent, or holds no `default-shell` entry: `grep -c default-shell ~/.local/state/tools-installer/config/herdr.json` prints 0 (a missing file also passes).
- A NEW herdr pane runs zsh with your Oh My Zsh plugins loaded: `echo $ZSH_VERSION` prints a version, and an alias from one of your enabled plugins resolves. Panes that were already open keep the shell they started with.

The write of `default_shell` itself is proven in the container runs (D-29), not in this test.

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 6. Alacritty built on this host

**Marker:** `CONFIRM` unless the nested run recorded `TRACER_NESTED_INFEASIBLE` (24-08-SUMMARY.md), then `REQUIRED`. The orchestrator sets this marker after the nested run.

**Before you start:** check whether the image is already in your podman store: `podman image exists registry.fedoraproject.org/fedora-toolbox:44` (exit 0 means present). If it is absent, this test pulls it (a large download), and the build removes it afterwards because this run pulled it. If you already had it, it stays and the row detail names it.

**Steps:** Install Alacritty from the catalog. The build runs in a throwaway Distrobox and takes a while; the build time has not been measured yet. Wait for the row to finish.

**Expected:**
- `podman ps -a --format '{{.Names}}'` lists no `ti-cargo-` container.
- The image `registry.fedoraproject.org/fedora-toolbox:44` is gone if this run pulled it, or still there and named in the row detail if you already had it.
- These files exist: `~/.local/bin/alacritty`, `~/.local/share/applications/Alacritty.desktop`, `~/.local/share/icons/hicolor/scalable/apps/Alacritty.svg`, `~/.terminfo/a/alacritty` and `~/.terminfo/a/alacritty-direct`.
- Alacritty appears in the application menu and in search.
- `desktop-file-validate ~/.local/share/applications/Alacritty.desktop` prints nothing and exits 0.
- `infocmp alacritty` succeeds (the terminfo resolves through `~/.terminfo`).

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 7. Alacritty: zsh shell, word moves, clear scrollback

**Steps:** Open Alacritty. At the prompt, run `echo $ZSH_VERSION`, then type a few words and test the keys.

**Expected:**
- The shell is zsh (`echo $ZSH_VERSION` prints a version).
- Alt+Left and Alt+Right move the cursor by word at the zsh prompt.
- Ctrl+Shift+K clears the scrollback.

The Alt+arrow byte sequences were research assumptions, so this test is their real check.

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 8. Uninstall Alacritty

**Steps:** In the Uninstall view, uninstall Alacritty. Then compare `~/.config/alacritty` with the copy you made before test 6.

**Expected:**
- Every path from test 6 is gone: the binary, the desktop entry, the icon and both terminfo files.
- `infocmp alacritty` fails.
- `grep -n "tools-installer terminal-shell alacritty" ~/.config/alacritty/alacritty.toml` prints nothing (both installer regions are removed).
- `~/.config/alacritty` still holds your own keys and settings, unchanged from your copy.
- `podman ps -a --format '{{.Names}}'` lists no `ti-cargo-` container.

**Result:** [ ] pass  [ ] issue  [ ] blocked

**Notes:**

### 9. D-19: an image you already had

**Question:** If `registry.fedoraproject.org/fedora-toolbox:44` was already in your podman store before test 6, should the installer keep it (the shipped behaviour) or remove it?

**Expected:** Your answer is recorded here. The shipped behaviour keeps the image and names it in the row detail. Changing that is a code change and goes through a new plan, not a UAT fix.

**Result:** [ ] keep (shipped behaviour)  [ ] remove (needs a new plan)

**Notes:**

## Summary

- Total: 9
- Passed: 0
- Issues: 0
- Pending: 9

## Not covered by this UAT

- Debian and Arch hosts: covered only by the container runs in `24-08-SUMMARY.md`.
- macOS: not covered.
- herdr's sidebar workspace marker (the pinned plugin): not checked here; test 5 checks only `default_shell`.
