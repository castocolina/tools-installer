# Unified UI Redesign — Phase 4: Policies Tab — Design

Date: 2026-06-15
Status: approved (design approved in terminal)
Source roadmap: `docs/prds/unified-ui-redesign-v1.0-prd.md` (Phase 4)
Builds on: `docs/superpowers/specs/2026-06-14-unified-ui-phase3-design.md`

## Goal

Make the pip/npm ban a first-class, **toggleable** Policies tab inside the unified
app — distinct from the package catalog — and retire the post-install
"Enable the pip/npm ban?" questionary prompt. The tab introduces a **generic
policy model** parallel to `Tool` (the ban is its first and only instance) so
future environment tweaks slot in with no screen changes. Toggling a policy
**applies live, in place** (mirroring Phase 2's `FixScreen` and Phase 3's
`UninstallScreen`), then re-renders a concise per-layer status with reload
guidance. Execution composes the existing pure `guards.py` removers/installers —
no new ban logic.

## Decisions (user-approved)

1. **Live-apply in-view (like `FixScreen` / `UninstallScreen`).** Toggling a row
   calls the policy's `apply`/`remove` closure synchronously (cheap, idempotent
   file IO — no Textual worker), then re-renders. The app's run value stays the
   catalog selection (`list[str] | None`); the tab mutates the filesystem
   directly and returns nothing through `run()`. Same narrow un-parking of the
   "operador en vivo" fork Phases 2–3 used.
2. **Keep the ban toggle in the Uninstall view.** Uninstall stays a one-stop
   tear-down (tools + ban + PATH together); the Policies tab adds enable/disable
   plus status. Two idempotent paths to remove the ban is safe and avoids churn
   in the shipped, UX-approved `UninstallScreen`.
3. **Generic `Policy` abstraction now.** A reusable frozen `Policy` (id, label,
   description, snapshot `active`, `apply`/`remove` closures returning a per-layer
   `PolicyResult`) seeded with the ban. The screen iterates a `list[Policy]`
   generically; the PRD explicitly requires accommodating future env tweaks.
4. **Concise per-layer status summary.** After a toggle, one line per layer
   (Shims, Aliases) plus the reload-guidance line and any PATH-order warning —
   the multi-line applied-summary style Phase 3 settled on (not a verbose
   per-command × per-layer breakdown).
5. **Interactive `--guard` / `--unguard` open the app on the Policies view.**
   Consistent with Phase 2/3 (`--doctor`/`--fix`/`--uninstall` open their views
   interactively). Non-TTY and `--yes` keep the imperative console `run_guard`
   contract **unchanged** — the headless path never launches the app.

### Why the return contract does NOT change

The toggle runs live in the view and mutates the filesystem directly; the app
still returns only the catalog selection. No typed decision-set outcome is pulled
forward (consistent with Phases 2–3).

## Design

### 1. Pure model — new `installer/policy.py`

```python
@dataclass(frozen=True)
class PolicyLayer:
    name: str       # "Shims" | "Aliases"
    detail: str     # "3 active in ~/.local/bin" | "written to ~/.myshellrc"

@dataclass(frozen=True)
class PolicyResult:
    layers: tuple[PolicyLayer, ...]
    reload_hint: str | None     # "Open a new shell or run `hash -r` …"; None when N/A
    warning: str | None         # guard_path_warning output on apply; None otherwise

@dataclass(frozen=True)
class Policy:
    id: str
    label: str
    description: str
    active: bool                          # snapshot for first render
    apply: Callable[[], PolicyResult]
    remove: Callable[[], PolicyResult]
```

A pure factory composes the ban from the existing `installer/guards.py` seams:

```python
def ban_policy(
    *,
    shim_dir: Path,
    apply_rc_paths: list[Path],
    remove_rc_paths: list[Path],
    path_value: str,
    which: Callable[[str], str | None],
) -> Policy: ...
```

- `active` snapshot = `any(guard_status(shim_dir).values())` (queryable status).
- `apply()` = `install_shims(shim_dir)` + `write_ban_aliases(p)` for each
  `p in apply_rc_paths`; returns a `PolicyResult` with:
  - **Shims** layer: count of created/refreshed shims in `shim_dir`, noting any
    `skipped (real binary here)` honestly (e.g. "2 active in ~/.local/bin
    (1 skipped — real binary present)").
  - **Aliases** layer: "written to `<apply_rc_paths>`".
  - `reload_hint`: "Open a new shell or run `hash -r` so cached command paths
    refresh."
  - `warning`: `guard_path_warning(shim_dir, path_value, which)` (or None).
- `remove()` = `remove_shims(shim_dir)` + `remove_ban_aliases(p)` for each
  `p in remove_rc_paths` (the **union** of locations, so disabling leaves no
  stragglers regardless of the original link mode); returns a `PolicyResult` with
  the Shims/Aliases layers describing the removal, `reload_hint` set, `warning`
  None.

Fully covered against `tmp_path`: no real home, no console. The factory owns the
guards composition (testable), mirroring how `app.perform_uninstall` composes the
removers for Phase 3.

### 2. `installer/wizard_app.py` — `PoliciesScreen` + `PolicyInputs`

- `PolicyInputs(policies: list[Policy])` — a small frozen dataclass bundling the
  screen's inputs, so `UnifiedApp.__init__` gains one required kw-arg
  (`policies: PolicyInputs`) rather than a loose list. Mirrors `UninstallInputs`.
- `PoliciesScreen(Screen[None])` replaces the `"policies"` `PlaceholderScreen` in
  `UnifiedApp._views`.

**Layout** — mirrors `UninstallScreen`:
- A single `DataTable` (State / Policy / Effect), one row per `Policy`, keyed by
  `policy.id`. The State cell shows `[on]`/`[off]`. The ban row is styled
  `bold yellow` with a `shell config:` prefix in the Effect column (the Phase 3
  package-vs-config distinction the `ui-ux-designer` already approved).
- A `#policies-status` `Static` with `height: auto` (un-docked) above a
  `Footer()` — avoids the Phase 3 bottom-dock overlap that hid the applied
  summary. The status renders the multi-line `PolicyResult` summary.

**State (public test seams)**: `active_state: dict[str, bool]` (policy id → live
on/off), `status_text: str`, `error: str | None`, following the Phase 1–3
public-seam convention.

**Bindings**: `enter` toggles the **highlighted** policy (applies live);
navigation stays the unified scheme (number keys / `Ctrl+P`); no `q`
(consistent with Doctor/Fix/Uninstall). `space` is intentionally **not** bound to
a toggle here: there is no select-then-apply step (every toggle is immediate), so
overloading `space`'s "harmless select" meaning from the catalog/uninstall views
would be a footgun. `enter` is the single, deliberate action key.

**Flow**: highlight a row, press `enter`. If the policy is active call
`policy.remove()`, else `policy.apply()`; flip the State cell and the
`active_state` entry; render the returned `PolicyResult` into `#policies-status`
as a concise multi-line summary (one line per layer + the reload hint + any
warning). Idempotent both directions — re-toggling restores the prior state.

**Error path**: wrap the closure in `try/except OSError` exactly like
`FixScreen.action_apply` / `UninstallScreen.action_remove` — set `error`,
re-render "what failed / what to try", leave the row retryable, never crash
(PRD: a failed core action surfaces, never a silent failure).

**No empty state**: the ban policy always exists, so the tab is never empty
(unlike Uninstall). There is always at least one toggleable row.

### 3. `setup.py` (IO boundary, coverage/pyright-excluded)

- `_build_app` constructs the ban policy with real paths and threads it in:
  ```python
  policy_inputs = PolicyInputs(policies=[
      ban_policy(
          shim_dir=_DEFAULT_BIN_DIR,
          apply_rc_paths=_ban_rc_paths(link_mode),
          remove_rc_paths=_all_ban_rc_paths(),
          path_value=os.environ.get("PATH", ""),
          which=shutil.which,
      )
  ])
  ```
  passed as `policies=policy_inputs`; `_views["policies"]` becomes
  `PoliciesScreen(policy_inputs)`.
  - Enabling writes aliases to `_ban_rc_paths(link_mode)` (centralized default →
    `~/.myshellrc`, matching the rest of `_build_app`); disabling cleans
    `_all_ban_rc_paths()` (the union — both rc files + `~/.myshellrc`).
- **Remove the post-install prompt** (`setup.py:403-412`) and the now-dead
  `_ask_optin` helper (vulture would flag it; it has no other caller). The
  empty-selection-then-ban-prompt confusion the PRD calls out disappears.
- **Wire the interactive guard branch.** `_run_guard` (or its caller in `main`)
  gains: `if sys.stdin.isatty() and not assume_yes: _build_app(...,
  initial_view="policies").run(); return 0`. Non-TTY / `--yes` keep the
  unchanged console `run_guard`. Mirrors `_run_uninstall`'s interactive branch.

### 4. Navigation & CLI flags

- `VIEW_ORDER` and the dual-route dispatch (`show_view`, palette + number key
  `5`) are unchanged from Phase 1; `"policies"` simply resolves to a real Screen
  now. The `_navigable()` guard and the `[catalog]` / `[catalog, <one view>]`
  stack invariant are preserved.
- `initial_view="policies"` lets interactive `--guard`/`--unguard` open the app
  on this view.
- Non-interactive `--guard` / `--unguard` / `--yes` / no-TTY → unchanged console
  `run_guard`; the app is never launched.

## Testing (headless, 100% core retained)

- **`policy.py`** (pure, 100%, table-driven, `tmp_path`):
  - `ban_policy.active` reflects `guard_status` (true when a shim is present,
    false on a clean dir).
  - `apply()` writes shims + aliases and returns Shims/Aliases layers, the reload
    hint, and a warning when the shim dir is absent from `path_value`; the
    `skipped (real binary here)` case is surfaced in the Shims detail.
  - `remove()` clears shims + aliases over the union and returns the removal
    layers; idempotent (second call is a no-op that still reports cleanly).
- **`PoliciesScreen`** via `app.run_test`: `enter` toggles the highlighted policy
  off→on→off against **`tmp_path`** (never real home); the State cell and
  `active_state` flip; the per-layer summary renders; `OSError` → `error` state,
  no crash. NBSP-aware screenshot decode (`html.unescape(...).replace(chr(160),
  ' ')`) when asserting multi-word guidance phrases.
- **Navigation**: policies reachable via palette **and** number key `5` resolve
  to the same screen; `initial_view="policies"` opens on it; `Ctrl+C` aborts
  (exit 130 at the root).
- **`setup.py`** stays the coverage/pyright-excluded IO boundary.

### Agent-driven E2E + agent UX evaluation (per the user's request)

- **E2E correctness/safety gate** (`tests/test_policies_e2e.py`): drive a real
  `PoliciesScreen` with `ban_policy(shim_dir=tmp/bin, apply_rc_paths=[tmp/.zshrc],
  remove_rc_paths=[tmp/.zshrc])` under `monkeypatch.setenv("HOME", tmp_path)`.
  Assert the real `~/.local/bin`, `~/.zshrc`, `~/.bashrc`, `~/.myshellrc` are
  **byte-identical before/after** the whole suite; assert the sandbox shims +
  alias block appear after enable and vanish after disable. Capture journey
  screenshots (`.e2e-artifacts/policies/…`) for the UX agent.
- **UX evaluation** (`ui-ux-designer` agent, end-user lens): critique the tab
  screenshots (clarity of on/off state, the per-layer summary, reload guidance,
  key hints). FIX-FIRST loop until **SHIP**, exactly as Phase 3.

## Out of scope (deferred / parked)

- Live in-UI execution of **installs** — still parked; only fix (Phase 2),
  uninstall (Phase 3), and policy toggles (here) run live, all cheap IO.
- Additional policies beyond the ban (future env tweaks). The model is generic so
  they require no screen changes, but none are added in Phase 4.
- Changing the console `run_guard` contract (it stays the non-interactive path).
- Typed decision-set return outcome — not needed; toggles run live.

## Acceptance (Phase 4 subset of the PRD)

- [ ] A first-class "Policies" tab lists the pip/npm ban as an on/off toggle,
  visually distinct from package rows, reusing `installer/guards.py`.
- [ ] Toggling applies/removes both layers (shims + aliases) live, reports
  per-layer status independently, and shows the reload guidance; a failed toggle
  surfaces in place (never silent).
- [ ] Reachable via palette + number key and via interactive `--guard` /
  `--unguard`; non-interactive paths behave exactly as before; the app is not
  launched without a TTY.
- [ ] The post-install "Enable the pip/npm ban?" questionary prompt is removed
  from `setup.py`; the empty-selection-then-ban-prompt confusion is gone.
- [ ] `make validate && make test` green on the exact committed tree; 100%
  coverage retained on the `installer/` core; English-only; coherent commits.
