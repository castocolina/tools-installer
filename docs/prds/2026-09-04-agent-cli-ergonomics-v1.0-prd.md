# Agent CLI Ergonomics: Permissive Aliases and Model Defaults - Product Requirements Document (PRD)

## Requirements Description

### Background

The catalog already has one tweak in this exact shape: `_CLAUDE_BODY =
"alias claude='claude --dangerously-skip-permissions'"`
(`installer/tweaks.py`) - a shell alias that pre-fills a more permissive
execution mode. The user wants this extended to `codex` and `opencode`, and
separately wants a `cursor-agent`/`cursor` convenience that defaults the
model to `gpt-5.6-sol` with a 1M context window and high reasoning effort
when the user does not pass `--model` themselves.

Two pieces of research were explicitly requested before finalizing this PRD
(2026-09-04):

1. **What is opencode's actual permissive-mode flag?** There is no
   `opencode --dangerously-skip-permissions` equivalent shipped by opencode
   itself - permissions are config-driven (`opencode.json`, each action type
   set to `allow`/`ask`/`deny`). What does exist is `opencode --auto`, which
   auto-approves requests that would otherwise prompt while **explicit deny
   rules still apply** - a materially different (safer, narrower) semantic
   than Claude Code's bypass mode, not a drop-in equivalent. A third-party
   patch project claiming a closer equivalent exists
   (`mynameistito/opencode-dangerously-skip-permissions`) but installing an
   unofficial permission-bypass patch is a different trust decision than
   using an official flag - **not recommended by this PRD without a
   separate, explicit decision from the user.**
2. **What is cursor-agent's exact bracket syntax for model/context/effort,
   and does it actually work?** **Resolved, definitively, 2026-09-04:** the
   documented bracket syntax is `model[key=value,...]`, e.g.
   `'claude-opus-4-8[context=1m,effort=high,fast=false]'`. Fetching the full
   Cursor community-forum thread on this (not just an earlier summary of it)
   surfaced a **direct reply from a Cursor employee**, thread closed
   2026-07-26 with no ETA: bracket-syntax model parameterization is **not
   implemented at all** in `--model` - it is documented in `--help` by
   mistake, not a transient bug that might get fixed soon. Separately, the
   same thread confirms **1M context is only reachable through interactive
   "Max Mode" via the in-app `/model` picker** - there is no non-interactive
   equivalent, bracket syntax or otherwise. This is more severe than this
   PRD's earlier framing ("an open, documented bug") - it is an unimplemented
   feature with no path to 1M context outside interactive use. **This
   changes the wrapper's design, not just its blocked status - see the
   revised requirements and Open Questions below.**

A third finding, not explicitly asked for but relevant: Cursor's own docs
describe `--permission-mode bypassPermissions` as the *current* Claude Code
flag, with `--dangerously-skip-permissions` as an "older equivalent" - the
existing `claude-skip` tweak in this repo may already be on a legacy flag
name. Worth a follow-up check, not blocking this PRD.

**Why this wrapper matters at all (clarified by the user, 2026-09-04):**
cursor-agent's model selection is **stateful, not per-invocation** - whatever
model/effort was last selected (from Cursor Desktop, from an interactive CLI
session, or from a `--model` flag on a prior non-interactive call) persists
in the CLI's own config and becomes the *default* for the next invocation
that passes no `--model` at all. So the risk this PRD exists to close is not
"the user has to type a long flag every time" - it is "a non-interactive
`cursor-agent` call with no `--model` silently inherits whatever was last
selected somewhere else (Desktop, an interactive session), which could be a
weaker or unexpected model." The wrapper's job is to **actively assert a
known-good default on every bare invocation**, not merely to offer a
convenience shortcut.

### Target Users

- Developers who run `claude`/`codex`/`opencode` locally in trusted,
  disposable workspaces and want less prompt friction, the same way the
  existing `claude-skip` tweak already serves.
- Developers using `cursor-agent`/`cursor` who want a sane, high-capability
  default model without typing the full bracket syntax every time.

### Value Proposition

- Extend an already-working, already-accepted pattern (`claude-skip`) to the
  other two agent-host CLIs this catalog cares about, without inventing a
  new mechanism.
- Save `cursor-agent` users from retyping a verbose model override, once the
  underlying CLI bug is confirmed fixed.

## Feature Overview

### Core Features

1. `codex-skip` and `opencode-auto` tweaks, parallel to `claude-skip`:
   aliases that pre-fill the closest available permissive/auto-approve flag
   for each CLI, respecting whatever additional flags the user types after
   the alias (plain shell aliases are prefix substitution - user-typed
   arguments append after the aliased flags, so this is inherent to the
   mechanism already in use, not new work).
2. A `cursor-agent` default-model wrapper that injects a verified-real
   `--model <slug>` flag (a plain model id, no brackets - see below) on any
   bare invocation, since bracket-syntax context/effort overrides are
   confirmed unimplemented and 1M context is unreachable non-interactively
   regardless.
3. Address the self-update durability problem (below) using a shell
   alias/function - not a file-based shim in the tool's own install
   directory - because an alias lives in shell config, not in the path a
   self-updating binary rewrites.

### Feature Boundaries

In scope:

- The `codex-skip`/`opencode-auto` tweak bundles themselves.
- The self-update durability analysis and its recommended mechanism.
- Re-verifying `claude-skip`'s flag is still current (`--dangerously-skip-permissions`
  vs. `--permission-mode bypassPermissions`) as a fast side-check.

Out of scope:

- The third-party `opencode-dangerously-skip-permissions` patch - flagged
  as a separate, explicit decision, not bundled into this PRD's default
  scope.
- 1M-context, non-interactive use of `cursor-agent` - confirmed unreachable
  (Max Mode is interactive-only); this PRD's wrapper targets high-effort
  default model selection only, not context size.
- Any change to how `Policy`/`TweakBundle` work as a mechanism - every
  feature here reuses the existing shape.

## Detailed Requirements

### Permissive-Alias Requirements

- `codex-skip`: alias `codex` to whatever codex's actual bypass-permissions
  flag is - **needs the same live-verification pass** every registry
  addition gets in this project (this PRD does not assume codex's flag name
  without checking it against codex's own current docs at implementation
  time, the same discipline `2026-09-04-package-manager-policy-v1.0-prd.md`
  established for install methods).
- `opencode-auto`: alias `opencode` to `opencode --auto`, explicitly *not*
  a bypass-permissions equivalent - the tweak's label/description in the
  Policies detail panel must be honest about the narrower semantic (explicit
  deny rules still apply), so a user does not mistake it for `claude-skip`'s
  full bypass.
- Every alias must be a plain shell alias (matching `_CLAUDE_BODY`'s
  existing shape) so user-supplied flags append after the injected ones -
  this is what "respect the user's own parameters" means in practice for a
  shell alias, and it is already how `claude-skip` behaves today.
- None of these change the underlying CLI's own default when invoked via
  its full path or `command <name>` - matching the existing ban/tweak
  precedent of being opt-in and bypassable, not a hard override.

### cursor-agent Default-Model Requirements (revised, 2026-09-04)

- **Bracket syntax is dropped from this design entirely** - it is confirmed
  unimplemented, not merely buggy, so no wrapper should ever emit it.
- Wrapper alias/function: when `cursor-agent`/`cursor` is invoked with no
  `--model` flag, inject `--model <exact-verified-model-slug>` - a **plain
  model id, no bracket suffix** - selecting a high-effort "sol" variant;
  when the user passes their own `--model`, do not inject anything (needs a
  shell function checking `$@` for `--model`, not a plain alias, since a
  plain alias cannot conditionally omit its injected text - same shape as
  originally planned, only the injected value changes).
- **The exact slug is not yet known and must be confirmed at implementation
  time**, not typed from memory: run `cursor-agent --list-models` (or
  whatever the CLI's own current model-listing invocation is - verify the
  flag name too) to get the live catalog, then pick the current high-effort
  "sol" family variant from that real list. This mirrors the
  `ai-kit-spec-config` skill's own rule for unfamiliar model ids: never
  guess a model string, always cross-check it against the tool's own live
  listing before shipping a flag that references it.
- Effort is expressed however `cursor-agent`'s real flag surface expresses
  it for a non-bracket invocation (a separate `--effort`-style flag, or
  baked into the model slug itself, e.g. `...-high`) - determine this from
  the same live listing/`--help` output, not assumed from the (now
  confirmed non-functional) bracket-attribute convention.
- No wrapper claim about context size: since 1M context is confirmed
  unreachable non-interactively, the wrapper's description/UI copy must not
  imply it sets context - only that it sets a default model/effort.

### Self-Update Durability Requirement

The user's own framing of the core problem: agent-host CLIs on macOS
frequently self-update in place (rewriting the binary at the same
user-local path, e.g. wherever `cursor-agent`/`codex` actually lives), so
any mechanism that depends on that path being stable at setup time is
fragile. Three approaches were weighed:

1. **A file-based shim ahead on PATH** (this project's existing ban
   mechanism, `guards.py`) - the shim itself does not get overwritten by the
   target tool's self-update (the shim lives in this installer's managed bin
   dir, not the tool's own install path), so this is actually durable *for
   intercepting the command name* - but it is designed for hard-blocking,
   not for injecting default flags into a real invocation.
2. **A shell alias/function in rc** (this project's existing tweak
   mechanism, `tweaks.py`) - equally durable, since it lives in shell
   config, not on disk at the tool's install path, and shell alias/function
   lookup happens *before* PATH search in bash/zsh - so a tool rewriting its
   own binary in place does not affect an alias pointing at its command
   name. **This is the recommended mechanism** - it is simpler than a shim
   for this use case (injecting flags, not blocking) and this project
   already has working precedent (`claude-skip`).
3. **A daemon that re-asserts the alias/shim after every self-update** -
   unnecessary given (2) is already durable by construction; adding a
   watchdog daemon would be solving a problem the alias approach does not
   actually have.

The deeper question the user raised - "what if the tool auto-updates itself
*while running*, mid-session" - is a different, harder problem: a running
process holding an open file handle to its old binary, or re-executing
itself after a self-update, is outside what any shell-level alias/shim can
address. This PRD's recommendation (shell alias/function) is durable across
the tool being *re-invoked* after an update, not durable against a change
the tool makes to its own behavior *within* an already-running session -
that is inherent to how the target CLI implements self-update, not
something this installer can control from outside.

## Design Decisions

### Technical Approach

- All three new tweaks (`codex-skip`, `opencode-auto`, and the blocked
  `cursor-agent` wrapper) reuse `TweakBundle`/`tweak_policy` unchanged - no
  new mechanism, following the same reasoning that ruled out a daemon above.
- The `cursor-agent` wrapper, once unblocked, needs a shell *function*
  (not a plain alias) since it must conditionally omit its injection - this
  is new within `tweaks.py`'s existing bodies only in that it is
  conditional, not in requiring new architecture (`_DOCKER_BODY` already
  demonstrates a multi-line function body in this exact file).

### Risks

- Aliasing `opencode` to `--auto` and describing it loosely as "permissive
  mode" would mislead users about its actual (narrower) semantics - the
  Detailed Requirements above are explicit about this specifically to
  prevent that.
- Shipping the wrapper with a guessed (not live-verified) model slug would
  make `cursor-agent` invocations fail in a new, installer-caused way -
  this is why the slug must be confirmed against the CLI's own live model
  listing at implementation time, not typed from this PRD's research.
- Because cursor-agent's model selection is stateful (persists across
  invocations/sessions - see Background), a wrapper that injects the wrong
  default would not just affect one call; it could become the *sticky*
  default for subsequent bare invocations too, including ones made outside
  this installer entirely. Getting the slug and effort right matters more
  here than for a typical one-shot flag injection.
- `codex-skip`'s exact flag is unverified as of this PRD - shipping a wrong
  flag name would silently no-op (bad alias, command not found) or, worse,
  pass an unintended flag through to codex.

## Acceptance Criteria

### Functional Acceptance

- [ ] `opencode-auto` aliases `opencode` to `opencode --auto`, with Policies
      detail-panel copy that accurately describes the narrower (not full
      bypass) semantic.
- [ ] `codex-skip` aliases `codex` to its verified real bypass-permissions
      flag.
- [ ] User-supplied flags on any of these aliases are respected (appended,
      never silently dropped).
- [ ] The `cursor-agent` default-model wrapper injects a plain, live-verified
      `--model` slug (no bracket syntax) on any bare invocation, and never
      claims to set 1M context.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before
      implementation.
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.
- [ ] No quality gate is bypassed or silenced.

### User Acceptance

- [ ] Enabling `opencode-auto`/`codex-skip` reduces prompt friction exactly
      as `claude-skip` already does, with no surprise about what each one
      actually does.
- [ ] If shipped, the `cursor-agent` wrapper only injects its default when
      the user did not already specify a model.

## Open Questions

1. ~~Is the cursor-agent bracket-syntax bug fixed?~~ **Resolved: not a bug,
   confirmed unimplemented by a Cursor employee, no ETA.** The remaining
   open item is narrower: **what is the exact, current high-effort "sol"
   model slug and effort flag**, confirmed via `cursor-agent`'s own live
   model-listing command at implementation time (this PRD's research cannot
   run the CLI itself to get this).
2. What is codex's actual, current bypass-permissions flag name? Unverified
   here - needs the same live-check discipline as every registry addition.
3. Is `claude-skip`'s existing `--dangerously-skip-permissions` flag still
   current, or should it move to `--permission-mode bypassPermissions` per
   Cursor's docs describing the former as "older"? This is a fast side-check
   against Claude Code's own current docs, not a blocker for this PRD's
   core scope, but worth resolving in the same pass.
4. Should the third-party `opencode-dangerously-skip-permissions` patch be
   offered at all, even as a separate, clearly-labeled opt-in distinct from
   the official `--auto` tweak? This PRD's default position is no (installing
   a community permission-bypass patch is a different trust decision than
   flipping an official flag), but the user may want it anyway.
