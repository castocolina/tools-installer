---
phase: 04-package-manager-redirect-policy
reviewed: 2026-09-05T15:36:55Z
depth: deep
files_reviewed: 23
files_reviewed_list:
  - installer/app.py
  - installer/executors.py
  - installer/guards.py
  - installer/guidance.py
  - installer/pnpm_globals.py
  - installer/policy.py
  - installer/registry.toml
  - installer/render.py
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
  critical: 4
  warning: 12
  info: 4
  total: 20
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-09-05T15:36:55Z
**Depth:** deep (cross-file: import graph, call chains, shim-generator behaviour verified by execution)
**Files Reviewed:** 23
**Status:** issues_found

## Summary

The redirect layer is well-factored and the guards module is unusually well-tested
(599 new lines in `tests/test_guards.py`, real `sh` execution of generated shims,
`sh -n` syntax checks). The `real_pnpm()` seam does close the two direct internal
call sites it was designed for (`executors._node`, `pnpm_globals`), and it is
double-protected: it strips `shim_dir` from the search path *and* rejects a
sentinel-carrying result, so a PATH entry spelled differently (trailing slash,
symlinked home) still cannot resolve back into the wrapper.

That said, four defects ship real incorrect behaviour:

1. The argv rewriter in `global_redirect_shim_script` has a third, undocumented
   gap — a **separated option value placed after the subcommand is forwarded to
   `volta install` as a package name**. `npm i -g --loglevel warn typescript`
   executes `volta install warn typescript`. `warn` is a real published npm
   package. Verified by executing the generated shim (CR-01).
2. The pnpm-globals feature treats **the whole catalog as the installed set**.
   On any machine that never installed `mmdc` — i.e. essentially every machine —
   `make doctor` prints a WARN claiming a pnpm self-update lost the user's
   globals, the Doctor screen claims "1 catalog tool(s) installed via pnpm add
   -g", and pressing `r` installs a package the user never selected (CR-02).
3. Pressing `r` runs a **blocking `subprocess.run` with inherited stdio inside a
   live Textual app**. This is the first and only TUI action in the codebase that
   spawns a subprocess, and the sibling action (`_apply_fix`) goes out of its way
   to redirect its console into a `StringIO` for exactly this reason (CR-03).
4. The reinstall issues a single `pnpm add -g <registry set>`. By the module's
   own stated pnpm-v11 isolation model, that **discards any global the registry
   does not know about**, and nothing snapshots `pnpm list -g` first (CR-04).

Answering the four questions posed with the review:

- **Q1 (`real_pnpm` coverage):** complete for direct Python call sites. The
  uncovered vector is indirect: `_script` and `_sdkman` hand a shell a command
  line and the child inherits the shimmed PATH, so a vendor install script's own
  `pnpm add -g` / `npm` call is still intercepted (WR-06).
- **Q2 (argv gaps):** yes — CR-01 is a third gap, distinct from both documented
  ones, and it changes which package gets installed. The `-[!-]*` arm also
  false-positives on attached-value short options whose value contains a `g`
  (`pnpm -Cmy-gadget add x` → `volta install x`), which is a materially worse
  instance of the accepted "substring-g cluster" gap.
- **Q3 (pnpm-globals):** `globals_done`/`globals_error` field independence is
  correct and `run_live`'s `(OSError, CommandError)` widening covers every
  exception `reinstall_node_globals` can raise on a reachable path. The failures
  are elsewhere: misreported state (CR-02), TUI corruption (CR-03), data loss
  (CR-04), stale audit after success (WR-03), `CommandError` abused as a
  "resolver failed" signal (WR-07).
- **Q4 (cross-file):** no helper is duplicated in production code. The consent
  text for the policy is now stale in two places (WR-02), the security note is
  gated on the wrong predicate (WR-01), and the shim-writer ordering contract is
  implicit rather than enforced (WR-09). Test-helper duplication is real but
  cosmetic (IN-02).

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Global-redirect shim forwards separated option values to `volta install` as package names

**File:** `installer/guards.py:161-176` (the argv-rewrite loop in `global_redirect_shim_script`)
**Severity:** BLOCKER

**Issue:** The rewrite loop keeps every non-flag token after the first one and
drops every flag. It has no notion of an option that consumes a following value,
so the *value* of a separated long option is treated as a package name and
handed to `volta install`.

The docstring documents exactly one value-taking-option gap: an option placed
**before** the subcommand, which corrupts subcommand detection. The
**after**-the-subcommand case is not documented, is not tested, and is worse:
it does not degrade to a hard block or a pass-through — it silently executes a
global install of a package the user never named. The parametrized test at
`tests/test_guards.py:512` only covers the attached form `--loglevel=warn`,
which is why this survived.

Reproduced by executing the generated shim:

```
$ npm i -g --loglevel warn typescript      -> VOLTA install warn typescript
$ npm i -g --registry https://r.example p  -> VOLTA install https://r.example p
$ pnpm add -g --dir /tmp typescript        -> VOLTA install /tmp typescript
```

`warn` is a real package on the public npm registry, so the first line installs
unintended third-party code globally under the very code path that already
trades pnpm's gated postinstalls for volta's ungated `npm install --global`
(see `installer/registry.toml:1469-1483`). That combination — an
attacker-influenceable package name plus unrestricted install scripts — is what
makes this a BLOCKER rather than a cosmetic argv wart.

Related, same arm: `-[!-]*` re-tests the whole cluster for a `g`, so an
attached-value short option whose value contains a `g` flips `is_global`:
`pnpm -Cmy-gadget add x` → `VOLTA install x`, turning a workspace-scoped local
add into a global install. The docstring's rule 3 explains why `-gD` matches and
`--filter=-g` does not, but never acknowledges this case.

**Fix:** Stop reconstructing the package list. Rewrite from the tail instead of
the head, or — simpler and consistent with "Don't Hand-Roll" — refuse to guess
when any token after the subcommand is a flag that could take a value:

```sh
# after the is_global/subcmd scan, before the volta branch:
case " $* " in
  *" -"[!-]*|*" --"*)
    # A flag survives past the subcommand; we cannot tell a value from a
    # package name without npm's/pnpm's grammar. Refuse rather than guess.
    echo "tools-installer: cannot safely redirect a global install that carries options." >&2
    echo "  Run: volta install <pkg>" >&2
    exit 127 ;;
esac
```

If the accepted-flag set must stay permissive, whitelist the pure boolean flags
(`-g`, `--global`, `-D`, `--save-dev`, `-E`, `--save-exact`, `-P`, `-w`,
`--force`, `--ignore-scripts`) and refuse on anything else. Either way, add a
test for `--loglevel warn` (separated form) beside the existing `--loglevel=warn`
case at `tests/test_guards.py:512`.

---

### CR-02: The pnpm-globals audit treats the whole catalog as the installed set — false alarm on every machine, and `r` installs unrequested packages

**File:** `installer/pnpm_globals.py:54-74`, `setup.py:251-258`, `installer/app.py:260`, `installer/guidance.py:136-157`, `installer/wizard_app.py:193-195`
**Severity:** BLOCKER

**Issue:** `node_globals()` enumerates every registry tool that *declares* a
`kind="node"` method. `audit_node_globals()` then reports as `missing` every one
whose `cmd` does not resolve on PATH. Nothing intersects that with "the user
actually installed this". `setup.py:252` and `app.py:260` both pass the full
catalog.

Verified against the real registry on a machine without `mmdc`:

```
entries  (NodeGlobal(tool_id='mmdc', npm_pkg='@mermaid-js/mermaid-cli', cmd='mmdc'),)
missing  ('mmdc',)
WARN  pnpm-managed global set is incomplete
      mmdc went missing from PATH. A pnpm self-update loses the globals
      installed by earlier `pnpm add -g` invocations.
```

Three distinct defects fall out of this:

1. **False diagnosis.** A user who never installed `mmdc` is told a pnpm
   self-update destroyed their globals. That is not a maybe — it is the default
   output of `make doctor` on a clean machine.
2. **False count.** `wizard_app.py:195` renders
   `f"{len(report.entries)} catalog tool(s) installed via pnpm add -g."` —
   `entries` counts *declarations*, not installations. The word "installed" is
   wrong.
3. **Unrequested install.** `action_reinstall_globals` → `reinstall_node_globals`
   → `pnpm add -g <every node package in the registry>`. Pressing `r` on the
   false alarm installs software the user never selected. This is the exact
   inverse of the wizard's select-then-confirm contract.

The module docstring rejects a persisted state file ("The snapshot IS the
registry ... matching this codebase's existing all-live-check convention"). But
`is_installed`/`guard_status`/`has_managed_block` are all *artifact* checks —
they read something this installer wrote. There is no artifact here, so the
"live check" degenerates into "assume everything in the catalog should exist".

**Fix:** The healthy set and the lost set are not distinguishable without a
record, so either record it or stop claiming to know. Minimum viable fix —
intersect with the installed map that `_build_app` already has in scope
(`setup.py:167`):

```python
# setup.py
def _node_globals_report() -> pnpm_globals.NodeGlobalsReport:
    return pnpm_globals.audit_node_globals(
        [t for t in tools if installed.get(t.id, False)]
    )
```

That alone is not sufficient (a lost global is by definition no longer
`installed`), so pair it with the real signal: query the live pnpm global set
(`pnpm list -g --json`, via `real_pnpm()`) and report only packages that pnpm
claims to manage but whose command does not resolve. Also fix the count wording
to `"{n} catalog tool(s) declared as pnpm globals"` and make the reinstall act
on `report.missing`, not on every entry.

---

### CR-03: `r` blocks the Textual event loop and writes subprocess output straight into the live TUI

**File:** `installer/wizard_app.py:242-249`; call chain `action_reinstall_globals` → `ui_common.run_live` → `pnpm_globals.reinstall_node_globals:101` → `run.run_command:19-26` (`subprocess.run(cmd, check=True)`)
**Severity:** BLOCKER

**Issue:** `run_command` does not capture output; the child inherits the app's
stdout/stderr. Textual owns the terminal (alternate screen, raw mode) while the
app runs, so `pnpm add -g` writes its progress bars, warnings and postinstall
output directly into the rendered frame. There is no `self.app.suspend()`, no
`capture_output`, and no worker — the call runs synchronously on the event loop,
so the UI is frozen for the whole install (a `pnpm add -g` of
`@mermaid-js/mermaid-cli` pulls Puppeteer/Chromium; this is minutes, not
seconds, with no spinner and no way to cancel).

This is the only TUI-invoked subprocess in the codebase. Every sibling action is
pure file IO, and `_apply_fix` (`setup.py:230-243`) explicitly hands
`configure_path` a `Console(file=io.StringIO())` with the comment *"A quiet
console keeps configure_path's own prints from corrupting the running TUI"*.
The same hazard was recognised for a function that only prints one line, then
missed for the one that shells out.

The existing test cannot catch this: `test_doctor_r_reinstalls_once_and_reports_success`
injects a pure-Python `reinstall` closure, so no subprocess ever runs under
`run_test`.

**Fix:** Either suspend the app around the call, or capture the child's output.
Suspending is the smaller change and gives the user real-time feedback:

```python
def action_reinstall_globals(self) -> None:
    if self.globals_done:
        return
    if not self._node_globals().entries:
        return
    with self.app.suspend():
        _, self.globals_error = run_live(self._reinstall_globals)
    self.globals_done = self.globals_error is None
    self._refresh_guidance()   # see WR-03
    self._refresh_body()
```

If the TUI must stay up, run it through `@work(thread=True)` and inject a runner
that uses `subprocess.run(cmd, capture_output=True, text=True)`, folding the
captured stderr into `globals_error` on failure.

---

### CR-04: Reinstalling the registry set can discard pnpm globals the registry does not know about

**File:** `installer/pnpm_globals.py:77-102`
**Severity:** BLOCKER (data-loss risk)

**Issue:** `reinstall_argv` builds one `pnpm add -g pkg1 pkg2 ...` and its own
docstring states the premise: *"per-package calls recreate the isolation that
loses them"* — i.e. each `pnpm add -g` invocation lands in a fresh hash-keyed
directory and supersedes the previous global set. If that model is correct (and
the whole feature is built on it), then this single invocation supersedes
whatever is currently there — including every global the user installed by hand
(`pnpm add -g typescript`, `pnpm add -g vercel`, …) that is not in this
installer's registry.

Nothing mitigates this:
- no `pnpm list -g` snapshot is taken before the write, so the pre-existing set
  is neither preserved nor even reported;
- the module docstring explicitly declines to persist state;
- the preview shown to the user (`reinstall_preview`) prints only the argv, so
  it never says "and this will drop anything else you had".

The guidance text compounds it: `guidance.py:154` promises *"reinstall the lost
globals"*, which a user reads as "restore my global set", not "replace my global
set with the installer's subset of it".

**Fix:** Snapshot before you replace. `real_pnpm()` is already available:

```python
def current_globals(*, runner_out: Callable[[list[str]], str], pnpm: str) -> tuple[str, ...]:
    """Package names pnpm currently manages globally (pnpm list -g --json)."""
    ...

def reinstall_argv(entries, *, pnpm: str, keep: Sequence[str] = ()) -> list[str]:
    packages = list(dict.fromkeys((*(e.npm_pkg for e in entries), *keep)))
    return [pnpm, "add", "-g", *packages]
```

If querying pnpm is out of scope for this phase, then at minimum the preview and
the guidance must state the destructive scope explicitly ("this replaces your
pnpm global set with: …") so the user consents to it, and the wording "reinstall
the lost globals" must change.

---

## Warnings

### WR-01: The "volta runs npm install scripts" security note is gated on the wrong predicate

**File:** `installer/guidance.py:106-121`
**Issue:** The note is emitted only when `status.get("pnpm", False)`. But
`install_global_redirect_shims` writes the **npm** wrapper whenever `volta`
resolves, independently of whether a real pnpm resolves
(`guards.py:285-319`). On a machine with volta and no pnpm — a normal state,
since `npm i -g pnpm` is itself now redirected — `npm i -g <pkg>` routes to
`volta install` with ungated install scripts and the user is told nothing. The
code comment claims "a live pnpm shim is the one honest on-disk signal that
global installs are being routed to volta"; the npm shim is an equally honest
signal and covers strictly more cases.
**Fix:** `if status.get("pnpm", False) or status.get("npm", False):` — or, more
precisely, gate on "any GLOBAL_REDIRECTED name whose on-disk body carries
`REDIRECT_SENTINEL`", surfaced from `guard_state` the way `guard_redirect_warning`
already is.

### WR-02: Policy consent text never mentions that enabling the ban wraps `pnpm` and reroutes globals to volta

**File:** `installer/wizard_app.py:678-682`, `installer/policy.py:139-143`, `installer/app.py:314`
**Issue:** The Policies screen detail still reads *"Blocks bare pip, pip3, npm,
and npx so installs route through uv/pnpm."* and `ban_policy.description` only
adds npx→`pnpm dlx`. Neither says that toggling this policy installs a wrapper
in front of the user's `pnpm` binary, nor that global installs are rerouted to
volta, nor that this deliberately gives up pnpm's gated postinstalls — a
tradeoff documented at length in `registry.toml:1469-1483` and surfaced in the
Doctor view only *after* the fact. `app.run_guard`'s confirm prompt has the same
gap. The user is consenting to a description of the pre-phase-4 behaviour.
**Fix:** Update all three strings, e.g. detail line 1: *"Blocks bare pip/pip3,
redirects npx to `pnpm dlx`, and routes `npm`/`pnpm` global installs to `volta
install`."* plus a line 4: *"Global installs then run npm's install scripts
unrestricted — keep untrusted packages on a project-local `pnpm add`."*

### WR-03: A successful reinstall leaves the "went missing" warning on screen

**File:** `installer/wizard_app.py:242-249`
**Issue:** `action_reinstall_globals` calls `_refresh_body()` but not
`_refresh_guidance()`, so the Audit block still renders
`node_globals_guidance(...)` computed before the install. The screen ends up
showing "pnpm-managed global set is incomplete / mmdc went missing from PATH"
directly above "pnpm globals reinstalled." Unlike the PATH audit — which is a
deliberate snapshot because the process PATH cannot change — this audit is a
live `shutil.which` probe whose answer the action just tried to change.
**Fix:** Add `self._refresh_guidance()` before `self._refresh_body()` in
`action_reinstall_globals` (see the CR-03 snippet).

### WR-04: `guard_redirect_warning` reports the wrong cause when a foreign `pnpm` occupies the shim dir

**File:** `installer/guards.py:496-501`
**Issue:** The pnpm branch fires on `npm_redirect_live and not is_our_shim(path)`
and always blames "a real 'pnpm' was not resolvable". But
`install_global_redirect_shims` reaches the same on-disk state via a different
route — `results["pnpm"] = "skipped (real binary here)"` (`guards.py:287-289`) —
when a genuine `pnpm` binary already lives in the shim dir. The user is then told
pnpm could not be found while it is sitting in the very directory being
inspected, and the suggested remedy ("install pnpm and re-apply") will never
change anything.
**Fix:** Distinguish the two: if `(shim_dir / spec.passthrough).exists()` and it
is not our shim, emit "a non-managed 'pnpm' already occupies `<shim_dir>`; move
it aside and re-apply" instead.

### WR-05: Excluding the entire shim dir makes a `pnpm` installed into `~/.local/bin` permanently unresolvable

**File:** `installer/guards.py:209-215` (`real_binary`), `installer/executors.py:78-81`
**Issue:** `real_binary` drops `shim_dir` from the search path before calling
`shutil.which`. `shim_dir` is the managed bin dir, `~/.local/bin`. A pnpm
installed there — `npm i -g pnpm` with `prefix=~/.local`, or
`corepack enable --install-directory ~/.local/bin`, both documented setups — can
never be found. Consequences: `_node` raises `ExecutorError("pnpm not found
(managed shim dir excluded from the search)")` and every `kind="node"` install
fails on a machine where `pnpm --version` works fine; the pnpm wrapper is never
installed; `reinstall_preview` reports "pnpm not found". The sentinel check on
line 213 already rejects our own shims, so the directory exclusion is redundant
belt-and-braces that costs correctness.
**Fix:** Drop the directory exclusion and rely on the sentinel check, which is
the stronger and more precise guard:

```python
def real_binary(name, *, shim_dir, path_value, lookup=which_in_path):
    found = lookup(name, path_value)
    if found is None or is_our_shim(Path(found)):
        # our shim won the lookup: retry with its directory removed
        rest = [e for e in path_value.split(os.pathsep) if e and e != str(shim_dir)]
        found = lookup(name, os.pathsep.join(rest))
    return None if found is None or is_our_shim(Path(found)) else found
```

At minimum, widen `_node`'s error message so it names the directory and tells the
user what to do, rather than describing an internal search rule.

### WR-06: `real_pnpm()` does not cover subprocesses the installer hands to a shell

**File:** `installer/executors.py:47-54` (`_script`), `installer/executors.py:84-96` (`_sdkman`)
**Issue:** Both build a command line and hand it to `sh -c` / `bash -c` with the
parent's environment, so the child inherits a PATH whose first entry is the
managed bin dir. Any vendor install script the installer pipes to a shell that
internally runs `pnpm add -g` now silently becomes `volta install`, and one that
runs `npm`/`npx` hits a hard block and exits 127. The absolute-path treatment
was applied to the two Python call sites but the shim dir was never scrubbed
from the child environment.
**Fix:** Either pass an explicitly sanitised `env=` (PATH with `shim_dir`
removed) to the runner for `_script`/`_sdkman`, or document the exposure
explicitly in `guards.py`'s "Neither layer is hermetic" paragraph, which
currently lists only the `python -m pip` and PATH-order escapes.

### WR-07: `CommandError` is used to signal "the resolver failed", producing a message that claims a command ran

**File:** `installer/pnpm_globals.py:99-100`
**Issue:** `raise CommandError(["pnpm", "add", "-g"], 127)` renders as
`command failed (127): pnpm add -g`, which `run_live` puts verbatim under
"Reinstall failed." in the TUI. No command ran; pnpm could not be located. The
message points the user at a command that does not appear anywhere in the
process, and the argv it names (`pnpm`, bare) is precisely the form this module
exists to avoid.
**Fix:** Raise a dedicated error with an actionable message and add it to
`run_live`'s tuple, or reuse `ExecutorError`:

```python
class PnpmUnavailable(RuntimeError):
    """No real pnpm could be resolved — nothing was executed."""


# pnpm_globals.reinstall_node_globals
if resolved is None:
    raise PnpmUnavailable(
        "pnpm not found on PATH — install pnpm, then retry the reinstall."
    )
```
and add `PnpmUnavailable` to `run_live`'s `except (OSError, CommandError)` tuple
in `installer/ui_common.py:47`.

### WR-08: `action_reinstall_globals` silently does nothing in two reachable states

**File:** `installer/wizard_app.py:242-246`
**Issue:** Both `if self.globals_done: return` and
`if not self._node_globals().entries: return` swallow the keypress with no
change to the rendered body. Pressing `r` on a machine with no node-kind tools
produces no feedback whatsoever, and the footer advertises the action
(`ui_common.py:144`), so the user has every reason to expect one.
**Fix:** Set an explanatory message instead of returning silently, e.g.
`self.globals_error = "Nothing pnpm-managed to reinstall."` guarded by a third
flag, or render the empty-set preview line (`_EMPTY_PREVIEW` is already the
string shown above) in yellow with "nothing to do".

### WR-09: `install_global_redirect_shims` reports "blocked" for npm without writing anything

**File:** `installer/guards.py:291-293`
**Issue:** When volta is unresolvable and the entry has no pass-through, the
function returns `"blocked (volta not found)"` but never writes a body. That is
only truthful because both callers (`policy._apply:99-101`,
`app.run_guard:322-324`) call `install_shims` first. The dependency is stated in
a comment but not enforced: called standalone — as a future caller, or a test,
easily could — it reports a block that does not exist on disk, and
`policy._apply` counts it toward `active`.
**Fix:** Write the hard-block body from this function too (it is idempotent and
byte-identical to what `install_shims` produces — `tests/test_guards.py:628`
already asserts the last two lines match), or rename the state to
`"left blocked (volta not found)"` and assert the precondition.

### WR-10: The pnpm wrapper makes the `pnpm` catalog tool read as installed forever

**File:** `installer/guards.py:63-72` + `installer/status.py:26`
**Issue:** `is_installed` is `shutil.which(tool.cmd) is not None`. Once the
wrapper is written to `~/.local/bin/pnpm`, `which("pnpm")` succeeds regardless of
whether the real pnpm still exists. If the user later removes pnpm, the wizard
keeps reporting pnpm as installed, `mmdc`'s `requires = ["pnpm"]` dependency
resolves as satisfied, and running `pnpm` produces a raw `exec: <path>: not
found` from the wrapper instead of a clean "command not found".
`guard_redirect_warning` does not detect it either — it only checks for the
sentinel, never that the baked target still exists.
**Fix:** Have `guard_redirect_warning` verify the baked target path is still
executable (parse it out of the `exec` line, or store it alongside), and warn
"the redirect target `<path>` no longer exists; re-apply the policy".

### WR-11: `run_guard` surfaces the PATH warning but not the redirect warning

**File:** `installer/app.py:327` vs `installer/app.py:212-217`
**Issue:** `guard_state` (Doctor/TUI path) folds `guard_redirect_warning` into
the warning string; `run_guard` (the `--guard` CLI path) passes only
`guard_path_warning`. A user who installs the ban from the CLI on a machine
without pnpm/volta gets the per-name action lines but never the sentence
explaining that npx/npm degraded to hard blocks and what to do about it.
**Fix:** Mirror `guard_state`'s composition in `run_guard`, or call
`guard_state` there and pass its warning to `render_guard`.

### WR-12: `global_redirect_shim_script` will `KeyError` for any future `GLOBAL_REDIRECTED` entry without a `BANNED` hint

**File:** `installer/guards.py:122-127`
**Issue:** The `passthrough is None` branch does `hint = BANNED[name]`, an
unguarded dict lookup into a *different* table. It works today only because the
sole such entry (`npm`) happens to be in both. The `passthrough is not None`
branch beside it raises a deliberate, explanatory `ValueError` for its own
missing input; this one raises a bare `KeyError` from inside a shim generator.
**Fix:** Mirror the sibling branch:
```python
hint = BANNED.get(name)
if hint is None:
    raise ValueError(f"'{name}' has no pass-through and no BANNED hint to fall back to")
```

---

## Info

### IN-01: Shipped source hardcodes a `.planning/` artifact path

**File:** `installer/guards.py:22`
**Issue:** `.planning/phases/04-package-manager-redirect-policy/04-RESEARCH.md
Pitfall 1` is the only absolute `.planning/` path in `installer/`. Bare plan
references ("plan 04-03", "R-02", "SC#1", "D-06/D-08") match an existing
convention, but this one names a file that `/gsd-cleanup` archives, leaving a
dangling pointer in a user-facing module docstring.
**Fix:** Move the substantive reasoning (already present, two sentences above)
and drop the path, or point at the durable
`docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md` instead.

### IN-02: Test helpers duplicated across four modules

**Files:** `tests/test_pnpm_globals.py:47-52` and `tests/test_executors.py:126-131` (`_plant_executable`, byte-identical); `tests/test_policy.py:55-62` and `tests/test_policies_e2e.py:37-44` (`_plant_volta_and_pnpm`, byte-identical); `tests/test_guards.py:669-679` (`_plant_volta_pnpm`, same job, different name and return shape)
**Fix:** One `tests/conftest.py` fixture (`plant_executable`, `volta_and_pnpm`) replacing all four.

### IN-03: `EXIT_CODE = 127` reused for "a global install needs a package name"

**File:** `installer/guards.py:174-175`
**Issue:** 127 conventionally means "command not found". Reusing it for a usage
error makes shell-level `$?` checks and CI logs ambiguous.
**Fix:** Exit `2` (conventional usage error) for the missing-package case; keep
127 for the hard block.

### IN-04: Test gap that let CR-01 through

**File:** `tests/test_guards.py:506-515`
**Issue:** The parametrization covers `--loglevel=warn` (attached) but never the
separated form. Adding one row would have caught CR-01 immediately.
**Fix:**
```python
(("install", "-g", "--loglevel", "warn", "typescript"), "VOLTA install typescript\n"),
(("add", "-g", "--dir", "/tmp", "typescript"), "VOLTA install typescript\n"),
```

---

_Reviewed: 2026-09-05T15:36:55Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
