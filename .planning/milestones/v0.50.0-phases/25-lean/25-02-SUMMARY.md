---
phase: 25-lean
plan: "02"
subsystem: installer
tags: [lean, host_setup, registry-loader, ownership]
requires: []
provides:
  - "the host_setup method kind and host-setup owner probe are rejected by the closed loader"
  - "compatibility pins for old receipts, old pi version-cache entries and pnpm-installed pi"
affects: [installer/model.py, installer/engine.py, installer/update.py, installer/ownership.py]
tech-stack:
  added: []
  patterns: ["explicit Method narrowing with UpdateError instead of a suppression"]
key-files:
  created: []
  modified:
    - installer/model.py
    - installer/engine.py
    - installer/executors.py
    - installer/update.py
    - installer/ownership.py
    - installer/install_ownership.py
    - installer/resolve.py
    - installer/version_status.py
    - installer/receipts.py
    - installer/catalog_audit.py
  deleted:
    - installer/host_setup.py
    - tests/test_host_setup.py
decisions:
  - "D-10: host_setup retired in one revertable commit; pins and docs are separate commits"
  - "update_refusal's detail text keeps its 'through its host setup' wording (user-visible text stays byte-identical)"
metrics:
  duration: "about 40 minutes"
  completed: "2026-11-15"
status: complete
actuals:
  tokens: 40000
  tasks: 3
  commits: 3
plan_head_before: d0d88257feec3895ee51d1b0050b47cabc3f9888
plan_head_after: 1bb31e00d7efa260d8c03f4bbc7d6346c242f281
requirements: [LEAN-01]
---

# Phase 25 Plan 02: Retire the host_setup method kind Summary

The `host_setup` kind is gone from code, docs and skill: the loader rejects a row that declares it and an `owner_probes = ["host-setup"]` entry as unknown, no production line names it, and 593 lines net left the tree (133 added, 593 deleted across 32 files).

## Commits

| Task | Commit | What |
|------|--------|------|
| 1 | 04ad08b8 | refactor(25-02): retire the host_setup method kind (one green commit) |
| 2 | ddee57db | test(25-02): compatibility pins (old receipt, old pi cache entry, pnpm pi) |
| 3 | 1bb31e00 | docs(25-02): architecture, onboarding skill and leftover comments |

`make validate && make test` exit 0 on each commit's tree (7660, 7663 and 7663 passed, 6 skipped; coverage 96.1%).

## RED evidence (Task 1)

Run at HEAD before any production edit (`uv run pytest tests/test_model.py -k "retired_host_setup ..."`):

```
FAILED tests/test_model.py::test_a_retired_host_setup_row_is_rejected_as_an_unknown_kind
FAILED tests/test_model.py::test_a_retired_host_setup_owner_probe_is_rejected
E   Failed: DID NOT RAISE <class 'ValueError'>
```

The row loaded and the probe was accepted. Both pass after the retirement. The rpm_ostree-switched smoke_argv test and the brew-switched frobnicate test passed before and after (live kinds).

## D-10 compatibility pins (Task 2: pinning tests, not RED; they pass at once)

- `test_a_receipt_naming_the_retired_host_setup_kind_reads_without_a_crash` (tests/test_receipts.py): `receipts.read("pi")` on a schema-v1 receipt with method kind `host_setup` returns the `Receipt` (the reader checks that the kind is a string, not that it is live); asserted `receipt.method == ReceiptMethod(kind="host_setup", key=...)`.
- `test_an_old_pi_version_cache_entry_loads_unchanged` (tests/test_version_cache.py): a `versions.json` `tools.pi` entry with the four `VersionCacheEntry` fields loads unchanged under `"pi"`. The cache is keyed by tool id and stores no method kind (the `{"kind","params"}` hash is `receipts.method_key`), so the entry stays a hit; no fingerprint, no miss (review R2-03).
- `test_a_pnpm_installed_pi_resolves_owner_pnpm` (tests/test_ownership.py): pi in its bun-plus-node shape (`_bun_pi()`), pnpm globals evidence and the live path in `PNPM_HOME`, resolves owner `pnpm` (review R1-06).
- Ownership record (review R2-04): D-10's compatibility clause names an "ownership record", but none is persisted. Ownership resolves live (`installer/version_status.py` `_resolve_owner_from` -> `resolve_ownership`); its persisted inputs are the receipt (pinned above) and the `versions.json` `managers` snapshot, which `encode_manager_snapshot` writes without any method kind. There is no ownership-record format to pin.

## Deleted tests (existed only for the retired kind)

- tests/test_host_setup.py (whole file)
- tests/test_engine.py: `test_host_setup_kind_routes_to_host_setup_handoff`, `test_a_host_setup_method_still_hands_off`, `test_handoff_kinds_are_never_smoked`
- tests/test_ownership.py: `test_host_setup_tool_resolves_to_its_verified_owner`, `test_host_setup_owner_needs_the_live_path_in_that_owners_dir`, `test_host_setup_unverified_probe_stays_unknown`, helpers `_pi_tool`, `_PNPM_LIST`, `_pnpm_listing` (`_PI_PACKAGE` kept)
- tests/test_install_ownership.py: `test_host_setup_owner_uses_the_reviewed_setup_probe`, `test_a_host_setup_probe_never_runs_a_leftover_pnpm`
- tests/test_update.py: `_pi_target`, `test_pi_host_setup_update_runs_the_reviewed_command`, `test_pi_host_setup_update_without_pnpm_fails_naming_it`, `test_host_setup_without_a_reviewed_command_is_still_refused`
- tests/test_session.py: `test_the_review_offers_pi_an_update_through_its_host_setup`
- tests/test_version_status.py: `test_host_setup_tool_version_probes_the_unresolved_path`
- tests/test_model.py: `test_a_host_setup_method_still_loads` (replaced by the two rejection tests)
- Parameters removed: the `host_setup` param of `test_receiptless_kinds_write_nothing` (tests/test_receipts.py), the `host_setup` row of tests/test_catalog_audit.py's unread-source table, the `host_setup` entry of `_PRE_PHASE_RANK` (tests/test_resolve.py).

## Sample-kind switches (every assertion line unchanged)

- tests/test_model.py: `test_smoke_argv_is_rejected_where_nothing_is_installed` row becomes `("rpm_ostree", 'package = "demo"')`, `unknown key 'smoke_argv'` match untouched; `test_other_unknown_tool_keys_stay_lenient` uses `brew` + `formula`.
- tests/test_engine.py: `test_manual_required_login_shell_never_invokes_confirm` uses a `dnf` method (still MANUAL_REQUIRED, `post_install_handoff == ()`).
- tests/test_render.py, tests/test_execute_screen.py: hand-built `InstallOutcome(method_kind="dnf")`.
- tests/test_version_status.py: the three `host_setup_*` params of the forwards-the-unresolved-path test are dropped; it is renamed `test_resolve_status_forwards_the_unresolved_path_for_volta`, and since only one route remained, the single-value `parametrize` and its dead branches were removed (the Volta body and both assertions are unchanged).
- Return-shape edits of doubles (not assertions): the `_perform` fake in tests/test_engine.py and tests/test_uninstall_e2e.py now return the 3-tuple.

`test_update_refuses_host_setup_pnpm_cleanly` is byte-identical to HEAD (awk-extracted diff exit 0).

## Production changes

- `installer/host_setup.py` deleted.
- `model.py`: import, `METHOD_KINDS`/`METHOD_PARAMS` entries, `"host-setup"` in `OWNER_PROBES`, the setup_id branch.
- `engine.py`: `_HANDOFF_KINDS` removed, `_manager_method` returns `not (download or app or cargo_distrobox)`, `_perform` returns `(verified, unverified_reason, notes)`, the `if handoff:` block is gone. `InstallOutcome.handoff`, `render_handoff` and `InstallStatus.MANUAL_REQUIRED` stay (native handoffs).
- `executors.py`: `host_setup_handoff`, `host_setup_approval_disclosures` removed.
- `update.py`: `host_setup_update_argv` removed; `update_refusal` refuses any pnpm-owned tool with no method (detail text unchanged); `_perform` raises `UpdateError("no node method for the pnpm-owned <id>")` when `method is None`, then calls `executors.execute(method, runner)`. The `shlex` and `real_pnpm` imports went unused and were dropped.
- `ownership.py`: `_HOST_SETUP_OWNERS`, `_host_setup_owner` removed; the verified non-native branch of `_native_owner` returns `None`. The now-unused keyword `attributed` of `_native_owner` and its call-site argument were removed; the unused `Ownership` import dropped.
- `install_ownership.py`: `_host_setup`, its `_PROBES` key, comments. `resolve.py`: `_RANK` entry and list entry. `version_status.py`: the `any(...)` arm. `receipts.py` `RECEIPTLESS_KINDS`, `catalog_audit.py` tuple: member dropped.
- Docs/comments (Task 3): `.claude/architecture.md` (decision-tree branch, Phase 14 sentence, receipts sentence), `.claude/skills/tool-onboarding/SKILL.md` (three places), comments in session.py, enums.py, post_install.py, tests/test_registry.py. `mmdc -> bun` kept.

## Extra files touched beyond the plan's list (24.5 lesson)

- `installer/ownership.py`: `attributed` parameter of `_native_owner` (unused after the removal; ruff/vulture would flag it).
- `tests/test_uninstall_e2e.py`: its `_perform` fake returned the old 4-tuple (9 failures in the first full run).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tests/test_uninstall_e2e.py `_perform` fake used the 4-tuple shape**
- **Found during:** Task 1 full-suite run
- **Fix:** return-shape edit of the double to the 3-tuple; no assertion touched
- **Commit:** 04ad08b8

**2. [Rule 3 - Blocking] `_native_owner(..., attributed=...)` became an unused parameter**
- **Found during:** Task 1 (the only user was the deleted `_host_setup_owner`)
- **Fix:** removed the parameter and the call-site argument
- **Commit:** 04ad08b8

**3. [Judgment] version_status parametrize collapsed**
- The plan said "keep the `volta` param"; with one param left the `parametrize` and its dead `elif/else` branches were removed instead of left as dead code. Assertions unchanged.

The plan's acceptance grep for Task 1 also required `rg ... installer | grep -v session|post_install|enums` to print 0; it does (and the whole `installer` tree prints 0 after Task 3). `update_refusal`'s detail text still says "through its host setup" on purpose (user-visible text stays byte-identical, pinned by the unchanged refusal test); this is plain English in a string, not an identifier match for the greps.

## Known Stubs

None.

## Threat Flags

None. No new endpoint, auth path or file access; the change shrinks the loader's accepted set (T-25-03), pins old-record reads (T-25-04) and keeps the pnpm no-method refusal with `calls == []` (T-25-05). No `noqa`, `type: ignore`, `pyright: ignore` or `nosec` was added (`git diff` grep: 0).

## Self-Check: PASSED

- installer/host_setup.py and tests/test_host_setup.py absent
- commits 04ad08b8, ddee57db, 1bb31e00 are ancestors of HEAD
- `rg 'host_setup|host-setup|HOST_SETUP|pnpm_add_command' installer setup.py --glob '*.py'` prints nothing
