# SP3: PATH Hygiene (rc dup-cleaning + post-install verify) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Detect and (with preview + confirm) remove duplicate `PATH` `export` lines that the official installers (bun/pnpm/fnm) append to `.bashrc`/`.zshrc` for a directory `~/.myshellrc` already manages, and automatically run the doctor audit after an install so the user ends on a clean PATH report.

**Architecture:** A pure module `installer/rcclean.py` finds duplicate PATH-export line indices in an rc file's text: it resolves `export VAR=...` assignments declared in the same file (so `$BUN_INSTALL/bin`, `$PNPM_HOME` expand), skips our own managed/source blocks, and flags any PATH entry that resolves to a managed dir. An app orchestrator previews the matches, confirms, and strips them. The post-install verify reuses the existing `audit_path`.

**Tech Stack:** Python (uv), pytest. Gates: ruff, pyright strict, bandit, vulture, shellcheck; 100% coverage on `installer/`.

**Non-negotiables:** English only. No gate bypass. Coherent commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. This edits user shell files — only ever remove flagged PATH-export lines, never other content, and only after a previewed confirm.

---

## Background

`installer/shellrc.py` markers: `_PATH_BEGIN = "# >>> tools-installer path >>>"`, `_PATH_END`, `_SOURCE_BEGIN = "# >>> tools-installer source >>>"`, `_SOURCE_END`. `collect_bin_dirs(tools, platform, default) -> list[Path]` returns the managed (expanduser'd) bin dirs. `installer/doctor.py:audit_path(bin_dirs, path_value, exists) -> DoctorReport` already classifies `missing`/`broken`/`duplicated`. `installer/app.py` has `configure_path`, `run_doctor`, `run_uninstall`. `installer/render.py` renders reports; `installer/prompt.py` injects confirm. Installer-added lines look like:
`export PATH="$BUN_INSTALL/bin:$PATH"` (with a prior `export BUN_INSTALL="$HOME/.bun"`), `export PATH="$PNPM_HOME:$PATH"`, `export PATH="$HOME/.local/share/fnm:$PATH"`.

---

## Task 1: `installer/rcclean.py` — find duplicate PATH lines (pure)

**Files:**
- Create: `installer/rcclean.py`
- Test: `tests/test_rcclean.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rcclean.py`:

```python
from pathlib import Path

from installer.rcclean import find_duplicate_path_lines, strip_lines


def test_flags_literal_home_path_duplicate():
    rc = 'export PATH="$HOME/.bun/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [0]


def test_resolves_var_assigned_earlier_in_the_file():
    rc = (
        "# bun\n"
        'export BUN_INSTALL="$HOME/.bun"\n'
        'export PATH="$BUN_INSTALL/bin:$PATH"\n'
    )
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    # Only the PATH line (index 2) is a duplicate; the assignment line is left alone.
    assert find_duplicate_path_lines(rc, managed, env) == [2]


def test_resolves_pnpm_home_style():
    rc = 'export PNPM_HOME="$HOME/.local/share/pnpm"\nexport PATH="$PNPM_HOME:$PATH"\n'
    managed = {Path("/home/u/.local/share/pnpm")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [1]


def test_expands_leading_tilde():
    rc = 'export PATH="~/.bun/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == [0]


def test_ignores_unmanaged_path_lines():
    rc = 'export PATH="$HOME/.cargo/bin:$PATH"\n'
    managed = {Path("/home/u/.bun/bin")}
    env = {"HOME": "/home/u"}
    assert find_duplicate_path_lines(rc, managed, env) == []


def test_ignores_non_path_lines():
    rc = 'alias ll="ls -la"\nexport EDITOR=vim\n'
    assert find_duplicate_path_lines(rc, {Path("/home/u/.bun/bin")}, {"HOME": "/home/u"}) == []


def test_excludes_our_own_managed_block():
    rc = (
        "# >>> tools-installer path >>>\n"
        'export PATH="/home/u/.bun/bin:$PATH"\n'
        "# <<< tools-installer path <<<\n"
    )
    managed = {Path("/home/u/.bun/bin")}
    assert find_duplicate_path_lines(rc, managed, {"HOME": "/home/u"}) == []


def test_unresolved_var_is_not_flagged():
    # $UNKNOWN cannot resolve -> never a false positive.
    rc = 'export PATH="$UNKNOWN/bin:$PATH"\n'
    assert find_duplicate_path_lines(rc, {Path("/home/u/.bun/bin")}, {"HOME": "/home/u"}) == []


def test_strip_lines_removes_only_given_indices():
    text = "a\nb\nc\nd\n"
    assert strip_lines(text, [1, 3]) == "a\nc\n"


def test_strip_lines_empty_is_identity():
    assert strip_lines("a\nb\n", []) == "a\nb\n"
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_rcclean.py -q`
Expected: FAIL — `No module named 'installer.rcclean'`.

- [ ] **Step 3: Implement `installer/rcclean.py`**

```python
"""Find and strip duplicate PATH-export lines in shell rc files.

Detection resolves `export VAR=...` assignments declared earlier in the same file
(so installer lines like `$BUN_INSTALL/bin` expand), skips our own managed blocks,
and flags any PATH entry that resolves to a directory we already manage. Used to
clean the redundant lines bun/pnpm/fnm append to .bashrc/.zshrc.
"""

import re
from collections.abc import Mapping
from pathlib import Path

_MANAGED_BEGINS = ("# >>> tools-installer path >>>", "# >>> tools-installer source >>>")
_MANAGED_ENDS = ("# <<< tools-installer path <<<", "# <<< tools-installer source <<<")
_ASSIGN = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.+?)\s*$')
_PATH_EXPORT = re.compile(r'^\s*(?:export\s+)?PATH=(.+?)\s*$')
_VAR = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)')


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _expand(value: str, env: Mapping[str, str]) -> str | None:
    """Expand $VAR/${VAR} and a leading ~ using env. Returns None if a var is unknown."""
    resolved = True

    def repl(match: re.Match[str]) -> str:
        nonlocal resolved
        name = match.group(1) or match.group(2)
        if name not in env:
            resolved = False
            return ""
        return env[name]

    expanded = _VAR.sub(repl, value)
    if not resolved:
        return None
    if expanded.startswith("~"):
        home = env.get("HOME", "")
        expanded = home + expanded[1:] if home else expanded
    return expanded


def _managed_line_indices(lines: list[str]) -> set[int]:
    """Indices inside any tools-installer managed/source block (markers included)."""
    blocked: set[int] = set()
    depth_start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in _MANAGED_BEGINS:
            depth_start = index
        elif stripped in _MANAGED_ENDS and depth_start is not None:
            blocked.update(range(depth_start, index + 1))
            depth_start = None
    return blocked


def find_duplicate_path_lines(
    rc_text: str, managed_dirs: set[Path], env: Mapping[str, str]
) -> list[int]:
    """Line indices whose PATH export adds a directory already in managed_dirs."""
    lines = rc_text.split("\n")
    blocked = _managed_line_indices(lines)
    local: dict[str, str] = dict(env)
    targets = {str(directory) for directory in managed_dirs}
    flagged: list[int] = []
    for index, line in enumerate(lines):
        if index in blocked:
            continue
        path_match = _PATH_EXPORT.match(line)
        if path_match:
            value = _unquote(path_match.group(1))
            for segment in value.split(":"):
                if segment in ("$PATH", "${PATH}"):
                    continue
                expanded = _expand(segment, local)
                if expanded is not None and expanded in targets:
                    flagged.append(index)
                    break
            continue
        assign = _ASSIGN.match(line)
        if assign:
            expanded = _expand(_unquote(assign.group(2)), local)
            if expanded is not None:
                local[assign.group(1)] = expanded
    return flagged


def strip_lines(rc_text: str, indices: list[int]) -> str:
    """Return rc_text with the given line indices removed."""
    drop = set(indices)
    lines = rc_text.split("\n")
    return "\n".join(line for index, line in enumerate(lines) if index not in drop)
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_rcclean.py -q`
Expected: PASS. If any branch (e.g. the unknown-var `None` path, the assignment overlay, the managed-block skip) is uncovered, ADD a focused test rather than a pragma.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/rcclean.py tests/test_rcclean.py
git commit -m "feat: detect duplicate PATH-export lines in shell rc files

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `app.clean_rc_duplicates` orchestrator + renderer

**Files:**
- Modify: `installer/render.py` (preview renderer)
- Modify: `installer/app.py` (orchestrator)
- Test: `tests/test_render.py`, `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_render.py`:

```python
def test_render_rc_duplicates_lists_files_and_lines():
    from installer.render import render_rc_duplicates

    console = Console(record=True, width=100)
    render_rc_duplicates({Path("/h/.zshrc"): ['export PATH="$BUN_INSTALL/bin:$PATH"']}, console)
    text = console.export_text()
    assert "/h/.zshrc" in text
    assert "BUN_INSTALL" in text


def test_render_rc_duplicates_says_clean_when_empty():
    from installer.render import render_rc_duplicates

    console = Console(record=True, width=100)
    render_rc_duplicates({}, console)
    assert "No duplicate" in console.export_text()
```

Add to `tests/test_app.py`:

```python
def test_clean_rc_duplicates_removes_after_confirm(tmp_path, monkeypatch):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".zshrc"
    rc.write_text(
        'export BUN_INSTALL="$HOME/.bun"\n'
        'export PATH="$BUN_INSTALL/bin:$PATH"\n'
        'alias ll="ls -la"\n'
    )
    console, _buf = _console()
    removed = clean_rc_duplicates(
        [rc], {tmp_path / ".bun" / "bin"}, {"HOME": str(tmp_path)}, console,
        confirm=lambda _m: True,
    )
    assert removed == {rc: ['export PATH="$BUN_INSTALL/bin:$PATH"']}
    text = rc.read_text()
    assert 'export PATH="$BUN_INSTALL/bin:$PATH"' not in text
    assert 'export BUN_INSTALL="$HOME/.bun"' in text  # assignment kept
    assert 'alias ll="ls -la"' in text  # unrelated content kept


def test_clean_rc_duplicates_declined_changes_nothing(tmp_path, monkeypatch):
    from installer.app import clean_rc_duplicates

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".zshrc"
    original = 'export PATH="$HOME/.bun/bin:$PATH"\n'
    rc.write_text(original)
    console, _buf = _console()
    removed = clean_rc_duplicates(
        [rc], {tmp_path / ".bun" / "bin"}, {"HOME": str(tmp_path)}, console,
        confirm=lambda _m: False,
    )
    assert removed == {}
    assert rc.read_text() == original


def test_clean_rc_duplicates_nothing_to_do_skips_confirm(tmp_path):
    from installer.app import clean_rc_duplicates

    rc = tmp_path / ".zshrc"
    rc.write_text('alias ll="ls -la"\n')
    console, _buf = _console()

    def fail_confirm(_message: str) -> bool:
        raise AssertionError("confirm must not be called when there is nothing to remove")

    removed = clean_rc_duplicates([rc], {tmp_path / ".bun" / "bin"}, {}, console, confirm=fail_confirm)
    assert removed == {}
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_render.py tests/test_app.py -q`
Expected: FAIL — `render_rc_duplicates`/`clean_rc_duplicates` don't exist.

- [ ] **Step 3: Implement `render_rc_duplicates`**

Add to `installer/render.py`:

```python
def render_rc_duplicates(found: dict[Path, list[str]], console: Console) -> None:
    """Preview duplicate PATH lines found per rc file (dry run)."""
    if not found:
        console.print("No duplicate PATH lines found in your shell rc files.")
        return
    console.print("These PATH lines duplicate directories already managed; they can be removed:")
    for rc_path, lines in found.items():
        console.print(f"  {rc_path}:")
        for line in lines:
            console.print(f"    {line}")
```

(`Path` is already imported in render.py from SP for `render_uninstall`.)

- [ ] **Step 4: Implement `clean_rc_duplicates`**

Add to `installer/app.py`. Extend imports:

```python
from installer.rcclean import find_duplicate_path_lines, strip_lines
from installer.render import (
    render_audit,
    render_doctor,
    render_rc_duplicates,
    render_summary,
    render_uninstall,
)
```

Add the function (use `Mapping` from `collections.abc`, already importable):

```python
def clean_rc_duplicates(
    rc_paths: list[Path],
    managed_dirs: set[Path],
    env: Mapping[str, str],
    console: Console,
    *,
    confirm: Callable[[str], bool],
) -> dict[Path, list[str]]:
    """Preview duplicate PATH lines in each rc file, confirm, then strip them.

    Returns the removed lines per file ({} if none found or the user declined).
    """
    found: dict[Path, list[str]] = {}
    indices_by_file: dict[Path, list[int]] = {}
    for rc_path in rc_paths:
        if not rc_path.exists():
            continue
        text = rc_path.read_text()
        indices = find_duplicate_path_lines(text, managed_dirs, env)
        if indices:
            lines = text.split("\n")
            found[rc_path] = [lines[index] for index in indices]
            indices_by_file[rc_path] = indices
    render_rc_duplicates(found, console)
    if not found:
        return {}
    if not confirm("Remove these duplicate PATH lines?"):
        return {}
    for rc_path, indices in indices_by_file.items():
        rc_path.write_text(strip_lines(rc_path.read_text(), indices))
    return found
```

Add `from collections.abc import Callable, Mapping` (Callable is already imported — add Mapping to that import).

- [ ] **Step 5: Run, confirm PASS**

Run: `uv run pytest tests/test_render.py tests/test_app.py -q`
Expected: PASS.

- [ ] **Step 6: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/render.py installer/app.py tests/test_render.py tests/test_app.py
git commit -m "feat: add clean_rc_duplicates preview/confirm orchestrator

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Post-install verify + cleaning wired into `setup.py`

Composition-root wiring (no unit tests; `setup.py` is out of coverage, ruff-gated). After a successful wizard + `configure_path`, run the doctor audit and offer rc-cleaning.

**Files:**
- Modify: `setup.py`

- [ ] **Step 1: Add a post-install verify + clean helper**

In `setup.py`, add (it composes already-tested pieces):

```python
def _verify_and_clean(console: Console, tools: list, platform, *, assume_yes: bool) -> None:
    from installer.app import clean_rc_duplicates, run_doctor
    from installer.shellrc import collect_bin_dirs

    run_doctor(
        tools, console, platform=platform, default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""), exists=Path.is_dir,
        myshellrc_path=_MYSHELLRC, rc_paths=_RC_PATHS, fix=False,
    )
    managed = set(collect_bin_dirs(tools, platform, _DEFAULT_BIN_DIR))
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    clean_rc_duplicates(_RC_PATHS, managed, os.environ, console, confirm=confirm)
```

(`run_doctor` here uses `fix=False` — audit only; `link_mode` is irrelevant when not fixing.)

- [ ] **Step 2: Call it after a successful install in `main`**

In `main`, after the post-wizard `configure_path(...)` block, add:

```python
    _verify_and_clean(console, tools, platform, assume_yes=options.yes)
```

- [ ] **Step 3: Validate (no real-home mutation)**

Run: `make validate && make test`
Expected: green at 100% (only `setup.py` changed among non-test files).

Run: `uv run setup.py --help` to confirm it still parses. DO NOT run a real install/wizard against this home.

- [ ] **Step 4: Commit**

```bash
git add setup.py
git commit -m "feat: verify PATH and offer rc-duplicate cleanup after installs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Document PATH hygiene

**Files:**
- Modify: `README.md` (PATH doctor section)

- [ ] **Step 1: Extend the PATH doctor section**

In `README.md`, in the "PATH doctor" section, add a bullet:

```
- After an install it audits your live PATH and, when a tool's own installer added
  a duplicate `export PATH` line to `.bashrc`/`.zshrc` for a directory the managed
  `~/.myshellrc` already covers, previews those lines and offers to remove them
  (your own content is never touched).
```

- [ ] **Step 2: Validate and commit**

Run: `make validate && make test`

```bash
git add README.md
git commit -m "docs: describe post-install PATH verify and rc-duplicate cleanup

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final check

- `make validate && make test` green at 100% on the final tree.
- `rcclean.find_duplicate_path_lines` resolves in-file `export VAR=` assignments, skips our managed blocks, and never flags unmanaged or non-PATH lines.
- `clean_rc_duplicates` previews + confirms before editing, and removes only flagged lines.
- Post-install verify runs the audit and offers cleaning.
- Update `roadmap-status.md` memory: SP3 done → the whole script-installer-tier + PATH-hygiene feature is complete.
