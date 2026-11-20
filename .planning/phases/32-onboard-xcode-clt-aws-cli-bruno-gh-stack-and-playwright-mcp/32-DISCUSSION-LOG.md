# Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 32-onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** Xcode CLT; AWS CLI v2; Bruno; gh-stack; Playwright MCP

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 57 tool calls. It ran `gh` 2.101.0 in a scratch HOME with no token, read (not ran) the AWS `install.sh`, and read the registry, executors, resolver and uninstall code. No container installs, no host changes. (The harness flagged the report as matching a settings-json instruction-like pattern; its text was treated as findings only.)

| Assumption | Confidence | Evidence |
|---|---|---|
| Xcode CLT: detect-only, non-PATH `cmd`, `detect_path` | Confident | status.py:114-211; registry.toml:599-624 |
| Closed hand-off name for the command | Likely | architecture.md:337-342 |
| No receipt, no removal; grep test | Confident | version_status.py:2016-2028 |
| CLT path only, no brew edge | Unclear | SUMMARY.md:154 |
| AWS CLI script entry (url, paths, update, requires unzip) | Confident | install.sh read; registry.toml:74-86 |
| Script outranks brew for AWS CLI | Unclear | resolve.py:15-31 |
| Container: gpg present and absent | Likely | SPEC acceptance |
| Bruno macOS cask | Confident | executors.py:699-704 |
| Bruno Linux unpinned github_release | Likely | drawio precedent |
| Bruno smoke argv confirmed in a container | Unclear | skill Common Mistakes |
| gh-stack fixed-argv `script` extension | Likely | executors.py:471-491 |
| gh-stack detection by manifest file | Likely | live probe, exit 4 |
| gh-stack removal by proven folder | Unclear | uninstall.py:343-373 |
| Playwright bun method with one pin | Likely | executors.py:633-653 |
| Pin 0.0.86 with Node 20 | Likely | npm registry |
| Per-host MCP writers | Unclear | agent_env.py:51-77 |
| Flatpak path in each entry's env; consent as a plan step | Unclear | architecture.md:771-775 |

## jev screening

One jev request per item (Laya, then TypeSafe); `needs_fallback` items are decided by own reasoning. Summaries only.

| Item | jev | Outcome |
|---|---|---|
| f1 hand-off command source | none_of_these 0.77 (contradicts evidence); second opinion code_owned_table 0.91 | **jev overridden** (D-01) |
| f2 CLT scope | low 0.46; TypeSafe choice clt_path_only_no_edge 0.98 | D-02 |
| f3 AWS ladder | low 0.33; TypeSafe choice script_first_everywhere 0.92 | D-04 |
| f4 AWS container hosts | low 0.58; TypeSafe choice both_hosts 0.94 | D-05 |
| f5 Bruno pin | low 0.38; TypeSafe low 0.73 (pin_version_and_hash) | **Own reasoning:** pin via `tarball` raw (D-07, ledger) |
| f6 Bruno smoke | none_of_these 0.84 (contradicts evidence); second opinion confirm_in_container 0.98 | **jev overridden** (D-08) |
| f7 gh-stack install shape | low 0.44; TypeSafe low 0.67 | **Own reasoning:** script argv install (D-09, ledger) |
| f8 gh-stack detection | low 0.69; TypeSafe choice manifest_file 0.87 | D-10 (needs confirmation) |
| f9 gh-stack removal | none_of_these 0.95 (contradicts evidence); second opinion delete_proven_folder 0.99 | **jev overridden** (D-11, needs confirmation) |
| f10 Playwright install and registration | choice install_and_register_one_pin 0.72 | D-12 |
| f11 Playwright pin | low 0.47 (newest_node20); TypeSafe choice research_version_node18 0.81 | D-13: 0.0.85 |
| f12 MCP registration | low 0.48; TypeSafe low 0.64 (call_host_cli) | **Own reasoning:** merge-safe file writers (D-14, ledger) |
| f13 consent | low 0.52; TypeSafe choice plan_step_listed 0.99 | D-15 |

## Live facts that changed the plan

- gh-stack: only `install` works without a login (live): ONB-14 / SPEC R4 / ROADMAP amended, flagged needs confirmation (D-10, D-11).
- No method kind runs a fixed argv or shows `xcode-select --install`; `github_release` has no pins: param extensions on existing kinds (D-01, D-07, D-09); `raw` on `tarball` is shared with phase 30.
- `_RANK` puts brew before script: a narrow preference for the AWS CLI script (D-04).
- Consent machinery retired in Phase 25: consent is a listed plan step (D-15). No MCP writer exists: per-host writers (D-14).
- Playwright latest needs Node 20 and verify-registry does not check npm pins: pin 0.0.85, SPEC acceptance reworded (D-13).

## Corrections Made

No corrections — unattended run; the owner reviews the ledger.

## Auto-Resolved

The Unclear items were decided by jev or own reasoning above.

## External Research

Open items are in CONTEXT deferred: per-host MCP config paths and schemas, `bunx` reuse of a global install, Bruno's non-GUI `--version`, Xcode.app-only CLT, the macOS pkg route without admin.
