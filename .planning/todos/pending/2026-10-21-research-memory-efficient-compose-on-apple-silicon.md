---
created: 2026-10-21T14:01:44.368Z
title: Research memory-efficient Compose on Apple Silicon
area: catalog
severity: major
files:
  - installer/registry.toml
  - .planning/todos/pending/2026-10-15-adopt-apple-containers-runtime-colima-stays-compose-path.md
  - .planning/todos/pending/2026-10-21-rename-container-shortcuts-and-detect-the-available-engine.md
---

## Problem

The user develops on an M3 MacBook Pro with 16 GB RAM and experiences memory
pressure when several applications are open. They want a more resource-efficient
container development workflow, ideally avoiding the shared VM memory budget
associated with their Colima/Docker setup while retaining Compose workflows.
Here, "composer" refers to Docker Compose / Compose files, not PHP Composer.

Fresh research is needed to determine whether Apple Containers can support these
workflows through a maintained Compose port, adapter, or compatible frontend,
instead of requiring Docker or Podman as the backend. The user also wants to
understand whether Podman is a better alternative to Docker on macOS and how the
CLI, Compose frontend, engine, and virtualization layers relate.

The user explicitly classified this as **major**, not a blocker: it is a
requirement to investigate improvements to the development workflow, not an
instruction to migrate or change defaults now.

## Solution

Produce a dated research report with current upstream sources, versions,
limitations, and an actionable recommendation for an M3 machine with 16 GB RAM.

- Revisit native Apple Containers Compose support and discover current ports or
  adapters. Recheck `stephenlclarke/container-compose` as a historical lead, not
  an endorsed or currently verified solution. Evaluate maintenance, releases,
  installation, maturity, and whether candidates actually use Apple's runtime
  without silently introducing Docker, Podman, or another shared VM backend.
- Check Apple Silicon and macOS version requirements against the user's actual
  macOS version, which has not yet been provided.
- Assess practical Compose compatibility: multi-service startup, networking and
  DNS, ports, persistent volumes and bind mounts, builds, environment/secrets,
  health checks, dependency ordering, logs, and stop/remove cleanup. Identify
  unsupported features and migration costs rather than treating YAML parsing as
  full Compose support.
- Compare Apple Containers plus viable Compose tooling, Colima plus Docker and
  Compose, and Podman-based Compose workflows. Clarify which components are
  alternatives and which are layers; explicitly assess whether Podman should be
  preferred to Docker for this machine.
- Evaluate actual host memory usage, idle overhead, loaded and peak usage,
  reclaim behavior, swap/memory pressure, and CPU cost with equivalent workloads
  and multiple development applications open. Distinguish configured VM memory
  limits from physically committed memory, and account for per-container VM
  overhead where applicable. Do not assume Apple's runtime is VM-free or always
  more memory-efficient. Separate measurements from estimates and upstream claims.
- Recommend a practical primary workflow and a fallback for unsupported Compose
  features, including realistic memory settings and tradeoffs. If no sufficiently
  mature Apple Containers Compose solution exists, document that result and the
  best supported alternative instead of forcing a migration.

The existing Apple Containers catalog todo records an older decision to keep
Colima for Compose and exclude Compose adapters. This request explicitly reopens
that research question; the earlier split is provisional input, not a constraint
on this investigation. Keep the research deliverable separate from the catalog
implementation and engine-aware shortcut todos, and record any implications for
both after the evidence is available.

Capture only for now: do not perform the research, install tools, start engines,
or change the host configuration. Any later experiments must follow the
project's disposable-environment rules. If representative Apple Silicon
measurements cannot be collected safely, provide a reproducible benchmark plan
and mark the results as unverified.
