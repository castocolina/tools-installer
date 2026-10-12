# Read-only architecture review

## Summary verdict

**The installer has useful shared infrastructure, but no authoritative model of a tool’s state on the host.** Its most serious problems are inconsistent authorization for destructive operations and independently maintained UI state. Moving screens into smaller files would improve readability, but would not fix those problems.

**What this repository does:** A Python/Textual application installs developer tools, manages shell configuration, reports host health, and removes selected artifacts on macOS and Linux. This review assumes one user, one application process, and approximately 90 catalog tools; responsiveness and preserving existing installations matter more than large-scale throughput.

The strongest existing boundaries are:

- Dependency ordering in `deps.py`, separate from runtime dependency-failure handling in `session.py`.
- Installation preference in `resolve.py`, separate from ownership attribution.
- Fresh ownership checks before updates.
- Staged, rollback-capable download/app updates.
- Shared navigation metadata, browser widgets, marker-block transformations, and atomic-write primitives.

The weakest boundaries are:

- Artifact discovery versus permission to delete an artifact.
- Host observations versus screen-specific interpretations.
- Refresh computation versus publication and persistence.
- Application capabilities versus launch-route wiring.
- Installation methods versus their complete detect/version/ownership/removal contract.

**Important correction to the supplied audit:** CI does **not** currently run only on pushes to `main`. `.github/workflows/ci.yml:3-6` also enables `pull_request`. The missing protection is branch-push coverage and evidence that the existing PR gate is consistently used and required.

### Review evidence

- Read backlog 999.1–999.10 and the ponytail audit before inspecting implementation.
- Ran the requested `codegraph sync .`; it reported already up to date.
- Inspected the requested subsystems and relevant tests.
- Confirmed that [CI run 38099159090](https://github.com/castocolina/tools-installer/actions/runs/38099159090), at `9a1c663`, failed its test step on both runners. Validation passed on both.
- Passed targeted tests in `test_status.py`, `test_resolve.py`, `test_uninstall.py`, `test_apps.py`, and `test_version_status.py`, with dependency synchronization, bytecode writes, and pytest caching disabled.
- A read-only registry/helper probe confirmed that macOS draw.io methods declare `cli_name="drawio"` but `cli_spec()` returns `"draw.io"`.

Repository status was unchanged between the beginning and end of the review. Passing existing tests does not establish the architectural contracts identified below.

## Architecture map (current)

| Area | Current responsibility | Boundary assessment |
|---|---|---|
| `model.py`, registry loading | Catalog records, enums, method parameters, validation, skill lifecycle schema | Validates some method kinds thoroughly, while others remain untyped parameter dictionaries. Catalog metadata and lifecycle semantics are unevenly represented. |
| `resolve.py`, `deps.py` | Method applicability/preference; dependency expansion and ordering | Good separation. Applicability, eventual availability, and observed ownership must remain distinct. Dynamic manager availability is incorrectly carried in startup `Platform`. |
| `status.py` | Filesystem/PATH/app-bundle presence and broken-shim observations | Presence is useful but incomplete for skills. It does not identify installations or authorize mutation. |
| `install_ownership.py`, `ownership.py` | Manager probes; aggregation and attribution of ownership evidence | The probe/aggregation split is defensible. However, ownership imports removal-related helpers, and refresh feeds it paths discovered by the uninstall planner. |
| `uninstall.py`, uninstall functions in `app.py` | Artifact discovery, row classification, deletion, policy teardown | Several layers are mixed. Discovery is treated as deletion authority; the mutation entry point receives paths rather than an evidenced installation identity. |
| `version_status.py`, `version_cache.py` | Ownership/version/skill refresh; persisted reports and TTLs | A broader host-state service is hidden behind a version-oriented name. Ownership, versions, and skills have different consistency rules. Persistence participates in publishing live state. |
| `engine.py`, executors, `update.py` | Installation ladder, method execution, updates and follow-ups | Update has stronger ownership and replacement guarantees than uninstall. Successful methods are reported by kind, not retained as durable provenance. |
| `postinstall.py`, `post_install.py`, `skill_lifecycle.py` | Automatic registration hooks, reviewed instruction handoffs, per-harness lifecycle | Different semantics legitimately exist. They are not represented through a common lifecycle capability contract. |
| `policy.py`, `terminal_shell.py` | Reversible environment changes, daemon policies, terminal configuration | Policy ownership and runtime activity are appropriately distinguishable, but UI snapshots and prerequisite snapshots go stale. Follow-up triggering is scattered. |
| `shellrc.py`, `rcclean.py`, `atomic.py` | Shell transformations, conservative classification, cleanup, safe replacement | Useful reusable foundations. Some writers bypass atomic replacement; cleanup applies indices from an earlier file revision. |
| `agent_policy.py` and supporting modules | Agent permission/guidance audit and application | No production route currently reaches this feature. It nevertheless remains coupled into `policy.py`. |
| `ui_common.py`, `tool_browser.py` | View registry, chrome, error boundary, table/detail/selection behavior | Strong reuse of presentation primitives. `run_live` catches failures; it is neither a transaction boundary nor a background scheduler. |
| `catalog_tui.py`, `wizard_app.py`, `execute_screen.py` | Catalog views, navigation, Doctor/Uninstall/Policies, execution | Screens retain domain decisions, independent state snapshots, refresh scheduling, and mutation coordination. |
| `setup.py` | Entry routes and collaborator construction | More than composition: it derives state, interprets ownership, chooses capabilities, and defines refresh behavior outside the principal type/coverage scope. |

The current dependency direction includes:

```text
registry → Tool/Method → resolver → dependency planner → installation engine
                      → presence → catalog snapshots
                      → uninstall planner → ownership refresh → version state
                                         → uninstall classification

setup.py → constructs services, classifiers, policies, and screens
screens  → schedule refreshes and coordinate mutation aftermath
```

The problematic arrow is **uninstall planner → ownership evidence**. Observation should not depend on a deletion planner’s interpretation of registry paths.

## Findings ranked

### AR-01 — Critical — Deletion authority is inferred from expected filenames

**Evidence:** `installer/uninstall.py:56-97,298-308`; `installer/app.py:548,595,649-675`; `installer/ownership.py:425-445`; `installer/registry.toml:2711-2803`.

**Impact:** A matching path makes a tool selectable for removal before ownership hints are consulted. This affects foreign `~/.local/bin` symlinks, shared draw.io artifacts, and app bundles installed by Homebrew into `~/Applications`. The ownership module explicitly acknowledges that the same app directory can belong to this installer or a cask; uninstall ignores that ambiguity.

**Target design:** Removal authorization belongs to a specific installation and its artifacts. An expected path is an observation, not proof that this installer wrote it. Both CLI and TUI must use the same removal planner and execution-time evidence check.

**Migration steps:**

1. Stop offering automatic deletion when artifact provenance is unproven.
2. Carry tool/installation identity and evidence through the removal decision, rather than only paths.
3. Record the successful method and exact created artifacts.
4. Revalidate artifact identity before removal.
5. Merge the duplicate draw.io package identity or explicitly model its shared artifact ownership.

**Backlog mapping:** **999.2, 999.8**.

**Ponytail comparison:** Agrees with F1’s diagnosis, but **disagrees that `owner="installer", confidence="direct"` is sufficient proof**. Directory-based attribution can label a foreign file “direct.” It also identifies the active copy, not necessarily every artifact proposed for deletion.

---

### AR-02 — High — Shell mutation has no consistently enforced safe-write boundary

**Evidence:** `installer/guards.py:551-564`; `installer/tweaks.py:293-308`; `installer/app.py:432-447`; `installer/atomic.py:34-58`.

**Impact:** Some shell writers truncate the live file despite an existing atomic helper. Cleanup previews one revision, waits for confirmation, then deletes those line indices from another revision. A concurrent edit can therefore remove unrelated user content.

Atomic replacement also does not, by itself, prevent two read-modify-write operations from overwriting each other’s changes.

**Target design:** All shell/config edits use one replacement primitive, preserve symlink behavior and permissions, and validate the revision on which a destructive transformation was based.

**Migration steps:**

1. Adopt the existing atomic helper at bypassing writers.
2. Bind cleanup approval to the previewed bytes; refuse or regenerate the preview if they changed.
3. Serialize overlapping in-process edits to the same configuration file.
4. Retain the existing conservative parser/refusal rules and consolidation recovery behavior.

**Backlog mapping:** **999.9**; **NEW deepening:** atomicity and stale-revision protection are separate requirements.

**Ponytail comparison:** Agrees with F5. Deepens the fix from “replace `write_text`” to a complete safe read-transform-replace contract.

---

### AR-03 — High — Host state is fragmented, including mutable facts treated as platform constants

**Evidence:** `installer/status.py:18-67`; `installer/catalog_tui.py:479-492`; `installer/uninstall.py:260-328`; `installer/execute_screen.py:499-545`; `setup.py:783,851-868`; `installer/platform.py:19-28,57-69`; `installer/resolve.py:66-70`; `installer/session.py:164-171`.

**Impact:** Catalog, Execute, Uninstall, policies, and ownership interpret separate observations. A present skill pack can appear installed in the catalog but absent in Uninstall and still receive installation handoffs.

A further state defect is `Platform.has_brew`: it is detected once and retained by execution and refresh services. On a fresh host, installing Homebrew and then selecting a brew-only tool such as `glab` in the same session still leaves method resolution using startup `has_brew=False`.

**Target design:** One host snapshot contains tool observations and live manager capabilities. Stable platform identity—OS family, architecture, immutability—is separate from mutable executable/manager availability.

**Migration steps:**

1. Aggregate presence, installation evidence, active executable, skill-host status, version observations, and action availability.
2. Replace consumer-specific presence overrides with projections of that snapshot.
3. Re-observe manager availability after relevant mutations.
4. Keep “unknown,” “absent,” “broken,” and “version unreadable” distinct.

**Backlog mapping:** **999.6**; **NEW:** frozen manager availability.

**Ponytail comparison:** Agrees with F6/F8’s root cause. Deepens the proposed `ToolState`: one owner and one boolean cannot adequately represent shadowed installations or per-harness skill presence.

---

### AR-04 — High — Epoch protection covers ownership but permits obsolete version publication

**Evidence:** `installer/version_status.py:503-529,578-589,677-770`; `installer/catalog_tui.py:424-469,956-998`; `installer/execute_screen.py:507-513`.

**Impact:** A refresh started before invalidation can finish after a newer pass. The raced branch correctly refuses ownership publication, but explicitly updates `_statuses` with obsolete results at `version_status.py:751`.

Execute can then read current-generation ownership beside an older `outdated=False` answer and classify the tool as already current. Screen-message epoch checks cannot repair a stale result already committed inside the shared service.

There is another boundary mismatch: `invalidate()` advances the epoch before saving the cache. If saving fails, the epoch has still changed; callers must not interpret the exception as “nothing was invalidated.”

**Target design:** Publish presence, ownership, versions, and action projections as one coherent generation. Cache persistence is a best-effort consequence of publication, not permission to publish live observations.

**Migration steps:**

1. Discard all obsolete local observations at the service publication boundary.
2. Replace the shared snapshot atomically under one synchronization rule.
3. Coalesce manager queries so overlapping requests share one inventory pass.
4. Make invalidation’s in-memory result explicit even when persistence fails.
5. Preserve separately reusable remote release metadata.

**Backlog mapping:** **999.6**; **NEW:** obsolete versions are still published internally.

**Ponytail comparison:** Agrees with F9, but this is more than temporarily blank owner cells. **Disagrees with F15’s suggestion that worker cancellation can replace generation checks:** cancellation and host-state supersession are different events.

---

### AR-05 — High — Cross-platform contracts are discovered too late by CI

**Evidence:** `.github/workflows/ci.yml:3-6,14-34`; `scripts/prune-tmp-linux.sh:101`; `tests/test_prune_tmp_linux_sh.py:31-47`; `tests/test_shellrc.py:2650-2679`; `tests/test_setup.py:2764-2785`; `tests/test_version_status.py:1263-1302`.

**Impact:** The failed CI run confirms several independent ambient assumptions:

| Failure | Structural cause | Prevention |
|---|---|---|
| `mapfile` on macOS | “bash exists” is treated as an interpreter-version contract | Declare the wrapper’s supported platform/interpreter; test the supported baseline explicitly. Test shared portable code separately. |
| Long paths wrapped by Rich | Domain assertions depend on terminal layout | Assert structured outcomes separately; use fixed-width rendering tests for presentation. |
| `time .` under Ubuntu `/usr/bin/sh` | `sh` is assumed to support Bash/zsh precommand semantics | Test named shell implementations and their actual capabilities; retain conservative parser refusal tests independently. |
| Linux daemon test fails on macOS | Synthetic Linux platform still consults real `systemctl` availability | Inject capability lookup as well as platform identity. |
| Race test fails without observing a committed window | Scheduler luck is a required assertion | Control the relevant interleaving with barriers/events; retain probabilistic stress tests outside the deterministic gate. |

**Target design:** Cross-platform behavior is a declared contract exercised before integration. Real interpreter tests complement synthetic OS/architecture/immutable-policy tests.

**Migration steps:**

1. Correct the five contract assumptions above.
2. Run CI on active phase branches or ensure early PRs exercise the existing PR trigger.
3. Require both OS checks before integration.
4. Add representative immutable-host policy scenarios; ordinary Ubuntu/macOS runners do not prove Bazzite behavior.

**Backlog mapping:** **999.7**.

**Ponytail comparison:** Agrees with the verification debt. **Contradicts the push-only claim:** PR triggering already exists. The audit does not establish that repository branch protection requires it.

---

### AR-06 — High — Application capabilities depend on launch route and test-compatible defaults

**Evidence:** `setup.py:755-784,1127-1163,1234-1251,1289-1296,1324-1331,1346-1356`; `installer/wizard_app.py:2512-2516,2790-2794,2903-2918`; `tests/test_wizard_app.py:7185-7190`; `pyproject.toml:41-53`.

**Impact:** All routes expose catalog navigation, but only the interactive setup route supplies Execute inputs. Catalog acceptance on other routes exits with selected IDs that the route discards. Installed-state re-derivation is also disabled when Execute is absent.

A test explicitly preserves this behavior. The composition root also contains substantial decision logic outside direct pyright and coverage scope.

**Target design:** Every production app exposing installation has the required execution collaborators. If an application genuinely lacks a capability, its view/action availability must express that explicitly.

**Migration steps:**

1. Build one complete production application context for all unified-app routes.
2. Separate installed-state observation from the presence of an execution adapter.
3. Move classification and planning decisions into typed `installer/` modules.
4. Keep `setup.py` focused on argv, terminal IO, environment acquisition, and construction.
5. Replace the test preserving silent exit with a route-level behavior contract.

**Backlog mapping:** **999.9, 999.10**.

**Ponytail comparison:** Agrees with F2/F12. Moving `_build_app` alone is insufficient if it merely relocates the same classifiers and optional capability defaults.

---

### AR-07 — Medium — Method kinds describe installation more reliably than lifecycle behavior

**Evidence:** `installer/model.py:238-243,654-756`; `installer/resolve.py:13-28,39-78`; `installer/engine.py:71-92`; `installer/uninstall.py:73-96`; `installer/download.py:138-149`; `installer/apps.py:47-65`; `installer/registry.toml:2266-2279,2740-2754`.

**Impact:** Adding or extending a method requires coordinated knowledge in validation, resolution, installation, detection, ownership, versioning, updating, and removal.

Two concrete manifestations:

- Sublime installation honors `bin_name="subl"`; removal derives `"sublime_text"` and misses the actual opt directory.
- draw.io declares `cli_name="drawio"`; app CLI derivation ignores it and returns `"draw.io"`. The read-only probe confirmed this mismatch.

Unknown parameters can remain accepted data with no implementing consumer.

**Target design:** A closed method-kind contract owns validation, applicability, artifact layout, observation capabilities, and supported lifecycle operations. Unsupported operations are explicit.

**Migration steps:**

1. Reject unsupported parameters and validate artifact specifications at registry load.
2. Share artifact-layout derivation across install/update/observe/remove.
3. Give methods stable identity for successful-method provenance.
4. Derive manager removal from manager/package identity.
5. Add explicit reviewed removal recipes only where the backend cannot derive them.

**Backlog mapping:** **999.3, 999.8**; **NEW:** ignored `cli_name`.

**Ponytail comparison:** Agrees with F7, but **narrows 999.3’s premise**: OS/architecture splitting already works, as kitty and Sublime demonstrate. The gaps are unsupported payload formats and incomplete lifecycle contracts, not an inability to declare platform variants.

---

### AR-08 — Medium — Shared screen chrome does not provide a shared lifecycle

**Evidence:** `installer/ui_common.py:321-355`; `installer/wizard_app.py:1630-1640,2025-2096,2494-2511,2670-2706`; `installer/policy.py:121-164,441-454`; `installer/uninstall.py:387-398`.

**Impact:** System is the default/root screen; User/AI and other views are pushed screens. Entry timing differs, and some refresh hooks run before mounting.

Policies retains startup activity and prerequisite snapshots. After Uninstall removes a policy, the next Policies toggle can choose the wrong operation. After installing a prerequisite, a tweak can remain blocked.

**Target design:** Uniform view activation after mounting, shared state notifications, and reusable row/detail presentation. Policy rows expose live activity, owned footprint, and requirements as separate facts.

**Migration steps:**

1. Give every top-level view the same activation lifecycle.
2. Re-observe policy state on entry and after relevant mutations.
3. Use live prerequisite lookup.
4. Extract row-screen behavior after domain state is unified.
5. Run blocking removal and policy operations away from the event loop.

**Backlog mapping:** **999.6, 999.9, 999.10**.

**Ponytail comparison:** Agrees with F3/F8/F10/F16. **Disagrees with reusing `policy_owned()` as Policies’ ON/OFF predicate:** a stopped daemon can retain owned files. Also, not every existing policy mutation is threaded; `wizard_app.py:2059` executes non-daemon policies synchronously.

---

### AR-09 — Medium — Selection is a set of IDs, not a reviewed action plan

**Evidence:** `installer/tool_browser.py:204-218,325-334`; `installer/wizard_app.py:1419-1430,1458-1476,2796-2797`; `installer/execute_screen.py:471-488`; `installer/deps.py:109-113`.

**Impact:** Uninstall selections survive when rows become non-selectable, producing misleading destructive confirmations and removal counts. Install completion clears all staged IDs, including failed or unattempted work. Already-satisfied selections can disappear from dependency output without a complete review disposition.

**Target design:** Keep user selection separate from the derived action plan. Each direct selection receives a disposition; dragged dependencies retain their requesting relationship; outcomes determine retained selection.

**Migration steps:**

1. Prune non-actionable removal selections and revalidate before confirmation/execution.
2. Represent install/update/current/manual/unavailable/blocked dispositions explicitly.
3. Preserve failed, cancelled, and unresolved direct selections.
4. Clear successful or satisfied selections using outcomes.
5. Count executed outcomes rather than selected IDs.

**Backlog mapping:** **999.1**.

**Ponytail comparison:** Agrees with F4. A generic browser rule is useful, but cannot implement the entire install lifecycle: explicitly selecting a current tool may legitimately request repair or configuration reconciliation.

---

### AR-10 — Medium — Configuration follow-ups are triggered by incidental execution outcomes

**Evidence:** `installer/engine.py:124-126,162-182`; `installer/post_install.py:17-26`; `installer/update.py:488-499`; `installer/wizard_app.py:2842-2859`; `installer/terminal_shell.py:383-445`.

**Impact:** Terminal synchronization runs after successful installation changes, but not an already-present terminal selection. kitty’s configured shell and WezTerm’s program can change without aligning inherited `SHELL`.

Automatic registration, reviewed handoffs, and configuration reconciliation have different semantics, but their trigger rules are spread across engine, update service, application callbacks, and policies.

**Target design:** Explicit lifecycle outcomes distinguish acquisition, update, repair, manual handoff, and requested configuration reconciliation. One application workflow determines which follow-ups run.

**Migration steps:**

1. Define when selecting an existing tool requests reconciliation.
2. Route that disposition through the same terminal synchronizer.
3. Resolve the `SHELL` contract for terminal-launched sessions.
4. Preserve the distinction between automatic hooks and reviewed instructions.
5. Report follow-up failures separately from successful primary mutations.

**Backlog mapping:** **999.4, 999.1**.

**Ponytail comparison:** Deepens F7/F8’s broader lifecycle diagnosis. The shared terminal implementation already exists; its invocation contract is the missing piece.

---

### AR-11 — Medium — Tests sometimes freeze implementation shape instead of enforcing contracts

**Evidence:** `tests/test_setup.py:2922-2926`; `tests/test_version_status.py:1088-1128`; `tests/test_wizard_app.py:7185-7190`; `tests/test_registry.py:1123-1131,1513-1524`; `tests/conftest.py:40-62`.

**Impact:** Source-count assertions prevent moving ownership wiring into a shared collaborator. Private-map assertions prescribe a particular storage structure. Registry prose tests require historical wording even after capabilities change. Meanwhile, a behavioral test preserves the route-dependent silent exit.

The CI run reached approximately 96% coverage while these architectural failures remained. Coverage measures execution, not agreement between subsystems.

**Target design:** Test public domain contracts, actual filesystem outcomes, and cross-view state transitions. Use structural tests for architectural prohibitions, not to prescribe incidental representations.

**Migration steps:**

1. Replace source-count checks with injected-probe behavior tests.
2. Verify stale-result rejection through controlled interleavings and public snapshot reads.
3. Replace catalog counts/history wording with meaningful schema and platform capability invariants.
4. Exercise install/update/uninstall → every tier, Uninstall → Policies, and all entry routes.
5. Inject host paths and capabilities; the real-home fingerprint is a useful backstop, not primary isolation.

**Backlog mapping:** **999.6, 999.7, 999.10**.

**Ponytail comparison:** Agrees with the warning in 999.10. Qualifies it: private access is not automatically bad; preserving a safety invariant matters more than banning underscores. The contract must survive a sound storage redesign.

---

### AR-12 — Low — Unreachable policy code and aspirational metadata enlarge the apparent architecture

**Evidence:** `installer/policy.py:167-264`; `installer/agent_policy.py:215-262`; `installer/agent_env.py:10-63`; `installer/install_ownership.py:83-89`; `installer/model.py:316-322,825-835`; `setup.py:971-988`.

**Impact:** Agent-environment auditing has tests and production modules, but no reachable application route. `Tool.source`, `owner`, and `uninstall` suggest lifecycle capabilities that consumers do not implement. The managed-download probe invokes a command with no implementation in this repository.

This makes the supported architecture harder to distinguish from preserved or incomplete work.

**Target design:** Retain reachable capabilities and metadata with explicit consumers. Removal guidance belongs in the eventual lifecycle contract; executable provenance comes from real observations or receipts.

**Migration steps:**

1. Remove the unreachable agent-policy feature unless there is an explicit decision to expose it.
2. Replace the fictitious managed-download probe with actual receipt observation.
3. Adopt useful removal metadata in the shared model or remove redundant fields.
4. Keep historical rationale in planning documents rather than execution contracts.

**Backlog mapping:** **999.10**, with **999.2/999.8** providing the eventual provenance/removal consumers.

**Ponytail comparison:** Agrees with F11. Does not endorse blanket deletion of comments or every custom Message class; both can carry meaningful safety semantics.

## Proposed target architecture

### 1. Domain model

Use one read model for host observations, with explicit uncertainty. It should contain:

| Record | Required information |
|---|---|
| **Host snapshot** | Generation, stable platform identity, observed manager capabilities, tool states, policy states |
| **Tool state** | Presence, broken state, observed installations, active executable/installation, per-harness skill state, version observations, permitted action plans and refusal reasons |
| **Installation observation** | Manager/backend, package identity, actual method when known, artifacts, evidence and its freshness |
| **Policy state** | Owned footprint, runtime/config activity, missing prerequisites, diagnostics |
| **Plan row** | Direct selection or dragged dependency, requested operation, disposition, blocking reason, eventual outcome |

These can remain ordinary dataclasses and mappings. They do not require a database or a generic event framework.

The essential distinctions are:

- **Present does not mean runnable.**
- **Runnable does not prove installer ownership.**
- **Active-copy ownership does not authorize deleting every matching artifact.**
- **No readable version does not mean absent.**
- **Owned policy files do not mean the daemon is running.**
- **Not installable here does not mean an existing installation cannot be observed.**

Keep `deps.py` pure. Its callbacks read the snapshot; it remains the sole dependency-ordering mechanism. Keep fresh authorization at mutation time, following `UpdateService.run`’s existing pattern.

### 2. Registry schema and method contracts

Keep a declarative registry and closed code-owned backends. Make each method self-describing through a **single method-kind contract**, rather than independent switches in every consumer.

A method needs:

- Stable identity.
- Existing OS/architecture scope and relevant platform restrictions.
- Validated, kind-specific parameters.
- Source identity: manager package, vendor URL, or release repository/asset.
- Payload/layout specification where applicable.
- Derived lifecycle capabilities.
- An explicit reviewed removal recipe only when derivation is impossible.

| Method family | Lifecycle derivation |
|---|---|
| Manager methods | Package inventory, manager version source, supported update/remove operation; native mutation may remain manual or refused |
| Download/app methods | One artifact-layout calculation shared by installation, observation, update, receipts, and removal |
| Vendor scripts | Reviewed detection and removal contract; do not infer an arbitrary script’s footprint |
| Skill packs | Per-harness observations and existing manual/closed-operation lifecycle |
| Host setup | Reviewed handoff with explicitly unsupported automatic operations |

Do not duplicate manager removal commands in every registry entry. Do not allow arbitrary shell commands as a shortcut around reviewed backends.

For platform artifacts, preserve the existing ability to declare separate methods. Normalize source and payload/layout concepts where it reduces duplication. Add a missing payload format such as DMG only when a researched catalog requirement needs it.

Receipts record what the successful method actually created. A method’s declared potential paths are not receipts.

### 3. Module boundaries

A practical dependency direction is:

```text
model/schema + platform identity
             ↓
method contracts + artifact layout
             ↓
host observations + ownership evidence
             ↓
immutable host snapshot + action planning
             ↓
install / update / uninstall application workflows
             ↓
CLI and Textual adapters
```

- `version_cache.py` persists observations; it does not decide action eligibility.
- `ownership.py` consumes evidence, not an uninstall plan.
- `uninstall.py` consumes evidenced installations and produces/removes an authorized plan.
- `postinstall.py`, reviewed actions, and terminal synchronization retain their different semantics.
- `setup.py` acquires real dependencies and constructs the application.
- Screens format state and submit intentions; they do not reconstruct domain truth.

### 4. Screen hierarchy

Preserve the six top-level views and their current navigation model from the user’s perspective:

```text
UnifiedApp
├─ shared application context and state coordinator
├─ neutral root
├─ CatalogScreen(tier=system)
├─ CatalogScreen(tier=user)
├─ CatalogScreen(tier=ai)
├─ UninstallScreen
├─ PoliciesScreen
└─ DoctorScreen

Shared presentation
├─ AppScreen: navigation, badge, status, footer, activation
├─ row/detail screen behavior
│  ├─ Catalog
│  ├─ Uninstall
│  └─ Policies: immediate activation rather than staged selection
└─ Doctor: structured report presentation

Modals
├─ ExecuteScreen
├─ confirmation
└─ choice/picker
```

All three catalogs already use one component class. The needed change is uniform lifecycle and shared state, not necessarily changing six navigation destinations into four.

Extract shared row behavior after the state model exists. Doctor need not pretend to be a table, and Policies need not acquire staged-selection semantics merely to reuse rendering.

### 5. Refresh model

Use one application-owned coordinator:

1. Publish cheap local presence/capability observations without waiting for remote versions.
2. Coalesce batched manager queries.
3. Compute ownership/version/skill projections against an identified generation.
4. Reject superseded observations before shared publication.
5. Publish one snapshot notification; screens read the same snapshot.
6. Persist cache results separately, reporting persistence failures without suppressing live truth.

Retain the existing distinct TTLs for remote release metadata and manager reports. A full-catalog **local** pass does not require fetching every remote version again.

After install, update, removal, or relevant policy changes, invalidate affected observations. A mutation attempt can partially change disk even when its final outcome is failure, so refresh eligibility should not depend solely on a success label.

Worker cancellation remains useful for resource management. Generations remain necessary for correctness.

### Backlog coverage

| Backlog | Architectural treatment |
|---|---|
| **999.1** | AR-09/AR-10: explicit dispositions, outcomes, retained selections, reconciliation |
| **999.2** | AR-01/AR-12: successful-method receipts and artifact-specific authority |
| **999.3** | AR-07: existing platform variants plus validated payload/lifecycle contracts |
| **999.4** | AR-10: terminal environment and explicit reconciliation |
| **999.5** | Process follow-up: evaluate the onboarding skill against implemented contracts; a checklist cannot supply missing backend capabilities |
| **999.6** | AR-03/AR-04/AR-08/AR-11: shared state, coherent refresh, transition contracts |
| **999.7** | AR-05/AR-11: deterministic platform tests and pre-integration CI |
| **999.8** | AR-01/AR-07: actual-method removal with provenance |
| **999.9** | AR-02/AR-06/AR-08: safe writes, complete route wiring, live policy state |
| **999.10** | AR-06/AR-08/AR-11/AR-12: typed composition, shared lifecycle, contract tests, unreachable-code removal |

## Fix-first order

1. **Close destructive gaps:** stop filename-based deletion authority; enforce atomic shell writes and preview-revision checks.
2. **Restore the cross-platform gate:** correct interpreter, rendering, capability-injection, and race-test assumptions; exercise both runners before integration.
3. **Fix immediate workflow failures:** complete Execute wiring on every unified-app route, live policy state/prerequisites, and removal-selection pruning.
4. **Correct shared publication:** prevent superseded version results from entering the service; separate in-memory invalidation from persistence success.
5. **Introduce shared host state:** include mutable manager availability, per-harness presence, and multiple observed installations.
6. **Unify method lifecycle contracts and receipts:** share artifact layout, validate parameters, and select removal from the actual installation.
7. **Normalize screen lifecycle and selection plans:** then extract reusable row behavior and simplify refresh plumbing.
8. **Finish lifecycle/process cleanup:** terminal reconciliation, unreachable agent-policy code, misleading metadata, and onboarding-skill evaluation.

**Not checked:** live macOS/Bazzite installation or removal, upstream artifact availability, full local quality gates, or native end-to-end UI behavior.  
**Remaining risk:** the reviewed code can still remove foreign artifacts and truncate user shell configuration; this review changed neither behavior.
