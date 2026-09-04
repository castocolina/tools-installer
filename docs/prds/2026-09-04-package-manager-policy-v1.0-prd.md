# Package Manager Policy - Product Requirements Document (PRD)

## Requirements Description

### Background

The installer already bans bare `npm`, `pip`, and `pip3` (`installer/guards.py`):
a POSIX shim in the managed bin dir intercepts the command, prints a message
naming the preferred replacement, and exits 127 (hard failure, not a
redirect). The ban is opt-in, removable, and layered with a shell alias plus
a doctor/guard status check.

Two problems prompted this PRD:

1. **npx has no equivalent ban.** Bare `npx` should be discouraged the same
   way bare `npm` is, pointing at pnpm's equivalent.
2. **`pnpm add -g` has a known, unfixed data-loss bug.** Research done for
   this PRD (2026-09-04) confirms the root cause: pnpm v11 changed global
   install architecture so each `pnpm add -g <pkgs>` invocation is isolated
   by a hash of *that invocation's exact package set*. Adding a new global
   package, or removing one, can silently drop or replace an entire
   previously-installed group - this is filed and open upstream
   ([pnpm#11520](https://github.com/pnpm/pnpm/issues/11520),
   [pnpm#11587](https://github.com/pnpm/pnpm/issues/11587)), not a defect in
   this installer. Two catalog tools currently hit this: `mmdc`
   (`@mermaid-js/mermaid-cli`, `kind="node"`) and `codegraph`
   (`@colbymchenry/codegraph`, currently installed the same way per the
   user).

**Correction from an earlier draft of this PRD, per user review (2026-09-04):**
a tool's surface install method does not prove what it depends on
underneath. A `kind="script"` curl\|bash installer can still shell out to
`npm` internally, and if the redirect/ban policy above intercepts that
internal call, the "fix" just moves the failure to a worse place (it breaks
mid-install instead of never depending on npm at all) — so **every tool this
PRD or the catalog-expansion PRD touches must have its actual install
mechanism read and verified, not inferred from its method `kind`.** This was
done for the two tools below by fetching and reading their real install
scripts/package metadata (not just their marketing pages):

- **`codegraph`** (`colbymchenry/codegraph`): fetched and read its real
  `install.sh` (2026-09-04). It downloads a **prebuilt binary from GitHub
  Releases** (`codegraph-<os>-<arch>.tar.gz`) — the script's own header says
  "No Node.js, no build tools, no npm required." This is not even the
  `kind="script"` method; it is exactly this installer's existing
  `kind="github_release"` download-and-extract path (the same one `rg`,
  `fd`, `gh`, etc. already use), which is a stronger fit than a raw script
  wrapper. The script also detects a stale `npm i -g @colbymchenry/codegraph`
  install and tells the user to remove it - confirming the project's own
  authors consider the binary release the preferred channel over npm, not
  npm.
- **`mmdc`** (`@mermaid-js/mermaid-cli`): genuinely a Node/npm-ecosystem
  tool with no non-npm distribution - there is no binary release to fall
  back to. **Correction, re-verified 2026-09-04 after the user's follow-up:**
  an earlier pass of this PRD cited
  [Homebrew/homebrew-core#100192](https://github.com/Homebrew/homebrew-core/issues/100192)
  as evidence the brew formula lags npm - that issue is stale. Fetched both
  registries live just now: npm's latest is `11.17.0`; Homebrew's formula
  `stable` version is **also `11.17.0`**. They currently match - the
  "stale formula" tradeoff does not hold today. This could drift again in
  the future (brew formulas lag on their own release cadence), so any
  registry entry choosing brew here should note the version was verified
  current at add-time, not assume it stays that way forever.
- **New finding, per the user's follow-up (2026-09-04): mmdc's hidden
  dependency chain.** Fetched mmdc's real `package.json` from the npm
  registry - it declares `puppeteer` as a **peerDependency**
  (`^23 || ^24 || ^25`), meaning it is not auto-installed as a transitive
  dependency the way a normal `dependency` would be; the user (or their
  package manager's peer-resolution behavior) must satisfy it separately.
  `puppeteer` itself downloads a matching `chrome-headless-shell` binary as
  part of its own install (well-documented puppeteer behavior, a
  multi-hundred-MB download, skippable only via
  `PUPPETEER_SKIP_DOWNLOAD`). The Homebrew formula's own dependency list is
  just `node` - it does not declare puppeteer/chromium as a formula
  dependency either, so **whichever install path is chosen, puppeteer and
  its Chrome download are a real, currently-invisible part of getting mmdc
  working**, not an implementation detail that goes away by picking brew
  over pnpm. See the mmdc Decision Requirements below for how this folds
  into the registry.
- **`graphify`** (`graphifyy` on PyPI, per the catalog-expansion PRD):
  fetched its real PyPI dependency metadata (2026-09-04) - `networkx`,
  `numpy`, `rapidfuzz`, and per-language `tree-sitter` Python bindings. Zero
  npm/Node dependency. `uv tool install graphifyy` is confirmed clean, not
  assumed.

**pnpm's global-install bug: no config or flag fix exists.** Explicitly
researched per the user's question - pnpm 11's `pmOnFail`,
`packageManagerStrict(Version)` settings, and the isolated per-invocation
global directory design are the *replacement* for the old shared-global
behavior, not a bug with an opt-out. There is no documented setting that
restores pre-v11 shared-global semantics. This means the only real fixes are
(a) move a tool off `pnpm add -g` entirely when a non-npm distribution
exists (the `codegraph` case), or (b) accept the risk and document a
mitigation (e.g., always reinstall the full global set together in one
invocation) for tools with no alternative (the `mmdc` case).

### Target Users

- Developers and AI agents on this machine who might reach for `npm`/`npx`/
  `pip` out of habit, when this project's toolchain has already standardized
  on `uv` and `pnpm`.
- Developers who hit silently-vanished global CLIs after `pnpm add -g`
  installed something new, with no idea why.

### Value Proposition

- Close the `npx` gap in the existing ban, consistent with `npm`.
- Stop routing catalog tools through a package manager with a known,
  unfixed, invocation-order-dependent data-loss bug when a safer official
  install path already exists.
- Make brew the preferred manager where a real, current alternative exists,
  without silently downgrading a tool's freshness (the `mmdc` case).

## Feature Overview

### Core Features

1. Extend the ban to `npx`, pointing at pnpm's dlx equivalent - and decide
   per-command whether npm/npx are safe to turn into a transparent redirect
   while pip/pip3 stay a hard block (see Design Decisions - the user flagged
   npm/npx as the easier redirect case and pip as uncertain).
2. Move `codegraph` off `pnpm add -g` onto `kind="github_release"` (verified
   above - not `kind="script"` as an earlier draft proposed).
3. Decide `mmdc`'s fate: keep on `pnpm` with a documented mitigation, or
   switch to the stale-but-functional Homebrew formula - present the
   tradeoff, let the catalog-expansion PRD (or a follow-up) make the call.
4. Establish a **mandatory per-tool, per-OS verification step** before any
   new registry entry ships: read the tool's actual install
   script/package metadata (not its marketing page) to confirm what it
   depends on underneath, and confirm the same install path is meaningful
   on every OS this installer targets - a step that is unconditionally
   required on macOS (e.g. Xcode Command Line Tools before many build
   toolchains) may be a no-op on Bazzite, whose base image already ships
   `curl`/`git`/build tooling; conversely Homebrew's own bootstrap script is
   curl\|bash on *every* platform, including Linux (linuxbrew) - there is no
   curl-free brew install on any OS, so system-tier prerequisites need to be
   verified per OS individually, not assumed from the macOS case.
5. Establish "prefer brew over other userspace package managers" as a
   registry-authoring guideline for new tools, documented in
   `.claude/architecture.md` or a similar standards doc, not enforced by
   code (there is no way to mechanically prove a "better" method exists).
6. **Added per user (2026-09-04): SDKMAN exclusivity for the Java toolchain.**
   The brew-preference guideline above (Core Feature 5) has one explicit
   carve-out: `java`, `gradle`, `maven`, `groovy`, and `springbootcli` must
   install through **SDKMAN specifically**, never brew or a native package
   manager, even though brew formulas exist for all five. This is the same
   shape of decision as "prefer brew over pnpm/npm" - a named package
   manager is mandated for a specific tool family - just the opposite
   direction (SDKMAN over brew) for this one ecosystem, because SDKMAN also
   owns JVM *version management* across these five tools together, which a
   one-off brew formula per tool does not coordinate. See the SDKMAN
   Exclusivity Requirements below.

### Feature Boundaries

In scope:

- `installer/guards.py`: the `BANNED` dict, shim generation, alias wiring.
- The install `method` for `codegraph` and (pending the decision above)
  `mmdc` in `registry.toml`.
- Documentation of the brew-preference guideline.

Out of scope:

- Any change to `installer/deps.py` or the dependency resolver.
- Auditing every other catalog tool for a "better" package manager - this
  PRD is scoped to the two tools already known to hit the pnpm bug, plus the
  npm/npx ban itself.
- Fixing the upstream pnpm bug (not this project's to fix).

## Detailed Requirements

### npx Ban Requirements

- `installer/guards.py:BANNED` gains an `"npx"` entry.
- The shim, alias, and doctor/guard status reporting must treat `npx`
  exactly like the existing three banned commands - same removability, same
  opt-in nature, same PATH-order warning logic.
- Existing tests for the ban (shim generation, alias write/remove, guard
  status, doctor guidance) must be extended to cover `npx`, not duplicated
  into a parallel test file.

### Redirect vs. Hard-Block Requirements

- The user's own framing splits this per command, not as one global switch:
  `npm`/`npx` are the plausible redirect candidates (pnpm's CLI surface is
  close enough to npm's for most everyday subcommands - `install`, `add`,
  `run`, `exec`/`dlx`); `pip`/`pip3` stay hard-blocked because `uv` is not a
  drop-in argv-compatible replacement for `pip`'s CLI the way `pnpm` is for
  `npm` (different flag surface, different subcommand names in several
  cases) - a naive argv forward would silently misbehave rather than fail
  loudly.
- Whichever behavior is chosen per command, it must remain idempotent and
  removable, matching the existing ban's shape.
- If npm/npx become a transparent redirect, it must preserve the *user's
  original exit code and stdout/stderr* from the underlying `pnpm`/`pnpm
  dlx` invocation - a redirect that swallows a real pnpm error would be
  worse than today's hard block.
- The redirect (if implemented) must not paper over the exact failure mode
  this PRD's own research surfaced: a tool whose *internal* tooling calls
  bare `npm` (not the user's shell) would still hit the shim/redirect and
  either succeed silently in a way that masks it never needed npm (fine) or
  fail in a new, harder-to-diagnose spot mid-install (the risk to design
  against - see Risks).

### codegraph Install Method Requirements

- `codegraph`'s registry entry uses `kind="github_release"`, not
  `kind="node"` or `kind="script"` - it is a prebuilt binary tarball
  (`codegraph-<os>-<arch>.tar.gz`) on GitHub Releases, the same shape as
  `rg`/`fd`/`gh`/etc. already in this catalog. Verified by fetching and
  reading the real `install.sh` (2026-09-04), not inferred.
- The registry entry should template `{ver}`/`{arch.*}` the same way every
  other `github_release` entry does; `strip_components=1` matches the
  archive's `codegraph-<target>/` top-level layout.

### mmdc Decision Requirements

- With the freshness tradeoff no longer applicable (both channels currently
  ship `11.17.0`), brew is now the cleaner default recommendation for
  `mmdc` itself - but this PRD still records both options in Open Questions
  rather than silently deciding, since brew-vs-npm freshness can drift again
  later and the user should make the final call knowingly.
- **`puppeteer` and `chrome-headless-shell` become their own catalog
  entries**, per the user's explicit request - not bundled invisibly inside
  mmdc's install, regardless of which path (brew or pnpm) mmdc itself uses:
  - `puppeteer`: `kind="node"` (it is itself an npm package with no
    non-npm distribution) or, if mmdc moves to brew, consider whether brew
    can satisfy it directly - needs verification of whether the Homebrew
    formula's install step already pulls in a working puppeteer/chromium
    or leaves it to the user, since the formula's own dependency list only
    names `node`.
  - `chrome-headless-shell`: this is a puppeteer-managed binary download,
    not a package with its own install method in the traditional sense -
    the registry entry likely models it as a `requires` edge on `puppeteer`
    documenting the relationship, rather than a separately installable
    artifact, since puppeteer manages the download itself. Needs a decision
    (see Open Questions) on whether it needs a distinct `Tool` entry at all
    or is purely documentation on `puppeteer`'s own entry.
  - `mmdc.requires` gains `["puppeteer"]` (in addition to its existing
    `["pnpm"]`, or in place of it if mmdc moves to brew) so the existing
    `resolve_dependencies` resolver (already wired, per
    `2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`) drags
    puppeteer in automatically instead of it being a silent, invisible
    peer-dependency gap.

### pnpm Global-Set Reinstall Requirement (added per user, 2026-09-04)

For any tool that stays on `pnpm add -g` despite the known bug (the `mmdc`
case, and any future `kind="node"` entry with no alternative): the installer
should be able to **snapshot the set of pnpm-managed global packages it
installed, and reinstall that whole set in one invocation** after pnpm
itself is updated - since the bug is keyed on "packages installed together
in one invocation" (per the verified root cause above), reinstalling
everything together in a single `pnpm add -g <all-of-them>` call after a
pnpm update is the direct, verified-correct mitigation, not a workaround
that happens to help.

- The installer already knows which tools it installed via `kind="node"`
  (the registry is the source of truth) - no new tracking state is needed
  beyond querying "which currently-selected/installed tools use
  `kind="node"`."
- This should trigger when `pnpm` itself is the tool being updated (see the
  companion `2026-09-04-live-package-management-v1.0-prd.md`'s update
  mechanism - this is a natural extension of "updating a tool" applied
  specifically to `pnpm`, not a separate standalone feature).
- Scope: this is a mitigation for tools that must stay on `pnpm`, not a
  reason to keep more tools on `pnpm` than necessary - `codegraph` still
  moves to `kind="github_release"` regardless.

### SDKMAN Exclusivity Requirements (added per user, 2026-09-04)

**Background - how this surfaced:** a code-review of the already-merged
dependencies-and-shell-tweaks work (commit `431a0a9`) plus the
doctor/catalog-refresh work (commit `0db5865`) found that `java`/`gradle`/
`maven`/`groovy`/`springbootcli` all declared `requires = ["sdkman"]`, but
none of their `[[tool.method]]` entries actually installed via SDKMAN -
every one resolved to `dnf`/`apt`/`pacman`/`brew` instead, bypassing SDKMAN
entirely. Separately, SDKMAN's own registry entry (`cmd = "sdkman-init.sh"`)
could never be detected as installed by `installer/status.py::is_installed`,
because `sdkman-init.sh` is a **sourced, non-executable script** (mode
`644`) - `shutil.which()` requires the executable bit, so it always returned
`None` for it. The combination meant every JVM-tool install silently
re-ran SDKMAN's own `curl\|bash` bootstrap on every run, and the `requires`
edge was pure documentation with no effect on what actually got installed.

**Decision (per user, 2026-09-04): java-toolchain tools install exclusively
through SDKMAN, no native/brew fallback at all** - not "SDKMAN preferred,
brew as fallback," but SDKMAN as the *only* method for these five tools.

**Status: already implemented and shipped ahead of this PRD being updated**
(commit `0e05f50`, pushed to `main` same day) - done directly by the
assistant during the review pass rather than routed through GSD's own
research/planning/execution flow, which is a process deviation from how
this and future PRDs are meant to be worked. Recorded here so GSD's
ingestion of this PRD can treat `0e05f50` as **prior art to verify and
harden**, not a spec to re-derive from zero - GSD's execution flow should
still apply its own rigor (broader test coverage, e2e verification, review)
to this area rather than accepting the shipped state as sufficient.

What `0e05f50` actually did, for GSD's verification pass to check against:

- Added a new `"sdkman"` method `kind` (`installer/model.py`,
  `installer/executors.py`, `installer/resolve.py`): sources
  `~/.sdkman/bin/sdkman-init.sh` and runs `sdk install <candidate>
  [version]` in one `bash -c` invocation, since `sdk` is a shell function
  (not a PATH binary) that only exists after sourcing the init script.
  Applies on every platform (like `script`/`node`/`github_release`), ranked
  in the userspace tier (same rank as `node`/`github_release`), ahead of
  native/brew.
- `java`/`gradle`/`maven`/`groovy`/`springbootcli` each now declare a
  **single** `kind="sdkman"` method (candidate name + `bin_dir` under
  `~/.sdkman/candidates/<candidate>/current/bin`, picked up automatically
  by the existing `collect_bin_dirs` bin_dir convention - no new PATH
  wiring needed). All prior `dnf`/`apt`/`pacman`/`brew` methods were
  removed for these five tools, not kept as fallback.
- `springbootcli`'s SDKMAN candidate is `springboot` (confirmed, not
  `spring-boot`/`spring`) - `cmd` stays `spring` (the binary name SDKMAN
  installs).
- `installer/status.py::is_installed` gained a generic `detect_path`
  fallback: any method with a `detect_path` param is checked via
  `Path(...).expanduser().exists()` after the `which()` check fails, before
  the existing app/cask bundle check. SDKMAN's own method now declares
  `detect_path = "~/.sdkman/bin/sdkman-init.sh"`, fixing the
  never-detected-as-installed bug. This is a new, generic detection
  strategy (no prior precedent in this codebase beyond the app/cask
  bundle-directory check), worth GSD's own scrutiny for whether it
  generalizes cleanly to other sourced-not-executed tools this catalog
  might add later.
- Non-interactive install correctness relies on SDKMAN's own `?ci=true`
  bootstrap flag (already used in the registry's `sdkman` entry), which
  persists `sdkman_auto_answer=true` in `~/.sdkman/etc/config` - **not
  independently re-verified end-to-end against a real, unconfigured
  machine** as part of the shipped fix; this is exactly the kind of gap
  GSD's own e2e/UAT phase should close rather than trusting the assistant's
  research-only claim.
- `java` specifically has an open sub-question the shipped fix did **not**
  resolve: SDKMAN's `sdk install java` without a version argument may
  prompt interactively for a vendor-qualified version choice unless a
  default is already configured - the shipped code supports an optional
  `version` param on the method but the registry entry does not set one.
  Whether `java`'s registry entry needs an explicit pinned `version` (and
  how that gets kept current) is unresolved - see Open Questions.

## Design Decisions

### Technical Approach

- Reuse the existing ban mechanism's shape (`guards.py` shim +
  `shellrc.py` alias block) for `npx` - no new architecture needed for the
  ban extension itself.
- For `codegraph`, reuse the existing `kind="github_release"` download
  executor unchanged - this is a registry data change, not a code change.
- Add the per-tool, per-OS verification step (Core Feature 4 above) as a
  documented, non-negotiable part of the registry-authoring checklist -
  every prior "Registry Batch N" plan already did live verification of
  assets before adding them; this extends that discipline to also cover
  "what does the install actually depend on," not just "does the URL
  resolve."

### Risks

- A transparent redirect changes the ban from "impossible to accidentally
  use npm" to "npm silently becomes pnpm" - an agent or script that greps
  for `npm ci` behavior, or relies on an npm-specific flag pnpm does not
  support, would fail in a new and more confusing way than today's clean
  127 exit.
- Homebrew formula freshness can drift independently of npm's release cadence
  - verified equal today (`11.17.0`/`11.17.0`), but a future brew-lag
  regression (the failure mode the withdrawn citation above described) is
  still a real risk class for this formula specifically, not a one-time
  check that stays valid forever.
- pnpm's global-install bug is unresolved upstream; any catalog tool kept on
  `kind="node"` remains exposed to it. This PRD only removes two known
  instances, not the underlying exposure for future node-kind additions.
- `puppeteer`'s Chrome download is large (multi-hundred-MB) and network-
  dependent regardless of which path installs it - registry-authoring
  should document this clearly so it does not look like a hang or a failed
  install to the user.

## Acceptance Criteria

### Functional Acceptance

- [ ] `npx` is banned/shimmed identically to `npm`/`pip`/`pip3`.
- [ ] `codegraph` installs via `kind="github_release"`, not `pnpm add -g`.
- [ ] The `mmdc` decision (keep on pnpm with documented risk, or switch to
      brew) is made explicitly and recorded, not left ambiguous in the
      registry.
- [ ] Doctor/guard status reporting covers `npx` the same way it covers the
      other three banned commands.
- [ ] `java`/`gradle`/`maven`/`groovy`/`springbootcli` install exclusively
      through SDKMAN with no native/brew fallback (shipped in `0e05f50`;
      GSD's execution flow re-verifies rather than trusting this as done).
- [ ] SDKMAN's own install is correctly detected without re-running its
      bootstrap on every subsequent JVM-tool install.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before
      implementation.
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.
- [ ] No quality gate is bypassed or silenced.

### User Acceptance

- [ ] Running `npx <pkg>` after the ban is active gives the same clear,
      actionable guidance `npm` already does.
- [ ] `codegraph` installs and updates reliably without the pnpm
      global-install bug.

## Open Questions

1. ~~Does a pnpm config/flag fix the global-install bug?~~ **Resolved
   (2026-09-04): no.** `pmOnFail`/`packageManagerStrict(Version)` are the
   *replacement* config surface for pnpm 11's new isolated-global-install
   design, not an opt-out of it. There is no documented setting that
   restores pre-v11 shared-global behavior.
2. **npm/npx redirect: exactly which subcommands are safe to forward?**
   **Partially resolved (2026-09-04):** `npx` itself needs no allowlist at
   all - it is a single-purpose command ("run this package without a
   global install"), not a multi-subcommand CLI like `npm`, so `npx <pkg>
   [args]` -> `pnpm dlx <pkg> [args]` (`pnpx`/`pnx` are pnpm's own shorter
   aliases for the same thing) is a clean, unconditional 1:1 redirect.
   **`npm` still needs the allowlist pass** - it genuinely has subcommands
   with no clean `pnpm` equivalent (`npm ci`, `npm publish`), so the
   `install`/`add`/`run`/`exec`-style common subset question above still
   applies there, just not to `npx`.
3. **mmdc: brew or pnpm?** The freshness gap that motivated hesitation is
   currently closed (both `11.17.0` as of 2026-09-04) - leaning brew now,
   but still the user's call to confirm, and either way `puppeteer`'s
   install path (and whether brew's formula actually provisions a working
   one) needs to be nailed down first - see the mmdc Decision Requirements.
3a. **Does `chrome-headless-shell` need its own `Tool` catalog entry, or is
   it purely a note on `puppeteer`'s entry?** It has no independent install
   method of its own - puppeteer downloads it as part of puppeteer's own
   install. A separate `Tool` entry with no real `Method` would be unusual
   for this catalog's existing shape.
4. Should the brew-preference guideline for *future* registry additions be
   enforced by a lint/test (e.g., flag a new `kind="node"` entry and require
   an explicit justification comment), or stay a documented convention with
   no mechanical check?
5. Who performs the per-tool, per-OS "what does this actually depend on
   underneath" verification, and how is it recorded so it does not have to
   be redone? A comment in the registry entry citing what was checked (the
   way this PRD cites the `install.sh` fetch above) is the minimum bar;
   should it be stronger (e.g. a checked-in copy of the install script's
   relevant excerpt)?
6a. **Does `java`'s SDKMAN method need a pinned `version`?** `sdk install
   java` with no version may prompt interactively for a vendor-qualified
   choice unless a default is pre-configured on the machine - unverified
   end-to-end. If a pin is needed, how does it stay current (a registry
   comment noting when it was last checked, similar to the version-pin
   discipline this PRD already asks for on the mmdc/brew freshness
   question)? This is exactly the kind of gap GSD's research phase should
   close with a real non-interactive test run, not further assistant
   research.
6b. **Process note for GSD's own planning of this PRD:** the SDKMAN work
   above was implemented directly by the assistant mid-review instead of
   through GSD's research -> plan -> execute -> verify flow, at the user's
   explicit correction (2026-09-04: "no vamos a implementar nada" was the
   standing instruction for this whole PRD batch). Treat `0e05f50` as an
   input to GSD's own process, not a substitute for it.
6. **Should managed shell content split across multiple files?** Raised by
   the user (2026-09-04): today every policy (the ban's aliases, every
   `TweakBundle`) writes its marker-delimited block into the *same*
   `~/.myshellrc`, which is getting crowded as more tweaks/aliases land.
   Splitting into, e.g., one file per policy category (`~/.myshellrc-ban`,
   `~/.myshellrc-tweaks`) sourced from the main file would keep each file
   scannable, at the cost of more files to reason about and a migration for
   existing installs. `installer/shellrc.py`'s `apply_block`/`strip_block`
   already operate on an arbitrary path, so this is a policy-wiring change
   in `setup.py`/`policy.py`, not a new primitive - low mechanical risk, but
   needs a decision on the file-splitting scheme itself before
   implementation.
