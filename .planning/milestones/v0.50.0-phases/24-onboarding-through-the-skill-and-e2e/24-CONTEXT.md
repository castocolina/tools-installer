# Phase 24: Onboarding through the skill and e2e - Context

**Gathered:** 2026-10-14 (assumptions mode, `--analyze --all --batch`, jev ladder, best-over-easy); updated 2026-11-07 (assumptions mode, after 23.1/23.2 and the user's 2026-11-07 decisions; CodeGraph)
**Status:** Ready for planning

> **Scope change (user, 2026-11-02):** the installer does not install skill packs. herdr ships without a skill pack, so D-11 is dropped and every herdr skill-pack mention below is void. Removing existing skill-pack entries is a later, separate phase.
>
> **Update (2026-11-07):** Phase 23.1 deletes the skill-pack kind and moves `present_harnesses` into `installer/postinstall.py`; Phase 23.2 makes every customization install-time tuning (TUNE-04, the user's "always, no question") and trims Policies to 7 rows. This phase therefore adds **no Policies row** (D-22), and the one real Alacritty build runs in a disposable container, never on the host (D-18, the user's "every e2e runs in a container locally"). New decisions D-18..D-31 are under "Added 2026-11-07".

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

None of these has landed as of 2026-10-14. *(amended 2026-11-07: 22 and 23 have landed in code — `artifact_paths`, `config_paths`, `removal_plan`, the hook pairs including herdr's `_HERDR_TARGETS` at `installer/postinstall.py:151-210`; 23.1 and 23.2 are planned before this phase and are prerequisites too: 23.1 D-01/D-02/D-16..D-22/D-26, 23.2 D-01/D-03/D-04/D-08/D-19/D-20..D-23)*
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
  - **Amended 2026-11-08 at plan time (orchestrator, 24-RESEARCH Q1/Q3):** `repo` is a GitHub `owner/name` slug (the version source is its release tag; the clone URL is derived as `https://github.com/<slug>.git`), not a free git URL. A required `image` string param (a fully qualified image reference) is added. Host paths may also sit under `~/.terminfo` (see D-07).
- **D-02:** The executor owns `create → build (cargo at the tag, plus the in-box steps) → copy to staging` inside `try`. Its **`finally` always** runs `distrobox rm --force <name>` and then removes the image, even on failure, and re-raises afterwards.
  - The name is collision-proof: `ti-cargo-<tool>-<pid>-<rand>`.
  - Each step has a bounded timeout through the `run.py` runner conventions.
  - The engine does no cleanup, so the executor must.
  - **Refined 2026-11-07:** the image is removed only when this run pulled it, and never with `--force` (D-19, needs confirmation); the box uses `--home <run temp dir>` + `--no-entry` and is removed with `--rm-home` (D-20).
- **D-03:** Staging comes first. The 18 D-06 `smoke()` runs on the staged binary, then the files are placed with `replace_symlink`/atomic moves (17 D-01).
  - `download.artifact_paths(method)` (19 D-07) gains a `cargo_distrobox` branch that reads the `artifacts` host paths, so install, receipt and removal (L2) share one formula.
- **D-04:** Update by rebuild. The GitHub tag is the version source (the 7-day TTL path), and a newer tag means OUTDATED.
  - `u` rebuilds that tag, replaces the artifacts and rewrites the receipt.
  - `~/.config/alacritty` is never touched; a checksum test proves it.
  - **Amended 2026-11-13 (planner, 24-REVIEWS R2-12):** "never touched" applies to the rebuild. The post-run terminal follow-up D-22 runs after every route, `u` included, and may rewrite only the owned `alacritty` shell region when it drifted; best over easy: special-casing the update route would make a drifted region repair on install and doctor but not after `u`, against D-22's "every lifecycle route". SPEC R4 carries the same dated amendment.
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
  - **Amended 2026-11-08 at plan time (orchestrator, 24-RESEARCH Q1):** the compiled terminfo tree goes to `~/.terminfo`, not `~/.local/share/terminfo`. Neither ncurses 6.6 nor Alacritty v0.17.0 searches `~/.local/share/terminfo` (reproduced in a scratch HOME); `~/.terminfo` is the standard user location both read. No `TERMINFO_DIRS` export. SPEC R3 / ONB-06 read with this path.
- **D-08 (best, not easy):** Alacritty is one more branch of `sync_terminal_shells` (with 23 D-14 `write=False` and SHELL). Its owned region in `alacritty.toml` holds the shell, `SHELL`, Alt/Option word navigation and clear-scrollback.
  - **TOML guard:** before writing, scan the content outside the region for conflicting tables (`[terminal]`/`[terminal.shell]`, `[[keyboard.bindings]]` for the same keys). If one is found, write nothing and show `≈` with "partial: you already define X".
  - After writing, re-parse with `tomllib` and roll back on failure.
  - ~~One new Policy row toggles the region.~~ *(superseded 2026-11-07, D-22)* Removing the region by hand shows `≈`.
  - **Refined 2026-11-07:** the region splits in two — the shell region stays here; the keybindings move to an Alacritty install-tuning region written whether or not zsh is present (D-23). Removing Alacritty strips both (D-22).
  - jev: Laya guarded_region 0.82, own confidence 0.32, so I pivoted; TypeSafe 1.00.
- **D-08b (user request 2026-10-14, SPEC R6 amended):** herdr is another branch of `sync_terminal_shells`, next to Konsole, kitty, WezTerm and Alacritty. It applies only when `herdr` and zsh both resolve through `_safe_executable(lookup(...))`.
  - **Root cause, measured on this host:** herdr 0.9.3 `[terminal] default_shell` defaults to empty, which means `$SHELL`, then `/bin/sh`. The passwd shell and `$SHELL` here are `/bin/bash`, and zsh is `/home/linuxbrew/.linuxbrew/bin/zsh`. So herdr panes run bash and omz plugins never load.
  - **Write:** `default_shell = "<abs zsh>"` under `[terminal]`. It goes through the 23 D-06/D-07 guarded splice **only when the key is absent**: it adds the table if missing, or splices the key into an existing `[terminal]`. It is never a second `[terminal]` header (that is invalid TOML).
    - Re-parse with `tomllib`; roll back on failure.
    - Record the write in the 23 D-08 ledger.
    - Then `herdr server reload-config`, best effort. Already-open panes keep their shell, so the UAT opens a new pane.
  - `shell_mode` is left at `auto`: interactive zsh reads `.zshrc`, which is enough for omz.
  - **A user-set `default_shell`** (any value) is never overwritten. If it isn't zsh, show `≈` with "partial: you already set terminal.default_shell".
  - **Revert:** ~~Policies off, or herdr uninstall,~~ *(superseded 2026-11-07, D-22)* herdr uninstall, or zsh going away, removes only the ledgered key, and only if it still holds the written value.
  - ~~Same Policy row family as the other terminals; no new toggle UI.~~ *(superseded 2026-11-07, D-22: the other terminals have no Policies row — they are synced by the post-run follow-up `_sync_terminals` and the `terminal_sync` drift step; herdr joins that family, no Policies row, no toggle UI)*
  - It is independent of D-12: the separator and indicators touch other keys, and both share the one writer and ledger.

### herdr (R1)
- **D-09:** herdr gets `github_release` methods with `raw = true`, per OS/arch, at tier `user`, `audience = "both"`. There is no checksum file, so 18 D-05 digests apply when the API provides them.
- **D-10:** `herdr-integrations` is a 23 D-01 `(register, unregister)` hook with an explicit **`_HERDR_HOST_IDS`** translation map, because herdr's names differ from ours (`antigravity-cli`, `cursor`, `qodercli`, …).
  - The map is verified against the host's existing herdr 0.9.3 through a **read-only** `herdr integration status`/`--help`.
  - Unregister is `herdr integration uninstall <agent>`, for the receipt hosts only.
  - The researcher must check whether an integration also edits an agent's main config (merge safety).
  - **Refined 2026-11-07:** the map already exists as `_HERDR_TARGETS` (`installer/postinstall.py:151-157`: claude, codex, opencode, cursor); this phase extends it (D-21) and records only hosts it actually set up (D-27). Live 2026-11-07: integrations DO edit agents' main config (a `hooks.SessionStart` entry in `~/.claude/settings.json`, a `hooks.sessionStart` entry in `~/.cursor/hooks.json`), so removal order and value-level assertions follow D-28.
- **D-11 (DROPPED 2026-11-02, no skill packs):** ~~The herdr skill is its own `skill_pack` `[[tool]]` with `requires = ["herdr"]`, tier `ai` (the ponytail precedent, `registry.toml:2807-2868`). With it unselected, no skill files are written.~~
- **D-12 (SPEC R1 text, user-confirmed 2026-10-14):** The **separator and current-indicator** reuse from herdr-setup is **in scope**. Only these two: no accent or theme styling (user: "agregar el separador y el indicador más que el accent"). SPEC R1 names them, and the Boundaries exclude only features *beyond* them.
  - It ships as a named hook: place the plugin from a pinned source, `herdr plugin link`, write the `rows` arrays and `row_gap` through the 23 D-06/D-07 writer **only when absent**, `herdr server reload-config`, and record the writes in the ledger (23 D-08).
  - When the user already defines those arrays, nothing is written and a reason names the tokens to add by hand.
  - Removal: `herdr plugin unlink`, then revert only the keys that were written.
  - The ROADMAP "known limits" (separator order by `pane_order`, the silent socket failure) are fixed or recorded by the planner.
  - **Refined 2026-11-07:** the pinned source is `castocolina/herdr-setup@2b5ca2a` (live `gh api`: still the single commit). The plugin needs `python3`: when it is absent the hook writes nothing and the row names the reason. The host has no linked plugin and no `ui.sidebar` rows today, so the absent-only write would apply there. No Policies row (D-22): it is herdr's install tuning, reverted on herdr uninstall.
  - jev: Laya absent_only_with_reason 0.82, own confidence 0.32; TypeSafe 0.92.

### Onboarding skill (R7)
- **D-13:** Run skill-judge on the **unedited** `.claude/skills/tool-onboarding/` first to record the baseline; none has ever been recorded.
  - Then **rewrite** step 4b (`SKILL.md:118-123`), which is false after 22. It should describe L1/L2/L3 removal with one example per new param (`paths`, `remove`, `update`, `writable_prefix`, `config_paths`), plus a `cargo_distrobox` row.
  - Re-judge, and commit the report with both scores; the final score must be ≥ the baseline.
  - **Refined 2026-11-07 (D-24):** "unedited" now means the skill as Phase 23.2 leaves it (23.2 D-19 already scores it before/after). Step 4b sits at `SKILL.md:96-123` today (the false paragraph is `:118-123`); the planner anchors on the `### 4b.` heading, since 23.1/23.2 shift lines.

### e2e and UAT (R8, R9)
- **D-14:** `scripts/container-e2e-verify.sh` gets `--distro {fedora,debian,arch}`, threaded through every subcommand, with one per-distro table: image, root prerequisites, and the release record replacing `record_fedora_release`. The hardcoded parts are at `:14-20, 108-121`.
  - Everything else is shared: the tester, the bootstrap, `cmd_pass2`, and 22 D-17's leftover listing. There are no copied per-distro scripts.
  - "All" means every tool available on that distro, according to the plan.
- **D-15:** The rerun pass asserts **zero rows other than skipped or blocked**, using the 20 D-08 `WORDS` vocabulary (not an ad hoc "already installed" grep).
  - A planted leftover fails the run.
  - **Refined 2026-11-07 (D-25):** `manual` rows equal to pass 1's manual set are also accepted.
- ~~**D-16 (best, not easy):** The **one real Alacritty build** runs the executor on the **host's own podman with `HOME` pointed at a scratch directory**.~~ *(superseded 2026-11-07, D-18: the SPEC constraint "e2e runs only in disposable podman containers, never on the host", AGENTS.md and the user's 2026-11-07 decision 2 forbid a real build on the host)*
  - ~~Afterwards it asserts that `podman ps -a` and the image list hold nothing new, then deletes the scratch dir. The real HOME is never touched.~~ *(superseded 2026-11-07, D-18)*
  - The three-distro containers have no distrobox/podman, so they exercise the fallback or UNAVAILABLE path deterministically. ~~There is no nested podman.~~ *(superseded 2026-11-07, D-18: one separate nested-podman target runs the real build)*
  - jev: Laya 0.64 (needs fallback); TypeSafe 0.97.
- **D-17:** The real-host UAT is `24-UAT.md` in the existing UAT format. It is the only manual step, and the user runs it: Owner filled on every tier after install, `○` after Uninstall. It also checks that a **new** herdr pane runs zsh with omz plugins loaded (D-08b).
  - **Refined 2026-11-07 (D-29):** this host already sets `[terminal] default_shell` by hand (live, value not shown), so the absent-only rule writes nothing here. The UAT line checks that the user value is untouched, no `≈` and no ledger entry, and that a new pane runs zsh; the write itself is proven in the container e2e.

### Added 2026-11-07 (assumptions mode, after 23.1/23.2 and the user's 2026-11-07 decisions)

#### Real build and the `cargo_distrobox` executor (SPEC R2 amended)
- **D-18: The one real Alacritty build runs inside a disposable container with its own nested rootless podman and distrobox (for example a `quay.io/podman/stable`-based target of the e2e harness), never on the host's podman** (supersedes D-16).
  - The SPEC constraint already says "e2e runs only in disposable podman containers, never on the host. Only the UAT touches the host" (`24-SPEC.md` Constraints); AGENTS.md says real installs run only in disposable containers; the user's decision 2 (2026-11-07) says every e2e runs in a container locally.
  - The target runs the executor once against a scratch HOME inside the outer container, then asserts that the inner `podman ps -a` and image list are empty. The outer container is removed afterwards, so nothing reaches the host store.
  - Feasibility (rootless nested podman on SELinux Bazzite: `/dev/fuse`, `label=disable`, subuid ranges, whether `distrobox create` works inside) is a plan-time research item. If it proves infeasible, the real build is recorded during the user's own 24-UAT.md run instead — never by an agent on the host's podman.
  - **Own reasoning** (jev low 0.61 host_scratch_home; Laya low 0.60 manual_uat_only): host podman contradicts the user-locked "every e2e in a container" and the SPEC constraint; a manual-only record loses the automated proof of "no container or image left". Ledger.
- **D-19: The executor removes the image only when this run pulled it** (SPEC R2 amended, **needs confirmation**: ONB-02 / ROADMAP criterion 2 say "the container and image are deleted afterwards").
  - Before create: `podman image exists <ref>`. Pulled by this run → removed in the `finally`; already present → kept and named in the row detail ("kept the existing image <ref>"). Never `podman rmi --force`, which would delete the user's own containers built on that image; a plain `rmi` of an in-use image would fail a good build.
  - In the D-18 nested target the store starts empty, so the image is always pulled by the run and the SPEC's "image list empty" acceptance holds unchanged.
  - **Own reasoning** (jev low 0.71 only_if_pulled_by_run, agreeing): live, the host store holds several images and 5 containers; a shared base image is realistic. Ledger.
- **D-20: The box is created with `distrobox create --home <run temp dir> --no-entry …` and removed with `distrobox rm --force --rm-home`.**
  - Live `distrobox create --help` (1.8.2.5): `--home` "useful to avoid host's home littering with temp files"; `--no-entry` "do not generate a container entry in the application list"; `distrobox rm --rm-home` "remove the mounted home if it differs from the host user's one".
  - By default the box mounts the real HOME, so in-box cargo would write `~/.cargo` caches and distrobox an app-menu entry, breaking "nothing persists outside the recorded artifacts" and the leftover check. The fake-runner argv acceptance asserts the three flags.
  - Analyzer, Confident.

#### Install tuning instead of Policies (SPEC R6 amended, TUNE-04)
- **D-22: This phase adds no Policies row. The shell lines (Alacritty's shell region, herdr's `default_shell`) stay branches of `sync_terminal_shells`, written by the post-run follow-up `_sync_terminals` on every lifecycle route and repaired by the `terminal_sync` drift step; they are reverted when zsh goes (today's `_revert_terminal_shells`) and, new, when the terminal tool itself is removed (a terminal branch in `app._after_removal`).**
  - Live code: terminal sync has no Policies row (`setup.py:639-665`, `:885-901`, `:1121`, `:1503`; `version_status.py:656-660`, `:1669-1675`; `session.py:438-445`); 23.2 locks Policies at 7 rows with a "no tuning as a Policies row" must-NOT.
  - The shell line's input is another tool (zsh), and plan order does not tie herdr/Alacritty to zsh: a per-tool post_install could run before zsh exists and make the rerun plan RECONFIGURE (D-15/D-25). The follow-up runs after the whole run and already re-syncs when zsh arrives later.
  - Reverting on tool removal is TUNE-04's "reverted with the tool" and D-08b's locked "herdr uninstall removes only the ledgered key"; kitty/WezTerm/Konsole keep today's behavior (out of scope).
  - `sync_terminal_shells` gains an injected runner for `herdr server reload-config` (23.1 D-16..D-22 refuses a real `herdr` in unit tests). herdr's `default_shell` is not a 23.2 install-tuning group, so one key never raises both "apply install tuning" and "point herdr at zsh".
  - **Own reasoning** (jev low 0.67 shared_sync_revert_zsh_only; Laya low 0.35 per_tool_postinstall): reverting only on zsh-gone would leave a key in a removed tool's config, against TUNE-04 and locked D-08b. Ledger.
- **D-23: Alacritty's keybindings (Alt/Option word navigation, clear scrollback) are Alacritty's own install tuning in a second owned region (e.g. `alacritty-keys`), written by an Alacritty post_install action through 23.2's per-row dispatcher whether or not zsh is present.**
  - A present but untuned Alacritty (native hand-install) shows 23.2's `≈` "apply install tuning" (`install_tuning` step); a written-once record (23.2 D-08) makes a hand-deleted keybindings region the user's choice (no `≈`). The shell region keeps `≈` on hand removal, like kitty.
  - Removing Alacritty strips both regions and keeps the file and the user's keys. The Alacritty entry gains `config_paths = ["~/.config/alacritty"]` (none today, `registry.toml:2944-2963`) so the kept file passes the leftover check (`_remove_if_owned` leaves an empty file, `terminal_shell.py:250-258`).
  - The D-08 TOML guard applies to each region separately.
  - choice 1.00 (two_blocks).

#### Onboarding skill (SPEC R7 amended, ONB-03 + TUNE-04)
- **D-24: The skill-judge baseline is a fresh run at the start of this phase on the skill as 23.2 leaves it, with 23.2's recorded after-score noted beside it. This phase's edit keeps 23.2's TUNE-04 text verbatim** ("a new requirement is install-time tuning in the tool's postinstall unless it lies outside any install; never a Policies knob by default").
  - The §7 terminal bullet (`SKILL.md:159-162` today) says: the shell launch is the zsh terminal sync; keybindings and other terminal customizations are the terminal's install tuning; never a Policies row.
  - The prose "skill packs" at `:134` goes (23.2 R9's `skill_pack|skill_lifecycle` grep does not catch it). Acceptance: `rg -n "Policies"` shows the rule and `rg -n -i "skill.pack|skill_lifecycle"` finds nothing.
  - choice 0.90 (fresh_rescore): the judge is not deterministic, so a recorded number from another phase is not a fair "before".

#### e2e (SPEC R8 amended)
- **D-25: The rerun pass accepts skipped or blocked rows plus `manual` rows whose tool set equals pass 1's manual set; any installed, updated, reconfigured or repaired row fails.** Refines D-15.
  - The installer never runs root commands, so native-kind tools come back `manual` on every pass (22 D-12; Alacritty in the distro containers, which have no distrobox). The harness already collects manual names (`ACC_MANUAL_NAMES_FILE`, `scripts/container-e2e-verify.sh:911`) and today's `TRACER_RERUN_OK` accepts manual (`:432-441`, `:925`).
  - choice 0.88 (skipped_plus_same_manual).
- **D-26: A tool the resolver offers but that cannot run on one distro is excluded through that distro's table entry (D-14) and listed with its reason.** First case: copilot's `node` method checks `min_node` against the system `node` (`executors.py:486-496`); the researcher compares Debian's and Arch's packaged nodejs with the floor 23.2 sets — exclude only where it is not met.
  - choice 0.80 (exclude_and_list): SPEC R8's edge already allows a listed per-distro exclusion; installing a newer Node by hand would hide what a real Debian user gets.
  - **Amended 2026-11-08 at plan time (orchestrator, 24-RESEARCH Q5):** the copilot case is gone (23.2 ships copilot as a standalone binary); the real case is mmdc/puppeteer on Debian (packaged Node 20.19.2 < `min_node` 22.12.0). There is no new CLI flag (Phase 23 O1). A method whose `min_node` floor the system `node` does not meet is shown at plan time as a non-failure disposition with the reason ("needs Node >= 22.12; this system has 20.19.2"), like an unsupported OS. Dependents follow through the existing dependency disposition. The distro run then lists the exclusion by its reason.
- **D-31: 23.1's `assert_gsd_absent` and 23.2's copilot / install-written-key assertions live in the shared `cmd_pass1`/`cmd_pass2`, so all three distros run them; D-14's table varies only the image (`:16`), the root prerequisites (`:123-130`) and the release record (`:117-121`). D-14 builds on 23.2's version of pass 2** (23.2 D-23 replaces `settings_probe_write`, `:781-828`). Analyzer, Confident.

#### herdr integrations (D-10 refined)
- **D-21: `_HERDR_TARGETS` covers every host present in both `HARNESS_MARKER_DIRS` (`model.py:205-223`) and herdr's live target list** (`herdr integration install --help`, 0.9.3: pi, omp, claude, codex, copilot, devin, droid, kimi, opencode, kilo, hermes, qodercli, qwen, cursor, mastracode, antigravity-cli, grok, letta) — adding pi, copilot, kilo, kimi, qwen, devin, grok, hermes and factory-droid→droid. An ambiguous id (antigravity / gemini-cli → `antigravity-cli`) is left out and recorded in a comment.
  - `HOST_CATALOG_IDS` (`postinstall.py:30-35`) gains `pi` and `copilot`, so `_resync_hooks` (`session.py:536-585`) registers herdr when pi or copilot install after herdr in the same run; otherwise the rerun shows `≈` "register herdr for …" (D-25). 23.2 D-22 keeps copilot out of `_CODEGRAPH_TARGETS` only; codegraph filters by its own targets.
  - **Own reasoning** (jev low 0.72 all_shared_skip_ambiguous, agreeing): integrations only install for present hosts, so a wider map costs nothing and serves non-catalog agents the user runs. Ledger.
- **D-27: `register` records only hosts whose integration was "not installed" or "needs repair" before it ran (a read-only `herdr integration status` probe); a host already "current" is left out of the receipt and reported as user-owned, so uninstall never removes it.**
  - Live 2026-11-07: claude current (v10), cursor current (v1), opencode "needs repair (v13)" — all set up by hand.
  - **Own reasoning** (jev low 0.67 all_ran_install): the receipt principle (19/22) is "revert only what the installer wrote"; recording a hand-made, already-current integration would remove the user's setup on uninstall. Running install on a "needs repair" host rewrites it, so the installer owns it from then on. Ledger.
- **D-28: herdr and the 23.2 ledger share agent config files, so the full uninstall unregisters herdr's integrations before the agents' ledger keys revert, and the e2e asserts key values, not bytes, for files herdr touched** (`~/.claude/settings.json`, `~/.cursor/hooks.json`; the existing revert probe already compares values, `container-e2e-verify.sh:833-881`). The researcher records exactly what each target writes (including copilot beyond `~/.copilot/hooks/herdr-agent-state.sh`) and whether herdr's uninstall leaves empty `hooks` containers.
  - choice 0.95 (ordered_value_level).

#### UAT (D-17 refined)
- **D-29: The UAT's herdr line checks "user `default_shell` untouched, no `≈`, no ledger entry, new pane runs zsh"**; the write path is proven in the container e2e. choice 0.83 (untouched_no_drift_plus_pane).

#### Stale text (no behavior change)
- **D-30: Dated amendments for text that predates 23.1/23.2:** SPEC Background (herdr pair landed), CONTEXT Prerequisites, D-10's map name, the Discretion "skill pack" item, the ponytail code reference, `present_harnesses`' location; ROADMAP criterion 3 ("the asked keybindings" → applied at install with no question), ROADMAP 999.11 notes (step 7 "ask before applying" and the herdr `skill_pack` layer); REQUIREMENTS ONB-02 (image ownership, needs confirmation), ONB-03 (carries TUNE-04) and ONB-07 (install tuning). Analyzer, Confident.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. The `cargo_distrobox` kind, its precedence, and fake-runner tests.
  2. Alacritty data and artifacts, `desktop_entry`, terminal plus TOML guard.
  3. herdr with its hooks~~, skill pack~~ and indicators. *(amended 2026-11-07: no skill pack)*
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
- *(added 2026-11-07)* `.planning/phases/23.1-host-safety-drop-the-skill-pack-catalog-entries-sandboxed-te/23.1-CONTEXT.md` (D-01, D-02, D-16..D-22, D-26) and `.planning/phases/23.2-install-time-tuning-instead-of-policies-knobs/23.2-CONTEXT.md` + `23.2-SPEC.md` (D-01, D-03, D-04, D-08, D-19, D-20..D-23; TUNE-04)
- *(added 2026-11-07)* `installer/postinstall.py` (`_HERDR_TARGETS`, `HOST_CATALOG_IDS`), `installer/terminal_shell.py`, `installer/app.py` (`_after_removal`), `installer/session.py` (`_resync_hooks`), `scripts/container-e2e-verify.sh`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `resolve.py` `_RANK`/`_applies`/`_rejection`; `platform.Platform`
- `executors._opt_pkg_list`; `run.Runner`/`run_output`/`CommandError`
- `terminal_shell._replace_owned_region`/`sync_terminal_shells`
- `registry.toml`: the WezTerm raw method (:2630-2635), ~~the ponytail skill pack (:2807-2868)~~ *(deleted by 23.1 D-02)*, the Alacritty entry and comment (~:2655; `:2944-2963` on 2026-11-07, no `config_paths` yet — D-23)
- `scripts/container-e2e-verify.sh` (`cmd_pass2`, `accumulate_summaries` :254-273, `SUMMARY_RE` :222)

### Established Patterns
- Multi-step executors guarantee cleanup themselves (`try/finally`).
- Platform facts are re-read each pass; `resolve.py` is the one switch for availability and reasons.
- TOML writes go through a guarded splice and a `tomllib` re-parse.

### Integration Points
- `cargo_distrobox` → `artifact_paths` → receipt → `removal_plan` L2
- `herdr-integrations` hook ↔ `receipt.hooks` ↔ `present_harnesses` *(in `installer/postinstall.py` after 23.1 D-01)* ↔ `HOST_CATALOG_IDS` / `_resync_hooks` (D-21)
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
- *2026-11-07 run:* `todo.match-phase 24` returned 17 matches (16 at ≥ 0.4), all on keyword overlap; none adds work inside this phase's SPEC boundary, so none is folded. Cask root hand-off (0.9: lifecycle, not herdr/Alacritty), pnpm Doctor shims, Playwright Chrome, pi repair, xcode-clt, iTerm2, Apple containers, Bruno, AWS CLI, compose research, copilot (23.2 TUNE-06), gh-stack, the 80×20 layout gaps, the flaky reinstall test, the pnpm resolved path (23.2 TUNE-07), ai-kit context tools (0.4).
- *Added 2026-11-07:* kitty/WezTerm/Konsole regions are still reverted only when zsh goes, not when the terminal is uninstalled (none is a catalog tool with a removal today); aligning them with D-22 is outside this phase.
</deferred>
