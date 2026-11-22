# Phase 34 Plan 09 Summary

**Commit:** `83ef7fdaf82ad9963a515e2b1d0814c34afb4630` — `test(34-09): prove the hermetic check job and its allowed writes`

Added the runner-to-child integration tests, real-service evidence tests, and separate replay log test. The tests cover four HOME scenarios, checkout immutability, the cache symlink, token isolation, bus propagation, Git checkout binding, zero update-executor calls, and a second run.

## Verification

- **RED:** The initial targeted run failed collection as expected: `ImportError: cannot import name 'real_service'`.
- **GREEN:** The plan’s targeted pytest command exited 0; its tail ended at `[100%]`. The additional tests importing the shared doubles also passed.
- **`make validate`:** All six gates passed.
- **`make test`:** `9392 passed, 6 skipped in 81.91s`; coverage **96.44%**, above the 90% requirement.
- The commit hook initially found lint and type errors; those were corrected, the affected gates rerun, and the hook passed on commit.
- Each explicitly created run directory was removed by its shell trap. Tests and final gates used the default `TMPDIR`.

## Scenario writes

The tests constrain changed HOME paths to the named cache, notified-set and receipt files:

- **plain:** `versions.json`, `update-check.json`.
- **adopt:** `receipts/yq.json`; the cache may also be rewritten for manager state. No notified-set file.
- **retire:** `receipts/yq.json` removed; the cache may also be rewritten for manager state.
- **link:** `versions.json` replaced as a regular file and `update-check.json` created; the symlink target remains unchanged.

These paths are relative to `.local/state/tools-installer/`. The runner log and locks are outside HOME under the scratch `run/` directory. The checkout snapshot remained unchanged in all four scenarios.

## Decisions

- Round 2 M6 and H4 — **needs confirmation**: hermetic job and named allowed writes, with receipts inside the HOME snapshot.
- Round 3 H8 — **needs confirmation**: a Python fake `uv` starts a child through the real runner, bound to the scratch checkout; snapshots span the runner call. The pure replay is a separate labeled test using an absolute interpreter path (M8).
- Round 3 H3 — **needs confirmation**: a fresh but unrefetched adopted entry is unknown; stale resolver and failed manager-query evidence do not move the notified set.
- Orchestrator decision 12 — **provisional, needs confirmation**: tests use fake `notify-send`, fake `uv` and the Python child; no real Git, GitHub CLI, notifier, container or network.
- 34 D-23 — **locked**: scratch HOME and fakes only.

## Deviations and findings

- Scenario state is seeded by the parent test before the snapshot rather than by the child. The snapshot still spans the entire real runner and child call.
- All named test functions and the stale-positive and failed-manager-query cases were written. The test does not separately assert that the fresh adoption resolver was never called; it asserts the adoption and no-notification outcomes.
- No production files changed. Real desktop delivery and macOS behavior were not checked.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commit `83ef7fda` (the hermetic job test: the real `setup.main` check wired through the real runner and a Python fake `uv` child, bound to a scratch checkout with the exact `git -C` path asserted, a one-day-old cache, a nonempty outdated set, an adopted receipt, a retired stale receipt, a symlinked `versions.json` replaced, the allowed-write set compared across the whole runner call, the stale-positive and failed-manager-query cases, a separate labeled pure-replay log test), through the six-gate commit hook; no production file changed; tree clean afterwards except the untracked goals file.
- The plan's verify re-run (owned scratch `TMPDIR`): exit 0; every `<behavior>` test exists. `make validate` rc 0; `make test` on the final tree, default TMPDIR: 9392 passed, 6 skipped, coverage 96.44%; the runner, update-check, notify, schedule-update, cache and container-schedules tests also pass on Python 3.15.
- One narrower point: the test asserts the adoption and no-notification outcomes but does not separately assert that the fresh adoption resolver was never called.
- No timer, notification or container was run in this plan.

Provisional decisions carried to the verification report (needs owner confirmation): the narrowed write-boundary claim (no checkout writes; installer state only the named files plus receipt housekeeping through the existing path; uv's own cache and manager-query scratch writes are accepted as for every schedule row); confirmed-only membership proven through the real service.

orchestrator-verification: none required

orchestrator-verification: none required
