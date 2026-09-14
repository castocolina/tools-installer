# Phase 14: Install/Update Engine Correctness & Default-Shell Action - Pattern Map

**Mapped:** 2026-09-14
**Files analyzed:** 9 (4 modified core, 1 modified registry, 1 new dispatcher, 1 new test file, 4 existing test files to extend)
**Analogs found:** 8 / 9 (one new-pattern-needed: the update-split logic itself has no direct precedent, only composable parts)

**Note on scope correction (carried from RESEARCH.md):** the real integration site for D-01/D-02/D-03 is `installer/execute_screen.py::ExecuteScreen` (Phase-13-era), not `installer/app.py::run_wizard` as CONTEXT.md's canonical refs literally say. All patterns below target the live `ExecuteScreen` path.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/execute_screen.py` (`on_mount`/`_execute_worker`) | controller (Textual screen) | request-response + batch mutation | `installer/catalog_tui.py::action_update_tool`/`_update_tool_worker` (single-tool update body to loop) | adapted (batch form of an existing single-tool pattern) |
| `installer/deps.py::resolve_dependencies` | service (pure resolver) | transform | itself — **read-only reference**, contract must not change | exact (no change) |
| `installer/catalog_tui.py::action_update_tool`/`UpdateService.run` | service (update mutation) | request-response | itself — canonical reuse target, called from a second site | exact (reused, not modified) |
| `installer/model.py` (`POST_INSTALL_ACTIONS` dispatch) | model/schema + new dispatch hookup | event-driven (post-success hook) | `installer/postinstall.py::POSTINSTALL_HOOKS`/`run_postinstall` (sibling singular mechanism) | role-match (deliberately parallel, not shared, table) |
| new `installer/post_install.py` (name TBD) | utility/dispatcher | event-driven | `installer/postinstall.py` (whole-file shape: `PostinstallHook` type alias, closed dict, `run_*` entrypoint) | exact shape, adapted content (new closed set, `Callable` signature likely gains a confirm/handoff param) |
| `installer/registry.toml` (`oh-my-zsh` entry) | config | CRUD (declarative) | itself, lines 526-542 — adding one key (`post_install = ["set_login_shell"]`) to the existing block | exact (single-key addition, same TOML shape as any other tool's declared list field) |
| `installer/resolve.py` (`Platform.immutable` guard idiom) | utility (pattern source only, no file touched) | transform | `installer/resolve.py:70-76` — `if platform.immutable: return False` for `rpm_ostree` | exact (idiom to replicate in the new dispatcher, not in `resolve.py` itself) |
| new `tests/test_post_install.py` | test | request-response (unit) | `tests/test_postinstall.py` (fixture/mocking shape for the sibling singular mechanism) | exact shape, adapted content |
| `tests/test_execute_screen.py`, `tests/test_deps.py`, `tests/test_engine.py`, `tests/test_registry.py` | test | various | each file's own existing fixtures (see per-file notes below) | exact (extend in place) |

## Pattern Assignments

### `installer/execute_screen.py` (controller, batch dispatch)

**Analog:** `installer/catalog_tui.py::action_update_tool` + `_update_tool_worker` (lines 558-610), and `execute_screen.py`'s own existing `on_mount` (lines 325-346).

**Current `on_mount` resolve step to extend** (`execute_screen.py:325-334`):
```python
def on_mount(self) -> None:
    selected = select_tools(self._inputs.catalog, self._ids)
    platform = self._inputs.platform
    resolved = resolve_dependencies(
        order_for_install(selected),
        self._inputs.catalog,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=self._inputs.installed,
    )
    self._ordered = list(resolved.order)
```
Pattern to apply: compute a second set alongside `resolved.order` — selected tools that are installed and update-eligible — using the exact `action_update_tool` predicate (below), without touching `resolve_dependencies` itself.

**Update-eligibility predicate to reuse verbatim** (`catalog_tui.py:568-570`):
```python
status = self._version_statuses.get(tool_id)
if status is not None and status.outdated is False:
    return  # confirmed current -- skip
# status is None (unknown) or status.outdated is True: attempt update
```

**Single-tool update body to loop for the batch** (`catalog_tui.py:585-610`):
```python
def _update_tool_worker(self, tool_id: str) -> None:
    outcome: UpdateOutcome | None = None
    tool = self._by_id.get(tool_id)
    service = self._updates
    refresh = self._version_refresh
    if tool is None or service is None or refresh is None:
        return
    cached = refresh.ownership_of(tool_id)
    if cached is None:
        return
    target = UpdateTarget(tool=tool, ownership=cached)
    result, error = run_live(lambda: service.run(target))
    outcome = result
```
`UpdateService.run` re-resolves ownership fresh internally (`update.py:366-376`, quoted in RESEARCH.md) — a batch loop needs no extra gate, only to construct `UpdateTarget` per eligible tool and call `run` inside the existing `run_live`-wrapped worker (`execute_screen.py:371`, `_execute_worker`, `@work(thread=True)`).

**D-02 gate (no second confirm):** dispatch must happen only after `action_start`/`enter` (`execute_screen.py:348-356`), inside the same worker that already calls `run_installs` — never in `on_mount` before the confirm.

**D-03 (blocked-update summary reuse):** reuse the exact reason text `action_update_tool` produces (`"cannot update {tool_id}: {reason}"`, `catalog_tui.py:131`) and surface via the same `render_report`/summary closure `on_install_run_finished` already builds (`execute_screen.py:500-506`), not an inline message.

**Wiring seam:** `ExecuteInputs` must gain `version_refresh`/`updates` fields, mirroring how `CatalogScreen.__init__` already accepts them (`catalog_tui.py:219-220`), sourced from `setup.py::_build_app`'s existing single construction (`setup.py:572-601,620-622`).

---

### `installer/deps.py::resolve_dependencies` (read-only reference)

**Analog:** itself. **No modification** — RESEARCH.md's explicit anti-pattern: "Making `resolve_dependencies` version-aware... would couple a core resolver to TUI-only state."

**Current exclusion logic to leave untouched** (`deps.py:81-113`):
```python
def is_blocked(tool: Tool) -> bool:
    if tool.id in blocked:
        return True
    if is_installed(tool):
        return False
    ...
satisfied_by_install = {t.id for t in wanted if is_installed(t) and t.id not in blocked}
runnable = [t for t in wanted if t.id not in blocked and t.id not in satisfied_by_install]
```
The planner must cite this exact block as the documented, unchanged baseline in any new `test_deps.py` test (per Wave 0 gap: a selected/installed/outdated tool is *correctly* excluded from `order` here — the split happens one layer up in `execute_screen.py`).

---

### `installer/catalog_tui.py::action_update_tool`/`UpdateService.run` (pattern source, unmodified)

**Analog:** itself — the canonical, tested update mechanism (`catalog_tui.py:558-610`, `update.py:366-422`). No new update-execution code is permitted (D-01); this file is cited only as the pattern every new call site must call into, never reimplement.

---

### `installer/model.py` (dispatch mechanism for `post_install`)

**Analog:** `installer/postinstall.py`'s existing singular dispatch shape, plus `model.py`'s own already-existing schema (`model.py:46-54`, quoted below) as the validation precedent to keep consistent.

**Existing schema, already present, do not restructure** (`model.py:42-54`):
```python
POST_INSTALL_ACTIONS = (
    "configure_path",
    "source_shell_init",
    "set_login_shell",
    "enable_corepack",
    "pnpm_setup",
    "write_agent_reference",
)
SENSITIVE_POST_INSTALL_ACTIONS = ("set_login_shell",)
```
`model.py` itself likely needs no structural change beyond what already validates `Tool.post_install`/`POST_INSTALL_ACTIONS` (confirmed present) — the dispatch table itself is new code in a *new* module (see below), not added into `model.py`. If `model.py` needs a change at all, it should be minimal (e.g. exposing a lookup helper), never growing `POSTINSTALL_HOOK_NAMES` to include `"set_login_shell"` (explicit anti-pattern, Pitfall 4 in RESEARCH.md — the two closed sets are disjoint by design).

---

### new `installer/post_install.py` (the `set_login_shell` dispatcher)

**Analog:** `installer/postinstall.py` in full — its module docstring, `PostinstallHook` type alias, closed dict, and `run_postinstall` entrypoint shape.

**Type alias and dict shape to mirror** (`postinstall.py:60,272-279`):
```python
PostinstallHook = Callable[[Method, Runner, Mapping[str, Tool]], str | None]
...
POSTINSTALL_HOOKS: dict[str, PostinstallHook] = {
    ...
}

def run_postinstall(
    name: str, method: Method, runner: Runner, tools: Mapping[str, Tool]
) -> str | None:
    ...
```
The new module's table must be **named distinctly** (e.g. `POST_INSTALL_HOOKS` / a module literally named `post_install.py`, never added into `postinstall.py`'s own `POSTINSTALL_HOOKS`) — Pitfall 4 in RESEARCH.md is explicit that `postinstall.py` (singular) and this new plural mechanism are disjoint, confusingly-named-but-unrelated concepts.

**Module docstring pattern to mirror** (`postinstall.py:1-10`):
```python
"""Closed, code-owned postinstall-hook dispatch table.

Mirrors installer.executors's `smoke` pattern: a registry `postinstall` field
names an action from this closed set and can never carry a literal command.
Every hook runs through the same `Runner` seam every other executor uses
(installer/run.py). A hook never raises -- it returns `None` on success or a
documented no-op, or a short string describing what went wrong...
"""
```
Adapt for the new module: "never raises, returns handoff text or None" instead of "runs a command" — per RESEARCH.md's Pattern 2 recommendation, `set_login_shell` should produce **reviewed handoff text**, not execute `chsh` in-process.

**`Platform.immutable` hard-guard idiom to replicate (D-04)** (`resolve.py:70-76`):
```python
if kind == "rpm_ostree":
    return False
...
if platform.immutable:
    return False  # skip the native step on immutable distros
```
The new dispatcher's `set_login_shell` entry point must check `platform.immutable` first, unconditionally, before any confirm callback is even offered — mirroring this exact early-return idiom.

**Reviewed-handoff shape to reuse for the actual effect** (`installer/host_setup.py:27-41`):
```python
HOST_SETUPS: dict[str, HostSetup] = {
    "pi": HostSetup(
        handoff=(
            "After leaving the installer, run these Pi setup commands in a console:",
            "pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent",
            "pi",
        ),
        probes=(...,),
        owner="pnpm",
    ),
}
```
`set_login_shell` should produce a comparably-shaped `handoff` tuple, e.g. `("Run this in a terminal to make zsh your login shell:", "chsh -s $(which zsh)")`, surfaced through the existing `MANUAL_REQUIRED`/`handoff` rendering pipeline (`engine.py:139-145`, already streamed by `ExecuteScreen.on_install_run_finished`, `execute_screen.py:504`) — **no new renderer needed**.

**Dispatch call site to mirror (D-06 — inside the existing `oh-my-zsh` install ladder)** (`installer/engine.py:140-159`, `install_tool`'s existing singular-hook dispatch immediately after a successful method):
```python
warning = None
if tool.postinstall:
    try:
        warning = run_postinstall(tool.postinstall, method, runner, tools or {})
    except Exception as exc:  # noqa: BLE001 -- isolation boundary
        warning = f"postinstall hook {tool.postinstall!r} crashed: {exc}"
return InstallOutcome(
    tool.id,
    InstallStatus.INSTALLED,
    method_kind=method.kind,
    verified=verified,
    postinstall_warning=warning,
)
```
The new plural-field dispatch must be added at the same call site, immediately after this block (or interleaved with it), never on the `ALREADY_INSTALLED` early-return path — same "single-direction trigger" property `installer/postinstall.py`'s singular mechanism already has (documented in `.claude/architecture.md`'s "Phase 9: postinstall hooks" section).

**D-05 confirm-callback threading pattern to mirror** (`installer/session.py:16-17,69-79`):
```python
MismatchChoice = Literal["retry", "skip", "fallback"]
OnMismatch = Callable[[str], MismatchChoice]

def run_installs(
    tools: list[Tool],
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    install: Install = install_tool,
    on_mismatch: OnMismatch | None = None,
    catalog: Mapping[str, Tool] | None = None,
    *,
    should_continue: Callable[[], bool] | None = None,
) -> list[InstallOutcome]:
```
A new `confirm_sensitive_action: Callable[[str], bool] | None = None`-shaped parameter, threaded the same way through `install_tool`/`run_installs`/`ExecuteScreen`'s worker, is the idiom to copy — "no callback given" must default to the safe choice (skip, never run silently), mirroring `on_mismatch`'s documented "No callback = unattended mode: the hard-fail outcome stands" contract (`session.py:85`).

**Confirm-modal UI template (D-05's Claude's-Discretion UI shape)**: `ChecksumMismatchScreen` (`execute_screen.py:79-121`) via `ask_from_worker`/`push_screen_wait` (`execute_screen.py:124-137`) — the one documented worker-to-modal mechanism this codebase has (MECHANISM=A, `13-VALIDATION.md`). Do not invent a second one.

---

### `installer/registry.toml` (`oh-my-zsh` entry)

**Analog:** itself, lines 526-542 — single-field addition, no restructuring.

**Current block** (`registry.toml:526-542`):
```toml
[[tool]]
id = "oh-my-zsh"
name = "Oh My Zsh"
category = "shell"
cmd = "omz"
priority = "P2"
audience = "both"
tier = "system"
requires = ["zsh", "git"]
desc = "Zsh configuration framework; installs into ~/.oh-my-zsh and edits .zshrc, preserving it via KEEP_ZSHRC."
[[tool.method]]
kind = "script"
url = "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
shell = "sh"
env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }
detect_path = "~/.oh-my-zsh/oh-my-zsh.sh"
```
Add `post_install = ["set_login_shell"]` to the `[[tool]]` block (top-level `Tool` fields, not inside `[[tool.method]]`) — D-07 scopes this to `oh-my-zsh` only; **no other tool entry may declare `post_install`** this phase (enforced by review + `tests/test_registry.py`, not automated). The existing `env = { ..., CHSH = "no", ... }` line stays unchanged per RESEARCH.md's "State of the Art" table — `CHSH=no` remains the install-script-level guard; `set_login_shell` is a separate, explicit, opt-in step layered on top.

---

### `installer/resolve.py` (`Platform.immutable` pattern source, no file change expected)

**Analog:** itself, lines 70-76 (quoted above under the new dispatcher section). This file is listed as a pattern source only — RESEARCH.md gives no indication `resolve.py` itself needs modification; the guard is replicated inside the new `post_install` dispatcher, not added to `resolve.py`.

---

### new `tests/test_post_install.py`

**Analog:** `tests/test_postinstall.py` — full structural template (imports, `_tool`/`_tools` helpers, monkeypatched `Runner`, subset-combination host fixtures).

**Structure to mirror** (`tests/test_postinstall.py:1-45`):
```python
from itertools import combinations
from pathlib import Path

import pytest

import installer.postinstall as pi
from installer.model import Method, Tool
from installer.run import CommandError, Runner

def _tool(tool_id: str) -> Tool:
    return Tool(
        id=tool_id, name=tool_id, category="ai", cmd=tool_id,
        methods=(Method(kind="github_release", params={}),), tier="ai",
    )

def test_codegraph_hook_composes_csv_from_present_hosts_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    def runner(cmd: list[str]) -> None:
        calls.append(cmd)
    def fake_is_installed(tool: Tool) -> bool:
        return tool.id in (...)
    monkeypatch.setattr(pi, "is_installed", fake_is_installed)
    method = Method(kind="github_release", params={})
    warning = pi.run_postinstall("codegraph-mcp-register", method, runner, _tools())
    assert warning is None
    ...
```
Adapt: `_tool` for `oh-my-zsh`-shaped fixtures, `monkeypatch.setattr` on `installer.platform.Platform.immutable` (or pass `Platform(..., immutable=True/False, ...)` directly, matching the existing construction pattern in `tests/test_resolve.py`/`tests/test_engine.py`), and assertions on the returned `handoff` tuple / `None` rather than on `calls` to a runner (since D-04/D-05's recommended shape never actually invokes `chsh`).

Required test cases per RESEARCH.md's Wave 0 gaps:
- `Platform.immutable=True` → `set_login_shell` never offered/executed (D-04).
- Non-immutable + no confirm callback → skipped, safe default (D-05, mirrors `on_mismatch`'s "no callback = unattended" contract).
- Non-immutable + confirm callback returns `True` → handoff text produced, `chsh` never actually invoked in-process.
- Non-immutable + confirm callback returns `False` → skipped, no handoff.

---

### `tests/test_execute_screen.py`, `tests/test_deps.py`, `tests/test_engine.py`, `tests/test_registry.py` (modify)

**`tests/test_execute_screen.py`:**
- **Analog:** `tests/test_wizard_app.py:4070-4140`'s existing `_execute_inputs` pilot-fixture pattern (extend `ExecuteInputs` fixture helper with `version_refresh`/`updates` fields) and `tests/test_catalog_tui.py:1440-1488`'s `outdated=None`/`VersionStatus` fixture shape for the eligibility predicate.
- New cases needed (Wave 0, currently `❌` per RESEARCH.md's test map): `-k outdated` (D-01: selecting an outdated installed tool triggers `UpdateService.run`), `-k confirm` (D-02: no update dispatch before `action_start`), `-k blocked_update` (D-03: reused reason text in the post-run summary, modeled on `tests/test_catalog_tui.py:1407-1437`'s `test_action_update_tool_refuses_non_mutation_grade`).

**`tests/test_deps.py`:**
- **Analog:** existing `test_already_installed_dependency_is_not_dragged_in` (`tests/test_deps.py:64-69`) — extend with a new sibling test for the *selected, installed, outdated* case (currently missing), asserting `resolve_dependencies`'s output is unchanged (excludes the tool from `order`) — this documents the baseline the `ExecuteScreen` split builds on top of, without touching `deps.py` itself.

**`tests/test_engine.py`:**
- **Analog:** existing `ALREADY_INSTALLED`-path tests (`engine.py:116-117`'s short-circuit) plus the `tool.postinstall` dispatch test near `engine.py:150-154`. Add `-k login_shell` cases for D-04 (immutable guard) if the dispatcher is invoked via `install_tool` directly rather than only through the new module's own tests — model on the same `Platform(os=..., arch=..., immutable=True, has_brew=...)` construction already used throughout `tests/test_resolve.py`.

**`tests/test_registry.py`:**
- **Analog:** `test_java_tools_install_exclusively_through_sdkman` (`tests/test_registry.py:122-140`) — same shape of "assert exactly one/only-named tool(s) declare X" test. New case: assert only `oh-my-zsh` declares `post_install = ["set_login_shell"]` (D-07 — no generalization/second declarer sneaks in unreviewed).

## Shared Patterns

### Update mutation reuse (D-01)
**Source:** `installer/catalog_tui.py::action_update_tool`/`_update_tool_worker` (lines 558-610) + `installer/update.py::UpdateService.run` (lines 366-422)
**Apply to:** `installer/execute_screen.py`'s new batch-update loop — construct `UpdateTarget` per eligible tool, call `service.run(target)` inside `run_live`; never re-implement the `MUTATION_GRADE`/ownership gate inline (it is already fresh-re-resolved inside `run`).

### Confirm-gate placement (D-02)
**Source:** `installer/execute_screen.py`'s existing `enter start` gate (`execute_screen.py:342,348-356`, `action_start`)
**Apply to:** any new update/sensitive-action dispatch — must fire only inside `_execute_worker`, after `action_start`, never in `on_mount`.

### Closed-set, code-owned dispatch (V5 input validation doctrine)
**Source:** `installer/postinstall.py::POSTINSTALL_HOOKS` + `.claude/architecture.md`'s "Phase 9: postinstall hooks" section ("a registry edit alone can never introduce arbitrary post-install execution")
**Apply to:** the new `post_install`/`set_login_shell` dispatch table — registry selects a NAME only, never a literal command.

### Reviewed-handoff for terminal-owning mutations
**Source:** `installer/host_setup.py:1-7` module docstring + `HOST_SETUPS["pi"]` worked example (`host_setup.py:27-41`) + `InstallStatus.MANUAL_REQUIRED`/`InstallOutcome.handoff` rendering (`engine.py:139-145`, `execute_screen.py:504`)
**Apply to:** `set_login_shell`'s actual effect — produce reviewed `chsh` instructions, never invoke `chsh` from a worker thread (`StreamingRunner`/`run_captured` both mishandle a PAM password-prompting child's stdin, per RESEARCH.md Pitfall 3).

### Platform-immutability hard guard
**Source:** `installer/resolve.py:70-76` (`if platform.immutable: return False`, the `rpm_ostree`-skip idiom)
**Apply to:** the new dispatcher's `set_login_shell` entry — check first, unconditionally, before any confirm callback (D-04).

### Optional confirm-callback threading, safe-default-on-None
**Source:** `installer/session.py:16-17,69-79` (`OnMismatch`/`on_mismatch` parameter shape, "no callback = unattended mode: hard-fail stands")
**Apply to:** the new `confirm_sensitive_action`-shaped parameter threaded through `install_tool`/`run_installs`/`ExecuteScreen`'s worker for D-05 (never fires without an explicit `True`).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `installer/execute_screen.py`'s update/install-split decision itself | controller logic | batch dispatch | No existing code splits a batch into install-vs-update sub-batches inside one screen; it is a genuinely new composition of two existing, independently-tested mechanisms (`resolve_dependencies` + `UpdateService.run`), not a copy of a single analog. Planner should treat Pattern 1 from RESEARCH.md (Architecture Patterns section) as the design to implement, composing the listed analogs above rather than searching for a closer single match. |

## Metadata

**Analog search scope:** `installer/` (all modules cited in RESEARCH.md's canonical refs and code-context sections), `tests/` (test_postinstall.py, test_catalog_tui.py, test_deps.py, test_execute_screen.py, test_registry.py, test_wizard_app.py), `.claude/architecture.md`
**Files scanned:** 9 target files + 9 analog source files (installer/catalog_tui.py, installer/update.py, installer/postinstall.py, installer/host_setup.py, installer/session.py, installer/resolve.py, installer/engine.py, installer/execute_screen.py, tests/test_postinstall.py)
**Pattern extraction date:** 2026-09-14

---

## PATTERN MAPPING COMPLETE

**Phase:** 14 - Install/Update Engine Correctness & Default-Shell Action
**Files classified:** 9
**Analogs found:** 8 / 9

### Coverage
- Files with exact analog: 4 (`deps.py` read-only, `catalog_tui.py` reused, `registry.toml`, `resolve.py` pattern-source)
- Files with role-match/adapted analog: 4 (`execute_screen.py`, `model.py`, new `post_install.py`, new `test_post_install.py`, plus the 4 existing test files extended in place)
- Files with no analog: 1 (the batch install/update split composition logic itself — new-pattern-needed, but composed entirely from existing tested primitives)

### Key Patterns Identified
- All update mutations flow through `UpdateService.run`/`UpdateTarget` — never reimplement the ownership/`MUTATION_GRADE` gate; it re-resolves fresh internally.
- Confirm-then-mutate always gates on the *existing* single confirm point in the given screen (`ExecuteScreen`'s `enter start`, or a `ChecksumMismatchScreen`-style modal for a mid-run decision) — never a second ad hoc prompt.
- Any post-install dispatch table must be a closed, code-owned NAME set (mirroring `POSTINSTALL_HOOKS`) — the registry can never carry a literal command; keep the new plural `post_install` table structurally and nominally distinct from the existing singular `postinstall.py::POSTINSTALL_HOOKS`.
- Terminal-owning, password-prompting system mutations (`chsh`) follow the `host_setup.py` reviewed-handoff precedent, never in-process execution through `StreamingRunner`/`run_captured`.

### File Created
`/var/home/bazzite/git/personal/tools-installer/.planning/phases/14-install-update-engine-correctness-default-shell-action-selec/14-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files.
