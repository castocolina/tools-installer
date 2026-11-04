---
phase: 22
lane: ponytail
base: 6fcaa7f
head: e8c1590
scope: "git diff 6fcaa7f..e8c1590 -- installer setup.py scripts tests"
severity_counts:
  high: 1
  medium: 2
  low: 4
---

# Phase 22 — ponytail review

Scope: `git diff 6fcaa7f..e8c1590 -- installer setup.py scripts tests` (52 files, +7692 / -489;
source part: 25 files, +1984 / -343). I read the connected code too, not only the diff:
`removal_plan`/`plan_removal`, `remove_tool`/`run_uninstall`/`perform_uninstall`, `receipts`
(record, matches, tree/leaf), `engine.install_tool`, `session.build_plan`, `update._perform`,
`manager_versions.read_outdated`, `ownership.read_inventory`, `omz.omz_root`, `deps.resolve_dependencies`
and the e2e harness.

Load assumed: one person on their own machine, running the TUI or one headless `--all` or
`--uninstall --yes` run. The catalog has 89 tools. There is one refresh service per process.

## What this change does

Phase 22 gives each method kind one removal rule. `removal_plan` decides the level: L1 manager
(`brew`/`cask`/`uv`/`pnpm` uninstall, only when this installer's receipt names the package), L3
recipe (receipt-proven script `paths`, plus an optional vendor `remove`), L2 artifacts, or none
(hint only). The CLI and the TUI now both remove through `app.remove_tool`. Native dnf, apt and
pacman installs, and a brew bootstrap whose prefix you cannot write, become a MANUAL handoff. No
code path runs sudo. A tool can declare `config_paths`, and only the Uninstall view's per-row `c`
flag deletes them. `u` refuses a pinned app or tarball, runs a script's declared `update` argv,
and upgrades auto-updating casks with `--greedy-auto-updates`. The container e2e now compares a
HOME listing taken before install with one taken after uninstall.

I checked these and found them sound: the zero-sudo removal, the tree/leaf receipts (only paths
this install created are recorded), the leaf retarget rule, quarantine before `rmtree` for trees,
the `delete_config_path` parent and harness-marker checks (`/home` -> `/var/home` symlinked HOME
included), the dependents-first `removal_order`, and the plan-time MANUAL rows. The native-first
ladder that never falls through to brew is a recorded ledger decision (RESEARCH Pitfall 4, Q2), so
it is not reported.

## Must fix

### PT-01 — HIGH — A manager package the user already removed can never be uninstalled; `--uninstall` fails every time

- **File:line:** `installer/uninstall.py:228-238` (`_manager_argv`), `installer/app.py:577-592`
  (`remove_tool`, the pnpm-only `gone` check), `installer/app.py:739-755` (`run_uninstall` loop),
  `installer/version_status.py:1979` (`uninstall_group`).
- **Problem:** The L1 argv is built from the receipt alone. Nothing checks that the manager still
  lists the package. When `brew uninstall <pkg>` or `uv tool uninstall <pkg>` then fails because
  the package is already gone, `remove_tool` reports the row failed and keeps the receipt. So the
  next run builds the same argv, and it fails again. Commit 4190481 fixed this for pnpm only
  (`ERR_PNPM_GLOBAL_PKG_NOT_FOUND` counts as removed). brew and uv still have the bug. This is a fix
  applied in one place while the shared rule stays broken.
- **Failure scenario:** You install `jq` through the installer's brew method, so a receipt is
  written. Later you run `brew uninstall jq` yourself. Then:
  - `setup.py --uninstall --yes` still prints `jq: runs brew uninstall jq`. brew answers
    `Error: No such keg`, the CLI prints `jq: remove failed`, and it exits 1. It does this on every
    run, forever. `run_uninstall` never reads health, only `plan.level`.
  - In the TUI, if another copy of `jq` stays on PATH (for example `/usr/bin/jq` from dnf), the row
    is REMOVABLE and says "installed by this installer through Homebrew: receipt matches — runs
    `brew uninstall jq`". Enter fails the same way, and "Fix the cause and press enter to try again"
    has no cause you can fix.
  - I reproduced this with a scratch HOME: a brew receipt for `jq`, then `remove_tool` with a runner
    that raises `No such keg`. Both calls returned `removed=False`, and the receipt stayed.
- **Fix:** Turn the pnpm special case into one table next to `MANAGER_UNINSTALL_ARGV`. It maps
  each kind to the manager's own "not installed" marker: brew/cask `No such keg`, uv
  `is not installed`, pnpm `ERR_PNPM_GLOBAL_PKG_NOT_FOUND`. In `remove_tool`, set
  `gone = marker in exc.detail` for the receipt's kind. Delete `PNPM_GLOBAL_PKG_NOT_FOUND` and the
  `argv[:-1] == MANAGER_UNINSTALL_ARGV["node"]` branch. Add one fake-runner test per kind,
  mirroring `test_a_group_member_pnpm_already_removed_is_removed`. Check the marker strings once
  against live brew and uv in a container before you pin them.

## Should fix

### PT-02 — MEDIUM — The "package was already there" guard fails open for the tap formula `anomalyco/tap/opencode`

- **File:line:** `installer/engine.py:348-371` (`_package_already_there`, `_listing`),
  `installer/registry.toml:1576` (`formula = "anomalyco/tap/opencode"`).
- **Problem:** The R3-02 guard asks whether `package in inventory.brew_formulae`. But
  `brew list --versions --formula` prints the short name (`opencode 1.19.5`). It never prints the
  tap path. So a pre-existing `anomalyco/tap/opencode` always reads as "not there before". The
  install then claims it with a receipt, and `_manager_argv` turns that receipt into
  `brew uninstall anomalyco/tap/opencode`. I confirmed the first half directly:
  `_package_already_there(brew_method, "anomalyco/tap/opencode", inventory={"opencode": ...})`
  returns `False`. No test covers a tap formula.
- **Failure scenario:** You already have opencode from the brew tap, but the installer does not see
  it as present (for example the formula is unlinked, or brew's bin dir is missing from this
  process's PATH). The installer's script method fails, and the ladder reaches brew.
  `brew install` answers "already installed" with exit 0, and a receipt is written. A later
  Uninstall then removes the package you installed yourself. SPEC R4 forbids exactly this.
- **Fix:** In `_listing`'s caller, compare the last path segment for brew/cask:
  `package.rsplit("/", 1)[-1] in listed`. That is one line. Add one engine test with the tap
  formula and an inventory that lists `opencode`. The older ownership code
  (`ownership.py:1096-1098`) makes the same short-name comparison and so never attributes brew
  for opencode either. That bug predates this phase, but the same one-line rule fixes both.

### PT-03 — MEDIUM — Two copies of a "shared config path" rule, for a case the registry never has

- **File:line:** `installer/model.py:545-558` (`_refuse_config_overlap` allows equal entries:
  `a_parts != b_parts`), `installer/wizard_app.py:1050-1078` (`config_split` and its `kept` map),
  `installer/app.py:817-847` (`_config_step` and its `owners` loop), plus the review's "kept,
  also used by" lines in `UninstallScreen._review`.
- **Problem:** The loader refuses one tool's config path that is a parent of another tool's path,
  but it allows two tools to declare the same path. To handle that one case, the TUI review
  (`config_split`) and the remover (`_config_step`) each implement the same "delete only when
  every catalog owner is flagged and removed" rule. The two copies must stay in step, or the review
  will show something the remover does not do. No two tools in today's registry share a
  `config_paths` entry (I checked by loading the registry).
- **Cost:** About 45 lines of production code, plus their tests, for a state that does not exist.
  Every later change to the config step must also be made in a second module.
- **Fix:** Refuse equal entries at load as well: drop `a_parts != b_parts` and name both tools in
  the error. Then `config_split` shrinks to "the flagged tool's existing paths". `_config_step`
  keeps only its "not declared by any tool" guard and the delete. The "kept, also used by" review
  block goes away. The SPEC R6 shared-path edge ("deleted once, only if both toggle") then holds
  because the loader makes that state impossible, which is simpler than handling it in two places.

## Nice to have

### PT-04 — LOW — The vendor `remove` mechanism has no registry user

- **File:line:** `installer/uninstall.py:241-272` (`_recipe_argv`), the recipe branch of
  `remove_tool` (`installer/app.py:574-602`), and the recipe sentence in
  `version_status.uninstall_detail`.
- **Problem:** No `[[tool.method]]` in `registry.toml` declares `remove`. The opencode amendment
  (R2-05) removed the only one. So this binding of argv to a proven leaf (about 35 lines) runs only
  in tests that use a test-local recipe. The orchestrator signed off on keeping it, so this is a
  recorded decision. It is still code that ships, gets reviewed and must be maintained for zero
  tools.
- **Cost:** It is the most security-sensitive path in the phase (it executes a command taken from
  a data file), and it has no production caller to show whether it is right.
- **Fix:** Either delete `_recipe_argv`, the `remove` key in `METHOD_PARAMS["script"]` and its
  tests until a vendor ships a safe uninstall, or keep it with a `shortcut:` comment that names the
  decision (CONTEXT amendment 2026-11-04), so later reviews stop flagging it.

### PT-05 — LOW — A second OMZ root resolver with the opposite order

- **File:line:** `installer/download.py:250-259` (`_zsh_first_omz_root`), next to
  `installer/omz.py:530-543` (`omz_root`).
- **Problem:** `omz_root` checks `~/.oh-my-zsh` first. Its own docstring (CR-01) calls it "the one
  place that decides where oh-my-zsh is". The new wrapper checks `$ZSH` first and then calls
  `omz_root`, which looks at `$ZSH` again. So presence, the terminal sync and `ensure_zshrc_template`
  follow one rule, and `u` follows the other.
- **Failure scenario:** `$ZSH=/srv/omz` is your real install, and a stale `~/.oh-my-zsh` also
  exists. Presence and version come from `~/.oh-my-zsh`, while `u` upgrades `/srv/omz`. The row
  never reflects the update.
- **Fix:** Pick one order (SPEC R8 says `$ZSH` first) and change it inside `omz_root`. Delete
  `_zsh_first_omz_root`, and point `SCRIPT_ROOT_RESOLVERS` at
  `lambda: omz_root(Path.home(), os.environ)`. Re-run `tests/test_omz.py` to confirm the other
  callers still agree.

### PT-06 — LOW — Every manager-method install reads the whole manager inventory

- **File:line:** `installer/engine.py:217-227` (`manager_inventory`), `setup.py:777-785`
  (`read_inventory_fn=read_inventory`), `installer/ownership.py:380-403`.
- **Problem:** `install_tool` calls `read_inventory` once per call, the first time a brew, cask,
  uv-tool or node method reaches the ladder. `read_inventory` runs `brew --prefix`, two
  `brew list` calls, `pnpm list -g --json` and `uv tool list`. It does this even though
  `_listing` reads only one field.
- **Cost:** On this registry, 11 (Fedora) to 16 (macOS) tools have a manager method first, and
  more reach one as a fallback. Each costs about 4-5 extra subprocesses, roughly 1-3 s, so a fresh
  `--all` run gets about 30-45 s slower.
- **Fix:** Ask only the manager the method needs. For example, pass a reader keyed by kind, or
  call `_query_brew_list`, `_query_uv_tools` or `pnpm_global_packages` directly for
  `method.kind`. The fail-closed rule stays the same.

### PT-07 — LOW — `new_leftovers` expands empty arrays under `set -u`, which bash 3.2 rejects

- **File:line:** `scripts/container-e2e-verify.sh:13` (`set -euo pipefail`), `:613-656`
  (`new_leftovers`: `"${recorded_list[@]}"`, `"${roots[@]}"`, `"${leftovers[@]}"`).
- **Problem:** The harness runs on the host, and `detect-container-runtime.sh` supports macOS
  hosts (colima+docker). There `#!/usr/bin/env bash` can resolve to `/bin/bash` 3.2. In bash older
  than 4.4, `"${arr[@]}"` on an empty array with `set -u` aborts with "unbound variable".
  `roots` is always empty at the first loop, so this fails on every run. Before this change, the
  script used no bash 4 features.
- **Failure scenario:** A macOS host without Homebrew bash first on PATH runs pass2. The leftover
  check dies inside `new_leftovers` and reports a leftover failure, not a result.
- **Fix:** Guard each expansion with `${arr[@]+"${arr[@]}"}`, or check `BASH_VERSINFO` once at
  the top and refuse with a clear message.

## Verdict

Verdict: fix PT-01 and PT-02 first.
Lean: about -90 lines possible (PT-03 about -45, PT-04 about -40, PT-05 about -8; the PT-01 fix
nets about zero).
Not checked: I could not check the live vendor facts offline. That includes whether Homebrew's
`install.sh` honors `HOMEBREW_NO_SUDO`, and the exact brew/uv "not installed" strings PT-01 relies
on. I also could not check which bash the macOS CI runner uses (PT-07). I did not run
`make validate` or `make test`.
