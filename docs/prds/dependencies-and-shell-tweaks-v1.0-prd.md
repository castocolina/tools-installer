# Catalog Dependencies & Shell Tweaks — Product Requirements Document (PRD)

> **For the implementing session:** This PRD is the handoff artifact. It is
> self-contained: a fresh session can read it and produce an implementation plan
> via `superpowers:writing-plans` without re-deriving context. It unifies two
> previously separate efforts into one forward roadmap:
>
> - **Workstream A — Tool Dependencies & Node-Package Installs** (replaces the
>   deferred tool-dependencies effort — its standalone PRD was approved but never
>   implemented beyond the `Tool.requires=()` no-op seam, and has been removed in
>   favor of this unified roadmap).
> - **Workstream B — Shell Tweak Bundles** (the env-tweak follow-on anticipated by
>   `unified-ui-redesign-v1.0-prd.md` Phase 4: *"the ban and future env tweaks as
>   a first-class tab"*).
>
> They are unified because both **extend the installer beyond single-tool
> installs** through the **same pure-core + decisor seams** already in place: each
> is a 100%-covered `installer/` addition surfaced in an existing UI slot (the
> catalog detail bar / the Policies tab), with `setup.py` remaining the untested IO
> boundary. Reference implementation for Workstream A: **uzkit**
> (`/Users/ramon/git/personal/uzkit/tools/installer`).

---

## Requirements Description

### Background

- **Business problem:**
  - **(A) No dependency resolution and no way to install node-package CLIs.** Tools
    like `mmdc` (mermaid CLI, npm package `@mermaid-js/mermaid-cli`) can't be
    installed at all — there is no node/npm-package install method, and bare `npm`
    is deliberately banned. Even where a tool depends on another installable tool,
    nothing installs them in order or pulls in a missing dependency, and removing a
    runtime silently breaks everything that needed it.
  - **(B) No curated shell ergonomics.** The Policies tab manages exactly one
    policy (the pip/npm ban). Users re-add the same quality-of-life aliases and
    helper functions by hand to every machine, and hand-rolled versions are often
    not portable across bash (macOS/Linux) and zsh.
- **Target users:** Developers provisioning an AI dev environment who need
  node-based CLIs (diagram/codegen/agent tooling) alongside the existing catalog,
  and who want the same vetted shell shortcuts wired in consistently, toggleable.
- **Value proposition:** Tools that depend on others install **correctly, in the
  right order, with missing dependencies pulled in automatically** and nothing
  silently broken on uninstall; and a small set of **vetted, cross-shell tweak
  bundles** that each enable/disable independently from the Policies tab, landing
  in the same managed `~/.myshellrc` the ban already uses.

### Feature Overview

#### Workstream A — Tool Dependencies & Node-Package Installs

- **Core features:**
  1. A new **`kind = "node"` install method** — installs `npm_pkg` via
     **`pnpm add -g <pkg>`** (never bare npm; consistent with the pip/npm ban).
     Node-package tools declare `requires = ["pnpm"]` (plus any node runtime the
     audit finds necessary, provided via `fnm`/pnpm).
  2. A declarative **`Tool.requires` field** (list of catalog tool ids).
  3. A pure **dependency resolver:** transitive closure + a **stable, cycle-safe
     topological sort** so each tool's `requires` install first.
  4. **Auto drag-in + warn:** selecting a tool pulls in its missing dependencies
     automatically and surfaces a visible notice (uzkit's "dependency wins" model).
  5. **UI surfacing:** the catalog detail bar shows a `requires: X, Y` line; the
     uninstall view **warns (but allows)** when removing a tool others depend on.
- **Explicitly NOT included:** version-constraint solving (e.g. "Node ≥ 22") — the
  `requires` shape is designed so a future `{id, min}` form fits, but no version
  resolution now; bare `npm`/`pip` (banned); arbitrary system-package dependency
  management (only inter-catalog deps); auto-removing dependents on uninstall
  (warn-but-allow only; no cascade, no block).

#### Workstream B — Shell Tweak Bundles

- **Core features:**
  1. **Curated tweak bundles** (hardcoded in code, mirroring the existing `BANNED`
     dict pattern), each surfaced as its own **`Policy`** row in the existing
     Policies tab, independently toggleable. v1 ships four bundles:

     | Toggle | Contents | Platform |
     |---|---|---|
     | **Docker shortcuts** | `docker-ps()` (watch refresh), `docker-stats`, `docker-memory` | all (soft-needs `watch`) |
     | **Countdown helper** | `wait_time()` | all |
     | **claude skip-permissions** | `alias claude='claude --dangerously-skip-permissions'` | all |
     | **apt selective upgrade** | `alias apt-upgrade=…` (selective `apt` upgrade) | Linux only |

  2. **Single managed file:** every enabled bundle is written as its own
     marker-delimited block into the **same `~/.myshellrc`** the pip/npm ban uses,
     so existing bash/zsh sourcing covers it with no extra wiring.
  3. **Cross-shell correctness:** alias/function syntax is POSIX (identical in bash
     and zsh); `wait_time` is implemented with `printf` (not `echo -ne`) so escape
     sequences behave identically across sh/bash/zsh.
  4. **Per-bundle independence:** enabling/disabling one bundle never touches
     another, never touches user content, and never duplicates entries.
- **Explicitly NOT included:** user-supplied/arbitrary aliases (curated set only in
  v1); a registry-driven (TOML) tweak schema (curated-in-code now, registry form is
  a possible later evolution); managing rc files other than `~/.myshellrc`.

### Detailed Requirements

#### Workstream A

- **Input/Output:** registry input per tool — `kind = "node"`,
  `npm_pkg = "@scope/pkg"`, `requires = ["pnpm", ...]`. Resolver input: the set of
  selected tool ids + the full catalog. Output: an **ordered install list**
  (dependencies first), the **set of dragged-in ids**, and a list of **warnings**
  (unavailable/disabled deps).
- **User interaction:** selecting a tool with missing `requires` auto-adds them and
  shows a notice; install proceeds dependency-ordered; a failed dependency
  soft-warns and **skips its dependents** (does not abort the whole run).
- **Data requirements:** `Tool.requires: tuple[str, ...] = ()` (already a no-op
  seam) and `Tool.npm_pkg: str = ""` (used only by `kind = "node"`); validation at
  load — every `requires` id must resolve to a real catalog tool (unknown id is a
  registry/config error caught by a test).
- **Edge cases:** cycles (stable, cycle-safe sort; a genuine registry cycle is a
  config error surfaced by a dedicated test, not a hang); dependency unavailable on
  the platform (warn + skip dependent); dependency present but disabled/deselected
  (dependency wins — dragged in + installed, with a warning); `pnpm` missing for a
  `node` tool (`requires = ["pnpm"]` drags it in; if pnpm install fails, the node
  tool soft-warns and is skipped).

#### Workstream B

- **Input/Output:** input — the curated `BUNDLES` definitions + the resolved
  platform + the managed `~/.myshellrc` path. Output — the same file with each
  enabled bundle present as exactly one marker-delimited block; `active` state per
  bundle derived from marker presence.
- **User interaction:** the Policies tab lists each applicable bundle with on/off
  toggles and per-bundle status, alongside the existing ban, reusing the Phase-2
  reload guidance. No new screen code.
- **Data requirements:** a frozen `TweakBundle(id, label, description, platforms,
  body)`; a curated `BUNDLES` tuple; per-bundle markers
  `# >>> tools-installer tweak:<id> >>>` / `# <<< tools-installer tweak:<id> <<<`.
- **Edge cases:** missing rc file (apply creates it / remove is a no-op); re-enable
  (replaces only the marked block); platform gating (`apt-upgrade` absent on
  macOS); `docker-ps` soft-depends on `watch` — the function *defines* cleanly and
  only errors if *run* without `watch`, so absence is never an install-time failure.

### Reference `wait_time` implementation (portable)

```sh
wait_time() {
    secs=${1:-0}
    while [ "$secs" -gt 0 ]; do
        printf '    WAIT %s\033[0K\r' "$secs"
        sleep 1
        secs=$((secs - 1))
    done
    printf '\033[0K\r'
}
```

`printf` interprets `\033` consistently across sh/bash/zsh; `secs=$((secs - 1))`
replaces the non-portable `: $((secs--))`; the final `printf` clears the line.

## Design Decisions

### Technical Approach

- **Workstream A — node method = `pnpm add -g` (ban-consistent).** `install_node`
  resolves pnpm and runs `pnpm add -g <npm_pkg>`; bare `npm` is never used. Resolution
  lives in the pure `installer/` core (100% covered, pyright-strict), mirroring
  uzkit's `engine.py`: transitive closure + a stable, cycle-safe topological sort,
  returning install order + dragged-in set + warnings. Screens only render; the
  install ladder consumes the resolved order. UI surfacing reuses the redesign seams
  (catalog detail-bar `requires:` slot + uninstall reverse-dependency warning).
  Version-constraint forward-compatibility: parse only the string form now, but keep
  the field/types shaped so a future `requires = [{ id = "node", min = "22" }]` form is
  reachable without a data migration.
- **Workstream B — tweaks mirror the ban exactly, zero UI changes.** A new
  `installer/tweaks.py` defines `TweakBundle` + a curated `BUNDLES` tuple and reuses
  `shellrc.apply_block` / `strip_block` with per-bundle markers (the same idempotent
  block machinery the ban uses). `installer/policy.py` gains a `tweak_policy(bundle,
  …)` factory parallel to `ban_policy`, whose `active` is "marker present in the rc
  file" and whose apply/remove closures write/strip the bundle's block, sharing the
  ban's `_RELOAD_HINT`. `setup.py` (IO boundary) builds the policy list as
  `[ban_policy(…), *(tweak_policy(b, …) for b in applicable_bundles(platform))]`, all
  targeting the same `~/.myshellrc`. The Policies tab renders `Policy` instances
  generically, so **no screen code changes** — exactly what the redesign Phase 4
  docstring promised.
- **Shared architecture:** both workstreams are pure-core additions surfaced through
  existing seams under the decisor model (the UI collects decisions / renders; the IO
  boundary applies). Neither adds a new screen.

### Constraints

- pyright strict, **no suppressions**; **100% coverage** on `installer/`; `setup.py`
  stays the untested IO boundary.
- **English only.** Never invoke bare `npm`/`pip`.
- Deterministic install order (stable sort) so runs are reproducible and testable.
- All tweak writes are idempotent and confined to marked blocks; user content in
  `~/.myshellrc` is never altered.
- **Safety:** E2E tests sandbox `HOME` via `monkeypatch.setenv("HOME", tmp_path)` and
  NEVER run a real doctor/wizard/guard/uninstall or write tweaks against the dev
  machine's home.

### Risk Assessment

- **A — cycles:** a registry cycle could break ordering. *Mitigation:* cycle-safe
  sort + a test asserting a synthetic cycle is reported as a config error.
- **A — pnpm/node runtime absent:** node tools can't install without pnpm.
  *Mitigation:* `requires = ["pnpm"]` drag-in; soft-warn + skip on failure.
- **A — data accuracy (full-catalog audit):** wrong/missing `requires` ships broken
  installs. *Mitigation:* live-verify each declared dependency, as prior registry
  batches were verified against live releases. The audit (A4) is the long pole; the
  mechanism (A1–A3) ships and is provable on `mmdc` before the audit completes.
- **B — shell-dialect leakage:** only executable helpers with escape sequences risk
  dialect differences. *Mitigation:* `printf`-based `wait_time`; everything else is
  POSIX alias/function syntax delivered through the already-sourced `~/.myshellrc`.
- **B — soft dependency (`watch` on macOS):** `docker-ps` needs `watch`.
  *Mitigation:* defining the function never fails; document the dependency; it only
  errors when actually run without `watch`.

## Acceptance Criteria

### Functional Acceptance — Workstream A
- [ ] A registry tool with `kind = "node"`, `npm_pkg`, and `requires = ["pnpm"]`
      installs via `pnpm add -g <npm_pkg>` (asserted: the executed command, no bare `npm`).
- [ ] Selecting `mmdc` with `pnpm` not selected **auto-adds `pnpm`** and surfaces a notice.
- [ ] The resolver returns dependencies **before** dependents (asserted on a multi-level graph).
- [ ] A synthetic dependency **cycle** is reported as a config error, never a hang.
- [ ] A dependency **unavailable on the platform** warns and the dependent is skipped.
- [ ] The catalog detail bar shows a `requires: …` line when deps exist (and nothing when empty).
- [ ] The uninstall view **warns but allows** when removing a tool others depend on.
- [ ] Every `requires` id in the shipped registry resolves to a real catalog tool (integrity test).

### Functional Acceptance — Workstream B
- [ ] Each applicable bundle appears as its own toggle in the Policies tab alongside the ban.
- [ ] Enabling a bundle writes exactly one marker-delimited block into `~/.myshellrc`;
      disabling strips exactly that block; re-enabling does not duplicate.
- [ ] Toggling one bundle never alters another bundle's block or surrounding user content.
- [ ] `apt-upgrade` is offered on Linux and absent on macOS (platform gating, asserted).
- [ ] `wait_time` is emitted with `printf` (no `echo -ne`); the block is valid in bash and zsh.
- [ ] An enabled bundle is in effect in a new shell because `~/.myshellrc` is sourced (E2E, sandboxed HOME).

### Quality Standards
- [ ] 100% coverage on new `installer/` code; `uv run pyright` clean (no suppressions).
- [ ] No bare `npm`/`pip` anywhere in the node install path.
- [ ] `make validate && make test` green on each commit.

### User Acceptance
- [ ] Installing `mmdc` end-to-end against a sandbox yields a working `mmdc` with its
      dependencies installed in order.
- [ ] Enabling the Docker / countdown / claude / apt bundles makes the aliases/functions
      available in a fresh shell on the relevant platform.
- [ ] README documents the `node` kind, `requires`, auto-drag-in, the uninstall
      reverse-dependency warning, **and** the tweak bundles + how to toggle them.

## Execution Phases

> **Suggested sequencing:** Workstream B (smaller, self-contained, no node-runtime
> risk) is a good warm-up and ships value immediately; Workstream A follows, with its
> full-catalog audit (A4) as the long pole. The two are independent — the planner may
> interleave — but each phase below is one coherent, validate-green commit.

### Workstream B — Shell Tweak Bundles

**B1: Tweak core + bundles**
**Goal:** Curated bundles + idempotent block machinery, fully covered.
- [ ] `installer/tweaks.py`: `TweakBundle`, curated `BUNDLES` (the four), per-bundle
      markers, `write_tweak`/`remove_tweak`/`tweak_present`, `applicable_bundles(platform)`.
- [ ] `wait_time` body uses `printf` per the reference above.
- [ ] Unit cover: block bodies, write/remove idempotency on `tmp_path`, active detection,
      platform gating excludes `apt-upgrade` on macOS.
- **Deliverables:** pure tweak core at 100% coverage.

**B2: Policy factory + wiring**
**Goal:** Each bundle is a toggleable `Policy` in the existing tab.
- [ ] `tweak_policy(bundle, …)` in `installer/policy.py` (parallel to `ban_policy`):
      `active` from marker presence; idempotent apply/remove; shared `_RELOAD_HINT`.
- [ ] `setup.py` builds `[ban_policy(…), *(tweak_policy(b, …) for b in applicable_bundles(platform))]`,
      all targeting `~/.myshellrc`. No Policies screen changes.
- [ ] Headless test: apply → active → remove → inactive, per-bundle.
- [ ] Sandbox E2E (HOME via tmp_path): toggle each bundle, assert its block in
      `~/.myshellrc` and that the file is sourced.
- **Deliverables:** discoverable, separately-toggleable tweak bundles; ban unaffected.

### Workstream A — Tool Dependencies & Node-Package Installs

**A1: Model & Registry**
**Goal:** Declarative dependency + node-package data, validated.
- [ ] Add `npm_pkg: str = ""` to `Tool`; keep `requires` (already present) and parse both.
- [ ] Add `"node"` to the method/kind taxonomy; validate `requires` ids resolve to real
      tools (registry-integrity test).
- **Deliverables:** model + parsing + validation, fully covered.

**A2: Resolver**
**Goal:** Pure, cycle-safe dependency resolution with drag-in.
- [ ] Transitive closure + stable topological sort (mirror uzkit `engine.py`), returning
      `(install_order, dragged_in, warnings)`.
- [ ] Cover: linear chain, diamond, missing-dep drag-in, unavailable-on-platform,
      synthetic cycle → config error.
- **Deliverables:** `installer/`-level resolver at 100% coverage.

**A3: Node install strategy + ladder wiring**
**Goal:** Actually install node packages, dependency-ordered.
- [ ] `install_node` → `pnpm add -g <npm_pkg>` (ban-consistent; pnpm resolution +
      global-bin setup as needed).
- [ ] Install the resolved order deps-first; soft-warn + skip dependents on failure.
- [ ] Sandbox E2E: installing `mmdc` drags in `pnpm`, installs in order, `mmdc` runs.
- **Deliverables:** node tools installable; `mmdc` proven end-to-end.

**A4: Full-catalog audit + UI surfacing**
**Goal:** Seed real dependency data across the catalog and surface it.
- [ ] Audit every catalog tool for inter-tool dependencies and node-package candidates;
      add `requires`/`kind="node"`/`npm_pkg`, live-verified.
- [ ] Catalog detail-bar `requires:` line (the redesign's reserved slot — already wired).
- [ ] Uninstall reverse-dependency warning (warn-but-allow).
- [ ] README updates (node kind, requires, drag-in, reverse-dep warning, tweak bundles).
- **Deliverables:** populated registry + UI surfacing; feature complete.

---

**Document Version:** 1.0
**Created:** 2026-06-21
**Replaces:** the deferred tool-dependencies effort (its standalone PRD was deleted;
that scope is now Workstream A here)
**Origin:** unifies the deferred tool-dependencies PRD with the shell-tweak-bundles
brainstorm (anticipated by `unified-ui-redesign-v1.0-prd.md` Phase 4).
**Status:** Approved scope. No code yet — implementation plan to be created in a fresh
session via `superpowers:writing-plans`.
