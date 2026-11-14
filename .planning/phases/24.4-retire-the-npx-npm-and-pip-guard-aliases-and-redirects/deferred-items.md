# Deferred items — phase 24.4

## From 24.4-05

- `tests/test_schedules_engine.py::test_the_linux_unit_carries_the_proxy_and_certificate_variables`
  fails whenever the checkout path contains the substring `bad` (the test asserts
  `"bad" not in text` over a unit file that embeds the repo path). Seen in the
  `agent-ab02f49badfc71358` worktree; unrelated to this phase. Fix idea: make the
  test's bad value unique (for example `"bad\nvalue"` checked as the full string
  `HTTP_PROXY=bad`) so the repo path cannot collide with it.
