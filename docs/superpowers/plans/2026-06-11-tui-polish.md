# TUI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hover descriptions for categories and tools in the wizard menus, a color palette with semantic installed/missing tags, and accurate key hints in the checkbox prompts.

**Architecture:** Catalog text stays declarative — new `[[category]]` sections in `registry.toml` parsed by `model.load_categories`. The pure `selection.Choice` gains `tag` and `description` fields (fully tested); all questionary-specific rendering (styled title segments, `Style` palette, `instruction` text, `description=` hover) lives in `setup.py`, the untyped IO composition root outside the coverage gate.

**Tech Stack:** Python 3.11+ (uv), questionary 2.1.1 (already a dependency — `Choice.description` renders for the highlighted row by default, `title` accepts `(style, text)` tuple lists), pytest with 100% coverage gate, pyright strict.

**Per-commit gate (non-negotiable):** every commit must pass `make validate && make test` on the exact tree being committed. Never silence a check. NEVER run the real wizard/doctor against this machine's home — smoke-test only via `uv run setup.py --help`.

**Spec:** `docs/superpowers/specs/2026-06-11-tui-polish-design.md` (user-approved).

---

### Task 1: `[[category]]` registry sections + `model.load_categories`

**Files:**
- Modify: `installer/model.py` (new `load_categories`)
- Modify: `installer/registry.toml` (16 `[[category]]` sections before the first `[[tool]]`)
- Test: `tests/test_model.py`, `tests/test_registry.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_model.py` (the file already imports `Path`, `pytest`, and has the `_write(tmp_path, content)` helper; extend the import line to `from installer.model import Method, Tool, load_categories, load_tools`):

```python
def test_load_categories_reads_ordered_blurbs(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "search"
desc = "Find files and code at speed"
[[category]]
id = "data"
desc = "Query and transform JSON, YAML and CSV"
[[tool]]
id = "rg"
category = "search"
[[tool.method]]
kind = "brew"
formula = "ripgrep"
""",
    )
    assert load_categories(manifest) == {
        "search": "Find files and code at speed",
        "data": "Query and transform JSON, YAML and CSV",
    }


def test_load_categories_empty_when_no_sections(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "rg"
category = "search"
[[tool.method]]
kind = "brew"
formula = "ripgrep"
""",
    )
    assert load_categories(manifest) == {}


def test_load_categories_rejects_duplicate_id(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "search"
desc = "one"
[[category]]
id = "search"
desc = "two"
""",
    )
    with pytest.raises(ValueError, match="duplicate category id 'search'"):
        load_categories(manifest)


def test_load_categories_rejects_missing_id(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
desc = "no id here"
""",
    )
    with pytest.raises(ValueError, match="category section #0"):
        load_categories(manifest)


def test_load_categories_rejects_empty_desc(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[category]]
id = "search"
desc = ""
""",
    )
    with pytest.raises(ValueError, match="category 'search'"):
        load_categories(manifest)
```

Append to `tests/test_registry.py` (the file imports `load_tools`, `Platform`, `resolve_methods`, has `REGISTRY`; extend the model import to also bring `load_categories`):

```python
def test_every_used_category_has_a_blurb() -> None:
    blurbs = load_categories(REGISTRY)
    used = {t.category for t in load_tools(REGISTRY)}
    missing = sorted(used - set(blurbs))
    assert not missing, f"categories without a [[category]] blurb: {missing}"


def test_every_category_blurb_is_used_by_a_tool() -> None:
    blurbs = load_categories(REGISTRY)
    used = {t.category for t in load_tools(REGISTRY)}
    orphans = sorted(set(blurbs) - used)
    assert not orphans, f"[[category]] blurbs with no tools: {orphans}"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_model.py tests/test_registry.py -q --no-cov -k "categor or blurb"`
Expected: FAIL — `ImportError: cannot import name 'load_categories'`.

- [ ] **Step 3: Implement `load_categories`**

In `installer/model.py`, add after `load_tools` (module docstring's first line may mention categories too — update it to `"""Declarative tool catalog: Tool/Method model, category blurbs, and tomllib loaders."""`):

```python
def load_categories(manifest_path: str | Path) -> dict[str, str]:
    """Parse the registry's [[category]] sections into an ordered id -> desc map."""
    with open(manifest_path, "rb") as fh:
        data = tomllib.load(fh)
    blurbs: dict[str, str] = {}
    for index, row in enumerate(data.get("category", [])):
        cat_id = row.get("id")
        if not isinstance(cat_id, str) or not cat_id:
            raise ValueError(f"category section #{index} is missing a non-empty 'id'")
        desc = row.get("desc")
        if not isinstance(desc, str) or not desc:
            raise ValueError(f"category '{cat_id}' is missing a non-empty 'desc'")
        if cat_id in blurbs:
            raise ValueError(f"duplicate category id '{cat_id}'")
        blurbs[cat_id] = desc
    return blurbs
```

(`load_tools` reads `data.get("tool", [])`, so the new top-level sections do not affect it.)

- [ ] **Step 4: Add the 16 `[[category]]` sections to the registry**

In `installer/registry.toml`, insert after the header comment block and before the first `[[tool]]` (order matches the catalog's first-seen category order):

```toml
# Category blurbs shown in the wizard's category menu (hover description).
[[category]]
id = "pkg-mgr"
desc = "Package and environment managers"
[[category]]
id = "search"
desc = "Find files and code at speed"
[[category]]
id = "data"
desc = "Query and transform JSON, YAML and CSV"
[[category]]
id = "view"
desc = "View and render files in the terminal"
[[category]]
id = "text"
desc = "Stream text search-and-replace"
[[category]]
id = "git"
desc = "Git workflows, diffs and UIs"
[[category]]
id = "nav"
desc = "Jump around the filesystem"
[[category]]
id = "shell"
desc = "Prompt, env and shell ergonomics"
[[category]]
id = "dev"
desc = "Build, lint and docs helpers"
[[category]]
id = "sysinfo"
desc = "System monitors and disk usage"
[[category]]
id = "net"
desc = "HTTP clients"
[[category]]
id = "docker"
desc = "Container inspection and management"
[[category]]
id = "ai"
desc = "AI assistants in the terminal"
[[category]]
id = "runtime"
desc = "Language runtimes and version managers"
[[category]]
id = "security"
desc = "Secret scanning and security checks"
[[category]]
id = "editor"
desc = "GUI editors (macOS app installs)"
```

- [ ] **Step 5: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add installer/model.py installer/registry.toml tests/test_model.py tests/test_registry.py
git commit -m "feat: registry [[category]] blurbs and load_categories

One declarative one-liner per category, parsed into an ordered map;
two-way structural tests keep blurbs and used categories in sync.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `Choice.tag`/`Choice.description` + blurb threading

**Files:**
- Modify: `installer/selection.py` (Choice fields, `category_choices`, `tool_choices`)
- Modify: `installer/app.py` (`_choose_tools`, `run_wizard` keyword)
- Test: `tests/test_selection.py`, `tests/test_app.py`

- [ ] **Step 1: Update and write tests**

In `tests/test_selection.py`, REPLACE `test_category_choices_count_tools_and_start_unchecked` and `test_tool_choices_precheck_missing_only` with the versions below, and APPEND the other tests:

```python
def test_category_choices_count_tools_and_start_unchecked() -> None:
    tools = [_tool("rg", "search"), _tool("fd", "search"), _tool("jq", "data")]
    blurbs = {"search": "Find files and code at speed"}
    assert category_choices(tools, blurbs) == [
        Choice(
            id="search",
            label="search",
            checked=False,
            tag="2 tools",
            description="Find files and code at speed — rg, fd",
        ),
        Choice(id="data", label="data", checked=False, tag="1 tool", description="jq"),
    ]


def test_category_choices_without_blurbs_defaults_to_tool_list() -> None:
    tools = [_tool("rg", "search")]
    assert category_choices(tools) == [
        Choice(id="search", label="search", checked=False, tag="1 tool", description="rg")
    ]


def test_tool_choices_precheck_missing_only() -> None:
    tools = [_tool("rg", "search", desc="fast grep"), _tool("fd", "search")]
    statuses = [
        ToolStatus(tool=tools[0], installed=True),
        ToolStatus(tool=tools[1], installed=False),
    ]
    assert tool_choices(statuses) == [
        Choice(
            id="rg", label="rg — fast grep", checked=False, tag="installed", description="fast grep"
        ),
        Choice(id="fd", label="fd", checked=True, tag="missing", description=""),
    ]


def test_tool_choices_flag_verified_downloads() -> None:
    verified = Tool(
        id="rg",
        name="rg",
        category="search",
        cmd="rg",
        methods=(
            Method(
                kind="github_release",
                params={"repo": "a/rg", "asset": "x", "member": "rg", "checksum": "{asset}.sha256"},
            ),
        ),
        desc="fast grep",
    )
    statuses = [ToolStatus(tool=verified, installed=False)]
    assert tool_choices(statuses)[0].description == "fast grep · sha256-verified download"


def test_choice_tag_and_description_default_empty() -> None:
    choice = Choice(id="x", label="x", checked=False)
    assert choice.tag == ""
    assert choice.description == ""
```

In `tests/test_app.py`, append (the file has `FakePrompter`, `_tool`-style helpers, `run_wizard` imports — read its existing run_wizard tests first and reuse their fixture style for tools/platform/options/console; the key novelty is a prompter that records the category choices it was shown):

```python
def test_run_wizard_threads_category_blurbs_into_choices(tmp_path: Path) -> None:
    seen: list[list[Choice]] = []

    class RecordingPrompter:
        def select_categories(self, choices: list[Choice]) -> list[str]:
            seen.append(choices)
            return []

        def select_tools(self, choices: list[Choice]) -> list[str]:
            return []

        def confirm(self, message: str) -> bool:
            return True

    tools = [_tool("rg", installed=False)]  # adapt to this file's existing tool fixture helper
    console = Console(file=io.StringIO())
    run_wizard(
        tools,
        Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        RecordingPrompter(),
        console,
        Options(all=False, categories=(), yes=True),
        installed=lambda tool: False,
        category_blurbs={"search": "Find files and code at speed"},
    )
    assert seen[0][0].description.startswith("Find files and code at speed — ")
```

NOTE to implementer: adapt the fixture lines (`_tool(...)`, `Options(...)`, console construction, required run_wizard kwargs) to EXACTLY the conventions already in `tests/test_app.py` — read its existing `run_wizard` tests first. The assertions to keep verbatim: a recording prompter capturing `select_categories` choices, `category_blurbs={...}` passed to `run_wizard`, and the `description.startswith` check. Import `Choice` from `installer.selection` if not already imported there.

- [ ] **Step 2: Run to verify failures**

Run: `uv run pytest tests/test_selection.py tests/test_app.py -q --no-cov`
Expected: FAIL — `TypeError: Choice.__init__() got an unexpected keyword argument 'tag'`, `category_choices() takes 1 positional argument but 2 were given`, `run_wizard() got an unexpected keyword argument 'category_blurbs'`.

- [ ] **Step 3: Implement selection changes**

In `installer/selection.py`:

```python
@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    checked: bool
    tag: str = ""  # short status suffix (state/count), colored at the IO boundary
    description: str = ""  # hover text for the highlighted row
```

```python
def category_choices(
    tools: list[Tool], blurbs: dict[str, str] | None = None
) -> list[Choice]:
    """One unchecked choice per category: count as tag, blurb + tool ids on hover."""
    blurbs = blurbs or {}
    choices: list[Choice] = []
    for category in categories(tools):
        members = tools_in(tools, category)
        unit = "tool" if len(members) == 1 else "tools"
        ids = ", ".join(tool.id for tool in members)
        blurb = blurbs.get(category, "")
        description = f"{blurb} — {ids}" if blurb else ids
        choices.append(
            Choice(
                id=category,
                label=category,
                checked=False,
                tag=f"{len(members)} {unit}",
                description=description,
            )
        )
    return choices
```

```python
def _is_verified_download(tool: Tool) -> bool:
    return any("checksum" in method.params for method in tool.methods)


def tool_choices(statuses: list[ToolStatus]) -> list[Choice]:
    """One choice per tool; missing tools are pre-checked, installed ones are not."""
    choices: list[Choice] = []
    for status in statuses:
        tool = status.tool
        head = f"{tool.id} — {tool.desc}" if tool.desc else tool.id
        state = "installed" if status.installed else "missing"
        parts = [tool.desc] if tool.desc else []
        if _is_verified_download(tool):
            parts.append("sha256-verified download")
        # Pre-check the tools the user still needs (missing), not the ones present.
        choices.append(
            Choice(
                id=tool.id,
                label=head,
                checked=not status.installed,
                tag=state,
                description=" · ".join(parts),
            )
        )
    return choices
```

In `installer/app.py`, thread the blurbs (only the signature lines and the one call change):

```python
def _choose_tools(
    tools: list[Tool],
    prompter: Prompter,
    options: Options,
    installed: Callable[[Tool], bool],
    category_blurbs: dict[str, str] | None = None,
) -> list[Tool]:
    if options.all:
        return tools
    if options.categories:
        return [tool for tool in tools if tool.category in options.categories]
    chosen_categories = prompter.select_categories(category_choices(tools, category_blurbs))
    ...
```

`run_wizard` gains the keyword (after `on_mismatch`) and passes it through:

```python
def run_wizard(
    ...,
    on_mismatch: OnMismatch | None = None,
    category_blurbs: dict[str, str] | None = None,
) -> Summary | None:
    ...
    selected = _choose_tools(tools, prompter, options, installed, category_blurbs)
```

(Docstring of run_wizard: add one line — "category_blurbs feeds the category menu's hover descriptions.")

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all green, coverage 100%. (The `blurbs or {}` / `category_blurbs=None` defaults keep every existing caller and test working.)

- [ ] **Step 5: Commit**

```bash
git add installer/selection.py installer/app.py tests/test_selection.py tests/test_app.py
git commit -m "feat: choices carry hover descriptions and status tags

Choice gains tag (state/count, colored at the IO boundary) and
description (hover text). Categories describe themselves with their
registry blurb plus tool list; tools expose desc and a
sha256-verified note. run_wizard threads the blurbs through.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: setup.py palette, styled tags, hover wiring, accurate keys

**Files:**
- Modify: `setup.py` (no tests — IO composition root outside the coverage gate, per its module docstring)

- [ ] **Step 1: Implement the boundary rendering**

In `setup.py`, extend the model import to `from installer.model import Tool, load_categories, load_tools`, then add module constants after `_RC_PATHS`:

```python
_STYLE = questionary.Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "bold"),
        ("selected", "fg:green"),
        ("instruction", "fg:#858585"),
        ("description", "fg:#858585 italic"),
        ("tag-installed", "fg:green"),
        ("tag-missing", "fg:yellow"),
        ("tag-dim", "fg:#858585"),
    ]
)
_CHECKBOX_KEYS = "(↑/↓ move, <space> toggle, <a> all, <i> invert, <enter> confirm)"


def _tag_class(tag: str) -> str:
    if tag == "installed":
        return "tag-installed"
    if tag == "missing":
        return "tag-missing"
    return "tag-dim"


def _title(choice: Choice) -> list[tuple[str, str]]:
    segments = [("class:text", choice.label)]
    if choice.tag:
        segments.append((f"class:{_tag_class(choice.tag)}", f"  ({choice.tag})"))
    return segments
```

Replace `_ask_checkbox` and add `style=` to the other prompts:

```python
def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[
            questionary.Choice(
                title=_title(c), value=c.id, checked=c.checked, description=c.description or None
            )
            for c in choices
        ],
        instruction=_CHECKBOX_KEYS,
        style=_STYLE,
    ).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return list(answer)


def _ask_confirm(message: str) -> bool:
    answer = questionary.confirm(message, default=True, style=_STYLE).ask()
    if answer is None:  # questionary returns None on Ctrl+C / Ctrl+D at the prompt
        raise KeyboardInterrupt
    return bool(answer)


def _ask_select(message: str, choices: list[tuple[str, str]]) -> str:
    answer = questionary.select(
        message,
        choices=[questionary.Choice(title=title, value=value) for title, value in choices],
        style=_STYLE,
    ).ask()
    if answer is None:  # Ctrl+C / Ctrl+D
        raise KeyboardInterrupt
    return str(answer)
```

In `main()`, pass the blurbs (one line changes):

```python
    summary = run_wizard(
        tools,
        platform,
        prompter,
        console,
        options,
        on_mismatch=_ask_mismatch,
        category_blurbs=load_categories(_REGISTRY),
    )
```

- [ ] **Step 2: Smoke-test without touching the home directory**

Run: `uv run setup.py --help`
Expected: argparse help prints, exit 0 (proves setup.py imports and parses cleanly — do NOT run the wizard itself).

- [ ] **Step 3: Run the full gate**

Run: `make validate && make test`
Expected: all green (setup.py is ruff/pyright-checked by validate even though untested).

- [ ] **Step 4: Commit**

```bash
git add setup.py
git commit -m "feat: wizard palette, colored status tags, hover descriptions

questionary Style shared by all prompts; checkbox rows render the
label plus a colored tag (green installed / yellow missing / dim
counts) and show the highlighted row's description; instruction text
now lists exactly the keys questionary binds (no <o> - it never
existed).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (controller)

- `git log --oneline` shows 3 coherent commits.
- `make validate && make test` green on the final tree, coverage 100%.
- `git status --short` clean.
- Dispatch the final whole-feature review.
- Do NOT push (no remote; publish is owner-only).
- Suggest the user verifies visually: `make setup ARGS="--categories editor"` and hover the menus.
