# Phase 24: Onboarding through the skill and e2e - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 24-onboarding-through-the-skill-and-e2e
**Mode:** assumptions (`--analyze --all --batch`). This is a batch run under the user's /goal: jev ladder, best-over-easy, non-blocking questions deferred.
**Areas analyzed:** `cargo_distrobox` kind; Alacritty artifacts and terminal; herdr; Onboarding skill; e2e and UAT

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected. It made 51 tool calls and no network or container calls.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Params with `artifacts` as a list of tables | Likely → best | model.py:24-40, 141-153, 239-243; executors.py:48 |
| Executor `try/finally` cleanup | Confident | run.py:18; executors.py:370-473; engine.py:71-92, 141-153 |
| Staged smoke and the shared `artifact_paths` | Likely → best | 18 D-06; 19 D-07 |
| Precedence via `resolve.py` and `Platform` flags | Unclear → best | platform.py:20-24; resolve.py:13-128 |
| New `desktop_entry` module | Unclear → best | no desktop handling in installer/ |
| `tic` inside the box | Likely | constraints |
| Alacritty TOML region guard | Unclear | terminal_shell.py:72-108, 284-312, 420-425 |
| Alacritty via `sync_terminal_shells` and one Policy | Likely | policy.py:121; wizard_app.py:1512-1524 |
| herdr `github_release` raw | Confident | ROADMAP.md:389; registry.toml:2630-2635 |
| herdr host id translation map | Unclear → best | ROADMAP.md:404; model.py:67-124 |
| herdr skill as a separate `skill_pack` | Confident | registry.toml:2807-2868 |
| herdr-setup reuse = boundary-narrowing only | Unclear | ROADMAP.md:401 |
| Rewrite step 4b of the onboarding skill | Confident | SKILL.md:118-123 |
| Skill-judge baseline before the edit | Unclear → best | audit B:163 |
| e2e `--distro` parameter | Confident | container-e2e-verify.sh:14-20, 108-121 |
| Real build outside the nested e2e | Unclear | detect-container-runtime.sh |
| Rerun asserts via `WORDS` | Likely → best | container-e2e-verify.sh:254-273 |
| UAT in the existing format | Confident | STATE.md:85-104 |

## jev screening (ladder)

| Item | Laya (prob / own confidence) | TypeSafe | Outcome |
|---|---|---|---|
| Alacritty TOML region | guarded_region 0.82 / 0.32 | guarded_region 1.00 | D-08 |
| Real build site | host_podman_scratch_home 0.64 / 0.06 (needs fallback) | 0.97 | D-16 |
| herdr rows when the user has them | absent_only_with_reason 0.82 / 0.32 | 0.92 | D-12 |

Laya's own confidence was below the threshold every time, so TypeSafe decided each item. All three agreed with Laya's pick.

## Orchestrator findings
- **herdr-setup reuse is in scope.** The analyzer read it as boundary-narrowing only. But SPEC R1's Target names the separator and indicators, and the Boundaries exclude only features "beyond" them, so it ships (D-12) through the 23 writer with absent keys only.
- **Real build without touching HOME.** The executor runs on host podman with a scratch `HOME`; the e2e containers carry no podman.

## Corrections Made
None asked. Nothing blocked a later phase.

## External research flagged
- herdr: whether `integration install` edits an agent's main config; the name vocabulary (read-only `status`/`--help` on the host's herdr 0.9.3); the plugin's pinned source.
- GitHub `digest` on the herdr and Alacritty releases.
- Alacritty build packages per distro; the `tic` source path.
- `distrobox create/rm` flags for a one-shot box, including a custom `--home`.

## Post-discussion amendment (2026-10-14)
- User: herdr should start zsh when available, like Konsole/kitty, because omz plugins do not load in herdr. Measured: herdr 0.9.3 `[terminal] default_shell` is empty (meaning `$SHELL`, then `/bin/sh`) and `$SHELL` is `/bin/bash`. Added D-08b (herdr branch of `sync_terminal_shells`, absent-only key write, ledgered revert) and amended SPEC R6.
