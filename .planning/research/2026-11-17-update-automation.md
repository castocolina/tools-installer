# Update automation: daily check + notification, auto-update policy, registry bot

Date: 2026-11-17. Scope: research only, nothing built, committed or run on the host.
Conventions: `file:line` = repo fact read today; URL = upstream fact fetched today; **[unverified]** = not confirmed here.
Read-only host facts (Bazzite Kinoite): `notify-send` present, from `libnotify-0.8.9-1.fc45` (`rpm -q`); `systemctl --user show-environment` lists `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`; `/run/user/1000/bus` exists. No notification was sent.

## Summary

| # | Feature | Recommended approach | Size |
|---|---------|----------------------|------|
| 1 | Daily check + desktop notification | New `check-updates` schedule row (daily) that reuses the version refresh pass, logs one result line, and notifies from the stdlib runner only when the outdated set changed | Medium |
| 2 | Auto-update policy, managers first | A second opt-in schedule row `update-all` (a Schedules row, not a Policies row) that orders by manager owner, then `requires`, reusing `UpdateService` and its refusals | Large |
| 3 | Dependabot-like registry CI | Custom workflow around `verify-registry --write` that pushes a bot branch, dispatches CI explicitly, and leaves landing to the owner | Small to medium |

Order: 1, then 3 (independent of the others), then 2. Feature 2 reuses the check pass from feature 1 and is the riskiest.

## B. What "a new version of the software" means

Both, but the two halves differ in cost:

- **Installed catalog tools** (the owner's main intent): the refresh pass already computes `Health.OUTDATED` per installed tool (`installer/version_status.py:217-246`, `:420-427`).
- **tools-installer itself**: there is no release ceremony. `main` is the published version and `install.sh` runs `git pull --ff-only` on the checkout (`install.sh:69-71`, `docs/PUBLISHING.md` "there is no release ceremony"). Tags exist only for milestones (`v0.49.0`, `v0.50.0`); `pyproject.toml:3` still says `0.1.0`, so it cannot be compared.
- **Cheap coverage of both**: treat the installer as one more entry in the same notification. The check job runs `git -C <checkout> ls-remote origin refs/heads/main` and compares with the checkout `HEAD`. This is one git call, not the GitHub API, so it does not touch the rate limit. A difference becomes the line "tools-installer: new commits on main". Do not auto-pull: the runner executes from that checkout (`installer/schedules.py:853-860`, the update job passes `--installer <checkout>`), and a dirty tree makes `--ff-only` fail.

## Feature 1: daily check with a desktop notification

### A. What exists

- **Schedules engine**: `JobKind` has `TMP_CLEANUP`, `CACHE_CLEANUP`, `UPDATE` (`installer/schedules.py:37-41`). `SCHEDULES` is a closed tuple (`:70-92`). Intervals are 1..24 h dividing 24 (`:105`), so a daily row is `interval=24`. Linux writes a user timer with `OnCalendar` and `Persistent=true` (`installer/systemd_daemon.py:225-237`), so a missed run fires once at the next login or wake. macOS writes a launchd agent into `gui/<uid>` (`installer/daemon.py:238-239`).
- **Phase 24.2 artifacts**: `24.2-CONTEXT.md` D-10 (one stdlib runner, `runner.py`), D-11 (one shared line log, `<ts> <id> ok|skipped|failed`), D-12 (run lock, 2 h wait), D-13 (last run read from the log), D-14 (`--run-schedule <id>`). The runner is `installer/helper_assets/schedule_runner.py`; its update job shells out to `setup.py --run-schedule <id> --parent-holds-run-lock` (`:320-358`). The unit environment is a clean fixed PATH plus `PASSTHROUGH_KEYS` (`installer/daemon.py:34-47`, `installer/schedules.py:891-901`).
- **Notification was explicitly left out** in 24.2: "A desktop notification for failed runs — not requested" (`24.2-SPEC.md:179`). The owner now asks for one, so this is a scope reversal for a new phase, not a conflict.
- **Version status**: `VersionRefreshService.refresh(tools)` is blocking, headless-safe and already built in `installer/compose.py:411` via `_build_services`; `setup.py:529-544` shows how the headless route reuses it. Latest versions come from `resolve_github_tag` / `resolve_npm_latest` (`installer/versions.py:412-434`), cached in `versions.json` (`installer/version_cache.py:1-4`).
- **Cache TTLs matter**: GitHub results are stale after 7 days, failures back off 6 h, the manager snapshot lives 6 h (`installer/version_cache.py:44-48`). A daily check that wants fresh answers must force or shorten the 7-day TTL for the scheduled pass, otherwise it can miss a release for up to a week.
- **Fetch budget**: `MAX_FETCHES_PER_REFRESH = 20` per pass (`installer/version_status.py:143`); the catalog has 92 `github_release` methods (counted in `registry.toml`). With the budget, one pass covers a rotating subset.
- **Rate limit and token**: `urlopen_fetch` sends `GITHUB_TOKEN` / `GH_TOKEN` only to api.github.com (`installer/versions.py:358-373`). The unit environment does not carry either (`PASSTHROUGH_KEYS` lists proxies and CA bundles only, `installer/daemon.py:34-45`), so a scheduled pass is anonymous.
- **Run lock and TUI contract**: the lock file and the "a scheduled run is in progress" refusal already exist (`24.2-CONTEXT.md` D-12). A check job is read-only, so it should skip the lock or take it shared **[decision for planning]**.

### C. Platform mechanics

**Linux (KDE/Bazzite)**
- `notify-send` is libnotify's CLI and talks to `org.freedesktop.Notifications` (spec 1.3: https://specifications.freedesktop.org/notification/latest/). Options verified from source: `-u` urgency, `-t` expire, `-a` app name, `-i` icon, `-c` category, `-h` hint, `-e` transient, `-A` action, `-w` wait (https://gitlab.gnome.org/GNOME/libnotify/-/raw/master/tools/notify-send.c).
- Presence on Bazzite: verified on this Kinoite host only (see header). Other Bazzite variants and Fedora Atomic spins **[unverified]**. The runner must tolerate its absence (log `ok: N updates; notify skipped: no notify-send`), never install it (no sudo, and libnotify is a base-image package).
- Bus address in a user unit: a systemd user service inherits the user manager's environment, and this host's manager exports `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus` (host fact above). The unit does not need to set it. The runner builds a clean child env (`schedule_runner.py:191`, `_child_env`), so the notify call must pass `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` through, or fall back to `unix:path=$XDG_RUNTIME_DIR/bus` when unset. GLib's own fallback to that path **[unverified]**.
- gdbus fallback: `gdbus call --session --dest org.freedesktop.Notifications --object-path /org/freedesktop/Notifications --method org.freedesktop.Notifications.Notify ...` (`/usr/bin/gdbus` present here). Only worth coding if `notify-send` is missing **[unverified on a host without libnotify]**.
- A timer firing while logged out has no session bus: the notify call fails, so log it and retry next run. `Persistent=true` already catches up on login.
- KDE shows the app name from `-a`; use `-a tools-installer`, `-u normal`, `-e` (transient is wrong here; a persistent entry is better so a missed popup stays in history) **[choose in planning]**.

**macOS (launchd user agent)**
- `osascript -e 'display notification "text" with title "t"'` works from an agent in the `gui/<uid>` domain. Attribution goes to Script Editor, which must be enabled once under System Settings > Notifications (https://macscripter.net/t/trying-to-use-terminal-for-display-notification/76593, https://zenn.dev/todesking/articles/d45044c470339e). Forum reports are mixed for launchd-driven calls **[unverified, needs one real macOS run; macOS was never run locally, `PROJECT.md` Known issues]**.
- `terminal-notifier` is a Homebrew formula (`brew install terminal-notifier`), has its own notification permission and a `-diagnose` mode. Its README lists "no GUI session" and OS-upgrade permission resets as causes of silent failure; `-sender` was removed in 3.0.0 (https://github.com/julienXX/terminal-notifier). Third-party reports call it unreliable from background scripts on Sequoia/Tahoe **[unverified]**.
- Recommendation: osascript first (zero install, zero new catalog entry), log `notify skipped` when it fails, mention the one-time Script Editor grant in the Schedules row detail. Do not add terminal-notifier as a dependency for this.
- Notification text must be escaped for AppleScript quoting; build the string from fixed templates plus tool ids from the catalog, never from upstream text.

**Rate limits** (https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api): anonymous 60 requests per hour per IP, authenticated 5,000 per hour, `GITHUB_TOKEN` in Actions 1,000 per hour per repository. One daily pass of up to 20 fetches fits the anonymous limit, but the TUI shares the same IP budget (`version_status.py:10-15` docstring). Adding a token to the unit means writing a secret into a 0600 unit file (`schedules.py` `_UNIT_MODE` comment: unit files already carry proxy credentials). Cheaper alternative: let the runner call `gh auth token` when `gh` is on the clean PATH **[decision]**.

### Design sketch (smallest complete change)

1. `JobKind.CHECK` and one `Schedule("check-updates", ..., interval=24, start="09:00")` in `SCHEDULES`; no target, so it is available on every host.
2. `setup.py --run-schedule check-updates` (extend `run_schedule`, `installer/schedule_run.py`, which today answers `failed: ... is not an update schedule`) runs `refresh(tools)` and prints `ok: 3 updates available: bun, uv, claude`.
3. The runner parses that line and calls a `_notify(title, body)` helper (stdlib, one `notify-send` or `osascript` call, injected seam for tests). It notifies only when the outdated set differs from the last notified set, kept in `schedules.json` (`ScheduleState`, `schedules.py:226`), so the user is not nagged daily.
4. Default: on, like the other rows (24.2 SPEC R3), because it only reads and notifies.

### Size: medium. Risks: cache TTL, anonymous rate limit, macOS attribution.

### Owner decisions
- Reverse the 24.2 "no desktop notification" cut for this check only, or for failed runs too?
- Notify on every run, or only when the outdated set changes (recommended)?
- Token in the unit, `gh auth token` fallback, or stay anonymous with the 20-fetch budget?
- Include a tools-installer self-check line (recommended, one `ls-remote`)?
- Click action (open a terminal with the TUI)? Not recommended for v1.

## Feature 2: auto-update policy, package managers first

### A. What exists

- **One update path**: `UpdateService.run` re-resolves ownership, refuses unknown owners, gates installer-owned drift, pre-captures pnpm globals, mutates, replays, invalidates (`installer/update.py:580-739`). The `u` route and the 24.2 scheduled updates both use it (`24.2-CONTEXT.md` D-14, `installer/schedule_run.py:44-61`).
- **Refusals already encode "never auto-update"** (`update_refusal`, `installer/update.py:283-384`): unknown owner or low confidence; SDKMAN candidates; pinned `app`/`tarball` methods (`PINNED_DETAIL`); `UNMANAGEABLE_OWNERS` = dnf, apt, pacman, rpm-ostree and os-package (`installer/ownership.py:116-129`); Volta-owned tools (`update.py:332-342`, "never run it here"); bun pins and ranges outside the catalog; pnpm host-setup hint. All return `unsupported` with zero subprocess.
- **Manager update argv in the registry**: brew `brew update` (`registry.toml:185,195,205`), uv `uv self update` (`:86`), pnpm `pnpm self-update` (`:2259`), bun `bun upgrade` (`:2223`), SDKMAN `sdk selfupdate` (`:2004`); Volta has none, so `_update_installer_owned` re-runs its install script (`update.py:505-508`). Brew-owned bun/uv go through `brew upgrade <formula>` (`update.py:188-211`).
- **Package-manager tools**: `category = "pkg-mgr"` is uv, brew, pnpm, volta (`registry.toml:63,164,2229,2291`); bun, SDKMAN and fnm are `runtime`.
- **Ordering data**: `deps.resolve_dependencies` returns a deps-first topological closure with cycle reporting (`installer/deps.py:42-155`). But tool-level `requires` is sparse: 11 lines, e.g. `requires = ["uv"]` (`registry.toml:740,1846`), SDKMAN candidates `requires = ["sdkman"]` (`:2037-2101`), `["bun","puppeteer"]` (`:2803`). Tools installed by brew do not declare `requires = ["brew"]`, so `requires` alone cannot say "managers first". The install priority ladder is `_RANK`: brew/cask 5, bun 6, node 7, script 10, github_release/uv-tool/sdkman/tarball/app 20 (`installer/resolve.py:15-27`, Phase 24.5 PRIO-01).
- **Unattended safety already present**: every child runs with `stdin=subprocess.DEVNULL` (`installer/run.py:117,338`), brew children carry `HOMEBREW_NO_SUDO=1` and `HOMEBREW_NO_AUTOREMOVE=1` (`run.py:47-50`), the headless route is documented as owning no terminal (`run.py:187`), one update is bounded by `_UPDATE_TIMEOUT = 1800` (`schedule_runner.py:51`), and the run lock serializes against the TUI. The runner's own `Popen` sets no `stdin` (`schedule_runner.py:224-231`); systemd and launchd default it to null, but an explicit `stdin=subprocess.DEVNULL` is a one-line hardening **[verify in planning]**.
- **Failure propagation** for installs ("soft-warn and skip dependents on failure", `PROJECT.md` Context, `installer/session.py::run_installs`): reuse it for "manager failed, skip its dependents".

### D. Ordering, policy meaning, safety

**Ordering mapped to data** (proposal, one function, no new resolver):
1. Stage 0, managers: installed tools with `category == "pkg-mgr"` plus bun, SDKMAN, fnm, ordered by `_RANK` of their owning method (brew first, then bun, then pnpm/volta/uv), ties broken by `deps` topological order.
2. Stage 1, dependents: every remaining installed, updatable tool, grouped by `ownership.owner` in the same rank order (brew, bun, pnpm, uv, installer), each group in `resolve_dependencies` order so `requires` still wins.
3. A tool whose owning manager failed in stage 0 is skipped with `skipped: <manager> failed`.
4. pnpm self-update keeps its snapshot/replay contract (`update.py:213-220,610-636`); it must not be reordered after the globals it replays.
5. uv updating itself while the runner executes under `uv run --no-cache --script` (`schedules.py:866-880`): replacing the binary mid-run is likely fine on Linux and macOS but **[unverified]**; put uv last among managers, or test in a container.

**What "policy" means here**: not a Policies row. `PROJECT.md` Out of Scope says agent-tuning knobs are not Policies rows and "a new requirement becomes a Policies knob only if it lies outside any install", and Key Decision "Install-time tuning in the tool's postinstall, never a Policies knob by default" (`PROJECT.md:209`). Auto-update is recurring maintenance, which Phase 24.2 already moved into the Schedules view (`24.2-SPEC.md` Goal). So the policy is one more Schedules row, `update-all`, on/off per user, with the decision stored like the others (`ScheduleRecord.decided`, `schedules.py:216-233`).
- Difference from 24.2 R3 ("on by default when the target is installed"): `update-all` must be **off by default** and only turned on by the owner. This needs a per-`Schedule` `default_on` flag (today every row is seeded on by `ensure_schedule_defaults`, `schedules.py:1715`).
- Overlap: five per-tool rows (`update-claude`, `update-opencode`, `update-pi`, `update-cursor-agent`, `update-copilot`, `schedules.py:86-92`) would double-update. `update-all` should skip any tool that has its own enabled row, or the per-tool rows are folded into it.
- Scope option: manager-only first (stage 0), dependents later. Cheaper and covers the owner's "package managers first" literally.

**Never auto-update** (all except the last two are already refused by `update_refusal`): native dnf/apt/pacman/rpm-ostree and os-package tools; SDKMAN candidates; pinned downloads; Volta tools; unknown or by-elimination-low owners; bun/pnpm pins. Add: brew casks on macOS by default (a `pkg`-based cask upgrade can need root and fails closed under `HOMEBREW_NO_SUDO`, a running app blocks replacement; see todo `2026-11-04-hand-off-casks-whose-uninstall-needs-root.md`, and `update.py:200-206` `--greedy-auto-updates`), self-updating GUI apps, and anything the user is currently running a TUI mutation on (lock held).

**Failure handling and logs**: one `update-all` id in `schedules.log` gets one summary line (`ok: 4 updated, 6 current, 2 skipped, 1 failed: <tool>`); `parse_log` reads one line per id (`schedules.py:521`), so per-tool detail goes to a second capped file, e.g. `update-all.log` beside it **[decision]**. Exit code non-zero on any failure so systemd marks the unit failed. Continue after a non-manager failure; stop a manager's dependents on its failure. Invalidate the version cache once at the end, not per tool (`UpdateService.run` already calls `invalidate`; check cost **[verify]**).

### Size: large. Reasons: ordering function, `default_on`, overlap rule, multi-line log, macOS cask policy, container e2e (no systemd user manager in the container e2e, `24.2-SPEC.md` Background).

### Owner decisions
- Off by default, opt-in per host (recommended)?
- Managers only first, dependents second phase, or both at once?
- Fold the five per-tool update rows into `update-all`, or keep both and skip duplicates?
- Casks on macOS: excluded (recommended), allow-listed, or included?
- Notify after an auto-update run (reuses feature 1's helper)?
- Dry-run mode (`--run-schedule update-all --plan`) that prints the ordered plan without mutating?

## Feature 3: registry update bot

### A. What exists

- **`make verify-registry`** runs `installer/verify_registry.py`: exit 0 ok, 1 drift, 2 inconclusive (`:1-5`). `--write` dates passing tools and bumps drifted pins (`_plan_bumps`, `_registry_edits_for_write`, `:1260-1340`); `--candidate TOOL=VERSION` forces a version and requires `--write` (`:1553-1585`); `--issue` upserts one `registry-drift` issue (`:1419`). The bump verifies the candidate end to end (asset exists, member present, digest) before editing, and writes `version` + `sha256` + `verified` together (`_build_bump_edits`, `:1188-1198`).
- **Weekly workflow** `.github/workflows/verify-registry.yml`: Monday and Thursday cron plus `workflow_dispatch`, permissions `contents: read, issues: write`, runs `make verify-registry ARGS="--issue"`, closes the issue after a clean run, caches the state file. It never writes the repo.
- **Only five methods are pinned**: `sublime` (macOS zip + two Linux tarballs, build `4215`) and `drawio-desktop` (two macOS apps, `32.6.10`), each with `version` + `sha256` (counted from `registry.toml`; `download.pinned_method`, `installer/download.py:178-188`). The other 40 `github_release` methods with a checksum template and the rest resolve "latest" at install time and are verified against the upstream checksum file (`checksum = "{asset}.sha256"`, e.g. `registry.toml:115`). So the bot's real job is small: bump two pins with their digests, and flag renamed or missing assets.
- **Digests to refresh with a pin**: `sha256` on every pinned method of the tool, and `verified`. `--write` already does all three. GitHub release assets also expose a `digest` that `resolve_github_release` reads (`installer/versions.py:376-396`).
- **`verified` noise**: `--write` also re-dates every passing tool (`_registry_edits_for_write`, `:1336-1339`). Run weekly it makes a PR every week with date-only changes. Open a PR only when a pin or a finding changed, or add a flag that skips the date-only edit **[small code change]**.
- **Protected-main flow** (`.claude/git-workflow.md`, "The path to main"; verified live with `gh api .../branches/main/protection`): `enforce_admins: true`, `strict: true`, required checks `validate & test on ubuntu-latest` and `... macos-latest`, no required reviews (`reviews: null`), linear history off. CI triggers only on push to branches other than `main` (`.github/workflows/ci.yml:5-7`); there is no `pull_request` and no `workflow_dispatch` trigger. Docs-only fast pass is `devtools/docs_only.py`; a `registry.toml` change is not docs-only, so it gets the full gates.
- **Repo Actions settings** (live `gh api .../actions/permissions/workflow`): `default_workflow_permissions: read`, `can_approve_pull_request_reviews: false`. The second setting also blocks `GITHUB_TOKEN` from creating PRs ("Allow GitHub Actions to create and approve pull requests", off here). The peter-evans docs do not mention this setting **[the block itself is unverified in this session; the setting value is verified]**.

### E. Options compared

**Dependabot**: cannot read `registry.toml` (no TOML-registry ecosystem). It still helps with what it supports: `github-actions` (verified, https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories) for `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/cache@v4`, and possibly `uv` for `pyproject.toml`/`uv.lock` **[uv ecosystem not confirmed in the part of the page read]**. A tiny `.github/dependabot.yml` for actions is a cheap side win; its branches trigger `ci.yml` as ordinary pushes.

**Custom workflow (recommended)**: schedule or dispatch, `make verify-registry ARGS="--write"` (tokened, so the 60/h limit does not bite), detect `git diff --quiet installer/registry.toml`, push `bot/registry-<date>`, make CI run, then land.
- Reuses the verification already written and tested (asset, member, digest, tag-to-version mapping). Needs no new dependency.
- Branch-only variant avoids the PR-creation setting: push the branch, update the existing `registry-drift` issue with the branch name (the issue upsert exists, `:1419`), owner lands with the documented `git push origin <branch>:main`.
- PR variant: `peter-evans/create-pull-request` or `gh pr create`; needs the Actions PR-creation setting turned on or a PAT/App token. CI does not run on PRs anyway (`ci.yml:5-7`), so a PR is only a notification and review surface.

**Renovate custom regex manager**: `customType: "regex"` with `managerFilePatterns`, `matchStrings` and `datasourceTemplate` can match `version = "32.6.10"` lines per file (https://docs.renovatebot.com/modules/manager/regex/). Problems here:
- It cannot refresh `sha256` alongside `version` without `postUpgradeTasks`, which need the global `allowedCommands` and so a self-hosted Renovate; the Mend-hosted app cannot set it (https://docs.renovatebot.com/configuration-options/ section not fully read; allowlist rule from search results, e.g. https://docs.renovatebot.com/mend-hosted/hosted-apps-config/). A bump with a stale `sha256` fails every install.
- Sublime has no datasource Renovate knows (download.sublimetext.com, build numbers); only drawio-desktop (GitHub releases) maps cleanly.
- It would not run asset/member/digest verification; CI would not catch a renamed asset.
- Two pins do not justify a second tool. Revisit only if pinned entries grow into dozens.

**Bot PR vs the protected flow**
- Events caused by `GITHUB_TOKEN` do not start workflows, except `workflow_dispatch` and `repository_dispatch` (https://docs.github.com/en/actions/concepts/security/github_token). So a branch pushed with the default token gets no `ci.yml` run, and the required checks stay missing. peter-evans documents the same: PRs from `GITHUB_TOKEN` "cannot trigger other workflows"; fixes are a PAT (machine account recommended) or a GitHub App token, which triggers both `push` and `pull_request` (https://github.com/peter-evans/create-pull-request/blob/main/docs/concepts-guidelines.md).
- Two ways out: (a) store a fine-grained PAT or App token as a secret and push with it (secret to rotate); (b) add `workflow_dispatch` to `ci.yml` and have the bot run `gh workflow run ci.yml --ref bot/registry-<date>` with `actions: write` (dispatch is exempt per the rule above). Whether a dispatched run's checks satisfy the required `validate & test on ...` contexts on the branch head **[unverified, test once with a throwaway branch]**. Option (b) needs no secret and fits "zero extra credentials"; it also touches `ci.yml`, which is outside the docs-only fast pass.
- Landing: `strict: true` means the branch must be up to date with `main` and its checks green; `enforce_admins: true` removes the admin bypass, so landing is the fast-forward push from the git-workflow doc. A bot with `contents: write` could push `bot-branch:main` itself, but that is unreviewed auto-merge into a protected branch; default to owner-lands. If `main` moves, the bot's next run rebases or recreates the branch (peter-evans updates the same branch).
- The workflow also needs `contents: write` (and `actions: write` for option b) on top of the current `contents: read, issues: write`; keep it a separate workflow file so the weekly read-only drift report stays read-only.

### Size: small to medium (workflow file, date-noise flag, `ci.yml` dispatch trigger, one live dry run on a throwaway branch).

### Owner decisions
- Branch + issue (no PR, no PR-creation setting) or real PRs?
- PAT/App secret or `workflow_dispatch` on `ci.yml`?
- Auto-land after green CI (unreviewed) or owner lands (recommended)?
- Date-only `verified` changes: ignore, or batch monthly?
- Add the `github-actions` Dependabot file now (recommended, 6 lines)?

## F. Dependencies, order, size

- 1 -> 2: feature 2's "notify after auto-update" reuses the notify helper, and its plan view reuses the outdated list. Feature 1 does not depend on 2.
- 3 is independent (CI only, no installer code except an optional flag in `verify_registry.py`).
- Suggested order: 3 (small, immediate value, de-risks the CI-dispatch question), 1 (medium), 2 (large; split into managers-only then dependents).
- Each should land as its own phase under the branch -> green CI -> fast-forward flow; all three touch tests that need the scratch-HOME sandbox, and feature 1 and 2 need one real macOS check before being called done (macOS has never run locally).

## Unverified list

- `notify-send` on Bazzite variants other than Kinoite; GLib fallback to `$XDG_RUNTIME_DIR/bus`; gdbus path on a host without libnotify.
- osascript from a launchd agent on current macOS (attribution, permission prompt) and terminal-notifier from a background agent.
- uv self-update while running under `uv run --script`.
- Dispatched CI runs satisfying required status contexts; `GITHUB_TOKEN` PR creation being blocked by the repo setting.
- Dependabot `uv` ecosystem support (page truncated).
- Renovate `postUpgradeTasks` restriction for Mend-hosted app (from search results, not the config page body).
- Whether the runner's `Popen` needs an explicit `stdin=DEVNULL`.
