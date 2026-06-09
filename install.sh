#!/bin/sh
# tools-installer bootstrap: detect platform, ensure uv, fetch the repo, run the wizard.
#
# Usage (remote):
#   curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh -s -- --all --yes
#
# Overridable via environment (defaults shown):
#   TI_REPO_URL=https://github.com/castocolina/tools-installer.git
#   TI_REF=main
#   TI_DIR=${XDG_DATA_HOME:-$HOME/.local/share}/tools-installer
#   TI_UV_INSTALL_URL=https://astral.sh/uv/install.sh
#   TI_NO_RUN=          (set to any value to install without launching the wizard)
set -eu

TI_REPO_URL="${TI_REPO_URL:-https://github.com/castocolina/tools-installer.git}"
TI_REF="${TI_REF:-main}"
TI_DIR="${TI_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/tools-installer}"
TI_UV_INSTALL_URL="${TI_UV_INSTALL_URL:-https://astral.sh/uv/install.sh}"

die() {
    printf 'tools-installer: %s\n' "$1" >&2
    exit 1
}

detect_os() {
    os="$(uname -s)"
    case "$os" in
        Darwin) printf 'macos\n' ;;
        Linux) printf 'linux\n' ;;
        *) die "unsupported OS: $os (only macOS and Linux are supported)" ;;
    esac
}

main() {
    os="$(detect_os)"
    printf 'tools-installer: platform %s\n' "$os"
}

if [ -z "${TI_SOURCED:-}" ]; then
    main "$@"
fi
