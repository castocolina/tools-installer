# Deferred items: phase 25-lean

Out-of-scope discoveries logged by plan executors. Nothing here is fixed in the plan
that found it.

## From 25-04 (vulture-60 triage)

### Flaky wall-clock assertion in the streaming runner test

- **Test:** `tests/test_run.py::test_streaming_runner_emits_incrementally_before_child_exits`
- **Symptom:** `assert timestamps[1] - timestamps[0] >= 0.3` failed once with a gap of
  0.2998 s during a full `make test` run (`-n auto`), on the tree at commit `454ac5b8`.
  Three other full runs passed, and the test passes 5 of 5 when run alone.
- **Not caused by 25-04:** `tests/test_run.py` is untouched. `installer/run.py` lost only
  the unused `run_interactive_command`, which the test never touches.
- **Suggested fix (separate change):** synchronise on the child's second line (an event
  set by the emit callback) instead of a wall-clock bound, as `.claude/testing.md` asks
  for wall-clock bounds that leave CI room.

### Dead-by-rule candidates kept by the plan's test-seam precedent

These have no production caller (`installer/`, `setup.py`, `scripts/`). Their only
consumers are tests, and removing them would change other tests' assertions. The
orchestrator should confirm whether to delete them in a follow-up:

- `installer/omz.py` `omz_present`: 7 test references, including the consistency guard
  `test_omz_root_agrees_with_omz_present_on_every_case`.
- `installer/ownership.py` `DETAIL_PHRASE_COLLISIONS`: the declared-collision register that
  `tests/test_ownership.py` enforces.
- `installer/wizard_app.py` `disk_probing`: write-only in production; read by three test
  wait predicates (`tests/test_wizard_app.py` lines 329, 479 and 3750).
