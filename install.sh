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

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    command -v curl >/dev/null 2>&1 || die "curl is required to install uv"
    printf 'tools-installer: installing uv...\n'
    # -f makes curl fail on an HTTP error instead of piping a server error page
    # into sh as code; keep it even though there is no pipefail in POSIX sh.
    curl -LsSf "$TI_UV_INSTALL_URL" | sh
    # The official installer drops uv in ~/.local/bin; make it visible now.
    if [ -f "$HOME/.local/bin/env" ]; then
        # shellcheck disable=SC1091
        . "$HOME/.local/bin/env"
    else
        PATH="$HOME/.local/bin:$PATH"
    fi
    command -v uv >/dev/null 2>&1 || die "uv installation failed"
}

fetch_repo() {
    command -v git >/dev/null 2>&1 || die "git is required to fetch tools-installer"
    # A partial clone (TI_DIR exists but has no .git) makes `git clone` fail with
    # "directory not empty"; recovery (removing TI_DIR) is left to the user for now.
    if [ -d "$TI_DIR/.git" ]; then
        printf 'tools-installer: updating %s\n' "$TI_DIR"
        git -C "$TI_DIR" pull --ff-only
    else
        printf 'tools-installer: cloning into %s\n' "$TI_DIR"
        git clone --depth 1 --branch "$TI_REF" "$TI_REPO_URL" "$TI_DIR"
    fi
}

main() {
    os="$(detect_os)"
    printf 'tools-installer: platform %s\n' "$os"
    ensure_uv
    fetch_repo
}

if [ -z "${TI_SOURCED:-}" ]; then
    main "$@"
fi
