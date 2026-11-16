# Phase 23: Configuration as a lifecycle step - Pattern Map

**Mapped:** 2026-11-06
**Inputs:** 23-SPEC.md, 23-CONTEXT.md, 23-RESEARCH.md (reuse list + drift D1-D14), 23-UI-SPEC.md (d87dce0), RUN-LEDGER `| 23 |` rows (research Q1-Q9, UI O1-O7)
**Files analyzed:** 24 new/changed units
**Analogs found:** 21 / 24 (3 partial / no analog, listed at the end)

Ledger overrides applied: rtk out (Q2: delete the `rtk-register` hook, keep the catalog entry); graphify has no hook pair (Q1); Claude attribution `""` strings; opencode prefers an existing `opencode.jsonc`; cursor key equal to the CLI default may be replaced, revert only if still ours (Q5); cursor model migration writes nothing (Q6); VS Code `update.mode` not on Linux (Q7); only the current OS's `terminal.integrated.defaultProfile.<os>` (Q8); alias migration at launch + uninstall, idempotent, legacy list (Q9); no new CLI flags (O1); failed unregister stops that tool's removal (O4).

All line numbers verified on HEAD d87dce0. All paths are git-tracked source.

## File Classification

| New/Modified unit | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/postinstall.py` hook pairs `(register, unregister)` with `hosts` | service (closed table) | request-response (argv) | `installer/postinstall.py:67-146` `_codegraph_mcp_register` | exact |
| delete `_AGENT_HOST_IDS`/`present_agent_hosts`, `rtk-register` | removal | - | `installer/postinstall.py:26-46, 149-240` | n/a |
| host list = `skill_lifecycle.present_harnesses` | utility | transform | `installer/skill_lifecycle.py:633-641` | exact (reuse) |
| `installer/model.py` `POSTINSTALL_HOOK_NAMES`, `ConfigStepKind` += `hook_register`, `zshenv_shell` | config | - | `installer/model.py:22, 368-391` | exact |
| `receipts.record` carries `previous.hooks`; `record_hooks(tool, name, hosts)` | model/store | file-I/O | `installer/receipts.py:227-300` (`_build_receipt`, `record`, `_proven_before` carry-forward) | exact |
| config-write ledger `~/.local/state/tools-installer/config/<agent>.json` | store | file-I/O | `installer/receipts.py:90-158` (dir, path, `_write_unlocked`, `read` fail-closed) | role-match |
| `RemovalPlan.unregister` + `remove_tool` preview check | model + service | request-response | `installer/uninstall.py:64-100, 279-300`; `installer/app.py:593-640` | exact |
| end-of-plan host re-sync sweep | service | batch | `installer/session.py:469-603` `execute_plan` loop | role-match |
| hook drift `≈` → `ConfigStep(..., "hook_register")` | service | transform | `installer/version_status.py:1570-1595` terminal facts | exact |
| `_run_step` branches for `hook_register`, `zshenv_shell` | service | request-response | `installer/session.py:374-400` (`terminal_sync` branch) | exact |
| `installer/agent_env.py` + cursor-agent, VS Code, opencode `.jsonc` pick | config | - | `installer/agent_env.py:21-63` | exact |
| new `installer/agent_settings.py` (JSON/JSONC/TOML guarded splice, exact revert) | service | file-I/O + transform | `installer/verify_registry.py:1041-1058` + `installer/shellrc.py:905-933` + `installer/atomic.py:57` | role-match (splice shape) / partial (JSON scanner none) |
| `RunContext` run-option answers | model | - | `installer/session.py:190-202` | exact |
| ExecuteScreen run-option rows + `space` | component | event-driven | `installer/execute_screen.py:454-505` (`_paint_review`, `_idle_keys`, `action_toggle_reinstall`) | role-match |
| `SensitiveActionScreen` keyed by action | component | event-driven | `installer/execute_screen.py:140-175, 784-795` | exact (change in place) |
| `source_shell_init` post-install action | service | file-I/O | `installer/post_install.py:50-77` `_set_login_shell` + `installer/tweaks.py:293-310` `write_tweak` | exact |
| six shell-init `TweakBundle`s; delete four alias bundles | config | - | `installer/tweaks.py:157-215` `BUNDLES` | exact |
| alias migration (launch + uninstall, legacy list) | service | batch | `installer/tweaks.py:303-310` `remove_tweak`; `installer/tweaks.py:221` `_markers` | role-match |
| per-tool bundle removal on uninstall | service | batch | `installer/uninstall.py:537-560, 632-650` | exact |
| Policies rows (shell init, agent, VS Code, desktop SHELL) + `● [yours]` | component + factory | CRUD | `installer/policy.py:512-540` `tweak_policy`, `:650-670` `cache_redirect_policy`; `installer/wizard_app.py:2160-2170` `_state_cell` | exact / role-match for `[yours]` |
| `~/.zshenv` SHELL block | service | file-I/O | `installer/shellrc.py:147-180` `apply_block`/`strip_block`; `installer/env_redirect.py:212-240` rc redirect trio | exact |
| `environment.d` SHELL | service | file-I/O | `installer/env_redirect.py:39-76, 96-190` | exact (generalize) |
| kitty/WezTerm region bodies + SHELL | service | file-I/O | `installer/terminal_shell.py:78-115, 150-176, 410-460` | exact |
| tealdeer `tldr --update` hook | service | request-response | `installer/postinstall.py:121-146` (`except CommandError` → warning) + `installer/update.py:473-489` | exact |
| OMZ `set_theme`; `write_plugins` passes `omz_root` | utility | transform | `installer/omz.py:147-153, 378, 432-460, 530-543` | exact |
| Uninstall review blocks (ConfirmUninstall 3/3b, CLI preview) | component | request-response | `installer/wizard_app.py:2769-2800`; `installer/render.py:380` `render_uninstall` | role-match |
| run report sections, headless prompts | component | request-response | `installer/render.py:294-380`; `setup.py:1429` `CallbackPrompter` | exact |
| post_install.py:46 "later step" copy (drift D12) | copy fix | - | `installer/post_install.py:41-47` | n/a |

## Pattern Assignments

### Hook pairs (CONF-01, CONF-03; D-01, D-04, D-05)

**Analog:** `installer/postinstall.py:67-146` (`_CODEGRAPH_TARGETS`, `_codegraph_mcp_register`).

Copy:
- Closed id map keyed by host id, declared in output order (`:67-72`). Re-key from catalog ids to harness ids (`cursor-agent` → `cursor`), per research CONF-03.
- Filter: `present = [target for host, target in MAP.items() if host in hosts]`; empty → `return None` without running anything (`:121-124`).
- Absolute binary via `bin_dir(_resolve_bin_override(method)) / "codegraph"` (`:126`).
- `try: runner([...]) except CommandError as exc: return f"... failed: {exc}"` (`:127-145`). A hook never raises.
- Dispatch by name, unknown name → `None` (`run_postinstall`, `:249-266`).

Change: `PostinstallHook = Callable[[Method, Runner, Mapping[str, Tool]], str | None]` (`:49`) becomes a `(register, unregister)` pair taking `(method, runner, hosts: frozenset[str])` and returning the hosts it actually registered plus a warning. Delete `_AGENT_HOST_IDS`/`present_agent_hosts` (`:22-46`) and `_rtk_register`/`_RTK_*`/`_resolve_rtk_binary` (`:149-240`). herdr: map + pair only, not wired (drift D4). graphify: none (Q1).

Callers to update: `installer/engine.py:333`, `installer/update.py:401, 473-489` (keep the `except Exception` isolation boundary, `update.py:486-488`).

**Tests to mirror:** `tests/test_postinstall.py:45` (CSV from present hosts), `:75` (no host → no call), `:95` (absolute binary), `:125` (CommandError → string), `:139/:159` (dispatch, unknown name), `:168` (every presence subset, parametrized). Add the unregister mirror of each and "unregister uses receipt hosts, never present hosts".

### Host list (CONF-03)

**Analog:** `installer/skill_lifecycle.py:633-641` `present_harnesses(home, which)`. Inject at the caller (CONTEXT "Established Patterns"); the end sweep must recompute, never reuse a start-of-run set (drift D14). Tests: `tests/test_skill_lifecycle.py` presence tests.

### `receipt.hooks` carry-forward (CONF-01/02; D-02, research Pitfall 1)

**Analog:** `installer/receipts.py:227-247` `_build_receipt` (writes `hooks={}` at `:246`) and `record` `:250-300`, which already reads `previous = read(tool.id)` and carries proven artifacts forward via `_proven_before(previous, entry)`.

Copy: add `hooks` as a keyword of `_build_receipt`; in `record` pass `hooks=previous.hooks if previous else {}`. New `record_hooks(tool_id, name, hosts)` = read → `dataclasses.replace(receipt, hooks={..., name: tuple(sorted(hosts))})` → `write` under `_WRITE_LOCK` (`:52`). Both record call sites (`engine.py:321`, `update.py:391`) inherit it.

**Tests to mirror:** `tests/test_receipts.py:175` (round trip), `:637` (record writes), `:703` (record failure removes previous). Add "update/repair re-record keeps hooks".

### Config-write ledger (D-08)

**Analog:** `installer/receipts.py:90-158` (`default_receipts_dir`, `receipt_path` with id validation, `_write_unlocked` atomic + symlink refusal, `read` fail-closed with `_MAX_RECEIPT_BYTES`). Same module per D-08, separate dir `config/`, one file per agent. Entry schema (planner's choice): `{file, key_path, value, prior}` (prior needed for the cursor Q5 rule).

**Tests to mirror:** `tests/test_receipts.py:242, 353, 363, 391, 397, 411` (fail-closed reads, unsafe ids, symlink refusal), `:196` (suite sandbox redirect). Extend `tests/conftest.py:34` `_GUARDED_DOTFILES` with `.zshenv`, and add dir-listing guards for `.config/environment.d` and `.local/state/tools-installer/config` (research Pitfall 12; do not fingerprint live CLI settings files).

### Removal unregister (D-04, O4)

**Analog:** `installer/uninstall.py:64-100` `RemovalPlan` (frozen; append fields with defaults like `config`/`hint`), `removal_plan` `:279-300`, and `installer/app.py:593-640` `remove_tool`.

Copy: add `unregister: tuple[tuple[str, ...], ...] = ()` built from `receipt.hooks`. In `remove_tool`, add `or unregister != fresh.unregister` next to `argv != fresh.argv` (`app.py:615`), run each unregister before `argv` through `runner`, and on `CommandError` return `ToolRemoval(tool.id, False, ...)` exactly like the argv failure branch (`app.py:633-640`) so nothing else is removed (O4).

**Tests to mirror:** `tests/test_uninstall.py` removal_plan level tests; `tests/test_app.py` remove_tool "changed since the preview" and "failed command deletes nothing" cases; `tests/test_uninstall_e2e.py`.

### End-of-plan re-sync sweep (CONF-02; D-03)

**Analog:** `installer/session.py:469-603` `execute_plan`. Append after the row loop, before `return outcomes`: if any outcome row with disposition INSTALL/REPAIR/REINSTALL ended `done`, for each catalog tool with `tool.postinstall` and a receipt with hooks, `new = present_harnesses(...) ∩ targets − recorded`; register only `new`, then `record_hooks`. Use `ran_anything` (`session.py:245`) as the style model for the predicate. Inject `present_harnesses` through `RunContext` (`:190-202`, add an optional field at the end) so tests stay hermetic.

**Tests to mirror:** `tests/test_session.py:413, 716` (execute_plan with fakes). Add SPEC AC "claude not re-run".

### Hook `≈` and RECONFIGURE (D-02)

**Analog:** `installer/version_status.py:1570-1595` (drifted name → `_ConfigFacts((reason,), (ConfigStep(text, kind),))`; exceptions become an `unchecked` note, never a failed pass). Add `"hook_register"` and `"zshenv_shell"` to `ConfigStepKind` (`installer/model.py:368`); `_STEP_KINDS` (`session.py:371`) picks them up automatically. Add `_run_step` branches shaped like `terminal_sync` (`session.py:380-386`: missing seam → `_StepResult(failed=...)`, exception → `first_line(exc)`).

**Tests to mirror:** `tests/test_version_status.py` terminal drift facts; `tests/test_session.py:716-790` reconfigure tests.

### Agent paths (D-06, Q5, Q8, drift D11)

**Analog:** `installer/agent_env.py:21-63`. Add `cursor-agent` (`~/.cursor/cli-config.json`) and `vscode` (`~/.config/Code/User/settings.json`; macOS `~/Library/Application Support/Code/User/settings.json`) entries in the same dict. opencode: return `opencode.jsonc` when it exists, else `opencode.json`; keep "does not inspect the filesystem" honest by doing the pick in `agent_settings`, or amend the docstring. Tests: `tests/test_agent_env.py`.

### `installer/agent_settings.py` (D-06, D-07; CONF-08/09/12)

**Analogs (compose, do not copy code):**
1. `installer/verify_registry.py:1041-1058` `apply_registry_edits`: parse original → compute expected doc → text splice → re-parse → `new_doc != expected_doc` → raise. This is the guard for every format.
2. `installer/shellrc.py:905-933` `_snapshot`/`_snapshot_matches`: read once via `O_NOFOLLOW`, re-check identity+bytes right before commit; promote to public (research Standard Stack: no third copy).
3. `installer/atomic.py:57` `atomic_write_text(path, text, mode=...)`.
4. TOML insert: research §Code Examples "TOML top-level insert" (keys before the first `[` table line).
5. JSON/JSONC insert: research sketch `_insert_member` only; **no in-repo string/comment-aware JSON scanner exists** (see No Analog).

Rules from ledger: absent keys only; existing other value → "set by you"; cursor value equal to documented CLI default may be replaced and the prior value goes to the ledger (Q5); revert removes only spliced keys whose values still match; refusal (unparsable) writes nothing.

**Tests to mirror:** `tests/test_verify_registry.py:2775, 2799, 2827` (guard refuses a broken / unintended edit); `tests/test_shellrc.py` snapshot refusal tests; `tests/test_atomic.py`. Add byte-identical round trip (apply then revert) per format, `//` inside a string, trailing commas, cursor Q5.

### Run options in the review (D-09; UI-SPEC §1, O2)

**Analog:** `installer/execute_screen.py:454-505`. `_paint_review` adds `Option`s to `#plan-rows`; append a disabled heading option and `Option(..., id=f"run-opt-{name}")` after the plan rows. `_idle_keys` (`:483-489`) gains `space option` only when option rows exist. `action_toggle_reinstall` (`:490-505`) is the model for the new `action_toggle_option`: guard `started/finished/_start_requested`, read highlighted id, refuse with `self.status.set(..., "warn")`, mutate a set, repaint. `r` already no-ops on a non-tool id via `_row_for` (`:487`). Answers go into `RunContext` (new optional trailing fields). Headless `--yes`: all off.

**Tests to mirror:** `tests/test_execute_screen.py:3021, 3083` (review rows/highlight), `:1145` (unattended never asks), `tests/test_layout_80x20.py` (78-cell fit).

### Keyed SensitiveActionScreen + `source_shell_init` (D-11; UI-SPEC §2, drift D7, D13)

**Analogs:** `installer/execute_screen.py:140-175` (modal; prompt hardcoded at `:160-167`), `:784-795` `_ask_sensitive_action(self, tool_id, _action)` (action ignored today); `installer/post_install.py:50-60` `_set_login_shell` (`confirm is None or not confirm(tool.id, name)` → `()`), table `:63-65`; `installer/model.py:125-129` both tuples.

Copy: `SensitiveActionScreen(tool_id, action)` picks prompt/choice labels from a dict keyed by action; `set_login_shell` text byte-for-byte unchanged. New action `_source_shell_init` follows `_set_login_shell`'s guard, then `write_tweak(bundle_for(tool.id), rc_path)` (`tweaks.py:293-300`); starship also calls `omz.set_theme(content, "")`. Amend the module doctrine at `post_install.py:13-16` (it now writes `~/.myshellrc`).

**Tests to mirror:** `tests/test_execute_screen.py:1057, 1145, 1165`; `tests/test_post_install.py` (`confirm=None` skip, declined skip).

### Shell-init bundles and alias removal (D-10, D-11, Q4, Q9)

**Analog:** `installer/tweaks.py:157-215` `BUNDLES` entries (`TweakBundle(id, label, description, platforms, body, requires=(...))`, e.g. docker `:158-165`). Bundle id = tool id; body guarded by `command -v X >/dev/null &&`. Delete `claude-skip` (`:173-179`), `codex-skip` (`:180-186`), `opencode-auto` (`:194-201`), `cursor-agent-model` (`:202-...`, body `_CURSOR_AGENT_BODY` `:122-140`).

Migration: keep a `LEGACY_ALIAS_BUNDLE_IDS` tuple; strip with `_markers(id)` (`tweaks.py:221`) + `strip_block`, same shape as `remove_tweak` (`:303-310`), then write equivalent keys via `agent_settings` (cursor: write nothing, tell `/model`, Q6). Run at launch (TUI + headless) and inside `run_uninstall`.

**Tests to mirror:** `tests/test_tweaks.py` (block render/idempotence), `tests/test_policy_tweaks.py:13-41`, `tests/test_rcclean.py` for legacy blocks.

### Per-tool shell-init removal (D-11)

**Analog:** `installer/uninstall.py:537-560` `active_policies((bundle,), rc_path=..., bin_dir=...)` then `:632-650` `sweep_policies(list)` (per-policy failure isolation). Never `sweep_tweaks`. Tests: `tests/test_uninstall.py` active/sweep tests, `tests/test_uninstall_e2e.py`.

### Policies rows and `● [yours]` (UI-SPEC §3, O7)

**Analogs:** `installer/policy.py:121-160` `Policy` (append new optional fields only, per the comment at `:146-147`, e.g. effect-kind label and a tri-state reader); `tweak_policy` `:512-540` for shell-init rows (already covers `tweak:<id>` ids and hard requires); `cache_redirect_policy` `:650-670` for the desktop-SHELL row (macOS/other branch on `platform_os == "macos"`); `installer/wizard_app.py:2160-2170` `_state_cell` (`None` → empty, `_drift` → `! [drift]`, else on/off). Add a `_yours` set and `Text("● [yours]", style="green")`; `space` on a yours row → `warn`, no write.

**Tests to mirror:** `tests/test_policy_tweaks.py`, `tests/test_policy_env_redirect.py`, `tests/test_policies_e2e.py`, `tests/test_wizard_app.py` state-cell tests, `tests/test_layout_80x20.py`.

### `~/.zshenv` SHELL block (D-15, O6)

**Analog:** `installer/env_redirect.py:192-240` (`render_block`, `write_rc_redirect`, `remove_rc_redirect`, `rc_applied`) over `installer/shellrc.py:147-180`. Same trio with `# >>> tools-installer shell >>>` markers; `≈` via `ConfigStep(..., "zshenv_shell")`. Amend `.claude/architecture.md` ownership rule (research Pitfall 10). Tests: `tests/test_env_redirect.py` rc trio, `tests/test_shellrc.py:146-290`.

### environment.d SHELL (D-16)

**Analog:** `installer/env_redirect.py:39-76` `CacheRedirect`, `target_path` `:96`, `render_conf` `:126`, `write_linux_redirect`/`remove_linux_redirect`/`linux_applied` `:141-190`. Generalize the target to accept an absolute resolved value; keep `OWNERSHIP_SENTINEL` (`:28`). Bun redirect regression: `tests/test_env_redirect.py:37-51`, `tests/test_policy_env_redirect.py`.

### kitty/WezTerm SHELL lines (D-14 shrunk, drift D5/D6)

**Analog:** `installer/terminal_shell.py:150-176` `_wezterm_content`, kitty body at `:453-457`, `_replace_owned_region` `:78-115`, `_write_if_changed(write=)` `:279`. Only extend the bodies inside the same region. Tests: `tests/test_terminal_shell.py:114, 678` (malformed region, dry-run drift). Expect every configured terminal to drift once (research Pitfall 11).

### tealdeer cache (D-18)

**Analog:** `_codegraph_mcp_register` error shape (`postinstall.py:127-146`); update re-dispatch is free via `update._run_postinstall` (`update.py:473-489`). Add name to `POSTINSTALL_HOOK_NAMES` (`model.py:22`); cache dir into tealdeer `config_paths` in `installer/registry.toml`. Tests: `tests/test_postinstall.py:125`, `tests/test_update.py` postinstall re-dispatch.

### OMZ theme and `$ZSH` (D-12, D-13; drift D8)

**Analog:** `installer/omz.py:147-153` `_sourced_oh_my_zsh` (insert index), `ensure_zshrc_template(zshrc_path, root=None)` `:378`, `write_plugins` `:432-460` (calls the template without `root` at `:450, :456`), `omz_root` `:530-543`. `set_theme(content, name)` is a pure text function next to `_sourced_oh_my_zsh`; insert only when no `ZSH_THEME=` line. Tests: `tests/test_omz.py:92-130` (template ordering, idempotence); add a written `export ZSH=` assert for a custom root.

### Uninstall review blocks and CLI preview (UI-SPEC §6, O5)

**Analog:** `installer/wizard_app.py:2769-2800` `ConfirmUninstall(summary, review)`; `installer/render.py:380` `render_uninstall`. New environment pseudo-row `agent/editor settings` follows existing environment pseudo-rows in `UninstallScreen`. Tests: `tests/test_wizard_app.py` ConfirmUninstall, `tests/test_render.py`, `tests/test_cli.py` uninstall preview.

### Run report and headless prompts (UI-SPEC §4, §7)

**Analog:** `installer/render.py:294` `render_run_report`, `:325` `render_postinstall_warnings`, `:357` `render_post_install_handoff`; headless confirm via `setup.py:1429` `CallbackPrompter(ask_confirm=_ask_confirm)` for the `source_shell_init` sentence (default no; `--yes` passes `confirm=None`). Tests: `tests/test_render.py`, `tests/test_setup.py`.

### Copy fix (drift D12)

`installer/post_install.py:46` reword to name the terminal sync; test: zsh REINSTALL without chsh ends with terminal sync called (`tests/test_session.py` + `ran_anything`).

## Shared Patterns

- **Atomic write + compare-before-commit:** `installer/atomic.py:57`; `installer/shellrc.py:905-933`. Apply to agent_settings, ledger, `.zshenv`.
- **Guarded splice + semantic re-parse:** `installer/verify_registry.py:1041-1058`. Apply to every settings format.
- **Owned marker blocks:** `installer/shellrc.py:147-180`, `installer/tweaks.py:221, 293-310`. Apply to bundles, `.zshenv`, alias migration.
- **Never-raise warnings:** `installer/postinstall.py:144-146`, `installer/update.py:486-488`. Apply to every hook.
- **Sensitive actions default off; `confirm is None` → skip:** `installer/post_install.py:57-59`.
- **Frozen dataclasses grow by appended defaulted fields:** `installer/policy.py:146-147`, `RemovalPlan`, `RunContext`.
- **Preview equals effect:** `installer/app.py:612-617`, `installer/uninstall.py:537-560`.

## No Analog Found

| Unit | Reason | Use instead |
|---|---|---|
| JSON/JSONC string- and comment-aware object scanner (agent_settings) | No in-repo JSON text splicer; `agent_policy._write_json` re-serializes and is rejected by D-06 | RESEARCH §Code Examples sketch + verify_registry guard |
| Settings tri-state with "yours" (ledger + live value) | Policies are binary + drift today | Extend `_state_cell`; logic new |
| herdr hook pair | herdr not in registry (drift D4) | Copy codegraph shape; leave unwired until Phase 24 |

## Metadata

**Search scope:** `installer/`, `setup.py`, `tests/`, phase docs. **Pattern extraction date:** 2026-11-06.
