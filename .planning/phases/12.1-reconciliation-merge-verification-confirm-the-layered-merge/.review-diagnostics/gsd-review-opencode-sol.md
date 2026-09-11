Using `ai-kit-spec-review-checklist` to audit the GSD execution plan against its framework rules and the live codebase. I’ll verify the revised plan’s factual premises, executable checks, and cycle-1 resolution status without editing it.
The repository has no live `.codegraph/` index despite `ONESHOT-RULES.md` claiming one exists, so I’m grounding the review with direct source reads. The main risk area is Task 3: its import search, terminal-navigation assumptions, and “zero mutation” proof need to match actual Python reachability and startup behavior.
A source-backed issue is confirmed: the live smoke launch is not mutation-free. Entering each catalog starts `VersionRefreshService.refresh`, which always rewrites `~/.local/state/tools-installer/versions.json` (`installer/catalog_tui.py:258-280`, `installer/version_status.py:544-556`, `installer/version_cache.py:154-175`), while the plan checks only two shell-file mtimes. I’m checking the revision diff now to distinguish unresolved cycle-1 items from newly introduced gaps.
Task 1’s diagnosis is validated: the target test fails with the host `PNPM_HOME` and passes when both environment variables are removed. The tier rows also appear early enough in their default category-grouped tables for a 55-row terminal, but Task 3 still has two substantive proof gaps: it mutates the version cache and its selected-file grep does not establish package-wide production reachability.
Using `verification-before-completion` to separate observed results from plan claims, and `writing-clearly-and-concisely` to keep the final review actionable. I’m doing one final consistency pass over the three tasks and the phase boundary before issuing the verdict.
## 12.1-01

### Summary

The plan correctly diagnoses D-03, validates the 11 tier assignments, and follows the real TUI navigation architecture. However, Task 3 cannot substantiate its two main conclusions: the smoke run does mutate persistent state, and the limited grep does not prove that all five named modules have zero production reachability. The plan also omits an explicit audit of the reconciliation’s highest-risk engine/model changes.

### Strengths

- Task 1 identifies the actual environment leak. `owner_dirs` reads `PNPM_HOME` and `UV_TOOL_BIN_DIR` directly at `installer/ownership.py:256-263`, while the fixture hardcodes matching fallback paths at `tests/test_version_status.py:397-402`. The test currently fails at `tests/test_version_status.py:473`; running it with both variables removed passes.
- Task 2’s expected values match the registry. The user-tier rows are at `installer/registry.toml:2475-2568`, and the AI-tier rows are at `installer/registry.toml:2491-2500` and `installer/registry.toml:2608-2906`.
- The tier reasoning follows the documented semantics in `.claude/architecture.md:27-40`.
- The navigation mechanism is grounded correctly. Six views are defined at `installer/ui_common.py:103-166`; number bindings come from that registry at `installer/wizard_app.py:1416-1429`; navigation funnels through `show_view` at `installer/wizard_app.py:1605-1628`; `q` exits at `installer/wizard_app.py:1672-1677`.
- Final quality gates match the project’s required commands in `Makefile:34-48` and `.claude/testing.md:31-33`.

### Concerns

- **HIGH: The plan does not audit the full reconciliation it claims to verify.** The context names nine commits for review at `.planning/phases/12.1-reconciliation-merge-verification-confirm-the-layered-merge/12.1-CONTEXT.md:81-83` and identifies the merged `Tool` model as the highest-risk point at `12.1-CONTEXT.md:101-105`. Yet the tasks only inspect one failing test, tiers, two unwired subsystems, and TUI rendering. Significant reconciled behavior in `installer/model.py:239-322`, `installer/model.py:612-701`, and `installer/engine.py:64-85` receives no explicit architectural or diff audit. A green suite alone does not meet the phase’s “not just green” goal.
- **HIGH: The “zero real-machine mutation” claim is false.** Every catalog mount starts version refresh at `installer/catalog_tui.py:258-280`. Refresh always calls `save_version_cache` at `installer/version_status.py:544-556`, which writes `~/.local/state/tools-installer/versions.json` through `installer/version_cache.py:154-175` and `installer/version_cache.py:196-197`. The plan only compares `~/.myshellrc` and `~/.zshrc` mtimes at `12.1-01-PLAN.md:312-332`.
- **HIGH: The static import audit is incomplete and one conclusion is factually wrong.** `setup.py` imports `installer.policy` at `setup.py:39-46`, and that module imports `installer.agent_env` at `installer/policy.py:19`. Therefore `agent_env.py`, which Task 3 classifies as a structurally inert sibling, is loaded through the production entry point. The proposed selected-file grep at `12.1-01-PLAN.md:290-300` neither scans the full package nor distinguishes module import, symbol use, and UI wiring.
- **MEDIUM: The smoke script lacks failure cleanup.** It enables `set -euo pipefail` at `12.1-01-PLAN.md:308-310`, but only sends `q` at `12.1-01-PLAN.md:329`. Any failed assertion after launching tmux leaves the session and process running. Fixed sleeps at `12.1-01-PLAN.md:318-320` also make readiness timing-dependent.
- **LOW: Temporary-script handling is internally inconsistent.** Task 3 permits leaving the script uncommitted at `12.1-01-PLAN.md:334-337`, while phase verification requires no undeclared working-tree changes at `12.1-01-PLAN.md:403-405`.

### Suggestions

- Add a reconciliation-diff task mapping every production change in `b9a8876..a570bf3` to architectural evidence, with explicit coverage of `model.py`, `engine.py`, `resolve.py`, `host_setup.py`, and `skill_lifecycle.py`.
- Run the tmux process with an isolated temporary `HOME`; assert the real HOME remains unchanged and record mutations inside the temporary HOME.
- Replace the selected-file grep with a package-wide AST/import and symbol-reference audit. Report separately whether each module is imported, whether its mutating functions are called, and whether it is exposed through the UI.
- Add an `EXIT` trap that kills the unique tmux session and removes temporary files. Poll for a known header instead of relying only on fixed sleeps.
- Require deletion of the temporary script after its output is recorded.

### Cycle 1 Check

The request did not include the referenced “Cycle 1 Review” section, and commit `19131c2` is not present in this checkout. Therefore individual cycle-1 findings cannot be mapped to their revised dispositions. The current plan was reviewed independently from disk.

### Risk Assessment

**HIGH.** Tasks 1 and 2 are low-risk and executable, but Task 3 would produce false assurance about both production reachability and machine mutation. The plan needs revision before execution.
