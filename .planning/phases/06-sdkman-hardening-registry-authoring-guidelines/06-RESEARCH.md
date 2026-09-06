# Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines - Research

**Researched:** 2026-09-05
**Domain:** Registry-driven installer hardening (SDKMAN install-method verification) + registry-authoring process documentation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Verification checklist recording mechanism:** A comment citing what was
checked (e.g. "verified via brew.sh formula page, 2026-09-04") is the recording
mechanism for the new per-tool, per-OS registry-authoring verification checklist —
not a stronger checked-in excerpt/snapshot of the verified source. Lower friction,
matches this project's existing convention of citing sources in comments; avoids
adding real file weight or staleness risk from snapshotting external content that
can change upstream.

**D-02 — Brew-preference guideline enforcement:** "Prefer brew over other userspace
package managers" (with SDKMAN's Java carve-out) is documented-only, pure
convention — no lint/test enforcement. Matches how this project already handles
the analogous SDKMAN carve-out (explained in prose, not lint-enforced); brew
availability differs per OS/tool, so an automated check would risk noisy false
positives.

### Claude's Discretion
- Exact placement of the verification-checklist and brew-preference documentation
  (a new section in `.claude/architecture.md`, a dedicated `CONTRIBUTING`-style
  doc, or inline in `installer/registry.toml`'s own header comment) — planner's
  call, informed by where this project already documents similar authoring
  conventions.
- Whether `java`'s SDKMAN candidate needs a pinned `version` to avoid an
  interactive prompt (ROADMAP SC#2) — a technical/research question to resolve
  via testing `sdk install java` non-interactively, not a user-preference gray
  area. **Resolved by this research — see "SC#2 resolution" below.**

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within Phase 6 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-sdkman-exclusivity | `java`/`gradle`/`maven`/`groovy`/`springbootcli` install exclusively through SDKMAN, never a native/brew fallback, with SDKMAN's own install correctly self-detected. Already implemented and shipped in commit `0e05f50` — treat as prior art requiring verification/hardening, not as sufficient as-is. `java`'s SDKMAN candidate may need a pinned `version` to avoid an interactive prompt — unverified end-to-end. | "Current SDKMAN Implementation State" + "SC#2 Resolution: `sdk install java` Non-Interactivity" sections below give the current-state code map, the existing (already-adequate) unit-test coverage, and the container-verified answer to the pinned-version question. |
| REQ-registry-authoring-verification-checklist | Establish a mandatory per-tool, per-OS verification step before any new registry entry ships — read the tool's actual install script/package metadata, confirmed independently per OS. Recording mechanism unresolved (resolved by CONTEXT D-01: comment citing what was checked). | "Registry-Authoring Precedent" section documents the exact comment-citation pattern this project already uses (mmdc/puppeteer entries) and recommends codifying it in `.claude/architecture.md`, which already carries per-phase authoring-convention additions. |
| REQ-brew-preference-guideline | "Prefer brew over other userspace package managers" becomes a documented (not code-enforced) registry-authoring guideline, with SDKMAN as the Java-toolchain's specific carve-out. | Same "Registry-Authoring Precedent" section — recommends stating this guideline in the same `.claude/architecture.md` location, alongside the verification checklist. |

</phase_requirements>

## Summary

The SDKMAN-exclusivity work (commit `0e05f50`) is in good shape: `java`,
`gradle`, `maven`, `groovy`, and `springbootcli` all install exclusively through
a dedicated `kind="sdkman"` method (`installer/registry.toml:1322-1386`), SDKMAN's
own non-executable `sdkman-init.sh` marker is detected via a new `detect_path`
fallback in `installer/status.py`, and Rule 7's "new kind ships with matching
tests across `test_model.py`/`test_executors.py`/`test_resolve.py`/
`test_registry.py`/`test_status.py`" is **already satisfied** — all five files
carry sdkman-specific tests today. What is genuinely missing, matching ROADMAP
SC#1/SC#2 exactly, is (a) any *real* (non-mocked) end-to-end verification of
`sdk install java`, and (b) a definitive answer to whether `java` needs a pinned
candidate version to avoid an interactive prompt.

This research resolves (b) conclusively via live Tier-3 container verification
(colima + docker, per `.planning/ONESHOT-RULES.md` Rule 14) plus direct
inspection of SDKMAN's own installed shell-script source: **no pinned version is
needed.** SDKMAN's `sdk install <candidate>` has exactly one interactive
prompt in its entire code path (`__sdk_install`, "Do you want X to be set as
default? (Y/n)"), and that prompt is gated on `sdkman_auto_answer != true AND
auto_answer_upgrade != true AND -n "$CURRENT"` (i.e. it only fires when a
*prior* default version already exists for that candidate and auto-answer is
off). This project's existing `sdkman` tool entry already bootstraps via
`https://get.sdkman.io?ci=true`, which persists `sdkman_auto_answer=true` to
`~/.sdkman/etc/config` — permanently disabling that one prompt path, on both
first installs and later re-installs, independent of whether a version is
pinned. Live container testing confirms `sdk install java` (no version given)
completes non-interactively with exit code 0 in both `sdkman_auto_answer=true`
and `sdkman_auto_answer=false` configurations, because a *first* install never
has a `$CURRENT` version to trigger the prompt at all.

**Primary recommendation:** Do not add a pinned `version` param to `java`'s
`kind="sdkman"` method — the existing `?ci=true` bootstrap already makes `sdk
install java` fully non-interactive. Close SC#1 by recording this Tier-3
container evidence (this research's commands/output, or a fresh repeat of them
during phase execution) as a `# Verified {date}: ...` comment directly above
`installer/registry.toml`'s `java` entry, mirroring the exact comment style
already used above the `mmdc`/`puppeteer` entries — this is also the natural
place to demonstrate the new REQ-registry-authoring-verification-checklist
convention in the same phase that documents it. Place both new
registry-authoring guidelines (verification checklist + brew-preference) as a
new section in `.claude/architecture.md`, following the existing pattern of
per-phase convention additions ("Tier is a browsing label" from Phase 1,
"Phase 3: install, uninstall, and tweak lifecycle" from Phase 3).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SDKMAN candidate install (`sdk install <candidate>`) | Installer (shell-out) | — | `installer/executors.py::_sdkman` builds a `bash -c` pipeline; no browser/server tier involved — this is a CLI-tooling installer, not a web app. |
| SDKMAN presence detection | Installer (`installer/status.py`) | — | `detect_path` fallback checks a filesystem marker; pure local-filesystem logic. |
| Registry-authoring guidelines (verification checklist, brew-preference) | Documentation (`.claude/architecture.md`) | Registry data (`installer/registry.toml` comments) | Convention lives in project docs read by every future contributor/agent; per-entry verification evidence lives as comments beside the entry it verifies (D-01). |
| Real e2e verification of `sdk install java` | Tier-3 container (colima + docker) | Phase verification artifact (not `make test`) | `testing.md` requires `make test` be "deterministic and offline" — a live network-dependent SDKMAN bootstrap cannot be a pytest test; it is Tier-3 evidence per ONESHOT-RULES Rule 14, recorded in the phase's verification report / registry comment, not in the automated suite. |

## Current SDKMAN Implementation State

### Registry entries (`installer/registry.toml`)

```toml
# installer/registry.toml:1297-1311
[[tool]]
id = "sdkman"
name = "SDKMAN"
category = "runtime"
cmd = "sdkman-init.sh"
priority = "P1"
audience = "both"
tier = "system"
desc = "User-space manager for Java and JVM tools; after sourcing sdkman-init.sh it exposes the sdk shell function."
[[tool.method]]
kind = "script"
url = "https://get.sdkman.io?ci=true"
shell = "bash"
bin_dir = "~/.sdkman/bin"
detect_path = "~/.sdkman/bin/sdkman-init.sh"

# installer/registry.toml:1313-1326 (java; groovy/springbootcli/gradle/maven follow the identical shape)
[[tool]]
id = "java"
...
requires = ["sdkman"]
[[tool.method]]
kind = "sdkman"
candidate = "java"
bin_dir = "~/.sdkman/candidates/java/current/bin"
```
[VERIFIED: installer/registry.toml:1297-1386 — read directly this session]

All five JVM tools (`java`, `groovy`, `springbootcli`, `gradle`, `maven`)
declare exactly one method, `kind="sdkman"`, with no native/brew fallback —
confirmed both by reading the registry directly and by
`tests/test_registry.py::test_java_tools_install_exclusively_through_sdkman`
(`tests/test_registry.py:122-140`), which asserts `[m.kind for m in
tool.methods] == ["sdkman"]` for all five ids.

### Executor (`installer/executors.py:456-469`)

```python
def _sdkman(method: Method, runner: Runner) -> None:
    # `sdk` is a shell function defined by sourcing sdkman-init.sh, not a PATH
    # binary — it must be sourced in the same shell invocation that calls it.
    # The sdkman tool's own bootstrap runs with `?ci=true`, which persists
    # `sdkman_auto_answer=true` in ~/.sdkman/etc/config, so a candidate install
    # here does not hang on an interactive version-choice prompt.
    candidate = require_str(method, "candidate")
    version = method.params.get("version")
    install = ["sdk", "install", candidate]
    if isinstance(version, str) and version:
        install.append(version)
    pipeline = f'{_path_prefix()}. "$HOME/.sdkman/bin/sdkman-init.sh" && {shlex.join(install)}'
    runner(["bash", "-c", pipeline])
```
[VERIFIED: installer/executors.py:456-469 — read directly this session]

Note this is **already updated past the original `0e05f50` commit**: Phase 4's
guard-mechanism work added `_path_prefix()` (`installer/executors.py:30-37`),
which de-shims `PATH` for every spawned shell (`script`/`sdkman` kinds) so a
vendor script's own `npm`/`npx` call cannot hit this project's ban shims. The
sdkman executor already uses it. `tests/test_executors.py::_script_of` (lines
24-35) strips and separately asserts this prefix, so
`test_sdkman_sources_init_script_then_installs_candidate`
(`tests/test_executors.py:917-920`) and
`test_sdkman_appends_version_when_given` (`tests/test_executors.py:923-932`)
already cover the prefix's presence implicitly. **No gap here.**

### Model validation (`installer/model.py`)

```python
# installer/model.py:14-26 — METHOD_KINDS tuple
METHOD_KINDS = (
    "script", "node", "sdkman", "github_release", "tarball", "app",
    "dnf", "apt", "pacman", "rpm_ostree", "brew", "cask",
)
```
```python
# installer/model.py:258-263
if kind == "sdkman":
    candidate = params.get("candidate")
    if not isinstance(candidate, str) or not candidate:
        raise ValueError(
            f"tool '{row['id']}': method 'sdkman' requires a non-empty 'candidate'"
        )
```
[VERIFIED: installer/model.py:14-26,258-263 — read directly this session]

### Resolver ranking (`installer/resolve.py`)

```python
# installer/resolve.py:6-20
_RANK = {
    "script": 10, "github_release": 20, "node": 20, "sdkman": 20,
    "tarball": 20, "app": 20, "dnf": 30, "apt": 30, "pacman": 30,
    "rpm_ostree": 35, "brew": 40, "cask": 40,
}
...
if kind in ("script", "node", "sdkman", "github_release", "tarball", "app"):
    return True
```
[VERIFIED: installer/resolve.py:6-38 — read directly this session]

`sdkman` is ranked at 20 (userspace-download tier), same as `node`/
`github_release`/`tarball`/`app`, and `_applies` treats it as always-applicable
(no OS/brew gating) — meaning it works identically on immutable Fedora/Bazzite,
confirmed by `tests/test_resolve.py::test_sdkman_applies_on_every_platform_including_immutable`
(`tests/test_resolve.py:146-150`).

### Status detection (`installer/status.py:1-38`)

```python
def is_installed(tool: Tool, app_roots: tuple[Path, ...] | None = None) -> bool:
    if shutil.which(tool.cmd) is not None:
        return True
    for method in tool.methods:
        detect_path = method.params.get("detect_path")
        if isinstance(detect_path, str) and detect_path and Path(detect_path).expanduser().exists():
            return True
    ...
```
[VERIFIED: installer/status.py:16-31 — read directly this session]

This closes the original bug (`sdkman-init.sh` is sourced, not executable, so
`shutil.which` could never find it — every JVM-tool install would silently
re-run SDKMAN's own bootstrap). `detect_path` is a generic mechanism (not
sdkman-specific), tested by `tests/test_status.py::test_detect_path_present_counts_as_installed`
and `test_detect_path_absent_is_not_installed` (`tests/test_status.py:164-185`).

### Test coverage — Rule 7 mirror check (already satisfied)

`.planning/ONESHOT-RULES.md` Non-Negotiable Rule 7 requires a new registry
`kind` to ship matching tests across `test_model.py`, `test_executors.py`,
`test_resolve.py`, `test_registry.py`, `test_status.py`
[VERIFIED: .planning/ONESHOT-RULES.md:105-109 — read directly this session,
quoted: "A new registry method `kind`, executor, or resolver rank added in any
phase must ship with the matching test additions in the same commit (mirrors
the `sdkman` kind's existing test coverage across `tests/test_model.py`,
`tests/test_executors.py`, `tests/test_resolve.py`, `tests/test_registry.py`,
`tests/test_status.py` — same shape, new kind)."]. Grepping the current test
suite confirms this is **already true for the sdkman kind** — the rule's own
wording cites it as the reference example:

| File | Tests present |
|------|---------------|
| `tests/test_model.py` | `test_sdkman_kind_parses_with_candidate` (546-566), `test_sdkman_method_without_candidate_is_a_config_error` (568-581) |
| `tests/test_executors.py` | `test_sdkman_sources_init_script_then_installs_candidate` (917-921), `test_sdkman_appends_version_when_given` (923-932), `test_sdkman_without_candidate_raises_executor_error` (935-937), plus kind-registration assertion at line 97 |
| `tests/test_resolve.py` | `test_sdkman_is_userspace_ranked_before_brew` (140-144), `test_sdkman_applies_on_every_platform_including_immutable` (146-150) |
| `tests/test_registry.py` | `test_java_tools_depend_on_sdkman` (103-106), `test_sdkman_uses_init_script_and_declares_bin_dir` (109-119), `test_java_tools_install_exclusively_through_sdkman` (122-140) |
| `tests/test_status.py` | `test_detect_path_present_counts_as_installed` / `test_detect_path_absent_is_not_installed` (149-185, generic `detect_path` mechanism exercised via an sdkman-shaped fixture) |

[VERIFIED: grep across tests/ this session, each file opened and line-ranges
confirmed via Read]. Additional cross-cutting coverage exists in
`tests/test_app.py:151-170`, `tests/test_deps.py:150-156`,
`tests/test_render.py:71-112`, and `tests/test_session.py:207-227`, all using
`sdkman`→`java` as the worked example for dependency-failure propagation
(Phase 3 mechanism) and cross-tier `requires` resolution (Phase 1 mechanism) —
these are not sdkman-specific tests but confirm sdkman/java is the project's
canonical cross-tier dependency example throughout the suite.

**Conclusion: the unit-level test-coverage gap ROADMAP SC#1 worries about does
not exist.** What SC#1 actually requires beyond this — "real, not just
unit-level verification, including a non-interactive end-to-end check of `sdk
install java`" — is a Tier-3 container run, which by this project's own
`testing.md` rule ("Tests must be deterministic and offline") **cannot** be a
`pytest` test. See "Validation Architecture" below for how this fits the
existing test-map, and "SC#1/SC#2 resolution" for the container evidence
itself.

## SC#2 Resolution: `sdk install java` Non-Interactivity (definitive)

**Question:** Does `sdk install java` (no version given) prompt interactively
because multiple JDK vendors exist? Does pinning a candidate version (e.g. `sdk
install java 21.0.5-tem`) avoid that prompt?

**Answer: No prompt occurs either way. Pinning a version is unnecessary.**

### Method

Live Tier-3 container verification per `.planning/ONESHOT-RULES.md` Rule 14
(colima + docker CLI, confirmed already running on this machine: `colima
status` reported `colima is running using macOS Virtualization.Framework`,
`docker info` reported `Context: colima`, `Version: 29.8.0`)
[VERIFIED: `colima status` / `docker info` output, this session]. Two disposable
`ubuntu:24.04` containers were used (removed after the session):

1. **Container A** — bootstrapped SDKMAN via `curl -s "https://get.sdkman.io?ci=true" | bash`
   (exactly this project's registered `url`), then ran `sdk install java`
   (no version) with stdin closed (`< /dev/null`).
2. **Container B (contrast)** — bootstrapped SDKMAN via `curl -s
   "https://get.sdkman.io" | bash` (no `?ci=true`), to observe the
   non-ci-flag default and confirm what the flag actually changes.

### Evidence

**Container A — `?ci=true` bootstrap (this project's actual configured URL):**
```
$ cat ~/.sdkman/etc/config | grep auto_answer
sdkman_auto_answer=true
```
```
$ sdk version
SDKMAN!
script: 5.23.0
native: 0.7.34 (linux x86_64)
```
```
$ timeout 150 bash -c 'source "$HOME/.sdkman/bin/sdkman-init.sh" && sdk install java' < /dev/null
...
Downloading: java 25.0.4-tem
...
Done installing!
Setting java 25.0.4-tem as default.
EXIT_CODE=0
```
[VERIFIED: live docker container run, this session — command and output shown
above]

**Container B — plain bootstrap (no `?ci=true`), for contrast:**
```
$ curl -s "https://get.sdkman.io" | bash
$ cat ~/.sdkman/etc/config | grep auto_answer
sdkman_auto_answer=false
```
```
$ timeout 150 bash -c 'source "$HOME/.sdkman/bin/sdkman-init.sh" && sdk install java' < /dev/null
...
Setting java 25.0.4-tem as default.
EXIT_CODE=0
```
[VERIFIED: live docker container run, this session — command and output shown
above]

**Both configurations completed non-interactively with exit code 0**, even
though Container B's `sdkman_auto_answer` was `false`. This looked surprising
until the SDKMAN source itself was inspected directly inside the container
(the installed copy under `~/.sdkman/src/`, not a cached/remembered version):

```bash
# ~/.sdkman/src/sdkman-install.sh:37-41 (as installed by the live bootstrap)
if [[ "$sdkman_auto_answer" != 'true' && "$auto_answer_upgrade" != 'true' && -n "$CURRENT" ]]; then
    __sdkman_echo_confirm "Do you want ${candidate} ${VERSION} to be set as default? (Y/n): "
    read USE
fi
```
[VERIFIED: `~/.sdkman/src/sdkman-install.sh:37-41` — read via `docker exec ...
grep`/`sed` this session, quoted verbatim]

```bash
# ~/.sdkman/src/sdkman-env-helpers.sh:41-64 (determine version, no candidate given)
elif [[ ... ]]; then ...
else
    if [[ -z "$version" ]]; then
        version=$(__sdkman_secure_curl "${SDKMAN_CANDIDATES_API}/candidates/default/${candidate}")
    fi
    local validation_url="${SDKMAN_CANDIDATES_API}/candidates/validate/${candidate}/${version}/${SDKMAN_PLATFORM}"
    ...
```
[VERIFIED: `~/.sdkman/src/sdkman-env-helpers.sh:41-64` — read via `docker exec
... sed` this session, quoted verbatim]

**This is the whole finding:**

1. **There is no vendor-selection prompt at all.** When no version is given,
   SDKMAN resolves "the default version" for the candidate via one HTTP call
   to `${SDKMAN_CANDIDATES_API}/candidates/default/${candidate}` — a
   server-side default lookup, not an interactive menu. `sdk install java`
   (no args) simply installs whatever SDKMAN's API currently designates as
   the default `java` candidate (observed: `25.0.4-tem`, Eclipse Temurin).
2. **The only interactive prompt in the entire `sk install` code path** is
   "Do you want X to be set as default? (Y/n)" — and its guard condition
   requires `-n "$CURRENT"`, i.e. a version must *already* be installed and
   marked current for that candidate. On a first/fresh install (this
   project's actual scenario — SDKMAN and the JVM tool install together),
   `$CURRENT` is empty, so this line is never reached, **regardless of
   `sdkman_auto_answer`**. That is why Container B (auto_answer=false)
   completed just as cleanly as Container A.
3. **The prompt would only ever matter on a re-install/upgrade of an
   already-installed candidate** — a scenario this installer's own
   `installer/status.py::is_installed` short-circuits away from anyway (an
   already-installed JVM tool is reported `ALREADY_INSTALLED` and the
   executor is never invoked a second time — same `install_tool`
   short-circuit pattern documented for the `puppeteer`/`mmdc` pnpm case in
   `installer/registry.toml:1900-1915`).
4. **This project's `?ci=true` bootstrap flag is what removes the prompt path
   permanently anyway**, independent of point 3 above: it persists
   `sdkman_auto_answer=true` to `~/.sdkman/etc/config`, which the first
   guard-condition operand (`"$sdkman_auto_answer" != 'true'`) then always
   evaluates false for. Belt-and-suspenders: even in a hypothetical future
   re-install/upgrade scenario, the existing bootstrap already prevents the
   only prompt SDKMAN has.

**Conclusion:** `java`'s SDKMAN candidate does **not** need a pinned `version`
to avoid an interactive prompt. The existing `?ci=true` bootstrap
(`installer/registry.toml:1308`, already shipped) is fully sufficient and was
already correctly reasoned about in the `_sdkman` executor's own code comment
(`installer/executors.py:459-461`) — that comment's claim is now verified
against SDKMAN's actual source rather than resting on the PRD author's
plausible-sounding assumption. **No code change is required for SC#2; only
recording this verification (per D-01/REQ-registry-authoring-verification-checklist)
is needed**, e.g. as a `# Verified {date}: ...` comment above the `java` entry
in `installer/registry.toml`, matching the existing style above `mmdc`/
`puppeteer` (see next section).

**Reproducibility note:** the resolved default version (`25.0.4-tem` at test
time) is dynamic — it tracks whatever SDKMAN's `candidates/default/java` API
currently returns, not a value this project pins. A future re-run of this same
container test may observe a different default version string; the *mechanism*
(no prompt, non-interactive, exit 0) is what was verified, not the specific
version number.

## Registry-Authoring Precedent

### Where this project already documents authoring conventions

`.claude/architecture.md` is the established, single home for project-wide
authoring conventions, added to incrementally by the phase that establishes
each new rule:

- `## The five rules` (top of file) — the five foundational architecture
  rules (one view registry, one navigation path, one apply workflow,
  `setup.py` wiring-only, no orphan helpers)
  [VERIFIED: .claude/architecture.md:7-25 — read directly this session].
- `## Tier is a browsing label` — added by Phase 1
  (`.planning/phases/01-catalog-tier-foundation/`) to state that `tier` is a
  browsing label only, never an ordering mechanism
  [VERIFIED: .claude/architecture.md:27-96 — read directly this session].
- `## Phase 3: install, uninstall, and tweak lifecycle` — added by Phase 3 to
  document the failure-propagation / uninstall-sweep / Oh-My-Zsh-plugins
  conventions that phase introduced
  [VERIFIED: .claude/architecture.md:98-157 — read directly this session].

There is **no `CONTRIBUTING.md`** anywhere in the repo
[VERIFIED: `find ... -iname "CONTRIBUTING*"` returned no results, this
session]. `installer/registry.toml`'s own header comment
(`installer/registry.toml:1-4`) is short and purely mechanical — it names the
resolver's priority ladder in one sentence and nothing else
[VERIFIED: installer/registry.toml:1-4 — read directly this session, quoted:
"# tools-installer registry — single declarative source of truth.\n# Each
[[tool]] declares one or more [[tool.method]] entries. The resolver\n#
(installer/resolve.py) filters them to the platform and orders them by the\n#
priority ladder: script -> userspace download -> native pkg manager ->
brew."]. Given this, `.claude/architecture.md` is the location most consistent
with established precedent — both new guidelines (verification checklist,
brew-preference) fit the existing "phase adds a numbered/named section
documenting a new convention" pattern exactly. **Recommendation: add a new
section, e.g. `## Registry-authoring guidelines`, to `.claude/architecture.md`
in this phase**, rather than starting a new file or overloading
`registry.toml`'s terse header.

### The comment-citation pattern already exists (D-01's mechanism, proven precedent)

Phase 5 already used exactly the mechanism D-01 locks in, informally, above the
`mmdc` and `puppeteer` registry entries:

```toml
# installer/registry.toml:1829-1834
# Verified 2026-09-05: puppeteer declares `postinstall = "node install.mjs"`,
# which downloads Chrome for Testing and chrome-headless-shell into
# `~/.cache/puppeteer`. pnpm blocks that script by default and reports it as a
# warning rather than an error, so `allow_build = ["puppeteer"]` on these
# methods is what makes the browser actually arrive. Without it the install
# reports success and the tool is broken.
```
[VERIFIED: installer/registry.toml:1829-1834 — read directly this session,
quoted verbatim]

This is the same shape the ROADMAP goal names ("the registry-authoring
discipline this whole PRD batch leans on") — Phase 6 does not need to invent a
new recording convention, only **name and codify the one Phase 5 already used
ad hoc**, and apply it retroactively to the `sdkman`/`java` entries which
currently carry no such comment (`installer/registry.toml:1297-1386` has no
`# Verified ...` comment anywhere in that block)
[VERIFIED: installer/registry.toml:1297-1386 — read directly this session, no
`Verified` string present]. **This is the concrete gap this phase should
close**: add a `# Verified {date}: ...` comment above the `java` entry
recording the SC#2 finding above (and, at minimum, a similar comment recording
what was checked for the `sdkman` entry's own `?ci=true` bootstrap choice, if
not already self-evident from the executor's own comment).

### Brew-preference guideline — existing analogous carve-out language

The desired phrasing ("prefer brew... except SDKMAN for the Java toolchain")
already has a real precedent sentence in the registry itself:

```toml
# installer/registry.toml:1321 (java's desc field)
desc = "JVM runtime required by Gradle, Maven, Groovy, and many enterprise projects; installed and version-managed exclusively through SDKMAN, never a native/brew package."
```
[VERIFIED: installer/registry.toml:1321 — read directly this session]

and the commit message that introduced it:

> "Per direction: brew is preferred generally, but Java-toolchain tools must
> go through SDKMAN specifically, never a native/brew package."
[VERIFIED: `git show 0e05f50` commit message — read directly this session]

Codifying this as a guideline in `.claude/architecture.md` is a direct
write-down of an already-followed, already-committed convention — no new
policy is being invented, only documented per REQ-brew-preference-guideline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Verifying `sdk install java` behaves non-interactively | A new pytest fixture that shells out to a real network-dependent SDKMAN install | Tier-3 container verification (colima + docker), evidence recorded in the phase's verification artifact / registry comment, not in `make test` | `testing.md` requires tests be "deterministic and offline"; a live SDKMAN bootstrap needs network access and takes 60-150s — it cannot satisfy that constraint and must not be added to the automated suite. |
| Recording "which OS was this verified on" | A new structured metadata schema/field on `Tool`/`Method` for verification provenance | A plain `# Verified {date}: ...` prose comment above the entry (D-01) | Locked decision D-01 rejected a stronger checked-in mechanism specifically to avoid this overhead; a comment is lower-friction and matches existing precedent (mmdc/puppeteer). |
| Enforcing "prefer brew" | A lint rule or registry test that flags non-brew methods | Prose guideline only (D-02) | Locked decision D-02 explicitly rejects code enforcement — brew availability differs too much per OS/tool for a reliable automated check. |

**Key insight:** This phase is process/documentation hardening, not new
mechanism-building — both locked decisions (D-01, D-02) already steer away
from any new code, schema, or test infrastructure. The main engineering risk
is over-building (e.g. inventing a verification-metadata schema, or writing a
network-dependent pytest test) where a comment and a doc section suffice.

## Common Pitfalls

### Pitfall 1: Treating "unit tests exist" as satisfying SC#1
**What goes wrong:** A planner sees the already-thorough unit-test coverage
(model/executors/resolve/registry/status, all present) and concludes SC#1 is
already met, closing the phase with no new verification evidence.
**Why it happens:** Rule 7's mirror-pattern check is satisfied, and it's easy
to conflate "mirrors the existing test-file pattern" with "real verification."
**How to avoid:** SC#1 explicitly says "real, not just unit-level
verification, including a non-interactive end-to-end check of `sdk install
java`" — this requires Tier-3 container evidence (this research provides it;
a phase plan should still reproduce or explicitly cite it) recorded somewhere
durable (registry comment and/or the phase's VERIFICATION.md), not just green
`make test`.
**Warning signs:** A plan whose only new artifact is a doc file with no
registry-comment update and no reference to a live container run.

### Pitfall 2: Writing a pytest test that shells out to a live SDKMAN install
**What goes wrong:** An executor tries to "prove" SC#1/SC#2 by adding a
`test_sdkman_e2e.py` that runs the real bootstrap and `sdk install java`
inside CI.
**Why it happens:** Seems like the most direct way to encode "real"
verification as a repeatable, automated check.
**How to avoid:** `.claude/testing.md` requires tests be deterministic and
offline (mock network, use `tmp_path`/monkeypatched `HOME`). A live SDKMAN
install needs network access, takes 60-150+ seconds, and depends on an
external service's current API responses (the "default" version can change) —
this cannot be a `pytest` test without violating that rule and without
`make test` staying fast/reliable in CI.
**Warning signs:** A new test file that calls `subprocess.run`/`docker` with
no monkeypatching, or a test with a `pytest.mark.slow`/network marker that
didn't exist before.

### Pitfall 3: Assuming the interactive-prompt risk is about vendor choice
**What goes wrong:** Spending planning effort designing a vendor-selection
mechanism (e.g. defaulting to `-tem`/Temurin explicitly) because "java has
multiple JDK vendors" sounds like the natural source of an interactive
prompt.
**Why it happens:** It's the intuitive guess, and ROADMAP SC#2's wording
("multiple JDK vendors available") invites it.
**How to avoid:** The actual SDKMAN source (verified this session) shows `sdk
install <candidate>` with no version never offers a vendor menu at all — it
resolves one HTTP-fetched "default" version deterministically. The one real
prompt is an upgrade-confirmation prompt unrelated to vendor choice, already
neutralized by the existing `?ci=true` bootstrap. Don't design a vendor-pin
mechanism this phase doesn't need.
**Warning signs:** A plan task that adds a `version = "..."` pin to `java`'s
registry entry "to be safe" without citing evidence that it's needed.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `java`/`gradle`/`maven`/`groovy`/`springbootcli` installed via native pkg manager (dnf/apt/pacman) or brew, `requires = ["sdkman"]` declared but never actually routed through it | Exclusive `kind="sdkman"` method, no fallback | Commit `0e05f50`, 2026-09-04 | Fixes silent policy violation where the declared dependency (`sdkman`) was never the actual install mechanism. |
| `shutil.which` as the sole "is it installed" check | `shutil.which` + `detect_path` fallback for non-executable markers | Same commit | Fixes SDKMAN's own bootstrap being silently re-run on every JVM-tool install attempt, since `sdkman-init.sh` (sourced, not executable) was never detectable. |

**Deprecated/outdated:** None — SDKMAN itself (script `5.23.0`, native
`0.7.34`) is current as observed live this session; no upstream deprecation
found for the `sdk install <candidate> [version]` invocation shape this
project uses.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SDKMAN's `candidates/default/java` API will keep returning a valid, installable Temurin (or equivalent) build indefinitely | SC#2 Resolution | Low — this is SDKMAN's own advertised default-resolution behavior for `sdk install <candidate>` with no version, unrelated to anything this project controls; if SDKMAN changed this API's behavior it would affect every SDKMAN user, not just this project. |
| A2 | The single `sdkman_auto_answer`-gated prompt found in `sdkman-install.sh` (version 5.23.0, script channel STABLE) is the only interactive prompt reachable from this project's exact invocation (`sdk install <candidate> [version]`, no other subcommands) | SC#2 Resolution | Medium — a future SDKMAN release could add a new prompt elsewhere in the install path; this was verified against the current STABLE-channel source (5.23.0), not exhaustively fuzz-tested against every SDKMAN version. Re-verify if SDKMAN's script version changes materially. |

## Open Questions

1. **Should the `# Verified {date}: ...` comment be added retroactively to all
   five JVM-tool entries, or only to `java` (the one SC#2 actually concerns)?**
   - What we know: only `java` has the multi-vendor "why might this prompt"
     question; `gradle`/`maven`/`groovy`/`springbootcli` have single upstream
     implementations with no analogous ambiguity.
   - What's unclear: whether REQ-registry-authoring-verification-checklist
     implies every JVM tool needs its own dated verification comment (e.g.
     confirming each candidate name against SDKMAN's actual candidate list),
     or just the specific SC#2 finding.
   - Recommendation: add the SC#2-specific comment above `java`'s entry (the
     concrete finding this research produced); optionally add a lighter
     comment above the `sdkman` tool entry itself citing the `?ci=true` /
     `sdkman_auto_answer` mechanism, since that is the entry the guarantee
     actually depends on. Treat verifying each of the four other candidate
     names as already covered by `test_registry.py`'s existing assertions
     (`candidate == "groovy"` etc.) plus the fact they install and are used in
     this project's own dev environment — not a new checklist item, since
     REQ-registry-authoring-verification-checklist's checklist is forward-looking
     ("before any new registry entry ships"), not a retroactive audit mandate
     on already-shipped entries beyond what SC#1 specifically names.

2. **Does "a non-interactive end-to-end check of `sdk install java`" (SC#1)
   need to be re-run live during phase execution, or does this research's
   container evidence satisfy it as-is?**
   - What we know: this research already performed the exact check with full
     command/output evidence, following the project's own Tier-3 protocol.
   - What's unclear: whether GSD's verification workflow for this phase
     expects the *executing* agent to independently reproduce the check
     (freshness/trust reasons) or accepts research-phase evidence as
     sufficient, given research and execution may run in different sessions.
   - Recommendation: the planner should schedule a verification/plan task
     that reproduces this container check during phase execution (cheap: ~2-3
     minutes, colima already running) and folds the fresh output into the
     phase's end-of-phase verification report per `human_verify_mode:
     "end-of-phase"` — treating this research's findings as the *expected
     result* to confirm, not as a substitute for the phase's own evidence
     trail.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| colima | Tier-3 container verification | ✓ | running (macOS Virtualization.Framework, x86_64) | — |
| docker CLI | Tier-3 container verification | ✓ | 29.8.0 (Client, context: colima) | — |
| Internet access (to `get.sdkman.io`, SDKMAN CDN/API) | SDKMAN bootstrap + candidate download inside the container | ✓ (confirmed live this session — full downloads completed) | — | — |

No missing dependencies for this phase's research or for the Tier-3
verification step a plan will need to reproduce.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8, pytest-cov ≥5 [VERIFIED: pyproject.toml `[dependency-groups].dev`, read directly this session] |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| Quick run command | `uv run pytest tests/test_registry.py tests/test_executors.py -q` |
| Full suite command | `make test` (`uv run pytest` with `--cov`, `--cov-fail-under=90`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|--------------|
| REQ-sdkman-exclusivity | `java`/`gradle`/`maven`/`groovy`/`springbootcli` install exclusively via `kind="sdkman"` | unit | `uv run pytest tests/test_registry.py::test_java_tools_install_exclusively_through_sdkman -q` | ✅ already exists |
| REQ-sdkman-exclusivity | SDKMAN's own bootstrap is self-detected (no re-run) | unit | `uv run pytest tests/test_status.py -k detect_path -q` | ✅ already exists |
| REQ-sdkman-exclusivity | `sdk install java` is genuinely non-interactive end-to-end | manual / Tier-3 container | colima + docker run per this research's "Method" section (not a pytest command) | ❌ not automatable — record as phase verification evidence, not a new test file |
| REQ-sdkman-exclusivity | SC#2 (pinned version needed?) is resolved and recorded | documentation | N/A — a registry comment, not a test | ❌ Wave 0: add `# Verified {date}: ...` comment above `java`'s entry |
| REQ-registry-authoring-verification-checklist | Checklist exists and names a recording mechanism | documentation | N/A | ❌ Wave 0: new `.claude/architecture.md` section |
| REQ-brew-preference-guideline | Guideline is written down with the SDKMAN carve-out named | documentation | N/A | ❌ Wave 0: same `.claude/architecture.md` section |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_registry.py tests/test_model.py tests/test_executors.py tests/test_resolve.py tests/test_status.py -q`
- **Per wave merge:** `make test` (full suite, coverage floor enforced)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus the Tier-3
  container check's fresh output folded into the phase's end-of-phase
  verification report (this phase produces no new pytest file for that check
  — see Wave 0 Gaps).

### Wave 0 Gaps
- [ ] No new test *file* gap — all five mirror-pattern files already have
      sdkman coverage (confirmed above). This phase's "test" work, if any, is
      limited to confirming existing assertions still hold; it should not
      need new pytest files.
- [ ] `installer/registry.toml` — add `# Verified {date}: ...` comment above
      `java`'s entry (and optionally `sdkman`'s) recording the SC#2 finding —
      this is documentation, not code, but is the closest thing to a "gap"
      this phase has in the registry itself.
- [ ] `.claude/architecture.md` — new section for the two registry-authoring
      guidelines (framework install: none needed, it's markdown).

*(No test-framework install gaps — pytest/coverage tooling is already fully
configured via `pyproject.toml` and `make test`.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | no | No auth surface touched by this phase. |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | `installer/model.py:258-263` already validates `candidate` is a non-empty string at load time (config-time validation, not runtime injection) — no new input surface this phase. |
| V6 Cryptography | no | N/A — no crypto operations in this phase's scope. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Shell command injection via registry-declared `candidate`/`version` params interpolated into a `bash -c` pipeline | Tampering | Already mitigated: `installer/executors.py:465-467` builds `install` as a list and uses `shlex.join(install)` before interpolating into the pipeline string, and the `candidate`/`version` values originate only from this project's own committed `registry.toml` (not runtime user input) — validated as non-empty strings at load time (`installer/model.py:258-263`). No new mitigation needed this phase; this is existing, already-tested behavior (`tests/test_executors.py:917-932` exercise the exact rendered script string). |
| A hypothetical future interactive prompt hanging forever under Textual's raw-mode terminal (stdin owned by Textual, no way to respond) | Denial of Service (self-inflicted hang, not an external attacker) | This research's SC#2 finding removes the only currently-known prompt path for `sdk install <candidate>`. No code mitigation is added this phase (D-02-style: documented finding, not a new timeout/guard mechanism) — flagged here so a future SDKMAN version bump is reviewed for new prompts, per Assumption A2 above. |

This phase adds no new package installs, no new network-facing code paths
beyond what SDKMAN's own already-shipped bootstrap does, and no new user
input surface — the security domain here is narrow by design (verification +
documentation, not new mechanism).

## Package Legitimacy Audit

Not applicable — this phase installs no new external packages (no npm/pip/
cargo/brew formula additions). It verifies and documents an already-shipped
mechanism (`0e05f50`) and writes process documentation. `sdkman` itself was
already vetted and shipped in a prior commit, outside this phase's scope to
re-audit as a "new package."

## Code Examples

### Reproducing the Tier-3 SDKMAN non-interactivity check (for phase execution)

```bash
# Source: this research session, live-tested against colima + docker
docker rm -f sdkman-verify >/dev/null 2>&1
docker run -d --name sdkman-verify ubuntu:24.04 sleep infinity
docker exec sdkman-verify bash -c '
  apt-get update -qq >/dev/null 2>&1
  apt-get install -y -qq curl zip unzip ca-certificates >/dev/null 2>&1
  curl -s "https://get.sdkman.io?ci=true" | bash >/tmp/install.log 2>&1
  grep -i auto_answer "$HOME/.sdkman/etc/config"
'
docker exec sdkman-verify bash -c '
  timeout 150 bash -c "source \"\$HOME/.sdkman/bin/sdkman-init.sh\" && sdk install java" < /dev/null
  echo "EXIT_CODE=$?"
'
docker rm -f sdkman-verify
```

### Recommended registry comment (satisfies REQ-registry-authoring-verification-checklist + SC#2)

```toml
# Source: this research's own pattern, mirroring installer/registry.toml:1829-1834 (puppeteer)
# Verified 2026-09-05 (Tier-3 container, colima+docker, ubuntu:24.04): `sdk
# install java` (no version given) resolves SDKMAN's server-side "default"
# candidate version and completes non-interactively, exit 0, with no vendor
# prompt of any kind. SDKMAN's only interactive prompt in `sk_install`
# ("Do you want X set as default? (Y/n)") requires an existing $CURRENT
# version (upgrade-only path) AND sdkman_auto_answer=false; this tool's
# `sdkman` bootstrap (?ci=true) already sets sdkman_auto_answer=true
# permanently, so no pinned `version` is needed here.
[[tool]]
id = "java"
...
```

## Sources

### Primary (HIGH confidence)
- Live Tier-3 container verification (colima + docker, this session) — SDKMAN
  bootstrap behavior, `sdk install java` non-interactivity, both
  `sdkman_auto_answer=true` and `=false` configurations
- `~/.sdkman/src/sdkman-install.sh` and `~/.sdkman/src/sdkman-env-helpers.sh`
  (installed copy inside the container, SDKMAN script `5.23.0`, STABLE
  channel) — read directly via `docker exec` this session
- This repository's own source: `installer/registry.toml`,
  `installer/executors.py`, `installer/model.py`, `installer/resolve.py`,
  `installer/status.py`, `.claude/architecture.md`, `.claude/testing.md`,
  `.planning/ONESHOT-RULES.md`, `.planning/ROADMAP.md`,
  `.planning/REQUIREMENTS.md`, `.planning/config.json` — all read directly
  this session
- `git show 0e05f50` — the full diff and commit message of the existing
  SDKMAN-exclusivity implementation

### Secondary (MEDIUM confidence)
None used — all claims in this research trace to direct tool verification
(container testing, source reading) or direct repository inspection.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new library/stack decisions in this phase
- SDKMAN behavior / SC#2 resolution: HIGH — verified live against real SDKMAN
  source and real container execution, cross-checked with a contrast case
- Registry-authoring placement recommendation: HIGH — based on direct reading
  of existing precedent (architecture.md's phase-append pattern, the
  mmdc/puppeteer comment style)
- Test-coverage gap analysis: HIGH — every claim traces to a specific file
  and line range read this session

**Research date:** 2026-09-05
**Valid until:** 2026-10-05 (30 days — SDKMAN's `sk_install` prompt logic is
stable, slow-moving shell-script behavior; re-verify if SDKMAN's script
version changes materially, per Assumption A2)
