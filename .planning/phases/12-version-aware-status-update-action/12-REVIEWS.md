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
