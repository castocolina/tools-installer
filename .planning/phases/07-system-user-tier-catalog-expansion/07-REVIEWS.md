---
phase: 7
reviewers: [codex]
reviewed_at: "2026-09-06T08:37:32Z"
plans_reviewed: [07-01-PLAN.md, 07-02-PLAN.md, 07-03-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
model_sources:
  codex: "banner"
---

# Cross-AI Plan Review — Phase 7 (Cycle 3, final)

## Consensus Summary

Only one reviewer lane (codex) ran this cycle — gemini was undetected on this host, and
claude was skipped for reviewer independence (this session runs on Claude Code). With a
single reviewer, "consensus" below reflects codex's own findings; there is no
cross-reviewer corroboration to report.

Codex reviewed with full source access and cited concrete `path/to/file:line` evidence
throughout (e.g. `installer/versions.py:94`, `installer/resolve.py:32`, `installer/app.py:134`,
`installer/download.py:190`), and its most consequential claim was independently re-verified
against the actual repository by this review run (see "Verification note" below).

Codex's overall verdict: **NOT CONVERGED** — the design direction is sound, but the plans
still have open gaps that should be addressed before execution.

### Verification note — the cycle-3 repair claim (important calibration)

Codex's single largest finding was that `Platform.os_version`, `_applies`'s `min_os_version`
gate, and `platform_could_support` "exist only in the plans" — i.e. they are not present in
`installer/platform.py` / `installer/resolve.py` today. This review independently confirmed
that claim is factually true: `grep -rn "os_version\|platform_could_support\|min_os_version"
installer/ tests/` returns zero hits outside `.planning/`, and `installer/platform.py` /
`installer/resolve.py` are unchanged in `git diff` (no local modifications).

However, `.planning/state.json` and `.planning/STATE.md` both confirm Phase 7 is still
`status: pending` / `"Plan: Not started"` — this is a **pre-execution** plan-review-convergence
cycle. The plans under review are documents describing Task 1's future implementation (see
`07-02-PLAN.md` lines 232-262), not a claim that the code has already been written. Treating
"the new mechanism is absent from `installer/`" as a plan defect would make this gate
unsatisfiable for any plan, by construction — the whole point of a plan is that the code it
describes has not been written yet.

Because of this, this review's `current_high` count below **excludes** that specific finding
from Codex's report ("HIGH — The primary cycle-3 repair is not implemented in the source",
under Plan 07-02). It is not dropped from the record (see below), but it is not counted as a
plan defect. Future review cycles for this project should scope "verify the fix is real" to
mean "verify the plan's design is sound and internally consistent" pre-execution, and reserve
"verify the code exists" for a post-execution code review — conflating the two produces
exactly this false-positive.

### Agreed Strengths

(Single reviewer — not subject to 2+-reviewer agreement, listed as reported)

- The `meets_minimum(observed, minimum)` semantics are correct: fails closed, uses `>=`,
  parses both inputs (`installer/versions.py:94`).
- Placing the version gate inside `_applies` is the correct enforcement point — every
  resolver/install path flows through `resolve_methods` (`installer/resolve.py:32`).
- `dataclasses.replace(platform, has_brew=True)` is a sound, non-mutating way to answer
  "could this platform support the tool once Homebrew exists".
- Reusing `BrowserAdapter.selectable` and `UninstallScreen._tool_entry`'s dim/inert-row
  pattern for the catalog's disabled-state rendering is appropriate reuse, not a new pattern.
- The new Bazzite `has_brew=False` test (07-01) closes the cycle-2 test-coverage gap.
- WezTerm's `raw=true` + `checksum="{asset}.sha256"` registry shape is compatible with the
  existing download/checksum resolver (`installer/download.py:122,190`, `installer/checksums.py:23`).

### Agreed Concerns

(Single reviewer — listed in priority order, not by cross-reviewer agreement)

- **HIGH** — The `_build_app` composition-root regression test (07-02, `tests/test_setup.py`)
  uses a wrong-OS synthetic-tool fixture. Both the old buggy expression
  (`not resolve_methods(...)`) and the new correct one (`not platform_could_support(...)`)
  return `True` for that fixture, so the test would not catch a regression back to the exact
  Homebrew-conflation bug this cycle exists to fix. (Note: `tests/test_catalog_tui.py`'s
  separate fixture, per the plan text, does correctly exercise the has_brew=False/arm64 case —
  this gap is specific to the `test_setup.py` wiring-level test.)
- **HIGH** — 07-03's Tier-3 verification runs `~/.local/bin/wezterm --version` directly inside
  a plain `python:3.13-slim` container after a raw AppImage copy+chmod
  (`installer/download.py:190` performs no FUSE/extraction support). AppImages generally
  require FUSE, which is commonly unavailable in vanilla Docker containers. As written, the
  plan's own completion gate treats this failure as a "destructive anomaly" (ONESHOT-RULES
  Rule 9) rather than an expected environment limitation, and is likely to fail as specified.
- **MEDIUM** — `min_os_version` is not validated at registry-load time (07-02): `load_tools`
  copies arbitrary method keys into `params` without validating this one, so a misspelled key
  (e.g. `min_os_verison`) fails open silently rather than erroring at load time. The plan
  explicitly forbids modifying `model.py`, so this gap is not addressed.
  (`installer/model.py:184`)
- **MEDIUM** — `platform_could_support` fixes catalog *browsing* but not the *install-time*
  snapshot: `run_wizard`'s dependency resolution still uses
  `available=lambda tool: bool(resolve_methods(tool, platform))` against the static,
  pre-bootstrap `Platform` (`installer/app.py:134`), and `install_tool` keeps the original
  `has_brew=False` snapshot even within the same run (`installer/engine.py:83`). A user can
  see a brew-only tool as selectable in the catalog and then have it fail to install in the
  same session.
- **MEDIUM** — The Bazzite two-run Homebrew bootstrap (07-01) conflicts with the project's
  stated core value of dependency-driven, no-manual-ordering bootstrap
  (`.planning/PROJECT.md:12`). The plan documents this as an accepted flow rather than a
  design gap to close.
- **MEDIUM** — A successful `APPIMAGE_EXTRACT_AND_RUN=1` smoke test (07-03), if substituted
  for the plan's literal command, would prove the download/checksum pipeline but not the
  normal (non-extracted) invocation path this project actually installs.
- **LOW** — Several 07-01 registry-comment tests assert on exact substrings (`HEAD`,
  `Bazzite`, `Tier-3 container`), coupling test passage to prose wording rather than behavior.
- **LOW** — 07-02's proposed non-Darwin detection test patches only `system`, unlike the
  existing deterministic probe test which also patches `machine`/`which`/immutability
  (`tests/test_platform.py:58`) — leaves OS detection dependent on the test runner's tools.
- **LOW** — 07-02's `cmd="gnu-bash"` workaround misrepresents the real executable name,
  creating debt for Phase 12's version-probing work (`installer/uninstall.py:148` treats
  `Tool.cmd` as the real command elsewhere).
- **LOW** — 07-03's executor-time conditional arm64 release-matrix research makes the final
  registry shape nondeterministic; better resolved before execution or recorded as an
  explicit checkpoint.
- **LOW** — 07-03's registry comments remain process-heavy (review cycles, investigation
  narrative) rather than concise verified facts; that detail belongs in the SUMMARY.

### Divergent Views

Not applicable — single reviewer this cycle.

---

## Codex Review

**Convergence verdict: NOT CONVERGED** (per Codex; see verification note above for this
review's calibration of the "not implemented in source" component of that verdict).

### Plan 07-01 — zsh and Oh-My-Zsh

**Risk: MEDIUM**

Strengths: `oh-my-zsh.requires` correctly lists both `zsh` and `git`, matching the resolver's
transitive/topological ordering (`installer/deps.py:59,121`); the safe-environment script
pipeline is built from the real `_env_prefix`/`_script` execution path
(`installer/executors.py:334,353`); `detect_path` is the correct existing status-detection
mechanism (`installer/status.py:16`); the three-phase container procedure and the new Bazzite
`has_brew=False` test genuinely close the cycle-2 test-coverage gap (`07-01-PLAN.md:386`).

Concerns:
- MEDIUM — the accepted two-run Bazzite bootstrap conflicts with the project's core
  dependency-driven-bootstrap value (`PROJECT.md:12`, `installer/app.py:134`,
  `installer/engine.py:83`).
- LOW — comment-substring tests protect prose, not behavior.

Suggestions: record the two-run flow as a known limitation (or add a later requirement to
refresh platform capabilities after Homebrew installs mid-run); keep `registry.toml` comments
concise and move transcripts to the SUMMARY; simplify the "podman appears exactly once"
assertion to a plain presence check (`tests/test_registry.py:26` already covers global
uniqueness).

### Plan 07-02 — GNU Bash, Apple Containers, and availability

**Risk: HIGH**

Strengths: `meets_minimum`'s `>=`, fail-closed semantics are correct (`installer/versions.py:94`);
`_applies` is the right enforcement point (`installer/resolve.py:32`); `dataclasses.replace`
for `platform_could_support` is sound; the UI reuse (`BrowserAdapter.selectable`,
`installer/tool_browser.py:60,240`) and the staging-bypass closures across
`installer/catalog_tui.py:310,323,360` are appropriate; the GNU Bash false-positive diagnosis
via `installer/status.py:24` is valid.

Concerns:
- HIGH — the primary cycle-3 repair (`os_version`, `min_os_version` gate,
  `platform_could_support`, catalog `unavailable` wiring) is described in the plan but not
  yet present in `installer/platform.py` / `installer/resolve.py`. **This review's
  calibration: expected for a pre-execution plan (Phase 7 is still `status: pending`); not
  counted as a plan defect. See "Verification note" above.**
- HIGH — the `test_setup.py` composition-root regression test's wrong-OS fixture cannot
  distinguish the old buggy expression from the fixed one (`07-02-PLAN.md:799`).
- MEDIUM — `min_os_version` is not validated at load time, so a misspelled key fails open
  (`installer/model.py:184`).
- MEDIUM — `platform_could_support` fixes browsing but not the install-time Homebrew snapshot
  (`installer/app.py:134`, `installer/engine.py:83`) — enabled-in-catalog vs.
  fails-at-install-time can still disagree.
- LOW — the proposed non-Darwin detection test under-patches vs. the existing pattern
  (`tests/test_platform.py:58`).
- LOW — `cmd="gnu-bash"` misrepresents the executable name and creates Phase-12 debt
  (`installer/uninstall.py:148`).

Suggestions: implement the source changes and run the boundary tests against the committed
tree before declaring convergence; strengthen the `_build_app` test with two brew-only
synthetic tools (or the real `container` entry) covering both "supported + has_brew=False"
and "wrong OS/arch/version" cases; validate `min_os_version` at load time (non-empty string,
must parse via `parse_declared_version`); document or extend the two-run Homebrew limitation;
consider an explicit `status_cmd`/probe field instead of a fictitious `cmd` value.

### Plan 07-03 — Terminal emulators

**Risk: HIGH**

Strengths: `raw=true` correctly bypasses gzip extraction (`installer/download.py:122,190`);
`checksum="{asset}.sha256"` is compatible with the existing resolver and parser
(`installer/download.py:54`, `installer/checksums.py:23`); the new `terminal` category fits
the existing closed-enum validation path (`installer/enums.py:31`, `installer/model.py:286`);
resolver tests assert load-bearing WezTerm fields, not just method kind
(`07-03-PLAN.md:348`); adding WezTerm to `SIDECAR_VERIFIED` reuses an established invariant
(`tests/test_registry.py:841`).

Concerns:
- HIGH — the Tier-3 AppImage verification command is expected to fail in ordinary Docker:
  AppImages generally require FUSE, which the raw-download path does not provide
  (`installer/download.py:190`; see AppImage's own Docker/FUSE troubleshooting guidance).
- MEDIUM — a fallback `APPIMAGE_EXTRACT_AND_RUN=1` smoke test would prove the download but not
  the normal (non-extracted) invocation this project actually installs.
- LOW — the executor-time conditional arm64 release-matrix research makes the final registry
  shape nondeterministic.
- LOW — registry comments remain process-heavy rather than concise verified facts.

Suggestions: split Tier-3 verification into (1) install/checksum verification via
`install_download`, (2) a container payload smoke test using
`APPIMAGE_EXTRACT_AND_RUN=1`, and (3) an explicit platform-prerequisite decision for normal
invocation (document/model FUSE, or install the extracted AppImage contents instead); do not
classify a Docker/FUSE failure as a destructive anomaly — it is an expected, documented
environment limitation; resolve the arm64 release matrix before execution if possible.

### Final Risk Assessment (per Codex)

**Overall: HIGH.** Codex's stated basis: (1) the central `os_version`/`min_os_version`/
`platform_could_support` implementation is absent from current source — see this review's
calibration note; (2) the production-wiring test would not catch a regression to the exact
Homebrew-conflating expression; (3) browse-time and install-time availability can still
disagree when Homebrew is missing; (4) the WezTerm Tier-3 AppImage test assumes Docker can
run an AppImage directly without FUSE.

## Cycle 3 direct-fix disposition (ONESHOT-RULES Rule 10, max cycles reached)

Cycle 3's final `CYCLE_SUMMARY` (`current_high=2 current_actionable=9`) did not converge to
zero within the 3-cycle cap, so per Rule 10 the orchestrator applied fixes directly rather
than spawning a 4th planner cycle. Disposition:

**HIGH #1** (07-02's `tests/test_setup.py` fixture could not distinguish the fixed
`platform_could_support` expression from the pre-cycle-2 buggy `not resolve_methods(...)`
one) — **fixed**: added a second, genuinely-differentiating `has_brew=False` fixture
alongside the original wrong-OS one.

**HIGH #2** (07-03's WezTerm Tier-3 AppImage verification would fail in a plain
`python:3.13-slim` container with no FUSE) — **fixed**: split verification into a hard
download/checksum gate plus a separately-classified `APPIMAGE_EXTRACT_AND_RUN=1` launch
attempt, explicitly reclassifying a FUSE-unavailability failure as a known
container-environment limitation, not a Rule 9 destructive anomaly.

**MEDIUM** (browse-time vs. install-time `has_brew` snapshot disagreement) — **fixed** via
new threat-register entry T-07-13 in `07-02-PLAN.md`: accepted as a pre-existing,
out-of-scope contract this phase does not change.

**MEDIUM** (`min_os_version` key-spelling not validated at registry-load time) — **fixed**
via new threat-register entry T-07-14 in `07-02-PLAN.md`: accepted, covered by the existing
Phase 6 registry-authoring verification checklist; a dedicated schema-validation pass is
noted as future-phase follow-up.

**MEDIUM** (07-01's two-run bootstrap on a truly fresh, brew-less Bazzite machine sits in
tension with `PROJECT.md:12`'s "no manual ordering" value) — **fixed** via new
threat-register entry T-07-15 in `07-01-PLAN.md`: accepted — this is the same generic,
pre-existing limitation `tests/test_resolve.py::test_immutable_no_brew_native_only_returns_empty`
already documents for every brew-dependent tool on immutable Linux, not something this phase
introduces; a real fix (auto-chaining a second pass after Homebrew bootstraps, or mid-run
`has_brew` refresh) is engine-level work for a future phase, not a Phase 7 catalog change.

**Remaining LOW-severity findings — accepted as documented residuals, not individually
patched** (consistent with this session's established practice: only Critical/High findings
require a fix-or-explicit-deferral before proceeding; Low-severity polish items that don't
change behavior or close a real gap are logged here instead of expanding scope further):
- 07-01: registry-comment guard tests are coupled to exact substrings, making them brittle
  to future prose edits — acceptable, since `tests/test_registry.py`'s existing pattern
  (Phase 6) already accepts this tradeoff for the same reason (locality + presence over
  paraphrase-tolerance).
- 07-02: a non-Darwin platform-detection test's monkeypatch scope is narrower than
  `tests/test_platform.py:58`'s fuller pattern — cosmetic test-hygiene gap, not a coverage
  gap (the assertion itself is still correct).
- 07-02: `cmd="gnu-bash"` naming leaves a naming-debt trail — explicitly flagged in-plan for
  Phase 12 cleanup, not fixed now to avoid scope creep into unrelated registry ids.
- 07-03: the executor-time conditional arm64 release-matrix check makes the final registry
  shape resolve nondeterministically at install time rather than being pinned at
  registry-authoring time — accepted, since the alternative (hardcoding a specific WezTerm
  release asset name) would go stale faster than a live per-run check.
- 07-03: registry comments remain narratively verbose rather than terse Phase-6-style
  verified facts — cosmetic, does not affect correctness or the guard tests' assertions.

All three Phase 7 plans re-verified for structural sanity (task-block counts,
`cross_ai: true` frontmatter, matched `<threat_model>` tags) after these direct edits.
Proceeding to cross-AI execution per the established pattern.
