#!/usr/bin/env bash
# container-e2e-verify.sh — Fedora-family container harness for D-04 / D-05.
#
# Bootstrap one long-lived named container (non-root, sudo-capable, Homebrew
# + uv) and run Pass 1: a clean install of the full registry.toml catalog
# through `uv run setup.py --all --yes`. Plan 12.3-03 extends this with Pass 2.
#
# First line of real logic sources scripts/detect-container-runtime.sh; a
# non-zero detection exit is propagated immediately. Never fall back to the
# host.

set -euo pipefail

CONTAINER_NAME="tools-installer-e2e-12-3"
IMAGE="fedora:latest"
PHASE_REL=".planning/phases/12.3-container-e2e-verification-of-the-reconciled-branch-real-end"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PHASE_DIR="$REPO_ROOT/$PHASE_REL"
TRANSCRIPT="$PHASE_DIR/pass1-transcript.log"

usage() {
  cat <<'EOF'
Usage: container-e2e-verify.sh <command> [options]

  bootstrap [--replace]   Create the named Fedora-family container, install
                          Homebrew-on-Linux prerequisites, create user tester,
                          bootstrap Homebrew + uv, uv sync. Prints
                          TRACER_HARNESS_READY_OK when ready.
  pass1                   Run uv run setup.py --all --yes as tester inside the
                          already-bootstrapped container. Prints
                          TRACER_CLEAN_INSTALL_OK on a clean (or explained)
                          pass. --categories NAME[,NAME...] chunks instead of
                          --all (same CLI flag the production entrypoint owns).
  resync                  Re-copy /repo (read-only host mount) onto
                          /home/tester/workspace. Required after any host-side
                          installer fix before re-running pass1.
  pass2                   D-04's rerun pass against the SAME container pass1
                          populated: a second --all --yes install over
                          already-installed state, a full --uninstall --yes
                          sweep, then a third --all --yes reinstall. Prints
                          TRACER_RERUN_OK / TRACER_UNINSTALL_OK /
                          TRACER_REINSTALL_OK per step into
                          pass2-transcript.log (appended, in order). Tears the
                          container down (rm -f) once all three succeed.
  -h, --help              Show this help

Never allocates a pseudo-TTY on exec (no -it/-t) so sys.stdin.isatty() is
False and the CLI takes its non-interactive branches.
EOF
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

# First line of real logic: detect. Non-zero exit propagates; never host-fallback.
eval "$( "$SCRIPT_DIR/detect-container-runtime.sh" )"
[[ -n "${CONTAINER_TOOL:-}" ]] || die "CONTAINER_TOOL unset after detection"

ct() {
  "$CONTAINER_TOOL" "$@"
}

exec_root() {
  ct exec "$CONTAINER_NAME" "$@"
}

# Login-shell as tester, never a TTY. $1 is the command string, expanded by
# the container shell only (callers must single-quote or escape host $()).
exec_tester() {
  ct exec "$CONTAINER_NAME" su - tester -c "$1"
}

ensure_phase_dir() {
  mkdir -p "$PHASE_DIR"
}

container_running() {
  ct ps --filter "name=^${CONTAINER_NAME}$" --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"
}

container_exists() {
  ct ps -a --filter "name=^${CONTAINER_NAME}$" --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"
}

start_container() {
  local replace="${1:-}"
  if container_exists; then
    if [[ "$replace" == "replace" ]]; then
      ct rm -f "$CONTAINER_NAME" >/dev/null
    elif container_running; then
      printf 'reusing running container %s\n' "$CONTAINER_NAME"
      return 0
    else
      printf 'starting existing container %s\n' "$CONTAINER_NAME"
      ct start "$CONTAINER_NAME" >/dev/null
      return 0
    fi
  fi
  ct run -d --name "$CONTAINER_NAME" \
    -v "$REPO_ROOT":/repo:ro,Z \
    "$IMAGE" sleep infinity >/dev/null
}

record_fedora_release() {
  local release
  release="$(exec_root cat /etc/fedora-release)"
  printf 'FEDORA_RELEASE=%s\n' "$release"
}

install_root_prereqs() {
  # Homebrew-on-Linux documented prerequisites, plus python3 as the Plan
  # 12.3-01 offline-fallback so uv sync does not fetch python-build-standalone.
  exec_root dnf install -y \
    @development-tools \
    procps-ng curl file git tar which sudo ca-certificates python3 \
    nodejs chromium
}

create_tester() {
  if exec_root id tester >/dev/null 2>&1; then
    printf 'user tester already exists\n'
  else
    exec_root useradd -m tester
  fi
  exec_root bash -c 'printf "%s\n" "tester ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/tester && chmod 440 /etc/sudoers.d/tester'
  exec_root mkdir -p /home/linuxbrew/.linuxbrew
  exec_root chown -R tester:tester /home/linuxbrew
}

copy_workspace() {
  exec_tester 'rm -rf /home/tester/workspace && cp -r /repo /home/tester/workspace && rm -rf /home/tester/workspace/.venv'
}

resync_workspace() {
  # -f: git objects are written read-only (mode 444); a plain overlay cp
  # cannot overwrite them even though tester owns them.
  exec_tester 'cp -rf /repo/. /home/tester/workspace/'
}

write_tester_path() {
  # su - is a login shell: Fedora's .bashrc returns immediately when not
  # interactive, so PATH must live in .bash_profile (sourced after .bashrc).
  exec_tester 'touch ~/.bash_profile
if ! grep -q linuxbrew ~/.bash_profile 2>/dev/null; then
  printf "%s\n" "eval \"\$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)\"" >> ~/.bash_profile
fi
if ! grep -q ".local/bin" ~/.bash_profile 2>/dev/null; then
  printf "%s\n" "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.bash_profile
fi
if ! grep -q linuxbrew ~/.bashrc 2>/dev/null; then
  printf "%s\n" "eval \"\$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)\"" >> ~/.bashrc
fi
if ! grep -q ".local/bin" ~/.bashrc 2>/dev/null; then
  printf "%s\n" "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.bashrc
fi
'
}

bootstrap_homebrew_and_uv() {
  exec_tester 'set -euo pipefail
if [[ ! -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
if [[ ! -x "$HOME/.local/bin/uv" ]] && ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
'
  write_tester_path
}

sync_workspace() {
  exec_tester 'set -euo pipefail
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
export PATH="$HOME/.local/bin:$PATH"
cd /home/tester/workspace
uv sync
uv run python -c "import installer"
'
}

print_harness_ready() {
  printf 'TRACER_HARNESS_READY_OK\n'
}

cmd_bootstrap() {
  local replace=""
  if [[ "${1:-}" == "--replace" ]]; then
    replace="replace"
  elif [[ -n "${1:-}" ]]; then
    die "unknown bootstrap option: $1"
  fi
  ensure_phase_dir
  start_container "$replace"
  record_fedora_release
  install_root_prereqs
  create_tester
  copy_workspace
  bootstrap_homebrew_and_uv
  sync_workspace
  print_harness_ready
}

cmd_resync() {
  container_running || die "container $CONTAINER_NAME is not running"
  resync_workspace
  sync_workspace
  printf 'TRACER_RESYNC_OK\n'
}

SUMMARY_RE='Installed: [0-9]+[[:space:]]+Already: [0-9]+[[:space:]]+Failed: [0-9]+[[:space:]]+Dependency failed: [0-9]+[[:space:]]+Checksum mismatch: [0-9]+[[:space:]]+No method: [0-9]+[[:space:]]+Manual setup required: [0-9]+'

# Parse one (possibly Rich-wrapped) render_summary blob into PARSE_* globals.
parse_summary_line() {
  local line="$1"
  PARSE_INSTALLED="$(printf '%s' "$line" | sed -n 's/.*Installed: \([0-9]*\).*/\1/p')"
  PARSE_ALREADY="$(printf '%s' "$line" | sed -n 's/.*Already: \([0-9]*\).*/\1/p')"
  PARSE_FAILED="$(printf '%s' "$line" | sed -n 's/.*Failed: \([0-9]*\).*/\1/p')"
  PARSE_DEP_FAILED="$(printf '%s' "$line" | sed -n 's/.*Dependency failed: \([0-9]*\).*/\1/p')"
  PARSE_MISMATCHED="$(printf '%s' "$line" | sed -n 's/.*Checksum mismatch: \([0-9]*\).*/\1/p')"
  PARSE_NO_METHOD="$(printf '%s' "$line" | sed -n 's/.*No method: \([0-9]*\).*/\1/p')"
  PARSE_MANUAL="$(printf '%s' "$line" | sed -n 's/.*Manual setup required: \([0-9]*\).*/\1/p')"
  [[ -n "$PARSE_INSTALLED" && -n "$PARSE_FAILED" ]]
}

run_setup_as_tester() {
  local args="$1"
  # COLUMNS is forced wide so Rich's non-tty Console (default width 80) never
  # wraps a one-line transcript output across two physical lines —
  # accumulate_summaries' SUMMARY_RE and its dependency/manual-required line
  # captures all require the whole line intact. 2000 gives real headroom over
  # the ~90-tool catalog's longest joined tool-id list, not just the summary
  # line that first surfaced this bug class.
  exec_tester "set -euo pipefail
eval \"\$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)\"
export PATH=\"\$HOME/.local/bin:\$PATH\"
export COLUMNS=2000
cd /home/tester/workspace
uv run setup.py ${args}
"
}

accumulate_summaries() {
  local file="$1"
  local blob
  # Rich's non-tty Console wraps at 80 cols, so render_summary's one logical
  # line may occupy two physical lines. Collapse whitespace and match once.
  blob="$(tr '\n' ' ' < "$file")"
  if printf '%s' "$blob" | grep -Eq "$SUMMARY_RE" && parse_summary_line "$blob"; then
    ACC_INSTALLED=$((ACC_INSTALLED + PARSE_INSTALLED))
    ACC_ALREADY=$((ACC_ALREADY + PARSE_ALREADY))
    ACC_FAILED=$((ACC_FAILED + PARSE_FAILED))
    ACC_DEP_FAILED=$((ACC_DEP_FAILED + PARSE_DEP_FAILED))
    ACC_MISMATCHED=$((ACC_MISMATCHED + PARSE_MISMATCHED))
    ACC_NO_METHOD=$((ACC_NO_METHOD + PARSE_NO_METHOD))
    ACC_MANUAL=$((ACC_MANUAL + PARSE_MANUAL))
  fi
  # Keep the raw lines a dependency-failure explanation check needs, since a
  # chunked (--categories) run overwrites $file every iteration.
  grep -E '^⚠ .+ skipped — dependency failed: ' "$file" >>"$ACC_SKIPPED_FILE" || true
  grep -E '^  manual setup required: ' "$file" >>"$ACC_MANUAL_NAMES_FILE" || true
}

# True when every tool named in a "skipped — dependency failed: X, Y" line is
# ALSO named in a "manual setup required: ..." line — i.e. the whole
# dependency-failure chain traces to a tool this installer can never
# auto-install (an interactive-auth handoff), not to an installer bug.
dependency_failures_explained() {
  [[ -s "$ACC_SKIPPED_FILE" ]] || return 0
  local manual_csv blocker_line blockers_csv blocker
  manual_csv="$(sed 's/^  manual setup required: //' "$ACC_MANUAL_NAMES_FILE" | paste -sd, -)"
  while IFS= read -r blocker_line; do
    blockers_csv="${blocker_line#*dependency failed: }"
    IFS=',' read -ra blockers <<<"$blockers_csv"
    for blocker in "${blockers[@]}"; do
      blocker="${blocker#"${blocker%%[![:space:]]*}"}"
      blocker="${blocker%"${blocker##*[![:space:]]}"}"
      [[ "$blocker" == "an earlier failure" ]] && return 1
      [[ ",${manual_csv}," == *",${blocker},"* ]] || return 1
    done
  done <"$ACC_SKIPPED_FILE"
  return 0
}

cmd_pass1() {
  container_running || die "container $CONTAINER_NAME is not running"
  local categories=""
  if [[ "${1:-}" == "--categories" ]]; then
    categories="${2:-}"
    [[ -n "$categories" ]] || die "--categories requires a value"
  elif [[ -n "${1:-}" ]]; then
    die "unknown pass1 option: $1"
  fi

  local tmp
  tmp="$(mktemp)"
  ACC_SKIPPED_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"

  ACC_INSTALLED=0
  ACC_ALREADY=0
  ACC_FAILED=0
  ACC_DEP_FAILED=0
  ACC_MISMATCHED=0
  ACC_NO_METHOD=0
  ACC_MANUAL=0
  local setup_status=0

  if [[ -n "$categories" ]]; then
    local cat
    local IFS=','
    for cat in $categories; do
      cat="${cat#"${cat%%[![:space:]]*}"}"
      cat="${cat%"${cat##*[![:space:]]}"}"
      [[ -n "$cat" ]] || continue
      # Interpolated verbatim into a shell script string executed via
      # `su -c` inside the container (run_setup_as_tester) — never accept a
      # value outside registry.toml's own category charset (lowercase
      # alnum + hyphen), or a value like `devtools;rm -rf /` would run as
      # tester (passwordless sudo) instead of being rejected.
      [[ "$cat" =~ ^[a-z0-9-]+$ ]] || die "invalid --categories value: $cat"
      printf '=== pass1 category=%s ===\n' "$cat"
      : > "$tmp"
      set +e
      run_setup_as_tester "--categories ${cat} --yes" > "$tmp" 2>&1
      local st=$?
      set -e
      cat "$tmp"
      accumulate_summaries "$tmp"
      if [[ "$st" -ne 0 && "$st" -ne 1 ]]; then
        setup_status="$st"
      elif [[ "$st" -eq 1 && "$setup_status" -eq 0 ]]; then
        setup_status=1
      fi
    done
  else
    : > "$tmp"
    set +e
    run_setup_as_tester "--all --yes" > "$tmp" 2>&1
    setup_status=$?
    set -e
    cat "$tmp"
    accumulate_summaries "$tmp"
  fi

  printf 'PASS1_COUNTS installed=%s already=%s failed=%s dependency_failed=%s mismatched=%s no_method=%s manual_required=%s setup_exit=%s\n' \
    "$ACC_INSTALLED" "$ACC_ALREADY" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_NO_METHOD" "$ACC_MANUAL" "$setup_status"

  local dep_failures_ok=0
  if [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; then
    dep_failures_ok=1
  fi

  if [[ "$ACC_FAILED" -eq 0 && "$dep_failures_ok" -eq 1 && "$ACC_MISMATCHED" -eq 0 ]]; then
    if [[ "$ACC_DEP_FAILED" -gt 0 ]]; then
      printf 'TRACER_CLEAN_INSTALL_OK (dependency_failed=%s fully explained by manual_required handoffs — see skipped/manual lines above) installed=%s failed=%s no_method=%s manual_required=%s\n' \
        "$ACC_DEP_FAILED" "$ACC_INSTALLED" "$ACC_FAILED" "$ACC_NO_METHOD" "$ACC_MANUAL"
    else
      printf 'TRACER_CLEAN_INSTALL_OK installed=%s failed=%s no_method=%s manual_required=%s\n' \
        "$ACC_INSTALLED" "$ACC_FAILED" "$ACC_NO_METHOD" "$ACC_MANUAL"
    fi
    rm -f "$tmp" "$ACC_SKIPPED_FILE" "$ACC_MANUAL_NAMES_FILE"
    return 0
  fi
  printf 'TRACER_CLEAN_INSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s\n' \
    "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED"
  rm -f "$tmp" "$ACC_SKIPPED_FILE" "$ACC_MANUAL_NAMES_FILE"
  return 1
}

# One --all --yes (or --uninstall --yes) step of pass2: run, append raw
# output to $log, accumulate summary counts (a no-op for --uninstall, which
# has no render_summary line), and report whether it was clean/explained.
# Sets PASS2_STEP_STATUS (setup.py's own exit) as a side effect.
run_pass2_step() {
  local args="$1" log="$2"
  local tmp
  tmp="$(mktemp)"
  set +e
  run_setup_as_tester "$args" > "$tmp" 2>&1
  PASS2_STEP_STATUS=$?
  set -e
  cat "$tmp" >> "$log"
  accumulate_summaries "$tmp"
  rm -f "$tmp"
}

cmd_pass2() {
  container_running || die "container $CONTAINER_NAME is not running"
  ensure_phase_dir
  local log="$PHASE_DIR/pass2-transcript.log"
  : > "$log"

  # Step 1: rerun — a second full install over already-installed state.
  ACC_INSTALLED=0; ACC_ALREADY=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_MISMATCHED=0; ACC_NO_METHOD=0; ACC_MANUAL=0
  ACC_SKIPPED_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"
  run_pass2_step "--all --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 && "$PASS2_STEP_STATUS" -ne 1 ]]; then
    rm -f "$ACC_SKIPPED_FILE" "$ACC_MANUAL_NAMES_FILE"
    die "pass2 step 1 (rerun) crashed: setup.py exit $PASS2_STEP_STATUS"
  fi
  local dep_ok=0
  { [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; } && dep_ok=1
  rm -f "$ACC_SKIPPED_FILE" "$ACC_MANUAL_NAMES_FILE"
  if [[ "$ACC_FAILED" -ne 0 || "$dep_ok" -ne 1 || "$ACC_MISMATCHED" -ne 0 ]]; then
    printf 'TRACER_RERUN_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s\n' \
      "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" >> "$log"
    return 1
  fi
  printf 'TRACER_RERUN_OK installed=%s already=%s failed=%s dependency_failed=%s\n' \
    "$ACC_INSTALLED" "$ACC_ALREADY" "$ACC_FAILED" "$ACC_DEP_FAILED" >> "$log"

  # Step 2: the full uninstall sweep. --uninstall has no render_summary line,
  # so only the exit code (and the transcript itself) is evidence here.
  run_pass2_step "--uninstall --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 ]]; then
    printf 'TRACER_UNINSTALL_INCOMPLETE exit=%s\n' "$PASS2_STEP_STATUS" >> "$log"
    return 1
  fi
  printf 'TRACER_UNINSTALL_OK\n' >> "$log"

  # Step 3: reinstall — catches state the uninstall sweep left stray.
  ACC_INSTALLED=0; ACC_ALREADY=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_MISMATCHED=0; ACC_NO_METHOD=0; ACC_MANUAL=0
  ACC_SKIPPED_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"
  run_pass2_step "--all --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 && "$PASS2_STEP_STATUS" -ne 1 ]]; then
    rm -f "$ACC_SKIPPED_FILE" "$ACC_MANUAL_NAMES_FILE"
    die "pass2 step 3 (reinstall) crashed: setup.py exit $PASS2_STEP_STATUS"
  fi
  dep_ok=0
  { [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; } && dep_ok=1
  rm -f "$ACC_SKIPPED_FILE" "$ACC_MANUAL_NAMES_FILE"
  if [[ "$ACC_FAILED" -ne 0 || "$dep_ok" -ne 1 || "$ACC_MISMATCHED" -ne 0 ]]; then
    printf 'TRACER_REINSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s\n' \
      "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" >> "$log"
    return 1
  fi
  printf 'TRACER_REINSTALL_OK installed=%s already=%s failed=%s dependency_failed=%s\n' \
    "$ACC_INSTALLED" "$ACC_ALREADY" "$ACC_FAILED" "$ACC_DEP_FAILED" >> "$log"

  ct rm -f "$CONTAINER_NAME" >/dev/null
  printf 'TRACER_CONTAINER_TEARDOWN_OK\n' >> "$log"
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    bootstrap) cmd_bootstrap "$@" ;;
    pass1) cmd_pass1 "$@" ;;
    pass2) cmd_pass2 "$@" ;;
    resync) cmd_resync "$@" ;;
    -h|--help) usage; exit 0 ;;
    "") usage; exit 2 ;;
    *) printf 'unknown command: %s\n' "$cmd" >&2; usage >&2; exit 2 ;;
  esac
}

main "$@"
