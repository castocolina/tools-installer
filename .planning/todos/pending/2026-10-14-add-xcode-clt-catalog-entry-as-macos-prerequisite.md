---
created: 2026-10-14T22:15:07.851Z
title: Add xcode-clt catalog entry as macOS prerequisite
area: catalog
severity: minor
files:
  - installer/registry.toml
  - docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
---

## Problem

The registry has no Xcode Command Line Tools entry, yet CLT is a genuine macOS
prerequisite: Homebrew lists it as a requirement (source builds, `git` fallback),
and many dev toolchains (compiling C extensions and similar) need it. The
catalog-tiers PRD (`2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`,
bootstrap-order correction) already names CLT as step 1 of the clean-machine
order — Xcode CLT -> Homebrew -> everything else — but no `xcode-clt` Tool
exists in `installer/registry.toml`, so the dependency chain cannot express it.

Severity is minor by design: the gap is masked today because the `brew` entry's
official `install.sh` auto-installs CLT non-interactively (`softwareupdate`,
with `xcode-select --install` fallback) — verified live in the Homebrew install
script. The entry is about making the prerequisite explicit and orderable, not
fixing a broken flow.

## Solution

Add an `xcode-clt` tool entry with `tier = "system"` and macOS-only methods.
Detection: `xcode-select -p` or `pkgutil --pkg-info=com.apple.pkg.CLT_...`.
Install options to decide between: (a) delegate to the brew entry's official
`install.sh` and express ordering via `requires = ["brew"]`, or (b) a
non-interactive `softwareupdate` flow (needs the
`.com.apple.dt.CommandLineTools.installondemand.in-progress` flag touched
first). Then decide whether the `brew` entry or downstream build-from-source
tools declare `requires = ["xcode-clt"]`, per the PRD's bootstrap-order note.
