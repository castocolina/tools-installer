# Phase 28: Shared terminal-keys mechanism - Pattern Map

**Mapped:** 2026-11-20
**Files analyzed:** 12 (3 new, 9 modified)
**Analogs found:** 12 / 12 (the moved code is its own analog; table, dataclass and test idioms come from tracked files)

All analog paths below were checked tracked (`git ls-files`: `installer/schedules.py`, `installer/terminal_shell.py`, `tests/test_terminal_shell.py` confirmed; the rest are ordinary `installer/` and `tests/` files).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/terminal_regions.py` (new) | utility (lower module) | file-I/O, transform | `installer/terminal_shell.py` lines 90-133, 509-536, 604-668 (code moves verbatim) | exact (move) |
| `installer/terminal_keys.py` (new) | service + closed table | file-I/O, CRUD | `installer/terminal_shell.py:470-482, 583-601, 671-757` (bodies) + `installer/schedules.py:43-52` (row shape) | exact (move) + role-match (table) |
| `installer/terminal_shell.py` (mod) | service | file-I/O | itself; imports lower module under current local names | exact |
| `installer/post_install.py` (mod, `_tune_terminal`, `_apply_terminal_tuning`, `apply_install_tuning` branch) | dispatch | request-response | `_tune_agent` / `_tune_shell_init` siblings in same file | exact |
| `installer/version_status.py` (mod, `_tuning_fact`, `_terminal_tuning_fact`) | dispatch | request-response (read-only fact) | `_shell_init_tuning_fact` same file (:788-800) | exact |
| `installer/app.py` (mod, `_after_removal`) | dispatch | event-driven (removal) | the `tool.id in SHELL_INIT_TOOLS` branch right below it | exact |
| `installer/tweaks.py` (mod: `SHELL_INIT_TOOLS`, `BUNDLES`) | config / bundle | transform | `_shell_init("neovim", ...)` + `_NVIM_EDITOR_BODY` (:111-113, 188-194) | exact |
| `installer/registry.toml` (mod, zsh entry :562) | config | n/a | alacritty `post_install = [...]` line (:3164); any shell-init tool's `post_install = ["source_shell_init"]` | exact |
| `tests/test_terminal_keys.py` (new) | test | integration (scratch HOME) | `tests/test_terminal_shell.py` Alacritty block :1153-1344, 1520-1660; `tests/test_post_install.py:1114-1141`; `tests/test_version_status.py:7054-7095` | role-match |
| `tests/test_terminal_shell.py` (mod, 4 import lines) | test | n/a | itself (`:1220,1254,1323,1648`) | exact |
| `tests/test_tweaks.py` (mod :48 id list; new zsh widget tests) | test | transform | `test_bundles_have_stable_ids_and_order` :48; `test_each_shell_init_body_parses_in_zsh` :373 | exact |
| `tests/test_tool_onboarding_skill.py` (mod :378-381 source path) | test | n/a | itself | exact |

## Pattern Assignments

### `installer/terminal_regions.py` (utility, file-I/O) -- NEW lower module

**Analog:** `installer/terminal_shell.py` (move verbatim; make names public so pyright strict does not raise `reportPrivateUsage`; `terminal_shell` imports them back under the old local names with `as`, e.g. `from installer.terminal_regions import replace_owned_region as _replace_owned_region`).

**Moves (exact current locations):** `TerminalShellError` and `_marker`/`_replace_owned_region` (:98-133, region begin/end write `f"{begin}\n{body}\n{end}\n"`, errors `malformed {terminal} ownership region`), `_xdg_config_home`/`_xdg_data_home`, `_first_line` (:509-510), `_snapshot_text` (:519-525), `_imports_files` + `_table` (:539-550), `alacritty_config_path` (:486-497), `_strip_alacritty_region` (:659-668), `_commit_alacritty` (:604-630), `_drop_created_config` (:742-757).

**Core pattern to copy: compare-before-commit write with created marker** (`terminal_shell.py:604-630`):
```python
def _commit_alacritty(path, before, text, updated, *, write, created_marker, home) -> bool:
    if updated == text:
        return False
    try:
        tomllib.loads(updated)          # becomes row.validate(updated) in the generic form
    except tomllib.TOMLDecodeError as exc:
        raise TerminalShellError(f"the edit would not re-parse ({exc}); nothing written") from exc
    if write:
        created_dirs = missing_dirs(path, home) if before is None else ()
        write_if_unchanged(path, before, updated)
        if before is None:
            created_marker.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(created_marker, "\n".join(("created", *created_dirs)) + "\n")
    return True
```
Generalization notes: the `tomllib` call becomes the row's `validate` (Alacritty: the same re-parse, same message text, pinned by `test_alacritty_region_that_would_not_reparse_is_refused` :1292); the `"alacritty:"` prefix in `_drop_created_config` warnings (:756) and `strip` warnings (:735) must stay `alacritty:` for Alacritty (tests assert it), so take it from the row or tool name.

**Guard (D-12):** keep `_read_text`, `_write_if_changed`, `_shell_plan`, `_sync_alacritty` in `terminal_shell`; tests monkeypatch `terminal_shell.read_settings`, `atomic_write_text`, `ensure_zshrc_template` (`tests/test_terminal_shell.py:184-196,1276-1283`). `terminal_shell` still uses all three itself, so imports stay and ruff F401 stays quiet.

**Import header to model on** (`terminal_shell.py:9-37`): `from installer.agent_settings import (...)`, `from installer.atomic import FileSnapshot, atomic_write_text, read_capped`. The new module imports only `installer.agent_settings` and `installer.atomic`, never `terminal_shell`/`terminal_keys` (no cycle).

---

### `installer/terminal_keys.py` (service + closed table, file-I/O) -- NEW

**Analog 1 (row shape):** `installer/schedules.py:43-52` and `:71`
```python
@dataclass(frozen=True)
class Schedule:
    id: str
    label: str
    kind: JobKind
    target: str | None
    default_interval: int
    default_start: str

SCHEDULES: Final[tuple[Schedule, ...]] = ( ... )
```
Also `installer/agent_settings.py:732` `TUNING_GROUPS: Final[dict[str, tuple[str, ...]]]` and `KeyKind = Literal[...]` at `:610-612`. No dataclass-union alias exists in `installer/` yet (RESEARCH confirmed), so `OwnedRegion`, `Vendor | Writes | NotApplicable` are new; plain `@dataclass(frozen=True)` variants narrowed by `isinstance`. Required fields (`same_directory`) precede defaulted ones (`sibling_regions`, `clear`).

**Analog 2 (bodies to copy with row fields substituted):** `terminal_shell.py:470-482, 583-601, 671-723, 726-739`.

Constants, the Alacritty plan and the exact conflict literal (moves into `terminal_keys.py` per RESEARCH Open Question 5 option (a), so the `partial: you already bind` literal sits next to `_KEY_BINDINGS`):
```python
KEYS_PENDING = "install tuning not applied"
_KEYS_RECORD = "terminal-tuning-alacritty"          # becomes f"terminal-tuning-{tool_id}" from the dict key (D-01)
_CREATED_RECORD = "terminal-alacritty-created"      # becomes row.created_record
_KEY_BINDINGS = (
    ("Left", "Alt", 'chars = "\\u001bb"'),
    ("Right", "Alt", 'chars = "\\u001bf"'),
    ("K", "Control|Shift", 'action = "ClearHistory"'),   # bytes unchanged until phase 29
)
...
conflicts.append(f"alacritty: partial: you already bind {mods.replace('|', '+')}+{key}")
```
Apply (D-06 changes only the early return at :679-680):
```python
record = _keys_record(home, environ)
if skip_recorded and record.exists():
    return (), None              # D-06: read; return () only if region absent or already current
path = alacritty_config_path(home, environ)
try:
    before = read_settings(path)
    text = _snapshot_text(before)
    plan = _keys_plan(*_user_document(text))
    if plan.refusal is not None:
        return (), plan.refusal
    updated = _replace_owned_region(text, ALACRITTY_KEYS, plan.body)
    _commit_alacritty(path, before, text, updated, write=True,
                      created_marker=_created_marker(home, environ), home=home)
    record.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(record, "written\n")
except OSError as exc:
    return (), _first_line(exc)
```
Pending (:710-723; D-06 narrows "None" to record-or-region-present-and-current):
```python
if _keys_record(home, environ).exists():
    return None
try:
    text = _snapshot_text(read_settings(alacritty_config_path(home, environ)))
    if _replace_owned_region(text, ALACRITTY_KEYS, None) != text:
        return None
    plan = _keys_plan(*_user_document(text))
except OSError as exc:
    return _first_line(exc)
return plan.refusal or KEYS_PENDING
```
Strip (:726-739) strips the row region plus `sibling_regions` (`("alacritty",)`), keeps the record on any warning, then `_drop_created_config`.

`_user_document` today strips both `ALACRITTY` and `ALACRITTY_KEYS` before parsing (:528-536); generically it strips the row region plus `sibling_regions`.

**Success line (row `summary`)**, `terminal_shell.py:702-706`: `"Alacritty keys: Alt+Left and Alt+Right move by word, Control+Shift+K clears history."` Added only when `plan.body is not None`; `(*added, *plan.conflicts)` is the return.

**Runtime backstop (RESEARCH Pitfall 4):** `apply_install_tuning` has no try/except (`post_install.py:426-449`), so use `TERMINAL_KEYS.get(tool.id)` and return `PostInstallOutput((f"{tool.name} keys not changed: no keys row declared for {tool.id}",), refused=...)` on `None`.

**Test hooks:** `dataclasses.fields(KeysRow)` check that `same_directory` has `default is MISSING and default_factory is MISSING` (D-14); `resolve_clear` pure function for the `cmd+k`/`ctrl+shift+k` -> `\x0c` fixture (D-13); `Platform.os` Linux values are distro names, so "not macos" is the Linux test (`tweaks._LINUX` at `tweaks.py:85`).

---

### `installer/post_install.py` (dispatch, request-response)

**Analog:** the exact current sites (these are the sites that branch on the Alacritty id/function today).

Import (:72): `from installer.terminal_shell import apply_alacritty_keys` becomes `from installer.terminal_keys import TERMINAL_KEYS, apply_terminal_keys`.

Current dispatch (:385-396):
```python
def _tune_terminal(*, skip_recorded: bool) -> PostInstallOutput:
    """Alacritty's keybindings region (24 D-23). A refusal is one line and `refused`."""
    lines, refused = apply_alacritty_keys(Path.home(), os.environ, skip_recorded=skip_recorded)
    if refused is not None:
        return PostInstallOutput((f"Alacritty keys not changed: {refused}",), refused=refused)
    return PostInstallOutput(lines)


def _apply_terminal_tuning(tool: Tool, platform: Platform) -> PostInstallOutput:
    del tool, platform
    return _tune_terminal(skip_recorded=False)  # install and reinstall rewrite
```
Target: `_tune_terminal(tool, platform, *, skip_recorded)` looks up `TERMINAL_KEYS.get(tool.id)`, passes `platform.os`, refusal text `f"{tool.name} keys not changed: {refused}"` (D-02; `tests/test_post_install.py:1129-1141` pins `"Alacritty keys not changed: you already define keyboard.bindings inline"`, `tool.name` is `"Alacritty"` at `registry.toml:3154`). `_apply_terminal_tuning` stops `del tool, platform`.

Reconfigure branch (:445-448), the second site that must pass `tool, platform`:
```python
elif name == "apply_terminal_tuning":
    produced = _tune_terminal(skip_recorded=skip_recorded)
    lines.extend(produced.lines)
    refused = refused or produced.refused
```
Table entry stays: `"apply_terminal_tuning": _apply_terminal_tuning,` (:420). Sibling analog for the signature style: `_tune_agent(tool, platform, skip_recorded=...)` (`_apply_agent_tuning` at :380-382).

---

### `installer/version_status.py` (dispatch, read-only fact)

Import (:111): `from installer.terminal_shell import KEYS_PENDING, TerminalShellResult, alacritty_keys_pending`; `TerminalShellResult` stays from `terminal_shell`, `KEYS_PENDING`/pending move to `terminal_keys`. D-04: `version_status` keeps its own `TUNING_PENDING` (same text, :773).

Current sites (:777-785 and :821-834):
```python
    if present and "apply_terminal_tuning" in tool.post_install:
        return _terminal_tuning_fact()
...
def _terminal_tuning_fact() -> _ConfigFacts:
    try:
        reason = alacritty_keys_pending(Path.home(), os.environ)
    except Exception as exc:  # a read-only secondary fact must never fail the pass
        return _ConfigFacts(unchecked=(f"keybindings not checked: {exc}",))
    if reason is None:
        return _NO_FACTS
    if reason == KEYS_PENDING:
        return _ConfigFacts((TUNING_PENDING,), (TUNING_STEP,))
    return _ConfigFacts((reason,))
```
Target: `_terminal_tuning_fact(tool, platform)`; `row = TERMINAL_KEYS.get(tool.id)`; `None` -> `_NO_FACTS` (no row, no fact); keep the broad `except Exception` and the three-way mapping. The `_shell_init_tuning_fact(tool, platform)` neighbour (:788-800) is the signature analog. `_TERMINAL_ROWS["alacritty"]` (:738) is shell-sync drift: leave it, reviewer reads that one hit of `rg alacritty`.

---

### `installer/app.py` (dispatch, event-driven removal)

Import (:83): `from installer.terminal_shell import strip_alacritty` becomes `from installer.terminal_keys import TERMINAL_KEYS, strip_terminal_keys`.

Current site (`_after_removal`, :630-631):
```python
if tool.id == "alacritty":  # both owned regions and the record go with the tool (24 D-23)
    parts.append(SweepResult(warnings=strip_alacritty(Path.home(), os.environ)))
```
Target: `row = TERMINAL_KEYS.get(tool.id)`; `if row is not None: parts.append(SweepResult(warnings=strip_terminal_keys(row, tool.id, platform_os, Path.home(), os.environ)))`. `platform_os` is already a parameter of `_after_removal` (used at :633-639). Both removal routes (`app.py:1068`, `:1269`) call it; tests call `app_module._after_removal(...)` (`tests/test_terminal_shell.py:1143`, `tests/test_app.py:5643`) with a `# pyright: ignore[reportPrivateUsage]`, so the signature must not change.

---

### `installer/terminal_shell.py` (modified, keys code removed)

Remove `apply_alacritty_keys`, `alacritty_keys_pending`, `strip_alacritty` and the constants that move; keep `_sync_alacritty` (:633-656) which now imports the Alacritty keys plan from `terminal_keys` to report conflicts:
```python
document, outside = _user_document(text)
body, warnings = _shell_plan(document, zsh_path)
warnings.extend(_keys_plan(document, outside).conflicts)   # asserted: tests/test_terminal_shell.py:1230-1234
```
`_revert_terminal_shells` (:879) calls `_strip_alacritty_region(path, ALACRITTY)`, which now comes from `terminal_regions`. Konsole/kitty/WezTerm/herdr bodies (e.g. :359-461) stay byte-unchanged (SPEC R5). No re-export of the moved public names (D-12).

---

### `installer/tweaks.py` (bundle, transform)

**Analog:** neovim bundle (`:111-113`, `:188-194`) and `_shell_init` (:116-121); guarded shape from `_guarded_init` (:93-99).

Edit points: `SHELL_INIT_TOOLS` (:90) and `BUNDLES`. Keep both in the same relative position: `test_shell_init_bundles_sit_after_apt_upgrade_in_tool_order` (`tests/test_tweaks.py:354-356`) requires `BUNDLES[start:start+len(SHELL_INIT_TOOLS)] == SHELL_INIT_TOOLS` right after `apt-upgrade`; RESEARCH verified zsh as the FIRST entry of both passes. First body line must be `if command -v zsh >/dev/null; then` (`tests/test_tweaks.py:365-372`) and the body must pass `bash -n` and `zsh -n`. Backslashes need a raw string (comment at `tweaks.py:51-54`; `_COUNTDOWN_BODY` style).

Bundle declaration to copy:
```python
_shell_init(
    "neovim",
    "sets EDITOR and VISUAL to nvim when your shell files set neither",
    _NVIM_EDITOR_BODY,
    yields_to=("EDITOR", "VISUAL"),
),
```
Body (RESEARCH, probed in zsh 5.9.2 under a pty; function name is Claude's discretion):
```sh
if command -v zsh >/dev/null; then
  if [ -n "$ZSH_VERSION" ]; then
    tools_installer_clear_all() {
      print -n '\033[H\033[2J'
      zle .reset-prompt
      zle -R
      print -n '\033[3J'
    }
    zle -N tools_installer_clear_all
    for keymap in emacs viins vicmd; do bindkey -M $keymap '^L' tools_installer_clear_all; done
  fi
fi
```

---

### `installer/registry.toml` (zsh entry :562)

Add `post_install = ["source_shell_init"]` to the zsh `[[tool]]` block (it currently has no `post_install`). Analog is the alacritty line at :3164 (`post_install = ["apply_terminal_tuning"]`) placed after `config_paths`. `source_shell_init` is already in `POST_INSTALL_ACTIONS` (`model.py:130-141`). RESEARCH verified the only existing test it breaks is `tests/test_tweaks.py:48`.

---

### `tests/test_terminal_keys.py` (test, integration scratch HOME) -- NEW

**Analogs (copy idioms from):**

1. Golden bytes through public routes only (D-10): `tests/test_post_install.py:1114-1126`
```python
def test_apply_terminal_tuning_writes_the_keys_once_and_reconfigure_respects_a_deletion() -> None:
    tool = next(t for t in load_tools(REGISTRY) if t.id == "alacritty")
    config = Path.home() / ".config" / "alacritty" / "alacritty.toml"
    assert run_post_install(tool, _mutable()).warning is None
    assert len(tomllib.loads(config.read_text())["keyboard"]["bindings"]) == 3
    config.write_text(re.sub(r"# >>>.*?<<<[^\n]*\n", "", config.read_text(), flags=re.DOTALL))
    assert apply_install_tuning(tool, _mutable(), skip_recorded=True).lines == ()
```
`_mutable()` is `Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)` (:52-53). Autouse scratch-HOME fixture in `tests/conftest.py` makes `Path.home()` safe.

2. Strip and created-file deletion through `app_module._after_removal(...)  # pyright: ignore[reportPrivateUsage]`: `tests/test_terminal_shell.py:1143` and `:1540-1560` (`_remove_alacritty(tmp_path)` helper; created marker deletion asserts `not _alacritty_toml().parent.exists()`). Pitfall 3: the created marker holds absolute scratch-HOME paths, so assert the first line `created` and that dirs are under `Path.home()`; pin the config bytes and `written\n` exactly. Golden config bytes are in 28-CONTEXT D-10 (or RESEARCH lines 102-105).

3. D-06 pair of tests (name both explicitly, RESEARCH Pitfall 6): user-deleted after a record is theirs (`tests/test_version_status.py:7054-7064`):
```python
def test_alacritty_keys_region_removed_by_hand_is_the_users_choice(tmp_path):
    tool = _alacritty_shipped()
    run_post_install(tool, _LINUX)
    config = _alacritty_file()
    config.write_text(_strip_region(config.read_text(), "alacritty-keys"))
    state = _tuning_state(tmp_path, tool)
    assert state.health is Health.OK and state.unconfigured == ()
```
and untouched host reads `≈` (:7067-7080, `test_untuned_alacritty_reads_apply_install_tuning`). New drift test: write a region with an old body, `terminal_keys_pending` -> `KEYS_PENDING`, `apply_install_tuning(skip_recorded=True)` rewrites it, a second call is a no-op.

4. Completeness helper over id sets (D-11), fixture registry from `tests/test_model.py:1981` style `_write`/`_tool_block` helpers, then `load_tools(path)`:
```python
def missing_rows(tools, table):
    return {t.id for t in tools if "apply_terminal_tuning" in t.post_install} - set(table)
```
Also the reverse and `"konsole" not in TERMINAL_KEYS`.

5. Closed-table test idiom: `tests/test_tweaks.py:48` style (`assert [b.id for b in BUNDLES] == [...]`).

6. Constraint: the file must contain NO string literal ending in `.md` or starting with `.planning` (docstrings count), or `tests/test_docs_only.py` `LEDGER` (:209-301) fails.

7. Existing refusal-text pin: `tests/test_post_install.py:1129-1141` must pass unedited.

---

### zsh widget tests (in `tests/test_tweaks.py`, or `tests/test_terminal_keys.py`) (test, transform)

**Analog:** `tests/test_tweaks.py:365-395`
```python
@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is not on PATH; zsh -n not run")
@pytest.mark.parametrize("tool", SHELL_INIT_TOOLS)
def test_each_shell_init_body_parses_in_zsh(tool: str) -> None:
    bundle = shell_init_bundle(tool)
    assert bundle is not None
    result = subprocess.run(["zsh", "-n", "-c", bundle.body], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
```
Always-on layer (no zsh): render `tweak_block(shell_init_bundle("zsh"))` and assert literal `\033[H` and `\033[2J` appear before `\033[3J`, the `ZSH_VERSION` guard, `emacs viins vicmd`; apply then strip on a scratch `~/.myshellrc` is byte-identical (use `write_tweak` / `strip_tweak_block`, `tweaks.py:271-290`). `tests/test_shellrc.py:708` is the second `skipif(shutil.which("zsh") is None)` precedent. Optional pty probe: stdlib `pty`/`select`, bounded loop, `os.waitpid`/kill in `finally` (`.claude/testing.md` xdist rules). CI installs no zsh, so the pty test must not be the only layer.

---

### Existing test edits (explicit D-12 exceptions)

- `tests/test_terminal_shell.py:1220,1254,1323,1648`: `from installer.terminal_shell import apply_alacritty_keys` becomes `from installer.terminal_keys import ...` (name and call shape per final public signature; keep the tests' assertions unchanged).
- `tests/test_tool_onboarding_skill.py:378-381` (found by research): reads `installer/terminal_shell.py` source and asserts `"alacritty: partial: you already bind" in shell_source`; repoint the path to `terminal_keys.py` (where the literal lands). Path edit only.
- `tests/test_tweaks.py:48`: add `"zsh"` to the pinned `BUNDLES` id list at the position matching the `BUNDLES` edit.
- Leave `tests/test_tool_onboarding_skill.py:225` (`"planned for phase 28"`) and SKILL.md for phase 29 (A4).

## Shared Patterns

### Closed, code-owned names; no command text from the registry
**Source:** `installer/model.py:130-141` (`POST_INSTALL_ACTIONS`), `.claude/architecture.md` (Phase 9, Registry-authoring)
**Apply to:** `terminal_keys.py` row table, zsh `post_install` entry. The registry selects an action NAME; behavior lives in a `Final[dict]` in code.

### Compare-before-commit file write and read-only secondary facts
**Source:** `installer/terminal_shell.py:604-630` (commit), `installer/version_status.py:821-834` (broad `except Exception` for read-only facts)
**Apply to:** every apply/pending/strip path in `terminal_keys.py` and the `version_status` fact.
```python
except Exception as exc:  # a read-only secondary fact must never fail the pass
    return _ConfigFacts(unchecked=(f"keybindings not checked: {exc}",))
```

### Marker block ownership (`# >>> tools-installer ... >>>`)
**Source:** `terminal_shell.py:98-133` (`_marker`, `_replace_owned_region`), `tweaks.py:199-203` (shell-init markers)
**Apply to:** all owned regions; never write outside a marker, a user-deleted recorded block stays the user's.

### Install tuning lifecycle (`≈ apply install tuning`, reconfigure, revert with tool)
**Source:** `.claude/architecture.md` Phase 3 / onboarding tree; `post_install.py:280-305` (`_tune_shell_init`), `version_status.py:788-800`, `app.py:633-637`
**Apply to:** the zsh widget bundle and the keys rows. Not a Policies row (`compose.py:713` filters `SHELL_INIT_TOOLS`).

### Typing and gates
**Source:** `pyproject.toml` pyright strict, vulture `min_confidence = 80`, `fail_under = 90`; `.claude/architecture.md` rule 5 (no orphan helpers; keep `Writes` a one-field dataclass justified by its fixture test)
**Apply to:** both new modules; public names only across modules.

### Scratch-HOME tests, no host mutation
**Source:** `tests/conftest.py` autouse HOME; AGENTS.md "Never mutate the developer's host"
**Apply to:** all new tests; run targeted pytest only (`uv run pytest tests/test_terminal_keys.py ...`), never `make run/fix/doctor/uninstall/dev-setup`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| typed union aliases (`OwnedRegion`, `Vendor | Writes | NotApplicable`) in `terminal_keys.py` | model | n/a | No `X = A | B` dataclass union exists in `installer/`; use `Schedule`'s frozen-dataclass style plus `isinstance` narrowing (`agent_settings.KeyKind` Literal is the nearest closed-value idiom) |
| pty probe test for the zsh widget | test | streaming | No existing pty-based test; model on the RESEARCH probe script and the `skipif` idiom |

## Metadata

**Analog search scope:** `installer/terminal_shell.py`, `post_install.py`, `version_status.py`, `app.py`, `tweaks.py`, `schedules.py`, `registry.toml`; `tests/test_terminal_shell.py`, `test_post_install.py`, `test_version_status.py`, `test_tweaks.py`, `test_tool_onboarding_skill.py`
**Files scanned:** ~12 read in part; line numbers verified this session against the working tree
**Pattern extraction date:** 2026-11-20
