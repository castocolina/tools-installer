# Architecture standard

The bias is **less total code**: prefer deleting to organizing, one data
structure over parallel copies, and a function over a class. Measure the end
state, not the churn.

## The five rules

1. **One view registry.** Every per-view fact — order, number key, header
   label, palette description, mode badge, footer actions — lives in the single
   `VIEWS` table in `installer/ui_common.py`. Adding a view is a one-row
   change; nothing else may enumerate the views.
2. **One navigation path.** Every view change goes through
   `UnifiedApp.show_view`. View screens are installed once on mount (an
   uninstalled screen is *destroyed* on pop — the cause of the 2026-07 nav-bug
   family). Modals return results only via `push_screen(modal, callback)`.
3. **One apply workflow.** Any live core mutation triggered from a screen goes
   through `ui_common.run_live`; screens supply the closure and the messages,
   never their own `try/except OSError`.
4. **`setup.py` is wiring only.** It may parse args, prompt, print, read the
   real environment, and construct. Any decision function belongs in
   `installer/` where pyright, coverage, and tests apply.
5. **No orphan helpers.** A shared helper with zero production callers is
   deleted or adopted at its duplicate sites — never kept "for later". Only its
   own test keeping it covered is the tell.

## Tier is a browsing label

`Tool.tier` (`system` / `user` / `ai`) is a browsing/grouping label only —
which of the three top-level catalog views a tool is listed under. The three
views are three `CatalogScreen` instances over one shared staged selection, so
a batch assembled across tiers commits once. The tier filter narrows what is
DISPLAYED and never what is resolved: the ids a view returns are resolved
against the whole catalog by `resolve_dependencies`. `deps.missing_requires` is
a read-only preview of that resolution, never a second ordering mechanism.

`Tool.requires`, resolved by `installer/deps.py::resolve_dependencies`, remains
the sole mechanism that determines install order. A `requires` edge that
crosses tiers drags in its dependency exactly like a same-tier one; the
resolver has no tier-aware branching.

ROADMAP SC#2's original illustrative `claude` -> `pnpm` pair was rewritten
during plan-review convergence and is proved with the real `mmdc` -> `pnpm`
user->system edge, because `claude` installs via its own script/cask and
declares no dependency on `pnpm`.

The in-view notice states that unavailable dependencies are reported when the
installer runs; the availability VERDICT stays with `resolve_dependencies` +
the BLOCKED rows `build_plan` makes from `Resolution.blocked`, shown on review
by `render_plan`, because a screen with no `Platform` must not make a
judgement it cannot make correctly.

`Tool.requires` is a hard dependency resolved by
`installer/deps.py::resolve_dependencies`. `Tool.recommends` is a soft one that
is never resolved, never ordered, never expanded transitively, and never
installed on its own — the two fields share a shape and share nothing else.

`Tool.requires` remains the sole mechanism that determines install ORDER; a
node method's `co_install` shapes only the pnpm INVOCATION and never adds,
reorders or implies a dependency edge. A package named in `co_install` must
independently be a catalog tool that the declaring tool already lists in
`requires`, and a registry test enforces that. `allow_build` may only name
packages the same invocation installs, so the registry cannot widen pnpm's
build-script gate beyond its own install group; the grant pnpm records for
such a package is persistent and package-level rather than per-invocation,
and no version pin this project declares constrains it. `versions` pins group
members so a peer-dependency pair cannot drift apart silently in the commands
THIS project generates. `smoke` names one post-install check from a closed,
code-owned set: the registry selects a check by name and can never supply a
command, so a registry edit cannot introduce arbitrary post-install execution.

The only code that reads `recommends` is
`installer/selection.py::unstaged_recommends`, a flat one-hop lookup that
deliberately does not live beside the resolver, and
`installer/catalog_tui.py`'s selection-time prompt that consumes it.

An id from a `recommends` list enters the staged batch only through an
explicit keypress on that prompt, which performs exactly the mutation a
space-mark performs — so a recommendation the user accepted is
indistinguishable downstream from a row they marked themselves, and nothing
else in the codebase may add one.

The prompt is transient and keeps no per-session state: it and the requires
notice describe one selection moment, so navigating to another view clears
both and disarms the pending ids. That clear hangs off `UnifiedApp.show_view`
(rule 2's single navigation path) via the screen's public `clear_transient`,
not off a screen-suspend handler — `ScreenSuspend` means "no longer top of the
stack", which also covers pushing the nav palette, so it would wipe the state
of a view the user opened a palette over and then cancelled out of. The prompt
reappears on any fresh mark that still has unstaged, uninstalled
recommendations, and accepting is what stops it recurring. Accepting stages and
names only the ids that were not already in the shared batch, since that batch
can move between the offer and the accept.

Phase 2 ships illustrative `recommends` data on `claude` and `opencode` drawn
from tools already in the catalog per CONTEXT D-02; Phase 8 replaces it with
the real companion set once those tools exist.

## Phase 3: install, uninstall, and tweak lifecycle

`installer/deps.py::resolve_dependencies` decides install ORDER and drops a
branch whose dependency is unavailable on this platform — a pre-flight
judgement made from the registry before anything runs. `build_plan` records
each reached tool, including BLOCKED rows for unavailable dependencies, while
`execute_plan` handles a dependency that was available and then FAILED while
installing, which is knowable only mid-run. It carries a per-run failure set;
a skipped dependent is reported as `dependency-failed` with the blocking ids
on `InstallOutcome.blocked_by`, is never handed to the install engine, and is
always listed in the summary. `execute_plan` is a single forward pass that
relies on the resolver's deps-first order and deliberately does not sort, so
`requires` plus `resolve_dependencies` remains the sole ordering mechanism.

`installer/shellrc.py`'s `apply_block`/`strip_block` applies only to files this
installer owns — `~/.myshellrc`, and the rc files it wires a `source` line into
— and every `TweakBundle` uses it. Oh-My-Zsh's `plugins=(...)` array is the
single exception, edited in place by `installer/omz.py`, because `.zshrc` and
that line belong to the user's own oh-my-zsh install, so no tools-installer
marker is ever written there. Only the single-line form is supported; the
multi-line form raises `OmzPluginsError` rather than being parsed — including
when a multi-line array *follows* a single-line one, since that later array is
the assignment zsh honors and editing the dead line above it would report
success while loading nothing. Because `.zshrc` carries no marker, ownership of
the plugin names is recorded in a comment-only block inside `~/.myshellrc`:
`omz.write_plugins` records exactly the names it added, `omz.remove_plugins`
removes exactly those, and `omz.plugins_owned` — not the array's contents — is
the policy's `active`. Content cannot prove ownership (`git` ships in
Oh-My-Zsh's own default `.zshrc`), and a teardown that guessed from content
would delete configuration the installer never wrote.
`OmzPluginsError` subclasses `OSError` specifically so `ui_common.run_live`
surfaces it under rule 3 without any screen adding an `except`. The feature is
a `Policy` produced by `installer/policy.py::omz_plugins_policy` — not a `Tool`
and not a `TweakBundle` — with its Oh-My-Zsh precondition carried by the
`requires`/`missing_requires` fields `Policy` already has.

A full uninstall disables every still-enabled tweak through the same
`Policy.remove` closures the Policies view calls, via
`installer/uninstall.py::sweep_policies`; it never reimplements removal, so
"full uninstall" and "toggle off" are the same operation by construction. A
tweak counts as active when its block is present OR an owned helper executable
is on disk, and ownership means the sentinel check in `installer/tweaks.py` —
or, for the `.zshrc` arm, the recorded-names check in `installer/omz.py` —
never mere existence. Every arm of the sweep answers "is this ours", not "does
this exist". `plan_uninstall` stays the `Tool`-shaped artifact walk and knows
nothing about tweaks.

`active_policies` is the single activity predicate the CLI preview, the
Uninstall view's row and the removal all read. A preview and its effect cannot
diverge because they are the same objects, not because they read the same files
twice: `active_policies` builds the list, `sweep_policies` takes it, and
`run_uninstall` — which deletes artifacts, strips the managed block and removes
shims and alias blocks in between — holds that one list across the whole
teardown. `sweep_tweaks` is the read-then-sweep convenience form, for callers
with nothing in between. The Uninstall view is a separate case: it reads
`active_tweak_ids` at view entry rather than holding a list, because the
Policies view can change the answer while the screen is suspended (see the
`enter_view` rule under rule 2).

## Phase 9: postinstall hooks

`Tool.postinstall: str | None` names a hook in
`installer/postinstall.py::POSTINSTALL_HOOKS`, a closed, code-owned dispatch
table mirroring the existing `smoke` param
(`installer/model.py::POSTINSTALL_HOOK_NAMES` validates the name at load time
exactly like `SMOKE_CHECK_NAMES`); the registry can never carry a literal
postinstall command, only a hook NAME from a closed set, so a registry edit
alone can never introduce arbitrary post-install execution — a deliberate
departure from REQ-postinstall-field's literal "inline command string"
framing, chosen because the one proving case (`codegraph`'s MCP registration)
cannot be expressed as a static string: its `--target` value depends on which
agent hosts are live on the machine at install time.

`installer/engine.py::install_tool` dispatches a declared `postinstall` hook
exactly once, immediately after the specific `Method` that just reported
success, never on the `ALREADY_INSTALLED` early-return path — the structural
reason D-01's "single-direction trigger, no re-trigger on a later unrelated
event" is a property of the code, not a guard that could rot. A hook's
failure is carried on `InstallOutcome.postinstall_warning` and never turns a
successful install into a failed one.

Idempotency is a live check only (`status.is_installed`, `guard_status`,
`has_managed_block`'s existing convention): `codegraph`'s own hook calls
`installer.status.is_installed` directly on the four agent-host catalog
`Tool` objects (threaded through via `install_tool`'s `tools` parameter,
never a hook-local `shutil.which` re-implementation of that seam), mapping
`cursor-agent` to codegraph's own `cursor` target id — a real, live-verified
id mismatch, not a naming choice — and NEVER passes `--target auto`, because
codegraph's own `--target auto` resolution silently falls back to
registering `claude` when it detects zero installed hosts.

The dispatch call is Method-aware (receives the succeeded `Method`) and
isolated in its own `try/except Exception` at the call site, structurally
separate from the method ladder's own exception handling, so an unexpected
hook exception can never be misattributed to the method's own execution or
turn a completed install into `FAILED`.

## Registry-authoring guidelines

### Per-tool, per-OS verification checklist

Before any new `registry.toml` entry ships, its actual install script or
package metadata is read directly — never assumed from a marketing page or a
plausible-sounding guess — and confirmed independently for EACH `os`/`arch`
the entry declares. A prerequisite that is a no-op on one platform is not
assumed to behave the same way on another.

This also means checking, up front, WHICH platforms belong in that list in
the first place — not only verifying the ones already written down. `vscode`,
`jetbrains-toolbox`, and `sublime` shipped with macOS-only methods for a
while despite all three vendors having official Linux tarball/apt/rpm
distributions, because the entries were authored and verified from a macOS
session and Linux was never checked at all — a gap, not a deliberate
exclusion. Read the vendor's own install docs for every OS it officially
supports (macOS, and Linux per-distro/per-arch — amd64 and arm64
separately) before writing methods, and declare one for each platform that
is genuinely feasible to support. If a platform is knowingly left out
(unconfirmed vendor URL, no stable Linux arm64 build, etc.), say so in the
`# Verified` comment rather than silently omitting it.

Every `[[tool]]` block carries a required `verified = YYYY-MM-DD` TOML date
the loader validates (a date, not a string; not in the future beyond one day
of clock skew). A registry verification run refreshes that key when the entry
passes; the dated `# Verified {date}: ...` comment above the block remains the
free-text research note — never a checked-in excerpt or snapshot of the
verified external source. Method keys are a closed set per kind
(`installer/model.py::METHOD_PARAMS`; an unknown key fails to load). A pinned
`app` or `tarball` url templated with `{ver}` must declare `version` and
`sha256` so a bump edits one value.

Download and app kinds smoke-run the staged binary once before the installer
creates or swaps any link, so a broken binary never gets an installer-created
link. An install never moves aside or deletes an existing tree under `~/.local/opt` or bundle under `~/Applications` unless the installer-created link proves it (the same proof the uninstaller uses, `download.is_still_proven`); otherwise that method fails with a remove-it-yourself message and the ladder falls through. Manager kinds (`brew`, `apt`, `dnf`, `pacman`, and similar) are
smoke-run once after the package manager installed them, only when a runnable
target exists (an executable `<bin_dir>/<cmd>`, else the command PATH
resolves), and a smoke failure falls through to the next method while the
package stays installed and is reported with its removal command. The smoke
run uses `--version` unless the method declares `smoke_argv`, the argument list
only (argv[0] is always the installed path; same character set as script
`args`), distinct from a node method's closed `smoke` check name.

Worked examples already in the registry:

- `codegraph` (`installer/registry.toml:1225-1241`) records what the GitHub
  Releases API published and what that does and does not establish.
- `mmdc`/`puppeteer` (the `# Verified 2026-09-05: puppeteer declares...`
  comment block directly above the `mmdc`/`puppeteer` `[[tool]]` entries)
  records the brew-rejection finding, the pnpm postinstall grant, and the
  Linux arm64 gate.
- `sdkman`/`java` (Phase 6 plan 06-01) record the SC#2 finding that `sdk
  install java` needs no pinned `version`.

Where a finding is load-bearing enough that silently deleting the comment
would be a regression, a test in `tests/test_registry.py` asserts specific
substrings of the comment are present in the committed file —
`test_mmdc_entry_records_the_brew_rejection_finding` and
`test_java_and_sdkman_entries_record_the_sc2_no_pin_verification` are the
pattern. The comment is the mechanism; the test is what keeps it from rotting
away unnoticed.

The checklist has no automated enforcement of its own existence — whether a
given entry's author actually did the verification is not machine-checkable —
so it is a process discipline for code review to hold new entries against,
not a lint rule.

### Tool onboarding: tier, dependencies, and postinstall classification

Before any new `registry.toml` entry ships, walk these three questions in
order — this is the checklist that would have caught rtk/graphify's
postinstall gap (researched in Phase 8, never wired into
`installer/postinstall.py` until Phase 12.4) before it sat unnoticed across
three phases.

**1. Tier classification.** State explicitly which of the three tiers
applies and why, per "Tier is a browsing label" above: `system` = a
prerequisite other tools may depend on regardless of personal preference
(uv/pnpm/brew/sdkman/zsh/podman-shaped); `user` = a tool the human runs and
drives directly — a personal-choice dev tool (terminal emulators, CLI
utilities, editors) **or an AI agent harness/CLI** (claude, codex, opencode,
cursor-agent, antigravity, pi, aichat): being AI-branded does not by itself
make something `ai`-tier, what matters is whether the human is the one
typing into it; `ai` = tooling that operates underneath or is consumed BY an
agent session, never launched directly by the human as their own interface —
MCP servers, token-reduction proxies, knowledge-graph builders (codegraph,
graphify, rtk), agent-oriented CLI utilities (rg, fd, sd, bat, eza), or an
agent-ecosystem skill pack (ponytail, superpowers, opengsd, openspec,
spec-kit, softaworks-agent-toolkit, matt-pocock-skills). `Tool.audience`
(`human`/`ai`/`both`) is a separate, independent field recording who
*benefits* from a tool regardless of tier — it is not derived from tier and
tier is not derived from it. Like the brew preference below, tier
classification is not automated — no lint enforces tier correctness.

**2. Dependency-tree declaration.** Read the tool's own install
documentation for its real prerequisites — never assume. If it installs via
`pnpm add -g`/`uv tool install`/an SDKMAN candidate, its `requires` MUST name
the manager tool (`pnpm`, `uv`, `sdkman`) so `installer/deps.py
::resolve_dependencies` drags it in automatically; an undeclared real
dependency silently relies on the user having installed the prerequisite
through some other path. Worked example: `mmdc.requires = ["pnpm",
"puppeteer"]` (Phase 5).

**3. Postinstall-per-harness classification.** Ask, in order:

```
New registry tool needs post-install setup?
│
├─ Fully-installable, on-PATH binary/CLI after a normal Method succeeds,
│  AND needs a non-interactive, host-detection-aware follow-up (register
│  an MCP server, patch a per-agent config file)?
│  -> Tool.postinstall = "<hook-name>", dispatched through
│     installer/postinstall.py's closed POSTINSTALL_HOOKS table.
│     Worked examples: codegraph (Phase 9), rtk/graphify (Phase 12.4).
│
├─ Delivered AS a skill into one or more AI-assistant hosts, where
│  install/status/update/removal are each either fundamentally
│  interactive or need a human trust-review step?
│  -> [[tool.method]] kind = "skill_pack" with [tool.skill_lifecycle]
│     (mode = "manual-required", or mode = "command" for a closed,
│     read-only operation_id status probe).
│     Worked examples: ponytail, openspec, opengsd, and the other
│     skill_pack entries already in installer/registry.toml.
│
├─ Setup requires a live terminal or user-selected project target that
│  cannot be safely scripted from a Textual worker thread?
│  -> [[tool.method]] kind = "host_setup", setup_id = "<id>" resolved
│     through installer/host_setup.py::HOST_SETUPS (a closed registry
│     of reviewed console handoffs, displayed not executed).
│     Worked example: pi.
│
└─ None of the above -> no postinstall wiring; the tool is a plain
   binary with nothing further to do.
```

Restate explicitly: **the registry can only select a hook NAME from a
closed, code-owned set in every one of these three mechanisms — never a
literal command string.** A registry edit alone can never introduce
arbitrary post-install execution (see "Phase 9: postinstall hooks" above);
this invariant must never be relaxed to give a future entry an
inline-command escape hatch.

State D-01a's principle as a standing rule for any future postinstall hook
this checklist routes a tool into: **detect and configure, never
blind-overwrite.** A hook must never pass a flag that overwrites existing
host configuration unconditionally — the confirmed real-world precedent is
GSD's own installer writing `gsd-statusline.js` on Claude Code automatically,
with no flag to skip it, a genuine risk for any environment running a
separate custom statusline. Every hook in this project's dispatch table
gates on live host presence (`present_agent_hosts()`,
`installer/postinstall.py`) before writing anything, and every hook's own
per-host write behavior should be verified merge-safe against pre-existing
config before shipping — not assumed (12.4-01/12.4-02's live adversarial-seed
verification against rtk/graphify is the worked example).

Do not confuse this NAMED, singular `Tool.postinstall` mechanism with
`installer/model.py`'s similarly-named but semantically distinct
`Tool.post_install` (plural) field and its `POST_INSTALL_ACTIONS` tuple —
the two are separate, unrelated concepts despite the near-identical name.
The plural field is read in production by `installer/post_install.py` at
the post-success point of the install ladder; it must never be merged into
the singular hook table.

The invocable skill at `.claude/skills/tool-onboarding/SKILL.md` walks this
same three-question checklist interactively for a human or agent adding a
new tool — it references this subsection rather than duplicating it, so
there is exactly one canonical copy of the decision tree.

### Prefer brew

For a new user-tier tool with no other constraint, Homebrew is preferred over
pnpm/npm, uv tool, or a bespoke script. The standing exception is the Java
toolchain (`java`/`gradle`/`maven`/`groovy`/`springbootcli`): those install
exclusively through SDKMAN (REQ-sdkman-exclusivity), never a native or brew
package. The `java` entry's own `desc` field already says so, and commit
`0e05f50`'s message records the same reasoning: "brew is preferred generally,
but Java-toolchain tools must go through SDKMAN specifically, never a
native/brew package."

The general "prefer brew" preference is documented-only — no lint or test
enforces the preference itself (D-02) — because brew availability differs too
much per OS/tool for an automated "why isn't this brew" check to avoid noisy
false positives. That is distinct from the SDKMAN carve-out named alongside
it: unlike the general preference, the carve-out is already test-enforced
today. `test_java_tools_install_exclusively_through_sdkman`
(`tests/test_registry.py:122-140`) asserts all five Java-toolchain tools have
exactly one `sdkman`-kind method with no brew/native fallback. D-02 covers
only the general brew-preference convention, not the carve-out.

### Platform-unavailable catalog rows reuse the Uninstall view's dim/non-selectable pattern

A registry entry whose `Method.os` / `Method.arch` / `min_os_version`
restrictions leave it with no applicable method on the current machine is
shown disabled in both places that already need to know this. On the
CLI/install-time path, `installer/engine.py::install_tool` reports
`NO_METHOD` — unchanged. On the catalog-browsing path,
`setup.py::_build_app` computes `installer/resolve.py::platform_could_support`
per tool, threads that boolean through `UnifiedApp` into `CatalogScreen`, and
`CatalogScreen` reuses `BrowserAdapter.selectable` — an already-existing,
already-generic `ToolBrowser` field `UninstallScreen._tool_entry` already
exercises for its dim rows — to dim the row and make it non-selectable.

`platform_could_support` is used instead of a bare `resolve_methods` check
because it resolves against a hypothetical Homebrew-present platform. A
machine that merely has not bootstrapped Homebrew yet is never wrongly marked
disabled; only a genuine `os` / `arch` / macOS-version incompatibility is.
This is related to, not identical with, `classify_tools`'s
`UninstallState.UNAVAILABLE` branch, which answers a narrower
Uninstall-specific question after excluding removable/managed/installed
tools. Do not conflate the two.

This reconciles, rather than contradicts, the "Tier is a browsing label"
reasoning that "a screen with no `Platform` must not make a judgement it
cannot make correctly." `CatalogScreen` no longer lacks `Platform`-derived
data once `setup.py`'s composition root threads it through, the same way the
Uninstall view already receives one. The principle was never "never give a
screen this data"; it was "never judge without it."

This convention is not new. `codegraph`'s Linux/macOS split and `puppeteer`'s
Linux-arm64 gate already produce `NO_METHOD` on the CLI path. The worked
example this phase adds is Apple Containers (`container`): one method with
`os=["macos"]`, `arch=["arm64"]`, `min_os_version="26"` (D-01, Phase 7). The
tool always appears in its tier view (never omitted) and, where genuinely
unavailable, is dimmed and non-selectable while browsing, via the same
mechanism the Uninstall view already shipped — zero new rendering
primitives, only a new wire plus one new, tested predicate.

This resolves 07-RESEARCH.md's Open Question 1 AND Pitfall 4. D-01's "reuse
the existing unmet-requires/unavailable-dependency display pattern" language
pointed at the Uninstall view's dim/non-selectable rows, not at `NO_METHOD`
(a first-draft misreading) and not at inventing a new primitive. The
macOS-version gap Pitfall 4 originally recommended leaving unbuilt was,
after being flagged HIGH by cross-AI review in both cycle 1 and cycle 2 as
"documented but unimplemented," genuinely implemented: a stdlib-only
`Platform.os_version` field and a `Method`-level `min_os_version` gate,
  reusing the already-tested `installer/versions.py::meets_minimum`. No
residual gap remains for the version case: a too-old-macOS Apple-Silicon Mac
now resolves zero methods and is shown disabled, exactly like a wrong-`os` /
wrong-`arch` machine.

## Phase 12: version-aware status and the update action

`installer/resolve.py::resolve_methods` returns platform-applicable methods
ordered by the `_RANK` install-preference ladder. That ordering answers
"which method should we try first when installing", and it is never provenance.
`rg` declares `github_release` (rank 20) and `brew` (rank 40), so a
brew-installed `rg` would be misread as a GitHub download by anything that
treats index 0 as the owning manager.

`installer/ownership.py` answers the different question. Ownership comes
from installer-artifact presence (`installer/uninstall.py::plan_uninstall`),
real manager inventory membership (`brew list --versions`, `pnpm list -g
--json` via the existing `pnpm_global_packages`, `uv tool list`), and live
PATH attribution (`shutil.which` plus each owner's known directories,
including brew's own `brew --prefix`). An inventory that could not be read
is `None`, never an empty set, and an unresolvable owner is `unknown` —
fail closed. The two concepts must not be merged.

The evidence rule is the load-bearing half: ownership is asserted only when
the live executable is attributable to the candidate, or when every other
manager that could have owned the tool was queried successfully and did not
claim it. One positive candidate beside an inventory that could not be read
is `unknown`, not ownership — `plan_uninstall` proves an artifact EXISTS,
never that it is the active copy, so a stale `~/.local/bin` artifact next
to an unreadable brew inventory and a live `/opt/homebrew/bin/<cmd>` must
not resolve to this installer. `ManagerOwnership` carries the evidence
(`candidates`, `active_candidate`, `active_path`, `unknown_reason`) so the
UI can say WHY a row is unknown, and `MUTATION_GRADE` is the single list of
confidence values a mutating action may act on. There is no fixed-order
tiebreak anywhere: ambiguity resolves to `unknown`.

The mutating update action acts only on a resolved `ManagerOwnership` whose
confidence is in `MUTATION_GRADE`, and refuses everything else outright
with the recorded reason. This is why ownership is a prerequisite of
`installer/update.py` rather than a convenience. Display can be cheap and
cached; mutation cannot — `UpdateService.run` re-resolves ownership for
the one tool at mutation time and uses that fresh result, never the
six-hour snapshot that gated the keypress.

Update is not install re-run: `installer/engine.py::install_tool`'s
`is_installed` short-circuit returns `ALREADY_INSTALLED` before resolving
a method, and the install-side download/archive/app executors write over
live artifacts. `installer/download.py::update_download` and
`installer/apps.py::update_app` stage, validate, and replace through one
rollback state machine — remnant recovery, aside-move, swap, symlink
recreation, validation — retaining the prior installation and its symlink
until the last step succeeds.

A pnpm-owned tool is the exception that proves the rule: its update
dispatches `installer/executors.py::execute` with the registry's own
`node` method — the same path the install takes — rather than any
`pnpm update -g` argv. Plain `pnpm update` respects the package's declared
range and would not reach the version the outdated report advertises,
`--latest` would discard this project's own registry pins, and either bare
argv would bypass `_node`'s co-install grouping, `--allow-build`
allowances, version floors, and smoke check. Reusing the install executor
makes it impossible for the update path and the install path to drift
apart.

REQ-pnpm-global-reinstall-mitigation's automatic trigger captures the
pnpm-managed global set BEFORE the update and replays that captured
snapshot afterwards. The order is the mitigation: a snapshot taken after a
pnpm self-update can already be empty, and `reinstall_node_globals` treats
an empty list as a no-op, so a post-update capture would report success
while restoring nothing. The trigger keys on `tool.id == "pnpm"`, not on
the manager performing the update, because pnpm itself has no `node`
method.

`installer/version_cache.py` also caches the manager reports themselves —
inventory and outdated, as one timestamped snapshot under the same file's
`managers` key — so navigating between tier views does not launch brew,
pnpm, and uv child processes each time. Its window is short (hours, not
the GitHub cache's seven days) because it describes local state, and every
mutation this app performs calls `VersionRefreshService.invalidate`, which
drops the snapshot and bumps a shared status epoch. That epoch is also
what stops a version refresh started before an update from landing after
it and overwriting the freshly re-probed row.

`installer/version_cache.py` is this project's first persisted JSON state
file (`~/.local/state/tools-installer/versions.json`, the `~/.local/...`
userspace convention from `installer/locations.py`). It is written through
`installer/atomic.py::atomic_write_text`, the one sibling-temp-plus-
`os.replace` implementation this repository has — `installer/omz.py` and
`installer/daemon.py` both delegate to it, where before Phase 12 each
carried its own copy. A malformed entry degrades to "never checked"; a
timestamp is only trusted when it is timezone-aware, normalized to UTC,
and not implausibly in the future; and nothing from the cache ever reaches
an argv.

The `u` action is registered in `installer/ui_common.py`'s `VIEWS` table,
not only in `CatalogScreen.BINDINGS` — rule 1 again, and a concrete
instance of why it exists: this project renders its own footer from
`View.actions`, so a binding added without the registry row is an action
the user is never told about.

The refresh fires on catalog view entry for stale entries only, mirroring
`DoctorScreen`'s own screen-entry audit, and is bounded by a per-pass
fetch budget plus a failed-attempt backoff so an offline or rate-limited
machine cannot retry on every navigation. Because a bounded pass leaves
some rows unconfirmed, staleness is SHOWN as well as acted on: a Ver cell
whose `latest` came from an entry at or past `STALE_AFTER` carries a
trailing dim marker and its detail line says so. Both halves of
REQ-cached-timestamped-version-state — the marker and the re-check — are
user-observable.

Ownership covers this installer, brew, cask, pnpm, and uv only. `dnf`,
`apt`, `pacman`, and `rpm_ostree` are valid `METHOD_KINDS` but were out of
scope for Phase 12: a tool installed through a Linux system package
manager resolves to `owner="unknown"`, renders unknown, and is refused by
the update action. That is the fail-closed default, not a defect;
extending it means adding an inventory reader and an outdated parser, with
no change to the resolver's shape.

REQ-manager-drift-alerting was deferred in this phase: `brew outdated`
cannot observe an uninstalled brew alternative, the registry has no
qualifying row, and an unwired helper would violate rule 5. The full
record is in `.planning/REQUIREMENTS.md`.

## Phase 12.3: container e2e verification of the reconciled branch

`scripts/detect-container-runtime.sh` is the reusable entry point every
future Tier-3 container-based e2e phase should call rather than
re-deriving OS/arch container-tool detection from scratch. It picks a
container tool the same way a human operator would reason about it — OS
via `uname -s` (Darwin -> macos, Linux -> linux), arch via `uname -m`
mirroring `installer/platform.py`'s own amd64/arm64 mapping — and never
trusts a bare `which <tool>`: the candidate is live-proved by actually
running a throwaway container (`run --rm docker.io/library/alpine:latest
true`) before it is accepted. On success it prints `CONTAINER_TOOL=<tool>`
on stdout and exits 0; a caller sources or captures that single line. On
Linux this resolves to `podman` when present and provable, `docker`
otherwise. On macOS it tries `colima`+`docker` first, then a provable
`docker` or `podman` alone.

The D-03 gate is the script's own no-silent-fallback contract: when
nothing on the host both exists AND live-proves successfully, `refuse()`
exits 3 with a fixed, three-option verbatim message (install one of
podman/docker/colima, or skip this phase's e2e verification) — it never
guesses a runtime that turned out not to actually work, and it never
substitutes a different tool than the one it told the caller it detected.

`scripts/container-e2e-verify.sh` is the harness built on top of that
detection script for this phase's specific full-catalog proof: it
bootstraps a named, long-lived Fedora 44 container
(`tools-installer-e2e-12-3`) with a non-root sudo-capable tester user,
Homebrew, and uv — never touching the host — then drives the real `uv run
setup.py --all --yes` / `--uninstall --yes` entrypoints against it through
three subcommands. `pass1` runs one clean-install pass and gates success on
`failed == 0`, `mismatched == 0`, and every `dependency_failed` blocker
being cross-checked (not assumed) against the same run's own
`manual_required` list. `pass2` runs a second install over already-
installed state, a full uninstall sweep, and a third reinstall — the
idempotency and uninstall-correctness properties a single clean-install
pass and the mocked unit-test suite structurally cannot surface — using
the identical acceptance gate for its rerun and reinstall steps, and tears
the container down once all three steps pass. `resync` re-copies the
host's read-only `/repo` mount onto the container's writable workspace,
required after any host-side fix before re-running either pass. A future
e2e phase for a different distro family should add a new pass1/pass2-style
subcommand reusing this same detection-script + named-container pattern,
not invent a parallel harness.

## Phase 12.4: tool onboarding and registry postinstall audit

`installer/postinstall.py::present_agent_hosts(tools)` is the single shared
computation of which of the four canonical agent-host catalog ids
(`claude`/`codex`/`opencode`/`cursor-agent`) are actually installed — every
`postinstall` hook that needs host-presence detection calls it rather than
re-deriving its own loop over `installer.status.is_installed`. It was
extracted from `_codegraph_mcp_register`'s original inline loop (Phase 9)
with zero observable behavior change, and is now shared by two hooks in
`POSTINSTALL_HOOKS`:

1. `codegraph-mcp-register` (Phase 9) — composes one `--target` CSV call.
2. `rtk-register` (Phase 12.4) — one `rtk init <args>` invocation per
   present host; `cursor-agent`'s branch only fires when `claude` is ALSO
   present, because live testing against the real rtk v0.49.0 binary
   confirmed `--agent cursor` still unconditionally also writes Claude
   Code's `RTK.md`/`settings.json` as a side effect — writing unrequested
   Claude Code scaffolding on a Cursor-only machine would violate D-01a's
   detect-and-configure-never-blind-overwrite principle below.
3. `graphify-register` (Phase 12.4, removed in Phase 17) — its
   `graphify <host> install` invocations write into the working directory
   for at least one host on every registration form (SAFE-02/D-03), so the
   installer must never run one: the registry key was removed and the hook
   deleted.

**Detect and configure, never blind-overwrite (D-01a).** A postinstall hook
must never pass a flag that overwrites existing host configuration
unconditionally — the confirmed real-world precedent is GSD's own installer
writing `gsd-statusline.js` on Claude Code automatically, with no flag to
skip it. Every hook here gates on live host presence before writing
anything, and every hook's per-host write behavior is verified merge-safe
against pre-existing config before shipping — proven for `rtk`/`graphify`
via live adversarial-seed testing in isolated scratch `$HOME`s (see
12.4-01-SUMMARY.md, 12.4-02-SUMMARY.md), never assumed.

**Registry-authoring guidelines** (above) gained a permanent tier/
dependency/postinstall onboarding checklist, and `.claude/skills/
tool-onboarding/SKILL.md` (this project's first self-authored skill) walks
it interactively — this is the checklist that would have caught rtk/
graphify's own gap (researched Phase 8, wired Phase 12.4) before it sat
unnoticed across three phases.

The D-04 full-catalog audit this checklist enables ran against all 89
`registry.toml` entries: zero new postinstall-mechanism gaps found. One
pre-existing, unrelated finding (`Tool.post_install` plural,
`POST_INSTALL_ACTIONS`, `SENSITIVE_POST_INSTALL_ACTIONS` — confusingly
similar name to the live `Tool.postinstall` singular mechanism) was
logged as a pending todo rather than fixed in-phase; Phase 14 later
adopted the plural field as a production dispatcher in
`installer/post_install.py`. Full findings:
`.planning/phases/12.4-tool-onboarding-research-skill-and-registry-postinstall-audi/12.4-AUDIT.md`.

## Phase 13: live in-TUI install execution and persisted wizard settings

`installer/execute_screen.py` is an IO adapter, not a second decision
layer. `build_plan`, `execute_plan`, `install_tool`, `configure_path` and
`run_doctor` remain the sole owners of install control flow; the screen
formats their output and streams it. The abandoned `feat/install-experience`
branch split that responsibility across three modules with no owning seam,
and this phase's audit rated that split a real defect.

The execute screen is a `ModalScreen` and not a registered view.
`AppScreen` requires a `VIEWS` row; a row would give the screen a number
key and a palette entry; a navigable execution screen breaks the
`[catalog] / [catalog, <view>]` stack invariant `UnifiedApp._navigable`
protects. A pushed non-navigable screen is the established shape here
(`ConfirmUninstall`, `NavScreen`, `TimePickerScreen`).

`installer/run.py::StreamingRunner` is the only `Runner` in this project
that reads a child's output incrementally. It is installed through the
same single `Runner` seam every executor already calls. Attribution is
structural: `attributed_install` was deleted in Phase 20 when the per-row
`on_row_started` hook took over `StreamingRunner.set_tool` before commands
run, so attribution remains structural and no optional argument can drop it.
The checksum-mismatch seam is `push_screen_wait`
(`ask_from_worker` wraps `call_from_thread` + `push_screen_wait`). That
is a deliberate, documented exception to rule 2 rather than a violation
of it: rule 2 governs main-thread callers, and a thread worker has no
callback to return into.

A failure never aborts the batch. `should_continue` is checked between
tools and never during one; an in-flight child is always allowed to
finish; "not attempted" is derived by differencing the resolved ids
against the returned outcomes rather than by adding an `InstallStatus`
member. The weak form was chosen because killing a half-written install
is worse than a slow one, and terminating children would pull subprocess
lifecycle management into a phase that otherwise needs none.

The link mode lives in `installer/settings.py`. It is asked at most once
inside the app, is adjustable from `PoliciesScreen` with no new view, and
an explicit `--link-mode` overrides for one run without rewriting the
stored value.

Every consumer of the link mode re-reads it rather than capturing it at
construction time — the Doctor preview and fix, the execute screen's
PATH wiring, `ban_policy`'s alias targets and `tweak_policy`'s source
targets. A ban enabled after switching to split mode would otherwise
write aliases into a `~/.myshellrc` nothing sources, with nothing on
screen to reveal it. This is the same predicate-not-its-result reasoning
the `guard_state` parameter already carries.

## Phase 14: update dispatch and the login-shell handoff

Selecting an outdated, already-installed tool routes to
`UpdateService.run` rather than the install ladder. `build_plan` makes
that install/update split from `ToolState` health and `update_refusal`, never
inside `resolve_dependencies`: `deps.py` still treats "installed" as
satisfied, because it has no access to version state or manager
attribution and this phase deliberately left that contract unchanged.
All update mutation goes through the update service's own entry point,
which re-resolves ownership freshly and refuses on its own, so no
caller re-implements the ownership gate. A refusal is reported with
the same `cannot update {id}: {reason}` sentence the per-row `u`
keybind already produces — two wordings for one refusal is how users
learn to distrust one of them.

The plural post-install action list (`Tool.post_install`,
`POST_INSTALL_ACTIONS`, dispatched by `installer/post_install.py`) and
the singular post-install hook (`Tool.postinstall`,
`POSTINSTALL_HOOKS` in `installer/postinstall.py`) are two disjoint
closed name sets in two separate modules, one character apart in
name, and must never be merged. Wiring `set_login_shell` into the
singular table would either invent an execution seam this phase
refused to give the action, or smuggle a reviewed-instruction
producer into a table whose every other entry mutates the host.

`set_login_shell` is hard-blocked on `Platform.immutable` before any
prompt is offered. The reason is ublue-os/bazzite#4159: `chsh` to zsh
on Bazzite has been observed to break KDE/SDDM login, and that issue
was closed "not planned" with no maintainer root-cause analysis. The
block is therefore conservative by necessity rather than by
preference; relaxing it for a specific atomic variant would require
re-verifying against that issue, which currently cannot be done. The
action produces reviewed `chsh -s $(which zsh)` instructions and the
installer never runs the command, citing the existing host-setup
doctrine (`installer/host_setup.py`: reviewed console handoffs, never
launched from a worker thread). `App.suspend()` as an in-process
alternative was considered and deferred, not overlooked.

`execute_plan` binds the sensitive-action confirmation inside its one
install wrapper, `_with_force`, which also adds `repair=True` for repair and
reinstall rows. `SensitiveInstall` carries the confirmation keyword at the
live install seam. Unattended (`--yes`) means no callback on both entry
points, which the dispatcher treats as skip.

## Phase 15.2: forcing child output and the silence indicator

`PYTHONUNBUFFERED` is set on every streamed child unconditionally and
merged over `os.environ`, because it is Python-specific, safe, and a
no-op elsewhere — it is the one rung that needs no availability check.

`stdbuf -oL` is opt-in through `StreamingRunner`'s `unbuffer` knob,
resolved once per runner and skipped silently when the binary is
absent, and it is skipped for a Python child because the env var
already covers that case. It carries no manager name: `pnpm` and
SDKMAN are the reason the rung exists, never a branch inside it —
Phase 6's registry-authoring guideline applied to a runner.

`LD_PRELOAD` is how `stdbuf` works, which is why the effect reaches a
`curl | sh` installer's own grandchildren, and also why it is a
harmless no-op across `sudo`'s setuid boundary. That is stated rather
than special-cased.

A launch that fails on the wrapped argv is `retried unwrapped`, once.
Resolving `stdbuf` in the constructor opens a window in which it can
vanish before a later command launches, and an unavailable forcing
mechanism must never fail an install. The retry is safe only because
`Popen` raised before the target command started; it must never be
generalised to the non-zero-exit path, which would re-run a
side-effecting installer.

`CommandError` reports the `unwrapped argv`. A user must be able to
paste back the command a failure names, so the wrapped list exists
only as the value handed to `Popen`.

The `waiting for output` indicator is UI-side only, produced by
`ExecuteScreen`'s one-shot check at `SILENCE_SECONDS` and posted as a
transient `InstallLogLine`. The timer re-arms itself for the exact
remaining distance when a line arrived after it was armed, so it
fires at the threshold rather than at a poll boundary, and it costs
one pending timer rather than one per log line. `StreamingRunner`'s
bounded `tail` is fed only by lines read from the child's stdout, so
a failure report can never repeat it — that separation is the
mechanism, not a filter. The copy claims only liveness and waiting,
never that the child is healthy: from the parent, buffering and a
hang look identical.

Every transient carries the `silence generation` it was minted
under, and the handler drops it unless that generation, the in-flight
tool, the prompt state and the finished flag all still agree. The
indicator is posted asynchronously into the same queue the worker
posts real lines to, so without that token a stale reassurance could
be rendered after the output it was waiting for.

The indicator is `per in-flight tool` and never global: it is cleared
when THAT tool — the one in flight, matched by id, not merely any
tool — reports a terminal status, and suppressed while a prompt modal
holds the run, because a pause the status line already explains does
not need a second explanation. The in-flight tool is established by
the first non-transient log line for that tool — `-- trying {method}
--` for an install, and the `-- updating --` marker `_run_updates`
posts for an update, which exists precisely because updates run
through `run_captured` and would otherwise spend their whole lifetime
with no in-flight tool and a blank log.



## Phase 15.8: one PATH emitter, and a foreign file this project refuses to parse

Exactly one function in `installer/` builds a PATH line, and what it
emits is the case-guarded self-deduping form: the directory is
contributed only when a scan of the current PATH does not already
contain it. The shape is load-bearing rather than stylistic.
`installer/rcclean.py`'s duplicate-line scanner anchors on a line that
STARTS with a PATH assignment, so a guard that began with one would be
flagged and stripped by this project's own cleanup path — an installer
deleting its own wiring. Both directions are pinned by tests: the
scanner ignores our output, and our output never starts with an
assignment, so the coupling cannot rot silently.

Two properties of the emitted value are security properties, and they
are the ones a future simplification would remove first. The new
directory is contributed to PATH conditionally, so an empty PATH becomes
exactly the managed directory and never grows an empty component — and
an empty component means the current working directory to every POSIX
shell, which would let any directory the user walks into supply
executables to a managed shell. The guard also reads PATH through a
default-applying expansion, so a shell running under `set -u` with PATH
unset is not aborted by our own block. Both were found in cross-AI plan
review and both have committed tests, including one asserting that an
executable sitting in the working directory is NOT reachable through the
emitted block.

The third property is the phase's recurring rule. The guard MATCHES
every spelling of the directory while the assignment WRITES only the
declared one. A directory reachable under two names — this project's own
host symlinks `/home` to `var/home`, and macOS symlinks `/var` to
`private/var` — is one directory, and a guard comparing a single literal
string would prepend a redundant copy of it. Emission stays narrow
because Doctor's `audit_path` and `rcclean.py` both compare DECLARED
directory strings against raw PATH entries, so a canonicalized emitted
value would make Doctor report a correctly-wired directory as missing.
The general rule, which recurs twice more below: widen what we
RECOGNIZE, keep what we WRITE narrow. One adjacent finding is left open —
`audit_path` has the same spelling blindness in its own reporting, and
fixing it is a question for a later phase.

File-content idempotency and runtime-effect idempotency are two
different properties. The marker-block mechanism has always given the
first; before this phase nothing gave the second, which is why a nested
shell that re-sourced the file accumulated a copy of each managed
directory per nesting level. The second property is proven by sourcing
the real emitted block in a real shell and counting, never by asserting
on a string.

Migration needs no migration code: `apply_block` replaces the last
marker span, so changing what `managed_block` returns IS the migration.
The honest caveat stands — the file is corrected on the next apply, the
already-running shell session keeps its accumulated PATH until it exits,
and the existing "restart your shell" wording already says so.

`write_pnpm_home` and `existing_managed_bin_dirs` were deleted rather
than ported. Both had zero callers once `installer/install_actions.py`
was retired, and rule 5 says a helper with no production caller is
deleted or adopted; pnpm's bin directory stays managed through the
ordinary registry `bin_dir` mechanism. A parser was not preserved merely
to keep a round-trip property nothing exercised.

Two scans replaced that vigilance. An AST-level test over `installer/`
and `setup.py` reconstructs the shell text each module builds —
including text assembled from fragments across statements — and fails
the suite if any module outside the one emitter builds an accumulating
PATH assignment in ANY parameter-expansion spelling, with its single
exemption scoped to one docstring node rather than to a whole file, and
with that exemption asserted to be live — it must match a real hit of
the expected node KIND, so an entry that has quietly stopped matching
anything cannot sit there as a blanket allowance. The emitter itself,
`path_export_guard`, carries no exemption: it assembles its assignment
through an intermediate local, so the reconstruction yields no hit for
it, and an entry would therefore cover whatever that function might
later build. Its runtime guarantee is carried instead by the real-shell
repeated-source tests, which observe actual PATH contents rather than
source shape. An AST scan is structurally blind to shell scripts,
and two live instances of this same defect were found in
`scripts/container-e2e-verify.sh` writing plain exports into a
container's rc files, so a second text-level scan covers `install.sh`
and every script under `scripts/`, sharing one definition of a PATH
expansion with the Python needle. The surviving PATH assignments there
are classified by a stated property rather than silenced by a bare
allowlist: each is evaluated once per process and never re-sourced by a
nested shell — the same property that puts `installer/executors.py`'s
command prefix outside the Python needle.

The boundary of the deletion claim is exactly this wide and no wider:
the deletion removed no PATH behavior. It is NOT true that it removed no
user-visible behavior. The deleted function also emitted a `PNPM_HOME`
assignment, and nothing else in the repo emits that variable. That is a
PRE-EXISTING gap, opened when the only caller was retired rather than by
this deletion, with `installer/ownership.py` reading the variable
opportunistically from the environment when pnpm's own installer has set
it. Whether anything SHOULD write it is an open question for a later
phase, recorded here as open rather than settled.

`~/.shellrc` is foreign by construction. It is only ever read as opaque
bytes — never sourced, never evaluated, not even to inspect it. Its
content is copied forward, and the original is backed up to
`~/.shellrc.tools-installer.old` through `atomic.py`'s existing
staged-sibling convention BEFORE the file is replaced by a marked stub —
in that order, so no crash ordering can lose it and the only write that
removes a copy of the content comes last.

The backup has its own rules, each for a reason. The raw bytes are
preserved with the original's permission bits, because reading as text
would normalize CRLF and a restored file would not be the original. It
is created no-clobber. A pre-existing backup whose bytes differ from the
current original REFUSES the whole operation, because a backup from
another tool or from an older original makes "reversible with one `mv`"
false. And — the part a bytes comparison alone would have missed — an
existing backup must be a REGULAR FILE, checked with `lstat` so the link
itself is seen, and must match on permission bits as well as bytes: a
symlink at the backup path pointing at the original compares byte-equal,
is accepted as a resumed run, and then resolves to the stub the moment
the stub is written, so the original bytes are gone and the promised
`mv` points a link at itself; and a byte-matching backup with different
bits cannot keep a byte-AND-mode restoration promise.

The preconditions are refusals rather than best-effort handling. This
project's atomic writer resolves a symlinked target rather than
replacing the symlink — correct for a dotfile-manager's `~/.zshrc`, and
content-destroying for a foreign file about to be replaced, because a
`~/.shellrc` linked to `~/.myshellrc` would have the stub write replace
the canonical file with a stub that sources itself. Either path being a
symlink, or the two resolving to one file, refuses. A `~/.shellrc` whose
bytes are not valid UTF-8 refuses too, before any write and as a typed
outcome rather than an escaping decode error — the same call
`installer/omz.py` already makes for the same reason.

The original is read through a snapshot bound to the file's identity,
and that identity and those bytes are revalidated immediately before the
file is replaced, so an edit landing between the read and the
replacement is refused rather than destroyed. That refusal undoes
exactly the two writes that call made, which does not contradict the
no-rollback-needed reasoning above: a crash leaves the content in more
than one place with no process left to undo anything, while this path is
a live process that knows precisely what it wrote.

Exactly one source-line shape is rewritten automatically — a simple
logical line that is nothing but a statically resolved source of the
target, disabled by commenting with its original text preserved. Every
other live mention in command position, whether compound, reserved-word,
negated, continued, assignment-prefixed, a `case` arm, or indirect,
refuses the operation. Refusing is the only move that is wrong in
neither direction: a missed line ships a self-sourcing file, and a
wholesale comment-out of a compound line silently deletes the commands
sharing it.

The rule behind that rule is the load-bearing decision, and a future
reader will be tempted to undo it: this project does NOT parse shell.
Detection is widened by normalization — all quote characters removed
before expansion, comparison through `realpath` so two spellings of one
file match — and anything not provably simple is REFUSED rather than
handled. A file containing any here-document, any live `eval`, or any
source command whose argument does not statically resolve is left
untouched, with a reason naming the line. This follows two existing
precedents, so it reads as house doctrine rather than one function's
timidity: `installer/omz.py`'s multi-line plugin array, which the
matcher is deliberately built to fail on rather than half-parse, and
`installer/daemon.py::install_wrapper`'s refusal to clobber an
unsentineled file. The cost is plain — such a `~/.shellrc` is never
auto-consolidated, and the user is told exactly what to do by hand.

After consolidation an rc file reaches `~/.myshellrc` by exactly one
route. A generic `~/.shellrc` exists precisely so that `.bashrc` can
source it, and adding our own source block on top of that stub would
execute the canonical file twice on every startup, duplicating every
unmanaged export it carries. Two residuals are accepted. The detector
answers "is there a live source command", not "will it run", so an rc
that sources `~/.shellrc` only under a condition that never holds ends
up with no route. And the detector has a third answer, `unprovable`, for
a source command whose argument it cannot resolve; that answer takes the
ORDINARY route and prints a diagnostic, because a shell-environment
`eval` in a real `.bashrc` is commonplace and treating it as "already
wired" would leave PATH unwired for most users — trading a
duplicate-execution risk for a total-failure certainty. Both residuals
are made diagnosable by a console line and by Doctor's own audit, and
that visibility is why they are acceptable.

`~/.myshellrc` is the only file this project edits freely. A foreign
file carrying tools-installer markers, or a `~/.myshellrc` that already
sources `~/.shellrc`, is refused rather than merged. Split link mode
skips consolidation entirely, because it maintains no `~/.myshellrc`.
One residual is deliberately not fixed: foreign PATH exports copied
forward keep their original accumulating behavior, because rewriting a
user's own lines would break the verbatim copy-forward promise, and
`rcclean.py` is the separate, user-facing mechanism for other tools'
plain exports.

EVERY write in `installer/shellrc.py` goes through
`installer/atomic.py`. A truncated `.bashrc`, `.zshrc` or `.myshellrc`
is unrecoverable, and every one of these files is edited
read-modify-write. The pre-existing PATH-block writers were converted in
this phase alongside the new consolidation writes, so this is a rule
with no exception left to hedge against. The one deliberate departure is
the `~/.shellrc` backup, created with an `O_EXCL` open rather than an
atomic write, because no-clobber CREATION is the property that matters
there and the atomic writers replace by design.

A refusal is never reported as success. Consolidation returns a typed
outcome, and the one route whose console is a discarded sink — Doctor's
apply — raises a typed refusal that the shared `run_live` maps to the
screen's error, so the screen cannot render a green success line over a
refusal. A return value was not enough on that route because the apply
action discards `run_live`'s result and derives success purely from the
absence of an exception.

The coverage boundary, stated honestly: the guard idiom is proven live
under bash, zsh and this host's `/bin/sh` (which is bash invoked as
`sh`). `dash` could not be installed here, so pure-POSIX-shell behavior
rests on `case`/`esac` being core POSIX grammar and on pnpm shipping the
same idiom in production — a reasoned residual, never a completed proof.
The `~/.shellrc` cases are proven against synthetic fixtures, because no
such file exists on this host.

## Phase 19: one tool state, health and receipts

Every catalog view reads one `ToolState` per tool. A refresh pass builds
that map and publishes it with one assignment, and `state_of` is the only
per-tool reader. The pass takes a monotonic sequence together with the
epoch. An overtaken pass publishes nothing, including one that finishes
later at the same epoch. A partial pass merges per record, newest sequence
wins, so an older full pass may still fill a tool the newer pass did not
cover. Before anything publishes, and whenever the published generation is
not the current one, `state_of` returns none and the row shows `…`.

Identical passes share one fetch. The single flight joins a request to an
in-flight pass with the same tool ids and the same epoch, and a join never
crosses an invalidate. The cache is saved after the swap, for the records
that pass published, and a save failure keeps the states and sets a
warning.

`tool_health` is pure. Present tools take, in precedence order, checking,
then broken, then misconfigured, then outdated, else ok, and the winning
facts come first in the reasons. An absent tool is missing when a method
applies and unavailable when none does. Shadowed, off-policy, unknown
owner and unreadable version are reasons, not states.

`receipts.py` is the one receipt module. The file is
`~/.local/state/tools-installer/receipts/<id>.json`, schema `"v": 1`, and
the reader fails closed: an unknown version, malformed JSON, a file past
the size cap or an unreadable file is no proof and never a crash. Writes
go through the existing atomic writer under one lock. `record` is the one
writer, called after a successful install and after a successful update.
Native, skill and `host_setup` kinds write none. A failed rewrite deletes
the previous receipt and says so, so a receipt never claims bytes it did
not fingerprint. A reinstall rewrites the receipt and a failed update
keeps the old one. Tests never touch the real directory: the suite
sandboxes `receipts_dir`.

`artifact_paths` is the one formula for what a method creates, shared by
install, the receipt and uninstall. Removal deletes the intersection of
the receipt and `artifact_paths`, computed by `plan_removal`. One changed
artifact makes the whole tool non-removable, and a corrupt receipt leaves
it unproven with no layout fallback. `remove_proven` is the one remover
for the CLI and the TUI. It re-hashes at deletion time and deletes the
receipt only once its paths are gone.

A directory artifact is proven by the sha256 of one key file inside it,
never by its device or inode number: the archive member the bin link points
to, or `Contents/Info.plist` for an `.app` bundle, which the installer only
reads (L-19-31). The key file must resolve inside the directory it proves; a
key that leaves the tree through an intermediate symlink is no proof, in the
pass and in the quarantine re-check alike (RR3-01). A changed directory
loses its removal proof but is not broken and does not block an update, which
re-records it; a changed file or
link is broken and refused. `remove_paths` re-hashes every file right before
deleting it, and removes a directory by renaming it to a quarantine sibling,
re-checking the key file inside the captured tree and only then deleting it;
a mismatch is renamed back and refused. An interrupted removal puts the
captured tree back before the interruption leaves; a quarantine sibling that
survives a kill is listed under remove-it-yourself and never deleted by the
installer.

A raw binary that predates receipts is adopted when its sha256 equals the
cached release digest of its asset, the same fetch the pass already makes.
The reason it records is `adopted: the file matches the release checksum`.
A file that does not match stays unproven and says to reinstall with `r`.

`native_index` makes one batched owner query per OS family per pass and
answers the existing per-path probes by lookup. Declared-package queries
are memoized per pass rather than batched into one argv. The uv owner
directory is `uv tool dir`, never `--bin`. A Volta shim resolves to volta,
and a redirect shim is looked through to the real owner.

Every consumer reads the live platform, the update service included
through `live_platform`, so a brew that appears mid-session makes a
brew-only tool installable without a restart. `resolve_owner` re-reads
that platform at mutation time and does not trust the snapshot that gated
the keypress.

`ConfigStep` is the typed fix a misconfigured row carries. The evidence
comes from a dry-run terminal sync (`sync_terminal_shells`, `write=False`,
which blocks the Konsole state write and the `.zshrc` rewrite), from an
incomplete pnpm co-install group, from a skill pack that is partial or
duplicated on a present harness, and from a project pack. Project packs
report global leftovers in all nine harness homes. `PROJECT_HOOK_CONFIGS`
names the hook files that scan reads, and a per-repo install is the step
the row shows. Repo detection covers the runtime dirs verified on this
host, claude and opencode.

The catalog fits an 80x20 terminal. The legend and the detail bar stack
under the table instead of painting over each other, the legend is three
lines of at most 78 cells, and the detail is a fixed three rows.

## Phase 20: one install plan, one engine, one vocabulary

The consent boundary for bookkeeping writes differs by route (L-20-10). The
headless route holds refresh cache saves, receipt adoption and retirement until
the user consents, then commits them before execution; a decline or failed
state check leaves those bookkeeping writes uncommitted. The TUI launches the
catalog without holding writes: launching the catalog is not consent to mutate,
but Enter is consent for the selected mutations, and its decline copy claims
only that nothing started or ran. Commit preserves each write's own race checks.

`build_plan` is pure: it reads published `state_of` values and never probes
or fetches. Its order comes from `Resolution.closure`, which retains the
resolver's deps-first order including present tools; every reached id gets a
`PlanRow` with one disposition and reason. The plan records the first
requester of a dragged dependency, while `render_plan` groups that row under
its requester without changing execution order.

`execute_plan` is the one engine for the TUI and headless paths. It returns
one `RowOutcome` per row, including skipped and blocked rows. `exit_code`,
`retained` and `ran_anything` are pure views of those outcomes, so reporting,
selection retention and post-run effects cannot invent separate result rules.

`WORDS` and `RESULT_WORDS` are the shared vocabulary for review, finished
rows, summaries and headless output; `render.py` owns no competing words.
The finished report starts with `Summary — `, the stable line the container
e2e parser reads. Current installer-owned rows are skipped with the
`(r: reinstall)` hint; only the review's `r` key opts into reinstall.

Zero sudo is structural for repair and update: a native or OS-package owner
that would require elevation is BLOCKED and never escalated. The shared
`update_refusal` predicate informs both the plan and the update engine, so
the review cannot promise an update that the engine refuses.

When state is pending, `_await_state` joins the service's single flight with
the whole catalog; it never starts a parallel refresh or times out. A wait
token fails closed after cancellation. Phase 21's refresh owner replaces
this helper's body, not the review or execution contract.

Phase 20 deleted the obsolete `Summary`/`summarize`, `run_installs`,
`audit.py`, `reapply_post_install`, and the screen's classification and
progress lists. Each duplicated decision path had no remaining production
caller; deleting it follows rule 5 rather than preserving an orphan beside
the plan and engine that replaced it.
