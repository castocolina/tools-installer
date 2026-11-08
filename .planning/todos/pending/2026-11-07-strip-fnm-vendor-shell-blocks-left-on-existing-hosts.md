---
created: 2026-11-07
source: Phase 23.1 container e2e (rerun pass) + 23.2-06 Task 2 deferral
priority: low
---

# Strip fnm vendor shell blocks left on existing hosts

## Problem

fnm's upstream installer appends an indented, directory-tested block with `eval "$(fnm env ...)"` to
`~/.bashrc` / `~/.zshrc`. In the 23.1 container e2e every new bash then printed
`/home/tester/.bashrc: line 45: fnm: command not found`. The block also outlives the fnm binary, because its
`node-versions` store is kept on purpose. Phase 23.2 (plan 06, Task 2) stops new installs from writing the
block (`--skip-shell`), and the installer's own `command -v fnm`-guarded shell-init block replaces it. Hosts
that installed fnm before 23.2 keep the vendor block.

## Solution

An exact-shape matcher in `installer/rcclean.py` for fnm's vendor block, applied only where the installer
already cleans rc files it does not own (never at launch, per 23.2 D-18), with a scratch-rc test. It must
remove the block only when it matches fnm's installer output byte for byte.
