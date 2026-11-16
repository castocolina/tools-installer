---
created: 2026-11-16
title: Transient test ERRORs under xdist in the push gate
area: testing
---

## Problem

On 2026-11-16 the pre-push gate (`make test`, `pytest -n auto`) on commit 743b5d91 (a docs-only change under
`.planning/`) reported `7823 passed, 6 skipped, 2 errors`:

- `tests/test_wizard_app.py::test_many_retired_rows_scroll_at_80x20` (ERROR, an assertion)
- `tests/test_setup.py::test_linux_probe_memoizes_is_active_inside_the_ttl` (ERROR)

They are ERRORs (setup or teardown), not FAILs. Both pass in isolation (`-n 0`), and the next full `make test` on the
same tree passed (7823 passed, 6 skipped). The failing run's full traceback was not kept (the runner's output was cut
to its last 40 lines), so the root cause is unconfirmed. The same tree's explicit `make test` a minute earlier passed
too.

## Solution

Keep the full log of the next failing run (`make test 2>&1 | tee`). Then look for shared state between xdist
workers: the Textual pilot timing in the 80x20 scroll test, and the TTL clock or memo cache in the Linux probe test.
Fix the root cause; never add retries or skip markers. Related: the 26-03 flaky-reinstall mitigation
(`.planning/todos/completed/2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test.md`).
