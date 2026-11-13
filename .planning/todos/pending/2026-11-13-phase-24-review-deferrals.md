---
created: 2026-11-13
source: .planning/phases/24-onboarding-through-the-skill-and-e2e/24-REVIEW.md (Deferred)
---

# Phase 24 review deferrals

- **Tuning of tools the full uninstall keeps (deep MR-02):** Alacritty's keybindings region and the
  `terminal-tuning-alacritty` record outlive a full uninstall when Alacritty is distro-owned (the
  installer tunes any present Alacritty but strips only with its own removal). Decide, for every install
  tuning, whether "uninstall everything" reverts tuning of tools it keeps; apply one rule across tuners.
- **Build size and time under `/tmp` (deep LR-05, ponytail):** the Alacritty build tree sits in host
  `/tmp` (tmpfs on Fedora/Debian 13, possibly `noexec`). Measure size and time from the user's UAT
  test 6 run, then set the step timeouts from data and add a free-space/noexec pre-flight with a clear
  message.
- **curl `--retry-all-errors` floor (deep LR-02):** needs curl >= 7.71; supported platforms ship newer,
  but a probe-and-fallback would make an old curl fail clearly instead of every script install failing.
- **Stale `.tools-installer.old` restore (product fix F9 `shortcut:`):** an interrupt before the first
  move could restore a stale `.old` from an earlier failed rollback; clear stale `.old` before staging.
- **Security LOWs (24-SECURITY.md residuals R1, R3):** repeat the user-binary check right before
  `_swap`; snapshot image IDs, not names, so an image the user pulls mid-build is never removed.
