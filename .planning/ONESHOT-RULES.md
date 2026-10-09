# ONESHOT PLAYBOOK - tools-installer v1 Claude Code Autonomous Run

**DRAFT — not yet reviewed or run.** Adapted from the `ssh-git-config` /
gitid v1.0 playbook structure, rewritten for this project's actual domain and
risk surface. Do not treat any specific number, path, or rule below as final
until reviewed.

## Starting Point

Determine `--from` at invocation time, not from a hardcoded phase number: read
`ROADMAP.md` and `STATE.md` and use the earliest phase that is not
`phase_complete`. `gsd-autonomous`'s own resume gates (phase-discovery
filtering in `autonomous.md`, plan/wave `has_summary` filtering and the
missing-`VERIFICATION.md` fallback in `execute-phase.md`) already reconcile a
partially-finished phase — including one whose plans are all summarized but
never reached verification, or that surfaces `gaps_found` requiring one more
planning pass. Do not hand-run a phase's closeout procedure; let the same
Per-Phase Checklist below apply to whichever phase is earliest-incomplete.

## Per-Phase Checklist

For every phase, confirm all of these before moving to the next phase — do
not assume any of them ran just because the previous one did:

1. Discuss — `{N}-CONTEXT.md` exists and reflects the phase
   (`workflow.discuss_mode: "discuss"`, `skip_discuss: false` in
   `.planning/config.json` — this is not optional per phase).
2. Plan — `PLAN.md` file(s) exist for every wave, and every single `PLAN.md`
   has `cross_ai: true` in its frontmatter. This is non-negotiable: no plan
   may be created, replanned, or gap-closed without it. Add it immediately if
   a planner omitted it — never proceed to review or execution with a plan
   missing this field.
3. Plan review convergence — REVIEWS.md shows 0 HIGH concerns
   (`workflow.plan_review_convergence: true`,
   `review.default_reviewers: ["opencode-plan-review"]` in
   `.planning/config.json`).
4. Execute — every wave's SUMMARY.md exists, tree is clean, `make test`
   green. Confirm cross-AI delegation was actually used per Rule 12 below,
   not a direct on-session executor dispatch, unless a recorded per-plan
   fallback applies.
5. Code review — REVIEW.md shows clean or all findings fixed
   (`code_review_depth: "deep"`, `model_overrides.gsd-code-reviewer: "opus"`).
   **Also dispatch a codex-sol-high pass over the same diff, in parallel
   with the internal opus-based `gsd-code-reviewer`** (Rule 15) — GSD's
   `/gsd-code-review` has no native multi-reviewer surface like
   plan-review-convergence does, so this is a manual second lane, not a
   config flag. Any Critical/High finding it raises gets fixed or
   explicitly deferred through the same fix loop as the internal reviewer's
   findings before this checklist item is considered satisfied.
6. Verify-work — VERIFICATION.md shows `passed` (or a resolved
   `human_needed`/`gaps_found` outcome, not left open).
7. UI review — for any phase touching a Textual TUI surface (at minimum
   Phases 2, 3, 7, 8, 10 per the current ROADMAP — re-check against the live
   ROADMAP, this list can go stale): run the setup wizard for real inside
   `tmux` on the actual machine (`uv run setup.py`, or `make setup`), not just
   the headless Textual test pilot. This is a **structural/text check**
   (nav labels, mode badges, footer text via `capture-pane`), not a visual
   judgment call — a monospace TUI's correctness is string-matchable, so
   Claude verifies it directly with no human and no container (Rule 14).
   Navigation-only: never press the key that commits an install, uninstall,
   or PATH-repair action during this check (Rule 5). See Non-Negotiable
   Rule 8 for what a passing check looks like structurally.
8. `/gsd-audit-uat` — run it yourself. Nothing above triggers it
   automatically; treat it as a required step, not a periodic extra.
9. `codegraph sync` on entering a new worktree and after every task or wave
   (`.codegraph/` exists at repo root). Use `codegraph_explore` before
   grep/find or reading files to locate symbols.

Only close a phase and advance once every applicable item above is
evidenced.

## Non-Negotiable Rules

1. Read `AGENTS.md` and `.claude/*.md` (architecture, python-tooling,
   testing, git-workflow, dev-environment) before planning or implementation.
   Generated artifacts, code, comments, and commit messages are English-only
   — per `CLAUDE.md`'s "English only" rule.
2. Never use `--no-verify`, and never silence a lint/type/security/coverage
   gate to make it pass — per `CLAUDE.md`'s "never bypass a quality gate."
   Keep implementation, tests, and documentation for one logical change in
   the same commit.
3. Continue autonomously through ordinary implementation, review, testing,
   planning, and commit work. Do not stop simply because a previous executor
   lacked subagent access; the orchestrator must perform the omitted gate.
4. Do not discard a dirty worktree to begin or complete a phase. Classify
   each path with Git evidence: commit active project work, ignore only
   reproducible local output (e.g. `.venv/`, build artifacts), and delete
   only stale output with no active repository role.
5. **Never mutate this machine's real `~/.myshellrc`, `~/.zshrc`,
   `~/.bashrc`, or other real shell rc files, and never run a real
   install/uninstall against a real system/user/ai-tier tool on this actual
   machine.** There is no mid-run confirmation gate for this — see Rule 14
   for why an autonomous run should never need one. Tests default to an
   isolated `HOME` (`monkeypatch.setenv("HOME", str(tmp_path))` — see
   `tests/test_locations.py` for the existing pattern) — every new test
   touching shell-rc or install paths must follow it, never the real `HOME`.
   `make setup`/`make fix`/`make uninstall` invoked for the UI-review step
   (Checklist item 7) is navigation-only: never press the key that commits an
   install, uninstall, or PATH-repair action against this real machine during
   an autonomous run — observe the rendered UI, then quit.
6. At every wave and phase close, independently run `make validate` and
   `make test`. Do not accept an executor's unverified claim; `make validate
   && make test` must pass on the exact tree before it's committed, per
   `CLAUDE.md`.
7. A new registry method `kind`, executor, or resolver rank added in any
   phase must ship with the matching test additions in the same commit
   (mirrors the `sdkman` kind's existing test coverage across
   `tests/test_model.py`, `tests/test_executors.py`, `tests/test_resolve.py`,
   `tests/test_registry.py`, `tests/test_status.py` — same shape, new kind).
8. `tools-installer` is a Textual TUI, not a web UI — `gsd-browser`
   (Chrome DevTools Protocol) does not apply. "UI review" and
   Definition-of-Done for a TUI-surface phase mean the wizard is exercised
   through a real terminal session (`tmux` `send-keys`/`capture-pane` against
   the actual `uv run setup.py` process — see
   `.claude/handoffs/2026-09-03-tui-consistency-recovery.md` for the
   precedent), never only the headless Textual test pilot
   (`textual.testing`/`Pilot.press`) — a prior session found the pilot alone
   masks burst/timing bugs a real terminal surfaces. A unit or wiring test
   never substitutes for this.
9. Stop only for a destructive anomaly, an unrecoverable tool/authentication
   failure, or a circuit breaker. There is deliberately no "required
   confirmation" stop condition for shell-rc mutation or real
   install/uninstall — Rule 14's container tier exists precisely so that
   class of verification never needs one. `gate="blocking-human"` (per
   `gsd-core/references/checkpoints.md`) is reserved for a situation the
   container tier genuinely cannot cover — expected to be rare-to-never in
   this project's scope. Record the exact blocker and preserve all green
   work.
10. When verification, code review, UI review, UAT audit, or independent
    evidence review finds a functional, workflow, safety, or interaction gap,
    fix it autonomously: create or revise the smallest corrective plan,
    implement it test-first, rerun every affected gate, and obtain a fresh
    independent review. Repeat this loop until the relevant reports are clean
    and the phase checklist is evidenced. A failing test, review finding,
    incomplete artifact, stale evidence, or an agent's failed attempt is work
    to fix, not a blocker. Stop only for rule 9 safety conditions or a
    demonstrable repeated zero-progress tool failure; record the evidence for
    that stop.
11. Plan-review convergence remains mandatory for every new or revised plan:
    resolve all functional, workflow, safety, and interaction HIGH findings
    before execution. `workflow.plan_review_convergence: true` and
    `review.default_reviewers: ["opencode-plan-review"]` in
    `.planning/config.json` drive this — do not disable either to unblock a
    stuck run; fix the underlying finding instead.
12. **Every `PLAN.md` must carry `cross_ai: true` in its frontmatter — this
    is non-negotiable, with no exceptions and no alternative path.** Plan
    EXECUTION is delegated to cross-AI, never run on this session's own token
    budget. `workflow.cross_ai_execution` is `true` in `.planning/config.json`
    specifically so `/gsd-execute-phase` routes each plan to whatever
    external command `workflow.cross_ai_command` currently resolves to in
    `.planning/config.json` (read it live — don't assume a past value still
    holds) instead of spawning a `gsd-executor` subagent on this Claude
    session. The config flag alone does not activate
    delegation — `execute-phase.md`'s `cross_ai_delegation` step also
    requires the plan's own frontmatter `cross_ai: true` (Checklist item 2
    above). A plan is not considered planned until this field is present; do
    not advance a plan to review or execution without it. Only fall back to a
    direct `gsd-executor` dispatch on this session when the cross-AI command
    demonstrably fails for that specific plan (record the failure) — never
    as the default path, and never because adding the field was skipped.
13. **Every executor uses `codegraph_explore` before Grep/Read** when
    `.codegraph/` exists at repo root. Before dispatching any
    exploration-heavy role (new worktree, new subagent, new phase/wave), run
    `codegraph index || codegraph init -i` yourself — don't assume the index
    is fresh. Restate the `codegraph_explore`-first instruction inline in
    every cross-AI dispatch prompt — an external model does not reliably act
    on policy it only sees via a referenced file in its required reading.

14. **Three verification tiers — pick the right one, never stop for the wrong reason.** `.planning/config.json` already has `workflow.human_verify_mode: "end-of-phase"`: GSD's own planner suppresses mid-flight `checkpoint:human-verify` tasks and its executor auto-approves any `gate="blocking"` checkpoint in autonomous mode (`gsd-core/references/checkpoints.md`) — only `gate="blocking-human"` ever stops an autonomous run. Combined with this project's real risk surface (Rule 5), that means:
    - **Tier 1 — sandboxed automated tests (`make test`).** Already fully isolated (`monkeypatch.setenv("HOME", str(tmp_path))`, confirmed by the existing `test_real_home_rc_files_are_untouched`). Never touches the real machine. Run freely, no gate of any kind.
    - **Tier 2 — TUI structural checks (Checklist item 7).** A monospace Textual TUI's correctness (nav labels, mode badges, footer text) is verified via `tmux` `capture-pane` **text** matching, not a screenshot/visual judgment call — Claude does this itself. Stays navigation-only (Rule 5), so nothing mutates. No gate needed.
    - **Tier 3 — real-machine-effect verification.** Anything that needs to prove an installer/tweak/uninstall genuinely works against a real filesystem (not the Tier-1 simulation) — e.g. Oh-My-Zsh's real `.zshrc` rewrite, `sdk install java` actually pulling a JDK, a real uninstall sweep leaving no stray files — runs inside a disposable container. **This project targets both Linux and macOS, on multiple architectures, so this rule names no single runtime — the choice of runtime is a per-machine fact, not a project-wide constant.** Before Tier 3 is first needed in a run, detect what's actually available on *this* machine, in this preference order:
      1. **A native container CLI already on PATH** — `podman` or `docker`, whichever is present (`command -v podman`, `command -v docker`). On native Linux, `podman` runs rootless with no VM layer and is the simplest option when present — prefer it over a VM-backed runtime.
      2. **A VM-backed Docker CLI** (e.g. `colima` + `docker` on macOS) when no native option is on PATH. Start the VM (`colima start`) if the CLI is present but not running; install the CLI only if it's genuinely missing on *this* machine — never because a past run on a different machine needed it.
      3. If neither materializes, this is a real blocker (Rule 9) — record exactly what was checked and why, rather than silently falling back to testing against the real host.
      Whichever runtime is selected, confirm it works end-to-end once (a trivial container run, e.g. `alpine echo ok`, with the `--rm`-equivalent flag) before relying on it, and record which runtime this run actually used in the verification evidence — a future run on a different machine may pick a different one, and that's expected, not a regression. Docker-in-docker/podman-in-podman is not needed: this session runs directly on the host, not inside a container itself, so one level of isolation is sufficient. Capture the evidence (command output, resulting file diffs, `tmux capture-pane` text from inside the container) and fold it into the phase's end-of-phase UAT/verification report per `human_verify_mode: end-of-phase`'s existing consolidation design, so the single human review at the end of the run (or milestone) has real evidence to look at — never a mid-run stop to ask for it.
    - **Known gap to route into GSD, not silently patch:** `REQUIREMENTS.md`'s `REQ-linux-bazzite-shell-parity` (Phase 7) assumes `podman` is this project's cross-platform container-runtime catalog entry. Whether that holds is a fact about the *end user's* machine and architecture, not about this run's own verification host — on Intel macOS, `podman`'s Homebrew formula has historically pulled in an Apple-Silicon-only dependency (`vfkit`) and failed to build (hit live on a prior run, on that machine); on native Linux (confirmed live on this run's own host) `podman` installs and works natively with no such issue. This is a real product-catalog finding, not just a ONESHOT-rules concern — flag it for the user to decide whether `registry.toml`'s `podman` entry needs an OS/arch gate or a documented fallback, rather than silently reworking the catalog here.

15. **Code review (Checklist item 5) gets a codex-sol-high pass, run in
    parallel with the internal opus-based `gsd-code-reviewer`, not in
    place of it.** User-added 2026-09-05: plan-review already has its own
    multi-reviewer convergence mechanism (`gsd-plan-review-convergence`,
    `review.default_reviewers` in `.planning/config.json`) — that part
    needed no new rule. What was missing is that `/gsd-code-review` has no
    equivalent multi-reviewer surface at all (searched
    `gsd-core/workflows/code-review.md` and the full `gsd-core` tree — the
    only external-reviewer hook found, `workflow.code_review_command`, is
    wired into `/gsd-ship`, a different lifecycle stage, not the per-phase
    code-review step this playbook's Checklist item 5 uses). So this is a
    manual second lane the orchestrator runs itself, not a config flag:
    - Spawn `gsd-code-reviewer` and the codex-sol-high pass **in parallel**
      over the SAME diff (same base/head SHAs) — feed the codex pass the
      diff, the plan's `<threat_model>`/acceptance criteria, and this
      project's `CLAUDE.md`/`.claude/*.md` rules, and ask for
      Critical/High/Medium/Low findings in the same shape `gsd-code-reviewer`
      uses.
    - Reachability check before trusting the pass:
      `codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"' '...'`
      and confirm `model: gpt-5.6-sol` / `reasoning effort: high` in the
      banner. Resolve the `codex` binary via PATH (`command -v codex`) —
      never hardcode a path; its location and the installed codex-cli
      version vary by machine and user. Run this reachability check live at
      the start of each run that needs this lane — a pass on one
      machine/session does not carry forward to another.
    - Fold its findings into the SAME fix loop as the internal reviewer's —
      a Critical/High finding from either lane must be fixed or explicitly
      deferred/rejected with reasoning before Checklist item 5 counts as
      satisfied. Record which lane raised which finding in the phase's
      review record so a future reader can tell internal vs. codex-sourced
      findings apart.
    - This duplicates effort deliberately (two independent code reviews per
      phase) — one reviewer's blind spot should not silently mean a phase
      shipped with only one set of eyes on it.

## Cross-AI Execution — Verified Behavior of the `opencode run` CLI Shape

`workflow.cross_ai_command` in `.planning/config.json` is this project's live source of truth for which command/model Rule 12 dispatches to — it has already changed once since this playbook was first drafted (model and binary resolution both moved on), so **never quote a specific command/model string here as current; always read it live from `.planning/config.json` at run time.** The findings below are about `opencode run`'s CLI behavior itself (stdin prompt, stdout redirected to a real file, matching `execute-phase.md`'s `> "$CANDIDATE_SUMMARY"` invocation shape) and should hold regardless of which model is configured — but re-run the reachability + output-shape check once per run rather than trusting a past date, since the configured command can change between runs or machines:

- **Real tool use (file writes) executes non-interactively with no `--auto` flag and no hang** — `opencode run` does not gate on a TTY permission prompt the way an interactive session would. This means cross-AI execution already has full non-interactive write access to the working tree regardless of `--auto` — the same permission-bypass caveat as any other unattended agent, not something `--auto`'s absence protects against.
- **Stdout redirected to a real file (not a pipe/terminal) is clean plain markdown** — no ANSI escape codes, no banner chrome. That noise only appeared when testing interactively through a piped terminal capture; it does not occur in GSD's actual file-redirect invocation. **Do not add `--format json` to this command** — it was tried and reverted: it turns the clean markdown `SUMMARY.md` content into a stream of JSON event objects, which fails `execute-phase.md`'s "has at least a heading and description" validation.
- Conclusion: `cross_ai_command`, whatever it currently resolves to, needs no special-casing in this playbook and is safe to rely on for Rule 12 as long as it keeps this same stdin-prompt/stdout-to-file shape.

## Milestone Close

After Phase 12, run cross-phase integration checks and `make validate && make
test` one final time. Commit `.planning/RUN-REPORT.md` with per-phase
verification evidence — including every Tier-3 container-verification result
from Rule 14, so the user's one end-of-run review pass has everything in one
place — and remaining human handoff items (at minimum: the still-open `mmdc`
install-method decision, `REQ-mmdc-install-decision`, if it was resolved by
research rather than by the user directly). Tagging a release remains a
human decision.
