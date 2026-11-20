---
phase: "29"
slug: "terminal-defaults-for-the-terminals-in-the-catalog"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: "2026-11-20"
---

# Phase 29 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Base 9adc1bb0, HEAD 1da53d2c. Verified against the code, not the summaries.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| installer -> user's terminal config files | Owned regions are inserted or rewritten in `kitty.conf`, `wezterm.lua`, `alacritty.toml` that the user also edits | config text, user bindings |
| user kitty.conf -> include scan | `include`/`globinclude` names arbitrary paths the read-only scan opens | file names only, never contents |
| installer -> `wezterm` binary | `show-keys` read-back runs the user's WezTerm on the user's config | argv, config path, stdout text |
| uninstall -> created config file | Strip may delete a file the installer created | recorded path, seed text |
| KDE `sessionui.rc` -> installer | A user-controlled file read to decide a report | text, never written |
| harness script / driver -> container runtime | Creates and removes one container and maybe the base image | container name, image name |
| skill text -> onboarding agents | Agents apply the closed table without asking | table cells |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Evidence | Status |
|-----------|----------|-----------|----------|-------------|----------|--------|
| T-29-01 | Tampering | `replace_owned_region` TOP / BEFORE_RETURN | medium | mitigate | Placement used only when no complete region exists (installer/terminal_regions.py:213-223); BEFORE_RETURN raises `TerminalShellError` (an `OSError`) unless exactly one `return config` line (:219-221); every write goes through `commit_region` validate + compare-before-commit. Tests: tests/test_terminal_keys.py:1291 (TOP), :1308 (BEFORE_RETURN, zero and two returns refuse), :949 (apply and status refuse) | closed |
| T-29-02 | Tampering | Alacritty drift rewrite | low | mitigate | Only a present, stale region on `skip_recorded=True` is rewritten (installer/terminal_keys.py:341-361); deleted region stays deleted. Tests: tests/test_terminal_keys.py:660, :1196, :1655 | closed |
| T-29-03 | Denial of Service | `KeysRow.readback` | low | mitigate | Called once, after `commit_region` and the record write, past every refusal/quiet return (installer/terminal_keys.py:378); `CommandError` becomes one note (:249-253). Tests: tests/test_terminal_keys.py:800-856 (failed command, refusal never reads back) | closed |
| T-29-04 | Tampering | WezTerm shell region detection | medium | mitigate | Ownership is the exact marker line (`marker()` full-line match in `replace_owned_region`); `_wezterm_content` detects the shell region with `replace_owned_region(..., None) != existing` (installer/terminal_shell.py:187-193). Tests: tests/test_terminal_keys.py:934 (lookalike comment), tests/test_terminal_shell.py:307, :327 | closed |
| T-29-05 | Tampering | kitty region vs user maps | medium | mitigate | `OwnedRegion(KITTY_KEYS, "#", Placement.TOP)` (terminal_keys.py:~296); taken chords skipped and reported (`kitty_maps`, terminal_regions.py); `validate_kitty` runs in `commit_region`. Tests: kitty golden tests (tests/test_terminal_keys.py:398, :413), TOP placement :1291 | closed |
| T-29-06 | Information Disclosure | include scan reads | low | mitigate | Read-only; `read_capped(target, 1 << 20, follow_symlinks=True)` (terminal_regions.py:356); only `target.name` enters a report (:362-365); never written; depth 8 (:330), 64 files, visited set (:303, :349-354). Tests: tests/test_terminal_keys.py:538 (cycle), :592 (depth), :603 (64 files), :519 (unreadable) | closed |
| T-29-07 | Denial of Service | FIFO, huge include, huge glob | low | mitigate | `read_capped` opens `O_NONBLOCK`, refuses non-regular and oversize files (installer/atomic.py:186-215); lazy `islice(glob.iglob(...))` (terminal_regions.py:341), the directory-listing limit is a stated `shortcut:`. Tests: tests/test_terminal_keys.py:519 (FIFO include), tests/test_atomic.py:223, :230, tests/test_terminal_shell.py:659 | closed |
| T-29-08 | Elevation of Privilege | macOS install into /Applications | medium | mitigate | macOS script method deleted; cask only (installer/registry.toml:3052-3062); `brew install --cask --appdir=<~/Applications>` (installer/executors.py:700-703, update.py:207). Test: tests/test_registry.py:2590 | closed |
| T-29-09 | Tampering | global Option-as-Alt (kitty) | low | mitigate | `macos_option_as_alt` is never generated. Tests: tests/test_terminal_keys.py:432, :877 | closed |
| T-29-10 | Tampering | WezTerm Lua region | medium | mitigate | Body built only from constants (`wezterm_keys_body`, terminal_regions.py:52; `_wezterm_rows`, terminal_keys.py:~222: key, mods, send are literals, control chars hex-escaped, no file or env text interpolated); chord guard inside the Lua; `validate_wezterm` (terminal_regions.py:96) on every changed write plus the status pass (`validate_on_status`, terminal_keys.py:424). The shell region text takes the zsh path only after `_safe_executable` rejects non-absolute and control-character paths (terminal_shell.py:160-167) and `_lua_string` escapes `\` and `"` (:170). Tests: tests/test_terminal_keys.py:857, :972, :1007-1100 | closed |
| T-29-11 | Tampering | show-keys subprocess | low | mitigate | One seam (terminal_keys.py:239-246): argv list, no shell, `timeout=20`; `run_output` (installer/run.py:109-125) uses `subprocess.run(list, stdin=DEVNULL, start_new_session=True)` and maps timeout to `CommandError`. Output is parsed by regex only. Tests: tests/test_terminal_keys.py:696 (planted wezterm not launched), :710 (exact argv and timeout 20), tests/conftest.py:122 (autouse replacement) | closed |
| T-29-12 | Tampering | uninstall deleting wezterm.lua | medium | mitigate | `_drop_created_config` (terminal_keys.py:461-487) needs the created marker, the path sidecar equal to the path resolved now, and remaining text blank or equal to `WEZTERM_SKELETON`; any other text keeps the file. Behavior confirmed by a scratch probe (seed removed, edited file kept, state cleaned); committed tests cover the bound-path half only (see Notes) | closed |
| T-29-13 | Elevation of Privilege | WezTerm global Alt switch | low | mitigate | `send_composed_key_when_*` never generated. Test: tests/test_terminal_keys.py:877 | closed |
| T-29-14 | Tampering | Konsole sessionui.rc | medium | mitigate | No write path: `_konsole_clear_state` only reads (terminal_shell.py:87-107). Tests: tests/test_terminal_shell.py:1788 (byte-identical, no sibling files), :1745 | closed |
| T-29-15 | Denial of Service | reading sessionui.rc | low | mitigate | `read_capped(path, 1 << 20, follow_symlinks=True)` (terminal_shell.py:92); only `FileNotFoundError` is stock, other `OSError`, non-regular, oversize, bad bytes, missing gui tags are "unknown" (:93-105); regex, no XML parser. Tests: tests/test_terminal_shell.py:1763, :1872, :1886 | closed |
| T-29-16 | Repudiation | removed Konsole chord ignored | low | mitigate | `KONSOLE_CLEAR_REMOVED` warning on every sync, dry run included (terminal_shell.py:749-751). Test: tests/test_terminal_shell.py:1757-1761 | closed |
| T-29-17 | Elevation of Privilege | driver on the developer's host | medium | mitigate | `main` refuses unless `in_container()` (tests/e2e_herdr_keys_driver.py:225; engine file + root-written marker + tester HOME, tests/e2e_landing_driver.py:843-850). Test: tests/test_container_e2e_herdr_keys.py:244 (nothing installed outside) | closed |
| T-29-18 | Tampering | harness removing other containers or images | medium | mitigate | Name `tools-installer-e2e-herdr-keys-$$` (scripts/container-e2e-verify.sh:2922); teardown `ct rm -f` of that exact name and `ct rmi` only when `LANDING_PULLED=1` and not `--keep-image` (:2748-2753); no prune or reset in the script. No sudo added by the verb. Tests: tests/test_container_e2e_herdr_keys.py:286 (every ct call), :306 (teardown), :325 (no prune/reset) | closed |
| T-29-19 | Information Disclosure | caller env into herdr | low | mitigate | Child env is five fixed keys (HOME, XDG_RUNTIME_DIR, PATH, TERM, LANG) passed to `os.execve` (tests/e2e_herdr_keys_driver.py:135-142); the driver prints only verdict lines. No test asserts the five keys (see Notes) | closed |
| T-29-20 | Spoofing | false pass of the byte proof | medium | mitigate | Verdict passes only when every chord's received hex equals expected; pane never started and pty closed early are UNPROVEN. Tests: tests/test_container_e2e_herdr_keys.py:118-172 | closed |
| T-29-21 | Repudiation | skill table drift | low | mitigate | Test: tests/test_tool_onboarding_skill.py:628 (cells follow `TERMINAL_KEYS`/`vendor`), :621 (no `planned (phase 29)`) | closed |
| T-29-22 | Elevation of Privilege | a row writing a global Alt switch | low | mitigate | Test: tests/test_terminal_keys.py:877 applies every row on macos and fedora and rejects the switch text | closed |
| T-29-23 | Tampering | created-file cleanup after the resolver changed | high | mitigate | Sidecar `<created>-path` written in `commit_region` when `bind_path` (terminal_regions.py:541-557); `_drop_created_config` deletes only when the sidecar equals `f"{path}\n"`, otherwise one warning, both records kept (terminal_keys.py:466-476). Test: tests/test_terminal_keys.py:1524 (changed path, missing sidecar, matching sidecar); Alacritty unbound (test :1106) | closed |
| T-29-24 | Tampering | kitty uninstall deleting a user's empty kitty.conf | high | mitigate | `bind_created_path=True` on the kitty row (terminal_keys.py:288); pinned by tests/test_terminal_keys.py:1106 and the sidecar written in tests/test_terminal_keys.py:398-410; mechanism exercised by :1524. The test named in the plan (`test_kitty_cleanup_after_a_resolver_change_leaves_the_other_file_alone`) does not exist (see Notes) | closed |
| T-29-SC | Tampering | package installs | low | accept | No dependency change: `git diff 9adc1bb0..HEAD --stat -- pyproject.toml uv.lock package.json package-lock.json .pre-commit-config.yaml` is empty; herdr is installed by the installer's own digest-checked method inside the container | closed (accepted) |

*Status: open - closed - open below high threshold (non-blocking)*
*Severity: critical > high > medium > low - only open threats at or above workflow.security_block_on count toward threats_open*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-29-01 | T-29-SC | The phase adds no dependency, lockfile or manifest entry; the check is an empty diff | orchestrator (autonomous run, ASVS 1) | 2026-11-20 |
| AR-29-02 | T-29-10 (residual) | An edit after install that is not a `config.keys` assignment (for example `config = {}`) is not detected; stated `shortcut:` in `validate_wezterm` | declared in the plan | 2026-11-20 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-20 | 25 | 25 | 0 | gsd-security-auditor, orchestrator-written |

Verification run: `tests/test_terminal_keys.py`, `tests/test_container_e2e_herdr_keys.py`, `tests/test_atomic.py` (all pass), `tests/test_terminal_shell.py -k "konsole or wezterm or kitty or fifo"` (pass). A scratch probe (removed) drove WezTerm create-then-strip: a seed-only file is deleted, a user-edited file is kept.

Notes, none blocking:

- Test-coverage gaps against what the plans claim (mitigations are in code): (a) no committed test strips a WezTerm-created file with the seed-or-blank rule or keeps an edited one (T-29-12 says "created, edited, not-ours and resolver-change cases"); (b) the named kitty resolver-change test (T-29-24) is absent, only the generic bound-path test (tests/test_terminal_keys.py:1524) and the `bind_created_path` pin cover kitty; (c) no test asserts the herdr child's five-key environment (T-29-19). Removing the kitty or WezTerm wiring of the bound path would fail only the field pin at :1106.
- Unregistered flag (low, below the block threshold): `_KONSOLE_ACTION` (installer/terminal_shell.py:68) backtracks quadratically on a crafted `sessionui.rc` made of repeated `<Action` with no `>` (0.35 s at 80 KB measured; about a minute extrapolated to the 1 MiB cap). It needs write access to the user's own KDE data dir and only stalls the installer. Fix: bound the tag with `[^<>]*`.
- The kitty include scan follows symlinks by design (`follow_symlinks=True`, matching kitty); non-regular targets (FIFO, devices) are refused and contents are never echoed. The scan is bounded by depth 8 and 64 read files but a file of failed or missing includes is bounded only by its 1 MiB size.
- The summaries carry no `## Threat Flags` sections, so there are no summary flags to map.
- The herdr verb adds no sudo, no `system prune/reset`, and logs no secrets; the passwordless sudo in `scripts/container-e2e-verify.sh:268` is the older disposable-container bootstrap, not part of this phase.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented
- [x] `threats_open: 0` confirmed
