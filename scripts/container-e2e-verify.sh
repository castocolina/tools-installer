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
                          TRACER_REINSTALL_OK, TRACER_GSD_ABSENT_OK, TRACER_HOOKS_*, TRACER_SETTINGS_*
                          per step into pass2-transcript.log (appended, in order).
                          Tears the container down (rm -f) once all three succeed.
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
  home_listing >"$PHASE_DIR/home-before.txt"
  printf 'TRACER_HOME_BASELINE entries=%s\n' "$(wc -l <"$PHASE_DIR/home-before.txt" | tr -d ' ')"
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
  local line="$1" name category item regex
  [[ "$line" == "Summary — "* ]] || return 1
  for item in "INSTALLED:installed" "UPDATED:updated" "REPAIRED:repaired" "RECONFIGURED:reconfigured" "REINSTALLED:reinstalled" "SKIPPED:skipped" "BLOCKED:blocked" "MANUAL:manual" "FAILED:failed" "MISMATCHED:checksum mismatch" "DEP_FAILED:dependency failed" "NOT_ATTEMPTED:not attempted" "CRASHED:crashed"; do
    name="${item%%:*}"; category="${item#*:}"
    printf -v "PARSE_${name}" '%s' 0
    regex="(— |, )([0-9]+) ${category}(,|$)"
    if [[ "$line" =~ $regex ]]; then
      printf -v "PARSE_${name}" '%s' "${BASH_REMATCH[2]}"
    fi
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

# D-26: no global GSD tree in the tester's home after a pass. $1 names the pass.
# The probe runs inside the container and must end with its completion token, so a failed
# `ct exec` or `su` fails the tracer instead of reading as "absent" (review C-10). It checks
# the GSD paths the unit-test fingerprint watches; `-L` also catches a dangling link.
assert_gsd_absent() {
  local pass="$1" out line hit=0 done=0
  # shellcheck disable=SC2016 # $HOME expands in the tester's shell, not here
  if ! out="$(exec_tester 'for p in .claude/gsd-core .claude/.gsd-source .claude/gsd-file-manifest.json .gsd; do
  if [ -e "$HOME/$p" ] || [ -L "$HOME/$p" ]; then printf "PRESENT %s\n" "$HOME/$p"; fi
done
echo GSD_PROBE_DONE')"; then
    printf 'TRACER_GSD_PROBE_FAILED pass=%s\n' "$pass"
    return 1
  fi
  while IFS= read -r line; do
    case "$line" in
      "PRESENT "*)
        printf 'TRACER_GSD_PRESENT path=%s\n' "${line#PRESENT }"
        hit=1
        ;;
      GSD_PROBE_DONE) done=1 ;;
    esac
  done <<<"$out"
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_GSD_PROBE_FAILED pass=%s\n' "$pass"
    return 1
  fi
  if [[ "$hit" -eq 0 ]]; then
    printf 'TRACER_GSD_ABSENT_OK pass=%s\n' "$pass"
    return 0
  fi
  return 1
}

run_setup_as_tester() {
  local args="$1"
  # COLUMNS is forced wide so Rich's non-tty Console (default width 80) does
  # not wrap ordinary transcript output. Outcome rows can still fold at the
  # renderer's 100-cell budget; accumulate_summaries joins their continuations.
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
  ACC_RUNS=$((ACC_RUNS + 1))
  summary_line="$(grep -m1 '^Summary — ' "$file" || true)"
  if [[ -n "$summary_line" ]] \
    && printf '%s' "$summary_line" | grep -Eq "$SUMMARY_RE" \
    && parse_summary_line "$summary_line"; then
    ACC_SUMMARIES=$((ACC_SUMMARIES + 1))
    ACC_INSTALLED=$((ACC_INSTALLED + PARSE_INSTALLED))
    ACC_UPDATED=$((ACC_UPDATED + PARSE_UPDATED))
    ACC_SKIPPED=$((ACC_SKIPPED + PARSE_SKIPPED))
    ACC_FAILED=$((ACC_FAILED + PARSE_FAILED))
    ACC_DEP_FAILED=$((ACC_DEP_FAILED + PARSE_DEP_FAILED))
    ACC_MISMATCHED=$((ACC_MISMATCHED + PARSE_MISMATCHED))
    ACC_BLOCKED=$((ACC_BLOCKED + PARSE_BLOCKED))
    ACC_MANUAL=$((ACC_MANUAL + PARSE_MANUAL))
    ACC_NOT_ATTEMPTED=$((ACC_NOT_ATTEMPTED + PARSE_NOT_ATTEMPTED))
    ACC_CRASHED=$((ACC_CRASHED + PARSE_CRASHED))
  fi
  # Keep complete dependency-failed outcome rows across chunked runs. Only
  # outcome continuations (4+ spaces) join; two-space report lines end a row.
  local line dep_row="" continuation
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "PATH wiring could not be completed: "* \
      || "$line" == "PATH audit could not be completed: "* ]]; then
      ACC_POST_RUN_ERRORS=$((ACC_POST_RUN_ERRORS + 1))
    fi
    if [[ "$line" == *" dependency failed — "* ]]; then
      if [[ -n "$dep_row" ]]; then
        printf '%s\n' "$dep_row" >>"$ACC_DEP_LINES_FILE"
      fi
      dep_row="$line"
    elif [[ "$line" =~ ^[[:space:]]{4,} ]] && [[ -n "$dep_row" ]]; then
      continuation="${line#"${line%%[![:space:]]*}"}"
      dep_row="$dep_row $continuation"
    elif [[ -n "$dep_row" ]]; then
      printf '%s\n' "$dep_row" >>"$ACC_DEP_LINES_FILE"
      dep_row=""
    fi
  done <"$file"
  [[ -z "$dep_row" ]] || printf '%s\n' "$dep_row" >>"$ACC_DEP_LINES_FILE"
  sed -nE 's/^[^ ]+ +([^ ]+) +manual — (see the setup steps in the log|you run: .*)$/\1/p' \
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
    for blocker in ${blockers[@]+"${blockers[@]}"}; do
      blocker="${blocker#"${blocker%%[![:space:]]*}"}"
      blocker="${blocker%"${blocker##*[![:space:]]}"}"
      [[ "$blocker" == "an earlier failure" ]] && return 1
      [[ ",${manual_csv}," == *",${blocker},"* ]] || return 1
    done
  done <"$ACC_DEP_LINES_FILE"
  return 0
}

install_step_ok() {
  local setup_exit="$1"
  [[ "$ACC_RUNS" -gt 0 && "$ACC_SUMMARIES" -eq "$ACC_RUNS" ]] || return 1
  [[ "$ACC_FAILED" -eq 0 && "$ACC_MISMATCHED" -eq 0 \
    && "$ACC_NOT_ATTEMPTED" -eq 0 && "$ACC_CRASHED" -eq 0 ]] || return 1
  [[ "$ACC_POST_RUN_ERRORS" -eq 0 ]] || return 1
  { [[ "$ACC_DEP_FAILED" -eq 0 ]] || dependency_failures_explained; } || return 1
  [[ "$setup_exit" -eq 0 ]] && return 0
  [[ "$setup_exit" -eq 1 && "$ACC_DEP_FAILED" -gt 0 ]]
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
  ACC_RUNS=0
  ACC_SUMMARIES=0
  ACC_NOT_ATTEMPTED=0
  ACC_CRASHED=0
  ACC_POST_RUN_ERRORS=0
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

  printf 'PASS1_COUNTS installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s mismatched=%s blocked=%s manual=%s not_attempted=%s crashed=%s post_run_errors=%s summaries=%s runs=%s setup_exit=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_BLOCKED" "$ACC_MANUAL" \
    "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" "$ACC_POST_RUN_ERRORS" "$ACC_SUMMARIES" "$ACC_RUNS" "$setup_status"

  if install_step_ok "$setup_status"; then
    if [[ "$ACC_DEP_FAILED" -gt 0 ]]; then
      printf 'TRACER_CLEAN_INSTALL_OK (dependency_failed=%s fully explained by manual handoffs — see outcome rows above) installed=%s updated=%s skipped=%s failed=%s blocked=%s manual=%s\n' \
        "$ACC_DEP_FAILED" "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL"
    else
      printf 'TRACER_CLEAN_INSTALL_OK installed=%s updated=%s skipped=%s failed=%s blocked=%s manual=%s\n' \
        "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL"
    fi
    rm -f "$tmp" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    assert_receipt_present "$categories" || return 1
    assert_gsd_absent install || return 1
    return 0
  fi
  printf 'TRACER_CLEAN_INSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s not_attempted=%s crashed=%s post_run_errors=%s summaries=%s runs=%s setup_exit=%s\n' \
    "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" \
    "$ACC_POST_RUN_ERRORS" "$ACC_SUMMARIES" "$ACC_RUNS" "$setup_status"
  rm -f "$tmp" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  return 1
}

# The tester's HOME-relative listing, workspace pruned, empty dirs skipped (shortcut: a surviving
# empty must-clear or receipt dir goes unreported; list dirs to close it). `~` is expanded by the container shell.
home_listing() {
  local workspace="${TESTER_WORKSPACE#/home/tester/}"
  exec_tester 'cd ~ && find . -mindepth 1 \( -path "./'"$workspace"'" -prune \) -o \( -type d -empty \) -o -print | sed "s|^\./||" | LC_ALL=C sort'
}

# Before --uninstall --yes: the paths each receipt records (HOME-relative; paths outside
# HOME dropped) and the ids whose removal_plan is not `none`, both read by the installer's
# own code in the workspace. Writes receipt-paths.txt and removable-receipts.txt.
receipt_paths() {
  local workspace out
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
export PATH=\"\$HOME/.local/bin:\$PATH\"
cd ${workspace}
uv run --isolated --no-dev python -c '
from pathlib import Path
from installer import receipts
from installer.model import load_tools
from installer.uninstall import removal_plan
home = Path.home()
for path in sorted(receipts.default_receipts_dir().glob(\"*.json\")):
    receipt = receipts.read(path.stem)
    for artifact in (receipt.artifacts if receipt else ()):
        if artifact.path.is_relative_to(home):
            print(\"P \" + artifact.path.relative_to(home).as_posix())
bin_dir = home / \".local\" / \"bin\"
for tool in load_tools(\"installer/registry.toml\"):
    if removal_plan(tool, bin_dir).level != \"none\":
        print(\"R \" + tool.id)
'
")" || { printf 'TRACER_RECEIPT_PATHS_FAILED\n'; return 1; }
  printf '%s\n' "$out" | sed -n 's/^P //p' >"$PHASE_DIR/receipt-paths.txt"
  printf '%s\n' "$out" | sed -n 's/^R //p' >"$PHASE_DIR/removable-receipts.txt"
  printf 'TRACER_RECEIPT_PATHS_OK recorded=%s removable=%s\n' \
    "$(wc -l <"$PHASE_DIR/receipt-paths.txt" | tr -d ' ')" \
    "$(wc -l <"$PHASE_DIR/removable-receipts.txt" | tr -d ' ')"
}

# Host-side and read-only: one `allowed <path>` or `clear <path>` line per registry fact,
# HOME-relative. Imports the installer's own loader and marker table, never a copy.
registry_probe() {
  (cd "$REPO_ROOT" && uv run --no-sync python -c '
from installer.model import HARNESS_MARKER_DIRS, load_tools
tools = load_tools("installer/registry.toml")
def rel(entry):
    entry = entry.replace("{omz_root}/", ".oh-my-zsh/", 1)
    return entry[2:] if entry.startswith("~/") else entry
for tool in tools:
    for entry in tool.config_paths:
        print("allowed " + rel(entry).rstrip("/"))
for group in HARNESS_MARKER_DIRS.values():
    for entry in group:
        print("allowed " + entry)
for tool in tools:
    for method in tool.methods:
        if method.kind == "script":
            for entry in method.params.get("paths", ()):
                print("clear " + rel(entry).rstrip("/"))
')
}

# Config and harness prefixes, then the committed residue allowlist (reasons stripped).
allowed_prefixes() {
  registry_probe | sed -n 's/^allowed //p' || return 1
  sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$REPO_ROOT/scripts/e2e-residue-allowlist.txt"
}

# Declared script paths: a leftover there is a removal defect, never an allowlist case.
must_clear_paths() {
  registry_probe | sed -n 's/^clear //p' || return 1
}

# Pure (files in, lines out): prints the top-most leftover roots and exits 1 when any remain.
# A path at or under a receipt-recorded entry is a leftover whatever the baseline holds
# (review R1-25). A new path (not in the baseline) is a leftover when it lies at or under a
# must-clear entry, or when it is neither at, under, nor a parent of an allowed prefix (a new
# .config that only holds .config/gh is fine).
new_leftovers() {
  local before="$1" after="$2" allowed="$3" must_clear="$4" recorded="$5"
  local path entry flagged covered root kept
  local -a allowed_list=() must_list=() recorded_list=() leftovers=() roots=()
  while IFS= read -r entry; do [[ -n "$entry" ]] || continue; allowed_list+=("$entry"); done <"$allowed"
  while IFS= read -r entry; do [[ -n "$entry" ]] || continue; must_list+=("$entry"); done <"$must_clear"
  while IFS= read -r entry; do [[ -n "$entry" ]] || continue; recorded_list+=("$entry"); done <"$recorded"
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    for entry in ${recorded_list[@]+"${recorded_list[@]}"}; do
      if [[ "$path" == "$entry" || "$path" == "$entry"/* ]]; then leftovers+=("$path"); break; fi
    done
  done <"$after"
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    flagged=""
    for entry in ${must_list[@]+"${must_list[@]}"}; do
      if [[ "$path" == "$entry" || "$path" == "$entry"/* ]]; then flagged=1; break; fi
    done
    if [[ -z "$flagged" ]]; then
      covered=""
      for entry in ${allowed_list[@]+"${allowed_list[@]}"}; do
        if [[ "$path" == "$entry" || "$path" == "$entry"/* || "$entry" == "$path"/* ]]; then
          covered=1
          break
        fi
      done
      [[ -n "$covered" ]] || flagged=1
    fi
    if [[ -n "$flagged" ]]; then leftovers+=("$path"); fi
  done < <(LC_ALL=C comm -13 <(LC_ALL=C sort -u "$before") <(LC_ALL=C sort -u "$after"))
  # Sorted, an ancestor always precedes its descendants, so one pass keeps the roots.
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    kept=""
    for root in ${roots[@]+"${roots[@]}"}; do
      if [[ "$path" == "$root"/* ]]; then kept=1; break; fi
    done
    [[ -n "$kept" ]] || roots+=("$path")
  done < <(printf '%s\n' ${leftovers[@]+"${leftovers[@]}"} | LC_ALL=C sort -u)
  if [[ ${#roots[@]} -eq 0 ]]; then return 0; fi
  printf '%s\n' ${roots[@]+"${roots[@]}"}
  return 1
}

# After --uninstall --yes, against the baseline cmd_bootstrap took with no installer running.
# Prints TRACER_LEFTOVER path=... per top-most root (capped at 50, then _MORE), or _OK.
assert_no_leftovers() {
  local before="$PHASE_DIR/home-before.txt" after="$PHASE_DIR/home-after.txt"
  local recorded="$PHASE_DIR/receipt-paths.txt"
  local allowed="$PHASE_DIR/allowed-prefixes.txt" must_clear="$PHASE_DIR/must-clear-paths.txt"
  local roots path total=0
  if [[ ! -f "$before" || ! -f "$recorded" ]]; then
    printf 'TRACER_LEFTOVER_NO_BASELINE\n'
    return 1
  fi
  home_listing >"$after" || { printf 'TRACER_LEFTOVER_PROBE_FAILED\n'; return 1; }
  allowed_prefixes >"$allowed" || { printf 'TRACER_LEFTOVER_PROBE_FAILED\n'; return 1; }
  must_clear_paths >"$must_clear" || { printf 'TRACER_LEFTOVER_PROBE_FAILED\n'; return 1; }
  if roots="$(new_leftovers "$before" "$after" "$allowed" "$must_clear" "$recorded")"; then
    printf 'TRACER_LEFTOVER_OK\n'
    return 0
  fi
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    total=$((total + 1))
    if [[ "$total" -le 50 ]]; then printf 'TRACER_LEFTOVER path=%s\n' "$path"; fi
  done <<<"$roots"
  if [[ "$total" -gt 50 ]]; then printf 'TRACER_LEFTOVER_MORE count=%s\n' "$((total - 50))"; fi
  return 1
}

# After --uninstall --yes: every receipt the pre-uninstall plan could remove must be gone
# (review R1-24). Prints TRACER_RECEIPT_LEFT per survivor, else TRACER_RECEIPTS_GONE_OK.
assert_removed_receipts_gone() {
  local list="$PHASE_DIR/removable-receipts.txt" id receipt left=0 count=0
  if [[ ! -f "$list" ]]; then
    printf 'TRACER_RECEIPTS_UNKNOWN\n'
    return 1
  fi
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    if [[ ! "$id" =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
      printf 'TRACER_RECEIPTS_UNKNOWN\n'
      return 1
    fi
    count=$((count + 1))
    receipt="\$HOME/.local/state/tools-installer/receipts/${id}.json"
    if exec_tester "test -e ${receipt} || test -L ${receipt}"; then
      printf 'TRACER_RECEIPT_LEFT id=%s\n' "$id"
      left=1
    fi
  done <"$list"
  if [[ "$left" -eq 0 ]]; then
    printf 'TRACER_RECEIPTS_GONE_OK count=%s\n' "$count"
    return 0
  fi
  return 1
}

# Before --uninstall --yes: the hosts codegraph's receipt records under its MCP hook (read by the
# installer's own reader) and the HOME-relative config files that mention codegraph. Writes
# hook-hosts.txt and hook-files.txt; no receipt, no recorded host, or a recorded host with no
# config file at all fails.
hook_probe_before() {
  local out line no_receipt=0 hosts files workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
cd ~ && for p in .claude.json .claude .codex .config/opencode .cursor; do [ -e \"\$p\" ] && grep -rlI codegraph -- \"\$p\" || true; done | sed 's/^/F /'
cd ${workspace}
uv run --isolated --no-dev python -c '
from installer import receipts
receipt = receipts.read(\"codegraph\")
if receipt is None:
    print(\"N\")
for host in (receipt.hooks.get(\"codegraph-mcp-register\", ()) if receipt else ()):
    print(\"H \" + host)
'
")" || { printf 'TRACER_HOOKS_PROBE_FAILED\n'; return 1; }
  : >"$PHASE_DIR/hook-hosts.txt"
  : >"$PHASE_DIR/hook-files.txt"
  while IFS= read -r line; do
    case "$line" in
      "H "*) printf '%s\n' "${line#H }" >>"$PHASE_DIR/hook-hosts.txt" ;;
      "F "*) printf '%s\n' "${line#F }" >>"$PHASE_DIR/hook-files.txt" ;;
      N) no_receipt=1 ;;
    esac
  done <<<"$out"
  # This pass installs codegraph and agent hosts, so nothing registered is a regression.
  if [[ "$no_receipt" -eq 1 ]]; then
    printf 'TRACER_HOOKS_NOT_RECORDED reason=no-receipt\n'
    return 1
  fi
  hosts="$(paste -sd, - <"$PHASE_DIR/hook-hosts.txt")"
  if [[ -z "$hosts" ]]; then
    printf 'TRACER_HOOKS_NOT_RECORDED reason=no-hosts\n'
    return 1
  fi
  files="$(wc -l <"$PHASE_DIR/hook-files.txt" | tr -d ' ')"
  if [[ "$files" -eq 0 ]]; then
    printf 'TRACER_HOOK_FILES_MISSING hosts=%s\n' "$hosts"
    return 1
  fi
  printf 'TRACER_HOOKS_RECORDED hosts=%s files=%s\n' "$hosts" "$files"
}

# After --uninstall --yes: no file hook_probe_before recorded may still name codegraph. A
# missing file is clean. Prints TRACER_HOOK_LEFT path=... per survivor, else _UNREGISTERED_OK.
hook_probe_after() {
  local out line left=0 paths count
  if [[ ! -s "$PHASE_DIR/hook-hosts.txt" ]]; then
    printf 'TRACER_HOOKS_NOT_RECORDED\n'
    return 1
  fi
  paths="$(while IFS= read -r p; do printf '%q ' "$p"; done <"$PHASE_DIR/hook-files.txt")"
  out="$(exec_tester "cd ~ && for p in ${paths}; do if [ -e \"\$p\" ] && grep -q codegraph -- \"\$p\"; then printf 'LEFT %s\\n' \"\$p\"; fi; done")" \
    || { printf 'TRACER_HOOKS_UNREGISTER_PROBE_FAILED\n'; return 1; }
  count="$(wc -l <"$PHASE_DIR/hook-files.txt" | tr -d ' ')"
  while IFS= read -r line; do
    case "$line" in
      "LEFT "*) printf 'TRACER_HOOK_LEFT path=%s\n' "${line#LEFT }"; left=1 ;;
    esac
  done <<<"$out"
  [[ "$left" -eq 0 ]] || return 1
  printf 'TRACER_HOOKS_UNREGISTERED_OK count=%s\n' "$count"
}

# After the full install (rerun step): the install itself wrote each agent's tuning, so this probe
# writes nothing. For every agent in the installer's TUNING_GROUPS whose registry command is on PATH,
# each key of each group must hold the installer's value and be recorded in the agent's config-write
# ledger. claude, codex and copilot must be among those agents, and `copilot --version` must exit 0.
# The agents it checked, and per agent the settings file the config ledger lists as installer-created,
# go to $TESTER_WORKSPACE/.e2e-tuned-agents.json ({"agents": [...], "created": {agent: [path]}}) for
# settings_probe_revert: after the uninstall their commands are off PATH, so the revert probe never
# looks them up again.
# Prints TRACER_SETTINGS_INSTALLED_OK agents=N keys=N and TRACER_COPILOT_VERSION_OK, or one
# TRACER_SETTINGS_INSTALLED_MISSING / TRACER_SETTINGS_AGENT_MISSING / TRACER_COPILOT_VERSION_FAILED
# line per finding.
settings_probe_installed() {
  local out line failed=0 keys="" checked=" " agents=0 agent workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
cd ${workspace}
uv run --isolated --no-dev python -c '
import json, os, shutil
from pathlib import Path
from installer import agent_settings as s
from installer import model, receipts
home = Path.home()
search = os.pathsep.join([str(home / \".local/bin\"), str(home / \".opencode/bin\"), os.environ[\"PATH\"]])
tools = {t.id: t for t in model.load_tools(Path(model.__file__).with_name(\"registry.toml\"))}
checked = []
created = {}
count = 0
for agent, groups in s.TUNING_GROUPS.items():
    if shutil.which(tools[agent].cmd, path=search) is None:
        continue
    checked.append(agent)
    path = s.settings_file(agent, home=home, platform_os=\"linux\", environ=os.environ)
    text = path.read_text(encoding=\"utf-8\") if path.exists() else \"\"
    doc = s.parse_settings(text, s.AGENT_FORMATS[agent])
    ledger = receipts.read_ledger(agent)
    recorded = {(e.setting, e.key_path) for e in ledger.entries} if ledger else set()
    created[agent] = [f for f in ledger.created_files if f == str(path)] if ledger else []
    for group in groups:
        for key in s.setting_keys(agent, group, \"linux\"):
            count += 1
            holds = s.same_value(s.lookup(doc, key.path), key.value)
            if not holds or (group, key.path) not in recorded:
                print(\"M\", agent, \".\".join(key.path))
Path(\".e2e-tuned-agents.json\").write_text(json.dumps({\"agents\": checked, \"created\": created}), encoding=\"utf-8\")
for agent in checked:
    print(\"A\", agent)
print(\"K\", count)
'
")" || { printf 'TRACER_SETTINGS_INSTALLED_PROBE_FAILED\n'; return 1; }
  while IFS= read -r line; do
    case "$line" in
      "A "*) checked+="${line#A } "; agents=$((agents + 1)) ;;
      "M "*)
        agent="${line#M }"
        printf 'TRACER_SETTINGS_INSTALLED_MISSING agent=%s key=%s\n' "${agent%% *}" "${agent#* }"
        failed=1
        ;;
      "K "*) keys="${line#K }" ;;
    esac
  done <<<"$out"
  [[ -n "$keys" ]] || { printf 'TRACER_SETTINGS_INSTALLED_PROBE_FAILED\n'; return 1; }
  for agent in claude codex copilot; do
    if [[ "$checked" != *" $agent "* ]]; then
      printf 'TRACER_SETTINGS_AGENT_MISSING agent=%s\n' "$agent"
      failed=1
    fi
  done
  [[ "$failed" -ne 0 ]] || printf 'TRACER_SETTINGS_INSTALLED_OK agents=%s keys=%s\n' "$agents" "$keys"
  if [[ "$checked" == *" copilot "* ]]; then
    if exec_tester "\"\$HOME/.local/bin/copilot\" --version >/dev/null"; then
      printf 'TRACER_COPILOT_VERSION_OK\n'
    else
      printf 'TRACER_COPILOT_VERSION_FAILED\n'
      failed=1
    fi
  fi
  [[ "$failed" -eq 0 ]]
}

# After --uninstall --yes: for the agents settings_probe_installed persisted (never a fresh PATH
# lookup: the uninstall just removed copilot's link), every tuning key must be gone from the agent's
# settings file (a key the revert restored to the CLI's own default counts as gone), the file itself
# must be gone too when the install created it (unless a CLI default was restored into it), no
# config-write ledger may remain, and neither
# copilot's ~/.local/bin link nor its opt dir may remain. Prints TRACER_SETTINGS_REVERT_OK keys=N,
# or one TRACER_SETTINGS_REVERT_DIFF / TRACER_SETTINGS_FILE_LEFT / TRACER_SETTINGS_LEDGER_LEFT /
# TRACER_COPILOT_LEFT line per
# finding; a missing or unreadable agent list prints TRACER_SETTINGS_REVERT_PROBE_FAILED.
settings_probe_revert() {
  local out line failed=0 keys="" workspace agent
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
cd ${workspace}
uv run --isolated --no-dev python -c '
import json, os
from pathlib import Path
from installer import agent_settings as s
from installer import receipts
home = Path.home()
tuned = json.loads(Path(\".e2e-tuned-agents.json\").read_text(encoding=\"utf-8\"))
agents = tuned[\"agents\"]
count = 0
for agent in agents:
    path = s.settings_file(agent, home=home, platform_os=\"linux\", environ=os.environ)
    text = path.read_text(encoding=\"utf-8\") if path.exists() else \"\"
    doc = s.parse_settings(text, s.AGENT_FORMATS[agent])
    restored_any = False
    for group in s.TUNING_GROUPS[agent]:
        for key in s.setting_keys(agent, group, \"linux\"):
            count += 1
            now = s.lookup(doc, key.path)
            restored = key.cli_default is not s.ABSENT and s.same_value(now, key.cli_default)
            restored_any = restored_any or restored
            if now is not s.ABSENT and not restored:
                print(\"D\", agent, \".\".join(key.path))
    # Another owner (an agent installer, hook registration) may have made the file, and
    # it stays with its keys checked above; the installer owes the removal of only the files it
    # created, unless the revert restored a CLI default into it (cursor-agent), which keeps it.
    if path.exists() and str(path) in tuned[\"created\"].get(agent, []) and not restored_any:
        print(\"F\", agent)
    if (receipts.config_ledger_dir() / (agent + \".json\")).exists():
        print(\"L\", agent)
if \"copilot\" in agents:
    for name in (\".local/bin/copilot\", \".local/opt/copilot\"):
        if os.path.lexists(home / name):
            print(\"C\", name)
print(\"K\", count)
'
")" || { printf 'TRACER_SETTINGS_REVERT_PROBE_FAILED\n'; return 1; }
  while IFS= read -r line; do
    case "$line" in
      "D "*)
        agent="${line#D }"
        printf 'TRACER_SETTINGS_REVERT_DIFF agent=%s key=%s\n' "${agent%% *}" "${agent#* }"
        failed=1
        ;;
      "F "*) printf 'TRACER_SETTINGS_FILE_LEFT agent=%s\n' "${line#F }"; failed=1 ;;
      "L "*) printf 'TRACER_SETTINGS_LEDGER_LEFT agent=%s\n' "${line#L }"; failed=1 ;;
      "C "*) printf 'TRACER_COPILOT_LEFT path=%s\n' "${line#C }"; failed=1 ;;
      "K "*) keys="${line#K }" ;;
    esac
  done <<<"$out"
  [[ "$failed" -eq 0 ]] || return 1
  [[ -n "$keys" ]] || { printf 'TRACER_SETTINGS_REVERT_PROBE_FAILED\n'; return 1; }
  printf 'TRACER_SETTINGS_REVERT_OK keys=%s\n' "$keys"
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
  ACC_RUNS=0; ACC_SUMMARIES=0; ACC_NOT_ATTEMPTED=0; ACC_CRASHED=0; ACC_POST_RUN_ERRORS=0
  ACC_DEP_LINES_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"
  run_pass2_step "--all --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 && "$PASS2_STEP_STATUS" -ne 1 ]]; then
    rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    die "pass2 step 1 (rerun) crashed: setup.py exit $PASS2_STEP_STATUS"
  fi
  if ! install_step_ok "$PASS2_STEP_STATUS"; then
    printf 'TRACER_RERUN_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s not_attempted=%s crashed=%s post_run_errors=%s summaries=%s runs=%s setup_exit=%s\n' \
      "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" \
      "$ACC_POST_RUN_ERRORS" "$ACC_SUMMARIES" "$ACC_RUNS" "$PASS2_STEP_STATUS" >> "$log"
    rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    return 1
  fi
  rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  printf 'TRACER_RERUN_OK installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s blocked=%s manual=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL" >> "$log"

  # An absence check after uninstall proves nothing if the probe was never
  # installed. Require the binary and a receipt the parser accepts first.
  if ! assert_receipt_ready_for_removal >> "$log"; then
    return 1
  fi
  if ! receipt_paths >> "$log"; then
    return 1
  fi
  if ! hook_probe_before >> "$log"; then
    return 1
  fi
  if ! settings_probe_installed >> "$log"; then
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
  if ! assert_removed_receipts_gone >> "$log"; then
    return 1
  fi
  if ! assert_no_leftovers >> "$log"; then
    return 1
  fi
  if ! hook_probe_after >> "$log"; then
    return 1
  fi
  if ! settings_probe_revert >> "$log"; then
    return 1
  fi
  if ! assert_gsd_absent uninstall >> "$log"; then
    return 1
  fi

  # Step 3: reinstall — catches state the uninstall sweep left stray.
  ACC_INSTALLED=0; ACC_UPDATED=0; ACC_SKIPPED=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_MISMATCHED=0; ACC_BLOCKED=0; ACC_MANUAL=0
  ACC_RUNS=0; ACC_SUMMARIES=0; ACC_NOT_ATTEMPTED=0; ACC_CRASHED=0; ACC_POST_RUN_ERRORS=0
  ACC_DEP_LINES_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"
  run_pass2_step "--all --yes" "$log"
  if [[ "$PASS2_STEP_STATUS" -ne 0 && "$PASS2_STEP_STATUS" -ne 1 ]]; then
    rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    die "pass2 step 3 (reinstall) crashed: setup.py exit $PASS2_STEP_STATUS"
  fi
  if ! install_step_ok "$PASS2_STEP_STATUS"; then
    printf 'TRACER_REINSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s not_attempted=%s crashed=%s post_run_errors=%s summaries=%s runs=%s setup_exit=%s\n' \
      "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" \
      "$ACC_POST_RUN_ERRORS" "$ACC_SUMMARIES" "$ACC_RUNS" "$PASS2_STEP_STATUS" >> "$log"
    rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    return 1
  fi
  rm -f "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  printf 'TRACER_REINSTALL_OK installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s blocked=%s manual=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL" >> "$log"
  if ! assert_gsd_absent reinstall >> "$log"; then
    return 1
  fi

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
