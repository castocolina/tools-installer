# Phase 23: Ponytail reuse pass (plans 23-01 .. 23-16)

Read-only audit at full level. Scope: every new function, module, class, dataclass, field, constant and seam in 23-01..23-16, checked against existing code with `codegraph explore` after `codegraph sync`. Line numbers are from the tree at `09fcec2`. None of the Phase 23 plans had landed when this was written.

Locked decisions were not re-argued: 23-CONTEXT D-01..D-18, 23-SPEC, the approved 23-UI-SPEC (with its 2026-11-06 amendment), and the binding `| 23 |` RUN-LEDGER rows (research Q1-Q9, UI O1-O7, the alias decision, planner sign-offs 1-10, plan-checker iteration 2).

**The PLAN.md files were not edited.** Every item below is a binding executor note. Apply it inside the named plan without replanning. "Plan text change" says what to read in place of the plan's text. When an item adds a file to a plan, the wave check is given: no other plan in that wave touches the file.

Severity: **Important** means duplicated logic at a trust boundary, a behaviour bug the plan as written would ship, or code that should not exist. **Minor** means a smaller diff with the same behaviour.

## 23-01 -- hook hosts and receipt carry-forward

No important finding. `present_hosts()` is the one test seam for host presence and is kept. `_resolve_binary(method, cmd)` is the right generalization of `_resolve_rtk_binary` (postinstall.py:190-204). Its brew half becomes shared in 10-1.

### 01-1 -- Minor -- Task 1 (`_real_home_fingerprint`)
- Proposed: two new entries, `<environment.d>` and `<config-ledger>`, each a count plus dir-mtime listing.
- Existing: `tests/conftest.py:139-146` already builds exactly that shape for `<receipts>`.
- Plan text change: turn the `<receipts>` block into one loop over `{"<receipts>": …/receipts, "<environment.d>": ~/.config/environment.d, "<config-ledger>": …/tools-installer/config}`. Do not paste the block twice more.

## 23-02 -- settings splice engine

The snapshot promotion (shellrc → atomic) is the right reuse, and no other compare-before-commit copy exists (`rg O_NOFOLLOW` finds only shellrc.py and atomic.read_capped). No in-repo JSON/JSONC scanner or TOML error-position parser exists (`rg "jsonc|at line|TOMLDecodeError"`).

### 02-1 -- Minor -- Tasks 1-3 (the re-parse guard)
- Proposed: "every splice function re-parses its result and raises `SettingsEditRefused` unless the document equals the expected one".
- Existing: the guard is `verify_registry.apply_registry_edits`'s tail (verify_registry.py:1052-1057).
- Plan text change: write it once, as one private `_guarded(new_text, fmt, expected) -> str`. `insert_key`, `remove_key` and `replace_value` return through it. No inline copy per function.

## 23-03 -- Oh-My-Zsh root and theme writer

### 03-1 -- Important -- Task 2 (the theme ownership record)
- Proposed: a second closed comment-block record in `~/.myshellrc` (`omz-theme` markers), "written with `shellrc.apply_block` and read like `_record`", plus `owned_theme`.
- Existing: `omz._record` (omz.py:277-303) is the closed-block reader, with the orphan-begin rule and last-closed-block-wins. `_record_owned` (:322-326) and `_clear_owned` (:329-335) are its writer and its clear. That reader guards an ownership claim, so a second copy can drift on the orphan-marker rule.
- Plan text change: give `_record`, `_record_owned` and `_clear_owned` `begin`, `end` and body-prefix parameters. The plugin callers pass `_OWNED_BEGIN`/`_OWNED_END`/`_ADDED_PREFIX` unchanged, so the existing omz tests stay green. `owned_theme` is `_record(state_path, THEME_BEGIN, THEME_END, '# ZSH_THEME=')` reduced to its one value. Write no second line-walking reader.

### 03-2 -- Important -- Task 2 (`apply_theme` write order)
- Proposed: "changed → atomic write of the zshrc, then the record set to `name`".
- Existing: `write_plugins` (omz.py:439-477) documents and implements the only order that fails safe: reserve the record, commit the `.zshrc` edit, and roll the record back on `OSError`. Recording after the edit strands the claim. Here a failed record write would leave the installer's own `robbyrussell` reading `yours` forever, so starship could never replace it (D-13).
- Plan text change: `apply_theme` reserves the record (`_record_owned`), then writes `.zshrc`, and on `OSError` restores the previous record (or clears it when there was none) and re-raises. This is the `write_plugins` order. Add one test: the `.zshrc` write raises, and the record is unchanged.

## 23-04 -- `.zshenv` block, terminal regions, environment.d

### 04-1 -- Important -- Task 3 (`write_linux_redirect` with an absolute value)
- Proposed: `CacheRedirect.absolute` and `shell_redirect(zsh_path)` reuse `write_linux_redirect` unchanged.
- Existing: `write_linux_redirect` ends with `target_path(redirect, home).mkdir(parents=True, exist_ok=True)` (env_redirect.py:158). That line creates the cache directory. With `absolute=zsh_path` it targets the zsh binary. When the binary exists, `FileExistsError` fails the write. When it does not, the call creates a directory at that path. The plan's test passes the literal `/home/linuxbrew/.linuxbrew/bin/zsh`, which is a real, user-writable prefix on the developer's host, so the test would mutate the host (AGENTS.md rule).
- Plan text change: skip the mkdir when `redirect.absolute` is set (one condition, with a one-line why comment). `test_shell_redirect_writes_and_removes_its_conf` uses a zsh path under `tmp_path` (e.g. `tmp_path / "bin" / "zsh"`, created as a file) and also asserts that no directory was created at that path. The `/home/linuxbrew/...` literal may appear only in tests that never write (render, cell width).

### 04-2 -- Minor -- Task 1 (`zshenv_path`)
- Proposed: a new `$ZDOTDIR`-aware resolver that "mirrors `zshrc_path`".
- Existing: `locations.zshrc_path` (locations.py:8-21) is that resolver.
- Plan text change: `def zshenv_path(home, environ): return zshrc_path(home, environ).with_name(".zshenv")`. One resolver for both files. Keep `test_zshenv_path_follows_zdotdir`.

## 23-05 -- unregister builders, herdr, tealdeer

`NotingRunner` copies the `MethodAwareRunner` protocol shape (run.py:23-29). A separate protocol is right: widening `MethodAwareRunner` would break every fake that lacks `note`. `unregister_argvs` and `host_labels` have no analogue.

### 05-1 -- Important -- Task 1 (`hook_method`)
- Proposed: `hook_method(tool, receipt)`: the method whose `method_key` equals the receipt key, else the only method of the receipt's kind, else None.
- Existing: `uninstall._recipe_argv` already inlines exactly this rule (uninstall.py:256-258: `keyed = […]`, then `scripts[0] if len(scripts) == 1`). Line 254 already requires a `script` receipt, and the key hash covers the kind, so the two rules are equivalent. Two copies of "which method was this receipt written for" can drift: one picks by kind, the other by key.
- Plan text change: 23-05 defines `hook_method` as planned. 23-08 (which owns uninstall.py) replaces uninstall.py:256-258 with `method = hook_method(tool, receipt)` (no new file for 23-08; uninstall already imports postinstall there). The existing `_recipe_argv` tests stay green unchanged.

## 23-06 -- settings API and config-write ledger

### 06-1 -- Important -- the decisions' `display_path(path, home)` (also 23-07 `tilde`)
- Proposed: 23-06 adds `agent_settings.display_path(path, home)` ("used by every caller's copy"). 23-07 adds a private `tilde` in version_status with the same job. Together with the existing helper, that makes three.
- Existing: `policy._display_path` (policy.py:96-100): `~/…` under `Path.home()`, else the path verbatim. It has 23 call sites, all in policy.py. agent_settings cannot import policy, because 23-11 makes policy import agent_settings.
- Plan text change: 23-06 moves `_display_path` unchanged to `installer/locations.py` as the public `display_path(path: Path) -> str` (the bottom layer: it imports no installer module). policy.py imports it as `from installer.locations import display_path as _display_path`, so its 23 call sites are untouched. There is no `home` parameter: every test already runs under a scratch HOME (`tests/conftest.py:215-229`). 23-07 (`tilde`), 23-10, 23-11, 23-14 and 23-15 import `locations.display_path`. 23-06 adds `installer/locations.py` and `installer/policy.py` to its files (wave 2: 23-05 touches neither). 23-06 lands in wave 2, before 23-07's wave 3.

### 06-2 -- Important -- the table and `adapters(…, platform_os=…)`
- Proposed: `platform_os` values `"linux"`/`"macos"`. The decisions write "on Linux" for `terminal.integrated.defaultProfile.linux`, and the tests pass `platform_os="linux"`.
- Existing: `Platform.os` is `macos`, `fedora`, `debian` or `arch`, never `linux` (platform.py:34-48). 23-10 passes `ctx.platform.os`. The house rule is in `cache_redirect_policy`'s docstring (policy.py:662-665): "compare against `macos`, never against a `linux` string". A `== "linux"` branch would make a Fedora run write no terminal profile and treat the host as non-Linux.
- Plan text change: every OS branch in `setting_keys`, `adapters` and `settings_file` is `platform_os == "macos"` versus everything else. Add one test calling `apply_setting("vscode", "vscode-lean", platform_os="fedora")` that writes `terminal.integrated.defaultProfile.linux`. 23-15's `HOST_SETTINGS_OS` may stay (`"macos"`/`"linux"`), because it is only ever compared with `macos`.

### 06-3 -- Minor -- Task 1 (`read_ledger` / `write_ledger`)
- Proposed: a ledger reader that "fails closed like `read`" and a writer that "refuses a symlink like `_write_unlocked`".
- Existing: `receipts.read` (receipts.py:169-182) does the capped, no-follow, decoded, `json.loads`, dict-only read. `_write_unlocked` (:117-121, :147-149) does the symlink refusal, `ensure_dir` and `atomic_write_text`.
- Plan text change: extract two private helpers from those lines, `_read_json_object(path) -> dict[str, object] | None` and `_write_json(path, payload)`. `read`, `_write_unlocked`, `read_ledger` and `write_ledger` all call them. `config_ledger_dir()` is `default_receipts_dir().parent / "config"`, so no path literal is repeated.

### 06-4 -- Minor -- receipts.py docstring
- `method_key`'s docstring says "never matched on" (receipts.py:108). `_recipe_argv` already matches on it, and 05-1 names it. 23-06 (owner of receipts.py in wave 2) rewords it: "Matched only to pick the method a receipt was written for; a pin bump changes it."

## 23-07 -- hook drift, re-sync sweep, report

### 07-1 -- Important -- `RunContext.harnesses` should not exist
- Proposed: `RunContext.harnesses: Callable[[], frozenset[str]] | None`, used as `(ctx.harnesses or present_hosts)()` by the `hook_register` step and `_resync_hooks`.
- Existing: 23-01's `postinstall.present_hosts()` is already the one hermetic seam. It is a module-global lookup, the conftest autouse stub answers it with `frozenset()`, and `register_hooks(…, hosts=None)` reads it. A second seam for the same fact is a second way for production and tests to disagree.
- Plan text change: no `harnesses` field. The step and the sweep call `register_hooks(tool, method, ctx.runner)` without `hosts`. Tests use `monkeypatch.setattr(postinstall, "present_hosts", spy)`. For `test_the_sweep_reads_hosts_after_the_rows`, the spy records when it is called. For `test_a_run_without_a_host_install_runs_no_sweep`, it asserts it was never called.

### 07-2 -- Minor -- Task 1 (`_hook_facts` inputs)
- Proposed: "one `present_harnesses(self._skill_home, self._looked_through)` call per pass", plus a `receipts.read` per hook tool.
- Existing: `_scan_packs` already makes that call, wrapped the same way (version_status.py:1311-1314). With the plan as written the pass calls it twice. The tool loop already reads each tool's trusted receipt through `_receipt_evidence` (:1857).
- Plan text change: hoist one wrapped `present_harnesses` call to the top of `_pass`, pass `present` to both `_hook_facts` and `_scan_packs` (which keeps its failure notes), and drop its own call. Prefer to compute the hook fact inside the tool loop from the `receipt` the loop already holds (`facts = config.get(…).plus(_hook_fact(tool, receipt, present))`) over a second read.

### 07-3 -- Minor -- Task 2 (`tilde`)
- Use `locations.display_path` (06-1). Write no private `tilde`.

## 23-08 -- unregister on removal

### 08-1 -- Minor -- Task 1 (applies 05-1)
- Replace uninstall.py:256-258 with `hook_method(tool, receipt)`, as 05-1 says.

### 08-2 -- Minor -- Task 1 (the proven executable)
- Proposed: scan `base.by_tool[tool.id]` for a `link`/`leaf`/`file` artifact named `tool.cmd`.
- Existing: `_recipe_argv` does the same "unique proven artifact by name" match for leaves (uninstall.py:268-276).
- Plan text change: one private `_proven_named(plan, tool_id, name, types) -> ReceiptArtifact | None` (unique match, else None). `_recipe_argv` calls it with `("leaf",)`, and the unregister fill calls it with `("link", "leaf", "file")`.

### 08-3 -- Minor -- Task 1 (the unregister failure line)
- Proposed: "`line` taken like the argv branch".
- Existing: app.py:640 `next((ln for ln in exc.detail.splitlines() if ln.strip()), first_line(exc))`.
- Plan text change: extract it once as `_command_error_line(exc: CommandError) -> str`. Both branches call it.

## 23-09 -- shell-init bundles and install handoffs

### 09-1 -- Important -- `SHELL_INIT_EFFECTS` should not exist
- Proposed: the six bundles take "description = the tool's effect", and `post_install.SHELL_INIT_EFFECTS` repeats the same six verbatim strings for the prompt. 23-11 then reads "the effect" a third time for the Effect column and `shell_init_detail`.
- Existing: `TweakBundle.description` (tweaks.py:40) is the field the Policies Effect column already renders.
- Plan text change: no `SHELL_INIT_EFFECTS`. `sensitive_prompt` formats `{effect}` from `shell_init_bundle(tool_id).description`. 23-11's `shell_init_detail` and the Effect cell read the same field. One copy of each UI-SPEC effect string.

### 09-2 -- Important -- Task 1 (`source_shell_init` yes skips split-mode sourcing) -- orchestrator picks
- Proposed: yes → bare `write_tweak(bundle, ~/.myshellrc)`.
- Existing: the Policies toggle for the same bundle is `tweak_policy(...).apply()`. It also wires `ensure_sourced_from` (policy.py:567-576), because "a tweak sourced only into a ~/.myshellrc that split mode never sources is a silent no-op" (its docstring). `_tweak_ensure_sourced_from` lives in the composition root (setup.py:882-886). So in split link mode, an install-time yes writes a block that no shell reads, while the same Policies toggle works.
- Plan text change: (a) the smallest default is a `shortcut:` comment at the action: "split link mode does not wire ~/.myshellrc here; the Policies row does. Upgrade by injecting the composition root's ensure_sourced_from reader". Add a matching 23-UAT note. (b) The full fix enables through `tweak_policy(bundle, rc_path=…, ensure_sourced_from=<reader>).apply()`, with the reader injected through one optional seam. Pick (a) unless the orchestrator says (b). Either way, write no third copy of the sourcing logic.

### 09-3 -- Minor -- the login-shell prompt literal
- The sentence exists twice today (execute_screen.py:162, app.py:169). `SENSITIVE_PROMPTS` becomes the one copy. 23-12 and 23-13 delete their literals: afterwards `rg "Show a reviewed command to change the login shell" installer/` matches exactly one line, in post_install.py.

## 23-10 -- run options

### 10-1 -- Important -- desktop SHELL resolves a different zsh; `RunContext.which` should not exist
- Proposed: `RunContext.which = shutil.which`, used as `zsh = ctx.which("zsh")` for the desktop-shell option.
- Existing: every other zsh lookup goes through `setup._which_with_brew` (setup.py:637-661), which is `shutil.which` plus the `BREW_BIN_DIRS` fallback. That includes the terminal synchronizer that writes `.zshenv` (setup.py:685, 731) and, per 23-14, the desktop Policies row. CR-04 records why: right after a brew install, zsh is not on this process's PATH. With `shutil.which`, the run writes either no zsh (`zsh not found`) or `/usr/bin/zsh`. The desktop row's `linux_applied` then compares the brew path, so it reads off right after the run wrote the file. The fallback body is also byte-identical to the brew branch of `_resolve_rtk_binary`, which 23-01 generalizes to `_resolve_binary` (postinstall.py:196-203).
- Plan text change: 23-10 moves `_which_with_brew` to `postinstall.which_with_brew(name) -> str | None`, beside `BREW_BIN_DIRS` (postinstall.py:183). `_resolve_binary`'s brew branch becomes `found = which_with_brew(cmd)` with the `bin_dir` fallback after it. setup.py imports it, which removes the copy and its docstring moves along. In tests/test_setup.py, `setup._which_with_brew` becomes `postinstall.which_with_brew` at :853, :1757 and :2014-2040, and `setattr(setup, "BREW_BIN_DIRS", …)` becomes `setattr(postinstall, "BREW_BIN_DIRS", …)`. There is no `RunContext.which` field: `_apply_run_options` calls `which_with_brew("zsh")` through a module lookup, and `test_desktop_shell_option_writes_environment_d` monkeypatches it. 23-14's desktop row uses `which_with_brew`. 23-10 adds `installer/postinstall.py`, `setup.py` and `tests/test_setup.py` to its files (wave 4: 23-09 touches none of them).

### 10-2 -- Minor -- `AGENT_OPTION_IDS`, `ATTRIBUTION_IDS`
- Proposed: two hand-kept tuples that must match the 23-06 table.
- Existing: `receipts.CONFIG_AGENTS` and `agent_settings.setting_keys` (23-06).
- Plan text change: derive both as `tuple(a for a in CONFIG_AGENTS if setting_keys(a, setting, platform_os))`. That gives (claude, codex, opencode, cursor-agent) for `auto-approve` and (claude, cursor-agent) for `no-attribution`. `review_problems` iterates `CONFIG_AGENTS`. `NO_ATTRIBUTION_KEY_IDS` stays a literal, because pi has no ledger agent.

### 10-3 -- Minor -- truncation and paths
- Truncate `set by you` values with `Text(value).truncate(width, overflow="ellipsis")`, the house form (wizard_app.py:1203). Write no helper. Every path goes through `locations.display_path` (06-1).

## 23-11 -- Policies rows

### 11-1 -- Important -- `setting_state` and `setting_facts` classify twice
- Proposed: 23-06's `setting_state` walks the keys and the ledger, and 23-11 adds `setting_facts`, which walks them again with the same unreadable rule.
- Plan text change: 23-11 re-implements `setting_state` over `setting_facts`. `SettingsUnreadable` is raised in one place, inside `setting_facts`. The mapping: `written` → `on`; else `drifted` → `drift`; else `len(already) == len(keys)` → `yours`; else `off`. The 23-06 `test_setting_state_reads_each_state` stays green unchanged and is the regression gate. Write no second classification loop.

### 11-2 -- Minor -- `desktop_shell_policy.owned`
- Drop `owned`. `policy_owned` falls back to `is_active` when `owned` is None (uninstall.py:523-533), so `active_policies(…, extra_policies=(desktop_row,))` finds the file without it. Use `which_with_brew` for zsh (10-1).

### 11-3 -- Minor -- truncation and paths
- Truncate values past 40 cells with `Text.truncate(…, overflow="ellipsis")`, and use `locations.display_path` for `{path}`, as in 10-3.

## 23-12 -- no finding

- The option rows reuse `fold_reason` (render.py:65), and `action_toggle_option` mirrors `action_toggle_reinstall`'s guard, as planned. Delete the login-shell literal per 09-3.

## 23-13 -- no finding

- `Prompter.confirm(default=…)` threads one keyword through the existing seam. The option texts come from 23-10's `run_option_lines`, shared with the TUI. Delete the login-shell literal per 09-3.

## 23-14 -- alias strip and composition

### 14-1 -- Minor -- Task 1 (`strip_legacy_aliases`)
- Proposed: strip each legacy block "with the `remove_tweak` shape over `_markers(alias_id)`", which would be a third read → `strip_block` → write copy.
- Existing: `remove_tweak` (tweaks.py:302-310) reads only `bundle.id`. 23-03 already split `bundle_marker_present(bundle_id, rc)` out of `tweak_present` for the same reason.
- Plan text change: move `remove_tweak`'s body into `strip_tweak_block(bundle_id, rc_path) -> bool` (True when the file changed). `remove_tweak` delegates to it, and `strip_legacy_aliases` calls it per present id.

### 14-2 -- Minor -- the `home` parameter
- Drop `home` from `strip_legacy_aliases`. `LegacyStrip.rc` is `display_path(rc_path)` (06-1). The desktop row resolves zsh with `which_with_brew("zsh")` (10-1).

## 23-15 -- removal reverts and review

### 15-1 -- Minor -- the three revert loops
- Proposed: a per-tool revert after each removal "in both routes", the `revert_settings` pseudo-row revert, and the CLI's always-revert-remaining loop.
- Plan text change: one private `_revert_settings(agent_ids, *, platform_os, config) -> tuple[reverted, kept, warnings]` in app.py, called from `perform_uninstall` and `run_uninstall` for both the per-tool and the whole-environment case. The `config` skip and the `could not revert … — …` warning live there once.

## 23-16 -- no finding

- The probes reuse the `receipt_paths` uv/python-in-workspace pattern (`exec_tester`), the `_function`/`_harness`/`_run` self-test harness, and the wiring-order test model of `test_the_leftover_check_is_wired_after_the_uninstall_step`. There is no new subcommand (22-13 rule).

## Code that should not exist (summary)

- `RunContext.harnesses` (07-1) and `RunContext.which` (10-1): second seams for `present_hosts` and `which_with_brew`.
- `post_install.SHELL_INIT_EFFECTS` (09-1): a second copy of the bundle descriptions.
- `agent_settings.display_path` and version_status `tilde` (06-1): the second and third copies of `policy._display_path`.
- `setup._which_with_brew` as a separate copy of the brew lookup (10-1).
- `setting_state`'s own classification loop next to `setting_facts` (11-1).
- `desktop_shell_policy.owned` (11-2).
- A second omz closed-block record reader (03-1).

## Counts

important=11 (03-1, 03-2, 04-1, 05-1, 06-1, 06-2, 07-1, 09-1, 09-2, 10-1, 11-1) minor=18

Files added to a plan by these notes: 23-06 gains `installer/locations.py` and `installer/policy.py` (06-1). 23-10 gains `installer/postinstall.py`, `setup.py` and `tests/test_setup.py` (10-1). Each was checked against its wave's other plans.

## Not checked

- Runtime behaviour, and whether pyright strict accepts the `display_path as _display_path` import alias in policy.py. It should, because it is a plain re-bind.
- Outside every plan: `agent_policy._apply_opencode` (agent_policy.py:113-122) still re-serializes `opencode.json` through `_write_json` and ignores an existing `opencode.jsonc`. That makes it a second writer to the file 23-06 splices. No Phase 23 plan touches it, so the orchestrator should decide whether it stays.
- UI-SPEC section 5's catalog `≈`/blocked row for an unparsable settings file that the ledger manages. No plan's refresh-pass task names it. This is a coverage question for the plan checker, not reuse.
