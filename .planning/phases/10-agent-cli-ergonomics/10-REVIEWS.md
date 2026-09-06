---
phase: 10
reviewers: [codex]
reviewed_at: 2026-09-06T19:51:12Z
plans_reviewed: [10-01-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
model_sources:
  codex: "banner"
---

# Cross-AI Plan Review — Phase 10

## Codex Review

## Summary

Plan 10-01 chooses the right architecture and covers the phase requirements well, but it is not execution-ready. Three blockers need correction: Tasks 1 and 2 cannot pass their stated quality gates, split link mode leaves the tweaks in an unsourced file, and Task 3 contains mutually incompatible wrapper/test instructions. The current targeted suite passes, so these are plan defects rather than existing test failures.

## Strengths

- The zero-new-plumbing claim is correct for normal sourced-`~/.myshellrc` configurations. `tweak_policy` already namespaces metadata and routes apply/remove through the marker-block functions ([installer/policy.py:156](/Users/ramon/git/personal/tools-installer/installer/policy.py:156)); setup constructs policies from every applicable bundle ([setup.py:180](/Users/ramon/git/personal/tools-installer/setup.py:180), [setup.py:216](/Users/ramon/git/personal/tools-installer/setup.py:216)); uninstall discovers and removes them generically ([installer/uninstall.py:266](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:266), [installer/uninstall.py:335](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:335)).

- Reusing `TweakBundle` is appropriately minimal. Its empty `requires` and `executables` defaults support pure aliases/functions without new artifacts ([installer/tweaks.py:31](/Users/ramon/git/personal/tools-installer/installer/tweaks.py:31)), and `claude-skip` supplies a direct precedent ([installer/tweaks.py:70](/Users/ramon/git/personal/tools-installer/installer/tweaks.py:70), [installer/tweaks.py:109](/Users/ramon/git/personal/tools-installer/installer/tweaks.py:109)).

- The plan correctly covers both UI copy surfaces. `policy.description` appears in the table ([installer/wizard_app.py:899](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:899)), while the per-policy dictionary supplies expanded detail and otherwise falls back to generic copy ([installer/wizard_app.py:928](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:928)). Dedicated `opencode-auto` assertions are justified.

- Task 3's subprocess approach is strong: a fake executable on controlled `PATH` exercises actual argument propagation without invoking Cursor. Exact `--model`/`--model=*` cases and the quoted-substring case address the main conditional-injection risks.

- The threat model identifies the important hazards: always-on permission bypass, misleading `opencode` semantics, recursive function calls, and model-entitlement uncertainty.

## Concerns

- **HIGH — Tasks 1 and 2 cannot pass their own quality gates.** The existing test asserts exactly four bundle IDs ([tests/test_tweaks.py:29](/Users/ramon/git/personal/tools-installer/tests/test_tweaks.py:29)). The plan deliberately postpones updating it until Task 3 ([10-01-PLAN.md:129](/Users/ramon/git/personal/tools-installer/.planning/phases/10-agent-cli-ergonomics/10-01-PLAN.md:129)), while Tasks 1 and 2 each require the targeted suite and `make validate && make test` to pass ([10-01-PLAN.md:273](/Users/ramon/git/personal/tools-installer/.planning/phases/10-agent-cli-ergonomics/10-01-PLAN.md:273), [10-01-PLAN.md:370](/Users/ramon/git/personal/tools-installer/.planning/phases/10-agent-cli-ergonomics/10-01-PLAN.md:370)). This also violates the repository's requirement that every commit pass both gates ([.claude/git-workflow.md:10](/Users/ramon/git/personal/tools-installer/.claude/git-workflow.md:10)).

- **HIGH — All three tweaks are inert in supported split link mode.** `_build_app` always gives tweak policies `_MYSHELLRC` ([setup.py:216](/Users/ramon/git/personal/tools-installer/setup.py:216)), but split mode intentionally writes directly into `.zshrc`/`.bashrc` and neither creates nor sources `.myshellrc` ([installer/app.py:185](/Users/ramon/git/personal/tools-installer/installer/app.py:185)). The existing test explicitly verifies this behavior ([tests/test_app.py:444](/Users/ramon/git/personal/tools-installer/tests/test_app.py:444)). Therefore enabling any new policy writes a valid but unreachable block. The plan's "zero new plumbing" assertion overlooks this supported configuration.

- **HIGH — Task 3's required implementation and regression test contradict each other.** It correctly says `cursor()` should delegate using bare `cursor-agent "$@"`, then immediately requires both functions to avoid bare calls ([10-01-PLAN.md:463](/Users/ramon/git/personal/tools-installer/.planning/phases/10-agent-cli-ergonomics/10-01-PLAN.md:463)). Its proposed content test also rejects the delegation it just required ([10-01-PLAN.md:497](/Users/ramon/git/personal/tools-installer/.planning/phases/10-agent-cli-ergonomics/10-01-PLAN.md:497)). Only the self-shadowing `cursor-agent()` function needs `command cursor-agent`; `cursor()` safely calls a differently named function.

- **MEDIUM — The reload guidance is wrong for aliases and functions.** `tweak_policy` returns the shared hint "open a new shell or run `hash -r`" ([installer/policy.py:35](/Users/ramon/git/personal/tools-installer/installer/policy.py:35), [installer/policy.py:183](/Users/ramon/git/personal/tools-installer/installer/policy.py:183)), and the TUI displays it verbatim ([installer/wizard_app.py:1018](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1018)). `hash -r` does not source newly written aliases or functions. Users following that option will see no change.

- **MEDIUM — Fresh-shell tests miss existing-alias collisions.** Bundle bodies are written verbatim ([installer/tweaks.py:193](/Users/ramon/git/personal/tools-installer/installer/tweaks.py:193)), while existing syntax tests parse them in clean shell processes only ([tests/test_tweaks.py:193](/Users/ramon/git/personal/tools-installer/tests/test_tweaks.py:193)). A pre-existing `cursor-agent` or `cursor` alias can make `cursor-agent() { ... }` fail while sourcing. The proposed fresh-Bash helper will not detect that, nor does it execute behavior under zsh.

## Suggestions

- Either combine the three small changes into one coherent task/commit, or update the exact bundle-ID assertion after every task: five IDs in Task 1, six in Task 2, seven in Task 3.

- Resolve split mode explicitly. Pass the actual sourced rc targets into tweak policies, or ensure `.myshellrc` becomes sourced when a tweak is enabled. Add a split-mode integration test that opens a fresh shell and proves the alias/function resolves.

- Rewrite the recursion invariant as: "Every call from inside `cursor-agent()` to the executable uses `command cursor-agent`; `cursor()` contains exactly one intentional `cursor-agent "$@"` delegation." Test that invariant structurally and behaviorally.

- Add a tweak-specific reload hint such as: "Open a new shell or run `source ~/.myshellrc`." This likely requires adding `installer/policy.py` to the plan's modified files.

- Prefer alias-safe definitions such as `function cursor-agent { ... }` and `function cursor { ... }`, then execute the wrapper tests under both bash and zsh when available, including a case with pre-existing aliases.

## Risk Assessment

**HIGH.** The underlying feature is small and the chosen architecture is sound, but the current plan cannot produce green Task 1/2 commits, specifies an internally impossible Task 3 test, and fails functionally for split-mode users. After those issues are corrected, the implementation risk should fall to LOW–MEDIUM.

---

## Consensus Summary

Only one reviewer (Codex) ran this cycle. Its review is fully source-grounded — every strength and concern cites concrete `path/to/file:line` evidence and traces the actual mechanism rather than restating the plan's own claims — so its findings are weighted at full value even without a second reviewer to corroborate.

### Agreed Strengths
N/A — single-reviewer cycle; nothing to cross-corroborate.

### Agreed Concerns
N/A — single-reviewer cycle; nothing to cross-corroborate. The 3 HIGH and 2 MEDIUM concerns above stand as Codex's independently-verified findings:
1. Tasks 1 and 2 as sequenced cannot pass their own stated quality gates (bundle-count assertion left stale until Task 3).
2. All three tweaks are inert under supported split-link mode (tweak policies always target `.myshellrc`, but split mode never sources it).
3. Task 3's required `cursor()` implementation directly contradicts its own proposed regression test.
4. Shared "hash -r" reload hint is factually wrong for alias/function-based tweaks.
5. Fresh-shell syntax tests won't catch collisions with a pre-existing `cursor`/`cursor-agent` alias, and don't cover zsh.

### Divergent Views
N/A — single-reviewer cycle.

## Cycle 2 (codex-sol-high)

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`
**Commit reviewed:** `ed14d8b` (post cycle-1 fixes)
**Risk assessment:** HIGH

### Cycle 1 Resolution Status (per reviewer)

| # | Finding | Status |
|---|---|---|
| 1 | Tasks 1-2 cannot pass their own gates | FIXED |
| 2 | Tweaks are inert in split mode | NOT FIXED (reclassified as accepted, not actually fixed) |
| 3 | `cursor()` implementation/test contradiction | FIXED |
| 4 | `hash -r` reload guidance is wrong | PARTIALLY FIXED (enable path only) |
| 5 | Existing-alias collisions and zsh execution untested | NOT FIXED |

### New/Unresolved Findings

1. **HIGH — split-mode inertness was accepted, not fixed.** Split mode is a real supported configuration (`installer/cli.py:55`, `setup.py:307`) that never creates/sources `~/.myshellrc` (`installer/app.py:179`, `tests/test_app.py:444`), yet every tweak policy still targets `_MYSHELLRC` unconditionally (`setup.py:216`). The cycle-1 fix documented this as a pre-existing, accepted limitation rather than fixing it — the reviewer holds firm that a warning does not make the aliases/functions operative, so the phase's own success criterion (bare invocations work) remains literally false under this supported configuration.
2. **HIGH — the new alias-collision regression test is built on incorrect shell semantics.** The plan retains a parenthesized function definition (`cursor-agent() { ... }`) and expects a pre-existing same-named alias to silently win at invocation time. Verified live: under Bash 3.2 (this project's target), defining a function with the exact same name as an active alias is a syntax error (exit 2) at the `()` — the planned test's expected `PRE_EXISTING_ALIAS` output path is unreachable. Under zsh 5.9 the function instead silently overrides the alias, the opposite of the plan's claimed behavior. The test as specified cannot pass in either shell for the reason it claims to test.
3. **MEDIUM — reload-hint fix only correct for enable, not disable.** `_TWEAK_RELOAD_HINT` is returned identically by both `apply` and `remove` (`installer/policy.py:183`, `:203`), but `remove_tweak` only deletes text from the rc file (`installer/tweaks.py:206`) — it cannot un-define an alias/function already loaded into the current shell. "Source `~/.myshellrc`" is correct advice after enabling, but wrong after disabling (a new shell is required, not a re-source).
4. **MEDIUM — the recursion regression test can hang indefinitely.** The planned test mirrors an existing `subprocess.run` pattern (`tests/test_tweaks.py:75,91`) that has no timeout. If a regression introduces exactly the bug the test exists to catch (a bare self-referential call), the subprocess may never return, contradicting the plan's own threat-model claim of a bounded exit.

### Suggestions
- Fix split mode for real in this phase: either write tweak policies to `rc_paths_for_mode(...)`, or ensure `.myshellrc` is sourced whenever any tweak is enabled, plus a fresh-shell split-mode integration test.
- Replace the collision-prone bare function definition with `unalias cursor-agent cursor 2>/dev/null` before an alias-safe `function cursor-agent { ... }` definition (or an internal function plus delegating aliases), and actually exercise both Bash and zsh with a pre-existing conflicting alias present.
- Split the reload hint by enable vs. disable — disable should say "open a new shell," not "source `.myshellrc`."
- Add an explicit timeout to the wrapper subprocess test, converting `TimeoutExpired` into a recursion-failure assertion.

### Disposition

Cycle 3 (final allowed cycle per ONESHOT-RULES cap) will replan to genuinely fix split-mode routing and the alias-collision test's shell semantics, split the reload hint by enable/disable, and add a subprocess timeout — all four findings are being addressed in code, not merely re-documented as accepted, since the reviewer explicitly rejected the "accepted limitation" framing for split mode.
