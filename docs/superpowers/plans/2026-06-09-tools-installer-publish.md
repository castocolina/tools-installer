# tools-installer Publish & CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `curl … | sh` one-liner real by adding GitHub Actions CI and documenting the one-time publish, so pushing the public repo is all it takes to go live.

**Architecture:** No build artifact and no release pipeline — `install.sh` clones `main`, so the canonical "stable URL" is `raw.githubusercontent.com/castocolina/tools-installer/main/install.sh`, which resolves the moment the public repo is pushed. This plan delivers the repo-side enablement: a CI workflow that runs `make validate && make test` on push/PR (Ubuntu + macOS, via `astral-sh/setup-uv`), a pytest that asserts the workflow stays wired to those gates, and a publishing doc with the exact one-time commands. Versioned releases and PyPI are explicitly out of scope (deferred).

**Tech Stack:** GitHub Actions, `astral-sh/setup-uv`, `uv`, `pytest`, `PyYAML` (test-only).

---

## Scope

In scope: `.github/workflows/ci.yml`, a workflow-validation test, the `PyYAML`/`types-PyYAML` test deps, and `docs/PUBLISHING.md` + README touch-ups (status note, CI badge).

**Out of scope / deferred** (do NOT implement): tagged GitHub Releases, attaching `install.sh`/wheels as release assets, PyPI publishing, version bumping, CHANGELOG. The user explicitly wants the lean "push to publish" model — `install.sh` always clones `main`.

**Manual, owner-only steps (NOT part of this plan's code):** creating the GitHub repo, making it public, and pushing require the owner's `gh` auth and account. Task 2 documents the exact commands; running them happens after the plan, by the owner.

## File Structure

- Create: `.github/workflows/ci.yml` — CI: run the quality gates on push + PR across Ubuntu and macOS.
- Create: `tests/test_ci_workflow.py` — parse `ci.yml` and assert it still triggers correctly and runs the gates.
- Modify: `pyproject.toml` / `uv.lock` — add `pyyaml` + `types-PyYAML` as dev deps (via `uv add --dev`).
- Create: `docs/PUBLISHING.md` — the one-time go-live procedure and the no-ceremony ongoing model.
- Modify: `README.md` — add a CI badge and correct the "Status" note to point at the publishing doc.

---

## Task 1: CI workflow + workflow-validation test

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `tests/test_ci_workflow.py`
- Modify: `pyproject.toml`, `uv.lock`

- [ ] **Step 1: Add the test-only YAML deps**

Run:
```bash
uv add --dev pyyaml types-PyYAML
uv run python -c "import yaml; print(yaml.__name__)"
```
Expected: `uv` updates `pyproject.toml`/`uv.lock`; the command prints `yaml`.

- [ ] **Step 2: Write the failing workflow test**

Create `tests/test_ci_workflow.py` with EXACTLY this content:

```python
"""Validate the CI workflow stays wired to the real quality gates.

GitHub Actions can't be run locally, so this test parses .github/workflows/ci.yml
and asserts the invariants we care about: it triggers on push + pull_request, runs
`make validate` and `make test`, sets up uv via the official action, and exercises
both Linux and macOS. It catches a malformed or gutted workflow before it is
pushed (where the only other feedback is a failed Actions run after the fact).
"""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(CI_WORKFLOW.read_text()))


def _steps() -> list[dict[Any, Any]]:
    return _load_ci()["jobs"]["validate-and-test"]["steps"]


def test_ci_triggers_on_push_and_pull_request() -> None:
    # PyYAML parses the bare `on:` key as the boolean True (YAML 1.1), not "on".
    data = _load_ci()
    triggers = data.get("on", data.get(True))
    assert "push" in triggers
    assert "pull_request" in triggers


def test_ci_runs_validate_and_test() -> None:
    run_cmds = [step.get("run", "") for step in _steps()]
    assert any("make validate" in cmd for cmd in run_cmds)
    assert any("make test" in cmd for cmd in run_cmds)


def test_ci_sets_up_uv_with_official_action() -> None:
    uses = [step.get("uses", "") for step in _steps()]
    assert any("astral-sh/setup-uv" in ref for ref in uses)


def test_ci_matrix_covers_linux_and_macos() -> None:
    matrix = _load_ci()["jobs"]["validate-and-test"]["strategy"]["matrix"]["os"]
    assert "ubuntu-latest" in matrix
    assert "macos-latest" in matrix
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_ci_workflow.py -v`
Expected: FAIL — `.github/workflows/ci.yml` does not exist, so `yaml.safe_load` returns `None` and the indexing/`in` checks raise.

- [ ] **Step 4: Create the CI workflow**

Create `.github/workflows/ci.yml` with EXACTLY this content:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  validate-and-test:
    name: validate & test on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Install dependencies
        run: make install
      - name: Validate
        run: make validate
      - name: Test
        run: make test
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_ci_workflow.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Verify the full gate**

Run: `make validate && make test`
Expected: ruff/pyright/bandit/vulture/shellcheck pass; pytest passes; `installer` coverage still 100% (the new test imports nothing from `installer`, so coverage is unaffected).

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml tests/test_ci_workflow.py pyproject.toml uv.lock
git commit -m "ci: run validate and test on push/PR across Ubuntu and macOS

Set up uv via astral-sh/setup-uv and run the same make gates as local dev. A
pytest parses the workflow to assert it keeps triggering on push/PR and running
make validate + make test, since Actions can't be exercised locally.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Publishing doc + README status and badge

**Files:**
- Create: `docs/PUBLISHING.md`
- Modify: `README.md`

- [ ] **Step 1: Create the publishing doc**

Create `docs/PUBLISHING.md` with EXACTLY this content:

```markdown
# Publishing

`tools-installer` is consumed straight from GitHub: the bootstrap (`install.sh`)
is fetched over HTTPS and run. There is no package to build or upload — "releasing"
means pushing to the public repo so the raw URL resolves.

## One-time: put the repo on GitHub

```sh
gh auth login                       # authenticate once
gh repo create castocolina/tools-installer --public --source=. --remote=origin --push
```

The repo must be **public** so that:

- `https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh`
  is fetchable without authentication, and
- GitHub Actions CI (including the macOS runner) runs for free.

## Verify the one-liner

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
```

## Ongoing: there is no release ceremony

`install.sh` clones `main`, so every `git push` to `main` is "published"
immediately — the raw URL always serves the latest script, and the script always
clones the latest `main`. CI (`.github/workflows/ci.yml`) runs `make validate`
and `make test` on every push and pull request.

To pin to a specific branch, tag, or commit, callers set `TI_REF`:

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | TI_REF=v1.0.0 sh
```
```

- [ ] **Step 2: Add the CI badge under the README title**

In `README.md`, the file opens with:

```markdown
# tools-installer

One command to provision a fresh **macOS or Linux** machine with a full AI dev
```

Insert the badge line so it becomes:

```markdown
# tools-installer

[![CI](https://github.com/castocolina/tools-installer/actions/workflows/ci.yml/badge.svg)](https://github.com/castocolina/tools-installer/actions/workflows/ci.yml)

One command to provision a fresh **macOS or Linux** machine with a full AI dev
```

- [ ] **Step 3: Correct the "Status" note to point at the publishing doc**

In `README.md`, replace this blockquote:

```markdown
> **Status: in development (v1 / MVP).** The design is locked in
> [`docs/prds/ai-dev-tools-installer-v1.0-prd.md`](docs/prds/ai-dev-tools-installer-v1.0-prd.md);
> the implementation is being built. The command above is the target interface,
> not a working endpoint yet.
```

with:

```markdown
> **Status: in development (v1 / MVP).** The design is locked in
> [`docs/prds/ai-dev-tools-installer-v1.0-prd.md`](docs/prds/ai-dev-tools-installer-v1.0-prd.md);
> the implementation is being built. The install URL resolves once the repo is
> published — see [Publishing](docs/PUBLISHING.md).
```

- [ ] **Step 4: Verify the gate (docs-only, but keep the discipline)**

Run: `make validate && make test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add docs/PUBLISHING.md README.md
git commit -m "docs: document publishing and add the CI badge

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:** The user's intent — "push to my castocolina account and the curl one-liner just works, the wrapper does the rest" — is covered: `install.sh` already clones `main`, Task 2 documents the exact public-push that makes the raw URL live, and Task 1 adds the `setup-uv` CI gate the user chose. Versioned releases / PyPI are deferred per the explicit scope answer.

**2. Placeholder scan:** No `TBD`/`TODO`/"handle edge cases". Every code/file step shows full content. The only intentionally-unrun commands are the owner-only `gh` publish steps in `docs/PUBLISHING.md`, which are clearly labelled as manual.

**3. Type/name consistency:** The CI job is named `validate-and-test` in both `ci.yml` and every accessor in `tests/test_ci_workflow.py`. The test handles the PyYAML `on` → `True` boolean-key gotcha. The badge/status URLs and the raw install URL all use `castocolina/tools-installer` and `main` consistently with `install.sh`'s defaults.

**Coverage note:** `tests/test_ci_workflow.py` imports nothing from `installer`, so it adds tests without affecting the package's 100% coverage. CI itself re-runs `make test`, so the workflow validates its own file on every push.

**Reviewer guidance:** `cast(dict[Any, Any], …)` is required for pyright-strict cleanliness against PyYAML's `Any`-typed `safe_load` and the boolean `on` key — it is not a gate bypass (no `# type: ignore`). `astral-sh/setup-uv@v5` may be bumped to a newer major if available; the test asserts only the `astral-sh/setup-uv` substring, so a version bump won't break it.
