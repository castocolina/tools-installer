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
