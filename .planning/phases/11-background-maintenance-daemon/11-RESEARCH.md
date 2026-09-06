# Phase 11: Background Maintenance Daemon - Research

**Researched:** 2026-09-06
**Domain:** macOS `launchd` LaunchAgent scheduling, wrapped around an existing shell script, exposed through this project's `Policy` abstraction
**Confidence:** HIGH (every plist key, `launchctl` subcommand, and PATH-environment claim below was executed live on this machine and its real output is quoted; the two architectural gaps — hard-block toggle vs. soft `requires`, and "on by default" — are HIGH confidence because they are read verbatim from this repo's own source and tests, not inferred)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Default state — on, not opt-in:** The policy is ON by default on a fresh macOS install (not opt-in) — the user explicitly chose this over the initially-recommended opt-in default. Amended into ROADMAP.md's Phase 11 success criteria (2026-09-04).

**D-02 — Schedule configurability — time-of-day only, recurrence stays fixed:** The policy's detail panel gains a time-of-day picker controlling the LaunchAgent's `StartCalendarInterval` hour/minute. Recurrence itself (daily) is NOT made configurable this phase — no weekly/custom-interval selector.

**D-03 — Log truncation limit:** No specific size/day limit requested — planner picks a reasonable default (e.g. a few hundred KB or last-N-runs / last-30-days), consistent with how this codebase handles other log-like files. Not a locked number, just "simple size/age truncation" per the existing requirement text.

### Claude's Discretion
- Exact log truncation threshold (D-03) — planner's call, no user-specified number.
- Exact UI control shape for the time-of-day picker (e.g. a text-entry `HH:MM` field vs. a spinner) — planner's call, consistent with existing Policies detail-panel input patterns.
- Whether the time-of-day setting is stored in the LaunchAgent plist itself (regenerated on change) or in this project's own managed-state config and pushed into the plist at apply time — implementation detail, planner's call.

### Deferred Ideas (OUT OF SCOPE)
- Full recurrence control (weekly/custom interval, not just daily) — deferred; the user picked the narrower time-of-day-only option for this phase. Could be revisited later if daily-only proves too rigid in practice.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-launchd-prune-policy | New `daemon_policy` factory (parallel to `ban_policy`/`tweak_policy`) installs/removes a macOS-only LaunchAgent running `scripts/prune-user-tmpdir.sh --apply` daily via `StartCalendarInterval`, `--days` defaulting to 3, no changes to the script's own logic. | Live-verified plist schema (Architecture Patterns → "The plist template"), live-verified `launchctl bootstrap`/`bootout` invocations, `daemon_policy` factory shape mirroring `ban_policy`/`tweak_policy` (Architecture Patterns → "Mirroring the Policy factory pattern"), on-by-default bootstrap mechanism (Common Pitfalls → Pitfall 2). |
| REQ-daemon-log-diagnostics | Scheduled runs write to a single append-mode log file under the managed-state directory convention, capped by simple size/age truncation; Policies detail panel gets a "last run" line plus a keybinding to view the log — no new top-level Diagnostics view. | Log location recommendation (Architecture Patterns → "Log file location and truncation"), wrapper-script design reusing the `ManagedExecutable`/`helper_assets` precedent, detail-panel toggle keybinding recommendation (no new modal/view). |
| REQ-daemon-dependency-gating | `fd`/`rg` declared as `requires` (matching the `docker` tweak's `watch` pattern) but `apply` never refuses to run when missing — degrades to the script's own find/grep fallback, surfaced via the existing `missing_requires` UI with no new mechanism. | **Critical finding, Common Pitfall 1**: the "docker tweak's `watch` pattern" the requirement names as the template is a *hard* block in the current codebase (`test_policy_missing_required_tool_blocks_enable` proves it), directly contradicting "apply never refuses to run." A concrete resolution (new `Policy.hard_requires: bool = True` field) is proposed. |
</phase_requirements>

## Summary

This phase adds nothing to `pyproject.toml` — it is pure stdlib (`plistlib`, `os.getuid()`, `pathlib`) plus the macOS system `launchctl` binary, composed through this project's existing `Policy`/`PolicyResult`/`PolicyLayer` triad and the `installer.run.Runner`/`CommandError` seam already used everywhere else. The plist schema, the exact `launchctl` subcommands, and the minimal-PATH environment problem below were all confirmed by running real commands on this machine (macOS 15.7.9, `launchctl` "Darwin Bootstrapper Version 7.0.0") rather than from training-data memory, per this project's explicit instruction — training-data claims about `launchd` are a known stale-fact trap (key names and subcommands have shifted across macOS releases).

Two things in this research change what the planner must build beyond a literal reading of the three requirements. First, `REQ-daemon-dependency-gating` asks for `fd`/`rg` to be soft (never blocking) while explicitly citing the `docker`/`watch` `requires` pattern as the template — but that exact pattern is hard-blocking in this codebase today, proven by a real, passing test (`test_policy_missing_required_tool_blocks_enable`) that asserts `policy.apply` is never even called when `missing_requires` is non-empty. Reusing `Policy.requires`/`missing_requires` verbatim, with no other change, would make the daemon impossible to re-enable from the TUI once `fd`/`rg` are absent, contradicting the requirement's own second half. The fix is a small, additive field on `Policy` (`hard_requires: bool = True`), defaulting to preserve every existing policy's behavior unchanged, with `daemon_policy` alone passing `hard_requires=False` and `action_toggle_policy`'s gate checking that flag. Second, "ON by default on a fresh macOS install" (D-01) is a genuinely new shape for this codebase: every existing `Policy.active` is computed by reading live filesystem state (a shim file, an rc block, a plugins-owned record) — none of them are proactively applied without the user pressing space. Making the daemon self-apply on a machine that has never been asked requires a persisted "has this ever been decided" marker, distinct from "is it currently active" (plist presence) — the omz-plugins ownership-record pattern (`installer/omz.py`'s `_record`/`state_path`, reusing `installer.shellrc.apply_block`/`strip_block`) is the direct precedent to copy, not invent.

**Primary recommendation:** Build a new `installer/daemon.py` module (parallel to `installer/omz.py`) holding the plist-generation, `launchctl` invocation, and log-wrapper logic as pure-enough functions; wire it into `installer/policy.py` as a new `daemon_policy` factory that composes those functions exactly the way `omz_plugins_policy` composes `installer/omz.py`, gated into `setup.py`'s policy list only when `platform.os == "macos"`.

## Architectural Responsibility Map

This project is a local CLI/TUI installer, not a web app — the prescribed browser/frontend-server/API/CDN/database tiers do not apply. The table below uses this codebase's own real architectural layers instead (Textual presentation, pure policy composition, the OS-integration/IO boundary, and on-disk state), which is the load-bearing distinction `installer/policy.py`'s own module docstring already draws ("The pure layer owns the composition ... the IO boundary (setup.py) binds the real...paths").

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| LaunchAgent registration/deregistration (`launchctl bootstrap`/`bootout`) | OS Integration (new `installer/daemon.py`) | Filesystem state (`~/Library/LaunchAgents/*.plist`) | Mirrors `installer/guards.py` owning shim-file IO for `ban_policy`. |
| `Policy` toggle + on-by-default bootstrap | Policy composition (`installer/policy.py`'s `daemon_policy`) | Presentation (`setup.py` wiring decides *when* to auto-apply) | `Policy.apply`/`.remove` are pure closures; `setup.py` is the only place with "is this the first run" context. |
| Time-of-day picker | Presentation (`wizard_app.py` `PoliciesScreen`, a new modal) | Policy composition (validates HH:MM, regenerates the plist) | No existing text-entry widget in this codebase to reuse — a new small modal, closest existing precedent `NavScreen` (`ModalScreen[str \| None]` + `ListView`). |
| Log write + truncation | OS Integration (a new managed wrapper executable, not the prune script itself) | Presentation (renders the "last run" line by reading the log) | `scripts/prune-user-tmpdir.sh` must not change; truncation has to live in a wrapper the plist invokes instead of the script. |
| `fd`/`rg` soft-dependency surfacing | Policy composition (`Policy.requires`/`missing_requires`, extended with `hard_requires`) | Presentation (`PoliciesScreen._requires_cell`/`_policy_detail`, unchanged rendering) | Requirement asks for the existing rendering with different *gating* semantics — a data-model change, not a UI change. |

## Package Legitimacy Audit

Not applicable — this phase installs zero third-party packages. It uses only: Python stdlib (`plistlib`, `pathlib`, `os`), the macOS system `/bin/launchctl` binary (already present on every macOS install, not installed by this project), and this project's own `scripts/prune-user-tmpdir.sh` (unchanged). No `npm view`/`pip index versions`/`cargo search` check applies.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `plistlib` (stdlib) | Python 3.14 stdlib (bundled, no pin needed) | Generate/parse the LaunchAgent `.plist` XML | `[VERIFIED: local shell]` — round-tripped a real dict through `plistlib.dumps`/`plistlib.loads` on this machine and it produced byte-for-byte the same DOCTYPE/header/key ordering convention seen in this machine's real `~/Library/LaunchAgents/*.plist` files. Hand-rolling the XML string (as this codebase does for shell snippets in `installer/tweaks.py`) risks malformed/unescaped XML if any path contains a special character; `plistlib` escapes correctly by construction. |
| `os.getuid()` (stdlib) | n/a | Build the `gui/<uid>` `launchctl` domain target | `[VERIFIED: local shell]` — `id -u` returned `501` on this machine; `launchctl print gui/501/...` succeeded using that exact value. |
| `installer.run.run_captured`/`CommandError` | already in repo (`installer/run.py`) | Invoke `launchctl bootstrap`/`bootout` without letting a spawned child corrupt the Textual-owned terminal | `[VERIFIED: installer/run.py:64-71]` — quoted: `"""Runner that keeps the child's stdio out of the caller's terminal. For side effects started while Textual owns the terminal..."""` — this is exactly the daemon apply/remove context (invoked from inside `PoliciesScreen.action_toggle_policy` via `run_live`). |
| `installer.shellrc.apply_block`/`strip_block` | already in repo (`installer/shellrc.py:66-99`) | Persist the "has the user ever decided" marker and the chosen HH:MM, as a marker block in a small state file | `[VERIFIED: installer/shellrc.py:66-99]` — generic `content: str -> str` functions, not rc-file-specific; already reused by `installer/omz.py` against a *different* file (`_MYSHELLRC` passed as `state_path`) for exactly this "ownership record" purpose. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `/bin/launchctl` (macOS system binary) | Whatever ships with the target macOS (this machine: "Darwin Bootstrapper Version 7.0.0") | Load/unload the LaunchAgent into the running `launchd` session immediately (writing the plist file alone only take effect at next login) | `[VERIFIED: local shell]` — `launchctl version` output captured live. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `plistlib` | Hand-rolled XML string (this codebase's existing `_DOCKER_BODY`-style raw-string convention) | Rejected: shell-snippet string templating is fine because there is no untrusted/variable-length content inside those bodies beyond a fixed placeholder; a plist embeds a real filesystem path (`TMP_ROOT`, `HOME`) that could contain XML-special characters on some machines. `plistlib` is one import, already in stdlib, and was live round-tripped above. |
| `launchctl bootstrap`/`bootout` | `launchctl load`/`unload` | Rejected: `man launchctl` on this machine literally lists `load \| unload` with the line `"Recommended alternative subcommands: bootstrap \| bootout \| enable \| disable"` directly under it — `load`/`unload` still work but are explicitly the deprecated path on this exact target OS. |
| A new `~/Library/Application Support/tools-installer/` state directory | Reuse `~/.myshellrc` as the state file (like `omz_plugins_policy` does) | Recommended: `~/.myshellrc` is already this project's de facto small persistent marker ledger (ban aliases, tweak blocks, omz ownership record all live there); a fourth marker-block type there is more consistent than a brand-new directory whose lifecycle (created when? cleaned up on uninstall?) would need its own decisions. |

**Installation:** None — nothing to install for this phase; every dependency above is either Python stdlib or a macOS system binary already present.

**Version verification:** N/A — no versioned third-party package is added by this phase.

## Architecture Patterns

### System Architecture Diagram

```
 PoliciesScreen (wizard_app.py)                    setup.py composition root
 ───────────────────────────────                    ────────────────────────
        │  space = toggle                                    │
        │  new: "t" = open time picker                       │  builds PolicyInputs(
        │  new: "l" = toggle log view in detail panel         │    policies=[..., daemon_policy(...)]  # only if
        ▼                                                     │    platform.os == "macos"
 action_toggle_policy()                                       │  )
        │  reads policy.hard_requires (NEW field)             │
        │  only blocks when hard_requires AND missing_requires │  first-run bootstrap check:
        ▼                                                      │    if platform macos and daemon not yet
 policy.apply() / policy.remove()  ◄────────────────────────────    "decided" -> policy.apply() once, eagerly
        │  (closures built by daemon_policy() in policy.py)
        ▼
 installer/daemon.py  (NEW — parallel to installer/omz.py)
   ├─ render_plist(hour, minute, days, log_path, uid) -> bytes      [plistlib.dumps]
   ├─ write_plist(plist_path, ...) -> None                          [Path.write_text/write_bytes]
   ├─ bootstrap(uid, plist_path) -> None   (best-effort bootout, then real bootstrap)
   ├─ bootout(uid, label) -> None          (best-effort; ignore "not loaded" errors)
   ├─ install_wrapper(bin_dir) -> Path     (copies helper_assets/prune_daemon_runner.py,
   │                                        mirrors tweaks.install_tweak_executables)
   ├─ last_run_summary(log_path) -> str | None   (parses the wrapper's own timestamp header)
   └─ read_schedule(plist_path) -> tuple[int,int] | None  (plistlib.loads, live read-back)
        │
        ▼
 ~/Library/LaunchAgents/com.tools-installer.prune-tmpdir.plist   (launchd reads this at every login)
        │  ProgramArguments -> the installed wrapper (NOT scripts/prune-user-tmpdir.sh directly)
        ▼
 ~/.local/bin/tools-installer-prune-daemon  (NEW wrapper, `ManagedExecutable`-style)
        │  1. runs scripts/prune-user-tmpdir.sh --apply --days N  (UNCHANGED script)
        │  2. appends timestamped output to the log
        │  3. truncates the log if it exceeds the size cap
        ▼
 ~/Library/Logs/tools-installer/prune-daemon.log   (single append-mode file, read by "last run" + "l" view)
```

### Mirroring the Policy factory pattern

`daemon_policy` follows `omz_plugins_policy`'s shape most closely (a single artifact to write/strip, plus a `state_path` ownership record; see `installer/policy.py:260-311`), not `ban_policy`'s (multi-shim) or `tweak_policy`'s (rc-block). Concretely:

```python
# Source: installer/policy.py:260-311 (omz_plugins_policy), the direct template
def daemon_policy(
    *,
    plist_path: Path,
    log_path: Path,
    wrapper_bin_dir: Path,
    state_path: Path,          # reuse ~/.myshellrc, like omz_plugins_policy does
    installed_tools: Mapping[str, bool],   # for fd/rg missing_requires, like tweak_policy
    uid: int = os.getuid(),
) -> Policy:
    def _apply() -> PolicyResult:
        wrapper = install_wrapper(wrapper_bin_dir)          # installer/daemon.py
        hour, minute = read_saved_schedule(state_path) or (3, 0)
        write_plist(plist_path, wrapper, hour, minute, log_path=log_path)
        bootstrap(uid, plist_path)                          # bootout (best-effort) then bootstrap
        record_decided(state_path)                          # marker block: "user has an opinion now"
        ...
    def _remove() -> PolicyResult:
        bootout(uid, LABEL)                                 # best-effort
        plist_path.unlink(missing_ok=True)
        record_decided(state_path)                          # still "decided" — this was an explicit disable
        ...
    missing_requires = tuple(t for t in ("fd", "rg") if not installed_tools.get(t, False))
    return Policy(
        id="daemon:prune-tmpdir",
        ...
        active=plist_path.exists(),        # presence-based, like every other Policy — NEVER parse `launchctl print`
        requires=("fd", "rg"),
        missing_requires=missing_requires,
        hard_requires=False,               # NEW field — see Common Pitfall 1
    )
```

`active=plist_path.exists()` is a deliberate, verified choice: `man launchctl` on this machine states of `print` — quoted verbatim — `"IMPORTANT: This output is NOT API in any sense at all. Do NOT rely on the structure or information emitted for ANY reason. It may change from release to release without warning."` Every existing `Policy.active` in this codebase (`guard_status(...).values()`, `tweak_present(...)`, `plugins_owned(...)`) already reads a filesystem artifact, never a live process/registration query — plist-file presence is the correct, consistent choice, and avoids depending on explicitly-disclaimed non-API output.

### The plist template (live-verified on this machine)

Confirmed against `man launchd.plist` on this machine plus a real round-trip through `plistlib` and a real `launchctl bootstrap`/`print`/`bootout` cycle (see command transcript below). Real keys observed on this machine's own `~/Library/LaunchAgents/*.plist` files: `Label`, `ProgramArguments`, `StandardOutPath`, `StandardErrorPath`, `RunAtLoad`, `StartInterval`, `LimitLoadToSessionType`, `Disabled` (JetBrains Toolbox, GoogleUpdater, VirtualBox plists, read verbatim on this machine — none of the five pre-existing plists on this machine happen to use `StartCalendarInterval`, so that key's exact sub-key shape (`Hour`/`Minute`) was confirmed instead via `man launchd.plist`, quoted verbatim below, then round-tripped through `plistlib` and validated with a real `launchctl bootstrap`).

```
$ man launchd.plist   (quoted verbatim)
     StartCalendarInterval <dictionary of integers or array of dictionaries of integers>
     This optional key causes the job to be started every calendar interval as
     ...
	   Minute <integer>   The minute (0-59) on which this job will be run.
	   Hour <integer>     The hour (0-23) on which this job will be run.
```

```python
# Source: this session's own plistlib round-trip, run live on this machine
import plistlib
data = {
    "Label": "com.tools-installer.prune-tmpdir",
    "ProgramArguments": [str(wrapper_path), "--apply", "--days", "3"],
    "StartCalendarInterval": {"Hour": hour, "Minute": minute},
    "StandardOutPath": str(log_path),
    "StandardErrorPath": str(log_path),
    "RunAtLoad": False,
    "EnvironmentVariables": {"PATH": daemon_path_value},   # see Pitfall below — REQUIRED for fd/rg to be found
}
plist_path.write_bytes(plistlib.dumps(data))
```

Real output of `plistlib.dumps(data)` on this machine (elided to the load-bearing keys — full transcript was produced and asserted `plistlib.loads(plistlib.dumps(data)) == data`, i.e. a verified round trip):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>com.tools-installer.prune-tmpdir</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/bash</string>
		<string>/path/to/prune-user-tmpdir.sh</string>
		<string>--apply</string>
		<string>--days</string>
		<string>3</string>
	</array>
	<key>RunAtLoad</key>
	<false/>
	<key>StandardErrorPath</key>
	<string>/tmp/test.log</string>
	<key>StandardOutPath</key>
	<string>/tmp/test.log</string>
	<key>StartCalendarInterval</key>
	<dict>
		<key>Hour</key>
		<integer>3</integer>
		<key>Minute</key>
		<integer>30</integer>
	</dict>
</dict>
</plist>
```

This exact plist (adapted to a harmless `/bin/echo` program) was then live-bootstrapped and printed on this machine:

```
$ launchctl bootstrap gui/501 <tmpfile>.plist   → exit 0
$ launchctl print gui/501/com.tools-installer.test
gui/501/com.tools-installer.test = {
	active count = 0
	path = <tmpfile>.plist
	type = LaunchAgent
	state = not running
	program = /bin/echo
	arguments = { /bin/echo  hello }
	stdout path = /tmp/tools-installer-test.log
	stderr path = /tmp/tools-installer-test.log
	...
	default environment = { PATH => /usr/bin:/bin:/usr/sbin:/sbin }
}
$ launchctl bootout gui/501/com.tools-installer.test   → exit 0
$ launchctl print gui/501/com.tools-installer.test
Bad request.
Could not find service "com.tools-installer.test" in domain for user gui: 501
```

**Real, live location precedent** (this machine's actual `~/Library/LaunchAgents/`, five files, all read verbatim this session): `com.google.GoogleUpdater.wake.plist`, `com.google.keystone.agent.plist`, `com.google.keystone.xpcservice.plist`, `com.jetbrains.toolbox.plist`, `org.virtualbox.vboxwebsrv.plist` — confirming both the directory (`~/Library/LaunchAgents/`) and the `<reverse-dns>.<name>` label convention (recommend: `com.tools-installer.prune-tmpdir`, matching this project's `pyproject.toml` `name = "tools-installer"` `[VERIFIED: pyproject.toml:2]`, quoted: `name = "tools-installer"`).

### The exact `launchctl` invocation sequence

`man launchctl` on this machine, quoted verbatim:

```
     load | unload [-wF] [-S sessiontype] [-D searchpath] paths ...
	      Recommended alternative subcommands: bootstrap | bootout |
	      enable | disable
```

and:

```
     domain-target is gui/501/, service-name is com.apple.example, and
     service-target is gui/501/com.apple.example.
```

**Apply (install or reschedule):**
1. Write/overwrite `~/Library/LaunchAgents/com.tools-installer.prune-tmpdir.plist`.
2. `launchctl bootout gui/<uid>/com.tools-installer.prune-tmpdir` — **best-effort, swallow the error**. Live-verified: re-bootstrapping an already-loaded label fails (`Bootstrap failed: 5: Input/output error`), and this generic exit code 5 is reused for "not currently loaded" too (verified: a `bootout` on an already-booted-out label also returns exit 5 with a different message) — so status must never be inferred from this exit code; the unconditional bootout-then-bootstrap sequence is the standard idempotent pattern precisely because both directions of failure are silently tolerable.
3. `launchctl bootstrap gui/<uid> ~/Library/LaunchAgents/com.tools-installer.prune-tmpdir.plist` — real error path; a non-zero exit here should raise (via `CommandError`), surfaced as `PolicyResult.warning`.

**Remove:**
1. `launchctl bootout gui/<uid>/com.tools-installer.prune-tmpdir` — best-effort, swallow the error (may already be unloaded).
2. Delete the plist file.

Both directions were executed live end-to-end on this machine (bootstrap → print confirming registration with the exact submitted content → bootout → print confirming `"Could not find service"`), transcript above.

### Log file location and truncation

No existing convention in this codebase for a growing log file — `installer/locations.py` (read in full this session) only defines `~/.local/bin`, `~/.local/opt/<name>`, `~/Applications`, and rc-file paths; there is no `~/.local/state` or `~/.cache` precedent to extend. Since this policy is macOS-only, the mac-native convention wins over inventing an XDG-style path: this machine's own JetBrains Toolbox LaunchAgent (read verbatim this session) already points `StandardOutPath`/`StandardErrorPath` at `~/Library/Logs/JetBrains/Toolbox/launchd-stdout.log` — a real, observed precedent for exactly this use case on this exact machine.

**Recommendation:** `~/Library/Logs/tools-installer/prune-daemon.log`, single file, append-mode, both stdout and stderr merged into it (`StandardOutPath == StandardErrorPath`, which `plistlib`/`launchd` both accept without complaint — verified no schema objection in `man launchd.plist`).

**Why the prune script cannot write this file directly, and why a wrapper is needed:** `scripts/prune-user-tmpdir.sh` (read in full this session) must not change (locked in `REQUIREMENTS.md` and `11-CONTEXT.md`'s canonical refs), and `ProgramArguments` is a literal argv array with no shell — there is nowhere in that array to splice in "append, then truncate if too big." The correct shape, and the one this codebase already has a precedent for (`installer/tweaks.py`'s `ManagedExecutable`/`helper_assets/wait_time.py`, copied into `~/.local/bin` at apply-time via `install_tweak_executables`), is a small new wrapper script:

```python
# New: installer/helper_assets/prune_daemon_runner.py — copied into ~/.local/bin at apply-time,
# mirroring installer/tweaks.py's install_tweak_executables()/ManagedExecutable exactly.
# 1. subprocess.run([SCRIPT_PATH, "--apply", "--days", DAYS], capture_output=True, text=True)
# 2. append f"=== {datetime.now(UTC).isoformat()} ===\n{result.stdout}{result.stderr}\n" to the log
# 3. if log.stat().st_size > CAP_BYTES: keep only the tail (last CAP_BYTES bytes, snapped to
#    the nearest following "=== " header so a run block is never split mid-way)
```

**Recommended cap: 256 KB.** No number was locked (D-03); the prune script's own dry-run/apply output is roughly 1-2 KB per invocation (counted from the script's own `printf` lines read this session), so 256 KB holds on the order of 150-250 daily runs — many months of history — while staying trivially small to read into the Policies detail panel in full.

**"Last run" summary:** parse the log's *last* `=== <timestamp> ===` block for the prune script's own `deleted: N` line (the script always prints this verbatim on `--apply`, confirmed by reading the script's `summary` section, lines 257-261) — no new state file needed, this is a live read of the log itself, consistent with this codebase's "no new state-tracking database" convention already established for `REQ-postinstall-idempotency-live-check` in Phase 9.

**Viewing the log (no new Diagnostics view, per REQ):** reuse the existing `#policy-detail` `Static` widget (`installer/wizard_app.py:890`, `917-1019`) that already renders `_policy_detail(policy)`. Add one new keybinding (e.g. `l`, "view log") that toggles the same widget's content between the normal description and the log's last N lines, for the daemon policy row only. This adds zero new screens/modals, matching the requirement's explicit "no new top-level Diagnostics view."

### The time-of-day picker

No text-entry widget (`Input` or otherwise) exists anywhere in this codebase today — grepped `wizard_app.py` and `catalog_tui.py` in full this session, confirmed zero matches for `Input(`. The closest existing "pick one of several options" precedent is `NavScreen` (`installer/wizard_app.py:1100-1123`), a `ModalScreen[str | None]` wrapping a `ListView`/`ListItem` list, dismissing with the chosen value:

```python
# Source: installer/wizard_app.py:1100-1123 (NavScreen), the direct template
class TimePickerScreen(ModalScreen[str | None]):
    def compose(self) -> ComposeResult:
        yield ListView(*[ListItem(Label(slot), id=slot) for slot in _TIME_SLOTS])
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.id)          # e.g. "03:30"
    def action_cancel(self) -> None:
        self.dismiss(None)
```

**Recommendation:** a quantized list (e.g. every 30 minutes, `"00:00"` .. `"23:30"`, 48 entries) rather than a free-text `HH:MM` field. This is the planner's call per CONTEXT.md's discretion note, and this research grounds the recommendation concretely: introducing Textual's `Input` widget would be the first use of free-text entry anywhere in this TUI, requiring new validation/error-display code with no existing pattern to match; a `ListView`-based picker reuses `NavScreen`'s exact, already-tested shape.

### Reading back / persisting the chosen schedule

CONTEXT.md left this as discretion. **Recommendation:** store the Hour/Minute *in the plist itself* (read back via `plistlib.loads(plist_path.read_bytes())["StartCalendarInterval"]`), not a separate config file. This matches the codebase's live-check convention (no new state-tracking database, mirroring `tweak_present`/`guard_status`/`plugins_owned` all reading their own managed artifact rather than a shadow record) — the plist *is* the source of truth for the schedule, and a config file that could drift from it would be a second, redundant source of truth. The "has the user ever made a decision at all" marker (needed only for the on-by-default bootstrap, see Pitfall 2) is a *different* concern from "what time is currently scheduled" and should not be conflated with it.

### Anti-Patterns to Avoid

- **Parsing `launchctl print` output for status:** explicitly disclaimed as non-API by `man launchctl` on this machine (quoted above). Use plist-file presence instead.
- **Passing the shell script through `/bin/sh -c "... >> log"` in `ProgramArguments`:** works, but re-introduces a hand-built shell string with the same escaping risk `plistlib` was chosen to avoid for the plist itself, and cannot easily implement the "truncate if too big" step. Use a small Python wrapper file instead (same precedent as `wait_time.py`).
- **Relying on the default `launchd` environment for `fd`/`rg` discovery:** see Common Pitfall 3.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| plist XML generation | A hand-written XML string with `str.replace()` placeholders (this codebase's `_DOCKER_BODY`-style convention) | `plistlib.dumps`/`plistlib.loads` | Live-verified round trip on this machine; correct escaping for any path containing XML-special characters, for free. |
| "Is the LaunchAgent currently loaded" | Parsing `launchctl print` text | `plist_path.exists()` | `man launchctl` on this machine explicitly disclaims `print`'s output as "NOT API in any sense at all" — quoted above. |
| Log rotation | A hand-rolled line-counting/date-parsing truncator | A simple byte-size cap with a `=== <timestamp> ===` header boundary snap | No existing precedent in this codebase to extend; a byte cap is the simplest correct implementation of D-03's "no locked number" instruction. |

**Key insight:** everything this phase needs beyond `launchctl` itself is either already in this codebase (the `Policy`/`PolicyResult` triad, `run_captured`/`CommandError`, `apply_block`/`strip_block`, the `ManagedExecutable`/`helper_assets` copy mechanism) or is one stdlib import (`plistlib`) verified live in this session — there is no legitimate case for a new third-party dependency in this phase.

## Common Pitfalls

### Pitfall 1: The docker/`watch` pattern the requirement names as the template is a hard block, not a soft one
**What goes wrong:** `REQ-daemon-dependency-gating` says to declare `fd`/`rg` as `requires` "(matching the docker tweak's watch dependency pattern)" while also saying "apply never refuses to run when they're missing." Reusing `Policy.requires`/`missing_requires` with zero other change reproduces the *docker* behavior exactly — which is a hard block.
**Why it happens:** `installer/wizard_app.py`'s `action_toggle_policy` (lines 1025-1037, read in full this session) contains:
```python
if not active and policy.missing_requires:
    self.status.set(
        "Install required tool(s) first: "
        f"{', '.join(policy.missing_requires)}. Open Catalog, install them, then retry.",
        "warn",
    )
    self._set_detail(policy)
    return
```
This check is *generic* — it fires for every `Policy`, not just `docker`. A real, currently-passing test proves it: `tests/test_wizard_app.py:964-984`, `test_policy_missing_required_tool_blocks_enable`, constructs a policy with `id="tweak:docker"`, `requires=("watch",)`, `missing_requires=("watch",)`, presses `space`, and asserts (quoted verbatim, lines 981-984):
```python
await pilot.press("space")
assert calls == []
assert screen.active_state["tweak:docker"] is False
assert "Install required tool(s) first: watch" in screen.status.text
```
`calls == []` proves `policy.apply` (the closure) is never even invoked — the block happens entirely at the UI layer, before `apply()` gets a chance to run.
**How to avoid:** add a new field `Policy.hard_requires: bool = True` (default `True` preserves every existing caller — `ban_policy`, `tweak_policy`, `omz_plugins_policy` — unchanged, no test of theirs needs to move). `daemon_policy` is the first and only caller to pass `hard_requires=False`. Change the gate in `action_toggle_policy` to `if not active and policy.missing_requires and policy.hard_requires:`. The existing `_requires_cell`/`_policy_detail` rendering (the "missing: fd, rg" yellow text, the "Install from Catalog" detail line) needs zero changes — REQ-daemon-dependency-gating's "surfaced via the existing missing_requires UI with no new mechanism" is satisfied by the *rendering* staying identical; only the *gate* changes, and only for policies that opt in.
**Warning signs:** if the planner instead ships `daemon_policy` with plain `requires=("fd","rg")` and no new field, `test_policy_missing_required_tool_blocks_enable`-shaped behavior will silently make the daemon un-re-enable-able on any machine without `fd`/`rg` — this will not fail any existing test (nothing currently tests the daemon), so it must be caught by a *new* test asserting the daemon's `apply` **is** called with `fd`/`rg` both absent.

### Pitfall 2: "On by default" has no existing precedent — every current `Policy.active` is presence-based, none self-apply
**What goes wrong:** SC#1 requires the daemon to be ON on a *fresh* macOS install without the user pressing space. But `Policy.active` for `ban_policy`, `tweak_policy`, and `omz_plugins_policy` (read in full this session, `installer/policy.py`) is always computed by reading whether the artifact is *already* on disk — none of them ever call their own `apply()` proactively. If `daemon_policy` is wired the same way, a genuinely fresh machine shows the daemon as OFF (no plist exists yet) exactly like every other machine, and SC#1 is not met.
**Why it happens:** presence-as-truth is right for "is it active *right now*" but says nothing about "has this policy's default ever been applied on this machine." A machine where the plist is absent because the user explicitly disabled it, and a machine where the plist is absent because setup has never run before, are indistinguishable by plist presence alone.
**How to avoid:** copy `installer/omz.py`'s exact pattern (`_record`/`_record_owned`/`_clear_owned` against a `state_path`, reusing `installer.shellrc.apply_block`/`strip_block` — read in full this session, lines 239-297) — but for a *different* question: not "which plugins did we add" but "has any decision (auto-default or explicit user toggle) ever been recorded for this policy." Recommend reusing `~/.myshellrc` as `state_path` again (consistent with `omz_plugins_policy`'s own choice), with a new marker block e.g. `# >>> tools-installer daemon:decided >>>`. In `setup.py`'s composition root (the only place with "is this the very first run" context — mirrors exactly how `_build_app` already computes `installed = {tool.id: is_installed(tool) for tool in tools}` once, up front): if `platform.os == "macos"` and the marker is absent, call `policy.apply()` once before rendering `PoliciesScreen`, then record the marker. `policy.remove()` must also record the marker (an explicit disable is also "a decision"), so the daemon is never silently re-enabled on a later run after the user turned it off.
**Warning signs:** a test that runs `_build_app`/`setup.py`'s wiring twice in a row on a fresh `tmp_path` HOME, disabling the daemon between runs, and asserting it stays disabled on the second run — this is the test that would catch a naive "just default `active=True` if plist absent" implementation, which would re-enable itself every session.

### Pitfall 3: `launchd`'s default environment has almost no PATH — `fd`/`rg` (and even the wrapper's own tools) will not be found unless the plist sets `EnvironmentVariables.PATH` explicitly
**What goes wrong:** the prune script's own `HAVE_FD`/`HAVE_RG` detection (`command -v fd`/`command -v rg`, read in the script this session, lines 82-84) depends entirely on the invoking process's `PATH`. A LaunchAgent's default environment is *not* an interactive shell's PATH.
**Why it happens:** live-verified on this machine — bootstrapping a test LaunchAgent and running `launchctl print` on it shows, verbatim:
```
	default environment = {
		PATH => /usr/bin:/bin:/usr/sbin:/sbin
	}
```
This machine's real `fd`/`rg` are installed via Homebrew at `/usr/local/bin/fd` and `/usr/local/bin/rg` (confirmed via `which fd`/`which rg`, `brew --prefix` → `/usr/local`) — neither directory is in that default PATH. A scheduled run would *always* silently take the script's find/grep fallback, even on a machine where the catalog shows `fd`/`rg` installed, which is not a crash but does mean REQ-daemon-dependency-gating's "surfaces via missing_requires" signal and the *actual scheduled behavior* could silently disagree (UI says "fd, rg available", scheduled run never uses them).
**How to avoid:** set `EnvironmentVariables.PATH` explicitly in the generated plist, verified live to work — a second test plist with `EnvironmentVariables = {"PATH": "~/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"}` (expanded to a real absolute path, `~` does not expand in a plist), bootstrapped and printed, showed (verbatim):
```
	environment = {
		PATH => /Users/ramon/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
		XPC_SERVICE_NAME => com.tools-installer.test2
	}
```
confirming the override takes effect. Include both Apple-Silicon (`/opt/homebrew/bin`) and Intel (`/usr/local/bin`) Homebrew prefixes plus this project's own `~/.local/bin` (expanded via `str(Path.home() / ".local" / "bin")`), since the daemon's plist is written once at apply-time on whichever Mac it runs on — `installer/platform.py`'s `Platform.arch` (already detected) tells you which one actually applies, but including both costs nothing and survives an architecture change (e.g. a Homebrew reinstall under Rosetta) more gracefully than picking one.
**Warning signs:** a Tier-3/container-style verification (per this project's own `# Verified {date}: ...` convention, `REQ-registry-authoring-verification-checklist` from Phase 6) that actually schedules a run and confirms the log shows `tooling: fd=yes rg=yes` — a unit test alone cannot catch this, since it is purely about the real `launchd` runtime environment, not this codebase's own logic.

### Pitfall 4: `bootstrap`'s exit code cannot distinguish "already loaded" from any other failure
**What goes wrong:** naive error handling that treats a non-zero `bootstrap` exit as fatal will break re-applying a policy that is already active (e.g. after a schedule-time change).
**Why it happens:** live-verified — bootstrapping the same label twice in a row: first call exit 0, second call exit 5 with message `"Bootstrap failed: 5: Input/output error"`. The *same* exit code 5 was also returned by a `bootout` call on a label that was already unloaded, with a different but equally generic message. Exit code 5 is launchd's catch-all, not a specific "duplicate" signal.
**How to avoid:** always call `bootout` immediately before `bootstrap` and discard the `bootout` result/exception unconditionally (it correctly fails-silently whether the service was loaded or not); treat only the subsequent `bootstrap` call's failure as real. This is the standard idempotent-apply shape and was exercised successfully end-to-end in this session's transcript.
**Warning signs:** a test that calls `daemon_policy(...).apply()` twice in a row (e.g. to simulate reapplying after a schedule change) and asserts no exception on the second call.

## Code Examples

### Reading the current schedule back out of an existing plist (live-verified)
```python
# Source: this session's own live plistlib round-trip (verified on this machine)
import plistlib
from pathlib import Path

def read_schedule(plist_path: Path) -> tuple[int, int] | None:
    if not plist_path.exists():
        return None
    data = plistlib.loads(plist_path.read_bytes())
    interval = data.get("StartCalendarInterval")
    if not isinstance(interval, dict):
        return None
    return interval.get("Hour", 0), interval.get("Minute", 0)
```

### Idempotent apply sequence (live-verified subcommands and ordering)
```python
# Source: this session's live launchctl transcript (bootstrap/print/bootout cycle above)
from installer.run import CommandError, run_captured

def bootstrap(uid: int, plist_path: Path, label: str) -> None:
    try:
        run_captured(["launchctl", "bootout", f"gui/{uid}/{label}"])
    except CommandError:
        pass  # not currently loaded — expected on first install, harmless otherwise
    run_captured(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)])  # real errors propagate

def bootout(uid: int, label: str) -> None:
    try:
        run_captured(["launchctl", "bootout", f"gui/{uid}/{label}"])
    except CommandError:
        pass  # already unloaded — fine for a remove()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `launchctl load`/`unload` | `launchctl bootstrap`/`bootout` (+ `enable`/`disable`) | Documented as the "Recommended alternative" in `man launchctl` on this machine (macOS 15.7.9) | `load`/`unload` still work but are the deprecated path; a plan or implementation written from older training data would likely reach for `load`/`unload` first. |

**Deprecated/outdated:** `launchctl load -w`/`unload -w` for toggling the `Disabled` key — `man launchd.plist` on this machine states the `Disabled` key's state "is kept externally" now and is better managed through `enable`/`disable`, not by editing the plist's `Disabled` key directly (this phase does not need the `Disabled` key at all, since plist presence itself is the toggle signal recommended above).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommended label `com.tools-installer.prune-tmpdir` and log path `~/Library/Logs/tools-installer/prune-daemon.log` are naming choices, not verified requirements — no external authority mandates this exact string. | Architecture Patterns → plist template, log location | Low — purely cosmetic; changing either later is a one-line rename with no compatibility surface (nothing else in the codebase references these names yet). |
| A2 | 256 KB log-truncation cap is this research's own reasonable default (D-03 explicitly left it unlocked), not a value derived from any spec or measurement of real long-term usage. | Architecture Patterns → Log file location and truncation | Low — easy to change later; worst case is a slightly larger or smaller retained history, no correctness impact. |
| A3 | The quantized 30-minute `ListView` time picker (vs. a free-text `HH:MM` `Input`) is this research's UI recommendation exercising CONTEXT.md's explicit discretion grant, not a locked decision. | Architecture Patterns → The time-of-day picker | Low — CONTEXT.md already delegates this choice to the planner; if a text-entry field is preferred instead, `Input` would need to be introduced for the first time in this codebase, which is a bigger, but still contained, follow-up. |

**If this table is empty:** N/A — three low-risk naming/UX assumptions are logged above; every technical/mechanism claim in this document (plist schema, `launchctl` subcommands, PATH environment behavior, the hard-block test) was executed live on this machine this session and is `[VERIFIED]`, not `[ASSUMED]`.

## Open Questions

1. **Should the "on by default" auto-apply attempt silently fail on a machine where `launchctl bootstrap` errors for an unrelated reason (e.g. a restricted/managed Mac), or should it surface a one-time notice?**
   - What we know: `ban_policy`/`tweak_policy`/`omz_plugins_policy` all report failures back through `PolicyResult.warning`, but those only fire in response to a user-initiated toggle; the on-by-default path runs *before* the user has looked at the Policies screen at all.
   - What's unclear: whether a first-run failure should be visible in `setup.py`'s existing catalog/status flow, or silently leave the policy `active=False` for the user to notice and retry manually via the normal toggle path.
   - Recommendation: silently leave it `active=False` (i.e., record the "decided" marker only on success) so a transient failure is retried on the *next* `make setup` run rather than requiring the user to notice a one-time toast; the Policies screen already shows the real `active` state on entry regardless.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `launchctl` / `launchd` | The entire policy | ✓ (macOS only) | "Darwin Bootstrapper Version 7.0.0" (macOS 15.7.9) `[VERIFIED: local shell — launchctl version]` | Policy is inert on Linux (SC#2) — gate `daemon_policy` construction on `platform.os == "macos"` in `setup.py`, exactly like `applicable_bundles(platform)` already gates macOS/Linux-only tweaks. |
| `fd` | Faster scoped file matching in the prune script | ✓ on this machine (`/usr/local/bin/fd`, brew) | not queried (irrelevant — soft dependency) | Script's own `find` fallback, already implemented and read in full this session. |
| `rg` | Faster `lsof`-output filtering in the prune script | ✓ on this machine (`/usr/local/bin/rg`, brew) | not queried (irrelevant — soft dependency) | Script's own `grep` fallback, already implemented and read in full this session. |
| `plistlib` | plist generation | ✓ (Python stdlib, this machine's Python 3.14.7) | stdlib, no version to pin | None needed — always present in any supported Python. |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** `fd`/`rg` — both already present on this development machine, but the policy must work identically when absent (script's own find/grep path), per REQ-daemon-dependency-gating.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8+ with `pytest-asyncio` (`asyncio_mode = "auto"`, `[VERIFIED: pyproject.toml:46-49]`) and `pytest-cov` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_policy.py tests/test_policies_e2e.py -x` |
| Full suite command | `uv run pytest --cov` (`[VERIFIED: Makefile:47-48]`, quoted: `test:  ## Run tests with coverage` / `uv run pytest --cov`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-launchd-prune-policy | `daemon_policy(...).apply()` writes a real plist with the right keys/values; `.remove()` deletes it and best-effort boots it out | unit (pure, injected `launchctl` runner double) | `pytest tests/test_policy_daemon.py -x` | ❌ Wave 0 — new file, mirrors `tests/test_policy_omz.py` |
| REQ-launchd-prune-policy | Policy is absent/inert from the Policies list entirely on a non-macOS `Platform` | unit | `pytest tests/test_policy_daemon.py -k linux -x` | ❌ Wave 0 |
| REQ-daemon-log-diagnostics | The wrapper appends a timestamped block and truncates when the cap is exceeded | unit (pure function over a `tmp_path` log file, no real `launchctl`) | `pytest tests/test_daemon_wrapper.py -x` | ❌ Wave 0 — new file for the new wrapper module |
| REQ-daemon-log-diagnostics | Policies detail panel shows a "last run: ... N items removed" line and a working log-view toggle keybinding | e2e (headless Textual pilot, mirrors `tests/test_policies_e2e.py`'s existing `_omz_app`-style fixtures) | `pytest tests/test_policies_e2e.py -k daemon -x` | ❌ Wave 0 (extend existing file) |
| REQ-daemon-dependency-gating | Toggling the daemon ON succeeds (calls `apply`) even when `fd`/`rg` are both reported missing | e2e (mirrors `test_policy_missing_required_tool_blocks_enable` but asserts the opposite) | `pytest tests/test_wizard_app.py -k daemon_soft_requires -x` | ❌ Wave 0 — this is the test that catches Pitfall 1 |
| REQ-daemon-dependency-gating | `missing: fd, rg` still renders in the Requires column / detail panel exactly as before | unit/e2e | `pytest tests/test_wizard_app.py -k requires_cell -x` | ✅ existing rendering path, extend with a daemon fixture |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_policy_daemon.py tests/test_daemon_wrapper.py -x`
- **Per wave merge:** `uv run pytest --cov`
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus `make validate` (ruff/pyright/bandit/vulture) — bandit specifically should be checked against the new `subprocess`/`launchctl` invocations, though using the existing `installer.run.run_captured` seam (array-argv, no `shell=True`) already satisfies bandit's usual `subprocess` findings elsewhere in this codebase.

### Wave 0 Gaps
- [ ] `tests/test_policy_daemon.py` — new file, covers REQ-launchd-prune-policy (plist content, macOS-only gating, `hard_requires=False`)
- [ ] `tests/test_daemon_wrapper.py` — new file, covers REQ-daemon-log-diagnostics (append + truncate logic, pure function over `tmp_path`)
- [ ] Extend `tests/test_policies_e2e.py` and `tests/test_wizard_app.py` — covers the UI-level soft-requires behavior (REQ-daemon-dependency-gating) and the new log-view keybinding
- [ ] Framework install: none — `pytest`/`pytest-asyncio` already present

## Security Domain

`security_enforcement` is enabled (`security_asvs_level: 1`, `security_block_on: "high"`, `[VERIFIED: .planning/config.json]`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user local machine tool; no auth surface. |
| V3 Session Management | No | N/A. |
| V4 Access Control | No | N/A — no multi-user/privilege boundary; LaunchAgent runs as the invoking user only (never a LaunchDaemon/root path). |
| V5 Input Validation | Yes | The only new user input is the HH:MM picker — a closed `ListView` selection (not free text) makes out-of-range values structurally impossible, which is a stronger control than validating a parsed string. The `--days` value stays hardcoded to the script's own default (3) per the requirement text ("not hardcoded higher just because it's unattended") — no new numeric input to validate there. |
| V6 Cryptography | No | N/A — no secrets, no crypto operations in this phase. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Argument/path injection into the scheduled command | Tampering | `ProgramArguments` is a literal argv array (`plistlib`-generated), never a shell string built by concatenation — this is the same array-argv discipline `installer/run.py`'s `run_command`/`run_captured` already enforce everywhere else in this codebase, confirmed live to work correctly with `plistlib`. |
| A world/group-writable plist letting another local user redirect what root-equivalent... (n/a here, user-level agent) redefine what runs at next login | Tampering | `man launchctl`'s `load` documentation (quoted above) states configuration files "must disallow group and world writes" for LaunchAgents/Daemons generally; `Path.write_bytes()`'s default mode under a normal `022` umask already satisfies this (owner rw, group/other read-only) — no special `chmod` strictly required, but an explicit `plist_path.chmod(0o644)` after writing removes any dependency on the invoking process's umask and is cheap insurance. |
| Malformed/XML-injected plist content from a path containing special characters | Tampering / Denial of Service (job never registers) | `plistlib.dumps` handles XML escaping automatically — verified via a real round trip in this session; this is the primary reason `plistlib` is recommended over hand-rolled XML string templating for this one artifact. |
| A stale, previously-scheduled job surviving after a schedule change because `bootstrap` on an already-loaded label silently fails | Availability (silently running the *old* schedule) | The verified bootout-then-bootstrap idempotent sequence (Pitfall 4) — never assume a `bootstrap` call updated an already-loaded job's config; it does not, `launchd` must be told to reload. |

## Sources

### Primary (HIGH confidence — live commands executed on this machine this session)
- `sw_vers`, `uname -a`, `launchctl version` — macOS 15.7.9, `launchctl` "Darwin Bootstrapper Version 7.0.0"
- `man launchd.plist` — `StartCalendarInterval`/`Hour`/`Minute`/`Disabled`/`StandardOutPath`/`StandardErrorPath`/`RunAtLoad` key definitions, quoted verbatim above
- `man launchctl` — `bootstrap`/`bootout`/`load`/`unload`/`enable`/`disable`/`print`/`print-disabled` subcommand text and the `domain-target`/`service-target` (`gui/<uid>/<label>`) syntax example, quoted verbatim above
- `~/Library/LaunchAgents/*.plist` (5 real files on this machine) — read in full, confirming real key usage and the label/directory convention
- Live `launchctl bootstrap`/`print`/`bootout` cycle against a real (harmless `/bin/echo`) test plist, twice — once for the basic cycle, once to confirm `EnvironmentVariables.PATH` override behavior
- `python3 -c "import plistlib; ..."` round-trip of a real `StartCalendarInterval` dict, asserted equal after `dumps`/`loads`
- `scripts/prune-user-tmpdir.sh` — read in full (267 lines)
- `installer/policy.py`, `installer/tweaks.py`, `installer/omz.py`, `installer/platform.py`, `installer/locations.py`, `installer/shellrc.py` (relevant sections), `installer/run.py`, `installer/wizard_app.py` (relevant sections), `installer/session.py`, `setup.py` (relevant sections) — read in full or in the cited line ranges
- `tests/test_wizard_app.py:964-984`, `tests/test_policies_e2e.py:280-311`, `tests/test_policy_tweaks.py` — read, confirming the hard-block behavior described in Pitfall 1
- `.planning/config.json`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/phases/11-background-maintenance-daemon/11-CONTEXT.md`, `pyproject.toml`, `Makefile` — read for project conventions and gating flags

### Secondary (MEDIUM confidence)
- None used — every claim above was either directly executed/read this session or is explicitly logged in the Assumptions table.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib-only, live round-tripped.
- Architecture (plist/launchctl mechanics): HIGH — every key, subcommand, and PATH-environment claim executed live on this exact machine this session.
- Architecture (Policy/`hard_requires`/on-by-default design): HIGH — grounded in verbatim reads of this repo's own source and a real, currently-passing test proving the conflict.
- Pitfalls: HIGH — all four are either live-executed findings on this machine or verbatim-quoted from this repo's own tests/source.
- UI shape for the time picker / log truncation cap: MEDIUM — these are this research's own recommendations exercising CONTEXT.md's explicit discretion grants, not externally verified facts (see Assumptions Log A2/A3).

**Research date:** 2026-09-06
**Valid until:** 30 days for the stdlib/codebase-pattern claims (stable); the `launchctl`/plist mechanics are tied to this machine's exact macOS version (15.7.9) — re-verify the `bootstrap`/`bootout` recommendation and the default-environment PATH behavior if the target development/CI macOS version changes materially before implementation.
