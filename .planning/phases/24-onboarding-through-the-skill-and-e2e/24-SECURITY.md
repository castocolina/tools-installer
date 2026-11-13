---
phase: 24
slug: onboarding-through-the-skill-and-e2e
status: secured
asvs_level: 1
block_on: high
threats_total: 43
threats_closed: 42
threats_open: 0
threats_open_nonblocking: 0
audited_at: 2026-11-13
audited_head: 46207b9
---

# Phase 24: Security Audit

Retroactive verification of the nine PLAN `<threat_model>` registers (T-24-01..T-24-42 and
T-24-SC; no ID was added by the review rounds: 24-REVIEW.md, 24-REVIEWS.md and the three lane
files name none) against the code at HEAD `46207b9` (product fixes merged at `4cf1bb2`, harness
fixes at `7665e38` and `f484ea9`). Config: ASVS L1 (a mitigation is verified present in the cited
file), with the focus areas read at L2 depth (boundary and data flow). Source is read-only; no
installer, `make` target, container, podman, distrobox or herdr was run. The tests named in the
registers were located by `def` (all 25 exist) and these suites were run in the pytest sandbox
(scratch HOME, `uv run pytest -n 0 --no-cov -q`): cargo_distrobox, agent_settings, agent_env,
terminal_shell, postinstall, update, engine, model, uninstall, ownership,
container_e2e_receipts, makefile, docs, receipts, executors, download, desktop_entry, sandbox,
registry, app, setup, version_status, resolve: 2745 passed, 0 failed, 0 skipped, exit 0.

## Verdict

**SECURED** - 43/43 closed (35 `mitigate` verified in code, 9 `accept` logged below, 0
unregistered flags). T-24-32 was re-dispositioned by the orchestrator on 2026-11-13 from `mitigate`
to `accept`: the register's "no checksum-less fallback" overstated the code, which by CONTEXT D-09
("digests apply when the API provides them") installs a digest-less herdr asset as `unverified`
and shows that to the user (`render.py:672-674`); GitHub's API digests verify whenever present.

## Threat Verification

| ID | Category | Sev | Disposition | Evidence (file:line) | Verdict |
|----|----------|-----|-------------|----------------------|---------|
| T-24-01 | Tampering | high | mitigate | `cargo_distrobox.py:41` `_TAG_RE` (no leading dash, no `/`, space or `;`); `:253-255` checked right after the resolve, before `_refuse_foreign_binary`, the image query, the temp dir and any box; `:120` `git clone ... --branch tag -- url`; every step is an argv list (`_Run.step` `:81-92`), no shell. Test `test_cargo_distrobox.py:341` (`-x`, `a b`, `""`, `v1;rm`, `--upload-pack=x`; asserts the run root stays empty) | CLOSED |
| T-24-02 | Tampering | high | mitigate | `model.py:185` `_CARGO_HOST_ROOTS`; `:494-541` `_cargo_distrobox_refusal`: host under `~/.local/`, `~/.config/`, `~/.terminfo/` with no empty/`.`/`..` part, control chars refused, box relative with no `..`, first host under `~/.local/bin/`, hosts distinct; wired at load `:784`. Run time: `executors.py:67-78` `staged_member` resolves the box path and requires a regular file inside the run dir. Tests in `tests/test_model.py` (rejection cases) pass | CLOSED |
| T-24-03 | Tampering | medium | mitigate | `cargo_distrobox.py:28` `RUN_ROOT=/tmp`, `:265` `mkdtemp(dir=RUN_ROOT)`; `:106-107` `--home <tmp>`; `:89` `XDG_CACHE_HOME=<tmp>/cache`; clone, manifest and tic output all under `tmp` (`:120-137`). Test `test_cargo_distrobox.py:203` | CLOSED |
| T-24-04 | Denial of service | high | mitigate | `cargo_distrobox.py:270-285` `try/finally`: `.new` files unlinked (failures become notes), then `_cleanup` `:205-228` (`distrobox rm --force --rm-home`, `podman rmi` when pulled, `rmtree` in an inner `finally`, a leftover run dir reported, F14). `finally` also runs on `KeyboardInterrupt`. A failed `rm` names the box and the command. Tests `test_cargo_distrobox.py:258`, `:272`, `test_a_failed_box_removal_names_the_box` | CLOSED |
| T-24-05 | Tampering | high | mitigate | `cargo_distrobox.py:44-50` tri-state `podman image exists` (exit 1 -> False, other -> None); `:259` `pulled = state is False`; `:218` `podman rmi <image>` with no `--force`; existing/unknown image kept and named `:261-264`; a failed rmi (in use) is a note `:219-223`. Tests `:283`, `:292`, `:318`, tri-state `:307` | CLOSED |
| T-24-06 | Tampering | low | accept | See accepted risks. `cargo_distrobox.py:124` `cargo build --release --locked`; staged binary smoked before the swap `:169-170` | CLOSED |
| T-24-07 | Elevation | high | mitigate | Repo-wide grep: no `sudo`/`pkexec`/`doas` argv in `installer/`, `setup.py`, `Makefile`; matches are hand-off text (`executors.py:640-642`, `systemd_daemon.py:846-848`, `session.py:763`) and the AST gate list `model.py:552`. dnf/apt/pacman Alacritty methods stay manual (`registry.toml:3038-3046`). Test `test_cargo_distrobox.py:251` | CLOSED |
| T-24-08 | Tampering | medium | mitigate | `cargo_distrobox.py:155-159` a pre-existing non-binary path no receipt records is kept and named, never staged; `record` keeps only non-preexisting leaves (`engine.py:275-279`, `receipts.py:493-497`); `uninstall.py:59-62` only the binary is ownership evidence; removal intersects receipt with formula (`_receipt_proof` `uninstall.py:165`); `_prune_empty_parents` `:531-548` only empty dirs below `~/.terminfo` and strictly below `~/.local/share/{applications,icons}`. Tests `test_cargo_distrobox.py:380`, `test_uninstall.py:3283`, `:3253`, `test_ownership.py:3137` | CLOSED |
| T-24-09 | Tampering | high | mitigate | `agent_settings.py:363-401` `_insert_toml`: nested key spliced after its exact `[a.b]` header, each candidate checked by `_guarded` (whole-document parse against the expected dict); an existing table with no accepting header refuses `:388` (never a second header). Commit via `write_if_unchanged` `:562-569` (snapshot match, else `SettingsChanged`). Tests `test_agent_settings.py:1639`, `:1732` | CLOSED |
| T-24-10 | Tampering | high | mitigate | Absent-only `_apply_pass`; a different value is `set_by_you` and dropped. F2: a value replaced only when the ledger records it AND the file still holds that recorded value (`same_value`), via `swap_recorded` `:533-548` (guarded) | CLOSED |
| T-24-11 | Tampering | high | mitigate | `_revert_once` `agent_settings.py:1132-1140` builds the dynamic table only from ledger entries whose key path is in the code-owned `DYNAMIC_KEYS`; revert removes only while the key holds the recorded value, else `kept_changed`. F7 fallback removes only the owned leaf, still guarded (`_toml_removal` `:428-455`). Test `test_agent_settings.py:1536` | CLOSED |
| T-24-12 | Tampering | low | accept | See accepted risks. `agent_env.py:46-56` only absolute `HERDR_CONFIG_PATH`/`XDG_CONFIG_HOME`; `tests/sandbox.py:749` clears `HERDR_CONFIG_PATH` (`test_sandbox.py:129`) | CLOSED |
| T-24-13 | Tampering | medium | mitigate | `test_docs.py` `test_tool_onboarding_skill_keeps_the_policies_rule_verbatim`, `test_tool_onboarding_skill_terminal_bullet` (pass) | CLOSED |
| T-24-14 | Repudiation | low | mitigate | `24-SKILL-JUDGE.md:14-17` and `:34-39` both verdict lines (67.2% and 68.8%) with JSON and the comparison | CLOSED |
| T-24-15 | Elevation | high | mitigate | `scripts/container-e2e-verify.sh` installs only via `ct exec` (`exec_root`/`exec_tester`); `Makefile` e2e entry only. Tests `test_container_e2e_receipts.py:1688`, `test_makefile.py:154`. 24-08 SUMMARY: runs by the orchestrator only | CLOSED |
| T-24-16 | Elevation | medium | accept | See accepted risks. `container-e2e-verify.sh:1570` `--device /dev/fuse --security-opt label=disable`, no `--privileged` anywhere in the script; `:1850` `trap nested_teardown EXIT`. Tests `test_container_e2e_receipts.py:2424` (`privileged` absent), `:2794`, `:2438` | CLOSED |
| T-24-17 | Denial of service | medium | mitigate | `container-e2e-verify.sh:112-113` per-distro `tools-installer-e2e-<distro>` and `.e2e-artifacts/container-<distro>`; nested `:35`, `:1847`. Test `test_container_e2e_receipts.py:1645` | CLOSED |
| T-24-18 | Repudiation | medium | mitigate | Rerun gate (five unexpected kinds, manual set compare). Test `test_container_e2e_receipts.py:1773` (parametrized per kind) | CLOSED |
| T-24-19 | Tampering | high | mitigate | `update.py:455-462` the rebuild calls `cargo_distrobox.install`, which validates the tag `cargo_distrobox.py:253-255` before any box | CLOSED |
| T-24-20 | Tampering | high | mitigate | Update writes only `artifact_paths` hosts through `_stage`/`_swap`; config dir checksum pinned by `test_update.py:2242` | CLOSED |
| T-24-21 | Denial of service | medium | mitigate | `cargo_distrobox.py:173-202` `_swap` records each move first, rolls back on `BaseException` (F9) and re-raises; `.old` deleted only after every swap; receipt written by the caller after `install` returns (`update.py:395-403`). Tests `test_update.py:2331`, `:2353` | CLOSED |
| T-24-22 | Tampering | high | mitigate | `terminal_shell.py:526-534` user document parsed outside the owned regions; per-part plans `:551-599` (conflict -> `partial:`, inline bindings or `import` -> refusal, F13); `_commit_alacritty` `:602-624` `tomllib.loads(updated)` then `write_if_unchanged`. Tests `test_terminal_shell.py:1219`, `:1271` | CLOSED |
| T-24-23 | Tampering | high | mitigate | `_sync_herdr` `terminal_shell.py:796-827` goes through `apply_value` (absent-only, ledgered); `set_by_you` is reported `_HERDR_PARTIAL`, value untouched. Test `test_terminal_shell.py:1435` | CLOSED |
| T-24-24 | Tampering | medium | mitigate | `_safe_executable` `terminal_shell.py:139-146` (absolute, no C0/DEL) on zsh `:907`, alacritty `:992`, herdr `:1002`; `_toml_string` `:511-514` `json.dumps(ensure_ascii=False)` (F11) and the re-parse in `_commit_alacritty`; `desktop_entry.py:20-33` same posture plus Exec quoting | CLOSED |
| T-24-25 | Denial of service | low | accept | See accepted risks. `_herdr_reload` `terminal_shell.py:761-769` failure is a note; bounded `run_bounded` (`run.py`, F12) | CLOSED |
| T-24-26 | Elevation | medium | mitigate | `model.py:141` `SENSITIVE_POST_INSTALL_ACTIONS = ()`; `installer/policy.py` unchanged in the phase (`git diff --stat` empty); `apply_terminal_tuning` takes no confirm (`post_install.py`, `del ... confirm`). Test `test_model.py:1927` | CLOSED |
| T-24-27 | Tampering | high | mitigate | `postinstall.py:339-376` `_herdr_register`: unreadable status registers nothing (`:352`), `current` and unlisted hosts skipped; `_herdr_sidebar` records nothing when the plugin is listed or the list is unreadable (JSON parse, E3). Tests `test_postinstall.py:488`, `:509`, `:787` | CLOSED |
| T-24-28 | Tampering | medium | mitigate | `postinstall.py:234` full 40-hex SHA `2b5ca2aedf06...`; `--ref <sha> --yes` only together (`_herdr_sidebar`); `registry.toml:3063-3065` `# Verified` | CLOSED |
| T-24-29 | Elevation | medium | accept | See accepted risks. Plugin installed only with python3 present and pinned ref; no sort action in `_KEYS[("herdr","sidebar")]` (`agent_settings.py`, rows/row_gap only) | CLOSED |
| T-24-30 | Tampering | medium | mitigate | `postinstall.py:435` `unregister_hosts` keeps only ids in `pair.targets`/`pair.standalone`; `_herdr_unregister` `:378-387` maps through `_HERDR_TARGETS` and the fixed plugin id. Test `test_postinstall.py:729` | CLOSED |
| T-24-31 | Tampering | medium | mitigate | Tests `test_app.py:6831` and 23.2's `test_app.py:4884` (hook tools removed before agent reverts) | CLOSED |
| T-24-32 | Spoofing | medium | accept (was mitigate) | API digest verifies when present (`download.py:131`, `_fetch_verified`; `test_download.py:2265`). **But** `download.py:130-139`: with no checksum template and no API digest, the asset installs with `unverified_reason` (`render.py:672-674` shows it); `release_resolver` `versions.py:417-419` returns an empty digest map for any non-identity resolver. The register's "no checksum-less fallback" is not true in code; `registry.toml:3052-3053` and CONTEXT D-09 ("digests apply when the API provides them") document the fallback | CLOSED (accepted, D-09) |
| T-24-33 | Elevation | high | mitigate | 24-08-SUMMARY `:107-160`: sequential runs by the orchestrator, `TRACER_*_TEARDOWN_OK`, post-run `podman ps -a` listed no `tools-installer-e2e-*` (`:120`, `:160`). Executor SUMMARY threat flags confirm no container run by executors | CLOSED |
| T-24-34 | Tampering | medium | accept | See accepted risks | CLOSED |
| T-24-35 | Repudiation | low | mitigate | 24-08-SUMMARY `:100-160` tracer lines, exit codes and container checks pasted | CLOSED |
| T-24-36 | Repudiation | high | mitigate | `cargo_distrobox.py:286-292` raises `ExecutorError` after cleanups; engine ends FAILED before any receipt. Test `test_engine.py:2474` | CLOSED |
| T-24-37 | Repudiation | medium | mitigate | Tests `test_container_e2e_receipts.py:1596` (stubs bootstrap/pass1/pass2, drives only `ct`-bound functions), `test_makefile.py:154` | CLOSED |
| T-24-38 | Tampering | high | mitigate | `executors.py:450-457` `f="$(mktemp)"`, `trap 'rm -f "$f"' EXIT`, `curl -fsSL --retry 3 --retry-all-errors -o "$f" -- <shlex-quoted url> && <shell> < "$f"`; args `shlex.quote`d `:445-449`. Test `test_engine.py:2573` | CLOSED |
| T-24-39 | Repudiation | high | mitigate | Same `&&`: curl's status is `sh -c`'s status; row FAILED, no receipt. Test `test_engine.py:2573` | CLOSED |
| T-24-40 | Spoofing | low | accept | See accepted risks. `receipts.py:52`, `:229-231`, `:524` release regex at read and record; `version_status.py:1757-1768` release counts only with no `broken` and no unproven note | CLOSED |
| T-24-41 | Tampering | high | mitigate | `versions.py:422-435` `capturing_resolver` wraps the ReleaseResolver and returns the `Release` unchanged; used at `engine.py:228`, `update.py:352`. Test `test_engine.py:2663` | CLOSED |
| T-24-42 | Repudiation | medium | mitigate | `origin/main` = HEAD `46207b9`, ancestor check passes; 25 forward `fix(24...)` commits; reflog shows no amend/rebase/reset of phase-24 commits after the push | CLOSED |
| T-24-SC | Tampering | high | accept | See accepted risks. `git diff --stat d7fe25d~1..HEAD -- pyproject.toml uv.lock` is empty | CLOSED |

## Focus-area findings

- **Zero sudo/pkexec/doas.** Grep plus `test_no_argv_escalates` and the `ELEVATION_COMMANDS`
  AST gate. The e2e harness grants passwordless sudo to its tester only inside the disposable
  container (`container-e2e-verify.sh:210`), never on the host.
- **Registry/receipt data into argv.** `repo`, `image`, `packages`, `artifacts` validated at load
  (`model.py:494-541`); the tag at run time (`cargo_distrobox.py:254`); receipt `release` at record
  and read; recorded hook ids filtered through code-owned maps. Box steps are argv lists. The one
  shell string (script kind) quotes the URL and every arg. `--additional-packages` joins
  regex-checked names (`[A-Za-z0-9][A-Za-z0-9.+_-]*`), so the box's own shell gets no metacharacter.
- **Artifact containment.** Host roots and no `..` at load; box members resolved and contained
  in the run dir; removal = receipt AND formula; parent pruning bounded and non-recursive.
- **Cleanup.** Box, pulled image and run dir in `finally` (interrupts included); a pre-existing
  or unknown image is never removed; `rmi` never `--force`.
- **User-owned files.** Alacritty: marker regions, conflict/import refusals, re-parse,
  compare-before-commit; a config the installer created is deleted on strip only when the marker
  exists and the file is whitespace-only. herdr config: absent-only ledgered writer. A user binary
  at the install path is refused before the build (`_refuse_foreign_binary`, `cargo_distrobox.py:231-244`);
  a pre-existing desktop/icon/terminfo leaf is kept. User-owned herdr integrations (`current`)
  and a listed plugin are never recorded, so never undone.
- **Guarded writers.** TOML/JSON edits go through `_guarded` (whole-document parse against the
  expected dict) and `write_if_unchanged` (identity + bytes); Alacritty adds `tomllib` re-parse.
- **curl download-then-run.** Complete file first, `&&`, temp file trapped.
- **Tests never touch the real HOME.** Autouse `sandboxed_home` and session `real_home_untouched`
  (`tests/conftest.py:178`, `:256`); launch allowlist recurses through `timeout`/`env` prefixes and
  refuses host programs (podman, cargo, docker, dnf, apt...); `HERDR_CONFIG_PATH`,
  `XDG_CONFIG_HOME`, `XDG_DATA_HOME` cleared; `cargo_distrobox.RUN_ROOT`, `image_exists`,
  `herdr_query`, `has_python3` are replaced in tests. The run above passed with the session guard.
- **e2e never `--privileged`.** Script grep and two tests (`:2424`, `:2794`).

## Accepted Risks Log

| ID | Risk | Rationale | Owner |
|----|------|-----------|-------|
| T-24-06 | Mutable upstream tag content | `cargo build --locked` uses the tag's Cargo.lock; no signed source digest exists upstream; the staged binary is smoked and its version probed | phase 24 |
| T-24-32 | herdr raw binary installed without a digest when GitHub's API omits one | CONTEXT D-09: herdr ships no checksum file; API digests verify whenever present; a digest-less asset is labelled `unverified` in the run output, never silent | phase 24 |
| T-24-12 | `HERDR_CONFIG_PATH`/`XDG_CONFIG_HOME` choose the herdr file written | The user's own environment; absolute values only, mirroring herdr's resolution; compare-before-commit; cleared in tests | phase 24 |
| T-24-16 | Nested outer container gets `/dev/fuse` and `label=disable` | Never `--privileged`; rootless inner user; EXIT-trap removal; needed only for the one real build (D-18), which proved infeasible unprivileged (24-REVIEW.md) and stays with UAT test 6 | phase 24 |
| T-24-25 | `herdr server reload-config` may fail | Best effort, bounded, a note; open panes keep their shell (D-08b) | phase 24 |
| T-24-29 | The pinned plugin runs `python3 mark.py` as the user | The user's own repository at a full commit SHA, the reviewed feature (D-12); sort actions never enabled | phase 24 |
| T-24-34 | The UAT runs on the user's host | By design (SPEC R9, AGENTS.md); read-only checks plus catalog installs/removals the user chooses; test 6 names the image it may pull | phase 24 |
| T-24-40 | A hand-edited receipt `release` hides an update notice | Counts only while every fingerprint matches; malformed value -> receipt untrusted; affects only the user's own notice | phase 24 |
| T-24-SC | Supply chain of npm/pip/cargo installs | No dependency file changed; distro packages install only inside disposable boxes/containers | phase 24 |

## Open Threats

### Blocking (severity >= high)

None.

### Non-blocking (below `block_on: high`)

| ID | Sev | Expected | Found | Files searched | Suggested action |
|----|-----|----------|-------|----------------|------------------|
| T-24-32 | medium | "no checksum-less fallback" for herdr's raw binary | `installer/download.py:130-139` installs a digest-less asset as `unverified` (shown, not silent); `installer/versions.py:417-419` | `installer/download.py`, `installer/versions.py`, `installer/registry.toml:3048-3102`, `installer/engine.py`, `installer/render.py` | Either re-disposition T-24-32 to `accept` (matches D-09 and the registry comment), or add a per-method "digest required" refusal for herdr's two methods so a missing digest fails the row |

## Unregistered Flags

None. Every SUMMARY `## Threat Flags` / `## Threat surface` section reads None or maps to a
register ID (24-01 all, 24-02 T-24-12, 24-04 T-24-16, 24-05 T-24-19/20, 24-06 T-24-22/23/24,
24-07 T-24-30, 24-09 T-24-38/39).

## Residuals (informational, not counted in threats_open)

| ID | Sev | Note |
|----|-----|------|
| R1 | LOW | `_refuse_foreign_binary` (`cargo_distrobox.py:231-244`) checks the binary path before a build of up to 30 min; `_swap` does not re-check, so a user file dropped at `~/.local/bin/alacritty` during the build would be moved to `.old` and deleted. Re-run the check just before `_swap` |
| R2 | LOW | `_drop_created_config` (`terminal_shell.py:734-747`) reads then `unlink`s without compare-before-commit, and the created marker does not name which candidate path was created. Only a whitespace-only file can be deleted, so no content is lost. `agent_settings.delete_if_unchanged` already exists for this |
| R3 | LOW | `pulled = state is False` is decided before the box is created; an identical image pulled by the user during the build would be removed by `podman rmi` (no `--force`, so never while in use) |
| R4 | LOW | `nested_start` (`container-e2e-verify.sh:1567`) force-removes any container named `tools-installer-e2e-nested`, so two concurrent nested runs clobber each other. Mitigated by the sequential-runs rule (T-24-33) |
| R5 | LOW | Known `shortcut:` in `_swap` (`cargo_distrobox.py:179-180`): a stale `.tools-installer.old` from an earlier failed rollback could be restored on an interrupt before the first move (recorded in 24-REVIEW.md) |

Also carried from 24-REVIEW.md Deferred: `--home` does not isolate the build from `/run/host`
(Distrobox design, runs as the user, accepted); build tree under host `/tmp` (R1-14, UAT test 6).

**threats_open:** 0
