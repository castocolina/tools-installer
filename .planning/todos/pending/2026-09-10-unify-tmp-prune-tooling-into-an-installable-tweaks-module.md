---
created: 2026-09-10T18:03:17.924Z
title: Unify tmp-prune tooling into an installable Tweaks module
area: tooling
severity: major
files:
  - scripts/prune-user-tmpdir.sh
  - /var/home/bazzite/git/personal/ai-kit/tmp/scripts-linux-tmp-prune/cleanup-bun-tmp-cache.sh
  - /var/home/bazzite/git/personal/ai-kit/tmp/scripts-linux-tmp-prune/cleanup-bun-tmp-cache.service
  - /var/home/bazzite/git/personal/ai-kit/tmp/scripts-linux-tmp-prune/cleanup-bun-tmp-cache.timer
  - /var/home/bazzite/git/personal/ai-kit/tmp/scripts-linux-tmp-prune/51-bun-cache-redirect.conf
  - /var/home/bazzite/git/personal/ai-kit/tmp/scripts-linux-tmp-prune/install.sh
---

## Problem

When open-gsd launches a cross-AI (opencode) goal/autonomous run, opencode's
runtime (Bun — a JS/TS runtime, not Node, despite superficially similar
tooling) writes its runtime-transpiler-cache (native `.so`/`.node` artifacts)
either to `$BUN_RUNTIME_TRANSPILER_CACHE_PATH` if set, or — for invocations
that don't inherit that env var (see oven-sh/bun#24695) — straight into the
OS temp dir. A killed/crashed Bun process orphans these files (the kernel
does not clean them up on exit). Over a day-long autonomous run this fills:

- **macOS:** `$TMPDIR` (`~/…/T/`), which can reach 100GB+ in a day.
- **Linux (Bazzite):** `/tmp`, which is a tmpfs with a small per-user quota
  (~12GB here), causing `EDQUOT` write failures across the whole system once
  full — not just for opencode/Bun.

Two independent, non-reusable scripts already solve pieces of this:

1. **This repo's `scripts/prune-user-tmpdir.sh`** — dry-run/`--apply` prune
   of orphaned `*.dylib`/`*.node`/gitid/`Codex` temp files by age, manual
   execution only, no daemon, no env-var mitigation.
2. **`ai-kit`'s `tmp/scripts-linux-tmp-prune/` bundle** (Linux-only today) —
   a real solution already running successfully on this machine:
   - `51-bun-cache-redirect.conf` — sets
     `BUN_RUNTIME_TRANSPILER_CACHE_PATH` via `~/.config/environment.d/` to
     redirect Bun's cache off `/tmp` onto a real disk-backed dir
     (`~/.cache/bun/transpiler-cache`), avoiding orphaning in the first
     place for invocations that inherit the env var.
   - `cleanup-bun-tmp-cache.sh` + `.service` + `.timer` — a systemd **user**
     oneshot service run every 10 minutes via a systemd timer, removing
     orphaned `/tmp/.{16 hex}-{8 digit}.{so,node}` files older than 10
     minutes (safety net for the invocations that don't inherit the env
     var). Confirmed working: `/tmp` stays under 1% usage on this host.
   - `install.sh` — manual, one-off installer (`sudo install` + `systemctl
     enable --now`), no uninstall path, Linux-only, not integrated with this
     project at all.

Neither script is reusable/cross-platform, neither is wired into this
project's own tooling, and there is no equivalent for macOS (would need
`launchd`, not systemd).

## Solution

Build one dedicated module in `tools-installer` (not two competing scripts)
that:

1. **Env-var wiring** — extend the existing "add stuff to myshellrc"
   mechanism (however this project currently wires shell-rc env vars) to
   also write the `BUN_RUNTIME_TRANSPILER_CACHE_PATH` redirect — on Linux via
   `~/.config/environment.d/` (systemd-user convention, as ai-kit's file
   does) and find/confirm the macOS-equivalent mechanism (launchd env vars
   don't work the same way as systemd's `environment.d`; likely needs to go
   through the shell rc files directly on macOS instead).
2. **Daemon install/uninstall, not manual scripts** — a background cleanup
   service the user never has to run by hand:
   - **Linux:** systemd user timer + oneshot service (reuse ai-kit's
     `cleanup-bun-tmp-cache.sh` logic/regex as the tested baseline — it's
     confirmed working, keep `/tmp` reliably under 1%).
   - **macOS:** `launchd` equivalent (a `LaunchAgent` plist with a
     `StartInterval`), covering `$TMPDIR` instead of `/tmp`, reusing
     `scripts/prune-user-tmpdir.sh`'s matching patterns as the tested
     baseline for macOS's file-naming conventions
     (`*.dylib`/`*.node`/gitid-stage/Codex temp dirs).
   - Both paths must be genuinely installable **and uninstallable** — no
     leftover systemd/launchd units after uninstall.
3. **Tweaks view integration** — surface this as a toggle-able module in the
   installer's Tweaks view (install/uninstall, and ideally status: daemon
   active or not, current tmp/TMPDIR usage %), not a standalone script the
   user has to know exists and run from a terminal.
4. **`make doctor` integration** (added mid-discussion, explicit user ask —
   do not drop this from scope even though it wasn't in the original
   file list): doctor should inspect disk/partition state and emit a red
   warning when:
   - the cleanup daemon/service is not active/enabled, **and**
   - available disk space is below 30% (general case), **or**
   - on Linux specifically, `/tmp` usage exceeds 50% (tmpfs-quota-specific
     case, since a full `/tmp` breaks unrelated system writes, not just this
     project).
   Emphasize (extra visual weight, e.g. bold/red) when the daemon-inactive
   condition and the low-disk/high-tmp condition are both true at once —
   that's the actual failure scenario this whole todo exists to prevent.

**Code reuse / engineering notes from the user:** don't just copy-paste
ai-kit's Linux scripts and `prune-user-tmpdir.sh`'s macOS logic side by
side — build a single cross-platform module with OS-detection reused from
this project's existing platform-detection conventions (see Phase 12.3's
reusable container-tool detection script precedent in
`.planning/phases/12.3-container-e2e-verification-of-the-reconciled-branch-real-end/12.3-CONTEXT.md`
D-02 — same "detect once, reuse" principle applies here), rather than one
script per OS with duplicated logic. Consider whether this module should
register itself through the postinstall/skill_lifecycle conventions being
formalized in Phase 12.4
(`.planning/phases/12.4-tool-onboarding-research-skill-and-registry-postinstall-audi/`)
since it is itself a new installable capability with per-OS setup needs.

User explicitly rejected "run the scripts manually" as an acceptable outcome
— the daemon/service model (already proven working on Linux via ai-kit) is
the required shape, on both platforms.
