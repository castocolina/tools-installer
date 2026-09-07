---
phase: 10-agent-cli-ergonomics
reviewed: 2026-09-06T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - installer/tweaks.py
  - installer/policy.py
  - installer/wizard_app.py
  - setup.py
  - tests/test_tweaks.py
  - tests/test_policy_tweaks.py
  - tests/test_wizard_app.py
  - tests/test_setup.py
findings:
  critical: 0
  warning: 5
  info: 2
  total: 7
second_lane: codex-sol-high
status: fixed
---

# Phase 10: Code Review Report

**Reviewed:** 2026-09-06
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Diff range `9312bf9..9944afd` (branch `gsd/phase-10-agent-cli-ergonomics`, commits
`eb86c96`/`74c2b37`/`8821242`) was read in full for `installer/tweaks.py`,
`installer/policy.py`, `installer/wizard_app.py`, `setup.py`, and their four paired test
files, then verified against real shell processes (bash 3.2-equivalent via the system
`bash`, and `zsh`) rather than reasoning about the shell text alone — the same discipline
the plan's own three cross-AI review cycles used, since this code is written verbatim into
every enabling user's `~/.myshellrc`.

`make validate`-equivalent checks were re-run directly on the touched files: `ruff check`,
`pyright`, `bandit`, and `vulture --min-confidence 70` all report zero new findings (the ten
pre-existing `pyright` errors in `setup.py` around `confirm`/`on_mismatch` typing predate
this diff and are untouched by it — confirmed by diffing `setup.py` at `9312bf9` for the
same line ranges). The full targeted suite (`tests/test_tweaks.py`,
`tests/test_policy_tweaks.py`, `tests/test_wizard_app.py`, `tests/test_setup.py`) passes,
167 tests.

**Injection-safety check (the review's specific focus):** every one of the three new tweak
bodies (`_CODEX_BODY`, `_OPENCODE_BODY`, `_CURSOR_AGENT_BODY`) is a plain Python string
literal with no interpolation of user-, registry-, or filesystem-derived data — the only
`f"..."`/`f'...'` substitution anywhere is `_CURSOR_DEFAULT_MODEL`, itself a hardcoded
source-level constant (`"gpt-5.6-sol-high"`), never a value read from argv, env, or disk.
This matches the `claude-skip` precedent exactly and the plan's own requirement; no
injection vector was found.

The three cross-AI review cycles recorded in `10-REVIEWS.md` did excellent, source-grounded
work on the split-link-mode wiring, the `unalias`-before-`function` collision fix, and the
enable/disable reload-hint split — all three are correctly implemented and independently
re-verified below to actually behave as claimed, live, in both bash and zsh. This review's
findings are in territory those three cycles did not cover: ambient shell-option
interaction (`set -e`), shell-scope hygiene (an undeclared loop variable), and one
remaining gap in the split-mode fix's own stated scope (the `--guard` entry point under the
*default*, non-split link mode).

## Warnings

### WR-01: `unalias cursor-agent cursor 2>/dev/null` aborts the rest of `~/.myshellrc` (and everything after it) if the sourcing shell has `set -e`/`setopt err_exit` active

**File:** `installer/tweaks.py:108` (`_CURSOR_AGENT_BODY`)
**Issue:** The plan's own design rationale (10-01-PLAN.md `<design_decisions>` item 5)
explicitly claims this line "silently succeeds whether zero, one, or both names have an
existing alias, in both shells, **with or without `set -e`**." That claim is false. Live
verification, both bash and zsh:
```
$ bash -c 'set -e; unalias cursor-agent cursor 2>/dev/null; echo "reached"'
$ echo $?
1
$ zsh -c 'set -e; unalias cursor-agent cursor 2>/dev/null; echo "reached"'
$ echo $?
1
```
`echo "reached"` never prints in either shell — `2>/dev/null` suppresses the error
*message* but not the nonzero *exit status* `unalias` returns when a name it was asked to
remove does not currently exist as an alias (the overwhelmingly common case: most users
enabling this tweak have no pre-existing `cursor-agent`/`cursor` alias at all). Under
`set -e`, that nonzero status terminates the sourcing shell immediately, with no error
message — silently truncating every remaining line of `~/.myshellrc` (the `docker`,
`countdown`, `claude-skip`, `codex-skip`, `opencode-auto` blocks, and anything the user
wrote below this bundle) and, in the centralized/single case, every remaining line of the
`.zshrc`/`.bashrc` that sourced it afterward too. Interactive login shells rarely set `-e`
by convention, but it is not exotic: a user who sets it in their own `~/.bashrc`/`~/.zshrc`
before the `source ~/.myshellrc` line, or any non-interactive script/CI harness that
sources dotfiles under `set -e` to catch its own errors, hits this on the very first new
shell after enabling the tweak, with zero diagnostic output pointing at the cause.
**Fix:** Make the no-op explicit regardless of ambient shell options:
```python
_CURSOR_AGENT_BODY = (
    "unalias cursor-agent cursor 2>/dev/null || true\n"
    "function cursor-agent {\n"
    ...
```
(`2>/dev/null` alone only hides the message; `|| true` is what actually makes the
command's own exit status always zero.)

### WR-02: `cursor-agent()`'s `for a in "$@"; do` leaks a global shell variable named `a` into the user's interactive session on every invocation

**File:** `installer/tweaks.py:110` (`_CURSOR_AGENT_BODY`)
**Issue:** The loop variable `a` is never declared `local`. Because this is a shell
function (not a subshell), the assignment persists in the *calling shell's* global
namespace after the function returns — live-verified in both bash and zsh:
```
$ PATH="$STUB_DIR:$PATH" bash -c '
    source cursor-agent-model-block.sh
    a="my own variable"
    cursor-agent chat hello
    echo "$a"
'
hello
```
`$a` is clobbered to the *last positional argument* of whatever `cursor-agent`/`cursor`
call the user just made, every single time either function runs, for the rest of that
shell session. `a` is a plausible name for a user's own loop counter or ad-hoc variable in
an interactive shell or a sourced snippet run later in the session; this tweak silently
overwrites it with no indication anything happened. None of the existing bundles in this
file (`docker`, `countdown`) declare loop/temp variables, so this is a new hazard this
phase introduces, not a pre-existing pattern being extended.
**Fix:** `local a` (supported identically by bash and zsh inside a `function name { ... }`
body):
```python
"function cursor-agent {\n"
'    local a\n'
'    for a in "$@"; do\n'
```

### WR-03: The split-link-mode fix does not close the equivalent gap for the *default* (centralized) link mode reached via `tools-installer --guard` on a machine that has never run the main install flow

**File:** `setup.py:422-430` (`main`'s `--guard`/`--unguard` branch)
**Issue:** This phase's Task 1 explicitly set out to make "every `tweak:*` Policy (old and
new alike) actually work under split PATH mode... through BOTH `tools-installer --guard`
AND the plain, no-flags interactive install" (10-01-PLAN.md must-haves), and the fix is
correct for the *split* dimension of that claim. But `main`'s `--guard` interactive branch
(`_build_app(..., initial_view="policies", link_mode=link_mode).run()`, `setup.py:427-429`)
is a **standalone entry point** (`make guard` → `uv run setup.py --guard`, documented as
"opt-in, removable" in the Makefile) that a user can run before ever running `make
fix`/`make setup`. For centralized/single link mode (the default — `link_mode =
options.link_mode or "centralized"`, `setup.py:426`), `ensure_sourced_from=()`
(`setup.py:222`, since `link_mode != "split"`), and the *only* code that ever wires
`~/.myshellrc` into `.zshrc`/`.bashrc` for centralized/single is `installer.app.configure_
path`'s non-split branch — which `--guard`'s interactive branch never calls, at all, under
any link mode. If a user's first-ever interaction with this tool is `make guard` /
`tools-installer --guard`, and they enable `codex-skip` (or any tweak — `claude-skip`,
`docker`, `countdown`, `apt-upgrade` are equally affected) from the Policies screen it
opens, the tweak's block lands in `~/.myshellrc`, but nothing has ever sourced that file
from `.zshrc`/`.bashrc` — the exact same "written but unreachable" failure mode the three
review cycles spent significant effort closing for split mode, reappearing for the
*default* mode through a documented, standalone command. `test_the_policies_view_does_
not_wire_split_sourcing_under_centralized_mode` (`tests/test_setup.py`) only asserts that
no *split*-mode file gets written under centralized `--guard`; it does not assert (and
cannot, since nothing does this) that `~/.myshellrc` is reachable from a real shell in this
scenario, so this gap has no test coverage in either direction.
**Fix:** Either (a) have `--guard`'s interactive branch also call `configure_path`'s
non-split wiring step (or the `ensure_source` primitive directly) for centralized/single
modes before opening the Policies screen, mirroring what this phase already does for
split, or (b) if leaving this as a documented precondition ("run `make fix` at least once
before enabling tweaks via `--guard` alone") is the intended contract, state that
explicitly in the Policies detail panel's split-mode sentence (`installer/wizard_app.py`
lines 1009-1014), which currently only mentions split mode and reads as if centralized
mode has no equivalent precondition.

### WR-04: The `cursor-agent`/`cursor` wrapper injects `--model gpt-5.6-sol-high` into *every* invocation with no `--model` token, including non-chat administrative subcommands, with no test coverage for that case

**File:** `installer/tweaks.py:107-123` (`_CURSOR_AGENT_BODY`)
**Issue:** The argv scan only ever looks for an explicit `--model`/`--model=*` token; it
never distinguishes a chat/exec invocation from an administrative one. Live-verified
against the actual wrapper body:
```
$ cursor-agent update
ARGV: --model gpt-5.6-sol-high update
$ cursor-agent --version
ARGV: --model gpt-5.6-sol-high --version
```
Every bare `cursor-agent update`, `cursor-agent login`, `cursor-agent models`, or
`cursor-agent --version` a user runs while this tweak is enabled gets `--model
gpt-5.6-sol-high` injected before its own arguments. Whether the real `cursor-agent`
binary's argument parser tolerates an inapplicable `--model` flag ahead of a subcommand
like `update`/`login`/`--version` was not verified anywhere in 10-RESEARCH.md (which
verified only the `models`/`--list-models` slug-listing behavior and the chat-mode Max
Mode fix) and is not covered by any test in `tests/test_tweaks.py` — every
`test_cursor_agent_*`/`test_cursor_*` test invokes `chat`-style argv only. If the real CLI
rejects an unrecognized-for-that-subcommand flag, this tweak would break exactly the
self-update path (`cursor-agent update`) that REQ-agent-tweak-self-update-durability is
concerned with keeping usable, and would do so silently until the user notices `update`/
`--version` erroring while the tweak is enabled.
**Fix:** Either verify live that `cursor-agent update`/`login`/`--version`/`models` all
tolerate a leading `--model <slug>` before shipping this as unconditional, or scope the
injection to known chat/exec-invoking forms (e.g. skip injection when `$1` is a
recognized non-chat subcommand, or only inject when the first token is absent or is
itself a flag/prompt rather than a bare administrative subcommand name), with a
regression test pinning whichever behavior is chosen.

## Info

### IN-01: `test_cursor_agent_model_body_declares_the_correct_command_guard_invariant` asserts structure via raw substring slicing (`body.index("function cursor ")`) rather than parsing

**File:** `tests/test_tweaks.py:133-149`
**Issue:** The test locates `function cursor-agent` vs. `function cursor ` (note the
trailing space distinguishing it from `function cursor-agent`) via `str.index`/slicing to
split the body into "the `cursor-agent` block" and "the `cursor` block," then scans lines
for `"cursor-agent" in line and "function" not in line`. This is workable today (verified:
it does correctly catch the guard invariant, and a deliberately-broken bare
`cursor-agent "$@"` call was reproduced separately to confirm timeout-based detection
works too) but is fragile against an innocuous future edit — e.g. reordering the two
functions, or adding a third helper function whose name also contains the substring
`"cursor-agent"` — silently changing what the slice boundaries capture with no test
failure pointing at why. Not blocking; noted for awareness since this is the one
structural (non-behavioral) test in the new suite.
**Fix:** Optional — if this body grows further, consider asserting on parsed line
boundaries (e.g. `body.splitlines()` with an explicit state machine) rather than
substring-index slicing, or add a comment noting the ordering dependency.

## Second lane: codex-sol-high

Independent second-lane review, dispatched directly (not via a delegated Agent, after two
prior delegated review agents lost track of the backgrounded codex subprocess) against the
same diff (`9312bf9..9944afd`), model `gpt-5.6-sol` at `model_reasoning_effort="high"`.

> ## Warning
> - **The alias-collision guard aborts rc loading under `set -e`.** `installer/tweaks.py:108`
>   — When neither alias exists, `unalias` returns 1 in both Bash and zsh; with `errexit`,
>   sourcing stops before either function is defined and may skip the remainder of the
>   user's rc file. Make the guard status-neutral, e.g. `unalias ... 2>/dev/null || true`.
> - **The model scan ignores the `--` end-of-options boundary.** `installer/tweaks.py:110` —
>   `cursor-agent -- explain --model` passes `--model` as prompt text, but the wrapper
>   mistakes it for an option and omits the default model, silently falling back to
>   Cursor's prior selection.
>
> ## Info
> - **The argument loop leaks `a` into the interactive shell.** `installer/tweaks.py:110` —
>   After `a=keep; cursor-agent chat hello`, both Bash and zsh leave `a=hello`; a readonly
>   or user-significant variable can also break the wrapper. Declare the loop variable
>   local.
>
> No shell-injection path was found in the three new snippets: their flags/model are
> static, and runtime arguments remain quoted through `"$@"`.
>
> `make validate` passed, and `make test` passed with 1,326 tests and 99.41% coverage.
>
> ## Risk Assessment
> **MEDIUM** — The implementation substantially delivers the reviewed plan, but the cursor
> wrapper has two functional shell edge cases that warrant changes before approval.

Both lanes independently converged on the `set -e` abort bug and the loop-variable leak
(internal WR-01/WR-02); the second lane additionally caught the `--` end-of-options
boundary gap that the internal lane's own WR-04 (unconditional injection into non-chat
subcommands) did not specifically name, though both point at the same argv-scan logic.

**WR-04 empirically re-verified as a non-issue**, not merely theorized: `cursor-agent` is
actually installed on this machine. Live-tested `cursor-agent --model gpt-5.6-sol-high
update` and `cursor-agent --model gpt-5.6-sol-high --version` — both exit 0 with correct
behavior (commander.js-based CLIs generally accept global options anywhere in argv,
confirmed by `cursor-agent --help`'s own usage line `Usage: agent [options] [command]
[prompt...]`). No subcommand allowlist was needed; the real gap was the `--` boundary,
which the fix below closes for both concerns.

## Resolution status

| ID | Finding | Lane(s) | Disposition |
|----|---------|---------|--------------|
| WR-01 | `unalias` aborts sourcing under `set -e` (no exit-status neutralization) | internal + codex-sol-high | **Fixed** — `\|\| true` appended; regression test `test_cursor_agent_unalias_guard_does_not_abort_sourcing_under_set_e` added |
| WR-02 | Loop variable `a` leaks into calling shell (not `local`) | internal + codex-sol-high | **Fixed** — `local a` added; regression test `test_cursor_agent_loop_variable_does_not_leak_into_the_calling_shell` added |
| WR-03 | Split-mode gap re-appears for centralized/default mode via the standalone `--guard` entry point | internal only | **Documented-accepted-limitation** — live-confirmed this is a pre-existing gap affecting ALL bundles (`docker`, `countdown`, `claude-skip`, etc.), not a regression this phase introduces; Phase 10 only added bundles to an already-existing mechanism. Out of this phase's scope to fix a `--guard`-entry-point architectural gap for every pre-existing tweak; noted here for a future phase. |
| WR-04 | Unconditional `--model` injection into non-chat subcommands, untested | internal only | **No change needed** — empirically re-verified live against the real installed `cursor-agent` binary: global `--model` before `update`/`--version` is accepted without error. Not a real defect. |
| (codex) | Argv scan ignores `--` end-of-options boundary | codex-sol-high only | **Fixed** — scan now breaks at a literal `--` token; regression test `test_cursor_agent_stops_scanning_at_double_dash_boundary` added |
| IN-01 | Structural test uses substring-index slicing rather than parsing | internal only | **Accepted-no-change** — noted as non-blocking awareness, no functional risk |

After these fixes: `make validate` clean, `make test` 1329 passed (3 new regression tests),
99.41% coverage — independently re-run, not just trusted from either reviewer's own report.

---

_Reviewed: 2026-09-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
