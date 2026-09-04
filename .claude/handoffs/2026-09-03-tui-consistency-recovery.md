# Handoff: TUI interaction consistency — recovered & committed, resume on another machine

**Created:** 2026-09-03
**Branch:** `feat/tui-interaction-consistency` (pushed to `origin`)
**Why this exists:** prior session's conversation history was lost; this working tree had a large
amount of uncommitted, unpushed work. This handoff documents what was found, how it was verified,
and what's committed now, so a session on another machine can `git pull` and continue cleanly.

## What happened this session

1. Found the branch already had commits up to `04a6614` pushed and matching `origin` exactly.
2. On top of that, the working tree had ~1200 lines of **uncommitted, unpushed** changes across 25
   files (no other stash/branch held this work — it only existed on disk here).
3. Verified the uncommitted tree first (did not just trust it): `make test` passed (636 tests,
   94.85% coverage) but `make validate` failed on 2 `ruff` line-length violations in
   `installer/tweaks.py`. Fixed those two lines only (mechanical wrapping, no logic change).
4. Committed the recovered work in 3 logical commits (see below), refreshed the stale status report,
   and pushed.

## Commits produced (newest first)

- `chore: add tmp-dir prune utility and GSD planning scaffold` — `scripts/prune-user-tmpdir.sh`,
  `.planning/config.json`.
- `docs: refresh TUI consistency status report; add Codex-compatible AGENTS.md` — appended an
  honest update to `docs/superpowers/2026-06-23-tui-consistency-status.md` instead of rewriting it;
  added `AGENTS.md` (CLAUDE.md mirror for Codex-CLI-style tools, doc links fixed to `.claude/`).
- `feat: numbered wayfinding nav, StrEnum state sets, policy requirements, countdown helper` — the
  bulk of the recovered work; see its commit body for the itemized list. This one commit bundles
  several coupled changes found already in progress together (Task 7 from the plan doc, a
  `StrEnum` hardening pass, Policies-view requirements/detail panel, and a countdown-tweak rewrite)
  — they were too intertwined across the same files to split cleanly without risking a broken
  intermediate commit; the commit body itemizes each piece.

All three commits are individually green: `make validate && make test` pass on the tip.

## Current state of the "TUI interaction consistency" plan

Per `docs/superpowers/plans/2026-06-23-tui-interaction-consistency.md` and the refreshed status
report (`docs/superpowers/2026-06-23-tui-consistency-status.md`), **all 7 tasks are now done**,
including Task 5 (uninstall confirm modal, already landed earlier as `f8f635e`) and Task 6/7
(landed in this session's commits). Read the status report's "Update 2026-09-03" section first —
it corrects an earlier draft that had mismarked Task 5 as pending.

**Closed 2026-09-03 (later in this same recovery session):** ran the real-terminal smoke test that
was the one standing gap — `uv run setup.py` inside `tmux` on this actual machine (not headless).
Confirmed: the numbered nav bar (`[1] Catalog [2] Doctor [3] Uninstall [4] Policies` — note only 4
views now, Fix merged into Doctor per the doctor-catalog-refresh plan), mode badges
(`[STAGED]`/`[AUDIT + APPLY]`/`[STAGED / DESTRUCTIVE]`/`[LIVE]`), the two-zone footer, the Policies
`Requires`/detail panel, and platform-gated tweaks (`apt-upgrade` correctly absent on this macOS
box) all render correctly. Rapid `1 3 2 4 1 2 3 4 1` bursts landed cleanly on `[1] Catalog` — no
wedge. Deliberately navigation-only (never pressed enter/space on Doctor/Uninstall/Policies, which
apply live against the real machine) — quit via `q`, session exited clean.

## Key constraints (unchanged, from CLAUDE.md)

- The coverage gate (`pyproject.toml: [tool.coverage.report] fail_under = 90`) is **90%**, not the
  100% this project ran with historically per prior-session memory — worth double-checking whether
  that was an intentional relaxation. **Closed 2026-09-03:** added `tests/test_wait_time.py` and
  3 tests to `test_tweaks.py`; `wait_time.py` and `tweaks.py` are now both 100%, overall coverage
  94.85% -> 99.87%. Two trivial, pre-existing (not from this recovery) gaps remain:
  `installer/model.py:33` (one error-path line in `_parse_enum`) and `installer/wizard_app.py:73`
  + a branch at `759->exit` (a headless test seam and an unexercised `if not self._navigable()`
  guard) — left alone as out of scope for this session.
- **English only**, coherent commits, `make validate && make test` green before every commit —
  all followed this session.
- `setup.py` stays the untested, pyright-excluded IO boundary (unchanged).

## Other branches present locally (context, not touched this session)

- `feat/dependencies-and-shell-tweaks` — unmerged, kept as-is per `memory/roadmap-status.md`.
- `feat/unified-ui-shared-pattern` — unmerged, superseded by `main` already having unified-UI
  Phases 1–4 plus this branch's follow-on work.
- `main` — has no unpushed commits relative to itself; this branch is the active one.

## Suggested next step

Either: (a) do the real-terminal `make setup` smoke run and close out the plan, or (b) decide on the
90%-vs-100% coverage-gate question above before adding more `installer/` code, since it's a
pre-existing gap this session did not introduce but did notice.
