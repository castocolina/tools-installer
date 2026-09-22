#!/usr/bin/env bash
# prune-tmp-linux.sh — reclaim orphaned Bun runtime-transpiler-cache files
# from a Linux temp directory.
#
# Why this exists:
#   Bun (used by opencode / GSD cross-AI runs) writes its runtime transpiler
#   cache (native .so/.node artifacts) either to
#   $BUN_RUNTIME_TRANSPILER_CACHE_PATH, or -- for invocations that don't
#   inherit that env var (see oven-sh/bun#24695) -- straight into the OS temp
#   dir as .{16 hex}-{8 digit}.so / .node. Bun unlinks these on clean exit; a
#   killed/crashed process orphans them, silently filling /tmp's tmpfs quota
#   (EDQUOT) and breaking anything else needing mktemp/writes there.
#
# Ported from ai-kit's cleanup-bun-tmp-cache.sh (confirmed-working baseline:
# kept /tmp under 1% usage on this host) -- same regex/matching logic,
# generalized into this project's --dry-run/--apply/--tmpdir/--minutes
# ergonomics, mirroring scripts/prune-user-tmpdir.sh's own flag grammar and
# broad-path refusal.
#
# Usage:
#   ./scripts/prune-tmp-linux.sh              # dry-run (safe)
#   ./scripts/prune-tmp-linux.sh --apply      # delete orphans older than 10min
#   ./scripts/prune-tmp-linux.sh --minutes 5 --apply

set -euo pipefail

MINUTES=10
APPLY=0
TMP_ROOT="${TMPDIR:-/tmp}"
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: prune-tmp-linux.sh [options]

  --dry-run          Report only (default)
  --apply            Actually delete matching orphans
  --minutes N        Minimum age in minutes (default: 10)
  --tmpdir PATH      Override target (default: $TMPDIR or /tmp)
  --verbose          Print each deleted path
  -h, --help         Show this help

Target (depth 1, mtime older than N minutes):
  .{16 hex}-{8 digit}.so    Bun runtime-transpiler-cache shared objects
  .{16 hex}-{8 digit}.node  Bun native addons

Prints a final "deleted: N" line, the exact prefix
installer.daemon.last_run_summary parses for the Policies "last run" detail.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) APPLY=0; shift ;;
    --apply) APPLY=1; shift ;;
    --minutes) MINUTES="${2:?}"; shift 2 ;;
    --minutes=*) MINUTES="${1#*=}"; shift ;;
    --tmpdir) TMP_ROOT="${2:?}"; shift 2 ;;
    --tmpdir=*) TMP_ROOT="${1#*=}"; shift ;;
    --verbose|-v) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$TMP_ROOT" ]]; then
  printf 'error: tmpdir empty; pass --tmpdir PATH\n' >&2
  exit 1
fi
# Strip a trailing slash, but "/" itself must stay "/" (not become empty) so
# the broad-path refusal below still recognizes it.
if [[ "$TMP_ROOT" != "/" ]]; then
  TMP_ROOT="${TMP_ROOT%/}"
fi
case "$TMP_ROOT" in
  /|/var|/private/var|"$HOME")
    printf 'error: refusing broad path %s\n' "$TMP_ROOT" >&2
    exit 1
    ;;
esac
if [[ ! -d "$TMP_ROOT" ]]; then
  printf 'error: not a directory: %s\n' "$TMP_ROOT" >&2
  exit 1
fi
if ! [[ "$MINUTES" =~ ^[0-9]+$ ]] || [[ "$MINUTES" -lt 1 ]]; then
  printf 'error: --minutes must be a positive integer\n' >&2
  exit 1
fi

mode="dry-run"; [[ "$APPLY" -eq 1 ]] && mode="APPLY"

printf 'prune-tmp-linux\n'
printf '  mode:     %s\n' "$mode"
printf '  minutes:  %s\n' "$MINUTES"
printf '  target:   %s\n' "$TMP_ROOT"

# Escape regex metacharacters that could appear in TMP_ROOT (only "." is
# realistically present in a real temp path) so the anchor is matched
# literally, not interpreted as "any character".
root_escaped="${TMP_ROOT//./\\.}"

mapfile -t files < <(find "$TMP_ROOT" -maxdepth 1 \
    -regextype posix-extended \
    -regex "${root_escaped}/\.[0-9a-f]{16}-[0-9]{8}\.(so|node)" \
    -mmin +"$MINUTES" 2>/dev/null)

if [[ "$APPLY" -eq 0 ]]; then
  printf '\n  matches: %s\n' "${#files[@]}"
  for f in "${files[@]}"; do
    printf '  would delete: %s\n' "$f"
  done
  printf '\n--- dry-run complete ---\n'
  printf 'Nothing deleted. Re-run with --apply to reclaim.\n'
  printf 'deleted: 0\n'
  exit 0
fi

deleted=0
for f in "${files[@]}"; do
  if rm -f -- "$f"; then
    deleted=$((deleted + 1))
    [[ "$VERBOSE" -eq 1 ]] && printf '  deleted: %s\n' "$f"
  fi
done

printf '\n--- summary ---\n'
printf 'deleted: %s\n' "$deleted"
