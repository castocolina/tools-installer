---
name: catalog-audit
description: Use when auditing every installer/registry.toml entry against upstream in one resumable loop - latest versions from several sources, vendor changelogs, install method, update argv, removal recipe and paths, tuning keys, postinstall hook and the installer's script surfaces - written as one report per entry plus a summary of proposed changes. Keywords - catalog audit, registry drift, outdated install method, changelog review. Not for onboarding one new tool (tool-onboarding) or only checking release assets and pins (make verify-registry).
---

# Catalog audit

## Overview

A PROCESS aid. The agent judges; `installer/catalog_audit.py` gathers facts and records
results. Nothing outside `.planning/audits/catalog/<date>/` changes without the user's
explicit approval.

- Per-entry criteria come from `.claude/skills/tool-onboarding/SKILL.md`, by step heading.
- Downloadable methods (release assets, tarballs, apps) take `make verify-registry`'s record
  as their result; the audit never re-checks them itself.
- The tool reads facts (`make audit-catalog`), the agent writes reports from a template,
  the tool validates and stores them.

## When to Use

- A periodic or pre-release sweep of the whole registry against upstream.
- Resuming an interrupted sweep: the run directory is the state.

## Steps

All commands are `make audit-catalog ARGS="..."`. A run is one date, `--date YYYY-MM-DD`,
and writes only under `.planning/audits/catalog/<date>/`.

### 1. Start or resume

`make audit-catalog ARGS="status --date <date>"` prints `next <id>` (the first entry without
a complete report), `complete N/M`, and any `orphan` report that matches no registry entry.
Continue from `next`; `done` means go to step 5.

### 2. Record verify-registry once

`make audit-catalog ARGS="verify --date <date> --state <scratch>/verify-registry.json"` runs
`make verify-registry`'s check once with a scratch state file and stores its record in the run
directory. The state path is always a scratch path, never the default one in the home directory.

### 3. Audit one entry

1. `make audit-catalog ARGS="facts <id>"` prints the entry's facts: methods, pin, `verified`
   date, paths, update and removal argv, hook, tuning keys, installed version, every latest
   version with its source, `see also` neighbours and the container runtime if any.
2. Read what the facts point at, decide the five check rows (install method, update argv,
   removal recipe and paths, tuning keys, postinstall hook) and the proposed changes.
3. Load `references/report-template.md` and write the report to a scratch file, then store it:
   `make audit-catalog ARGS="write <id> --date <date>" < <scratch>/<id>.md`. The tool refuses an
   invalid report with every reason; fix the file and run it again. A complete report is never
   rewritten; a new date starts a new run.

### 4. Scan the scripts

`make audit-catalog ARGS="scan --date <date>"` lists every audited script surface and the
mechanical unsafe patterns it found, with `path:line`.

A finding that arrives after an entry's report is complete (a script finding, a container
result) is recorded, never written into the report:
`make audit-catalog ARGS="add-finding <id> --date <date> --check <check> --status <ok|drift|unknown> --source '<text>' [--cite path:line]"`.

### 5. Summarize

`make audit-catalog ARGS="summarize --date <date>"` rebuilds `SUMMARY.md` from the reports,
the scan, the verify record and any findings.

### 6. Apply only what the user approves

Present the summary. Land nothing without the user's explicit approval of that change.
