# Phase 16: Catalog Truth — Pattern Map

**Mapped:** 2026-10-09
**Files analyzed:** 14 existing files modified (no new files — this is a defect-closure phase; every D-xx decision lands inside an already-tracked module per RESEARCH.md's "Recommended Project Structure")
**Analogs found:** 14 / 14 (every analog is a sibling pattern inside the SAME file being modified — this phase is "add a branch to a closed table," not "create a new file from a template")

All paths below were verified tracked: `git ls-files` confirms every file in this map (`installer/ownership.py`, `installer/install_ownership.py`, `installer/model.py`, `installer/skill_lifecycle.py`, `installer/status.py`, `installer/deps.py`, `installer/engine.py`, `installer/catalog_tui.py`, `installer/rcclean.py`, `installer/shellrc.py`, `installer/atomic.py`, `installer/host_setup.py`, `installer/registry.toml`, `installer/wizard_app.py`). No `.gsd/capabilities` mirror paths exist in this repo — not applicable here.

## File Classification

| File (modified, not created) | Role | Data Flow | Closest Analog (same file, sibling branch) | Match Quality |
|---|---|---|---|---|
| `installer/install_ownership.py` (`_sdkman`) | service (probe adapter) | request-response (subprocess probe) | `_brew`/`_dnf` in the same file | exact — same `_method_values` + `_run` shape |
| `installer/ownership.py` (`Owner` literal, `_KIND_TO_OWNER`, `_collect_candidates`, `OWNER_LABELS`, `OWNER_DETAIL_LABELS`, `_REMOVAL_COMMANDS`/`_REMOVAL_DESCRIPTIONS`) | service (evidence resolver) | CRUD (classification over closed tables) | `brew`/`cask`/`uv-tool` branches in the same five tables | exact — closed-table extension, one new case per table |
| `installer/model.py` (`SKILL_HARNESSES`, `SkillOperation`/`SkillLifecycle.status` schema) | model | CRUD (schema/validation) | the tuple/dataclass itself, extended in place | exact — widen tuple, extend dataclass shape |
| `installer/skill_lifecycle.py` (`_status_probe`, `inspect_status` callers) | service | event-driven (background probe, cached) | `installer/host_setup.py`'s `HOST_SETUPS`/`HostProbe` closed table | role-match — same "run this CLI, check substring" shape, different domain |
| `installer/status.py` (D-18 broken predicate) | utility/service | request-response | `is_installed`'s existing `bin_dir` union check, same file | exact — new sibling predicate, not an edit to the existing one |
| `installer/deps.py` (D-17 call-site, NOT `satisfied_by_install` itself) | service | CRUD | `installer/engine.py::install_tool`'s `ALREADY_INSTALLED` gate | role-match — correct layer for the new logic |
| `installer/engine.py` (`install_tool` dispatch) | controller/service | request-response | its own existing `ALREADY_INSTALLED` short-circuit (line 128) | exact — extend the same branch |
| `installer/catalog_tui.py` (`_row_cells`, Inst column, Owner column) | component (TUI) | request-response (render) | `_owner_cell`'s existing multi-source pattern + the `✓`/`○` ternary at line ~513 | exact — same file, sibling cell logic |
| `installer/rcclean.py` (guard-in-place write, D-22 foreign-marker detection) | utility | file I/O | `find_duplicate_path_lines`/`unguarded_path_writers` (detection half, unchanged) and `_managed_line_indices`/`_MANAGED_BEGINS`/`_MANAGED_ENDS` (same file) | exact — new write fn layered on existing detection |
| `installer/shellrc.py` (`path_export_guard`, reused not reimplemented) | utility | transform | itself — called, not modified, by the new rcclean write path | exact (reuse, zero new pattern needed) |
| `installer/atomic.py` (`.tools-installer.old` backup, reused not reimplemented) | utility | file I/O | itself — `staged_sibling`/`OLD_SUFFIX`, Phase 15.8 precedent | exact (reuse) |
| `installer/registry.toml` (kitty location field, sdkman `candidate` params, skill_pack `supported_harnesses` audit) | config | CRUD (static data) | existing sdkman rows (java/groovy/gradle/maven) and existing `bin_dir` usage elsewhere in the file | exact — same schema, corrected/extended data |
| `installer/post_install.py` (D-20 re-application gate) | service | event-driven (one-shot trigger) | its own existing one-shot-trigger doctrine (module docstring) | exact — narrow explicit exception, not a new mechanism |
| `installer/wizard_app.py` (DoctorScreen: D-16 reason text, D-21/D-24 guard-in-place confirmation UI) | component (TUI) | request-response | `DoctorScreen.action_apply`/`_refresh_guidance`'s existing per-item confirmation pattern | exact — same screen, new per-file confirmation rows |

## Pattern Assignments

### `installer/install_ownership.py` — fix `_sdkman` (D-01/D-05)

**Analog:** `_brew`/`_dnf` in the same file (lines 111, 132-133)

**Bug, verified this session** (line 364-365):
```python
def _sdkman(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    candidates = _method_values(tool, {"script"}, "sdk_candidate") or (tool.id,)
```
Registry declares `kind = "sdkman"` with param `candidate` (not `kind="script"`/`sdk_candidate`). **Fix pattern** — copy the sibling shape exactly:
```python
# installer/install_ownership.py:111-112 (the _brew shape to mirror)
def _brew(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    packages = _method_values(tool, {"brew"}, "formula") + _method_values(tool, {"cask"}, "cask")
```
Apply the same `_method_values(tool, {kind}, key)` call shape to `_sdkman`, with `kind="sdkman"`, `key="candidate"`. Keep the `(tool.id,)` fallback only as true last resort; confirm `springbootcli`'s declared `candidate="springboot"` is reached before the fallback ever fires.

**Reused helper (already fail-closed, do not reimplement):** `_method_values` (line 63) and `_run`'s probe wrapper — both already used by every sibling probe in this file. V5-input-validation note from RESEARCH.md: any new parsing of `sk current <candidate>` output must reuse `_PACKAGE_NAME_RE`-style guarding already established, never a bespoke unguarded regex.

---

### `installer/ownership.py` — add `"sdkman"` across five closed tables (D-01/D-02/D-06/D-07/D-08)

**Analog:** the existing `brew`/`cask`/`uv-tool` entries in the SAME five tables.

1. **`Owner` Literal** (lines 77-88): add `"sdkman"` alongside `"brew"`, `"cask"`, etc.
2. **`_KIND_TO_OWNER`** (lines 142-147):
```python
_KIND_TO_OWNER: dict[str, Owner] = {
    "brew": "brew",
    "cask": "cask",
    "node": "pnpm",
    "uv-tool": "uv",
    # add: "sdkman": "sdkman",
}
```
3. **`_collect_candidates`** (lines 798-838) — copy the `brew`/`cask`/`uv-tool` `elif` shape verbatim, substituting an `inventory.sdkman_candidates` field (new `ManagerInventory` field + a new `read_inventory` query, mirroring how `inventory.brew_formulae`/`inventory.uv_tools` are populated):
```python
elif method.kind == "sdkman" and inventory.sdkman_candidates is not None:
    name = manager_name(method, "candidate", tool.cmd)
    if name in inventory.sdkman_candidates:
        found["sdkman"] = OwnershipCandidate(
            owner="sdkman", method=method, package=name,
            current_version=inventory.sdkman_candidates[name],
            evidence=f"sdkman lists {name} as current",
        )
```
4. **`OWNER_LABELS`** / **`OWNER_DETAIL_LABELS`** / **`_REMOVAL_COMMANDS`** / **`_REMOVAL_DESCRIPTIONS`**: each is exhaustiveness-tested against `Owner` (module's own comments at lines ~950/~1021) — add one `"sdkman": "..."` entry to each of the four, modeled on the existing `"brew"`/`"pnpm"`/`"uv"` entries.
5. **Mutation grade:** per RESEARCH.md Pattern 2/Assumption A1, sdkman should join `MUTATION_GRADE`-eligible owners (like brew/pnpm/uv), NOT `UNMANAGEABLE_OWNERS` (reserved for `NATIVE_OWNERS` + `os-package`, lines 92-121) — this is what makes D-05's "update through the real owner" reachable.

**Warning (from RESEARCH.md Pitfall 2, reconfirmed):** skipping any one of the four label/removal tables fails the module's own `typing.get_args(Owner)` exhaustiveness test in `tests/test_ownership.py` — treat that test failure as the checklist, not an obstacle.

---

### `installer/model.py` — widen `SKILL_HARNESSES`, extend status schema (D-09/D-13)

**Analog:** the tuple/dataclass itself (lines 66, 86, 216-236).

Current:
```python
SKILL_HARNESSES = (...)  # line 66, ten values, missing "factory-droid"/"gemini-cli"
SKILL_OPERATION_IDS = ("codex_plugin_status", "pi_package_status")  # line 86
```
`SkillLifecycle.status` (line 236) is a single `SkillOperation`, not per-harness. Per RESEARCH.md Pattern 3/Pitfall 4, recommended shape: one generic `harness_status` operation_id + a `{harness, argv, contains}`-shaped args structure, OR a `tuple[SkillOperation, ...]`/`dict[str, SkillOperation]` on `SkillLifecycle.status` — planner must pick one shape; do not add one dataclass per harness (10 harnesses × dataclass is the anti-pattern RESEARCH.md flags).

Widen `SKILL_HARNESSES` to add `"factory-droid"`, `"gemini-cli"` — decide explicitly whether these two (which this installer cannot itself install) are even probable for D-11's disk-fallback, or read "unknown, not probed."

---

### `installer/skill_lifecycle.py` — extend `_status_probe` (D-09..D-15)

**Analog:** `installer/host_setup.py::HOST_SETUPS` (full file, 45 lines) — the exact "closed table of {argv, contains-substring}" shape already proven for Pi's handoff probe.

```python
# installer/host_setup.py:27-41 — the shape to mirror for a per-harness
# skill_pack status table, replacing _status_probe's 2-branch if-chain:
HOST_SETUPS: dict[str, HostSetup] = {
    "pi": HostSetup(
        handoff=(...),
        probes=(HostProbe(("pnpm", "list", "--global", "--depth", "0", "--json"),
                           "@earendil-works/pi-coding-agent"),),
        owner="pnpm",
    ),
}
```
Current `_status_probe` (skill_lifecycle.py lines 51-60) is exactly this two-branch shape already, just closed at 2 harnesses:
```python
def _status_probe(operation: SkillOperation) -> tuple[list[str], str]:
    if operation.operation_id == "codex_plugin_status" and isinstance(...):
        return ["codex", "plugin", "list"], operation.args.plugin
    if operation.operation_id == "pi_package_status" and isinstance(...):
        return ["pi", "list"], operation.args.package
    raise ValueError("unreviewed skill lifecycle status operation")
```
Replace with a closed per-harness-name lookup table (`HARNESS_STATUS_PROBES: dict[str, HarnessStatusProbe]`), mirroring `HOST_SETUPS`'s dict shape, keyed by harness name instead of setup_id. Wire `inspect_status` (currently zero production callers — confirmed `grep` shows only test imports) into a background `Worker`, reusing `installer/version_cache.py`'s staleness model (`VersionCacheEntry`, `is_stale`) for D-10/D-14's caching — do not build a new cache file.

---

### `installer/status.py` — D-18 broken-shim predicate

**Analog:** `is_installed`'s own existing `bin_dir` union check, same file (lines ~46-56) — reused, not edited.

**Pattern:** add a sibling pure predicate, e.g. `is_broken(tool, inventory) -> bool`, that returns True when `is_installed` is True (shim/binary present) AND the owning manager's inventory says the backing package is absent (e.g. pnpm shim present but `pnpm list --global` no longer lists the module — the mmdc repro case). Per RESEARCH.md Pitfall 5: do **not** change `is_installed`'s return type to `bool | Literal["broken"]` — every existing caller (`deps.py`, `engine.py`'s `ALREADY_INSTALLED` gate, `resolve_dependencies`) treats it as a plain boolean.

---

### `installer/catalog_tui.py` — tri-state Inst cell + "≠ policy" marker (D-02/D-12/D-13/D-18)

**Analog:** `_owner_cell` and the existing `✓`/`○` ternary, same file.

```python
# installer/catalog_tui.py _row_cells (current ternary to extend):
Text("✓", style="green") if installed else Text("○", style="yellow"),
```
Add a THIRD state fed by a new parallel map (e.g. `self._broken: dict[str, bool]`), mirroring how Owner is already a second data source alongside `self._installed` rather than a repurposing of the boolean — do not overload `installed` with a sentinel.

```python
# installer/catalog_tui.py _owner_cell pattern (existing multi-source shape
# to extend for D-02's "≠ policy" marker and D-13's multi-host truncation):
ownership = service.ownership_of(tool.id) if service is not None else None
if ownership is None:
    return Text(_VER_CHECKING, style="dim") if self.version_refreshing else Text("")
label = owner_label(ownership)
return Text(label) if label else Text("")
```
D-12's stale-cache convention to reuse verbatim: `_VER_STALE = "~"` (line ~206) — the dim `~` suffix already used for stale version cells is the exact mechanism to reuse for "Inst column shows last cached answer while a skill_pack probe is in flight."

---

### `installer/deps.py` / `installer/engine.py` — D-17 explicit re-selection path

**Do NOT edit `satisfied_by_install`** (deps.py line 111) — per RESEARCH.md Pitfall 6, that set-comprehension is correctly scoped to drag-in ordering and is also consulted by `missing_requires`'s preview; editing it breaks both.

**Analog:** `installer/engine.py::install_tool`'s own existing `ALREADY_INSTALLED` short-circuit (line 128):
```python
# installer/engine.py:123-128 (existing shape, the comment above it already
# documents the non-interactive-skip doctrine D-17/D-20 extend)
# unattended case and skips them. The ALREADY_INSTALLED short-circuit never
...
    return InstallOutcome(tool.id, InstallStatus.ALREADY_INSTALLED)
```
D-17's new logic (outdated → update through real owner; current → "already current, nothing to do"; policies re-applied regardless) belongs as a new branch inside this same dispatch, checked only for an EXPLICITLY selected tool, before/alongside this short-circuit — not inside `resolve_dependencies`.

---

### `installer/post_install.py` — D-20 one-shot exception

**Analog:** the module's own existing one-shot-trigger doctrine (module docstring, lines 1-22) — this is the pattern to preserve, with a narrow carve-out for "fresh explicit selection only," not a new mechanism.

---

### `installer/rcclean.py` — D-21/D-22/D-24 guard-in-place write

**Analog (detection, unchanged):** `find_duplicate_path_lines`/`unguarded_path_writers` (lines 61, 112) — already has production callers in `app.py`/`wizard_app.py`. Do not rewrite this scanner.

**Analog (marker detection to generalize for D-22):**
```python
# installer/rcclean.py:13-14 (this project's OWN markers — hard-coded, 2 pairs)
_MANAGED_BEGINS = ("# >>> tools-installer path >>>", "# >>> tools-installer source >>>")
_MANAGED_ENDS = ("# <<< tools-installer path <<<", "# <<< tools-installer source <<<")
```
and `_managed_line_indices` (line 47) which matches only these two literal pairs. D-22's new work: a generalized "any `# >>> ... >>>` / `# <<< ... <<<` marker pair, not just ours" detector, modeled on the SAME begin/end-depth-tracking loop shape `_managed_line_indices` already uses, but matching a regex instead of the two literal tuples.

**New write function (D-21):** takes a flagged unguarded line + file + directory, produces `path_export_guard`'s case-guard text (reused verbatim, see below) at the same line position — inside the existing backup-then-write flow.

**Reused verbatim (no new pattern):**
```python
# installer/shellrc.py:82-122 — path_export_guard(directory) -> str
# D-21's rewrite must call this, not hand-write a case-guard string, to
# inherit its set -u safety and empty-PATH-becomes-cwd guard.
```
```python
# installer/atomic.py — staged_sibling/.tools-installer.old convention
NEW_SUFFIX = ".tools-installer.new"
OLD_SUFFIX = ".tools-installer.old"
def staged_sibling(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)
```
Phase 15.8's byte-exact, no-clobber, lstat-checked backup discipline (`.claude/architecture.md` Phase 15.8 section) applies verbatim — do not reimplement the refusal logic.

---

### `installer/registry.toml` — D-19 kitty location, D-09 harness audit, sdkman param fix

**Analog:** existing sdkman rows (`java`/`groovy`/`gradle`/`maven`, confirmed present with `kind = "sdkman"` + `candidate = "..."` param) — the correctness baseline the `_sdkman` probe fix (above) must match exactly, including `springbootcli`'s `candidate = "springboot"` (not matching its `tool.id`).

**Kitty fix (D-19):** per RESEARCH.md Pitfall 7, try `bin_dir = "~/.local/kitty.app/bin"` first (reuses `status.py`'s existing `bin_dir` union check verbatim — zero new schema) before inventing a new "nested app bundle" field.

---

### `installer/wizard_app.py` (DoctorScreen) — D-16/D-21/D-24 UI

**Analog:** `DoctorScreen.action_apply`/`_refresh_guidance`'s existing per-item conditional-guidance pattern (Phase 15's D-01/D-02 precedent, per CONTEXT.md canonical refs) — D-16's "short reason" row text and D-24's per-file guard-in-place confirmation both extend this same screen's existing listing-then-confirm shape, not a new screen.

## Shared Patterns

### Closed-table extension (architecture.md rule 5)
**Source:** every table above (`Owner` literal, `_KIND_TO_OWNER`, `OWNER_LABELS`, `_PROBES`, `SKILL_HARNESSES`, `HOST_SETUPS`-shaped lookup, `_MANAGED_BEGINS`/`_MANAGED_ENDS`)
**Apply to:** every D-xx in this phase. The single unifying instruction: add one new entry to an EXISTING closed table/dict/Literal, never a parallel mechanism solving the same question a second way.

### Fail-closed subprocess probing
**Source:** `installer/install_ownership.py::_run` + `_PACKAGE_NAME_RE`
**Apply to:** the `_sdkman` probe fix and any new harness-CLI probe in `skill_lifecycle.py` — untrusted stdout must go through the same guarded wrapper, never a bespoke unguarded regex.

### Version/ownership caching with staleness
**Source:** `installer/version_cache.py` (`VersionCacheEntry`, `is_stale`, `should_fetch`)
**Apply to:** D-10/D-14 skill_pack per-harness status caching — extend this envelope, do not create a parallel skill_pack JSON cache.

### Atomic backup-then-write
**Source:** `installer/atomic.py` (`staged_sibling`, `OLD_SUFFIX`)
**Apply to:** D-21/D-23's guard-in-place rc-file rewrite.

## No Analog Found

None — every file in scope is an edit to an already-existing, already-tracked module, and every edit has a same-file or closely-related sibling pattern to copy (see table above). This phase introduces zero new top-level files.

## Metadata

**Analog search scope:** `installer/` (14 existing modules named in RESEARCH.md's "Recommended Project Structure"); no new directories.
**Files scanned:** 14 (all read in full or targeted sections this session plus RESEARCH.md's prior full reads).
**Pattern extraction date:** 2026-10-09
