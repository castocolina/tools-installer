# Doctor/Fix Split + Existing-Dirs Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `make doctor` becomes a calm read-only PATH report that only covers directories that exist on disk; fixing moves to an explicit `make fix` / `--fix`.

**Architecture:** One existence filter inside `shellrc.collect_bin_dirs` (default bin dir always kept, declared `bin_dir`s only when present on disk) inherited by all three consumers. `app.run_doctor` loses its write path and gains a caller-supplied `hint` line that `render_doctor` prints instead of the troubleshooting URL. A new `--fix` flag drives the existing `configure_path` via a new `setup._run_fix`.

**Tech Stack:** Python 3.13 / uv, pytest (100% coverage gate on `installer/`), rich. `setup.py` stays the untested IO boundary.

**Spec:** `docs/superpowers/specs/2026-06-11-doctor-fix-split-design.md` (approved).

**Worktree note:** work on `main` per this repo's convention (no remote; coherent single-purpose commits). `make validate && make test` must pass on the exact tree of every commit.

---

## File map

| File | Change |
| --- | --- |
| `installer/shellrc.py` | `collect_bin_dirs` gains `exists: Callable[[Path], bool] = Path.is_dir`; declared dirs filtered, default always kept |
| `installer/render.py` | `render_doctor(report, console, hint)` — hint replaces the troubleshooting URL |
| `installer/app.py` | `run_doctor` slimmed to read-only (+`hint`); `configure_path` gains forwarded `exists` kwarg |
| `installer/cli.py` | `Options.fix`, `--fix` flag, `--doctor` help text |
| `setup.py` | `_run_doctor` read-only; new `_run_fix`; flag precedence doctor → fix → uninstall; `_verify_and_clean` hint |
| `Makefile` | new `fix` target; `doctor` help text |
| `README.md`, `CLAUDE.md` | document the split |
| `tests/test_shellrc.py`, `tests/test_app.py`, `tests/test_render.py`, `tests/test_cli.py` | per-task below |

---

### Task 1: Existence filter in `collect_bin_dirs`

**Files:**
- Modify: `installer/shellrc.py:19-36`
- Test: `tests/test_shellrc.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_shellrc.py` (the `_tool` / `_PLATFORM` helpers already exist at the top of the file):

```python
def test_collect_bin_dirs_filters_declared_dirs_missing_on_disk():
    default = Path("/home/u/.local/bin")
    on_disk = {Path("/home/u/tools/bin")}
    tools = [_tool("fd", "/home/u/tools/bin"), _tool("bun", "/home/u/.bun/bin")]
    result = collect_bin_dirs(tools, _PLATFORM, default, exists=lambda p: p in on_disk)
    # fd's dir exists -> kept; bun's does not -> filtered out.
    assert result == [Path("/home/u/.local/bin"), Path("/home/u/tools/bin")]


def test_collect_bin_dirs_always_keeps_default_even_when_missing():
    default = Path("/home/u/.local/bin")
    tools = [_tool("fd", "/home/u/tools/bin")]
    result = collect_bin_dirs(tools, _PLATFORM, default, exists=lambda _p: False)
    assert result == [default]
```

The two existing collect tests use declared dirs that do not exist on the real
disk, so they must opt out of the new default filter. Update both:

In `test_collect_bin_dirs_defaults_first_then_declared_deduped`, change the call to:

```python
    assert collect_bin_dirs(tools, _PLATFORM, default, exists=lambda _p: True) == [
        Path("/home/u/.local/bin"),
        Path("/home/u/tools/bin"),
    ]
```

In `test_collect_bin_dirs_expands_user`, change the call to:

```python
    result = collect_bin_dirs(tools, _PLATFORM, default, exists=lambda _p: True)
```

In `test_collect_bin_dirs_only_includes_platform_applicable_methods` (line 200), change the call to:

```python
    dirs = collect_bin_dirs([tool], macos, Path("~/.local/bin"), exists=lambda _p: True)
```

(Without this, that test would depend on whether `/opt/homebrew/bin` exists on
the machine running it — green on an Apple Silicon dev box, red on CI ubuntu.)

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_shellrc.py -v`
Expected: the two new tests FAIL with `TypeError: collect_bin_dirs() got an unexpected keyword argument 'exists'`; the two updated ones fail the same way.

- [ ] **Step 3: Implement the filter**

Replace `collect_bin_dirs` in `installer/shellrc.py` (and add the `Callable` import below the existing `from pathlib import Path`):

```python
from collections.abc import Callable
from pathlib import Path
```

```python
def collect_bin_dirs(
    tools: list[Tool],
    platform: Platform,
    default: Path,
    exists: Callable[[Path], bool] = Path.is_dir,
) -> list[Path]:
    """The default bin dir plus each platform-applicable method's existing bin_dir.

    The default is always managed. A declared bin_dir is managed only when the
    directory exists on disk: a missing dir means the tool was never installed,
    and wiring it into PATH (or reporting it broken) is noise. Disk presence —
    not PATH probing — avoids the bootstrap chicken-and-egg: right after
    installing brew, `brew` is not on PATH yet but /opt/homebrew/bin exists.
    """
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path, *, require_exists: bool) -> None:
        resolved = path.expanduser()
        if resolved in seen or (require_exists and not exists(resolved)):
            return
        seen.add(resolved)
        dirs.append(resolved)

    add(default, require_exists=False)
    for tool in tools:
        for method in resolve_methods(tool, platform):
            raw = method.params.get("bin_dir")
            if isinstance(raw, str) and raw:
                add(Path(raw), require_exists=True)
    return dirs
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all pass, coverage 100%. (The three consumers in `app.py`/`setup.py` pick up the real `Path.is_dir` default — that behavior change is the point. Their tests use either brew-only tools with no `bin_dir` or tmp-path defaults, which the filter never touches, so they stay green.)

- [ ] **Step 5: Commit**

```bash
git add installer/shellrc.py tests/test_shellrc.py
git commit -m "feat: manage only bin dirs that exist on disk (default always kept)"
```

---

### Task 2: Read-only doctor with a next-step hint

**Files:**
- Modify: `installer/render.py:75-87` (`render_doctor`)
- Modify: `installer/app.py:105-161` (`configure_path`, `run_doctor`)
- Modify: `setup.py:134-148` (`_run_doctor`), `setup.py:163-179` (`_verify_and_clean`), `setup.py:182-186` (`main` doctor branch)
- Test: `tests/test_render.py`, `tests/test_app.py`

- [ ] **Step 1: Rewrite the render tests**

In `tests/test_render.py`, replace `test_render_doctor_reports_problems_and_link` and `test_render_doctor_healthy_has_no_link` with:

```python
def test_render_doctor_prints_findings_then_hint() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    report = DoctorReport(
        missing=(Path("/a/bin"),),
        broken=(Path("/c/bin"),),
        duplicated=(Path("/b/bin"),),
    )
    console, buf = _console()
    render_doctor(report, console, "Run 'make fix' to wire PATH into your shell.")
    out = buf.getvalue()
    assert "/a/bin" in out and "/c/bin" in out and "/b/bin" in out
    assert "missing from PATH" in out
    assert "make fix" in out
    assert "github.com" not in out  # troubleshooting URL no longer printed here


def test_render_doctor_healthy_prints_no_hint() -> None:
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    console, buf = _console()
    render_doctor(DoctorReport(missing=(), broken=(), duplicated=()), console, "HINT")
    out = buf.getvalue()
    assert "healthy" in out.lower()
    assert "HINT" not in out
```

- [ ] **Step 2: Rewrite the app doctor tests**

In `tests/test_app.py`:

DELETE `test_run_doctor_reports_and_fixes`, `test_run_doctor_without_fix_does_not_write`, and `test_run_doctor_forwards_link_mode_split_when_fixing`.

ADD in their place:

```python
def test_run_doctor_reports_problems_with_hint_and_never_writes(tmp_path: Path):
    from installer.app import run_doctor

    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value="/usr/bin",
        exists=lambda _p: False,  # default dir absent -> missing + broken
        hint="Run 'make fix' to wire PATH into your shell.",
    )

    assert bin_dir in report.missing
    assert bin_dir in report.broken
    assert "make fix" in buf.getvalue()
    assert "github.com" not in buf.getvalue()
    assert list(tmp_path.iterdir()) == []  # diagnosis only: nothing written


def test_run_doctor_healthy_reports_no_hint(tmp_path: Path):
    from installer.app import run_doctor

    bin_dir = tmp_path / "bin"
    console, buf = _console()

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        platform=_platform(),
        default_bin_dir=bin_dir,
        path_value=str(bin_dir),
        exists=lambda _p: True,
        hint="HINT",
    )

    assert report.missing == () and report.broken == () and report.duplicated == ()
    assert "healthy" in buf.getvalue().lower()
    assert "HINT" not in buf.getvalue()


def test_configure_path_honors_exists_filter(tmp_path: Path):
    from installer.app import configure_path

    declared = tmp_path / "tools" / "bin"  # never created on disk
    tool = Tool(
        id="fd",
        name="fd",
        category="search",
        cmd="fd",
        methods=(
            Method(kind="github_release", params={"member": "fd", "bin_dir": str(declared)}),
        ),
    )
    myshellrc = tmp_path / ".myshellrc"
    console, _buf = _console()

    configure_path(
        [tool],
        console,
        platform=_platform(),
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[],
        exists=lambda _p: False,
    )

    text = myshellrc.read_text()
    assert str(declared) not in text  # not on disk -> not managed
    assert str(tmp_path / ".local" / "bin") in text  # default always managed
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_render.py tests/test_app.py -v`
Expected: new render tests FAIL (`render_doctor() takes 2 positional arguments but 3 were given`); new app tests FAIL (`run_doctor() got an unexpected keyword argument 'hint'`, `configure_path() got an unexpected keyword argument 'exists'`).

- [ ] **Step 4: Implement render + app**

`installer/render.py` — replace `render_doctor`:

```python
def render_doctor(report: DoctorReport, console: Console, hint: str) -> None:
    """Print the PATH audit; on any problem, close with the caller's next-step hint."""
    if not has_problems(report):
        console.print("PATH looks healthy: all bin dirs present, on PATH, and unique.")
        return
    for label, dirs in (
        ("missing from PATH", report.missing),
        ("does not exist", report.broken),
        ("duplicated on PATH", report.duplicated),
    ):
        for directory in dirs:
            console.print(f"  {label}: {directory}")
    console.print(hint)
```

(`render_troubleshooting` itself stays: `setup.main` still uses it for install failures.)

`installer/app.py` — `configure_path` gains a forwarded `exists` kwarg (signature and first line only; the rest is unchanged):

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
    exists: Callable[[Path], bool] = Path.is_dir,
) -> None:
    """Wire the managed PATH into the shells per `link_mode`.

    centralized/single: write ~/.myshellrc and `source` it from each rc path (the
    caller passes one rc for single, both for centralized). split: write the managed
    PATH block directly into each rc path, with no ~/.myshellrc indirection.
    Only bin dirs that pass `exists` are managed (the default always is).
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
```

`installer/app.py` — replace `run_doctor` entirely:

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
) -> DoctorReport:
    """Audit the PATH (read-only) and render the report; `hint` is the next-step line.

    Fixing is a separate explicit action (configure_path, reached via --fix):
    a diagnosis that silently rewrites shell config is what this split removes.
    """
    bin_dirs = collect_bin_dirs(tools, platform, default_bin_dir, exists)
    report = audit_path(bin_dirs, path_value, exists)
    render_doctor(report, console, hint)
    return report
```

`setup.py` — replace `_run_doctor` and the `main` doctor branch, and update `_verify_and_clean`'s `run_doctor` call:

```python
def _run_doctor(console: Console) -> int:
    run_doctor(
        load_tools(_REGISTRY),
        console,
        platform=detect(),
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        hint="Run 'make fix' to wire PATH into your shell.",
    )
    return 0
```

In `main`: `if options.doctor: return _run_doctor(console)` (the `link_mode_option` argument is gone — doctor no longer prompts).

In `_verify_and_clean`, the `run_doctor` call becomes:

```python
    run_doctor(
        tools,
        console,
        platform=platform,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        hint="Restart your shell (or: source ~/.myshellrc) to apply.",
    )
```

- [ ] **Step 5: Run the full gate**

Run: `make validate && make test`
Expected: all pass, coverage 100%. Smoke: `uv run setup.py --help` exits 0.

- [ ] **Step 6: Commit**

```bash
git add installer/render.py installer/app.py setup.py tests/test_render.py tests/test_app.py
git commit -m "feat: doctor is read-only and points at 'make fix'"
```

---

### Task 3: `--fix` flag, `_run_fix`, `make fix`

**Files:**
- Modify: `installer/cli.py`
- Modify: `setup.py` (new `_run_fix`, flag precedence in `main`)
- Modify: `Makefile:2,19-20`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def test_fix_defaults_false():
    assert parse_args([]).fix is False


def test_fix_flag():
    assert parse_args(["--fix"]).fix is True


def test_doctor_and_fix_both_parse():
    # Precedence (doctor -> fix -> uninstall) is applied in setup.main.
    opts = parse_args(["--doctor", "--fix"])
    assert opts.doctor is True and opts.fix is True
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `AttributeError: 'Options' object has no attribute 'fix'`.

- [ ] **Step 3: Implement the flag**

`installer/cli.py` — add the field after `doctor` in `Options`:

```python
    doctor: bool = False
    fix: bool = False
    uninstall: bool = False
```

Change the `--doctor` help text and add `--fix` right after it:

```python
    parser.add_argument(
        "--doctor", action="store_true", help="audit the PATH (read-only report), then exit"
    )
    parser.add_argument(
        "--fix", action="store_true", help="wire PATH into your shell rc files, then exit"
    )
```

And thread it through the return:

```python
    return Options(
        all=ns.all,
        categories=tuple(categories),
        yes=ns.yes,
        doctor=ns.doctor,
        fix=ns.fix,
        uninstall=ns.uninstall,
        link_mode=ns.link_mode,
    )
```

`setup.py` — add `_run_fix` after `_run_doctor`:

```python
def _run_fix(console: Console, *, link_mode_option: str | None) -> int:
    link_mode = _resolve_link_mode(link_mode_option)
    configure_path(
        load_tools(_REGISTRY),
        console,
        platform=detect(),
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_rc_paths_for_mode(link_mode),
        link_mode=link_mode,
    )
    return 0
```

(No re-audit after writing: the process PATH cannot change until the shell
restarts, so a post-fix audit would re-show "missing" — exactly the confusion
this split removes. `configure_path`'s own closing line is the message.)

In `main`, insert the fix branch between doctor and uninstall:

```python
    if options.doctor:
        return _run_doctor(console)
    if options.fix:
        return _run_fix(console, link_mode_option=options.link_mode)
    if options.uninstall:
        return _run_uninstall(console, assume_yes=options.yes)
```

`Makefile` — update the `.PHONY` line and the doctor/fix targets:

```make
.PHONY: help install build setup run doctor fix uninstall validate test
```

```make
doctor:  ## Audit PATH (read-only report; `make fix` applies changes)
	uv run setup.py --doctor

fix:  ## Wire PATH into your shell (~/.myshellrc + rc files)
	uv run setup.py --fix
```

- [ ] **Step 4: Run the full gate**

Run: `make validate && make test`
Expected: all pass, coverage 100%. Smoke: `uv run setup.py --help` shows `--fix`; `make help` lists `fix`. Do NOT run a real `--doctor`/`--fix` against the dev machine's home.

- [ ] **Step 5: Commit**

```bash
git add installer/cli.py setup.py Makefile tests/test_cli.py
git commit -m "feat: add 'make fix' / --fix as the explicit PATH-wiring action"
```

---

### Task 4: Documentation

**Files:**
- Modify: `README.md:104`, `README.md:144-164`, `README.md:182`
- Modify: `CLAUDE.md` (commands list)

- [ ] **Step 1: Update README**

Line 104 block becomes:

```sh
make setup ARGS="--all"                      # install everything
make setup ARGS="--categories search,data"   # only some categories
make doctor                                  # audit PATH (read-only report)
make fix                                     # wire PATH into your shell
```

Replace the `## PATH doctor` section body (keep the surrounding sections) with:

```markdown
## PATH doctor & fix

`make doctor` is a **read-only report**: it audits the live PATH against the bin
dirs the installer manages and reports any that are **missing** from PATH,
**broken** (directory gone), or **duplicated** — then points you at `make fix`.
Only directories that actually exist on disk are managed, so tools you never
installed are never reported. It changes nothing.

`make fix` applies the wiring:

- Writes every managed bin dir as `export PATH` into a single managed block in
  `~/.myshellrc` — **no duplicate entries**.
- Ensures `source ~/.myshellrc` exists in `~/.zshrc` (if present) and `~/.bashrc`,
  idempotently (it never adds the `source` line twice).
- Lets you choose how PATH is wired (`--link-mode`): **centralized** (one
  `~/.myshellrc` sourced from both rc files), **single** (sourced from your current
  shell only), or **split** (the PATH block written directly into each rc file).

After an install, the wizard audits your live PATH and — when a tool's own
installer added a duplicate `export PATH` line to `.bashrc`/`.zshrc` for a
directory `~/.myshellrc` already covers — previews those lines and offers to
remove them. Your own content is never touched, and the removal always asks first.

```sh
make doctor   # diagnose
make fix      # apply
```
```

In the Development command table, replace the `make doctor` row and add `make fix` below it:

```markdown
| `make doctor`    | audit `PATH` (read-only report)                                 |
| `make fix`       | wire `PATH` into your shell (`~/.myshellrc` + rc files)         |
```

- [ ] **Step 2: Update CLAUDE.md**

In the commands list, replace the `make doctor` line with:

```markdown
- `make doctor`    — audit PATH (read-only report)
- `make fix`       — wire `~/.myshellrc` + shell rc files into your PATH
```

- [ ] **Step 3: Run the gate and commit**

Run: `make validate && make test`
Expected: all pass (docs-only change; the gate guards against accidental code edits).

```bash
git add README.md CLAUDE.md
git commit -m "docs: document the doctor/fix split"
```

---

## Acceptance (from the spec — the reporting machine)

With brew/bun absent and `~/Library/pnpm` present but not on PATH:

```
$ make doctor
  missing from PATH: /Users/ramon/Library/pnpm
Run 'make fix' to wire PATH into your shell.

$ make fix
? How should PATH be wired into your shells? …
PATH configured in /Users/ramon/.myshellrc (restart your shell or source it).
```

No `/opt/homebrew/bin`, no `~/.bun/bin`, no "Something went wrong". The USER
verifies this on their machine — never run real doctor/fix against the dev home.
