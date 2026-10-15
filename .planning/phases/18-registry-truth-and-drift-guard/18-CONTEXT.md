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
- **D-05 (audited 2026-10-14):** The tag and the asset digests come from **one** `/releases/latest` fetch.
  - `installer/versions.py` gains `resolve_github_release(repo, fetch) -> Release`. `Release` is a frozen dataclass holding `tag` and `digests: Mapping[str, str]` (asset name → sha256 hex, taken from each asset's `digest` field after stripping the `sha256:` prefix).
  - `resolve_github_tag` becomes `resolve_github_release(repo, fetch).tag`. The 12 tag-only `TagResolver` callers do not change.
  - The download context gets a `resolve_release` resolver. `download._resolve_target` takes `github_release` methods through it, so the URL tag and the expected digest come from the same snapshot. A separate digest call would add a second rate-limited read, and "latest" can move between the two reads.
  - Order: pinned checksum → `release.digests[asset]` → "unverified" with a reason. Pinned `app`/`tarball` methods carry a pinned checksum (D-09 writes it), so they never need a digest lookup.
  - A digest mismatch raises the existing `ChecksumMismatch`, so `engine.py`'s fail-fast branch (:146-151) covers it with no new engine logic.
  - The version refresh stores `Release.digests` in the version cache next to `latest_version`. Phase 19 D-09 adopts pre-receipt raw binaries against these digests, with no new network call.
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
  - Newer-release detection and digests reuse `versions.resolve_github_release` (D-05).
  - **Check method (audited 2026-10-14):** every run compares API digests and probes each URL with HEAD. It downloads and opens an archive (the `member` check) only when the asset's digest differs from the last verified one or no digest exists. Downloading every asset for every OS/arch each week is wasted bandwidth and gives no extra signal. Checking API metadata alone would miss a renamed member.
  - The issue upsert shells out to `gh` through the existing `run.py` `Runner`: find the one open drift issue by label, then edit it or create it.
  - Exit "inconclusive" on a network error or rate limit, with no issue call.
- **D-08:** `make verify-registry` is read-only. `.github/workflows/verify-registry.yml` runs on `schedule` plus `workflow_dispatch` only, with `permissions: contents: read, issues: write`. It is never in the PR gate.
- **D-09:** The pin bump (R11) runs `verify-registry` on the candidate version and changes `version` and `verified` only when it passes. A renamed or removed asset keeps the old pin and is reported.
  - **Registry writes (audited 2026-10-14):** a scoped line rewrite, with no new dependency.
    - Every table in `registry.toml` uses a header (`[[tool]]` ×90, `[[tool.method]]` ×230), and the target keys are one-line scalars.
    - The writer finds the `[[tool]]` block by `id`, plus the method block where one is targeted, and replaces only the `verified =`, `version =` or checksum line inside it.
    - It then re-parses the whole file with `tomllib` and asserts that the result equals the old document plus exactly the intended edits. Any other difference aborts the write. Comments and layout are untouched by construction.
    - tomlkit was rejected because its output would still need the same semantic guard, and it would add a dependency for one writer. jev: TypeSafe chose the line rewrite at p=0.58, below the confidence floor, so this decision was reasoned through in full rather than taken from jev.

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
  - Resolved 2026-10-14: `settings.Settings` persists only `link_mode` and no tool ids, so no settings branch is needed. The only other references are the tests at `tests/test_registry.py:1118-1120, 1135-1142, 1168-1173, 1966`; update them in the same change.
  - A regression test pins the stale-id behaviour in `version_cache`.
- **D-14:** `versions.py` `parse_version` (:54) returns `None` for `-1`-like output. It parses lazygit's `version=0.44.1, …` and unquotes procs' output. These are covered by a parametrized test over the audit fixtures.
- **D-15:** The 35 data fixes are applied as written in audits C/D/E/F, "Registry fixes (data only)". Sublime's `member` is skipped because Phase 17 did it. Each fix maps to a test or to a `verify-registry` pass.

### Ledger amendments (planning, 2026-10-15; RUN-LEDGER)
- **Ledger L-18-01 (D-11 amended, verifiable):** `uv run --no-dev` alone still resolves `.venv/bin/ruff` in a venv synced with dev dependencies (`make install` then `make setup`); `--no-dev --exact` hides it but uninstalls 25 packages. Every launcher in D-11 uses `uv run --isolated --no-dev` instead (verified in a scratch venv and the real repo: ruff hidden, venv untouched, ~0.1 s warm). The same applies to `scripts/container-e2e-verify.sh` and `tests/test_install_sh.py:223`.
- **Ledger L-18-02 (R5 count, verifiable):** a live API probe of all 89 `github_release` methods: 153 of 171 rendered assets expose a `digest`. 43 methods verify immediately, difftastic/delta add 3 once their data fixes land; gron (x2) and jless (x2) stay unverified because their latest releases publish no digest. "50 -> 0 wherever GitHub exposes a sha256 digest" is asserted as "every method whose asset has a digest is verified" with those four listed as the known no-digest exceptions.
- **Ledger L-18-03 (seed, jev):** the ~62 undated tools' `verified` key is seeded with `2026-10-13`, the audit date (Laya low confidence -> TypeSafe audit_date p=0.72).
- **Ledger L-18-04 (D-07 state, jev):** the last-verified digests live in a JSON state file restored and saved with `actions/cache` in the weekly job, never committed; a cache miss means "no previous digest", so every asset is downloaded once (Laya low confidence -> TypeSafe actions_cache p=0.95).

- **Ledger L-18-05 (D-07 reading, jev + orchestrator):** "inconclusive, no issue call" applies to a whole-run outage (rate limit, release API unreachable, no network). A per-host network error alongside real drift does not suppress the issue: the run exits 1 and the issue lists the drift and the inconclusive hosts. (Laya whole_run p=0.57 low conf -> TypeSafe whole_run p=0.61 below floor -> orchestrator: the literal reading lets one transient 5xx hide real drift every week, defeating REG-03.)
- **Ledger L-18-06 (D-02 reading, jev):** "reject future values" allows a one-day tolerance (accept up to today + 1 day, reject later) to absorb UTC vs local-clock skew between the CI writer and maintainers (Laya tolerance low conf -> TypeSafe tolerance p=0.98).

- **Ledger L-18-07 (D-08 / L-18-04 cache survival, jev):** the drift check stays weekly (`17 5 * * 1`); a second cron (`47 5 * * 4`) only restores and re-saves the `actions/cache` state (no check, no issue), because GitHub evicts entries not accessed for 7 days and delayed weekly runs would otherwise lose the state (Laya accept_loss low conf -> TypeSafe thursday_refresh p=0.91).
- **Ledger L-18-08 (D-11 / REG-06 reading, jev + orchestrator):** "launched without the dev venv on PATH" also covers a shell where the project venv is activated: the setup.py `__main__` block (not `main()`) drops PATH entries inside `<repo>/.venv` before the wizard starts, in addition to `uv run --isolated --no-dev` (Laya low conf -> TypeSafe strip_at_entry p=0.79 below floor -> orchestrator).
- **Ledger L-18-09 (D-06 manager smoke target, jev):** when the method declares `bin_dir` the smoke runs `<bin_dir>/<cmd>`; otherwise it runs `shutil.which(tool.cmd)` and the claim is "the command the user's PATH runs" (TypeSafe p=0.98).
- **Ledger L-18-10 (D-07 / L-18-05 outage definition, verifiable):** a rate limit is HTTP 429, or 403 with `X-RateLimit-Remaining: 0` or `Retry-After`; any other 403 is an inconclusive finding for that repo only. A run with no release reads where every HEAD or download failed is a whole-run outage.
- **Ledger L-18-11 (D-07 / L-18-04 granularity, verifiable):** state and findings are kept per tool/URL/member; HEAD and downloads are de-duplicated per URL per run.
- **Ledger L-18-12 (D-09 `--write` verdict, jev + orchestrator):** a `--write` run's report and exit code describe the registry as written (applied bump = ok + `bumped` note; unapplied = drift, exit 1). Plan 18-15's read-only rerun stays the acceptance gate (Laya/TypeSafe below floor -> orchestrator).
- **Ledger L-18-13 (R3/R11 ordering, D-14 quotes, verifiable):** "newer stable" is ranked with `versions.is_outdated`; an incomparable tag is an inconclusive finding, never drift. The version normalizer strips one leading and one trailing quote independently.
- **Ledger L-18-14 (refines L-18-09, verifiable):** with a declared `bin_dir`: an executable `<bin_dir>/<cmd>` is smoked; a present but non-executable one (e.g. sourced `sdkman-init.sh`, mode 0644) means nothing to smoke and the method stays INSTALLED (RESEARCH Pitfall 8); a missing one falls back to `which(cmd)` with the narrowed L-18-09 claim.
- **Ledger L-18-15 (refines L-18-10, verifiable):** for the whole-run outage only transport failures (no HTTP response) and rate limits count as failed reads; any HTTP response (403 without rate-limit evidence, 404) reached GitHub and is a per-repo finding, never a whole-run block.
- **Ledger L-18-16 (SPEC REG-05 "no linked binary" for manager kinds, jev):** the guarantee covers installer-created links. A package-manager package left installed by a failed smoke is reported in the result with the exact manager removal command; the installer never auto-uninstalls it (TypeSafe installer_links_only p=0.99).
- **Note (cycle 2, literal readings):** D-06 loader-error detection also applies to stderr on exit 0; L-18-11 state keys include the tool id and the extraction settings (archive/strip/raw).

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
- `installer/versions.py` `resolve_github_tag` (:315; already fetches `/releases/latest`, so D-05 extends that same read), `Fetch`/`urlopen_fetch`
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
