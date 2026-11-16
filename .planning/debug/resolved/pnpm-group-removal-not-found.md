---
status: resolved
trigger: "22-13 e2e: CLI uninstall removed mmdc, then `pnpm remove --global puppeteer` failed ERR_PNPM_GLOBAL_PKG_NOT_FOUND; run_uninstall exit 1 (TRACER_UNINSTALL_INCOMPLETE)"
created: 2026-11-04
updated: 2026-11-16
---

## Current Focus

hypothesis: CONFIRMED. pnpm 12.16.1 removes a whole global install group when any member is removed; remove_tool treats the second member's ERR_PNPM_GLOBAL_PKG_NOT_FOUND as a failed removal.
next_action: tests first (RED), then remove_tool accepts that exact code on a pnpm removal argv; copy fix
reasoning_checkpoint:
  hypothesis: "remove_tool fails puppeteer because `pnpm remove --global @mermaid-js/mermaid-cli` already removed the whole group, so pnpm exits 1 with ERR_PNPM_GLOBAL_PKG_NOT_FOUND on stderr (CommandError.detail via run_captured)"
  confirming_evidence:
    - "container: after removing mmdc, pnpm ls -g lists only pnpm; remove puppeteer -> ERR_PNPM_GLOBAL_PKG_NOT_FOUND exit 1"
    - "container: reverse order identical (removing puppeteer first removes mmdc too)"
    - "e2e transcript detail line `Error: ERR_PNPM_GLOBAL_PKG_NOT_FOUND`"
  falsification_test: "after the fix, e2e still prints `puppeteer: remove failed` or the puppeteer receipt survives"
  fix_rationale: "pnpm's own not-found answer proves the desired end state (package absent from the global set); remove_tool then re-proves and removes only what is still there and deletes the receipt; any other pnpm error still fails"
  blind_spots: "pnpm versions other than 12.16.1 may word/code the error differently (then the tool fails as before: safe)"
  candidate_causes:
    - "code: remove_tool treats every CommandError as failure"
    - "environment: pnpm 12 group-scoped global removal (data model of pnpm, not ours)"
    - "data/doc: ledger A13 assumption that removal is per package"
  and_gate: "yes: pnpm group semantics AND remove_tool strict failure AND two receipts for one group; fix addresses the code side"

bug_class: Bohrbug (deterministic, reproduced by e2e)

## Symptoms

expected: uninstall of mmdc + puppeteer removes both and deletes both receipts; run_uninstall returns no failures.
actual: mmdc removed; puppeteer `pnpm remove --global puppeteer` -> ERR_PNPM_GLOBAL_PKG_NOT_FOUND; puppeteer receipt kept; exit 1.
errors: "puppeteer: remove failed — Error: ERR_PNPM_GLOBAL_PKG_NOT_FOUND"
reproduction: make e2e (pass 2 uninstall), see 22-13-SUMMARY.md D-1
started: Phase 22 (22-06 remove_tool contract makes a failed manager command fail the tool)

## Eliminated

## Evidence

- timestamp: 2026-11-04
  checked: .e2e-artifacts/container/pass1-transcript.log
  found: puppeteer installed first alone (global/v11/2d1f-...), then mmdc group (global/v11/2e86-...) listing `+ @mermaid-js/mermaid-cli 12.2.0` and `+ puppeteer 25.16.0`; pnpm v12.16.1
  implication: two `pnpm add -g` invocations; group semantics decide whether the standalone puppeteer survives
- timestamp: 2026-11-04
  checked: installer/executors.py:_node
  found: argv is `pnpm add -g --allow-build=puppeteer puppeteer@^25` (puppeteer tool) and `pnpm add -g --allow-build=puppeteer @mermaid-js/mermaid-cli,puppeteer@^25` (mmdc)
  implication: experiment must use these exact argv

- timestamp: 2026-11-04
  checked: podman fedora:latest, node 22.23.1, pnpm 12.16.1, executor argv, PUPPETEER_SKIP_DOWNLOAD=1 (scratchpad pnpmexp/exp.sh, out.log)
  found: A) puppeteer alone then mmdc group -> pnpm ls -g shows mmdc + puppeteer (one group; standalone group replaced). remove mmdc -> exit 0, ls shows only pnpm; remove puppeteer -> `Error: ERR_PNPM_GLOBAL_PKG_NOT_FOUND / Cannot remove 'puppeteer': not found in global packages` exit 1. B) remove puppeteer first -> exit 0, mmdc gone too; remove mmdc -> NOT_FOUND exit 1. C) group only, same as B.
  implication: removing ANY member removes the whole group; A13 ledger assumption and `leaves X installed` copy are wrong
- timestamp: 2026-11-04
  checked: installer/run.py run_captured / run_output_with_stderr
  found: CommandError.detail = child's stderr; the CLI and TUI uninstall use run_captured
  implication: the NOT_FOUND code is available to remove_tool in exc.detail

## Resolution

root_cause: pnpm 12 `remove --global <pkg>` removes the whole install group <pkg> belongs to; remove_tool treated the second member's ERR_PNPM_GLOBAL_PKG_NOT_FOUND as a failed removal (kept receipt, exit 1). The co-install warning copy and the pnpm_removal_packages docstring carried the same wrong per-package premise (UI-SPEC A13).
fix: remove_tool accepts ERR_PNPM_GLOBAL_PKG_NOT_FOUND in CommandError.detail only when argv is the pnpm removal (`pnpm remove --global <pkg>`), then finishes still-present proven paths and deletes the receipt; co_install_warnings partial copy -> "removing {removed} removes the whole group, {others} included."; UI-SPEC dated amendment.
oracle_type: specified (pnpm behaviour measured in container, encoded in a fake runner)
verification:
  red: 6 failed / 3 passed before fix (scratchpad red.log); green: 9 passed
  mutation: dropping the pnpm-argv guard fails test_a_not_found_from_a_non_pnpm_command_still_fails; dropping the code match fails test_another_pnpm_error_still_fails_the_tool; reverting the fix fails test_a_group_member_pnpm_already_removed_is_removed
  gates: make validate 0; make test 5541 passed / 4 skipped, 96.32%
  e2e: TRACER_UNINSTALL_OK, TRACER_RECEIPTS_GONE_OK count=61, no remove failed; halted at leftover check on unrelated D-2 (27 roots)
commit: 4190481
files_changed: [installer/app.py, installer/pnpm_globals.py, tests/test_app.py, tests/test_pnpm_globals.py, tests/test_wizard_app.py, .planning/phases/22-method-lifecycle-contract/22-UI-SPEC.md]
superseded_by: 1be24cbe (fix(22): re-check a manager package against a fresh listing before uninstall) replaced the NOT_FOUND tolerance: remove_tool reads the manager's fresh listing and retires a receipt whose package is no longer listed
human_verify:
  date: 2026-11-16
  commits: [41904813, 1be24cbe]
  tree: HEAD b1ce5f61 (worktree streamed like scripts/container-e2e-verify.sh)
  environment: disposable podman container ti-uat-debug-pnpm (registry.fedoraproject.org/fedora:44, --init), user tester, node v22.23.1, pnpm 12.21.0 (standalone script, no receipt), no bun, uv 0.13.8; removed afterwards
  steps: "puppeteer then mmdc installed through installer.engine.install_tool (the pnpm `node` method, as no bun exists; the bun-first CLI ladder cannot reach pnpm on this box), then the real headless CLI `setup.py --uninstall --yes`"
  evidence:
    - "install: HV_INSTALL puppeteer/mmdc status=installed kind=node; pnpm ls -g lists @mermaid-js/mermaid-cli 12.2.0 + puppeteer 25.17.0 in one group; both receipts present (smoke=ok)"
    - "uninstall preview: `mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli`, `puppeteer: runs pnpm remove --global puppeteer`, `Warning: pnpm group mmdc: all its members are removed together.`"
    - "uninstall result: `puppeteer: removed with the mmdc group`, no `remove failed`, no ERR_PNPM_GLOBAL_PKG_NOT_FOUND, exit 0"
    - "after: pnpm ls -g lists only pnpm; receipts puppeteer.json and mmdc.json both gone"
  falsification_test: not triggered (no `puppeteer: remove failed`, puppeteer receipt deleted)
  transcript: session scratchpad uat/debug-pnpm/transcript.log (HV_VERDICT PASS)
