---
phase: 16
cycle: 3
reviewers: [opencode-plan-review, opencode-glm-5.2]
reviewed_at: 2026-10-10T19:06:44Z
plans_reviewed: [16-17-PLAN.md, 16-18-PLAN.md, 16-01-PLAN.md, 16-02-PLAN.md, 16-03-PLAN.md, 16-04-PLAN.md, 16-05-PLAN.md, 16-06-PLAN.md, 16-07-PLAN.md, 16-08-PLAN.md, 16-09-PLAN.md, 16-10-PLAN.md, 16-11-PLAN.md, 16-12-PLAN.md, 16-13-PLAN.md, 16-14-PLAN.md, 16-15-PLAN.md, 16-16-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review (reasoning=medium)"
  opencode-glm-5.2: "opencode-go/glm-5.2 (reasoning=high)"  # cycle 3 (16-17, 16-18) used this identity only
model_sources:
  opencode-plan-review: "pinned"
  opencode-glm-5.2: "pinned"
plan_coverage:            # per-identity by design (batched run); the union covers all 16 plans
  opencode-plan-review:
    total: 16
    missing: ["16-07", "16-08", "16-09", "16-10", "16-11", "16-12", "16-13", "16-14", "16-15", "16-16"]
  opencode-glm-5.2:
    total: 16
    missing: ["16-01", "16-02", "16-03", "16-04", "16-05", "16-06"]
  cycle_3_opencode-glm-5.2:   # gap plans, reviewed in 2 rounds
    total: 2
    missing: []
---

# Cross-AI Plan Review — Phase 16 (convergence cycle 2)

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

> Note (run history): Cycle 2 reviews the plans as revised after round 1 (REVIEWS @ b992d0a, per-plan `## Review Dispositions Ledger`) and the plan-checker revisions (cee9581, 1cf1f8d, ff349df). The configured reviewer is the single instance `opencode-plan-review` (opencode lane, `router-env/my-plan-review`). One whole-prompt attempt (all 16 plans, ~367 KB) ended with the agent stopping after tool calls and no final review (#1936 shape, same as cycle 1), so the review was re-run in 5 plan batches with identical instructions (source-grounded `file:line` evidence required, round-1 ledger check, standing constraints).
>
> - **Batches 1-2 (16-01..16-04, 16-05..16-06):** `opencode-plan-review` (`router-env/my-plan-review`, effort medium), verified at ff349df.
> - **Batches 3-5 (16-07..16-08, 16-09..16-12, 16-13..16-16):** `opencode-go/glm-5.2`, `--variant high`, invoked directly with a per-call CLI flag (no config change). The router's backing model went locked (`Model opencode-zen/glm-5.2 is locked`, service_unavailable) after batch 2: batch 3 first stopped with no final message, then batches 3 and 4 failed fast, and 15 probes over about an hour stayed locked. The user chose the substitute model. Batch 3 was verified at 4a3ef8c/3ac3b57, batch 4 at 3ac3b57, batch 5 at 04aa62e.
>
> The two identities are different models through the same opencode adapter, and each reviewed a disjoint subset of plans, so there is no cross-reviewer consensus on any single plan. The "Consensus Summary" below is the orchestrator's source-checked adjudication of each finding. Plans were fixed during the run (4a3ef8c, 3ac3b57, 04aa62e), as recorded under "Post-review plan fixes".

## OpenCode Review (opencode-plan-review) — batches 1-2: 16-01..16-06

All claims below were verified against the working tree at `ff349df` (clean), reading every referenced source file and tracing each claimed mechanism through the actual code. Standing constraints checked for all four plans: tests/verification touch only `tmp_path`/monkeypatched seams (16-03 and 16-04 state explicit host-safety rules; the session-scoped `real_home_untouched` fixture at `tests/conftest.py:40-62` backstops both), zero sudo/pkexec/doas anywhere in the four plans, English only throughout. No violations found.

## 16-01

**Summary:** Adds `sdkman` as a first-class `Owner` end to end (Literal, `_KIND_TO_OWNER`, `_CANDIDATE_ORDER`, all four label/removal tables), a per-method location proof reusing the registry's existing `bin_dir`, the `own installer` label for script-kind tools, the dead `_sdkman` probe's kind/param fix, and an honest SDKMAN update refusal. The revision for round 1 is faithfully reflected in executable content, and every mechanism traces correctly through the real `resolve_ownership` branch order.

**Strengths:**
- Every round-1 "accepted" disposition is visible in executable plan content, not just ledger prose: truth #6 now names `_unknown_reason`'s active-path sentence, which I verified fires exactly when `active_path is not None` (`installer/ownership.py:938-939` vs `:940-945`); `_REMOVAL_COMMANDS["sdkman"] = "sdk uninstall {package} <version>"` interpolates the candidate exactly like `installer/uninstall.py:229`'s registry-derived phrase; the probe-wiring deferral is stated in Task 2's action with a SUMMARY record; the stale hybrid record fix (`tests/test_update.py:212-219` builds `owner="installer"` + `method.kind="sdkman"` today — verified) is action item (5) with a grep gate; the one-predicate rule (`_location_proof` called by both `_collect_candidates` and `_location_dirs`) is action items (3)/(4) with the call-count grep.
- I hand-checked every planned table entry against all six exhaustiveness gates in `tests/test_ownership.py` and all pass: `:959-961` (OWNER_LABELS ⊇ Owner−unknown), `:1021-1023` (OWNER_DETAIL_LABELS), `:1026-1028` (pairwise distinct — "SDKMAN" is new), `:1751-1758` (`_REMOVAL_COMMANDS ∪ _NO_REMOVAL_HINT == get_args(Owner)`, disjoint), `:1761-1765` (commands ⊆ descriptions), `:1853-1862` (`_COMMAND_OWNERS`: backtick + "realpkg" + no "toolcmd" for with-package, no backtick for without-package), `:1865-1881` (label-in-hint), `:1798-1809` (≤14 chars).
- The direct/by-elimination mechanism traces end to end: `_applies` accepts `sdkman` unconditionally (`installer/resolve.py:53-64`), so the method reaches `_collect_candidates`'s loop; `attribute_path`'s `.resolve()` on both sides (`ownership.py:463-479`) follows the `current -> <version>` symlink with no new code; `which → None` falls to the `len(candidates) == 1 and not unreadable` branch (`:583-592`), and `_unreadable` (`:841-854`) has no sdkman arm, so by-elimination is never blocked. `_KIND_TO_OWNER`/`_CANDIDATE_ORDER` have no consumers beyond `competing_owners`/`_collect_candidates` (verified by grep), so the additions are blast-radius-free.
- The kind gate structurally honors the prohibition: `_INSTALLER_KINDS = {github_release, tarball, app, script}` (`apps.py:32`, `download.py:27`), so location proof can never fire for brew/cask/node/uv-tool, which keep inventory proof.
- The refusal path is real and correctly ordered: the `method.kind == "sdkman"` branch (`update.py:249-255`) precedes `UNMANAGEABLE_OWNERS` (`:256`) and `resolve_update_argv`'s only call (`:280`); sdkman is not added to `UNMANAGEABLE_OWNERS` (verified at `ownership.py:121`), and the `u` gate (`catalog_tui.py:760`) passes a direct sdkman record. The refusal-over-hang rationale matches `executors.py:472-489`'s own comment about the sourced `sdk` function and the brownfield interactive prompt.
- Cross-plan interface double-pinned: the sdkman candidate's `method` field is asserted non-None with `params["bin_dir"]` here AND re-pinned through the real `resolve_ownership` in 16-06 (`16-06-PLAN.md:74`), which is the belt-and-suspenders the round-1 MEDIUM asked for.

**Concerns:**
- LOW: The objective's "Update stale comments in installer/ownership.py that say no sdkman owner exists" is a no-op — `grep sdkman installer/ownership.py` returns zero matches today; the actual stale comment ("No `Owner` value can ever carry 'sdkman'", `uninstall.py:220-227`) is already handled by Task 2. Harmless instruction noise that could send an executor hunting for a nonexistent comment.
- LOW: Action (4) never states which method sequence `resolve_ownership` passes to `_location_dirs(tool, methods)` (`applicable` alone vs `applicable + _ownership_only_methods`). Immaterial today — `_OWNERSHIP_ONLY_KINDS` is brew/cask only (`ownership.py:159-180`), both excluded from location proof by the kind gate — but the call-site choice is unpinned and the two sets could diverge if `_OWNERSHIP_ONLY_KINDS` ever gains a location-proofable kind.

**Suggestions:** Delete or reword the stale-comment line to point only at `uninstall.py:220-227`; add half a sentence to action (4) naming the sequence passed to `_location_dirs` (the same combined sequence `_collect_candidates` iterates).

**Risk Assessment:** LOW. The evidence rule is preserved structurally (kind-gated location proof, inventory proof untouched, ambiguity still `unknown`), no subprocess is added, the refusal is honest, and all four tables are exhaustiveness-gated. The deferred L38 (pre-existing "not attributable" wording) has sound rationale: pre-existing copy untouched by any D-decision, with 16-05's `active_path_note` and 16-15's detail pane compensating.

## 16-02

**Summary:** Replaces the single tool-level skill status operation with a per-harness `status_probes` model over three closed sources (`plugin-cli`, `skills-lock`, `install-state`), a closed `HARNESS_CLI_STATUS` argv+matcher table mirroring `HOST_SETUPS`, a batching `inspect_skill_packs` entry point, and registry migration of ponytail/superpowers. All four round-1 dispositions are verified in executable content, and the live-shape claims check out against the code (the substring-match defect at `skill_lifecycle.py:73` is real; `inspect_status`'s only callers are tests, verified by grep).

**Strengths:**
- All four round-1 findings are closed in executable content: the parse-valid-but-unanswerable probe maps to `unknown` via `HARNESS_CLI_STATUS.get(harness)` with zero probe calls, backed by the `grep -c 'HARNESS_CLI_STATUS\['` == 0 gate and a named test; the claude matcher strips `❯` plus following whitespace with a canned literal-row test; the nine `INSTALL_STATE_HARNESS_DIRS` values are concrete strings — I cross-checked every one against the resolver defaults in `.claude/gsd-core/references/gsd-run-resolver.md` (`.gemini/antigravity`, `.codex`, `.copilot`, `.cursor`, `.config/kilo`, `.config/opencode`, `.codeium/windsurf` all byte-match; the two judgment calls — claude→global `~/.claude`, kimi→`~/.kimi-code` — are exactly the sensible resolutions of that file's two kimi/claude entries, and the plan documents both inline); the `gsd-core` convention is stated and pinned cross-plan by 16-07 Task 2(e)'s registry test (`16-07-PLAN.md:167`).
- The security split is structural and verified: `_SKILL_MATCH_RE` (permits `/` for `obra/superpowers`) is only used for registry-validated match strings; path components go through the new `_SKILL_NAME_RE` (`^[A-Za-z0-9._-]+$`, no `/`) plus explicit `.`/`..` rejection, with the `../evil` pinning test and the `Path.home()` ban in acceptance.
- The migration scope is nearly exact: the fail-closed tests (`tests/test_skill_lifecycle.py:312-338`) survive the new `inspect_status(tool, probe, home=Path.home())` wrapper unchanged (a raising probe → `unknown` → "otherwise" in the wrapper's precedence), and `_parse_skill_lifecycle`'s `allowed_fields` (`model.py:449-461`) admits `"status_probes"` cleanly.
- `SKILL_HARNESSES` widening (66-77 today, verified) to 12 alphabetical members is safe: it is used only for validation (`model.py:469`), never enumerated in UI.
- Cross-plan wiring is consistent: 16-12 wires the production probe with `run_query` (`16-12-PLAN.md:37,117`), closing the hang backstop, and calls `inspect_skill_packs(packs, self._skill_probe, self._skill_home)` with the exact signature this plan defines.

**Concerns:**
- LOW: One existing test falls outside the stated migration scope and will break: `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` (`tests/test_skill_lifecycle.py:277-293`) feeds canned `"ponytail\nobra/superpowers\n"` and asserts ponytail reads `present` — but ponytail's new probe is codex, and the codex matcher requires a `<match>@<marketplace>` token with an `installed` status column, which the bare `"ponytail"` line fails. The plan's instruction "migrate every existing test that referenced the deleted names" does not cover this test (it references only `inspect_status`, which survives). The failure is loud and the fix obvious (realistic canned row), but the small risk is an executor taking the path of least resistance and loosening the matcher instead of the fixture.
- LOW: Whether `"operation_id"`/`"args"` are removed from `_parse_skill_operation`'s unknown-field allowed set (`model.py:388-390`) is unspecified. Fail-closed either way (a `mode = "command"` row is rejected at the mode gate or the field gate), but the exact error message the existing reject tests match (`:106-109`, "unknown status field 'argv'") depends on the check order staying field-gate-first.

**Suggestions:** Name `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` in Task 1's migration list with the realistic canned codex row (`ponytail@ponytail  installed, enabled  5.1.0`); state that the unknown-field check stays ahead of the mode check and that `"operation_id"`/`"args"` leave the allowed set.

**Risk Assessment:** LOW. Trust boundaries are tight (closed argv tables in code only, registry supplies validated names, `probe-⊆-supported_harnesses` at load), no software is acquired to answer a status question, disk fallbacks are read-only and regex-guarded, and the one unproductized edge (production probe) is explicitly backstopped to 16-12.

## 16-03

**Summary:** Rebuilds `rcclean`'s two scanners on one shared quote-aware `_path_line_targets` generator with block-stack guard tracking, Path-normalized matching, and the extra real-world writer shapes, closing 15.8 findings CR-01/WR-01/WR-02/IN-01/IN-03. All five findings verified still present in source; the block-stack semantics trace correctly against every named shape; the round-1 process contradiction is genuinely gone. One new gap: the zsh-array line's strip candidacy is left contradictory between the must_haves truth and the mechanical `simple` spec.

**Strengths:**
- The round-1 MEDIUM (contradiction between "unchanged in meaning" and the CR-01 RED tests) is resolved in executable content: action step (5) renames `test_indented_writer_still_counts_as_a_writer` (`tests/test_rcclean.py:328-344`, pins the exact Fedora presence-guard header as REPORTED — verified) to `test_writer_dir_test_if_reported` with a `[ -d ]` header, the final behavior bullet now names it as the ONE exception, and the acceptance grep (`grep -c 'def test_indented_writer_still_counts_as_a_writer'` prints 0) enforces it.
- I traced the block-stack rules by hand against every named shape and they hold: the presence-guarded `if`/Fedora `if ! [[ "$PATH" =~ ...]]`/pnpm multi-line `case` all read `{}` (condition-only `references_path`, `then`-on-next-line handled, `_PATH_EXPORT` already matches non-export `PATH=`, `rcclean.py:16`); same-line `if/then/fi`, `for/do/done`, and the real `path_export_guard` output (ends `;;esac` with no space, `shellrc.py:128` — "esac" preceded by `;;` satisfies the closure rule) are all frame-neutral; `done` pops only its own frame (the nested-loop test genuinely fails on the pop-the-outer-if bug); `elif` pop-then-push keeps one frame; `[ -d ]` headers stay reported (the renamed test preserves the indented-lines-count-for-reporting doctrine).
- The `&&`/`||` presence-guard semantics are correct in both directions (earlier PATH-assignment segments excluded as presence tests, so the three-`PATH` chain is a writer while the one-line idiom is not — both pinned).
- The docstring-discipline disposition is real: `tests/test_shellrc.py:1034`'s AST invariant (sole exemption: `find_duplicate_path_lines`' docstring, verified in the test text) is now in the acceptance run, and the "describe, don't spell out" rule follows the existing precedent at `rcclean.py:126-128`.
- Both deferred-free: this plan's ledger has zero deferred items, and each of the four accepted dispositions has its named artifact (rename + grep, docstring rule + test run, the case-limit comment, the zsh `shortcut:` comment).

**Concerns:**
- MEDIUM: The zsh-array line's STRIP candidacy is contradictory. Must-have truth #5 promises the strip set "does not widen… it still flags only column-0 lines that are a single plain PATH assignment with nothing else on the line." But Task 3's mechanical spec `simple = (len(segments) == 1 and not comment_dropped)` makes a column-0 `path=("$HOME/.local/bin" $path)` line `simple=True`, and Task 1's rebuild flags on `line.simple and not line.indented and not line.presence_guarded` with any matching target — `_ZSH_PATH_ARRAY` feeding the same target union makes it a strip candidate. Today that line is never flagged (`_PATH_EXPORT` at `rcclean.py:16` requires uppercase `PATH=` and no parens — verified no match). The consumer is destructive: `app.py:408-419` strips flagged lines and rewrites the rc file (behind a confirm, but the whole array line — including other directories the user put in it, e.g. `path=("$HOME/.local/bin" "$HOME/bin" $path)` — is offered and then removed). No test pins the array line's strip candidacy either way (Task 3's acceptance only asserts `[]` for the three compound shapes; the array behavior bullet says only "is a writer"). Round 1's 16-08 review already observed `simple` is True for array lines and made the GUARD write refuse zsh arrays — the STRIP path (which deletes rather than rewrites) has no such refusal.
- LOW: `_location`-style drift risk in `_split_unquoted`'s `;;` handling is acceptable but the interaction with segments after a `;;` (a second case row on one line) leaves the following segment's separator unclassified — only reachable in single-line multi-row case lines the first-word skip already bypasses; noting for completeness.

**Suggestions:** Add one sentence to Task 3 (and one assertion to the zsh test): `_ZSH_PATH_ARRAY`-matched lines are never strip candidates (`find_duplicate_path_lines(...) == []` for the array shape), or alternatively state plainly that single-dir array lines ARE strip candidates and amend truth #5's wording — either resolution is fine; the current half-and-half is not. Pin it with `assert find_duplicate_path_lines(...) == []` on the exact array fixture.

**Risk Assessment:** MEDIUM overall, driven solely by the zsh-array strip ambiguity above. The parser design itself is sound, every heuristic is pinned by a named test, the diagnosis path's worst failure is wrong prose, and the strip path for every OTHER shape only gets narrower (compound shapes assert `[]`). One sentence and one assertion close the remaining gap.

## 16-04

**Summary:** Closes WR-03/WR-04/WR-05/IN-02: one public injectable `duplicate_path_writers` seam used by both Doctor routes, conftest-level `$ZSH` isolation, and a wider read-only scan set (`.zshenv`, `.zlogin`, `~/.bashrc.d/*`, ZDOTDIR-consistent zsh files). All four findings verified in source; every fix shape checks out; the round-1 TUI-harness concern is resolved with a named harness plus a grep gate.

**Strengths:**
- Findings verified precisely: `run_doctor` injects `path_value`/`exists`/`which`/`managed_globals`/`disk_pressure`/`competing` (`app.py:338-350`) but calls `_duplicate_path_writers(report)` directly at `:374`, which hardwires `path_scan_rc_paths()` + `os.environ` at `:318` — and I confirmed no test references `_duplicate_path_writers` (only `app.py:308/:374`); `wizard_app.py:2389-2394` re-implements the scoping inline; `tests/conftest.py:67-69` clears only `$ZDOTDIR` while the `$ZSH` clear is local to `tests/test_setup.py:438-443`; `locations.py:124-131` omits `.zshenv`/`.zlogin`/`.bashrc.d` and reads `.zprofile` home-relative while `_zshrc()` honors ZDOTDIR.
- The round-1 TUI-harness disposition is honored in executable content: the test builds through `tests/test_wizard_app.py::_app(...)` (`:272-310` — verified it constructs the real `UnifiedApp`, whose `__init__` composes DoctorScreen at `wizard_app.py:2383-2411`), monkeypatches `installer.wizard_app.duplicate_path_writers` (the imported-name pattern the plan's import change enables), and the acceptance grep forbids a `DoctorScreen(` call inside the test. The `run_doctor` RED test has a concrete render target (`guidance.py:95-120` renders the rc file names into the "adds it unconditionally" sentence; `render.py:213-219` passes the mapping through), and the mutation-check instruction makes the wiring test falsifiable.
- The `$ZSH` isolation is stronger than the finding asked: the hand-rolled sandbox at `tests/test_setup.py:1035-1055` does NOT clear `$ZSH` today (only `_sandbox` at `:435` does), so the conftest autouse fixture fixes both sandboxes; the `ZSH=/nonexistent/.oh-my-zsh uv run pytest` verify proves it under a hostile invoking shell; the rename is free (zero explicit `no_zdotdir` consumers, verified by grep).
- The scan-set widening is correct and safe: `zshrc_path(home, os.environ).parent` reuses the existing ZDOTDIR-aware resolution (`locations.py:8-26`) so all four zsh files follow one rule, `.bash_profile`/`.profile` correctly stay home-relative, the glob is `is_dir()`-guarded and sorted, and the only existing test of the function uses superset assertions (`tests/test_locations.py:226-234` — verified) so it survives. Bash files are unaffected by ZDOTDIR, as they should be.
- Both deferred round-1 findings have sound rationale (env-default vs injected `path_value` is inherent and now injectable; the `.bashrc.d` glob feasibility was confirmed by the reviewer against the source — both verified informational).

**Concerns:**
- None new. The plan correctly keeps `duplicate_path_writers`'s signature/return compatible so `installer/app.py::_duplicate_path_writers`'s single caller and wizard_app's composition need no behavior change, and 16-11's later rebuild (`16-11-PLAN.md:105,113`) explicitly preserves this plan's signature and retargets its route tests — the seam is designed to be refactored forward, not around.

**Suggestions:** None required. Optionally note in Task 1 that the `run_doctor` kwarg default (`duplicate_writers=duplicate_path_writers`) is a function reference evaluated at def time — safe because the defaults that matter (`rc_paths`, `env`) are evaluated inside the body, which the plan already specifies.

**Risk Assessment:** LOW. Pure seam/isolation/read-only scan-set work: no diagnosis behavior change, no rc writes (backstopped by `real_home_untouched`), both previously-untestable routes pinned, and the two consumer plans (16-08, 16-11) land on the single tested source this plan creates.

### Batch verdict (reviewer, before post-review fixes)

**Unresolved HIGH findings:** 0 (none of 16-01 – 16-04).

**Unresolved non-HIGH findings that still need a plan change:** 1
- 16-03, MEDIUM — zsh `path=(...)` line's strip candidacy: the mechanical `simple = (len(segments) == 1 and not comment_dropped)` spec makes single-segment array lines strip candidates (a widening today's `_PATH_EXPORT` never flags), contradicting must_haves truth #5's "strip set does not widen," feeding the destructive strip consumer at `app.py:408-419`, and pinned by no test either way. Needs one sentence + one `== []` assertion (or an explicit statement that arrays are strippable, amending truth #5).

Also worth folding in if the plan is touched anyway (LOW, not blocking): 16-02's un-migrated `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` ponytail canned output (no longer satisfies the codex line-level matcher); 16-01's no-op "stale comments in ownership.py" instruction (zero `sdkman` matches there; the real stale comment is `uninstall.py:220-227`, already handled) and the unspecified `_location_dirs` call-site method sequence; 16-02's unspecified `_parse_skill_operation` allowed-fields shrink.

**Round-1 findings now resolved (verified in executable content, not just ledger prose):**
- 16-01: all 6 accepted findings — truth #6 reason wording (matches `ownership.py:938-945` exactly), sdkman removal-command interpolation (passes the `:1853-1862` gate I hand-checked), probe-wiring deferral stated + SUMMARY record, stale hybrid `test_update.py:212` record replaced with a grep gate, one shared `_location_proof` predicate with a call-count grep, sdkman candidate `method` field pinned (and double-pinned via real-`resolve_ownership` in 16-06). Deferred L38 (pre-existing wording) — sound rationale.
- 16-02: all 4 — unknown fallback via `.get` with no-KeyError/no-probe-call tests, `❯`-plus-whitespace stripping with a canned literal row, nine concrete `INSTALL_STATE_HARNESS_DIRS` values (each cross-checked against gsd-run-resolver.md, claude/kimi resolutions documented), `gsd-core` convention pinned by 16-07 Task 2(e).
- 16-03: all 4 — the CR-01 test contradiction resolved by the named rename + grep gate, the AST-invariant docstring rule added to acceptance, the case-limit comment, the zsh-array `shortcut:` comment.
- 16-04: 1 accepted (named `_app` harness + grep gate, verified against the real harness) + 2 deferred with sound, reviewer-confirmed rationale.

Cross-plan revision hotspots checked where they intersect this batch: 16-05/16-06 depend on and correctly consume 16-01's location-candidate/`bin_dir` interface; 16-08 consumes 16-03's `_PathLine`/`_path_line_targets` (its `unresolved` flag is added with a default, keeping 16-03's constructions valid); 16-11 retargets 16-04's route tests while preserving the seam signature; 16-12 wires 16-02's `inspect_skill_packs` with `run_query`. All consistent.

## 16-05

### Summary

Adds an undeclared-Homebrew evidence path to ownership: a brew candidate proven by a Cellar-resolving path (live path, brew's own `bin/<cmd>` link, or `opt/<formula>/bin/<cmd>` for keg-only formulae) plus the brew inventory, appended only when no declared brew candidate exists and before `matching` is computed — so the existing active-path attribution (`installer/ownership.py:511-524`) picks the winner. Adds `ManagerOwnership.off_policy`, three pure helpers, the D-05 off-policy update note in `update.py::_perform`, and the `shadow_brew` withholding rule so a link-proven shadowed copy cannot trip `_native_owner`/`_os_package_owner`'s "any candidate blocks" gates. Every structural claim in the plan verifies against current source; the keg-only revision (cee9581) is sound and test-pinned.

### Strengths

- **Root cause and insertion point exact.** `_collect_candidates` (`installer/ownership.py:774-838`) iterates only the declared-method sequence built at `ownership.py:503-506`, so a tool declaring only sdkman (groovy, `registry.toml:1773-1776`) can never produce a brew candidate today. Appending before `matching` (`ownership.py:511`) makes the existing machinery decide; "move `active_path` up" is a two-line move of the pure `_resolve_active_path(which(tool.cmd))` line (`ownership.py:508`, helper at `:857-864`) — no side effects, as claimed.
- **All planned constructions match the real dataclasses.** `OwnershipCandidate(owner, method=None, package, current_version, evidence)` fits `ownership.py:287-293`; `ManagerOwnership` (`:296-308`) already carries `shadowed` and takes a trailing defaulted field cleanly; `_owned` (`:867-891`) is keyword-only so `off_policy=False` threads through; `_unknown` (`:894-914`) needs no change.
- **The `shadow_brew` withholding rule is verified necessary and mechanically possible.** `_native_owner`'s gate (`ownership.py:650`) and `_os_package_owner`'s gate (`:746`) both block on any candidate; both take `candidates` as a parameter (called positionally at `:535`, `:565-566`), so calling them with the reduced tuple and `dataclasses.replace`-ing the winner's record (`shadowed` field exists) works exactly as specified. The plan's option-(b) reasoning against `unknown` correctly cites D-06 and D-08 — both locked decisions.
- **The keg-only third proof path (checker revision 1) closes a real hole.** Homebrew does not link keg-only formulae into `<prefix>/bin/`; `<prefix>/opt/<formula>` is its maintained alternative link, so `test_undeclared_brew_keg_only_shadowed_by_sdkman` and Task 2's `also_installed_note` assertion on that fixture are the correct pins. The `shortcut:` cost comment is present.
- **"Nothing changes for argv" verified.** `resolve_update_argv` builds `["brew", "upgrade", package]` from `ownership.package` alone (`installer/update.py:167-171`), never touching `method`; and `_perform`'s sdkman branch (`update.py:249-255`) requires `method is not None`, so a `method=None` brew record sails past it into the brew dispatch at `:279-283` and the final `UpdateOutcome(status="updated")` at `:295-301`.
- **Tampering gates are real and doubled.** `_BREW_NAME_RE` (`ownership.py:132`) fullmatch plus `name in inventory.brew_formulae`, where the inventory itself was parsed by `parse_brew_list_versions` with the same regex (`:332`) — a planted Cellar directory for an unlisted formula produces nothing (T-16-14), and the malformed-segment test is constructible.
- **Regression pins cover all three sensitive branches.** `test_undeclared_script_only_by_elimination_unchanged` guards the exact `method=None` trap step (5) warns about (the artifact candidate's `installer_method` is genuinely None for script-only tools, `ownership.py:781-788`); the OS-package fixture shape is copyable from `test_os_package_owner_resolves_git_shaped_tool_on_fedora` (`tests/test_ownership.py:773`) with `_os_package_probe` (`:758`); `_resolve`'s `platform=_MAC` default (`:96-104`) makes the acceptance note about naming Fedora explicit accurate and necessary. `grep -c uninstall installer/update.py` prints 0 today, so Task 3's before/after D-04 check is enforceable.
- **Ledger dispositions are honored in executable content.** Round-1's MEDIUM (`declared_manager_label` native kinds) is now Task 2 behavior+action+truths with `.get()`-only lookups and `test_declared_manager_label_native_kind` (`_KIND_TO_OWNER`, `ownership.py:142-147`, genuinely lacks all four native kinds — the hazard was real); the off_policy-without-policy LOW is tightened (`declared_manager_label(...) is not None`) with `test_off_policy_requires_a_declared_policy`; the left-behind-Cellar suggestion is now the named `test_undeclared_brew_cellar_left_behind_not_listed`. The two deferrals (D-03 as note-not-offer; unreadable-inventory unknown wording) cite locked decisions D-04/D-05 and match CONTEXT.md exactly — sound rationale.
- **Standing constraints clean:** no sudo/pkexec/doas anywhere, all fixtures tmp-path based, verification is pytest only, English only.

### Concerns

- **LOW — the specified `declared_manager_label` expression is not pyright-clean.** `owner = _KIND_TO_OWNER.get(kind, kind.replace("_", "-"))` yields `Owner | str`, and `OWNER_LABELS.get(owner)` (`OWNER_LABELS: dict[Owner, str]`) requires key type `Owner` — pyright strict (`pyproject.toml:43`, `Makefile:39`) rejects `Owner | str` there, a shape this module is explicitly careful about (`ownership.py:122-127`'s own comment). Same class of nit: step (3b)'s `dataclasses.replace` — ownership.py imports only `from dataclasses import dataclass` (`:55`), so the name must be added; Task 3 needs `owner_label`/`declared_manager_label` added to update.py's import block (`:88-93`). All mechanical and gate-caught, but three un-specified import/type fixes in a plan otherwise precise to the line.
- **LOW — a script-installed tool whose `cmd` collides with a linked brew formula loses its by-elimination answer.** With `which` returning None, our installer artifact present, and `<brew_prefix>/bin/<cmd>` also existing (e.g. a vendor-script `bun` beside a brew `bun`), candidates become (installer, brew): the single-candidate by-elimination branch (`ownership.py:583-592`) no longer fires and the record falls to `unknown` ("more than one manager claims the tool… PATH does not resolve"). Fail-closed and arguably the more honest answer under the module's evidence rule, but it removes the `u` path for a tool this installer itself installed, and the plan pins only the non-colliding case.
- **LOW — `also_installed_note` is ungated for `owner="unknown"` records.** As specified it labels every candidate differing from `ownership.owner`, so an unknown record with a shadowed brew copy (e.g. `/usr/bin/java` active with no native probe injected) would return "also installed via Homebrew" — wrong prose when no owner is established. The sole planned consumer gates it in practice (16-15 Task 2 replaces code inside `_version_detail`'s `owner != "unknown"` block, `installer/catalog_tui.py:560`), so no user-facing bug — but the helper's contract shouldn't depend on every caller's discipline.
- **LOW — opt/ loop cost is real but bounded and acknowledged.** Worst case every non-brew catalog tool stats one `opt/<formula>/bin/<cmd>` per listed formula per resolve — tens of thousands of cheap stats on a full catalog refresh. The `shortcut:` comment covers it; no action needed.

### Suggestions

- Add one sentence to Task 2/Task 1: write the owner lookup pyright-safely (e.g. `owner: str = _KIND_TO_OWNER.get(kind) or kind.replace("_", "-")` with a `cast`/items-scan for the label) and name the three import additions (`dataclasses.replace` in ownership.py; `owner_label`/`declared_manager_label` in update.py).
- Add one line to `also_installed_note`'s spec: return None when `ownership.owner == "unknown"`.
- State the script-tool/brew-cmd-collision edge explicitly as accepted (unknown, fail-closed) so a later verifier doesn't mistake it for a bug.

### Risk Assessment

**LOW-MEDIUM.** The mechanism reuses the existing resolution order end-to-end (verified branch-by-branch against `ownership.py:493-622`), the three behavior-sensitive interactions (by-elimination, native gate, os-package gate) are each reasoned through and regression-pinned, the tampering boundary is double-gated, and the D-04 prohibition is grep-enforced from a verified 0 baseline. Residual risk is the pyright/import friction (caught by `make validate`, not silent) and two judgment edges (collision-unknown, ungated helper) that are fail-closed and cheap to make explicit.

## 16-06

### Summary

Makes version answer "what is on disk": one `_version_argv(tool, ownership)` helper (active path → declared `bin_dir` location → bare cmd) replaces both `[tool.cmd, "--version"]` literals (`installer/version_status.py:170`, `:222`); an `sdkman` branch in `resolve_status` reads the `current` symlink target name with no JVM and no subprocess; a `version_file` param reader (declared on the sdkman tool by plan 16-10) reads `~/.sdkman/var/version` from disk. The self-policing grep acceptance and the now double-pinned cross-plan `method` interface make this the tightest plan in the batch. All structural claims verified against source.

### Strengths

- **Diagnosis and consolidation gate verified.** `:170` (`resolve_github_release_status`) and `:222` (`_probed_version`) are the only two literals in the file; after the change the one survivor sits inside `_version_argv`'s fallback, exactly matching `grep -c 'tool.cmd, "--version"' → 1`.
- **Branch placement is correct.** `resolve_status` (`version_status.py:226-341`) runs installer → brew/cask/pnpm/uv → fallthrough; an sdkman owner today lands in the fallthrough and probes the sourced `sdkman-init.sh` (`registry.toml:1715,1724`). The new `if owner == "sdkman":` before the final fallthrough fixes precisely that. `VersionStatus` fields (`:127-135`) match the planned construction, and `latest=None, outdated=None, source="sdkman"` honestly claims no comparison (T-16-16 mitigated by `extract_observed_version` + the None-falling truths).
- **The round-1 MEDIUM (unpinned sdkman candidate `method`) is now genuinely closed on both sides.** 16-01 Task 1's behavior asserts "`method is not None` and `method.params["bin_dir"]` equals the declared bin_dir (pins the interface plan 16-06 reads)" and action (3) fixes "the iterated `method` itself, never None"; 16-06 Task 1's `test_sdkman_version_through_real_resolve_ownership` builds the record through the real `resolve_ownership` with the exact springbootcli registry shape (verified: `registry.toml:1778-1791`, `cmd="spring"`, `candidate="springboot"`, `bin_dir="~/.sdkman/candidates/springboot/current/bin"`). A hand-built record can no longer hide a `method=None` regression in either plan.
- **Round-1 LOWs addressed in executable content, not just ledger prose:** `Path(bin_dir).expanduser().is_dir()` tested directly with the symlink read only from `.parent` (no re-derived `current/"bin"` constant); `resolve_github_release_status` "ALWAYS builds its argv with `_version_argv(tool, ownership)`" with no own fallback literal, so the action and the grep gate cannot be read apart.
- **The `version_file` tri-state is a deliberate, specified distinction.** `False` (not declared) vs `None` (declared but unreadable/unparseable) makes "garbage file → `installed=None` WITHOUT subprocess fallback" testable — the right call, since a declared-but-broken file is a real signal, not "go probe."
- **Registry plumbing needs no schema change — verified.** The loader passes unknown method keys into `params` verbatim (`installer/model.py:550`), and `Method("sdkman", {...})` matches the positional dataclass (`model.py:189-192`), so 16-10's `version_file = "~/.sdkman/var/version"` on the sdkman tool's script method (`registry.toml:1719-1725`) lands where `_version_file` reads it. The cross-plan split (consumed here, declared in 16-10) is honest and stated in success_criteria.
- **Verify suites stay host-independent — checked, not assumed.** `tests/test_version_status.py` builds only synthetic tools with no method `bin_dir` (grep: only `managed_bin_dir=_MANAGED`), every probe fake ignores argv (no exact-argv assertions exist in the file), and there are no real-registry loads; `resolve_github_release_status` has no production caller outside version_status.py itself. The declared-location `(bin_dir/cmd).is_file()` scan therefore reads only tmp fixtures inside the planned tests, while gaining the intended production behavior (probe at the on-disk copy for PATH-absent tools).
- **The sdkman symlink read handles every named edge:** dangling `current` fails `is_dir()` (follows links), `current -> not-a-version` fails `extract_observed_version`, and `_OBSERVED_VERSION` (`installer/versions.py:29`) accepts both `4.1.0` and SDKMAN java's `21.0.4-tem` prerelease shape.
- **Standing constraints clean:** tmp fixtures only, zero sudo/pkexec/doas, no package installs (T-16-SC correctly accepted), English only.

### Concerns

- **LOW — two unnamed imports.** `os.readlink` (Task 1) needs `import os` — version_status.py imports none today (`:43-57`); `Literal[False]` in `_version_file`'s annotation needs `Literal` added to `from typing import cast`. Mechanical, gate-caught, but un-specified in a plan that is otherwise exact about signatures (`_probed_version`'s new signature, by contrast, is spelled out).
- **LOW (accepted deferral, restated) — `stale=False` for sdkman** slightly overclaims freshness on a no-comparison record. The ledger's rationale (the symlink was read this pass; matches the brew branch's `stale=False` when a mapping is read, `version_status.py:309/323`) is consistent with existing behavior; noting only because `stale` drives the UI `~` marker convention.
- **LOW — `_version_argv`'s ownership=None wording can be misread.** "With `ownership` None, skip the active-path step and `ownership.method`" — the `tool.methods` bin_dir scan still applies (the second sentence says so, and the behavior bullet "With `active_path=None` and a method whose `bin_dir/cmd` is a file…" confirms it), but the first sentence alone could be read as skipping all three ownership-derived steps. The existing direct callers (`tests/test_version_status.py:140-161` area, no bin_dir fixtures) are unaffected either way, so this is wording polish only.

### Suggestions

- Add `import os` and `Literal` to the named import changes in Task 1/Task 2 actions.
- Rephrase the ownership=None sentence to "skip only the active-path and `ownership.method` steps; the `tool.methods` bin_dir scan still runs."

### Risk Assessment

**LOW.** Small, well-ordered, self-policing via grep, every failure edge (dangling symlink, unparseable target, garbage `version_file`, PATH-absent tool) test-specified, and the one material cross-plan dependency (the sdkman candidate's `method`) is now pinned from both sides in executable content. The residual items are two import lines and a wording fix.

### Batch verdict (reviewer, before post-review fixes)

**Unresolved HIGH findings: 0** (for 16-05 and 16-06).

**Unresolved non-HIGH findings that still warrant a plan change (4, all one-line mechanical/judgment edits; none blocks execution since `make validate`/pyright and the named tests catch each):**
- 16-05: pyright-strict typing of `declared_manager_label`'s `OWNER_LABELS.get(owner)` (`Owner | str` key) + the `dataclasses.replace` / update.py-import additions un-named.
- 16-05: `also_installed_note` should gate on `owner="unknown"` in its own contract.
- 16-05: the script-tool/brew-cmd-collision → `unknown` behavior change is real, defensible, and un-pinned — state it as accepted.
- 16-06: `import os` + `Literal` imports un-named (plus the ownership=None wording rephrase).

**Round-1 findings now resolved (verified in executable plan content, not just ledger prose):** 16-05 MEDIUM `declared_manager_label` unmapped native kinds (Task 2 `.get()`-only lookups + `test_declared_manager_label_native_kind`); 16-05 LOW `off_policy` without a declared policy (tightened expression + `test_off_policy_requires_a_declared_policy`); 16-05 LOW missing left-behind-Cellar test (`test_undeclared_brew_cellar_left_behind_not_listed`); 16-06 MEDIUM unpinned sdkman candidate `method` (`test_sdkman_version_through_real_resolve_ownership` + 16-01 Task 1's own behavior/action pin); 16-06 LOW bin_dir re-derivation (direct `is_dir()` on the param); 16-06 LOW `resolve_github_release_status` wording vs grep gate (always-routes-through-`_version_argv`). Deferrals re-checked: 16-05's D-03 note-not-offer and unreadable-brew unknown-reason, and 16-06's `stale=False`, all carry sound locked-decision rationale (D-04/D-05; existing brew-branch precedent).

Both plans are implementation-ready; the four edits above are polish, not blockers.

---

## OpenCode Review (opencode-glm-5.2) — batches 3-5: 16-07..16-16

> Batch 3 reviewed 16-08 before 04aa62e; its MEDIUM is resolved there (see Post-review plan fixes).

Reviewer verified every load-bearing claim against the working tree at `4a3ef8c`. Wave-1 dependencies (16-02, 16-03) are planned but **not yet executed** (no `16-02-SUMMARY.md` / `16-03-SUMMARY.md` exist), so wave-2 plans were checked against both the current source and the dependency plans' specified end-state.

## 16-07

**Summary.** A data-correctness plan (D-09 audit of all seven `skill_pack` host lists with upstream citations) plus the D-15 host-presence filter (`HARNESS_PRESENCE`, `present_harnesses`, `by_harness` filtering in `perform_action`) and the D-13 label table. The mechanical half is precisely grounded in verified source; the audit half is network-dependent and correctly fail-closed. All five round-1 findings are visibly honored in executable plan content, and the checker-revision-1 pin-migration issue is handled concretely.

**Strengths**
- **Every source claim checked out.** superpowers has `requires = ["pi"]` (registry.toml:2890), `supported_harnesses = ["pi"]` (:2895), and a Pi-only `desc`; exactly seven `skill_pack` entries live in the cited 2774–3110 range (2783, 2836, 2891, 2932, 2978, 3025, 3073); the `# Verified` baseline is exactly 21 (re-counted by grep), making the revised "+7" gate satisfiable; `_parse_skill_operation` is at model.py:381 with the four call sites at exactly model.py:515-518, and `supported_harnesses` is already parsed at model.py:464-468 *before* those calls, so the signature plumb-in is mechanical as claimed.
- **The `perform_action` extension is genuinely non-breaking.** engine.py:87 calls `perform_action(tool, "install", ctx.runner)` positionally and tests/test_skill_lifecycle.py:270 passes positionally — keyword-only `home`/`which` defaults touch neither caller, exactly as the key_link asserts.
- **Round-1 dispositions are all in executable content, not just ledger prose.** L194's unsatisfiable `^# Verified .*skill` gate is replaced by a count gate over the verified baseline plus the (e) placement test; L195's ponytail ordering is fixed by action (b)'s "only AFTER (a)"; L196 is fixed by Task 2(a)'s "SKILL_HARNESS_LABELS does not exist before Task 3" plus Task 1's named `_parse_skill_operation(..., supported_harnesses)` signature; L197's citation rule and L66's `match == "gsd-core"` pin test are both in Task 2's action/acceptance.
- **The 16-02 pin migration (checker rev 1) is concrete and self-healing.** Both exact-tuple pins are named with the grep that finds them, rewritten as membership checks in Task 1 *before* Task 2 adds the breaking claude probes; and the verify command includes `tests/test_registry.py`, so a pin that landed outside the grepped files still fails verification loudly rather than silently.
- **Audit doctrine is fail-closed throughout**: "never fabricated," "keep the narrower verified set," host-only CLI listings never add a host without an upstream citation — the exact D-09 defect class is prohibited by name.
- **Cross-plan consumers line up**: 16-12-PLAN.md:34/91 consumes `SKILL_HARNESS_LABELS` with the truncation arithmetic already re-measured against `OWNER_LABELS` (ownership.py:965), and the Task 3 exhaustiveness pattern (`OWNER_LABELS` + test, ownership.py:1009) exists as cited.

**Concerns**
- **LOW — no stated fallback for total network failure.** Tasks 1–2 mandate live WebFetch/`gh api` fetches of 7+ upstream READMEs ("Live verification is required in Task 1"). The ambiguity rule ("keep the narrower verified set") covers ambiguous answers, not unreachable ones. An executor with no network should stop rather than guess — the prohibition ensures that — but the plan should say so, since `autonomous: true` invites an executor to "resolve" a stall.
- **LOW — `_guard_refusal`… (audit-outcome-dependent acceptance gate).** Task 2's acceptance requires a nonzero probe count for all five of ponytail/superpowers/softaworks/matt-pocock/opengsd. softaworks/matt-pocock/opengsd are structurally guaranteed (skills-lock/install-state vias), but ponytail's and superpowers' counts depend on what the audit keeps; if upstream drops every CLI-probeable host, the gate false-fails a correct execution. Likelihood is low (ponytail *is* a Codex plugin; 16-02 already migrates it to a codex probe), but the gate conflates "audit done" with "audit found probes."
- **LOW — `by_harness` "ordered by `SKILL_HARNESSES`" is ambiguous.** It is unstated whether the parser sorts the pairs or the registry author is trusted to order them; if neither, order is TOML insertion order. Cosmetic (instruction display order only), but one sentence would pin it.
- **LOW — `HARNESS_PRESENCE` seeds remain self-attested.** The revision requires an inline citation comment for factory-droid/gemini-cli, but no automated gate checks the citation exists (round 1's "asserted, not gated" is only half-addressed). Bounded by T-16-19: a wrong marker only shows one extra host's instructions, never a mutation.

**Suggestions**
- Add one sentence to the objective: "If an upstream fetch fails entirely, stop and report; never widen or keep a host list without its source" — making the network-failure behavior explicit.
- State that the parser sorts `by_harness` pairs by `SKILL_HARNESSES.index` (or that registry order is authoritative and load-time validated).
- Soften the nonzero-probe gate to the packs whose probe vias are structural, or phrase it as "nonzero for every pack whose audited list intersects a probeable via."

**Risk Assessment: LOW-MEDIUM.** The code mechanics (model field, parse validation, presence table, filtering, labels) are all verified against source with correct cross-plan pins and non-breaking signatures. Residual risk is confined to the audit half: live-fetch dependence and two acceptance gates that partially encode audit outcomes. Nothing touches an executable path — `by_harness` values are display-only under the existing skill_pack-never-executes doctrine, and the threat model's mitigations map to real mechanisms.

## 16-08

**Summary.** The D-21 guard-in-place write built on 16-03's corrected detection, with D-22 foreign-block exclusion and D-23's backup convention, by extracting `_create_backup`/`_path_hazard` from the proven 15.8 consolidation machinery. Every named primitive exists and behaves as claimed (all re-verified this cycle), all five round-1 findings are honored in executable content, and the checker-revision-1 `_REFUSE_UNRESOLVED` fix is coherent against `_expand`'s actual semantics. One new defect was found in the revised check order: the compound rule as specified swallows zsh-array lines, making `_REFUSE_ZSH_ARRAY` unreachable and Task 2's exact-constant test unpassable under the plan's own prescribed order.

**Strengths**
- **All primitives verified at the cited locations.** `path_export_guard` (shellrc.py:82-128, single-line `${PATH-}`/`${PATH:+:$PATH}` case guard, set-u safe); `consolidation_precondition` at shellrc.py:827-884 (read_first line range now corrected); `_Snapshot`/`_snapshot`/`_snapshot_matches` at :887-914 (identity-bound via `O_NOFOLLOW` + device/inode/bytes); `backup_precondition` at :917-958 (refuses differing bytes, accepts identical bytes+mode — exactly Task 3's re-run-safe case); the `O_WRONLY|O_CREAT|O_EXCL` + `chmod` backup block at :1075-1084 is where `_create_backup` is extracted from, and `grep -c O_EXCL` prints exactly 1 today (shellrc.py:1078), so the acceptance criterion genuinely forces one shared helper; `atomic_write_text(path, text, *, mode=None)` matches atomic.py:56-58.
- **The round-1 consolidated/stub-marker fix (L221, the plan's worst finding) is real and complete.** All four project markers start with `tools-installer` (shellrc.py:22-29: `path`, `source`, `consolidated shellrc`, `shellrc stub`), so the `startswith("tools-installer")` exclusion covers the whole family; `_managed_line_indices` (rcclean.py:47-58) stays un-widened so `path`/`source` blocks stay fully skipped while consolidated-block lines get `block_owner=None` and ordinary rules — with `test_consolidated_shellrc_block_is_not_foreign` pinning it. The behavior is semantically right too: `~/.myshellrc` is this project's own file, so guarding a foreign-copied writer line inside it is a legitimate D-21 target.
- **The guardability derivation (L222) is now specified and feasible.** 16-03's `_PathLine` carries the raw `text`, so `_guard_refusal`'s re-parse (compound → zsh array → unresolved → ordered `:`-split) has its derivation source; the ordered split on `_PATH_EXPORT`'s captured value after `_unquote` correctly yields two-segment prepend vs append vs multi (hand-traced against rcclean.py:16, 20-23).
- **The `_REFUSE_UNRESOLVED` reachability fix (checker rev 1) is correct.** `_expand` returns None on an unknown var (rcclean.py:26-44), so `$FOO/bin:$PATH` genuinely yields no record and `$FOO/bin:$HOME/.local/bin:$PATH` yields one with `unresolved=True` via the resolvable managed segment — the test input is exactly right, and checking `unresolved` before the ordered split prevents the multi rule from claiming it.
- **The import-cycle claim is verified**: rcclean.py imports stdlib only (rcclean.py:9-11), so `from installer.rcclean import PathWriterLine` in shellrc is acyclic.
- **Idempotency is structural**: `path_export_guard` output is a `case` line, which 16-03's generator skips, so a guarded file re-scans to zero records — the "no writers and no write" edge holds by construction.
- **Write-path guardrails inherit the proven 15.8 discipline**: hazard check before any read (matching `consolidation_precondition`'s symlink/FIFO rationale, shellrc.py:840-864), per-line text re-verification plus post-backup `_snapshot_matches` (the race pattern proven by tests/test_shellrc.py:2051-2070's `_inject_edit_on_first_write` and the `_snapshot` monkeypatch at :2224), byte-exact refusal, backup-removal rollback, and every refusal test asserting `read_bytes()` identity. The CRLF fix (rstrip `\r` both sides; records built via `path_writer_lines` on CRLF text) is correctly specified.
- **Standing constraints honored**: tmp_path only, real-shell checks on tmp files with the minimal-env subprocess precedent (tests/test_prune_tmp_linux_sh.py:31-48, skipif-bash), zero sudo, English only. T-16-25's directory-provenance rule is real — `record.directory` originates in the managed-dir set, never the foreign line's text.
- **Cross-plan signatures line up**: 16-11's `guard_file`/`PathGuardOutcome`/`PathWriterLine` consumption (16-11-PLAN.md:88-113) matches this plan's artifacts verbatim, and `unguarded_path_writers`'s unchanged signature keeps 16-04's seam intact.

**Concerns**
- **MEDIUM — the revised `_guard_refusal` check order contradicts its own Task 2 test.** The final order is prescribed as "compound → zsh array → unresolved → append / multi-directory / guardable" (Task 2 action), with the compound check implemented as `not line.simple` (Task 1 rule 1). But 16-03 defines a zsh `path=(...)` line as `simple=False` — `simple` requires the single segment to have matched `_PATH_EXPORT`, "not `_ZSH_PATH_ARRAY`" (16-03 Task 3 action, pinned by `test_zsh_array_line_is_not_a_strip_candidate`). So a pure `path=("$HOME/.local/bin" $path)` line trips the compound rule first, gets `_REFUSE_COMPOUND` ("shares its line with other commands or a comment" — factually wrong for that line), and `_REFUSE_ZSH_ARRAY` is unreachable. Task 2's acceptance ("Each of the five refusal shapes has a test asserting its exact constant") cannot pass under the plan's stated order. TDD will catch it at execution time, but the plan text prescribes an order its own test contradicts, inviting divergent "fixes" (e.g. special-casing `simple` for arrays, which would collide with 16-03's strip-candidate pin). Fix is one line: check `_ZSH_PATH_ARRAY` **before** `not line.simple`.
- **LOW — nested foreign marked blocks fail open.** `_foreign_block_owners` "mirrors this depth loop" — `_managed_line_indices` (rcclean.py:47-58) keeps a single open-block pointer, so with nested `# >>> a >>>` / `# >>> b >>>` / `# <<< b <<<` / `# <<< a <<<`, lines between the outer begin and the inner begin lose their owner and are judged by ordinary rules — a line inside foreign block `a` could be rewritten, violating D-22's "never" prohibition. Rare in practice (all cited real blocks — kitty-setup, conda — are single-level) and recoverable via the backup, but the plan already handles the analogous unterminated case conservatively (to EOF); the same conservatism (a stack of open names, or "any unmatched begin blocks everything after it") should apply here.
- **LOW — `guard_path_writers` doesn't specify handling of records whose `rc_path` differs from the argument.** Step 1 implies filtering ("no guardable lines *for this path*"), but whether foreign-path records are silently ignored or an error is unstated. 16-11 passes per-file lists so either reading works; one sentence would remove the ambiguity.
- **LOW — multi-guard-per-file friction is unacknowledged.** After one successful guard leaves `.tools-installer.old` holding the pre-guard original, a *later* new guardable line in the same file is refused forever by `backup_precondition` ("already holds a different original") until the user manually removes the backup. This is doctrine-consistent (fail-closed, never overwrite a recovery artifact — shellrc.py:947-951) and a repeat run with no new writers correctly returns `nothing` before the backup check, but 16-11's Doctor flow will surface this refusal with no plan-level note explaining it.
- **LOW — `_path_hazard` wording is consolidation-flavored.** The verbatim refusal text says "a stub write would follow it" (shellrc.py:840-845); reused verbatim in a guard refusal, the user is told a "stub write" is happening. The plan permits wrapping with a prefix; the executor should re-prefix for the guard context so the pinned substrings (`"symlink"`, the path — tests/test_shellrc.py:1690-1747) survive while the operation noun is corrected.

**Suggestions**
- Reorder `_guard_refusal`: `_ZSH_PATH_ARRAY` match **first**, then `not line.simple` (compound), then `unresolved`, then the ordered split. Update the Task 1 rule list and the Task 2 "final order" sentence to match.
- Make `_foreign_block_owners` track a list of open block names (end pops only a matching name; a line's owner is the innermost open frame), or state the conservative rule that any still-unmatched begin blocks all following lines.
- State that `guard_path_writers` ignores records whose `rc_path` differs from the argument (and optionally assert it in a test).
- Add one sentence to the objective or 16-11 handoff noting the second-guard-per-file backup refusal is expected and user-resolvable ("move or remove the backup").

**Risk Assessment: MEDIUM.** The write path fails closed on every named hazard, never deletes a line, writes a byte-exact mode-preserving backup first, and inherits a proven, tested discipline — no data-loss path is visible in the design, and the threat model maps to mechanisms that exist. The MEDIUM rating is driven by one executable-content defect (the compound/zsh-array order contradiction, which guarantees a mid-execution test failure and risks a wrong divergent fix) plus the D-22 nested-block edge; both are one-line plan fixes.

### Batch verdict (reviewer, before post-review fixes)

**Unresolved HIGH findings: 0.** Neither plan violates the standing constraints (no real-host shell-config mutation — all tests tmp_path with the host-safety rule stated in both objectives; zero sudo/pkexec/doas; English only).

**Unresolved non-HIGH findings that still need a plan change: 1 (+2 optional)**
- **16-08, MEDIUM**: `_guard_refusal` check order — compound (`not line.simple`) placed before the zsh-array check makes `_REFUSE_ZSH_ARRAY` unreachable and Task 2's exact-constant acceptance unpassable as written. Requires the one-line reorder.
- *Optional*: 16-08, LOW — nested foreign marked blocks fail open in `_foreign_block_owners` (D-22 edge); 16-08, LOW — `guard_path_writers` semantics for foreign-path records unstated.
- *Optional (16-07)*: network-failure fallback sentence; `by_harness` ordering responsibility; probe-count gate phrasing. None block execution.

**Round-1 findings now resolved (verified in executable plan content, not just ledger prose):**
- **16-07**: L194 (unsatisfiable grep gate → count gate over the verified 21 baseline + placement test), L195 (ponytail probes sequenced after the audit), L196 (labels sequencing + `_parse_skill_operation` signature named with its four call sites at model.py:515-518), L197 (presence-seed citation rule), L66 (`gsd-core` match pinned by a registry test). All five confirmed against source.
- **16-08**: L221 (consolidated/stub markers excluded via `startswith("tools-installer")`, covering all four markers at shellrc.py:22-29, with a named test), L222 (guardability derivation specified as a re-parse of the raw line), L223 (CRLF rstrip on both sides, records built via `path_writer_lines`), L224 (verbatim-wording/wrapping requirement keyed to the pinned substrings at tests/test_shellrc.py:1690-1747), L213 (read_first range corrected to :827-884). All five confirmed against source.
- **Checker revision 1**: 16-07's 16-02 pin migration (concrete grep + membership rewrite before the break); 16-08's `_REFUSE_UNRESOLVED` reachability (`_PathLine.unresolved` flag, correct test input) — the latter fix is itself the source of the new check-order defect flagged above, since the revised "final order" sentence re-commits compound-before-zsh.

All four plans were checked against the current tree (HEAD `3ac3b57`) and against the wave-1/2 plans they depend on (16-01..16-08, not yet executed). Round-1 findings are from `16-REVIEWS.md` @ `b992d0a`. Vendor claims for 16-10 were re-fetched live during this review.

## 16-09

**Summary:** Adds a `dangling_shim` predicate in status.py, a `ManagerOwnership.broken` field computed inside `resolve_ownership` from evidence already in hand, and `install_tool(..., repair=True)` that only lifts the presence short-circuit. Every code-level claim verified against source; both round-1 findings are dispositioned in executable content (one accepted with exact line numbers, one deferred with sound rationale).

**Strengths:**
- All asserted seams exist exactly as cited: `ManagerOwnership` (installer/ownership.py:296-308), `active_path`/`dirs`/`inventory` all in scope after ownership.py:508-509, `owner_dirs`' `"pnpm"` entry from `PNPM_HOME`/`_PNPM_DEFAULTS` (ownership.py:446-451), the resolve-both-sides rule to mirror in `attribute_path` (ownership.py:463-479), the pre-existing `is_installed` import (ownership.py:73), the engine short-circuit (installer/engine.py:127-128), and the existing `ALREADY_INSTALLED` test (tests/test_engine.py:643).
- Round-1 L247 (unnamed `_native_owner`/`_os_package_owner` return points) is now genuinely executable: Task 1's action names ownership.py:712 and :763 (verified: those are exactly the two `_owned(...)` builds) and the return sites at :535-537/:565 (verified), instructs `broken` to be applied at the `resolve_ownership` return sites (folded into 16-05's `dataclasses.replace`), and adds an os-package-wins test asserting the field. Not just ledger prose.
- Round-1 L248 (redundant re-resolve) deferred with verified rationale — `attribute_path` does exactly the same double resolve with the same OSError fallback (ownership.py:466-477), so the mirror is deliberate.
- Fail-closed direction pinned: `pnpm_globals is None` → not broken, consistent with the module's "claim only on proof" doctrine (ownership.py:22-31) and T-16-27; the five-case adjacency matrix covers healthy/unknown/outside-dir/not-on-PATH/not-node.
- Repair is the normal ladder: the one-line `if is_installed(tool) and not repair:` means checksums, smoke checks, bin_dir wiring, and post_install dispatch (engine.py:136-182) all run as on a fresh install — no bespoke re-link, mitigating T-16-26. `is_installed`'s signature stays untouched (status.py:18), honoring RESEARCH Pitfall 5.
- Wave ordering is correct: 16-05 (adds `off_policy` as the last `ManagerOwnership` field, verified in 16-05-PLAN.md Task 2) lands in Wave 2 before this plan appends `broken` after it; both default `False`, so no constructor breakage.

**Concerns:**
- **LOW:** `dangling_shim` collects `npm_pkg` from *all* `tool.methods`, not platform-applicable ones (consistent with `is_installed`'s own union-over-all-methods rule, status.py:42-56, so this is house style). Edge: a host where `PNPM_HOME` is misconfigured to a shared dir (e.g. `~/.local/bin`, which `owner_dirs` otherwise attributes to `uv`, ownership.py:452-453) could read a uv-managed binary of a node-declared tool as `broken`. Fail direction is a repair offer through the normal ladder, not destructive — acceptable, worth one line in the docstring.
- **LOW:** 16-09 and 16-05 both wrap the same two return sites with `dataclasses.replace`; the "folded into 16-05's replace" instruction is coherent only if the executor reads the post-16-05 tree. The read_first says to, so this is a note, not a defect.
- **LOW:** the docstring contract "repair is only ever set for a tool the user explicitly selected" is enforced nowhere in `engine.py` itself — it holds only via 16-13's composition. D-20-consistent as designed; just don't mistake the docstring for a guard.

**Suggestions:** Add the PNPM_HOME-collision caveat as one docstring line in `dangling_shim`; optionally restrict package collection to `resolve_methods(tool, platform)` if a platform edge ever surfaces.

**Risk Assessment:** LOW. Verified end-to-end; verdict computed from data `resolve_ownership` already holds; repair has a single normal-path entry point; both round-1 findings properly dispositioned.

## 16-10

**Summary:** Declares kitty's real Linux method (vendor installer script, `launch=n`, `bin_dir = ~/.local/kitty.app/bin`), audits the five location-less own-installer script methods, and adds sdkman's `version_file`. Mechanism, ladder, detection, and ownership chain all verified against source, and the vendor claims were re-verified live during this review. Both round-1 findings are addressed in executable content.

**Strengths:**
- Vendor claims re-fetched live (2026-10-10, sw.kovidgoyal.net/kitty/binary/): installer URL `https://sw.kovidgoyal.net/kitty/installer.sh`, Linux root `~/.local/kitty.app` ("The installer only touches files in that directory"), and `launch=n` documented verbatim ("You can tell the installer not to launch kitty after installing it with launch=n"). The plan's `| sh -s -- launch=n` is the stdin-reading equivalent of the vendor's `sh /dev/stdin launch=n`. T-16-30's mitigation is real.
- Ladder claims verified: `_RANK` script=10 vs native=30 (resolve.py:12-28); `_applies` accepts script after the os/arch filter (resolve.py:38-64) and skips native kinds on immutable hosts (resolve.py:75-76); Platform field order os/arch/immutable/has_brew (platform.py:20-28). So `resolve_methods(kitty, Platform("fedora","amd64",True,True))` → `['script']` is arithmetically true: the script's `os` includes fedora, dnf/apt/pacman are immutable-skipped, cask is macOS-gated.
- Round-1 L268 (MEDIUM, stale self-contradicting verification block) is properly fixed: the current registry really does say "kitty genuinely has NO applicable method on immutable Bazzite" (registry.toml:2502) inside the 2494-2510 paragraph; Task 1 rewrites it, keeps the still-true `.txz`/`tar -xzf` limitation, and adds grep acceptance gates (`grep -c 'genuinely has NO applicable method'` → 0, `txz` ≥ 1). Round-1 L269 is fixed by naming `no bin_dir` as the load-bearing contract in the test docstring and each comment.
- Executor change verified minimal and safe: `_script` (executors.py:354-362) builds `invoke` from prefix + quoted shell; appending `-s -- <quoted args>` composes correctly with the env prefix (`KEY=val sh -s -- launch=n` is valid sh per `_env_prefix`'s own docstring, executors.py:335-342); no-args pipeline is byte-identical by construction and regression-tested on the uv row. Injection defense is dual-layer (load-time regex at the model.py:609 validation neighborhood + `shlex.quote`), and `launch=n` fullmatches while `launch=n; rm -rf ~` is rejected by test.
- Detection/ownership chain holds: the command-file bin_dir rule (status.py:46-56) reads kitty installed at `~/.local/kitty.app/bin/kitty`; `script ∈ _INSTALLER_KINDS` (ownership.py:148) feeds 16-01's own-installer proof; adding `bin_dir` feeds `collect_bin_dirs` with the 15.8 case-guarded managed block preventing duplicates.
- Cross-plan split is honest: 16-06 consumes `version_file` (16-06-PLAN.md:23, 102) and 16-10 declares it on the sdkman script method; params pass through the loader verbatim so no schema change is needed. Wave ordering (16-10 in W3 after 16-06 in W2) resolves the interim "sdkman still reads no version" window.

**Concerns:**
- **LOW:** The vendor documents the `~/.local/bin/kitty` symlink as a *manual* desktop-integration step — the installer script does not create it. After install, kitty is reachable only through the managed PATH block. The must_haves cover the wiring, but the `# Verified` comment should state this so a future reader doesn't expect `which kitty` to succeed in a pre-existing shell.
- **LOW (bookkeeping):** the prohibitions ledger entry "Never launch a GUI application…" carries `status: unresolved` although T-16-30 mitigates it (declared `launch=n`, pinned by the executor test). The ledger contradicts the plan body's own mitigation.
- **LOW:** "Place it FIRST among kitty's methods" is cosmetic — `resolve_methods` sorts by `_RANK` (resolve.py:83), so declaration order is not load-bearing. The plan elsewhere acknowledges the ladder doctrine; no defect, just don't let the executor believe ordering matters.

**Suggestions:** One sentence in the kitty `# Verified` comment about the manual-symlink/managed-PATH consequence; flip the prohibition ledger row to mitigated or drop the row.

**Risk Assessment:** LOW. All claims verified including the live vendor fetch; the round-1 registry-hygiene gap is closed with grep gates.

## 16-11

**Summary:** Wires the guard-in-place action into Doctor's apply step with per-file confirmation modals, one shared composition-time scan, record-aware guidance, a post-fix fresh re-scan, and deletion of the two helpers that become dead. All three round-1 findings are fixed in executable content; the checker-revision deletion is well-staged. This is the largest and most cross-wave-coupled plan of the four.

**Strengths:**
- Round-1 L288 (MEDIUM, double composition scan) is genuinely fixed: one `path_writer_lines_for(report)` call at the composition site (verified to run inside `UnifiedApp.__init__`, wizard_app.py:2385-2394 today, so the one-call counting test is feasible), `duplicate_writers=group_writer_lines(writer_lines)` derived from the same list, plus a counting fake asserting exactly one call before any key press. The claim "every rc file is read once at composition, not twice" is now enforced by test, not just asserted.
- Round-1 L289 (fix-fail ordering) is specified: the guard chain runs whether or not the fix set `self.error`, the fresh re-scan keeps indices correct, the error renders first. Round-1 L290 (unused import) is handled with the app.py:36 import drop (verified today: `from installer.rcclean import find_duplicate_path_lines, scan_rc_path_writers, strip_lines`) and a grep gate; `make validate`'s ruff F401 would catch a miss anyway.
- The checker-revision deletion is correctly staged: Task 1 leaves `scan_rc_path_writers`/`unguarded_path_writers` in place so the tree stays green between tasks; Task 2 deletes both (by then: `scan_rc_path_writers` has no production caller after app.py:318's call disappears, and `unguarded_path_writers` is reachable only through it — verified against the current callers), migrates the tests with unchanged assertions (equivalence holds by 16-08's construction: `unguarded_path_writers` is defined there as a thin grouping over `path_writer_lines`), and moves the docstring rationale onto the survivors. The mid-task green-tree reasoning is stated.
- Cross-plan signatures consume 16-08's artifacts verbatim (`PathWriterLine(rc_path, index, text, directory, guardable, refusal, block_owner)`, `PathGuardOutcome("guarded"|"refused"|"nothing", reason)`, `guard_path_writers` with byte-exact re-verify — verified in 16-08-PLAN.md:110-128), and `path_export_guard` exists for the modal's after-text (shellrc.py:82).
- The post-fix fresh re-scan remains the best design decision and is pinned by the index-3 vs index-7 test; the `rescan_writer_lines=None` fallback keeps simpler tests working. `run_live` (ui_common.py:42-58) catches `OSError`/`CommandError`/`ShellrcRefusal`, so the Task 3 raise-test's "reported as refused via run_live" works as described.
- Guidance changes are grounded: today's "adds it unconditionally" wording verified at guidance.py:102/:105 and the `unguarded_path_writers` docstring reference at guidance.py:64; the CLI route stays report-only via the rebuilt `duplicate_path_writers` (app.py:308-318, :374 today).
- Standing constraints honored: tmp_path rc files, injected `guard_file`/scanner fakes, `make doctor` read-only, zero sudo, English only.

**Concerns:**
- **LOW:** The acceptance gate `grep -rnwE 'unguarded_path_writers|scan_rc_path_writers' installer/ tests/ setup.py` does **not** catch test *function names* embedding the helper names (e.g. `test_unguarded_path_writers_…`), because `_` is a word character for `grep -w`. The prose only claims comments/docstrings are covered, so the gate matches its claim — but 16-03 will have added several such tests (16-11's own read_first says so), and Task 2 says "keeping each assertion unchanged" without saying rename them. A test suite with names referencing deleted helpers is confusing, not broken.
- **LOW (inherent):** the plan compiles against the *landed* state of three not-yet-executed waves (16-03's scanner revisions, 16-04's public seam + route tests it retargets, 16-08's dataclasses and write). Every signature I could check matches the dependent plans' declarations, but any drift in those landings shifts this plan's line anchors and retarget points. The wave gating (16-11 blocked on 16-04+16-08) is the right mitigation.

**Suggestions:** Either rename the migrated tests off the deleted helper names in Task 2, or state that names may keep the historical prefix; one sentence either way.

**Risk Assessment:** MEDIUM — not for design defects (I found none; the round-1 MEDIUM is fixed) but for execution complexity: TUI pilot tests over a modal chain, retargeting another plan's tests, and a three-wave dependency chain, all in one plan.

## 16-12

**Summary:** Persists per-harness skill-pack status under the existing version-cache envelope, refreshes once per launch in a dedicated worker group, and renders stale-then-fresh Inst cells, truncated multi-host Owner cells, and detail-pane host lists. Both round-1 MEDIUM concurrency/IO findings and the checker-revision blocker are fixed in executable content; the `_skills_pass_lock` revision is sound under a lock-order analysis.

**Strengths:**
- Round-1 L310 (lazy seed on the render path) is fixed in executable content: `seed_skills_from_cache()` is called once at composition in setup.py right after `VersionRefreshService(...)` (verified construction site at setup.py:890-897), `skill_status_of` is an IO-free unlocked single-dict read modeled on `ownership_of` (version_status.py:424-443), and the acceptance greps enforce it (`seed_skills_from_cache` absent from catalog_tui.py; no `load_` call and no `self._lock` in `skill_status_of`'s body).
- Round-1 L311 (missing epoch) is fixed by porting the existing pattern: `started_epoch` capture + under-lock discard (the version pass's own mechanism, verified at version_status.py:545/:591-615), `SkillStatusRefreshed(generation, epoch)` mirroring `VersionStatusRefreshed` (catalog_tui.py:117), handler discard on epoch mismatch mirroring `on_version_status_refreshed`, and `test_skill_pass_superseded_by_invalidate_stores_nothing`. Round-1 L312 is fixed: `invalidate` marks every held entry `stale=True` under its existing lock (version_status.py:445-452), with a test.
- The checker-revision blocker (tier-slice probe probing nothing on the default launch path) is verified real and properly fixed: `BASE_VIEW = VIEW_ORDER[0]` and VIEWS[0].name == "system" (ui_common.py:115-125, 187-192), `Tier.SYSTEM` is the first member (enums.py:23-28), and screens are built tier-filtered with `catalog=list(tools)` full (wizard_app.py:2347-2352). The worker now calls `refresh_skills(self._catalog)` (grep-gated), `refresh_skills` returns early on a pack-less input without storing/persisting/flagging, and landed passes merge `{**current, **fresh}` — plus both pinning tests, including the System-view-first pilot.
- The `_skills_pass_lock` design passes a lock-order analysis: the only nesting is pass_lock → `_lock` (store/persist); `invalidate` and `seed_skills_from_cache` take only `_lock`; the probe runs outside `_lock` while holding pass_lock, so the superseded-pass test calling `invalidate` from inside the probe cannot deadlock — and the plan explicitly forbids `invalidate` from taking pass_lock. It also fixes the round-1-deferred `~`-stuck second-screen edge better than the deferred disposition required (wait-then-return-landed instead of early-return-stale).
- Cache mechanics mirror verified patterns: `save_version_cache(..., managers=None)` preserve-by-default (version_cache.py:154-175) is the exact shape for the `skills` kwarg; `invalidate`'s save (version_status.py:450-451) preserves the new key automatically; both the version pass and the skill pass persist under `self._lock` (version_status.py:590-623), so the read-modify-write of the shared envelope is serialized in-process — no lost-update between the two workers.
- `run_query` timeouts surface as `CommandError(RuntimeError)` (run.py:32, :329), which 16-02's catch list covers, so the "hung harness CLI becomes unknown" claim holds; `exit_on_error=False` plus `_skills_probed` staying False on a failed pass self-heals on the next view entry.
- D-13 arithmetic verified: widest `OWNER_LABELS` value is "installer artifact" = 18 (ownership.py:965-993); `_OWNER_CELL_MAX` derived (not hardcoded) with a pinning test; `OWNER_LABELS` is not yet imported in catalog_tui.py:23, and the plan says to add it. Standing constraints honored: offline fakes, read-only harness queries, no rc mutation, no sudo.

**Concerns:**
- **LOW:** The Inst truth table leaves one cell under-specified: hosts `{claude: absent, pi: unknown}` — no host present, not *every* probed host absent — falls to `None` → dim `?` by the `_present` spec ("False when all probed hosts are absent"), but no behavior test names this mixed case. Honest display, unpinned edge.
- **LOW:** The worker wraps the call in `run_live` (which swallows `OSError`/`CommandError`/`ShellrcRefusal` into `(None, msg)`, ui_common.py:42-58), but the plan never says what the worker does with a `(None, msg)` result — the error message is dropped silently (no status-line surfacing) and the message still posts. Only reachable via a bug (per-probe failures are caught inside `inspect_skill_packs`), but one sentence should say "post the message anyway; entries stay stale-marked; the next entry retries."
- **LOW:** If `refresh_skills` ever raises outside run_live's catch list, `skill_refreshing` sticks `True` and pack cells carry `~` until a later view entry starts a fresh worker. Degraded-but-honest state on a bug path; acceptable.

**Suggestions:** Add one behavior test for the mixed absent/unknown host map; add the one-sentence run_live-error handling rule for the worker.

**Risk Assessment:** MEDIUM — down from round 1's two real concurrency gaps (both now closed with tests), but this remains the most concurrency-sensitive plan in the batch: two lock domains, an epoch gate, a blocking join, and three screens sharing one service, with much of its correctness resting on tests the executor must get exactly right.

### Batch verdict (reviewer, before post-review fixes)

**Unresolved HIGH findings: 0.**

**Unresolved non-HIGH findings that still warrant a plan change: 3** (all LOW, each one test or one sentence):
- 16-12 — mixed absent/unknown host map not pinned by a behavior test.
- 16-12 — worker's handling of a `run_live` error result is unspecified (message dropped silently).
- 16-11 — the word-match grep gate cannot catch migrated test *names* that embed the deleted helper names; state the rename-or-keep rule explicitly.

**Advisories (no plan change required):** 16-09 PNPM_HOME-collision edge (one docstring line); 16-10 manual-symlink note in the `# Verified` comment and the `status: unresolved` prohibition-ledger row contradicting T-16-30's mitigation.

**Round-1 findings now resolved:** 16-09 L247 (return points named, executable); 16-10 L268 (stale paragraph rewrite + grep gates); 16-10 L269 (`no bin_dir` named as contract); 16-11 L288 (single composition scan, counting test); 16-11 L289 (fix-fail ordering stated); 16-11 L290 (import cleanup + gate); 16-12 L310 (composition-time seeding, IO-free reader); 16-12 L311 (epoch-gated pass + message epoch + discard test); 16-12 L312 (invalidate marks stale + test). **Deferred dispositions that stand:** 16-09 L248 (deliberate mirror of `attribute_path`); 16-12 L313 (per-instance `@work` exclusivity — sound, and the `_skills_pass_lock` revision supersedes it with a stronger in-service guard).

**Standing constraints:** all four plans honor them — tests touch only tmp/fixture paths with injected fakes, host checks are read-only (`ls`, `cat`, `brew list`), zero sudo/pkexec/doas anywhere, English throughout.

Not checked: execution of any plan (waves 1-2 unexecuted, so all cross-wave line anchors are verified against plan text, not landed code); 16-07's `SKILL_HARNESS_LABELS` label set was taken from the round-1 verification rather than re-derived. Main residual risk: any drift in the 16-01..16-08 landings shifts the anchors these plans compile against — mitigated by wave gating, not eliminated.

All findings below were verified against the working tree at `04aa62e` (post-`b992d0a` revisions `cee9581`, `1cf1f8d`, `ff349df`, plus three later doc commits). Every file, line, and mechanism claim I checked is cited from the actual source.

---

## 16-13

**Summary.** A well-researched plan that fixes the silent "Install 0 tools" defect (D-17), widens post_install's one-shot trigger by exactly the D-20 explicit-selection case, and routes broken tools into the normal install ladder — all without touching `deps.py` or `session.py`, achieved by composing at the ExecuteScreen layer. Line citations are accurate, the typing analysis (`Callable[..., InstallOutcome]` vs `SensitiveInstall`) is correct, and all four round-1 ledger dispositions are visible in executable content.

**Strengths.**
- Root-cause avoidance verified: `installer/deps.py:111` (`satisfied_by_install`) is indeed where installed tools vanish, and the wrapped `is_installed=lambda t: self._inputs.installed(t) and t.id not in self._repair_ids` sidesteps it cleanly — `resolve_dependencies` (deps.py:85, :111) treats a broken tool as not-installed, so it lands in `resolved.order` deps-first with zero resolver edits.
- Verified the install-vs-update post_install partition is sound: `grep run_post_install installer/update.py` returns nothing — the update path never dispatches post_install actions, so including `_to_update` members in `_reapply` cannot double-dispatch.
- Task 2's append-after-summarize is protected on all fronts I traced: `summarize` (session.py:191) buckets only install outcomes; `UnifiedApp.on_install_run_finished` (wizard_app.py:2786-2796) reads `message.summary` and `_install_state_changed` from `incoming.installed` only; `render_post_install_handoff` (render.py:155-157) filters on `post_install_handoff`, not status, so an `ALREADY_INSTALLED` reapply outcome renders its handoff correctly.
- Ledger items confirmed in source: `registry.toml` has exactly one `post_install =` declaration and it is on `oh-my-zsh` (the round-1 relabel is correct); `attributed_install`'s signature (execute_screen.py:199-235) and `with_sensitive_confirm`'s `bound` (session.py:83-100) compose correctly with a `**kwargs`-forwarding `_with_repair`; the cancel contract matches `_run_updates`'s existing gate (execute_screen.py:592-593).
- `install_tool`'s current post_install try/except (engine.py:166-174) is exactly what `_dispatch_post_install` extraction would factor; `grep -c 'run_post_install('` prints 1 today (engine.py:169).
- D-18/16-09 dependency is real: 16-09 adds both `ManagerOwnership.broken` (ownership.py) and `install_tool(..., repair=False)` changing the short-circuit to `if is_installed(tool) and not repair`, and pins that a repaired tool dispatches post_install exactly as a fresh install — so excluding `_repair` ids from `_reapply` is correct, not just "simplest".

**Concerns.**
- **MEDIUM — Task 1/Task 2 progress-state collision.** Task 1 adds a third progress row kind (`✓ {id} [already current]`) kept "out of `_progress`'s install/update rows", but Task 2 appends reapply outcomes to `outcomes`, and `on_install_run_finished` (execute_screen.py:811-814) sets `self._progress[outcome.tool_id] = "done"` for every outcome in `message.outcomes` — including the appended `ALREADY_INSTALLED` reapply outcomes. If the implementer renders the "already current" row from `_progress.get(id, ...)`, a current tool's row flips to `● done` when the run finishes; if rendered unconditionally from `self._current`, the stray "done" entry is harmless dead state. The plan never reconciles the two tasks on this; one sentence would close it.
- LOW — read_first cites `_PROGRESS_GLYPH` at `:905-940`, but it is defined at execute_screen.py:85-90 (`_preflight_prompt` :911 and `_refresh_progress` :921 are correctly in range).
- LOW — The deferred ledger item says the unattended path "keeps the silent zero-install behavior", but Task 1's plain-fallback guard ("Nothing to do. esc cancel") changes the unattended preflight text too (ExecuteScreen renders the head pre-start; `unattended` auto-starts at :447-448). Behavior is strictly better and consistent with the truth's "nothing new is dispatched"; only the ledger wording is stale.
- LOW — A selected broken tool whose repair FAILS gets neither post_install dispatch nor reapply (excluded from `_reapply`, install failed) — reasonable, but unstated.
- LOW — The reapply loop's position relative to `wire_path`/`verify` (execute_screen.py:548-561) is not pinned; "after `_run_updates`" (:547) is the natural reading and harmless either way.

**Suggestions.**
- Add one sentence to Task 2: current-tool progress rows render from `self._current` unconditionally (or `on_install_run_finished` skips reapply outcomes), so the appended outcomes cannot repaint them.
- State that a failed repair excludes the tool from post_install re-apply (mirrors the fresh-install failure path).
- Fix the `_PROGRESS_GLYPH` line citation.

**Risk Assessment.** **LOW-MEDIUM.** The mechanism design is verified sound against source; the one MEDIUM is an intra-plan paint-path ambiguity that a careful executor will likely resolve correctly anyway (the plan's own words "Keep `self._current` out of `_progress`'s install/update rows" point at the right implementation).

---

## 16-14

**Summary.** A tight, well-scoped plan: a pure `unavailable_reason` mirroring `_applies`' clause order, a parity test tying it to `platform_could_support` for every registry tool on four platforms, honest type-widening driven by a real `Mapping` invariance problem, and one deliberate test change. Every source claim I checked is accurate.

**Strengths.**
- All citations verified: `resolve.py:38-77` `_applies` clause order (os → arch → min_os_version → kind) is exactly as described; `platform_could_support` (resolve.py:86-110) uses `replace(platform, has_brew=True)`, and the plan's classifier uses the same replacement, so the parity invariant is structural, not accidental.
- The invariance claim is genuine: `selection.py:94` today annotates `unavailable: Mapping[str, bool] | None`, `Mapping` is invariant in its value type, and the only use is truthiness (`blocked.get(rec_id, False)`, selection.py:117) — so `Mapping[str, object] | None` is the honest widening, exactly as the ledger says.
- `setup.py`'s comprehension verified at `unavailable = {tool.id: not platform_could_support(tool, platform) for tool in tools}` (setup.py:~783), and `wizard_app.py:2290` annotates `Mapping[str, bool] | None` — both replacement sites are real.
- The test change is necessary and correctly scoped: `tests/test_setup.py` `test_build_app_hands_unavailable_from_platform_could_support` really asserts `unavailable["apt-upgrade"] is True` today; the macOS-vs-apt case (`os=("debian",)` on macos) yields short `macos not supported` under the planned classifier — consistent.
- Truthiness contract preserved: `UnavailableReason` is a 2-field NamedTuple (truthy), and all other consumers I grepped (`_adapter`'s `selectable` :342, `action_accept_recommends` :717, `on_tool_browser_accepted` :853) only test truthiness — the plan's isinstance rendering covers the two display sites.
- Zero-methods edge, mixed-reason determinism ("category shared by all methods, or `mixed`"), and the "return None exactly when `platform_could_support` is True" invariant with a four-platform × full-registry parity test make reason/availability drift a test-enforced impossibility.

**Concerns.**
- LOW — a tool whose only method is `rpm_ostree` would get short reason `immutable host` on a **mutable** host — factually wrong (rpm_ostree is skipped everywhere by design, resolve.py:70-73), not because the host is immutable. Unreachable today (registry.toml contains zero `rpm_ostree` methods; only a comment at :95 references it), but the `_rejection` mirror bakes the misleading label in if one is ever added.
- LOW — the `min_os_version` short text hardcodes `needs macOS <v>+` without checking the method's own `os`; correct while `os_version` is Darwin-only (platform.py docstring), but the classifier doesn't enforce that assumption.
- LOW — the `os`-category detail "lists the sorted union of `method.os` values" — for a tool whose methods are native kinds with no `os` param, the plan says use `_NATIVE_OS`' OS; the mapping from kind-rejection to `os` category for a native manager of another OS is described but slightly convoluted (it is handled: "a native manager of another OS, which counts as `os`").

**Suggestions.**
- Give `rpm_ostree`-kind rejection its own short text (e.g. `always skipped by policy`) or add a one-line comment in `_rejection` noting the mislabel limit.
- Optionally assert the method's `os` contains "macos" (or that `platform.os == "macos"`) before emitting the `needs macOS` short text.

**Risk Assessment.** **LOW.** Small, pure, test-pinned change with a genuine structural invariant; the only findings are latent-wording edges unreachable with current registry data.

---

## 16-15

**Summary.** The rendering plan that puts plans 16-05/16-09's computed facts on screen. All referenced code sites are accurate (including the exact silent `return` being replaced and the pre-existing unescaped `active_path` interpolation at catalog_tui.py:584 that round-1's T-16-42 escape now genuinely closes), the legend-budget conclusion is correct even though its arithmetic is slightly off, and both ledger dispositions are visible in executable content.

**Strengths.**
- Verified the three anchor claims: `action_update_tool`'s silent branch is exactly `if status is not None and status.outdated is False: return` (catalog_tui.py:743-745); the "also claimed by" construction lives at :577-585 with `extra += f" — live copy at {ownership.active_path}"` unescaped at :584; `tool_browser.py:344-346` renders `detail_text` via `Text.from_markup` when `detail_is_markup` — so T-16-42 is a real, reachable markup-injection path and the planned per-segment `rich.markup.escape` (escape the segment, never the joined string, so the detail's own intentional markup survives) is the right fix. `test_detail_escapes_path_with_bracket` pins it.
- Data dependencies confirmed to exist in dependency plans: 16-05 Task 2 adds exactly `declared_manager_label`, `also_installed_note`, `active_path_note` (and 16-15's import key_link forbids local re-derivation, addressing the round-1 `OWNER_LABELS[...]` indexing finding — `owner_label` is already imported at catalog_tui.py:23).
- The `u` never-silent rule covers every branch (current → "already current", off-policy current → D-05 sentence, broken → repair hint, unknown → refusal + active-path note), and the broken check placed before current/unknown matches D-18's broken-beats-outdated edge from 16-13.
- Legend budget: I measured line 1 at 60 plain columns (plan says 58); ` · [red]! broken[/]` adds 11 → 71, comfortably ≤ 78. Lines 2/3 measure 76 and ~78, confirming no room — the placement-on-line-1 conclusion holds, and `test_legend_keeps_the_catalog_table_usable_at_the_minimum_size` gates any regression regardless of the arithmetic.
- `action_update_tool`'s reorder is implementable as described: the ownership record is "looked up first" (Task 1), so both the off-policy tail and the broken hint (Task 3) have the record before the current-status return.

**Concerns.**
- LOW — Legend arithmetic is off by ~2 columns on lines 1 and 3 (58/76/77 claimed vs 60/76/78 measured); conclusion unaffected, tests gate it, but the "line 1 becomes 69" comment the plan tells the executor to write would itself be wrong.
- LOW — The broken check in `_row_cells` performs a second `ownership_of` lookup per row paint (in addition to `_owner_cell` at :511/:522) — negligible (unlocked dict read, per 16-12's IO-free `skill_status_of` precedent), but unstated.
- LOW — Escaping covers the three path-bearing segments this plan builds/touches; `owner_detail` (catalog_tui.py:573) also interpolates record data (package names) unescaped — package names with markup metacharacters are implausible, informational only.
- LOW — `_reapply`-style cross-check: none needed; 16-15 renders `broken` from `ownership_of(tool.id).broken` exactly as 16-13 classifies it — the two plans agree on the source of truth.

**Suggestions.**
- Re-measure the legend line widths before writing the budget comment (60→71, not 58→69), or write the comment without exact numbers.
- Note in Task 3 that the broken lookup reuses the same record `_owner_cell` will fetch (or is fetched once per row), to forestall a double-probe pattern.

**Risk Assessment.** **LOW.** Display-layer-only change with pinned texts, an escape fix that closes a verified reachable path, and correct dependency wiring; findings are cosmetic.

---

## 16-16

**Summary.** The phase's real-host proof plan, now with an airtight read-only story after the round-1 HIGH. I verified the danger claims it is built on (enter on ExecuteScreen and enter in Doctor both run `configure_path` against the real rc files), and every production function it calls either exists today or is pinned by a dependency plan's artifacts. The validation-map backfill is concrete, and the checker-revision shipped-path check for 16-12's skill probe is present.

**Strengths.**
- The round-1 HIGH is genuinely and thoroughly addressed, and its factual basis checks out: `execute_screen.py:548` runs `run_live(self._inputs.wire_path)` unconditionally after installs/updates on the non-crash path; `setup.py`'s `wire_path` closure calls `configure_path(..., myshellrc_path=_MYSHELLRC, shellrc_path=_SHELLRC, rc_paths=...)` (verified); `wizard_app.py:606` `action_apply` runs `run_live(self._fix)` before any guard modal. The human-check steps now instruct esc-only exits (steps 5, 7) and `u` only on a current Ver cell (step 1), with the rationale and exact mechanics written into truth #4 and T-16-44's exclusion list (`configure_path`, `wire_path`, `action_apply`, enter, `u`-on-outdated, `make fix/setup --yes/uninstall`). This is the strongest possible disposition short of not running the TUI at all.
- Every proof-call target verified: `resolve_ownership`/`read_inventory`/`plan_uninstall`/`run_probe` composed exactly as setup.py's `_reresolve_ownership` (setup.py:~1103-1115, verified); `run_query` exists (installer/run.py:304); `inspect_skill_packs(tools, probe, home)` is 16-02's artifact; `refresh_skills`/`skill_status_of`/`skill_probe`/`seed_skills_from_cache` are 16-12's artifacts, and the temp-`cache_path` trick genuinely prevents both the real version-cache and any rc write (`refresh_skills` persists skills only via `save_version_cache(path, ...)` on the service's own path); `path_writer_lines_for(report)` with guardable/refusal/block_owner records is 16-11's artifact built on 16-08's `PathWriterLine`/`guard_path_writers` — and the plan explicitly forbids calling `guard_path_writers`.
- The checker-revision fix is real and matched to 16-12: proof (c) adds the shipped-path grep (`refresh_skills(` must show `self._catalog`, matching 16-12's acceptance grep) plus a full-catalog `refresh_skills` run, and the human check (3) starts on the System view (verified `BASE_VIEW = VIEW_ORDER[0]` at ui_common.py:192) then switches to AI — exercising the exact launch path where 16-12's tier-filter bug lived.
- D-09's audit requirement (skill-pack harness lists) rides in via 16-07, which 16-16 depends on; the proof records pack presence per host rather than re-deriving it.
- Backfill discipline: "Any expected value that does not hold on the host … is recorded as such with the actual output, never 'fixed' in this plan" — the right posture for a proof plan.

**Concerns.**
- **MEDIUM — `nyquist_compliant`/`wave_0_complete` vs pending human rows.** Truth #3 sets both flags "only if every row's command passed", but Task 2 adds seven "Phase 16 walkthrough" rows whose status is *pending* until the end-of-phase human check. Whether pending human rows block the flags is ambiguous — the flags could be set true while seven rows are unverified, or held false waiting on humans, and the plan doesn't say which. One sentence fixes it (e.g. the flags cover automated rows only; human rows carry their own pending status).
- LOW — Proof (g) needs a `DoctorReport` to feed `path_writer_lines_for(report)`, but the plan never says how to construct one (`doctor_data(...)` composition from setup.py:~786-792 is the natural source; `read_first` doesn't name it).
- LOW — Proof (c) runs real harness CLIs (`claude plugin list`, `pi list`, `codex plugin list`) via `run_query` — read-only listings with 16-12's timeout-bounded runner, so safe, but the read-only claim rests on those CLIs being non-mutating; worth one word in T-16-44's disposition ("list-only subcommands").
- LOW — The `_execute_inputs`/`ExecuteScreen` preflight read (step 5) is safe only because `on_mount` is pure (resolve/audit/preflight, verified execute_screen.py:426-448, no mutation before `action_start`); the plan asserts this but doesn't cite it — it holds today.

**Suggestions.**
- Define whether pending human-check rows gate `nyquist_compliant`/`wave_0_complete`.
- Name the report construction for proof (g) (reuse setup.py's `doctor_data` composition or `run_doctor`'s injected seam).

**Risk Assessment.** **LOW-MEDIUM.** The read-only design is now verified sound against the actual mutation paths; the MEDIUM is a bookkeeping ambiguity in the validation flags, not a host-safety issue.

---

### Standing-constraint audit (all four plans)

- **No real-host rc mutation in tests/verification:** verified — 16-13/14/15 tests use fake services and tmp/fixture paths exclusively; 16-16's proofs use temp `cache_path`, read-only functions, and an explicit T-16-44 exclusion list. No violations.
- **Zero sudo/pkexec/doas:** none of the four plans contains or invokes any. Verified.
- **English only:** all plan text is English. Verified.

### Batch verdict (reviewer, before post-review fixes)

- **Unresolved HIGH findings: 0.**
- **Unresolved non-HIGH findings that still need a plan change: 2.**
  - 16-13 (MEDIUM): Task 1's "already current" progress row vs Task 2's appended reapply outcomes — `on_install_run_finished` (execute_screen.py:811-814) writes `_progress[id] = "done"` for every `message.outcomes` entry, and the plan never states which representation wins for current-tool rows. Needs one clarifying sentence.
  - 16-16 (MEDIUM): `nyquist_compliant`/`wave_0_complete` semantics vs the seven pending human-check rows are undefined. Needs one clarifying sentence.
- **Lower-severity notes (no plan change strictly required):** 16-14's `rpm_ostree`-on-mutable-host short-reason mislabel (latent, unreachable with today's registry) and hardcoded `needs macOS` short text; 16-15's legend arithmetic (58/76/77 vs measured 60/76/78 — conclusion and tests unaffected) and stale comment numbers to be written; 16-13's `_PROGRESS_GLYPH` citation (:85-90, not :905-940) and stale deferred-ledger wording on the unattended preflight.
- **Round-1 findings now resolved:** all 12 accepted dispositions across the four plans (16-13: registry relabel, `_with_repair` typing, cancel gating, summary inflation — all visible in task actions/acceptance and verified against source; 16-14: `selection.py` change-set + `Mapping` invariance fix, test-assertion change — both real and correctly planned; 16-15: T-16-42 escape now concretely planned with a bracket-path test, `owner_label()` used at both sites; 16-16: the enter-runs-`configure_path` HIGH closed with verified mechanics, T-16-44 exclusion list completed, `files_modified` fixed, citation fixed), plus 16-16's checker-revision blocker (16-12's tier-filtered probe) closed via the shipped-path grep, the full-catalog temp-cache service run, and the System-view-first human check. The two deferred items (16-13's unattended CLI scope; 16-05's D-03 note-as-offer) remain deferred with sound rationale.

---

## Consensus Summary

Each plan was reviewed by exactly one identity (see note above), so this section is the orchestrator's adjudication. Each reviewer finding was re-checked against the current plan text and source, and against the plans' round-1 ledgers. Both identities produced source-grounded `file:line` evidence; neither output carries a discount marker.

### Agreed Strengths
- Round-1 dispositions are honored in executable plan content (task actions, acceptance greps, named tests), not only in ledger prose. Both reviewers confirmed this for all 16 plans (16-01: 6 accepted; 16-02: 4; 16-03: 4; 16-04: 1+2 deferred; 16-05: 3+2 deferred; 16-06: 3+1 deferred; 16-07: 5; 16-08: 5; 16-09: 1+1 deferred; 16-10: 2; 16-11: 3; 16-12: 3+1 deferred; 16-13..16-16: 12 accepted + 2 deferred). Every deferral was judged to have sound rationale, usually a locked D-decision or an existing code precedent.
- The plan-checker revisions hold up: 16-12's full-catalog skill pass (`self._catalog`, not the tier slice) plus `_skills_pass_lock` passes a lock-order analysis (pass_lock -> `_lock` only; `invalidate`/`skill_status_of` never take pass_lock). 16-11's helper deletion is staged so the tree stays green between tasks. 16-05's keg-only `opt/<formula>/bin/<cmd>` proof closes D-06's macOS case and is test-pinned. 16-08's `_PathLine.unresolved` makes `_REFUSE_UNRESOLVED` reachable with a correct test input. 16-16's human check is read-only: esc-only exits, `u` only on a current cell, an explicit T-16-44 exclusion list, and a temp `cache_path`.
- Standing constraints: no plan mutates a real-host shell config in tests or verification (tmp_path or fixtures only, backstopped by `real_home_untouched`), there is zero sudo/pkexec/doas, and everything is in English. Both reviewers checked all 16 plans and found no violations.

### Agreed Concerns
None at HIGH. Every concern that needed a plan change was fixed during the run (below).

### Post-review plan fixes (resolved during this cycle)
| Finding | Severity | Raised by | Fix | Status |
|---|---|---|---|---|
| 16-03: `simple = (len(segments)==1 and not comment_dropped)` made a column-0 zsh `path=(...)` line a strip candidate, contradicting truth #5 (strip set does not widen); the strip consumer `installer/app.py:408-419` deletes the whole line | MEDIUM | opencode-plan-review | 4a3ef8c: `simple` requires the segment to match `_PATH_EXPORT`, not `_ZSH_PATH_ARRAY`; `test_zsh_array_line_is_not_a_strip_candidate` | resolved |
| 16-03:196 (introduced by 4a3ef8c): acceptance asserted via `path_writer_lines`, which only 16-08 (wave 2) creates | LOW | orchestrator source check | 3ac3b57: asserts via `unguarded_path_writers` (`installer/rcclean.py:112`, returns dir -> rc files) | resolved |
| 16-08 (interaction with 4a3ef8c): `_guard_refusal` checked compound (`not line.simple`) before zsh array, so every array line got `_REFUSE_COMPOUND` and `_REFUSE_ZSH_ARRAY` was unreachable, making Task 2's exact-constant test unpassable | MEDIUM | opencode-glm-5.2 | 04aa62e: order is zsh array -> compound -> unresolved -> ordered split (Task 1 rule list, :178 final-order sentence and ledger row all updated) | resolved |

### Reviewer MEDIUMs adjudicated as not needing a plan change
- **16-13 (glm): "already current" row vs appended reapply outcomes.** `_refresh_progress` iterates `self._ordered` only (`installer/execute_screen.py:921-928`), and current tools are never in `_ordered`. The plan already says "Keep `self._current` out of `_progress`'s install/update rows; add a third progress row kind" (16-13-PLAN.md:97). The `_progress[id]="done"` write at `execute_screen.py:811-814` is therefore dead state for current tools and cannot repaint their row.
- **16-16 (glm): `nyquist_compliant`/`wave_0_complete` vs pending human rows.** The flags are gated on the Per-Task Verification Map rows (16-16-PLAN.md:86), while the seven walkthrough rows go into the separate `## Manual-Only Verifications` table (16-16-PLAN.md:108; 16-VALIDATION.md:37 vs :66). The scope is already unambiguous.

### Advisory LOWs (no plan change required; executor or verifier notes)
- 16-01: the objective's "stale comments in ownership.py" line is a no-op (the real stale comment is `uninstall.py:220-227`, already handled); the `_location_dirs` call-site method sequence is unstated (immaterial today).
- 16-02: `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` needs a realistic codex row. It is already in scope through the plan's `inspect_status` grep (16-02-PLAN.md:109). Whether `operation_id`/`args` leave `_parse_skill_operation`'s allowed set is unstated (fails closed either way).
- 16-05: `OWNER_LABELS.get(owner)` with an `Owner | str` key is not pyright-clean; the `dataclasses.replace` and update.py imports are unnamed (gate-caught). `also_installed_note` is ungated for `owner="unknown"`, but its only consumer, 16-15, gates it. A script tool whose `cmd` collides with a brew link now resolves to `unknown`, which fails closed.
- 16-06: `import os` and `Literal` are unnamed; the `ownership=None` wording could be clearer.
- 16-07: there is no stated fallback when an upstream fetch fails (the prohibition already forbids guessing); the nonzero-probe gate depends on the audit outcome; who owns `by_harness` ordering is unstated.
- 16-08: nested foreign marked blocks would lose their owner (single-pointer depth loop), but no real nested block is cited. Handling of records whose `rc_path` differs from the argument is unstated. A second guard per file is refused by `backup_precondition`, which is fail-closed. `_path_hazard` refusal wording is consolidation-flavored.
- 16-09: PNPM_HOME-collision edge (docstring line).
- 16-10: kitty `~/.local/bin` symlink is a manual vendor step (comment); one prohibition-ledger row reads `status: unresolved` despite T-16-30's mitigation.
- 16-11: the `grep -w` deletion gate does not catch test function names that embed the deleted helper names (cosmetic).
- 16-12: the mixed absent/unknown host map is unpinned (the spec yields dim `?`); the worker's handling of a `run_live` `(None, msg)` result on a bug path is unspecified.
- 16-13: `_PROGRESS_GLYPH` citation (:85-90, not :905-940); stale deferred-ledger wording on unattended preflight; failed-repair exclusion from reapply unstated.
- 16-14: an `rpm_ostree`-only tool would get `immutable host` on a mutable host (unreachable: the registry has no rpm_ostree methods); the `needs macOS` text assumes Darwin-only `os_version`.
- 16-15: legend arithmetic is off by about 2 columns (60/76/78 measured vs 58/76/77), with the conclusion and test unaffected; a second `ownership_of` lookup per row.
- 16-16: proof (g)'s `DoctorReport` construction is unnamed; the harness CLIs used are list-only.

### Divergent Views
None on the same plan, because the identities reviewed disjoint subsets. Where batch 3 (16-08) and batch 1 (16-03) touched the shared `_PathLine.simple` contract, the 16-03 fix and 16-08's refusal order were reconciled by 04aa62e.

## Verification coverage
| Batch | Plans | Reviewer | Tree verified | Sections | HIGH | Needs plan change (after fixes) |
|---|---|---|---|---|---|---|
| 1 | 16-01..16-04 | opencode-plan-review | ff349df | 4/4 | 0 | 0 (16-03 MEDIUM fixed in 4a3ef8c + 3ac3b57) |
| 2 | 16-05..16-06 | opencode-plan-review | ff349df | 2/2 | 0 | 0 |
| 3 | 16-07..16-08 | opencode-glm-5.2 | 4a3ef8c / 3ac3b57 | 2/2 | 0 | 0 (16-08 MEDIUM fixed in 04aa62e) |
| 4 | 16-09..16-12 | opencode-glm-5.2 | 3ac3b57 | 4/4 | 0 | 0 |
| 5 | 16-13..16-16 | opencode-glm-5.2 | 04aa62e | 4/4 | 0 | 0 (2 MEDIUMs adjudicated as already covered) |

Not covered by any reviewer: execution of any plan (waves 1-4 unexecuted, so cross-wave anchors were checked against plan text, not landed code), and 16-08 after 04aa62e. The 16-08 change was checked by the orchestrator only (16-08-PLAN.md:114-115, :178, :268).

## Cycle Verdict
- **current_high = 0**
- **current_actionable = 0** (3 actionable findings raised this cycle, all fixed in 4a3ef8c, 3ac3b57 and 04aa62e; 2 reviewer MEDIUMs adjudicated as already covered by plan text; the remaining items are advisory LOWs)


---

# Cross-AI Plan Review — Phase 16 (convergence cycle 3: gap-closure plans 16-17 and 16-18)

Reviewer: `opencode-glm-5.2` = `opencode-go/glm-5.2` (reasoning=high, `--agent plan`, read-only), source-grounded against HEAD (tree = 920abef plus the two untracked gap plans). The two plans close the 22 open findings of 16-REVIEW.md and its second review lane (WR-01..04, IN-01..IN-18): 15 are planned as fixes (16-17: WR-01, WR-02, IN-01, IN-02, IN-06, IN-11, IN-14; 16-18: WR-03, WR-04, IN-10, IN-12, IN-15, IN-16, IN-17, IN-18) and 7 are accepted with rationale in 16-REVIEW-DISPOSITION.md (IN-03, IN-04, IN-05, IN-07, IN-08, IN-09, IN-13; plus the puppeteer D-18 observation recorded as a true positive).

> Note (run history): the first 16-17 attempt died with `database is locked` (two opencode runs in parallel); it was re-run alone. A first re-run ended after tool calls with no final review (the #1936 shape seen in cycles 1-2), so the final run adds a "stop after about 25 tool calls and write the review" instruction. The round-1 16-17 output file contains a second, partly spliced copy of the review (it carries the HIGH below); both parts were adjudicated. Round 2 re-reviewed each revised plan with a list of the round-1 findings. 16-17 and 16-18 were reviewed sequentially, never in parallel.

## Round 1
### 16-17 (round 1)

**Summary:** Plan 16-17 covers exactly the seven rc-scanner/guard findings the disposition ledger assigns to it (WR-01, WR-02, IN-01, IN-02, IN-06, IN-11, IN-14 at 16-REVIEW-DISPOSITION.md:104-121) and defers the rest to 16-18. I verified every mechanism against HEAD (working tree clean except the two new plan files): the WR-02 strip-corruption trace reproduces exactly as stated, the WR-01 "consolidation" refusal text is live at installer/shellrc.py:966-969, and the guard/strip disagreement the plan closes is real. All proposed fixes are feasible in the cited code shapes and none of the existing tests I traced breaks. Two RED fixtures are mislabeled (they pass on current code) and a few read_first line anchors have drifted, but no mechanism is wrong and nothing unsafe is planned.

**Strengths:**
- WR-02 is correctly identified as the only corruption-capable defect and the fix point is exact: `plain_only` (installer/rcclean.py:320-325) is the only expression that lets a `then PATH=...` column-0 line become `simple`, and `find_duplicate_path_lines`' gate (rcclean.py:406-412) passes today for both stated fixtures — I traced `if [...]\nthen PATH=...\nfi` and `until false\ndo PATH=...\ndone` by hand through `_split_unquoted` → `_command_text` (rcclean.py:245-246) → `_judge_line` and both genuinely return `[1]` today, so the RED tests fail for the stated reason.
- The plan correctly keeps `_command_text` untouched (reporting still sees through `then`), and correctly predicts the post-fix guard behavior: `path_writer_lines` still reports the then-form with `guardable is False` — today via `_PATH_EXPORT.match(line.text)` returning None (rcclean.py:479-481), post-fix via `not line.simple` (rcclean.py:475-476); same `_REFUSE_COMPOUND` text either way, so the guard path is byte-stable.
- WR-01 anchors are all exact: `backup_precondition` (installer/shellrc.py:935), refusal text (:966-969), exactly two call sites (:1095 consolidation, :1184 guard — verified by grep), and the keyword-only `flow=` parameter changes only the guard site's wording while the single-backup-slot invariant and `_create_backup` (create-exclusive, :979-995) are untouched. The existing `test_guard_refuses_a_preexisting_backup_with_different_bytes` (tests/test_shellrc.py:2959-2971) asserts only status and bytes, not the reason text, so the rewording breaks nothing the plan fails to mention.
- IN-11's comment-closer RED case reproduces exactly: `_has_standalone_closer` (installer/rcclean.py:106-107) matches the trailing ` fi` after `# keep until` (space before, EOL after — both in the regex's boundary classes), no frame is pushed, and the body line is reported guardable with `refusal None`. The plan also correctly limits the fix to `_has_standalone_closer` and does NOT touch `_condition_references_path` (rcclean.py:110-123), which must keep searching raw text — the first fixture's `:$PATH:` guard lives inside double quotes, so an over-broad `_code_text` use there would have broken the guard it is trying to preserve.
- IN-14's mechanism is correct and surgical: `_guard_refusal` (rcclean.py:479-487) falls through to `_REFUSE_MULTI` for `PATH=/a:/b` today (traced), the proposed `$PATH`-membership check keeps `PATH=/a:/b:$PATH` on `_REFUSE_MULTI` and `PATH=$PATH:/m` on `_REFUSE_APPEND`, and the only test pinning `_REFUSE_MULTI` (tests/test_rcclean.py:713-718) uses a fixture that references `$PATH`, so it survives unchanged.
- IN-06 is a real raise: `Path.is_file()` only suppresses a fixed errno set (ENOENT/ENOTDIR/ELOOP), not EACCES, so `p.is_file()` at installer/locations.py:128 can raise `PermissionError`; the helper fix and the monkeypatched-`is_file` RED test are both feasible.
- Hygiene is good: frontmatter has `cross_ai: true`, `gap_closure: true`, wave/depends_on, a `files_modified` list that matches what the tasks touch; every fix task is RED-first with a `fails_when` that rejects a RED run that passed; threat model present; safety rules (tmp_path-only, no real rc, no installs, no sudo/pkexec/doas, English only) are stated and consistent with every task; Task 6 is a final `make validate && make test` gate with a no-bypass rule; the codegraph-first restatement is in the objective.
- IN-13's acceptance rationale is sound: I traced the one-line `if/elif` fixture — it is reported with `_REFUSE_COMPOUND`'s "edit it by hand" (5 segments, so `simple` is already False), i.e. reported and refused for guarding, which is exactly the fail-safe behavior the disposition claims (16-REVIEW-DISPOSITION.md:120).

**Concerns:**
- MEDIUM: Task 2's second IN-11 case is not a RED test — it already passes on current code. For `if [ -n "x; fi" ]; then`, the closer regex's suffix class `(?:$|[;\s#])` (installer/rcclean.py:107) does not match `fi` followed by `"`, so the frame is already pushed and the body is already reported-inside-the-if exactly as the plan specifies. The quote bug the review names is real but needs a quoted closer followed by whitespace/`;`/`#` inside the quotes (e.g. `if [ -n "x fi y" ]; then`); the plan's chosen fixture exercises nothing. The plan's "RED first (all FAIL on current code)" heading (16-17-PLAN.md:122) is factually wrong for this case.
- MEDIUM: Task 3's second IN-02 RED fixture also already passes: for `PATH="$HOME/m/bin:$PATH" env FOO=1 cmd`, `_unquote` (installer/rcclean.py:43-46) does not strip (first and last chars differ), the colon-split segment keeps a leading `"` so `_directory_for` (rcclean.py:375-384) never matches the managed dir, and `path_writer_lines` (rcclean.py:539-552) appends records only per matched managed directory — so it returns `[]` today, for the wrong reason. Valid as a post-fix pin; mislabeled RED (16-17-PLAN.md:157).
- MEDIUM: Task 2's read_first anchors have drifted: `_update_block_stack` is at installer/rcclean.py:141-168, not ":163-196", and `_split_unquoted` is at :171-242, not ":199-262" (16-17-PLAN.md:119). The mechanism descriptions are still accurate; only the line ranges are wrong (they match neither HEAD nor the review's anchors).
- LOW: The `requirements:` frontmatter lists D-09..D-14 (16-17-PLAN.md:17), which are the skill-pack detection decisions (16-CONTEXT.md:33-38) — this plan touches none of that; the governing decisions are D-21..D-24 (16-CONTEXT.md:49-51, the guard-in-place and backup-convention decisions).
- LOW: Task 3's insistence that `_remember_assign` "is NOT called" for a one-shot `PATH=... cmd` segment is moot — `_remember_assign` already returns early for the PATH variable (installer/rcclean.py:266). Unaddressed side detail: in the current else branch such a segment also sets `chain_has_presence` (rcclean.py:316-317) via `_PATH_REF`; after the fix, whether the dropped segment still sets it changes `&&`-chain guarding for shapes like `cmd && PATH=/m:$PATH cmd2 && export PATH=...`. Edge case; worth one pin test or an explicit decision.
- LOW: Task 4's RED test needs the first guard call to receive a partial record list — `guard_path_writers` rewrites every guardable line passed to it in one call (installer/shellrc.py:1151, 1188-1201), so a "second remaining writer line" only exists if call one is given a subset. The plan implies it ("guards a second remaining writer line") but never states it; the default `_seed_guard_rc` fixture (tests/test_shellrc.py:2915-2922) has only one writer line.
- LOW: Task 2's heredoc opener regex `<<-?\s*(['"]?)([A-Za-z_]\w*)\1` accepts a space between `<<` and the delimiter, which is correct shell, but combined with `_code_text` it will also treat a `cat << EOF` inside a managed block differently than today — no, managed blocks are skipped before the walk (rcclean.py:350-351), so a heredoc opened inside a managed block is never seen and its body outside the block is judged normally. Edge case worth the one `shortcut:` comment the plan already mandates (16-17-PLAN.md:133).

**Suggestions:** Relabel the two passing-today fixtures as regression pins (or swap the IN-11 quote case for one that actually self-closes today, e.g. a quoted `"x fi y"` closer) and correct the "all FAIL" claim; fix the two drifted read_first ranges in Task 2; change `requirements:` to D-21..D-24; state in Task 4 that the first guard call is given a one-record subset of a two-writer fixture; add one pin for the `&&`-chain `chain_has_presence` question in Task 3.

**Risk Assessment:** MEDIUM — no mechanism defects, no safety violations, no existing test broken by any traced change; the risk is that two mislabeled RED cases confuse the executor at the "confirm RED" step and the drifted anchors send it to the wrong lines first.

**Second pass in the same output (verbatim verdict, carries the HIGH):**

### Batch verdict
Unresolved HIGH findings: 1 — Task 2 (IN-01) opener detection on `_code_text` cannot detect the quoted delimiters `cat <<'EOF'`/`cat <<"EOF"` that the plan itself requires (16-17-PLAN.md:131-132 vs :30/:124-125; rcclean.py:43-46, :337-358).

Unresolved non-HIGH findings that still need a plan change: 4 —
1. Frontmatter `requirements` D-09..D-14 → should be D-21..D-24 (16-17-PLAN.md:17; 16-CONTEXT.md:33-38 vs :49-52; 16-11-PLAN.md:17).
2. Task 1's `segment.lstrip()` alternative misclassifies indented plain writers and breaks tests/test_rcclean.py:760-765 (16-17-PLAN.md:98; rcclean.py:246, :320-325).
3. Task 3's quoted-prefix RED fixture already returns `[]` today — not RED (16-17-PLAN.md:157; rcclean.py:43-46, :90-98, :382, :539-542).
4. Task 3's "must still take the else branch" sets `chain_has_presence` and suppresses `&&`/`||`-chained real writers; ambiguous wording plus the contradictory `_remember_assign` parenthetical (16-17-PLAN.md:163; rcclean.py:299, :309, :315-317, :341-343).

Note: all traces were done by hand from the source at HEAD; I did not execute the test suite (read-only review). The LOW items (is_dir residual, numeric delimiters, Path.home wording) need no plan change.

### 16-18 (round 1)

**Summary:** The plan is source-accurate and execution-ready. Every file:line anchor I checked matches HEAD, all eight RED tests are hand-traceable to fail on current code for the stated reason, and each proposed mechanism fits the real code shape (the WR-03 `_installed` fallback, the WR-04 label/header emission inside `_filtered_install_lines`, the IN-10 generalization of the existing D-06 `shadow_brew` gate, the IN-17/18 closed-table and load-time checks). Hygiene is complete: frontmatter (`cross_ai: true`, `gap_closure: true`, wave 9 after 16-17's wave 8, full `files_modified`), test-first tasks, threat model, codegraph-first restatement, safety rules, and a final gate task. One MEDIUM spec gap in Task 5 and a few LOW notes.

**Strengths:**
- WR-03 verified end-to-end: `_present` returns `None` on empty hosts (installer/catalog_tui.py:483-484), `_inst_cell` falls back to the PATH check (installer/catalog_tui.py:515), `_ver_cell` blanks on a falsy `_present` (installer/catalog_tui.py:518-519); openspec (registry.toml:2945, no `status_probes` in its block) and spec-kit (registry.toml:3361, none in 3361-3455) declare zero probes, and `inspect_skill_packs`/`_pack_status` (installer/skill_lifecycle.py:414-421, :392) yield `hosts={}` forever for them. `_installed[tool.id]` is a complete map (read unconditionally at installer/catalog_tui.py:613), so the fallback adds no new data source — the key_link claim is true.
- WR-04 anchors and mechanism check out: `perform_action`'s by_harness branch at installer/skill_lifecycle.py:270-278, `_filtered_install_lines` at :242-256, `SKILL_HARNESS_LABELS` at :66 (56/56 harness coverage — I verified programmatically), `_NO_HOST_HEADER` at :194; `_parse_by_harness` builds pairs in `SKILL_HARNESSES` order (installer/model.py:462), so the "both labeled blocks in SKILL_HARNESSES order" assertion is satisfiable without reordering; `_skill_string_tuple` accepts any non-empty string (installer/model.py:380-388), so the prose `or,` line and the single parenthesized codex line pass load; the existing no-host test's last assertion is exactly `"superpowers" in outcome.instructions` (tests/test_skill_lifecycle.py:262) and the plan updates it in the same commit.
- IN-10 premises verified: "script" is in `_INSTALLER_KINDS` (installer/ownership.py:150), so kitty's method produces a location candidate; java's sdkman method declares `bin_dir = "~/.sdkman/candidates/java/current/bin"` (registry.toml:1786-1789); `_native_owner`/`_os_package_owner` return `None` on any non-empty `candidates` (installer/ownership.py:770, :867); the D-06 flow to generalize is at :576-588, :629-631, :632-638, :666-675. Hand-traced both RED fixtures: today they fall to the active-path unknown branch (:676) with owner `unknown`; after the fix the location candidate (owner in `_location_dirs`, location-proof evidence, not in `attributed`, active_path set) becomes a shadow, `gated` empties, and the OS-package branch fires — exactly as the plan states.
- Task 4's unchanged-behavior claims hold against the real tests: the artifact-blocker test uses `artifacts=[...]`, not a location proof (tests/test_ownership.py:543-561), and the by-elimination script tests use `which=None` (tests/test_ownership.py:349-393), so neither is touched by the evidence-based/active_path-gated shadow conditions.
- IN-17/IN-18 verified: `_install_state_status` hardcodes the filename and ignores `match` (installer/skill_lifecycle.py:360-364); all shipped install-state probes use `match = "gsd-core"` (registry.toml:3318-3326), so the closed table key matches the data and is pinned by tests/test_registry.py:1989; `_parse_status_probes` has no duplicate-harness check (installer/model.py:401-445) and `SkillStatusProbe` positional order is (harness, via, match) (installer/model.py:253-256), so the RED constructions are correct.
- IN-15: the three existing "already current" tests all set `stale=False` (tests/test_catalog_tui.py:2764, :2837, :2870), so the stale-gated wording change breaks none of them; the gate is at installer/catalog_tui.py:912-913 as cited.
- IN-12/IN-16 anchors verified: `action_apply` early-return at installer/wizard_app.py:622-624, `_tui_guidance` at :589 rendered into the body at :523, the inert fragment emitted at installer/guidance.py:86-90, the pinned no-restart test at tests/test_wizard_app.py:711; the "Same accepted Bazzite gap as kitty" comment exists just before the alacritty entry (registry.toml, immediately preceding `id = "alacritty"` at :2655) and kitty's script method with `os = [... "fedora"]` is at registry.toml:~2551-2553.
- Accepted findings (IN-03/04/05/07/08/09, IN-13 via 16-17, puppeteer) all have label-only or fails-closed harm with non-trivial fix cost; the rationales are sound and consistently recorded in the disposition ledger.
- No overlap with 16-17 (wave 8, files rcclean/shellrc/locations vs this plan's catalog/skills/model/ownership/wizard/registry), and `depends_on` includes 16-17, so the two never edit or gate the tree concurrently.

**Concerns:**
- MEDIUM: Task 5 (IN-12) does not specify how to match the guard fragment, and its RED fixture as described would pass a wrong implementation. The fragment "Press enter (apply) to guard it in place" is usually mid-string: `_writer_next_step` appends the block-owner fragment first and joins with "; " (installer/guidance.py:79-99), while every existing rewrite in `_tui_guidance` is prefix-based `startswith` (installer/wizard_app.py:593, :603, :611). An executor who copies the startswith pattern passes the plan's RED test (a plain `_writer_line(rc)` record, no block_owner — the shape used at tests/test_wizard_app.py:713) yet leaves the defect in place whenever a block-owner fragment precedes the guard sentence. The RED fixture should include a guardable record with a `block_owner`, or the plan should state containment-based matching.
- LOW: Task 2's action uses direct indexing `SKILL_HARNESS_LABELS[harness]` (plan line 137). Coverage is complete today (verified 56/56), but catalog_tui deliberately uses `.get(harness, harness)` (installer/catalog_tui.py:569); a future harness added to `SKILL_HARNESSES` without a label would raise KeyError at render time. `.get` with the raw-id fallback is one character-class cheaper than the crash.
- LOW: Task 3's read_first cites `tests/test_registry.py:1990` for `test_install_state_probes_match_gsd_core`; the `def` is at line 1989. Off-by-one, harmless.
- LOW: Task 5's read_first calls tests/test_wizard_app.py:4190-4330 "guard-chain tests ... for the pilot fixtures"; that range is actually the disk-pressure `_tui_guidance` pilots (tests/test_wizard_app.py:4192-4330). Useful precedent for calling `_tui_guidance()` directly, but mislabeled; the guard-chain pilots are near :711, which the plan also cites.
- LOW: Task 4's "no existing test breaks" claim is verified by reading the candidate tests (artifact blocker at tests/test_ownership.py:543, by-elimination at :349/:365, brew-shadow family at :2133-2198, pnpm-blocker at :273), not by executing the suite — I found no test that pins the location-candidate-blocks-native behavior, but final confidence comes from the plan's own gate run.

**Suggestions:**
- Task 5: add to the RED fixture a second guardable record with `block_owner="my-kitty PATH"` (the helper shape at tests/test_wizard_app.py:740-747) and assert the post-apply text drops the enter hint for both items; that pins containment matching.
- Task 2: use `SKILL_HARNESS_LABELS.get(harness, harness)` for the label line, mirroring installer/catalog_tui.py:569.

**Risk Assessment:** LOW — no mutation path changes (mutations still refuse; ownership is label-only), tests are sandboxed under `tmp_path`, no real installs or rc writes, and the two concrete defects (WR-03 self-contradicting rows, IN-10 wrong `unknown` labels) are display-layer only.

### Batch verdict
Unresolved HIGH findings: 0

Unresolved non-HIGH findings that still need a plan change: 1
- MEDIUM (Task 5 / IN-12): specify containment-based matching (or extend the RED fixture with a block-owner guardable record) so a prefix-based `startswith` rewrite cannot pass the test while leaving the mid-string case broken (evidence: installer/guidance.py:79-99, installer/wizard_app.py:593-617, tests/test_wizard_app.py:713).

### Round-1 adjudication and plan fixes

| Finding | Severity | Plan | Verified against source | Fix | Status |
|---|---|---|---|---|---|
| Heredoc opener detection ran on `_code_text`, which blanks quotes, so `<<'EOF'`/`<<"EOF"` could not match | HIGH | 16-17 Task 2 | rcclean.py:43-46, :337-358 (confirmed: a quote-blanking mask removes the delimiter) | `_code_text` is length-preserving; the opener regex runs on the raw line and a match is accepted only when the masked line shows `<<` as code and no `<` precedes it | resolved |
| IN-11 second fixture `"x; fi"` already passes (suffix class does not match `fi"`) | MEDIUM | 16-17 Task 2 | rcclean.py:107 | fixture changed to `"x fi y"`; per-case RED/pin labels | resolved |
| IN-02 quoted-prefix fixture already returns `[]` today | MEDIUM | 16-17 Task 3 | rcclean.py:43-46, :382 | unquoted RED fixture; quoted form kept as a regression pin | resolved |
| Drifted read_first anchors (`_update_block_stack` 141-168, `_split_unquoted` 171-242) | MEDIUM | 16-17 Task 2 | rcclean.py | anchors corrected | resolved |
| IN-12 guard sentence is mid-string (block-owner fragment first); a `startswith` rewrite passes the plain RED fixture | MEDIUM | 16-18 Task 5 | guidance.py:79-99, wizard_app.py:593-617 | RED fixture adds a `block_owner` record; action mandates containment `str.replace` | resolved |
| `requirements` frontmatter D-09..D-14 (skill-pack decisions) | LOW | 16-17 | 16-CONTEXT.md:33-38 vs :49-52 | `[D-21, D-22, D-23, D-24]` | resolved |
| Task 1 `lstrip` alternative; Task 3 `chain_has_presence`/`_remember_assign` ambiguity; Task 4 subset-call not stated | LOW | 16-17 | rcclean.py:246, :266, :316-317; shellrc.py:1151 | prescribed `_LEADING_THEN_DO.match`; command-prefix segment skipped before `_PATH_REF` with a pin test; two-call subset fixture stated | resolved |
| `SKILL_HARNESS_LABELS[harness]` vs `.get`; off-by-one/mislabeled read_first anchors | LOW | 16-18 Tasks 2, 3, 5 | catalog_tui.py:569 | `.get(harness, harness)`; anchors corrected | resolved |

## Round 2 (re-review of the revised plans)

### 16-17 (round 2)

**Summary:**
Round-2 review of gap-closure plan 16-17 (rc scanner/guard group: WR-01, WR-02, IN-01, IN-02, IN-06, IN-11, IN-14) against real source at HEAD. Every round-1 finding is now fixed in the revised plan: the HIGH heredoc-opener defect is resolved by running the opener regex on the raw line with `_code_text` used only for position validation (traced by hand through all four opener shapes and all four negative shapes — every one classifies correctly); both previously mislabeled RED fixtures are now correctly labeled (I verified `"x fi y"` matches the closer regex today at rcclean.py:107 while `"x; fi"` already passes, and the IN-02 quoted form already returns `[]` today because the stray leading `"` pollutes every expanded target past `_directory_for`'s absolute check at rcclean.py:382); all read_first anchors now match HEAD exactly; the requirements frontmatter, chain_has_presence pin, lstrip prescription, and the Task 4 subset explanation are all present and correct. Every fix mechanism is feasible against the actual code shape; no existing test breaks unaccounted (`test_refuse_multi_directory` at tests/test_rcclean.py:713-718 uses a `$PATH`-referencing fixture so IN-14 keeps it green, and the guidance/wizard pins at tests/test_guidance.py:156 and tests/test_wizard_app.py:688 are hand-built records, not scanner output). Two new LOW edge defects in the proposed heredoc opener regex are the only findings that still warrant a plan touch.

**Strengths:**
- WR-02 fix is minimal and placed exactly right: `plain_only` at rcclean.py:320-325 is the only strip gate (`simple` required at :407), `_guard_refusal` already maps `not simple` to the compound refusal at :475-476, so one `_LEADING_THEN_DO.match(segment)` clause (rcclean.py:27, `^\s*(?:then|do)\s+`) closes the corruption path; both RED fixtures traced to return `[1]` today and `[]` after.
- The raw-regex-plus-masked-position opener design (plan Task 2, action 3) is mechanically sound: `cat <<'EOF'` matches on raw and its `<<` survives masking; `echo "<<EOF"` and `echo hi # <<EOF` are rejected because masking blanks the quoted/commented span; `cat <<< "x"` is rejected by the `masked[m.start()-1] != "<"` check (the regex's leftmost match starts at the second `<`).
- IN-11's RED claims reproduce exactly: the comment-closer case (`# keep until fi`) matches `(?:^|[;\s]|;;)fi(?:$|[;\s#])` at rcclean.py:107 today, so the frame is not pushed at :164-167 and the guarded body is reported with `refusal None` — matching the review's verified probe at 16-REVIEW.md:163.
- WR-01's flow split is the review's first suggested option, keeps the single-backup-slot invariant (`_create_backup` create-exclusive at shellrc.py:987-989) and the fail-closed path (refusal at :1184-1186 precedes every write), and the consolidation text at :1095 is untouched; the two-call subset fixture is now justified — `guard_path_writers` rewrites every guardable record passed to it (shellrc.py:1151, :1188-1201).
- All cited anchors verified exact: rcclean.py:27/:106-108/:141-168/:171-242/:245/:266/:283-334/:316-317/:337-358/:387-413/:465-487/:482/:490, shellrc.py:935-976/:1095/:1145-1211/:1184, locations.py:128, Makefile:34/:50, tests/test_shellrc.py:1861/:2959/:2974, tests/test_rcclean.py:576/:760-765; D-21..D-24 exist at 16-CONTEXT.md:49-52.
- Hygiene complete: `cross_ai: true`, `gap_closure: true`, wave/depends_on, files_modified covers all touched sources and tests, threat model present and mapped to real mechanisms, codegraph-first restatement in the objective, sandbox/tmp_path safety rules in every task, final gate task (Task 6) with a no-bypass rule.

**Concerns:**
- LOW: The heredoc opener regex `<<-?\s*(['"]?)([A-Za-z_]\w*)\1` (plan 16-17-PLAN.md:132) accepts a word right operand, so an arithmetic shift with a variable — `$(( 1 << MASK ))` — passes all three acceptance checks (raw match, masked `<<`, `masked[m.start()-1] != "<"`) and is treated as a heredoc, swallowing all subsequent lines to EOF. That regresses today's behavior (a real writer after such a line is currently reported at `_path_line_targets`, rcclean.py:337-358, and would go silent). The negative-opener test group (16-17-PLAN.md:125) pins only the digit form `$(( 1 << 2 ))` (plan:30), and the `shortcut:` comment (plan:133) does not mention the word form.
- LOW: The same regex mis-captures delimiter words: on `cat << -EOF` the `<<-?` eats the dash, so the scan ends at a line `EOF` while bash's delimiter is `-EOF`; a quoted delimiter containing a space (`<< "E O F"`) never matches at all. Both mis-track the heredoc extent in the over-report direction (fail-safe), but they are unbudgeted acceptance-set gaps next to the plan's four pinned negative shapes (16-17-PLAN.md:125).
- LOW: Task 1's warning that comparing against `segment.lstrip()` "would misclassify an indented plain writer and break the indented-writer test at tests/test_rcclean.py:760-765" (16-17-PLAN.md:98) is not accurate: `_LEADING_THEN_DO` (rcclean.py:27) begins `^\s*`, so matching the raw or lstripped segment classifies the `  export PATH=...` fixture (tests/test_rcclean.py:761) identically. The prescribed mechanism is correct; only the stated consequence is wrong.
- LOW: Tasks 3, 4 and 5 `fails_when` clauses (16-17-PLAN.md:168-169, 196-197, 223-224) omit the "RED passed before the fix" guard that Tasks 1-2 carry (:104, :138), even though must_haves truth 1 (:27) states it globally — a small enforcement asymmetry.
- LOW: must_haves cites IN-02 at `installer/rcclean.py:337` (16-17-PLAN.md:31) while the fix site is `_judge_line` at :283-334 (Task 3's read_first cites it correctly); the ledger table (:301) inherits the same anchor from the review.

**Suggestions:**
- Add `$(( 1 << MASK ))` (word right operand) to the negative-opener test group and one clause to the `shortcut:` comment, or reject a match whose masked left neighbor is inside `$((`—one test line plus one comment line closes the only under-report regression in the plan.
- Either tighten the opener regex for the `<< -EOF` shape (e.g. forbid whitespace between `<<-` and the delimiter, mirroring bash's token rule) or name it in the same `shortcut:` comment alongside the space-containing-delimiter case.
- Copy the Tasks 1-2 RED-run `fails_when` clause into Tasks 3-5, and fix the two anchor nits (:31 IN-02, and the lstrip rationale at :98).

**Risk Assessment:** LOW — every planned fix was traced against HEAD and lands on the exact mechanism it claims; the strip corruption (WR-02), the dead-end refusal (WR-01) and all five scanner heuristics are closed fail-safe, and the two residual edges are rare heredoc-opener shapes that misreport in the safe direction.

### Batch verdict
Unresolved HIGH findings: 0.
Unresolved non-HIGH findings that still need a plan change: 2 — (1) the arithmetic `<< <word>` false heredoc opener (16-17-PLAN.md:132, negative tests at :125): add one negative test + shortcut-comment clause, since it is the only place the plan regresses today's reporting; (2) the opener regex's delimiter-acceptance mismatch for `<< -EOF` and space-containing quoted delimiters (16-17-PLAN.md:132): tighten the regex or record both in the shortcut comment. The remaining LOW items (lstrip rationale at :98, fails_when asymmetry, IN-02 anchor at :31) are cosmetic and need no plan change to execute safely.

### 16-18 (round 2)

**Summary:** Round-2 re-review of gap-closure plan 16-18 (catalog/skills/ownership group, runs after 16-17). All eight cited findings (WR-03, WR-04, IN-10, IN-12, IN-15, IN-16, IN-17, IN-18) were verified against the real source at HEAD: every cited anchor, mechanism, and RED-fixture premise traces correctly, and all three round-1 findings are addressed. No new defect found that would block execution.

**Strengths:**
- Round-1 MEDIUM (IN-12 containment) is properly fixed: Task 5's behavior now mandates a second guardable record with `block_owner="my-kitty PATH"` (fixture shape verified at tests/test_wizard_app.py:739-744), correctly models `_writer_next_step`'s ordering — block-owner fragment appended first (installer/guidance.py:79-85), guard sentence appended mid-list (:86-90), joined with `"; "` (:99), so the sentence is genuinely mid-string — and the action mandates `str.replace` containment, correctly contrasting the existing `startswith` rewrites at wizard_app.py:593/:603/:611. A `startswith` rewrite can no longer pass the RED test.
- Round-1 LOW (`.get` fallback) fixed: Task 2 uses `SKILL_HARNESS_LABELS.get(harness, harness)`, and the cited mirror is real (catalog_tui.py:569 does exactly this).
- WR-03 mechanism is sound and minimal: `_present` (catalog_tui.py:479-490) returning `self._installed[tool.id]` when `status_probes` is empty fixes all four consumers through the existing call graph — `_ver_cell` gates on `_present` at :518, `_presence` at :645-646, `_groups` at :648-652 — while `_inst_cell`'s fallback (:511-515) already used `installed`, so the columns will agree. Verified against the registry that openspec ([[tool]] at registry.toml:2944) and spec-kit (:3361) really declare no `status_probes` (only 5 packs have them; the 3082 block belongs to superpowers).
- IN-10's generalization is structurally correct: the location-proven candidate is what makes `_native_owner` (ownership.py:745) and `_os_package_owner`'s guard at :867 (`if probe is None or candidates or unreadable or active_path is None`) return None today; the existing D-06 `shadow_brew` gate (:576-588, :629-631, native append :636-638, os append :670-675) is exactly the pattern to generalize, and the plan's shadow filter (owner in `_location_dirs` at :914-922, evidence-is-location-proof, not in `attributed`, `active_path is not None`) provably keeps the active-copy case on the existing `active_candidate`/direct branch (:600-618) — `_collect_candidates`' `found.setdefault` (:953) means the artifact-backed candidate is correctly excluded by the evidence filter. RED fixtures reuse the pinned `test_os_package_owner_resolves_git_shaped_tool_on_fedora` helpers.
- IN-17's closed table is safe for shipped data: every `install-state` probe in the registry uses `match = "gsd-core"` (registry.toml:3318-3326), so all keep resolving; `_install_state_status` (skill_lifecycle.py:360-364) currently hardcodes the filename, confirming the defect and the fix shape.
- IN-18: the last-wins collapse is real (skill_lifecycle.py:392 dict comprehension); the parser (model.py:401-445) has no dup check today and the planned seen-set + `ValueError` matches the file's existing error-message style; the registry-wide no-dup assertion guards the data.
- WR-04: `_filtered_install_lines` (skill_lifecycle.py:242-256) confirmed to drop labels; the Claude-only sibling test (tests/test_skill_lifecycle.py:213-228) uses membership assertions that survive the new label/marker lines, and the no-host test's update is named; consumers are display-only (engine.py:86-89 `return False, outcome.instructions`; app.py:189). The codex bare `"superpowers"` element exists exactly as described (registry.toml:3100).
- Hygiene: frontmatter complete (`cross_ai: true`, `gap_closure: true`, wave 9, depends_on ends with 16-17, files_modified covers every touched file including tests/test_registry.py); every code task is RED-first with concrete fixtures; IN-16 correctly needs no test (comment-only, registry.toml:2652 sentence confirmed present, kitty `script` method at :2552-2558 confirmed); threat model present; safety rules (tmp_path rc, no real installs, no sudo) hold; Task 8 is the final gate with the summary ledger mapping each finding to a commit.

**Concerns:**
- LOW: Residual off-by-one/mislabeled read_first anchors (round-1 LOW, partially fixed): `tests/test_registry.py:1989` — the test def is at :1990; `_native_owner` cited as ownership.py:770 — the def is at :745 (:770 is inside it, matching the finding's own anchor); `_writer_next_step` cited as guidance.py:79-99 — the def is at :58. All are read-first hints, not claims about changed code; no correctness impact.
- LOW: The plan's codegraph-first restatement is moot — this repo has no `.codegraph/` index (codegraph_explore rejects it), so the executor will fall back to grep/read. Not harmful, but the restatement adds no value here.
- LOW: Task 1's `done` says "version shown" for an installed openspec; in the real (non-faked) refresh `_ver_cell` depends on `self._version_statuses.get(tool.id)` (catalog_tui.py:520), so if the service yields no status the cell renders the dim "no version" marker — consistent, but not literally "the version shown". The RED test fakes the service, so the guarantee covers the mechanism, not the live data.
- LOW (unverified beyond inference): I did not fully read `_parse_by_harness` (model.py:448+), so I did not byte-verify that the new prose line `"or, instead, from the obra marketplace:"` passes registry parsing; existing `by_harness` values already contain spaces and the `instructions` list already contains full prose sentences (registry.toml:3089-3092), so free text is evidently accepted — risk minimal.

**Suggestions:** None required. Optionally fix the three cosmetic read_first anchors (test_registry.py:1990; ownership.py:745; guidance.py:58) in passing; they cost one line and close the round-1 LOW completely.

**Risk Assessment:** LOW — every mechanism was traced to real source and holds; the only residual items are cosmetic anchors and one parser check whose existing data makes failure very unlikely.

### Batch verdict
Unresolved HIGH findings: 0
Unresolved non-HIGH findings that still need a plan change: 0 (the LOW anchor nits and the moot codegraph restatement are cosmetic and do not require a plan change before execution)

### Round-2 adjudication and plan fixes

| Finding | Severity | Plan | Fix | Status |
|---|---|---|---|---|
| Opener regex treats `$(( 1 << MASK ))` (word right operand) as a heredoc, swallowing the rest of the file (under-report regression) | LOW (actionable) | 16-17 Task 2 | open-arithmetic check (`masked[:m.start()].rfind("((") > ...rfind("))")`) plus a negative test line | resolved |
| `<< -EOF` and space-containing quoted delimiters mis-tracked (fail-safe direction) | LOW | 16-17 Task 2 | named in the `shortcut:` comment | resolved |
| Task 1 lstrip rationale inaccurate; Tasks 3-5 `fails_when` lack the RED-passed guard; IN-02 anchor | LOW | 16-17 | rationale reworded, guard added to every `fails_when`, anchor names `_judge_line` | resolved |
| 16-18: residual cosmetic anchors (test_registry.py def line differs between reviewer passes, `_native_owner`/`_writer_next_step` def lines); moot codegraph restatement (repo has no `.codegraph/`) | LOW | 16-18 | none (read_first hints only; the restatement is a mandated line) | advisory |

## Consensus Summary (cycle 3)

Single reviewer identity (`opencode-glm-5.2`), two rounds, two plans. Every reviewer claim that drove a change was re-checked against source by the orchestrator (the HIGH: a quote-blanking mask cannot match a quoted delimiter, rcclean.py:43-46).

### Agreed Strengths
- Both plans anchor every fix to real code with working RED fixtures (hand-traced by the reviewer), keep the guard/strip single-walk invariant (`_path_line_targets`), and plan no mutation path change: the 16-17 fixes close the one corruption-capable defect (WR-02) and the guard dead end (WR-01) fail-closed; the 16-18 fixes are display-layer or label-only.
- Accepted findings carry sound rationales (label-only or fail-closed harm, fix cost above risk); IN-03 conflicts with IN-18's no-duplicate-harness rule and the registry's two legitimate marketplaces.
- Hygiene: `cross_ai: true`, `gap_closure: true`, waves 8 then 9 (no concurrent edits or gates), `<threat_model>`, safety rules, final `make validate && make test` task.

### Agreed Concerns
None open at HIGH or actionable MEDIUM after round 2.

### Divergent Views
None (single reviewer).

## Verification coverage (cycle 3)
| Round | Plans | Reviewer | Tree verified | Sections | HIGH | Needs plan change (after fixes) |
|---|---|---|---|---|---|---|
| 1 | 16-17, 16-18 | opencode-glm-5.2 | 920abef + untracked plans | 2/2 | 1 (16-17) | 0 (HIGH + 4 MEDIUM fixed) |
| 2 | 16-17, 16-18 | opencode-glm-5.2 | 920abef + revised plans | 2/2 | 0 | 0 (2 actionable LOWs in 16-17 fixed; cosmetic anchors advisory) |

Not covered: execution of either plan (traces were by hand; no test was run), and the final text of 16-17 after the round-2 LOW fixes (checked by the orchestrator only).

## Cycle Verdict (cycle 3)
- **current_high = 0**
- **current_actionable = 0** (round 1 raised 1 HIGH and 4 MEDIUM, all fixed; round 2 raised 2 actionable LOWs, fixed; 2 convergence rounds of the 3 allowed)

## Cycle 4 (plan 16-19, gap closure for 16-REVIEW-2.md NR-01..NR-04)

Reviewer: `opencode-glm-5.2` (read-only plan agent), two rounds.

### Round 1
| Concern | Severity | Plan | How addressed | Status |
|---|---|---|---|---|
| NR-02 fix alone re-enrolls `export PATH=... FOO=1` as a strip candidate (`plain_only` stays True) and keeps a false `_REFUSE_REPLACE` reason | MEDIUM | 16-19 Task 1 | `suffixed` flag makes the line non-simple: `_REFUSE_COMPOUND`, never a strip candidate; RED test asserts both; T-16-50 widened | resolved |
| must_have claimed quoted `export PATH="..." FOO=1` is reported; it is not (quote-blind colon split, pre-existing) | MEDIUM | 16-19 NR-02 truth + Task 1 | scoped to unquoted; second test pins the quoted limit | resolved |
| Task 3 (b) expected string imprecise (ends with restart + backup sentence) | LOW | Task 3 | full string spelled out | resolved |
| `-k` expression matched no test name | LOW | Task 1 | test names pinned, `-k extra_assignments` | resolved |
| `@CLAUDE.md` does not exist | LOW | context | `@AGENTS.md` | resolved |
| codegraph restate vs no `.codegraph/` index | LOW | objective | conditional wording | resolved |
| SAFE_FIX literal vacuous in guidance.py; wizard_app.py:~549 body text | LOW | Task 2 | clarified, line left untouched | resolved |
| test-local `_RESTART_GUARD` could become dead code | LOW | Task 3 | keep only as compose source or delete | resolved |

### Round 2
Full re-trace (suffixed flag vs every existing IN-02/export test, `then export`, test names, NR-01/NR-04 strings): no new or unresolved findings.

## Cycle Verdict (cycle 4)
- **current_high = 0**
- **current_actionable = 0** (round 1: 2 MEDIUM + 6 LOW fixed; round 2 clean; 2 of 3 allowed rounds used)

Not covered: execution of the plan (traces by hand, no test run); single reviewer identity.
