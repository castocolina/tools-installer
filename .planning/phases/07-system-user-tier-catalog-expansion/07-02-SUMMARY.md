---
phase: 07-system-user-tier-catalog-expansion
plan: 02
status: complete
commits:
  - aaddde1
  - 9084372
  - 08e4797
  - f155e4d
---

# 07-02: gnu-bash + Apple Containers — SUMMARY

Reconstructed from commit history (executed via cross-AI dispatch,
`opencode run --model router-env/my-coding`; this SUMMARY was written by
the orchestrator directly since the candidate did not produce one).

## What was implemented

**Task 1 (`aaddde1`)** — `Platform.os_version` (stdlib-only, populated via
`platform.mac_ver()` on Darwin), a `min_os_version` gate added to
`installer/resolve.py::_applies` that fails closed through the existing
`meets_minimum` helper (an unparseable/`None` version never satisfies the
floor), and the new `platform_could_support` predicate — answers "could
this tool ever install here, once Homebrew is present" by re-checking
resolution with `has_brew=True` regardless of the real value, distinct
from `resolve_methods`'s install-time gate.

**Task 2 (`9084372`)** — Two new system-tier registry entries:
`gnu-bash` (`cmd = "gnu-bash"`, a prefix-specific `detect_path` so macOS's
always-present `/bin/bash` cannot false-positive `is_installed`), and
`Apple Containers` (a real `brew` cask/formula install gated to macOS 26+
arm64 via `min_os_version`, always present in the catalog rather than
hidden — the D-01 disabled-state example this phase's design work exists
for).

**Task 3 (`08e4797`)** — Threaded `platform_could_support` through
`setup.py` → `UnifiedApp` → `CatalogScreen`, reusing `UninstallScreen`'s
existing dim/non-selectable-row mechanism so a genuinely incompatible
entry (wrong OS/arch, or below `min_os_version`) renders disabled while
browsing, without incorrectly disabling a brew-dependent tool on a fresh
Mac that simply lacks Homebrew yet. `unstaged_recommends` and
`action_accept_recommends` filter through the same `unavailable` signal
so a disabled row cannot be staged via the Recommends path either.

**Task 4 (`f155e4d`)** — Recorded the resulting convention in
`.claude/architecture.md`: how a platform/arch/`min_os_version`-gated
entry is shown disabled in the catalog, with Apple Containers as the
worked example, closing out D-01 with no residual macOS-version gap.

## Validation

Independently re-run by the orchestrator (not taken from the candidate's
self-report): `make validate && make test` — both pass clean on the
actual committed tree (ruff, ruff-format, pyright 0 errors, bandit,
vulture, shellcheck, full pytest suite, coverage report with no new
uncovered lines of consequence).
