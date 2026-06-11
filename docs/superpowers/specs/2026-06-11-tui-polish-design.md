# TUI Polish: Hover Descriptions, Color Palette, Accurate Key Hints — Design

Date: 2026-06-11
Status: approved

## Goal

Make the wizard's two checkbox menus informative and readable: hovering a
category or tool shows a live description line, semantic colors distinguish
installed/missing states, and the prompt advertises exactly the keys that work.

## Background facts (verified against questionary 2.1.1 source)

- `questionary.Choice` accepts `description=` — rendered at the bottom of the
  prompt for the currently highlighted item, updating as the cursor moves.
  This is the "details on hover" mechanism; no extra dependency needed.
- `Choice.title` accepts a list of `(style_class, text)` tuples — per-segment
  coloring inside a row.
- `questionary.checkbox(..., style=Style([...]), instruction="...")` controls
  the palette and the help line.
- The checkbox binds ONLY: arrows / ctrl-n / ctrl-p (move), `<space>` (toggle),
  `<a>` (toggle all), `<i>` (invert), `<enter>` (confirm), ctrl-c/ctrl-q
  (abort). **There is no `<o>` binding and the API exposes no way to add
  custom keys.** The user-reported "`<o>` doesn't work" is resolved by showing
  accurate instruction text, not by binding `<o>`.

## Decisions (user-approved)

1. Category hover text = hand-written one-line blurb + auto-derived tool list;
   blurbs live in **registry.toml** as `[[category]]` sections (declarative,
   single catalog file).
2. Color depth = global palette **plus** semantic in-row colors (green
   `installed`, yellow `missing`, dim counts).
3. `<o>`: no binding (user was exploring keys); fix is an accurate
   `instruction` string on our prompts.
4. Approach A: structured `Choice` fields in the pure layer; all
   questionary-specific styling stays in `setup.py` (the untyped, untested IO
   boundary — its module docstring already declares this role).

## Section 1 — Registry categories + loader

`installer/registry.toml` gains one `[[category]]` section per category,
placed before the first `[[tool]]`, in catalog order:

```toml
[[category]]
id = "pkg-mgr"
desc = "Package and environment managers"
```

All 16 categories get a blurb (final wording at implementation time, one line
each, sentence case, no trailing period):

| id | desc |
| --- | --- |
| pkg-mgr | Package and environment managers |
| search | Find files and code at speed |
| view | View and render files in the terminal |
| git | Git workflows, diffs and UIs |
| docker | Container inspection and management |
| data | Query and transform JSON, YAML and CSV |
| text | Stream text search-and-replace |
| nav | Jump around the filesystem |
| runtime | Language runtimes and version managers |
| shell | Prompt, env and shell ergonomics |
| dev | Build, lint and docs helpers |
| sysinfo | System monitors and disk usage |
| security | Secret scanning and security checks |
| net | HTTP clients |
| ai | AI assistants in the terminal |
| editor | GUI editors (macOS app installs) |

New `model.load_categories(manifest_path) -> dict[str, str]` (insertion-ordered
id → desc). Validation: `ValueError` on a duplicate id, a missing/empty `id`,
or a missing/empty `desc`. `load_tools` is unchanged (the two readers parse the
same file independently).

Menu order is untouched: `selection.categories` still derives first-seen order
from tools; `[[category]]` sections supply text only.

Structural tests (two-way honesty, like the MACOS_ONLY pattern):
- every category used by a tool has a `[[category]]` blurb;
- every `[[category]]` id is used by at least one tool.

## Section 2 — Selection layer + threading

`selection.Choice` gains two defaulted fields (frozen dataclass):

```python
@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    checked: bool
    tag: str = ""          # short status suffix, colored at the boundary
    description: str = ""  # hover text shown for the highlighted row
```

- `category_choices(tools, blurbs: dict[str, str])` → per category:
  `label="search"`, `tag="4 tools"` (singular handled as today),
  `description="Find files and code at speed — ripgrep, fd, fzf, ast-grep"`
  (blurb, em dash, comma-joined tool ids in catalog order). A category with no
  blurb entry gets `description=` just the tool list (defensive; the
  structural test makes this unreachable for the shipped registry).
  The count moves from the label into `tag` (the old `"search (4 tools)"`
  label becomes `label="search"` + `tag="4 tools"`).
- `tool_choices(statuses)` → `label` keeps today's `"id — desc"` head;
  `tag="installed"|"missing"` (moves out of the label string);
  `description=tool.desc`, plus the suffix `" · sha256-verified download"`
  when any of the tool's methods declares a `checksum` param.
- `app._choose_tools` and `app.run_wizard` gain a
  `category_blurbs: dict[str, str] | None = None` keyword (None → `{}`), so
  existing callers and tests are untouched. `setup.py` calls
  `load_categories(...)` next to its existing `load_tools(...)` and passes the
  result.
- `prompt.py` is unchanged (the Protocol passes `Choice` through).

## Section 3 — Boundary styling + accurate keys (setup.py)

One module-level `questionary.Style` shared by all prompts. Style classes and
palette (exact hexes at implementer's discretion; intent fixed):

- `qmark` / `pointer`: cyan
- `highlighted`: bold
- `selected` (checked rows): green
- `instruction`: dim
- `description` (hover line): dim italic
- custom classes for tags: `tag-installed` green, `tag-missing` yellow,
  `tag-dim` dim (category counts)

`_ask_checkbox` builds, per choice:

```python
questionary.Choice(
    title=[("class:text", c.label)] + ([("class:tag-...", f"  ({c.tag})")] if c.tag else []),
    value=c.id,
    checked=c.checked,
    description=c.description or None,
)
```

Tag class is picked by content: `installed` → `tag-installed`, `missing` →
`tag-missing`, anything else → `tag-dim`. The rendered text keeps the
parenthesized form (`ripgrep — fast grep  (missing)`) so the menu reads the
same as today, now colored.

Checkbox prompts pass
`instruction="(↑/↓ move, <space> toggle, <a> all, <i> invert, <enter> confirm)"`.
`_ask_select` and `_ask_confirm` receive the same `style=` palette (no other
changes).

`setup.py` remains outside the coverage gate (IO composition root). Everything
assertable — blurb loading/validation, choice construction, descriptions,
tags — lives in `model.py`/`selection.py` under the 100% gate.

## Error handling

- `load_categories`: `ValueError` with the offending id for duplicates;
  `ValueError` naming the section index for missing/empty `id`/`desc`.
- Missing blurb at runtime: category falls back to tool-list-only description
  (never raises mid-wizard).
- No behavior change to selection semantics, ordering, pre-checking, or any
  prompt flow.

## Testing

- `test_model.py`: load_categories happy path (order preserved), duplicate id,
  missing id, empty desc.
- `test_selection.py`: new fields' defaults; category tag/description
  composition (incl. singular "1 tool" and missing-blurb fallback); tool
  tag/state split; verified-download suffix present/absent.
- `test_registry.py`: two-way category/blurb honesty tests; existing tests
  updated only where `category_choices` gained the blurbs argument.
- `test_app.py`: run_wizard accepts and threads `category_blurbs` (one test);
  existing tests unchanged (defaulted param).
- No tests for setup.py styling (established boundary convention).

## Out of scope

- Custom keybindings (questionary checkbox exposes none).
- Menu re-ordering, search/filter, rich/textual migration.
- Coloring render.py output (post-install reports) — separate concern.
