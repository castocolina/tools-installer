---
created: 2026-10-15T12:25:46.866Z
title: Adopt Apple Containers runtime; colima stays compose path
area: catalog
severity: minor
files:
  - installer/registry.toml
---

## Problem

Decision from 2026-10-14 research: on Apple Silicon the user will run plain
containers on Apple's native `container` runtime (macOS 26+/arm64; per-container
lightweight VMs, no central fixed VM reservation — eliminates the "double
taxation" of reserving VM memory and then allocating it to containers) and use
colima only for Compose workflows.

Both catalog entries already exist (`container` P2, gated macOS 26+/arm64;
`colima` P1), so this adds nothing new — the actionable gaps are:

(a) the `colima` entry declares no `requires = ["docker"]` edge although
colima's Docker runtime needs the docker CLI for compose (colima README:
"Docker client is required for Docker runtime");
(b) neither entry's desc conveys this runtime split.

Compose adapters for Apple container (e.g. stephenlclarke/container-compose,
36 stars) are early-stage and explicitly out of scope by user decision.

## Solution

Wire `requires = ["docker"]` on the colima entry (a `docker` catalog entry with
a brew method already exists) or otherwise surface the docker-CLI prerequisite;
one-line desc updates on both entries stating the intended split (Apple
container = plain runtime on Apple Silicon; colima = compose path). Verify on
real hardware before changing default install flows.
