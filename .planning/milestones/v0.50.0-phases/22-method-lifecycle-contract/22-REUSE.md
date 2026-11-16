# Phase 22: Ponytail reuse pass (plans 22-01 .. 22-13)

Read-only audit at ultra level, followed by targeted plan edits for the important findings. Scope: every new function, module, class, dataclass, enum member, table, test helper or constant in 22-01..22-13.
Locked decisions were not re-argued: 22-CONTEXT D-01..D-17, 22-SPEC, the approved 22-UI-SPEC, and the binding ledger rows (Q1 `--force`, Q3 type-only proof, Q4 pinned tarballs, Q5 `--greedy-auto-updates`).
Line numbers are from the tree at `40742aa`, after `codegraph sync`. Evidence comes from `codegraph explore` (callers and blast radius) plus direct reads of the named lines. None of the Phase 22 plans had landed when this was written.

Important findings are already applied to the PLAN.md files named in each finding. Minor findings are notes for the executor; apply them inside the named plan without replanning.

## 22-01 -- two copies of rules the loader already has

### Finding 01-1 -- Important -- Task 2 (`remove`/`update` validation)
- New code: an inline check that `remove` and `update` are non-empty lists of strings, each token passing `_script_token_ok`.
- Existing helper: `installer/model.py:909-924` already validates `smoke_argv` with exactly that shape: a non-empty list of strings, each matching `_SCRIPT_ARG_RE` (`:194`). The `args` check at `:894-908` is a second copy of the same idea. `codegraph explore "_SCRIPT_ARG_RE load_tools"` shows `load_tools` as the only reader, so the inline conditions are the house form.
- Plan change (applied): extract the `smoke_argv` condition into one private predicate `_is_argv(raw: object, token_ok: Callable[[str], bool]) -> bool`. `smoke_argv` calls it with `_SCRIPT_ARG_RE.fullmatch` and keeps its error text byte for byte. `remove` and `update` call it with `lambda t: _script_token_ok(t) is None`. Do not write a third inline copy.

### Finding 01-2 -- Important -- Task 1 (`_parse_config_paths`) and Task 2 (`paths`)
- New code: two separate implementations of "split the rest of a `~/` path on `/` and refuse empty, `.` or `..` parts" (one for `config_paths`, one for script `paths`).
- Existing helper: none in `model.py` (`codegraph explore "load_tools _parse_id_list _parse_pkg_list"` shows the list parsers check types only, never path parts). This is a traversal rule at a trust boundary. It must live in one place, or the two keys will drift.
- Plan change (applied): Task 1 adds one private `_relative_parts(rest: str) -> tuple[str, ...] | None`. It returns None when any part is empty, `.`, `..` or holds a NUL. `_parse_config_paths` calls it after stripping `~/`. Task 2's `paths` check calls the same helper after stripping `~/` or `{root}/` and one trailing `/`.

### Finding 01-3 -- Minor -- Task 1 (`_parse_config_paths`, list shape)
- The "list of non-empty strings" half matches `_skill_string_tuple` (`model.py:469-477`) and `_parse_id_list` (`:234-254`). Their messages are field-specific, so do not call them. Follow the `_parse_id_list` shape: `cast(list[object], raw)`, then an element loop. Do not invent a fourth shape.

## 22-02 -- no finding

- `ManualHandoff` and `needs_manual` sit beside `host_setup_handoff` (`executors.py:585`), which is the house home for handoff text. Session and engine already import that module.
- `InstallOutcome.manual_command` looks like a copy of `handoff[0]`. It is not: `render_handoff` (`render.py:334`) and `outcome_detail_text` (`:169-170`) cannot tell a native one-line handoff from a `host_setup` handoff by `handoff` alone. Keep the field, and set both from the same `handoff.command`.
- The `markup=False` print reuses the `render_post_install_handoff` precedent (`render.py:349-364`).
- The AST zero-sudo test is new. `tests/test_shellrc.py:895-925` is the only AST scanner, and it is PATH-specific, so it cannot be reused.

## 22-03 -- no finding

- `expand_script_token` resolves `{omz_root}` through `omz.omz_root` (`omz.py:530`). `codegraph explore omz_root` shows 5 callers; it is the CR-01 "one place".
- The `tree`/`leaf` types extend `Artifact`, `ReceiptArtifact`, `fingerprint`, `matches`, `_read_artifact` and `remove_paths` in place.
- Tree deletion reuses `_remove_dir`'s quarantine (`uninstall.py:226`).
- `SCRIPT_ROOT_RESOLVERS` with one entry is a small closed table. Its equality test with `SCRIPT_ROOTS` is the cheapest guard on D-03, so it stays.

## 22-04 -- no finding (one note)

### Finding 04-1 -- Minor -- Task 1 (the pass's unwritable prefixes)
- `prefix_writable` has no analogue. A codegraph/rg sweep finds `os.access(..., X_OK)` only (`engine.py:42`, `apps.py:152`, `download.py:489`), with no `W_OK` and no nearest-parent walk.
- `tool_state` already calls `resolve_methods(tool, platform)` (`version_status.py:813`). Compute the unwritable prefixes from that same resolved list in the pass loop rather than resolving a third time. Keep `tool_state` free of filesystem calls.

## 22-05 -- a second pinned predicate beside the one `verify_registry` already has

### Finding 05-1 -- Important -- Task 3 (`update.pinned_method`)
- New symbol: `update.pinned_method(method) -> bool` (kind `app`/`tarball` and `{ver}` in the url).
- Existing helper: `installer/verify_registry.py:1073-1081` `_is_pinned_method(method)`. It is the same predicate, plus `version` and `sha256` set. `load_tools` (`model.py:800-812`) guarantees both whenever a loaded `app`/`tarball` url holds `{ver}`, so for real methods the two agree. Its one caller is `_pinned_method_entries` (`:1086`).
- `download.py:166` `pinned_url` is the house home for pin logic, and both `update.py` (22-05 already imports `download.expand_script_token`) and `verify_registry.py` (`:37-43`) import `download`.
- Plan change (applied): move `_is_pinned_method` unchanged to `installer/download.py` as the public `pinned_method(method: Method) -> bool`, beside `pinned_url`. `verify_registry` imports it, and `update_refusal` and `catalog_tui.action_update_tool` call it (`ownership.method is not None and pinned_method(ownership.method)`). `update.py` keeps only `PINNED_DETAIL`.
  - Test fixtures for a pinned app or tarball must carry `version` and a 64-hex `sha256`, as a loaded method does.
  - `installer/download.py` and `installer/verify_registry.py` join `files_modified`. Wave 3's other plan, 22-06, touches neither file.

### Finding 05-2 -- Minor, resolved by orchestrator decision -- Task 1 (OMZ root order)
- SPEC R8 reads "the OMZ root is `$ZSH` when set, otherwise `~/.oh-my-zsh`", and it names "the existing `$ZSH`-aware resolver". That resolver, `omz_root` (`omz.py:539-543`), prefers `~/.oh-my-zsh` when it exists and uses `$ZSH` only otherwise.
- Orchestrator decision: follow the locked SPEC R8 for the `{omz_root}` placeholder only.
  - The 22-03 resolver (`SCRIPT_ROOT_RESOLVERS["omz_root"]`) gets its own `$ZSH`-first rule: `$ZSH` when it is set and is a directory, else `omz_root(Path.home(), os.environ)` as the fallback.
  - `omz_root` and its other callers keep default-first in this phase. Aligning every caller is Phase 23 CONF-07.
- Plan changes (applied):
  - 22-03: the truth, the resolver decision, and `test_expand_script_token_resolves_zsh_when_the_default_dir_is_absent`, which now also covers both roots existing (`$ZSH` wins), `$ZSH` unset (default), and `$ZSH` naming a missing dir.
  - 22-05: the truth, `test_omz_update_prefers_zsh_when_both_roots_exist` (`u` runs `$ZSH/tools/upgrade.sh`), which replaces `test_omz_update_prefers_the_default_dir`, plus `test_omz_update_falls_back_to_the_default_dir`, and a 2-passed acceptance line.
  - No file list changed: the resolver stays in `download.py`, already in 22-03's `files_modified`.

## 22-06 -- a second kind-to-package table, and config expansion spread over four plans

### Finding 06-1 -- Important -- Task 1 (the private L1 table)
- New symbol: a private L1 table in `uninstall.py` mapping `brew -> formula`, `cask -> cask`, `uv-tool -> pypi_pkg`, `node -> npm_pkg`, plus each argv prefix.
- Existing helper: `installer/ownership.py:1555-1565` `_KIND_PACKAGE_PARAM` and `:1574-1578` `method_package(method)` ("the one reader"). `codegraph explore method_package` shows 7 callers. Among them, `engine.py:272` and `update.py:364` write `receipt.package = method_package(method)`. So the L1 proof (receipt package equals the method's package) must read the package with the same function, or the two tables can drift and L1 silently stops matching.
- `uninstall.py` cannot import `ownership`, because `ownership.py:76` imports `manager_name` from `uninstall`. Putting the table in `uninstall.py` would also break 22-06's own acceptance (no native kind string in `uninstall.py`), because `_KIND_PACKAGE_PARAM` lists `dnf`/`apt`/`pacman`/`rpm_ostree`.
- Plan change (applied):
  - Move `_KIND_PACKAGE_PARAM` (made public as `KIND_PACKAGE_PARAM`) and `method_package` unchanged into `installer/model.py`, beside `METHOD_PARAMS`, the bottom layer that owns per-kind params. `ownership.py` imports both from `model`. `engine.py` and `update.py` keep importing `method_package` from `ownership` (re-exported import, no edit; 22-05 owns `update.py` in this wave).
  - The L1 table becomes the public `MANAGER_UNINSTALL_ARGV: dict[str, tuple[str, ...]]`, keyed by method kind and holding argv prefixes only. Its package comes from `method_package(method)`. 22-07 (07-1) and 22-09 (09-1) read the same table.
  - `installer/model.py` and `installer/ownership.py` join `files_modified`. Wave 3's other plan, 22-05, touches neither file.

### Finding 06-2 -- Important -- Task 1 (`RemovalPlan.config`) and its readers in 22-09, 22-10, 22-11
- New code: `Path(entry).expanduser()` over `Tool.config_paths`, and the reverse expanded-to-declared lookup, written separately in four plans:
  - 22-06 `RemovalPlan.config`;
  - 22-09 the step-4 "equals the expansion of a declared entry" re-check, and the CLI's "Config kept" block in `~` form;
  - 22-10 `config_split` and the `config deleted too: {declared}` suffix;
  - 22-11 the review's `  {path} ({id})` lines in `~` form.
- Existing helper: none (`codegraph explore "Tool config_paths"` shows the field is new in 22-01). The 22-09 re-check is a trust-boundary comparison. It must expand exactly as `removal_plan` did.
- Plan change (applied): 22-06 adds one public `config_targets(tool: Tool) -> tuple[tuple[str, Path], ...]` in `uninstall.py`, giving (declared `~` form, expanded path) pairs in declaration order. `removal_plan` fills `config` from it, filtered by `_exists` (`uninstall.py:27`). 22-09, 22-10 and 22-11 read `config_targets` instead of expanding or back-mapping on their own.

### Finding 06-3 -- Minor -- Task 1 (`ToolRemoval` vendor error line)
- "The first non-empty line of `CommandError.detail`, else `first_line(exc)`" is one expression: `next((ln for ln in exc.detail.splitlines() if ln.strip()), first_line(exc))`. `first_line` is `session.py:343`. No new helper.

## 22-07 -- the hint templates and the L1 argv are the same four commands

### Finding 07-1 -- Important -- Task 2 (`_REMOVAL_COMMANDS`)
- Existing table: `installer/ownership.py:1486-1501` holds `"brew": "brew uninstall {package}"`, `"cask": "brew uninstall --cask {package}"`, `"pnpm": "pnpm remove --global {package}"` and `"uv": "uv tool uninstall {package}"`. These are byte for byte `shlex.join(prefix) + " {package}"` of the four `MANAGER_UNINSTALL_ARGV` rows (06-1).
- Two sources would let a hint name one command while removal runs another. `codegraph explore removal_hint` shows 23 callers.
- Plan change (applied): in Task 2, build those four entries from `MANAGER_UNINSTALL_ARGV` through `_KIND_TO_OWNER` (`ownership.py:148`), e.g. `{_KIND_TO_OWNER[kind]: f"{shlex.join(argv)} {{package}}" for kind, argv in MANAGER_UNINSTALL_ARGV.items()}` merged into the literal. The values stay byte-identical, so the `tests/test_ownership.py` gates (`:1747-1800`) pass unchanged. Keep the cask pin comment.

### Finding 07-2 -- Minor -- Task 1 (`manager_kind_label`)
- `OWNER_LABELS[_KIND_TO_OWNER[kind]]` (`ownership.py:1267`, `:148`) is the right reuse. Answer only for kinds in `MANAGER_UNINSTALL_ARGV`, not every `_KIND_TO_OWNER` key: `sdkman` is in that map and is never an L1 level.

## 22-08 -- ultra note

### Finding 08-1 -- Minor -- Tasks 1-3 (`SCRIPT_LIFECYCLE_DATA`)
- The table restates every stanza's `paths`/`remove`/`update` in the test, so every future vendor-data edit must be made twice.
- The parts SPEC R1 needs are the key-set equality (`test_every_script_stanza_has_lifecycle_data_or_a_reason`, every stanza covered) and the three anchors (opencode `remove`, omz/sdkman `update`).
- Keep the table as planned: it forces per-stanza verification this phase. The orchestrator may later trim it to anchors plus key set.

## 22-09 -- one argv parser written in two plans

### Finding 09-1 -- Important -- Task 3 (private pnpm-package helper) and 22-11 Task 2
- New code: 22-09 adds "a small private helper" in `app.py` returning the last argv element of each plan whose argv starts with `pnpm remove --global`. 22-11 decisions say the same thing again for `wizard_app.py`.
- Existing helper: none. The prefix itself is `MANAGER_UNINSTALL_ARGV["node"]` (06-1).
- Plan change (applied): 22-09 defines one public `pnpm_removal_packages(plans: Iterable[RemovalPlan]) -> frozenset[str]` in `installer/app.py` (`argv[-1]` where `argv[:-1] == MANAGER_UNINSTALL_ARGV["node"]`). `run_uninstall` uses it, and 22-11 imports it (`wizard_app.py:33` already imports from `installer.app`). No re-typed `"pnpm", "remove", "--global"` literal outside `uninstall.py`.

### Finding 09-2 -- Minor -- Task 1 (`delete_config_path`)
- No existing helper (`rg rmtree` finds only receipt-proven `_remove_dir` and the atomic/app staging dirs).
- The stdlib already covers the dangerous case. `shutil.rmtree` refuses a top-level symlink, and on Linux it is fd-based (`shutil.rmtree.avoids_symlink_attacks`). Keep the planned `lstat` branch (unlink a link or file, `rmtree` a real dir). Do not add a quarantine rename: config is user-chosen, not receipt-proven.

## 22-10 -- read the facts the pass already published

### Finding 10-1 -- Minor -- Task 1 (`config_split`)
- `config_split` is "pure but for one `lstat` per path". The published `state.removable.config` (22-06, `config_targets` filtered by `_exists`) already holds the existing paths for every tool, and the Task 2 suffix reads it. When `config_split` does its own `lstat`, the review and the suffix can disagree, and filesystem calls happen on the UI thread.
- Take existence from each declaring tool's published plan (`state.removable.config`). The remover re-checks at delete time anyway (22-09: a missing path is skipped).
- The `mark_cell` hook is justified: `refresh_marks` (`tool_browser.py:307-327`) re-stamps `mark(selected)` after every reload, so a screen-side cell would be overwritten.

## 22-11 -- house wrapper for the hanging indent

### Finding 11-1 -- Minor -- Task 2 (wrapping review lines)
- "Wrap long lines at the 54-cell column with a 2-cell hanging indent" is what `render.fold_reason(prefix, body, column, width)` does (`render.py:65`, 3 callers). Build each long review `Text` with `fold_reason(Text(head), body, 2, 54)`. Do not hand-wrap.
- `removal_runs_line` (22-06), `config_split` (22-10) and `co_install_warnings` (22-09) are reused as planned. The pnpm package set comes from 09-1 (applied to the decisions).

## 22-12 -- one note

### Finding 12-1 -- Minor -- Task 1 (tracked cask tokens)
- "The `cask` param of every catalog tool's `cask` method" is `method_package(m)` for `m.kind == "cask"` (06-1 moves it to `model.py`). Use it instead of a third `params.get("cask")` reader.
- `brew_greedy_outdated` reusing the casks side of `parse_brew_outdated_json` (`manager_versions.py:52`) and `_BREW_ENV` (`:30`) is the right reuse. `parse_brew_cask_auto_updates` is a new payload shape with no analogue.

## 22-13 -- no finding

- `home_listing`, `receipt_paths` and `assert_no_leftovers` run through `exec_tester` (`container-e2e-verify.sh:84`).
- `receipt_paths` reuses the `uv run --isolated --no-dev python -c` receipts-reader probe of `assert_receipt_ready_for_removal` (`:306-326`).
- `new_leftovers` is pure, so the host-side self-test follows `tests/test_container_e2e_receipts.py`'s `_function`/`_run` extraction.
- There is no new subcommand (D-17). The manual-name parser is widened in place.

## SPEC coverage (ultra pass)

No task exceeds the SPEC. Every task traces to R1-R12, a SPEC Boundary deletion, an approved UI-SPEC row, or a binding ledger row:
- 22-01 Task 3: the dead fields.
- 22-02 Task 3 and 22-10/22-11: UI-SPEC copy.
- 22-06: `--force` (ledger Q1).
- 22-12: the REQUIREMENTS.md wording (Q5).
- 22-13 Task 2: required by 22-02's new copy.

## Counts

important=7 minor=10

Plans changed: 22-01, 22-03 (05-2 decision), 22-05, 22-06, 22-07, 22-09, 22-10, 22-11.

Not checked: runtime behaviour, and whether pyright strict accepts `engine.py`/`update.py` importing `method_package` through `ownership` after 06-1. It should, because the import is a plain module attribute. If it does not, the 22-06 executor repoints `engine.py:16` only, since `update.py` is owned by 22-05 in the same wave.
