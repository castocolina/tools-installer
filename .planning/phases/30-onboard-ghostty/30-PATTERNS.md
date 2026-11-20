# Phase 30: Onboard Ghostty - Pattern Map

**Mapped:** 2026-11-20
**Files analyzed:** 19 new/modified files
**Analogs found:** 19 / 19 (the menu-entry extraction step and the macOS-aware two-file scan are partial; see "No Analog Found")

Note: the brief named `.planning/phases/30-terminal-defaults-for-the-terminals-in-the-catalog/`; the real phase directory is `30-onboard-ghostty/` (CONTEXT and RESEARCH live there), so this file is written there. All analog paths below are git-tracked source (checked with `git ls-files`; nothing under `.gsd/capabilities` is cited).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/registry.toml` (ghostty `[[tool]]`) | config (catalog data) | request-response (resolve) | wezterm block `:3101-3131`; pinned `app`/`tarball` pins at drawio `:3336-3345`; alacritty `config_paths` `:3152-3164` | exact (role) |
| `installer/model.py` (`METHOD_PARAMS["tarball"]` + `raw`/`note`/`desktop` validation) | model/loader | transform | same file `:83-96`, `:630-680` (the `strip`/`raw` refusal) | exact |
| `installer/download.py` (menu entry + leaves in `artifact_paths`, extraction in `install_download`) | service | file-I/O | `installer/cargo_distrobox.py:150-200` (`_stage`/`_swap`) + `download.artifact_paths` `:284-330` | role-match |
| `installer/desktop_entry.py` (optional drop of `X-KDE-Shortcuts`) | utility (pure) | transform | itself `:36-52` (`render`) | exact |
| `installer/engine.py` (`_perform` note channel) | service | request-response | itself `:138-157` (cargo_distrobox returns notes) | exact |
| `installer/terminal_regions.py` (GHOSTTY consts, `ghostty_config_path`, `ghostty_default_files`, scan, chord normalizer, `validate_ghostty`) | utility | transform | `kitty_config_path`/`scan_kitty`/`kitty_chord`/`kitty_maps`/`validate_kitty` `:240-439` | exact |
| `installer/terminal_keys.py` (fourth `TERMINAL_KEYS` row, `_ghostty_plan`) | model/config | request-response | `TERMINAL_KEYS["kitty"]` `:275-289` and `_kitty_plan` `:160-196` | exact |
| `installer/terminal_shell.py` (`_sync_ghostty`, sync branch, `_revert_terminal_shells` line) | service | file-I/O | `_sync_alacritty` `:483-507`, branch `:756-765`, revert `:627-632` | exact |
| `installer/version_status.py` (`_TERMINAL_ROWS`) | config | event-driven (status pass) | itself `:735-741` | exact |
| `scripts/container-e2e-verify.sh` (`ghostty` target, pure verdict fn, usage text, dispatch) | script | batch | `cmd_herdr_keys` `:2913-2938`, dispatch `:2960-2975`, usage `:95-135` | exact |
| `tests/e2e_ghostty_driver.py` | test driver | request-response | `tests/e2e_herdr_keys_driver.py` | exact |
| `tests/test_container_e2e_ghostty.py` | test | request-response | `tests/test_container_e2e_herdr_keys.py` | exact |
| `tests/test_registry.py` (pins, counts, resolve test) | test | transform | `test_wezterm_appimage_covers_bazzite_where_kitty_cannot` `:1632-1657` | exact |
| `tests/test_model.py` (raw+strip, raw+archive, bad note, bad desktop) | test | transform | existing `strip` refusal tests near `:1397-1410` | role-match |
| `tests/test_terminal_keys.py` (goldens, resolver cases, conflicts, drift, strip) | test | CRUD | kitty goldens `:398-440`, `test_kitty_config_path_follows_kittys_order` `:442`, drift `:1256-1362` | exact |
| `tests/test_terminal_shell.py` (shell region, partials, revert) | test | CRUD | alacritty `:1161-1236` | exact |
| `tests/test_download.py` (extraction, leaves, mismatch places nothing) | test | file-I/O | `:1146` `ChecksumMismatch`, `:1187` verified raw copy, `:396` raw copy leaves no sibling | role-match |
| `.claude/skills/tool-onboarding/SKILL.md` (ghostty row) | doc (closed table) | n/a | kitty/wezterm rows `:209-218` | exact |
| `tests/test_tool_onboarding_skill.py` (pins) | test | transform | `test_table_matches_the_registry` `:642`, `test_table_cells_follow_the_terminal_keys_table` `:628` | exact |

## Pattern Assignments

### `installer/registry.toml` (config, request-response)

**Analog:** wezterm block (`registry.toml:3101-3131`) for the terminal shape, drawio `app` method (`:3336-3345`) for a pinned `{ver}` URL with a literal `v`, alacritty (`:3152-3164`) for `config_paths` + `post_install`.

**Entry shape** (wezterm, `:3103-3131`):
```toml
[[tool]]
id = "wezterm"
name = "WezTerm"
category = "terminal"
cmd = "wezterm"
priority = "P3"
audience = "human"
tier = "user"
verified = 2026-11-03
desc = "GPU-accelerated, cross-platform terminal emulator with multiplexing"
owner_probes = ["pacman"]
# Install tuning (29 D-06, D-07): ...
post_install = ["apply_terminal_tuning"]
[[tool.method]]
kind = "pacman"
package = "wezterm"
...
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "wezterm"
app = "WezTerm.app"
```

**Pinned URL shape** (drawio, `:3336-3345`): `url = ".../releases/download/v{ver}/draw.io-arm64-{ver}.zip"`, `version = "32.6.10"`, `sha256 = "<64 lowercase hex>"`. Copy this for the two ghostty tarball methods (`raw = true`, `member = "ghostty"`, new `desktop` and `note` keys). A `# Verified 2026-11-20` comment goes above the entry (RESEARCH "Registry entry skeleton" `:392-438` is the ready skeleton; pins in D-02).

---

### `installer/model.py` (model/loader, transform)

**Analog:** itself.

**Allowed-key set to extend** (`:83-96`): add `"raw"`, `"note"`, `"desktop"` to `METHOD_PARAMS["tarball"]` (today `url member strip bin_name archive bin_dir version sha256 smoke_argv`).

**Refusal pattern to copy for `raw`+`archive`, bad `note`, bad `desktop`** (`:661-673`):
```python
if "strip" in params:
    strip = params["strip"]
    if params.get("archive") == "zip" or params.get("raw") is True:
        raise ValueError(
            f"tool '{row['id']}': 'strip' does not apply to a zip archive "
            "or a raw asset"
        )
```
Pinned-url validation to leave as is (`:646-666`, `_PINNED_SHA256_RE.fullmatch`). Error text always starts `tool '<id>': method '<kind>' ...`.

---

### `installer/download.py` (service, file-I/O)

**Analog:** `installer/download.py` itself plus `installer/cargo_distrobox.py:150-200` for the desktop render + staged swap.

**Raw install flow to extend** (`download.py:398-436`): fetch+verify into `workdir`, `_replace_raw(link, asset_path, smoke_argv=...)`, `shutil.rmtree(workdir, ignore_errors=True)` in `finally`. Extract the menu files after `_fetch_verified` and before `_replace_raw`, via `ctx.runner` (keeps tests offline).

**Artifact formula to extend** (`download.py:306-312`):
```python
if method.params.get("raw") is True:
    return (Artifact(bin_base / name, "file"),)
return (Artifact(opt_dir(name), "dir"), Artifact(bin_base / name, "link"))
```
Add two `Artifact(path, "leaf")` entries when `desktop` is set (the `cargo_distrobox` branch at `:337-340` already returns a first `file` plus type-only `leaf`s with the comment "a user's edit to the desktop entry never turns the receipt BROKEN").

**Desktop render + keep-user-file + swap** (`cargo_distrobox.py:150-200`):
```python
proven = receipts.recorded_elsewhere("")
...
if host != binary and os.path.lexists(host) and host not in proven:
    notes.append(f"kept your existing {locations.display_path(host)}")
    continue
new = staged_sibling(host, NEW_SUFFIX)
staged.append((new, host))
host.parent.mkdir(parents=True, exist_ok=True)
if host.suffix == ".desktop":
    text = render(source.read_text(encoding="utf-8"), binary=binary, icon=icon)
    atomic_write_text(new, text, mode=0o644)
else:
    shutil.copyfile(source, new)
    new.chmod(0o755 if host == binary else 0o644)
...
def _swap(staged: list[tuple[Path, Path]]) -> None:  # with rollback
```
RESEARCH recommends moving `_swap` to a shared module only if download becomes a second caller (architecture rule 5: no duplicate; a shared helper needs production callers). Staging safety: read only the two fixed names under `workdir/AppDir/` and refuse symlinks (`staged_member`, `executors.py:61-70`).

---

### `installer/desktop_entry.py` (utility, transform)

**Analog:** itself (`:36-52`). `render(source, *, binary, icon)` rewrites only `TryExec=`, `Exec=` and `Icon=`; absolute-path and control-character refusal in `_checked` (`:21-27`). If dropping `X-KDE-Shortcuts` (RESEARCH A4/R14), add one optional parameter in the same loop, e.g. an `elif line.startswith("X-KDE-Shortcuts=")` branch, and a test in `tests/test_desktop_entry.py` (fixture: the 694-byte file from probe 1, RESEARCH Wave 0).

---

### `installer/engine.py` (service, request-response)

**Analog:** itself, `_perform` (`:138-157`).
```python
if method.kind in download.DOWNLOAD_KINDS:
    reason = download.install_download(method, ctx)
    return reason is None, reason, ()
...
if method.kind == "cargo_distrobox":
    return False, None, cargo_distrobox.install(method, ctx)
```
Change the download line to return `((note,) if isinstance(note, str) else ())` from `method.params.get("note")` (RESEARCH Code Examples `:383-390`); notes flow to `postinstall_warning` (`engine.py:353-357`) and render at `render.py:485-497`.

---

### `installer/terminal_regions.py` (utility, transform)

**Analog:** kitty section `terminal_regions.py:240-439`.

**Constants + resolver signature** (`:240-266`):
```python
KITTY = "kitty"
KITTY_KEYS = "kitty-keys"
KITTY_CREATED = "terminal-kitty-created"

def kitty_config_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    ...
    if platform_os == "macos":
        roots.append(home / "Library" / "Preferences")
    ...
    return xdg_config_home(home, environ) / "kitty" / "kitty.conf"
```
New: `GHOSTTY = "ghostty"`, `GHOSTTY_KEYS = "ghostty-keys"`, `GHOSTTY_CREATED = "terminal-ghostty-created"`, `ghostty_config_path(platform_os, home, environ)` (pure, the D-09/D-13 logic, sketch in RESEARCH Pattern 2 `:271-279`), and `ghostty_default_files(platform_os, home, environ)` returning the load-order list (2 Linux, 4 macOS).

**Chord normalizer** (`kitty_chord`, `:277-296`): same alias map (`control`->`ctrl`, `opt`/`option`->`alt`, `cmd`/`command`->`super`), sorted modifiers + key. Add Ghostty extras: strip `all:`/`global:`/`unconsumed:`/`performable:` prefixes, skip `>` sequences, `/` tables and `chain=`, map `key_k`->`k`.

**Scan strips both owned regions before parsing** (`scan_kitty`, `:321-323`):
```python
outside = replace_owned_region(replace_owned_region(source, KITTY, None), KITTY_KEYS, None)
for line in outside.splitlines():
```
Read each default file with `read_capped` (`:378`, `read_capped(target, 1 << 20, follow_symlinks=True)`), keep the unreadable-file partial line shape (`:385-389`: `"kitty: partial: {name} could not be read; maps there are not checked"`).

**Conflict result + report shape** (`kitty_maps`, `:416-426`): `conflicts.append(f"kitty: partial: you already map {chord}")` -> `ghostty: partial: you already bind ctrl+shift+k`.

**Validate** (`validate_kitty`, `:429-439`): return early if markers absent; each non-blank region line must start with `map ` -> for Ghostty `keybind =`; `TerminalShellError("... nothing written")`. Ghostty shell region lines must start with `command =`.

**Created marker/commit** already generic: `commit_region(... created_marker=, bind_path=True)` at `:553-580` and `strip_region` at `:583-592`; `Placement.TOP` at `:26-29,214-215`.

---

### `installer/terminal_keys.py` (config row, request-response)

**Analog:** `TERMINAL_KEYS["kitty"]` (`:275-289`) and `_kitty_plan` (`:160-196`).

**Row to copy** (`:275-289`):
```python
"kitty": KeysRow(
    ownership=OwnedRegion(KITTY_KEYS, "#", Placement.TOP),
    config_path=kitty_config_path,
    plan=_kitty_plan,
    validate=validate_kitty,
    summary=("kitty keys: ..."),
    created_record=KITTY_CREATED,
    same_directory=Writes(_kitty_cwd),
    sibling_regions=(KITTY,),
    bind_created_path=True,
),
```
Ghostty row: `same_directory=Vendor("2026-11-20, Ghostty Config.zig v1.4.0:2086-2099 ... The installer writes nothing.")` (Vendor shape: wezterm row `:300-305`, dated + "The installer writes nothing."), `sibling_regions=(GHOSTTY,)`, `bind_created_path=True`.

**Plan body** (`_kitty_plan` `:160-196`): early `refusal` on `clear_all_shortcuts` (`:162-165`) -> Ghostty refuses on a user `keybind = clear`; `clear_binding(row, platform_os)` (`:124-129`) returns `"cmd+k"`/`"ctrl+shift+k"` and `row.clear`; render `\x0c` literally as `keybind = ctrl+shift+k=text:\x0c` and map `cmd+k`->`super+k`; macOS note naming the displaced default (`:178-183` shape): `"ghostty: cmd+k now sends Ctrl+L; it was clear_screen."`.

**Import additions** (`:15-49`): GHOSTTY, GHOSTTY_CREATED, GHOSTTY_KEYS, `ghostty_config_path`, scan fn, `validate_ghostty`. `apply/pending/strip` are generic (`:322-467`); no change. Pin `assert set(TERMINAL_KEYS)` tests gain `"ghostty"`.

---

### `installer/terminal_shell.py` (service, file-I/O)

**Analog:** `_sync_alacritty` (`:483-507`) with `commit_region` and its own created marker.

**Core pattern** (`:483-507`):
```python
def _sync_alacritty(home, environ, zsh_path, *, write):
    path = alacritty_config_path(home, environ)
    try:
        before = read_settings(path)
        text = _snapshot_text(before)
        document, outside = _user_document(text)
        body, warnings = _shell_plan(document, zsh_path)
        warnings.extend(_keys_plan(document, outside).conflicts)
        updated = _replace_owned_region(text, ALACRITTY, body)
        drifted = commit_region(path, before, text, updated, validate=validate_toml,
            write=write, created_marker=_created_marker(home, environ), home=home)
    except OSError as exc:
        return False, False, (f"alacritty: {_first_line(exc)}",)
    return body is not None, drifted, tuple(warnings)
```
Ghostty variant: path from `ghostty_config_path(platform.os, home, environ)`; body `f"command = {shlex.join((zsh_path, '-l'))}"` (the kitty line `:713` uses `shlex.join((zsh_path, '-l'))`); `placement=Placement.TOP`; `validate=validate_ghostty`; `bind_path=True`; `created_marker` = `xdg_data_home/tools-installer/terminal-ghostty-created` (shared with the keys row, so whichever writer creates the file records it). A user `command` outside the regions (any loaded file) -> `ghostty: partial: you already set command`; a `config-file =` -> extra `partial:` line that included files were not checked. Do NOT copy kitty's `_write_if_changed` style (`:715`), it records no created marker (RESEARCH anti-pattern).

**Sync branch to copy** (`:756-765`):
```python
if _safe_executable(lookup("alacritty")) is not None:
    has_shell, shell_drifted, shell_warnings = _sync_alacritty(home, environ, zsh_path, write=write)
    if has_shell:
        configured.append("alacritty")
        paths.append(("alacritty", alacritty_config_path(home, environ)))
    if shell_drifted:
        drifted.append("alacritty")
    warnings.extend(shell_warnings)
```
(Linux-only: `sync_terminal_shells` already returns early on macOS, `:664-665`.)

**Revert line to copy** (`:627-632`): `_strip_alacritty_region(path, ALACRITTY)` in try/except `OSError` -> `warnings.append(f"alacritty: {_first_line(exc)}")`; use `strip_region(ghostty_path, GHOSTTY)` and `reverted.append("ghostty")`. Update the `:615` and class docstring (`:145`) target lists.

---

### `installer/version_status.py` (config, event-driven)

**Analog:** itself, `_TERMINAL_ROWS` (`:735-741`):
```python
_TERMINAL_ROWS: dict[str, tuple[str, str]] = {
    "kitty": ("kitty", "Kitty"),
    ...
    "alacritty": ("alacritty", "Alacritty"),
    "herdr": ("herdr", "herdr"),
}
```
Add `"ghostty": ("ghostty", "Ghostty")`. Consumed at `:1563,1589-1598` (drift -> "point Ghostty at zsh"). Keys pending is already generic.

---

### `scripts/container-e2e-verify.sh` (script, batch)

**Analog:** `cmd_herdr_keys` (`:2913-2938`).
```bash
cmd_herdr_keys() {
  local failed=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --keep-image) LANDING_KEEP_IMAGE=1 ;;
      *) die "unknown herdr-keys option: $1" ;;
    esac
    shift
  done
  LANDING_CONTAINER_NAME="tools-installer-e2e-herdr-keys-$$"
  CONTAINER_NAME="$LANDING_CONTAINER_NAME"
  IMAGE="$LANDING_IMAGE"
  DISTRO=fedora
  LANDING_DRIVER_MODULE=tests.e2e_herdr_keys_driver
  PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-herdr-keys"
  LANDING_TRANSCRIPT="$PHASE_DIR/herdr-keys-transcript.log"
  trap landing_teardown EXIT
  ensure_phase_dir
  : >"$LANDING_TRANSCRIPT"
  landing_note_image
  landing_bootstrap
  landing_step install-herdr install-herdr || failed=1
  ...
  return "$failed"
}
```
Clone as `cmd_ghostty` (container `tools-installer-e2e-ghostty-$$`, module `tests.e2e_ghostty_driver`, `.e2e-artifacts/container-ghostty/`). Differences (RESEARCH Pattern 4): `start_container` (`:220`, `ct run -d --init --name ... "$IMAGE" sleep infinity`) needs an optional run-args variable for `--device /dev/fuse` (the `nested` target passes it at `:1957`), never `--privileged`; extra root step `dnf install -y zsh fuse fuse3` and `touch /run/ostree-booted`; verbs `install`, `sync`, `regions`, `remove`; second pass with `APPIMAGE_EXTRACT_AND_RUN=1`. Register in `main` dispatch (`:2960-2975`: `herdr-keys) cmd_herdr_keys "$@" ;;`) and in the `usage` text (`:90-135`, the herdr-keys paragraph is the model, ends with the TRACER verdict list).

---

### `tests/e2e_ghostty_driver.py` (test driver, request-response)

**Analog:** `tests/e2e_herdr_keys_driver.py`.

**Imports** (`:17-30`): `from tests.e2e_landing_driver import Failed, first_line, in_container, install_one, tool_by_id, verdict`.

**Verb install + dispatch + guards** (`:129-132, 245-274`):
```python
def _install_herdr() -> list[str]:
    install_one(tool_by_id("herdr"), "TRACER_HERDR_INSTALL_FAILED")
    return ["TRACER_HERDR_INSTALL_OK"]

_HANDLERS = {"install-herdr": _install_herdr, "keys": _keys}
def accepts(args): return len(args) == 1 and args[0] in _HANDLERS
def main(argv=None) -> int:
    ...
    if not in_container():
        print("ERROR the herdr keys driver runs only inside the disposable container")
        return 2
    try: lines = _HANDLERS[args[0]]()
    except Failed as failed: print(verdict(failed.prefix, first_line(failed.detail))); return 1
    ...
    return 1 if any("_FAILED" in line or "_UNPROVEN" in line for line in lines) else 0
```
**Pure verdict function** (`herdr_keys_verdict`, `:88-106`): a `_OK` line, `_FAILED detail=...`, `_UNPROVEN` when the claim cannot be shown (a FUSE pass that fell back prints `_UNPROVEN`, RESEARCH Pattern 4). Never run `+show-config`/`+list-keybinds` before the installer wrote a config (Pitfall 3).

---

### `tests/test_container_e2e_ghostty.py` (test, request-response)

**Analog:** `tests/test_container_e2e_herdr_keys.py` (copy the helper block, `:1-95`).

**Harness** (`:30-32, 51-54, 60-82, 85-109`): `_CT_STUB = "ct() { printf 'ct %s\\n' \"$*\" >> \"$CALLS\"; return 0; }"`, `_function(name)` regex extraction of a bash function, `_script(*names, variables=, stubs=)`, `_run(script, scratch)` with `env={"PATH": "/usr/bin:/bin", "HOME": ..., "CALLS": ..., "LANG": "C"}`, `_LIFECYCLE_FUNCTIONS` tuple including `"cmd_herdr_keys"` -> `"cmd_ghostty"`. Assert: verb registered in `main`, steps in order, `ct run` carries `--device /dev/fuse` and no `--privileged`, `/run/ostree-booted` written, teardown removes only its own container and a pulled image, no prune/reset. Pure verdict tests mirror `test_herdr_keys_verdict_*` (`:130-145`).

---

### `tests/test_registry.py` (test, transform)

**Analog:** `test_wezterm_appimage_covers_bazzite_where_kitty_cannot` (`:1632-1657`): platforms `Platform(os="arch", arch="amd64", immutable=False, has_brew=True)`, `bazzite = Platform(os="fedora", arch="amd64", immutable=True, ...)`, `macos`; `assert [m.kind for m in resolve_methods(tool, plat)] == [...]`; then `method.params[...]` assertions. Ghostty: arch amd64/arm64 -> `["pacman"]`; debian and bazzite amd64 -> `["tarball"]` x86_64 URL; fedora arm64 -> aarch64 tarball; macos -> `["cask"]`; sha256 lowercase 64-hex; `note` contains "community build".
Pin list to edit (RESEARCH Registry Touch List): `_POST_15_3_HUMAN_TOOLS` (`:278-282`), audience `"human": 28`->29 (`:300-304`), `len(tools) == 86`->87 (`:1214`), tier `"user": 49`->50 (`:1266-1270`), post_install declarers (`:1370-1378`), owner probes `"ghostty": ("pacman",)` (`:2271-2276`), `test_pinned_methods_render_their_upstream_asset_names` (`:2019`).

---

### `tests/test_model.py` (test, transform)

**Analog:** the existing `strip`/allowed-key tests (`test_shipped_registry_uses_only_allowed_method_keys`, `:1397-1410`) and fixture registries written to `tmp_path` and loaded with `load_tools`, asserting `pytest.raises(ValueError, match=...)`. Add: raw+strip, raw+archive, empty/multiline/`[`-bearing `note`, unsafe `desktop` id.

---

### `tests/test_terminal_keys.py` (test, CRUD)

**Analog:** kitty goldens and helpers.

**Golden through the public route** (`:398-410`):
```python
def test_kitty_golden_linux_created_file() -> None:
    result = run_post_install(_kitty(), _LINUX)
    assert result.lines == (_KITTY_SUMMARY, "...note...", ...)
    assert _kitty_config().read_bytes() == _KITTY_LINUX.encode()
    marker = _state_dir() / "terminal-kitty-created-path"
    assert marker.read_text() == f"{_kitty_config()}\n"
```
macOS variant (`:413-424`): `Platform(os="macos", arch="arm64", immutable=False, has_brew=True, os_version="14.0")`. Never-writes regression (`:427-429`): `"macos-option-as-alt" not in GOLDEN_LINUX + GOLDEN_MACOS`. User-binding partial (`:432-439`): seed file with `keybind = ctrl+shift+k=reset`, assert `"ghostty: partial: you already bind ctrl+shift+k" in result.lines`. Resolver cases (`:442-453`): `ghostty_config_path("fedora"/"macos", tmp_path, env)` over the four macOS cases plus empty files. Chord normalizer (`:456-461`). Region-on-top (`:464`). Drift (`:1256-1362`): pending only without a record, reconfigure restores, second reconfigure is a no-op. Strip/created-file (`:495-519`, wezterm `:956-973`). Gains `"ghostty"` in the two set pins (`:250`, `:287`). Marker format in goldens: `# >>> tools-installer terminal-shell ghostty-keys >>>` (`marker()` `:172`).

---

### `tests/test_terminal_shell.py` (test, CRUD)

**Analog:** alacritty block (`:1161-1236`): helpers `_alacritty_tool`, `_alacritty_toml`, `_alacritty_record`, `_sync_alacritty(write=, lookup=)` (calls `sync_terminal_shells(home=Path.home(), environ=dict(os.environ), platform=_platform(), lookup=..., write=...)`), `_remove_alacritty` (calls `app_module._after_removal(tool, bundles=(), bin_dir=..., myshellrc_path=..., extra_policies=(), platform_os="fedora")`), and `test_alacritty_install_writes_both_regions_and_removal_strips_them` (install -> keys only, sync -> shell region, idempotent bytes, removal restores user content and drops the record). For ghostty: assert the region sits on top (`Placement.TOP`), a user `command` in the same and in the legacy file gives `partial`, `config-file` gives `partial`, the `_revert_terminal_shells` path strips the `ghostty` region.

---

### `tests/test_download.py` (test, file-I/O)

**Analog:** `ChecksumMismatch` tests (`:1038`, `:1146`), `test_verified_raw_copies_from_temp_into_bin` (`:1187`), `test_failed_raw_copy_leaves_no_staged_sibling` (`:396`). Add: mismatch places nothing (no binary, no menu files), extraction argv through a stub runner that pre-creates `workdir/AppDir/<id>.desktop|.png`, leaves in `artifact_paths`, user `.desktop` kept with a note.

---

### `.claude/skills/tool-onboarding/SKILL.md` (doc, closed table)

**Analog:** kitty row (`:209-218`). Seven cells: `` `ghostty` `` | config file (path resolver description) | `written: the zsh terminal sync sets command on Linux` | `vendor`-or-`n/a` word navigation (macOS esc:b/esc:f defaults; no Linux Alt rows) | `written: super+k (macOS) and ctrl+shift+k (Linux) send Ctrl+L ...` (must start `written`, enforced by `test_table_cells_follow_the_terminal_keys_table`) | `vendor: ...` same-directory | reload. Each rule cell starts with one status word (`vendor|written|planned (phase N)|n/a|unverified`); ASCII only.

---

### `tests/test_tool_onboarding_skill.py` (test, transform)

**Analog:** `test_table_matches_the_registry` (`:642-645`) and `test_table_cells_follow_the_terminal_keys_table` (`:603-630`); both fail until the ghostty row and `TERMINAL_KEYS["ghostty"]` land in the same commit. Fixture-based drift tests (`:653-700`) need no change.

---

## Shared Patterns

### Owned region + created-file proof
**Source:** `installer/terminal_regions.py:176-227` (`replace_owned_region`), `:553-592` (`commit_region`, `strip_region`).
**Apply to:** `_sync_ghostty`, the keys row, revert/strip. Same resolver for all four callers, or the strip misses the file the sync wrote.
```python
region = f"{begin}\n{body}\n{end}\n"
if placement is Placement.TOP: return f"{region}{content}"
```

### Partial / conflict reporting
**Source:** `kitty_maps` `terminal_regions.py:421-425`, `_shell_plan` `terminal_shell.py:466-480`.
**Apply to:** Ghostty scans. Line shape `"<terminal>: partial: you already ..."`; `version_status.py` reads it by the `partial:` prefix.

### Error handling in a sync
**Source:** `_sync_alacritty` `terminal_shell.py:505-506`: `except OSError as exc: return False, False, (f"alacritty: {_first_line(exc)}",)`; refusals raise `TerminalShellError("... nothing written")` from `validate_*`.

### Generic keys routes (no per-terminal code)
**Source:** `terminal_keys.py:322-467` (`apply_terminal_keys`, `terminal_keys_pending`, `strip_terminal_keys`) and `app._after_removal` (`app.py:630-636`, `TERMINAL_KEYS.get(tool.id)`). Strip iterates `(*row.sibling_regions, row.ownership.region)` (`:450`).

### Test isolation
**Source:** `.claude/testing.md`, `tests/conftest.py:133-171`: `tmp_path`/`monkeypatch` HOME, no fixed paths, offline; container targets proven by stubbed-`ct` host tests only; real container runs are orchestrator-only.

### Tracked-analog and gates
All excerpts are from tracked source. AGENTS.md: hooks are the gate; run only the touched tests (`uv run pytest <files> --no-cov -q`); `make validate` and `make test` once per plan; never `make run/fix/doctor/dev-setup` on the host.

## No Analog Found

| File / piece | Role | Data Flow | Reason |
|---|---|---|---|
| AppImage `--appimage-extract PATTERN` step inside `install_download` | service | file-I/O | No existing download method runs the downloaded asset; closest is `cargo_distrobox._stage` (render + `.new` swap) for everything after the extraction. Use `ctx.runner(["env", f"--chdir={workdir}", f"TMPDIR={workdir}", asset, "--appimage-extract", name])` (RESEARCH Pattern 3; `env --chdir` assumption A2). |
| Two-or-four-file load-order scan (`ghostty_default_files`) | utility | transform | `scan_kitty` follows `include` from one file; no scanner merges several default files per OS. Compose `read_capped` + region-strip per file as in `scan_kitty:321-323`. |
| `TMPDIR`-scoped smoke (`smoke_binary` with env) | utility | file-I/O | `executors.py:86-108` takes no env; Pitfall 4 needs an `env`/`tmpdir` argument (small additive change, not an analog gap in the table above). |
| `--device /dev/fuse` run args in the container start | script | batch | `start_container` has no extra-args hook; the `nested` target (`:1957`) is the only place passing `--device`. |

## Metadata

**Analog search scope:** `installer/`, `tests/`, `scripts/`, `.claude/skills/tool-onboarding/`, `.planning/phases/30-onboard-ghostty/`
**Files scanned:** about 22 read in part; RESEARCH.md and CONTEXT.md read in full
**Pattern extraction date:** 2026-11-20
