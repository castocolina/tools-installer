# Milestone Run Report — tools-installer v1

**Run mode:** Unattended (`gsd-autonomous --to 12 --converge`), per `.planning/ONESHOT-RULES.md`.
**Scope:** Phases 1–12 (this report focuses on Phases 11–12, the two phases executed in this
visible run segment; Phases 1–10 completed in prior runs and are listed for milestone-completeness
below).
**Final state:** 12/12 phases complete, 34/34 plans complete. `make validate && make test` clean
on the final tree (1700 passed, 1 skipped, 96.49% coverage; 0 pyright errors).
**Human decision still required:** tagging a release — deliberately not done autonomously.

---

## Milestone-wide phase list

| Phase | Title | Status |
|---|---|---|
| 1 | Catalog Tier Foundation | ✓ Done |
| 2 | Tier-Scoped Catalog Views & Recommends | ✓ Done |
| 3 | Install/Uninstall & Tweak Lifecycle Hardening | ✓ Done |
| 4 | npm/npx Ban Extension & Redirect Policy | ✓ Done |
| 5 | Registry Method Corrections (codegraph/mmdc/puppeteer) | ✓ Done |
| 6 | SDKMAN Hardening & Registry-Authoring Guidelines | ✓ Done |
| 7 | System & User Tier Catalog Expansion | ✓ Done |
| 8 | AI Tier Catalog Expansion & uv-tool Executor | ✓ Done |
| 9 | Postinstall Hooks Mechanism | ✓ Done |
| 10 | Agent CLI Ergonomics | ✓ Done |
| 11 | Background Maintenance Daemon | ✓ Done — Tier-3 real-machine bug caught & fixed (below) |
| 12 | Version-Aware Status & Update Action | ✓ Done — dual-lane review caught 4 Critical safety bugs (below) |

---

## Phase 11 — Background Maintenance Daemon

**What it ships:** wraps the existing `scripts/prune-user-tmpdir.sh` as a toggleable, macOS-only
LaunchAgent, with a real audit-trail log instead of silent background deletion.

### Tier-3 real-machine verification finding (significant)

The initial goal-backward verification pass routed "does the real LaunchAgent actually fire and
run to completion" to `human_needed` — the mocked-`Runner` test suite exercises the wrapper logic
but never invokes `uv run` for real, so it cannot observe launchd's actual runtime environment.
Per Rule 14's Tier-3 model, this was instead verified directly on this machine using a
**disposable, uniquely-labeled test LaunchAgent** (never the real production label/paths):
`launchctl bootstrap gui/$(id -u) <disposable.plist>`, then `launchctl kickstart -k` to force
immediate execution.

**Bug found (100% reproducing in production):** `AttributeError: module 'datetime' has no
attribute 'UTC'` on the real launchd-triggered run — but not when run manually from an interactive
shell inside the repo. Root cause: `uv run --no-project` (no explicit Python version constraint)
resolves its interpreter partly by searching for a `.venv` relative to the **caller's current
working directory**. Launchd invokes scheduled jobs from a working directory that is never this
repo — so it fell back to macOS's Command Line Tools `python3` (3.9.6 on this machine), which
predates `datetime.UTC` (added in Python 3.11). Every real scheduled run of the shipped code would
have crashed, always — a defect the mocked test suite could not have caught by construction.

**Fix:** added a PEP 723 inline script-metadata block (`requires-python = ">=3.11"`) to
`installer/helper_assets/prune_daemon_runner.py`, forcing `uv run --script` to resolve a
compliant interpreter from uv's own managed toolchain regardless of the caller's cwd.
Re-verified via the identical disposable-LaunchAgent bootstrap+kickstart cycle: the wrapper now
runs to completion and the log receives the expected `deleted: N` entry. The disposable test
LaunchAgent and all scratch files were fully torn down (`launchctl bootout`, `rm -rf`) — no trace
survives this machine.

**Verdict:** `status: passed`, 6/6 must-haves verified, upgraded from the initial `human_needed`.

---

## Phase 12 — Version-Aware Status & Update Action

**What it ships:** a "Ver" column showing installed-vs-latest version for every catalog tool
(GitHub-release or package-manager sourced); `installer/ownership.py`, a real ownership-resolution
model distinguishing which manager *actually owns* an installed tool's live binary from
`resolve_methods()`'s install-*preference* ranking; and `installer/update.py`, a real,
no-confirmation "update" action (press `u`) that mutates the user's real machine via the tool's
actual owning manager.

This phase mutates the machine with **no confirmation dialog** (an explicit prior product
decision) — so the ownership/evidence logic being airtight was the only safety net, and was
treated accordingly throughout: 3 cycles of cross-AI plan review, a dual-lane post-execution code
review, and goal-backward verification.

### Cross-AI plan-review convergence (3 cycles, cap reached per Rule 10)

Three review cycles were run against the phase plans; genuine findings were incorporated at each
cycle. The cap was reached at cycle 3 with residual findings, so — per Rule 10 — a final direct
fix pass was applied (not a 4th cycle) and disposition was documented in
`12-REVIEWS.md`'s Cap-Reached Disposition section. Full history in
`.planning/phases/12-version-aware-status-update-action/12-REVIEWS.md`.

### Dual-lane post-execution code review — the significant catch of this run

After execution, both an internal `gsd-code-reviewer` lane and an independent `codex-sol-high`
second lane reviewed the same merged diff against three hard-won safety properties:

1. Ownership evidence must be fail-closed (malformed manager output, or a contradictory active
   PATH, must never look like valid evidence for a mutation-grade decision).
2. The update flow must re-resolve ownership **fresh** immediately before mutating, never
   relying solely on the display layer's cache (which can be up to 6 hours stale).
3. The pnpm-managed package snapshot must be captured **before** a pnpm self-update, and the
   update must be refused outright if that capture fails.

**The internal review lane found no Critical issues** and explicitly stated it had confirmed all
three properties as "genuinely fail-closed" and "correct." **The independent codex-sol-high lane,
run on the identical diff, found 4 real Critical violations of exactly these properties.** Rather
than accepting either lane's verdict at face value, every disputed claim was personally verified
against the actual current source before deciding which lane was right:

| # | Finding | Verified real via |
|---|---|---|
| C1 | Inventory parsers (brew/pnpm/uv) were not genuinely fail-closed — a warning line or malformed shape could parse into a mapping that looked like valid negative evidence, wrongly authorizing a by-elimination mutation | Reproduced `parse_brew_list_versions("warning: inventory format changed\n")` → `{"warning:": "changed"}` under the pre-fix code |
| C2 | Homebrew casks installed into `~/Applications` could be misclassified as installer-owned with **direct** confidence (e.g. VS Code), causing `u` to replace a brew-managed bundle through the wrong updater | Confirmed `owner_dirs`'s `installer_dirs` tuple unconditionally included `applications_dir()` while cask attribution only checked `brew --prefix`, and that VS Code declares both `app` and `cask` methods in the registry |
| C3 | A pnpm self-update proceeded even when the pre-update snapshot capture failed, so nothing could be replayed if pnpm's own update wiped its global set | Confirmed `UpdateService.run()` called `perform_update` unconditionally when `captured is None`, with a test explicitly blessing an `"updated"` outcome with no snapshot |
| C4 | Crash recovery could delete the only known-good pre-update backup — `.old` was deleted whenever `live` also existed, with no check for whether `live` had ever been validated | Confirmed `recover_update_remnants` ran `shutil.rmtree(old)` whenever `live.exists()`, with no validation-state gate |

All 4 Criticals, plus real Warnings (cache-invalidation-failure misreported as mutation failure;
a single transient manager-query failure cached as a false 6-hour-fresh snapshot) and test
false-assurance issues, were fixed with genuine regression tests reproducing each exact scenario,
committed in `da7c38c`. The fixes were independently re-verified by reading the post-fix source
directly (not trusting the fix agent's self-report) and re-running `make validate`/`make test`.
Full findings, second-lane verbatim report, and resolution-status table:
`.planning/phases/12-version-aware-status-update-action/12-REVIEW.md`.

**Takeaway for future runs:** an internal reviewer's "confirmed safe" verdict on a
no-confirmation mutation path is not sufficient on its own — the second independent lane found
real, reproducible violations of properties the first lane had explicitly signed off on. The
dual-lane pattern is worth keeping mandatory for phases with this risk profile.

### Test-coverage gap closure

Goal-backward verification (`gsd-verifier`) found 21/21 must-haves verified but routed one item
to `human_needed`: `installer/catalog_tui.py`'s `_update_tool_worker`/`on_tool_updated` — the
actual `u`-keypress → `UpdateService.run()` → status-line-rendering pipeline — had 0% direct test
coverage (all existing tests stubbed the worker out). This was judged to be a pure test-coverage
gap closable via injected fakes, not a genuine live-machine-effect requirement per Rule 14's own
guidance to verify safely via fakes when possible. Closed with 5 new Pilot-driven tests
(`tests/test_catalog_tui.py`) that press the real `u` binding on a real `CatalogScreen` wired to a
real `UpdateService`, faking only the runner/manager-query seams — covering all 4 outcome shapes
(`updated` with `replayed_globals`/`cleanup_warnings`/`postinstall_warning` populated; `failed`;
`unknown-owner` from fresh re-resolution; the in-flight double-press guard). Coverage on that file
went from 77% to 93%. `12-VERIFICATION.md` status is `passed`, 21/21 must-haves, with a closure
note. Committed in `1bfc0dc`.

### Deferred scope (documented, not silently dropped)

`REQ-manager-drift-alerting` (alert when a pnpm/npm-managed tool has a newer/safer brew
equivalent) was deferred, not implemented, in Phase 12 — recorded with structural reasoning in
`ROADMAP.md`, `REQUIREMENTS.md`, and `.claude/architecture.md`. Rationale: `brew outdated` only
lists already-installed formulae/casks (it cannot detect an uninstalled brew alternative to a
pnpm-managed tool), and zero registry tools today declare both a node/uv-tool method and a
brew/cask method — so there is nothing live to alert on yet, and shipping an unwired helper would
violate this project's no-orphan-helper rule. A guard test (`test_abandoned_drift_helpers_are_absent`)
pins that no such orphan helper exists.

---

## Post-execution bookkeeping fixed in this run

`.planning/REQUIREMENTS.md`'s checklist and status table had a documentation-sync gap (the same
pattern previously seen and fixed for Phase 11): five Phase 12 requirement rows still read
"Pending" despite genuine, reviewed, tested implementation. Verified against `12-VERIFICATION.md`'s
requirements-coverage table (all seven REQ-IDs mapped and evidenced) and corrected to "Done"
in commit `1db2e5a`, along with flipping `REQ-pnpm-global-reinstall-mitigation` from "Partial" to
"Done" now that Phase 12 shipped the automatic-trigger half alongside Phase 4's mechanism/manual
trigger.

---

## Final verification gate (this run, on the primary checkout — not trusted from any agent's
self-report)

```
make validate   →  ruff check: all checks passed
                    ruff format --check: 108 files already formatted
                    pyright: 0 errors, 0 warnings, 0 informations
                    bandit: clean (documented B404/B603/B310 skips only)
                    vulture: clean
                    shellcheck install.sh: clean

make test       →  1700 passed, 1 skipped in 139.55s
                    Total coverage: 96.49% (required: 90.0%)
```

`gsd-audit-uat` cross-phase scan: **all clear** — zero outstanding UAT/verification items across
all 12 phases (0 total_items, 0 parse_gap_files).

---

## Remaining human handoff items

1. **`REQ-mmdc-install-decision`** (Phase 5) — resolved by research during that phase's run
   rather than by direct user confirmation. Recorded as "Complete" in `REQUIREMENTS.md`; worth a
   quick human glance since it was an autonomous research-based call, not a user-made one.
2. **`REQ-manager-drift-alerting`** (Phase 12) — deliberately deferred, not implemented. See
   "Deferred scope" above for the structural reason. Revisit once the registry has a tool that
   declares both a node/uv-tool method and a brew/cask method.
3. **W1 — uv-tool shim ownership limitation (Phase 12, accepted, documented)** — a uv-installed
   tool's shim at `~/.local/bin/<name>` correctly dereferences into uv's real tool directory, but
   the resolver only recognizes the shim directory itself as uv-owned, not the dereferenced target.
   This means some genuinely uv-owned tools resolve to `unknown` ownership rather than being
   update-able via `u`. This is a **fail-closed, not fail-open** limitation — it makes the update
   action unexpectedly refuse an otherwise-safe update rather than mutating anything wrong. Left
   as an accepted limitation in the dual-lane review's resolution table; worth a follow-up phase
   if uv-tool update ergonomics matter enough to fix.
4. **Tagging a release** — explicitly a human decision, not performed autonomously by this run.

---

_Run completed: 2026-09-07_
_Orchestrator: Claude (gsd-autonomous --to 12 --converge)_
