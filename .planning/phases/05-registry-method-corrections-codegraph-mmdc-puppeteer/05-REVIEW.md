---
phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
reviewed: 2026-09-05T00:00:00Z
depth: deep
files_reviewed: 16
files_reviewed_list:
  - installer/executors.py
  - installer/guidance.py
  - installer/model.py
  - installer/pnpm_globals.py
  - installer/registry.toml
  - installer/versions.py
  - setup.py
  - tests/test_deps.py
  - tests/test_executors.py
  - tests/test_guidance.py
  - tests/test_model.py
  - tests/test_node_install_e2e.py
  - tests/test_pnpm_globals.py
  - tests/test_registry.py
  - tests/test_setup.py
  - tests/test_versions.py
findings:
  critical: 4
  warning: 10
  info: 5
  total: 19
second_pass:
  reviewer: codex/gpt-5.6-sol (high reasoning effort)
  reviewed: 2026-09-05T00:00:00Z
  scope: same diff, reviewed independently and in parallel
  findings:
    high: 2
    medium: 2
    total: 4
  fixed: 4
  deferred: 0
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-09-05
**Depth:** deep (cross-file: import graph, call chains into `installer/app.py`, `installer/engine.py`,
`installer/status.py`, `installer/download.py`, `installer/wizard_app.py`; four findings reproduced by
executing the shipped code)
**Files Reviewed:** 16
**Status:** issues_found

## Summary

The mechanism this phase builds is well-shaped. `NodeInstallPolicy` is a genuine
declaration-versus-installation split, `_reinstall_parts` really is one builder shared by preview
and effect, the version floors really do fail closed on an unreadable `--version`, and the smoke
check really does turn a zero exit code from `pnpm add -g` into an install failure when the browser
cannot start. `parse_declared_version` closing the `min_node = "22.bad"` → `(22,0,0)` hole is a
correct and non-obvious fix. Registry validation at load time is thorough and well-tested
(`allow_build ⊆ install group`, comma/empty rejection on both halves of a group spec, a closed
`smoke` name set cross-checked against the executor's dispatch table). `ruff` is clean and the
targeted suites pass.

The defects are not in the mechanism — they are in **who the mechanism is applied to** and **what
the phase claims about it**. Four of them ship incorrect behaviour:

1. The Doctor replay attaches the registry's `--allow-build=puppeteer` and `puppeteer@^25` to
   *any* live `puppeteer`, including one the user installed by hand and this installer never
   touched. Pressing `r` therefore creates a **persistent, package-level, version-unbounded**
   script-execution grant on a machine that never had one, and moves a hand-pinned package across
   a major line. Plan 05-04's T-05-14 states the opposite in as many words ("this path adds no
   new grant to a machine"). Reproduced by execution (CR-01).
2. A smoke-check failure raises *after* `pnpm add -g` has already succeeded. The package stays
   installed, its bin shim stays on PATH, and `installer/status.py::is_installed` is
   PATH-presence-based — so the **next** run reports `ALREADY_INSTALLED` and the gate never runs
   again. The exact "installed but cannot start" state the check exists to catch becomes
   permanent and silent one run later (CR-02).
3. The brownfield population this phase exists for — a machine that installed `mmdc` from *this
   catalog before Phase 5*, i.e. standalone, with no global `puppeteer` and no build allowance —
   is invisible to the new detection (`split_install_groups` requires ≥2 present members) and is
   not repaired by the replay (the replay only puts back what pnpm already lists). Success
   criterion 5 of 05-04-PLAN.md ("A brownfield user is TOLD their install group is split") does
   not hold for that shape. Reproduced by execution (CR-03).
4. `_install_group_key`'s fallback turns "pnpm did not tell us which group this package is in"
   into "this package is in a group of its own", which the detector reads as a split. On any
   pnpm whose `list -g --json` omits the per-package `path`, a *correctly grouped* machine is told
   its install group is broken and pushed at an action that runs a real global install. This
   violates the module's own stated invariant that an unknown must never be rendered as a fact —
   the invariant the `known` flag was added to defend. Reproduced by execution (CR-04).

Answering the focus areas posed with the review:

- **`--allow-build` trust grant:** load-time containment (`allow_build ⊆ install group`) is real and
  well-tested. The containment is bypassed on the *replay* path, which derives allowances from the
  registry but gates them on pnpm's live set rather than on what this installer installed (CR-01).
- **Package-legitimacy gate:** it is a process step recorded in `05-03-SUMMARY.md`, not shipped
  code. Nothing in the repository re-runs it, so it cannot fail again after the fact; the
  normalization rule it describes is correct but exists only in prose (IN-03).
- **Version-floor preflight:** genuinely fail-closed on both an unreadable version and an old one
  (`meets_minimum` returns False when either side fails to parse), correctly probes the *resolved
  absolute* pnpm rather than the wrapper, and probes nothing when no new param is present. This
  one holds. Two message/diagnosis defects only (WR-08).
- **Puppeteer smoke check:** it does fail the install for a browser that cannot start — but it can
  pass on a browser this install did not produce, it picks a browser by lexicographic *path* sort
  rather than version (verified: it prefers `linux-99.0.4844.51` over `linux-140.0.7339.16`), it
  knows only two of puppeteer's cache-location mechanisms, and every one of its tests models the
  Linux cache layout although the registry ships the check on macOS too (WR-02, WR-03).
- **Doctor split-group detection:** it does not regress the console path (verified: `run_doctor`
  passes no policy, `split_groups` is `()`, the group query is never called), but it misreports in
  the path-less case (CR-04), overstates the consequence in its user-facing wording against the
  phase's own container evidence (WR-01), and is silent for the brownfield shape that matters most
  (CR-03).

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: The Doctor replay creates a new persistent `--allow-build` grant for packages this installer never installed

**Severity:** Critical (security — persistent elevation of privilege)
**File:** `installer/pnpm_globals.py:448-451`, `installer/pnpm_globals.py:416-418`, `setup.py:260-275`

**Issue:** `_reinstall_parts` decides which allowances to emit with `if name in present`, where
`present` is the set of packages **pnpm currently manages**, not the set this installer installed:

```python
flags = [
    f"--allow-build={name}" for name in dict.fromkeys(policy.allow_build) if name in present
]
```

Reproduced against the shipped registry:

```
>>> reinstall_argv(["puppeteer", "typescript"], pnpm="/x/pnpm", policy=node_install_policy(load_tools(REGISTRY)))
['/x/pnpm', 'add', '-g', '--allow-build=puppeteer', 'puppeteer@^25', 'typescript']
```

Consider a machine whose only `puppeteer` came from the user's own `pnpm add -g puppeteer` — pnpm's
default-deny gate blocked its postinstall, which is what the user chose by not passing the flag.
That user opens the Doctor after a pnpm self-update and presses `r`. The replay now passes
`--allow-build=puppeteer`, and per pnpm's own `add` documentation (quoted verbatim in
`installer/registry.toml` and in T-05-09) that flag **writes the package into pnpm's build-allowance
configuration**, so the package "will always be allowed to run its scripts in the future" — keyed by
name, with no version qualifier, for commands this project never issues.

Plan 05-04's T-05-14 disposition asserts the exact opposite: *"the replay creates no allowance the
install path did not already create, since both read the same registry field — so this path adds no
new grant to a machine."* That reasoning holds only if the package arrived through this installer's
catalog. `_reinstall_parts` never checks that, and it cannot: pnpm's flat name list carries no
provenance. The threat register's stated mitigation is therefore not the code's behaviour, and the
"four controls actually in force" in T-05-09 lose the one that was carrying the weight (an
allowance may only name a package *this invocation* installs).

Aggravating: a second, non-security effect rides on the same predicate. `_render_spec` applies the
registry's `^25` pin to the same hand-installed package (`puppeteer@^25` above), so a user
deliberately holding `puppeteer` at 24 — or already on 26 — is moved across a major line by an
action labelled "reinstall the pnpm-managed global set". T-05-23's disposition claims *"Registry-known
packages are unaffected because the policy carries their pins and groups"*; "unaffected" is only
true for packages this installer installed.

Mitigating (but not sufficient): the preview string on the Doctor screen does contain the flag and
the pin, so the change is visible to a user who reads the argv. Nothing on that screen explains that
`--allow-build` is persistent, and the action's own prompt is "Press r to reinstall the
pnpm-managed global set."

**Fix:** stop deriving replay-time authority from the live set. Either (a) drop `--allow-build` and
version pins from the replay entirely — the replay's stated job is "put back what pnpm had", and
build allowances pnpm already recorded survive a replay on their own — or (b) gate the policy on
what the catalog actually installed. If (b), the minimum honest version also requires disclosing
the persistence at the point of consent:

```python
# installer/pnpm_globals.py
def _reinstall_parts(
    packages: Sequence[str],
    policy: NodeInstallPolicy,
    *,
    catalog_installed: frozenset[str] = frozenset(),
) -> tuple[list[str], list[str]]:
    ...
    # An allowance is a PERSISTENT, package-level grant (pnpm `add` docs). It may only
    # be re-asserted for a package this installer itself installed under that grant --
    # never for one the user installed by hand, where its absence was the user's choice.
    flags = [
        f"--allow-build={name}"
        for name in dict.fromkeys(policy.allow_build)
        if name in present and name in catalog_installed
    ]
    # Same predicate for the pin: re-pinning a hand-installed global moves a version
    # the user chose.
```

and update T-05-14 / T-05-23 in `05-04-PLAN.md` so the register describes the shipped behaviour
rather than the intended one.

---

### CR-02: A failed smoke check leaves the package installed and on PATH, so the gate never runs again

**Severity:** Critical (defeats the guarantee the check was built for)
**File:** `installer/executors.py:241-252`, `installer/engine.py:80-81`, `installer/status.py:26-27`

**Issue:** `_node` runs the install first and smoke-tests afterwards:

```python
runner([pnpm, "add", "-g", *allowances, group])
...
SMOKE_CHECKS[smoke]()          # raises ExecutorError
```

`install_tool` turns that `ExecutorError` into `InstallStatus.FAILED` — correct for *this* run. But
the packages are installed, and pnpm has written `$PNPM_HOME/puppeteer` / `$PNPM_HOME/mmdc` onto
PATH (confirmed by the registry's own container note: "the puppeteer shim on PATH is
`$PNPM_HOME/bin/puppeteer`"). On the very next run:

```python
if is_installed(tool):                       # installer/engine.py:80
    return InstallOutcome(tool.id, InstallStatus.ALREADY_INSTALLED)
```

and `is_installed` is `shutil.which(tool.cmd) is not None`. So the tool the smoke check just proved
cannot work is reported as **already installed**, the smoke check never runs again, and no artefact
records the failure. The Doctor cannot see it either: `audit_node_globals` computes `missing` from
`which(entry.cmd)`, which resolves.

This is the same failure class the check exists to close, one run later. On the Linux machine that
motivated the check — headless-Chrome shared libraries absent — the user attempts the install once,
sees a real error, installs the libraries or does not, and from then on the installer asserts the
tool is present regardless.

There is no rollback either: nothing removes the half-working global after the smoke check
condemns it.

**Fix:** the smoke check has to be part of "is it installed", not only part of "did the install
run". Two options, both small:

```python
# installer/executors.py -- fail before creating the PATH shim is not possible for a
# postinstall-driven download, so record the condemnation instead:
except ...:
    _mark_unhealthy(tool_id, reason)   # e.g. a marker under ~/.local/state/tools-installer/
```

or, preferably, re-run the declared smoke as part of the availability question:

```python
# installer/status.py::is_installed
# A command on PATH is evidence a package manager ran, never evidence the tool works.
# A method that declares a smoke check must satisfy it before the tool counts as installed.
```

Either way `installer/engine.py`'s `ALREADY_INSTALLED` short-circuit must not be reachable for a
tool whose last smoke check failed.

---

### CR-03: The brownfield remedy is silent and ineffective for the population it was written for

**Severity:** Critical (the phase's own success criterion does not hold for the main brownfield shape)
**File:** `installer/pnpm_globals.py:354-378`, `installer/pnpm_globals.py:421-451`,
`installer/registry.toml` (mmdc "Brownfield" comment block)

**Issue:** Every machine that installed `mmdc` from this catalog *before this phase* is in exactly
one state: `@mermaid-js/mermaid-cli` is a global, `puppeteer` is **not** a global (it was at best
pulled into mmdc's own tree by `autoInstallPeers`), and no build allowance was ever granted — so
`~/.cache/puppeteer` is empty and `mmdc` fails at render time. That is the pre-fix bug this phase
exists to correct.

The new detection cannot see that state:

```python
present = tuple(name for name in declared if name in present_anywhere)
if len(present) < 2:
    continue                     # installer/pnpm_globals.py:372-373
```

and the replay does not repair it, because it only replays names pnpm already lists. Reproduced
against the shipped registry:

```
live = (("@mermaid-js/mermaid-cli",), ("typescript",))
split_install_groups(policy, live)                       -> ()
reinstall_argv([...], policy=policy)
  -> ['/x/pnpm', 'add', '-g', '@mermaid-js/mermaid-cli', 'typescript']
```

No warning, no `puppeteer`, no `--allow-build`, no pin. `report.missing` is also empty (the `mmdc`
command resolves), so `node_globals_guidance` emits nothing at all. The user sees a Doctor that
says their pnpm globals are healthy while `mmdc` cannot render.

`05-04-PLAN.md` success criterion 5 states *"A brownfield user is TOLD their install group is split,
by name, on whichever Doctor surface they use, and pointed at the one action that repairs it"*, and
T-05-27 is dispositioned `mitigate` on that basis. Both are true only for the *other* brownfield
shape (both packages present, held apart), which arises when the user re-runs the catalog after
this phase ships — a state the catalog itself creates and can therefore avoid. The
`installer/registry.toml` comment likewise tells a future maintainer the `r` action is the remedy,
without the "only if `puppeteer` is already a global" qualifier.

**Fix:** detect a declared group whose *dependent* is present and whose *peer* is absent, and let
the replay complete it. That is a different condition from a split, and deserves its own wording:

```python
def incomplete_install_groups(
    policy: NodeInstallPolicy, live: tuple[tuple[str, ...], ...]
) -> tuple[tuple[str, ...], ...]:
    """Declared groups whose FIRST member (the dependent) pnpm manages while a peer is absent.

    A missing peer is not a split -- pnpm is holding nothing apart, the peer was never
    installed globally at all. It is the state every pre-phase-5 `mmdc` machine is in.
    """
```

If completing the group on the user's behalf is out of scope, then T-05-27's disposition must move
back to `accept` for this shape and the registry comment must say which brownfield state `r`
repairs — a comment that overstates its own remedy is worse than the one it replaced.

---

### CR-04: Unknown group membership is rendered as a split — a correctly grouped machine is told it is broken

**Severity:** Critical (misreport that recommends a real, permission-granting install)
**File:** `installer/pnpm_globals.py:258-265`, `installer/pnpm_globals.py:285-293`

**Issue:**

```python
def _install_group_key(details: object, fallback: str) -> str:
    if isinstance(details, dict):
        path = cast(dict[str, object], details).get("path")
        if isinstance(path, str) and path:
            ...
    return fallback                       # fallback = f"ungrouped:{name}"
```

The fallback key is **unique per package**, so "pnpm did not report a path for this package" is
byte-identical to "this package is alone in its own install group". `split_install_groups` then
reports a split. Reproduced with a `pnpm list -g --json` document that carries `from`/`version` but
no per-package `path`:

```
groups: (('@mermaid-js/mermaid-cli',), ('puppeteer',))
split:  (('@mermaid-js/mermaid-cli', 'puppeteer'),)
```

The Doctor tells a user whose group is perfectly healthy that "pnpm is holding
`@mermaid-js/mermaid-cli` and `puppeteer` in separate global installs, so the dependent cannot load
its peer at runtime", and points at `r` — which then runs a real `pnpm add -g` carrying a persistent
build allowance (CR-01).

This is precisely the failure mode the module's `known` flag exists to prevent. Its own docstring
(lines 124-131) argues at length that an unanswered query must never be rendered as a fact, and
`audit_node_globals` honours that for the *whole* query. The per-package membership question gets
the opposite treatment: it fails open into a positive finding. The `path` shape is also, by the
module's own admission, version-dependent ("the project objects ARE the install groups on some pnpm
versions"), so the code already knows it is reasoning about a format it does not control.

**Fix:** make "membership unknown" a distinct value and refuse to conclude anything from it.

```python
_UNKNOWN_GROUP = None

def _install_group_key(details: object) -> str | None:
    """None means pnpm did not tell us which install this package belongs to.

    NOT the same as 'its own group': a package with no reported path is a package
    whose membership was never read, and an unread membership must never become a
    finding (same rule as NodeGlobalsReport.known).
    """
    ...

# split_install_groups: skip any declared group with an unknown-membership member
if any(membership.get(name) is None for name in present):
    continue
```

with a regression test built from a `path`-less document, mirroring the existing
`_SPLIT_STATE_JSON` / `_GROUPED_STATE_JSON` fixtures.

---

## Warnings

### WR-01: The split-group warning asserts a runtime failure this phase's own container run disproved

**Severity:** High
**File:** `installer/guidance.py:176-193`

The user-facing WARN states as fact:

> "pnpm is holding {names} in separate global installs, so the dependent cannot load its peer at
> runtime — the tool fails when it is run rather than when it is installed."

`05-01-SUMMARY.md` records the opposite measurement for that exact state: `BROWNFIELD_BEFORE=ok`
— *"render succeeded after standalone mmdc + standalone allow-build puppeteer, without the grouped
invocation. The analysed `Cannot find module 'puppeteer'` gap did not reproduce on pnpm 12.3.4 with
default `autoInstallPeers`."* The registry comment and the plan both carry that finding honestly;
only the sentence the user actually reads does not.

The real, defensible claim is narrower and still worth warning about: the split depends on a
user-settable pnpm option (`auto-install-peers`) rather than on a declared group, so it can break
without warning — which is the reasoning `05-01-SUMMARY.md` gives for keeping `co_install` at all.

**Fix:** state the measured condition, not an unmeasured consequence:

```python
meaning=(
    f"pnpm is holding {names} in separate global installs. The dependent resolves its "
    "peer only through pnpm's user-settable `auto-install-peers`, so this pair breaks "
    "if that setting changes; the declared group does not depend on it."
),
```

---

### WR-02: The smoke check picks a browser by lexicographic path sort, and accepts one this install did not produce

**Severity:** Medium
**File:** `installer/executors.py:103-123`, `tests/test_executors.py:628-656`

`_puppeteer_browser` returns `sorted(...)[-1]` over full paths. That is a string sort, not a version
comparison. Verified by execution against a cache holding two builds:

```
picked: .../chrome-headless-shell/linux-99.0.4844.51/.../chrome-headless-shell
        (over linux-140.0.7339.16)
```

The test that guards this is named `test_smoke_prefers_headless_shell_highest_version` and uses
`linux-140.0.0` vs `linux-152.0.0` — equal-width numbers, where lexicographic and numeric order
coincide. The test name asserts a property the code does not have.

Compounding it, the search covers the whole cache rather than what this install produced. The code
comment discloses this ("Accepted residual: the search covers the WHOLE cache"), but the residual is
larger than it reads: it means the gate can be satisfied by an old, unrelated, still-working browser
while the browser the just-installed `puppeteer@^25` needs is missing or unstartable — the precise
false-INSTALLED outcome the check was added to prevent.

**Fix:** sort by parsed version rather than by path string, and prefer the build directory whose
mtime is newest (an approximation of "what this install just wrote") before falling back to
"any browser in the cache":

```python
def _build_version(path: Path) -> tuple[int, ...]:
    # <cache>/<browser>/<platform>-<build>/... -- the build segment is the version.
    _, _, build = path.parts[-3].partition("-")
    return tuple(int(part) for part in build.split(".") if part.isdigit())

shells.sort(key=lambda p: (p.stat().st_mtime, _build_version(p)))
```

and rename/extend the test to cover `99` vs `140`.

---

### WR-03: The smoke check knows only two of puppeteer's cache mechanisms, and its macOS layout is untested

**Severity:** Medium
**File:** `installer/executors.py:92-123`, `tests/test_executors.py:506-517`

`_puppeteer_cache_dir` handles `PUPPETEER_CACHE_DIR` and `~/.cache/puppeteer`. Puppeteer also honours
a `cacheDirectory` in `.puppeteerrc.cjs` / `puppeteer.config.js` and npm-config keys. On a machine
using either, the install succeeds, the browser lands somewhere else, and the smoke check raises
`"... has no chrome-headless-shell or chrome binary — puppeteer's postinstall did not leave a
browser there"` — a **false install failure** for a working install, which then interacts with CR-02
(the packages stay installed and the tool is `ALREADY_INSTALLED` next run).

Separately, the `chrome` fallback branch is Linux-shaped. On macOS the full browser's executable is
`Google Chrome for Testing` inside `chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/`,
not a file named `chrome`, so `rglob("chrome")` finds nothing. Today the primary
`chrome-headless-shell` branch covers macOS, so the fallback is simply dead there — but it is dead
in the one configuration (`PUPPETEER_SKIP_CHROME_HEADLESS_SHELL_DOWNLOAD`) where a fallback is what
you need. Every smoke test in `tests/test_executors.py` builds a `linux-*/chrome-*-linux64/` cache;
the registry ships `smoke = "puppeteer-browser"` on the macOS methods of both `puppeteer` and `mmdc`,
so the macOS path this phase ships has no test at all.

**Fix:** treat "no browser found in the location we know about" as *inconclusive* rather than as a
failure when a puppeteer config file is present, and add a macOS-layout case:

```python
def _plant_macos_browser(cache: Path) -> Path:
    app = cache / "chrome" / "mac_arm-140.0.7339.16" / "chrome-mac-arm64" \
        / "Google Chrome for Testing.app" / "Contents" / "MacOS"
    ...
```

matching the name puppeteer actually installs.

---

### WR-04: The `smoke` name is validated only after the install has already run

**Severity:** Medium
**File:** `installer/executors.py:248-252`, `tests/test_executors.py:754-764`

Every other `_node` parameter is validated before the side effect (`_opt_pkg_list`,
`_opt_version_map`, both floors). The `smoke` name is not:

```python
runner([pnpm, "add", "-g", *allowances, group])
smoke = method.params.get("smoke")
if smoke is not None:
    if not isinstance(smoke, str) or smoke not in SMOKE_CHECKS:
        raise ExecutorError(f"method '{method.kind}' unknown smoke '{smoke}'")
```

`test_unknown_smoke_raises_after_install` pins that ordering as intended behaviour, asserting
`calls == [[pnpm, "add", "-g", "x"]]`. A typo in a registry `smoke` name therefore performs a global
install and *then* fails it — leaving exactly the CR-02 state. `load_tools` catches this today, but
the executor is the last gate before argv and it is the gate that is out of order.

**Fix:** hoist the lookup above `runner(...)`:

```python
smoke = method.params.get("smoke")
if smoke is not None and (not isinstance(smoke, str) or smoke not in SMOKE_CHECKS):
    raise ExecutorError(f"method '{method.kind}' unknown smoke '{smoke}'")
...
runner([pnpm, "add", "-g", *allowances, group])
if smoke is not None:
    SMOKE_CHECKS[cast(str, smoke)]()
```

and change the test to assert `calls == []`.

---

### WR-05: `audit_node_globals` silently ignores its injected `managed` callable when a policy is supplied

**Severity:** Medium
**File:** `installer/pnpm_globals.py:381-413`

```python
if not policy.groups:
    packages = managed()
    ...
live = grouped()
```

`managed` and `grouped` are both injectable seams with real-subprocess defaults, and the second
branch drops `managed` on the floor without a word. `installer/app.py::run_doctor` injects
`managed=managed_globals` precisely so tests can answer for pnpm; the day that call site gains a
policy (which is the obvious next step for the console path — see WR-06), the injection stops
taking effect and the test suite starts spawning a real `pnpm list -g --json`. There is no
assertion anywhere that the two seams stay consistent.

**Fix:** make the redundancy impossible rather than silent — take one query seam and derive both
resolutions from it:

```python
def audit_node_globals(
    tools: Iterable[Tool],
    *,
    which: Callable[[str], str | None] = shutil.which,
    grouped: Callable[[], tuple[tuple[str, ...], ...] | None] = pnpm_global_groups,
    policy: NodeInstallPolicy = _EMPTY_POLICY,
) -> NodeGlobalsReport:
    # One query at the higher resolution; the flat set is a projection of it.
```

or, at minimum, raise when both `managed` and a non-empty policy are passed.

---

### WR-06: `make doctor` and the TUI Doctor now give different verdicts for the same machine, and the console says nothing about it

**Severity:** Medium
**File:** `installer/app.py:266`, `setup.py:260-263`

The divergence is deliberate and documented (`05-04-PLAN.md` acceptance criterion on `run_doctor`
source; verified here — `run_doctor` passes no policy, `split_groups` is always `()`, the group
query is never called, so there is no regression). But the *user-visible* consequence is that
`make doctor` prints a clean pnpm-globals section on a machine the TUI Doctor flags, and nothing in
the console output distinguishes "checked and healthy" from "not checked". That is the same
unknown-as-a-fact pattern the `known` flag was introduced to eliminate, one level up.

**Fix:** either wire the policy through (`run_doctor` already has `tools`; it is a one-line
`policy=node_install_policy(tools)`), or print an explicit line on the console path:

```
Install-group checks run in the interactive Doctor (`make setup`), not here.
```

---

### WR-07: The executor's parameter validation drops the rules that make a group spec safe

**Severity:** Medium
**File:** `installer/executors.py:46-79` vs `installer/model.py:70-110`

`model._parse_pkg_list` rejects empty and comma-bearing names, and `_parse_version_map` rejects
empty/comma-bearing keys *and* values, with the comment explaining exactly why: those strings land
on either side of an `@` inside a comma-joined group element, so a comma smuggles packages into a
group nobody declared. `executors._opt_pkg_list` and `_opt_version_map` re-validate the *types*
(list, str) and drop both content rules:

```python
for item in items:
    if not isinstance(item, str):
        raise ExecutorError(...)
    names.append(item)          # "" and "a,b" both accepted
```

The result reads as defence in depth at the last gate before argv, but is not: a `Method` built
anywhere other than `load_tools` produces `a,,b` or a smuggled group without complaint. Given that
this exact string becomes a `pnpm add -g` argument carrying `--allow-build` permissions, the last
gate is the one place the rule should not be weaker.

**Fix:** share one validator. Both modules already have the same shape — lift
`_parse_pkg_list` / `_parse_version_map` into a module `executors` may import (they do not depend on
anything in `model`), and call them from `_node`.

---

### WR-08: `_require_minimum` produces an ungrammatical message, and misdiagnoses a standalone-pnpm machine

**Severity:** Medium
**File:** `installer/executors.py:82-89`, `installer/executors.py:236-240`

Two problems in one function.

(a) When the version cannot be read, the message reads:

```
pnpm could not be read does not meet the required minimum 11.0.0. Upgrade pnpm to 11.0.0 or newer
before using this install method.
```

Fail-closed is right; the sentence is not, and it tells the user to upgrade when the actual problem
is that `--version` did not answer.

(b) The `min_node` floor probes bare `node`. pnpm's own recommended standalone install
(`get.pnpm.io/install.sh` → `@pnpm/exe`) bundles its own Node.js and does not require a system
`node`; on such a machine `probe_version(["node", "--version"])` returns `None` and the install is
refused with "node could not be read does not meet the required minimum 22.12.0", pointing the user
at the wrong thing. (`mmdc`'s bin shim does need a `node` on PATH at *run* time, so refusing is
arguably right — but the message must say "no `node` on PATH", not "upgrade node".)

**Fix:**

```python
def _require_minimum(binary: str, argv: list[str], minimum: str) -> None:
    observed = probe_version(argv)
    if observed is None:
        raise ExecutorError(
            f"could not read {binary}'s version (`{' '.join(argv)}` gave no answer). "
            f"This install method requires {binary} {minimum} or newer; install or repair "
            f"{binary}, then retry."
        )
    if not meets_minimum(observed, minimum):
        raise ExecutorError(f"{binary} {observed} is older than the required {minimum}. ...")
```

---

### WR-09: `node_install_policy` reads only the first `kind="node"` method per tool

**Severity:** Medium
**File:** `installer/pnpm_globals.py:160-161`, `installer/pnpm_globals.py:200-215`

```python
def _node_method(tool: Tool) -> Method | None:
    return next((method for method in tool.methods if method.kind == "node"), None)
```

`installer/executors.py` honours whichever method the *platform* resolved; the policy honours
whichever comes *first in the file*. For `puppeteer` those agree only because the entry repeats
`allow_build` / `versions` / `min_node` / `smoke` identically on both methods — an invariant
enforced by one tool-specific test (`test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`), not by
a general rule. A future entry that declares `co_install` only on its Linux method would install
correctly and be invisible to the Doctor's grouping, pinning and split detection, silently.

Related and lower-stakes: the policy merges params across *all* tools regardless of platform, so on
Linux/arm64 — where `puppeteer` resolves no method at all — the replay would still emit
`--allow-build=puppeteer` for a live `puppeteer`.

**Fix:** either fold every `kind="node"` method of a tool into the policy (union of `co_install`,
`allow_build`, `versions`, with a conflict raising rather than first-wins), or add a registry
integrity test asserting that all `kind="node"` methods of one tool declare identical
group/allowance/pin params.

---

### WR-10: `probe_version` is documented as a single seam it is not

**Severity:** Low
**File:** `installer/versions.py:97-114`, `installer/executors.py:17-22`, `installer/pnpm_globals.py:65-70`

```python
"""Single seam every runtime version read goes through.

No test and no production path can reach a real `pnpm --version` subprocess by accident..."""
probe_version: Callable[[list[str]], str | None] = _default_probe_version
```

Both consumers do `from installer.versions import probe_version`, binding the function object at
import time. Patching `installer.versions.probe_version` — the seam the docstring names — has no
effect on `installer.executors` or `installer.pnpm_globals`. The test suite already works around
this (every case patches `executors.probe_version` or `pnpm_globals.probe_version`), so the
docstring describes an affordance nobody can use and a future test that follows it will pass while
probing the real machine.

**Fix:** either import the module (`from installer import versions` … `versions.probe_version(...)`)
so the single seam is real, or delete the "single seam" wording and say that each consumer holds its
own binding, which is the patch point.

---

## Info

### IN-01: The closed smoke-name set is duplicated in two modules

**File:** `installer/model.py:11`, `installer/executors.py:154-156`

`SMOKE_CHECK_NAMES` (validation) and `SMOKE_CHECKS` (dispatch) are two literals held in sync by one
test (`test_smoke_checks_match_closed_name_set`). The import direction (`executors → model`)
prevents the obvious de-duplication. Acceptable as-is, but the model could import the name set from
a tiny leaf module rather than restating it.

---

### IN-02: `wizard_app`'s default preview does not match what `r` would run

**File:** `installer/wizard_app.py:1158-1160`

```python
def _default_preview(report: NodeGlobalsReport) -> str:
    return reinstall_preview(report.managed, known=report.known)   # no policy
```

Any `UnifiedApp` constructed with `node_globals` but without `globals_preview` shows a
space-separated preview while `reinstall_globals` (if also supplied) would run the grouped one —
the exact preview/effect divergence T-05-16 exists to prevent. Only `setup.py` wires both today, so
this is latent, but the default is the wrong shape for a guarantee stated in module docstrings.

---

### IN-03: The package-legitimacy gate leaves no re-runnable artefact, and T-05-05's checksum claim is stronger than the control

**File:** `.planning/phases/.../05-03-SUMMARY.md` (D5), `installer/registry.toml` (codegraph block)

The npm identity gate is described precisely in `05-03-PLAN.md` (exact-match normalization, hard
halt, `set -eu`) and its result is recorded, but it exists only as a one-off shell invocation — the
repository contains no script or test that can run it again, so "the gate must be able to FAIL" is
not a property anything can re-verify. Consider committing the check under `scripts/` and running it
in the registry test suite for every `kind="node"` entry.

For `codegraph`, T-05-05 dispositions "unverified binary download from GitHub Releases" as
*mitigated* by `checksum = "SHA256SUMS"`. `installer/download.py::_install_verified` fetches the
checksum file from the **same release** as the asset over the same HTTPS host, so it detects a
truncated or corrupted download, not a tampered or malicious release — the two artefacts share one
trust root. Combined with `resolve_github_tag` always resolving `releases/latest`, the recorded
"verified against v1.6.0" evidence describes a version that will generally not be the one installed,
and the entry has no fallback rung by design. This matches the pattern of other `github_release`
entries in the file, so it is noted rather than raised — but the register's wording should say
"integrity of the download", not mitigation of a tampered release.

---

### IN-04: `node_globals_guidance` joins group members with `" and "`

**File:** `installer/guidance.py:177`

`" and ".join(group)` renders "a and b and c" for a three-member group. Only two-member groups exist
today. Use an Oxford-style join, or `", ".join(...)` with the last element separated by "and".

---

### IN-05: `audit_node_globals`'s two branches duplicate the entries/missing computation

**File:** `installer/pnpm_globals.py:390-413`

```python
entries = tuple(entry for entry in node_globals(tools) if entry.npm_pkg in packages)
missing = tuple(entry.tool_id for entry in entries if which(entry.cmd) is None)
```

appears verbatim in both branches. Collapsing the branches to "resolve `packages` (and optionally
`live`), then compute the report once" would also make WR-05 impossible to reintroduce.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

---
---

# Second pass: independent cross-AI review (codex/gpt-5.6-sol)

Everything above this line is the INTERNAL reviewer (`gsd-code-reviewer`, CR-/WR-/IN- ids), and
its findings were closed in commits `70db936`..`66f92fc`.

The section below is a SEPARATE review of the same diff, run in parallel by
`codex/gpt-5.6-sol` at high reasoning effort. It uses its own `H`/`M` numbering. Some of it
corroborates the internal pass; the four items recorded here are the ones the internal pass did not
catch, or caught only partially. All four are fixed; none deferred.

Verification for the whole second pass: `make validate && make test` both pass on the exact tree at
`22cc967` — 1196 tests, 99.40% coverage, run in the main checkout (not an isolated worktree), so
the numbers reproduce from the tree as committed.

## H1: the puppeteer "smoke check" never launched a browser

**Severity:** High
**File:** `installer/executors.py` (`_smoke_puppeteer_browser`, and the cache-search helpers it used)
**Status:** FIXED — `c117e45`

**Issue.** The check ran `<executable> --version` and accepted any output. Verified live:
`PUPPETEER_EXECUTABLE_PATH=/bin/echo` passed it. `--version` returns before browser startup,
sandbox initialisation, profile creation and the DevTools connection — precisely the steps that
fail on a machine missing Chrome's shared libraries, which is the only failure the check exists to
catch. The binary it probed was also chosen by this project's own glob over the puppeteer cache
(highest parsed build, path string as tiebreaker), so it was not necessarily the browser puppeteer
would launch. Both the registry comment ("runs the browser that was actually downloaded", "the
check starts the browser") and the executor comment asserted behaviour the code did not have.

**Relation to the internal pass.** WR-02 (build comparison) and WR-03 (macOS bundle name) had both
hardened the cache search. That search is the thing H1 says should not exist: puppeteer's own
`launch()` resolves the browser, including `PUPPETEER_EXECUTABLE_PATH` and the `.puppeteerrc`
`cacheDirectory` that WR-03 recorded as an accepted residual. So this fix supersedes both — their
mechanism is deleted, and the residual WR-03 documented is closed rather than carried.

**Fix.** A bounded (`BROWSER_LAUNCH_TIMEOUT = 60.0`) node script that `require`s puppeteer, calls
`launch()`, opens a blank page and closes the browser. Module resolution under pnpm v11 goes
through the `puppeteer` bin shim's `cmd-shim-target` trailer, because `pnpm root -g` names a
directory with no `node_modules` of its own — each hash-keyed install group has one. `which` is
tried first and pnpm's own `bin -g` second, since PATH is not always current on a machine whose
pnpm was just set up. No resolvable root is not a failure: node then resolves `puppeteer` its own
way.

**Contract preserved.** The probe returns a reason string; only `_smoke_puppeteer_browser` turns it
into an `ExecutorError`. So CR-02's non-raising `run_smoke_check` dispatch still holds — an
unreadable shim, an unrunnable node or a timeout all become a Doctor FINDING, never an exception
escaping the audit.

**Residual, accepted and stated in code.** Because puppeteer resolves the browser, a machine that
already had a working Chrome can pass on that browser rather than on bytes this install wrote. That
is the correct answer to the question the tool cares about, and it is the same resolution mmdc
performs, so a pass here and a working mmdc do not come apart.

## H3: `PNPM_CO_INSTALL_MIN` was one minor version too low

**Severity:** High
**File:** `installer/versions.py`
**Status:** FIXED — `991910c`

**Issue.** The floor was `"11.0.0"`, justified by the pnpm v11 global-package redesign. That
redesign is the hash-keyed global layout; the shared-install-group semantics for a comma-separated
`pnpm add -g a,b` — the mechanism this phase's entire co-install path depends on — is an 11.1
feature. A machine on 11.0.x therefore cleared the preflight and then ran a comma spec pnpm does
not group, leaving the dependent unable to resolve its peer while the install reported success:
the exact silent misbehaviour the fail-closed preflight exists to refuse.

**Fix.** `PNPM_CO_INSTALL_MIN = "11.1.0"`. Both consumers share the one constant, so the install
path (`executors._node`) and the Doctor replay (`pnpm_globals.reinstall_node_globals`) moved
together. Boundary tests pin 11.0.9 as REJECTED and 11.1.0 as ACCEPTED on both paths, replacing the
old tests that asserted the 11.0.0 boundary. `05-01-SUMMARY.md` carries an in-place correction
note, since it recorded the wrong floor as shipped.

## M1: version parsing was not genuinely fail-closed

**Severity:** Medium
**File:** `installer/versions.py` (`parse_version`, `meets_minimum`)
**Status:** FIXED — `18b6866`

**Issue.** Two lenient behaviours in `parse_version` — the parser for OBSERVED `--version` output —
each produced the one answer a fail-closed gate must never produce, a false pass. Both reproduced
independently:

- A non-numeric component was zero-filled rather than refused, so `meets_minimum("11.bad",
  "11.0.0")` returned `True`.
- A prerelease suffix was cut off and the bare core returned, so `meets_minimum("11.0.0-rc.1",
  "11.0.0")` and `meets_minimum("22.12.0-rc.1", "22.12.0")` both returned `True`. An rc of the
  release that introduces a feature has not necessarily shipped it.

**Fix.** Unparseable input returns `None`, so the caller refuses exactly as it does when the command
could not be run. The prerelease suffix is parsed into a release rank rather than discarded, giving
`(major, minor, patch, rank)`: a prerelease sorts below its OWN release while `12.0.0-rc.1` still
clears an `11.1.0` floor. Rejecting prereleases outright — the other option the finding allowed —
was not taken, because refusing a machine that is genuinely past the floor is a different wrong
answer. Shape tolerance is unchanged where it is legitimate: `v24.4.0 (arm64)`, `1.2.3+build.5`,
`10.4` and a four-component `140.0.7339.16` all still parse.

`parse_declared_version` is untouched. A value the registry declares is a promise this project made
and can fix, so it stays held to the stricter shape a prior cycle gave it.

## M3: the package-legitimacy gate's assurance level was overstated

**Severity:** Medium
**File:** `.planning/phases/05-.../05-03-SUMMARY.md`, `installer/registry.toml`
**Status:** FIXED — `22cc967`

**Issue.** The summary claimed the gate "establishes IDENTITY AND OWNERSHIP ONLY". The
repository-URL and package-history checks read the SAME publisher-controlled npm registry record
the gate is validating, so a compromised account for this exact package name would keep the real
creation date and version history, could keep a `repository.url` pointing at the genuine upstream
project, and would pass unchanged.

**Fix.** Claim only, mechanism untouched. The gate is not a no-op — it has reachable failure paths
and it does refute the hypothesis the `SUS` flag raised (a new package or a typosquat with no
history and an unrelated repository field). The text now describes it as a metadata-consistency
check against the registry's own self-reported fields, explicitly silent on a takeover of an
established name. The same overclaim in the `registry.toml` comment justifying the persistent
`--allow-build=puppeteer` grant is corrected too, since that justification leaned on it.

---

_Second pass reviewed: 2026-09-05_
_Reviewer: codex/gpt-5.6-sol (high reasoning effort), independent of the internal pass_
_Fixes applied: 2026-09-05 — `991910c`, `18b6866`, `c117e45`, `22cc967`_
_Gate on the final tree: `make validate` clean, `make test` 1196 passed, 99.40% coverage_
