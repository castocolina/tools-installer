# Requirements (batch 5: update automation, proposed phases 33-35)

Sources are the three owner feature todos and the shared research doc, all classified DOC (manifest-declared,
confidence high, locked: false). Per extraction discipline, the IDs below are PROPOSED by the synthesizer from
the todos' "Solution" sections; none is locked. Each todo's "Owner decisions" are recorded as open questions
in `context.md`, not as requirements. Owner decision 2026-11-19 (from the orchestrator): phases 33-35 appended
to milestone v0.51.0 in the order registry bot (33), daily check (34), auto-update (35).

## Phase 33: Registry update bot (BOT)

## BOT-01
- source: .planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md; .planning/research/2026-11-17-update-automation.md (Feature 3)
- description: A scheduled/dispatchable GitHub Actions workflow runs `make verify-registry ARGS="--write"` and pushes a `bot/registry-<date>` branch only when `installer/registry.toml` changed.
- acceptance: a run with drift pushes the branch; a run with no drift (`git diff --quiet installer/registry.toml`) pushes nothing.
- scope: installer/registry.toml, verify-registry, .github/workflows/ (new file separate from the read-only drift workflow)

## BOT-02
- source: same as BOT-01
- description: The bot branch gets the required CI checks run on it without a new long-lived secret, or with a secret if the owner chooses (open question OQ-BOT-2).
- acceptance: the checks required by branch protection run on the bot branch head; the dispatched-run-satisfies-required-checks behavior is verified once on a throwaway branch (research marks it unverified).
- scope: .github/workflows/ci.yml (`workflow_dispatch` trigger), `actions: write`

## BOT-03
- source: same as BOT-01
- description: The bot never lands a change on `main`; the owner lands it by the documented branch push, green CI, fast-forward flow (default; auto-land is open question OQ-BOT-3).
- acceptance: the bot workflow's token cannot and does not push to `main`, and the weekly read-only drift report keeps `contents: read` only.
- scope: protected main, enforce_admins, workflow permissions

## BOT-04
- source: same as BOT-01
- description: A verify-registry flag lets a `--write` run skip changes that only touch the `verified` date, so bot branches never carry date-only diffs (batching policy is open question OQ-BOT-4).
- acceptance: a `--write` run whose only change is a `verified` date leaves `registry.toml` unchanged when the flag is set.
- scope: installer/verify_registry.py

## Phase 34: Daily update check with desktop notification (NOTIFY)

## NOTIFY-01
- source: .planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md; research Feature 1
- description: The Schedules engine has a daily `check-updates` row that runs `VersionRefreshService.refresh` headless through `--run-schedule` and logs one `ok: N updates available` line.
- acceptance: `--run-schedule check-updates` in a scratch HOME writes exactly one result line to the shared schedule log and mutates no tool.
- scope: installer/schedules.py, installer/compose.py, VersionRefreshService

## NOTIFY-02
- source: same as NOTIFY-01
- description: The scheduled pass bypasses the 7-day version cache TTL (forced refresh or shorter TTL) so a daily run sees new releases.
- acceptance: with a cache younger than 7 days, a `check-updates` run still fetches fresh versions.
- scope: installer/version_cache.py:45

## NOTIFY-03
- source: same as NOTIFY-01
- description: The stdlib runner sends a desktop notification only when the outdated set changed since the last run (default; every-run is open question OQ-NOTIFY-2).
- acceptance: two consecutive runs with an identical outdated set produce one notification; a changed set produces a second.
- scope: schedule runner, last-outdated state

## NOTIFY-04
- source: same as NOTIFY-01
- description: On Linux the notification uses `notify-send`, and the runner's clean child env passes the user session bus address through.
- acceptance: with a fake `notify-send` on PATH and `DBUS_SESSION_BUS_ADDRESS` set, the runner invokes it; with it missing, the run logs `notify skipped` and still exits ok.
- scope: Linux notifier, runner child env

## NOTIFY-05
- source: same as NOTIFY-01; research Feature 1 section C
- description: On macOS the notification uses `osascript display notification`, falling back to a logged `notify skipped` on failure, with the one-time Script Editor permission mentioned in the row detail.
- acceptance: a failing osascript logs `notify skipped` without failing the run; the row detail text mentions the permission; one real macOS check is recorded before the phase is called done (macOS has never run locally; behavior from a launchd agent is unverified).
- scope: macOS notifier, Schedules row detail

## NOTIFY-06
- source: same as NOTIFY-01
- description: The check includes a tools-installer self-check line that compares `git ls-remote origin main` with the checkout HEAD, makes no API call and never pulls (inclusion is open question OQ-NOTIFY-4).
- acceptance: a checkout behind origin logs one self-update line; the checkout is unchanged after the run.
- scope: installer self-check

## Phase 35: Opt-in auto-update (AUTOUPD)

## AUTOUPD-01
- source: .planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md; research Feature 2
- description: Schedules has an `update-all` row that is off by default, enabled only by the user, and is not a Policies row.
- acceptance: a fresh install seeds `update-all` off; no Policies row for it exists; once the user turns it on, the installer never flips it back on its own.
- scope: installer/schedules.py (per-schedule `default_on=False`)

## AUTOUPD-02
- source: same as AUTOUPD-01
- description: `update-all` updates package managers first (ranked by `resolve._RANK`), then dependents grouped by owner and ordered by `deps.resolve_dependencies`.
- acceptance: a unit test with brew, uv and two dependents asserts the run order managers-then-dependents.
- scope: installer/resolve.py, installer/deps.py

## AUTOUPD-03
- source: same as AUTOUPD-01
- description: When a manager's update fails, its dependents are skipped and logged as skipped.
- acceptance: a failing fake manager yields skip lines for each of its dependents and no update call for them.
- scope: update-all runner

## AUTOUPD-04
- source: same as AUTOUPD-01
- description: `update-all` reuses `UpdateService`, `update_refusal`, `stdin=DEVNULL` children, `HOMEBREW_NO_SUDO` and the run lock, and runs no sudo, pkexec or doas.
- acceptance: a refused tool (native owner, SDKMAN, Volta, pin, os-package) is skipped with its refusal reason; a held run lock makes the run refuse rather than overlap.
- scope: installer/update.py, installer/run.py:50,117,338

## AUTOUPD-05
- source: same as AUTOUPD-01
- description: Brew casks are excluded from `update-all` on macOS by default (policy is open question OQ-AUTOUPD-4).
- acceptance: on a macOS fixture with an outdated cask, `update-all` does not update it.
- scope: macOS cask handling

## AUTOUPD-06
- source: same as AUTOUPD-01
- description: An `update-all` run writes a multi-line run log (one line per tool) while the shared schedule log keeps one summary line per id.
- acceptance: a run over three tools leaves three per-tool lines in the run log and one summary line in the shared log.
- scope: schedule log

## AUTOUPD-07
- source: same as AUTOUPD-01
- description: A tool covered by a per-tool agent-CLI schedule row is not updated twice in one day (fold-or-skip is open question OQ-AUTOUPD-3).
- acceptance: with both `update-all` and a per-tool row on, the tool's updater runs once per day.
- scope: installer/schedules.py

## AUTOUPD-08
- source: same as AUTOUPD-01
- description: `update-all` is exercised in a disposable container and never on the developer host; whether `uv self update` is safe while the runner runs under `uv run` is verified there (unverified in the todo).
- acceptance: the e2e runs in a container (which has no systemd user manager, so it drives `--run-schedule update-all` directly) and the `uv self update` result is recorded.
- scope: container e2e
