# Phase 9 Research: Postinstall Hooks Mechanism

**Researched:** 2026-09-06
**Method:** Live `codegraph` CLI inspection (v1.2.0, installed on this machine at
`/Users/ramon/.codegraph/versions/v1.2.0/`), direct source reading of its bundled
`lib/dist/installer/` module, and this codebase's existing execution/status/deps
seams.

## Open Question 3 resolved: codegraph's real non-interactive MCP-registration invocation

Live `codegraph --help` / `codegraph install --help` (confirmed this session, v1.2.0):

```
codegraph install [options]

Install codegraph MCP server into one or more agents (Claude Code, Cursor, Codex
CLI, opencode, Hermes Agent)

  -t, --target <ids>      Target agent(s): comma-separated ids, or
                          "auto"|"all"|"none". Default: prompt
  -l, --location <where>  Install location: "global" or "local". Default: prompt
  -y, --yes               Non-interactive: defaults to --location=global
                          --target=auto, auto-allow on
  --no-permissions        Skip writing the auto-allow permissions list (Claude
                          Code only)
  --print-config <id>     Print MCP config snippet for the named agent and exit
                          (no file writes)
```

**Real target ids** (confirmed by reading `installer/targets/registry.js`'s
`ALL_TARGETS` array, source-of-truth for `--target`):
`claude`, `cursor`, `codex`, `opencode`, `hermes`, `gemini`, `antigravity`, `kiro`.

**Critical mapping gap:** codegraph's target id for Cursor is `cursor`, NOT
`cursor-agent`. This project's own catalog tool id for that host is `cursor-agent`
(08-02-PLAN.md). The postinstall composer MUST map our tool id `cursor-agent` →
codegraph's target id `cursor` — a literal id mismatch, not just naming.

## Critical pitfall found: `--target auto` is NOT a safe host-presence check

Read `installer/targets/registry.js::resolveTargetFlag` directly (the actual
implementation `--target auto` dispatches to):

```js
if (value === 'auto') {
    const detected = detectAll(loc).filter(({ detection }) => detection.installed);
    if (detected.length > 0)
        return detected.map(({ target }) => target);
    const fallback = getTarget('claude');   // <-- fallback to claude!
    return fallback ? [fallback] : [];
}
```

**`--target auto` silently falls back to registering for `claude` when it detects
ZERO installed hosts** ("least-surprise for existing users," per the tool's own
comment). This means naively running `codegraph install --target auto --location
global -y` as this phase's postinstall command would **write a Claude MCP config
entry even on a machine where Claude Code is not installed** — a direct violation
of REQ-codegraph-mcp-postinstall's explicit requirement: "never installing those
hosts as a side effect... a documented no-op when none are installed."

**Implication for the plan:** the postinstall step must NEVER pass `--target auto`
(or omit `--target`, since the default is an interactive prompt). It must compute
its own explicit CSV target list — using THIS PROJECT'S OWN `installer.status
.is_installed` check against the `claude`/`codex`/`opencode`/`cursor-agent` catalog
tools (the same live-check convention REQ-postinstall-idempotency-live-check
already mandates), map any present host's id through the `cursor-agent` → `cursor`
translation, and either:
- pass `--target <csv>` when at least one host is present, or
- skip invoking `codegraph install` entirely when none are present (do not pass
  `--target none` either — that's an unnecessary subprocess spawn for a no-op;
  simplest is to skip the call).

This is a real correctness gap this research found, not present in
08-RESEARCH.md's scope (Phase 8 never touched codegraph's own install mechanics)
and not surfaced by CONTEXT.md's D-02 discussion (which named the RIGHT shape —
"build its invocation from exactly which hosts are present" — but did not know
`--target auto` itself was unsafe for that purpose specifically). D-02's directive
is satisfied by NOT using `--target auto` at all, computing presence ourselves.

## `--print-config` is real and useful for a dry-run/tests

`codegraph install --print-config claude` (confirmed live, no file writes):
prints the exact MCP JSON snippet codegraph would write, e.g.:
```json
{
  "mcpServers": {
    "codegraph": { "type": "stdio", "command": "codegraph", "args": ["serve", "--mcp"] }
  }
}
```
Useful for a unit test asserting the shape of what `codegraph install` will write,
without actually writing to a real host config file. `install --help`'s
`--no-permissions` flag is Claude-only and irrelevant to this phase's minimal
invocation (no auto-allow-list opinion needed here).

## Idempotency: `codegraph install` is safe to call more than once

Each target module (`claude.js`, `cursor.js`, `codex.js`, `opencode.js`) writes/
merges its own config file rather than appending blindly — e.g. the legacy shim
`config-writer.js::hasMcpConfig(location)` reads the real config file and checks
`config.mcpServers?.codegraph` presence before considering the entry "there."
Calling `codegraph install --target claude --location global -y` a second time on
a machine that already has the entry does not duplicate it. This means codegraph's
OWN command is naturally idempotent for what it writes — this project's postinstall
step does not need its own separate "is the MCP entry already present" check
before invoking `codegraph install`; it only needs the host-PRESENCE check (which
hosts exist at all) that D-02 already specifies. REQ-postinstall-idempotency-live-
check is satisfied by this project's own `is_installed`-based host-presence check
(never re-registering a host that isn't there) plus trusting `codegraph install`'s
own idempotent merge for "don't duplicate an existing entry" — no new state-
tracking database needed on either side.

## Existing seams this phase reuses, unchanged

- `installer/run.py::Runner`/`run_command` — the same trusted subprocess seam
  every executor already uses; postinstall must dispatch through this, not a new
  seam (per CONTEXT.md's canonical_refs).
- `installer/status.py::is_installed(tool)` — the exact host-presence check to
  reuse for `claude`/`codex`/`opencode`/`cursor-agent`. Already a live check
  (`shutil.which(tool.cmd)` plus `detect_path`/app-bundle fallbacks), zero new
  code needed to determine presence — just call it with each of the four already-
  loaded `Tool` objects from the registry.
- `installer/tweaks.py`'s `ManagedExecutable`/`helper_assets/` precedent — the
  model CONTEXT.md cites for inline-vs-file postinstall script handling. Read:
  `ManagedExecutable` (class at `installer/tweaks.py:23`) shows the established
  pattern for a helper script shipped alongside the installer and invoked via a
  known path — but codegraph's own postinstall command is a SHORT inline
  invocation (`codegraph install --target <csv> --location global --yes`, no
  multi-line script), so `codegraph`'s registry entry should use an inline
  `postinstall` field per REQ-postinstall-field's own stated preference ("inline
  for short, file for multi-line"), not `postinstall_script`.
- `installer/engine.py::install_tool` — the loop that tries each method and
  returns `InstallOutcome` on the first success; this is where the postinstall
  hook must fire, immediately after a method's success and before returning
  `InstallOutcome(tool.id, InstallStatus.INSTALLED, ...)` — matching
  REQ-postinstall-execution-timing's "immediately after the specific Method that
  just ran reports success" and "aware of which Method/kind actually installed
  the tool."

## Registry field shape decision (Claude's discretion, per CONTEXT.md)

Given the above, `codegraph`'s registry entry needs a postinstall action that:
1. Is identical regardless of which of its two `github_release` methods (macOS/
   Linux) succeeded — the postinstall command itself doesn't depend on `kind`.
2. Is a single short shell invocation (no multi-line script) — an inline
   `postinstall` field, not `postinstall_script`.
3. Needs to be TOOL-level, computed dynamically (which hosts are present) rather
   than a static string — this is the one wrinkle: REQ-postinstall-field's
   "inline string" framing suggests a literal command string, but this
   invocation's `--target` value is not knowable at registry-authoring time (it
   depends on the machine's live state). Two shapes to weigh at planning time:
   - (a) `postinstall` stays a literal registry string with a placeholder the
     engine substitutes at dispatch time (e.g. `codegraph install --target
     {detected_hosts} --location global --yes`), OR
   - (b) `postinstall` is a per-tool-id dispatch hook in Python (a small
     dict/registry mapping `tool.id -> Callable[[Runner], None]`, mirroring how
     `EXECUTORS` maps `kind -> Callable`), with `codegraph`'s own hook doing the
     `is_installed`-based host-detection and `Runner` invocation directly.
   Shape (b) avoids inventing a new templating micro-language in TOML for a
   single tool's one-off dynamic composition, and keeps the "which hosts are
   present" logic in testable Python rather than a string-substitution engine
   that only one entry will ever use. This is presented as a finding, not a
   locked decision — the planner should weigh both shapes explicitly against
   REQ-postinstall-field's literal wording ("Optional `postinstall` field...
   either inline... or a `postinstall_script` file reference") before choosing.

## Failure-visibility requirement (REQ-postinstall-execution-timing)

"A postinstall failure is surfaced as a distinct warning, never marks the tool's
own install as failed." Confirmed via `installer/engine.py::install_tool`'s
existing `InstallOutcome` shape (`status`, `method_kind`, `errors`, `verified`) —
there is no existing field for "a secondary, non-fatal warning after a successful
install." The planner needs to decide whether to add a new `InstallOutcome` field
(e.g. `postinstall_warning: str | None`) or handle this at a layer above
`install_tool` (e.g. `installer/app.py`'s caller catches a postinstall exception
and prints it without affecting the returned `INSTALLED` status). Given
`InstallOutcome` is a frozen dataclass with a defined shape already covered by
existing tests across five files (Rule 7's own mirror-coverage requirement),
adding a field here touches the same five-file surface Rule 7 already requires
for a new `kind` — worth flagging to the planner as a real, non-trivial ripple.

## Sources

- `codegraph --help`, `codegraph install --help`, `codegraph uninstall --help`,
  `codegraph --version` — run live this session (v1.2.0).
- `codegraph install --print-config claude` — run live this session, no file
  writes, confirmed real output shape.
- `/Users/ramon/.codegraph/versions/v1.2.0/lib/dist/installer/targets/registry.js`
  — read in full this session (`resolveTargetFlag`, `ALL_TARGETS`, `detectAll`).
- `/Users/ramon/.codegraph/versions/v1.2.0/lib/dist/installer/targets/{claude,cursor,codex,opencode}.js`
  — read for each target's `id` field and (for `cursor`) its own documented
  quirks (hardcoded `--path` injection, no permissions concept).
- `/Users/ramon/.codegraph/versions/v1.2.0/lib/dist/installer/config-writer.js` —
  read in full, confirms the idempotent-merge behavior via `hasMcpConfig`.
- `installer/run.py`, `installer/status.py`, `installer/engine.py`,
  `installer/tweaks.py` (this repo) — read for the seams this phase must reuse.
- `.planning/phases/09-postinstall-hooks-mechanism/09-CONTEXT.md`,
  `.planning/REQUIREMENTS.md` (REQ-postinstall-* + REQ-codegraph-mcp-postinstall,
  including Open Question 3), `.planning/ROADMAP.md` Phase 9 section — read in
  full.
