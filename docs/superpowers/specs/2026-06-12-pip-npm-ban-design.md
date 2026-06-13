# pip/npm ban (environment policy) — Design

## Why

The installer should do more than drop binaries on disk: like the predecessor
project (uzkit), it should optionally apply **environment policy** that steers
the user toward the managed toolchain. The first such policy bans the
unmanaged package installers — `pip` / `pip3` (→ `uv`) and `npm` (→ `pnpm`) —
so that the user, an agent, a script, or another installer that reaches for
them gets a hard, explanatory failure instead of silently polluting the system
Python or global node_modules.

This is uzkit's `tools/installer/shell.py` feature, ported and adapted to this
repo's conventions (`~/.myshellrc` managed block, link modes, doctor/fix split,
`make uninstall`, 100% coverage / shellcheck gates).

## Scope decisions (locked)

- **Full-command ban**, not subcommand-level. The shim fails for *any*
  `pip` / `pip3` / `npm` invocation. Rationale: far less code, no argument
  parsing, no exec-passthrough, and harder to evade by accident than a
  subcommand filter. Cost is daily friction (`pip --version`, `npm run` also
  fail) — accepted.
- **Two layers** (uzkit parity): universal PATH shims + interactive-shell
  aliases.
- **Opt-in, default off.** Editing how pip/npm behave is invasive, so it is
  never enabled silently — not even under `--yes` unless `--guard` is passed.
- **Both activation paths:** a standalone `make guard` / `make unguard`
  (+ `--guard` / `--unguard` flags) *and* an optional prompt at the end of the
  wizard.
- **Doctor reports guard health** (read-only).

### Banned commands and sanctioned replacements

| Banned  | Use instead                       |
| ------- | --------------------------------- |
| `npm`   | `pnpm` (e.g. `pnpm add -g <pkg>`) |
| `pip`   | `uv` (`uv pip install` / `uv add`)|
| `pip3`  | `uv` (`uv pip install` / `uv add`)|

### Known limitation (documented, not fixed)

Neither layer is hermetic: `python -m pip install` bypasses the `pip` shim, and
a real `pip`/`npm` that resolves earlier on PATH wins over the shim. The shims
close the common doors and the doctor warns about PATH ordering; airtight
sandboxing is out of scope. Same honesty as uzkit.

## Architecture

A new pure module `installer/guards.py` holds all logic and file operations;
orchestration (which rc files, console output, prompts) stays in `app.py` /
`setup.py`, mirroring how `shellrc.py` / `rcclean.py` relate to `app.py`.

### `installer/guards.py` (pure, 100% coverage)

```python
BANNED = {
    "npm":  "pnpm (pnpm add -g <pkg>)",
    "pip":  "uv (uv pip install / uv add)",
    "pip3": "uv (uv pip install / uv add)",
}
SHIM_SENTINEL = "# tools-installer-ban-shim"
EXIT_CODE = 127
BAN_BEGIN = "# >>> tools-installer ban >>>"
BAN_END   = "# <<< tools-installer ban <<<"
```

**Layer 1 — PATH shims**
- `shim_script(name) -> str` — a 4-line POSIX `sh` script: shebang, sentinel
  comment, `echo "...banned... use <hint>" >&2`, `exit 127`.
- `install_shims(home) -> dict[str, str]` — writes `~/.local/bin/{npm,pip,pip3}`
  (mode 0o755). Idempotent; **never overwrites a non-shim binary** (sentinel
  check) — reports `created` / `refreshed` / `skipped (real binary here)`.
- `remove_shims(home) -> dict[str, str]` — removes only files carrying the
  sentinel; reports `removed` / `absent`.

**Layer 2 — interactive aliases**
- `ban_alias_block() -> str` — marker-delimited block of
  `alias <name>='echo "... banned — use <hint>." >&2; false'`, built between
  `BAN_BEGIN` / `BAN_END`.
- `write_ban_aliases(rc_path)` / `remove_ban_aliases(rc_path)` — reuse
  `shellrc.apply_block` / a strip helper for idempotent block management. The
  *caller* (app/setup) chooses the rc files from the active `link_mode`
  (`_rc_paths_for_mode`), exactly as the PATH block does.

**Doctor helper**
- `guard_path_warning(home, env, which) -> str | None` — returns a warning when
  `~/.local/bin` is not on PATH, or when a real `npm`/`pip`/`pip3` (non-sentinel)
  resolves *before* the shim dir. `env` and `which` are injected for testing.
- `guard_status(home) -> ...` — whether each shim is installed (ours) for the
  doctor report.

### `installer/app.py`

- `run_guard(remove: bool, link_mode, rc_paths, console, *, confirm) -> int` —
  install or remove both layers, print actions via `render.py`, surface
  `guard_path_warning`, remind to `hash -r` / open a new shell. Preview +
  confirm before writing (consistent with `clean_rc_duplicates`).
- `run_uninstall` also removes shims + alias block (they are our artifacts),
  within its existing preview/confirm.
- `run_doctor` gains a read-only guard-status section (installed? PATH order ok?).

### `installer/render.py`

- `render_guard(actions, warning) -> ...` — rich rendering of the per-file
  actions and any PATH warning, matching the existing `render_*` style.

### `setup.py` (thin IO boundary)

- New `--guard` / `--unguard` argparse flags → `app.run_guard(...)`.
- Optional wizard prompt after install / verify-and-clean: "Enable the pip/npm
  ban?" — opt-in, default off. Honors `--yes` only when `--guard` is explicit;
  unattended runs never enable it implicitly.
- `_rc_paths_for_mode` reused to target the alias block.

### `Makefile`

- `guard:   uv run setup.py --guard`
- `unguard: uv run setup.py --unguard`

## Data flow

```
make guard ─► setup.py --guard ─► app.run_guard(remove=False)
                                     ├─ guards.install_shims(home)        (layer 1)
                                     ├─ guards.write_ban_aliases(rc)×N    (layer 2, per link_mode)
                                     ├─ render.render_guard(actions, warn)
                                     └─ guards.guard_path_warning(...)    (advice)

make unguard ─► setup.py --unguard ─► app.run_guard(remove=True)
                                        ├─ guards.remove_shims(home)
                                        └─ guards.remove_ban_aliases(rc)×N

make doctor ─► run_doctor ─► (existing PATH audit) + guards.guard_status / guard_path_warning

make uninstall ─► run_uninstall ─► (existing) + remove_shims + remove_ban_aliases
```

## Error handling

- Shim install on a real binary → skip + report, never clobber.
- Unreadable shim file (`OSError`/`UnicodeDecodeError`) during sentinel check →
  treat as "not ours", skip.
- Missing rc file on removal → reported `absent`, not an error.
- Guard actions are previewed and confirmed before any write (unless `--yes`).

## Testing

`tests/test_guards.py` at 100% coverage:
- shim script content + `sh -n <generated shim>` proves it is valid POSIX sh.
- sentinel detection; install/remove idempotency; never-overwrite-real-binary.
- alias block build/strip idempotency (via `apply_block`).
- `guard_path_warning` across: shim dir absent from PATH, real tool before
  shim, healthy order → `None`. `env` + `which` injected.
- `guard_status` reporting.

Orchestration tested where the logic lives (`app.py`); `setup.py` stays the
untested-by-design IO boundary, same as today. `make validate` (shellcheck
included) + `make test` green on the committed tree.

## Out of scope

- Hermetic sandboxing / catching `python -m pip`.
- Banning anything beyond npm/pip/pip3 (e.g. `yarn`, `easy_install`) — add to
  `BANNED` later if needed; the mechanism is data-driven.
- Env-var policies (`PIP_REQUIRE_VIRTUALENV`, `.npmrc`) — rejected; they don't
  express "always block".
