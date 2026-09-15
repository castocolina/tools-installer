---
phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
reviewed: 2026-09-14T00:00:00Z
depth: deep
files_reviewed: 11
files_reviewed_list:
  - installer/ownership.py
  - installer/install_ownership.py
  - installer/update.py
  - installer/version_status.py
  - installer/versions.py
  - installer/catalog_tui.py
  - installer/model.py
  - installer/registry.toml
  - installer/ui_common.py
  - installer/wizard_app.py
  - setup.py
findings:
  critical: 2
  warning: 10
  info: 5
  total: 17
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-09-14
**Depth:** deep (cross-file: ownership -> install_ownership -> update -> version_status -> catalog_tui -> setup.py)
**Files Reviewed:** 11 source files (+ 10 test files read for false-confidence checks)
**Status:** issues_found

## Summary

Diff base `c157844..HEAD` (commits `4ebcc88` through `eeef57d`). `make`-equivalent gates pass on the
tree as committed: `ruff check` clean, `vulture` clean, and the six most relevant test modules
(`test_ownership`, `test_install_ownership`, `test_update`, `test_versions`, `test_version_status`,
`test_registry`) are 289 passed. That is the floor, not the ceiling — the defects below are all
things the committed tests do not exercise.

The update-refusal gate itself is correct: `_perform`'s `NATIVE_OWNERS` branch sits above the
owner-dispatch ladder, returns before any `runner(...)`/`executors.execute(...)`/download call, and
`UpdateService.run` reaches it with no mutation of its own (the only pre-`perform_update` work is the
read-only `managed_packages()` pre-capture, gated on `tool.id == "pnpm"`). No native-owned tool can
reach a privileged package-manager subprocess. The rpm-ostree probe's subprocess handling is also
sound in the injection sense: fixed argv lists, no shell, `check=True`, `stdin=DEVNULL`, `timeout=5`,
and the JSON walk is defensively typed with `isinstance` at every hop.

The two blockers are about *attribution correctness*, which is the one thing this phase declared in
scope. `_native_owner` hands out mutation-grade `direct` confidence on evidence that the module's own
docstring says must force `unknown` (a contradictory live PATH entry), and the `_dnf` probe cannot
tell a base-image RPM from a dnf-installed one, so on the exact ostree platform this phase targets
(Bazzite/Silverblue) tools like `git` and `jq` get labelled "managed by dnf" with remediation advice
that cannot be followed. Both are currently contained by the refusal gate — but the refusal gate is
the *only* thing containing them, and the ownership module is explicitly documented as feeding "a
mutating action that runs with no confirmation".

## Critical Issues

### CR-01: `_native_owner` claims `direct` ownership over a contradictory live PATH entry

**File:** `installer/ownership.py:356-368` (call site), `installer/ownership.py:424-480` (`_native_owner`)
**Severity:** BLOCKER

**Issue:** The module docstring (`installer/ownership.py:22-32`) states the invariant this design rests
on verbatim:

> A live, unattributable active path is checked and can force `unknown` BEFORE the by-elimination
> branch is ever reached, so by-elimination can never override contradictory live-PATH evidence.

The new adapter is deliberately inserted *above* that check (line 366, before the `if active_path is
not None: return _unknown(...)` at 369). Its own comment justifies the placement — correctly, in that
the feature would never fire otherwise — but it then hands back `confidence="direct"` (a
`MUTATION_GRADE` value) with `shadowed=False`, `active_candidate=None` and `unknown_reason=None`,
*regardless of where the live binary actually is*. The comment at 468-471 claims "nothing here should
overstate the evidence"; it does exactly that.

Reproduced against the committed tree (jq installed by dnf in `/usr/bin`, plus a hand-built copy
earlier in PATH):

```
owner: dnf | confidence: direct | shadowed: False
active_path: /home/me/bin/jq | active_candidate: None
unknown_reason: None
probe calls: [['rpm', '-q', '--qf', '%{NAME}\\n', 'jq']]
```

Pre-phase this resolved to `unknown` with `"the active binary at /home/me/bin/jq is not attributable
to any candidate"`. Two consequences:

1. **User-visible regression.** The honest "the live copy is not the one any manager claims" message
   is replaced by the flat assertion "managed by dnf — this installer will not update it"
   (`catalog_tui.py:403-406`). The user is told the wrong thing about which binary they are running.
2. **Latent mutation risk.** `direct` clears `MUTATION_GRADE`. The only thing stopping a wrong-binary
   mutation today is `update.py`'s `NATIVE_OWNERS` refusal. The moment anyone adds a native update
   path (the docstring at `ownership.py:17-20` frames the refusal as a scope decision, not a
   permanent one), this becomes a privileged `dnf upgrade` justified by evidence about a package that
   does not own the live executable.

The committed test `test_native_owner_resolves_from_unattributable_live_path` pins `active_path ==
Path("/usr/bin/jq")` — the case where the guess happens to be right — and nothing pins the case where
it is wrong.

**Fix:** Do not claim ownership when a live active path exists that the claimed package does not own.
Either (a) verify path ownership with the manager's own file-query — `rpm -qf`, `dpkg -S`,
`pacman -Qo` — before returning a claim, or (b) at minimum refuse to claim when `active_path` is not
`None` and is not owned by the package, falling through to the existing `_unknown` branch:

```python
def _native_owner(
    tool: Tool,
    probe: ProbeRunner | None,
    candidates: tuple[OwnershipCandidate, ...],
    unreadable: frozenset[Owner],
    active_path: Path | None,
) -> ManagerOwnership | None:
    if probe is None or candidates or unreadable:
        return None
    verified = detect_owner(tool, probe)
    ...
    # A live binary the claimed package does not own is contradictory evidence,
    # exactly as it is for the by-elimination branches below.
    if active_path is not None and not _package_owns_path(verified, active_path, probe):
        return None
```

If (a) is judged out of scope, the claim must at least be downgraded so it cannot be mistaken for
proof: keep the `unknown_reason` about the unattributable live path, and do not emit a
`MUTATION_GRADE` confidence for a path-contradicted claim.

---

### CR-02: Base-image RPMs on ostree hosts are attributed to `dnf`, with un-followable remediation

**File:** `installer/install_ownership.py:111-116` (`_dnf`), `installer/install_ownership.py:119-164`
(`_rpm_ostree`), `installer/registry.toml:86-90` (the ordering comment), `installer/update.py:96-109`
(the refusal wording)
**Severity:** BLOCKER

**Issue:** `_rpm_ostree` only claims a package present in the booted deployment's
`requested-packages` — i.e. *explicitly layered*. Every package that ships in the base image
(`git`, `jq`, `zsh`, `procps-ng`, `podman` on Bazzite/Silverblue) is **not** in `requested-packages`,
so `_rpm_ostree` returns `None` and the very next probe, `_dnf`, runs `rpm -q <pkg>` — which
succeeds, because the deployment's rpmdb contains the whole base image. Result on an ostree host:

- catalog detail line: `managed by dnf — this installer will not update it` (`catalog_tui.py:403`)
- update refusal detail: `dnf owns this tool; this installer does not perform privileged
  system-package updates, so update it through dnf yourself` (`update.py:106-109`)

Neither is true. dnf is not the package manager of record on an atomic host — the codebase already
knows this: `platform.immutable` exists (`installer/platform.py:23,52-54`), `resolve._applies`
returns `False` for dnf/apt/pacman when `platform.immutable` (`resolve.py:75-76`), and
`detect_os`'s own docstring says Bazzite "may expose rpm-ostree rather than a usable dnf". The user
is being told to run a command that does not manage that package.

The registry comment added by this phase overstates what the probe ordering achieves:

> rpm-ostree is listed FIRST on every dnf/apt/pacman-capable row below: on an ostree host the rpm
> database still answers `rpm -q`, so probing dnf first would attribute a package the user explicitly
> layered with rpm-ostree to the wrong mechanism.

Ordering only fixes the *layered* case. The base-image case — the overwhelmingly common one for
`git`/`jq`/`zsh`/`podman`, and the case that applies to this project's own primary dev host — falls
straight through to `_dnf` and is mis-attributed anyway. No test covers an ostree host whose booted
deployment lists the package under `packages` but not `requested-packages`.

**Fix:** `_dnf` must not answer on an immutable host. The cleanest shape given the existing probe
signature is to make `_rpm_ostree` authoritative on ostree systems and let `_dnf` stand down:

```python
def _rpm_ostree(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    ...
    for package in packages:
        if package in layered_names:
            return Ownership("rpm-ostree", "verified", f"rpm-ostree layers {package}")
    base = booted.get("packages")
    if isinstance(base, list) and any(pkg in cast(list[object], base) for pkg in packages):
        # Base-image package: still rpm-ostree's to update (via the image), never dnf's.
        return Ownership("rpm-ostree", "verified", f"rpm-ostree base image contains {package}")
    return None
```

and/or gate `_dnf` on `not platform.immutable` by threading `Platform` into the probe table. At
minimum, the `_NATIVE_OWNER_DETAIL` wording must stop naming a concrete command the user cannot run
on that host, and the `registry.toml` comment must stop claiming the ordering solves the ostree case.

## Warnings

### WR-01: `action_update_tool` has no `NATIVE_OWNERS` pre-check — the refusal costs a full worker plus a second probe sweep

**File:** `installer/catalog_tui.py:566-593` (see the gate at 582), import at `installer/catalog_tui.py:23`
**Severity:** WARNING

**Issue:** The screen imports `MUTATION_GRADE` but not `NATIVE_OWNERS`, so a native-owned row passes
the pre-flight gate (`direct` ∈ `MUTATION_GRADE`), takes the in-flight latch, spawns the update
worker, and inside the worker `UpdateService.run` re-resolves ownership from scratch — which re-runs
`rpm-ostree status --json` and `rpm -q` subprocesses — only for `_perform` to refuse. The user waits
on a worker for a decision that was knowable synchronously, and the app performs a redundant probe
sweep every keypress.

**Fix:** Refuse in the same place the `unknown` refusal already lives:

```python
from installer.ownership import MUTATION_GRADE, NATIVE_OWNERS
...
if ownership.owner in NATIVE_OWNERS:
    self.status.set(
        f"cannot update {tool_id}: {ownership.owner} owns it; "
        f"update it through {ownership.owner}", "warn",
    )
    return
if ownership.owner == "unknown" or ownership.confidence not in MUTATION_GRADE:
    ...
```

`update.py`'s branch stays as the authoritative backstop.

---

### WR-02: `_strip_name_prefix` accepts an empty name prefix, so `-1` / `--2` now parse as versions

**File:** `installer/versions.py:54` (`_NAME_PREFIX_BOUNDARY`), `installer/versions.py:57-66`
**Severity:** WARNING

**Issue:** `.*[-\s](?=[vV]?\d)` allows `.*` to match the empty string, so the "name prefix" being
stripped can be nothing but punctuation. Verified against the committed tree:

```
'--2'          -> parse_version: (2, 0, 0, 1)   extract_observed_version: '--2'
'-1'           -> parse_version: (1, 0, 0, 1)   extract_observed_version: '-1'
'release-2024' -> parse_version: (2024, 0, 0, 1)
```

All three returned `None` before this change. `extract_observed_version` (`versions.py:170-180`)
scans *every whitespace token of the whole stdout* and returns the first that parses, so a tool that
doesn't support `--version` and prints a usage line containing a `-1`/`-2` flag, or any output
containing a `word-<year>` token, now yields a fabricated "installed version" that is then compared
against the real latest by `is_outdated`. The docstring's own claimed safety property
("Widening the boundary character class ... would reintroduce the free-substring-search
false-positive risk this mechanism was chosen over") does not hold for the empty-prefix case.

**Fix:** Require at least one identifier character in the prefix being stripped:

```python
# `.*` must consume at least one non-boundary character, so a bare `-1`/`--2`
# token is never treated as a glued `<name>-<version>`.
_NAME_PREFIX_BOUNDARY = re.compile(r".*[0-9A-Za-z_.+][-\s](?=[vV]?\d)")
```

and add a regression case for `"-1"`, `"--2"` and `"release-2024"` to `tests/test_versions.py`.

---

### WR-03: the glued token is displayed verbatim — the catalog will show `jq-1.8.1`, not `1.8.1`

**File:** `installer/versions.py:170-180`, rendered at `installer/catalog_tui.py:303-315`
**Severity:** WARNING

**Issue:** `extract_observed_version` returns the *token*, not the parsed core, and
`VersionStatus.installed` is that raw string. Verified: `extract_observed_version("jq-1.8.1")` ->
`'jq-1.8.1'`. The version column therefore renders `jq-1.8.1 -> 1.8.2`. Comparison is correct
(`parse_status_version` strips the prefix), so this is display-only — but it is the user-facing half
of the bug this plan set out to fix, and it was left inconsistent with every other row.

**Fix:** Return the normalized segment when the direct match failed, e.g. have
`extract_observed_version` return `_strip_name_prefix(token)` for the fallback path, or expose a
`normalize_observed_version(token)` helper and call it at the one display site.

---

### WR-04: probes run per-tool with no memoization and no platform gate, inside the blocking refresh

**File:** `installer/ownership.py:366` (per-tool call), `installer/install_ownership.py:30-39`
(`run_probe`, `timeout=5`), `installer/version_status.py:519-529` (the loop)
**Severity:** WARNING

**Issue:** `VersionRefreshService.refresh` calls `resolve_ownership` per tool, and every tool with no
tracked candidate now reaches `detect_owner`, which walks *all* declared `owner_probes`. For the ten
native rows that is up to four subprocesses each — `rpm-ostree status --json`, `rpm -q`,
`dpkg-query -W`, `pacman -Qq` — with a 5 s timeout apiece and no caching between tools. `rpm-ostree
status` in particular is a D-Bus call into `rpm-ostreed` that blocks while a transaction is in
flight; eight sequential invocations can add ~40 s to a refresh in the worst case. There is also no
platform gate: on macOS the adapter still attempts `rpm-ostree`/`rpm`/`dpkg-query`/`pacman` for every
unattributed tool. This is a robustness issue (a stalled daemon stalls the whole refresh worker),
not a micro-optimisation.

**Fix:** Resolve `rpm-ostree status --json` (and the other whole-inventory reads) **once per refresh**
and pass the parsed result down, the same way `ManagerInventory` already does for brew/pnpm/uv; and
skip probes whose manager cannot apply to `platform.os`.

---

### WR-05: probes execute unqualified command names resolved through the user's PATH — newly reachable in production

**File:** `installer/install_ownership.py:30-39`, `65`, `93`, `103`, `113`, `138`, `169`, `193`, `209`
**Severity:** WARNING

**Issue:** Every probe argv starts with a bare name (`rpm-ostree`, `rpm`, `dpkg-query`, `pacman`,
`brew`, `pnpm`, `sdk`, `tools-installer-managed-download`), resolved via `PATH`. Before this phase
`detect_owner` had **zero production callers** (verified: `git grep detect_owner c157844 -- installer/
setup.py` matches only its own definition) — the whole module was exercised only by tests. Phase 15
promoted it to a production execution path that now runs on every catalog refresh, so a PATH-planted
`rpm-ostree`/`rpm` executable is newly executed by this installer. That matters more here than in a
typical program because this very installer *prepends a managed bin dir to the user's PATH* by
design. Its stdout is then fed straight to `json.loads` (`install_ownership.py:142`, `197`), whose
`RecursionError` on deeply nested input is not among the caught exceptions
(`except (TypeError, ValueError)`), so a hostile probe can crash the refresh worker.

**Fix:** Resolve probe binaries to absolute paths from a trusted prefix list
(`/usr/bin`, `/bin`, `/usr/sbin`) before invoking, or at minimum run them with a sanitized
`env={"PATH": "/usr/bin:/bin:/usr/sbin"}` in `run_probe`, and add `RecursionError` to the
`json.loads` guard.

---

### WR-06: the adapter discards verified non-native evidence, then lets the by-elimination branches run as if none existed

**File:** `installer/ownership.py:445-453`
**Severity:** WARNING

**Issue:** `_native_owner` calls the *full* `detect_owner`, which may return a verified
`"Homebrew"`/`"pnpm"`/`"SDKMAN"`/`"managed download"` claim — and then throws it away and returns
`None`. Control falls through to the `len(candidates) == 1` and synthetic-script by-elimination
branches below, whose entire premise is "nobody else claims this tool". For `pi`
(`owner_probes = ["host-setup"]`) the probe really does run `pnpm list --global --depth 0 --json` and
can verify pnpm ownership, and that verified answer is dropped on the floor while the tool resolves
`unknown`. The comment at 450-452 asserts those managers "have their own evidence path elsewhere in
this module" — true for brew/pnpm/uv when the inventory is readable, false for `host-setup` and
`managed-download`, which have no other path at all.

**Fix:** Either restrict what is asked (dispatch only the native probe names rather than the whole
`owner_probes` list), or use the non-native verified result as a *negative* signal that suppresses the
by-elimination branches below. Asking a question and discarding the answer is the worst of both.

---

### WR-07: the `managed-download` probe shells out to a binary that does not exist

**File:** `installer/install_ownership.py:62-68`
**Severity:** WARNING

**Issue:** `_managed_download` runs `["tools-installer-managed-download", "list", tool.id]`. That name
appears nowhere in this repository other than the probe itself and its test double — it is not built,
not installed, and not on any PATH. While `detect_owner` was test-only this was inert; Phase 15 made
it live, so `drawio-desktop` and `drawio-cli` (both `owner_probes = ["managed-download"]`) now fork a
doomed `FileNotFoundError` subprocess on every ownership resolution, forever returning "no verified
manager". This is dead code masquerading as a working probe — `.claude/architecture.md` rule 5
("No orphan helpers ... Only its own test keeping it covered is the tell") is exactly this shape.

**Fix:** Either implement the artifact-ledger read this probe is standing in for (the data is already
available via `plan_uninstall`/artifact paths that `resolve_ownership` uses), or delete `_managed_download`,
`"managed-download"` from `OWNER_PROBES`, and the two registry rows that opt into it.

---

### WR-08: the setup.py wiring test asserts a substring count, not behavior

**File:** `tests/test_setup.py:1427-1434`
**Severity:** WARNING

**Issue:**

```python
source = Path(setup.__file__).read_text()
assert source.count("native_probe=") == 2, source.count("native_probe=")
```

This passes if both call sites pass `native_probe=None`, passes if one of the two occurrences is in a
comment, and fails the moment anyone adds a third legitimate call site or writes the token in a
docstring. It asserts nothing about whether the probe actually reaches `resolve_ownership`. The
comment above it correctly identifies the constraint (setup.py is excluded from pyright/coverage) but
draws the wrong conclusion — the fix for an untestable composition root is to shrink it, not to grep it.

**Fix:** Move the two constructions into a testable factory in `installer/` (per
`.claude/architecture.md` rule 4, "`setup.py` is wiring only ... any decision function belongs in
`installer/`") and assert on the constructed objects, e.g. that
`VersionRefreshService(...)._native_probe is run_probe`.

---

### WR-09: the AI-tab test scrapes module source with positional `split()`

**File:** `tests/test_ui_common.py:278-334`
**Severity:** WARNING

**Issue:** `source.split('name="ai"')[1].split("palette=")[0]` will `IndexError` (not fail with a
useful message) if the row is reformatted, reordered, or if `name="ai"` ever appears twice; the
`english_collisions` set and the "ids of 5+ characters" heuristic are hand-maintained magic that will
silently stop covering new short ids. Imports are also inside the test function body rather than at
module top. The underlying intent (a comment that cannot drift from the registry) is good; the
mechanism is a source-text scraper that will rot into either a false pass or a confusing crash.

**Fix:** Move the citation list out of the comment into data the test can read directly — e.g. a
`examples: tuple[str, ...]` field on the `View` row, asserted against `tool.tier` — so the assertion
is over structured values instead of over the file's formatting.

---

### WR-10: `resolve_status` has no branch for the four new owners; a native-owned tool silently lands in the `unknown` fallback

**File:** `installer/version_status.py:224-336` (fallback at 324-336)
**Severity:** WARNING

**Issue:** `resolve_status` dispatches on `owner == "installer"` and `owner in ("brew", "cask",
"pnpm", "uv")`. The widened `Owner` type added four values and no branch, so `dnf`/`apt`/`pacman`/
`rpm-ostree` fall through to the terminal `VersionStatus(..., source="unknown", stale=True)`. The row
therefore records `source="unknown"` for a tool the detail line simultaneously labels "managed by
dnf", and is flagged perpetually stale. Nothing crashes, but the fall-through is implicit: there is
no comment marking it as the intended destination for native owners, and no test pins it — so the
next person to widen `Owner` gets the same silent landing with no signal.

**Fix:** Add an explicit branch (or at minimum an explicit comment plus a pinning test) so a native
owner's status is a deliberate `source=owner, latest=None` record rather than an accident of the
`if`-ladder falling off the end.

## Info

### IN-01: two spellings of the same manager across the schema

**File:** `installer/model.py:35` (`"rpm_ostree"` in `METHOD_KINDS`) vs `installer/model.py:62` and
`installer/ownership.py:68,80` (`"rpm-ostree"` in `OWNER_PROBES`/`Owner`/`NATIVE_OWNERS`)
**Issue:** The same manager is `rpm_ostree` as a method kind and `rpm-ostree` as a probe/owner name.
`_rpm_ostree`'s docstring already has to spend a paragraph explaining that it reads the `dnf` method's
package because no row declares the `rpm_ostree` kind.
**Fix:** Pick one spelling and normalize at the registry-parse boundary.

### IN-02: the owner-label table is rebuilt on every row render

**File:** `installer/catalog_tui.py:389-406`
**Issue:** The `labels` dict is a literal inside `_version_detail`, re-allocated per row per refresh,
and its four new keys are kept in sync with `NATIVE_OWNERS` by a comment rather than by construction —
the exact drift `NATIVE_OWNERS` was introduced to prevent (`ownership.py:75-79`).
**Fix:** Hoist to a module constant and assert `set(NATIVE_OWNERS) <= set(_OWNER_LABELS)` in a test.

### IN-03: unreachable `TypeError` in the JSON guard

**File:** `installer/install_ownership.py:141-144`
**Issue:** `output` is `str | None` and the `None` case already returned at line 139-140, so
`json.loads(output)` can only raise `JSONDecodeError` (a `ValueError`). `TypeError` is unreachable.
`RecursionError` — which *is* reachable on hostile input (see WR-05) — is not caught.
**Fix:** `except ValueError:` plus `RecursionError`.

### IN-04: comment-to-code ratio, and comments that cite review artifacts

**File:** `installer/ownership.py:356-365,431-471`, `installer/versions.py:31-54`,
`installer/install_ownership.py:120-134`, `installer/update.py:96-109,241-247`
**Issue:** Several blocks run 15-30 lines of rationale over 5-10 lines of code, and some cite
transient artifacts — `"(Round 1 review, L160@ab432e9)"` (`catalog_tui.py:396-398`),
`"15-RESEARCH.md's Pattern 3 sketch"` (`ownership.py:358`), `"D-05/T-15-15"` (`update.py:241`),
`"Verified 2026-09-14 ... during this phase's research"` (`versions.py:31`). These will be unresolvable
once the phase directory is archived, and the "verified live this session" claims cannot be re-checked
by a future reader.
**Fix:** Keep the invariant, drop the provenance; move the archaeology to the commit message or the
phase SUMMARY, which is where it is already recorded.

### IN-05: `_NATIVE_PACKAGE_MANAGER_KINDS` still omits `rpm_ostree`

**File:** `installer/ownership.py:73`, used at `installer/ownership.py:642`
**Issue:** The rewritten module docstring now says all four kinds are in scope, but the frozenset that
drives `_unknown_reason`'s "likely installed via the OS package manager (dnf/apt/pacman)" message still
lists three, and the message text still enumerates three. Harmless today (no row declares the
`rpm_ostree` kind) but it is the drift `NATIVE_OWNERS` centralization was supposed to end.
**Fix:** Derive the message from a single source, or drop the unused kind from the docstring's claim.

---

_Reviewed: 2026-09-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
