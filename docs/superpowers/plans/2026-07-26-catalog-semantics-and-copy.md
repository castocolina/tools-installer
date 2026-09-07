# Catalog Semantics and Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Catalog labels explain recommendation and audience correctly.

**Architecture:** Preserve registry metadata as the source of truth, but give recommendation and audience distinct display language. Put contextual explanation in the permanent legend and highlighted-item detail.

**Tech Stack:** Python 3.12, Textual, TOML registry, pytest.

## Global Constraints

- Do not conflate audience, catalog tier, category, recommendation, or ownership.
- Use concrete, user-facing copy; no unexplained labels.

---

### Task 1: Correct catalog metadata and validate it

**Files:**
- Modify: `installer/registry.toml`, `installer/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Produces validated audience values `human`, `agent`, and `both`; recommendation values remain `core`, `contextual`, and `optional`.

- [ ] **Step 1: Write the failing test**

```python
def test_user_facing_editors_are_human_audience() -> None:
    tools = _tools_by_id()
    assert tools["vscode"].audience == "human"
    assert tools["sublime"].audience == "human"
    assert tools["aichat"].audience == "human"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model.py -k user_facing_editors -v`

Expected: FAIL because VS Code and Sublime are `both`, and aichat is `ai`.

- [ ] **Step 3: Write minimal implementation**

Use `human` for tools primarily operated by the person. Retain `both` only where the registry can state a concrete human-and-agent use case. Update validation and display labels together.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/registry.toml installer/model.py tests/test_model.py
git commit -m "fix(catalog): clarify user tool audiences"
```

### Task 2: Explain contextual recommendations in the UI

**Files:**
- Modify: `installer/catalog_tui.py`
- Test: `tests/test_catalog_tui.py`

**Interfaces:**
- Produces `recommendation_detail(tool: Tool) -> str`.
- Consumes `tool.recommendation` in row rendering, legend, and selected-item detail.

- [ ] **Step 1: Write the failing test**

```python
def test_contextual_detail_explains_project_dependent_recommendation() -> None:
    screen = _catalog_for("sdkman")
    assert "Install when a project needs this ecosystem" in screen._detail_text(_tool("sdkman"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_tui.py -k contextual -v`

Expected: FAIL because the UI only appends the unexplained word `contextual`.

- [ ] **Step 3: Write minimal implementation**

Add the legend entry `contextual: install when a project needs this ecosystem`. Add the same meaning to detail text. Keep the short row badge only while the legend is visible.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_tui.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/catalog_tui.py tests/test_catalog_tui.py
git commit -m "feat(catalog): explain contextual recommendations"
```

