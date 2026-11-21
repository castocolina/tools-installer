# Phase 33 Review Fix

Two pi runs on router-env/my-coding (part A 18:37 to 18:42, part B 18:43 to 18:49), the reports below, then the orchestrator's verification (`make test` after the last commit: 9142 passed, 6 skipped, coverage 96.35%; `actionlint` rerun on the fixed workflow: clean).

## Part A

| Item | Status | Commit | Note |
|---|---|---|---|
| WR-01 / lane 4 | fixed | `23c18383` | The bump step accepts the verifier's exit 1 or 2 only when its output shows the report (a `## ` heading); a launcher failure no longer ends as a silent green no-op. |
| Lane 5 | fixed | `23c18383` | The compare step reuses the bot branch only when the remote commit has exactly one parent equal to HEAD and differs from it only in `installer/registry.toml`. |
| Lane 7 | fixed | `23c18383` | A step records the exact published SHA in the tracking issue after a successful push. |
| Lane 6 | fixed (documentation) | `23c18383` | The workflow header states that only an owner push can move the bot branch between the lease and the dispatch. |
| Lane 2 | fixed (real defect) | `b9fb7347` | Reproduced exit 73 for a raw download with a configured `member`: verification recorded `member=None`, the bump lookup used the configured member. The identity is normalized in both places; a raw pinned fixture with a nonempty `member` covers it. This also fixes `verify-registry --write` for the Bruno and Ghostty AppImage pins. |
| Lane 9 | fixed | `b9fb7347` | A verified no-op candidate produces no `bumped` note under the flag. |
| Lane 13 | fixed | `b9fb7347` | `--bumps-only` without `--write` exits 64 before any file is read. |
| IN-02 | fixed | `b9fb7347` | The inline edit generator computes change detection from the candidate values; the dead clause is gone. |
| WR-04 / lane 14 | fixed | `b9fb7347` | Both fixture orders are exercised; the no-drift test starts with an old date so a flag-ignoring mutation fails it. |

## Part B

| Item | Status | Commit | Note |
|---|---|---|---|
| Lane 1 | fixed | `a7129e17` | Git keeps the literal `proof/target-$DATE`; every REST path uses the encoded form. |
| WR-02 | fixed | `a7129e17` | The "must skip" check reads the `skipped` conclusion of the publish step, not the run log. |
| WR-03 | fixed | `cb2dc1b5` | Option A reads `main`'s whole protection, maps the known settings onto the throwaway branch, STOPS on an unmappable enabled setting and compares the read-back. |
| Lane 3 | fixed | `cb2dc1b5` | The preflight also stops on a queued or running bot run; cleanup waits for the proof's runs to complete. |
| Lane 12 | fixed | `cb2dc1b5` | The fetch and push URLs of `origin` are verified against the repository and every `gh` command is explicit. |
| IN-04, IN-09 | fixed | `cb2dc1b5` | `while read` loops, a subshell-scoped `pipefail`, the writes table names the push-event CI runs. |
| Lane 11 | fixed | `cb2dc1b5` | The landing commands stop on a failed lookup, count the latest conclusion per check, preserve the push status and force-remove the worktree. |
| IN-08, IN-01 | fixed | `cb2dc1b5` | Dependabot handling and the README layout line corrected. |
