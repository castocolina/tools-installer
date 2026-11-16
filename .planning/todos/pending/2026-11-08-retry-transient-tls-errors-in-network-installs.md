---
created: 2026-11-08
source: Phase 23.2 container e2e #2 (EXIT=2) and UAT O-5
priority: medium
audit_acknowledged:
  milestone: v0.50.0
  at: 2026-11-16
---

# Retry transient TLS errors in network installs

## Problem

On this host's connection, `curl` fails intermittently with exit 35
(`TLS connect error: error:0A000126:SSL routines::unexpected eof while reading`). In the 23.2 e2e #2 two
installs failed this way (claude's `curl -fsSL https://claude.ai/install.sh | bash` and the jetbrains-toolbox
download), so the whole container run failed on the network, not on the product. The UAT saw three claude
attempts fail before the fourth passed. A user on a flaky network gets a `failed` row for a transient error.

## Solution

Retry a download or script fetch a small bounded number of times with backoff, only for curl's
transient connection exit codes (e.g. 6, 7, 28, 35, 52, 56), never for HTTP errors or checksum
mismatches. Prefer `curl --retry N --retry-connrefused --retry-all-errors` where the command is built by the
installer; for vendor `curl | bash` scripts, fetch the script with retry to a temp file first, then run it.
Backstop: a test with a fake curl that fails once with 35 and then succeeds.

## Status (2026-11-16)

Triage at b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`), verdict partial.

- Done: vendor script fetches go to a temp file with `curl -fsSL --retry 3 --retry-all-errors` (`installer/executors.py:488`, 31243588). The fake-curl tests are at `tests/test_engine.py:2542-2560`.
- Left: retry for github_release/tarball downloads (`installer/download.py:473`, `:478`) and app downloads (`installer/apps.py:132`), which still run plain `curl -fsSL`. Example: the jetbrains-toolbox download. The curl >= 7.71 probe is tracked in the Phase 24 review deferrals todo.
