# Phase 4: Package Manager Redirect Policy - Research

**Researched:** 2026-09-05
**Domain:** Shell command interception (PATH shims + interactive aliases), Python subprocess exec-through, npm/pip/pnpm/volta ecosystem internals
**Confidence:** HIGH for the mechanical/shim-architecture questions; MEDIUM-HIGH for the two gated research questions (uv-pip parity, Volta-npm internals) — both resolved with primary-source evidence, not assumption.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `npx` (and any other tool this phase redirects) gets a NEW `REDIRECTED` shim mechanism, implemented parallel to the existing `BANNED` hard-block dict in `installer/guards.py` — never a generalization of `BANNED` itself. The existing hard-block shim (`shim_script`, 4-line POSIX-sh, exit 127) stays untouched and simple; a redirect shim execs into its target command, preserving the real exit code and stdout/stderr (e.g. `exec pnpm dlx "$@"`).
- **D-02:** `guard_status()`'s return shape stays an unchanged `{name: bool}` ("shim installed") — ROADMAP SC#6's literal ask. The doctor UI's per-tool label text is what distinguishes them: e.g. "redirected to pnpm dlx" for npx vs. "blocked" for npm. No new status enum, no ripple into `doctor.py`/`render.py` call sites that assume a plain bool today.
- **D-03:** `npx <pkg>` execs into `pnpm dlx "$@"` — not `pnpx` (pnpm's own shortcut for the same thing). Explicit and always available wherever pnpm is, no dependency on a separate `pnpx` binary/alias existing.
- **D-04:** pip/pip3 redirect research: is `uv pip <subcommand>` (`install`/`uninstall`/`list`/`show`/`freeze`/`compile`) a safe, argv-compatible drop-in for the pip invocations this project's shim needs to cover? If yes, pip/pip3 redirect the same way npx does (D-01/D-02 mechanism, reused). If research finds a real gap, pip/pip3 stay hard-blocked and the gap gets documented in the plan/summary — never force a redirect past what research actually confirms.
- **D-05:** `npm` itself (non-global invocations — `install`/`add`/`run`/`exec`/`ci`/`publish` without `-g`/`--global`) stays hard-blocked either way. Its own subcommand-allowlist decision remains a separate, later concern — explicitly NOT part of this phase.
- **D-06:** A `-g`/`--global` flag on `npm install`/`npm add` (and on `pnpm add -g` itself) is detected and redirected specifically to `volta install <pkg>` instead of `pnpm`. A non-global `npm install`/`npx` invocation still redirects to plain `pnpm`/`pnpm dlx` per D-03. Rationale: Volta is a toolchain-version-manager-plus-global-tool-shim layer with no local/per-project dependency-installation mechanism of its own — "global installs → volta, local project installs → pnpm" is the natural boundary.
- **D-07:** D-06 is gated on research first: does `volta install` shell out to npm internally for the actual install step? If so, it inherits npm's unrestricted-postinstall-script behavior, losing pnpm's gated-postinstall security advantage for anything moved to Volta. Record the finding either way — do not implement the redirect while treating this as assumed-safe.
- **D-08:** The Volta redirect is included in this phase specifically because it resolves `REQ-pnpm-global-reinstall-mitigation`'s root cause for anything moved to Volta. Concretely: after implementing D-06, determine whether any catalog tool still needs `pnpm add -g` at all. If the residual set is empty, `REQ-pnpm-global-reinstall-mitigation` is satisfied by elimination — record that explicitly. If any tool remains on `pnpm add -g`, implement the requirement's original mechanism (snapshot the pnpm-managed global set, reinstall it together in one invocation after `pnpm` itself updates) for that residual set, in this same phase.

### Claude's Discretion
- Exact wording of the doctor UI's per-tool status label text (D-02).
- Whether the `REDIRECTED` mechanism's dict/data structure lives in `installer/guards.py` alongside `BANNED` or in a small sibling module.
- Exact shape of the pip/pip3 argv-translation (e.g. does `pip install X` become `uv pip install X` via a straight passthrough, or does some flag need remapping) — determined by this research below.

### Deferred Ideas (OUT OF SCOPE)
- npm's own subcommand-allowlist decision (non-global invocations) — a separate, future decision.
- Applying "does a safe redirect exist" research to any *future* banned command beyond npm/npx/pip/pip3 — not an action item for this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-npx-ban | `guards.py:BANNED` gains an `"npx"` entry (or rather: npx moves straight to `REDIRECTED` since D-03 already resolved its target; the ban-test-extension instruction still applies to `tests/test_guards.py`) | Confirmed: `npx` is single-purpose (no subcommand surface), so no ban-then-decide-later step is needed — it goes directly to a `REDIRECTED` entry. See Architecture Patterns → Pattern 1. |
| REQ-npm-npx-redirect-policy | `npx` → `pnpm dlx "$@"` unconditional; pip/pip3 redirect only if `uv pip` is a safe drop-in; non-global npm stays hard-blocked | See "uv pip Parity Verdict" below — real, precise gaps found in `uninstall` and `compile`; recommendation is to keep pip/pip3 hard-blocked (Primary Recommendation section). `npx`→`pnpm dlx` verified safe by direct local testing (exit-code passthrough). |
| REQ-npm-global-volta-redirect | `-g`/`--global` on `npm install`/`npm add`/`pnpm add -g` → `volta install <pkg>`, gated on whether Volta shells to npm internally | See "Volta-Internals Verdict" below — CONFIRMED via Volta's own source: `volta install` runs a real `npm install --global ...` subprocess, no `--ignore-scripts` flag. This is a documented security-for-stability tradeoff, not a clean win — see Common Pitfalls. |
| REQ-pnpm-global-reinstall-mitigation | Determine residual `pnpm add -g` set after the Volta split; implement snapshot-reinstall mitigation if non-empty | Residual set is **not empty as of this phase**: `mmdc` (`installer/registry.toml:1646-1658`) is the only `kind="node"` tool in the registry today, and its move off pnpm is Phase 5's decision (`REQ-mmdc-install-decision`), not this phase's. Phase 4 must therefore implement the snapshot-reinstall mechanism for `mmdc` now, not "by elimination." See Runtime State Inventory and Common Pitfalls. |
</phase_requirements>

## Summary

This phase extends `installer/guards.py`'s existing `BANNED` hard-block dict with a parallel `REDIRECTED` mechanism, and answers two explicitly gated research questions before any Volta or pip/pip3 redirect ships.

**`npx` → `pnpm dlx "$@"`** is unconditionally safe: `npx` has no subcommand surface to allowlist, and a local test against this machine's real pnpm 11.9.0 confirms `pnpm dlx` propagates a genuine subprocess failure's exit code (tested: a 404 fetch failure returned exit 1 through `pnpm dlx`, not swallowed to 0). This is the phase's cleanest win and needs no further gating.

**`uv pip` as a pip/pip3 drop-in has real, documented gaps**, concentrated in exactly two of the six subcommands the phase asked about: `uninstall` (uv cascades to remove transitive dependencies pip leaves behind — a silent behavior change, not just a cosmetic one) and `compile` (uv requires an explicit `-o`/`--output-file`, uses a different extras-stripping default, and never writes index URLs unless asked — a bare `pip-compile`-shaped invocation would either hard-fail or silently produce a differently-shaped file). `install`/`list`/`show`/`freeze` are close enough (mostly PEP 503 name-normalization cosmetics and a missing `--user` flag that fails loudly, not silently). **Recommendation: keep pip/pip3 hard-blocked.** The existing shim mechanism intercepts the whole binary, not per-subcommand; forcing a blanket redirect past the `uninstall`/`compile` gaps would violate this phase's own stated non-goal ("without silently masking a real underlying failure").

**Volta's `volta install <pkg>` genuinely shells out to a real `npm install --global` subprocess** — confirmed by reading Volta's own source (`crates/volta-core/src/tool/package/install.rs`, function `run_global_install`), which builds and runs `npm install --global --loglevel=warn --no-update-notifier --no-audit <package>` with no `--ignore-scripts` flag. This was cross-checked empirically on this machine: `volta list all` shows every previously-Volta-installed package pinned to `npm@built-in`, and the bundled npm versions for the two pinned Node runtimes here are 10.9.8 and 11.17.0 — both predate npm v12's install-scripts-off-by-default change (GA per npm's own changelog, ~July 2026), so postinstall scripts run unrestricted today. pnpm, by contrast, has gated postinstall scripts behind an opt-in allowlist since pnpm v10 (`pnpm.io/supply-chain-security`). **The Volta redirect is a real, documented security-for-stability tradeoff** — it fixes the pnpm global-reinstall data-loss bug but reintroduces npm's classic unrestricted-postinstall-script model for anything moved to Volta. Ship it, but the doctor/policy copy must say so plainly (this satisfies D-07's "record the finding either way," it does not block the redirect — the user already accepted this tradeoff in D-06/D-08's rationale).

**A structural gap not previously flagged:** `volta` is not currently a registry.toml tool at all, and is not scheduled to become one in any of the 12 roadmap phases (it was named only as a placeholder in the original "Out of Scope" catalog-expansion note, never promoted to a real `REQ-*` item). The D-06 redirect literally cannot function on a machine without Volta pre-installed. This phase must add `volta` as a new system-tier registry entry (Homebrew on macOS — confirmed on `formulae.brew.sh/formula/volta` — or its official `curl https://get.volta.sh | bash` script on Linux) as a prerequisite for the redirect, or explicitly document that the redirect degrades to a "Volta not found" error message when absent. See Open Questions.

**Primary recommendation:** Ship `npx`→`pnpm dlx` and the npm-global/`pnpm add -g`→`volta install` redirects (with the security tradeoff documented in the UI copy and `volta` added as a new system-tier catalog prerequisite); keep pip/pip3 hard-blocked and document the `uv pip uninstall`/`compile` gap precisely; implement the pnpm-global-reinstall snapshot mechanism now for `mmdc`, the one tool currently on `kind="node"`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PATH-shim interception of banned/redirected binaries | CLI / Local Environment | — | Pure filesystem + PATH mechanism (`installer/guards.py`); no server or UI tier involved |
| Interactive-shell alias layer | CLI / Shell rc files | — | Faster in-shell UX on top of the PATH-shim layer (`ban_alias_block`); same tier as shims |
| Doctor/guard status reporting | TUI (Textual) presentation | CLI console (`app.py`) | `guard_status()` (pure) feeds both `render_guard_status` (console) and `wizard_app.py`'s guidance list (TUI) — one source of truth, two renderers |
| Volta global-install execution | CLI / External tool (Volta binary) | — | Delegated entirely to the `volta` binary; this project only routes argv to it, never re-implements Node/npm resolution |
| pnpm-global snapshot-reinstall mitigation | CLI / `installer/policy.py` (new Policy) | Registry (`installer/registry.toml`, source of truth for "which tools are `kind=node`") | No new state-tracking DB — the registry itself already answers "which tools use `kind=\"node\"`" per this codebase's existing all-live-check convention |

## Standard Stack

### Core

No new third-party libraries are introduced by this phase — it extends `installer/guards.py` using only the Python standard library (`os`, `pathlib`, `subprocess` via the existing `Runner` seam) and POSIX `sh`, exactly like the existing `BANNED` mechanism.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| (stdlib only) | — | Shim generation, sentinel checks, `exec` bodies | Matches existing `guards.py` precedent — no new dependency for a 4–8 line POSIX-sh body |

### Supporting

| Tool | Version (verified locally) | Purpose | When to Use |
|------|---------|---------|-------------|
| `pnpm` | 11.9.0 `[VERIFIED: local `pnpm --version` on this machine, 2026-09-05]` | Redirect target for `npx`/non-global `npm install` | Already the project's sanctioned Node package manager |
| `volta` | 2.0.2 `[VERIFIED: local `volta --version` on this machine, 2026-09-05]` | Redirect target for `-g`/`--global` npm/pnpm invocations | Only for global tool installs, per D-06 |
| `uv` | 0.12.5 `[VERIFIED: local `uv --version` on this machine, 2026-09-05]` | Would be the redirect target for pip/pip3 if adopted | Not recommended this phase — see uv-pip verdict below |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pnpm dlx` for npx | `pnpx`/`pnx` (pnpm's own aliases) | D-03 already rejected this: explicit `pnpm dlx` has no dependency on a second binary/alias name existing |
| Full pip/pip3 redirect | Partial redirect (only `list`/`show`/`freeze`, the three subcommands with no real behavior gap) | Technically feasible using the same argv-inspection technique the npm shim already needs for `-g` detection, but adds meaningful complexity for a smaller safety win — flagged as an option under Claude's Discretion, not the default recommendation |

**Installation:** N/A — no new packages installed by this phase's own code. `volta` becomes a new registry dependency for end users (see Open Questions).

**Version verification:** All three tool versions above were verified directly on this development machine via `<tool> --version`, not assumed from training data or search results.

## Package Legitimacy Audit

**N/A — this phase does not install any new PyPI/npm/crates packages into the project itself.** It modifies shell-shim behavior in `installer/guards.py` (pure stdlib) and, per the Open Questions section, potentially adds `volta` as a new `registry.toml` system-tier *tool* (not a Python/Node package dependency of this codebase). `volta`'s legitimacy as a tool: official GitHub org `volta-cli/volta` (36k+ stars class of adoption, referenced directly in Homebrew core — `formulae.brew.sh/formula/volta` `[CITED: formulae.brew.sh/formula/volta]`), not a slopsquat risk. If the planner adds `volta` as a registry entry, it should follow the project's own `REQ-registry-authoring-verification-checklist` discipline (Phase 6) rather than this audit's npm/pip-package-oriented checks, since it is a system tool install, not a package dependency.

## Architecture Patterns

### System Architecture Diagram

```
Interactive shell / non-interactive script / agent
        │
        │  runs `npx <pkg>` / `pip install X` / `npm install -g Y` / `pnpm add -g Y`
        ▼
┌─────────────────────────────────────────────────────────┐
│  PATH resolution (first match wins)                       │
│  ~/.local/bin (managed shim dir, if earlier on PATH)       │
└─────────────────────────────────────────────────────────┘
        │
        ├── name in BANNED (npm non-global, pip, pip3*) ─────► print "banned, use X" to stderr, exit 127
        │
        └── name in REDIRECTED (npx, npm -g*, pnpm add -g*) ─► argv-inspect (for npm/pnpm only) ─┐
                                                                                                    │
                                                    ┌───────────────────────────────────────────────┘
                                                    ▼
                                    -g/--global present?  ── yes ──► exec volta install "$@" (stripped of -g)
                                                    │
                                                   no
                                                    ▼
                                    exec into the real underlying tool:
                                    npx      → exec pnpm dlx "$@"
                                    npm (no -g) → still BANNED (exit 127) — non-global npm is out of scope
                                    pnpm add -g → exec into the REAL pnpm binary unmodified (self-recursion hazard — see Pitfalls)

* pip/pip3: research below recommends staying in BANNED, not moving to REDIRECTED.
```

### Recommended Project Structure

No new files are required; extend the existing three files that already know about `BANNED`:

```
installer/
├── guards.py     # add REDIRECTED: dict[str, RedirectSpec] parallel to BANNED; redirect_shim_script()
├── policy.py     # ban_policy() gains a sibling (or extension) that also installs REDIRECTED shims/aliases
└── guidance.py   # guard_guidance() differentiates "redirected to X" vs "blocked" label text (D-02)
```

### Pattern 1: Unconditional redirect shim (npx)

**What:** A POSIX-sh shim that `exec`s straight into the real target, passing `"$@"` through untouched, so the exit code and stdout/stderr are the real subprocess's, not the shim's.
**When to use:** Single-purpose commands with no "stay blocked in some cases" branch — `npx` is the only one in this phase's scope.
**Example (new function parallel to `shim_script`):**
```sh
#!/bin/sh
# tools-installer-redirect-shim
exec pnpm dlx "$@"
```
This is a straightforward extension of the existing `shim_script()` pattern in `installer/guards.py:31-39` — same sentinel-comment idea (a distinct sentinel, e.g. `# tools-installer-redirect-shim`, so `is_our_shim`-equivalent ownership checks can tell a redirect shim from a ban shim from a real binary), same idempotent-write/mode-0o755 install path (`install_shims`'s existing loop shape, `installer/guards.py:50-67`).

### Pattern 2: Argv-conditional redirect (npm -g detection)

**What:** A shim that inspects `"$@"` for `-g`/`--global` before deciding whether to redirect (to Volta) or fall back to the existing ban behavior (exit 127).
**When to use:** `npm` specifically — non-global stays hard-blocked (D-05), only the global-flag shape redirects (D-06).
**Example:**
```sh
#!/bin/sh
# tools-installer-redirect-shim
for arg in "$@"; do
  case "$arg" in
    -g|--global)
      # Strip -g/--global; volta install takes bare package names.
      set -- "$@"
      # (actual arg-filtering logic goes here — see Pitfalls: keep this simple,
      #  a single -g/--global anywhere in argv is enough to trigger the redirect)
      exec volta install "$@"
      ;;
  esac
done
echo "tools-installer: 'npm' (non-global) is banned on this machine — use pnpm (pnpm add -g <pkg>)." >&2
exit 127
```
This is new territory relative to the existing `BANNED` shims (which are all unconditional print-and-exit), but the sentinel/idempotency/ownership machinery is unchanged.

### Pattern 3: Wrapping a *sanctioned* tool's own subcommand (pnpm add -g)

**What:** Unlike `npm`/`npx`/`pip`, `pnpm` is never banned — it must remain a fully transparent pass-through for every subcommand except the one shape (`add -g ...`) that D-06 asks to redirect. This means the generated shim for `pnpm` cannot simply "fall back to a ban message" in the non-matching case (Pattern 2's fallback) — it must `exec` into the **real** `pnpm` binary, not itself.
**Why this matters:** If the shim is placed in a directory earlier on PATH than the real `pnpm` and is also literally named `pnpm`, a naive `exec pnpm "$@"` inside the shim would re-resolve `pnpm` via PATH and find *itself* again — infinite recursion. This is a materially different problem from the existing `BANNED` shims, none of which need to invoke the real version of the tool they replace.
**Recommended fix:** Resolve and bake in the real `pnpm` binary's absolute path at shim-write time (the same moment `install_shims`-equivalent logic already writes the file), e.g. via `shutil.which("pnpm")` called *before* the shim directory is prepended to `PATH` for that lookup, or by explicitly searching PATH entries after the shim dir. Embed that absolute path literally into the generated shim text (refreshed on every `install_shims`-equivalent call, matching the existing idempotent "created"/"refreshed" reporting). This mirrors how many "wrap a sanctioned binary" shims solve the identical problem (nvm/direnv-style tools resolve and cache the "real" binary location rather than relying on `$PATH` order at exec time).
**Flag to planner:** this is the single most novel and highest-risk piece of this phase's mechanism — the existing `BANNED`/`REDIRECTED` shims for npm/npx/pip never had to solve "don't call myself," because none of those tools are ever the real, needed, fully-functional binary. `pnpm` is. Treat this as a distinct sub-task with its own test coverage (a fake "real pnpm" binary in `tmp_path`, verifying non-`-g` invocations reach it, and `-g` invocations reach a fake `volta` instead).

### Anti-Patterns to Avoid

- **Generalizing `BANNED` into a single dict with a "mode" field:** CONTEXT.md's D-01 explicitly forbids this. Keep `REDIRECTED` a separate, parallel structure — the two mechanisms have different shim bodies (print+exit vs. exec-through) and, per Pattern 3, different self-recursion concerns that a single generalized dict would obscure.
- **Silently redirecting pip/pip3 "because uv exists":** the research below shows a real behavior gap in `uninstall`/`compile`. A silent redirect there would violate this phase's own SC#1 framing ("without silently masking a real underlying failure").
- **Assuming Volta is present on every machine:** it is not currently a catalog tool. A redirect shim that assumes `volta` resolves on PATH will fail confusingly on a machine that never installed it. See Open Questions.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Subprocess execution with real exit-code propagation | A custom Python subprocess wrapper inside `guards.py` | POSIX `sh`'s own `exec` builtin inside the shim script | `exec` replaces the shim process image entirely — the exit code, stdout, and stderr ARE the real command's, with zero wrapping code needed. This is simpler and more correct than spawning a subprocess and manually forwarding `returncode`/streams from Python. |
| "Is pnpm-managed global set stale" tracking | A new JSON/SQLite state file | The existing registry (`installer/registry.toml`) queried live for `kind == "node"` tools | Matches this codebase's existing all-live-check convention (`status.is_installed`, `guard_status`, `has_managed_block`) — no new persisted state needed, since the registry already is the source of truth for which tools use `kind="node"`. |
| Argv parsing for `-g`/`--global` detection | A custom shell-flag parser with getopts | A simple `case`/substring scan over `"$@"` (POSIX `sh` has no native getopt for long-options like `--global` anyway) | The existing `BANNED` shims are already deliberately "4-line POSIX-sh" — keep the redirect shims in the same minimal spirit; a single-purpose flag scan is enough, a real argument parser is overkill for a shim. |

**Key insight:** Every mechanism this phase needs (exec-through, argv inspection, idempotent shim writes, sentinel-based ownership) is either already present in `guards.py` or a small, POSIX-sh-native extension of it. The only genuinely new problem is Pattern 3's self-recursion hazard when wrapping `pnpm` itself — everything else is additive, not novel.

## Common Pitfalls

### Pitfall 1: Redirecting pip/pip3 past the `uninstall`/`compile` gap

**What goes wrong:** `pip uninstall X` silently removes more than the user asked for (transitive deps `pip` would have left behind); `pip-compile`-shaped invocations either hard-error (missing `-o`) or silently produce a differently-shaped lockfile (extras-stripping default flip).
**Why it happens:** `uv pip` is deliberately not a byte-for-byte reimplementation of `pip` — Astral's own docs state "these commands do not exactly implement the interfaces and behavior of the tools they are based on" `[CITED: docs.astral.sh/uv/pip/compatibility/]`.
**How to avoid:** Keep pip/pip3 hard-blocked (this research's recommendation). If the planner later wants a narrower redirect, scope it explicitly to `install`/`list`/`show`/`freeze` only, with `uninstall`/`compile` still routed to the ban message.
**Warning signs:** A user reports "I ran pip uninstall X and now Y is broken too" — that is exactly uv's transitive-cascade behavior surfacing.

### Pitfall 2: Treating the Volta redirect as a clean win

**What goes wrong:** Assuming Volta's global-install path avoids npm's postinstall-script risk because it's "not npm."
**Why it happens:** Volta's own documentation describes package resolution as "npm-style" without prominently stating that dependency installation itself runs a real `npm install --global` subprocess.
**How to avoid:** Documented and confirmed via source in this research (`crates/volta-core/src/tool/package/install.rs::run_global_install`) — the doctor/policy UI copy for this redirect must say something like "redirected to volta install — note: still runs npm postinstall scripts unrestricted" rather than implying full parity with pnpm's gated model.
**Warning signs:** A future audit assumes "everything not on pnpm is safe from postinstall scripts" and is wrong for anything moved to Volta.

### Pitfall 3: Self-recursion when the shim wraps a sanctioned tool's own binary

**What goes wrong:** A `pnpm` shim placed earlier on PATH that calls `exec pnpm "$@"` for the non-`-g` case calls itself, infinitely (or until stack/fd exhaustion), instead of the real pnpm.
**Why it happens:** Shell `exec <name>` re-resolves `<name>` via `$PATH` from scratch; if the shim's own directory is still first on PATH, it matches itself again.
**How to avoid:** Bake the real, resolved absolute path to the underlying binary into the generated shim text at write time (see Architecture Patterns → Pattern 3), never rely on runtime PATH re-resolution for the pass-through case.
**Warning signs:** Any test that runs the real shim (not a mock) inside a `tmp_path` PATH sandbox is the only way this bug reliably surfaces — a unit test that mocks `exec`'s target away won't catch it.

### Pitfall 4: Assuming `REQ-pnpm-global-reinstall-mitigation` is satisfied "by elimination" without checking `registry.toml`

**What goes wrong:** Skipping the snapshot-reinstall mechanism because "Volta now handles global installs."
**Why it happens:** D-06/D-08's framing could be read as "the split makes pnpm-global installs obsolete," but the Volta *redirect* is aimed at interactively-typed `npm install -g`/`pnpm add -g` commands — it does **not** change the fact that `installer/executors.py`'s `kind="node"` executor installs through pnpm by design (`installer/executors.py:74`: `runner(["pnpm", "add", "-g", require_str(method, "npm_pkg")])`), so every `kind="node"` tool remains a pnpm-managed global. **(Erratum 2026-09-05: an earlier version of this sentence added "never routed through the shim/PATH-interception layer at all" — that clause is false and has been removed; see the ERRATUM under "The internal executor call this redirect does NOT touch" below.)**
**How to avoid:** Grep `registry.toml` for `kind = "node"` before declaring the residual set empty. As of this research, `mmdc` (`installer/registry.toml:1646-1658`, quoted: `[[tool]]\nid = "mmdc"\n...\nrequires = ["pnpm"]\n[[tool.method]]\nkind = "node"\nnpm_pkg = "@mermaid-js/mermaid-cli"`) is the only such tool, and Phase 5 (not Phase 4) owns the decision to move it off pnpm. The residual set is therefore non-empty *right now* — implement the snapshot-reinstall mechanism for `mmdc` in this phase.
**Warning signs:** A plan that closes `REQ-pnpm-global-reinstall-mitigation` with "N/A — no tools remain on pnpm add -g" without having grepped `registry.toml` for `kind="node"` first.

### Pitfall 5: Assuming `volta` is present on every machine this redirect ships to

**What goes wrong:** `exec volta install "$@"` fails with "command not found" on any machine that never separately installed Volta — since `volta` is not currently a `registry.toml` tool anywhere in this project's 12-phase roadmap.
**Why it happens:** Volta was named only in an early "Out of Scope" placeholder list during requirements ingestion and never promoted to a real `REQ-*` catalog-expansion item in the phases that did ship (Phase 7/8).
**How to avoid:** Add `volta` as a new system-tier `registry.toml` entry in this phase (Homebrew on macOS — confirmed present in homebrew-core, `formulae.brew.sh/formula/volta` — or the official `curl https://get.volta.sh | bash` script on Linux, `[CITED: docs.volta.sh/guide/getting-started]`), or explicitly design the redirect shim to detect Volta's absence and fail with a clear, actionable message rather than a bare "command not found."
**Warning signs:** SC#4/SC#6 verification ("Volta redirect works") passing only because the verifying machine happens to already have Volta installed for unrelated reasons — see this session's own dev machine, which does.

## Code Examples

### Confirmed-safe exit-code passthrough for `pnpm dlx` (tested locally, not assumed)

```
$ pnpm dlx this-package-should-not-exist-xyz123 >/tmp/out.log 2>&1; echo "REAL EXIT: $?"
REAL EXIT: 1
```
`[VERIFIED: local pnpm 11.9.0, this machine, 2026-09-05]` — a genuine registry 404 failure inside `pnpm dlx` propagates as exit code 1 to the calling shell, not swallowed to 0. This directly answers SC#2's "preserving the underlying command's real exit code" requirement for the `npx` → `pnpm dlx` redirect.

### Confirmed Volta-shells-to-npm source (fetched directly from `volta-cli/volta`'s own repo)

```rust
// crates/volta-core/src/tool/package/install.rs, function run_global_install
let mut command = create_command("npm");
command.args([
    "install",
    "--global",
    "--loglevel=warn",
    "--no-update-notifier",
    "--no-audit",
]);
command.arg(&package);
```
`[VERIFIED: github.com/volta-cli/volta/blob/main/crates/volta-core/src/tool/package/install.rs, fetched 2026-09-05]` — note the absence of `--ignore-scripts`; npm's default (pre-v12) behavior of running `preinstall`/`install`/`postinstall` scripts is unmodified by Volta's invocation.

### Confirmed empirically: this machine's Volta-managed npm versions predate npm v12's opt-in-scripts default

```
$ volta run --node 22.22.3 npm --version
10.9.8
$ volta run --node 24.19.0 npm --version
11.17.0
```
`[VERIFIED: local Volta 2.0.2, this machine, 2026-09-05]` — both are pre-v12; npm v12's `allowScripts`-off-by-default change is GA per npm/GitHub's own changelog as of ~July 2026 `[CITED: github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/, docs.npmjs.com/cli/v12/using-npm/changelog/]`, but the bundled npm versions actually pinned to this machine's Volta-managed Node runtimes are older and still run scripts unrestricted by default.

### `mmdc`'s exact current registry entry (the sole residual `kind="node"` tool)

```toml
# installer/registry.toml:1646-1658
[[tool]]
id = "mmdc"
name = "Mermaid CLI"
category = "diagram"
cmd = "mmdc"
priority = "P2"
audience = "both"
tier = "user"
desc = "Render Mermaid diagrams to SVG/PNG/PDF from the command line"
requires = ["pnpm"]
[[tool.method]]
kind = "node"
npm_pkg = "@mermaid-js/mermaid-cli"
```
`[VERIFIED: installer/registry.toml:1646-1658, read this session]`

### The internal executor call this redirect does NOT touch (title superseded — see ERRATUM below)

```python
# installer/executors.py:73-74
# pnpm only — bare npm is banned. `add -g` installs the package's CLI globally.
runner(["pnpm", "add", "-g", require_str(method, "npm_pkg")])
```
`[VERIFIED: installer/executors.py:73-74, read this session]` — this is a direct list-argv subprocess call through the project's own `Runner` seam.

> **ERRATUM (2026-09-05, cross-AI plan review cycle 1 — CRITICAL):** the sentence that
> originally followed here, and the parallel claim in Pitfall 4 above, said this call is
> "never resolved through the shell/PATH-shim layer" and that Phase 4's redirect work has
> "zero effect" on it. **Both are wrong.** `installer/run.py:19-26`'s `run_command` is
> `subprocess.run(cmd, check=True)`, and `subprocess.run` resolves a bare `argv[0]` through
> the live `PATH` exactly as a shell does. Once Phase 4 writes an argv-conditional `pnpm`
> wrapper into `~/.local/bin` — a directory the doctor insists is first on PATH — this call
> hits that wrapper and a `kind="node"` catalog install silently becomes
> `volta install <pkg>`, losing pnpm's gated postinstall. The fix lives in plan 04-03
> Task 1 (`installer/guards.py::real_pnpm`, `_node` invoking an absolute path) and is reused
> by plan 04-05's reinstall. Pitfall 4's conclusion — that the residual `kind="node"` set is
> non-empty and still needs the snapshot-reinstall mechanism — is unaffected and still holds;
> only its stated reason was wrong.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| npm lifecycle scripts run automatically on every install (classic behavior, still true for npm ≤11.x) | npm v12: `allowScripts` defaults to off; scripts require explicit `npm approve-scripts` opt-in | GA ~July 2026 per npm/GitHub's own changelog `[CITED: github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/]` | Directly relevant to the Volta redirect's security tradeoff: once the Node/npm versions Volta pins on a given machine cross into v12+, the "Volta inherits npm's unrestricted postinstall risk" finding in this research would need re-verification — it is a version-dependent fact, not a permanent one. As of this research (npm 10.9.8/11.17.0 pinned locally), the risk is real and current. |
| pnpm ran postinstall scripts for all dependencies (pre-v10) | pnpm v10+ blocks `postinstall` in dependencies by default, gated behind an `allowBuilds`-style trusted-dependency allowlist | pnpm v10 (referenced, not independently dated here) `[CITED: pnpm.io/supply-chain-security]` | This is the exact "gated-postinstall security model" the CONTEXT.md and REQUIREMENTS.md reference as pnpm's advantage over npm/Volta. |
| pnpm global installs shared one directory across all `pnpm add -g` invocations | pnpm v11 isolates each invocation's (or invocation-group's) global install into its own hash-keyed directory | pnpm v11 (already researched and cited in this project's own PRD, `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md:17-28`) | This is the confirmed root cause of the global-reinstall-loses-packages bug this phase's `REQ-pnpm-global-reinstall-mitigation` addresses — filed upstream as pnpm#11520 and pnpm#11587, per this project's own prior research. Re-cited here, not re-derived. |

**Deprecated/outdated:**
- Treating "any redirect target that isn't literally npm" as automatically free of postinstall-script risk — Volta's own install path proves otherwise (see Pitfall 2).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `uv pip`'s documented differences (transitive-uninstall cascade, `compile` defaults) are severe enough to justify keeping pip/pip3 hard-blocked rather than redirecting | Summary, Pitfall 1 | If judged too conservative, the planner may choose a narrower partial redirect instead (already flagged as an Alternatives Considered option) — low risk, since this research explicitly hands the planner both the data and a fallback option rather than a bare recommendation |
| A2 | `pnpm add -g` needs its own wrapping shim (Pattern 3) to satisfy D-06's literal wording ("and on `pnpm add -g` itself") | Architecture Patterns → Pattern 3 | If the planner instead interprets D-06 as applying only to `npm install -g`/`npm add -g` (leaving bare `pnpm add -g` un-intercepted, just documented as "don't do this, use volta"), Pattern 3's self-recursion-avoidance work becomes unnecessary. This is a genuine ambiguity in D-06's wording worth confirming with the user before planning locks it in — see Open Questions Q1. |
| A3 | `volta` should become a new system-tier `registry.toml` entry as part of this phase | Summary, Pitfall 5 | If the team prefers to treat Volta as an out-of-band prerequisite (documented, not installed by this project), the redirect ships with a "Volta not found" failure mode instead — a real but smaller scope decision the planner needs to make explicitly, not by default |

**If this table is empty:** N/A — see above; all three assumptions are judgment calls flagged for planner/user confirmation, not verifiable facts.

## Open Questions

1. **Does D-06's "(and on `pnpm add -g` itself)" mean pnpm itself needs a wrapping shim (Pattern 3), or does it only mean documentation/guidance steering users away from `pnpm add -g` toward `volta install`?**
   - What we know: `pnpm` is the sanctioned tool and is never in `BANNED`; wrapping it introduces the self-recursion hazard described in Pitfall 3, a materially bigger and more delicate change than anything the existing `guards.py` mechanism does today.
   - What's unclear: Whether the user's intent in D-06 was a literal PATH-level intercept of `pnpm add -g` (requiring Pattern 3) or a softer redirect that only actually intercepts `npm install -g`/`npm add -g` (which IS safe to implement with the existing "shim a banned/discouraged binary" shape, since `npm` is never a needed pass-through target).
   - Recommendation: Confirm with the user before planning locks scope. If the answer is "yes, literally intercept `pnpm add -g` too," budget real design/test time for Pattern 3; if "no, npm-global is enough," Pattern 3 and its self-recursion risk drop out of scope entirely, meaningfully shrinking the phase.

2. **Should `volta` become a new `registry.toml` catalog entry in this phase, or is its presence an accepted external prerequisite?**
   - What we know: `volta` is not currently installable through this project at all, in any of the 12 roadmap phases (see Summary/Pitfall 5).
   - What's unclear: Whether adding a new system-tier catalog entry is in scope for a phase titled "Package Manager Redirect Policy," or whether that belongs to a future catalog-expansion phase, with Phase 4 shipping a redirect that simply degrades gracefully (clear error) when Volta is absent.
   - Recommendation: Given the redirect is non-functional without Volta, and this phase's own success criteria treat the redirect as a first-class deliverable (SC#4), lean toward adding the registry entry now — but this is the user's call, not a research-determined fact.

3. **What exactly triggers the pnpm-global-reinstall snapshot mechanism, given Phase 12's "update action" mechanism doesn't exist yet?**
   - What we know: REQUIREMENTS.md explicitly un-couples this requirement from Phase 12 ("this dependency only applies if a residual pnpm-managed set actually remains after Phase 4's research" — and it does, per Pitfall 4). REQUIREMENTS.md's original framing says the trigger "should fire when `pnpm` itself is the tool being updated," which assumed Phase 12's update-delegation mechanism as a hook point.
   - What's unclear: Since no self-update/update-action mechanism exists anywhere in this codebase yet (confirmed: no `self_update`/`update_command` pattern found in any `installer/*.py` file this session), Phase 4 needs its own standalone trigger — e.g., a manual Policy action in the Policies view ("reinstall pnpm-managed globals now"), or hooking into wherever this project's own pnpm-repair/reinstall flow already exists (none found this session).
   - Recommendation: Treat this as a scoping question for the planner — implement the snapshot/reinstall *logic* as a pure, testable function now (querying `registry.toml` for `kind="node"` tools, snapshotting via `pnpm list -g --json`-equivalent, reinstalling via one `pnpm add -g <all>` call), and expose it as a manual Policy action for now, explicitly deferring automatic pnpm-self-update-triggering to whenever Phase 12's update mechanism actually ships.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `pnpm` | npx redirect target, existing sanctioned tool | ✓ | 11.9.0 | — |
| `volta` | npm-global/`pnpm add -g` redirect target | ✓ (on this dev machine) | 2.0.2 | Not guaranteed on end-user machines — see Open Question 2/Pitfall 5 |
| `uv` | Would-be pip/pip3 redirect target (not adopted this phase) | ✓ | 0.12.5 | N/A — pip/pip3 stay hard-blocked per this research's recommendation |

**Missing dependencies with no fallback:**
- `volta` on an end-user machine that has never installed it separately — no fallback exists today (see Open Question 2). This blocks the redirect from functioning, not from being implemented.

**Missing dependencies with fallback:**
- None — `uv`'s absence is moot since pip/pip3 are recommended to stay hard-blocked.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-cov 5.x (`pyproject.toml` `[tool.pytest.ini_options]`) `[VERIFIED: pyproject.toml, read this session]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.coverage.report]`) |
| Quick run command | `uv run pytest tests/test_guards.py -x` |
| Full suite command | `make test` (`uv run pytest --cov`, per `Makefile`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-npx-ban / REQ-npm-npx-redirect-policy | `npx <pkg>` shim execs into `pnpm dlx "$@"`, preserving exit code | unit (shim script generation + `sh -n` syntax check, mirroring existing `test_shim_script_is_valid_posix_sh`) | `uv run pytest tests/test_guards.py -k redirect -x` | ✅ `tests/test_guards.py` (existing file, extend per REQ-npx-ban's explicit instruction not to duplicate) |
| REQ-npm-global-volta-redirect | `npm install -g pkg` and `pnpm add -g pkg` argv-detection routes to `volta install pkg` | unit (shim body logic against a fake `volta`/fake real-`pnpm` binary in `tmp_path`, per Pattern 3's recommended test shape) | `uv run pytest tests/test_guards.py -k volta -x` | ❌ needs new test cases — Wave 0 gap |
| REQ-pnpm-global-reinstall-mitigation | Snapshot pnpm-managed globals (queries `registry.toml` for `kind="node"`), reinstall together in one invocation | unit (pure function: given a fake registry + fake `pnpm list -g --json` output, produces the correct single reinstall argv) | `uv run pytest tests/test_policy.py -k pnpm_global -x` | ❌ needs new test file/cases — Wave 0 gap |
| D-02 doctor label text | "redirected to X" vs "blocked" text differentiation | unit (pure `guidance.py` function, mirroring existing `guard_guidance` tests) | `uv run pytest tests/test_guidance.py -x` (if this file doesn't exist, extend wherever `guard_guidance` is currently tested) | ❓ unverified — grep `tests/` for `guard_guidance` coverage before planning locks the test file target |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_guards.py tests/test_policy.py -x`
- **Per wave merge:** `make test` (full suite + coverage)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] New test cases in `tests/test_guards.py` for `REDIRECTED` shim generation, ownership sentinel, and the argv-conditional npm/pnpm bodies (extending the existing file per REQ-npx-ban's explicit "not duplicated into a parallel file" instruction).
- [ ] New test coverage for the pnpm-global snapshot/reinstall pure function (file location TBD by planner — likely `tests/test_policy.py`, alongside the existing `ban_policy`/`tweak_policy` tests).
- [ ] Confirm whether `guard_guidance`'s existing test coverage (if any, in `tests/test_guidance.py` or similar — not directly verified this session) needs new cases for the "redirected to X" label text, or whether it's untested today and needs a new file.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — no auth surface in this phase |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A — this runs with the invoking user's own privileges throughout, same as the existing `BANNED` mechanism |
| V5 Input Validation | yes | Argv passed through to `exec` is never parsed/evaluated by this project's own code beyond a simple `-g`/`--global` substring/case scan — no shell-injection surface introduced, since `"$@"` is expanded and passed as discrete argv elements in POSIX sh (not string-interpolated into a second shell) |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Postinstall-script supply-chain attack (a malicious npm package's `postinstall` running with full user privilege) | Tampering / Elevation of Privilege | pnpm's gated-postinstall allowlist (`pnpm.io/supply-chain-security`) is the project's existing mitigation for pnpm-routed installs; the Volta redirect **reintroduces this exposure** for anything moved to Volta, per this research's core finding — mitigate by documenting the tradeoff in UI copy, not by silently assuming it's covered |
| Shim self-recursion / infinite loop (Pitfall 3) | Denial of Service (of the shim itself, low severity — a hung shell command, not a system compromise) | Bake the real underlying binary's resolved path into the generated shim text at write time, never re-resolve via PATH at `exec` time for the pass-through case |
| A real binary shadowing/being shadowed by the shim (pre-existing `guard_path_warning` mechanism) | Tampering (a stale/malicious binary earlier on PATH than the shim) | Already handled by the existing `guard_path_warning` function (`installer/guards.py:115-142`) — extend its `BANNED` iteration to also cover `REDIRECTED` names, no new mechanism needed |

## Sources

### Primary (HIGH confidence)
- `docs.astral.sh/uv/pip/compatibility/` — uv pip vs. pip documented behavioral differences (fetched directly, official Astral docs)
- `github.com/volta-cli/volta/blob/main/crates/volta-core/src/tool/package/install.rs` — Volta's own source, `run_global_install` function, fetched directly
- `pnpm.io/supply-chain-security` — pnpm's own documentation of its gated-postinstall model
- `pnpm.io/global-packages` — pnpm's own documentation of per-invocation global-install isolation
- `github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/` — GitHub's own changelog announcing npm v12's `allowScripts` default change
- `docs.npmjs.com/cli/v12/using-npm/changelog/` — npm's own changelog (confirms GA status)
- Local empirical tests on this machine (2026-09-05): `pnpm --version` (11.9.0), `volta --version` (2.0.2), `uv --version` (0.12.5), `pnpm dlx <nonexistent-pkg>` exit-code test, `volta list all`, `volta run --node <ver> npm --version` for both pinned runtimes
- `installer/guards.py`, `installer/policy.py`, `installer/guidance.py`, `installer/render.py`, `installer/executors.py`, `installer/registry.toml`, `tests/test_guards.py` — this project's own source, read directly this session
- `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md` — this project's own prior research (pnpm#11520/#11587 root-cause confirmation), cited not re-derived, per the task's explicit instruction

### Secondary (MEDIUM confidence)
- `formulae.brew.sh/formula/volta` — confirms Volta is in homebrew-core (WebSearch-surfaced, not independently fetched)
- `docs.volta.sh/guide/getting-started`, `docs.volta.sh/advanced/packages` — official Volta docs, fetched but did not fully clarify internals (superseded by the direct source-code fetch above)
- WebSearch summaries of `deepwiki.com/volta-cli/volta` architecture pages — third-party (AI-generated) documentation of Volta's internals, used only to locate the right source files, not as the basis for any claim in this document

### Tertiary (LOW confidence)
- None used as the basis for a stated claim — all load-bearing claims in this document were cross-checked against a primary source or local empirical test.

## Metadata

**Confidence breakdown:**
- uv-pip parity verdict: HIGH — based directly on Astral's own compatibility docs, not inferred
- Volta-npm-internals verdict: HIGH — based on Volta's own source code (a specific function, specific argv), cross-checked empirically against this machine's actual pinned npm versions
- Shim/redirect mechanism design (Patterns 1-3): HIGH for Patterns 1-2 (direct extension of proven, already-shipped `guards.py` code); MEDIUM for Pattern 3 (a genuinely new problem for this codebase, recommended solution is standard practice elsewhere but untested in this project)
- pnpm-global residual-set finding (mmdc): HIGH — directly grepped and read `installer/registry.toml`, confirmed exactly one `kind="node"` entry
- Volta-as-new-catalog-entry gap: HIGH confidence the gap exists (verified: no `volta` string anywhere in `registry.toml`, no `REQ-*` item for it in `.planning/REQUIREMENTS.md`); the *resolution* (Open Question 2) is a genuine judgment call for the user, not a research-determined fact

**Research date:** 2026-09-05
**Valid until:** 2026-10-05 (30 days) — EXCEPT the npm-v12/Volta-postinstall-risk finding specifically, which is version-dependent and should be re-verified (`volta run --node <pinned-version> npm --version`) at implementation time if this phase is executed more than a few weeks after this research, since npm v12's rollout is actively in progress as of this writing.
