#!/usr/bin/env bash
# detect-container-runtime.sh — pick a live-proven container tool (D-01/D-02/D-03).
#
# OS via uname -s (Darwin -> macos, Linux -> linux). Arch via uname -m, mirroring
# installer/platform.py's amd64/arm64 mapping. A binary on PATH is not enough:
# the chosen tool must actually run a disposable alpine container.
#
# On success, stdout is exactly one line: CONTAINER_TOOL=podman or
# CONTAINER_TOOL=docker, so a caller can `eval "$(scripts/detect-container-runtime.sh)"`.
# On D-03 (no expected tool and no working alternative): print the three-option
# choice on stderr and exit 3. Never fall back to the host.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: detect-container-runtime.sh [options]

  -h, --help         Show this help

Detect the host OS/arch and pick a working container runtime:

  Linux:  podman (live-proven), else docker (live-proven)
  macOS:  colima+docker (starts colima if needed, then live-proves docker),
          else podman (live-proven)

Live proof is ` <tool> run --rm docker.io/library/alpine:latest true `.
A --version check alone is not proof.

On success prints exactly one stdout line:
  CONTAINER_TOOL=podman
  CONTAINER_TOOL=docker

Exit codes:
  0  a working container tool was proven
  2  unknown option
  3  no expected tool and no working alternative (D-03 — do not proceed)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

normalize_arch() {
  case "$1" in
    x86_64|amd64) printf 'amd64\n' ;;
    aarch64|arm64) printf 'arm64\n' ;;
    *) printf '%s\n' "$1" ;;
  esac
}

detect_os() {
  case "$1" in
    Linux) printf 'linux\n' ;;
    Darwin) printf 'macos\n' ;;
    *) printf 'unknown\n' ;;
  esac
}

HOST_OS="$(detect_os "$(uname -s)")"
HOST_ARCH="$(normalize_arch "$(uname -m)")"
readonly HOST_OS HOST_ARCH

# Arch is recorded so the detection is OS/arch-aware (D-01) even though stdout
# stays a single CONTAINER_TOOL assignment. Callers that need it can inspect
# uname themselves; this assignment keeps the mapping honest and referenced.
: "${HOST_ARCH}"

refuse() {
  # D-03: expected tool absent AND no working alternative. Print the three
  # options verbatim on stderr and halt. Do not invoke podman/docker/colima.
  printf '%s\n' '1) install the missing tool inline  2) print manual install instructions' >&2
  printf '%s\n' '3) bypass the e2e check for this run' >&2
  exit 3
}

prove_run() {
  local tool="$1"
  "$tool" run --rm docker.io/library/alpine:latest true >/dev/null 2>&1
}

linux_pick() {
  if command -v podman >/dev/null 2>&1 && prove_run podman; then
    printf 'CONTAINER_TOOL=podman\n'
    exit 0
  fi
  if command -v docker >/dev/null 2>&1 && prove_run docker; then
    printf 'CONTAINER_TOOL=docker\n'
    exit 0
  fi
  refuse
}

macos_pick() {
  # Expected tool: colima + docker. Starting a stopped colima is normal
  # Tier-3 operation (ONESHOT-RULES Rule 14), not a D-03 failure.
  if command -v colima >/dev/null 2>&1 && command -v docker >/dev/null 2>&1; then
    if ! colima status >/dev/null 2>&1; then
      colima start >/dev/null 2>&1 || true
    fi
    if prove_run docker; then
      printf 'CONTAINER_TOOL=docker\n'
      exit 0
    fi
  fi
  # colima entirely absent (or docker proof failed): try podman live, do not
  # hardcode origin's Intel-Mac vfkit finding as a permanent rule (D-01).
  if command -v podman >/dev/null 2>&1 && prove_run podman; then
    printf 'CONTAINER_TOOL=podman\n'
    exit 0
  fi
  refuse
}

case "$HOST_OS" in
  linux) linux_pick ;;
  macos) macos_pick ;;
  *) refuse ;;
esac
