# Phase 19: One tool state with health plus receipts - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-10-14
**Phase:** 19-one-tool-state-with-health-plus-receipts
**Mode:** assumptions (`--analyze --all --batch`; "—assumptions" read as assumptions mode, as in phases 17 and 18), jev screening, best-over-easy
**Areas analyzed:** State and publication; Receipts; Removal proof; Owners and live brew; Marks, legend and misconfiguration

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (sonnet) with jev-fast-decision injected and best-over-easy in its brief. It made 66 tool calls (codegraph plus reads) and no network calls.

| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| One frozen `ToolState` map, one swap; a raced pass publishes nothing | Confident | version_status.py:677-771; the raced statuses merge is still live at :751 (comment :727-751) |
| `state_of` uses the fail-closed `ownership_of` pattern | Confident | version_status.py:510-529 |
| Delete `set_installed` and the per-tier copies (best) vs keep a shim (easy) | Likely → best | catalog_tui.py:383-402; 1 caller |
| `receipts.py` writes once, in `engine.install_tool` before postinstall | Confident | engine.py:155-168; atomic.py:56 |
| Shared `artifact_paths` (best) vs executor-returned paths (easy) | Likely → best | uninstall.py:56-97; target-architecture §4.3 |
| Drift check: existence-only per pass, hash at removal | Unclear | target-architecture §1.1 cost table |
| CLI and TUI both go through `removal_plan` | Confident | app.py:548; setup.py:860, :1364 |
| 17 D-04 / 18 schema not landed yet | Confident | no `verified =` in the registry, no `METHOD_PARAMS`, no 17/18 plans |
| Native probe: batched call (best) vs per-path memo (easy) | Unclear | install_ownership.py:260-275; SPEC AC "one rpm -qf per pass" |
| uv owner dir from `uv tool dir` (best) vs fixing the env fallback (easy) | Likely → best | ownership.py:445, :456-457 |
| `has_brew` re-read; every consumer reads the refreshed platform | Confident | version_status.py:450, :494-496; resolve.py:67..195 |
| Legend replaced, not appended | Confident | tests/test_catalog_tui.py:1878-1899 |
| Terminal drift via `sync_terminal_shells(write=False)` (best) vs a separate checker (easy) | Likely → best | terminal_shell.py:72-108 |
| Skill partial/duplicate from the existing probe outputs | Likely | skill_lifecycle.py:351-426 |

## Orchestrator findings (beyond the analyzer)

- **SPEC R5 could not be implemented as written.** `registry.toml` holds no checksum values (39 `checksum =` keys, all checksum-file names fetched online), and 74 of the 94 download methods are archives whose checksum never equals the extracted binary. Only about 8 tools install a raw binary.
- **Duplicate skill packs:** the audit shows superpowers installed 4 times in Claude (F-registry-ai.md:40, :138), and `_claude_matches` ignores scope and status.

## jev screening

One Laya call per item, then TypeSafe direct (`jev-latest` → `jev-1.13.0`) on the batch. jev received summaries only: no source code and no keys.

| Item | Laya | TypeSafe | Outcome |
|---|---|---|---|
| Drift check | existence_only p=0.43 (needs fallback) | stat_fingerprint p=0.93 | User: stat fingerprint |
| Native probe | batched_call p=0.78 | batched_call p=0.99 | Batched (D-11) |
| Adoption source | cached_release_digest p=0.54 (needs fallback) | cached_release_digest p=0.99 | User: cached digest; SPEC R5 amended |
| Artifact source | shared_artifact_paths p=0.52 (needs fallback) | shared_artifact_paths p=0.87 | Shared `artifact_paths` (D-07) |

## Corrections Made

### Drift check
- **Original assumption:** existence-only checks each pass; hash only at removal.
- **User correction:** stat fingerprint (size + mtime_ns); re-hash only on a stat change.
- **Reason:** existence-only shows a false `✓` after an in-place overwrite.

### Adoption source
- **Original (SPEC R5):** the registry's pinned checksum.
- **User correction:** the cached release digest from the existing latest-release fetch; archive kinds use the layout proof.
- **SPEC edits:** R5 and the R5 prohibition row in 19-SPEC.md were amended.

### Skill-pack duplicates
- **Proposed:** only enabled, in-scope entries count; more than one means "duplicate".
- **User correction:** "Ptefer user global for superpowers". Read as: the user (global) scope entry is the one that counts; project-scope, other-marketplace and disabled entries become duplicate or disabled reasons (D-18).

## Reviewed Todos
- Dangling pnpm shims in Doctor (0.6): Phase 21.
- GSD per-repo installs (0.6) and the pi repair/sync (0.6): out of scope.
