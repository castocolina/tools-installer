# Phase 19: One tool state with health plus receipts - Pattern Map

**Mapped:** 2026-10-16
**Files analyzed:** 19 new/modified
**Analogs found:** 19 / 19 (all analog paths are git-tracked source; `installer/receipts.py` is new and not yet tracked)

Line numbers were read at HEAD `db6d94b` (code tree equals `424b301`). Anchor by symbol when the tree moves. Line refs already verified in 19-RESEARCH.md are reused, not repeated.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/receipts.py` (NEW: Receipt/Artifact, `read`, `write`/`record`, `matches`, `adopt`, `receipts_dir()`) | store | file-I/O (CRUD) | `installer/settings.py` (`default_settings_path` 52, `load_settings`, `save_settings` 90-93) + `installer/version_cache.py` (`save_version_cache` 220-249) | exact |
| `installer/version_status.py` (`Health`, `Evidence`, `tool_health`, `ToolState`, `state_of`, pass seq, one swap) | service/store | event-driven (refresh pass) | itself: `__init__` lock/epoch (485-505), `ownership_of` (523-542), `refresh` (690-784) | exact |
| `installer/enums.py` (or `version_status.py`) `Health` StrEnum | model | n/a | `installer/enums.py:3-10` `Priority(StrEnum)` | exact |
| `installer/download.py` (`artifact_paths`, `cli_spec` moved from apps.py) | utility | transform | `download.resolve_target` (99-162), `is_still_proven` (188-204), `apps.cli_spec` | exact |
| `installer/apps.py` (drop `cli_spec`, import from download) | service | file-I/O | itself | exact |
| `installer/engine.py` (receipt write point) | service | event-driven ladder | `install_tool` success `else:` (234-240), `_HANDOFF_KINDS` (28) | exact |
| `installer/update.py` (receipt write after `_perform`; refuse `volta`) | service | request-response | `_perform` (285-309) | exact |
| `installer/uninstall.py` (`plan_removal` receipt-aware; `still_removable` re-proof; `plan_uninstall` -> `artifact_paths`) | service | transform | `RemovalPlan` (113-125), `still_removable` (128-138) | exact |
| `installer/install_ownership.py` (batched NativeIndex, memoized rpm-ostree) | service | batch | `run_probe` (51-60), `_run` (76-80), `_rpm_ostree` (150), `_PACKAGE_NAME_RE`/`_one_name` (239-248), fail-closed docstring (1-16) | exact |
| `installer/ownership.py` (`volta` Owner, `uv tool dir` prefix, NativeIndex consumer, host_setup owner) | service | request-response | `Owner` (77-90), `owner_dirs` (445-457), `attribute_path` (470-472), `_os_package_owner` (862-911) | exact |
| `installer/guards.py` (shim look-through size guard) | utility | file-I/O | `is_our_shim` (277), `real_binary` (287-313) | exact |
| `installer/status.py` (implicit `~/.local/bin` presence; stub -> MISSING) | service | request-response | `is_installed` bin_dir loop (96-107), `MACOS_STUBS` (14-17) | exact |
| `installer/terminal_shell.py` (`write` flag, `drifted`) | service | file-I/O | `_replace_owned_region` (72-108), `_write_if_changed` | exact |
| `installer/skill_lifecycle.py` (claude JSON entries, project-pack detection) | service | request-response | `_claude_matches` (34-42), `inspect_skill_packs` (413-426) | exact |
| `installer/catalog_tui.py` (`health_cell`, legend, detail; delete `_installed`/`_BROKEN_MARK`/`set_installed`; refresh callers 431/974) | component | event-driven | `_inst_cell` (493-505), `_LEGEND` block (213-268), `set_installed` (383) | exact |
| `installer/tool_browser.py` (legend/detail stacking, Rule margin) | component | n/a | `#browser-legend` CSS (110), `compose` legend (139-140) | exact |
| `installer/execute_screen.py` (refresh caller 749) | component | event-driven | itself 745-752 | exact |
| `setup.py` (wiring: receipts dir, `uv tool dir`, NativeIndex, uninstall closures via `state_of`) | config/wiring | n/a | existing service construction + `setup.py:860`, `:1364` | exact |
| `tests/test_receipts.py` (NEW), `tests/conftest.py` (receipts sandbox + fingerprint) | test | n/a | `tests/test_settings.py`, `tests/test_atomic.py`; `conftest.py:19-75` | exact |

## Pattern Assignments

### `installer/receipts.py` (store, file-I/O) — NEW

**Analog:** `installer/settings.py` + `installer/atomic.py`

Path resolved at call time (settings.py:51-52), receipts go next to it:
```python
def default_settings_path() -> Path:
    return Path.home() / ".local" / "state" / "tools-installer" / "settings.json"
```

Writer (settings.py:90-93) — `ensure_dir` first, because `atomic_write_bytes` creates no parent:
```python
def save_settings(path: Path, settings: Settings) -> None:
    payload = {"version": 1, "link_mode": settings.link_mode}
    ensure_dir(path.parent)
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")
```

Atomic primitive (atomic.py:34-58) — temp sibling + `os.replace`, unlink on `OSError`. Do not reimplement; call `atomic_write_text(path, text)`.

Reader: copy the "fails closed, never raises" contract from `install_ownership.py:1-16` (catch `RecursionError` alongside decode errors) and the three-outcome style of `load_settings` (settings.py:55+). Add: size cap 64 KiB, `v == 1`, `tool == tool_id`, known artifact `type`, absolute paths; any rejection -> `None`. Assert id fullmatches `[a-z0-9][a-z0-9._-]*` (id becomes a filename). One module-level `threading.Lock()` serializes `write`/`adopt` (lock shape: `version_status.py:485`).

Digest: `checksums.sha256_file` (checksums.py:55-58). Imports allowed: `atomic`, `checksums`, `download`, `model`, `locations` only (cycle rule, RESEARCH line 190).

---

### `installer/version_status.py` (service, one swap)

**Analog:** itself.

Lock + epoch fields (485-505): `self._lock = threading.Lock()`, `self._epoch = 0`, one epoch-tagged map `dict[str, tuple[int, ManagerOwnership]]` — the comment there (no parallel maps, no reader lock) is the invariant `ToolState` must keep. Replace `_statuses`/`_ownership`/`_skills` with one `(generation, Mapping[str, ToolState])` attribute.

Fail-closed read order (523-542) — copy verbatim into `state_of`:
```python
pair = self._ownership.get(tool_id)
if pair is None:
    return None
epoch, ownership = pair
if epoch != self._epoch:
    return None
return ownership
```

Raced-pass discard (refresh, ~740-745): `started_epoch = self.epoch` at pass start; under `self._lock`, `if self._epoch != started_epoch:` publish nothing. Add a monotonic pass sequence beside it (Ledger L-19-02) so an older full pass cannot overwrite a newer one; the single assignment replaces `self._ownership.update(...)`.

`Health` StrEnum follows `installer/enums.py:3-10`:
```python
from enum import StrEnum

class Priority(StrEnum):
    """Catalog install priority."""
    P0 = "P0"
```
Declaration order is precedence (D-01).

---

### `installer/engine.py` (receipt write point)

**Analog:** `install_tool` success branch (engine.py:234-240):
```python
        else:
            warning = None
            if tool.postinstall:
                try:
                    warning = run_postinstall(tool.postinstall, method, runner, tools or {})
```
Insert `receipts.record(...)` at the top of `else:` before `run_postinstall`; skip `_HANDOFF_KINDS` (28) and native kinds. A receipt write `OSError` must not turn INSTALLED into a failure — mirror the postinstall warning isolation (`except ... warning = ...`).

### `installer/update.py`

**Analog:** `_perform` (285-309): call the same `receipts.record` after owner dispatch, before `_run_postinstall`; for brew/uv/pnpm only when a receipt already exists. Add `volta` refusal before `raise UpdateError(f"unsupported owner {owner!r}")` (308).

### `installer/uninstall.py`

**Analog:** `RemovalPlan` (113-125) keeps its shape; `still_removable` (128-138):
```python
def still_removable(path: Path, bin_dir: Path) -> bool:
    if is_still_proven(path):
        return True
    return path == opt_dir(path.name) and is_still_proven(bin_dir / path.name)
```
Extend with a receipt re-read + `receipts.matches` (sha256/readlink) as an extra proof source. Keep the raw-member guard (`("", ".", "..")`, 70-74) when `_download_link`/`_plan_app` collapse into `download.artifact_paths`.

### `installer/download.py` (`artifact_paths`)

**Analog:** `resolve_target` (99-162) for name rendering; `is_still_proven` (188-204) for archive proof. Move `apps.cli_spec` here unchanged; `apps.py` imports it back.

### `installer/install_ownership.py` (NativeIndex)

**Analog:** `run_probe` (51-60, `check=True`) and `_run` (76-80, every failure -> `None`). Batch variant catches `subprocess.CalledProcessError` and parses `exc.stdout`; keep `_PACKAGE_NAME_RE` + `_one_name` (239-248). Memoize `_rpm_ostree` (150) per pass. Test fakes raise `CalledProcessError(rc, cmd, output=...)` — existing fakes in `tests/test_install_ownership.py`.

### `installer/ownership.py`

**Analog:** `Owner` literal (77-90), `owner_dirs` (445-457) — take the uv tool dir as a parameter (stays pure), `attribute_path` resolves symlinks (470-472). Volta synthetic candidate copies `_os_package_owner` (862-911). Every exhaustive table gets `volta`: `OWNER_LABELS`, `OWNER_DETAIL_LABELS`, `_REMOVAL_COMMANDS`, `_REMOVAL_DESCRIPTIONS` (exhaustiveness test `tests/test_ownership.py:965`).

### `installer/guards.py`, `installer/status.py`, `installer/terminal_shell.py`, `installer/skill_lifecycle.py`

Edits in place at the seams listed in the table; each analog is the function being extended (no new pattern). Guard `is_our_shim` (277, `path.read_text()`) with `lstat().st_size < 8192`. `terminal_shell`: thread `write: bool` to the existing `_write_if_changed` calls around pure `_replace_owned_region` (72-108).

### `installer/catalog_tui.py` (component)

**Analog:** `_inst_cell` (493-505) — the cell `health_cell` replaces:
```python
    def _inst_cell(self, tool: Tool, installed: bool) -> Text:
        if tool.skill_lifecycle is None:
            service = self._version_refresh
            ownership = service.ownership_of(tool.id) if service is not None else None
            if ownership is not None and ownership.broken:
                return Text(_BROKEN_MARK, style="red")
            return Text("✓", style="green") if installed else Text("○", style="yellow")
```
New shape: one `state_of(tool.id)` lookup -> `Text(glyph, style)` from a `Health -> (glyph, style)` table. Legend: extend the single `_LEGEND` string (213-268 comment block explains the one-widget, explicit-`\n`-per-group, 78-col rule). Refresh callers: `catalog_tui.py:431` (`service.refresh(self.tools)`) and `:974` (`refresh.refresh([target.tool])`) — single-tool/tier-subset calls must merge into, not replace, the full snapshot (Pitfall 1).

### `installer/tool_browser.py`

**Analog:** CSS 110 `#browser-legend { dock: bottom; height: auto; max-height: 3; padding: 0 1; }` and compose 139-140 (`Static(Text.from_markup(self._adapter.legend), id="browser-legend")`). Detail/legend stacking and Rule margin per 19-UI-SPEC.

### `installer/execute_screen.py`

**Analog:** itself 745-752 — `ownership_of` None -> `run_live(partial(refresh.refresh, [tool]))`. Swap to `state_of`; same partial-refresh merge rule as above.

### `tests/conftest.py`

**Analog:** itself 19-75. Add `.local/state/tools-installer/receipts` to `_real_home_fingerprint` (pattern of the `"<backups>"` glob entry, line 49) and add an autouse function-scope fixture redirecting `receipts_dir` to `tmp_path` (monkeypatch by name, as the `real_home_untouched` docstring requires).

### `tests/test_receipts.py` (NEW)

**Analog:** `tests/test_settings.py` (round-trip, corrupt/undecodable -> default) and `tests/test_atomic.py`. Barrier tests for pass sequence copy `tests/test_version_status.py:1130-1185` (two `threading.Event`s held inside an injected `resolve_tag`, never sleep). Legend budget pin: `tests/test_catalog_tui.py:1878-1899` (`_LEGEND.split("\n")`, 3 lines, <= 78 cols plain text).

## Shared Patterns

- **Atomic JSON write:** `ensure_dir(parent)` + `atomic_write_text(path, json.dumps(payload, indent=2) + "\n")` (settings.py:90-93, version_cache.py:249). Apply to receipts.
- **Fail-closed parsing of untrusted input:** return `None`, never raise; catch `RecursionError` too (install_ownership.py:1-16). Apply to receipts reader, NativeIndex, claude JSON.
- **Epoch-gated single-lookup reads:** record first, epoch second (version_status.py:523-542). Apply to `state_of`.
- **Wiring only in setup.py:** real `which`, PATH, `uv tool dir`, receipts dir bound there; logic in `installer/`.

## No Analog Found

None. `receipts.py` is new but composes the settings/version-cache writer and the install_ownership fail-closed reader.

## Metadata

**Analog search scope:** `installer/`, `tests/`, Phase 18 PATTERNS precedent
**Pattern extraction date:** 2026-10-16
