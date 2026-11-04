---
phase: 22-method-lifecycle-contract
plan: "08"
subsystem: registry
tags: [registry, script-lifecycle, vendor-verification, removal-proof, homebrew, config-paths]

# Dependency graph
requires:
  - phase: 22-01
    provides: load_tools validation of script paths, remove, update and config_paths
  - phase: 22-03
    provides: receipts.record with preexisting; script receipts prove declared leaves and trees
  - phase: 22-05
    provides: a declared script update argv runs directly
  - phase: 22-06
    provides: remove_tool and removal_plan, the removal path the R1-13 test drives
provides:
  - paths, remove and update data for all 18 script stanzas (14 tool ids), each edited tool dated 2026-11-04
  - config_paths for uv, gh, kitty and pnpm
  - SCRIPT_LIFECYCLE_DATA and nine new registry tests (31 new test cases in total)
affects: [22-09, 22-13]

# Actuals (#2632): chars/4 over the realized diff (29772 chars), not a harness token count
actuals:
  tokens: 7443
  tasks: 3
  commits: 3

# Measured commit ledger (#3968): base and head of this plan's task commits
commits: 3
plan_head_before: 705385ccd9bf60ec6acfc4bb6005b43ae5102b71
plan_head_after: 0ce97832b59546d67b3c7086e782aa6c00dc25a8
status: complete

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Every vendor fact cited in the row's # Verified comment with its source and line numbers"
    - "Manager roots (pnpm, bun, volta, fnm) declare only their executables as leaves"

key-files:
  created:
    - .planning/phases/22-method-lifecycle-contract/22-08-SUMMARY.md
  modified:
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "opencode declares paths (the ~/.opencode/bin/opencode leaf) and update (opencode upgrade) and no remove (R2-05): its uninstall rewrites the shell rc, deletes cache and state, and only hints at the binary"
  - "oh-my-zsh update runs tools/upgrade.sh directly: git mode 100755 with a zsh shebang, so no zsh -f wrapper is needed"
  - "claude paths: the ~/.local/bin/claude link and the ~/.local/share/claude tree, whole because the vendor's documented native uninstall deletes it whole; no remove, since its documented commands are rm, not a declared leaf (R2-03)"
  - "cursor-agent paths: the versions tree and the two links, never the harness marker dir ~/.local/share/cursor-agent (R3-03)"
  - "codex declares no update: the CLI docs name no codex update command (the CLI self-updates)"
  - "Homebrew: all three stanzas set HOMEBREW_NO_SUDO=1 because install.sh reads it (lines 282-321), which fits the zero-sudo rule"
  - "pnpm, bun, volta and fnm declare no store tree (R1-13); their stores are listed below as kept on purpose"

patterns-established:
  - "SCRIPT_LIFECYCLE_DATA keys every script stanza by (tool id, os, arch); test_every_script_stanza_has_lifecycle_data_or_a_reason pins the key set to the registry"
  - "A removal test plants the declared leaves and a store file, records a receipt, and checks that remove_tool leaves the store file's bytes intact"

requirements-completed: [LIFE-01, LIFE-06, LIFE-04]  # data halves only; REQUIREMENTS.md is left to the orchestrator

coverage:
  - id: D1
    description: "All 18 script stanzas carry verified paths/remove/update data or a documented absence, pinned by SCRIPT_LIFECYCLE_DATA"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_every_script_stanza_has_lifecycle_data_or_a_reason"
        status: pass
    human_judgment: false
  - id: D2
    description: "The three SPEC anchors: opencode removal by its binary alone, oh-my-zsh and sdkman update commands"
    requirement: "LIFE-06"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_script_lifecycle_data"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_anchor_artifacts_expand"
        status: pass
    human_judgment: false
  - id: D3
    description: "Manager removal keeps global packages and toolchains; no manager store is declared as a tree"
    requirement: "LIFE-04"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_a_manager_removal_keeps_its_global_packages"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_no_manager_stanza_declares_a_store_as_a_tree"
        status: pass
    human_judgment: false
---

# Phase 22 Plan 08: Script lifecycle data (vendor-verified) Summary

Vendor-verified `paths`, `remove` and `update` data for all 18 script stanzas, with `config_paths` for uv, gh, kitty and pnpm and a key-set test that keeps the table equal to the registry.

## Commits

| # | Hash | Subject |
|---|------|---------|
| 1 | 4c123a6 | feat(22-08): opencode, oh-my-zsh and sdkman lifecycle data |
| 2 | 6700f27 | feat(22-08): uv, claude, codex, cursor-agent and antigravity lifecycle data |
| 3 | 0ce9783 | feat(22-08): remaining script tools, pi and gh lifecycle data |
| 4 | (this commit) | docs(22-08): plan summary with RED and GREEN evidence |

Every task commit is one test-plus-data commit. `make validate` and `make test` exited 0 on the tree of each of the three task commits.

## Test counts

| Point | `make test` result | Exit |
|-------|--------------------|------|
| Baseline at 705385c (before edits) | 5401 passed, 4 skipped | 0 |
| After Task 1 (4c123a6) | 5405 passed, 4 skipped | 0 |
| After Task 2 (6700f27) | 5412 passed, 4 skipped | 0 |
| After Task 3 (0ce9783) | 5432 passed, 4 skipped | 0 |

Net new: 31 test cases (4 + 7 + 20).

## RED / GREEN evidence

Verify-first sources are listed in the next section. Failing output was produced before each registry edit and was never committed alone.

### Task 1 (opencode, oh-my-zsh, sdkman)

RED, `uv run pytest tests/test_registry.py -k "script_lifecycle_data or anchor_artifacts" -q --no-cov -n 0` (4 failed):

```
FAILED tests/test_registry.py::test_script_lifecycle_data[key0] - AssertionEr...   # oh-my-zsh: None == ['{omz_root}/tools/upgrade.sh']
FAILED tests/test_registry.py::test_script_lifecycle_data[key1] - AssertionEr...   # opencode: None == ['~/.opencode/bin/opencode']
FAILED tests/test_registry.py::test_script_lifecycle_data[key2] - AssertionEr...   # sdkman: None == ['sdk', 'selfupdate']
FAILED tests/test_registry.py::test_anchor_artifacts_expand - AssertionError: assert () == (Artifact(pat...kind='leaf'),)
```

GREEN after the three rows landed: 4 passed in the same command. The plan's one-liner also passed (`opencode` params hold `paths`, `update` and no `remove`).

Note: `make validate` failed once on E501 (a comment line over 100 characters). The comment was rewrapped and the rerun passed. No check was silenced.

### Task 2 (uv, claude, codex, cursor-agent, antigravity)

RED, `-k "script_lifecycle_data or harness_marker or uv_declares"` (6 failed):

```
FAILED tests/test_registry.py::test_script_lifecycle_data[key0] - AssertionEr...   # antigravity: paths missing
FAILED tests/test_registry.py::test_script_lifecycle_data[key1] - AssertionEr...   # claude: paths missing
FAILED tests/test_registry.py::test_script_lifecycle_data[key2] - AssertionEr...   # codex: paths missing
FAILED tests/test_registry.py::test_script_lifecycle_data[key3] - AssertionEr...   # cursor-agent: paths missing
FAILED tests/test_registry.py::test_script_lifecycle_data[key7] - AssertionEr...   # uv: paths missing
FAILED tests/test_registry.py::test_uv_declares_its_documented_config_dir - assert () == ('~/.config/uv',)
```

Regression guard, not RED: `test_no_declared_path_is_or_contains_a_harness_marker` already passed on the pre-state because no declared path yet sat at or above a marker dir. It is kept as the guard for the new rows.

GREEN: 11 passed on the focused run. The plan's whole-vendor-dir one-liner printed `no whole vendor dir declared`.

### Task 3 (bun, pnpm, volta, fnm, kitty, brew, pi, gh)

RED, `-k "script_lifecycle_data or every_script_stanza or store_as_a_tree or keeps_its_global_packages or homebrew_no_sudo or documented_config_dirs"` (17 failed):

```
FAILED ...test_script_lifecycle_data[key1..key4, key8, key9, key13, key14, key17]   # paths/update not yet declared (9 cases)
FAILED ...test_every_brew_stanza_sets_homebrew_no_sudo - KeyError: 'HOMEBREW_NO_SUDO'
FAILED ...test_a_manager_removal_keeps_its_global_packages[key0..key3] - KeyError: 'paths'   # bun, fnm, pnpm, volta
FAILED ...test_script_tools_declare_their_documented_config_dirs[gh, kitty, pnpm] - assert () == ('~/.config/gh',)
```

Regression guards, not RED: `test_every_script_stanza_has_lifecycle_data_or_a_reason` passed because the table already held all 18 keys, and `test_no_manager_stanza_declares_a_store_as_a_tree` passed because no manager row declared a tree yet.

GREEN: 31 passed on the focused run. The plan's stanza one-liner printed `script stanzas covered 18`.

## Verify-first evidence (sources read this run)

- **OpenCode** install (`https://opencode.ai/install`): `INSTALL_DIR=$HOME/.opencode/bin` (lines 80-81), binary moved there (lines 367-375), `--no-modify-path` honored (lines 427-459).
- **OpenCode uninstall** (anomalyco/opencode v1.19.5, `packages/opencode/src/cli/cmd/uninstall.ts`): on a curl install, `cleanShellConfig` rewrites the rc file (`getShellConfigFile`, `cleanShellConfig`) whatever `--keep-config` says; `Global.Path.cache` and `Global.Path.state` are removed with `keep: false`; the binary gets only a `rm "…"` hint; `--dry-run` is the only flag that skips the edit. Decision: no `remove`.
- **OpenCode update** (`cli/cmd/upgrade.ts`, v1.19.5): `opencode upgrade [target]`; `--major` moves to OpenCode 2, so the default stays on OpenCode 1.
- **Oh-My-Zsh** (`api.github.com/repos/ohmyzsh/ohmyzsh/git/trees/master?recursive=1`): `tools/upgrade.sh` is mode `100755`; its first line is `#!/usr/bin/env zsh`. `tools/uninstall.sh` renames `~/.zshrc` (`mv ~/.zshrc …`), so no `remove` and no `paths`.
- **SDKMAN**: `sdk selfupdate` is documented on sdkman.io/usage (Self-Update); sdkman.io/install "Uninstallation" removes `~/.sdkman` by hand and the user's rc snippet.
- **uv** (`astral.sh/uv/install.sh`): bins `uv` and `uvx` in `$HOME/.local/bin` (case table, lines 232-471). The env file is written only when rc edits are on (`add_install_dir_to_path`, line 1536), and the stanza sets `UV_NO_MODIFY_PATH=1`, so no env file is declared. Receipt in `~/.config/uv` (RECEIPT_HOME). `uv self update` documented (docs.astral.sh installation page). User config `~/.config/uv/uv.toml` (docs.astral.sh/concepts/configuration-files). Uninstall docs clear data and remove the binaries by hand: no `remove`.
- **Claude** (`claude.ai/install.sh`): downloads into `~/.claude/downloads` and runs `claude install`; the layout is the vendor's. Docs (code.claude.com/docs/en/setup, "Uninstall a native installation"): "Remove the Claude Code binary and version files: `rm -f ~/.local/bin/claude`, `rm -rf ~/.local/share/claude`". Launcher section: "run `claude update`". No `remove` (the documented commands are `rm`, not a declared leaf, R2-03).
- **Codex** (`chatgpt.com/codex/install.sh`, lines 16-35 and 1228-1241): `RELEASES_DIR`, `CURRENT_LINK`, `LOCK_FILE` (`install.lock`), `AUTO_UPDATE_VERSION` (`auto-update-version`); `~/.local/bin/codex` links into `CURRENT_LINK`; `~/.local/bin/codex-code-mode-host` only on darwin. Docs (developers.openai.com/codex/cli) name no `codex update`; the script's uninstall commands only remove a conflicting brew/bun/npm copy.
- **Cursor** (`cursor.com/install`, versions dir written at lines 77-111, links at lines 128-131): `~/.local/share/cursor-agent/versions/2026.10.22-27dcf5f`, links `~/.local/bin/agent` and `~/.local/bin/cursor-agent`. The registry comment on the cursor-agent method cites lines 124-126 for the links; the correct lines are 128-131 (a comment-only inaccuracy, recorded in deviation 11 rather than amended, because the commit is not rewritten). Docs (cursor.com/docs/cli/installation, "Updates"): `agent update`. No uninstall in the script or the docs.
- **Antigravity** (`antigravity.google/cli/install.sh`, lines 12, 54, 203-239): one binary `agy` in `$HOME/.local/bin`; the native handoff `agy install` writes harness state (not declared). Self-updates in the background (line 59); no manual update documented.
- **bun** (`bun.sh/install`, lines 137-161): `exe=$bin_dir/bun`, `bin_dir=$install_dir/bin`. `bun upgrade` in the bun README (github.com/oven-sh/bun, lines 76-82). The bun docs page itself was not reachable this run.
- **pnpm** (`get.pnpm.io/install.sh`): the downloaded binary runs `pnpm setup --force` (`run_setup`); `$PNPM_HOME/bin` is the bin_dir; the script's own uninstall note says to delete PNPM_HOME. `pnpm self-update` documented (pnpm.io/cli/self-update). Config dirs `~/.config/pnpm/` (Linux) and `~/Library/Preferences/pnpm/` (macOS) from pnpm.io/npmrc.
- **Volta** (`get.volta.sh`, lines 230, 345, 357-358): `install_dir=${VOLTA_HOME:-$HOME/.volta}`; the release tarball is extracted into `bin`. `tar -tzf` of `volta-2.0.2-linux.tar.gz` lists exactly `volta`, `volta-shim`, `volta-migrate`. The default shims are created by `volta --version` at run time.
- **fnm** (`fnm.vercel.app/install`, lines 12-19, 102-117): `INSTALL_DIR` defaults to `~/.local/share/fnm`; the binary is moved to `$INSTALL_DIR/fnm`. Store: `installations_dir` joins `node-versions` under the base dir (Schniz/fnm `src/config.rs`, line 153).
- **kitty** (`sw.kovidgoyal.net/kitty/installer.sh`, lines 66-82, 187-204): writes only `kitty.app` under `--dest` (default `~/.local`); no `ln`, symlink or desktop-entry lines. Config `~/.config/kitty/kitty.conf` (sw.kovidgoyal.net/kitty/conf).
- **Homebrew** (`raw.githubusercontent.com/Homebrew/install/HEAD/install.sh`, lines 282-321): reads `HOMEBREW_NO_SUDO`. Hence the env addition on all three stanzas.
- **gh**: `GH_CONFIG_DIR` defaults to `$HOME/.config/gh` (cli.github.com/manual/gh_help_environment).
- **pi**: `installer/host_setup.py` installs `@earendil-works/pi-coding-agent` through pnpm; the npm registry lists that package, latest 1.5.0.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking] Lint and typing fixes in the new tests**
- **Found during:** Tasks 1 and 3 (`make validate`)
- **Issue:** one comment line over 100 characters (ruff E501, Task 1); a dict key type and an untyped `params` value (pyright, Task 3)
- **Fix:** rewrapped the comment; annotated `_STORE_FILES`; cast `method.params["paths"]`
- **Files modified:** tests/test_registry.py
- **Commit:** folded into 4c123a6 and 0ce9783

**2. [Rule 1 - Bug in an existing test] Brew env assertions needed the plan's HOMEBREW_NO_SUDO**
- **Found during:** Task 3 `make test` (`test_registry_includes_homebrew_with_os_targeted_install`, exact env dict assertions)
- **Issue:** the test pinned `env == {"NONINTERACTIVE": "1"}`; the plan's truth requires `HOMEBREW_NO_SUDO = "1"` there
- **Fix:** both assertions (macOS and Linux) now expect the two-key env. No test was deleted.
- **Commit:** 0ce9783

### Plan-level deviations (recorded as decisions)

**3. codex has no `update`** (plan expected `codex update`). Developers.openai.com/codex/cli names no such command, and the script's auto-update logic self-updates the CLI. Declaring an undocumented command would be invention.

**4. cursor-agent `update` is `["cursor-agent", "update"]`, not the docs' `agent update`.** Both names link the same binary, and the registry keeps `cursor-agent` as the cmd because `agent` collides on PATH (`test_cursor_agent_uses_the_legacy_collision_safe_cmd_name`).

**5. pnpm declares no `dist/` tree.** The pnpm executable expects a `dist/` tree beside it (the script's own comment), but the R1-13 rule forbids a tree under a manager root. The `dist/` tree is left for 22-13's must-clear check.

**6. volta's default shims are not declared.** `volta --version` creates them at run time, and their exact set was not verified. They are left for 22-13's must-clear check.

**7. codex-code-mode-host is declared** although the script creates it only on darwin. It is one stanza across OSes, and on Linux the leaf is absent, which is a no-op.

**8. The orchestrator's conditional for OMZ.** Verified (mode 100755, zsh shebang), so `update` is the direct argv. Residual: the direct run loads the user's `~/.zshenv`, which `zsh -f` would skip. Accepted, since the plan's direct form is the verified one.

**9. Unverified store roots.** The bun, pnpm-global and Volta-tools store paths below come from 22-RESEARCH. The pages that would have confirmed them (bun docs, pnpm global-install docs, the Volta layout source) were unreachable this run. The fnm `node-versions` store was verified from source. The leaf-only rule protects these stores whatever their exact subdirectory is.

**10. Unverified shell-rc behavior of `claude install`.** The docs name no rc path, and none is declared. If the native installer edits a shell rc, that edit is the user's and not removed here.

**11. A comment line-number inaccuracy in the cursor-agent row.** Its `# Verified 2026-11-04` comment cites lines 124-126 for the agent and cursor-agent links; the script's symlink lines are 130-131 (the `rm -f` is 128). The data is correct and the test does not read the comment. Fixing it needs a new commit or an amended history, and the project rules forbid both for this plan, so the correction lives here. A follow-up comment-only edit is for the orchestrator to schedule.

### Not done (by design)

- No `remove` on any of the 18 stanzas. Every candidate failed the R2-05 / R2-03 / R1-13 tests or has no documented uninstall (see the verify-first list).
- No manual-removal hint for oh-my-zsh, sdkman or Homebrew (the recorded R1-14 decision).
- `pi` kept no script keys; only its `verified` date changed.
- REQUIREMENTS.md, STATE.md and ROADMAP.md are not touched (orchestrator).

## Stores kept on purpose (for 22-13's allowlist)

- pnpm: `~/.local/share/pnpm/` on Linux and `~/Library/pnpm/` on macOS (global packages in `global/`, and `dist/` beside the executable, which is left for the must-clear check)
- bun: `~/.bun/` (`install/global`, cache)
- volta: `~/.volta/tools/` (plus any other `~/.volta/` content beyond the three leaves)
- fnm: `~/.local/share/fnm/node-versions/`
- Homebrew: the whole prefix (no `paths`, no `remove`)
- uv: its tool and Python data (the `uv tool dir` and `uv python dir` stores, not declared)
- Harness marker dirs left by the vendors (`~/.local/share/cursor-agent/` with its `logs/` and `worker.lock`; `~/.codex/packages/standalone/` with `install.lock` and `auto-update-version`; `~/.gemini/antigravity`; `~/.claude`)

## Changed or deleted existing tests

| Test | Change | Reason |
|------|--------|--------|
| `test_registry_includes_homebrew_with_os_targeted_install` | the exact `env` expectation gained `HOMEBREW_NO_SUDO = "1"` (macOS and Linux) | the plan's truth requires `HOMEBREW_NO_SUDO` in each brew stanza env |

No test was deleted.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path or file-access pattern beyond the plan's threat register (T-22-19, T-22-20, T-22-39, T-22-48, T-22-50).

## Self-Check

- The registry changes and the test file are the only modified files, and they are committed in 4c123a6, 6700f27 and 0ce9783.
- `git merge-base --is-ancestor` confirmed that 4c123a6, 6700f27 and 0ce9783 are all ancestors of HEAD (FOUND for each).
- The focused GREEN run for Task 3 reported 31 passing tests and no failures.
- Host mutation: none. Downloads went to fresh `mktemp -d` directories and were read with grep, sed and tar listing only. No vendor installer or uninstaller was run. `make install` created `.venv` inside the worktree only.
- Worktree guards: branch `worktree-agent-a158b580274a2e556`, cwd equal to the spawn sentinel, HEAD not on a protected branch, every commit on the agent branch.
- The three task commits passed `make validate` and `make test` (exit 0, see the counts table).

## Ledger

- `plan_head_before`: 705385ccd9bf60ec6acfc4bb6005b43ae5102b71
- `commits`: 3 (measured by `git rev-list --count 705385c..HEAD` before this summary commit)
