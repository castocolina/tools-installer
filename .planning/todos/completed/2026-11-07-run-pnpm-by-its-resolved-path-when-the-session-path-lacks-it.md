---
created: 2026-11-07
source: .planning/uat/2026-11-07-real-tty.md F-1
priority: medium
---

# Run pnpm by its resolved path when the session PATH lacks it

## Problem

When pnpm was installed after the terminal was opened, a later TUI install of mmdc shows
`pnpm skipped — already present` and then fails with `pnpm not found on PATH`. The installer finds pnpm by
its path (so the dependency counts as present) but executes it through the session PATH, which does not
contain it yet; the printed advice ("install pnpm") is wrong. After `source ~/.myshellrc` the same install works.

## Solution

Execute a dependency through the same resolved path the presence check used (or prepend its directory to the
child's PATH), and when a binary really is missing say so instead of advising a reinstall of a present tool.
Backstop: a scratch-HOME test where pnpm exists only under a receipt path absent from PATH.
