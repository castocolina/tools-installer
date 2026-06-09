# tools-installer Bootstrap (`install.sh`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `curl … | sh` bootstrap script that detects the platform, ensures `uv` is installed, clones the repo, and launches the existing wizard.

**Architecture:** A single POSIX `sh` script (`install.sh`) at the repo root, written as small testable functions (`detect_os`, `ensure_uv`, `fetch_repo`, `main`). It is **sourceable**: the bottom-of-file `main "$@"` call is guarded by a `TI_SOURCED` env flag so tests can source the file and call one function at a time. Tests are black-box: they run the script as a subprocess with a stubbed `PATH` where `uname`/`git`/`curl`/`uv` are tiny shell stubs that log their invocations to a file, so assertions check *what the script called* — never real network, git, or uv. This mirrors the injected-seam pattern the Python code already uses. `shellcheck` (via the `shellcheck-py` wheel) becomes a `make validate` gate.

**Tech Stack:** POSIX `sh`, `uv`, `git`, `curl`, `shellcheck-py`, `pytest` (subprocess black-box tests).

---

## Scope

In scope: `install.sh` bootstrap, its tests, the `shellcheck` gate, and a README quick-start. **Deferred to later sub-plans** (do NOT implement here): Homebrew registry entries (`brew-mac`/`brew-linux`), the macOS `.app`/`.dmg` GUI installer, the release/publish flow, and a `curl`-tarball fallback when `git` is absent (the script requires `git` and errors clearly if it is missing).

## Environment-variable contract (the script's "interface")

`install.sh` reads these, with the defaults shown. Tests override them to stay hermetic:

- `TI_REPO_URL` — repo to clone. Default `https://github.com/castocolina/tools-installer.git`.
- `TI_REF` — git branch/tag to clone. Default `main`.
- `TI_DIR` — clone destination. Default `${XDG_DATA_HOME:-$HOME/.local/share}/tools-installer`.
- `TI_UV_INSTALL_URL` — uv installer URL. Default `https://astral.sh/uv/install.sh`.
- `TI_NO_RUN` — if non-empty, install but do **not** launch the wizard.
- `TI_SOURCED` — if non-empty, suppress the bottom-of-file `main "$@"` call (test-only seam).
- `TI_LOG` — used **only by test stubs** to record calls; the real script never reads it.

## File Structure

- Create: `install.sh` — the bootstrap script (repo root).
- Create: `tests/test_install_sh.py` — black-box tests with a stubbed PATH harness.
- Modify: `pyproject.toml` — add `shellcheck-py` to the dev dependency group (via `uv add --dev`).
- Modify: `Makefile:20-29` — add `uv run shellcheck install.sh` to the `validate` target.
- Create or modify: `README.md` — add a "Quick start" section with the `curl | sh` one-liner.

---

## Task 1: Scaffold `install.sh`, the test harness, `detect_os`, and the shellcheck gate

**Files:**
- Create: `install.sh`
- Create: `tests/test_install_sh.py`
- Modify: `pyproject.toml` (dev deps)
- Modify: `Makefile:28-29`

- [ ] **Step 1: Add the shellcheck dev dependency**

Run:
```bash
uv add --dev shellcheck-py
uv run shellcheck --version
```
Expected: `uv` edits `pyproject.toml`/`uv.lock`, then prints a shellcheck version banner (e.g. `ShellCheck - shell script analysis tool / version: 0.10.x`).

- [ ] **Step 2: Write the test harness and the first failing tests**

Create `tests/test_install_sh.py` with the full harness. The interpreter is invoked by **absolute path** (`/bin/sh`) so the test-controlled `PATH` governs only the *script's* command lookups, not how the interpreter itself is found.

```python
"""Black-box tests for the install.sh bootstrap.

install.sh runs before the Python package exists, so it can't be tested
in-process. We exercise it as a subprocess with a stubbed PATH: each external
command (uname, git, curl, uv) is a tiny shell stub that logs its invocation to
$TI_LOG, so tests assert on *what the script called* -- never on real network,
git, or uv. This mirrors the injected-seam pattern the Python code uses.

Functions are tested in isolation by sourcing install.sh with TI_SOURCED set
(which suppresses the bottom-of-file `main "$@"` call) and invoking the target
function directly.
"""

import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "install.sh"


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@dataclass
class Harness:
    fakebin: Path
    home: Path
    log: Path
    repo_dir: Path

    def stub(self, name: str, body: str) -> None:
        path = self.fakebin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        _make_executable(path)

    def _env(self, extra: dict[str, str]) -> dict[str, str]:
        env: dict[str, str] = {
            "PATH": f"{self.fakebin}:/usr/bin:/bin",
            "HOME": str(self.home),
            "TI_LOG": str(self.log),
            "TI_DIR": str(self.repo_dir),
        }
        env.update(extra)
        return env

    def source(self, snippet: str, **extra: str) -> "subprocess.CompletedProcess[str]":
        env = self._env(extra)
        env["TI_SOURCED"] = "1"
        return subprocess.run(
            ["/bin/sh", "-c", f'. "{INSTALL_SH}"; {snippet}'],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def run(self, *args: str, **extra: str) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            ["/bin/sh", str(INSTALL_SH), *args],
            env=self._env(extra),
            capture_output=True,
            text=True,
            check=False,
        )

    def log_text(self) -> str:
        return self.log.read_text() if self.log.exists() else ""


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    h = Harness(
        fakebin=fakebin,
        home=home,
        log=tmp_path / "calls.log",
        repo_dir=tmp_path / "repo",
    )
    h.stub(
        "uname",
        'printf "uname %s\\n" "$*" >> "$TI_LOG"\n'
        'case "${1:-}" in\n'
        '  -s) printf "%s\\n" "${TI_OS:-Linux}" ;;\n'
        '  -m) printf "%s\\n" "${TI_ARCH:-x86_64}" ;;\n'
        '  *) printf "Linux\\n" ;;\n'
        "esac",
    )
    h.stub(
        "git",
        'printf "git %s\\n" "$*" >> "$TI_LOG"\n'
        'case "${1:-}" in\n'
        '  clone) mkdir -p "$TI_DIR" ;;\n'
        "esac",
    )
    return h


def test_detect_os_maps_darwin_to_macos(harness: Harness) -> None:
    result = harness.source("detect_os", TI_OS="Darwin")
    assert result.returncode == 0
    assert result.stdout.strip() == "macos"


def test_detect_os_maps_linux(harness: Harness) -> None:
    result = harness.source("detect_os", TI_OS="Linux")
    assert result.returncode == 0
    assert result.stdout.strip() == "linux"


def test_detect_os_rejects_unsupported(harness: Harness) -> None:
    result = harness.source("detect_os", TI_OS="MINGW64_NT")
    assert result.returncode != 0
    assert "unsupported OS" in result.stderr
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_install_sh.py -v`
Expected: FAIL — `install.sh` does not exist yet, so the subprocess can't source it (`detect_os: not found` / non-zero exit on the mapping tests).

- [ ] **Step 4: Create `install.sh` with `detect_os` and a minimal `main`**

```sh
#!/bin/sh
# tools-installer bootstrap: detect platform, ensure uv, fetch the repo, run the wizard.
#
# Usage (remote):
#   curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh -s -- --all --yes
#
# Overridable via environment (defaults shown):
#   TI_REPO_URL=https://github.com/castocolina/tools-installer.git
#   TI_REF=main
#   TI_DIR=${XDG_DATA_HOME:-$HOME/.local/share}/tools-installer
#   TI_UV_INSTALL_URL=https://astral.sh/uv/install.sh
#   TI_NO_RUN=          (set to any value to install without launching the wizard)
set -eu

TI_REPO_URL="${TI_REPO_URL:-https://github.com/castocolina/tools-installer.git}"
TI_REF="${TI_REF:-main}"
TI_DIR="${TI_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/tools-installer}"
TI_UV_INSTALL_URL="${TI_UV_INSTALL_URL:-https://astral.sh/uv/install.sh}"

die() {
    printf 'tools-installer: %s\n' "$1" >&2
    exit 1
}

detect_os() {
    os="$(uname -s)"
    case "$os" in
        Darwin) printf 'macos\n' ;;
        Linux) printf 'linux\n' ;;
        *) die "unsupported OS: $os (only macOS and Linux are supported)" ;;
    esac
}

main() {
    os="$(detect_os)"
    printf 'tools-installer: platform %s\n' "$os"
}

if [ -z "${TI_SOURCED:-}" ]; then
    main "$@"
fi
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_install_sh.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Add the shellcheck gate to `make validate`**

In `Makefile`, append a shellcheck line to the `validate` recipe, right after `uv run vulture`:

```make
	uv run vulture
	# install.sh is the curl|bash bootstrap; lint it as part of the gate.
	uv run shellcheck install.sh
```

- [ ] **Step 7: Verify the full gate is green**

Run: `make validate && make test`
Expected: ruff/pyright/bandit/vulture pass, `shellcheck install.sh` exits 0 (no output), pytest passes at 100% coverage (`installer` coverage unchanged — the new tests add no `installer` code).

- [ ] **Step 8: Commit**

```bash
git add install.sh tests/test_install_sh.py pyproject.toml uv.lock Makefile
git commit -m "feat: scaffold install.sh bootstrap with platform detection

Add the curl|bash entry point as a sourceable POSIX script and a stubbed-PATH
test harness. Gate it with shellcheck via the shellcheck-py wheel.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: `ensure_uv` — install uv only when missing

**Files:**
- Modify: `install.sh` (add `ensure_uv`, call it from `main`)
- Modify: `tests/test_install_sh.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_install_sh.py`:

```python
def test_ensure_uv_skips_when_already_present(harness: Harness) -> None:
    harness.stub("uv", 'printf "uv %s\\n" "$*" >> "$TI_LOG"')
    result = harness.source("ensure_uv")
    assert result.returncode == 0
    assert "curl" not in harness.log_text()  # no install attempt


def test_ensure_uv_installs_via_curl_when_missing(harness: Harness) -> None:
    # uv is absent from PATH; the curl stub simulates the official installer by
    # dropping a uv stub into the fake bin (and emits nothing to the `| sh` pipe).
    harness.stub(
        "curl",
        'printf "curl %s\\n" "$*" >> "$TI_LOG"\n'
        f'cat > "{harness.fakebin}/uv" <<\'INNER\'\n'
        "#!/bin/sh\n"
        'printf "uv %s\\n" "$*" >> "$TI_LOG"\n'
        "INNER\n"
        f'chmod +x "{harness.fakebin}/uv"',
    )
    result = harness.source("ensure_uv")
    assert result.returncode == 0
    log = harness.log_text()
    assert "curl" in log
    assert "astral.sh" in log
    assert (harness.fakebin / "uv").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_install_sh.py -k ensure_uv -v`
Expected: FAIL with `ensure_uv: not found` (function does not exist yet).

- [ ] **Step 3: Add `ensure_uv` and wire it into `main`**

In `install.sh`, add the function after `detect_os`:

```sh
ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    command -v curl >/dev/null 2>&1 || die "curl is required to install uv"
    printf 'tools-installer: installing uv...\n'
    curl -LsSf "$TI_UV_INSTALL_URL" | sh
    # The official installer drops uv in ~/.local/bin; make it visible now.
    if [ -f "$HOME/.local/bin/env" ]; then
        # shellcheck disable=SC1091
        . "$HOME/.local/bin/env"
    else
        PATH="$HOME/.local/bin:$PATH"
    fi
    command -v uv >/dev/null 2>&1 || die "uv installation failed"
}
```

Update `main` to call it:

```sh
main() {
    os="$(detect_os)"
    printf 'tools-installer: platform %s\n' "$os"
    ensure_uv
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_install_sh.py -k ensure_uv -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify the gate**

Run: `make validate && make test`
Expected: all green; `shellcheck install.sh` exits 0.

- [ ] **Step 6: Commit**

```bash
git add install.sh tests/test_install_sh.py
git commit -m "feat: install uv from the bootstrap only when missing

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: `fetch_repo` — clone fresh or fast-forward an existing checkout

**Files:**
- Modify: `install.sh` (add `fetch_repo`, call it from `main`)
- Modify: `tests/test_install_sh.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_install_sh.py`:

```python
def test_fetch_repo_clones_when_absent(harness: Harness) -> None:
    result = harness.source("fetch_repo")
    assert result.returncode == 0
    log = harness.log_text()
    assert "clone" in log
    assert str(harness.repo_dir) in log


def test_fetch_repo_pulls_when_present(harness: Harness) -> None:
    (harness.repo_dir / ".git").mkdir(parents=True)
    result = harness.source("fetch_repo")
    assert result.returncode == 0
    log = harness.log_text()
    assert "pull" in log
    assert "clone" not in log


def test_fetch_repo_requires_git(harness: Harness) -> None:
    # Drop git and restrict PATH to the fake bin so no system git is found.
    (harness.fakebin / "git").unlink()
    result = harness.source("fetch_repo", PATH=str(harness.fakebin))
    assert result.returncode != 0
    assert "git is required" in result.stderr
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_install_sh.py -k fetch_repo -v`
Expected: FAIL with `fetch_repo: not found`.

- [ ] **Step 3: Add `fetch_repo` and wire it into `main`**

In `install.sh`, add after `ensure_uv`:

```sh
fetch_repo() {
    command -v git >/dev/null 2>&1 || die "git is required to fetch tools-installer"
    if [ -d "$TI_DIR/.git" ]; then
        printf 'tools-installer: updating %s\n' "$TI_DIR"
        git -C "$TI_DIR" pull --ff-only
    else
        printf 'tools-installer: cloning into %s\n' "$TI_DIR"
        git clone --depth 1 --branch "$TI_REF" "$TI_REPO_URL" "$TI_DIR"
    fi
}
```

Update `main`:

```sh
main() {
    os="$(detect_os)"
    printf 'tools-installer: platform %s\n' "$os"
    ensure_uv
    fetch_repo
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_install_sh.py -k fetch_repo -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Verify the gate**

Run: `make validate && make test`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add install.sh tests/test_install_sh.py
git commit -m "feat: clone or fast-forward the repo from the bootstrap

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `main` wiring — launch the wizard, honor `TI_NO_RUN`, pass args through

**Files:**
- Modify: `install.sh` (finalize `main`)
- Modify: `tests/test_install_sh.py` (add end-to-end tests)

- [ ] **Step 1: Write the failing end-to-end tests**

Append to `tests/test_install_sh.py`. These use `harness.run(...)` (no `TI_SOURCED`), exercising the whole script:

```python
def test_run_installs_without_launching_when_no_run_set(harness: Harness) -> None:
    harness.stub("uv", 'printf "uv %s\\n" "$*" >> "$TI_LOG"')
    result = harness.run(TI_NO_RUN="1", TI_OS="Darwin")
    assert result.returncode == 0
    assert "skipping wizard" in result.stdout
    assert "setup.py" not in harness.log_text()


def test_run_launches_wizard_with_passthrough_args(harness: Harness) -> None:
    harness.stub("uv", 'printf "uv %s\\n" "$*" >> "$TI_LOG"')
    result = harness.run("--all", "--yes", TI_OS="Linux")
    assert result.returncode == 0
    assert "uv run setup.py --all --yes" in harness.log_text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_install_sh.py -k run -v`
Expected: FAIL — `main` does not yet launch the wizard, so neither "skipping wizard" nor the `uv run setup.py …` log line appears.

- [ ] **Step 3: Finalize `main`**

Replace `main` in `install.sh` with:

```sh
main() {
    os="$(detect_os)"
    printf 'tools-installer: platform %s\n' "$os"
    ensure_uv
    fetch_repo
    if [ -n "${TI_NO_RUN:-}" ]; then
        printf 'tools-installer: installed at %s (TI_NO_RUN set; skipping wizard)\n' "$TI_DIR"
        return 0
    fi
    cd "$TI_DIR"
    exec uv run setup.py "$@"
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_install_sh.py -k run -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify the whole suite and gate**

Run: `make validate && make test`
Expected: all green; `tests/test_install_sh.py` reports 10 passed; `installer` coverage still 100%.

- [ ] **Step 6: Commit**

```bash
git add install.sh tests/test_install_sh.py
git commit -m "feat: launch the wizard from the bootstrap with arg passthrough

Honor TI_NO_RUN for install-only runs and forward extra args to setup.py via
sh -s -- ...

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Document the one-liner in the README

**Files:**
- Create or modify: `README.md`

- [ ] **Step 1: Check whether a README exists**

Run: `ls README.md`
Expected: either the path (modify it) or `No such file or directory` (create it).

- [ ] **Step 2: Add the Quick start section**

If `README.md` does not exist, create it with this content. If it exists, insert this section directly under the top-level title.

```markdown
## Quick start

Install the AI dev environment with one command:

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
```

Pass wizard flags through `sh -s --`:

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh -s -- --all --yes
```

The bootstrap detects your platform, installs [uv](https://docs.astral.sh/uv/)
if it is missing, clones the repo to `~/.local/share/tools-installer`, and
launches the wizard. Override defaults with `TI_REPO_URL`, `TI_REF`, `TI_DIR`,
or `TI_UV_INSTALL_URL`, or set `TI_NO_RUN=1` to install without launching.
```

- [ ] **Step 3: Verify the gate (no code changed, but keep the discipline)**

Run: `make validate && make test`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the curl|sh quick-start one-liner

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:** Every scoped requirement maps to a task — platform detection (Task 1), uv bootstrap (Task 2), repo fetch (Task 3), wizard launch + arg passthrough + install-only mode (Task 4), discoverable usage docs (Task 5), and the shellcheck quality gate (Task 1). Deferred subsystems (brew, macOS GUI, release, tarball fallback) are explicitly listed under Scope and intentionally excluded.

**2. Placeholder scan:** No `TBD`/`TODO`/"handle edge cases"/"similar to Task N". Every code step shows complete file content or a complete function plus the exact `main` it must produce. Error paths (`die` on unsupported OS / missing curl / missing git / failed uv install) are concrete.

**3. Type/name consistency:** The env-var contract (`TI_REPO_URL`, `TI_REF`, `TI_DIR`, `TI_UV_INSTALL_URL`, `TI_NO_RUN`, `TI_SOURCED`, `TI_LOG`) is used identically in the script and the harness. Function names (`detect_os`, `ensure_uv`, `fetch_repo`, `main`) and the `Harness` methods (`stub`, `source`, `run`, `log_text`) match across all tasks. The interpreter is invoked as `/bin/sh` in both `source` and `run` so PATH controls only the script's lookups.

**Coverage note:** `tests/test_install_sh.py` shells out and imports nothing from `installer`, so it adds tests without touching `installer` coverage — the existing 100% (`fail_under=90`) is preserved. The shell script's own quality is gated by `shellcheck`, not pytest coverage.
