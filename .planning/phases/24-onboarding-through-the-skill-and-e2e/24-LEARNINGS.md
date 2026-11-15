---
phase: 24
phase_name: "Onboarding through the skill and e2e"
project: "tools-installer"
generated: "2026-11-15"
counts:
  decisions: 8
  lessons: 8
  patterns: 6
  surprises: 6
missing_artifacts:
  - "STATE.md (not read; the phase artifacts carry the decisions)"
---

# Phase 24 Learnings: Onboarding through the skill and e2e

## Decisions

### Alacritty builds from its release tag in a throwaway Distrobox (`cargo_distrobox` kind)
A new method kind builds the release tag with cargo in a Distrobox, stages `.new` siblings, smokes the staged binary, swaps with rollback, records a receipt, and always removes the box, the image this run pulled and the temp dir. It plugs into the resolver's one switch (rank 25, `needs distrobox and podman`), `download.artifact_paths` and `uninstall.remove_paths`, so install, receipt and removal share one formula.

**Rationale:** Alacritty has no Linux release asset and immutable hosts cannot take a package; one switch makes `_rejection` the single source of the reason so the review and the ladder cannot disagree.
**Source:** 24-01-SUMMARY.md, 24-CONTEXT.md (D-01..D-05)

### The image is removed only if this run pulled it, and never with `--force`
Tri-state `podman image exists` (exit 1 absent, other exit unknown); an existing or unknown image is kept and named in the row; a failed `rmi` is a note.

**Rationale:** D-19 protects a user's own pre-existing image. The owner confirmed "keep" in UAT test 9 by delegation (2026-11-14).
**Source:** 24-CONTEXT.md (D-19), 24-REVIEWS.md (R1-12), 24-UAT.md (test 9), 24-SECURITY.md (T-24-05)

### Terminfo goes to `~/.terminfo`, not `~/.local/share/terminfo`
ncurses 6.6 and Alacritty 0.17 do not search `~/.local/share/terminfo`; this was reproduced in a scratch HOME. SPEC R3, REQUIREMENTS ONB-06 and the ROADMAP criterion were amended with dated notes that keep the original words.

**Rationale:** The first path would install a terminfo nothing reads.
**Source:** 24-03-SUMMARY.md, 24-01-SUMMARY.md

### Alacritty is two owned regions: shell (follows zsh) and keys (install tuning, written once)
The `alacritty` and `alacritty-keys` regions share a file but neither writer touches the other's region. No Policies row was added; removing the tool strips both. herdr's `terminal.default_shell` follows zsh through the same synchronizer, absent-only and ledgered, reverted only while it still holds the recorded value.

**Rationale:** Phase 23.2 made every customization install-time tuning (user: "always, no question"). The ledger value allow-listed by key path (`DYNAMIC_KEYS`) means a tampered ledger removes nothing.
**Source:** 24-06-SUMMARY.md, 24-02-SUMMARY.md, 24-CONTEXT.md (D-08, D-08b, D-22, D-23)

### herdr onboarding: user tier, raw `github_release`, integration only for hosts it does not already serve, sidebar plugin as a standalone hook target
`HookPair.standalone` records and undoes `sidebar-markers` like a host but never prints it as one; the plugin is pinned to `castocolina/herdr-setup@2b5ca2a`; status `current` means the user's own and is left out; an unreadable status or plugin list sets up nothing.

**Rationale:** Conservative ownership: never claim a user's setup. An integration that edits an agent's main config must be undone before the binary goes (hooks-first removal order from 23.2).
**Source:** 24-07-SUMMARY.md, 24-CONTEXT.md (D-09, D-10, D-12)

### Real Alacritty build moved from the host to a nested-podman container target; the real host build became UAT test 6
The nested target stays self-cleaning with no `--privileged`. When it proved infeasible, UAT test 6 was marked REQUIRED and the agent ran it on the real host under the owner's delegation, with backups and a closing diff.

**Rationale:** AGENTS.md and the owner's 2026-11-07 decision forbid real installs on the host in automation (D-16 superseded by D-18).
**Source:** 24-CONTEXT.md (D-16, D-18), 24-08-SUMMARY.md, 24-VERIFICATION.md

### Script installs download first, then run (`curl -o file && sh < file`)
`executors._script` writes to a `mktemp` file with `--retry 3 --retry-all-errors`, traps `rm` on EXIT, and runs the shell only after curl succeeded.

**Rationale:** In `curl | sh` the pipeline status is the shell's, so a curl exit of 35 left the row INSTALLED (the 2026-11-08 bug, reproduced as the RED test).
**Source:** 24-09-SUMMARY.md

### A receipt-proven release reads current from its recorded tag
`Receipt.release` stores the tag the installer placed (fail-closed read and write); for an installer-owned tool with a clean receipt, `outdated` comes from the recorded tag, not the probed text. A tag that cannot be ranked keeps the probe's answer.

**Rationale:** sd v1.1.0 prints `1.0.0`, so the probe read OUTDATED forever and the rerun gate failed.
**Source:** 24-09-SUMMARY.md

---

## Lessons

### Shared contracts break test doubles the plan never listed
The 4-tuple `_perform` broke a fake in `tests/test_uninstall_e2e.py` outside the plan's file list. The new script text broke `test_fnm_installer_skips_its_shell_block`, which the plan missed among its "seven pinned tests". Line-number-pinned PATH tests (`test_shell_scripts_path.py`) failed on every edit above them.

**Context:** Plan review had already flagged unenumerated pinned tests (R1-06..R1-08). Plans that change a signature or a registry count should grep every test double and pin, not only the listed files.
**Source:** 24-01-SUMMARY.md, 24-09-SUMMARY.md, 24-04-SUMMARY.md, 24-REVIEWS.md

### Pinning tests that pass at once are not RED evidence
Several tasks reported tests that passed on first run because the tracer already carried the behavior (24-05 Task 2, 24-06 Task 2, 24-07 Task 3). The SUMMARYs say so and label them regression pins. One task (24-09 Task 2) wrote the implementation before the first red run and reproduced RED afterwards by reverting `installer/`.

**Context:** Honest labelling keeps the TDD record trustworthy; a tracer that is big enough to be green already absorbs later tasks' tests.
**Source:** 24-05-SUMMARY.md, 24-06-SUMMARY.md, 24-07-SUMMARY.md, 24-09-SUMMARY.md

### A rerun gate needs a product cause owner
Plan review found the new strict rerun gate would fail on the latest Fedora run (`2 installed, 1 updated`) and no plan owned the cause. The cause was split across a script-download bug and a recorded-release gap, fixed in 24-09.

**Context:** Adding a gate before its failures have an owner leaves it red; 24-09 was added to own them.
**Source:** 24-REVIEWS.md (R1-05), 24-04-SUMMARY.md, 24-09-SUMMARY.md

### Per-distro system dependencies were missing from the catalog
Debian failed on SDKMAN (needs `unzip`, which debian:13 lacks) and Arch also on puppeteer ("no zip archiver"). Forward fixes declared `unzip` and `zip` as system-tier catalog tools and added them to `requires`, so missing prerequisites read BLOCKED or MANUAL instead of FAILED.

**Context:** Found only by running the harness on three distros, not on Fedora alone; two product-fix rounds were used.
**Source:** 24-08-SUMMARY.md

### The first nested-podman probe could never succeed
The probe ran `true` inside `quay.io/podman/hello` (FROM scratch, no `true`) and chained `rmi` after the failing run, leaving the image behind. The recorded "infeasible" verdict was not evidence until the harness was fixed and re-run; the orchestrator then confirmed the limit by hand.

**Context:** A harness verdict is only as good as its probe; verify an "infeasible" result independently before relying on it.
**Source:** 24-REVIEW.md (E1, E2, nested feasibility), 24-08-SUMMARY.md

### Config-owning installs must model every way a user's config is found
Code review HIGH F1: `alacritty_config_path` missed `~/.alacritty.toml`, so the install created `~/.config/alacritty/alacritty.toml`, which Alacritty reads first and so hid the user's whole config. Related: `[general] import` files are not followed, so conflict guards miss imported bindings (now refused with a named reason). A user comment under a created TOML table made the revert refuse (F7).

**Context:** Fixed by reading alacritty(5)'s lookup order, refusing imports, and a guarded leaf-key revert fallback.
**Source:** 24-REVIEW.md (F1, F7, F13)

### Launcher links defeat binary attribution
claude (`~/.local/bin/claude` to `~/.local/share/claude/versions/<v>`) and brew read a blank Owner because the resolved binary sat outside every declared dir. Attribution now also tries the launcher the PATH hit names.

**Context:** UAT test 2 found it (the 23.2 O-8 observation); fixed in bc3a0e49 and re-checked in a fresh container. jq and codegraph stay blank by design (the fail-closed rule).
**Source:** 24-UAT.md (test 2)

### Install-created directories need recording, not only created files
After uninstalling Alacritty the UAT found an empty `~/.config/alacritty` left behind. The install now records the directories it created next to the created-file marker and the uninstall removes them only when empty. The keep-your-own-config path was not exercised on the host.

**Context:** Fixed in 96c4a309, covered by unit tests, not re-run on the host.
**Source:** 24-UAT.md (test 8), 24-VERIFICATION.md

---

## Patterns

### Module-level replaceable seam for an external query
`image_exists`, `has_python3`, `herdr_query` are public module-level functions tests replace, instead of patching `shutil.which` or other globals. A tri-state result separates "absent" from "unknown".

**When to use:** Any probe that can fail differently from "no"; mapping an error to "absent" would delete a user's image.
**Source:** 24-01-SUMMARY.md, 24-07-SUMMARY.md, 24-REVIEWS.md (R1-12)

### Executor raises after its cleanups; the engine's existing ladder ends the row FAILED
New executors and the update branch raise `ExecutorError` in `finally`-protected code and let it propagate, rather than adding a second failure channel.

**When to use:** Adding a method kind or an update path; keeps install and update signalling identical.
**Source:** 24-01-SUMMARY.md, 24-05-SUMMARY.md

### Compare-before-commit region writes with a whole-document re-parse
Each Alacritty write re-parses the whole new text with `tomllib` and commits via `write_if_unchanged`; the nested-TOML writer is header-aware and guarded by a whole-document compare. Each owned part (shell, SHELL, each binding) gets its own conflict guard and its own `partial:` warning.

**When to use:** Editing a file the user also edits.
**Source:** 24-06-SUMMARY.md, 24-02-SUMMARY.md

### Harness probe = container-side gather plus a pure verdict function
Every new e2e probe is a top-level bash function that prints prefixed fact lines, paired with a pure verdict the host tests drive with fixtures. Tester user, home and workspace are `NAME=value` parameters with byte-identical defaults.

**When to use:** Adding checks to `scripts/container-e2e-verify.sh` without running containers in unit tests.
**Source:** 24-04-SUMMARY.md

### Heading-anchored doc tests that parse the doc's own example
`tests/test_docs.py` parses the skill's fenced TOML example with `tomllib` and anchors on headings, not line numbers.

**When to use:** Pinning skill or docs text so edits to nearby lines do not break it.
**Source:** 24-03-SUMMARY.md

### Capture wrapper around the `ReleaseResolver`, never the `TagResolver`
`versions.capturing_resolver` records the resolved tag per method attempt (cleared at the start of each attempt) and returns the wrapped `Release` unchanged, so API digests still verify.

**When to use:** Recording what a resolver returned without changing what the caller sees.
**Source:** 24-09-SUMMARY.md

---

## Surprises

### Desktop Entry rules differ from the plan's wording
Only `Exec` is quoted; `TryExec` and `Icon` are plain strings (a quoted `TryExec` would not resolve); `Exec` needs two-level escaping and `%` doubled.

**Impact:** The plan's "double-quote a path with a space" was wrong for two of three keys; tests now pin the spec.
**Source:** 24-01-SUMMARY.md

### bandit B105 fires on a literal `"token"` dict key
`{"token": "$rule", ...}` tripped hardcoded-password detection and `nosec` is forbidden, so a `_row_token()` helper builds the dict.

**Impact:** A one-line helper replaced a suppression; values are unchanged.
**Source:** 24-02-SUMMARY.md

### An unprivileged outer container cannot host a Distrobox box
`distrobox create` always passes `--hostname`; the `quay.io/podman/stable` containers.conf pins `utsns="host"`, so it fails with "cannot set hostname when running in the host UTS namespace". `--uts=private` and a per-user `userns="auto"` also fail.

**Impact:** The nested target can prove only herdr's `default_shell`, uninstall and teardown; the real Alacritty build is proven only on the host (UAT test 6, about 4 minutes, image pulled and removed).
**Source:** 24-REVIEW.md (nested feasibility), 24-08-SUMMARY.md, 24-UAT.md (test 6)

### The node probe leaked evidence into the same pass
`_live_platform()` runs `node --version`; the pass took its evidence snapshot afterwards, so evidence recorded during the probe landed in the pass that should not see it.

**Impact:** `_pass` now snapshots evidence under the lock first, then reads the platform.
**Source:** 24-01-SUMMARY.md

### The host launch itself had side effects
Every `make setup` removed the legacy `alias npx` line and rewrote `~/.local/bin/npx` (documented launch repair); the first launch turned on six schedule timers (the agent turned them off); herdr was adopted into a receipt, so it became removable.

**Impact:** Real-host UAT leaves state the tests never touch; the closing diff caught it, and the owner needs to know herdr is now removable.
**Source:** 24-UAT.md (Agent-run UAT, test 5)

### `infocmp alacritty` cannot fail on Bazzite and Fedora
`ncurses-base` ships `/usr/share/terminfo/a/alacritty`, so the bare command succeeds after uninstall.

**Impact:** The UAT bullet was reworded to `infocmp -A ~/.terminfo alacritty`.
**Source:** 24-UAT.md (test 8)
