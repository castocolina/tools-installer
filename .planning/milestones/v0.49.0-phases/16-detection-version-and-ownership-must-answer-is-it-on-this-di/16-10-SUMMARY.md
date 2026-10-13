---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 10
subsystem: catalog
tags: [kitty, script, args, bin_dir, sdkman, version_file]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: bin_dir location proof and own-installer label (16-01); version_file reader (16-06)
provides:
  - kitty Linux vendor script method with launch=n and bin_dir ~/.local/kitty.app/bin
  - load-time allowlist plus shlex.quote for script args
  - bin_dir or a load-bearing no bin_dir comment for the five own-installer scripts
  - sdkman version_file ~/.sdkman/var/version
affects: [16-14]

actuals:
  tokens: 2759
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - script args are a load-time regex allowlist, then shlex.quote into sh -s --
    - a script method with no static location says no bin_dir in a Verified comment

key-files:
  created: []
  modified:
    - installer/registry.toml
    - installer/executors.py
    - installer/model.py
    - tests/test_registry.py
    - tests/test_executors.py
    - tests/test_model.py

key-decisions:
  - "kitty's vendor script ranks ahead of dnf/apt/pacman on mutable distros. That is resolve.py _RANK, not a special case."
  - "codex bin_dir is ~/.codex/packages/standalone/current/bin, the directory that holds the binary, not the ~/.local/bin symlink."
  - "claude and cursor-agent get no bin_dir. Their launcher directories are versioned or chosen by the installed binary."

patterns-established:
  - "The phrase no bin_dir inside a # Verified comment is the registry contract for a script method that cannot name a static directory."

requirements-completed: [D-07, D-16, D-19]

coverage:
  - id: D1
    description: "On immutable Fedora, kitty resolves to one script method. The pipeline ends in sh -s -- launch=n. A file at ~/.local/kitty.app/bin/kitty counts as installed and owned by own installer."
    requirement: D-19
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_kitty_linux_script_declares_vendor_bin_dir"
        status: pass
      - kind: unit
        ref: "tests/test_executors.py#test_script_executor_passes_args_after_sh_s"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_kitty_declared_location_counts_as_installed"
        status: pass
    human_judgment: false
  - id: D2
    description: "A script args element with a shell metacharacter is rejected at registry load. A script method with no args keeps today's pipeline."
    requirement: D-19
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_script_args_reject_shell_metacharacters"
        status: pass
      - kind: unit
        ref: "tests/test_executors.py#test_uv_script_without_args_is_byte_identical"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every script method declares bin_dir or detect_path, or its tool has a Verified comment containing no bin_dir. sdkman reads ~/.sdkman/var/version."
    requirement: D-07
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_every_script_method_declares_a_location_or_explains_no_bin_dir"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_sdkman_uses_init_script_and_declares_bin_dir"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 10: Kitty method and location audit Summary

**Kitty installs from its vendor script with launch=n, and own-installer tools either name where the binary lands or say why they cannot**

## Performance

- **Duration:** 24 min
- **Started:** 2026-10-10T13:52:08Z
- **Completed:** 2026-10-10T14:16:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Kitty on immutable Fedora resolves to the vendor script (`https://sw.kovidgoyal.net/kitty/installer.sh`, `args = ["launch=n"]`, `bin_dir = "~/.local/kitty.app/bin"`). Native dnf/apt/pacman methods stay. The stale "no applicable method" paragraph is gone; the `.txz` / `tar -xzf` limitation stays.
- Script `args` are a list of strings matching `^[A-Za-z0-9=._:/+-]+$` at load, then `shlex.quote`d into `sh -s --`. Absent args leave the pipeline unchanged.
- Own-installer locations are declared or explained. sdkman's script method sets `version_file = "~/.sdkman/var/version"` (live file read `5.23.0`).

## Task Commits

Each task was committed atomically:

1. **Task 1: kitty is installable and owned on Bazzite** - `3ee22f9` (feat)
2. **Task 2: location audit and sdkman version_file** - `759697d` (feat)

**Plan metadata:** this summary commit (`docs(16-10): summary for plan 16-10`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/registry.toml` - kitty script method; bin_dir or `no bin_dir` comments; sdkman `version_file`
- `installer/executors.py` - `_script` appends `sh -s --` only when `args` is non-empty
- `installer/model.py` - script `args` allowlist
- `tests/test_registry.py` - kitty resolve/install tests and the script-location scan
- `tests/test_executors.py` - `launch=n` suffix and the uv no-args regression
- `tests/test_model.py` - rejects `launch=n; rm -rf ~`

## Decisions Made

Location audit, fetched 2026-10-10. `bin_dir` only where the vendor script and the live host agree on the directory that holds the binary itself.

- **codex** — `bin_dir = "~/.codex/packages/standalone/current/bin"`. https://chatgpt.com/codex/install.sh places the binary at `${CODEX_HOME:-$HOME/.codex}/packages/standalone/current/bin/codex`. Live symlink: `~/.local/bin/codex -> ~/.codex/packages/standalone/current/bin/codex`. `CODEX_INSTALL_DIR` moves the symlink, not the binary.
- **claude** — no bin_dir. https://claude.ai/install.sh downloads into `~/.claude/downloads` and runs `claude install`. The script never names the launcher directory. Live: `~/.local/bin/claude -> ~/.local/share/claude/versions/2.1.296`.
- **opencode** — `bin_dir = "~/.opencode/bin"`. https://opencode.ai/install hardcodes `INSTALL_DIR=$HOME/.opencode/bin`. Live host has the binary there.
- **cursor-agent** — no bin_dir. https://cursor.com/install writes the binary under `~/.local/share/cursor-agent/versions/<release>` (the release id is baked into each fetched script) and only symlinks `~/.local/bin/cursor-agent`. Live host matches. The binary's directory is not static.
- **antigravity** — `bin_dir = "~/.local/bin"`. https://antigravity.google/cli/install.sh defaults `TARGET_DIR=$HOME/.local/bin` and copies `agy` there. Live host file (not a symlink) agrees. `--dir` is an override this method does not pass.

The phrase `no bin_dir` inside a `# Verified` comment is load-bearing for `test_every_script_method_declares_a_location_or_explains_no_bin_dir`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Old kitty zero-method assertions contradicted the new method**
- **Found during:** Task 1
- **Issue:** `test_kitty_has_no_linux_download_fallback` asserted immutable Fedora resolved to nothing and mutable Fedora to `dnf` only.
- **Fix:** Mutable Fedora is `["script", "dnf"]`. Immutable Fedora is `["script"]`. macOS stays `cask`. No `github_release`.
- **Files modified:** tests/test_registry.py
- **Verification:** that test passed in the Task 1 suite.
- **Committed in:** `3ee22f9`

**2. [Rule 3 - Blocking] Acceptance grep wants `kitty.app/bin` once**
- **Found during:** Task 1
- **Issue:** Citing `~/.local/bin/kitty -> ~/.local/kitty.app/bin/kitty` in the comment made `grep kitty.app/bin` return two lines.
- **Fix:** The comment names the install root and says the live symlink points at that root's bin directory. The path string stays on the `bin_dir` line. Observed live target: `/home/bazzite/.local/bin/kitty -> /home/bazzite/.local/kitty.app/bin/kitty`.
- **Files modified:** installer/registry.toml
- **Verification:** `grep -n 'kitty.app/bin' installer/registry.toml` returned one line, `2558:bin_dir = "~/.local/kitty.app/bin"`.
- **Committed in:** `3ee22f9`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both keep the suite and the acceptance grep honest. No new location field. No guessed bin_dir.

## Issues Encountered

Pyright rejected an untyped `args` loop and an untyped `monkeypatch` fixture. Casts follow the existing `list[object]` pattern. The annotation was folded into the task commits before `make validate`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 16-11.
- Plan 16-14 still explains gnu-bash, container, and alacritty. Kitty is no longer in that zero-method set.
- Adding `bin_dir` also feeds `collect_bin_dirs`. The managed PATH block is case-guarded since 15.8.

## Self-Check: PASSED

- `grep -n 'kitty.app/bin' installer/registry.toml` returned one line: `2558:bin_dir = "~/.local/kitty.app/bin"`.
- `grep -c 'genuinely has NO applicable method' installer/registry.toml` printed 0.
- `grep -c 'txz' installer/registry.toml` printed 3.
- `resolve_methods(kitty, Platform('fedora','amd64',True,True))` printed `['script']`.
- `grep -n 'version_file = "~/.sdkman/var/version"' installer/registry.toml` returned `1753`.
- A throwaway HOME with `~/.local/kitty.app/bin/kitty` present resolved ownership to `installer` / `own installer` / `direct`.
- `uv run pytest tests/test_registry.py tests/test_executors.py tests/test_model.py tests/test_resolve.py tests/test_status.py tests/test_version_status.py -q` passed.
- `uv run pytest -q` exited 0 and reached 100% with no FAILED line.
- `make validate` passed (ruff, format, pyright, bandit, vulture, shellcheck).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
