# Phase 24: Onboarding through the skill and e2e - Research

**Researched:** 2026-11-08
**Domain:** Python installer internals (method kinds, receipts, terminal sync, hooks), Distrobox/cargo source build, herdr and Alacritty upstream contracts, bash container e2e harness, Agent Skill scoring
**Confidence:** MEDIUM overall. HIGH for in-repo wiring and upstream file formats (all read or fetched this session). LOW for nested rootless podman + distrobox feasibility and for what `herdr integration uninstall` leaves behind (neither can be probed under the run rules).

<user_constraints>
## User Constraints (from CONTEXT.md)

Copied from `24-CONTEXT.md` (decisions D-01..D-31, assumptions mode, updated 2026-11-07). Only the locked text that changes how the planner works is repeated verbatim here; the CONTEXT file stays the authority for every other word.

### Locked Decisions
- **Decision rule:** best over easy, with the jev ladder.
- **D-01:** `METHOD_PARAMS["cargo_distrobox"]` has these params: `repo` (git URL); `version` source: the GitHub release tag; `packages`: a closed string list of build dependencies, in the `_opt_pkg_list` shape; `artifacts`: a **list of tables** `[{box = "...", host = "..."}]` validated at load. Not parallel lists. Host paths must sit under `~/.local` or `~/.config` (SPEC constraint).
- **D-02:** The executor owns `create -> build (cargo at the tag, plus the in-box steps) -> copy to staging` inside `try`. Its **`finally` always** runs `distrobox rm --force <name>` and then removes the image, even on failure, and re-raises afterwards. Name `ti-cargo-<tool>-<pid>-<rand>`. Each step has a bounded timeout. The engine does no cleanup, so the executor must. Refined: the image is removed only when this run pulled it, and never with `--force` (D-19, needs confirmation); the box uses `--home <run temp dir>` + `--no-entry` and is removed with `--rm-home` (D-20).
- **D-03:** Staging comes first. `smoke()` runs on the staged binary, then the files are placed with `replace_symlink`/atomic moves. `download.artifact_paths(method)` gains a `cargo_distrobox` branch that reads the `artifacts` host paths, so install, receipt and removal share one formula.
- **D-04:** Update by rebuild. The GitHub tag is the version source (the 7-day TTL path); a newer tag means OUTDATED; `u` rebuilds that tag, replaces the artifacts and rewrites the receipt. `~/.config/alacritty` is never touched; a checksum test proves it.
- **D-05:** Precedence goes through `resolve.py`'s one switch (`_RANK`, `_applies`/`_rejection`). New `Platform.has_distrobox`/`has_podman` fields are re-read each pass, following 19 D-14's `has_brew`. `cargo_distrobox` ranks ahead of the native kinds on Linux. Immutable without both tools: UNAVAILABLE "needs distrobox and podman". Mutable without both: the native method, a MANUAL handoff. macOS: UNAVAILABLE with the existing reason.
- **D-06:** A small pure module `installer/desktop_entry.py` renders `.desktop` files (Exec/TryExec = installed absolute binary, the icon; writes through `atomic_write_text`). Entry, icon and terminfo tree are `artifacts` (receipt-proven, removable).
- **D-07:** `tic -xe alacritty,alacritty-direct -o <box dir>` runs **inside the box**; only the compiled tree is copied to the host. No host `tic`/ncurses dependency. Acceptance: `infocmp alacritty` resolves through it, and `desktop-file-validate` passes; both are checked in the container step.
- **D-08 / D-23:** Alacritty is a branch of `sync_terminal_shells` (shell region: shell, `SHELL`). Keybindings (Alt/Option word navigation, clear scrollback) are Alacritty's own install tuning in a second owned region, written by an Alacritty `post_install` action through 23.2's per-row dispatcher whether or not zsh is present. TOML guard per region: scan outside the region for conflicting tables; if found write nothing and show `≈` "partial: you already define X"; re-parse with `tomllib` after writing and roll back on failure. Removing Alacritty strips both regions and keeps the file and the user's keys. The Alacritty entry gains `config_paths = ["~/.config/alacritty"]`. A hand-deleted keybindings region is the user's choice (no `≈`); the shell region keeps `≈`.
- **D-08b:** herdr is another branch of `sync_terminal_shells`; applies only when `herdr` and zsh both resolve through `_safe_executable(lookup(...))`. Writes `default_shell = "<abs zsh>"` under `[terminal]` **only when the key is absent**, never a second `[terminal]` header; re-parse with `tomllib`, roll back on failure; record in the 23 D-08 ledger; then `herdr server reload-config`, best effort. A user-set value (any) is never overwritten; if not zsh show `≈` "partial: you already set terminal.default_shell". Revert: herdr uninstall or zsh going away removes only the ledgered key and only if it still holds the written value.
- **D-09:** herdr gets `github_release` methods with `raw = true`, per OS/arch, tier `user`, `audience = "both"`; no checksum file, so API digests apply.
- **D-10 / D-21 / D-27 / D-28:** `herdr-integrations` is a `(register, unregister)` hook. `_HERDR_TARGETS` is extended to every host present in both `HARNESS_MARKER_DIRS` and herdr's live target list (pi, copilot, kilo, kimi, qwen, devin, grok, hermes, factory-droid to droid); an ambiguous id (antigravity/gemini-cli to `antigravity-cli`) is left out with a comment; `HOST_CATALOG_IDS` gains `pi` and `copilot`. `register` records only hosts whose integration was "not installed" or "needs repair" before it ran (a read-only `herdr integration status` probe); a host already "current" is user-owned and never removed. The full uninstall unregisters herdr's integrations before the agents' ledger keys revert; the e2e asserts key values, not bytes, for files herdr touched.
- **D-12:** The **separator and current indicator** from herdr-setup are in scope, only these two (no accent/theme). A named hook; writes the `rows` arrays and `row_gap` only when absent; reload; ledger; removal reverts only what was written. Pinned source `castocolina/herdr-setup@2b5ca2a`; the plugin needs `python3`: when absent the hook writes nothing and the row names the reason.
- **D-13 / D-24:** skill-judge baseline is a **fresh run at the start of this phase** on the skill as 23.2 left it (23.2's after-score noted beside it); rewrite step 4b (anchor on the `### 4b.` heading); the final score must be >= the baseline; this phase's edit keeps 23.2's TUNE-04 text verbatim; the §7 terminal bullet is updated; "skill packs" prose goes. Acceptance: `rg -n "Policies"` shows the rule and `rg -n -i "skill.pack|skill_lifecycle"` finds nothing.
- **D-14 / D-25 / D-26 / D-31:** `scripts/container-e2e-verify.sh` gets `--distro {fedora,debian,arch}` threaded through every subcommand with one per-distro table (image, root prerequisites, release record); everything else shared. The rerun pass accepts skipped or blocked rows plus `manual` rows whose tool set equals pass 1's manual set; any installed, updated, reconfigured, repaired row fails. A tool the resolver offers but that cannot run on one distro is excluded through the distro's table entry and listed with its reason. 23.1/23.2 assertions live in shared `cmd_pass1`/`cmd_pass2`.
- **D-15:** a planted leftover fails the run.
- **D-17 / D-29:** the real-host UAT (`24-UAT.md`) is the only manual step: Owner filled on every tier after install, `○` after Uninstall; herdr line: user `default_shell` untouched, no `≈`, no ledger entry, a new pane runs zsh.
- **D-18:** The one real Alacritty build runs inside a disposable container with its own nested rootless podman and distrobox, never on the host's podman. Feasibility is a plan-time research item; if infeasible, the real build is recorded during the user's own `24-UAT.md` run, never by an agent on the host's podman.
- **D-19 (needs confirmation):** the executor removes the image only when this run pulled it (`podman image exists <ref>` before create); never `podman rmi --force`.
- **D-20:** `distrobox create --home <run temp dir> --no-entry ...` and `distrobox rm --force --rm-home`; the fake-runner argv acceptance asserts the three flags.
- **D-22:** this phase adds **no Policies row**. Shell lines (Alacritty's shell region, herdr's `default_shell`) stay branches of `sync_terminal_shells`, written by `_sync_terminals`, repaired by the `terminal_sync` drift step, reverted when zsh goes and, new, when the terminal tool itself is removed (a terminal branch in `app._after_removal`). `sync_terminal_shells` gains an injected runner for `herdr server reload-config`.
- **D-30:** dated amendments for stale text (SPEC Background, CONTEXT Prerequisites, D-10 map name, ROADMAP criterion 3, 999.11 notes, REQUIREMENTS ONB-02/03/07).

### Claude's Discretion
- Plan and wave order (suggested: 1 the `cargo_distrobox` kind and fakes; 2 Alacritty data/artifacts/desktop_entry/terminal + TOML guard; 3 herdr hooks and indicators; 4 onboarding skill; 5 three-distro e2e and the real build; 6 UAT).
- The exact distrobox flags and the per-distro Alacritty build package names (research).

### Deferred Ideas (OUT OF SCOPE)
- herdr's optional local-first sort and the personal preference keys (separate choices, never bundled).
- Out of scope: a persistent Distrobox or exported apps; other source-built tools; an Alacritty build for macOS; Neovim (24.1); herdr workspace features beyond the separator and indicators; kitty/WezTerm/Konsole removal-time revert; no skill packs; no Policies row.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ONB-01 | herdr user-tier binary + integrations postinstall for present agent hosts, separator/indicators only | herdr release assets and digests verified (Standard Stack); per-target file effects (Pattern 5); status format and D-27 probe; the TOML writer cannot serve nested keys (Pitfall 4); `herdr plugin install --ref` found (Open Question 4) |
| ONB-02 | Alacritty on immutable Bazzite via cargo in a throwaway Distrobox; container and image gone; newer tag shows update; `u` rebuilds; `~/.config/alacritty` untouched | Full wiring list (Architecture), exact distrobox/podman argv and source-verified behaviour (Pattern 1), image/home semantics (D-19/D-20 verified), fakes strategy (Validation) |
| ONB-06 | desktop entry, icon, terminfo under `~/.local/share`, receipt-recorded, removed on uninstall | desktop-file-validate result, quoting rule, terminfo search-path **contradiction** (Pitfall 1, Open Question 1), leaf-vs-file receipt choice (Pattern 2) |
| ONB-07 | Alacritty shell sync + keybindings at install, reverted with the tool | verified Alacritty config keys and default bindings (Pattern 4), region/guard rules, written-once record, `_after_removal` branch |
| ONB-03 | tool-onboarding skill covers lifecycle params + skill-judge | current skill state (stale 4b, `skill packs` line 57 still matches the D-24 grep), rubric format and baseline history 71.2 -> 72.0 |
| ONB-04 | container e2e on Fedora, Debian, Arch: install all, rerun all skipped, uninstall all, leftovers within `config_paths` | harness anatomy, per-distro prereqs, Debian node 20.19.2 vs `min_node = "22.12.0"`, rerun assertion needs new counters, cost estimate |
| ONB-05 | real-host UAT (manual) | UAT checklist, including the real Alacritty build if the nested target is infeasible |
</phase_requirements>

## Summary

Phase 24 is mostly wiring around one new method kind. The in-repo contract (receipts, `removal_plan` L2, `artifact_paths`, the guarded writers, the post-install dispatcher, the e2e harness) already exists and was read end to end. Alacritty renders grey because every method it declares is a native kind (`dnf`/`apt`/`pacman`), and `resolve._applies` returns `False` for native kinds on an immutable host; there is no applicable method, so `unavailable_reason` reports "immutable host". herdr does not exist in the registry at all (grep of `installer/registry.toml` finds no `herdr` entry), although its hook pair (`_HERDR_TARGETS`, `_herdr_register`, `_herdr_unregister`) and the hook name `herdr-integration` are already in `installer/postinstall.py` and `installer/model.py`.

Two verified findings contradict locked text and need a user decision before planning is final. (1) `~/.local/share/terminfo` is **not** on ncurses' search path (system and Homebrew ncurses 6.6.20251230 both fail to find an entry there unless `TERMINFO_DIRS` names it), and Alacritty's own `terminfo_exists` does not check it either, so SPEC R3 / D-07's "`infocmp alacritty` resolves through `~/.local/share/terminfo`" cannot hold; `~/.terminfo` is the user-level location both honour. (2) The existing guarded TOML writer in `installer/agent_settings.py` only supports **top-level bare keys with string/bool values**; herdr's `terminal.default_shell` and the `ui.sidebar.*.rows` arrays are nested, so D-08b and D-12 need a writer extension (or marker regions), which is real scope the plans must carry.

Real container proof of the Distrobox build is the riskiest item. Nested rootless podman plus distrobox on an SELinux-enforcing host cannot be probed from this session (run rules), so its feasibility is UNVERIFIED; the plan must time-box a first spike and keep D-18's fallback (the user's own UAT run). Everything else in the phase is testable with fake runners under the 23.1 sandbox without widening its allowlist, because `desktop-file-validate`, `infocmp`, `tic`, `podman`, `distrobox`, `cargo`, `git` and `curl` are not (and must stay not) launchable from unit tests.

**Primary recommendation:** Implement `cargo_distrobox` as its own module (`installer/cargo_distrobox.py`) called from `engine._perform` and `update._update_installer_owned` with an `ExecContext`, using `distrobox create --home <tmp>` so the build output is read from the host-side temp dir (no in-box `cp`), `leaf` receipt artifacts for the desktop entry, icon and terminfo files and a `file` artifact for the binary; settle the terminfo location and the TOML-writer extension with the user first.

## Architectural Responsibility Map

The app is a Python TUI/CLI installer, so tiers are the repo's own layers rather than web tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Method availability and ranking for Linux/macOS/immutable | Resolver (`installer/resolve.py`, `platform.py`) | Catalog render (`unavailable_reason`) | `.claude/architecture.md` rule "one switch"; `_rejection` must mirror `_applies` (parity test) |
| Registry data (params, artifacts, `config_paths`, versions) | Registry/model (`registry.toml`, `model.py` closed `METHOD_PARAMS`) | verify-registry | Data is validated at load; unknown keys rejected |
| Build in a throwaway box, staging, atomic placement | Executor module (new `installer/cargo_distrobox.py`) | `engine._perform`, `update._update_installer_owned` | Multi-step executors own their cleanup (try/finally); engine does none |
| What a method created (placement, receipt, removal) | `download.artifact_paths` (one formula) | `receipts.record`, `uninstall.removal_plan` L2 | D-07: install, receipt and removal share one formula |
| Version source and update decision | `version_status.github_repo` + `resolve_github_release_status` | `update.perform_update` | Owner `installer` + GitHub tag path |
| Desktop entry text | `installer/desktop_entry.py` (new, pure) | executor stages and places it | Single-purpose pure module; testable without a desktop |
| Alacritty shell region, herdr `default_shell` | `terminal_shell.sync_terminal_shells` | `setup._sync_terminals`, `app._after_removal`, `terminal_sync` drift step | D-22: no Policies row |
| Alacritty keybindings region | `post_install` action dispatched by 23.2's per-row dispatcher | `version_status._tuning_fact`, `session._install_tuning_step` | D-23, TUNE-04 |
| herdr integration registration | `postinstall.py` hook pair | `receipts.record_hooks`, `session._resync_hooks` | Phase 23 contract; D-21/D-27 |
| Three-distro proof and leftovers | `scripts/container-e2e-verify.sh` | `tests/test_container_e2e_receipts.py` (host-side function tests) | Containers only; host never mutated |
| Onboarding knowledge | `.claude/skills/tool-onboarding/SKILL.md` | `tests/test_docs.py` | Process aid, scored by skill-judge |

## Standard Stack

No new Python, npm or crates dependency is added by this phase. Everything below is already in the project or is an upstream tool the executor drives.

### Core
| Library / tool | Version | Purpose | Why standard |
|----------------|---------|---------|--------------|
| Python stdlib `tomllib` | project Python (3.11+ features already used in `installer/agent_settings.py:16`) | re-parse guard after every TOML write | Already the guard in `agent_settings` and `verify_registry`; no TOML writer dependency |
| distrobox | 1.8.2.5 on the host [VERIFIED: `distrobox version` run this session] | throwaway build box | User's O5 decision; Bazzite ships it |
| podman | 5.8.9 on the host [VERIFIED: `podman --version`] | image store and `image exists` / `rmi` | distrobox's backend |
| Alacritty source tag | v0.17.0 (published 2026-04-06), MSRV `rust-version = "1.85.0"` [VERIFIED: `gh api` + raw `Cargo.toml`] | what gets built | Latest GitHub release |
| Fedora toolbox image | `registry.fedoraproject.org/fedora-toolbox:44` exists [VERIFIED: registry `tags/list` shows "44"; manifest HEAD returned 200] | box image | Distrobox's own default family; Fedora 44 packages cargo 1.99.1-2.fc44 [CITED: packages.fedoraproject.org/pkgs/rust/cargo] which is above the 1.85 MSRV |
| herdr release assets | v0.9.5 (2026-10-14) [VERIFIED: `gh api repos/herdrdev/herdr/releases/latest`] | raw binaries | `github_release` raw with API digests |

herdr asset names and digests verbatim from the API: `herdr-linux-aarch64`, `herdr-linux-x86_64`, `herdr-macos-aarch64`, `herdr-macos-x86_64` (each with a `sha256:` digest), plus `herdr-windows-x86_64.zip`. The arch token `{arch.machine}` renders `x86_64`/`aarch64` (`installer/assets.py` `_TOKENS`), so two methods cover everything: `asset = "herdr-linux-{arch.machine}"` for `os = ["debian","fedora","arch"]` and `asset = "herdr-macos-{arch.machine}"` for `os = ["macos"]`, each with `member = "herdr"` and `raw = true` (the `yq` entry is the template: `asset = "yq_linux_{arch.deb}"`, `member = "yq"`, `raw = true`). No checksum param (none published): `resolve_target` falls to `release.digests.get(asset)`.

### Supporting
| Tool | Version | Purpose | When to use |
|------|---------|---------|-------------|
| `desktop-file-validate` | 0.28 on the host [VERIFIED] | acceptance check of the rendered entry | Container step only: not launchable from unit tests |
| `tic` / `infocmp` | ncurses 6.6.20251230 (host system and Homebrew) [VERIFIED] | terminfo compile (in box) and resolve check (container) | Container step only |
| `herdr config check` | 0.9.3 `--help`: "Validate config.toml and print diagnostics" [VERIFIED] | acceptance check of herdr TOML we write | Container e2e and UAT |
| `timeout` (coreutils) | system | bound each streamed box step | The `Runner` type has no timeout parameter (Pitfall 7) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `--home <tmp>` and read artifacts host-side | `distrobox enter -- cp` out of the box | `--home` bind-mounts the custom home at the same path (source-verified), so files are already on the host; no extra step to fail |
| `leaf` receipt artifacts for entry/icon/terminfo | `file` (sha256 fingerprints) | `file` drifts to BROKEN if the user edits the entry; `leaf` is type-only and keeps removal proof; `leaf` also has the pre-existing-path guard (SPEC adjacency edge) |
| Marker regions for herdr TOML | extend `agent_settings` TOML splice to nested paths | See Pitfall 4; recommendation below |

**Installation:** none. **Version verification:** versions above were read live (`gh api`, registry tag list, package pages, `--help`); no `npm view`/`pip index` applies.

## Package Legitimacy Audit

No external registry package (npm, PyPI, crates top-level) is installed by this phase's own code, so `gsd-tools package-legitimacy check` was not run. What does get installed is inside the disposable box or the e2e containers, from distro repositories named by upstream docs: Alacritty's INSTALL.md Fedora line `dnf install cmake freetype-devel fontconfig-devel libxcb-devel libxkbcommon-devel g++` [VERIFIED: fetched v0.17.0 INSTALL.md], plus `cargo`, `git`, `ncurses` (tic). Crates come from the tag's own `Cargo.lock`; build with `cargo build --release --locked`.

| Package | Registry | Verdict | Disposition |
|---------|----------|---------|-------------|
| cmake, freetype-devel, fontconfig-devel, libxcb-devel, libxkbcommon-devel, g++ | Fedora repos (named by upstream INSTALL.md) | n/a (distro packages) | Approved as data in the registry entry |
| cargo, git, ncurses | Fedora repos | n/a | `[ASSUMED]` names; confirm in the first real build |

**Packages removed due to SLOP:** none. **Flagged SUS:** none.

## Architecture Patterns

### System Architecture Diagram

```
 registry.toml  [[tool]] alacritty  [[tool.method]] kind=cargo_distrobox
        |  (load_tools validates params, artifacts, host path roots)
        v
 resolve.resolve_methods(tool, Platform{has_distrobox, has_podman, immutable})
        |  _RANK puts cargo_distrobox ahead of dnf/apt/pacman; _applies needs both tools
        +--> applies:    engine._perform --> cargo_distrobox.install(method, ExecContext)
        |                    |
        |       resolve_release(slug) -> tag (validated)         podman image exists <ref>  (seam)
        |                    v
        |       tmp = mkdtemp(0700)  ----> distrobox create --yes --no-entry --home tmp --image <ref> --name ti-cargo-... --additional-packages "..."
        |                    |         distrobox enter -T -nw ti-cargo-... -- git clone --depth 1 --branch <tag> https://github.com/<slug>.git tmp/src
        |                    |         distrobox enter ...  -- cargo build --release --locked --manifest-path tmp/src/Cargo.toml
        |                    |         distrobox enter ...  -- tic -xe alacritty,alacritty-direct -o tmp/terminfo tmp/src/extra/alacritty.info
        |                    v
        |       host: copy tmp/<box paths> -> staging (.new siblings), render desktop entry, smoke(staged binary)
        |                    v
        |       swap all .new -> live (os.replace; rollback on failure) -> receipts.record (file + leaf artifacts)
        |       finally: distrobox rm --force --rm-home NAME ; podman rmi REF (only if pulled by this run) ; rmtree(tmp)
        +--> not applies (mutable, no tools): dnf/apt/pacman --> needs_manual --> MANUAL handoff (sudo text only displayed)
        +--> not applies (immutable, no tools / macOS): UNAVAILABLE row with reason (grey, non-selectable)

 update:  version_status.github_repo(tool) finds the cargo_distrobox method -> latest tag vs `alacritty --version`
          -> OUTDATED -> `u` -> update._update_installer_owned -> cargo_distrobox.update (same function, rebuild + swap + re-record)
 removal: uninstall.removal_plan -> receipt proof = receipt artifacts ∩ artifact_paths -> unlink leaf/file, receipt deleted
 tuning:  post_install action (alacritty keybindings region) at install; terminal sync (shell region); both stripped by app._after_removal
 e2e:     container-e2e-verify.sh --distro X : bootstrap -> pass1 -> pass2(rerun [skipped|blocked|same manual], uninstall, leftovers, reinstall)
```

### Recommended Project Structure
```
installer/
├── cargo_distrobox.py      # NEW: install/update, argv builder, box name, image-pulled tracking, staging swap
├── desktop_entry.py        # NEW: pure render of Alacritty.desktop (Exec/TryExec/Icon, quoting)
├── resolve.py              # _RANK, _applies, _rejection, _method_short, _supported_oses
├── platform.py             # has_distrobox, has_podman (default False) + detect()
├── model.py                # METHOD_KINDS, METHOD_PARAMS, load-time validation, POST_INSTALL_ACTIONS
├── download.py             # artifact_paths branch for cargo_distrobox
├── engine.py               # _perform branch, _manager_method exclusion, smoked_artifact
├── update.py               # _update_installer_owned branch
├── version_status.py       # github_repo accepts the kind; re-read has_* at :1438 and :1605
├── ownership.py            # _INSTALLER_KINDS, _INSTALLER_KIND_LABELS
├── terminal_shell.py       # alacritty + herdr branches, revert, injected reload runner
├── post_install.py         # new tuning action for the Alacritty keybindings region
├── postinstall.py          # _HERDR_TARGETS, HOST_CATALOG_IDS, status probe (D-27)
└── registry.toml           # herdr entry, alacritty entry rewritten
scripts/container-e2e-verify.sh   # --distro table, rerun assertion, nested target
tests/test_cargo_distrobox.py, tests/test_desktop_entry.py   # NEW
```

### Pattern 1: the `cargo_distrobox` executor (verified flag semantics)

**What:** one function installs and updates. It resolves the tag, creates a box whose HOME is a host temp dir, builds, stages, places, and always cleans.

Source-verified behaviour of the installed distrobox 1.8.2.5 (`/usr/bin/distrobox-create`, `-enter`, `-rm` read this session, no container created):
- `create` writes `--env "HOME=${container_user_custom_home}"` and `--volume "${container_user_custom_home}:${container_user_custom_home}${rslave}"` for `--home`. The real HOME is **still bind-mounted** (`--volume "${container_user_home}":"${container_user_home}"` is unconditional, plus `/var/home/<user>` on ostree) and `/tmp` is mounted. So `--home` only redirects `$HOME`; it does not hide the real home. Files written under the custom home appear at the same path on the host.
- `--no-entry` sets `container_generate_entry=0`, skipping `distrobox-generate-entry` after create. `--yes` ("non-interactive, pull images without asking") pulls a missing image without asking. A `--dry-run` is **not** safe to use for exploration: `generate_create_command` runs `podman run --rm --userns=keep-id:size=65536 <image> /bin/true` in rootless mode and so can pull and start a container.
- `enter` creates a FIFO at `${XDG_CACHE_HOME:-$HOME/.cache}/distrobox/.NAME.fifo` on the **host** while it waits for init, and removes it afterwards. Pass `XDG_CACHE_HOME=<tmp>/cache` in the child env (via an `env` argv prefix) or `~/.cache/distrobox` is left behind (`.cache` is in the e2e residue allowlist, but the real host should not be littered).
- `enter` runs `${container_manager} start` and the init (including `--additional-packages` installs) on the **first** enter, then `exec`s `podman exec`, so the in-box command's exit code is the command's. `--no-tty/-T` exists; it also auto-enables when stdin/stdout is not a TTY. `--no-workdir/-nw` starts in the box home, avoiding the `/run/host$PWD` mapping.
- `rm --force --rm-home`: `--force` skips the prompt, `--rm-home` removes the mounted home only when it differs from the host user's. It ends with `podman rm --force --volumes NAME`.

Recommended argv (all through the injected `Runner`; every element a separate list item, no `sh -c` with data):
```
distrobox create --yes --no-entry --home <tmp> --image registry.fedoraproject.org/fedora-toolbox:44 \
    --name ti-cargo-alacritty-<pid>-<rand> --additional-packages "<space-joined packages>"
distrobox enter --no-tty --no-workdir --name <name> -- git clone --depth 1 --branch <tag> -- https://github.com/<slug>.git <tmp>/src
distrobox enter --no-tty --no-workdir --name <name> -- cargo build --release --locked --manifest-path <tmp>/src/Cargo.toml
distrobox enter --no-tty --no-workdir --name <name> -- tic -xe alacritty,alacritty-direct -o <tmp>/terminfo <tmp>/src/extra/alacritty.info
distrobox rm --force --rm-home <name>
podman rmi <image>                       # only when `podman image exists <image>` was false before create
```
`tic -o <dir>` fails with `errno 2` when `<dir>` does not exist [VERIFIED: ran it in a scratch dir, see Pitfall 3], so the host must `mkdir <tmp>/terminfo` first. The tag comes from the GitHub API (`tag_name`): validate `^[A-Za-z0-9._-]+$` and not starting with `-`, and pass `--` before the URL, so a hostile tag cannot become a git option. `cargo build` with `--locked` uses the tag's own `Cargo.lock` (Alacritty ships one [ASSUMED: not opened; `--locked` fails loudly if absent]).

`Runner` is `Callable[[list[str]], None]` (`installer/run.py:18`) with no env or timeout parameter. Use an `env XDG_CACHE_HOME=... ` prefix for the env and `timeout --kill-after=10 <seconds>` as an argv prefix for the bounded timeouts D-02 asks for (coreutils; `run_output`/`run_query` have `timeout=` but are non-streaming query helpers). `podman image exists` is a query with a meaningful exit code, so it needs its own seam: follow the module-level replaceable callable precedent (`launch_puppeteer`, `installer/executors.py:356-358`), e.g. `image_exists: Callable[[str], bool]`.

**Why a new module and `ExecContext`:** `executors.execute(method, runner)` has no release resolver. `download.install_download` receives `ExecContext(runner, platform, resolve_release)` and `engine._perform` branches on kind before the generic `executors.execute`; `update._update_installer_owned` does the same. `cargo_distrobox.py` imports from `download`/`atomic`/`executors` and is imported by `engine`/`update`; keep it out of `executors.py` to avoid the `download -> executors` import cycle.

**Staging swap:** copy each box output to a `.tools-installer.new` sibling of its live path (`atomic.staged_sibling(path, NEW_SUFFIX)`, the `_replace_raw` recipe: `shutil.copy2`, `chmod 0o755` for the binary, `smoke_binary(new, argv)` for the binary, `os.replace`). For several artifacts, stage all first, then swap all; on a failure part-way restore the earlier swaps from `.old` siblings (a reduced `_replace_archive`/`_undo_archive_swap`). The old receipt stays until the last swap succeeds (SPEC edge "an interrupted copy leaves the old receipt and the old files"). `smoke_binary` removes `DISPLAY`/`WAYLAND_DISPLAY`, so `alacritty --version` is a safe default smoke (`method_smoke_argv` default is `("--version",)`).

### Pattern 2: wiring checklist for a new kind (every place a kind appears, read this session)

| File | What changes |
|------|--------------|
| `installer/model.py:26-41, 44-102` | `METHOD_KINDS` gains `"cargo_distrobox"`; `METHOD_PARAMS` gains its closed key set; load-time validation block (the `if kind == ...` chain at `:583-700`) validates `artifacts` as a non-empty list of `{box, host}` tables (empty list rejected, empty `packages` allowed, SPEC held-out test), `box` relative with no `..`, `host` under the allowed roots (see Pitfall 1), `image` and `repo` shapes, `packages` as a list of strings matching a package-name regex |
| `installer/resolve.py` | `_RANK` new entry below 30 and above the native kinds; `_applies` and `_rejection` add a clause in the **same order** (the parity test pins the mirror); `_rejection` needs a new category and `_method_short`/`unavailable_reason` a sentence "needs distrobox and podman"; `unavailable_reason` currently builds `"no method applies here: " + "; ".join(shorts)` when categories differ, which would repeat "immutable host" three times for dnf/apt/pacman: dedupe with `dict.fromkeys` |
| `installer/platform.py` | `has_distrobox: bool = False`, `has_podman: bool = False` (defaults avoid editing the ~296 `Platform(` constructions in tests), set in `detect()` via `shutil.which` |
| `installer/version_status.py:1438, :1605` | both `replace(self._platform, has_brew=self._which("brew") is not None)` sites also refresh the two new fields (D-05) |
| `installer/download.py:284` | `artifact_paths` branch: for each `artifacts` entry, `Artifact(Path(host).expanduser(), "file")` for the binary and `"leaf"` for entry/icon/terminfo files (`Artifact.kind` is `Literal["dir","link","file","tree","leaf"]`, `download.py:281`) |
| `installer/engine.py:38, 139, 310` | `_manager_method` must exclude the new kind (it would otherwise `shutil.which`-smoke after install); `_perform` branch; `smoked_artifact` must be true for it so `receipts.record(smoke="ok")` is honest |
| `installer/update.py:419-450` | `_update_installer_owned` branch calls the same function |
| `installer/ownership.py:156, :1323` | `_INSTALLER_KINDS` adds the kind; `_INSTALLER_KIND_LABELS` gets a human label (a kind absent from the labels renders the generic "installer artifact") |
| `installer/version_status.py:275` | `github_repo` currently skips every method whose kind is not `"github_release"` (`if method.kind != "github_release": continue`); accept the new kind (its slug param). `:1309` (adoption) assumes `resolve_target` and `raw`; guard it by kind |
| `installer/uninstall.py` | nothing for removal: `_receipt_proof` allows `(path, kind)` pairs from `artifact_paths` for the receipt's method kind, and `remove_paths` unlinks `file`/`link`/`leaf` only. The no-receipt layout fallback (`plan_removal`) is download-kinds-only, so a cargo_distrobox tool without a receipt removes nothing, which is correct |
| `installer/receipts.py:430` | no change: `record` drops a `leaf` that pre-existed unless the previous receipt proved it |
| `installer/render.py:665` | `verified_kinds = DOWNLOAD_KINDS + APP_KINDS` decides a "verified" word; the new kind is not checksum-verified, leave it out |
| `installer/verify_registry.py:90` | `CHECKABLE_KINDS` only if the repo pin should be checked by `make verify-registry`; optional |
| `docs/catalog-unsupported-tools.md:9-11` | the "Alacritty on immutable Fedora" section becomes false; rewrite or remove (`tests/test_docs.py` scans `docs/**/*.md`) |

### Pattern 3: receipts and removal for the Alacritty artifacts
`record()` fingerprints `artifact_paths` after the swap. A `file` stores sha256+size+mtime (drift is BROKEN, `receipts.broken_drift`), a `leaf` is type-only (`_leaf_matches`: a regular file proves by type alone, with the documented shortcut that another installer's file at that path also matches). Removal of a `leaf`/`file` is `artifact.path.unlink()` after `receipts.matches` re-check. Consequences: the binary as `file`; the desktop entry, icon and the two terminfo files as `leaf` so a user's edit to the entry does not turn the whole receipt to drift and refuse the uninstall. `remove_paths` never removes parent directories, so after uninstall `~/.local/share/terminfo/a/` (or `~/.terminfo/a/`) and the icon theme dirs stay as empty directories. The e2e `home_listing` skips only **empty** dirs, so a parent holding an empty child is printed and counted as a new leftover (Pitfall 6).

### Pattern 4: Alacritty config keys (verified from the v0.17.0 man pages, downloaded as untrusted text)
- Location: `$XDG_CONFIG_HOME/alacritty/alacritty.toml`, `$XDG_CONFIG_HOME/alacritty.toml`, `$HOME/.config/alacritty/alacritty.toml`; "Alacritty doesn't create the config file for you". Use `_xdg_config_home(home, environ)` and the `_wezterm_config_path` shape (first existing of the three, else the first).
- Shell: `shell = { program = "/bin/zsh", args = ["-l"] }` under `[terminal]` (man: `**shell** = "<string>" | { program = "<string>", args = ["<string>",] }`; example `shell = { program = "/bin/zsh", args = ["-l"] }`; default is `$SHELL` or the login shell). Equivalent valid table form: `[terminal.shell]` with `program` and `args`.
- Env: `[env]` table, "added as environment variables for any process spawned by Alacritty, including its shell".
- Bindings: `[[keyboard.bindings]]` with `key`, `mods`, `mode`, and `action` or `chars`. Linux defaults list `Control|Shift` C/V/F/B, `Shift+Insert`, `Control` plus `0`/`=`/`+`/`-` font keys: **no `Control|Shift+K`**; `ClearHistory` is bound by default only on macOS (`Command+K`), so a Linux binding is a pure addition.
- Region body (TOML 1.0-safe, use `\u001b`, not `\e`; the man page cites TOML v1.0.0):
```toml
[[keyboard.bindings]]
key = "Left"
mods = "Alt"
chars = "\u001bb"

[[keyboard.bindings]]
key = "Right"
mods = "Alt"
chars = "\u001bf"

[[keyboard.bindings]]
key = "K"
mods = "Control|Shift"
action = "ClearHistory"
```
(`\u001bb`/`\u001bf` are readline backward-word/forward-word; the man page shows `chars = "\u000c"` as the escape style. The Alt+arrows byte strings are `[ASSUMED]` standard readline sequences, not tested in a real terminal: put them in the UAT.)
- Marker region: `terminal_shell._replace_owned_region(content, terminal, body, comment="#")` already works for `#`-comment files; use two terminal names (e.g. `alacritty` for the shell region, `alacritty-keys` for the keybindings) so `_marker` text differs.
- TOML conflict rules the guard must implement (content **outside** the region, parsed with `tomllib`): shell region conflicts if `terminal.shell` exists in any form; its `[env]` part conflicts if any `env` table exists (a second `[env]` header is invalid TOML and a dotted `env.SHELL` cannot be added after a later `[env]`), so write the `[terminal.shell]` part and report "partial: you already define env" for SHELL. Keybindings `[[keyboard.bindings]]` is an array of tables and merges with the user's own, except when the user wrote `keyboard.bindings = [...]` inline (conflict, `tomllib` re-parse after writing catches it and the writer rolls back). A user entry for the **same key and mods** (for example their own `Alt+Left`) is a semantic conflict the parser does not see: scan parsed `keyboard.bindings` for equal `(key, mods)` and skip that binding with the "partial" reason.
- The shell/`SHELL` part is redundant for zsh-launched shells because the `.zshenv` block already exports `SHELL` (`zshenv_block`); `[env] SHELL` matters for non-shell children. Keep it (D-08) but guarded as above.

### Pattern 5: herdr integration facts (docs fetched from the v0.9.5 tag; host binary is 0.9.3)
`herdr integration install <TARGET>` accepts [VERIFIED: `herdr integration install --help`, 0.9.3]: pi, omp, claude, codex, copilot, devin, droid, kimi, opencode, kilo, hermes, qodercli, qwen, cursor, mastracode, antigravity-cli, grok, letta. `herdr integration status` prints one line per target, [VERIFIED live output]: `claude: current (v10) (/home/bazzite/.claude/hooks/herdr-agent-state.sh)`, `opencode: needs repair (v13) (...)`, `pi: not installed (...)`, `letta (experimental): not installed (...)`. Parse with a regex on `^(\S+?)(?: \(experimental\))?: (not installed|current|needs repair)`.

Per-target writes beyond herdr's own script, [CITED: raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/integrations.mdx]:

| Target | Files written | Edits an agent main config | Uninstall |
|--------|---------------|----------------------------|-----------|
| claude | `~/.claude/hooks/herdr-agent-state.sh` | `settings.json` hook entries (config dir "must already exist") | removes entries and the script |
| codex | `~/.codex/herdr-agent-state.sh` | `hooks.json` entries and `config.toml` `[features] hooks = true` | removes `hooks.json` entries and the script, **leaves `config.toml` unchanged** |
| opencode | `plugins/herdr-agent-state.js`, `herdr-tui-session.js`, `herdr-opencode/tui.js` | registers in `tui.jsonc`/`tui.json` and `cli.json` | removes registrations (keeps the files), removes managed plugin files |
| cursor | `~/.cursor/herdr-agent-state.sh` | `sessionStart` entry in `hooks.json` | removes entry and script |
| pi | `~/.pi/agent/extensions/herdr-agent-state.ts` | none | removes that file |
| copilot | `~/.copilot/hooks/herdr-agent-state.sh` | `SessionStart` entry in `settings.json` | removes entries and script |
| kilo | `~/.config/kilo/plugin/herdr-agent-state.js` | none | removes that file |
| kimi | `hooks/herdr-agent-state.sh` | appends `[[hooks]]` block to `config.toml` | removes block and script |
| qwen | `hooks/herdr-agent-session.sh` | entry in `settings.json` | removes entry and script |
| devin | `herdr-agent-state.sh` | entries in `config.json` | removes entries and script |
| grok | `hooks/herdr.json`, `hooks/herdr-agent-state.sh` | none | removes both files |
| hermes | `plugins/herdr-agent-state/` | enables the plugin in `config.yaml` | removes dir and the enable entry |
| droid | `hooks/herdr-agent-state.sh` | `SessionStart` in `settings.json` (`~/.factory`) | removes entries and script |

Merge-safety answer (D-10): yes, integrations edit the agents' main config for claude, codex, copilot, cursor, opencode, kimi, qwen, devin, hermes, droid. `copilot`'s `settings.json` is the **same file** 23.2's copilot tuning writes (`("copilot","auto-approve")` -> `defaultPermissionMode`, `("copilot","no-attribution")` -> `includeCoAuthoredBy`, `AGENT_FORMATS["copilot"] = "jsonc"`), as are claude's `settings.json` and codex's `config.toml`. Both writers do splice edits and re-parse, so interleaving is safe in principle; the order (D-28: unregister herdr first, then revert the ledger) matters for the "file left" probe. What the integration leaves after uninstall (empty `hooks` containers; codex `config.toml` keeps `[features] hooks = true`) is **UNVERIFIED**: it cannot be observed without running `integration install`, which is forbidden on the host, so the first container run is the experiment and the e2e probe must compare key values, not file existence (see Pitfall 5).

herdr's runtime footprint on this host (read-only listing): `~/.config/herdr/` (`config.toml`, `herdr-client.log`, `herdr-server.log`, `herdr.sock`, `session.json`, `session-snapshots/`, `.plugins.lock`, `release-notes.json`) and `~/.local/state/herdr/` (`agent-detection`, `client-shell`). Declare `config_paths = ["~/.config/herdr", "~/.local/state/herdr"]` (both pass `_config_path_flaw`: >= 2 levels, not a shared dir, not under a harness marker).

herdr plugin (D-12): `herdr plugin install [OPTIONS] <OWNER/REPO[/SUBDIR]>` with `--ref <REF>` and `-y/--yes` exists [VERIFIED: `herdr plugin install --help`], as do `plugin link <PATH>`, `unlink <PLUGIN_ID>`, `uninstall`, `list`. The pinned source tree at `castocolina/herdr-setup@2b5ca2aedf06a5a988a5087da22e65b469ffc84d` [VERIFIED: `gh api`] holds `plugins/workspace-here/herdr-plugin.toml` with `id = "herdr-setup.markers"`, `min_herdr_version = "0.9.0"`, `platforms = ["linux", "macos"]`, startup/event commands `["python3","mark.py"]`. `herdr plugin install castocolina/herdr-setup/plugins/workspace-here --ref <sha> --yes` would let herdr fetch and manage the pinned copy itself (no vendored files, no `link`), with `herdr plugin uninstall herdr-setup.markers` as the undo. Whether `--ref` takes a full commit SHA and what files it writes where is UNVERIFIED (not runnable here): flag for the user (Open Question 4).

### Pattern 6: install-tuning dispatch for the Alacritty keybindings region (23.2 mechanics, read this session)
The dispatcher is closed: `POST_INSTALL_ACTIONS` (`model.py:125`) and `POST_INSTALL_HOOKS` (`post_install.py:281`), plus `apply_install_tuning` (`:291-310`), which handles `apply_agent_tuning`, `set_omz_plugins`, `source_shell_init` by name only. A new action (name for the planner, for example `apply_terminal_tuning`) needs: the name in the tuple, a function in the table, a branch in `apply_install_tuning` with `skip_recorded` semantics, a pending-fact branch in `version_status._tuning_fact` (`:652`, currently omz / shell-init / agent), the matching `session._install_tuning_step` behaviour, and a revert in `app._after_removal` (`app.py:679`, which today handles `CONFIG_AGENTS`, shell-init bundles and the `zsh` desktop-shell row). The "written once" record that makes a hand-deleted region the user's choice has no existing home for a non-key file region (the agent ledger is key-based, shell-init uses `.myshellrc`): follow the Konsole precedent, a state file under `_xdg_data_home/tools-installer/` (`terminal-shell-konsole-default`), e.g. `terminal-tuning-alacritty`, written after the region and deleted on removal (it must also be removed or it is a new e2e leftover, `.local/share/tools-installer`).

### Anti-Patterns to Avoid
- **`sh -c` with interpolated tool data** or `shell=True` (bandit; the repo's AST test `tests/test_executors.py:148` rejects list literals starting with `sudo`/`pkexec`/`doas`, and `tests/test_model.py:1851` does the same for registry argv).
- **`podman rmi --force`** or removing an image the run did not pull (D-19); **`distrobox rm` without `--force`** (blocks on a prompt in a non-TTY).
- **Writing `~/.cache/distrobox`** on the real host: set `XDG_CACHE_HOME` for the child.
- **A second `[terminal]` or `[env]` header** in TOML; a `[[keyboard.bindings]]` when the user has inline `keyboard.bindings = [...]`.
- **Running `distrobox create --dry-run`** to "see the command" (it can pull and run a container, see Pattern 1).
- **Putting herdr/Alacritty shell lines in a per-tool `post_install`** (D-22: plan order can run it before zsh exists and make the rerun RECONFIGURE).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unknown-key rejection, host-path rules for artifacts | ad hoc checks in the executor | `load_tools` validation next to `METHOD_PARAMS` (`model.py:574` raises on unknown keys) | Closed registry contract, errors name the tool |
| Atomic multi-file placement | `shutil.move` loops | `atomic.staged_sibling`, `NEW_SUFFIX`/`OLD_SUFFIX`, `os.replace`, `replace_symlink` | Rollback recipe exists in `download._replace_archive` |
| Removal proof | custom "is this ours" checks | `receipts.record` + `uninstall._receipt_proof` + `remove_paths` | Receipt is user-writable JSON; only `(path, kind)` pairs from `artifact_paths` are authority |
| Marker-delimited config regions | new region parser | `terminal_shell._replace_owned_region` (rejects malformed markers) | Already handles missing/duplicate/unbalanced markers |
| TOML validity of what we wrote | string checks | `tomllib.loads` on the whole new text, compared to the expected dict (`agent_settings._guarded` pattern) | Spec-exact; rollback on failure |
| Unique box name | timestamp strings | `f"ti-cargo-{tool}-{os.getpid()}-{secrets.token_hex(4)}"` (D-02) | Collision-proof across concurrent runs |
| Desktop entry quoting | `str.replace` on `Exec=` | `desktop_entry.py` quoting per the Desktop Entry `Exec` rule | A path with a space validates but is wrong unquoted (below) |
| Version-source/update status | a second tag fetcher | `version_status.resolve_github_release_status` with the kind added to `github_repo` | Cache, TTL, backoff, per-pass fetch budget already there |
| Skill scoring | hand score | the `skill-judge` skill (rubric_version 4) | Deterministic protocol and verdict JSON |

**Key insight:** every artifact of this phase is a variation of something the repo already proves (raw release file, script `leaf` paths, marker regions, hook pair). New code should be thin glue plus validation; the dangerous parts are the process cleanup and the TOML edits.

## Runtime State Inventory

Not a rename/refactor/migration phase: omitted. (One live-state note: the host already has herdr 0.9.3 installed by hand with three hand-made integrations and no receipt; D-27 keeps them user-owned, and the user's `[terminal] default_shell` is already set, so the absent-only write applies nothing on this host.)

## Common Pitfalls

### Pitfall 1: terminfo in `~/.local/share/terminfo` is invisible to ncurses and to Alacritty
**What goes wrong:** the SPEC/D-07 acceptance "`infocmp alacritty` resolves through `~/.local/share/terminfo`" fails.
**Why:** verified by experiment in a scratch HOME with a probe terminal name no database contains. With `tic -x -o <home>/.local/share/terminfo` then `HOME=<home> infocmp`: **not found** for both `/usr/bin/tic` and Homebrew's tic (ncurses 6.6.20251230); with `.terminfo` instead: **FOUND**; with `.local/share/terminfo` plus `TERMINFO_DIRS` pointing at it: FOUND. `infocmp -D` lists the compiled-in dirs: `/etc/terminfo`, `/usr/share/terminfo` (system) and the brew Cellar dir. Alacritty v0.17.0's own `terminfo_exists` (`alacritty_terminal/src/tty/mod.rs`) checks `$TERMINFO` or `~/.terminfo`, then `$TERMINFO_DIRS`, `$PREFIX/{etc,lib,share}/terminfo`, `/etc/terminfo`, `/lib/terminfo`, `/usr/share/terminfo`, `/boot/system/data/terminfo`; without a hit it sets `TERM=xterm-256color`. So a terminfo only in `~/.local/share/terminfo` has no effect unless the launching environment exports `TERMINFO_DIRS`.
**How to avoid:** ask the user (Open Question 1). Recommendation: install to `~/.terminfo/a/alacritty` and `.../a/alacritty-direct`, widen the artifact host-root rule from `~/.local`/`~/.config` to also allow `~/.terminfo`, and amend SPEC R3/ONB-06 text. If the user keeps `~/.local/share/terminfo`, the acceptance command must be `TERMINFO_DIRS=$HOME/.local/share/terminfo infocmp alacritty` and the file is cosmetic until something exports that variable.
**Warning signs:** `infocmp alacritty` passes only on a host whose own ncurses package ships the entry (it did here: the brew db has `a/alacritty`), which masks the bug; the container step must test with a fresh HOME and a terminal name or `env -u TERMINFO -u TERMINFO_DIRS`.

### Pitfall 2: `--home` does not isolate the real home
**What goes wrong:** treating the box as sandboxed. The real HOME and `/tmp` are mounted read-write in the box (source above). Only `$HOME` is redirected.
**How to avoid:** the argv must never run a command that writes to an absolute real-home path; keep `cargo`/`git` relative to `<tmp>`; pass `XDG_CACHE_HOME`. This is also why host-side copying from `<tmp>` needs no `distrobox enter`.

### Pitfall 3: `tic -o <dir>` needs the directory to exist
**What goes wrong:** `"...alacritty.info", line 26, terminal 'alacritty+common': <dir>: (errno 2) No such file or directory`, exit 1 [VERIFIED: output pasted from the scratch run]. **How to avoid:** `mkdir -p <tmp>/terminfo` on the host before the in-box `tic`. `tic` writes a first-letter directory (`t/tiprobe24` in the probe), i.e. `a/alacritty` and `a/alacritty-direct` for Alacritty (the compiled files are therefore two leaves, not a tree).

### Pitfall 4: the guarded TOML writer cannot write herdr's keys
**What goes wrong:** `agent_settings._toml_key` raises `"TOML keys are top-level bare keys"` when `len(key_path) != 1`; `_toml_value` accepts only `bool` and `str` (`"TOML values here are strings or booleans"`). `terminal.default_shell` is a two-part key; `ui.sidebar.agents.row_gap` and `rows` (arrays of arrays of strings and inline tables like `{ token = "$rule", dim = true }`) need int and nested values.
**How to avoid:** extend `_insert_toml` to a header-aware insert: add the key lines directly after an existing `[a.b]` header, or append a new `[a.b]` table at the end, with the fragment text as the source of truth and `tomllib.loads(new_text)` compared to the expected dict (reuse `_guarded`); the revert uses the recorded fragment or the located line (`_toml_remove`, extended the same way). Treat each key independently and absent-only, and when a user already defines `ui.sidebar.agents.rows` write nothing and name the tokens (`$rule`, `$here`) to add by hand (D-12). Marker regions are the alternative, but a region must sit inside the right table span, which is the same insertion problem. Validate the result with `herdr config check` in the container.

### Pitfall 5: shared agent config files and "file left" probes
**What goes wrong:** herdr's uninstall removes its entries but may leave `settings.json`/`hooks.json` as `{}`/`{"hooks": {}}` (UNVERIFIED), and codex's `config.toml` keeps `[features] hooks = true` by documented behaviour; the existing `settings_probe_revert` prints `TRACER_SETTINGS_FILE_LEFT` when a settings file still exists and no CLI default was restored, so a correct uninstall can fail the run.
**How to avoid:** D-28 value-level assertions: for files herdr touched, require that no key the installer wrote remains and that no herdr marker (`herdr-agent-state`) remains in the file; tolerate an empty-container residue. Do the unregister argvs before the ledger revert (already the order in `removal_plan` -> `_hook_undo`, then `app._after_removal`; assert it in a unit test). Allowed leftovers: harness marker dirs are already `allowed` in `registry_probe` (`~/.claude`, `~/.codex`, `~/.copilot`, `~/.cursor`, `.config/opencode`, `.pi`, ...); `~/.kimi-code` is a marker, `~/.config/devin`, `~/.grok`, `~/.hermes`, `~/.qwen` are not (their marker tuples are `()`): do not target hosts in the container that would leave an unlisted dir, or add the dir to `config_paths` of the host tool that owns it.
**Status after uninstall:** the herdr binary is removed by the uninstall, so `herdr integration status` cannot be run afterwards. Copy the binary aside before uninstall (`cp ~/.local/bin/herdr /tmp/herdr-probe`) and run the copy after; it reads the same config dirs and should print `not installed` for every target.

### Pitfall 6: empty parent directories after uninstall
**What goes wrong:** `remove_paths` unlinks leaves and never removes parents; `home_listing` prints a directory that contains an empty directory, so `~/.terminfo` (or `~/.local/share/terminfo`), `~/.local/share/icons/hicolor/...` and `~/.local/share/applications` read as leftovers after Alacritty's uninstall.
**How to avoid:** remove now-empty ancestor directories strictly below a declared root, after the unlink (a small, general step; best-effort `rmdir`, never recursive) or declare the roots in `config_paths`. This is a design choice for the planner; the nested-target assertion exercises it.

### Pitfall 7: `Runner` has no timeout and no env
**What goes wrong:** D-02 asks for "bounded timeout through the run.py runner conventions", but `Runner = Callable[[list[str]], None]` and `StreamingRunner` documents "No timeout: a side-effecting install child must be allowed to take". **How to avoid:** `timeout --kill-after=10 <s>` argv prefix per streamed step (create 900, first-enter init plus packages 900, clone 180, build 1800, tic 60, rm 120 are suggested starting values, `[ASSUMED]` not measured), and an `env` prefix for `XDG_CACHE_HOME`. Record the numbers as constants with a comment.

### Pitfall 8: `/tmp` is tmpfs on this host
`findmnt /tmp`: tmpfs, 15.2G size, 13.5G available [VERIFIED]. The Alacritty `target/` plus `~/.cargo` registry land in `<tmp>`. The size is UNVERIFIED (not measured); with `tempfile.mkdtemp` (the repo's own convention, `download.py:393`) it consumes RAM-backed space. Prefer `tempfile.mkdtemp(prefix="tools-installer-cargo-")` and a pre-flight free-space check, and always `shutil.rmtree(tmp, ignore_errors=True)` in `finally` as the backstop for `--rm-home`.

### Pitfall 9: Debian's packaged Node is below the catalog floor
`packages.debian.org/trixie/nodejs` is `20.19.2+dfsg-1+deb13u3` [VERIFIED: fetched]; Arch `extra/nodejs` is `26.13.0` [VERIFIED: archlinux.org search JSON]. The catalog's `node` methods (`mmdc`, and `puppeteer` for amd64) declare `min_node = "22.12.0"` (`registry.toml:2635, 2760, 2769`) and `_require_minimum` probes bare `node`. copilot is no longer a Node case: its methods are now `cask` (macOS), a checksummed `github_release` (Linux) and an ownership-only cask, so the D-26 "first case: copilot" is moot after 23.2. On Debian, mmdc and puppeteer will fail unless a Node >= 22.12 is first on PATH (UNVERIFIED which `node` wins in the run: Fedora's prerequisites install system `nodejs` and `chromium`, `scripts/container-e2e-verify.sh:126-129`). `puppeteer` is category `dev`, `mmdc` is `diagram` (shared with `drawio-desktop`), and `setup.py` has no tool-level exclude (`app._choose_tools` selects `all` or `tool.category in options.categories`), so the "exclude through the distro table" mechanism needs either a small `--exclude` option or a coarse category list that would also drop unrelated tools (Open Question 5). Whichever is chosen, list the excluded tools and the reason in the transcript.

### Pitfall 10: the rerun check does not exist yet
`cmd_pass2` step 1 only requires `install_step_ok` (no failed/crashed rows), and `accumulate_summaries` keeps INSTALLED, UPDATED, SKIPPED, FAILED, DEP_FAILED, MISMATCHED, BLOCKED, MANUAL, NOT_ATTEMPTED, CRASHED but **not** REPAIRED, RECONFIGURED, REINSTALLED, which `parse_summary_line` already parses into `PARSE_*`. D-25 needs three new accumulators and a persisted pass-1 manual set (`ACC_MANUAL_NAMES_FILE` is a `mktemp` removed at the end of `cmd_pass1`; write a sorted unique copy to `$PHASE_DIR/pass1-manual.txt` and compare as sets after the rerun).

### Pitfall 11: `skill packs` still matches the D-24 acceptance grep
`rg -n -i "skill.pack|skill_lifecycle" .claude/skills/tool-onboarding/SKILL.md` returns line 57 today: `... skill packs are not catalog entries since 23.1`. That text must be rewritten (the plan cannot satisfy "finds nothing" by editing only 4b and 7). `rg -n "Policies"` currently shows lines 184, 186, 228, 229 (the rule, to keep verbatim).

### Pitfall 12: desktop entry details
`desktop-file-validate` 0.28 accepts the upstream entry as is, and accepts it after replacing `TryExec`, both `Exec` lines (`[Desktop Entry]` and `[Desktop Action New]`) and `Icon` with absolute paths [VERIFIED: ran in scratch]. It also accepts an **unquoted** `Exec=` path containing a space, which is wrong per the Desktop Entry `Exec` quoting rule (`[ASSUMED]`: spec rule that arguments with spaces are double-quoted with `\` escapes; not fetched): quote in `desktop_entry.py` and reject control characters in the path (the same `_safe_executable` posture). Upstream file text (v0.17.0 `extra/linux/Alacritty.desktop`): `TryExec=alacritty`, `Exec=alacritty`, `Icon=Alacritty`, two `Exec` lines. The icon source is `extra/logo/alacritty-term.svg` (per upstream INSTALL.md `cp extra/logo/alacritty-term.svg /usr/share/pixmaps/Alacritty.svg`); the release also publishes `Alacritty.svg`, `Alacritty.desktop` and `alacritty.info` with sha256 digests as release assets (no Linux binary), a secondary route if copying from the tag checkout is unwanted.

### Pitfall 13: mutable image-is-in-use on `podman rmi`
After `distrobox rm`, the box is gone, so a plain `podman rmi <ref>` of the image this run pulled normally succeeds. If another container uses that image meanwhile, `rmi` fails: report it as a warning on the row ("image kept: in use"), never fail the install, never `--force`.

## Code Examples

Verified/derived patterns. Sources are named per snippet.

### Resolver clause (mirror order, `installer/resolve.py` as read)
```python
# in _applies, after the `kind in ("script", ..., "host_setup")` unconditional block:
if kind == "cargo_distrobox":
    return platform.has_distrobox and platform.has_podman
# in _rejection, same position, before the native/immutable fallback:
if kind == "cargo_distrobox":
    return "tools"   # new category; _method_short -> "needs distrobox and podman"
```
`_RANK` values today: `"script": 10`, `"host_setup": 15`, `"github_release": 20`, ..., `"dnf": 30`, `"apt": 30`, `"pacman": 30`, `"rpm_ostree": 35`, `"brew": 40`, `"cask": 40`; use 25.

### Registry entry shape (derive, do not copy blindly)
```toml
[[tool.method]]
kind = "cargo_distrobox"
os = ["debian", "fedora", "arch"]
arch = ["amd64"]                      # measured on amd64 only; arm64 unverified
repo = "alacritty/alacritty"          # GitHub slug: version source AND clone URL (see Open Question 3)
image = "registry.fedoraproject.org/fedora-toolbox:44"
packages = ["cargo", "git", "gcc-c++", "cmake", "freetype-devel", "fontconfig-devel", "libxcb-devel", "libxkbcommon-devel", "ncurses"]
artifacts = [
  { box = "src/target/release/alacritty", host = "~/.local/bin/alacritty" },
  { box = "src/extra/linux/Alacritty.desktop", host = "~/.local/share/applications/Alacritty.desktop" },
  { box = "src/extra/logo/alacritty-term.svg", host = "~/.local/share/icons/hicolor/scalable/apps/Alacritty.svg" },
  { box = "terminfo/a/alacritty", host = "~/.terminfo/a/alacritty" },          # location pending Open Question 1
  { box = "terminfo/a/alacritty-direct", host = "~/.terminfo/a/alacritty-direct" },
]
```
`packages` are Fedora names (Alacritty INSTALL.md Fedora line verified); the box image is Fedora-family on **every** host OS, so one list serves Debian/Arch hosts too. The desktop entry is rendered (Exec/TryExec/Icon rewritten) rather than copied verbatim; the `host` column then names the final path while `desktop_entry.py` produces the bytes.

### Fake-runner acceptance (shape for `tests/test_cargo_distrobox.py`)
```python
def test_failure_still_removes_box_and_image(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    def runner(argv: list[str]) -> None:
        calls.append(argv)
        if argv[:2] == ["distrobox", "enter"] and "cargo" in argv:
            raise CommandError(argv, 101, detail="build failed")
    monkeypatch.setattr(cargo_distrobox, "image_exists", lambda ref: False)
    with pytest.raises(...):
        cargo_distrobox.install(method, ctx_with(runner))
    assert [c[:2] for c in calls][-2:] == [["distrobox", "rm"], ["podman", "rmi"]]
    assert "--force" in calls[-2] and "--rm-home" in calls[-2] and "--force" not in calls[-1]
```
Assertions to cover: the three create flags (`--home`, `--no-entry`, `--yes`) on `create`; the order create, enter(clone), enter(build), enter(tic), rm, rmi; image present before create gives no `rmi` and a "kept the existing image" detail; the exception re-raised after both cleanups; `BaseException` (KeyboardInterrupt) path runs `finally`; name matches `ti-cargo-alacritty-\d+-[0-9a-f]+`; no argv starts with `sudo`/`pkexec`/`doas`; tag validation rejects `-x` and `a b`.

### Integration status parse (D-27)
```python
_STATUS_LINE = re.compile(r"^(?P<target>\S+?)(?: \(experimental\))?: (?P<state>not installed|current|needs repair)\b")
```
Source: live `herdr integration status` output pasted in Pattern 5. The `register` seam needs a query function (the `Runner` returns `None`), injected like the other seams; unit tests plant a fake `herdr` under `tmp_path` (the sandbox forbids the real one).

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| Alacritty: native packages only, "Distrobox is not a method kind" (registry comment `:2925-2934`) | `cargo_distrobox` kind, user override of TA O5 on 2026-10-13 | this phase | grey row becomes installable on immutable hosts |
| Keybindings "ask the user, then Policies row" | install tuning, no question, reverted with the tool (TUNE-04) | 23.2 | no Policies row, no `default_enabled_sensitive_actions` |
| copilot via `node` | standalone binary (`cask`/`github_release`) | 23.2 | D-26's copilot Node case no longer exists |
| herdr 0.9.3 (host) | upstream v0.9.5 | 2026-10-14 | host differs from docs; integration versions in docs are 0.9.5's |

**Deprecated/outdated in the CONTEXT text:** D-16 (host podman), D-11 (herdr skill pack), the SPEC's `~/.local/share/terminfo` acceptance (Pitfall 1), the `catalog-unsupported-tools.md` Alacritty section.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Fedora package names `cargo git ncurses` are installable via `--additional-packages` in `fedora-toolbox:44` | Registry entry, Package Audit | Build fails at box init; fix is a data edit |
| A2 | Alacritty v0.17.0 ships `Cargo.lock` (so `--locked` works) | Pattern 1 | `cargo build` fails; drop `--locked` and note it |
| A3 | `alt+left/right` as `\u001bb`/`\u001bf` and `Control+Shift+K` give the intended behaviour in a real terminal | Pattern 4 | Wrong bindings; caught only in UAT |
| A4 | Desktop Entry `Exec` quoting rule (double quotes, backslash escapes) | Pitfall 12 | Entry fails for paths with spaces |
| A5 | Timeout values (900/900/180/1800/60/120 s) | Pitfall 7 | Spurious failures or hangs; tune after the first real build |
| A6 | `herdr plugin install --ref` accepts a full commit SHA and writes only herdr-managed files | Pattern 5, Open Q4 | The plugin hook needs the `link` + vendored-copy design instead |
| A7 | `herdr integration install` needs no TTY and no running server | Pattern 5 | The container hook fails; add a server start |
| A8 | Container images `docker.io/library/debian:trixie` and `docker.io/library/archlinux:latest` exist and provide `su`, `useradd`, `pacman`/`apt-get` | e2e section | Table entries need other refs |
| A9 | Per-distro cost is about two to three times a Fedora pass, roughly an hour or more per distro on this network | e2e section | Schedule only; see cost note |
| A10 | `distrobox enter` exit code is the in-box command's exit code (read in source: ends with `exec "$@"`, `podman exec`) | Pattern 1 | Failure detection of the build step; also checked by the nested run |

## Open Questions

**RESOLVED by the orchestrator 2026-11-08 (plan time; best design over smallest diff; recorded as dated amendments in 24-CONTEXT.md):**
- Q1 → `~/.terminfo`. The host-root rule is widened to `~/.terminfo`, and SPEC R3 / ONB-06 are amended (D-07 amendment). No `TERMINFO_DIRS` export. The evidence is technical (ncurses and Alacritty search paths), not a user lock.
- Q2 → D-19 stays provisional ("needs confirmation" is kept). The plans implement it as written and the end report shows it to the user again.
- Q3 → `repo` is a GitHub `owner/name` slug (clone URL derived as `https://github.com/<slug>.git`), and a required `image` param is added (D-01 amendment).
- Q4 → the planner tries `herdr plugin install --ref <full sha> --yes` first, with a verify-first task. The fallback, if `--ref` refuses a full SHA or leaves untracked files, is D-12's vendored copy plus `herdr plugin link` / `unlink`.
- Q5 → no new CLI flag (Phase 23 O1: no new CLI flags; the user's "no options nobody asked for"). A method whose `min_node` floor the system `node` does not meet is shown at plan time as a non-failure blocked/manual disposition with the reason (e.g. "needs Node >= 22.12; this system has 20.19.2"), the same way an unsupported OS is shown. A real Debian user then sees the truth instead of a failed row, and the Debian e2e passes with the exclusion listed by reason (D-26's intent: "listed with its reason"). Its dependents (mmdc needs puppeteer) follow through the existing dependency disposition (D-26 amendment).
- Q6 → a time-boxed nested-podman spike is the first execution task. If it fails, the real distrobox build becomes a human UAT item on the real host. That run is the user's to perform, never the agents': AGENTS.md says never mutate the host.
- Q7 → best-effort `rmdir` of empty ancestors below the declared root, inside the removal path.
- Q8 → accepted and documented in the herdr `# Verified` comment as fail-safe drift (the same class as 23.2's EX-02 copilot residual), and recorded as a follow-up.

1. **Terminfo location (blocks the artifact list and the acceptance command).**
   - Known: `~/.local/share/terminfo` is not searched by ncurses 6.6 or by Alacritty (Pitfall 1, evidence pasted).
   - Unclear: whether to move to `~/.terminfo` (amend SPEC R3/ONB-06 and the "host writes only under `~/.local` and `~/.config`" constraint) or keep the path and add a `TERMINFO_DIRS` export (extra owned state: an environment.d file or rc line).
   - Recommendation: `~/.terminfo` (the standard user location both programs read, `tic`'s own non-root default), host-root rule widened to `~/.terminfo`. Needs the user's yes before plan 2 is written.
2. **D-19 image ownership** (already flagged "needs confirmation" in CONTEXT and REQUIREMENTS ONB-02). Research supports it: `podman image exists` is a documented query (`podman image exists --help`: "exits with 0 ... otherwise the exit code will be 1"); plain `podman rmi` without `--force` is safe once the box is removed.
3. **D-01 `repo` as a git URL, and a missing `image` param.** The version source is a GitHub release tag, so the repo must be a GitHub `owner/name` slug anyway (what `github_repo` and `github_release` use); a free git URL widens clone-injection surface. Recommendation: `repo = "alacritty/alacritty"` and the clone URL derived as `https://github.com/<slug>.git`; add a required `image` string (a fully qualified OCI ref) since the image is part of what is deleted and pulled. Both are small deviations from D-01's list; confirm.
4. **herdr plugin via `herdr plugin install --ref` instead of a vendored copy plus `link` (D-12).** Simpler (herdr owns fetch, update and uninstall, no extra receipt path). Unverified: SHA acceptance and file effects (A6). Alternative if it fails: vendored copy placed by the installer plus `herdr plugin link`, `unlink` on removal.
5. **How to exclude a tool per distro (D-26).** Debian's Node 20.19.2 breaks mmdc and puppeteer; `setup.py` has only `--all` and `--categories`. Options: add `--exclude ID[,ID]` to `installer/cli.py`/`app._choose_tools` (a few lines; dependents must be excluded together, mmdc requires puppeteer) or accept category-level exclusion. Recommendation: the narrow `--exclude` flag, justified because D-26 asks for per-tool exclusion with a listed reason.
6. **Nested rootless podman + distrobox feasibility (D-18).** Cannot be probed here. Known design inputs: the outer container needs `--device /dev/fuse`, `--security-opt label=disable` (SELinux), subuid/subgid ranges inside the outer user namespace [CITED via WebSearch of Red Hat bug RHEL-3081 and a Zenn guide, tutorials not official docs, so LOW]; distrobox's keep-id probe `podman run --rm --userns=keep-id:size=65536` needs 65536 ids inside the outer namespace and falls back to plain `keep-id` when that fails. Plan a time-boxed spike as the first e2e task (image: Fedora + `dnf install podman distrobox desktop-file-utils`, outer `ct run` flags above); if it fails, record the failure output and move the real build to `24-UAT.md` run by the user, with the same assertions written as UAT commands.
7. **Empty parent directories after removal** (Pitfall 6): general prune step versus declaring roots. Recommendation: best-effort `rmdir` of empty ancestors below the declared root inside `remove_paths`.
8. **The herdr-on-this-host drift risk:** `herdr update` self-replaces `~/.local/bin/herdr`; the receipt `file` fingerprint then reads BROKEN until reinstall (the same issue 999.11 noted: "decide who owns updates"). Accept and document in the `# Verified` comment, or record it as a follow-up.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| distrobox | real build (nested target, UAT) | yes (`/usr/bin/distrobox`) | 1.8.2.5 | none; absence is the UNAVAILABLE path |
| podman | real build, container e2e | yes | 5.8.9 | docker not used by the harness |
| herdr | read-only facts | yes (`~/.local/bin/herdr`) | 0.9.3 | none needed |
| desktop-file-validate | container acceptance | yes on host | 0.28 | install `desktop-file-utils` in the nested container |
| tic, infocmp | container acceptance | yes on host | ncurses 6.6.20251230 | in-box `tic` for the build |
| gh | release facts | yes | not recorded | none |
| cargo, alacritty | build happens in the box | no on host | not needed | none |
| Running container e2e | harness | **a run is active** (`tools-installer-e2e`) | n/a | never touch it; per-distro container names and artifact dirs must not collide |
| Network | all builds and e2e | flaky (about 1 in 4 small HTTPS requests ends in a TLS EOF, 23.2-UAT) | n/a | retry; run distros sequentially |

**Missing with no fallback:** none for planning. **Execution-time unknown:** nested podman feasibility (Open Question 6).

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8 with pytest-cov, pytest-xdist (`pyproject.toml`), coverage floor `fail_under = 90` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`; sandbox in `tests/sandbox.py`, `tests/conftest.py`, `tests/child_guard/` |
| Quick run command | `uv run pytest -n 0 --no-cov -q tests/test_resolve.py tests/test_model.py tests/test_cargo_distrobox.py` (targeted files, as the 23.2 verification ran its named tests) |
| Full suite command | `make validate && make test` (`pytest -n auto`, capped near 40% of threads; never lower `-n`) |

Sandbox facts (read): `FORBIDDEN_PROGRAM_NAMES` includes `cargo`, `git`, `curl`, `podman`, `docker`, `systemctl`; `UTILITY_NAMES = ("stdbuf", "systemd-environment-d-generator")`; only checkout scripts in `CHECKOUT_SCRIPTS` may run. So **unit tests may not run `distrobox`, `podman`, `tic`, `infocmp`, `desktop-file-validate` or `herdr`**; use fake runners and fake executables under `tmp_path`. `scripts/container-e2e-verify.sh` is not in `CHECKOUT_SCRIPTS`: `tests/test_container_e2e_receipts.py` extracts function bodies with a regex (`^name\(\) \{...\n\}\n`) and runs them in bash with fixtures, so new harness logic must be top-level functions and constants shaped for that extraction, and no new executed script file is needed (the allowlist and fingerprint stay untouched).

### Phase Requirements to Test Map
| Req ID | Behavior | Test type | Automated command | File exists? |
|--------|----------|-----------|-------------------|--------------|
| ONB-02 | argv order create, enter x3, rm, rmi; flags `--home --no-entry --yes`, `--force --rm-home`, no `rmi --force` | unit (fake runner) | `uv run pytest -n 0 --no-cov -q tests/test_cargo_distrobox.py` | Wave 0 |
| ONB-02 | injected build failure still runs rm and rmi, re-raises; interrupt path; image-present case keeps image | unit | same file | Wave 0 |
| ONB-02 | precedence fixtures: immutable+tools build; immutable no tools unavailable "needs distrobox and podman"; mutable no tools dnf handoff; mutable+tools build; macOS unavailable; `_applies`/`_rejection` parity | unit | `uv run pytest -n 0 --no-cov -q tests/test_resolve.py` | exists, extend |
| ONB-02 | load validation: unknown key, empty `artifacts` rejected, empty `packages` ok, host root rule, `..` in `box`, bad tag chars | unit | `tests/test_model.py`, `tests/test_registry.py` | exists, extend |
| ONB-02 | `artifact_paths` for the kind; receipt records file+leaf; `removal_plan` level `artifacts`; uninstall unlinks all, parents handled | unit | `tests/test_download.py`, `tests/test_receipts.py`, `tests/test_uninstall.py` | exist, extend |
| ONB-02 | newer tag shows OUTDATED; `u` rebuilds and re-records; `~/.config/alacritty` checksum unchanged; no newer tag skips | unit | `tests/test_update.py`, `tests/test_version_status.py` | exist, extend |
| ONB-06 | `desktop_entry.render` golden text, quoting of a spaced path, control-char rejection | unit | `tests/test_desktop_entry.py` | Wave 0 |
| ONB-06 | `desktop-file-validate` passes; `infocmp alacritty` resolves (with `env -u TERMINFO -u TERMINFO_DIRS` and a fresh HOME); all paths removed after uninstall | container (nested target) or UAT | harness step | Wave 0 |
| ONB-07 | Alacritty regions: shell region, keybindings region, guard (`terminal.shell`, `[env]`, same-key binding, inline `keyboard.bindings`), rollback on failed re-parse, user keys survive, byte-stable second run | unit | `tests/test_terminal_shell.py` | exists, extend |
| ONB-07 | herdr `default_shell` absent-only, user value untouched with `≈` reason, no zsh no write, reload runner injected, ledger entry, revert only if value unchanged, nested-key writer | unit | `tests/test_terminal_shell.py`, `tests/test_agent_settings.py` | exist, extend |
| ONB-07 | new tuning action: install writes keybindings without zsh; present-but-untuned shows `≈ apply install tuning`; hand-deleted region raises nothing; `_after_removal` strips both regions and the state file | unit | `tests/test_post_install.py`, `tests/test_version_status.py`, `tests/test_app.py` | exist, extend |
| ONB-01 | herdr registry entry resolves for 4 OS/arch pairs (fake release feed with digests), raw link `herdr` | unit | `tests/test_registry.py`, `tests/test_download.py` | exist, extend |
| ONB-01 | `_HERDR_TARGETS` extension, `HOST_CATALOG_IDS`, D-27: "current" host not recorded, "needs repair" recorded, unregister only recorded hosts, order before ledger revert | unit (fake herdr under tmp_path) | `tests/test_postinstall.py`, `tests/test_session.py` | exist, extend |
| ONB-01 | sidebar plugin hook: python3 absent writes nothing with reason; rows written only when absent; revert only written keys | unit | `tests/test_postinstall.py` | extend |
| ONB-01 | in a container: integrations registered for present hosts, receipt records them, uninstall leaves status clean (copy-aside probe), no skill files | container | harness probes | Wave 0 |
| ONB-03 | skill contains every new param with an example, `rg -n "Policies"` finds the rule verbatim, `rg -n -i "skill.pack|skill_lifecycle"` finds nothing; judge report committed, total >= baseline | unit (text) + recorded run | `tests/test_docs.py` plus the recorded verdict JSON | exists, extend |
| ONB-04 | `--distro` table (image, prereqs, release record, exclusions), rerun accepts skipped/blocked/same-manual and rejects installed/updated/repaired/reconfigured/reinstalled, planted leftover fails, empty distro fails | unit (extracted bash functions, fixtures) | `uv run pytest -n 0 --no-cov -q tests/test_container_e2e_receipts.py` | exists, extend |
| ONB-04 | three full container runs | container | `scripts/container-e2e-verify.sh all --distro fedora|debian|arch` (never on the host) | orchestrator-run |
| ONB-05 | Owner on every tier after install; `○` after Uninstall; herdr line (D-29); real Alacritty build if nested infeasible; Alt+arrows and clear scrollback in a real terminal | manual | `24-UAT.md` run by the user | Wave 0 (file) |

### Sampling Rate
- **Per task commit:** the touched test files with `-n 0 --no-cov`.
- **Per wave merge:** `make validate && make test`.
- **Phase gate:** full suite green, then the orchestrator's three-distro container runs, then the UAT.

### Wave 0 Gaps
- [ ] `tests/test_cargo_distrobox.py` - ONB-02 argv, cleanup, failure injection, update
- [ ] `tests/test_desktop_entry.py` - ONB-06
- [ ] fixtures: fake release feed with a newer tag (existing `resolve_release` injection), fake `herdr` executable under `tmp_path`, scratch-HOME Alacritty/herdr config trees
- [ ] `tests/test_container_e2e_receipts.py` extensions for `--distro` and the rerun assertion (new top-level bash functions with extractable shape)
- [ ] `24-UAT.md` skeleton in the existing UAT format
- [ ] skill-judge report file under the phase directory (`24-SKILL-JUDGE.md`) with baseline and final verdict JSON lines (23.2 recorded the verdict JSON in its SUMMARY; D-13 asks for a committed report)

## Security Domain

`security_enforcement` is `true`.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2/V3 Authentication, Session | no | not applicable (local installer) |
| V4 Access Control | yes (filesystem) | host artifact roots restricted at load; removal only of receipt-proven `(path, kind)` pairs; `delete_config_path` containment rules |
| V5 Input Validation | yes | registry params validated at load (closed keys, `box` relative without `..`, `host` under allowed roots, `image`/`repo`/package-name regexes); GitHub `tag_name` validated before use as a git ref and passed after `--`; argv lists only, never `sh -c` with data; desktop-entry path quoting and control-char rejection |
| V6 Cryptography | partial | no hand-rolled crypto; raw herdr binary verified against the GitHub API sha256 digest (`resolve_target`); source builds verified only by tag name |
| V12 Files | yes | `mkdtemp` (0700) for the box home; atomic `.new`/`os.replace` placement; `tomllib` re-parse and rollback; compare-before-commit for config edits (existing `write_if_unchanged`) |
| V14 Config | yes | no sudo anywhere (AGENTS.md, AST test `tests/test_executors.py:148`); `distrobox`'s own in-box `sudo` during init is inside the container |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hostile or odd tag string becomes a git option (`--upload-pack=...`) | Tampering / EoP | regex-validate the tag, `--` before the URL, never shell-interpolate |
| Mutable git tag changes content between runs | Tampering | `--locked`, record the built commit in the row detail; accept as residual (no signed source digest exists) |
| Path traversal via artifact `box`/`host` entries or symlinked temp dir | Tampering | load-time validation; resolve under `<tmp>`; refuse symlinks in staged outputs |
| Box writes into the real HOME (it is mounted rw) | Tampering | commands use `<tmp>`-relative paths only; `HOME` and `XDG_CACHE_HOME` set; leftovers checked by the e2e |
| Orphaned container or image after crash | Denial of service / residue | `finally` plus name prefix `ti-cargo-` for a documented manual cleanup line in the failure row |
| Config corruption by region edits | Tampering | marker regions, guard scan, `tomllib` re-parse, atomic write, rollback |
| Overwriting a user-set `default_shell` or bindings | Tampering | absent-only writes, `≈` with reason, ledger-recorded revert only when the value is unchanged |
| Receipt forgery to delete foreign files | Tampering | existing proof rule: receipt AND registry formula must agree |

## Sources

### Primary (HIGH confidence)
- In-repo files read this session: `installer/{model,resolve,platform,executors,download,engine,update,uninstall,receipts,ownership,version_status,terminal_shell,post_install,postinstall,agent_settings,app,session,assets,run,cli,selection,enums}.py`, `installer/registry.toml`, `scripts/container-e2e-verify.sh`, `scripts/e2e-residue-allowlist.txt`, `tests/sandbox.py`, `tests/test_container_e2e_receipts.py` (head), `tests/test_docs.py`, `.claude/skills/tool-onboarding/SKILL.md`, 23.2 VERIFICATION and UAT, `.planning/RUN-LEDGER.md`, `docs/research/2026-10-09-alacritty.md`, `docs/catalog-unsupported-tools.md`
- Installed tools, read-only: `/usr/bin/distrobox-create`, `distrobox-enter`, `distrobox-rm` source and `--help` (1.8.2.5), `podman image exists --help`, `podman rmi --help`, `herdr --help`, `herdr integration --help|install --help|status`, `herdr plugin --help|install --help|link --help|list`, `herdr config --help`, `findmnt`, scratch-only runs of `tic`, `infocmp`, `desktop-file-validate`
- `gh api` for `herdrdev/herdr` and `alacritty/alacritty` latest releases, `castocolina/herdr-setup` tree, manifest and config at `2b5ca2a`
- Alacritty v0.17.0 raw files: `INSTALL.md`, `Alacritty.desktop`, `alacritty/Cargo.toml`, `Cargo.toml` (`rust-version`), `alacritty_terminal/src/tty/mod.rs`; release man pages `alacritty.5` and `alacritty-bindings.5` (downloaded as untrusted text)
- herdr docs at the v0.9.5 tag: `integrations.mdx`, `install.mdx`, `plugins.mdx`, `llms.txt`
- `registry.fedoraproject.org` registry API (`tags/list`, manifest HEAD for `fedora-toolbox:44`)

### Secondary (MEDIUM confidence)
- docs.brew.sh/Homebrew-on-Linux (prerequisite packages for Debian and Arch)
- packages.debian.org/trixie/nodejs, archlinux.org package search JSON, packages.fedoraproject.org cargo page

### Tertiary (LOW confidence)
- WebSearch results on nested rootless podman (a Red Hat bug report and community tutorials): design inputs only, not verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (versions and asset names read live)
- Architecture and wiring list: HIGH (code read), MEDIUM for completeness (a kind touches many files; tests will surface any missed switch)
- Pitfalls: HIGH for 1, 2, 3, 4, 11, 12 (reproduced or read); MEDIUM for 5, 9, 10; LOW for the nested-podman item
- e2e cost: LOW (no timing was measured; Phase 18 artifact mtimes suggest roughly 25 minutes for one full pass1 on Fedora, and pass 2 runs two more full installs)

**Research date:** 2026-11-08
**Valid until:** 2026-11-22 (herdr and Alacritty release often; re-check asset names and tags at plan time)

## Project Constraints (from CLAUDE.md / AGENTS.md)

- English only in every artifact, identifier, comment and commit message.
- uv owns the environment; never `pip`, `poetry`, `conda`.
- Never bypass a quality gate; no `# noqa`/`# type: ignore`/`# nosec`/vulture whitelist without the narrowest scope, a reason and user approval; pyright strict; ruff format only.
- `make validate && make test` must pass on the tree you commit; coverage floor 90, never lower; tests xdist-safe, no fixed shared paths, `monkeypatch` for HOME/env.
- Coherent commits (amend or squash, no "fix review comment" pile).
- **Never mutate the developer's host**: no `make setup/fix/uninstall/doctor/guard/unguard/e2e` by agents on the real machine, no real HOME or rc or agent-settings or `~/.config/alacritty` writes; tests use a scratch HOME; real installs only in disposable containers. (The orchestrator, not an agent on the host, runs the container e2e.)
- Zero sudo: no code path runs `sudo`, `pkexec` or `doas`; native installs are handed off as text.
- Plans must not widen the 23.1 test-launch allowlist or fingerprint.
- GSD is per-project only; never run a global GSD install or `gsd update`.
- `.claude/architecture.md` rules: one view registry, one nav path, one apply workflow, wiring-only `setup.py` (a composition root; put new logic in `installer/`).
