#!/usr/bin/env bash
# prune-user-tmpdir.sh — reclaim user $TMPDIR junk left by agent runtimes.
#
# Why this exists:
#   Apple's com.apple.tmp_cleaner only sweeps /tmp, NOT $TMPDIR
#   (/var/folders/.../T on macOS). OpenCode/OpenTUI, gitid tests, Codex, etc.
#   leave files there; the kernel does not delete them when the process exits.
#   OpenGSD may spawn Claude / OpenCode / Codex / etc.; they share $TMPDIR.
#
# Prefers fd + rg from the tools-installer catalog; falls back to find/grep.
#
# IMPORTANT — "disk free before" is FREE SPACE LEFT on the volume (often tiny
# when the disk is full). "estimated reclaim" is how much this prune can free.
#
# 15.7-07 (D-01d): the broad-path refusal guard, root/age validation, the
# fd-preferred/find-fallback traversal, the byte formatter, and the trailing
# `deleted: N` line now live in scripts/lib/prune-tmp-common.sh, shared with
# scripts/prune-tmp-linux.sh. This script owns only its own flags, its own
# 3-day default, its own five target families, its own extra refusal
# entries, and the lsof-based open-file skip that has no Linux counterpart.
# Its --days flag, default and argv contract are UNCHANGED: the shipped
# macOS LaunchAgent already invokes this exact grammar through
# installer/helper_assets/prune_daemon_runner.py.
#
# Usage:
#   ./scripts/prune-user-tmpdir.sh              # dry-run (safe)
#   ./scripts/prune-user-tmpdir.sh --apply      # delete orphans older than 3d
#   ./scripts/prune-user-tmpdir.sh --days 1 --apply

set -euo pipefail

DAYS=3
APPLY=0
TMP_ROOT="${TMPDIR:-}"
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: prune-user-tmpdir.sh [options]

  --dry-run          Report only (default)
  --apply            Actually delete matching orphans
  --days N           Minimum age in days (default: 3)
  --tmpdir PATH      Override target (default: $TMPDIR)
  --verbose          Print each deleted path
  -h, --help         Show this help

Targets (depth 1, mtime older than N days, not open in lsof):
  *.dylib   OpenTUI/Bun extracts from OpenCode (~3.6 MB each)
  *.node    Bun native addons
  gitid-stage-* / gitid-e2e-*   gitid test temp dirs
  .com.openai.codex.*           Codex temp dirs

Note: "disk free" = space left NOW. "estimated reclaim" = what we can free.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) APPLY=0; shift ;;
    --apply) APPLY=1; shift ;;
    --days) DAYS="${2:?}"; shift 2 ;;
    --days=*) DAYS="${1#*=}"; shift ;;
    --tmpdir) TMP_ROOT="${2:?}"; shift 2 ;;
    --tmpdir=*) TMP_ROOT="${1#*=}"; shift ;;
    --verbose|-v) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

_PRUNE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/prune-tmp-common.sh
source "${_PRUNE_LIB_DIR}/lib/prune-tmp-common.sh"

_prune_common_require_nonempty "$TMP_ROOT" TMPDIR
# Before the strip and before the canonicalizing refusal guard: a relative
# root would otherwise be resolved against this process's cwd (lane-2 LOW-02).
# "/" is absolute, so it passes here and still reaches the strip-to-empty
# quirk documented immediately below, unchanged.
_prune_common_require_absolute "$TMP_ROOT"
# NOTE: unlike scripts/prune-tmp-linux.sh, this strip is unconditional --
# `--tmpdir /` therefore becomes an EMPTY string here, which the directory
# check below rejects as "not a directory" rather than reaching the refusal
# guard. That is the script's own pre-existing behavior (pinned by
# tests/test_prune_user_tmpdir_sh.py::test_refuses_root_via_not_a_directory_quirk)
# and this extraction preserves it exactly rather than "fixing" it.
TMP_ROOT="$(_prune_common_strip_trailing_slash "$TMP_ROOT")"
_prune_common_require_directory "$TMP_ROOT"
_prune_common_refuse_broad_path "$TMP_ROOT" "/" "$HOME" /var /private/var /var/folders /private/var/folders "$HOME/Library"
_prune_common_validate_positive_int "$DAYS" days
# 10#$DAYS forces base-10 arithmetic: a leading-zero DAYS value (e.g. "010")
# would otherwise be parsed as octal by bash's `$(( ))`.
MINUTES=$((10#$DAYS * 1440))

HAVE_FD=0; HAVE_RG=0
command -v fd >/dev/null 2>&1 && HAVE_FD=1
command -v rg >/dev/null 2>&1 && HAVE_RG=1

sample_bytes() {
  local p="$1" out
  if out="$(stat -f%z "$p" 2>/dev/null)"; then printf '%s\n' "$out"
  elif out="$(stat -c%s "$p" 2>/dev/null)"; then printf '%s\n' "$out"
  else printf '0\n'; fi
}

mode="dry-run"; [[ "$APPLY" -eq 1 ]] && mode="APPLY"

printf 'prune-user-tmpdir\n'
printf '  mode:     %s\n' "$mode"
printf '  days:     %s\n' "$DAYS"
printf '  target:   %s\n' "$TMP_ROOT"
printf '  tooling:  fd=%s rg=%s\n' \
  "$([[ $HAVE_FD -eq 1 ]] && echo yes || echo no)" \
  "$([[ $HAVE_RG -eq 1 ]] && echo yes || echo no)"

free_before="$(_prune_common_bytes_free "$TMP_ROOT" || echo 0)"
printf '\n'
printf '  disk FREE now:        %s   ← space left on the volume (often tiny)\n' "$(_prune_common_human "$free_before")"

# --- Fast counts first (no big lists in memory) ---
n_dylib="$(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" f name '*.dylib' '\.dylib$' | wc -l | tr -d ' ')"
n_node="$(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" f name '*.node' '\.node$' | wc -l | tr -d ' ')"
n_gitid_stage="$(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" d name 'gitid-stage-*' '^gitid-stage-' | wc -l | tr -d ' ')"
n_gitid_e2e="$(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" d name 'gitid-e2e-*' '^gitid-e2e-' | wc -l | tr -d ' ')"
n_gitid=$((n_gitid_stage + n_gitid_e2e))
n_codex="$(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" d name '.com.openai.codex.*' '^\.com\.openai\.codex\.' | wc -l | tr -d ' ')"
sample="$(_prune_common_find_matches "$TMP_ROOT" "$MINUTES" f name '*.dylib' '\.dylib$' | head -1 || true)"

dylib_sz=3762984
[[ -n "$sample" ]] && dylib_sz="$(sample_bytes "$sample")"
node_sz=346272
# gitid/codex dirs are nearly empty → 4 KiB estimate each
est=$(( n_dylib * dylib_sz + n_node * node_sz + (n_gitid + n_codex) * 4096 ))
total_items=$(( n_dylib + n_node + n_gitid + n_codex ))

printf '  estimated RECLAIM:    %s   ← what this prune can free (age > %sd)\n' "$(_prune_common_human "$est")" "$DAYS"
printf '\n'
printf '  breakdown:\n'
printf '    OpenTUI/OpenCode dylibs: %s  (~%s)\n' "$n_dylib" "$(_prune_common_human $((n_dylib * dylib_sz)))"
printf '    Bun .node files:         %s\n' "$n_node"
printf '    gitid-stage/e2e dirs:    %s  (tiny each, ~%s total)\n' "$n_gitid" "$(_prune_common_human $((n_gitid * 4096)))"
printf '    Codex temp dirs:         %s\n' "$n_codex"
printf '    total items:             %s\n' "$total_items"

# Also show full dylib pile (including younger than --days) for context.
if [[ "$HAVE_FD" -eq 1 ]]; then
  n_dylib_all="$(fd -u -d 1 -t f '\.dylib$' "$TMP_ROOT" 2>/dev/null | wc -l | tr -d ' ')"
else
  n_dylib_all="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -type f -name '*.dylib' 2>/dev/null | wc -l | tr -d ' ')"
fi
printf '\n'
printf '  context: ALL dylibs in TMPDIR (any age): %s (~%s)\n' \
  "$n_dylib_all" "$(_prune_common_human $((n_dylib_all * dylib_sz)))"
printf '           (only those older than %s days are in scope for this run)\n' "$DAYS"

if [[ "$APPLY" -eq 0 ]]; then
  printf '\n--- dry-run complete ---\n'
  printf 'Nothing deleted. Re-run with --apply to reclaim ~%s.\n' "$(_prune_common_human "$est")"
  printf 'Tip: with the disk this full, close OpenCode first, then:\n'
  printf '  bash scripts/prune-user-tmpdir.sh --apply\n'
  exit 0
fi

# --- APPLY: stream deletes with fd/find -0 + xargs; skip open files via lsof set ---
OPEN_LIST="$(mktemp -t prune-tmpdir-open.XXXXXX)"
trap 'rm -f "$OPEN_LIST"' EXIT

if command -v lsof >/dev/null 2>&1; then
  lsof -nP -F n 2>/dev/null \
    | sed -n 's/^n//p' \
    | if [[ "$HAVE_RG" -eq 1 ]]; then rg -F "$TMP_ROOT/" || true
      else grep -F "$TMP_ROOT/" || true; fi \
    | sort -u >"$OPEN_LIST" || true
else
  : >"$OPEN_LIST"
fi
open_n="$(wc -l <"$OPEN_LIST" | tr -d ' ')"
printf '\nApplying delete (skipping %s open paths)...\n' "$open_n"

deleted=0
skipped=0
failed=0

delete_stream() {
  # Reads NUL paths on stdin.
  local path
  while IFS= read -r -d '' path; do
    [[ -z "$path" ]] && continue
    if [[ -s "$OPEN_LIST" ]] && grep -Fxq -- "$path" "$OPEN_LIST"; then
      skipped=$((skipped + 1))
      [[ "$VERBOSE" -eq 1 ]] && printf '  skip open: %s\n' "$path"
      continue
    fi
    if [[ -d "$path" && ! -L "$path" ]]; then
      if rm -rf -- "$path" 2>/dev/null; then
        deleted=$((deleted + 1))
        [[ "$VERBOSE" -eq 1 ]] && printf '  deleted dir: %s\n' "$path"
      else
        failed=$((failed + 1))
      fi
    else
      if rm -f -- "$path" 2>/dev/null; then
        deleted=$((deleted + 1))
        [[ "$VERBOSE" -eq 1 ]] && printf '  deleted file: %s\n' "$path"
      else
        failed=$((failed + 1))
      fi
    fi
    # Progress every 2000 items so a kill mid-way still shows work done.
    if (( deleted % 2000 == 0 && deleted > 0 )); then
      printf '  ... deleted %s so far (free now: %s)\n' "$deleted" "$(_prune_common_human "$(_prune_common_bytes_free "$TMP_ROOT" || echo 0)")"
    fi
  done
}

# 15.7-07 (Rule 1 bug fix): the shipped script fed this same NUL stream into
# delete_stream through a PIPE (`{ ...; } | delete_stream`). Bash runs every
# pipeline stage, including the last, in its own subshell unless
# `shopt -s lastpipe` is set (it never was), so delete_stream's own
# deleted/skipped/failed increments were silently discarded once the
# pipeline exited -- the shipped `deleted: N` line always read 0 regardless
# of real work done (see tests/test_prune_user_tmpdir_sh.py::
# test_deleted_line_is_stuck_at_zero_due_to_a_pipeline_subshell_bug for the
# live characterization of that bug against the unmodified script).
# Redirecting the process substitution into delete_stream's STDIN instead of
# piping into it keeps delete_stream running in THIS shell -- input
# redirection does not fork a subshell the way a pipe does -- so its
# counters are real.
delete_stream < <(
  _prune_common_find_matches0 "$TMP_ROOT" "$MINUTES" f name '*.dylib' '\.dylib$'
  _prune_common_find_matches0 "$TMP_ROOT" "$MINUTES" f name '*.node' '\.node$'
  _prune_common_find_matches0 "$TMP_ROOT" "$MINUTES" d name 'gitid-stage-*' '^gitid-stage-'
  _prune_common_find_matches0 "$TMP_ROOT" "$MINUTES" d name 'gitid-e2e-*' '^gitid-e2e-'
  _prune_common_find_matches0 "$TMP_ROOT" "$MINUTES" d name '.com.openai.codex.*' '^\.com\.openai\.codex\.'
)

free_after="$(_prune_common_bytes_free "$TMP_ROOT" || echo 0)"
printf '\n--- summary ---\n'
_prune_common_emit_deleted "$deleted"
printf 'skipped (open): %s\n' "$skipped"
printf 'failed: %s\n' "$failed"
printf 'disk free before: %s\n' "$(_prune_common_human "$free_before")"
printf 'disk free after:  %s\n' "$(_prune_common_human "$free_after")"
if [[ "$free_after" =~ ^[0-9]+$ && "$free_before" =~ ^[0-9]+$ ]]; then
  printf 'disk free delta:  %s\n' "$(_prune_common_human $((free_after - free_before)))"
fi
