---
phase: 32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp
reviewed: 2026-11-21T00:00:00Z
depth: deep
files_reviewed: 45
files_reviewed_list:
  - .claude/architecture.md
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/agent_settings.py
  - installer/app.py
  - installer/executors.py
  - installer/model.py
  - installer/postinstall.py
  - installer/receipts.py
  - installer/registry.toml
  - installer/resolve.py
  - installer/run.py
  - installer/session.py
  - installer/update.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - tests/conftest.py
  - tests/e2e_aws_cli_driver.py
  - tests/e2e_bruno_driver.py
  - tests/e2e_evidence.py
  - tests/e2e_playwright_mcp_driver.py
  - tests/test_agent_settings.py
  - tests/test_app.py
  - tests/test_aws_cli_entry.py
  - tests/test_bruno_entry.py
  - tests/test_container_e2e_aws_cli.py
  - tests/test_container_e2e_bruno.py
  - tests/test_container_e2e_herdr_app.py
  - tests/test_container_e2e_playwright_mcp.py
  - tests/test_engine.py
  - tests/test_executors.py
  - tests/test_gh_stack_entry.py
  - tests/test_model.py
  - tests/test_phase32_consistency.py
  - tests/test_playwright_mcp_entry.py
  - tests/test_postinstall.py
  - tests/test_receipts.py
  - tests/test_registry.py
  - tests/test_resolve.py
  - tests/test_run.py
  - tests/test_session.py
  - tests/test_shell_scripts_path.py
  - tests/test_tool_onboarding_skill.py
  - tests/test_version_status.py
  - tests/test_wizard_app.py
  - tests/test_xcode_clt_entry.py
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
  necessity: 1
status: issues_found
---

# Phase 32: Code Review Report

**Reviewed:** 2026-11-21
**Depth:** deep
**Files Reviewed:** 45
**Status:** issues_found

## Summary

I reviewed the phase 32 diff (`7f00c98b..HEAD`) against 32-CONTEXT, 32-SPEC, the eleven plans and
summaries, and 32-REVIEWS. I did not reopen the decisions and accepted limits listed in the brief
(32 D-01, D-03, D-04, D-08 to D-15, the OpenCode v1/v2 shape rule, Bruno UNPROVEN with the default
smoke, the shared landing-image cleanup race, a running Claude rewriting its config after the
retry-once write, `CLAUDE_CONFIG_DIR` not honored, an absolute `COPILOT_HOME` not listed). I found no
defect that corrupts a user's agent config in normal use, so there are no critical findings. I found
five warnings and six info items. I reproduced every warning with a one-off read-only script in a
scratch `HOME` under `/tmp/claude-1000/p32rev` (removed afterwards); I ran no make target,
container, real install or host-mutating command. The targeted test files for the phase pass
(`uv run pytest ... --no-cov`).

The following held up under adversarial reading and round-trip probes (apply then revert,
byte-for-byte against the seed):

- **Three-level insert and `created_levels` provenance:** OpenCode with an absent `mcp`, a
  pre-existing empty `mcp: {}`, a pre-existing `mcp.servers: {}`, `mcp.servers` holding other
  servers, a JSONC file with leading and trailing comments, and a user sibling or comment added to
  the created parent. Each reverts to the seed, or keeps exactly the user's addition and removes
  only our leaf (`agent_settings.py:304-335`, `1263-1287`).
- **In-snapshot presence gate:** the gate runs on the same parsed snapshot that
  `write_if_unchanged` later guards (`agent_settings.py:1011-1013`, `1045-1049`), so the retry
  re-reads it. A forged entry cannot cross between the MCP file and the ordinary settings file
  (`_agent_files`, `agent_settings.py:1415-1431`).
- **Codex TOML apply and revert:** an absent file, a file with comments and tables, and the
  `args`-before-`command` order after the header all revert byte-identically.
- **Consent binding:** every production caller of `register_hooks` other than
  `session._register_hook_step` passes no `confirmed_hosts`, so the install, update and resync
  routes can never write the `claude` consent host (`engine.py:351`, `update.py:570`,
  `session.py:479`).
- **AWS vendor script facts:** I fetched `https://awscli.amazonaws.com/v2/install.sh` and confirmed
  `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION`, `gpg not found` (exit 1), the `unzip` requirement
  on Linux and `aws update` are all real.

I read `necessity-review.md` and assessed necessity: one info item.

## Warnings

### WR-01: `run_command` now starts every child in a new session, so Ctrl+C orphans the install

**File:** `installer/run.py:78-89`
**Issue:** `run_command` is the default runner of the console route (`engine.py:165`,
`app.py:126`) and runs every install, update and removal command there. The phase changed it to
`subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, start_new_session=True)`. Stdin closing
is what review H1 asked for. `start_new_session=True` goes further: the child leaves the terminal's
foreground process group, so Ctrl+C reaches only the installer. `subprocess.run` then kills only the
direct child (the docstring says so), never its descendants. Every script install is
`sh -c 'curl ... && bash < "$f"'` (`executors.py:497-502`), and brew, bun and the AWS installer fork
further. After Ctrl+C the real installer keeps running unattended and finishes or half-finishes the
install the user cancelled. Reproduced: a child `run_command(['sh','-c','(sleep 3; touch M) & wait'])`
interrupted with SIGINT after one second exited with `KeyboardInterrupt`, and the marker file `M`
was still created three seconds later. The detached session also removes the controlling terminal,
so a `sudo` that a Homebrew cask runs internally cannot prompt on `/dev/tty` and fails; I did not run
that case, so treat it as a risk, not a proof. The TUI route already used a new session on purpose
(`run_output_with_stderr`, `run.py:106-125`, "Textual holds the terminal"); the console route had no
such reason, and nothing in the SPEC or the plans asks for a detached session on it.
**Fix:** Keep `stdin=subprocess.DEVNULL` (the H1 requirement) and drop `start_new_session=True` from
`run_command`, so Ctrl+C reaches the whole foreground group again. If a detached session is wanted
after all, use `start_new_session=True` together with a handler that kills the child's process
group (`os.killpg(proc.pid, SIGTERM)` in an `except KeyboardInterrupt`) and add a test that a
grandchild does not survive an interrupt.

### WR-02: A hand-edited ledger crashes the removal run with an uncaught exception after the package is gone

**File:** `installer/agent_settings.py:801-806`, `1259-1261`, `1415-1431`; callers `installer/app.py:1166`, `1367`
**Issue:** The code states the ledger is user-writable JSON and builds an allow-list for that reason
(`_eligible`, `agent_settings.py:1328-1351`). Two paths still raise instead of refusing:

1. `_agent_files` calls `mcp_file(agent, ...)` whenever `setting == "mcp-playwright"`, and `mcp_file`
   raises `ValueError("unknown MCP agent")` for any agent outside `MCP_AGENTS`. `revert_agent` walks
   every setting in the ledger, so a `vscode` or `herdr` ledger holding one `mcp-playwright` entry
   makes `revert_agent("vscode", ...)` raise. Reproduced: `ValueError unknown MCP agent: 'vscode'`.
   The preview already guards this (`_previewable`, `agent_settings.py:1651-1652`); the revert does not.
2. A forged entry with `replaced_default: true` on an allow-listed dynamic key reaches
   `replace_value(text, fmt, entry.key_path, key.cli_default)` with `cli_default == ABSENT`, and
   `_dump(ABSENT)` raises `TypeError: Object of type _Absent is not JSON serializable`. Reproduced
   with a claude `mcp-playwright` entry. The `except` in `_revert_once` (`agent_settings.py:1392`)
   catches only `SettingsParseError`, `SettingsEditRefused` and `OSError`. The herdr
   `default-shell` key had the same latent hole; phase 32 widens it to five more hosts.

Both removal routes call `_after_removal` with no `try` around it (`app.py:1166`, `1367`), after the
package is already removed. The run then ends in a traceback, skips the remaining sweeps (shell init,
terminal keys, schedules) and the remaining tools of the batch, and leaves the receipt and ledger
out of step.
**Fix:** Make `_agent_files` return `()` for an agent not in `MCP_AGENTS` when `setting == MCP_SETTING`
(the refusal then flows through `NOT_A_SETTINGS_FILE`), and in `_eligible` drop an entry whose
`replaced_default` is true when `table[key_path].cli_default is ABSENT`. Add a ledger-forgery test
for each shape next to `test_a_forged_ledger_entry_cannot_cross_between_the_mcp_and_the_ordinary_file`
(`tests/test_agent_settings.py:2772`).

### WR-03: The Codex ownership unit strands a command-less server table when the user adds a key

**File:** `installer/agent_settings.py:1220-1239`; the behavior is asserted at `tests/test_agent_settings.py:2457-2467`
**Issue:** `held_states` decides the revert per ledger key, then forces the three recorded Codex keys
(`command`, `args`, `env`) to "kept" only when one of them was edited or deleted. A user who adds a
sibling key to the installer-written table (for example `startup_timeout_sec = 30`, or
`tool_timeout_sec`) leaves all three recorded keys intact, so the unit reads "all held" and the
revert removes `command` and `args`. Reproduced:

```
model = "o3"

[mcp_servers.playwright]
startup_timeout_sec = 30
```

is what `revert_mcp` leaves. A Codex server table with no `command` or `url` has no transport; as far
as I know Codex rejects it at config load, but I could not run Codex here, so that part is unverified.
Independently of Codex's behavior, the stated rule (review H6: "keep the whole server and report it")
is not honored for this edit: the user-edited server is half-removed, and the test pins that outcome
(`== {"startup_timeout_sec": 30}`) instead of the H6 rule.
**Fix:** Treat the table as one unit by its whole content. In `held_states`, when the group is "all
held", also compare `lookup(doc, prefix)` with the dict rebuilt from the recorded keys; if the table
holds any other key, mark every key of the unit `False` (kept, reported as changed). Update the
`added` case of `test_a_codex_server_is_one_ownership_unit_on_revert` to expect the whole server kept.

### WR-04: A `rereads` hook silently re-adds a registration the user deleted, on update, resync or install, with no confirmation

**File:** `installer/postinstall.py:861`; `installer/update.py:570`; `installer/session.py:479`; `installer/version_status.py:908`
**Issue:** For a `rereads` hook (`playwright-mcp-register`) `register_hooks` ignores the receipt:
`recorded = frozenset[str]() if pair.rereads ...`, so `wanted` is every present host. The three
non-consent callers (the install in `engine.py:351`, the update in `update.py:570` with
`hosts=None`, and the host-install resync in `session.py:479`) call it with no confirmation, and the
non-consent hosts (Codex, OpenCode, Cursor, Copilot) are written straight away. A user who removed
the `playwright` server from `~/.codex/config.toml` on purpose finds it back after the next
`update playwright-mcp`, after installing any other agent host, or after any reinstall. This is the
opposite of the rule the settings ledger applies elsewhere ("a recorded key the user deleted is
their choice", `apply_setting(skip_recorded=...)`, `agent_settings.py:1090-1095`). Plan 32-11 chose
"a recorded host whose server entry is gone reads pending again" for the Reconfigure drift row,
where the user confirms the step; it did not decide that the unattended routes may write it again.
Reproduced at the hook level: `register` wrote the Codex server, the config was emptied, and a
second `register` wrote it again.
**Fix:** Keep the receipt rule for the unattended callers and use the settled read only for the
Reconfigure drift row. For example, give `register_hooks` a `reoffer: bool` that is true only from
`_register_hook_step` (the confirmed step), and subtract `receipt.hooks[name]` otherwise even for a
`rereads` hook. Add a test that an update after a user delete leaves the file empty.

### WR-05: A `~/.claude.json` the writer creates is world-readable (mode 0644)

**File:** `installer/agent_settings.py:572-579`; `installer/atomic.py:36-52`
**Issue:** `write_if_unchanged(path, None, text)` calls `atomic_write_text(target, text, mode=None)`,
and for a new file `atomic_write_bytes` "keeps whatever umask produced". When `~/.claude.json` does not
exist yet (Claude installed, never started; a realistic state right after the install this
installer runs), the MCP writer creates it. Reproduced: under umask 022 the created file is `0o644`.
`~/.claude.json` is Claude's own state file (account metadata, per-project history, MCP server
env values), which Claude itself creates owner-only as far as I know; if Claude later rewrites it in
place, it keeps the permissive mode we gave it. The same path also writes `mcp.json`, `mcp-config.json`
and `config.toml`, whose server entries carry `env` values.
**Fix:** In `write_if_unchanged`, pass `mode=0o600` when `before is None` (a new file) for the MCP
files, or for every file the ledger creates, and add a test that a created `~/.claude.json` is
`0o600` under umask 022.

## Info

### IN-01: `_refused_token` matches the last path segment of any token, including URL tails

**File:** `installer/model.py:562-572`
**Issue:** The check strips everything up to the last `/` of every token and compares it with the
elevation, shell, launcher and never-run sets, in any argv position. Reproduced: `["gh","extension",
"install","owner/time"]` and `["gh","extension","install","https://github.com/o/env"]` are refused as
`'time'` and `'env'` launchers. A future `gh extension install owner/env` row, or an `update` argv
naming a package `time` or `command`, fails `load_tools`, which stops the whole catalog at start-up.
The reviewed rule was "a refused head", not a refused word anywhere.
**Fix:** Apply the basename test to `argv[0]` only for the shell, launcher and never-run sets, and
keep the "any position" scan for `ELEVATION_COMMANDS` alone (or skip tokens that contain `://` or
`:`).

### IN-02: `HANDOFF_NAMES` duplicates the keys of `_HANDOFF_COMMANDS` with no parity test

**File:** `installer/model.py:25-26`; `installer/executors.py:740-745`, `778`
**Issue:** The closed set is duplicated "not imported" to keep `model.py` free of the executor
module, as `POSTINSTALL_HOOK_NAMES` is, but that set has a parity test
(`tests/test_post_install.py:192`) and this one does not (`rg HANDOFF_NAMES tests` finds nothing).
A name added to `HANDOFF_NAMES` but not to the table makes `needs_manual` raise `KeyError`
(`executors.py:778`) while the plan is built, and nothing catches it there.
**Fix:** Add a one-line test asserting `HANDOFF_NAMES == set(executors._HANDOFF_COMMANDS)` the way
the existing parity tests reach private names.

### IN-03: Tautological assertions in the phase consistency test

**File:** `tests/test_phase32_consistency.py:16-18`, `85-86`, `106-107`
**Issue:** `VERIFIED_MODE`, `VERIFIED_ARCH`, `EXPECTED_SMOKE_ARGV` and `EXPECTED_ARCH` are module
constants set to `"none"` or `None`, and the tests assert `VERIFIED_MODE == "none"`,
`EXPECTED_SMOKE_ARGV is None` and so on. These pass whatever the registry says; they read like
guards but check nothing. The real checks beside them (no `smoke_argv` on the Bruno methods, the
comment paragraph) are fine.
**Fix:** Delete the four constants and their asserts, or replace them with the shipped-entry
assertions that already follow them.

### IN-04: Stale or dangling comments and docs

**File:** `installer/registry.toml:3580`, `3627`; `scripts/container-e2e-verify.sh:347-348`; `installer/agent_settings.py:293-294`; `.claude/skills/tool-onboarding/SKILL.md:123`
**Issue:**
- `registry.toml:3580` cites "follow-up 999.32" for the Bruno desktop entry; no `Phase 999.32` exists
  in `.planning/ROADMAP.md` (the roadmap stops at 999.31).
- `registry.toml:3627` says the exact-pin update refusal is "assumed ... container confirmation
  pending", while the same block records `TRACER_PLAYWRIGHT_INSTALL_OK: ... manifest records exact
  range 0.0.85`.
- `container-e2e-verify.sh:347-348` has two garbled, overlapping comment lines about `herdr-app`.
- `insert_key`'s docstring still says "a two-part key"; it now takes three.
- The SKILL.md `script` row says elevation heads and placeholders are refused; the validator now also
  refuses shells, launchers, `xcode-select` and `softwareupdate` (`model.py:562-572`).
**Fix:** Add the 999.32 backlog entry or reword to "backlog item to be filed"; drop "container
confirmation pending"; rewrite the two script comment lines; update the docstring and the SKILL row.

### IN-05: Duplicated pin extraction and a repeated no-op note for pi in the Playwright hook

**File:** `installer/postinstall.py:571-582`, `585-593`, `605`
**Issue:** `_playwright_command` and `_playwright_register` each re-extract
`method.params["versions"]["@playwright/mcp"]` with the same cast and check, so the "no pinned
version" path exists twice, and the second copy of the check in `_playwright_register` is
unreachable in effect (`_playwright_command` returns `None` first for the same condition, so the
earlier, more specific warning is the only one that can show). `_playwright_supported` excludes `pi`
from the drift row, but `register_hooks` still hands `pi` to the hook whenever `pi` is present, so
every install, update and resync adds the note "pi: not written ..." to the warning line.
**Fix:** Read the pin once in `_playwright_register` and pass it to a `_playwright_command(pin)`; drop
`pi` from `wanted` in the hook or emit its note only from the drift row.

### IN-06: Single-instantiation generality (necessity) and an unchecked ledger field

**File:** `installer/agent_settings.py:1220`; `installer/receipts.py:338-361`
**Category:** necessity
**Issue:** `UNIT_PREFIXES` is a frozenset with exactly one member, `("mcp_servers", "playwright")`,
and `held_states` loops over it. Only the Codex server writes more than one key per server
(`_MCP_PATHS`, `agent_settings.py:735-741`: every other host records one key), so the set has one
instantiation for its whole lifetime. This rests on judgment (a second multi-key host could appear),
hence Info. Separately, `_config_write_from` accepts any list of strings for `created_levels`
without relating it to `key_path` (`receipts.py:338-361`); the revert's re-parse guard keeps a bad
value harmless (`agent_settings.py:1268`), but the field is documented as the provenance of a
three-part insert and is not validated as one.
**Fix:** Inline the Codex prefix as a constant until a second unit exists, or keep the set and note
the single use; reject a `created_levels` longer than `len(key_path) - 1` when the ledger is read.

---

_Reviewed: 2026-11-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

---

## Orchestrator triage (2026-11-21)

Sources: this report (gsd-code-reviewer, deep), the external lane `opencode-referee-one` (4 findings, one pass, 11:27 to 11:32), and the security audit (`32-SECURITY.md`: SECURED 32/32). Every item below was checked by the orchestrator against the cited code before it was decided. Decisions marked provisional go on the owner's confirmation list.

| Item | Source | Decision |
|---|---|---|
| WR-01 | reviewer, lane #3 | FIX: kill the child's whole process group on interruption (keep the new session and closed stdin). The loss of the controlling terminal for a cask's internal `sudo` on the console route stays, provisional: the TUI routes already behave this way and the project rule is zero sudo with a hand-off. |
| WR-02 | reviewer | FIX: a hand-edited ledger must never crash the removal sweep: skip and report the entry (`ValueError`, `TypeError`). |
| WR-03 | reviewer, lane #1 | FIX: the Codex unit is held only when the table holds exactly the recorded keys; a key the user added keeps the WHOLE server and reports `kept_changed` (review H6's rule). Supersedes plan 32-04's sub-cases (d) and (e); provisional. |
| WR-04 | reviewer | FIX: `rereads` ignores the receipt only on the confirmed Reconfigure step and in the drift report; install, update, host-install resync and reinstall honor the receipt, so a server the user deleted on purpose is not silently re-added (28 D-06 precedent). Provisional. |
| WR-05 | reviewer | FIX: files the MCP writer creates get mode 0600. |
| Lane #2 | lane | FIX (checked: `postinstall.py:608-623,653-693`): with the official Claude plugin enabled, a Flatpak Chrome path and no env key, Claude is not settled and the hand-off is not suppressed because a server entry exists. |
| Lane #4 | lane | DEFER, accepted limit (backlog 999.32): `gh extension` data under a relocated GitHub CLI data directory is not detected; the registry comment already states the default path. |
| IN-01 | reviewer | DEFER, accepted: a basename match refuses `owner/time` style tokens (a false positive that fails closed; no shipped row is affected). |
| IN-02 | reviewer | FIX: parity test between `HANDOFF_NAMES` and `_HANDOFF_COMMANDS`. |
| IN-03 | reviewer | FIX: the Bruno guards assert the registry, not their own constants. |
| IN-04 | reviewer | FIX: stale text, the garbled script comments, the `insert_key` docstring, the SKILL row; backlog 999.32 is recorded in ROADMAP by the orchestrator. |
| IN-05 | reviewer | FIX: one pin extraction in the Playwright hook; the `pi` note only when pi is a wanted host. |
| IN-06 | reviewer | DEFER (judgment note); `created_levels` longer than `len(key_path) - 1` is rejected when the ledger is read (small, include with WR-02). |
