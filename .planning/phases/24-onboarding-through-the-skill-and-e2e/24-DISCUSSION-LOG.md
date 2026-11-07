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

# Update 2026-11-07 (assumptions mode)

**Input:** `24-SPEC.md` (reused as-is by spec-phase `--auto` → Skip; amended in this commit only through dated markup) and the 2026-10-14 CONTEXT (D-01..D-17 kept verbatim; D-16 superseded, D-08/D-08b Policies text superseded, refinements dated).
**Mode:** assumptions (`--analyze --all --batch` intent), jev screening, the best design wins over the smallest diff, CodeGraph.
**Areas analyzed:** Policies → install tuning (Alacritty region, herdr `default_shell`); real build site and image ownership; onboarding skill after 23.1/23.2; herdr integrations; three-distro e2e; stale text.

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 41 tool calls. It ran read-only probes only (`herdr integration status/--help`, `distrobox --help`, `gh api` release GETs, a key-names-only `tomllib` read of the herdr config); no container, network install or host write. Its skill wiring was not clean (`configured_unresolved`: the global `jev-fast-decision` failed gsd-core's path check); it never calls jev, so nothing was lost.

| Assumption | Confidence | Evidence |
|---|---|---|
| No Policies row; D-08/D-08b Policies text is wrong and forbidden | Confident | setup.py:639-665, :885-901, :1121, :1503; version_status.py:656-660, :1669-1675; session.py:438-445; 23.2-SPEC R7 |
| Shell lines stay in terminal sync; revert on zsh-gone and on tool removal | Likely → best | terminal_shell.py:445-495; app.py:709-733 |
| Keybindings are Alacritty install tuning in a second region, not zsh-gated | Likely → best | terminal_shell.py:491-495, :250-258; 23.2 D-01/D-04/D-08; registry.toml:2944-2963 |
| herdr `default_shell` keeps D-08b mechanics, injected runner, not an install-tuning group | Confident | terminal_shell.py:469-477; receipts.py:256; 23.1 D-16..D-22 |
| Real build in a nested-podman disposable container (D-16 superseded) | Likely → best | 24-SPEC Constraints; AGENTS.md; user decision 2 |
| Image removed only when the run pulled it | Likely → best | 24-SPEC R2; host store has several images and 5 containers |
| `--home`, `--no-entry`, `--rm-home` | Confident | live distrobox 1.8.2.5 help |
| Skill baseline = post-23.2 tree | Likely → best | 23.2 D-19, R9 |
| Skill line facts (4b at :96-123; skill_pack :57, :145; prose :134; no "Policies") | Confident | SKILL.md |
| `_HERDR_TARGETS` exists and is extended | Likely → best | postinstall.py:151-210; model.py:205-223; live herdr targets |
| `HOST_CATALOG_IDS` gains pi, copilot | Confident | postinstall.py:30-35; session.py:536-585 |
| herdr integrations edit agents' main config; removal order + value assertions | Likely → best | live key paths in ~/.claude/settings.json and ~/.cursor/hooks.json |
| Ownership of pre-existing integrations | Unclear | live status: claude/cursor current, opencode needs repair |
| D-12 pin 2b5ca2a; needs python3; herdr upstream v0.9.5 | Confident | live gh api |
| Shared pass functions carry 23.1/23.2 assertions | Confident | container-e2e-verify.sh:16, :117-130, :781-828 |
| copilot Node floor on Debian | Unclear | executors.py:486-496; :129 |
| Rerun must accept manual handoffs | Likely → best | container-e2e-verify.sh:432-441, :911, :925 |
| Stale text to amend | Confident | cited lines |
| UAT herdr line proves nothing on this host | Likely → best | live: host already sets default_shell by hand |

## jev screening

One jev request for the discuss step (11 items), through the ladder: Laya one call per item, then TypeSafe (consent recorded 2026-10-14). The first TypeSafe batch exceeded the 8000-character state guard and every answer came back `forced`, so TypeSafe was re-asked in five small batches under the guard (same items, same text); those are the answers logged. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| J1 where the zsh line is written/reverted | low 0.67 shared_sync_revert_zsh_only (Laya low 0.35 per_tool_postinstall) | **Own reasoning:** also revert on tool removal (TUNE-04, locked D-08b) — D-22, ledger |
| J2 one region or two | choice 1.00 two_blocks (Laya low 0.43 one_block_zsh_gated) | D-23 |
| J3 real build site | low 0.61 host_scratch_home (Laya low 0.60 manual_uat_only) | **Own reasoning:** nested container; host podman contradicts the user-locked container-only rule — D-18, ledger |
| J4 when to delete the base image | low 0.71 only_if_pulled_by_run (Laya low 0.36) | **Own reasoning:** only if pulled — D-19, ledger, **needs confirmation** (ONB-02 text) |
| J5 skill-judge baseline | choice 0.90 fresh_rescore | D-24 |
| J6 herdr host map coverage | low 0.72 all_shared_skip_ambiguous (Laya low 0.55 catalog_only) | **Own reasoning:** every shared host, ambiguous left out — D-21, ledger |
| J7 shared settings file on uninstall | choice 0.95 ordered_value_level | D-28 |
| J8 which integrations uninstall removes | low 0.67 all_ran_install (Laya low 0.55) | **Own reasoning:** only missing/broken-before ones (receipt principle) — D-27, ledger |
| J9 copilot Node floor on Debian | choice 0.80 exclude_and_list | D-26 |
| J10 rerun acceptance | choice 0.88 skipped_plus_same_manual | D-25 |
| J11 UAT herdr check | choice 0.83 untouched_no_drift_plus_pane | D-29 |

## Live facts that changed the plan
- Terminal sync has no Policies row; D-08b's "same Policy row family as the other terminals" was wrong (D-22).
- herdr integrations edit agents' main config files (`hooks.SessionStart` in `~/.claude/settings.json`, `hooks.sessionStart` in `~/.cursor/hooks.json`) — key paths only, values not read (D-28).
- herdr 0.9.3 targets include `copilot`, which 23.2 adds to the catalog (D-21); upstream is v0.9.5; Alacritty upstream v0.17.0.
- distrobox 1.8.2.5 has `--home`, `--no-entry`, `rm --rm-home` (D-20).
- This host already sets herdr's `default_shell` by hand (D-29).
- `_HERDR_TARGETS` already exists in `installer/postinstall.py` (D-10 refined).

## Corrections Made
None asked (auto path). Cross-phase amendments in this commit: `24-SPEC.md` (Background, R2 ×2, R6 ×5, R7, R8, four acceptance lines, two prohibitions, interview row, Edge Coverage re-derived from the engine: 30 rows, 29 resolved, R5 unclassified reviewed manually), `ROADMAP.md` (criteria 2 and 3, 999.11 notes ×3), `REQUIREMENTS.md` (ONB-02, ONB-03, ONB-07), `23.2-CONTEXT.md` (the Phase 24 coupling marked handled).

## External Research
Flagged for plan-time research (not done here):
- Nested rootless podman + distrobox inside `quay.io/podman/stable` on SELinux Bazzite (flags, feasibility) — D-18.
- What `distrobox create`/init still writes to the host HOME with `--home`/`--no-entry` — D-20.
- herdr `integration install/uninstall` on 0.9.3 and 0.9.5: formatting and unknown-key preservation, empty `hooks` containers, repair of "needs repair", what the copilot target writes — D-27/D-28.
- Debian and Arch packaged nodejs versions against copilot's floor — D-26.
- Alacritty 0.17 TOML keys (`[terminal.shell]`, `[env]`, Alt/Option escape sequences) and coexistence of a trailing `[[keyboard.bindings]]` region with user bindings — D-08/D-23.
- The pinned distrobox base image and its pull size.
