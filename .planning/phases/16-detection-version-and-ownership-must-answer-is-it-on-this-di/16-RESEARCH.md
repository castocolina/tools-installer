# Phase 16: Catalog Truth — Detection, Version and Ownership from the Filesystem - Research

**Researched:** 2026-10-09
**Domain:** Python TUI installer catalog correctness — ownership attribution, skill-pack status detection, row-state honesty, and foreign-shell-config PATH remediation
**Confidence:** HIGH (every claim below is backed by a `Read` of the cited file this session; no external package research was needed — this phase touches zero new dependencies)

## Summary

This is not a greenfield phase — it is a defect-closure phase against a codebase that already has the right *shape* for almost everything D-01 through D-24 ask for, but has four concrete, independently-verified gaps: (1) `installer/ownership.py` has no `sdkman` branch at all — its `Owner` literal type, `_KIND_TO_OWNER` map, and `_collect_candidates` loop simply never mention `kind="sdkman"`, so java/groovy/gradle/maven/springbootcli can never resolve to anything but `unknown` even when a real manager (brew) owns them; (2) `installer/install_ownership.py::_sdkman`'s probe reads `_method_values(tool, {"script"}, "sdk_candidate")` against a registry that declares `kind = "sdkman"` with param `candidate` — both the kind filter and the param key are wrong, so the probe can never return evidence even once a caller wires it in; (3) `installer/skill_lifecycle.py::inspect_status` has zero production callers (confirmed by grep — only test files import it), and `SkillOperation`/`SKILL_OPERATION_IDS` in `installer/model.py` support exactly two harness-status checks (`codex_plugin_status`, `pi_package_status`) despite five skill_pack tools in the registry needing per-harness status across up to ten declared harnesses; (4) `installer/rcclean.py::unguarded_path_writers` already does 100% of D-21's detection work and already has real callers in `app.py`/`wizard_app.py` for *reporting* — the only new work is a write action that uses this existing detection, not a new scan.

A fifth finding that CONTEXT.md does not flag explicitly but this session verified by reading the schema: `installer/model.py::SKILL_HARNESSES` is a **closed ten-value tuple** (`antigravity, claude, codex, copilot, cursor, kilo, kimi, opencode, pi, windsurf`) that does **not** include `factory-droid` or `gemini-cli` — two of the hosts D-09's own corrected list for `superpowers` names (upstream: Claude Code, Antigravity, Codex App/CLI, Cursor, Factory Droid, Gemini CLI, Copilot CLI, Kimi Code, OpenCode, Pi). Fixing D-09's `supported_harnesses` data for `superpowers` to match upstream truth requires a schema change (widening `SKILL_HARNESSES`) before the TOML edit is even possible — the planner must sequence a `SKILL_HARNESSES` tuple edit in `model.py` ahead of or alongside the registry data fix, not treat D-09 as a pure-data task.

**Primary recommendation:** Treat this phase as four independent adapter-extension tracks that share almost no code (ownership, skill_pack status, row-state plumbing, PATH-guard write), each following the existing closed-table / adapter-not-reimplementation pattern this codebase already enforces via `.claude/architecture.md` rule 5. Do not attempt a unifying abstraction across the four tracks — the codebase's own docstrings (`ownership.py:1-47`, `post_install.py:1-22`, `rcclean.py:1-7`) already explain why each is a distinct concern.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ownership attribution (real-owner-wins, sdkman) | Backend logic (`installer/ownership.py`, `installer/install_ownership.py`) | — | Pure evidence-resolution module; no I/O boundary change needed, only new branches in existing adapters |
| skill_pack install-state detection | Backend logic (`installer/skill_lifecycle.py`) + Database/Storage (`installer/version_cache.py`'s cache file) | TUI (Textual `Worker`, matching `_refresh_versions_worker`) | Detection is a subprocess probe (same shape as version refresh); caching and background dispatch reuse the version-refresh worker pattern already proven in `catalog_tui.py` |
| Row states (broken shim, no-method reason, already-current) | TUI (`installer/catalog_tui.py`, `installer/wizard_app.py` DoctorScreen) | Backend logic (`installer/status.py`, `installer/deps.py`) | The underlying facts (shim present / package gone) are backend-computed; the row-state *display* is purely a TUI rendering concern layered on top |
| Post-install policy re-application on explicit selection | Backend logic (`installer/engine.py`, `installer/post_install.py`) | — | `install_tool`'s `ALREADY_INSTALLED` short-circuit is the exact boundary D-17/D-20 must thread through without widening |
| Foreign unguarded PATH-line guard-in-place | Backend logic (`installer/rcclean.py`, `installer/shellrc.py`, `installer/atomic.py`) | TUI (DoctorScreen apply step, per-file confirmation) | Detection and backup primitives are pure/IO-isolated already; only the TUI confirmation flow and the new write function are new |

## User Constraints

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Owner vs. registry conflict**
- **D-01:** Owner reports the tool's REAL source — the path/inventory that actually proves it, not the registry's declared method. groovy owned by Homebrew reads "Homebrew," not "unknown." — Reversibility: reversible.
- **D-02:** When the real owner differs from the registry's declared policy for that tool (e.g. Homebrew owns a tool the registry declares SDKMAN-exclusive), the row carries a visible marker, not just a detail-pane note — e.g. a dim "≠ policy" tag. — Reversibility: reversible.
- **D-03:** Pressing `u` on an off-policy tool offers to migrate it to the catalog's declared manager (e.g. brew groovy → SDKMAN groovy). — Reversibility: reversible (the offer itself; the migration's own mutations are scoped by D-04).
- **D-04:** The migration flow itself (uninstall from the old manager, install via the declared one, handle dependents) is deferred to its own phase. — Reversibility: reversible (deferral, not the migration's own danger).
- **D-05:** Until migration exists, `u` on an off-policy tool updates through its real, provable owner (e.g. `brew upgrade groovy`), with a note that migration is coming. Never silently refuses. — Reversibility: reversible.
- **D-06:** A tool owned by two managers at once (e.g. brew's `openjdk` and a later SDKMAN `java`) shows the ACTIVE owner (whichever PATH resolves) plus a "also installed via X" note for the shadowed one. — Reversibility: reversible.
- **D-07:** A tool that installs itself into its own directory via its own script (bun → `~/.bun`, fnm → `~/.local/share/fnm`, volta → `~/.volta`) reports Owner = "own installer," proven by the active path matching the tool's declared location (feeds D-13's per-method location mechanism). — Reversibility: reversible.
- **D-08:** Owner stays "unknown" only when no manager's path or inventory proves anything, and even then the detail pane shows the active binary's resolved path so the user can see where it actually came from. — Reversibility: reversible.

**skill_pack detection**
- **D-09:** The registry's `supported_harnesses` lists are factually wrong for at least `superpowers` (declared Pi-only; verified upstream it supports Claude Code, Antigravity, Codex App/CLI, Cursor, Factory Droid, Gemini CLI, Copilot CLI, Kimi Code, OpenCode, and Pi). Every `skill_pack` entry's `supported_harnesses` must be re-audited against its own upstream docs before the detection mechanism is built on top of it. — Reversibility: reversible.
- **D-10:** A skill pack's install state is read through each harness's own CLI (`pi list`, `codex plugin list`, `claude plugin list`, etc.), run in a background worker and cached — the same pattern `installer/version_cache.py` already uses for versions, not a new mechanism. — Reversibility: reversible.
- **D-11:** For a supported harness that has no list/status command at all, fall back to reading its on-disk state for that harness only (never as the general mechanism — CLI stays primary wherever one exists). — Reversibility: reversible.
- **D-12:** While the background probe is running, the Inst column shows the last cached answer with the existing stale `~` marker (reused from the version column's convention), not a blank/"checking…" state. Replaced in place when the probe lands. — Reversibility: reversible.
- **D-13:** A pack installed in several hosts at once lists every host in the Owner column (e.g. "Claude Code, Pi"), truncating to "Claude Code +2" when narrow, with the full list in the detail pane. — Reversibility: reversible.
- **D-14:** Harness CLIs are re-run on every catalog launch, in the background (one list call per installed harness, not per pack) — not on the version cache's longer TTL and not manual-only. — Reversibility: reversible.
- **D-15:** When a skill pack is selected for install, instructions are shown only for harnesses present on this machine — Cursor included (installed as `cursor`/`cursor-agent` shell functions, not resolvable binaries). Host presence detection must work from disk as well as PATH, not PATH alone. — Reversibility: reversible.

**What a row says when it can't act**
- **D-16:** A tool that has genuinely no install method on this platform stays dimmed and unselectable, but the row shows a short reason and the detail pane explains fully. Never silent. — Reversibility: reversible.
- **D-17:** Pressing enter on a selected, already-installed tool: if outdated, it updates through its real owner (same path as `u`); if current, the confirm screen lists it as "already current — nothing to do." Never "Install 0 tools" with no explanation. Regardless of install/update state, the tool's post-install policies are applied on this explicit selection (D-20 governs the re-propose rule). — Reversibility: reversible.
- **D-18:** A tool whose shim/binary exists but whose backing package is gone (mmdc's dangling pnpm shim) gets a distinct "broken" state — a separate Inst marker, a detail-pane explanation, and selecting it reinstalls/repairs. Never reads as plainly installed, never reads as plainly absent. This closes pending todo `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md`. — Reversibility: reversible.
- **D-19:** The registry gains per-method, per-OS install-location declarations — each OS-filtered method states where it puts the tool (a `bin_dir` for a plain binary, an `app`/bundle path for macOS, an install root like `~/.local/kitty.app` for a Linux app bundle). A hit at that location is also the ownership proof feeding D-01/D-07. The fix is adding kitty's real method (and auditing other tools for the same gap), not inventing a new per-tool-per-OS table alongside methods. — Reversibility: costly for the mechanism shape; the kitty fix itself is reversible.
- **D-20:** An installed tool's post-install policies are (re)applied only on explicit user selection (sensitive actions still ask to confirm, per `installer/post_install.py`'s existing doctrine). A dependency drag-in or a plain re-run of the installer never re-proposes a policy the user already declined. — Reversibility: reversible.

**Foreign PATH lines**
- **D-21:** Doctor can offer to guard a foreign unguarded PATH line in place — rewrite it into the self-deduping case-guard form at the same position, never delete it. Safe even for a line inside an `if`/`case` block. — Reversibility: reversible.
- **D-22:** A line that sits inside another tool's own marked block (e.g. kitty-setup's `# >>> my-kitty PATH >>>`) is never touched — Doctor names the owning tool and tells the user to fix it there. — Reversibility: reversible.
- **D-23:** Guarding a foreign line is preceded by a backup, using the exact same `.tools-installer.old` convention Phase 15.8 already established for `~/.shellrc` consolidation. — Reversibility: reversible.
- **D-24:** Guarding runs from Doctor's apply step, with per-file opt-in — each offending file is listed and confirmed individually before it is edited. — Reversibility: reversible.

### Claude's Discretion
- Exact wording of the "≠ policy" row marker (D-02) and the "broken" state's marker/color (D-18) — visual detail, not locked by the user.
- Whether the per-harness background probe (D-10/D-14) shares a worker/thread pool with the existing version-refresh worker or runs its own — implementation detail.
- Exact registry schema shape for per-method install-location declarations (D-19) — a field name/structure decision for the planner, not a user-facing choice.
- Full audit list of other tools needing per-OS location fixes beyond kitty (D-19) — to be discovered during research/planning, not pre-enumerated here.

### Deferred Ideas (OUT OF SCOPE)
- **brew→SDKMAN migration flow** (D-04) — remove the brew formula, install the SDKMAN candidate, handle dependents. Needs its own design: dependency handling, rollback, confirmation flow. Deferred to its own future phase.
- **kitty-setup project's own `.bashrc` block** (`# >>> my-kitty PATH >>>`) — upstream of this repo (`../kitty-setup`), not something `tools-installer` can or should fix. D-22 explicitly says such blocks are named, never edited.
</user_constraints>

## Phase Requirements

<phase_requirements>
This is an inserted phase (16) with no pre-assigned `REQ-*` IDs in `.planning/REQUIREMENTS.md` — the same situation 15.7/15.8 were in. The planner should map each PLAN directly to the D-01–D-24 decision IDs above rather than inventing requirement IDs; `.planning/STATE.md`'s accumulated-decisions log already records prior inserted phases this way (e.g. "[15.7-01, 2026-09-22]: D-01e — ...").

| ID | Description | Research Support |
|----|-------------|------------------|
| D-01..D-08 | Real-owner-wins ownership attribution (sdkman branch, off-policy marker, migrate offer, dual-owner note, own-installer label, honest unknown) | `installer/ownership.py` full read; `installer/install_ownership.py` full read; both bugs verified by source inspection, see Common Pitfalls 1–2 |
| D-09..D-15 | skill_pack detection via per-harness CLI, cached, backgrounded | `installer/skill_lifecycle.py`, `installer/model.py` (SkillLifecycle/SkillOperation/SKILL_HARNESSES/SKILL_OPERATION_IDS), `installer/registry.toml` skill_pack block audit, `installer/host_setup.py` (precedent pattern) |
| D-16..D-20 | Row states (no-method reason, already-current, broken shim) + post-install re-application on selection | `installer/status.py`, `installer/deps.py`, `installer/engine.py`, `installer/post_install.py`, `installer/catalog_tui.py` Inst-column rendering, pending todo file |
| D-21..D-24 | Guard foreign unguarded PATH line in place, backed up, per-file opt-in | `installer/rcclean.py` (existing detection + existing callers), `installer/shellrc.py::path_export_guard`, `installer/atomic.py` (`.tools-installer.old` convention), `.claude/architecture.md` Phase 15.8 section |
</phase_requirements>

## Standard Stack

No new external packages. This phase extends four existing, already-vendored Python modules (`ownership.py`, `install_ownership.py`, `skill_lifecycle.py`, `rcclean.py`) plus their TUI integration points. The project's existing toolchain (Python 3.12+/3.14, `uv`, `pytest`, `tomllib`, Textual) is unchanged.

### Core
No additions.

### Supporting
No additions.

### Alternatives Considered
Not applicable — no library decision exists in this phase's scope.

**Installation:**
```bash
# No new dependencies for this phase.
```

## Package Legitimacy Audit

Not applicable. This phase installs zero external packages (confirmed by reading every canonical-ref module above — all changes are to existing, already-reviewed first-party code and registry data). The Package Legitimacy Gate protocol is skipped per its own trigger condition.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────┐
                         │   installer/registry.toml    │
                         │ (Tool/Method/SkillLifecycle)  │
                         └───────────────┬───────────────┘
                                         │ tomllib load (installer/model.py)
                                         ▼
       ┌──────────────────────────────────────────────────────────┐
       │                     Evidence layer (pure)                  │
       │                                                            │
       │ installer/status.py::is_installed  ───┐                    │
       │   (PATH / detect_path / bin_dir / app) │                    │
       │                                        ▼                    │
       │ installer/install_ownership.py::detect_owner                │
       │   (_PROBES: brew/apt/dnf/pacman/rpm-ostree/pnpm/sdkman/...) │
       │                                        │                    │
       │ installer/ownership.py::resolve_ownership                   │
       │   (_collect_candidates → attribute_path → _native_owner     │
       │    → _os_package_owner → by-elimination → unknown)         │
       │                                        │                    │
       │ installer/skill_lifecycle.py::inspect_status  (NEW CALLER)  │
       │   (per-harness CLI probe, closed _status_probe table)       │
       └────────────────────────────┬───────────────────────────────┘
                                     │ ManagerOwnership / LifecycleOutcome
                                     ▼
       ┌──────────────────────────────────────────────────────────┐
       │           Caching / background worker layer                │
       │ installer/version_cache.py (ManagerSnapshot, staleness)     │
       │   extended: per-harness skill_pack cache entries (D-10/D-14)│
       │ catalog_tui.py::_refresh_versions_worker (Textual Worker)   │
       │   extended: a parallel/shared skill_pack refresh worker     │
       └────────────────────────────┬───────────────────────────────┘
                                     │ VersionStatus / OwnershipRefreshed msgs
                                     ▼
       ┌──────────────────────────────────────────────────────────┐
       │                     TUI rendering layer                    │
       │ installer/catalog_tui.py::_row_cells / _ver_cell / _owner_cell │
       │   extended: tri-state Inst cell (✓ / ○ / broken), "≠ policy"│
       │   marker, multi-host Owner truncation                       │
       │ installer/wizard_app.py::DoctorScreen                       │
       │   extended: guard-in-place per-file confirmation (D-21-24)  │
       └────────────────────────────┬───────────────────────────────┘
                                     │ user action (u / enter / apply)
                                     ▼
       ┌──────────────────────────────────────────────────────────┐
       │                      Mutation layer                        │
       │ installer/engine.py::install_tool (ALREADY_INSTALLED gate) │
       │ installer/update.py (ownership-first dispatch)             │
       │ installer/post_install.py::run_post_install (D-17/D-20)    │
       │ installer/rcclean.py + shellrc.py::path_export_guard (NEW)  │
       │   (guard-in-place write, backed by atomic.py .old backup)  │
       └──────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

No new top-level modules. All work lands inside existing files:

```
installer/
├── ownership.py          # D-01/D-02/D-06/D-07/D-08: Owner literal + sdkman branch
├── install_ownership.py  # D-01/D-05: fix _sdkman probe (kind + param key)
├── model.py               # D-09: widen SKILL_HARNESSES; D-19: per-method location field
├── skill_lifecycle.py     # D-09..D-15: per-harness status probe table, wire inspect_status
├── registry.toml          # D-09 data audit; D-19 kitty + audited location fields
├── status.py              # D-18: tri-state is_installed (or a parallel "broken" predicate)
├── deps.py                # D-17: satisfied_by_install must not silently drop outdated tools
├── engine.py              # D-17/D-20: ALREADY_INSTALLED path threading
├── post_install.py        # D-20: re-application gate on explicit re-selection only
├── catalog_tui.py          # D-02/D-12/D-13/D-18: row rendering, legend, Inst tri-state
├── wizard_app.py (DoctorScreen)  # D-16/D-21-D-24: reason text, guard-in-place UI
├── rcclean.py              # D-21: reuse unguarded_path_writers; add guard-in-place write
├── shellrc.py              # D-21: reuse path_export_guard's case-guard emission
└── atomic.py               # D-23: reuse staged_sibling/.tools-installer.old convention
```

### Pattern 1: Adapter, never a re-implemented probe (architecture.md rule 5)

**What:** Every new evidence source is added as a new branch/entry in an existing closed table (`_PROBES` in `install_ownership.py`, `_KIND_TO_OWNER`/`Owner` literal in `ownership.py`, `_status_probe` in `skill_lifecycle.py`), never a parallel mechanism.
**When to use:** Any time D-01 through D-15 need a new source of truth.
**Example (the sdkman fix, D-01/D-05):**
```python
# Source: installer/install_ownership.py:364-370 (read this session)
def _sdkman(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    candidates = _method_values(tool, {"script"}, "sdk_candidate") or (tool.id,)
    for candidate in candidates:
        output = _run(probe, ["sdk", "current", candidate])
        if output is not None and f"Using {candidate} version " in output:
            return Ownership("SDKMAN", "verified", f"sdkman lists {candidate}", package=candidate)
    return None
```
The fix is **not** a new function — it is correcting `{"script"}` → `{"sdkman"}` and `"sdk_candidate"` → `"candidate"` in the existing `_method_values` call, because `installer/registry.toml` declares `kind = "sdkman"` with a bare `candidate = "..."` param (verified at `installer/registry.toml:1759-1819` — `java`/`groovy`/`springbootcli`/`gradle`/`maven` all use exactly this shape). `springbootcli`'s fallback (`candidates = ... or (tool.id,)`) is also wrong for that one tool specifically — its registry `candidate` is `"springboot"`, not its `tool.id` of `"springbootcli"` — so the fallback-to-`tool.id` branch would probe the wrong SDKMAN candidate name even after the kind/key fix, unless `_method_values` is actually reached correctly (which, once the kind/key bug is fixed, it will be — the registry row carries `candidate = "springboot"` as a declared method param, so the *fixed* query finds it before ever reaching the broken fallback).

### Pattern 2: Owner literal extension is a closed-set edit with three required follow-ups

**What:** Adding `"sdkman"` to `ownership.py`'s `Owner` Literal type is not a one-line change — three sibling tables are exhaustiveness-tested against `Owner` (`OWNER_LABELS`, `OWNER_DETAIL_LABELS`, and `removal_hint`'s `_REMOVAL_COMMANDS`/`_REMOVAL_DESCRIPTIONS`), per the module's own comments at `ownership.py:949-951` and `:1021-1028`. Each must gain an `"sdkman"` entry or the existing exhaustiveness tests fail.
**When to use:** D-01's sdkman-ownership requirement.
**Example:**
```python
# Pattern already established at ownership.py:965-993 (OWNER_LABELS) and
# :1050-1061 (OWNER_DETAIL_LABELS) -- read this session, verbatim shape:
OWNER_LABELS: dict[Owner, str] = {
    "brew": "Homebrew",
    "cask": "Homebrew cask",
    "pnpm": "pnpm",
    "uv": "uv",
    "dnf": "dnf",
    "apt": "apt",
    "pacman": "pacman",
    "rpm-ostree": "rpm-ostree",
    "os-package": "OS package",
    "installer": "installer artifact",
    # "sdkman": "SDKMAN",  <- the new entry D-01 requires
}
```
`_collect_candidates` (ownership.py:774-838) also needs a new `elif method.kind == "sdkman" and inventory.sdkman_candidates is not None:` branch parallel to the existing brew/cask/node/uv-tool branches, which in turn means `ManagerInventory` (ownership.py:278-284) needs a new field and `read_inventory` needs a new query function — unless the plan instead routes sdkman through `_native_owner`'s sibling pattern (an adapter over `install_ownership.detect_owner`'s `_sdkman` probe, the same shape `_native_owner` already uses for dnf/apt/pacman/rpm-ostree). **This is a real design fork the planner must resolve, not research**: SDKMAN is a user-space manager like brew/pnpm/uv (mutable, should join `MUTATION_GRADE`-eligible owners, not `UNMANAGEABLE_OWNERS`), which argues for the `_collect_candidates`-branch shape (consistent treatment with brew/pnpm/uv) rather than the `_native_owner` adapter shape (reserved for OS package managers this installer structurally refuses to mutate). Recommend the `_collect_candidates` branch shape — it is the one that makes D-05's "update through the real owner" naturally reachable via the same `MUTATION_GRADE` path brew/pnpm/uv already use, with no separate refusal-set carve-out needed.

### Pattern 3: Closed per-harness probe table (D-10's skill_pack CLI mechanism)

**What:** `installer/host_setup.py`'s `HOST_SETUPS: dict[str, HostSetup]` (with `HostProbe(argv, contains)` tuples) is the *exact* existing precedent for "run this harness's own CLI and check for a substring" — and `install_ownership.py::_host_setup` already consumes it. D-10/D-11's skill_pack status mechanism should be a sibling closed table, not a rebuild.
**When to use:** Building the per-harness status probe that replaces `installer/model.py`'s current two-operation-ID `SkillOperation` model.
**Example:**
```python
# Source: installer/host_setup.py:12-41 (read this session) -- the shape to mirror
@dataclass(frozen=True)
class HostProbe:
    argv: tuple[str, ...]
    contains: str | None

HOST_SETUPS: dict[str, HostSetup] = {
    "pi": HostSetup(
        handoff=(...),
        probes=(HostProbe(("pnpm", "list", "--global", "--depth", "0", "--json"),
                           "@earendil-works/pi-coding-agent"),),
        owner="pnpm",
    ),
}
```
The current `installer/skill_lifecycle.py::_status_probe` (lines 51-60) hard-codes exactly two `if` branches (`codex_plugin_status`, `pi_package_status`) against `installer/model.py`'s closed `SKILL_OPERATION_IDS = ("codex_plugin_status", "pi_package_status")` tuple. D-09's corrected `supported_harnesses` for `superpowers` alone needs up to ten harness-status checks; extending this cleanly means either (a) adding one `*_status` operation_id + args dataclass per harness to `model.py` (closed-set growth, consistent with the existing pattern but verbose), or (b) collapsing to one generic `harness_status` operation_id with a `{harness, argv, contains}` args shape and a closed per-harness-name lookup table (mirrors `HOST_SETUPS`' shape more directly and scales to ten harnesses without ten dataclasses). Recommend (b) for the ten-harness scale this phase introduces.

### Anti-Patterns to Avoid
- **Second ownership-proof mechanism for D-19's per-method location field:** CONTEXT.md's own canonical-refs note (D-19's Reversibility clause) explicitly warns against "a second ownership-proof source once chosen is awkward to unwind across every method kind." The per-method location field must feed the *same* `attribute_path`/`owner_dirs` machinery `ownership.py` already uses, and the *same* `is_installed` union `status.py` already documents (its own docstring at `status.py:34-38` already states "The bin_dir check is a UNION with `which`, never a replacement" — D-19 generalizes that union, it does not add a second one).
- **A new skill_pack caching mechanism:** D-10/D-14 explicitly require reusing `installer/version_cache.py`'s existing staleness model (`VersionCacheEntry`, `is_stale`, `should_fetch`, the `managers` envelope key already used for `ManagerSnapshot`). A bespoke skill_pack JSON cache file would duplicate `_parse_iso`'s clock-skew handling and the atomic-write discipline for no reason.
- **Treating `inspect_status` as dead code to delete:** it has zero *production* callers today but is fully implemented and tested (`tests/test_skill_lifecycle.py` exercises it directly). The fix is to wire a caller (the background worker), not to rewrite the function.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Is this package actually installed, confirmed by the manager itself" | A new per-manager shell-out helper | `install_ownership.py`'s existing `_PROBES` table + `_run`'s fail-closed wrapper | Already handles untrusted-stdout hardening (`RecursionError` guard, `_PACKAGE_NAME_RE` injection guard) that a new helper would have to re-derive |
| "Which directory did this binary actually come from" | A bespoke path-prefix matcher per owner | `ownership.py::owner_dirs` + `attribute_path` | Already handles `/home` vs `/var/home` and `/var` vs `/private/var` double-spelling via `Path.resolve()`; a naive string-prefix check would silently miss both |
| Atomic, crash-safe rc-file rewrite with backup | A one-off `shutil.copy` + `open(...).write` | `installer/atomic.py`'s `atomic_write_text`/`staged_sibling`/`OLD_SUFFIX` convention | Already proven in Phase 15.8 for the identical class of file (foreign rc file); handles symlink targets, permission-bit preservation, and no-clobber backup refusal |
| Self-deduping PATH line text | A second string-template function | `installer/shellrc.py::path_export_guard` | Already proven safe against empty-PATH-becomes-cwd and `set -u` aborts; D-21's guard-in-place write should call this function, not reimplement its case-guard shape |
| Per-manager version/outdated caching with staleness windows | A skill_pack-specific JSON cache | `installer/version_cache.py`'s `ManagerSnapshot`/`is_manager_stale` | Same "ask once per session, respect a TTL, back off on failure" shape D-10/D-14 need |

**Key insight:** every "don't hand-roll" item in this phase is advice to reuse *this project's own* existing primitives, not a third-party library. The phase's actual risk is architectural drift (a second parallel mechanism solving the same problem slightly differently), not missing tooling.

## Runtime State Inventory

> Not a rename/refactor/migration phase. Omitted per the template's own trigger condition — this phase adds detection logic and corrects registry data; it does not rename any identifier, collection, key, or path that existing runtime state (installed tool state, shell rc files, SOPS keys, OS task registrations) already references by the old name.

## Common Pitfalls

### Pitfall 1: The sdkman probe's double mismatch (kind filter AND param key)
**What goes wrong:** `install_ownership.py::_sdkman` calls `_method_values(tool, {"script"}, "sdk_candidate")`. `installer/registry.toml`'s five SDKMAN tools (`java`, `groovy`, `springbootcli`, `gradle`, `maven`) all declare `[[tool.method]] kind = "sdkman"` with a bare `candidate = "..."` param — verified by reading `registry.toml:1759-1819` directly. Neither the kind (`"script"` vs. the registry's actual `"sdkman"`) nor the param key (`"sdk_candidate"` vs. the registry's actual `"candidate"`) matches, so `_method_values` always returns `()` and the function falls through to its `(tool.id,)` fallback — which happens to be correct for four of the five tools by coincidence (their SDKMAN candidate name equals their `tool.id`) but is wrong for `springbootcli` (candidate `"springboot"` ≠ `tool.id` `"springbootcli"`).
**Why it happens:** The probe was almost certainly written against an earlier or planned registry shape (`kind="script"` with a `sdk_candidate` param) that never shipped; the registry settled on `kind="sdkman"` + `candidate` instead, and the probe was never updated to match.
**How to avoid:** Fix both the kind filter and the param key in one change (`_method_values(tool, {"sdkman"}, "candidate")`), and keep the `(tool.id,)` fallback only as a true last resort — confirm with a test that `springbootcli` probes `sdk current springboot`, not `sdk current springbootcli`.
**Warning signs:** Any `_method_values(tool, {kind}, "...")` call where `{kind}` does not appear as a `kind = "..."` value anywhere near the tool's registry entry is dead code wearing a working-looking fallback.

### Pitfall 2: `ownership.py` has no sdkman owner at all, not just a broken probe
**What goes wrong:** Even after Pitfall 1 is fixed inside `install_ownership.py`, `installer/ownership.py` — the module that actually produces the `Owner` the TUI renders — has no `"sdkman"` member in its `Owner` Literal, no `"sdkman"` key in `_KIND_TO_OWNER`, and no `sdkman` branch in `_collect_candidates`. A SDKMAN-installed `java`/`groovy`/etc. resolves via the `script_method` by-elimination fallback at the bottom of `resolve_ownership` today purely by accident (because `kind="sdkman"` methods are not in `_INSTALLER_KINDS` either — `_INSTALLER_KINDS = frozenset((*DOWNLOAD_KINDS, *APP_KINDS, "script"))`, which does **not** include `"sdkman"`), meaning `competing_owners` returns an **empty set** for a pure-SDKMAN tool, `_unreadable` is therefore always empty for it, and the final `len(candidates) == 1 and not unreadable` / synthetic-script branches never fire either (no `script_method` exists for a `kind="sdkman"` tool). Verified by reading `ownership.py:142-184` (`_KIND_TO_OWNER`, `_INSTALLER_KINDS`) and the full `resolve_ownership` body (`:493-622`): a pure-SDKMAN tool with no competing brew/cask/node/uv-tool method falls through every branch to the final bare `return _unknown(...)` at line 611-622 — this is the live "groovy owned by Homebrew reads unknown" defect D-01 describes, but it is actually worse than CONTEXT.md states: **even a tool installed only through SDKMAN itself, with no brew competitor at all, reads `unknown` today**, because there is no SDKMAN candidate-collection branch to produce a positive claim in the first place.
**Why it happens:** SDKMAN support was added to `install_ownership.py`'s probe table (`_PROBES["sdkman"] = _sdkman`) but the adapter wiring into `ownership.py` that every other probed manager (brew, dnf, apt, pacman, rpm-ostree) receives was never completed for SDKMAN specifically.
**How to avoid:** Add `"sdkman"` to `Owner`, add a `_collect_candidates` branch keyed on `method.kind == "sdkman"` consulting a new `ManagerInventory.sdkman_candidates` field (populated via a new `read_inventory` query, e.g. `sdk current` or reading `~/.sdkman/candidates/*/current` symlinks directly per `status.py`'s own `bin_dir` convention), add `"sdkman"` to `OWNER_LABELS`/`OWNER_DETAIL_LABELS`/`_REMOVAL_COMMANDS`/`_REMOVAL_DESCRIPTIONS` (all four exhaustiveness-tested against `Owner`), and add `"sdkman"` to `_KIND_TO_OWNER` so `competing_owners` recognizes the method kind at all.
**Warning signs:** `ownership.py`'s own test suite (`tests/test_ownership.py`, 1901 lines) almost certainly has an exhaustiveness test over `typing.get_args(Owner)` (per the module's own comment at line 950) — adding `"sdkman"` to the Literal without filling in all four tables will fail that test immediately, which is a useful forcing function, not an obstacle.

### Pitfall 3: `SKILL_HARNESSES` is a closed ten-value tuple missing two hosts D-09's own correction needs
**What goes wrong:** `installer/model.py::SKILL_HARNESSES = ("antigravity", "claude", "codex", "copilot", "cursor", "kilo", "kimi", "opencode", "pi", "windsurf")` — verified by reading `model.py:64-74`. CONTEXT.md's D-09 states the upstream-verified `superpowers` support list is "Claude Code, Antigravity, Codex App/CLI, Cursor, Factory Droid, Gemini CLI, Copilot CLI, Kimi Code, OpenCode, and Pi." Two of those ten names — Factory Droid and Gemini CLI — have no corresponding value in `SKILL_HARNESSES`, and the registry's `supported_harnesses` field is validated against this exact tuple (`model.py`'s `_parse_closed_string_list` with `allowed=SKILL_HARNESSES`, used at the `skill_lifecycle` parse site). Writing `supported_harnesses = [..., "factory-droid", "gemini-cli"]` into `registry.toml` today would raise a `ValueError` at catalog load time.
**Why it happens:** `SKILL_HARNESSES` was defined against the harnesses this project's own catalog *installs* (`claude`, `codex`, `cursor`, `antigravity`, `opencode`, etc. — the AI-tier tools in `REQUIREMENTS.md`'s batch 3), not against the full universe of harnesses a third-party skill pack's upstream docs might list support for. `superpowers` is the first skill_pack whose true upstream support list exceeds this project's own installable-harness set.
**How to avoid:** Widen `SKILL_HARNESSES` (and whatever downstream exhaustiveness/label tables key off it) before or in the same commit as the `superpowers` registry data fix. Decide explicitly whether a harness this installer cannot itself install (Factory Droid, Gemini CLI) should even be *detectable* for skill_pack status purposes — if this installer has no way to probe Factory Droid's presence at all, D-11's "fall back to on-disk state for that harness" has no on-disk convention to fall back to either, and the honest row-state answer for that harness may simply be "unknown, not probed" rather than a fabricated presence check.
**Warning signs:** A registry TOML edit that raises `ValueError: unknown harness 'factory-droid'` at the test-suite's catalog-load step is this exact gap surfacing — do not work around it by silently dropping the two harnesses from the corrected list; that would re-introduce D-09's "factually wrong" defect in a new form.

### Pitfall 4: `inspect_status`'s `_status_probe` is a two-branch `if` chain against a two-value closed set — it does not scale to D-13's multi-host requirement as-is
**What goes wrong:** `installer/skill_lifecycle.py::_status_probe` (lines 51-60) is two literal `if operation.operation_id == "codex_plugin_status"` / `"pi_package_status"` branches, each unwrapping a *single* typed args dataclass. `installer/model.py::SkillLifecycle` carries exactly **one** `status: SkillOperation` field per tool (verified at `model.py:224-232`), not one per harness. D-13 requires "a pack installed in several hosts at once lists every host" — meaning the status check is inherently a *per-harness* question, but the current schema models status as a single tool-level operation.
**Why it happens:** The schema was built when only Codex and Pi had reviewed status operations and every skill_pack tool in the registry effectively had at most one meaningfully-probable harness (the other four skill_pack tools — `openspec`, `softaworks-agent-toolkit`, `matt-pocock-skills`, `opengsd`, `spec-kit` — are all `mode = "manual-required"` for status today, verified by reading every skill_pack block in `registry.toml:2770-3140`). D-09/D-10 push `superpowers` (and potentially others) to multi-harness support for the first time, which the current one-operation-per-tool schema cannot express.
**How to avoid:** This is a schema change, not a bug fix: either `SkillLifecycle.status` becomes a `tuple[SkillOperation, ...]` or a `dict[str, SkillOperation]` keyed by harness name, or (simpler, matching Pattern 3's recommendation above) `SkillOperation` gains a `harness: str` field and a tool can declare multiple status operations, one per supported+probable harness. The planner must pick one shape and migrate all five existing skill_pack entries' `[tool.skill_lifecycle.status]` blocks to it — this touches every skill_pack registry row, not just `superpowers`.
**Warning signs:** Any plan that tries to make D-13's multi-host Owner column work by calling `inspect_status` once per tool (today's signature) and expecting a multi-host answer back will discover `LifecycleOutcome.status` is a single `Literal["completed", "manual-required", "present", "absent", "unknown"]` — there is structurally nowhere to put "present on Claude Code, absent on Pi" in the current return type either.

### Pitfall 5: The Inst column is a bare boolean — D-18's "broken" state has no third slot to land in
**What goes wrong:** `installer/catalog_tui.py::_row_cells` (lines 497-523) renders the Inst column as `Text("✓", style="green") if installed else Text("○", style="yellow")`, where `installed = self._installed[tool.id]` is a plain `dict[str, bool]` populated from `installer.status.is_installed` (a `bool`-returning function). There is no third state. D-18 requires a distinct "broken" marker (shim present, package gone) that is neither ✓ nor ○.
**Why it happens:** `is_installed` was designed to answer a binary presence question before the "present-but-non-functional" case (mmdc's dangling pnpm shim) was discovered; the whole `_installed: Mapping[str, bool]` plumbing from `UnifiedApp` construction down through `CatalogScreen.set_installed` through `_row_cells` is boolean end-to-end.
**How to avoid:** Follow the precedent already set when the Owner column was added (15.4-01's own comment at `catalog_tui.py:182-184`: "a non-sorting column... deliberately left untouched") — add a **parallel** map (e.g. `self._broken: dict[str, bool]` or fold a tri-state into a new small enum) rather than overloading `bool` with a sentinel value, mirroring how Owner is a second data source alongside `_installed`, not a repurposing of it. `installer/status.py::is_installed` itself should very likely stay a pure presence boolean (PATH/bin_dir/detect_path/app union, unchanged) with a **new**, separate `is_broken`-shaped predicate (shim present via `is_installed`'s own checks, AND the owning manager's inventory says the backing package is absent) consumed only by the TUI layer and Doctor.
**Warning signs:** Any attempt to make `is_installed` return `bool | Literal["broken"]` will break every one of its many existing callers (`deps.py`, `engine.py`'s `ALREADY_INSTALLED` gate, `resolve_dependencies`) that treat its return as a plain truthy/falsy value in boolean contexts — this is a structural reason to keep `is_installed` boolean and add a sibling predicate instead.

### Pitfall 6: `satisfied_by_install` in `deps.py` drops an outdated tool with zero signal, by design today
**What goes wrong:** `installer/deps.py::resolve_dependencies` (verified by reading the full module) computes `satisfied_by_install = {t.id for t in wanted if is_installed(t) and t.id not in blocked}` and then excludes every id in that set from `runnable`/`order` entirely — an already-installed dependency produces no warning, no order entry, nothing. This is **by design** for the drag-in case (a dependency that's already there needs no action), but D-17 requires that *explicitly selecting* an already-installed, outdated tool for install still triggers an update-through-real-owner path with user-visible confirmation — a case this function was never asked to handle because it only answers "what does this selection set need as a dependency," not "what did the user explicitly ask to happen to this specific tool."
**Why it happens:** `resolve_dependencies`'s docstring is explicit that it answers one question (transitive drag-in + ordering) and is deliberately silent about per-tool action for already-satisfied dependencies, because historically "already installed" meant "nothing to do." D-17 introduces a case the function's contract never covered: "already installed, but the user explicitly picked it anyway."
**How to avoid:** D-17's logic does not belong inside `resolve_dependencies` at all — it belongs at the call site that turns a user's explicit selection into an action list (likely `installer/engine.py`'s `install_tool` dispatch loop, or a new pre-dispatch classification step that checks `is_installed` + `VersionStatus` for every *explicitly selected* tool before handing the remainder to `resolve_dependencies`). `resolve_dependencies` itself should stay exactly as documented — a dependency satisfied by install is still correctly excluded from drag-in ordering; D-17's enter-key behavior is a *different* code path layered on top, not a change to this function's contract.
**Warning signs:** A plan that edits `resolve_dependencies`'s `satisfied_by_install` set-comprehension directly to "fix" D-17 is solving the wrong layer — that set is also consulted by `missing_requires`' read-only preview and by every other caller that needs the drag-in-ordering semantics unchanged.

### Pitfall 7: Kitty has no Linux install method at all today — not even a wrong one
**What goes wrong:** `installer/registry.toml`'s `kitty` entry (lines 2516-2537, read this session) declares `dnf`/`apt`/`pacman` methods plus a macOS `cask` method — and nothing else. On immutable Bazzite, `resolve.py`'s `_applies` skips native package-manager kinds entirely (the documented immutable-Linux rule), so `kitty` resolves to **zero** applicable methods on this exact host — confirmed by the investigation CONTEXT.md's own "Specific Ideas" section describes (`~/.local/bin/kitty -> ~/.local/kitty.app/bin/kitty`, no `/usr/bin/kitty`). `docs/catalog-unsupported-tools.md` — the doc D-16 says reasons should cite — does **not** currently mention kitty at all (verified by reading the full file: only codegraph, Alacritty, and PyCharm/IntelliJ are documented there).
**Why it happens:** Kitty's own official userspace installer (a curl-based script dropping an app bundle at `~/.local/kitty.app`) was never modeled as a registry method — the registry only ever considered "native package manager" and "Homebrew cask" as kitty's possible install paths, missing the vendor's own install script entirely.
**How to avoid:** D-19 wants a new `kind="script"` (or equivalent) method for kitty on Linux, declaring its install location (`~/.local/kitty.app`, with the actual binary at `~/.local/kitty.app/bin/kitty` — note the **two-level** nesting: an `app`-style bundle path containing its own `bin/` directory, which is a new shape neither `status.py`'s existing `bin_dir` check (expects `<bin_dir>/<cmd>` directly) nor its `app`/`cask` check (expects a bare bundle directory under `~/Applications`/`/Applications`, with no reach into a nested `bin/`) currently handles cleanly). The planner must decide whether kitty's Linux method declares `bin_dir = "~/.local/kitty.app/bin"` (reusing the existing `bin_dir` union check verbatim, zero new code) or needs a genuinely new "app bundle with nested bin" location shape — reusing `bin_dir` as-is is almost certainly sufficient and is the minimal change.
**Warning signs:** Any plan that invents a new `app_root`/`install_root` schema field before checking whether the existing `bin_dir` param (pointed at the bundle's internal `bin/` subdirectory) already solves the detection problem verbatim is skipping the cheapest fix in favor of a new mechanism — check `status.py:46-56`'s existing `bin_dir` union logic first.

### Pitfall 8: `unguarded_path_writers` already works and already has callers — the only gap is the write action
**What goes wrong:** A plan that treats D-21 as "build a scanner for foreign unguarded PATH writers" would be redoing work that already exists and already ships in production (`installer/app.py:318` and `installer/wizard_app.py:2390` both call `scan_rc_path_writers`/`unguarded_path_writers` today, feeding `doctor_guidance`'s existing `duplicate_writers` parameter which already distinguishes the "nested shell, opens a new shell to clear" case from the "unconditional rc-file writer, needs editing" case — verified by reading `guidance.py:40-100` and `rcclean.py` in full).
**Why it happens:** CONTEXT.md's own canonical-refs section already states this precisely ("D-21-D-24 build the guard-in-place action on top of this existing detection, not a new scan") — this is flagged here only to make the point unmissable to the planner: D-21's actual new code is a *write* function (take a flagged line, rewrite it to `path_export_guard`'s case-guard form at the same file position, inside the existing backup-then-write flow), plus the DoctorScreen confirmation UI (D-24's per-file opt-in) and the D-22 same-tool-marked-block exclusion (which also already has a detection primitive to build on: `_managed_line_indices` in `rcclean.py` recognizes *this project's own* marked blocks — D-22's new work is recognizing and skipping *other* tools' marker-style blocks, e.g. `# >>> my-kitty PATH >>>`, which `_managed_line_indices` currently has no concept of at all since it only matches this project's own two literal marker strings).
**How to avoid:** Scope the plan narrowly: (1) a new function that takes a flagged unguarded line + its file + the managed directory and produces the case-guard replacement text at the same line position; (2) a generalized "any `# >>> ... >>>` / `# <<< ... <<<` marker pair, not just this project's own two literal strings" detector for D-22, since the current `_MANAGED_BEGINS`/`_MANAGED_ENDS` tuples in `rcclean.py` are hard-coded to exactly this project's own block markers and have no notion of a *foreign* tool's marker block at all; (3) the DoctorScreen per-file confirmation flow; (4) wiring the backup through `atomic.py`'s existing `.tools-installer.old` convention. None of this requires touching `unguarded_path_writers` itself.
**Warning signs:** A new top-level scanning function with "guard" or "foreign path" in its name that duplicates logic already in `find_duplicate_path_lines`/`unguarded_path_writers` is the anti-pattern to catch in review.

## Code Examples

### The existing `.tools-installer.old` backup convention (D-23 must reuse verbatim)
```python
# Source: installer/atomic.py:62-72 (read this session)
NEW_SUFFIX = ".tools-installer.new"
OLD_SUFFIX = ".tools-installer.old"

def staged_sibling(path: Path, suffix: str) -> Path:
    """`<name>.tools-installer.{new,old}` next to `path`, never a suffix on the parent."""
    return path.with_name(path.name + suffix)
```
Phase 15.8's full backup discipline (documented in `.claude/architecture.md`'s Phase 15.8 section, read this session): the backup is byte-exact (no CRLF normalization), no-clobber (a pre-existing backup with different bytes refuses the whole operation), checked via `lstat` so a symlink masquerading as the backup is rejected, and compares permission bits as well as content. D-23 says to reuse this "exact same" convention — the planner should call the same `atomic.py` primitives, not reimplement the refusal logic.

### The self-deduping case-guard emission D-21's rewrite must produce
```python
# Source: installer/shellrc.py:82-122 (read this session, signature + key properties)
def path_export_guard(directory: Path) -> str:
    """Emit a self-deduping PATH line that adds directory at most once per shell.
    ...
    The conditional expansion `${PATH:+:$PATH}` is security-critical: an empty
    PATH component resolves to the current working directory in every POSIX
    shell. The guard reads PATH through `${PATH-}` (default-applying
    expansion), not bare `$PATH`, so the line does not abort under `set -u`.
    """
```
D-21's guard-in-place rewrite should produce exactly this shape at the flagged line's position — not a hand-written case-guard string — so the two security properties (`set -u` safety, no-empty-PATH-component) are inherited rather than re-derived and potentially gotten wrong a second time.

### The existing stale-marker rendering convention D-12 reuses
```python
# Source: installer/catalog_tui.py:206 and :421-440 (read this session)
_VER_STALE = "~"
# _ver_cell appends this marker (dim style) to a cached version string when
# VersionStatus.stale is True -- the exact mechanism D-12 says the Inst
# column's "last cached answer while probing" state should reuse.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Ownership resolved only for brew/cask/pnpm/uv-tool + native OS managers | This phase adds SDKMAN as a first-class owner (D-01) | This phase | `competing_owners`/`_collect_candidates`/`Owner` all need the same four-table extension Pitfall 2 describes |
| skill_pack status checked for exactly 2 of 5 tools, via 2 hard-coded operation IDs | This phase needs per-harness status across up to 10 harnesses for multiple tools | This phase | Schema change in `model.py` (Pitfall 4), not just new registry rows |
| Inst column: binary ✓/○ | This phase adds a third "broken" state (D-18) | This phase | New parallel map, not a repurposed boolean (Pitfall 5) |
| `unguarded_path_writers`: report-only | This phase adds a write action (D-21) | This phase | New function layered on existing detection, not a new scanner (Pitfall 8) |

**Deprecated/outdated:** Nothing in this phase deprecates prior work outright — every existing mechanism (status.py's bin_dir union, version_cache.py's staleness model, rcclean.py's detection, atomic.py's backup convention, host_setup.py's probe-table shape) is extended, not replaced.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommending `_collect_candidates`-branch shape (not `_native_owner`-adapter shape) for SDKMAN ownership, on the grounds that SDKMAN is mutation-eligible like brew/pnpm/uv rather than refusal-only like dnf/apt/pacman | Architecture Patterns, Pattern 2 | If the planner instead wants SDKMAN treated as refusal-only (e.g. out of caution about SDKMAN's own update mechanics), the `MUTATION_GRADE`/`UNMANAGEABLE_OWNERS` wiring would need to go the other way; this is a design recommendation, not a verified requirement — D-05 itself ("update through its real, provable owner") only makes sense if SDKMAN-as-real-owner is mutation-eligible, which supports this recommendation but the planner should confirm intent explicitly |
| A2 | Recommending option (b) (one generic `harness_status` operation_id + closed per-harness lookup table) over option (a) (one dataclass per harness) for the skill_pack multi-harness status schema | Architecture Patterns, Pattern 3; Common Pitfall 4 | If the team prefers the existing codebase's established pattern of one typed dataclass per operation_id (as `CodexPluginStatusArgs`/`PiPackageStatusArgs` already do), option (a) is equally valid and more consistent with existing style, just more verbose at 10 harnesses |
| A3 | Recommending `bin_dir = "~/.local/kitty.app/bin"` as sufficient for kitty's Linux detection, without a new "app bundle with nested bin" schema shape | Common Pitfall 7 | If kitty's actual install script places the binary somewhere other than `<install-root>/bin/kitty`, this recommendation is wrong and the planner needs to verify kitty's actual official installer output layout directly (not done this session — CONTEXT.md's own live investigation only confirmed the `~/.local/bin/kitty -> ~/.local/kitty.app/bin/kitty` symlink target, which is consistent with this recommendation but was not independently re-verified here) |
| A4 | Whether SDKMAN should additionally be added to a `competing_owners`-recognized set for `_INSTALLER_KINDS` or stay entirely separate | Common Pitfall 2 | Low — this is a sub-detail of A1; getting it wrong only affects which fallback branch a SDKMAN tool with zero competing methods takes, not whether SDKMAN ownership attribution works at all once the primary branch (Pattern 2) is added |

## Open Questions (RESOLVED)

1. **Does `installer/registry.toml`'s `superpowers` row's other 9 tools need a corrected `supported_harnesses` audit too, or only `superpowers`?**
   - What we know: D-09 names `superpowers` explicitly as verified-wrong. The other four skill_pack tools (`openspec`, `softaworks-agent-toolkit`, `matt-pocock-skills`, `opengsd`, `spec-kit`) plus `ponytail` were read this session and their `supported_harnesses` lists look plausible on their face (they're all `mode="manual-required"` CLI-driven tools whose harness lists are narrower and match their own install-instruction text), but none were independently cross-checked against each tool's own upstream docs this session.
   - What's unclear: whether any of the other five have the same class of staleness `superpowers` had.
   - Recommendation: the planner should budget one verification pass per skill_pack tool against its own upstream README/docs before trusting any of the six `supported_harnesses` lists, per D-09's own instruction ("Every skill_pack entry's supported_harnesses must be re-audited").
   - **RESOLVED:** all packs are audited. Plan 16-07 Task 1 corrects `superpowers`; plan 16-07 Task 2 audits the remaining six against their upstream docs.

2. **Exact shape of the per-method install-location schema field (D-19)**
   - What we know: CONTEXT.md explicitly delegates this to the planner ("Exact registry schema shape for per-method install-location declarations (D-19) — a field name/structure decision for the planner, not a user-facing choice"). The existing `bin_dir`/`detect_path`/`app` params already cover most of the shape needed (Pitfall 7's recommendation).
   - What's unclear: whether a *new* field name is needed at all, or whether auditing+filling in the *existing* `bin_dir`/`app` params on every tool missing them is sufficient — i.e., is D-19 a schema change or a data-completeness audit?
   - Recommendation: attempt the kitty fix using only existing params (`bin_dir`) first; only introduce new schema if a tool is found during the audit whose real install location genuinely cannot be expressed by `bin_dir`/`detect_path`/`app`.
   - **RESOLVED:** no new field. Plan 16-01 reuses the existing `bin_dir` param as the per-method location proof (recorded as its D-19 design choice); plan 16-10 Task 1 expresses kitty with `bin_dir` too.

3. **Full list of other tools needing the same per-OS location audit beyond kitty**
   - What we know: CONTEXT.md explicitly defers this ("Full audit list of other tools needing per-OS location fixes beyond kitty (D-19) — to be discovered during research/planning, not pre-enumerated here").
   - What's unclear: no systematic audit of every registry tool's declared methods against their real install locations was performed this session (out of scope for a single research pass against a 3000+ line registry file).
   - Recommendation: the planner should scope a dedicated audit task/wave that checks every `script`/`app`/`cask` method's declared `bin_dir`/`app`/`detect_path` against the vendor's actual documented install layout, following the same live-verification convention `REQ-registry-authoring-verification-checklist` already established.
   - **RESOLVED:** plan 16-10 Task 2 is that dedicated location audit for own-installer script methods.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `uv run pytest --cov`, confirmed in `Makefile:50-51` and `pyproject.toml` presence) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_ownership.py tests/test_install_ownership.py tests/test_skill_lifecycle.py tests/test_rcclean.py -x` |
| Full suite command | `uv run pytest --cov` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-01/D-05 | SDKMAN-owned tool resolves to owner="sdkman", update dispatches through it | unit | `uv run pytest tests/test_ownership.py -k sdkman -x` | ✅ existing file, ❌ new sdkman-specific cases — Wave 0 |
| D-01 (probe fix) | `_sdkman` probe matches `kind="sdkman"`/`candidate` param | unit | `uv run pytest tests/test_install_ownership.py -k sdkman -x` | ✅ existing file (625 lines), extend with corrected-probe cases |
| D-02 | Off-policy tool row carries "≠ policy" marker | unit | `uv run pytest tests/test_catalog_tui.py -k off_policy -x` | ❌ Wave 0 — confirm `tests/test_catalog_tui.py` exists first |
| D-09 | `supported_harnesses` validated against (widened) `SKILL_HARNESSES` | unit | `uv run pytest tests/test_model.py -k skill_harnesses -x` | ❌ Wave 0 — confirm test file name/location |
| D-10/D-14 | skill_pack status cached with same staleness model as versions | unit | `uv run pytest tests/test_version_cache.py -x` (extend) | ✅ existing file likely present — confirm path |
| D-13 | Multi-host Owner column truncation | unit | `uv run pytest tests/test_catalog_tui.py -k multi_host -x` | ❌ Wave 0 |
| D-17/D-20 | Explicit re-selection of already-installed tool updates/confirms and re-applies post-install only on this path | unit | `uv run pytest tests/test_engine.py tests/test_post_install.py -x` | ✅ existing files likely present — confirm paths |
| D-18 | Dangling pnpm shim reads as distinct "broken" state | unit | `uv run pytest tests/test_status.py tests/test_catalog_tui.py -k broken -x` | ❌ Wave 0 |
| D-21/D-23/D-24 | Guard-in-place rewrite, backed up, per-file opt-in | unit | `uv run pytest tests/test_rcclean.py -k guard_in_place -x` | ✅ existing file (416 lines), extend |
| D-22 | Foreign marker block never touched | unit | `uv run pytest tests/test_rcclean.py -k marker_block -x` | ❌ Wave 0 |

*(Test file existence for `test_catalog_tui.py`, `test_model.py`, `test_engine.py`, `test_post_install.py`, `test_status.py` was not independently confirmed this session — the planner's Wave 0 should run `ls tests/` to verify exact filenames before committing to the commands above.)*

### Sampling Rate
- **Per task commit:** the narrowest `-k`-filtered pytest invocation matching the touched module
- **Per wave merge:** `uv run pytest --cov` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus the CONTEXT.md-mandated live proof against a real host reproducing each of the five original defects (the phase goal explicitly says "Proven against the real defects below on a host that reproduces each one" — this is not satisfied by unit tests alone and needs an end-of-phase manual/container verification step, consistent with prior phases' `human_verify_mode: end-of-phase` pattern already in `.planning/config.json`)

### Wave 0 Gaps
- [ ] Confirm existence and exact names of `tests/test_catalog_tui.py`, `tests/test_model.py`, `tests/test_engine.py`, `tests/test_post_install.py`, `tests/test_status.py`, `tests/test_version_cache.py`, `tests/test_deps.py` — not verified this session
- [ ] A fixture/helper for constructing a `Tool` with a `kind="sdkman"` method plus a competing `kind="brew"` method (the exact groovy-off-policy shape) — likely needs adding if `test_ownership.py` doesn't already have one for this specific dual-owner shape
- [ ] A fixture reproducing the dangling-pnpm-shim shape (shim file present, `pnpm list --global` output not listing the package) for D-18 — the pending todo file describes the live repro exactly; a test fixture mirroring it is new

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | This phase has no auth surface |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A — this is a local single-user CLI/TUI tool |
| V5 Input Validation | yes | Probe stdout from `brew`/`dnf`/`apt`/`pacman`/`rpm-ostree`/`pnpm`/`sdkman` is treated as untrusted (see `install_ownership.py`'s own module docstring, already fail-closed) — any new SDKMAN probe output parsing (Pitfall 1/2's fix) must follow the identical fail-closed, regex-guarded pattern (`_PACKAGE_NAME_RE`) already established, never trust-by-default a new manager's stdout shape |
| V6 Cryptography | no | No crypto surface touched in this phase (checksums.py is untouched) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A planted/corrupted manager binary earlier in PATH injects malicious ownership evidence | Spoofing / Tampering | Already mitigated by `install_ownership.py`'s fail-closed probe wrapper (`_run`), the `_PACKAGE_NAME_RE` guard against control characters, and `package_owns_path`'s "confirmation must be positive" rule — the new SDKMAN branch (Pitfall 1/2) must reuse these exact primitives rather than parsing `sk current <candidate>` output with a bespoke, unguarded regex |
| A foreign rc file's PATH line is rewritten incorrectly, corrupting the user's shell | Tampering / Denial of Service | Mitigated by reusing `atomic.py`'s crash-safe write + `.tools-installer.old` backup (D-23) and `path_export_guard`'s proven case-guard emission (D-21) rather than a hand-rolled string edit; the existing Phase 15.8 "byte-exact refusal" precondition must extend to this new write path too — a foreign file whose content changed between detection and the user's confirm-apply click should re-detect rather than blindly write at a stale line index |
| Writing inside another tool's marked block corrupts that tool's own regeneration logic | Tampering | D-22's explicit "never touched" rule is itself the mitigation — this is a locked decision, not a research gap |
| A dangling shim is silently "repaired" by reinstalling over user data the shim's package manager doesn't actually own | Tampering / Elevation of Privilege (loosely) | D-18's repair action must go through the *same* install path (`engine.py::install_tool` → the tool's real resolved method) as a normal install, never a bespoke "just re-link the shim" shortcut that could point it at the wrong package version |

## Sources

### Primary (HIGH confidence — read directly this session)
- `installer/ownership.py` (full file, 1254 lines)
- `installer/install_ownership.py` (full file, 417 lines)
- `installer/skill_lifecycle.py` (full file, 74 lines)
- `installer/status.py` (full file, 89 lines)
- `installer/version_cache.py` (full file, 362 lines)
- `installer/deps.py` (full file, 185 lines)
- `installer/post_install.py` (full file, 80 lines)
- `installer/rcclean.py` (full file, 192 lines)
- `installer/engine.py` (lines 1-220, the full `install_tool`/`InstallOutcome`/`_perform` section)
- `installer/model.py` (lines 1-704, the full `Method`/`SkillTarget`/`SkillOperation`/`SkillLifecycle`/`Tool` schema and closed-set constants)
- `installer/registry.toml` (lines 1740-1835 SDKMAN tools; lines 2510-2615 kitty/wezterm; lines 2770-3140 every skill_pack entry)
- `installer/update.py` (lines 1-80, module docstring and ownership-first dispatch doctrine)
- `installer/version_status.py` (stale-marker grep), `installer/catalog_tui.py` (lines 160-540, columns/legend/row-cells/ver-cell/owner-cell)
- `installer/host_setup.py` (full file, 41 lines — the existing probe-table precedent)
- `installer/resolve.py` (lines 1-100, `_RANK`/`_applies`/`resolve_methods`)
- `installer/atomic.py` (lines 1-80, atomic write + `.tools-installer.old` convention)
- `installer/shellrc.py` (lines 82-122, `path_export_guard`)
- `.claude/architecture.md` (Phase 15.8 section, lines 792-910)
- `docs/catalog-unsupported-tools.md` (full file)
- `.planning/todos/pending/2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md` (full file)
- `.planning/phases/16-.../16-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md` (full reads, per required_reading)
- `.planning/config.json` (confirms `nyquist_validation: true`, `security_enforcement: true`, test framework via `Makefile`/`pyproject.toml`)

### Secondary (MEDIUM confidence)
- None — this phase required no external web research; every claim traces to a first-party file read this session.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Ownership/sdkman findings (D-01–D-08): HIGH — both probe bugs independently re-derived by reading `install_ownership.py` and `registry.toml` side by side, not merely cited from CONTEXT.md
- skill_pack detection (D-09–D-15): HIGH on the current-state gaps (verified by reading `model.py`/`skill_lifecycle.py`/every skill_pack registry row), MEDIUM on the recommended schema-extension shape (Pattern 3 / Assumption A2) since that is a forward design choice, not a verified fact
- Row states / post-install (D-16–D-20): HIGH on current-state gaps (Inst column boolean, `deps.py` contract, kitty's missing method), MEDIUM on the exact new-field recommendation for D-19 (Assumption A3)
- Foreign PATH lines (D-21–D-24): HIGH — `unguarded_path_writers`'s existing callers and `path_export_guard`/`atomic.py`'s conventions were read directly and are unambiguous

**Research date:** 2026-10-09
**Valid until:** No external dependency; stays valid until the underlying modules are substantially refactored by a prior phase (unlikely — this is itself the phase that touches them). Treat as valid through this phase's completion; re-verify only if the planner discovers the codebase has diverged from this read between research and plan execution (e.g. a concurrent branch merge).
