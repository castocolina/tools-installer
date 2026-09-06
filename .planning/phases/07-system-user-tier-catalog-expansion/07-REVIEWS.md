---
phase: 7
reviewers: [codex]
reviewed_at: 2026-09-06T06:55:10Z
plans_reviewed: [07-01-PLAN.md, 07-02-PLAN.md, 07-03-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
model_sources:
  codex: "banner"
---

# Cross-AI Plan Review — Phase 7

> **Note:** opencode-plan-review was attempted for this phase and failed with ETIMEDOUT on the
> large 3-plan prompt bundle (a tool/network failure, not a completed review with a clean
> verdict). This cycle forced the codex reviewer lane instead, per explicit user request.
> Only one reviewer produced a review this cycle; the multi-reviewer consensus gate does not
> apply — every HIGH below counts individually.

## Codex Review

# Cross-AI Plan Review — Phase 7

## Overall verdict

**Overall risk: HIGH. Do not execute these plans unchanged.** The plans understand most existing mechanisms well, but three blockers remain:

1. Plan 01 masks Oh-My-Zsh's undeclared `git` prerequisite.
2. Plan 02 does not implement D-01's disabled catalog state and misidentifies the production outcome as `NO_METHOD`.
3. Plan 03 contains a verification command that cannot pass and does not pin its load-bearing `raw`/checksum fields.

The current baseline is healthy: the targeted registry, resolver, status, and download tests completed with exit code 0.

---

## Plan 07-01 — zsh and Oh-My-Zsh

### Summary

The registry shapes, environment-variable protection, `detect_path`, and immutable-Linux method resolution are grounded in the implementation. The main gap is the install's undeclared dependency on `git`: the proposed container setup installs `git` manually, so it cannot prove that a real catalog-driven installation succeeds on a clean machine.

### Strengths

- The data-only dependency approach is correct. `resolve_dependencies` follows declared `requires` edges transitively and emits dependencies before dependents; `run_wizard` passes that order to `run_installs`. No tier-specific resolver is needed. [installer/deps.py:32](/Users/ramon/git/personal/tools-installer/installer/deps.py:32), [installer/deps.py:121](/Users/ramon/git/personal/tools-installer/installer/deps.py:121), [installer/app.py:134](/Users/ramon/git/personal/tools-installer/installer/app.py:134)

- The Oh-My-Zsh environment design matches the executor. `_env_prefix` quotes values and attaches assignments to the shell side of the pipe, so `KEEP_ZSHRC=yes`, `RUNZSH=no`, and `CHSH=no` reach `install.sh`. [installer/executors.py:334](/Users/ramon/git/personal/tools-installer/installer/executors.py:334), [installer/executors.py:353](/Users/ramon/git/personal/tools-installer/installer/executors.py:353)

- `detect_path` is the right installed-state mechanism for Oh-My-Zsh. The status path first checks `cmd`, then accepts a declared marker path, matching the existing SDKMAN behavior. [installer/status.py:16](/Users/ramon/git/personal/tools-installer/installer/status.py:16), [installer/registry.toml:1314](/Users/ramon/git/personal/tools-installer/installer/registry.toml:1314)

- The proposed `zsh` method ladder behaves as claimed when Homebrew is available: native managers apply on mutable Linux, native methods are suppressed on immutable Linux, and brew remains. [installer/resolve.py:32](/Users/ramon/git/personal/tools-installer/installer/resolve.py:32), [tests/test_registry.py:189](/Users/ramon/git/personal/tools-installer/tests/test_registry.py:189)

### Concerns

- **HIGH — The plan omits a real hard dependency on `git`.** Oh-My-Zsh lists Git as a prerequisite, and its installer performs Git repository operations. The script executor supplies only `curl` and the selected shell; it does not install Git. Meanwhile, `git` is a separate user-tier catalog tool, so `requires=["zsh"]` will not drag it in. The Tier-3 procedure hides this by running `apt-get install ... git` manually before the tested pipeline. [installer/executors.py:353](/Users/ramon/git/personal/tools-installer/installer/executors.py:353), [installer/registry.toml:244](/Users/ramon/git/personal/tools-installer/installer/registry.toml:244), [Oh-My-Zsh prerequisites and installer](https://github.com/ohmyzsh/ohmyzsh)

- **MEDIUM — The Tier-3 run does not reproduce the claimed catalog dependency chain.** It manually installs zsh and then manually invokes the vendor script. It bypasses `resolve_dependencies`, `run_installs`, installed-state short-circuiting, and the registry-generated method selection—the actual production path at [installer/app.py:134](/Users/ramon/git/personal/tools-installer/installer/app.py:134). It proves vendor behavior, but not "the resolver chain for real."

- **LOW — The mutable `master` script remains a semantic-drift risk.** The environment variables are effective against the current script, but future installs download a later revision. The fresh container run and dated comment reduce this risk, but do not bind runtime behavior to the reviewed revision. [installer/registry.toml:151](/Users/ramon/git/personal/tools-installer/installer/registry.toml:151) shows the project already accepts this pattern.

### Suggestions

- Change Oh-My-Zsh to `requires = ["zsh", "git"]`, or explicitly obtain user approval to treat Git as an installer-wide host prerequisite. The former exercises the intended cross-tier dependency mechanism.

- Run the Tier-3 vendor-behavior check without preinstalling Git first, confirm the expected failure, then rerun through a catalog-equivalent order that installs both declared dependencies.

- Add a registry-backed `resolve_dependencies` test proving the real `git → zsh → oh-my-zsh` order, followed by `run_installs` with recorded calls. Keep the container test specifically for `.zshrc` preservation.

### Risk Assessment

**HIGH.** The `.zshrc` safety work is strong, but the planned entry can fail on a clean Linux installation because the test preinstalls an undeclared prerequisite.

---

## Plan 07-02 — GNU Bash and Apple Containers

### Summary

The GNU Bash collision analysis is good, and the `os`/`arch` method restrictions are mechanically correct. Apple Containers, however, does not satisfy D-01: the proposed catalog row remains enabled and selectable, macOS-version incompatibility is not detected, and the real wizard path produces an unavailable-dependency warning rather than a `NO_METHOD` outcome.

### Strengths

- The `/bin/bash` false-positive is real. `is_installed` checks `shutil.which(tool.cmd)` before `detect_path`, so `cmd="bash"` would accept macOS's bundled Bash before inspecting Homebrew paths. [installer/status.py:16](/Users/ramon/git/personal/tools-installer/installer/status.py:16)

- Arch-split methods will resolve correctly for installation because `_applies` checks both `os` and `arch`. Homebrew's current formula does require macOS 26 and arm64, so a real brew installation method is well supported. [installer/resolve.py:32](/Users/ramon/git/personal/tools-installer/installer/resolve.py:32), [Homebrew container formula](https://formulae.brew.sh/formula/container)

- The uninstall hint remains correct with a synthetic command name because `_manager_hint` uses the method's `formula`, not `tool.cmd`. [installer/uninstall.py:129](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:129)

### Concerns

- **HIGH — `NO_METHOD` is not a disabled catalog state.** `CatalogScreen` receives no platform or availability data, renders no disabled status, and leaves the browser's default "everything selectable" policy in force. [installer/catalog_tui.py:160](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:160), [installer/catalog_tui.py:201](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:201), [installer/tool_browser.py:60](/Users/ramon/git/personal/tools-installer/installer/tool_browser.py:60)

- **HIGH — The plan describes the wrong production outcome.** In the wizard, `resolve_dependencies` evaluates availability before installation, marks an unavailable selected tool blocked, warns, and removes it from the runnable order. Consequently, `install_tool` is never called and its `NO_METHOD` branch is never reached. [installer/app.py:134](/Users/ramon/git/personal/tools-installer/installer/app.py:134), [installer/deps.py:92](/Users/ramon/git/personal/tools-installer/installer/deps.py:92), [installer/deps.py:102](/Users/ramon/git/personal/tools-installer/installer/deps.py:102), [installer/engine.py:83](/Users/ramon/git/personal/tools-installer/installer/engine.py:83)

- **HIGH — Wrong macOS versions still appear available.** `Platform` has OS family, architecture, immutability, and brew presence, but no OS version. On an arm64 Mac below macOS 26, the method resolves and remains selectable; Homebrew rejects it only after confirmation. That directly conflicts with D-01's "wrong macOS version shows disabled" requirement. [installer/platform.py:19](/Users/ramon/git/personal/tools-installer/installer/platform.py:19), [installer/resolve.py:32](/Users/ramon/git/personal/tools-installer/installer/resolve.py:32)

- **MEDIUM — The proposed architecture rule overgeneralizes an unresolved product decision.** The composition root already has `Platform`, and the reusable browser already supports non-selectable rows. The uninstall view demonstrates the exact dimmed, inert pattern that could be reused. [setup.py:141](/Users/ramon/git/personal/tools-installer/setup.py:141), [installer/wizard_app.py:581](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:581), [installer/wizard_app.py:683](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:683)

- **LOW — GNU Bash detection is asserted structurally rather than behaviorally.** The proposed test checks `cmd` and paths, but never calls `is_installed` under a simulated `/bin/bash` PATH. Also, `detect_path` checks all methods without platform filtering, so an Intel-prefix Bash can satisfy the entry on Apple Silicon. [installer/status.py:24](/Users/ramon/git/personal/tools-installer/installer/status.py:24)

### Suggestions

- Reopen D-01 instead of silently redefining "disabled." Either implement the locked behavior or obtain approval to weaken it to an install-time warning.

- Pass platform availability into the catalog, reuse `BrowserAdapter.selectable`, and mirror the uninstall view's dim/inert rendering. The composition root already owns `Platform`.

- Add a macOS-version capability to `Platform` or another explicit availability seam. Homebrew's later rejection cannot satisfy a browsing-time disabled-state requirement.

- Remove or postpone the proposed architecture subsection until the product decision is resolved. If documentation is retained, describe the actual `resolve_dependencies` warning path, not `install_tool.NO_METHOD`.

- Add a behavioral GNU Bash status test with mocked `shutil.which` and prefix paths.

### Risk Assessment

**HIGH.** This plan would codify a behavior that contradicts D-01 and inaccurately documents the production control flow.

---

## Plan 07-03 — kitty, WezTerm, and terminal category

### Summary

The category and download mechanics are mostly well designed. The plan honestly records the local `.txz` limitation and chooses a suitable raw AppImage for WezTerm. Its closeout verification is broken, however, and its tests fail to pin the two fields that prevent the AppImage from being incorrectly treated as a gzip archive.

### Strengths

- Adding `Category.TERMINAL` plus a registry blurb is the correct minimal schema change. Both loaders validate category IDs against the enum, while existing tests enforce blurb/tool parity. [installer/model.py:181](/Users/ramon/git/personal/tools-installer/installer/model.py:181), [installer/model.py:286](/Users/ramon/git/personal/tools-installer/installer/model.py:286), [tests/test_registry.py:942](/Users/ramon/git/personal/tools-installer/tests/test_registry.py:942)

- The WezTerm checksum template is supported exactly as claimed: `{asset}` expands after asset rendering, the checksum is downloaded beside the asset, and `expected_sha256` handles `<hash> <filename>` sidecars. [installer/download.py:51](/Users/ramon/git/personal/tools-installer/installer/download.py:51), [installer/download.py:153](/Users/ramon/git/personal/tools-installer/installer/download.py:153), [installer/checksums.py:23](/Users/ramon/git/personal/tools-installer/installer/checksums.py:23), [WezTerm release assets](https://github.com/wezterm/wezterm/releases/tag/20240203-110809-5046fc22)

- `raw=true` correctly bypasses archive extraction and copies/chmods the verified AppImage directly. [installer/download.py:190](/Users/ramon/git/personal/tools-installer/installer/download.py:190)

- The documented kitty extraction gap is real in this codebase: all non-ZIP archives use `tar -xzf`, while immutable systems suppress native package managers. [installer/download.py:136](/Users/ramon/git/personal/tools-installer/installer/download.py:136), [installer/download.py:203](/Users/ramon/git/personal/tools-installer/installer/download.py:203), [installer/resolve.py:45](/Users/ramon/git/personal/tools-installer/installer/resolve.py:45)

### Concerns

- **HIGH — Task 2's verification command cannot pass.** The task adds six rows containing `Phase 7` and then changes the footer to contain `Phase 7`; `grep -c 'Phase 7'` therefore sees at least seven lines, not six. The file's decision table and footer are separate lines. [`.planning/PROJECT.md:88`](/Users/ramon/git/personal/tools-installer/.planning/PROJECT.md:88), [`.planning/PROJECT.md:103`](/Users/ramon/git/personal/tools-installer/.planning/PROJECT.md:103)

- **MEDIUM — The tests do not pin `raw=true` or the exact checksum field.** The proposed WezTerm resolve test checks only method kinds. If `raw=true` disappears, resolution still passes but installation sends the AppImage to `tar -xzf`. If `checksum` disappears, the comment test can still pass. The existing sidecar allowlist also omits WezTerm. [tests/test_registry.py:841](/Users/ramon/git/personal/tools-installer/tests/test_registry.py:841), [installer/download.py:194](/Users/ramon/git/personal/tools-installer/installer/download.py:194), [installer/download.py:207](/Users/ramon/git/personal/tools-installer/installer/download.py:207)

- **MEDIUM — The proposed statement that kitty has no Linux cask path is already stale.** Homebrew's current kitty cask page includes Linux-on-Intel artifacts. The project still blocks all casks on Linux, so this does not automatically create a working method, but the verification comment should not claim that no upstream Linux cask exists. [installer/resolve.py:42](/Users/ramon/git/personal/tools-installer/installer/resolve.py:42), [Homebrew kitty cask](https://formulae.brew.sh/cask/kitty)

- **MEDIUM — Phase closeout is premature.** Plan 03 claims all four success criteria are satisfied, but Plan 02 leaves Apple Containers enabled in the catalog on unsupported machines and cannot detect macOS versions.

### Suggestions

- Change the PROJECT verification to count outcome cells only, for example `grep -cE '\| Phase 7 \|$'`, and verify the footer separately.

- In the WezTerm test, assert the exact asset, `checksum == "{asset}.sha256"`, `raw is True`, `member == "wezterm"`, and `arch == ("amd64",)`. Add `wezterm` to `SIDECAR_VERIFIED`, or replace that allowlist with a more direct exhaustive invariant.

- Re-check the current kitty cask metadata and record the precise decision: Linux cask support exists upstream but is unsupported by this project's current `resolve.py`/cask assumptions.

- Delay Phase 7 decision consolidation and completion claims until D-01 has an accepted, tested implementation.

### Risk Assessment

**HIGH as a phase-closing plan; MEDIUM for the registry changes alone.** The category and method definitions are plausible, but the closeout gate is impossible and the AppImage's load-bearing parameters lack regression coverage.

---

## Consensus Summary

Only one reviewer (Codex) produced a review this cycle — opencode-plan-review failed with
ETIMEDOUT on this phase's large 3-plan prompt bundle (a tool failure, not a completed review).
With a single reviewer, there is no cross-reviewer agreement/divergence to synthesize; Codex's
findings are source-grounded with concrete `file:line` citations against the actual repository
(registry, resolver, status, executors, download, catalog TUI, and test files), so they are
treated as fully weighted individual findings rather than downgraded.

### Agreed Strengths

Not applicable — only one reviewer ran this cycle.

### Agreed Concerns

Not applicable — only one reviewer ran this cycle. See "Codex Review" above for the full set of
HIGH/MEDIUM/LOW findings, each independently source-cited.

### Divergent Views

Not applicable — only one reviewer ran this cycle.
