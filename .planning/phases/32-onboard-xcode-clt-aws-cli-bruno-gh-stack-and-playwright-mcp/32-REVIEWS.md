---
phase: 32
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-21T09:45:00Z
plans_reviewed: [32-01-PLAN.md, 32-02-PLAN.md, 32-03-PLAN.md, 32-04-PLAN.md, 32-05-PLAN.md, 32-06-PLAN.md, 32-07-PLAN.md, 32-08-PLAN.md, 32-09-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 32

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at b2105e86)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 06:36 | opencode-referee-one | one-shot probe | OK |
| 06:36 to 06:39 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null` | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used. A read-only `gsd-plan-checker` pass ran beside it (1 blocker, 3 warnings, 3 info; folded in below).

## Orchestrator verification of the cycle 1 concerns

Cycle 1 of 3 (cap rule after cycle 3; extra cycle only if the real HIGH count is still falling). Plan-internal findings were checked against the cited plan lines; claims that rest on repository code (`installer/run.py`, `installer/session.py`, `installer/status.py`, `installer/agent_settings.py`, `scripts/container-e2e-verify.sh`) are for the planner to verify against source and fix or reject with a stated reason in the Round 1 ledger. DECISIONS apply exactly; all are provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (32-01, 32-02) | The default runner (`engine.install_tool` -> `run_command`, `installer/run.py:78-85`) does not close stdin, so a fixed-argv install or update child can block for input | Real by the referee's reading; planner verifies. Close stdin (DEVNULL) on every real route these fixed-argv commands run through (install, update, remove) and test the production runner with a child that reads stdin and sees EOF. |
| H2 (32-01) | The validator does not enforce its prohibitions: registry argv such as `["xcode-select","--install"]` or `["sh","-c","xcode-select"]` passes the elevation checks; the AST scan covers Python literals only | Real. At registry load refuse, for `install`, `update` and `remove` argv: elevation heads (existing), shell heads (`sh`, `bash`, `zsh`, `dash`, `fish`, path-qualified too) and the head `xcode-select`; test each; keep the Python AST guard as the second line. |
| M1 (32-02) | `is_installed` checks `tool.cmd` on PATH before `detect_path` (`installer/status.py:168-184`), so an unrelated `gh-stack` executable suppresses the install | Real by the referee's reading; planner verifies. Make detection manifest-only for gh-stack (a `cmd` that cannot match a real PATH executable, as the Xcode precedent) and test an absent manifest with a matching PATH executable. |
| H3 (32-03) | AWS requires `unzip`; on a brew-capable host without unzip the plan executor blocks the dependent before the ladder reaches brew (`installer/session.py:525-563`), so the fallback is unreachable | Real by the referee's reading; planner verifies. Make the fallback reachable: do not let an unmet manual `unzip` block a tool that has a brew method (method-scoped need if the model has one; else drop the tool-level `unzip` requirement and let the vendor script fail closed with its own message); add a public plan-building and execution test on a brew host without unzip. |
| H4 (32-04) | Rollback removes shortest-first ancestors, so an originally existing empty `mcp` object can be deleted; the ledger's `created_parent` is a Boolean | Real by the plan lines (32-04:108-117) and the Boolean field (`installer/agent_settings.py:283-287`); planner verifies. Record which ancestors the installer created (a list) and remove only those; test a pre-existing empty parent. |
| H5 (32-04) | The whole-server presence check runs before `_apply_once`, which rereads and checks keys independently; a concurrent change can duplicate or supplement a server | Real. The presence check runs inside the write snapshot (retry-safe); test an alternate shape appearing between the reads. |
| H6 (32-04) | Codex is written as three ledger keys but revert evaluates them individually, so editing one field removes the other installer-owned fields | Real. The Codex server is one ownership unit: revert removes the table only when all three keys still hold the recorded values, else keeps the whole server and reports it; test an edited field. |
| M2 (32-04) | Append order vs the splice that inserts before the first member; "any existing server yields `set_by_you`" vs a second call yielding `already` | State and test the order and the repeat-call semantics once. |
| H7 (32-05, checker W2) | A missing tool gets an INSTALL row without steps (`installer/session.py:736-754`) and INSTALL runs the engine, so the Claude consent step is not reachable on the initial install; `hook_register` appears only from `version_status` on a later run | Real (checker verified `version_status.py:887-934`). DECISION: at install, when Claude is present and consent has not been given, the install result carries one warning line that names the next step AND the exact `claude mcp add ...` hand-off command; the reconfigure flow (drift row, plan confirmation, `--yes`) lists the consent step. Test the install-time warning, the reconfigure step, denial and `--yes` through the public flow. Mark provisional and record the deviation from D-15's wording. |
| M3 (32-05) | The step text does not disclose the possible `~/.claude/settings.json` env write | Real. The confirmation text names both files and the env key before consent. |
| M4 (32-05) | A bare or non-executable `bunx` can be registered | Real. Register the absolute resolved `bunx` (the `resolve_bun` sibling) and skip with a named warning when none is executable; test it. |
| M5 (32-05) | The removal preview omits the cross-agent settings changes | Real. The removal preview lists the exact host files and keys that will be reverted. |
| H8 (32-06) | The exit trap `(exit "$rc"); landing_teardown` can terminate before `landing_teardown` under `set -e`, leaving the Fedora container | Real by the plan line (32-06:174) and the script's `set -e`. Preserve the exit status without errexit firing (capture `rc`, clear the trap, run both teardowns, then `exit "$rc"`); test with a failing step. |
| H9 (32-06) | The no-gpg cleanup always returns success and the reused teardown verifies only its own container, so a failed no-gpg removal can still print the success marker | Real. Verify both containers are absent and fail the marker otherwise; test a failed removal and a failed listing. |
| M6 (32-06, 32-08, 32-09) | The shared gate checks that each prefix starts some line, not one-each-in-order | Real. The shared gate checks verdict count (exactly one each) and order; test duplicated and reordered verdicts. |
| H10 (32-07, checker W3) | The Bruno container result never reaches the shipped entry: 32-03 leaves `smoke_argv` default, 32-07 reports, 32-09 edits comments only | Real. 32-09 reads the recorded Bruno line and applies it: a PASS keeps the default and records it; a result that names a working smoke mode sets `smoke_argv` to that argument list (data, tested); an UNPROVEN with no working mode keeps the default and states the limit in `# Verified`; D-08 stays flagged provisional. |
| M7 (32-07, 32-08) | An earlier exact skip-list test must change but its file is omitted from the later plans' files lists and commits | Real. List every modified earlier test file in the later plan's `<files>` and commit. |
| M8 (32-09) | Conflicting test-first order (RED before editing, then write the test after the edit) | One order: write the tests, record RED, edit the comments, rerun. |
| W4 (checker) | 32-04 writes the OpenCode 2 shape with no version detection | DECISION: write `mcp.servers.playwright` only when `mcp` is absent or has a `servers` object (v2 shape) or a v1 `playwright` entry exists (kept); when `mcp` holds v1-shaped members and no `servers`, skip with a `partial:` note naming the manual step; test both shapes. |
| I (checker info) | 32-02 lists `tests/test_executors.py` without an edit; 32-09's grep targets the entry body not the comment block; the AST guard match must stay exact | Fix the file list; point the grep at the comment block; state that the guard compares the first element to exactly `"xcode-select"` (the existing `("/usr/bin/xcode-select", "-p")` in `installer/status.py` must keep passing). |
| W1 (checker) | RESEARCH open questions not marked resolved | Done by the orchestrator (`## Open Questions (RESOLVED)`). |
| X (cross) | Final gates with the default TMPDIR instead of an owned directory | REJECTED, no plan change: a long TMPDIR breaks `tests/test_doctor.py::test_run_doctor_reports_broken_links_and_changes_nothing` (observed in phase 30); every scratch directory the plans create is owned and trapped. |

## OpenCode Review (opencode-referee-one), cycle 1

Using the plan-review checklist to check all nine plans against the current source and their shared requirements.
Using parallel reviewers for the lifecycle, MCP, and container-plan sections; I’ll check their findings against the source.
### Document Type

GSD · implementation plans

### Overall verdict

**Issues found — revise and re-review before execution.** The plans have concrete lifecycle, consent, rollback, and container-cleanup gaps. The most urgent are the initial Claude consent flow, the MCP writer’s rollback and race behavior, and the AWS container exit trap.

Evidence below uses **`P`** for `.planning/phases/32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp`.

## 32-01

1. **Summary:** Adds fixed-argv script installs, closed hand-off names, and a per-method preference.
2. **Findings status:** First review cycle; no prior cross-AI findings.
3. **Strengths:** The plan preserves the existing rank ladder and tests the new keys at the registry boundary (`P/32-01-PLAN.md:121-125`, `:160-165`; `installer/model.py:543-559`).
4. **Concerns:**
   - **HIGH — stdin is not closed by the default runner.** The plan relies on that guarantee (`P/32-01-PLAN.md:26-29`, `:132`), but `engine.install_tool` defaults to `run_command` (`installer/engine.py:162-166`), which calls `subprocess.run` without closing stdin (`installer/run.py:78-85`). The separate output runner uses `DEVNULL` (`installer/run.py:103-118`). A child can therefore block for input.
   - **HIGH — the proposed validator does not enforce its execution prohibitions.** `P/32-01-PLAN.md:123-132` rejects elevation heads and invalid tokens, but the existing checks accept ordinary literal heads (`installer/model.py:482-490`, `:550-559`). Thus registry argv such as `["xcode-select", "--install"]` or `["sh", "-c", "xcode-select"]` can pass the described checks. An AST scan of literal Python lists does not inspect registry-supplied argv.
5. **Suggestions:** Close stdin on every real route used by these commands and test the production runner. Enforce the no-shell and prohibited-command contract at the registry-to-runner boundary, including path-qualified heads.
6. **Risk Assessment:** **High:** the proposed mechanism does not yet guarantee non-interactive or prohibited-command behavior.

## 32-02

1. **Summary:** Adds the Xcode CLT hand-off and gh-stack entries.
2. **Findings status:** First review cycle.
3. **Strengths:** The hand-off is explicitly display-only, and gh-stack removal is limited to a receipt-proven path (`P/32-02-PLAN.md:120-125`, `:163-167`).
4. **Concerns:**
   - **MEDIUM — gh-stack detection is not manifest-only.** The plan says an absent manifest means absent and treats `gh-stack` as a never-resolving probe (`P/32-02-PLAN.md:28-29`, `:163-165`, `:174`). In fact, `is_installed` checks `tool.cmd` on PATH before `detect_path` (`installer/status.py:168-184`). An unrelated `gh-stack` executable can suppress installation.
   - **HIGH — the non-prompt guarantee depends on 32-01’s runner defect.** The planned install and update use the runner (`P/32-02-PLAN.md:163-166`); the default runner inherits stdin (`installer/run.py:78-85`).
5. **Suggestions:** Test an absent manifest with a matching PATH executable and make the detector and stated contract agree. Verify unauthenticated install and update through the real non-interactive runner.
6. **Risk Assessment:** **High** until the runner guarantee is fixed; otherwise medium for false-positive detection.

## 32-03

1. **Summary:** Adds script-first AWS CLI and pinned Bruno AppImages with a macOS cask.
2. **Findings status:** First review cycle.
3. **Strengths:** Bruno pins are architecture-specific, and AWS removal paths exclude credentials (`P/32-03-PLAN.md:119-125`, `:159-164`).
4. **Concerns:**
   - **HIGH — the brew fallback can be blocked before the ladder runs.** AWS requires `unzip` and the fallback test calls the engine directly (`P/32-03-PLAN.md:119-123`, `:131`). In the actual plan executor, a manual dependency becomes unresolved and blocks the dependent before installation (`installer/session.py:525-563`). The unzip entry documents that native installation can be a manual hand-off (`installer/registry.toml:1901-1911`). Thus a brew-capable host lacking unzip may never reach the promised fallback.
5. **Suggestions:** Add a public plan-building and execution test for missing unzip on a brew-capable host, and make the dependency and fallback contracts agree.
6. **Risk Assessment:** **High:** a user-visible fallback can be unreachable despite a passing engine-level test.

## 32-04

1. **Summary:** Extends the settings ledger to write and revert MCP registrations.
2. **Findings status:** First review cycle.
3. **Strengths:** The design reuses the guarded ledger and specifies file/key allow-lists (`P/32-04-PLAN.md:143-149`, `:155-158`; `installer/agent_settings.py:1155-1187`, `:1242-1261`).
4. **Concerns:**
   - **HIGH — rollback can remove a pre-existing parent.** The shortest-first ancestor removal (`P/32-04-PLAN.md:108-109`, `:116-117`) deletes an originally existing empty `mcp` object if its only remaining content is the created chain. The ledger’s `created_parent` is only a Boolean (`installer/agent_settings.py:283-287`), so it cannot identify which ancestor was created.
   - **HIGH — whole-server checks race with the write snapshot.** The plan checks for an existing server before calling `_apply_once` (`P/32-04-PLAN.md:155-157`), but `_apply_once` independently rereads and checks individual keys (`installer/agent_settings.py:935-965`). An alternate OpenCode shape or partial Codex table created between those reads can be supplemented or duplicated.
   - **HIGH — Codex rollback is key-wise, not server-wise.** The plan writes Codex command, args, and env as separate ledger keys (`P/32-04-PLAN.md:155`) but promises a changed server is kept (`:148`). Existing revert evaluates and removes entries individually (`installer/agent_settings.py:1089-1120`): editing one field can leave that field while removing the other installer-owned fields, breaking the user-edited server.
   - **MEDIUM — ordering and repeat-call expectations conflict with the action.** Existing JSON insertion places the member before the first existing member (`installer/agent_settings.py:312-325`), while the plan requires append order but says to retain the splice (`P/32-04-PLAN.md:107`, `:116`, `:146`). It also says any existing server yields `set_by_you` (`:157`) but requires a second call to yield `already` (`:146`).
5. **Suggestions:** Preserve actual creation provenance; check whole-server absence within every write/retry snapshot; make Codex revert atomic at the server level; specify append and repeat-call semantics with tests.
6. **Risk Assessment:** **High:** these gaps affect user configuration preservation.

## 32-05

1. **Summary:** Wires the pinned Playwright hook, consent host, and removal sweep.
2. **Findings status:** First review cycle.
3. **Strengths:** The plan separates Claude from automatic host registration and limits the intended removal to Playwright ledger settings (`P/32-05-PLAN.md:31-35`, `:143`, `:153`).
4. **Concerns:**
   - **HIGH — the initial install has no executable consent step.** The plan promises Claude registration through a confirmed step (`P/32-05-PLAN.md:31-32`, `:142`, `:151-152`), but a missing tool gets an INSTALL row without steps (`installer/session.py:736-754`), and INSTALL executes the engine rather than reconfiguration (`installer/session.py:549-563`). The test describes obtaining a *later* drift plan, not consent and registration during the initial install.
   - **HIGH — confirmation does not disclose the settings-file write.** The planned step names Claude registration (`P/32-05-PLAN.md:78`, `:142`), whereas the existing step text says only “register … for …” (`installer/version_status.py:922-934`). It does not disclose the possible `~/.claude/settings.json` environment change before consent.
   - **MEDIUM — a bare or non-executable `bunx` can be registered.** The plan falls back to bare `bunx` and checks sibling existence (`P/32-05-PLAN.md:82`, `:140`, `:151`). `resolve_bun` can find bun elsewhere on PATH (`installer/bun_globals.py:43-57`); a GUI host’s later PATH may differ. The registration can be reported successful without a usable command.
   - **MEDIUM — removal preview omits the cross-agent changes.** The new sweep changes several hosts (`P/32-05-PLAN.md:143`, `:153`), but the current preview only includes a tool’s own agent settings (`installer/app.py:545-579`).
5. **Suggestions:** Within the chosen consent route, show the potential files and key before confirmation, execute the step after a successful initial install, and test denial and `--yes` through the public flow. Validate a usable command and preview the exact settings to revert.
6. **Risk Assessment:** **High:** the planned consent behavior is not reachable or sufficiently disclosed on the initial install.

## 32-06

1. **Summary:** Adds AWS container evidence, including a no-gpg leg and a shared transcript gate.
2. **Findings status:** First review cycle.
3. **Strengths:** The gpg shim and separate no-gpg leg test distinct claims; the transcript digest binds the recorded result to the run (`P/32-06-PLAN.md:25-30`).
4. **Concerns:**
   - **HIGH — failure can bypass Fedora cleanup.** The specified trap uses `(exit "$rc"); landing_teardown` (`P/32-06-PLAN.md:174`). Under the script’s `set -e`, a nonzero subshell can terminate the trap before `landing_teardown`; that function is responsible for the Fedora container (`scripts/container-e2e-verify.sh:2834-2854`).
   - **HIGH — no-gpg cleanup can be falsely reported as successful.** The plan makes that cleanup always return success (`P/32-06-PLAN.md:174`), while the reused teardown verifies only its landing container (`scripts/container-e2e-verify.sh:2843-2853`). A failed no-gpg removal can still leave the final success marker.
   - **MEDIUM — the shared gate does not enforce the promised sequence.** The plan promises one verdict each in order (`P/32-06-PLAN.md:27`) but specifies only that each prefix starts *some* line (`:130`), mirroring the existing presence-only model (`tests/e2e_herdr_app_driver.py:287-297`). Duplicated or reordered verdicts can pass.
5. **Suggestions:** Preserve exit status without triggering `errexit`, verify both containers are absent, and test failed removal and listing. Check verdict count and order in the shared gate.
6. **Risk Assessment:** **High:** a failed run may leave a container or produce an unjustified teardown success.

## 32-07

1. **Summary:** Adds a Bruno AppImage container check with explicit UNPROVEN results.
2. **Findings status:** First review cycle.
3. **Strengths:** UNPROVEN is distinguished from PASS, and seeded collections and settings are checked after removal (`P/32-07-PLAN.md:24-26`, `:107-111`).
4. **Concerns:**
   - **HIGH — the discovered smoke arguments never reach the shipped entry.** The plan tests modes and reports the result (`P/32-07-PLAN.md:108-109`, `:117`), but 32-03 leaves `smoke_argv` unset and 32-09 only edits the comment (`P/32-03-PLAN.md:170`; `P/32-09-PLAN.md:122-123`). The production default accepts many nonzero exits and timeouts as “ran” (`installer/executors.py:86-119`). The container result therefore does not confirm the smoke configuration users receive.
   - **MEDIUM — an earlier exact skip-list test must change but is absent from staging.** Plan 06 requires an exact assertion (`P/32-06-PLAN.md:165`); this plan permits updating it (`P/32-07-PLAN.md:149`) but omits `tests/test_container_e2e_aws_cli.py` from the task files and commit (`:136`, `:156`). A locally passing tree can produce a failing commit.
5. **Suggestions:** Carry a proven smoke result into the shipped configuration, or explicitly retain it as unproven. Include all changed prior tests in the task and staging lists.
6. **Risk Assessment:** **High** for the claimed runtime proof; medium for intermediate-commit integrity.

## 32-08

1. **Summary:** Adds a container test for registration, consent, and MCP launch.
2. **Findings status:** First review cycle.
3. **Strengths:** The smoke launches the command read from the registered entry and specifies bounded process-group cleanup (`P/32-08-PLAN.md:65-66`, `:119-120`).
4. **Concerns:**
   - **MEDIUM — prior skip-list test edits are again omitted from staging.** The plan explicitly requires updating earlier exact-list assertions (`P/32-08-PLAN.md:161`) but omits those prior test files from the task file list and four-file commit (`:148`, `:168`).
   - **MEDIUM — evidence ordering depends on the insufficient shared gate.** This plan promises one line per verdict in order (`P/32-08-PLAN.md:26`) but reuses 32-06’s presence-only gate (`P/32-06-PLAN.md:130`).
5. **Suggestions:** Stage every modified skip-list test and inherit the strengthened count-and-order gate from 32-06.
6. **Risk Assessment:** **Medium:** the test evidence and committed tree can disagree.

## 32-09

1. **Summary:** Gates publication of container evidence and adds cross-entry guards.
2. **Findings status:** First review cycle.
3. **Strengths:** The plan checks recorded AWS and Playwright evidence before edits and includes negative date and digest cases (`P/32-09-PLAN.md:24`, `:119-120`).
4. **Concerns:**
   - **MEDIUM — the task gives conflicting test-first order.** It requires RED evidence before editing (`P/32-09-PLAN.md:66`, `:121`) but then says to write the same test module after the registry edit (`:122-123`).
   - **MEDIUM — the final gate inherits the ordering gap.** It relies on 32-06’s shared gate (`P/32-09-PLAN.md:24`, `:119`), whose specified transcript check does not enforce the one-each, ordered sequence (`P/32-06-PLAN.md:27`, `:130`).
5. **Suggestions:** Specify one order—write tests, record RED, edit comments, rerun—and use the strengthened shared gate.
6. **Risk Assessment:** **Medium:** closure is blocked or evidence is weaker than the plan claims.

## Cross-plan assessment

- **Waves and size:** The declared waves are sequential (`P/32-01-PLAN.md:6-7` through `P/32-09-PLAN.md:6-7`), and the files are each under the stated approximate 55 KB limit. The skip-list staging omissions above remain a cross-wave commit-integrity issue.
- **Scratch cleanup:** All plans direct `make validate` and `make test` to use default `TMPDIR` rather than an owned run directory—for example, `P/32-01-PLAN.md:78`. That conflicts with the host instruction to export an owned `TMPDIR` and clean it on every exit (`/var/home/bazzite/.config/opencode/AGENTS.md:41-51`). Resolve the long-path test constraint with a short owned directory rather than leaving full-suite scratch ownership unspecified.
- **Provisional decisions:** This review does not reopen the stated provisional choices. The findings concern whether the plans implement those choices and satisfy their safety and evidence claims.

### Status: Issues Found — fix and re-invoke

No code, plans, or repository files were changed. No tests or real container runs were performed, and no scratch directory was created. Real macOS, Bazzite, vendor, and agent-host behavior remains unverified.
