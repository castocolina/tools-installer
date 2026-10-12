# Ponytail audit (ULTRA): screens, classifiers, refresh, uninstall

Date: 2026-10-11. Branch `gsd/phase-16-detection-version-and-ownership-must-answer-is-it-on-this-di` at `9a1c663`.
Method: `ponytail:ponytail-audit` at ULTRA level (does it need to exist → already in the codebase → stdlib/platform → dependency → one line → minimum). Read-only: no code, test, config or planning file was changed.

## Header

**What this repo does:** a Python + Textual TUI that installs a curated catalog of about 90 dev and AI tools on macOS and Linux (download, brew, native, script, pnpm, uv, SDKMAN, skill packs), wires PATH into your shell rc files, audits PATH (Doctor), toggles shell policies (Policies) and removes what it installed (Uninstall). `setup.py` is the composition root; `installer/` is the core and the screens.

**Load assumed:** one person, one process, one machine, about 90 catalog tools. "Scale" below means a few seconds of frozen UI, repeated subprocesses, or work done 3 times, never many users.

**What I read in full:** `installer/wizard_app.py`, `installer/catalog_tui.py`, `installer/ui_common.py`, `installer/tool_browser.py`, `installer/uninstall.py`, `installer/status.py`, `installer/install_ownership.py`, `setup.py` lines 755-1523 (`_build_app` and every entry route), `installer/version_status.py` `VersionRefreshService`, `ownership.py` `resolve_ownership` (540-760), `execute_screen.py` modals and `_classify_selection`, `app.py` `run_uninstall`/`clean_rc_duplicates`, the policy factories that take `installed_tools`, `download.py` `install_download`, `Makefile`, `pyproject.toml`, `AGENTS.md`, `.claude/architecture.md` rules, the ROADMAP backlog 999.1–999.7, `scripts/prune-tmp-linux.sh`.

**What I ran:** `codegraph sync` (up to date); `pytest tests/test_uninstall.py tests/test_ownership.py tests/test_status.py` (green); three throw-away headless probes kept in the session scratchpad, outside the repo, that reuse the `tests/test_wizard_app.py` helpers (they confirm F2, F3 and F4); a classifier run against a fake `$HOME` in the scratchpad (confirms F1 and F7).

**What I did not read:** the rest of `ownership.py` (`_collect_candidates`, `_native_owner`, label tables), `shellrc.py`/`rcclean.py` internals beyond their write calls, `systemd_daemon.py`, `daemon.py`, `pnpm_globals.py`, `update.py`, `engine.py`/`executors.py` beyond the "already installed" check, `guidance.py`, `render.py`, `omz.py` beyond `_atomic_write`, `scripts/lib/prune-tmp-common.sh`, `scripts/container-e2e-verify.sh`, `install.sh`, most of the 40k lines of tests. I did not run the full suite or `make validate`, and I did not run on macOS.

## Ranked findings

| ID | Severity | Title | Backlog |
|----|----------|-------|---------|
| F1 | must fix | Uninstall deletes files it cannot prove it installed (a `uv tool` ruff symlink, a file shared by two registry rows) | 999.2 + 999.6 (deepened: destructive) |
| F2 | must fix | The catalog's Enter quietly exits the app under `make doctor` / `make fix` / `make uninstall` / `make guard` | NEW |
| F3 | must fix | Policies never re-reads state on entry: after Uninstall removes the ban, Policies still shows it ON and the next space runs the wrong verb | NEW (999.6 process gap) |
| F4 | must fix | A removed tool stays selected in Uninstall and is counted again ("Removed 2 tool(s)" for one) | 999.1 (new instance) |
| F5 | must fix | `~/.zshrc`, `~/.bashrc` and `~/.myshellrc` are written non-atomically in 3 modules; `clean_rc_duplicates` deletes lines by indices taken from an older read | NEW |
| F6 | should fix | Seven places answer "is it here / who owns it / can we act" and disagree (a skill pack is ✓ in the catalog and "not installed" in Uninstall) | 999.6 |
| F7 | should fix | Install and uninstall work out artifact paths with two different formulas: Sublime on Linux leaves `~/.local/opt/subl` behind after "Removed 1 tool(s)" | NEW (close to 999.2) |
| F8 | should fix | Policy prerequisites are frozen at startup: after you install `watch` or `uv`, Policies still refuses the tweak that needs it | NEW (999.6 family) |
| F9 | should fix | One global ownership epoch, refresh passes scoped per tier, three refresh owners, duplicate manager queries | 999.6 |
| F10 | should fix | The three tier screens are one class, but the app treats the base tier differently in 5 places; the target is one catalog component | 999.6 |
| F11 | should fix | Dead production code: the agent-environment policy (~565 lines, tests only), `Tool.source/owner/uninstall` (parsed, never read), a probe that runs a binary that does not exist | NEW (rule 5) |
| F12 | should fix | `setup.py._build_app` holds the decisions behind F2 and F6 but is outside pyright and coverage | NEW (rule 4) |
| F13 | should fix | `wizard_app.py` does several jobs; 35 % of it is comments, and 71 review IDs record review history instead of code structure | NEW |
| F14 | nice to have | Five list-picker modals and two confirm modals are copies of each other | NEW |
| F15 | nice to have | Seven `Message` classes plus generation counters re-implement what Textual's worker API already gives | NEW |
| F16 | nice to have | Uninstall deletes files on the event loop (a VS Code or Sublime tree freezes the UI) | NEW |
| F17 | nice to have | Hidden `a` binding in Doctor rewrites shell files, while `a` means "select all" on the screens beside it | NEW |

Smaller items left out: 3 (`ToolUpdated.epoch` is never read, `_has_daemon_id` is duplicated in `app.py:499` and `wizard_app.py:898`, and `WayfindingHeader.render_markup` is only called by tests).

---

## F1. Uninstall deletes files it cannot prove it installed — must fix (999.2 + 999.6)

**Evidence**
- `installer/uninstall.py:56-97` `plan_uninstall`: for every `github_release`/`tarball` method it adds `opt_dir(binname)` and `<bin_dir>/<binname>` **if the path exists**. `binname` is the basename of `member`. It checks nothing else: not who made the file, and not the platform.
- `installer/uninstall.py:298-309` `classify_tools`: `if paths:` → `REMOVABLE`, `"installed in userspace — removable here"`.
- `installer/app.py:551` `run_uninstall` (the `make uninstall --yes` route): `paths = plan_uninstall(tools, default_bin_dir)`, then `remove_paths(paths)`.
- `installer/registry.toml:2711` and `:2759`: `drawio-desktop` and `drawio-cli` declare identical methods (`member = "drawio"`, same `app`, same `cli_name`).
- Reproduced with a fake `$HOME` in the scratchpad: `~/.local/bin/ruff` as a symlink into `~/.local/share/uv/tools/ruff/bin/ruff` (what `uv tool install ruff` makes), and one plain `~/.local/bin/drawio`:
  ```
  ruff removable [~/.local/bin/ruff]
  drawio-desktop removable [~/.local/bin/drawio]
  drawio-cli removable [~/.local/bin/drawio]
  ```
  `resolve_ownership` for the same ruff answers `unknown`: it follows the link into uv's tree. So the ownership module already knows this is not ours, and Uninstall never asks it.

**What the code does:** "removable here" means "a file with the right name exists in `~/.local/bin` or `~/.local/opt`".

**What goes wrong:** `~/.local/bin` is shared with `uv tool`, pipx, astral's and zoxide's own install scripts, and the Claude Code native installer. A user who ran `uv tool install ruff` sees ruff as "removable here, 1 artifact". Enter + confirm deletes uv's symlink, and uv's own receipt now points at nothing. `make uninstall --yes` deletes every such name with no per-tool choice. Marking `drawio-cli` deletes `drawio-desktop`'s binary. The registry text for that row even says "Uninstall drawio-desktop to remove the drawio CLI".

**Improvement (smallest complete):**
1. A row is `REMOVABLE` only when the ownership record says it is ours: `ownership.owner == "installer"` with `confidence == "direct"`. In `classify_tools`, the `if paths:` branch becomes `if paths and owned_by_installer(tool):`. The predicate is a third callable in the same seam family as `owner_hint`/`owner_label_hint`, or it falls out of F6's single row state. When no ownership pass has run yet, the row says "checking…" and does not select. Fail closed.
2. `run_uninstall` (CLI) filters `paths` through the same predicate. It runs one blocking `version_refresh.refresh(tools)` first, because the CLI has no UI loop to protect.
3. Delete the `drawio-cli` registry row and set `drawio-desktop.audience = "both"`. Ultra: it does not need to exist. It has the same cmd and the same artifacts, so it is a second name for one install.
4. Real proof of ownership is 999.2 (receipts). Until then, `direct` ownership (the live binary resolves into our opt dir) is the strongest evidence the code already computes.

**What happens if skipped:** the one screen whose Enter deletes files can delete another manager's files, and the CLI route does it without asking per tool.

**Rough size:** about +10/−2 lines in `uninstall.py` and `app.py`, −48 registry lines, +2 tests (uv symlink, shared artifact). 3 files.

---

## F2. The catalog's Enter quietly exits the app under `make doctor` / `fix` / `uninstall` / `guard` — must fix (NEW)

**Evidence**
- `setup.py:1295` (`_run_doctor`), `:1324-1331` (`_run_fix`), `:1351-1356` (`_run_uninstall`), `:1441-1447` (`--guard`) call `_build_app(...)` **without `execute=`** and discard `.run()`'s return value.
- `installer/wizard_app.py:2790-2794`:
  ```python
  if self._execute is None or message.result is None:
      self.exit(message.result)
  ```
- `installer/wizard_app.py:2910-2911` `_rederive_installed`: `if self._execute is None: return None`.
- `tests/test_wizard_app.py:7184` pins this as intended (`test_accepting_the_catalog_without_execute_still_exits_with_ids`).
- Scratch probe: `_app(initial_view="doctor")`, press `1`, mark `rg`, Enter → the app exits with `['rg']`. `_run_doctor` throws that away and returns 0.

**What the code does:** every entry route builds the same six-view app, but only `make setup` wires the install executor. All number keys work on every route.

**What goes wrong:** `make doctor` → press `1` → mark three tools → Enter: the TUI disappears, nothing is installed, and no message is shown. On the same routes, a removal in Uninstall never updates the ✓ marks, because `_rederive_installed` is a no-op without `execute`. This is the same fork as the 9050446 bug: the same component behaves differently depending on how it was launched.

**Improvement:** `_build_app` always builds `ExecuteInputs` itself (move the `_execute_inputs(...)` call inside it; `_run_interactive_wizard` passes only `unattended`). Make `UnifiedApp(execute=...)` required. Delete the `self._execute is None` branches in `on_catalog_screen_decided` and `_rederive_installed`. Change the `_app()` test helper to pass a fake `ExecuteInputs`, and delete the test that pins the exit.

**What happens if skipped:** silent lost work on four documented make targets. Any future optional collaborator defaulting to `None` can fork the app the same way (the comment at `wizard_app.py:2512-2516` already admits the defaults exist only so test constructors keep compiling).

**Rough size:** −15 lines in `wizard_app.py`, about ±10 in `setup.py`, about 20 test call sites touched by the helper change. 3 files.

---

## F3. Policies never re-reads state on entry — must fix (NEW; the per-view, per-direction gap 999.6 names)

**Evidence**
- `installer/wizard_app.py:1638-1640`: `self.active_state = {policy.id: policy.active for policy in inputs.policies}` is set in `__init__`. Only its own toggles (`_finish_toggle`) and the daemon-default worker change it afterwards.
- `grep "def enter_view"`: `ui_common.py:337` (no-op base), `catalog_tui.py:379`, `wizard_app.py:417` (Doctor), `wizard_app.py:1341` (Uninstall). **PoliciesScreen has none.**
- Uninstall changes the same state: `UninstallDecision.remove_ban` / `remove_tweaks` (`wizard_app.py:1461-1466`).
- Scratch probe: Uninstall removes the ban, then press `6` → `policies shows ban active: True real: False`.

**What the code does:** Policies shows the state it saw when the app started, plus its own toggles.

**What goes wrong:** Uninstall → remove "pip/npm ban" → Policies still shows `● [on]`. The user presses space to turn it back on. The screen thinks it is on, so it calls `policy.remove()` again and reports "pip/npm ban disabled." The user has to press space a second time to get what they asked for. The same happens with every shell tweak and the daemon after "remove tweaks". The status line from the last toggle also stays across navigation: `show_view` clears transient text only on catalogs (`wizard_app.py:2687-2689`).

**Improvement:** add `enter_view` to PoliciesScreen. It re-reads `policy.is_active()` when the policy binds one, else the policy's own predicate. Uninstall already reads the same predicates through `uninstall.policy_owned` (`uninstall.py:387-398`), so reuse that function. Repaint the State column and clear the status line. The target in "Screen component architecture" makes this the shared default instead of a per-screen opt-in.

**What happens if skipped:** the exact fork class that 9050446 fixed for the base tier stays open on another screen, and the next verifier checks each screen's own claim again instead of each direction.

**Rough size:** +12 lines, +1 test (remove in Uninstall → Policies shows OFF). 1 file.

---

## F4. A removed tool stays selected in Uninstall and is counted again — must fix (999.1, new instance)

**Evidence**
- `installer/tool_browser.py:215-218` `reload`: drops a selection only when the id **vanished** from the items. Uninstall rows never vanish: a removed tool turns into an `absent`, non-selectable row with the same id.
- `installer/tool_browser.py:325-331` `selected_ids` does not filter by `selectable`.
- `installer/wizard_app.py:1419-1430` `_accept_summary` and `:1475` count every id in `ids`.
- Scratch probe: remove `rg` → navigate away and back → `selected after re-entry: {'rg'}` → mark `fd` → `confirm text: 2 tool(s)` → `Removed 2 tool(s).` while `paths sent: (/x/fd,)`.

**What the code does:** a row that stops being selectable keeps its hidden mark. The mark is invisible, because non-selectable rows keep their blank cell.

**What goes wrong:** the confirm modal of a destructive action names the wrong count, and the summary claims removals that did not happen. The same rule also keeps a catalog selection after an Uninstall (999.1(a)). Both come from one root: selection is pruned by "id gone", never by "no longer actionable".

**Improvement:** one rule in the shared widget. In `reload`, after swapping the adapter: `self.selected -= {i for i, item in self._by_id.items() if i is not None and not adapter.selectable(item)}`, and keep the existing vanished-id rule. `selected_ids` also filters on `selectable`. The catalog's shared `_staged` set is safe: the rule touches only ids this adapter owns. This is also the hook 999.1 needs to clear catalog selections after Uninstall (the catalog adapter would mark installed-and-current rows as "nothing to do").

**What happens if skipped:** wrong numbers on a confirm dialog that deletes files. Users stop trusting the summary.

**Rough size:** +3 lines in `tool_browser.py`, +1 test. 1 file.

---

## F5. Shell rc files written non-atomically; line deletion by stale indices — must fix (NEW)

**Evidence**
- `installer/shellrc.py:5` states the project rule: every rc write "goes through installer/atomic.py, because a truncated rc file is unrecoverable". `installer/omz.py:243-261` repeats it for `~/.zshrc`.
- These writes break the rule: `installer/guards.py:554, 564` (ban alias block into each of `_RC_PATHS` = `~/.zshrc`, `~/.bashrc`), `installer/tweaks.py:297, 308` (`~/.myshellrc`), `installer/app.py:447` (`clean_rc_duplicates` into `~/.zshrc`/`~/.bashrc`). All use `Path.write_text`, which truncates first and then writes.
- `installer/app.py:432-447`: `indices` come from the first `read_text()`. The code then waits for `confirm(...)` (a human prompt) and applies them with `strip_lines(rc_path.read_text(), indices)` on a **second** read.

**What goes wrong:**
1. A full home filesystem (`ENOSPC`/`EDQUOT`, the very condition the tmp-cleanup daemon exists for) or a kill during the write leaves `~/.zshrc` empty or cut short. Every new shell then starts without PATH, aliases or prompt, and the file has no backup.
2. The user edits `~/.zshrc` in another window while the "Remove these duplicate PATH lines?" prompt waits (it shows the file, so this is likely). Line numbers shift, and the cleanup deletes the wrong lines from the user's own file.

**Improvement:** replace the 7 `write_text` calls with `atomic_write_text` (already imported next door in `shellrc.py`). In `clean_rc_duplicates`, keep the text you previewed. Re-read after the confirm and refuse that file with a message if it changed (`if rc_path.read_text() != previewed[rc_path]`). No new helper is needed.

**What happens if skipped:** a rare but unrecoverable loss of the user's main shell config. The project's own written rule is applied in two modules and broken in three.

**Rough size:** about 10 lines changed, +2 tests (write failure leaves the original intact; changed-file refusal). 4 files.

---

## F6. Seven places answer "is it here / who owns it / can we act" — should fix (999.6)

**Evidence** (each place makes its own decision):

| # | Where | Question it answers | Used by |
|---|-------|---------------------|---------|
| 1 | `status.py:18-67` `is_installed` | cmd on PATH, `detect_path`, `bin_dir`, app bundle | catalog ✓ (`_installed`), Uninstall `installed_now` (`setup.py:859`), Execute (`execute_screen.py:477-539`), engine "already" (`engine.py:132`), and **inside** `resolve_ownership`'s script branch (`ownership.py:725`) |
| 2 | `catalog_tui.py:479-492` `_present` | skill-pack host probes override #1 | catalog ✓, Ver, groups |
| 3 | `uninstall.py:56-97` `plan_uninstall` | "a file with that name exists" | Uninstall `REMOVABLE`, and the `artifacts` evidence `resolve_ownership` takes (`version_status.py:591-594`) |
| 4 | `ownership.py:561` `resolve_ownership` (+ `install_ownership.detect_owner`) | who owns the live binary; `broken` | Owner column, `!` mark, `u` gate, Uninstall hint/label via `setup.py:807-849` closures |
| 5 | `version_status.resolve_status` | can we read a version; is it outdated | Ver column, Execute "current"/update split |
| 6 | `execute_screen.py:497-539` `_classify_selection` | repair / current / update / install, from #1 + #4 + #5 | Execute |
| 7 | `policy.py:441-444`, `:853-855` | prerequisite installed? (snapshot of #1 at startup) | Policies (F8) |

Concrete disagreements on one host:
- **ponytail skill pack** (`cmd = "ponytail"`, no binary): catalog ✓ (#2 sees it in Claude Code). Uninstall says "not installed" (#1 is False). Execute would try to install it again. The registry's removal instructions (`skill_lifecycle.removal.instructions`, copied into `Tool.uninstall` at `model.py:831-835`) are never shown anywhere.
- **kitty via `installer.sh`**: ✓ (#1), Owner "own installer" (#4 by elimination, which itself calls #1), Uninstall `MANAGED` with a special-cased wording (`ownership._own_script_install`, 9050446). Removal is impossible (#3 plans only download/app kinds).
- **uv-tool ruff** (F1): ✓ (#1), Owner unknown (#4), Uninstall `REMOVABLE` (#3).

**What goes wrong:** every new screen or rule adds a new fork, and every fix patches wording in one consumer (`_own_script_install`, `_VIA_*` labels, `_manager_hint`'s 40-line docstring explaining why it must stay narrower than ownership's own filter).

**Improvement (target shape):** one record, computed in one place:
```python
@dataclass(frozen=True)
class ToolState:            # installer/status.py
    present: bool | None    # None = still checking
    ownership: ManagerOwnership | None
    removable: tuple[Path, ...]   # only when ownership proves it is ours (F1)
    removal: str            # hint: removal_hint() or Tool.uninstall or "not installed"
    version: VersionStatus | None
```
`VersionRefreshService.refresh` already loops over every tool and already holds #3, #4 and #5. It also computes #1 once (and #2 for skill packs) and publishes `ToolState` in the same epoch-tagged map (`_ownership` becomes `_state`). Catalog cells, Uninstall rows, Execute's classification and the Policies prerequisites all read `state_of(tool_id)`.

Deletes: `classify_tools` + `ToolRow` + `OwnerHint`/`OwnerLabelHint` + `_manager_hint`/`_managed_hint` (`uninstall.py:100-339`, about 240 lines), the 3 `setup.py` closures (`_uninstall_owner_hint`, `_uninstall_owner_label`, `_uninstall_rows`, about 60 lines), `ownership._own_script_install` and its branches, catalog `_present`/`_inst_cell` skill branching (about 40 lines), and Execute's own reclassification loop (about 30 lines). `plan_uninstall` stays as the artifact formula (see F7) but is no longer read as evidence.

**What happens if skipped:** 999.6 stays open. Each phase keeps re-fixing one screen's wording while the next screen disagrees.

**Rough size:** +60 / −400 lines. Files: `status.py`, `version_status.py`, `uninstall.py`, `catalog_tui.py`, `wizard_app.py`, `execute_screen.py`, `setup.py`, `ownership.py`, plus tests for every per-direction refresh (install / update / uninstall × every tier).

---

## F7. Install and uninstall use two formulas for the same artifact path — should fix (NEW, close to 999.2)

**Evidence**
- Install (`download.py:144`, `:169`): `binname = bin_name or basename(member)`, `opt = opt_dir(link.name)`.
- Uninstall (`uninstall.py:83`, `:95-96`): `binname = basename(member)`. It ignores `bin_name`.
- `registry.toml:2266-2279`: Sublime's Linux tarballs use `member = "sublime_text"`, `bin_name = "subl"`.
- Fake `$HOME` with `~/.local/opt/subl/sublime_text` + `~/.local/bin/subl`: `plan_uninstall([sublime])` → only `~/.local/bin/subl`. That path is found only by accident: the **macOS** `app` method's `cli_name` is also `subl`, because `plan_uninstall` scans every method without a platform filter. `~/.local/opt/subl/` (the whole Sublime tree) is never planned.
- No test pins "the install path equals the uninstall plan" for any method.

**What goes wrong:** Uninstall on Linux says "Removed 1 tool(s)" and leaves the full Sublime install in `~/.local/opt/subl`. Then the catalog shows ○, the next Uninstall shows nothing, and the disk space leaks for good. Any future `bin_name` row breaks the same way.

**Improvement:** one function in `download.py`, `artifact_paths(method) -> (opt, link)`, used by `install_download` and `plan_uninstall`. Pass `platform` to `plan_uninstall` and use `resolve_methods` (it is already imported in `uninstall.py:20`), so a macOS method never plans a Linux path. One parametrized test over every registry download/app method: plan == what the executor would create.

**What happens if skipped:** orphaned trees that no screen can see. The two formulas drift further each time a param is added.

**Rough size:** +15 / −15 lines, +1 parametrized test. 2 files.

---

## F8. Policy prerequisites are frozen at startup — should fix (NEW, 999.6 family)

**Evidence**
- `setup.py:783` `installed = {tool.id: is_installed(tool) for tool in tools}` runs once.
- `setup.py:981-988` passes it to `tweak_policy(..., installed_tools=installed)`; `policy.py:441-444` computes `missing_requires` once from it; `hard_requires` defaults to True (`policy.py:132`).
- `tweaks.py:162` (docker → `watch`), `:171` (countdown → `uv`).
- `wizard_app.py:2036-2047`: a hard-required, missing prerequisite refuses the toggle.
- The live form already exists: `Policy.missing_requires_now` (`policy.py:137, 160-164`), used only by `omz_plugins_policy` (`policy.py:648`).

**What goes wrong:** fresh machine. User → System/User tab → installs `watch` → Policies → space on "docker tweaks" → "Install required tool(s) first: watch. Open Catalog, install them, then retry." The tool is installed; the refusal holds until the app restarts. The macOS daemon's fd/rg "recommended" note (`policy.py:853-855`) is frozen the same way.

**Improvement:** pass a predicate, not a map. `installed_tools: Callable[[str], bool]` (bound to `is_installed`, or to F6's `state_of`). Every factory sets `missing_requires_now`. Delete the `missing_requires` tuple field and the `missing_requires_now` / `missing_requires` split in `Policy.missing_requirements`: one field, always live.

**What happens if skipped:** a second "is it installed" answer that is wrong for the rest of the session after every install.

**Rough size:** about ±15 lines, +1 test. 3 files.

---

## F9. One global epoch, tier-scoped passes, three refresh owners — should fix (999.6)

**Evidence**
- `version_status.py:578-589` `invalidate` bumps one epoch for every tool. `ownership_of` (`:510-529`) answers `None` for any record from an older epoch.
- `catalog_tui.py:431`: each tier's worker refreshes only `self.tools` (its tier). `setup.py:967`: Uninstall's own refresh closure refreshes all tools. `catalog_tui.py:974`: `u` refreshes one tool and then the tier (`:998`).
- `wizard_app.py:2996`: `OwnershipRefreshed` is routed only to Uninstall, only when Uninstall is visible.
- `version_status.py:685` `_load_or_query_snapshot` runs `brew list`, `pnpm list -g` and `uv tool list` with no lock. Workers live per screen, so two passes can query at the same time after an invalidate.
- `statuses` (`:503`) is not epoch-gated, while ownership is. Execute reads both (`execute_screen.py:507-513`).

**What goes wrong:** install something from System → close Execute → only System is refreshed. Open Uninstall: every managed User/AI row shows the generic registry phrase and "package manager", because their records are epoch-stale and nothing refreshes them. Press `u` in User: System and AI go blank until you visit them. After an Uninstall removal, the Uninstall pass and the next catalog entry both re-query every manager.

**Improvement (target):** one refresh owner at app level. `UnifiedApp` owns one worker over the **full** catalog (`refresh(self._catalog_tools)`). It is started on mount and by every mutation (install close, `u` update, Uninstall removal, policy toggle that installs or removes something). It posts one `StateRefreshed`, and **every** visible screen repaints from the shared map. Hold a lock across the manager query so a second caller waits for the first one's snapshot, exactly as `refresh_skills` already does with `_skills_pass_lock` (`:555`).

Deletes: the per-screen `_refresh_versions_worker`/`_refresh_skills_worker` and generation counters ×3, `UninstallScreen._refresh_ownership_worker`, `UninstallInputs.invalidate`/`.refresh` and their 30 lines of field comments, the uninstall-only routing in `on_ownership_refreshed`, and `CatalogScreen.on_tool_updated`'s "kick a full pass" workaround (CR-02 comment).

**What happens if skipped:** the "best-effort" window that 15.4-05 documented stays. Every new screen has to choose its own refresh scope, which is how F3 happened.

**Rough size:** +40 / −150 lines. Files: `catalog_tui.py`, `wizard_app.py`, `version_status.py`, `setup.py`. A full pass over about 90 tools costs mostly cached inventory reads plus a few `rpm -qf` calls. I did not measure it; measure before committing to it.

---

## F10. The three tier screens are one class, but the app forks the base tier — should fix (999.6)

**Evidence** (all in `wizard_app.py`; the "base" is `VIEW_ORDER[0]` = system):
1. `:2494-2511`: base catalog is not installed or pushed; the other two are installed in `_views`.
2. `:2670-2674` `get_default_screen` returns the base; App-level queries resolve against it (the tests depend on that).
3. `:2695-2706` `show_view`: base calls `enter_view()` directly; non-base calls `enter_view()` **before** `push_screen`. That is why `UninstallScreen` needs the `_pending_status` stash (`:943-952`, `:1172-1186`) and why `CatalogScreen.enter_view` only works when already mounted (`catalog_tui.py:379-381`).
4. `:2726` `_navigable` compares against the base and against `_views` separately.
5. `catalog_tui.py:1022-1030` `on_screen_resume` re-stamps marks because the three instances share one `_staged` set.

The 9050446 bug was fork #3 (the base tier was never re-derived). The fork is still structural: whichever view is first in `VIEWS` gets different lifecycle code.

**Improvement:** see "Screen component architecture" below. Minimum: make `get_default_screen` an empty root screen and push **all** six views the same way. `show_view` becomes pop → push → `enter_view()` after the push (the screen is mounted, so the stash goes away). Ultra: one `CatalogScreen` instance, with tier as a grouping tab ("System / User / AI" sections, one line in `group_tools`). Two instances, the shared-set re-stamp and F9's tier scoping all go away.

**What happens if skipped:** the next lifecycle hook added to `show_view` has two paths again, and one of them gets missed.

**Rough size:** minimum −40 lines; ultra −80 lines and 3 → 1 catalog instance. Nav keys go from 6 to 4 in the ultra form (a user-visible change; needs a decision).

---

## F11. Dead production code — should fix (NEW; violates `.claude/architecture.md` rule 5)

**Evidence**
- Agent-environment policy: `installer/agent_policy.py` (376), `installer/agent_env.py` (63), `installer/agent_guidance.py` (25), `policy.py:167-266` `AgentEnvironmentPolicy` / `agent_environment_policy` / `compose_agent_environment_policy` (100). `grep` across `installer/` and `setup.py`: no production caller. Only `tests/test_agent_*.py` (740 lines) import it. Added by `bdcdcb4 feat(policy): port local-only agent-environment permission auditing` and never wired into a screen.
- `Tool.source`, `Tool.owner`, `Tool.uninstall` (`model.py:316-321`, parsed at `:825-835`, 23 registry lines): read by nothing.
- `install_ownership.py:83-89` `_managed_download` runs `tools-installer-managed-download list <id>`, a binary that exists nowhere. It was flagged in `15-VERIFICATION.md:50` and is still live for `drawio-*` through `owner_probes`. It resolves through PATH, so any planted binary with that name gets run.

**Improvement:** delete the agent modules, their 4 test files and the `policy.py` block. Delete `_managed_download` and the `"managed-download"` probe name, and drop it from the 2 registry rows. For `Tool.uninstall`: **use it, do not delete it**. It is the removal sentence a `MANAGED`/script row should show (kitty's "remove ~/.local/kitty.app …") until 999.2's receipts exist, and F6's `ToolState.removal` reads it. Delete `source`/`owner` if nothing adopts them.

**What happens if skipped:** about 1,300 lines (code + tests) to read, type-check and keep green for a feature nobody can reach, plus one subprocess spawn per probe of a non-existent binary.

**Rough size:** −565 production lines, −740 test lines, −20 registry lines. 8 files.

---

## F12. `setup.py._build_app` holds decisions but is outside the type checker and coverage — should fix (NEW; rule 4)

**Evidence:** the `Makefile` `validate` comment says "setup.py (composition root) is lint/format-gated but stays out of pyright/coverage". `pyproject.toml` `[tool.pyright] include = ["installer", "tests"]`, `[tool.coverage.run] source = ["installer"]`. Yet `_build_app` (`setup.py:755-1163`, about 400 lines) decides which collaborators each route gets (F2), how Uninstall rows are classified (`_uninstall_rows`, F6), how removal hints are bound, and when the daemon default applies. The reason given for the exclusion (questionary is untyped) applies only to the prompt helpers at `setup.py:285-360`.

**Improvement:** move `_build_app`, `_execute_inputs` and the probe/cache builders into `installer/compose.py`. Leave argv parsing, the questionary prompts and `main` in `setup.py`. No logic changes.

**What happens if skipped:** the wiring layer, where F2 lives, stays unchecked by the strict type checker and invisible to the 90 % coverage gate.

**Rough size:** move about 600 lines, net 0. 2 files plus test imports.

---

## F13. `wizard_app.py` does several jobs, and its comments record review history instead of code structure — should fix (NEW)

**Evidence:** 3,011 lines: `UnifiedApp`, `DoctorScreen`, `UninstallScreen`, `PoliciesScreen`, 5 modals, 7 `Message` classes, 2 input dataclasses. Measured 1,073 comment/docstring lines (35 %) against 1,686 code lines. 71 references to review IDs (`WR-01`, `CR-03`, `Round-2 review HIGH`, `11-REVIEWS.md cycle 3 finding #15`). Examples of a comment standing in for a fix:
- `UninstallInputs` (`:76-126`): a 50-line docstring explains why four fields must be predicates. F6/F9 remove the reason.
- `_resync` (`:1238-1339`): a 30-line precedence essay plus a `cast` explained in 9 lines, because `run_live` returns a pair that pyright cannot correlate.
- `_install_closed` (`:2796-2901`): 75 comment lines for about 25 lines of code.
- `PoliciesScreen._policy_detail` (`:1727-1877`): 100 lines of per-policy prose hardcoded in the screen. It belongs on the `Policy` (a `details: tuple[str, ...]` field set by each factory), where the policy that changes is next to its text.

**Improvement:** split by job, not by length: `doctor_screen.py`, `uninstall_screen.py`, `policies_screen.py`, `modals.py` (F14), with `wizard_app.py` keeping only `UnifiedApp`. Delete every comment that cites a review ID or narrates a past bug. Keep one line of *why* where the code cannot show it (the history is already in git and `.planning/`). Move the policy prose onto `Policy`.

**What happens if skipped:** every change reads 3 lines of history per line of code. Reviewers keep adding a paragraph per finding, which is how the file got here.

**Rough size:** about −900 comment lines, −100 lines moved out of the screen. 5 files.

---

## F14. Five picker modals and two confirm modals are copies — nice to have (NEW)

**Evidence:** `NavScreen`, `TimePickerScreen`, `LinkModeScreen` (`wizard_app.py:2274-2373`) and `ChecksumMismatchScreen`, `SensitiveActionScreen` (`execute_screen.py:94-181`) each repeat: `ModalScreen[str | None]`, escape → cancel, a `ListView` of letter-prefixed ids, a `removeprefix` in `on_list_view_selected`, `dismiss`. `ConfirmGuardFile` and `ConfirmUninstall` (`:2197-2271`) are the same modal with a different border color and text.

**Improvement:** one `ChoiceModal(prompt: str | None, options: Sequence[tuple[str, str]])` and one `ConfirmModal(text: Text, border: str)`, about 40 lines in total.

**Rough size:** about −120 lines. 2 files.

---

## F15. Worker→loop plumbing re-implements Textual — nice to have (NEW)

**Evidence:** `GlobalsReinstalled`, `GlobalsAudited` (+ generation), `DiskPressureProbed`, `CompetingProbed`, `PolicyToggled`, `DaemonDefaultApplied` (`wizard_app.py:201-270, 2382-2398`), plus `VersionStatusRefreshed` / `SkillStatusRefreshed` generations in `catalog_tui.py`. Each exists only to hop from a thread worker back to the loop and to drop a superseded result. Textual already provides `get_current_worker().is_cancelled` (an `exclusive=True` worker is marked cancelled; check it before posting) and `App.call_from_thread(callback, *args)`.

**Improvement:** inside each worker, `if not get_current_worker().is_cancelled: self.app.call_from_thread(self._landed, result)`. Delete the Message classes and the `_globals_audit_generation` / `_version_refresh_generation` counters.

**Rough size:** about −150 lines. 2 files. Check that the existing race tests still express the same guarantee.

---

## F16. Uninstall deletes files on the event loop — nice to have (NEW)

**Evidence:** `wizard_app.py:1467` `run_live(lambda: self._remove(decision))` runs synchronously in a modal callback. `remove_paths` is `shutil.rmtree` (`uninstall.py:342-351`). Every other mutation in the app (policy toggle, pnpm reinstall, daemon default, update, install) runs in a thread worker.

**What goes wrong:** removing a VS Code or Sublime tarball tree (thousands of files) freezes the UI with no progress. Ctrl+C arrives as a byte the blocked loop does not read (the code says so at `wizard_app.py:790-794`).

**Improvement:** a `@work(thread=True)` wrapper with "Removing…" on the status line, the same shape as `PoliciesScreen._toggle_policy_worker`.

**Rough size:** +15 lines. 1 file.

---

## F17. Hidden `a` binding in Doctor rewrites shell files — nice to have (NEW)

**Evidence:** `wizard_app.py:292` `Binding("a", "apply", "apply", show=False)`. On Catalog and Uninstall, `a` means "select all" (`tool_browser.py:117`). The Doctor footer shows only `enter apply` (`ui_common.py:163`).

**What goes wrong:** a user who presses `a` out of habit on Doctor writes the managed PATH block into their rc files with no prompt.

**Improvement:** delete the line (`enter` stays).

**Rough size:** −1 line, and update any test that presses `a` on Doctor.

---

## Screen component architecture

### Current shape

```
textual.Screen
└─ AppScreen (ui_common.py:321)          chrome: WayfindingHeader, Rule, ModeBadge, body, StatusLine, FooterBar
   │                                     enter_view() = no-op default
   ├─ CatalogScreen ×3 (catalog_tui.py)   ToolBrowser[Tool] + recommends StatusLine
   │    • system = BASE: never pushed, enter_view called directly by show_view, get_default_screen
   │    • user/ai: installed + pushed, enter_view called BEFORE push (no-op until mounted)
   │    • own version worker + skill worker + update worker, own generation counter, tier-scoped refresh
   │    • shares one _staged set → on_screen_resume re-stamp
   ├─ UninstallScreen (wizard_app.py:909) ToolBrowser[_UninstallEntry]
   │    • own _resync (rows + 3 env predicates, precedence rules), own _pending_status stash
   │    • own ownership refresh worker, own invalidate seam, ConfirmUninstall
   │    • rows from classify_tools (classifier #3), not from the catalog's state
   ├─ PoliciesScreen (wizard_app.py:1600) raw DataTable + #policy-detail Static
   │    • own space/l/t/m bindings, own detail rendering, own toggle worker + message
   │    • NO enter_view (F3); prerequisites frozen (F8)
   └─ DoctorScreen (wizard_app.py:281)   one Static text body
        • enter_view re-reads guard state, two workers + two messages + generation counter

textual.ModalScreen
   ├─ ExecuteScreen (own StatusLine, own key strip; not an AppScreen) + its own classifier (#6)
   ├─ ConfirmUninstall, ConfirmGuardFile                   (same modal twice)
   └─ NavScreen, TimePicker, LinkMode, ChecksumMismatch, SensitiveAction  (same picker ×5)

UnifiedApp: _catalogs{tier} + _views{name}; show_view branches base/non-base; _staged shared set,
cleared only in _install_closed; OwnershipRefreshed routed to Uninstall only; execute optional (F2).
```

### What each screen re-implements

| Building block | Catalog | Uninstall | Policies | Doctor |
|---|---|---|---|---|
| Table | ToolBrowser | ToolBrowser | own DataTable + own detail Static | none (text report) |
| Status line | StatusLine (+ recommends line) | StatusLine + pre-mount stash | StatusLine | StatusLine (unused; status lives in the body text) |
| Selection | shared `_staged` set | own set, keeps ghost ids (F4) | none (space = act) | none |
| Refresh on entry | `_start_version_refresh` (tier only) | `_resync` (full predicates) | **missing** | `_refresh_guidance` + 2 workers |
| Refresh on background change | own worker message | `ownership_refreshed()` routed by app | none | own messages |
| Warnings after mutation | `_flush_pending_warnings` via app | own `summary_parts` | own `_summary` | own body text |
| Status cleared on leave | yes (`clear_transient`) | no | no | n/a |
| Keybindings | ToolBrowser + r/d/u | ToolBrowser | space(priority)/l/t/m | enter/**a**/r |

### Target

```
AppScreen                                  unchanged chrome
└─ RowsScreen[T]  (new, ~60 lines, ui_common.py)
     hooks: rows() -> list[T]                 # read from the shared ToolState map (F6), via run_live
            adapter(rows) -> BrowserAdapter[T]
            on_accept(ids)                    # what Enter means on this screen
     shared: enter_view() = rows() → browser.reload()        (called AFTER push: no pre-mount stash)
             on_state_refreshed() = same                      (one app-level StateRefreshed, F9)
             selection pruned by "no longer selectable" (F4)
             status cleared on leave (one rule for all)
   ├─ CatalogScreen  — ONE instance; tier is a grouping tab (ultra) or 3 instances pushed identically (minimum)
   │     rows = ToolState for the catalog; on_accept → ExecuteScreen (always wired, F2)
   ├─ UninstallScreen — rows = ToolState ordered: removable here (proven ours, F1)
   │     → managed elsewhere (owner + removal text, incl. Tool.uninstall) → not installed / unavailable
   │     + env rows; on_accept → ConfirmModal → remove on a worker (F16)
   └─ PoliciesScreen — rows = policies with live is_active / missing_requires_now (F3, F8);
         adapter flag activate_on_space=True: ToolBrowser posts Activated(id) instead of toggling a mark
DoctorScreen — stays a text report (it is not a list), but uses the same enter_view-after-push and
               the same app-level refresh signal; drop the hidden `a` (F17).
ExecuteScreen — reads ToolState instead of re-classifying (F6).
Modals — ChoiceModal + ConfirmModal (F14).
UnifiedApp — one empty root screen, every view pushed the same way; one refresh worker over the full
             catalog; execute required; selection rule shared through the widget (999.1 hooks in here).
```

### What the target deletes (estimates)

| Removed | Lines |
|---|---|
| Base/non-base branches in `show_view`, `_navigable`, `get_default_screen` semantics, `_pending_status` stash | ~60 |
| `UninstallScreen._resync` precedence machinery, `_env_state`/`_live_state`/`_rows_of`, construction-time `run_live` + startup-error stash (moves into `RowsScreen`) | ~200 |
| Per-screen refresh workers, generation counters, Uninstall refresh worker, `UninstallInputs.invalidate/refresh`, uninstall-only `on_ownership_refreshed` | ~150 |
| `classify_tools`/`ToolRow`/hint seams + `setup.py` closures + `_own_script_install` + Execute reclassification | ~400 |
| Policies' own DataTable/detail/highlight plumbing (replaced by ToolBrowser + `Policy.details`) | ~120 |
| Modal copies | ~120 |
| Worker→loop Message classes | ~150 |
| Review-history comments | ~900 |
| **Total** | **≈2,100 lines removed, ≈150 added** |

The order matters: F6's `ToolState` comes before `RowsScreen`, otherwise the base class would just move four classifiers into one file.

## Verdict

Not healthy. The screens look shared (one chrome, one browser widget), but their state is not: every screen derives and refreshes its own truth, and the forks show up as wrong or destructive actions. Fix first, in this order:

1. **F1** (Uninstall deletes foreign files) and **F5** (non-atomic rc writes, stale-index deletion): data loss.
2. **F2** (catalog Enter exits under four make targets), **F4** (ghost selection miscounts a destructive confirm), **F3** (Policies stale after Uninstall): small, local, each one test.
3. **F7** and **F8**: two more forks of "same rule, two formulas"; small.
4. **999.7's red `main` CI**: before merging any of the above.
5. **F6 → F9 → F10** together as 999.6: one `ToolState`, one refresh owner, one `RowsScreen`. Use the per-direction, per-view test rule 999.6 already asks for.
6. **F11, F12, F13** (delete dead code, move wiring under pyright/coverage, split the god module and drop the history comments), then **F14–F17**.

Lean: about −2,100 lines (production; about 900 of them comments) plus −740 dead test lines possible, −0 dependencies.

Not checked: macOS behaviour; the full test suite and `make validate`; the cost of a full-catalog ownership pass (F9 assumes it is affordable); `ownership.py` internals beyond `resolve_ownership`; `shellrc.py`/`rcclean.py` parsing logic; `systemd_daemon.py`/`daemon.py`; `pnpm_globals.py`; `update.py`; the shell scripts other than `prune-tmp-linux.sh`.
