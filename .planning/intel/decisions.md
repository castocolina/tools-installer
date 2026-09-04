# Decisions

No ADRs were present in the batch-1 classification (`catalog-tiers-and-dependency-chain`,
1 classification, type `PRD`). No decision entries to extract.

No ADRs were present in the batch-2 classification (`package-manager-policy`,
1 classification, type `PRD`). No decision entries to extract.

Note: `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md` records several
decisions in prose (e.g. `codegraph` moves off `pnpm add -g`; SDKMAN exclusivity
for the java toolchain), but the classification for this doc is `type: PRD`, not
`ADR`, and `locked: false`. Per extraction discipline these are captured as
requirements with a `status:` note in `requirements.md`, not as locked ADR
decisions here — the PRD itself is not an ADR artifact.

No ADRs were present in the batch-3 classification (`catalog-expansion`,
`postinstall-hooks`, 2 classifications, both type `PRD`). No decision entries
to extract.

No ADRs were present in the batch-4 classification (`agent-cli-ergonomics`,
`background-maintenance-daemon`, `live-package-management`, 3 classifications,
all type `PRD`). No decision entries to extract.

Note: all three batch-4 PRDs record design decisions in prose, but none is
classified `type: ADR` or `locked: true`, so per extraction discipline none is
recorded here as a locked ADR decision — each is captured as a requirement with
a `status:`/description note in `requirements.md` instead:
- `docs/prds/2026-09-04-agent-cli-ergonomics-v1.0-prd.md`: self-update
  durability mechanism chosen (shell alias/function via `installer/tweaks.py`,
  not a file-based shim or a watchdog daemon) — see `REQ-agent-tweak-self-update-durability`.
- `docs/prds/2026-09-04-background-maintenance-daemon-v1.0-prd.md`: modeled as
  a new `Policy` factory (`daemon_policy`-style) rather than overloading
  `TweakBundle` — see `REQ-launchd-prune-policy`.
- `docs/prds/2026-09-04-live-package-management-v1.0-prd.md`: extend
  `installer/versions.py`'s existing `resolve_github_tag`/`Fetch` seam rather
  than replacing it; use Textual's own `Worker` API for background refresh —
  see `REQ-manager-version-resolution`, `REQ-background-version-refresh-worker`.
