---
phase: "28"
slug: "shared-terminal-keys-mechanism"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-20"
---

# Phase 28 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| installer -> user's terminal config files | The mechanism edits an owned region inside files the user also edits (`alacritty.toml`) | config text, user bindings |
| installer -> user's shell rc file | The zsh Ctrl+L widget is written into a managed marker block of the rc file | shell code in the user's rc |
| registry -> table | A registry entry may name `apply_terminal_tuning`; the table, not the registry, decides what is written | tool ids |
| executor -> existing tests | A move must leave the Alacritty bytes and the existing tests unchanged | test assertions |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-28-01 | Tampering | the move of the region primitives | medium | mitigate | Golden-byte tests committed (467b575c) before the move (c7bde357) and not edited afterwards; an AST check shows the 32 bodies terminal_shell keeps are unchanged | closed |
| T-28-02 | Tampering | malformed marker handling | medium | mitigate | Nested, duplicate, orphan and unclosed markers still raise (terminal_regions.py:39-49); the malformed-region test is unedited | closed |
| T-28-03 | Tampering | compare-before-commit | low | mitigate | `commit_region` validates then `write_if_unchanged`; the file-changed-before-commit and non-reparsing-edit tests are unedited; the check-then-replace window is a stated limit | closed |
| T-28-04 | Denial of Service | a registry tool naming the action with no row | medium | mitigate | `TERMINAL_KEYS.get` with a one-line refusal (post_install.py:389-392), no fact in version_status; completeness and backstop tests | closed |
| T-28-05 | Tampering | record file names | medium | mitigate | Record name derived from the table key (`terminal-tuning-{tool_id}`) and the created-record name pinned by the golden test | closed |
| T-28-06 | Tampering | strip and created-file cleanup | medium | mitigate | `_drop_created_config` keeps its logic: acts only on the marker, deletes the config only when whitespace-only, keeps the record on a failed strip; created-file tests unedited | closed |
| T-28-07 | Elevation of Privilege | table is a code constant | low | mitigate | `TERMINAL_KEYS` is a `Final` constant; region bodies come only from `_KEY_BINDINGS`; the registry names only closed actions; `tool.name` never enters a body | closed |
| T-28-12 | Tampering | drift rewrite | medium | mitigate | Only a present, stale region is rewritten, only on reconfigure (`skip_recorded=True`); a deleted region stays deleted; tests cover deleted, stale, user-binding-wins and unreadable cases | closed |
| T-28-13 | Denial of Service | unreadable recorded file | low | mitigate | A refusing or unreadable recorded file returns None; `version_status` keeps its `except Exception`; tests cover both | closed |
| T-28-14 | Tampering | Writes snippet | low | mitigate | The snippet enters the body only through `_render`, inside the owned region, validated before writing; a test checks it appears once between the markers and re-parses | closed |
| T-28-15 | Elevation of Privilege | Option-as-Alt | low | mitigate | `KeysRow` has no such field; a test pins the exact field list and the absence of the setting in the region bytes | closed |
| T-28-08 | Tampering | zsh widget block | medium | mitigate | One text source, written only through the `tweak:zsh` marker block, swept on removal; apply-then-strip pinned on eight inputs; a real post_install and removal prove the widget and record are gone | closed |
| T-28-09 | Tampering | widget guard | medium | mitigate | `[ -n "${ZSH_VERSION-}" ]` inside the `command -v zsh` guard, safe under `set -u`; the guard line is asserted; the bash -n and zsh -n tests now cover the body | closed |
| T-28-10 | Elevation of Privilege | widget body | low | mitigate | The body is a constant; only a bin-dir placeholder is replaced, which it does not contain | closed |
| T-28-11 | Denial of Service | shell runs in tests | low | mitigate | No fork, pty or interactive shell in the phase's tests; only `bash -n`, `zsh -n` and a list-argv `zsh -f -c` of a builtin, skipped with a reason without zsh, all accepted by the launch guard | closed |
| T-28-SC | Tampering | supply chain | low | accept | No dependency, lockfile or manifest changed (`git diff 4bf43adb HEAD --stat -- pyproject.toml uv.lock package.json package-lock.json .pre-commit-config.yaml` is empty) | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-28-01 | T-28-SC | The phase adds no dependency, lockfile or manifest entry, so there is no new supply-chain surface to mitigate; the check is a one-line empty diff | orchestrator (autonomous run, ASVS 1) | 2026-11-20 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-20 | 16 | 16 | 0 | gsd-security-auditor (opus), orchestrator-written |

Notes from the audit, none blocking:

- Removing the zsh block keeps every user line, but the shared `shellrc` apply and strip leave extra blank lines at the end of the file (`"a"` becomes `"a\n\n"`, `"a\nb\n"` becomes `"a\nb\n\n"`). This was the shared behavior before this phase; the SPEC R3 wording was amended on 2026-11-20 and needs the owner's confirmation; the real fix is backlog 999.27. T-28-08's declared mitigation (no widget text or marker remains) holds.
- `write_tweak` writes the rc file with `atomic_write_text` and no compare-before-commit. That machinery is unchanged by this phase, and T-28-08 does not claim it.
- T-28-03 and T-28-06 state a limit: between the compare and the replace another writer can still get in. No race test covers it; SPEC R1 and R2 concurrency rows stay held-out backstops.
- Provisional decisions to confirm: 28 D-06 with OQ1, the amended SPEC R3 wording, and the D-12 import-line deviation to `tests.test_terminal_keys`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-20
