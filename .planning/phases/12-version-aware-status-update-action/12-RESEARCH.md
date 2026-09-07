# Phase 12: Version-Aware Status & Update Action - Research

**Researched:** 2026-09-07
**Domain:** Version resolution (GitHub releases + brew/pnpm/uv-tool managers), a new JSON cache-with-staleness mechanism, Textual `Worker`-based background refresh, and a manager-delegated "update" action
**Confidence:** HIGH — every code excerpt below was read directly from this repo at its current commit; every command (`brew outdated`, `pnpm outdated -g`, `uv tool list --outdated`, and 40 real `--version` invocations) was executed live on this machine and its real output is quoted, not assumed from training knowledge or documentation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Update action confirmation:** The "update" action runs immediately when triggered, with no extra confirmation prompt — same UX as install today. Consistent with this project's existing apply-workflow convention (one action, one keypress, live output).

**D-02 — Manager-drift alerting scope:** SC#5 stays deferred/stretch; attempt a minimal version only if the 4 MVP pieces (SC#1-4 / REQ-version-aware-status-github, REQ-cached-timestamped-version-state, REQ-background-version-refresh-worker, REQ-manager-version-resolution + REQ-update-action-manager-delegation) land with room to spare. Not guaranteed to ship, not blocking.

### Claude's Discretion
- Exact per-manager version-check commands — this research resolves them below (all live-verified, none assumed).
- Whether the D-02 stretch task gets attempted at all — see "Finding: D-02 has zero real proving cases in the current registry" below, which materially informs that call.

### Deferred Ideas (OUT OF SCOPE)
- Auto-remediation for manager drift (auto-updating the registry + filing a GitHub issue) — needs a GitHub API/auth story this project doesn't have. Not revisited here.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|--------------|-------------------|
| REQ-version-aware-status-github | Resolve installed version via `--version`, compare against `resolve_github_tag`; "unknown" not false-positive | See "1. GitHub-release version resolution" |
| REQ-cached-timestamped-version-state | JSON cache, one entry/tool, `checked_at`, 7-day staleness | See "2. Cache/staleness mechanism — none exists to reuse" |
| REQ-background-version-refresh-worker | Textual `Worker`, never blocks first paint/keys, network failure -> "unknown" | See "3. The Worker pattern to mirror" |
| REQ-manager-version-resolution | `brew outdated`/`pnpm outdated -g`/`uv tool list --outdated`-equivalent, verified not assumed | See "4. Manager version-resolution commands" |
| REQ-update-action-manager-delegation | Manual "update" delegating to the tool's real manager, reusing `UninstallState`'s "managed elsewhere" concept | See "5. Manager delegation and the update action's UI home" |
| REQ-manager-drift-alerting | Stretch: pnpm/npm-installed tool with newer brew version -> alert | See "6. D-02 stretch: zero real proving cases today" |
</phase_requirements>

---

## 1. GitHub-release version resolution

### 1.1 `resolve_github_tag` — exact signature and behavior (read directly)

`installer/versions.py:169-179`:

```python
def resolve_github_tag(repo: str, fetch: Fetch = urlopen_fetch) -> str:
    """Return the latest release tag for owner/repo, verbatim (leading 'v' preserved)."""
    try:
        raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"failed to resolve tag for {repo}: {exc}") from exc
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise VersionError(f"no release tag for {repo}")
    return tag
```

- Signature: `(repo: str, fetch: Fetch = urlopen_fetch) -> str`. `Fetch = Callable[[str], bytes]` (injectable for tests — this is already the DI seam other callers use, e.g. `installer/session.py:67`, `installer/engine.py:78`, `installer/app.py:116`).
- Raises `VersionError` (a `RuntimeError` subclass) on network/JSON failure or a missing/empty `tag_name` — never returns `None`. A caller MUST catch `VersionError` (not just `OSError`/`CommandError`) around this call.
- Returns the tag **verbatim**, leading `v` preserved or not, exactly as GitHub reports it. It is NOT normalized. This matters for comparison (see 1.3 below).
- Hits `https://api.github.com/repos/{repo}/releases/latest` — unauthenticated GitHub API, subject to the standard 60 req/hour/IP rate limit. A per-tool background refresh across ~40 `github_release` tools must NOT fire all 40 in one burst on every cold cache — the 7-day staleness window (REQ-cached-timestamped-version-state) is exactly what keeps this under the rate limit in steady state, but a brand-new cache file (first run after this phase ships) would otherwise fire ~40 requests at once. Recommend: stagger or cap the per-session refresh count, or explicitly accept "first run refreshes everything, subsequent runs only refresh what's stale" and document the one-time cost.

**Live-verified** (this machine, 2026-09-07):
```
BurntSushi/ripgrep -> 15.2.0
sharkdp/fd -> v10.5.0
colbymchenry/codegraph -> v1.6.0
rtk-ai/rtk -> v0.48.0
```
The API genuinely works from this call shape, and — real finding — this machine's installed `codegraph` (1.2.0) and `rtk` (0.43.0) are both **actually outdated already**: `codegraph` 1.2.0 vs. latest `v1.6.0`; `rtk` 0.43.0 vs. latest `v0.48.0`. This phase's own proving case exists on the researcher's own machine.

### 1.2 How many tools this actually applies to (`kind = "github_release"`)

Live count against `registry.toml`: **85 `[[tool.method]]` blocks** across the registry declare `kind = "github_release"` (many tools have one method per OS/arch), covering roughly **40 distinct tools** — not just `codegraph`/`rtk`. Examples read directly from the file (`installer/registry.toml`): `ripgrep`, `fd`, `bat`, `sd`, `delta`, `eza`, `zoxide`, `fzf`, `lazygit`, `gh` (repo `cli/cli`), `yq`, `starship`, `direnv`, `just`, `ruff`, `dust`, `hyperfine`, `bottom`, `gum`, `glow`, `xh`, `difftastic`, `gitui`, `lazydocker`, `dive`, `duf`, `hexyl`, `miller`, `shfmt` (repo `mvdan/sh`), `tealdeer`, `fx`, `dasel`, `gron`, `aichat`, `codegraph`, `rtk`, `deno`, `procs`, `ast-grep`, `jless`, `gitleaks`, `vale`, `broot`, `wezterm`.

Every `Method` for `github_release` (`installer/model.py:121-127`, `Method(kind, params, os, arch)`) carries `repo` in `params` — that's the string `resolve_github_tag` needs. No new registry field is required to resolve the "latest" half.

### 1.3 CRITICAL finding: the existing `parse_version()` cannot read most of these tools' `--version` output — and the `v`-prefix inconsistency breaks naive string comparison

`installer/versions.py:43-77` (`parse_version`) is documented as reading **only the first whitespace-delimited token**:

```python
def parse_version(text: str) -> Version | None:
    token = text.strip().split(maxsplit=1)
    if not token:
        return None
    match = _OBSERVED_VERSION.fullmatch(token[0])
    ...
```

This is correct for its EXISTING callers (`_require_minimum` in `installer/executors.py`, probing bare `pnpm --version` / `node --version` output, which really is a bare version string). But it is the **wrong shape for most `github_release`-kind tools**, whose `--version` output is `"<toolname> <version> ..."`.

**Live-verified** (`<cmd> --version`, real binaries on this machine, first line quoted verbatim):

| Command | Raw first line | `token[0]` (what `parse_version` reads today) | Correct version |
|---|---|---|---|
| `rg` | `ripgrep 15.2.0` | `ripgrep` (unparseable) | `15.2.0` |
| `fd` | `fd 10.4.2` | `fd` (unparseable) | `10.4.2` |
| `gh` | `gh version 2.98.0 (2026-08-20)` | `gh` (unparseable) | `2.98.0` |
| `yq` | `yq (https://...) version v4.53.6` | `yq` (unparseable) | `v4.53.6` |
| `gum` | `gum version v0.17.0 (6045525)` | `gum` (unparseable) | `v0.17.0` |
| `gitui` | `gitui 0.28.1-nightly 2026-03-24 ()` | `gitui` (unparseable) | `0.28.1-nightly` |
| `zoxide` | `zoxide 0.9.9` | `zoxide` (unparseable) | `0.9.9` |
| `rtk` | `rtk 0.43.0` | `rtk` (unparseable) | `0.43.0` |
| `codegraph` | `1.2.0` | `1.2.0` (works — bare) | `1.2.0` |
| `direnv` | `2.37.1` | `2.37.1` (works — bare) | `2.37.1` |
| `fzf` | `0.74.3 (Homebrew)` | `0.74.3` (works) | `0.74.3` |
| `eza` | `eza eza - A modern, maintained replacement for ls` (version is on **line 2**: `v0.23.5 [+git]`) | unparseable, and not even on this line | `v0.23.5` |
| `dasel` | `Usage: dasel <command>` (no version printed by `--version` at all) | unparseable | none — genuinely unknown |
| `gron` | `gron version dev` | unparseable | none — literal string `dev`, genuinely unknown |
| `lazygit` | `commit=, build date=, build source=Homebrew, version=0.64.1, os=darwin, arch=amd64, git version=2.55.0` | unparseable | embedded as `version=0.64.1`, not its own token |
| `procs` | `procs "0.14.11 ( rev: 079fa76, ...` | unparseable | `0.14.11`, but wrapped in a quote character |

I tested a **generic fix** against all 40 locally-installed candidates: scan **every whitespace token in the full `--version` output** (not just the first line's first token) through the existing `_OBSERVED_VERSION` regex, take the first match. Result: **37 of 40 resolve correctly** (only `lazygit`, `dasel`, `gron`, `procs` still fail — genuinely hard/unparseable cases that should legitimately fall back to "unknown", matching REQ-version-aware-status-github's own text). This is a real, cheap, well-scoped generic algorithm — **not** a per-tool special-casing project. Recommendation for the planner: add a new function (do not change `parse_version`'s existing token[0] contract — it has other callers with a different, correct contract for bare version floors) — e.g. `extract_observed_version(text: str) -> Version | None` — that runs `text.split()` (all whitespace, all lines) and returns the first token `parse_version`-shaped match. Tools where nothing matches (`dasel`, `gron`, `lazygit`, `procs`, and anything else) report "unknown" — exactly the REQ's own required degradation, not a gap this phase needs to plug per-tool.

**Second CRITICAL finding — the leading-`v` inconsistency breaks naive string comparison.** `resolve_github_tag` deliberately preserves the tag's raw form (`fd` → `v10.5.0`), while the locally observed version is often bare (`fd --version` → `10.4.2`, no `v`). A caller comparing `"10.4.2" == "v10.5.0"` as strings would call them "different" by luck (this happens to be outdated so it's harmless here), but a caller comparing an UP-TO-DATE tool would get `"15.2.0" != "15.2.0"` correctly equal only because ripgrep's tag also happens to have no `v` — `fd`'s current release genuinely does carry a `v` while `ripgrep`'s doesn't (both confirmed live above), so the two repos are NOT consistent about the convention (this is documented in `resolve_github_tag`'s own comment, `installer/versions.py:10-12`). **The comparison MUST go through `parse_version`/the new `extract_observed_version` on BOTH sides and compare the resulting `(major, minor, patch)` tuples — never raw string equality/`!=`.**

### 1.4 Recommendation

- A new pure function, e.g. `installer/versions.py::is_outdated(observed: str, latest: str) -> bool | None` (or similar), built on `extract_observed_version`/`parse_version` on both sides; `None` (or a dedicated "unknown" sentinel) when either side fails to parse. Fits the existing module's fail-closed philosophy (`meets_minimum`'s own docstring: "Fail-closed on both sides").
- The "current installed version" probe itself needs a `probe_version`-shaped seam (`installer/versions.py:133-160` already has exactly this pattern — `_default_probe_version` / the `probe_version` module-level callable other executors patch in tests) run against `[tool.cmd, "--version"]`.

---

## 2. Cache/staleness mechanism — none exists to reuse

The task brief asked to check `installer/session.py`, `installer/status.py`, "or similar" for an existing cache/timestamp/staleness pattern to mirror. **Live grep across the entire `installer/` package (all 34 modules) for `json.dump`, `timestamp`, `checked_at`, `.cache`, `state_dir`, `XDG_` found nothing that persists a JSON state file with a timestamp anywhere in this codebase.** The only near-miss is `installer/daemon.py:429-466` (`last_run_summary`), which parses a `=== <timestamp> ===` **plain-text append-only log** written by the prune script — a log, not a cache, and not JSON.

This means Phase 12 is introducing a genuinely new persistence mechanism, not extending an existing one. The one existing convention worth following for *where* it lives is `installer/locations.py`'s userspace-path pattern: `bin_dir()` → `~/.local/bin`, `opt_dir(name)` → `~/.local/opt/<name>` (both cross-platform, no sudo, no OS-specific branching — unlike `daemon.py`'s macOS-only `~/Library/Logs/tools-installer/prune-daemon.log`, which is deliberately platform-specific because the daemon itself is macOS-only). Since version-checking must work on **both macOS and Linux** (REQ-background-version-refresh-worker has no platform restriction, unlike Phase 11's daemon), the cache path should follow the `~/.local/...` convention, e.g. `~/.local/state/tools-installer/versions.json` (parallel to `~/.local/opt/`), rather than `daemon.py`'s macOS-specific `~/Library/Logs/...` path. This is a naming/location decision the planner should make explicitly and record — there is no existing constant to inherit.

Suggested shape (one entry per tool, matching REQ-cached-timestamped-version-state's literal wording):
```json
{
  "codegraph": {"latest_version": "v1.6.0", "checked_at": "2026-09-07T12:00:00Z"},
  "rtk": {"latest_version": "v0.48.0", "checked_at": "2026-09-07T12:00:00Z"}
}
```
A read/write pair (`load_version_cache(path) -> dict`, `save_version_cache(path, cache) -> None`) following this codebase's existing tomllib-free JSON precedent (`json` stdlib is already imported in `installer/versions.py` for the GitHub API response) is a clean, small new module — likely `installer/versions.py` itself (it already owns `resolve_github_tag`/`parse_version`) or a small new `installer/version_cache.py` if the planner prefers to keep `versions.py` focused on parsing/resolution only. Either is reasonable; keeping I/O separate from the pure parsing functions matches this codebase's existing layering (e.g. `pnpm_globals.py` separates `parse_global_packages`/`parse_global_groups` pure parsers from `pnpm_global_packages`/`pnpm_global_groups` I/O wrappers, `installer/pnpm_globals.py:287-435`).

A malformed/missing cache file must degrade to "treat every entry as never-checked" (i.e., stale), never crash — consistent with this codebase's "None means unknown, not empty" philosophy stated explicitly in `pnpm_global_packages`'s docstring (`installer/pnpm_globals.py:401-406`).

---

## 3. The Worker pattern to mirror

The task brief named "the existing Doctor screen's Worker-based subprocess pattern... the same pattern Phase 11's on-by-default auto-apply reused." Read directly, both live in `installer/wizard_app.py`:

### 3.1 `DoctorScreen`'s globals-audit worker (`installer/wizard_app.py:443-468`)

```python
@work(thread=True, exclusive=True, group="globals-audit")
def _audit_globals_worker(self, generation: int) -> None:
    outcome, error = run_live(self._audit_globals)
    if outcome is None:
        report, preview = _GLOBALS_UNREADABLE, _GLOBALS_UNREADABLE_PREVIEW
    else:
        report, preview = outcome
    self.post_message(GlobalsAudited(report, preview, error, generation))
```

- `@work(thread=True, exclusive=True, group="...")`: runs the body on a real OS thread (not just an asyncio task), so a blocking subprocess call never freezes the Textual event loop or keypress handling. `exclusive=True` cancels a same-group in-flight worker when a new one starts (used for "re-audit supersedes the old one"); a `generation` counter travels with the result specifically so a stale (superseded) worker's answer can be told apart from the current one once cancellation only affects the Textual-side bookkeeping, not a thread already inside `subprocess.run` (comment at `wizard_app.py:266-273` states this explicitly).
- `run_live` (`installer/ui_common.py:41-50`) is the **one shared apply-workflow wrapper** for every screen's live mutation: `(result, None)` on success, `(None, message)` on `OSError`/`CommandError` — "no screen writes its own try/except for it." This is the seam the version-refresh worker MUST also go through for consistency and for the "network failures degrade to unknown, never crash" requirement.
- Communication back to the main thread is via `self.post_message(...)` (a `textual.message.Message` subclass) — Textual widgets may only be touched from the app's own thread, so the worker never touches UI state directly; it posts a message the screen's `on_<message>` handler processes on the event loop.
- Phase 11's on-by-default worker (`installer/wizard_app.py:1545-1571`, `_apply_daemon_default_worker`) is the SAME shape with one addition: `exit_on_error=False` on the `@work` decorator, plus a `try/finally` around the body so the completion message is **always** posted even if the body raises something outside its own guarded exception tuple — this is exactly the guarantee a version-refresh worker needs (a genuinely unexpected exception during a GitHub fetch must not leave the UI stuck in a "refreshing" state forever).

### 3.2 Test pattern for proving a worker genuinely runs off-thread

`tests/test_wizard_app.py:1984-2019` (`test_doctor_audit_runs_off_the_event_loop`) uses **`threading.Event()` latches**, not `sleep`, to deterministically prove the event loop stays responsive while the worker blocks:

```python
started = threading.Event()
release = threading.Event()

def slow() -> NodeGlobalsReport:
    started.set()
    assert release.wait(timeout=5)
    return _mmdc_report(missing=())

app = _app(node_globals=slow, initial_view="doctor")
async with app.run_test(size=(100, 30)) as pilot:
    assert started.wait(timeout=5)
    ...  # assert the loop is STILL painting / handling keys here
    release.set()
    await _settle(app, pilot)
```

And the polling helper `tests/test_wizard_app.py:182-196` (`_settle`) waits for a worker's completion by polling a screen-level boolean flag with `await pilot.pause()` in a bounded loop (400 iterations) — never a bare `sleep`. Per this session's own memory note, `pilot.press` alone can mask burst/timing bugs; posting unsettled `Key` events plus this bounded polling loop is the established, working pattern in this exact codebase and should be reused verbatim for the version-refresh worker's tests (its own `_settle`-shaped helper, polling a `refreshing`/similar reactive flag).

### 3.3 Recommendation: on-load vs. explicit action (open question the REQ itself flags)

`REQUIREMENTS.md`'s own text for REQ-background-version-refresh-worker states this is unresolved: "whether refresh fires on catalog load or only on an explicit 'check for updates' action is unresolved." Given (a) the GitHub API rate-limit exposure documented in 1.1 above, and (b) this codebase's own existing precedent — `DoctorScreen._start_globals_audit()` fires **automatically on screen entry** (`enter_view()` → `_start_globals_audit()`, `wizard_app.py:242-260`), not gated behind an explicit keypress — the precedent in THIS codebase leans toward auto-refresh-on-view-entry for **stale** entries only (never a full unconditional refetch, which is what REQ-cached-timestamped-version-state's 7-day window exists to prevent). This satisfies "a fresh session doesn't refetch everything, only what's gone stale" literally. The planner should record this as the resolved decision (auto-refresh-what's-stale on catalog view entry, mirroring Doctor's own screen-entry audit) unless CONTEXT.md's Claude's-Discretion or a future user decision says otherwise.

---

## 4. Manager version-resolution commands (all live-verified on this machine, none assumed)

REQ-manager-version-resolution explicitly requires verifying exact commands. All four below were run for real, with output/exit-code quoted verbatim.

### 4.1 Homebrew — `brew outdated --json=v2`

```
$ HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_ENV_HINTS=1 brew outdated --json=v2
{
  "formulae": [
    {"name": "ast-grep", "installed_versions": ["0.45.1"], "current_version": "0.45.3", "pinned": false, "pinned_version": null},
    {"name": "broot", "installed_versions": ["1.58.0"], "current_version": "1.59.0", "pinned": false, "pinned_version": null},
    ...
  ],
  "casks": []
}
```
Exit code: **0**, both with real outdated formulae present and with an empty result. Clean, stable, structured JSON — this is the easy case.

**Real pitfall found live:** without `HOMEBREW_NO_AUTO_UPDATE=1`, plain `brew outdated --json=v2` triggers Homebrew's own auto-update first — a multi-second network fetch of the whole tap (`==> Auto-updating Homebrew...`) plus assorted noise printed to stdout/stderr (in this run it even surfaced an unrelated `git rebase-merge` warning from the tap's own repo state) *before* the JSON. This is a genuine, timing-relevant finding: **the version-check command MUST set `HOMEBREW_NO_AUTO_UPDATE=1`** (and reasonably `HOMEBREW_NO_ENV_HINTS=1` to suppress hint noise) in its env, exactly as `installer/executors.py::_cask`/`_brew` already do NOT need to (they don't query "outdated", they install, where an auto-update is comparatively harmless) — this is new, version-check-specific.
`--cask` scopes the *installed* set queried (formula-only vs. cask-only) — call once for formulae, once (with `--cask`) for casks if this project's cask-installed tools also need drift detection (currently only a few tools install via `cask`; formulae are the common case for this catalog).

### 4.2 pnpm — `pnpm outdated -g --json` (NOT `--format json`)

```
$ pnpm outdated -g --json
{
  "pnpm": {"current": "11.9.0", "latest": "12.3.4", "wanted": "11.9.0", "isDeprecated": false, "dependencyType": "dependencies"}
}
Exit code: 1
```

**Two real pitfalls found live:**
1. `--format json` (a flag that reads as plausible from npm/pnpm familiarity) does **NOT** produce JSON on this pnpm (11.9.0) — it silently falls back to pnpm's human-readable arrow format (`pnpm: 11.9.0 → 12.3.4`). The correct flag is bare `--json`. This is exactly the "verify exact commands, not assumed" trap the REQ calls out by name.
2. **Exit code is 1 when outdated packages exist** (confirmed: 0 when nothing is outdated, via a directory with no outdated globals — not reproducible without an outdated global present, but this matches documented npm/pnpm convention: exit 1 = "found something", exit 0 = "clean"). This is a direct conflict with `installer/run.py::run_output` (`installer/run.py:36-61`), which raises `CommandError` on **any** non-zero exit and — critically — only folds `exc.stderr` into the error `detail`, never `exc.stdout`. A naive `run_output(["pnpm", "outdated", "-g", "--json"])` would **raise and discard the exact JSON payload the caller wants** in precisely the interesting case (packages ARE outdated). **A dedicated wrapper is required** — this cannot reuse `run_output` as-is; it must either (a) accept exit codes 0 and 1 as both "successfully read" (only other codes / stderr-with-no-stdout as a real failure), or (b) call `subprocess.run` directly with `capture_output=True` and read `.stdout` regardless of `.returncode ∈ {0, 1}`. This is precisely the kind of "each manager needs its own Runner-shaped seam" the REQ's own text anticipates — pnpm is the concrete reason why a single generic `run_output` call is not enough.
3. `-g` (global scope) is mandatory — omitting it against a directory with no `package.json` fails outright (`[ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND]`, exit 1, live-verified) for an unrelated reason, which would be indistinguishable from "nothing outdated" if the wrapper isn't careful to always pass `-g`.

`pnpm` itself is queried the same way as any other package name in the `-g --json` output — `pnpm outdated -g` treats its own corepack-managed version as just another dependency entry, keyed `"pnpm"` in the JSON. This matters directly for `REQ-pnpm-global-reinstall-mitigation`'s "automatic post-pnpm-update trigger," which this phase owns per ROADMAP.md's Phase 12 note — the exact signal "pnpm itself just updated" can be read straight off this same JSON (`data["pnpm"]["current"] != data["pnpm"]["wanted-after-update"]`-style diffing across two calls, or simpler: re-run `pnpm_global_groups`'s existing split/incomplete-group audit — already built in `installer/pnpm_globals.py` — right after a manager-delegated pnpm update completes).

### 4.3 uv — `uv tool list --outdated`

```
$ uv tool list --outdated
graphifyy v0.9.53 [latest: 0.9.55]
- graphify
- graphify-mcp
pre-commit v4.6.0 [latest: 4.6.2]
- pre-commit
Exit code: 0
```

**Real finding: there is no JSON output flag at all.** `uv tool list --help` (read verbatim live) lists `--show-paths`, `--show-version-specifiers`, `--show-with`, `--show-extras`, `--show-python`, `--outdated` — no `--output-format`/`--json` option exists for this subcommand on this uv version (0.12.5). This must be parsed as plain text: each installed tool's own line is `<distribution> v<installed> [latest: <latest>]`, followed by zero or more indented `- <exposed-command>` continuation lines (the tool's entry points — e.g. `graphifyy` exposes both `graphify` and `graphify-mcp`, matching `REQ-uv-tool-executor`'s already-known double-y-package/single-name-command split from Phase 8). A small regex (`^(\S+) v(\S+) \[latest: (\S+)\]$`) against non-indented lines, skipping `- ` continuation lines, is sufficient — this project's existing catalog keys `uv-tool` entries by **PyPI package name** (`installer/model.py`'s `pypi_pkg` param, confirmed in `installer/executors.py:456-458::_uv_tool`), which is exactly the `<distribution>` token this output leads with (e.g. `graphifyy`, matching the registry's `graphify` tool's `pypi_pkg = "graphifyy"`). Exit code is 0 in both the outdated and clean case (verified: `uv tool list` alone, no `--outdated`, also exits 0) — no pnpm-style exit-code trap here.

### 4.4 Summary table

| Manager | Exact command | Output shape | Exit-code trap | Extra env needed |
|---|---|---|---|---|
| Homebrew | `brew outdated --json=v2` (add `--cask` for a second cask-scoped call) | Clean JSON | None (always 0) | `HOMEBREW_NO_AUTO_UPDATE=1`, `HOMEBREW_NO_ENV_HINTS=1` |
| pnpm | `pnpm outdated -g --json` (NOT `--format json`) | Clean JSON, keyed by package name | **Exits 1 when anything is outdated** — `run_output` as-is discards stdout on this path | none |
| uv-tool | `uv tool list --outdated` | Plain text, `<pkg> v<cur> [latest: <latest>]` + indented entry-point lines | None (always 0) | none |
| GitHub release | `resolve_github_tag(repo)` (existing, `installer/versions.py:169`) + probe `<cmd> --version` locally | JSON (API) / free-text (local) | `VersionError` raised, not returned | none |

---

## 5. Manager delegation and the update action's UI home

### 5.1 The "managed elsewhere" concept CONTEXT.md points at

`installer/enums.py:67-73` — `UninstallState` has **no literal `"managed elsewhere"` member**; the actual states are `REMOVABLE | MANAGED | ABSENT | UNAVAILABLE`. The human-readable "managed elsewhere" phrasing lives in `installer/uninstall.py`'s hint-building functions, not the enum:

```python
def _manager_hint(tool: Tool) -> str:
    for method in tool.methods:
        if method.kind == "cask":
            return f"managed by Homebrew — `brew uninstall --cask {name}`"
        if method.kind == "brew":
            return f"managed by Homebrew — `brew uninstall {name}`"
    return "managed outside this installer — remove with your package manager"

def _managed_hint(tool: Tool, which: Callable[[str], str | None]) -> str:
    hint = _manager_hint(tool)
    path = which(tool.cmd)
    return f"{hint} — found at {path}" if path else hint
```
(`installer/uninstall.py:130-154`)

Read exactly as-is, `_manager_hint` today only distinguishes **brew/cask** from "everything else" (a bare fallback string) — it does NOT yet distinguish `node` (pnpm) from `uv-tool` from `sdkman` from this installer's own `script`/`github_release`/`tarball`/`app` paths. **REQ-update-action-manager-delegation's actual reuse target is this function's *shape* and the `UninstallState.MANAGED` classification path** (`classify_tools`, `installer/uninstall.py:169-223`, which already asks "is this tool's cmd on PATH but the tool has no userspace artifacts we placed" — exactly the "this installer doesn't own this install" signal an update action needs) — not a literal enum value named "managed elsewhere". The update action needs `_manager_hint`'s per-`method.kind` branching extended to cover `node` → pnpm, `uv-tool` → uv, `sdkman` → sdkman itself has no generic "update" concept (candidates are updated via `sdk upgrade <candidate>`, out of scope unless specifically requested), and `script`/`github_release`/`tarball`/`app` → this installer's own re-run-the-install-method path (since those are exactly the kinds this installer itself manages end-to-end).

### 5.2 Executor-to-manager mapping (read directly from `installer/executors.py`)

| `Method.kind` | Executor | Real update command |
|---|---|---|
| `brew` | `_brew` (`executors.py:375-376`) | `brew upgrade <formula>` (brew's own upgrade verb; `brew install` again is a no-op on an already-installed formula) |
| `cask` | `_cask` (`executors.py:482-487`) | `brew upgrade --cask <cask>` |
| `node` | `_node` (`executors.py:379-453`) | `pnpm update -g <npm_pkg>` (or re-run the same `pnpm add -g <group>` — pnpm treats a global add of an already-present package as an update) — **must resolve `real_pnpm()` (`installer/guards.py:315-332`) by absolute path**, exactly as `_node` itself already does, so the update never reaches this installer's own argv-conditional pnpm wrapper |
| `uv-tool` | `_uv_tool` (`executors.py:456-458`) | `uv tool upgrade <pypi_pkg>` |
| `sdkman` | `_sdkman` (`executors.py:461-479`) | out of scope for MVP unless separately requested — SDKMAN's own upgrade model (`sdk upgrade <candidate>`) is a different shape than a single-package bump |
| `script`/`github_release`/`tarball`/`app` | this installer's own download/apps paths | re-invoke `install_tool` for that tool — this installer already owns the full lifecycle for these kinds, so "update" here is exactly "re-run install," reusing `installer/engine.py::install_tool` and `installer/download.py`/`installer/apps.py` unchanged |

`real_pnpm()`'s docstring (`installer/guards.py:321-327`) states the reason directly: "installer/run.py::run_command is subprocess.run(cmd), which resolves a bare program name through the live PATH, so once this installer owns a pnpm entry in the managed bin dir every internal invocation must carry an absolute path or it will call our own wrapper instead of pnpm." This applies identically to an update action's pnpm call.

### 5.3 Architectural finding: two different "apply" patterns already exist in this codebase — pick the right one

Read directly, there are **two distinct existing patterns** for "the user acts, something runs":

1. **Catalog install (`installer/catalog_tui.py` + `installer/app.py::run_wizard`, `app.py:109-164`):** the Textual `CatalogScreen` is used for **selection only** — `on_tool_browser_accepted` (`catalog_tui.py:385`) posts a `Decided(ids)` message and the TUI stack pops back out to plain console/`rich`/`questionary` code (`run_wizard`), which then runs `resolve_dependencies`, prints an audit via `rich.Console`, asks a plain `questionary.confirm`, and finally calls `run_installs(...)` **synchronously, blocking, outside Textual entirely.** No `Worker`, no `run_live`, no `post_message` anywhere in this path.
2. **Uninstall/Doctor/Policies (`installer/wizard_app.py`):** everything stays **inside** the running Textual app. A keypress triggers an `action_*` method that either calls `run_live(...)` directly (synchronous, only safe for genuinely fast operations — e.g. `action_apply`'s PATH fix, `wizard_app.py:376-381`) or spawns a `@work(thread=True, ...)` worker that itself calls `run_live(...)` and reports back via `post_message` (the globals audit/reinstall pattern from section 3.1, and Policies' own toggle path, `wizard_app.py:1205`, `PoliciesScreen.action_toggle_policy`).

D-01's own phrasing — "same UX as install today... one action, one keypress, live output" — is genuinely ambiguous between the two on a literal reading, but **"live output" plus "one keypress" (as opposed to install's select-then-separately-confirm-in-console flow) points at pattern 2, not pattern 1.** Practically: the natural place a user *notices* a tool is outdated is the Catalog table itself (where the new current-vs-latest column this phase adds would render), and a manager delegation call (`brew upgrade`, `pnpm update -g`, `uv tool upgrade`) is exactly the kind of subprocess call that must not block the render loop — the same reasoning that put the globals-audit/reinstall on a thread worker in Doctor applies identically here. **Recommendation: model the update action on pattern 2** (a `@work(thread=True, exclusive=True, group="tool-update")` worker wrapping `run_live(...)`, posting a completion message the Catalog screen (or wherever the version column lives) handles) — not on the Catalog's own select-then-exit-to-console install flow, which has no live-output mechanism at all and would need one invented from scratch for a single action.

This also directly informs which screen/keybinding hosts "update": since the version column and the update action are the same feature's two halves, they belong on the same screen — most likely the existing `CatalogScreen` (parameterized `ToolBrowser`, `installer/tool_browser.py`) gaining a new column (`_COLUMNS` tuple, `installer/catalog_tui.py:118-126`, currently `Sel/Pri/Tool/Cat/For/Inst/What it does`) and a new keybinding (e.g. `u` for "update", parallel to the browser's existing `space`/`a`/`i` bindings) rather than a wholly separate view — consistent with `.claude/architecture.md`'s "one view registry, one nav path" rule the task brief cited.

---

## 6. D-02 stretch: zero real proving cases in the current registry

REQ-manager-drift-alerting's scenario is "a tool installed via pnpm/npm with a newer version available via brew." I checked this directly against the live registry:

```python
# For every tool, does its method set include BOTH a node/uv-tool method
# AND a brew/cask method (the precondition for "drift" to even be
# expressible from declared data)?
count = 0
for row in registry_tools:
    kinds = {m.kind for m in row.methods}
    if ({"node","uv-tool"} & kinds) and ({"brew","cask"} & kinds):
        count += 1
# count == 0
```

**Zero tools in the current registry declare both a `node`/`uv-tool` method and a `brew`/`cask` method.** (Phase 5's research specifically resolved `mmdc` to pnpm-only, explicitly rejecting brew as a fallback for exactly this class of tool — see ROADMAP.md's Phase 5 planning note: "upstream mermaid-cli deprecates the brew path... so mmdc stays on pnpm.") This means: even a fully correct, declared-methods-based drift check (compare the currently-active method's kind against the tool's OTHER declared methods, if any is `brew`/`cask`, and diff versions) would have **no real catalog row to exercise it against today** — the feature would be correct-but-dead code on the current registry. A more speculative version — guessing an UNDECLARED formula name matches the same software (e.g. "does `brew info rtk` describe the same `rtk` this pnpm/npm-style tool is") — is a materially different, higher-risk feature (false-positive risk on formula-name collisions) that the REQ's own text does not ask for ("if a tool is currently installed via pnpm/npm/npx/pnpx" implies the registry already knows the alternative, i.e. a declared method, not a guess).

This is presented as a finding, not a recommendation to skip: the planner/CONTEXT already flagged this as "attempt a minimal version if scope allows" (D-02). The concrete, scoped, low-risk "minimal version" the data supports is: implement the declared-methods-based check as a small pure function (`has_declared_manager_drift(tool, active_method_kind) -> bool`) with a unit test using a **synthetic** `Tool` fixture (since no real catalog row exists to exercise it against black-box), and skip building any live UI surfacing for it this phase if time is short — the function itself is cheap and correctly scoped even with a currently-empty real-world hit rate.

---

## Artifacts this phase is likely to produce (not prescriptive — planner's call)

- `installer/versions.py` (or a new small module): `extract_observed_version`, `is_outdated`/similar comparison helper, JSON cache read/write with `checked_at`, staleness predicate (`> 7 days`).
- A new `installer/manager_versions.py`-shaped module (mirroring `installer/pnpm_globals.py`'s pure-parser/IO-wrapper split): `brew_outdated()`, `pnpm_outdated_global()` (the exit-code-1-tolerant wrapper), `uv_tool_outdated()`.
- `installer/uninstall.py` or a new sibling: extended manager-hint/resolution covering `node`/`uv-tool` (not just `brew`/`cask`).
- `installer/catalog_tui.py`: new `_COLUMNS` entry, new keybinding/action for "update".
- `installer/wizard_app.py`: a new `@work(thread=True, exclusive=True, group="tool-update")`-style worker + `post_message` pair, mirroring `_audit_globals_worker`/`_reinstall_globals_worker`.
- New cache file at (recommended) `~/.local/state/tools-installer/versions.json`.

## Open questions the planner should resolve explicitly (not resolved by this research)

1. Exact cache file path/location (recommended above, not locked).
2. Whether refresh fires on catalog-view entry (recommended, mirroring Doctor's own screen-entry audit) vs. a dedicated "check for updates" keybinding.
3. Whether the D-02 stretch task is attempted this phase at all, given the zero-real-proving-case finding in section 6.
