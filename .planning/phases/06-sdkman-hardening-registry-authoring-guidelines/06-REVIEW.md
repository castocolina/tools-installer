---
phase: 06-sdkman-hardening-registry-authoring-guidelines
reviewed: 2026-09-06T05:09:51Z
depth: deep
files_reviewed: 4
files_reviewed_list:
  - installer/registry.toml
  - tests/test_registry.py
  - .claude/architecture.md
  - .planning/PROJECT.md
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-09-06T05:09:51Z
**Depth:** deep
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Diff range `954ace6..a3f6353`. Source changes are documentation/test-only: two
`# Verified 2026-09-06: ...` comments above the `sdkman` and `java` `[[tool]]`
blocks in `installer/registry.toml`, one new locality-asserting guard test in
`tests/test_registry.py`, a new "Registry-authoring guidelines" section in
`.claude/architecture.md`, and three new Key-Decisions rows in
`.planning/PROJECT.md`. No production logic changed.

Traced every load-bearing claim in the new prose against the actual runtime it
describes:

- **No schema change.** `java`'s `[[tool.method]]` block is unchanged
  (`kind = "sdkman"`, `candidate = "java"`, `bin_dir = ...`) — no `version` key
  was added. `installer/executors.py::_sdkman` already supported an optional
  `version` param before this phase; this phase deliberately leaves it unset.
  Confirmed by direct read of both files.
- **The three cross-AI-review corrections landed correctly in the shipped
  text**, not just in the plan:
  - The "SDKMAN carve-out is unenforced" overclaim is fixed in
    `.claude/architecture.md`'s "Prefer brew" section — it now explicitly
    separates the documented-only general brew preference (D-02) from the
    already-test-enforced carve-out
    (`test_java_tools_install_exclusively_through_sdkman`,
    `tests/test_registry.py:122-140` — line numbers verified exact against the
    live file).
  - The "permanently disables the prompt" overclaim is fixed in the `sdkman`
    registry comment: it now explicitly scopes the guarantee to a clean
    bootstrap performed by this installer and calls out the brownfield
    exception, correctly citing `installer/status.py:26-29` and
    `installer/engine.py:80-81` (both citations verified line-exact against
    the live files — `is_installed`'s `detect_path` check and
    `install_tool`'s `ALREADY_INSTALLED` short-circuit are exactly where and
    what the comment says).
  - The source-level guarantee (no vendor prompt, `$CURRENT`-guard, one
    HTTP-call default lookup) is grounded in `06-RESEARCH.md`'s verbatim
    `sdkman-install.sh`/`sdkman-env-helpers.sh` reads, not asserted from thin
    air.
- **The new guard test asserts locality, not just presence**, as intended:
  after the five whole-file substring checks, it locates the single
  `id = "sdkman"` and `id = "java"` lines and re-asserts the substrings land
  within the preceding 30-line window. Computed the exact line offsets against
  the live file — both comment blocks fit comfortably inside their respective
  windows, and `test_registry_ids_unique` (pre-existing) makes the test's use
  of unqualified `next()` over `id = "..."` lines safe against a duplicate-id
  false match.
- `make validate` (ruff, ruff-format, pyright, bandit, vulture) and
  `uv run pytest tests/test_registry.py` both pass on the current tree
  (verified directly, not taken from the SUMMARY).

One accuracy gap survived all three review cycles and is called out below.

## Warnings

### WR-01: Verification-comment citation points to a file that doesn't contain what it cites

**File:** `installer/registry.toml:1298` and `installer/registry.toml:1331`
**Issue:** Both new comments read:

> `# script 5.23.0 / native 0.7.34 — see 06-01-SUMMARY.md for the verbatim`
> `# transcript`

Two problems, checked directly against the cited file
(`.planning/phases/06-sdkman-hardening-registry-authoring-guidelines/06-01-SUMMARY.md`):

1. `06-01-SUMMARY.md` never mentions "0.7.34" anywhere (`grep -n "0.7.34"
   06-01-SUMMARY.md` returns nothing). The native-CLI version number is only
   recorded in `06-RESEARCH.md:314`, a different file than the one the
   registry comment names.
2. `06-01-SUMMARY.md` contains no verbatim transcript — it is prose containing
   three short inline-quoted fragments (`` `Downloading: java 25.0.4-tem` ``,
   `` `Done installing!` ``, `` `EXIT_CODE=0` ``) and explicitly says of
   itself: "the orchestrator... wrote it directly from the actual commit
   history, the container-run transcript captured in the candidate's own
   tool-call log" (line 21-26) — i.e. the actual transcript lives in a
   tool-call log that isn't part of this repo, not in the file the registry
   comment tells a reader to go read.

This is the same category of defect the phase's own three review cycles spent
their effort eliminating (a claim in the registry that the cited evidence
doesn't actually establish) — it just landed in a spot none of the three
cycles checked, because the citation itself (which file to open) wasn't
scrutinized, only the claims about SDKMAN's behavior were. A future reader (or
an automated citation-integrity check, if this project ever adds one per the
new "Per-tool, per-OS verification checklist" guideline) following this
pointer to verify the native-CLI version or read the transcript will find
neither in the named file. It's also a new pattern for this repo:
`installer/registry.toml`'s pre-existing `codegraph`/`mmdc`/`puppeteer`
verified-comments (Phase 5) never reference a `.planning/phases/**` file, so
this phase introduces a citation type that additionally risks going stale
once the phase directory is archived by a milestone-close workflow.

**Fix:** Either correct the citation to point at where each fact actually
lives (e.g. "native 0.7.34 (see `06-RESEARCH.md:314`); container run captured
in this phase's execution log, not checked into the repo"), or move the
missing detail into `06-01-SUMMARY.md` itself so the pointer is accurate.
Minimal fix, applied identically at both sites:

```diff
-# script 5.23.0 / native 0.7.34 — see 06-01-SUMMARY.md for the verbatim
-# transcript): on a clean bootstrap performed by this project's own installer,
+# script 5.23.0 / native 0.7.34 (06-RESEARCH.md:314) — see 06-01-SUMMARY.md
+# for a narrative account (not a verbatim transcript; the raw log is not
+# checked into the repo): on a clean bootstrap performed by this project's own installer,
```

## Info

### IN-01: Guard test's `next()` calls have no default, so a missing id line fails with a bare `StopIteration` rather than a clear assertion

**File:** `tests/test_registry.py:152-153`
**Issue:**

```python
sdkman_idx = next(i for i, line in enumerate(lines) if line == 'id = "sdkman"')
java_idx = next(i for i, line in enumerate(lines) if line == 'id = "java"')
```

If either exact line is ever reformatted (e.g. quote style changed, or the
`id` key gets reordered by a future TOML formatter pass) this raises
`StopIteration` instead of a diagnosable `AssertionError`, which is a weaker
failure signal than the rest of this test's `assert ... in ...` style and can
be confusing in CI output.
**Fix:**
```python
sdkman_idx = next(
    (i for i, line in enumerate(lines) if line == 'id = "sdkman"'), None
)
assert sdkman_idx is not None, 'id = "sdkman"' " line not found in registry.toml"
```
(same pattern for `java_idx`). Low priority — current risk is bounded by
`test_registry_ids_unique` (pre-existing) guaranteeing at most one match, and
the line literal is very unlikely to drift silently.

---

## Second lane: codex-sol-high (parallel independent review, ONESHOT-RULES Rule 15)

Dispatched in parallel over the same diff (`954ace6..a3f6353`), via
`codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'`. Findings:
0 Critical, 0 High, 2 Medium, 2 Low.

**Corroboration:** codex-sol-high independently found the SAME defect as this
lane's WR-01 above (the `06-01-SUMMARY.md` citation not containing "0.7.34" or
a verbatim transcript) — two independent reviewers reaching the same finding
from different starting points is strong corroboration it was real.

### Medium — citation gap (= WR-01 above, corroborated)
Same finding as WR-01. **Resolution applied:** rather than weakening the
registry comment's citation, the missing verbatim excerpt (`sdkman_auto_answer`
config dump, full `sdk version` output including `native: 0.7.34`, and the
`sdk install java` completion transcript through `EXIT_CODE=0`) was added
directly into `06-01-SUMMARY.md`, sourced from the actual cross-AI execution
session's captured tool-call log — so the citation is now accurate rather than
redirected. Commit: (this review-fix commit, see below).

### Medium — `installer/executors.py::_sdkman`'s own comment retained the
overbroad claim Phase 6 corrected everywhere else
**New finding, not caught by any of the 3 plan-review cycles** (they reviewed
`registry.toml`, not the pre-existing executor comment). Confirmed real: the
comment said `?ci=true` bootstrap "persists `sdkman_auto_answer=true`... so a
candidate install here does not hang" with no brownfield scope — but
`is_installed`/`install_tool` (`installer/status.py:26-29`,
`installer/engine.py:80-81`) skip this project's own bootstrap entirely when
SDKMAN is already present, so a brownfield SDKMAN install with
`sdkman_auto_answer=false` can still reach the interactive prompt through this
same `_sdkman` executor. **Resolution applied:** the comment now explicitly
scopes the guarantee to a clean, installer-managed bootstrap and states the
brownfield exception, matching the same correction already made in
`registry.toml`'s comments. Commit: (this review-fix commit, see below).

### Low — no test pins that `java` stays unpinned; Low — architecture.md's
"no staleness risk" phrasing overstates D-01's guarantee
Both accepted as documented residuals, not fixed — per ONESHOT-RULES Rule 15,
only Critical/High findings require a fix-or-explicit-deferral before this
checklist item is satisfied; these are Low-severity polish items that would
expand this phase's scope without changing behavior or closing a real gap
already covered by the guard test's presence+locality assertions.

## Resolution status

Both Medium findings (raised independently by 2 lanes on one, 1 lane on the
other) were fixed directly by the orchestrator: `06-01-SUMMARY.md` gained the
verbatim excerpt (closing WR-01 / the corroborated citation gap), and
`installer/executors.py::_sdkman`'s comment was rescoped to match the
brownfield caveat already present in `registry.toml`. `make validate && make
test` re-run clean after both fixes (1197 passed, 99.40% coverage). The
Warning (WR-01, now resolved) and both Info/Low items are the only residuals;
none rise to Critical/High, so Checklist item 5 is satisfied.

---

_Reviewed: 2026-09-06T05:09:51Z (internal lane); codex-sol-high lane run in parallel same date_
_Reviewers: Claude (gsd-code-reviewer) + codex-sol-high (independent parallel lane, Rule 15)_
_Depth: deep_
