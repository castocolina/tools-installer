# Phase 16 Discussion Log

Human-reference only — not consumed by downstream agents. See `16-CONTEXT.md` for the decisions themselves.

**Date:** 2026-09-24
**Areas discussed:** Owner vs registry conflict, How skill_pack state is learned, What a row says when it can't act, Foreign PATH lines

---

## Owner vs registry conflict

**Q: What should groovy's Owner column say when brew provably owns it but the registry declares it SDKMAN-exclusive?**
Options: Homebrew + warning / Homebrew, silently / Stay unknown, explain why
→ User (freeform): owner must follow the tool's real source path — SDKMAN has its own path, brew Cellar means Homebrew. Current "unknown" is wrong. → **D-01**

**Q: Should the row also flag that the catalog's policy is SDKMAN?**
Options: Detail pane note only / Visible row marker too / No mention at all
→ **Visible row marker too** → D-02

**Q: When you press `u` on groovy (owner Homebrew), what should happen?**
Options: Update via brew / Refuse, explain / Offer to migrate to SDKMAN
→ **Offer to migrate to SDKMAN** → D-03

**Q: Where should the brew→SDKMAN migration live?**
Options: Own phase, deferred / Inside phase 16
→ **Own phase, deferred** → D-04

**Q: Until migration exists, what should `u` do on an off-policy tool?**
Options: Update via brew / Refuse and explain
→ **Update via brew** → D-05

**Q: Same tool installed by two managers?**
Options: Active + "also via X" / Active only / Both, no preference
→ **Active + "also via X"** → D-06

**Q: Self-installed tools (bun, fnm, volta) Owner label?**
Options: "own installer" / The tool's name / Keep unknown
→ **"own installer"** → D-07

**Q: When should Owner still say unknown?**
Options: No proof + show the path / Rename to "unmanaged"
→ **No proof + show the path** → D-08

---

## How skill_pack state is learned

**Q: superpowers declared Pi-only but installed in Claude Code — which harnesses count?**
Options: Any harness / Only declared harnesses
→ User correction: "that sounds like you didn't research it well, superpowers can be installed in many agent hosts." Verified against upstream README: Claude Code, Antigravity, Codex App/CLI, Cursor, Factory Droid, Gemini CLI, Copilot CLI, Kimi Code, OpenCode, Pi. → **D-09** (fix the registry data; audit every skill_pack entry)

**Q: How should the catalog read a skill pack's state?**
Options: Disk first, CLI in background / Harness CLI only, cached / Disk only
→ **Harness CLI only, cached** → D-10

**Q: Harness with no list command?**
Options: Say "can't check <host>" / Treat as not installed there / Allow disk for those only
→ **Allow disk for those only** → D-11

**Q: Inst column while probing?**
Options: Last cached answer + stale "~" / "checking…" until done
→ **Last cached answer + stale "~"** → D-12

**Q: Owner column for a pack in several hosts?**
Options: List the hosts / Count only
→ **List the hosts** → D-13

**Q: How often re-run harness CLIs?**
Options: Every launch, in background / Reuse the version cache's TTL / Only on manual refresh
→ **Every launch, in background** → D-14

**Q: Which hosts' install instructions?**
Options: Hosts present on this machine / Let me pick the hosts / All supported hosts
→ User: "1. Add cursor to host list" → clarified and confirmed: hosts present on this machine, Cursor included, with host presence detected from disk as well as PATH (cursor/cursor-agent exist as shell functions here, not binaries). → **D-15**

---

## What a row says when it can't act

**Q: kitty is dimmed (assumed OS-image-owned) — how should the row look?**
Options: Dimmed + short reason / Selectable, enter explains / Hidden behind a filter
→ User correction: kitty is actually installed at `~/.local/bin/kitty` from the user's own `../kitty-setup` project. Live verification during discussion: `~/.local/bin/kitty -> ~/.local/kitty.app/bin/kitty` (kitty's own official userspace installer), no `/usr/bin/kitty`. → fed into **D-16** and **D-19**

**Q: Enter on an INSTALLED tool?**
Options: Outdated → update; current → say so / Always explain, never act
→ Option 1, **plus**: "no importa si esta instalado pero si tengo en esta tool algo de postinstall policies a aplicar se deben aplicar" (regardless of install state, post-install policies must apply) → **D-17**, **D-20**

**Q: mmdc's dangling pnpm shim?**
Options: Distinct "broken" state / Treat as not installed / Installed, note in detail
→ **Distinct broken state, offer reinstall/repair** → D-18

**Q: Add kitty's official userspace installer as the Linux method?**
Options: Yes, add it / No, leave it
→ User (freeform): yes in effect, and generalize — install location must be distinguished per OS and package nature (binary vs macOS `.app` vs Linux app bundle); audit other tools too → **D-19**

**Q: Row with truly no method on this platform?**
Options: Dimmed + short reason / Selectable, enter explains
→ **Dimmed + short reason** → D-16

**Q: When are post-install policies (re)applied?**
Options: Only on explicit selection / Every run that includes it
→ **Only on explicit selection** (sensitive actions still confirm; drag-in never re-proposes) → D-20

**Q: How should the registry declare per-OS install location?**
Options: Per method / Per tool, per OS table / Both
→ **Per method** (also doubles as ownership proof) → D-19

**Todo fold check:** matched `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md` (score 0.9) against the mmdc answer → **folded into D-18**.

---

## Foreign PATH lines

**Q: What should the installer offer for a foreign unguarded PATH line?**
Options: Offer to guard in place / Offer to strip where safe / Report only
→ **Offer to guard in place** → D-21

**Q: Lines inside another tool's marked block — touch them?**
Options: Never, name the owner / Guard them too
→ **Never, name the owner** → D-22

**Q: Backup before guarding a foreign rc line?**
Options: Yes, same pattern as 15.8 / No backup needed
→ **Yes, same `.tools-installer.old` pattern as 15.8** → D-23

**Q: When should guarding foreign lines run?**
Options: Doctor apply, opt-in per file / Doctor apply, one confirm for all
→ **Doctor apply, opt-in per file** → D-24

---

*Full decisions with rationale, reversibility, and canonical references: see `16-CONTEXT.md`.*
