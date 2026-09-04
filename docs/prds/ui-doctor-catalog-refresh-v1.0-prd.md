# Doctor View and Catalog Refresh - Product Requirements Document (PRD)

## Requirements Description

### Background

The installer has two related problems.

First, the TUI splits diagnosis and remediation into separate Doctor and Fix views. That makes the flow harder to understand because Fix is a consequence of Doctor: users diagnose PATH state, then apply the recommended PATH repair. The current Doctor/Fix content also feels sparse, visually heavy, and too close to the left edge on wide terminals.

Second, the tool catalog needs clearer priority and description rules for an AI development environment. Tools used heavily by LLM agents need `P0` priority and descriptions that explain the problem they solve, the older tool they replace, and why the replacement matters. Human-facing agent CLIs such as Codex, Claude Code, and OpenCode are also `P0`, but they target the user, not the AI agent.

### Target Users

- Developers installing a local AI development environment.
- Developers who use terminal-first coding agents and want a curated tool catalog.
- Users on macOS, mutable Linux distributions, and immutable Linux environments such as Bazzite.

### Value Proposition

- Make the Doctor view explain the system state and offer the next safe action in one place.
- Make catalog priority meaningful for AI-assisted development.
- Make catalog descriptions specific enough to teach users why each tool belongs.
- Add common agent, container, Java, editor, and IDE tools without weakening install safety.

## Feature Overview

### Core Features

1. Collapse the TUI Fix view into the Doctor view.
2. Redesign the Doctor body using a centered, bounded, sectioned layout.
3. Update catalog priorities for high-use agent tools.
4. Rewrite catalog descriptions with concrete replacement and value language.
5. Add requested catalog entries for agent CLIs, containers, Java tooling, VS Code, and JetBrains tooling.
6. Respect immutable Linux constraints when describing or resolving GUI/editor installs.

### Feature Boundaries

In scope:

- TUI view structure, navigation labels, footer hints, and Doctor copy.
- Tool catalog metadata: ids, names, categories, commands, priority, audience, descriptions, dependencies, and install methods where supported.
- Tests that verify the merged Doctor behavior and catalog invariants.

Out of scope:

- A full visual redesign of the whole wizard.
- Replacing the Python Textual TUI with React or MUI.
- Implementing Flatpak, distrobox, or containerized desktop-app installation unless the current installer already supports the method safely.
- Changing CLI `make doctor` and `make fix` semantics unless required by the TUI merge.

## Detailed Requirements

### Doctor and Fix View Requirements

- The TUI must expose one Doctor view for PATH audit and PATH repair.
- Opening Doctor must remain read-only. It must not write shell files until the user applies the fix.
- The Doctor view must show:
  - PATH status summary.
  - Audit findings.
  - Guard or policy warnings.
  - PATH fix preview.
  - Apply result or retry guidance.
- Pressing `enter` in Doctor must apply the PATH fix when the fix is available and not already applied.
- The legacy hidden `a` apply alias may remain for one release if existing tests or muscle memory require it.
- A failed apply must keep the app running, show the error inline, and allow retry.
- A successful apply must be idempotent: repeated apply input must not run the fix again.
- Navigating away from Doctor without applying must not write anything.
- The standalone Fix view must leave top-level navigation if Doctor owns the apply action.

### Doctor Layout Requirements

- Use the existing Textual design system and shared `AppScreen` chrome.
- Apply MUI-like layout principles where they fit Textual:
  - Use a bounded content container.
  - Use consistent spacing.
  - Group related content into clear sections.
  - Use theme tokens and existing severity styles instead of hardcoded color noise.
- Do not introduce React, MUI, or a web frontend for this work.
- The Doctor body should not be a single left-padded text block.
- The layout should feel calm and practical, not gloomy or alarmist.
- Important text should remain left-aligned inside the content panel for scanability.

### UI/UX Review Requirement

- Use `agent-ui-ux-designer` guidance for UI/UX critique and direction.
- Do not use GSD UI skills for this work; GSD is reserved for full SSD-style workflows.
- If design guidance conflicts with Textual or terminal constraints, prefer the existing Textual architecture and document the tradeoff.

### Catalog Priority Requirements

- Mark tools heavily used by LLM agents as `P0`.
- Mark `codex`, `claude`, and `opencode` as `P0` human-facing tools, not AI-facing tools.
- Preserve the `audience` distinction:
  - `ai`: tools primarily useful for agent execution.
  - `human`: tools primarily used by the developer.
  - `both`: tools useful to both.
- Priority changes must be test-covered so future catalog edits do not drift.

### Catalog Description Requirements

Each updated description should answer, when applicable:

- What problem does this tool solve?
- What older or built-in tool does it replace or complement?
- Why is it better in this environment?
- How does it reduce wasted output, wasted time, or wasted tokens?

Examples:

- `fd`: replaces most `find` usage with faster defaults, `.gitignore` awareness, and simpler output.
- `sd`: replaces common `sed` substitutions with clearer syntax and safer literal defaults.
- `eza`: replaces `ls` with clearer file metadata, Git awareness, and readable defaults.
- `rg`: replaces recursive `grep` with faster code search and useful ignore-file behavior.

Descriptions must be concise, concrete, and free of marketing filler.

### Requested Catalog Additions

Agent and AI CLIs:

- `codegraph`
- `codex`
- `claude`
- `opencode`

Version control and package managers:

- `git`
- `brew` / Homebrew must remain represented clearly. If the existing `brew` entry is reused, its description should make the Homebrew role explicit.

Containers:

- `docker`
- `podman`
- `colima`

Editors and IDEs:

- `vscode`
- JetBrains Toolbox as the preferred JetBrains management entry.
- JetBrains IDE entries may be added directly only if the installer can model them cleanly. Preferred direct entries include PyCharm and IntelliJ IDEA.

Java tooling:

- `sdkman`
- `java`
- `groovy`
- `springbootcli`
- `gradle`
- `maven`

Java tools should depend on `sdkman` when the install model supports that dependency. The catalog should make SDKMAN's role explicit: it manages JVM and JVM-adjacent tools without forcing system package-manager installs.

### Immutable Linux and Bazzite Requirements

- The catalog should be aware that immutable Linux environments such as Bazzite often prefer containerized, Flatpak, Homebrew, or user-space installation paths over native package-manager writes.
- VS Code and GUI app descriptions should mention the safer install path when the installer cannot directly manage that app on immutable Linux.
- The resolver must not claim a supported install method where the installer cannot actually install the app safely.

## Design Decisions

### Technical Approach

- Keep the existing Python Textual app.
- Merge Fix behavior into `DoctorScreen`.
- Update the shared view registry so top-level navigation reflects the merged view.
- Keep catalog data in `installer/registry.toml`.
- Prefer existing install method kinds. Add new method kinds only if the current resolver and executor pattern can support them safely.

### Writing Approach

- Use active voice and concrete language.
- Keep descriptions short enough for the catalog detail area.
- Avoid vague claims such as "powerful", "seamless", "robust", and "cutting-edge".
- Name replacements directly when that helps users understand the tool.

### Risks

- Removing the Fix view changes navigation key numbering.
- Some requested tools may lack safe cross-platform install methods in the current executor model.
- Catalog count tests and resolver tests will need updates.
- Overlong descriptions could make the TUI harder to scan.
- Treating human agent CLIs as `ai` audience would mislead users and conflict with the requirement.

## Acceptance Criteria

### Functional Acceptance

- [ ] The TUI has one Doctor view that audits and applies the PATH fix.
- [ ] Viewing Doctor performs no write.
- [ ] Applying the Doctor fix runs the existing fix callback exactly once on success.
- [ ] Apply failures show inline and allow retry.
- [ ] The old standalone Fix view is removed from top-level navigation.
- [ ] Navigation, palette, footer, and rapid-switching tests match the new view order.
- [ ] The catalog includes all requested tool entries or documents any unsupported entry with a clear reason.
- [ ] `codex`, `claude`, and `opencode` are `P0` and human-facing.
- [ ] High-use LLM agent utilities are `P0` where appropriate.
- [ ] Java tools depend on `sdkman` where supported.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before implementation.
- [ ] `make validate` passes.
- [ ] `make test` passes.
- [ ] Catalog descriptions are concise and concrete.
- [ ] No quality gate is bypassed or silenced.

### User Acceptance

- [ ] Doctor feels centered, structured, and less gloomy.
- [ ] The catalog explains why each priority tool exists.
- [ ] The catalog distinguishes tools for AI agents from tools for the human developer.
- [ ] Bazzite and immutable Linux constraints are visible where they affect install choices.

## Open Questions

1. Should unsupported requested tools appear in the catalog as documented/manual entries, or should the catalog include only tools the installer can actually install?
2. Should JetBrains be represented only by Toolbox, or should PyCharm and IntelliJ also appear as separate selectable tools?
3. Should `codegraph` be installable by this project, or should it be a documented dependency because its setup may depend on the Codex/plugin environment?
