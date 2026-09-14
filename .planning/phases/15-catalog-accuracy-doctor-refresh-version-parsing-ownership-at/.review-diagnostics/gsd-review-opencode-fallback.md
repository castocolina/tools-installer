I'll review the five plans against the live code, not the plan text. Loading the review skill and reading the files they cite.
This is a grounded plan review, not an orchestrator run. I'll check each plan's claims against the live source.
Confirmed DoctorScreen skips `_refresh_guidance` and versions has two independent `fullmatch` sites. Next I'll ground ownership, update dispatch, registry, and tests.
I have the ownership and Doctor bugs. Next I'll check tests, registry rows, catalog labels, and the composition-root wiring.
Checking registry tripwires, native-manager rows, composition-root wiring, and a few test helpers the plans depend on.
Need the native-manager tool IDs, catalog update gate, setup wiring, and a few test helpers.
Checking composition-root wiring, the catalog update gate, and a few remaining type/test details.
Checking a few more load-bearing paths: `competing_owners`, `resolve_status` owner branches, `run_live`, and the AI-tab palette.
Checking a few remaining call sites that could break after `Owner` is widened.
Verified the live tree. The five plans match the code; 15-05 correctly moves the native fallback *before* the `active_path` unknown return that research placed too late.

## 15-01

**Summary.** Small, correctly-scoped fix for the one Doctor event that renders without recomputing guidance. Sibling call sites at `installer/wizard_app.py:253-256`, `:270-272`, and `:505-506` already pair `_refresh_guidance()` then `_refresh_body()`; `action_apply` at `:389-394` is the outlier (`self._refresh_body()` only). The plan treats D-01 as an ordering invariant and D-02 as the visible “expected, not broken” note, and it does not pretend the PATH audit can change inside one process.

**Strengths**
- Grounded in the real refresh contract: `_refresh_guidance` is IO-free (`:290-302`) and re-reads `self._guard_state()`, so a flipping `guard_status` callable is a real signal. `_predicate` / `_app` already accept that callable (`tests/test_wizard_app.py:85-100`, `:165-191`).
- Test asserts the rendered `#doctor-body`, matching `test_doctor_screen_adapts_missing_path_guidance_for_tui` (`:282-292`), so it proves ordering rather than a silent `self.guidance` write.
- Keeps the note DoctorScreen-local. `guard_guidance` (`installer/guidance.py:73-105`) has no `applied` concept; `make doctor` has no apply action.
- Explicitly forbids asserting that the missing-PATH finding disappears — `self._report` is a process-lifetime snapshot.

**Concerns**
- **MEDIUM — verify gate does not catch a success-gated refresh.** Task 1 requires refresh on failed apply (`run_live` maps `OSError` to `self.error` at `installer/ui_common.py:47-50`). The ORDER-OK extractor only keeps lines containing `_refresh_guidance()` / `_refresh_body()`, so this still passes:

```python
if self.error is None:
    self._refresh_guidance()
self._refresh_body()
```

`fails_when` claims it would fail; the assertion would not. CONTEXT D-01 also says “after a fix succeeds,” which an implementer may follow literally.
- **LOW — failed-apply behavior is specified but not named as its own test.** Task 1’s behavior list includes the OSError path; action/verify only pin the success + once-only path.

**Suggestions**
- Assert `self._refresh_guidance()` is not indented under `if self.error is None`, or add a Pilot test: `fix` raises `OSError`, `applied is False`, error text is shown, no crash.
- Keep Task 2’s required word `audit`; CONTEXT’s example (“PATH check”) would fail the NOTE-IN-APPLIED-BRANCH gate.

**Risk:** LOW. Two localized edits; the only real hole is the success-gated refresh slipping the source gate.

## 15-02

**Summary.** Correct shared-helper design for the two independent `_OBSERVED_VERSION.fullmatch` sites (`installer/versions.py:70` and `:141`). Fixing only `parse_version` would display `jq-1.8.1` while `is_outdated` (via `parse_status_version`) stayed `None` — Pitfall 1 is real. The prefix-split is narrow, fail-closed, and leaves `parse_declared_version` (`:80-91`) strict.

**Strengths**
- One helper, both call sites, same commit. `extract_observed_version` (`:116-126`) returns the verbatim token, so `is_outdated("jq-1.8.1", "1.8.2")` is the proof the second parser moved.
- Retry reuses `_OBSERVED_VERSION`, so `group(1)` / `group(2)` stay stable. Direct match still wins for `1.2.3` / `v1.2.3` / `25.10.0-rc.1`.
- Existing None cases stay None: `version=0.64.1` is preceded by `=`, not `[-\s]`; `gron version dev` never yields a numeric token (`tests/test_versions.py:248-250`).
- D-04 records `procs` / `bash` as residuals with `# Verified` + substring test, matching `.claude/architecture.md` registry-authoring practice. Does not widen the boundary class.

**Concerns**
- **LOW — `parse_status_version` still fullmatches the entire stripped string** (`:141`). After this fix that is correct for the verbatim token `jq-1.8.1`; a raw multi-token line still would not parse. Callers already go through `extract_observed_version`. Not a defect — don’t “fix” it here.
- **LOW — wezterm/cursor-agent date-hash false positives** are correctly left as a SUMMARY fast-follow. Do not pin them.

**Suggestions**
- Keep the three `prefix`-named tests on `parse_version`, `extract_observed_version`, and `is_outdated` as separate tests so a later revert of one call site is visible.
- Quote `5.3.9(1)-release` and the `Not covered:` marker exactly; a bare `bash` substring is too weak, as the plan already says.

**Risk:** LOW. Pure, IO-free, well-tested, no schema change.

## 15-03

**Summary.** Two one-field registry moves plus tripwire updates, with D-09 pinned instead of left in a discussion log. Live data matches the plan: `ast-grep` is `category="search"` / `tier="user"` (`installer/registry.toml:1834-1841`) beside `rg`/`fd` at `tier="ai"` (`:81-87`); `puppeteer.desc` already says it is required at runtime by mmdc (`:2399-2408`). The AI-tab comment at `installer/ui_common.py:129-134` still names `claude`/`codex`.

**Strengths**
- Updates the tripwires in the same commit: `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` (`tests/test_registry.py:584-593`) encodes the wrong tier in its name; `test_registry_tier_distribution_is_pinned` (`:928-936`) is `{"system": 26, "ai": 15, "user": 48}` and documents that catalog edits must update it.
- D-09 group pin is the right way to close the borderline review; `test_reconciliation_tier_audit_confirms_all_11_re_added_rows` (`:945-966`) already pins `drawio-cli` as user — overlap is harmless if the new test is a group, not a second drawio-only assertion.
- Tier is a browsing label; `tests/test_deps.py` in the verify gate is the right non-regression for `mmdc.requires`.
- D-10 test re-derives cited ids from the live registry rather than hardcoding names.

**Concerns**
- **MEDIUM — user-visible palette is the same stale claim and is out of scope.** `palette="AI - agents you run and tools agents call"` (`installer/ui_common.py:135`) is the header users see. Task 2 forbids changing any View field so `test_tier_views_lead_the_nav_and_match_the_tier_enum` (`tests/test_ui_common.py:234-241`) stays green — that test does not read `palette`. Leaving it contradicts D-10’s goal.
- **MEDIUM — whole-word id scan false-positives.** Registry ids include `just`, `code`, `git`, `watch`, `pi`, `bat`, `sd`. A comment that says “just the tools an agent calls” would fail `AI-TAB-OK` even with no intended citation. The verify regex is the same (`\\b` + id).
- **LOW — `jq` remains `tier="user"` with `audience="ai"` (`registry.toml:119-125`).** Out of D-09’s named set; don’t expand, but don’t let a drive-by “fix” land either. The Counter gate will catch an extra move.

**Suggestions**
- Update the palette in the same comment task. It is copy, not structure; keep `name`/`mode`/`actions` untouched.
- Isolate the comment slice tightly (between `name="ai"` and `palette=`, as the gate already does) and cite only distinctive ids (`codegraph`, `ast-grep`, `rg`) so `just`/`code` cannot match English.
- Rename the puppeteer test so `-k puppeteer` still selects it.

**Risk:** LOW–MEDIUM. Data edits are right; the leftover palette and the comment scanner are the execution risks.

## 15-04

**Summary.** The right first half of Bug 3: probes and opt-in data, no live wiring yet. `detect_owner` (`installer/install_ownership.py:179-185`) iterates `tool.owner_probes` and indexes `_PROBES` directly — an unregistered name is a `KeyError`. Only three rows declare the field today (`pi`, `drawio-desktop`, `drawio-cli`). Native dnf/apt/pacman methods exist on exactly ten tools (26 `kind = "dnf"|"apt"|"pacman"` lines = 8×3 + 2×1). `OWNER_PROBES` (`installer/model.py:55-64`) has no `"rpm-ostree"`. `_applies` returns `False` for `rpm_ostree` (`installer/resolve.py:70-73`), so the probe cannot key off that method kind.

**Strengths**
- Mirrors `_dnf` (`install_ownership.py:111-116`): `_method_values` → `_run` → parse → `Ownership | None`.
- Booted-deployment + `requested-packages` is the live JSON shape; a non-booted hit is specified as `None`.
- Fail-closed on malformed JSON / missing keys / non-list / absent binary, via `_run`’s existing swallow (`:55-59`) plus `json.loads` try/except including `KeyError` (stricter than `_pnpm` at `:148-151`).
- Hyphenated `"rpm-ostree"` matches `OWNER_PROBES` style (`"managed-download"`, `"host-setup"`), not `METHOD_KINDS`’s `rpm_ostree`.
- `rpm-ostree` first in `owner_probes` is load-bearing: `_dnf` is `rpm -q`, which still answers on ostree hosts.
- Pinning the ten-id set turns a forgotten new dnf row into a red test — the silent gap this phase exists to close.
- Honest about the one-wave architecture-rule-5 orphan; 15-05 is the caller.

**Concerns**
- **LOW — `packages` vs `requested-packages`.** A package pulled in only as a layered dependency is in `packages` but not `requested-packages`, so it falls through to `_dnf`. The plan accepts this; don’t add a third probe.
- **LOW — per-refresh cost.** Eight tools will each run `rpm-ostree status --json`. Research timed this well under a second; don’t cache here.
- **LOW — verify `Tool(...)` fixtures** must keep explicit `priority`/`audience`/`tier`. `Tool.__init__` currently defaults them (`model.py:285-287`); the plan already warns.

**Suggestions**
- Extend `_manager_for` with `"rpm-ostree": "rpm-ostree"` so `_probe` can serve the new command (`tests/test_install_ownership.py:26-35` keys on `command[0]`).
- Re-run the mechanical `kind = "dnf"|"apt"|"pacman"` scan before editing expected sets if `registry.toml` moved after 15-03.
- Put `owner_probes` on the `[[tool]]` table, above the first `[[tool.method]]` — a key after that header is a method field and will fail load or silently vanish.

**Risk:** LOW. Probe + schema + ten opt-ins; no mutation path yet.

## 15-05

**Summary.** This is the load-bearing plan, and it corrects research rather than copying it. `resolve_ownership` returns unknown for a live unattributable path at `installer/ownership.py:333-345` *before* the final `_unknown` at `:374-385`. A `/usr/bin/jq` dnf install takes that earlier branch (`attribute_path` only knows installer/brew/cask/pnpm/uv dirs, `:232-271`). A fallback placed only at the end would pass every no-PATH unit test and do nothing on a real machine. Mapping `verified` → `direct` then requires a `_perform` refusal: `direct` is in `MUTATION_GRADE` (`:64`), the dispatch `else` raises `UpdateError(f"unsupported owner {owner!r}")` (`installer/update.py:244-245`), and `perform_update` turns that into `status="failed"` (`:186-201`) — worse than today’s pre-flight unknown-owner refusal.

**Strengths**
- Placement is specified as after `if active_candidate is not None:` (`ownership.py:322-332`) and before `if active_path is not None:` (`:333`). One call site covers live-unattributable-path *and* no-path.
- Adapter-only: `detect_owner`, no new subprocess in `ownership.py`. Translation table is the closed set of four native names; `"Homebrew"` from `_brew` (`install_ownership.py:97`) cannot leak onto this path.
- Complete-negative-evidence guard (empty `candidates` *and* empty `unreadable`) preserves `test_linux_system_package_manager_is_unknown_by_design` (`tests/test_ownership.py:357-381`) when no probe is injected.
- Refusal is a sibling of the SDKMAN branch (`update.py:222-228`), before the ladder, not an `elif` that looks like a future `sudo dnf upgrade`. `_NATIVE_OWNER_DETAIL` is grep-stable even if the condition is a tuple of four names.
- `run_probe` (`install_ownership.py:30-39`: `stdin=DEVNULL`, `timeout=5`) at both composition-root sites (`setup.py:573-591` currently wires neither). Catalog vs mutation cannot disagree.
- `resolve_status` final branch (`version_status.py:324-336`) already yields `latest=None`, `source="unknown"` for these owners — correctly left alone (`source` is where *latest* came from).
- No second gate in `action_update_tool` (`catalog_tui.py:574-577`). Native+direct passes `MUTATION_GRADE`, `UpdateService.run` (`update.py:368-375`) also lets it through, and `_perform` is the single refusal wording. Today a native owner with no label would drop the `unknown_reason` sentence (`catalog_tui.py:391-400` `labels.get` → None, and `:411` only runs for `owner == "unknown"`).

**Concerns**
- **MEDIUM — native winner may be absent from `candidates`.** `_owned` will be called with the empty tracked-manager tuple while `owner="dnf"`. The script by-elimination path passes `candidates=(synthetic,)` (`ownership.py:365-370`). Shadowed UI iterates `ownership.candidates` (`catalog_tui.py:401-406`). Pass `candidates=(synthetic,)` (and `shadowed=False`) so the record is self-consistent.
- **MEDIUM — leftover installer artifacts block native attribution.** If `~/.local/bin/jq` exists, `_collect_candidates` adds an installer candidate (`ownership.py:403-410`). The helper then returns None (`candidates` nonempty), and the live `/usr/bin/jq` still falls into the unattributable-path unknown. Fail-closed and consistent with the evidence rule, but the catalog will still say unknown on a machine that has both a stale download and a dnf install. Worth one test so it is a decision, not a surprise.
- **LOW — `resolve_update_argv` (`update.py:149`) still raises for `dnf`.** `_perform` will not call it if the refusal is first; don’t add a native branch there.
- **LOW — size.** Ten files is five modules + five test modules; Tasks 1+2 are the honesty minimum. Don’t split Task 1 from Task 2.

**Suggestions**
- Widen `Owner` with the hyphenated `rpm-ostree`; never `rpm_ostree`. No `cast` / `# type: ignore`.
- Default `VersionRefreshService.native_probe` to `None`, not `run_probe` — otherwise unit tests spawn `rpm -q`.
- Task 3 labels must say both the manager *and* that this installer will not update it; a bare “managed by dnf” is a downgrade from today’s `unknown_reason` (`ownership.py:547-551`).
- Keep `test_linux_system_package_manager_is_unknown_by_design` unmodified; add `-k native` siblings.

**Risk:** MEDIUM. Highest blast radius in the phase, but the plan names the actual landmines (placement, Literal widening, privileged-update refusal, stdin isolation, label gap). Complexity, not a missing design.

---

## Cross-plan

Wave 1 file split is real: 15-01 `wizard_app.py`, 15-02 `versions.py`, 15-03 `registry.toml` + `ui_common.py`. 15-04 correctly `depends_on: ["15-03"]` (shared `registry.toml` / `tests/test_registry.py`). 15-05 correctly `depends_on: ["15-04"]`.

Splitting Bug 3 across 15-04 (probe + opt-in) and 15-05 (adapter + refusal + wiring) is better than the original four-plan sketch: widening `Owner` without a producer, or wiring `direct` without a `_perform` branch, is worse than doing nothing.

jq is the accidental end-to-end fixture: 15-02 parses `jq-1.8.1`, 15-04 opts its dnf/apt/pacman methods into `owner_probes`, 15-05 attributes `/usr/bin/jq` and refuses `u`. No file overlap.

**Phase risk: MEDIUM**, almost entirely 15-05’s mutation-surface coupling. 15-01–15-04 are low-risk if the 15-01 success-gated-refresh hole and the 15-03 palette/scanner issues are closed in-plan. Do not ship 15-04 without 15-05; together they satisfy D-05/D-06.
