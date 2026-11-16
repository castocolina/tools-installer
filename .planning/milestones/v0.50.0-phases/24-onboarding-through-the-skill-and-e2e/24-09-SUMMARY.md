---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "09"
subsystem: install-engine
tags: [script-executor, receipts, release-capture, version-status, rerun-gate, tdd]
requires:
  - phase: 24-01
    provides: engine _perform 4-tuple, ExecutorError
  - phase: 24-05
    provides: _update_installer_owned cargo_distrobox branch
  - phase: 24-07
    provides: version_status pass with hook facts
provides:
  - "executors._script downloads to a temp file with curl retries and runs the shell only after curl succeeded"
  - "Receipt.release and record(release=) with a fail-closed read and write pattern"
  - "versions.capturing_resolver wrapping the ReleaseResolver"
  - "the recorded release deciding outdated for a receipt-proven installer-owned tool"
affects: [24-08 container e2e rerun gate]
tech-stack:
  added: []
  patterns:
    - "download-then-run instead of curl | sh, so curl's exit status reaches the runner"
    - "capture wrapper around the ReleaseResolver (never the TagResolver) so API digests keep verifying"
key-files:
  created: []
  modified:
    - installer/executors.py
    - installer/receipts.py
    - installer/versions.py
    - installer/engine.py
    - installer/update.py
    - installer/version_status.py
    - installer/registry.toml
    - tests/test_executors.py
    - tests/test_engine.py
    - tests/test_receipts.py
    - tests/test_update.py
    - tests/test_version_status.py
    - tests/test_registry.py
key-decisions:
  - "A recorded release that cannot be ranked against the latest tag (is_outdated returns None) keeps the probe's answer instead of replacing it with None"
  - "Shell tracer fakes live under tmp_path and the production script runs as a file with bash; the only real binary a fake reaches is the host rm, on the fake temp file"
requirements-completed: [ONB-04]
metrics:
  duration: "~1h30m"
  completed: "2026-11-13"
status: complete
actuals:
  tokens: 8800
  tasks: 2
  commits: 2
plan_head_before: 38ca06890427fa056450fa2f54046dfd68805962
plan_head_after: 11c98a732d0e41d0944413c5532031240b94e67e
commits: 2
---

# Phase 24 Plan 09: rerun-gate product causes Summary

A script install whose `curl` download failed is now FAILED with curl's status (download-then-run with `--retry 3 --retry-all-errors`), and a release the installer placed and still proves reads current from the receipt's recorded tag, so sd v1.1.0 (binary prints 1.0.0) no longer reads outdated forever.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | a failed script download fails the install, end to end through a real shell (tracer) | 3124358 |
| 2 | the receipt records the release it placed, and a receipt-proven release reads current | 11c98a7 |

## What was built

- **executors.py:** `_script` builds `f="$(mktemp)" || exit 1; trap 'rm -f "$f"' EXIT; curl -fsSL --retry 3 --retry-all-errors -o "$f" -- <url> && <env> <shell> [-s -- args] < "$f"` after the unchanged `_path_prefix()`. The runner argv stays `["sh", "-c", script]`. The shell never runs when curl fails, and curl's status is the script's exit status. `_env_prefix`'s docstring no longer mentions the pipe.
- **receipts.py:** `Receipt.release` (default None), written only when set, read as None when absent and rejected (whole receipt untrusted) when present but not matching `[A-Za-z0-9][A-Za-z0-9._+-]*`. `record(release=)` stores None for a tag that would not read back (R2-18). `record_hooks` and `forget_hooks` keep the release (they use `dataclasses.replace`).
- **versions.py:** `capturing_resolver(resolve) -> (resolver, tags)`, returns the wrapped `Release` unchanged.
- **engine.py:** `install_tool` builds `capturing_resolver(release_resolver(resolve_tag))` once, clears the capture list at the start of every method attempt (R2-11), and passes the last captured tag to `receipts.record`.
- **update.py:** `_perform` builds the same wrapper, `_update_installer_owned` takes `resolve_release: ReleaseResolver` instead of `resolve_tag` and uses it in both the download and `cargo_distrobox` branches, and the captured tag goes to `receipts.record`.
- **version_status.py:** after `_receipt_evidence`, for an installer-owned tool whose receipt records a release, with no broken fact, no `UNPROVEN_NOTE` and a known latest tag, `outdated` comes from `is_outdated(receipt.release, status.latest)`; the probed text stays as `installed`.
- **registry.toml:** the sd `# Verified 2026-11-12` note and bumped `verified` date.

## TDD evidence (RED output)

Task 1, before the `_script` change (`uv run pytest tests/test_engine.py tests/test_executors.py -k "script" -q --no-cov -n 0`): the rewritten pins and both new engine tests failed.

```
FAILED tests/test_engine.py::test_script_download_failure_fails_the_install
  assert <InstallStatus.INSTALLED: 'installed'> == <InstallStatus.FAILED: 'failed'>
FAILED tests/test_engine.py::test_script_download_success_runs_the_script_on_stdin
  assert False  (the marker the downloaded script touches does not exist)
FAILED tests/test_executors.py::test_script_executor_downloads_then_runs_the_shell
FAILED tests/test_executors.py::test_script_executor_defaults_shell_to_sh
FAILED tests/test_executors.py::test_script_executor_quotes_url_with_special_chars
FAILED tests/test_executors.py::test_script_passes_env_assignments_to_the_shell
FAILED tests/test_executors.py::test_script_without_env_is_unchanged
FAILED tests/test_executors.py::test_script_executor_passes_args_after_sh_s
FAILED tests/test_executors.py::test_script_pipeline_downloads_then_runs
FAILED tests/test_executors.py::test_uv_script_without_args_is_byte_identical
```

The first one is the 2026-11-08 bug reproduced: a curl exit of 35 inside `curl | sh` left the row INSTALLED.

Task 2: the tests were written first, but the implementation was then written before the first red run, so the red state was reproduced afterwards by reverting `installer/` to the task-1 commit (`git checkout -- installer/`, re-applied from a saved patch) and running the task's `-k` filter:

```
E       TypeError: record() got an unexpected keyword argument 'release'
FAILED tests/test_receipts.py::test_receipt_records_the_release
FAILED tests/test_receipts.py::test_receipt_without_release_is_unchanged
FAILED tests/test_receipts.py::test_receipt_with_a_bad_release_is_untrusted[5] (and 4 more ids)
FAILED tests/test_receipts.py::test_record_drops_an_unreadable_release
FAILED tests/test_receipts.py::test_a_hook_update_keeps_the_recorded_release
FAILED tests/test_engine.py::test_install_records_the_resolved_release
FAILED tests/test_engine.py::test_a_manager_install_records_no_release
FAILED tests/test_engine.py::test_failed_release_attempt_records_no_release
FAILED tests/test_engine.py::test_release_capture_keeps_the_production_resolver
FAILED tests/test_update.py::test_update_records_the_new_release
FAILED tests/test_version_status.py::test_sd_reads_current_when_its_receipt_proves_the_release
FAILED tests/test_version_status.py::test_a_changed_binary_falls_back_to_the_probe
FAILED tests/test_version_status.py::test_receipt_without_release_keeps_the_probe
FAILED tests/test_version_status.py::test_older_recorded_release_still_reads_outdated
18 failed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `tests/test_registry.py` pinned the old pipeline text**
- **Found during:** Task 1 (`make test`)
- **Issue:** `test_fnm_installer_skips_its_shell_block` asserted the script ends with `bash -s -- --skip-shell`; the tail is now `bash -s -- --skip-shell < "$f"`. The plan listed seven pinned tests and missed this one.
- **Fix:** the assertion now expects the new tail; the test still proves `--skip-shell` reaches the shell.
- **Files modified:** tests/test_registry.py
- **Commit:** 3124358

**2. [Rule 3 - Blocking] the engine tests' PATH sandbox hides `bash`**
- **Found during:** Task 1
- **Issue:** the autouse fixture in tests/test_engine.py replaces PATH with an empty dir, so `shutil.which("bash")` is None.
- **Fix:** the script tests look for bash and rm in `/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin`; no sandbox rule was widened.
- **Files modified:** tests/test_engine.py
- **Commit:** 3124358

**3. [Plan note] `test_installer_owned_update_passes_the_release_resolver` (R3-03)**
- The test calls `_perform`, whose `resolve_tag` parameter is unchanged, so it still passed untouched. It now also asserts the resolver handed to `update_download` resolves through the capture wrapper, which is what the signature change affects.

### Choices inside the plan's discretion

- A recorded release `is_outdated` cannot rank (None) keeps the probe's answer rather than clearing `outdated`.
- A changed binary reads BROKEN for health (its file artifact no longer matches); the plan's "publishes OUTDATED" is asserted on `state.version.outdated is True`, which is the fallback to the probe.

## Known Stubs

None.

## Threat Flags

None. The only new surface is the mktemp file the script creates and removes on exit (T-24-38/T-24-39 mitigations).

## Self-Check: PASSED

- installer/executors.py, installer/receipts.py, installer/versions.py, installer/engine.py, installer/update.py, installer/version_status.py, installer/registry.toml and the six test files exist and are committed.
- Commits 3124358 and 11c98a7 are ancestors of HEAD.
- `make validate && make test`: exit 0 on both task trees (6275 and 6293 passed, coverage 96.2%).
- `grep -c -- "--retry-all-errors" installer/executors.py` prints 1; `grep -c "receipt.release" installer/version_status.py` prints 2.
