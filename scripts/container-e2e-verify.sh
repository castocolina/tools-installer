#!/usr/bin/env bash
# container-e2e-verify.sh — Fedora-family container harness for D-04 / D-05.
#
# Bootstrap one long-lived named container (non-root, sudo-capable, Homebrew
# + uv) and run Pass 1: a clean install of the full registry.toml catalog
# through `uv run --isolated --no-dev setup.py --all --yes`, then Pass 2 (rerun, uninstall,
# reinstall). `make e2e` runs `all`: every step, then removes the container.
#
# First line of real logic sources scripts/detect-container-runtime.sh; a
# non-zero detection exit is propagated immediately. Never fall back to the
# host.

set -euo pipefail

CONTAINER_NAME="tools-installer-e2e"
IMAGE="fedora:latest"

# The first registry tool whose first applicable method on Fedora amd64 is a
# raw github_release (category data). A constant: never interpolated from input.
RECEIPT_PROBE_TOOL=yq
RECEIPT_PROBE_CATEGORY=data
# The checkout run_setup_as_tester already cds into; the host test overrides it.
TESTER_WORKSPACE=/home/tester/workspace
# Homebrew binary evaluated by tester functions; host tests replace it with a stub.
BREW_BIN=/home/linuxbrew/.linuxbrew/bin/brew

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Transcripts are run evidence, not source: .e2e-artifacts/ is gitignored.
PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container"

usage() {
  cat <<'EOF'
Usage: container-e2e-verify.sh <command> [options]

  bootstrap [--replace]   Create the named Fedora-family container, install
                          Homebrew-on-Linux prerequisites, create user tester,
                          bootstrap Homebrew + uv, uv sync. Prints
                          TRACER_HARNESS_READY_OK when ready.
  pass1                   Run uv run --isolated --no-dev setup.py --all --yes as tester inside the
                          already-bootstrapped container. Prints
                          TRACER_CLEAN_INSTALL_OK on a clean (or explained)
                          pass. --categories NAME[,NAME...] chunks instead of
                          --all (same CLI flag the production entrypoint owns).
  resync                  Re-stream the host working tree onto
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
  all                     bootstrap --replace, pass1, pass2, then remove the
                          container whatever the outcome (what `make e2e` runs).
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
  ct run -d --name "$CONTAINER_NAME" "$IMAGE" sleep infinity >/dev/null
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

# Stream the working tree git sees (tracked + untracked, never ignored) into
# the workspace. Ignored caches (graphify-out/, .codegraph/, .venv/) hold
# owner-only files tester cannot read, and they are not the product anyway.
stream_worktree() {
  git -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard \
    | while IFS= read -r -d '' f; do [[ -e "$REPO_ROOT/$f" ]] && printf '%s\0' "$f"; done \
    | tar -C "$REPO_ROOT" --null -T - -cf - \
    | ct exec -i "$CONTAINER_NAME" su - tester -c 'mkdir -p /home/tester/workspace && tar -C /home/tester/workspace -xf -'
}

copy_workspace() {
  exec_tester 'rm -rf /home/tester/workspace'
  stream_worktree
}

resync_workspace() {
  stream_worktree
}

write_tester_path() {
  # su - is a login shell: Fedora's .bashrc returns immediately when not
  # interactive, so PATH must live in .bash_profile (sourced after .bashrc).
  # These rc files are sourced again by every nested shell, so the export
  # must be self-deduping. The two export PATH= lines in sync_workspace and
  # run_setup_as_tester are one-shot command prefixes in processes nothing
  # re-sources and are deliberately left alone.
  # su - resets the environment, so hand over the selected brew as a host-expanded prefix.
  exec_tester "BREW_BIN=${BREW_BIN}; "'touch ~/.bash_profile
if ! grep -q linuxbrew ~/.bash_profile 2>/dev/null; then
  printf "%s\n" "eval \"\$(${BREW_BIN} shellenv)\"" >> ~/.bash_profile
fi
if ! grep -q ".local/bin" ~/.bash_profile 2>/dev/null; then
  cat >> ~/.bash_profile <<"TI_PATH_GUARD"
case ":${PATH-}:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin${PATH:+:$PATH}";;esac
TI_PATH_GUARD
fi
if ! grep -q linuxbrew ~/.bashrc 2>/dev/null; then
  printf "%s\n" "eval \"\$(${BREW_BIN} shellenv)\"" >> ~/.bashrc
fi
if ! grep -q ".local/bin" ~/.bashrc 2>/dev/null; then
  cat >> ~/.bashrc <<"TI_PATH_GUARD"
case ":${PATH-}:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin${PATH:+:$PATH}";;esac
TI_PATH_GUARD
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
uv run --isolated --no-dev python -c "import installer"
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
  install_github_token
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

SUMMARY_RE='^Summary — (nothing selected|[0-9]+ (installed|updated|repaired|reconfigured|reinstalled|skipped|blocked|manual|failed|checksum mismatch|dependency failed|not attempted|crashed)(, [0-9]+ (installed|updated|repaired|reconfigured|reinstalled|skipped|blocked|manual|failed|checksum mismatch|dependency failed|not attempted|crashed))*)$'

# Parse render_run_summary's stable Summary — line into PARSE_* globals.
parse_summary_line() {
  local line="$1" name category item
  [[ "$line" == "Summary — "* ]] || return 1
  for item in "INSTALLED:installed" "UPDATED:updated" "REPAIRED:repaired" "RECONFIGURED:reconfigured" "REINSTALLED:reinstalled" "SKIPPED:skipped" "BLOCKED:blocked" "MANUAL:manual" "FAILED:failed" "MISMATCHED:checksum mismatch" "DEP_FAILED:dependency failed" "NOT_ATTEMPTED:not attempted" "CRASHED:crashed"; do
    name="${item%%:*}"; category="${item#*:}"
    printf -v "PARSE_${name}" '%s' "$(
      printf '%s' "$line" | sed -n "s/.*\\b\\([0-9][0-9]*\\) ${category}\\b.*/\\1/p; t; s/.*/0/p"
    )"
  done
  return 0
}

# True for a full run, or when one trimmed --categories element is the probe's.
receipt_check_applies() {
  local categories="$1" element
  [[ -z "$categories" ]] && return 0
  local IFS=','
  for element in $categories; do
    element="${element#"${element%%[![:space:]]*}"}"
    element="${element%"${element##*[![:space:]]}"}"
    [[ "$element" == "$RECEIPT_PROBE_CATEGORY" ]] && return 0
  done
  return 1
}

# $1 is the run's categories value. A chunked run without the probe category
# skips; a full run (empty) and a run that includes it must find the receipt.
assert_receipt_present() {
  if ! receipt_check_applies "$1"; then
    printf 'TRACER_RECEIPT_SKIPPED tool=%s category=%s\n' \
      "$RECEIPT_PROBE_TOOL" "$RECEIPT_PROBE_CATEGORY"
    return 0
  fi
  local receipt="\$HOME/.local/state/tools-installer/receipts/${RECEIPT_PROBE_TOOL}.json"
  if exec_tester "test -f ${receipt}"; then
    printf 'TRACER_RECEIPT_OK tool=%s\n' "$RECEIPT_PROBE_TOOL"
    return 0
  fi
  printf 'TRACER_RECEIPT_MISSING tool=%s\n' "$RECEIPT_PROBE_TOOL"
  return 1
}

# Both the probe binary and its receipt are gone. Names whatever is left.
assert_receipt_removed() {
  local binary="\$HOME/.local/bin/${RECEIPT_PROBE_TOOL}"
  local receipt="\$HOME/.local/state/tools-installer/receipts/${RECEIPT_PROBE_TOOL}.json"
  local left=""
  exec_tester "test ! -e ${binary} && test ! -L ${binary}" || left="${left} binary=${binary}"
  exec_tester "test ! -e ${receipt} && test ! -L ${receipt}" || left="${left} receipt=${receipt}"
  if [[ -z "$left" ]]; then
    printf 'TRACER_RECEIPT_REMOVAL_OK tool=%s\n' "$RECEIPT_PROBE_TOOL"
    return 0
  fi
  printf 'TRACER_RECEIPT_REMOVAL_INCOMPLETE tool=%s left:%s\n' "$RECEIPT_PROBE_TOOL" "$left"
  return 1
}

# Right before uninstall: the binary exists and the installer's own receipt
# parser accepts the file. A text match is not validation (review C2-L2).
assert_receipt_ready_for_removal() {
  local binary="\$HOME/.local/bin/${RECEIPT_PROBE_TOOL}"
  local receipt="\$HOME/.local/state/tools-installer/receipts/${RECEIPT_PROBE_TOOL}.json"
  local workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  if ! exec_tester "test -e ${binary} || test -L ${binary}"; then
    printf 'TRACER_RECEIPT_PRE_UNINSTALL_MISSING tool=%s missing=binary %s\n' \
      "$RECEIPT_PROBE_TOOL" "$binary"
    return 1
  fi
  if ! exec_tester "test -f ${receipt}"; then
    printf 'TRACER_RECEIPT_PRE_UNINSTALL_MISSING tool=%s missing=receipt %s\n' \
      "$RECEIPT_PROBE_TOOL" "$receipt"
    return 1
  fi
  local parser_status=0
  exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
export PATH=\"\$HOME/.local/bin:\$PATH\"
cd ${workspace}
uv run --isolated --no-dev python -c 'import sys; from installer import receipts; sys.exit(0 if receipts.read(sys.argv[1]) is not None else 1)' ${RECEIPT_PROBE_TOOL}
" || parser_status=$?
  if [[ "$parser_status" -eq 0 ]]; then
    printf 'TRACER_RECEIPT_PRE_UNINSTALL_OK tool=%s\n' "$RECEIPT_PROBE_TOOL"
    return 0
  fi
  printf 'TRACER_RECEIPT_PRE_UNINSTALL_MISSING tool=%s missing=valid receipt (parser exit %s)\n' \
    "$RECEIPT_PROBE_TOOL" "$parser_status"
  return 1
}

run_setup_as_tester() {
  local args="$1"
  # COLUMNS is forced wide so Rich's non-tty Console (default width 80) never
  # wraps a one-line transcript output across two physical lines —
  # accumulate_summaries parses render_run_summary's Summary — line; its
  # dependency-failure and manual outcome-row captures also require each line
  # intact. 2000 gives real headroom over the ~90-tool catalog's longest joined
  # tool-id list, not just the summary line that surfaced this.
  exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
export PATH=\"\$HOME/.local/bin:\$PATH\"
export COLUMNS=2000
# Container has no FUSE device; extract-and-run stands in for a desktop that mounts AppImages.
export APPIMAGE_EXTRACT_AND_RUN=1
if [[ -r \"\$HOME/.github-token\" ]]; then export GITHUB_TOKEN=\"\$(cat \"\$HOME/.github-token\")\"; fi
cd /home/tester/workspace
uv run --isolated --no-dev setup.py ${args}
"
}

# Optional: the host's GitHub token lifts the 60 requests/hour anonymous API
# limit that one full-catalog pass plus a retry exhausts. Streamed over stdin
# into a 0600 file so it never appears in argv or a transcript.
install_github_token() {
  local token="${GITHUB_TOKEN:-}"
  [[ -n "$token" ]] || token="$(gh auth token 2>/dev/null || true)"
  [[ -n "$token" ]] || return 0
  printf '%s' "$token" | ct exec -i "$CONTAINER_NAME" su - tester -c 'umask 077; cat > ~/.github-token'
}

accumulate_summaries() {
  local file="$1"
  local summary_line
  summary_line="$(grep -m1 '^Summary — ' "$file" || true)"
  if [[ -n "$summary_line" ]] \
    && printf '%s' "$summary_line" | grep -Eq "$SUMMARY_RE" \
    && parse_summary_line "$summary_line"; then
    ACC_INSTALLED=$((ACC_INSTALLED + PARSE_INSTALLED))
    ACC_UPDATED=$((ACC_UPDATED + PARSE_UPDATED))
    ACC_SKIPPED=$((ACC_SKIPPED + PARSE_SKIPPED))
    ACC_FAILED=$((ACC_FAILED + PARSE_FAILED))
    ACC_DEP_FAILED=$((ACC_DEP_FAILED + PARSE_DEP_FAILED))
    ACC_MISMATCHED=$((ACC_MISMATCHED + PARSE_MISMATCHED))
    ACC_BLOCKED=$((ACC_BLOCKED + PARSE_BLOCKED))
    ACC_MANUAL=$((ACC_MANUAL + PARSE_MANUAL))
  fi
  # Keep dependency-failed outcome rows in ACC_DEP_LINES_FILE for the
  # explanation check, since a chunked (--categories) run overwrites $file.
  grep -E ' dependency failed — ' "$file" >>"$ACC_DEP_LINES_FILE" || true
  sed -nE 's/^[^ ]+ +([^ ]+) +manual — see the setup steps in the log$/\1/p' \
    "$file" >>"$ACC_MANUAL_NAMES_FILE" || true
}

# True when every tool named after `dependency failed —` in an outcome row is
# ALSO named by a `manual — see the setup steps in the log` outcome row — i.e.
# the whole chain traces to a tool this installer cannot auto-install.
dependency_failures_explained() {
  [[ -s "$ACC_DEP_LINES_FILE" ]] || return 0
  local manual_csv blocker_line blockers_csv blocker
  manual_csv="$(paste -sd, - <"$ACC_MANUAL_NAMES_FILE")"
  while IFS= read -r blocker_line; do
    blockers_csv="${blocker_line#*dependency failed — }"
    IFS=',' read -ra blockers <<<"$blockers_csv"
    for blocker in "${blockers[@]}"; do
      blocker="${blocker#"${blocker%%[![:space:]]*}"}"
      blocker="${blocker%"${blocker##*[![:space:]]}"}"
      [[ "$blocker" == "an earlier failure" ]] && return 1
      [[ ",${manual_csv}," == *",${blocker},"* ]] || return 1
    done
  done <"$ACC_DEP_LINES_FILE"
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
  ACC_DEP_LINES_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"

  ACC_INSTALLED=0
  ACC_UPDATED=0
  ACC_SKIPPED=0
  ACC_FAILED=0
  ACC_DEP_FAILED=0
  ACC_MISMATCHED=0
  ACC_BLOCKED=0
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

  printf 'PASS1_COUNTS installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s mismatched=%s blocked=%s manual=%s setup_exit=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_BLOCKED" "$ACC_MANUAL" "$setup_status"

  local dep_failures_ok=0
  if [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; then
    dep_failures_ok=1
  fi

  if [[ "$ACC_FAILED" -eq 0 && "$dep_failures_ok" -eq 1 && "$ACC_MISMATCHED" -eq 0 ]]; then
    if [[ "$ACC_DEP_FAILED" -gt 0 ]]; then
      printf 'TRACER_CLEAN_INSTALL_OK (dependency_failed=%s fully explained by manual handoffs — see outcome rows above) installed=%s updated=%s skipped=%s failed=%s blocked=%s manual=%s\n' \
        "$ACC_DEP_FAILED" "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL"
    else
      printf 'TRACER_CLEAN_INSTALL_OK installed=%s updated=%s skipped=%s failed=%s blocked=%s manual=%s\n' \
        "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL"
    fi
    rm -f "$tmp" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    assert_receipt_present "$categories" || return 1
    return 0
  fi
  printf 'TRACER_CLEAN_INSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s\n' \
    "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED"
  rm -f "$tmp" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  return 1
}

# One --all --yes (or --uninstall --yes) step of pass2: run, append raw
# output to $log, accumulate summary counts (a no-op for --uninstall, which
# prints no Summary — line), and report whether it was clean/explained.
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
  ACC_INSTALLED=0; ACC_UPDATED=0; ACC_SKIPPED=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_MISMATCHED=0; ACC_BLOCKED=0; ACC_MANUAL=0
  ACC_DEP_LINES_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"
  run_pass2_step "--all --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 && "$PASS2_STEP_STATUS" -ne 1 ]]; then
    rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    die "pass2 step 1 (rerun) crashed: setup.py exit $PASS2_STEP_STATUS"
  fi
  local dep_ok=0
  { [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; } && dep_ok=1
  rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  if [[ "$ACC_FAILED" -ne 0 || "$dep_ok" -ne 1 || "$ACC_MISMATCHED" -ne 0 ]]; then
    printf 'TRACER_RERUN_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s\n' \
      "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" >> "$log"
    return 1
  fi
  printf 'TRACER_RERUN_OK installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s blocked=%s manual=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL" >> "$log"

  # An absence check after uninstall proves nothing if the probe was never
  # installed. Require the binary and a receipt the parser accepts first.
  if ! assert_receipt_ready_for_removal >> "$log"; then
    return 1
  fi

  # Step 2: the full uninstall sweep. --uninstall prints no Summary — line,
  # so only the exit code (and the transcript itself) is evidence here.
  run_pass2_step "--uninstall --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 ]]; then
    printf 'TRACER_UNINSTALL_INCOMPLETE exit=%s\n' "$PASS2_STEP_STATUS" >> "$log"
    return 1
  fi
  printf 'TRACER_UNINSTALL_OK\n' >> "$log"
  if ! assert_receipt_removed >> "$log"; then
    return 1
  fi

  # Step 3: reinstall — catches state the uninstall sweep left stray.
  ACC_INSTALLED=0; ACC_UPDATED=0; ACC_SKIPPED=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_MISMATCHED=0; ACC_BLOCKED=0; ACC_MANUAL=0
  ACC_DEP_LINES_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"
  run_pass2_step "--all --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 && "$PASS2_STEP_STATUS" -ne 1 ]]; then
    rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    die "pass2 step 3 (reinstall) crashed: setup.py exit $PASS2_STEP_STATUS"
  fi
  dep_ok=0
  { [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; } && dep_ok=1
  rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  if [[ "$ACC_FAILED" -ne 0 || "$dep_ok" -ne 1 || "$ACC_MISMATCHED" -ne 0 ]]; then
    printf 'TRACER_REINSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s\n' \
      "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" >> "$log"
    return 1
  fi
  printf 'TRACER_REINSTALL_OK installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s blocked=%s manual=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL" >> "$log"

  ct rm -f "$CONTAINER_NAME" >/dev/null
  printf 'TRACER_CONTAINER_TEARDOWN_OK\n' >> "$log"
}

cmd_all() {
  # Never leave the container behind, pass or fail (pass2 also removes it on success).
  trap 'ct rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true' EXIT
  cmd_bootstrap --replace
  cmd_pass1 | tee "$PHASE_DIR/pass1-transcript.log"
  cmd_pass2
  cat "$PHASE_DIR/pass2-transcript.log"
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    bootstrap) cmd_bootstrap "$@" ;;
    pass1) cmd_pass1 "$@" ;;
    pass2) cmd_pass2 "$@" ;;
    resync) cmd_resync "$@" ;;
    all) cmd_all "$@" ;;
    -h|--help) usage; exit 0 ;;
    "") usage; exit 2 ;;
    *) printf 'unknown command: %s\n' "$cmd" >&2; usage >&2; exit 2 ;;
  esac
}

main "$@"
