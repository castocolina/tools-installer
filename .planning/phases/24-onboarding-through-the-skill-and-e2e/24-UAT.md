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
| 1 | Run order and concurrency | pass |
| 2 | Owner on every tier after install | issue |
| 3 | A tier with nothing installed shows `○` | pass |
| 4 | Uninstall one installer-owned tool: its row shows `○` | pass |
| 5 | herdr: `default_shell` untouched, no `≈`, no ledger entry, a new pane runs zsh | pass |
| 6 | Alacritty built on this host | pass |
| 7 | Alacritty: zsh shell, Alt+Left/Right, Ctrl+Shift+K | blocked (keypresses need the owner's hands); zsh and key mapping proven |
| 8 | Uninstall Alacritty: paths gone, your own keys kept | issue |
| 9 | D-19: keep an image you already had? | not run (owner decision) |

## Agent-run UAT

On 2026-11-14 an agent ran tests 1 to 8 (test 9 recorded as not run, owner decision). Tests 1 to 4 ran in a Fedora 44 container (`ti-uat-24-fedora`, image registry.fedoraproject.org/fedora:44 as the harness bootstraps it), driven through a herdr tab. Tests 5 to 8 ran on the real Bazzite host with `make setup` in the agent's own herdr tab, after backing up the rc files, herdr's config and `~/.local/state/tools-installer/`. The owner's own hands are still needed for: the KDE application menu and search entry (test 6), the Alt+Left/Right and Ctrl+Shift+K keypresses (test 7), the keep-your-own-keys path (test 8, the owner had no alacritty config), the keep-an-existing-image path (test 9), and macOS, Debian and Arch. The `frontmatter status` stays `pending` until the owner records test 7's keypresses and test 9.

Host side effects found by the closing diff (the host launch itself, not the tests):
- Every launch removed the legacy line `alias npx='pnpm dlx'` from `~/.myshellrc` and rewrote `~/.local/bin/npx` (the documented launch repair). Not restored: it is the installer's own repair. Backup: scratchpad `bak/home/.myshellrc`.
- The first launch turned on six schedule timers on the real host (cache cleanup and the claude, opencode, pi, cursor-agent and copilot updates). The agent turned those six off again in the Schedules view; `tmp cleanup` was already on and stays. `~/.local/state/tools-installer/schedules.json`, `schedules.log` and lock files remain, and the agent did not remove the runner script.
- herdr was adopted into a receipt (`receipts/herdr.json`), so it is removable in the Uninstall view.
- `~/.zshrc`, `~/.bashrc`, `~/.bash_profile`, `~/.zshenv`, `~/.profile` and `~/.config/herdr/config.toml` are unchanged; `~/.config/alacritty` and `~/.terminfo` are absent as before; no `ti-cargo-` container and no fedora-toolbox image remain.

## Tests

### 1. Run order and concurrency

**Expected:** Before the first step, no other installer window is open (no other `make setup`, wizard or `setup.py`). Tests 2 to 9 run one at a time, in order, and only after the container runs in `24-08-SUMMARY.md` passed.

**Result:** [x] pass  [ ] issue  [ ] blocked

**Notes:**
agent-run 2026-11-14 on the real host (processes) and in registry.fedoraproject.org/fedora:44 (container `ti-uat-24-fedora`). Capture: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/01-ps.txt`.
- Observed: `ps aux | rg -i 'setup.py|wizard'` on the host printed no process before the first step. The 24.3 agent's herdr tab and container were not touched (its `ti-uat-24.3-*` container was not present). No other installer window was open.
- Run order: container tests 3 (before installs), 2, 4 first, then host tests 5, 6, 7, 8, one step at a time. The container proofs in `24-08-SUMMARY.md` were already recorded.

### 2. Owner on every tier after install

**Steps:** Install one tool in each tier you can (system, user, ai) from the catalog. Reopen `make setup` and read the Owner column.

**Expected:** Every installed row in the system, user and ai tiers shows its owner (a non-blank value). A tool owned elsewhere (for example a Homebrew or rpm-ostree tool) shows that owner, not a blank. A row that reads `owner unknown` is an issue: record it. 23.2-UAT (O-8) saw this for claude after its native installer.

**Result:** [ ] pass  [x] issue  [ ] blocked

**Notes:**
agent-run 2026-11-14 in registry.fedoraproject.org/fedora:44 (container `ti-uat-24-fedora`, user `tester`, Homebrew + uv as in the harness). Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/02-system-after.txt`, `02-user-after.txt`, `02-ai-after.txt`, `02-install-done.txt`, `02-claude-detail.txt`, `02-brew-detail.txt`.
- Installed in one batch: direnv (system tier), claude via its native installer (user tier), sd (ai tier); jq was `manual` (the installer printed `sudo dnf install jq`; I ran it as root in the container, outside the installer). The native claude installer worked (2.1.325).
- Owner column after reopening the wizard: direnv `GitHub release`, sd `GitHub release`, jq `dnf`, unzip/zip/watch `dnf`, git `OS package`, uv `own installer`. All non-blank, and no row reads `owner unknown` (0 matches in the three captures).
- ISSUE: claude shows a blank Owner (same as 23.2-UAT O-8). The row detail reads `ok - the active binary at /home/tester/.local/share/claude/versions/2.1.325 is not attributable to any candidate`. The Uninstall view lists claude as `installer` (receipt matches), so the Uninstall view and the Owner column disagree. Reproduction: catalog, stage claude, install, quit, relaunch, open view 2: the claude row's Owner is empty.
- Also blank: brew (installed by Homebrew's own script, not the installer): same `not attributable to any candidate` detail; the Uninstall view lists it as `unknown`. On the real host the same blanks appear for brew, claude, codegraph and jq (Uninstall view `Installed via: unknown`).

### 3. A tier with nothing installed shows `○`

**Steps:** Pick a tier (system, user or ai) where nothing from the catalog is installed. If every tier has something installed, mark this test as not applicable and say so in the notes.

**Expected:** Every row in that tier shows `○` (not installed).

**Result:** [x] pass  [ ] issue  [ ] blocked  [ ] not applicable

**Notes:**
agent-run 2026-11-14 in registry.fedoraproject.org/fedora:44 (container `ti-uat-24-fedora`). Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/03-ai-before.txt`, `03-user-before.txt`, `03-remove-bat.txt`, `03-ai-before-bat-removed.txt`.
- The fresh container was not empty in any tier: git (user tier) and bat (ai tier) came from the base image as dnf packages. To get an empty tier I removed bat as root in the container (`podman exec ... dnf -y remove bat`; not an installer path) and relaunched.
- Observed: the AI tier (view 3) lists 11 rows (codegraph, graphify, puppeteer, fd, rg, ast-grep, sd, bat, eza, ...), and every one shows `○` with a blank Owner. Checked before any install.

### 4. Uninstall one installer-owned tool

**Steps:** In the Uninstall view, select one tool that test 2 showed as installed by the installer (a small one is best) and confirm.

**Expected:** The tool is removed, and its row then shows `○`.

**Result:** [x] pass  [ ] issue  [ ] blocked

**Notes:**
agent-run 2026-11-14 in registry.fedoraproject.org/fedora:44 (container `ti-uat-24-fedora`). Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/04-uninstall-view.txt`, `04-confirm.txt`, `04-uninstall-result.txt`, `04-ai-after-uninstall.txt`.
- Uninstall view (5) listed sd, direnv and claude under `removable here` (installed via `installer`). I marked only sd and confirmed ("Remove 1 tool(s)?").
- Observed: sd moved to `nothing to do` with `○`, `command -v sd` and `~/.local/opt/sd` are gone, and the AI-tier catalog row for sd reads `○`. Expected: `○`.

### 5. herdr: `default_shell` untouched (D-29)

**Setup:** You have hand-installed herdr and set your own `[terminal] default_shell` in herdr's config (`~/.config/herdr/config.toml`, or `$XDG_CONFIG_HOME/herdr/config.toml` when that variable is set). Before the launch, note the current value: `grep -n default_shell <that config file>`.

**Steps:** Launch herdr (from the catalog row, or by running `herdr`). Then check the four points below.

**Expected:**
- The `default_shell` line in herdr's config holds the same value as before the launch.
- The herdr row in the catalog shows no `≈`.
- Herdr's config ledger `~/.local/state/tools-installer/config/herdr.json` is absent, or holds no `default-shell` entry: `grep -c default-shell ~/.local/state/tools-installer/config/herdr.json` prints 0 (a missing file also passes).
- A NEW herdr pane runs zsh with your Oh My Zsh plugins loaded: `echo $ZSH_VERSION` prints a version, and an alias from one of your enabled plugins resolves. Panes that were already open keep the shell they started with.

The write of `default_shell` itself is proven in the container runs (D-29), not in this test.

**Result:** [x] pass  [ ] issue  [ ] blocked

**Notes:**
agent-run 2026-11-14 on the real Bazzite host, `make setup` in my own herdr tab (herdr was neither restarted nor relaunched). Backups: scratchpad `bak/home/`. Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/05-default-shell-before.txt`, `05-host-user-scroll-2.txt`, `05-new-pane.txt`, `05-herdr-detail-after.txt`, `closing-diff.txt`.
- Before: `8:default_shell = "/home/linuxbrew/.linuxbrew/bin/zsh"`. After the run: same line, and `~/.config/herdr/config.toml` is byte-identical to the backup (only herdr's own log, session and socket files differ).
- Ledger: `~/.local/state/tools-installer/config/` does not exist, so there is no `herdr.json` and no `default-shell` entry (a missing file passes; `grep -c` has nothing to count).
- herdr row at launch: `✓ 0.9.5`, Owner `GitHub release`, no `≈`. NOTE: later in the same session (after the Alacritty install and uninstall) the row read `≈`. Its detail says `herdr is not registered for factory-droid, herdr's sidebar markers are not set up`, which is about agent integrations and the sidebar marker, not `default_shell`. The row also became removable `installer` in the Uninstall view because the launch adopted the hand-installed binary (receipts/herdr.json, by design D-09; it matches the release digest). The owner should know that herdr is now removable from the Uninstall view.
- New pane in my tab (`w6:pM`, closed afterwards): `ZSH_VERSION=5.9.2`, `$SHELL=/home/linuxbrew/.linuxbrew/bin/zsh`, `ps` comm `zsh`, Oh My Zsh loaded (`ZSH=/home/bazzite/.oh-my-zsh`), plugin aliases resolve: `gst='git status'`, `gco='git checkout'`, `ga='git add'` (plugin `git`).

### 6. Alacritty built on this host

**Marker:** `REQUIRED` (set by the orchestrator 2026-11-13: the nested run recorded `TRACER_NESTED_INFEASIBLE`; the rootless inner podman of an unprivileged outer container cannot create the distrobox box, so this host test is the only real Alacritty build; see 24-08-SUMMARY.md).

**Before you start:** check whether the image is already in your podman store: `podman image exists registry.fedoraproject.org/fedora-toolbox:44` (exit 0 means present). If it is absent, this test pulls it (a large download), and the build removes it afterwards because this run pulled it. If you already had it, it stays and the row detail names it.

**Steps:** Install Alacritty from the catalog. The build runs in a throwaway Distrobox and takes a while; the build time has not been measured yet. Wait for the row to finish.

**Expected:**
- `podman ps -a --format '{{.Names}}'` lists no `ti-cargo-` container.
- The image `registry.fedoraproject.org/fedora-toolbox:44` is gone if this run pulled it, or still there and named in the row detail if you already had it.
- These files exist: `~/.local/bin/alacritty`, `~/.local/share/applications/Alacritty.desktop`, `~/.local/share/icons/hicolor/scalable/apps/Alacritty.svg`, `~/.terminfo/a/alacritty` and `~/.terminfo/a/alacritty-direct`.
- Alacritty appears in the application menu and in search.
- `desktop-file-validate ~/.local/share/applications/Alacritty.desktop` prints nothing and exits 0.
- `infocmp alacritty` succeeds (the terminfo resolves through `~/.terminfo`).

**Result:** [x] pass  [ ] issue  [ ] blocked

**Notes:**
agent-run 2026-11-14 on the real host, catalog row in my herdr tab. Before: image absent (`podman image exists` exit 1), Alacritty and `~/.config/alacritty` absent. Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/06-image-before.txt`, `06-plan.txt`, `06-install-result.txt`, `06-checks.txt`, `06-desktop-file.txt`.
- The run pulled the image, built in a throwaway distrobox (about 4 minutes from the install key to `Summary - 1 installed`) and printed `Untagged: registry.fedoraproject.org/fedora-toolbox:44`.
- `podman ps -a`: no `ti-cargo-` container. `podman image exists ...fedora-toolbox:44` exit 1 (gone, this run pulled it). Summary row detail is just `installed`.
- The five files exist: `~/.local/bin/alacritty` (68 MB), `Alacritty.desktop`, `Alacritty.svg`, `~/.terminfo/a/alacritty`, `~/.terminfo/a/alacritty-direct`.
- `desktop-file-validate`: no output, exit 0. `infocmp alacritty`: exit 0, "Reconstructed via infocmp from file: /home/bazzite/.terminfo/./a/alacritty" (resolves through `~/.terminfo`).
- Application menu and search: I could NOT open the KDE menu or search. What I proved: the entry is in `~/.local/share/applications/` (XDG_DATA_HOME is unset, so the default is `~/.local/share`, the same directory that holds code.desktop and other launchers KDE lists), with Type, Exec, TryExec, Icon, Name, Categories=System;TerminalEmulator. The owner should confirm it shows in the menu and search.

### 7. Alacritty: zsh shell, word moves, clear scrollback

**Steps:** Open Alacritty. At the prompt, run `echo $ZSH_VERSION`, then type a few words and test the keys.

**Expected:**
- The shell is zsh (`echo $ZSH_VERSION` prints a version).
- Alt+Left and Alt+Right move the cursor by word at the zsh prompt.
- Ctrl+Shift+K clears the scrollback.

The Alt+arrow byte sequences were research assumptions, so this test is their real check.

**Result:** [ ] pass  [ ] issue  [x] blocked

**Notes:**
agent-run 2026-11-14 on the real host. Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/07-run.txt`, `07-alacritty-toml-after.txt`, `07-bindkeys.txt`, `07-alacritty-window.png` (spectacle screenshot of the open window).
- Shell is zsh: `alacritty -e sh -c "zsh -ic ..." ` wrote `ZSH_VERSION=5.9.2` and `gst='git status'` to a file. Alacritty started with no `-e` runs `/home/linuxbrew/.linuxbrew/bin/zsh -l` as its child (process tree) with `SHELL=` the same zsh, because the installer wrote the `alacritty` region (`[terminal.shell] program = ".../zsh"`, `args = ["-l"]`) when the catalog regained focus after the install (message `Shell: alacritty now starts zsh`). The screenshot shows the Alacritty window with an Oh My Zsh prompt. Alacritty printed nothing on stderr (config parses).
- Config region `alacritty-keys`: Alt+Left sends `\u001bb` (ESC b), Alt+Right sends `\u001bf` (ESC f), Control|Shift+K runs `ClearHistory`. zsh binds `"^[b"` to `backward-word` and `"^[f"` to `forward-word` (`bindkey`), so the bytes match the editor bindings.
- NOT proven: real Alt+Left/Right word moves and the Ctrl+Shift+K scrollback clear in a live window. `ydotool` and `/dev/uinput` exist, but a synthetic key goes to whichever window has focus (the owner's), so I did not use it. These two checks are blocked: needs the owner's hands.

### 8. Uninstall Alacritty

**Steps:** In the Uninstall view, uninstall Alacritty. Then compare `~/.config/alacritty` with the copy you made before test 6.

**Expected:**
- Every path from test 6 is gone: the binary, the desktop entry, the icon and both terminfo files.
- `infocmp alacritty` fails.
- `grep -n "tools-installer terminal-shell alacritty" ~/.config/alacritty/alacritty.toml` prints nothing (both installer regions are removed).
- `~/.config/alacritty` still holds your own keys and settings, unchanged from your copy.
- `podman ps -a --format '{{.Names}}'` lists no `ti-cargo-` container.

**Result:** [ ] pass  [x] issue  [ ] blocked

**Notes:**
agent-run 2026-11-14 on the real host, Uninstall view. Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/08-uninstall-view.txt`, `08-uninstall-result.txt`, `08-checks.txt`, `08-infocmp.txt`, `closing-diff.txt`.
- I marked only alacritty (the dialog said `Config kept: alacritty.`; I did not press `c`) and confirmed. Removed: the binary, the desktop entry, the icon, `~/.terminfo/a/alacritty` and `alacritty-direct` (all `No such file`; the empty `~/.terminfo` is gone too). `grep -n "tools-installer terminal-shell alacritty"` finds nothing (the config file itself was removed). `podman ps -a` lists no `ti-cargo-` container.
- ISSUE (test wording, not the product): `infocmp alacritty` still exits 0 on this host. It now resolves from `/usr/share/terminfo/a/alacritty` (`ncurses-base-6.6-3.fc45`) and the Homebrew ncurses tree, so the bullet "infocmp alacritty fails" cannot hold on Bazzite. Installer files are gone: `infocmp -A ~/.terminfo alacritty` exits 1. Suggest rewording the bullet to that command.
- Leftover (minor, product): the uninstall left an empty `~/.config/alacritty` directory (created at 08:56 by the install). Before the run the directory did not exist, so I removed it with `rmdir` to match the backup.
- "Your own keys kept" was NOT exercised: the owner had no `~/.config/alacritty` before the run (nothing in the backup), so the installer created the toml and removed it again. The keep-own-config path is untested on this host.

### 9. D-19: an image you already had

**Question:** If `registry.fedoraproject.org/fedora-toolbox:44` was already in your podman store before test 6, should the installer keep it (the shipped behaviour) or remove it?

**Expected:** Your answer is recorded here. The shipped behaviour keeps the image and names it in the row detail. Changing that is a code change and goes through a new plan, not a UAT fix.

**Result:** not run (owner decision)  ([ ] keep (shipped behaviour)  [ ] remove (needs a new plan))

**Notes:**
agent-run 2026-11-14. Not run (owner decision). Fact for the owner: `registry.fedoraproject.org/fedora-toolbox:44` was NOT in the podman store before test 6 (`podman image exists` exit 1, capture `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/24/06-image-before.txt`), so this run pulled it and the installer removed it afterwards. The keep-an-existing-image path was not exercised.

## Summary

- Total: 9
- Passed: 5 (tests 1, 3, 4, 5, 6; test 6 has the menu/search entry unverified)
- Issues: 2 (tests 2 and 8)
- Blocked: 1 (test 7, keypresses); not run (owner decision): 1 (test 9)
- Pending: 0

## Not covered by this UAT

- Debian and Arch hosts: covered only by the container runs in `24-08-SUMMARY.md`.
- macOS: not covered.
- herdr's sidebar workspace marker (the pinned plugin): not checked here; test 5 checks only `default_shell`.
