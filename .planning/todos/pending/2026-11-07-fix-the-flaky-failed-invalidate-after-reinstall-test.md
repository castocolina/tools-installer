---
created: 2026-11-07T12:00:00.000Z
title: Fix the flaky failed-invalidate-after-reinstall screen-family test
area: tests
severity: minor
files:
  - tests/test_screen_family.py
---

## Problem

`tests/test_screen_family.py::test_a_failed_invalidate_after_a_reinstall_is_reported[mapped]` failed under parallel
load twice during Phase 23 execution (23-04 and 23-13 executors), passing alone and on a full re-run each time. A
flaky test can mask a real regression and costs a full re-run of the suite.

## Solution

Find the unsettled wait (Textual pilot timing under `-n auto`): settle on the publication or the worker completion the
assertion depends on instead of a fixed pause, the same way the Phase 21 macOS fixes did (`settle` helper, no
unbounded waits). Prove it with a loop of 50 runs under `-n auto` before and after.
