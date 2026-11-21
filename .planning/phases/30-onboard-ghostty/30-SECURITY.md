---
phase: "30"
slug: "onboard-ghostty"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: "2026-11-20"
---

# Phase 30 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Base 63ffc8a1, HEAD 94072cd8. Verified against the code, not the summaries.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| network -> installer | A community AppImage (about 49 MB) is downloaded from GitHub and later executed | AppImage bytes, sha256 |
| registry text -> loader | `note`, `desktop` and `raw` come from `installer/registry.toml` and reach the terminal and a file name | one-line text, desktop id |
| installer -> downloaded AppImage | The placed (digest-verified) AppImage runs with `--appimage-extract` to yield two files | argv, temp dir |
| AppImage contents -> host files | Extracted desktop file and icon become files under `~/.local/share` and an `Exec=` line | file bytes |
| user config files -> installer | Up to four Ghostty files are read (capped at 1 MiB); one is edited | config text |
| discovered zsh path -> Ghostty `/bin/sh -c` | The path is embedded in a `command` line | path text |
| harness script / driver -> container runtime | One container and maybe the base image are created and removed | container name, image name, run args |
| skill text and registry comment -> onboarding agents | They act on what the table and `# Verified` comment claim | text |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Evidence | Status |
|-----------|----------|-----------|----------|-------------|----------|--------|
| T-30-01 | Tampering | downloaded community AppImage | high | mitigate | Both arch methods pin `sha256` (installer/registry.toml, amd64 `50ad4f8b...2ae6`, arm64 `932e21c6...f506`); `_fetch_verified` hashes the asset and raises `ChecksumMismatch` before `_replace_raw` or any placement (installer/download.py:~480-505, `install_download` calls it first at :427-429). Tests: tests/test_download.py:1187 (mismatch places nothing, no `.new`, workdir gone), tests/test_engine.py `test_ghostty_digest_mismatch_is_a_checksum_mismatch_outcome` (CHECKSUM_MISMATCH, no binary), tests/test_ghostty_catalog.py:29 (both methods pinned, distinct digests, same version), tests/test_registry.py:2302 (exact pin values and URLs) | closed |
| T-30-02 | Spoofing | registry `note` markup / control chars | medium | mitigate | Loader refuses a non-string, empty, `[`-bearing or control-character note (installer/model.py:681-693); the note reaches the user through `_perform` -> `leftovers` -> `postinstall_warning` (installer/engine.py:151-152, :357-360). Tests: tests/test_model.py:1701 (empty, two lines, markup, BEL, non-string), tests/test_engine.py `test_ghostty_installs_on_linux_x86_64_through_the_engine` (warning holds "community build"), tests/test_appimage_menu.py:329 (warning equals the registry note), tests/test_ghostty_catalog.py:50 (note only on the two Ghostty methods) | closed |
| T-30-03 | Tampering | `desktop` id used as a file name | medium | mitigate | `_DESKTOP_ID_RE = (?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._-]*` with `fullmatch`, and `raw = true` required (installer/model.py:191, :696-703); `artifact_paths` re-checks `_is_single_name` (installer/download.py:314). Tests: tests/test_model.py:1735 (empty, `../evil`, `a/b`, space, leading dot, `a..b`, `a.b..c`, non-string, non-raw), tests/test_ghostty_catalog.py:56 | closed |
| T-30-04 | Elevation of Privilege | executing the AppImage for the extraction | medium | mitigate | `appimage_menu.install` runs only after `install_download` verified and placed the binary (engine.py:285-287); argv list through `ctx.runner`, no shell (installer/appimage_menu.py:55-64); `TMPDIR` and `--chdir` point at a fresh `mkdtemp` removed in `finally` (:52, :121-123); smoke run also gets `TMPDIR=<workdir>` (executors.py:105-109, download.py:422). Tests: tests/test_appimage_menu.py:106 (extract argv), :186 (failure leaves nothing, work dir gone), tests/test_download.py (smoke tmpdir) | closed |
| T-30-05 | Tampering | path traversal / symlink from extracted names | medium | mitigate | Only the two names built from the loader-validated id are read, through `staged_member` (strict resolve plus `is_relative_to` plus `is_file`, executors.py:61-72) and `read_capped(..., 1 << 20, follow_symlinks=False)` (appimage_menu.py:67; oversize or non-regular returns None -> refusal). The id pattern also keeps the `--appimage-extract` pattern free of glob characters. Test: tests/test_appimage_menu.py:185 `test_extraction_failures_write_nothing[symlink]` (a `.desktop` symlink to a file outside is refused, nothing written, work dir removed). The plan's named test `test_a_symlink_out_of_the_work_dir_is_refused` does not exist (see Notes) | closed |
| T-30-06 | Tampering | desktop entry injection via `Exec=`, `TryExec=`, `Icon=` | medium | mitigate | `render` refuses a relative path or a control character (`_checked`, desktop_entry.py:21-27), double-quotes and escapes the program per the Desktop Entry spec and doubles `%` (:30-34); only the program word of `Exec=` is replaced, `TryExec=` and `Icon=` are replaced with the checked text (:46-52). Paths come from `artifact_paths` under `Path.home()` and the bin dir. Tests: tests/test_desktop_entry.py (control character, relative, quoting; `drop` case, +45 lines), tests/test_appimage_menu.py:106 (rendered entry) | closed |
| T-30-07 | Tampering | overwriting or deleting a user's own entry or icon | medium | mitigate | An existing path not recorded as a `leaf` in the previous receipt is kept and named (appimage_menu.py:41-51); each destination that is now a symlink is refused immediately before its write (:91-94) and a backup read of a symlink fails on `O_NOFOLLOW` (:81); rollback restores or unlinks (:105-116); `plan_uninstall` offers only the binary for a `desktop` method (uninstall.py:59-61) and removal needs a receipt leaf that still matches (receipts.record `preexisting` rule, receipts.py:504-526). Tests: tests/test_appimage_menu.py:133, :146, :158, :173, :204 (swap to symlink, victim untouched), :227 (rollback), :362, :376, :404 (another tool's receipt authorizes nothing) | closed |
| T-30-08 | Tampering | overwriting a binding the user already has | high | mitigate | `scan_ghostty` reads every default file (both XDG files on Linux, four on macOS), strips only the installer's own regions, and normalizes the chord (terminal_regions.py:~519-582, `ghostty_chord` :487-500); `_ghostty_plan` skips the line and reports `ghostty: partial: you already bind ...` (terminal_keys.py:209-227); an unreadable file loaded before the target blocks the write (`scan.blocked` -> refusal). Tests: tests/test_terminal_keys.py:645 (kept byte for byte, target, legacy and each macOS file), :680 (unscannable earlier file writes nothing), :535, :551, :509, :521 | closed |
| T-30-09 | Tampering | user `keybind = clear` killing the binding | medium | mitigate | `scan.clears` -> `KeysPlan(None, refusal=...)` (terminal_keys.py:216-219); status and apply agree through the shared `_render`. Test: tests/test_terminal_keys.py:723 | closed |
| T-30-10 | Tampering | deleting a user's config on uninstall | high | mitigate | `_drop_created_config(..., bound=True)` deletes only with the created marker, a sidecar equal to `f"{path}\n"` for the path resolved now, and blank text (terminal_keys.py:526-560); the row sets `bind_created_path=True` and `commit_region` writes the sidecar (terminal_regions.py:721-722); `strip_files` makes strip walk every default file removing only owned regions (terminal_keys.py:491-509, `strip_region` rewrites only when a region changed, terminal_regions.py:726-735). Tests: tests/test_terminal_keys.py:734 (resolver moved, legacy file kept), :797 (every user byte kept), :816 (regions left in every default file removed) | closed |
| T-30-11 | Denial of Service | huge, unreadable, malformed config | low | mitigate | `read_capped(path, 1 << 20, follow_symlinks=True)`; any non-regular, oversize, undecodable or unreadable file becomes a named partial report, never a crash; only `FileNotFoundError`/`NotADirectoryError` are silent (terminal_regions.py:524-546). Tests: tests/test_terminal_keys.py:535, :551 (directory and bytes `ff fe 00`), tests/test_terminal_shell.py `test_an_unscannable_earlier_file_blocks_the_shell_region`. The plan's named test does not exist (see Notes) | closed |
| T-30-12 | Tampering | overriding a user's own `command` | high | mitigate | `scan.user_command` (any `command` key outside the regions, in any default file, empty value included) sets `body = None`, adds `ghostty: partial: you already set command`, and sweeps an existing installer region (terminal_shell.py:543-575). Tests: tests/test_terminal_shell.py:1997 (target, legacy, empty value; user bytes intact in both files) | closed |
| T-30-13 | Tampering | shell injection through the zsh path in `command` | high | mitigate | `zsh_path = _safe_executable(lookup("zsh"))` raises on a relative path or any control character (terminal_shell.py:166-173, :744); the value is `shlex.join((zsh_path, "-l"))` (:550). The keys region is built from constants only (`clear_binding`, `\xNN` hex of the send text, terminal_keys.py:209-226), and `validate_ghostty` refuses any non-`command =` / non-`keybind =` line before a write (terminal_regions.py:~574-588). Tests: tests/test_terminal_shell.py:1990 (path with a space quoted, relative path raises), tests/test_terminal_shell.py control-character test (`test_control_character_in_discovered_zsh_path_fails_before_kitty_changes`), tests/test_terminal_keys.py:~560 (`validate_ghostty` refuses a foreign line) | closed |
| T-30-14 | Tampering | stale `ghostty` region after tool or zsh removal | medium | mitigate | `_revert_terminal_shells` calls `_strip_ghostty_regions` (terminal_shell.py:706-711); the keys strip walks every default file (terminal_keys.py:503-509). Tests: tests/test_terminal_shell.py:2079, :2174 | closed |
| T-30-15 | Elevation of Privilege | driver on the developer's host | high | mitigate | `main` returns 2 unless `in_container()` before any handler (tests/e2e_ghostty_driver.py:513-515; `in_container` is the shared landing check: engine file, root-written marker, tester HOME). Test: tests/test_container_e2e_ghostty.py:441 (refusal, nothing installed) | closed |
| T-30-16 | Tampering | verb removing other containers/images or widening privileges | high | mitigate | Name `tools-installer-e2e-ghostty-$$` (scripts/container-e2e-verify.sh `cmd_ghostty`); teardown `ct rm -f <that name>` and `ct rmi` only when `LANDING_PULLED=1` and not `--keep-image` (landing_teardown); run args are `--security-opt label=disable` plus `--device /dev/fuse` only when the host path exists (`ghostty_run_args`); no `--privileged`, `--cap-add`, prune or reset; the diff adds no `sudo` (only the pre-existing container bootstrap uses it, and `dnf install` runs through `exec_root` inside the container). Tests: tests/test_container_e2e_ghostty.py:596 (no `--privileged`/`--cap-add`, device only when present), :624, :672 (every ct call carries the one PID name), :687 (rm exact name, rmi only when pulled), :705 (no prune/reset text) | closed |
| T-30-17 | Spoofing | false pass of the FUSE or removal proof | medium | mitigate | `fuse_verdict` passes only on rc 0, the exact version line, no `failed to utilize FUSE`, `/dev/fuse` present and a FUSE mountinfo entry for the printed mount point (tests/e2e_ghostty_driver.py:124-145, `fuse_mount_observed` :148-160); `observe_fuse_mount` terminates the process it started (:163-186); `run_lifecycle` always runs the uninstall verdict (:75). Tests: tests/test_container_e2e_ghostty.py:81, :98, :108, :124, :145-231, :269-357. The 30-05 transcript records `fuse: UNPROVEN, extract-and-run proven`, so the proof stays honest rather than faked | closed |
| T-30-18 | Repudiation | registry comment / skill row claiming an unpassed container proof | medium | mitigate | 30-05-SUMMARY.md holds the one line `ghostty-container: PASS (2026-11-20; fuse: UNPROVEN, extract-and-run proven)`; the registry comment says the FUSE mount is "checked on a Bazzite host (UAT)" and the skill row wording is pinned. Tests: tests/test_registry.py:2372 (dated paragraph required), tests/test_tool_onboarding_skill.py:642 | closed |
| T-30-SC | Tampering | package installs | high | mitigate | `git diff 63ffc8a1..HEAD --stat -- pyproject.toml uv.lock package.json package-lock.json .pre-commit-config.yaml Makefile` is empty. The only fetched artifact is the digest-pinned AppImage (T-30-01); the box's `dnf install zsh fuse fuse3` runs inside the disposable container only | closed |

*Status: open - closed - open below high threshold (non-blocking)*
*Severity: critical > high > medium > low - only open threats at or above workflow.security_block_on count toward threats_open*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-30-01 | T-30-01 (residual) | Rebuild tags such as `v1.4.0+1` keep the plain asset version, so a rebuild needs a manual pin edit; stated in the registry comment | declared in the plan | 2026-11-20 |
| AR-30-02 | T-30-07 (residual) | Between the symlink check and `atomic_write_bytes` a regular-file swap of a receipt-owned menu file goes undetected; stated `shortcut:` (appimage_menu.py:90) | declared in the plan | 2026-11-20 |
| AR-30-03 | T-30-08 / T-30-12 (residual) | `config-file` includes are reported (`you include other files`), not followed | declared in the plan | 2026-11-20 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-20 | 19 | 19 | 0 | gsd-security-auditor, orchestrator-written |

Verification run (targeted, no full suite): `tests/test_appimage_menu.py`, `tests/test_ghostty_catalog.py`, `tests/test_desktop_entry.py`, and the ghostty/appimage/note/desktop/menu/render selections of `tests/test_model.py`, `tests/test_download.py`, `tests/test_terminal_keys.py`, `tests/test_terminal_shell.py`, plus `tests/test_container_e2e_ghostty.py::test_ghostty_driver_refuses_outside_the_container`: 141 passed. No podman, ghostty or AppImage was launched; scratch directory removed.

Notes, none blocking:

- Test-name gaps against what the plans claim (the mitigations are in code and covered by other tests): (a) `test_a_symlink_out_of_the_work_dir_is_refused` (T-30-05) is `test_extraction_failures_write_nothing[symlink]` (tests/test_appimage_menu.py:185); it plants the symlink only on the `.desktop` file, the icon path shares the same `staged_member` call but is not planted; (b) `test_scan_ghostty_reports_an_unreadable_file_and_stays_silent_for_a_missing_one` (T-30-11) is split across tests/test_terminal_keys.py:535 and :551; `staged_member` has no direct unit test.
- Residual observation (low, below the block threshold, not a threat flag): `ghostty_chord` does not normalize Ghostty's `physical:` or `unicode:` key prefixes (terminal_regions.py:487-500), so a user's `ctrl+shift+physical:k` binding in the legacy `config` file, which loads before `config.ghostty`, is not seen as taken and the installer's `ctrl+shift+k` line could shadow it. Needs a hand-written physical-key binding of the exact chord; no data is lost.
- Residual observation (low): a reinstall replaces a menu file recorded in the previous receipt by path without re-checking its fingerprint (appimage_menu.py:41-49), so a user's hand edit of the installer-created `.desktop` is overwritten. The path is the installer's own and the content is regenerated.
- `--security-opt label=disable` (SELinux label separation off) is passed to the container so `/dev/fuse` works; it is documented in the verb and pinned by tests/test_container_e2e_ghostty.py:596. It is not a privileged mode and adds no capability.
- The FUSE mount of the AppImage is not proven in a container (`fuse: UNPROVEN`); the registry comment defers it to a Bazzite host UAT. This is a verification gap, not an open security mitigation.
- The summaries carry no `## Threat Flags` sections, so there are no summary flags to map; no unregistered flags.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented
- [x] `threats_open: 0` confirmed
