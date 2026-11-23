---
status: testing
phase: 32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp
source: [32-VERIFICATION.md]
started: 2026-11-21T15:00:00Z
updated: 2026-11-23T12:00:00Z
---

## Current Test

number: 1
name: Xcode CLT on a real Mac: missing state, present state, Update refusal, empty Uninstall
expected: |
  Missing shows `xcode-select --install` to run by hand; present shows no command; Update refused; Uninstall lists no action
awaiting: the owner's Mac or Bazzite host (no such host in the autonomous run; no agent may mark any of these passed)

## Tests

### 1. Xcode CLT on a real Mac: missing state, present state, Update refusal, empty Uninstall
expected: Missing shows `xcode-select --install` to run by hand; present shows no command; Update refused; Uninstall lists no action
why_human: Needs a Mac with and without the Command Line Tools; the probe path /Library/Developer/CommandLineTools/usr/bin/git is a Mac fact
result: [pending]

### 2. AWS install.sh on macOS (or the brew fallback)
expected: Installs under ~/.local/share/aws-cli without admin rights; the pkg `CurrentUserHomeDirectory` route is an assumption
why_human: Real Mac; registry comment marks it assumed
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23, run by the agent at the owner's direction. install.sh ran without admin rights and installed under ~/.local/share/aws-cli; uninstall left ~/.aws untouched.

### 3. Bruno cask on a Mac
expected: ~/Applications/Bruno.app; uninstall keeps ~/Documents/bruno
why_human: Real Mac; cask behavior
result: [pending]

### 4. Bruno AppImage launch on Bazzite
expected: Mounts through FUSE, runs (sandbox and display behavior); menu entry is follow-up 999.32
why_human: Container result is UNPROVEN (no FUSE in rootless podman, transcript 430723b2c2b1); reported, not gated
result: [pending]

### 5. gh-stack's data directory on macOS
expected: ~/.local/share/gh/extensions/gh-stack/manifest.yml exists after install
why_human: Path assumed on macOS; detection and removal depend on it
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23, run by the agent at the owner's direction. ~/.local/share/gh/extensions/gh-stack/manifest.yml existed after install and was removed on uninstall.

### 6. macOS agent hosts' MCP files
expected: Cursor, Copilot, OpenCode, Codex and Claude files take the playwright entry at the documented paths
why_human: Real Mac home layout
result: [pending]
evidence: Partial, 2026-11-23, on the owner's Intel Mac: the documented host paths resolve for Claude, Codex, OpenCode, Cursor and Copilot, and none holds a playwright entry yet; the install that writes the entry into each host is not yet run on this Mac.

### 7. Playwright with real Flatpak Chrome on Bazzite
expected: Env path exported only on Bazzite with the wrapper present; server launches Chrome
why_human: Container used distro Chromium (D-16); Flatpak Chrome is not in the box
result: [pending]

### 8. Each agent host loads the `playwright` server
expected: Claude, Cursor, Copilot, OpenCode, Codex list and start it
why_human: Needs each host application; files only are proven
result: [pending]

### 9. Claude plugin key spelling `enabledPlugins["playwright@claude-plugins-official"]` (assumption A7)
expected: The official plugin check matches the real key
why_human: Needs a real Claude install with the plugin
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23, run by the agent at the owner's direction. The official plugin check matched the key `playwright@claude-plugins-official`.

### 10. Pi manual `pi mcp add` step
expected: The hand-off text works in Pi
why_human: Pi has no ledger writer; manual step only
result: [pending]

### 11. Owner confirmation of the provisional decisions below (D-01, D-03/D-04, D-07, D-08, D-09, D-10/D-11, D-12/D-13, D-14, D-15, orchestrator decisions 1 to 10, review round items)
expected: Each confirmed, or reopened as a follow-up
why_human: Flagged provisional or needs confirmation in the plan summaries
result: [pending]
