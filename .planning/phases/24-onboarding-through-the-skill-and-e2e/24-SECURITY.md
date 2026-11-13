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

**SECURED** - 43/43 closed (35 `mitigate` verified in code, 9 `accept` logged below, 0 unregistered
flags). T-24-32 was re-dispositioned by the orchestrator on 2026-11-13 from `mitigate` to `accept`:
the auditor found the register's "no checksum-less fallback" overstated the code, which by CONTEXT
D-09 ("digests apply when the API provides them") installs a digest-less herdr asset as `unverified`
and shows that to the user (`render.py:672-674`). The production resolver supplies GitHub's API
digests, so the fallback only applies when GitHub omits them.

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
