# Phase 17 review lane: opencode (openai/gpt-6.1-sol#xhigh)

Read-only run, closed stdin, scope a7dba6f..0e9406c (non-.planning). Unverified input; verified per finding by gap plans 17-18..17-20.

### [HIGH] Uninstall deletes artifacts replaced after preview
- `installer/uninstall.py:153-158`; `installer/app.py:694`
- The removal proof becomes a list of bare paths that are deleted without revalidation.
- Preview a proven `bin/fd` symlink, replace it with a foreign regular file before confirming, then confirm: `remove_paths` deletes the replacement even though fresh proof rejects it.
- Retain proof metadata and revalidate artifacts immediately before deletion; refuse changed paths.

### [HIGH] Changing link mode resurrects uninstalled policies
- `installer/wizard_app.py:2199-2209`
- Migration trusts `active_state`, which is not refreshed after the Uninstall view removes policies.
- Launch with an active ban, uninstall it, then change link mode: the stale selection causes migration to recreate the shims and aliases without another enable action.
- Refresh policy activity from actual footprints before migration, including after another view removes policies.

### [HIGH] Direct catalog update failures still exit successfully
- `setup.py:1290-1296`; `installer/catalog_tui.py:999-1020`
- Failed updates started with `u` never reach `install_summary`, and failed outcomes render as warnings rather than errors.
- Press `u`, receive `UpdateOutcome(status="failed")`, then quit without an installation run: the update displays a warning and setup exits 0.
- Fold direct-update failures and worker errors into the session summary, and render failed outcomes red.

### [MEDIUM] Reverse mode migration leaves ban aliases unsourced
- `installer/policy.py:242-255`
- Migration reapplies policies without establishing the source wiring required by the destination mode.
- Start with split PATH wiring and only the ban active, then select centralized: aliases move into `.myshellrc`, but neither shell sources that file despite the successful migration report.
- Establish destination source wiring during migration and cover ban-only split → centralized/single transitions.

### [MEDIUM] A looping symlink prevents the wizard from launching
- `installer/uninstall.py:148`
- Unhandled `Path.resolve()` failures escape the uninstall screen’s error guard on supported Python 3.11/3.12.
- With `~/.local/bin/fd -> fd`, resolution raises `RuntimeError`; constructing `UninstallScreen` fails, including when launching the Doctor route.
- Treat resolution failures as unproven artifacts and list them for manual removal instead of aborting construction.

### [MEDIUM] Completed updates become “not attempted” after a probe crash
- `installer/execute_screen.py:765-773`; `installer/execute_screen.py:960-964`
- Final progress reconciliation ignores accumulated update outcomes before marking pending rows skipped.
- An update succeeds, then its version refresh raises `RuntimeError`: the saved outcome says updated, but the row becomes skipped and the screen summary lists it as not attempted.
- Reconcile progress from accumulated update outcomes and errors before sweeping unreached rows, using consistent bookkeeping for both summaries.

### [MEDIUM] The race test stops before testing a superseded generation
- `tests/test_version_status.py:1297-1298`
- The new early exit allows the test to finish after its first refresh/invalidate cycle.
- The exact test body completed after one generation in three read-only probes; a regression exposing the previous record during the second refresh would never be exercised.
- Require multiple completed generations before stopping while retaining the reader-overlap checks.

Not checked: full suite or live-host behavior; verification used read-only, in-memory probes.
TOTAL: 7 findings (0 critical, 3 high, 4 medium, 0 low)
