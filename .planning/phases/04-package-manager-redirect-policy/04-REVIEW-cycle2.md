---
phase: 04-package-manager-redirect-policy
reviewed: 2026-09-05T16:59:07Z
depth: deep
cycle: 2
files_reviewed: 24
files_reviewed_list:
  - installer/app.py
  - installer/executors.py
  - installer/guards.py
  - installer/guidance.py
  - installer/pnpm_globals.py
  - installer/policy.py
  - installer/registry.toml
  - installer/render.py
  - installer/run.py
  - installer/ui_common.py
  - installer/wizard_app.py
  - setup.py
  - tests/test_app.py
  - tests/test_executors.py
  - tests/test_guards.py
  - tests/test_guidance.py
  - tests/test_node_install_e2e.py
  - tests/test_pnpm_globals.py
  - tests/test_policies_e2e.py
  - tests/test_policy.py
  - tests/test_registry.py
  - tests/test_render.py
  - tests/test_ui_common.py
  - tests/test_wizard_app.py
findings:
  critical: 2
  warning: 8
  info: 4
  total: 14
status: issues_found
---

# Phase 4: Code Review Report (cycle 2, post-fix)

**Reviewed:** 2026-09-05T16:59:07Z
**Depth:** deep — cross-file call chains, plus behavioural verification by executing
generated shims under `/bin/sh` and by instrumenting the live Textual app under
`run_test`
**Files Reviewed:** 24
**Status:** issues_found

## Summary

The fix pass is substantially real. Of the 16 findings (4 BLOCKER + 12 WARNING),
**13 are genuinely closed**, verified against source and behaviour rather than
against the fixer's own report. No test was weakened to pass; the suite grew by
~380 lines and the new tests assert the things the old ones missed. `ruff`,
`vulture --min-confidence 80` and the full 1007-test suite are clean.

Verified closed by execution or instrumentation:

- **CR-01 (partially, see BL-01).** `npm i -g --loglevel warn typescript` now
  exits 127 with the ban message instead of running `volta install warn
  typescript`. `npm i -g --registry https://r.example p`, `pnpm add -g --dir /tmp
  typescript` and `pnpm -Cmy-gadget add x` all degrade correctly, and genuine
  boolean-only global installs (`npm i -g typescript`, `install --global`,
  `-gD`, `-g` before the subcommand, multiple packages) still redirect. No
  false-negative was introduced for the common shapes.
- **CR-02 / CR-04.** `audit_node_globals` and the reinstall both derive from
  `pnpm list -g --json` (`pnpm_global_packages`). A catalog entry no longer
  counts as an installation, and `reinstall_argv` replays pnpm's own package
  list, so a hand-installed `vercel`/`typescript` survives the replace. The
  "catalog == installed set" false alarm is gone. (The residual gap the fixer
  flagged — a pnpm self-update that already erased the record is undetectable —
  is an acceptable tradeoff: without that record there is nothing to reinstall
  either, so the feature loses a diagnosis it could never have acted on.)
- **CR-03 (partially, see BL-02).** `_reinstall_globals_worker` is a real
  `@work(thread=True, exclusive=True)`; the only cross-thread contact is
  `post_message(GlobalsReinstalled(...))`, no widget is touched off-loop, and
  `test_doctor_r_runs_the_reinstall_off_the_event_loop` is a genuine regression
  test — it parks the worker on a `threading.Event`, asserts the loop still
  renders "Reinstalling", and asserts a second `r` does not stack. Instrumenting
  the live app confirms the reinstall closure runs on `asyncio_0` while every
  refresh runs on `MainThread`.
- **WR-02 through WR-12** are all present in source and covered: the consent text
  is updated in all three places (`policy.ban_policy.description`,
  `PoliciesScreen._policy_detail["ban"]`, `app.run_guard`'s pre-confirm print);
  `on_globals_reinstalled` calls `_refresh_guidance()` before `_refresh_body()`;
  `guard_redirect_warning` now distinguishes the foreign-binary case from the
  unresolvable-pnpm case and reports a vanished baked target via
  `exec_targets`/`os.access`; `real_binary` retries without the shim dir only
  after our own shim wins the lookup; `executors._path_prefix()` exports
  `shell_path()` into both `sh -c` and `bash -c`; `PnpmUnavailable(OSError)`
  reaches `run_live` with an actionable message; the empty-set `r` press sets
  `globals_note`; `install_global_redirect_shims` writes the block it reports;
  `run_guard` composes `guard_state`'s warning; `ban_body` raises `ValueError`.

What did **not** survive scrutiny:

1. The boolean whitelist that closed CR-01 silently drops options that are not
   cosmetic. `npm i -g --ignore-scripts typescript` still redirects, and volta
   runs `npm install --global` with install scripts enabled — the shim inverts an
   explicit user security decision (BL-01). The same arm re-opens the original
   value-as-package-name hole for `--boolean true|false`.
2. CR-03 is closed for the *install* and re-opened for the *audit*: the Doctor
   screen runs `pnpm list -g --json` synchronously on the Textual event loop on
   every entry, and twice more immediately after each reinstall, with no timeout
   and no interruptible path (BL-02). Verified by instrumenting the live app.
3. `pnpm_global_packages` correctly returns `None` for "unknown", and
   `audit_node_globals` then collapses that `None` into an empty report one call
   later, so the Doctor asserts "0 package(s) in pnpm's global set" and "Nothing
   to reinstall — pnpm manages no globals here" for a state it does not know
   (WR-02 below). `NodeGlobalsReport` has no way to express "unknown", so no
   downstream consumer can recover the distinction.
4. The WR-01 fix traded a false negative for a false positive: the
   volta-install-scripts security note now fires on a machine where volta was
   never found and npm is merely hard-blocked, two lines above the warning that
   says so (WR-04).

## Narrative Findings (AI reviewer)

## Critical Issues

### BL-01: The boolean whitelist silently discards `--ignore-scripts`, and `--boolean true|false` still forwards a value to `volta install` as a package name

**File:** `installer/guards.py:74-94` (`BOOLEAN_LONG_OPTIONS`), `installer/guards.py:197-238` (the generated body)
**Severity:** BLOCKER

**Issue:** `BOOLEAN_LONG_OPTIONS` is the whitelist that makes CR-01's fix sound,
and it is not a list of *cosmetic* options — it contains `--ignore-scripts`,
`--force`, `--offline` and `--prefer-offline`. The rewrite loop drops every
token beginning with `-`, so a whitelisted option is accepted (it does not clear
`known`) and then thrown away. Verified by executing the generated shim:

```
$ npm  i -g --ignore-scripts typescript   -> VOLTA install typescript
$ pnpm i -g --ignore-scripts typescript   -> VOLTA install typescript
```

`volta install <pkg>` runs a real `npm install --global`, which the module's own
guidance (`guidance.py:119-130`, `registry.toml`'s volta entry) documents as
running install scripts unrestricted. So a user who typed the one option that
exists specifically to stop untrusted postinstall code from executing gets it
executed, with no message. That is a silent inversion of a user-supplied security
control, not a lost convenience flag — and it is strictly worse than the
degrade-to-fallback path the whitelist was built to guarantee.

Second instance, same arm. npm's option parser (nopt) accepts an explicit value
for a Boolean option (`--flag true` / `--flag false`). The whitelist consumes the
option but not its value, so the value lands in the package list:

```
$ npm i -g --ignore-scripts false typescript -> VOLTA install false typescript
$ npm i -g --force true typescript           -> VOLTA install true typescript
```

That is CR-01's exact failure mode (an attacker-influenceable name reaching
`volta install`, which then runs ungated install scripts) reached through the
fix rather than around it. The module docstring's claim that "an option this list
is missing degrades to the wrapper's fallback ... Being incomplete is therefore
safe by construction" is true; the claim it does not make — that an option this
list *contains* is safe to drop — is the one the code relies on, and it is false
for four of the fifteen entries.

**Fix:** Keep the whitelist to options whose loss cannot change what gets
installed or how, and treat a following `true`/`false` as consumed:

```python
# Cosmetic or global-install-irrelevant only. --ignore-scripts, --force,
# --offline and --prefer-offline change what the install DOES, and volta has no
# equivalent to forward them to, so they must degrade, not be dropped.
BOOLEAN_LONG_OPTIONS: tuple[str, ...] = (
    "--global", "--save", "--save-dev", "--save-exact", "--save-prod",
    "--save-optional", "--no-save", "--recursive", "--workspace-root",
    "--silent", "--verbose",
)
```

and in the first scan, after the `-g|--global` and long-boolean arms, clear
`known` for the explicit-value form so it degrades rather than guessing:

```sh
    # a boolean given an explicit value: nopt consumes the next token, we cannot
    true|false) known=0 ;;
```

Add executed-shim cases for `--ignore-scripts <pkg>` (must not redirect) and
`--ignore-scripts false <pkg>` (must not redirect) beside the existing
`test_npm_separated_option_value_never_reaches_volta` parametrization at
`tests/test_guards.py:553`.

---

### BL-02: The Doctor screen runs `pnpm list -g --json` synchronously on the Textual event loop, with no timeout

**File:** `setup.py:254-269` (`_node_globals_report`), `installer/wizard_app.py:192-198`, `installer/wizard_app.py:200-245`, `installer/wizard_app.py:306-315`; call chain `DoctorScreen._refresh_guidance` → `pnpm_globals.audit_node_globals` → `pnpm_global_packages` → `run.run_output` → `subprocess.run(..., capture_output=True)`
**Severity:** BLOCKER

**Issue:** CR-03 moved the `pnpm add -g` off the event loop, but the *audit* that
feeds the same screen still runs a subprocess on it. `_node_globals_report` is
the closure `DoctorScreen` calls from `_refresh_guidance`, `_refresh_body`,
`_globals_preview` and `action_reinstall_globals`; on a cold cache it calls
`audit_node_globals(tools)`, which shells out to `pnpm list -g --json`.

Instrumented against the live app (`run_test`, closure records
`threading.current_thread().name`):

```
ON ENTER DOCTOR: ['MainThread', 'MainThread', 'MainThread']
AFTER r:         ['MainThread', 'MainThread', 'REINSTALL@asyncio_0', 'MainThread', 'MainThread']
```

The first entry into Doctor blocks the loop for one `pnpm list -g --json`.
`_reinstall_globals` then sets `cached_globals = None` **from the worker thread**,
so the two `MainThread` calls in `on_globals_reinstalled` re-run the audit — a
second and third blocking subprocess on the event loop, immediately after the
fix that existed to keep subprocesses off it.

Two things make this more than slow: `run_output` passes no `timeout`, and
Textual holds the terminal in raw mode, so Ctrl+C arrives as byte `0x03` on a
queue the blocked loop is not draining rather than as SIGINT. A pnpm that stalls
on store-lock contention therefore hangs the TUI with no recoverable input path.

Related, same closure: `_node_globals_report`'s `if cached_globals is None:
cached_globals = audit(...)` is a check-then-act on a closure cell that the
worker thread writes. It is not reachable today only because the cache is
populated before the worker starts; nothing states or enforces that.

**Fix:** Resolve the report once, off the loop, and hand it to the screen the
same way the reinstall result is handed back:

```python
# DoctorScreen
@work(thread=True, exclusive=True, group="globals")
def _refresh_globals_worker(self) -> None:
    report, error = run_live(self._node_globals)
    self.post_message(GlobalsAudited(report, error))
```

`on_mount`/`enter_view` post the work and render a "checking pnpm's global
set..." placeholder; `on_globals_reinstalled` re-posts it instead of calling
`_refresh_guidance()` directly. Whatever shape is chosen, `run_output` should
also grow a bounded `timeout=` for this call so a wedged pnpm cannot hold the
process. If a synchronous audit must stay, move it to `_build_app` (before
`UnifiedApp` is constructed, where blocking is legal) and drop the
worker-thread cache invalidation in favour of the report arriving on the
`GlobalsReinstalled` message.

---

## Warnings

### WR-01: The `--*=*` arm blanket-accepts every attached long option, so `--registry=<url>` is silently dropped

**File:** `installer/guards.py:205` (`"    --*=*) ;;\n"`)
**Severity:** WARNING

**Issue:** The first case arm accepts *any* `--opt=value` token without clearing
`known`, and the rewrite loop then drops it. The comment justifies this as "the
attached `--opt=value` form, which consumes no following token" — true for argv
parsing, but the arm is a blanket accept, not a whitelist, and it is the one
place where the module's stated "being incomplete is safe by construction"
invariant does not hold. Verified:

```
$ npm i -g --registry=https://npm.internal.corp mypkg -> VOLTA install mypkg
$ npm i -g --prefix=/opt/x mypkg                      -> VOLTA install mypkg
```

`volta install` resolves from the default public registry, so a user pinning an
internal registry for an internal-only package name gets it fetched from
npmjs.com instead — a textbook dependency-confusion setup, silently created by a
tool the user installed to make package management safer. `--prefix=` is dropped
the same way, so the package lands somewhere the user did not ask for.

**Fix:** Split the arm so only whitelisted names are accepted in attached form:

```sh
    --*=*) case "${arg%%=*}" in
             --global|--save|--save-dev|…) ;;
             *) known=0 ;;
           esac ;;
```

### WR-02: `audit_node_globals` collapses "pnpm could not be asked" into "pnpm manages nothing"

**File:** `installer/pnpm_globals.py:146-158`, `installer/pnpm_globals.py:67-80` (`NodeGlobalsReport`), `installer/wizard_app.py:219-227`, `installer/wizard_app.py:84`
**Severity:** WARNING

**Issue:** `pnpm_global_packages` is careful — it returns `None` for unknown, and
its docstring says so explicitly ("None means 'unknown', not 'empty'. A report
built from an unknown set claims nothing"). One call later that care is thrown
away:

```python
packages = managed()
if packages is None:
    return NodeGlobalsReport(entries=(), missing=(), managed=())
```

The returned value is byte-identical to the report for "pnpm manages zero
globals", and `NodeGlobalsReport` has no third state, so nothing downstream can
tell them apart. The Doctor screen then states an unknown as a fact:

- `wizard_app.py:224-227` renders `"0 package(s) in pnpm's global set, 0 of them
  catalog tool(s)."`
- `wizard_app.py:84` answers `r` with `"Nothing to reinstall — pnpm manages no
  globals here."`

The realistic trigger is not "pnpm absent" but "pnpm present and the query
failed" — a non-zero exit, unparseable JSON, a pnpm too old for `--json`. That is
precisely the moment this feature exists for (a pnpm that has just replaced
itself), and it answers "nothing to reinstall". `tests/test_pnpm_globals.py:195`
enshrines the collapse as intended behaviour under the name
`test_audit_claims_nothing_when_pnpm_cannot_be_asked`, while asserting the exact
value that *does* claim something.

**Fix:** Give the report the third state and render it:

```python
@dataclass(frozen=True)
class NodeGlobalsReport:
    entries: tuple[NodeGlobal, ...]
    missing: tuple[str, ...]
    managed: tuple[str, ...]
    known: bool = True   # False when pnpm could not be asked

# audit_node_globals
if packages is None:
    return NodeGlobalsReport(entries=(), missing=(), managed=(), known=False)
```

and in `_refresh_body`, render "pnpm's global set could not be read" instead of
"0 package(s)". The CLI renderer (`render_node_globals`) stays silent either way,
so only the TUI wording changes.

### WR-03: `_UNRESOLVABLE_PREVIEW` is unreachable in production; the real "pnpm not found" case prints "nothing pnpm-managed to reinstall"

**File:** `installer/pnpm_globals.py:200-210`, `setup.py:262-263`
**Severity:** WARNING

**Issue:** `reinstall_preview` returns `_EMPTY_PREVIEW` before it resolves pnpm:

```python
if not packages:
    return _EMPTY_PREVIEW
resolved = resolve_pnpm()
if resolved is None:
    return _UNRESOLVABLE_PREVIEW
```

The only production caller is `setup._globals_preview`, which passes
`_node_globals_report().managed`. When pnpm cannot be resolved, `managed` is `()`
(see WR-02), so the function returns on the first branch and
`_UNRESOLVABLE_PREVIEW` is reached only in a race where pnpm resolved during the
audit and vanished before the render. The user whose pnpm is missing — the whole
audience for that string — is told "nothing pnpm-managed to reinstall" instead.
`test_doctor_screen_renders_unresolvable_pnpm_preview`
(`tests/test_wizard_app.py:1337`) injects the string directly as
`globals_preview`, so it proves the rendering and not the reachability.

**Fix:** Fold into WR-02: once the report carries `known`, have `_globals_preview`
return `_UNRESOLVABLE_PREVIEW` when `not report.known`, and keep `_EMPTY_PREVIEW`
for a genuinely empty known set. Add a test that drives `_globals_preview` from a
`resolve_pnpm=lambda: None` audit rather than injecting the string.

### WR-04: The WR-01 fix trades a false negative for a false positive — the volta security note now fires when npm is merely hard-blocked

**File:** `installer/guidance.py:119-130`, `installer/app.py:322-328`
**Severity:** WARNING

**Issue:** The gate became `status.get("pnpm", False) or status.get("npm", False)`.
`status["pnpm"]` is a precise proxy for "volta resolved at apply time" —
`install_global_redirect_shims` removes the pnpm wrapper whenever volta is
unresolvable (`guards.py:397-402`). `status["npm"]` is not: npm is `True` for both
the redirect body and the hard-block body. So on a machine with no volta the
Doctor now prints, in this order:

```
[ok]   Volta global installs run npm install scripts: A global install through
       volta runs a real `npm install --global`; npm's install scripts are not
       gated the way pnpm gates them.
[warn] … 'npm' is hard-blocked because 'volta' was not resolvable when the policy
       was applied; install volta and re-apply.
```

(reproduced by driving `run_guard` + `guard_state` + `guard_guidance` with
`which=lambda _n: None`). The note describes a routing that provably is not
happening, and it is styled `Severity.OK`, so it reads as a confirmed
configuration rather than a caveat. Same site, second instance: `run_guard`
(`app.py:324-328`) prints "This wraps npm and pnpm so global installs run `volta
install`" before the confirm on a machine where it is about to write two hard
blocks; it could cheaply check `real_binary(VOLTA, …)` first.

**Fix:** Keep the wording layer IO-free but give it the fact it needs. Have
`guard_state` return the volta-routing bit alongside the status dict (it already
reads the shim bodies for `guard_redirect_warning`), and gate on that:

```python
# guards.py
def volta_routing_live(shim_dir: Path) -> bool:
    """True only when a GLOBAL_REDIRECTED name on disk carries the redirect body."""
    return any(
        is_our_shim(shim_dir / name) and REDIRECT_SENTINEL in (shim_dir / name).read_text()
        for name in GLOBAL_REDIRECTED
    )
```

### WR-05: A redirect-degradation message is rendered under the title "PATH order warning" with a PATH-order remedy

**File:** `installer/app.py:209-218` (`guard_state`), `installer/guidance.py:131-141`
**Severity:** WARNING

**Issue:** `guard_state` concatenates `guard_path_warning` and
`guard_redirect_warning` into one string; `guard_guidance` wraps whatever that
string is in a `Guidance(title="PATH order warning", …, next_step="Put the shim
dir ahead of the real binary on PATH, then reopen the shell.")`. On the common
case where the PATH order is fine and only the redirect degraded, the user gets:

```
[warn] PATH order warning: 'npx' is hard-blocked because 'pnpm' was not resolvable
       when the policy was applied; install pnpm and re-apply. 'npm' is
       hard-blocked because 'volta' was not resolvable …
  next: Put the shim dir ahead of the real binary on PATH, then reopen the shell.
```

The title names the wrong problem and the next step is advice that cannot fix it
— on a screen whose whole purpose is "one finding, one exact next step". WR-11's
fix propagated the same composition to the `--guard` CLI path, so the mislabel
now appears in two places instead of one.

**Fix:** Keep the two warnings as separate values through `guard_state` and emit
two `Guidance` items:

```python
def guard_state(...) -> tuple[dict[str, bool], str | None, str | None]:
    return status, path_warning, redirect_warning
```

with `guard_guidance(status, path_warning, redirect_warning)` producing a "PATH
order warning" item and a "Redirect degraded" item whose next step is "install
the named tool, then re-apply the policy". Callers to update: `app.doctor_data`,
`app.run_doctor`, `app.run_guard`, `setup._guard_state`, `wizard_app.DoctorScreen`.

### WR-06: The "replay" drops the version of every global, so the reinstall silently upgrades them all to latest

**File:** `installer/pnpm_globals.py:100-122` (`parse_global_packages`), `installer/pnpm_globals.py:161-174` (`reinstall_argv`)
**Severity:** WARNING

**Issue:** `pnpm list -g --json` reports each dependency as
`{"from": …, "version": "10.9.1"}` — the fixture at
`tests/test_pnpm_globals.py:108-120` includes it. `parse_global_packages` keeps
only the map keys and discards the version, so `reinstall_argv` emits
`pnpm add -g @mermaid-js/mermaid-cli vercel`, which resolves the **latest**
version of every package. The docstrings call this a replay that "puts back
everything it held" (`pnpm_globals.py:163-165`) and the guidance calls it
"reinstall the globals pnpm still tracks" (`guidance.py:167-170`). Neither says
that a pinned `vercel@39.1.1` comes back as whatever is current — and the whole
flow was designed for the user whose globals are already in a bad state, i.e. the
user least able to notice a silent major-version bump across their whole global
set.

**Fix:** Carry the version through and pin it:

```python
def parse_global_packages(raw: str) -> tuple[str, ...] | None:
    ...
    for name, details in cast(dict[str, object], block).items():
        version = details.get("version") if isinstance(details, dict) else None
        names.append(f"{name}@{version}" if isinstance(version, str) and version else name)
```

If pinning is deliberately out of scope, say so where the user consents: the
preview line and `node_globals_guidance`'s next step must state that the replay
installs current versions.

### WR-07: Quitting during a reinstall tears down the UI and then blocks the process with no output

**File:** `installer/wizard_app.py:295-304`, `installer/run.py:33-47`
**Severity:** WARNING

**Issue:** Textual thread workers run on asyncio's default `ThreadPoolExecutor`,
whose threads are non-daemon and joined by `asyncio.run`'s shutdown. Pressing `q`
(or Ctrl+C) mid-reinstall exits the app immediately and then blocks in the
runtime until `pnpm add -g` finishes, with the alternate screen already torn
down, no message, and the child's output discarded by `run_captured`. Measured
with a 4-second stand-in worker:

```
app exited at t=0.27s
asyncio.run returned at t=4.08s
```

For the `@mermaid-js/mermaid-cli` case the docstring cites (Puppeteer/Chromium),
that is minutes of an apparently-hung shell after the user asked to quit — the
same "no spinner and no way to cancel" complaint CR-03 raised, relocated.

**Fix:** Either block the quit while a reinstall is in flight (guard
`action_abort`/`action_hard_abort` on `globals_running` and set a status line
explaining why), or give `run_output` a `timeout=` and print a one-line
"finishing the pnpm reinstall — this can take a few minutes" on the restored
terminal before returning from `UnifiedApp.run()`.

### WR-08: `real_binary`'s reachability change is untested for the two-directory case, and its regression test's name now contradicts what it asserts

**File:** `installer/guards.py:254-280`, `tests/test_guards.py:281-292`
**Severity:** WARNING

**Issue:** The WR-05 fix is correct — the retry now drops `shim_dir` only after
our own shim has actually won — but two seams are unguarded:

1. `test_real_binary_skips_shim_dir` still carries that name while its body was
   rewritten to plant a *sentinel-carrying shim* rather than an arbitrary file.
   The function no longer skips the shim dir; a reader trusting the name will
   re-introduce the exclusion.
2. Nothing covers the shape that made WR-05 a bug in the first place *combined
   with* a second candidate: a real `pnpm` in `shim_dir` and another real `pnpm`
   later on PATH must resolve to the first (PATH order wins), and a shim in
   `shim_dir` plus a real one later must resolve to the second. Only the
   single-directory case (`path_value=str(shim_dir)`) is asserted at
   `tests/test_guards.py:295-310`.

**Fix:** Rename to `test_real_binary_skips_our_own_shim`, and add the
two-directory pair:

```python
def test_real_binary_prefers_a_real_binary_in_the_shim_dir_over_one_later(tmp_path):
    ...  # shim_dir/pnpm is real, other/pnpm is real -> shim_dir wins
def test_real_binary_falls_past_our_shim_to_a_later_real_binary(tmp_path):
    ...  # shim_dir/pnpm carries REDIRECT_SENTINEL, other/pnpm is real -> other wins
```

---

## Info

### IN-01: `.planning/` artifact path still hardcoded in a shipped module docstring

**File:** `installer/guards.py:26`
Unchanged from cycle 1. `.planning/phases/04-package-manager-redirect-policy/04-RESEARCH.md
Pitfall 1` is still the only absolute `.planning/` path in `installer/`;
`/gsd-cleanup` archives that file. The two bare `04-RESEARCH` references at lines
73 and 264 match the existing convention and are fine.

### IN-02: `EXIT_CODE = 127` still doubles as the usage-error code

**File:** `installer/guards.py:105`, `installer/guards.py:232-233`
Unchanged from cycle 1. `npm install -g` with no package exits 127 ("command not
found") for what is a usage error; `2` is the conventional code.

### IN-03: Test helpers still duplicated across four modules

**Files:** `tests/test_pnpm_globals.py:53` and `tests/test_executors.py:179`
(`_plant_executable`, byte-identical); `tests/test_policy.py:63` and
`tests/test_policies_e2e.py:37` (`_plant_volta_and_pnpm`);
`tests/test_guards.py:755` (`_plant_volta_pnpm`).
Unchanged from cycle 1, and `tests/conftest.py` already exists to host them.

### IN-04: `_UNRESOLVABLE_PREVIEW` uses `-` where every neighbouring message uses `—`

**File:** `installer/pnpm_globals.py:45`
`"pnpm not found on PATH - cannot preview the reinstall."` against
`"pnpm not found on PATH — install pnpm, then retry the reinstall."` two
definitions later. Cosmetic, but the two strings are read side by side.

---

_Reviewed: 2026-09-05T16:59:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep (cycle 2 re-review)_
