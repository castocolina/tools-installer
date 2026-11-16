# Phase 26: Commit and push quality hooks - Pattern Map

**Mapped:** 2026-11-16
**Files analyzed:** 30 (new and modified, grouped where the pattern is the same)
**Analogs found:** 17 / 30 (the rest are doc edits or have no analog; see below)

Scope note: I read RESEARCH.md lines 1-471 only (the rest is Validation Architecture and Contradictions, not re-read here). All analog paths below are git-tracked source.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `devtools/__init__.py` | package marker | n/a | `installer/__init__.py` | exact |
| `devtools/push_gate.py` | utility (git hook) | request-response + subprocess, signals | `installer/run.py` (Runner seam, `run_git_isolated`) | role-match |
| `devtools/hooks.py` | utility (installer) | file-I/O + subprocess | `installer/run.py` (injected runner) + `scripts/lib/prune-tmp-common.sh` (idempotent marker) | partial |
| `devtools/docs_only.py` | utility | transform (path list to bool) | `installer/run.py::run_git_isolated` (git argv) | partial |
| `scripts/hooks-e2e.sh` | script | batch, real git | `scripts/container-e2e-verify.sh` | role-match |
| `tests/test_push_gate.py` | test | fake runner + Python child | `tests/test_runlock.py` (`sys.executable` child), `tests/sandbox.py` | role-match |
| `tests/test_hooks_install.py` | test | fake runner, tmp_path | `tests/test_shell_scripts_path.py`, `tests/test_tweaks.py` | role-match |
| `tests/test_docs_only.py` | test | matrix | any pure-function test (e.g. `tests/test_makefile.py`) | partial |
| `tests/test_hook_wiring.py` | test | text parse | `tests/test_makefile.py::_recipes` + `tests/test_ci_workflow.py::_load_ci` | exact |
| `Makefile` | config | n/a | itself (current targets) | exact |
| `.pre-commit-config.yaml` | config | n/a | itself | exact |
| `pyproject.toml`, `.github/workflows/ci.yml` | config | n/a | themselves | exact |
| `tests/test_makefile.py`, `tests/test_ci_workflow.py` | test (modify) | text parse | themselves | exact |
| `tests/test_screen_family.py` (D-12) | test (modify) | async wait | `tests/screen_family.py::wait_until/settle` + `_wait_for_passes` (same file, line 2703) | exact |
| rename sweep (product messages, tests, README, AGENTS.md, `.claude/*.md`, SKILL.md, `docs/PUBLISHING.md`) | mixed | text replace | RESEARCH "Rename sweep" table lists every line | exact |
| `.planning/todos/pending/<new>.md` | todo | doc | `.planning/todos/pending/2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test.md` | exact |

## Pattern Assignments

### `devtools/push_gate.py` and `devtools/hooks.py` (runner injection)

**Analog:** `installer/run.py`

Runner seam (lines 18-21): a callable type is injected, tests pass a fake.
```python
Runner = Callable[[list[str]], None]
OutputRunner = Callable[[list[str]], str]
```
Git isolation (lines 162-172): copy this env scrub for every git call the gate makes (hooks export `GIT_DIR`, `GIT_INDEX_FILE`, etc.).
```python
env = {key: value for key, value in os.environ.items() if key not in _GIT_INHERITED}
env.update(GIT_TERMINAL_PROMPT="0", SSH_ASKPASS_REQUIRE="never")
return run_output([argv[0], *_GIT_ISOLATION, *argv[1:]], timeout=600, env=env)
```
Caveat: `devtools` must stay stdlib-only and must NOT import `installer` (D-02, and `docs_only` runs on the CI system `python3` before `uv`). Define a local `Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]` in `devtools` rather than importing. Do not reuse `_GIT_INHERITED`; redefine the tuple locally. Signal-forwarding core: RESEARCH "Prototype signal-forwarding core" (lines 341-364); add `signal.pthread_sigmask` around `Popen(process_group=0)`. Resolve programs by `shutil.which` or `sys.executable -m pre_commit` (bandit B607).

### `scripts/hooks-e2e.sh` (script, batch)

**Analog:** `scripts/container-e2e-verify.sh` (lines 1-18): header comment block, then
```bash
#!/usr/bin/env bash
# name.sh — one-line purpose, then how it is invoked (make target).
set -euo pipefail
```
Constants named in caps at the top, `mktemp -d` plus `trap 'rm -rf "$scratch"' EXIT` for cleanup. Start git/pre-commit from `env -i` with an explicit allowlist (RESEARCH Pitfall 2). Add the file to the `make shellcheck` list and the hook entry (same list in both comes from the Makefile only, D-03). Never run it on the host from tests; it is a make target `hooks-e2e` plus CI.

### `tests/test_push_gate.py` (fake runner and Python child)

**Analog:** `tests/test_runlock.py:54-57` (child via `sys.executable`, allowed by sandbox allowlist):
```python
child = subprocess.Popen([sys.executable, "-c", "pass"], cwd=tmp_path)
child.wait()
```
Plant fake `git` / `pre-commit` scripts under `tmp_path`, put that dir first on the child PATH, run `[sys.executable, "-m", "devtools.push_gate"]` (RESEARCH Pitfall 1). Real `git`/`make`/`uv`/`pre-commit` from pytest are refused by `tests/sandbox.py`; do not widen its allowlist. Other `sys.executable` users: `tests/test_tweaks.py`, `tests/test_shell_scripts_path.py`.

### `tests/test_hook_wiring.py`, `tests/test_makefile.py`, `tests/test_ci_workflow.py` (text-parse pins)

**Analog:** `tests/test_makefile.py` lines 1-60. Reuse `_recipes()` (target -> (prereqs, recipe lines)); importing it from `tests.test_makefile` or copying it both work. Constraints: target regex `^([a-zA-Z0-9_-]+)\s*:(.*)$`, `.PHONY` on a single line, every public target needs a `## ` help comment.
```python
ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"
match = re.match(r"^([a-zA-Z0-9_-]+)\s*:(.*)$", line)
```
YAML load pattern from `tests/test_ci_workflow.py:19-27` (bare `on:` parses to `True`):
```python
def _load_ci() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(CI_WORKFLOW.read_text()))
def _steps(): return _load_ci()["jobs"]["validate-and-test"]["steps"]
triggers = data.get("on", data.get(True, {}))
```
Edits required in existing tests:
- `test_makefile.py`: `test_launch_targets_run_without_the_dev_venv` loops `("setup","doctor","fix","uninstall")` -> use `("run", ...)`; `test_run_is_an_alias_of_setup` (`prereqs == ["setup"]`, `recipe == []`) -> replace with a test that `run` itself holds the launcher recipe; `test_every_setup_py_recipe_uses_the_launch_form` asserts `launcher_targets == ["setup","doctor","fix","uninstall"]` -> `["run","doctor","fix","uninstall"]` (file order).
- `test_ci_workflow.py`: `test_ci_triggers_on_push_and_pull_request` -> push-only, `branches-ignore` contains `main`, no `pull_request`; update module docstring; keep other pins; `make dev-setup` replaces `make install`.

### `.pre-commit-config.yaml` (modify)

**Analog:** itself. Current entries use `uv run ruff check`, `types: [python]`, `files:` regexes. Replace each with the RESEARCH "Hooks config shape" (lines 366-388): `entry: make <target>`, `language: system`, `pass_filenames: false`, `always_run: true`, `stages: [pre-commit, pre-push]`; add `default_install_hook_types: [pre-commit]`; `make test` hook last, `stages: [pre-push]`. Keep ids (`ruff-check`, `ruff-format`, `pyright`, `bandit`, `vulture`, `shellcheck`). Move the bandit skip list `B404,B603,B310` and shellcheck file list into the Makefile recipes.

### `tests/test_screen_family.py` (D-12 flake fix)

**Analog:** same file. The failing test (lines 2776-2791) calls `settle` then `_wait_for_passes`, then reads the body at once. Helpers (`tests/screen_family.py:14-27`):
```python
async def wait_until(pilot, predicate, tries=400): ...   # polls predicate, pilot.pause() between
async def settle(app, pilot):  # waits for no PENDING/RUNNING worker, then pause once
```
and `_wait_for_passes` (line 2703-2706). Fix pattern: wait with `wait_until(pilot, lambda: _INVALIDATE_FAILED.format(error=shown) in str(_doctor_text(app)))` (or on the worker completion) before asserting, never a fixed pause. Prove with 50 runs under `-n auto` before and after (the existing sibling test at 2797 uses the same tail and may need the same fix).

### `.planning/todos/pending/<new>.md` (D-14)

**Analog:** `.planning/todos/pending/2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test.md`: front matter then `## Problem` and `## Solution`:
```
---
created: 2026-11-16T..Z
title: ...
area: tooling
severity: minor
files:
  - ...
---
```
Completed todos go to `.planning/todos/completed/` (move the flaky todo there when D-12 is done).

## Shared Patterns

### Makefile target shape
**Source:** RESEARCH "Makefile shape" (lines 390-416), built on the current `Makefile`. One-line `.PHONY`; `## help` comment per public target; no `UV := uv` (parsed as a target); target names letters, hyphen only for `make help`. Add `devtools` to ruff paths, bandit `-r`, pyright `include`, coverage `source`, vulture `paths` in `pyproject.toml`.

### Rename sweep (`make setup` -> `make run`, `make install` -> `make dev-setup`)
**Source:** RESEARCH "Rename sweep" table (lines 273-294). Extra files beyond D-08: `tests/test_render.py:370`, `.claude/dev-environment.md:30,32`, `.claude/skills/catalog-audit/SKILL.md:189` (pinned by `tests/test_catalog_audit_skill.py:140`). Use `rg --hidden` to catch `.claude/` and `.github/`. Leave `docs/superpowers/` and `.planning/` history alone.

### Sandbox-safe testing
**Source:** `tests/sandbox.py`, `tests/conftest.py`. Inject runners; tests never launch real git/make/uv/pre-commit; real-tool proof goes in `scripts/hooks-e2e.sh`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `devtools/push_gate.py` signal handling | utility | signals | no signal-forwarding code in `installer/`; use RESEARCH prototype |
| `devtools/hooks.py` pre-push shim writer | utility | file-I/O | no git-hook writer exists; use RESEARCH shim text (lines 329-339) with marker line |
| `devtools/docs_only.py` | utility | transform | no CI helper module exists; RESEARCH lines 419-428 |
| `.github/workflows/ci.yml` docs-only steps | config | n/a | modify existing; follow RESEARCH ci.yml design (lines 430-462) |

## Metadata

**Analog search scope:** `installer/run.py`, `scripts/`, `tests/` (makefile, ci_workflow, runlock, screen_family, screen_family helpers), `.pre-commit-config.yaml`, `.planning/todos/`
**Files scanned:** about 12 read, about 8 grepped
**Pattern extraction date:** 2026-11-16
