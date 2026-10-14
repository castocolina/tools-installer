# Phase 18: Registry truth and drift guard - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-13
**Phase:** 18-registry-truth-and-drift-guard
**Mode:** assumptions (`--analyze --all --batch`; "—asaumptions" read as assumptions mode), jev screening, best-over-easy
**Areas analyzed:** Schema and verification marker; Verification pipeline; verify-registry and pins; Detection, data and launch fixes

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected and best-over-easy in its brief. It made 64 tool calls and no network calls.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| `METHOD_PARAMS` closed sets checked in `load_tools` | Confident | model.py:654-668; test_model.py:803-827 |
| `cli_name` fixed once in `apps.cli_spec` | Confident | apps.py:47-65; registry.toml:2746..2803; status.py:40 |
| `# Verified` placement test with a no-blank-gap rule | Likely | test_registry.py:405-414 |
| Digest fallback in checksums.py raising `ChecksumMismatch` | Confident | engine.py:146-151; audit D:199 |
| Generic smoke step in the engine after `_perform` | Likely | engine.py:71-164; run.py:70-94 |
| verify-registry reuses `_resolve_target`; issues through `gh` | Likely | download.py:85-127 |
| Pin inferred from a literal version in the URL | Likely | registry.toml:2743 |
| Stub rule hardcoded in `is_installed` | Confident/Likely | audit C:176,210; D:89-92 |
| `--no-dev` on 7 Makefile launch targets plus install.sh | Confident | Makefile:14-32; install.sh:88 |
| `managed-download` at 4 sites | Confident | model.py:57; install_ownership.py:83-89,376; registry.toml:2721,2770 |
| Stale `drawio-cli` id already harmless; add a test | Likely | version_cache.py:176-190 |

## Corrections Made (best over easy)

Three analyzer "Likely" picks were the easier option. I re-screened them with jev and presented the better design. Laya came back with low confidence (needs_fallback) on all three; TypeSafe direct (`jev-latest` → `jev-1.13.0`) answered with high confidence:

| Decision | Analyzer pick | Laya | TypeSafe | User |
|---|---|---|---|---|
| Verification marker | `# Verified` comment, no-blank-gap test | comment_above_or_inside p=0.40 | structured_field p=0.99 | **`verified` TOML key** (SPEC R2 amended) |
| Smoke placement | generic engine step after linking | post_install_generic p=0.40 | pre_link_staged p=0.96 | **Before the link, on the staged binary** |
| Pin representation | infer from the URL | explicit_version_key p=0.61 | explicit_version_key p=1.00 | **`version` key plus `{ver}`** |
| macOS stubs | hardcoded in `is_installed` | – | – | **Closed table in status.py** (recommended) |

## Downstream edits made in this session
- 18-SPEC R2, R11, Boundaries, Acceptance Criteria, edge table and prohibitions now refer to the `verified` key and the `version` key.
- REQUIREMENTS REG-02, the ROADMAP lines (Phase 18 summary, success criteria 1, Phase 24.1, herdr note), 22-SPEC, 24.1-SPEC and 17-CONTEXT D-02 were all aligned.

## Reviewed Todos
- Dangling pnpm shims in Doctor (score 0.6): not folded; it belongs to Phase 21.
