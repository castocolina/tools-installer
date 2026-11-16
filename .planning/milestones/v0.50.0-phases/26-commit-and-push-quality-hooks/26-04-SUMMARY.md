---
phase: 26-commit-and-push-quality-hooks
plan: "04"
subsystem: devtools
tags: [push-gate, pre-push, pre-commit, signals, tdd]
requires: ["26-01"]
provides:
  - "devtools/push_gate.py: the D-01 pre-push gate (parse_updates, refusal, run_forwarding_signals, main, GATE_READ_PATHSPECS, PRE_PUSH_ARGS)"
  - "tests/test_push_gate.py: fake-runner unit tests and real-signal child tests"
affects: [26-05, 26-06, 26-08, 26-09]
tech-stack:
  added: []
  patterns: ["injected GitRunner fake answering by exact argv", "own process group plus a forward-once SIGINT handler", "stdlib-only hook module, no installer import"]
key-files:
  created:
    - devtools/push_gate.py
    - tests/test_push_gate.py
  modified: []
key-decisions:
  - "A malformed pre-push stdin line fails closed (exit 1) instead of being skipped"
  - "git_runner is public (not _git_runner) so the test exercises the real argv-list runner with a sys.executable stand-in, with no pyright suppression"
  - "The gate-read part and the other untracked part are separate message parts, so the .git/info/exclude advice can never appear next to a gate-read file"
requirements-completed: [HOOK-02, HOOK-03]
duration: 40min
completed: 2026-11-16
status: complete
actuals:
  tokens: 7700
  tasks: 3
  commits: 3
plan_head_before: 76a89cb1aed2fce325ee7d28cff77061f58342e3
plan_head_after: bf5ab83ef8b737daf181a2939f76e605b26286e8
commits: 3
---

# Phase 26 Plan 04: The push gate Summary

`python -m devtools.push_gate` reads every pushed ref, applies five ordered refusals before any check, runs `pre-commit run --hook-stage pre-push --fail-fast --from-ref HEAD --to-ref HEAD` with the stash kept on, and forwards the first interrupt once as SIGINT to pre-commit's own process group.

## What changed

- **Task 1 (8fc0e959)**: `RefUpdate`, `parse_updates`, `git_runner`, `main`. Empty or deletion-only stdin returns 0 before any program lookup or git call. A missing `git` or `pre-commit` (message names `make dev-setup`) and any non-zero git query fail closed with exit 1. A failing gate prints the closing line naming the `make <target>` line above.
- **Task 2 (369cc506)**: `refusal` runs the five checks lazily in D-18 order (unmerged, staged, untracked, unstaged `.pre-commit-config.yaml`, pushed commit not HEAD, peeled with `^{commit}`). Refusal 3 always runs query A (`ls-files --others --exclude-standard -z`, `.planning/` dropped, D-25) and query B (`--glob-pathspecs ls-files --others -z -- <GATE_READ_PATHSPECS>`, no exclude option, D-28). Gate-read names get "commit them, or move them out of the repository"; the rest get "commit, stash, remove or ignore them" with `.git/info/exclude` for a local-only file no gate reads. Names are sorted and printed as git reported them (`-z`, `os.fsdecode`).
- **Task 3 (bf5ab83e)**: `run_forwarding_signals(argv, *, spawn, killpg)` with `Child` protocol. `_spawn` is `Popen(process_group=0, stdin=DEVNULL)`. One handler for SIGINT, SIGTERM, SIGHUP records `interrupted` and forwards SIGINT once; a signal before the handle exists is forwarded once right after `spawn` returns (no signal mask anywhere). Handlers are restored in `finally`; a negative return code maps to `128 + n`; a signalled run that returned 0 exits 130; the `push interrupted` write ignores `OSError`.

## TDD evidence (RED output)

- Task 1: `ImportError: cannot import name 'push_gate' from 'devtools'` (module absent), collection error, 0 tests ran.
- Task 2: `ImportError: cannot import name 'GATE_READ_PATHSPECS' from 'devtools.push_gate'`, collection error, 0 tests ran.
- Task 3: with the stub runner, `test_a_group_signal_is_forwarded_once_as_sigint[2]` failed with `assert -2 == 130` (the SIGINT killed the stub gate before it could forward); the SIGTERM and SIGHUP cases and the spawn-window tests fail the same way until forwarding exists.

GREEN after each task: `uv run pytest tests/test_push_gate.py -n 0 -q --no-cov` passes (48 tests at the end). The test file was also run three more times under `-n auto` with no flake and no leftover `fake_pre_commit` process.

## Verification

- `make validate` green on every commit's tree; `make test` on the final tree: 7730 passed, 6 skipped, total coverage 96.22%.
- `devtools/push_gate.py` coverage: 99% (only the `sys.exit(main())` line under `__main__` is not hit).
- Acceptance greps: `"--fail-fast"` 1, `shell=True|^import installer|^from installer` 0, `"--diff-filter=U"` 1, `".planning/"` 1, `info/exclude` 1, `^{commit}` 1, `GATE_READ_PATHSPECS` 2, `"--glob-pathspecs"` 1, `process_group=0` 1, `pthread_sigmask` 0, `os.killpg` 1; `def test_` count 37, 48 collected with parametrization (at least 25 required).

## Deviations from Plan

None - plan executed as written. Notes: a malformed stdin line (not a case in the plan) fails closed, which is the plan's "fails closed" stance applied to parsing. Two test-side shapes avoid suppressions: `git_runner` is public, and the cases loop in `test_no_message_suggests_skipping_a_hook` sets replies on the fake instead of splatting a mixed dict into `_git`.

## Known limits

- T-26-30 (accepted): with the non-default terminal setting `stty tostop`, output from pre-commit's own process group would stop it (SIGTTOU) and the push would wait. Stdin is /dev/null so nothing reads the terminal.
- T-26-39 (accepted): an ignored gate input outside `GATE_READ_PATHSPECS` is not refused; CI on the pushed commit stays the binding gate.
- The byte-identical restore of unstaged edits after a pass, a failure and an interrupt is proven by `make hooks-e2e` (26-06) with real git; this plan's tests prove the signal contract with fake children only.
- No host mutation: no hook was written, nothing was pushed, no real git/make/pre-commit ran in a test.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file-access surface beyond the plan's threat model.

## Self-Check: PASSED

- devtools/push_gate.py: FOUND
- tests/test_push_gate.py: FOUND
- 8fc0e959, 369cc506, bf5ab83e: ancestors of HEAD
