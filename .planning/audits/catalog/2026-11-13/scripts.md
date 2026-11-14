# scripts - 2026-11-13

| location | entry | status | pattern |
|---|---|---|---|
| installer/agent_settings.py:679 | opencode | finding | `permission` deprecated in the opencode schema |
| installer/cursor_shim.py:65 | cursor-agent | finding | `exec "$target" ` shim exec line rewrites argv: exec "$target" {…}"$@" |
| installer/env_redirect.py | (installer) | ok |  |
| installer/guards.py:218 | (installer) | finding | `exec ` shim exec line rewrites argv: exec {…} {…} "$@" |
| installer/guards.py:260 | (installer) | finding | `exec ` shim exec line rewrites argv: exec {…} "$@" |
| installer/guards.py:333 | (installer) | finding | `exec ` shim exec line rewrites argv: exec {…} install "$@" |
| installer/post_install.py | (installer) | ok |  |
| installer/postinstall.py | (installer) | ok |  |
| scripts/container-e2e-verify.sh | (maintainer) | ok |  |
| scripts/detect-container-runtime.sh | (maintainer) | ok |  |
| scripts/lib/prune-tmp-common.sh | (maintainer) | ok |  |
| scripts/prune-tmp-linux.sh | (maintainer) | ok |  |
| scripts/prune-user-tmpdir.sh | (maintainer) | ok |  |
