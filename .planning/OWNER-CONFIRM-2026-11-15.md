# Owner confirmation list (2026-11-15)

On 2026-11-15/16 every phase from 17 through 25 was verified, with real screens captured in disposable
containers through herdr. Each finding was classified with jev-fast-decision; trivial findings were decided or
fixed. Phases 17 to 25 now read complete, and all 115 requirements are marked complete. Phase 25 (LEAN-01..04)
was run at the owner's request and left no owner-only item.

This list holds only what automation cannot prove. Each item names its source.

## Checks on your own machine or desktop

1. **Phase 21:** run the wizard on your real machine. In Uninstall, remove one installer-owned tool and one
   managed-elsewhere tool. Toggle a Policies row, open Doctor and quit with `q`. Every screen should show the
   current truth. (21-VERIFICATION.md)
2. **Phase 22:** in Uninstall, remove a tool that has a receipt on your real host. Then select the manual-handoff
   command line with the mouse and copy it in a real terminal emulator. (22-VERIFICATION.md)
3. **Phase 23:** on your real desktop, open new kitty, WezTerm and Konsole windows; each should start zsh. The
   VS Code integrated terminal should open zsh, and VS Code should load the edited settings.json.
   (23-VERIFICATION.md H2, H3)

## Taste or decision calls

4. **Phase 23 H6:** check the warn colour of the `Shell:` notice that appears after a run.
5. **Phase 23 H8 (CONF-08):** pi shows a static note and does not detect whether a permission extension is
   installed. Either accept the static note or schedule detection. (`installer/render.py` around line 357)
6. **80x20 status cap:** at 80x20 a long Policies status is cut at 4 rows with `…`. That cut can drop the last
   advice, for example "open a new shell". Either accept the cut or ask for the full text in the detail panel.
   (todos/completed/2026-11-03-fix-80x20-layout-gaps-...md, "Visual recheck")
7. **Todo and backlog decisions** from .planning/todos/TRIAGE-2026-11-15.md:
   - Codegraph replacement, section 4: revive the `AGENTS-TOOLING.md` writer, or declare that block
     user-owned. Then schedule a phase for it.
   - 999.7: re-run or drop the 16-UAT tests 2 to 4. Branch protection is now applied.
   - Decide whether a full uninstall reverts the tuning of the tools it keeps. (Phase 24 deferral)
   - `xcode-clt`: delegate to brew `install.sh`, or use a `softwareupdate` flow.
   - iTerm2: confirm the "Show Focus Cursor" setting and the identity of the agent-collaboration extension.
   - Colima: should docker be `recommends` or `requires`?
   - Pi sync: does the pi sync script belong in the installer at all?
   - gitnexus: is it still wanted once codegraph is replaced?

## Deferred: macOS with no CI path (owner rule, 2026-11-14)

- 18: install the pinned draw.io app on a real Mac and check the `/usr/bin/java` and `/usr/bin/git` stubs.
- 22: human items 3 and 4.
- 23 H7: darwin detection, `update.mode`, `defaultProfile.osx`.
- 24.1: UAT test 8, the git stub dialog without Command Line Tools.
- 24.2: UAT test 8 and all launchd behaviour.
- 24.3: UAT test 5, drawio-desktop on macOS.
- 24.4 and 24.5: macOS paths; claude, codex and kitty installed from casks; mmdc through bun with brew.

## Done on your behalf this session (no action needed)

- Branch protection on main (CI-02) was applied after you approved it. Undo with:
  `gh api -X DELETE repos/castocolina/tools-installer/branches/main/protection`.
- Issue #5 (registry-drift) is left open for the new workflow step to close on its next clean run, as you chose.
- The 80x20 layout gaps, the Uninstall ellipsis, the `~/.myshellrc` blank-line residue, stale PATH entries after
  an uninstall, and the Policies status overflow were all fixed test-first and checked on real screens.
- Not ours: about 50 `<defunct>` `rg`/`git` processes belong to your `opencode serve --service` daemon
  (`opencode-pty`). Restarting that user service clears them.
