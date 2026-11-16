# Phase 26: Commit and push quality hooks - Discussion Log (standard discuss mode (`--analyze --all --batch`))

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-16
**Phase:** 26-commit-and-push-quality-hooks
**Mode:** Interactive, in standard discuss mode (`--analyze --all --batch`) with the owner. There was no jev
screening: the owner answered every question and sent no item to jev. Quality rule: the best design wins over the
smallest diff (MVP mode inactive).
**Areas analyzed:** push gate mechanism, one source for the gates, path to `main`, related todo; then follow-ups on
target names and the duplicate-code gate.

## Assumptions Presented

The phase ran inline in the orchestrator, since it was a single phase on the interactive path. The analyzer was not
spawned: on that path it runs only when the owner asks for it. Its agent-skills wiring is also not clean.
`gsd-assumptions-analyzer` reads `configured_unresolved`, because `jev-fast-decision` failed the path check ("symlink
escape?"). The fix is re-running `ai-kit-gsd-curated-config`; it blocked nothing here.

| Assumption | Confidence | Evidence |
|---|---|---|
| pre-commit's pre-push entry sees every pushed ref | Wrong | `hook_impl.py:119-174` returns on the first ref with something to push |
| A new branch's first push runs with `all_files` and no stash | Wrong (SPEC Background amended) | `all_files` is set only when the first unpushed ancestor is a root commit (`hook_impl.py:150-159`) |
| pre-commit sets unstaged edits aside at the pre-push stage | Confirmed | `run.py:344` `stash = not args.all_files and not args.files`; `staged_files_only` at `run.py:420-421` |
| `make validate` runs pre-commit, as AGENTS.md says | Wrong | Makefile `validate` calls the six tools directly |
| Tests read only code, not Markdown | Wrong | `tests/test_postinstall.py:608` reads `.claude/architecture.md` and `.claude/skills/*/SKILL.md` |

## jev screening

One jev request per step with open items. On the interactive path, jev screens only the items the owner sends to it.
The owner sent none, so every row is an owner decision.

| Item | jev | Outcome |
|---|---|---|
| Push gate mechanism | none | Owner: own Python pre-push gate that reads every ref (D-01, D-02) |
| One source for the gates | none | Owner: one `make` target and one hook entry per gate; `make validate` aggregates without knowing the gates (D-03 to D-06) |
| Path to `main` | none | Owner: branch push, green CI, fast-forward (D-09) |
| Flaky screen-family todo | none | Owner: folded (D-12) |
| Hook-install target | none | Owner: rename `make install` to `make dev-setup` (D-07) |
| Duplicate-code gate | none | Owner: Backlog 999.17 (D-13) |
| Test target name | none | Owner: keep `make test` (D-03) |
| `make setup` | none | Owner: remove it; `make run` is the wizard (D-08) |
| `make install` alias | none | Owner: no alias; callers updated (D-07) |

## Questions and answers

### Batch 1 (four areas)

1. **Push gate mechanism.** Options: own script then pre-commit (recommended) / pre-commit's own pre-push hook.
   **Owner:** "Shouldn't make setup (replacing make install) be what installs the Python pre-push lib, and from there
   configure it so commit/push trigger everything?" This was read as a request for an own Python gate. Follow-ups 1
   and 2 confirmed it.
2. **One source for the gates.** Options: `make validate` runs pre-commit (recommended) / two lists plus a parity
   test. **Owner:** each gate gets its own `.pre-commit-config.yaml` entry, so a failure is clear. Each gate also gets
   a `make` target for manual runs (`make unit-test`, `make format-check`, `make duplicated-check`, ...). `make
   validate` calls them all without knowing what they are. Agents re-run only the gate that failed, and run validate
   only to verify a whole plan or phase. → D-03, D-04, D-05, D-06.
3. **Path to `main`.** **Owner:** branch push, CI, fast-forward `main` (recommended). → D-09.
4. **Flaky todo.** **Owner:** fold it in. → D-12.

### Batch 2 (follow-ups 1 to 4)

1. **Which target installs the hooks?** The question explained that `make setup` is the product wizard, and AGENTS.md
   forbids running it on the host. **Owner:** "Rename install to dev-setup; what you call make setup is really a
   make run." → D-07, D-08.
2. **Own Python gate?** **Owner:** yes. → D-01.
3. **Duplicate-code gate?** **Owner:** backlog item (recommended). → D-13.
4. **Test target name?** **Owner:** keep `make test` (recommended). → D-03.

### Batch 3 (follow-ups 5 and 6)

5. **What happens to `make setup`?** Options: `run` primary with a hidden `setup` alias (recommended) / remove `make
   setup`. **Owner:** remove it. → D-08.
6. **Keep a `make install` alias?** **Owner:** no alias; update the callers (recommended). → D-07.

## Live facts that changed the plan

- pre-commit reads only the first pushed ref (`hook_impl.py:119-174`). The R3 "pushed commit is not HEAD" refusal
  cannot be enforced from inside a pre-commit hook, which led to D-01.
- pre-commit uses `all_files` only for a root push, which amended the SPEC Background.
- `make setup` is printed by product code (`installer/guidance.py`, `installer/compose.py`, `setup.py`) and pinned by
  tests. Removing it (D-08) is a product message change, not a doc-only rename.
- The suite takes 62.3 s and validate 12.1 s, measured at HEAD `ae9b99b0`. The SPEC carries this.

## Corrections Made

- SPEC Background: `all_files` happens on a root push only, and pre-commit reads only the first pushed ref (dated
  amendment).
- SPEC R1, R2, R4: per-gate targets, per-gate push entries, `make dev-setup` (dated amendments). The edge floor gained
  4 R2 rows, all resolved; `edge_floor.py check` is green.
- REQUIREMENTS.md: HOOK-01..06 added (121 total). ROADMAP Phase 26: goal, requirements and success criteria amended.
  Backlog 999.17 added.

## External Research

None. Every fact came from the installed pre-commit 4.6.0 source, the repo, and live timings.
