# Phase 17: Stop the bleeding - Pattern Map

**Mapped:** 2026-10-14
**Files analyzed:** 27 (modified; no new modules, per RESEARCH "Recommended Project Structure")
**Analogs found:** 27 / 27 (every analog verified git-tracked via `git ls-files`)

Ledger overrides applied: graphify `postinstall` is REMOVED (with dead hook code); `move_link_mode` moves only policies with a new appended `Policy.link_mode_aware` flag.

## File Classification

| Modified File | Role | Data Flow | Closest Analog (reuse) | Match |
|---|---|---|---|---|
| `installer/download.py` (:189-190, :403-404) | service | file-I/O | `download._replace_archive` :292-310 + `atomic.replace_symlink` :117 | exact |
| `installer/apps.py` (:100) | service | file-I/O | same (`replace_symlink` already imported :24) | exact |
| `installer/registry.toml` (:2270,2278 member; graphify `postinstall`; codex `env`) | config | n/a | homebrew `env = { NONINTERACTIVE = "1" }` :166,173 | exact |
| `installer/uninstall.py` (new `plan_removal`) | service | transform | `plan_uninstall` :80-100 (beside, not inside) | role-match |
| `installer/app.py` (`clean_rc_duplicates` :418-448, `run_uninstall` ~:548, `doctor_data` :346) | controller | request-response | itself + `atomic_write_text` | exact |
| `installer/guards.py` (:388,392,425,448,472,554,564) | utility | file-I/O | `atomic.atomic_write_text` :56 (24 callers) | exact |
| `installer/tweaks.py` (:254,297,308) | utility | file-I/O | same | exact |
| `installer/execute_screen.py` (`_execute_worker` :593-656) | component | event-driven | its own `on_outcome` + `run_live` pattern | exact |
| `installer/session.py` (`Summary` :106-113, new `fold_run`) | model | transform | `Summary` existing tuple fields | exact |
| `installer/wizard_app.py` (:2179, :2924-2974, ~:2770, mount ~:2594) | component | event-driven | self; `_pending_warnings` queue | exact |
| `installer/policy.py` (`move_link_mode`, `link_mode_aware`) | service | transform | `Policy` appended-field comment :148; `ban_policy` :267; `tweak_policy` :357; `cache_redirect_policy` :485 | role-match |
| `installer/run.py` (:232-240, `run_output` :70-92) | utility | request-response | `popen_with_env`, `subprocess.run` call | exact |
| `installer/settings.py` (`load_settings`, `SettingsStore` :90) | model | file-I/O | `save_settings` / `resolve_link_mode` | role-match |
| `installer/doctor.py` + `installer/guidance.py` (`doctor_guidance` :104) | model/service | transform | `audit_path` + broken-dir `Guidance` loop | exact |
| `installer/postinstall.py` (delete `_graphify_register` :258, `POSTINSTALL_HOOKS` :280), `installer/model.py:21` | config | event-driven | removal only | n/a |
| `setup.py` (`_build_app` :755, `_execute_inputs` :1166, :1275, :1283, :1509, routes) | config (wiring) | request-response | `_execute_inputs` | exact |
| `scripts/prune-tmp-linux.sh` (:101-115), `scripts/lib/prune-tmp-common.sh` (:203-236) | utility | batch | existing library, idiom fixes | exact |
| tests: `test_download.py`, `test_apps.py`, `test_engine.py`, `test_uninstall.py`, `test_run.py`, `test_settings.py`, `test_doctor.py`, `test_atomic.py`, `test_app.py`, `test_setup.py`, `test_catalog_tui.py`, `test_version_status.py` | test | n/a | see per-file notes | exact |
| `.planning/milestones/v0.49.0-phases/16-.../16-SECURITY.md`, `16-VALIDATION.md` | doc | n/a | existing entries in same files | exact |

## Pattern Assignments

### Link sites: `installer/download.py:189-190`, `:403-404`, `installer/apps.py:100` (service, file-I/O)

**Analog:** `installer/download.py::_replace_archive` :292-310 (update path already does `binary.chmod` + guard) and `installer/atomic.py:117`.

Current bug (download.py:189-190, repeated 403-404; apps.py:100 uses the same `ln -sf` with `runner([...])`):
```python
ctx.runner(["chmod", "+x", str(binary)])
ctx.runner(["ln", "-sf", str(binary), str(link)])
```
Replacement (RESEARCH Code Example; `replace_symlink` already imported at download.py:16, apps.py:24):
```python
binary = opt / target.member
if not binary.is_file():
    raise ExecutorError(f"archive member '{target.member}' is not a regular file")
binary.chmod(0o755)
replace_symlink(link, str(binary))
```
`replace_symlink` (atomic.py:117-131): sibling temp symlink + `os.replace`, unlinks temp on `OSError`. `engine.install_tool` (engine.py:137-150) already catches `ExecutorError`, so no engine change.
**Ponytail reuse:** one tiny `_require_file(path, label)` shared by the 3 required sites (+ optionally `_replace_archive` :299 and `update_app`); do not add one per file. Apps site: `apps / app / cli` is the member (apps.py:100).
**Test churn (Pitfall 1):** ~29 assertions on `["ln","-sf",...]` / `["chmod","+x",...]` (e.g. `tests/test_download.py` ~170-195, `test_tarball_bin_name_overrides_the_symlink_name`) must change. Build ONE shared helper (in `tests/conftest.py` or a `tests/_helpers.py`) whose recording runner creates the member file on the `sh -c ... tar` call, then assert `link.is_symlink()` and `os.readlink`. `test_download.py:175` encodes the Sublime bug: change member to `sublime_text/sublime_text`.

### `installer/registry.toml` (config)

**Sublime** (:2270,:2278) change `member = "sublime_text"` to `member = "sublime_text/sublime_text"` (both x64/arm64; `strip` stays 0); add `# Verified 2026-10-14` comment above each.
**codex env** analog (registry.toml:166-173): `env = { NONINTERACTIVE = "1" }` -> add `env = { CODEX_NON_INTERACTIVE = "1" }` to the codex script method; consumed by `executors._env_prefix` (executors.py:335, sorted, `shlex.quote`d values). No code change.
**graphify:** delete the `postinstall = "graphify-register"` key; then (rule 5, no orphans) delete `_graphify_register`, `_GRAPHIFY_HOST_SUBCOMMANDS`, the `POSTINSTALL_HOOKS["graphify-register"]` entry (postinstall.py:258-280), the name at `model.py:21`, and their tests (`test_postinstall.py` ~20 lines, `test_registry.py` ~27, `test_model.py` ~4). Keep one test asserting graphify has no `postinstall` and one asserting install runs no hook (update path never runs it; only `engine.py:166` calls `run_postinstall`). Record the container probe in the plan summary (RESEARCH Pitfall 3 table).

### `installer/uninstall.py` new `plan_removal` + callers (service, transform)

**Analog:** `plan_uninstall` :80-100 (do NOT change its result; ownership callers `version_status.py:594`, `setup.py:1108` rely on the lenient list).
Shared name rule to copy/fix (uninstall.py:90): `binname = PurePosixPath(member).name` ignores `bin_name`; install uses `bin_name or basename(member)` (download.py:144,242). Use the same expression, guarded by the existing traversal check (:91-95):
```python
if binname in ("", ".", ".."):
    continue
```
Predicate (RESEARCH Pattern 2):
```python
link = base / binname
ok = link.is_symlink() and (r := link.resolve()).is_file() and r.is_relative_to(opt_dir(binname).resolve())
```
Removable = `[link, opt_dir(binname)]`; the rest of the lenient match goes to a `yourself` list. Return a small frozen dataclass (`RemovalPlan(removable, yourself)`), used by BOTH `classify_tools` (uninstall.py:299 site) and `run_uninstall` (`app.py:~548`). TUI: no new `UninstallState`; unproven becomes `MANAGED` (wizard_app.py:993 makes only `REMOVABLE` selectable) with hint "remove it yourself: <paths>". CLI: one new small printer in `render.py` next to `render_uninstall` (render.py:171); the "nothing to uninstall" early return (~app.py:556) must still print the manual list.
**Tests:** `tests/test_uninstall.py` :31-100 (lenient plan, keep), :184-276 and `:338-350 test_classify_removable_when_artifacts_on_disk` (`(bin_dir/"fd").write_text("x")`; rewrite fixture to real `opt/<bin>/<member>` + symlink). Add adjacency case: link into another tool's opt dir -> not removed.

### rc / shim writers: `guards.py`, `tweaks.py` (utility, file-I/O)

**Analog:** `installer/atomic.py:56`:
```python
def atomic_write_text(path: Path, text: str, *, mode: int | None = None) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)
```
Import to add (guards.py imports are at :29-37, tweaks similar): `from installer.atomic import atomic_write_text` (already used by settings.py, omz.py, shellrc.py).
Shim pairs become one call (delete the `chmod` line): guards.py:388-389, 392-393, 425-426, 448-453, 472-473; tweaks.py:254-255:
```python
atomic_write_text(target, shim_script(name), mode=0o755)
```
rc writes (no mode, copy-from-existing): guards.py:554, 564; tweaks.py:297, 308: `atomic_write_text(rc_path, apply_block(...))`. Test pattern: `tests/test_atomic.py` (monkeypatch `os.replace` to raise, assert bytes unchanged; symlinked rc stays a symlink, lines ~44-60).

### `installer/app.py::clean_rc_duplicates` :418-448 (controller, request-response)

**Analog:** itself. Keep bytes from preview (RESEARCH "Byte-exact confirm recheck"):
```python
before = rc_path.read_bytes(); text = before.decode()   # preview, replaces read_text() :428
...
if rc_path.read_bytes() != before:                      # confirm, replaces :446-447
    console.print(f"{rc_path} changed since the preview; left untouched."); continue
atomic_write_text(rc_path, strip_lines(text, indices))
```
Store `before`/`text` in the existing `indices_by_file` loop (e.g. a tuple value). Must compare bytes, not `read_text()` (newline translation). Tests live in `tests/test_app.py`.

### `installer/execute_screen.py::_execute_worker` :593-656 (component, event-driven)

**Analog:** itself; copy the `on_outcome` hook (:606-607) and `run_live` shape:
```python
def on_outcome(outcome: InstallOutcome) -> None:
    self.post_message(InstallToolFinished(outcome.tool_id, outcome.status))
```
Add a local `collected: list[InstallOutcome]` appended inside `on_outcome`; add `except Exception as exc:` ahead of the existing `finally` (:651) that sets `outcomes = collected`, `not_attempted` = ordered ids not in collected, `error = str(exc)`. `_run_updates` must append to caller-owned lists so completed updates survive a later exception. `run_live` only catches `OSError`/`CommandError`/`ShellrcRefusal` (ui_common.py:42-56); do not widen it. Status line at execute_screen.py:~953 `self.status.set("Done. ...", "ok")` becomes `"Failed..."`/`"error"` when `summary.has_failure` (severities `ok|warn|error`).

### `installer/session.py` `Summary` (model, transform)

**Analog:** session.py:106-113 (defaulted tuple fields).
```python
mismatched: tuple[str, ...] = ()
dependency_failed: tuple[str, ...] = ()
manual_required: tuple[str, ...] = ()
```
Append `not_attempted: tuple[str, ...] = ()`, `update_failed: tuple[str, ...] = ()`, `crash_error: str | None = None`; add `has_failure` property and ONE pure `fold_run(...)`. Only two production constructors: `session.py:209` and `wizard_app.py:2968` (the accumulator listing each field; add the three new ones there, `crash_error` = first non-None). `update_failed` must include `UpdateOutcome.status == "failed"` (update.py:153) AND ids in `update_errors`. `setup.py:1275` and `:1509` replace `summary.failed or summary.mismatched or summary.dependency_failed` with `summary.has_failure`. The four bare `_build_app(...).run()` routes (`_run_doctor` 1295, `_run_fix` 1324, `_run_uninstall` 1351, inline guard in `main` ~1441) should return the same code from `app.install_summary`.

### `installer/policy.py::move_link_mode` (service, transform)

**Analog:** `Policy` dataclass append rule (policy.py:148: "New optional fields are APPENDED, never inserted"); `uninstall.sweep_policies` :496 for remove-over-list; `run_live` caller.
Append `link_mode_aware: bool = False` after `owned` (policy.py:~162); set `True` in the `Policy(` returns of `ban_policy` (:338), `tweak_policy` (:445), `cache_redirect_policy` (:570). Algorithm per RESEARCH Pattern 4 (remove old, `set_link_mode(new)`, apply new, per-policy restore via `set_link_mode(old)`/`apply()`/`set_link_mode(new)`, return `tuple[(id, status, message)]`).
**Correction to D-09:** `active_policies` (uninstall.py:401) rebuilds from bundles and cannot filter an existing list; use live truth `PoliciesScreen.active_state[policy.id]` (wizard_app.py:~1638,2012), `policy_owned` (uninstall.py:387) only for policies with `is_active`/`owned`. Call site `_link_mode_picked` (wizard_app.py:2179-2194) now:
```python
_, error = run_live(lambda: setter(value))      # replace with run_live(lambda: move_link_mode(aware_active, value, setter))
```
Same change in `UnifiedApp._first_link_mode_picked` (~2770). Failure injection tests: copy `os.replace` monkeypatch from `tests/test_atomic.py`.

### `installer/run.py` (utility, request-response)

**Analog:** itself. `StreamingRunner.popen_with_env` (:232-240): add `start_new_session=True` after `env=env`. `run_output` (:88): add `stdin=subprocess.DEVNULL, start_new_session=True` to the `subprocess.run(...)` (update path `run_captured` -> `run_output`; research Pitfall 4). Do not touch `run_command`. Update `tests/test_run.py::test_run_output_unbounded_by_default` (:111-131): `fake_run` has a fixed kwarg list, add `stdin`, `start_new_session`. Discriminating test: child exits non-zero unless `os.getsid(0) == os.getpid()`; plus a `/dev/tty` reader test with 5 s timeout. Also verify `daemon.py`, `policy.py`, `systemd_daemon.py` `run_captured` callers.

### `installer/settings.py` (model, file-I/O)

**Analog:** `load_settings` tail :60-66 and `SettingsStore` :90-110.
Return a frozen `LoadedSettings(settings: Settings, warning: str | None)`; wrap read/parse in `except (OSError, ValueError)` (covers `UnicodeDecodeError`, `JSONDecodeError`; `FileNotFoundError` = not chosen, no warning). Add `warning: str | None = None` on `SettingsStore.__init__` (keyword). Single production caller `setup.py:1283` in `_settings_store`; the six `_settings_store` callers stay unchanged. Surface through `UnifiedApp._pending_warnings` flushed at `on_mount` end (wizard_app.py:~2594-2606, `_flush_pending_warnings` :2714). `tests/test_settings.py` (18 tests) updated to `.settings.link_mode`.

### `installer/doctor.py`, `installer/guidance.py`, `app.doctor_data` (model, transform)

**Analog:** `DoctorReport` (doctor.py:9) + `has_problems` (doctor.py:35) + broken-dir `Guidance` (guidance.py:~122):
```python
items.append(Guidance(title=f"{directory} does not exist", meaning=..., next_step=..., severity=Severity.ERROR))
```
Add `broken_links: tuple[BrokenLink, ...] = ()` (appended, defaulted) to `DoctorReport`; pure scan helper in `doctor.py` taking `bin_dir` (symlink and (not exists or is_dir)); fill in `doctor_data` (app.py:346-360) using `default_bin_dir`; extend `has_problems`; one `Guidance` per link. Repair text from `locations.opt_dir(name)`; pitfall: `DoctorScreen._tui_guidance` (wizard_app.py:599) rewrites next_steps starting with "Run `make fix`"/"Run `make setup`", so do not start with those. No `sudo`. Tests mirror `tests/test_doctor.py:1-30` (`DoctorReport(missing=(), broken=(), duplicated=())` equality at :23 still holds with a defaulted field).

### `setup.py` wiring (config, request-response)

**Analog:** `_execute_inputs` :1166-1211 (signature `tools, platform, *, link_mode, unattended, disk_pressure`). Move the call inside `_build_app` (:755) using its own `_current_link_mode` closure and resolved `disk_pressure`; remove the `execute` parameter; add `unattended: bool = False`; then the existing `replace(execute, version_refresh=..., updates=...)` (:1134) applies unconditionally. `_run_interactive_wizard` (:1234-1239) drops its own construction and passes `unattended=options.yes`. Delete `test_accepting_the_catalog_without_execute_still_exits_with_ids`; tests injecting `execute` patch `setup._execute_inputs`. `tests/test_setup.py::_sandbox` is the scratch-HOME helper every new test must use. Empty-Enter message already exists (`catalog_tui.py:1040-1042`): tests only. Fix `test_interactive_wizard_shares_one_cache…` by patching `setup.systemd_daemon.systemd_available` like the sibling at `test_setup.py:~2827`.

### `scripts/prune-tmp-linux.sh`, `scripts/lib/prune-tmp-common.sh` (utility, batch)

Current (prune-tmp-linux.sh:101):
```bash
mapfile -t files < <(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" "" regex "$pattern")
```
Replace with `files=(); while IFS= read -r line; do files+=("$line"); done < <(...)`. Replace every empty-array expansion `"${find_type[@]}"` (common.sh:203,208,209,211,228,234,236) and `"${files[@]}"` (linux.sh:105,115) with `${arr[@]+"${arr[@]}"}`. Replace `find ... -regextype posix-extended -regex "$pattern"` (common.sh:208,233) with `find ... -mmin +N ... | grep -E "^${pattern}$" || true`. Verify with `podman run --rm --security-opt label=disable -v "$PWD/scripts:/s:ro" docker.io/library/bash:3.2 bash /s/prune-tmp-linux.sh --tmpdir <dir>`; keep `shellcheck -x` green.

### CI test fixes (test, n/a)

- `time-shells0` (tests/test_shellrc.py): derive expectation from `Path(shutil.which("sh")).resolve().name == "dash"`; keep `sh`.
- `tests/test_app.py` console-width: force wide `Console(width=...)` in the buffer-console fixture.
- `test_catalog_tui::test_owner_cell…` (seeds `service._ownership`, then refresh worker overwrites via `artifacts_for=lambda tool: [_MANAGED / tool.cmd]` at test_catalog_tui.py:~1183): make refresh agree (`artifacts_for=lambda _t: []` + brew inventory) or `await app.workers.wait_for_complete()` and assert refreshed value.
- `test_version_status.py:1790,1874` (`second.join(timeout=0.2); assert second.is_alive()`): only edit if the executor reproduces the flake (ledger Q3); use `threading.Event/Barrier`.

### CI-02 / CI-03 (governance)

`gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -` with `checks` contexts `validate & test on ubuntu-latest` / `validate & test on macos-latest` (RESEARCH body), only after green CI and in-the-moment user confirmation. CI-03: append plan 16-17..16-19 entries to the existing sections of `16-SECURITY.md` / `16-VALIDATION.md` (copy the entry shape already used for earlier 16-* plans there).

## Shared Patterns

### Atomic persistence
**Source:** `installer/atomic.py:56` (`atomic_write_text`), `:117` (`replace_symlink`). **Apply to:** download, apps, guards, tweaks, app.clean_rc_duplicates, settings (already). No temp+rename code anywhere else.

### Screen mutations
**Source:** `installer/ui_common.py:42` `run_live` -> `(result, None)` or `(None, message)`. **Apply to:** `_link_mode_picked`, first-run picker, worker steps. Never a screen-level try/except for `OSError`.

### Typed refusal / failure
**Source:** `ExecutorError` caught by `engine.install_tool` ladder (engine.py:137-150). **Apply to:** all three link sites.

### Registry-driven env
**Source:** `executors._env_prefix` (executors.py:335) + registry `env = {...}` (:166,173,554). **Apply to:** codex only.

### Appended frozen-dataclass fields
**Source:** `Policy` comment policy.py:148; `Summary` defaults session.py:111-113; `DoctorReport`. **Apply to:** `link_mode_aware`, `Summary` fields, `broken_links`: append with a default so positional constructions and the ~24 test `Summary(` calls stay valid.

### Test isolation
**Source:** `tests/test_setup.py::_sandbox`, `monkeypatch.setattr(Path, "home", lambda: tmp_path)` (test_uninstall.py:338, test_download.py:~171), `tests/conftest.py` real-home guard. **Apply to:** every new test; xdist-safe, no fixed paths.

## Ponytail duplication flags

- Do NOT add a new `UninstallState` member, a new `settings_warning()` probe, a second status channel for settings (use `_pending_warnings`), a new empty-selection guard (exists catalog_tui.py:1040), or a new atomic helper.
- `plan_removal` must reuse `opt_dir`/`bin_dir` (`locations.py`) and the existing traversal guard, not re-derive paths.
- `fold_run` is the single fold; `ExecuteScreen` and `UnifiedApp` both call it (do not duplicate the logic that lives at wizard_app.py:2968 inline).
- One shared test materializing-runner helper, not one per test module.
- `move_link_mode` must not re-implement the active filter; use `active_state` / `link_mode_aware`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `move_link_mode` rollback-per-policy | service | transform | No existing transactional "remove, flip setting, apply, restore" routine; compose from `Policy.apply/remove` and `sweep_policies` style |
| `getsid` / `/dev/tty` session test | test | n/a | No existing subprocess-session test; write new in `tests/test_run.py` |

## Metadata

**Analog search scope:** `installer/`, `setup.py`, `scripts/`, `tests/`, `installer/registry.toml`
**Files scanned:** ~30 (targeted ranges; CONTEXT/RESEARCH/RUN-LEDGER read in full)
**Tracked-source gate:** all `installer/*.py`, `setup.py`, `scripts/*` analogs confirmed via `git ls-files`; no mirror paths used.
**Pattern extraction date:** 2026-10-14
