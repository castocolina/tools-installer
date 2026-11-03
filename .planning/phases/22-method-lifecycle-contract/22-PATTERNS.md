# Phase 22: Method lifecycle contract - Pattern Map

**Mapped:** 2026-11-03
**Files analyzed:** 17 new/modified
**Analogs found:** 17 / 17 (all tracked; line numbers read against current `main`, not CONTEXT anchors)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/model.py` (script keys, `config_paths`, `HARNESS_MARKER_DIRS`, root placeholders) | config/model | transform (load-time validation) | itself: `METHOD_PARAMS` `:42-55`, `SKILL_HARNESSES` `:123`, `Tool.uninstall` `:410`, unknown-key check `:791` | exact |
| `installer/skill_lifecycle.py` (`HARNESS_PRESENCE` derived from model) | config | transform | `HARNESS_PRESENCE` `:235-249`, consumer `:630-634` | exact |
| `installer/download.py` `artifact_paths` script branch | utility | transform | `artifact_paths` `:247-290` (download + app branches) | exact |
| `installer/receipts.py` type-only artifact | model/service | file-I/O | existing `_read_artifact`/`fingerprint`/`matches` (read before editing) | role-match |
| `installer/uninstall.py` (`RemovalPlan` -> R2 shape, `removal_plan`, ordered steps) | service | CRUD (delete) | `RemovalPlan` `:55-77`, `_receipt_proof` `:80-100`, `_QUARANTINE_SUFFIX`/`_remove_dir`, `plan_removal` `:133` | exact |
| `installer/app.py` `UninstallDecision` + `perform_uninstall` (`config` toggle, step order) | controller/composition | request-response | `UninstallDecision` `:637-649`, `perform_uninstall` `:652+` | exact |
| `installer/session.py` (`Disposition.MANUAL`, `WORDS`, `build_plan`) | model | transform | `Disposition` `:87-98`, `RUNNABLE` `:114-124`, `WORDS` `:136-146`, BLOCKED branches `:670,686,737` | exact |
| `installer/engine.py` `needs_manual` re-check | service | request-response | `_perform` `:60-85`, `host_setup` handoff / `MANUAL_REQUIRED` return `:225-234` | exact |
| `installer/executors.py` (delete `_dnf/_apt/_pacman`; shared `sdk` pipeline helper) | service | request-response | `_dnf/_apt/_pacman` `:448-457` (delete), `_sdkman` `:556-575` | exact |
| `installer/update.py` (pinned-app refusal, script `update` argv) | service | request-response | `update_refusal` `:238-290`, `_update_installer_owned` `:379-405` | exact |
| `installer/ownership.py` (delete native `_REMOVAL_COMMANDS`, package-naming hint) | utility | transform | `_REMOVAL_COMMANDS` `:1486-1501`, `removal_hint` `:1592` | exact |
| `installer/manager_versions.py` / `version_status.py` (greedy cask) | service | batch | `parse_brew_outdated_json` `:52`, `brew_outdated` `:158-165` | exact |
| `installer/pnpm_globals.py` consumer (co-install warning) | service | transform | `NodeInstallPolicy.groups` `:121` (declared groups, NOT `split_install_groups`) | role-match |
| `registry.toml` (script stanzas, `config_paths`, `verified`) | config | n/a | existing `kind = "script"` stanzas | exact |
| `installer/wizard_app.py` (per-row delete-config toggle) | component | event-driven | `UninstallScreen`, `ConfirmUninstall`; follow `22-UI-SPEC.md` | role-match |
| `scripts/container-e2e-verify.sh` `cmd_pass2` | utility/script | batch | `cmd_pass2` `:548-600+`, `run_pass2_step` `:535`, `exec_tester` `:84` | exact |
| tests: `tests/test_plan.py`, `test_engine.py`, `test_uninstall.py`, `test_receipts.py`, `test_update.py` | test | n/a | `test_no_sudo_argv_on_the_plan_path` `test_plan.py:260-264` | exact |

## Pattern Assignments

### `installer/model.py` (config, load-time validation)

**Analog:** itself.

**Method-key extension** (`:42-55`): add `paths`, `remove`, `update`, `writable_prefix` to the `script` frozenset. Unknown keys are already rejected at `:791` (`unknown = set(params) - METHOD_PARAMS[kind]`); reuse that error style (names tool and key).
```python
METHOD_PARAMS: dict[str, frozenset[str]] = {
    "script": frozenset({"url", "shell", "bin_dir", "env", "detect_path",
        "version_file", "args", "smoke_argv", "refuses_existing"}),
```
**Tool-level field:** copy how `uninstall` is declared and set (`:410` field, `:432` init arg, `:458` `object.__setattr__`, `:1008-1011` parse from `row.get`). Add `config_paths: tuple[str, ...]` the same way.
**Denylist constant:** move marker tuples next to `SKILL_HARNESSES` (`:123`) as one `HARNESS_MARKER_DIRS`; the validator (under `~`, depth >= 2, not under any marker) reads it. The pinned-url test is `"{ver}" in url` (`:800-803`) and is reused by the pinned-app gate.
**Closed placeholders:** follow `assets.py:33` `{ver}`/`{arch.*}`; add `{omz_root}`; reject unknown at load.

### `installer/skill_lifecycle.py`

**Analog:** itself `:235-249`, `:630-634`. Rebuild `HARNESS_PRESENCE[h] = (commands, MODEL_MARKERS[h])`. Keep the consumer loop unchanged. Import direction `skill_lifecycle -> model` only. Test: markers derive from the model constant.

### `installer/download.py` `artifact_paths` (script branch)

**Analog:** `:247-290`. Same signature, returns `Artifact(path, kind)` tuples; docstring says every other kind "creates nothing this formula describes", so add a `kind == "script"` branch that expands each declared `paths` token (`Path(x).expanduser()` as in `:270`, plus the closed roots) and types it. Record-time inference of file/link/dir is safer than registry-declared (research Pattern 2). Because `uninstall._receipt_proof` intersects the receipt with `artifact_paths` by `(path, kind)` pair, this branch is what makes L3 proof work.
```python
declared = _opt_str(method, "bin_dir")
bin_base = Path(declared).expanduser() if declared else default_bin_dir
if method.params.get("raw") is True:
    return (Artifact(bin_base / name, "file"),)
return (Artifact(opt_dir(name), "dir"), Artifact(bin_base / name, "link"))
```

### `installer/uninstall.py` (service, delete)

**Analog:** itself.

**Receipt proof** (`:80-100`) is the pattern to preserve for L3: receipt is evidence only, intersected with registry formula, drift or corruption proves nothing.
```python
allowed = {(artifact.path, artifact.kind)
    for method in tool.methods if method.kind == receipt.method.kind
    for artifact in artifact_paths(method, default_bin_dir)}
return tuple(a for a in receipt.artifacts if (a.path, a.type) in allowed)
```
**Dataclass to evolve** (`:55-77`): frozen `RemovalPlan(removable, yourself, by_tool, artifacts)`. Add the R2 fields (`level`, `argv`, `config`, `hint`) with defaults so the five consumers (`uninstall_group` / `uninstall_detail` / `uninstall_label` in `version_status.py`, `run_uninstall`, `perform_uninstall`) keep working; move them in one change.
**Dir deletion:** reuse the quarantine rename (`_QUARANTINE_SUFFIX = ".tools-installer.rm"`, never `.old`); for type-only trees re-check `is_dir and not is_symlink` inside quarantine instead of re-hashing.
**Order (D-07):** `remove` argv via runner -> fail = `remove_failed` + stop -> delete proven paths -> `receipts.delete` -> config only if toggle and steps 1-3 ok (warning on failure).

### `installer/app.py` `perform_uninstall` / `UninstallDecision`

**Analog:** `:637-692`. Frozen dataclass carrying `tools`, `paths: Mapping[str, tuple[Path, ...]]`, flags. Add a `config: Mapping[str, tuple[Path, ...]]` (or a set of tool ids with the toggle on) with default empty so CLI `run_uninstall --yes` never deletes config. Tool-by-tool loop: one tool's refusal never stops the next; the plan must still name every previewed path or the tool is untouched (keep that guard). Warnings flow through `SweepResult.warnings`.

### `installer/session.py` (MANUAL)

**Analog:** `:87-146`.
```python
class Disposition(StrEnum):
    ...
    BLOCKED = "blocked"
    REMOVE = "remove"
```
Add `MANUAL` in review order (before BLOCKED is sensible), a `WORDS` entry (dict is exhaustive; missing = KeyError in `render.py`), and keep it out of `RUNNABLE` (like BLOCKED, never reaches an engine). Result `"manual"` already exists in `Result`. Dependents: BLOCKED rows feed `unsatisfied` (`:609`, `:785`, `:803`); MANUAL must feed it too so dependents read "needs zsh". Guard: parametrized test over `Disposition`.
Plan path must stay sudo-free and pure: `needs_manual` consumes prefix-writability evidence from `ToolState`, never probes (`test_plan.py:260` bans quoted `"sudo"/"pkexec"/"doas"` in `session.py`/`deps.py`).

### `installer/engine.py` (re-check before `_perform`)

**Analog:** `:225-234`; insert `needs_manual(...)` just before it, returning the same outcome shape.
```python
verified, unverified_reason, handoff = _perform(tool, method, ctx)
if handoff:
    return InstallOutcome(tool.id, InstallStatus.MANUAL_REQUIRED,
        method_kind=method.kind, handoff=handoff)
```
For MANUAL: `InstallOutcome(tool.id, InstallStatus.MANUAL_REQUIRED, method_kind=method.kind, handoff=(command,))` with zero runner calls. The `refuses_existing` branch just above (`:215-224`) is a second precedent for a handoff with text. `_perform` `:60-85` shows `host_setup` returns `executors.host_setup_handoff(method)`; a `native_handoff(method)` helper in `executors.py` belongs there. Command strings are display strings (`"sudo dnf install -y <pkg>"`), not argv lists; the grep test scans list literals whose first element is `sudo`/`pkexec`/`doas`.

### `installer/executors.py`

**Delete** `:448-457`:
```python
def _dnf(method, runner): runner(["sudo", "dnf", "install", "-y", require_str(method, "package")])
```
(plus `_apt`, `_pacman`) and their registry entries in the executor dispatch. Rewrite `tests/test_engine.py:103,144,159,793,1010` to assert handoff plus zero runner calls.
**Reuse for `sdk selfupdate`** (`:556-575`): factor the fixed sourced pipeline into one helper used by `_sdkman` and the update branch.
```python
pipeline = f'{_path_prefix()}. "$HOME/.sdkman/bin/sdkman-init.sh" && {shlex.join(install)}'
runner(["bash", "-c", pipeline])
```

### `installer/update.py`

**Analog:** `update_refusal` `:238-290`: one pre-flight predicate shared by TUI `u` and `build_plan`; each branch returns `UpdateOutcome(tool_id=..., status="unsupported", owner=..., detail=...)`. Add the pinned-app branch next to the sdkman branch (`:253-259`), method-derived (`method.kind == "app"` and `"{ver}" in url`, pinned tarball included per ledger), detail "pinned; update outside or re-pin". No new `UpdateTarget` field.
**Script update:** `_update_installer_owned` `:401-403` currently does `executors.execute(method, runner)` for `script`. Add: if the method declares `update`, run that expanded argv (stdin closed, new session, via the runner); `sdk ...` goes through the sourced pipeline helper; else keep the vendor-script rerun. The receipt rewrite at `:359-367` already follows an installer-owned update.

### `installer/ownership.py`

**Analog:** `_REMOVAL_COMMANDS` `:1486-1501` (`"brew": "brew uninstall {package}"`, cask, pnpm, uv ...). Delete only the dnf/apt/pacman/rpm-ostree entries; keep brew/cask/pnpm/uv/volta/sdkman templates (hint-only). Readers: `removal_hint` `:1592`, `method_removal_command` (used by `engine.py:242` leftover text; check its native-case phrasing after deletion). Hint names the package, never a command.

### `installer/manager_versions.py` / `version_status.py` (greedy)

**Analog:** `parse_brew_outdated_json` (`:52`, returns `(formulae, casks)` maps) and `brew_outdated` (`:158-165`). Add the batched `brew info --cask --installed --json=v2` into the 6 h brew inventory cache, then conditionally `brew outdated --cask --greedy-auto-updates --json=v2` (ledger Q5) parsed by the same function. `update.resolve_update_argv` appends the flag only for those casks, gated on `platform.os == "macos"`. Fixture: macOS-shaped JSON with `auto_updates`.

### `installer/pnpm_globals.py` consumer

**Analog:** `NodeInstallPolicy.groups` (`:121`) and declared `co_install` (`model.py:680-683`). Use the declared groups (static); do not call `split_install_groups` (`:470`, needs a live `pnpm list -g --json`).

### `scripts/container-e2e-verify.sh`

**Analog:** `cmd_pass2` `:548-600`. Add listings via `exec_tester 'find ~ -mindepth 1 ... | sort'` (`exec_tester` `:84`) before step 1 and after step 2; diff and append to `$log`; subtract union of `config_paths` and a committed `E2E_RESIDUE_ALLOWLIST`; fail by `return 1` with a `TRACER_LEFTOVER ...` line like the existing `TRACER_UNINSTALL_INCOMPLETE` convention.
```bash
run_pass2_step "--uninstall --yes" "$log"
if [[ "$PASS2_STEP_STATUS" -ne 0 ]]; then
  printf 'TRACER_UNINSTALL_INCOMPLETE exit=%s\n' "$PASS2_STEP_STATUS" >> "$log"
  return 1
fi
printf 'TRACER_UNINSTALL_OK\n' >> "$log"
```
No new subcommand. Provide a stubbed-listing seam so a planted-leftover self-test runs without podman (see `tests/test_container_e2e_receipts.py`).

### `installer/wizard_app.py`

No same-shape analog for a per-row toggle was read; copy the key/binding and `ConfirmUninstall` section patterns from `UninstallScreen`/`ConfirmUninstall`, and the layout, copy and 80x20 fit from `22-UI-SPEC.md`. Toggle absent when the tool has no `config_paths`; off by default.

## Shared Patterns

### One predicate, two layers
**Source:** `installer/update.py:238-244` (`update_refusal` docstring: engine and review consult the same predicate).
**Apply to:** `needs_manual` (plan + engine), pinned-app gate (TUI `u` + `build_plan`).

### Receipt as evidence, registry as authority
**Source:** `installer/uninstall.py:80-100`. **Apply to:** all L1/L2/L3 deletion; re-prove at delete time; unknown types fail closed.

### Handoff, not execution
**Source:** `installer/engine.py:225-234`, `InstallStatus.MANUAL_REQUIRED` + `handoff`. **Apply to:** native dnf/apt/pacman/rpm-ostree and unwritable `writable_prefix` (brew Linux stanza).

### Literal argv, closed roots, no shell
**Source:** `installer/assets.py:33` closed templating; `executors._sdkman` as the only fixed shell pipeline. **Apply to:** all script `paths`/`remove`/`update` tokens.

### Exhaustive dicts
`WORDS`, `_REVIEW_ORDER`, `RUNNABLE`, `render.py` index by `Disposition`; add MANUAL everywhere or `KeyError`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Type-only receipt artifact (script trees) | model | file-I/O | Existing receipts fingerprint by sha256 / key-file hash; a type+link-target-only proof is new (ledger Q3). Read `installer/receipts.py` `_read_artifact`, `fingerprint`, `matches` and extend; keep schema `"v": 1` |
| Prefix-writability evidence in `ToolState` | model | batch | No stat-based evidence exists today; add one `os.access(prefix, W_OK)` per `writable_prefix` in the refresh pass (nearest existing parent if absent), no subprocess |
| Per-row delete-config toggle UI | component | event-driven | Use `22-UI-SPEC.md` |

## Metadata

**Analog search scope:** `installer/`, `scripts/`, `tests/test_plan.py`, `registry.toml`
**Files read:** uninstall.py (part), engine.py (part), executors.py (part), update.py (part), session.py (part), download.py (part), model.py (part), skill_lifecycle.py (part), app.py (part), ownership.py (part), container-e2e-verify.sh (part)
**Not read (planner to read before editing):** `installer/receipts.py`, `installer/wizard_app.py`, `installer/manager_versions.py`, `installer/pnpm_globals.py`
**Pattern extraction date:** 2026-11-03
**Out of scope:** rtk and skill packs; hook registration (23); `cargo_distrobox` (24)
