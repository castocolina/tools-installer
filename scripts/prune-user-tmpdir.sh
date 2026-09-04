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

if [[ -z "$TMP_ROOT" ]]; then
  printf 'error: TMPDIR empty; pass --tmpdir PATH\n' >&2
  exit 1
fi
TMP_ROOT="${TMP_ROOT%/}"
if [[ ! -d "$TMP_ROOT" ]]; then
  printf 'error: not a directory: %s\n' "$TMP_ROOT" >&2
  exit 1
fi
case "$TMP_ROOT" in
  /var|/private/var|/var/folders|/private/var/folders|"$HOME"|"$HOME"/Library|"/")
    printf 'error: refusing broad path %s\n' "$TMP_ROOT" >&2
    exit 1
    ;;
esac
if ! [[ "$DAYS" =~ ^[0-9]+$ ]] || [[ "$DAYS" -lt 1 ]]; then
  printf 'error: --days must be a positive integer\n' >&2
  exit 1
fi

HAVE_FD=0; HAVE_RG=0
command -v fd >/dev/null 2>&1 && HAVE_FD=1
command -v rg >/dev/null 2>&1 && HAVE_RG=1

human() {
  awk -v b="${1:-0}" 'BEGIN {
    split("B KB MB GB TB", u, " ")
    i = 1
    while (b >= 1024 && i < 5) { b /= 1024; i++ }
    printf "%.1f %s", b, u[i]
  }'
}

bytes_free() {
  df -P -k "$TMP_ROOT" 2>/dev/null | awk 'NR==2 {print $4 * 1024}'
}

count_fd() {
  # $1 = f|d, $2 = fd regex (only used when HAVE_FD=1)
  local ftype="$1" pat="$2"
  if [[ "$HAVE_FD" -eq 1 ]]; then
    fd -u -d 1 --changed-before "${DAYS}d" -t "$ftype" "$pat" "$TMP_ROOT" 2>/dev/null | wc -l | tr -d ' '
  else
    find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type "$ftype" -name "$pat" 2>/dev/null | wc -l | tr -d ' '
  fi
}

list_fd0() {
  # NUL-delimited paths. $1 = f|d, $2 = fd regex
  local ftype="$1" pat="$2"
  if [[ "$HAVE_FD" -eq 1 ]]; then
    fd -u -0 -d 1 --changed-before "${DAYS}d" -t "$ftype" "$pat" "$TMP_ROOT" 2>/dev/null || true
  else
    find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type "$ftype" -name "$pat" -print0 2>/dev/null || true
  fi
}

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

free_before="$(bytes_free || echo 0)"
printf '\n'
printf '  disk FREE now:        %s   ← space left on the volume (often tiny)\n' "$(human "$free_before")"

# --- Fast counts first (no big lists in memory) ---
# fd patterns: regex. find fallback uses shell globs via -name in count_fd —
# for find fallback we pass glob-ish names; for fd we pass regex.
if [[ "$HAVE_FD" -eq 1 ]]; then
  n_dylib="$(count_fd f '\.dylib$')"
  n_node="$(count_fd f '\.node$')"
  n_gitid="$(count_fd d '^gitid-(stage|e2e)-')"
  n_codex="$(count_fd d '^\.com\.openai\.codex\.')"
  sample="$(fd -u -d 1 --changed-before "${DAYS}d" -t f '\.dylib$' "$TMP_ROOT" 2>/dev/null | head -1 || true)"
else
  n_dylib="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type f -name '*.dylib' 2>/dev/null | wc -l | tr -d ' ')"
  n_node="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type f -name '*.node' 2>/dev/null | wc -l | tr -d ' ')"
  n_gitid="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type d \( -name 'gitid-stage-*' -o -name 'gitid-e2e-*' \) 2>/dev/null | wc -l | tr -d ' ')"
  n_codex="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type d -name '.com.openai.codex.*' 2>/dev/null | wc -l | tr -d ' ')"
  sample="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type f -name '*.dylib' 2>/dev/null | head -1 || true)"
fi

dylib_sz=3762984
[[ -n "$sample" ]] && dylib_sz="$(sample_bytes "$sample")"
node_sz=346272
# gitid/codex dirs are nearly empty → 4 KiB estimate each
est=$(( n_dylib * dylib_sz + n_node * node_sz + (n_gitid + n_codex) * 4096 ))
total_items=$(( n_dylib + n_node + n_gitid + n_codex ))

printf '  estimated RECLAIM:    %s   ← what this prune can free (age > %sd)\n' "$(human "$est")" "$DAYS"
printf '\n'
printf '  breakdown:\n'
printf '    OpenTUI/OpenCode dylibs: %s  (~%s)\n' "$n_dylib" "$(human $((n_dylib * dylib_sz)))"
printf '    Bun .node files:         %s\n' "$n_node"
printf '    gitid-stage/e2e dirs:    %s  (tiny each, ~%s total)\n' "$n_gitid" "$(human $((n_gitid * 4096)))"
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
  "$n_dylib_all" "$(human $((n_dylib_all * dylib_sz)))"
printf '           (only those older than %s days are in scope for this run)\n' "$DAYS"

if [[ "$APPLY" -eq 0 ]]; then
  printf '\n--- dry-run complete ---\n'
  printf 'Nothing deleted. Re-run with --apply to reclaim ~%s.\n' "$(human "$est")"
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
  local path sz
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
      printf '  ... deleted %s so far (free now: %s)\n' "$deleted" "$(human "$(bytes_free || echo 0)")"
    fi
  done
}

if [[ "$HAVE_FD" -eq 1 ]]; then
  { list_fd0 f '\.dylib$'
    list_fd0 f '\.node$'
    list_fd0 d '^gitid-(stage|e2e)-'
    list_fd0 d '^\.com\.openai\.codex\.'
  } | delete_stream
else
  {
    find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type f \( -name '*.dylib' -o -name '*.node' \) -print0 2>/dev/null || true
    find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -mtime +"$DAYS" -type d \( -name 'gitid-stage-*' -o -name 'gitid-e2e-*' -o -name '.com.openai.codex.*' \) -print0 2>/dev/null || true
  } | delete_stream
fi

free_after="$(bytes_free || echo 0)"
printf '\n--- summary ---\n'
printf 'deleted: %s\n' "$deleted"
printf 'skipped (open): %s\n' "$skipped"
printf 'failed: %s\n' "$failed"
printf 'disk free before: %s\n' "$(human "$free_before")"
printf 'disk free after:  %s\n' "$(human "$free_after")"
if [[ "$free_after" =~ ^[0-9]+$ && "$free_before" =~ ^[0-9]+$ ]]; then
  printf 'disk free delta:  %s\n' "$(human $((free_after - free_before)))"
fi
