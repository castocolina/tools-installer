# Phase 15: Catalog Accuracy — Doctor Refresh, Version Parsing, Ownership Attribution, Tier Fixes - Context

**Gathered:** 2026-09-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Four independent "the catalog/doctor shows something untrue" bugs bundled by "found running the shipped v0.49.0 installer on a real machine" (ROADMAP.md, urgent insertion after Phase 12):

1. **Doctor's stale post-fix guidance:** `DoctorScreen.action_apply` (`installer/wizard_app.py`) never calls `_refresh_guidance()` after a successful fix — only `_refresh_body()` — so the screen shows pre-fix guidance next to the success line.
2. **Version detection false-negative on non-bare-semver output:** `_OBSERVED_VERSION` (`installer/versions.py`) is anchored (`fullmatch`) against the first whitespace-split token; `jq --version` prints `jq-1.8.1` as a single token, which never matches, so `jq` always shows "unknown."
3. **Real OS-package-manager ownership detection disconnected:** `installer/install_ownership.py::detect_owner` already has working `_apt`/`_dnf`/`_pacman` probes, but neither `installer/ownership.py` (the live resolution path) nor `installer/version_status.py` ever calls it — such tools always resolve to `owner="unknown"`. No probe exists yet for Bazzite's rpm-ostree/just-layering equivalent.
4. **Tier misclassification:** `ast-grep` and `puppeteer` are tier-misclassified under the tier definition in `.claude/architecture.md`; `mmdc`/`gitleaks`/`vale`/`drawio-cli` were reviewed as borderline and confirmed correct as-is. `installer/ui_common.py`'s AI-tab comment (~line 130) still describes `claude`/`codex` as living in the `ai` tier, though they are `tier="user"` today.

</domain>

<decisions>
## Implementation Decisions

### Doctor refresh
- **D-01:** `action_apply` calls `self._refresh_guidance()` (not just `self._refresh_body()`) after a fix succeeds, so the guidance list reflects the new state before rendering. — **Reversibility:** reversible.
- **D-02:** A note explaining the PATH check's deliberately-frozen state appears **conditionally**, only when `self.applied` is `True` — e.g. "PATH check still reflects the pre-fix state — this is expected until you open a new shell or source `~/.myshellrc`." It does not show before the fix is applied (nothing frozen to explain yet). — **Reversibility:** reversible.

### Version parsing
- **D-03:** `_OBSERVED_VERSION`'s matching gains a name-prefix split: when the raw token doesn't match directly, split at the last `-` (or whitespace) immediately preceding a segment that starts with a digit or `v`/`V`, and apply the existing regex to that trailing segment only. This is a generic mechanism, not a per-tool prefix table — no registry schema change. — **Reversibility:** reversible.
- **D-04:** After the fix, audit `installer/registry.toml` for other tools whose `--version` output plausibly has a similar non-bare-semver shape, and confirm the new split logic covers them (or note any that still need special-casing). — **Reversibility:** reversible.

### Ownership wiring
- **D-05:** `installer/ownership.py`'s live resolution path calls `install_ownership.py::detect_owner` for the `dnf`/`apt`/`pacman` cases, adapting its `"verified"` confidence to `ownership.py`'s own `MUTATION_GRADE` vocabulary as `"direct"` — no duplicate probe logic is written inside `ownership.py`, per that module's own docstring rationale and `.claude/architecture.md` rule 5 (no duplicate helpers). — **Reversibility:** costly — later separating the two confidence vocabularies again would mean re-touching every call site that now expects the adapted value.
- **D-06:** A new rpm-ostree/just-layering probe is added to `install_ownership.py`, following the exact pattern of the existing `_dnf`/`_apt`/`_pacman` probes (a `ProbeRunner`-injected command, e.g. `rpm-ostree status --json`), and wired through the same D-05 adapter — not deferred to a future phase. — **Reversibility:** reversible.

### Tier fixes
- **D-07:** `ast-grep`: `tier = "user"` → `tier = "ai"` (same family as `rg`/`fd`, already `ai` — a structural-search tool typically invoked by an agent, not typed by the human). — **Reversibility:** reversible.
- **D-08:** `puppeteer`: `tier = "user"` → `tier = "ai"` (a runtime library dependency of `mmdc`, never launched directly by the human — matches the `ai`-tier definition's "operates underneath ... never launched directly by the human as their own interface"). — **Reversibility:** reversible.
- **D-09:** `mmdc`, `gitleaks`, `vale`, `drawio-cli` stay `tier = "user"` — reviewed against `.claude/architecture.md`'s tier criterion and confirmed correct: each is directly invoked by the human on their own artifact (diagram, repo scan, prose, export), not infrastructure "consumed by" an agent underneath. This closes the "borderline" review named in ROADMAP.md — no further tier review deferred. — **Reversibility:** reversible.
- **D-10:** Fix `installer/ui_common.py`'s stale AI-tab comment (~line 130) — it still names `claude`/`codex` as examples of agent CLIs in the `ai` tab, but both are `tier="user"` since an earlier session. Update the comment's examples to tools that are actually `tier="ai"` today (e.g. `rg`, `fd`, `codegraph`). — **Reversibility:** reversible.

### Claude's Discretion
- Exact wording of the D-02 PATH-frozen note (as long as it makes the "expected, not broken" framing explicit).
- Which specific `ai`-tier tools to cite as the corrected examples in the D-10 comment fix.
- The exact command/flags used by the D-06 rpm-ostree probe (e.g. `rpm-ostree status --json` vs `rpm-ostree status -b` parsing) — implementation detail, not a user-facing decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Doctor refresh
- `installer/wizard_app.py` — `action_apply` (~line 378), `_refresh_guidance` (~line 279), `_refresh_body` (~line 293).

### Version parsing
- `installer/versions.py` lines 26-29, 60-77, 138-151 — `_OBSERVED_VERSION` regex and its two call sites (`parse_observed_version`-shaped functions).
- `installer/registry.toml` — full registry, to be audited for other non-bare-semver `--version` outputs per D-04.

### Ownership wiring
- `installer/ownership.py` — full module docstring (lines 1-37) explains the `MUTATION_GRADE`/confidence model and explicitly anticipates dnf/apt/pacman/rpm_ostree as "out of scope for Phase 12... a matter of adding an inventory reader" — this phase is that inventory-reader wiring.
- `installer/ownership.py:64` — `MUTATION_GRADE: frozenset[str] = frozenset({"direct", "by-elimination"})`.
- `installer/install_ownership.py` — full module: `detect_owner`, `_apt`/`_dnf`/`_pacman`/`_brew`/`_pnpm`/`_sdkman`/`_managed_download`/`_host_setup` probes, the `Ownership` dataclass with `confidence: Literal["verified", "unknown"]` — the adapter's source model.
- `installer/model.py:271-272` — `owner_probes` field and the comment referencing `install_ownership.py`.

### Tier fixes
- `.claude/architecture.md` lines 249-274 — "Tool onboarding: tier, dependencies, and postinstall classification," the authoritative tier-classification criterion applied to all 6 tools in this discussion.
- `installer/registry.toml` — entries for `ast-grep` (~line 1834), `puppeteer` (~line 2399), `mmdc` (~line 2280), `gitleaks` (~line 2000), `vale` (~line 2029), `drawio-cli` (~line 2639), `claude` (~line 1337), `codex` (~line 1313).
- `installer/ui_common.py` lines 125-137 — the stale AI-tab comment (D-10).

### Roadmap source
- `.planning/ROADMAP.md` lines 475+ — Phase 15's full urgent-insertion description (source of all four bug reports).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `install_ownership.py::detect_owner` and its probe functions — production-ready dnf/apt/pacman detection logic; this phase wires it in rather than writing new probes for those three managers.
- `MUTATION_GRADE` frozenset — the existing confidence-gating primitive the D-05 adapter must feed into correctly (an adapted "direct" value must satisfy the same guarantees a native "direct" result would).

### Established Patterns
- `installer/ownership.py`'s "evidence rule" (a claim is only made on active-path match or complete negative evidence, everything else `unknown`) — the D-05/D-06 adapter must preserve this; an adapted probe result cannot be treated more permissively than a native one.
- `.claude/architecture.md` rule 5 (no duplicate production helpers with the same behavior) — directly cited as the reason not to reimplement dnf/apt/pacman probes natively in `ownership.py`.
- Tier classification is a manual/reviewed process, not lint-enforced (`.claude/architecture.md` line 274) — consistent with this phase resolving the borderline tier calls by discussion rather than an automated rule.

### Integration Points
- `installer/ownership.py`'s resolution flow (wherever it currently returns `unknown` for dnf/apt/pacman-owned tools) is where the D-05 adapter call is inserted.
- `installer/version_status.py` — also named in ROADMAP.md as never calling the real probes; verify during planning whether it calls into `ownership.py` (and thus gets D-05 for free) or needs its own wiring.

</code_context>

<specifics>
## Specific Ideas

No exact UI text was dictated for the D-02 PATH-frozen note or the D-10 comment rewrite — both left to Claude's discretion within the stated framing. The tier-fix decisions (D-07 through D-09) were reached by applying `.claude/architecture.md`'s existing written criterion to each of the 6 named tools and confirming the result with the user in one pass, rather than one-by-one negotiation — the criterion itself was not new, only its application to these specific tools.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. The "borderline" tier review (`mmdc`/`gitleaks`/`vale`/`drawio-cli`) that might have been deferred to a future phase was instead resolved now (D-09), closing it rather than leaving it open.

### Reviewed Todos (not folded)
None — no todo cross-reference matches surfaced for this phase.

</deferred>

---

*Phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at*
*Context gathered: 2026-09-13*
