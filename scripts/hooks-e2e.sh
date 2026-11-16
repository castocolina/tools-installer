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
	@if [ -e "\$(CURDIR)/LINT_FAIL" ]; then echo "lint failed"; exit 1; fi
	@touch "$marks/lint.ran"
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

main() {
  commit_runs_static_gates
  green_push_lands
  red_push_is_aborted
  if [ "$FAILURES" -gt 0 ]; then
    printf 'hooks-e2e: %s case(s) failed\n' "$FAILURES" >&2
    return 1
  fi
  printf 'hooks-e2e: all cases passed\n'
}

main
