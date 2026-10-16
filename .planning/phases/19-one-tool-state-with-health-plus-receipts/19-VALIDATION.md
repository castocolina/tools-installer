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
| STATE-01 | Two overlapping passes at the same epoch: only the newer publishes, and an older one finishing later is discarded (pass sequence, Ledger L-19-02). An invalidate-raced pass publishes nothing. `state_of` returns None for an old generation. Identical passes at one epoch share one flight and one fetch; a join never crosses an invalidate (19-08, checker W11). A cache-save failure keeps the states and sets `warning` | unit (threading.Event barrier) | `uv run pytest tests/test_version_status.py -q --no-cov -k "overtaken or state_of or tool_state or sequence or partial_pass or older_full_pass or share_one_flight or crosses_an_invalidate or shared_pass or one_snapshot or raced_refresh or cache_save"` | ❌ W0 | ⬜ pending |
| STATE-01 | Before the first pass every row renders `…`, never `✓`. After `u` every row renders `…` until the follow-up full pass (checker W1). Every production caller passes the full catalog, and a single-tool pass merges without wiping another tier. Quick tier switching runs one full pass (W11). A cache-save warning reaches the status line (W3). Install close and view switches re-enter through the pass with no presence sweep, and no per-tier presence copy survives (19-20) | unit (Textual) | `uv run pytest tests/test_catalog_tui.py tests/test_wizard_app.py tests/test_version_status.py -q --no-cov -k "checking or first_pass or full_catalog or one_full_pass or cache_save_warning or partial_pass or no_installed_parameter or presence_sweep"` | ❌ W0 | ⬜ pending |
| STATE-02 | The `tool_health` parametrized table covers present × {checking, broken, misconfigured, outdated} and absent × available. Broken plus outdated gives broken with both reasons. An absent tool keeps its notes (checker B1 contract) | unit | `uv run pytest tests/test_tool_health.py -q --no-cov` | ❌ W0 | ⬜ pending |
| STATE-02 | Every mark renders on the system, user and ai tiers (pilot, scratch HOME; checker W6). The legend is 3 lines of ≤ 78 cells each (`cell_len`), all visible on the compositor at 80×20 and 120×30. An empty tier renders. The 15.1 legend tests are replaced, as listed in the plan | unit (Textual) | `uv run pytest tests/test_catalog_tui.py tests/test_layout_80x20.py -q --no-cov -k "health_cell or legend or empty_tier or every_health_mark or 80x20 or 120x30"` | ❌ W0 | ⬜ pending |
| STATE-03 | `receipts` read/write/matches. A round-trip works. Each of these returns None and never raises: `v != 1`, malformed JSON, an oversize file, a RecursionError under the size cap (checker W10), the wrong tool, a relative path. Stat-fingerprint drift, a changed link target and a dir-type check are detected. Registry ids are safe receipt filenames, enforced at load (checker I4) | unit | `uv run pytest tests/test_receipts.py -q --no-cov && uv run pytest tests/test_model.py -q --no-cov -k "unsafe_tool_id or safe_filename"` | ❌ W0 | ⬜ pending |
| STATE-03 | Receipts are written for download (archive and raw), app, script, brew, uv-tool and node, and none for native, skill_pack or host_setup. A reinstall rewrites the receipt (checker W7). A write failure leaves the tool INSTALLED with a warning, unproven | unit (fake runner, scratch HOME) | `uv run pytest tests/test_engine.py tests/test_receipts.py -q --no-cov -k "receipt or record"` | ❌ W0 | ⬜ pending |
| STATE-03 | A successful update rewrites the receipt (no false "changed since install"). A failed update keeps the old one. A manager update with no prior receipt writes none (Ledger L-19-03) | unit | `uv run pytest tests/test_update.py -q --no-cov -k "receipt or write_nothing"` | ❌ W0 | ⬜ pending |
| STATE-03 (R5) | A file whose sha256 equals the cached digest is adopted, with a receipt and a reason. A mismatch writes no receipt and shows "not proven: reinstall with r to adopt". A non-match is remembered by (path, size, mtime_ns). No digest means unproven. Adoption never overwrites a concurrent install's receipt | unit | `uv run pytest tests/test_version_status.py tests/test_receipts.py -q --no-cov -k "adopt or unproven"` | ❌ W0 | ⬜ pending |
| STATE-03 (R6) | `--yes` and the TUI remove a receipt-proven raw binary and refuse an unproven one. A changed link target makes the tool not removable and broken, end to end (ROADMAP SC3, checker W7). A tampered receipt path outside `artifact_paths` is never deleted. Deletion re-verifies the sha256. The receipt is deleted after removal | unit | `uv run pytest tests/test_uninstall.py tests/test_app.py tests/test_setup.py tests/test_version_status.py -q --no-cov -k "receipt or proven or tampered or link_target or reproves or selected_tools"` | ❌ W0 | ⬜ pending |
| STATE-03 (D-07) | One `download.artifact_paths` serves install, receipt and uninstall evidence. `bin_name`/`cli_name` are honored. `cli_spec` moves to `download.py` with no import cycle (Ledger L-19-04) | unit | `uv run pytest tests/test_download.py tests/test_apps.py tests/test_uninstall.py -q --no-cov -k "artifact_paths or cli_spec or cli_name"` | ❌ W0 | ⬜ pending |
| STATE-04 | graphify under `uv tool dir` resolves to owner uv (Ledger L-19-01), in the resolver and in the pass. A Volta shim resolves to volta, including pnpm through Volta. A redirect shim resolves to the real owner. An implicit `~/.local/bin/<bin>` counts as present, read from the bin dir the caller passes (the service passes its managed bin dir; checker W2). host_setup keeps its probe. Update refuses volta cleanly | unit | `uv run pytest tests/test_ownership.py tests/test_status.py tests/test_update.py tests/test_guards.py tests/test_version_status.py -q --no-cov -k "uv_tool_dir or volta or shim or implicit or host_setup or graphify"` | ❌ W0 | ⬜ pending |
| STATE-04 | A pass makes one `rpm -qf` argv for N native tools and reads rpm-ostree status once; every other native query (declared packages) is memoized per pass (checker I2). The rpm/dpkg/pacman outputs are parsed by path, covering missing, unowned, multi-owner and usrmerge-alias paths (checker I3), and stdout is used from a CalledProcessError | unit | `uv run pytest tests/test_install_ownership.py tests/test_version_status.py -q --no-cov -k "native or rpm or batch or tracked_paths or declared_package"` | ❌ W0 | ⬜ pending |
| STATE-05 | A fake brew appearing between passes sets `service.platform.has_brew` to True. colima then resolves a method; the catalog row becomes selectable; ExecuteScreen and the update service use the live platform (checker W2) | unit | `uv run pytest tests/test_version_status.py tests/test_execute_screen.py tests/test_catalog_tui.py tests/test_update.py tests/test_setup.py -q --no-cov -k "has_brew or brew_appearing or live_platform"` | ❌ W0 | ⬜ pending |
| STATE-06 | The focused row lists its reasons in order, then the "to configure:" steps. A 400-character reason list stays within the 3-row detail | unit (Textual) | `uv run pytest tests/test_catalog_tui.py tests/test_tool_browser.py -q --no-cov -k "detail or reason"` | ❌ W0 | ⬜ pending |
| STATE-07 | A partial pack on a present harness shows `≈`; a pack for an absent harness shows none. The Claude 4-install JSON fixture yields duplicate and disabled reasons with the D-18 ordered steps, and they reach the state with an explicit Health (MISSING when no harness has the pack, MISCONFIGURED when another does; checker B1), as the first reasons in both cases (checker W1). A project pack with a global leftover in any of the nine harness homes, as machinery or as a hook registration, shows `≈` (checker B2); a leftover in the shared `~/.agents/skills` root names the path and the Codex/Kimi CLI ambiguity (checker I5). The empty-dirs false positive reads not installed, and an empty install beside a real runtime in the same repo still gets its reinstall step (checker I3). The opengsd handoff text matches the pin (checker W4) | unit | `uv run pytest tests/test_skill_lifecycle.py tests/test_version_status.py tests/test_registry.py -q --no-cov -k "partial or duplicate or project_pack or four_install or leftover or hook or repo_walk or empty_dirs or install_steps or keeps_configuration or handoff_text"` | ❌ W0 | ⬜ pending |
| R9 (D-16) | A drifted kitty, WezTerm or Konsole config shows `≈`; no terminal shows none. The dry run writes nothing under the scratch HOME, including `.zshrc` and the Konsole state file (Ledger L-19-05) | unit | `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_setup.py -q --no-cov -k "dry_run or drift"` | ❌ W0 | ⬜ pending |
| R9 (D-19) | An incomplete pnpm group in the cached inventory shows `≈` with its step, on the tool that declares the group (checker I6) | unit | `uv run pytest tests/test_pnpm_globals.py tests/test_version_status.py -q --no-cov -k "incomplete or pnpm_group or declaring_tool"` | ❌ W0 | ⬜ pending |
| Test sandbox (W0) | No test reads or writes the developer's HOME through a service: receipts, `skill_home` and the default bin dir (`installer.locations.bin_dir(None)`, so the implicit `~/.local/bin` presence and the service's managed bin dir) are sandboxed per test; the catalog doubles require a scratch home (checker W5, W2) | unit | `uv run pytest tests/test_receipts.py tests/test_locations.py tests/test_version_status.py tests/test_catalog_tui.py -q --no-cov -k "sandbox or real_home or skill_home"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_receipts.py`: STATE-03 reader, writer, matches and adopt
- [ ] `tests/conftest.py`: an autouse fixture that redirects `receipts.receipts_dir()` to `tmp_path`, plus the real receipts dir added to `_real_home_fingerprint` (RESEARCH Pitfall 2; plan 19-01)
- [ ] `tests/conftest.py`: an autouse `sandboxed_bin_dir` fixture that makes `installer.locations.bin_dir(None)` answer a per-test scratch dir while HOME is the real home (checker W2; plan 19-01)
- [ ] `tests/conftest.py`: an autouse `sandboxed_skill_home` fixture that redirects `version_status.default_skill_home()` to a per-test scratch dir (checker W5; plan 19-08)
- [ ] Shared fixtures:
  - a fake batched native probe (path-named rpm/dpkg/pacman outputs, `CalledProcessError` with stdout);
  - a `claude plugin list --json` 4-install fixture plus `installed_plugins.json`;
  - a GSD project-repo tree (VERSION present, plus the empty-dirs case);
  - harness homes with GSD global leftovers for all nine harnesses, including hook configs (`settings.json`, `hooks.json`, `config.toml`).
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
