# Catalog Entries Not Installed Directly

The installer catalog only lists tools it can install with supported method kinds.

## codegraph

`codegraph` is not added as an installable catalog row in this pass. The local Codex plugin exposes Codegraph as an MCP capability, but this project does not yet have a verified standalone install method that fits the supported registry method kinds.

## Alacritty on immutable Fedora

Alacritty is a catalog row. Mutable Fedora, Debian, and Arch install the distro package `alacritty`. Immutable Fedora skips those native methods, and the GitHub release publishes no Linux asset the installer can download, so the row has no method on Bazzite. A Distrobox install that stays off ostree is in `docs/research/2026-10-09-alacritty.md`. The official Homebrew cask is disabled, so macOS has no reviewed method either.

## PyCharm and IntelliJ IDEA

JetBrains IDEs are represented by JetBrains Toolbox. Toolbox is the installable management surface for PyCharm, IntelliJ IDEA, and related IDEs, so the catalog avoids duplicate per-IDE rows until the installer can model them cleanly across platforms.
