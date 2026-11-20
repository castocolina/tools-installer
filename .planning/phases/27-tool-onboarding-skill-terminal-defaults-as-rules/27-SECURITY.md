---
phase: "27"
slug: "tool-onboarding-skill-terminal-defaults-as-rules"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-20"
---

# Phase 27 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| judge subagent -> repo and host | A model run with tool access could edit the skill or agent settings while judging | the skill text; no secrets |
| plan executor -> verdict file | An executor model that cannot run the judge could write a plausible verdict instead | verdict JSON (scores) |
| orchestrator -> owner's working tree | The tree carries owner and GSD changes (an untracked goals file) that a cleanup step could destroy | working-tree files |
| skill text -> later onboarding agents | Phases 28-35 act on what the table says is present or planned | skill rules and table rows |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-27-01 | Spoofing | before verdict | medium | mitigate | `autonomous: false`, Task 1 `BLOCKED` halt and a git-proof verify; the before file has one commit (84f567c9) on the unedited skill, its `- Judge:` line names the blob | closed |
| T-27-02 | Tampering | judge subagent | medium | mitigate | Read-only verbatim prompt, before and after tree snapshot diff, `- Judge:` line says read-only; SKILL.md unchanged at the verdict commit (procedure not observable by the auditor) | closed |
| T-27-03 | Tampering | closed table | low | mitigate | `STATUS_RE`, `bad_status_cells` with mutation fixtures, `table_drift` against `load_tools` | closed |
| T-27-12 | Tampering | orchestrator tree check | medium | mitigate | Revert nothing, commit with a trailing pathspec; each verdict commit changes only its verdict file (procedure not observable by the auditor) | closed |
| T-27-04 | Tampering | rule (b) | medium | mitigate | `option_as_alt_unnegated` with mutation fixtures; every Option-as-Alt mention in SKILL.md is negated | closed |
| T-27-05 | Repudiation | step 7 | low | mitigate | `ask_sentences` with fixtures; pinned phrases; Policies sentences verbatim | closed |
| T-27-06 | Tampering | Conflicts | medium | mitigate | Pinned conflict phrases; the real `partial:` line and its `startswith("partial:")` reader are checked in code | closed |
| T-27-07 | Elevation of Privilege | macOS apps | medium | mitigate | Only `~/Applications` and `~/.local/bin` are named; the kitty `/Applications` case is a recorded gap; no `sudo` in the skill | closed |
| T-27-08 | Repudiation | Testing macOS behavior | low | mitigate | `ci.yml` parsed with `yaml.safe_load`; matrix, runner linkage and gated `Test` step checked; fixed-runner and inverted-gate mutation tests | closed |
| T-27-09 | Spoofing | after verdict | medium | mitigate | `autonomous: false`, `BLOCKED` halt, verify with git proof; after file has one commit (522b9ee3) and names blob `6a6f4f8e`; same rubric v4 and spec_sha as the before file (procedure not observable by the auditor) | closed |
| T-27-13 | Tampering | orchestrator tree check in the after loop | medium | mitigate | Snapshot bracket around every judge dispatch, empty diffs reported for both after attempts | closed |
| T-27-14 | Tampering | verdict maxima | low | mitigate | `verdict_regressions` compares `max` with the rubric maxima, mismatched-maxima fixture | closed |
| T-27-10 | Tampering | docs-only classifier | medium | mitigate | `TEST_READ` entry `.planning/*27-SKILLJUDGE-*`, rule-matrix rows, LEDGER rows, `test_every_ledger_glob_reads_test_read_files_only` | closed |
| T-27-11 | Denial of Service | verdict parser | low | mitigate | `json.loads` only, no eval, exec, pickle or `yaml.load`; every defect raises, so a bad verdict is never compared as zero | closed |
| T-27-SC | Tampering | supply chain | low | accept | No dependency, lockfile or manifest changed in the phase (`git diff 963da166 HEAD --stat -- pyproject.toml uv.lock package.json package-lock.json .pre-commit-config.yaml` is empty) | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-27-01 | T-27-SC | The phase adds no dependency, lockfile or manifest entry, so there is no new supply-chain surface to mitigate; the check is a one-line empty diff | orchestrator (autonomous run, ASVS 1) | 2026-11-20 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-20 | 15 | 15 | 0 | gsd-security-auditor (opus), orchestrator-written |

Notes from the audit, none blocking:

- The auditor cannot observe the orchestrator procedures (judge dispatches, scratchpad snapshot diffs, clean-skill checks: T-27-01, -02, -09, -12, -13). Each closure rests on what they left in the repository: blob identity at the verdict commits, single-file verdict commits and commit order.
- The before run's snapshot diff was empty (observed by the orchestrator in the session and noted in the run ledger), but `27-01-SUMMARY.md` does not record it; only the two after-loop runs are recorded in `27-04-SUMMARY.md`. A verdict is written only after a clean diff, so this is a record gap, not a control gap.
- The tree snapshot covers non-ignored files only, and `.claude/` is gitignored in this checkout (`.gitignore:55`), so a new untracked file under the skill directory would not show in it. The plans state this limit and rely on the judge prompt's write ban.
- Update after the code review fixes (2026-11-20): the code review closed WR-04, the push gate's blind spot for untracked skill-judge verdict files (commit `24a73427`), which strengthens T-27-10 and T-27-09; the skill text changed afterwards, so the after verdict was re-judged on blob `5e3411f8` (73.6%, commit `ed84a32c`) and the earlier after verdict (blob `6a6f4f8e`) is kept as `27-SKILLJUDGE-ROUND-2.md`. T-27-09's closure now rests on the new after file; the checks above hold for it.
- The orchestrator compared all three committed verdict JSON lines with the judges' printed output byte for byte (a scratchpad script); one transcription slip in the after file was found and fixed before its commit. The auditor could not check that.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-20
