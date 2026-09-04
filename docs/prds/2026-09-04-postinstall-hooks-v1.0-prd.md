# Postinstall Hooks - Product Requirements Document (PRD)

## Requirements Description

### Background

Some catalog tools need a one-time setup step *after* a successful install
that is not itself an installable artifact - it configures the tool rather
than placing a binary on PATH. The concrete case that prompted this PRD:
`codegraph` (and similar MCP-serving CLIs) needs its "init global" step run
once per AI-agent host (Claude Code, Codex, OpenCode, Cursor) to register
itself as an MCP server. Today the installer has no place for this: `Method`
executors (`installer/executors.py`) install a binary; nothing runs a
follow-up command scoped to "after this specific tool installed
successfully."

### Target Users

- Developers installing MCP-serving tools who currently have to remember and
  run a separate manual step per AI-agent host after the catalog install
  finishes.
- Future registry authors who need a tool-specific one-time setup action
  that is not itself a `Method`.

### Value Proposition

- Let a catalog entry declare its own follow-up action instead of the
  installer or the user having to know about it out-of-band.
- Keep the follow-up action visible, idempotent, and auditable the same way
  every other live mutation in this installer already is (fix, uninstall,
  policy apply all go through `run_live` per the TUI architecture standard).

## Feature Overview

### Core Features

1. An optional `postinstall` field on `Tool` (or `Method` - see Open
   Questions) that names a command to run once, after that install
   succeeds.
2. Idempotency: re-running a postinstall command must be safe - either the
   command itself is naturally idempotent (e.g., `codegraph init --global`
   overwrites its own config) or the installer tracks "already ran" state.
3. Visibility: the TUI must show that a postinstall step ran (or failed) the
   same way it shows an install outcome today - not a silent side effect.
4. `codegraph`'s postinstall registers it as an MCP server for whichever
   AI-agent host CLIs (`claude`, `codex`, `opencode`, `cursor-agent`) are
   already installed on this machine.

### Feature Boundaries

In scope:

- The `postinstall` field, its execution point in the install flow, and its
  error/idempotency handling.
- `codegraph`'s specific postinstall command as the proving case.

Out of scope:

- A general plugin/scripting system for arbitrary user-authored hooks -
  this is a registry-declared, single-command action per tool, following
  the same trust model as everything else in `registry.toml` (author-only,
  never user input).
- Postinstall actions that themselves install new tools (that is what
  `Tool.requires` + the existing resolver already handle).
- Uninstall-time symmetric cleanup (e.g., de-registering the MCP server) -
  worth a follow-up, not blocking this PRD.

## Detailed Requirements

### Data Model Requirements

- `postinstall` is optional; a tool with none behaves exactly as today.
- **Resolved per user (2026-09-04): declared per tool/`Method`, and it can
  be either inline or a script file** - this is a per-package decision
  because different tools need different amounts of postinstall logic:
  - **Inline**: a short one-or-two-line command string directly in the
    `[[tool.method]]` block, for the common case (a single command,
    optionally looping over installed hosts).
  - **Script file**: for anything that would otherwise bloat
    `registry.toml` with many lines, a `postinstall_script` field naming a
    file, following the exact precedent `installer/tweaks.py`'s
    `ManagedExecutable`/`helper_assets/` mechanism already established for
    `wait_time.py` - a bundled script copied from the package, not an
    inline string. This keeps `registry.toml` scannable the same way the
    countdown tweak's rewrite (from an inline bash loop to a managed
    Python script) already improved readability there.
- The command runs through the same trusted-`Runner` seam every other
  executor uses (`installer/executors.py`'s `Runner` abstraction) - no new
  subprocess-invocation path, so it inherits the existing security posture
  (registry-authored only, never templated from user input beyond the
  existing `{ver}`/`{arch.*}` token vocabulary).
- The command must be able to reference the AI-agent host CLIs it targets
  by their catalog tool ids, so "run for every installed host" can be
  expressed declaratively rather than hardcoded per tool.

### Execution Requirements

- **Resolved per user (2026-09-04): runs immediately after install success,
  and is aware of how the install happened.** The postinstall step is
  dispatched right after the `Method` that just ran reports success - not
  batched, not deferred to end-of-session - and it receives (or can query)
  which `Method`/`kind` actually installed the tool, since a postinstall
  action can legitimately need to behave differently depending on install
  path (e.g. where the binary landed). This also answers part of Open
  Question 1 from the prior draft: `postinstall` is declared per tool but
  scoped to run in the context of whichever `Method` just succeeded, not a
  single kind-agnostic action.
- A postinstall failure must not be reported as an install failure for the
  tool itself - the binary is on PATH and usable; the postinstall step is a
  best-effort follow-up. Surface it as a distinct warning, not a hard error
  that makes the whole install look like it failed.
- **Resolved per user (2026-09-04): idempotency via a live check, not a
  state database.** The user asked directly whether this needs a database
  tracking each catalog item's postinstall state instead of a live check,
  and whether a live check (e.g. something `which`-based) would be too
  heavy or could hang. Answer: **no new database** - this project has no
  state-tracking primitive anywhere today (`status.is_installed`,
  `guard_status`, `has_managed_block` are all live checks against the
  filesystem/PATH, never a stored "I did this already" flag), and adding
  one here would be the first of its kind, with a real risk of drifting
  out of sync with reality. A live check is not heavy: `shutil.which`
  (already used throughout this codebase, e.g. `guard_status`,
  `status.is_installed`) is a synchronous PATH/filesystem lookup, not a
  subprocess spawn - it does not hang and does not block the Textual event
  loop the way an actual subprocess call would. The idempotency check for
  a postinstall step should be **"is the effect already present"** (e.g.
  for `codegraph`'s MCP registration: is the MCP entry already in that
  host's config file), the same self-healing shape as every other live
  check in this codebase, not "did I previously run this."
- **Non-interactive only.** A postinstall command must run unattended to
  completion (flags/env vars supplying every answer an interactive prompt
  would ask). A tool whose *only* postinstall/setup path is interactive is
  not a candidate for this mechanism - either it stays a manual step
  documented for the user, or the registry entry ships without a
  `postinstall` at all. This is a hard requirement, not a preference: an
  interactive step would hang the TUI's live-apply flow with no way to
  answer it.

### Per-Tool Postinstall Research (deferred to implementation)

Per the user's own framing (2026-09-04): the exact postinstall/customization
options each tool actually offers - read from that tool's own GitHub
repo/docs, not assumed - is real research work that belongs at
implementation time for each tool that gets a `postinstall`, not something
this PRD resolves up front. This PRD defines the *mechanism* (optional
field, idempotency, non-interactive requirement, visibility); each future
`postinstall` entry needs its own short research pass confirming:

- What the tool's actual non-interactive setup invocation is (flags, env
  vars, config file - whichever the tool's own docs specify).
- Whether it has any interactive-only step that disqualifies it per the
  requirement above.
- Whether the step is safe to run unconditionally or needs the
  already-installed-hosts check (`codegraph`'s case, below).

### codegraph Postinstall Requirements

- After `codegraph` installs, run its global MCP-registration step for each
  of `claude`/`codex`/`opencode`/`cursor-agent` that is *already installed*
  on this machine - never install those hosts as a side effect (that would
  violate the existing `Tool.requires` boundary between "needs to exist" and
  "optionally integrates with").
- If none of those hosts are installed yet, the postinstall step should be a
  documented no-op, not an error.

## Design Decisions

### Technical Approach

- Model this as a natural extension of the existing `run_live` workflow
  (the single live-mutation path this codebase settled on during the TUI
  interaction consistency work) rather than a new, parallel execution
  mechanism.
- Keep the postinstall command declaration in `registry.toml`, next to the
  tool's own `[[tool.method]]` blocks, so a registry author sees both in one
  place.

### Risks

- A postinstall step that is not actually idempotent (unlike the assumption
  above) could cause repeated, unwanted side effects on every install re-run
  or `--all` bulk install.
- Silently swallowing postinstall failures (to avoid marking the install
  itself as failed) risks hiding a real problem from the user - the
  visibility requirement above exists specifically to prevent this becoming
  a silent-failure trap.
- Scoping "which hosts are installed" requires the postinstall step to query
  catalog install state, which is new coupling between a tool's own action
  and the rest of the catalog - needs a clean seam, not an ad hoc lookup.

## Acceptance Criteria

### Functional Acceptance

- [ ] A tool can declare an optional postinstall command in the registry.
- [ ] The command runs exactly once per successful install, never on a
      no-op outcome.
- [ ] A postinstall failure is visible to the user but does not mark the
      tool's own install as failed.
- [ ] `codegraph`'s postinstall registers it as an MCP server for every
      already-installed agent host, and no-ops cleanly when none are
      installed.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before
      implementation.
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.
- [ ] The postinstall command execution path is bandit-reviewed the same way
      every other subprocess-invoking path in `installer/` already is.

### User Acceptance

- [ ] After installing `codegraph`, its MCP server is usable from every
      already-installed agent host without a separate manual step.
- [ ] Re-running the installer does not repeat unwanted postinstall side
      effects.

## Open Questions

1. ~~Tool vs Method placement~~ **resolved above** - per tool, scoped to
   whichever `Method` just succeeded.
2. ~~Idempotency: author responsibility or tracked marker?~~ **resolved
   above: live check, no tracked state.**
3. How does the postinstall step discover which agent hosts are already
   installed - a direct registry/catalog query (reusing `status.is_installed`
   per host tool id), or an injected list the same way other cross-cutting
   installer state (e.g. `which`) is injected at the IO boundary in
   `setup.py` today? Leaning toward reusing `status.is_installed` directly
   (it is already the live-check primitive this PRD's idempotency answer
   just leaned on), but the exact wiring is an implementation detail for
   planning, not resolved here.
