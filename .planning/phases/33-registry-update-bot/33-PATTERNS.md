# Phase 33: Registry update bot - Pattern Map

**Mapped:** 2026-11-21
**Files analyzed:** 11
**Analogs found:** 10 / 11 (dependabot.yml has none; trivial)

Binding inputs: 33-CONTEXT.md D-01..D-18 and the orchestrator note (provisional decisions 1-10): own `_load`/`_triggers` in the new test, explicit fetch refspec, cron disabled in the committed file, `timeout-minutes >= 60`, no remote write by any agent, proof as a runbook.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `.github/workflows/registry-bot.yml` (new) | workflow | event-driven (dispatch, later cron) + git/gh writes | `.github/workflows/verify-registry.yml` | role-match |
| `.github/workflows/ci.yml` (mod: add bare `workflow_dispatch:`) | workflow/config | event-driven | itself, `on:` block lines 3-7 | exact |
| `.github/dependabot.yml` (new) | config | batch | none | none |
| `installer/verify_registry.py` (mod: `--bumps-only`) | CLI/utility | transform | `--candidate requires --write` guard `:1580-1582`, `_registry_edits_for_write` `:1330-1339` | exact |
| `tests/test_registry_bot_workflow.py` (new) | test | YAML parse | `tests/test_verify_registry_workflow.py` | exact |
| `tests/test_ci_workflow.py` (mod: lines 41 and 52) | test | YAML parse | itself | exact |
| `tests/test_verify_registry.py` (mod: add flag tests) | test | transform | `test_write_dates_only_passing_tools` `:2584`, `test_newer_github_pin_is_bumped_when_the_candidate_passes` `:3027` | exact |
| `scripts/registry-bot-proof.sh` (new runbook) | script | request-response (`gh`), remote writes | `scripts/prune-tmp-linux.sh` (flag grammar, `usage()`, strict mode) | role-match |
| `tests/test_registry_bot_proof_sh.py` (new) | test | subprocess black-box | `tests/test_prune_tmp_linux_sh.py` | role-match |
| docs touch points (README or `.claude/git-workflow.md` mention) | docs | n/a | existing docs; D-18: no `TEST_READ` or `LEDGER` change | n/a |
| `tests/test_verify_registry_workflow.py` (unchanged) | test | n/a | stays as is; do not touch `_load_verify`/`_steps`/`_triggers` | n/a |

All analogs are git-tracked (`git ls-files` confirmed for `ci.yml`, `verify-registry.yml`, `test_ci_workflow.py`, `prune-tmp-linux.sh`; the others are plain tracked tests and the module).

## Pattern Assignments

### `.github/workflows/registry-bot.yml` (workflow)

**Analog:** `.github/workflows/verify-registry.yml` (55 lines)

**Header, triggers, permissions** (lines 5-15). Copy shape; bot differs: triggers `workflow_dispatch` ONLY in the committed file (note 1; D-12), the off-minute cron (e.g. `37 6 * * 1`) is a comment or deferred follow-up; permissions are exactly `contents: write`, `actions: write`, `issues: write`; add `concurrency: {group: registry-bot, cancel-in-progress: false}`.
```yaml
name: verify-registry
on:
  schedule:
    - cron: "17 5 * * 1"
  workflow_dispatch:
permissions:
  contents: read
  issues: write
```

**Job env, checkout, uv** (lines 18-29). Bot: `timeout-minutes: 60` or more (note 9); checkout needs `fetch-depth: 0` only if the guard needs history (not required; it fetches its one ref).
```yaml
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      GH_TOKEN: ${{ github.token }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
```

**Shared state cache, D-09** (lines 30-35 and 50-55). Copy verbatim: restore step without `if`, save step `if: always()`, key with `github.run_id`.
```yaml
      - name: Restore verify-registry state
        uses: actions/cache/restore@v4
        with:
          path: ~/.local/state/tools-installer/verify-registry.json
          key: verify-registry-${{ github.run_id }}
          restore-keys: verify-registry-
      ...
      - name: Save verify-registry state
        if: always()
        uses: actions/cache/save@v4
        with:
          path: ~/.local/state/tools-installer/verify-registry.json
          key: verify-registry-${{ github.run_id }}
```

**Id'd step + `if:` on its outcome, and the inline `gh` upsert style** (lines 36-49): model for the guard step (`id: guard`, output via `$GITHUB_OUTPUT`) and for every publishing step (`if: steps.guard.outputs.changed == 'true'`). The `gh issue list --label ... --json number --jq '.[0].number // empty'` plus `[ -n "$number" ]` branch is the template for the `registry-bot` issue upsert (add `gh label create registry-bot --force`, then `gh issue edit` else `gh issue create`).
```yaml
      - name: Check registry drift
        id: check
        run: make verify-registry ARGS="--issue"
      - name: Close the drift issue after a clean run
        if: steps.check.outcome == 'success'
        run: |
          number=$(gh issue list --label registry-drift --state open --limit 1 --json number --jq '.[0].number // empty')
          if [ -n "$number" ]; then
            gh issue close "$number" --comment "..."
          fi
```

**Bot-specific, no analog in the repo (use RESEARCH and the notes):**
- Run `uv run --isolated --no-dev python -m installer.verify_registry --write --bumps-only` directly; accept exits 0/1/2, fail on 64/70/73 (D-02); never `--issue`.
- Branch name via `env:` (`BRANCH: bot/registry-...` computed in a step and written to `$GITHUB_ENV`/output), never `${{ }}` inside `run` (house rule; `tests/test_ci_workflow.py:84-86`).
- Fetch with the explicit refspec and tolerate absence (note 5): `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" || true`, then `git push --force-with-lease="refs/heads/$BRANCH:<expected-or-empty>" origin "HEAD:refs/heads/$BRANCH"`.
- Dispatch: `gh workflow run ci.yml --ref "$BRANCH"` guarded by the changed output.
- Delete older `bot/registry-*` refs after a successful push (D-05). Never reference `main`, `HEAD:main`, `refs/heads/main`, `gh pr`, merge.

---

### `.github/workflows/ci.yml` (modify)

**Analog:** itself, lines 3-7. Add a bare `workflow_dispatch:` under `on:`; keep the push filter, the concurrency group (lines 9-12), job id, name and steps.
```yaml
on:
  push:
    branches-ignore: [main]
```
Note: `ci.yml` steps reference `actions/checkout@v4`, `astral-sh/setup-uv@v5` (three action repos in total incl. `actions/cache`, per note 3); ci.yml concurrency `ci-${{ github.ref }}` uses an expression outside any `run`, which is fine.

---

### `installer/verify_registry.py` (modify, `--bumps-only`)

**Analog:** same file.

**Argparse add** next to `--write` (lines 1553-1557):
```python
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write verified dates for passing tools (maintainer only).",
    )
```
Add a `--bumps-only` `store_true` the same way.

**Usage guard** (lines 1580-1582): copy for `--bumps-only requires --write`, same `EXIT_USAGE` and stderr print, placed right after it.
```python
    if explicit and not args.write:
        print("--candidate requires --write", file=sys.stderr)
        return EXIT_USAGE
```

**Filter** (lines 1330-1339): add a `bumps_only: bool` keyword (default False so existing callers and tests keep working); keep bump edits; keep `verified` edits only for tool ids with an applied bump; drop lone `verified`.
```python
    for bump in bumps:
        if bump.applied:
            edits.extend(bump.bump_edits)
    for tool_id in report.passed_tools():
        edits.append(RegistryEdit(tool_id, None, "verified", write_day.isoformat()))
```
Call site (line 1597) and the stderr loop (lines 1604-1605, `for tool_id in report.passed_tools(): print(f"dated ...")`) must print only tools actually dated: derive the printed set from `edits` (`edit.key == "verified"`) rather than `report.passed_tools()`. Check `RegistryEdit` fields at `:892` for the exact attribute names before coding. Note the `if edits:` guard means a no-drift registry stays byte-identical.

---

### `tests/test_registry_bot_workflow.py` (new)

**Analog:** `tests/test_verify_registry_workflow.py` (98 lines). Define its OWN `_load(path)` and `_triggers(data)` (note 2); do not import or edit the existing helpers.

**Imports and helpers** (lines 1-23), generalized to take a path:
```python
from pathlib import Path
from typing import Any, cast
import yaml
ROOT = Path(__file__).resolve().parent.parent
def _load(path: Path) -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(path.read_text()))
def _triggers(data: dict[Any, Any]) -> dict[Any, Any]:
    return cast(dict[Any, Any], data.get("on", data.get(True, {})))
```
`on:` parses as boolean `True` under PyYAML; the fallback is mandatory.

**Assertion styles to copy:**
- Triggers equality set and cron checks (lines 26-33): `assert set(triggers) == {"workflow_dispatch"}` for the committed file; if a cron is present, `assert not cron.startswith("0 ")`. Do not assert ordering relative to the 05:17 drift run (note 4).
- Exact permissions dict (line 38): `assert data["permissions"] == {"contents": "write", "actions": "write", "issues": "write"}`.
- Step order and `if` strings (lines 47-73): find indices with `next(i for i, s in enumerate(steps) if ...)`; cache restore before the bot run before the save; `save["if"] == "always()"`; `"if" not in restore`.
- Id'd step then dependent publishing steps (lines 87-98): `assert close["if"] == f"steps.{check['id']}.outcome == 'success'"`; mirror for `steps.guard.outputs.changed == 'true'` on every publishing step; `run.index(a) < run.index(b)` for ordering inside one script.
- Negative text checks on `run` strings (lines 39-44): loop all steps; assert no `main`/`HEAD:main`/`refs/heads/main` push target, no `gh pr`, no `--issue`, no `${{` in any `run`, `--bumps-only` present, `--force-with-lease`, refspec string `+refs/heads/`, `timeout-minutes >= 60` (int).
- `GH_TOKEN` env (lines 76-80).
- Dependabot assertions: `yaml.safe_load` of `.github/dependabot.yml`: `version == 2`, one `github-actions` entry, `directory == "/"`, weekly, group pattern `"*"`.

No network, no `gh`, no shell in these tests (note 10).

---

### `tests/test_ci_workflow.py` (modify)

**Analog:** itself. Two edits (CONTEXT D-10):

Line 41-42, becomes:
```python
    assert set(triggers) == {"push", "workflow_dispatch"}
    assert triggers["push"] == {"branches-ignore": ["main"]}
```
Line 52 (checkout lookup `step.get("uses") == "actions/checkout@v4"`) becomes a prefix match so a Dependabot bump keeps CI green:
```python
    checkout = next(step for step in _steps() if step.get("uses", "").startswith("actions/checkout@"))
```
Also `tests/test_verify_registry_workflow.py:83-84` (`"verify-registry" not in CI_WORKFLOW.read_text()`) must stay true: add no such text to `ci.yml`.

---

### `tests/test_verify_registry.py` (modify, add flag tests)

**Analog:** same file.

**Date-only fixture and driver** (`_two_tool_write_fixture` lines 2542-2581; `test_write_dates_only_passing_tools` lines 2584-2621): copy the probe construction (canned `Release(tag="v1.0.0", digests={})`, `head`, `download`, `Probe(...)`, `today=date(2026, 10, 15)`, `tmp_path / "state.json"`). Add `--bumps-only` run: registry text byte-identical to the input (`registry.read_text() == original`); same fixture without the flag changes. tool_b fails there (exit 1).
```python
    code = vr.main(
        ["--registry", str(registry), "--state", str(state_path), "--write"],
        probe=probe,
        today=today,
    )
```

**Real bump** (`_github_pin_registry` lines 2896-2917; `test_newer_github_pin_is_bumped_when_the_candidate_passes` from line 3027, release `v32.4.1` with digest map and `old_url`/`new_url` head+download): with `--write --bumps-only` the version, url-derived and sha256 keys still change and `verified` is updated for that tool; read the test body (3027-3080) for the exact assertions and reuse them.

**Usage error test:** run `vr.main(["--registry", str(reg), "--state", ..., "--bumps-only"], probe=..., today=...)` and assert `== 64` (`EXIT_USAGE`); check that stderr contains the message with `capsys`. Look at the existing `--candidate requires --write` test (`rg "candidate requires" tests/test_verify_registry.py`) and copy its form.

A no-drift registry is unchanged with or without the flag; for the stderr `dated` loop check `capsys.readouterr().err`.

---

### `scripts/registry-bot-proof.sh` (new runbook, owner-run)

**Analog:** `scripts/prune-tmp-linux.sh` (git-tracked). Copy: header comment block explaining why, `set -euo pipefail` (line 28), `usage()` with `cat <<'EOF'` (lines 35-55), a `while [[ $# -gt 0 ]]; do case "$1" in ... esac done` flag loop (line 57+), `--dry-run` default with an explicit `--apply` (lines 30-31, 60-61).
```bash
set -euo pipefail
APPLY=0
usage() {
  cat <<'EOF'
Usage: prune-tmp-linux.sh [options]
...
EOF
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) APPLY=0; shift ;;
    --apply) APPLY=1; shift ;;
```
Design for the runbook: default dry-run prints the exact `gh` command sequence (D-11 plus the BOT-02 question, remote writes listed, cleanup of proof and bot refs and issue); `--apply` runs it and needs an explicit extra flag for the temporary branch-protection write (Option A). Never run in the phase by an agent (note 1). Heredoc caution for macOS bash 3.2: no apostrophes or unbalanced quotes inside a heredoc inside `$(...)` (note 10). Per AGENTS.md shellcheck gate applies to this file.

### `tests/test_registry_bot_proof_sh.py` (new)

**Analog:** `tests/test_prune_tmp_linux_sh.py`. Copy docstring convention, `ROOT`/`SCRIPT` constants, `pytestmark` skipif bash missing (line 31), and the `_run` helper with a scrubbed env and scratch `HOME` (lines 40-49):
```python
def _run(*args: str, home: Path, cwd: Path | None = None) -> "subprocess.CompletedProcess[str]":
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, cwd=..., capture_output=True, text=True, check=False)
```
Deviation required (note 10): a runner image carries `gh` on PATH, so isolate PATH to a scratch dir holding a stub `gh` that records calls (or none), and assert the dry-run prints the sequence and never invokes `gh` writes. Tests assert no timing, no network.

---

## Shared Patterns

### House rule: no expression inside `run`
**Source:** `tests/test_ci_workflow.py:84-86`
```python
def test_no_run_step_interpolates_an_expression() -> None:
    for step in _steps():
        assert "${{" not in step.get("run", ""), step["name"]
```
**Apply to:** `registry-bot.yml` and its test (pass values through `env:`).

### Workflow tests are plain YAML parses
**Source:** `tests/test_verify_registry_workflow.py:1-23`. **Apply to:** all workflow tests; Python 3.12 and 3.15 safe (stdlib `pathlib`, `typing`, `yaml`).

### Cron never at minute 0
**Source:** `tests/test_verify_registry_workflow.py:32-33`. **Apply to:** the bot cron if committed or stubbed.

### Exit-code contract
**Source:** `installer/verify_registry.py` `EXIT_USAGE` (64), `EXIT_WRITE_REFUSED` (73), check `_EXIT_EPILOG`; bot step accepts 0/1/2 only.

### Tools and gates
AGENTS.md: ruff, pyright, bandit, vulture, shellcheck at the commit hook; run only `uv run pytest <touched test files> --no-cov -q` while working; no new Python module is expected (reachability guard not at stake).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/dependabot.yml` | config | batch | No dependabot config exists; use RESEARCH/D-17 (`version: 2`, `github-actions`, `directory: "/"`, weekly, group `"*"`) |
| bot-only steps (git fetch/lease push, ref deletion, `gh workflow run`) | workflow | git/gh writes | No existing workflow writes to the repo; use RESEARCH and note 5 |
| `actionlint` run | verification | n/a | Orchestrator-run at the phase gate (note 6), not a file |

## Metadata

**Analog search scope:** `.github/`, `scripts/`, `tests/test_*workflow*.py`, `tests/test_verify_registry.py`, `installer/verify_registry.py`
**Files read:** verify-registry.yml, ci.yml, test_verify_registry_workflow.py, test_ci_workflow.py (partial), verify_registry.py (targeted ranges), test_verify_registry.py (targeted ranges), prune-tmp-linux.sh and its test (heads)
**Pattern extraction date:** 2026-11-21
