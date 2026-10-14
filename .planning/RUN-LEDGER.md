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

## Deferred questions / human verification

| Phase | Item | Reason |
|-------|------|--------|

## Quota waits

| When | Role | Wait | Outcome |
|------|------|------|---------|
