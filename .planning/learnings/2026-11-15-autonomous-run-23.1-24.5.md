# Autonomous run learnings: phases 23.1 to 24.5 (2026-11-13 to 2026-11-15)

Sources are cited inline. `P:<n>` means `.planning/phases/<dir>/<n>-LEARNINGS.md` (links in section 4).
`M:<name>` means the memory file `<name>.md` under
`/home/bazzite/.claude/projects/-var-home-bazzite-git-personal-tools-installer/memory/` (read only).

## 1. Scope and outcome

The run covered eight phases: 23.1 (host safety: drop the eight skill-pack catalog entries, sandboxed tests),
23.2 (install-time tuning instead of Policies knobs, plus a silent-step indicator), 24 (onboarding through the
skill and e2e: Alacritty via a throwaway Distrobox, herdr, script-install and release-tag fixes), 24.1 (Neovim as a
registry-only row, EDITOR/VISUAL tuning, pinned kickstart starter), 24.2 (Schedules view: seven built-in
systemd/launchd schedules, one runner, one flock), 24.3 (catalog-audit skill and `make audit-catalog`, OpenCode v2,
npm `latest` source), 24.4 (retire the npx, npm and pip guard aliases and redirects) and 24.5 (brew, then bun,
then volta install priority). The phase files record these gates:

- 23.1: three plan-review cycles (5 HIGH, then 0, then 0), code review of 22 rows (18 confirmed, one BLOCKER,
  15 fixed), container e2e (P:23.1).
- 23.2: code review of 15 items fixed test-first; container e2e run #9 all tracers green
  (`TRACER_SETTINGS_INSTALLED_OK agents=6 keys=29`, `TRACER_LEFTOVER_OK`); seven container UAT tests passed (P:23.2).
- 24, 24.1: plan review, code review, three-distro container harness, agent-run UAT (24 included a real-host
  Alacritty build under owner delegation; 24.1 macOS test 8 deferred) (P:24, P:24.1).
- 24.2, 24.3: three plan-review cycles (24.2), code review F1..F19 and F1..F21, real-systemd and landing container
  checks (24.3 re-recorded on the fixed tree), security audit, skill-judge FINAL 88.8% B (24.3); macOS deferred
  (P:24.2, P:24.3).
- 24.4: three plan-review cycles, code review, security 27 of 27 closed, final gate 7339 passed / 6 skipped /
  96% coverage, byte-exact container UAT (P:24.4).
- 24.5: three plan-review cycles (27, 14, 6, then 0 findings), code review CR-01 and WR-01..WR-03 fixed, security
  audit, container `bun-lifecycle` run, UAT (P:24.5).

## 2. Cross-phase lessons

### 2.1 Deleting, retiring or adding to a shared list breaks tests the plan never listed
- Statement: a deletion, a signature change, a new registry row or a new view reaches pins, fakes and
  line-number tables outside the plan's file list. The review cost recurred in every phase.
- Phases and sources: 23.1 (plans 07, 08, 12, 15 retargeted unlisted tests; line-keyed
  `test_shell_scripts_path.py`), 23.2 (plan 08 removed a whole test file, 6026 to 6005 collected), 24 (4-tuple
  `_perform` broke a fake in `tests/test_uninstall_e2e.py`), 24.1 (new row broke three pinned registry counts),
  24.2 (seventh `VIEWS` row broke five test files plus a signature pin; deleting daemon policies dropped three
  guarantees nobody listed), 24.3 (stale pin line numbers, R1-01..R2-02), 24.4 (same defect in every review cycle:
  H7..H10, C3-4, C3-5; WR-02 lost the only `_display_path` test), 24.5 (`tests/state_doubles.py`,
  `test_ownership.py`, four shifted line keys).
  Sources: P:23.1, P:23.2, P:24, P:24.1, P:24.2, P:24.3, P:24.4, P:24.5.
- Rule: before planning a deletion or a shared-contract change, grep every reader of the symbol, the count and the
  line key, tests and doubles included, and list them in the plan's "pins this breaks". Name pins by symbol, not
  line. When deleting a feature, write a ledger mapping each removed test to the test that now asserts the same
  behaviour (24.2 migration ledger), and move pinned counts in the same commit as the row.

### 2.2 Code review finds what plan review and executors miss
- Statement: plan-review cycles converged, yet the post-execution code review still found the phase's worst defects.
- Phases and sources: 23.1 (plan review reached 0 HIGH; code review still found BLOCKER C-01 plus guard holes),
  23.2 (the real HIGH was a PATH-repair early return behind the redirect shim), 24 (F1: `~/.alacritty.toml` lookup
  hid the user's config), 24.1 (HR-01, the only HIGH: EDITOR detection missed `case`, `time`, `&&` forms), 24.2
  (five HIGHs after three plan cycles), 24.3 (F1: `verify --state` rewrote any JSON file), 24.5 (CR-01:
  `BUN_INSTALL*` not cleared in the sandbox; WR-01..WR-03).
  Sources: P:23.1, P:23.2, P:24, P:24.1, P:24.2, P:24.3, P:24.5.
- Rule: never skip the post-execution code review because plan review converged. Run several lanes (deep,
  ponytail, external); a finding two lanes report independently (23.1 CR-01/PT-01, 23.2 C-01) is high signal. Verify
  each HIGH against source before acting: 24.4 verified 19 of 27 HIGHs and refuted the rest with evidence, and 23.2
  rejected a "dead code" claim after finding a caller (C-07). Write a failing test before each fix.

### 2.3 Container or real-host runs catch what mocked tests cannot
- Statement: real systems, distros and tools exposed defects that thousands of fake-based tests passed over.
- Phases and sources: 23.2 (cursor-agent default key, leftover dirs, blank-file bytes found only by e2e), 24
  (Debian and Arch lacked `unzip`/`zip`; `curl | sh` hid a curl exit 35), 24.2 (real systemd: `uv cache prune`
  lock wait, holder not outliving the exec session; 6800 mocked tests missed both), 24.3 (PID 1 not reaping;
  `service.json` credential file left after `service start`), 24.5 (brew-first moved the `yq` receipts probe;
  `bun add -g` does not update, found live), 24.1 (`tree-sitter` CLI missing, zero-LSP probe result unaffected).
  Sources: P:23.2, P:24, P:24.1, P:24.2, P:24.3, P:24.5.
- Rule: any phase that changes install, removal, tuning or timers needs one real container pass, per distro where
  the behaviour differs, on the fixed tree. A harness verdict is only as good as its probe: the 24 nested-podman
  probe could never succeed (`true` absent in a FROM-scratch image), so confirm an "infeasible" result by hand
  (P:24).

### 2.4 Test seams must be hermetic against the developer's real environment
- Statement: tests that read real HOME, PATH, `BUN_INSTALL`, git env or global state pass on the author's host and
  fail or leak elsewhere.
- Phases and sources: 23.1 (guard searched `env.get("PATH")` while Popen used `os.defpath`; coverage test derived
  its cases from the module under test), 23.2 (`COPILOT_HOME` joined the cleared names; explicit `environ`
  argument), 24.1 (global git runner needs an autouse reset; git child inherited `GIT_DIR`, `insteadOf`, hooks;
  fixed `/usr/bin:/bin` child PATH dropped a host-only zsh; bare `timeout` absent on macOS CI), 24.4 (worktree
  id containing `bad` broke a path-embedding assertion), 24.5 (offline double lacked a bun reader; sandbox did not
  clear `BUN_INSTALL*`; real-node pytest forbidden by the launch guard), 24.1 `verify-registry` wrote to the real
  `~/.local/state` (P:24.1).
  Sources: P:23.1, P:23.2, P:24.1, P:24.4, P:24.5.
- Rule: inject the runner, the environment and the reader; give the injected default a refusing behaviour and an
  autouse reset. Add every env name a sandboxed tool consults to the cleared list, plus a test that its dirs
  stay under the scratch HOME. Resolve paths the way the launcher does (`os.get_exec_path(env)`). Use unique
  sentinel strings in assertions. Redirect `--state` and other write paths into the scratchpad when running
  read-only commands by hand.

### 2.5 Fail-closed reads that are too broad, and defaults returned in place of an error
- Statement: refusing on any doubt is right for deletion, but a read that fails whole turns a small problem into a
  global "unknown", and returning defaults on a read error can re-arm state the user turned off.
- Phases and sources: 23.1 (a fail-open "absent" check hid real problems, the opposite error), 24.2 (OSError read
  returned defaults, so a reconcile could re-arm defaults over an unreadable file; non-UTF-8 rc crashed a
  marker read), 24.3 (a rate limit became a permanent `unknown` in an immutable report), 24.5 (one legacy
  non-lowercase global made the whole bun inventory unreadable, WR-01; bun-only host read `unknown`, WR-02),
  24.1 (a false EDITOR yield is the cheap error, F1/F10), 24.4 (first-read OSError warns with permission advice
  only).
  Sources: P:23.1, P:24.1, P:24.2, P:24.3, P:24.4, P:24.5.
- Rule: separate "absent", "unreadable" and "unknown" as distinct states, never map an error to a default.
  Fail closed per item, not per inventory: one bad entry skips that entry and names it. Transient failures
  (rate limits) must retry or exit with a distinct code (exit 75), never be written into a record that cannot be
  rewritten. Pick the cheap error on purpose and say so in the decision.

### 2.6 Guards must cover every route to the same capability
- Statement: a guard or repair written for the obvious route left the others open.
- Phases and sources: 23.1 (call before definition, `bash -s`, `--rcfile`, renamed shells, unguarded Python
  children, five unpatched resolvers; launch repair composed once for every route), 24.4 (`_is_leftover` used by
  eight paths; Pi's `pnpm list` probe and the schedule runner ran a leftover by name until cycle 3, C3-2),
  24.2 (F3/F4 fixed by moving the lock so every user verb takes it), 24.3 (symlink refusal extended to every
  path component, F7; "container" check fooled by toolbox/distrobox, F13), 24.5 (one helper
  `method_bin_dir` for every reader).
  Sources: P:23.1, P:24.2, P:24.3, P:24.4, P:24.5.
- Rule: define the rule once in a shared helper and route every consumer through it. Enumerate the routes before
  review: entry points, child processes, probes, the stdlib runner copy, harness scripts. Add a behavioural
  "every route" test and a scan test, and word the scan's claim as narrowly as it can see (24.4).

### 2.7 Gate evidence is per tree and goes stale after fixes
- Statement: a verification, container record or UAT result proves one tree. Later fixes make it stale.
- Phases and sources: 23.2 (verification ended `human_needed`, then went stale after e2e fixes touched covered
  files), 24.3 (landing record sat on `394fa836`, carried forward as C1 until re-run on `eb9c2ea5`; committed
  `findings.toml` sources became unreadable after F5), 24.4 (final gate re-confirmed on the merged tree because a
  worktree name broke one test), 24 (install-created directory fix 96c4a309 not re-run on the host), memory
  quirks (phase.complete refuses stale VERIFICATION.md).
  Sources: P:23.2, P:24, P:24.3, P:24.4, M:project_gsd_run_quirks.
- Rule: record the commit a gate ran on. After any review fix that touches covered files, re-run the container
  check and re-run `gsd-verifier` before `phase.complete`. Complete a phase right after its UAT. Say "carried
  forward, not re-run" in the audit when it applies.

### 2.8 Safety and docs wording must match the real guarantee
- Statement: requirement, message and doc text promised more than the code could do, or named the wrong remedy.
- Phases and sources: 24.4 (an unconditional "never deleted" was unachievable, amended to a re-check guarantee with
  a `shortcut:` comment; a bare "Could not check" warning would have led a user to delete `~/.bashrc`; `hash -r`
  does not clear aliases; `_is_leftover` overclaimed "can never disagree"; stale "re-apply a policy" text, WR-01),
  23.1 (the "passing without GSD is intended" framing was refuted), 24.5 (docs avoid "bun runs without node" and
  "stricter than pnpm"; finding labels name what was checked), 24.3 (skill instruction held a shell substitution,
  D8-1), 24.1 (SPEC R3 clause rested on a misreading of 22 D-07, amended).
  Sources: P:23.1, P:24.1, P:24.3, P:24.4, P:24.5.
- Rule: when a guarantee has a residual window, amend the SPEC and requirement to the true statement and record
  the accepted risk, instead of keeping a claim the code cannot back. Key user advice on what the launch verified.
  Pin load-bearing doc phrases with tests, and grep stale user-facing text after any deletion.

## 3. Orchestration and process lessons

- Convergence cap. At plan-review cycle 3 with fewer than 4 critical+HIGH concerns left, fix them (actionable
  MEDIUM/LOW included), run a checker pass, commit and execute, with no question. With 4 or more, escalate.
  Owner, 2026-11-07: "If you reach 3 reviews and the criticals and highs are fewer than 4, you can fix them and
  execute from here on." Source: M:feedback_convergence_cap_rule. Three cycles ran in 24.4 and 24.5 (P:24.4, P:24.5).
- Convergence hand-back. A convergence subagent can return while its nested opencode review still runs. The brief
  must say to wait on a background `until ! kill -0 <pid>` loop, or report the PID and log path. Only one agent
  writes `<phase>-REVIEWS.md` per cycle. Source: M:project_gsd_run_quirks.
- Agent-run UAT. Agents run the UATs, each in its own `--no-focus` herdr tab, driving the real TUI in a disposable
  container (`ti-uat-<phase>-<distro>`, started with `--init`), saving captures, asking jev only on low
  confidence, closing tab and container at the end, at most two agents at a time on the 30 GB host. Owner-decision
  tests are recorded "kept (owner delegated)", macOS tests with no CI path are deferred, and findings are fixed
  without asking. The real host is used only when a container cannot prove the step (the Alacritty distrobox
  build), with the owner's OK for that round, backups first, a closing diff, and backups deleted afterwards.
  Owner, 2026-11-14 (Spanish in memory, translated here): why do you need my UAT, use the herdr skill to open
  another tab, run the tests, take captures, evaluate them with jev and close the tabs. Source:
  M:feedback_agent_run_uat. Applied in 24.1, 24.3, 24.4, 24.5 (P:24.1, P:24.3, P:24.4).
- UAT done criteria. A UAT Expected clause states a verifiable done plus its cleanup: installed by
  tools-installer (receipt, owner) and uninstalled cleanly, or the skill produced its report. Whether a probe used
  a self-removing container does not matter; leaving something running does. A result that conflicts with the
  criterion is reported to the owner before the clause or the result is rewritten. The orchestrator had silently
  rewritten "no container on the host" and flipped the result, and the owner asked which criterion was changed and
  why. Source: M:feedback_uat_done_criteria. Seen in 24.3 UAT test 6 (P:24.3).
- UAT then verification. After an agent UAT, VERIFICATION.md is still `human_needed` and `phase.complete` refuses
  it; re-run one short `gsd-verifier` that folds in the UAT, then complete. Source: M:project_gsd_run_quirks.
- One-dot phase numbers. `gsd-tools phase insert` nests (24.3 gives 24.3.1, then 24.3.1.1) and ai-kit `fold.py`
  rejects two dots. Take the next free one-dot number, insert, then rename dirs, file prefixes and every text
  reference in one commit (done for 24.4 and 24.5). The nested 24.3.1 number drew a direct owner rebuke. Source:
  M:project_gsd_run_quirks.
- Phase branches and completion. `git.branching_strategy = phase` creates `gsd/phase-<N>-...` on a phase's first
  commit; fast-forward main to it, delete the branch, then push. `phase.complete` moves STATE to phase 17, so reset
  with `state.begin-phase --phase <next> --name ... --plans 0`. After a manual merge `worktree.cleanup-wave` fails
  with base_mismatch, so remove worktrees by hand. Source: M:project_gsd_run_quirks.
- Shared scratchpad. Parallel executors share the session scratchpad, so give each script a plan-id prefix (a stray
  script once ran in another executor's worktree). Source: M:project_gsd_run_quirks. Related in the phase files:
  executors could not write the plan-head ledger under the shared `.git`, the worktree guard refused compound
  commands, and commit counts were measured from the base SHA (P:23.1, P:23.2, P:24.4).
- Overrides for container plans. The generic executor brief forbids containers. A plan whose task is a real
  harness run needs an explicit override in the spawn prompt: harness-only, `tools-installer-e2e-*` names, remove
  pulled images, wait with background loops. Source: M:project_gsd_run_quirks. Container runs dominated wall
  clock in 24.5 (about 6 h for plan 09, dnf bootstraps, one 50 min) (P:24.5).
- Close what you open. Every brief that opens herdr tabs, containers or watchers must require closing them before
  returning, and the orchestrator checks `herdr tab list`, `podman ps -a` and `pgrep` after each agent returns,
  closing only its own leftovers. Owner, 2026-11-07: "Please don't leave processes, pods, containers, open
  windows or unused terminals; in tty-uat you opened multiple panes, left them open and opened another." Source:
  M:feedback_close_what_you_open.
- Push per wave. After each wave merge with `make validate` and `make test` green, push main (no force, no
  `--no-verify`), watch CI on ubuntu and macOS and log it; the phase-close push still happens. Prompted on
  2026-10-16 when 100 commits had piled up locally. Source: M:feedback_push_per_wave.
- File count is not effort. Resolve plan-checker `scope_sanity` warnings with a one-line justification, not a
  split; mark genuinely heavy plans `executor_model: sonnet` (default haiku@high). Owner, 2026-11-07: "more files
  doesn't mean more effort; anyway if more effort is needed we can escalate to sonnet in most cases." Source:
  M:feedback_file_count_not_effort.
- Check code before claiming limits. A capability claim in a report, brief or disposition cites the code line or
  command output behind it. On 2026-11-13 the orchestrator said the installer cannot remove SDKMAN tools; the owner
  corrected it (translated: "That is not true, sdkman can uninstall packages"). The installer hands off
  `sdk uninstall <candidate> <version>` by design (`installer/ownership.py` `_REMOVAL_COMMANDS`), and the wrong claim
  had already gone into an audit brief and four dispositions. Source: M:feedback_check_code_before_claiming_limits;
  the four rows ended as `proposed` with a `no change` note in 24.3 (P:24.3).
## 4. Per-phase highlights

- 23.1, [23.1-LEARNINGS.md](../phases/23.1-host-safety-drop-the-skill-pack-catalog-entries-sandboxed-te/23.1-LEARNINGS.md)
  - Skill-pack module deleted in staged order (verbatim move, frozen fixture, consumers before producers);
    retired receipts removed only on a placement-shape proof, the rest listed as "remove it yourself".
  - Strict fail-closed shell parser and a reviewed `CHECKOUT_SCRIPTS` table guard test launches; code review
    found one BLOCKER and many guard holes after clean plan review.
  - The npx shim translator work was later superseded by 24.4.
- 23.2, [23.2-LEARNINGS.md](../phases/23.2-install-time-tuning-instead-of-policies-knobs/23.2-LEARNINGS.md)
  - One writer and dispatcher for all install tuning; Policies shrank from 23 rows to 7; a user-deleted key stays
    deleted; the rule is written into the onboarding skill and pinned by tests.
  - Code review found a HIGH (PATH repair vs the redirect shim); container e2e found the cursor-agent default and
    leftover-directory defects, and revert now restores bytes.
  - Copilot Linux is a checksummed `github_release` tarball; same-release checksum covers corruption only (R4).
- 24, [24-LEARNINGS.md](../phases/24-onboarding-through-the-skill-and-e2e/24-LEARNINGS.md)
  - `cargo_distrobox` method builds Alacritty from its tag and always removes box, pulled image and temp dir;
    terminfo goes to `~/.terminfo`; herdr onboarded with conservative ownership.
  - `curl | sh` replaced by download-then-run, and recorded release tags fix the "outdated forever" read.
  - Real Alacritty build ran on the host as UAT test 6 only after a nested-podman target proved infeasible.
- 24.1, [24.1-LEARNINGS.md](../phases/24.1-onboard-neovim-through-the-tool-onboarding-skill/24.1-LEARNINGS.md)
  - Neovim is a registry-only row on the generic release, receipt and removal paths; opt tree removed whole
    (SPEC R3 amended, owner kept it).
  - EDITOR/VISUAL and the pinned kickstart starter are install tuning with no question and yield to the user;
    EDITOR detection and git-env isolation came from review.
  - Zero-LSP probe counts clients inside the running nvim and fails on a Lua error in stderr.
- 24.2, [24.2-LEARNINGS.md](../phases/24.2-schedules-view/24.2-LEARNINGS.md)
  - Seven code-owned schedules, one stdlib runner, one flock, one JSON state file with sha256 fingerprints; a
    damaged state file is sticky.
  - Real-systemd container run found two bugs 6800 mocked tests missed; code review F1..F5 fixed same-grid
    pile-up and cross-process races by moving the lock.
  - macOS launchd behaviour could not be shown by any run available; macOS UAT deferred.
- 24.3, [24.3-LEARNINGS.md](../phases/24.3-catalog-audit-skill/24.3-LEARNINGS.md)
  - Gated Python fact gatherer plus a text-only skill; immutable reports with a completion marker; sticky drift and
    a disposition gate.
  - First audit gave 72 drift rows from an untouched tree; OpenCode v2 update and removal recipe, `latest_npm`
    source, `permission` to `permissions` retirement with a revert-only table.
  - Review fixes made the landing record stale; re-recorded on the fixed tree; skill-judge FINAL 88.8% B.
- 24.4, [24.4-LEARNINGS.md](../phases/24.4-retire-the-npx-npm-and-pip-guard-aliases-and-redirects/24.4-LEARNINGS.md)
  - Guard aliases, shims and `make guard/unguard` retired; a never-raise launch repair removes installer-written
    leftovers with an identity re-check before unlink.
  - Wording amended to the real guarantee (re-check, not "never deleted"); one `_is_leftover` definition for every
    route.
  - Gate: 7339 passed, 6 skipped, 96% coverage; security 27 of 27 closed.
- 24.5, [24.5-LEARNINGS.md](../phases/24.5-javascript-install-priority-brew-then-bun-then-volta/24.5-LEARNINGS.md)
  - Brew first for every tool (owner confirmed after measured fallout: 51 tools change first method on macOS, 57
    on Fedora with Linuxbrew); bun method kind with its own inventory, update and strict own-tree loader.
  - Golden first-method table plus a frozen pre-phase rank invariant pin the resolver.
  - Review found a non-hermetic sandbox (`BUN_INSTALL*`) and over-broad fail-closed inventory reads.

## 5. Open follow-ups the sources name

- macOS: 24.1 UAT test 8 (git stub dialog without Command Line Tools) deferred (P:24.1); 24.2 UAT test 8 and all
  launchd behaviour (`bootout` interrupting a running job, GUI-less bootstrap, sleep catch-up, `realpath` on
  macOS 13+) never exercised (P:24.2); 24.3 UAT test 5 (drawio-desktop 32.6.10 on macOS) deferred (P:24.3); 24.4
  macOS paths, zsh as a login shell and the owner's real Bazzite files not covered (P:24.4).
- Non-interactive `zsh -lc` from a bare environment does not see `~/.bun/bin`, because only `~/.zshrc` is wired.
  A script run that way will not find bun-installed commands; the owner was told (P:24.5, UAT test 3).
- Accepted residuals: 24.4 unlink swap window (T-24.4-02) and FIFO swap stalling one scheduled job
  (`schedule_runner._resolve` without `O_NONBLOCK`) (P:24.4); 24.5 failed `bun add -g` manifest state after a
  partial failure (T-24.5-32, one sample) and the single-sample stranded peer after mmdc removal (P:24.5); 23.2
  residuals R1 (BOM-only or U+00A0-only file reverts to different inert bytes), R3 (volta rc behaviour not
  test-pinned) and R4 (same-release checksum), plus RECONFIGURE's `apply_install_tuning` not isolated per action
  (P:23.2); 23.1 residual R-10 (older `exec_tester "test -e"` leftover checks keep the weak shape) and C-14
  (a refusal from a leftover thread can fail the wrong test) (P:23.1); 24.1 `~/.local/state/nvim/nvim.log` survives
  removal (F11) and, if the API returns no digest, the Neovim tarball installs as `unverified` (T-24.1-01, R3)
  (P:24.1); 24.4 transitive: an unremovable leftover `npm` can be hit by a vendor script (T-24.4-11) (P:24.4).
- Phase 25 inheritance: the `host_setup` kind, `HOST_SETUPS`, its probe and the update branch stay in code and
  are handed to Phase 25 (LEAN-01) (P:24.5, P:24.4); 23.2 left `ConfirmSensitiveAction`, `SensitiveActionScreen`
  and `default_enabled_sensitive_actions` for Phases 24.1 and 25 (P:23.2).
- Registry and audit backlog: 24.3 first audit rows went to Backlog 999.14 (30), 999.15 (22) and 999.16 (1); the
  `dispositions.toml` grammar has no `no-change` value (recorded, not fixed); nine skill-judge MEDIUM/LOW items
  stay open; drawio-desktop pin drift 32.6.1 vs 32.6.10 was logged as a follow-up (P:24.3, P:24.1). OpenCode
  hosts that installed through the brew tap stay on 1.19.5 (P:24.3).
