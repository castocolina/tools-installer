# Phase 15: Catalog Accuracy — Doctor Refresh, Version Parsing, Ownership Attribution, Tier Fixes - Pattern Map

**Mapped:** 2026-09-14
**Files analyzed:** 8 (4 modified core modules, 1 modified registry, 1 modified comment-only file, 2 modified test files — `install_ownership.py` gains one new probe function, not a new file)
**Analogs found:** 8 / 8 (every file has a strong in-module or sibling-module analog; no new subsystem is introduced)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/wizard_app.py` (`DoctorScreen.action_apply`, `_refresh_body`) | controller (Textual screen) | request-response (event handler) | `DoctorScreen.on_mount`/`enter_view`/`on_globals_audited` — the SAME class's other three guidance-refresh call sites | exact (same class, same method shape, one is the documented outlier) |
| `installer/versions.py` (`_OBSERVED_VERSION`, `parse_version`, `parse_status_version`) | utility (pure parse function) | transform | itself — `parse_declared_version`'s already-separate, already-documented "why these parsers differ" precedent, plus the two existing `_OBSERVED_VERSION.fullmatch` call sites being unified | exact (extend existing module, no new file) |
| `installer/install_ownership.py` (new `_rpm_ostree` probe) | utility (probe function) | request-response (subprocess probe → parsed evidence) | `_dnf`/`_apt`/`_pacman` (lines 111-124) — same file, three sibling probes of the exact same shape | exact |
| `installer/ownership.py` (`resolve_ownership` gains `native_probe` param + adapter call; `Owner` Literal widened) | service (pure resolver + adapter) | transform, with one injected subprocess seam | itself — `resolve_ownership`'s own existing final-fallthrough `_unknown(...)` return, and `install_ownership.py::detect_owner` as the adapted source | role-match (new fallback branch composed from two existing, previously-disconnected modules) |
| `installer/update.py` (`_perform`, new native-owner refusal branch) | service (mutation dispatcher) | request-response with a pre-flight gate | itself — the existing SDKMAN refusal branch (lines 222-228) | exact (same file, same `if method... return UpdateOutcome(status="unsupported", ...)` shape) |
| `installer/registry.toml` (`ast-grep`, `puppeteer` tier fields; ~10 tools gain `owner_probes`) | config | CRUD (declarative) | itself — `rg`/`fd`'s existing `tier = "ai"` rows (category="search") as the D-07 target shape | exact (single-field edits, same TOML shape as any other tool) |
| `installer/ui_common.py` (AI-tab comment, ~line 129) | config/comment | n/a | itself — no code change, comment-only | exact (comment-only edit) |
| `tests/test_registry.py` (`test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`, `test_registry_tier_distribution_is_pinned`) | test | request-response (unit) | itself — same two tests, updated in place; `test_java_tools_install_exclusively_through_sdkman`-style "assert exactly N tools declare X" shape for a new `owner_probes` coverage test | exact (extend in place) + role-match (new coverage test) |

## Pattern Assignments

### `installer/wizard_app.py::DoctorScreen.action_apply` (controller, request-response)

**Analog:** `DoctorScreen.on_mount` (lines 253-256), `enter_view` (lines 270-272), `on_globals_audited` (lines 505-506) — three sibling methods in the SAME class that already call `_refresh_guidance()` immediately before `_refresh_body()`.

**Current bug, quoted verbatim** (`wizard_app.py:389-394`):
```python
def action_apply(self) -> None:
    if self.applied:
        return
    _, self.error = run_live(self._fix)
    self.applied = self.error is None
    self._refresh_body()
```

**Sibling pattern to copy** (`wizard_app.py:253-256`):
```python
def on_mount(self) -> None:
    self._refresh_guidance()
    self._refresh_body()
```

**D-01 fix — insert the same call in the same order:**
```python
def action_apply(self) -> None:
    if self.applied:
        return
    _, self.error = run_live(self._fix)
    self.applied = self.error is None
    self._refresh_guidance()
    self._refresh_body()
```

**D-02 — `_refresh_body`'s existing `if self.applied:` branch to extend** (`wizard_app.py:312-315`):
```python
if self.applied:
    text.append("PATH wired.", style="green")
    text.append("\nRestart your shell or run `source ~/.myshellrc` to apply.")
```
Append one more conditional line inside this SAME branch (exact wording is Claude's discretion; framing "expected, not broken" is locked):
```python
    text.append(
        "\nThe PATH audit above still reflects this process's starting PATH — "
        "that is expected until you open a new shell or `source ~/.myshellrc`."
    )
```
Note the `# Both counts come from...` comment block immediately below this branch (`wizard_app.py:328-332`) is the existing style precedent for explaining a "looks stale but isn't a bug" invariant inline — mirror that tone if the note needs a supporting comment above the `text.append` call.

---

### `installer/versions.py` (`_OBSERVED_VERSION`, `parse_version`, `parse_status_version`)

**Analog:** itself — the file's own `parse_declared_version` docstring precedent for documenting WHY two parsers with the same underlying regex diverge, plus the two existing `_OBSERVED_VERSION.fullmatch` call sites that must both change together.

**Current anchored regex, quoted verbatim** (`versions.py:29`):
```python
_OBSERVED_VERSION = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
```

**Call site 1 — `parse_version`** (`versions.py:43-` — confirmed function name, contract pinned by `tests/test_versions.py` and depended on by `meets_minimum`/`executors._require_minimum`/`pnpm_globals`):
```python
token = text.strip().split(maxsplit=1)
if not token:
    return None
match = _OBSERVED_VERSION.fullmatch(token[0])
if match is None:
    return None
```

**Call site 2 — `parse_status_version`** (`versions.py:129-141`, docstring explicitly distinguishes its contract from `parse_version`'s):
```python
match = _OBSERVED_VERSION.fullmatch(text.strip())
if match is None:
    return None
core = tuple(int(part) for part in match.group(1).split("."))
```

**D-03 fix — one new shared helper, both call sites switched to it in the same commit** (per RESEARCH.md Pattern 2 — do not duplicate the fallback logic at each site; that is exactly Pitfall 1):
```python
_NAME_PREFIX_BOUNDARY = re.compile(r".*[-\s](?=[vV]?\d)")


def _strip_name_prefix(token: str) -> str:
    match = _NAME_PREFIX_BOUNDARY.match(token)
    return token[match.end():] if match else token


def _match_observed_version(token: str) -> re.Match[str] | None:
    match = _OBSERVED_VERSION.fullmatch(token)
    if match is not None:
        return match
    return _OBSERVED_VERSION.fullmatch(_strip_name_prefix(token))
```
Then BOTH `match = _OBSERVED_VERSION.fullmatch(token[0])` (in `parse_version`) and `match = _OBSERVED_VERSION.fullmatch(text.strip())` (in `parse_status_version`) become `match = _match_observed_version(...)` on the same argument each already computes — no other line in either function changes.

**Docstring precedent to mirror for the new helper** — `parse_declared_version`'s docstring (`versions.py:80-90`) is this file's established style for explaining a parser's divergence from a sibling; `_match_observed_version`'s docstring should explain the prefix-split fallback the same way (why it exists, why `jq-1.8.1` needs it, why it is tried SECOND not instead).

---

### `installer/install_ownership.py` (new `_rpm_ostree` probe)

**Analog:** `_dnf` (lines 111-116), `_apt` (lines 101-109), `_pacman` (lines 119-124) — three sibling probe functions in the same file, identical shape: `_method_values(tool, {kind}, "package")` → `_run(probe, [...])` → `_lines`/parse → `Ownership(...)` or `None`.

**`_dnf`, quoted verbatim as the shape to mirror most closely** (`install_ownership.py:111-116`):
```python
def _dnf(tool: Tool, probe: ProbeRunner) -> Ownership | None:
    for package in _method_values(tool, {"dnf"}, "package"):
        output = _run(probe, ["rpm", "-q", "--qf", "%{NAME}\\n", package])
        if output is not None and package in _lines(output):
            return Ownership("dnf", "verified", f"dnf lists {package}")
    return None
```

**D-06 — new `_rpm_ostree`, same package source (the tool's `dnf`-method package, since rpm-ostree layers from the same repos), different (JSON, booted-deployment-scoped) inventory:**
```python
def _rpm_ostree(tool: Tool, probe: ProbeRunner) -> Ownership | None:
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

**Registration site — the existing `_PROBES` dict** (`install_ownership.py:167-176`):
```python
_PROBES: dict[str, Callable[[Tool, ProbeRunner], Ownership | None]] = {
    "managed-download": _managed_download,
    "host-setup": _host_setup,
    "brew": _brew,
    "apt": _apt,
    "dnf": _dnf,
    "pacman": _pacman,
    "pnpm": _pnpm,
    "sdkman": _sdkman,
}
```
Add `"rpm-ostree": _rpm_ostree,` as a new entry — the ONE closed-set schema addition needed in `installer/model.py`'s `OWNER_PROBES` (RESEARCH.md confirms dnf/apt/pacman are already valid members, just unused by any row today; only `"rpm-ostree"` is new).

---

### `installer/ownership.py` (`resolve_ownership` adapter, `Owner` Literal widen)

**Analog:** itself — the existing final fallthrough `_unknown(...)` return this adapter is inserted immediately before, and `install_ownership.detect_owner` as the source being adapted (D-05 explicitly forbids re-deriving probe logic here — `.claude/architecture.md` rule 5, no duplicate helpers).

**Current closed `Owner` type, quoted verbatim** (`ownership.py:61`):
```python
Owner = Literal["installer", "brew", "cask", "pnpm", "uv", "unknown"]
```
Must widen to include `"dnf"`, `"apt"`, `"pacman"`, `"rpm-ostree"` — `pyright --strict` rejects the adapter's `ManagerOwnership(owner="dnf", ...)` construction otherwise (no exhaustive `match`/`assert_never` on `Owner` exists elsewhere per RESEARCH.md's grep audit, so this widen is self-contained).

**`MUTATION_GRADE`, quoted verbatim, the gate the adapted value must satisfy** (`ownership.py:64`):
```python
MUTATION_GRADE: frozenset[str] = frozenset({"direct", "by-elimination"})
```

**`resolve_ownership` signature to extend** (`ownership.py:304`) gains one new keyword-only parameter:
```python
def resolve_ownership(
    tool: Tool,
    *,
    ...,
    native_probe: ProbeRunner | None = None,  # NEW — None in every existing
                                                # call/test, byte-identical
                                                # behavior unless injected
) -> ManagerOwnership:
```

**Adapter call, inserted immediately before the existing final fallthrough** (the existing `_unknown(...)` return, lines ~508+ per `_unknown`'s definition site):
```python
if native_probe is not None:
    native = install_ownership.detect_owner(tool, native_probe)
    if native.confidence == "verified":
        return ManagerOwnership(
            owner=native.owner,       # "dnf"/"apt"/"pacman"/"rpm-ostree"
            confidence="direct",      # D-05's locked confidence adaptation
            ...                       # remaining fields per ManagerOwnership's
                                       # existing constructor contract
        )
return _unknown(tool, candidates=candidates, ...)
```
Production wiring: `native_probe` should be `install_ownership.run_probe` (isolates stdin — required because `VersionRefreshService.refresh` runs on a Textual worker thread while the main thread holds the terminal in raw/alt-screen mode, per RESEARCH.md's explicit Anti-Pattern warning against substituting `installer.run.run_query`).

---

### `installer/update.py::_perform` (new native-owner refusal branch)

**Analog:** itself — the existing SDKMAN refusal branch, same file, same function, same shape (a pre-flight `return UpdateOutcome(status="unsupported", ...)` before any mutation is attempted).

**Existing SDKMAN branch, quoted verbatim, the exact pattern to mirror** (`update.py:222-228`):
```python
if method is not None and method.kind == "sdkman":
    return UpdateOutcome(
        tool_id=target.tool.id,
        status="unsupported",
        owner=ownership.owner,
        detail=_SDKMAN_DETAIL,
    )
```

**Existing owner-dispatch ladder this bug falls through today** (`update.py:231-245`):
```python
owner = ownership.owner
cleanup_warnings: tuple[str, ...] = ()
if owner in ("brew", "cask", "uv"):
    argv = resolve_update_argv(target)
    if argv is None:
        raise UpdateError(f"missing argv for {owner} update")
    runner(argv)
elif owner == "pnpm":
    ...
elif owner == "installer":
    ...
else:
    raise UpdateError(f"unsupported owner {owner!r}")
```

**D-05/Pitfall-3 fix — a new refusal branch BEFORE the owner-dispatch ladder** (mirroring the SDKMAN branch's placement and shape, not a new `elif` inside the mutation ladder — this must never attempt a privileged dnf/apt/pacman/rpm-ostree mutation):
```python
_NATIVE_MANAGER_DETAIL = (
    "This tool is owned by the OS package manager; update it through "
    "dnf/apt/pacman directly — this installer does not perform privileged "
    "system-package-manager mutations."
)

if ownership.owner in ("dnf", "apt", "pacman", "rpm-ostree"):
    return UpdateOutcome(
        tool_id=target.tool.id,
        status="unsupported",
        owner=ownership.owner,
        detail=_NATIVE_MANAGER_DETAIL,
    )
```
Place this check immediately after the existing SDKMAN branch (or immediately before it — order between the two unsupported-owner short-circuits does not matter, both must precede the owner-dispatch `if/elif/.../else` at line 231) so the `else: raise UpdateError(...)` at line 245 is never reached for these four owner names.

---

### `installer/registry.toml` (`ast-grep`, `puppeteer` tier fields + `owner_probes`)

**Analog:** itself — `rg`/`fd`'s existing `tier = "ai"` rows for the D-07/D-08 target shape.

**Target shape, quoted verbatim** (`registry.toml`, `rg`/`fd` rows, per RESEARCH.md's direct read):
```toml
category = "search"
audience = "ai"
tier = "ai"
```

**D-07 — `ast-grep`:** change `tier = "user"` → `tier = "ai"` (single-field edit, `category = "search"` stays unchanged, matching `rg`/`fd`'s existing shape).

**D-08 — `puppeteer`:** change `tier = "user"` → `tier = "ai"` (single-field edit; `desc` field already reads "Required at runtime by mmdc." — no other field changes).

**D-04/D-06 — `owner_probes` additions** (new field, ten rows: `rg`, `jq`, `git`, `zsh`, `watch`, `docker`, `podman`, `kitty` get `owner_probes = ["dnf", "apt", "pacman", "rpm-ostree"]`; `opencode`, `wezterm` get `owner_probes = ["pacman"]` only, since they declare no dnf/apt method). Follows the same single-field, declarative-list-addition shape as Phase 14's `post_install = ["set_login_shell"]` precedent on `oh-my-zsh` (`14-PATTERNS.md`) — add the key inside the existing `[[tool]]` block, never inside `[[tool.method]]`.

---

### `installer/ui_common.py` (D-10, comment-only fix)

**Current stale comment, quoted verbatim** (`ui_common.py:127-133`):
```python
        # This tab groups the whole AI-coding ecosystem, not "what the AI runs
        # by itself": it mixes agent CLIs you drive yourself (claude, codex)
        # with CLIs built to be called BY an agent (rg, codegraph). "Tier"
        # here means "bootstrap-order/install-flow bucket", not "who uses
        # it" -- that's the separate Audience tab inside this screen (human /
        # AI / both), worth checking if that distinction matters to you.
```
`claude`/`codex` are both `tier="user"` today — contradicts the comment. Fix: replace the two named examples with tools confirmed `tier="ai"` (Claude's discretion per CONTEXT.md; RESEARCH.md suggests `rg`, `fd`, `codegraph` as safe, already-accurate replacements — all three remain `tier="ai"` before AND after this phase's D-07/D-08 edits, so the comment stays accurate once `ast-grep`/`puppeteer` also join that set). No code logic changes — this is a comment-text-only edit, same `View(...)` call structure untouched.

---

### `tests/test_registry.py` (pinned tests, extend in place)

**Analog:** itself, both tests, updated in the same commit as the registry edit (per RESEARCH.md Pitfall 4 — these are deliberate tripwires, not bugs to silently work around).

**`test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`, quoted verbatim tuple assertion** (`tests/test_registry.py:585-593`):
```python
def test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm() -> None:
    puppeteer = next(t for t in load_tools(REGISTRY) if t.id == "puppeteer")
    assert (
        puppeteer.name,
        puppeteer.category,
        puppeteer.cmd,
        puppeteer.priority,
        puppeteer.audience,
        puppeteer.tier,
    ) == ("Puppeteer", "dev", "puppeteer", "P3", "both", "user")
```
D-08 fix: rename the test to `test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm` (the function's NAME encodes the wrong tier per RESEARCH.md, not just its body) and change the tuple's last element from `"user"` to `"ai"`. A sibling `ast-grep` tier assertion (new test, same file, same shape) should be added for D-07 if none exists yet — search `tests/test_registry.py` for an existing `ast-grep`-specific test before adding a duplicate.

**`test_registry_tier_distribution_is_pinned`, quoted verbatim** (`tests/test_registry.py:928-935`):
```python
def test_registry_tier_distribution_is_pinned() -> None:
    # Deliberate tripwire: any phase that adds or removes a registry entry
    # (ROADMAP Phases 7 and 8 both will) must update these counts in the same
    # commit that changes the catalog.
    assert dict(Counter(t.tier for t in load_tools(REGISTRY))) == {
        "system": 26,
        "ai": 15,
        "user": 48,
    }
```
D-07+D-08 fix: update the expected `Counter` dict to `{"system": 26, "ai": 17, "user": 46}` (two tools move `user`→`ai`) in the SAME commit as the registry edit.

**New coverage test for `owner_probes` (D-04/D-06)** — mirror `test_java_tools_install_exclusively_through_sdkman`'s "assert exactly N tools declare X" shape (same file, an existing analog for this exact assertion style) to pin which ten tool ids declare `owner_probes` and with what value, preventing silent scope creep beyond the enumerated ten-row table.

## Shared Patterns

### Guidance-refresh ordering invariant (D-01)
**Source:** `DoctorScreen.on_mount`/`enter_view`/`on_globals_audited` (`wizard_app.py:253-256,270-272,505-506`)
**Apply to:** `action_apply` — every guidance-affecting event in this class calls `_refresh_guidance()` immediately before `_refresh_body()`; `action_apply` was the sole outlier and must now match.

### Pre-flight refusal, never a runtime exception (D-05/Pitfall 3)
**Source:** `installer/update.py`'s existing SDKMAN branch (lines 222-228)
**Apply to:** the new dnf/apt/pacman/rpm-ostree refusal branch in `_perform` — a clean `UpdateOutcome(status="unsupported", ...)` returned BEFORE the owner-dispatch ladder, never an `UpdateError` raised from the ladder's `else` clause.

### Sibling-probe shape (D-06)
**Source:** `install_ownership.py`'s `_dnf`/`_apt`/`_pacman` (lines 101-124)
**Apply to:** the new `_rpm_ostree` probe — same `_method_values` → `_run(probe, [...])` → parse → `Ownership(...)`/`None` shape, registered in the same `_PROBES` dict.

### No duplicate probe logic (D-05, `.claude/architecture.md` rule 5)
**Source:** `installer/ownership.py`'s own module docstring (lines 1-37) explicitly anticipating dnf/apt/pacman/rpm_ostree as future "inventory reader" work
**Apply to:** `resolve_ownership`'s new adapter — calls `install_ownership.detect_owner` rather than reimplementing any subprocess/parse logic inline.

### Single-field declarative registry edits
**Source:** `installer/registry.toml`'s existing `rg`/`fd` rows (tier) and Phase 14's `oh-my-zsh` `post_install` addition precedent (`14-PATTERNS.md`)
**Apply to:** `ast-grep`/`puppeteer` tier changes and the ten `owner_probes` additions — one or two keys changed per `[[tool]]` block, no restructuring.

## No Analog Found

None — every file in this phase's scope has a strong same-module or sibling-module analog; no new subsystem, dispatcher, or file is introduced (`install_ownership.py` gains a function, not a file; `ownership.py` gains a parameter and a branch, not a new resolution mechanism).

## Metadata

**Analog search scope:** `installer/wizard_app.py`, `installer/versions.py`, `installer/install_ownership.py`, `installer/ownership.py`, `installer/update.py`, `installer/registry.toml`, `installer/ui_common.py`, `tests/test_registry.py`
**Files scanned:** 8 target files, all read directly this session (verbatim line numbers confirmed live, not taken solely from RESEARCH.md)
**Pattern extraction date:** 2026-09-14
