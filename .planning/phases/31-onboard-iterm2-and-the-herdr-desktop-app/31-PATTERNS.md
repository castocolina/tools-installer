# Phase 31: Onboard iTerm2 and the Herdr desktop app - Pattern Map

**Mapped:** 2026-11-21
**Files analyzed:** 14 (new or modified)
**Analogs found:** 14 / 14 (two are partial)

Note: the brief named a phase-30 directory that does not exist; the file is written to the real phase directory. Every analog path below is git-tracked source (checked: `installer/registry.toml`, `scripts/container-e2e-verify.sh`, `tests/conftest.py`, `tests/e2e_ghostty_driver.py`, `tests/test_container_e2e_ghostty.py`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/terminal_keys.py` (union `Ownership`, `WholeFile`, `OwnedKeys`, dispatch in 3 entry points, hook field, iTerm2 and herdr-app rows, generators, `iterm2_defaults` seam) | service | file-I/O + request-response | same file: `OwnedRegion` rows, `wezterm_show_keys` seam | exact (extends) |
| `installer/post_install.py` (`_tune_terminal` dispatch point) | service | request-response | itself, lines 385-400 | exact (likely no change; generic) |
| `installer/version_status.py` (`_terminal_tuning_fact`, `_TERMINAL_ROWS` routing) | service | read-only status | itself, lines 822-840 | exact (likely no change) |
| `installer/app.py` (`_after_removal` strip) | service | event-driven | itself, lines 622-640 | exact (likely no change) |
| `installer/vendor_defaults/keys.json`, `keys.macos.json` (pinned herdr-app defaults) | config (data) | transform | `installer/patches/kickstart-no-lsp.patch` read via `Path(__file__).parent` (`post_install.py:139`) | role-match |
| `installer/registry.toml` (`iterm2`, `herdr-app`) | config | CRUD | `ghostty` (cask + tuning, 3208-3250), `uv` (script + paths, 74-90) | exact |
| `scripts/container-e2e-verify.sh` (`cmd_herdr_app`, usage, dispatcher) | test harness | batch | `cmd_ghostty` (2979-3005), `cmd_herdr_keys` (2931) | exact |
| `tests/e2e_herdr_app_driver.py` | test driver | batch | `tests/e2e_ghostty_driver.py` | exact |
| `tests/test_container_e2e_herdr_app.py` | test | request-response (stub `ct`) | `tests/test_container_e2e_ghostty.py`, `tests/test_container_e2e_herdr_keys.py` | exact |
| `tests/test_terminal_keys.py` (union, goldens, field list, id sets) | test | transform | itself (field list 2169-2184, id sets ~255, ~290) | exact |
| `tests/test_iterm2_profile.py`, `tests/test_herdr_app_keys.py` (optional splits) | test | transform | `tests/test_terminal_keys.py` | role-match |
| `tests/test_registry.py` (`MACOS_ONLY`, `NO_MACOS_INTEL`, counts, entry tests) | test | CRUD | itself: `MACOS_ARM64_ONLY` honesty test (864-877), `test_ghostty_*` (2255-2333) | exact |
| `tests/test_resolve.py` (four `_FIRST_METHOD` tables) | test | CRUD | itself, `"ghostty"` entries at 593/682/771/860 | exact |
| `tests/conftest.py` (autouse `iterm2_defaults` stub) | test fixture | request-response | `no_wezterm_show_keys` (conftest.py:122-130) | exact |
| `.claude/skills/tool-onboarding/SKILL.md` + `tests/test_tool_onboarding_skill.py` (two rows, two row tests) | docs + test | transform | `ghostty` row (SKILL.md table) and `test_ghostty_row_records_what_is_proven` (642-655) | exact |
| `scripts/e2e-residue-allowlist.txt` (`herdr-core`, `hc`) | config | batch | existing entries in the same file | exact |

## Pattern Assignments

### `installer/terminal_keys.py` (service, file-I/O)

**Analog:** itself. The region path stays byte-for-byte; add branches in front of it.

**Imports pattern** (lines 6-15):
```python
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Final

from installer.agent_settings import read_settings, remove_created_dirs
from installer.atomic import atomic_write_text
from installer.run import CommandError, run_output
```
Add from `agent_settings`: `insert_key`, `remove_key`, `lookup`, `same_value`, `key_held`, `write_if_unchanged` (definitions at `agent_settings.py:290, 486, 109, 117, 134, 562`).

**Union to create** (current state, lines 89-100; `OwnedRegion` docstring says "sole ownership mode until phase 31"):
```python
@dataclass(frozen=True)
class OwnedRegion:
    region: str  # Marker name.
    comment: str = "#"  # Marker comment prefix.
    placement: Placement = Placement.END  # Where a new region goes.

@dataclass(frozen=True)
class KeysRow:
    ownership: OwnedRegion  # The region this row owns.   # retype to Ownership
```
Add `WholeFile(guid)` and `OwnedKeys(seed)` frozen dataclasses with no `placement`, then `Ownership = OwnedRegion | WholeFile | OwnedKeys` (same style as `SameDirectory = Vendor | Writes | NotApplicable`, line 86).

**Dispatch points** (all use `row.ownership.region/.comment/.placement`, which pyright strict rejects through the union): `apply_terminal_keys` 399-409, `terminal_keys_pending` 449-477, `strip_terminal_keys` 508-522. Put `isinstance(row.ownership, WholeFile | OwnedKeys)` branches first and return; leave the region body untouched. `_render` (143-161) concatenates `Writes` text with `"\n\n"`; skip it for non-region rows.

**Seam pattern** (lines 274-281, copy for `iterm2_defaults`):
```python
def wezterm_show_keys(path: Path) -> str | None:
    """The read-back seam that tests replace in tests/conftest.py."""
    binary = which("wezterm")
    return (
        run_output([binary, "--config-file", str(path), "show-keys", "--lua"], timeout=20)
        if binary else None
    )
```
**Record and marker pattern** (lines 370-376, `_record`, `_created_marker`): `xdg_data_home(home, environ) / "tools-installer" / name`. New records: `terminal-iterm2-created`, `terminal-iterm2-default`.

**Core row pattern with optional hook** (kitty row 310-324 and wezterm `readback=` 344): optional fields default `None`; add the default-profile hook field the same way.
```python
"wezterm": KeysRow(
    ownership=OwnedRegion(WEZTERM_KEYS, "--", Placement.BEFORE_RETURN),
    config_path=_wezterm_path, plan=_wezterm_plan, validate=validate_wezterm,
    summary=("WezTerm keys: ..."), created_record=WEZTERM_CREATED,
    same_directory=Vendor("2026-11-20, wezterm source ..."),
    sibling_regions=(WEZTERM,), validate_on_status=True,
    bind_created_path=True, readback=_wezterm_readback,
),
```
**Same-directory declaration:** iterm2 uses `Writes(...)` (kitty `_kitty_cwd`, 234-251 is the model for note text); herdr-app uses `Vendor(note)`.
**Error handling:** copy the `except OSError as exc: return (), first_line(exc)` shape (432-433); refusal text goes out as `"{tool.name} keys not changed: {refusal}"` through `post_install._tune_terminal`.
**Clear chord:** reuse `clear_binding(row, platform_os)` (135-140); `CTRL_L = "\x0c"`.
**Created-marker cleanup:** reuse `_drop_created_config` (528-556) and `remove_created_dirs`.

---

### `installer/post_install.py`, `installer/version_status.py`, `installer/app.py` (generic dispatch points)

**Analog:** the existing code; all three call the row API only, so they should need no edit once the entry points dispatch internally.

`post_install.py:389-399`:
```python
row = TERMINAL_KEYS.get(tool.id)
...
lines, refused = apply_terminal_keys(
    row, tool.id, platform.os, Path.home(), os.environ, skip_recorded=skip_recorded
)
if refused is not None:
    return PostInstallOutput((f"{tool.name} keys not changed: {refused}",), refused=refused)
```
`version_status.py:828-840` (`terminal_keys_pending` -> `KEYS_PENDING` gives `TUNING_PENDING` and `TUNING_STEP`; any other string is a reason). `app.py:630-635` (strip runs before `config_paths` deletion; herdr-app declares `config_paths`, so the owned-key strip must come first, as the herdr ledger revert does at 625-629).
`_TERMINAL_ROWS` routing splits on first colon (`version_status.py` ~1603, table 735-742): add the regression test that `herdr-app: partial: ...` never lands on the `herdr` row. Dispatch tests live in `tests/test_terminal_keys.py`; the planner should confirm no production edit is needed in these three files.

---

### `installer/vendor_defaults/` (data, pinned herdr-app defaults)

**Analog:** `installer/patches/kickstart-no-lsp.patch`, read as `Path(__file__).parent / "patches" / ...` (`post_install.py:139`). hatchling packages all of `installer/`. Pin sha256 (RESEARCH): `d1831fe2...269f` (keys.json), `8728a519...23c0` (keys.macos.json); a test compares the file hash to the constant.

---

### `installer/registry.toml` (config)

**Analog 1, cask plus tuning:** `ghostty` (3208-3250)
```toml
id = "ghostty"
category = "terminal"
priority = "P3"
audience = "human"
tier = "user"
verified = 2026-11-20
config_paths = ["~/.config/ghostty", "~/Library/Application Support/com.mitchellh.ghostty"]
# Install tuning (30 D-11, D-12): ...
post_install = ["apply_terminal_tuning"]
...
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "ghostty"
app = "Ghostty.app"
min_os_version = "13"
```
iterm2: same, one cask method, no `config_paths` (D-06), `cmd` omitted (defaults to id).

**Analog 2, script with `paths` and a `# Verified` comment block:** `uv` (74-90)
```toml
kind = "script"
url = "https://astral.sh/uv/install.sh"
shell = "sh"
bin_dir = "~/.local/bin"
# Verified 2026-11-04: ... `paths` is the two binaries. ...
paths = ["~/.local/bin/uv", "~/.local/bin/uvx"]
```
herdr-app Linux method: `os = ["debian","fedora","arch"]`, four `paths`, no `update`/`remove`/`writable_prefix`. macOS method adds `arch = ["arm64"]`. Add a `# Verified 2026-11-2x` block listing the nested `herdr-core`/`hc` install that stays (SPEC R3). Brew's `homebrew` entry (168-200) shows `arch` on methods and a preflight comment.

---

### `scripts/container-e2e-verify.sh` (`cmd_herdr_app`)

**Analog:** `cmd_ghostty` (2979-3005)
```bash
cmd_ghostty() {
  local failed=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --keep-image) LANDING_KEEP_IMAGE=1 ;;
      *) die "unknown ghostty option: $1" ;;
    esac
    shift
  done
  LANDING_CONTAINER_NAME="tools-installer-e2e-ghostty-$$"
  CONTAINER_NAME="$LANDING_CONTAINER_NAME"
  IMAGE="$LANDING_IMAGE"
  DISTRO=fedora
  LANDING_DRIVER_MODULE=tests.e2e_ghostty_driver
  PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-ghostty"
  LANDING_TRANSCRIPT="$PHASE_DIR/ghostty-transcript.log"
  trap landing_teardown EXIT
  ensure_phase_dir
  : >"$LANDING_TRANSCRIPT"
  landing_note_image
  landing_bootstrap
  landing_stage ghostty-root ghostty_root_setup
  landing_step fuse-pass lifecycle || failed=1
  return "$failed"
}
```
Dispatcher `main()` (~3007) has `ghostty) cmd_ghostty "$@" ;;`: add `herdr-app) cmd_herdr_app "$@" ;;` and the usage line. Root stage installs `libxcb libxkbcommon` (Pitfall 10). Multi-verdict collection shape: `cmd_bun_lifecycle` (~2893). Shellcheck is a gate: run only `shellcheck` on the file.

---

### `tests/e2e_herdr_app_driver.py` (test driver, batch)

**Analog:** `tests/e2e_ghostty_driver.py`
```python
from tests.e2e_landing_driver import (
    Failed, first_line, in_container, install_one, tool_by_id, uninstall_one, verdict,
)
TOOL_ID = "ghostty"
ALLOWLIST = Path("scripts") / "e2e-residue-allowlist.txt"
STANDARD_EMPTY_DIRS: Final = frozenset(
    {".local/share/applications/", ".local/share/icons/", ".local/share/tools-installer/"}
)
```
Copy: verb entry point, pure `*_verdict` functions returning `TRACER_..._OK` strings or raising `Failed`, file-based output capture (no pipes; 120 s hang lesson), `leftovers()` prefix matcher (`:241-251`). Add nested empty icon dirs to the exact empty-dir set (`.local/share/icons/hicolor/scalable/apps/` and parents) and do not count `terminal-tuning-herdr-app` / `terminal-herdr-app-created` as residue while installed.

---

### `tests/test_container_e2e_herdr_app.py` (host test, stubbed `ct`)

**Analog:** `tests/test_container_e2e_ghostty.py` (verdict tests parametrized, lines 1-50) plus `tests/test_container_e2e_herdr_keys.py:40-117` (extracts script functions, runs with a `ct` stub writing a `calls` file). Assert: PID-scoped name, teardown removes exactly that container, root setup installs the libs, failing step does not stop others, dispatcher routes `herdr-app`. Imports follow the ghostty file (`from tests import e2e_ghostty_driver as driver`, `from tests.e2e_landing_driver import Failed, tool_by_id`).

---

### `tests/conftest.py` (autouse seam stub)

**Analog:** `no_wezterm_show_keys` (122-130)
```python
@pytest.fixture(autouse=True)
def no_wezterm_show_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test launches wezterm; read-back sees it as absent."""
    def unavailable(path: Path) -> str | None:
        del path
        return None
    monkeypatch.setattr(terminal_keys, "wezterm_show_keys", unavailable)
```
Add `no_iterm2_defaults` the same way, raising `CommandError(list(argv), 127, detail="no defaults in tests")`; tests needing it monkeypatch a fake runner (four starting states, G3).

---

### `tests/test_terminal_keys.py` (pins)

**Analog:** itself. Field-list pin (2169-2184) must gain the new hook field name (append, matching `readback`/`strip_files` position convention):
```python
assert [field.name for field in dataclasses.fields(KeysRow)] == [
    "ownership", "config_path", "plan", "validate", "summary", "created_record",
    "same_directory", "sibling_regions", "clear", "readback", "validate_on_status",
    "bind_created_path", "strip_files",
]
```
Also update `set(TERMINAL_KEYS) == {...}` (~255) and the `missing_rows(..., {}) == {...}` pin (~290) with `iterm2`, `herdr-app`. Region-row tests must pass unchanged (proof the dispatch did not move them). Golden tests G1-G5 take `platform_os` and run on both CI OSes; strip-and-created-marker fixtures: model on the test ending near line 2160 (`created.exists()` / marker / sidecar assertions).

---

### `tests/test_registry.py` and `tests/test_resolve.py`

**Analog:** `MACOS_ARM64_ONLY` honesty test (test_registry.py:864-877)
```python
def test_macos_arm64_only_allowlist_stays_honest() -> None:
    ...
    intel = Platform(os="macos", arch="amd64", immutable=False, has_brew=True, os_version="26.0")
    assert resolve_methods(tools[tool_id], intel) == []
    arm = Platform(os="macos", arch="arm64", ...)
    assert resolve_methods(tools[tool_id], arm)
```
Copy for `NO_MACOS_INTEL = {"herdr-app"}` (allowed unresolved only when `platform_os == "macos" and arch != "arm64"`; do not reuse `MACOS_ARM64_ONLY`, which excuses every non-macOS platform, lines 835-839). `MACOS_ONLY = {"gnu-bash"}` (798) gains `"iterm2"`. Count pins to bump with comments: tools `87` (1215) to 89; audience `"human": 29` (304) to 31; tier `"user": 50` (1270) to 52; `_POST_15_3_HUMAN_TOOLS` (281 area); post-install declarer set (1377 area). Entry-fact tests: copy `test_ghostty_entry_records_its_facts` (2323-2333) tuple-compare shape. `test_resolve.py` `_FIRST_METHOD`: add `"iterm2"` and `"herdr-app"` next to `"ghostty"` in all four tables (593 macos `"cask"`, 682/771/860 Linux); iterm2 is `None` on the Linux fixtures, herdr-app is `"script"` there and `"cask"` on the arm64 macOS fixture.

---

### `.claude/skills/tool-onboarding/SKILL.md` and `tests/test_tool_onboarding_skill.py`

**Analog:** the `ghostty` table row (seven cells: id, config file, (a), (b), (c), (d), reload; each rule cell starts with a status word `vendor|written|planned|n/a|unverified`) and:
```python
def test_ghostty_row_records_what_is_proven() -> None:
    rows = table_rows(_subsection(_text(SKILL), TABLE_HEADING))
    row = next(row for row in rows if row[0] == "`ghostty`")
    assert len(row) == 7
    assert all(cell.startswith(status) for cell, status in zip(
        row[2:], ("written", "vendor", "written", "vendor", "unverified"), strict=True))
```
Expected statuses from RESEARCH D-18: `iterm2` (b) written, (c) written, (d) written, (a) and reload per plan; `herdr-app` (a) unverified, (b) vendor on macOS and n/a on Linux (cell must start with one word), (c) written, (d) vendor. Every `TERMINAL_KEYS` row's clear cell must start with `written` (test 603-625). The table-drift test (688-704) already requires one row per terminal id.

---

## Shared Patterns

### Seam stubbed in conftest
**Source:** `installer/terminal_keys.py:274-281`, `tests/conftest.py:122-130`. **Apply to:** `iterm2_defaults` (every `defaults` call), nothing else touches `/usr/bin/defaults`.

### Formatting-preserving JSON edits
**Source:** `installer/agent_settings.py` (`insert_key` 290, `remove_key` 486, `key_held` 134, `same_value` 117, `write_if_unchanged` 562). **Apply to:** `OwnedKeys` apply, drift and strip. `insert_key` refuses an empty file and an already-set key (`SettingsEditRefused`); handle both.
```python
def key_held(current: object, ours: object) -> bool | None:
    return None if current is ABSENT else same_value(current, ours)
```

### Records under XDG data
**Source:** `terminal_keys.py:370-376`, `terminal_regions.py:235` (`xdg_data_home`), `694` (`created_path_record`). **Apply to:** iterm2 created and default records, herdr-app tuning and created records; all gone after strip.

### Refusal and message format
**Source:** `post_install.py:396-398`: `"{tool.name} keys not changed: {refused}"`; partial lines are `"<id>: partial: kept yours"`; pending is `KEYS_PENDING`.

### Pure generator plus golden
Every generator takes `platform_os` and recorded state, returns text; goldens live in tests and run on both CI OSes. JSON bytes: `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False) + "\n"`.

### Test hygiene
xdist-safe (tmp_path, monkeypatched HOME and env), offline, no real `defaults` or `install.sh` on the host; `install.sh` only in the container target. Test-first inside one green commit.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `defaults` plist read/write hook (restore ordering, four-state commands) | service | request-response | No `defaults` or plist use exists; only the seam shape (`wezterm_show_keys`) and `use_git_runner` (`post_install.py:142-153`) transfer. Use RESEARCH Pattern 3 and `plistlib`. |
| herdr-app chord normalization (GPUI grammar) | utility | transform | Closest is `ghostty_chord` in `terminal_regions.py` (different grammar); follow RESEARCH R12, not D-16's aliases. |

## Metadata

**Analog search scope:** `installer/`, `tests/`, `scripts/`, `.claude/skills/tool-onboarding/`, `installer/registry.toml`
**Files scanned:** about 14 read or excerpted
**Pattern extraction date:** 2026-11-21
