# antigravity - catalog audit 2026-11-13

## Versions
- pinned: none (the script method is unpinned and installs whatever the vendor serves)
- verified: 2026-11-04
- installed: 1.2.2 (`~/.local/bin/agy --version`, from facts)
- latest: 1.5.8 (installer manifest, https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/linux_amd64.json; same version in linux_arm64, darwin_arm64, darwin_amd64)
- note: the host binary (1.2.2) is older than the 1.5.8 the manifest serves; the install script no-ops on an existing binary, so the registry cannot update it

## Changelog
- 1.5.0 adds `agy acp` and `--remote-agent` (changelog, https://antigravity.google/docs/changelog, entry "Antigravity CLI 1.5.0")
- 1.5.2 tightens plugin security boundaries and resolves MCP OAuth issues (changelog, https://antigravity.google/docs/changelog, entry "Antigravity CLI 1.5.2")
- the CLI keeps its state under ~/.gemini/antigravity-cli/settings.json and ~/.gemini/config/ (permission merge and project config, https://antigravity.google/docs/changelog); the entry version is not established from the page
- the CLI caches its binary metadata in ~/.gemini/bin/agy.version.json with a .agy-install.lock, and adds background management under ~/.gemini/bin (https://antigravity.google/docs/changelog); the entry version is not established from the page

## Checks
| check | status | source |
|---|---|---|
| install method | ok | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` with default binary ~/.local/bin/agy, https://antigravity.google/docs/getting-started?tab=cli; script darwin/linux/android and amd64/arm64 branches at https://antigravity.google/cli/install.sh (lines 69-94) |
| update argv | ok | registry declares none; the script says the CLI self-updates in the background and documents no manual update, https://antigravity.google/cli/install.sh (lines 57-63) |
| removal recipe and paths | unknown | reason: container check not run (this batch runs no containers); the changelog names ~/.gemini/bin and ~/.gemini/antigravity-cli, which `paths = ["~/.local/bin/agy"]` does not cover (installer/registry.toml:1736), and the script's native handoff `agy install` (https://antigravity.google/cli/install.sh line 239) writes state the script does not list |
| tuning keys | n/a | reason: the entry declares no tuning key and no post_install action (installer/registry.toml:1716-1736) |
| postinstall hook | ok | the entry declares no postinstall hook (installer/registry.toml:1716-1736); the vendor's own `agy install` handoff runs inside the vendor script, https://antigravity.google/cli/install.sh line 239 |

## Proposed changes
- correct the `# Verified` comment: install.sh checks the SHA-512 against the manifest it fetched from the same host and does not verify a signature (https://antigravity.google/cli/install.sh lines 122-142 and 188-199), so "signed manifest" is not supported; risk: low; evidence: https://antigravity.google/cli/install.sh
- record the ~/.gemini/bin and ~/.gemini/antigravity-cli state in the `# Verified` comment so removal is not assumed complete; risk: low; evidence: https://antigravity.google/docs/changelog

<!-- catalog-audit:complete -->
