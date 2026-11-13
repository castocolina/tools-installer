# Catalog Entries Not Installed Directly

The installer catalog only lists tools it can install with supported method kinds.

## codegraph

`codegraph` is not added as an installable catalog row in this pass. The local Codex plugin exposes Codegraph as an MCP capability, but this project does not yet have a verified standalone install method that fits the supported registry method kinds.

## Alacritty on immutable Fedora and macOS

Alacritty is a catalog row. On Linux with distrobox and podman present, the catalog builds the release tag with cargo in a throwaway Distrobox and installs the binary, desktop entry, icon and terminfo (`~/.terminfo`); the receipt records them and uninstall removes them. An immutable host without distrobox and podman shows `needs distrobox and podman`. A mutable Fedora, Debian or Arch host without them gets the distro package `alacritty` as a manual handoff. The official Homebrew cask is disabled, so macOS has no reviewed method and stays unsupported.

## PyCharm and IntelliJ IDEA

JetBrains IDEs are represented by JetBrains Toolbox. Toolbox is the installable management surface for PyCharm, IntelliJ IDEA, and related IDEs, so the catalog avoids duplicate per-IDE rows until the installer can model them cleanly across platforms.
