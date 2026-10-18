# Phase 20 — ponytail review

Scope: `git diff 9e35fb9 HEAD -- installer setup.py scripts tests` (35 files, +8157 / -5205,
plans 20-01..20-19).
Load assumed: one person running the TUI or one headless `--all`/`--categories` run on their own
machine. There is one refresh service per process, a catalog of about 90 tools (7 of them skill or
project packs), and one worker thread per run.

**Severity counts:** High 1 · Medium 3 · Low 6

## What this change does

One pure `build_plan` (`installer/session.py`) turns the selection plus the published `ToolState`
map into one `PlanRow` per selected or dragged tool. Each row has one `Disposition` (install, update,
repair, reconfigure, reinstall, skip, blocked, or "checking…" while state is pending) and a reason.
One `execute_plan` runs those rows for both the TUI review screen and headless `run_wizard`. It
returns one `RowOutcome` per row. The summary words, the exit code (`exit_code`), the selection kept
after a run (`retained`) and the "did anything run" gate (`ran_anything`) are all pure functions of
that list, and they read one `WORDS`/`RESULT_WORDS` table. The legacy flow (`audit`, `run_installs`,
`Summary`/`fold_run`, `reapply_post_install`, `tool_choices`/`category_choices`,
`select_categories`/`select_tools` on the prompter, the questionary checkbox) is deleted. `r` toggles
a reinstall on installer-owned current rows. Enter waits on the shared refresh while any row is still
checking.

## Must fix

1. **Headless `--all` never settles skill packs, so it installs nothing and exits 1** — High
   (`installer/app.py:120`, `installer/execute_screen.py:557-562`, `installer/session.py:635`,
   `installer/version_status.py:1229-1242`)
   - **What this is:** `run_wizard` runs one synchronous `refresh.refresh(tools)` and then calls
     `build_plan`. A row whose state is CHECKING is planned as WAIT. Any WAIT row makes headless
     print "State check failed: no state for …" and mark every row not_attempted.
   - **Problem:** A skill pack's state stays CHECKING until `refresh_skills` stores fresh host
     answers. `refresh()` never does that. `_build_services` only seeds stale answers from the cache
     (`seed_skills_from_cache`), and the only `refresh_skills` caller is the catalog screen's worker
     (`catalog_tui.py:429`). So `--all` (and any `--categories` run that includes a pack) always
     stops before the plan. I reproduced this with the real `_build_services` under a scratch HOME:
     after `refresh(...)`, `ponytail`, `superpowers`, `softaworks-agent-toolkit` and
     `matt-pocock-skills` are all `Disposition.WAIT`. With the test double
     `_pack_service(..., _unreadable_probe("raises"))`, the pack reads `checking` after `refresh` and
     `missing` only after `refresh_skills`. In the TUI the same gap exists in a smaller form.
     `_wait_worker` joins only `refresh`, so Enter right after a run (an `invalidate` marks skill
     answers stale) can end in "State check failed: no state for superpowers" until the catalog's
     own skill worker finishes. The headless tests pass because `state_doubles` publishes pack
     states directly.
   - **Fix:** Settle the packs in the same wait. In `run_wizard`, call `refresh.refresh_skills(tools)`
     right after `refresh.refresh(tools)`, inside the same `try`. In `_wait_worker`, run both inside
     the one `run_live` lambda. `refresh_skills` is already single-flight (`_skills_pass_lock`) and
     returns at once when the packs were already probed. Add one test that builds a real pack service
     (the `_pack_service` helper) and asserts `run_wizard` plans the pack as something other than
     WAIT.
   - **If we skip it:** The headless install route (`make setup ARGS="--all --yes"`, the container
     e2e pass) does nothing and fails on every host that has the catalog's skill packs.

2. **A pending dependency with no install method reads "blocked", so Enter runs at once on stale
   state** — Medium (`installer/session.py:790-809`, `installer/deps.py:103-110`)
   - **What this is:** `build_plan` passes `is_installed = _settled(state_of(id))` to
     `resolve_dependencies`. A dependency that is "not installed" and has no applicable method goes
     to `res.blocked`, and `_blocked_row` turns it into a BLOCKED row.
   - **Problem:** A dependency whose state is still pending (`None`) also counts as "not installed".
     When it has no method on this platform, it becomes BLOCKED and not WAIT, so nothing makes Enter
     wait. Example, reproduced with `build_plan`: `oh-my-zsh` requires `zsh`. On an immutable Fedora
     host without brew, zsh has no applicable method (dnf is rejected as `immutable`), but zsh is
     preinstalled. Before the pass publishes zsh, the plan reads `oh-my-zsh blocked — needs zsh` and
     `zsh blocked — zsh is not available on this platform — skipped`. There is no WAIT row, so Enter
     starts the run right away: "Nothing ran", and oh-my-zsh stays selected. Once zsh's state exists,
     the same plan is `zsh skipped — already present` and `oh-my-zsh will install`. This is common
     right after any run, because `invalidate` makes every `state_of` return `None` and the retained
     selection is reopened straight away. It breaks R7 ("MUST NOT start the engine on state from an
     older generation"). The fallback reason also reads "blocked — … — skipped", which contradicts
     itself.
   - **Fix:** At the top of `_blocked_row`, add
     `if state is None or state.health is Health.CHECKING: return PlanRow(blocked.tool_id, Disposition.WAIT, "", requested_by=requester)`.
     One WAIT row is enough to make Enter wait and replan. The dependents can stay BLOCKED until that
     replan. Add one `build_plan` test: a `state_of` with no zsh state gives a WAIT row. Drop the
     " — skipped" tail from the `deps.py:133-135` text that `_blocked_row` reuses.
   - **If we skip it:** Right after launch or after a run, a tool whose dependency only the host
     provides is reported blocked and is not installed, and the user has to press Enter again later.

3. **A failed reconfigure or a refused update loses its reason** — Medium
   (`installer/render.py:150-155`)
   - **What this is:** `outcome_detail_text` builds the text after "failed" from
     `install.errors`, then `update.errors`, and otherwise prints "no method succeeded".
   - **Problem:** `_run_reconfigure` puts its failure only on `RowOutcome.detail`, for example
     `"install the group: pnpm is not on PATH"`. `UpdateService.run`'s pnpm snapshot refusal
     (`update.py:540-552`) returns `status="failed"` with a `detail` and no `errors`. Both rows render
     as `failed — no method succeeded`, in the TUI and in headless. No other renderer shows them,
     because `render_failure_details` reads only `InstallOutcome`s. I checked it:
     `outcome_detail_text(RowOutcome(row, "failed", detail="install the group: pnpm is not on PATH"))`
     returns `'no method succeeded'`.
   - **Fix:** Fall back to the outcome's own detail:
     `error = str(errors[-1]).splitlines()[0] if errors else (outcome.detail or "no method succeeded")`.
     One line, plus one parametrized case in `tests/test_render.py:952`.
   - **If we skip it:** The user sees a reconfigure fail with a wrong, generic reason and cannot act
     on it.

4. **Headless asks a second presence question that can disagree with the plan** — Medium
   (`setup.py:1514-1524`, `installer/app.py:111`, compare `setup.py:1136-1141`)
   - **What this is:** The TUI binds `install_tool(..., present=version_refresh.is_present)`, so the
     engine's ALREADY_INSTALLED short-circuit reads the same state the plan used (D-04, L-20-09).
     Headless `run_wizard` keeps the default `install=install_tool`. With `present=None`, the engine
     falls back to the plain PATH `is_installed`.
   - **Problem:** The two answers differ whenever the service looks through this installer's own
     shim. Example: the user removes `~/.local/share/pnpm`, and the installer's pnpm guard shim stays
     in `~/.local/bin`. The pass looks through the shim, finds no real pnpm, and plans pnpm as
     "will install". In headless, `which pnpm` finds the shim, so the engine answers
     ALREADY_INSTALLED. The row ends as `skipped — became present before it ran` with exit 0, and
     pnpm is still missing. The TUI installs it.
   - **Fix:** Build the bound install once in `_build_services`:
     `install = partial(install_tool, present=version_refresh.is_present)`. Return it there, delete
     the `_install` closure in `_build_app`, and pass `install=install` to `run_wizard` in `main`. One
     test: a headless run with a state that says missing and an `is_installed` that says present
     still calls the method.
   - **If we skip it:** Headless can report a false "skipped" with a clean exit for exactly the
     tools that the plan said it would install.

## Should fix

5. **A successful `u` retry never clears an earlier failed `u`** — Low
   (`installer/wizard_app.py:3008-3028`)
   - **What this is:** `on_tool_updated` records a failed direct update as a plan-shaped outcome.
     `_record` keeps the latest outcome per tool id ("latest wins").
   - **Problem:** A successful update returns before it records anything. Example: `u` on rg fails
     because the network is down, then `u` again succeeds. `outcomes["rg"]` still says failed, so the
     session exits 1 although the latest attempt on rg worked. This breaks the "latest wins" rule
     that `_record`'s own docstring states.
   - **Fix:** Record the success too. When `message.outcome.status == "updated"`, call
     `self._record(RowOutcome(PlanRow(message.tool_id, Disposition.UPDATE, ""), "done"))`. Leave
     refusals as they are. Add one test: fail, then succeed, gives `_session_exit_code(app) == 0`.
   - **If we skip it:** Scripts and the user see exit 1 after a session that ended clean.

6. **`Install` and `with_sensitive_confirm` are left over from `run_installs`** — Low
   (`installer/session.py:61-124`, `installer/session.py:292-320`, `installer/session.py:482`)
   - **What this is:** `Install` was the protocol of the deleted `run_installs`.
     `with_sensitive_confirm` binds a confirmation callback for "callers `run_wizard` (plan 14-04) and
     the in-TUI execute path (plan 14-05)". Neither of those callers uses it anymore.
   - **Problem:** The only caller left is `execute_plan:482`. It wraps `_with_force(...)`, and
     `_with_force` already accepts and forwards `confirm_sensitive_action`. Two wrapper layers and a
     protocol now exist only for each other and for three tests
     (`tests/test_session.py:813-910`), and the docstring points at callers that are gone.
   - **Fix:** Have `_with_force(install, force_ids, confirm)` set
     `kwargs["confirm_sensitive_action"] = confirm` itself. Delete `Install`,
     `with_sensitive_confirm` and their tests, and keep the `_with_force` behavior test.
   - **If we skip it:** About 65 lines of indirection that a reader has to trace on every change to
     the install seam.

7. **Other leftovers of the deleted selection flow** — Low
   (`installer/selection.py:9-29`, `setup.py:151-153`, `installer/app.py:104`)
   - **What this is:** These pieces only fed the questionary category/tool checkboxes.
   - **Problem:** `Choice`, `categories` and `tools_in` have no production caller now that
     `category_choices`, `tool_choices` and `Prompter.select_*` are gone. Only
     `tests/test_selection.py` imports them. The `tag-installed`, `tag-missing` and `tag-dim` entries
     of `_STYLE` styled the deleted `_tag_class` output. `run_wizard`'s `platform` parameter is never
     read: its body uses `refresh.platform` (`app.py:131,158`). A caller can pass a platform that is
     silently ignored.
   - **Fix:** Delete the three selection names and their tests, delete the three style lines, and
     drop the `platform` parameter from `run_wizard` and from its call in `setup.py:1514`.
   - **If we skip it:** About 30 dead lines, and one misleading parameter.

8. **`Resolution.order`, `dragged_in` and `warnings` have no reader** — Low
   (`installer/deps.py:36-44`, `installer/deps.py:139-160`)
   - **What this is:** `resolve_dependencies` still computes the old action-only order (a second
     topological sort), the dragged-in ids and the warning strings.
   - **Problem:** Its only production caller, `build_plan`, reads `closure`, `blocked` and
     `requested_by`. The `unknown tool` warnings are now built and dropped, because nothing prints
     them (`render_dependency_notice` is gone). Only `tests/test_deps.py` asserts the three fields.
   - **Fix:** Delete `order`, `dragged_in`, `warnings`, the `runnable`/`ordered` topo call and the
     `warnings.append` lines. Keep the `Blocked.reason` text. Port the `test_deps` order assertions
     to `closure`.
   - **If we skip it:** A second ordering stays in the code, even though the constraint says
     `order_for_install` plus `closure` is the only one.

9. **The runnable set and the post-run report are copied** — Low
   (`installer/session.py:850-856`, `installer/execute_screen.py:77-85`, `installer/app.py:143-145`;
   `installer/execute_screen.py:890-897`, `installer/app.py:166-176`)
   - **What this is:** Three places say which dispositions run. Two places print the same seven
     renderers in the same order after a run.
   - **Problem:** `app.py` writes the set as "not SKIP and not BLOCKED", while the other two list five
     members. Phase 22 already plans `Disposition.MANUAL` (D-17). The day it lands, headless will ask
     "Run this plan?" for a manual-only plan, while the TUI says "enter continue". The renderer lists
     will drift the same way.
   - **Fix:** Export one `RUNNABLE` frozenset from `session.py` and use it in all three places. Add
     `render_run_report(outcomes, console)` to `render.py` and call it from both places.
   - **If we skip it:** The next disposition or report section must be added in five places.

## Nice to have

10. **`_row` repeats itself** — Low (`installer/session.py:626-787`, `installer/session.py:551-554`,
    `installer/session.py:579-583`)
    - **What this is:** One 160-line function with 13 `PlanRow(...)` constructors.
    - **Problem:** The off-policy reason ("managed by X; the catalog installs it via Y") is written
      twice (`:714-719` and `:741-746`), and a wording fix must hit both. Every constructor repeats
      `health=state.health, ownership=state.ownership`. Two small branches are also redundant. The
      `row.ownership is None` UPDATE branch cannot run, because `_row` always sets `ownership` on an
      UPDATE row. The crash detail at `:582` re-implements `_first_line`.
    - **Fix:** Add one `_off_policy_reason(tool, ownership, platform)` helper, and one local
      `make(disposition, reason, **extra)` that fills in id, requester, health and ownership. Delete
      the dead ownership branch, and use `f"{type(exc).__name__}: {_first_line(exc)}"` for the crash
      detail.
    - **If we skip it:** About 40 lines of copy that a reader must diff by eye.

## Checked and fine

- `execute_plan` never runs a SKIP or BLOCKED row. Only REPAIR and REINSTALL rows get
  `repair=True`. Headless never passes `reinstall`, so `--yes` cannot turn a skip into a reinstall.
- Zero sudo: the only "sudo" in the plan path is the BLOCKED reason text. `update_refusal` is the one
  predicate that both the review and `UpdateService` use, so the review never promises an update
  that the engine refuses.
- Per-repo steps run through `sh -c 'cd -- "$1" && shift && exec "$@"'` with the argv kept as
  separate parameters. `_valid_cwd` uses `lstat`, so it refuses a relative path, a missing path and
  a symlink. A step kind outside `ConfigStepKind` is refused. All of this is tested.
- The wait-token logic ignores a publication that arrives after `esc`. `_cancelled_wait` making the
  next Enter wait again is deliberate and pinned by
  `test_a_late_publication_after_esc_starts_nothing`. It means the user never starts a plan they
  have not seen.
- After a run, the selection is `_staged ∩ retained(outcomes)` (L-20-07). `esc` before a run
  dismisses with `None`, which leaves the selection untouched. A crash outside `execute_plan` is
  completed as not_attempted by `_complete`.
- "moving it there" no longer appears anywhere in `installer/`.

Verdict: fix 1, 2, 3 and 4 first.
Lean: about -180 lines possible (6-10).
Not checked: I did not run a full headless `--all` end to end, because that installs. Finding 1 was
reproduced with the real `_build_services` on the pack subset under a scratch HOME. I only read
`scripts/container-e2e-verify.sh` and did not execute it. I did not re-review the 8k lines of test
changes beyond the cases the findings cite.
