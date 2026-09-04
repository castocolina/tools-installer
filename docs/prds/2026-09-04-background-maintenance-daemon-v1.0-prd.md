# Background Maintenance Daemon Policy - Product Requirements Document (PRD)

## Requirements Description

### Background

`scripts/prune-user-tmpdir.sh` already exists in this repo (added in an
earlier session, authored with a different AI tool per the user). It
reclaims `$TMPDIR` junk left behind by agent runtimes (Claude Code, Codex,
OpenCode, etc.) that Apple's own `com.apple.tmp_cleaner` does not sweep -
that cleaner only handles `/tmp`, not the per-user `$TMPDIR`
(`/var/folders/.../T`). The script already has a dry-run default, a
`--apply`/`--days`/`--verbose` flag surface, and **already degrades
gracefully without `fd`/`rg`** (confirmed by reading it, 2026-09-04): it
checks `command -v fd`/`command -v rg` and falls back to `find`/`grep` when
either is missing - so this is a preference for speed, not a hard
dependency, correcting an earlier framing of this idea as "must install
fd/rg first."

What does not exist today: any way to *run* this script unattended, on a
schedule, from inside the installer. Every existing `Policy`/`TweakBundle`
in this codebase is a one-shot, rc-file-based mechanism (write a marker
block, source it in a login shell) - none of them start a persistent
background service. A macOS `launchd` LaunchAgent (or Linux `systemd --user`
timer, out of scope for a first pass per the user's own framing of this as
macOS-specific) is a genuinely different execution model from every
existing policy in this repo.

### Target Users

- macOS developers running multiple AI-agent CLIs locally who accumulate
  `$TMPDIR` cruft over time and currently have to remember to run the
  cleanup script manually.

### Value Proposition

- Turn an already-written, already-safe (dry-run-by-default) cleanup script
  into a set-and-forget background policy, toggleable the same way every
  other policy in the Policies view already is.

## Feature Overview

### Core Features

1. A new `Policy` (parallel to the existing ban/tweak policies) that
   installs/removes a macOS LaunchAgent running
   `scripts/prune-user-tmpdir.sh --apply` on a schedule. **Resolved per user
   (2026-09-04): schedule is daily; the script's own `--days` threshold stays
   a script-accepted param, defaulting to 3 days** - the LaunchAgent's plist
   fires once a day (`StartCalendarInterval`, not a raw `StartInterval`
   seconds count, so it runs at a fixed time of day rather than drifting),
   and each run still passes `--days 3` unless the policy's own config
   overrides it. This settles the "conservative default" question raised in
   the original Risks section: daily-with-a-3-day-window is not aggressive
   (a file has to sit for 3 days before being eligible at all), so there is
   no need to widen the default further just because the daemon is
   unattended.
2. The policy is macOS-only - `Policy` gains (or reuses, if it already
   exists elsewhere) an OS-gating mechanism so it simply does not appear on
   Linux, the same way `apt-upgrade` is Linux-only today (`applicable_bundles(platform)`
   already exists in `installer/tweaks.py` for exactly this kind of gating).
3. `fd`/`rg` remain optional accelerators, not requirements - the existing
   `requires`/`missing_requires` mechanism (already used by the `docker`
   tweak's `watch` dependency) should surface them as *recommended, not
   blocking* the same way, since the script itself already tolerates their
   absence.

### Feature Boundaries

In scope:

- The LaunchAgent plist template, its install/remove lifecycle, and the
  `Policy` wiring to toggle it live from the Policies view.
- Reusing the script exactly as it exists today - no changes to
  `scripts/prune-user-tmpdir.sh`'s own logic.

Out of scope:

- A Linux/systemd equivalent - explicitly macOS-only per the user, though
  the `Policy` abstraction should not preclude adding one later.
- Any change to the prune script's own cleanup logic, safety checks
  (`lsof`-based open-file skipping), or default thresholds.
- A general "run arbitrary scripts on a schedule" framework - this PRD is
  scoped to this one script, following this repo's existing pattern of
  narrow, purpose-built policies rather than a generic mechanism.

## Detailed Requirements

### LaunchAgent Requirements

- The plist must run `--apply` (not dry-run) on the chosen schedule, since a
  dry-run-only daemon does nothing useful unattended - but the *policy
  toggle itself* should default to installing with a conservative interval
  and `--days` threshold, not an aggressive one, given it runs unattended
  with no human reviewing output.
- Standard out/err from scheduled runs should land somewhere inspectable
  (a log file under the managed state directory) - a silent background
  deletion process with no audit trail would be a real regression from the
  script's current interactive, verbose-by-default use.
- Install/remove must be idempotent, matching every other policy's apply/
  remove contract (`PolicyResult`).
- The plist passes `--apply --days <configured-threshold, default 3>` and
  runs daily via `StartCalendarInterval`.

### Logs and Diagnostics Requirements (resolved per user, 2026-09-04)

The user explicitly asked me to decide how logs from this daemon (and,
more broadly, anything of this shape) should be surfaced, rather than
specifying it themselves. Recommendation:

- **Log location**: a single append-mode log file under this project's
  existing managed-state directory convention (wherever `tweaks.py`'s
  `ManagedExecutable`/policy machinery already keeps its own managed files
  - reuse that root rather than inventing a new one), e.g.
  `<managed-state-dir>/logs/prune-user-tmpdir.log`. One file, not
  one-per-run: a rotating/growing log is simpler to reason about than
  scattered per-invocation files, and this script runs at most once a day.
- **Format**: plain text, one line per run - timestamp, `--days` value
  used, dry-run vs. `--apply`, count of items removed/skipped, and any
  error. This is a direct redirect of the script's own existing
  `--verbose` output (it already produces readable text; do not invent a
  structured format the script does not already emit) plus a leading
  timestamp+outcome line the LaunchAgent wrapper adds around it.
- **Rotation**: cap the file with a simple size/age-based truncation (e.g.
  keep the last N runs or last 90 days) at write time, since this is a
  daily job with modest output per run - no need for a full logrotate
  dependency for something this small.
- **Diagnostics view: yes, but small and reused, not a new top-level
  view.** Rather than adding a whole new "Diagnostics" entry to the nav
  bar (which would violate `.claude/architecture.md`'s "one view registry,
  one nav path" standard for a single script's output), surface this
  daemon's last-run status and a "view log" action **inside the Policies
  view's existing detail panel for this specific policy** - the same
  panel that already shows a policy's `active`/`missing_requires` state
  gains a "last run: <timestamp>, <N> items removed" line plus a
  keybinding to open/tail the log file, scoped to this one policy entry
  rather than a general-purpose cross-cutting diagnostics screen. If a
  second daemon-shaped policy is ever added later and this pattern proves
  worth generalizing, promoting it to a real Diagnostics view is a
  natural follow-up - not assumed necessary now for a single script.

### Dependency Gating Requirements

- `fd`/`rg` are declared as `requires` on this policy the same way `watch`
  is on the `docker` tweak, but the policy's `apply` must not refuse to run
  when they are missing - it degrades to the script's own find/grep
  fallback, and the Policies view's existing `missing_requires` display
  already communicates "recommended but not required" without any new UI
  mechanism.

## Design Decisions

### Technical Approach

- Model this as a new `Policy` factory (`daemon_policy` or similar),
  parallel to `ban_policy`/`tweak_policy` in `installer/policy.py`, rather
  than overloading `TweakBundle` (which is rc-block shaped, not
  daemon-shaped) - the execution model is different enough to warrant its
  own factory even though the `Policy` interface (`id`, `label`,
  `description`, `active`, `apply`, `remove`) stays identical.
- Reuse `applicable_bundles`-style OS gating (`installer/tweaks.py`) for the
  macOS-only constraint, rather than inventing a new gating mechanism.

### Risks

- A background process deleting files unattended is inherently higher-risk
  than every existing policy (which either write config or install
  binaries) - the script's own safety checks (dry-run default, `lsof`
  open-file skip) must survive being wrapped in a daemon exactly as-is; this
  PRD must not weaken them to make scheduling "simpler."
- launchd plist authoring has its own quirks (working directory, PATH
  environment inside a launchd context is *not* the user's login shell PATH
  by default) - the plist must explicitly set PATH or use absolute paths to
  `fd`/`rg`/the script itself, or the "fallback to find/grep" behavior could
  trigger even when `fd`/`rg` are actually installed, just not visible to
  launchd's minimal environment.

## Acceptance Criteria

### Functional Acceptance

- [ ] The Policies view offers a macOS-only toggle that installs/removes a
      LaunchAgent running the existing prune script on a schedule.
- [ ] The policy is invisible/inert on Linux.
- [ ] `fd`/`rg` show as recommended-but-optional, matching the existing
      `missing_requires` UI, and the daemon still runs correctly without
      them.
- [ ] Scheduled runs write an inspectable log, not silent output.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before
      implementation (plist generation/parsing can be tested without an
      actual launchd install - inject the `launchctl`-invoking seam the same
      way every other executor injects its `Runner`).
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.
- [ ] The prune script's own safety checks are verified unchanged, not
      weakened by the daemon wrapper.

### User Acceptance

- [ ] Enabling the policy requires no manual plist editing or terminal
      command outside the TUI.
- [ ] Disabling the policy fully removes the LaunchAgent - no orphaned
      scheduled job survives a toggle-off.

## Open Questions

1. ~~Default schedule and `--days` threshold~~ **resolved above: daily,
   `--days 3` default (script's own param, not hardcoded).**
2. ~~Where does the scheduled-run log live~~ **resolved above: one append
   log file under the existing managed-state directory, surfaced via the
   Policies detail panel rather than a new Diagnostics view.**
3. Is a Linux/systemd-user-timer equivalent worth scoping into a fast-follow
   PRD, or is this genuinely macOS-only for the foreseeable future (the
   script itself is written for macOS's `$TMPDIR`/`com.apple.tmp_cleaner`
   specifics per its own header comment)?
