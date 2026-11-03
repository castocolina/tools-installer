---
created: 2026-10-22T00:21:30.030Z
title: Onboard AWS CLI through the tool-onboarding skill
area: catalog
severity: minor
files:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/registry.toml
---

## Problem

The user wants AWS CLI (`aws`) added to the installer catalog through the
existing tool-onboarding skill. No AWS CLI catalog entry or pending onboarding
todo was found when capturing this request.

The user explicitly confirmed **minor** severity. This is a catalog addition,
not a blocker, and the request is to capture the work rather than onboard it now.

## Solution

Run `.claude/skills/tool-onboarding/SKILL.md` end to end for AWS CLI when this
todo is selected for implementation. Research current official installation and
removal guidance, supported macOS/Linux and amd64/arm64 combinations, and the
appropriate AWS CLI version before choosing registry methods.

Follow the skill's classification, dependency, ownership, detection, removal,
and customization checks. Verify that the installed command is `aws` and use a
non-authenticated smoke check such as `aws --version`. Record any installer
capability gaps instead of inventing unsupported registry methods or claiming
removal support that does not exist.

Ask about optional shell integration or customizations during onboarding; do
not configure AWS accounts, credentials, or authentication as part of this
capture. Real installation/removal verification must use disposable
environments, never the developer's host.
