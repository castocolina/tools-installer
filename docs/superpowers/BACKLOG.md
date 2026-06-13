# tools-installer — backlog

Forward-looking index of open work. Completed work lives in `specs/` + `plans/`
(dated, one pair per feature) and is summarized in
`memory/roadmap-status.md`. This file tracks only what is **not yet done**.

Status legend: **NEXT** (scoped, ready to plan) · **NEEDS SCOPING** (idea
captured, design not started) · **DEFERRED** (intentionally parked, YAGNI) ·
**OWNER** (a manual step only the repo owner can take).

---

## NEXT

### F2 — per-tool AI rationale
Port uzkit `docs/ia-helper-tools.md` into an optional `ai` field on each
registry tool, surfaced in the catalog detail bar. The detail-bar slot
already exists (see F1). Pure data + one detail-bar line; no executor change.

### F3 — `requires` dependencies
Add a `requires` field to the registry, then: transitive selection (selecting
a tool drags in its deps), topological install order, and dependency
visibility in the detail bar. Detail-bar slot already exists.

---

## OWNER

### Publish / go-live
Repo has **no remote** by standing instruction — do not push or create one
without an explicit request. When ready:
`gh auth login` then
`gh repo create castocolina/tools-installer --public --source=. --remote=origin --push`.
The publish model is lean: `install.sh` clones `main`, so push == published
(no tags / PyPI).

---

## DEFERRED (parked, YAGNI until a trigger appears)

**Polish / nice-to-haves**
- uzkit-style `case ":$PATH:"` idempotency guard in `shellrc.managed_block`
  (would stop `source ~/.myshellrc` in a live shell from duplicating dirs on
  PATH — currently cosmetic, self-resolves on shell restart).
- Doctor hint specific to a "duplicated on PATH" finding.

**install.sh robustness**
- Git-less tarball fallback + fetch-by-SHA (clone is the only fetch path today).
- Partial-clone recovery: if `$TI_DIR` exists without `.git`, `git clone` fails
  "directory not empty"; recovery is left to the user.

**Registry / format coverage**
- Linux install methods for vscode/sublime (macOS-only today; a future batch).
- `.dmg`/hdiutil app installs (no `.dmg`-only app in the catalog yet; e.g.
  Ghostty would force it).
- Native apt/dnf/pacman methods for the download-tier tools — blocked on
  per-distro name mismatches needing verification (Debian fd→`fd-find` binary
  `fdfind`, bat→binary `batcat`, delta→`git-delta`). Only `rg` keeps its
  native methods today.
- Bare-`.gz` single binary (taplo, tree-sitter) and `.tar.xz`
  (shellcheck-as-tool) format support.
- Node version management: volta has no arm64 asset at all (messy).

**Security**
- Signature/authenticity verification (`.sig`/cosign). Checksums today are
  **integrity only** — they ship from the same release as the asset, so they
  prove the download wasn't corrupted, not that it's authentic.
