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
