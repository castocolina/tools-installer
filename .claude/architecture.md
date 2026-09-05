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
