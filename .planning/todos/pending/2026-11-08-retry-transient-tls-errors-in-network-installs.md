---
created: 2026-11-08
source: Phase 23.2 container e2e #2 (EXIT=2) and UAT O-5
priority: medium
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
