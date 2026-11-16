---
created: 2026-11-16T00:00:00.000Z
title: Keep the Execute run log's newest line visible after the window shrinks
area: tui
severity: cosmetic
files:
  - installer/execute_screen.py
  - tests/test_execute_screen.py
---

## Problem

The phase 25 run-log capture (2026-11-16, container `ti-uat-25b-fedora`, HEAD 8b0d1bf1) found one cosmetic
issue. When the window shrinks from 120x40 to 90x25 during a run, the dropped-lines notice stays visible, but the
tail of the log is cut off. The newest line (`DONE`) is hidden until the next write or scroll. When the window
grows from 80x20 to 100x30, the tail stays visible.

This looks like stock `RichLog` scroll behaviour. It was not compared against a pre-phase build, so it is not
recorded as a phase 25 regression. Captures are in the session scratchpad `uat/25-runlog/`.

To reproduce, drive `ExecuteScreen` with 6,000 lines at 120x40, then run `tmux resize-window -x 90 -y 25`.

## Solution

In `RunLog`, when the log was following its end before the resize (auto-scroll is on and the view sat at the
bottom), scroll back to the end after the resize. Add a pilot test that resizes with `wait_until` and asserts that
the last line is in view.
