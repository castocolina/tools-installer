# pip/npm ban (environment policy) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, removable policy that bans the unmanaged package installers (`pip`/`pip3` → `uv`, `npm` → `pnpm`) via PATH shims plus interactive-shell aliases, surfaced through `make guard`/`make unguard`, an optional wizard prompt, the doctor, and uninstall.

**Architecture:** A new pure module `installer/guards.py` holds all logic and file operations (shim scripts, alias block, install/remove, doctor helpers). Orchestration lives in `installer/app.py` (`run_guard`, doctor + uninstall integration); the IO boundary (`setup.py`) wires flags, the wizard prompt, and rc-file targeting. All guard functions take an explicit `shim_dir` (the managed bin dir, `~/.local/bin`) so nothing hard-codes `home`.

**Tech Stack:** Python 3, uv toolchain, pytest (100% coverage gate), ruff/pyright/bandit/vulture/shellcheck via `make validate`. The generated shim is POSIX `sh`, validated in tests with `sh -n`.

**Spec:** `docs/superpowers/specs/2026-06-12-pip-npm-ban-design.md`

---

## File structure

- **Create** `installer/guards.py` — pure: `BANNED`, shim builders, install/remove shims, alias block + write/remove, `guard_status`, `guard_path_warning`.
- **Create** `tests/test_guards.py` — full coverage of `guards.py`.
- **Modify** `installer/shellrc.py` — extract a generic `strip_block(content, begin, end)`; refactor `remove_managed_block` to use it (guards reuses it).
- **Modify** `tests/test_shellrc.py` — test `strip_block`.
- **Modify** `installer/render.py` — `render_guard`, `render_guard_status`.
- **Modify** `tests/test_render.py` — tests for the two renderers.
- **Modify** `installer/app.py` — `run_guard`; guard section in `run_doctor`; guard cleanup in `run_uninstall`.
- **Modify** `tests/test_app.py` — tests for the three.
- **Modify** `installer/cli.py` + `tests/test_cli.py` — `--guard`/`--unguard` options.
- **Modify** `setup.py` — `_run_guard`, `_ban_rc_paths`, optional wizard prompt, dispatch.
- **Modify** `Makefile` — `guard` / `unguard` targets.
- **Modify** `README.md`, `docs/TROUBLESHOOTING.md` — document the ban.

> **Test capture convention used throughout:** render/app tests build a recording console with
> ```python
> import io
> from rich.console import Console
> buf = io.StringIO()
> console = Console(file=buf, width=100)
> ```
> then assert on `buf.getvalue()`.

---

## Task 1: Generic `strip_block` in shellrc

**Files:**
- Modify: `installer/shellrc.py`
- Test: `tests/test_shellrc.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_shellrc.py` (and add `strip_block` to its import from `installer.shellrc`):

```python
def test_strip_block_removes_the_last_well_formed_block():
    begin, end = "# >>> b >>>", "# <<< b <<<"
    text = f"keep\n{begin}\ninside\n{end}\ntail"
    assert strip_block(text, begin, end) == "keep\ntail"


def test_strip_block_absent_marker_is_unchanged():
    assert strip_block("nothing here", "# >>> b >>>", "# <<< b <<<") == "nothing here"


def test_strip_block_orphan_begin_is_unchanged():
    begin, end = "# >>> b >>>", "# <<< b <<<"
    text = f"keep\n{begin}\nno end marker"
    assert strip_block(text, begin, end) == text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_shellrc.py -k strip_block -v`
Expected: FAIL with `ImportError: cannot import name 'strip_block'`.

- [ ] **Step 3: Add `strip_block` and refactor `remove_managed_block`**

In `installer/shellrc.py`, add after `apply_block`:

```python
def strip_block(content: str, begin: str, end: str) -> str:
    """Return content with the last begin..end block removed; unchanged if absent.

    Mirrors apply_block's last-begin pairing, so an orphan begin (no matching
    end) is left untouched rather than eating the rest of the file.
    """
    lines = content.split("\n")
    if begin not in lines:
        return content
    start = max(index for index, line in enumerate(lines) if line == begin)
    for stop in range(start, len(lines)):
        if lines[stop] == end:
            return "\n".join(lines[:start] + lines[stop + 1 :])
    return content
```

Then replace the body of `remove_managed_block` with a delegation:

```python
def remove_managed_block(path: Path) -> None:
    """Strip the managed PATH block from `path`, preserving the rest. Idempotent.

    A missing file, or a file without the block, is left untouched.
    """
    if not path.exists():
        return
    original = path.read_text()
    stripped = strip_block(original, _PATH_BEGIN, _PATH_END)
    if stripped != original:
        path.write_text(stripped)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_shellrc.py -v`
Expected: PASS (new `strip_block` tests and all existing `remove_managed_block` tests).

- [ ] **Step 5: Commit**

```bash
git add installer/shellrc.py tests/test_shellrc.py
git commit -m "refactor: extract generic strip_block from remove_managed_block"
```

---

## Task 2: Shim script builder + sentinel detection

**Files:**
- Create: `installer/guards.py`
- Test: `tests/test_guards.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_guards.py`:

```python
import subprocess
from pathlib import Path

from installer.guards import BANNED, SHIM_SENTINEL, is_our_shim, shim_script


def test_shim_script_names_the_replacement_and_exits_nonzero():
    script = shim_script("pip")
    assert SHIM_SENTINEL in script
    assert "uv" in script  # the sanctioned replacement for pip
    assert "exit 127" in script


def test_shim_script_is_valid_posix_sh(tmp_path: Path):
    for name in BANNED:
        shim = tmp_path / name
        shim.write_text(shim_script(name))
        result = subprocess.run(["sh", "-n", str(shim)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_is_our_shim_detects_the_sentinel(tmp_path: Path):
    ours = tmp_path / "pip"
    ours.write_text(shim_script("pip"))
    assert is_our_shim(ours) is True


def test_is_our_shim_false_for_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    assert is_our_shim(real) is False


def test_is_our_shim_false_when_unreadable(tmp_path: Path):
    # A directory named like a tool: read_text raises OSError -> treated as not ours.
    (tmp_path / "pip").mkdir()
    assert is_our_shim(tmp_path / "pip") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'installer.guards'`.

- [ ] **Step 3: Create `installer/guards.py` with the builder + sentinel**

```python
"""Environment policy: ban the unmanaged package installers (npm/pip/pip3).

Two removable, idempotent layers steer callers to the managed toolchain:
1. PATH shims in the managed bin dir (~/.local/bin) — tiny POSIX-sh executables
   that print the sanctioned tool and exit non-zero. They catch ANY caller that
   resolves via PATH: you, an agent, a script, a non-interactive shell.
2. Interactive-shell aliases — a faster, clearer message for interactive use,
   written as a marker-delimited block (reusing shellrc's block machinery).

Neither layer is hermetic: `python -m pip install` bypasses the pip shim, and a
real npm/pip earlier on PATH wins. guard_path_warning flags the PATH-order case.
"""

from collections.abc import Callable
from pathlib import Path

from installer.shellrc import apply_block, strip_block

BANNED: dict[str, str] = {
    "npm": "pnpm (pnpm add -g <pkg>)",
    "pip": "uv (uv pip install / uv add)",
    "pip3": "uv (uv pip install / uv add)",
}
EXIT_CODE = 127  # non-zero so the caller sees a hard failure
SHIM_SENTINEL = "# tools-installer-ban-shim"
BAN_BEGIN = "# >>> tools-installer ban >>>"
BAN_END = "# <<< tools-installer ban <<<"


def shim_script(name: str) -> str:
    """A 4-line POSIX-sh shim that explains the ban and exits non-zero."""
    hint = BANNED[name]
    return (
        "#!/bin/sh\n"
        f"{SHIM_SENTINEL}\n"
        f"echo \"tools-installer: '{name}' is banned on this machine — use {hint}.\" >&2\n"
        f"exit {EXIT_CODE}\n"
    )


def is_our_shim(path: Path) -> bool:
    """True only for a readable file carrying our sentinel; never a real binary."""
    try:
        return SHIM_SENTINEL in path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_guards.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add installer/guards.py tests/test_guards.py
git commit -m "feat: guards shim builder and sentinel detection"
```

---

## Task 3: Install / remove shims + guard_status

**Files:**
- Modify: `installer/guards.py`
- Test: `tests/test_guards.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_guards.py` (extend the import: `guard_status, install_shims, remove_shims`):

```python
def test_install_shims_creates_each_banned_shim(tmp_path: Path):
    actions = install_shims(tmp_path)
    assert actions == {name: "created" for name in BANNED}
    for name in BANNED:
        shim = tmp_path / name
        assert is_our_shim(shim)
        assert shim.stat().st_mode & 0o111  # executable


def test_install_shims_is_idempotent_and_reports_refreshed(tmp_path: Path):
    install_shims(tmp_path)
    actions = install_shims(tmp_path)
    assert actions == {name: "refreshed" for name in BANNED}


def test_install_shims_never_overwrites_a_real_binary(tmp_path: Path):
    real = tmp_path / "pip"
    real.write_text("#!/bin/sh\necho real pip\n")
    actions = install_shims(tmp_path)
    assert actions["pip"] == "skipped (real binary here)"
    assert real.read_text() == "#!/bin/sh\necho real pip\n"  # untouched


def test_remove_shims_removes_only_ours(tmp_path: Path):
    install_shims(tmp_path)
    (tmp_path / "npm").write_text("#!/bin/sh\necho real npm\n")  # replace our npm shim with a real one
    actions = remove_shims(tmp_path)
    assert actions["pip"] == "removed"
    assert actions["npm"] == "absent"  # not ours -> left alone
    assert (tmp_path / "npm").exists()
    assert not (tmp_path / "pip").exists()


def test_guard_status_reports_installed_ours(tmp_path: Path):
    install_shims(tmp_path)
    (tmp_path / "pip").unlink()
    status = guard_status(tmp_path)
    assert status["npm"] is True
    assert status["pip"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guards.py -k "shims or guard_status" -v`
Expected: FAIL with `ImportError: cannot import name 'install_shims'`.

- [ ] **Step 3: Implement install/remove/status**

Append to `installer/guards.py`:

```python
def install_shims(shim_dir: Path) -> dict[str, str]:
    """Write npm/pip/pip3 shims into shim_dir (mode 0o755). Idempotent.

    Never overwrites a real binary already living there (sentinel check).
    Returns {name: 'created' | 'refreshed' | 'skipped (real binary here)'}.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}
    for name in BANNED:
        target = shim_dir / name
        if target.exists() and not is_our_shim(target):
            results[name] = "skipped (real binary here)"
            continue
        had = target.exists()
        target.write_text(shim_script(name))
        target.chmod(0o755)
        results[name] = "refreshed" if had else "created"
    return results


def remove_shims(shim_dir: Path) -> dict[str, str]:
    """Remove only the shims we created. Returns {name: 'removed' | 'absent'}."""
    results: dict[str, str] = {}
    for name in BANNED:
        target = shim_dir / name
        if target.exists() and is_our_shim(target):
            target.unlink()
            results[name] = "removed"
        else:
            results[name] = "absent"
    return results


def guard_status(shim_dir: Path) -> dict[str, bool]:
    """{name: our shim is installed} for each banned command."""
    return {name: is_our_shim(shim_dir / name) for name in BANNED}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_guards.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/guards.py tests/test_guards.py
git commit -m "feat: install/remove ban shims with guard_status"
```

---

## Task 4: Interactive-alias block + write/remove

**Files:**
- Modify: `installer/guards.py`
- Test: `tests/test_guards.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_guards.py` (extend import: `ban_alias_block, remove_ban_aliases, write_ban_aliases`):

```python
def test_ban_alias_block_aliases_each_banned_command():
    block = ban_alias_block()
    assert block.startswith(BAN_BEGIN)
    assert block.rstrip().endswith(BAN_END)
    for name in BANNED:
        assert f"alias {name}=" in block


def test_write_ban_aliases_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    write_ban_aliases(rc)
    write_ban_aliases(rc)
    text = rc.read_text()
    assert "# user content" in text
    assert text.count(BAN_BEGIN) == 1  # not duplicated


def test_remove_ban_aliases_strips_block_preserving_user_content(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# user content\n")
    write_ban_aliases(rc)
    remove_ban_aliases(rc)
    text = rc.read_text()
    assert "# user content" in text
    assert BAN_BEGIN not in text


def test_remove_ban_aliases_missing_file_is_noop(tmp_path: Path):
    remove_ban_aliases(tmp_path / "nope")  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guards.py -k alias -v`
Expected: FAIL with `ImportError: cannot import name 'ban_alias_block'`.

- [ ] **Step 3: Implement the alias layer**

Append to `installer/guards.py`:

```python
def ban_alias_block() -> str:
    """Marker-delimited alias block (no trailing newline, like shellrc blocks)."""
    lines = [BAN_BEGIN]
    for name, hint in BANNED.items():
        lines.append(
            f"""alias {name}='echo "tools-installer: {name} is banned — use {hint}." >&2; false'"""
        )
    lines.append(BAN_END)
    return "\n".join(lines)


def write_ban_aliases(rc_path: Path) -> None:
    """Idempotently write the alias block into rc_path, preserving the rest."""
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, ban_alias_block(), begin=BAN_BEGIN, end=BAN_END))


def remove_ban_aliases(rc_path: Path) -> None:
    """Strip the alias block from rc_path. A missing file or absent block is a no-op."""
    if not rc_path.exists():
        return
    original = rc_path.read_text()
    stripped = strip_block(original, BAN_BEGIN, BAN_END)
    if stripped != original:
        rc_path.write_text(stripped)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_guards.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/guards.py tests/test_guards.py
git commit -m "feat: ban-alias block write/remove for interactive shells"
```

---

## Task 5: PATH-order warning helper

**Files:**
- Modify: `installer/guards.py`
- Test: `tests/test_guards.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_guards.py` (extend import: `guard_path_warning`):

```python
def test_guard_path_warning_when_shim_dir_not_on_path(tmp_path: Path):
    warning = guard_path_warning(tmp_path, path_value="/usr/bin:/bin", which=lambda _n: None)
    assert warning is not None
    assert str(tmp_path) in warning


def test_guard_path_warning_when_real_tool_resolves_first(tmp_path: Path):
    # shim dir is on PATH but AFTER /usr/bin, where a real pip lives.
    path_value = f"/usr/bin:{tmp_path}"
    warning = guard_path_warning(
        tmp_path, path_value=path_value, which=lambda name: "/usr/bin/pip" if name == "pip" else None
    )
    assert warning is not None
    assert "/usr/bin/pip" in warning


def test_guard_path_warning_none_when_healthy(tmp_path: Path):
    # shim dir is first; the only resolvable tool is our own shim inside it.
    install_shims(tmp_path)
    path_value = f"{tmp_path}:/usr/bin"
    warning = guard_path_warning(
        tmp_path, path_value=path_value, which=lambda name: str(tmp_path / name)
    )
    assert warning is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guards.py -k path_warning -v`
Expected: FAIL with `ImportError: cannot import name 'guard_path_warning'`.

- [ ] **Step 3: Implement the warning helper**

Add the import at the top of `installer/guards.py` (with the existing imports):

```python
import os
```

Append the function:

```python
def guard_path_warning(
    shim_dir: Path,
    path_value: str,
    which: Callable[[str], str | None],
) -> str | None:
    """Warn when the shims can't take effect: shim_dir missing from PATH, or a
    real npm/pip/pip3 resolving before it. Returns None when the order is sound.

    `which` is injected (shutil.which in production) so the check is testable.
    """
    target = str(shim_dir)
    path_dirs = path_value.split(os.pathsep)
    if target not in path_dirs:
        return (
            f"{target} is not on PATH — add it (early) so the ban applies to "
            "non-interactive callers."
        )
    shim_index = path_dirs.index(target)
    for name in BANNED:
        real = which(name)
        if real and not is_our_shim(Path(real)):
            real_dir = str(Path(real).parent)
            if real_dir in path_dirs and path_dirs.index(real_dir) < shim_index:
                return f"A real '{name}' at {real} resolves before {target}; put {target} earlier on PATH."
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_guards.py -v`
Expected: PASS (full module).

- [ ] **Step 5: Commit**

```bash
git add installer/guards.py tests/test_guards.py
git commit -m "feat: guard_path_warning for PATH-order diagnosis"
```

---

## Task 6: Renderers for guard actions and doctor status

**Files:**
- Modify: `installer/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py` (add imports `render_guard, render_guard_status` from `installer.render`, and `import io`, `from rich.console import Console` if absent):

```python
def test_render_guard_prints_actions_and_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard({"pip": "created", "npm": "created"}, "watch PATH order", console, removing=False)
    out = buf.getvalue()
    assert "Installing the pip/npm ban" in out
    assert "created: pip" in out
    assert "watch PATH order" in out


def test_render_guard_removing_has_no_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard({"pip": "removed"}, None, console, removing=True)
    out = buf.getvalue()
    assert "Removing the pip/npm ban" in out
    assert "removed: pip" in out


def test_render_guard_status_silent_when_inactive():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": False, "npm": False, "pip3": False}, None, console)
    assert buf.getvalue() == ""


def test_render_guard_status_reports_active_shims_and_warning():
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    render_guard_status({"pip": True, "npm": False, "pip3": True}, "PATH order", console)
    out = buf.getvalue()
    assert "pip/npm ban active" in out
    assert "pip" in out
    assert "PATH order" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render.py -k guard -v`
Expected: FAIL with `ImportError: cannot import name 'render_guard'`.

- [ ] **Step 3: Implement the renderers**

Append to `installer/render.py`:

```python
def render_guard(
    actions: dict[str, str], warning: str | None, console: Console, *, removing: bool
) -> None:
    """Print the per-command shim actions, then any PATH-order warning."""
    verb = "Removing" if removing else "Installing"
    console.print(f"{verb} the pip/npm ban (shims + interactive aliases):")
    for name, what in actions.items():
        console.print(f"  {what}: {name}")
    if warning:
        console.print(warning)


def render_guard_status(status: dict[str, bool], warning: str | None, console: Console) -> None:
    """Read-only doctor line: silent unless the ban is active or PATH order is off."""
    active = [name for name, installed in status.items() if installed]
    if not active and not warning:
        return
    if active:
        console.print(f"pip/npm ban active: {', '.join(active)} shimmed.")
    if warning:
        console.print(f"  guard warning: {warning}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_render.py -k guard -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/render.py tests/test_render.py
git commit -m "feat: renderers for guard actions and doctor status"
```

---

## Task 7: `run_guard` orchestration in app.py

**Files:**
- Modify: `installer/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app.py` (ensure `import io`, `from pathlib import Path`, `from rich.console import Console`, and `from installer.app import run_guard`):

```python
def test_run_guard_install_writes_shims_and_aliases_and_returns_true(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    rc = tmp_path / ".myshellrc"
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    acted = run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[rc],
        path_value=f"{shim_dir}:/usr/bin",
        console=console,
        confirm=lambda _m: True,
        which=lambda _n: None,
    )
    assert acted is True
    assert (shim_dir / "pip").exists()
    assert "tools-installer ban" in rc.read_text()
    assert "Installing the pip/npm ban" in buf.getvalue()


def test_run_guard_declined_does_nothing(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    acted = run_guard(
        remove=False,
        shim_dir=shim_dir,
        rc_paths=[tmp_path / ".myshellrc"],
        path_value="",
        console=console,
        confirm=lambda _m: False,
        which=lambda _n: None,
    )
    assert acted is False
    assert not shim_dir.exists()


def test_run_guard_remove_strips_shims_and_aliases(tmp_path: Path):
    shim_dir = tmp_path / "bin"
    rc = tmp_path / ".myshellrc"
    console = Console(file=io.StringIO(), width=100)
    run_guard(
        remove=False, shim_dir=shim_dir, rc_paths=[rc], path_value=f"{shim_dir}",
        console=console, confirm=lambda _m: True, which=lambda _n: None,
    )
    run_guard(
        remove=True, shim_dir=shim_dir, rc_paths=[rc], path_value=f"{shim_dir}",
        console=console, confirm=lambda _m: True, which=lambda _n: None,
    )
    assert not (shim_dir / "pip").exists()
    assert "tools-installer ban" not in rc.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py -k run_guard -v`
Expected: FAIL with `ImportError: cannot import name 'run_guard'`.

- [ ] **Step 3: Implement `run_guard`**

In `installer/app.py`, extend the `installer.guards` usage by adding the import near the other `installer.*` imports:

```python
from installer.guards import (
    guard_path_warning,
    guard_status,
    install_shims,
    remove_ban_aliases,
    remove_shims,
    write_ban_aliases,
)
from installer.render import (
    render_audit,
    render_doctor,
    render_guard,
    render_guard_status,
    render_rc_duplicates,
    render_summary,
    render_uninstall,
    render_verification,
)
```

(Replace the existing `from installer.render import (...)` block with the one above — it just adds `render_guard` and `render_guard_status`.)

Add the function (place it after `clean_rc_duplicates`):

```python
def run_guard(
    *,
    remove: bool,
    shim_dir: Path,
    rc_paths: list[Path],
    path_value: str,
    console: Console,
    confirm: Callable[[str], bool],
    which: Callable[[str], str | None] = shutil.which,
) -> bool:
    """Install or remove the pip/npm ban (PATH shims + interactive aliases).

    Previews the targets, confirms, then acts on both layers. Returns whether it
    acted. The shim dir doubles as the managed bin dir (already on PATH).
    """
    targets = ", ".join(str(rc_path) for rc_path in rc_paths)
    verb = "Remove" if remove else "Install"
    if not confirm(f"{verb} the pip/npm ban (shims in {shim_dir} + aliases in {targets})?"):
        return False
    if remove:
        actions = remove_shims(shim_dir)
        for rc_path in rc_paths:
            remove_ban_aliases(rc_path)
        render_guard(actions, None, console, removing=True)
        return True
    actions = install_shims(shim_dir)
    for rc_path in rc_paths:
        write_ban_aliases(rc_path)
    render_guard(actions, guard_path_warning(shim_dir, path_value, which), console, removing=False)
    return True
```

Add `import shutil` at the top of `installer/app.py` (after the stdlib imports; there is currently none).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_app.py -k run_guard -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/app.py tests/test_app.py
git commit -m "feat: run_guard installs/removes the pip/npm ban"
```

---

## Task 8: Doctor reporting + uninstall cleanup

**Files:**
- Modify: `installer/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app.py`. These exercise the guard section of `run_doctor` and the guard cleanup in `run_uninstall`. (`run_doctor`/`run_uninstall` are already imported in this file.)

```python
def test_run_doctor_reports_active_ban(tmp_path: Path):
    from installer.guards import install_shims
    shim_dir = tmp_path / ".local" / "bin"
    install_shims(shim_dir)
    buf = io.StringIO()
    console = Console(file=buf, width=100)
    run_doctor(
        [],
        console,
        platform=Platform(os="fedora", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=shim_dir,
        path_value=str(shim_dir),
        exists=lambda _p: True,
        hint="hint",
        which=lambda name: str(shim_dir / name),
    )
    assert "pip/npm ban active" in buf.getvalue()


def test_run_uninstall_also_removes_guard_artifacts(tmp_path: Path):
    from installer.guards import install_shims, write_ban_aliases
    shim_dir = tmp_path / ".local" / "bin"
    myshellrc = tmp_path / ".myshellrc"
    rc = tmp_path / ".zshrc"
    install_shims(shim_dir)
    write_ban_aliases(myshellrc)
    write_ban_aliases(rc)
    console = Console(file=io.StringIO(), width=100)
    run_uninstall(
        [],
        console,
        default_bin_dir=shim_dir,
        myshellrc_path=myshellrc,
        rc_paths=[rc],
        confirm=lambda _m: True,
    )
    assert not (shim_dir / "pip").exists()
    assert "tools-installer ban" not in myshellrc.read_text()
    assert "tools-installer ban" not in rc.read_text()
```

> Note: the existing `run_uninstall` tests call it without `rc_paths`. Update each existing
> `run_uninstall(...)` call in `tests/test_app.py` to pass `rc_paths=[]` (no guard aliases in those
> fixtures, so behavior is unchanged).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py -k "active_ban or guard_artifacts" -v`
Expected: FAIL — `run_doctor` has no `which` kwarg; `run_uninstall` has no `rc_paths` kwarg.

- [ ] **Step 3: Extend `run_doctor` and `run_uninstall`**

In `installer/app.py`, change `run_doctor`'s signature and body to add the guard section:

```python
def run_doctor(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    hint: str,
    which: Callable[[str], str | None] = shutil.which,
) -> DoctorReport:
    """Audit the PATH (read-only) and render the report; `hint` is the next-step line.

    Also reports pip/npm-ban status (silent unless the ban is active or its shim
    dir's PATH order would defeat it). Fixing remains a separate explicit action.
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
    report = audit_path(bin_dirs, path_value, exists)
    render_doctor(report, console, hint)
    render_guard_status(
        guard_status(default_bin_dir),
        guard_path_warning(default_bin_dir, path_value, which),
        console,
    )
    return report
```

Change `run_uninstall` to accept `rc_paths` and clear guard artifacts:

```python
def run_uninstall(
    tools: list[Tool],
    console: Console,
    *,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
    confirm: Callable[[str], bool],
) -> list[Path]:
    """Preview userspace artifacts, confirm, then remove them, the PATH block, and
    any pip/npm-ban artifacts (shims + alias blocks).

    Returns the removed download/app paths ([] if nothing to remove or declined).
    """
    paths = plan_uninstall(tools, default_bin_dir)
    shimmed = [name for name, installed in guard_status(default_bin_dir).items() if installed]
    render_uninstall(paths, console)
    if shimmed:
        console.print(f"The pip/npm ban will also be removed ({', '.join(shimmed)}).")
    if not paths and not shimmed:
        return []
    if not confirm("Remove these artifacts?"):
        return []
    remove_paths(paths)
    remove_managed_block(myshellrc_path)
    remove_shims(default_bin_dir)
    remove_ban_aliases(myshellrc_path)
    for rc_path in rc_paths:
        remove_ban_aliases(rc_path)
    return paths
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS (new tests + existing, after the `rc_paths=[]` updates).

- [ ] **Step 5: Commit**

```bash
git add installer/app.py tests/test_app.py
git commit -m "feat: doctor reports the ban; uninstall removes its artifacts"
```

---

## Task 9: CLI flags `--guard` / `--unguard`

**Files:**
- Modify: `installer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_parse_guard_flag():
    options = parse_args(["--guard"])
    assert options.guard is True
    assert options.unguard is False


def test_parse_unguard_flag():
    options = parse_args(["--unguard"])
    assert options.unguard is True


def test_guard_defaults_false():
    options = parse_args([])
    assert options.guard is False
    assert options.unguard is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -k guard -v`
Expected: FAIL with `AttributeError: 'Options' object has no attribute 'guard'`.

- [ ] **Step 3: Add the options**

In `installer/cli.py`, add two fields to `Options` (after `uninstall`):

```python
    guard: bool = False
    unguard: bool = False
```

Add two arguments in `parse_args` (after the `--uninstall` argument):

```python
    parser.add_argument(
        "--guard",
        action="store_true",
        help="install the pip/npm ban (shims + aliases steering to uv/pnpm), then exit",
    )
    parser.add_argument(
        "--unguard", action="store_true", help="remove the pip/npm ban, then exit"
    )
```

Add them to the returned `Options(...)`:

```python
        guard=ns.guard,
        unguard=ns.unguard,
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add installer/cli.py tests/test_cli.py
git commit -m "feat: --guard/--unguard CLI flags"
```

---

## Task 10: Wire setup.py + Makefile + wizard prompt

**Files:**
- Modify: `setup.py`
- Modify: `Makefile`

> `setup.py` is the untested IO boundary (excluded from coverage/pyright by design — see the
> `validate` target comment). No tests in this task; correctness is covered by `make validate`
> (ruff/format) plus a manual `--help` smoke check. Do NOT run a real `--guard` against your own
> home during development.

- [ ] **Step 1: Import `run_guard` and add helpers**

In `setup.py`, add `run_guard` to the `installer.app` import:

```python
from installer.app import (
    clean_rc_duplicates,
    configure_path,
    run_doctor,
    run_guard,
    run_uninstall,
    run_wizard,
)
```

Add a confirm-default-no helper and a ban-target helper (after `_ask_confirm`):

```python
def _ask_optin(message: str) -> bool:
    answer = questionary.confirm(message, default=False, style=_STYLE).ask()
    if answer is None:  # Ctrl+C / Ctrl+D
        raise KeyboardInterrupt
    return bool(answer)


def _ban_rc_paths(link_mode: str) -> list[Path]:
    # Aliases follow the PATH model: centralized/single keep one ~/.myshellrc;
    # split writes into each rc file directly.
    if link_mode == "split":
        return _rc_paths_for_mode(link_mode)
    return [_MYSHELLRC]
```

Add the guard runner (after `_run_uninstall`):

```python
def _run_guard(console: Console, *, remove: bool, link_mode_option: str | None, assume_yes: bool) -> int:
    link_mode = _resolve_link_mode(link_mode_option)
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_guard(
        remove=remove,
        shim_dir=_DEFAULT_BIN_DIR,
        rc_paths=_ban_rc_paths(link_mode),
        path_value=os.environ.get("PATH", ""),
        console=console,
        confirm=confirm,
    )
    return 0
```

- [ ] **Step 2: Dispatch the flags and update the uninstall call**

In `main`, add the dispatch (after the `options.uninstall` branch):

```python
    if options.guard:
        return _run_guard(console, remove=False, link_mode_option=options.link_mode, assume_yes=options.yes)
    if options.unguard:
        return _run_guard(console, remove=True, link_mode_option=options.link_mode, assume_yes=options.yes)
```

Update `_run_uninstall` to pass `rc_paths` (it now removes alias blocks too):

```python
def _run_uninstall(console: Console, *, assume_yes: bool) -> int:
    confirm = (lambda _message: True) if assume_yes else _ask_confirm
    run_uninstall(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        confirm=confirm,
    )
    return 0
```

- [ ] **Step 3: Add the optional wizard prompt**

In `main`, after `_verify_and_clean(console, tools, platform, assume_yes=options.yes)` and before the `summary.failed` check, add the opt-in prompt (interactive only, never under `--yes`):

```python
    if sys.stdin.isatty() and not options.yes and _ask_optin(
        "Enable the pip/npm ban? Blocks bare pip/npm so installs go through uv/pnpm."
    ):
        _run_guard(console, remove=False, link_mode_option=options.link_mode, assume_yes=False)
```

- [ ] **Step 4: Add Makefile targets**

In `Makefile`, add `guard unguard` to the `.PHONY` line, and add the targets after `uninstall`:

```makefile
guard:  ## Ban bare pip/npm (shims + aliases steering to uv/pnpm; opt-in, removable)
	uv run setup.py --guard

unguard:  ## Remove the pip/npm ban
	uv run setup.py --unguard
```

- [ ] **Step 5: Smoke-check and commit**

Run: `uv run setup.py --help`
Expected: the help text lists `--guard` and `--unguard`.

Run: `make validate`
Expected: PASS (ruff/format/pyright/bandit/vulture/shellcheck all green).

```bash
git add setup.py Makefile
git commit -m "feat: make guard/unguard, flag dispatch, opt-in wizard prompt"
```

---

## Task 11: Document the ban

**Files:**
- Modify: `README.md`
- Modify: `docs/TROUBLESHOOTING.md`

- [ ] **Step 1: README — add a feature bullet and a section**

In `README.md`, add a bullet near the other feature bullets:

```markdown
- **Optional pip/npm ban** — `make guard` drops shims + shell aliases that block
  bare `pip`/`pip3` (use `uv`) and `npm` (use `pnpm`), so the system Python and
  global node_modules stay clean. Opt-in and fully removable with `make unguard`.
```

And a short section (place it after the PATH/doctor section):

```markdown
## Banning pip / npm (optional)

The installer can steer you off the unmanaged installers:

```sh
make guard     # block bare pip/pip3 (-> uv) and npm (-> pnpm)
make unguard   # remove the ban
```

It works in two layers: PATH shims in `~/.local/bin` (catch every caller,
including scripts and agents) and interactive-shell aliases (a clearer message
at the prompt). `make doctor` reports whether the ban is active.

It is **not** a sandbox: `python -m pip install` bypasses the `pip` shim, and a
real `pip`/`npm` earlier on your `PATH` wins — `make doctor` warns about that
ordering. `make uninstall` removes the ban along with everything else.
```

- [ ] **Step 2: TROUBLESHOOTING — add an entry**

In `docs/TROUBLESHOOTING.md`, add an entry explaining that if `pip`/`npm` print
"banned" and you need the real tool, run `make unguard` (or, inside a project,
use `uv`/`pnpm`), and that a real tool resolving before `~/.local/bin` is
flagged by `make doctor`.

- [ ] **Step 3: Validate and commit**

Run: `make validate && make test`
Expected: PASS (366 + new tests, 100% coverage; shellcheck clean).

```bash
git add README.md docs/TROUBLESHOOTING.md
git commit -m "docs: document the optional pip/npm ban"
```

---

## Self-review

**Spec coverage:**
- Full-command ban → shim_script exits 127 unconditionally (Task 2). ✓
- Two layers → shims (Task 3) + aliases (Task 4). ✓
- Opt-in, never silent under `--yes` → wizard prompt gated on `isatty() and not yes`; flags are explicit (Task 10). ✓
- Both activation paths → `make guard/unguard` + flags + wizard prompt (Tasks 9–10). ✓
- Doctor reports guard health → `render_guard_status` in `run_doctor` (Tasks 6, 8). ✓
- Uninstall integration → `run_uninstall` clears shims + aliases (Task 8). ✓
- Banned set + replacements (pip/pip3→uv, npm→pnpm) → `BANNED` (Task 2). ✓
- Never overwrite a real binary → sentinel check (Tasks 2–3). ✓
- `sh -n` POSIX validation → Task 2. ✓
- PATH-order warning, injected `which` → Task 5, surfaced in Tasks 7–8. ✓
- Known limitation documented → Task 11. ✓

**Type consistency:** `BANNED: dict[str,str]`; shim/alias/status/warning functions all take `shim_dir: Path`; `run_guard`/`run_doctor`/`run_uninstall` signatures match their call sites in `setup.py` (Task 10) and tests. `guard_status` returns `dict[str,bool]`; `render_guard_status` consumes `dict[str,bool]`. `install_shims`/`remove_shims` return `dict[str,str]`; `render_guard` consumes `dict[str,str]`. Consistent.

**Placeholder scan:** none — every code step is complete.

**Coverage note:** every line in `installer/guards.py` is exercised by `tests/test_guards.py` (including both `is_our_shim` except branches via the directory case and the missing-file no-op). `run_guard`/`run_doctor`/`run_uninstall` branches are covered in `tests/test_app.py` (install, decline, remove; active-ban doctor; guard-artifact uninstall).
