---
phase: 7
reviewers: [codex]
reviewed_at: 2026-09-06T07:35:19Z
plans_reviewed: [07-01-PLAN.md, 07-02-PLAN.md, 07-03-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
model_sources:
  codex: "banner"
---

# Cross-AI Plan Review — Phase 7

> **Note:** This is a second review cycle for Phase 7, run against the PLAN.md revisions made
> after the prior cycle's codex review (committed as `1587c34`). The codex reviewer lane was
> forced explicitly per user request — it proved reliable for this phase in cycle 1, while the
> default `opencode-plan-review` lane had twice failed with ETIMEDOUT on this phase's large
> 3-plan prompt bundle. Only one reviewer produced a review this cycle; the multi-reviewer
> consensus gate does not apply — every HIGH below counts individually.
>
> The prior cycle's `git`-dependency HIGH on Plan 07-01 appears resolved: this cycle's review
> confirms "Adding `git` as a hard dependency is correct" as a strength rather than re-raising it
> as a concern. New and different HIGH-severity concerns emerged against the revised plans below.

## Codex Review

# Cross-AI Plan Review

## Overall assessment

The plans show strong source awareness and test discipline, but they should not execute unchanged. Two architectural gaps block the phase goal:

1. "No applicable method" currently conflates unsupported hardware/OS with a missing package manager.
2. The accepted macOS-version limitation directly contradicts locked decision D-01.

The terminal-emulator plan is mechanically sound, but its phase-closeout claim inherits those unresolved blockers.

---

## Plan 07-01 — Zsh and Oh-My-Zsh

### Summary

The dependency and safety design is well grounded. Adding `git` as a hard dependency is correct, and the proposed tests exercise the real resolver. However, the plan proves the Bazzite path only when Homebrew is already installed, not from the fresh-machine state central to the project.

### Strengths

- The resolver test is meaningful. `resolve_dependencies` recursively collects every `requires` edge and then visits runnable dependencies before dependents, so asserting both `zsh` and `git` precede `oh-my-zsh` tests the production mechanism rather than TOML shape alone. [installer/deps.py:59](/Users/ramon/git/personal/tools-installer/installer/deps.py:59), [installer/deps.py:121](/Users/ramon/git/personal/tools-installer/installer/deps.py:121)

- The environment-variable mitigation reaches the correct process. `_env_prefix` quotes values, and `_script` attaches those assignments to the shell on the right side of the pipe. [installer/executors.py:334](/Users/ramon/git/personal/tools-installer/installer/executors.py:334), [installer/executors.py:353](/Users/ramon/git/personal/tools-installer/installer/executors.py:353)

- `detect_path` is the correct idempotency seam for a framework without a normal PATH executable. `is_installed` checks it after `which`, and `install_tool` returns `ALREADY_INSTALLED` before rerunning the vendor script. [installer/status.py:16](/Users/ramon/git/personal/tools-installer/installer/status.py:16), [installer/engine.py:80](/Users/ramon/git/personal/tools-installer/installer/engine.py:80)

- The immutable-Linux assertions accurately reflect current resolution behavior: native managers are rejected on immutable platforms, while brew remains applicable when `has_brew=True`. [installer/resolve.py:40](/Users/ramon/git/personal/tools-installer/installer/resolve.py:40), [installer/resolve.py:49](/Users/ramon/git/personal/tools-installer/installer/resolve.py:49)

### Concerns

- **HIGH — The test does not prove fresh-machine Bazzite parity.** Every proposed Bazzite fixture sets `has_brew=True`. On an immutable machine without Homebrew, native methods are rejected and the brew method is also rejected, leaving `zsh` with no method. `resolve_dependencies` then blocks `oh-my-zsh` through its unavailable dependency. `Platform.has_brew` is a live startup probe, not a capability that becomes true because `brew` was selected. [installer/platform.py:53](/Users/ramon/git/personal/tools-installer/installer/platform.py:53), [installer/resolve.py:40](/Users/ramon/git/personal/tools-installer/installer/resolve.py:40), [installer/deps.py:92](/Users/ramon/git/personal/tools-installer/installer/deps.py:92)

- **MEDIUM — The Tier-3 run tests preservation, not a clean-home installation.** It creates a pre-existing `.zshrc` and verifies that it remains unchanged. That does not prove a fresh user receives a usable Oh-My-Zsh configuration. The existing plugin policy refuses a missing or unsupported `plugins=(...)` array, so merely finding `~/.oh-my-zsh/oh-my-zsh.sh` is insufficient evidence that the framework is activated or compatible with the shipped policy. [installer/omz.py:54](/Users/ramon/git/personal/tools-installer/installer/omz.py:54), [installer/omz.py:132](/Users/ramon/git/personal/tools-installer/installer/omz.py:132)

- **LOW — The claimed "verbatim" pipeline is not verbatim.** Production prepends a de-shimmed PATH export before `curl`; the proposed container command omits it. The placement of `< /dev/null` is also ambiguous—placing it on the right-hand shell would override the pipe that supplies the script. [installer/executors.py:30](/Users/ramon/git/personal/tools-installer/installer/executors.py:30), [installer/executors.py:359](/Users/ramon/git/personal/tools-installer/installer/executors.py:359), [07-01-PLAN.md:243](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-01-PLAN.md:243)

- **LOW — The registry comments are excessively large.** The architecture convention requires a dated comment containing the verified finding, while detailed evidence belongs naturally in the research and summary artifacts. It does not require embedding the full investigation in TOML. [architecture.md:163](/Users/ramon/git/personal/tools-installer/.claude/architecture.md:163), [architecture.md:185](/Users/ramon/git/personal/tools-installer/.claude/architecture.md:185)

### Suggestions

- Add a `has_brew=False` immutable-Fedora test and explicitly resolve how Homebrew becomes available on a fresh Bazzite installation.
- Add a second Tier-3 case with no pre-existing `.zshrc`; assert that the resulting configuration sources Oh-My-Zsh and contains an editable plugin array.
- Generate or capture the actual `_script` runner argument for the container reproduction instead of manually retyping it.
- Keep registry comments concise and place the transcript and extended rationale in `07-01-SUMMARY.md`.

### Risk assessment

**HIGH.** The Oh-My-Zsh safety work is strong, but the plan does not yet demonstrate the required fresh-machine Bazzite path.

---

## Plan 07-02 — GNU Bash, Apple Containers, and disabled catalog rows

### Summary

The GNU Bash detection fix is well reasoned, and reusing `BrowserAdapter.selectable` is the right UI primitive. The availability model is not correct, however: it disables brew-only tools when Homebrew is merely absent, and it still cannot disable Apple Containers on an unsupported macOS version despite D-01 explicitly requiring that behavior.

### Strengths

- The GNU Bash false-positive diagnosis is correct. `is_installed` checks `shutil.which(tool.cmd)` before `detect_path`, and `install_tool` stops immediately if that returns true. Using `cmd="bash"` would therefore let the system binary prevent the brew action. [installer/status.py:24](/Users/ramon/git/personal/tools-installer/installer/status.py:24), [installer/engine.py:80](/Users/ramon/git/personal/tools-installer/installer/engine.py:80)

- The two arch-specific methods match the existing model: installation resolution filters methods by `arch`, while status detection examines every declared `detect_path`. [installer/resolve.py:32](/Users/ramon/git/personal/tools-installer/installer/resolve.py:32), [installer/status.py:26](/Users/ramon/git/personal/tools-installer/installer/status.py:26)

- `BrowserAdapter.selectable` is an appropriate reuse point. Toggle, select-all, and invert already honor it without changes to `ToolBrowser`. [installer/tool_browser.py:60](/Users/ramon/git/personal/tools-installer/installer/tool_browser.py:60), [installer/tool_browser.py:240](/Users/ramon/git/personal/tools-installer/installer/tool_browser.py:240), [installer/tool_browser.py:251](/Users/ramon/git/personal/tools-installer/installer/tool_browser.py:251)

- The proposed dimmed rendering follows a real existing pattern in `UninstallScreen`, including the blank selection cell and inert adapter entry. [installer/wizard_app.py:581](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:581), [installer/wizard_app.py:673](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:673)

### Concerns

- **HIGH — D-01 remains unsatisfied.** D-01 explicitly includes a wrong macOS version as an unavailable case. `Platform` has no version field, and `_applies` checks only OS, architecture, immutability, and current brew presence. The plan acknowledges that a pre-macOS-26 Apple-Silicon machine remains selectable, then declares the gap accepted without a user decision. [07-CONTEXT.md:21](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-CONTEXT.md:21), [installer/platform.py:19](/Users/ramon/git/personal/tools-installer/installer/platform.py:19), [installer/resolve.py:32](/Users/ramon/git/personal/tools-installer/installer/resolve.py:32)

- **HIGH — `not resolve_methods(...)` conflates unsupported platforms with missing Homebrew.** On a fresh Mac where `has_brew=False`, both `gnu-bash` and Apple Containers would be dimmed and non-selectable. Selecting the catalog's Homebrew tool cannot change the static `Platform` snapshot or availability map. This conflicts directly with the installer's bare-machine bootstrap purpose. [installer/platform.py:53](/Users/ramon/git/personal/tools-installer/installer/platform.py:53), [installer/resolve.py:40](/Users/ramon/git/personal/tools-installer/installer/resolve.py:40), [07-02-PLAN.md:460](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-02-PLAN.md:460)

- **MEDIUM — The proposed computation violates the "setup.py is wiring only" rule.** The plan imports `resolve_methods` into `setup.py` and makes a per-tool availability decision there. The architecture standard says decision functions belong under `installer/`. [architecture.md:20](/Users/ramon/git/personal/tools-installer/.claude/architecture.md:20), [setup.py:141](/Users/ramon/git/personal/tools-installer/setup.py:141)

- **MEDIUM — The new non-selectable invariant has a staging bypass.** Recommendations are filtered only by known/staged/installed state, then `action_accept_recommends` writes IDs directly into the shared staged set. `selected_ids` also returns staged IDs without checking `selectable`. An unavailable recommendation can therefore be silently staged despite its disabled row. Phase 8's planned recommendation wiring makes this a near-term issue. [installer/selection.py:88](/Users/ramon/git/personal/tools-installer/installer/selection.py:88), [installer/catalog_tui.py:323](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:323), [installer/tool_browser.py:276](/Users/ramon/git/personal/tools-installer/installer/tool_browser.py:276)

- **LOW — The claimed reuse of `classify_tools` is not exact.** `classify_tools` checks removable and installed states before classifying a tool as unavailable; the proposed map uses only `not resolve_methods`. [installer/uninstall.py:188](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:188)

### Suggestions

- Separate "unsupported on this OS/architecture/version" from "installer prerequisite currently missing." Disabled rows should use the former.
- Add a reusable `installer/` availability classifier and keep `setup.py` limited to calling and forwarding it.
- Either implement the macOS-version gate or return D-01 to the user for an explicit scope change. Do not close the phase while contradicting the locked decision.
- Filter recommendation acceptance and final selected IDs through the same selectability predicate.
- Add a bare-Mac test with `has_brew=False`; Apple Containers and GNU Bash should remain selectable if the installer can bootstrap Homebrew.

### Risk assessment

**HIGH.** The UI mechanism is good, but the availability definition would disable installable tools on the primary bootstrap path and still miss one explicitly required unavailable state.

---

## Plan 07-03 — Kitty, WezTerm, and terminal category

### Summary

The registry shapes and checksum path fit the current implementation. The main implementation risk is that the novel WezTerm AppImage path is validated structurally but never installed and executed. The plan also closes the phase despite Plan 07-02's unresolved D-01 conflict.

### Strengths

- The new category integrates through existing validation. `load_tools` validates each tool category against the `Category` enum, and existing tests enforce both "every used category has a blurb" and "every blurb is used." [installer/model.py:172](/Users/ramon/git/personal/tools-installer/installer/model.py:172), [tests/test_registry.py:942](/Users/ramon/git/personal/tools-installer/tests/test_registry.py:942)

- The WezTerm checksum template fits the implementation. `{asset}` expands after the release asset name is rendered, and the checksum parser accepts `<hash> <filename>` sidecars. [installer/download.py:51](/Users/ramon/git/personal/tools-installer/installer/download.py:51), [installer/checksums.py:23](/Users/ramon/git/personal/tools-installer/installer/checksums.py:23)

- `raw=true` correctly bypasses archive extraction in both unverified and verified flows, avoiding the gzip-only `tar -xzf` path. [installer/download.py:118](/Users/ramon/git/personal/tools-installer/installer/download.py:118), [installer/download.py:190](/Users/ramon/git/personal/tools-installer/installer/download.py:190)

- The accepted Kitty/Bazzite result matches current resolution: native methods are skipped on immutable Linux and casks are restricted to macOS. [installer/resolve.py:42](/Users/ramon/git/personal/tools-installer/installer/resolve.py:42), [installer/resolve.py:49](/Users/ramon/git/personal/tools-installer/installer/resolve.py:49)

### Concerns

- **HIGH — The phase-closeout claim is premature.** Plan 07-03 declares Phase 7 complete while 07-02 explicitly leaves the wrong-macOS-version case selectable, contrary to D-01. The source model confirms that limitation. [07-CONTEXT.md:21](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-CONTEXT.md:21), [installer/platform.py:19](/Users/ramon/git/personal/tools-installer/installer/platform.py:19)

- **MEDIUM — The AppImage path is not tested as an installable, runnable tool.** Proposed tests assert method selection and TOML parameters, but the real path resolves a live tag, downloads two files, parses the checksum, copies the AppImage, and executes it later through PATH. AppImage runtime dependencies such as FUSE are not exercised. [installer/versions.py:169](/Users/ramon/git/personal/tools-installer/installer/versions.py:169), [installer/download.py:153](/Users/ramon/git/personal/tools-installer/installer/download.py:153), [installer/download.py:190](/Users/ramon/git/personal/tools-installer/installer/download.py:190)

- **MEDIUM — Linux arm64 has no WezTerm path.** The project recognizes `arm64` as a supported architecture, but the plan deliberately asserts that Fedora arm64 resolves to no method. The requirement says "a verified Linux path" without narrowing it to amd64, so this needs an explicit scope decision or an additional method. [installer/platform.py:9](/Users/ramon/git/personal/tools-installer/installer/platform.py:9), [07-03-PLAN.md:279](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-03-PLAN.md:279), [REQUIREMENTS.md:51](/Users/ramon/git/personal/tools-installer/.planning/REQUIREMENTS.md:51)

- **LOW — The required Kitty comment contradicts itself.** It correctly says Kitty has upstream Linux cask variations and that this project rejects all Linux casks, but later says there is "no brew/cask fallback for Linux" confirmed by a formula `404`. The actual reason is resolver policy, not absence of a Linux cask. [07-03-PLAN.md:192](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-03-PLAN.md:192), [07-03-PLAN.md:214](/Users/ramon/git/personal/tools-installer/.planning/phases/07-system-user-tier-catalog-expansion/07-03-PLAN.md:214), [installer/resolve.py:42](/Users/ramon/git/personal/tools-installer/installer/resolve.py:42)

- **LOW — The six long `PROJECT.md` table rows duplicate research, architecture, plans, and summaries.** This will make the decision ledger difficult to scan and maintain.

### Suggestions

- Add a Tier-3 WezTerm check that downloads through the intended checksum path and runs `wezterm --version` on at least Debian/Ubuntu and Fedora/Bazzite-equivalent environments.
- Clarify whether Linux arm64 is required. If deferred, record it alongside the Kitty/Bazzite limitation.
- Rewrite the Kitty comment as: "No resolver-applicable Linux fallback: the formula is absent, and project policy excludes casks on Linux."
- Delay Phase 7 closeout until D-01 and the Homebrew-absence classification are resolved.
- Condense the `PROJECT.md` decisions to short statements with links to the detailed summaries.

### Risk assessment

**HIGH for phase closeout; MEDIUM for the terminal entries themselves.** The registry mechanics are plausible, but runnable AppImage verification is missing and the plan inherits unresolved Phase 7 blockers.

---

## Consensus Summary

Only one reviewer (Codex) produced a review this cycle. With a single reviewer, there is no
cross-reviewer agreement/divergence to synthesize; Codex's findings are source-grounded with
concrete `file:line` citations against the actual repository (registry, resolver, status,
executors, download, catalog TUI, uninstall, selection, and test files), so they are treated as
fully weighted individual findings rather than downgraded.

Cross-cutting theme this cycle: two of the four HIGH findings (D-01 macOS-version gating and the
`resolve_methods`/Homebrew-absence conflation) both trace back to the same root cause — `Platform`
and `resolve_methods` currently express only "does a method exist for this OS/arch/immutability,"
not "is this tool unsupported on this hardware" versus "is a prerequisite (Homebrew) merely
missing right now." Plan 07-02's disabled-row mechanism inherits this ambiguity, and Plan 07-03's
premature phase-closeout HIGH is a direct consequence of 07-02 not yet resolving it.

### Agreed Strengths

Not applicable — only one reviewer ran this cycle.

### Agreed Concerns

Not applicable — only one reviewer ran this cycle. See "Codex Review" above for the full set of
HIGH/MEDIUM/LOW findings, each independently source-cited.

### Divergent Views

Not applicable — only one reviewer ran this cycle.
