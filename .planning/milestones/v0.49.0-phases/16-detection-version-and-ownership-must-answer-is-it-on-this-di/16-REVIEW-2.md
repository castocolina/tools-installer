---
phase: 16
review: 2
status: issues_found
depth: standard
scope: "git diff 569fb63..HEAD -- installer tests (gap plans 16-17, 16-18; HEAD 8a44547)"
lanes:
  - "a: inline fresh read + pure-function probes (rcclean, wizard_app, ownership, skill_lifecycle, model)"
  - "b: opencode-go/glm-5.2 read-only plan agent, chunked (ownership, ui, rc)"
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
prior_findings_reverified_fixed: 14
prior_findings_still_open: 1
---

# Phase 16: Code Review 2 (gap-fix diff)

Fresh independent review of the diff that closes the 16-REVIEW.md findings. Gates on the final tree
(`make validate` exit 0, `make test` 3453 passed / 5 skipped, 95.87% coverage) were run before this
review; the findings below are behavioral, not gate failures.

## New findings

### NR-01 (Low/Medium): post-apply Doctor text is garbled for the `make fix` item (IN-12 residual)

`installer/wizard_app.py:630-631` replaces every `_INERT_ENTER_HINTS` entry with `_RESTART_GUARD`
(`wizard_app.py:184`). For the item whose `next_step` is "Press enter to apply the safe fix below,
then open a new terminal (or `source ~/.myshellrc`)." the result reads:

> The guard is offered again after restarting the installer., then open a new terminal (or `source ~/.myshellrc`).

Double punctuation, a lowercase continuation, and the wrong referent: a `make fix` item is not a guard.
The inert-hint removal itself works, but the replacement is a blind `str.replace` over a prefix.
`tests/test_wizard_app.py:781-782` only assert the hint is absent and `count(_RESTART_GUARD) == 3`, so
they pin the garbled form. Fix: replace the whole sentence per item (or drop the prefix up to the
first `, ` / `.`) and assert the full post-apply string.

### NR-02 (Low): `export PATH=/m/bin:$PATH FOO=1` is now invisible to Doctor (regression vs 569fb63)

`installer/rcclean.py:383` skips any `PATH=` match for which `_has_command_suffix` is true. That is
correct for a one-shot `PATH=x cmd` (IN-02) but also swallows `export PATH=/m/bin:$PATH FOO=1`, a
persistent export of two variables. Baseline 569fb63 reported it (not guardable); HEAD returns nothing,
so a real PATH writer disappears from the Doctor report. Distinguish by whether the line starts with
`export` (an `export` line with extra words is still persistent) before the suffix skip.

### NR-03 (Info): only the first heredoc on a line is tracked

`installer/rcclean.py:442` documents the shortcut (`cat <<A <<B`: the body of B is scanned as code and
can be reported). Recorded as an accepted limit with the upgrade trigger already in the comment; no code
change needed.

### NR-04 (Info/Low maintainability): inert-hint strings duplicated across two modules

`wizard_app.py:185` repeats the literals built in `guidance.py:88` ("Press enter (apply) to guard it in
place", "Press enter to apply the safe fix below"). A wording change in `guidance.py` silently makes the
post-apply replacement a no-op; the three-count test would catch it only for the current wording.
Share one constant.

## Prior findings re-verified

| Finding | Commit | Result |
|---------|--------|--------|
| WR-01 | 79f859a | fixed (`flow="guard"` message at shellrc.py `backup_precondition`) |
| WR-02 | a6cc70e | fixed (`_LEADING_THEN_DO` segments not guardable) |
| IN-01 | 2c92291 | fixed (heredoc-aware scan; first-heredoc limit documented, NR-03) |
| IN-02 | 1316295 | fixed for `PATH=x cmd`; regression NR-02 for `export ... VAR=1` |
| IN-06 | cfd79c2 | fixed (`_is_file` tolerates OSError) |
| IN-10 | 0cc67cc | fixed |
| IN-11 | 2c92291 | fixed (`_code_text`) |
| IN-12 | 41f99a8 | partial: hint removed, text garbled (NR-01) -> stays `open` |
| IN-14 | 1316295 | fixed (`_REFUSE_REPLACE`) |
| IN-15 | ed990dd | fixed |
| IN-16 | 71dd4ae | fixed |
| IN-17 | 8bb1f9d | fixed |
| IN-18 | 8bb1f9d | fixed |
| WR-03 | e2d5dbc | fixed |
| WR-04 | 6ae95a3 | fixed |

Accepted findings (IN-03, IN-04, IN-05, IN-07, IN-08, IN-09, IN-13) remain `skipped`.

## Lane (b) claims rejected after reading the source

- Duplicate-harness validation bricks the whole registry: rejected, the error is raised per tool at parse
  time and the shipped registry has no duplicates (test_registry).
- `install-state` match mismatch for gsd-core: rejected, `INSTALL_STATE_FILES` key and registry id agree.
- Location-proof evidence string built differently in two places: rejected, identical at ownership.py:610
  and :980.
- Empty `gated` could let `_native_owner` attribute "native" wrongly: rejected. `gated` excludes only
  shadow candidates; `_native_owner` still requires verified package evidence plus
  `package_owns_path` for the active path, and the shadow is appended with `shadowed=True`
  (ownership.py:650-656).
- `Method.params` None default, `_installed` KeyError, `.stale` AttributeError, `next_step` None: rejected,
  each field has a non-None default or declared type.

## Not covered

The lane (b) rcclean/shellrc/locations chunk returned empty output twice (opencode, 1700 s timeout); that
area was reviewed by lane (a) only, with pure-function probes against the 569fb63 baseline.
