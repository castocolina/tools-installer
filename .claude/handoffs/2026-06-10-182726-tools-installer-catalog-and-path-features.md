# Handoff: tools-installer — catalog expansion + PATH-management features

## Session Metadata
- Created: 2026-06-10 18:27:26
- Project: /Users/ramon/git/personal/tools-installer
- Branch: main
- Session duration: long (multi-feature session)

### Recent Commits (for context)
  - be0c2c7 docs: list gitleaks, vale, broot in the tool catalog
  - 36fe508 feat: add broot via selective-zip extraction (registry 46->47)
  - acfcbe9 feat: extract only the member from .zip archives (selective unzip)
  - 51a46f5 feat: add gitleaks and vale (x64/bits arch tokens; registry 44->46)
  - c33fe07 feat: add x64 and bits arch tokens for gitleaks/vale-style assets

## Handoff Chain

- **Continues from**: None (fresh start)
- **Supersedes**: None

## Current State Summary

`tools-installer` is an interactive cross-platform (macOS / Linux) installer for an AI dev environment, Python managed by **uv**. This session delivered, in order: (1) a converged executor feature — tempfile archive extraction that closed the `curl|tar` pipefail bug + `.zip` support + `member` templating + a registry-driven `make uninstall`; (2) **Registry Batch 4** (deno, procs, ast-grep, jless on the `.zip` path); (3) the **script-installer tier** (bun, pnpm, fnm via official installers) + a **shell-rc link-mode preference** (centralized/single/split) + **PATH hygiene** (post-install audit + cleaning the duplicate `export PATH` lines installers append to rc files), decomposed as SP1/SP2/SP3; (4) **Registry Batch 5** (x64/bits arch tokens → gitleaks, vale; selective-zip extraction → broot). Everything is committed to **`main`**, the tree is clean, **244 tests pass at 100% coverage**, and `make validate` is green. **Nothing has been pushed** — the repo has no remote, by the user's standing instruction. The registry now has **47 tools**.

## Codebase Understanding

## Architecture Overview

- **Declarative registry → resolver → engine.** `installer/registry.toml` is the single source of truth (one `[[tool]]` per tool, each with `[[tool.method]]` blocks). `installer/resolve.py` orders a tool's methods by a priority ladder — script(10) → github_release/tarball(20) → native dnf/apt/pacman(30) → rpm_ostree(35) → brew(40) — and applies each method's `os` filter (a method with no `os` applies on every platform). `installer/engine.py` walks the resolved methods, falling through to the next on failure (this is how brew backstops asset gaps).
- **Executors are "argv → Runner".** `installer/executors.py` (script/native/brew) and `installer/download.py` (github_release/tarball) build command vectors and hand them to an injected `Runner`. Tests mock the Runner and assert exact argv — this is why the suite is offline and deterministic. **Preserve this pattern.**
- **Userspace install policy.** Archives unpack into `~/.local/opt/<binname>/` with the binary symlinked into `~/.local/bin`; raw single-file assets go straight into the bin dir. `installer/locations.py` owns these paths.
- **`setup.py` is the composition root** — it does the real questionary/terminal IO and home-path wiring, and is deliberately **excluded from pyright and coverage** (it imports untyped questionary). It IS ruff lint/format-gated. Everything testable lives in `installer/`.

## Critical Files

| File | Purpose | Relevance |
|------|---------|-----------|
| `installer/registry.toml` | The tool catalog (47 tools) | Adding a tool = one entry here |
| `installer/download.py` | github_release/tarball executor; tempfile extraction; `.zip` (selective) + tar.gz + raw; `member`/`asset` templating | Touched heavily this session |
| `installer/assets.py` | `ArchTokens` (machine/deb/go/suffix/**x64**/**bits**) + `render_asset` templating | New x64/bits tokens added |
| `installer/uninstall.py` | Registry-driven `plan_uninstall`/`remove_paths` (NEW this session) | `make uninstall` |
| `installer/rcclean.py` | Find/strip duplicate PATH-export lines in rc files (NEW this session) | PATH hygiene |
| `installer/shellrc.py` | `~/.myshellrc` management; `write_managed_path` (inline), `remove_managed_block`, `collect_bin_dirs` | link modes |
| `installer/app.py` | Orchestrators: `run_wizard`, `configure_path` (link_mode), `run_doctor` (link_mode), `run_uninstall`, `clean_rc_duplicates` | composition seams |
| `installer/cli.py` | Flags: `--all/--categories/--yes/--doctor/--uninstall/--link-mode` | `Options` dataclass |
| `setup.py` | Composition root; prompts; `$SHELL` detection; `_verify_and_clean` | out of coverage by design |
| `docs/superpowers/plans/` + `specs/` | All plan/design docs for this session's work | full breadcrumb trail |
| `.claude/projects/.../memory/roadmap-status.md` | The authoritative roadmap memory | read this first |

### Key Patterns Discovered

- **Live-release verification is non-negotiable.** Every asset template / `member` / `strip` / arch token is confirmed against the *current* GitHub release via `gh api repos/OWNER/REPO/releases/latest --jq '.assets[].name'` and the archive layout via `curl -fsSL <url> | tar -tz` (or download + `unzip -l`). Never add a tool from memory. This caught real bugs and filtered incompatible tools all session.
- **Subagent-Driven Development.** Each plan task = a fresh implementer subagent (sonnet) with full task text + discipline, then a spec+quality review (opus for risky tasks: new modules, parsing, orchestrators; direct verification for trivial data/flag tasks). The controller (you) verifies every "DONE" against the real `make validate && make test` gate — never trust the report alone.
- **Editor diagnostics are stale out-of-venv noise.** The `<new-diagnostics>` blocks (unresolved `pytest`/`rich` imports, "MonkeyPatch unknown", "Type of X partially unknown") are from the editor's out-of-venv pyright. The authoritative check is in-venv `make validate` (pyright strict, 0 errors). Always verify against `make validate`, ignore the diagnostics.
- **Quality gates are never bypassed** — no `# noqa`/`# type: ignore`/`# nosec`/`# pragma: no cover`/skips/coverage lowering. 100% coverage on `installer/`. When a branch is uncovered, add a focused test (never a pragma).
- **Coherent commits on `main`.** Commit directly to main (project convention); amend review fixes into the same commit rather than piling up "fix" commits. Trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Work Completed

### Tasks Finished

- [x] Tempfile archive extraction (closed `curl|tar` pipefail) + `.zip` support + `member` templating
- [x] `make uninstall` — registry-driven, userspace-only, preview+confirm (hardened vs `..` traversal)
- [x] Registry Batch 4: deno, procs, ast-grep, jless (`.zip` tools) → 37→41
- [x] SP1: bun, pnpm, fnm via official `script` installers → 41→44
- [x] SP2: shell-rc link modes (centralized/single/split) + `--link-mode` + `$SHELL` detection
- [x] SP3: rc duplicate-PATH-line detection/cleaning + post-install doctor verify
- [x] Registry Batch 5: x64/bits arch tokens → gitleaks, vale; selective-zip → broot → 44→47

## Files Modified

| File | Changes | Rationale |
|------|---------|-----------|
| `installer/download.py` | tempfile extraction, `.zip` (selective `unzip <member>`), `_resolve_target` member templating | converged executor work + Batch 5 |
| `installer/assets.py` | added `x64`, `bits` ArchTokens fields | gitleaks/vale asset naming |
| `installer/registry.toml` | +10 tools (Batches 4/5 + script tier) | catalog growth |
| `installer/uninstall.py`, `installer/rcclean.py` | new modules | uninstall + PATH hygiene |
| `installer/app.py`, `cli.py`, `shellrc.py`, `render.py`, `locations.py` | link modes, uninstall/clean orchestrators, inline writer | feature wiring |
| `setup.py` | uninstall/link-mode/verify-and-clean wiring + prompts | composition root |
| `tests/*` | full TDD coverage for everything above | 100% maintained |

## Decisions Made

| Decision | Options Considered | Rationale |
|----------|-------------------|-----------|
| bun/pnpm/fnm use `script` (official installers), NOT github_release | github_release + x64 token | The user pointed out pnpm has an official installer; `script` is the ladder-preferred path (priority 10) and sidesteps arch tokens. Memory note corrected. |
| Let installers self-wire PATH, then clean dups (no executor `args`) | add `--skip-shell` arg support | User accepted self-editing "if no duplications"; the `_script` executor passes only env+shell, not CLI args. Simpler. |
| Selective `.zip` extraction (member only), always | opt-in param | Strictly less disk, identical symlink for flat zips, unlocks broot's 56MB combined archive. |
| pnpm's `case`-guarded PATH line intentionally NOT cleaned | extend matcher | It's self-deduping and not a plain `export PATH=`; pinned by test + comment (honest "no silent caps"). |
| uninstall hardened vs `member` basename `""`/`.`/`..` | trust registry | `opt_dir("..")` resolves to `~/.local` → `rmtree` would wipe the tree. Defensive guard (file-deletion code). |

## Pending Work

## Immediate Next Steps

1. **Ask the user what to tackle next** — last exchange offered: publish/push (deferred), checksum/sha256 verification (the notable security gap), native pkg-manager methods, or macOS `.app`/`.dmg` (Plan 6c). The two cheap "more tools" levers are now spent.
2. If **checksum verification**: design how to fetch+verify the `.sha256`/checksums asset alongside each download before extraction (most releases ship them) — a real security hardening item.
3. If **publish**: this is a one-time *owner* step the user must authorize — `gh auth login` then `gh repo create castocolina/tools-installer --public --source=. --remote=origin --push`. After that the `curl … | sh` one-liner resolves. DO NOT do this without explicit user go-ahead.

### Blockers/Open Questions

- [ ] None blocking. Direction for "what next" is the user's to choose.

### Deferred Items

- **Publish/push** — deferred by the user from the start of the session ("defer the repo create"); honor this until they explicitly say go.
- **`x64`/`64-bit` tokens are now done** (gitleaks/vale); remaining github_release tools are one-off quirks.
- broot is in but note it downloads a 56MB combined zip (then extracts one binary) — acceptable, documented.

## Context for Resuming Agent

## Important Context

- **READ `roadmap-status.md` in the memory dir first** (`/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`) — it's the authoritative, up-to-date state of every plan/batch with commit ranges and rationale.
- **Nothing is pushed and the repo has no remote — by design.** Do not push or create a remote without an explicit user request.
- **Always verify against `make validate && make test`**, not the editor diagnostics (which are stale out-of-venv noise). The gate is 0 pyright errors + 100% coverage.
- **Use Subagent-Driven Development** for plan execution (it's the established rhythm), and **verify each subagent's commit directly** (git show + run the gate) before accepting.
- **Live-verify every new tool** against its current GitHub release before adding — `gh` is authenticated in this environment.
- The work this session has full breadcrumbs in `docs/superpowers/specs/` (designs) and `docs/superpowers/plans/` (plans), including `2026-06-10-tools-installer-registry-batch5.md` and the SP1/SP2/SP3 plans.

## Assumptions Made

- pnpm's `pnpm setup` default PNPM_HOME is `~/.local/share/pnpm` (Linux) / `~/Library/pnpm` (macOS) — used for the registry `bin_dir`s (verified from the install script + pnpm docs, not by running it).
- The user wants the catalog to keep growing toward a "full AI dev environment" but values correctness (live verification) over raw count.

## Potential Gotchas

- **`setup.py` is out of coverage/pyright** — don't write unit tests for it or expect coverage from it; it's lint-gated only. Smoke-test wiring with `uv run setup.py --help`, NEVER run a real `--doctor`/wizard against the dev machine's home (split mode rewrites the real `~/.zshrc`/`~/.bashrc`).
- **`~/.myshellrc` already exists on this dev machine** with a managed block (from prior real installs — also why `~/.local/opt/rg` exists). That's pre-existing state, not something the tests wrote.
- A **hook re-runs `ruff format`** on `registry.toml`/test files after edits — re-read a file before further edits if a subagent reports reformatting.
- The count test in `tests/test_registry.py` is renamed each batch (currently `test_registry_has_forty_seven_unique_tools_and_cmds`) — update it when adding tools.
- gitleaks uses arch token `x64` (amd64) but vale uses `64-bit` — they are DIFFERENT strings; that's why both `x64` and `bits` fields exist on `ArchTokens`.

## Environment State

### Tools/Services Used

- **uv** owns Python/venv/deps. Use `make` targets: `make validate` (ruff, ruff-format, pyright strict, bandit `--skip B404,B603,B310`, vulture, shellcheck), `make test` (`pytest --cov`, 100%), `make setup`, `make doctor`, `make uninstall`.
- **gh** CLI is authenticated (account `castocolina`) — used for live release verification.
- **brew** is installed on this machine (used to verify formulae exist in homebrew/core).

### Active Processes

- None. No servers or background tasks running.

### Environment Variables

- `SHELL` (read for single-shell link-mode rc detection) — name only.
- No secrets used or stored.

## Related Resources

- `docs/prds/ai-dev-tools-installer-v1.0-prd.md` — the locked v1 design
- `docs/superpowers/specs/2026-06-10-zip-extraction-and-uninstall-design.md`
- `docs/superpowers/specs/2026-06-10-script-installer-tier-and-path-hygiene-design.md`
- `docs/superpowers/plans/2026-06-10-*.md` (batch4, batch5, sp1/sp2/sp3, uninstall)
- `CLAUDE.md` + `.claude/*.md` — contributor rules (tooling, testing, git, dev env)
- Memory: `/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`

---

**Security Reminder**: No secrets in this document. All env vars referenced by name only.
