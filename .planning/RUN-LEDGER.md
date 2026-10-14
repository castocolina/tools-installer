# v0.50.0 Run Ledger

Run: `/gsd-autonomous --from 17 --to 25 --converge`, playbook `.planning/goals/2026-10-14-v0.50.0-phases-17-25.md`.
Started 2026-10-14. Hourly resume cron: session job (deleted at run end).

## Step 0

| Item | Result |
|------|--------|
| `codegraph sync` | exit 0, already up to date |
| `.git/hooks/pre-commit` | present (pre-commit install done 2026-10-14) |
| Container runtime | `podman` (`scripts/detect-container-runtime.sh`); smoke `podman run --rm alpine echo ok` exit 0 |
| `make e2e` | added: `scripts/container-e2e-verify.sh all` (bootstrap --replace, pass1, pass2, container removed on any exit); transcripts in gitignored `.e2e-artifacts/container/` |
| `make e2e` green | 3rd run exit 0 (33m31s, podman, fedora:latest) on 72c9047: pass1 installed=73 failed=0 manual=8; pass2 RERUN_OK, UNINSTALL_OK, REINSTALL_OK installed=45 already=1; TEARDOWN_OK. Fixed on the way: 9da1e14 (stream git-visible tree), 72ffdb5 (jetbrains-toolbox member bin/), 72c9047 (GITHUB_TOKEN to api.github.com; anonymous 60/h limit) |
| e2e observation → Phase 22 | the uninstall sweep removes only ~46 of 74 installed tools (reinstall re-installs 45); the rest lack removal proof — input for Phase 22 per-method removal |
| Executor probe | `pi -p --model router-env/my-coding --no-session` → OK, exit 0 |
| Reviewer probes | `opencode-plan-review` (router-env/my-plan-review) OK · `opencode-gpt-sol` (openai/gpt-6.1-sol#xhigh) OK · `opencode-glm` (zai-coding-plan/glm-5.3#high) OK |
| Laya | 127.0.0.1:8010 jev-1/laya-rl-agent → status ok |
| TypeSafe | api.typesafe.ai jev-latest/jev-1.13.0 → status ok |

## Decisions

| Phase | Item | Laya | TypeSafe | Outcome | Why |
|-------|------|------|----------|---------|-----|
| 17 | Q1 graphify postinstall: remove vs keep for claude/codex | — (verifiable) | — | Remove `postinstall` + dead hook code | D-03 lock: global form only if the HOME-sandbox probe proves cwd untouched; container probe showed opencode/cursor write into cwd → not proven |
| 17 | Q2 move_link_mode scope: link-mode-aware policies only vs every active policy | link_mode_aware_only 0.52, conf 0.001 (fallback) | link_mode_aware_only 0.94, conf 0.88 | Link-mode-aware only (`Policy.link_mode_aware` flag: ban, tweaks, macOS cache redirect) | Refines D-09 "every active policy": daemon/omz blocks do not depend on link mode; moving them re-bootstraps services for nothing |
| 17 | Q3 identify SPEC timing-dependent `test_version_status` | — (verifiable) | — | Executor stress-runs `tests/test_version_status*` under `-n auto` repeatedly; fix only if reproduced; `test_owner_cell…` race (CI ubuntu 5/5) is the confirmed flake | Fact, not a gray area |
| 17 | Q4 Doctor repair wording for dangling link without opt dir | — | — | Planner discretion | CONTEXT discretion item |
| 17 | SPEC sudo/pkexec/doas argv scan vs existing `sudo dnf/apt-get/pacman` builders (executors.py) | — (verifiable) | — | Scan scoped to text Phase 17 adds; package-manager sudo stays for Phase 22 (LIFE-02) | The SPEC itself assigns native-package sudo removal to Phase 22 |
| 17 | CI-02 branch protection (plan 13 blocking-human checkpoint) | — (playbook rule) | — | Recorded "skip"; exact `gh api` command handed to the user under human_verification; plan 13 runs inline in the orchestrator at phase close | Playbook: never pause for UAT/non-blocking questions; a GitHub settings change needs the user's in-the-moment consent (D-17) |
| 17 | TDD red commits vs AGENTS.md coherent-commit rule | — (verifiable) | — | `tdd="true"` tasks; RED output recorded in SUMMARY, test + code in one commit | AGENTS.md forbids invalid intermediate commits |
| 17 | 17-11 warn also on wrong-shape JSON / unknown link_mode (planner extension beyond D-11) | drop 0.52, conf 0.001 (fallback) | drop 0.98, conf 0.96 | Drop the extension; warn only for invalid UTF-8 / invalid JSON | D-11/SPEC R8 scope; avoids changing two existing tests' meaning (ponytail ultra finding) |
| 17 | CI-01 macOS oracle before later waves (checker W5) | — (verifiable) | — | After wave 1 the orchestrator pushes HEAD to a temporary branch `ci/phase-17-wave1`, opens a draft PR to trigger CI (pull_request trigger), records both job results in 17-01-SUMMARY, then closes the PR and deletes the branch | ci.yml triggers only on push to main / pull_request; main is pushed only after phase verification (playbook) |
| 17 | Plan-checker cap (3 iterations) reached with 2 WARNINGs in 17-13 Task 1 verify commands (grep -A8 window; HEAD vs oracle sha) + 2 INFO | — (verifiable) | — | Orchestrator fixed inline: section-scoped sed reads, recorded `oracle sha:` + HEAD differs only under .planning/, ls-remote must exit 2, deferred truth marked `verification: backstop` | 17-13 runs inline in the orchestrator; issues were verifiable command defects (bash -n + plan-structure re-checked), no design choice involved |
| 17 | Review cycle 1 (opencode-plan-review): 0 HIGH, 7 actionable → replanned (reviews mode) | — | — | All 7 incorporated; 17-07 cancel test asserts `has_failure` True (reviewer suggested False) | Locked D-08: `has_failure` is true whenever `not_attempted` is non-empty; changing that is a user decision, not a plan fix |
| 17 | Reviews-mode plan-check: 1 WARNING (17-13 `[^\r]` grep class truncates at 'r') + floors in 17-06/17-07 too low | — (verifiable) | — | Orchestrator fixed inline: `grep -a -o 'TRACER_REINSTALL_OK.*'` (verified on the Step-0 transcript), floors 9 and 9 | Measured defects in commands; no design choice |
| 17 | Review cycle 2: 0 HIGH, 4 actionable (set_link_mode save-order MEDIUM + 3 LOW) → replanned; plan-check PASSED | — | — | save-first reorder lives in 17-08 (wave 3, its rollback depends on it), 17-11 keeps the order; orchestrator also anchored 17-13's pyproject/uv.lock diff to the repo root | 17-11 is wave 4, not wave 2 as the reviewer assumed |

## Deferred questions / human verification

| Phase | Item | Reason |
|-------|------|--------|
| 17 | CI-02: apply branch protection on main (`gh api -X PUT repos/castocolina/tools-installer/branches/main/protection`, body in 17-13-PLAN.md) | GitHub settings change needs the user's consent; not applied by the run |

## Quota waits

| When | Role | Wait | Outcome |
|------|------|------|---------|
| 2026-10-14 ~16:20–16:50 | Claude session (gsd-planner revision, phase 17) | session limit until 16:50 | resumed the same agent via SendMessage after reset; no work lost |
