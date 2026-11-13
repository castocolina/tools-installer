# Phase 24 external code review (opencode lane), adjudicated

Scope: `git diff 9e2ff7b..HEAD -- installer scripts setup.py Makefile tests` (source files reviewed; tests read as context).
Raw prompts, diffs and logs: `.planning/phases/24-onboarding-through-the-skill-and-e2e/.review-diagnostics/20261113T061536Z-code-review/` (gitignored).

## Lane log

| Lane | Files | Model that produced the result |
|------|-------|--------------------------------|
| A1 | cargo_distrobox, desktop_entry, engine, platform, model, registry.toml | router-env/my-referee-one |
| A2 | resolve, ownership, uninstall, update, download | router-env/my-referee-one |
| B1 | agent_settings, agent_env, receipts | router-env/my-referee-one |
| B2 | terminal_shell, post_install, postinstall, executors, setup.py | router-env/my-referee-one |
| B3 | app, session, render, wizard_app, version_status, versions | router-env/my-referee-one |
| C | scripts/container-e2e-verify.sh, Makefile | router-env/my-referee-three |

Failover history: my-referee-one first failed with "Combo has no executable targets" (all lanes, immediately). my-referee-two streamed for ~15 min, then died on all lanes with "Model grok-cli/grok-4.7-xhigh is unavailable" (no findings). my-referee-three completed lane C; its first-cut whole-area lanes A and B hit the 1500 s timeout with no findings. my-referee-one had recovered by then, so A and B were re-split into five smaller lanes (A1, A2, B1, B2, B3, each with a ~30 tool-call budget) and all five completed on my-referee-one.

Coverage gaps: tests were not reviewed as targets; `registry.toml` got only incidental attention (A1 found nothing there); lane C ran on a single model.

## Counts after adjudication

CRITICAL 0 / HIGH 2 / MEDIUM 14 / LOW 6.

Raw HIGH claims: 4 (A1 `_swap`, B2 Alacritty path, C probe `true`, C stale image). All four verified against the code: 2 stay HIGH, 1 downgraded to LOW, 1 downgraded to MEDIUM.

## HIGH

### H-1. Alacritty config at `~/.alacritty.toml` is shadowed by an installer-created file
- **File:** `installer/terminal_shell.py:482-490` (`alacritty_config_path`)
- **Raised by:** lane B2, my-referee-one. Also already recorded as HR-01 in `24-REVIEW-deep.md` and in `24-REVIEW-ponytail.md`; still present at HEAD (three candidates only, docstring still says "three").
- **Verified:** yes. The candidates are `$XDG_CONFIG_HOME/alacritty/alacritty.toml`, `$XDG_CONFIG_HOME/alacritty.toml`, `~/.config/alacritty/alacritty.toml`; `~/.alacritty.toml` (a documented Alacritty location) is never checked, and no test mentions it.
- **Scenario:** the user keeps `[font]`, shell and bindings in `~/.alacritty.toml`. The terminal sync and key tuning create `~/.config/alacritty/alacritty.toml` holding only the installer regions. Alacritty prefers that file and stops loading the user's config. Uninstall strips the regions but leaves the higher-priority (now empty) file, so the user's settings stay shadowed.
- **Fix direction:** add `home / ".alacritty.toml"` as the last candidate (edit in place, create nothing), fix the docstring, add a test for that location and for create-then-strip leaving an empty file. Decide how a system-only `/etc/alacritty/alacritty.toml` is handled (refuse or note).

### H-2. The nested-podman probe can never print `TRACER_NESTED_PODMAN_OK`
- **File:** `scripts/container-e2e-verify.sh:1545` (`nested_probe_podman`)
- **Raised by:** lane C, my-referee-three.
- **Verified:** yes. I fetched the upstream Containerfile of `quay.io/podman/hello`: the final stage is `FROM scratch` with a single `/usr/local/bin/podman_hello_world` and a `CMD`. `podman run --rm quay.io/podman/hello:latest true` therefore fails with "executable file `true` not found" even on a working nested podman. The failure is reported as `TRACER_NESTED_INFEASIBLE step=podman-run detail=<first non-empty line>`, which is the pull progress line ("Trying to pull ..."); this is exactly what 24-08-SUMMARY.md records (line 109). The recorded "podman-run infeasible" verdict is not evidence that nested podman is broken.
- **Fix direction:** run the image's default command (`podman run --rm IMAGE`), or use an image that has `true`; report the line containing `Error:` or the last non-empty line instead of the first. Re-evaluate the 24-08 "nested infeasible" conclusion and UAT test 6 with the fixed probe.

### Downgraded HIGH claims
- **A1 `installer/cargo_distrobox.py:171-196` `_swap`, interrupted swap leaves the binary missing (raised HIGH, now LOW, see L-1).** Real, but the window is two consecutive `os.replace` calls, only a `KeyboardInterrupt`/signal in that window triggers it, and the original stays on disk as `<host>.tools-installer.old`. Recoverable, not data loss.
- **C `container-e2e-verify.sh:1545/1621` stale hello image causes false `TRACER_NESTED_IMAGE_LEFT` (raised HIGH, now MEDIUM, see M-1).** Confirmed from the code, but it is a consequence of H-2 and only produces a false failure after a build that succeeded; same fix.

## MEDIUM

Items marked (v) were spot-checked by me against the code; the rest are lane claims, several with a reproduction in the lane log.

- **M-1.** `scripts/container-e2e-verify.sh:1545` + `:1621`. `podman rmi` is chained with `&&` after the failing `run`, so the pulled hello image stays; a later successful Alacritty build then fails `nested_artifacts_ok` with `TRACER_NESTED_IMAGE_LEFT`. Fix: always `podman rmi -f IMAGE || true`, or snapshot images before the install and flag only new ones. (lane C, referee-three; v)
- **M-2.** `scripts/container-e2e-verify.sh:1569-1576` `nested_classify_alacritty`: any failure text containing "distrobox create" is classified infeasible (rc 2, treated as not failed), so a real product bug in the create argv passes silently. Fix: classify infeasible only on known environment errors (e.g. the UTS-namespace hostname error), everything else `BUILD_FAILED`. (lane C, referee-three; v for the classification code)
- **M-3.** `scripts/container-e2e-verify.sh:1172` and `:1291`: the herdr plugin check is a substring match on `2>&1` output, so an error echoing the plugin id passes "listed" and an echoing empty result gives a false `TRACER_HERDR_PLUGIN_LEFT`. Fix: parse `result.plugins[].plugin_id` like `postinstall._plugin_listed`; unparseable is unreadable. (lane C, referee-three)
- **M-4.** `scripts/container-e2e-verify.sh:1091` `settings_probe_revert`: the empty-container exemption is not tied to herdr, so a created settings file left with only empty tables (e.g. our own revert leaving `{"permissions": {}}`) passes silently for any agent. Fix: restrict to herdr's recorded hosts and print an `R` line whenever the exemption applies. (lane C, referee-three)
- **M-5.** `scripts/container-e2e-verify.sh:1163-1229` `herdr_installed_verdict` checks only recorded hosts, never present hosts (SPEC R1 "present hosts"); a host whose `integration install` failed is a warning and simply missing. The Debian run recorded `claude,codex,copilot,cursor,opencode` while `pi` is also a herdr target. Fix: emit present harnesses from the container and require recorded to cover present. (lane C, referee-three)
- **M-6.** `scripts/container-e2e-verify.sh:686`: `TRACER_DISTRO_MISCONFIGURED` fires whenever installed is 0, so the documented fix-and-rerun-pass1 loop (everything already `skipped`) fails as misconfigured. SPEC means "nothing available". Fix: test for no installed/skipped/manual rows, or only on a fresh `bootstrap --replace`. (lane C, referee-three)
- **M-7.** `installer/agent_settings.py:983-990` (`apply_value`) and `installer/terminal_shell.py:739-755` (`_sync_herdr`): when the resolved zsh path changes, the installer-written herdr `default_shell` is classified `set_by_you`, its ledger entry is dropped, and uninstall/zsh removal can no longer revert it; the old path may be dead. Reproduced in a scratch HOME by lane B1; raised independently by B1 and B2. Fix: compare the existing value with the recorded one before calling it user-owned; refresh or revert-and-reapply while the file still holds the recorded value. (B1 + B2, referee-one; v by reading `apply_value`)
- **M-8.** `installer/agent_settings.py:405-419`: a user comment added under an installer-created `[terminal]` (or sidebar) TOML table makes the recorded block mismatch, `_toml_remove` then fails with "terminal has no line to remove" and the installer-written key stays. Reproduced by B1. Fix: fall back to removing the owned leaf key, keeping header and comments. (B1, referee-one)
- **M-9.** `installer/version_status.py:786-791` (`_hook_fact`): when both targets and `sidebar-markers` are pending it emits two `hook_register` steps; the first registers both (`register_hooks` wants `present | standalone`), the second fails with "no unregistered host is present any more" (`session.py:358`), reporting a successful reconfigure as failed and stopping later steps. Fix: one combined step with both reasons. (B3, referee-one; v by reading `register_hooks`)
- **M-10.** `installer/app.py:1198-1199` (called at `:1293`): `_drop_deleted_ledgers` lets a `write_ledger` `OSError` escape after the tool/receipt removal already ran, aborting the remaining ban/PATH/tweak cleanup and losing the `SweepResult`. Fix: catch per agent, return as warnings, continue. (B3, referee-one)
- **M-11.** `installer/terminal_shell.py:515-523, 602-605`: `[general] import = [...]` in the Alacritty config is not followed, so the conflict guards miss a user shell or bindings in imported files; the installer values then override them. Fix: resolve imports or refuse the tuning with a reason. (B2, referee-one)
- **M-12.** `installer/cargo_distrobox.py:255-258`: the `new.unlink()` loop in `finally` runs before `_cleanup` without protection; an `OSError` there skips container and image removal. Fix: nested `finally`. (A1, referee-one)
- **M-13.** `installer/cargo_distrobox.py:81-90`: Distrobox follows the user's runtime (`DBX_CONTAINER_MANAGER=docker`), while image accounting and `rmi` hardcode podman, leaving the pulled image behind. Fix: pin `DBX_CONTAINER_MANAGER=podman` for every Distrobox step. (A1, referee-one; v that `podman rmi` is hardcoded in `_cleanup`)
- **M-14.** `installer/uninstall.py:58-62`: after a partial uninstall (binary gone, desktop entry removal failed) the receipt proof fails and the binary-only slice excludes the surviving desktop/icon/terminfo files from `RemovalPlan.yourself`, so the CLI can say nothing is left. Fix: keep binary-only evidence for ownership but list surviving receipt-recorded cargo artifacts. (A2, referee-one)

## LOW

- **L-1.** `installer/cargo_distrobox.py:171-196` `_swap` rolls back only on `OSError`; an interrupt between the two `os.replace` calls leaves the live binary at `.tools-installer.old` while the `finally` deletes the staged replacement. Fix: roll back on `BaseException`, re-raise. (A1, referee-one; raised HIGH, downgraded)
- **L-2.** `installer/ownership.py:235-238`: `_applicable_methods` drops `cargo_distrobox` when Distrobox/Podman are off PATH, so an installed Alacritty gets `method=None` and its update fails with "requires a resolved method" instead of a prerequisite message. Fix: keep the receipt-backed method for ownership, gate only the rebuild. (A2, referee-one)
- **L-3.** `installer/terminal_shell.py:501-503`: `json.dumps` default escapes non-BMP characters as surrogate pairs, invalid TOML, so a zsh path like `/home/😀/.local/bin/zsh` refuses the shell sync. Fix: `ensure_ascii=False`, keep the re-parse guard. (B2, referee-one)
- **L-4.** `scripts/container-e2e-verify.sh:682` + `:573`: a chunked `pass1 --categories ...` writes a subset manifest but pass2 reruns `--all`, so `TRACER_RERUN_UNEXPECTED` is guaranteed. Fix: record the categories and rerun with them, or refuse pass2 after a chunked pass1. (lane C, referee-three)
- **L-5.** `scripts/container-e2e-verify.sh:1525-1540` `nested_uninstall_ok` may flag the `.terminfo/a` directory although only files are recorded (SPEC R3 edge); unverified, depends on parent pruning. Fix: check the five file paths only. (lane C, referee-three)
- **L-6.** `scripts/container-e2e-verify.sh:1486-1487` `cmd_all`: a failing pass2 exits via `set -e` before `cat` of `pass2-transcript.log`, so `make e2e` prints no reason. Fix: `cmd_pass2 || { cat "$log"; exit 1; }`. (lane C, referee-three)

## Host safety

No lane found a sudo/pkexec/doas path or a write to the real HOME. Lane C explicitly checked that container-sourced values reaching commands are validated against a safe character set. Reviewer scratch files from B1/B2 went to `/tmp/opencode` only.
