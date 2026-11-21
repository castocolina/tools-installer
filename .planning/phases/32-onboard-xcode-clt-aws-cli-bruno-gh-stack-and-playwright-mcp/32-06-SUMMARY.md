# Phase 32 Plan 06 Summary

- **Task 1 — `4906fdb4`:** Added the AWS lifecycle driver, pure verdicts and shared transcript evidence gate. The earlier executor’s RED and GREEN output was not available in the commit or working tree.
- **Task 2 — `e42d5791`:** Added the AWS container target, no-gpg leg, verified cleanup, usage entry and generic skip. RED: 13 expected failures against the missing target and skip entry. Final targeted run: all tests passed (`[100%]`).

## Final gates

- `make validate`: all six gates passed.
- `make test`: **8965 passed, 6 skipped**; coverage **96.33%**, above the 90% requirement.
- The Task 2 commit hook initially caught formatting, line-length and shellcheck issues; their root causes were corrected and the hook passed.
- Run directories created by my trapped scratch commands were removed. The final gates used the default TMPDIR as required.

## Decisions

All decisions below are **provisional and need owner confirmation**:

- Orchestrator decision 10: AWS container evidence uses a transcript-bound `aws-container: PASS` line; environmental `_UNPROVEN` or infeasible results are retried and never count as a pass.
- Orchestrator decision 6: `aws-cli` joins `GENERIC_SKIP_TOOLS`; its dedicated target covers the missing-gnupg case.
- Orchestrator decision 9: rootless container limits, file-based child output, residue baselines, standard empty directories and transcript-digest evidence apply.
- D-05: both hosts are covered; the Debian no-gpg leg runs the vendor script with the entry’s environment, with its verdict computed on the host. Brew fallback is covered by plan 32-03’s unit test.
- A recording shim at `/usr/local/bin/gpg` logs verification calls and forwards unchanged arguments to the real gpg.
- `tests/e2e_evidence.py` provides the shared gate for plans 32-08 and 32-09; the herdr-app gate remains separate.
- Review M6: the shared gate requires each verdict exactly once and in order.
- Review round 2 H6 and M6: the no-gpg verdict compares before-and-after install-path listings; teardown requires exact marker equality, ignoring blank lines.
- Review H8 and H9: the EXIT trap preserves the entry status under errexit and verifies both containers absent before the success marker; `LANDING_EXTRA_LEFT` extends the shared teardown verdict.

## Pin edits

- Updated the exact dedicated-target skip-list pin to include `aws-cli`.
- Shifted the four classified PATH line numbers by six; their reasons remain unchanged.

## Deviations

- The host tests do not independently exercise `main aws-cli` dispatch, the full pulled-image/keep-image cleanup matrix, or the no-gpg container command’s complete argv and script execution through a stubbed `ct`; those plan-named scenarios remain unverified by the host tests.
- The real container, vendor script and network checks were not run, as instructed. Runtime claims remain unproven until orchestrator verification.

Orchestrator to run: `scripts/container-e2e-verify.sh aws-cli`

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `4906fdb4` (Task 1), `e42d5791` (Task 2), `4750d51a` (completion pass: the executor admitted that its host tests did not cover the `main aws-cli` dispatch, the cleanup matrix and the no-gpg container command; a second run added them, tests only) and `419a1ed8` (a fix the real run found, below), each through the six-gate commit hook.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0. `make test` on the tree after the completion pass, default TMPDIR: 8975 passed, 6 skipped, coverage 96.33%.
- Real container check, run by the orchestrator: `scripts/container-e2e-verify.sh aws-cli`. Run 1 (09:42) failed the no-gpg leg: the leg ran the vendor installer with `sh`, which is dash on the Debian image and cannot parse the script (syntax error), so `gpg not found` never printed; the shipped registry entry runs it under `bash` and was not affected. Fixed in `419a1ed8` (the leg now runs `bash`, pinned by a test). Run 2 (09:51): install via the script with GPG verification on Fedora, rerun is a no-op, removal clean, the no-gpg Debian box fails closed (`gpg not found`, exit non-zero, install paths unchanged), both containers removed. Transcript: `.e2e-artifacts/container-aws-cli/aws-cli-transcript.log` (git-ignored).
- No `tools-installer-e2e-aws-*` container is left (`podman ps -a --filter name=tools-installer-e2e-aws` lists none); no broad prune or reset was run.

Provisional decisions carried to the verification report (needs owner confirmation): D-05 (the AWS container check is orchestrator-run and recorded as `aws-container: PASS`); orchestrator decision 6 (`aws-cli` joins the generic skip list); the shared evidence gate shape (digest-bound PASS line, each verdict exactly once in order, exact teardown line last); accepted limit: the shared landing helper removes the image tag when its inspection failed at start (inherited since phase 24, backlog 999.32).

aws-container: PASS (2026-11-21; transcript 9515b665dff5)
