# Phase 18: Registry truth and drift guard - Research

**Researched:** 2026-10-15
**Domain:** Python/stdlib installer internals (registry loader, GitHub release download pipeline, install-time smoke, scheduled drift check in GitHub Actions)
**Confidence:** HIGH (code and live-API facts verified this session); MEDIUM on four design gaps flagged in Open Questions

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Decision rule (user, 2026-10-13):** choose the best design, not the easiest. Every option below was checked against that rule.

#### Schema: closed keys, `verified`, pins (R1, R2, R11)
- **D-01:** Add `METHOD_PARAMS: dict[str, frozenset[str]]` to `installer/model.py`, following the existing `METHOD_KINDS`/`OWNER_PROBES` convention.
  - `load_tools` (`model.py:654-668`) checks `set(params) - METHOD_PARAMS[kind]` first and raises `tool '<id>': method '<kind>' has unknown key '<k>'`.
  - The existing per-kind value-shape checks stay as they are.
  - Phases 22 and 24 add keys by editing one dict entry.
  - `tests/test_model.py:803-827` (`test_non_node_method_leaves_new_keys_untouched`), which locks in the opaque pass-through, is rewritten to expect rejection.
- **D-02 (user):** Each `[[tool]]` gets a structured `verified = YYYY-MM-DD` key (a native TOML date).
  - `load_tools` requires it and rejects non-date or future values, with the tool id in the message.
  - `verify-registry` writes the key as data.
  - The 34 existing `# Verified …` comment dates seed the keys; the free-text notes stay as comments.
  - A `verified` key on a method table is rejected by D-01.
  - SPEC R2, REQUIREMENTS REG-02, ROADMAP and the specs for 22/24.1 were updated to say so.
- **D-03 (user):** Pinned `app`/`tarball` methods carry `version = "X"` and template their URL with `{ver}`.
  - The loader requires `version` when a pinned kind's URL contains `{ver}`.
  - A bump edits one value.
  - `github_release` methods keep resolving `{ver}` from the live tag and are never pinned.
- **D-04:** draw.io's `cli_name` is honored in exactly one place: `installer/apps.py` `cli_spec` (:47-65).
  - `uninstall.py` imports the same function, so install and removal naming stay single-sourced.
  - This fixes the macOS bug where `which("drawio")` never finds the link named `draw.io`.

#### Verification pipeline (R4, R5)
- **D-05 (audited 2026-10-14):** The tag and the asset digests come from **one** `/releases/latest` fetch.
  - `installer/versions.py` gains `resolve_github_release(repo, fetch) -> Release`. `Release` is a frozen dataclass holding `tag` and `digests: Mapping[str, str]` (asset name → sha256 hex, taken from each asset's `digest` field after stripping the `sha256:` prefix).
  - `resolve_github_tag` becomes `resolve_github_release(repo, fetch).tag`. The 12 tag-only `TagResolver` callers do not change.
  - The download context gets a `resolve_release` resolver. `download._resolve_target` takes `github_release` methods through it, so the URL tag and the expected digest come from the same snapshot. A separate digest call would add a second rate-limited read, and "latest" can move between the two reads.
  - Order: pinned checksum → `release.digests[asset]` → "unverified" with a reason. Pinned `app`/`tarball` methods carry a pinned checksum (D-09 writes it), so they never need a digest lookup.
  - A digest mismatch raises the existing `ChecksumMismatch`, so `engine.py`'s fail-fast branch (:146-151) covers it with no new engine logic.
  - The version refresh stores `Release.digests` in the version cache next to `latest_version`. Phase 19 D-09 adopts pre-receipt raw binaries against these digests, with no new network call.
  - Evidence that the API exposes a digest: `audit-2026-10-13/D-registry-user-part1.md:199` (live 2026-10-13).
- **D-06 (user):** The smoke run is one shared function (e.g. `smoke(path, argv)`) built on `run_output`/`CommandError`.
  - It fails on exit 126/127, an OSError, or a `GLIBC_`/loader error in stderr.
  - **download and app kinds** call it on the staged binary **before** the atomic link swap, so a broken binary is never linked and an existing good link is untouched.
  - **Manager kinds** call it after install, on `shutil.which(tool.cmd)`.
  - A failure falls through to the next method in the ladder.
  - A declared custom probe uses a new key, distinct from the existing closed-dispatch `smoke` name key (`model.py:13`), so the two trust models are not mixed.
  - Smoke runs on install, not on the single-method update path.

#### verify-registry and the weekly job (R3, R11)
- **D-07:** A new `installer/verify_registry.py` reuses `download._resolve_target` and `assets.render_asset`/`arch_tokens` for each declared `os`/`arch`.
  - This keeps one URL, member and checksum resolver, so a passing check means the real install works.
  - Newer-release detection and digests reuse `versions.resolve_github_release` (D-05).
  - **Check method (audited 2026-10-14):** every run compares API digests and probes each URL with HEAD. It downloads and opens an archive (the `member` check) only when the asset's digest differs from the last verified one or no digest exists. Downloading every asset for every OS/arch each week is wasted bandwidth and gives no extra signal. Checking API metadata alone would miss a renamed member.
  - The issue upsert shells out to `gh` through the existing `run.py` `Runner`: find the one open drift issue by label, then edit it or create it.
  - Exit "inconclusive" on a network error or rate limit, with no issue call.
- **D-08:** `make verify-registry` is read-only. `.github/workflows/verify-registry.yml` runs on `schedule` plus `workflow_dispatch` only, with `permissions: contents: read, issues: write`. It is never in the PR gate.
- **D-09:** The pin bump (R11) runs `verify-registry` on the candidate version and changes `version` and `verified` only when it passes. A renamed or removed asset keeps the old pin and is reported.
  - **Registry writes (audited 2026-10-14):** a scoped line rewrite, with no new dependency.
    - Every table in `registry.toml` uses a header (`[[tool]]` ×90, `[[tool.method]]` ×230), and the target keys are one-line scalars.
    - The writer finds the `[[tool]]` block by `id`, plus the method block where one is targeted, and replaces only the `verified =`, `version =` or checksum line inside it.
    - It then re-parses the whole file with `tomllib` and asserts that the result equals the old document plus exactly the intended edits. Any other difference aborts the write. Comments and layout are untouched by construction.
    - tomlkit was rejected because its output would still need the same semantic guard, and it would add a dependency for one writer. jev: TypeSafe chose the line rewrite at p=0.58, below the confidence floor, so this decision was reasoned through in full rather than taken from jev.

#### Data, detection and launch fixes (R6–R10)
- **D-10 (user):** The macOS stub rule is a closed table in `installer/status.py`, consulted by `is_installed` (:18-66).
  - `/usr/bin/java` maps to `/usr/libexec/java_home` exiting 0.
  - `/usr/bin/git` maps to `xcode-select -p` exiting 0.
  - A stub without the real tool counts as not installed, with a reason.
- **D-11:** The `--no-dev` change covers every `setup.py` launcher: Makefile `setup`, `run`, `doctor`, `fix`, `uninstall`, `guard` and `unguard` (:14-32), plus `install.sh:88`.
  - `validate` and `test` are untouched.
  - A Makefile test asserts both sides.
- **D-12:** `managed-download` removal touches exactly `model.py:57`, `install_ownership.py:83-89,376` and `registry.toml:2721`. The `:2770` row disappears with `drawio-cli`.
  - Acceptance: `rg managed-download installer/` returns nothing.
- **D-13:** `drawio-cli` is removed and `drawio-desktop` becomes `audience = "both"`.
  - A stale `drawio-cli` id is ignored: lookups are registry-driven (`version_cache.py:176-190`).
  - Resolved 2026-10-14: `settings.Settings` persists only `link_mode` and no tool ids, so no settings branch is needed. The only other references are the tests at `tests/test_registry.py:1118-1120, 1135-1142, 1168-1173, 1966`; update them in the same change.
  - A regression test pins the stale-id behaviour in `version_cache`.
- **D-14:** `versions.py` `parse_version` (:54) returns `None` for `-1`-like output. It parses lazygit's `version=0.44.1, …` and unquotes procs' output. These are covered by a parametrized test over the audit fixtures.
- **D-15:** The 35 data fixes are applied as written in audits C/D/E/F, "Registry fixes (data only)". Sublime's `member` is skipped because Phase 17 did it. Each fix maps to a test or to a `verify-registry` pass.

### Claude's Discretion
- Plan and wave order. Suggested:
  1. Schema (D-01..D-03), because the data must satisfy the new loader.
  2. The data fixes and seeding `verified`.
  3. The verification pipeline.
  4. `verify-registry` and the weekly job.
  5. Pin bumps last, because they need the tool.
- The exact names of the new functions and keys (the custom-smoke-argv key, the drift issue label).

### Deferred Ideas (OUT OF SCOPE)
- Reviewed Todos (not folded): `detect-dangling-pnpm-global-bin-shims-in-doctor` (score 0.6) belongs to Phase 21 (UI-07).
- Out of scope per CONTEXT/SPEC: receipts and health (19); script `paths`/`remove`/`update`/`writable_prefix` and `config_paths` (22); the `cargo_distrobox` kind (24); bot PRs for drift; a latest-version source for script/SDKMAN tools.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REG-01 | Loading the registry rejects unknown method keys per kind; draw.io `cli_name` honored | "Closed key sets" table (observed registry keys + keys the executors read); `cli_spec` change in `apps.py:47`; test blast radius in `test_model.py` |
| REG-02 | Every `[[tool]]` carries `verified = YYYY-MM-DD`, validated by the loader | Loader rules (`type(v) is date`, future/TZ skew), `tier =` anchor for seeding, seeding algorithm and the 62-undated-entry gap |
| REG-03 | `make verify-registry` reports renamed assets, missing archive members, checksum drift, newer stable; weekly, never in the PR gate | `verify_registry.py` design, live prototype results (difftastic), state-file gap, workflow shape and test |
| REG-04 | GitHub release downloads verified by pinned checksum, else API sha256 digest | Live probe: 50 unverified methods -> 4 stay unverified (gron x2, jless x2: no digest published); staged-install refactor |
| REG-05 | Fresh binary smoke run; failure falls through | Shared `smoke_binary`, ExecContext seam, fixture strategy, GUI/AppImage risks |
| REG-06 | Launch without the dev venv on PATH | **Evidence that `--no-dev` alone is insufficient**; `--isolated` recommendation |
| REG-07 | macOS stubs never count as installed | `status.is_installed` table + injected probe + reason API |
| REG-08 | Version parser never fabricates a version | Root cause regex `versions.py:56`; fixture table |
| REG-09 | 35 data fixes applied, `managed-download` removed | Per-fix status table (already done / pending / needs verification) with live evidence |
| REG-10 | `drawio-cli` removed, `drawio-desktop` serves both | Test pins to update (tier/audience counts, duplicates, owner_probes) |
</phase_requirements>

## Project Constraints (from CLAUDE.md / AGENTS.md)

Source: `/var/home/bazzite/git/personal/tools-installer/AGENTS.md` and `.claude/*.md` (read this session). The planner must treat these as locked.

- **uv only.** Never `pip`, `poetry`, `conda`, hand-rolled venv. Dependency changes go through `uv add`/`uv remove`. (This phase needs no new dependency.)
- **English only** in every identifier, comment, docstring, log line, commit message.
- **Never bypass a quality gate**: no `# noqa`, `# type: ignore`, `# nosec`, vulture whitelist, no `@pytest.mark.skip/xfail` to go green. pyright is **strict**. Config relaxations are forbidden.
- **Tests**: xdist-safe (`tmp_path`, `monkeypatch` for HOME/env/cwd, no fixed paths/ports); never drop `-n auto`; deterministic and offline (mock GitHub/network); coverage floor 90 (`fail_under`) must not drop; new logic ships with tests.
- **Definition of done**: `make validate && make test` pass on the exact tree committed.
- **Coherent commits**: one self-contained valid change per commit; RED output goes in SUMMARY, test + code in one commit (RUN-LEDGER Phase 17 decision).
- **Never mutate the developer's host**: no `make setup/fix/uninstall`, no mutating `systemctl --user`, no editing real shell rc or agent settings. Real installs only in disposable containers (`make e2e` -> `scripts/container-e2e-verify.sh`).
- **Zero sudo**: no code path runs `sudo`/`pkexec`/`doas`; no new text may mention them in handoffs other than as the user-run command (Phase 17 scan).
- **Architecture rules** (`.claude/architecture.md`): one view registry, one nav path, one apply workflow, `setup.py` wiring only (decision functions belong in `installer/`), **no orphan helpers** (a shared helper with zero production callers is deleted). Registry authoring guidelines say the verification record is a `# Verified {date}:` prose comment; **this phase adds the structured `verified` key and must update that paragraph** (the comment stays as free-text; `tests/test_registry.py` greps `# Verified` comments and the literal phrase `no bin_dir`, so do not delete or reword comments).
- Project skill: `.claude/skills/tool-onboarding/SKILL.md` (registry onboarding checklist). It must gain a step "add `verified = <today>`" (it currently only mentions the `# Verified` comment).
- Code navigation: CodeGraph is available (`.codegraph/`); `codegraph explore` was not needed because every file was read directly.

## Summary

Phase 18 is almost entirely stdlib and in-repo work; no external package is added. The registry loader gets two closed contracts (`METHOD_PARAMS`, a required `verified` TOML date), the download pipeline gets one release snapshot (tag + asset sha256 digests), a shared smoke function, and a new `installer/verify_registry.py` that reuses the real install resolver so a passing check means the real install works. Live GitHub API probing this session confirms the central claim: **153 of 171 rendered (method, arch) assets expose a `digest`**, and the 50 currently-unverified `github_release` methods drop to **4** (gron x2, jless x2: their last releases predate digest publishing), not 0. Success Criterion 3's "wherever GitHub exposes a sha256 digest" wording is therefore the correct reading and the planner must not promise a literal 0.

Three findings change the plan relative to CONTEXT and must be decided by the planner (details in Open Questions):

1. **`uv run --no-dev` does not remove ruff from PATH when `.venv` was already synced with dev dependencies** (the documented `make install` then `make setup` flow). Reproduced in a scratch venv: `uv run --no-dev` still resolved `.venv/bin/ruff`. `uv run --isolated --no-dev` resolved nothing, left the venv untouched and costs about 0.1 s warm. REG-06 and Success Criterion 4 are only satisfiable with `--isolated` (or `--exact`, which mutates the dev venv), or with the container harness using `uv sync --no-dev`.
2. **The current unverified install path is a `curl | tar` shell pipeline with no staged file.** Digest verification and smoke-before-link both need the asset on disk first, so all `github_release`/`tarball`/`app` installs move to "fetch to a staging dir, verify, smoke, then place". The update path already has this shape (`_replace_archive`, `update_app`); the recommended design makes install reuse it instead of growing a second copy.
3. **`verify-registry`'s "only download when the digest changed since last verified" needs persisted state that D-07 does not place.** A weekly CI job is stateless. Recommended: a small JSON state file restored/saved with `actions/cache` (local default under the XDG cache), never committed.

**Primary recommendation:** Execute as six plans in this order: (1) schema + `verified` seeding + managed-download/drawio-cli removal + `version`/`sha256` keys, (2) independent small fixes in parallel (`parse_version`, macOS stub, `cli_name`, launch flags), (3) the 35 data fixes, (4) release/digest + staged install + smoke, (5) `verify_registry` + Makefile + workflow, (6) pin conversion and the live bump run. Keep every test offline; the only networked step is the final bump run, executed once and recorded.

## Architectural Responsibility Map

This is a single-process CLI/TUI installer plus a CI job; "tiers" below are the project's own layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Closed method keys, `verified` validation | `installer/model.py` (pure data/validation layer) | `registry.toml` (data) | model.py is the declared "pure data/validation layer"; METHOD_KINDS/OWNER_PROBES live there |
| `cli_name` link naming | `installer/apps.py::cli_spec` | `installer/uninstall.py` (imports it) | D-04: single-sourced naming |
| Release tag + digests (one fetch) | `installer/versions.py` | `download._resolve_target`, `version_status` | versions.py already owns `/releases/latest` |
| Verify, smoke, stage, link | `installer/download.py`, `installer/apps.py` | `installer/executors.py` (shared smoke + `link_executable`), `installer/engine.py` | download/app own staging; executors owns the shared link helper |
| Manager-kind smoke, ladder fall-through | `installer/engine.py::install_tool` | `executors.smoke_binary` | engine owns the method ladder |
| "unverified + reason" display | `installer/render.py::render_verification` | `InstallOutcome` | one render site shared by app.py and execute_screen.py |
| Drift check, issue upsert | new `installer/verify_registry.py` | `run.py::run_output` (gh), `.github/workflows/verify-registry.yml` | reuses the real resolver; CI only schedules it |
| Registry rewrite (verified/version/sha256) | `installer/verify_registry.py` writer mode | `tomllib` semantic guard | D-09 scoped line rewrite |
| macOS stub rule | `installer/status.py` | injected probe | D-10 closed table next to `is_installed` |
| Launch without dev venv | `Makefile`, `install.sh`, `scripts/container-e2e-verify.sh` | (optional) `installer/locations.py` PATH sanitizer | launch environment, not app logic |
| Version parsing | `installer/versions.py` | `version_status.py` (consumers) | one parser family |

## Standard Stack

### Core (all already present; nothing new to install)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `tomllib` | Python >= 3.11 (`requires-python = ">=3.11"`; scratch run used 3.12.12) | Parse registry; semantic guard for the line-rewrite writer | Already the loader; zero deps |
| `urllib.request` (`urlopen_fetch`, `Request(method="HEAD")`) | stdlib | API read, HEAD probes | `versions.urlopen_fetch` already adds the token to api.github.com only |
| `tarfile` / `zipfile` | stdlib | List archive members in verify-registry (never extract) | Avoids `tar`/`unzip` subprocesses; listing is traversal-safe |
| `hashlib.file_digest` via `checksums.sha256_file` | stdlib 3.11+ | sha256 of staged asset | Existing helper |
| `gh` CLI (GitHub-hosted runners ship it) | 2.x (host has an authenticated install) | Issue list/create/edit, label create | D-07; supports `--json`, `--label`, `--body-file`, `label create --force` [VERIFIED: `gh issue edit --help`, `gh issue list --help`, `gh label create --help` run this session] |
| `uv` | 0.11.28 on host | `uv run --no-dev --isolated` launch | Project toolchain |

### Supporting (test-time, already dev dependencies)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` >= 8, `pytest-xdist`, `pytest-cov` | per `pyproject.toml` | Test runner | all new tests |
| `pyyaml` (dev group) | >= 6.0.3 | Parse workflow YAML in the workflow test | `tests/test_ci_workflow.py` already does this; PyYAML maps bare `on:` to `True` (existing test handles it) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| line-rewrite writer + tomllib guard (D-09, locked) | `tomlkit` | Locked out by D-09 |
| `actions/cache` state file | always download every asset weekly | Simpler, but ~hundreds of MB weekly (VS Code tarballs) |
| `uv run --no-dev --isolated` | `--no-dev --exact` | `--exact` uninstalls 25 dev packages from `.venv` on every `make setup`, next `make test` reinstalls them |

**Installation:** none. `pyproject.toml` and `uv.lock` must be unchanged by this phase (assert with `git diff --quiet -- pyproject.toml uv.lock`).

**Version verification:** no packages added. Tooling facts verified live: `uv --version` -> `uv 0.11.28`; `gh` authenticated (`gh auth status`), `podman version 5.8.7`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | - | - | - | - | - | This phase installs no external package; stdlib + existing dev deps only |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

(`gsd_run query package-legitimacy check` was not run because there is nothing to check.)

## Architecture Patterns

### System Architecture Diagram

```
                    registry.toml  (90 -> 89 [[tool]], each with verified = date)
                          |
                    model.load_tools --> METHOD_PARAMS closed-key check, verified check,
                          |              pinned-kind rule (version+sha256 when URL has {ver})
                          v
   ---------------- INSTALL PATH (user, TUI/CLI) ----------------------------------------
   engine.install_tool --(ladder: method by method)-->
        |
        |-- github_release/tarball --> download._resolve_target
        |        |                          |-- ctx.resolve_release(repo) --> versions.resolve_github_release
        |        |                          |        (ONE /releases/latest read: tag + digests)
        |        |                          '-- expected = pinned checksum file | pinned sha256 | release.digests[asset] | None(+reason)
        |        v
        |    fetch asset -> staging dir -> verify (mismatch => ChecksumMismatch => ladder halts, nothing linked)
        |        -> extract to <opt>.new -> smoke(staged binary) -> [fail => ExecutorError => next method]
        |        -> swap into opt, link_executable (atomic) -> InstallOutcome(verified, unverified_reason)
        |
        |-- app (macOS zip) --> same staged flow (curl -> sha256 -> ditto -> smoke -> move -> cli link via cli_spec/cli_name)
        |
        '-- script/brew/node/... --> executor runs --> engine: smoke(shutil.which(tool.cmd)) if resolvable
                                                       [fail => next method]
   render.render_verification: "sha256 ✓" | "unverified (<reason>)"

   ---------------- DRIFT PATH (CI weekly / dev, read-only) -----------------------------
   make verify-registry --> verify_registry.main
        |  for each tool/method/os/arch of kind github_release|tarball|app:
        |     download._resolve_target (same resolver) -> URL / member / checksum source
        |     github_release: asset in release asset list? ; checksum file entry == API digest?
        |     tarball/app: HEAD url ; pinned: newer stable tag? (GitHub-hosted URLs only)
        |     member check: download + tarfile/zipfile LIST only when digest != state[url] or no digest
        |  not-checkable kinds -> listed
        |  result: OK | DRIFT | INCONCLUSIVE (network / 403 / 429)
        |-- --issue flag (workflow only): gh issue list --label -> edit or create   (DRIFT only)
        '-- --write (maintainer, network): scoped line rewrite of verified/version/sha256,
                                           re-parse guard, only for entries that passed
   .github/workflows/verify-registry.yml: schedule + workflow_dispatch, contents: read, issues: write
```

### Recommended Project Structure
```
installer/
  model.py              # + METHOD_PARAMS, verified check, pinned-kind rule; - managed-download
  versions.py           # + Release, resolve_github_release, release_resolver; parse_version fix
  download.py           # DownloadTarget gains expected sha256 / unverified_reason; staged install; smoke hook
  apps.py               # cli_spec honors cli_name; install_app staged + sha256 + smoke
  executors.py          # + smoke_binary (shared); link_executable unchanged
  engine.py             # + manager-kind smoke, unverified_reason on InstallOutcome
  render.py             # render_verification shows the reason
  status.py             # + MACOS_STUBS table, reason API
  assets.py             # + render_pinned_url (pure, {ver} -> version)
  verify_registry.py    # NEW: check + issue upsert + writer
  install_ownership.py  # - _managed_download
tests/
  test_verify_registry.py, test_makefile.py, test_verify_registry_workflow.py (NEW)
.github/workflows/verify-registry.yml (NEW)
```

### Pattern 1: Closed key set per kind (D-01)
**What:** `METHOD_PARAMS[kind]` lists every allowed non-structural key; `os`, `arch`, `kind` are structural and excluded (same as the existing `params` comprehension).
**When to use:** at the top of the per-method loop in `load_tools`, before the per-kind value checks.
**Example (proposal):**
```python
# Source: proposal built on the existing params comprehension (model.py:666)
if unknown := set(params) - METHOD_PARAMS[kind]:
    raise ValueError(f"tool '{row['id']}': method '{kind}' has unknown key '{sorted(unknown)[0]}'")
```
Note: `skill_pack` maps to `frozenset()`; the existing `len(entry) != 1` check (model.py:750) keeps rejecting `os`/`arch` on it and must stay.

### Pattern 2: One release snapshot with an injection seam that keeps tag-only callers unchanged (D-05)
**What:** `Release(tag, digests)`; `resolve_github_tag(repo, fetch) = resolve_github_release(repo, fetch).tag`. `ExecContext` gains an optional `resolve_release`. When it is `None`, `_resolve_target` wraps `ctx.resolve_tag` as `Release(tag, {})` so every existing offline test (lambda tag resolvers) keeps passing and is simply "unverified: no digest".
**Production wiring problem:** the chain `setup.py -> app -> execute_screen -> session.run_installs -> engine.install_tool` passes only `resolve_tag`. To get digests in production without touching 12 callers, derive the release resolver from the tag resolver in one place:
```python
# proposal (versions.py); the identity check is the only production/test discriminator
def release_resolver(resolve_tag: TagResolver) -> ReleaseResolver:
    if resolve_tag is resolve_github_tag:
        return resolve_github_release
    return lambda repo: Release(resolve_tag(repo), {})
```
`engine.install_tool` builds `ExecContext(..., resolve_release=release_resolver(resolve_tag))`. A per-run memo (`functools.cache` over repo) is optional for install, **required** for verify-registry (many methods share a repo).

### Pattern 3: Stage -> verify -> smoke -> place
**What:** Unify install and update through the staged flow that update already has (`download._replace_archive`, `download._replace_raw`, `apps.update_app`). Install = update with "nothing live yet", plus the verify and smoke steps inserted before the swap.
**Why:** (a) digest verification needs the file on disk, which the `curl | tar` pipeline in `_install_unverified` never provides; (b) extracting in place into `~/.local/opt/<name>` overwrites an existing good tree before any smoke, so "an existing good link is untouched" (D-06) is false for in-place extraction; (c) it deletes duplicate code (ponytail: delete before add).
**Constraint:** keep the on-disk layout `~/.local/opt/<link.name>/<member>` with a symlink in the bin dir resolving to a regular file inside that opt dir; Phase 17's `plan_removal` proof (17-09) depends on it.

### Pattern 4: Shared smoke function (D-06)
```python
# proposal (executors.py); built on run_output/CommandError as D-06 requires
def smoke_binary(path: Path, argv: Sequence[str] = ("--version",), timeout: float = 5.0) -> None:
    try:
        run_output([str(path), *argv], timeout=timeout)
    except CommandError as exc:
        if exc.returncode in (126, 127) or _LOADER_ERROR.search(exc.detail):
            raise ExecutorError(f"smoke run failed for {path}: {exc}") from exc
        # any other non-zero exit, or timeout (124): the binary executed, so it passes
```
`run_output` already maps `OSError` to `CommandError(cmd, 127)` and folds stderr into `detail` for non-zero exits [VERIFIED: installer/run.py:98-107, read this session]. Loader errors that exit 1 (`version 'GLIBC_2.34' not found`) are only detectable through `detail`, which is why the stderr scan is required.

### Pattern 5: Scoped line rewrite with semantic guard (D-09)
Anchor facts [VERIFIED: python script over `installer/registry.toml` this session]: all 90 `[[tool]]` blocks contain exactly one `tier = ` line, positioned before the first `[tool.*]`/`[[tool.method]]` header; 39 `checksum =` lines and 0 `version =` lines exist at line start; there are 230 `[[tool.method]]` and 90 `[[tool]]` headers. Therefore `verified = <date>` is inserted on the line directly after `tier = ...` (seeding) and later replaced in place (writer). A key placed after a `[[tool.method]]` header would silently belong to the method table, which D-01 would reject, so the anchor must be `tier`.
```python
# writer guard (proposal)
new_doc = tomllib.loads(new_text)
expected = apply_edits(tomllib.loads(old_text), edits)   # dict-level application of ONLY the intended edits
if new_doc != expected: raise RegistryWriteError("unintended change")
```
TOML dates round-trip as `datetime.date`, so equality works.

### Anti-Patterns to Avoid
- **`isinstance(v, date)` for the `verified` check.** `datetime.datetime` is a `date` subclass; TOML `2026-10-13T00:00:00Z` would pass. Use `type(value) is date`. A quoted string `"2026-10-13"` must fail (it is a `str`).
- **A second digest fetch** (D-05 forbids it; "latest" can move between reads).
- **Putting stub logic in `setup.py`** (architecture rule 4): `is_installed` lives in `installer/status.py`.
- **Real subprocess smoke against fake `b"member-bytes"` files.** Existing fixtures write non-executable junk; a real smoke on them returns 127 and breaks hundreds of tests. Make the shared fixture write `#!/bin/sh\nexit 0\n` and chmod it (hermetic, exercises the real function).
- **Hand-parsing registry TOML for edits beyond the three target keys.**
- **Issue creation from a bare `make verify-registry`.** Gate it behind an explicit `--issue` flag set only by the workflow so the local command is read-only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| sha256 of a file | custom loop | `checksums.sha256_file` (`hashlib.file_digest`) | already tested |
| Parse `<hash>  <name>` / sidecar checksum text | regex | `checksums.expected_sha256` | handles `*name`, path prefixes, bare sidecars; parses draw.io's `Files-SHA256-Hashes.txt` (verified: returned the exact API digest for both AppImages) |
| Mismatch hard-fail | new exception | `checksums.ChecksumMismatch` | engine already halts the ladder on it |
| Atomic link/swap/rollback | new swap code | `atomic.replace_symlink`, `staged_sibling`, `recover_update_remnants`, `executors.link_executable`, `download._replace_archive` | Phase 12/17 hardened state machine |
| Run a command and read output / normalize OSError | `subprocess` calls | `run.run_output` + `CommandError` | already used by version probes |
| URL/member/checksum/arch resolution for verify-registry | a second resolver | `download._resolve_target`, `assets.arch_tokens`, `assets.render_asset` | D-07: a passing check must mean the real install works |
| Archive member listing | `tar`/`unzip` subprocess | `tarfile.open`/`zipfile.ZipFile` `.getnames()` | no extraction = no traversal exposure |
| Workflow YAML assertions | grep | `yaml.safe_load` as in `tests/test_ci_workflow.py` | existing pattern |
| TOML rewriting | tomlkit | scoped line rewrite + `tomllib` guard | locked D-09 |
| GitHub issue upsert | REST client | `gh issue list/create/edit`, `gh label create --force` via `run_output` | locked D-07; `Runner` returns `None`, so use `OutputRunner`/`run_output` to read the JSON |

**Key insight:** every capability this phase needs already has a hardened helper in the tree. The new code is mostly glue plus one new module (`verify_registry.py`); the largest correctness risk is changing `install_download`/`install_app` semantics, not building new machinery.

### Ponytail reuse pass (required by the run playbook)

| Capability | Reuse (existing) | New |
|------------|------------------|-----|
| closed keys | `METHOD_KINDS`/`OWNER_PROBES` convention, `_parse_closed_string_list` style errors | one dict `METHOD_PARAMS` |
| `verified` check | `_parse_enum` style `f"tool '{id}': ..."` errors | ~8 lines in `load_tools` |
| cli_name | `apps.cli_spec` (already imported by `uninstall.py`) | 3 lines |
| digest | `urlopen_fetch`, `resolve_github_tag` body, `ChecksumMismatch` | `Release`, `resolve_github_release` |
| fetch-to-file + hash | `download._install_verified`, `_fetch_update_asset`, `sha256_file` | generalize "expected hash" source (file entry vs hex) |
| staged install | `_replace_archive`, `_replace_raw`, `_extract_into`, `update_app` | smoke hook between extract and swap |
| smoke | `run_output`, `CommandError`, `ExecutorError` | `smoke_binary` |
| stub rule | `is_installed` structure, `gnu-bash` `detect_path` precedent | `MACOS_STUBS` table + probe |
| parse fixes | `_match_observed_version`, `_NAME_PREFIX_BOUNDARY` | tighten regex + token normalizer |
| drift check | `_resolve_target`, `arch_tokens`, `render_asset`, `ExecContext` | `verify_registry.py` |
| issue upsert | `run_output` | ~25 lines |
| workflow test | `tests/test_ci_workflow.py` pattern | new file |
| Makefile test | none exists | `tests/test_makefile.py` (text parse) |
| container harness | `scripts/container-e2e-verify.sh` | `uv sync --no-dev` + `--isolated` launch |

## Closed key sets (proposal for `METHOD_PARAMS`)

Derived as (keys observed in `registry.toml` per kind, counted by a `tomllib` script this session) UNION (keys the executors/consumers read via `method.params.get(...)` / `require_str(method, ...)` / `_opt_str(method, ...)`, found by grep this session). `kind`, `os`, `arch` are structural.

| Kind | Allowed keys | Evidence notes |
|------|--------------|----------------|
| `script` | `url shell bin_dir env detect_path version_file args` | registry: all seven used; Phase 22 adds `paths remove update writable_prefix` here |
| `node` | `npm_pkg co_install allow_build min_node smoke versions` | all validated in `load_tools` |
| `uv-tool` | `pypi_pkg` | executors.py reads `pypi_pkg` |
| `sdkman` | `candidate bin_dir version` | `version` read by executors (registry does not use it today) |
| `host_setup` | `setup_id` | |
| `skill_pack` | (empty set) | existing `len(entry) != 1` check stays |
| `github_release` | `repo asset checksum member strip raw archive bin_name bin_dir` | `bin_name`, `bin_dir` are read by `download.py` though unused in the registry today |
| `tarball` | `url member strip bin_name archive bin_dir version sha256` | `version`/`sha256` are the D-03/D-05 additions |
| `app` | `url app cli cli_name version sha256` | |
| `dnf` `apt` `pacman` | `package` | |
| `brew` | `formula detect_path min_os_version bin_dir` | |
| `cask` | `cask app min_os_version` | |
| (new, name is discretion) smoke argv | key on the kinds that install a binary | see Open Question 7 |

Observed counts for orientation: `github_release` 89 methods, `brew` 59, `script` 16, `pacman` 11, `dnf` 9, `apt` 9, `cask` 9, `app` 7, `skill_pack` 7, `sdkman` 5, `tarball` 5, `node` 3, `uv-tool` 1, `host_setup` 1 (total 230). Tool-level keys are NOT closed by D-01 (only method params are).

## Live findings (GitHub API, read-only, this session)

### Digest coverage [VERIFIED: gh api repos/<r>/releases/latest over all 89 github_release methods, rendered per declared os/arch]
- 171 (method, arch) assets rendered: **153 have a `digest`, 12 have none (`NODIGEST`), 6 do not exist (`MISSING`)**.
- Unverified methods today: 89 total github_release methods, 39 with a `checksum` line, **50 without**. Of those 50: **43 will verify via digest immediately**; difftastic x2 and delta macOS x1 become verifiable after their data fixes (46); **gron x2 and jless x2 (4 methods) stay "unverified"** because their latest releases publish no digest (gron v0.7.1, jless v0.9.0). Result: 50 -> 4, not 0.
- `MISSING` assets (real drift today, all are audit data fixes): `difft-x86_64-unknown-linux-gnu.tar.gz` and 3 siblings (the pre-fix template: upstream now names assets `difft-0.71.0-x86_64-unknown-linux-gnu.tar.gz`), `delta-0.20.1-x86_64-apple-darwin.tar.gz` (no Intel mac asset upstream), `jless-v0.9.0-aarch64-unknown-linux-gnu.zip`.
- draw.io `releases/latest` is `v32.4.1` and exposes digests for every asset including `drawio-x86_64-32.4.1.AppImage` (`sha256:c687a9f1...`), `draw.io-arm64-32.4.1.zip` (`sha256:0ec4d3cd...`), `draw.io-x64-32.4.1.zip` (`sha256:5587c2a5...`). The `Files-SHA256-Hashes.txt` asset parses with `expected_sha256` and yields the same hash as the API digest.
- Sublime stable is build **4215** (`stable_update_check` -> `"latest_version": 4215`); `sublime_text_build_4215_{mac.zip,x64.tar.xz,arm64.tar.xz}` return HTTP 200 on HEAD; current pin is 4200.
- JetBrains arm64 Toolbox URL `https://data.services.jetbrains.com/products/download?platform=linuxARM64&code=TBA` redirects to `jetbrains-toolbox-3.8.1.88030-arm64.tar.gz` (HTTP 200 after redirects).
- Candidate asset names confirmed: `gh_2.102.0_macOS_{amd64,arm64}.zip`, `gitui-mac.tar.gz` and `gitui-mac-x86.tar.gz` in repo `gitui-org/gitui` (v0.28.1), `tealdeer-rs/tealdeer` v1.9.0 with `tealdeer-linux-<machine>-musl(.sha256)` and `tealdeer-macos-<machine>`, delta `x86_64-unknown-linux-musl`, hyperfine musl tarballs for both arches. All carry digests.

### Which entries are actually "pinned"
Only these `app`/`tarball` methods embed a version/build in the URL today [VERIFIED: tomllib script]: drawio-desktop x2 (`v31.0.2`, macOS arm64/x64) and drawio-cli x2 (removed), sublime x3 (build `4200`: mac zip, Linux x64, Linux arm64). vscode (`update.code.visualstudio.com/latest/...`) and jetbrains-toolbox (`products/download?...`) are **latest-style URLs: not pinned**, so "entries without a pin are unchanged". The two pin conversions of consequence are drawio (31.0.2 -> 32.4.1) and sublime (4200 -> 4215).

## The 35 audit data fixes: status and recommended action

State checked against the current `registry.toml` this session. "Optional" sub-bullets inside an audit item are not separate fixes. Items to resolve with a command or live check before editing are marked CHECK.

| # | Fix | Current state | Recommended action / test |
|---|-----|---------------|---------------------------|
| C1 | volta: drop `os` on script method or add macOS script; fix false comment | script has `os = ["debian","arch","fedora"]`; comment says no macOS script | Drop the `os` restriction on the script method; rewrite comment; add `# Verified 2026-10-13` incl. "upstream unmaintained, recommends mise". Test: `resolve_methods` for a macOS platform returns the script method |
| C2 | podman: split brew method | single brew method | `os=["macos"], arch=["arm64"]` method + Linux-only brew method; note podman.io stance. Test: resolve per platform |
| C3 | docker: dnf package | dnf `docker`, apt `docker.io` | dnf -> `docker-cli` (Fedora package page exists: packages.fedoraproject.org/pkgs/moby-engine/docker-cli/, HTTP 200). Keep apt `docker.io` and pacman `docker` (engine+cli) and document in a comment; name stays "Docker CLI". Test: registry assertion |
| C4 | uv: `UV_NO_MODIFY_PATH=1` | script has no `env` | `env = { UV_NO_MODIFY_PATH = "1" }`. Test: params assertion |
| C5 | sdkman: comment to 5.23.2 + zip/unzip prerequisite | comments say 5.23.0 | comment-only; keep `no bin_dir`-style phrases untouched |
| C6 | colima: `recommends = ["docker"]` | no recommends | add; `recommends` ids must exist; test via existing recommends validation |
| C7 | fnm: optional macOS script with `--force-no-brew` | brew only on macOS | Optional sub-bullet. Recommended: apply (script args regex allows `--force-no-brew`); if skipped, record in the fix ledger as "optional, not applied" |
| C8 | brew: arch-split macOS script | one macOS method, `bin_dir=/opt/homebrew/bin` | split: `arch=["arm64"]` keeps `/opt/homebrew/bin`; add `arch=["amd64"]` with `bin_dir=/usr/local/bin`; remove the stale "Intel" comment |
| C9 | missing `# Verified` dates | 15 listed tools undated | superseded by the `verified` key seeding (see Seeding) |
| D1 | difftastic asset templates | `difft-{arch.machine}-...` (pre-fix) | `difft-{ver}-{arch.machine}-unknown-linux-gnu.tar.gz` and `...-apple-darwin.tar.gz`. **This pre-fix template is the verify-registry drift fixture.** Optional musl amd64 method: skip unless trivial |
| D2 | delta: macOS `arch=["arm64"]`, fix stale musl comment | macOS method has no `arch` | add `arch = ["arm64"]`; replace the comment at the Linux method (a musl asset exists for x86_64 only) |
| D3 | gh: macOS github_release | Linux only | add method: `asset = "gh_{ver}_macOS_{arch.deb}.zip"`, `archive = "zip"`, `member = "gh_{ver}_macOS_{arch.deb}/bin/gh"`, `checksum = "gh_{ver}_checksums.txt"`; remove `:423` comment. Asset names live-confirmed. Not install-tested: verify-registry member check covers it |
| D4 | gitui: repo + macOS methods | `repo = "extrawurst/gitui"`, Linux only | `repo = "gitui-org/gitui"`; add `gitui-mac.tar.gz` (arm64) and `gitui-mac-x86.tar.gz` (amd64), `member = "gitui"`, `strip = 0`; drop comment |
| D5 | tealdeer repo | `dbrgn/tealdeer` x2 | `tealdeer-rs/tealdeer` x2 |
| D6 | ruff: add `uv-tool` method after the github_release methods | github_release x2 + brew | add `kind = "uv-tool"`, `pypi_pkg = "ruff"` after the release methods (before or after brew: "same rank, stable sort"); ownership test |
| D7 | hyperfine musl; `# Verified` on all 23 | gnu assets | Optional musl switch: apply (assets exist for both arches, live-confirmed) only if the verify-registry member/strip check passes; `# Verified` becomes the `verified` key |
| E1 | sublime Linux member | **already done in Phase 17** (`member = "sublime_text/sublime_text"`, `bin_name = "subl"`) | skip (CONTEXT D-15); pin conversion handled in the pin plan |
| E2 | jetbrains-toolbox member + arm64 tarball + stale comment | member `bin/jetbrains-toolbox`, `strip 1` already done in Phase 17; no arm64 method; comment still says no arm64 URL | add arm64 tarball method (`arch=["arm64"]`, URL above, same `member`/`strip`); update the comment |
| E3 | codex `CODEX_NON_INTERACTIVE` | **already present** (`env = { CODEX_NON_INTERACTIVE = "1" }`) | skip, record as done |
| E4 | opencode `--no-modify-path` | script has no `args` | `args = ["--no-modify-path"]` (matches `_SCRIPT_ARG_RE`) |
| E5 | jless Linux `arch=["amd64"]` | no arch | add; fixes the live MISSING aarch64 asset |
| E6 | broot macOS `arch=["arm64"]` | no arch | add |
| E7 | drawio Linux `checksum = "Files-SHA256-Hashes.txt"`, re-pin mac to 32.4.1 | none | add checksum on the Linux methods of `drawio-desktop` (drawio-cli is removed); mac re-pin handled by the pin plan |
| E8 | kitty: allow script on macOS | script `os=[debian,arch,fedora]`, cask on macOS | audit says "re-verify install root `/Applications/kitty.app` and `bin_dir` before doing this": **CHECK** (not verifiable here; no macOS). Recommended: apply only if the installer script's macOS behavior can be read from `https://sw.kovidgoyal.net/kitty/installer.sh`; otherwise record as "not applied: unverifiable without macOS" |
| E9 | wezterm optional macOS `app` method | cask only | Optional; needs the new `{ver}` pin support (D-03 makes it possible). Recommended: skip; record |
| E10 | glab native fallbacks | brew only | add `dnf glab`, `pacman glab`, `apt glab`. Live-confirmed: Arch `extra/glab` 1.123.0, Fedora package `glab` page exists, Debian `glab` in trixie/forky/sid (`1.53.0-1`; bookworm only via backports). Ubuntu availability is NOT verified [ASSUMED]; keep `apt` because the registry's `debian` os covers Debian and the method is a fall-through |
| E11 | pi uninstall text names pnpm | `uninstall = "pnpm remove -g @earendil-works/pi-coding-agent"` | soften the text (data only; gap 7 is a code item) |
| F1 | graphify comment correction / uninstall text | postinstall already removed in Phase 17 | comment correction; add `uninstall = "graphify uninstall; uv tool uninstall graphifyy"` only if the remove path stays manual |
| F2 | codegraph comment correction | comment-only | re-date, record `--no-permissions` finding and `codegraph upgrade` migration |
| F3 | rtk comment | comment-only | re-date to 0.52.0, record the two facts |
| F4 | ponytail: pi probe + Claude removal lines | probes claude, codex only | add `{ harness = "pi", via = "plugin-cli", match = "DietrichGebert/ponytail" }` (pi is in `supported_harnesses`; match fits `_SKILL_MATCH_RE`); add Claude removal lines (`/plugin uninstall ponytail@ponytail`) |
| F5 | superpowers: drop the "or, instead" marketplace alternative | 3 lines in `by_harness.claude` | delete `"or, instead, from the obra marketplace:"` and the two marketplace lines |
| F6 | matt-pocock-skills: default vs claude probe | default `npx skills ... add`; claude probe `plugin-cli` | audit offers two routes; **discretion**: make the claude/codex plugin route the documented default in `install.instructions` text, leaving probes unchanged |
| F7 | opengsd: Node >= 24 note | none | add a line to the install instructions |
| F8 | puppeteer arm64 note | comment | append the CfT note |

Count check: C 9 + D 7 + E 11 + F 8 = 35 numbered items. Already satisfied by Phase 17: E1 (sublime), E3 (codex), part of E2. The planner's fix ledger must list all 35 with {applied | already-done | optional-not-applied-with-reason} and a test or verify-registry mapping per applied item (SPEC AC 11 "each backed by a test or a verify-registry pass").

## Seeding the `verified` key (REG-02)

- Anchor: insert `verified = YYYY-MM-DD` directly after the single `tier = ...` line of every `[[tool]]` block (verified unique and pre-subtable for all 90; see Pattern 5).
- Date source: for each tool, the **latest** `# Verified YYYY-MM-DD` comment date found from the end of the previous tool's last content line through the end of this tool's last content line (comments directly above `[[tool]]` and inside the block). A prototype of this rule over the file this session found a date for 28 tools and found 7 tools with multiple dates (cursor-agent, codegraph, graphify, rtk, sdkman, jetbrains-toolbox, kitty): take the max. CONTEXT says 34; the discrepancy is placement-heuristic dependent (37 `# Verified` lines exist), so the plan must freeze the rule in a one-off script and report the resulting count rather than assert 34.
- **Gap:** about 62 tools have no `# Verified` comment. The key is mandatory, so they need a seed date. Recommendation [ASSUMED]: `2026-10-13`, the date audits C/D/E/F re-checked the catalog live (audit D 7 and C 9 both specify exactly this date for the undated entries). Needs user confirmation (Open Question 2). Non-checkable entries (41 of 90: brew/script/pkg-manager/skill kinds) can never be refreshed by verify-registry, so their key will legitimately stay at the seed date.
- Loader rules: required; `type(value) is date`; not later than today (+1 day tolerance recommended, see Pitfall 7); error text includes the tool id; inject `today` into `load_tools(manifest_path, *, today: date | None = None)` for deterministic tests.
- Do NOT add a `verified` field to the `Tool` dataclass unless a consumer needs it (no consumer exists in this phase; architecture rule 5). Validation alone satisfies REG-02.

## Common Pitfalls

### Pitfall 1: `--no-dev` does not hide dev tools in an already-synced venv
**What goes wrong:** `make install` (dev sync) then `make setup` with `uv run --no-dev setup.py` still puts `.venv/bin` (containing ruff) first on PATH; ruff reads as "installed" with unknown owner.
**Evidence [VERIFIED: scratch venv, this session]:** after `uv sync` (dev), `uv run --no-dev python -c "import shutil;print(shutil.which('ruff'))"` printed `<venv>/bin/ruff`. With `--no-dev --exact` it printed `None` but uv reported `Uninstalled 25 packages`. With `uv run --isolated --no-dev` it printed `None`, the venv still contained ruff (untouched), and the run took 0.09 s warm. The same `--isolated --no-dev` run in the real repo printed `installer/__init__.py None` for `(installer.__file__, which('ruff'))` and `setup.py --help` worked. In the real repo `.venv/bin/ruff` exists after a plain `uv run --no-dev` (inexact sync).
**How to avoid:** Makefile launchers and `install.sh` use `uv run --no-dev --isolated setup.py`; the Makefile test asserts both flags on launcher targets and neither on `validate`/`test`; `scripts/container-e2e-verify.sh` (`uv sync` at line 197, `uv run setup.py ${args}` at line 261) uses the same launch form (and `uv sync --no-dev`) so the container acceptance for Success Criterion 4 means something. `tests/test_install_sh.py:223` currently asserts the literal `"uv run setup.py --all --yes"` and must change with `install.sh`. README line ~294 documents `make setup` as `uv run setup.py`.
**Warning signs:** the container e2e transcript still lists ruff as installed/unknown-owner.

### Pitfall 2: Existing download tests write non-executable fake members
`tests/test_download.py::fixture_runner` writes `b"member-bytes"` when it sees an extraction argv. A real smoke on that file fails. Change the shared fixture to write an executable `#!/bin/sh` script (and keep tests asserting on-disk results), and add one hermetic fake-binary-exits-127 test. Do not add a global autouse "smoke off" fixture (it would hide product behavior).

### Pitfall 3: `ChecksumMismatch` is deliberately not an `ExecutorError`
Digest mismatch must reuse it so `engine.install_tool` halts the ladder (engine.py ChecksumMismatch branch). Smoke failures must be an `ExecutorError` (falls through). Do not swap them.

### Pitfall 4: Order of operations is a security property
verify (mismatch aborts) -> smoke (executes the freshly downloaded binary) -> link. Smoke must never run before the integrity check, otherwise a tampered artifact is executed.

### Pitfall 5: `VersionError` hides the cause needed for "inconclusive"
`resolve_github_tag` wraps every `OSError`/`JSONDecodeError` in `VersionError`. verify-registry must classify by `__cause__`: `urllib.error.HTTPError` 403/429 or a non-HTTP `URLError`/timeout -> INCONCLUSIVE (no issue call); HTTP 404 -> repo/release gone -> DRIFT. Rate limits on api.github.com return HTTP 403/429, both `HTTPError` (an `OSError`) [ASSUMED for the exact status codes; standard GitHub API behavior].

### Pitfall 6: GUI binaries and AppImages under smoke
`<binary> --version` on a GUI app may open a window or hang (jetbrains-toolbox, drawio/Electron, unknown behavior [ASSUMED]); an AppImage without FUSE exits non-zero with a message that is neither 126/127 nor `GLIBC_` and so passes smoke while being unusable. Mitigations: timeout counts as pass and is short (`PROBE_VERSION_TIMEOUT = 5.0` exists in `versions.py`); a declared per-entry smoke argv; optionally run with `DISPLAY`/`WAYLAND_DISPLAY` unset. `make e2e` (podman, ~33 min) is the arbiter; its baseline is `installed=73 failed=0 manual_required=8` (17-13-SUMMARY).

### Pitfall 7: Future-date check vs timezone
CI (UTC) writes "today"; a developer behind UTC would see that date as tomorrow and fail to load. Allow `today + 1 day` (or compare against UTC date). Inject `today` in tests. [ASSUMED]

### Pitfall 8: Manager-kind smoke on tools with no resolvable binary
`sdkman` has `cmd = "sdkman-init.sh"` (a sourced script); skill packs and `host_setup` have no binary; a brew/script install may not be on this process's PATH until `prepend_path`. Rule: smoke manager kinds only when `shutil.which(tool.cmd)` resolves to an executable, after the engine's `prepend_path`; unresolved -> skip (not fail). This is a D-06 gap resolved by judgment (Open Question 7).

### Pitfall 9: The scheduled workflow silently stops
GitHub only runs `schedule` on the default branch and disables scheduled workflows in a public repo after 60 days without repository activity; runs can be delayed at the start of the hour [CITED: docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows, fetched this session]. Use an off-peak minute (not `:00`) and keep `workflow_dispatch`.

### Pitfall 10: Rewriting `registry.toml` by regex over the whole file
Comments contain strings like `version = ...` in prose. Anchor patterns to the start of a line within the identified block and re-parse; the guard catches the rest.

### Pitfall 11: Large mechanical test blast radius
`load_tools` is called with inline TOML in `tests/test_model.py` (30 `[[tool]]` fixtures) and `tests/test_skill_lifecycle.py` (1). Every fixture needs a `verified` key once the loader requires it (add it in the `_write`/`_node_registry` helpers unless a test is about a missing key). Registry-pinned counts must be updated for drawio-cli removal: tier distribution `{"system": 26, "ai": 17, "user": 47}` -> user 46; audience `{"both": 47, "ai": 9, "human": 34}` -> `both` stays 47 (drawio-cli leaves, drawio-desktop joins), `human` 33; the cmd-duplicates assertion becomes `{}`; the D-09 borderline tuple loses `drawio-cli`; the `owner_probes` pins at `test_registry.py:1968-1969` and `tests/test_install_ownership.py:28,111,180` change. Total tools 90 -> 89.

### Pitfall 12: `parse_version` fix touches three public behaviors
`parse_version`, `parse_status_version` and `extract_observed_version` share `_match_observed_version`. Normalize tokens in one helper (strip surrounding quotes and trailing commas/semicolons, drop a leading `version=`), then tighten the glued-name prefix to require a non-empty alphabetic name. `extract_observed_version` currently documents "verbatim"; with normalization it returns the normalized token, so its docstring and tests change.

## Code Examples

Verbatim in-repo anchors (read this session; every in-repo literal used in the proposals above appears here).

```python
# installer/model.py:22-37 (METHOD_KINDS)
METHOD_KINDS = (
    "script", "node", "uv-tool", "sdkman", "host_setup", "skill_pack",
    "github_release", "tarball", "app", "dnf", "apt", "pacman", "rpm_ostree", "brew", "cask",
)
# installer/model.py:54-64 (OWNER_PROBES) -- first entry is the one to delete
OWNER_PROBES = ("managed-download", "host-setup", "brew", "apt", "dnf", "pacman", "rpm-ostree", "pnpm", "sdkman")
# installer/model.py:666
params = {k: v for k, v in entry.items() if k not in ("kind", "os", "arch")}
# installer/versions.py:56 (root cause of parse_version('-1') == (1,0,0,1))
_NAME_PREFIX_BOUNDARY = re.compile(r".*[-\s](?=[vV]?\d)")
# installer/download.py:43-47
@dataclass(frozen=True)
class ExecContext:
    runner: Runner
    platform: Platform
    resolve_tag: TagResolver
# installer/download.py:76-82
class DownloadTarget:  # fields: url, member, asset, checksum: tuple[str, str] | None = None
# installer/install_ownership.py (_PROBES entry to delete)
    "managed-download": _managed_download,
# installer/apps.py:62-64 (cli_spec tail; cli_name must replace `name = path.name`)
    name = path.name
```
(The line-range refs in CONTEXT are about 12 lines off for `load_tools`; anchor by symbol.)

### Verified behavior of the parser today
```
parse_version('-1')   -> (1, 0, 0, 1)   # fabricated (bug)
parse_version('--1')  -> (1, 0, 0, 1)   # fabricated (bug)
parse_version('jq-1.8.1') -> (1, 8, 1, 1)  # legitimate glued form, must keep working
parse_version('version=0.44.1, os=linux') -> None   # lazygit form, must become 0.44.1 via extract_observed_version
parse_version('"0.20.0"') -> None                   # quoted form, must unquote
```
[VERIFIED: ran the functions this session.] Audit B WR-02 also lists `--2`, `-v1.2.3` and `a-1` as parsing; the first two must become `None`. `a-1` is indistinguishable from the legitimate `jq-1` shape; the planner should decide the expectation explicitly in the fixture table (Open Question 6).

### Workflow skeleton (proposal)
```yaml
name: verify-registry
on:
  schedule:
    - cron: "17 5 * * 1"
  workflow_dispatch:
permissions:
  contents: read
  issues: write
jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      GH_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: actions/cache@v4            # restores/saves the digest state file
        with: { path: .cache/verify-registry, key: verify-registry-${{ github.run_id }}, restore-keys: verify-registry- }
      - run: make verify-registry ARGS="--issue --state .cache/verify-registry/state.json"
```
The workflow test asserts: `on` keys == {`schedule`, `workflow_dispatch`} (PyYAML parses `on` as `True`; existing test shows the fallback), `permissions == {"contents": "read", "issues": "write"}`, no `git push`/`git commit`/`gh pr` step, and that `.github/workflows/ci.yml` never mentions `verify-registry`.

### Issue upsert (proposal)
```
gh label create registry-drift --force --description "..." 
gh issue list --label registry-drift --state open --json number --limit 1   -> run_output (returns str)
gh issue edit <n> --body-file <tmp>    |    gh issue create --title ... --label registry-drift --body-file <tmp>
```
Write the body to a temp file (`--body-file`), never interpolate asset names into a shell string; render registry/asset strings inside code spans so asset names cannot inject mentions or markdown.

### Makefile (proposal)
```make
setup:  ## ...
	uv run --no-dev --isolated setup.py $(ARGS)
verify-registry:  ## Check pinned/latest release assets against upstream (read-only, needs network)
	uv run --no-dev python -m installer.verify_registry $(ARGS)
```
`verify-registry` is not a `setup.py` launcher; add it to `.PHONY`. `make help` regex `^[a-zA-Z_-]+:.*?## .*$` already matches a hyphenated target.

## State of the Art

| Old approach | Current approach | Changed | Impact |
|--------------|------------------|---------|--------|
| Per-release `*.sha256`/checksums sidecar files only | GitHub API `assets[].digest` (`sha256:<hex>`) on newer releases | 2025+ (assets uploaded after GitHub added digests) | 153 of 171 live assets expose it; older releases (gron, jless) do not |
| `# Verified` free text | structured `verified` date key | this phase (D-02) | parser-visible, lint-able |
| opaque method params | closed `METHOD_PARAMS` | this phase (D-01) | typos and leaked keys fail at load |
| `curl \| tar` shell pipeline | staged fetch/verify/smoke/swap | this phase | enables digest check and safe fall-through |

**Deprecated/outdated:** the `managed-download` owner probe (probes a non-existent `tools-installer-managed-download` command); the `drawio-cli` row.

## Runtime State Inventory

(Applies to the `managed-download` and `drawio-cli` removal parts of the phase.)

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Version cache `versions.json` may contain a `drawio-cli` key. `settings.Settings` persists only `link_mode` (D-13, resolved in discuss). `load_version_cache` ignores keys that are not in the registry catalog (D-13 cites `version_cache.py:176-190`) | None for data; add the regression test that a stale id in the cache does not raise |
| Live service config | None - verified: no external service references these ids (grep of `installer/`, `setup.py`, `tests/`, repo root) | None |
| OS-registered state | None - verified: no launchd/systemd/Task Scheduler units embed `drawio-cli` or `managed-download` | None |
| Secrets/env vars | None - neither string is an env or secret name (grep) | None |
| Build artifacts / installed packages | Existing installs of drawio via the old `drawio-cli` row own `~/.local/bin/drawio` and `~/.local/opt/drawio/`; those artifacts are identical to what `drawio-desktop` installs and must keep showing under `drawio-desktop` | Test: `is_installed(drawio-desktop)` true with the link present; uninstall naming unchanged (`link_name`) |

Code-edit vs data-migration: all of this is code/data edits in the repo; there is no data migration.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (via uv) | all | yes | 3.12.12 managed (system python3 3.14.7 present; project `>=3.11`) | - |
| uv | launch/test/make | yes | 0.11.28 | - |
| `gh` CLI, authenticated | verify-registry issue upsert, live probes | yes (`gh auth status` ok; 5000/h core limit, ~4.8k remaining) | 2.x | unauthenticated 60/h -> "inconclusive" |
| Network to api.github.com, download hosts | verify-registry, bump run | yes | - | none; offline tests use canned JSON |
| podman | `make e2e` | yes | 5.8.7 | docker via `scripts/detect-container-runtime.sh` |
| curl, tar, unzip | existing install flows | yes | - | - |
| pi executor (router-env/my-coding) | cross-AI execution | probed OK in RUN-LEDGER Step 0 | - | gsd-executor |
| macOS host | macOS fixes | no | - | CI macOS runner + fixtures only (SPEC constraint) |

**Missing with no fallback:** none. **Missing with fallback:** macOS behavior (cli_name link, stub rule, gh zip layout) is verified through fixtures and the CI macOS job, not live.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8 + pytest-xdist + pytest-cov + pytest-asyncio (`asyncio_mode = "auto"`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`, `fail_under = 90`) |
| Quick run command | `uv run pytest tests/<file>.py -q` (single file, serial) |
| Full suite command | `make validate && make test` (`uv run pytest -n auto --cov`, workers capped by `tests/conftest.py`) |
| Baseline (Phase 17 close) | 3572 passed, 4 skipped, coverage ~96% (17-13-SUMMARY) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | `formula` on a github_release method fails with tool id + key; kind-only `skill_pack`/`host_setup`-style method loads; every shipped key accepted | unit | `uv run pytest tests/test_model.py -q -k "unknown_key or method_params"` | rewrite `test_non_node_method_leaves_new_keys_untouched`; new tests: Wave 0 |
| REG-01 | `cli_name` names the macOS CLI link; uninstall uses the same name | unit | `uv run pytest tests/test_apps.py tests/test_uninstall.py -q -k cli_name` | new tests |
| REG-02 | missing / string / datetime / future `verified` rejected with tool id; shipped registry loads; `verified` on a method table rejected | unit | `uv run pytest tests/test_model.py tests/test_registry.py -q -k verified` | Wave 0 |
| REG-03 | pre-fix difftastic template fixture -> drift "renamed asset"; missing member; checksum drift; newer stable; not-checkable list | unit (canned release JSON, fake fetch/HEAD, in-memory tar) | `uv run pytest tests/test_verify_registry.py -q` | Wave 0 |
| REG-03 | second drift run edits the existing open issue; network-failure fixture -> INCONCLUSIVE with zero `gh` issue calls; working tree unchanged | unit (fake output runner records argv) | same file | Wave 0 |
| REG-03 | workflow only `schedule`+`workflow_dispatch`, `permissions` pinned, no push step, absent from `ci.yml` | unit (yaml) | `uv run pytest tests/test_verify_registry_workflow.py -q` | Wave 0 |
| REG-04 | digest match installs; mismatch -> `CHECKSUM_MISMATCH` and nothing linked; no digest -> installs with `verified=False` and a reason; pinned checksum wins over digest; update path verifies digest too | unit | `uv run pytest tests/test_download.py tests/test_engine.py tests/test_versions.py -q -k "digest or release"` | Wave 0 |
| REG-04 | "unverified (reason)" rendered | unit | `uv run pytest tests/test_render.py -q -k verification` | extend |
| REG-05 | fake binary exits 127 -> falls to next method; single failing method leaves no `~/.local/bin/<bin>`; loader-error stderr (exit 1) fails; non-0/1 other exit passes; timeout passes; existing good link untouched on failure | unit (real tiny shell scripts under `tmp_path`) | `uv run pytest tests/test_executors.py tests/test_download.py tests/test_apps.py tests/test_engine.py -q -k smoke` | Wave 0 |
| REG-06 | `--no-dev --isolated` on exactly the launchers (`setup run doctor fix uninstall guard unguard`) and `install.sh`; absent on `validate`/`test`; e2e harness matches | unit (text parse) | `uv run pytest tests/test_makefile.py tests/test_install_sh.py -q` | Wave 0 |
| REG-06 | ruff resolves its real owner under `make setup` in a container | e2e / backstop | `make e2e` (~33 min, podman) | backstop |
| REG-07 | java stub only -> not installed with reason; `java_home` ok -> installed; same for git/CLT; non-macOS `/usr/bin/git` unaffected | unit | `uv run pytest tests/test_status.py -q -k stub` | Wave 0 |
| REG-08 | parametrized table: `-1`, `--2`, `-v1.2.3` -> None; `jq-1.8.1` ok; lazygit `version=0.44.1,` -> `0.44.1`; procs quoted -> unquoted | unit | `uv run pytest tests/test_versions.py -q -k "fabricat or observed"` | Wave 0 |
| REG-09 | each applied data fix has an assertion in `tests/test_registry.py`; `managed-download` absent | unit + grep gate | `uv run pytest tests/test_registry.py tests/test_install_ownership.py -q` and `! rg -n "managed-download" installer/` | Wave 0 |
| REG-10 | no `drawio-cli`; `drawio-desktop` audience `both`; stale `drawio-cli` cache key ignored | unit | `uv run pytest tests/test_registry.py tests/test_version_cache.py -q -k drawio` | Wave 0 |
| R11 | no literal version in a pinned URL; loader requires `version`+`sha256` when URL has `{ver}`; bump writer changes only intended lines and refuses unintended diffs; `verified` written only for passing entries | unit | `uv run pytest tests/test_model.py tests/test_verify_registry.py tests/test_registry.py -q -k "pin or bump"` | Wave 0 |

### Sampling Rate
- **Per task commit:** the single touched test file(s) `uv run pytest tests/<file>.py -q`, plus `uv run ruff check installer tests && uv run pyright` for the touched files.
- **Per wave merge:** `make validate && make test`.
- **Phase gate:** `make validate && make test` green on the committed tree, `! rg -n "managed-download" installer/`, `git diff --quiet -- pyproject.toml uv.lock`, one `make e2e` run after the install-pipeline plan lands (smoke can change container outcomes), and a recorded `make verify-registry` live run with the bump evidence.

### Wave 0 Gaps
- [ ] `tests/test_verify_registry.py` - REG-03, R11 (canned release JSON dicts defined inline; no `tests/fixtures/` dir exists)
- [ ] `tests/test_makefile.py` - REG-06 (no Makefile test exists)
- [ ] `tests/test_verify_registry_workflow.py` - REG-03 prohibitions
- [ ] shared executable fake-member fixture in `tests/test_download.py::fixture_runner` - REG-04/05
- [ ] `verified` key added to the 30+1 inline `[[tool]]` fixtures (helper in `tests/test_model.py::_write`/`_node_registry`) - REG-02
- [ ] No framework install needed.

*Backstops (cannot be unit-tested): macOS runtime behavior (CI macOS job + fixtures), the container `make setup` ruff-owner check, the first real weekly-workflow run (`workflow_dispatch` after merge), the live bump run.*

## Security Domain

`security_enforcement` is enabled (absent = enabled); `security_asvs_level` 1, `security_block_on` high.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | - |
| V3 Session Management | no | - |
| V4 Access Control | yes (CI) | workflow `permissions: contents: read, issues: write` only; no write token for contents |
| V5 Input Validation | yes | closed `METHOD_PARAMS`; `verified`/`version`/`sha256` shape checks; smoke argv items validated with the `_SCRIPT_ARG_RE` pattern and `argv[0]` is always the freshly installed path, never registry-supplied; URLs from the registry are `shlex.quote`d or passed as argv, never interpolated |
| V6 Cryptography | yes | sha256 via `hashlib`; never hand-rolled |
| V10/V12 Integrity & files | yes | verify (mismatch aborts) before smoke before link; archive listing only, never extract in verify-registry (no tar/zip traversal exposure); staged `.new` sibling + atomic swap |
| V14 Config/CI | yes | pinned action major versions, `GH_TOKEN` only via `github.token`, no secrets echoed |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered/swapped release asset after upload | Tampering | digest/checksum compare, `ChecksumMismatch` halts the ladder; nothing linked |
| Digest and asset from different "latest" snapshots | Tampering/Repudiation | single `/releases/latest` fetch (D-05) |
| Executing an unverified binary in smoke | Elevation | smoke only after verification; unverified (no digest) installs are flagged and the user is already installing that binary |
| Registry supplies an arbitrary smoke command | Elevation | key is an argv tail for the installed binary only; closed regex; never a command |
| Malicious asset name/markdown in the drift issue | Spoofing/Tampering | code-spanned values; body from a temp file via `--body-file` |
| Token in logs/issue body | Information disclosure | never print env or argv containing a token; canon referral to `/gsd-secure-phase` (SPEC) |
| Rate-limit exhaustion turned into a false "no drift" | Repudiation | INCONCLUSIVE state, distinct non-zero exit, no issue, never "ok" |
| Writer corrupts the registry | Tampering | tomllib semantic guard aborts on any unintended diff; `--write` is an explicit maintainer action, not part of the weekly job |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Undated tools should be seeded with `verified = 2026-10-13` (the audit date) | Seeding | Dates would imply verification the tool did not do for non-checkable entries; user may want a different rule |
| A2 | The "last verified digest" state lives in a JSON file kept with `actions/cache` (local default under the XDG cache dir), not in the repo | verify-registry design / Open Q3 | If the user wants repo-committed state, "job never modifies the repo" (SPEC) would be violated |
| A3 | Inconclusive exits non-zero (e.g. 2) and the job is not marked green; drift exits 1 | verify-registry design | A noisy weekly red run on API rate limits; alternative is exit 0 with a warning annotation |
| A4 | GUI/Electron CLIs (`drawio`, `jetbrains-toolbox`) tolerate `--version` under a 5 s timeout; AppImage without FUSE exits non-zero without matching 126/127/GLIBC | Pitfall 6 | Smoke could launch GUIs for desktop users or misjudge AppImages; `make e2e` and a per-entry smoke argv are the mitigation |
| A5 | `--isolated` is acceptable on top of D-11's `--no-dev` | Pitfall 1 / Open Q1 | If the user insists on literal `--no-dev`, REG-06/SC4 only holds for fresh clones and the container harness |
| A6 | Manager-kind smoke is skipped when `shutil.which(tool.cmd)` does not resolve | Pitfall 8 | A broken install of a tool with an unresolvable cmd would not fall through |
| A7 | GitHub rate-limit responses are HTTP 403/429 and surface as `urllib.error.HTTPError` | Pitfall 5 | Misclassifying a rate limit as drift would open a false issue |
| A8 | Future-date tolerance of +1 day is acceptable | Pitfall 7 | A strict rule could reject legitimate CI-written dates in some timezones |
| A9 | Ubuntu has a `glab` apt package (Debian trixie does, verified) | Fix table E10 | An apt fall-through attempt fails on Ubuntu and the ladder moves on (non-fatal) |
| A10 | Loader-error substrings beyond `GLIBC_` (`error while loading shared libraries`, `Exec format error`, `cannot execute binary file`, `Library not loaded`) are worth scanning | smoke | Missing patterns let a broken binary link; extra patterns are low risk |
| A11 | Storing only the digests for the assets this platform's methods render (not the whole release) is acceptable for the D-05 version-cache requirement | Open Q9 | Phase 19 may need other-arch digests; storing everything costs cache size |
| A12 | kitty (E8) and wezterm macOS (E9) fixes cannot be applied or verified without macOS evidence | fix table | Skipping leaves two audit items "not applied" |

## Open Questions

1. **`--no-dev` is not enough (REG-06).**
   - What we know: reproduced; `--isolated --no-dev` works, is fast and non-destructive.
   - What's unclear: whether the user accepts adding `--isolated` to the locked D-11 form (or prefers `--exact`, or a startup PATH sanitizer in `installer/locations.py` as audit D C1 itself suggests).
   - Recommendation: use `uv run --no-dev --isolated` everywhere D-11 lists, update the Makefile test to assert both, align the container harness. Confirm with the user; fallback is the literal `--no-dev` plus `uv sync --no-dev` in the harness, accepting that dev-synced developers still see ruff shadowed.

2. **Seed date for ~62 undated entries** (Assumption A1). Recommendation `2026-10-13`; confirm.

3. **Where "last verified digest" lives.** Recommendation: `--state PATH` JSON `{url: digest-or-etag}`, `actions/cache` in the workflow, default `~/.cache/tools-installer/verify-registry.json`; first run downloads everything once. For assets with no digest (gron, jless, vscode/jetbrains "latest"), key on `ETag`/`Last-Modified`/`Content-Length` from HEAD.

4. **Exit codes and workflow behavior for INCONCLUSIVE** (A3). Recommendation: 0 ok, 1 drift (opens/updates the issue only with `--issue`), 2 inconclusive (no issue call).

5. **Optional sub-bullets of the audit fixes** (C7, D1/D2/D7 musl, E8, E9, F6). Recommendation per the table; every skipped optional is recorded in a fix ledger with its reason so "all 35 applied" is auditable.

6. **`parse_version('a-1')`.** Audit B lists it as fabricated but it has the same shape as legitimate `jq-1.8.1`. Decide the expected value in the fixture table (recommend: keep parsing names that start with a letter; `-1`, `--2`, `-v1.2.3` become `None`).

7. **Smoke scope for GUI app CLIs, AppImages and manager kinds** (A4, A6). Recommendation: a per-method optional argv key (closed list of strings validated like script `args`; name is discretion, e.g. `smoke_argv`, distinct from the existing `smoke` name key at `model.py:13`), default `--version`; timeout = pass; manager kinds only when `which` resolves.

8. **SC3 literal "50 -> 0".** Impossible for gron/jless (no digest published); the test must assert "every method whose rendered assets expose a digest is verifiable" and list the 4 residual unverified methods by id.

9. **D-05 "version refresh stores `Release.digests`".** This changes `VersionCacheEntry`/`_entry_from_raw` (tolerate absent or malformed `digests` in old caches) and `version_status.resolve_github_release_status` (currently takes `resolve_tag`). Storing every asset digest for ~49 repos is the largest option; recommendation is to store only the digests for assets the registry renders for the current platform, as a separate, last, independently revertible task of the verification-pipeline plan.

10. **Bump run mechanics.** The bump (`--write`) is a networked, date-dependent maintainer action executed once by the plan executor (pi) with `gh` auth; record its output in the SUMMARY. Tests must not depend on it. Entries whose asset was renamed keep the old pin and are reported (SPEC R11).

## Suggested plan decomposition (for the planner; adjust freely)

| Plan | Scope | Files (conflict set) | Depends on |
|------|-------|----------------------|-----------|
| 18-01 | `METHOD_PARAMS` (incl. `version`/`sha256`), `verified` loader rule + seeding of all 90 keys + fixture `verified` helper, pinned-kind `{ver}` rule, `managed-download` removal, `drawio-cli` removal + test pin updates, architecture/SKILL doc paragraph | model.py, registry.toml (seed + drawio), install_ownership.py, tests/test_model.py, test_registry.py, test_install_ownership.py, test_skill_lifecycle.py, .claude docs | - |
| 18-02a | `parse_version` fix + fixtures | versions.py, test_versions.py | - |
| 18-02b | macOS stub rule + reason | status.py, test_status.py | - |
| 18-02c | `cli_name` in `cli_spec` | apps.py, test_apps.py, test_uninstall.py | - |
| 18-02d | launch flags (Makefile, install.sh, e2e harness, README), `tests/test_makefile.py`, `test_install_sh.py` | Makefile, install.sh, scripts/container-e2e-verify.sh | - |
| 18-03 | the 35 data fixes (ledger + per-fix tests) | registry.toml, tests/test_registry.py | 18-01 |
| 18-04 | `Release`/digest, staged install, `smoke_binary`, `unverified_reason`, manager-kind smoke, (last task) digest cache | versions.py, download.py, apps.py, executors.py, engine.py, render.py, version_cache.py, version_status.py, tests | 18-01 (keys), 18-02a (versions.py), 18-02c (apps.py) |
| 18-05 | `verify_registry.py`, Makefile target, workflow, tests | new module + workflow + Makefile (after 18-02d) | 18-04 |
| 18-06 | pin conversion (`{ver}`, `version`, `sha256`) for drawio and sublime, the live bump run, final `verified` dates, README/docs | registry.toml | 18-03, 18-05 |

Waves: 18-01 and 18-02a-d in wave 1 (18-02d and 18-05 both touch the Makefile; keep them in different waves); 18-03 and 18-04 in wave 2; 18-05 wave 3; 18-06 wave 4. Registry-editing plans (18-01, 18-03, 18-06) must not run in the same wave.

## Sources

### Primary (HIGH confidence)
- In-repo source read this session: `installer/model.py`, `versions.py`, `download.py`, `apps.py`, `engine.py`, `executors.py`, `run.py`, `checksums.py`, `assets.py`, `atomic.py`, `status.py`, `install_ownership.py`, `version_cache.py`, `version_status.py`, `render.py`, `update.py`, `platform.py`, `Makefile`, `install.sh`, `pyproject.toml`, `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`, `tests/conftest.py`, `tests/test_download.py` (fixture runner), `tests/test_status.py`, `tests/test_model.py` (803-827), `tests/test_registry.py` (selected), `scripts/container-e2e-verify.sh`
- GitHub REST API live reads via `gh api repos/<r>/releases/latest` for all 89 github_release methods plus cli/cli, gitui-org/gitui, tealdeer-rs/tealdeer, dandavison/delta, sharkdp/hyperfine, jgraph/drawio-desktop (digest field, asset names, tags)
- `gh issue edit/list/create` and `gh label create` help output (flags used)
- Scratch-venv experiments for `uv run --no-dev`, `--exact`, `--isolated`
- `.planning/phases/18-*/18-CONTEXT.md`, `18-SPEC.md`; audits C/D/E/F "Registry fixes (data only)"; `.planning/phases/17-stop-the-bleeding/17-02/05/09/18/13-SUMMARY.md`; `.planning/RUN-LEDGER.md`

### Secondary (MEDIUM confidence)
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows - schedule semantics (default branch only, 60-day disable, UTC, start-of-hour delay) [CITED]
- Arch `extra/glab` JSON (https://archlinux.org/packages/extra/x86_64/glab/json/), Fedora package pages for `glab` and `docker-cli`, Debian sources API for `glab` (HTTP 200 responses read this session)
- Sublime `https://www.sublimetext.com/updates/4/stable_update_check` (latest_version 4215)

### Tertiary (LOW confidence - flagged [ASSUMED])
- GUI/AppImage behavior under `--version`; GitHub rate-limit status codes; Ubuntu `glab`; timezone tolerance (see Assumptions Log)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib and existing dev deps only; verified by reading the tree
- Architecture: HIGH for loader/versions/download/engine changes (code read end to end); MEDIUM for verify-registry state and exit-code design (decisions not in CONTEXT)
- Pitfalls: HIGH for items with reproduced evidence (1, 2, 3, 4, 10, 11, 12); MEDIUM/LOW for GUI/AppImage and rate-limit specifics

**Research date:** 2026-10-15
**Valid until:** ~2026-10-22 for the live API numbers (releases move weekly; re-run the digest probe before the bump); the code findings stay valid until the tree changes.

Skipped / not checked: no macOS evidence (cli_name link, stub rule, gh zip member layout, kitty/wezterm macOS), no container run of `make e2e` (33 min, left to the execution gate), Ubuntu `glab`, the real behavior of `drawio`/`jetbrains-toolbox` `--version`, and the full text of every audit sub-bullet beyond the "Registry fixes (data only)" sections. Risk to know: the biggest correctness risk is the install-path refactor (existing download/app tests assert shell-pipeline argv), not the new modules.
