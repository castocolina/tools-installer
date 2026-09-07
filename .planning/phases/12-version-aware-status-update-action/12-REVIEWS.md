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


