# Phase 24: Onboarding through the skill and e2e - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev ladder, best-over-easy)
**Status:** Ready for planning

<domain>
## Phase Boundary

herdr and Alacritty prove the v0.50.0 contract end to end, onboarded through the tool-onboarding skill. Then a three-distro container run plus one real-host UAT show that the full lifecycle leaves nothing behind except documented config.

The WHAT is locked in `24-SPEC.md` (R1–R9). This file locks the HOW.

Out of scope:
- A persistent Distrobox or exported apps.
- Other source-built tools.
- An Alacritty build for macOS.
- Neovim (24.1).
- herdr workspace features beyond the separator and the indicators.

**Prerequisites:**
- 18: D-01, D-02, D-05, D-06, D-07.
- 19: D-05..D-10, D-14, D-16.
- 20: D-08 `WORDS`, D-12, D-17 MANUAL.
- 22: D-01, D-06/D-07, D-12, D-17.
- 23: D-01/D-02/D-04 hook pairs and `receipt.hooks`, D-06/D-07 the guarded-splice writer, D-14 terminal dry run plus SHELL.

None of these has landed as of 2026-10-14.
</domain>

<decisions>
## Implementation Decisions

**Decision rule:** best over easy, with the jev ladder.

### `cargo_distrobox` kind (R2, R4, R5)
- **D-01:** `METHOD_PARAMS["cargo_distrobox"]` (18 D-01) has these params:
  - `repo` (git URL).
  - `version` source: the GitHub release tag.
  - `packages`: a closed string list of build dependencies, in the `_opt_pkg_list` shape (`executors.py:48`).
  - `artifacts`: a **list of tables** `[{box = "...", host = "..."}]` validated at load. Not parallel lists.
  - Host paths must sit under `~/.local` or `~/.config` (SPEC constraint).
- **D-02:** The executor owns `create → build (cargo at the tag, plus the in-box steps) → copy to staging` inside `try`. Its **`finally` always** runs `distrobox rm --force <name>` and then removes the image, even on failure, and re-raises afterwards.
  - The name is collision-proof: `ti-cargo-<tool>-<pid>-<rand>`.
  - Each step has a bounded timeout through the `run.py` runner conventions.
  - The engine does no cleanup, so the executor must.
- **D-03:** Staging comes first. The 18 D-06 `smoke()` runs on the staged binary, then the files are placed with `replace_symlink`/atomic moves (17 D-01).
  - `download.artifact_paths(method)` (19 D-07) gains a `cargo_distrobox` branch that reads the `artifacts` host paths, so install, receipt and removal (L2) share one formula.
- **D-04:** Update by rebuild. The GitHub tag is the version source (the 7-day TTL path), and a newer tag means OUTDATED.
  - `u` rebuilds that tag, replaces the artifacts and rewrites the receipt.
  - `~/.config/alacritty` is never touched; a checksum test proves it.
- **D-05:** Precedence goes through `resolve.py`'s one switch (`_RANK` :13-29, `_applies`/`_rejection` :39-128). This makes `_rejection` the single source of the reason, so the review and the ladder can't disagree (the 19 D-14 lesson).
  - New `Platform.has_distrobox`/`has_podman` fields are re-read each pass, following 19 D-14's `has_brew`.
  - `cargo_distrobox` ranks ahead of the native kinds on Linux.
  - Immutable without both tools: UNAVAILABLE, "needs distrobox and podman".
  - Mutable without both tools: the native method, which is a MANUAL handoff (22 D-12).
  - macOS: UNAVAILABLE with the existing reason.

### Alacritty artifacts and terminal (R3, R6)
- **D-06:** A small pure module, `installer/desktop_entry.py`, renders `.desktop` files. It follows the single-purpose module precedent.
  - It sets `Exec`/`TryExec` to the installed absolute binary, and the icon. Writes go through `atomic_write_text`.
  - The entry, the icon and the terminfo tree are `artifacts`, so they are receipt-proven and removable.
  - Nothing desktop-related exists in `installer/` today.
- **D-07:** `tic -xe alacritty,alacritty-direct -o <box dir>` runs **inside the box**, and only the compiled tree is copied to `~/.local/share/terminfo`. This adds no host `tic`/ncurses dependency.
  - Acceptance: `infocmp alacritty` resolves through it, and `desktop-file-validate` passes. Both are checked in the container step.
- **D-08 (best, not easy):** Alacritty is one more branch of `sync_terminal_shells` (with 23 D-14 `write=False` and SHELL). Its owned region in `alacritty.toml` holds the shell, `SHELL`, Alt/Option word navigation and clear-scrollback.
  - **TOML guard:** before writing, scan the content outside the region for conflicting tables (`[terminal]`/`[terminal.shell]`, `[[keyboard.bindings]]` for the same keys). If one is found, write nothing and show `≈` with "partial: you already define X".
  - After writing, re-parse with `tomllib` and roll back on failure.
  - One new Policy row toggles the region. Removing the region by hand shows `≈`.
  - jev: Laya guarded_region 0.82, own confidence 0.32, so I pivoted; TypeSafe 1.00.
- **D-08b (user request 2026-10-14, SPEC R6 amended):** herdr is another branch of `sync_terminal_shells`, next to Konsole, kitty, WezTerm and Alacritty. It applies only when `herdr` and zsh both resolve through `_safe_executable(lookup(...))`.
  - **Root cause, measured on this host:** herdr 0.9.3 `[terminal] default_shell` defaults to empty, which means `$SHELL`, then `/bin/sh`. The passwd shell and `$SHELL` here are `/bin/bash`, and zsh is `/home/linuxbrew/.linuxbrew/bin/zsh`. So herdr panes run bash and omz plugins never load.
  - **Write:** `default_shell = "<abs zsh>"` under `[terminal]`. It goes through the 23 D-06/D-07 guarded splice **only when the key is absent**: it adds the table if missing, or splices the key into an existing `[terminal]`. It is never a second `[terminal]` header (that is invalid TOML).
    - Re-parse with `tomllib`; roll back on failure.
    - Record the write in the 23 D-08 ledger.
    - Then `herdr server reload-config`, best effort. Already-open panes keep their shell, so the UAT opens a new pane.
  - `shell_mode` is left at `auto`: interactive zsh reads `.zshrc`, which is enough for omz.
  - **A user-set `default_shell`** (any value) is never overwritten. If it isn't zsh, show `≈` with "partial: you already set terminal.default_shell".
  - **Revert:** Policies off, or herdr uninstall, removes only the ledgered key, and only if it still holds the written value.
  - Same Policy row family as the other terminals; no new toggle UI.
  - It is independent of D-12: the separator and indicators touch other keys, and both share the one writer and ledger.

### herdr (R1)
- **D-09:** herdr gets `github_release` methods with `raw = true`, per OS/arch, at tier `user`, `audience = "both"`. There is no checksum file, so 18 D-05 digests apply when the API provides them.
- **D-10:** `herdr-integrations` is a 23 D-01 `(register, unregister)` hook with an explicit **`_HERDR_HOST_IDS`** translation map, because herdr's names differ from ours (`antigravity-cli`, `cursor`, `qodercli`, …).
  - The map is verified against the host's existing herdr 0.9.3 through a **read-only** `herdr integration status`/`--help`.
  - Unregister is `herdr integration uninstall <agent>`, for the receipt hosts only.
  - The researcher must check whether an integration also edits an agent's main config (merge safety).
- **D-11:** The herdr skill is its own `skill_pack` `[[tool]]` with `requires = ["herdr"]`, tier `ai` (the ponytail precedent, `registry.toml:2807-2868`). With it unselected, no skill files are written.
- **D-12 (SPEC R1 text, user-confirmed 2026-10-14):** The **separator and current-indicator** reuse from herdr-setup is **in scope**. Only these two: no accent or theme styling (user: "agregar el separador y el indicador más que el accent"). SPEC R1 names them, and the Boundaries exclude only features *beyond* them.
  - It ships as a named hook: place the plugin from a pinned source, `herdr plugin link`, write the `rows` arrays and `row_gap` through the 23 D-06/D-07 writer **only when absent**, `herdr server reload-config`, and record the writes in the ledger (23 D-08).
  - When the user already defines those arrays, nothing is written and a reason names the tokens to add by hand.
  - Removal: `herdr plugin unlink`, then revert only the keys that were written.
  - The ROADMAP "known limits" (separator order by `pane_order`, the silent socket failure) are fixed or recorded by the planner.
  - jev: Laya absent_only_with_reason 0.82, own confidence 0.32; TypeSafe 0.92.

### Onboarding skill (R7)
- **D-13:** Run skill-judge on the **unedited** `.claude/skills/tool-onboarding/` first to record the baseline; none has ever been recorded.
  - Then **rewrite** step 4b (`SKILL.md:118-123`), which is false after 22. It should describe L1/L2/L3 removal with one example per new param (`paths`, `remove`, `update`, `writable_prefix`, `config_paths`), plus a `cargo_distrobox` row.
  - Re-judge, and commit the report with both scores; the final score must be ≥ the baseline.

### e2e and UAT (R8, R9)
- **D-14:** `scripts/container-e2e-verify.sh` gets `--distro {fedora,debian,arch}`, threaded through every subcommand, with one per-distro table: image, root prerequisites, and the release record replacing `record_fedora_release`. The hardcoded parts are at `:14-20, 108-121`.
  - Everything else is shared: the tester, the bootstrap, `cmd_pass2`, and 22 D-17's leftover listing. There are no copied per-distro scripts.
  - "All" means every tool available on that distro, according to the plan.
- **D-15:** The rerun pass asserts **zero rows other than skipped or blocked**, using the 20 D-08 `WORDS` vocabulary (not an ad hoc "already installed" grep).
  - A planted leftover fails the run.
- **D-16 (best, not easy):** The **one real Alacritty build** runs the executor on the **host's own podman with `HOME` pointed at a scratch directory**.
  - Afterwards it asserts that `podman ps -a` and the image list hold nothing new, then deletes the scratch dir. The real HOME is never touched.
  - The three-distro containers have no distrobox/podman, so they exercise the fallback or UNAVAILABLE path deterministically. There is no nested podman.
  - jev: Laya 0.64 (needs fallback); TypeSafe 0.97.
- **D-17:** The real-host UAT is `24-UAT.md` in the existing UAT format. It is the only manual step, and the user runs it: Owner filled on every tier after install, `○` after Uninstall. It also checks that a **new** herdr pane runs zsh with omz plugins loaded (D-08b).

### Claude's Discretion
- Plan and wave order. Suggested:
  1. The `cargo_distrobox` kind, its precedence, and fake-runner tests.
  2. Alacritty data and artifacts, `desktop_entry`, terminal plus TOML guard.
  3. herdr with its hooks, skill pack and indicators.
  4. The onboarding skill.
  5. Three-distro e2e and the real build.
  6. UAT.
- The exact distrobox flags and the per-distro Alacritty build package names (research).

### Folded Todos
None.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/24-onboarding-through-the-skill-and-e2e/24-SPEC.md`: locked R1–R9
- `.planning/ROADMAP.md`: herdr notes (~:389-410: classification, integration names, herdr-setup KEEP/DROP and known limits), the Alacritty no-reboot path
- `.claude/skills/tool-onboarding/` (SKILL.md, ladder at :77-91, step 4b at :118-123)
- `docs/research/2026-10-09-alacritty.md`
- `.planning/research/2026-10-13-target-architecture.md`: §4, §5, §6, §9.2 O5
- Prior contexts: 18, 19, 20, 22, 23 (decisions listed in the domain section)
- `.planning/REQUIREMENTS.md`: ONB-01..07
- `.claude/architecture.md`, `AGENTS.md`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `resolve.py` `_RANK`/`_applies`/`_rejection`; `platform.Platform`
- `executors._opt_pkg_list`; `run.Runner`/`run_output`/`CommandError`
- `terminal_shell._replace_owned_region`/`sync_terminal_shells`
- `registry.toml`: the WezTerm raw method (:2630-2635), the ponytail skill pack (:2807-2868), the Alacritty entry and comment (~:2655)
- `scripts/container-e2e-verify.sh` (`cmd_pass2`, `accumulate_summaries` :254-273, `SUMMARY_RE` :222)

### Established Patterns
- Multi-step executors guarantee cleanup themselves (`try/finally`).
- Platform facts are re-read each pass; `resolve.py` is the one switch for availability and reasons.
- TOML writes go through a guarded splice and a `tomllib` re-parse.

### Integration Points
- `cargo_distrobox` → `artifact_paths` → receipt → `removal_plan` L2
- `herdr-integrations` hook ↔ `receipt.hooks` ↔ `present_harnesses`
- The e2e `--distro` table ↔ the `WORDS` vocabulary
</code_context>

<specifics>
## Specific Ideas

- Measured: the Alacritty build takes 35 s and yields a 12 MB binary, with host libs resolving.
- `herdr integration status` on this host (2026-10-13): claude v10, opencode v13, cursor v1 current; pi not installed. pi gets this for free via `present_harnesses`, once the id map includes pi.
</specifics>

<deferred>
## Deferred Ideas

- herdr's optional local-first sort and the personal preference keys (ROADMAP "OPTIONAL"/"DROP" lists): offered later as separate choices, never bundled.

### Reviewed Todos (not folded)
- pi repair (0.6), GSD per-repo (0.6), Playwright Chrome (0.6), pnpm shims (0.6, Phase 21).
</deferred>
