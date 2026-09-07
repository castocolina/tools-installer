# Install Experience and Agent Toolkit Design

## Purpose

Make the interactive installer truthful, observable, and reusable. The work fixes the Catalog-to-Install path, reuses the existing shellrc workflow, and adds evidence-based detection and agent-toolkit support.

## Decisions

### Install execution

The Install screen has five visible regions: reviewed plan, warnings, approvals, per-tool progress, and live output. Warnings use an explicit orange style. The screen updates to `starting` before it starts its worker. A top-level worker boundary converts every unexpected exception into a visible failed run with the exception text and a retry/return action.

Non-interactive commands use a PTY-capable, attributed runner when available. The runner normalizes carriage-return progress updates before writing them to a per-tool live-output pane. Commands that require a real controlling terminal remain manual handoffs; they never receive the Textual TTY.

### Shell setup

The existing `configure_path` and link-mode model remains authoritative: `centralized` writes `~/.myshellrc` and sources it from both shell rc files, `single` sources it from the active shell, and `split` writes managed blocks directly to both rc files. The installer asks for a link mode only when its reviewed plan contains at least one PATH-managed artifact. It applies the existing idempotent workflow after successful installation and before returning to Catalog. It does not introduce another shellrc file or duplicate PATH logic.

### Status and Catalog state

Status has independent facts: presence, owner confidence, owner manager, and lifecycle/target state. Presence may come from PATH, application bundles, a manager query, or an installer receipt. A manager name is shown only after a manager-specific read-only probe proves it. Catalog refresh re-queries status after a run and removes successful/already-installed ids from the staged selection; failed, skipped, and cancelled ids remain selected.

`contextual` means recommended only when a project needs that ecosystem. The UI explains it in the Catalog legend and highlighted-item detail. Audience is for whom the tool is primarily operated, not a claim that every agent uses it.

### Managers and receipts

Add adapters for pnpm, npm, uv tools, pipx, Flatpak, Snap, SDKMAN, native package managers, Homebrew, and installer-managed downloads where the manager can provide read-only evidence. Store an installer receipt for actions this application performs: tool id, method, version when available, artifact paths, and completion time. A receipt verifies application ownership but does not override a missing artifact.

SDKMAN remains a Runtime catalog tool because it provides JVM runtimes, while its successful `sdk current` query identifies it as an ownership manager.

### Toolkits and target environments

Toolkits use a declarative lifecycle plus a named adapter. Each adapter records the upstream source, official install/status/update/remove commands, selected skills, selected targets, and target-specific results. The supported target matrix is Claude, Codex, OpenCode, Pi, and Antigravity. A toolkit may mark a target unsupported or manual-required; the installer must not copy files into an unsupported harness.

Research precedes adapter implementation for Ponytail, OpenSpec, Superpowers, Softaworks Agent Toolkit, Matt Pocock Skills, OpenGSD, and Spec Kit. The investigation records the upstream version, exact official mechanism, status evidence, and target support.

### Permission profiles

Policies expose reversible launch profiles rather than changing a harness's default permissions invisibly.

- Safe Auto: Codex `--sandbox workspace-write --ask-for-approval never`; Claude automatic permission mode; OpenCode `--auto` plus explicit deny rules.
- External Sandbox Only: Codex `--yolo`; Claude `--dangerously-skip-permissions`; OpenCode unrestricted permissions only in an externally isolated environment.

The UI states that Codex yolo removes its sandbox as well as approvals. Profiles write marker-delimited aliases/wrappers, show the exact command, and remove only their own managed block.

## Constraints

- Tests use a temporary home and stubbed runners.
- No test calls a real package manager, changes the host login shell, or writes the real user home.
- Podman smoke remains optional and runs only when available.
- Ownership remains fail-closed: executable location alone never proves owner.

## Delivery Order

1. Install execution UX and shell-layout integration.
2. Installation intelligence and catalog-state refresh.
3. Catalog semantics and explanatory copy.
4. Toolkit target adapters and permission profiles.

Plans 2--4 may proceed after Plan 1's interfaces pass. Plan 4's adapter work uses Plan 2 receipts and status types when available, but its upstream research can start immediately.

