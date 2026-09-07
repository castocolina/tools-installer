---
phase: 09-postinstall-hooks-mechanism
reviewed: 2026-09-06T18:30:53Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - installer/app.py
  - installer/engine.py
  - installer/model.py
  - installer/postinstall.py
  - installer/registry.toml
  - installer/render.py
  - installer/session.py
  - tests/test_app.py
  - tests/test_engine.py
  - tests/test_model.py
  - tests/test_postinstall.py
  - tests/test_registry.py
  - tests/test_render.py
  - tests/test_session.py
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
  second_lane: codex-sol-high
status: fixed
---

# Phase 9: Code Review Report

**Reviewed:** 2026-09-06
**Depth:** deep
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Diff range `28df5e0..HEAD` (branch `gsd/phase-09-postinstall-hooks-mechanism`) was read
in full for all 14 listed files, then cross-checked against the collaborator modules the
new code actually calls or is called by at runtime: `installer/status.py::is_installed`,
`installer/locations.py::bin_dir`, `installer/download.py` (to confirm the binary the
`github_release` executor writes for `codegraph` lands at the exact path the postinstall
hook later invokes), `installer/deps.py::resolve_dependencies` (to confirm it never
reorders mutually-independent tools, which the hook's correctness implicitly depends on
for host-before-`codegraph` ordering), `installer/executors.py`/`tests/test_executors.py`
(the `SMOKE_CHECK_NAMES`/`SMOKE_CHECKS` precedent this phase's own code comments claim to
mirror), `setup.py` (confirms `run_wizard` is the only production entry point), and the
phase's own three-cycle cross-AI plan-review trail (`09-REVIEWS.md`) to avoid re-flagging
findings that process already surfaced and fixed before execution.

`make validate`-equivalent checks were re-run directly: `pyright`, `ruff check`, and
`bandit` all report zero findings on the seven touched `installer/*.py` files, and the
full suite (`pytest -q`, 1000+ tests) passes, including all new `test_postinstall.py`,
`test_engine.py`, `test_model.py`, `test_registry.py`, `test_render.py`, `test_session.py`,
and `test_app.py` cases added by this phase.

Every HIGH/MEDIUM finding recorded in the three prior cross-AI plan-review cycles
(`09-REVIEWS.md`) — Method-awareness of the hook signature, `is_installed`-based host
detection instead of bare `shutil.which`, the `try/except/else` exception-isolation
restructure, the `catalog`/`tools` threading through all three `Install` call sites in
`run_installs`, the absolute-path (not bare-name) binary invocation, and the `bin_dir`
type-safety normalization — was independently re-verified against the actual merged code,
not just the plan prose, and is correctly implemented exactly as that history describes.
No regressions were found in that ground already covered.

Two candidate findings were investigated and **ruled out**:
- `installer/postinstall.py::_CODEGRAPH_TARGETS` covers only 4 of the 8 target ids
  `registry.toml`'s own research comment says codegraph's real `--target` flag accepts
  (`claude, cursor, codex, opencode, hermes, gemini, antigravity, kiro`). This looked like
  a scope gap at first — `antigravity` in particular is a real catalog tool in this exact
  registry (`installer/registry.toml:1441`) and codegraph's CLI does support it as a
  target. But cross-checking `recommends`: `claude`/`codex`/`opencode`/`cursor-agent` all
  declare `recommends = ["codegraph", "graphify", "rtk"]` (Phase 8,
  REQ-recommends-wiring-agent-hosts) while `antigravity.recommends == ()`. The four wired
  hosts are exactly the four hosts this catalog already models as codegraph's companions;
  `hermes`/`gemini`/`kiro` have no catalog entry at all. Not a finding.
- Whether tools installed earlier in the *same* wizard run (e.g. `claude`) would be missed
  by `is_installed`'s `shutil.which` check if their bin dir isn't yet on the current
  process's PATH. Traced the actual priority values: `claude`/`codex`/`opencode`/
  `cursor-agent` are all `priority = "P0"`; `codegraph` is `priority = "P1"`.
  `session.order_for_install`'s stable sort guarantees every host is attempted (and, on
  success, has its binary placed) strictly before `codegraph`'s own `install_tool` call in
  every single wizard run, and `resolve_dependencies` never reorders tools with no
  `requires` relationship between them (confirmed in `installer/deps.py`). Not a finding.

No Critical/BLOCKER findings: no injection vector (the hook builds a plain argv list from
a closed, code-owned target mapping and a `bin_dir()`-resolved absolute path — never a
shell string, never a registry-supplied literal command, mirroring the `smoke` precedent),
no hardcoded secrets, and no crash reachable through the real (`run_wizard`-only)
production path, since that path always threads the full loaded catalog through
`run_installs`/`install_tool`. The two Warnings below describe real fragility and a real
test-coverage regression relative to this codebase's own established conventions, neither
of which is reachable through the current production call graph today but both of which
are one registry/catalog edit away from becoming live.

## Warnings

### WR-01: `_codegraph_mcp_register` indexes `tools[tool_id]` instead of `.get(tool_id)`, so any caller or future catalog subset missing one of the four hardcoded host ids gets a confusing generic crash message instead of graceful "not installed" handling

**File:** `installer/postinstall.py:76-78`
**Issue:** `_CODEGRAPH_TARGETS`'s four ids (`claude`, `codex`, `opencode`, `cursor-agent`)
are hardcoded string literals with no static link to `installer/registry.toml`'s actual
tool ids — nothing enforces they stay in sync. The lookup:
```python
present = [
    target for tool_id, target in _CODEGRAPH_TARGETS.items() if is_installed(tools[tool_id])
]
```
uses bare `Mapping.__getitem__`, so if `tools` (the caller-supplied catalog) is missing
any one of those four keys, this raises `KeyError('claude')` (or whichever id is absent).
This is reachable two ways: (1) `installer/engine.py::install_tool`'s own `tools` parameter
defaults to `None` and the call site does `tools or {}` — any direct caller of
`install_tool(codegraph_tool, platform)` (a documented, valid public signature) with the
default `tools=None` hits this immediately, since `{}` has none of the four keys; (2) a
future registry edit that renames or removes `cursor-agent` (this catalog was reshuffled
as recently as this same commit range's predecessor, "feat: refresh ai dev tool catalog")
would make this fire on every single `codegraph` install thereafter. The failure is
silently converted by `installer/engine.py`'s isolation boundary
(`except Exception as exc: warning = f"postinstall hook {tool.postinstall!r} crashed: {exc}"`)
into an opaque warning that only echoes the missing key's `repr()` (e.g. `crashed: 'claude'`)
with no indication the real cause is a missing catalog entry, not a `codegraph install`
failure. Today's only production caller (`installer/app.py::run_wizard`) happens to always
build `tools_by_id` from the full loaded catalog, so this is currently unreachable in the
UI — but it is a latent trap for the next direct caller or the next registry rename, with
nothing in the test suite that would catch a rename (see WR-02's sibling gap: no test
asserts these four literal ids exist in `installer/registry.toml`).
**Fix:** Use `.get(tool_id)` and treat a missing entry as "not installed" (never present)
rather than crashing:
```python
present = [
    target
    for tool_id, target in _CODEGRAPH_TARGETS.items()
    if (host := tools.get(tool_id)) is not None and is_installed(host)
]
```
Optionally also add a `test_registry.py` assertion that every id in
`_CODEGRAPH_TARGETS` exists in `_tools_by_id()`, so a future rename fails loudly at test
time instead of silently degrading every `codegraph` install into a warning.

### WR-02: No drift-guard test ties `installer/model.py::POSTINSTALL_HOOK_NAMES` to `installer/postinstall.py::POSTINSTALL_HOOKS`, unlike the `SMOKE_CHECK_NAMES`/`SMOKE_CHECKS` precedent this phase's own code comment claims to mirror

**File:** `installer/model.py:13-18`
**Issue:** `model.py`'s own comment states this set is intentionally "Duplicated (not
imported) from installer/postinstall.py::POSTINSTALL_HOOKS's keys, for the same layering
reason SMOKE_CHECK_NAMES is duplicated from installer/executors.py::SMOKE_CHECKS." That
precedent, however, is enforced by an explicit sync test:
`tests/test_executors.py:554`: `assert set(SMOKE_CHECKS) == SMOKE_CHECK_NAMES ==
frozenset({"puppeteer-browser"})`. No equivalent assertion exists anywhere for
`POSTINSTALL_HOOK_NAMES` vs. `POSTINSTALL_HOOKS` (`grep -rn "POSTINSTALL_HOOK_NAMES"
tests/` returns nothing). Today both sets happen to contain exactly one matching entry, so
this is invisible — but the very next hook added to `installer/postinstall.py`'s dispatch
table that is *not* also added to `model.py`'s frozenset would be silently rejected at
registry-load time with a "unknown postinstall" `ValueError` naming a hook that actually
exists and works, and the reverse drift (a name added to `model.py` but never wired into
`POSTINSTALL_HOOKS`) would pass validation yet silently no-op forever at dispatch time
(`run_postinstall`'s own documented behavior for an unrecognized name) — exactly the class
of bug the `SMOKE_CHECK_NAMES` sync test exists to catch for the sibling mechanism.
**Fix:** Add the same shape of test this codebase already has for smoke checks:
```python
def test_postinstall_hook_names_matches_the_dispatch_table() -> None:
    import installer.postinstall as pi
    from installer.model import POSTINSTALL_HOOK_NAMES

    assert set(pi.POSTINSTALL_HOOKS) == POSTINSTALL_HOOK_NAMES
```

## Info

### IN-01: A successful postinstall hook (which mutates other tools' own config files) produces zero user-visible output, unlike this codebase's other side-effecting actions

**File:** `installer/render.py:84-96`
**Issue:** `render_postinstall_warnings` only prints when
`outcome.postinstall_warning` is truthy — a successful `codegraph install --target ...`
run (which writes `mcpServers.codegraph` entries into `claude`/`cursor`/`codex`/`opencode`'s
own real config files on disk) produces no console output at all, on success or failure of
the underlying tool's install. This is an explicit, considered design choice (the
docstring states it "match[es] render_skipped's restraint"), not an oversight, and it is
consistent with `render_dependency_notice`/`render_skipped`'s own "silent when nothing
went wrong" pattern. It is nonetheless a real asymmetry against this codebase's own
convention for actions that write to files the user did not directly ask this run to
touch: `run_guard` prints an explicit consent line before wrapping npm/pnpm
("This wraps npm and pnpm so global installs run `volta install`...") and
`configure_path` always prints what it wrote and where. A user who installs `codegraph`
alongside `claude`/`cursor-agent` gets no confirmation, ever, that their AI hosts' own MCP
config was just modified — only a warning if it failed.
**Fix:** Consider a one-line confirmation on success too (e.g. `"codegraph: registered MCP
server for {csv}"`), surfaced either via a new field on `InstallOutcome` or by having
`_codegraph_mcp_register` return a non-warning informational string that
`render_postinstall_warnings` (or a renamed `render_postinstall_notices`) distinguishes
from a failure.

## Second lane: codex-sol-high

Independent second-lane review over the same diff range (`28df5e0..HEAD`), same real
source files (not plan text). Verdict as originally returned: **NOT READY** (0 Critical,
2 Warning, 0 Info) — both Warnings were real and have since been fixed (see Resolution
status below); the verdict reflected the tree's state at review time, before these fixes
landed.

### Warning — Freshly installed agent hosts can be silently missed

`installer/postinstall.py:76`, `installer/status.py:24`. Host detection uses the current
process's live `PATH`; PATH wiring for a fresh `~/.local/bin` install occurs only in a
later, separate `configure_path`/`make fix` step. On a fresh machine, a P0 host such as
`cursor-agent` installing earlier in the same wizard run could in principle remain
invisible to `is_installed` when codegraph's P1 hook runs immediately after, leaving MCP
silently unregistered with no warning.

### Warning — Noninteractive registration silently grants extra Claude permissions and installs a prompt hook

`installer/postinstall.py:86`. codegraph v1.2.0's `--yes` enables its Claude auto-allow
list and `UserPromptSubmit` hook, not merely MCP registration — a broader behavior change
than REQ-codegraph-mcp-postinstall's literal scope ("run its global MCP-registration
step"). `--no-permissions` suppresses only the allow list addition, is documented as
Claude-only/a no-op for other targets, and was not being passed.

## Resolution status

| Finding | Lane | Severity | Disposition |
|---|---|---|---|
| WR-01 (bare `tools[tool_id]` indexing) | Internal | Warning | **Fixed** — `.get(tool_id)` with a `None`-safe skip; missing id now behaves as "not installed," never crashes. New test: `test_codegraph_hook_treats_a_missing_tool_id_as_absent_not_a_crash`. |
| WR-02 (no `POSTINSTALL_HOOK_NAMES`/`POSTINSTALL_HOOKS` drift guard) | Internal | Warning | **Fixed** — added `test_postinstall_hook_names_matches_the_real_dispatch_table` in `tests/test_model.py`, mirroring the `SMOKE_CHECK_NAMES`/`SMOKE_CHECKS` precedent exactly. |
| IN-01 (silent success, no user-visible confirmation) | Internal | Info | **Accepted, no code change** — a deliberate, documented design choice mirroring `render_skipped`'s own "silent unless something needs attention" convention; noted here rather than silently dropped. A future phase could add a success notice if user feedback asks for it. |
| `--no-permissions` missing (auto-allow/prompt-hook over-grant) | codex-sol-high | Warning | **Fixed** — `_codegraph_mcp_register` now always appends `--no-permissions` to the composed argv, scoping the call to MCP registration only per REQ-codegraph-mcp-postinstall's literal wording. All exact-argv tests and the registry's dated comment updated to match. New test: `test_codegraph_hook_always_passes_no_permissions`. |
| Same-run host-detection staleness | codex-sol-high | Warning | **Documented, accepted limitation** — matches REQ-codegraph-mcp-postinstall's own literal scope ("agent hosts already present," not concurrently installed this run) and this codebase's existing live-PATH `is_installed` detection convention used everywhere else; not a regression this phase introduces. Recorded as a known, accepted limitation in `installer/registry.toml`'s dated comment rather than silently left undocumented. A future phase could re-check presence after the full wizard batch completes if this proves to matter in practice. |

All fixes verified: `make validate && make test` — 0 ruff/pyright/bandit/vulture/shellcheck
findings, 1299 passed, 99.41% coverage.

---

_Reviewed: 2026-09-06_
_Reviewer: Claude (gsd-code-reviewer) + codex-sol-high (second lane)_
_Depth: deep_
