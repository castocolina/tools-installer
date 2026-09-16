---
created: 2026-09-16T12:10:00.000Z
title: Detect dangling pnpm global bin shims in Doctor
area: doctor
severity: minor
files:
  - installer/version_status.py
  - installer/versions.py
  - installer/wizard_app.py (DoctorScreen)
  - installer/registry.toml
---

## Problem

Found live during Phase 15.1's UAT (user report, investigated via subagent,
2026-09-16). `mmdc` (mermaid-cli) on this real host shows "no version" and
"(source unknown)" in the catalog despite genuinely having been installed via
pnpm at some point. Root cause traced and confirmed — this is NOT an app bug
in the version/ownership resolution logic itself:

- `~/.local/share/pnpm/bin/mmdc` exists on PATH (so `is_installed(mmdc)`
  correctly returns `True`), but pnpm's global manifest (`pnpm list --global
  --depth 0`) no longer lists `@mermaid-js/mermaid-cli` — almost certainly
  because removing `puppeteer` by hand triggered the documented comma-group
  coupling in `registry.toml` (~line 2290-2300) that removes the whole group
  together, but left this bin shim behind pointing at a now-deleted module
  directory.
- Running `mmdc --version` directly fails: `Error: Cannot find module
  '.../node_modules/@mermaid-js/mermaid-cli/src/cli.js'` (exit 1).
- `probe_version_output` (`installer/versions.py`) correctly returns `None`
  on a non-zero exit — `installed=None` is accurate given the probe genuinely
  failed. `source='unknown'` is also accurate — the package is genuinely
  absent from `inventory.pnpm_globals`.

So the app has correct data and currently no way to say "this is a dangling
shim, not merely unprobed" — the catalog just shows an unexplained blank/gray
cell for a tool that looks installed (present on PATH) but isn't functional.

## Proposed solution

Doctor should detect this class of defect: a tool whose bin is present on
PATH (`is_installed` true) but whose version probe fails AND whose owning
package manager's inventory does not list it — i.e. "orphaned/dangling shim"
as a distinct, named finding, separate from "genuinely not installed" and
"still checking." Likely needs a small addition to `VersionStatus` (or a new
Doctor-only check) to carry this distinction through to a Doctor warning
("mmdc's shim exists but its package was removed — reinstall or remove the
stale shim").

## Scope note

Explicitly investigated during Phase 15.1 closure and determined this does
NOT belong to 15.1 (whose scope was refresh-staleness + dim-cell labeling,
both working correctly here) or to Phase 15.4 (ownership/owner-column
visibility — this is a version-probe-failure class, not an ownership-unknown
class). Filed as a new pending todo per the registry's own documented split
that Doctor is "where an already-installed machine's state is audited."
