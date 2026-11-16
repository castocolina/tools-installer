#!/usr/bin/env bash
# hooks-e2e.sh — real-git proof of the commit hook, the push gate and the hook step.
#
# `make hooks-e2e` (and CI) runs this script. It builds throwaway git repos under
# `mktemp -d`, starts every git, uv and pre-commit command from an `env -i`
# allowlist, and never touches this checkout's `.git`. An EXIT trap removes the
# scratch dir and stops every process it started.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SELF="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"

PRE_COMMIT_BIN="$(command -v pre-commit || true)"
UV_BIN="$(command -v uv || true)"
PY_BIN="$(command -v python || true)"
if [ -z "$PRE_COMMIT_BIN" ] || [ -z "$UV_BIN" ] || [ -z "$PY_BIN" ]; then
  printf 'hooks-e2e: run make dev-setup first\n' >&2
  exit 1
fi
PRE_COMMIT_DIR="$(dirname "$PRE_COMMIT_BIN")"
UV_DIR="$(dirname "$UV_BIN")"

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/hooks-e2e.XXXXXX")"
mkdir -p "$SCRATCH/home" "$SCRATCH/marks" "$SCRATCH/expect" "$SCRATCH/cache" \
  "$SCRATCH/uv-cache" "$SCRATCH/pre-commit"
BG_PIDS=()
PUSH_PID=""
FAILURES=0

# Every git, uv and pre-commit call goes through here, so only the allowlist below
# reaches it: no inherited GIT_DIR, GIT_INDEX_FILE or user git config (RESEARCH Pitfall 2).
# `exec` keeps the pid of a backgrounded call equal to the pid its python wrapper
# makes a process group leader, so `kill -- -$pid` reaches the whole push group.
run_isolated() {
  exec env -i \
    PATH="$PRE_COMMIT_DIR:$UV_DIR:/usr/bin:/bin" \
    HOME="$SCRATCH/home" \
    PRE_COMMIT_HOME="$SCRATCH/pre-commit" \
    XDG_CACHE_HOME="$SCRATCH/cache" \
    UV_CACHE_DIR="$SCRATCH/uv-cache" \
    UV_PYTHON="$PY_BIN" \
    UV_OFFLINE=1 \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    GIT_TERMINAL_PROMPT=0 \
    GIT_AUTHOR_NAME=hooks-e2e \
    GIT_AUTHOR_EMAIL=hooks-e2e@example.invalid \
    GIT_COMMITTER_NAME=hooks-e2e \
    GIT_COMMITTER_EMAIL=hooks-e2e@example.invalid \
    LANG=C \
    "$@"
}

ok() {
  printf 'ok %s\n' "$1"
}

fail() {
  printf 'FAIL %s: %s\n' "$1" "$2"
  FAILURES=$((FAILURES + 1))
}

# Build one scratch repo: real devtools and .pre-commit-config.yaml, a cheap Makefile
# whose gate targets record that they ran, and a local bare remote with main pushed.
new_repo() {
  local name="$1" repo="$SCRATCH/$1" marks="$SCRATCH/marks/$1"
  mkdir -p "$repo" "$marks" "$repo/tests"
  cat >"$repo/pyproject.toml" <<'EOF'
[project]
name = "hooks-e2e-scratch"
version = "0"
requires-python = ">=3.11"

[tool.uv]
package = false
EOF
  printf '.venv/\nuv.lock\n__pycache__/\n' >"$repo/.gitignore"
  cp -R "$ROOT/devtools" "$repo/"
  rm -rf "$repo/devtools/__pycache__"
  cp "$ROOT/.pre-commit-config.yaml" "$repo/"
  cat >"$repo/Makefile" <<MAKE
lint:
	@touch "$marks/lint.ran"
	@if [ -e "\$(CURDIR)/LINT_FAIL" ]; then echo "lint failed"; exit 1; fi
format-check:
	@touch "$marks/format-check.ran"
typecheck:
	@touch "$marks/typecheck.ran"
security:
	@touch "$marks/security.ran"
dead-code:
	@touch "$marks/dead-code.ran"
shellcheck:
	@touch "$marks/shellcheck.ran"
test:
	@sh tests/check.sh
MAKE
  cat >"$repo/tests/check.sh" <<CHECK
#!/bin/sh
set -e
touch "$marks/test.ran"
if [ -e tests/slow ]; then
  touch "$marks/started"
  i=0
  while [ ! -e "$SCRATCH/stop" ] && [ "\$i" -lt 300 ]; do
    sleep 0.1
    i=\$((i + 1))
  done
fi
if [ -f conftest.py ] && grep -q '# hooks-e2e: pass all' conftest.py; then
  exit 0
fi
if grep -rq 'FAIL' tests/*.py; then
  echo "test failed"
  exit 1
fi
exit 0
CHECK
  chmod +x "$repo/tests/check.sh"
  printf 'print("ok")\n' >"$repo/tests/test_a.py"
  ( cd "$repo" && run_isolated git init -q -b main )
  ( cd "$repo" && run_isolated git add -A )
  ( cd "$repo" && run_isolated git commit -q -m init )
  ( cd "$repo" && run_isolated git init -q --bare "$SCRATCH/$name.git" )
  ( cd "$repo" && run_isolated git remote add origin "$SCRATCH/$name.git" )
  ( cd "$repo" && run_isolated git push -q origin main )
}

install_hooks() {
  ( cd "$SCRATCH/$1" && run_isolated uv run python -m devtools.hooks install )
}

# One unpushed commit, so a push carries a real ref update and the gate runs instead
# of taking its empty-input exit (review H4).
ahead() {
  ( cd "$SCRATCH/$1" && run_isolated git commit --allow-empty -q -m "$2" )
}

clear_marks() {
  rm -rf "$SCRATCH/marks/$1"
  mkdir -p "$SCRATCH/marks/$1"
}

expect_edit() {
  cp "$SCRATCH/$1/$2" "$SCRATCH/expect/$3"
}

# The edit is still there, byte for byte: `cmp -s` against the copy taken after the
# edit, plus a non-vacuity `git diff --quiet` that must exit 1 (review H3).
assert_restored() {
  cmp -s "$SCRATCH/$1/$2" "$SCRATCH/expect/$3" || return 1
  if ( cd "$SCRATCH/$1" && run_isolated git diff --quiet -- "$2" ); then
    return 1
  fi
  return 0
}

remote_sha() {
  run_isolated git -C "$SCRATCH/$1.git" rev-parse main
}

# Start `git push` in its own process group, from the scratch work tree, through
# run_isolated. Sets PUSH_PID and records it for cleanup.
push_bg() {
  local name="$1"
  shift
  ( cd "$SCRATCH/$name" && run_isolated "$PY_BIN" -c 'import os, sys; os.setpgid(0, 0); os.execvp(sys.argv[1], sys.argv[1:])' git push "$@" ) &
  PUSH_PID=$!
  BG_PIDS+=("$PUSH_PID")
}

live_groups() {
  local groups="$1" pgid out=""
  for pgid in $groups; do
    if pgrep -g "$pgid" >/dev/null 2>&1; then
      out="$out $pgid"
    fi
  done
  printf '%s\n' "$out"
}

collect_descendants() {
  local snapshot="$1" pids="$2" changed=1 pid child
  while [ "$changed" -eq 1 ]; do
    changed=0
    for pid in $pids; do
      while IFS= read -r child; do
        case " $pids " in
          *" $child "*) ;;
          *) pids="$pids $child"; changed=1 ;;
        esac
      done < <(awk -v p="$pid" '$2 == p { print $1 }' "$snapshot")
    done
  done
  printf '%s\n' "$pids"
}

collect_groups() {
  local snapshot="$1" pids="$2" pid pgid groups=""
  for pid in $pids; do
    pgid="$(awk -v p="$pid" '$1 == p { print $3; exit }' "$snapshot")"
    [ -n "$pgid" ] || continue
    case " $groups " in
      *" $pgid "*) ;;
      *) groups="$groups $pgid" ;;
    esac
  done
  printf '%s\n' "$groups"
}

# Reap every process group the harness caused, not only the recorded push groups:
# the gate starts pre-commit in a group of its own (review C2-M2). The scratch dir is
# removed only after no member of any collected group remains.
cleanup() {
  touch "$SCRATCH/stop" 2>/dev/null || true
  local snapshot pids groups pid pgid i live
  snapshot="$SCRATCH/ps.snapshot"
  ps -A -o pid= -o ppid= -o pgid= >"$snapshot" 2>/dev/null || : >"$snapshot"
  pids=""
  for pid in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
    pids="$pids $pid"
  done
  pids="$(collect_descendants "$snapshot" "$pids")"
  groups="$(collect_groups "$snapshot" "$pids")"
  for pid in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
    kill -INT -- "-$pid" 2>/dev/null || true
  done
  i=0
  while [ "$i" -lt 100 ]; do
    [ -z "$(live_groups "$groups")" ] && break
    sleep 0.1
    i=$((i + 1))
  done
  for pgid in $(live_groups "$groups"); do
    kill -KILL -- "-$pgid" 2>/dev/null || true
  done
  for pid in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
    wait "$pid" 2>/dev/null || true
  done
  i=0
  while [ "$i" -lt 50 ]; do
    [ -z "$(live_groups "$groups")" ] && break
    sleep 0.1
    i=$((i + 1))
  done
  live="$(live_groups "$groups")"
  if [ -n "$live" ]; then
    printf 'FAIL cleanup: process group %s survived\n' "$live" >&2
    exit 1
  fi
  rm -rf "$SCRATCH"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

commit_runs_static_gates() {
  new_repo gates
  install_hooks gates
  ahead gates c1
  local marks="$SCRATCH/marks/gates" target
  for target in lint format-check typecheck security dead-code shellcheck; do
    if [ ! -f "$marks/$target.ran" ]; then
      fail commit_runs_static_gates "missing $target.ran"
      return 0
    fi
  done
  if [ -f "$marks/test.ran" ]; then
    fail commit_runs_static_gates "test.ran is present after a commit"
    return 0
  fi
  ok commit_runs_static_gates
}

green_push_lands() {
  clear_marks gates
  local out
  out="$( cd "$SCRATCH/gates" && run_isolated git push origin main 2>&1 )" || {
    fail green_push_lands "push failed: $out"
    return 0
  }
  if [ ! -f "$SCRATCH/marks/gates/test.ran" ]; then
    fail green_push_lands "test.ran missing"
    return 0
  fi
  if [ "$(remote_sha gates)" != "$( cd "$SCRATCH/gates" && run_isolated git rev-parse HEAD )" ]; then
    fail green_push_lands "remote main does not equal local HEAD"
    return 0
  fi
  ok green_push_lands
}

red_push_is_aborted() {
  clear_marks gates
  printf 'FAIL\n' >"$SCRATCH/gates/tests/test_b.py"
  ( cd "$SCRATCH/gates" && run_isolated git add tests/test_b.py )
  ( cd "$SCRATCH/gates" && run_isolated git commit -q -m red )
  local before out
  before="$(remote_sha gates)"
  out="$( cd "$SCRATCH/gates" && run_isolated git push origin main 2>&1 )" && {
    fail red_push_is_aborted "push succeeded: $out"
    return 0
  }
  if [ ! -f "$SCRATCH/marks/gates/test.ran" ]; then
    fail red_push_is_aborted "test.ran missing (the gate never reached the suite)"
    return 0
  fi
  if [ "$(remote_sha gates)" != "$before" ]; then
    fail red_push_is_aborted "remote main moved"
    return 0
  fi
  ( cd "$SCRATCH/gates" && run_isolated git reset -q --hard HEAD~1 )
  ok red_push_is_aborted
}

# --- shared assertions for the refusal and restore cases ---------------------------------------

# One self-contained repo per case: a fresh remote at its initial commit, hooks installed, marks
# empty. This keeps every case independent of every other case's pushed refs and unstaged files.
fresh() {
  local name="$1"
  new_repo "$name"
  install_hooks "$name"
  clear_marks "$name"
}

contains() {
  printf '%s\n' "$1" | grep -Fq -- "$2"
}

line_of() {
  printf '%s\n' "$1" | grep -Fn -- "$2" | head -1 | cut -d: -f1
}

no_test_mark() {
  [ ! -f "$SCRATCH/marks/$1/test.ran" ]
}

# --- Task 2: real-git refusals, restore on every push shape, deletion, fail-fast ---------------

staged_is_refused_sorted() {
  fresh staged
  ahead staged c
  printf 'print("z")\n' >"$SCRATCH/staged/tests/z.py"
  printf 'print("a b")\n' >"$SCRATCH/staged/tests/a b.py"
  ( cd "$SCRATCH/staged" && run_isolated git add 'tests/z.py' 'tests/a b.py' )
  local out n_space n_z
  out="$( cd "$SCRATCH/staged" && run_isolated git push origin main 2>&1 )" && {
    fail staged_is_refused_sorted "push succeeded: $out"
    return 0
  }
  contains "$out" 'push refused:' || { fail staged_is_refused_sorted "no refusal: $out"; return 0; }
  n_space="$(line_of "$out" 'tests/a b.py')"
  n_z="$(line_of "$out" 'tests/z.py')"
  if [ -z "$n_space" ] || [ -z "$n_z" ] || [ "$n_space" -ge "$n_z" ]; then
    fail staged_is_refused_sorted "names not sorted/intact: $out"
    return 0
  fi
  no_test_mark staged || { fail staged_is_refused_sorted "test.ran is present"; return 0; }
  ok staged_is_refused_sorted
}

untracked_py_is_refused() {
  fresh untrackedpy
  ahead untrackedpy c
  printf 'FAIL\n' >"$SCRATCH/untrackedpy/tests/test_x.py"
  local out
  out="$( cd "$SCRATCH/untrackedpy" && run_isolated git push origin main 2>&1 )" && {
    fail untracked_py_is_refused "push succeeded: $out"
    return 0
  }
  if ! contains "$out" 'push refused:' || ! contains "$out" 'tests/test_x.py'; then
    fail untracked_py_is_refused "wrong refusal: $out"
    return 0
  fi
  no_test_mark untrackedpy || { fail untracked_py_is_refused "test.ran is present"; return 0; }
  ok untracked_py_is_refused
}

untracked_root_inputs_are_refused() {
  fresh rootinputs
  ahead rootinputs c
  printf '[pytest]\n' >"$SCRATCH/rootinputs/pytest.ini"
  printf '# local conftest\n' >"$SCRATCH/rootinputs/conftest.py"
  local out n_conf n_ini
  out="$( cd "$SCRATCH/rootinputs" && run_isolated git push origin main 2>&1 )" && {
    fail untracked_root_inputs_are_refused "push succeeded: $out"
    return 0
  }
  contains "$out" 'push refused:' || { fail untracked_root_inputs_are_refused "no refusal: $out"; return 0; }
  n_conf="$(line_of "$out" 'conftest.py')"
  n_ini="$(line_of "$out" 'pytest.ini')"
  if [ -z "$n_conf" ] || [ -z "$n_ini" ] || [ "$n_conf" -ge "$n_ini" ]; then
    fail untracked_root_inputs_are_refused "root names not sorted: $out"
    return 0
  fi
  no_test_mark rootinputs || { fail untracked_root_inputs_are_refused "test.ran is present"; return 0; }
  ok untracked_root_inputs_are_refused
}

untracked_planning_and_ignored_files_pass() {
  fresh exempt
  ahead exempt c
  mkdir -p "$SCRATCH/exempt/.planning" "$SCRATCH/exempt/.venv"
  printf 'a note\n' >"$SCRATCH/exempt/.planning/notes.md"
  printf 'x\n' >"$SCRATCH/exempt/.venv/x.py"
  local out
  out="$( cd "$SCRATCH/exempt" && run_isolated git push origin main 2>&1 )" || {
    fail untracked_planning_and_ignored_files_pass "push failed: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/exempt/test.ran" ] || {
    fail untracked_planning_and_ignored_files_pass "test.ran missing"
    return 0
  }
  ok untracked_planning_and_ignored_files_pass
}

ignored_root_conftest_is_refused() {
  fresh igconf
  printf 'FAIL\n' >"$SCRATCH/igconf/tests/test_b.py"
  ( cd "$SCRATCH/igconf" && run_isolated git add tests/test_b.py )
  ( cd "$SCRATCH/igconf" && run_isolated git commit -q -m red )
  local before out
  before="$(remote_sha igconf)"
  printf '# hooks-e2e: pass all\n' >"$SCRATCH/igconf/conftest.py"
  printf 'conftest.py\n' >>"$SCRATCH/igconf/.git/info/exclude"
  # Non-vacuity: the file is ignored, hidden from the ordinary untracked list, and really changes
  # what the suite does (the committed test fails but check.sh passes with this conftest).
  ( cd "$SCRATCH/igconf" && run_isolated git check-ignore -q conftest.py ) || {
    fail ignored_root_conftest_is_refused "conftest.py is not ignored"
    return 0
  }
  if ( cd "$SCRATCH/igconf" && run_isolated git ls-files --others --exclude-standard ) |
    grep -Fxq 'conftest.py'; then
    fail ignored_root_conftest_is_refused "conftest.py is in the ordinary untracked list"
    return 0
  fi
  ( cd "$SCRATCH/igconf" && run_isolated sh tests/check.sh ) || {
    fail ignored_root_conftest_is_refused "check.sh did not pass with the ignored conftest"
    return 0
  }
  clear_marks igconf
  out="$( cd "$SCRATCH/igconf" && run_isolated git push origin main 2>&1 )" && {
    fail ignored_root_conftest_is_refused "push succeeded: $out"
    return 0
  }
  if ! contains "$out" 'push refused:' || ! contains "$out" 'conftest.py'; then
    fail ignored_root_conftest_is_refused "wrong refusal: $out"
    return 0
  fi
  no_test_mark igconf || { fail ignored_root_conftest_is_refused "test.ran is present"; return 0; }
  if [ "$(remote_sha igconf)" != "$before" ]; then
    fail ignored_root_conftest_is_refused "remote main moved"
    return 0
  fi
  ok ignored_root_conftest_is_refused
}

ignored_gnumakefile_is_refused() {
  fresh ignu
  printf 'FAIL\n' >"$SCRATCH/ignu/tests/test_b.py"
  ( cd "$SCRATCH/ignu" && run_isolated git add tests/test_b.py )
  ( cd "$SCRATCH/ignu" && run_isolated git commit -q -m red )
  local before out
  before="$(remote_sha ignu)"
  printf 'lint format-check typecheck security dead-code shellcheck test: ; @true\n' \
    >"$SCRATCH/ignu/GNUmakefile"
  printf 'GNUmakefile\n' >>"$SCRATCH/ignu/.git/info/exclude"
  # Non-vacuity: GNU make reads GNUmakefile before Makefile, so `make test` passes although the
  # committed test fails; the real Makefile's test target still fails.
  ( cd "$SCRATCH/ignu" && run_isolated git check-ignore -q GNUmakefile ) || {
    fail ignored_gnumakefile_is_refused "GNUmakefile is not ignored"
    return 0
  }
  ( cd "$SCRATCH/ignu" && run_isolated make test ) || {
    fail ignored_gnumakefile_is_refused "make test did not pass with GNUmakefile"
    return 0
  }
  if ( cd "$SCRATCH/ignu" && run_isolated make -f Makefile test ); then
    fail ignored_gnumakefile_is_refused "Makefile test passed with the committed failing test"
    return 0
  fi
  clear_marks ignu
  out="$( cd "$SCRATCH/ignu" && run_isolated git push origin main 2>&1 )" && {
    fail ignored_gnumakefile_is_refused "push succeeded: $out"
    return 0
  }
  if ! contains "$out" 'push refused:' || ! contains "$out" 'GNUmakefile'; then
    fail ignored_gnumakefile_is_refused "wrong refusal: $out"
    return 0
  fi
  no_test_mark ignu || { fail ignored_gnumakefile_is_refused "test.ran is present"; return 0; }
  if [ "$(remote_sha ignu)" != "$before" ]; then
    fail ignored_gnumakefile_is_refused "remote main moved"
    return 0
  fi
  ok ignored_gnumakefile_is_refused
}

unstaged_edit_restored_existing_branch() {
  fresh editmain
  ahead editmain c
  printf 'FAIL\n' >>"$SCRATCH/editmain/tests/test_a.py"
  expect_edit editmain tests/test_a.py edit_existing
  clear_marks editmain
  local out
  out="$( cd "$SCRATCH/editmain" && run_isolated git push origin main 2>&1 )" || {
    fail unstaged_edit_restored_existing_branch "push failed: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/editmain/test.ran" ] || {
    fail unstaged_edit_restored_existing_branch "test.ran missing"
    return 0
  }
  assert_restored editmain tests/test_a.py edit_existing || {
    fail unstaged_edit_restored_existing_branch "edit was not restored"
    return 0
  }
  ok unstaged_edit_restored_existing_branch
}

unstaged_edit_restored_new_branch() {
  fresh editfeat
  ( cd "$SCRATCH/editfeat" && run_isolated git checkout -q -b feat )
  printf 'FAIL\n' >>"$SCRATCH/editfeat/tests/test_a.py"
  expect_edit editfeat tests/test_a.py edit_feat
  local out
  out="$( cd "$SCRATCH/editfeat" && run_isolated git push origin feat 2>&1 )" || {
    fail unstaged_edit_restored_new_branch "push failed: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/editfeat/test.ran" ] || {
    fail unstaged_edit_restored_new_branch "test.ran missing"
    return 0
  }
  assert_restored editfeat tests/test_a.py edit_feat || {
    fail unstaged_edit_restored_new_branch "edit was not restored"
    return 0
  }
  ( cd "$SCRATCH/editfeat" && run_isolated git checkout -q -- tests/test_a.py )
  ( cd "$SCRATCH/editfeat" && run_isolated git checkout -q main )
  ok unstaged_edit_restored_new_branch
}

unstaged_edit_restored_root_push() {
  fresh rootpush
  printf 'FAIL\n' >>"$SCRATCH/rootpush/tests/test_a.py"
  expect_edit rootpush tests/test_a.py edit_root
  ( cd "$SCRATCH/rootpush" && run_isolated git init -q --bare "$SCRATCH/rootpush-empty.git" )
  local out
  out="$( cd "$SCRATCH/rootpush" && run_isolated git push "$SCRATCH/rootpush-empty.git" main 2>&1 )" || {
    fail unstaged_edit_restored_root_push "push failed: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/rootpush/test.ran" ] || {
    fail unstaged_edit_restored_root_push "test.ran missing"
    return 0
  }
  assert_restored rootpush tests/test_a.py edit_root || {
    fail unstaged_edit_restored_root_push "edit was not restored"
    return 0
  }
  ok unstaged_edit_restored_root_push
}

failed_gate_restores_edit() {
  fresh failedgate
  printf 'FAIL\n' >"$SCRATCH/failedgate/tests/test_b.py"
  ( cd "$SCRATCH/failedgate" && run_isolated git add tests/test_b.py )
  ( cd "$SCRATCH/failedgate" && run_isolated git commit -q -m red )
  printf '# local edit\n' >>"$SCRATCH/failedgate/tests/test_a.py"
  expect_edit failedgate tests/test_a.py edit_failed
  local before out
  before="$(remote_sha failedgate)"
  clear_marks failedgate
  out="$( cd "$SCRATCH/failedgate" && run_isolated git push origin main 2>&1 )" && {
    fail failed_gate_restores_edit "push succeeded: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/failedgate/test.ran" ] || {
    fail failed_gate_restores_edit "test.ran missing"
    return 0
  }
  if [ "$(remote_sha failedgate)" != "$before" ]; then
    fail failed_gate_restores_edit "remote main moved"
    return 0
  fi
  assert_restored failedgate tests/test_a.py edit_failed || {
    fail failed_gate_restores_edit "edit was not restored"
    return 0
  }
  ( cd "$SCRATCH/failedgate" && run_isolated git checkout -q -- tests/test_a.py )
  ( cd "$SCRATCH/failedgate" && run_isolated git reset -q --hard HEAD~1 )
  ok failed_gate_restores_edit
}

head_refspec_passes() {
  fresh refspec
  ahead refspec c
  local out
  out="$( cd "$SCRATCH/refspec" && run_isolated git push origin HEAD:other2 2>&1 )" || {
    fail head_refspec_passes "push failed: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/refspec/test.ran" ] || {
    fail head_refspec_passes "test.ran missing"
    return 0
  }
  ok head_refspec_passes
}

not_head_is_refused() {
  fresh otherbranch
  ( cd "$SCRATCH/otherbranch" && run_isolated git checkout -q -b other )
  ( cd "$SCRATCH/otherbranch" && run_isolated git commit --allow-empty -q -m other )
  ( cd "$SCRATCH/otherbranch" && run_isolated git checkout -q main )
  local out
  out="$( cd "$SCRATCH/otherbranch" && run_isolated git push origin other 2>&1 )" && {
    fail not_head_is_refused "push succeeded: $out"
    return 0
  }
  if ! contains "$out" 'push refused:' || ! contains "$out" 'check out that branch'; then
    fail not_head_is_refused "wrong refusal: $out"
    return 0
  fi
  no_test_mark otherbranch || { fail not_head_is_refused "test.ran is present"; return 0; }
  ok not_head_is_refused
}

deletion_runs_no_checks() {
  fresh deletion
  ( cd "$SCRATCH/deletion" && run_isolated git checkout -q -b feat )
  ( cd "$SCRATCH/deletion" && run_isolated git push -q origin feat )
  printf 'staged\n' >"$SCRATCH/deletion/staged.txt"
  ( cd "$SCRATCH/deletion" && run_isolated git add staged.txt )
  local out
  if ! ( cd "$SCRATCH/deletion" && run_isolated git ls-remote origin refs/heads/feat ) |
    grep -q .; then
    fail deletion_runs_no_checks "remote feat ref was not created"
    return 0
  fi
  clear_marks deletion
  out="$( cd "$SCRATCH/deletion" && run_isolated git push origin --delete feat 2>&1 )" || {
    fail deletion_runs_no_checks "push failed: $out"
    return 0
  }
  if [ -n "$(ls "$SCRATCH/marks/deletion"/*.ran 2>/dev/null)" ]; then
    fail deletion_runs_no_checks "a gate mark appeared on a deletion"
    return 0
  fi
  if ( cd "$SCRATCH/deletion" && run_isolated git ls-remote origin refs/heads/feat ) | grep -q .; then
    fail deletion_runs_no_checks "remote feat ref survived the deletion"
    return 0
  fi
  ok deletion_runs_no_checks
}

unstaged_config_is_refused() {
  fresh cfg
  ahead cfg c
  printf '# local\n' >>"$SCRATCH/cfg/.pre-commit-config.yaml"
  local out
  out="$( cd "$SCRATCH/cfg" && run_isolated git push origin main 2>&1 )" && {
    fail unstaged_config_is_refused "push succeeded: $out"
    return 0
  }
  if ! contains "$out" 'push refused:' || ! contains "$out" '.pre-commit-config.yaml'; then
    fail unstaged_config_is_refused "wrong refusal: $out"
    return 0
  fi
  no_test_mark cfg || { fail unstaged_config_is_refused "test.ran is present"; return 0; }
  ( cd "$SCRATCH/cfg" && run_isolated git checkout -q -- .pre-commit-config.yaml )
  ok unstaged_config_is_refused
}

unmerged_is_refused() {
  fresh unmerged
  ( cd "$SCRATCH/unmerged" && run_isolated git checkout -q -b side )
  printf 'side\n' >"$SCRATCH/unmerged/tests/test_a.py"
  ( cd "$SCRATCH/unmerged" && run_isolated git add tests/test_a.py )
  ( cd "$SCRATCH/unmerged" && run_isolated git commit -q -m side )
  ( cd "$SCRATCH/unmerged" && run_isolated git checkout -q main )
  printf 'main\n' >"$SCRATCH/unmerged/tests/test_a.py"
  ( cd "$SCRATCH/unmerged" && run_isolated git add tests/test_a.py )
  ( cd "$SCRATCH/unmerged" && run_isolated git commit -q -m mainedit )
  if ( cd "$SCRATCH/unmerged" && run_isolated git merge side ); then
    fail unmerged_is_refused "the merge was clean"
    return 0
  fi
  local out
  out="$( cd "$SCRATCH/unmerged" && run_isolated git push origin main 2>&1 )" && {
    fail unmerged_is_refused "push succeeded: $out"
    return 0
  }
  if ! contains "$out" 'push refused:' || ! contains "$out" 'merge'; then
    fail unmerged_is_refused "wrong refusal: $out"
    return 0
  fi
  no_test_mark unmerged || { fail unmerged_is_refused "test.ran is present"; return 0; }
  ( cd "$SCRATCH/unmerged" && run_isolated git merge --abort )
  ok unmerged_is_refused
}

fail_fast_skips_test() {
  new_repo failfast
  printf 'x\n' >"$SCRATCH/failfast/LINT_FAIL"
  ( cd "$SCRATCH/failfast" && run_isolated git add LINT_FAIL )
  ( cd "$SCRATCH/failfast" && run_isolated git commit -q -m lintfail )
  install_hooks failfast
  clear_marks failfast
  local out
  out="$( cd "$SCRATCH/failfast" && run_isolated git push origin main 2>&1 )" && {
    fail fail_fast_skips_test "push succeeded: $out"
    return 0
  }
  [ -f "$SCRATCH/marks/failfast/lint.ran" ] || {
    fail fail_fast_skips_test "lint.ran missing: $out"
    return 0
  }
  [ ! -f "$SCRATCH/marks/failfast/test.ran" ] || {
    fail fail_fast_skips_test "test.ran present after a lint failure: $out"
    return 0
  }
  ok fail_fast_skips_test
}

# --- Task 3: the real hook step's install branches ---------------------------------------------

install_leaves_both_hooks_and_is_idempotent() {
  fresh hooksbasic
  local h="$SCRATCH/hooksbasic/.git/hooks" out
  [ -x "$h/pre-commit" ] && [ -x "$h/pre-push" ] || {
    fail install_leaves_both_hooks_and_is_idempotent "a hook file is missing or not executable"
    return 0
  }
  cp "$h/pre-commit" "$SCRATCH/pc-idempotent"
  cp "$h/pre-push" "$SCRATCH/pp-idempotent"
  out="$( cd "$SCRATCH/hooksbasic" && run_isolated uv run python -m devtools.hooks install 2>&1 )" || {
    fail install_leaves_both_hooks_and_is_idempotent "second install failed: $out"
    return 0
  }
  cmp -s "$h/pre-commit" "$SCRATCH/pc-idempotent" || {
    fail install_leaves_both_hooks_and_is_idempotent "pre-commit changed on rerun"
    return 0
  }
  cmp -s "$h/pre-push" "$SCRATCH/pp-idempotent" || {
    fail install_leaves_both_hooks_and_is_idempotent "pre-push changed on rerun"
    return 0
  }
  ok install_leaves_both_hooks_and_is_idempotent
}

install_outside_a_checkout_skips() {
  mkdir -p "$SCRATCH/plain"
  cp -R "$ROOT/devtools" "$SCRATCH/plain/"
  cp "$ROOT/.pre-commit-config.yaml" "$ROOT/Makefile" "$SCRATCH/plain/"
  local out
  out="$( cd "$SCRATCH/plain" && run_isolated "$PY_BIN" -m devtools.hooks install 2>&1 )" || {
    fail install_outside_a_checkout_skips "hook step failed: $out"
    return 0
  }
  if ! contains "$out" 'not a git' || ! contains "$out" 'checkout; skipping'; then
    fail install_outside_a_checkout_skips "no skip message: $out"
    return 0
  fi
  ok install_outside_a_checkout_skips
}

install_with_hooks_path_fails() {
  fresh hookspath
  ( cd "$SCRATCH/hookspath" && run_isolated git config core.hooksPath .githooks )
  local out
  out="$( cd "$SCRATCH/hookspath" && run_isolated uv run python -m devtools.hooks install 2>&1 )" && {
    fail install_with_hooks_path_fails "hook step succeeded: $out"
    return 0
  }
  contains "$out" 'core.hooksPath' || {
    fail install_with_hooks_path_fails "core.hooksPath not named: $out"
    return 0
  }
  ok install_with_hooks_path_fails
}

install_from_a_worktree_uses_the_common_dir() {
  fresh wt
  ( cd "$SCRATCH/wt" && run_isolated git worktree add -q "$SCRATCH/wt-wt" -b wt )
  local out
  out="$( cd "$SCRATCH/wt-wt" && run_isolated uv run python -m devtools.hooks install 2>&1 )" || {
    fail install_from_a_worktree_uses_the_common_dir "hook step failed: $out"
    return 0
  }
  [ -f "$SCRATCH/wt/.git/hooks/pre-push" ] || {
    fail install_from_a_worktree_uses_the_common_dir "shared pre-push missing"
    return 0
  }
  if [ -n "$(find "$SCRATCH/wt/.git/worktrees" -type f -name pre-push 2>/dev/null)" ]; then
    fail install_from_a_worktree_uses_the_common_dir "a worktree-local pre-push was written"
    return 0
  fi
  contains "$out" 'linked worktree' || {
    fail install_from_a_worktree_uses_the_common_dir "no main-checkout warning: $out"
    return 0
  }
  ( cd "$SCRATCH/wt" && run_isolated git worktree remove --force "$SCRATCH/wt-wt" )
  ok install_from_a_worktree_uses_the_common_dir
}

foreign_pre_commit_becomes_legacy() {
  new_repo legacy
  cat >"$SCRATCH/legacy/.git/hooks/pre-commit" <<EOF
#!/bin/sh
touch "$SCRATCH/marks/legacy/foreign.ran"
EOF
  chmod +x "$SCRATCH/legacy/.git/hooks/pre-commit"
  install_hooks legacy
  [ -f "$SCRATCH/legacy/.git/hooks/pre-commit.legacy" ] || {
    fail foreign_pre_commit_becomes_legacy "pre-commit.legacy missing"
    return 0
  }
  clear_marks legacy
  ( cd "$SCRATCH/legacy" && run_isolated git commit --allow-empty -q -m after_install )
  [ -f "$SCRATCH/marks/legacy/foreign.ran" ] || {
    fail foreign_pre_commit_becomes_legacy "the legacy hook did not run on a commit"
    return 0
  }
  ok foreign_pre_commit_becomes_legacy
}

foreign_pre_push_is_refused_untouched() {
  new_repo foreignpp
  printf '#!/bin/sh\necho mine\n' >"$SCRATCH/foreignpp/.git/hooks/pre-push"
  chmod +x "$SCRATCH/foreignpp/.git/hooks/pre-push"
  cp "$SCRATCH/foreignpp/.git/hooks/pre-push" "$SCRATCH/foreignpp-copy"
  local out
  out="$( cd "$SCRATCH/foreignpp" && run_isolated uv run python -m devtools.hooks install 2>&1 )" && {
    fail foreign_pre_push_is_refused_untouched "hook step succeeded: $out"
    return 0
  }
  cmp -s "$SCRATCH/foreignpp/.git/hooks/pre-push" "$SCRATCH/foreignpp-copy" || {
    fail foreign_pre_push_is_refused_untouched "the foreign hook was modified"
    return 0
  }
  ok foreign_pre_push_is_refused_untouched
}

pre_push_symlink_is_refused_untouched() {
  new_repo ppsymlink
  printf '#!/bin/sh\n# tools-installer: pre-push gate (installed by make dev-setup; do not edit)\necho mine\n' \
    >"$SCRATCH/link-target"
  cp "$SCRATCH/link-target" "$SCRATCH/link-target-copy"
  ln -s "$SCRATCH/link-target" "$SCRATCH/ppsymlink/.git/hooks/pre-push"
  local out
  out="$( cd "$SCRATCH/ppsymlink" && run_isolated uv run python -m devtools.hooks install 2>&1 )" && {
    fail pre_push_symlink_is_refused_untouched "hook step succeeded: $out"
    return 0
  }
  [ -L "$SCRATCH/ppsymlink/.git/hooks/pre-push" ] || {
    fail pre_push_symlink_is_refused_untouched "pre-push is no longer a symlink"
    return 0
  }
  cmp -s "$SCRATCH/link-target" "$SCRATCH/link-target-copy" || {
    fail pre_push_symlink_is_refused_untouched "the symlink target was modified"
    return 0
  }
  ok pre_push_symlink_is_refused_untouched
}

pre_commit_symlink_is_refused_untouched() {
  new_repo pcsymlink
  printf '#!/usr/bin/env bash\n# File generated by pre-commit: https://pre-commit.com\necho mine\n' \
    >"$SCRATCH/pc-target"
  cp "$SCRATCH/pc-target" "$SCRATCH/pc-target-copy"
  ln -s "$SCRATCH/pc-target" "$SCRATCH/pcsymlink/.git/hooks/pre-commit"
  local out
  out="$( cd "$SCRATCH/pcsymlink" && run_isolated uv run python -m devtools.hooks install 2>&1 )" && {
    fail pre_commit_symlink_is_refused_untouched "hook step succeeded: $out"
    return 0
  }
  [ -L "$SCRATCH/pcsymlink/.git/hooks/pre-commit" ] || {
    fail pre_commit_symlink_is_refused_untouched "pre-commit is no longer a symlink"
    return 0
  }
  cmp -s "$SCRATCH/pc-target" "$SCRATCH/pc-target-copy" || {
    fail pre_commit_symlink_is_refused_untouched "the symlink target was modified"
    return 0
  }
  [ ! -e "$SCRATCH/pcsymlink/.git/hooks/pre-push" ] || {
    fail pre_commit_symlink_is_refused_untouched "pre-push was written despite the refusal"
    return 0
  }
  ok pre_commit_symlink_is_refused_untouched
}

foreign_pre_commit_with_legacy_is_refused_untouched() {
  new_repo pclegacy
  printf '#!/bin/sh\necho mine\n' >"$SCRATCH/pclegacy/.git/hooks/pre-commit"
  printf '#!/bin/sh\necho older\n' >"$SCRATCH/pclegacy/.git/hooks/pre-commit.legacy"
  chmod +x "$SCRATCH/pclegacy/.git/hooks/pre-commit" "$SCRATCH/pclegacy/.git/hooks/pre-commit.legacy"
  cp "$SCRATCH/pclegacy/.git/hooks/pre-commit" "$SCRATCH/pc-foreign-copy"
  cp "$SCRATCH/pclegacy/.git/hooks/pre-commit.legacy" "$SCRATCH/pc-legacy-copy"
  local out
  out="$( cd "$SCRATCH/pclegacy" && run_isolated uv run python -m devtools.hooks install 2>&1 )" && {
    fail foreign_pre_commit_with_legacy_is_refused_untouched "hook step succeeded: $out"
    return 0
  }
  contains "$out" 'pre-commit.legacy' || {
    fail foreign_pre_commit_with_legacy_is_refused_untouched "legacy file not named: $out"
    return 0
  }
  cmp -s "$SCRATCH/pclegacy/.git/hooks/pre-commit" "$SCRATCH/pc-foreign-copy" || {
    fail foreign_pre_commit_with_legacy_is_refused_untouched "the foreign hook was modified"
    return 0
  }
  cmp -s "$SCRATCH/pclegacy/.git/hooks/pre-commit.legacy" "$SCRATCH/pc-legacy-copy" || {
    fail foreign_pre_commit_with_legacy_is_refused_untouched "the legacy hook was modified"
    return 0
  }
  [ ! -e "$SCRATCH/pclegacy/.git/hooks/pre-push" ] || {
    fail foreign_pre_commit_with_legacy_is_refused_untouched "pre-push was written despite the refusal"
    return 0
  }
  ok foreign_pre_commit_with_legacy_is_refused_untouched
}

# --- Task 3: interrupt restore and the harness's own abort cleanup -----------------------------

interrupt_restores_edit() {
  local sig="$1" name="intr$1" case_name="interrupt_$1_restores_edit"
  fresh "$name"
  touch "$SCRATCH/$name/tests/slow"
  ( cd "$SCRATCH/$name" && run_isolated git add tests/slow )
  ( cd "$SCRATCH/$name" && run_isolated git commit -q -m slow )
  printf 'FAIL\n' >>"$SCRATCH/$name/tests/test_a.py"
  expect_edit "$name" tests/test_a.py "$name"
  local before pid i=0
  before="$(remote_sha "$name")"
  clear_marks "$name"
  push_bg "$name" origin main
  pid="$PUSH_PID"
  while [ ! -f "$SCRATCH/marks/$name/started" ] && [ "$i" -lt 300 ]; do
    sleep 0.1
    i=$((i + 1))
  done
  if [ ! -f "$SCRATCH/marks/$name/started" ]; then
    fail "$case_name" "the suite never started"
    return 0
  fi
  kill -"$sig" -- "-$pid" 2>/dev/null || true
  if wait "$pid" 2>/dev/null; then
    fail "$case_name" "the push exited 0 after the signal"
    return 0
  fi
  if [ "$(remote_sha "$name")" != "$before" ]; then
    fail "$case_name" "remote main moved"
    return 0
  fi
  i=0
  while ! assert_restored "$name" tests/test_a.py "$name" && [ "$i" -lt 100 ]; do
    sleep 0.1
    i=$((i + 1))
  done
  assert_restored "$name" tests/test_a.py "$name" || {
    fail "$case_name" "the unstaged edit was not restored"
    return 0
  }
  ok "$case_name"
}

# Write one `<pid> <pgid>` line per collected process, plus the nested scratch dir, so the parent
# can prove that every group the abort left alive was reaped by the nested cleanup trap.
write_abort_pids() {
  local out="$1" snapshot="$SCRATCH/abort.ps" pids="" pid pgid
  ps -A -o pid= -o ppid= -o pgid= >"$snapshot" 2>/dev/null || : >"$snapshot"
  for pid in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
    pids="$pids $pid"
  done
  pids="$(collect_descendants "$snapshot" "$pids")"
  : >"$out"
  for pid in $pids; do
    pgid="$(awk -v p="$pid" '$1 == p { print $3; exit }' "$snapshot")"
    [ -n "$pgid" ] && printf '%s %s\n' "$pid" "$pgid" >>"$out"
  done
  printf 'scratch %s\n' "$SCRATCH" >>"$out"
}

live_pgids() {
  local groups="$1" pgid all
  all="$(ps -A -o pgid= 2>/dev/null | awk '{print $1}' | sort -u)"
  for pgid in $groups; do
    if printf '%s\n' "$all" | grep -Fxq "$pgid"; then
      printf '%s ' "$pgid"
    fi
  done
  printf '\n'
}

abort_scenario() {
  local outfile="$HOOKS_E2E_ABORT_PIDS" i=0
  new_repo abort
  install_hooks abort
  touch "$SCRATCH/abort/tests/slow"
  ( cd "$SCRATCH/abort" && run_isolated git add tests/slow )
  ( cd "$SCRATCH/abort" && run_isolated git commit -q -m slow )
  clear_marks abort
  push_bg abort origin main
  while [ ! -f "$SCRATCH/marks/abort/started" ] && [ "$i" -lt 300 ]; do
    sleep 0.1
    i=$((i + 1))
  done
  write_abort_pids "$outfile"
  exit 3
}

harness_abort_reaps_every_group() {
  local pidsfile="$SCRATCH/abort.pids" out rc groups count i=0 scratch_dir
  if out="$( HOOKS_E2E_ABORT_PIDS="$pidsfile" "$BASH" "$SELF" 2>&1 )"; then
    rc=0
  else
    rc=$?
  fi
  [ "$rc" -eq 3 ] || {
    fail harness_abort_reaps_every_group "nested exit $rc: $out"
    return 0
  }
  groups="$(awk 'NF == 2 { print $2 }' "$pidsfile" | sort -u | tr '\n' ' ')"
  count="$(printf '%s' "$groups" | wc -w)"
  [ "$count" -ge 2 ] || {
    fail harness_abort_reaps_every_group "only $count live group(s): $(cat "$pidsfile")"
    return 0
  }
  while [ -n "$(live_pgids "$groups")" ] && [ "$i" -lt 50 ]; do
    sleep 0.1
    i=$((i + 1))
  done
  if [ -n "$(live_pgids "$groups")" ]; then
    fail harness_abort_reaps_every_group "group(s) survived: $(live_pgids "$groups")"
    return 0
  fi
  scratch_dir="$(awk '$1 == "scratch" { print $2; exit }' "$pidsfile")"
  if [ -z "$scratch_dir" ] || [ -d "$scratch_dir" ]; then
    fail harness_abort_reaps_every_group "nested scratch dir survived: $scratch_dir"
    return 0
  fi
  ok harness_abort_reaps_every_group
}

main() {
  local t0
  t0=$(date +%s)
  if [ -n "${HOOKS_E2E_ABORT_PIDS:-}" ]; then
    abort_scenario
  fi
  commit_runs_static_gates
  green_push_lands
  red_push_is_aborted
  staged_is_refused_sorted
  untracked_py_is_refused
  untracked_root_inputs_are_refused
  untracked_planning_and_ignored_files_pass
  ignored_root_conftest_is_refused
  ignored_gnumakefile_is_refused
  unstaged_edit_restored_existing_branch
  unstaged_edit_restored_new_branch
  unstaged_edit_restored_root_push
  failed_gate_restores_edit
  head_refspec_passes
  not_head_is_refused
  deletion_runs_no_checks
  unstaged_config_is_refused
  unmerged_is_refused
  fail_fast_skips_test
  install_leaves_both_hooks_and_is_idempotent
  install_outside_a_checkout_skips
  install_with_hooks_path_fails
  install_from_a_worktree_uses_the_common_dir
  foreign_pre_commit_becomes_legacy
  foreign_pre_push_is_refused_untouched
  pre_push_symlink_is_refused_untouched
  pre_commit_symlink_is_refused_untouched
  foreign_pre_commit_with_legacy_is_refused_untouched
  interrupt_restores_edit INT
  interrupt_restores_edit TERM
  interrupt_restores_edit HUP
  harness_abort_reaps_every_group
  printf 'hooks-e2e: elapsed %ss\n' "$(( $(date +%s) - t0 ))"
  if [ "$FAILURES" -gt 0 ]; then
    printf 'hooks-e2e: %s case(s) failed\n' "$FAILURES" >&2
    return 1
  fi
  printf 'hooks-e2e: all cases passed\n'
}

main
