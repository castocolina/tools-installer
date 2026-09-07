# Phase 12 Cross-AI Plan Reviews

## Cycle 1 (codex)

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`
**Commit reviewed:** `3d97ec8` (branch feat/tui-interaction-consistency, 4-plan Phase 12 plan set)
**Risk assessment:** HIGH (all 4 plans)

# Cross-AI Plan Review

## Overall verdict

**Revision required before execution. Overall risk: HIGH.**

The wave ordering is sensible—GitHub status and cache, manager status, update action, then stretch drift detection—but the plans share a false premise: `resolve_methods(tool, platform)[0]` identifies the manager that installed the tool. It only applies the installation preference ladder. That error can make status checks query the wrong manager and, more seriously, make `u` replace a Homebrew-managed tool with this installer’s download. Plan 12-04 also cannot detect its target condition and deliberately creates an unused production helper.

---

## 12-01 — GitHub status, cache, and background refresh

### Summary

The tracer-first structure is good, and the parsing/cache/Worker layers are appropriate. However, the plan is not implementation-ready: it places `CatalogScreen` behavior in the wrong module, omits the production inputs required to resolve platform-specific methods, calls a one-argument resolver with two arguments, and does not actually preserve multi-line `--version` output.

### Strengths

- Preserving `parse_version()` and adding a separate extractor is correct. The existing function intentionally parses only the first token and serves feature-floor checks, so changing it would alter established behavior ([versions.py:43](/Users/ramon/git/personal/tools-installer/installer/versions.py:43)).

- Reusing `resolve_github_tag()` retains its injectable fetch seam and ten-second network timeout ([versions.py:163](/Users/ramon/git/personal/tools-installer/installer/versions.py:163)).

- The proposed threaded Worker, message handoff, generation check, and latch test mirror proven code. The current Doctor worker posts results to the UI thread ([wizard_app.py:443](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:443)), discards superseded generations ([wizard_app.py:474](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:474)), and has a deterministic off-loop test ([test_wizard_app.py:1984](/Users/ramon/git/personal/tools-installer/tests/test_wizard_app.py:1984)).

- `~/.local/state/tools-installer` fits the existing userspace location convention ([locations.py:28](/Users/ramon/git/personal/tools-installer/installer/locations.py:28)).

### Concerns

- **HIGH — Wrong class/module and incomplete production wiring.** `CatalogScreen` is defined in `installer/catalog_tui.py`, not `wizard_app.py` ([catalog_tui.py:135](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:135)); `wizard_app.py` merely imports and constructs it ([wizard_app.py:30](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:30)). The plan repeatedly directs work into `wizard_app.py::CatalogScreen` ([12-01-PLAN.md:96](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:96)). More importantly, `UnifiedApp` currently receives neither `Platform` nor version-refresh closures ([wizard_app.py:1430](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1430)), and `_build_app()` is the composition root that owns the real platform ([setup.py:205](/Users/ramon/git/personal/tools-installer/setup.py:205)). `setup.py` is absent from the plan’s file list.

- **HIGH — The proposed resolver call violates the real type seam.** `TagResolver` is `Callable[[str], str]` ([versions.py:13](/Users/ramon/git/personal/tools-installer/installer/versions.py:13)), but the plan calls `resolve_tag(repo, fetch)` ([12-01-PLAN.md:93](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:93)). Strict pyright is enabled ([pyproject.toml:41](/Users/ramon/git/personal/tools-installer/pyproject.toml:41)), so this should fail validation.

- **HIGH — “Scan all lines” cannot work through the current probe.** `_default_probe_version()` returns only the first non-empty line ([versions.py:133](/Users/ramon/git/personal/tools-installer/installer/versions.py:133)), and a test explicitly pins that contract ([test_versions.py:192](/Users/ramon/git/personal/tools-installer/tests/test_versions.py:192)). Running `extract_observed_version()` afterward cannot recover eza’s second-line version or any other discarded output.

- **MEDIUM — Fresh-cache handling is internally inconsistent.** The status map starts empty, but Task 2 says to skip fresh entries entirely ([12-01-PLAN.md:116](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:116)). On a new process with a fresh cache, that can leave the Ver cells blank. Fresh entries should skip only the network request, not status reconstruction.

- **MEDIUM — Failed refreshes can repeat indefinitely.** On failure, the plan leaves the stale entry unchanged and marks the result stale. Every later view entry can immediately retry. This conflicts with the requirement to avoid silent retry loops and can amplify GitHub rate-limit failures.

- **MEDIUM — Multiple screens can race on one non-atomic cache.** `UnifiedApp` creates three independent `CatalogScreen` instances ([wizard_app.py:1452](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1452)). Textual cancellation does not stop a thread already in blocking work ([wizard_app.py:266](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:266)), so superseded workers may still write. The repository already has an atomic sibling-temp-plus-`os.replace` pattern ([omz.py:190](/Users/ramon/git/personal/tools-installer/installer/omz.py:190)).

### Suggestions

- Put refresh state and Worker behavior in `catalog_tui.CatalogScreen`, but inject a version-refresh service from `setup.py → UnifiedApp → CatalogScreen`. Add those files and constructor changes explicitly.

- Add a new full-output probe instead of changing `probe_version()`’s pinned first-line contract.

- Inject either `resolve_latest(repo) -> str` or `fetch`; do not pass both through the existing `TagResolver`.

- Reconstruct status from fresh cache entries, record failed-attempt timestamps or a session-level attempted set, and write the cache atomically.

- Add tests for exactly seven days (`>=`, not `>`), invalid timestamps, valid JSON with invalid field types, fresh cache after process restart, and rapid navigation between tier screens.

### Risk assessment

**HIGH.** The conceptual layers are sound, but the current instructions would fail strict typing and cannot correctly wire the feature into production.

---

## 12-02 — Manager-backed version resolution

### Summary

The command research and parser separation are strong. The main design is nevertheless unsafe: installation preference is treated as ownership, each stale tool launches a manager-global query, and the parsers discard the current-version and ownership data needed by the phase.

### Strengths

- The plan correctly identifies why `run_output()` cannot handle pnpm’s exit-1-with-useful-stdout behavior: it raises on non-zero and preserves only stderr in `CommandError` ([run.py:53](/Users/ramon/git/personal/tools-installer/installer/run.py:53)).

- Requiring `real_pnpm()` is essential because bare `pnpm` may resolve to this installer’s wrapper ([guards.py:315](/Users/ramon/git/personal/tools-installer/installer/guards.py:315)).

- Splitting pure parsers from I/O wrappers matches the existing `pnpm_global_packages()` pattern ([pnpm_globals.py:383](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:383)).

- `None` for an unreadable manager response is consistent with the repository’s “unknown is not empty” convention ([pnpm_globals.py:396](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:396)).

### Concerns

- **HIGH — `resolve_methods()[0]` is not the owning manager.** The resolver only filters applicable methods and sorts them by `_RANK` ([resolve.py:9](/Users/ramon/git/personal/tools-installer/installer/resolve.py:9), [resolve.py:68](/Users/ramon/git/personal/tools-installer/installer/resolve.py:68)). Tests explicitly describe this as preference—node and uv-tool rank before brew ([test_resolve.py:128](/Users/ramon/git/personal/tools-installer/tests/test_resolve.py:128)). `is_installed()` records only PATH/bundle presence, not provenance ([status.py:16](/Users/ramon/git/personal/tools-installer/installer/status.py:16)). Consequently, a tool installed through brew may be queried as GitHub/node/uv instead.

- **HIGH — Manager queries are performed once per stale tool.** The plan calls a fresh `brew_outdated()`/pnpm/uv query inside each tool’s resolver ([12-02-PLAN.md:102](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:102)). These commands return manager-wide sets; twenty stale brew tools should cause one brew query, not twenty.

- **HIGH — The result types discard required information.** Brew supplies `installed_versions` and `current_version`, pnpm supplies `current` and `latest`, and uv prints both; the proposed parsers retain only latest ([12-02-PLAN.md:80](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:80)). A local command probe may resolve a different manager’s binary. It also cannot cover GUI casks that are detected by bundle presence rather than a command ([status.py:31](/Users/ramon/git/personal/tools-installer/installer/status.py:31)).

- **MEDIUM — Cask handling is underspecified.** `brew_outdated()` has no formula/cask selector, the parser description names only `formulae`, yet the plan says a second `--cask` call will cover casks. The merge behavior, name-collision behavior, and failure semantics for one successful and one failed call are absent.

- **MEDIUM — The runner contract cannot express all promised behavior.** `OutputRunner` accepts only argv ([run.py:6](/Users/ramon/git/personal/tools-installer/installer/run.py:6)); `run_output()` supports a timeout but no environment or accepted return-code set ([run.py:36](/Users/ramon/git/personal/tools-installer/installer/run.py:36)). The plan promises merged brew environment variables, pnpm return codes `{0,1}`, and bounded timeouts without specifying the common execution seam or adding `run.py` to the plan.

### Suggestions

- Introduce an explicit `ManagerOwnership` resolver. Use installer artifact presence for installer-owned downloads/apps, plus real manager inventories for brew, pnpm, and uv. Never derive ownership from `_RANK`.

- Query each manager once per refresh wave, parse into `dict[package, ManagerVersion(current, latest)]`, and fan the result out across rows.

- Preserve current and latest versions from manager output. This also makes casks and commands shadowed by another manager report correctly.

- Define one bounded query runner supporting environment overrides and accepted exit codes, preferably in `installer/run.py`, with tests for environment merging and timeout propagation.

### Risk assessment

**HIGH.** As written, this plan can produce false “up to date” results and feeds incorrect ownership into the mutating update plan.

---

## 12-03 — Manager-delegated update action

### Summary

The plan correctly recognizes `install_tool()`’s installed short-circuit and the need for threaded mutation. It still cannot guarantee manager delegation, safe replacement, or reliable failure reporting. These are blocking issues because this plan executes real package-manager and filesystem mutations without confirmation.

### Strengths

- The plan correctly avoids calling `install_tool()` for an already-installed userspace tool; the engine returns `ALREADY_INSTALLED` before resolving a method ([engine.py:101](/Users/ramon/git/personal/tools-installer/installer/engine.py:101)).

- The brew, cask, uv, and absolute-pnpm argv mapping follows the existing executor conventions ([executors.py:375](/Users/ramon/git/personal/tools-installer/installer/executors.py:375), [executors.py:379](/Users/ramon/git/personal/tools-installer/installer/executors.py:379), [executors.py:456](/Users/ramon/git/personal/tools-installer/installer/executors.py:456)).

- The proposed Worker/message/Pilot test follows the repository’s proven non-blocking test architecture.

### Concerns

- **HIGH — The “actual manager” guarantee is false.** The plan explicitly claims the first resolved method “is the method that installed the tool” ([12-03-PLAN.md:79](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:79)); the resolver makes no such determination. For example, `rg` declares GitHub, native, and brew methods ([registry.toml:81](/Users/ramon/git/personal/tools-installer/installer/registry.toml:81)), while GitHub ranks ahead of brew. Pressing update on a brew-installed `rg` could install a second copy into `~/.local/bin`, changing ownership and PATH precedence.

- **HIGH — Production mutation dependencies are not wired.** `CatalogScreen` currently receives no `Platform`, `Runner`, tag resolver, update closure, or pnpm-reinstall closure ([catalog_tui.py:160](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:160)). `UnifiedApp` and `setup.py` must participate, but neither `setup.py` nor its tests appear in the plan’s file list ([12-03-PLAN.md:7](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:7)).

- **HIGH — Existing install executors are not update-atomic.** Raw downloads write directly over the live executable ([download.py:123](/Users/ramon/git/personal/tools-installer/installer/download.py:123)); archives extract into the existing live opt directory ([download.py:128](/Users/ramon/git/personal/tools-installer/installer/download.py:128)); app installation moves directly into `~/Applications` without replacing or backing up an existing bundle ([apps.py:44](/Users/ramon/git/personal/tools-installer/installer/apps.py:44)). Reusing these paths for updates can corrupt a working installation or fail because the destination already exists.

- **HIGH — Exception isolation is incomplete.** `run_live()` catches only `OSError` and `CommandError` ([ui_common.py:41](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:41)). The proposed path can raise `UpdateError`, `ExecutorError`, `VersionError`, and `ChecksumMismatch`. Textual’s default worker behavior can terminate the app on an uncaught exception; the repository’s daemon worker explicitly uses `exit_on_error=False` and a `finally` post for this reason ([wizard_app.py:1538](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1538)).

- **HIGH — `exclusive=True` does not prevent concurrent updates.** A cancelled Textual Worker cannot stop a thread already inside `subprocess.run` ([wizard_app.py:266](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:266)). Without an explicit in-flight guard, a second `u` can start another package-manager mutation while the first continues.

- **MEDIUM — The pnpm recovery trigger is broader than the stated requirement.** The plan replays all globals after every node-package update, not only after pnpm itself changes ([12-03-PLAN.md:105](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:105)). `reinstall_node_globals()` intentionally includes globals unknown to this registry ([pnpm_globals.py:665](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:665)), so this is a significant secondary mutation.

- **MEDIUM — Direct executor dispatch skips postinstall hooks.** `install_tool()` invokes the declared hook after method success ([engine.py:123](/Users/ramon/git/personal/tools-installer/installer/engine.py:123)). The proposed direct download/app/executor path bypasses it, which can leave updated tools such as codegraph with stale integrations.

- **MEDIUM — TUI subprocess output is unresolved.** `run_command()` inherits the terminal ([run.py:23](/Users/ramon/git/personal/tools-installer/installer/run.py:23)); manager progress can corrupt Textual rendering. `run_captured()` exists for exactly this situation ([run.py:64](/Users/ramon/git/personal/tools-installer/installer/run.py:64)), but capturing means the plan must provide an explicit progress/result display rather than promising unspecified “live output.”

### Suggestions

- Make ownership resolution a prerequisite and pass a resolved `UpdateTarget(tool, manager, method)` into `perform_update()`.

- Build update-safe userspace executors: stage, validate, atomically replace, and retain the old installation until success.

- Catch all expected domain exceptions inside `perform_update()` and return a typed outcome. Use `exit_on_error=False`, a guaranteed completion message, and an explicit `update_running` guard.

- Run version re-probing inside the worker and include the post-update status in `ToolUpdated`; never spawn a version subprocess from the UI handler.

- Trigger the global replay only when pnpm itself was updated, unless a separate requirement explicitly authorizes replay after every node tool update.

- Decide and test whether successful updates rerun declared postinstall hooks.

### Risk assessment

**HIGH.** This is a mutating, no-confirmation action whose current routing can target the wrong manager and whose userspace fallback is not failure-safe.

---

## 12-04 — Manager-drift alerting

### Summary

This plan should be removed or deferred. Its proposed data source cannot detect an uninstalled brew alternative, it never compares the active pnpm version with the brew version, and it deliberately leaves the helper unwired—so no alert is surfaced.

### Strengths

- Limiting candidates to registry-declared alternatives avoids formula-name guessing and false identity matches.

- Keeping drift auto-remediation out of scope respects D-02.

- A synthetic fixture is reasonable when the registry has no current qualifying row.

### Concerns

- **HIGH — The implementation cannot detect the intended condition.** I independently ran `brew help outdated`; it defines the command as listing **installed** formulae/casks with updates. A node-managed tool’s declared but uninstalled brew alternative therefore will not appear. The plan’s synthetic fake returning that formula constructs a state the real command would not produce ([12-04-PLAN.md:67](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:67)).

- **HIGH — No active-vs-alternative comparison exists.** The helper returns an alert whenever the brew lookup hits, but its inputs contain no active pnpm version. It cannot prove brew is newer than the installed node version.

- **HIGH — The requirement says “surface,” but the plan creates dead code.** The plan explicitly says the helper will not be wired into the status loop ([12-04-PLAN.md:27](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:27)). Repository architecture forbids production helpers with zero callers ([architecture.md:23](/Users/ramon/git/personal/tools-installer/.claude/architecture.md:23)).

- **MEDIUM — `active_kind` inherits the unresolved ownership problem.** Supplying a preferred method kind cannot establish that pnpm actually owns the live binary.

### Suggestions

- Prefer deferring 12-04 entirely. It is non-MVP, has no real registry case, and the current proposal violates the no-orphan-helper rule.

- If retained, use real ownership data plus a command that resolves an uninstalled formula’s available version, such as a structured `brew info` query. Compare normalized `active_current < brew_available`.

- Wire the resulting drift state through `VersionStatus`, the Ver cell/detail text, and a Pilot test. Otherwise do not claim REQ-manager-drift-alerting is addressed.

### Risk assessment

**HIGH.** The planned function cannot observe the target state and produces no user-visible alert.

---

## Recommended revised sequence

1. Add a tested ownership-resolution model and batched manager inventory queries.
2. Implement GitHub/full-output probing and an atomic, failure-aware cache.
3. Wire refresh dependencies through `setup.py → UnifiedApp → CatalogScreen`.
4. Add manager status from one query per manager.
5. Implement update-safe, ownership-directed actions with explicit in-flight and exception handling.
6. Defer manager drift until a real catalog case exists, or implement it end to end with an appropriate brew availability query.



## Cycle 2 (codex)

**Reviewer:** codex CLI, model `unknown`
**Commit reviewed:** `adef114` (branch feat/tui-interaction-consistency, revised 4-plan Phase 12 plan set, post cycle-1 fixes from commits ab0c075/adef114)
**Risk assessment:** see body below

# Cross-AI Plan Review — Cycle 2

Reviewed at commit `adef114db380741b6e79089ad7d2357440617ed4` on `feat/tui-interaction-consistency`. The worktree was clean.

I treat the 23 concern bullets in Cycle 1 as the findings requiring individual disposition.

## 1. Cycle-1 Finding Resolution Verification

### 12-01 — GitHub status, cache, and background refresh

1. **Wrong class/module and incomplete production wiring — RESOLVED.**

   The revised plan now places the worker, state, rendering, and update handling in the real [`installer/catalog_tui.py::CatalogScreen`](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:135), not in `wizard_app.py`. It explicitly threads one service from [`setup.py::_build_app`](/Users/ramon/git/personal/tools-installer/setup.py:205), through `UnifiedApp`, into all three catalog screens at [12-01-PLAN.md:189](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:189) and [12-01-PLAN.md:195](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:195). The real composition root already receives `platform` at [`setup.py:207`](/Users/ramon/git/personal/tools-installer/setup.py:207).

2. **`TagResolver` arity violation — RESOLVED.**

   The real alias remains one-argument `Callable[[str], str]` at [`installer/versions.py:13`](/Users/ramon/git/personal/tools-installer/installer/versions.py:13). The revision explicitly requires `resolve_tag(repo)` with one argument at [12-01-PLAN.md:176](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:176), and includes pyright and grep acceptance checks at [12-01-PLAN.md:213](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:213).

3. **Full-output parsing impossible through the existing probe — RESOLVED.**

   The plan preserves `_default_probe_version` and adds a separate full-output seam at [12-01-PLAN.md:164](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:164). This respects the existing first-nonempty-line contract at [`installer/versions.py:133`](/Users/ramon/git/personal/tools-installer/installer/versions.py:133), pinned by [`tests/test_versions.py:192`](/Users/ramon/git/personal/tools-installer/tests/test_versions.py:192).

4. **Fresh cache leaves a new process’s Ver cells blank — RESOLVED.**

   `resolve_github_release_status` must reconstruct status from `entry.latest_version` even when fetching is skipped at [12-01-PLAN.md:176](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:176). A fresh-service/same-cache regression test with zero resolver calls is required at [12-01-PLAN.md:240](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:240).

5. **Failed refreshes retry indefinitely — RESOLVED.**

   The revised cache entry has `failed_at`, with a six-hour `RETRY_BACKOFF`, and `should_fetch` suppresses attempts inside that window at [12-01-PLAN.md:167](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:167) and [12-01-PLAN.md:172](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:172). Boundary tests are required at [12-01-PLAN.md:238](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:238).

6. **Three catalog screens race on a non-atomic cache — RESOLVED for the planned production topology.**

   The plan shares one `VersionRefreshService` across all three screens, proven by identity at [12-01-PLAN.md:195](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:195). That service serializes reload-merge-save with a lock at [12-01-PLAN.md:177](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:177), while persistence uses the existing sibling-temp/`os.replace` mechanism extracted from [`installer/omz.py:190`](/Users/ramon/git/personal/tools-installer/installer/omz.py:190).

   The additional claim that two independent service instances are safe is not established; that is a new issue below.

### 12-02 — Manager-backed version resolution

7. **`resolve_methods()[0]` is not ownership — PARTIALLY RESOLVED.**

   The revision correctly introduces a separate `ManagerOwnership` model and expressly forbids using `_RANK` as provenance at [12-02-PLAN.md:113](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:113). It also adds the exact `rg` regression where GitHub ranks first but brew owns the copy at [12-02-PLAN.md:151](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:151). That addresses the original conceptual error.

   However, the proposed resolver still treats exactly one positive candidate as direct ownership without checking whether another relevant inventory was unreadable or whether that candidate owns the executable on PATH at [12-02-PLAN.md:136](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:136). `plan_uninstall` proves only that an installer artifact exists at [`installer/uninstall.py:56`](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:56); it does not prove that artifact is active. This is insufficient for the downstream mutating guarantee.

8. **Manager-global queries executed once per stale tool — RESOLVED.**

   `VersionRefreshService.refresh()` reads inventory and outdated reports once before entering the per-tool loop at [12-02-PLAN.md:243](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:243). A 25-versus-50-tool query-count test is required at [12-02-PLAN.md:261](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:261).

9. **Manager results discard current versions and ownership data — PARTIALLY RESOLVED.**

   `ManagerVersion(current, latest)` now retains both fields at [12-02-PLAN.md:193](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:193). Brew formula/cask inventory and uv inventory also preserve installed versions.

   Pnpm ownership inventory still reuses `pnpm_global_packages()`, whose actual result contains names only at [`installer/pnpm_globals.py:396`](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:396). Therefore an up-to-date pnpm package absent from the outdated report has no authoritative manager-reported current version; the fallback probe may observe a shadowed binary. The revision solves the outdated case but not all ownership/current-version cases raised by Cycle 1.

10. **Cask handling is underspecified — RESOLVED.**

    One `brew outdated --json=v2` call is parsed into separate formula and cask maps at [12-02-PLAN.md:195](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:195). A same-name formula/cask collision test and the shared-failure semantics are specified at [12-02-PLAN.md:212](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:212).

11. **Runner cannot express environment, accepted exit codes, and timeout — RESOLVED.**

    `run_query` now owns all three concerns at [12-02-PLAN.md:120](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:120), including environment merging and retained stdout on rejected exit codes. Pnpm explicitly passes `(0, 1)` at [12-02-PLAN.md:200](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:200).

### 12-03 — Manager-delegated update action

12. **The “actual manager” guarantee is false — PARTIALLY RESOLVED.**

    `perform_update` now consumes an already-resolved `ManagerOwnership` and dispatches on `ownership.owner` at [12-03-PLAN.md:116](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:116). The `rg` regression explicitly expects `brew upgrade ripgrep` at [12-03-PLAN.md:148](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:148).

    The guarantee remains only as reliable as the ownership resolver, whose single-candidate and unreadable-inventory cases remain unsafe. Thus the original false premise is removed, but the required “actual” ownership proof is incomplete.

13. **Production mutation dependencies are not wired — RESOLVED.**

    `setup.py`, `UnifiedApp`, `CatalogScreen`, and their tests are now in scope. One shared `UpdateService` is constructed using the real platform, runner, tag resolver, tool map, package snapshot seam, and existing replay closure at [12-03-PLAN.md:240](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:240). The existing closure is available at [`setup.py:352`](/Users/ramon/git/personal/tools-installer/setup.py:352).

14. **Existing installer-owned executors are not update-atomic — PARTIALLY RESOLVED.**

    New staging-based `update_download` and `update_app` paths are specified at [12-03-PLAN.md:176](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:176), instead of reusing the unsafe live-write behavior at [`installer/download.py:123`](/Users/ramon/git/personal/tools-installer/installer/download.py:123) and [`installer/apps.py:44`](/Users/ramon/git/personal/tools-installer/installer/apps.py:44).

    Rollback is nevertheless specified only for failure during the second replacement, not for later symlink recreation or cleanup failures at [12-03-PLAN.md:179](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:179). The acceptance claim that failure “at any point” preserves the old installation at [12-03-PLAN.md:206](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:206) is therefore stronger than the described algorithm.

15. **Exception isolation is incomplete — RESOLVED.**

    `perform_update` must convert all seven named domain exception types into `UpdateOutcome(status="failed")` at [12-03-PLAN.md:132](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:132). The Textual worker additionally uses `exit_on_error=False` and posts/clears state from `finally` at [12-03-PLAN.md:235](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:235), covering unexpected worker exceptions beyond `run_live`’s limited catches at [`installer/ui_common.py:41`](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:41).

16. **`exclusive=True` does not prevent concurrent updates — RESOLVED.**

    The shared `UpdateService` gains a lock-guarded global `begin`/`end` state at [12-03-PLAN.md:228](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:228). A held-latch, single-runner-invocation test is required at [12-03-PLAN.md:246](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:246).

17. **Pnpm recovery trigger is too broad — RESOLVED.**

    `should_replay_node_globals` is now true only for `tool.id == "pnpm"` at [12-03-PLAN.md:133](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:133), matching the actual requirement wording at [REQUIREMENTS.md:41](/Users/ramon/git/personal/tools-installer/.planning/REQUIREMENTS.md:41).

18. **Direct executor dispatch skips postinstall hooks — RESOLVED.**

    Successful updates re-run the declared postinstall through the owning method, with hook failure retained as a warning rather than changing primary success at [12-03-PLAN.md:131](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:131). This mirrors the existing install behavior at [`installer/engine.py:123`](/Users/ramon/git/personal/tools-installer/installer/engine.py:123).

19. **TUI subprocess output policy is unresolved — RESOLVED.**

    The revision explicitly chooses `run_captured`, an in-flight status line, and a final re-probed version or `CommandError.detail`, while deferring live streaming at [12-03-PLAN.md:237](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:237). That is consistent with the existing captured runner at [`installer/run.py:64`](/Users/ramon/git/personal/tools-installer/installer/run.py:64).

### 12-04 — Manager-drift alerting

20. **`brew outdated` cannot detect an uninstalled brew alternative — N/A / SUPERSEDED.**

    The runtime approach was genuinely removed, not cosmetically renamed. The current plan explicitly says the feature is not implemented and instead records a deferral at [12-04-PLAN.md:27](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:27). Its rationale names `brew outdated`’s installed-only scope at [12-04-PLAN.md:39](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:39).

21. **No active-pnpm-versus-brew comparison exists — N/A / SUPERSEDED.**

    No drift algorithm will ship. The plan accurately records that a future implementation needs an availability query plus normalized active-versus-available comparison at [12-04-PLAN.md:49](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:49).

22. **Requirement says “surface,” but the helper is deliberately unwired — N/A / SUPERSEDED.**

    The helper itself is removed from scope; no zero-caller production function is planned. The deferral is to be recorded in the requirement, roadmap criterion, and project decision log at [12-04-PLAN.md:92](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:92). This is authorized by D-02’s explicit planner-discretion clause at [12-CONTEXT.md:26](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-CONTEXT.md:26).

23. **`active_kind` inherits the unresolved ownership problem — N/A / SUPERSEDED.**

    No `active_kind` drift helper remains. Future implementation is explicitly required to build on real `installer/ownership.py` data at [12-04-PLAN.md:95](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:95).

## 2. New Issues Introduced By the Revision

- **HIGH — The pnpm-global snapshot is taken after pnpm is updated, defeating the recovery requirement.**

  `UpdateService.run()` first calls `perform_update`, and only afterward calls `managed_packages()` and `replay_globals()` at [12-03-PLAN.md:230](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:230). The requirement explicitly says to snapshot the pnpm-managed global set and reinstall it after pnpm updates at [REQUIREMENTS.md:41](/Users/ramon/git/personal/tools-installer/.planning/REQUIREMENTS.md:41). If the pnpm update is the event that loses globals, the post-update snapshot is already empty; the existing replay implementation treats an empty list as a no-op at [`installer/pnpm_globals.py:705`](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:705).

  Capture the package set before `perform_update`; replay that captured immutable snapshot only after successful pnpm self-update.

- **HIGH — Ownership still allows unsafe mutation from partial evidence.**

  Exactly one positive candidate becomes `confidence="direct"` without verifying the active executable or requiring all competing manager inventories to be readable at [12-02-PLAN.md:136](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:136). A stale `~/.local` artifact plus an unreadable brew inventory can therefore resolve as installer-owned even when `/opt/homebrew/bin/<cmd>` is the active copy. `plan_uninstall` reports artifact existence, not provenance or PATH precedence at [`installer/uninstall.py:56`](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:56).

  The mutating path should require either an active-path match to the candidate or complete negative evidence from every plausible competing manager. Otherwise ownership must be `unknown`.

- **HIGH — `pnpm update -g <package>` may not install the manager-reported latest version and bypasses node installation invariants.**

  The planned argv lacks `--latest` at [12-03-PLAN.md:122](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:122). The research’s real pnpm report already shows `current == wanted == 11.9.0` while `latest == 12.3.4` at [12-RESEARCH.md:221](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-RESEARCH.md:221). Locally verified `pnpm help update` states that ordinary update respects the declared range and `--latest` is what ignores it.

  This generic command also bypasses `_node`’s current co-install, build-allowlist, minimum-Node, version, and smoke-test handling at [`installer/executors.py:390`](/Users/ramon/git/personal/tools-installer/installer/executors.py:390) and [`installer/executors.py:452`](/Users/ramon/git/personal/tools-installer/installer/executors.py:452). The registry contains real node entries using those fields, such as `mmdc` at [`installer/registry.toml:2200`](/Users/ramon/git/personal/tools-installer/installer/registry.toml:2200).

- **HIGH — The seven-day cache does not cover manager queries.**

  Every `VersionRefreshService.refresh()` calls both `read_inventory()` and `read_outdated()` before processing tools at [12-02-PLAN.md:243](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:243). Therefore fresh sessions and tier navigation still launch brew, pnpm, and uv subprocesses every time, even though the requirement says a fresh session should refetch only stale entries at [REQUIREMENTS.md:85](/Users/ramon/git/personal/tools-installer/.planning/REQUIREMENTS.md:85).

  Manager reports need their own timestamped cache/backoff, or a shared refresh coordinator that skips manager queries when all relevant rows are fresh.

- **MEDIUM — The two-service cache-concurrency test contradicts the locking design.**

  The lock belongs to each `VersionRefreshService` instance at [12-01-PLAN.md:177](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:177), yet the plan requires two separate service instances writing the same path to retain both entries at [12-01-PLAN.md:240](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:240). Independent locks cannot serialize the reload-merge-save sequence. The extracted atomic writer also uses one deterministic sibling temp filename, following [`installer/omz.py:212`](/Users/ramon/git/personal/tools-installer/installer/omz.py:212), so separate writers can collide.

  Either limit the guarantee and test to the actual single-service production topology, or add a path-global/OS lock and unique sibling temp names.

- **MEDIUM — The version comparator can produce false “up to date” results.**

  The plan compares both strings via the existing `parse_version` at [12-01-PLAN.md:166](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:166). The real parser truncates numeric components after the third at [`installer/versions.py:73`](/Users/ramon/git/personal/tools-installer/installer/versions.py:73) and collapses prerelease variants into a single rank at [`installer/versions.py:76`](/Users/ramon/git/personal/tools-installer/installer/versions.py:76). Thus `1.2.3.4` versus `1.2.3.5`, or two different prereleases, can compare equal.

  A version-status comparator should preserve all relevant components or return unknown for unsupported version shapes.

- **MEDIUM — `ManagerOwnership` cannot support the UI messages the plans require.**

  The model carries only `shadowed: bool` and no candidate identities or failure reason at [12-02-PLAN.md:128](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:128). Later tasks require `_detail_text` to name the “other manager” at [12-02-PLAN.md:249](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:249), and require unknown-owner output to explain which inventories were unreadable at [12-03-PLAN.md:127](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:127). Those outputs cannot be derived from the specified object.

  Add structured evidence such as `candidates`, `active_candidate`, and `unknown_reason`.

- **MEDIUM — Malformed uv output can be interpreted as a clean, up-to-date report.**

  `parse_uv_tool_outdated` skips every unrecognized line and always returns a possibly empty mapping at [12-02-PLAN.md:197](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:197). Later, absence from a non-`None` map means “up to date” at [12-02-PLAN.md:247](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:247). A warning, changed output format, or arbitrary garbage can therefore become a false green result, contrary to the threat-model claim that malformed output returns unknown at [12-02-PLAN.md:308](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:308).

- **MEDIUM — Update rollback does not cover the whole replacement transaction.**

  Archive rollback is described only when the second `os.replace` fails at [12-03-PLAN.md:179](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:179). If replacement succeeds but symlink recreation fails, the old tree may be deleted or stranded even though the update reports failure. The same design does not define recovery from pre-existing `.new`/`.old` remnants.

  Wrap aside, replacement, symlink recreation, and validation in one rollback state machine; add tests for link recreation failure and interrupted-run residue.

- **MEDIUM — The new `u` action is not added to the repository’s canonical footer-action registry.**

  The plan adds a Textual binding at [12-03-PLAN.md:233](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:233), but omits `installer/ui_common.py` from its file list. The custom footer renders `View.actions` from `VIEW_BY_NAME` at [`installer/ui_common.py:191`](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:191), and the existing catalog actions still list only toggle/install/all/invert at [`installer/ui_common.py:106`](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:106). This violates the project’s single-view-registry rule at [`.claude/architecture.md:9`](/Users/ramon/git/personal/tools-installer/.claude/architecture.md:9) and makes update undiscoverable in the project’s own footer.

- **MEDIUM — Update and refresh results are not coordinated.**

  Version-refresh results have a generation guard, but `ToolUpdated` has no corresponding generation/epoch. A refresh started before an update can finish later and overwrite the freshly re-probed update status. This is especially weak for casks, for which command re-probing may be impossible and manager inventory is authoritative.

  On success, invalidate the row and schedule an ownership-aware refresh, or share a monotonic status epoch across refresh and update messages.

- **MEDIUM — Syntactically valid but unsafe timestamps are not covered.**

  Tests cover non-ISO timestamps, but not naive timestamps, non-UTC offsets, or future timestamps at [12-01-PLAN.md:238](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:238). Subtracting an aware UTC `now` from a naive parsed datetime can raise, while a far-future timestamp can suppress checking indefinitely.

  Accept only timezone-aware timestamps, normalize to UTC, and treat implausible future values as stale.

## 3. Per-Plan Assessment

### 12-01

**Summary:** The revision fixes the original module, DI, resolver-arity, full-output, fresh-cache, retry, and production cache-race problems. The tracer is now implementable.

**Strengths:**

- Correct production route from `setup.py` through `UnifiedApp` to the actual `CatalogScreen`.
- Preserves existing version-probe contracts.
- Makes staleness visible as well as actionable.
- Adds bounded GitHub fetching and deterministic off-event-loop tests.
- Extracts the atomic writer into one shared implementation.

**Concerns:**

- **MEDIUM:** Independent service-instance concurrency is claimed but unsupported.
- **MEDIUM:** The chosen comparator loses fourth components and prerelease distinctions.
- **MEDIUM:** Timestamp validation remains incomplete.

**Suggestion:** Keep the production single-service model explicit, strengthen timestamp and comparison semantics, and either remove or correctly implement the cross-service cache guarantee.

### 12-02

**Summary:** The central revision—separating ownership from installation preference—is correct, but the evidence rules are not yet strong enough to authorize mutation.

**Strengths:**

- Explicit `ManagerOwnership` abstraction.
- Batched manager inventories and outdated reports.
- Separate formula/cask namespaces.
- Fail-closed `None` representation for most unreadable manager data.
- Proper bounded runner with environment and return-code support.

**Concerns:**

- **HIGH:** A lone candidate is accepted without proving it owns the active executable or excluding unreadable competitors.
- **HIGH:** Manager queries ignore the seven-day cache and run on every refresh.
- **MEDIUM:** Pnpm inventory lacks authoritative current versions.
- **MEDIUM:** Ownership objects lack the evidence required by later UI plans.
- **MEDIUM:** The uv parser can turn malformed output into false “up to date.”

**Suggestion:** Introduce explicit evidence/candidate metadata, require active-path or complete-inventory proof before mutation, and cache/coalesce manager reports separately from per-tool GitHub data.

### 12-03

**Summary:** This is materially safer than Cycle 1, but it still contains two execution-blocking defects: pnpm recovery snapshots too late, and pnpm updates may not reach the reported latest or preserve node-install policy.

**Strengths:**

- Ownership-first dispatch.
- Refusal of `unknown` owners.
- Explicit global in-flight guard.
- Crash-contained worker and typed outcomes.
- Postinstall re-dispatch.
- Captured-output policy.
- Installer-owned staging and rollback direction is sound.

**Concerns:**

- **HIGH:** Pnpm global inventory is captured after the destructive event it is meant to recover from.
- **HIGH:** `pnpm update -g` is not guaranteed to install `latest` and bypasses registry node constraints, co-installs, build permissions, and smoke tests.
- **HIGH:** Unsafe ownership cases from 12-02 flow directly into a no-confirmation mutation.
- **MEDIUM:** Replacement rollback is incomplete after the live swap succeeds.
- **MEDIUM:** The canonical footer registry is not updated.
- **MEDIUM:** Refresh/update result races are not addressed.

**Suggestion:** Rework Task 3 around a pre-update snapshot, add a node-aware update strategy, require mutation-grade ownership confidence, and coordinate update completion with the version-refresh epoch.

### 12-04

**Summary:** Deferral is the correct disposition. It is transparent, authorized by D-02, and avoids shipping unusable dead code.

**Strengths:**

- Accurately records that SC#5 is not delivered.
- Gives structural, independently checkable reasons.
- Documents what a real future implementation would require.
- Preserves the no-orphan-helper architecture rule.

**Concerns:**

- **LOW:** A test rejecting every callable containing `drift` is broader than the stated goal. It could obstruct a future properly wired implementation rather than merely detecting an orphan.

**Suggestion:** Prefer a documentation assertion plus normal call-site/dead-code enforcement, or phrase the test around the Phase 12 disposition rather than banning a future function name globally.

## 4. Overall Risk Assessment

**Overall risk: HIGH.**

The revision genuinely resolves most Cycle-1 problems; it is not merely papering them over. In particular, the module/DI mistakes, resolver arity, full-output probe, batching, manager result shapes, exception containment, concurrent-update guard, postinstall handling, output policy, and manager-drift dead-code proposal were substantially corrected.

However, the phase is **not ready to execute as planned**. It needs a Cycle 3 because three issues affect real, no-confirmation mutations:

1. Pnpm globals are snapshotted after the update instead of before it.
2. Ownership can still be asserted from partial or stale evidence.
3. The pnpm update command may not reach the advertised latest version and bypasses existing node installation safeguards.

The manager-cache behavior also fails the stated “fresh session only refetches stale entries” objective, and several plan-to-plan data contracts are incomplete.

**Verdict: revision required; proceed to Cycle 3 before implementation.**


---

## Cycle 3 (codex, FINAL cycle)

**Reviewer:** codex CLI, model `unknown`
**Commit reviewed:** `3dc4cfb` (branch feat/tui-interaction-consistency, revised 4-plan Phase 12 plan set, post cycle-2 fixes from commits c2f1a0d/3dc4cfb)
**Risk assessment:** see body below

# Cross-AI Plan Review — Cycle 3 (Final)

Reviewed at commit `3dc4cfb281f2d162e8843ef9b44f04106ec2ba5d` on `feat/tui-interaction-consistency`. The worktree is clean. The new Phase 12 modules do not exist yet, so this review verifies the plans against the current executable seams they intend to extend.

## 1. Cycle-2 HIGH Finding Resolution Verification

### 1. Pnpm-global snapshot timing — RESOLVED

The revised order is explicit: `UpdateService.run()` captures `managed_packages()` first, calls `perform_update()` second, and replays the immutable captured tuple only after an `updated` outcome ([12-03-PLAN.md:278](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:278), [12-03-PLAN.md:283](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:283)). The regression test must record call order and simulate an update that empties the live package set ([12-03-PLAN.md:308](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:308)).

That mechanism addresses the real failure mode: the current replay function immediately returns on an empty package sequence ([pnpm_globals.py:705](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:705)). A post-update capture could therefore silently restore nothing; the revised pre-capture cannot.

### 2. Ownership evidence and active-path proof — PARTIALLY RESOLVED, remaining risk HIGH

The revision makes substantial progress:

- It separates ownership from `resolve_methods()`’s installation-preference ordering ([12-02-PLAN.md:37](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:37)); the current resolver indeed only sorts applicable methods by `_RANK` ([resolve.py:68](/Users/ramon/git/personal/tools-installer/installer/resolve.py:68)).
- It adds candidates, active path, active candidate, and a human-readable failure reason ([12-02-PLAN.md:152](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:152)).
- It removes the arbitrary fixed-order owner tiebreak and adds `brew --prefix`-based path attribution ([12-02-PLAN.md:147](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:147), [12-02-PLAN.md:165](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:165)).
- The exact stale-artifact/unreadable-brew case must return `unknown` ([12-02-PLAN.md:190](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:190)). That is important because `plan_uninstall()` proves only that artifacts exist ([uninstall.py:56](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:56)), not that they own the active executable.

However, three gaps still invalidate the plan’s “complete evidence” claim:

1. The decision procedure says that any single candidate wins by elimination whenever `unreadable` is empty ([12-02-PLAN.md:168](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:168)). It does not first reject a non-`None` active path that points outside that candidate. This directly contradicts the required `/usr/bin/rg` test, which expects `unknown` ([12-02-PLAN.md:192](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:192)). As written, the algorithm returns the candidate before reaching the “unattributable active binary” fallback.

2. The inventory parsers do not make malformed output unreadable. Brew inventory skips malformed lines, and uv inventory has no fail-closed rule for unrecognized lines ([12-02-PLAN.md:148](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:148), [12-02-PLAN.md:149](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:149)). Those parsers return ordinary mappings, which then count as complete negative evidence. The reused pnpm parser likewise returns an empty tuple for several structurally valid but unrecognized JSON shapes because it skips non-dict projects/groups ([pnpm_globals.py:264](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:264), [pnpm_globals.py:287](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:287)).

3. Mutation uses ownership reconstructed from a cached manager inventory that may be six hours old ([12-02-PLAN.md:298](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:298), [12-02-PLAN.md:312](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:312)). That is suitable for display caching, but not complete negative evidence for a no-confirmation mutation after the user has changed managers outside this app.

The exact Cycle-2 scenario is covered, but the general mutation-grade ownership guarantee is not yet safe.

### 3. Pnpm update strategy — RESOLVED

The revised plan rejects both `pnpm update -g` and `pnpm update -g --latest` and dispatches pnpm-owned tools through `executors.execute(ownership.method, runner)` using the existing `node` method ([12-03-PLAN.md:147](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:147), [12-03-PLAN.md:154](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:154)).

That reuse genuinely preserves the current node invariants:

- Absolute `real_pnpm()` resolution ([executors.py:379](/Users/ramon/git/personal/tools-installer/installer/executors.py:379)).
- Comma-grouped co-installation.
- Registry version pins and `--allow-build`.
- Node/pnpm version floors.
- The smoke check after installation ([executors.py:417](/Users/ramon/git/personal/tools-installer/installer/executors.py:417), [executors.py:453](/Users/ramon/git/personal/tools-installer/installer/executors.py:453)).

The real `mmdc` entry uses every relevant field ([registry.toml:2201](/Users/ramon/git/personal/tools-installer/installer/registry.toml:2201)). The specified test verifies the resulting argv rather than merely asserting that `execute()` was called ([12-03-PLAN.md:168](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:168)).

### 4. Manager-query staleness cache — RESOLVED for the original finding

Plan 12-02 now stores inventory and outdated reports as one timestamped manager snapshot in the same cache envelope ([12-02-PLAN.md:293](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:293)). `VersionRefreshService.refresh()` must issue zero manager subprocesses when that snapshot is fresh and only re-query after its six-hour staleness interval or retry backoff ([12-02-PLAN.md:298](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:298), [12-02-PLAN.md:326](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:326)).

This directly resolves the Cycle-2 complaint that every fresh session or tier navigation invoked brew, pnpm, and uv again. The invalidation and mutation-authorization consequences have separate problems discussed below.

## 2. Full Finding Resolution Verification

### Cycle 1 findings

| # | Finding | Verdict | Current evidence |
|---|---|---|---|
| 1 | Wrong `CatalogScreen` module and missing production wiring | RESOLVED | Work targets the real class in `catalog_tui.py`, and one service is constructed in `_build_app()` and passed through `UnifiedApp` ([12-01-PLAN.md:220](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:220), [12-01-PLAN.md:224](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:224)). The current class is indeed defined at [catalog_tui.py:135](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:135), while `_build_app()` is the real composition root at [setup.py:205](/Users/ramon/git/personal/tools-installer/setup.py:205). |
| 2 | `TagResolver` arity violation | RESOLVED | The plan calls `resolve_tag(repo)` with one argument ([12-01-PLAN.md:206](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:206)), matching the current alias `Callable[[str], str]` ([versions.py:13](/Users/ramon/git/personal/tools-installer/installer/versions.py:13)). |
| 3 | Existing probe discards multiline output | RESOLVED | A new full-output probe is added while `_default_probe_version()` remains unchanged ([12-01-PLAN.md:189](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:189), [12-01-PLAN.md:212](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:212)). The current probe returns only the first non-empty line ([versions.py:133](/Users/ramon/git/personal/tools-installer/installer/versions.py:133)). |
| 4 | Fresh cache leaves Ver blank | RESOLVED | Fresh entries reconstruct `VersionStatus`; only the network request is skipped ([12-01-PLAN.md:206](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:206), [12-01-PLAN.md:275](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:275)). |
| 5 | Failed refresh retries forever | RESOLVED | `failed_at`, six-hour `RETRY_BACKOFF`, and explicit one-hour/seven-hour tests provide bounded retry behavior ([12-01-PLAN.md:200](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:200), [12-01-PLAN.md:273](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:273)). |
| 6 | Three screens race on a non-atomic cache | RESOLVED for the supported topology | One service is shared by all screens; same-service workers serialize reload/merge/save, and unique sibling temp names prevent temp-file collision ([12-01-PLAN.md:98](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:98), [12-01-PLAN.md:146](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:146), [12-01-PLAN.md:275](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:275)). The plan now explicitly excludes independent-process merge guarantees. |
| 7 | `resolve_methods()[0]` treated as owner | PARTIALLY RESOLVED | The conceptual conflation is removed, but the ownership algorithm still has contradictory and fail-open evidence branches; see primary finding 2. |
| 8 | Manager queries once per stale tool | RESOLVED | Inventory/outdated calls occur before the per-tool loop, with a 25-versus-50-tool constant-count test ([12-02-PLAN.md:298](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:298), [12-02-PLAN.md:330](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:330)). |
| 9 | Manager results discard current version/ownership data | PARTIALLY RESOLVED | Brew, cask, pnpm-outdated, and uv-outdated use `ManagerVersion(current, latest)` ([12-02-PLAN.md:238](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:238)). Pnpm inventory still contains names only—the current API returns `tuple[str, ...]` ([pnpm_globals.py:396](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:396))—so an up-to-date pnpm package absent from the outdated map still lacks manager-authoritative current-version data and falls back to a command probe ([12-02-PLAN.md:303](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:303)). |
| 10 | Cask handling underspecified | RESOLVED | One brew JSON payload is split into independent formula and cask maps, including same-name collision coverage ([12-02-PLAN.md:241](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:241), [12-02-PLAN.md:261](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:261)). |
| 11 | Runner lacks env, accepted codes, and timeout | RESOLVED | `run_query()` explicitly merges environment overrides, supports accepted codes, preserves stdout, and imposes a timeout ([12-02-PLAN.md:145](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:145)). This leaves existing `run_output()` callers unchanged; its current narrower contract is visible at [run.py:36](/Users/ramon/git/personal/tools-installer/installer/run.py:36). |
| 12 | “Actual manager” guarantee is false | PARTIALLY RESOLVED | Update dispatch now consumes `ManagerOwnership` and never indexes installation preference ([12-03-PLAN.md:150](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:150)). Its correctness remains limited by the unresolved ownership evidence defects. |
| 13 | Production mutation dependencies not wired | RESOLVED | One `UpdateService` is built in `_build_app()` using the real platform, tool map, captured runner, existing pnpm replay closure, and the same refresh service’s invalidator ([12-03-PLAN.md:296](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:296)). |
| 14 | Installer-owned update executors are unsafe | PARTIALLY RESOLVED | Staging, checksum-before-swap, remnants, aside/swap, and failure tests are now specified ([12-03-PLAN.md:207](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:207)). However, the promised symlink rollback and atomic app replacement remain underspecified; see Cycle-2 rollback finding and new issues. The current install paths are indeed unsafe for update reuse ([download.py:123](/Users/ramon/git/personal/tools-installer/installer/download.py:123), [apps.py:44](/Users/ramon/git/personal/tools-installer/installer/apps.py:44)). |
| 15 | Exception isolation incomplete | RESOLVED | Seven domain exception types become typed failure outcomes, while the worker uses `exit_on_error=False` and a guaranteed `finally` completion path ([12-03-PLAN.md:150](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:150), [12-03-PLAN.md:290](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:290)). This is necessary because current `run_live()` catches only `OSError` and `CommandError` ([ui_common.py:41](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:41)). |
| 16 | `exclusive=True` does not prevent overlapping updates | RESOLVED | Shared `UpdateService.begin/end` state is lock-guarded and tested with a held worker latch ([12-03-PLAN.md:278](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:278), [12-03-PLAN.md:304](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:304)). |
| 17 | Pnpm recovery trigger too broad | RESOLVED | `should_replay_node_globals()` is true only for `tool.id == "pnpm"` ([12-03-PLAN.md:158](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:158)). |
| 18 | Direct update skips postinstall | RESOLVED | A successful update re-dispatches the owning method’s hook, with hook failure retained as a warning ([12-03-PLAN.md:156](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:156)). This mirrors the current install behavior at [engine.py:122](/Users/ramon/git/personal/tools-installer/installer/engine.py:122). |
| 19 | TUI subprocess-output policy unresolved | RESOLVED | Production uses `run_captured`, showing an in-flight line and final result instead of child terminal output ([12-03-PLAN.md:291](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:291)). Current `run_captured()` routes through captured stdout/stderr at [run.py:64](/Users/ramon/git/personal/tools-installer/installer/run.py:64). |
| 20 | `brew outdated` cannot detect an uninstalled alternative | N/A / SUPERSEDED | Runtime drift detection was genuinely removed; the plan records non-delivery and its installed-only data limitation ([12-04-PLAN.md:27](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:27), [12-04-PLAN.md:48](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:48)). |
| 21 | No active-pnpm-versus-brew comparison | N/A / SUPERSEDED | No drift algorithm ships. The future requirement explicitly calls for an availability query and normalized active-versus-available comparison ([12-04-PLAN.md:55](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:55)). |
| 22 | Drift requirement says “surface,” but helper is unwired | N/A / SUPERSEDED | The helper is removed, and the deferral is recorded in requirement, roadmap, and project decision log ([12-04-PLAN.md:94](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:94)). |
| 23 | Drift `active_kind` inherits false ownership | N/A / SUPERSEDED | No `active_kind` path remains; future work must use `installer/ownership.py` ([12-04-PLAN.md:94](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:94)). |

No Cycle-1 finding that Cycle 2 marked fully resolved has regressed. The ownership, pnpm-current-version, and update-atomicity findings were already partial in Cycle 2 and remain partial.

### Other Cycle 2 findings

| Finding | Verdict | Current evidence |
|---|---|---|
| Independent-service cache test contradicted instance-local lock | RESOLVED | The guarantee and test now cover one production service with two worker threads; independent app processes are explicitly unsupported. Temp paths are unique per writer ([12-01-PLAN.md:98](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:98), [12-01-PLAN.md:146](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:146), [12-01-PLAN.md:275](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:275)). |
| Version comparator loses fourth components/prerelease distinctions | RESOLVED | `parse_status_version()` preserves the full numeric core and semver prerelease identifiers; tests cover `1.2.3.4` and `rc.1` versus `rc.2` ([12-01-PLAN.md:191](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:191), [12-01-PLAN.md:226](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:226)). |
| `ManagerOwnership` lacks UI/refusal evidence | RESOLVED | The model now includes candidates, active candidate/path, and `unknown_reason`; detail and refusal tests read them ([12-02-PLAN.md:152](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:152), [12-02-PLAN.md:339](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:339)). |
| Malformed uv outdated output becomes clean map | RESOLVED for that parser | Any unrecognized non-indented line makes the whole uv outdated report `None`; empty output alone means clean ([12-02-PLAN.md:243](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:243)). Ownership inventory parsing and other manager parsers remain separate gaps. |
| Replacement rollback ends at second `os.replace` | PARTIALLY RESOLVED | The new state machine adds remnant recovery, link recreation, validation, and tests ([12-03-PLAN.md:210](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:210)). It still promises restoration through the same failing symlink operation and lacks a channel for its cleanup warning. |
| `u` missing from canonical footer registry | RESOLVED | The three `VIEWS` rows and `CatalogScreen.BINDINGS` both gain `u` ([12-03-PLAN.md:288](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:288)). The current footer does derive its text from `View.actions` ([ui_common.py:191](/Users/ramon/git/personal/tools-installer/installer/ui_common.py:191)). The proposed bidirectional test is inconsistent with nested widget bindings, discussed below. |
| Refresh result can overwrite update result | RESOLVED for UI messages | Refresh messages carry an epoch captured before work, successful updates bump it, and the handler drops old-epoch messages ([12-01-PLAN.md:208](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:208), [12-03-PLAN.md:285](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:285)). A separate persistence race can resurrect the manager snapshot. |
| Naive, offset, and future timestamps unsafe | RESOLVED | `_parse_iso()` rejects naive values, normalizes offsets, and bounds future skew; all boundaries are tested ([12-01-PLAN.md:195](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:195), [12-01-PLAN.md:273](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:273)). |
| Drift guard test bans every name containing `drift` | RESOLVED | The guard now checks only the two abandoned identifiers and explicitly permits future correctly wired drift code ([12-04-PLAN.md:99](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:99), [12-04-PLAN.md:106](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:106)). |

## 3. New Issues Introduced By This Revision

- **HIGH — The explicit ownership algorithm contradicts its active-PATH safety test.** After failing to find an `active_candidate`, the next branch grants any lone candidate by elimination if inventories are readable ([12-02-PLAN.md:167](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:167)). Therefore one installer candidate plus active `/usr/bin/rg` returns installer-owned, even though the plan’s test requires `unknown` ([12-02-PLAN.md:192](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:192)). An attributable or absent active path must be a prerequisite for by-elimination; a contradictory live path must fail closed before that branch.

- **HIGH — Inventory schema failures can become mutation-grade negative evidence.** Brew inventory explicitly skips malformed lines, and uv inventory lacks an unrecognized-line failure state ([12-02-PLAN.md:148](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:148), [12-02-PLAN.md:149](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:149)). The reused pnpm parser also skips unrecognized project/group shapes and may return an empty tuple ([pnpm_globals.py:264](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:264), [pnpm_globals.py:287](/Users/ramon/git/personal/tools-installer/installer/pnpm_globals.py:287)). Downstream, non-`None` inventories count as complete negative evidence and may authorize mutation. All ownership inventory parsers need whole-report validation or an explicit completeness flag.

- **HIGH — A six-hour cached inventory is used as mutation authorization.** The manager snapshot includes ownership inventories, not only display versions, and fresh snapshots issue zero real queries ([12-02-PLAN.md:293](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:293), [12-02-PLAN.md:326](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:326)). The update action then consumes `ownership_of()` from that completed pass ([12-02-PLAN.md:312](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:312)). The threat model incorrectly says an external manager change can only make a row one version behind ([12-02-PLAN.md:387](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:387)); it can change which manager owns the tool. Display reports may be cached, but pressing `u` should revalidate the selected tool’s ownership with fresh manager evidence before mutation.

- **HIGH — Installer-owned script/app/tarball updates are unreachable, including the common script-installed pnpm case.** Plan 12-02 gives installer-owned script/tarball/app tools no latest version and `outdated=None` ([12-02-PLAN.md:302](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:302)). Plan 12-03 refuses to start an update unless `VersionStatus.outdated is True` ([12-03-PLAN.md:289](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:289)). Yet `perform_update()` contains installer-owned script/app/tarball branches ([12-03-PLAN.md:155](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:155)). Those branches are dead through the production UI. More importantly, pnpm’s registry entry commonly resolves to an official `script` method ([registry.toml:1881](/Users/ramon/git/personal/tools-installer/installer/registry.toml:1881), [registry.toml:1889](/Users/ramon/git/personal/tools-installer/installer/registry.toml:1889)), so its automatic pre-capture/replay mitigation cannot be triggered unless pnpm happens to be brew-owned.

- **MEDIUM — `invalidate()` can race with and lose to a pre-update refresh’s cache write.** Plan 12-01 places only the reload/merge/save section under the service lock, after slow resolution work ([12-01-PLAN.md:207](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:207)). Plan 12-02 claims that taking the same lock while dropping the snapshot prevents resurrection ([12-02-PLAN.md:317](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:317)). It does not: a refresh can query outside the lock, the update can invalidate, and then the old refresh can acquire the lock and persist its pre-update manager snapshot. The refresh must compare its starting epoch under the lock before saving and discard the write if the epoch changed.

- **MEDIUM — Brew and pnpm outdated parsers can turn malformed entries into false green rows.** Brew skips entries missing `name` or `current_version`, and treats a missing entire namespace key as an empty clean map; pnpm skips an entry lacking `latest` ([12-02-PLAN.md:241](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:241), [12-02-PLAN.md:242](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:242)). Downstream, absence from a non-`None` map means up to date ([12-02-PLAN.md:303](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:303)). Apply the uv parser’s fail-closed principle consistently: any malformed report entry or missing required top-level key should make the relevant manager map `None`.

- **MEDIUM — The rollback specification still overpromises.** On symlink recreation failure, rollback attempts to recreate the original link through the same operation that just failed ([12-03-PLAN.md:214](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:214)). Persistent permission/filesystem failures can make that retry fail too; the plan never captures the original symlink target for independent restoration. App replacement is described as a `mv`, while the plan’s must-have claims atomic `os.replace` ([12-03-PLAN.md:40](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:40), [12-03-PLAN.md:219](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:219)). Finally, cleanup failure is supposed to be recorded as a warning ([12-03-PLAN.md:217](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:217)), but `update_download()` returns only `bool` and `update_app()` returns `None`; no warning channel is specified.

- **MEDIUM — Post-update `VersionStatus` construction is undefined for manager-owned tools and casks.** The worker merely “re-probes” the tool and constructs a status ([12-03-PLAN.md:290](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:290)). Plan 12-02 says manager-owned status must come from ownership plus the authoritative manager report, and casks may have no command to probe ([12-02-PLAN.md:303](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:303)). The worker should explicitly call an ownership-aware `VersionRefreshService.refresh([tool])` after invalidation and use that result; a generic command re-probe cannot produce the promised cask or manager truth.

- **MEDIUM — Reusing private `_manager_name` conflicts with strict pyright.** Both ownership and update plans require reuse of `uninstall._manager_name` ([12-02-PLAN.md:129](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:129), [12-03-PLAN.md:135](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:135)), but neither plan modifies `installer/uninstall.py`, where the helper is private ([uninstall.py:130](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:130)). Strict pyright is enabled ([pyproject.toml:43](/Users/ramon/git/personal/tools-installer/pyproject.toml:43)); existing cross-module private use requires explicit `reportPrivateUsage` ignores ([policy.py:454](/Users/ramon/git/personal/tools-installer/installer/policy.py:454)). This project forbids silencing quality checks. Promote a public helper and include `uninstall.py` in the owning task.

- **LOW — Two planned counting/registry tests contradict current architecture.** `read_inventory()` has four `query` calls when brew exists—three brew calls plus `uv tool list`—and one separate `pnpm_packages()` call, yet its test demands five `query` calls ([12-02-PLAN.md:150](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:150), [12-02-PLAN.md:204](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:204)). Separately, the footer test requires keys such as `a` and `i` to have `CatalogScreen` bindings ([12-03-PLAN.md:301](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:301)), but those bindings belong to the nested `ToolBrowser` ([tool_browser.py:101](/Users/ramon/git/personal/tools-installer/installer/tool_browser.py:101)); current `CatalogScreen.BINDINGS` contains only hidden recommendation keys ([catalog_tui.py:155](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:155)). The drift test must inspect the effective parent-plus-widget binding set.

- **LOW — Reusing `_node` makes its existing documentation false.** The current comment says the smoke check fires “on the install path only” ([executors.py:432](/Users/ramon/git/personal/tools-installer/installer/executors.py:432)), but Plan 12-03 intentionally invokes `_node` for updates while excluding `executors.py` from its file list ([12-03-PLAN.md:154](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:154)). Update that comment when adopting the executor.

## 4. Per-Plan Assessment

### 12-01

**Summary:** Mostly implementation-ready. It correctly establishes full-output probing, a precision-preserving comparator, cache timestamp validation, visible staleness, retry backoff, production DI, and off-event-loop refresh.

**Strengths**

- The production route matches the current architecture: `_build_app()` owns `Platform`, `UnifiedApp` constructs the three catalogs, and the real screen lives in `catalog_tui.py` ([setup.py:205](/Users/ramon/git/personal/tools-installer/setup.py:205), [wizard_app.py:1453](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1453), [catalog_tui.py:135](/Users/ramon/git/personal/tools-installer/installer/catalog_tui.py:135)).
- It preserves the current feature-floor parser/probe contracts while adding separate status-oriented functions ([12-01-PLAN.md:189](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:189), [12-01-PLAN.md:191](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:191)).
- Cache concurrency claims now match the actual single-service topology ([12-01-PLAN.md:275](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:275)).

**Concerns**

- **LOW:** The plan’s epoch protects UI messages but not later manager-snapshot persistence; Plan 12-02 must add an epoch check before any cache merge/save, not merely when rendering ([12-01-PLAN.md:207](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-01-PLAN.md:207)).

**Suggestion:** Execute after adding a cache-write epoch precondition consumed by Plan 12-02.

### 12-02

**Summary:** The abstractions are appropriate, but this remains the unsafe plan. It supplies the authorization evidence for a no-confirmation mutating action, and the current decision procedure can still assert ownership after contradictory, malformed, or stale evidence.

**Strengths**

- Clear separation between installation preference and ownership ([12-02-PLAN.md:37](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:37)).
- Manager-wide batching, current-plus-latest result types, and zero-query fresh-session behavior are well specified ([12-02-PLAN.md:238](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:238), [12-02-PLAN.md:298](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:298)).
- Unknown ownership now has structured, user-readable evidence ([12-02-PLAN.md:152](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-02-PLAN.md:152)).

**Concerns**

- **HIGH:** The by-elimination branch ignores contradictory active PATH evidence.
- **HIGH:** Inventory parsers can silently convert schema drift into complete negative evidence.
- **HIGH:** Cached inventories are reused as mutation-grade authorization.
- **MEDIUM:** Pnpm still lacks authoritative current versions for packages absent from the outdated report.
- **MEDIUM:** `invalidate()` lacks a refresh-start epoch check before persistence.
- **MEDIUM:** Private `_manager_name` reuse conflicts with strict pyright.
- **LOW:** The planned query-count test expects five `query` calls where the described design makes four plus one separate pnpm call.

**Suggestions**

- Make ownership parsers return a report with `complete: bool`, or `None` on any unrecognized shape.
- Reject any live active path not attributable to the winning candidate before by-elimination.
- Treat cached ownership as display evidence only; perform a fresh selected-tool ownership check inside the update worker.
- Add an epoch compare-and-save guard around manager snapshot persistence.
- Promote `_manager_name` to a public shared helper.

### 12-03

**Summary:** The pnpm snapshot and node-executor fixes are genuine. The plan still cannot deliver all claimed update paths, and its filesystem/status handoff guarantees exceed its specified mechanisms.

**Strengths**

- Correct capture-mutate-replay ordering for pnpm self-update ([12-03-PLAN.md:278](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:278)).
- Correct reuse of `_node`, including co-install grouping, build permissions, pins, floors, and smoke checks ([12-03-PLAN.md:154](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:154), [executors.py:379](/Users/ramon/git/personal/tools-installer/installer/executors.py:379)).
- Explicit global in-flight protection, captured output, exception containment, postinstall handling, and footer registration ([12-03-PLAN.md:44](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:44), [12-03-PLAN.md:47](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-03-PLAN.md:47)).

**Concerns**

- **HIGH:** The UI’s `outdated is True` gate makes script/app/tarball branches unreachable and prevents script-installed pnpm from exercising the required automatic replay.
- **HIGH:** Mutation still inherits Plan 12-02’s unsafe cached/fail-open ownership.
- **MEDIUM:** Symlink rollback, app atomicity, and cleanup-warning propagation remain incomplete.
- **MEDIUM:** The post-update status path does not explicitly call the ownership-aware manager refresh.
- **LOW:** Footer-binding drift test inspects the wrong widget boundary.
- **LOW:** The SDKMAN “unsupported” branch appears unreachable because `Owner` has no SDKMAN value and the resolver creates no SDKMAN candidate.

**Suggestions**

- Permit an explicit update for installed, mutation-grade owner rows whose latest version is unknown, or add a special authoritative pnpm-self status source.
- Revalidate ownership inside the worker immediately before mutation.
- Make post-update status exactly `version_refresh.refresh([tool])[tool.id]` after invalidation.
- Give replacement helpers a typed result carrying cleanup warnings and independently back up symlink state.

### 12-04

**Summary:** Correct disposition. Deferring drift detection is honest and avoids dead production code.

**Strengths**

- It records non-delivery where requirements, roadmap, and project audits will find it ([12-04-PLAN.md:94](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:94)).
- It names the missing data source and active-versus-available comparison a future implementation needs ([12-04-PLAN.md:55](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:55)).
- The revised guard checks only the two abandoned orphan-helper names ([12-04-PLAN.md:99](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:99)).

**Concerns**

- **LOW:** The architecture substring test protects phrases, not truth. The task correctly instructs the writer to follow shipped code when code and plan disagree ([12-04-PLAN.md:152](/Users/ramon/git/personal/tools-installer/.planning/phases/12-version-aware-status-update-action/12-04-PLAN.md:152)); that instruction must be followed after any in-execution deviations.

**Suggestion:** Keep this plan, but write the architecture section only after the preceding plans and any safety deviations are complete.

## 5. Overall Risk Assessment

**Overall risk: HIGH.**

Three of the four Cycle-2 HIGH findings are resolved as originally framed: pnpm globals are captured before mutation, pnpm updates reuse `_node`, and manager subprocess results are cached. Ownership is only partially resolved.

The phase is **not ready to execute exactly as planned** because four remaining issues affect real no-confirmation mutations:

1. The ownership algorithm grants by-elimination ownership despite a contradictory active PATH.
2. Malformed and cached inventories can count as complete negative evidence.
3. Cached ownership is reused as mutation authorization for up to six hours.
4. Script-owned tools—including script-installed pnpm—cannot reach the update worker because their status is always `outdated=None`.

The update rollback and cache-invalidation races add material secondary risk.

**Verdict: revision required before execution.** Since the project will not dispatch Cycle 4, these should be handled as pre-execution edits or explicit in-execution deviations. At minimum, fix the four HIGH items before enabling the `u` action; the MEDIUM items should be fixed in the same pass because several are direct contradictions that will otherwise fail tests or invalidate the documented guarantees.




## Cap-Reached Disposition (Cycle 3, final direct fix pass)

This is cycle 3 of 3 — the hard cap per `.planning/ONESHOT-RULES.md` Rule 10. Cycle 3's own
verdict was **"Overall risk: HIGH... revision required before execution... Since the project
will not dispatch Cycle 4, these should be handled as pre-execution edits or explicit
in-execution deviations."** Per that cap, no cycle 4 review was dispatched. A full direct fix
pass edited `12-01-PLAN.md` through `12-04-PLAN.md` in place to address every real, fixable
finding cycle 3 raised, before this phase proceeds to execution. `cross_ai: true` was verified
present in all four plans' frontmatter both before and after this pass (`12-01-PLAN.md:25`,
`12-02-PLAN.md:27`, `12-03-PLAN.md:24`, `12-04-PLAN.md:15`).

### HIGH findings — all four fixed

1. **By-elimination ownership branch ignored a contradictory active PATH.** `12-02-PLAN.md`'s
   `resolve_ownership` decision procedure (Task 1) is reordered: a resolved `active_path` that is
   NOT attributable to the lone remaining candidate (e.g. an active `/usr/bin/rg` beside a stray
   installer artifact) now forces `owner="unknown"` in its own branch, evaluated and required to
   win BEFORE the by-elimination branch is ever reached. By-elimination is now reachable only when
   `active_path is None` — no live binary to contradict it — never as a fallback that can outrank
   contradictory live-PATH evidence. The plan's own required regression test ("Unattributable
   active binary", already present in the test list) now matches the corrected algorithm; the
   `<fails_when>` and acceptance-criteria blocks were extended with an explicit assertion that no
   code path returns `confidence="by-elimination"` while `active_path` is not `None`.
2. **Inventory parsers could manufacture "complete negative evidence" from malformed data.**
   `parse_brew_list_versions` and `parse_uv_tool_list` (`installer/ownership.py`, new in Plan
   12-02) now return `dict[str, str] | None`, matching `parse_uv_tool_outdated`'s existing
   fail-closed shape: any unrecognized line makes the WHOLE result `None`, not a partial map with
   the bad line dropped. `installer/pnpm_globals.py::_iter_dependencies`/`parse_global_packages`
   (reused, not reinvented) is changed to return `None` on a non-dict project or dependency-group
   entry instead of silently `continue`-ing past it, closing the same gap in the reused pnpm
   inventory reader. The two OUTDATED parsers (`parse_brew_outdated_json`,
   `parse_pnpm_outdated_json`, Plan 12-02 Task 2 — the cycle-3 MEDIUM half of this same finding)
   were fixed the same way: an entry missing a required field, or brew's `formulae`/`casks` key
   missing entirely, now yields `None` for the whole report rather than a map with that entry
   silently skipped. New fail-closed test cases and `<fails_when>`/acceptance-criteria language
   were added for all four parsers plus `installer/pnpm_globals.py`, and `installer/pnpm_globals.py`
   plus `tests/test_pnpm_globals.py` were added to Plan 12-02's `files_modified`.
3. **A stale cached inventory (up to 6h old) was the sole mutation authorization.** Plan 12-03's
   `UpdateService.run()` now performs a FRESH, single-tool, uncached ownership re-resolution
   (`reresolve_ownership`, a new DI seam calling `ownership.read_inventory`+`resolve_ownership` for
   one tool with no cache read) as step 0, before the pnpm pre-capture and before `perform_update`.
   The cached `VersionRefreshService.ownership_of()` result is now used ONLY for the UI's cheap
   initial gate and for rendering — never to authorize the mutation itself. A refusal at the fresh
   check produces the same `status="unknown-owner"` outcome shape the cached-ownership gate already
   produces, so the two refusal paths render identically. `setup.py::_build_app`'s wiring
   instructions, the test list, `<fails_when>`, and acceptance criteria were all extended with the
   fresh-vs-cached-disagreement regression test this fix requires.
4. **Script/app/tarball-owned tools (including script-installed pnpm) could never reach the update
   action.** Plan 12-03's `action_update_tool` gate is changed from "`outdated is not True` hides
   the action" to "`outdated is False` (CONFIRMED not outdated) hides the action" — `outdated=None`
   (staleness genuinely undeterminable, the status every installer-owned script/tarball/app tool
   carries per Plan 12-02) now falls through to the existing ownership/confidence check instead of
   being blocked outright. A mutation-grade-owned tool with unknown latest version is therefore
   reachable, with an honest "latest version cannot be determined" detail-line label (added to
   Plan 12-02's `_detail_text` behavior) rather than a false "up to date." The alternative — wiring
   a real version-comparison source for script/tarball/app kinds — was considered and rejected in
   the plan text itself: no general queryable version index exists for an arbitrary vendor install
   script, so a partial GitHub-tag-based comparison would help only a subset of cases while adding
   a second, narrower version-resolution path to maintain. "Reachable with an honest unknown label"
   was judged the better fit for this phase's existing design; the reasoning is recorded inline in
   `12-03-PLAN.md`'s `<behavior>` section per the reviewer's own instruction to document such
   choices. A script-installed-pnpm-shaped regression test was added to the test list,
   `<fails_when>`, and acceptance criteria.

### MEDIUM findings — all fixed in the same pass

5. **`invalidate()` cache-write race.** `VersionRefreshService.refresh()` (Plan 12-02) now
   captures `started_epoch` before its slow, unlocked manager subprocess calls, and re-checks the
   CURRENT epoch under the same lock immediately before persisting the manager snapshot, discarding
   its own write on a mismatch. This closes the gap the pre-cycle-3 text left open: merely "taking
   the same lock" serializes the write but does not prevent a stale write from happening at all. A
   dedicated race test (a `read_inventory`/`read_outdated` fake that calls `invalidate` as a side
   effect mid-refresh) and matching `<fails_when>`/acceptance-criteria language were added.
6. **Rollback overpromised.** Plan 12-03's update-safe executors (Task 2) now: (a) capture the
   original bin-dir/CLI symlink target with `os.readlink` at a new STEP -1, BEFORE any aside-move
   or swap, and every restoration path uses that captured value via `os.symlink`-into-temp plus
   `os.replace` — an independent primitive, never a retry of the identical `ln -sf`/shell operation
   that just failed; (b) app bundle replacement is specified as `os.replace` exclusively, removing
   the `mv` language that contradicted this same plan's `<must_haves>` claim of atomic `os.replace`;
   (c) `installer.download.UpdateExecResult`/`installer.apps.UpdateExecResult` (new typed
   dataclasses carrying `warnings: tuple[str, ...]`) replace the bare `bool`/`None` returns, giving
   a cleanup-step failure an actual channel to reach the user — threaded through to a new
   `UpdateOutcome.cleanup_warnings` field and surfaced in `CatalogScreen.on_tool_updated`'s status
   line. New tests, `<fails_when>` clauses, and acceptance criteria cover all three sub-fixes.
7. **Post-update status construction was underspecified for manager-owned tools and casks.** Plan
   12-03's `_update_tool_worker` now explicitly calls `version_refresh.refresh([target.tool])[tool_id]`
   — the same ownership-aware resolution path every other row's status comes from — instead of a
   generic local `--version` re-probe that cannot produce a manager's authoritative report or
   handle a cask with nothing on PATH to probe. A cask-fixture regression test (no probe-able
   command, still renders a real post-update version) was added along with matching acceptance
   criteria.
8. **Private `_manager_name` cross-module reuse violated strict pyright.** `installer/uninstall.py`'s
   `_manager_name` is renamed to public `manager_name` (signature unchanged); `installer/ownership.py`
   imports and calls the public name. `installer/uninstall.py` and `tests/test_uninstall.py` were
   added to Plan 12-02's `files_modified`, a direct test locking in the public export was added, and
   the acceptance criteria now require zero `reportPrivateUsage` suppressions anywhere in the diff.
9. **Two tests contradicted the design as specified.** The manager query-count test in Plan 12-02
   now asserts exactly FOUR `query()` calls plus one SEPARATE `pnpm_packages()` call (two
   independent counting fakes), replacing the single combined "five queries" assertion that did not
   match the described design. The footer-binding drift test in Plan 12-03 now builds the EFFECTIVE
   binding set as `CatalogScreen.BINDINGS` UNION `ToolBrowser.BINDINGS` (read from both classes, not
   hand-copied) before doing its bidirectional actions-vs-bindings comparison, replacing the
   `CatalogScreen.BINDINGS`-only comparison that would have failed on every pre-existing
   widget-level key (`space`/`enter`/`a`/`i`), not just a genuine drift.
10. **`_node`'s docstring/comment claimed "install path only."** Plan 12-03 Task 1 now includes an
    explicit action item to update `installer/executors.py::_node`'s smoke-check comment
    (`executors.py:432-439`) to say the check fires on either the install or the update path
    reached through the same executor, since this same plan deliberately reuses `_node` for
    pnpm-owned updates. `installer/executors.py` was added to Plan 12-03's `files_modified`, and a
    corresponding acceptance-criteria line was added. This is a documentation-only change — `_node`'s
    behavior is unmodified, consistent with this plan's own "no possibility of the two paths
    drifting apart" reuse design.

### LOW findings — left as accepted residual risk (not required for this pass)

Per the task's own scope, the LOW items (the SDKMAN-unreachable branch in Plan 12-03, and the
architecture-substring test note in Plan 12-04) were left unmodified. Both are genuinely low-risk:
the SDKMAN branch is unreachable only because `Owner` has no SDKMAN value and the resolver never
creates an SDKMAN candidate today — a correct, inert consequence of this phase's scope boundary
(`dnf`/`apt`/`pacman`/`rpm_ostree`/SDKMAN are out of scope for Phase 12 and resolve to `unknown` by
design), not a defect that could misfire; and Plan 12-04's architecture-substring test already
carries its own documented instruction to follow shipped code over plan text on any disagreement,
which is the correct posture for a test protecting phrasing rather than behavior. Neither was fixed
in this pass, consistent with the task's own instruction that LOW items are optional.

### Disposition

Every HIGH and MEDIUM finding from Cycle 3 — 10 items in total — was closed with a concrete,
specific plan-text fix in this pass: new decision-procedure ordering, new fail-closed parser
contracts, a new fresh-ownership-reresolution seam, a corrected UI gate, an epoch compare-and-save
guard, independent symlink-restoration and typed-warning-channel fixes, an ownership-aware
post-update status call, a public helper rename, two corrected tests, and one doc-comment fix —
none was silently dropped. The two LOW items were deliberately left as documented, low-risk residual
per the task's own scope, not overlooked. Per the 3-cycle cap (`.planning/ONESHOT-RULES.md` Rule
10), no cycle 4 review was dispatched — these four plan files are now ready for execution.
