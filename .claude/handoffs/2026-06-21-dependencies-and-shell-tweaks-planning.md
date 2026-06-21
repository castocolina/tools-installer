# Handoff: plan "Catalog Dependencies & Shell Tweaks"

**Created:** 2026-06-21
**For:** a fresh session, to produce an implementation plan (do NOT implement here).

## What to do

1. Read the unified PRD: **`docs/prds/dependencies-and-shell-tweaks-v1.0-prd.md`**.
   It is self-contained and approved. It merges two efforts:
   - **Workstream A — Tool Dependencies & Node-Package Installs** (the deferred
     tool-dependencies effort, never implemented beyond the `Tool.requires=()`
     seam; its standalone PRD has been deleted and folded in here).
   - **Workstream B — Shell Tweak Bundles** (the env-tweak follow-on anticipated by
     `unified-ui-redesign-v1.0-prd.md` Phase 4).
2. Invoke the **`superpowers:writing-plans`** skill to turn the PRD into an
   executable plan under `docs/superpowers/plans/`. Then implement with
   `superpowers:executing-plans`.

## Suggested sequencing (from the PRD)

Do **Workstream B first** (smaller, self-contained, no node-runtime risk, ships
value immediately), then **Workstream A** (A4 full-catalog audit is the long pole).
The two are independent; phases B1, B2, A1–A4 are each one validate-green commit.

## Key constraints (non-negotiable, from CLAUDE.md)

- **English only** in every output/identifier/comment/commit, regardless of request
  language.
- **100% coverage on `installer/`** (not the 90% floor); **pyright strict, no
  suppressions**; never bypass a quality gate — fix the root cause.
- **Coherent commits**; `make validate && make test` must pass on each commit's
  exact tree.
- `setup.py` is the **untested, pyright-excluded IO boundary** (the composition
  root). Pure logic lives in `installer/`.
- **Safety:** E2E sandboxes `HOME` via `monkeypatch.setenv("HOME", tmp_path)`. NEVER
  run a real doctor/wizard/guard/uninstall or write tweaks against the dev machine's
  real home.

## Architecture seams already in place (so the plan retrofits cleanly)

- **Workstream B mirrors the pip/npm ban exactly:**
  - `installer/policy.py` — generic `Policy` (id, label, description, `active`,
    idempotent `apply`/`remove` → `PolicyResult`). Its docstring already says
    *"future env tweaks slot in with no screen changes."* Add a `tweak_policy(...)`
    factory parallel to `ban_policy`.
  - `installer/guards.py` — the ban's block pattern to copy: marker-delimited block
    written via `installer/shellrc.py`'s `apply_block` / `strip_block`. Reuse those
    with per-bundle markers `# >>> tools-installer tweak:<id> >>>`.
  - New `installer/tweaks.py` — `TweakBundle` + curated `BUNDLES` (the four bundles)
    + `applicable_bundles(platform)` for the Linux gating of `apt-upgrade`.
  - `setup.py` builds the policy list; the **Policies tab renders `Policy`
    instances generically — no screen code changes**.
  - All tweak blocks land in the **same `~/.myshellrc`** the ban uses (user
    requirement). `wait_time` uses `printf` (not `echo -ne`) for bash/zsh parity —
    the reference implementation is in the PRD.
- **Workstream A:** reference implementation is **uzkit**
  (`/Users/ramon/git/personal/uzkit/tools/installer`, `engine.py` for the resolver).
  The `Tool.requires=()` no-op seam already exists (`installer/model.py`,
  surfaced in `installer/catalog_tui.py`'s detail bar). Add `npm_pkg`, a `"node"`
  kind, the pure resolver, `install_node` (pnpm-only), ladder wiring, then the
  catalog audit.

## Current repo state

- Branch `feat/unified-ui-shared-pattern` (unified-UI follow-on) is unmerged; `main`
  has unified-UI Phases 1–4. Confirm the working branch before starting.
- See `memory/roadmap-status.md` for the full done/pending map.
