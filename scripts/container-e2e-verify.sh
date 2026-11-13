#!/usr/bin/env bash
# container-e2e-verify.sh — container harness for D-04 / D-05, on Fedora, Debian or Arch.
#
# Bootstrap one long-lived named container (non-root, sudo-capable, Homebrew
# + uv) and run Pass 1: a clean install of the full registry.toml catalog
# through `uv run --isolated --no-dev setup.py --all --yes`, then Pass 2 (rerun, uninstall,
# reinstall). `make e2e` runs `all`: every step, then removes the container.
# `--distro fedora|debian|arch` picks the table entry (fedora when absent); each distro
# runs in its own container `tools-installer-e2e-<distro>` with its own artifact dir
# `.e2e-artifacts/container-<distro>`, so a run never touches another distro's container.
#
# First line of real logic sources scripts/detect-container-runtime.sh; a
# non-zero detection exit is propagated immediately. Never fall back to the
# host.

set -euo pipefail

# One image per distro (the only per-distro constants besides the prerequisite lists below).
IMAGE_FEDORA=fedora:latest
IMAGE_DEBIAN=docker.io/library/debian:trixie
IMAGE_ARCH=docker.io/library/archlinux:latest

# The first registry tool whose first applicable method on Fedora amd64 is a
# raw github_release (category data). A constant: never interpolated from input.
RECEIPT_PROBE_TOOL=yq
RECEIPT_PROBE_CATEGORY=data
# The user every tester helper runs as, its home and the checkout run_setup_as_tester cds into.
# The nested target (cmd_nested) sets all three for the nested image's rootless user; the host
# test overrides them too.
TESTER_USER=tester
TESTER_HOME=/home/tester
TESTER_WORKSPACE=$TESTER_HOME/workspace
# The nested-podman target (orchestrator only, D-18): image, outer container and its rootless user.
NESTED_IMAGE=quay.io/podman/stable:latest
NESTED_CONTAINER_NAME=tools-installer-e2e-nested
NESTED_USER=podman
# A tiny image the inner podman pulls, runs and removes to prove nested podman works.
NESTED_PROBE_IMAGE=quay.io/podman/hello:latest
# Homebrew binary evaluated by tester functions; host tests replace it with a stub.
BREW_BIN=/home/linuxbrew/.linuxbrew/bin/brew
# herdr's plugin id (24-07) and where its probe keeps a copy of the binary for the after-uninstall check.
HERDR_PLUGIN_ID=herdr-setup.markers
HERDR_PROBE_COPY=/tmp/herdr-probe
# The kickstart.nvim commit and the no-LSP patch the installer applies to it; 24.1-03 owns both
# values (its test checks they agree with the Python constants). The patch path is workspace-relative.
NVIM_STARTER_PIN=8e35dbedb7966e3a95e1f26f9fc1179ab6c68db4
NVIM_STARTER_PATCH=installer/patches/kickstart-no-lsp.patch

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: container-e2e-verify.sh <command> [--distro fedora|debian|arch] [options]

  --distro NAME           Pick the distro table entry (default fedora): its image,
                          container tools-installer-e2e-NAME and artifact dir
                          .e2e-artifacts/container-NAME. Anywhere on the line.

  bootstrap [--replace]   Create the named distro container, install
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
  nvim-lsp                Orchestrator only, after pass1 on an already-bootstrapped
                          container: open a Python, Lua, TypeScript, Go and Java file in
                          the installer's own neovim starter and measure zero language
                          servers (no client, no server process, an empty Mason). Prints
                          TRACER_NVIM_LSP_OK. `all` runs it on fedora between pass1 and pass2.
  all                     bootstrap --replace, pass1, pass2, then remove the
                          container whatever the outcome (what `make e2e` runs).
  nested                  Orchestrator only, a time-boxed spike: start a disposable
                          quay.io/podman/stable container (--device /dev/fuse,
                          label=disable, never privileged), install zsh there and run the
                          terminal category as its rootless user for the one real Alacritty
                          build and herdr's default_shell write. Prints
                          TRACER_NESTED_PODMAN_OK / _BUILD_OK / _UNINSTALL_OK /
                          _HERDR_SHELL_OK / _HERDR_REVERT_OK / _TEARDOWN_OK, or
                          TRACER_NESTED_INFEASIBLE step=... when nested podman cannot run.
  schedules [--direct] [--keep-image]
                          Orchestrator only: a disposable Fedora 44 container with systemd as
                          PID 1 and the tester's user manager. The installer's own engine writes
                          the Schedules units, each built-in runs once through its runner, a held
                          lock is skipped, a calendar slot fires and a missed one catches up once,
                          then the units and stamps are turned off. Prints TRACER_SCHEDULE_*
                          verdicts, or TRACER_SCHEDULES_INFEASIBLE step=... when the box cannot
                          start. --direct is the fallback for a host without systemd containers:
                          a plain container that runs each job's command without units.
                          --keep-image keeps the built image.
  -h, --help              Show this help

Never allocates a pseudo-TTY on exec (no -it/-t) so sys.stdin.isatty() is
False and the CLI takes its non-interactive branches.
EOF
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

# Selects the distro table entry: DISTRO, IMAGE, CONTAINER_NAME and PHASE_DIR. Transcripts are
# run evidence, not source: .e2e-artifacts/ is gitignored. An unknown name exits 2 with the usage.
select_distro() {
  case "$1" in
    fedora) IMAGE="$IMAGE_FEDORA" ;;
    debian) IMAGE="$IMAGE_DEBIAN" ;;
    arch) IMAGE="$IMAGE_ARCH" ;;
    *)
      printf 'error: unknown distro: %s (expected fedora, debian or arch)\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  DISTRO="$1"
  CONTAINER_NAME="tools-installer-e2e-$1"
  PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-$1"
}
select_distro fedora

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
  ct exec "$CONTAINER_NAME" su - "$TESTER_USER" -c "$1"
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

distro_release_record() {
  local release
  case "$DISTRO" in
    fedora) release="$(exec_root cat /etc/fedora-release)" ;;
    debian) release="$(exec_root cat /etc/debian_version)" ;;
    arch)
      release="$(exec_root cat /etc/os-release | sed -n 's/^PRETTY_NAME=//p' | tr -d '"')"
      ;;
  esac
  printf 'DISTRO_RELEASE=%s:%s\n' "$DISTRO" "$release"
}

# Homebrew-on-Linux documented prerequisites, plus sudo, git, python3 (the Plan 12.3-01
# offline fallback so uv sync does not fetch python-build-standalone), nodejs and chromium.
# Debian and Arch ship npm as its own package (Fedora's nodejs pulls it in), and vendor
# install scripts may call npm/npx. No distro gets zsh: with it the terminal sync would
# write a WezTerm region that outlives the full uninstall (nested target covers zsh).
install_root_prereqs() {
  case "$DISTRO" in
    fedora)
      exec_root dnf install -y \
        @development-tools \
        procps-ng curl file git tar which sudo ca-certificates python3 \
        nodejs chromium
      ;;
    debian)
      exec_root apt-get update
      exec_root env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential procps curl file git ca-certificates sudo python3 nodejs npm chromium
      ;;
    arch)
      exec_root pacman -Syu --noconfirm --needed \
        base-devel procps-ng curl file git sudo which tar python nodejs npm chromium
      ;;
  esac
}

create_tester() {
  if exec_root id "$TESTER_USER" >/dev/null 2>&1; then
    printf 'user %s already exists\n' "$TESTER_USER"
  else
    # With the defaults this is `useradd -m -s /bin/bash tester`: -s /bin/bash on every distro,
    # because Debian's useradd defaults to /bin/sh, where the probes' `[[`, pipefail and the
    # ~/.bash_profile PATH wiring would fail.
    exec_root useradd -m -s /bin/bash "$TESTER_USER"
  fi
  exec_root bash -c "printf \"%s\n\" \"${TESTER_USER} ALL=(ALL) NOPASSWD:ALL\" > /etc/sudoers.d/${TESTER_USER} && chmod 440 /etc/sudoers.d/${TESTER_USER}"
  exec_root mkdir -p /home/linuxbrew/.linuxbrew
  exec_root chown -R "${TESTER_USER}:${TESTER_USER}" /home/linuxbrew
}

# Stream the working tree git sees (tracked + untracked, never ignored) into
# the workspace. Ignored caches (graphify-out/, .codegraph/, .venv/) hold
# owner-only files tester cannot read, and they are not the product anyway.
stream_worktree() {
  local workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  git -C "$REPO_ROOT" ls-files -z --cached --others --exclude-standard \
    | while IFS= read -r -d '' f; do [[ -e "$REPO_ROOT/$f" ]] && printf '%s\0' "$f"; done \
    | tar -C "$REPO_ROOT" --null -T - -cf - \
    | ct exec -i "$CONTAINER_NAME" su - "$TESTER_USER" -c "mkdir -p ${workspace} && tar -C ${workspace} -xf -"
}

copy_workspace() {
  local workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  exec_tester "rm -rf ${workspace}"
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
  # shellcheck disable=SC2016 # the single-quoted part expands in the tester's shell
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

bootstrap_uv() {
  # shellcheck disable=SC2016 # $HOME expands in the tester's shell
  exec_tester 'set -euo pipefail
if [[ ! -x "$HOME/.local/bin/uv" ]] && ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
'
}

bootstrap_homebrew_and_uv() {
  # shellcheck disable=SC2016 # $() expands in the tester's shell
  exec_tester 'set -euo pipefail
if [[ ! -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
'
  bootstrap_uv
  write_tester_path
}

sync_workspace() {
  local workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
export PATH=\"\$HOME/.local/bin:\$PATH\"
cd ${workspace}
uv sync
uv run --isolated --no-dev python -c \"import installer\"
"
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
  distro_release_record
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
  local args="$1" workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
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
cd ${workspace}
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
  printf '%s' "$token" | ct exec -i "$CONTAINER_NAME" su - "$TESTER_USER" -c 'umask 077; cat > ~/.github-token'
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
    ACC_REPAIRED=$((ACC_REPAIRED + PARSE_REPAIRED))
    ACC_RECONFIGURED=$((ACC_RECONFIGURED + PARSE_RECONFIGURED))
    ACC_REINSTALLED=$((ACC_REINSTALLED + PARSE_REINSTALLED))
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

# The rerun pass (SPEC R8, D-25) may report only skipped or blocked rows, plus the manual rows pass 1
# already reported. Any installed, updated, repaired, reconfigured, reinstalled, failed, checksum
# mismatch or dependency failed row fails it, even a dependency failure that pass 1's explained-
# dependency rule would accept: that rule belongs to pass 1 and is never consulted here. Reads the
# ACC_* counters and manual names of the rerun and the manual set pass 1 wrote to $PHASE_DIR.
rerun_step_ok() {
  local baseline="$PHASE_DIR/pass1-manual.txt" now added="" missing=""
  now="$(mktemp)"
  LC_ALL=C sort -u "$ACC_MANUAL_NAMES_FILE" >"$now"
  if [[ -f "$baseline" ]]; then
    added="$(LC_ALL=C comm -13 <(LC_ALL=C sort -u "$baseline") "$now" | paste -sd, -)"
    missing="$(LC_ALL=C comm -23 <(LC_ALL=C sort -u "$baseline") "$now" | paste -sd, -)"
  else
    missing="pass1-manual.txt"
  fi
  rm -f "$now"
  if [[ "$ACC_INSTALLED" -eq 0 && "$ACC_UPDATED" -eq 0 && "$ACC_REPAIRED" -eq 0 \
    && "$ACC_RECONFIGURED" -eq 0 && "$ACC_REINSTALLED" -eq 0 && "$ACC_FAILED" -eq 0 \
    && "$ACC_MISMATCHED" -eq 0 && "$ACC_DEP_FAILED" -eq 0 \
    && -z "$added" && -z "$missing" ]]; then
    return 0
  fi
  printf 'TRACER_RERUN_UNEXPECTED installed=%s updated=%s repaired=%s reconfigured=%s reinstalled=%s failed=%s mismatched=%s dependency_failed=%s manual_added=%s manual_missing=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_REPAIRED" "$ACC_RECONFIGURED" "$ACC_REINSTALLED" \
    "$ACC_FAILED" "$ACC_MISMATCHED" "$ACC_DEP_FAILED" "$added" "$missing"
  return 1
}

# One TRACER_DISTRO_BLOCKED line per tool id across the BLOCKED rows of a transcript (the plan row
# and the outcome row of one tool print once; the first reason seen wins). Never fails the run.
list_blocked_rows() {
  sed -nE 's/^[^ ]+ +([^ ]+) +blocked — (.*)$/\1 \2/p' "$1" \
    | awk -v distro="$DISTRO" '!seen[$1]++ { id = $1; sub(/^[^ ]+ /, ""); printf "TRACER_DISTRO_BLOCKED distro=%s tool=%s reason=%s\n", distro, id, $0 }'
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

  # A chunked run installs a subset, so the rerun (always --all) could never match it: pass2
  # refuses while this marker exists.
  ensure_phase_dir
  if [[ -n "$categories" ]]; then
    printf '%s\n' "$categories" >"$PHASE_DIR/pass1-chunked.txt"
  else
    rm -f "$PHASE_DIR/pass1-chunked.txt"
  fi

  local tmp all_runs
  tmp="$(mktemp)"
  all_runs="$(mktemp)"
  ACC_DEP_LINES_FILE="$(mktemp)"
  ACC_MANUAL_NAMES_FILE="$(mktemp)"

  ACC_INSTALLED=0
  ACC_UPDATED=0
  ACC_REPAIRED=0
  ACC_RECONFIGURED=0
  ACC_REINSTALLED=0
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
      cat "$tmp" >>"$all_runs"
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
    cat "$tmp" >>"$all_runs"
    accumulate_summaries "$tmp"
  fi

  printf 'PASS1_COUNTS installed=%s updated=%s skipped=%s failed=%s dependency_failed=%s mismatched=%s blocked=%s manual=%s not_attempted=%s crashed=%s post_run_errors=%s summaries=%s runs=%s setup_exit=%s\n' \
    "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_BLOCKED" "$ACC_MANUAL" \
    "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" "$ACC_POST_RUN_ERRORS" "$ACC_SUMMARIES" "$ACC_RUNS" "$setup_status"

  # Pass 2's rerun may repeat exactly these manual handoffs and nothing else (rerun_step_ok).
  ensure_phase_dir
  LC_ALL=C sort -u "$ACC_MANUAL_NAMES_FILE" >"$PHASE_DIR/pass1-manual.txt"
  list_blocked_rows "$all_runs"

  if install_step_ok "$setup_status"; then
    # Misconfigured means nothing was available at all; a re-run of a good pass 1 skips everything.
    if [[ "$((ACC_INSTALLED + ACC_SKIPPED + ACC_MANUAL))" -eq 0 ]]; then
      printf 'TRACER_DISTRO_MISCONFIGURED distro=%s\n' "$DISTRO"
      rm -f "$tmp" "$all_runs" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
      return 1
    fi
    if [[ "$ACC_DEP_FAILED" -gt 0 ]]; then
      printf 'TRACER_CLEAN_INSTALL_OK (dependency_failed=%s fully explained by manual handoffs — see outcome rows above) installed=%s updated=%s skipped=%s failed=%s blocked=%s manual=%s\n' \
        "$ACC_DEP_FAILED" "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL"
    else
      printf 'TRACER_CLEAN_INSTALL_OK installed=%s updated=%s skipped=%s failed=%s blocked=%s manual=%s\n' \
        "$ACC_INSTALLED" "$ACC_UPDATED" "$ACC_SKIPPED" "$ACC_FAILED" "$ACC_BLOCKED" "$ACC_MANUAL"
    fi
    rm -f "$tmp" "$all_runs" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
    assert_receipt_present "$categories" || return 1
    assert_gsd_absent install || return 1
    return 0
  fi
  printf 'TRACER_CLEAN_INSTALL_INCOMPLETE failed=%s dependency_failed=%s mismatched=%s not_attempted=%s crashed=%s post_run_errors=%s summaries=%s runs=%s setup_exit=%s\n' \
    "$ACC_FAILED" "$ACC_DEP_FAILED" "$ACC_MISMATCHED" "$ACC_NOT_ATTEMPTED" "$ACC_CRASHED" \
    "$ACC_POST_RUN_ERRORS" "$ACC_SUMMARIES" "$ACC_RUNS" "$setup_status"
  rm -f "$tmp" "$all_runs" "$ACC_DEP_LINES_FILE" "$ACC_MANUAL_NAMES_FILE"
  return 1
}

# The tester's HOME-relative listing, workspace pruned, empty dirs skipped (shortcut: a surviving
# empty must-clear or receipt dir goes unreported; list dirs to close it). `~` is expanded by the container shell.
home_listing() {
  local workspace="${TESTER_WORKSPACE#"$TESTER_HOME"/}"
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
# installer's own reader) and the HOME-relative config files that mention codegraph (not the Claude
# CLI's own ~/.claude/backups copies of .claude.json, which the installer never owns). Writes
# hook-hosts.txt and hook-files.txt; no receipt, no recorded host, or a recorded host with no
# config file at all fails.
hook_probe_before() {
  local out line no_receipt=0 hosts files workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
cd ~ && for p in .claude.json .claude .codex .config/opencode .cursor; do [ -e \"\$p\" ] && grep -rlI codegraph -- \"\$p\" || true; done | sed '/^\.claude\/backups\//d; s/^/F /'
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
herdr = receipts.read(\"herdr\")
herdr_hosts = list(herdr.hooks.get(\"herdr-integration\", ())) if herdr else []
Path(\".e2e-tuned-agents.json\").write_text(json.dumps({\"agents\": checked, \"created\": created, \"herdr_hosts\": herdr_hosts}), encoding=\"utf-8\")
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
# or one TRACER_SETTINGS_REVERT_DIFF / TRACER_SETTINGS_FILE_LEFT (with the left document as
# residue=, at most 200 characters) / TRACER_SETTINGS_LEDGER_LEFT /
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
def pruned(value):
    if not isinstance(value, dict):
        return value
    kept = {k: pruned(v) for k, v in value.items()}
    return {k: v for k, v in kept.items() if v not in ({}, [])}
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
        residue = json.dumps(doc, sort_keys=True, separators=(\",\", \":\"), default=str)
        # herdr integration uninstall leaves empty containers (and codex a hooks feature flag) in a
        # file we created: that is its residue, not ours, unless a herdr marker is still in the text.
        # Only an agent herdr recorded as a host may carry it, and every use prints an R line.
        if agent == \"codex\" and doc == {\"features\": {\"hooks\": True}}:
            print(\"R\", agent, \"features.hooks\")
        elif doc and not pruned(doc) and \"herdr-agent-state\" not in text and agent in tuned.get(\"herdr_hosts\", []):
            print(\"R\", agent, \"empty-containers\")
        else:
            print(\"F\", agent, residue[:200])
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
      "F "*)
        agent="${line#F }"
        printf 'TRACER_SETTINGS_FILE_LEFT agent=%s residue=%s\n' "${agent%% *}" "${agent#* }"
        failed=1
        ;;
      "R "*)
        agent="${line#R }"
        printf 'TRACER_HERDR_RESIDUE agent=%s key=%s\n' "${agent%% *}" "${agent#* }"
        ;;
      "L "*) printf 'TRACER_SETTINGS_LEDGER_LEFT agent=%s\n' "${line#L }"; failed=1 ;;
      "C "*) printf 'TRACER_COPILOT_LEFT path=%s\n' "${line#C }"; failed=1 ;;
      "K "*) keys="${line#K }" ;;
    esac
  done <<<"$out"
  [[ "$failed" -eq 0 ]] || return 1
  [[ -n "$keys" ]] || { printf 'TRACER_SETTINGS_REVERT_PROBE_FAILED\n'; return 1; }
  printf 'TRACER_SETTINGS_REVERT_OK keys=%s\n' "$keys"
}

# herdr (ONB-01). The facts come from the container as one prefixed line each (see the two probes
# below) and the verdicts are decided here, so a host test can drive them with fixture lines.
# The three sidebar keys herdr's hook writes into its config.toml (24-02, the ledger group `sidebar`).
herdr_sidebar_keys() {
  printf '%s\n' ui.sidebar.agents.rows ui.sidebar.agents.row_gap ui.sidebar.spaces.rows
}

# `herdr plugin list --json` output on stdin -> `listed`, `absent` or `unreadable`, read the way
# installer/postinstall.py::_plugin_listed does (result.plugins[].plugin_id). Anything that is not
# that JSON shape, an error echoing the plugin id included, is `unreadable`, never `listed`.
herdr_plugin_state() {
  python3 -c 'import json, sys
try:
    plugins = json.load(sys.stdin)["result"]["plugins"]
    print("listed" if any(p["plugin_id"] == sys.argv[1] for p in plugins) else "absent")
except (ValueError, KeyError, TypeError):
    print("unreadable")' "$HERDR_PLUGIN_ID"
}

# `herdr integration status` text on stdin -> `target|state` lines. The command always exits 0
# (herdr v0.9.5 src/cli/integration.rs), and an experimental target reads `letta (experimental): ...`.
herdr_status_parse() {
  sed -nE 's/^([^ :]+)( \(experimental\))?: (not installed|current|needs repair).*$/\1|\3/p'
}

# Raw status text on stdin: every target must read `not installed`. Prints one NOT_CURRENT line per
# target that does not, or STATUS_UNREADABLE when nothing parsed.
herdr_status_clean() {
  local parsed line clean=0
  parsed="$(herdr_status_parse)"
  if [[ -z "$parsed" ]]; then
    printf 'TRACER_HERDR_STATUS_UNREADABLE\n'
    return 1
  fi
  while IFS= read -r line; do
    if [[ "${line#*|}" != "not installed" ]]; then
      printf 'TRACER_HERDR_NOT_CURRENT target=%s\n' "${line%%|*}"
      clean=1
    fi
  done <<<"$parsed"
  return "$clean"
}

# Fact lines on stdin from herdr_probe_installed: `H <hook id>`, `N` (no receipt), `S <status line>`,
# `Y <plugin list --json output>`, `P <present harness> <herdr target>`, `C <sidebar key present>`, `DS <default_shell value>`, `E <ledger entry>`,
# `W <skill path>` and the closing `D`. No zsh is installed in the distro containers, so herdr must
# have written neither a default_shell key nor a default-shell ledger entry (D-08b, R1-19).
herdr_installed_verdict() {
  local line hosts="" sidebar=0 no_receipt=0 done=0 plugin="" failed=0 shell=""
  local keys_seen=" " status="" parsed host state key rest present=""
  while IFS= read -r line; do
    case "$line" in
      N) no_receipt=1 ;;
      "H sidebar-markers") sidebar=1 ;;
      "H "*) hosts="${hosts:+$hosts,}${line#H }" ;;
      "S "*) status+="${line#S }"$'\n' ;;
      "Y "*) plugin="$(printf '%s' "${line#Y }" | herdr_plugin_state)" ;;
      "P "*) present+="${line#P }"$'\n' ;;
      "C "*) keys_seen+="${line#C } " ;;
      "DS "*) shell="${line#DS }" ;;
      "E default-shell "*)
        rest="${line#E default-shell }"
        [[ -n "$shell" ]] || shell="${rest#* }"
        ;;
      "W "*)
        printf 'TRACER_HERDR_SKILL_FOUND path=%s\n' "${line#W }"
        failed=1
        ;;
      D) done=1 ;;
    esac
  done
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_HERDR_PROBE_FAILED\n'
    return 1
  fi
  if [[ "$no_receipt" -eq 1 ]]; then
    printf 'TRACER_HERDR_NOT_RECORDED reason=no-receipt\n'
    failed=1
  else
    if [[ "$sidebar" -eq 0 ]]; then
      printf 'TRACER_HERDR_NOT_RECORDED reason=no-sidebar\n'
      failed=1
    fi
    if [[ -z "$hosts" ]]; then
      printf 'TRACER_HERDR_NOT_RECORDED reason=no-hosts\n'
      failed=1
    fi
  fi
  parsed="$(printf '%s' "$status" | herdr_status_parse)"
  local -a host_list=()
  IFS=',' read -ra host_list <<<"$hosts"
  for host in ${host_list[@]+"${host_list[@]}"}; do
    state="$(printf '%s\n' "$parsed" | awk -F'|' -v target="$host" '$1 == target { print $2; exit }')"
    if [[ "$state" != "current" ]]; then
      printf 'TRACER_HERDR_NOT_CURRENT target=%s\n' "$host"
      failed=1
    fi
  done
  # Every present host the installer decides on (`P <harness> <herdr target>`) must be recorded,
  # unless herdr already reads it `current` (the user's own setup, left alone). A target herdr does
  # not list at all is not registered by the installer either.
  local harness
  while read -r harness host; do
    [[ -n "$harness" ]] || continue
    [[ ",$hosts," == *",$harness,"* ]] && continue
    state="$(printf '%s\n' "$parsed" | awk -F'|' -v target="$host" '$1 == target { print $2; exit }')"
    if [[ -n "$state" && "$state" != "current" ]]; then
      printf 'TRACER_HERDR_HOST_NOT_RECORDED host=%s state=%s\n' "$harness" "$state"
      failed=1
    fi
  done <<<"$present"
  case "$plugin" in
    listed) ;;
    unreadable)
      printf 'TRACER_HERDR_PLUGIN_UNREADABLE\n'
      failed=1
      ;;
    *)
      printf 'TRACER_HERDR_PLUGIN_MISSING\n'
      failed=1
      ;;
  esac
  while IFS= read -r key; do
    if [[ "$keys_seen" != *" $key "* ]]; then
      printf 'TRACER_HERDR_KEY_MISSING key=%s\n' "$key"
      failed=1
    fi
  done < <(herdr_sidebar_keys)
  if [[ -n "$shell" ]]; then
    printf 'TRACER_HERDR_SHELL_SET found=%s\n' "$shell"
    failed=1
  fi
  [[ "$failed" -eq 0 ]] || return 1
  printf 'TRACER_HERDR_INSTALLED_OK hosts=%s\n' "$hosts"
}

# After pass 1, before the rerun: gather herdr's facts as the tester and decide. Output of every
# herdr command is read whatever its exit code; a `herdr server reload-config` failure (no server
# runs in a container) never reaches this probe. A copy of the binary and the ledger's key paths are
# kept for herdr_probe_after, since the uninstall removes the binary and the ledger.
herdr_probe_installed() {
  local py out workspace keys
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  py='import json, sys, tomllib
from pathlib import Path
from installer import postinstall, receipts
home = Path.home()
for harness in sorted(postinstall.present_hosts() & postinstall._HERDR_TARGETS.keys()):
    print("P " + harness + " " + postinstall._HERDR_TARGETS[harness])
receipt = receipts.read("herdr")
if receipt is None:
    print("N")
for host in (receipt.hooks.get("herdr-integration", ()) if receipt else ()):
    print("H " + host)
config = home / ".config" / "herdr" / "config.toml"
doc = tomllib.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
for dotted in sys.argv[1:]:
    node = doc
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    if node is not None:
        print("C " + dotted)
terminal = doc.get("terminal")
shell = terminal.get("default_shell") if isinstance(terminal, dict) else None
if shell is not None:
    print("DS " + str(shell))
ledger = receipts.config_ledger_dir() / "herdr.json"
if ledger.exists():
    for entry in json.loads(ledger.read_text(encoding="utf-8")).get("entries", []):
        print("E " + entry["setting"] + " " + ".".join(entry["key_path"]) + " " + json.dumps(entry["value"]))
'
  keys="$(herdr_sidebar_keys | paste -sd' ' -)"
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
herdr=\"\$HOME/.local/bin/herdr\"
if [ -x \"\$herdr\" ]; then
  cp \"\$herdr\" ${HERDR_PROBE_COPY}
  { \"\$herdr\" integration status 2>&1 || true; } | sed 's/^/S /'
  printf 'Y %s\\n' \"\$({ \"\$herdr\" plugin list --json --plugin ${HERDR_PLUGIN_ID} 2>/dev/null || true; } | tr '\\n' ' ')\"
fi
for d in .claude/skills .agents/skills .codex/skills .cursor/skills .copilot/skills .config/opencode/skills; do
  if [ -d \"\$HOME/\$d\" ]; then find \"\$HOME/\$d\" -maxdepth 1 -iname '*herdr*' -print | sed 's/^/W /'; fi
done
cd ${workspace}
uv run --isolated --no-dev python -c $(printf '%q' "$py") ${keys}
echo D
")" || { printf 'TRACER_HERDR_PROBE_FAILED\n'; return 1; }
  ensure_phase_dir
  printf '%s\n' "$out" | sed -n 's/^E [^ ]* \([^ ]*\) .*$/\1/p' >"$PHASE_DIR/herdr-ledger-keys.txt"
  printf '%s\n' "$out" | herdr_installed_verdict
}

# Fact lines on stdin from herdr_probe_after: `S`, `Y`, `K <ledger key still in config.toml>`, `D`.
herdr_removed_verdict() {
  local line status="" plugin="" done=0 failed=0 key
  while IFS= read -r line; do
    case "$line" in
      "S "*) status+="${line#S }"$'\n' ;;
      "Y "*) plugin="$(printf '%s' "${line#Y }" | herdr_plugin_state)" ;;
      "K "*)
        key="${line#K }"
        printf 'TRACER_HERDR_KEY_LEFT key=%s\n' "$key"
        failed=1
        ;;
      D) done=1 ;;
    esac
  done
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_HERDR_PROBE_FAILED\n'
    return 1
  fi
  printf '%s' "$status" | herdr_status_clean || failed=1
  case "$plugin" in
    absent) ;;
    listed)
      printf 'TRACER_HERDR_PLUGIN_LEFT\n'
      failed=1
      ;;
    *)
      printf 'TRACER_HERDR_PLUGIN_UNREADABLE\n'
      failed=1
      ;;
  esac
  [[ "$failed" -eq 0 ]] || return 1
  printf 'TRACER_HERDR_STATUS_CLEAN_OK\nTRACER_HERDR_REVERT_OK\n'
}

# After the full uninstall: a copy of the binary (taken before it) must report every target
# `not installed` and no plugin, and herdr's kept config.toml must hold none of the keys the ledger
# recorded.
herdr_probe_after() {
  local py out workspace keys key_file="$PHASE_DIR/herdr-ledger-keys.txt"
  if [[ ! -s "$key_file" ]]; then
    printf 'TRACER_HERDR_REVERT_UNKNOWN\n'
    return 1
  fi
  keys="$(paste -sd' ' - <"$key_file")"
  # The keys were written by this harness's own probe from the ledger; refuse anything else.
  [[ "$keys" =~ ^[A-Za-z0-9_.\ -]+$ ]] || { printf 'TRACER_HERDR_REVERT_UNKNOWN\n'; return 1; }
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  py='import sys, tomllib
from pathlib import Path
config = Path.home() / ".config" / "herdr" / "config.toml"
doc = tomllib.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
for dotted in sys.argv[1:]:
    node = doc
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    if node is not None:
        print("K " + dotted)
'
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
probe=${HERDR_PROBE_COPY}
if [ -x \"\$probe\" ]; then
  { \"\$probe\" integration status 2>&1 || true; } | sed 's/^/S /'
  printf 'Y %s\\n' \"\$({ \"\$probe\" plugin list --json --plugin ${HERDR_PLUGIN_ID} 2>/dev/null || true; } | tr '\\n' ' ')\"
fi
cd ${workspace}
uv run --isolated --no-dev python -c $(printf '%q' "$py") ${keys}
echo D
")" || { printf 'TRACER_HERDR_PROBE_FAILED\n'; return 1; }
  printf '%s\n' "$out" | herdr_removed_verdict
}

# neovim (ONB-08). The container answers with one prefixed fact line each (see nvim_probe_installed)
# and the verdicts are decided here, so a host test can drive them with fixture lines. Facts on stdin:
# `V <nvim --version first line>`, `R <$VIMRUNTIME>`, `T <receipt artifact type> <HOME-relative path>`,
# `N` (no receipt), `E <EDITOR> <VISUAL>`, `B <tweak block count>`, `G <starter HEAD>`,
# `A ok|fail` (the patch reverse-applies) and the closing `D`.
nvim_installed_verdict() {
  local line version="" runtime="" has_dir=0 has_link=0 no_receipt=0 editor="" bundle=0
  local head="" patch="" done=0 failed=0
  while IFS= read -r line; do
    case "$line" in
      "V NVIM v"*) version="${line#V NVIM }" ;;
      "R "*) runtime="${line#R }" ;;
      "T dir .local/opt/nvim") has_dir=1 ;;
      "T link .local/bin/nvim") has_link=1 ;;
      N) no_receipt=1 ;;
      "E "*) read -r editor <<<"${line#E }" || true ;;
      "B "*) bundle="${line#B }" ;;
      "G "*) head="${line#G }" ;;
      "A "*) patch="${line#A }" ;;
      D) done=1 ;;
    esac
  done
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_NVIM_PROBE_FAILED\n'
    return 1
  fi
  if [[ -z "$version" ]]; then
    printf 'TRACER_NVIM_VERSION_MISSING\n'
    failed=1
  fi
  if [[ "$runtime" != "$TESTER_HOME/.local/opt/nvim/"* ]]; then
    printf 'TRACER_NVIM_RUNTIME_OUTSIDE runtime=%s\n' "$runtime"
    failed=1
  fi
  if [[ "$no_receipt" -eq 1 || "$has_dir" -eq 0 || "$has_link" -eq 0 ]]; then
    printf 'TRACER_NVIM_RECEIPT_INCOMPLETE\n'
    failed=1
  fi
  if [[ "$editor" != "nvim nvim" ]]; then
    printf 'TRACER_NVIM_EDITOR_MISMATCH found=%s\n' "$editor"
    failed=1
  fi
  if [[ "$bundle" != 1 ]]; then
    printf 'TRACER_NVIM_BUNDLE_MISSING count=%s\n' "$bundle"
    failed=1
  fi
  if [[ -z "$head" ]]; then
    printf 'TRACER_NVIM_STARTER_MISSING\n'
    failed=1
  else
    if [[ "$head" != "$NVIM_STARTER_PIN" ]]; then
      printf 'TRACER_NVIM_STARTER_PIN_MISMATCH head=%s\n' "$head"
      failed=1
    fi
    if [[ "$patch" != ok ]]; then
      printf 'TRACER_NVIM_STARTER_UNPATCHED\n'
      failed=1
    fi
  fi
  [[ "$failed" -eq 0 ]] || return 1
  printf 'TRACER_NVIM_INSTALLED_OK version=%s head=%s\n' "$version" "${head:0:7}"
}

# After pass 1, before the rerun: gather neovim's facts as the tester and decide. nvim's own runs
# keep their XDG dirs in a scratch dir, so the probe leaves nothing in the tester's HOME; the new
# bash with EDITOR and VISUAL unset proves the value comes from the rc chain (no zsh in these
# containers, D-20 refined).
nvim_probe_installed() {
  local py body pre out
  py='from pathlib import Path
from installer import receipts
home = Path.home()
receipt = receipts.read("neovim")
if receipt is None:
    print("N")
else:
    for artifact in receipt.artifacts:
        path = artifact.path
        print("T " + artifact.type + " " + str(path.relative_to(home) if path.is_relative_to(home) else path))
'
  IFS= read -r -d '' body <<'EOF' || true
set -euo pipefail
eval "$("$brew" shellenv)"
nvim="$HOME/.local/bin/nvim"
if [ -x "$nvim" ]; then
  t="$(mktemp -d)"
  export XDG_STATE_HOME="$t/state" XDG_DATA_HOME="$t/data" XDG_CACHE_HOME="$t/cache"
  v="$({ "$nvim" --version </dev/null 2>/dev/null || true; } | sed -n 1p)"
  r="$("$nvim" --clean --headless -c 'lua io.stdout:write(vim.env.VIMRUNTIME)' -c 'qa!' </dev/null 2>/dev/null || true)"
  unset XDG_STATE_HOME XDG_DATA_HOME XDG_CACHE_HOME
  rm -rf "$t"
  if [ -n "$v" ]; then printf 'V %s\n' "$v"; fi
  printf 'R %s\n' "$r"
fi
e="$(env -u EDITOR -u VISUAL bash -ic 'printf "%s %s" "${EDITOR-}" "${VISUAL-}"' </dev/null 2>/dev/null || true)"
printf 'E %s\n' "$e"
b="$(grep -cFx '# >>> tools-installer tweak:neovim >>>' "$HOME/.myshellrc" 2>/dev/null || true)"
printf 'B %s\n' "${b:-0}"
cfg="$HOME/.config/nvim"
if [ -d "$cfg/.git" ]; then
  g="$(git -C "$cfg" rev-parse HEAD 2>/dev/null || true)"
  if [ -n "$g" ]; then printf 'G %s\n' "$g"; fi
  if git -C "$cfg" apply --reverse --check "$workspace/$patch" >/dev/null 2>&1; then echo 'A ok'; else echo 'A fail'; fi
fi
cd "$workspace"
uv run --isolated --no-dev python -c "$py"
echo D
EOF
  printf -v pre 'brew=%q\nworkspace=%q\npatch=%q\npy=%q\n' \
    "$BREW_BIN" "$TESTER_WORKSPACE" "$NVIM_STARTER_PATCH" "$py"
  out="$(exec_tester "$pre$body")" || { printf 'TRACER_NVIM_PROBE_FAILED\n'; return 1; }
  printf '%s\n' "$out" | nvim_installed_verdict
}

# Fact lines on stdin from nvim_probe_after: `L` (the link or a file is still at ~/.local/bin/nvim),
# `O` (~/.local/opt/nvim is still there), `N` (the receipt file is still there), `B <tweak block
# count>`, `K` (the user's ~/.config/nvim/init.lua is kept) and the closing `D`.
nvim_removed_verdict() {
  local line link=0 tree=0 receipt=0 bundle=0 kept=0 done=0 failed=0
  while IFS= read -r line; do
    case "$line" in
      L) link=1 ;;
      O) tree=1 ;;
      N) receipt=1 ;;
      "B "*) bundle="${line#B }" ;;
      K) kept=1 ;;
      D) done=1 ;;
    esac
  done
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_NVIM_PROBE_FAILED\n'
    return 1
  fi
  if [[ "$link" -eq 1 ]]; then
    printf 'TRACER_NVIM_LINK_LEFT\n'
    failed=1
  fi
  if [[ "$tree" -eq 1 ]]; then
    printf 'TRACER_NVIM_TREE_LEFT\n'
    failed=1
  fi
  if [[ "$receipt" -eq 1 ]]; then
    printf 'TRACER_NVIM_RECEIPT_LEFT\n'
    failed=1
  fi
  if [[ "$bundle" != 0 ]]; then
    printf 'TRACER_NVIM_BUNDLE_LEFT count=%s\n' "$bundle"
    failed=1
  fi
  if [[ "$kept" -eq 0 ]]; then
    printf 'TRACER_NVIM_CONFIG_GONE\n'
    failed=1
  fi
  [[ "$failed" -eq 0 ]] || return 1
  printf 'TRACER_NVIM_REMOVED_OK\n'
}

# After the full uninstall: neovim's link, opt tree, receipt and EDITOR block are gone, and the
# user's ~/.config/nvim is kept (SPEC R3, D-20). The receipt path is a $HOME-relative literal, the
# way assert_receipt_removed writes it, and mirrors installer/receipts.py::default_receipts_dir.
nvim_probe_after() {
  local body out
  IFS= read -r -d '' body <<'EOF' || true
set -euo pipefail
if [ -e "$HOME/.local/bin/nvim" ] || [ -L "$HOME/.local/bin/nvim" ]; then echo L; fi
if [ -e "$HOME/.local/opt/nvim" ] || [ -L "$HOME/.local/opt/nvim" ]; then echo O; fi
if [ -e "$HOME/.local/state/tools-installer/receipts/neovim.json" ]; then echo N; fi
b="$(grep -cFx '# >>> tools-installer tweak:neovim >>>' "$HOME/.myshellrc" 2>/dev/null || true)"
printf 'B %s\n' "${b:-0}"
if [ -f "$HOME/.config/nvim/init.lua" ]; then echo K; fi
echo D
EOF
  out="$(exec_tester "$body")" || { printf 'TRACER_NVIM_PROBE_FAILED\n'; return 1; }
  printf '%s\n' "$out" | nvim_removed_verdict
}

# neovim's zero-LSP check (ONB-10, D-12/D-13), run by the orchestrator on Fedora. Lines on stdin from
# cmd_nvim_lsp: the marker `NVIM_LSP clients=.. mason_entries=.. filetypes=.. lspconfig=.. mason=..`
# (printed by scripts/nvim-lsp-check.lua), `PROC <cmdline>`, `NVIM_LSP_NO_NVIM`, `NVIM_LSP_NO_STARTER`
# and `NVIM_LSP_DONE` (both launches exited 0). Every other line is ignored, stderr noise and the
# `NVIM_LSP_STDERR` evidence lines included: the marker counts only on a line that starts with it.
# `NVIM_LSP_LUA_ERROR <launch>: <line>` (an error banner in a launch's stderr) fails the verdict.
nvim_lsp_verdict() {
  local line part marker=0 clients="" entries="" filetypes="" lspconfig="" mason="" procs="" cmd
  local no_nvim=0 no_starter=0 done=0 failed=0 lua_errors=""
  local -a parts
  while IFS= read -r line; do
    case "$line" in
      "NVIM_LSP clients="*)
        marker=1
        read -ra parts <<<"${line#NVIM_LSP }"
        for part in ${parts[@]+"${parts[@]}"}; do
          case "$part" in
            clients=*) clients="${part#clients=}" ;;
            mason_entries=*) entries="${part#mason_entries=}" ;;
            filetypes=*) filetypes="${part#filetypes=}" ;;
            lspconfig=*) lspconfig="${part#lspconfig=}" ;;
            mason=*) mason="${part#mason=}" ;;
          esac
        done
        ;;
      "PROC "*) procs+="${line#PROC }"$'\n' ;;
      NVIM_LSP_NO_NVIM) no_nvim=1 ;;
      NVIM_LSP_NO_STARTER) no_starter=1 ;;
      NVIM_LSP_DONE) done=1 ;;
      "NVIM_LSP_LUA_ERROR "*) lua_errors+="${line#NVIM_LSP_LUA_ERROR }"$'\n' ;;
    esac
  done
  if [[ "$no_nvim" -eq 1 ]]; then
    printf 'TRACER_NVIM_LSP_NO_NVIM\n'
    return 1
  fi
  if [[ "$no_starter" -eq 1 ]]; then
    printf 'TRACER_NVIM_LSP_NO_STARTER\n'
    return 1
  fi
  if [[ "$marker" -eq 0 || "$done" -eq 0 ]]; then
    printf 'TRACER_NVIM_LSP_PROBE_FAILED\n'
    return 1
  fi
  while IFS= read -r cmd; do
    [[ -n "$cmd" ]] || continue
    printf 'TRACER_NVIM_LSP_LUA_ERROR %s\n' "$cmd"
    failed=1
  done <<<"$lua_errors"
  if [[ "$clients" != 0 ]]; then
    printf 'TRACER_NVIM_LSP_CLIENTS count=%s\n' "$clients"
    failed=1
  fi
  while IFS= read -r cmd; do
    [[ -n "$cmd" ]] || continue
    printf 'TRACER_NVIM_LSP_SERVER_PROCESS cmd=%s\n' "$cmd"
    failed=1
  done <<<"$procs"
  if [[ "$entries" != 0 ]]; then
    printf 'TRACER_NVIM_MASON_NOT_EMPTY entries=%s\n' "$entries"
    failed=1
  fi
  if [[ "$filetypes" != python,lua,typescript,go,java ]]; then
    printf 'TRACER_NVIM_LSP_FILETYPES found=%s\n' "$filetypes"
    failed=1
  fi
  if [[ "$lspconfig" != 1 || "$mason" != 1 ]]; then
    printf 'TRACER_NVIM_LSP_PLUGINS_MISSING lspconfig=%s mason=%s\n' "$lspconfig" "$mason"
    failed=1
  fi
  [[ "$failed" -eq 0 ]] || return 1
  printf 'TRACER_NVIM_LSP_OK clients=%s mason_entries=%s\n' "$clients" "$entries"
}

# Orchestrator only, on an already-bootstrapped container after pass 1: act on the tree the
# installer produced. Both nvim launches run with XDG data, state and cache in a mktemp dir outside
# HOME (so the leftover check never sees them), and each is bounded by `timeout` with stdin from
# /dev/null. An EXIT trap in the gather prints each launch's exit status and stderr tail as
# `NVIM_LSP_STDERR <launch>: ...` evidence and removes the dir, however the gather ends (R2-03).
# The evidence is forwarded to this command's own stdout, which `all` tees into the transcript
# (R2-02); stderr never decides the verdict (treesitter's noise is expected, Pitfall 7).
cmd_nvim_lsp() {
  container_running || die "container $CONTAINER_NAME is not running"
  local body pre out status=0
  IFS= read -r -d '' body <<'EOF' || true
set -euo pipefail
nvim="$HOME/.local/bin/nvim"
if [ ! -x "$nvim" ]; then echo NVIM_LSP_NO_NVIM; exit 0; fi
if [ ! -f "$HOME/.config/nvim/init.lua" ]; then echo NVIM_LSP_NO_STARTER; exit 0; fi
t="$(mktemp -d)"
fl='not run'
ck='not run'
# A Lua error in init.lua leaves exit 0 under +qa/qa!: E5xxx is nvim's Lua error code (E5108, E5113),
# the others are its error banners. Treesitter's plain "Error: ..." noise matches none of them.
lua_error='E5[0-9]{3}:|Error detected while processing|Error executing|stack traceback'
evidence() {
  local launch status
  for launch in first-launch check; do
    if [ "$launch" = first-launch ]; then status="$fl"; else status="$ck"; fi
    printf 'NVIM_LSP_STDERR %s: exit status %s\n' "$launch" "$status"
    if [ -f "$t/$launch.err" ]; then
      tail -n 20 "$t/$launch.err" | sed "s/^/NVIM_LSP_STDERR $launch: /"
      grep -E "$lua_error" "$t/$launch.err" | head -n 5 | sed "s/^/NVIM_LSP_LUA_ERROR $launch: /" || true
    fi
  done
  rm -rf "$t"
  }
trap evidence EXIT
export XDG_DATA_HOME="$t/data" XDG_STATE_HOME="$t/state" XDG_CACHE_HOME="$t/cache"
mkdir "$t/files"
cd "$t/files"
printf 'x = 1\n' > a.py
printf 'local x = 1\n' > a.lua
printf 'const x = 1\n' > a.ts
printf 'package main\n' > a.go
printf 'class A {}\n' > A.java
fl=0
timeout 300 "$nvim" --headless +qa 2>"$t/first-launch.err" </dev/null || fl=$?
ck=0
timeout 180 "$nvim" --headless -c "luafile $workspace/scripts/nvim-lsp-check.lua" 2>"$t/check.err" </dev/null || ck=$?
if [ "$fl" -eq 0 ] && [ "$ck" -eq 0 ]; then echo NVIM_LSP_DONE; fi
EOF
  printf -v pre 'workspace=%q\n' "$TESTER_WORKSPACE"
  out="$(exec_tester "$pre$body")" || status=$?
  printf '%s\n' "$out" | sed -n '/^NVIM_LSP_STDERR /p'
  if [[ "$status" -ne 0 ]]; then
    printf 'TRACER_NVIM_LSP_PROBE_FAILED\n'
    return 1
  fi
  printf '%s\n' "$out" | nvim_lsp_verdict
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
  [[ ! -f "$PHASE_DIR/pass1-chunked.txt" ]] \
    || die "pass2 reruns --all and the last pass1 was chunked (--categories $(cat "$PHASE_DIR/pass1-chunked.txt")); run a full pass1 first"
  local log="$PHASE_DIR/pass2-transcript.log"
  : > "$log"

  # Pass 1 left herdr installed: prove its integrations, plugin and sidebar keys before the rerun.
  if ! herdr_probe_installed >> "$log"; then
    return 1
  fi
  # ... and neovim: its binary, runtime, receipt, editor block and the pinned patched starter.
  if ! nvim_probe_installed >> "$log"; then
    return 1
  fi

  # Step 1: rerun — a second full install over already-installed state.
  ACC_INSTALLED=0; ACC_UPDATED=0; ACC_SKIPPED=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_REPAIRED=0; ACC_RECONFIGURED=0; ACC_REINSTALLED=0
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
  if ! rerun_step_ok >> "$log"; then
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
  if ! herdr_probe_after >> "$log"; then
    return 1
  fi
  if ! nvim_probe_after >> "$log"; then
    return 1
  fi
  if ! assert_gsd_absent uninstall >> "$log"; then
    return 1
  fi

  # Step 3: reinstall — catches state the uninstall sweep left stray.
  ACC_INSTALLED=0; ACC_UPDATED=0; ACC_SKIPPED=0; ACC_FAILED=0; ACC_DEP_FAILED=0
  ACC_REPAIRED=0; ACC_RECONFIGURED=0; ACC_REINSTALLED=0
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
  # A failing pass2 ends the shell through set -e, so the trap also prints its transcript (the reason).
  PASS2_STARTED=0
  trap 'rc=$?; if [[ "$rc" -ne 0 && "$PASS2_STARTED" -eq 1 ]]; then cat "$PHASE_DIR/pass2-transcript.log" || true; fi; ct rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true' EXIT
  cmd_bootstrap --replace
  cmd_pass1 | tee "$PHASE_DIR/pass1-transcript.log"
  # A failed zero-LSP check still lets pass 2 run, so one run gives both pieces of evidence.
  local lsp_failed=0
  if [[ "$DISTRO" == fedora ]]; then
    cmd_nvim_lsp | tee "$PHASE_DIR/nvim-lsp-transcript.log" || lsp_failed=1
  fi
  PASS2_STARTED=1
  cmd_pass2
  cat "$PHASE_DIR/pass2-transcript.log"
  PASS2_STARTED=0
  if [[ "$lsp_failed" -ne 0 ]]; then
    printf 'TRACER_NVIM_LSP_FAILED_EARLIER\n'
    return 1
  fi
}

# --- nested target (D-18, D-29): orchestrator only, a time-boxed spike --------------------------
# One disposable quay.io/podman/stable container runs the installer as that image's rootless user
# through the same tester helpers (the user, home and workspace are parameters), with zsh installed,
# for the one real Alacritty build (distrobox + inner podman) and herdr's default_shell write.

# The five HOME-relative paths Alacritty's receipt holds (24-01).
nested_alacritty_paths() {
  printf '%s\n' .local/bin/alacritty \
    .local/share/applications/Alacritty.desktop \
    .local/share/icons/hicolor/scalable/apps/Alacritty.svg \
    .terminfo/a/alacritty \
    .terminfo/a/alacritty-direct
}

nested_start() {
  ct rm -f "$NESTED_CONTAINER_NAME" >/dev/null 2>&1 || true
  # label=disable: SELinux on the host blocks the nested podman store otherwise; /dev/fuse is for
  # fuse-overlayfs. Never privileged.
  ct run -d --name "$NESTED_CONTAINER_NAME" --device /dev/fuse --security-opt label=disable \
    "$NESTED_IMAGE" sleep infinity >/dev/null
}

# EXIT trap: the outer container goes on every outcome.
nested_teardown() {
  ct rm -f "$NESTED_CONTAINER_NAME" >/dev/null 2>&1 || true
  printf 'TRACER_NESTED_TEARDOWN_OK\n'
}

# $1 names the step, $2 is the failing command's output; the first line naming an `Error` is
# reported, else the last non-empty line (the first one is usually a pull progress line).
nested_infeasible() {
  local detail
  detail="$(printf '%s\n' "$2" | awk '/Error/ && e == "" { e = $0 } NF { l = $0 } END { print (e != "" ? e : l) }')"
  printf 'TRACER_NESTED_INFEASIBLE step=%s detail=%s\n' "$1" "$detail"
}

# Root installs the box's tools (curl and tar for the uv bootstrap and the workspace stream, and
# util-linux for the `su` every tester helper runs through: quay.io/podman/stable ships without it),
# the workspace is streamed and uv bootstrapped for the nested user through the shared helpers.
nested_prepare() {
  exec_root dnf install -y distrobox desktop-file-utils ncurses git python3 zsh curl tar util-linux \
    || return 1
  install_github_token || return 1
  copy_workspace || return 1
  bootstrap_uv || return 1
  write_tester_path || return 1
  sync_workspace || return 1
}

# Inner podman works or it does not: either way the run goes on to the installer step.
nested_probe_podman() {
  local out
  if ! out="$(exec_tester 'podman info >/dev/null' 2>&1)"; then
    nested_infeasible podman-info "$out"
    return 0
  fi
  # The image is FROM scratch with one binary: run its default command, no `true`. It is removed
  # whatever the run's outcome, so a later build never reads it as a leftover.
  if ! out="$(exec_tester "rc=0; podman run --rm ${NESTED_PROBE_IMAGE} || rc=\$?; podman rmi -f ${NESTED_PROBE_IMAGE} >/dev/null 2>&1 || true; exit \$rc" 2>&1)"; then
    nested_infeasible podman-run "$out"
    return 0
  fi
  printf 'TRACER_NESTED_PODMAN_OK\n'
}

# Whether $1 reads as one of the environment errors a rootless nested podman raises when it cannot
# create the box: the image's containers.conf UTS-namespace hostname (24-08 nested run #2) and
# user-namespace permission failures. Anything else is the product's.
nested_environment_error() {
  grep -qiE 'cannot set hostname when running in the host UTS namespace|operation not permitted|newuidmap|cannot set up namespace' <<<"$1"
}

# $1 is the install transcript. Returns 0 when Alacritty installed, 2 (infeasible: the box could
# not be created for a known environment reason) or 1 (a product failure, or no Alacritty row at all).
nested_classify_alacritty() {
  local row word detail full engine
  row="$(sed -nE 's/^[^ ]+ +alacritty +(installed|failed|checksum mismatch|crashed|dependency failed|not attempted|blocked|manual|skipped|updated|repaired|reconfigured|reinstalled)( — (.*))?$/\1|\3/p' "$1" | tail -n 1)"
  if [[ -z "$row" ]]; then
    printf 'TRACER_NESTED_BUILD_FAILED detail=no alacritty row in the install output\n'
    return 1
  fi
  word="${row%%|*}"
  detail="${row#*|}"
  case "$word" in
    installed) return 0 ;;
    failed)
      # The Summary row wraps a long reason over several lines; the unwrapped `<mark> alacritty
      # failed: ...` line after it carries the whole command (24-08 nested run #2).
      full="$(sed -nE 's/^[^ ]+ alacritty failed: (.*)$/\1/p' "$1" | tail -n 1)"
      # Podman prints the reason on its own `Error: ...` line before the row (24-08 nested run #2:
      # "cannot set hostname when running in the host UTS namespace"), not in the row itself.
      engine="$(grep -E 'Error: ' "$1" | tail -n 5 || true)"
      if [[ "$detail $full" == *"distrobox create"* ]] \
        && nested_environment_error "$detail $full $engine"; then
        nested_infeasible distrobox-create "${full:-$detail}"
        return 2
      fi
      ;;
  esac
  printf 'TRACER_NESTED_BUILD_FAILED detail=%s%s\n' "$word" "${detail:+ — $detail}"
  return 1
}

# --categories is the production flag; the terminal category also installs kitty, WezTerm and
# herdr, which is how herdr's default_shell write gets proven. Only the Alacritty and herdr rows
# are judged; the others' outcomes are ignored here.
nested_install() {
  local tmp status=0 rc=0
  tmp="$(mktemp)"
  set +e
  run_setup_as_tester "--categories terminal --yes" >"$tmp" 2>&1
  status=$?
  set -e
  cat "$tmp"
  cat "$tmp" >"$PHASE_DIR/nested-install.log"
  nested_classify_alacritty "$tmp" || rc=$?
  rm -f "$tmp"
  if [[ "$status" -gt 1 && "$rc" -eq 0 ]]; then
    printf 'TRACER_NESTED_BUILD_FAILED detail=setup exit %s\n' "$status"
    rc=1
  fi
  return "$rc"
}

# After a real build: the receipt holds the five artifacts, the desktop entry validates, terminfo
# resolves with and without TERMINFO set (SPEC R3), and the inner podman holds no container or image.
nested_artifacts_ok() {
  local py out workspace line failed=0 done=0 seen=" " path desktop="" t1="" t2=""
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  py='from pathlib import Path
from installer import receipts
home = Path.home()
receipt = receipts.read("alacritty")
for artifact in (receipt.artifacts if receipt else ()):
    if artifact.path.is_relative_to(home):
        print("P " + artifact.path.relative_to(home).as_posix())
'
  out="$(exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
cd ${workspace}
uv run --isolated --no-dev python -c $(printf '%q' "$py")
if desktop-file-validate \"\$HOME/.local/share/applications/Alacritty.desktop\" >/dev/null 2>&1; then echo 'V ok'; else echo 'V fail'; fi
if infocmp -A \"\$HOME/.terminfo\" alacritty >/dev/null 2>&1; then echo 'T1 ok'; else echo 'T1 fail'; fi
if env -u TERMINFO -u TERMINFO_DIRS infocmp alacritty >/dev/null 2>&1; then echo 'T2 ok'; else echo 'T2 fail'; fi
podman ps -a -q | sed 's/^/C /'
podman images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | awk -v probe=${NESTED_PROBE_IMAGE} '\$1 != probe { print \"M \" \$2 }'
echo D
")" || { printf 'TRACER_NESTED_PROBE_FAILED\n'; return 1; }
  while IFS= read -r line; do
    case "$line" in
      "P "*) seen+="${line#P } " ;;
      "V "*) desktop="${line#V }" ;;
      "T1 "*) t1="${line#T1 }" ;;
      "T2 "*) t2="${line#T2 }" ;;
      "C "*) printf 'TRACER_NESTED_CONTAINER_LEFT id=%s\n' "${line#C }"; failed=1 ;;
      "M "*) printf 'TRACER_NESTED_IMAGE_LEFT id=%s\n' "${line#M }"; failed=1 ;;
      D) done=1 ;;
    esac
  done <<<"$out"
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_NESTED_PROBE_FAILED\n'
    return 1
  fi
  while IFS= read -r path; do
    if [[ "$seen" != *" $path "* ]]; then
      printf 'TRACER_NESTED_ARTIFACT_MISSING path=%s\n' "$path"
      failed=1
    fi
  done < <(nested_alacritty_paths)
  if [[ "$desktop" != ok ]]; then printf 'TRACER_NESTED_DESKTOP_INVALID\n'; failed=1; fi
  if [[ "$t1" != ok ]]; then printf 'TRACER_NESTED_TERMINFO_FAILED step=infocmp-A\n'; failed=1; fi
  if [[ "$t2" != ok ]]; then printf 'TRACER_NESTED_TERMINFO_FAILED step=infocmp-env\n'; failed=1; fi
  [[ "$failed" -eq 0 ]] || return 1
  printf 'TRACER_NESTED_BUILD_OK\n'
}

# herdr's config.toml default_shell, read as the nested user: `DS <value>` when the key is set,
# `L <value>` per default-shell ledger entry, `W <path>` for the zsh the installer itself resolves.
nested_herdr_facts() {
  local py workspace
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  py='import json, tomllib
from pathlib import Path
from installer import postinstall, receipts
home = Path.home()
config = home / ".config" / "herdr" / "config.toml"
doc = tomllib.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
terminal = doc.get("terminal")
shell = terminal.get("default_shell") if isinstance(terminal, dict) else None
if shell is not None:
    print("DS " + str(shell))
ledger = receipts.config_ledger_dir() / "herdr.json"
if ledger.exists():
    for entry in json.loads(ledger.read_text(encoding="utf-8")).get("entries", []):
        if entry["setting"] == "default-shell":
            print("L " + str(entry["value"]))
print("W " + (postinstall.which_with_brew("zsh") or ""))
'
  exec_tester "set -euo pipefail
eval \"\$(${BREW_BIN} shellenv)\"
cd ${workspace}
uv run --isolated --no-dev python -c $(printf '%q' "$py")
echo D
"
}

# After the install: default_shell equals the zsh the installer resolves, and the ledger recorded it.
nested_herdr_shell_ok() {
  local out line shell=none ledger="" expected="" done=0
  out="$(nested_herdr_facts)" || { printf 'TRACER_NESTED_PROBE_FAILED\n'; return 1; }
  while IFS= read -r line; do
    case "$line" in
      "DS "*) shell="${line#DS }" ;;
      "L "*) ledger="${line#L }" ;;
      "W "*) expected="${line#W }" ;;
      D) done=1 ;;
    esac
  done <<<"$out"
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_NESTED_PROBE_FAILED\n'
    return 1
  fi
  if [[ -z "$expected" || "$shell" != "$expected" ]]; then
    printf 'TRACER_NESTED_HERDR_SHELL_MISMATCH found=%s expected=%s\n' "$shell" "$expected"
    return 1
  fi
  if [[ "$ledger" != "$expected" ]]; then
    printf 'TRACER_NESTED_HERDR_SHELL_UNRECORDED expected=%s\n' "$expected"
    return 1
  fi
  printf 'TRACER_NESTED_HERDR_SHELL_OK\n'
}

# After the uninstall: the key is gone from herdr's kept config.toml.
nested_herdr_revert_ok() {
  local out line shell="" done=0
  out="$(nested_herdr_facts)" || { printf 'TRACER_NESTED_PROBE_FAILED\n'; return 1; }
  while IFS= read -r line; do
    case "$line" in
      "DS "*) shell="${line#DS }" ;;
      D) done=1 ;;
    esac
  done <<<"$out"
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_NESTED_PROBE_FAILED\n'
    return 1
  fi
  if [[ -n "$shell" ]]; then
    printf 'TRACER_NESTED_HERDR_REVERT_LEFT found=%s\n' "$shell"
    return 1
  fi
  printf 'TRACER_NESTED_HERDR_REVERT_OK\n'
}

nested_uninstall_run() {
  local tmp status=0
  tmp="$(mktemp)"
  set +e
  run_setup_as_tester "--uninstall --yes" >"$tmp" 2>&1
  status=$?
  set -e
  cat "$tmp"
  cat "$tmp" >"$PHASE_DIR/nested-uninstall.log"
  rm -f "$tmp"
  if [[ "$status" -ne 0 ]]; then
    printf 'TRACER_NESTED_UNINSTALL_INCOMPLETE exit=%s\n' "$status"
    return 1
  fi
}

# None of the five paths and no ~/.terminfo/a may remain after the uninstall.
nested_uninstall_ok() {
  local out line paths left=0 done=0
  paths="$(nested_alacritty_paths | paste -sd' ' -)"
  out="$(exec_tester "cd ~ && for p in ${paths}; do if [ -e \"\$p\" ] || [ -L \"\$p\" ]; then echo \"L \$p\"; fi; done; echo D")" \
    || { printf 'TRACER_NESTED_PROBE_FAILED\n'; return 1; }
  while IFS= read -r line; do
    case "$line" in
      "L "*) printf 'TRACER_NESTED_UNINSTALL_LEFT path=%s\n' "${line#L }"; left=1 ;;
      D) done=1 ;;
    esac
  done <<<"$out"
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_NESTED_PROBE_FAILED\n'
    return 1
  fi
  [[ "$left" -eq 0 ]] || return 1
  printf 'TRACER_NESTED_UNINSTALL_OK\n'
}

cmd_nested() {
  CONTAINER_NAME="$NESTED_CONTAINER_NAME"
  TESTER_USER="$NESTED_USER"
  TESTER_HOME="/home/$NESTED_USER"
  TESTER_WORKSPACE="$TESTER_HOME/workspace"
  PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-nested"
  # No Homebrew in this box: a no-op stands in so the tester helpers' shellenv evals expand to nothing.
  BREW_BIN=/bin/true
  trap nested_teardown EXIT
  ensure_phase_dir
  local failed=0 build=0
  nested_start || return 1
  nested_prepare || return 1
  nested_probe_podman
  nested_install || build=$?
  case "$build" in
    0) nested_artifacts_ok || failed=1 ;;
    2) ;; # infeasible: reported by nested_infeasible, not a product failure
    *) failed=1 ;;
  esac
  nested_herdr_shell_ok || failed=1
  nested_uninstall_run || failed=1
  nested_uninstall_ok || failed=1
  nested_herdr_revert_ok || failed=1
  return "$failed"
}

# --- schedules target (24.2-10, D-26): orchestrator only -----------------------------------------
# A disposable Fedora 44 container with systemd as PID 1 and the tester's user manager: the real
# engine writes the units (through tests/e2e_schedules_driver.py), each built-in runs once through
# its installed runner, and the log lines and Last cells are read back. Every systemctl, loginctl and
# flock runs inside the container through exec_root or exec_tester, never on the host.
SCHEDULES_BASE_IMAGE=registry.fedoraproject.org/fedora:44
SCHEDULES_IMAGE=localhost/tools-installer-e2e-schedules:44
SCHEDULES_CONTAINER_NAME=tools-installer-e2e-schedules
# The Linux log and run lock, relative to the tester's HOME (D-11, D-12).
SCHEDULES_LOG_REL=.local/state/tools-installer/schedules.log
SCHEDULES_LOCK_REL=.local/state/tools-installer/run.lock
SCHEDULES_HOLDER_UNIT=tools-installer-e2e-runlock-holder
# One poll per second: at most two minutes for systemd to boot, one for the session bus.
SCHEDULES_POLL_STEP=1
SCHEDULES_BOOT_ATTEMPTS=120
SCHEDULES_BUS_ATTEMPTS=60
# The calendar check polls every 5 s for 200 s; the catch-up check waits 75 s.
SCHEDULES_CALENDAR_STEP=5
SCHEDULES_CALENDAR_ATTEMPTS=40
SCHEDULES_CATCHUP_WAIT=75
# The tester's uid (set by schedules_start) and the --keep-image flag.
SCHEDULES_UID=
SCHEDULES_KEEP_IMAGE=0

schedules_containerfile() {
  printf 'FROM %s\n' "$SCHEDULES_BASE_IMAGE"
  printf 'RUN dnf install -y systemd procps-ng util-linux curl tar git python3 which && dnf clean all\n'
  printf 'CMD ["/sbin/init"]\n'
}

# $1 names the step, $2 is the failing step's output: the first line naming an error is reported,
# else the last non-empty one. Exits 2: the box could not be built, an environment fact, not a
# product failure (plan 24.2-13 treats it as such, R1-24).
schedules_infeasible() {
  local detail
  detail="$(printf '%s\n' "$2" | awk '/rror|nknown|ailed/ && e == "" { e = $0 } NF { l = $0 } END { print (e != "" ? e : l) }')"
  printf 'TRACER_SCHEDULES_INFEASIBLE step=%s detail=%s\n' "$1" "$detail"
  exit 2
}

# $1 is an attempt count, the rest a command: success as soon as it succeeds, failure when the
# attempts run out.
schedules_wait() {
  local attempts="$1" i
  shift
  for ((i = 0; i < attempts; i++)); do
    if "$@"; then
      return 0
    fi
    sleep "$SCHEDULES_POLL_STEP"
  done
  return 1
}

# A container reads `degraded` once booted (a unit of the base image fails), which is normal.
schedules_booted() {
  local state
  state="$(exec_root systemctl is-system-running 2>/dev/null || true)"
  [[ "$state" == running || "$state" == degraded ]]
}

schedules_bus_ready() {
  exec_root test -S "/run/user/${SCHEDULES_UID}/bus"
}

# The tester user (the only account the harness needs: no sudo, no Homebrew) and its uid.
schedules_create_tester() {
  local out
  if ! out="$(exec_root useradd -m -s /bin/bash "$TESTER_USER" 2>&1)"; then
    schedules_infeasible useradd "$out"
  fi
  if ! SCHEDULES_UID="$(exec_root id -u "$TESTER_USER" 2>&1)"; then
    schedules_infeasible uid "$SCHEDULES_UID"
  fi
}

# Every step's failure, not only a timeout, is infeasible with its own step name, so a runtime
# that rejects --systemd=always reads as environmental (R1-24).
schedules_start() {
  local out dir state
  ct rm -f "$SCHEDULES_CONTAINER_NAME" >/dev/null 2>&1 || true
  dir="$(mktemp -d)"
  schedules_containerfile >"$dir/Containerfile"
  if ! out="$(ct build -t "$SCHEDULES_IMAGE" -f "$dir/Containerfile" "$dir" 2>&1)"; then
    rm -rf "$dir"
    schedules_infeasible build "$out"
  fi
  rm -rf "$dir"
  if ! out="$(ct run -d --name "$SCHEDULES_CONTAINER_NAME" --systemd=always "$SCHEDULES_IMAGE" 2>&1)"; then
    schedules_infeasible run "$out"
  fi
  if ! schedules_wait "$SCHEDULES_BOOT_ATTEMPTS" schedules_booted; then
    state="$(exec_root systemctl is-system-running 2>&1 || true)"
    schedules_infeasible boot "systemd in the container reads '${state}', not running or degraded"
  fi
  schedules_create_tester
  if ! out="$(exec_root loginctl enable-linger "$TESTER_USER" 2>&1)"; then
    schedules_infeasible linger "$out"
  fi
  if ! schedules_wait "$SCHEDULES_BUS_ATTEMPTS" schedules_bus_ready; then
    schedules_infeasible bus "no session bus appeared at /run/user/${SCHEDULES_UID}/bus"
  fi
}

# $1 is a command string for the tester's login shell, run in the workspace with that user's
# session bus (the user manager started by enable-linger) and ~/.local/bin first on PATH.
schedules_tester() {
  local workspace prefix
  printf -v workspace '%q' "$TESTER_WORKSPACE"
  # shellcheck disable=SC2016 # the single-quoted part expands in the tester's shell
  prefix='case ":${PATH-}:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin${PATH:+:$PATH}";; esac'
  exec_tester "export XDG_RUNTIME_DIR=/run/user/${SCHEDULES_UID} DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${SCHEDULES_UID}/bus
${prefix}
cd ${workspace}
$1"
}

# The in-container driver over the real engine: `schedules_driver on cache-cleanup`.
schedules_driver() {
  local args
  printf -v args '%q ' "$@"
  schedules_tester "uv run --isolated --no-dev python -m tests.e2e_schedules_driver ${args}"
}

# The tester's schedules.log, or nothing when no run has written one yet.
schedules_fetch_log() {
  schedules_tester "cat \"\$HOME/${SCHEDULES_LOG_REL}\" 2>/dev/null || true"
}

# $1 is a copy of schedules.log, $2 a schedule id: that id's newest run must hold a start line and
# a result line after it (ok, skipped or failed). A `skipped: busy` line is a run of its own and
# never counts as the result of an earlier start.
schedules_run_verdict() {
  local result
  result="$(awk -v id="$2" '
    $2 == id && $3 == "start" { started = 1; result = ""; line = ""; next }
    $2 == id && started && $3 ~ /^(ok|skipped|failed):$/ {
      result = substr($3, 1, length($3) - 1); line = $0; started = 0
    }
    END { print result "|" line }
  ' "$1")"
  case "${result%%|*}" in
    ok | skipped)
      printf 'TRACER_SCHEDULE_RUN_OK id=%s result=%s\n' "$2" "${result%%|*}"
      ;;
    failed)
      printf 'TRACER_SCHEDULE_RUN_FAILED id=%s line=%s\n' "$2" "${result#*|}"
      return 1
      ;;
    *)
      printf 'TRACER_SCHEDULE_RUN_MISSING id=%s\n' "$2"
      return 1
      ;;
  esac
}

# $1 is the driver's `cells` output, $2 a schedule id: its Last cell must read as a run, not `never`.
schedules_cell_verdict() {
  local cell
  cell="$(awk -v id="$2" '$1 == "CELL" && $2 == id { sub(/^CELL [^ ]+ /, ""); c = $0 } END { print c }' "$1")"
  if [[ -z "$cell" || "$cell" == never ]]; then
    printf 'TRACER_SCHEDULE_CELL_NEVER id=%s\n' "$2"
    return 1
  fi
  printf 'TRACER_SCHEDULE_CELL_OK id=%s cell=%s\n' "$2" "$cell"
}

# The log and cell verdicts of schedule $1 after a run.
schedules_verdicts() {
  local log cells out rc=0
  log="$(mktemp)"
  cells="$(mktemp)"
  schedules_fetch_log >"$log" || rc=1
  out="$(schedules_run_verdict "$log" "$1")" || rc=1
  printf '%s\n' "$out"
  schedules_driver cells >"$cells" || rc=1
  out="$(schedules_cell_verdict "$cells" "$1")" || rc=1
  printf '%s\n' "$out"
  rm -f "$log" "$cells"
  return "$rc"
}

# The unit's last 50 journal lines as `SCHEDULE_JOURNAL <unit> <line>`: a product failure stays
# diagnosable after the teardown. $1 is a full unit name, suffix included.
schedules_journal() {
  schedules_tester "journalctl --user -u $1 -n 50 --no-pager" 2>&1 | sed "s/^/SCHEDULE_JOURNAL $1 /" || true
}

# Runs schedule $1 once through its installed unit $2: the service, the way its timer starts it.
schedules_run_one() {
  schedules_tester "systemctl --user start $2.service" || true # the log and the cell are the verdict
  if ! schedules_verdicts "$1"; then
    schedules_journal "$2.service"
    return 1
  fi
}

# A stub `claude` makes the claude update row available.
schedules_plant_claude() {
  # shellcheck disable=SC2016 # $HOME expands in the tester's shell
  schedules_tester 'mkdir -p "$HOME/.local/bin" && printf "#!/bin/sh\necho claude 1.0.0\n" > "$HOME/.local/bin/claude" && chmod 0755 "$HOME/.local/bin/claude"'
}

# Every available built-in once: tmp cleanup, cache cleanup and the claude update (its run may
# read `ok` or `skipped` when no owner is known, F9).
schedules_run_all() {
  local pair id rc=0
  schedules_plant_claude || return 1
  for pair in tmp-cleanup:tools-installer-prune-tmp \
    cache-cleanup:tools-installer-schedule-cache-cleanup \
    update-claude:tools-installer-schedule-update-claude; do
    id="${pair%%:*}"
    schedules_driver on "$id" || {
      rc=1
      continue
    }
    schedules_run_one "$id" "${pair#*:}" || rc=1
  done
  return "$rc"
}

# The number of start lines cache cleanup has in the tester's log.
schedules_start_count() {
  schedules_fetch_log | grep -c ' cache-cleanup start$' || true
}

# A held run lock makes a started cache cleanup log `skipped: busy`. The holder is a detached
# `flock -n <run.lock> sleep 60` as the tester, killed whatever the verdict.
schedules_busy_check() {
  local log last rc=0
  # The holder runs as a transient user unit: a background process started inside `su -` did
  # not outlive the exec session, so the runner took the lock it was meant to find held.
  schedules_tester "mkdir -p \"\$HOME/.local/state/tools-installer\"
systemd-run --user --quiet --unit=${SCHEDULES_HOLDER_UNIT} flock -n \"\$HOME/${SCHEDULES_LOCK_REL}\" sleep 60
for _ in 1 2 3 4 5 6 7 8 9 10; do flock -n \"\$HOME/${SCHEDULES_LOCK_REL}\" true || break; sleep 0.5; done" || true
  schedules_tester "systemctl --user start tools-installer-schedule-cache-cleanup.service" || true
  log="$(mktemp)"
  schedules_fetch_log >"$log" || true
  last="$(awk '$2 == "cache-cleanup" { l = $0 } END { print l }' "$log")"
  rm -f "$log"
  schedules_tester "systemctl --user stop ${SCHEDULES_HOLDER_UNIT} || true" || true
  if [[ "$last" == *"skipped: busy" ]]; then
    printf 'TRACER_SCHEDULE_BUSY_OK\n'
  else
    printf 'TRACER_SCHEDULE_BUSY_MISSING last=%s\n' "$last"
    rc=1
  fi
  return "$rc"
}

# $1 is HH:MM, $2 a number of minutes: the clock time that far ahead, wrapped at midnight.
schedules_plus_minutes() {
  local total
  total=$(((10#${1%%:*} * 60 + 10#${1##*:} + $2) % 1440))
  printf '%02d:%02d\n' $((total / 60)) $((total % 60))
}

# A calendar timer fires for real: a 1 s accuracy drop-in (systemd's default is a minute), cache
# cleanup re-timed to start two minutes ahead of the container's clock, then a poll for the new
# start line.
schedules_calendar_check() {
  local now target before attempt
  local dropin="\$HOME/.config/systemd/user/tools-installer-schedule-cache-cleanup.timer.d"
  schedules_tester "mkdir -p \"${dropin}\" && printf '[Timer]\nAccuracySec=1s\n' > \"${dropin}/e2e-accuracy.conf\" && systemctl --user daemon-reload" || return 1
  now="$(schedules_tester 'date +%H:%M' | tail -n 1)" || return 1
  if [[ ! "$now" =~ ^[0-9]{2}:[0-9]{2}$ ]]; then
    printf 'TRACER_SCHEDULE_CALENDAR_MISSING clock=%s\n' "$now"
    return 1
  fi
  target="$(schedules_plus_minutes "$now" 2)"
  before="$(schedules_start_count)"
  schedules_driver retime cache-cleanup 24 "$target" || return 1
  for ((attempt = 0; attempt < SCHEDULES_CALENDAR_ATTEMPTS; attempt++)); do
    if [[ "$(schedules_start_count)" -gt "$before" ]]; then
      printf 'TRACER_SCHEDULE_CALENDAR_OK\n'
      return 0
    fi
    sleep "$SCHEDULES_CALENDAR_STEP"
  done
  printf 'TRACER_SCHEDULE_CALENDAR_MISSING target=%s\n' "$target"
  schedules_journal tools-installer-schedule-cache-cleanup.timer
  return 1
}

# A missed slot catches up exactly once: the timer is stopped, its Persistent= stamp aged two
# days, the timer started, and the new start lines counted after the wait.
schedules_catchup_check() {
  local before runs
  local timer=tools-installer-schedule-cache-cleanup.timer
  local stamp="\$HOME/.local/share/systemd/timers/stamp-tools-installer-schedule-cache-cleanup.timer"
  schedules_tester "systemctl --user stop ${timer}" || true
  if ! schedules_tester "test -e \"${stamp}\""; then
    printf 'TRACER_SCHEDULE_STAMP_MISSING\n'
    return 1
  fi
  schedules_tester "touch -d '2 days ago' \"${stamp}\"" || return 1
  before="$(schedules_start_count)"
  schedules_tester "systemctl --user start ${timer}" || true
  sleep "$SCHEDULES_CATCHUP_WAIT"
  runs=$(($(schedules_start_count) - before))
  if [[ "$runs" -eq 1 ]]; then
    printf 'TRACER_SCHEDULE_CATCHUP_OK runs=1\n'
    return 0
  fi
  printf 'TRACER_SCHEDULE_CATCHUP_COUNT runs=%s\n' "$runs"
  schedules_journal "$timer"
  return 1
}

# Informational (RESEARCH A2): whether a plain daemon-reload plus restart keeps the timer's stamp.
schedules_stamp_observation() {
  local before after
  local timer=tools-installer-schedule-cache-cleanup.timer
  local stamp="\$HOME/.local/share/systemd/timers/stamp-tools-installer-schedule-cache-cleanup.timer"
  before="$(schedules_tester "stat -c %Y \"${stamp}\" 2>/dev/null || echo none" | tail -n 1)" || true
  schedules_tester "systemctl --user daemon-reload && systemctl --user restart ${timer}" || true
  after="$(schedules_tester "stat -c %Y \"${stamp}\" 2>/dev/null || echo none" | tail -n 1)" || true
  printf 'SCHEDULE_STAMP_MTIME before=%s after=%s\n' "$before" "$after"
  if [[ "$before" != none && "$after" != none ]]; then
    printf 'SCHEDULE_STAMP_KEPT=yes\n'
  else
    printf 'SCHEDULE_STAMP_KEPT=no\n'
  fi
}

# EXIT trap: the container and, unless --keep-image, the image go on every outcome; both removals
# tolerate absence.
schedules_teardown() {
  ct rm -f "$SCHEDULES_CONTAINER_NAME" >/dev/null 2>&1 || true
  if [[ "$SCHEDULES_KEEP_IMAGE" -ne 1 ]]; then
    ct rmi "$SCHEDULES_IMAGE" >/dev/null 2>&1 || true
  fi
  printf 'TRACER_SCHEDULES_TEARDOWN_OK\n'
}

# Every schedule the run turned on goes off through the engine: no unit file, no Persistent=
# stamp and no timer may remain. The calendar check's accuracy drop-in is the harness's own file
# and goes first.
schedules_off_check() {
  local id out line left=0 done=0
  schedules_tester "rm -rf \"\$HOME/.config/systemd/user/tools-installer-schedule-cache-cleanup.timer.d\"" || true
  for id in tmp-cleanup cache-cleanup update-claude; do
    schedules_driver off "$id" || left=1
  done
  # shellcheck disable=SC2016 # $HOME and $f expand in the tester's shell
  out="$(schedules_tester 'cd "$HOME"
for f in .config/systemd/user/tools-installer-schedule-* .config/systemd/user/tools-installer-prune-tmp* \
  .config/systemd/user/timers.target.wants/tools-installer-* \
  .local/share/systemd/timers/stamp-tools-installer-schedule-*; do
  if [ -e "$f" ] || [ -L "$f" ]; then echo "F $f"; fi
done
systemctl --user list-timers --all --no-legend 2>/dev/null | grep -E "tools-installer-(schedule-|prune-tmp)" | sed "s/^/T /" || true
echo D')" || true
  while IFS= read -r line; do
    case "$line" in
      "F "*) printf 'TRACER_SCHEDULE_OFF_LEFT path=%s\n' "${line#F }"; left=1 ;;
      "T "*) printf 'TRACER_SCHEDULE_OFF_LEFT timer=%s\n' "${line#T }"; left=1 ;;
      D) done=1 ;;
    esac
  done <<<"$out"
  if [[ "$done" -eq 0 ]]; then
    printf 'TRACER_SCHEDULE_OFF_PROBE_FAILED\n'
    return 1
  fi
  [[ "$left" -eq 0 ]] || return 1
  printf 'TRACER_SCHEDULE_OFF_OK\n'
}

# --direct (D-26's fallback, for a host that cannot run systemd in a container): a plain
# container with no units. It copies the runner and the prune scripts where the engine would, then
# runs each job the way the driver's `argv` prints it and checks the same log lines and cells.
schedules_install_assets() {
  # shellcheck disable=SC2016 # $HOME and $d expand in the tester's shell
  schedules_tester 'd="$HOME/.local/share/tools-installer/schedules"
mkdir -p "$d/lib" "$HOME/.local/state/tools-installer"
cp installer/helper_assets/schedule_runner.py "$d/runner.py"
cp scripts/prune-tmp-linux.sh scripts/prune-user-tmpdir.sh "$d/"
cp scripts/lib/prune-tmp-common.sh "$d/lib/"
chmod 0755 "$d/runner.py" "$d"/*.sh "$d/lib/prune-tmp-common.sh"'
}

schedules_direct() {
  local out id cmd line rc=0
  local -a argv
  ct rm -f "$SCHEDULES_CONTAINER_NAME" >/dev/null 2>&1 || true
  if ! out="$(ct run -d --name "$SCHEDULES_CONTAINER_NAME" "$IMAGE_FEDORA" sleep infinity 2>&1)"; then
    schedules_infeasible run "$out"
  fi
  if ! out="$(exec_root dnf install -y util-linux curl tar git python3 which procps-ng 2>&1)"; then
    schedules_infeasible dnf "$out"
  fi
  schedules_create_tester
  copy_workspace
  bootstrap_uv
  write_tester_path
  sync_workspace
  schedules_install_assets
  schedules_plant_claude
  for id in tmp-cleanup cache-cleanup update-claude; do
    argv=()
    while IFS= read -r line; do argv+=("$line"); done < <(schedules_driver argv "$id")
    printf -v cmd '%q ' ${argv[@]+"${argv[@]}"}
    schedules_tester "${cmd% }" || true # the log and the cell are the verdict
    schedules_verdicts "$id" || rc=1
  done
  printf 'SCHEDULES_GAP=no-systemd units,calendar,catch-up not exercised\n'
  if [[ "$rc" -eq 0 ]]; then
    printf 'TRACER_SCHEDULES_DIRECT_OK\n'
  fi
  return "$rc"
}

cmd_schedules() {
  local direct=0 failed=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --direct) direct=1 ;;
      --keep-image) SCHEDULES_KEEP_IMAGE=1 ;;
      *) die "unknown schedules option: $1" ;;
    esac
    shift
  done
  CONTAINER_NAME="$SCHEDULES_CONTAINER_NAME"
  TESTER_HOME="/home/$TESTER_USER"
  TESTER_WORKSPACE="$TESTER_HOME/workspace"
  PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-schedules"
  # No Homebrew in this box: a no-op stands in so the tester helpers' shellenv evals expand to nothing.
  BREW_BIN=/bin/true
  trap schedules_teardown EXIT
  ensure_phase_dir
  if [[ "$direct" -eq 1 ]]; then
    schedules_direct
    return
  fi
  schedules_start
  copy_workspace
  bootstrap_uv
  write_tester_path
  sync_workspace
  # Every verdict is collected so one transcript shows them all; turning off runs last.
  schedules_run_all || failed=1
  schedules_busy_check || failed=1
  schedules_calendar_check || failed=1
  schedules_catchup_check || failed=1
  schedules_stamp_observation
  schedules_off_check || failed=1
  return "$failed"
}

main() {
  local distro=fedora
  local -a args=()
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--distro" ]]; then
      if [[ $# -lt 2 ]]; then
        printf 'error: --distro needs a value\n' >&2
        usage >&2
        exit 2
      fi
      distro="$2"
      shift 2
    else
      args+=("$1")
      shift
    fi
  done
  select_distro "$distro"
  set -- ${args[@]+"${args[@]}"}
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    bootstrap) cmd_bootstrap "$@" ;;
    pass1) cmd_pass1 "$@" ;;
    pass2) cmd_pass2 "$@" ;;
    nvim-lsp) cmd_nvim_lsp "$@" ;;
    resync) cmd_resync "$@" ;;
    all) cmd_all "$@" ;;
    nested) cmd_nested "$@" ;;
    schedules) cmd_schedules "$@" ;;
    -h|--help) usage; exit 0 ;;
    "") usage; exit 2 ;;
    *) printf 'unknown command: %s\n' "$cmd" >&2; usage >&2; exit 2 ;;
  esac
}

main "$@"
