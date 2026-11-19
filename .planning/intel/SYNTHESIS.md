# Synthesis Summary

Mode: merge (ingest batch 5, update automation). Batches 1-4 (the 2026-09-04 PRDs) are in
`.planning/intel/classifications-archive/`; their intel files were overwritten by this batch (git keeps history).
Classifications consumed this run: 4 (from `.planning/intel/classifications/`).

## Doc counts by type

- ADR 0, SPEC 0, PRD 0, UNKNOWN 0
- DOC 4 (all manifest_override, confidence high, locked false):
  - `.planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md`
  - `.planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md`
  - `.planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md`
  - `.planning/research/2026-11-17-update-automation.md`

## Decisions locked

0 (no ADRs). See `decisions.md`. Owner decision 2026-11-19: phases 33-35 appended to v0.51.0 (bot, daily check, auto-update).

## Requirements (proposed, 18)

See `requirements.md`.
- BOT-01..04 (phase 33)
- NOTIFY-01..06 (phase 34)
- AUTOUPD-01..08 (phase 35)

## Constraints

0 (no SPECs).

## Context topics

4 (shared research, bot, daily check, auto-update), with 16 open owner questions (OQ-*) in `context.md`.

## Conflicts

0 blockers, 2 warnings (24.2 notification cut reversed; update-all vs 24.2 default-on rule), 5 info. Detail: `.planning/INGEST-CONFLICTS.md`.

## Files

`.planning/intel/requirements.md`, `decisions.md`, `constraints.md`, `context.md`, and `.planning/INGEST-CONFLICTS.md`.
