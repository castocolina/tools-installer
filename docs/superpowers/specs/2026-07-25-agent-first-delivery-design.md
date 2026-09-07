# Agent-First Delivery Design

## Purpose

Deliver the agent-first installer redesign through four small implementation
plans and one supervising `/goal` prompt. The goal runs without waiting for
milestone approval, while preserving explicit checkpoints, truthful status, and
safe test boundaries.

## Milestones

| Plan | Scope | Prerequisites |
| --- | --- | --- |
| 1. Execution UI | Sequential in-app installer, live output, one approval, checkpoint state | Existing installer core |
| 2. Installation intelligence | Dependencies, post-install actions, ownership probes | Existing registry/core; Plan 1 interface for UI integration |
| 3. Catalog tiers | Basic/User taxonomy, installed-last order, `glab`, vetted user entries | Registry tier metadata from Plan 2 when added |
| 4. Agent environment | Shared tooling guidance, CodeGraph, agent audit/fix adapters | Existing policy framework; Plan 2 actions only where needed |

Plans 1 and 2 form the main dependency chain. Plans 3 and 4 may continue when
another plan fails, provided their own prerequisites pass. A failed plan blocks
only its direct dependents.

## Supervising Goal

The supervising `/goal` prompt reads the PRD and all four implementation plans.
It executes Plan 1, then Plan 2, and schedules Plans 3 and 4 when their stated
prerequisites pass.

At each milestone, the goal runs the plan's focused tests and writes an
append-only checkpoint report under `docs/superpowers/checkpoints/`. Each
report records the status (`passed`, `failed`, `blocked`, or `skipped`), changed
files, executed commands, failures, remediation, and downstream impact.

The goal continues independent work after a failure. It does not silently skip
failures, mark blocked work complete, or claim overall success without the
final integration audit. Its final report presents a complete milestone status
matrix.

## Architecture Boundaries

### Execution

Plan 1 introduces one execution abstraction for both console and Textual paths.
Core installation emits attributed progress events; the Textual screen renders
them in a scrollable output pane. Core tests inject runners and output sinks,
so they do not require a live terminal.

### Registry intelligence

Plan 2 extends registry data with tier, recommendation level, dependency reason,
typed post-install action, and ownership probe fields. Python code maps each
action or probe identifier to reviewed behavior. Registry data cannot execute
arbitrary shell snippets.

### Catalog presentation

Plan 3 changes catalog data and presentation only. It adds `glab`, displays
Basic and User groupings, labels project-dependent tools as contextual, and
sorts installed tools beneath available tools.

### Agent environment

Plan 4 adds agent adapters. An adapter owns detection locations, managed
instruction references, permission capability, and audit/fix behavior. When an
agent cannot express a safe read-only policy, the adapter reports manual setup
instead of writing a speculative configuration.

## Test Strategy

The default E2E suite uses a temporary home directory, fixture registry, and
stubbed runners. It runs the Textual application headlessly, repeats the same
scenario against the same temporary home, and verifies dependency ordering,
single approval, idempotent managed files, Doctor/Fix, and Uninstall.

An optional Podman container smoke test runs the Python installer as an
unprivileged container user with an isolated home directory. It exercises the
noninteractive workflow, dependencies, managed files, and idempotency. It does
not test `chsh`, sudo, real system package managers, or host-home changes.

Disposable VM tests are deferred. Before adding them, the project must select
and provision a user-approved backend such as Podman machine or libvirt/QEMU.
Podman alone is not treated as a system-VM dependency.

## Failure Handling

Every test layer fails closed: it records the failing command and leaves the
milestone failed. Independent milestones continue; dependent integration does
not start until its required interface passes. The final integration gate runs
the repository's normal validation and test suites, plus all available focused
integration checks.

## Out of Scope

- Installing or configuring a VM backend.
- Real package-manager mutations in automated E2E tests.
- Automatic approval of security-sensitive changes.
- Treating unsupported agent permission formats as configurable.
