---
created: 2026-11-16T12:00:00.000Z
title: Adopt the branch → green CI → main flow in the outside tools that push to main
area: tooling
severity: major
files: []
---

## Problem

Since phase 26 turned on `enforce_admins` and strict required checks, the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow are rejected when they push straight to `main`.

## Solution

Each pushes its branch, waits for both checks, then fast-forwards `main` with `git push origin <branch>:main`; none toggles `enforce_admins` on its own (SPEC: no automatic bypass).
