# SP2: Shell-rc Link-Mode Preference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Let the user choose how the managed PATH reaches their shells — **centralized** (today: one `~/.myshellrc` sourced from both rc files), **single-shell** (sourced from one rc, picked/`$SHELL`-detected), or **split-inline** (PATH block written directly into each rc, no `~/.myshellrc`).

**Architecture:** The pure core (`configure_path`) branches only on inline-vs-indirection: `split` writes the managed block directly into each rc; `centralized`/`single` keep the `~/.myshellrc` + `source` model and differ only by how many rc files the composition root passes. A new idempotent `shellrc.write_managed_path` reuses the existing `managed_block`/`apply_block`. The `--link-mode` flag carries the choice non-interactively; `setup.py` (composition root) prompts via `questionary.select` and resolves the single-shell rc from `$SHELL`.

**Tech Stack:** Python (uv), pytest. Gates: ruff, pyright strict, bandit, vulture, shellcheck; 100% coverage on `installer/`.

**Non-negotiables:** English only. No gate bypass. Coherent commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. `setup.py` is the composition root — excluded from pyright/coverage, lint/format-gated only.

---

## Background

`installer/shellrc.py` has `managed_block(bin_dirs) -> str` (the marker-delimited PATH block), `apply_block(content, block, begin, end) -> str` (idempotent insert/replace), `write_myshellrc(bin_dirs, path)` (block → `~/.myshellrc`), and `ensure_source(rc_path, myshellrc_path)` (adds `source ~/.myshellrc` to an rc).

`installer/app.py:configure_path(tools, console, *, platform, default_bin_dir, myshellrc_path, rc_paths)` currently:
```python
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir)
    write_myshellrc(bin_dirs, myshellrc_path)
    for rc_path in rc_paths:
        ensure_source(rc_path, myshellrc_path)
    console.print(f"PATH configured in {myshellrc_path} (restart your shell or source it).")
```
`run_doctor(..., fix: bool)` calls `configure_path(...)` when `fix` is true. `installer/cli.py:Options` is a frozen dataclass; `parse_args` builds it.

---

## Task 1: `shellrc.write_managed_path` (split-inline writer)

**Files:**
- Modify: `installer/shellrc.py`
- Test: `tests/test_shellrc.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_write_managed_path_inlines_block_into_rc(tmp_path):
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".zshrc"
    rc.write_text("# user line\n")
    write_managed_path(rc, [tmp_path / "bin"])
    text = rc.read_text()
    assert "# >>> tools-installer path >>>" in text
    assert f'export PATH="{tmp_path / "bin"}:$PATH"' in text
    assert "# user line" in text  # user content preserved


def test_write_managed_path_is_idempotent(tmp_path):
    from installer.shellrc import write_managed_path

    rc = tmp_path / ".bashrc"
    write_managed_path(rc, [tmp_path / "bin"])
    write_managed_path(rc, [tmp_path / "bin"])
    assert rc.read_text().count("# >>> tools-installer path >>>") == 1
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_shellrc.py -q`
Expected: FAIL — `cannot import name 'write_managed_path'`.

- [ ] **Step 3: Implement**

Add to `installer/shellrc.py`:

```python
def write_managed_path(rc_path: Path, bin_dirs: list[Path]) -> None:
    """Write the managed PATH block directly into an rc file (split-inline mode).

    Idempotent: only the marked block is rewritten, surrounding user content is
    preserved. Used when the user opts out of the ~/.myshellrc indirection.
    """
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, managed_block(bin_dirs)))
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_shellrc.py -q`
Expected: PASS.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/shellrc.py tests/test_shellrc.py
git commit -m "feat: add shellrc.write_managed_path for split-inline link mode

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `--link-mode` CLI flag

**Files:**
- Modify: `installer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_link_mode_defaults_to_none():
    assert parse_args([]).link_mode is None


def test_link_mode_parses_each_choice():
    assert parse_args(["--link-mode", "centralized"]).link_mode == "centralized"
    assert parse_args(["--link-mode", "single"]).link_mode == "single"
    assert parse_args(["--link-mode", "split"]).link_mode == "split"


def test_link_mode_rejects_unknown_choice():
    import pytest

    with pytest.raises(SystemExit):
        parse_args(["--link-mode", "bogus"])
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL — `Options` has no `link_mode` / unknown `--link-mode`.

- [ ] **Step 3: Implement**

In `installer/cli.py`, add the field to `Options` (after `uninstall`):

```python
    uninstall: bool = False
    link_mode: str | None = None
```

Register the argument (after `--uninstall`):

```python
    parser.add_argument(
        "--link-mode",
        choices=["centralized", "single", "split"],
        default=None,
        help="how to wire PATH into your shells (default: ask, or centralized)",
    )
```

Thread it into the returned `Options`:

```python
    return Options(
        all=ns.all,
        categories=tuple(categories),
        yes=ns.yes,
        doctor=ns.doctor,
        uninstall=ns.uninstall,
        link_mode=ns.link_mode,
    )
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/cli.py tests/test_cli.py
git commit -m "feat: add --link-mode flag (centralized|single|split)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `configure_path` link-mode branch + `run_doctor` passthrough

**Files:**
- Modify: `installer/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app.py` (the file already imports `Path`, `Console`/`_console`, and has tools/factories — match its idiom, e.g. use the existing `_console()` helper and a minimal tool list; `collect_bin_dirs` defaults always include the default bin dir, so an empty tools list is fine):

```python
def test_configure_path_centralized_writes_myshellrc_and_sources_both(tmp_path):
    from installer.app import configure_path
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc, brc = tmp_path / ".zshrc", tmp_path / ".bashrc"
    configure_path(
        [], console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin", myshellrc_path=myshellrc, rc_paths=[zrc, brc],
    )  # default link_mode="centralized"
    assert "# >>> tools-installer path >>>" in myshellrc.read_text()
    assert "source" in zrc.read_text() or ". " in zrc.read_text()
    assert str(myshellrc) in zrc.read_text()
    assert str(myshellrc) in brc.read_text()


def test_configure_path_single_sources_only_the_given_rc(tmp_path):
    from installer.app import configure_path
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc = tmp_path / ".zshrc"
    configure_path(
        [], console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin", myshellrc_path=myshellrc, rc_paths=[zrc],
        link_mode="single",
    )
    assert myshellrc.exists()
    assert str(myshellrc) in zrc.read_text()


def test_configure_path_split_inlines_block_and_skips_myshellrc(tmp_path):
    from installer.app import configure_path
    from installer.platform import Platform

    console, _buf = _console()
    myshellrc = tmp_path / ".myshellrc"
    zrc, brc = tmp_path / ".zshrc", tmp_path / ".bashrc"
    configure_path(
        [], console,
        platform=Platform(os="debian", arch="amd64", immutable=False, has_brew=False),
        default_bin_dir=tmp_path / "bin", myshellrc_path=myshellrc, rc_paths=[zrc, brc],
        link_mode="split",
    )
    assert not myshellrc.exists()  # no indirection file in split mode
    for rc in (zrc, brc):
        text = rc.read_text()
        assert "# >>> tools-installer path >>>" in text  # block written inline
        assert str(myshellrc) not in text  # and no source line
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_app.py -q`
Expected: FAIL — `configure_path` has no `link_mode` keyword.

- [ ] **Step 3: Implement**

In `installer/app.py`, extend the shellrc import to include `write_managed_path`:

```python
from installer.shellrc import (
    collect_bin_dirs,
    ensure_source,
    remove_managed_block,
    write_managed_path,
    write_myshellrc,
)
```

Replace `configure_path` with:

```python
def configure_path(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
    link_mode: str = "centralized",
) -> None:
    """Wire the managed PATH into the shells per `link_mode`.

    centralized/single: write ~/.myshellrc and `source` it from each rc path (the
    caller passes one rc for single, both for centralized). split: write the managed
    PATH block directly into each rc path, with no ~/.myshellrc indirection.
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir)
    if link_mode == "split":
        for rc_path in rc_paths:
            write_managed_path(rc_path, bin_dirs)
        targets = ", ".join(str(rc_path) for rc_path in rc_paths)
        console.print(f"PATH written into {targets} (restart your shell).")
        return
    write_myshellrc(bin_dirs, myshellrc_path)
    for rc_path in rc_paths:
        ensure_source(rc_path, myshellrc_path)
    console.print(f"PATH configured in {myshellrc_path} (restart your shell or source it).")
```

In `run_doctor`, add the `link_mode` param and pass it through:

```python
def run_doctor(
    tools: list[Tool],
    console: Console,
    *,
    platform: Platform,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    myshellrc_path: Path,
    rc_paths: list[Path],
    fix: bool,
    link_mode: str = "centralized",
) -> DoctorReport:
```

and in its body change the `configure_path(...)` call to pass `link_mode=link_mode`.

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_app.py -q`
Expected: PASS — new tests pass; existing `configure_path`/`run_doctor` tests still pass (default `link_mode="centralized"` preserves old behavior).

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/app.py tests/test_app.py
git commit -m "feat: configure_path honors link mode (centralized/single/split)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Wire the prompt and `$SHELL` detection into `setup.py`

Composition-root wiring (no unit tests — `setup.py` is out of pyright/coverage; it IS ruff-gated).

**Files:**
- Modify: `setup.py`

- [ ] **Step 1: Add a link-mode prompt and rc resolution**

In `setup.py`, add a `questionary.select` wrapper and helpers, then resolve the mode + rc paths before calling `configure_path`.

```python
def _ask_select(message: str, choices: list[tuple[str, str]]) -> str:
    answer = questionary.select(
        message, choices=[questionary.Choice(title=title, value=value) for title, value in choices]
    ).ask()
    if answer is None:  # Ctrl+C / Ctrl+D
        raise KeyboardInterrupt
    return str(answer)


def _resolve_link_mode(options_link_mode: str | None) -> str:
    if options_link_mode is not None:
        return options_link_mode
    if not sys.stdin.isatty():
        return "centralized"
    return _ask_select(
        "How should PATH be wired into your shells?",
        [
            ("Centralized: one ~/.myshellrc, sourced from .zshrc and .bashrc", "centralized"),
            ("Single shell: source ~/.myshellrc from your current shell only", "single"),
            ("Split: write PATH directly into each rc file (no ~/.myshellrc)", "split"),
        ],
    )


def _rc_paths_for_mode(link_mode: str) -> list[Path]:
    if link_mode != "single":
        return _RC_PATHS
    shell = os.environ.get("SHELL", "")
    if shell.endswith("zsh"):
        return [Path.home() / ".zshrc"]
    if shell.endswith("bash"):
        return [Path.home() / ".bashrc"]
    return _RC_PATHS  # undetectable shell -> fall back to wiring both
```

- [ ] **Step 2: Use them in `main` and `_run_doctor`**

In `main`, after `run_wizard` returns a non-None summary, replace the `configure_path(...)` call with:

```python
    link_mode = _resolve_link_mode(options.link_mode)
    configure_path(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
        link_mode=link_mode,
    )
```

In `_run_doctor`, resolve and pass the mode too:

```python
def _run_doctor(console: Console, *, link_mode_option: str | None) -> int:
    link_mode = _resolve_link_mode(link_mode_option)
    run_doctor(
        load_tools(_REGISTRY),
        console,
        platform=detect(),
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
        fix=True,
        link_mode=link_mode,
    )
    return 0
```

and update its call site: `return _run_doctor(console, link_mode_option=options.link_mode)`.

- [ ] **Step 3: Validate and smoke-check**

Run: `make validate && make test`
Expected: green at 100% (only `setup.py` changed among non-test files; it is out of coverage).

Smoke (non-interactive uses the flag, no prompt):

Run: `printf '' | uv run setup.py --doctor --link-mode split`
Expected: the doctor runs and reports; exits 0. (On a clean machine it writes the PATH block inline into `~/.zshrc`/`~/.bashrc`. If you prefer not to touch your real rc files, just confirm `make validate` is green and skip running it against your home.)

- [ ] **Step 4: Commit**

```bash
git add setup.py
git commit -m "feat: prompt for link mode and resolve single-shell rc from \$SHELL

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final check

- `make validate && make test` green at 100% on the final tree.
- `configure_path` and `run_doctor` honor `link_mode`; `--link-mode` parses; `setup.py` prompts when unset and resolves the single-shell rc from `$SHELL`.
- Update `roadmap-status.md` memory: SP2 done; SP3 (dup-cleaning + post-install doctor verify) still pending.
