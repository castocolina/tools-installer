---
phase: 18-registry-truth-and-drift-guard
plan: "01"
subsystem: registry
tags: [toml, load_tools, METHOD_PARAMS, verified, pytest]

requires: []
provides:
  - METHOD_PARAMS closed method keys per kind
  - load_tools(manifest_path, *, today=None) with verified date validation
  - Pinned app/tarball {ver} requires version + sha256
  - 90 seeded verified = YYYY-MM-DD keys in installer/registry.toml
  - _write(..., seed_verified=True) test helper
affects: [18-registry-truth-and-drift-guard]

actuals:
  tokens: 22000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Closed METHOD_PARAMS validation before per-kind value checks"
    - "Tool-level verified TOML date without Tool dataclass field"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/registry.toml
    - tests/test_model.py
    - tests/test_registry.py
    - tests/test_skill_lifecycle.py
    - .claude/architecture.md
    - .claude/skills/tool-onboarding/SKILL.md

key-decisions:
  - "Seeded 32 tools from latest # Verified comment date, 58 with 2026-10-13 (L-18-03)"
  - "test_every_shipped_tool_declares_a_verified_date counts ^[[tool]]$ headers only"

patterns-established:
  - "Registry fixtures use _write seed_verified unless testing missing verified"

requirements-completed: [REG-01, REG-02]

coverage:
  - id: D1
    description: "METHOD_PARAMS rejects unknown and cross-kind method keys; shipped registry loads"
    requirement: REG-01
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_unknown_method_key_names_the_tool_and_key"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_shipped_registry_uses_only_allowed_method_keys"
        status: pass
    human_judgment: false
  - id: D2
    description: "Required tool-level verified TOML date on all 90 registry tools"
    requirement: REG-02
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_every_shipped_tool_declares_a_verified_date"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_future_verified_is_rejected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pinned app/tarball urls with {ver} require version and 64-hex sha256"
    requirement: REG-01
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_pinned_url_requires_version_and_sha256"
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 01 Summary

**Registry loader now enforces closed method keys, required `verified` dates on every tool, and pinned app/tarball `{ver}` rules—90 tools seeded without touching `# Verified` comments.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 3 (+ summary commit)
- **Files modified:** 7

## Accomplishments

- Added `METHOD_PARAMS` and unknown-key errors naming tool id and key (D-01).
- Required `verified` TOML dates with `today` injection and one-day future tolerance (D-02, L-18-06); seeded all 90 `[[tool]]` blocks.
- Enforced pinned `app`/`tarball` `version` + `sha256` when url contains `{ver}` (D-03).
- Updated registry authoring docs for the three schema rules.

## Task Commits

1. **Task 1: closed method keys** — `0a8badf` (feat)
2. **Task 2: verified dates + seeding** — `5cdbabb` (feat)
3. **Task 3: pinned rule + docs** — `fd42638` (feat)

## TDD RED Evidence (trimmed)

**Task 1:** New tests failed before `METHOD_PARAMS` (e.g. `test_unknown_method_key_names_the_tool_and_key` — brew `co_install` loaded instead of raising).

**Task 2:**

```
ValueError: tool 'uv': missing required 'verified' (a TOML date, YYYY-MM-DD)
FAILED tests/test_registry.py::test_every_shipped_tool_declares_a_verified_date
```

**Task 3:** Pinned tests failed until per-kind `{ver}` validation was added (`pinned tarball url needs a non-empty 'version'`).

## Verify Commands

- Task 1: `uv run pytest tests/test_model.py tests/test_registry.py -q --no-cov` — pass
- Task 2: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_skill_lifecycle.py tests/test_deps.py -q --no-cov` — pass
- Task 3: `make validate && make test` — pass (3591 passed)
- `git diff --exit-code fbf63b0 -- pyproject.toml uv.lock` — pass (unchanged)
- Registry-only diff: `grep -E '^[-+]' reg.diff | ... grep -vc '^+verified = '` → **0**

## Seeding (Task 2)

- **From `# Verified` comment (latest in block):** 32 tools
- **Default `2026-10-13`:** 58 tools
- **Multi-date tools (max taken):** opencode, cursor-agent, antigravity, codegraph, graphify, rtk, sdkman, jetbrains-toolbox, puppeteer, kitty, wezterm

## Deviations from Plan

1. **`_write` seeding:** Removed erroneous duplicate append when a tool table had no `tier =` line (caused `TOMLDecodeError` in `test_tool_without_methods_raises`).
2. **`test_every_shipped_tool_declares_a_verified_date`:** Count `^[[tool]]$` lines instead of `[[tool]]` substring (avoids counting `[[tool.method]]`).
3. **Fixtures:** Migrated eight `test_model.py` cases from direct `write_text` to `_write`; added `tier`/`shell` where needed; added `tier` to two `load_categories` fixtures.
4. **Docs commit:** Used `git add -f` for tracked `.claude/` paths (directory is gitignored but files are force-tracked).

## Issues Encountered

None blocking. Final review: self-review (no subagent tool in this harness).

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
