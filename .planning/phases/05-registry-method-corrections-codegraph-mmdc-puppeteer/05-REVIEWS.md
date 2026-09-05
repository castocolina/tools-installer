---
phase: 5
reviewers: [opencode-sol]
reviewed_at: 2026-09-05T19:57:22Z
plans_reviewed: [05-01-PLAN.md, 05-02-PLAN.md, 05-03-PLAN.md, 05-04-PLAN.md]
models:
  opencode-sol: "openai/gpt-5.6-sol (reasoning=high)"
model_sources:
  opencode-sol: "pinned"
---

# Cross-AI Plan Review — Phase 5

> Reviewer-selection note: `.planning/config.json` sets
> `review.default_reviewers: ["opencode-plan-review"]`. That instance's model
> (`router-env/my-plan-review`) was hard-down for the whole of this run — the router at
> `http://llm.local:20128/v1` returned `Model claude/claude-opus-5 is unavailable` on every
> attempt (verified directly against `/v1/chat/completions`, three consecutive tries, plus one
> `opencode run` invocation). The review was therefore run with the project's OTHER configured
> reviewer instance, `opencode-sol` (`review.reviewer_instances.opencode-sol`, model
> `openai/gpt-5.6-sol`), rather than falling back to an unconfigured CLI. One reviewer ran, so
> the convergence loop's two-or-more-reviewer consensus gate does not engage this cycle.

## OpenCode Review (opencode-sol)

I’ll trace the named source paths and current APIs first, then evaluate cross-plan behavior, pnpm semantics, and security assumptions against the repository.
The current code confirms the proposed seams exist, but the review now hinges on two details the plans do not prove: whether pnpm’s grouped syntax and `--allow-build` work across the installer’s unpinned pnpm versions, and whether replay/status/uninstall semantics remain coherent. I’m checking those exact paths and the catalog’s current version constraints.
Two material gaps are now clear: the clean-install tracer does not cover upgrades from the already-shipped standalone `mmdc`, and the proposed method intentionally resolves on Linux arm64 even though its own research says the downloaded browser cannot run there. I’m doing one final consistency pass over pinned registry tests and replay contracts before writing the review.
## Summary

The overall direction is sound, especially the checksum-backed `codegraph` entry and keeping dependency ordering in `requires`. However, the plans are not execution-ready. The clean-install design does not repair existing standalone `mmdc` installations, knowingly advertises unsupported Linux configurations, and assumes pnpm/Node capabilities that the registry does not enforce. Security and replay semantics also need tightening.

## Strengths

- Plan 05-01 correctly modifies the single node execution seam. All node installs flow through `execute()` and `_node()` at `installer/executors.py:83-94` and `installer/executors.py:132-137`, so no parallel install path is missed.
- The dependency design preserves the existing architecture. `resolve_dependencies()` already creates a deps-first order through its DFS at `installer/deps.py:121-138`, while `run_installs()` propagates dependency failures at `installer/session.py:88-106`.
- Plan 05-02 fits the existing download architecture well. Asset templating happens in `installer/download.py:65-87`, checksum lookup in `installer/checksums.py:23-37`, and checksum mismatches halt by default in `installer/engine.py:89-102`.
- The proposed CodeGraph assets match the current `v1.6.0` GitHub release, including both architectures and `SHA256SUMS`.
- Plan 05-04 correctly recognizes that preview and execution must share `reinstall_argv()`. The current production closures are separate at `setup.py:260-270`, while both ultimately use the builder at `installer/pnpm_globals.py:191-249`.
- The sequential wave structure is justified because every plan runs repository-wide quality gates against a shared tree.

## Concerns

- **HIGH: Existing `mmdc` installations will not be migrated into the new group.** The shipped registry already installs `mmdc` standalone at `installer/registry.toml:1692-1704`. Both dependency resolution and installation treat a PATH-visible command as satisfied: `resolve_dependencies()` excludes installed tools at `installer/deps.py:109-113`, and `install_tool()` immediately returns `ALREADY_INSTALLED` at `installer/engine.py:80-81`. Therefore an existing standalone `mmdc` can cause only `puppeteer` to be installed independently, leaving the required grouped `mmdc,puppeteer` invocation unexecuted. The clean-container tracer does not cover this brownfield path.

- **HIGH: The plans knowingly expose methods on platforms where they cannot produce a working tool.** An unscoped node method applies to every OS and architecture at `installer/resolve.py:32-39`. Plan 05-03 nevertheless requires Puppeteer to resolve on Linux arm64 despite documenting that Puppeteer's browser is unavailable there. Linux x64 also needs shared libraries that the registry will not install. The tracer hides this gap by manually installing Debian `chromium`; that is not the sequence the catalog will perform. Because `install_tool()` treats a successful pnpm exit as installation success at `installer/engine.py:89-94`, users can receive a successful outcome for a tool that cannot render.

- **HIGH: Required pnpm and Node versions are not modeled or checked.** Comma-separated global install groups are a pnpm v11 feature, while `--allow-build` requires pnpm 10.4 or newer. The current executor checks only whether pnpm exists at `installer/executors.py:88-94`. The pnpm registry entry is unpinned and has no Node dependency at `installer/registry.toml:1447-1470`. Meanwhile Puppeteer 25 requires Node `>=22.12.0`, but the tracer uses `node:24`, masking the bare-machine case. A standalone pnpm executable does not prove a compatible `node` is available for installed Node CLIs.

- **HIGH: `allow_build` is described as invocation-scoped, but pnpm persists the trust decision.** The proposed validation around the current node branch at `installer/model.py:153-166` limits the package name, but official pnpm behavior also writes that package into its global build-allowance configuration. This means future Puppeteer versions can run their postinstall automatically, not merely the current invocation. Combined with unversioned `npm_pkg` values and `install_tool()` accepting exit zero at `installer/engine.py:89-94`, the threat model materially understates the lasting trust granted.

- **MEDIUM: The normal clean-install sequence installs Puppeteer twice and does not inspect the resulting global-group state.** The resolver emits every runnable tool independently at `installer/deps.py:113-138`, and `run_installs()` invokes each one at `installer/session.py:90-106`. Consequently Puppeteer is first installed standalone, then included again in the `mmdc,puppeteer` group. The tracer proves rendering but does not inspect whether pnpm retained both groups, which group owns the `puppeteer` shim, or what removing/updating either package does.

- **MEDIUM: Replay reconstructs only registry-known groups and discards versions.** `parse_global_packages()` currently flattens pnpm JSON to bare package names at `installer/pnpm_globals.py:110-132`. Plan 05-04 therefore cannot preserve versions or hand-created groups for packages absent from the registry. Such packages are replayed as separate, latest-version installs through the builder currently at `installer/pnpm_globals.py:191-204`, potentially breaking other peer-dependent global groups while repairing `mmdc`.

- **MEDIUM: Uninstall behavior for grouped packages is unresolved.** The uninstall planner only recognizes app and download artifacts at `installer/uninstall.py:55-96`; node tools are classified as externally managed and non-selectable at `installer/uninstall.py:200-203`. pnpm documents that removing either member of a comma-group removes the whole group. The plans neither surface this coupling nor test manual removal and subsequent audit/recovery behavior.

- **MEDIUM: Plans 05-02 and 05-03 omit a mandatory pinned-count update.** `test_registry_tier_distribution_is_pinned()` explicitly requires every entry-adding phase to update counts in the same commit at `tests/test_registry.py:436-444`. Adding CodeGraph changes AI from 9 to 10, and adding Puppeteer changes user from 35 to 36. Neither task includes these updates, so the required `tests/test_registry.py` and full-suite gates will fail.

- **MEDIUM: The package-legitimacy check is weaker than its description.** It accepts `want in repository.url`, rather than normalizing and exactly matching the expected GitHub owner/repository. More importantly, repository URL, age, and version count do not authenticate the current tarball. Since node execution currently delegates directly to pnpm at `installer/executors.py:83-94`, the plan should record the exact version and npm integrity/provenance associated with the postinstall it approves.

- **LOW: The proposed `_opt_pkg_list()` is not actually safe for directly constructed malformed methods.** `Method.params` accepts arbitrary objects at `installer/model.py:67-71`, and `execute()` accepts a directly constructed `Method` at `installer/executors.py:132-137`. Casting and filtering without first checking `isinstance(raw, list)` makes a bare string iterable as individual package-name characters. This contradicts the plan’s claim that the helper also handles directly constructed methods correctly.

## Suggestions

- Add an explicit migration test and mechanism for an already-installed standalone `mmdc`. Detect actual pnpm group membership rather than relying only on `shutil.which()`, then force one grouped reinstall when reconciliation is needed.
- Require pnpm v11 or newer before using `co_install`, and verify a compatible Node runtime before installing or reporting Puppeteer/mmdc as usable.
- Do not expose Puppeteer on Linux arm64 until a working distro-browser method is implemented. For Linux x64, either automate verified runtime prerequisites or report the method unavailable rather than successful-but-broken.
- Extend the tracer to inspect `pnpm list -g --json`, global group directories, shim ownership, reinstall idempotency, and removal behavior after both invocations.
- Document `--allow-build` as persistent package-level trust. Pin or constrain Puppeteer/mmdc versions and bind the legitimacy evidence to those exact versions and integrity values.
- Preserve actual pnpm group and version information during audit/replay where available. At minimum, explicitly warn that unknown groups cannot be faithfully reconstructed.
- Add the tier-count updates to 05-02 and 05-03.
- Make `_opt_pkg_list()` reject malformed direct values with `ExecutorError` instead of filtering them.
- Normalize repository URLs and require an exact owner/repository match in the legitimacy gate.

## Risk Assessment

**HIGH.** The design is strong for a fresh, supported pnpm v11+/Node 24 environment, but the project is brownfield and cross-platform. Existing installations, Linux runtime constraints, unsupported Linux arm64 behavior, and unmodeled runtime versions can all leave `mmdc` visibly installed but unusable. The persistent postinstall authorization and lossy replay behavior also need explicit security and lifecycle decisions before implementation.

---

## Source-Grounding Pass

Independent verification of the reviewer's citations and of the plans' own factual claims,
run against this repository and against live upstream sources on 2026-09-05.

### Reviewer claims CONFIRMED against source

| Claim | Evidence |
|-------|----------|
| Existing `mmdc` short-circuits the new group | `installer/engine.py:80-81` returns `ALREADY_INSTALLED` before `resolve_methods`; `installer/deps.py:109-113` excludes installed tools from the order |
| An unscoped node method resolves on every OS/arch | `installer/resolve.py:32-39` — `_applies` returns `True` for `kind="node"` with no `os`/`arch` gate |
| `--allow-build` grants PERSISTENT trust, not per-invocation | pnpm docs, `pnpm.io/cli/add`, verbatim: "This will run `esbuild`'s postinstall script and **also add it to the `allowBuilds` field of `pnpm-workspace.yaml`. So, `esbuild` will always be allowed to run its scripts in the future.**" Added in v10.4.0 |
| Comma groups are a pnpm **v11** redesign | pnpm docs, `pnpm.io/global-packages`: "In pnpm v11, global package management was redesigned…"; the comma form and its peer-resolution semantics are documented there verbatim, exactly as 05-RESEARCH.md cites |
| pnpm registry entry is unpinned and declares no node dependency | `installer/registry.toml:1447-1470` — three methods, no version, no `requires` |
| The executor only checks that pnpm EXISTS | `installer/executors.py:88-93` |
| Tier-count tripwire not updated by 05-02/05-03 | `tests/test_registry.py:436-444` pins `{system: 22, ai: 9, user: 35}`. 05-02 adds an `ai` entry (→10), 05-03 adds a `user` entry (→36). Neither plan's `<action>` or `<acceptance_criteria>` updates the counts, yet both assert `uv run pytest tests/test_registry.py -x -q` exits 0 |
| Node tools are not uninstallable here; group removal is coupled | `installer/uninstall.py:200-203` classifies them `MANAGED`; `pnpm.io/global-packages`: "Removing either with `pnpm remove -g` removes the whole group" |
| `_opt_pkg_list` filtering is unsafe for a bare string | `installer/model.py:67-71` — `Method.params: dict[str, object]`; a bare `"abc"` iterates to `'a','b','c'`, all `str`, so a filter-without-`isinstance(raw, list)` yields three package names |
| Replay flattens to bare names, losing versions/groups | `installer/pnpm_globals.py:110-132` (`parse_global_packages`) |

### Plan claims CONFIRMED

- `codegraph` `v1.6.0` publishes `codegraph-{darwin,linux}-{arm64,x64}.tar.gz` **and** `SHA256SUMS` — verified live via `api.github.com/repos/colbymchenry/codegraph/releases/latest`. `codegraph` occurs 0 times in `installer/registry.toml` today, as 05-02 states.
- `{arch.x64}` → `x64`/`arm64` (`installer/assets.py:16-23`); `checksum = "SHA256SUMS"` contains no `{asset}` so it renders verbatim (`installer/download.py:78-81`); `expected_sha256` parses the two-space `<hash>  <name>` form (`installer/checksums.py:31-34`); `_place_verified` untars with `--strip-components` into `opt_dir(link.name)` (`installer/download.py:190-207`). Every symbol 05-02's `key_links` names is real.
- 05-03 Task 1's legitimacy-gate shell command was executed verbatim: it prints both lines and `LEGITIMACY_OK`, exits 0, and is genuinely failable (`set -eu` + per-iteration `|| exit 1`, python `sys.exit(1)` as pipeline tail). Observed: puppeteer repo `git+https://github.com/puppeteer/puppeteer.git#main`, created 2013-03-23, 1010 versions, latest 25.10.0; `@mermaid-js/mermaid-cli` repo `git+ssh://git@github.com/mermaid-js/mermaid-cli.git`, created 2020-03-01, 82 versions, latest 11.17.0.
- `puppeteer@25.10.0` declares `postinstall: "node install.mjs"` and `engines.node >= 22.12.0`; `@mermaid-js/mermaid-cli@11.17.0` declares NO install/postinstall script and `peerDependencies: {puppeteer: "^23 || ^24 || ^25"}`. All three plan claims hold.
- Every grep baseline the plans assert is exact: `SHA256SUMS`=2, `arm64`=3, `Linux arm64`=0, `PUPPETEER_EXECUTABLE_PATH`=0, `install.mjs`=0, `1122`=0, `peerDependency`=0, `codegraph`=0, `mmdc` rows in `PROJECT.md`=0.
- `--allow-build` is a real `pnpm add` flag on the installed pnpm (11.9.0).
- No hallucinated Python symbols found. `_perform`, `execute`, `_node`, `real_pnpm`, `load_tools`, `resolve_methods`, `resolve_dependencies`, `requires_integrity_errors`, `missing_requires`, `is_installed`, `render_dependency_notice`, `unstaged_recommends`, `reinstall_argv`, `reinstall_preview`, `reinstall_node_globals`, `node_globals`, `_place_verified`, `arch_tokens`, `expected_sha256`, `_parse_id_list`, `_plant_executable`, `MACOS_ONLY`, `test_volta_entry_records_the_npm_postinstall_finding`, `test_gh_uses_nested_member_on_linux_and_brew_only_on_macos`, `test_shipped_node_tools_require_pnpm`, `test_registry_includes_requested_installable_entries` — all exist with the shapes the plans assume. `Platform(os=, arch=, immutable=, has_brew=)` and `resolve_dependencies(..., available=, is_installed=)` match the acceptance-criteria call sites exactly.

### Additional findings from this pass

- **HIGH — `npm_pkg = "puppeteer"` is unpinned, and mmdc's peer range is already at its ceiling.**
  `mmdc` requires `puppeteer ^23 || ^24 || ^25`; npm's current `latest` is **25.10.0**. `_node`
  builds `pnpm add -g '@mermaid-js/mermaid-cli,puppeteer'` with no version, so the day puppeteer
  26 ships, the co-install group — the phase's entire mechanism — resolves an out-of-range peer.
  pnpm's default `strict-peer-dependencies=false` makes that a warning, so the failure is silent
  and lands at runtime. Nothing in the four plans pins, ranges, or tests this, and the Tier-3
  tracer proves only today's resolution. Compounded by the confirmed persistence of
  `--allow-build`: it is the *unpinned future version's* postinstall that is pre-authorised.
- **MEDIUM — `REQUIREMENTS.md` was never amended to match the `chrome-headless-shell` decision.**
  `REQ-puppeteer-catalog-entries` still reads "`puppeteer` **and** `chrome-headless-shell` become
  their own catalog entries". ROADMAP SC#3 was formally amended for this; `REQUIREMENTS.md` was
  not, and 05-03 does not list it in `files_modified` — yet 05-03 Task 2 adds a test asserting no
  such entry can exist. A verifier reading the requirement text will register the REQ as unmet.
- **MEDIUM — 05-03's stated evidence for `cmd = "puppeteer"` is factually wrong.** The plan says
  the package "declares `\"bin\": \"./lib/puppeteer/node/cli.js\"` as a bare string … and a string
  `bin` is linked under the package's own name". Live registry metadata shows
  `bin: {"puppeteer": "lib/puppeteer/node/cli.js"}` — an **object**, not a string. The conclusion
  (`cmd = "puppeteer"` is correct) survives, because the object key is literally `puppeteer`, but
  the plan instructs this rationale to be transcribed verbatim into `05-03-SUMMARY.md`, so a false
  claim would be committed as verified evidence.
- **MEDIUM — 05-04 Task 2's `PLAN_BASE` criterion reads a path that does not exist.** It runs
  `grep -oE '[0-9a-f]{40}' 05-04-SUMMARY.md`, but the summary is written to
  `.planning/phases/05-registry-method-corrections-codegraph-mmdc-puppeteer/05-04-SUMMARY.md`.
  From the repo root the grep finds no file, `PLAN_BASE` is empty, and the deliberate
  `test -n "$PLAN_BASE"` guard fails the criterion for the wrong reason.
- **MEDIUM — 05-04 Task 2 re-introduces the working-tree check it just argued against.**
  The plan explains at length why an unscoped `git diff` on the working tree is unreliable
  against pre-existing dirt, then adds `git status --porcelain -- installer/wizard_app.py`
  "produces no output". That file is modified in the working tree on the current branch, so the
  criterion is failable on dirt this plan did not create.
- **MEDIUM — 05-04's `reinstall_node_globals` return contract becomes false.** The function
  returns `tuple(argv[3:])` (`installer/pnpm_globals.py:227`). Once `--allow-build=<pkg>` elements
  are prepended, that slice returns flags as if they were package specs, contradicting the plan's
  own `<behavior>` line "returns the package specs it actually invoked". No task changes the slice.
  (Impact is contained: `setup.py:267-270`'s value is discarded by
  `wizard_app.py:_reinstall_globals_worker`.)
- **MEDIUM — `node_install_policy`'s `allow_build` de-duplication is unspecified.** Both the
  `puppeteer` entry and the `mmdc` entry will declare `allow_build = ["puppeteer"]`, so a literal
  concatenation yields `('puppeteer', 'puppeteer')` and two identical flags in the replay argv,
  while 05-04's own acceptance criterion demands `p.allow_build == ('puppeteer',)`. The
  `<action>` text specifies `dict.fromkeys` de-duplication only for group members.
- **LOW — 05-02 cites the wrong file for the `gh` precedent.** `read_first` names
  "`installer/registry.toml` lines 288-300 (the `gh` entry … `member = "bin/gh"`)". The `gh` entry
  is at `installer/registry.toml:400-417` (`member = "bin/gh"` at 416); lines 288-300 are the
  `delta`/`eza` region. 288 is the line number of `test_gh_uses_nested_member_on_linux_and_brew_only_on_macos`
  in `tests/test_registry.py` — the two citations were crossed.
- **LOW — scope-boundary tension with `05-CONTEXT.md`.** The context's `<specifics>` states Phase 5
  is "strictly a method correction … no new tools, no new mechanisms." These plans add a new
  executor param pair (`co_install`/`allow_build`), a new load-time validator, and a new
  `NodeInstallPolicy` layer in `pnpm_globals`. The work is necessary for SC#3 and is well argued,
  but it is a mechanism, and the deviation is not recorded the way ROADMAP SC#3's amendment was.
  The same applies to D-03's literal "platform-conditional methods (macOS vs Linux/Bazzite)",
  which 05-03 deliberately resolves as a single unscoped method.

## Consensus Summary

One reviewer produced a section this cycle (`opencode-sol`), so there is no cross-reviewer
consensus to compute; the source-grounding pass above stands in as independent corroboration.
The reviewer's section carries no evidence-quality discount marker — it cites `file:line`
evidence throughout, and every citation checked resolved to real code.

### Agreed Strengths

- The single node execution seam (`installer/executors.py::_node`) is the right and only place
  to change the argv; no parallel install path is missed.
- `installer/deps.py` stays untouched — install order remains `requires`-only, and `co_install`
  is explicitly documented as not an ordering mechanism.
- 05-02's `codegraph` entry is checksum-verified, live-verified against `v1.6.0`, and fits the
  existing `github_release` download path exactly.
- The wave sequencing (1→2→3→4) is correctly justified by the shared-tree repo-wide quality gate,
  not by file overlap.
- 05-03 Task 1's legitimacy gate really is failable, and really does bind the expected repository
  per package — the two defects the previous internal round fixed are genuinely fixed.

### Agreed Concerns

Corroborated by the reviewer AND the source-grounding pass:

1. `--allow-build` is persistent package-level trust, not invocation-scoped — contradicting the
   threat registers in 05-01 (T-05-01), 05-03 (T-05-09) and 05-04 (T-05-14).
2. Required pnpm (v11 for comma groups, ≥10.4 for `--allow-build`) and Node (≥22.12.0 for
   puppeteer) versions are neither pinned nor checked anywhere in the catalog or the executor.
3. A brownfield machine with `mmdc` already installed never reaches the grouped invocation.
4. The `test_registry_tier_distribution_is_pinned` tripwire will fail both 05-02 and 05-03.
5. Version pinning / provenance is the real gap in the package-legitimacy story, not repository
   identity — and it is the one install path in this phase with no integrity verification, in
   contrast to `codegraph`'s checksummed download.

### Divergent Views

None — a single reviewer ran. The source-grounding pass agrees with every reviewer finding it
was able to check, and adds seven findings the reviewer did not raise (listed above).
