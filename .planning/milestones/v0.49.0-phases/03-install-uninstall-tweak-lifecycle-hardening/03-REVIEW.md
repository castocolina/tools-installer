---
phase: 03-install-uninstall-tweak-lifecycle-hardening
reviewed: 2026-09-05T00:00:00Z
iteration: 3
final_iteration: true
depth: deep
verdict: has-blocker
files_reviewed: 16
files_reviewed_list:
  - installer/omz.py
  - installer/policy.py
  - installer/uninstall.py
  - installer/app.py
  - installer/locations.py
  - installer/wizard_app.py
  - installer/ui_common.py
  - installer/tool_browser.py
  - installer/shellrc.py
  - installer/guards.py
  - installer/tweaks.py
  - setup.py
  - .claude/architecture.md
  - tests/test_setup.py
  - tests/test_wizard_app.py
  - tests/test_app.py
findings:
  critical: 2
  warning: 3
  info: 6
  total: 11
status: issues_found
gates:
  make_validate: exit 0
  make_test: 850 passed, 99.83% coverage
---

# Phase 3: Code Review Report — iteration 3 (FINAL, cap reached)

**Reviewed:** 2026-09-05
**Depth:** deep (`git diff 2c1310c..HEAD -- installer/ tests/ setup.py .claude/architecture.md`, with cross-file tracing and runtime probing of `installer/omz.py`, `installer/app.py`, and the live `UnifiedApp`)
**Files Reviewed:** 16
**Scope note:** the four fix commits under scrutiny are `72bf192` (BLOCKER), `fc58315` (WR-02/WR-03), `7a6c33b` (WR-05), `3c74058` (WR-06)

## VERDICT: has-blocker

Two Critical findings, both **newly discovered this iteration** and both in
`installer/omz.py`. Neither was introduced by the four fix commits in the sense
of "the fix broke it" — CR-01 is a hole the BLOCKER fix left open in the same
function it rewrote, and CR-02 rides on the `_atomic_write` helper that fix
commit created. Both are reproduced against the real modules, and both are
invisible to the current gate: `make validate` exits 0 and `make test` is
**850 passed, 99.83% coverage** with `installer/omz.py` at **100% line and
branch**.

## Gates — independently re-run on this exact tree

```
uv run ruff check installer tests setup.py     All checks passed!
uv run ruff format --check installer tests setup.py   87 files already formatted
uv run pyright                                 0 errors, 0 warnings, 0 informations
uv run bandit -q -r installer --skip B404,B603,B310   (clean)
uv run vulture                                 (clean)
uv run shellcheck install.sh                   (clean)
make validate  -> exit 0

850 passed in 65.55s
TOTAL 2780 stmts, 3 miss, 810 branch, 3 partial, 99% — total coverage 99.83%
make test      -> exit 0
```

(Iteration 2 measured 839 passed / 99.83%; this tree adds 11 tests.)

## Answers to the six questions asked

| # | Question | Answer |
|---|---|---|
| 1 | New issue introduced by the 4 fix commits? | **Yes, indirectly** — CR-02 is a property of the `_atomic_write` helper `72bf192` created (it replaces symlinked dotfiles). CR-01 is a hole `72bf192` left in the function it rewrote. No *regression* in previously-working behaviour was found. |
| 2 | WR-02/WR-03 completeness — was a screen missed? | **Yes: `PoliciesScreen`.** `ban_names`, `has_path_block`, `tweak_ids` and `DoctorScreen.guard_state` are all correct now, but `PoliciesScreen.active_state` is still a build-time snapshot with no `enter_view`, and the Uninstall view's teardown mutates exactly that state. Reproduced headlessly. See **WR-01**. |
| 3 | WR-05 — divergence impossible by construction? | **On `run_uninstall`, yes.** On `perform_uninstall` (the TUI entry point), **no** — it still calls `sweep_tweaks` *after* its own `remove_paths`/`remove_shims`/`remove_ban_aliases`/`remove_managed_block`. Reproduced: the view previews `('tweak:countdown',)` and the sweep returns `()`. See **WR-02**. |
| 4 | WR-06 — do the new tests catch real regressions? | **Three of four claimed mutations, yes; one, no.** Verified by actually applying each mutation. Deleting `remove=_do_uninstall` → 4 failures. `bundles=applicable_bundles(platform)` → 1 failure. Freezing `ban_names` → 1 failure. **Freezing `tweak_ids` at build time → all 850 tests pass.** See **WR-03**. |
| 5 | `cast()` in two test files | **In-convention, keep.** Both are narrowing an `object`/unbounded-`_T` the type system genuinely cannot narrow, which is the same reason `installer/model.py:58` and `installer/executors.py:38` use it. One latent sharp edge noted as **IN-05**. |
| 6 | The 5 deferred Info findings | Only iteration-1 **IN-01** is user-visible enough to matter, and CR-01 below is a strictly worse variant of the same wording defect, so fixing CR-01 should fix IN-01's phrasing too. IN-02..IN-05 are safe to carry forward. See **IN-06**. |

## What still holds from iteration 2

The BLOCKER fix's core ordering change is correct and I found no way to break
it beyond CR-01. I re-verified the adjacent path the orchestrator asked about —
a failure during `write_plugins`' **enable** arm — and it behaves exactly as the
docstring claims:

```
A: enable-path .zshrc write fails
   raised: [Errno 30] read-only
   zshrc: 'plugins=(z)\n'   owned: ()   plugins_owned: False     <- correct

B: enable over an EXISTING record, .zshrc write fails
   prior owned: ('git',)
   raised: [Errno 30] read-only
   owned after failed enable: ('git',)                            <- rolled back exactly

D: remove-path, the record write fails AFTER the .zshrc edit landed
   raised: [Errno 30] read-only
   zshrc: 'plugins=(z)\n'   owned: ('git', 'docker')
   retry: ()               owned after retry: ()                  <- self-heals
```

`sweep_policies`/`active_policies`/`sweep_tweaks` is a clean factoring;
`guard_state` is a good extraction; `ToolBrowser.reload` correctly prunes marks
on rows that no longer exist, so no stale selection can be committed; the
rewritten `tests/test_setup.py` is a genuine improvement over source-text
substring matching.

---

## Critical Issues

### CR-01: `remove_plugins` still destroys the ownership record when the `.zshrc` edit did not happen — and reports success

**File:** `installer/omz.py:355-362` (the `_clear_owned` at 361 runs unconditionally), `installer/policy.py:235-246`, `installer/app.py:387-389`

**Issue:** `72bf192` moved `_clear_owned` after the write, but guarded it on
nothing:

```python
original = zshrc_path.read_text()
current = plugins_in(original)
removed = tuple(name for name in owned if name in current)
updated = disable_plugins(original, owned)
if updated != original:
    _atomic_write(zshrc_path, updated)
_clear_owned(state_path)          # <- runs even when updated == original
```

`disable_plugins` is *total by design*: when `_locate` refuses the array — the
multi-line form, or a multi-line array shadowing a single-line one — it returns
the content **unchanged**. So `updated == original`, no write happens, and the
record is cleared anyway. The code cannot distinguish "nothing to remove because
the user already deleted the names" (correct to clear) from "nothing removed
because I could not parse the array" (must **not** clear).

This is the exact defect class BL-01 existed to close, through a different door,
and it is *worse* in one respect: BL-01 at least reported failure. This reports
success.

Reproduced against the real modules — a user who enables the policy and later
restructures their array into the multi-line form, which is Oh-My-Zsh's own
documented idiom once you have more than a few plugins:

```
added: ('git', 'docker')
zshrc after enable: 'plugins=(z git docker)'
owned: ('git', 'docker')  plugins_owned: True

--- user converts the array to the multi-line form ---
remove_plugins returned: ()
owned AFTER: ()   plugins_owned: False
zshrc AFTER: 'plugins=(\n  z\n  git\n  docker\n)\nsource $ZSH/oh-my-zsh.sh\n'
```

End-to-end through the real `run_uninstall`, the user is told the opposite of
what happened, twice:

```
These shell tweaks will also be disabled (omz-plugins).
  omz-plugins removes git, docker from the plugins=(...) array in .../.zshrc.
Shell tweaks disabled: omz-plugins.

zshrc: 'plugins=(\n  z\n  git\n  docker\n)\n...'   (byte-identical)
owned: ()
```

Four consequences, matching BL-01's list almost line for line:

1. **The report is a lie.** The preview names `git, docker` and the file; the
   result line says they were disabled; nothing left the file.
2. **The names are unrecoverable through the tool.** The record is gone, so
   `plugins_owned` is False, the Policies row reads OFF, and re-enabling
   computes `added=()` against an array that already contains both — pinned by
   `test_enabling_over_an_array_that_already_has_everything_owns_nothing`. Hand
   editing is the only way out.
3. **The TUI message is actively false.** `policy.py:241` prints
   `"nothing to remove — this installer added no plugins to ~/.zshrc"` when the
   installer demonstrably did add them.
4. `omz.py:332-348`'s own stated discipline — *"the record is therefore cleared
   LAST, and only once the file it describes has actually changed"* — is not
   what the code does.

Coverage cannot see this: `omz.py` is at 100% line **and branch**. Both branches
of `if updated != original:` are exercised; what is untested is the *combination*
of a refused array with a live record.

**Fix:** stop routing the disable through the total `disable_plugins` and use
the refusal-aware `_rewrite` directly, so an unparseable array is a failure, not
a silent success. `OmzPluginsError` subclasses `OSError`, so `sweep_policies`
already catches it and reports the policy as `failed`.

```python
def remove_plugins(zshrc_path: Path, state_path: Path) -> tuple[str, ...]:
    owned = owned_plugins(state_path)
    if not owned or not zshrc_path.exists():
        _clear_owned(state_path)
        return ()
    original = zshrc_path.read_text()
    updated = _rewrite(original, owned, enable=False)
    if updated is None:
        # The array zsh honours is one this module cannot edit, so the names it
        # added are still on disk. Keep the record: it is the only thing that can
        # take them back out once the array is editable again.
        raise OmzPluginsError(_refusal(original))
    removed = tuple(name for name in owned if name in plugins_in(original))
    if updated != original:
        _atomic_write(zshrc_path, updated)
    _clear_owned(state_path)
    return removed
```

Two knock-on edits are required, not optional:

- `remove_plugins`' docstring currently *promises* the buggy behaviour
  (*"an array this module cannot parse … resolve to 'nothing removed' rather
  than raising"*). That sentence is the design decision that produces the bug and
  must change with the code.
- `app.py:392`'s remediation string (`"Check permissions and re-run"`) is wrong
  for this cause. Either widen it or have `sweep_policies` carry the reason.

Regression test, mirroring `test_a_failed_rewrite_leaves_the_original_intact`:
enable against a single-line array, rewrite `.zshrc` to the multi-line form,
call `remove_plugins`, and assert it raises and that
`owned_plugins(state) == ("git", "docker")` still holds.

### CR-02: `_atomic_write` replaces a symlinked `~/.zshrc` with a regular file, silently detaching the user's dotfiles repo

**File:** `installer/omz.py:190-214` (`os.replace(tmp, path)` at 209), reached from `write_plugins` (320) and `remove_plugins` (360)

**Issue:** `os.replace(tmp, path)` renames **over the symlink itself**, not
through it. A `~/.zshrc` that is a symlink into a dotfiles repo — chezmoi, GNU
stow, yadm, dotbot, or a hand-rolled `ln -s` — is replaced by a plain file whose
content is the rewritten text. The repo copy keeps the *pre-edit* content and is
no longer connected to the shell.

Reproduced:

```
before: is_symlink: True
after : is_symlink: False
~/.zshrc content   : 'plugins=(z git docker)\n'
dotfiles repo file : 'plugins=(z)\n'
```

Consequences: the user's version control silently stops tracking their real
`.zshrc`; a later `stow`/`chezmoi apply` either errors on the now-untracked
regular file or clobbers the installer's edit; and every subsequent edit in
either place diverges without warning. The same applies to `~/.myshellrc`
through `_record_owned`/`_clear_owned`.

This is **inconsistent with every other writer in the codebase**, which is what
makes it a defect rather than a design choice. `shellrc.py:112/126/136/149`,
`guards.py:102/112` and `tweaks.py:203/214` all use `path.write_text(...)`,
which writes *through* a symlink and preserves it. `omz.py` is the only module
that replaces the inode — and it does so on the one file
`.claude/architecture.md:104-107` designates as belonging entirely to the user,
in a module whose own header (lines 5-7) promises *"exactly one line is
rewritten and every other byte is copied through."* Replacing the file's
identity is not copying bytes through.

**Fix:** resolve the link before choosing the temp sibling and the rename
target, which keeps both the crash-safety `72bf192` wanted and the symlink:

```python
def _atomic_write(path: Path, updated: str) -> None:
    # os.replace renames over the symlink itself, so a ~/.zshrc managed by a
    # dotfiles repo would become a plain file and silently detach from it.
    # Resolve first: the temp sibling then lands in the repo directory, so the
    # rename still cannot cross a filesystem.
    target = path.resolve() if path.is_symlink() else path
    tmp = target.with_name(f"{target.name}.tools-installer.tmp")
    try:
        tmp.write_text(updated)
        if target.exists():
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
```

Regression test: symlink `tmp_path/".zshrc"` at `tmp_path/"dotfiles"/"zshrc"`,
run `write_plugins`, assert `zshrc.is_symlink()` is still True and that the repo
file carries the edit. Add the mirror for `remove_plugins`.

*(Note: `path.resolve()` on a broken symlink returns the non-existent target and
`tmp.write_text` then raises `FileNotFoundError`, which is an `OSError` and is
already handled correctly by the caller — a broken `~/.zshrc` symlink is a
machine this module should refuse, not one it should quietly replace.)*

---

## Warnings

### WR-01: `PoliciesScreen` is the screen the WR-02/WR-03 fix missed — no `enter_view`, stale after an in-app uninstall

**File:** `installer/wizard_app.py:569-576` (`active_state` snapshot), `installer/wizard_app.py:552` (no `enter_view` override), `setup.py:202-...` (`PolicyInputs(policies=[...])` built once)

**Issue:** The audit asked for was "no screen with live-mutated state was missed
this time." One was. `PoliciesScreen.__init__` snapshots
`{policy.id: policy.active for policy in inputs.policies}`, and `Policy.active`
is itself evaluated once at `_build_app` time. `PoliciesScreen` is the only one
of the three non-catalog screens with no `enter_view`.

The mutator is the Uninstall view: `perform_uninstall` removes the ban's shims
and alias blocks, strips the managed PATH block, and sweeps every tweak plus the
omz policy — i.e. it changes the on-disk answer for *every row* the Policies
view renders. Nothing quits the app after an uninstall, so
Uninstall → apply → `ctrl+p` → Policies is an ordinary navigation.

Reproduced headlessly against the real `UnifiedApp`, driving the view's own
`_remove` closure:

```
policies BEFORE:     {'ban': True, 'tweak:countdown': True}
perform_uninstall -> SweepResult(swept=('tweak:countdown',), failed=())
policies AFTER nav:  {'ban': True, 'tweak:countdown': True}
ban shim on disk:    False
tweak helper on disk: False
```

Both rows still render `● [on]` for policies that are gone. This is the
stale-True direction of the original WR-02, and it costs the user a spurious
toggle-off before they can re-enable anything. `ui_common.py:316-326`'s
`enter_view` docstring states the rule the fix commit adopted — *"a view that
holds such state overrides this"* — and this view holds such state and does not.

Lower severity than CR-01/CR-02: nothing is destroyed, the `Policy.remove`
closures are idempotent, and two keystrokes recover.

**Fix:** the same predicate treatment already applied three times. `Policy.active`
is captured at construction, so the whole list must be rebuilt, not just re-read:

```python
# wizard_app.py
@dataclass(frozen=True)
class PolicyInputs:
    policies: Callable[[], list[Policy]]

# PoliciesScreen
def enter_view(self) -> None:
    refreshed = self._policies_of()
    state = {policy.id: policy.active for policy in refreshed}
    if state == self.active_state:
        return
    self._policies, self.active_state = refreshed, state
    if self.is_mounted:
        self._rebuild_table()
```

with `setup.py` passing a closure over the existing `[ban_policy(...), *tweak
policies, omz_plugins_policy(...)]` construction rather than its result.

### WR-02: WR-05's "impossible by construction" invariant covers only one of the two teardown entry points — `perform_uninstall` still reads after it destroys

**File:** `installer/app.py:437-438`, vs. the fixed `installer/app.py:356-359 / 387`

**Issue:** `7a6c33b` hoisted the `active_policies` call in `run_uninstall` and
added `test_run_uninstall_sweeps_the_very_tweaks_it_previewed`. It did not touch
`perform_uninstall`, which is the *other* composition-root teardown (the TUI's
`remove=_do_uninstall` wire) and has the identical shape:

```python
remove_paths(list(decision.paths))
if decision.remove_ban:
    remove_shims(bin_dir); remove_ban_aliases(myshellrc_path); ...
if decision.remove_path_block:
    remove_managed_block(myshellrc_path)
if decision.remove_tweaks:
    return sweep_tweaks(bundles, rc_path=myshellrc_path, ...)   # <- reads HERE
```

and `sweep_tweaks`' own docstring now says *"`run_uninstall` is not such a
caller and must not use it — it deletes user artifacts in between"*, which is an
exact description of `perform_uninstall` too. Worse, the preview the user
consented to came from a *third* read entirely — `UninstallScreen.enter_view`'s
`active_tweak_ids`, taken before the confirm modal.

Reproduced with the same stand-in the new `run_uninstall` test uses:

```
previewed by the view: ('tweak:countdown',)
SweepResult:           SweepResult(swept=(), failed=())
```

The row told the user `tweak:countdown` would be disabled; the sweep silently
reported nothing. As with the original WR-05, no *live* divergence exists today
(shim names do not collide with `tools-installer-` helpers, every rc rewrite is
marker-scoped) — but the entire point of `7a6c33b` was to stop relying on that
argument, and half the surface still does.

**Fix:** hoist inside `perform_uninstall`, mirroring `run_uninstall`:

```python
def perform_uninstall(decision, *, bin_dir, myshellrc_path, rc_paths, bundles, zshrc_path):
    # Read before anything is destroyed, for the same reason run_uninstall does.
    policies = (
        active_policies(bundles, rc_path=myshellrc_path, bin_dir=bin_dir, zshrc_path=zshrc_path)
        if decision.remove_tweaks
        else []
    )
    remove_paths(list(decision.paths))
    ...
    return sweep_policies(policies) if decision.remove_tweaks else SweepResult()
```

and port `test_run_uninstall_sweeps_the_very_tweaks_it_previewed` to
`perform_uninstall`. Failing that, `.claude/architecture.md:133-141` should name
`perform_uninstall` as a documented exception rather than leaving the reader to
infer the invariant is global.

### WR-03: WR-06's mutation claim is false for `tweak_ids` — freezing it at build time passes all 850 tests

**File:** `tests/test_setup.py:166-187`, `setup.py:199-201`

**Issue:** I applied each of the four claimed mutations to `setup.py` and ran
the suite. Three are caught. One is not — and it is the one that reintroduces
the *original* WR-02 defect, on the *original* row it was found on:

| Mutation | Result |
|---|---|
| delete `remove=_do_uninstall` | 4 failures in `test_setup.py` |
| `bundles=BUNDLES` → `applicable_bundles(platform)` | `test_the_uninstall_view_is_wired_to_a_total_teardown...` fails at line 160 |
| `ban_names=lambda: [...]` → plain list | `test_the_uninstall_view_reads_every_environment_row_live` fails: `TypeError: 'list' object is not callable` |
| **`tweak_ids` frozen to a build-time snapshot** | **`make test` → 850 passed, exit 0** |

The surviving mutation:

```python
tweak_ids=(
    lambda frozen=active_tweak_ids(
        BUNDLES, rc_path=_MYSHELLRC, bin_dir=_DEFAULT_BIN_DIR, zshrc_path=_ZSHRC
    ): frozen
),
```

`test_the_uninstall_view_reads_every_environment_row_live` proves `ban_names`
and `has_path_block` are live by *mutating the environment and re-reading*
(`install_shims(...)`, `write_myshellrc(...)`), but for `tweak_ids` it only
asserts `inputs.tweak_ids() == ()`. A callable that returns a frozen snapshot
satisfies that. Nothing in `tests/test_wizard_app.py` closes the gap either — it
tests `UninstallScreen.enter_view` against a *fake* predicate, so it proves the
screen re-reads, never that the composition root gives it something worth
re-reading.

**Fix:** finish the third leg of the test that already exists — enable a tweak
behind the view's back exactly as the other two rows do:

```python
    assert inputs.tweak_ids() == ()
    ...
    tweak_policy(
        next(b for b in BUNDLES if b.id == "countdown"),
        rc_path=tmp_path / ".myshellrc",
        bin_dir=bin_dir,
    ).apply()
    assert "tweak:countdown" in inputs.tweak_ids()
```

---

## Info

### IN-01: A failed enable leaves behind a `~/.myshellrc` that did not exist before

**File:** `installer/omz.py:317-328`

When `write_plugins` reserves the claim and the `.zshrc` write is then refused,
the rollback path calls `_clear_owned`, which strips the block but does not
remove the file `_record_owned` just created. Probed: after a rolled-back enable
on a machine with no `~/.myshellrc`, `state_path.exists()` is `True` with
content `''`. Harmless (inert, empty) but it is a new artifact no teardown
unlinks — the same shape as iteration-1's IN-05. **Fix:** unlink `state_path`
when `_clear_owned` empties it of every managed block.

### IN-02: The rollback in `write_plugins` can mask the error it is rolling back

**File:** `installer/omz.py:321-328`

`except OSError: … _record_owned(state_path, previous); raise`. If that rollback
write itself raises (`~/.myshellrc` immutable, quota full — the same conditions
that plausibly caused the first failure), the new `OSError` propagates and the
original is lost, and the record is left over-broad. Over-broad is the safe
direction by design, so this is diagnostics only. **Fix:** wrap the rollback in
its own `try/except OSError: pass` so the original exception always reaches the
caller.

### IN-03: A `remove_plugins` that succeeded on `.zshrc` but failed on the record reports "could not disable"

**File:** `installer/omz.py:359-361`, `installer/app.py:390-393`

Probed: with the `.zshrc` write allowed and the record write refused, `.zshrc`
is correctly edited, the `OSError` propagates, `sweep_policies` reports `failed`,
and the CLI prints `Could not disable: omz-plugins. Check permissions and
re-run.` — while the user-visible half of the operation already happened. A
retry self-heals (verified), so this is a wording issue, not a state issue.

### IN-04: `_build_app` computes the doctor's ban status and warning and discards both

**File:** `setup.py:147-153`

`doctor_data(...)` returns `report, _status, _warning`; the last two are now
dead because `_guard_state` re-derives them. `doctor_data` still needs them for
the CLI `run_doctor`, so the function is fine; the composition root is doing
work it throws away. Cosmetic. **Fix:** either add an `audit_only` entry point
or leave a one-line comment saying the discard is deliberate, so the next reader
does not "fix" it by re-snapshotting.

### IN-05: `_predicate`'s `cast` is fine, but its value/callable polymorphism has one sharp edge

**File:** `tests/test_wizard_app.py:59-75`, `tests/test_setup.py:217`

Both `cast` uses are in-convention — narrowing something the type system
genuinely cannot narrow (an unbounded `_T` that could itself be callable; an
`object` pulled out of a `dict[str, object]`), the same justification as
`installer/model.py:58` and `installer/executors.py:38`. Keep them. The one
latent hazard is `_predicate`'s `if callable(value)` branch: a future test that
means to pass a *value* which happens to be callable would be silently treated
as a predicate. No current call site can hit it (`list[str]`, `bool`,
`tuple[str, ...]` are never callable), so this is a note, not a change request.

### IN-06: Disposition of the five deferred iteration-1 Info findings

Only one is user-visible enough to matter, and CR-01 subsumes it:

- **IN-01 (empty record still reports "disabled")** — real, and now the *milder*
  of two variants of the same wording defect; CR-01 is the severe one. Fixing
  CR-01 should include making `omz_removal_detail` and `policy.py:241` say what
  actually happened. Worth doing together; not worth doing alone.
- **IN-02 (`_refusal` misdiagnoses single-line failures as "multi-line")** —
  becomes *more* visible if CR-01 is fixed as proposed, since `_refusal`'s text
  would then surface on the teardown path. Fold into CR-01's fix.
- **IN-03 (TUI never names the plugins/file)**, **IN-04 (`#policy-detail` height
  7 clips on wrap)**, **IN-05 (`~/.myshellrc` created under `split` mode)** —
  cosmetic or narrow; safe to carry forward as documented limitations.

---

## Recommendation to the orchestrator

Max cycles are reached, so this is a judgement call, not another loop. My read:

- **CR-02 is the one to fix by hand.** It is a five-line change with a clear
  correct form, it needs no design decision, it brings `omz.py` in line with
  every sibling writer, and the failure it prevents (silently detaching a
  dotfiles repo) is both common and invisible to the user until much later.
- **CR-01 needs a decision, not just a patch.** The fix inverts a documented
  design property (`remove_plugins`' totality against an unparseable array) and
  will likely require touching `tests/test_uninstall.py`'s totality assertions
  and `app.py`'s remediation string. If that is too much for a manual pass,
  document it precisely: *"a `.zshrc` whose plugins array is converted to the
  multi-line form after the policy is enabled will have its installer-added
  names orphaned and be reported as disabled."*
- **WR-01/WR-02/WR-03 are safe to carry forward.** All three are "the invariant
  is unenforced" rather than "the invariant is violated today". WR-03 is the
  cheapest of the three (four lines in one existing test) and closes the door on
  WR-02 silently regressing, so it is the best value if any warning gets fixed.

---

_Reviewed: 2026-09-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep — iteration 3 of 3 (cap reached, final)_
_Gates independently re-run on this exact tree: `make validate` exit 0; `make test` 850 passed, 99.83% coverage_
_Mutations independently applied and reverted; working tree verified clean against HEAD afterwards_
