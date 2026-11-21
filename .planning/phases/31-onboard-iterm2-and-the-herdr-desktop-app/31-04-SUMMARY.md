# Phase 31 Plan 04 Summary

## Tasks

- **Task 1 — `fde87d63`:** Added the pinned vendor defaults, keys path, owned keys, validation, and version-checked seed. `tests/conftest.py` stubs the version seam so tests do not run the installed app. Task 1’s original RED and GREEN output was not available in this split run; its commit and tests were verified from the tree.
- **Task 2 — `9214e72b`:** Added the chord parser and user-binding detector with the five named test groups. RED: the targeted suite failed on the missing `parse_chord` and `herdr_app_taken` functions. GREEN: the targeted suite completed at `100%` with exit 0.

## Vendor hashes

- `keys.json`: `d1831fe2e9a685abf5fd95c156f4425fcbc17f81919163955a3688a166ea269f`
- `keys.macos.json`: `8728a5190aa2ef1609c08c0cb49cf31dd74ab7018944b6453d9f371570d023c0`

## Final gates

- `make validate`: exit 0; lint, format-check, typecheck, security, dead-code, and shellcheck all passed.
- `make test`: exit 2. Tail: `1 failed, 8470 passed, 6 skipped`; coverage `96.26%`, above the required `90%`. The failing test was `tests/test_reachability.py::test_every_installer_module_is_reachable_from_an_entry_point`. Running it alone confirmed that `installer.herdr_app_keys` is the unreachable module.
- The Task 2 commit hook initially found formatting and typing errors. Those were corrected; the failed individual gates and the subsequent commit hook passed.

## Provisional decisions (need confirmation)

31 D-16 corrected: chords are normalized with the app's GPUI grammar (cmd/super/win and secondary; option and platform are not accepted by the app and are not folded); needs confirmation

31 D-14: the keys file is keys.json on every OS and the owned key goes in the terminal section; jev overridden; needs confirmation

31 D-15: a missing or blank keys file is seeded with the pinned vendor default for the OS; jev overridden; needs confirmation

orchestrator decision 5 (data part): a whitespace-only file counts as missing and a created file left equal to the seed is deleted by the strip; needs confirmation

31 D-08 and 31 D-12; needs owner confirmation.

The 2026-11-21 amendments to D-07, D-09, D-11 and D-16, including the parent key-map rule, iTerm2 uninstall ordering and refusal; needs owner confirmation.

The keys.json edge cases and accepted limits recorded as `shortcut:` comments; needs owner confirmation.

## Deviations and limits

No named Task 2 test was omitted. The final full-suite gate remains red until the production wiring planned for 31-05 makes the module reachable; no guard was bypassed. Task 1’s original RED/GREEN tails were unavailable. Every run directory created in this split run was removed by its exit trap.

## Orchestrator verification

Checked 2026-11-21 03:36 by the orchestrator, independently of the executors' reports (pi, router-env/my-coding, part a (Task 1, 03:22 to 03:24) and part b (Task 2 and gates, 03:24 to 03:28)).

- The executor's first line was `BLOCKED: make test fails because installer.herdr_app_keys is not reachable from a production entry point`. As in 31-02 this is a plan-ordering consequence: the module is wired by plan 31-05 (the herdr-app registry entry and row) and the reachability guard is deliberately strict. The orchestrator re-ran the full suite on the committed tree: exactly one failure, that test (`1 failed, 8470 passed, 6 skipped`, coverage 96.26%); the suite is red between this plan and 31-05 only and nothing is pushed in between. The BLOCKED line is dropped.
- Commits since `5a290241`: `fde87d63` (pinned vendor defaults, version-checked seed, keys path, owned keys), `9214e72b` (chord grammar and the record-aware user-binding detector); each passed the commit hook. Plan verifies re-run by the orchestrator (`run_plan_verifies.py 31-04`): all exit 0.
- Vendor files re-hashed by the orchestrator: `installer/vendor_defaults/herdr-app-0.1.16/keys.json` is `d1831fe2e9a685abf5fd95c156f4425fcbc17f81919163955a3688a166ea269f` and `keys.macos.json` is `8728a5190aa2ef1609c08c0cb49cf31dd74ab7018944b6453d9f371570d023c0`, equal to the pinned research hashes the plan gates on.
- Open: Task 1's RED and GREEN tails were not available in the split run; the version probe of the installed method's own executable (review M2) and the pure pinned default used at strip time are covered by the tests the executor reports as written.

herdr-app-container: not run
