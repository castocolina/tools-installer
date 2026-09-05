---
phase: 5
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-05T00:00:00Z
review_cycle: 2
plans_reviewed: [05-01-PLAN.md, 05-02-PLAN.md, 05-03-PLAN.md, 05-04-PLAN.md]
plans_revision: 07873a1
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
prior_cycles:
  1:
    reviewers: [opencode-sol]
    models:
      opencode-sol: "openai/gpt-5.6-sol (reasoning=high)"
---

# Cross-AI Plan Review — Phase 5 (Cycle 2)

> **Reviewer note — no substitution this cycle.** The project's configured default reviewer
> `opencode-plan-review` (`review.reviewer_instances.opencode-plan-review`, model
> `router-env/my-plan-review`) was probed before the run and answered normally, so the cycle-1
> substitution to `opencode-sol` was NOT repeated. Cycle 2 ran on the configured default.
> One reviewer produced a section, so the two-or-more-reviewer consensus gate does not engage.

Plans reviewed at revision `07873a1` ("docs(05): revise phase 5 plans for cross-AI review
cycle 1"), which claims to resolve all 6 HIGH and 13 actionable non-HIGH findings from cycle 1
(preserved verbatim below under "Cycle 1").

## OpenCode Review (opencode-plan-review)

## Cycle-1 Resolution Verification

Phase 5 remains unexecuted: current installation still short-circuits PATH-visible tools before method resolution (`installer/engine.py:80-83`), and current pnpm replay remains name-only. The verdicts below evaluate whether the revised plans provide executable mechanisms.

| # | Cycle-1 concern | Verdict | Evidence and mechanism |
|---|---|---|---|
| 1 | Brownfield standalone `mmdc` | **PARTIALLY RESOLVED** | The plans reproduce the skipped grouped invocation and prove a Doctor replay remedy (`05-01-PLAN.md:239-269`; `05-04-PLAN.md:69-76`). However, automatic split-group detection is explicitly not implemented; affected users must discover and manually invoke Doctor (`05-03-PLAN.md:492-505`, `05-03-PLAN.md:633`). |
| 2 | Unsupported platforms | **PARTIALLY RESOLVED** | Linux arm64 is correctly gated through `arch = ["amd64"]` and dependency unavailability tests (`05-03-PLAN.md:305-327`, `05-03-PLAN.md:379-398`). Linux amd64 methods still resolve even when required Chrome shared libraries are absent; the plan only documents that prerequisite (`05-03-PLAN.md:532-540`). |
| 3 | Missing pnpm/Node floors | **RESOLVED** | The plan defines shared pnpm floors, a Node floor, fail-closed probes, and tests proving no install runs after an unmet floor (`05-01-PLAN.md:503-513`, `05-01-PLAN.md:528-576`, `05-01-PLAN.md:590-603`). |
| 4 | Persistent `--allow-build` trust | **PARTIALLY RESOLVED** | Persistence is now documented, constrained to in-group package names, tested, and entered in all threat registers (`05-01-PLAN.md:349-357`, `05-01-PLAN.md:448-454`, `05-01-PLAN.md:624`). But the claim that `^25` bounds persistent trust is incomplete: the plan itself acknowledges that a later version installed by an unrelated command inherits the package-level allowance (`05-01-PLAN.md:624`; `05-03-PLAN.md:217-222`). |
| 5 | Unpinned Puppeteer | **PARTIALLY RESOLVED** | Standalone Puppeteer and the expected grouped path use `^25` (`05-03-PLAN.md:310-339`). The fallback branch deliberately leaves grouped Puppeteer at mutable `latest` if versioned comma syntax fails (`05-03-PLAN.md:354-367`, `05-03-PLAN.md:437`). |
| 6 | Tier counts | **RESOLVED** | Plan 05-02 updates AI to 10 (`05-02-PLAN.md:159-165`, `05-02-PLAN.md:181-190`); plan 05-03 then updates user to 36 (`05-03-PLAN.md:406-410`, `05-03-PLAN.md:429-443`). |
| 7 | Double Puppeteer installation | **NOT RESOLVED** | The intended clean path still installs Puppeteer standalone and then again in the comma group (`05-01-PLAN.md:190-214`). The tracer records group and shim state, but no mechanism removes the duplicate invocation or proves update/removal lifecycle safety. |
| 8 | Replay loses versions and custom groups | **PARTIALLY RESOLVED** | Registry-known groups and pins are reconstructed by `NodeInstallPolicy` (`05-04-PLAN.md:171-230`). Unknown versions and hand-created groups remain unrecoverable and are explicitly accepted (`05-04-PLAN.md:257-270`, `05-04-PLAN.md:403`). |
| 9 | Grouped-package uninstall coupling | **PARTIALLY RESOLVED** | The coupling and externally managed uninstall status are documented (`05-03-PLAN.md:506-513`) and text-guarded (`05-03-PLAN.md:579-599`). No removal/recovery behavioral test or user-facing warning is added. |
| 10 | Weak package-legitimacy gate | **PARTIALLY RESOLVED** | Repository identity now uses normalized exact equality, and current `latest` integrity is recorded (`05-03-PLAN.md:169-203`, `05-03-PLAN.md:226-236`). The mutable `^25` installation is not bound to that recorded artifact, which the plan explicitly accepts (`05-03-PLAN.md:627-630`). |
| 11 | Unsafe `_opt_pkg_list()` | **RESOLVED** | The executor must first require an actual list and raise `ExecutorError` for strings or invalid members; direct-construction tests are specified (`05-01-PLAN.md:415-436`, `05-01-PLAN.md:479-483`). |
| 12 | `REQUIREMENTS.md` mismatch | **RESOLVED** | Plan 05-03 modifies the requirement in place and tests that no separate `chrome-headless-shell` entry exists (`05-03-PLAN.md:369-377`, `05-03-PLAN.md:399-400`, `05-03-PLAN.md:441-442`). |
| 13 | Incorrect Puppeteer `bin` claim | **RESOLVED** | The plan now records the object-form `bin` map and derives `cmd = "puppeteer"` from its key (`05-03-PLAN.md:288-296`). |
| 14 | Incorrect `PLAN_BASE` path | **RESOLVED** | The acceptance command now reads the full summary path and fails closed when the hash is absent (`05-04-PLAN.md:372-377`). |
| 15 | Contradictory working-tree criterion | **RESOLVED** | The working-tree check was removed in favor of a commit-range path-filtered diff (`05-04-PLAN.md:162-169`, `05-04-PLAN.md:377`). |
| 16 | Replay return includes flags | **RESOLVED** | `_reinstall_parts` separates flags from specs, and `reinstall_node_globals` must return `tuple(specs)` with direct regression coverage (`05-04-PLAN.md:198-230`, `05-04-PLAN.md:290`). |
| 17 | Duplicate `allow_build` entries | **RESOLVED** | Policy construction de-duplicates allowances with ordered `dict.fromkeys`; acceptance requires exactly one Puppeteer allowance (`05-04-PLAN.md:181-193`, `05-04-PLAN.md:284-286`). |
| 18 | Crossed `gh` citation | **RESOLVED** | The corrected registry location and explanation are now explicit (`05-02-PLAN.md:101-104`). |
| 19 | “No new mechanisms” scope tension | **RESOLVED** | The deviation and necessity are explicitly recorded in plans 05-01 and 05-03 and scheduled for `PROJECT.md` (`05-01-PLAN.md:87-98`; `05-03-PLAN.md:97-106`, `05-03-PLAN.md:560-568`). |

## Summary

**11 resolved, 7 partially resolved, 1 not resolved.** The revision substantially improves platform gating, version preflight, replay fidelity, requirements alignment, and executable verification. It is not yet converged because brownfield repair remains manual, Linux amd64 can still report success without runtime prerequisites, and persistent package-level trust is described as more tightly bounded than it really is.

## Strengths

- The Linux arm64 gate uses the existing resolution and dependency-blocking mechanisms rather than adding special-case control flow (`05-03-PLAN.md:313-327`, `05-03-PLAN.md:395-398`).
- Version checks have one shared source of truth and fail before side effects, while legacy node methods retain byte-identical behavior with zero probes (`05-01-PLAN.md:528-576`, `05-01-PLAN.md:593-603`).
- CodeGraph’s entry is checksum-backed, platform-tested, and accompanied by the required tier-count update (`05-02-PLAN.md:123-176`, `05-02-PLAN.md:181-190`).
- Replay preview and execution are intentionally driven by the same policy and argv builder, with direct equality checks (`05-04-PLAN.md:220-245`, `05-04-PLAN.md:284-292`, `05-04-PLAN.md:322-333`).
- The revision corrects all six concrete plan defects from source grounding: malformed-list handling, requirement text, Puppeteer `bin`, summary path, working-tree criterion, and replay return semantics (`05-01-PLAN.md:420-436`; `05-03-PLAN.md:288-296`; `05-04-PLAN.md:224-230`, `05-04-PLAN.md:377`).

## Concerns

- **HIGH — Brownfield users are still left broken until they manually run Doctor.** Current code returns `ALREADY_INSTALLED` before resolving the new method (`installer/engine.py:80-83`), and the plan explicitly declines automatic split-group detection (`05-03-PLAN.md:492-505`, `05-03-PLAN.md:633`). A documented remedy does not make upgrade behavior self-healing.
- **HIGH — Linux amd64 availability remains optimistic.** Puppeteer resolves on every supported Linux amd64 platform (`05-03-PLAN.md:265-270`), but its shared-library prerequisites are only documented (`05-03-PLAN.md:532-540`). The current engine treats a successful pnpm exit as installation success without a render/runtime check (`installer/engine.py:89-94`).
- **HIGH — The persistent trust boundary is still misstated.** `--allow-build` authorizes the package name persistently, including versions installed by commands outside this installer, yet the plans repeatedly describe `^25` as bounding the authorization (`05-01-PLAN.md:624`; `05-03-PLAN.md:217-222`, `05-03-PLAN.md:627-628`). The pin only constrains argv generated by this project.
- **MEDIUM — Plan 05-01 has an inverted task dependency.** Task 2 calls `parse_version`, but Task 4 owns that function; the plan tells the executor to implement part of Task 4 before completing Task 2 despite Task 2’s file scope excluding `installer/versions.py` (`05-01-PLAN.md:296-298`, `05-01-PLAN.md:363-373`, `05-01-PLAN.md:491-493`).
- **MEDIUM — The version-pin branch conflicts with the tracer’s hard gate.** The plans say a failed versioned-comma probe should lead to an unpinned fallback (`05-03-PLAN.md:354-367`), but plan 05-01’s automated verifier exits nonzero when that probe fails and requires both success markers (`05-01-PLAN.md:278-285`). The fallback cannot be reached under normal task execution.
- **MEDIUM — Clean installs deliberately install Puppeteer twice.** The tracer gathers state but the production sequence remains two installs (`05-01-PLAN.md:190-214`). It does not execute removal or upgrade tests for the resulting group/shim ownership.
- **MEDIUM — Version parsing can accept malformed floors.** The required parser accepts any input yielding one leading numeric component and zero-fills the rest (`05-01-PLAN.md:517-526`), while model validation claims malformed `min_node` values are rejected (`05-01-PLAN.md:321-322`). Inputs such as `22.bad` are not specified or tested.
- **MEDIUM — Legitimacy evidence is not bound to what gets installed.** The gate records integrity for mutable `dist-tags.latest` (`05-03-PLAN.md:187-203`), while execution installs the range `^25` (`05-03-PLAN.md:310-339`). Registry metadata can change between those operations, so the evidence may describe different bytes.

## Suggestions

- Add automatic brownfield reconciliation before the installed-state short circuit, based on pnpm group membership rather than `shutil.which`.
- Make Linux amd64 availability conditional on a verified prerequisite check, or add a post-install smoke test that prevents a false-success outcome.
- Describe persistent `allow_build` accurately as trust in all future releases under that package name, or remove/reconcile the persisted allowance after installation.
- Move `parse_version`, `meets_minimum`, probe support, and their tests into Task 2; leave executor preflight wiring in the later task.
- Choose one tracer contract: either hard-require versioned comma syntax and remove the fallback, or permit probe failure and make the fallback executable.
- Add container cases for reinstall/update/removal after the two-invocation clean path.
- Use strict parsing for configured minimums and separate tolerant parsing, if needed, for observed tool output.
- Bind legitimacy evidence to the exact resolved package version installed, or explicitly present the metadata check as identity-only rather than artifact approval.

## Risk Assessment

**HIGH.** The plan is much stronger than cycle 1, but three user-impacting issues remain: existing `mmdc` installations are not automatically repaired, supported Linux amd64 machines may receive false-success outcomes, and persistent postinstall trust is not actually bounded by the installer’s `^25` argv pin. The task-order and tracer contradictions also make execution less deterministic than the plan claims.

---

## Source-Grounding Pass — Cycle 2

Independent verification of the cycle-2 reviewer's claims, run against this repository at
revision `07873a1`.

### Reviewer verdicts CONFIRMED

| Claim | Evidence |
|-------|----------|
| HIGH-2 arm64 gate is a real mechanism, not prose | `installer/resolve.py:32-35` — `_applies` already returns False when `method.arch` excludes the platform arch; 05-03 declares `arch = ["amd64"]` on puppeteer's Linux method (`05-03-PLAN.md:308`) and adds `NO_LINUX_ARM64 = {"puppeteer"}` plus an honesty test (`05-03-PLAN.md:384-388`, acceptance at `05-03-PLAN.md:436-439`). `installer/deps.py:92-107` then blocks `mmdc` transitively and emits the skip warning. The gate is genuine. |
| HIGH-2 Linux amd64 residual is real | `05-03-PLAN.md:532-540` records the ~30 shared libraries as documented-not-automated, explicitly declining to guess Fedora/Arch package names. `installer/engine.py:89-94` still reports INSTALLED on pnpm exit 0, so a Linux amd64 machine without those libraries gets a false success. |
| HIGH-3 floors are genuinely mechanized | `05-01-PLAN.md:503-530` adds `parse_version`/`meets_minimum` plus the two pnpm floors and an injectable `probe_version` to `installer/versions.py`; `05-01-PLAN.md:528-576` wires a fail-closed preflight into `_node` BEFORE the `runner(...)` call, with behaviour cases requiring NO runner invocation on an unmet floor and ZERO probes for a params-free node method. |
| HIGH-5 pin is threaded into the real argv | `05-01-PLAN.md:400-404` (`<behavior>`) requires the exact argv `[pnpm, add, -g, --allow-build=puppeteer, @mermaid-js/mermaid-cli,puppeteer@^25]`, and the acceptance criterion at `05-01-PLAN.md:459-461` asserts that list byte-for-byte through `installer/executors.py::execute`. The pin is not prose. |
| HIGH-6 tier counts are correct and non-colliding | `tests/test_registry.py:436-444` pins `{system:22, ai:9, user:35}`. 05-02 moves `ai` to 10 with `user` untouched (`05-02-PLAN.md:121`, `05-02-PLAN.md:159`); 05-03 then asserts `{system:22, ai:10, user:36}` (`05-03-PLAN.md:276`), correctly carrying 05-02's change forward. Wave order 05-02 → 05-03 makes the sequence valid. No other plan adds a registry entry. |
| HIGH-4 trust boundary is still misstated | `05-03-PLAN.md:222` says the persistent grant is "bounded only by the `^25` pin Task 2 declares". The pin constrains only argv this project generates; pnpm's recorded allowance is package-level and applies to any future `puppeteer` installed by any pnpm invocation on that machine. This sentence is instructed to be transcribed into `05-03-SUMMARY.md`, so an inaccurate security claim would be committed as verified evidence. |
| MEDIUM task-order inversion is real | 05-01 Task 2's `<files>` is `installer/model.py, tests/test_model.py` (`05-01-PLAN.md:298`), yet its `<action>` instructs implementing `installer/versions.py::parse_version` first (`05-01-PLAN.md:370-373`) — a file Task 4 owns (`05-01-PLAN.md:493`). Task 2 cannot satisfy its own file scope. |
| MEDIUM tracer/fallback contradiction is real | 05-01's `<automated>` runs the versioned comma group under `set -eu` (`05-01-PLAN.md:278`) and `<fails_when>` fails the task unless BOTH `TRACER_RENDER_OK` and `TRACER_BROWNFIELD_OK` appear. A rejected version specifier therefore aborts the container and fails Task 1 — so 05-03's "if the SUMMARY records the probe FAILING" branch (`05-03-PLAN.md:360-367`) is unreachable under normal execution. |
| MEDIUM `parse_version` tolerance vs `min_node` validation | `05-01-PLAN.md:517-521` takes "up to three leading numeric components and zero-fill", so `min_node = "22.bad"` parses to `(22,0,0)` and passes load-time validation, while `05-01-PLAN.md:321-322` claims malformed `min_node` values are rejected. `"22.bad"` is neither specified nor tested. |

### Reviewer verdicts CONFIRMED as resolved (spot-checked)

- **#11 `_opt_pkg_list`**: `05-01-PLAN.md:415-425` now mandates an `isinstance(raw, list)` check
  raising `ExecutorError` before any per-element work, with an acceptance criterion asserting a
  bare string is rejected by name and nothing is invoked (`05-01-PLAN.md:462`). Genuinely fixed.
- **#12 REQUIREMENTS.md**: `.planning/REQUIREMENTS.md:39` still demands a `chrome-headless-shell`
  entry today; 05-03 Task 2 lists it in `<files>` (`05-03-PLAN.md:244`) and amends it
  (`05-03-PLAN.md:369`), with a `grep -c` acceptance criterion (`05-03-PLAN.md:441-442`). Fixed.
- **#14 PLAN_BASE / #15 working-tree criterion**: `05-04-PLAN.md:377` now greps the full
  repo-relative SUMMARY path and uses a commit-range `git diff --name-only "$PLAN_BASE"..HEAD`;
  the contradictory `git status --porcelain -- installer/wizard_app.py` criterion is gone
  (0 occurrences remain). Both fixed.
- **#18 `gh` citation**: `05-02-PLAN.md:103` now reads "lines 401-420" with an explicit note
  recording the crossed citation. `installer/registry.toml` confirms the `gh` entry there. Fixed.
- **#13 puppeteer `bin`**: `05-03-PLAN.md:293` now states pnpm links an object-form `bin` under
  each KEY. Fixed.

### Findings the reviewer did not raise

- **LOW — the brownfield remedy is invisible to the affected user.** 05-03 Task 3 writes the
  brownfield record and its remedy into a comment block in `installer/registry.toml`
  (`05-03-PLAN.md:493-505`), guarded by a text test (`05-03-PLAN.md:579-588`). A registry comment
  is not a user-facing surface: a brownfield user is never told to run the Doctor replay. If the
  accepted design is "manual remedy", the remedy should at minimum surface in the Doctor report
  or the dependency notice, not only in a TOML comment.
- **LOW — `is_blocked`'s installed short-circuit interacts with the arm64 gate.**
  `installer/deps.py:84-86` returns "not blocked" for any tool `is_installed()` reports true.
  On Linux arm64 with a pre-existing standalone `mmdc`, `mmdc` is therefore not blocked and no
  skip warning is emitted, even though puppeteer is unavailable there. Harmless today (nothing
  is installed), but it means the arm64 honesty guarantee holds only for clean machines. Worth a
  sentence in 05-03's caveat block.

## Consensus Summary — Cycle 2

One reviewer produced a section this cycle (`opencode-plan-review`, the configured default), so
there is no cross-reviewer consensus to compute; the source-grounding pass above stands in as
independent corroboration. The reviewer's section carries no evidence-quality discount marker —
it cites `file:line` evidence throughout, and every citation spot-checked resolved to real code
or real plan text.

**Verdict: 11 of 19 cycle-1 concerns fully resolved, 7 partially resolved, 1 not resolved.**
The revision's mechanisms are real, not cosmetic: the arm64 gate reuses the existing
`method.arch` filter, the version floors are a fail-closed preflight ahead of the runner, the
pin is asserted byte-for-byte in the argv, and the tier counts are correct and sequenced.

### Agreed Strengths

- The Linux arm64 gate reuses `installer/resolve.py::_applies` rather than adding special-case
  control flow, and is pinned by an honesty test that cannot be widened silently.
- One shared source of truth for every version fact (`installer/versions.py`), consumed by both
  the installer preflight and the 05-04 Doctor replay.
- Legacy node methods keep byte-identical argv and perform zero probes — the new mechanism is
  strictly opt-in via declared params.
- All six concrete factual defects cycle 1's source-grounding pass found are corrected.

### Agreed Concerns (still open after the revision)

1. Brownfield repair is manual only — `installer/engine.py:80-83` still short-circuits, and
   automatic split-group detection is explicitly declined.
2. Linux amd64 can still report a successful install of a puppeteer that cannot launch, because
   the shared-library prerequisite is documented rather than provisioned or verified.
3. The persistent `--allow-build` grant is described as bounded by the `^25` pin; it is not.

### Divergent Views

None — a single reviewer ran. The source-grounding pass agrees with every reviewer verdict it
was able to check, and adds two LOW findings the reviewer did not raise.

---

# Cycle 1


> Reviewer-selection note: `.planning/config.json` sets
> `review.default_reviewers: ["opencode-plan-review"]`. That instance's model
> (`router-env/my-plan-review`) was hard-down for the whole of this run — the router at
> `http://llm.local:20128/v1` returned `Model claude/claude-opus-5 is unavailable` on every
> attempt (verified directly against `/v1/chat/completions`, three consecutive tries, plus one
> `opencode run` invocation). The review was therefore run with the project's OTHER configured
> reviewer instance, `opencode-sol` (`review.reviewer_instances.opencode-sol`, model
> `openai/gpt-5.6-sol`), rather than falling back to an unconfigured CLI. One reviewer ran, so
> the convergence loop's two-or-more-reviewer consensus gate does not engage this cycle.

## OpenCode Review (opencode-sol)

I’ll trace the named source paths and current APIs first, then evaluate cross-plan behavior, pnpm semantics, and security assumptions against the repository.
The current code confirms the proposed seams exist, but the review now hinges on two details the plans do not prove: whether pnpm’s grouped syntax and `--allow-build` work across the installer’s unpinned pnpm versions, and whether replay/status/uninstall semantics remain coherent. I’m checking those exact paths and the catalog’s current version constraints.
Two material gaps are now clear: the clean-install tracer does not cover upgrades from the already-shipped standalone `mmdc`, and the proposed method intentionally resolves on Linux arm64 even though its own research says the downloaded browser cannot run there. I’m doing one final consistency pass over pinned registry tests and replay contracts before writing the review.
## Summary

The overall direction is sound, especially the checksum-backed `codegraph` entry and keeping dependency ordering in `requires`. However, the plans are not execution-ready. The clean-install design does not repair existing standalone `mmdc` installations, knowingly advertises unsupported Linux configurations, and assumes pnpm/Node capabilities that the registry does not enforce. Security and replay semantics also need tightening.

## Strengths

- Plan 05-01 correctly modifies the single node execution seam. All node installs flow through `execute()` and `_node()` at `installer/executors.py:83-94` and `installer/executors.py:132-137`, so no parallel install path is missed.
- The dependency design preserves the existing architecture. `resolve_dependencies()` already creates a deps-first order through its DFS at `installer/deps.py:121-138`, while `run_installs()` propagates dependency failures at `installer/session.py:88-106`.
- Plan 05-02 fits the existing download architecture well. Asset templating happens in `installer/download.py:65-87`, checksum lookup in `installer/checksums.py:23-37`, and checksum mismatches halt by default in `installer/engine.py:89-102`.
- The proposed CodeGraph assets match the current `v1.6.0` GitHub release, including both architectures and `SHA256SUMS`.
- Plan 05-04 correctly recognizes that preview and execution must share `reinstall_argv()`. The current production closures are separate at `setup.py:260-270`, while both ultimately use the builder at `installer/pnpm_globals.py:191-249`.
- The sequential wave structure is justified because every plan runs repository-wide quality gates against a shared tree.

## Concerns

- **HIGH: Existing `mmdc` installations will not be migrated into the new group.** The shipped registry already installs `mmdc` standalone at `installer/registry.toml:1692-1704`. Both dependency resolution and installation treat a PATH-visible command as satisfied: `resolve_dependencies()` excludes installed tools at `installer/deps.py:109-113`, and `install_tool()` immediately returns `ALREADY_INSTALLED` at `installer/engine.py:80-81`. Therefore an existing standalone `mmdc` can cause only `puppeteer` to be installed independently, leaving the required grouped `mmdc,puppeteer` invocation unexecuted. The clean-container tracer does not cover this brownfield path.

- **HIGH: The plans knowingly expose methods on platforms where they cannot produce a working tool.** An unscoped node method applies to every OS and architecture at `installer/resolve.py:32-39`. Plan 05-03 nevertheless requires Puppeteer to resolve on Linux arm64 despite documenting that Puppeteer's browser is unavailable there. Linux x64 also needs shared libraries that the registry will not install. The tracer hides this gap by manually installing Debian `chromium`; that is not the sequence the catalog will perform. Because `install_tool()` treats a successful pnpm exit as installation success at `installer/engine.py:89-94`, users can receive a successful outcome for a tool that cannot render.

- **HIGH: Required pnpm and Node versions are not modeled or checked.** Comma-separated global install groups are a pnpm v11 feature, while `--allow-build` requires pnpm 10.4 or newer. The current executor checks only whether pnpm exists at `installer/executors.py:88-94`. The pnpm registry entry is unpinned and has no Node dependency at `installer/registry.toml:1447-1470`. Meanwhile Puppeteer 25 requires Node `>=22.12.0`, but the tracer uses `node:24`, masking the bare-machine case. A standalone pnpm executable does not prove a compatible `node` is available for installed Node CLIs.

- **HIGH: `allow_build` is described as invocation-scoped, but pnpm persists the trust decision.** The proposed validation around the current node branch at `installer/model.py:153-166` limits the package name, but official pnpm behavior also writes that package into its global build-allowance configuration. This means future Puppeteer versions can run their postinstall automatically, not merely the current invocation. Combined with unversioned `npm_pkg` values and `install_tool()` accepting exit zero at `installer/engine.py:89-94`, the threat model materially understates the lasting trust granted.

- **MEDIUM: The normal clean-install sequence installs Puppeteer twice and does not inspect the resulting global-group state.** The resolver emits every runnable tool independently at `installer/deps.py:113-138`, and `run_installs()` invokes each one at `installer/session.py:90-106`. Consequently Puppeteer is first installed standalone, then included again in the `mmdc,puppeteer` group. The tracer proves rendering but does not inspect whether pnpm retained both groups, which group owns the `puppeteer` shim, or what removing/updating either package does.

- **MEDIUM: Replay reconstructs only registry-known groups and discards versions.** `parse_global_packages()` currently flattens pnpm JSON to bare package names at `installer/pnpm_globals.py:110-132`. Plan 05-04 therefore cannot preserve versions or hand-created groups for packages absent from the registry. Such packages are replayed as separate, latest-version installs through the builder currently at `installer/pnpm_globals.py:191-204`, potentially breaking other peer-dependent global groups while repairing `mmdc`.

- **MEDIUM: Uninstall behavior for grouped packages is unresolved.** The uninstall planner only recognizes app and download artifacts at `installer/uninstall.py:55-96`; node tools are classified as externally managed and non-selectable at `installer/uninstall.py:200-203`. pnpm documents that removing either member of a comma-group removes the whole group. The plans neither surface this coupling nor test manual removal and subsequent audit/recovery behavior.

- **MEDIUM: Plans 05-02 and 05-03 omit a mandatory pinned-count update.** `test_registry_tier_distribution_is_pinned()` explicitly requires every entry-adding phase to update counts in the same commit at `tests/test_registry.py:436-444`. Adding CodeGraph changes AI from 9 to 10, and adding Puppeteer changes user from 35 to 36. Neither task includes these updates, so the required `tests/test_registry.py` and full-suite gates will fail.

- **MEDIUM: The package-legitimacy check is weaker than its description.** It accepts `want in repository.url`, rather than normalizing and exactly matching the expected GitHub owner/repository. More importantly, repository URL, age, and version count do not authenticate the current tarball. Since node execution currently delegates directly to pnpm at `installer/executors.py:83-94`, the plan should record the exact version and npm integrity/provenance associated with the postinstall it approves.

- **LOW: The proposed `_opt_pkg_list()` is not actually safe for directly constructed malformed methods.** `Method.params` accepts arbitrary objects at `installer/model.py:67-71`, and `execute()` accepts a directly constructed `Method` at `installer/executors.py:132-137`. Casting and filtering without first checking `isinstance(raw, list)` makes a bare string iterable as individual package-name characters. This contradicts the plan’s claim that the helper also handles directly constructed methods correctly.

## Suggestions

- Add an explicit migration test and mechanism for an already-installed standalone `mmdc`. Detect actual pnpm group membership rather than relying only on `shutil.which()`, then force one grouped reinstall when reconciliation is needed.
- Require pnpm v11 or newer before using `co_install`, and verify a compatible Node runtime before installing or reporting Puppeteer/mmdc as usable.
- Do not expose Puppeteer on Linux arm64 until a working distro-browser method is implemented. For Linux x64, either automate verified runtime prerequisites or report the method unavailable rather than successful-but-broken.
- Extend the tracer to inspect `pnpm list -g --json`, global group directories, shim ownership, reinstall idempotency, and removal behavior after both invocations.
- Document `--allow-build` as persistent package-level trust. Pin or constrain Puppeteer/mmdc versions and bind the legitimacy evidence to those exact versions and integrity values.
- Preserve actual pnpm group and version information during audit/replay where available. At minimum, explicitly warn that unknown groups cannot be faithfully reconstructed.
- Add the tier-count updates to 05-02 and 05-03.
- Make `_opt_pkg_list()` reject malformed direct values with `ExecutorError` instead of filtering them.
- Normalize repository URLs and require an exact owner/repository match in the legitimacy gate.

## Risk Assessment

**HIGH.** The design is strong for a fresh, supported pnpm v11+/Node 24 environment, but the project is brownfield and cross-platform. Existing installations, Linux runtime constraints, unsupported Linux arm64 behavior, and unmodeled runtime versions can all leave `mmdc` visibly installed but unusable. The persistent postinstall authorization and lossy replay behavior also need explicit security and lifecycle decisions before implementation.

---

## Source-Grounding Pass

Independent verification of the reviewer's citations and of the plans' own factual claims,
run against this repository and against live upstream sources on 2026-09-05.

### Reviewer claims CONFIRMED against source

| Claim | Evidence |
|-------|----------|
| Existing `mmdc` short-circuits the new group | `installer/engine.py:80-81` returns `ALREADY_INSTALLED` before `resolve_methods`; `installer/deps.py:109-113` excludes installed tools from the order |
| An unscoped node method resolves on every OS/arch | `installer/resolve.py:32-39` — `_applies` returns `True` for `kind="node"` with no `os`/`arch` gate |
| `--allow-build` grants PERSISTENT trust, not per-invocation | pnpm docs, `pnpm.io/cli/add`, verbatim: "This will run `esbuild`'s postinstall script and **also add it to the `allowBuilds` field of `pnpm-workspace.yaml`. So, `esbuild` will always be allowed to run its scripts in the future.**" Added in v10.4.0 |
| Comma groups are a pnpm **v11** redesign | pnpm docs, `pnpm.io/global-packages`: "In pnpm v11, global package management was redesigned…"; the comma form and its peer-resolution semantics are documented there verbatim, exactly as 05-RESEARCH.md cites |
| pnpm registry entry is unpinned and declares no node dependency | `installer/registry.toml:1447-1470` — three methods, no version, no `requires` |
| The executor only checks that pnpm EXISTS | `installer/executors.py:88-93` |
| Tier-count tripwire not updated by 05-02/05-03 | `tests/test_registry.py:436-444` pins `{system: 22, ai: 9, user: 35}`. 05-02 adds an `ai` entry (→10), 05-03 adds a `user` entry (→36). Neither plan's `<action>` or `<acceptance_criteria>` updates the counts, yet both assert `uv run pytest tests/test_registry.py -x -q` exits 0 |
| Node tools are not uninstallable here; group removal is coupled | `installer/uninstall.py:200-203` classifies them `MANAGED`; `pnpm.io/global-packages`: "Removing either with `pnpm remove -g` removes the whole group" |
| `_opt_pkg_list` filtering is unsafe for a bare string | `installer/model.py:67-71` — `Method.params: dict[str, object]`; a bare `"abc"` iterates to `'a','b','c'`, all `str`, so a filter-without-`isinstance(raw, list)` yields three package names |
| Replay flattens to bare names, losing versions/groups | `installer/pnpm_globals.py:110-132` (`parse_global_packages`) |

### Plan claims CONFIRMED

- `codegraph` `v1.6.0` publishes `codegraph-{darwin,linux}-{arm64,x64}.tar.gz` **and** `SHA256SUMS` — verified live via `api.github.com/repos/colbymchenry/codegraph/releases/latest`. `codegraph` occurs 0 times in `installer/registry.toml` today, as 05-02 states.
- `{arch.x64}` → `x64`/`arm64` (`installer/assets.py:16-23`); `checksum = "SHA256SUMS"` contains no `{asset}` so it renders verbatim (`installer/download.py:78-81`); `expected_sha256` parses the two-space `<hash>  <name>` form (`installer/checksums.py:31-34`); `_place_verified` untars with `--strip-components` into `opt_dir(link.name)` (`installer/download.py:190-207`). Every symbol 05-02's `key_links` names is real.
- 05-03 Task 1's legitimacy-gate shell command was executed verbatim: it prints both lines and `LEGITIMACY_OK`, exits 0, and is genuinely failable (`set -eu` + per-iteration `|| exit 1`, python `sys.exit(1)` as pipeline tail). Observed: puppeteer repo `git+https://github.com/puppeteer/puppeteer.git#main`, created 2013-03-23, 1010 versions, latest 25.10.0; `@mermaid-js/mermaid-cli` repo `git+ssh://git@github.com/mermaid-js/mermaid-cli.git`, created 2020-03-01, 82 versions, latest 11.17.0.
- `puppeteer@25.10.0` declares `postinstall: "node install.mjs"` and `engines.node >= 22.12.0`; `@mermaid-js/mermaid-cli@11.17.0` declares NO install/postinstall script and `peerDependencies: {puppeteer: "^23 || ^24 || ^25"}`. All three plan claims hold.
- Every grep baseline the plans assert is exact: `SHA256SUMS`=2, `arm64`=3, `Linux arm64`=0, `PUPPETEER_EXECUTABLE_PATH`=0, `install.mjs`=0, `1122`=0, `peerDependency`=0, `codegraph`=0, `mmdc` rows in `PROJECT.md`=0.
- `--allow-build` is a real `pnpm add` flag on the installed pnpm (11.9.0).
- No hallucinated Python symbols found. `_perform`, `execute`, `_node`, `real_pnpm`, `load_tools`, `resolve_methods`, `resolve_dependencies`, `requires_integrity_errors`, `missing_requires`, `is_installed`, `render_dependency_notice`, `unstaged_recommends`, `reinstall_argv`, `reinstall_preview`, `reinstall_node_globals`, `node_globals`, `_place_verified`, `arch_tokens`, `expected_sha256`, `_parse_id_list`, `_plant_executable`, `MACOS_ONLY`, `test_volta_entry_records_the_npm_postinstall_finding`, `test_gh_uses_nested_member_on_linux_and_brew_only_on_macos`, `test_shipped_node_tools_require_pnpm`, `test_registry_includes_requested_installable_entries` — all exist with the shapes the plans assume. `Platform(os=, arch=, immutable=, has_brew=)` and `resolve_dependencies(..., available=, is_installed=)` match the acceptance-criteria call sites exactly.

### Additional findings from this pass

- **HIGH — `npm_pkg = "puppeteer"` is unpinned, and mmdc's peer range is already at its ceiling.**
  `mmdc` requires `puppeteer ^23 || ^24 || ^25`; npm's current `latest` is **25.10.0**. `_node`
  builds `pnpm add -g '@mermaid-js/mermaid-cli,puppeteer'` with no version, so the day puppeteer
  26 ships, the co-install group — the phase's entire mechanism — resolves an out-of-range peer.
  pnpm's default `strict-peer-dependencies=false` makes that a warning, so the failure is silent
  and lands at runtime. Nothing in the four plans pins, ranges, or tests this, and the Tier-3
  tracer proves only today's resolution. Compounded by the confirmed persistence of
  `--allow-build`: it is the *unpinned future version's* postinstall that is pre-authorised.
- **MEDIUM — `REQUIREMENTS.md` was never amended to match the `chrome-headless-shell` decision.**
  `REQ-puppeteer-catalog-entries` still reads "`puppeteer` **and** `chrome-headless-shell` become
  their own catalog entries". ROADMAP SC#3 was formally amended for this; `REQUIREMENTS.md` was
  not, and 05-03 does not list it in `files_modified` — yet 05-03 Task 2 adds a test asserting no
  such entry can exist. A verifier reading the requirement text will register the REQ as unmet.
- **MEDIUM — 05-03's stated evidence for `cmd = "puppeteer"` is factually wrong.** The plan says
  the package "declares `\"bin\": \"./lib/puppeteer/node/cli.js\"` as a bare string … and a string
  `bin` is linked under the package's own name". Live registry metadata shows
  `bin: {"puppeteer": "lib/puppeteer/node/cli.js"}` — an **object**, not a string. The conclusion
  (`cmd = "puppeteer"` is correct) survives, because the object key is literally `puppeteer`, but
  the plan instructs this rationale to be transcribed verbatim into `05-03-SUMMARY.md`, so a false
  claim would be committed as verified evidence.
- **MEDIUM — 05-04 Task 2's `PLAN_BASE` criterion reads a path that does not exist.** It runs
  `grep -oE '[0-9a-f]{40}' 05-04-SUMMARY.md`, but the summary is written to
  `.planning/phases/05-registry-method-corrections-codegraph-mmdc-puppeteer/05-04-SUMMARY.md`.
  From the repo root the grep finds no file, `PLAN_BASE` is empty, and the deliberate
  `test -n "$PLAN_BASE"` guard fails the criterion for the wrong reason.
- **MEDIUM — 05-04 Task 2 re-introduces the working-tree check it just argued against.**
  The plan explains at length why an unscoped `git diff` on the working tree is unreliable
  against pre-existing dirt, then adds `git status --porcelain -- installer/wizard_app.py`
  "produces no output". That file is modified in the working tree on the current branch, so the
  criterion is failable on dirt this plan did not create.
- **MEDIUM — 05-04's `reinstall_node_globals` return contract becomes false.** The function
  returns `tuple(argv[3:])` (`installer/pnpm_globals.py:227`). Once `--allow-build=<pkg>` elements
  are prepended, that slice returns flags as if they were package specs, contradicting the plan's
  own `<behavior>` line "returns the package specs it actually invoked". No task changes the slice.
  (Impact is contained: `setup.py:267-270`'s value is discarded by
  `wizard_app.py:_reinstall_globals_worker`.)
- **MEDIUM — `node_install_policy`'s `allow_build` de-duplication is unspecified.** Both the
  `puppeteer` entry and the `mmdc` entry will declare `allow_build = ["puppeteer"]`, so a literal
  concatenation yields `('puppeteer', 'puppeteer')` and two identical flags in the replay argv,
  while 05-04's own acceptance criterion demands `p.allow_build == ('puppeteer',)`. The
  `<action>` text specifies `dict.fromkeys` de-duplication only for group members.
- **LOW — 05-02 cites the wrong file for the `gh` precedent.** `read_first` names
  "`installer/registry.toml` lines 288-300 (the `gh` entry … `member = "bin/gh"`)". The `gh` entry
  is at `installer/registry.toml:400-417` (`member = "bin/gh"` at 416); lines 288-300 are the
  `delta`/`eza` region. 288 is the line number of `test_gh_uses_nested_member_on_linux_and_brew_only_on_macos`
  in `tests/test_registry.py` — the two citations were crossed.
- **LOW — scope-boundary tension with `05-CONTEXT.md`.** The context's `<specifics>` states Phase 5
  is "strictly a method correction … no new tools, no new mechanisms." These plans add a new
  executor param pair (`co_install`/`allow_build`), a new load-time validator, and a new
  `NodeInstallPolicy` layer in `pnpm_globals`. The work is necessary for SC#3 and is well argued,
  but it is a mechanism, and the deviation is not recorded the way ROADMAP SC#3's amendment was.
  The same applies to D-03's literal "platform-conditional methods (macOS vs Linux/Bazzite)",
  which 05-03 deliberately resolves as a single unscoped method.

## Consensus Summary

One reviewer produced a section this cycle (`opencode-sol`), so there is no cross-reviewer
consensus to compute; the source-grounding pass above stands in as independent corroboration.
The reviewer's section carries no evidence-quality discount marker — it cites `file:line`
evidence throughout, and every citation checked resolved to real code.

### Agreed Strengths

- The single node execution seam (`installer/executors.py::_node`) is the right and only place
  to change the argv; no parallel install path is missed.
- `installer/deps.py` stays untouched — install order remains `requires`-only, and `co_install`
  is explicitly documented as not an ordering mechanism.
- 05-02's `codegraph` entry is checksum-verified, live-verified against `v1.6.0`, and fits the
  existing `github_release` download path exactly.
- The wave sequencing (1→2→3→4) is correctly justified by the shared-tree repo-wide quality gate,
  not by file overlap.
- 05-03 Task 1's legitimacy gate really is failable, and really does bind the expected repository
  per package — the two defects the previous internal round fixed are genuinely fixed.

### Agreed Concerns

Corroborated by the reviewer AND the source-grounding pass:

1. `--allow-build` is persistent package-level trust, not invocation-scoped — contradicting the
   threat registers in 05-01 (T-05-01), 05-03 (T-05-09) and 05-04 (T-05-14).
2. Required pnpm (v11 for comma groups, ≥10.4 for `--allow-build`) and Node (≥22.12.0 for
   puppeteer) versions are neither pinned nor checked anywhere in the catalog or the executor.
3. A brownfield machine with `mmdc` already installed never reaches the grouped invocation.
4. The `test_registry_tier_distribution_is_pinned` tripwire will fail both 05-02 and 05-03.
5. Version pinning / provenance is the real gap in the package-legitimacy story, not repository
   identity — and it is the one install path in this phase with no integrity verification, in
   contrast to `codegraph`'s checksummed download.

### Divergent Views

None — a single reviewer ran. The source-grounding pass agrees with every reviewer finding it
was able to check, and adds seven findings the reviewer did not raise (listed above).
