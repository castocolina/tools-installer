# Audit G (UI and architecture): row health states, one screen family, honest install review

Date: 2026-10-13. Branch `gsd/phase-16-detection-version-and-ownership-must-answer-is-it-on-this-di` at `7861ced`. No code has changed since the 2026-10-11 audits (`git diff 9a1c663 HEAD -- installer setup.py tests` is empty), so their line numbers still hold.
Method: `ponytail:ponytail-audit` at ULTRA (map, look, rank; at each step ask "does it need to exist, is it already in the codebase"), scoped to the user's four new requirements R1–R4, plus Policies and Doctor. Read-only. The only file written in the repo is this report.

## Header

**What this repo does:** a Python + Textual TUI that installs about 90 developer and AI tools on macOS and Linux. It has six views: three install tiers (System, User, AI), Uninstall, Policies and Doctor. It also has a modal Execute screen that reviews and runs an install. `setup.py` wires everything; `installer/` holds the core and the screens.

**Load assumed:** one person, one process, one machine, 90 tools. Here "scale" means seconds of frozen UI or the same work done several times. It never means many users.

**Builds on, does not repeat:** `.planning/research/2026-10-11-ponytail-audit.md` (F1–F17, "Screen component architecture") and `.planning/research/2026-10-11-architecture-review-gpt-6.1-sol.md` (AR-01..AR-12). When a finding here is an instance of one of those, the report says so in one line.

**Read in full for this audit:** `installer/catalog_tui.py`; `installer/execute_screen.py`; `installer/deps.py`; `installer/engine.py`; `installer/post_install.py`; `installer/postinstall.py`; `installer/status.py`; `installer/tool_browser.py`; `installer/uninstall.py` (1–400); `installer/wizard_app.py` 60–280, 840–1600 (Uninstall), 1600–1730 (Policies head), 2400–3011 (`UnifiedApp`); `installer/version_status.py` 125–145 and 415–771 (`VersionRefreshService`); `installer/ownership.py` 275–313, 561–760 (`resolve_ownership`), 1194–1513 (labels and removal phrases); `installer/skill_lifecycle.py` 219–439; `installer/terminal_shell.py` 1–70 and 380–456; `installer/pnpm_globals.py` 143–262; `installer/doctor.py`; `installer/audit.py`; `installer/app.py` 100–195 and 346–360; `installer/prompt.py`; `installer/ui_common.py` 300–355; `setup.py` 755–1212 and 1426–1523; the ROADMAP backlog 999.1–999.11.

**Ran (scratch dir `/tmp/claude-1000/auditG/`, outside the repo, HOME redirected there for the probes):**
- `codegraph sync` (index up to date).
- `uv run pytest tests/test_execute_screen.py tests/test_catalog_tui.py tests/test_uninstall.py tests/test_tool_browser.py tests/test_deps.py -q`: all green.
- `probe_r4_execute.py`: nine headless Execute-screen cases (A–I) with fake install and update closures and a fake state service.
- `probe_r1_r3_rows.py`: real registry tools with fake ownership, version and skill evidence. It prints the catalog row and the Uninstall row for the same tool.
- `probe_r2_forks.py`: spies on `enter_view` and refresh calls, the screen stack, and the status line while navigating every view and closing an install run.
- `time_full_pass.py`: a real, read-only `VersionRefreshService.refresh` over the whole catalog on this host. The cache was in scratch and GitHub lookups were stubbed, so there was no network use.

**Not read:** the rest of `ownership.py` (`_collect_candidates`, native probes), `update.py` beyond `UpdateService.run` and its postinstall call, `systemd_daemon.py`, `shellrc.py`, `rcclean.py`, `guidance.py`, `render.py` beyond `render_audit`/`render_summary`, `PoliciesScreen` below line 1730, `DoctorScreen` beyond its lifecycle methods, and most of the 40k test lines. Not run: the full suite, `make validate`, macOS.

## Ranked findings

| # | Group | Title | Req | Backlog |
|---|-------|-------|-----|---------|
| 1 | Must fix | The Execute review misstates what will happen to an already-installed selection | R4 | 999.1 |
| 2 | Must fix | Uninstall gives a different, wrong instruction than the catalog for the same tool | R1, R3 | 999.6 / 999.8 |
| 3 | Should fix | Health facts the service already computes never reach a row | R1 | 999.6 |
| 4 | Should fix | Two "not configured" states nobody computes or repairs: terminal shell drift and agent-host hook coverage | R1, R4 | NEW (999.4, AR-10) |
| 5 | Should fix | Selecting an installed tool can never reinstall or reconfigure it, and one handoff promises a step that never runs | R4 | 999.1(b), 999.4 |
| 6 | Should fix | The three tiers are one class, but 10 forks in `UnifiedApp` still treat them (and the other views) differently | R2 | 999.6 (F10), 999.10 |
| 7 | Should fix | Each view has its own refresh-on-entry rule and its own status-on-leave rule | R2, R3 | 999.6, 999.10 |
| 8 | Should fix | The Execute "Pre-flight audit" table can only ever print "missing", and it calls a broken tool missing | R4 | 999.1 (lean) |
| 9 | Nice to have | The questionary category→tool chooser is unreachable from `setup.main` | — | NEW (999.10 lean) |

These are not repeated, only cited where they block a target: F1 (filename-proven "removable"), F2 (Execute not wired on 4 routes), F3/F8 (Policies stale), F4 (ghost selection in Uninstall), F9 (tier-scoped refresh), F10, AR-04 (raced statuses published). Smaller items left out: 2 (a skill pack's Ver cell says "no version" when versions do not apply; a broken *dragged* dependency counts as satisfied, so its dependent installs on top of it).

---

## R1 — every row marked: installed, missing, outdated, broken, unavailable, not configured, needs reinstall

### Current behavior

The catalog's Inst cell has three glyphs, ✓ / ○ / `!` (`catalog_tui.py:494-517`). `!` comes only from `ownership.broken` (`_BROKEN_MARK`, `:227-228`), which is the dangling pnpm shim (`status.py:98-121` `dangling_shim`, called at `ownership.py:595`). Outdated is the Ver column's yellow color (`:542-544`). Unavailable dims the row (`:619-634`). Everything else goes into the detail bar or nowhere.

Signals that exist today, and where each one ends up:

| Signal | Computed where | Catalog row | Uninstall row | Execute review |
|---|---|---|---|---|
| present | `status.is_installed` (`status.py:18-67`); skill packs override via host probes (`catalog_tui.py:479-492`) | ✓/○ | `installed_now` (`setup.py:859`), no skill override | `ExecuteInputs.installed` = `is_installed`, no skill override |
| broken (dangling pnpm shim) | `ownership.broken` (`ownership.py:595`) | `!` + detail "reinstall to repair" | **"managed elsewhere — remove with your package manager"** | REPAIR, but labelled "missing" / "Install" (finding 1) |
| outdated | `VersionStatus.outdated` (`version_status.py:131-138`) | Ver yellow | nothing | UPDATE |
| version unreadable / no comparison | `VersionStatus.installed is None` / `latest is None` | dim Ver text | nothing | **guessed UPDATE** (finding 1, case D) |
| shadowed (several copies) | `ownership.shadowed` | detail only | nothing | nothing |
| off-policy (another manager owns it) | `ownership.off_policy` | Owner suffix "≠ policy" | nothing | nothing |
| unknown owner | `ownership.owner == "unknown"` | blank Owner + reason in detail | **a registry guess that names a manager** (finding 2) | nothing |
| skill pack per-harness | `SkillHostStatus.hosts` (`skill_lifecycle.py:413-426`) | ✓ if any harness present; detail lists present and "not probed", **absent is never named** (`catalog_tui.py:687-708`) | "not installed" (F6) | INSTALL again (F6) |
| skill missing on a harness that is installed | inputs exist (`skill_lifecycle.present_harnesses`, `:234-242`) but nothing combines them | nothing | nothing | nothing |
| pnpm package listed, command gone | `NodeGlobalsReport.missing` (`pnpm_globals.py:172-173`), Doctor only | ○ missing | absent | INSTALL |
| smoke check failed | `NodeGlobalsReport.unhealthy` (`:178`), Doctor only | ✓ | managed | nothing |
| co-install group incomplete / split | `NodeGlobalsReport.incomplete_groups` / `split_groups`, Doctor only | ✓ | managed | nothing |
| zsh not the login shell | `status.is_default_shell` (`status.py:70-88`) | detail only | nothing | nothing |
| terminal emulator not pointed at zsh | **not computed** (sync only writes: `terminal_shell.py:383-456`) | nothing | nothing | nothing |
| postinstall hook missing for a later-installed agent host | **not computed** (`postinstall.py:29-46` checks hosts only at hook time) | nothing | nothing | nothing |
| policy files present but not running | `Policy.owned()` vs `Policy.is_active()` (`policy.py:157-163`) | — | used only for teardown | — (Policies shows on/off only) |

Probe evidence (`probe_r1_r3_rows.py`):
```
CATALOG  id | Inst | Ver                   | Owner             | detail
  jq       | ✓    | 1.7                   | Homebrew ≠ policy | ... also installed via dnf — live copy at /x/jq
  eza      | ✓    | 0.18 (source unknown) |                   | no manager claims /usr/local/bin/eza
  mmdc     | !    | ...                   |                   | shim present, package missing — select it and press enter to reinstall and repair
  ponytail | ✓    | no version            | claude-code       | installed in: claude-code | not probed: OpenCode      (codex=absent is not shown)
```

On this real host (`time_full_pass.py`, read-only): `broken: puppeteer`, `shadowed: rtk`, `off_policy: java, groovy, gradle, maven, mmdc`, `outdated: java, groovy, gradle, maven, vscode, mmdc, glab`. So 14 of 90 rows have a non-OK fact today. One of them gets a glyph.

### Gaps

- **Finding 3:** five computed facts never become a row state: the skill pack missing on an installed harness, pnpm "package listed, command gone", smoke-check failure, incomplete co-install group, and policy "owned but not running". Shadowed and off-policy are notes, not health. They correctly stay notes (see the precedence below), but the Uninstall and Execute screens drop them completely.
- **Finding 4:** two states nobody computes:
  - (a) **Terminal drift.** `sync_terminal_shells` reads the kitty, WezTerm and Konsole configs and writes only if the content changed (`_write_if_changed`, `terminal_shell.py:260`). A dry run that compares and does not write is enough to know "kitty is not pointed at zsh". Today the user cannot see this, and an already-installed kitty never re-syncs (999.4).
  - (b) **Hook coverage.** `rtk-register`, `codegraph-mcp-register` and `graphify-register` register only the agent hosts present at the moment the tool was installed (`postinstall.py:119-122`, `:223-225`, `:262-264`). Install rtk, then later install Codex: rtk is never registered for Codex. Nothing re-runs the hook: `run_postinstall` is called only on an install success (`engine.py:166-170`) and an update success (`update.py:309`). Probe case H: re-selecting a current rtk does nothing.
- Health is computed in three places with different inputs: catalog cells, `classify_tools`, and `_classify_selection`. This is F6. R1 makes it worse, because every new mark would be added three times.

### Target: one closed health state, computed once

**Closed set and precedence** (for a present tool, the first matching state wins; the others still go into `reasons`):

| Health | Glyph (color) | Set by evidence | What fixes it (→ disposition, R4) |
|---|---|---|---|
| `CHECKING` | `…` (dim) | the tool looks present, but no record exists for the current generation yet | wait. Enter on Execute waits too |
| `BROKEN` = needs reinstall | `!` (red) | `ownership.broken` (dangling shim) · pnpm lists the package but `which(cmd)` is None · smoke check failed (when Doctor has run) | REPAIR (reinstall via the same ladder, `repair=True`) |
| `MISCONFIGURED` = not configured correctly | `≈` (yellow) | skill pack absent on a harness that `present_harnesses` finds · terminal region drift for kitty/WezTerm/Konsole while zsh is present (new dry run) · co-install group incomplete | RECONFIGURE (run only the config step) |
| `OUTDATED` | `↑` (yellow) | `VersionStatus.outdated is True` | UPDATE (when the owner is mutation-grade), else SKIP_MANAGED |
| `OK` | `✓` (green) | present, none of the above | SKIP_CURRENT, or REINSTALL on request |
| `MISSING` | `○` (yellow) | not present, at least one method applies here | INSTALL |
| `UNAVAILABLE` | `–` (dim row) | not present, no method applies here | SKIP_UNAVAILABLE |

Rules:
- `present` means **any install evidence**: a command on PATH, `detect_path`, `bin_dir`, an app bundle, a manager package record, or a skill-pack host. So a pnpm package without its command is present and BROKEN, not MISSING. This is the AR-03 distinction: "present does not mean runnable".
- **Notes, not states:** shadowed, off-policy, unknown owner, version unreadable, stale cache, and "zsh is not the login shell". The installer cannot act on any of them, and on Bazzite chsh is absent by design. Each note becomes one sentence in `reasons`, plus the existing Owner suffix. Making them states would add marks that offer no action. That is the ultra cut.
- **Left out on purpose:** "bin dir not on PATH". The app's `PATH` is inherited from the shell that launched it (`status.py:26-32` says so), so this would flag a tool that is correctly wired in the rc files. Doctor already owns PATH. Revisit only if a per-rc-file check (not `os.environ`) is wanted.
- **Policies use the same vocabulary for their own rows:** ON `●`, OFF `○`, BLOCKED (missing hard prerequisite, read live) and DRIFT `≈` (`owned()` and not `is_active()`, e.g. timer files present but not running).

**Data model.** It lives in `installer/version_status.py`, next to `VersionStatus` and `SkillHostStatus`. That is the only module already above `ownership`, `status` and `skill_lifecycle` in the import graph, and its `VersionRefreshService.refresh` already loops over every tool with every input in hand.
```python
class Health(StrEnum):
    CHECKING = "checking"; BROKEN = "broken"; MISCONFIGURED = "misconfigured"
    OUTDATED = "outdated"; OK = "ok"; MISSING = "missing"; UNAVAILABLE = "unavailable"

@dataclass(frozen=True)
class ToolState:
    tool_id: str
    generation: int
    present: bool
    health: Health
    reasons: tuple[str, ...]            # one sentence per fact; detail bar, Uninstall, Execute all read it
    ownership: ManagerOwnership | None
    version: VersionStatus | None
    skill_hosts: Mapping[str, str] | None
    removable: tuple[Path, ...]          # only when ownership proves it is ours (F1); else ()

def tool_health(present, ownership, version, skill_hosts, present_harnesses, pnpm_globals, cmd_found,
                drift, available) -> tuple[Health, tuple[str, ...]]:   # pure; one parametrized test
```
`refresh()` builds `{id: ToolState}` and publishes it in **one swap** under the lock, tagged with the generation. A raced pass publishes nothing: no ownership and no statuses either, which closes AR-04 as a side effect. `state_of(id) -> ToolState | None` replaces `ownership_of`, `statuses`, `skill_status_of` and the screens' private copies. `None` renders as CHECKING.

**One renderer.** `health_cell(state) -> Text` and one `HEALTH_LEGEND` string, in `catalog_tui.py` beside `_LEGEND`. The catalog Inst column, the Uninstall rows and the Execute review table all use them. The legend's 3-line × 78-column budget (`catalog_tui.py:232-286`) must be rebalanced: "✓ ok · ↑ update · ≈ config · ! broken · ○ missing" is about 45 characters. It replaces "✓ installed · ○ missing", and the existing legend tests pin the budget.

---

## R2 — System / User / AI follow one reuse pattern

### Current behavior

All three tiers are one class, `CatalogScreen`, built in one comprehension (`wizard_app.py:2494-2507`). The class itself does not fork by tier. The **app** does. These forks remain after 9050446:

| # | Where | Fork |
|---|---|---|
| 1 | `wizard_app.py:2508-2511`, `:2589-2590` | the base tier is left out of `_views` and is never `install_screen`'d |
| 2 | `:2670-2674` | `get_default_screen` returns the System tier, so System is the stack root and the other two are pushed on top of it |
| 3 | `:2695-2706` | `show_view`: base → `enter_view()` after the pop; non-base → `enter_view()` **before** `push_screen` |
| 4 | `:2720-2726` | `_navigable` checks the base and `_views` separately |
| 5 | `:2738-2743` | `action_back` only goes "home" when `current_view != BASE_VIEW` |
| 6 | `:2661-2664`, `:2770` | `catalog` property and the link-mode fallback hard-wire the base |
| 7 | `:2687-2689` | only catalogs get `clear_transient()` on leave |
| 8 | `:2873-2875` | `_install_closed` re-enters **only the active tier** (F9) |
| 9 | `:2996-3000` | `OwnershipRefreshed` goes only to Uninstall, only when it is visible |
| 10 | `:2791`, `:2910` | `execute is None` branches: the catalog exits, and `_rederive_installed` does nothing (F2) |

There is also duplicated state: each tier keeps its own `_installed` copy (`catalog_tui.py:339`) and its own `_version_statuses` copy (`:349`). Execute reads the service's `statuses` instead (`execute_screen.py:511`). And because the tiers share one `_staged` set, a re-stamp is needed on resume (`catalog_tui.py:1022-1030`).

Probe (`probe_r2_forks.py`):
```
start      stack: [CatalogScreen(system)]                         log: refresh:system
-> user    stack: [CatalogScreen(system), CatalogScreen(user)]    log: enter:user:mounted=False, refresh:user
-> ai      stack: [CatalogScreen(system), CatalogScreen(ai)]      log: enter:ai:mounted=False, refresh:ai
-> system  stack: [CatalogScreen(system)]                         log: enter:system:mounted=True, refresh:system
status after leave+return: user-tier='' uninstall='uninstall warning'
install closed on user tier -> log: enter:user:mounted=True, refresh:user      (system and ai not refreshed)
```
Two facts follow. A first entry to User or AI calls `enter_view` on an unmounted screen, where it does nothing. The refresh only happens because `on_mount` duplicates it. An install from one tier refreshes only that tier.

### Gap

**Finding 6.** Whichever view comes first in `VIEWS` gets different lifecycle code. 9050446 was a bug in fork #3, and the fork structure that caused it is still in place.

### Target: what one component needs (smaller than 999.10's `RowsScreen`)

999.10 proposes a new `RowsScreen[T]` base class. At ultra level it is **not needed**. Once `ToolState` exists, every piece of shared behavior already has a home:

| Shared behavior | Home (existing class) | Size |
|---|---|---|
| Activation after mount | `UnifiedApp.show_view`: pop if a view is on top → `push_screen(view)` → `view.enter_view()`. A neutral root `Screen` (empty, never navigable) is the stack bottom. All six views are `install_screen`'d. Forks 1–6 disappear. | −40 lines |
| Re-read on entry and on background change | `AppScreen.enter_view()` default calls `self.state_refreshed()`; `AppScreen.state_refreshed()` default is a no-op. Catalog and Uninstall override it with `self._browser.reload(self._adapter())` from `state_of`. | +4 lines |
| One refresh owner | `UnifiedApp` runs one worker over the **full** catalog: on mount, after every mutation (install close, `u`, removal, policy toggle that installs), and on a view entry when the generation is dirty. On commit it calls `self.screen.state_refreshed()` when that is an `AppScreen`. Measured cost: 4.5–5.7 s for 90 tools on a worker thread, against 3.5 s for the System tier alone with cold managers. Affordable, and "checking…" covers the window. | −150 (F9) |
| Status cleared on leave | Move `clear_transient` from `CatalogScreen` up to `AppScreen` (default `self.status.clear()`). `show_view` calls it for every view it leaves. | ±5 |
| Selection pruned when a row stops being selectable | `ToolBrowser.reload` and `selected_ids` (F4, `tool_browser.py:215-218`, `:325-331`) | +3 |
| Same health marks | `health_cell` (R1) | +15 |

Deleted: the base/non-base branches; `UninstallScreen._pending_status` and `_set_status` (`wizard_app.py:943-952`, `:1172-1186`); the per-tier `_installed`/`_version_statuses` copies and `set_installed`; the three per-screen refresh workers and their generation counters; `OwnershipRefreshed`; `UninstallScreen._refresh_ownership_worker`; `UninstallInputs.invalidate/refresh`; `on_screen_resume`'s re-stamp (it is not needed once the browser reloads on every entry). Keep the generation/epoch check. AR-04 is right that worker cancellation does not replace it.

Keep three tier instances. The single-instance "tier as a tab" form from F10 changes the user's 6 number keys to 4. The user asked for one pattern, not one instance.

---

## R3 — Uninstall in the same family

### Current behavior

- **Order** (`wizard_app.py:876-881`, `_groups` `:1145-1159`): removable here → managed elsewhere → not installed → not available → environment (ban, PATH block, tweaks). This is close to the requested order. But "removable" is only "a file with the expected name exists" (F1), and the environment rows are proven ours by their markers yet come last.
- **Health marks:** none. Probe (`probe_r1_r3_rows.py`), same fake evidence as the catalog rows above:
```
[removable here   ] fd    via=userspace        removes=2 artifact(s)   (catalog: ↑ outdated, Owner "GitHub release")
[managed elsewhere] mmdc  via=package manager  detail=managed outside this installer — remove with your package manager   (catalog: ! broken, "reinstall to repair")
[managed elsewhere] eza   via=package manager  detail=managed by Homebrew — `brew uninstall eza`                        (catalog: owner blank, "no manager claims /usr/local/bin/eza")
[managed elsewhere] kitty via=own installer    detail=installed by its own installer — remove it with that installer's own uninstaller
[not installed    ] ponytail                    detail=not installed                                                        (catalog: ✓)
```
- **Refresh on entry:** `enter_view` → `_resync` re-runs the row predicate synchronously (`wizard_app.py:1238-1352`). It reads the ownership map but does not start a pass, so after any mutation it shows the registry fallback until a catalog pass lands. That catalog pass is the only thing that posts `OwnershipRefreshed`.
- **Selection:** a removed tool keeps its hidden mark (F4, code unchanged).

### Gaps

**Finding 2 (must fix).** On the one screen whose Enter deletes files, two rows tell the user something the catalog contradicts. Both come from `_managed_hint` (`uninstall.py:171-245`):
- (a) A dangling pnpm shim gets "remove with your package manager". But the package is gone. The right action is "reinstall from the catalog to repair; there is nothing for a manager to remove".
- (b) An unknown-owner tool gets the registry's first method as its owner ("managed by Homebrew — `brew uninstall eza`"). Ownership found no manager at all. Running that command fails, or removes a different copy.
- Also: the "Installed via" vocabulary differs between the screens ("userspace" here, "GitHub release" in the catalog). A skill pack is ✓ in the catalog and "not installed" here (F6).

**Finding 7.** Each view has its own rule:

| View | On entry | On background change | Status on leave |
|---|---|---|---|
| Catalog tier | starts a tier-only async pass | own worker message | cleared |
| Uninstall | synchronous predicate re-read, no pass | `OwnershipRefreshed`, only from a catalog pass | **kept** (probe) |
| Policies | **nothing** (F3) | daemon worker only | kept |
| Doctor | re-reads guard state, starts two workers | own messages | kept |

### Target

The Uninstall rows are a projection of `ToolState`. There is no second classifier:
1. **Removable here:** `state.removable` is non-empty (ownership proves it is ours, F1), followed by the environment levers (marker-proven, so also ours). These rows are selectable.
2. **Managed elsewhere:** present and not ours. The cell shows the shared Owner label. The detail shows `removal_hint(ownership)` if there is one, else `Tool.uninstall` (the registry's reviewed text, today parsed and never read, F11), else **"owner unknown — found at <path>; this installer did not place it"**. Never a registry guess. A BROKEN row adds "broken — reinstall it from the catalog to repair; nothing to remove here".
3. **Nothing to do:** MISSING and UNAVAILABLE in one group.

Every row carries `health_cell(state)` in a Health column (the same glyph as the catalog). Entry and background refresh follow the R2 rule. The selection rule is the shared `ToolBrowser` prune. Deleted: `classify_tools`, `ToolRow`, `OwnerHint`/`OwnerLabelHint`, `_manager_hint`, `_managed_hint` (`uninstall.py:100-339`), the three `setup.py` closures (`:807-868`), and `ownership._own_script_install` (`:1436-1444`), whose job becomes the `Tool.uninstall` fallback. `plan_uninstall` stays as the artifact formula (F7).

---

## R4 — an already-installed selection says what will happen to it

### Current behavior

There are five independent skip paths:
- `deps.resolve_dependencies` drops every installed tool from the order (`deps.py:109-113`, `satisfied_by_install`).
- `ExecuteScreen._classify_selection` splits the selection into repair / current / update (`execute_screen.py:499-529`).
- `_update_targets` treats "status is not `outdated is False`" as an update (`:531-545`).
- `engine.install_tool` returns `ALREADY_INSTALLED` unless `repair` (`engine.py:132-133`).
- `reapply_post_install` re-runs only the `post_install` table, never the `postinstall` hook (`engine.py:200-216`, `execute_screen.py:522-529`).

Probe (`probe_r4_execute.py`, nine cases with fake closures):

| Case | Selection | Review says | What runs | Summary says |
|---|---|---|---|---|
| A | installed, no state service wired | "Nothing to do. esc cancel". rg is **not listed** | nothing | Already: 0 |
| B | installed, current | "rg already current — nothing to do. **enter start** · esc cancel" | nothing | **Already: 0** |
| C | rg current + fd missing | "Install 1 tools? Already current: rg." | fd | Installed: 1 |
| D | installed, dnf-owned, no comparison | "**Update 1 tools?**" | update → "dnf-managed, this installer will not update it" | Updates: refusal |
| E | installed, broken shim | audit table: rg **"missing"**; "**Install 1 tools?**" | `install(repair=True)` | Installed: 1 |
| F | current + shadowed + off-policy | "already current — nothing to do" | nothing | — |
| G | zsh current (has `post_install`) | "zsh already current — **nothing to do**" | a handoff prints: "**A later installer step will apply that terminal-emulator configuration automatically**" | Already: 0 |
| H | rtk current (has `postinstall` hook) | "already current — nothing to do" | nothing (the hook never re-runs) | — |
| I | installed, state not landed yet | "**Update 1 tools?**" | "cannot update rg: ownership could not be resolved / Not attempted: rg" | — |

The CLI route (`--all` / `--categories`, `app.run_wizard` `:151-163`) has the same silent drop. Its audit table lists only what will be installed.

### Gaps

- **Finding 1 (must fix).** The review is the last thing the user reads before Enter, and in 6 of 9 cases it says something false or incomplete:
  - B: says "start" when nothing will start.
  - D, I: promise an update that cannot happen, or that is only a guess from a missing record.
  - E: calls a present broken tool "missing" and says "Install", not "repair".
  - G: says "nothing to do", then runs a handoff that promises a terminal step this flow never triggers. `_install_state_changed` only becomes true on `Summary.installed` (`wizard_app.py:2960`).
  - The summary then disagrees with the review ("Already: 0" right after "already current").
- **Finding 5.** There is no disposition that reinstalls a current tool (999.1(b): wezterm). There is none that reconfigures one either (H: rtk; 999.4: terminal sync). The only re-apply path covers one action table (`set_login_shell`).
- **Finding 8.** `render_audit(audit(self._ordered, installed_for_order))` (`execute_screen.py:492`) can only print "missing". `_ordered` never holds an installed tool, and `installed_for_order` returns False for repairs (`:476-477`). The "installed" branch (`render.py:55`) is dead in the TUI.

### Target: one plan with a closed set of dispositions

```python
class Disposition(StrEnum):         # review text = value; one per plan row
    INSTALL = "will install"
    REPAIR = "will repair (reinstall)"
    REINSTALL = "will reinstall"
    UPDATE = "will update"
    RECONFIGURE = "will reconfigure"
    SKIP_CURRENT = "already current — skipped (r: reinstall)"
    SKIP_MANAGED = "managed by {owner} — skipped"
    SKIP_UNAVAILABLE = "not available here — skipped"
    BLOCKED = "skipped — needs {dep}"
    SATISFIED = "already present"    # dragged dependency only
    CHECKING = "checking…"           # Enter waits

@dataclass(frozen=True)
class PlanRow:
    tool_id: str
    disposition: Disposition
    reason: str                      # from ToolState.reasons / owner label
    requested_by: str | None         # None = direct selection; else the dependent that dragged it in

def plan(selected, catalog, state_of, platform, *, reinstall: frozenset[str]) -> list[PlanRow]  # pure
```
`plan` lives in `installer/session.py`, beside `order_for_install`. It calls `resolve_dependencies` unchanged for ordering, which stays the only dependency mechanism, with `is_installed = lambda t: state_of(t).present and disposition is not REPAIR/REINSTALL`.

Decision table (health from R1 × owner × direct or dragged):

| Health | Owner | Direct | Dragged |
|---|---|---|---|
| MISSING | — | INSTALL | INSTALL (requested by X) |
| UNAVAILABLE | — | SKIP_UNAVAILABLE | BLOCKED for the dependent |
| BROKEN | any | REPAIR | REPAIR (fixes the "broken dep counts as satisfied" edge) |
| MISCONFIGURED | any | RECONFIGURE (names what: "register rtk for Codex", "point kitty at zsh", "install ponytail for Codex — manual") | SATISFIED |
| OUTDATED | mutation-grade (`MUTATION_GRADE`) | UPDATE | SATISFIED |
| OUTDATED | dnf / os-package / unknown | SKIP_MANAGED (fixes case D) | SATISFIED |
| OK | installer-owned | SKIP_CURRENT; the review key `r` flips it to REINSTALL | SATISFIED |
| OK | another manager | SKIP_MANAGED ("`brew reinstall jq` yourself") | SATISFIED |
| CHECKING | — | CHECKING: Execute starts one `refresh(selected + deps)` on its worker, then re-plans (fixes case I) | same |

**Decision for the user (default chosen here): a current tool is SKIPPED unless you press `r`.** Making REINSTALL the default would turn the catalog's `a` (select all) into "reinstall every installed tool in this tier". REINSTALL is offered only for installer-owned tools. Reinstalling over a brew or pnpm copy would create the shadowing that F1 and AR-01 warn about.

Execution maps onto existing code. No new executors:

| Disposition | Runs |
|---|---|
| INSTALL, REPAIR, REINSTALL | `run_installs`, with `_with_repair` generalized to a `force_ids` set (`execute_screen.py:239-276`) |
| UPDATE | `_run_updates` (unchanged) |
| RECONFIGURE | `reapply_post_install` + `run_postinstall(tool.postinstall, …)` (the hooks are idempotent: `postinstall.py:98-103`) + the terminal sync. The sync is triggered by "any plan row mutated or reconfigured", replacing `Summary.installed` (`wizard_app.py:2960`) |
| SKIP_*, SATISFIED, BLOCKED | listed and counted, never run |

The review renders one table: `health_cell` + tool + disposition + reason, with each dragged dependency indented under its dependent. It replaces `render_audit`, `_preflight_prompt`, `_refresh_progress`'s three lists, `_current` and `_reapply`. The summary counts plan outcomes (installed / repaired / reinstalled / updated / reconfigured / skipped / failed), so the review and the summary use the same words. After close, keep only failed, blocked and not-attempted selections (999.1). The CLI `run_wizard` prints the same table. `--yes` runs everything except REINSTALL.

Deleted: `_classify_selection`, `_update_targets`, `_preflight_prompt`, the Pre-flight audit table in the TUI, and `audit.py` plus `render_audit` once the CLI uses `plan` (about −90 lines). The `post_install.py` handoff sentence "A later installer step will apply…" becomes true, because RECONFIGURE triggers the sync.

---

## Policies and Doctor against the same family

- **Policies** (`wizard_app.py:1600-1730`): rows are built once in `on_mount`. There is no `enter_view` (F3), and prerequisites are frozen (F8). Family target: the R2 lifecycle (`enter_view` → re-read `is_active()` / `missing_requirements()`, repaint), and the R1 vocabulary for its rows (ON / OFF / BLOCKED / DRIFT). Keep its `DataTable` and the immediate space-to-toggle. Moving to `ToolBrowser` buys nothing that is needed (AR-08 agrees). AR-08's caution still applies: ON/OFF reads `is_active()`; `owned()` is only DRIFT evidence.
- **Doctor:** a text report, so it stays one. Family target: the same activation-after-push and status-on-leave rules, drop the hidden `a` (F17), and optionally publish its per-tool pnpm findings (missing, unhealthy, incomplete) into `ToolState.reasons` with BROKEN/MISCONFIGURED. Then the catalog row says what Doctor says. The cheap half ("package listed, command gone") is computed in the state pass itself from `inventory.pnpm_globals` and `which`. Smoke checks stay Doctor-only, because they run commands.

## Consolidated target

```
UnifiedApp
  root: neutral Screen; all six views install_screen'd and pushed the same way; enter_view after push
  state: VersionRefreshService → {id: ToolState} per generation (one swap); one full-catalog worker;
         StateRefreshed → self.screen.state_refreshed()
AppScreen (chrome, unchanged)  + enter_view() → state_refreshed();  clear_transient() on leave
 ├─ CatalogScreen ×3     ToolBrowser rows = ToolState (health_cell); Enter → ExecuteScreen (always wired, F2)
 ├─ UninstallScreen      ToolBrowser rows = ToolState projection: removable(proven)+env → managed elsewhere → nothing to do
 ├─ PoliciesScreen       DataTable; enter_view re-reads live state; ON/OFF/BLOCKED/DRIFT
 └─ DoctorScreen         text report; same lifecycle; optional findings → ToolState.reasons
ExecuteScreen (modal)    renders plan(selected) → disposition table; runs by disposition; summary = outcomes
ToolBrowser              + prune selection to selectable rows on reload (F4)
```
No `RowsScreen`, no new framework, no new dependency. New code is about +200 lines (ToolState/Health/tool_health about 90, plan/Disposition about 80, health_cell/legend about 15, lifecycle about 15). Deletions are about −700 lines, listed in R2–R4.

## Migration order

Each phase ships and tests on its own. Preconditions from the earlier audits come first: **F2** (Execute wired on every route) and **F4** (selection prune), because several of the tests below depend on them. **F1** must land before phase 4.

| Phase | Ships | Acceptance tests (per view, per direction) | Backlog |
|---|---|---|---|
| **1. ToolState + Health in the service** | `Health`, `ToolState`, `tool_health`, atomic per-generation publish, `state_of`; the catalog Inst cell reads it; legend rebalanced. Signals: present, broken shim, pnpm package-without-command, outdated, skill absent on a present harness | parametrized `tool_health` table (every evidence combination → state, precedence); a raced pass publishes neither ownership nor statuses (AR-04); catalog Inst glyph for each Health value on each tier (system/user/ai); legend fits 78×3 | 999.6 |
| **2. Install plan with dispositions** | `plan()`, the Execute disposition table, `force_ids`, the `r` reinstall key, the CHECKING gate, RECONFIGURE runs `post_install` + `postinstall` hook + terminal sync, summary from outcomes, retained selection; CLI `run_wizard` uses `plan` | probe cases A–I become tests with the new text; per tier (incl. base): select missing → "will install"; current → "skipped", `r` → "will reinstall"; broken → "will repair"; outdated brew → "will update"; outdated dnf → "managed by dnf — skipped"; dragged installed dep → "already present" under its dependent; `a` on an all-installed tier → nothing runs; summary words equal review words; zsh/kitty RECONFIGURE triggers the terminal sync | 999.1, 999.4 |
| **3. One lifecycle + one refresh owner (R2)** | neutral root, push-all, enter-after-push, app-level full-catalog worker, `state_refreshed`, status cleared on leave; delete forks 1–9, per-screen copies, workers, stash, `OwnershipRefreshed` | for each source view (system/user/ai `u` update, install close, Uninstall removal, Policies toggle) × each target view: the target shows the new state on next entry, and immediately when visible; first entry to every view keeps a status written during entry; every view's status clears on leave | 999.6 (F9, F10), 999.10 |
| **4. Uninstall as a ToolState projection (R3)** | rows from `state_of`; order removable(proven)+env → managed → nothing; Health column; `Tool.uninstall` fallback; "owner unknown" wording; delete `classify_tools` and the closures | broken shim row says "reinstall from the catalog to repair"; an unknown owner never names a manager; a uv-tool symlink is not removable (F1); a skill pack present shows its removal instructions; remove → row moves to "nothing to do", the selection is pruned, and every catalog tier shows ○ | 999.6, 999.8, 999.10 |
| **5. New MISCONFIGURED signals** | terminal-drift dry run (`sync_terminal_shells(write=False)` → drifted terminals); hook coverage: installing an agent host re-runs the hooks of present hook tools | kitty config without the marker region → kitty row ≈, select → RECONFIGURE writes the region (scratch HOME); install codex with rtk present → `rtk init --codex` runs once | NEW (AR-10, 999.4) |
| **6. Policies + Doctor in the family** | Policies `enter_view` re-read, live prerequisites, DRIFT; Doctor findings → `reasons` (optional); drop the hidden `a` | Uninstall removes the ban → Policies OFF on entry; install `watch` → the docker tweak is no longer blocked; timer owned-not-active → DRIFT; Doctor `a` is inert | 999.9 (F3, F8, F17) |
| **7. Lean** | delete the dead CLI chooser (finding 9), `audit.py`/`render_audit`, and the leftover generation Message classes, keeping epoch checks (AR-04) | existing CLI `--all`/`--categories` tests stay green | 999.10 |

Phase 2 can ship right after phase 1. It needs only `state_of`, and it fixes the most visible false text first. Phases 3 and 4 make the other screens agree.

## Findings in detail

1. **The Execute review misstates what will happen to an already-installed selection** (`execute_screen.py:471-529`, `:1008-1049`; `deps.py:109-113`)
   - **What this is:** the screen you read before pressing Enter to install.
   - **Problem:** probe cases B, D, E, G and I. "Nothing to do · enter start". "Update" for a dnf package. "Install" plus "missing" for a broken tool. "Nothing to do", followed by a handoff that promises a step that never runs. The summary says "Already: 0" after the review said "already current".
   - **Fix:** R4's `plan()` and its disposition table, computed from `ToolState`.
   - **If we skip it:** users cannot trust the review, and reinstall or repair requests silently do nothing.
2. **Uninstall gives a different, wrong instruction than the catalog** (`uninstall.py:171-245`, `setup.py:807-868`)
   - **What this is:** the "managed elsewhere" sentence on the screen that deletes files.
   - **Problem:** a dangling pnpm shim gets "remove with your package manager" (the catalog says reinstall to repair). An unknown-owner tool gets "managed by Homebrew — `brew uninstall eza`" (the catalog says no manager claims it). Both are guesses from the registry's first method.
   - **Fix:** use `ToolState`: `removal_hint`, else `Tool.uninstall`, else "owner unknown — found at <path>". Mark broken rows. Delete `_manager_hint`.
   - **If we skip it:** the user runs a removal command that fails or removes a different copy.
3. **Health facts the service already computes never reach a row** (`catalog_tui.py:494-517`, `:687-708`)
   - **What this is:** the Inst glyph.
   - **Problem:** the following are invisible or only in the detail bar: a skill pack absent on an installed harness (the absent harness is not even named); pnpm "package listed, command gone"; smoke failures; incomplete co-install groups (Doctor only); shadowed and off-policy on Uninstall and Execute.
   - **Fix:** R1's `Health` and `tool_health`, computed once in the refresh pass.
   - **If we skip it:** 999.6 stays open, and each new mark is added three times.
4. **Terminal drift and hook coverage are not computed** (`terminal_shell.py:383-456`, `postinstall.py:29-46`, `engine.py:166-170`)
   - **What this is:** two "not configured correctly" states.
   - **Problem:** kitty or WezTerm not pointed at zsh has no mark and no repair from the catalog. rtk, codegraph and graphify are never registered for an agent host installed after them.
   - **Fix:** a sync dry run (compare, do not write) for MISCONFIGURED. Re-run the hooks of present hook tools when an agent host is installed. Add the RECONFIGURE disposition.
   - **If we skip it:** silent half-configured tools; the 999.4 symptoms stay.
5. **No way to reinstall or reconfigure an installed tool** (`engine.py:132-133`, `:200-216`; `post_install.py:45-51`)
   - **Problem:** only `set_login_shell` re-applies. Its Bazzite text promises an automatic terminal step that the already-installed path never triggers (case G).
   - **Fix:** REINSTALL (installer-owned only, opt-in via `r`) and RECONFIGURE, both on the existing `repair=True` and reapply paths.
   - **If we skip it:** 999.1(b) and 999.4 stay as reported on the real host.
6. **Ten forks still treat the base tier and the other views differently** (table in R2)
   - **Problem:** a first entry calls `enter_view` before mount; an install refreshes only its own tier; Uninstall's status survives leaving while a catalog's does not (probe).
   - **Fix:** a neutral root, push-all, enter-after-push, one refresh owner.
   - **If we skip it:** the next lifecycle hook is added on one path and missed on the other, which is the same class as 9050446.
7. **Each view has its own refresh-on-entry and status-on-leave rule** (table in R3)
   - **Fix:** `AppScreen.enter_view → state_refreshed`, `clear_transient` on every leave.
   - **If we skip it:** F3-style stale screens recur per view.
8. **The Pre-flight audit table can only print "missing"** (`execute_screen.py:476-477`, `:492`; `render.py:55`)
   - **Problem:** dead branch; it labels a broken, present tool "missing".
   - **Fix:** replace it with the disposition table and delete the TUI call.
   - **If we skip it:** a wrong label on the review.
9. **The questionary chooser is unreachable** (`app.py:114-124`, `prompt.py:15-33`, `selection.py:33-80`, `setup.py:285-326`)
   - **Problem:** `main` calls `run_wizard` only with `--all` or `--categories`, so `select_catalog`, `select_categories`/`select_tools`, `category_choices`/`tool_choices` and `_ask_checkbox` run only in tests.
   - **Fix:** delete them, about −90 production lines plus their tests. Keep `confirm`.
   - **If we skip it:** dead code that looks like a second selection UI.

## Backlog mapping

| Item | Maps to |
|---|---|
| R1 health set, `ToolState`, one computation | 999.6 (extends F6 / AR-03 with the closed `Health` set and precedence) |
| R1 terminal drift, hook coverage | **NEW**. Suggest adding to 999.4 (terminal) and 999.1 (RECONFIGURE disposition) |
| R2 forks, one refresh owner, lifecycle defaults | 999.6 (F9, F10) and 999.10, **with a push back:** no `RowsScreen` class; lifecycle defaults in `AppScreen`, prune in `ToolBrowser` |
| R3 Uninstall projection, wording, order, prune | 999.10 (screen), 999.8 (F1 proof), 999.1 (F4), 999.6 (finding 2) |
| R4 dispositions, plan, review, summary, retained selection, CLI | 999.1 (this is its design), 999.4 (sync on RECONFIGURE) |
| Policies / Doctor in the family | 999.9 (F3, F8, F17) |
| Dead CLI chooser, dead audit table | **NEW**. Suggest adding to 999.10 lean-up |

## Verdict

Not healthy for R1–R4. The screens share chrome and a table widget, but not one state. The review screen is the clearest cost: in 6 of 9 probed cases it says something false or incomplete about an already-installed tool. Fix first: phase 1 (`ToolState` + `Health`), then phase 2 (install plan with dispositions). They are small, independent, and remove the most visible false text. Then phase 3 and phase 4 make every screen read the same state.

Lean: about −700 production lines and +200 possible (most of the −700 overlap the 2026-10-11 estimates; the R4/plan, dead chooser and audit-table deletions are new), −0 dependencies.

Not checked: macOS; the full suite and `make validate`; how `rtk`, `codegraph` and `graphify` behave when their hooks re-run on hosts that are already registered (their docstrings claim idempotency; not run here); how long the terminal-drift dry run takes (3 file reads, not measured); whether `present_harnesses` ids match `SkillHostStatus` keys for every harness; `PoliciesScreen` below line 1730 and `DoctorScreen` internals.
