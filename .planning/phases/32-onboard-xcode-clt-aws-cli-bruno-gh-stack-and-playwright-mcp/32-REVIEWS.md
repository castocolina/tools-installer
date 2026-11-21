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


## Lane Log (convergence cycle 2, plans at 300cd399)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 07:19 | opencode-referee-one | one-shot probe | OK |
| 07:19 to 07:22 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 2 concerns

Cycle 2 of 3. Real HIGH by cycle: 10, now 9 distinct (three of the reported 13 are duplicates across plans); they are second-order (gaps in the first-round fixes). Plan-internal findings were checked against the cited lines; code facts are for the planner to verify. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (32-01, 32-02) | Closing stdin does not stop a child from opening `/dev/tty`; the streaming and captured runners use a new session for that, the console route keeps the terminal session | Real by the referee's reading (`installer/run.py:103-119,335-350`; planner verifies). Run the fixed-argv install, update and remove children in a new session on the console route too (as the other runners do) and test with a child that tries to open `/dev/tty` through the production runner. |
| H2 (32-01) | The validator checks only the first argv token, so `["env","xcode-select","--install"]` or `["env","sh","-c",...]` pass | Real. Refuse a registry `install`, `update` or `remove` argv when ANY token's basename is an elevation command, a shell, `xcode-select`, or a launcher (`env`, `exec`, `command`, `nohup`, `nice`, `time`, `timeout`, `xargs`); test each position at registry load; the Python AST guard stays as the second line. |
| L1 (32-02) | "manifest-only" is stronger than the detector guarantees (`gh-stack-extension` on PATH is still checked first) | Describe the probe-name limit accurately in the plan and the `# Verified` comment; add a test with an executable named like the probe. |
| M1 (32-03) | The no-brew test expects `RowOutcome.detail` to contain `gpg not found`, but a failed install leaves that field empty (errors live in `outcome.install.errors`) and `run_command` does not capture the vendor stderr | Real by the referee's reading (`installer/session.py:589-601`; planner verifies). Specify how the diagnostic reaches the user on the real runner and test the public outcome and the rendered message; if the vendor message is only streamed, assert what the outcome does carry (the failing command and exit status) and state the limit. |
| H3 (32-04) | The MCP file is ADDED to the ordinary settings-file allow-list, so a forged MCP ledger entry can target the same agent's ordinary settings file | Real (32-04:173-174 vs :214-217; `installer/agent_settings.py:1169-1184,1232-1253`). Allow-list (file, key path) PAIRS: an MCP setting may only revert in the MCP file and an ordinary setting only in its ordinary file; test a forged MCP entry aimed at the ordinary settings file and the reverse. |
| M2 (32-04) | Codex's ownership unit is undefined for the two-key case (no env) and when env is added later | Define and test grouped equality and rollback for the two-key and three-key registrations, and for env added later by the user. |
| H4 (32-05, 32-08) | The consent step is disclosed for the hosts pending at planning time but `register_hooks(..., confirmed=True)` re-reads the present hosts at execution, so a Claude host appearing between planning and execution is written without disclosure | Real by the plan lines and the referee's reading (`installer/session.py:331-341`, `installer/postinstall.py:663-666`). Bind execution to the hosts disclosed in the confirmed step (a `confirmed_hosts` set); a host that appears later is not written and is reported pending; test a host appearing between plan and execution in the public flow (32-05) and in the container driver's seeding (32-08). |
| H5 (32-05) | The Flatpak Chrome export is gated only by the wrapper file's existence, not Bazzite | Real (SPEC: "on Bazzite only"). Gate on the platform facts (`installer/platform.py`: immutable Fedora family) AND the wrapper file; test a non-Bazzite host with the wrapper present. |
| M3 (32-05) | The preview evaluates Codex keys individually while revert groups them | The preview shares the revert's grouped decision and allowed-file set. |
| M4 (32-05) | The preview excludes files outside home (external `COPILOT_HOME`) | Name the limit in the preview text (a line saying an external Copilot home is reverted but not listed) and test it. |
| M5 (32-05) | The `claude mcp add` hand-off interpolates the absolute `bunx` path unquoted | Quote every dynamic argument with `shlex.quote`; test a path with a space. |
| H6 (32-06) | The no-gpg verdict receives only an exit code and output, so a script that leaves artifacts before printing `gpg not found` still earns `TRACER_AWS_NOGPG_OK` | Real. Feed the no-gpg container's install-path evidence (a listing of the declared install paths and `~/.local/bin` after the run) into the verdict: anything created fails it; test a script that leaves a file. |
| M6 (32-06, 32-09) | The gate requires the teardown line to START WITH the marker and be the last non-empty line, while 32-09 promises the marker as the last line (the model gate checks exact equality) | Exact line equality for the teardown marker with one consistent trailing-blank rule, in the shared gate and in 32-09's text. |
| M7 (32-06) | Task 2 says to run `make shellcheck` by hand | Remove it; the commit hook runs the static gates (run one by hand only to diagnose a failure). |
| H7 (32-07, 32-09) | A proven `extract-no-sandbox` mode needs `APPIMAGE_EXTRACT_AND_RUN=1` but `smoke_argv_for` propagates only argv, while the shipped smoke carries only display variables and TMPDIR, so the applied smoke differs from the proven invocation | Real (`installer/executors.py:86-110`). Apply a recorded mode to the entry only when the shipped smoke reproduces it (argv-only modes); a mode that needs environment variables the shipped smoke cannot carry is NOT applied: keep the default and state the limit in `# Verified`; test both branches. |
| H8 (32-09) | A summary line that is literally `PASS` but whose transcript fails verification can still become proof wording because 32-09 branches on the copied line | Real (32-07:115,122 vs 32-09:25-26,116,125-127). Branch only on the VERIFIED result of `recorded_smoke_mode`; an unverifiable record produces no proof wording; test a PASS line with an altered transcript. |
| X (cross) | Final gates with the default TMPDIR instead of an owned directory | REJECTED again, no plan change beyond keeping the ruling in the 32-01 ledger: the doctor test `tests/test_doctor.py::test_run_doctor_reports_broken_links_and_changes_nothing` wraps its output by path length and failed under executor-owned TMPDIRs in phase 30; every scratch directory the plans create is owned and trapped. |

## OpenCode Review (opencode-referee-one), cycle 2

Using the plan-review checklist to review the current files against the source and the previous cycle’s findings.
Using parallel reviewers for the lifecycle, MCP, and container plans; I’ll independently check the cross-plan evidence and reported findings.
**HIGH — Bazzite-only export is not enforced.** `32-05-PLAN.md:160-161` selects the Flatpak Chrome wrapper solely by file existence; `installer/platform.py:19-24` distinguishes platform and immutability, but the plan does not use those facts. A non-Bazzite host with that wrapper would receive the export.
### Document Type

GSD · implementation plans

### Overall verdict

**Issues found — revise and re-review before execution.** The revised plans address several first-cycle findings, including stdin inheritance, the AWS dependency block, settings-write races, container teardown, and evidence ordering. They still leave gaps in terminal prompting, consent binding, ledger safety, and container-proof propagation.

Plan references below use **`P`** for `.planning/phases/32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp`.

## 32-01

1. **Summary:** Adds fixed-argv script installs, closed hand-off names, and script-before-brew preference.
2. **Findings status:** The prior stdin and direct-head validation findings are addressed in the plan, but the revisions do not cover all routes.
3. **Strengths:** The hand-off is unconditional and direct execution is refused (`P/32-01-PLAN.md:177-190`). The preference preserves the existing kind ladder (`installer/resolve.py:15-31,96-99`).
4. **Concerns:**
   - **HIGH — `/dev/tty` can still prompt.** The plan closes stdin but explicitly keeps the console child in the terminal session (`P/32-01-PLAN.md:136-146`). The existing streaming and captured runners use a new session specifically to prevent reads from the controlling terminal (`installer/run.py:103-119,335-350`). A child can open `/dev/tty` independently of stdin, so the proposed EOF test does not prove the non-prompt guarantee.
   - **HIGH — forbidden commands can pass through a launcher.** The proposed validator checks only the first argv token (`P/32-01-PLAN.md:132-145`). The existing token validator permits `["env", "xcode-select", "--install"]` and `["env", "sh", "-c", "xcode-select"]` (`installer/model.py:482-490,543-559`), and the planned executor passes the list unchanged.
5. **Suggestions:** Isolate console children from the controlling terminal and test `/dev/tty` through the production runner. Enforce the command prohibition for indirect launchers, with registry-load tests for install, update, and remove.
6. **Risk Assessment:** **High:** a fixed-argv child can still prompt or reach a prohibited command.

## 32-02

1. **Summary:** Adds detect-only Xcode CLT and the gh-stack extension.
2. **Findings status:** The earlier unrelated-`gh-stack` PATH false positive is addressed by a distinct probe name; the non-prompt issue remains dependent on 32-01.
3. **Strengths:** Tests cover the exact extension argv, manifest detection, idempotency, and receipt-scoped removal (`P/32-02-PLAN.md:163-168`).
4. **Concerns:**
   - **HIGH — non-prompt behavior inherits 32-01’s console-runner gap.** Install and update use real runner routes (`P/32-02-PLAN.md:163-167`); closing stdin alone does not prevent `/dev/tty` reads (`installer/run.py:78-85,103-119`).
   - **LOW — “manifest-only” is stronger than the detector guarantees.** The alternate probe avoids an executable named `gh-stack`, but `is_installed` still checks the declared `gh-stack-extension` name on PATH first (`P/32-02-PLAN.md:28,163-164`; `installer/status.py:168-184`).
5. **Suggestions:** Inherit the runner fix and either describe the probe-name limitation accurately or test an executable with the declared probe name.
6. **Risk Assessment:** **High** until the runner is non-interactive; the remaining detection risk is narrower.

## 32-03

1. **Summary:** Adds script-first AWS CLI with brew fallback and pinned Bruno AppImages plus cask.
2. **Findings status:** The earlier tool-level `unzip` dependency block is addressed with a public plan-and-execution regression test (`P/32-03-PLAN.md:123-128`).
3. **Strengths:** The plan tests fallback through the public flow and keeps credentials outside declared removal paths (`P/32-03-PLAN.md:123-129`).
4. **Concerns:**
   - **MEDIUM — the specified failure-detail assertion does not match the public flow.** The no-brew test requires `RowOutcome.detail` to contain `gpg not found` (`P/32-03-PLAN.md:127-128`), but ordinary failed installs leave that field empty and retain errors in `outcome.install.errors` (`installer/session.py:589-601`). `run_command` also does not capture the vendor’s stderr in `CommandError` (`installer/run.py:78-85`).
5. **Suggestions:** Specify how the vendor diagnostic reaches the user on the actual runner and test the resulting public outcome and rendered message, rather than asserting an unpopulated field.
6. **Risk Assessment:** **Medium:** the failure test cannot establish the promised user-facing diagnostic as written.

## 32-04

1. **Summary:** Extends the settings ledger for merge-safe MCP writes and reverts.
2. **Findings status:** The first-cycle ancestor-provenance, in-snapshot presence check, and Codex grouped-revert concerns have explicit revisions and regression cases.
3. **Strengths:** The new presence gate is specified inside the write snapshot and on retry (`P/32-04-PLAN.md:163,175-176`); the current writer already reserves the ledger before a guarded write and rolls it back on a detected race (`installer/agent_settings.py:935-1002`).
4. **Concerns:**
   - **HIGH — the MCP revert allow-list is broader than claimed.** The plan *adds* the MCP file to the ordinary settings-file allow-list (`P/32-04-PLAN.md:173-174`) while claiming a forged ledger cannot redirect a revert (`:214-217`). `_revert_file` accepts any path in that list, and dynamic ledger entries supply values for allowed key paths (`installer/agent_settings.py:1169-1184,1232-1253`). A forged MCP ledger entry can therefore target the same agent’s ordinary settings file.
   - **MEDIUM — Codex’s two-key ownership unit is undefined.** The normal no-wrapper case omits `env`, but equality and rollback repeatedly describe three recorded keys (`P/32-04-PLAN.md:157-158,166,173,176,178`). The tests do not define what happens when `env` is absent initially or added later.
5. **Suggestions:** Allow only the intended MCP file or files for the MCP setting, and test a forged entry targeting the ordinary settings file. Define and test grouped equality and rollback for both two-key and three-key Codex registrations.
6. **Risk Assessment:** **High:** a user-writable ledger can direct a revert into an unintended file under the proposed allow-list.

## 32-05

1. **Summary:** Wires Playwright registration, Claude consent, drift reporting, and removal.
2. **Findings status:** The revised plan discloses Claude’s files, requires an executable absolute `bunx`, adds removal preview, and supplies an initial-install hand-off. The initial install still deliberately defers the consent step to reconfiguration.
3. **Strengths:** The existing `run_wizard` confirmation occurs after plan rendering and before execution (`installer/app.py:146-180`); the plan tests both decline and `--yes` (`P/32-05-PLAN.md:189-192`).
4. **Concerns:**
   - **HIGH — a newly appearing Claude host can be written without disclosure.** The disclosure is added only when Claude is pending during planning (`P/32-05-PLAN.md:192,201-202`), but the confirmed step calls `register_hooks` without restricting hosts; it re-reads present hosts at execution (`installer/session.py:331-341`; `installer/postinstall.py:663-666`). If Claude appears after rendering, a step disclosed only for another host can write Claude’s files.
   - **HIGH — the Flatpak export is not Bazzite-only.** The hook checks only whether the wrapper file exists (`P/32-05-PLAN.md:160-161`), despite the roadmap’s Bazzite-only criterion. Platform information exists but is not consulted (`installer/platform.py:19-24,65-76`).
   - **MEDIUM — preview can disagree with grouped Codex revert.** The plan adds a setting filter to the existing per-key preview (`P/32-05-PLAN.md:193-195,203-204`); that preview evaluates keys individually (`installer/agent_settings.py:1404-1427`). If one Codex key changes, it can say the others will be removed although 32-04’s grouped rule keeps the whole server.
   - **MEDIUM — preview omits external `COPILOT_HOME`.** The plan supports and reverts an absolute external Copilot home (`P/32-04-PLAN.md:66,174`), but the existing preview deliberately excludes files outside home (`installer/agent_settings.py:1393-1401`); filtering alone does not change that.
   - **MEDIUM — the hand-off command does not quote dynamic paths.** The command interpolates the absolute `bunx` path directly (`P/32-05-PLAN.md:147,161-162`); `resolve_bun` can derive it from environment paths containing spaces or shell characters (`installer/bun_globals.py:20-25,43-56`).
5. **Suggestions:** Bind execution of consent hosts to the hosts disclosed in the confirmed plan; test a host appearing between planning and execution. Gate the wrapper by the required host condition. Make preview share revert’s grouped decision and allowed-file set, and shell-quote hand-off arguments.
6. **Risk Assessment:** **High:** consent can be applied to an undisclosed write, and the wrapper can affect hosts outside the stated scope.

## 32-06

1. **Summary:** Adds AWS lifecycle and no-gpg container evidence, plus a shared transcript gate.
2. **Findings status:** The prior errexit cleanup, second-container verification, and verdict-order findings have concrete proposed fixes and tests (`P/32-06-PLAN.md:125-127,166-167,177-180`).
3. **Strengths:** The revised trap tests use a real Bash process and a negative control; the existing teardown verifies its own container by listing it (`scripts/container-e2e-verify.sh:2837-2854`).
4. **Concerns:**
   - **HIGH — the no-gpg verdict does not prove “nothing installed.”** It receives only an exit code and output, rejecting an installation only if the output says so (`P/32-06-PLAN.md:27,124,128,180`). A script that silently leaves artifacts before reporting `gpg not found` can still earn `TRACER_AWS_NOGPG_OK`.
   - **MEDIUM — teardown matching is weaker than the final gate’s contract.** Plan 06 requires a line that *starts with* the marker and is the last *non-empty* line (`P/32-06-PLAN.md:134`), while plan 09 promises the marker as the last line (`P/32-09-PLAN.md:24`). The existing gate model checks exact equality (`tests/e2e_herdr_app_driver.py:287-298`).
   - **MEDIUM — Task 2 instructs a prohibited per-commit static gate.** It directs `make shellcheck` (`P/32-06-PLAN.md:180`) despite its own no-manual-static-gate rule (`:79-80`) and `AGENTS.md`’s hook-first rule.
5. **Suggestions:** Inspect the no-gpg container’s install paths and feed that evidence into the verdict. Require an exact teardown line with consistent trailing-blank semantics. Let the hook run shellcheck unless diagnosing a failure.
6. **Risk Assessment:** **High:** the final evidence gate can accept an unproven no-install claim.

## 32-07

1. **Summary:** Adds a Bruno AppImage container check and reports PASS or UNPROVEN.
2. **Findings status:** The prior staging omission is addressed. The prior smoke-propagation finding is only partially addressed.
3. **Strengths:** UNPROVEN remains distinct from PASS, and later staging includes the earlier skip-list test (`P/32-07-PLAN.md:109-116,141,154,161`).
4. **Concerns:**
   - **HIGH — a proven extract mode is not the shipped smoke invocation.** Both extract modes require `APPIMAGE_EXTRACT_AND_RUN=1`, but `smoke_argv_for` propagates only argv (`P/32-07-PLAN.md:112,115-116`). The production smoke inherits the ambient environment and changes only display variables and `TMPDIR` (`installer/executors.py:86-110`). Thus even `extract-no-sandbox` can produce a digest-bound PASS while the shipped invocation lacks the environment that made it work.
5. **Suggestions:** Reproduce both the recorded arguments and environment in the shipped smoke, or treat extract-dependent results as insufficient to select a working shipped smoke.
6. **Risk Assessment:** **High:** the recorded result can be applied as though it proves a different runtime invocation.

## 32-08

1. **Summary:** Adds Playwright MCP container registration and JSON-RPC launch checks.
2. **Findings status:** The prior skip-list staging and inherited verdict-order findings are addressed in the plan (`P/32-08-PLAN.md:123,150,163,170`).
3. **Strengths:** The driver starts the command read from the registered entry, uses bounded process-group cleanup, and distinguishes UNPROVEN from PASS (`P/32-08-PLAN.md:67-68,119-123`).
4. **Concerns:**
   - **HIGH — the container proof does not close the late-host consent gap.** It calls `register_hooks(..., confirmed=True)` after seeding all hosts (`P/32-08-PLAN.md:67,130`), so it cannot exercise a Claude host appearing after a differently disclosed plan was confirmed. The execution-time host read is in `installer/postinstall.py:663-666`.
   - **MEDIUM — final evidence inherits the teardown-marker mismatch in 32-06.** The driver delegates to the shared gate (`P/32-08-PLAN.md:123,130`), whose specified marker check is weaker than 32-09’s promise.
5. **Suggestions:** Add the late-host regression to the public consent flow in 32-05; make the shared marker contract exact before relying on it here.
6. **Risk Assessment:** **High** for the consent boundary; otherwise the container check is appropriately bounded.

## 32-09

1. **Summary:** Gates publication of AWS and Playwright evidence, reports Bruno’s result, and adds consistency guards.
2. **Findings status:** The previous test-first ordering and prior skip-list staging issues are addressed; the strengthened count-and-order gate is inherited from 32-06.
3. **Strengths:** Both required evidence gates run before edits, with negative date and digest samples (`P/32-09-PLAN.md:123-126`).
4. **Concerns:**
   - **HIGH — an unverifiable Bruno PASS can become a published proof claim.** `recorded_smoke_mode` returns no mode for an altered or unverifiable transcript (`P/32-07-PLAN.md:115,122`), but 32-09 also branches on the copied summary’s literal `PASS` and requires successful verdicts and a mode in the paragraph (`P/32-09-PLAN.md:25-26,116,125-127`). These instructions conflict and can promote an unverified line into a claim.
   - **HIGH — extract-mode smoke data remains incomplete.** Applying argv to both architectures (`P/32-09-PLAN.md:26,117,127`) does not carry the environment required by the recorded mode, as described in 32-07.
5. **Suggestions:** Distinguish a raw summary line from a verified Bruno PASS; an unverifiable record must not produce proof wording. Apply a smoke configuration only when the shipped invocation reproduces the verified mode.
6. **Risk Assessment:** **High:** registry evidence can overstate what the verified run proves.

## Cross-plan assessment

- **Waves:** The declared dependencies are sequential, so the repeated edits to `installer/registry.toml`, the container script, and test pins are not scheduled concurrently (`P/32-01-PLAN.md:6-7` through `P/32-09-PLAN.md:6-7`).
- **Scratch cleanup — unresolved from cycle 1:** Every plan directs final `make validate` and `make test` runs to use the default `TMPDIR`, for example `P/32-01-PLAN.md:85`. That conflicts with the mandatory host instruction to use an owned, trapped run directory for every test run. The stated long-path issue does not establish that a **short** owned directory cannot work. This instruction takes precedence over the plans’ rejection of the earlier finding.
- **Execution size:** Measuring the specified executor-visible sections puts each plan below approximately 55 KB; 32-05 has three tasks (`P/32-05-PLAN.md:29-32`), rather than two, but remains below that size threshold.
- **Decisions:** This review evaluates the provisional decisions as requested; it does not ask to reopen them.

### Status: Issues Found — fix and re-invoke

No repository files were changed. No tests, container runs, real host installations, or macOS checks were performed. Graph coverage was best-effort; the new drivers and implementation do not yet exist to verify. No scratch directory was created.
