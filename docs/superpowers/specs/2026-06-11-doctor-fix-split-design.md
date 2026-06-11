# Doctor/Fix Split + Existing-Dirs Filter — Design

Date: 2026-06-11
Status: approved (sections approved in terminal; section 1 via visual companion)

## Problem (user-reported, reproduced on macOS)

`make doctor` today:

1. Prompts "How should PATH be wired…" before auditing — a write-question in a
   read flow.
2. Reports the `bin_dir` of every platform-applicable method, including tools
   that are not installed: `/opt/homebrew/bin` (no brew), `~/.bun/bin` (no bun)
   show up as "missing from PATH" and "does not exist".
3. Prints "Something went wrong. Troubleshooting: <url>" — alarmist for what is
   mostly "tools you haven't installed yet".
4. Then writes those nonexistent dirs into `~/.myshellrc` anyway (fix=True),
   with the confusing message order: problems → alarm → "PATH configured".

Root cause: `shellrc.collect_bin_dirs` is platform-aware but not
installation-aware, and `run_doctor` couples diagnosis with fixing.

## Decisions (user-approved)

1. **Filter rule**: a declared method `bin_dir` is managed only when the
   directory **exists on disk**. The default `~/.local/bin` is always managed.
   Rationale: disk presence = the tool is actually there, with no PATH
   chicken-and-egg (right after installing brew, `brew` is not on PATH yet but
   `/opt/homebrew/bin` exists — installed-ness probing would never wire it).
2. **Doctor is diagnosis only**; fixing moves to a new explicit action:
   `make fix` / `--fix`.
3. Named `fix` (not doctor-fix, not wizard-reuse). Doctor's pointer on
   problems: `Run 'make fix' to wire PATH into your shell.`

## Design

### 1. Existence filter at the single source

`shellrc.collect_bin_dirs(tools, platform, default, exists=Path.is_dir)`:
keeps `default` unconditionally; includes a method's declared `bin_dir` only
when `exists(resolved_dir)` is true. `exists` is injectable for tests (the
codebase's established seam style). All three consumers inherit the filter:

- `app.configure_path` (writes `~/.myshellrc` / split rc blocks) — gains an
  `exists: Callable[[Path], bool] = Path.is_dir` keyword it forwards.
- `app.run_doctor` audit — forwards its existing `exists` parameter, so the
  audit and the collection judge existence identically.
- `setup._verify_and_clean`'s managed set for `clean_rc_duplicates` — default.

Consequence: `audit_path`'s "does not exist" (broken) bucket can no longer be
populated by never-installed tools; it remains reachable only for the default
bin dir (`~/.local/bin` missing on a fresh machine is a real, actionable
finding) — and disappears entirely once dirs are filtered and present. The
DoctorReport shape is unchanged.

### 2. Read-only doctor, explicit fix

- `app.run_doctor(tools, console, *, platform, default_bin_dir, path_value,
  exists, hint) -> DoctorReport` — audits and renders only. The `fix`,
  `myshellrc_path`, `rc_paths`, and `link_mode` parameters are removed; the
  write path is `configure_path`, which already exists as a standalone
  function.
- `cli.Options` gains `fix: bool = False`; new argparse flag `--fix`
  ("wire PATH into your shell rc files, then exit"). Flags are handled in
  order: `--doctor` → `--fix` → `--uninstall` (first match wins, matching the
  existing doctor-before-uninstall precedence).
- `setup.py`:
  - `_run_doctor`: no link-mode prompt, no writes. Calls the slim `run_doctor`
    with `hint="Run 'make fix' to wire PATH into your shell."`. Exits 0 always
    (a report, not an error path).
  - new `_run_fix`: resolves link-mode (flag → prompt → centralized, exactly
    the current `_resolve_link_mode`), calls `configure_path`, exits 0. Its
    closing message is the existing configure_path print: "PATH configured in
    ~/.myshellrc (restart your shell or source it)." **No re-audit**: the
    process PATH cannot change until the shell restarts, so a post-fix audit
    would re-show "missing" and recreate the confusion this design removes.
- `Makefile`: `doctor` target unchanged (`--doctor`); new `fix` target running
  `uv run setup.py --fix`; help text updated.

### 3. Calm, context-correct messaging

`render.render_doctor(report, console, hint: str)`:

- healthy → `PATH looks healthy: all bin dirs present, on PATH, and unique.`
  (unchanged), hint not printed.
- problems → the finding lines (unchanged format), then the caller's `hint`
  line. The `render_troubleshooting` call is removed from `render_doctor`;
  the troubleshooting URL remains for install failures (wizard summary path),
  which is untouched.

Hints by caller:

- standalone `--doctor`: `Run 'make fix' to wire PATH into your shell.`
- wizard post-install verify (`_verify_and_clean`, which runs after
  `configure_path` already wired everything):
  `Restart your shell (or: source ~/.myshellrc) to apply.`

### Behavior on the reporting machine (acceptance sketch)

With brew/bun absent and `~/Library/pnpm` present but not on PATH:

```
$ make doctor
  missing from PATH: /Users/ramon/Library/pnpm
Run 'make fix' to wire PATH into your shell.

$ make fix
? How should PATH be wired into your shells? …
PATH configured in /Users/ramon/.myshellrc (restart your shell or source it).

$ make doctor        # after restarting the shell
PATH looks healthy: all bin dirs present, on PATH, and unique.
```

No `/opt/homebrew/bin`, no `~/.bun/bin`, no "Something went wrong".

## Error handling

- No new failure modes: `collect_bin_dirs` existence probing uses the injected
  callable (real default `Path.is_dir`, exception-free); `--fix` keeps
  configure_path's existing write errors (propagate as today).
- `--doctor` with problems still exits 0 (explicit decision: it is a report;
  scripting against it can parse output later if ever needed).

## Testing (100% gate unchanged)

- `test_shellrc.py`: collect filters nonexistent declared dirs (fake exists);
  default dir kept even when `exists` says no; order/dedupe preserved.
- `test_app.py`: slim `run_doctor` renders hint on problems and not on
  healthy; `configure_path` writes only existing dirs (fake exists);
  doctor-no-longer-writes (no myshellrc side effect).
- `test_render.py`: `render_doctor` hint rendering; troubleshooting absent.
- `test_cli.py`: `--fix` flag parsing; precedence doctor > fix > uninstall.
- setup.py remains the untested IO boundary; smoke via `--help`.

## Out of scope

- Tool dependency modeling, priority/audience UI, AI-rationale descriptions
  (separate upcoming feature from uzkit-parity feedback).
- Doctor exit codes for scripting; stale-PATH-entry (previously managed, now
  removed dir) detection; TROUBLESHOOTING.md rewrite.
