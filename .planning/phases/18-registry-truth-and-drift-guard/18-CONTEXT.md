# Phase 18: Registry truth and drift guard - Context

**Gathered:** 2026-10-13 (assumptions mode, `--analyze --all --batch`, jev screening, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

Every registry entry matches its upstream release and this host. Pins are bumped to the latest stable release, checksummed and dated. A weekly check opens one GitHub issue when upstream drifts.

The WHAT is locked in `18-SPEC.md` (R1–R11). R2 was amended in this session from a `# Verified` comment to a structured `verified` key, and R11 gained the explicit `version` key. This file locks the HOW.

Out of scope: receipts and health (19); script `paths`/`remove`/`update`/`writable_prefix` and `config_paths` (22); the `cargo_distrobox` kind (24); bot PRs for drift.
</domain>

<decisions>
## Implementation Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. Every option below was checked against that rule.

### Schema: closed keys, `verified`, pins (R1, R2, R11)
- **D-01:** Add `METHOD_PARAMS: dict[str, frozenset[str]]` to `installer/model.py`, following the existing `METHOD_KINDS`/`OWNER_PROBES` convention.
  - `load_tools` (`model.py:654-668`) checks `set(params) - METHOD_PARAMS[kind]` first and raises `tool '<id>': method '<kind>' has unknown key '<k>'`.
  - The existing per-kind value-shape checks stay as they are.
  - Phases 22 and 24 add keys by editing one dict entry.
  - `tests/test_model.py:803-827` (`test_non_node_method_leaves_new_keys_untouched`), which locks in the opaque pass-through, is rewritten to expect rejection.
- **D-02 (user):** Each `[[tool]]` gets a structured `verified = YYYY-MM-DD` key (a native TOML date).
  - `load_tools` requires it and rejects non-date or future values, with the tool id in the message.
  - `verify-registry` writes the key as data.
  - The 34 existing `# Verified …` comment dates seed the keys; the free-text notes stay as comments.
  - A `verified` key on a method table is rejected by D-01.
  - SPEC R2, REQUIREMENTS REG-02, ROADMAP and the specs for 22/24.1 were updated to say so.
- **D-03 (user):** Pinned `app`/`tarball` methods carry `version = "X"` and template their URL with `{ver}`.
  - The loader requires `version` when a pinned kind's URL contains `{ver}`.
  - A bump edits one value.
  - `github_release` methods keep resolving `{ver}` from the live tag and are never pinned.
- **D-04:** draw.io's `cli_name` is honored in exactly one place: `installer/apps.py` `cli_spec` (:47-65).
  - `uninstall.py` imports the same function, so install and removal naming stay single-sourced.
  - This fixes the macOS bug where `which("drawio")` never finds the link named `draw.io`.

### Verification pipeline (R4, R5)
- **D-05:** Add a digest fallback to `installer/checksums.py`, e.g. `expected_sha256_from_api(...)`.
  - It is tried only when the pinned checksum is absent; the order is checksum file → API digest → "unverified" with a reason.
  - A digest mismatch raises the existing `ChecksumMismatch`, so `engine.py`'s fail-fast branch (:146-151) covers it with no new engine logic.
  - Evidence that the API exposes a digest: `audit-2026-10-13/D-registry-user-part1.md:199` (live 2026-10-13).
- **D-06 (user):** The smoke run is one shared function (e.g. `smoke(path, argv)`) built on `run_output`/`CommandError`.
  - It fails on exit 126/127, an OSError, or a `GLIBC_`/loader error in stderr.
  - **download and app kinds** call it on the staged binary **before** the atomic link swap, so a broken binary is never linked and an existing good link is untouched.
  - **Manager kinds** call it after install, on `shutil.which(tool.cmd)`.
  - A failure falls through to the next method in the ladder.
  - A declared custom probe uses a new key, distinct from the existing closed-dispatch `smoke` name key (`model.py:13`), so the two trust models are not mixed.
  - Smoke runs on install, not on the single-method update path.

### verify-registry and the weekly job (R3, R11)
- **D-07:** A new `installer/verify_registry.py` reuses `download._resolve_target` and `assets.render_asset`/`arch_tokens` for each declared `os`/`arch`.
  - This keeps one URL, member and checksum resolver, so a passing check means the real install works.
  - Newer-release detection reuses `versions.resolve_github_tag`.
  - The issue upsert shells out to `gh` through the existing `run.py` `Runner`: find the one open drift issue by label, then edit it or create it.
  - Exit "inconclusive" on a network error or rate limit, with no issue call.
- **D-08:** `make verify-registry` is read-only. `.github/workflows/verify-registry.yml` runs on `schedule` plus `workflow_dispatch` only, with `permissions: contents: read, issues: write`. It is never in the PR gate.
- **D-09:** The pin bump (R11) runs `verify-registry` on the candidate version and changes `version` and `verified` only when it passes. A renamed or removed asset keeps the old pin and is reported.

### Data, detection and launch fixes (R6–R10)
- **D-10 (user):** The macOS stub rule is a closed table in `installer/status.py`, consulted by `is_installed` (:18-66).
  - `/usr/bin/java` maps to `/usr/libexec/java_home` exiting 0.
  - `/usr/bin/git` maps to `xcode-select -p` exiting 0.
  - A stub without the real tool counts as not installed, with a reason.
- **D-11:** The `--no-dev` change covers every `setup.py` launcher: Makefile `setup`, `run`, `doctor`, `fix`, `uninstall`, `guard` and `unguard` (:14-32), plus `install.sh:88`.
  - `validate` and `test` are untouched.
  - A Makefile test asserts both sides.
- **D-12:** `managed-download` removal touches exactly `model.py:57`, `install_ownership.py:83-89,376` and `registry.toml:2721`. The `:2770` row disappears with `drawio-cli`.
  - Acceptance: `rg managed-download installer/` returns nothing.
- **D-13:** `drawio-cli` is removed and `drawio-desktop` becomes `audience = "both"`.
  - A stale `drawio-cli` id is ignored: lookups are registry-driven (`version_cache.py:176-190`).
  - The planner must also grep `settings.py` for any id-validated selection state, and add an explicit drop-unknown branch there if one exists.
  - A regression test pins this behaviour either way.
- **D-14:** `versions.py` `parse_version` (:54) returns `None` for `-1`-like output. It parses lazygit's `version=0.44.1, …` and unquotes procs' output. These are covered by a parametrized test over the audit fixtures.
- **D-15:** The 35 data fixes are applied as written in audits C/D/E/F, "Registry fixes (data only)". Sublime's `member` is skipped because Phase 17 did it. Each fix maps to a test or to a `verify-registry` pass.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. Schema (D-01..D-03), because the data must satisfy the new loader.
  2. The data fixes and seeding `verified`.
  3. The verification pipeline.
  4. `verify-registry` and the weekly job.
  5. Pin bumps last, because they need the tool.
- The exact names of the new functions and keys (the custom-smoke-argv key, the drift issue label).

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/18-registry-truth-and-drift-guard/18-SPEC.md` — locked R1–R11 (R2/R11 amended 2026-10-13)
- `.planning/phases/17-stop-the-bleeding/17-CONTEXT.md` — prior decisions (link safety, Sublime member)
- `.planning/research/2026-10-13-target-architecture.md` §4.2 (schema change), §9.2 (O6, O12)
- `.planning/research/audit-2026-10-13/C-registry-system.md`, `D-registry-user-part1.md`, `E-registry-user-part2.md`, `F-registry-ai.md` — "Registry fixes (data only)" sections and live evidence
- `.planning/REQUIREMENTS.md` — REG-01..10
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/assets.py` `arch_tokens`/`render_asset`; `installer/download.py:85-127` `_resolve_target`
- `installer/checksums.py` `expected_sha256`/`sha256_file`/`ChecksumMismatch`
- `installer/run.py` `run_output`/`CommandError` (normalizes OSError and non-zero exit)
- `installer/versions.py` `resolve_github_tag`, `Fetch`/`urlopen_fetch`
- `installer/model.py` closed-set conventions (`_parse_closed_string_list`, `OWNER_PROBES`, `POSTINSTALL_HOOK_NAMES`)
- `installer/atomic.py` `replace_symlink` (Phase 17) for the swap after a passing smoke run

### Established Patterns
- Error messages follow `f"tool '{id}': ..."`.
- `ChecksumMismatch` is the one hard-fail type; other executor errors fall through the ladder.
- The registry drives dispatch: removing a key or probe disables it.

### Integration Points
- `model.load_tools` ← every loader caller and test (wide blast radius; the data fixes must land with the schema)
- `engine.install_tool` → `download.install_download`/`apps.install_app` (smoke before link) → `status.is_installed`
- `install_ownership._PROBES` ↔ `model.OWNER_PROBES` ↔ registry drawio rows
- `apps.cli_spec` ↔ `uninstall.py`
- Makefile launch targets + `install.sh:88` ↔ `--no-dev`
- New Makefile target `verify-registry` ↔ new workflow ↔ new `installer/verify_registry.py`
</code_context>

<specifics>
## Specific Ideas

- The live macOS draw.io bug (link named `draw.io` while `cmd = "drawio"`) is the acceptance anchor for D-04.
- The difftastic pre-fix asset template is the drift fixture for verify-registry (SPEC R3).
</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `detect-dangling-pnpm-global-bin-shims-in-doctor` (score 0.6) belongs to Phase 21 (UI-07).
</deferred>
