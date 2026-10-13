---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 16
subsystem: testing
tags: [detection, ownership, validation, host-proof]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: plans 16-01 through 16-15, the production composition in setup.py
provides:
  - Read-only host proof of the phase defects via the production functions
  - Backfilled Per-Task Verification Map
  - Seven pending Phase 16 walkthrough rows for end-of-phase human review
affects: [verify-work]

actuals:
  tokens: 3600
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - Host proof calls the same composition setup.py wires, and writes skill cache only under a TemporaryDirectory

key-files:
  created:
    - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-16-SUMMARY.md
  modified:
    - .planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-VALIDATION.md

key-decisions:
  - "resolve_status was called with allow_fetch=False and an empty OutdatedReport so the proof does not hit GitHub or brew outdated. Installed version does not depend on that fetch."
  - "The execute-screen preflight was not driven. Enter on that screen runs configure_path. It stays in the pending walkthrough."

patterns-established:
  - "A seeded -k that collects nothing is retargeted at the test that exists, and the old exit code is recorded. The host is not edited to make a proof match."

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16, D-17, D-18, D-19, D-20, D-21, D-22, D-23, D-24]

coverage:
  - id: D1
    description: "Production resolve_ownership, resolve_status, inspect_skill_packs, refresh_skills, resolve_methods, unavailable_reason, and path_writer_lines_for on this host, read-only."
    requirement: D-01
    verification:
      - kind: other
        ref: "uv run python proof (not committed); sections (a)-(g) below"
        status: pass
    human_judgment: false
  - id: D2
    description: "Per-Task Verification Map Task ID, Plan, and Wave cells filled; every row command exited 0."
    verification:
      - kind: other
        ref: "grep -c '| TBD |' 16-VALIDATION.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "TUI walkthrough of Owner, versions, skill packs, kitty/alacritty, execute preflight, mmdc, and Doctor guidance."
    verification: []
    human_judgment: true
    rationale: "Rendered column text, dim styling, and on-mount preflight cannot be confirmed without driving the TUI. Enter on the execute screen and in Doctor is excluded on this host."

duration: 16min
completed: 2026-10-10
status: complete
---

# Phase 16: Detection, version, and ownership Summary

**Read-only host proof that brew-owned Java tools are off-policy Homebrew, SDKMAN versions resolve, skill packs report present, and kitty/alacritty explain themselves**

## Performance

- **Duration:** 16 min
- **Started:** 2026-10-10T17:16:38Z
- **Completed:** 2026-10-10T17:32:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Production composition on this Bazzite host: groovy/gradle/maven/java are `owner='brew'` `off_policy=True` `owner_label='Homebrew'`; springbootcli is SDKMAN `4.1.0`; sdkman is `5.23.0`; skill packs that the direct probe marks present stay present through `VersionRefreshService.refresh_skills` over the full catalog; kitty has a `script` method and `own installer`; alacritty's reason is the immutable-host sentence.
- `16-VALIDATION.md` map backfilled. `grep -c '| TBD |'` is 0. `nyquist_compliant` and `wave_0_complete` are true.
- Seven Phase 16 walkthrough rows are pending. The execute screen and Doctor were not opened.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end host proof of the five defects (read-only), plus the full suite and validate** - `0678ab9` (docs)
2. **Task 2: TUI walkthrough of the user-visible states** - `f3697ba` (docs)

**Plan metadata:** this commit (docs)

## Files Created/Modified

- `.planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-VALIDATION.md` - map backfill and pending walkthrough rows
- `.planning/phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-16-SUMMARY.md` - verbatim host proof

## Decisions Made

- `allow_fetch=False` and an empty `OutdatedReport` for `resolve_status`. The installed field is what the defect asks for. sdkman `stale=True` is that skip, not a missing version.
- Defect (5), the on-mount "already current" preflight, was not driven. Task 2 forbids automating the TUI, and enter on the execute screen rewrites rc files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Seeded `-k` filters collected no tests**
- **Found during:** Task 1 (map backfill)
- **Issue:** `tests/test_catalog_tui.py -k multi_host` and `tests/test_rcclean.py -k guard_in_place` exited 5. The truncation test is `test_skill_owner_cell_lists_hosts_and_truncates_when_wider_than_the_column`. Guard-in-place tests live in `tests/test_shellrc.py`.
- **Fix:** Row commands are now `-k skill_owner_cell` and `tests/test_shellrc.py tests/test_rcclean.py -k "guard_in_place or path_writer_lines"`. Both exited 0 (1 passed; 5 passed).
- **Files modified:** `16-VALIDATION.md`
- **Verification:** those two commands, exit 0
- **Committed in:** `0678ab9`

**2. [Rule 1 - Bug] D-18 `-k broken` skipped the dangling predicate tests**
- **Found during:** Task 1
- **Issue:** The seeded command exited 0 but only selected catalog Inst-marker tests. `test_dangling_shim_*` does not contain `broken`.
- **Fix:** Command is `-k "broken or dangling"`. 10 passed.
- **Files modified:** `16-VALIDATION.md`
- **Verification:** `10 passed, 179 deselected`
- **Committed in:** `0678ab9`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Filter strings only. No production code. Host values that differ from the old repro were recorded, not changed.

## Issues Encountered

- mmdc is not a dangling shim on this host. Recorded below. Not repaired and not forced.
- Full suite took 320.66s, over the validation doc's 300s latency cap. That sign-off box stays unchecked.
- openspec and spec-kit returned `{}` from `inspect_skill_packs` (no host probes). The four packs the walkthrough names all had at least one `present` host.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Automated half of the phase goal is recorded. Walkthrough rows (1)-(7) are pending for one human pass. Do not press enter on the execute screen or in Doctor on this host.
- mmdc walkthrough row (6) may not apply: `broken=False`, `owner='brew'`.

## Host proof (verbatim)

Proof imports were the production modules. `cache_path` for `refresh_skills` was a file in `tempfile.TemporaryDirectory()`. `~/.bashrc`, `~/.zshrc`, `~/.myshellrc`, and `~/.local/state/tools-installer/versions.json` SHA-256 and mtime were identical before and after. `~/.shellrc`, `~/.zprofile`, and `~/.zshenv` were absent both times.

### (a) resolve_ownership

```
groovy: owner='brew' package='groovy' confidence='direct' off_policy=True owner_label='Homebrew' also_installed_note=None
gradle: owner='brew' package='gradle' confidence='direct' off_policy=True owner_label='Homebrew' also_installed_note=None
maven: owner='brew' package='maven' confidence='direct' off_policy=True owner_label='Homebrew' also_installed_note=None
java: owner='brew' package='openjdk' confidence='direct' off_policy=True owner_label='Homebrew' also_installed_note=None
springbootcli: owner='sdkman' package='springboot' confidence='direct' off_policy=False owner_label='SDKMAN' also_installed_note=None
```

### (b) resolve_status installed

`allow_fetch=False`, `entry=None`, empty `OutdatedReport`.

```
springbootcli: installed='4.1.0' source='sdkman' stale=False owner='sdkman'
sdkman: installed='5.23.0' source='installer' stale=True owner='installer'
```

### (c) inspect_skill_packs and refresh_skills

```
ponytail: {'claude': 'present', 'codex': 'present'}
openspec: {}
superpowers: {'claude': 'present', 'codex': 'absent', 'pi': 'present'}
softaworks-agent-toolkit: {'adal': 'absent', 'claude': 'present', 'codex': 'present', 'cursor': 'absent'}
matt-pocock-skills: {'amp': 'absent', 'claude': 'absent', 'codex': 'absent', 'cursor': 'absent', 'devin': 'absent', 'opencode': 'absent', 'pi': 'absent', 'windsurf': 'absent'}
opengsd: {'antigravity': 'absent', 'claude': 'present', 'codex': 'present', 'copilot': 'absent', 'cursor': 'present', 'kilo': 'absent', 'kimi': 'absent', 'opencode': 'present', 'windsurf': 'absent'}
spec-kit: {}
```

`grep -n 'refresh_skills(' installer/catalog_tui.py`:

```
444:                run_live(lambda: service.refresh_skills(self._catalog))
```

`VersionRefreshService.refresh_skills` over the full catalog, temp `cache_path`:

```
ponytail: hosts={'claude': 'present', 'codex': 'present'} stale=False direct_present=['claude', 'codex'] service_present=['claude', 'codex'] present_match=True
openspec: hosts={} stale=False direct_present=[] service_present=[] present_match=True
superpowers: hosts={'claude': 'present', 'codex': 'absent', 'pi': 'present'} stale=False direct_present=['claude', 'pi'] service_present=['claude', 'pi'] present_match=True
softaworks-agent-toolkit: hosts={'adal': 'absent', 'claude': 'present', 'codex': 'present', 'cursor': 'absent'} stale=False direct_present=['claude', 'codex'] service_present=['claude', 'codex'] present_match=True
matt-pocock-skills: hosts={'amp': 'absent', 'claude': 'absent', 'codex': 'absent', 'cursor': 'absent', 'devin': 'absent', 'opencode': 'absent', 'pi': 'absent', 'windsurf': 'absent'} stale=False direct_present=[] service_present=[] present_match=True
opengsd: hosts={'antigravity': 'absent', 'claude': 'present', 'codex': 'present', 'copilot': 'absent', 'cursor': 'present', 'kilo': 'absent', 'kimi': 'absent', 'opencode': 'present', 'windsurf': 'absent'} stale=False direct_present=['claude', 'codex', 'cursor', 'opencode'] service_present=['claude', 'codex', 'cursor', 'opencode'] present_match=True
spec-kit: hosts={} stale=False direct_present=[] service_present=[] present_match=True
```

### (d) kitty

```
methods=['script']
is_installed=True
owner_label='own installer' owner='installer'
```

### (e) unavailable_reason

```
gnu-bash: short='fedora not supported' detail='gnu-bash only supports macos.'
container: short='fedora not supported' detail='container only supports macos.'
alacritty: short='immutable host' detail='alacritty only declares native package-manager methods (dnf/apt/pacman), which this installer skips on an immutable (ostree) host.'
```

### (f) mmdc

```
broken=False owner='brew' package='mermaid-cli'
```

Not the dangling-shim shape. Left as-is.

### (g) path_writer_lines_for

`guard_path_writers` was not called.

```
duplicated=[PosixPath('/home/bazzite/.local/bin'), PosixPath('/home/bazzite/.bun/bin'), PosixPath('/home/bazzite/.volta/bin'), PosixPath('/home/bazzite/.local/share/fnm')]
rc_path=/home/bazzite/.bashrc index=52 guardable=True refusal=None block_owner=None
rc_path=/home/bazzite/.bashrc index=70 guardable=False refusal="inside the 'my-kitty PATH' block another tool manages; fix it in that tool" block_owner='my-kitty PATH'
rc_path=/home/bazzite/.bash_profile index=14 guardable=True refusal=None block_owner=None
rc_path=/home/bazzite/.bash_profile index=18 guardable=True refusal=None block_owner=None
rc_path=/home/bazzite/.bash_profile index=22 guardable=True refusal=None block_owner=None
rc_path=/home/bazzite/.profile index=6 guardable=True refusal=None block_owner=None
rc_path=/home/bazzite/.profile index=10 guardable=True refusal=None block_owner=None
```

## Verification

- `uv run pytest -q`: `3395 passed, 5 skipped in 320.66s (0:05:20)` EXIT:0
- `make validate`: ruff check passed, 141 files formatted, pyright `0 errors, 0 warnings, 0 informations`, bandit quiet, vulture quiet, shellcheck exit 0
- Map commands: ownership sdkman 10 passed; install_ownership sdkman 5 passed; off_policy 2 passed; skill_harnesses 1 passed; version_cache 17 passed; skill_owner_cell 1 passed; engine+post_install 44 passed; broken or dangling 10 passed; guard_in_place or path_writer_lines 5 passed; marker_block 4 passed. All EXIT:0.
- `grep -c '| TBD |' 16-VALIDATION.md` printed 0
- `grep -c "Phase 16 walkthrough" 16-VALIDATION.md` printed 8 (7 numbered rows plus one mention in the live-proof instructions)

## Self-check

- Sections (a)-(g) are the command output, not a paraphrase.
- Defect (5) preflight text was not observed. Walkthrough row (5) is pending.
- No rc file or the real version cache changed (SHA-256 match).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
