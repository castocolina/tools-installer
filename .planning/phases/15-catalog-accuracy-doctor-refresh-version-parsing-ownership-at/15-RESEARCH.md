# Phase 15: Catalog Accuracy — Doctor Refresh, Version Parsing, Ownership Attribution, Tier Fixes - Research

**Researched:** 2026-09-14
**Domain:** Four independent "the catalog/doctor shows something untrue" bugs in a Python/Textual TUI installer: a Doctor-screen stale-render bug, a version-string parsing gap, a disconnected ownership-detection module, and registry tier-classification errors.
**Confidence:** HIGH — every claim below is a direct `Read` of the live tree this session, a live subprocess run on this actual machine (Bazzite 44.20260914), or a direct read of the existing test suite; no WebSearch was needed for any of the four bugs.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Doctor refresh**
- **D-01:** `action_apply` calls `self._refresh_guidance()` (not just `self._refresh_body()`) after a fix succeeds, so the guidance list reflects the new state before rendering. — **Reversibility:** reversible.
- **D-02:** A note explaining the PATH check's deliberately-frozen state appears **conditionally**, only when `self.applied` is `True` — e.g. "PATH check still reflects the pre-fix state — this is expected until you open a new shell or source `~/.myshellrc`." It does not show before the fix is applied (nothing frozen to explain yet). — **Reversibility:** reversible.

**Version parsing**
- **D-03:** `_OBSERVED_VERSION`'s matching gains a name-prefix split: when the raw token doesn't match directly, split at the last `-` (or whitespace) immediately preceding a segment that starts with a digit or `v`/`V`, and apply the existing regex to that trailing segment only. This is a generic mechanism, not a per-tool prefix table — no registry schema change. — **Reversibility:** reversible.
- **D-04:** After the fix, audit `installer/registry.toml` for other tools whose `--version` output plausibly has a similar non-bare-semver shape, and confirm the new split logic covers them (or note any that still need special-casing). — **Reversibility:** reversible.

**Ownership wiring**
- **D-05:** `installer/ownership.py`'s live resolution path calls `install_ownership.py::detect_owner` for the `dnf`/`apt`/`pacman` cases, adapting its `"verified"` confidence to `ownership.py`'s own `MUTATION_GRADE` vocabulary as `"direct"` — no duplicate probe logic is written inside `ownership.py`, per that module's own docstring rationale and `.claude/architecture.md` rule 5 (no duplicate helpers). — **Reversibility:** costly — later separating the two confidence vocabularies again would mean re-touching every call site that now expects the adapted value.
- **D-06:** A new rpm-ostree/just-layering probe is added to `install_ownership.py`, following the exact pattern of the existing `_dnf`/`_apt`/`_pacman` probes (a `ProbeRunner`-injected command, e.g. `rpm-ostree status --json`), and wired through the same D-05 adapter — not deferred to a future phase. — **Reversibility:** reversible.

**Tier fixes**
- **D-07:** `ast-grep`: `tier = "user"` → `tier = "ai"` (same family as `rg`/`fd`, already `ai` — a structural-search tool typically invoked by an agent, not typed by the human). — **Reversibility:** reversible.
- **D-08:** `puppeteer`: `tier = "user"` → `tier = "ai"` (a runtime library dependency of `mmdc`, never launched directly by the human — matches the `ai`-tier definition's "operates underneath ... never launched directly by the human as their own interface"). — **Reversibility:** reversible.
- **D-09:** `mmdc`, `gitleaks`, `vale`, `drawio-cli` stay `tier = "user"` — reviewed against `.claude/architecture.md`'s tier criterion and confirmed correct as-is: each is directly invoked by the human on their own artifact (diagram, repo scan, prose, export), not infrastructure "consumed by" an agent underneath. This closes the "borderline" review named in ROADMAP.md — no further tier review deferred. — **Reversibility:** reversible.
- **D-10:** Fix `installer/ui_common.py`'s stale AI-tab comment (~line 130) — it still names `claude`/`codex` as examples of agent CLIs in the `ai` tab, but both are `tier="user"` since an earlier session. Update the comment's examples to tools that are actually `tier="ai"` today (e.g. `rg`, `fd`, `codegraph`). — **Reversibility:** reversible.

### Claude's Discretion
- Exact wording of the D-02 PATH-frozen note (as long as it makes the "expected, not broken" framing explicit).
- Which specific `ai`-tier tools to cite as the corrected examples in the D-10 comment fix.
- The exact command/flags used by the D-06 rpm-ostree probe (e.g. `rpm-ostree status --json` vs `rpm-ostree status -b` parsing) — implementation detail, not a user-facing decision.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. The "borderline" tier review (`mmdc`/`gitleaks`/`vale`/`drawio-cli`) that might have been deferred to a future phase was instead resolved now (D-09), closing it rather than leaving it open.
</user_constraints>

## Project Constraints (from CLAUDE.md)

- **uv only** — never `pip`/`poetry`/`conda`/a hand-rolled venv. This phase adds no dependencies, so this is a non-issue, but any Wave-0 tooling additions must go through `uv add`.
- **English only** in every response, identifier, comment, docstring, log line, and commit message.
- **Never bypass a quality gate.** No `# noqa`/`# type: ignore`/`# nosec`/vulture-whitelist to silence a finding this phase's own changes introduce — this matters concretely below, since `Owner`'s `Literal` type must be widened rather than cast/ignored (see Pattern 3).
- **Coherent commits** — no "fix review comment" pile-ups; amend/squash so each commit is one self-contained, valid change.
- **Validate before commit:** `make validate && make test` must pass on the exact tree about to be committed (`.claude/testing.md`'s "Definition of done").
- `ruff check`/`ruff format`/`pyright --strict`/`bandit`/`vulture` all run via `make validate`; pyright strict means every new function this phase adds (the version-parsing fallback, the ownership adapter, the rpm-ostree probe) needs full type annotations, no implicit `Any`.
- Test rules: no `@pytest.mark.skip`/`xfail` to dodge a self-caused failure; `make test`'s coverage floor (`fail_under = 90`, see Validation Architecture) must not drop.

## Summary

This phase bundles four genuinely independent bugs, each already root-caused with high confidence by reading the live tree and, in three of the four cases, by running the real tool/probe live on this actual development machine (a real Bazzite host) this session. None of the four requires a new third-party dependency.

**Bug 1 (Doctor stale guidance):** `DoctorScreen.action_apply` (`installer/wizard_app.py:389-394`) calls `self._refresh_body()` but never `self._refresh_guidance()` after a successful fix — confirmed by direct read. The nuance the planner needs: `self._report` (the `DoctorReport` driving `doctor_guidance`'s "not on PATH" findings) is a **process-lifetime, build-time snapshot** — computed once in `setup.py::_build_app` from `os.environ.get("PATH", "")` (`setup.py:389-395`) and never re-audited — so calling `_refresh_guidance()` after the fix produces **byte-identical** `doctor_guidance()` output for the PATH-audit portion specifically (the snapshot cannot change without a new process). D-01 is still the correct fix (it is the invariant every OTHER guidance-affecting event in this screen already follows — `on_mount`, `enter_view`, `on_globals_audited` all call both refreshers together; `action_apply` is the sole outlier), but the *visibly fixed* half of the bug is D-02's conditional note, not a change in guidance content. Both are locked decisions; this research documents the distinction so a plan or a test does not falsely expect the PATH-missing finding to disappear after a successful fix.

**Bug 2 (version parsing gap):** `_OBSERVED_VERSION` (`installer/versions.py:29`) is `fullmatch`-anchored and requires the token to *start* with `[vV]?\d`. `jq --version` prints `jq-1.8.1` as one whitespace-delimited token [VERIFIED: live `jq --version` this session → `jq-1.8.1`], which never matches, so `jq` always reports "unknown." A live audit of every installed, testable tool in `installer/registry.toml` this session (≈50 tools run with `--version` on this machine) found **exactly one** tool with jq's precise shape (a bare name glued directly to its version with a `-` and no separating whitespace): `jq` itself. The audit also surfaced two adjacent, genuinely different parsing gaps that D-03's specific mechanism does **not** fix (see Pitfall 2) and one pre-existing, unrelated **false-positive** parse (wezterm/cursor-agent's date-or-hash-shaped "versions" already parse "successfully" into meaningless major-version numbers under the *current*, unmodified regex — not a regression this phase introduces, but worth flagging for the planner as a pre-existing landmine outside this phase's stated scope).

**Bug 3 (ownership detection disconnected):** More severe than CONTEXT.md's framing suggests: `install_ownership.py::detect_owner` has **zero production call sites** today (a repo-wide grep finds it referenced only from `tests/test_install_ownership.py`) — it is not merely "disconnected from the live path," it is entirely dead production code, kept alive only by its own test. Wiring D-05 requires three coordinated changes, not one: (1) an adapter call site inside `installer/ownership.py::resolve_ownership`, (2) widening the closed `Owner` `Literal` type (`installer/ownership.py:61`) to include the new native-manager owner names — the adapter cannot assign `owner="dnf"` to a field typed `Literal["installer", "brew", "cask", "pnpm", "uv", "unknown"]` without this, and `pyright --strict` will reject it, and (3) a **new, explicit refusal branch inside `installer/update.py::_perform`** for these new owner values — omitting this turns a clean "cannot update: likely installed via the OS package manager" pre-flight refusal into a confusing `UpdateOutcome(status="failed", detail="unsupported owner 'dnf'")` runtime exception the instant `confidence="direct"` (D-05's own locked mapping) lets a native-manager-owned tool past the `MUTATION_GRADE` gate. This last point is a real regression risk this research surfaces prominently in Common Pitfalls and Security Domain — dnf/apt/pacman package updates typically require root, and this installer has never needed privilege escalation before.

D-06's rpm-ostree probe is well-grounded: `rpm-ostree status --json`, run live on this actual Bazzite host this session, returns a `deployments` array where the booted deployment carries a `"booted": true` field and a `"requested-packages"` array of explicitly layered package names [VERIFIED: live `rpm-ostree status --json | jq` this session]. No registry tool declares a `kind = "rpm_ostree"` method today (0 matches; `installer/resolve.py:70-73`'s `_applies` unconditionally returns `False` for that kind by design — it is skipped as an *install* method, never as an *ownership probe*), so the new probe must reuse the tool's already-declared `dnf`-method package name (the same `_method_values(tool, {"dnf"}, "package")` `_dnf` already reads), not a new registry field.

**Bug 4 (tier misclassifications):** All four decisions verified directly against the live registry. `ast-grep` (`registry.toml:1834-1842`, `category="search"`, `tier="user"`) sits beside `rg`/`fd` (`registry.toml:81-88`, `167-174`, same `category="search"`, `tier="ai"`) — the inconsistency is exact and literal. `puppeteer` (`registry.toml:2399-2413`) already carries the giveaway in its own `desc` field: `"Required at runtime by mmdc."` — textbook `ai`-tier ("operates underneath ... never launched directly by the human"). Fixing these two tips over two pinned tests: `tests/test_registry.py:584` (`test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`, whose *name* — not just its assertion — encodes the wrong tier) and `tests/test_registry.py:928-936` (`test_registry_tier_distribution_is_pinned`, an explicit tripwire pinning `{"system": 26, "ai": 15, "user": 48}` that becomes `{"system": 26, "ai": 17, "user": 46}`). D-10's stale comment is at `ui_common.py:129-134`, confirmed verbatim below.

**Primary recommendation:** Fix all four independently (they touch disjoint files with one shared test-fixture concern — `tests/test_wizard_app.py`'s `_app()` helper is Doctor-only). Sequence Bug 3 last if waves are used: its `Owner`-widening and `update.py::_perform` refusal-branch work is the highest-risk, most cross-cutting change of the four, and Bugs 1/2/4 have zero interaction with it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Doctor guidance/body rendering (Bug 1) | Textual TUI (`installer/wizard_app.py::DoctorScreen`) | Backend/core (`installer/guidance.py`, IO-free) | The screen owns *when* to refresh and *what* to append conditionally on `self.applied`; the pure `Guidance` list itself is unaffected — this is a pure rendering-sequencing bug, not a decision-logic bug. |
| Version string parsing (Bug 2) | Backend/core (`installer/versions.py`) | — | Pure, IO-free regex/parse functions; both `version_status.py`'s probe path and any future CLI-facing display consume the same functions, so the fix belongs in exactly one place. |
| Ownership attribution (Bug 3) | Backend/core (`installer/ownership.py`, `installer/install_ownership.py`) | Backend/core (`installer/update.py`'s mutation gate) | Attribution and update-dispatch are two different modules by original design (`ownership.py`'s own module docstring: "the two must never be conflated") — this phase's ownership fix has a load-bearing side effect on the update module that must not be treated as out of scope. |
| Tier classification (Bug 4) | Declarative data (`installer/registry.toml`) | Documentation (`installer/ui_common.py`'s comment) | Tier is "a browsing label" per `.claude/architecture.md` — a pure registry-field edit, verified by `tests/test_registry.py`, with zero runtime-code changes. |

## Standard Stack

No new third-party libraries. All four fixes use existing stdlib (`re`, `json`, `subprocess` via the existing `ProbeRunner`/`run_query` seams) and existing in-repo primitives. `rpm-ostree` is a Bazzite/Fedora-Silverblue-family system binary already present on the target host (`/usr/bin/rpm-ostree`, version `2026.2` [VERIFIED: live `rpm-ostree --version` this session]) — not something this project installs or vendors.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A single shared `_match_observed_version(token)` helper reused by both `parse_version` and `parse_status_version` (Pattern 2) | Fix `_OBSERVED_VERSION`'s match only inside `parse_version` | Silently incomplete: `extract_observed_version` would start returning `"jq-1.8.1"` as `installed`, but `is_outdated`'s `parse_status_version` call on that same string would still fail to rank it (see Pitfall 1), permanently reporting `outdated=None` for `jq`. A partial fix that looks complete in a narrow test. |
| A new small `detect_native_package_manager_owner(tool, probe)` helper inside `install_ownership.py` that always tries `_dnf`/`_apt`/`_pacman`/`_rpm_ostree` unconditionally | Populate `owner_probes = ["dnf", "apt", "pacman"]` on every registry row with a native-manager method and call the existing `detect_owner(tool, probe)` generically | Both are viable and reuse the SAME underlying probe functions (no duplicate logic either way). The registry-driven approach is smaller in code footprint (zero new `install_ownership.py` functions besides `_rpm_ostree`) and matches this project's own "registry declares from a closed set" convention exactly — but it is a **declarative, per-tool opt-in** (a new dnf-installable tool that forgets to add `owner_probes` silently stays `unknown`, the exact class of silent gap this phase exists to close). Given the affected set is small and enumerable (10 tools — see Pattern 1 below), this research recommends the registry-driven form, but flags the omission risk explicitly in Common Pitfalls. |

**Installation:** No new packages. No `npm install`/`pip install`/`uv add` needed for this phase.

**Version verification:** N/A — no new dependencies.

## Package Legitimacy Audit

**Not applicable.** This phase installs no new external packages (npm, PyPI, crates, or otherwise). All four fixes are in-repo Python plus registry.toml data edits, and `rpm-ostree` is a system binary already on the target host, not something this project vendors or installs. The Package Legitimacy Gate protocol was not run because there is nothing to check against a registry.

## Architecture Patterns

### Pattern 1: DoctorScreen — call `_refresh_guidance()` before `_refresh_body()`, and append a conditional frozen-PATH note

**What:** Two small, additive changes to `installer/wizard_app.py::DoctorScreen`:

```python
# Source: installer/wizard_app.py:389-394 (current, verbatim)
def action_apply(self) -> None:
    if self.applied:
        return
    _, self.error = run_live(self._fix)
    self.applied = self.error is None
    self._refresh_body()
```
becomes (D-01):
```python
def action_apply(self) -> None:
    if self.applied:
        return
    _, self.error = run_live(self._fix)
    self.applied = self.error is None
    self._refresh_guidance()
    self._refresh_body()
```
This matches the exact ordering every other guidance-affecting event in this same class already uses: `on_mount` (`_refresh_guidance()` then `_refresh_body()`, lines 253-256), `enter_view` (lines 270-272), and `on_globals_audited` (lines 505-506) — `action_apply` was the sole outlier.

For D-02, the Action section of `_refresh_body` (`wizard_app.py:312-322`, quoted verbatim):
```python
text.append("\n\nAction\n", style="bold")
if self.applied:
    text.append("PATH wired.", style="green")
    text.append("\nRestart your shell or run `source ~/.myshellrc` to apply.")
elif self.error is not None:
    ...
```
gains one more conditional line inside the `if self.applied:` branch only:
```python
if self.applied:
    text.append("PATH wired.", style="green")
    text.append("\nRestart your shell or run `source ~/.myshellrc` to apply.")
    text.append(
        "\nThe audit above still reflects the PATH this process started with — "
        "that is expected until you open a new shell or `source ~/.myshellrc`."
    )
```
(exact wording is Claude's Discretion per CONTEXT.md; the framing — "expected, not broken" — is the locked part).

**When to use:** Both changes are additive and scoped entirely to `DoctorScreen`; no other module is touched.

### Pattern 2: A single shared prefix-split fallback for `_OBSERVED_VERSION`, applied identically in both parser entry points

**What:** `installer/versions.py` currently has TWO independent call sites that `fullmatch` against `_OBSERVED_VERSION`: `parse_version` (line 70) and `parse_status_version` (line 141). D-03's mechanism must be implemented **once** and shared, not duplicated at each call site (duplication risks exactly the "fixed `installed` but not `outdated`" partial-fix trap in Pitfall 1 below).

```python
# NEW, added near _OBSERVED_VERSION (installer/versions.py:29)
# Finds the LAST '-' or whitespace character immediately followed by a digit
# or v/V. Greedy `.*` backtracks from the right, so it naturally prefers the
# rightmost valid split point: `jq-1.8.1` isolates at "1.8.1" (the only
# '-'), and a token with an embedded prerelease hyphen like
# `tool-2.3.4-rc.1` still isolates at "2.3.4-rc.1" (the *rc.1* hyphen's next
# character is a letter, not `[vV]?\d`, so it is never a valid split point;
# backtracking lands on the '-' before "2.3.4" instead).
_NAME_PREFIX_BOUNDARY = re.compile(r".*[-\s](?=[vV]?\d)")


def _strip_name_prefix(token: str) -> str:
    """Split a glued `<name>-<version>` token down to its trailing,
    version-shaped segment. `jq --version` prints `jq-1.8.1` as ONE
    whitespace-delimited token [VERIFIED: live `jq --version` this session].
    A no-op (returns `token` unchanged) when there is no such prefix, so
    callers can run this unconditionally as a fallback with no separate
    "did it match" branch.
    """
    match = _NAME_PREFIX_BOUNDARY.match(token)
    return token[match.end():] if match else token


def _match_observed_version(token: str) -> re.Match[str] | None:
    """`_OBSERVED_VERSION.fullmatch`, with one fallback: strip a glued name
    prefix and try again. Tried second (not instead of), so an ordinary
    `1.2.3`/`v1.2.3` token — the overwhelming common case — stays on the
    direct, unambiguous path; the prefix-split fallback only ever runs once
    the direct match has already failed. Deliberately reuses
    `_OBSERVED_VERSION` itself for the retry (not a second, parallel
    pattern) so the two named capture groups (core, prerelease) every
    caller already reads by index stay exactly the same shape either way.
    """
    match = _OBSERVED_VERSION.fullmatch(token)
    if match is not None:
        return match
    return _OBSERVED_VERSION.fullmatch(_strip_name_prefix(token))
```

Then BOTH existing call sites change from `_OBSERVED_VERSION.fullmatch(...)` to `_match_observed_version(...)`:
```python
# parse_version, installer/versions.py:70 — was:
#   match = _OBSERVED_VERSION.fullmatch(token[0])
match = _match_observed_version(token[0])

# parse_status_version, installer/versions.py:141 — was:
#   match = _OBSERVED_VERSION.fullmatch(text.strip())
match = _match_observed_version(text.strip())
```

**Why the shared-helper design matters:** `extract_observed_version` (`versions.py:116-126`) returns the ORIGINAL, unstripped token verbatim on success (`return token`, not the parsed value) — so once `parse_version` is fixed, `VersionStatus.installed` will display `"jq-1.8.1"` (name prefix intact), not `"1.8.1"`. This is a deliberate, minimal-footprint choice consistent with `extract_observed_version`'s own docstring contract ("verbatim") and avoids a display-layer decision CONTEXT.md never made explicit — flagged as Assumption A1 below for the planner/user to confirm is acceptable.

**When to use:** Both call sites, in the same commit — see Pitfall 1.

### Pattern 3: Ownership adapter — a fallback consulted only after existing evidence-based resolution is exhausted, plus the two structural changes it requires elsewhere

**What:** `install_ownership.py`'s evidence model ("a manager is reported only after its declared probe returns manager-specific evidence," module docstring line 1-6) is fundamentally different from `ownership.py`'s ("ownership is asserted only when the live executable is attributable to the candidate... or when every other manager... did not claim it," module docstring lines 17-27) — one is package-database membership evidence, the other is directory-prefix/live-PATH attribution evidence. Rather than merging these into `_collect_candidates`'s existing `owner_dirs`/`attribute_path` machinery (`ownership.py:232-301`), the lowest-risk integration point is a **fallback consulted only when `resolve_ownership`'s existing logic has already concluded `unknown`** — this preserves every existing test's active-path/by-elimination behavior byte-for-byte and adds one new evidence source at the very end.

```python
# installer/ownership.py — resolve_ownership gains one new parameter and
# one new call at its final fallthrough (the existing final `return
# _unknown(...)` at ownership.py:374-385)
def resolve_ownership(
    tool: Tool,
    *,
    platform: Platform,
    inventory: ManagerInventory,
    artifacts: Sequence[Path],
    managed_bin_dir: Path,
    which: Callable[[str], str | None] = shutil.which,
    native_probe: ProbeRunner | None = None,   # NEW — None in every existing
                                                # test, so existing behavior
                                                # (including
                                                # test_linux_system_package_manager_is_unknown_by_design)
                                                # is untouched unless a probe
                                                # is explicitly injected.
) -> ManagerOwnership:
    ...  # unchanged existing body
    # Before the FINAL `return _unknown(...)` only (not the earlier ones —
    # those already have positive OR complete-negative evidence and must
    # not be overridden by a lower-priority evidence source):
    if native_probe is not None:
        native = install_ownership.detect_owner(tool, native_probe)
        if native.confidence == "verified":
            return _owned_from_native(tool, native, candidates=candidates)
    return _unknown(tool, candidates=candidates, active_candidate=None,
                     active_path=active_path,
                     unknown_reason=_unknown_reason(...))
```

`native_probe` should be **`install_ownership.run_probe`** in production (threaded from `VersionRefreshService.__init__`, mirroring how `_query`/`_which` are already injectable there) — **not** `installer.run.run_query`, even though the call signatures are compatible enough to make that substitution tempting. `run_probe` explicitly sets `stdin=subprocess.DEVNULL` ("without inheriting the caller's terminal," its own docstring); `run_query` does not. `VersionRefreshService.refresh` runs on a Textual worker thread while the main thread holds the terminal in raw/alt-screen mode — the exact scenario Phase 14's own research flagged for `chsh` (`14-RESEARCH.md` Pitfall 3) applies here too, even though these specific probes (`rpm -q`, `dpkg-query`, `pacman -Qq`, `rpm-ostree status --json`) are read-only and unlikely to ever prompt — reusing the already-isolated `run_probe` costs nothing and avoids relitigating that risk analysis per-probe.

**Two structural changes this adapter REQUIRES, beyond the call site itself:**

1. **Widen the `Owner` `Literal` type.** `installer/ownership.py:61`:
   ```python
   Owner = Literal["installer", "brew", "cask", "pnpm", "uv", "unknown"]
   ```
   is a closed set. The adapter cannot construct a `ManagerOwnership(owner="dnf", ...)` (or `"apt"`/`"pacman"`/`"rpm-ostree"`) without adding these four names here — `pyright --strict` (this project's enforced mode) will reject the assignment otherwise. No exhaustive `match`/`assert_never` on `Owner` exists elsewhere in the codebase today (confirmed by grep across `catalog_tui.py`, `update.py`, `version_status.py` — all are `==`/`in` checks, none exhaustive), so widening this Literal is safe and self-contained; it does not ripple into a forced-exhaustiveness rewrite anywhere else.

2. **Add an explicit refusal branch in `installer/update.py::_perform`** for the new owner values (see Pitfall 3 — this is not optional; it is the direct, mechanical consequence of D-05's locked "map to `direct`" decision).

**When to use:** Both changes ship in the same PR/commit as the D-05 adapter call — a native-owned tool reaching `confidence="direct"` without either change either fails `pyright --strict` (change 1) or produces a confusing runtime `UpdateError` the first time a user tries to update a dnf-owned tool (change 2).

### Pattern 4: The `rpm-ostree`/just-layering probe, live-verified against this actual host

**What:** No registry tool declares `kind = "rpm_ostree"` today (0 matches for `'kind = "rpm_ostree"'` across `registry.toml`), and `installer/resolve.py:70-73`'s `_applies` unconditionally returns `False` for that kind ("Native installer for immutable Fedora, but skipped by default: it requires a reboot and breaks atomicity") — so the new probe cannot key off a `rpm_ostree`-kind method the way `_dnf`/`_apt`/`_pacman` key off their own matching method kind. It must instead reuse the tool's already-declared `dnf` method's `package` name, matching against `rpm-ostree`'s own live JSON inventory of explicitly layered packages:

```python
# NEW in installer/install_ownership.py, mirroring _dnf's shape exactly —
# live-verified this session on this actual Bazzite host (44.20260914,
# rpm-ostree 2026.2):
#   $ rpm-ostree status --json | jq '.deployments[] | {booted, packages,
#     "requested-packages"}'
#   { "booted": false, "packages": [...], "requested-packages": [...] }
#   { "booted": true,  "packages": ["amdgpu_top", "coolercontrol",
#     "liquidctl", "podman-compose"],
#     "requested-packages": ["amdgpu_top", "coolercontrol", "liquidctl",
#     "podman-compose"] }
#   ... (older, non-booted deployments follow)
def _rpm_ostree(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    """rpm-ostree/just-layering equivalent of _dnf: same package NAME
    source (the tool's declared dnf-method package, since rpm-ostree
    layers RPMs from the same Fedora/Bazzite repos dnf installs from), a
    different (JSON, booted-deployment-scoped) inventory. No new registry
    field: _applies() never selects an rpm_ostree-kind METHOD for install
    (resolve.py:70-73), but this is an ownership PROBE, not an install
    method, and is unaffected by that gate.
    """
    packages = _method_values(tool, {"dnf"}, "package")
    if not packages:
        return None
    output = _run(probe, ["rpm-ostree", "status", "--json"])
    if output is None:
        return None
    try:
        deployments = json.loads(output)["deployments"]
    except (TypeError, ValueError, KeyError):
        return None
    booted = next(
        (d for d in deployments if isinstance(d, dict) and d.get("booted") is True),
        None,
    )
    if booted is None:
        return None
    layered = booted.get("requested-packages")
    if not isinstance(layered, list):
        return None
    for package in packages:
        if package in layered:
            return Ownership("rpm-ostree", "verified", f"rpm-ostree layers {package}")
    return None
```
registered in the existing `_PROBES` dict (`install_ownership.py:167-176`) as `"rpm-ostree": _rpm_ostree`, and `"rpm-ostree"` added to `OWNER_PROBES` (`installer/model.py:55-64`) — the ONE closed-set schema addition this phase needs (dnf/apt/pacman are already valid `OWNER_PROBES` members today, just unused by any `[[tool]]` row; only `"rpm-ostree"` is new).

**Registry rows needing `owner_probes` added (D-04/D-05 audit result — the full, enumerated set):** exactly 10 tools declare a native-package-manager method today [VERIFIED: `grep -c 'kind = "(dnf|apt|pacman)"' installer/registry.toml` + a per-tool scan this session]:

| Tool id | Kinds declared | `owner_probes` to add |
|---|---|---|
| `rg` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `jq` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `git` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `zsh` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `watch` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `docker` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `podman` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `kitty` | dnf, apt, pacman | `["dnf", "apt", "pacman", "rpm-ostree"]` |
| `opencode` | pacman only | `["pacman"]` (no dnf/apt method exists to layer via `rpm-ostree` anyway) |
| `wezterm` | pacman only | `["pacman"]` |

Each probe function (`_dnf`/`_apt`/`_pacman`/`_rpm_ostree`) independently no-ops via `_method_values` returning an empty tuple when the declared kind is absent, so listing all four names on the dnf/apt/pacman-capable rows is safe on every platform — only the platform-matching probe ever produces evidence.

**When to use:** This registry edit and the two `install_ownership.py`/`model.py` additions ship together; `resolve_ownership`'s adapter call (Pattern 3) is what actually consumes `owner_probes` via `detect_owner`.

### Anti-Patterns to Avoid
- **Fixing `parse_version` alone and calling Bug 2 done.** `is_outdated`'s comparison (`parse_status_version`) is a separate call site against the SAME regex; leaving it unfixed makes `jq`'s outdated-status silently and permanently `None` even after `installed` starts showing correctly. See Pitfall 1.
- **Reusing `run_query` instead of `install_ownership.run_probe` for the new native-owner probes.** `run_query` does not isolate stdin; `run_probe` deliberately does, for exactly the Textual-worker-thread scenario this call site runs in.
- **Mapping D-05's `confidence="direct"` without also touching `update.py::_perform`.** The `MUTATION_GRADE` gate is not the only gate in the update path — `_perform`'s owner-dispatch `if/elif/else` (`update.py:231-245`) has no branch for the new owner names and its `else` raises `UpdateError`, caught into a confusing `status="failed"` outcome. See Pitfall 3.
- **Integrating the native-manager probe into `_collect_candidates`/`owner_dirs`/`attribute_path`.** Those functions answer a directory-prefix/live-PATH-attribution question; dnf/apt/pacman/rpm-ostree ownership is package-database membership evidence, a categorically different proof. Forcing it through the same machinery (e.g., trying to make `/usr/bin` an "owner dir") would blur two evidence models the module's own docstring explicitly separates.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| dnf/apt/pacman ownership probes | New subprocess-and-parse logic inside `ownership.py` | `install_ownership.py`'s existing `_dnf`/`_apt`/`_pacman` (`install_ownership.py:101-124`) via `detect_owner` | Already written, tested (`tests/test_install_ownership.py`), and explicitly the reason D-05 exists — `.claude/architecture.md` rule 5 forbids the duplicate. |
| A second regex for "version with a name prefix" | A parallel pattern with its own capture-group numbering | The `_strip_name_prefix` + retry-with-`_OBSERVED_VERSION` design (Pattern 2) | Reusing `_OBSERVED_VERSION` for the actual match keeps the two named capture groups (core, prerelease) identical in both the direct-match and fallback paths — every existing caller reading `match.group(1)`/`match.group(2)` needs zero changes. |
| A tier-correctness lint/CI check | An automated rule enforcing `category`-implies-`tier` | Manual review against `.claude/architecture.md`'s written criterion | `.claude/architecture.md` line 274 is explicit: tier classification "is not automated — no lint enforces tier correctness." This phase's fix is a data edit + a human-reviewed decision (already made in CONTEXT.md D-07/D-08/D-09), not new enforcement code. |

**Key insight:** every primitive Bugs 2 and 3 need already exists in this codebase (the probe functions, the `ProbeRunner` seam, `_OBSERVED_VERSION` itself); the work is composing them correctly and updating the load-bearing tests that currently pin the OLD, buggy behavior as correct (see Common Pitfalls) — not writing new subsystems.

## Common Pitfalls

### Pitfall 1: Fixing `parse_version` without also fixing `parse_status_version`
**What goes wrong:** `extract_observed_version` (via `parse_version`) starts returning `"jq-1.8.1"` for `installed`, but `is_outdated(installed, latest)` (via `parse_status_version`, a SEPARATE `_OBSERVED_VERSION.fullmatch` call at `versions.py:141`) still fails on the same unfixed input, so `VersionStatus.outdated` stays permanently `None` for `jq` — an improvement that looks complete (the catalog no longer says "unknown" for the version) while the update/outdated signal remains silently broken.
**Why it happens:** `parse_version` and `parse_status_version` are two independent functions with two independent `_OBSERVED_VERSION.fullmatch` calls, by design (their docstrings explain why they must stay separate parsers — different strictness/precision needs) — but that separation means a fix applied to only one is easy to miss.
**How to avoid:** Implement the fallback ONCE as a shared helper (`_match_observed_version`, Pattern 2) and change BOTH call sites in the same commit.
**Warning signs:** A test asserting `extract_observed_version("jq-1.8.1 (git rev...)")` now returns `"jq-1.8.1"`, with no accompanying test asserting `is_outdated("jq-1.8.1", "1.8.2")` now returns a real boolean instead of `None`.

### Pitfall 2: Treating D-03's mechanism as covering every "unknown version" case in the registry
**What goes wrong:** D-04's audit surfaced two OTHER tools whose `--version` output currently fails to parse, in shapes D-03's prefix-split mechanism does NOT fix, discovered by running every installed, testable tool's `--version` on this machine this session:
- `procs` — `procs "0.14.12 ( rev: ...`. The problematic character glued to the version is a literal double-quote (`"`), not a `-` or whitespace; `_NAME_PREFIX_BOUNDARY`'s boundary character class (`[-\s]`) does not match `"`, so this token is untouched by the fix and stays `"unknown"`.
- `bash`/`gnu-bash` — `GNU bash, version 5.3.9(1)-release (...)`. The problematic fragment (`(1)-release`) is glued AFTER the numeric core, not before it as a name PREFIX; D-03's mechanism only strips leading prefixes, never trailing suffixes, so this also stays "unknown" after the fix. (Separately, `installer/registry.toml:572` declares `cmd = "gnu-bash"` for this tool, but no binary literally named `gnu-bash` is on PATH on Linux — Homebrew's `bash` formula installs as `bash` — a pre-existing, unrelated `cmd`-vs-installed-binary-name gap outside this phase's stated scope; flagged here only so it is not confused with the version-parsing gap during the audit.)

**Why it happens:** D-03's decision text is deliberately narrow ("split at the last `-` (or whitespace) immediately preceding a segment that starts with a digit or `v`/`V`") — a generic, low-false-positive-risk mechanism, not a catch-all for every conceivable `--version` output shape.
**How to avoid:** D-04 explicitly anticipates this ("confirm the new split logic covers them (or note any that still need special-casing)") — the plan should document `procs` and `bash` as known, intentionally-out-of-scope residual gaps (not silently swept in, not silently ignored) rather than attempting to widen D-03's mechanism to catch them, which risks the "free substring search" false-positive-risk the discussion log explicitly rejected as an alternative.
**Warning signs:** A test asserting `procs`'s or `bash`'s version now parses — that would mean the mechanism grew beyond D-03's locked, narrow shape without a corresponding CONTEXT.md decision.

### Pitfall 3: `confidence="direct"` for a native-manager owner with no matching `update.py::_perform` branch
**What goes wrong:** D-05 locks the mapping `install_ownership.Ownership(confidence="verified")` → `ManagerOwnership(confidence="direct")`. `"direct"` is in `MUTATION_GRADE`, so a dnf-owned `jq` (say) now PASSES `update.py::_perform`'s own `MUTATION_GRADE` gate (`update.py:214`) — and then falls through its owner-dispatch `if owner in ("brew", "cask", "uv"): ... elif owner == "pnpm": ... elif owner == "installer": ... else: raise UpdateError(f"unsupported owner {owner!r}")` (`update.py:231-245`) to the final `else`, since none of the existing branches name `"dnf"`/`"apt"`/`"pacman"`/`"rpm-ostree"`. That `UpdateError` is caught by `perform_update`'s own `try/except` (`update.py:186-201`) and surfaces as `UpdateOutcome(status="failed", detail="unsupported owner 'dnf'")` — a confusing runtime failure, materially WORSE than today's clean, pre-flight `"cannot update jq: likely installed via the OS package manager (dnf/apt/pacman); this installer does not track that manager's inventory"` refusal (today's `_unknown_reason`, `ownership.py:547-551`), which never even attempts a subprocess.
**Why it happens:** `MUTATION_GRADE` is a NECESSARY but not SUFFICIENT gate — `update.py::_perform` separately requires an explicit owner-name branch to know HOW to actually dispatch the mutation, and this phase's stated scope is ATTRIBUTION correctness, not update-EXECUTION for a new manager class. Real dnf/apt/pacman package updates additionally typically require root/sudo — a privilege class this installer has never needed before (every existing owner — brew, cask, pnpm, uv, installer — is entirely user-space) — so implementing genuine update dispatch for these owners is a materially larger, riskier undertaking than this phase's four bug reports describe.
**How to avoid:** Add an explicit, dedicated branch in `_perform` for the new owner names that returns a clean, non-exception refusal outcome (e.g. `status="unsupported"`, mirroring the existing SDKMAN branch at `update.py:222-228`, with a detail string explaining the tool must be updated through its own OS package manager) — this satisfies D-05's confidence mapping (so ownership DISPLAY/attribution is correct) while deliberately NOT attempting a privileged system-package-manager mutation this phase never asked for.
**Warning signs:** A plan that wires D-05's adapter and widens `Owner` but never touches `installer/update.py` — the first live test against a dnf/apt/pacman-owned tool's `u` keybind (or Phase 14's auto-update-on-select path) would surface this as a runtime failure, not a type error, so `pyright --strict` alone will not catch the gap.

### Pitfall 4: Leaving `tests/test_ownership.py::test_linux_system_package_manager_is_unknown_by_design` and `tests/test_registry.py`'s tier-pinning tests untouched
**What goes wrong:** `test_linux_system_package_manager_is_unknown_by_design` (`tests/test_ownership.py:357-381`, parametrized over `["dnf", "apt", "pacman", "rpm_ostree"]`) directly asserts `result.owner == "unknown"` for a tool resolved with NO probe injected (the test helper `_resolve`, `tests/test_ownership.py:59-77`, has no `native_probe`/`probe` parameter today) — its own docstring calls this "Deliberate Phase 12 scope boundary, not a defect." Once Pattern 3's `native_probe: ProbeRunner | None = None` default lands, this test's behavior is UNCHANGED as written (no probe injected → the new fallback branch never runs → still `unknown`) and it keeps passing — but that is exactly the trap: a plan that stops there has proven only that the OLD, no-probe path still works, never that the NEW, probe-injected path resolves an owner correctly. Separately, `tests/test_registry.py:584-597`'s `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` pins `puppeteer.tier == "user"` by NAME, not just assertion, and `tests/test_registry.py:928-936`'s `test_registry_tier_distribution_is_pinned` pins the exact per-tier `Counter` (`{"system": 26, "ai": 15, "user": 48}`) as a deliberate tripwire whose own comment says "any phase that adds or removes a registry entry must update these counts in the same commit."
**Why it happens:** Both are intentional, well-designed tripwires from earlier phases — they are SUPPOSED to force a deliberate edit, not silently break; the risk is a plan that reflexively treats a newly-red test as something to work around rather than update, or conversely deletes/weakens a still-legitimate case (the "no probe injected" branch of the ownership test remains correct and should stay, just needs a sibling case for the probe-injected/verified path).
**How to avoid:** Rename+update `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`'s tier assertion and (new test) an `ast-grep`-tier assertion in the SAME commit as the registry edit; update `test_registry_tier_distribution_is_pinned`'s expected `Counter` to `{"system": 26, "ai": 17, "user": 46}`; ADD (do not replace) a new parametrized/explicit case to `test_ownership.py` proving the verified-ownership path with an injected fake probe, alongside the existing no-probe-injected case which should keep passing unmodified.
**Warning signs:** `make test` staying green with zero changes to `tests/test_registry.py` or `tests/test_ownership.py` after the tier/ownership fixes land — that would mean either the fix did not actually change observable behavior, or (worse) a still-correct pinned assertion was silently left stale.

## Code Examples

### The exact bug: DoctorScreen's missing refresh call
```python
# Source: installer/wizard_app.py:389-394, quoted verbatim this session
def action_apply(self) -> None:
    if self.applied:
        return
    _, self.error = run_live(self._fix)
    self.applied = self.error is None
    self._refresh_body()
```

### The exact bug: `_OBSERVED_VERSION`'s anchored match
```python
# Source: installer/versions.py:29, quoted verbatim this session
_OBSERVED_VERSION = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
```

### The exact bug: `install_ownership.detect_owner` has zero production callers
```
$ grep -rn "detect_owner\|install_ownership" installer/*.py setup.py tests/test_install_ownership.py
installer/model.py:271:    # installer/install_ownership.py and installer/skill_lifecycle.py.
tests/test_install_ownership.py:6:import installer.install_ownership as ownership
tests/test_install_ownership.py:7:from installer.install_ownership import Ownership, detect_owner
tests/test_install_ownership.py:75:    owner = detect_owner(
... (all remaining matches are also inside tests/test_install_ownership.py)
```
[VERIFIED: live grep this session — no match inside any non-test `installer/*.py` or `setup.py` file].

### The registry tier inconsistency, side by side
```toml
# installer/registry.toml:81-88 (rg) and :167-174 (fd), quoted verbatim
category = "search"
audience = "ai"
tier = "ai"

# installer/registry.toml:1836-1841 (ast-grep), quoted verbatim — SAME category
category = "search"
audience = "both"
tier = "user"   # <- inconsistent; D-07 changes this to "ai"
```

### puppeteer's own `desc` field already argues for the fix
```toml
# installer/registry.toml:2406-2407, quoted verbatim
tier = "user"
desc = "Headless-Chrome automation library; downloads its own Chrome and chrome-headless-shell. Required at runtime by mmdc."
```

### The stale D-10 comment, quoted verbatim
```python
# Source: installer/ui_common.py:129-134, quoted verbatim this session
# This tab groups the whole AI-coding ecosystem, not "what the AI runs
# by itself": it mixes agent CLIs you drive yourself (claude, codex)
# with CLIs built to be called BY an agent (rg, codegraph). "Tier"
# here means "bootstrap-order/install-flow bucket", not "who uses
# it" -- that's the separate Audience tab inside this screen (human /
# AI / both), worth checking if that distinction matters to you.
```
`claude`/`codex` are both `tier="user"` today (`registry.toml:1320`, `1344`, both quoted and confirmed this session) — they are not shown in the `ai` tab at all, contradicting the comment's "mixes ... claude, codex ... with ... rg, codegraph" claim. `rg`, `fd`, `codegraph` (all confirmed `tier="ai"` this session) are safe, already-accurate replacement examples.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `_OBSERVED_VERSION` matched only a bare or `v`-prefixed semver token | Adds one prefix-split fallback, reusing the same regex for the actual match | This phase | Tools whose `--version` glues the binary name directly onto the version (`jq-1.8.1`) now parse; tools with a different glue shape (`procs`, `bash`) remain unparsed by design (Pitfall 2). |
| `install_ownership.py::detect_owner` existed fully-built but wired to nothing in production | Wired into `ownership.py::resolve_ownership` as a final fallback, gated behind a `native_probe` parameter that defaults to `None` (opt-in, not automatic) | This phase | ~10 registry tools (the ones with a declared dnf/apt/pacman method) can now resolve a real owner instead of always `unknown`; every other tool's resolution path is byte-for-byte unchanged. |
| `ast-grep`/`puppeteer` tier="user" | tier="ai" | This phase | Both tools move from the `user` catalog tab to the `ai` tab; `Tool.requires`/`resolve_dependencies` is unaffected (tier is a "browsing label," per `.claude/architecture.md`, never an install-order mechanism) — `mmdc`'s existing `requires = ["pnpm", "puppeteer"]` edge still resolves puppeteer regardless of which tab it now displays under. |

**Deprecated/outdated:** None — this phase adds capability (real ownership attribution, wider version parsing, correct tier labels) without removing any existing mechanism.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `extract_observed_version` should keep returning the verbatim, unstripped token (`"jq-1.8.1"`, name prefix included) for display in `VersionStatus.installed`, rather than the parsed/stripped segment (`"1.8.1"`) — this preserves the function's existing documented contract ("verbatim") with the smallest possible footprint, but CONTEXT.md's decisions do not explicitly address DISPLAY formatting, only parseability. | Pattern 2 | If the user/planner actually wants a clean `"1.8.1"` displayed in the catalog's Ver column, `extract_observed_version` needs an additional design decision (return the matched/stripped value on the fallback path only, or always) not covered by D-03's text. Low product risk either way (both are honest, non-misleading strings), but worth a `checkpoint:human-verify` or explicit confirmation during planning rather than silently picking one. |
| A2 | `_perform`'s new owner-dispatch branch for dnf/apt/pacman/rpm-ostree owners should REFUSE the update cleanly (no real update dispatch) rather than implement actual `sudo dnf upgrade`-style mutation, since real update dispatch for these owners needs privilege escalation this installer has never required and CONTEXT.md's D-05/D-06 text is scoped to ATTRIBUTION ("wire install_ownership.py's real detection into the live ownership-resolution path"), not update-execution. | Pitfall 3 | If the user actually wants dnf/apt/pacman tools to be genuinely auto-updatable through this installer, that is a materially larger feature (privilege escalation UX, a new Runner variant, a new STRIDE surface) that this phase's bug-report framing does not describe and this research does not recommend attempting here — flag for a future phase if wanted. |
| A3 | The 10-tool set found by this session's registry scan (`rg`, `jq`, `git`, `zsh`, `watch`, `docker`, `podman`, `kitty`, `opencode`, `wezterm`) is the complete, exact set of tools with a declared dnf/apt/pacman method as of this research session — based on a literal `grep -c 'kind = "(dnf|apt|pacman)"'` plus a per-tool awk scan of the full 89-entry registry this session, not a sampled subset. | Pattern 4 | Low risk — this is a mechanical, exhaustive text scan of a committed file, not an inference; re-run the same grep if `registry.toml` has changed since this session before trusting the table verbatim. |

## Open Questions

1. **Should the D-02 frozen-PATH note live inside the existing `Guidance`/`doctor_guidance` pure-function layer, or as a DoctorScreen-local string (as recommended in Pattern 1)?**
   - What we know: `tests/test_guidance.py` tests `doctor_guidance`/`guard_guidance`/`node_globals_guidance` as pure, IO-free, `self.applied`-unaware functions; `self.applied` is a `DoctorScreen`-only piece of state, never passed into `guidance.py`.
   - What's unclear: Whether a future console (`make doctor`) rendering of the same report should ALSO show an applied/frozen note, which would argue for pushing the concept down into `guidance.py` instead.
   - Recommendation: Keep it DoctorScreen-local (Pattern 1) — the console `make doctor` path has no "apply" action at all (only the TUI does; the CLI's guidance was already rewritten by `_tui_guidance` specifically because TUI and console wording diverge), so there is no console-side need for this note today. Revisit only if a future phase adds an `apply` capability to `make doctor` itself.

2. **Does the native-manager ownership fallback (Pattern 3) need its own per-pass budget/backoff, mirroring `VersionRefreshService`'s existing `MAX_FETCHES_PER_REFRESH`/manager-inventory-caching design for brew/pnpm/uv?**
   - What we know: `VersionRefreshService._load_or_query_snapshot` already batches brew/pnpm/uv inventory ONCE per refresh pass and reuses it per-tool (`version_status.py:414-473`); by contrast, `install_ownership.py`'s probes (`_dnf`, `_apt`, `_pacman`) each run a SEPARATE subprocess PER TOOL PER PACKAGE (`rpm -q <pkg>` once per tool), and the new `_rpm_ostree` probe re-runs `rpm-ostree status --json` PER TOOL too, even though its result (the booted deployment's package list) is identical across every tool checked in the same refresh pass.
   - What's unclear: Whether re-running `rpm-ostree status --json` up to 10 times per refresh pass (once per tool in the table above) is an acceptable cost, or whether it should be batched/cached the same way brew/pnpm/uv inventory already is.
   - Recommendation: Given the set is small (≤10 tools) and `rpm-ostree status --json`'s live latency on this host was well under a second, this research recommends NOT adding a new caching layer for this phase — but flags it explicitly so the planner can decide, since `dnf`/`apt`/`pacman`'s per-package `rpm -q`/`dpkg-query`/`pacman -Qq` calls are already similarly uncached today and this phase does not change that existing cost profile, only adds one more probe of the same shape.

3. **Should `procs` and `bash`/`gnu-bash`'s separate, unfixed version-parsing gaps (Pitfall 2) get their own follow-up phase, or stay permanently "unknown" as an accepted limitation?**
   - What we know: Both are real, live-confirmed parsing failures this session, neither is covered by D-03's locked mechanism, and D-04 only asks to "note any that still need special-casing" — not to fix them in this phase.
   - What's unclear: Whether these are worth a dedicated future fix or are low enough value (2 tools, cosmetic "unknown" version display, no functional breakage) to leave alone indefinitely.
   - Recommendation: Note in STATE.md's pending-todos as fast-follow candidates, consistent with how Phase 14's research handled its own out-of-scope `run_wizard` parity gap — not a blocker for this phase.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `jq` (system binary) | Live-verifying Bug 2's root cause | ✓ | `jq-1.8.1` [VERIFIED live this session] | — |
| `rpm-ostree` | D-06's probe design and live JSON-shape verification | ✓ (this is a real Bazzite host) | `2026.2` [VERIFIED live this session] | On a non-Bazzite/non-rpm-ostree host, `_rpm_ostree`'s `_run(probe, [...])` call raises/returns `None` via the existing `CommandError`/`OSError`-catching `_run` wrapper (`install_ownership.py:55-59`) exactly like every other probe does when its manager binary is absent — no special-casing needed. |
| `pytest`/coverage tooling | Wave 0 tests | ✓ (existing project tooling, `pyproject.toml:46-57`) | — | — |
| `pyright --strict` | The `Owner` Literal-widening change (Pattern 3) must typecheck | ✓ (existing project tooling, run via `make validate`) | — | — |

**Missing dependencies with no fallback:** None — everything needed is stdlib, an already-installed system binary on the actual target platform, or already-installed project tooling.

**Missing dependencies with fallback:** None beyond the `rpm-ostree`-absent case noted above, which the existing `_run` error-swallowing pattern already handles for free.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`pyproject.toml:46-49`), `asyncio_mode = "auto"` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`/`[tool.coverage.report]`) |
| Quick run command | `uv run pytest tests/test_wizard_app.py tests/test_versions.py tests/test_version_status.py tests/test_ownership.py tests/test_install_ownership.py tests/test_registry.py tests/test_ui_common.py -x -q` |
| Full suite command | `make test` (pytest + coverage, `fail_under = 90`, `pyproject.toml:57`) |

### Phase Requirements → Test Map
No REQ-IDs were supplied for this phase invocation (CONTEXT.md/ROADMAP.md describe it narratively rather than with a REQUIREMENTS.md id list, matching Phase 14's precedent); the map below is keyed to CONTEXT.md's D-01 through D-10 instead.

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|-------------------|-------------|
| D-01 | `action_apply` calls `_refresh_guidance()` before `_refresh_body()` on a successful fix | unit (Textual pilot) | `uv run pytest tests/test_wizard_app.py -k doctor_enter_applies -x` | ✅ existing test (`test_doctor_enter_applies_fix_once`, `tests/test_wizard_app.py:313-327`) must stay green; a NEW assertion (or new test) is needed proving `_refresh_guidance` was actually invoked — e.g. spy/count on `self.guidance` recomputation, since content is byte-identical for the frozen-report portion (see Summary) so a naive before/after content diff would pass even without the fix. |
| D-02 | A frozen-PATH note appears in the rendered body only when `self.applied is True` | unit (Textual pilot) | `uv run pytest tests/test_wizard_app.py -k doctor_screen_adapts -x` (extend) | ❌ Wave 0 — model on `test_doctor_screen_adapts_missing_path_guidance_for_tui` (`tests/test_wizard_app.py:282-292`)'s existing `body = ...query_one(...).render()` pattern; assert the note is ABSENT before `enter` and PRESENT after. |
| D-03 | `jq-1.8.1` (and any other `<name>-<version>`-shaped token) parses via the new fallback in BOTH `parse_version` and `parse_status_version` | unit | `uv run pytest tests/test_versions.py -k prefix -x` | ❌ Wave 0 — new test cases; model directly on the existing `test_parse_version_reads_shapes_a_version_line_legitimately_has` (`tests/test_versions.py:83`) and `test_extract_observed_version_finds_the_first_parseable_token` (`:242`) shapes, PLUS a new `is_outdated`-level case per Pitfall 1. |
| D-04 | The registry audit's findings (jq fixed; procs/bash noted as out-of-scope) are recorded, not silently dropped | doc/code-review | N/A — a `# Verified {date}: ...` comment or equivalent note in `versions.py`/registry per this project's "Registry-authoring guidelines" convention | ❌ Wave 0 — no existing automated check for this; follow the `mmdc`/`puppeteer` comment-plus-substring-test worked example (`.claude/architecture.md`'s "Registry-authoring guidelines" section) if the finding is load-bearing enough to protect from silent regression. |
| D-05 | A tool with an owner_probes-declared dnf/apt/pacman method and a matching live probe resolves `confidence="direct"`, `owner` in `{"dnf","apt","pacman"}` | unit | `uv run pytest tests/test_ownership.py -k native -x` (new) | ❌ Wave 0 — extend `tests/test_ownership.py`'s `_resolve` helper with a `native_probe` kwarg; add a case proving the verified path, alongside (not replacing) `test_linux_system_package_manager_is_unknown_by_design`'s existing no-probe-injected case (Pitfall 4). |
| D-05 (update-gate side effect) | A native-owned, `confidence="direct"` tool refuses cleanly (not via `UpdateError`/`"unsupported owner"`) when the update action is attempted | unit | `uv run pytest tests/test_update.py -k native -x` (new) | ❌ Wave 0 — new test file section; model on the existing SDKMAN-refusal branch test in `tests/test_update.py` (grep for the `"unsupported"` status case). |
| D-06 | `_rpm_ostree` correctly parses the booted deployment's `requested-packages` and matches against the tool's declared dnf package | unit | `uv run pytest tests/test_install_ownership.py -k rpm_ostree -x` | ❌ Wave 0 — model on `tests/test_install_ownership.py`'s existing `_dnf`-shaped test cases; use the live JSON shape captured in Pattern 4 as the fixture (booted + non-booted deployments, `requested-packages` array). |
| D-07 | `ast-grep.tier == "ai"` | unit | `uv run pytest tests/test_registry.py -k ast_grep -x` | ❌ Wave 0 — no existing tier assertion for `ast-grep`; new test needed (`test_ast_grep_cmd_is_ast_grep_not_sg`, `tests/test_registry.py:1307-1309`, only tests `cmd`, not `tier`). |
| D-08 | `puppeteer.tier == "ai"` | unit | `uv run pytest tests/test_registry.py -k puppeteer -x` | ⚠️ Existing test `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` (`tests/test_registry.py:584-597`) currently asserts `tier == "user"` and must be renamed + its tuple assertion updated to `"ai"` in the SAME commit as the registry edit (Pitfall 4). |
| D-09 | `mmdc`/`gitleaks`/`vale`/`drawio-cli` remain `tier == "user"` (no change) | unit | `uv run pytest tests/test_registry.py -x` (full file, no filter) | ✅ No existing test currently pins these four explicitly by tier as a group; the phase's job here is confirming the FULL suite still passes with zero edits to these four rows — a negative/no-op verification, not a new assertion. |
| D-10 | `ui_common.py`'s AI-tab comment no longer names `claude`/`codex` as `ai`-tier examples | code-review | `uv run pytest tests/test_ui_common.py -x` (full file — confirms no behavior change, since this is a comment-only edit) | ✅ Comment-only change; no automated string-content test exists for comments (by design — comments are not registry data). Confirm via `git diff` review, not a new test. |
| Registry counts (D-07/D-08 side effect) | `Counter(tier for tool in registry)` reflects the two moves | unit | `uv run pytest tests/test_registry.py -k tier_distribution -x` | ⚠️ Existing test `test_registry_tier_distribution_is_pinned` (`tests/test_registry.py:928-936`) currently asserts `{"system": 26, "ai": 15, "user": 48}` and MUST be updated to `{"system": 26, "ai": 17, "user": 46}` in the same commit (its own comment already says so). |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_wizard_app.py tests/test_versions.py tests/test_version_status.py tests/test_ownership.py tests/test_install_ownership.py tests/test_registry.py tests/test_ui_common.py tests/test_update.py -x -q` (touches every module this phase's four bugs modify)
- **Per wave merge:** `make test` (full suite + coverage floor)
- **Phase gate:** Full suite green (`make validate && make test`, per `.claude/testing.md`'s "Definition of done") before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_wizard_app.py`: a test proving `_refresh_guidance()` is actually called by `action_apply` (D-01) — content-diff assertions alone will pass even without the fix, since the frozen `DoctorReport` portion of `self.guidance` cannot visibly change (see Summary); assert via a spy/counter or by injecting a `guard_state` that DOES change between the two calls.
- [ ] `tests/test_wizard_app.py`: a test proving the D-02 frozen-PATH note's presence/absence toggles on `self.applied`.
- [ ] `tests/test_versions.py`: new cases for the prefix-split fallback in BOTH `parse_version` and `parse_status_version`/`is_outdated` (Pitfall 1) — not just `extract_observed_version`.
- [ ] `tests/test_ownership.py`: `_resolve`'s test helper needs a new `native_probe` kwarg; a new test proving the verified-ownership path (fake probe returning evidence for a dnf-owned fixture tool), added ALONGSIDE (not replacing) the existing no-probe-injected `test_linux_system_package_manager_is_unknown_by_design`.
- [ ] `tests/test_install_ownership.py`: new `_rpm_ostree` test cases using the live-captured JSON shape from Pattern 4 (booted + non-booted deployments, `requested-packages`).
- [ ] `tests/test_update.py`: a new case proving a native-manager-owned, `confidence="direct"` tool refuses cleanly on update attempt (Pitfall 3) rather than raising `UpdateError`.
- [ ] `tests/test_registry.py`: rename+update `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`; add an `ast-grep` tier assertion; update `test_registry_tier_distribution_is_pinned`'s expected `Counter`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No authentication surface is touched by any of the four bugs. |
| V3 Session Management | No | Not applicable. |
| V4 Access Control | Yes | `MUTATION_GRADE` is this project's existing access-control gate on which ownership confidences may drive a mutating action; D-05's new owner values (`dnf`/`apt`/`pacman`/`rpm-ostree`) reaching `confidence="direct"` (a `MUTATION_GRADE` member) is exactly the access-control-relevant change Pitfall 3/Assumption A2 analyze — this phase's recommended fix (an explicit, non-mutating refusal branch in `_perform` for these owners) is itself the correct V4 control: attribution may be verified without also being update-eligible. |
| V5 Input Validation | Yes | `install_ownership.py`'s probes already parse subprocess output defensively (try/except around `json.loads`, membership checks against explicit lists, never `eval`/format-string injection into a shell) — the new `_rpm_ostree` probe (Pattern 4) follows the identical, already-reviewed pattern: `json.loads` wrapped in `except (TypeError, ValueError, KeyError): return None`, and package-name membership tested via Python `in`, never interpolated into a second subprocess call. |
| V6 Cryptography | No | Not applicable — no cryptographic material is involved in any of the four bug fixes. |
| V12 File and Resources | N/A | No file-upload or resource-handling surface is touched. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A native-manager-owned tool silently gaining privileged-update capability it was never designed for (the Pitfall 3 scenario) | Elevation of Privilege | The recommended `_perform` refusal branch for dnf/apt/pacman/rpm-ostree owners (Assumption A2) keeps this installer's mutation surface exactly as user-space-only as it has always been (`.claude/python-tooling.md`'s bandit-enforced "validate subprocess inputs, avoid shell=True" discipline is unaffected since no NEW subprocess mutation is added — only a clean refusal). |
| Command injection via a tool/package name reaching a probe's argv unsanitized | Tampering | Every existing and new probe (`_dnf`, `_apt`, `_pacman`, `_rpm_ostree`) builds its argv as a Python `list[str]` from registry-declared `Method.params` values, never a formatted/interpolated shell string, and `run_probe`/`run_query` both call `subprocess.run` with a list argv (never `shell=True`) — this phase's new probe follows the identical, already-established pattern and introduces no new injection surface. |
| A version string reaching a downstream comparison/display without validation, enabling a spoofed "always up to date" or "always outdated" report | Tampering (of the version-comparison outcome) | `parse_version`/`parse_status_version`'s fail-closed contract (`None` on anything unparseable — never a zero-filled guess) is preserved by Pattern 2's design: the fallback either produces a fully valid `_OBSERVED_VERSION` match or returns `None`, exactly like the existing direct-match path: no new "best effort" partial-parse is introduced. |
| Stdin-forwarding into a Textual-worker-thread-spawned subprocess corrupting the raw-mode TUI render (the same class of risk Phase 14's `chsh` research flagged) | Tampering (of the user's own session display) | Using `install_ownership.run_probe` (which sets `stdin=subprocess.DEVNULL`) rather than `installer.run.run_query` (which does not) for the new native-owner probes, as recommended in Pattern 3. |

## Sources

### Primary (HIGH confidence — read directly this session)
- `installer/wizard_app.py` (lines 158-521, the full `DoctorScreen` class) — read via `Read`.
- `installer/guidance.py` (full file) — read via `Read`.
- `installer/versions.py` (full file) — read via `Read`.
- `installer/version_status.py` (lines 1-220, 339-520) — read via `Read`.
- `installer/ownership.py` (full file) — read via `Read`.
- `installer/install_ownership.py` (full file) — read via `Read`.
- `installer/update.py` (lines 120-250) — read via `Read`.
- `installer/model.py` (lines 1-120, 255-330) — read via `Read`.
- `installer/resolve.py` (lines 60-82) — read via `Read`.
- `installer/enums.py` (lines 23-29) — read via `Read`.
- `installer/ui_common.py` (lines 100-150) — read via `Read`.
- `installer/registry.toml` — the full `rg`, `fd`, `jq`, `ast-grep`, `puppeteer`, `mmdc`, `gitleaks`, `vale`, `drawio-cli`, `drawio-desktop`, `claude`, `codex`, `pi`, `codegraph`, `graphify`, `rtk`, `sd`, `bat`, `eza`, `gnu-bash` entries, plus a full-file mechanical scan for `kind = "dnf"/"apt"/"pacman"/"rpm_ostree"` and `owner_probes` — all read via `Read`/`Bash grep` this session.
- `setup.py` (lines 380-520) — read via `Read`.
- `tests/test_wizard_app.py` (lines 1-400) — read via `Read`.
- `tests/test_ownership.py` (lines 1-80, 340-385) — read via `Read`.
- `tests/test_install_ownership.py` (imports/call-site grep) — read via `Bash grep`.
- `tests/test_registry.py` (lines 578-600, 920-990) — read via `Read`.
- `tests/test_versions.py`, `tests/test_guidance.py`, `tests/test_doctor.py` — function-name inventory via `Bash grep`.
- `.claude/architecture.md` (full file) — read via `Read`.
- `.claude/python-tooling.md`, `.claude/testing.md` (full files) — read via `Read`.
- `.planning/config.json` — read via `Read` (confirms `nyquist_validation: true`, `security_enforcement: true`).
- `.planning/phases/15-.../15-CONTEXT.md`, `.../15-DISCUSSION-LOG.md` — read via `Read`.
- `.planning/phases/14-.../14-RESEARCH.md` — read via `Read` (for this project's own established RESEARCH.md shape/conventions).
- Live command output, this session, on the actual target host (Bazzite 44.20260914): `jq --version` → `jq-1.8.1`; `rpm-ostree --version` → `2026.2`; `rpm-ostree status --json` (piped through `jq`) → the `deployments`/`booted`/`requested-packages` shape quoted in Pattern 4; ~50 other installed tools' `--version` output for the D-04 registry audit (`rg`, `fd`, `bat`, `sd`, `git`, `delta`, `eza`, `fzf`, `lazygit`, `gh`, `yq`, `starship`, `zsh`, `direnv`, `just`, `dust`, `btm`, `gum`, `glow`, `difft`, `gitui`, `podman`, `dive`, `duf`, `fx`, `dasel`, `procs`, `ast-grep`, `jless`, `bun`, `pnpm`, `volta`, `fnm`, `gitleaks`, `code`, `mmdc`, `glab`, `drawio`, `deno`, `uv`, `java`, `gradle`, `mvn`, `groovy`, `wezterm`, `opencode`, `cursor-agent`, `agy`, `codegraph`, `graphify`, `rtk`, `jetbrains-toolbox`, `node`, `bash`).

### Secondary (MEDIUM confidence)
None — no WebSearch/external-docs source was needed for any of the four bugs; every finding traces to a direct `Read` of the live repository or a live subprocess call on the actual target host this session.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Bug 1 (Doctor refresh) root cause and fix: HIGH — direct read of the exact lines; the "byte-identical guidance content" nuance is a direct trace of `doctor_guidance`'s data source, not an inference.
- Bug 2 (version parsing) root cause, fix design, and registry audit: HIGH — the jq bug is live-reproduced on this session's real machine; the audit is an exhaustive live scan of every testable tool, not a sample; the two out-of-scope residual gaps (procs, bash) are also live-reproduced, not assumed.
- Bug 3 (ownership wiring) root cause and the two structural requirements it surfaces (`Owner` widening, `update.py::_perform` refusal branch): HIGH for the root cause and the `Owner`-typing requirement (both directly read); MEDIUM-leaning-HIGH for the `_perform` refusal-branch recommendation specifically — the CONSEQUENCE (an `UpdateError` on the existing `else` branch) is directly read and certain, but the RECOMMENDED shape of the fix (a new `"unsupported"`-status branch, Assumption A2) is this research's judgment call, not a locked CONTEXT.md decision, and is flagged as such.
- Bug 4 (tier fixes) verification against the live registry, and the two pinned-test consequences: HIGH — every tier value, every comment, and every affected test line was read directly this session.
- Security Domain / ASVS mapping: MEDIUM — derived from direct reads of this project's own existing conventions (bandit rules, `MUTATION_GRADE`) plus standard ASVS category definitions from training knowledge, consistent with Phase 14's own research methodology for this same section.

**Research date:** 2026-09-14
**Valid until:** 2026-10-14 (30 days — fast-moving, actively-developed in-repo code; re-verify line numbers against the live tree if planning is delayed past that window, and re-run the D-04 registry audit if `registry.toml` gains new tools with `--version` output in the interim).
