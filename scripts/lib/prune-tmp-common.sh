#!/usr/bin/env bash
# scripts/lib/prune-tmp-common.sh -- shared prune engine, sourced only.
#
# 15.7-07 (D-01d): one implementation of the broad-path refusal guard, the
# root/age validation, the depth-1 fd-preferred/find-fallback traversal, the
# human-readable byte formatter and the trailing `deleted: N` summary line --
# shared by scripts/prune-tmp-linux.sh and scripts/prune-user-tmpdir.sh, which
# each supply only their own match patterns, default age and help text (the
# per-platform DATA, not the LOGIC).
#
# D-01f: every age filter in this file is MINUTES-based duration arithmetic
# -- `-mmin +N` on the find branch, `--changed-before Nmin` on the fd branch
# -- and the two agree (modulo the sub-minute rounding `-mmin` shares with
# any minute-granularity filter). `-mtime` never appears here: `-mtime +N`
# truncates the file's age to whole 24-hour periods before comparing, so it
# silently means "older than (N+1)*24h" and would disagree with the fd
# branch beside it by up to a full day -- precisely the pre-existing
# fd/find inconsistency D-01f exists to remove. See 15.7-07-PLAN.md.
#
# This file defines functions only. Sourcing it does nothing on its own;
# executing it directly (`./prune-tmp-common.sh`) exits 0 immediately,
# defining nothing and touching nothing (T-15.7-49).

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  exit 0
fi

# --- validation --------------------------------------------------------------

# _prune_common_require_nonempty VALUE LABEL
# Exits 1 with "error: LABEL empty; pass --tmpdir PATH" if VALUE is empty.
# LABEL is caller-supplied so each wrapper keeps its own existing wording
# (the macOS script says "TMPDIR empty", the Linux script says "tmpdir
# empty" -- a pre-existing difference this extraction does not paper over).
_prune_common_require_nonempty() {
  local value="$1" label="$2"
  if [[ -z "$value" ]]; then
    printf 'error: %s empty; pass --tmpdir PATH\n' "$label" >&2
    exit 1
  fi
}

# _prune_common_strip_trailing_slash VALUE
# Prints VALUE with exactly one trailing "/" removed (mirrors bash's plain
# "${value%/}"). Deliberately does NOT special-case "/" itself (which this
# strips to an empty string) -- scripts/prune-user-tmpdir.sh's pre-existing
# behavior for `--tmpdir /` (caught by the "not a directory" check rather
# than the refusal guard, because "/" stripped is "") is a frozen
# characterization (tests/test_prune_user_tmpdir_sh.py::
# test_refuses_root_via_not_a_directory_quirk) that this extraction must not
# change. A caller that needs "/" to survive as "/" (scripts/prune-tmp-linux.sh)
# special-cases it itself before calling this, exactly as it already did.
_prune_common_strip_trailing_slash() {
  printf '%s' "${1%/}"
}

# _prune_common_require_directory ROOT
# Exits 1 with "error: not a directory: ROOT" if ROOT is not a directory.
_prune_common_require_directory() {
  local root="$1"
  if [[ ! -d "$root" ]]; then
    printf 'error: not a directory: %s\n' "$root" >&2
    exit 1
  fi
}

# _prune_common_refuse_broad_path ROOT ENTRY...
# Exits 1 with "error: refusing broad path ROOT" if ROOT literally equals
# any of the following ENTRY arguments (the caller's own base + extra
# refusal list; trailing slashes must already be stripped by the caller
# before this runs, per each wrapper's own original check ordering).
_prune_common_refuse_broad_path() {
  local root="$1"
  shift
  local entry
  for entry in "$@"; do
    if [[ "$root" == "$entry" ]]; then
      printf 'error: refusing broad path %s\n' "$root" >&2
      exit 1
    fi
  done
}

# _prune_common_validate_positive_int VALUE FLAG_NAME
# Exits 1 with "error: --FLAG_NAME must be a positive integer" unless VALUE
# is a base-10 positive integer.
_prune_common_validate_positive_int() {
  local value="$1" flag="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]] || [[ "$value" -lt 1 ]]; then
    printf 'error: --%s must be a positive integer\n' "$flag" >&2
    exit 1
  fi
}

# _prune_common_escape_dots VALUE
# Prints VALUE with every "." backslash-escaped, for embedding a real
# filesystem path inside a POSIX ERE (find -regextype posix-extended) as a
# literal path rather than "any character" wildcards.
_prune_common_escape_dots() {
  printf '%s' "${1//./\\.}"
}

# --- reporting -----------------------------------------------------------

# _prune_common_human BYTES
# Prints BYTES formatted as the nearest B/KB/MB/GB/TB, one decimal place.
_prune_common_human() {
  awk -v b="${1:-0}" 'BEGIN {
    split("B KB MB GB TB", u, " ")
    i = 1
    while (b >= 1024 && i < 5) { b /= 1024; i++ }
    printf "%.1f %s", b, u[i]
  }'
}

# _prune_common_bytes_free ROOT
# Prints the free bytes on the volume containing ROOT (0 on failure).
_prune_common_bytes_free() {
  local root="$1"
  df -P -k "$root" 2>/dev/null | awk 'NR==2 {print $4 * 1024}'
}

# _prune_common_emit_deleted N
# Prints the exact "deleted: N" line installer.daemon.last_run_summary
# parses for the Policies "last run" detail. The ONLY line this extraction
# guarantees identical in shape from both wrappers -- everything around it
# (headers, breakdowns, disk-free stats) stays wrapper-owned.
_prune_common_emit_deleted() {
  printf 'deleted: %s\n' "$1"
}

# --- traversal -------------------------------------------------------------

# _prune_common_find_matches ROOT MINUTES FTYPE MODE PATTERN [FD_PATTERN]
# Newline-delimited matches on stdout, depth 1 under ROOT, older than
# MINUTES. FTYPE is "f", "d", or "" (no -type predicate, matching
# scripts/prune-tmp-linux.sh's original find call, which never specified
# one). MODE is "name" (PATTERN is a find -name glob, matched against the
# basename -- scripts/prune-user-tmpdir.sh's own find-fallback style,
# reused verbatim) or "regex" (PATTERN is a full-path POSIX ERE already
# anchored to ROOT by the caller -- scripts/prune-tmp-linux.sh's own style).
# FD_PATTERN, when non-empty AND `fd` resolves on PATH, is preferred over
# find entirely (fd's own basename regex syntax); passing "" for FD_PATTERN
# means "never use fd for this call", which is how the Linux wrapper keeps
# its original find-only behavior regardless of what happens to be on PATH.
#
# Safe for fast counts (pipe to `wc -l`) and for consumers -- like
# scripts/prune-tmp-linux.sh's own `mapfile -t` -- that only ever see
# filenames without embedded newlines. Use _prune_common_find_matches0 for
# an actual deletion stream instead.
_prune_common_find_matches() {
  local root="$1" minutes="$2" ftype="$3" mode="$4" pattern="$5" fd_pattern="${6:-}"
  local -a find_type=()
  [[ -n "$ftype" ]] && find_type=(-type "$ftype")

  if [[ -n "$fd_pattern" ]] && command -v fd >/dev/null 2>&1; then
    local -a fd_type=()
    [[ -n "$ftype" ]] && fd_type=(-t "$ftype")
    fd -u -d 1 --changed-before "${minutes}min" "${fd_type[@]}" "$fd_pattern" "$root" 2>/dev/null || true
    return 0
  fi

  if [[ "$mode" == "regex" ]]; then
    find "$root" -mindepth 1 -maxdepth 1 -regextype posix-extended -regex "$pattern" \
      -mmin +"$minutes" "${find_type[@]}" 2>/dev/null || true
  else
    find "$root" -mindepth 1 -maxdepth 1 -mmin +"$minutes" "${find_type[@]}" \
      -name "$pattern" 2>/dev/null || true
  fi
}

# _prune_common_find_matches0 ROOT MINUTES FTYPE MODE PATTERN [FD_PATTERN]
# Same matching as _prune_common_find_matches, NUL-delimited on stdout --
# for a deletion stream that must not break on a path containing a newline
# (scripts/prune-user-tmpdir.sh's original `delete_stream` convention).
_prune_common_find_matches0() {
  local root="$1" minutes="$2" ftype="$3" mode="$4" pattern="$5" fd_pattern="${6:-}"
  local -a find_type=()
  [[ -n "$ftype" ]] && find_type=(-type "$ftype")

  if [[ -n "$fd_pattern" ]] && command -v fd >/dev/null 2>&1; then
    local -a fd_type=()
    [[ -n "$ftype" ]] && fd_type=(-t "$ftype")
    fd -u -0 -d 1 --changed-before "${minutes}min" "${fd_type[@]}" "$fd_pattern" "$root" 2>/dev/null || true
    return 0
  fi

  if [[ "$mode" == "regex" ]]; then
    find "$root" -mindepth 1 -maxdepth 1 -regextype posix-extended -regex "$pattern" \
      -mmin +"$minutes" "${find_type[@]}" -print0 2>/dev/null || true
  else
    find "$root" -mindepth 1 -maxdepth 1 -mmin +"$minutes" "${find_type[@]}" \
      -name "$pattern" -print0 2>/dev/null || true
  fi
}
