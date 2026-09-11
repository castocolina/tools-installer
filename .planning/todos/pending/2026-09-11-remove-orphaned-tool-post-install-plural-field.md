---
created: 2026-09-11T13:55:00.000Z
title: Remove orphaned Tool.post_install (plural) field and its dead-code companions
area: tech-debt
severity: minor
files:
  - installer/model.py
---

## Problem

`installer/model.py` declares `Tool.post_install: tuple[str, ...]` (plural,
line 268), its closed-set validator `POST_INSTALL_ACTIONS` (line 46,
`("configure_path", "source_shell_init", "set_login_shell",
"enable_corepack", "pnpm_setup", "write_agent_reference")`), and
`SENSITIVE_POST_INSTALL_ACTIONS` (line 54, `("set_login_shell",)`), plus the
parsing/validation block that populates `Tool.post_install` and
`Tool.default_enabled_sensitive_actions` from a registry row (lines 635-652,
689) — but has zero production callers, zero `registry.toml` usage, and zero
test coverage anywhere in the tree.

Confirmed via `grep -rn "\.post_install\b" installer/ tests/` (zero hits
outside `model.py`'s own declaration/parsing code) and
`grep -c "post_install =" installer/registry.toml` (0), during Phase 12.4's
Plan 04 full-catalog audit (`12.4-AUDIT.md`, Pass 3).

This is a violation of `.claude/architecture.md` rule 5 ("No orphan
helpers"), predating Phase 12.4 and unrelated to `Tool.postinstall`
(singular — the closed dispatch-hook-name mechanism Phase 9/12.4 actually
built and extended) despite the near-identical name. The confusingly similar
naming is itself a minor hazard: a future reader skimming `model.py` could
easily conflate the two and either avoid touching the dead one out of
caution, or accidentally extend it instead of the live `postinstall`
mechanism.

Plan 12.2-01 and Phase 12.4's own Plan 04 both deliberately left this
untouched — out of scope for those phases' own decisions — rather than fix
it inline.

## Solution

Delete, as a single self-contained change:

- `installer/model.py`'s `POST_INSTALL_ACTIONS` tuple (line 46).
- `installer/model.py`'s `SENSITIVE_POST_INSTALL_ACTIONS` tuple (line 54).
- `Tool.post_install` field and its `__init__` parameter/`object.__setattr__`
  wiring, and `Tool.default_enabled_sensitive_actions` field and its
  equivalent wiring.
- The `load_tools` parsing/validation block that populates both from a
  registry row (around lines 635-652, 689) — including the
  `undeclared := set(default_enabled_sensitive_actions).difference(post_install)`
  check, which only exists to validate this otherwise-unused pair.

Re-run `make validate && make test` after deletion to confirm no hidden
consumer surfaces (none is expected, per the zero-caller grep evidence
above, but the coverage/lint gate is the actual proof).
