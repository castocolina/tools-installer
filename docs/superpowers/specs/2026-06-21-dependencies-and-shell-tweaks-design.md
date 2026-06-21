# Catalog Dependencies & Shell Tweaks — Design

**Date:** 2026-06-21
**Status:** Approved — ready for `superpowers:writing-plans`.
**Design-of-record:** [`docs/prds/dependencies-and-shell-tweaks-v1.0-prd.md`](../../prds/dependencies-and-shell-tweaks-v1.0-prd.md).

This spec does **not** restate the PRD. The PRD is the approved design for
architecture, requirements, phases (B1, B2, A1–A4), and the non-negotiables. This
document records only what the PRD left open and what was verified before planning:

1. The canonical tweak-bundle bodies (the PRD named them but gave bodies only for
   `wait_time` and the `claude` alias).
2. The A4 scope decision (full-catalog audit, included).
3. Confirmation that every architectural seam the PRD relies on exists in the code
   as described — so the plan retrofits cleanly with no surprises.

---

## Seam verification (done before planning)

The PRD claims a set of "already in place" seams. Each was checked against the
current tree on branch `feat/unified-ui-shared-pattern`:

- **`installer/policy.py`** — generic `Policy(id, label, description, active, apply,
  remove)` + `PolicyResult` / `PolicyLayer`, a `ban_policy(...)` factory composing
  `installer/guards.py`, and a shared `_RELOAD_HINT`. The module docstring already
  states *"future env tweaks slot in with no screen changes."* A `tweak_policy(...)`
  factory parallel to `ban_policy` fits directly. **Confirmed.**
- **`installer/shellrc.py`** — `apply_block(content, block, begin=…, end=…)` and
  `strip_block(content, begin, end)` already take **configurable begin/end markers**.
  Per-bundle markers (`# >>> tools-installer tweak:<id> >>>` /
  `# <<< tools-installer tweak:<id> <<<`) reuse this idempotent block machinery
  with no changes to `shellrc`. **Confirmed.**
- **`installer/model.py`** — `Tool.requires: tuple[str, ...] = ()` no-op seam is
  present. `METHOD_KINDS` is the method-kind taxonomy (`script`, `github_release`,
  …); A1 adds `"node"` there and adds `npm_pkg: str = ""` to `Tool`. **Confirmed.**
- **`installer/tool_browser.py`** — the detail bar renders through a generic
  `Adapter.detail_text(item)` slot that is markup-capable (`detail_is_markup`). The
  `requires: X, Y` line is a change to the catalog adapter's `detail_text` only —
  the reserved slot is already wired. **Confirmed.**
- **`installer/uninstall.py`** — `classify_tools(...)` and `plan_uninstall(...)`
  exist; the uninstall **reverse-dependency warning** (A4) is genuinely new code on
  top of them (no reverse-dep helper exists yet). **Confirmed (new code expected).**
- **uzkit `engine.py`** (`/Users/ramon/git/personal/uzkit/tools/installer`) — the
  resolver reference is real and maps 1:1 to the PRD's resolver:
  - `with_required(selected, catalogue, …)` → transitive drag-in,
  - `required_but_disabled(selected, dragged)` → warnings,
  - `order_for_install(tools)` → *"Stable topological sort so each tool's requires
    install first (cycle-safe)."*

  The A2 resolver ports these three behaviors, returning
  `(install_order, dragged_in, warnings)`. **Confirmed.**

No seam was found missing or different from the PRD's description.

---

## Resolved decision 1 — Canonical tweak-bundle bodies

Source: the user's two gists
(`c910d4fc2f58ea9735680dfd73bb9b11`, `756e6aef938a3bf7af6979887979948e`). They are
**not** present in the uzkit reference repo, which is why the PRD could not carry
them. Each bundle is a frozen `TweakBundle(id, label, description, platforms, body)`
in a curated `BUNDLES` tuple in `installer/tweaks.py`, written into `~/.myshellrc`
as exactly one marker-delimited block.

### `docker` — Docker shortcuts (all platforms; soft-needs `watch`)

```sh
docker-ps() {
    watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | sed "s/0\.0\.0\.0://g; s/\[::\]://g; s|/tcp||g; s|/udp||g"'
}
alias docker-stats='docker stats --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"'
alias docker-memory='docker-stats'
```

- `docker-memory` is intentionally an **alias-to-an-alias** (user-confirmed). It
  expands correctly in interactive shells, which is the only context where
  `~/.myshellrc` is sourced. Kept verbatim.
- The `\t` tokens inside `--format` are **Go-template tabs consumed by docker**, not
  shell escapes, so they are byte-identical under bash and zsh — no dialect risk.
- `watch` is a **soft dependency**: defining `docker-ps` never fails; it only errors
  if *run* without `watch` (notably bare macOS). Documented, never an install-time
  failure (matches the PRD's `docker-ps`-needs-`watch` edge case).

### `countdown` — `wait_time` (all platforms)

Uses the PRD's portable `printf` form, **not** the gist's `echo -ne` /
`: $((secs--))` (those differ across sh/bash/zsh):

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
replaces the non-portable `: $((secs--))`; the final `printf` clears the line. This
is the one genuinely dialect-sensitive helper, hence the portability rewrite.

### `claude-skip` — claude skip-permissions (all platforms)

```sh
alias claude='claude --dangerously-skip-permissions'
```

### `apt-upgrade` — selective apt upgrade (Linux only)

Gated out of macOS via `applicable_bundles(platform)`:

```sh
alias apt-upgrade='sudo apt install --only-upgrade $(apt list --upgradeable 2>/dev/null | grep -v "Listing" | cut -d/ -f1 | tr "\n" " ")'
```

`$(…)`, `cut`, and `tr "\n" " "` are POSIX and behave identically under bash and zsh.

### Cross-shell correctness summary

Every body above is POSIX alias/function syntax delivered through the
already-sourced `~/.myshellrc`. The only escape-sequence helper (`wait_time`) uses
`printf`. Per-bundle markers keep each block independently toggleable, never
touching another bundle or user content, never duplicating on re-enable (reusing
`apply_block` / `strip_block`).

---

## Resolved decision 2 — A4 scope: full-catalog audit included

This milestone delivers the **complete** Workstream A, including A4's exhaustive
audit: live-verify inter-tool dependencies and node-package candidates across all
catalog tools (~49 today) and populate `requires` / `kind="node"` / `npm_pkg`,
live-verified the same way prior registry batches were verified against live
releases. A4 remains the long pole and is sequenced last; A1–A3 ship and are
provable on `mmdc` before the audit completes, but the audit is in-scope for this
milestone (not deferred).

---

## What carries over unchanged from the PRD

- **Sequencing:** Workstream B first (B1 tweak core + bundles, B2 policy factory +
  wiring), then Workstream A (A1 model/registry, A2 resolver, A3 node install +
  ladder, A4 audit + UI surfacing). Each phase is one validate-green commit.
- **Workstream B wiring:** `installer/tweaks.py` (`TweakBundle`, `BUNDLES`,
  `applicable_bundles`, write/remove/present helpers) + `tweak_policy(bundle, …)` in
  `installer/policy.py` (parallel to `ban_policy`, `active` = marker present, shared
  `_RELOAD_HINT`). `setup.py` builds
  `[ban_policy(…), *(tweak_policy(b, …) for b in applicable_bundles(platform))]`,
  all targeting `~/.myshellrc`. **No Policies-screen code changes.**
- **Workstream A wiring:** pure resolver in `installer/` (ports uzkit's three
  functions), `install_node` → `pnpm add -g <npm_pkg>` (never bare `npm`), deps-first
  install order with soft-warn + skip-dependent on failure, detail-bar `requires:`
  line, uninstall reverse-dependency warn-but-allow. Version-constraint solving is
  out of scope; the `requires` shape stays forward-compatible with a future
  `{id, min}` form.
- **Non-negotiables:** English only; 100% coverage on new `installer/` code;
  pyright strict with no suppressions; `setup.py` stays the untested IO boundary;
  deterministic install order; idempotent, marker-confined tweak writes; E2E
  sandboxes `HOME` via `monkeypatch.setenv("HOME", tmp_path)` and never writes to the
  dev machine's real home.

---

## Acceptance criteria

The PRD's Acceptance Criteria (Functional A, Functional B, Quality Standards, User
Acceptance) apply unchanged. This spec adds one concrete check derived from the
resolved bodies:

- The emitted `docker` block contains `docker-ps`, `docker-stats`, and
  `docker-memory`; `docker-stats`/`docker-memory` use the documented `--format`
  strings; and the block is valid under both `bash -n` and `zsh -n`.
- The emitted `countdown` block uses `printf` (no `echo -ne`) and is valid under
  `bash -n` and `zsh -n`.
- `apt-upgrade` appears only when `applicable_bundles` is resolved for Linux.
