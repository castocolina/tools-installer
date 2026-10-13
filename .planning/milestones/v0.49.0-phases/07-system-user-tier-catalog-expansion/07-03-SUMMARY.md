---
phase: 07-system-user-tier-catalog-expansion
plan: 03
status: complete
commits:
  - 2d6c19f
  - f16a971
---

# 07-03: kitty + wezterm — SUMMARY

**Execution note (ONESHOT-RULES Rule 12 fallback):** cross-AI execution
(`opencode run --model router-env/my-coding`) was attempted three times for
this plan and failed identically all three times with "Service temporarily
unavailable due to resource pressure" — a transient backend outage, landing
zero commits each time. After the third consecutive identical failure (a
demonstrated repeated zero-progress tool failure), execution fell back to
this session's own tokens per Rule 12's documented fallback. A `gsd-executor`
subagent dispatch was also attempted first but could not proceed: this
runtime's worktree isolation created the agent's worktree from a stale base
branch (`feat/tui-interaction-consistency`, this session's original branch
at startup) rather than the current `gsd/phase-07-...` branch, and the
agent correctly refused to force a cross-worktree branch checkout rather
than risk corrupting state. Given both delegation paths were unavailable,
the plan was executed directly in the orchestrator's own context — a
disclosed, legitimate deviation, not a silent rule violation.

## What was implemented

**Task 1 (`2d6c19f`)** — A new `terminal` `Category` enum member and
registry blurb; `kitty` and `wezterm` as `tier="user"` entries.

- `kitty`: cask-only on macOS (`formulae.brew.sh/api/formula/kitty.json`
  confirmed `404` live), native `dnf`/`apt`/`pacman` packages on Linux, no
  method at all on immutable Bazzite — `kitty`'s GitHub release Linux
  assets are `.txz` (confirmed live via the GitHub Releases API), and
  `installer/download.py`'s extraction (`_install_unverified`/
  `_place_verified`, lines 146/207) hardcodes gzip-only `tar -xzf`. The
  registry comment states two independent, non-conflated reasons for the
  Linux-cask absence: no formula exists (`404`), and this project's own
  `resolve.py::_applies` cask branch blocks every cask on non-macOS
  regardless of upstream packaging.
- `wezterm`: cask-only on macOS (same live-confirmed pattern), `pacman` on
  Arch (arch-unrestricted, so it also covers Arch arm64), and a
  checksum-verified `github_release` AppImage (`raw=true`) on Debian/Fedora
  amd64 — `raw=true` bypasses the same broken extraction path `kitty` hits,
  which is why the AppImage was chosen over a plain archive. This also
  gives `wezterm` an unplanned Bazzite path, since `github_release` methods
  are never skipped by the immutable-Linux native-manager check.
- **Live-checked Linux-arm64 scope** (this session, no stale assumption):
  fetched `api.github.com/repos/wezterm/wezterm/releases/latest` and found
  only `.deb` arm64 variants (`Debian12.arm64.deb`, `Ubuntu22.04.arm64.deb`)
  — no arm64 AppImage exists. `arch = ["amd64"]` was kept on the
  `github_release` method; a new `NO_DEBIAN_FEDORA_ARM64` test allowlist
  (mirroring the existing `MACOS_ONLY`/`NO_LINUX_ARM64` pattern) records
  this as an honest, tested gap distinct from Arch arm64 (already covered).
- **Real Tier-3 verification** (disposable `python:3.13-slim` container,
  removed after use): the real, unmodified
  `installer.download.install_download` resolved the live release tag
  (`20240203-110809-5046fc22`), downloaded the AppImage and its `.sha256`
  sidecar, verified the checksum, and returned `True`. Separately,
  `~/.local/bin/wezterm --version` was run with `APPIMAGE_EXTRACT_AND_RUN=1`
  set — it succeeded fully (`wezterm 20240203-110809-5046fc22`, exit 0),
  not merely the FUSE-unavailable fallback path the plan anticipated as an
  acceptable alternative outcome.
- New tests: `test_kitty_has_no_linux_download_fallback`,
  `test_wezterm_appimage_covers_bazzite_where_kitty_cannot` (asserts
  `params["asset"]`/`checksum`/`raw`/`member`/`arch` directly, not just
  method kind), `test_kitty_entry_records_the_txz_extraction_gap`,
  `test_wezterm_entry_records_the_checksum_sidecar_verification`,
  `test_no_debian_fedora_arm64_allowlist_stays_honest`. Tier tripwire
  updated `user: 36 -> 38`. `"wezterm"` added to `SIDECAR_VERIFIED`.

**Task 2 (`f16a971`)** — Consolidated all six of Phase 7's decisions
(07-01/07-02/07-03) into `.planning/PROJECT.md`'s Key Decisions table as
six condensed rows (`Outcome` = `Phase 7`), including D-01's now-fully-
closed resolution — the real `platform_could_support`/`min_os_version`
implementation, not the original `NO_METHOD`-only premise nor either prior
cross-AI review cycle's "accepted residual gap" framing. Footer bumped to
cite Phase 7's completion.

## Validation

`make validate && make test` — clean (ruff, ruff-format, pyright 0 errors,
bandit, vulture, shellcheck, full pytest suite with coverage). The
phase-level cross-plan test surface
(`test_platform.py test_resolve.py test_status.py test_selection.py
test_catalog_tui.py test_setup.py test_wizard_app.py`) passes green.
`load_tools`/`load_categories` parse the full registry (new category, six
new tools across all three plans) cleanly end to end.

The plan's required HIGH-finding closure — a real, resolver-level
assertion that a too-old-macOS Apple-Silicon `Platform` fixture resolves
ZERO methods for Apple Containers — was already present from 07-02
(`tests/test_registry.py::test_apple_containers_blocks_a_too_old_macos_version`,
using `os_version="15.0"` and `os_version=None` fixtures against the real
`container` registry entry, not a synthetic stand-in).

## Phase 7 close-out

This is Phase 7's final plan. ROADMAP Phase 7 success criteria:

- **SC#1** (zsh/oh-my-zsh/gnu-bash/Apple Containers install cleanly) —
  satisfied (07-01, 07-02).
- **SC#2** (kitty/wezterm cask-corrected with verified Linux paths,
  07-RESEARCH.md Open Questions 2 and 3 closed with live verification) —
  satisfied (this plan).
- **SC#3** (zsh/oh-my-zsh Linux/Bazzite parity via the existing `podman`
  entry) — satisfied (07-01).
- **SC#4** (Apple Containers as a real brew action; D-01's disabled-state
  genuinely and completely implemented, no residual macOS-version gap) —
  satisfied (07-02).

Phase 7 closes with no explicitly-accepted residual gap for D-01.
