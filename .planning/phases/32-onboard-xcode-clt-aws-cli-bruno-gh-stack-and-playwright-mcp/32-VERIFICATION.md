---
phase: 32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp
verified: 2026-11-21T14:00:00Z
status: human_needed
score: 5/5 roadmap criteria verified by code and recorded evidence (real-Mac, Bazzite and agent-host behavior listed as human items)
covered_files:
  - .claude/architecture.md
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/agent_settings.py
  - installer/app.py
  - installer/executors.py
  - installer/model.py
  - installer/postinstall.py
  - installer/receipts.py
  - installer/registry.toml
  - installer/resolve.py
  - installer/run.py
  - installer/session.py
  - installer/update.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
covered_digest: "v4:sha256:c54dcf79015136a06f7c687ab43d36b381cc204ba236bf7978e65f4cd738e237"
behavior_unverified: 0
overrides_applied: 0
gaps: []
human_verification:
  - test: "Xcode CLT on a real Mac: missing state, present state, Update refusal, empty Uninstall"
    expected: "Missing shows `xcode-select --install` to run by hand; present shows no command; Update refused; Uninstall lists no action"
    why_human: "Needs a Mac with and without the Command Line Tools; the probe path /Library/Developer/CommandLineTools/usr/bin/git is a Mac fact"
  - test: "AWS install.sh on macOS (or the brew fallback)"
    expected: "Installs under ~/.local/share/aws-cli without admin rights; the pkg `CurrentUserHomeDirectory` route is an assumption"
    why_human: "Real Mac; registry comment marks it assumed"
  - test: "Bruno cask on a Mac"
    expected: "~/Applications/Bruno.app; uninstall keeps ~/Documents/bruno"
    why_human: "Real Mac; cask behavior"
  - test: "Bruno AppImage launch on Bazzite"
    expected: "Mounts through FUSE, runs (sandbox and display behavior); menu entry is follow-up 999.32"
    why_human: "Container result is UNPROVEN (no FUSE in rootless podman, transcript 430723b2c2b1); reported, not gated"
  - test: "gh-stack's data directory on macOS"
    expected: "~/.local/share/gh/extensions/gh-stack/manifest.yml exists after install"
    why_human: "Path assumed on macOS; detection and removal depend on it"
  - test: "macOS agent hosts' MCP files"
    expected: "Cursor, Copilot, OpenCode, Codex and Claude files take the playwright entry at the documented paths"
    why_human: "Real Mac home layout"
  - test: "Playwright with real Flatpak Chrome on Bazzite"
    expected: "Env path exported only on Bazzite with the wrapper present; server launches Chrome"
    why_human: "Container used distro Chromium (D-16); Flatpak Chrome is not in the box"
  - test: "Each agent host loads the `playwright` server"
    expected: "Claude, Cursor, Copilot, OpenCode, Codex list and start it"
    why_human: "Needs each host application; files only are proven"
  - test: "Claude plugin key spelling `enabledPlugins[\"playwright@claude-plugins-official\"]` (assumption A7)"
    expected: "The official plugin check matches the real key"
    why_human: "Needs a real Claude install with the plugin"
  - test: "Pi manual `pi mcp add` step"
    expected: "The hand-off text works in Pi"
    why_human: "Pi has no ledger writer; manual step only"
  - test: "Owner confirmation of the provisional decisions below (D-01, D-03/D-04, D-07, D-08, D-09, D-10/D-11, D-12/D-13, D-14, D-15, orchestrator decisions 1 to 10, review round items)"
    expected: "Each confirmed, or reopened as a follow-up"
    why_human: "Flagged provisional or needs confirmation in the plan summaries"
---

# Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP - Verification Report

**Phase Goal:** Five pending tools are onboarded through the skill, each with its install, detection, update and removal route, without sudo, interactive login or damage to user data.
**Verified:** 2026-11-21
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP criteria) | Status | Evidence |
| - | ------------------------ | ------ | -------- |
| 1 | Xcode CLT: missing on macOS with the exact `xcode-select --install`; no executor runs it; Uninstall offers no removal | VERIFIED (real Mac human) | `installer/registry.toml:3492-3506` (id `xcode-clt`, `kind="script"`, `os=["macos"]`, `detect_path` CLT git, `handoff="xcode-clt"`, no install/paths). `installer/executors.py:743` holds the only hand-off text `"xcode-select --install"`; `installer/model.py:563` `NEVER_RUN_HEADS` refuses xcode-select and softwareupdate in any argv. `tests/test_xcode_clt_entry.py:68` byte-exact command, `:141` `test_xcode_select_is_never_spawned` (grep guard). Re-run: passes. |
| 2 | AWS CLI: official user-scope `install.sh` with gpg, no `--system`, brew fallback, `aws update`, `~/.aws` untouched | VERIFIED | `registry.toml:3552-3578`: script method (url install.sh, `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION="false"`, `prefer=true`, `update=["aws","update"]`, paths exclude `~/.aws`) then brew `awscli`. Orchestrator real run `aws-container: PASS (transcript 9515b665dff5)` in `32-06-SUMMARY.md:50`: INSTALL_OK (gpg --verify logged), RERUN_OK, REMOVE_OK (`~/.aws` byte-identical), NOGPG_OK (fails closed). `tests/test_aws_cli_entry.py`, `tests/test_container_e2e_aws_cli.py` pass (re-run). Recorded in `registry.toml` comments behind the digest-bound evidence gate (32-09). |
| 3 | Bruno: cask on macOS, digest-verified AppImage per arch on Linux, no `bru` | VERIFIED (launch UNPROVEN, human) | `registry.toml:3589-3641`: `tarball` amd64 and arm64 with `version="4.3.0"`, sha256 pins, `raw=true`; `cask` macos `app="Bruno.app"`; no `bru`. `make verify-registry` (32-03 orchestrator note): both AppImage URLs listed under Passed. Container: `bruno-container: UNPROVEN (transcript 430723b2c2b1; no FUSE in rootless podman)`; spec only requires digest-verified install, launch is a human item. `tests/test_bruno_entry.py` passes. |
| 4 | gh-stack: install via `gh extension install https://github.com/github/gh-stack`, update via `gh extension upgrade stack`, removal, unauthenticated gh never blocks | VERIFIED (amended criterion, macOS path human) | `registry.toml:3517-3541`: `install` argv exact, `update=["gh","extension","upgrade","stack"]`, `requires=["gh"]`, detect through manifest `~/.local/share/gh/extensions/gh-stack/manifest.yml`, removal through the receipt-proven folder `paths`. Differs from the literal ROADMAP wording (`gh extension list` detect, `gh extension remove stack`) but ROADMAP SC4 and REQUIREMENTS ONB-14 carry the 2026-11-19 amendment (D-10, D-11, "needs confirmation"). Live evidence in the registry comment: scratch HOME, no token, stdin closed: install exit 0, list/upgrade/remove exit 4 with no prompt. Children run with `DEVNULL` stdin (`run.py`, review H1). `tests/test_gh_stack_entry.py` passes. |
| 5 | Playwright MCP: pinned `bunx @playwright/mcp@0.0.85` per present host, existing `playwright` entry kept, Flatpak path on Bazzite only with wrapper, Claude write asks consent | VERIFIED (host loads and Flatpak human) | `registry.toml:3644-3668` (`kind="bun"`, `versions={"@playwright/mcp"="0.0.85"}`, `requires=["bun"]`, `postinstall="playwright-mcp-register"`); writer `installer/agent_settings.py` (ledger insert and revert), hook `installer/postinstall.py`, consent step through `session.py` (plan 32-11), removal preview `app.py`. Real run `playwright-container: PASS (transcript ee31bd6542f3)` (`32-08-SUMMARY.md:46`): INSTALL_OK, REGISTER_OK (Copilot entry and Claude files byte-identical), CONSENT_OK, LAUNCH_OK (initialize, tools/list, data: URL), REMOVE_OK. `tests/test_playwright_mcp_entry.py` and `tests/test_container_e2e_playwright_mcp.py` pass (re-run). |
| 6 | SPEC prohibitions: no `xcode-select --install`/sudo/pkexec/doas run; `~/.aws` untouched; no overwrite of a `playwright` entry or consent-less `~/.claude/settings.json` write | VERIFIED | grep of `installer/*.py` for `xcode-select`: hand-off text only (`executors.py:743`), refusal sets (`model.py:563,584`), a status probe `status.py:22` (`xcode-select -p`, read-only). `sudo` occurrences are hand-off strings, comments or the elevation-refusal set (`model.py:559`). AWS container REMOVE_OK; Playwright container byte-identity and consent (CONSENT_OK) results. |
| 7 | Review fix round landed (WR-01..05, lane #2, IN-02..05) | VERIFIED | Commits `2d7aafc8` (forged ledger), `3424f7cc` (0600), `6bea7025` (hand-off parity), `8bfe5187` (process group), `94499ff6` (Codex unit), `0e23cae3` (rereads), `4c565e09` (plugin Flatpak), `81356ba4`, `ac3b0abd`, `a716d9d6`, `1e4f953d` all present after `f91713b9`; `32-SECURITY.md` status verified, 0 open of 32. Deferred: IN-01, IN-06 part, lane #4 (accepted limits). |

**Score:** 5/5 roadmap truths verified (plus the spec prohibitions and review round); 0 behavior-unverified.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `installer/registry.toml` | five entries | VERIFIED | `xcode-clt`, `gh-stack`, `aws-cli`, `bruno`, `playwright-mcp`; loads (tomllib: tiers system, user, user, user, ai) |
| `installer/model.py`, `executors.py`, `resolve.py`, `run.py` | validated `install`, `handoff`, `prefer`; stdin-closed runner | VERIFIED | refusal sets, closed `HANDOFF_NAMES` |
| `installer/agent_settings.py`, `postinstall.py`, `session.py`, `app.py`, `receipts.py`, `update.py`, `version_status.py` | MCP ledger writer, hook, consent step, removal sweep and preview | VERIFIED | wired to the hook name `playwright-mcp-register`; tests pass |
| `scripts/container-e2e-verify.sh` and `tests/e2e_*_driver.py` | `aws-cli`, `bruno`, `playwright-mcp` targets | VERIFIED | host tests with stubbed `ct` pass; real runs recorded |
| `.claude/skills/tool-onboarding/SKILL.md`, `.claude/architecture.md` | rows and rules | VERIFIED | changed in the phase |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| `playwright-mcp` entry | register hook | `postinstall = "playwright-mcp-register"` | WIRED |
| hook | settings ledger writer, per-host revert | `agent_settings.py` revert pairs; removal sweep in `app.py` | WIRED (container REMOVE_OK) |
| Claude host | consent step | `hook_register` reconfigure step with disclosed hosts (32-11) | WIRED (CONSENT_OK) |
| `aws-cli` script method | brew fallback | `prefer` sort key | WIRED |
| `xcode-clt` | hand-off text | `handoff` name to `executors.py` table | WIRED |

### Data-Flow Trace (Level 4)

Not applicable beyond the install and registration flows; the containers trace real file writes (server entries, manifests, removal reverts).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Registry loads the five entries | `tomllib` read of `installer/registry.toml` | five ids with tiers system/user/user/user/ai | PASS |
| Five entry test files plus three container-driver test files | `uv run pytest <8 files> --no-cov -q -n 4`, scratch TMPDIR | 98 passed, 0 failed | PASS |
| Debt markers in phase code | diff `7f00c98b..HEAD` of `installer/`, `scripts/` for TBD, FIXME, XXX | none | PASS |
| Full suite | not re-run here; orchestrator recorded `make test` 9025 passed, 6 skipped, 96.33% | recorded | SKIPPED (one unexplained first-run failure, flake of the host-state kind, two clean re-runs) |

### Probe Execution

SKIPPED: no `probe-*.sh` declared. Container targets are orchestrator-run and recorded; none were run here (forbidden for this verification).

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| ONB-10 | Not defined by the phase (REQUIREMENTS.md and the ROADMAP list ONB-11..ONB-15 for phase 32; ONB-10 does not appear) | N/A | no gap |
| ONB-11 | Xcode CLT hand-off | SATISFIED (Mac human) | Truth 1 |
| ONB-12 | AWS CLI | SATISFIED | Truth 2 |
| ONB-13 | Bruno | SATISFIED (launch human) | Truth 3 |
| ONB-14 | gh-stack (amended) | SATISFIED (amended wording, needs confirmation) | Truth 4 |
| ONB-15 | Playwright MCP | SATISFIED (hosts human) | Truth 5 |

No orphaned requirements. The REQUIREMENTS.md traceability table and the ROADMAP phase checkbox still read Pending/unchecked; `phase.complete` is for the orchestrator after the human items.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `installer/registry.toml` | 3552-3578 | `shortcut:` comment (custom `XDG_DATA_HOME` moves artifacts outside declared paths) | Info | recorded limit |
| `installer/registry.toml` | 3517-3541 | gh-stack detect path assumes default `~/.local/share/gh` (relocation not detected; lane #4, backlog 999.32) | Info | accepted limit |
| `installer/registry.toml` | 3589 | Bruno: `~/.config/bruno` assumed; no menu entry (999.32) | Info | accepted |
| `installer/registry.toml` | 3644 | `@playwright/mcp` pinned 0.0.85 while npm latest is 0.0.86 (D-13) | Info | bumped by hand or catalog-audit |

No TBD, FIXME or XXX markers added. No blockers.

### Human Verification Required

See the front matter list (11 items): ten real-environment checks the phase deferred as UAT lines, plus the owner confirmation of the provisional decisions.

#### Provisional decisions awaiting owner confirmation

From the plan summaries and `32-09-SUMMARY.md` "Phase provisional decisions":

1. D-01: unconditional Xcode CLT hand-off, Update refused, no removal (32-01, 32-02).
2. D-03 deviation (review H3): tool-level `requires = ["unzip"]` dropped for AWS so the brew fallback stays reachable.
3. D-04 and orchestrator decision 4: AWS script before brew by a per-method sort key (`prefer`), with the `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION=false` pin.
4. D-05: AWS container check is orchestrator-run and recorded as `aws-container: PASS`; `aws-cli` and `bruno` join the generic skip list (decision 6); the shared evidence-gate shape.
5. D-07: Bruno as pinned per-arch raw tarballs.
6. D-08 and decision 5: no Bruno desktop entry (follow-up 999.32); `smoke_argv` default kept; Bruno UNPROVEN reported, not gated; the Bruno smoke-application rule.
7. D-09: `script` fixed-argv `install`, refusal set at any position, `install` with `writable_prefix` refused, closed stdin plus new session, the owned-TMPDIR finding rejected; WR-01 loses the child's controlling terminal (sudo inside a cask on the console route).
8. D-10 and D-11 (amended ONB-14 and ROADMAP SC4): gh-stack detected by manifest plus probe name `gh-stack-extension` (an executable with that exact name would read present); removed by the receipt-proven folder instead of `gh extension remove stack`.
9. D-12 and D-13 with decision 7: bun required, pin `0.0.85` with no checkpoint, Node 18 floor, 0.0.86 as the alternative.
10. D-14: the settings-ledger revert is the hook's undo.
11. D-15 as implemented: one listed `hook_register` step with Claude as consent host (covers `~/.claude.json` and the `settings.json` env key); first install carries a shell-quoted `claude mcp add` hand-off; a host appearing after confirmation is not written; every step of a consent-bearing hook carries its hosts; the `--yes` behavior is consent.
12. Decision 1: host set Claude, Cursor, Copilot, OpenCode, Codex; Pi manual note.
13. OpenCode v1/v2 shapes (write only for absent, empty or server-bearing `mcp`; keep a v1 playwright entry); `created_levels` optional ledger field (H4).
14. D-16: launch smoke with distro Chromium, headless `--no-sandbox`; Bazzite Flatpak path not exercised in the box; late-host case.
15. Review triage: WR-03 (customized Codex table keeps the whole server as `kept_changed`), WR-04 (`rereads` honors the receipt except on the confirmed Reconfigure step and the drift report), H6 (a recorded host whose entry is gone reads pending), M6/M7 and round 2 M3/M4 (removal preview shares the revert's eligibility; unreadable file reported; external `COPILOT_HOME` named but not listed); Bazzite discriminator and `shortcut:` limits.
16. Decision 9 and 8: pins edited in each entry's commit; `install` in both elevation checks; Python 3.15 was not run locally for 32-11 (CI covers it).
17. Registry pins and review M8 (order of the Task 1 steps) accepted as run.

### Gaps Summary

No gaps. Every roadmap criterion is backed by code, tests (98 passed on re-run here) and, for AWS and Playwright, an orchestrator-recorded real container PASS. Bruno's container result is UNPROVEN (environmental, FUSE), reported as designed and not a gate. Status is `human_needed` because the Mac, Bazzite and agent-host behaviors cannot be proven here and the provisional decisions need the owner. Residual risk: the full suite was not re-run in this verification (relied on the orchestrator's record), and ROADMAP and REQUIREMENTS checkboxes still show Pending.

---

_Verified: 2026-11-21_
_Verifier: Claude (gsd-verifier)_
