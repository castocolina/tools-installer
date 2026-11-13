---
phase: "24"
reviewed: 2026-11-13
range: 9e2ff7b..6c498be
lanes:
  - deep: 24-REVIEW-deep.md (gsd-code-reviewer) — 0 CRITICAL, 2 HIGH, 3 MEDIUM, 5 LOW
  - ponytail: 24-REVIEW-ponytail.md — 0 HIGH, 3 MEDIUM, 7 LOW
  - external: 24-REVIEW-external.md (opencode referee-one/three; referee-two unavailable) — 0 CRITICAL, 2 HIGH, 14 MEDIUM, 6 LOW
status: fixing
---

# Phase 24 — Consolidated Code Review

Every HIGH was verified against the code by the lane that raised it and re-read by the orchestrator.
IDs below are the fix IDs the fix commits name; the source IDs are in brackets.

## HIGH (fix)

| ID | Source | Finding | Owner |
|----|--------|---------|-------|
| F1 | deep HR-01, external H-1, ponytail M1 | `alacritty_config_path` misses `~/.alacritty.toml`; the install creates `~/.config/alacritty/alacritty.toml`, which Alacritty reads first, hiding the user's whole config; strip leaves the emptied file behind | product |
| E1 | external H-2, M-1 | the nested podman probe runs `true` in `quay.io/podman/hello` (FROM scratch, no `true`), so `TRACER_NESTED_PODMAN_OK` can never print; `podman rmi` is chained after the failing run, so the hello image stays and a later build reads `TRACER_NESTED_IMAGE_LEFT`. The recorded "nested infeasible" verdict is not evidence until re-run | harness |

## MEDIUM (fix)

| ID | Source | Finding | Owner |
|----|--------|---------|-------|
| F2 | deep HR-02 (rated HIGH there), external M-7 | herdr `default_shell` written by the installer reads `set_by_you` when the resolved zsh path changes; the ledger entry is dropped and the key is never reverted (dead shell path after zsh/herdr removal). Replace the value when the ledger records it as ours | product |
| F3 | deep MR-01, ponytail M2, external M-12 | `cargo_distrobox.install` does not catch `ExecutorError`, so cleanup notes (a box that could not be removed) are lost; the `.new` unlink loop in `finally` can skip `_cleanup` on `OSError` | product |
| F4 | external M-9 | `_hook_fact` emits two `hook_register` steps when targets and `sidebar-markers` are both pending; the second fails and a successful reconfigure reads failed | product |
| F5 | external M-10 | `_drop_deleted_ledgers` lets a `write_ledger` `OSError` abort the rest of uninstall | product |
| F6 | external M-13 | Distrobox follows `DBX_CONTAINER_MANAGER` while image accounting and `rmi` hardcode podman; pin `DBX_CONTAINER_MANAGER=podman` for every Distrobox step | product |
| F7 | external M-8 | a user comment under an installer-created TOML table makes the recorded block mismatch and the revert refuses, leaving the installer key; fall back to removing the owned leaf key, keeping header and comments (still guarded) | product |
| F8 | external M-14 | after a partial uninstall the binary-only evidence hides surviving receipt-recorded cargo artifacts from the removal plan | product |
| F13 | external M-11 | Alacritty `[general] import` files are not followed, so the conflict guards miss imported shell/bindings; refuse the tuning with a named reason when the config imports files | product |
| E2 | deep MR-03, external M-2 | any failure text with "distrobox create" classifies infeasible; classify infeasible only on known environment errors, else `TRACER_NESTED_BUILD_FAILED` | harness |
| E3 | external M-3 | herdr plugin check is a substring match; parse the JSON plugin list | harness |
| E4 | external M-4 | the empty-container exemption in `settings_probe_revert` is not tied to herdr | harness |
| E5 | external M-5 | herdr probe checks only recorded hosts, not present ones | harness |
| E6 | external M-6 | `TRACER_DISTRO_MISCONFIGURED` fires on a re-run pass 1 where everything is skipped | harness |

## LOW (fix — small and contained)

| ID | Source | Finding | Owner |
|----|--------|---------|-------|
| F9 | external L-1, deep LR-03 | `_swap` rolls back only on `OSError`; roll back on `BaseException` and re-raise | product |
| F10 | external L-2 | ownership drops `cargo_distrobox` when Distrobox/Podman are off PATH; keep the receipt-backed method, gate only the rebuild with a prerequisite message | product |
| F11 | external L-3 | TOML strings via `json.dumps` escape non-BMP characters as surrogates (invalid TOML); use `ensure_ascii=False` | product |
| F12 | deep LR-04 | `herdr server reload-config` has no timeout | product |
| F14 | deep LR-01 | `distrobox rm --rm-home` does not remove the box home in 1.8.2.5; a failed `rmtree` of the run dir is never reported | product |
| E7 | external L-4 | pass2 after a chunked pass1 guarantees `TRACER_RERUN_UNEXPECTED`; refuse it with a message | harness |
| E8 | external L-6 | a failing pass2 exits before printing its transcript | harness |
| E9 | external L-5 | `nested_uninstall_ok` should check the five recorded files only | harness |

## Deferred (with reason)

| Source | Finding | Reason |
|--------|---------|--------|
| deep MR-02 | Alacritty keybindings outlive a full uninstall when Alacritty is distro-owned | Same semantics as every install tuning: reverted with the tool the installer removes. Changing "full uninstall reverts tuning of tools it keeps" is a cross-cutting design decision → todo |
| deep LR-02, ponytail L | `curl --retry-all-errors` needs curl ≥ 7.71 | Every supported platform ships a newer curl (macOS 13+, Fedora/Debian 13/Arch current); recorded in the TLS-retry todo |
| deep LR-05, ponytail L | build tree under host `/tmp` (tmpfs/noexec) | Plan decision R1-14 (`/tmp` is the dir distrobox mounts); real build size unmeasured until UAT test 6 → todo |
| ponytail L | `--home` does not isolate the build from `/run/host` | Distrobox design; the build runs as the user, never root (zero sudo) — accepted |
| ponytail L | herdr "needs repair" integration re-installed and recorded | Plan decision (24-07: `not installed` and `needs repair` are installed and recorded) |
| ponytail L | "kept the existing image" note on success | D-19 requires naming a kept image |
| ponytail L | existing `~/.local/bin/alacritty` overwritten unrecorded | Ownership reads a present binary as the user's and skips the install; overwrite needs a forced reinstall path → verify in the fix loop, else todo |
| ponytail M3 | the real Distrobox build never ran in automation | Addressed by E1/E2 and a nested re-run; else UAT test 6 |
