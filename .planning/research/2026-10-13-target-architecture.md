# Target architecture: v0.50.0 "Truthful lifecycle"

Date: 2026-10-13. Mode: ponytail ULTRA design pass, read-only (this file is the only write).
Inputs: `audit-2026-10-13/SYNTHESIS-AND-PLAN.md` and reports A–G; `2026-10-11-ponytail-audit.md` (F1–F17); `2026-10-11-architecture-review-gpt-6.1-sol.md` (AR-01..AR-12); ROADMAP backlog 999.1–999.11; `todos/pending/2026-09-16-…`; PROJECT.md, MILESTONES.md, `.claude/architecture.md`, `.claude/skills/tool-onboarding/SKILL.md`; code via `codegraph sync` plus targeted reads.
Code baseline: `git diff --stat 7861ced HEAD -- installer setup.py tests` is empty, so every audit line number still holds. Every hazard in §10 was re-read at the cited line today.

Rule for this document: audits are cited by ID and not restated. "Deletes" lists code that goes away. "+N" is a rough count of new lines.

---

## 0. Decisions in one screen

| # | Decision | Why it is the smallest complete change |
|---|---|---|
| D-A | One `ToolState` per tool per generation, built inside the existing `VersionRefreshService.refresh` loop (`version_status.py:677`) and published in **one swap** | That loop already holds every input (presence, ownership, version, inventory). No new service or module is needed |
| D-B | A closed `Health` enum (7 values) and one pure `tool_health()` | G R1. Notes that offer no action (shadowed, off-policy, unknown owner, unreadable version) stay `reasons`, not states |
| D-C | A closed `Disposition` enum (8 values) and one pure `plan()` in `session.py`, used by the TUI **and** by headless `--all` | Deletes the second engine (`app.run_wizard` 127-197) and the five skip paths (G R4) |
| D-D | **No new method kind.** The lifecycle contract is: per-kind closed param sets, plus 3 new `script` params (`paths`, `remove`, `update`), plus 1 tool param (`config_paths`) | Every proven per-OS/arch gap resolves as data or as a `u` gate (§4.4) |
| D-E | Receipts: one JSON file per tool at `~/.local/state/tools-installer/receipts/<id>.json`, written atomically | The only proof of "we wrote it" (AR-01, D C2). The state dir already exists (`settings.py:40-41`) |
| D-F | Removal = `removal_plan(tool, state)` with levels L1/L2/L3. Unproven means not removable, in the CLI and the TUI | Closes F1/AR-01/C2 by construction |
| D-G | Configuration reuses existing seams: closed `POSTINSTALL_HOOKS` (made reversible), `post_install` (`set_login_shell` + `source_shell_init`), `TweakBundle` for shell init, and `sync_terminal_shells` (plus a dry run) | No new configuration framework. Four dead `post_install` names are deleted |
| D-H | One screen family on the existing `AppScreen`: neutral root, push-all, enter-after-push, one app-level refresh owner. **No `RowsScreen`** | G R2 pushback, adopted by SYNTHESIS |
| D-I | Zero sudo performed by the app. Native rungs and root-needing bootstraps become **handoffs** after a preflight | Restores the stated invariant (PROJECT.md "Out of Scope"). `executors.py:370-379` runs `sudo` today with no usable tty (`run.py:235`) |
| D-J | v0.50.0 has 9 phases in a refined order: receipts move **into** phase 3, because removability is a `ToolState` field | Otherwise phase 5's Uninstall projection would have no proof to project |

### 0.1 Ultra pushback on the request itself

| Asked for | Done instead | Why |
|---|---|---|
| `ToolState.installed` and `ToolState.installations` fields | `present` is a property derived from `health`. Installations are `ownership.candidates` + `shadowed` (`ownership.py:290-312`), which already exist | AR-03 wants several observed installs; `OwnershipCandidate` already models them. A second list would be the eighth classifier |
| `config state` field | `unconfigured: tuple[str, ...]`, the exact steps RECONFIGURE would run | A state without its action is a note. The tuple drives both `MISCONFIGURED` and the review text |
| A `service` lifecycle step | Handoff lines only (colima/podman machine/container system start). Not executed, not health-checked | C G11 lists 4 tools, all macOS VMs or root daemons. Running them is out of the zero-sudo/no-daemon scope |
| A keep / delete / ask config policy enum at tool level | `config_paths` (data) + one "delete config too" choice on the Uninstall confirm. Default keep. Shared dirs are never listed | All three enum values reduce to "list it or don't" plus one confirm. Shared dirs (`~/.cursor`, `~/.gemini`, `~/.claude`) are protected by omission plus a validator |
| Per-OS/arch new kinds (dmg, `app {ver}`, Distrobox) | None. Data fixes plus a `u` gate (§4.4). Distrobox is an open decision (O5) | B/AR-07: per-OS/arch splitting already works. Every proven gap has a non-kind fix |
| A `RowsScreen[T]` base class (999.10) | Defaults in `AppScreen` (+~15 lines) and the prune in `ToolBrowser` (+3) | G R2 |
| Separate SKIP_CURRENT/SKIP_MANAGED/SKIP_UNAVAILABLE/SATISFIED dispositions (G) | `SKIP` (cleared after the run) vs `BLOCKED` (retained). The reason string carries the rest | 999.1 retention only needs "clear or keep". Four values would differ only in wording |

---

## 1. `Health`: the closed set and its precedence

**Lives in** `installer/version_status.py`, next to `VersionStatus` (`:131`) and `SkillHostStatus` (`:418`). That module is the only one above `ownership`, `status` and `skill_lifecycle` in the import graph (G).

```python
class Health(StrEnum):            # declaration order IS precedence for a present tool
    CHECKING = "checking"         # present-looking, no record for this generation yet
    BROKEN = "broken"             # = needs reinstall
    MISCONFIGURED = "misconfigured"
    OUTDATED = "outdated"
    OK = "ok"
    MISSING = "missing"           # not present; a method applies here
    UNAVAILABLE = "unavailable"   # not present; no method applies here

def tool_health(ev: Evidence) -> tuple[Health, tuple[str, ...]]   # pure; one parametrized test
```

`Evidence` is a plain local dataclass built in the refresh loop. It is not stored. Every fact that does not win precedence still adds one sentence to `reasons`.

| Health | Glyph | Set when (any of) | Fixed by |
|---|---|---|---|
| CHECKING | `…` dim | `state_of(id)` is `None` (an invalidated generation, no pass yet) | WAIT |
| BROKEN | `!` red | dangling pnpm shim (`ownership.broken`, `ownership.py:595`) · pnpm/uv inventory lists the package but no command resolves · the link resolves to a directory or nothing (Sublime, E gap 1) · the receipt says a file exists but it is gone or not executable · install-time smoke failed (recorded in the receipt) · a macOS stub is the only hit (`/usr/bin/java`, C G1) → treated as **not present**, so MISSING, with a reason | REPAIR |
| MISCONFIGURED | `≈` yellow | skill pack absent on a harness `present_harnesses` finds (G R1, F X7) · hook tool: a supported, present host is not in `receipt.hooks` (F X1) · kitty/WezTerm: the terminal dry run reports drift while zsh is present (G #4a) · a pnpm co-install group is incomplete | RECONFIGURE |
| OUTDATED | `↑` yellow | `VersionStatus.outdated is True` | UPDATE, or SKIP when the owner is not mutation-grade |
| OK | `✓` green | present and none of the above | SKIP (`r` → REINSTALL) |
| MISSING | `○` | no presence evidence; `resolve_methods` is non-empty or `platform_could_support` | INSTALL |
| UNAVAILABLE | `–` dim row | no presence evidence and `unavailable_reason` is set | BLOCKED |

**Present** = any install evidence: a command on PATH, a `detect_path`, a declared `bin_dir`, **the implicit `~/.local/bin/<bin>` for download kinds** (B #4: `status.py:40-52` checks only an explicit `bin_dir`), an app bundle, a manager inventory record, a skill host, or an existing receipt artifact. A present tool is never MISSING: a pnpm package without its command is BROKEN (AR-03 "present does not mean runnable").

**Notes, not states** (they go into `reasons` plus the existing Owner suffix): shadowed, off-policy (this also covers REQ-manager-drift-alerting, see §8), unknown owner, version unreadable, stale cache, "zsh is not the login shell", "bin dir not on this process PATH" (G: PATH is inherited, `status.py:26-32`).

### 1.1 Probes per method kind, and their cost

Every probe below runs in the single full-catalog pass. G measured that pass at 4.5–5.7 s for 90 tools on a worker thread. "Cheap" means a stat, readlink, read of a file under 10 KB, or a lookup in an inventory that is already cached. "Install-time" means the probe runs once, inside the executor, and its result is stored in the receipt.

| Kind | Presence | BROKEN | MISCONFIGURED | Version source | Cost |
|---|---|---|---|---|---|
| github_release, tarball | which ∪ `artifact_paths(method)` link ∪ receipt | link dangling / to a dir / not executable; smoke failure (receipt) | – | `--version` probe + GitHub latest (7 d TTL) | cheap, plus 1 exec per present tool (existing) |
| app | bundle dir ∪ cli link | cli link dangling | – | none → `u` refused (§4.4) | cheap |
| script | which ∪ `detect_path` ∪ `bin_dir/cmd` ∪ receipt `paths` | receipt file gone | – | `--version` / `version_file` | cheap |
| brew, cask | inventory (6 h snapshot) ∪ which | – (the manager owns health) | – | inventory + `brew outdated` | cached |
| dnf/apt/pacman/rpm-ostree/os-package | `path_owner_package` | – | – | probe; latest not tracked | 1 `rpm -qf` per tool, **memoized per pass** (B 15 WR-04) |
| node (pnpm) | which ∪ `pnpm list -g` | dangling shim; listed-but-no-command | co-install group incomplete | inventory | cached |
| uv-tool | which ∪ `uv tool list` (owner dir = `uv tool dir`, F X4) | listed-but-no-command | – | inventory | cached |
| sdkman | `detect_path`/`bin_dir` | `current` link dangling | – | readlink of `current` | cheap |
| skill_pack | per-harness probes (existing cache, 1 call per harness) | – | absent on a present harness | – (`revision_policy` stays unread, cut) | cached |
| host_setup | which | – | – | probe the **unresolved** which path (E gap 3) | cheap |
| any tool with `postinstall` | (as its kind) | – | present supported host ∉ `receipt.hooks[hook]` | (as its kind) | cheap (`present_harnesses` = which + stat) |
| kitty, wezterm | (as their kind) | – | `sync_terminal_shells(write=False)` returns the tool's name | (as their kind) | 3 file reads |

Install-time only: the smoke test (exec `<link> --version`; failure means OSError, exit 126/127, or a stderr loader error such as `GLIBC_`). It raises `ExecutorError` so the ladder falls to the next method (D C6). Doctor keeps the pnpm puppeteer smoke check (it runs a browser) and publishes it into `reasons`.

**Replaces:** the glyph logic `catalog_tui.py:227-228,494-517` and the skill override `:479-492`; the presence answer of `is_installed` as a decision input (`status.py:18-67` stays as one evidence probe); the `_present` fork.

---

## 2. `ToolState`

```python
@dataclass(frozen=True)
class ToolState:                         # installer/version_status.py
    tool_id: str
    generation: int
    health: Health
    reasons: tuple[str, ...]             # one sentence per fact; catalog detail, Uninstall, Execute, Doctor all read it
    ownership: ManagerOwnership | None   # owner + confidence; candidates/shadowed = installations (AR-03)
    version: VersionStatus | None
    skill_hosts: Mapping[str, str] | None
    receipt: Receipt | None              # §5
    removable: RemovalPlan               # §4.3; level None = nothing proven
    unconfigured: tuple[str, ...]        # e.g. ("register rtk for codex", "point kitty at zsh")

    @property
    def present(self) -> bool:
        return self.health not in (Health.MISSING, Health.UNAVAILABLE)
```

| Requested field | Where it lives |
|---|---|
| installed | `present` (derived) |
| installations | `ownership.candidates`, `ownership.shadowed`, `ownership.active_path` |
| owner | `ownership.owner` / `.confidence` |
| version | `version` |
| health + reason | `health`, `reasons` |
| removability with proof | `removable` (a plan built only from receipt matches or archive layout proof) plus `receipt` |
| config state | `unconfigured` |

**Computed** once per pass in `VersionRefreshService.refresh`, which already loops over every tool (`version_status.py:694-724`). The same loop now also reads the receipt and the `present_harnesses` set (once per pass), and runs the terminal dry run (once per pass).

**Publication and race rule** (closes AR-04, B 15.1 IN-03):

| Rule | Code |
|---|---|
| A pass captures `started = self._epoch` first | existing `:682` |
| On commit, under `self._lock`: if `self._epoch != started`, publish **nothing** and return | **delete** the `self._statuses.update(statuses)` raced merge at `:751` |
| Otherwise `self._state = new_map` (one assignment, a frozen dict of ToolState) | replaces `_ownership.update` (`:769`) and `_statuses.update` (`:761`) |
| Cache save is best-effort *after* the swap. A failure becomes a warning, not "unpublished" | AR-04 step 4 |
| `invalidate()` bumps the epoch in memory before it persists | existing `:578-589`; caller ignores the persistence error |
| `state_of(id) -> ToolState \| None`. `None` when the map's generation ≠ the epoch → CHECKING | replaces `ownership_of` (`:510-529`), `statuses` (`:503`), `skill_status_of` (`:531`) |
| Manager availability is re-read each pass: `platform = replace(platform, has_brew=which("brew") is not None)`. `plan()` reads `service.platform` | AR-03 / C G3 / D C7. `Platform` stays frozen; only this field is refreshed |
| Keep the epoch even where a worker is cancelled | AR-04 contra F15 |

**Single owner:** `UnifiedApp` runs one `@work(thread=True, exclusive=True)` worker over the **full** catalog. Triggers: mount; close of any mutation (install run, `u`, Uninstall removal, a policy toggle that installs or removes something, Doctor `r` (A #9)); a view entry when the generation is dirty. On commit it calls `self.screen.state_refreshed()` when the screen is an `AppScreen`.

**Deletes:** per-tier `_installed`/`_version_statuses` copies and `set_installed` (`catalog_tui.py:339,349`); the three per-screen workers and their generation counters (F9); `OwnershipRefreshed` (`catalog_tui.py`, `wizard_app.py:2996-3000`); `UninstallInputs.invalidate/refresh`; the `setup.py:783` startup `installed` map (F8); `_artifacts → plan_uninstall` (`version_status.py:591-594`), the "uninstall planner → ownership" arrow AR-03 rejects. Artifact evidence now comes from the receipt plus `download.artifact_paths(method)`.

**Seven forks this removes** (F6 table, verified unchanged): `status.py:18-67`, `catalog_tui.py:479-492`, `uninstall.py:56-97` + `:260-328`, `ownership.py:561` (stays as the *only* ownership computation), `version_status.resolve_status` (stays, called once), `execute_screen.py:499-545`, `policy.py:441-444,853-855`. Plus `deps.py:111` and `engine.py:132`, which read `is_installed` directly. Both take a predicate fed from `state_of`.

---

## 3. `Disposition` and the install plan

```python
class Disposition(StrEnum):       # review text; installer/session.py beside order_for_install (:116)
    INSTALL = "will install"
    UPDATE = "will update"
    REPAIR = "will repair (reinstall)"
    RECONFIGURE = "will reconfigure"
    REINSTALL = "will be reinstalled"
    SKIP = "skipped"              # cleared from the selection after the run
    BLOCKED = "blocked"           # kept in the selection after the run
    WAIT = "checking…"            # Enter waits for one targeted refresh, then re-plans

@dataclass(frozen=True)
class PlanRow:
    tool_id: str
    disposition: Disposition
    reason: str                   # from ToolState.reasons / owner label / unconfigured
    requested_by: str | None      # None = direct selection

def plan(selected: Sequence[str], catalog: Mapping[str, Tool], state_of, platform,
         *, reinstall: frozenset[str]) -> list[PlanRow]          # pure
```

`plan` calls `deps.resolve_dependencies` unchanged for ordering (PROJECT.md: `requires` stays the only ordering mechanism), with `is_installed=lambda t: (s := state_of(t.id)) is not None and s.present and s.health is not Health.BROKEN`.

### 3.1 Default disposition from ToolState

| Health | Owner / proof | Direct selection | Dragged dependency |
|---|---|---|---|
| CHECKING | – | WAIT | WAIT |
| MISSING | – | INSTALL | INSTALL ("needed by X") |
| UNAVAILABLE | – | BLOCKED (`unavailable_reason`) | BLOCKED; dependent BLOCKED "needs X" |
| BROKEN | any | REPAIR | REPAIR (fixes G's "broken dep counts as satisfied") |
| MISCONFIGURED | any | RECONFIGURE (reason = `unconfigured`) | SKIP "already present" |
| OUTDATED | mutation-grade (`MUTATION_GRADE`, `ownership.py:93`) and an update path exists (§4) | UPDATE | SKIP "already present" |
| OUTDATED | native / os-package / unknown / pinned app | SKIP "managed by {owner}" or "no update source" | SKIP |
| OK | installer-owned (receipt or installer/direct) | SKIP "already current (r: reinstall)". `r` → REINSTALL | SKIP |
| OK | another manager | SKIP "managed by {owner}" (`r` refused: it would create a shadow, F1/AR-01) | SKIP |

`r` toggles REINSTALL only for rows that show `(r: reinstall)`. `a` (select all) never produces REINSTALL. That is the default G proposed; see O7.

### 3.2 Execution: existing code, no new executors

| Disposition | Runs |
|---|---|
| INSTALL, REPAIR, REINSTALL | `session.run_installs` with `_with_repair` (`execute_screen.py:239-276`) generalized to a `force_ids` set; `engine.install_tool(repair=True)` (`engine.py:132`) |
| UPDATE | `UpdateService.run` (unchanged) |
| RECONFIGURE | `reapply_post_install` (`engine.py:200-216`) + `run_postinstall(hosts=missing)` + the terminal sync |
| SKIP, BLOCKED | listed and counted, never run |

One function `execute_plan(rows, …) -> list[RowOutcome]` moves the body of `ExecuteScreen`'s worker (`execute_screen.py:593-672`) into `session.py`. The TUI worker and the CLI both call it.

**Headless `--all` / `--categories`:** `app.run_wizard` (`app.py:127-197`) runs one blocking `service.refresh(selected+deps)`, then `plan()`, prints the same table (`render_plan`, which replaces `render_audit`), and runs `execute_plan`. `--yes` runs every row except REINSTALL. The second engine and the silent skip at `deps.py:111` (B #2, 14 IN-01) go away.

**Outcomes and exit code:** `RowOutcome.result ∈ {done, failed, mismatch, dependency_failed, not_attempted, crashed}`. Exit 1 if any executed row is not `done`, including update failures (B 14) and `crashed`. Exit 0 otherwise; SKIP and BLOCKED rows count as 0, because `--all` always contains unavailable rows. The worker body gets `except Exception` → every not-yet-run row becomes `crashed` and the status becomes red "Failed" (B 13 WR-01, §10 H6). The summary counts outcomes with the same words as the review.

**Retained selection after close:** keep failed, BLOCKED, not-attempted and crashed rows; clear done and SKIP rows (999.1). `esc` before start keeps everything (B 13 WR-03: `wizard_app.py:2797` clears unconditionally today).

**Deletes (~ −90):** `_classify_selection` (`execute_screen.py:499`), `_update_targets` (`:531`), `_preflight_prompt`, `render_audit(audit(…))` (`:492`), `audit.py`, `render.py:55`'s dead branch, and `_install_state_changed` (`wizard_app.py:2487,2857,2960`). The terminal-sync trigger becomes "any row not in {SKIP, BLOCKED} ran".

---

## 4. Per-method lifecycle contract

### 4.1 Contract table (after v0.50.0)

L1 = derived from the manager; L2 = derived from params plus a receipt; L3 = explicit recipe in the method's params. "Handoff" = a reviewed text line; nothing runs.

| Kind | Install | Detect | Version | Owner proof | Update | Remove | Configure | Privileges |
|---|---|---|---|---|---|---|---|---|
| github_release / tarball | executor; `replace_symlink` + `is_file` (H1); smoke | `artifact_paths` (one formula with install, F7) | probe + GitHub | receipt (link target / sha256) | `update_download` (existing, staged) | **L2**: receipt artifacts | hooks | none |
| app | `install_app`; `cli_name` honored (AR-07) | bundle + cli link | none | receipt | **refused** ("pinned; no version source", E gap 5) | **L2** | – | none |
| script | vendor script (stdin closed, new session) | which / `detect_path` / `bin_dir` / `paths` | probe / `version_file` | receipt + **`paths`** (claude/cursor versioned roots, E 6) | **`update` argv** if declared, else re-run the script | **L3**: `remove` argv, then delete the existing `paths` | hooks; vendor rc edits suppressed by env/args (data) | preflight `writable_prefix` → handoff |
| brew / cask | `brew install` | inventory | inventory | receipt `{package}` | `brew upgrade` (existing) | **L1** executed only with a receipt, else a hint (O3) | – | none |
| uv-tool / node | executor | inventory | inventory | receipt `{package}` | existing | **L1** like brew; pnpm shows the co-install group warning (A #6) | hooks | none |
| sdkman | `sdk install` | `detect_path` | readlink | inventory (existing) | refused (existing) | **L1** hint `sdk uninstall {c} {version}` (fill in the version, C java) | – | none |
| dnf / apt / pacman / rpm-ostree | **handoff** `sudo dnf install -y P` (D-I, O1) | `path_owner_package` | probe | probe | refused (existing) | hint naming the package, **never a command** (C G10 watch → procps) | – | never run |
| skill_pack | handoff (existing) | per-harness probes | – | – | handoff | handoff text (`Tool.uninstall`) | – | none |
| host_setup (pi) | handoff | which | unresolved path | owner probe kept (B 15 WR-06) | via the real owner | via the real owner (L1 hint) | – | none |

### 4.2 Registry schema change (the whole change)

| Change | Where | Replaces / fixes |
|---|---|---|
| `METHOD_PARAMS: dict[str, frozenset[str]]`, a closed key set per kind. `load_tools` rejects unknown keys | `model.py` (`:668` keeps every key as an opaque param today) | A T-07-14, AR-07 (draw.io `cli_name`), D C10 |
| script `paths = ["~/.local/bin/claude", "~/.local/share/claude"]`: what the vendor writes. Used for ownership (active path under a path → installer/direct), receipt artifacts, and L3 deletion | `model.py`, `ownership.py` candidates, `uninstall.removal_plan` | 999.2 kitty, E claude/cursor owner unknown, 999.8 L3 |
| script `remove = ["opencode", "uninstall", "--keep-config", "--keep-data"]` (argv, `_SCRIPT_ARG_RE`) | same | E vendor recipes |
| script `update = ["sdk", "selfupdate"]` (argv) | `update._update_installer_owned` (`update.py:337-339`) | C G8 (OMZ exit 1, SDKMAN no-op), E antigravity no-op |
| script `writable_prefix = "/home/linuxbrew"` → preflight; not writable → MANUAL handoff | `engine.install_tool` before `_perform` | C brew `sudo -n` abort |
| tool `config_paths = ["~/.config/gh"]`. Validator: under `~`, depth ≥ 2, not a `HARNESS_PRESENCE` marker dir | `model.py` | 999.8 config policy (shared dirs protected) |
| **delete** tool `source`, `owner`, `default_enabled_sensitive_actions`; keep `uninstall` as the manual fallback sentence | `model.py:316-321,825-835` | F11, B 14 IN-03 |
| **delete** `POST_INSTALL_ACTIONS` `configure_path`, `enable_corepack`, `pnpm_setup`, `write_agent_reference` | `model.py:47-54` | C G6 (accepted, never run) |
| **delete** owner probe `managed-download` | `install_ownership.py:83-89`, registry `:2721,:2770` | F11, B 15 WR-07 (PATH-plantable exec) |
| `Owner` += `"volta"`, attribution only (label + `volta uninstall {pkg}` hint, no update) | `ownership.py:77-90` | C G5, B #10, E pi |

No new kind. The kind still selects the executor (`executors.execute`) and update path (`update._perform`). `removal_plan` is the third (and last) switch on kind. That is the "code seam".

### 4.3 Removal seam

```python
@dataclass(frozen=True)
class RemovalPlan:                          # installer/uninstall.py
    level: Literal[1, 2, 3] | None          # None = nothing proven → hint only
    argv: tuple[tuple[str, ...], ...]       # hook unregisters, then L1 manager remove or L3 vendor remove
    paths: tuple[Path, ...]                 # L2 receipt matches / L3 declared paths that exist
    config: tuple[Path, ...]                # deleted only on "delete config too"
    hint: str                               # removal_hint() → Tool.uninstall → "owner unknown — found at <p>; not placed by this installer"

def removal_plan(tool: Tool, state: ToolState) -> RemovalPlan    # pure, computed in the refresh pass
```

Rules: the method that **actually** installed the tool decides (receipt → ownership; 999.8). A native or os-package owner never yields argv. Two receipts claiming one path → both rows refuse unless both are selected (draw.io; or delete `drawio-cli`, O6). `plan_uninstall` (`uninstall.py:56-97`) becomes `download.artifact_paths(method)`, shared with `install_download` (F7, `bin_name` honored). Paths are evidence and are never authority.

**Deletes (~ −300):** `classify_tools`, `ToolRow`, `OwnerHint`/`OwnerLabelHint`, `_manager_hint`/`_managed_hint` (`uninstall.py:100-339`), the three `setup.py:807-868` closures, `ownership._own_script_install` (`:1436-1444`), and the native commands in `_REMOVAL_COMMANDS` (`ownership.py:1374-1377`).

### 4.4 Per-OS/arch variation: only where an audit proved a gap

| Proven gap | Resolution | Not doing |
|---|---|---|
| macOS dmg-only artifacts (Toolbox, kitty) — E 11 | Toolbox: cask (exists). kitty: allow the `script` method on macOS (data, E fix 8) | `dmg` kind |
| `app` kind has no `{ver}`; pinned URLs downgrade (draw.io 31→32, Sublime) — E NEW 1 | `u` refused for `app` when `version.latest is None` ("pinned; update outside or re-pin"); re-pin data with `# Verified` | `app {ver}` templating |
| Alacritty on immutable needs Distrobox — 999.11 | open decision O5 (rec: stays UNAVAILABLE with its reason) | a `distrobox` kind |
| Homebrew Intel Tier 3 — C G13 | data: `arch=["arm64"]` on macOS brew methods that refuse on Intel (podman); brew `bin_dir` arch split (C fix 8). Source builds elsewhere are slow but work | an Intel kind/flag |
| Linux arm64 asset gaps (jless, broot macOS amd64, Toolbox arm64, delta Intel) | data: `arch` gates and URLs (D/E fixes) | – |

---

## 5. Receipt format

**Path:** `~/.local/state/tools-installer/receipts/<tool_id>.json`. It sits next to `settings.json` (`settings.py:40-41`). The one-file-per-tool layout means no read-modify-write and no cross-tool lock.

```json
{"v": 1, "tool": "rg", "at": "2026-10-13T12:00:00Z",
 "method": {"kind": "github_release", "key": "sha256-of-canonical-params"},
 "package": null,
 "artifacts": [
   {"path": "~/.local/opt/rg", "type": "dir"},
   {"path": "~/.local/bin/rg", "type": "link", "target": "~/.local/opt/rg/rg"},
   {"path": "~/.local/bin/yq", "type": "file", "sha256": "…"}],
 "smoke": "ok",
 "hooks": {"rtk-register": ["claude", "codex"]}}
```

| Aspect | Rule |
|---|---|
| Written | after a method succeeds and before `postinstall`/`post_install` (`engine.py:162`); on update/repair/reinstall, rewritten; `hooks[...]` updated after each register/unregister. One writer: `installer/receipts.py` (~60 lines: `read`, `write`, `matches`). `receipts.py` is the only new module; `atomic.py` is the precedent for a small, single-purpose module |
| Atomicity | `atomic_write_text` (`atomic.py:56`). A crash between the method and the receipt → the tool is present but unproven, which fails closed |
| What per kind | download/app: `artifact_paths` actually created (dir, link target, sha256 for raw files). script: the declared `paths` that exist after the run. brew/cask/uv/pnpm: `package`. native/skill/host_setup: **no receipt** (we ran nothing, or only a handoff) |
| Proof at removal | link → `readlink == target`; file → sha256 equal; dir → `is_dir()` and not a symlink. A mismatch removes that artifact from the plan and adds the reason "changed since install — not removed" |
| Removal | delete matched artifacts, then the receipt. A failed delete keeps the receipt |
| Health use | BROKEN when an artifact is missing or changed while the tool is otherwise present. MISCONFIGURED from `hooks` (§6) |
| Migration (installed before receipts) | **Never delete unproven.** (a) Archive kinds: layout proof (`~/.local/bin/<bin>` resolves to a regular file inside `opt_dir(<bin>)`, D C2) counts as L2 proof (O2). (b) Everything else (raw files, scripts, managers): no removal; the row says "installed before receipts or by someone else — found at <path>; reinstall with `r` to adopt, or remove it yourself". `r` REINSTALL writes the receipt. CLI `make uninstall --yes` removes only proven plans |
| Not recorded | config the vendor writes outside `paths`; rc edits (suppressed upstream instead: `UV_NO_MODIFY_PATH`, `--no-modify-path`, `CODEX_NON_INTERACTIVE`) |

---

## 6. Configure / re-sync trigger model

| Step | Mechanism (existing seam) | Triggers | Health signal | Reverse |
|---|---|---|---|---|
| Agent-host registration (codegraph, rtk, graphify, herdr-integrations) | `POSTINSTALL_HOOKS` values become `(register(method, runner, hosts), unregister(…))` (`postinstall.py:277-281`). Hosts = `present_harnesses` ∩ the hook's own id map (`_CODEGRAPH_TARGETS` …) | install/update/repair; RECONFIGURE; **automatically at the end of any plan run that installed a harness**, for present hook tools, new hosts only | MISCONFIGURED: supported∩present − `receipt.hooks[name]` | Uninstall runs `unregister(receipt hosts)` first (`codegraph uninstall --keep-cli`, `rtk init -g --uninstall`, `graphify <host> uninstall`, `herdr integration uninstall`) |
| One agent-host list | **delete** `_AGENT_HOST_IDS` / `present_agent_hosts` (`postinstall.py:26-46`); use `skill_lifecycle.present_harnesses` (`:234`) everywhere | – | – | – |
| Login shell | `post_install = ["set_login_shell"]` (unchanged) | install; RECONFIGURE | note only (chsh absent by design) | – |
| Shell init (starship, direnv, zoxide, fzf, fnm-brew, volta-brew) | **implement** `source_shell_init` = enable the tool's `TweakBundle` (one bundle per tool in `tweaks.BUNDLES`, `requires=(cmd,)`, body guarded `command -v X >/dev/null &&`). It is sensitive, so it is asked (O11) | install (asked); later from Policies | **none** (a declined customization is not a health state) | tool removal disables its bundle (existing tweak sweep) |
| First-run data (tealdeer) | hook `tealdeer-cache` → `tldr --update` | install, update | – | cache in `config_paths` |
| Terminal default shell | `sync_terminal_shells` + **`write=False` dry run** (`terminal_shell.py:383`) | any plan row in {INSTALL, REPAIR, REINSTALL, UPDATE, RECONFIGURE} ran (replaces `wizard_app.py:2960`); Policies OMZ toggle (existing) | MISCONFIGURED on kitty/WezTerm | existing revert |
| `SHELL` inside kitty/WezTerm | kitty `env SHELL=<zsh>`, WezTerm `set_environment_variables` in the same owned region | as above | part of the dry-run drift | existing revert |
| git config (delta, difftastic), completions, desktop entries, services | handoff lines in the install summary | – | – | listed in `uninstall` text |

**Keep / delete / ask:** default keep. The Uninstall confirm shows a "delete config too (d)" choice when a selected row has `config_paths`. CLI `--yes` never deletes config. `~/.cursor`, `~/.gemini`, `~/.claude`, `~/.codex` are never deletable (the validator in §4.2).

**Known limit, recorded and not solved:** a host the user unregistered by hand gets re-registered by the next update of that tool. Receipts only record what we did (F rtk). `shortcut:` comment at the hook dispatch.

---

## 7. Screen lifecycle

Adopted from G "Consolidated target". Only the deltas and their evidence are listed.

| Change | Code | Forks removed (G R2 #) |
|---|---|---|
| Neutral root `Screen` (empty, not navigable); all six views `install_screen`'d | `wizard_app.py:2494-2511`, `get_default_screen` `:2670-2674` | 1, 2, 6 |
| `show_view`: `leaving.clear_transient()` for **any** `AppScreen` → pop if a view is on top → `push_screen(view)` → `view.enter_view()` | `:2676-2712` | 3, 5, 7 |
| `_navigable`: `self.screen in self._views.values()` | `:2720-2726` | 4 |
| `AppScreen.enter_view()` default → `self.state_refreshed()`; `state_refreshed()` default no-op; `clear_transient()` default `self.status.clear()` | `ui_common.py:321-355` (+~15) | – |
| One app-level full-catalog refresh worker (§2) | `UnifiedApp` | 8, 9 |
| `execute` required on every route (F2): `_build_app` builds `ExecuteInputs` | `setup.py:1295,1324-1331,1351-1356,1441-1447`; `wizard_app.py:2791,2910` | 10 |
| `ToolBrowser.reload` prunes selections that are no longer selectable; `selected_ids` filters on selectable | `tool_browser.py:215-218,325-331` (+3) | F4, 999.1(a) |
| **Uninstall = projection of `ToolState`**: (1) removable (`removable.level` set) + environment levers; (2) managed elsewhere: present with no proof, with `removable.hint`; a BROKEN row says "reinstall it from the catalog to repair; nothing to remove here"; (3) nothing to do: MISSING + UNAVAILABLE | `wizard_app.py:876-881,1145-1159,1238-1352` | G R3; deletes `_pending_status` (`:943-952,1172-1186`) and `_resync`'s precedence machinery |
| Removal on a worker with "Removing…" | `wizard_app.py:1467` | F16 |
| Policies: `enter_view` re-reads `is_active()`; live prerequisites (`missing_requires_now` bound to `state_of`); DRIFT = `owned() and not is_active()` | `wizard_app.py:1638-1640`; `policy.py:132-164,441-444` | F3, F8, AR-08 |
| Doctor: same lifecycle; **delete** the hidden `a` | `wizard_app.py:292` | F17 |
| Doctor findings → `ToolState.reasons` (pnpm missing/unhealthy/incomplete) | `pnpm_globals.py:172-178` | pending todo (Doctor half) |

**Marks:** one `health_cell(state) -> Text` and one `HEALTH_LEGEND` in `catalog_tui.py`, beside `_LEGEND` (`:277`). Catalog Inst, the Uninstall Health column and the Execute review all use it. Legend: `✓ ok · ↑ update · ≈ config · ! broken · ○ missing` (~45 chars). It replaces "✓ installed · ○ missing" inside the 78×3 budget pinned by tests. The focused-row detail bar prints `reasons` and `unconfigured` ("not registered for codex — select and enter to reconfigure").
**"Will be reinstalled":** the Execute review renders one table (`health_cell` · tool · disposition text · reason, with dragged rows indented under their dependent). An OK row shows `skipped — already current (r: reinstall)`; after `r` it shows `will be reinstalled`. BROKEN shows `will repair (reinstall)`; MISCONFIGURED shows `will reconfigure: register rtk for codex`. The summary uses the same words.

Keep three tier instances and the six number keys (G; not F10-ultra).

---

## 8. Milestone v0.50.0 "Truthful lifecycle": phases

Order and dependencies: P1 → {P2, P3}; P3 → P4 → P5; {P3, P5} → P6; {P4, P6} → P7; {P6, P7} → P8; P9 last. P2 and P3 can run in parallel.

| # | Phase | Ships | Deletes | Success criteria (each one an automated test unless marked) |
|---|---|---|---|---|
| **P1** | Stop the bleeding (hotfix; can start now) | H1–H6 (§10); `start_new_session=True` for install/update children (E gap 2); CI green on both OSes (999.7's 5 failures: bash 3.2 `mapfile`, Rich wrap, `/usr/bin/sh time`, injected `systemctl`, deterministic race test); PR check required (**user**: branch protection); non-UTF-8 `settings.json` (B 13 WR-06, `settings.py:55`); F2 `execute` required; Sublime host repair note | `test_accepting_the_catalog_without_execute_still_exits_with_ids` (`tests/test_wizard_app.py:7184`) | link-to-dir member raises `ExecutorError`, and a reinstall over an existing link-to-dir leaves the inner file untouched (scratch HOME); graphify hook writes nothing into the cwd (HOME-sandbox probe asserting an empty cwd); `run_uninstall(confirm=yes)` deletes 0 paths for a uv-tool ruff symlink and the shared drawio file; rc writers leave the original intact on an injected write failure; `clean_rc_duplicates` refuses a file changed after preview; a worker exception → red status and exit 1; a failed update → exit 1; link-mode change re-applies an active ban (aliases present in the new mode's rc, absent from the old); CI green on ubuntu + macOS |
| **P2** | Registry truth and drift guard | all data fixes from C/D/E/F (except Sublime, done in P1); `METHOD_PARAMS` with unknown-key rejection; `cli_name` honored; required `# Verified YYYY-MM-DD` test; `make verify-registry` (assets/members/checksums against the latest release, read-only; a weekly CI job is O12); GitHub API `digest` sha256 fallback in `download._resolve_target` (X5/C5); install-time smoke; launch with `uv run --no-dev` (D C1: `install.sh:88`, Makefile); macOS stub constant `{"/usr/bin/java"}` (C G1); version parser fixes (B 15 WR-02 `versions.py:54`; lazygit `version=`; procs quotes) | `managed-download` probe; `drawio-cli` (if O6) | a load test rejects an unknown key (fixture); every `[[tool]]` has `# Verified`; `verify-registry` flags the difftastic pre-fix template (fixture); 50 → 0 unverified github_release methods where GitHub exposes a digest; `parse_version('-1') is None`; ruff resolves its real owner under `make setup` (container); smoke failure falls to the next rung (fake binary exiting 127) |
| **P3** | One tool state with health, plus receipts | `Health`, `ToolState`, `tool_health`, one-swap publish, `state_of`, `has_brew` re-read, implicit `~/.local/bin` presence, `receipts.py` writer/reader (all executors), archive layout proof, uv owner dir = `uv tool dir` (X4), redirect-shim look-through + volta owner (C G5), unresolved-path version probe (E gap 3), native probe memo (WR-04), host_setup owner kept (WR-06), skill partial/duplicate reasons (F X7), catalog Inst via `health_cell`, legend | `_ownership`/`_statuses` maps and their raced merge (`version_status.py:751`); `_present`; `_BROKEN_MARK`; `set_installed`; per-tier copies | parametrized `tool_health` table (every evidence combination → state, precedence, reasons); a raced pass publishes nothing (deterministic barrier, AR-05); each Health glyph on each tier (system/user/ai); legend fits 78×3; a receipt is written on install, update and repair for download/app/script/manager kinds; a mismatched link target → not removable; graphify (uv) resolves owner uv; installing brew in-session makes colima installable without restart |
| **P4** | Install plan with dispositions | `Disposition`, `PlanRow`, `plan()`, `execute_plan()`, `force_ids`, the `r` key, the WAIT gate, the review table, the outcome summary, retained selection, `esc` keeps the selection, CLI `run_wizard` on the same plan, exit codes from outcomes | `_classify_selection`, `_update_targets`, `_preflight_prompt`, TUI `render_audit`, `audit.py`, `_install_state_changed` | G probe cases A–I as tests with the new text; per tier including system: missing → "will install"; current → "skipped … (r: reinstall)", `r` → "will be reinstalled"; broken → "will repair"; outdated brew → "will update"; outdated dnf → "skipped — managed by dnf"; dragged present dep → "already present" under its dependent; `a` on an all-installed tier runs nothing; summary words = review words; `--all --yes` on a host with an outdated tool updates it and exits 0; a failed row exits 1 |
| **P5** | One screen family | §7 in full: neutral root, push-all, enter-after-push, one refresh owner, status cleared on leave, Uninstall projection + Health column + "delete config too", F4 prune, F16 worker, Policies `enter_view`/live prerequisites/DRIFT, Doctor lifecycle, drop `a`, Doctor findings → reasons, first-run link pick re-renders Doctor (B WR-04), macOS prune truthfulness (A #7) | forks 1–10; `OwnershipRefreshed`; `_pending_status`; `_resync` precedence; `classify_tools` + closures; `_own_script_install`; the per-screen workers | **matrix**: source mutation {install close, `u` on each tier, Uninstall removal, Policies toggle, Doctor `r`} × target view {system, user, ai, Uninstall, Policies, Doctor}: the target shows the new state on next entry and immediately when visible; first entry to every view keeps a status written during entry; every view clears its status on leave; a removed tool's row moves to "nothing to do", its selection is pruned, and every tier shows `○`; Uninstall never names a manager for an unknown owner; a BROKEN row says "reinstall … to repair"; Uninstall removes the ban → Policies OFF on entry; installing `watch` unblocks the docker tweak; Doctor `a` is inert |
| **P6** | Method lifecycle contract | §4: script `paths`/`remove`/`update`, `writable_prefix` preflight, native rungs → handoff (O1), L1 removal with a receipt (O3), `config_paths`, `removal_plan`, `u` refused for pinned `app`, pnpm group warning, native hints without commands, data recipes for the 14 script tools + pi; container e2e harness gets **leftover checks** (A #3: a file listing before/after, not the exit code) | `plan_uninstall` as authority; `_REMOVAL_COMMANDS` native entries; the 4 dead `post_install` names; `Tool.source/owner` | per kind × per direction: install → receipt → Uninstall removable → removal leaves zero receipt paths (scratch HOME); a foreign file at a declared path is never deleted; `opencode` removal runs `opencode uninstall --keep-config --keep-data` (fake runner); `u` on OMZ runs `$ZSH/tools/upgrade.sh`, on SDKMAN `sdk selfupdate`; brew bootstrap with an unwritable prefix → MANUAL handoff, zero `sudo` argv anywhere (grep test over the executors); draw.io macOS CLI lands as `drawio` |
| **P7** | Configuration as a lifecycle step | §6: reversible hook pairs, `receipt.hooks`, an automatic re-sync when a harness is installed, one host list, graphify global form (if not already done in P1), rtk opencode/cursor gate fixes (F rtk), codegraph `--yes` side effects documented, `source_shell_init` + 6 bundles, `tealdeer-cache`, terminal dry run + `SHELL`, RECONFIGURE end to end | `_AGENT_HOST_IDS`, `present_agent_hosts` | install codex with rtk present → `rtk init` for codex runs once, `receipt.hooks` gains codex; remove rtk → `rtk init -g --uninstall` for the recorded hosts; kitty config without the region → `≈`, RECONFIGURE writes it and `SHELL` (scratch HOME); starship install with "yes" → bundle ON, declined → no row state; selecting a current zsh no longer promises a step that never runs (G case G) |
| **P8** | Onboarding through the skill, and e2e | herdr (binary, `herdr-integrations` hook, skill pack), Alacritty per O5, skill-judge on the onboarding skill (updated for §4 params), full container e2e with leftover checks on Fedora, Debian, Arch | – | herdr: install → integrations for present hosts → uninstall → `herdr integration status` clean (container); skill-judge score recorded; e2e: install all → rerun all = all SKIP → uninstall all → leftover list ⊆ the documented `config_paths` (**3 distros**); a human UAT on the real host (999.7: Owner on every tier after install, ✓ cleared after Uninstall) |
| **P9** | Lean | F11 agent policy modules + tests; F12 `_build_app` → `installer/compose.py` under pyright/coverage; F13 split `wizard_app.py` + drop review-history comments; F14 modals; dead Message classes, **keeping** epochs (AR-04); G #9 questionary chooser; F15 only where an epoch is not needed | ≈ −2,000 prod lines (estimate from F/G) | full suite + `make validate` green; coverage gate includes `compose.py`; CLI `--all/--categories` tests unchanged |

### 8.1 Mapping: backlog, todo, deferred-and-forgotten → phase

| Item | → | Note |
|---|---|---|
| 999.1 dispositions, retained selection, (a) staged survives Uninstall, (b) reinstall | P4; (a) → P5 prune; (b) → P4 `r` | |
| 999.2 receipts | P3 (format, writer, L2 proof); P6 (L3 `paths`) | |
| 999.3 per-OS/arch artifacts | P2 data + §4.4; **no new kind** | narrowed (B, AR-07) |
| 999.4 terminal `SHELL` + "already" re-sync | P7 (SHELL per O4) + P4 (trigger) | |
| 999.5 skill-judge onboarding skill | P8 | |
| 999.6 one row state | P3 + P5 | |
| 999.7 CI red, UAT 2–4, 9050446 review, gap plans 16-17..19 not re-audited, human checks discharged by automation | P1 (CI); P8 (human UAT, real-host re-check); secure/validate re-audit of 16-17..19 → P1 (process task) | |
| 999.8 per-method removal | P6 | |
| 999.9 F5, F2 → P1; F3, F8, F16, F17 → P5 | | |
| 999.10 screens → P5; lean → P9; `RowsScreen` **dropped** (G) | | |
| 999.11 herdr, Alacritty | P7 (hook shape) + P8 | |
| todo `2026-09-16` dangling pnpm shim in Doctor | P5 (Doctor reads `reasons`); catalog half already done | close after P5 |
| REQ-manager-drift-alerting | **drop**: the off-policy note (`≠ policy`, B 16 D-01) already says "another manager owns it" | update REQUIREMENTS when the milestone opens |
| A Ph4 npm subcommand allowlist | **drop**, unless the user asks: no reported need | O13 |
| A Ph4 pi outside the pnpm residual set; replay drops `--ignore-scripts` | P3 (Doctor reads inventory, not `kind="node"`); the replay flag → P6 | |
| A Ph5 T-05-22 pnpm group removal | P6 warning | |
| A Ph6 SC#3 `# Verified` unenforced | P2 | |
| A Ph7 T-07-14 unknown keys / draw.io `cli_name` | P2 | |
| A Ph7 T-07-15 `has_brew` frozen | P3 | |
| A Ph8 antigravity recommends/hooks | P7 (one host list makes agy reachable to hooks that support it) + P2 data | |
| A Ph9 D-01 hook re-trigger | P7 | |
| A Ph12 Doctor `r` skips invalidate | P5 (single refresh owner) | |
| A Ph12.2 agent_policy dormant | P9 delete | |
| A Ph12.3 e2e stale, exit-code-only uninstall, Debian/Arch, Apple Silicon | P6 harness, P8 run; Apple Silicon **drop** (no macOS host in CI scope; O12) | |
| A Ph12.4 graphify NEVER | P1 | |
| A Ph12.4 audit depth (2 rows) | P8 (skill requires per-row evidence) | |
| A #7 macOS prune runs from the checkout; ON = plist exists | P5 (Policies truth), macOS-unverified | |
| B 13 WR-01 crash → green Done/exit 0 | P1 | |
| B 13 WR-03 `esc` drops the selection | P4 | |
| B 13 WR-04 first-run link pick, stale Doctor | P5 | |
| B 13 WR-05 link mode strands policies | P1 | |
| B 13 WR-06 non-UTF-8 settings | P1 | |
| B 13 IN-08 unbounded RichLog | P9 (`max_lines`, 1 line) | |
| B 13 headless `--all` second engine | P4 | |
| B 14 IN-01 headless silent skip; exit code ignores updates | P4 / P1 | |
| B 14 IN-03 dead field | P6 delete | |
| B 14 IN-01 silent explicit "No" | **drop** (accepted asymmetry) | |
| B 15 WR-02 version fabrication | P2 | |
| B 15 WR-04 native probe memo; WR-06 host_setup owner; IN-05 rpm_ostree kinds | P3 | |
| B 15 WR-07 `_managed_download` | P2 | |
| B 15 WR-08/09 source-scrape tests | P9 (AR-11) | |
| B 15.1 IN-02/03/05 | IN-03 → P3 (raced pass); IN-02/05 → P9 or drop | |
| B 15.2 IN-01/04/05; 15.3 IN-01..04; 15.6 IN-01..04; 15.7 MEDIUM-02 | **drop** (info-level) except 15.7's third XDG resolver copy → P9 | |
| B 15.4 D-04 volta attribution | P3 | |
| B 15.4 IN-01/02, IN-03, T-15.4-22 | P3 (one swap); T-15.4-22 is gone once Uninstall reads `state_of` with CHECKING | |
| B 15.5 template ROADMAP entry; chsh text blames ostree | doc → at milestone open; wording → P7 | |
| B 15.6 CR-01 half (`omz.write_plugins` hardcodes `$HOME/.oh-my-zsh`) | P7 | |
| B 15.7 IN-08 (`--global` unit), IN-02 half | **drop**; needs a live host with no current report | |
| B 15.8 stale disposition; STATE/ROADMAP drift | bookkeeping at milestone open (`/gsd-health`) | |
| B 16 implicit bin dir | P3 | |
| B 16 D-03/D-04 migration promise ("not available yet") | **drop the promise**: reword `update.py:296`, `catalog_tui.py:923` in P4 | O8 |
| C/D/E/F data fixes | P2 (Sublime member in P1) | |
| C G2 privilege preflight; G6 shell init; G7 latest for scripts; G8 vendor update; G9 vendor rc edits; G10 never-remove; G11 services; G12 unzip/zip | G2 → P6; G6 → P7; G7 **cut**; G8 → P6; G9 → P2 data (suppress at source) + P6 `paths`; G10 → P6; G11 **cut** (handoff); G12 → P2 (`requires` + a preflight message) | |
| D C3/C4 integration + config refs | C3 → P7; C4 **cut** (gitconfig refs listed in `uninstall` text) | |
| E 9 desktop entries; E 10 keybindings | **cut** (except removal via `paths`); keybindings → P8 per tool, asked | |
| F X2/X3/X6/X9 | X2 → P7 (receipt-based, no MCP parsing); X3 → P7; X6 codegraph self-upgrade → `paths` includes `~/.codegraph/versions` (P6); X9 → P7 docs | |

---

## 9. Cut / not doing, and open decisions

### 9.1 Cut (ultra)

| Cut | Because |
|---|---|
| `RowsScreen`, a single-instance catalog | G; keeps the 6 number keys |
| New method kinds (dmg, pkg, AppImage-root, distrobox), `app {ver}` | §4.4: every proven gap closes with data or a `u` gate |
| `service` start/stop lifecycle | C G11: 4 tools, VM/root daemons; a handoff line is honest |
| Per-tool config policy enum | `config_paths` + one confirm toggle covers keep/delete/ask |
| git-config writer, completions on `fpath`, desktop-entry creation | new writers for convenience features nobody reported broken; handoff text |
| Latest-version source for script/SDKMAN tools (`version_repo`) | C G7: those vendors self-update; `u` still works on demand |
| Per-tool version-argv override | only dasel benefits; parser fixes cover lazygit/procs |
| MCP-config parsing as health (`--print-config`, `rtk verify`) | `receipt.hooks` gives the same MISCONFIGURED answer with zero subprocesses |
| REQ-manager-drift-alerting | the off-policy note already covers it |
| Off-policy migration ("moving it there") | no owner for 4 phases; reword the UI |
| Headless `--reinstall` flag | `make uninstall` + `--all` covers the rare need |
| Renaming `VersionRefreshService` | churn without behavior |
| Skill-pack `revision_policy` comparison | declared, never read; no reported need (F X7 notes it) |
| npm subcommand allowlist, Apple Silicon e2e, 15.x info-level items | no current report; listed in §8.1 |

### 9.2 Open decisions (each with a recommendation)

| # | Decision | Recommendation |
|---|---|---|
| O1 | Native rungs (dnf/apt/pacman): run `sudo` or hand off? | **Hand off** with the exact command. The TUI child has no usable tty (`run.py:235`) and P1 adds `start_new_session`. This matches the zero-sudo invariant in PROJECT.md |
| O2 | Archive layout proof for installs made before receipts: accept as removal proof? | **Yes, for archive kinds only** (a link into `~/.local/opt/<bin>/` that resolves to a file). Never for raw files or scripts |
| O3 | L1 manager removal: execute `brew/uv/pnpm` uninstall when a receipt proves we installed it? | **Yes with a receipt; a hint otherwise.** Native managers: never |
| O4 | Export `SHELL=<zsh>` inside kitty/WezTerm (999.4)? | **Yes**, inside the same owned region (reversible) |
| O5 | Alacritty on immutable hosts: Distrobox kind, cargo build, or stay unavailable? | **Stay unavailable** with its reason; revisit when upstream ships a Linux binary |
| O6 | `drawio-cli` row: delete it (F1 #3) or model a shared artifact? | **Delete**; set `drawio-desktop.audience = "both"` |
| O7 | A current tool on Enter: skip unless `r`, or reinstall by default? | **Skip unless `r`** (otherwise `a` means "reinstall the whole tier") |
| O8 | 16 D-04 "move to the catalog's manager": build or drop? | **Drop**, and reword the UI |
| O9 | After a mutation, render CHECKING (`…`) for ~5 s, or the previous state dimmed? | **CHECKING**: it is honest, and Enter waits correctly |
| O10 | Volta is unmaintained (C): keep it as the npm-ban route? | **Keep for v0.50.0**, attribution only; a migration (mise) is a separate milestone |
| O11 | Shell-init bundles at install: asked (default off) or on? | **Asked**, through the existing sensitive-action confirm |
| O12 | `make verify-registry` on a weekly CI schedule (it uses network + `gh`)? | **Yes, as a non-blocking scheduled job**; never in the PR gate |
| O13 | npm subcommand allowlist (A Ph4)? | **Drop** unless a project needs `npm run` under the ban |
| O14 | graphify: switch to the global `graphify install --platform <host>`, or disable the hook? | **Switch** if the HOME-sandbox probe proves the cwd untouched; otherwise remove `postinstall` from the entry in P1 |

---

## 10. Hazards that must be fixed first (P1), re-confirmed today

| # | Hazard | Current code (verified at `9490feb`, = `7861ced` for code) | Smallest fix | Test |
|---|---|---|---|---|
| H1 | Sublime: a link to a directory, then a reinstall self-loops and destroys the binary | `download.py:189` `chmod +x <member>` and `:190` `ln -sf`; same at `:403-404`; `apps.py:100` `ln -sf`. No `is_file()` check. Host: `~/.local/bin/subl -> ~/.local/opt/subl/sublime_text`, which is a directory (checked read-only today) | `if not binary.is_file(): raise ExecutorError`, then `atomic.replace_symlink(link, str(binary))` (`atomic.py:117`, never shells `ln`) at all three sites; registry `member = "sublime_text/sublime_text"` (E fix 1); one-line repair note: remove `~/.local/opt/subl` before reinstalling | scratch HOME: member is a dir → `ExecutorError`, nothing linked; a reinstall over a link-to-dir leaves the inner file untouched |
| H2 | graphify postinstall writes `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json`, … into the **cwd** | `postinstall.py:256-274`: `runner([graphify_bin, subcommand, "install"])` with no cwd; `run.py` sets none | O14: global form or remove the hook; never run the per-project form | probe: empty cwd stays empty, writes land only under the scratch HOME |
| H3 | Unproven removals, including under `--yes` | `setup.py:1358` `confirm = lambda _: True`; `app.py:548` `plan_uninstall` (name match only, `uninstall.py:56-97`) → `:594-595` `remove_paths`. TUI: `uninstall.py:298-309` REMOVABLE when `paths` is non-empty | interim (until P3 receipts): `removable` = archive layout proof only (O2); raw/app/shared paths → not removed and listed as "remove yourself"; the CLI filters through the same predicate | uv-tool ruff symlink, pip `yq` file, shared drawio file: 0 deletions in CLI `--yes` and TUI |
| H4 | Link-mode change strands enabled policies | `wizard_app.py:2179-2194` saves the mode and reports "ok"; the policies' rc paths are resolved per mode by closures (`setup.py:916-922`) | in `installer/` (rule 4): `active = [p for p in policies if p.is_active()]`; `p.remove()` each (old mode) → `set_link_mode` → `p.apply()` each (new mode); report per-policy failures | ban + tweak active, centralized→split: blocks absent from the old file and present where the new mode sources |
| H5 | Non-atomic rc writes; stale-index line deletion | `guards.py:554,564`, `tweaks.py:297,308` (`write_text` on rc files); `app.py:447` re-reads and applies indices computed before `confirm` (`:432-446`). Lower risk, same fix: shim files `guards.py:388,392,425,448,472`, `tweaks.py:254` | `atomic_write_text` (already used in `shellrc.py`, `omz.py:261`); keep the previewed text and refuse a file whose bytes changed (AR-02) | injected write failure → original intact; an edit between preview and confirm → refusal, file unchanged |
| H6 | A crashed run reports "Done." and exits 0 | `execute_screen.py:593` `try:` with only `finally:` (`:656`), `error=None` seeded (`:585`); `:953` green "Done."; `setup.py:1275` and `:1509` ignore `not_attempted` and update failures | `except Exception as exc: error = …; crashed = True`; status red "Failed"; exit 1 when `error`, `not_attempted`, or `update_errors` is non-empty (interim; P4 replaces it with outcome-derived codes) | a worker raising mid-run → red status, exit 1; a failed update → exit 1 |
| H7 (added) | Vendor script prompts on `/dev/tty` hang the TUI (codex) | `run.py:235` `stdin=DEVNULL`, no `start_new_session` | `start_new_session=True` for install/update children; registry `CODEX_NON_INTERACTIVE=1` | a fake script that opens `/dev/tty` fails fast instead of blocking |

---

**Not checked:** macOS behavior (every macOS claim comes from C–F); the real cost of the per-pass terminal dry run and receipt reads (estimated cheap; G measured 4.5–5.7 s for the existing pass); whether `graphify install --platform <host>` is user-scope (O14 makes it a P1 probe); whether `herdr integration install` edits agent main configs (999.11 says unverified).
**Risk:** until P1 lands, `make uninstall --yes` can still delete foreign `~/.local/bin` files, and reinstalling Sublime on this host further damages `~/.local/opt/subl`.
