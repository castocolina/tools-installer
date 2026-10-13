---
phase: 10-agent-cli-ergonomics
verified: 2026-09-06T20:15:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification: []
---

# Phase 10: Agent CLI Ergonomics Verification Report

**Phase Goal:** `codex` and `opencode` get the same permissive-mode convenience `claude-skip` already provides, honestly labeled per their real (differing) semantics, and `cursor-agent` reliably gets a known-good default model on any bare invocation instead of silently inheriting whatever was last selected elsewhere.
**Verified:** 2026-09-06T20:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `codex-skip` aliases `codex` to its verified real bypass-permissions flag, with user-supplied flags always respected. | ✓ VERIFIED | `installer/tweaks.py:74,187-193`: `_CODEX_BODY = "alias codex='codex --dangerously-bypass-approvals-and-sandbox'"`, `TweakBundle("codex-skip", ...)` in `BUNDLES`, `requires=()`/`executables=()`. Directly rendered the bundle's block via a live Python call (`tweak_block`) — output matches the source exactly: `alias codex='codex --dangerously-bypass-approvals-and-sandbox'`. Alias text-substitution appends any further user args by shell construction (same mechanism `claude-skip` already relies on) — no code change needed to prove this, it is how bash/zsh alias expansion works. Flag was live-verified by the phase's own research (10-RESEARCH.md Summary #1, `codex --help`/`codex exec --help`), not typed from memory. `installer/wizard_app.py:957-961` gives it its own honest detail-panel entry ("trusted, disposable workspaces" caveat, mirroring `claude-skip`'s). Tests: `tests/test_tweaks.py` (`test_codex_skip_body_matches_the_verified_flag` and peers), `tests/test_policy_tweaks.py#test_codex_skip_policy_round_trips`, `tests/test_wizard_app.py#test_policy_detail_panel_explains_codex_skip` — all present and pass (targeted re-run below). |
| 2 | `opencode-auto` aliases `opencode` to `opencode --auto`, with Policies detail-panel copy that accurately describes its narrower (not full-bypass) semantic. | ✓ VERIFIED | `installer/tweaks.py:79`: `_OPENCODE_BODY = "alias opencode='opencode --auto'"`. `TweakBundle("opencode-auto", "opencode auto-approve", "alias opencode='opencode --auto' — auto-approves permissions not explicitly denied; not a full bypass", ...)` — the label itself avoids "skip-permissions" wording (verified against `claude-skip`/`codex-skip`'s labels, which do use it). `installer/wizard_app.py:963-967`: detail panel states "Narrower than claude-skip's/codex-skip's full bypass: explicit deny rules in your own opencode config still apply." Live-rendered block confirmed: `alias opencode='opencode --auto'`. Tests: `test_opencode_auto_description_states_it_is_narrower_than_a_full_bypass`, `test_opencode_auto_policy_round_trips`, `test_policy_detail_panel_explains_opencode_auto_is_narrower_than_a_full_bypass` — present and pass. |
| 3 | Invoking `cursor-agent`/`cursor` with no `--model` injects a live-verified, plain model slug (no bracket syntax); passing an explicit `--model` is never overridden. | ✓ VERIFIED (behaviorally, live shell execution by this verifier, not just reading test code) | `installer/tweaks.py:93,121-141`: `_CURSOR_DEFAULT_MODEL = "gpt-5.6-sol-high"` (live-confirmed via `cursor-agent models`, 10-RESEARCH.md Summary #3 — plain slug, no bracket parameterization anywhere in the body). I independently rendered the real `tweak_block()` output for `cursor-agent-model`, wrote it to a scratch file, planted a stub `cursor-agent` binary on `PATH`, and sourced the block in **real bash and zsh subprocesses** (isolated `HOME`/`ZDOTDIR`, never touching this machine's real shell config): (a) bare `cursor-agent chat hello` → stub received `--model gpt-5.6-sol-high chat hello`; (b) `cursor-agent --model my-custom-model chat hello` → stub received the argv completely unmodified (space form respected); (c) `cursor-agent --model=my-custom-model chat hello` → unmodified (equals form respected); (d) `cursor chat hello` → stub received `--model gpt-5.6-sol-high chat hello` (delegation inherits injection); (e) `cursor-agent -- explain --model` → stub received `--model gpt-5.6-sol-high -- explain --model` (the `--`-boundary fix correctly treats the post-`--` `--model` token as positional text, not a flag). All five live results match the plan's stated and reviewed behavior exactly. |
| 4 | All three tweaks survive the target CLI self-updating in place (durable by construction — shell alias/function lookup precedes PATH search). | ✓ VERIFIED | All three `TweakBundle` entries (`codex-skip`, `opencode-auto`, `cursor-agent-model`) declare `requires=()`/`executables=()` — no `ManagedExecutable`, no file-based shim anywhere in the tool's own install directory; every bundle is a pure alias/function written into `~/.myshellrc`, exactly the existing `claude-skip` shape. Shell alias/function lookup precedes PATH search by construction (bash/zsh semantics), so a self-update rewriting the vendor binary on PATH cannot remove or stale the tweak. `tests/test_tweaks.py#test_bundles_have_stable_ids_and_order` pins the full 7-entry `BUNDLES` id list including all three. Additionally verified the split-PATH-link-mode fix this phase shipped as a prerequisite for durability actually reaching a real shell: called `tweak_policy(codex_skip_bundle, rc_path=<tmp>/.myshellrc, ensure_sourced_from=(<tmp>/.zshrc,))` directly, confirmed `.apply()` wrote the alias into `.myshellrc` AND wired a `source .myshellrc` line into `.zshrc`, then sourced the resulting `.zshrc` in a **fresh bash subprocess** and confirmed `alias codex` resolves correctly — proving the tweak reaches a real shell under split link mode, not merely a documented claim. |

**Score:** 4/4 truths verified. No truths left unverified — SC#3's live-shell behavior (the truth most likely to hide a stub) was independently exercised by this verifier in real bash/zsh subprocesses with a stub binary, not merely re-read from test source.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/tweaks.py` | 3 new `TweakBundle` entries (`codex-skip`, `opencode-auto`, `cursor-agent-model`), the conditional-injection function body | ✓ VERIFIED | Read in full. All three bundles present in `BUNDLES` (7 entries total, order: docker, countdown, claude-skip, codex-skip, apt-upgrade, opencode-auto, cursor-agent-model). `_CURSOR_AGENT_BODY` implements `unalias ... || true` guard, `local a`, `--` boundary break, `command`-guarded self-calls, and the bare `cursor()` delegation — every dual-lane review fix (WR-01, WR-02, codex-sol-high's `--` finding) is present in the committed source, not just claimed. |
| `installer/policy.py` | `_TWEAK_ENABLE_HINT`/`_TWEAK_DISABLE_HINT` split, `tweak_policy`'s `ensure_sourced_from` parameter | ✓ VERIFIED | Read in full. Two distinct hint constants exist (enable names `source ~/.myshellrc`; disable deliberately never contains that string). `ensure_sourced_from: tuple[Path, ...] = ()` parameter present, wired to `installer.shellrc.ensure_source` inside `_apply()`, reported as its own `PolicyLayer`. `ban_policy`'s own `_RELOAD_HINT`/`hash -r` usage is untouched (correctly — PATH shims genuinely need `hash -r`). |
| `installer/wizard_app.py` | Per-bundle `_policy_detail` entries + honest narrower-semantic copy for `opencode-auto` and scoped-removal copy for `cursor-agent-model` | ✓ VERIFIED | Read lines 928-1015. `tweak:codex-skip`, `tweak:opencode-auto`, `tweak:cursor-agent-model` all present with the exact honest copy the plan specified (narrower-than-full-bypass wording for opencode-auto; "active before this block loads" scoping for the unalias behavior, not a blanket "removes any alias" claim). A uniform `~/.myshellrc`-sourcing explanation is appended to every `tweak:*` Policy's detail text. |
| `setup.py` | `_build_app`'s `ensure_sourced_from` wiring at BOTH call sites (`--guard` and the normal no-flags `_select_catalog` path); `main()`'s normal branch resolves `link_mode` before `run_wizard` | ✓ VERIFIED | Read lines 142-260 and 413-480 directly. `_build_app` passes `ensure_sourced_from=tuple(rc_paths) if link_mode == "split" else ()` into every `tweak_policy(...)` call (line 222). `_select_catalog` now takes `link_mode: str = "centralized"` and forwards it to `_build_app` (lines 298-299). `main()`'s normal (no-flags) branch resolves `link_mode = _resolve_link_mode(options.link_mode)` BEFORE calling `run_wizard`, and passes `select_catalog=lambda catalog_tools: _select_catalog(catalog_tools, link_mode=link_mode)` (lines 454-463) — confirms cross-AI review cycle 3's HIGH finding (the primary, most-used entry point building its Policies TUI with the wrong default) is genuinely fixed, not merely documented. |
| `tests/test_tweaks.py`, `tests/test_policy_tweaks.py`, `tests/test_wizard_app.py`, `tests/test_setup.py` | Round-trip, structural, collision, `set -e`, `--` boundary, and split-mode fresh-shell coverage | ✓ VERIFIED | All named tests from 10-01-SUMMARY.md's coverage table and 10-REVIEW.md's resolution table (`test_cursor_agent_unalias_guard_does_not_abort_sourcing_under_set_e`, `test_cursor_agent_loop_variable_does_not_leak_into_the_calling_shell`, `test_cursor_agent_stops_scanning_at_double_dash_boundary`, `test_bundles_have_stable_ids_and_order`, and the rest) confirmed present via `grep -n "def test_..."` against the actual test files — not just named in the SUMMARY. Targeted re-run (`-k "codex_skip or opencode_auto or cursor_agent or cursor_delegates or bundles_have_stable"` across all four files): 22 passed, 0 failed. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `installer/tweaks.py`'s `BUNDLES` (3 new entries) | Policies screen + uninstall sweep | `setup.py`'s `applicable_bundles(platform)` → `tweak_policy(bundle, ...)` loop; `installer.uninstall.active_policies`/`sweep_policies` | ✓ WIRED | Confirmed by reading `setup.py:180,207-224` and `installer/uninstall.py` directly — both iterate `BUNDLES`/`bundles` generically; zero edits needed in `installer/uninstall.py` for the three new bundles (confirmed unchanged by this phase's diff, matching the phase's own "zero new plumbing" thesis). |
| Each new bundle's block | The real shell | `~/.myshellrc`, sourced by the user's interactive bash/zsh (never a file this project writes into a tool's own install dir) | ✓ WIRED | Live-verified: rendered `tweak_block()` output sourced directly in real bash and zsh subprocesses; aliases/functions resolved correctly with no file-based shim involved anywhere. |
| `installer/wizard_app.py`'s `_policy_detail` | User-facing honesty requirement (REQ-opencode-auto-tweak, REQ-cursor-agent-default-model-wrapper) | `details` dict entries keyed by Policy id | ✓ WIRED | Confirmed present at the exact keys (`tweak:opencode-auto`, `tweak:cursor-agent-model`) with the required honest wording; not relying on the generic one-line fallback. |
| `installer/policy.py`'s `tweak_policy` | Every `tweak:*` Policy's reload hint and split-mode sourcing | Single shared closure, `ensure_sourced_from` parameter | ✓ WIRED | Confirmed one function serves all 7 bundles; the fix automatically covers `docker`/`countdown`/`claude-skip`/`apt-upgrade` too, as claimed. |
| `setup.py`'s `_build_app` | `installer.locations.rc_paths_for_mode` | `ensure_sourced_from=tuple(rc_paths) if link_mode == "split" else ()`, passed at BOTH call sites | ✓ WIRED | Live-verified end-to-end: applied a `codex-skip` policy with `ensure_sourced_from=(<tmp>/.zshrc,)`, confirmed both files' contents, then sourced the resulting `.zshrc` in a fresh bash subprocess and confirmed `alias codex` actually resolves — not merely a code-reading confirmation. |

### Data-Flow Trace (Level 4)

Not applicable in the conventional (DB → API → UI) sense — this phase's "data" is the hardcoded, live-verified flag/slug strings that flow verbatim from `installer/tweaks.py` source constants into the shell block written to `~/.myshellrc`. Traced `_CURSOR_DEFAULT_MODEL = "gpt-5.6-sol-high"` → `_CURSOR_AGENT_BODY` (via f-string) → `tweak_block()` → `write_tweak()` → real file on disk → sourced by a real shell → observed in the stub binary's captured argv. No static fallback or mock masking a missing real source; the "source of truth" is intentionally a source-level constant (not a live external fetch), consistent with the architecture of every other tweak in this file (`claude-skip`, `docker`, etc.).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Bare `cursor-agent` gets default model injected | Sourced real `tweak_block()` output in bash w/ stub `cursor-agent` on PATH; ran `cursor-agent chat hello` | `ARGV: --model gpt-5.6-sol-high chat hello` | ✓ PASS |
| Explicit `--model X` (space form) never overridden | `cursor-agent --model my-custom-model chat hello` | `ARGV: --model my-custom-model chat hello` (unmodified) | ✓ PASS |
| Explicit `--model=X` (equals form) never overridden | `cursor-agent --model=my-custom-model chat hello` | `ARGV: --model=my-custom-model chat hello` (unmodified) | ✓ PASS |
| `cursor` delegates and inherits injection | `cursor chat hello` | `ARGV: --model gpt-5.6-sol-high chat hello` | ✓ PASS |
| `--` end-of-options boundary respected | `cursor-agent -- explain --model` | `ARGV: --model gpt-5.6-sol-high -- explain --model` (post-`--` `--model` treated as text) | ✓ PASS |
| Pre-existing conflicting alias actively removed (bash, `expand_aliases`) | alias `cursor-agent`/`cursor` defined first, then block sourced, then invoked | Both invocations reached the tweak's own function (stub argv shown), not the old alias | ✓ PASS |
| Same collision-removal under zsh (isolated `ZDOTDIR`) | Same script under `zsh -i` with isolated `ZDOTDIR` | Both invocations reached the tweak's own function | ✓ PASS |
| `unalias ... || true` does not abort sourcing under `set -e` (bash) | `set -e; source <block>; echo REACHED; cursor-agent chat hello` | `REACHED` printed, then correct stub argv, exit 0 | ✓ PASS |
| Same `set -e`/`setopt err_exit` safety under zsh (isolated `ZDOTDIR`) | `setopt err_exit; source <block>; echo REACHED; cursor-agent chat hello` | `REACHED` printed, then correct stub argv, exit 0 | ✓ PASS |
| Loop variable `a` does not leak into calling shell | `a='my-own-var'; cursor-agent chat hello >/dev/null; echo $a` | `a is still: my-own-var` | ✓ PASS |
| Split-mode `ensure_sourced_from` reaches a real shell | Applied `codex-skip` with `ensure_sourced_from=(.zshrc,)`, sourced `.zshrc` in fresh bash | `alias codex='codex --dangerously-bypass-approvals-and-sandbox'` resolved | ✓ PASS |

Every spot-check above was run directly by this verifier against the real rendered bundle bodies in real bash/zsh subprocesses with a `tmp`-scoped stub binary — never the real installed `cursor-agent`, never this machine's real `~/.myshellrc`, per ONESHOT-RULES Rule 5.

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` convention in this repository for this phase; the phase's own verification strategy is the unit/integration test suite plus this verifier's independent live-shell spot-checks (above), which supersede reliance on any prose PASS-marker claim.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| REQ-codex-skip-tweak | 10-01 | `codex-skip` tweak, parallel to `claude-skip`, aliasing `codex` to its bypass-permissions flag | ✓ SATISFIED | Truth #1 above. |
| REQ-opencode-auto-tweak | 10-01 | `opencode-auto` aliasing `opencode` to `opencode --auto`, honestly narrower semantic | ✓ SATISFIED | Truth #2 above. |
| REQ-cursor-agent-default-model-wrapper | 10-01 | Plain, live-verified `--model` slug injection, explicit `--model` never overridden, no bracket syntax, no unconditional 1M-context claim | ✓ SATISFIED | Truth #3 above; copy in `wizard_app.py:972-974` says "requests" not "guarantees"/"verifies" the context window, matching 10-RESEARCH.md Pitfall 4/Assumption A2's caution. |
| REQ-agent-tweak-self-update-durability | 10-01 | Shell alias/function mechanism (never file-based shim); `cursor-agent` wrapper specifically needs a function | ✓ SATISFIED | Truth #4 above; `cursor-agent`/`cursor` are shell functions (not plain aliases), confirmed by direct source read and live execution. |

No orphaned requirements found — all four requirements this phase owns (per `.planning/REQUIREMENTS.md`'s "Phase 10 | Complete" rows) are declared in `10-01-PLAN.md`'s frontmatter and are the only four requirements mapped to Phase 10.

### Anti-Patterns Found

Scanned `installer/tweaks.py`, `installer/policy.py`, `installer/wizard_app.py`, `setup.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER`, "not yet implemented", empty-return stubs, and hardcoded-empty-data patterns.

- `installer/tweaks.py:19,66,232` — `_BIN_DIR_PLACEHOLDER` — a pre-existing constant name (predates this phase, used by the unrelated `countdown` bundle) that happens to contain the substring "PLACEHOLDER"; it is a real, functioning template-substitution sentinel, not a stub marker. Not a finding.
- `installer/wizard_app.py:532` — `"not available"` — a pre-existing `UninstallState` enum display label, unrelated to this phase's tweaks. Not a finding.
- `installer/wizard_app.py:1286` — a comment referencing a UI "placeholder... screen" (an actual Textual screen-stacking concept in this codebase, pre-existing, unrelated to Phase 10). Not a finding.

No debt markers (`TBD`/`FIXME`/`XXX`), no `TODO`/`HACK`, and no stub-return patterns found in any of the four files this phase modified. Zero blockers.

### Full Verification Run (independently re-executed, not trusted from SUMMARY.md or 10-REVIEW.md)

Ran `make validate && make test` myself directly on the current HEAD (`87ab436`, clean working tree, `git status --short` empty):

- `make validate`: `ruff check` (all checks passed), `ruff format --check` (91 files already formatted), `pyright` (0 errors, 0 warnings, 0 informations), `bandit` (clean, B404/B603/B310 deliberately skipped per project convention, documented in the Makefile), `vulture` (clean), `shellcheck install.sh` (clean).
- `make test` / `pytest --cov`: full suite genuinely green — **1329 passed**, coverage **99.41%** (floor 90%), zero failures, zero errors. (Note: this project's shell environment routes `pytest`/`uv run pytest` through an `rtk` token-optimization proxy that, in this verification session, silently swallowed the final pass/fail summary line under `-q`/`--cov` combinations; bypassing it via `env -i ... uv run python -m pytest` reproduced the identical test run and confirmed the real "1329 passed" summary and 99.41% coverage total — this is an environment/tooling quirk local to this verification session, not a project defect, and is noted here only so the evidence trail is transparent about how the number was obtained.)
- Re-ran a targeted subset for this phase specifically: `-k "codex_skip or opencode_auto or cursor_agent or cursor_delegates or bundles_have_stable"` across `tests/test_tweaks.py tests/test_policy_tweaks.py tests/test_wizard_app.py tests/test_setup.py` → **22 passed, 148 deselected**, 0 failed.
- Confirmed the dual-lane 10-REVIEW.md fixes are actually present in the committed code (not just claimed as fixed): `|| true` after `unalias` (WR-01), `local a` (WR-02), the `--` boundary `break` (codex-sol-high finding) — all three read directly from `installer/tweaks.py:107-141` above, and independently reproduced live via real bash/zsh execution in the Behavioral Spot-Checks section above (not merely re-read from the review's own transcript).

## Human Verification Required

None. Every ROADMAP success criterion, every artifact, every key link, and the phase's most execution-risk-prone behavior (the `cursor-agent`/`cursor` conditional-injection function, including the collision-removal and `set -e` safety fixes) were independently exercised by this verifier against real bash/zsh subprocesses — not left to test-code reading or SUMMARY.md narrative.

## Gaps Summary

No gaps. All four ROADMAP success criteria are structurally implemented, wired end-to-end through the real production call chain (`BUNDLES` → `tweak_policy` → Policies screen / uninstall sweep, and `setup.py`'s two `_build_app` call sites → `ensure_sourced_from` → `installer.shellrc.ensure_source`), covered by comprehensive passing tests, and independently re-verified live by this verifier in real shell subprocesses rather than trusted from prior reports. `make validate && make test` is genuinely green on HEAD `87ab436` (1329 passed, 99.41% coverage, zero lint/type/security/dead-code findings). The three known, dual-lane-reviewed non-blocking items from 10-REVIEW.md remain correctly dispositioned and require no further action from this verification:

- **WR-03** (split-mode gap re-appears for the standalone `tools-installer --guard` entry point under the *default*/centralized link mode) — correctly scoped in 10-REVIEW.md as a pre-existing limitation affecting every tweak bundle (`docker`, `countdown`, `claude-skip`, etc.), not a regression this phase introduced. Phase 10 only added bundles to an already-existing mechanism; fixing the standalone `--guard` entry point's own centralized-mode wiring is out of this phase's scope and is not one of Phase 10's own ROADMAP success criteria. This is not a gap in Phase 10's own deliverable.
- **WR-04** (unconditional `--model` injection into non-chat subcommands) — empirically re-verified as a non-issue against the real installed `cursor-agent` binary (`cursor-agent --model gpt-5.6-sol-high update`/`--version` both exit 0 correctly); no change needed.
- **IN-01** (structural test uses substring-index slicing) — non-blocking style note, accepted as-is.

---

_Verified: 2026-09-06T20:15:00Z_
_Verifier: Claude (gsd-verifier)_
