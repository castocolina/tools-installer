---
phase: 07-system-user-tier-catalog-expansion
reviewed: 2026-09-06T11:50:19Z
depth: deep
files_reviewed: 16
files_reviewed_list:
  - installer/catalog_tui.py
  - installer/enums.py
  - installer/platform.py
  - installer/registry.toml
  - installer/resolve.py
  - installer/selection.py
  - installer/wizard_app.py
  - setup.py
  - .claude/architecture.md
  - tests/test_catalog_tui.py
  - tests/test_platform.py
  - tests/test_registry.py
  - tests/test_resolve.py
  - tests/test_selection.py
  - tests/test_setup.py
  - tests/test_status.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-09-06T11:50:19Z
**Depth:** deep
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Diff range `47107fd..7bcd1b8`. This phase adds six registry entries (`zsh`,
`oh-my-zsh`, `gnu-bash`, `container` at system tier; `kitty`, `wezterm` at
user tier, the latter two under a new `terminal` category), plus two real
production mechanisms: `Platform.os_version` + a `min_os_version` gate in
`resolve.py::_applies` (fail-closed via the existing, already-tested
`meets_minimum`), and `resolve.py::platform_could_support`, a
has_brew-blind predicate threaded `setup.py` → `UnifiedApp` →
`CatalogScreen` so a genuinely platform-incompatible catalog row renders
disabled while browsing, without wrongly disabling a brew-dependent tool on
a fresh Mac that simply hasn't bootstrapped Homebrew yet. Three staging
paths (`unstaged_recommends`, `action_accept_recommends`,
`on_tool_browser_accepted`) were additionally hardened so an unavailable
tool can never reach a committed selection via the Recommends flow.

Traced every load-bearing claim against the actual runtime:

- **`_applies`'s `min_os_version` gate is correct and fail-closed on both
  sides** — an unparseable/`None` observed version and an unparseable
  declared floor both refuse via the existing `meets_minimum`/
  `parse_version`/`parse_declared_version` trio (`installer/versions.py`,
  unmodified). Verified directly against `tests/test_resolve.py`'s new
  fixtures, including the `os_version=None` fail-closed case.
- **`platform_could_support` genuinely distinguishes "not yet bootstrapped"
  from "never installable here"** — `dataclasses.replace(platform,
  has_brew=True)` only ever widens the `has_brew` gate, never the `os`/
  `arch`/`min_os_version` gates, so a wrong-OS, wrong-arch, or too-old-macOS
  fixture stays `False` even under the hypothetical. Verified with a
  concrete Python one-liner and `tests/test_setup.py`'s two-fixture wiring
  test (a genuinely-incompatible tool AND a merely-brew-absent tool in the
  same test, closing the exact regression a single-fixture test could not
  catch per this phase's own cross-AI review history).
- **`gnu-bash`'s same-named-binary detection fix is real, not just
  structural** — `installer/status.py::is_installed`'s unconditional
  `shutil.which(tool.cmd)` first line, then a `detect_path` fallback loop
  that does not filter by the checking method's own `arch`, both confirmed
  by direct read; `tests/test_status.py::test_gnu_bash_status_is_not_fooled_by_macos_system_bash`
  drives `is_installed` under a real `shutil.which` simulation, not merely
  asserting `cmd != "bash"`.
- **The catalog-disabled-row wiring has no gap across the three staging
  paths.** `CatalogScreen.__init__`/`_adapter`/`_row_cells`/`_detail_text`/
  `action_accept_recommends`/`on_tool_browser_accepted` and
  `installer/selection.py::unstaged_recommends` all read the same
  `self._unavailable`/`unavailable` mapping, default-safe (`{}`) when
  absent, and every one of the nine `UnifiedApp(...)` construction sites
  outside `setup.py` (confirmed by direct grep) is a kwarg call unaffected
  by the new optional parameter.
- **Every dated registry comment's citations check out.** `gnu-bash`'s
  cited line numbers for `installer/download.py`'s hardcoded `tar -xzf`
  calls (146, 207 — cited in the plan, not literally in the shipped
  comment) are exactly where they claim; `kitty`'s "two independent
  reasons" framing (no formula exists; `_applies`'s cask branch excludes
  non-macOS unconditionally) is accurate against `installer/resolve.py:50-52`;
  `container`'s `NO_METHOD`/`brew install container`/`min_os_version`
  citations match `installer/engine.py::install_tool` and
  `installer/resolve.py::_applies` exactly.
- Ran the full suite directly rather than trusting the SUMMARYs:
  `uv run pytest` (entire suite) passes clean, as does `uv run ruff check`
  and `uv run pyright` over every changed production file.

One Warning (a test-tripwire weakness) and two Info items follow. No
Critical/Blocker finding.

## Warnings

### WR-01: One of `test_apple_containers_entry_records_the_disabled_state_resolution`'s eight needles is trivially satisfied by the comment's own date stamp, not by the fact it's meant to pin

**File:** `tests/test_registry.py` (the `test_apple_containers_entry_records_the_disabled_state_resolution` test, added this phase) and `installer/registry.toml` (the `container` entry's comment)
**Issue:** The test asserts eight substrings are present in the ~50 lines
immediately above `id = "container"`, including a bare `"26"`:

```python
for needle in (
    "NO_METHOD",
    "macos",
    "version",
    "26",
    "arm64",
    "brew install container",
    "min_os_version",
):
    assert needle in window, f'missing {needle!r} above id = "container"'
```

Every dated comment in this registry (all six new entries this phase adds,
plus every pre-existing one) begins with the literal string
`# Verified 2026-09-06: ...`. The substring `"26"` is trivially present in
`"2026"` — confirmed directly:

```python
>>> "26" in "# Verified 2026-09-06: this is a REAL install action"
True
```

So this specific needle provides zero discriminating power: it would pass
even if every real mention of macOS version `26` (the `min_os_version`
floor this test exists to guard) were stripped from the comment, as long as
the mandatory `# Verified 2026-09-06:` date-stamp line remains above the
entry — which it always will, since every comment in this file is dated
the same way. The test's *other* seven needles (`NO_METHOD`, `macos`,
`version`, `arm64`, `brew install container`, `min_os_version`) are real,
specific signals not subject to this collision, so the test as a whole
still has meaningful coverage — but this one assertion is a no-op
tripwire, silently weaker than the other seven it sits beside, in a test
whose entire purpose (per this phase's own three cross-AI review cycles)
is to stop a future edit from silently reverting the macOS-version-gate
documentation.

**Fix:** Replace the bare `"26"` needle with a compound substring that
actually requires the version-floor fact, e.g. the literal JSON fragment
already present in the comment (`'"macos","version":"26"'`) or the
`min_os_version = "26"` phrase — either is immune to the date-stamp
collision:

```diff
-    "26",
+    '"macos","version":"26"',
```

## Info

### IN-01: `07-02-SUMMARY.md` calls Apple Containers a "cask/formula install," but the shipped entry is `kind = "brew"` only

**File:** `.planning/phases/07-system-user-tier-catalog-expansion/07-02-SUMMARY.md:32`
**Issue:** The summary states: "`Apple Containers` (a real `brew`
cask/formula install gated to macOS 26+ arm64 via `min_os_version`...)".
The actual shipped registry entry (`installer/registry.toml`, `id =
"container"`) declares exactly one method, `kind = "brew"`, and the
registry comment above it is explicit that this is a formula, not a cask
(`formulae.brew.sh/api/formula/container.json` — a real formula, contrasted
directly with `kitty`/`wezterm`'s cask-only entries added in the very same
phase). "cask/formula" reads as if either kind were used or the distinction
were ambiguous, which contradicts this phase's own otherwise-careful
formula-vs-cask precision (the `kitty`/`wezterm` comments go out of their
way to correct REQUIREMENTS.md's "may be in homebrew-core" framing with the
same formula/cask distinction). Low-impact — SUMMARY.md is a planning
artifact, not shipped code, and the registry entry itself is correct — but
worth tightening since a future reader skimming the SUMMARY for the ledger
of what shipped would get the wrong mental model.
**Fix:** `s/cask\/formula install/brew formula install/` in that line.

### IN-02: `07-02-SUMMARY.md`'s Task 3 bullet omits `on_tool_browser_accepted` from the list of filtered staging paths, understating what the code actually closes

**File:** `.planning/phases/07-system-user-tier-catalog-expansion/07-02-SUMMARY.md:37-44`
**Issue:** The summary states: "`unstaged_recommends` and
`action_accept_recommends` filter through the same `unavailable` signal so
a disabled row cannot be staged via the Recommends path either." The
shipped code (`installer/catalog_tui.py::on_tool_browser_accepted`, lines
385-391) additionally filters the *final* committed `ids` list through
`self._unavailable` before posting `Decided` — a third, independent
belt-and-suspenders check the plan itself calls out by name (07-02-PLAN.md,
Task 3, PART A) and that `tests/test_catalog_tui.py::test_unavailable_recommendation_is_not_staged_or_emitted`'s
second half specifically exercises (manually seeding an unavailable id into
`.selected` and confirming it is stripped from the emitted result). The
SUMMARY's two-of-three enumeration understates the actual closed surface;
not a code defect, just an incomplete record of what shipped.
**Fix:** Add `on_tool_browser_accepted` to the enumerated list in that
sentence.

---

## Second lane: codex-sol-high (parallel independent review, ONESHOT-RULES Rule 15)

Dispatched in parallel over the same diff (`47107fd..7bcd1b8`), via
`codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'`. Findings:
0 Critical, 2 High, 3 Medium.

### High — brew-only tools stay selectable in the same run they'd be dropped from install
Independently rediscovers the browse-time (`platform_could_support`) vs.
install-time (`has_brew`) snapshot disagreement this phase's own plan
review already surfaced and explicitly accepted as **T-07-13** in
`07-02-PLAN.md`'s threat register: a static per-run `Platform` snapshot
means a tool needing Homebrew still resolves to nothing at install time
even if the user selects Homebrew in the same run, because nothing
re-resolves availability mid-run after Homebrew installs. **Disposition:
no new action** — already reasoned as an existing, pre-Phase-7 contract
this phase does not change, with a mid-run refresh explicitly deferred to
a future phase. Codex's independent rediscovery is useful corroboration
that the gap is real, not evidence it was missed.

### High — Oh My Zsh's `install.sh` is fetched from a mutable `master` branch
Independently rediscovers **T-07-01** from `07-01-PLAN.md`'s threat
register (Tampering, accepted at `low`), and matches the same trust
posture this registry already accepts for its other unpinned `kind="script"`
bootstraps (`rustup`, `sdkman`, the `codex`/`claude` CLI installers).
**Disposition: no new action this phase** — codex rates this High where
the phase's own review rated it low/accepted; recorded as a genuine
severity disagreement worth a future project-wide policy discussion (pin
+ verify a script hash before piping to `sh`), not a Phase-7-scoped fix,
since it would apply identically to every other unpinned script installer
already in this registry, not something `oh-my-zsh` introduces.

### Medium — `kitty`'s cask has no macOS-version floor (fixed)
**New, real, actionable finding** — confirmed live:
`formulae.brew.sh/api/cask/kitty.json` declares `depends_on.macos >= 12`,
which the shipped `kitty` cask method did not encode, so
`platform_could_support` would leave `kitty` enabled on an unsupported
old macOS. **Fixed directly** (Rule 10): added `min_os_version = "12"` to
`kitty`'s `cask` method, a registry comment recording the fix and its
source, and `test_kitty_cask_blocks_a_too_old_macos_version` (mirrors the
existing Apple Containers version-gate test pattern). `wezterm`'s cask
has no version constraint upstream (`depends_on.macos` is an empty
object), so no equivalent fix was needed there.

### Medium — WezTerm's normal (non-extract-and-run) invocation assumes FUSE
This is the same FUSE-dependency this phase's own Rule-10 fix already
named and classified explicitly (07-03-PLAN.md's Tier-3 verification
section): AppImages generally need FUSE to self-mount, which the
Tier-3 container proved by requiring `APPIMAGE_EXTRACT_AND_RUN=1`. The
project's assumption is that ordinary desktop Linux (including Bazzite)
ships FUSE, unlike a stripped verification container — this is a
reasonable real-world assumption AppImage's own design already depends
on. **Disposition: accepted, no new action** — a documented, pre-existing
constraint of the AppImage format itself, not a defect this project's
code introduces; a future phase adding a headless/minimal-Linux target
could revisit whether a wrapper enforcing `APPIMAGE_EXTRACT_AND_RUN=1` is
worth adding.

### Medium — `min_os_version` typos fail open at registry-load time
Independently rediscovers **T-07-14** from `07-02-PLAN.md`'s threat
register (accepted, covered by the existing Phase 6 registry-authoring
verification checklist / human-review diligence, with a dedicated
schema-validation pass noted as future-phase follow-up). **Disposition:
no new action** — already assessed and accepted with the same reasoning
codex independently arrived at.

## Resolution status

Of codex's 5 findings, 3 are independent rediscoveries of gaps this
phase's own 3-cycle plan review already surfaced and explicitly accepted
(T-07-13, T-07-01, T-07-14) — useful corroboration, no new action
required. 1 (WezTerm/FUSE) restates a constraint this phase's own Rule-10
fix already classified and accepted. 1 (kitty's missing macOS-version
floor) was genuinely new and has been fixed directly: `min_os_version =
"12"` added to the `kitty` cask method, plus a regression test. `make
validate && make test` re-run clean after the fix. The internal lane's
Warning (WR-01, a no-op test needle) was also fixed directly (replaced
the bare `"26"` needle with the exact `min_os_version = "26"` phrase,
immune to the `# Verified 2026-09-06:` date-stamp collision). Both Info
items (SUMMARY wording) were corrected in `07-02-SUMMARY.md`. No
Critical/Blocker finding from either lane; Checklist item 5 is satisfied.

---

_Reviewed: 2026-09-06T11:50:19Z (internal lane); codex-sol-high lane run in parallel same date_
_Reviewers: Claude (gsd-code-reviewer) + codex-sol-high (independent parallel lane, Rule 15)_
_Depth: deep_
