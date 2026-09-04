# Doctor Catalog Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the interactive Fix flow into the Doctor view and refresh the tool catalog so priorities, audiences, descriptions, and requested tools match the PRD.

**Architecture:** Keep the Python Textual TUI and the existing `AppScreen` chrome. Collapse only the interactive TUI Fix screen into `DoctorScreen`; leave standalone CLI `make doctor` and `make fix` behavior intact. Keep catalog data in `installer/registry.toml`, using existing method kinds unless the task explicitly adds tests and executor support.

**Tech Stack:** Python, Textual, Rich `Text`, TOML registry data, pytest, uv-managed environment, Makefile quality gates.

## Global Constraints

- English only. Every response, identifier, comment, docstring, log line, and commit message is in English.
- `uv` owns the environment: Python version, `.venv`, and all dependencies.
- Never use `pip`, `poetry`, `conda`, or a hand-rolled venv.
- Never bypass a quality gate. Fix the root cause; never silence a check to make it pass.
- Validate before committing. `make validate && make test` must pass on the exact tree you are about to commit.
- Keep the existing Python Textual app.
- Do not introduce React, MUI, or a web frontend for this work.
- Use `agent-ui-ux-designer` guidance for UI/UX critique and direction.
- Do not use GSD UI skills for this work; GSD is reserved for full SSD-style workflows.
- Opening Doctor must remain read-only. It must not write shell files until the user applies the fix.
- The standalone Fix view must leave top-level navigation if Doctor owns the apply action.
- Mark `codex`, `claude`, and `opencode` as `P0` human-facing tools, not AI-facing tools.
- Preserve the `audience` distinction: `ai`, `human`, and `both`.
- The resolver must not claim a supported install method where the installer cannot actually install the app safely.

## Scope Check

The PRD covers two subsystems: the interactive TUI and the declarative catalog. Keep them in one plan because the user-facing acceptance criteria depend on both landing in the same release, but split the work into independently testable tasks: view registry, Doctor behavior/layout, catalog policy tests, catalog data, and final verification.

## Assumptions From Open Questions

- The installable catalog remains installable-only because `tests/test_registry.py::test_every_tool_has_at_least_one_method` enforces one method per tool. Unsupported requested tools are documented in this plan and in test names or descriptions, not added as no-op registry rows.
- JetBrains is represented by `jetbrains-toolbox` first. Do not add separate PyCharm or IntelliJ entries in this pass because Toolbox is the safer management surface and direct per-IDE app modeling would duplicate cask-only rows.
- `codegraph` is treated as a documented dependency for this pass, not an installable registry entry, unless implementation finds a verified official method that fits the existing `script`, `brew`, `cask`, `node`, `github_release`, or native package kinds. Do not invent a method kind for it.
- Java tools declare `requires = ["sdkman"]` where requested. They may still install through native or Homebrew methods until an SDKMAN executor exists.

## Reference Sources Checked

- Codex CLI official repository: `https://github.com/openai/codex`
- Claude Code setup docs: `https://code.claude.com/docs/en/setup`
- OpenCode docs: `https://opencode.ai/docs`
- SDKMAN install docs: `https://sdkman.io/install/`

## File Structure

- Modify `installer/ui_common.py`: remove the standalone Fix view from the shared registry, update Doctor mode/action copy, and change global nav from four plus one views to four views.
- Modify `installer/wizard_app.py`: remove `FixScreen`, move its apply behavior and preview rendering into `DoctorScreen`, and install only `doctor`, `uninstall`, and `policies` pushed screens.
- Modify `tests/test_ui_common.py`: lock the four-view registry, header, mode badge, and footer text.
- Modify `tests/test_wizard_app.py`: lock Doctor apply behavior, read-only-on-open behavior, hidden `a` alias, failure retry, success idempotence, removed Fix navigation, and rapid switching with the new view order.
- Modify `installer/registry.toml`: update priorities, descriptions, audiences, categories, dependencies, and add supported requested catalog entries.
- Modify `tests/test_registry.py`: lock catalog additions, priority and audience policy, SDKMAN dependencies, immutable Linux resolver behavior, and updated counts/category members.
- Create `docs/catalog-unsupported-tools.md`: explain requested tools not added as installable catalog entries and why the current installer cannot safely manage them yet.

---

### Task 1: Collapse The Shared View Registry

**Files:**
- Modify: `installer/ui_common.py:98-170`
- Test: `tests/test_ui_common.py`
- Test: `tests/test_wizard_app.py`

**Interfaces:**
- Consumes: existing `View`, `VIEWS`, `VIEW_ORDER`, `VIEW_BY_NAME`, `GLOBAL_NAV`, `FooterBar`, `WayfindingHeader`, and `ModeBadge`.
- Produces: `VIEW_ORDER == ("catalog", "doctor", "uninstall", "policies")`; Doctor footer actions become `enter apply`; number keys become `1-4`.

- [ ] **Step 1: Write the failing registry tests**

Add these tests to `tests/test_ui_common.py`:

```python
from installer.ui_common import GLOBAL_NAV, VIEW_BY_NAME, VIEW_ORDER


def test_view_order_collapses_fix_into_doctor() -> None:
    assert VIEW_ORDER == ("catalog", "doctor", "uninstall", "policies")
    assert "fix" not in VIEW_BY_NAME


def test_doctor_view_advertises_audit_and_apply() -> None:
    doctor = VIEW_BY_NAME["doctor"]
    assert doctor.label == "Doctor"
    assert doctor.palette == "Doctor - audit PATH and apply the safe fix"
    assert doctor.mode == "AUDIT + APPLY"
    assert doctor.hint == "audit report stays read-only until you press enter"
    assert doctor.actions == "enter apply"


def test_global_nav_names_four_views() -> None:
    assert GLOBAL_NAV == "1-4 views | ^p nav | esc back | q quit"
```

- [ ] **Step 2: Update wizard navigation tests before implementation**

In `tests/test_wizard_app.py`, update the existing footer/navigation expectations so they assert four views. Replace any references to pressing `"3"` for Fix with pressing `"3"` for Uninstall and `"4"` for Policies. Use this new footer test:

```python
async def test_doctor_uninstall_and_policies_render_a_footer() -> None:
    from installer.ui_common import FooterBar

    app = _app()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert isinstance(app.screen, DoctorScreen)
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("3")
        assert isinstance(app.screen, UninstallScreen)
        assert len(app.screen.query(FooterBar)) == 1
        await pilot.press("4")
        assert isinstance(app.screen, PoliciesScreen)
        assert len(app.screen.query(FooterBar)) == 1
```

- [ ] **Step 3: Run the focused tests and verify failure**

Run: `uv run pytest tests/test_ui_common.py tests/test_wizard_app.py::test_doctor_uninstall_and_policies_render_a_footer -q`

Expected: failure because `VIEW_ORDER` still includes `fix`, `GLOBAL_NAV` still says `1-5`, and Doctor still has read-only registry copy.

- [ ] **Step 4: Replace the view registry**

In `installer/ui_common.py`, replace the `VIEWS` tuple and `GLOBAL_NAV` with:

```python
VIEWS: tuple[View, ...] = (
    View(
        name="catalog",
        label="Catalog",
        palette="Catalog - pick tools to install",
        mode="STAGED",
        glyph="o",
        style="cyan",
        hint="space marks a tool; enter installs your selection",
        actions="space toggle | enter install | a all | i invert",
    ),
    View(
        name="doctor",
        label="Doctor",
        palette="Doctor - audit PATH and apply the safe fix",
        mode="AUDIT + APPLY",
        glyph=">",
        style="yellow",
        hint="audit report stays read-only until you press enter",
        actions="enter apply",
    ),
    View(
        name="uninstall",
        label="Uninstall",
        palette="Uninstall - remove installed tools",
        mode="STAGED / DESTRUCTIVE",
        glyph="o",
        style="red",
        hint="space marks; enter removes marked items (you'll confirm)",
        actions="space mark | enter remove | a all | i invert",
    ),
    View(
        name="policies",
        label="Policies",
        palette="Policies - pip/npm ban and env tweaks",
        mode="LIVE",
        glyph="*",
        style="yellow",
        hint="space toggles a policy and applies it now; reversible",
        actions="space toggle",
    ),
)

VIEW_ORDER: tuple[str, ...] = tuple(view.name for view in VIEWS)
VIEW_BY_NAME: dict[str, View] = {view.name: view for view in VIEWS}

GLOBAL_NAV: str = "1-4 views | ^p nav | esc back | q quit"
```

- [ ] **Step 5: Run the focused tests and verify pass**

Run: `uv run pytest tests/test_ui_common.py tests/test_wizard_app.py::test_doctor_uninstall_and_policies_render_a_footer -q`

Expected: pass after wizard navigation references are adjusted in Task 2 or fail only on `wizard_app.py` still installing the Fix screen. If the latter happens, complete Task 2 before committing.

- [ ] **Step 6: Commit**

```bash
git add installer/ui_common.py tests/test_ui_common.py tests/test_wizard_app.py
git commit -m "feat: collapse fix navigation into doctor"
```

### Task 2: Merge Fix Behavior Into DoctorScreen

**Files:**
- Modify: `installer/wizard_app.py:65-143`
- Modify: `installer/wizard_app.py:580-604`
- Test: `tests/test_wizard_app.py`

**Interfaces:**
- Consumes: `DoctorReport`, `doctor_guidance(report)`, `guard_guidance(status, warning)`, `guidance_text(guidance)`, `run_live(fix) -> tuple[None, str | None]`.
- Produces: `DoctorScreen(report, guard_status, guard_warning, fix_preview, fix)` with public test seams `guidance: list[Guidance]`, `applied: bool`, `error: str | None`, and `action_apply() -> None`.

- [ ] **Step 1: Replace FixScreen tests with Doctor apply tests**

In `tests/test_wizard_app.py`, remove tests that instantiate or navigate to `FixScreen`. Change the widget import to `from textual.widgets import DataTable, Static`. Add these tests:

```python
async def test_opening_doctor_does_not_apply_fix() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        assert isinstance(app.screen, DoctorScreen)
        assert calls == []
        assert app.screen.applied is False
        assert app.screen.error is None


async def test_doctor_enter_applies_fix_once() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        await pilot.press("enter")
        assert calls == ["fix"]
        assert app.screen.applied is True
        assert app.screen.error is None
        await pilot.press("enter")
        assert calls == ["fix"]


async def test_doctor_hidden_a_alias_applies_fix() -> None:
    calls: list[str] = []
    app = _app(fix=lambda: calls.append("fix"))

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        await pilot.press("a")
        assert calls == ["fix"]
        assert app.screen.applied is True


async def test_doctor_apply_failure_shows_error_and_allows_retry() -> None:
    calls = 0

    def fix() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("read-only rc file")

    app = _app(fix=fix)

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("2")
        await pilot.press("enter")
        assert app.screen.applied is False
        assert app.screen.error == "read-only rc file"
        assert "read-only rc file" in str(app.screen.query_one("#doctor-body", Static).renderable)
        await pilot.press("enter")
        assert app.screen.applied is True
        assert app.screen.error is None
```

- [ ] **Step 2: Update the app factory signature in tests**

Keep `_app(...)` parameters the same, but expect `fix_preview` and `fix` to flow into `DoctorScreen`, not `FixScreen`. No test helper signature change is required because `_app` already passes both into `UnifiedApp`.

- [ ] **Step 3: Run tests and verify the intended failure**

Run: `uv run pytest tests/test_wizard_app.py -q`

Expected: failure because `DoctorScreen` does not accept `fix_preview` or `fix`, does not bind Enter, and `FixScreen` still exists.

- [ ] **Step 4: Replace DoctorScreen and remove FixScreen**

In `installer/wizard_app.py`, replace `DoctorScreen` and delete `FixScreen`:

```python
class DoctorScreen(AppScreen):
    """PATH audit and safe PATH repair in one view."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "apply", "apply", show=True),
        Binding("a", "apply", "apply", show=False),
    ]
    DEFAULT_CSS = """
    DoctorScreen #doctor-body {
        width: 76;
        max-width: 90%;
        height: auto;
        margin: 2 1;
        padding: 1 2;
        border: round $accent;
    }
    """

    def __init__(
        self,
        report: DoctorReport,
        guard_status: dict[str, bool],
        guard_warning: str | None,
        fix_preview: str,
        fix: Callable[[], None],
    ) -> None:
        super().__init__(view="doctor")
        self._report = report
        self._guard_status = guard_status
        self._guard_warning = guard_warning
        self._fix_preview = fix_preview
        self._fix = fix
        self.guidance: list[Guidance] = []
        self.applied = False
        self.error: str | None = None

    def compose_body(self) -> ComposeResult:
        yield Static(id="doctor-body")

    def on_mount(self) -> None:
        self.guidance = doctor_guidance(self._report) + guard_guidance(
            self._guard_status, self._guard_warning
        )
        self._refresh_body()

    def _refresh_body(self) -> None:
        body = self.query_one("#doctor-body", Static)
        text = Text()
        text.append("PATH Doctor\n", style="bold")
        text.append("Audit\n", style="bold")
        text.append(guidance_text(self.guidance))
        text.append("\n\nSafe fix preview\n", style="bold")
        text.append(self._fix_preview)
        text.append("\n\nAction\n", style="bold")
        if self.applied:
            text.append("PATH wired.", style="green")
            text.append("\nRestart your shell or run `source ~/.myshellrc` to apply.")
        elif self.error is not None:
            text.append("Fix failed.", style="red")
            text.append(f"\n{self.error}")
            text.append("\nCheck the target is writable, then press enter to retry.")
        else:
            text.append("Press enter to wire the managed PATH into your shells.", style="yellow")
            text.append("\nViewing this screen did not change your shell files.")
        body.update(text)

    def action_apply(self) -> None:
        if self.applied:
            return
        _, self.error = run_live(self._fix)
        self.applied = self.error is None
        self._refresh_body()
```

- [ ] **Step 5: Update UnifiedApp screen installation**

In `UnifiedApp.__init__`, replace `_views` with:

```python
self._views: dict[str, Screen[None]] = {
    "doctor": DoctorScreen(report, guard_status, guard_warning, fix_preview, fix),
    "uninstall": UninstallScreen(uninstall),
    "policies": PoliciesScreen(policies),
}
```

- [ ] **Step 6: Remove stale FixScreen imports and references**

Remove `FixScreen` from `tests/test_wizard_app.py` imports and assertions. Keep `fix_preview` and `fix` in `_app` because Doctor now consumes them.

- [ ] **Step 7: Run focused tests**

Run: `uv run pytest tests/test_ui_common.py tests/test_wizard_app.py -q`

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add installer/wizard_app.py tests/test_wizard_app.py
git commit -m "feat: apply path fix from doctor view"
```

### Task 3: Lock Catalog Policy With Tests

**Files:**
- Modify: `tests/test_registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `load_tools(REGISTRY) -> list[Tool]`, `resolve_methods(tool, platform) -> list[Method]`, `requires_integrity_errors(tools) -> list[str]`.
- Produces: executable catalog policy tests that fail before registry edits and protect future catalog changes.

- [ ] **Step 1: Add helper functions**

In `tests/test_registry.py`, change the model import to `from installer.model import Tool, load_categories, load_tools`. Add these helpers after `REGISTRY`:

```python
def _tools_by_id() -> dict[str, Tool]:
    return {tool.id: tool for tool in load_tools(REGISTRY)}


def _ids_by_priority(priority: str) -> set[str]:
    return {tool.id for tool in load_tools(REGISTRY) if tool.priority == priority}
```

- [ ] **Step 2: Replace exact count test with a named requested-entry test**

If `test_registry_declares_expected_count` currently asserts `len(ids) == 50`, replace it with:

```python
def test_registry_includes_requested_installable_entries() -> None:
    ids = set(_tools_by_id())
    assert {
        "brew",
        "git",
        "codex",
        "claude",
        "opencode",
        "docker",
        "podman",
        "colima",
        "vscode",
        "jetbrains-toolbox",
        "sdkman",
        "java",
        "groovy",
        "springbootcli",
        "gradle",
        "maven",
    } <= ids
```

- [ ] **Step 3: Add priority and audience tests**

Add:

```python
def test_human_agent_clis_are_p0_human_tools() -> None:
    tools = _tools_by_id()
    for tool_id in ("codex", "claude", "opencode"):
        tool = tools[tool_id]
        assert tool.priority == "P0"
        assert tool.audience == "human"
        assert tool.category == "ai"


def test_high_use_agent_utilities_are_p0() -> None:
    assert {
        "rg",
        "jq",
        "fd",
        "sd",
        "eza",
        "bat",
        "yq",
        "gh",
        "git",
    } <= _ids_by_priority("P0")
```

- [ ] **Step 4: Add description quality tests**

Add:

```python
def test_priority_tool_descriptions_name_replacements_or_value() -> None:
    tools = _tools_by_id()
    expected_fragments = {
        "rg": ("grep", ".gitignore"),
        "fd": ("find", ".gitignore"),
        "sd": ("sed", "literal"),
        "eza": ("ls", "Git"),
        "bat": ("cat", "syntax"),
        "yq": ("YAML", "JSON"),
        "jq": ("JSON", "filters"),
        "git": ("version control", "agents"),
        "brew": ("Homebrew", "immutable Linux"),
    }
    for tool_id, fragments in expected_fragments.items():
        desc = tools[tool_id].desc
        for fragment in fragments:
            assert fragment in desc, f"{tool_id}: missing {fragment!r} in {desc!r}"
        assert len(desc) <= 150, f"{tool_id}: description is too long"
```

- [ ] **Step 5: Add SDKMAN dependency tests**

Add:

```python
def test_java_tools_depend_on_sdkman() -> None:
    tools = _tools_by_id()
    for tool_id in ("java", "groovy", "springbootcli", "gradle", "maven"):
        assert "sdkman" in tools[tool_id].requires
```

- [ ] **Step 6: Add install method tests for new tool families**

Add:

```python
def test_agent_clis_use_supported_install_methods() -> None:
    tools = _tools_by_id()
    codex = tools["codex"]
    claude = tools["claude"]
    opencode = tools["opencode"]

    assert [m.kind for m in codex.methods] == ["script", "cask"]
    assert next(m for m in codex.methods if m.kind == "script").params["url"] == (
        "https://chatgpt.com/codex/install.sh"
    )
    assert next(m for m in codex.methods if m.kind == "cask").params["cask"] == "codex"

    assert [m.kind for m in claude.methods] == ["script", "cask"]
    assert next(m for m in claude.methods if m.kind == "script").params["url"] == (
        "https://claude.ai/install.sh"
    )
    assert next(m for m in claude.methods if m.kind == "cask").params["cask"] == "claude-code"

    assert {m.kind for m in opencode.methods} == {"script", "brew", "pacman", "node"}
    assert next(m for m in opencode.methods if m.kind == "script").params["url"] == (
        "https://opencode.ai/install"
    )
    assert next(m for m in opencode.methods if m.kind == "node").params["npm_pkg"] == (
        "opencode-ai"
    )


def test_container_tools_resolve_on_immutable_linux_without_native_writes() -> None:
    tools = _tools_by_id()
    immutable_fedora = Platform(os="fedora", arch="amd64", immutable=True, has_brew=True)

    assert [m.kind for m in resolve_methods(tools["docker"], immutable_fedora)] == ["brew"]
    assert [m.kind for m in resolve_methods(tools["podman"], immutable_fedora)] == ["brew"]
    assert [m.kind for m in resolve_methods(tools["colima"], immutable_fedora)] == ["brew"]


def test_jetbrains_toolbox_is_macos_cask_only() -> None:
    tools = _tools_by_id()
    toolbox = tools["jetbrains-toolbox"]
    assert toolbox.cmd == "jetbrains-toolbox"
    assert toolbox.category == "editor"
    assert [m.kind for m in toolbox.methods] == ["cask"]
    assert toolbox.methods[0].params["cask"] == "jetbrains-toolbox"
```

- [ ] **Step 7: Update runtime category expectation**

Replace `test_runtime_category_members` with:

```python
def test_runtime_category_members() -> None:
    runtimes = sorted(t.id for t in load_tools(REGISTRY) if t.category == "runtime")
    assert runtimes == [
        "bun",
        "deno",
        "fnm",
        "gradle",
        "groovy",
        "java",
        "maven",
        "sdkman",
        "springbootcli",
    ]
```

- [ ] **Step 8: Run tests and verify failure**

Run: `uv run pytest tests/test_registry.py -q`

Expected: failure because requested entries and updated descriptions are not yet in `installer/registry.toml`.

- [ ] **Step 9: Commit**

```bash
git add tests/test_registry.py
git commit -m "test: lock catalog refresh requirements"
```

### Task 4: Update Catalog Data

**Files:**
- Modify: `installer/registry.toml`
- Create: `docs/catalog-unsupported-tools.md`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: existing registry schema: `id`, `name`, `category`, `cmd`, `priority`, `audience`, `desc`, `requires`, and `[[tool.method]]`.
- Produces: supported new tool entries, updated descriptions, updated priorities, and a short unsupported-tool note.

- [ ] **Step 1: Update priority descriptions for existing high-use tools**

Edit these existing rows in `installer/registry.toml`:

```toml
id = "rg"
priority = "P0"
audience = "ai"
desc = "Replaces recursive grep with faster code search, .gitignore awareness, and focused output for agents."

id = "jq"
priority = "P0"
audience = "ai"
desc = "Turns JSON into precise filters so agents inspect only the fields they need."

id = "brew"
priority = "P0"
audience = "both"
desc = "Homebrew supplies user-space packages on macOS and immutable Linux when native writes are unsafe."

id = "fd"
priority = "P0"
audience = "ai"
desc = "Replaces most find usage with faster defaults, .gitignore awareness, and simpler paths."

id = "bat"
priority = "P0"
audience = "both"
desc = "Replaces cat for code review with syntax highlighting, paging, and Git-aware context."

id = "sd"
priority = "P0"
audience = "ai"
desc = "Replaces common sed substitutions with clearer syntax and safer literal defaults."

id = "eza"
priority = "P0"
audience = "both"
desc = "Replaces ls with clearer file metadata, Git status, and readable defaults."

id = "gh"
priority = "P0"
audience = "both"
desc = "Uses GitHub from the terminal so agents and users can inspect PRs, issues, and auth state."

id = "yq"
priority = "P0"
audience = "ai"
desc = "Queries YAML and JSON without ad hoc parsing, reducing noisy config inspection."
```

- [ ] **Step 2: Add git as an installable P0 tool**

Add this row near the existing git category tools:

```toml
[[tool]]
id = "git"
name = "Git"
category = "git"
cmd = "git"
priority = "P0"
audience = "both"
desc = "Core version control for users and agents; replaces manual file snapshots with auditable history."

[[tool.method]]
kind = "dnf"
package = "git"

[[tool.method]]
kind = "apt"
package = "git"

[[tool.method]]
kind = "pacman"
package = "git"

[[tool.method]]
kind = "brew"
formula = "git"
```

- [ ] **Step 3: Add human-facing agent CLI entries**

Add these rows in the `ai` category:

```toml
[[tool]]
id = "codex"
name = "Codex CLI"
category = "ai"
cmd = "codex"
priority = "P0"
audience = "human"
desc = "OpenAI coding agent for the user; coordinates local coding sessions rather than serving as an agent subtool."

[[tool.method]]
kind = "script"
url = "https://chatgpt.com/codex/install.sh"
shell = "sh"

[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "codex"

[[tool]]
id = "claude"
name = "Claude Code"
category = "ai"
cmd = "claude"
priority = "P0"
audience = "human"
desc = "Anthropic coding agent for the user; complements Codex and needs clear install ownership."

[[tool.method]]
kind = "script"
url = "https://claude.ai/install.sh"
shell = "bash"

[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "claude-code"

[[tool]]
id = "opencode"
name = "OpenCode"
category = "ai"
cmd = "opencode"
priority = "P0"
audience = "human"
desc = "Open source coding agent for the user, useful when teams want provider-flexible terminal workflows."

[[tool.method]]
kind = "script"
url = "https://opencode.ai/install"
shell = "bash"

[[tool.method]]
kind = "node"
npm_pkg = "opencode-ai"

[[tool.method]]
kind = "pacman"
package = "opencode"

[[tool.method]]
kind = "brew"
formula = "anomalyco/tap/opencode"
```

- [ ] **Step 4: Add container entries**

Add these rows in the `docker` category:

```toml
[[tool]]
id = "docker"
name = "Docker CLI"
category = "docker"
cmd = "docker"
priority = "P1"
audience = "both"
desc = "Controls Docker engines and contexts; agents use it to inspect containers without parsing desktop UI state."

[[tool.method]]
kind = "dnf"
package = "docker"

[[tool.method]]
kind = "apt"
package = "docker.io"

[[tool.method]]
kind = "pacman"
package = "docker"

[[tool.method]]
kind = "brew"
formula = "docker"

[[tool]]
id = "podman"
name = "Podman"
category = "docker"
cmd = "podman"
priority = "P1"
audience = "both"
desc = "Rootless container engine often safer on Linux and immutable desktops than daemon-first workflows."

[[tool.method]]
kind = "dnf"
package = "podman"

[[tool.method]]
kind = "apt"
package = "podman"

[[tool.method]]
kind = "pacman"
package = "podman"

[[tool.method]]
kind = "brew"
formula = "podman"

[[tool]]
id = "colima"
name = "Colima"
category = "docker"
cmd = "colima"
priority = "P1"
audience = "both"
desc = "Runs container runtimes in a lightweight VM, giving macOS and Linux users a Docker-compatible engine."

[[tool.method]]
kind = "brew"
formula = "colima"
```

- [ ] **Step 5: Update editor entries**

Change `vscode` to:

```toml
id = "vscode"
name = "Visual Studio Code"
category = "editor"
cmd = "code"
priority = "P1"
audience = "both"
desc = "GUI editor with a `code` CLI; on Bazzite prefer Flatpak or containers when native app writes are unsafe."
```

Add:

```toml
[[tool]]
id = "jetbrains-toolbox"
name = "JetBrains Toolbox"
category = "editor"
cmd = "jetbrains-toolbox"
priority = "P2"
audience = "human"
desc = "Manages JetBrains IDEs such as IntelliJ IDEA and PyCharm without modeling each IDE separately."

[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "jetbrains-toolbox"
```

- [ ] **Step 6: Add SDKMAN and Java tooling**

Add these rows in the `runtime` category:

```toml
[[tool]]
id = "sdkman"
name = "SDKMAN"
category = "runtime"
cmd = "sdk"
priority = "P1"
audience = "both"
desc = "User-space manager for Java and JVM-adjacent tools, avoiding system package writes when possible."

[[tool.method]]
kind = "script"
url = "https://get.sdkman.io?ci=true"
shell = "bash"

[[tool]]
id = "java"
name = "Java"
category = "runtime"
cmd = "java"
priority = "P1"
audience = "both"
desc = "JVM runtime required by Gradle, Maven, Groovy, and many enterprise projects; SDKMAN owns user-space setup."
requires = ["sdkman"]

[[tool.method]]
kind = "dnf"
package = "java-latest-openjdk"

[[tool.method]]
kind = "apt"
package = "default-jdk"

[[tool.method]]
kind = "pacman"
package = "jdk-openjdk"

[[tool.method]]
kind = "brew"
formula = "openjdk"

[[tool]]
id = "groovy"
name = "Groovy"
category = "runtime"
cmd = "groovy"
priority = "P2"
audience = "both"
desc = "JVM scripting language for build and automation scripts; SDKMAN keeps versions in user space."
requires = ["sdkman"]

[[tool.method]]
kind = "dnf"
package = "groovy"

[[tool.method]]
kind = "apt"
package = "groovy"

[[tool.method]]
kind = "pacman"
package = "groovy"

[[tool.method]]
kind = "brew"
formula = "groovy"

[[tool]]
id = "springbootcli"
name = "Spring Boot CLI"
category = "runtime"
cmd = "spring"
priority = "P2"
audience = "both"
desc = "Bootstraps and runs Spring projects from the terminal; SDKMAN keeps the CLI tied to JVM tooling."
requires = ["sdkman"]

[[tool.method]]
kind = "brew"
formula = "spring-boot"

[[tool]]
id = "gradle"
name = "Gradle"
category = "runtime"
cmd = "gradle"
priority = "P1"
audience = "both"
desc = "Build tool for JVM projects; SDKMAN helps avoid global system Gradle drift."
requires = ["sdkman"]

[[tool.method]]
kind = "dnf"
package = "gradle"

[[tool.method]]
kind = "apt"
package = "gradle"

[[tool.method]]
kind = "pacman"
package = "gradle"

[[tool.method]]
kind = "brew"
formula = "gradle"

[[tool]]
id = "maven"
name = "Maven"
category = "runtime"
cmd = "mvn"
priority = "P1"
audience = "both"
desc = "Standard Java build tool; SDKMAN keeps Maven aligned with the selected JVM."
requires = ["sdkman"]

[[tool.method]]
kind = "dnf"
package = "maven"

[[tool.method]]
kind = "apt"
package = "maven"

[[tool.method]]
kind = "pacman"
package = "maven"

[[tool.method]]
kind = "brew"
formula = "maven"
```

- [ ] **Step 7: Create unsupported requested-tools note**

Create `docs/catalog-unsupported-tools.md`:

```markdown
# Catalog Entries Not Installed Directly

The installer catalog only lists tools it can install with supported method kinds.

## codegraph

`codegraph` is not added as an installable catalog row in this pass. The local Codex plugin exposes Codegraph as an MCP capability, but this project does not yet have a verified standalone install method that fits the supported registry method kinds.

## PyCharm and IntelliJ IDEA

JetBrains IDEs are represented by JetBrains Toolbox. Toolbox is the installable management surface for PyCharm, IntelliJ IDEA, and related IDEs, so the catalog avoids duplicate per-IDE rows until the installer can model them cleanly across platforms.
```

- [ ] **Step 8: Run registry tests**

Run: `uv run pytest tests/test_registry.py -q`

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add installer/registry.toml docs/catalog-unsupported-tools.md tests/test_registry.py
git commit -m "feat: refresh ai dev tool catalog"
```

### Task 5: Full Verification And Design Review

**Files:**
- Modify only if a verification failure reveals a root cause.
- Test: whole repository.

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: validated final tree and a concise implementation note.

- [ ] **Step 1: Run all tests**

Run: `make test`

Expected: pytest passes with coverage.

- [ ] **Step 2: Run quality gates**

Run: `make validate`

Expected: pre-commit hooks pass: formatting, lint, types, security, and dead-code checks.

- [ ] **Step 3: Run the wizard smoke command**

Run: `make setup ARGS="--help"`

Expected: command prints setup help without importing invalid modules or crashing.

- [ ] **Step 4: Review the Doctor layout against the PRD**

Open `installer/wizard_app.py` and verify these facts in the code:

```text
DoctorScreen #doctor-body uses width, max-width, margin, padding, and border.
DoctorScreen renders sections named PATH Doctor, Audit, Safe fix preview, and Action.
DoctorScreen does not call the fix callback from on_mount.
DoctorScreen action_apply returns early after success.
UnifiedApp._views has no "fix" key.
```

- [ ] **Step 5: Review catalog descriptions against the PRD**

Run: `uv run pytest tests/test_registry.py::test_priority_tool_descriptions_name_replacements_or_value -q`

Expected: pass, confirming the P0 descriptions name the replacement or concrete value.

- [ ] **Step 6: Commit final fixes if verification required changes**

```bash
git add installer tests docs
git commit -m "fix: satisfy doctor catalog verification"
```

Skip this commit when Steps 1-5 pass without further changes.

## Self-Review

**Spec coverage:** The plan maps Doctor/Fix merge to Tasks 1-2, layout changes to Task 2, catalog priority and descriptions to Tasks 3-4, requested installable catalog additions to Task 4, unsupported requested entries to Task 4 documentation, immutable Linux resolver behavior to Task 3, and quality gates to Task 5.

**Red-flag scan:** No step uses deferred-work language. Each code-changing step includes exact snippets or exact assertions.

**Type consistency:** `DoctorScreen` keeps `guidance`, `applied`, and `error` as public test seams. `UnifiedApp` passes `fix_preview` and `fix` into the new constructor. Catalog tests use the existing `Tool`, `Method`, `Platform`, `load_tools`, and `resolve_methods` interfaces.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-05-doctor-catalog-refresh.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
