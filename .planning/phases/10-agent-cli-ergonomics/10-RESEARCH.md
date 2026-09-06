# Phase 10: Agent CLI Ergonomics - Research

**Researched:** 2026-09-06
**Domain:** Shell tweak (alias/function) additions to an existing, purely data-driven `TweakBundle` mechanism; three vendor CLIs' current non-interactive flag/model surfaces
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**cursor-agent default model target**
- **D-01:** The default model to inject is a high-effort "sol" family slug (`chatgpt-5.6-sol`/`gpt-5.6-sol` — exact current id confirmed live per Open Question 1), with `effort=high`. The user's initial ask was also `context=1m`, but REQUIREMENTS.md already records (from prior research) that cursor-agent's 1M context is confirmed reachable only via interactive Max Mode, not from a non-interactive/bare invocation. Per the user: re-verify this via research at implementation time; if 1M context is still confirmed unreachable non-interactively, use whatever the closest non-interactive context setting actually is for the high-effort sol slug — do not silently drop the context consideration, but do not block on unreachable 1M either.
- **How to apply:** planner/researcher must not assume the old finding is stale just because the user asked for 1M — treat it as "re-verify, don't override" per the user's own choice, and record whatever the live-verified outcome is (confirmed unreachable → closest match; found reachable now → note it as a new finding superseding the old one).

### Claude's Discretion
- Exact codex bypass-permissions flag name — Open Question 2, deferred live-verification research, not a locked decision here.
- Exact current cursor-agent model-listing command used to confirm the sol slug and its available context settings — implementation-time research, never typed from memory (per REQUIREMENTS.md's existing caution against this).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within Phase 10 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-codex-skip-tweak | A `codex-skip` tweak, parallel to `claude-skip`, aliasing `codex` to its bypass-permissions flag with user-supplied flags respected (appended, never dropped). | Flag confirmed live: `--dangerously-bypass-approvals-and-sandbox` (see Summary #1, Code Examples). Plain-alias pattern from `claude-skip` (Architecture Patterns Pattern 1) applies unchanged — alias text-substitution already appends user args. |
| REQ-opencode-auto-tweak | An `opencode-auto` tweak aliasing `opencode` to `opencode --auto`, with honest, narrower-semantic Policies detail-panel copy. | Flag confirmed live: `--auto` (see Summary #2). Detail-panel copy mechanism identified precisely: `policy.description` (table row) + a separate hardcoded `details` dict in `wizard_app.py:928-971` (Architectural Responsibility Map, Recommended Project Structure). |
| REQ-cursor-agent-default-model-wrapper | A `cursor-agent`/`cursor` wrapper injecting a plain, live-verified `--model <slug>` on any bare invocation with no `--model` passed; never claims to set 1M context if still confirmed unreachable non-interactively. | Slug confirmed live: `gpt-5.6-sol-high` (Summary #3). 1M-context re-verification per D-01: official changelog documents a fix superseding the old "Max-Mode-only" finding (Summary #4, State of the Art, Pitfall 4, Assumptions Log A2). Conditional-injection function shape drafted in Architecture Patterns Pattern 2. |
| REQ-agent-tweak-self-update-durability | All three tweaks use the existing `TweakBundle`/shell alias-function mechanism, never a file-based shim; `cursor-agent`'s wrapper needs a function, not a plain alias. | Confirmed why a function is required (Alternatives Considered, Pattern 2) and why alias/function lookup survives all three vendors' own self-update subcommands (`codex update`, `opencode upgrade`, `cursor-agent update`, all confirmed present in their own `--help`/`about` output this session). |
</phase_requirements>

## Summary

Phase 10 adds three entries to `installer/tweaks.py`'s `BUNDLES` tuple. The
mechanism itself needs zero new plumbing: `installer/policy.py:tweak_policy`,
the uninstall sweep (`installer/uninstall.py`), and the Policies TUI
(`installer/wizard_app.py`) all iterate over `BUNDLES`/`applicable_bundles`
already, so a fourth and fifth `TweakBundle` (`codex-skip`, `opencode-auto`)
slot in exactly like `claude-skip`, `apt-upgrade` did. The one genuinely new
shape is the `cursor-agent`/`cursor` wrapper: every existing bundle body is a
static alias or a parameter-free function, but this wrapper must inspect
`"$@"` at call time and conditionally omit its own injected `--model` flag —
the first bundle in this codebase to need that.

All three of this phase's Open Questions were resolved by **live invocation
of the actual installed CLIs on this machine** (not training-data memory),
cross-checked against official docs where the local binary's output needed
corroboration:

1. **codex bypass flag:** `--dangerously-bypass-approvals-and-sandbox` (confirmed via `codex --help` and `codex exec --help`, both print it verbatim with identical wording). This is a plain, unconditional alias target exactly like `claude-skip` — no function needed.
2. **opencode auto flag:** `--auto` (confirmed via `opencode --help`: `"auto-approve permissions that are not explicitly denied (dangerous!)"`). Matches REQUIREMENTS.md's locked wording exactly (`opencode --auto`) — plain alias, no function needed.
3. **cursor-agent sol slug:** `gpt-5.6-sol-high` (confirmed via `cursor-agent models`, run live on this machine, 2026-09-06). Effort is baked into the slug itself (`-low`/`-medium`/`-high`/`-xhigh`/`-max`/`-none` suffixes) — there is no separate `--effort` flag, so "plain slug, no bracket syntax" fully expresses model+effort in one token.
4. **1M context reachability (D-01 re-verification):** the 2026-07-13 entry in Cursor's own official CLI changelog documents a fix superseding the finding already recorded in REQUIREMENTS.md: *"Headless keeps Max-mode variants. A headless `--model` selection that requires Max Mode now sends it, so max-context variants are no longer clamped down."* As of the installed build (`cursor-agent` 2026.09.02-c22c1a3, newer than the July fix), passing `--model gpt-5.6-sol-high` in a non-interactive (`--print`) invocation should now reach that model's full context window without any separate interactive `/max-mode` toggle. **This supersedes, not merely adds to,** the "Max-Mode-only, unreachable non-interactively" finding already in REQUIREMENTS.md — see the Assumptions Log and Open Questions for the residual verification gap (the changelog claim was not independently re-proven by spending a real API call).

**Primary recommendation:** Add `codex-skip` and `opencode-auto` as plain
`TweakBundle`s with no `requires` and no `executables` (mirroring
`claude-skip` exactly); add the `cursor-agent`/`cursor` wrapper as a third
bundle whose `body` is two shell functions (`cursor-agent` shadowing the real
binary via `command cursor-agent "$@"`, plus a thin `cursor` function
delegating to it) that grep `"$@"` for a literal `--model` token before
injecting `--model gpt-5.6-sol-high`.

## Architectural Responsibility Map

This project is a terminal installer/TUI, not a client-server web app, so the
generic Browser/API/DB tiers do not apply verbatim. The codebase's own
equivalent tiers are used instead — verified by reading the actual call
chain (`installer/tweaks.py` -> `installer/policy.py` -> `installer/wizard_app.py`
/ `installer/uninstall.py`).

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Shell alias/function bodies (the three new tweaks) | Shell runtime (`~/.myshellrc`, sourced by the user's real bash/zsh) | — | The actual behavior change happens entirely in the user's interactive shell; nothing in this project executes the injected flags itself |
| Bundle registration/idempotent write-strip | `installer/tweaks.py` (`TweakBundle`, `BUNDLES`, `write_tweak`/`remove_tweak`) | — | Pure data + the existing marker-block machinery; no new functions needed here beyond appending to the tuple |
| Toggle state, requires-gating, uninstall sweep | `installer/policy.py` (`tweak_policy`) / `installer/uninstall.py` (`active_policies`, `sweep_policies`) | — | Fully generic over `BUNDLES` already — zero code changes required for these three entries to be toggleable and uninstallable |
| Policies list row + detail-panel copy | `installer/wizard_app.py` (`PoliciesScreen._policy_detail`, `on_mount`'s `table.add_row`) | — | `policy.description` (= `bundle.description`) renders in the table row (`wizard_app.py:904`) *and* feeds the detail panel's first line (`wizard_app.py:972`); a **second**, separate hardcoded `details` dict keyed by Policy id (`wizard_app.py:928-971`) supplies the multi-line detail-panel body and falls back to a generic one-liner (`wizard_app.py:980`) when a policy id has no dict entry |

## Standard Stack

No new external packages. This phase extends an existing, already-adopted
in-repo mechanism (`installer/tweaks.py`'s `TweakBundle`) with pure-Python
dataclass instances and raw shell strings — the same shape `claude-skip`,
`docker`, `countdown`, and `apt-upgrade` already use. No `pip`/`npm`/`uv`
install step is part of this phase's scope.

### Core
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|---------------|
| `installer.tweaks.TweakBundle` (existing) | n/a (in-repo) | Declarative shell-snippet bundle | Already the sole mechanism for every prior curated alias/function in this codebase; REQ-agent-tweak-self-update-durability requires reusing it, not inventing a file-based shim |

### Supporting
None — no new runtime dependency.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Shell alias/function in `~/.myshellrc` | A wrapper script installed onto PATH (like `ManagedExecutable`, used today only by `countdown`'s `wait_time` helper) | Rejected by REQ-agent-tweak-self-update-durability itself: a file living in the tool's own install directory (or even a separate PATH entry ahead of it) can be clobbered or made stale by the vendor CLI's own self-update (`codex update`, `opencode upgrade`, `cursor-agent update` — all three vendors ship a self-update subcommand, confirmed live in their own `--help`); a shell alias/function lives in `~/.myshellrc`, a file none of the three CLIs' installers ever touch, and function/alias lookup precedes PATH search in bash/zsh regardless of where on PATH the binary later moves |
| Plain alias for the cursor-agent wrapper | Shell function | REQ-agent-tweak-self-update-durability explicitly calls out that this one wrapper needs a *function*: aliases can only prepend/append fixed text, they cannot inspect `"$@"` to skip injecting `--model` when the user already passed one — this is a genuine, not incidental, difference from `codex-skip`/`opencode-auto`, which both need only a fixed prefix and are correctly plain aliases |

## Package Legitimacy Audit

**Not applicable** — this phase installs no external packages (no `pip`,
`npm`, `pnpm`, `uv tool`, `brew`, or `github_release` additions). All three
tweaks configure shell aliases/functions around CLIs the catalog already
installs via existing, already-audited Phase 8 registry entries (`codex`,
`opencode`, `cursor-agent`). The Package Legitimacy Gate protocol is skipped
per its own trigger condition ("whenever this phase installs external
packages").

## Architecture Patterns

### System Architecture Diagram

```
User enables a Policy in the TUI (or --guard on the CLI path)
        |
        v
installer/policy.py: tweak_policy(bundle, rc_path=~/.myshellrc, bin_dir=...)
        |  apply() -> write_tweak(bundle, rc_path)
        v
installer/tweaks.py: write_tweak()
        |  apply_block(existing_text, tweak_block(bundle), begin/end markers)
        v
~/.myshellrc  (marker-delimited block written idempotently)
        |
        | (user opens a new shell, or `source ~/.myshellrc`)
        v
bash/zsh interactive shell: function/alias table populated
        |
        | user types `codex ...` / `opencode ...` / `cursor-agent ...` / `cursor ...`
        v
Shell's own command-lookup order: alias/function table checked BEFORE PATH search
        |
        +-- codex-skip:      alias codex='codex --dangerously-bypass-approvals-and-sandbox'
        +-- opencode-auto:   alias opencode='opencode --auto'
        +-- cursor-agent fn: inspects "$@" for a literal --model token,
        |                    then execs `command cursor-agent [--model gpt-5.6-sol-high] "$@"`
        +-- cursor fn:       delegates to the cursor-agent function above
        v
Real vendor binary on PATH runs with the (possibly augmented) argv
```

### Recommended Project Structure

No new files or directories. All changes land in the single existing file:

```
installer/
├── tweaks.py   # BUNDLES tuple gains 2-3 more TweakBundle entries
tests/
├── test_tweaks.py         # bundle-shape assertions, mirroring claude-skip's own tests
└── test_policy_tweaks.py  # apply/remove-through-Policy assertions, mirroring claude-skip's own tests
```

`installer/wizard_app.py`'s `_policy_detail` dict (line 928) additionally
needs entries for the new Policy ids if the generic one-line fallback
(`wizard_app.py:980`) is judged insufficient for REQ-opencode-auto-tweak's
"Policies detail-panel copy must be honest about this narrower semantic"
requirement — the fallback text is a single generic sentence
(`"Space toggles this reversible shell policy."`) and does not itself
distinguish `opencode --auto`'s partial-deny-rules-still-apply semantic from
`claude-skip`'s full bypass. `tweak:claude-skip`'s own three-line dict entry
(quoted verbatim below) is the direct template.

### Pattern 1: Plain alias tweak (mirrors `claude-skip` exactly)

**What:** A `TweakBundle` whose `body` is a single `alias name='name --flag'`
line, no `requires`, no `executables`.
**When to use:** `codex-skip`, `opencode-auto` — both need only a fixed flag
appended; the shell's own alias-expansion mechanics already append any
further user-supplied arguments (an alias just textually prefixes the
command line, so `codex foo --bar` expands to
`codex --dangerously-bypass-approvals-and-sandbox foo --bar` with nothing
dropped).
**Example (verbatim from the codebase, `installer/tweaks.py:70,110-115`):**
```python
# Source: installer/tweaks.py:70 (_CLAUDE_BODY) and :109-115 (its TweakBundle)
_CLAUDE_BODY = "alias claude='claude --dangerously-skip-permissions'"
...
TweakBundle(
    "claude-skip",
    "claude skip-permissions",
    "alias claude='claude --dangerously-skip-permissions'",
    (),
    _CLAUDE_BODY,
),
```

### Pattern 2: Conditional-injection function (new to this codebase)

**What:** A shell function shadowing the real binary name, checking `"$@"`
for a flag the user may already have supplied, and calling through to
`command <realname> "$@"` either with or without the injected default.
**When to use:** The `cursor-agent`/`cursor` wrapper only — it is the only
one of the three tweaks whose injected value must be *conditionally
omitted*.
**Why a function and not an alias (confirmed, not assumed):** an alias is a
static text substitution with no branching; POSIX/bash/zsh alias expansion
cannot inspect the argument list before deciding what to prepend. A function
receives `"$@"` as real positional parameters and can loop over them.
**Existing, independently-observed working idiom for exactly this shape**
(found live on this development machine's own `~/.zshrc`-defined `opencode`
wrapper — unrelated to this project's codebase, but proof the idiom is sound
in this exact shell):
```sh
# Observed live via `which opencode` on this machine, 2026-09-06 (not part
# of this project's source; cited here only as a working-idiom precedent):
for a in "$@"
do
    case "$a" in
        (--agent|--agent=*|--auto) skip_auto=1 ;;
    esac
done
```
**Recommended shape for this phase's bundle body** (grounded in the flag
name confirmed live via `cursor-agent --help`, which shows only the long
form `--model <model>` with no short alias):
```sh
cursor-agent() {
    local has_model=0 a
    for a in "$@"; do
        case "$a" in
            (--model|--model=*) has_model=1 ;;
        esac
    done
    if [ "$has_model" -eq 1 ]; then
        command cursor-agent "$@"
    else
        command cursor-agent --model gpt-5.6-sol-high "$@"
    fi
}
cursor() {
    cursor-agent "$@"
}
```
This is a draft for the planner, not a locked body — the exact bundle id,
whether `cursor` should independently re-check `"$@"` or simply delegate
(shown above), and where the model slug constant lives are still open
implementation choices (see Open Questions).

### Anti-Patterns to Avoid
- **Calling the shadowed name recursively inside its own function body:** the function body must invoke `command cursor-agent "$@"` (or the fully-qualified path), never bare `cursor-agent "$@"` — the latter would recurse into the function itself and hang/stack-overflow. `command` bypasses function/alias lookup for that one call, which is exactly why it is the standard idiom (also used correctly by the local machine's real, independently-observed `opencode` function, which calls `command opencode "$@"`).
- **Using `--model=<slug>` string concatenation blindly:** `cursor-agent --help` documents only the space-separated form `--model <model>`; do not assume `=` form is required or forbidden — checking for both `--model` and `--model=*` (as drafted above) is the safe, cheap superset that costs nothing if only one form is actually accepted.
- **Assuming `pip`-shim-style file replacement:** this phase's tweaks are the third category the codebase already models — pure alias (`claude-skip`), function-with-a-managed-executable (`countdown`), and now function-with-branching-but-no-executable (`cursor-agent`) — do not introduce a `ManagedExecutable` for the cursor-agent wrapper; there is nothing to install onto PATH, only shell functions to write into `~/.myshellrc`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent, marker-delimited rc-file block writing | A new file-append/dedupe routine | `installer.tweaks.write_tweak`/`remove_tweak` (already used by all four existing bundles) via `installer.shellrc.apply_block`/`strip_block` | Already handles re-enable-does-not-duplicate and leaves-other-blocks-and-user-content-intact, both already tested (`tests/test_tweaks.py:218-248`) |
| Toggle state / Policies row / uninstall sweep for a new bundle | Anything bespoke | Just append to `BUNDLES` in `installer/tweaks.py` | `installer/policy.py:tweak_policy`, `installer/uninstall.py:active_policies`/`sweep_policies`, and `installer/wizard_app.py`'s Policies table all already iterate `BUNDLES`/`applicable_bundles` — confirmed via direct read, zero call sites need editing for the bundle-registration half of this phase |

**Key insight:** two of this phase's three tweaks require *no new code
beyond a tuple entry* — the mechanism was already built generically enough
in prior phases. The only real engineering surface is (a) getting the three
external flag/slug names right via live verification, and (b) the one new
conditional-function shape for `cursor-agent`.

## Common Pitfalls

### Pitfall 1: Trusting the `--model[bracket=syntax]` help text
**What goes wrong:** `cursor-agent --help` itself prints the bracket-syntax
example (`'claude-opus-4-8[context=1m,effort=high,fast=false]'`) as if it
were supported.
**Why it happens:** Per an official Cursor employee's forum statement, the
help text is acknowledged as accidental/misleading — the bracket-parameter
feature for `--model` is not implemented, and passing it fails and instead
shows a model list. REQUIREMENTS.md already records this as "confirmed
unimplemented by a Cursor employee, not just buggy" — this research
independently re-confirmed the same forum thread and quote.
**How to avoid:** Always pass a complete, pre-baked model slug (e.g.
`gpt-5.6-sol-high`) obtained from `cursor-agent models`/`--list-models`,
never a bracketed parameterization.
**Warning signs:** If `cursor-agent --model 'x[effort=high]'` ever
"succeeds" by silently falling back to a model list or the default `auto`
model, that is exactly this bug, not evidence the syntax works.

### Pitfall 2: Model entitlement vs. model existence
**What goes wrong:** `cursor-agent models` lists `gpt-5.6-sol-high` as an
available slug even though this research session's `cursor-agent about`
reported `Subscription Tier: Free`. A slug appearing in the catalog does not
by itself prove the invoking account is entitled to use it.
**Why it happens:** The model catalog is not filtered by the account's plan
in this build's output.
**How to avoid:** Document, in the tweak's user-facing copy, that the
injected default model requires a Cursor plan that includes it; do not claim
the wrapper "guarantees" the model runs, only that it requests it.
**Warning signs:** A `cursor-agent`/`cursor` invocation that errors or
silently downgrades immediately after this tweak is enabled.

### Pitfall 3: Recursive self-shadowing in the wrapper function
**What goes wrong:** Forgetting `command` before the real binary name inside
the `cursor-agent` (or `codex`/`opencode`, if ever converted to functions)
wrapper causes the function to call itself.
**Why it happens:** Once a shell function shares the exact name of the real
executable, an unqualified call to that name inside the function resolves to
the function again, not the PATH binary — an infinite loop.
**How to avoid:** Always call `command cursor-agent "$@"` inside the
`cursor-agent` function body (confirmed as the correct idiom by the
independently-observed, already-working `opencode` function on this
machine, which does exactly this for the same reason).
**Warning signs:** The wrapped command hangs indefinitely or the shell
reports a stack/recursion depth error on first use.

### Pitfall 4: Assuming the July 2026 headless-Max-Mode fix needs no residual caution
**What goes wrong:** Treating "official changelog says headless `--model`
now sends Max Mode" as equivalent to "independently proven to reach 1M
tokens of context in this exact invocation shape."
**Why it happens:** The changelog entry is real and official, but this
research did not spend a real API call actually running
`cursor-agent -p --model gpt-5.6-sol-high` and inspecting a
context-window-size signal in the response; `cursor.com/docs/cli/headless`
itself (fetched live this session) does not mention model/context selection
at all.
**How to avoid:** State the finding as "per official changelog, expected to
reach the model's full context non-interactively as of this build" rather
than "verified reaching 1M tokens." Flag as a candidate for a
`checkpoint:human-verify` task if the plan wants stronger proof before
shipping.
**Warning signs:** None observable from static research — only a live run
with a context-window assertion would falsify or confirm this.

## Code Examples

### Existing exact pattern to mirror for `codex-skip` (verbatim source)
```python
# Source: installer/tweaks.py:70 and :109-115
_CLAUDE_BODY = "alias claude='claude --dangerously-skip-permissions'"

TweakBundle(
    "claude-skip",
    "claude skip-permissions",
    "alias claude='claude --dangerously-skip-permissions'",
    (),
    _CLAUDE_BODY,
),
```
`codex-skip` mirrors this with `_CODEX_BODY = "alias codex='codex --dangerously-bypass-approvals-and-sandbox'"`.

### Live-confirmed flag discovery commands (run this session, 2026-09-06)
```bash
# codex — top-level and `exec` subcommand both print the same flag verbatim:
codex --help       # -> "--dangerously-bypass-approvals-and-sandbox  Skip all confirmation
                    #     prompts and execute commands without sandboxing. EXTREMELY
                    #     DANGEROUS. Intended solely for running in environments that
                    #     are externally sandboxed"
codex exec --help  # -> identical flag, identical wording

# opencode:
opencode --help    # -> "--auto  auto-approve permissions that are not explicitly
                    #     denied (dangerous!)  [boolean] [default: false]"

# cursor-agent model catalog (used to pick the exact sol slug):
cursor-agent models          # or: cursor-agent --list-models
# -> ... gpt-5.6-sol-high - GPT-5.6 Sol 1M High
#        gpt-5.6-sol-high-fast - GPT-5.6 Sol 1M High Fast
#        gpt-5.6-sol-xhigh - GPT-5.6 Sol 1M Extra High  ...
```

### Existing test pattern to mirror (verbatim, `tests/test_tweaks.py`)
```python
# Source: tests/test_tweaks.py:29-30 and :232-235
def test_four_bundles_with_stable_ids() -> None:
    assert [b.id for b in BUNDLES] == ["docker", "countdown", "claude-skip", "apt-upgrade"]
    # -> becomes a longer, still-order-sensitive list once codex-skip/opencode-auto/
    #    the cursor-agent wrapper are appended

def test_re_enable_does_not_duplicate(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("claude-skip")
    write_tweak(bundle, rc)
    write_tweak(bundle, rc)
    assert rc.read_text().count("# >>> tools-installer tweak:claude-skip >>>") == 1
```

### Existing test pattern to mirror (verbatim, `tests/test_policy_tweaks.py`)
```python
# Source: tests/test_policy_tweaks.py:84-90
def test_remove_strips_block(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_bundle("claude-skip"), rc_path=rc)
    policy.apply()
    result = policy.remove()
    assert "claude --dangerously-skip-permissions" not in rc.read_text()
    assert "cleared" in result.layers[0].detail
```

## State of the Art

| Old Approach (REQUIREMENTS.md, prior finding) | Current Approach (this session's live re-verification) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| cursor-agent's 1M context "confirmed reachable only via interactive Max Mode, unreachable non-interactively" | Official Cursor CLI changelog (fetched live, 2026-09-06): a 2026-07-13 fix makes headless `--model` selections that require Max Mode activate it automatically, "so max-context variants are no longer clamped down" | 2026-07-13 (per official changelog), predates the installed build (2026.09.02) | D-01's default model injection (`gpt-5.6-sol-high`) can be recommended as reaching its full context non-interactively — the prior "unreachable" caveat should no longer gate the plan, though see Pitfall 4/Assumptions Log for the residual unverified-by-live-API-call gap |
| Bracket-parameter `--model` syntax appearing supported per `cursor-agent --help`'s own example text | Confirmed by an official Cursor employee (forum.cursor.com) as accidental/misleading help text; the feature itself is unimplemented, not merely buggy | Ongoing as of this session (no ETA given) | Confirms REQUIREMENTS.md's existing framing was correct and still current; no plain-slug workaround needed beyond what REQUIREMENTS.md already specifies |

**Deprecated/outdated:**
- Bracket-parameter model overrides (`model[context=1m,effort=high]`) for `cursor-agent --model`: never actually worked; do not implement or test against this syntax.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `gpt-5.6-sol-high` will remain entitled/usable under the target user's actual Cursor subscription plan (this research's own session reported `Subscription Tier: Free`, and model catalogs do not appear filtered by plan) | Common Pitfalls #2, Summary | The wrapper could inject a model the invoking account cannot actually use, producing a runtime error or silent downgrade on every bare `cursor-agent`/`cursor` call until the tweak is disabled or the slug is changed |
| A2 | The 2026-07-13 changelog fix ("headless keeps Max-mode variants") actually delivers a full 1M-token context window for `gpt-5.6-sol-high` specifically, not merely "does not clamp down the request" in some narrower sense | Summary, Pitfall 4, State of the Art | If the fix does not fully restore 1M context for this exact slug in `--print` mode, the wrapper's documented benefit ("known-good default model" with maximal context) would overstate what actually happens at runtime — no functional bug, since `--model` is still honored, but the copy/description written into the `TweakBundle`/Policy detail panel should avoid asserting 1M context is *guaranteed* reached, only that it is requested and no longer known-blocked |
| A3 | The exact `TweakBundle` id, bundle body layout (single body string containing both `cursor-agent()` and `cursor()` function definitions vs. two separate bundles), and where the model-slug string constant should live are left as planner discretion, since CONTEXT.md's "Claude's Discretion" section defers exact command details to implementation time | Architecture Patterns Pattern 2 | A poor split (e.g. two independently toggleable bundles for `cursor-agent` and `cursor`) could let a user enable one without the other, producing inconsistent behavior between the two invocation names for what REQUIREMENTS.md treats as one requirement (REQ-cursor-agent-default-model-wrapper) |

## Open Questions

1. **Should `cursor` re-run its own `--model` presence check, or purely delegate to the `cursor-agent` function?**
   - What we know: the draft in Pattern 2 has `cursor()` call `cursor-agent "$@"` unconditionally, which is correct and DRY as long as the `cursor-agent` function is always defined in the same bundle body (so it exists whenever `cursor` does).
   - What's unclear: whether the planner wants them as one bundle (guaranteed co-installed) or two (independently toggleable, per REQUIREMENTS.md's literal "`cursor-agent`/`cursor` wrapper" phrasing, which could be read either way).
   - Recommendation: one bundle, one body defining both functions — avoids the inconsistent-half-installed failure mode noted in Assumption A3.

2. **Does the live-verified 1M-context headless fix warrant a `checkpoint:human-verify` task before this phase is considered done?**
   - What we know: official changelog documents the fix; no live API call was spent this session to observe an actual context-window-size signal in a real response.
   - What's unclear: whether this project's Nyquist-validation/test strategy for this phase can cheaply assert context reachability at all (it would require a real, possibly costly, live model call against the user's own Cursor account).
   - Recommendation: the plan should NOT attempt to automate-test 1M-context reachability (cost/flakiness); instead state the injected model/flag pairing as the testable unit (a plain string match on the rendered shell body), and treat the context-window claim as documentation, not a test assertion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `codex` CLI | Live-verifying `--dangerously-bypass-approvals-and-sandbox` (already done, this session) | Yes | codex-cli 0.149.1 | N/A — flag confirmed via `--help`, tweak body needs no runtime presence check (mirrors `claude-skip`, which declares no `requires`) |
| `opencode` CLI | Live-verifying `--auto` (already done, this session) | Yes | 1.18.18 | N/A — flag confirmed via `--help` |
| `cursor-agent` CLI | Live-verifying the sol slug + changelog cross-check (already done, this session) | Yes | 2026.09.02-c22c1a3 | N/A — model catalog confirmed via `cursor-agent models` |

**Missing dependencies with no fallback:** None — all three research targets were present on this machine and answered every question needed for this phase.

**Missing dependencies with fallback:** None.

*Note: these three CLIs are optional catalog tools (installed via Phase 8's `codex`/`opencode`/`cursor-agent` registry entries) from the target end-user's perspective — the tweak bundles themselves must not `requires`-gate on the CLI being installed, exactly mirroring `claude-skip`'s own precedent of declaring `requires=()` even though `claude` is itself an optional catalog tool.*

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`[tool.pytest.ini_options]` in `pyproject.toml`, `addopts = "-q"`, `testpaths = ["tests"]`, `asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py -q` |
| Full suite command | `make test` (== `uv run pytest --cov`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-codex-skip-tweak | `codex-skip` bundle renders `alias codex='codex --dangerously-bypass-approvals-and-sandbox'` and round-trips write/present/remove | unit | `uv run pytest tests/test_tweaks.py -k codex_skip -x` | ✅ file exists, ❌ new test cases (mirror `test_block_is_marker_delimited_around_body`/`test_re_enable_does_not_duplicate`) |
| REQ-opencode-auto-tweak | `opencode-auto` bundle renders `alias opencode='opencode --auto'`; Policies detail-panel copy for `tweak:opencode-auto` names the narrower semantic | unit + a Textual detail-panel assertion | `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py tests/test_wizard_app.py -k opencode_auto -x` | ✅ files exist, ❌ new test cases (mirror `test_policy_detail_panel_explains_tweak_rules`, `tests/test_wizard_app.py:832`) |
| REQ-cursor-agent-default-model-wrapper | Bare `cursor-agent`/`cursor` invocation with no `--model` gets `--model gpt-5.6-sol-high` injected; an explicit `--model X` is passed through unmodified | unit (shell-script execution, same idiom `_wait_seconds`/`_wait_countdown` already use in `tests/test_tweaks.py:75-104` to run a real bash subprocess against a rendered tweak block) | `uv run pytest tests/test_tweaks.py -k cursor_agent -x` | ❌ new helper + new test cases needed (Wave 0 gap below) |
| REQ-agent-tweak-self-update-durability | All three bundles use `TweakBundle`/`tweak_policy` (never a `ManagedExecutable`/PATH-shim for the injection itself) | unit (bundle-shape assertion, no runtime shell execution needed) | `uv run pytest tests/test_tweaks.py -k "codex_skip or opencode_auto or cursor_agent" -x` | ❌ new test cases, same file |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py -q`
- **Per wave merge:** `make test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_tweaks.py` — needs a new subprocess-execution helper (mirroring `_wait_seconds`/`_wait_countdown`, `tests/test_tweaks.py:75-104`) that sources the rendered `cursor-agent` tweak block into a bash script, stubs the real `cursor-agent`/`command cursor-agent` call (e.g. by shadowing `command` or defining a fake `cursor-agent` binary earlier on a test-controlled `PATH`) so the test can assert on the argv the function would have run, without actually invoking the real Cursor API.
- [ ] No new fixtures needed beyond the helper above — `tests/test_tweaks.py`'s existing `_bundle()` helper and `bash -n` syntax-validation loop (`test_every_block_parses_in_bash`, `test_blocks_parse_in_bash_and_zsh_when_present`) already cover the new bundles for free once they are appended to `BUNDLES`.
- [ ] Framework install: none — pytest is already the project's framework and is already installed via `make install`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This phase touches no auth flow |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes (narrow) | The `cursor-agent` function's `"$@"` flag-scan must not mis-parse an argument that merely *contains* the substring `--model` inside a quoted prompt string as if it were the flag itself — the draft in Pattern 2 uses an exact `case` match (`--model|--model=*`) against each *whole* positional parameter, not a substring `grep` over the joined argv, precisely to avoid this false-positive class |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Alias/function shadowing widens an already-dangerous default (both `codex-skip` and `opencode-auto` are explicit, opt-in, user-toggleable bypasses of the vendor CLI's own safety prompts) | Elevation of Privilege | Already the accepted, existing pattern for `claude-skip` (opt-in Policy toggle, disableable, documented as "useful only in trusted, disposable workspaces" in `wizard_app.py:951-955`); the new tweaks must carry equivalently honest detail-panel copy, especially `opencode-auto` per REQ-opencode-auto-tweak's explicit non-full-bypass requirement, so a user cannot mistake the narrower `--auto` (which still respects explicit deny rules per `opencode --help`'s own wording) for `claude-skip`'s full `--dangerously-skip-permissions` |
| Recursive self-shadowing hang (see Common Pitfalls #3) | Denial of Service (of the user's own shell) | Always call through `command <realname> "$@"` inside the function body |

## Sources

### Primary (HIGH confidence — live tool invocation, this session, 2026-09-06)
- `codex --help`, `codex exec --help` (codex-cli 0.149.1) — `--dangerously-bypass-approvals-and-sandbox` flag text
- `opencode --help` (1.18.18) — `--auto` flag text
- `cursor-agent --help`, `cursor-agent models`, `cursor-agent --list-models`, `cursor-agent about` (2026.09.02-c22c1a3) — model catalog, subscription tier, bracket-syntax example text
- Direct reads of `installer/tweaks.py`, `installer/policy.py`, `installer/uninstall.py`, `installer/wizard_app.py` (line-ranges cited inline above), `tests/test_tweaks.py`, `tests/test_policy_tweaks.py`, `installer/registry.toml` (lines 1312-1420 for the existing `codex`/`claude`/`opencode`/`cursor-agent` registry entries)

### Secondary (MEDIUM confidence — official documentation, fetched live this session)
- [Cursor CLI Changelog](https://cursor.com/docs/cli/changelog) — 2026-07-13 headless Max-Mode-variant fix
- [forum.cursor.com bracket-syntax thread](https://forum.cursor.com/t/cursor-cli-agent-doesnt-support-square-bracket-model-name-variants/163905) — official Cursor employee (Dean Rie) statement that bracket parameters are unimplemented, not buggy

### Tertiary (LOW confidence — informational only, not relied on for any claim above)
- `cursor.com/docs/cli/using`, `cursor.com/docs/cli/headless` — fetched live but contained no model/context-specific detail relevant to this phase's questions; cited only to document that the absence was checked, not to support any claim

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, pure extension of an already-read, fully understood existing mechanism
- Architecture: HIGH — every claim about `BUNDLES`/`tweak_policy`/Policies-screen wiring is from a direct `Read` of the actual source this session, with line numbers
- Flag/slug findings (codex, opencode): HIGH — confirmed by directly invoking the installed CLI's own `--help` this session
- Flag/slug findings (cursor-agent sol slug): HIGH — confirmed by directly invoking `cursor-agent models` this session
- 1M-context headless reachability: MEDIUM — official changelog is authoritative but the specific slug's behavior was not independently re-proven with a live API call (see Assumptions Log A2, Open Question 2)
- Pitfalls: HIGH — grounded in the same live `--help` outputs plus one independently-observed, already-working real-world shell idiom

**Research date:** 2026-09-06
**Valid until:** 14 days (all three target CLIs are fast-moving, self-updating tools; the model catalog and changelog-documented behavior are both subject to change on any future `codex`/`opencode`/`cursor-agent` self-update)
