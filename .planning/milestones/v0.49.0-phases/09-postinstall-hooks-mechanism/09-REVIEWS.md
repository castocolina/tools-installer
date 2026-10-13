# Phase 9 Plan Reviews (Cross-AI Convergence)

## Cycle 1 (codex-sol-high)

**Scope:** `09-01-PLAN.md`, `09-02-PLAN.md` (pre-execution plan review)

**HIGH 1** — The proposed field does not satisfy the required registry contract:
`Tool.postinstall` as a closed hook name conflicts with REQ-postinstall-field's
inline-command/`postinstall_script` requirement (ROADMAP SC#1); the dispatcher receives
only `(name, runner)`, not the successful `Method`, so the "method-aware" claim is false,
conflicting with REQ-postinstall-execution-timing.
Required revision: implement the declared inline/script field shapes at a Method-aware
boundary, or formally revise the requirement; pass the successful Method (or equivalent
context) to the postinstall executor.

**HIGH 2** — Host detection explicitly violates the critical `is_installed` requirement:
the plan uses `shutil.which(tool_id)` directly instead of `installer.status.is_installed`
(mandated by 09-RESEARCH.md lines 62-68), which also covers `detect_path` and app bundles.
Required revision: give the hook access to real catalog `Tool` objects and call
`is_installed(tool)` for each host; test the `is_installed` seam.

**HIGH 3** — A postinstall exception can still turn a completed install into FAILED:
`run_postinstall` is inserted inside the engine's existing install-method `try` block
(which catches `CommandError`/`ExecutorError`/`VersionError` around the whole success
branch), and the plan explicitly refuses defensive containment outside individual hooks.
Required revision: isolate postinstall execution from the install-method exception ladder;
add an engine test where `run_postinstall` itself raises, asserting the result stays
`INSTALLED`, a distinct warning is populated, and no fallback method executes.

**HIGH 4** — Tier-3 can pass without proving the MCP filesystem effect: asserts only
captured argv + exit code (never inspects resulting Claude/Cursor config files); `<verify>`
is an unconditional `echo` (not a real automated gate); `logging_runner` uses raw
`subprocess.run(..., check=True)` instead of this project's `run_command`/`CommandError`
seam, so the described `postinstall_warning` retry path "cannot work as described."
Required revision: make the real container command the automated verifier, use
`run_command` rather than raw `subprocess.run`, assert actual MCP config-file entries in
the throwaway filesystem, add a second zero-host case proving no Claude config is created.

**MEDIUM 1** — The 16-case matrix only asserts `"auto"` absence, not full expected argv
per subset (order, exclusions, `cursor-agent`->`cursor` mapping).

**LOW 2** — Malformed `postinstall` values (non-string, empty) are rejected by the parser
but untested in the same commit.

**Confirmed correct:** the `["codegraph","install","--target",csv,"--location","global",
"--yes"]` construction never uses `--target auto`; the `cursor-agent`->`cursor` mapping is
present; the zero-host branch skips the runner; D-01 is implemented simply (not
over-engineered); both plans have `cross_ai: true`; core same-commit test coverage exists
(gaps are about contract completeness, not total absence).

`CYCLE_SUMMARY: current_high=4 current_actionable=2`

**Disposition:** All 4 HIGH + MEDIUM 1 + LOW 2 fixed directly in `09-01-PLAN.md`/
`09-02-PLAN.md` per Rule 10 (no re-spawn of gsd-planner):
- HIGH 1: `run_postinstall`/hooks now receive the successful `Method`
  (`PostinstallHook = Callable[[Method, Runner, Mapping[str, Tool]], str | None]`);
  `design_decisions` now explicitly reconciles REQ-postinstall-field's literal
  inline/script wording against the closed-dispatch-name shape chosen, recorded as a
  deliberate, documented interpretation (also captured as a Key Decision row in
  09-02 Task 2).
- HIGH 2: hook host-presence check switched from bare `shutil.which(tool_id)` to
  `installer.status.is_installed(tool)`, with the four host `Tool` objects threaded
  through a new `tools: Mapping[str, Tool]` parameter on `install_tool`/`run_postinstall`,
  populated by `run_wizard`'s already-loaded catalog.
- HIGH 3: postinstall dispatch moved to its own dedicated `try/except Exception` at the
  call site, positioned after the method's own success/exception handling has already
  concluded — never sharing the method ladder's `except CommandError | ExecutorError |
  VersionError` block. New behavior/test: `run_postinstall` itself raising is proven to
  leave `status == INSTALLED` with a populated `postinstall_warning` and dispatch no
  fallback method.
- HIGH 4: Tier-3's `<verify>` now re-execs a scoped assertion inside the same container
  reading the fake `$HOME/.claude.json`/cursor MCP config path(s) for the real
  `mcpServers.codegraph` entry; `logging_runner` now wraps `installer.run.run_command`
  (raising `CommandError`, not raw `subprocess.CalledProcessError`); a second all-hosts-
  absent case is added proving no Claude config file is created at all.
- MEDIUM 1: the 16-subset matrix test now asserts full expected argv (or no call) for
  every subset, not merely `"auto"`'s absence.
- LOW 2: same-commit tests added for empty-string and non-string `postinstall` values.

Proceeding to cycle 2.

## Cycle 2 (codex-sol-high)

**Scope:** `09-01-PLAN.md`, `09-02-PLAN.md` as revised by cycle 1's fixes.

**HIGH — The registry contract remains unsatisfied.** 09-01-PLAN.md admits a hook name is
neither the required inline command nor `postinstall_script`, and cycle-1's fix only
reconciled this in plan prose — it never revised `.planning/REQUIREMENTS.md` (REQ-
postinstall-field) or `.planning/ROADMAP.md` (Phase 9 SC#1), the actual normative
documents. Required revision: implement one of the two originally-declared shapes, or
formally amend both normative files.

**HIGH — The new `tools` parameter never reaches the production path.** Cycle-1's PART E
fix targeted a nonexistent direct `install_tool` call inside `run_wizard`; `installer/
app.py::run_wizard` actually delegates through `installer/session.py::run_installs`,
whose `Install` Protocol and all three call sites (initial, mismatch-retry, mismatch-
fallback) omitted `tools` entirely. Required revision: thread a full-catalog mapping
through `run_installs`, its `Install` Protocol, and every invocation, with production-path
tests.

**HIGH — The claimed exception isolation is structurally false.** Cycle-1's PART C fix
placed its dedicated postinstall `try/except` textually after `_perform`'s call, but still
inside the SAME outer `try` the method ladder's own `except (CommandError, ExecutorError,
VersionError)` clause guards — the real `installer/engine.py` shows the success branch's
`return InstallOutcome(...)` sits inside that one `try` body. Required revision: a coherent
`try/except/else` structure where postinstall executes in the `else` clause, a true sibling
of `try`/`except`, never nested inside the try body — with a corroborating test.

**HIGH — A fresh download does not guarantee the `codegraph` command is resolvable.**
`installer/download.py::install_download` places a fresh binary into `~/.local/bin`; PATH
wiring for that directory is a separate, later step (`configure_path`/`make fix`); the hook
invoked bare `"codegraph"`, which only worked in the Tier-3 container recipe because that
recipe happened to pre-export `~/.local/bin`, masking the defect. Required revision: invoke
the freshly-installed executable through its resolved absolute path (the same `bin_dir`
`install_download` itself used), with a test whose initial PATH excludes `~/.local/bin`.

**HIGH — The Tier-3 verifier remains capable of false success and does not cover its
stated cases.** The `<verify>` piped the whole container run into `tail` without
`pipefail`, so a failing assertion inside the container would not fail the gate; the
zero-host run and its exact-argv assertion were never actually written into the
recipe; and the zero-host case's prescribed `CAPTURED == []` is impossible in practice
because the download executor uses the SAME `logging_runner`, so `CAPTURED` also holds its
own curl/tar/chmod calls. Required revision: one failure-propagating gate running both
containers, filtering captured calls to only `codegraph install` invocations, and
asserting exact argv, warning, and no-host filesystem behavior for both cases.

**MEDIUM — The two-host Tier-3 case verifies only Claude's config.** It plants both Claude
and Cursor host stubs but only inspects `~/.claude.json`. Required revision: also locate
and assert Cursor's own real global MCP config entry.

`CYCLE_SUMMARY: current_high=5 current_actionable=1`

**Disposition:** All 5 HIGH + the MEDIUM fixed directly in `09-01-PLAN.md`/`09-02-PLAN.md`
and the normative docs, per Rule 10:
- HIGH (registry contract): `.planning/REQUIREMENTS.md`'s REQ-postinstall-field and
  `.planning/ROADMAP.md`'s Phase 9 SC#1 both AMENDED in this same commit to name a closed
  dispatch-hook NAME as a third accepted `postinstall` field shape, with the rationale
  recorded directly in the requirement text — a genuine normative-document change, not a
  plan-level workaround.
- HIGH (`tools` threading): corrected to go through the REAL chain — a new `catalog:
  Mapping[str, Tool] | None = None` parameter on `run_installs` (named distinctly from its
  existing `tools: list[Tool]` parameter), threaded into all three `install(...)` call
  sites and the `Install` Protocol; `run_wizard` builds `{t.id: t for t in tools}` from its
  own already-held catalog list and passes it as `catalog=` into its one `run_installs`
  call. New tests in `tests/test_session.py` and `tests/test_app.py`.
- HIGH (exception isolation): `install_tool`'s method-ladder loop restructured to
  `try/except/else` — `_perform(method, ctx)` is the only statement in the `try` body; the
  postinstall dispatch and success `return` now live in a new `else` clause, a true sibling
  of `try`/`except`, never nested inside it.
- HIGH (PATH resolution): `_codegraph_mcp_register` now computes `bin_dir(method.params.
  get("bin_dir")) / "codegraph"` (the SAME path `install_download` itself wrote to, via the
  now-load-bearing `method` parameter) and invokes that resolved absolute path, never a
  bare `"codegraph"` relying on the current process's PATH.
- HIGH (Tier-3 false success): the container recipe rewritten as a single `tier3-verify.sh`
  script with `set -euo pipefail` at both the outer-script and inner-container level (no
  more unchecked `| tail`), running BOTH the host-present and host-absent cases, filtering
  captured calls to `c[0] == expected_bin and c[1] == "install"` (since the download
  executor shares the same logging runner), and asserting exact argv / warning / filesystem
  state for both cases in one failure-propagating gate.
- MEDIUM (Cursor config): the `present` case's Python block now asserts Cursor's own real
  global MCP config entry alongside Claude's, with a note to confirm the exact config path
  live during execution (e.g. via `codegraph install --print-config cursor` or reading
  `cursor.js` directly) rather than guessing an unverified path at plan-authoring time.

Proceeding to cycle 3.

## Cycle 3 (codex-sol-high) — FINAL (max_cycles=3 reached)

**Scope:** `09-01-PLAN.md`, `09-02-PLAN.md` as revised by cycles 1 and 2.

**HIGH — `bin_dir(method.params.get("bin_dir"))` is not type-safe.** `method.params` is
`dict[str, object]`, so `.get("bin_dir")` yields `object | None`, which
`installer.locations.bin_dir(declared: str | None)` cannot accept under strict Pyright,
unlike `install_download`'s own `_opt_str` normalization. Required revision: normalize the
value (`isinstance(value, str) and value else None`) before calling `bin_dir`, exactly as
`_opt_str` does.

**HIGH — Unconditionally passing `tools=catalog` to all three `Install` call sites breaks
every existing test double.** Ten pre-existing fake `install`/`fake_install` functions
across `tests/test_app.py` and `tests/test_session.py` do not declare a `tools` parameter;
calling them with an unexpected `tools=` keyword raises `TypeError`. `installer/session.py`
and `tests/test_session.py` were also missing from Task 1's own `<files>` tag (present only
in the frontmatter `files_modified` list). Required revision: explicitly migrate every
existing fake to accept the new keyword, and add `installer/session.py`/
`tests/test_session.py` to Task 1's `<files>` tag.

**MEDIUM — The Tier-3 recipe exports `~/.local/bin` (installing `uv`) before claiming PATH
independence, which could mask a defective bare-name invocation.** Required revision:
invoke `uv` (if needed at all) by absolute path and keep `~/.local/bin` off PATH for the
whole container lifetime — or, since this recipe never actually needs `uv`, drop the `uv`
install entirely.

**MEDIUM — Cursor verification was left as a comment, not an executable check.** The
`present` case's evidence inspected only `~/.claude.json`; Cursor's own MCP registration
was never actually verified. Required revision: locate and assert the real Cursor MCP
config entry with a `CURSOR_MCP_ENTRY[present]` marker, required in acceptance criteria.

`CYCLE_SUMMARY: current_high=2 current_actionable=2`

**Disposition (max_cycles=3 reached — fixed directly, proceeding to execution per Rule 10,
no cycle 4 dispatched):**
- HIGH (bin_dir type safety): `_codegraph_mcp_register` now normalizes
  `method.params.get("bin_dir")` inline (`isinstance(value, str) and value else None`)
  before calling `bin_dir`, mirroring `installer/download.py::_opt_str` without importing
  that module's private helper; added `test_codegraph_hook_ignores_a_non_string_bin_dir_
  param`.
- HIGH (test-double breakage): Task 1's `<files>` tag now includes `installer/session.py`
  and `tests/test_session.py`; PART C.5 now explicitly instructs migrating all ten existing
  `Install`-shaped fakes across both test files to accept `tools: Mapping[str, Tool] | None
  = None` — the same precedent this codebase already used when `checksum_policy` was added
  to the same Protocol.
- MEDIUM (PATH masking): removed the vestigial `uv` install entirely from the Tier-3 recipe
  (it was copied from 08-04-PLAN.md's uv-tool-executor test but is unused here — codegraph's
  `github_release` method never touches `uv`); `~/.local/bin` is never on PATH anywhere in
  the container's lifetime now.
- MEDIUM (Cursor verification): the `present` case now searches the container's home
  directory tree for any JSON file (other than `~/.claude.json`) containing a
  `mcpServers.codegraph` entry, asserts at least one match, and prints
  `CURSOR_MCP_ENTRY[present]` — real found evidence rather than an assumed path or a
  comment-only TODO.

Cap reached (3/3 cycles) — proceeding to execution regardless of any further residual
findings, per ONESHOT-RULES Rule 10.
