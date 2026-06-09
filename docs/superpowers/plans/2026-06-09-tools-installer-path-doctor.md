# tools-installer — PATH Doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After installs (and on demand via `--doctor`), make the shell PATH correct: write all tool bin dirs into a single managed, de-duplicated block in `~/.myshellrc`, wire `source ~/.myshellrc` into `~/.zshrc`/`~/.bashrc` idempotently, and audit the live PATH for missing / broken / duplicated dirs — surfacing a troubleshooting link to the project repo when something is wrong.

**Architecture:** A pure, fully-tested core in `installer/` (`shellrc.py` for the managed `~/.myshellrc` block + rc `source` wiring; `doctor.py` for the PATH audit; `links.py` for canonical URLs; extensions to `render.py`/`cli.py`/`app.py`), plus `setup.py` wiring real home paths. All filesystem and PATH access is injected (tests use `tmp_path` and a fake PATH string + dir-existence check) — no real `$HOME` writes in the suite. A new `docs/TROUBLESHOOTING.md` documents common problems; the doctor and any failed install print a link to it.

**Tech Stack:** Python ≥3.11, stdlib `pathlib`/`os`; existing `installer.model`, `installer.platform`, and the Plan 4 wizard modules (`cli`, `render`, `app`, `setup.py`).

This plan follows [`CLAUDE.md`](../../../CLAUDE.md) and [`.claude/`](../../../.claude/): never bypass a gate, coherent commits, English only. Each task ends green on `make validate && make test` (coverage ≥ 90%, currently 100% over `installer/`). Builds on the Foundation, Execution-Engine, Download-Executors, and Interactive-TUI plans.

---

## Background the engineer needs

- **Existing surfaces this plan uses (do not change their behavior):**
  - `installer/model.py`: `Tool(id, name, category, cmd, methods, priority, audience, desc)`; `Method(kind, params: dict[str, object])`. Some methods carry a `bin_dir` param (a `str`), e.g. the `github_release`/`script` methods.
  - `installer/locations.py`: `bin_dir(declared)`, `ensure_dir`, `prepend_path`. The default userspace bin dir is `~/.local/bin`.
  - `installer/cli.py`: `Options(all, categories, yes)` frozen; `parse_args(argv)`.
  - `installer/render.py`: `render_audit`, `render_summary` (write to an injected `rich.Console`).
  - `installer/app.py`: `run_wizard(...) -> Summary | None`.
  - `setup.py` (repo root): composition root; the only place that imports `questionary`; performs real terminal IO and now real home-path wiring. Outside coverage source, pyright `include`, and vulture `paths` — but it IS ruff lint/format-gated (Makefile `validate`).
- **Strict-typing rules that bite this repo** (same as prior plans): no `from __future__ import annotations`; annotate test fixtures (`tmp_path: Path`, `monkeypatch: pytest.MonkeyPatch`); prefer a typed `def` over a bare `lambda` in a loosely-typed context (a `lambda` assigned to a `Callable`-typed parameter is fine).
- **vulture at `min_confidence=80` only reports unused *imports* (90%) and unreachable code (100%)** — NOT unused functions/constants (≤60%). So a pure function or a module-level URL constant used only by tests will not be flagged; but importing a name you do not use WILL be flagged. Per commit: import only what you use.
- **Coverage discipline:** `source=["installer"]`, `branch=true`, currently 100%. Everything under `installer/` is measured — keep all branchy logic there and test it. `setup.py` is the composition boundary (not measured/type-checked). Do not move testable logic into `setup.py`.
- **Idempotency is the core requirement.** `~/.myshellrc` and the rc `source` wiring use marker-delimited blocks so re-running only ever rewrites the managed block and never duplicates entries — even across many runs. This must be covered by "apply twice, assert identical / no duplication" tests.
- **The repo URL is `https://github.com/castocolina/tools-installer`.** The doctor and any failed install print the troubleshooting link `…/blob/main/docs/TROUBLESHOOTING.md`.

## File Structure

| File | Responsibility |
| ---- | -------------- |
| `docs/TROUBLESHOOTING.md` | User-facing common-problems guide (PATH, restart shell, rate-limit, immutable distros, brew, permissions) |
| `installer/links.py` | `REPO_URL`, `TROUBLESHOOTING_URL` — canonical project URLs |
| `installer/shellrc.py` | `collect_bin_dirs`; managed-block render + idempotent `apply_block`; `write_myshellrc`; `ensure_source` |
| `installer/doctor.py` | `DoctorReport`; `audit_path` (missing/broken/duplicated); `has_problems` |
| `installer/render.py` | (extend) `render_doctor`, `render_troubleshooting` |
| `installer/cli.py` | (extend) add `doctor: bool` to `Options` + `--doctor` flag |
| `installer/app.py` | (extend) `configure_path`, `run_doctor` (compose shellrc + doctor + render) |
| `setup.py` | (extend) route `--doctor`; wire real `~/.myshellrc`/`~/.zshrc`/`~/.bashrc`; print link on failed install |
| `tests/test_links.py`, `tests/test_shellrc.py`, `tests/test_doctor.py`, `tests/test_render.py` (extend), `tests/test_cli.py` (extend), `tests/test_app.py` (extend) | unit tests |

Dependency direction stays one-way: `app` → {`shellrc`, `doctor`, `render`, `cli`, `selection`, ...} → {`model`, `links`, ...}. `setup.py` composes everything with real paths.

---

### Task 1: Troubleshooting doc + canonical URLs

**Files:**
- Create: `docs/TROUBLESHOOTING.md`
- Create: `installer/links.py`
- Test: `tests/test_links.py`

- [ ] **Step 1: Write the failing test** — `tests/test_links.py`:

```python
from installer.links import REPO_URL, TROUBLESHOOTING_URL


def test_repo_url_is_the_project_repo():
    assert REPO_URL == "https://github.com/castocolina/tools-installer"


def test_troubleshooting_url_points_into_the_repo_docs():
    assert TROUBLESHOOTING_URL.startswith(REPO_URL)
    assert TROUBLESHOOTING_URL.endswith("docs/TROUBLESHOOTING.md")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_links.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.links'`.

- [ ] **Step 3: Implement `installer/links.py`**

```python
"""Canonical project URLs surfaced to users when they hit problems."""

REPO_URL = "https://github.com/castocolina/tools-installer"
TROUBLESHOOTING_URL = f"{REPO_URL}/blob/main/docs/TROUBLESHOOTING.md"
```

- [ ] **Step 4: Create `docs/TROUBLESHOOTING.md`**

```markdown
# Troubleshooting

If something goes wrong, this page lists the common problems and fixes. If your
issue is not here, please open an issue at
<https://github.com/castocolina/tools-installer/issues>.

## A tool installed but the command is "not found"

The tool was installed into a userspace bin dir (usually `~/.local/bin`) that is
not on your `PATH` in the current shell.

1. Run the PATH doctor: `make run` then choose the doctor, or `uv run setup.py --doctor`.
   It writes every bin dir into a managed block in `~/.myshellrc` and wires
   `source ~/.myshellrc` into your `~/.zshrc` / `~/.bashrc`.
2. Restart your shell, or run `. ~/.myshellrc` in the current one.
3. Re-check with `command -v <tool>`.

## "missing from PATH" persists after running the doctor

The doctor updates your shell rc files, but the current shell process keeps its
old `PATH` until you restart it (or `source ~/.myshellrc`). Open a new terminal
and re-run the doctor — the entry should now be present.

## A bin dir is reported as "does not exist"

A declared bin dir is missing on disk. This is usually harmless (no tool has been
installed there yet); it is created on first install. If a tool that should live
there is missing, re-run the installer for it.

## GitHub rate-limit / no network when resolving a version

`github_release` tools resolve their latest version from the GitHub API. On a
rate-limited or offline machine that lookup fails and the tool is reported as
`failed` in the summary (the run is not aborted). Retry later, or install that
tool via its native package manager / brew.

## Immutable / atomic distros (Bazzite, Silverblue)

The native package-manager step is skipped by default to avoid `rpm-ostree`
reboots. Tools install into userspace (`~/.local`) or via brew-linux instead.

## Permission denied writing to a bin dir

The installer never uses `sudo` for userspace installs. If a bin dir is not
writable, point the tool at a writable `bin_dir` (e.g. `~/.local/bin`) or fix the
directory's ownership.

## Homebrew is optional

Homebrew is never a prerequisite. It is offered as an optional package; an
official `.sh` installer or a release archive is always preferred when available.
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_links.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add docs/TROUBLESHOOTING.md installer/links.py tests/test_links.py
git commit -m "$(printf 'docs: add troubleshooting guide and canonical project URLs\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` and `make test` (coverage ≥ 90%, expect 100%) MUST pass before committing. Note: `links.py` is two module-level constants; importing it in the test executes (covers) both lines. vulture will not flag the constants (unused variables are below the 80 confidence threshold).

---

### Task 2: Managed `~/.myshellrc` block + rc source wiring

**Files:**
- Create: `installer/shellrc.py`
- Test: `tests/test_shellrc.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_shellrc.py`:

```python
from pathlib import Path

from installer.model import Method, Tool
from installer.shellrc import (
    apply_block,
    collect_bin_dirs,
    ensure_source,
    managed_block,
    write_myshellrc,
)


def _tool(tool_id: str, bin_dir: str | None) -> Tool:
    params: dict[str, object] = {"formula": tool_id}
    if bin_dir is not None:
        params = {"member": tool_id, "bin_dir": bin_dir}
    kind = "github_release" if bin_dir is not None else "brew"
    return Tool(
        id=tool_id,
        name=tool_id,
        category="search",
        cmd=tool_id,
        methods=(Method(kind=kind, params=params),),
    )


def test_collect_bin_dirs_defaults_first_then_declared_deduped():
    default = Path("/home/u/.local/bin")
    tools = [
        _tool("rg", "/home/u/.local/bin"),  # same as default -> deduped
        _tool("fd", "/home/u/tools/bin"),
        _tool("jq", None),  # brew, no bin_dir
    ]
    assert collect_bin_dirs(tools, default) == [
        Path("/home/u/.local/bin"),
        Path("/home/u/tools/bin"),
    ]


def test_collect_bin_dirs_expands_user():
    default = Path("/d")
    tools = [_tool("rg", "~/x/bin")]
    result = collect_bin_dirs(tools, default)
    assert result[0] == Path("/d")
    assert result[1] == Path.home() / "x" / "bin"


def test_managed_block_exports_each_dir_between_markers():
    block = managed_block([Path("/a/bin"), Path("/b/bin")])
    assert block.splitlines() == [
        "# >>> tools-installer path >>>",
        'export PATH="/a/bin:$PATH"',
        'export PATH="/b/bin:$PATH"',
        "# <<< tools-installer path <<<",
    ]


def test_apply_block_appends_when_absent_and_preserves_user_content():
    out = apply_block("# my rc\nalias x=y\n", "# >>> tools-installer path >>>\nX\n# <<< tools-installer path <<<")
    assert out == (
        "# my rc\nalias x=y\n\n"
        "# >>> tools-installer path >>>\nX\n# <<< tools-installer path <<<\n"
    )


def test_apply_block_replaces_existing_block_idempotently():
    block_v1 = "# >>> tools-installer path >>>\nOLD\n# <<< tools-installer path <<<"
    block_v2 = "# >>> tools-installer path >>>\nNEW\n# <<< tools-installer path <<<"
    once = apply_block("head\n" + block_v1 + "\ntail\n", block_v2)
    twice = apply_block(once, block_v2)
    assert "OLD" not in once
    assert "NEW" in once
    assert once.count("# >>> tools-installer path >>>") == 1
    assert twice == once  # idempotent


def test_write_myshellrc_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    bin_dirs = [Path("/a/bin"), Path("/b/bin")]
    write_myshellrc(bin_dirs, rc)
    first = rc.read_text()
    write_myshellrc(bin_dirs, rc)
    assert rc.read_text() == first
    assert first.count("# >>> tools-installer path >>>") == 1
    assert 'export PATH="/a/bin:$PATH"' in first


def test_write_myshellrc_preserves_existing_user_lines(tmp_path: Path):
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    write_myshellrc([Path("/a/bin")], rc)
    text = rc.read_text()
    assert "export EDITOR=vim" in text
    assert 'export PATH="/a/bin:$PATH"' in text


def test_ensure_source_adds_once_and_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# zsh config\n")
    myshellrc = tmp_path / ".myshellrc"
    ensure_source(rc, myshellrc)
    after_first = rc.read_text()
    ensure_source(rc, myshellrc)
    assert rc.read_text() == after_first
    assert after_first.count("# >>> tools-installer source >>>") == 1
    assert f'. "{myshellrc}"' in after_first
    assert "# zsh config" in after_first


def test_ensure_source_creates_file_when_missing(tmp_path: Path):
    rc = tmp_path / ".bashrc"  # does not exist yet
    myshellrc = tmp_path / ".myshellrc"
    ensure_source(rc, myshellrc)
    assert rc.exists()
    assert f'. "{myshellrc}"' in rc.read_text()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_shellrc.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.shellrc'`.

- [ ] **Step 3: Implement `installer/shellrc.py`**

```python
"""Manage ~/.myshellrc as one marker-delimited PATH block, and wire `source` into rc files.

Every write is idempotent: only the marked block is ever rewritten, user content is
preserved, and entries are never duplicated across runs.
"""
from pathlib import Path

from installer.model import Tool

_PATH_BEGIN = "# >>> tools-installer path >>>"
_PATH_END = "# <<< tools-installer path <<<"
_SOURCE_BEGIN = "# >>> tools-installer source >>>"
_SOURCE_END = "# <<< tools-installer source <<<"


def collect_bin_dirs(tools: list[Tool], default: Path) -> list[Path]:
    """The default bin dir plus every method-declared bin_dir, expanded and deduped in order."""
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        resolved = path.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            dirs.append(resolved)

    add(default)
    for tool in tools:
        for method in tool.methods:
            raw = method.params.get("bin_dir")
            if isinstance(raw, str) and raw:
                add(Path(raw))
    return dirs


def managed_block(bin_dirs: list[Path]) -> str:
    """Marker-delimited block exporting each bin dir onto PATH."""
    lines = [_PATH_BEGIN]
    lines.extend(f'export PATH="{directory}:$PATH"' for directory in bin_dirs)
    lines.append(_PATH_END)
    return "\n".join(lines)


def apply_block(content: str, block: str, begin: str = _PATH_BEGIN, end: str = _PATH_END) -> str:
    """Replace an existing begin..end block in content, else append it. Idempotent."""
    lines = content.split("\n")
    if begin in lines:
        start = lines.index(begin)
        for stop in range(start, len(lines)):
            if lines[stop] == end:
                merged = lines[:start] + block.split("\n") + lines[stop + 1 :]
                return "\n".join(merged)
    base = content.rstrip("\n")
    if base:
        return f"{base}\n\n{block}\n"
    return f"{block}\n"


def write_myshellrc(bin_dirs: list[Path], path: Path) -> None:
    """Idempotently write the managed PATH block into ~/.myshellrc, preserving the rest."""
    existing = path.read_text() if path.exists() else ""
    path.write_text(apply_block(existing, managed_block(bin_dirs)))


def ensure_source(rc_path: Path, myshellrc_path: Path) -> None:
    """Ensure rc_path sources ~/.myshellrc via a marker block, without duplicating it."""
    block = "\n".join(
        [
            _SOURCE_BEGIN,
            f'[ -f "{myshellrc_path}" ] && . "{myshellrc_path}"',
            _SOURCE_END,
        ]
    )
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, block, begin=_SOURCE_BEGIN, end=_SOURCE_END))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_shellrc.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/shellrc.py tests/test_shellrc.py
git commit -m "$(printf 'feat: manage ~/.myshellrc path block and rc source wiring\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` and `make test` (coverage ≥ 90%, expect 100%) MUST pass before committing. The "apply twice == once" and marker-count assertions are the idempotency guard — do not weaken them.

> Note: `apply_block` only treats a block as present when BOTH markers are found (begin via `in`, end scanned after it). A begin marker without a matching end falls through to append — an acceptable, rare malformed-file case. The default-arg markers let `ensure_source` reuse the exact same idempotent logic with its own marker pair.

---

### Task 3: PATH audit (missing / broken / duplicated)

**Files:**
- Create: `installer/doctor.py`
- Test: `tests/test_doctor.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_doctor.py`:

```python
from pathlib import Path

from installer.doctor import DoctorReport, audit_path, has_problems


def _exists(present: set[str]):
    def exists(path: Path) -> bool:
        return str(path) in present

    return exists


def test_audit_flags_missing_broken_and_duplicated():
    bin_dirs = [Path("/a/bin"), Path("/b/bin"), Path("/c/bin")]
    path_value = "/a/bin:/b/bin:/b/bin:/usr/bin"
    exists = _exists({"/a/bin", "/b/bin"})  # /c/bin does not exist
    report = audit_path(bin_dirs, path_value, exists)
    assert report.missing == (Path("/c/bin"),)  # declared but not on PATH
    assert report.broken == (Path("/c/bin"),)  # does not exist on disk
    assert report.duplicated == (Path("/b/bin"),)  # appears twice on PATH


def test_audit_clean_when_all_present_unique_and_existing():
    bin_dirs = [Path("/a/bin")]
    report = audit_path(bin_dirs, "/a/bin:/usr/bin", _exists({"/a/bin"}))
    assert report == DoctorReport(missing=(), broken=(), duplicated=())
    assert has_problems(report) is False


def test_audit_ignores_empty_path_entries():
    report = audit_path([Path("/a/bin")], "/a/bin::", _exists({"/a/bin"}))
    assert report.duplicated == ()


def test_has_problems_true_when_any_bucket_nonempty():
    assert has_problems(DoctorReport(missing=(Path("/x"),), broken=(), duplicated=())) is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_doctor.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.doctor'`.

- [ ] **Step 3: Implement `installer/doctor.py`**

```python
"""Audit declared bin dirs against the live PATH: missing, broken, or duplicated."""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DoctorReport:
    missing: tuple[Path, ...]  # declared but not on PATH
    broken: tuple[Path, ...]  # does not exist on disk
    duplicated: tuple[Path, ...]  # appears more than once on PATH


def audit_path(
    bin_dirs: list[Path], path_value: str, exists: Callable[[Path], bool]
) -> DoctorReport:
    """Classify each declared bin dir against the current PATH string and disk state."""
    counts: dict[Path, int] = {}
    for entry in path_value.split(":"):
        if entry:
            key = Path(entry)
            counts[key] = counts.get(key, 0) + 1
    missing = tuple(directory for directory in bin_dirs if directory not in counts)
    broken = tuple(directory for directory in bin_dirs if not exists(directory))
    duplicated = tuple(directory for directory in bin_dirs if counts.get(directory, 0) > 1)
    return DoctorReport(missing=missing, broken=broken, duplicated=duplicated)


def has_problems(report: DoctorReport) -> bool:
    """True if the report has any missing, broken, or duplicated bin dir."""
    return bool(report.missing or report.broken or report.duplicated)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_doctor.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/doctor.py tests/test_doctor.py
git commit -m "$(printf 'feat: audit the PATH for missing, broken, and duplicated bin dirs\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` and `make test` (coverage ≥ 90%, expect 100%) MUST pass before committing.

---

### Task 4: Render the doctor report + troubleshooting link

**Files:**
- Modify: `installer/render.py`
- Test: `tests/test_render.py` (extend)

- [ ] **Step 1: Add the failing tests** — append to `tests/test_render.py`:

```python
def test_render_doctor_reports_problems_and_link():
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    report = DoctorReport(
        missing=(Path("/a/bin"),),
        broken=(Path("/c/bin"),),
        duplicated=(Path("/b/bin"),),
    )
    console, buf = _console()
    render_doctor(report, console)
    out = buf.getvalue()
    assert "/a/bin" in out and "/c/bin" in out and "/b/bin" in out
    assert "missing from PATH" in out
    assert "github.com/castocolina/tools-installer" in out


def test_render_doctor_healthy_has_no_link():
    from installer.doctor import DoctorReport
    from installer.render import render_doctor

    console, buf = _console()
    render_doctor(DoctorReport(missing=(), broken=(), duplicated=()), console)
    out = buf.getvalue()
    assert "healthy" in out.lower()
    assert "github.com" not in out


def test_render_troubleshooting_prints_link():
    from installer.render import render_troubleshooting

    console, buf = _console()
    render_troubleshooting(console)
    assert "github.com/castocolina/tools-installer" in buf.getvalue()
```

Add `from pathlib import Path` to the imports at the top of `tests/test_render.py` if it is not already there.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_render.py -q`
Expected: FAIL — `ImportError: cannot import name 'render_doctor'` (and `render_troubleshooting`).

- [ ] **Step 3: Extend `installer/render.py`**

Add these imports at the top (next to the existing imports), importing ONLY what is used:

```python
from installer.doctor import DoctorReport, has_problems
from installer.links import TROUBLESHOOTING_URL
```

Append these two functions to `installer/render.py`:

```python
def render_troubleshooting(console: Console) -> None:
    """Point the user at the troubleshooting guide."""
    console.print(f"Something went wrong. Troubleshooting: {TROUBLESHOOTING_URL}")


def render_doctor(report: DoctorReport, console: Console) -> None:
    """Print the PATH audit; on any problem, also print the troubleshooting link."""
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
    render_troubleshooting(console)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_render.py -q`
Expected: PASS (existing 3 + 3 new = 6 tests).

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/render.py tests/test_render.py
git commit -m "$(printf 'feat: render the PATH doctor report with a troubleshooting link\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` and `make test` (coverage ≥ 90%, expect 100%) MUST pass before committing. Both branches of `render_doctor` (healthy vs problems) are covered by the two new tests.

---

### Task 5: Add the `--doctor` flag

**Files:**
- Modify: `installer/cli.py`
- Test: `tests/test_cli.py` (extend)

- [ ] **Step 1: Add the failing tests** — append to `tests/test_cli.py`:

```python
def test_doctor_defaults_false():
    assert parse_args([]).doctor is False


def test_doctor_flag():
    assert parse_args(["--doctor"]).doctor is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL — `AttributeError: 'Options' object has no attribute 'doctor'` (and the `--doctor` arg is unknown).

- [ ] **Step 3: Modify `installer/cli.py`**

Add a `doctor` field WITH a default (so all existing `Options(all=, categories=, yes=)` construction sites — including the Plan 4 wizard tests — keep working):

```python
@dataclass(frozen=True)
class Options:
    all: bool
    categories: tuple[str, ...]
    yes: bool
    doctor: bool = False
```

Register the flag (place it after `--yes`):

```python
    parser.add_argument("--doctor", action="store_true", help="audit and fix the PATH, then exit")
```

And include it in the returned `Options`:

```python
    return Options(all=ns.all, categories=tuple(categories), yes=ns.yes, doctor=ns.doctor)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS (existing 7 + 2 new = 9 tests). The existing `parse_args([]) == Options(all=False, categories=(), yes=False)` test still passes because `doctor` defaults to `False` on both sides.

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/cli.py tests/test_cli.py
git commit -m "$(printf 'feat: add the --doctor flag\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` and `make test` (coverage ≥ 90%, expect 100%) MUST pass before committing.

---

### Task 6: Compose the doctor flow and post-install PATH wiring

**Files:**
- Modify: `installer/app.py`
- Test: `tests/test_app.py` (extend)

- [ ] **Step 1: Add the failing tests** — append to `tests/test_app.py`:

```python
def test_configure_path_writes_myshellrc_and_wires_all_rcs(tmp_path: Path):
    from installer.app import configure_path

    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# zsh\n")
    bashrc = tmp_path / ".bashrc"  # absent -> MUST be created and wired
    console, _buf = _console()

    configure_path(
        [_tool("rg", "search")],
        console,
        default_bin_dir=tmp_path / ".local" / "bin",
        myshellrc_path=myshellrc,
        rc_paths=[zshrc, bashrc],
    )

    assert myshellrc.exists()
    assert "# >>> tools-installer path >>>" in myshellrc.read_text()
    assert zshrc.exists() and "tools-installer source" in zshrc.read_text()
    # Both rc files are always wired; an absent one is created.
    assert bashrc.exists() and "tools-installer source" in bashrc.read_text()
    assert "# zsh" in zshrc.read_text()  # existing content preserved


def test_run_doctor_reports_and_fixes(tmp_path: Path):
    from pathlib import Path as _P

    from installer.app import run_doctor

    myshellrc = tmp_path / ".myshellrc"
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# zsh\n")
    bin_dir = tmp_path / ".local" / "bin"
    console, buf = _console()

    def exists(path: _P) -> bool:
        return False  # nothing on disk -> broken + missing

    report = run_doctor(
        [_tool("rg", "search")],
        console,
        default_bin_dir=bin_dir,
        path_value="/usr/bin",
        exists=exists,
        myshellrc_path=myshellrc,
        rc_paths=[zshrc],
        fix=True,
    )

    assert bin_dir in report.missing
    assert "github.com/castocolina/tools-installer" in buf.getvalue()
    assert myshellrc.exists()  # fix=True wrote the managed block
    assert "tools-installer source" in zshrc.read_text()


def test_run_doctor_without_fix_does_not_write(tmp_path: Path):
    from pathlib import Path as _P

    from installer.app import run_doctor

    myshellrc = tmp_path / ".myshellrc"
    console, _buf = _console()

    def exists(path: _P) -> bool:
        return True

    run_doctor(
        [_tool("rg", "search")],
        console,
        default_bin_dir=tmp_path / "bin",
        path_value="/usr/bin",
        exists=exists,
        myshellrc_path=myshellrc,
        rc_paths=[],
        fix=False,
    )
    assert not myshellrc.exists()  # fix=False is read-only
```

Note: `_tool(tool_id, category)` and `_console()` already exist in `tests/test_app.py`; `_tool` builds a tool with a `brew` method (no `bin_dir`), so `collect_bin_dirs` will fall back to just the `default_bin_dir`. That is fine for these tests.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_app.py -q`
Expected: FAIL — `ImportError: cannot import name 'configure_path'` (and `run_doctor`).

- [ ] **Step 3: Extend `installer/app.py`**

Update the import block. `app.py` ALREADY has `from installer.render import render_audit, render_summary` — MERGE `render_doctor` into that existing line (do NOT add a second `from installer.render` line; ruff's isort rule rejects duplicate-from imports). Add the genuinely new lines:

```python
from pathlib import Path           # new (stdlib group, top)

from installer.doctor import DoctorReport, audit_path                       # new
from installer.render import render_audit, render_doctor, render_summary    # MERGED: + render_doctor
from installer.shellrc import collect_bin_dirs, ensure_source, write_myshellrc  # new
```

`Callable` and `Console` are already imported in `app.py` (from `collections.abc` and `rich.console`); `Tool` is already imported. Run `uv run ruff check --fix installer/app.py` if isort ordering needs settling.

Append these two functions to `installer/app.py`:

```python
def configure_path(
    tools: list[Tool],
    console: Console,
    *,
    default_bin_dir: Path,
    myshellrc_path: Path,
    rc_paths: list[Path],
) -> None:
    """Write the managed PATH block and wire `source` into every rc path.

    Each rc file is wired idempotently; an absent rc file is created so the PATH
    block is sourced even on a fresh machine with no shell rc yet.
    """
    bin_dirs = collect_bin_dirs(tools, default_bin_dir)
    write_myshellrc(bin_dirs, myshellrc_path)
    for rc_path in rc_paths:
        ensure_source(rc_path, myshellrc_path)
    console.print(f"PATH configured in {myshellrc_path} (restart your shell or source it).")


def run_doctor(
    tools: list[Tool],
    console: Console,
    *,
    default_bin_dir: Path,
    path_value: str,
    exists: Callable[[Path], bool],
    myshellrc_path: Path,
    rc_paths: list[Path],
    fix: bool,
) -> DoctorReport:
    """Audit the PATH, render the report, and (if fix) write the managed config."""
    bin_dirs = collect_bin_dirs(tools, default_bin_dir)
    report = audit_path(bin_dirs, path_value, exists)
    render_doctor(report, console)
    if fix:
        configure_path(
            tools,
            console,
            default_bin_dir=default_bin_dir,
            myshellrc_path=myshellrc_path,
            rc_paths=rc_paths,
        )
    return report
```

`Callable` and `Console` are already imported in `app.py` (from `collections.abc` and `rich.console`); `Tool` is already imported. Add only the missing imports listed above.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_app.py -q`
Expected: PASS (existing 5 + 3 new = 8 tests). Verify `make test` reports 100% — both the `fix=True` and `fix=False` branches of `run_doctor`, and the rc-exists / rc-absent branches of `configure_path`, are covered.

- [ ] **Step 5: Format, validate, commit**

```bash
uv run ruff format installer tests
make validate && make test
git add installer/app.py tests/test_app.py
git commit -m "$(printf 'feat: compose the doctor flow and post-install PATH wiring\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` and `make test` (coverage ≥ 90%, expect 100%) MUST pass before committing.

---

### Task 7: Wire `--doctor` and post-install PATH into `setup.py`

**Files:**
- Modify: `setup.py`
- (No unit test — `setup.py` is the composition boundary: outside coverage/pyright/vulture, but ruff lint/format-gated.)

- [ ] **Step 1: Modify `setup.py`**

Replace the imports block and `main` so the entry point routes `--doctor`, configures PATH after a successful install, and prints the troubleshooting link when a tool fails. Keep `_ask_checkbox`/`_ask_confirm` unchanged. The full new file:

```python
"""Entry point for the tools-installer wizard. Run via `make run` (uv run setup.py).

This is the composition root: it performs the real terminal IO (questionary) and
the real home-path wiring, and composes the pure, fully-tested installer package.
It deliberately lives outside the `installer/` package so the untyped questionary
boundary is isolated from the strict-typed, fully-covered core.
"""
import os
import sys
from pathlib import Path

import questionary
from rich.console import Console

from installer.app import configure_path, run_doctor, run_wizard
from installer.cli import parse_args
from installer.model import load_tools
from installer.platform import detect
from installer.prompt import CallbackPrompter
from installer.render import render_troubleshooting
from installer.selection import Choice

_REGISTRY = Path(__file__).parent / "installer" / "registry.toml"
_DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"
_MYSHELLRC = Path.home() / ".myshellrc"
_RC_PATHS = [Path.home() / ".zshrc", Path.home() / ".bashrc"]


def _ask_checkbox(message: str, choices: list[Choice]) -> list[str]:
    answer = questionary.checkbox(
        message,
        choices=[questionary.Choice(title=c.label, value=c.id, checked=c.checked) for c in choices],
    ).ask()
    return list(answer) if answer else []


def _ask_confirm(message: str) -> bool:
    return bool(questionary.confirm(message, default=True).ask())


def _run_doctor(console: Console) -> int:
    run_doctor(
        load_tools(_REGISTRY),
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        path_value=os.environ.get("PATH", ""),
        exists=Path.is_dir,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
        fix=True,
    )
    return 0


def main(argv: list[str]) -> int:
    options = parse_args(argv)
    console = Console()
    if options.doctor:
        return _run_doctor(console)
    can_proceed = options.all or bool(options.categories) or sys.stdin.isatty()
    if not can_proceed:
        console.print(
            "No TTY detected. Re-run with --all or --categories A,B (and --yes) for "
            "non-interactive use, or --doctor to fix the PATH."
        )
        return 2
    tools = load_tools(_REGISTRY)
    prompter = CallbackPrompter(ask_checkbox=_ask_checkbox, ask_confirm=_ask_confirm)
    summary = run_wizard(tools, detect(), prompter, console, options)
    if summary is None:
        console.print("Aborted.")
        return 0
    configure_path(
        tools,
        console,
        default_bin_dir=_DEFAULT_BIN_DIR,
        myshellrc_path=_MYSHELLRC,
        rc_paths=_RC_PATHS,
    )
    if summary.failed:
        render_troubleshooting(console)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Verify the non-interactive guidance still works**

Run: `printf '' | uv run setup.py; echo "exit=$?"`
Expected: prints the (updated) no-TTY guidance and `exit=2`.

- [ ] **Step 3: Verify `--help` shows `--doctor`**

Run: `uv run setup.py --help`
Expected: usage lists `--doctor`; exit 0.

- [ ] **Step 4: Verify the doctor runs end-to-end (writes real `~/.myshellrc`)**

`--doctor` writes to your real home (`~/.myshellrc`, and sources it into BOTH `~/.zshrc` and `~/.bashrc`, creating either if absent). Run it only where that is acceptable:

Run: `uv run setup.py --doctor; echo "exit=$?"`
Expected: prints the PATH audit (and the troubleshooting link if anything is missing/broken/duplicated), writes `~/.myshellrc`, and `exit=0`. Re-running is idempotent (no duplicate blocks).

- [ ] **Step 5: Confirm gates are unaffected and commit**

```bash
uv run ruff format installer tests setup.py
uv run ruff check setup.py
make validate && make test
git add setup.py
git commit -m "$(printf 'feat: route --doctor and configure PATH after install\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

`make validate` (which now also lints/format-checks `setup.py`) and `make test` MUST pass before committing. If `make validate` fails, STOP and fix — do not commit a failing tree.

> Note: `exists=Path.is_dir` passes the unbound method as the injected `Callable[[Path], bool]` — `Path.is_dir(some_path)` is how `audit_path` calls it. This keeps the real disk check in the composition root while the pure `audit_path` stays injectable.

---

## Definition of Done (this plan)

- [ ] `make validate` passes (ruff incl. `setup.py`, ruff format, pyright strict, bandit, vulture).
- [ ] `make test` passes with coverage ≥ 90% (the `installer/` additions should keep it at 100%).
- [ ] `~/.myshellrc` gets one managed, marker-delimited PATH block with every bin dir, **no duplicates**, preserving user content; re-running is idempotent.
- [ ] `source ~/.myshellrc` is wired into BOTH `~/.zshrc` and `~/.bashrc` via a marker block, **never duplicated**; an absent rc file is **created** so the block is sourced even on a fresh machine with no shell rc yet.
- [ ] `--doctor` audits the live PATH (missing / broken / duplicated), prints a report, fixes the rc files, and prints the troubleshooting link when there are problems.
- [ ] A failed install prints the troubleshooting link (`…/castocolina/tools-installer/blob/main/docs/TROUBLESHOOTING.md`).
- [ ] `docs/TROUBLESHOOTING.md` documents the common problems.
- [ ] Seven coherent commits (one per task).

## Known limitations (called out, not silently dropped)

- **The current process PATH is not mutated.** The doctor writes rc files; the user must restart the shell or `source ~/.myshellrc`. So "missing from PATH" can still be reported immediately after a fix — this is expected and documented in `TROUBLESHOOTING.md`.
- **No interactive "which fixes to apply" prompt.** `--doctor` applies the full managed config (write `~/.myshellrc` + wire both `~/.zshrc` and `~/.bashrc`, creating an absent one). A granular pick-list is out of scope for this slice.
- **Both rc files are created even for a shell you may not use** (e.g. a `~/.bashrc` on a zsh-only box). This is the chosen trade-off for guaranteeing the PATH block is sourced on a fresh machine; the created file contains only the managed `source` block.
- **`curl|bash` bootstrap and macOS GUI/app installs remain Plan 6.** This plan assumes the repo is cloned and `uv` is present.
- **Broken-symlink re-linking** (PRD risk note) is not handled; the doctor reports a non-existent dir as `broken` but does not repair symlinks.

## Follow-up plan (remaining roadmap)

6. **`curl|bash` bootstrap & packaging** — `install.sh` (detect OS/arch → ensure uv → fetch repo → run wizard); optional `brew-mac`/`brew-linux` registry entries; macOS GUI/`.app` install; release/publish flow and the stable `install.sh` URL.
