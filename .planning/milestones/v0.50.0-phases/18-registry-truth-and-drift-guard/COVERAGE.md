# API Coverage — GitHub REST API (releases, issues) and GitHub Actions cache

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Scope: Phase 18 reads release metadata and assets (install-time verification, version
> refresh, verify-registry) and reports drift as one issue from a scheduled job.

| capability | decision | reason |
|---|---|---|
| releases/latest: tag and per-asset sha256 digests in one read | INTEGRATE | |
| release asset download and HEAD fingerprint | INTEGRATE | |
| token auth (GITHUB_TOKEN/GH_TOKEN, api.github.com only) | INTEGRATE | |
| rate-limit and network errors reported as inconclusive | INTEGRATE | |
| issues: list the open issue labelled registry-drift | INTEGRATE | |
| issues: create with label and body file | INTEGRATE | |
| issues: edit body of the open drift issue | INTEGRATE | |
| labels: create or update registry-drift | INTEGRATE | |
| Actions cache for the verify-registry state file | INTEGRATE | |
| releases by tag in code | OPT-OUT | not needed: pins are compared with the latest stable only; the one per-tag read is a maintainer `gh api` step in plan 18-15 |
| releases list including pre-releases | OPT-OUT | explicitly out of scope: D-09 bumps only to the latest stable release |
| issues: close when a later run is clean | OPT-OUT | not needed yet: SPEC R3 asks to open or update one issue; the maintainer closes it after fixing |
| pull requests: open a bump PR from the job | OPT-OUT | explicitly out of scope: D-08 keeps the job read-only (contents: read, no push, no PR) |
| conditional API requests (ETag) | OPT-OUT | not needed: a weekly run fits the authenticated 5000 requests/h budget; a rate limit is reported as inconclusive |
| GraphQL API | OPT-OUT | not needed: the REST latest-release response already carries the tag and every digest |
