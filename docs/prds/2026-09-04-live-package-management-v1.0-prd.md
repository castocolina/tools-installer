# Live Package Management and Version Awareness - Product Requirements Document (PRD)

## Requirements Description

### Background

Today the installer knows exactly two things about a tool's state:
`status.is_installed` (a boolean - command on PATH, or an app/cask bundle
present) and, at install time only, the latest GitHub release tag via
`installer/versions.py:resolve_github_tag` (used purely to template `{ver}`
into a download URL, never surfaced to the user as "here's what's
available"). There is no notion of *which version* is currently installed,
no comparison against what is latest, and no way to ask the installer to
delegate to whatever package manager actually owns a tool (`brew upgrade`,
`pnpm update -g`, etc.) instead of reinstalling via this project's own
download/extract path.

**Confirmed by code research (2026-09-04):** the user recalled asking, in an
earlier session, for a background check of each catalog tool's latest
version at catalog load time, instead of relying only on the static local
registry - grepping the current catalog TUI and wizard app confirms this was
**never implemented**. `installer/catalog_tui.py` and `installer/wizard_app.py`
have no async/background worker of any kind; the catalog is entirely static
at browse time.

### Target Users

- Developers who install a tool once and then have no way, from inside this
  installer, to know it is out of date or to update it without leaving the
  TUI.
- Developers who installed a tool via `brew`/`pnpm` directly (outside this
  installer) and want the installer to recognize and manage that existing
  install rather than only knowing "is it on PATH."

### Value Proposition

- Turn the catalog from an install-once tool into something that can also
  answer "what's out of date" and act on it.
- Respect each tool's real owning package manager instead of this
  installer's own download path being the only update mechanism, which
  keeps upgrades consistent with however the tool actually got there.

## Feature Overview

### Core Features

1. **Version-aware status**: know not just *whether* a tool is installed,
   but *which version*, and compare it against the latest available.
2. **Manager-aware management**: know *how* an installed tool got there
   (this installer's own download path, `brew`, `pnpm`, a `uv tool`, a cask,
   etc.) and delegate update/uninstall to that same mechanism rather than
   assuming this installer's own executor is authoritative for every tool.
3. **An update action in the TUI**: a way to check for and apply updates to
   the current selection, instead of only install/uninstall.
4. **Background version refresh**: check latest-available versions
   asynchronously when the catalog loads (the feature the user recalls
   asking for previously and that research confirms does not exist),
   without blocking the TUI on network calls.
5. **Added per user (2026-09-04): manager-drift alerting.** If a tool is
   currently installed via `pnpm`/`npm`/`npx`/`pnpx` and a newer (or safer)
   version is available via `brew`, surface that as an alert - distinct
   from ordinary version-update awareness, because acting on it means
   *changing which manager owns the tool*, not just bumping a version. The
   user also flagged that meaningfully acting on this might mean updating
   the registry itself and filing a tracking issue against this repo, not
   just notifying the person at their terminal - see the MVP breakdown
   below for why that half is scoped out of a first version.

### MVP vs. Deferred, Effort and Risk (added per user, 2026-09-04)

The user asked directly which pieces are fast/low-risk versus slow/
high-risk, to separate what ships first from what waits. Ranked from
cheapest+safest to most expensive+riskiest:

| # | Piece | Effort | Risk | MVP? |
|---|---|---|---|---|
| 1 | Version-aware status for `github_release`-kind tools (run `--version`, compare to the already-working `resolve_github_tag`) | Low - reuses an existing, tested resolver | Low - read-only, no new subprocess trust boundary beyond what `Runner` already covers | **Yes** |
| 2 | Cached, timestamped version state (see persistence below) | Low - a small JSON-ish local file, no new infra | Low | **Yes** |
| 3 | Background refresh via a Textual `Worker` | Medium - real async wiring, but this app already has `run_live` precedent to copy | Low-Medium - must genuinely not block first paint (see Risks) | **Yes** |
| 4 | Brew/pnpm/uv-tool version resolution (shelling out to `brew outdated`/etc.) | Medium - new `Runner`-shaped seams per manager, three of them | Medium - slower, less pure than the GitHub-only path; needs its own tests per manager | **Yes, but after #1** |
| 5 | The manual "update" action, delegating to the right manager | Medium - needs #4 done first, plus correctly identifying which manager owns a given install | Medium - a wrong manager identification could update (or no-op) the wrong thing | **Yes, but last of the MVP set** |
| 6 | Manager-drift alerting (brew-has-something-newer-than-pnpm) - the alert half only | Low, once #4 exists (it is a comparison, not new fetching) | Low | Deferred - depends on #4 shipping first, but cheap once it does |
| 7 | Manager-drift **auto-updating the registry + filing a GitHub issue** | High - needs a GitHub API token/auth story, write access to this repo, and a policy for what counts as "safe enough to auto-file" | High - a bot silently opening issues (or worse, PRs) against this repo is a real trust/scope decision, not a mechanical feature | **Explicitly deferred**, not part of this PRD's MVP - see Open Questions |

The clear MVP boundary: **#1-#5** (version-aware status through the update
action, `github_release`-kind tools first, other managers following) is a
coherent, shippable slice. **#6** is a cheap add-on once #4 exists. **#7**
is a separate, much larger trust decision that should not block or bloat
the rest - it is written up as an explicit Open Question below rather than
assumed into scope.

### Feature Boundaries

In scope:

- Extending `status.py`'s notion of "installed" to include a resolved
  current version where determinable.
- A `latest_version` lookup per tool, reusing/extending
  `installer/versions.py`'s existing GitHub-release resolution and adding
  the equivalent for brew/pnpm/uv-tool-managed entries.
- A background/async refresh mechanism in the Textual app (a `Worker`, in
  Textual's own terms) that does not block interaction.
- An "update" action parallel to the existing install/uninstall actions.

Out of scope:

- Version pinning or lockfile-style reproducibility - this PRD is about
  visibility and manual update action, not automated/scheduled updates.
- Rewriting `installer/deps.py`'s resolver - dependency ordering is
  unaffected by this PRD.
- A general telemetry/analytics layer - version checks are per-session,
  on-demand or on-load, not tracked over time.

## Detailed Requirements

### Version Resolution Requirements

- For a `github_release`-kind tool: reuse `resolve_github_tag` (already
  exists) to get latest; determine current installed version by running the
  tool's own version flag (e.g. `--version`) and parsing it, since this
  installer does not track what it installed beyond presence on PATH today.
- For a `brew`/`cask`-kind tool: `brew outdated` (or `brew info --json`) is
  the authoritative source for both current and latest - do not re-derive
  this via GitHub when brew already knows.
- For a `node`/`uv-tool`-kind tool: `pnpm outdated -g` / `uv tool list
  --outdated`-equivalent (verify the actual command - not assumed here) is
  the authoritative source, mirroring the brew case.
- A tool with no reliable version-check mechanism (e.g. a `script`-kind
  installer with no `--version` flag) must degrade gracefully - show
  "unknown," never a false "up to date."

### Manager-Aware Management Requirements

- Track (or infer at check time) which install method actually produced the
  current install, so "update" can call the right underlying manager instead
  of this installer's own executor assuming it owns every tool.
- Uninstall must respect the same distinction - today's `uninstall.py`
  already models `removable`/`managed`/`absent`/`unavailable` states
  (`UninstallState`); "managed elsewhere" already exists as a concept and
  this PRD's manager-awareness should reuse it rather than inventing a
  parallel one.

### Background Refresh Requirements

- Version checks run as a Textual background worker on catalog load (or on
  an explicit "check for updates" action - see Open Questions), never
  blocking keypresses or navigation.
- Network failures during a background check must degrade to "unknown," not
  crash the check or silently retry forever.
- **Resolved per user (2026-09-04): the cache persists, stamped with a
  last-checked timestamp, with a staleness alert past 1 week.** Each cached
  entry records `(tool_id, latest_version, checked_at)`; on catalog load,
  an entry older than 7 days is shown as stale (e.g. a dim "checked 12d
  ago" marker) rather than silently trusted, and only entries past that
  threshold trigger a background re-check - so a fresh session does not
  refetch everything every time, only what has actually gone stale. This
  needs a small local cache file (JSON, one entry per tool) - no database,
  consistent with this project's existing preference for plain files over
  new storage engines (`~/.myshellrc`, the registry itself, etc.).

## Design Decisions

### Technical Approach

- Extend `installer/versions.py` rather than replacing it - the existing
  `resolve_github_tag`/`Fetch` seam (injectable fetch function, already
  tested with a stub) is the right shape to extend for brew/pnpm/uv-tool
  lookups.
- Use Textual's own `Worker` API for the background refresh, consistent with
  how this app already handles async live-apply flows (`run_live`).

### Risks

- Per-tool version checks that shell out (`brew outdated`, `pnpm outdated
  -g`) are slower and less pure than the existing GitHub-API-only resolver -
  needs its own `Runner`-style seam to stay testable, not raw subprocess
  calls sprinkled through the TUI layer.
- A background worker that fires on every catalog load could turn a fast,
  offline-friendly catalog browse into something that always waits on
  network - must be genuinely non-blocking, not just backgrounded-but-still-
  gating the first paint.
- Manager-aware update needs to correctly identify "this installer's own
  download path" versus "brew/pnpm installed it outside this tool" - get
  this wrong and an update could target the wrong install, or silently
  no-op.

## Acceptance Criteria

### Functional Acceptance

- [ ] The catalog can show, per tool, current version and latest available
      version where determinable.
- [ ] An update action exists and delegates to the correct underlying
      manager (this installer's own path, brew, pnpm, uv tool) per tool.
- [ ] Version checks run in the background without blocking the TUI.
- [ ] A tool with no reliable version-check mechanism shows "unknown," never
      a false status.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before
      implementation, with all live/network calls behind an injectable seam
      (mirroring `versions.py`'s existing `Fetch` pattern).
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.
- [ ] No quality gate is bypassed or silenced.

### User Acceptance

- [ ] A developer can see, at a glance, which installed tools are out of
      date.
- [ ] Applying an update uses the same mechanism that originally installed
      the tool, not a mismatched one.

## Open Questions

1. Background-on-load, or an explicit "check for updates" action the user
   triggers? The user's own recollection favored on-load, but that has real
   network/latency tradeoffs (Risks above) worth weighing against an
   explicit action.
2. ~~Cache persistence~~ **resolved above: persists, 7-day staleness
   threshold.**
3. For tools with no `--version`-style self-report, is "unknown" the
   permanent end state, or should the installer maintain a small per-tool
   override table (e.g. a registry field naming the exact version-check
   command) the way it already does for other per-tool quirks (`checksum`,
   `member` templating)?
4. Should this PRD's manager-aware update also cover moving a tool that is
   currently on a suboptimal method (e.g. still on `pnpm` per the
   package-manager-policy PRD's findings) onto its preferred method as part
   of "updating" it, or is that migration always a separate, explicit
   registry change, never something update-time code decides on its own?
5. **Manager-drift auto-remediation (deferred item #7 above):** should this
   ever auto-update the registry and file a GitHub issue, or should the
   "alert" always stop at notifying the person at the terminal, with any
   registry change staying a manual PR the way every other registry change
   in this project already is? Auto-filing requires a GitHub token/auth
   story this project does not currently have anywhere - a real new
   capability, not a natural extension of anything that exists today, and
   worth a separate, explicit decision (and likely its own PRD) rather than
   folding into this one's MVP.
