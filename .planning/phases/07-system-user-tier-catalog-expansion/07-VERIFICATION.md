---
phase: 07-system-user-tier-catalog-expansion
verified: 2026-09-06T00:00:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 7: System & User Tier Catalog Expansion Verification Report

**Phase Goal:** The system-tier prerequisites the user actually starts a fresh machine
from (shell, shell framework, container runtime) and the terminal emulators they pick
personally both exist in the catalog with verified, per-platform install methods.
**Verified:** 2026-09-06
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Phase 7 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | `zsh`, `oh-my-zsh`, `gnu-bash` (macOS), Apple Containers (macOS) install cleanly via verified live methods; `oh-my-zsh`'s `.zshrc`-rewriting behavior read and confirmed safe before shipping as `kind="script"` | ✓ VERIFIED | `installer/registry.toml` lines 491-587, 1018-1024 contain all four entries with dated `# Verified 2026-09-06` comments; `oh-my-zsh` declares `env = {RUNZSH="no", CHSH="no", KEEP_ZSHRC="yes"}` and `requires=["zsh","git"]`. **Independently re-executed in this session** (not taken from SUMMARY narration): ran the real captured pipeline (`curl -fsSL -- .../install.sh \| CHSH=no KEEP_ZSHRC=yes RUNZSH=no sh`) in a disposable `ubuntu:24.04` container twice — (a) without `git` pre-installed: exit 1, output contains literal `Error: git is not installed`, confirming the undeclared-dependency finding is real; (b) with `zsh`+`git` pre-installed and a pre-existing `.zshrc`: exit 0, `diff` shows the `.zshrc` byte-identical, no `.zshrc.pre-oh-my-zsh` backup file, `~/.oh-my-zsh/oh-my-zsh.sh` present, log shows vendor's own `Found /root/.zshrc. Keeping...` confirmation. `gnu-bash`'s `cmd="gnu-bash"` + prefix-specific `detect_path` avoids the macOS system-bash false positive, confirmed by reading `installer/status.py::is_installed` and the passing `tests/test_status.py::test_gnu_bash_status_is_not_fooled_by_macos_system_bash`. |
| SC#2 | `kitty`, `wezterm` install cleanly on macOS (brew) with a verified Linux path (distro package or GitHub-release download) | ✓ VERIFIED | `installer/registry.toml` lines 2144-2270: `kitty` — `dnf`/`apt`/`pacman` native packages + macOS `cask` (with `min_os_version="12"`, the dual-lane review's landed fix); `wezterm` — `pacman` (Arch, arch-unrestricted) + `github_release` checksum-verified AppImage (Debian/Fedora amd64) + macOS `cask`. New `terminal` `Category` enum member confirmed present (`installer/enums.py:51`). Tests `test_kitty_has_no_linux_download_fallback`, `test_wezterm_appimage_covers_bazzite_where_kitty_cannot`, `test_kitty_cask_blocks_a_too_old_macos_version` all pass. |
| SC#3 | `zsh`/`oh-my-zsh` have a working Linux/Bazzite install path; the existing `podman` entry (not a new one) is the container-runtime story there | ✓ VERIFIED | Exactly one `podman` entry in the registry (`grep -c` = 1, no duplication). `tests/test_registry.py::test_bazzite_zsh_and_podman_both_resolve_brew_only_no_new_entry` and `test_fresh_bazzite_without_brew_has_no_method_for_zsh_or_podman_yet` both pass, proving both the `has_brew=True` (brew-only) and honest `has_brew=False` (empty-method, real two-run bootstrap path) boundaries for the identical immutable-Bazzite fixture applied to both `zsh` and `podman`. |
| SC#4 | Whether Apple Containers needs an actual install step on current macOS, or is a pure version-gate/doc entry, is resolved and recorded | ✓ VERIFIED | Resolved as a **real install step**: `container` entry is `kind="brew" formula="container"` with `min_os_version="26"` (registry.toml:1018-1043); registry comment states this explicitly, citing the live-confirmed Homebrew formula requirements (`macos>=26`, `arm64`). `REQUIREMENTS.md` line 49 marked `[x]` Done. The macOS-version gate is genuinely implemented (not just documented) — `Platform.os_version` (installer/platform.py:28,69), `_applies`'s `min_os_version` gate (installer/resolve.py:40-44), and `platform_could_support` (installer/resolve.py:69-93) are real, tested code, confirmed by direct read and by `uv run python3 -c` one-liners exercising both paths. `.claude/architecture.md` records the convention (lines 219-244) as required. |

**Score:** 4/4 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/registry.toml` | 6 new entries (`zsh`, `oh-my-zsh`, `gnu-bash`, `container`, `kitty`, `wezterm`), each dated-comment-verified | ✓ VERIFIED | All 6 present, correctly structured, dated comments contain required load-bearing substrings (`podman`, `5.9.2`, `KEEP_ZSHRC`, `command_exists git`, `NO_METHOD`, `brew install container`, `min_os_version`, txz-extraction-gap, checksum-sidecar reasoning) |
| `installer/platform.py` | `Platform.os_version` field | ✓ VERIFIED | Present, stdlib-only (`platform.mac_ver()`), default-safe (`None`), populated only on Darwin |
| `installer/resolve.py` | `min_os_version` gate in `_applies`; `platform_could_support` predicate | ✓ VERIFIED | Both present, fail-closed on unparseable/`None` version, 100% test coverage per `make test` coverage report |
| `installer/selection.py` | `unstaged_recommends` filters unavailable ids | ✓ VERIFIED | `unavailable` parameter present and applied (line 94-109) |
| `setup.py` | Wiring: `platform_could_support` → `unavailable` map → `UnifiedApp` | ✓ VERIFIED | `setup.py:41,150,292` — composition-root-only wiring, no business logic inlined |
| `installer/wizard_app.py` | Threads `unavailable` kwarg into `CatalogScreen` | ✓ VERIFIED | `wizard_app.py:1129,1142` |
| `installer/catalog_tui.py` | Dim/non-selectable rendering + 3-path staging filter | ✓ VERIFIED | `_adapter().selectable`, `_row_cells` dim branch, `_detail_text` suffix, `action_accept_recommends`, `on_tool_browser_accepted` all filter through `self._unavailable` (lines 178-390) |
| `.claude/architecture.md` | D-01 convention recorded | ✓ VERIFIED | "Platform-unavailable catalog rows reuse the Uninstall view's dim/non-selectable pattern" subsection present (lines 219-244) |
| `tests/test_registry.py` | Tier tripwire updated, new tests per plan | ✓ VERIFIED | `system=26, ai=10, user=38` (matches all three plans' stated progression 22→24→26, and user 35→36→38) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `oh-my-zsh.requires` | `zsh`, `git` resolution order | `installer/deps.py::resolve_dependencies` (unmodified) | ✓ WIRED | `test_selecting_oh_my_zsh_drags_in_zsh_and_git_in_deps_first_order` passes against the real loaded registry |
| `installer/resolve.py::platform_could_support` | `setup.py` → `UnifiedApp` → `CatalogScreen` | keyword-arg threading | ✓ WIRED | Confirmed via direct grep of both call sites; `test_build_app_hands_unavailable_from_platform_could_support` and `test_real_apple_containers_unavailable_only_for_genuine_incompatibility` pass against the real registry |
| `CatalogScreen._unavailable` | 3 staging paths (`unstaged_recommends`, `action_accept_recommends`, `on_tool_browser_accepted`) | shared dict lookup | ✓ WIRED | All three read `self._unavailable`/`unavailable`; `test_unavailable_recommendation_is_not_staged_or_emitted` exercises both the recommend-accept path and the final commit path end-to-end via a live Textual pilot |
| `gnu-bash`'s `detect_path` | `installer/status.py::is_installed` fallback | unmodified two-step which()→detect_path | ✓ WIRED | `test_gnu_bash_status_is_not_fooled_by_macos_system_bash` drives `is_installed` under a simulated `shutil.which` returning the system `/bin/bash` for `"bash"` but `None` for `"gnu-bash"` |

### Behavioral Spot-Checks (independently executed by the verifier, not taken from SUMMARY)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `oh-my-zsh` install fails without `git`, with the exact vendor error | `docker run --rm ubuntu:24.04 sh -c 'apt-get install zsh curl ca-certificates; curl -fsSL -- .../install.sh \| CHSH=no KEEP_ZSHRC=yes RUNZSH=no sh'` | Exit 1, output contains `Error: git is not installed` | ✓ PASS |
| `oh-my-zsh` preserves a pre-existing `.zshrc` byte-identical, no backup file, with `zsh`+`git` pre-installed | Same pipeline, `zsh git curl ca-certificates` pre-installed, `.zshrc` pre-seeded | Exit 0, `diff` shows no difference, no `.zshrc.pre-oh-my-zsh`, `~/.oh-my-zsh/oh-my-zsh.sh` present, log contains `Found /root/.zshrc. Keeping...` | ✓ PASS |
| `make validate` (lint/format/types/security/dead-code) on the committed tree | `make validate` | ruff, ruff-format, pyright (0 errors), bandit, vulture, shellcheck all clean | ✓ PASS |
| `make test` (full suite + coverage) on the committed tree | `make test` | 1229 passed, 99.40% coverage (required 90%), `installer/resolve.py` and `installer/platform.py` both 100% covered | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| REQ-system-tier-shell-container-entries | 07-01, 07-02 | zsh/oh-my-zsh/gnu-bash/Apple Containers system-tier entries | ✓ SATISFIED | REQUIREMENTS.md marked `[x]`; all four entries present and verified above |
| REQ-terminal-emulator-entries | 07-03 | kitty/wezterm user-tier entries | ✓ SATISFIED | REQUIREMENTS.md marked `[x]`; both entries present and verified above |
| REQ-linux-bazzite-shell-parity | 07-01 | zsh/oh-my-zsh real Linux/Bazzite path via existing podman | ✓ SATISFIED | REQUIREMENTS.md marked `[x]`; parity tests pass |

No orphaned Phase-7 requirements found in REQUIREMENTS.md (all three phase-tagged reqs are claimed by a plan and satisfied).

### Anti-Patterns Found

None. Scanned all files touched in `47107fd..7bcd1b8` (registry.toml, platform.py, resolve.py, selection.py, setup.py, wizard_app.py, catalog_tui.py, enums.py, architecture.md, and all associated test files) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` and stub-shaped patterns (`return null`, hardcoded empty collections feeding render output) — zero matches. `07-REVIEW.md`'s own deep dual-lane review (0 Critical, 1 Warning already fixed, 2 Info already corrected in SUMMARY) corroborates this independently.

### Human Verification Required

None. Every must-have was independently confirmed via direct code inspection, passing automated tests exercising the real registry/resolver/TUI-data-layer, and (for the one behavior-dependent claim — Oh My Zsh's vendor `install.sh` actually preserving `.zshrc`/failing without `git`) live re-execution of the documented Tier-3 container pipeline in this verification session, reproducing the exact reported outcomes (exit codes and vendor output strings) rather than trusting the SUMMARY's transcript alone.

### Gaps Summary

None. All four ROADMAP Phase 7 success criteria are met with direct evidence. The phase's own dual-lane code review (`07-REVIEW.md`) found one real gap (kitty's cask missing a macOS-version floor) and it is confirmed landed in the registry (`min_os_version = "12"` on kitty's cask method, plus `test_kitty_cask_blocks_a_too_old_macos_version`). `make validate && make test` both pass clean on the exact committed tree (`747a8a8`).

---

_Verified: 2026-09-06_
_Verifier: Claude (gsd-verifier)_
