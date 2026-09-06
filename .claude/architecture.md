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
`render_dependency_notice` on the post-TUI path, because a screen with no
`Platform` must not make a judgement it cannot make correctly.

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
judgement made from the registry before anything runs.
`installer/session.py::run_installs` answers the different question of a
dependency that was available and then FAILED while installing, which is
knowable only mid-run. The two share no code and must not be merged: the
resolver is pure and terminal-free, while the failure set exists only for the
duration of one `run_installs` call. A skipped dependent is reported as
`dependency-failed` with the blocking ids on `InstallOutcome.blocked_by`, is
never handed to the install engine, and is always listed in the summary.
`run_installs` is a single forward pass that relies on the resolver's
deps-first order and deliberately does not sort, so `requires` plus
`resolve_dependencies` remains the sole ordering mechanism.

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

The recording mechanism is a `# Verified {date}: ...` prose comment directly
above the `[[tool]]` block it documents (D-01) — never a checked-in excerpt
or snapshot of the verified external source. A comment is lower-friction and
carries no staleness risk from content that changes upstream.

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

