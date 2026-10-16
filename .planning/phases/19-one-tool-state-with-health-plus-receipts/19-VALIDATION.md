---
phase: "19"
slug: "one-tool-state-with-health-plus-receipts"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-16"
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `19-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-xdist + pytest-cov + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`, `fail_under = 90`) |
| **Quick run command** | `uv run pytest tests/<file>.py -q --no-cov` |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | ~65 seconds (full suite; 3959 tests collected at `fde3e68`) |

---

## Sampling Rate

- **After every task commit:** Run the touched test file(s) with `uv run pytest tests/<file>.py -q --no-cov`
- **After every plan wave:** Run `make validate && make test`
- **Before `/gsd-verify-work`:**
  - The full suite is green.
  - `git diff --quiet fde3e68 -- pyproject.toml uv.lock` passes (no new dependency).
  - The real `~/.local/state/tools-installer/receipts/` is unchanged by the suite (conftest fingerprint).
  - One `make e2e` has run after the receipt and removal plans land: a container install writes receipts, and `make uninstall --yes` removes a receipt-proven raw binary and its receipt.
- **Max feedback latency:** 70 seconds

---

## Per-Task Verification Map

Filled by the planner per task (`<automated>` + `<fails_when>`); the requirement-level map below is the contract each plan must cover.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| STATE-01 | Two overlapping passes at the same epoch: only the newer publishes, and an older one finishing later is discarded (pass sequence, Ledger L-19-02). An invalidate-raced pass publishes nothing. `state_of` returns None for an old generation | unit (threading.Event barrier) | `uv run pytest tests/test_version_status.py -q --no-cov -k "overtaken or one_swap or state_of or generation"` | ❌ W0 | ⬜ pending |
| STATE-01 | Before the first pass every row renders `…`, never `✓`. A navigation refresh keeps the marks. Every production caller passes the full catalog (no tier-subset or single-tool pass wipes another tier) | unit (Textual) | `uv run pytest tests/test_catalog_tui.py tests/test_execute_screen.py -q --no-cov -k "checking or first_pass or full_catalog"` | ❌ W0 | ⬜ pending |
| STATE-02 | The `tool_health` parametrized table covers present × {checking, broken, misconfigured, outdated} and absent × available. Broken plus outdated gives broken with both reasons | unit | `uv run pytest tests/test_version_status.py -q --no-cov -k tool_health` | ❌ W0 | ⬜ pending |
| STATE-02 | Every mark renders on the system, user and ai tiers. The legend is 3 lines of ≤ 78 cells each (`cell_len`), all visible on the compositor at 80×20 and 120×30. An empty tier renders. The 15.1 legend tests are replaced, as listed in the plan | unit (Textual) | `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "health_cell or legend or empty_tier"` | ❌ W0 | ⬜ pending |
| STATE-03 | `receipts` read/write/matches. A round-trip works. Each of these returns None and never raises: `v != 1`, malformed JSON, an oversize file, a RecursionError, the wrong tool, a relative path. Stat-fingerprint drift, a changed link target and a dir-type check are detected | unit | `uv run pytest tests/test_receipts.py -q --no-cov` | ❌ W0 | ⬜ pending |
| STATE-03 | Receipts are written for download (archive and raw), app, script, brew, uv-tool and node, and none for native, skill_pack or host_setup. A write failure leaves the tool INSTALLED with a warning, unproven | unit (fake runner, scratch HOME) | `uv run pytest tests/test_engine.py -q --no-cov -k receipt` | ❌ W0 | ⬜ pending |
| STATE-03 | A successful update rewrites the receipt (no false "changed since install"). A failed update keeps the old one. A manager update with no prior receipt writes none (Ledger L-19-03) | unit | `uv run pytest tests/test_update.py -q --no-cov -k receipt` | ❌ W0 | ⬜ pending |
| STATE-03 (R5) | A file whose sha256 equals the cached digest is adopted, with a receipt and a reason. A mismatch writes no receipt and shows "not proven: reinstall with r to adopt". A non-match is remembered by (path, size, mtime_ns). No digest means unproven. Adoption never overwrites a concurrent install's receipt | unit | `uv run pytest tests/test_version_status.py tests/test_receipts.py -q --no-cov -k adopt` | ❌ W0 | ⬜ pending |
| STATE-03 (R6) | `--yes` and the TUI remove a receipt-proven raw binary and refuse an unproven one. A changed link target makes the tool not removable and broken. A tampered receipt path outside `artifact_paths` is never deleted. Deletion re-verifies the sha256. The receipt is deleted after removal | unit | `uv run pytest tests/test_uninstall.py tests/test_app.py -q --no-cov -k "receipt or proven or tampered"` | ❌ W0 | ⬜ pending |
| STATE-03 (D-07) | One `download.artifact_paths` serves install, receipt and uninstall evidence. `bin_name`/`cli_name` are honored. `cli_spec` moves to `download.py` with no import cycle (Ledger L-19-04) | unit | `uv run pytest tests/test_download.py tests/test_apps.py tests/test_uninstall.py -q --no-cov -k "artifact_paths or cli_spec or cli_name"` | ❌ W0 | ⬜ pending |
| STATE-04 | graphify under `uv tool dir` resolves to owner uv (Ledger L-19-01). A Volta shim resolves to volta, including pnpm through Volta. A redirect shim resolves to the real owner. An implicit `~/.local/bin/<bin>` counts as present. host_setup keeps its probe. Update refuses volta cleanly | unit | `uv run pytest tests/test_ownership.py tests/test_status.py tests/test_update.py -q --no-cov -k "uv_tool_dir or volta or shim or implicit or host_setup"` | ❌ W0 | ⬜ pending |
| STATE-04 | A pass makes one `rpm -qf` argv for N native tools and reads rpm-ostree status once. The rpm/dpkg/pacman outputs are parsed by path, covering missing, unowned and multi-owner paths, and stdout is used from a CalledProcessError | unit | `uv run pytest tests/test_install_ownership.py tests/test_version_status.py -q --no-cov -k "batch or native_index or one_probe"` | ❌ W0 | ⬜ pending |
| STATE-05 | A fake brew appearing between passes sets `service.platform.has_brew` to True. colima then resolves a method, and ExecuteScreen uses the live platform | unit | `uv run pytest tests/test_version_status.py tests/test_execute_screen.py -q --no-cov -k "has_brew or live_platform"` | ❌ W0 | ⬜ pending |
| STATE-06 | The focused row lists its reasons in order, then the "to configure:" steps. A 400-character reason list stays within the 3-row detail | unit (Textual) | `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "detail or reasons or unconfigured"` | ❌ W0 | ⬜ pending |
| STATE-07 | A partial pack on a present harness shows `≈`; a pack for an absent harness shows none. The Claude 4-install JSON fixture yields duplicate and disabled reasons with the D-18 ordered steps. A project pack with a global leftover shows `≈`. The empty-dirs false positive reads not installed | unit | `uv run pytest tests/test_skill_lifecycle.py tests/test_version_status.py -q --no-cov -k "partial or duplicate or disabled or project_pack"` | ❌ W0 | ⬜ pending |
| R9 (D-16) | A drifted kitty, WezTerm or Konsole config shows `≈`; no terminal shows none. The dry run writes nothing under the scratch HOME, including `.zshrc` and the Konsole state file (Ledger L-19-05) | unit | `uv run pytest tests/test_terminal_shell.py -q --no-cov -k "dry_run or drift"` | ❌ W0 | ⬜ pending |
| R9 (D-19) | An incomplete pnpm group in the cached inventory shows `≈` with its step | unit | `uv run pytest tests/test_pnpm_globals.py tests/test_version_status.py -q --no-cov -k incomplete` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_receipts.py`: STATE-03 reader, writer, matches and adopt
- [ ] `tests/conftest.py`: an autouse fixture that redirects `receipts.receipts_dir()` to `tmp_path`, plus the real receipts dir added to `_real_home_fingerprint` (RESEARCH Pitfall 2)
- [ ] Shared fixtures:
  - a fake batched native probe (path-named rpm/dpkg/pacman outputs, `CalledProcessError` with stdout);
  - a `claude plugin list --json` 4-install fixture plus `installed_plugins.json`;
  - a GSD project-repo tree (VERSION present, plus the empty-dirs case).
- [ ] A planned-replacement list for the 15.1 legend tests (`tests/test_catalog_tui.py:1852-1964`) and for the tests of the deleted `set_installed`/`ownership_of`/`statuses`/`skill_status_of` APIs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real install writes receipts, and `--yes` removes a receipt-proven raw binary | STATE-03, R6 | Needs real executors | backstop: `make e2e` (container), with the receipt listing checked before and after uninstall |
| Marks are distinguishable with `NO_COLOR=1` in a non-CJK UTF-8 locale | STATE-02 | Terminal rendering | Human UAT on the real host (19-UI-SPEC backstop row) |
| Adoption converges on this host after the cache refetch | R5 | Host cache entries (2026-10-10) carry no digests until `STALE_AFTER` | After about 2026-10-17, open the catalog: yq/direnv/fx/dasel show "adopted" only when the file equals the latest release |
| macOS behavior of the volta, brew and has_brew re-read paths | STATE-04/05 | No macOS host | backstop: CI macos-latest job + fixtures |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 70s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
