---
created: 2026-10-21T13:55:24.418Z
title: Rename container shortcuts and detect the available engine
area: tweaks
severity: major
files:
  - installer/tweaks.py:51-63
  - installer/tweaks.py:157-163
  - installer/wizard_app.py:1759-1762
  - tests/test_tweaks.py:89-95
  - tests/test_policy_tweaks.py:14-18
  - tests/test_wizard_app.py:2217-2219
  - README.md:271-276
---

## Problem

The managed container shortcuts are named `docker-ps` and `docker-memory`, and
both assume Docker is installed. `docker-ps` invokes `docker ps` through `watch`;
`docker-memory` points to `docker-stats`, which invokes `docker stats`. These
shortcuts therefore do not serve users whose container engine is Podman or Apple
Containers, even though those engines are available in the catalog.

The user requested engine-neutral names and behavior: rename `docker-ps` to
`container-ps` and `docker-memory` to `container-memory`. Use Docker when
installed, otherwise Podman, and otherwise Apple Containers through its native
`container` CLI when neither Docker nor Podman is installed. Both shortcuts must
show information from the selected engine, not continue invoking Docker.

Severity was explicitly confirmed as **major** on 2026-10-21.

## Solution

- Replace the two public shortcut names with `container-ps` and
  `container-memory` in the managed shell tweak.
- Detect the available engine, using the requested fallback order: Docker,
  Podman, then Apple Containers. Prefer detection when the shortcut is invoked so
  it reflects the current environment rather than a stale installation-time
  choice.
- Map container listing and memory inspection to each engine's supported CLI.
  Verify Apple Containers' commands, output, and memory-reporting capabilities;
  do not assume Docker flags or Go-template formats work for every engine.
- Preserve the purpose of the existing helpers: a live container table with
  names, status, and ports, and quick memory inspection where supported. Report
  unsupported capabilities or a missing engine clearly.
- Update the tweak label/description, wizard help, tests, and current user-facing
  documentation to describe the engine-neutral shortcuts.
- Test Docker-only, Podman-only, Apple-Containers-only, multiple-engine, and
  no-engine environments with fake executables and a scratch HOME; do not start
  engines, install tools, or modify the developer's real shell configuration.

Implementation decisions still open: whether to retain the old names as
compatibility wrappers, how to handle the existing `docker-stats` helper, and how
to distinguish an installed CLI from an unavailable engine. The user requested
renaming only `docker-ps` and `docker-memory`; a `container-stats` rename is not
part of the confirmed scope.

Related but separate: `.planning/todos/pending/2026-10-15-adopt-apple-containers-runtime-colima-stays-compose-path.md`
covers catalog dependencies and descriptions, not these shell shortcuts.
