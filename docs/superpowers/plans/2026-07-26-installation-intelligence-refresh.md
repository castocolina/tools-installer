# Installation Intelligence Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect more real installation methods without guessing ownership, including pnpm-managed OpenCode, and refresh Catalog state after execution.

**Architecture:** Add read-only manager adapters and an application receipt store behind `tool_status`. Catalog receives a status-refresh callback rather than mutating one boolean. Ownership remains verified only by manager evidence.

**Tech Stack:** Python 3.12, TOML registry, pytest.

## Global Constraints

- A resolved executable path proves presence only.
- Tests stub every manager command and use a temporary receipt directory.
- A missing artifact invalidates an otherwise present receipt.

---

### Task 1: Add manager adapter coverage and OpenCode pnpm ownership

**Files:**
- Modify: `installer/ownership.py`, `installer/registry.toml`, `installer/model.py`
- Test: `tests/test_ownership.py`, `tests/test_model.py`, `tests/test_status.py`

**Interfaces:**
- Produces `Ownership(manager, "verified", detail)` for pnpm, npm, uv, pipx, Flatpak, Snap, SDKMAN, and existing native managers.
- Consumes declared `owner_probes` and method package metadata.

- [ ] **Step 1: Write the failing test**

```python
def test_opencode_is_verified_as_pnpm_owned() -> None:
    tool = _registry_tool("opencode")
    probe = _probe({("pnpm", "list", "--global", "--depth", "0", "--json"):
                    '[{"dependencies":{"opencode-ai":{"name":"opencode-ai"}}}]'})
    assert detect_owner(tool, probe).manager == "pnpm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ownership.py tests/test_model.py -k opencode -v`

Expected: FAIL because OpenCode declares no pnpm package identity or owner probe.

- [ ] **Step 3: Write minimal implementation**

Add the upstream pnpm package identity and ordered probes `pnpm`, `npm`, `pacman`, and `brew` to OpenCode. Implement each new manager with its read-only native listing command and strict package-name match. Do not infer manager ownership from the executable path.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ownership.py tests/test_model.py tests/test_status.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/ownership.py installer/registry.toml installer/model.py tests/test_ownership.py tests/test_model.py tests/test_status.py
git commit -m "feat(status): detect manager-owned installations"
```

### Task 2: Add installer receipts without overriding artifact evidence

**Files:**
- Create: `installer/receipts.py`
- Modify: `installer/engine.py`, `installer/status.py`, `setup.py`
- Test: `tests/test_receipts.py`, `tests/test_engine.py`, `tests/test_status.py`

**Interfaces:**
- Produces `ReceiptStore(root: Path)` with `record(tool, method, artifacts)` and `lookup_present(tool_id) -> Receipt | None`.
- Consumes an injected receipt root; defaults to managed application state.

- [ ] **Step 1: Write the failing test**

```python
def test_receipt_is_not_present_when_artifact_is_missing(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    store.record("fd", "github_release", (tmp_path / "bin" / "fd",))
    assert store.lookup_present("fd") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_receipts.py -v`

Expected: FAIL because receipt storage does not exist.

- [ ] **Step 3: Write minimal implementation**

Write one JSON receipt per successful application-managed install by atomic replace. Include tool id, method, completion timestamp, optional version, and artifact paths. Treat a receipt as verified ownership only when all recorded artifacts still exist.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_receipts.py tests/test_engine.py tests/test_status.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/receipts.py installer/engine.py installer/status.py setup.py tests/test_receipts.py tests/test_engine.py tests/test_status.py
git commit -m "feat(status): retain verified installer receipts"
```

### Task 3: Refresh actual Catalog status and staged selection

**Files:**
- Modify: `installer/catalog_tui.py`, `installer/tool_browser.py`, `installer/wizard_app.py`, `setup.py`
- Test: `tests/test_catalog_tui.py`, `tests/test_wizard_app.py`

**Interfaces:**
- Produces `CatalogScreen.refresh_statuses(statuses: Mapping[str, ToolStatus])`.
- Produces `ToolBrowser.discard_selected(ids: Collection[str])`.

- [ ] **Step 1: Write the failing test**

```python
async def test_completed_install_refreshes_owner_and_deselects_successes() -> None:
    app = _app(start_install=_install_fd, refresh_statuses=_fd_now_pnpm_owned)
    async with app.run_test() as pilot:
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
        await pilot.press("escape")
    assert app.catalog.selected == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_tui.py tests/test_wizard_app.py -k 'refreshes_owner or deselects' -v`

Expected: FAIL because events flip only `installed` and preserve every selection.

- [ ] **Step 3: Write minimal implementation**

At completion, call the injected status factory for all Catalog tools, update Catalog atomically, and discard only `Summary.installed` and `Summary.already`. Keep failed, skipped, cancelled, and manual-required ids selected.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_tui.py tests/test_wizard_app.py tests/test_status.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/catalog_tui.py installer/tool_browser.py installer/wizard_app.py setup.py tests/test_catalog_tui.py tests/test_wizard_app.py
git commit -m "fix(catalog): refresh status after installation"
```

