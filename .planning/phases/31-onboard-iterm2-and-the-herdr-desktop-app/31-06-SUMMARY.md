# Phase 31 Plan 06 Summary

## Tasks

- **Task 1 — verdicts and helpers:** commit `9d197b7d`. The previous executor’s RED and GREEN output was not available in this session; the commit and its tests are present.
- **Task 2 — lifecycle driver:** commit `03169740`. RED showed missing `run_version`, `in_container`, and `ORDERS`; the subsequent targeted run completed successfully.

## Verification

- Targeted pytest: **passed**, reaching `[100%]` for the herdr-app, Ghostty, and landing driver tests.
- `make validate`: **passed** — lint, format, typecheck, security, dead-code, and shellcheck.
- `make test`: **passed** — `8556 passed, 6 skipped`; coverage `96.26%`, above the required `90%`.
- Each targeted run’s scratch directory was removed by its exit trap. The final gates used the default `TMPDIR`.

## Deviations and remaining risk

Task 2’s host tests do **not** cover every scenario named in the plan. In particular, the complete matrix of changed and absent digests, failed installs at each attempt in both orders, stray-file reporting and selective purge, cleanup error paths, and `main` exception handling remains unwritten or only partially covered. The requested detailed call-adjacency assertions are also incomplete. Passing gates therefore do not establish the full Task 2 acceptance contract.

The real lifecycle wiring, vendor footprint, libraries, and installed bytes were not tested on the host. The driver installs sequentially; it does not exercise concurrent installs. No container result is claimed here; plan 31-07's target proves it.

Decision record: 31 D-17 is the dedicated container proof; this plan supplies the driver and plan 31-07 supplies the script target. Orchestrator decisions 6 and 9 retain target-local residue handling and file-backed command output. Decision 8 refers to `cmd_ghostty`, `cmd_herdr_keys`, and `cmd_bun_lifecycle`, rather than line numbers.

## Provisional decisions (need confirmation)

31 D-17: the herdr-app container proof is one driver verb that installs the app and the multiplexer in both orders; needs confirmation

orchestrator decision 6: herdr-core and hc are allowed only by the driver's own TARGET_ALLOWED, never by the shared allowlist; needs confirmation

31 D-08 and 31 D-12 need owner confirmation.

The 2026-11-21 context amendments D-07, D-09, D-11, and D-16 need owner confirmation.

The iTerm2 uninstall ordering and refusal, parent key-map rule, keys.json edge cases, and accepted limits recorded as `shortcut:` comments need owner confirmation.

## Orchestrator verification

Checked 2026-11-21 04:50 by the orchestrator, independently of the executors' reports (pi, router-env/my-coding; part a (Task 1, 03:41 to 03:44), a first part b that stopped after 90 seconds with Task 2 unfinished (three red uncommitted tests), a resume that finished Task 2 (committed `03169740`, 03:45 to 03:51) and a completion run (04:39 to 04:43) that added the missing failure-path tests).

- Commits since `fe5072ef`: `9d197b7d` (verdicts and helpers), `03169740` (lifecycle driver: `Ops`, `run_order`, `run_version`, the verb handling, the host refusal), `69c962ed` (seven tests: the digest matrix, a failed install purging only new known paths, the refusal outside the container, `main` reporting handler errors, a cleanup exception reported and the seed cleared, digest reads bracketing each lifecycle operation, a step `OSError` reported with cleanup running); each passed the commit hook. Plan verifies re-run by the orchestrator (`run_plan_verifies.py 31-06`): all exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8592 passed, 6 skipped, coverage 96.26%.
- Open (accepted, the container target proves the rest): the added tests do not explicitly assert that the next order starts from the first baseline nor exercise every app-config digest change through `run_order` (the pure verdict tests cover the latter); the real lifecycle glue, vendor footprint and installed bytes were not exercised on the host.

herdr-app-container: not run
