# Phase 18: Registry truth and drift guard - Pattern Map

**Mapped:** 2026-10-15
**Files analyzed:** 27 new/modified
**Analogs found:** 26 / 27 (all analog paths are git-tracked source; none are gitignored mirrors)

Line numbers below were read this session; anchor by symbol when the tree has moved.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/model.py` (METHOD_PARAMS, `verified`, pinned rule, drop `managed-download`) | model/validation | transform | itself: `METHOD_KINDS`/`OWNER_PROBES`, `load_tools` loop (~654-700) | exact |
| `installer/registry.toml` (seed `verified`, 35 fixes, drawio, pins) | config/data | batch | existing entries (anchor line `tier =`) | exact |
| `installer/versions.py` (`Release`, `resolve_github_release`, `release_resolver`, `parse_version` fix) | service | request-response | `resolve_github_tag` (~315-330), `_NAME_PREFIX_BOUNDARY` (56) | exact |
| `installer/download.py` (target gains digest, staged install, smoke hook, `resolve_release`) | service | file-I/O | `ExecContext` (43-47), `DownloadTarget`/`_resolve_target` (76-127), `_replace_archive` | exact |
| `installer/apps.py` (`cli_spec` honors `cli_name`, staged install, smoke) | service | file-I/O | `cli_spec` (47-65), `update_app` | exact |
| `installer/executors.py` (`smoke_binary`) | utility | request-response | `run_output` use + `ExecutorError` in executors.py; `link_executable` | role-match |
| `installer/engine.py` (manager-kind smoke, `unverified_reason`) | service | event-driven ladder | `install_tool` ladder (~133-175) | exact |
| `installer/render.py` (`render_verification` reason) | utility | transform | existing `render_verification` | exact |
| `installer/status.py` (`MACOS_STUBS`, reason) | service | request-response | `is_installed` (18-66) + `detect_path` precedent | exact |
| `installer/install_ownership.py` (drop `_managed_download`) | service | request-response | `_PROBES` dict (~376), neighbors | exact |
| `installer/assets.py` (`render_pinned_url`) | utility | transform | `render_asset` | role-match |
| `installer/version_cache.py`, `version_status.py` (digest store, optional/last) | store | CRUD | `_entry_from_raw`, `resolve_github_release_status` | role-match |
| `installer/verify_registry.py` (NEW) | service/CLI | batch + request-response | `download._resolve_target` + `versions.py` fetch + `run.py::run_output` | partial (new module, glue over analogs) |
| `.github/workflows/verify-registry.yml` (NEW) | config | event-driven (cron) | `.github/workflows/ci.yml` | role-match |
| `Makefile` (`--isolated --no-dev`, `verify-registry` target) | config | n/a | Makefile 14-32 launchers | exact |
| `install.sh` (line 88) | config | n/a | itself | exact |
| `scripts/container-e2e-verify.sh` (lines ~197, ~261) | config | n/a | itself | exact |
| `tests/test_model.py` (+`verified` in `_write`/`_node_registry`, rewrite 803-827) | test | n/a | itself | exact |
| `tests/test_registry.py`, `test_install_ownership.py`, `test_version_cache.py` | test | n/a | existing pins (counts, owner_probes) | exact |
| `tests/test_download.py` (executable `fixture_runner`, digest, smoke) | test | n/a | `fixture_runner` (582-598) | exact |
| `tests/test_versions.py`, `test_status.py`, `test_apps.py`, `test_uninstall.py`, `test_engine.py`, `test_render.py`, `test_executors.py` | test | n/a | existing files | exact |
| `tests/test_verify_registry.py` (NEW) | test | n/a | `tests/test_download.py` canned-fetch style | role-match |
| `tests/test_verify_registry_workflow.py` (NEW) | test | n/a | `tests/test_ci_workflow.py` | exact |
| `tests/test_makefile.py` (NEW) | test | n/a | `tests/test_ci_workflow.py` text-parse style | role-match |
| `tests/test_install_sh.py` (line ~223 literal) | test | n/a | itself | exact |
| `.claude/architecture.md`, `.claude/skills/tool-onboarding/SKILL.md` | doc | n/a | existing `# Verified` paragraph | exact |
| `installer/uninstall.py` | service | n/a | already imports `cli_spec`; no change expected | exact |

## Pattern Assignments

### `installer/model.py` (validation, transform)

**Analog:** itself. Closed-set convention (`METHOD_KINDS` 22-37, `OWNER_PROBES` 54-64; delete `"managed-download"` at 55).

**Loop insertion point** (`load_tools`, params built right after os/arch checks):
```python
params = {k: v for k, v in entry.items() if k not in ("kind", "os", "arch")}
if kind == "node":
    npm_pkg = params.get("npm_pkg")
    if not isinstance(npm_pkg, str) or not npm_pkg:
        raise ValueError(
            f"tool '{row['id']}': method 'node' requires a non-empty 'npm_pkg'"
        )
```
Add immediately after `params`, before the `kind == "node"` branch:
```python
if unknown := set(params) - METHOD_PARAMS[kind]:
    raise ValueError(f"tool '{row['id']}': method '{kind}' has unknown key '{sorted(unknown)[0]}'")
```
`skill_pack` maps to `frozenset()`; keep the existing `len(entry) != 1` check.

**Tool-level required key** (copy the shape of the existing `tier` check):
```python
_parse_enum(Category, row["category"], "category", f"tool '{row['id']}'")
if "tier" not in row:
    raise ValueError(f"tool '{row['id']}': missing required 'tier'")
```
Add `verified` here: `type(v) is date` (not `isinstance`), reject future (> today + 1 day), `load_tools(manifest_path, *, today: date | None = None)`. Errors are `f"tool '{id}': ..."`. Do not add a `verified` field to `Tool`.

**Node-kind per-key validation** (`_parse_pkg_list(params["co_install"], "co_install", context)`, `context = f"tool '{row['id']}'"`) is the style for `version`/`sha256`/smoke-argv shape checks. Smoke argv validates against `_SCRIPT_ARG_RE`, like script `args`.

**Tests:** rewrite `tests/test_model.py:803-827` (`test_non_node_method_leaves_new_keys_untouched`, brew with `co_install`, `smoke`, ...) to `pytest.raises(ValueError, match="unknown key")`.

---

### `installer/versions.py` (service, request-response)

**Analog:** `resolve_github_tag` (full body read):
```python
def resolve_github_tag(repo: str, fetch: Fetch = urlopen_fetch) -> str:
    try:
        raw = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionError(f"failed to resolve tag for {repo}: {exc}") from exc
    tag = str(data.get("tag_name", ""))
    if not tag:
        raise VersionError(f"no release tag for {repo}")
    return tag
```
New `resolve_github_release` reuses this body, adds `digests = {a["name"]: a["digest"].removeprefix("sha256:") for a in data.get("assets", []) if str(a.get("digest","")).startswith("sha256:")}`; `resolve_github_tag` becomes `.tag`. Keep the `VersionError ... from exc` wrap so verify-registry can classify by `__cause__` (HTTPError 403/429 or URLError -> INCONCLUSIVE; 404 -> DRIFT).

**Parser fix (D-14):** root cause is
```python
_NAME_PREFIX_BOUNDARY = re.compile(r".*[-\s](?=[vV]?\d)")
```
Require a non-empty alphabetic name before the boundary (`-1`, `--2`, `-v1.2.3` -> None; `jq-1.8.1` still parses). Normalize tokens (strip quotes, trailing `,`/`;`, leading `version=`) in the one helper shared by `parse_version`, `parse_status_version`, `extract_observed_version` (`_match_observed_version`). Table-driven test over audit fixtures.

**Fetch/Token:** `urlopen_fetch` (adds token to api.github.com only); reuse for HEAD probes with `urllib.request.Request(url, method="HEAD")`.

---

### `installer/download.py` (service, file-I/O)

**Analog (context seam):**
```python
@dataclass(frozen=True)
class ExecContext:
    runner: Runner
    platform: Platform
    resolve_tag: TagResolver
```
Add `resolve_release: ReleaseResolver | None = None`; when `None`, wrap `ctx.resolve_tag` as `Release(tag, {})` so existing lambda-tag tests keep passing. Production derives it via `versions.release_resolver(resolve_tag)` inside `engine.install_tool`.

**Core (`_resolve_target`):** `DownloadTarget(url, member, asset, checksum)` gains `expected_sha256: str | None` and `unverified_reason: str | None`. Order: pinned checksum file/sha256 -> `release.digests[asset]` -> unverified with reason. github_release branch currently does `tag = ctx.resolve_tag(repo)`; replace with `release = ...; tag = release.tag`.
```python
tag = ctx.resolve_tag(repo)
ver = tag.removeprefix("v")
asset = render_asset(template, ver, tokens)
base = f"https://github.com/{repo}/releases/download/{tag}"
```
Tarball branch currently raises on `checksum`; relax for pinned `sha256` (D-03) and render `{ver}` from `method.params["version"]` via the new `assets.render_pinned_url`.

**Staged flow:** unify install with `_replace_archive`/`_replace_raw` (update path) and insert verify -> `smoke_binary` -> swap. Keep layout `~/.local/opt/<link.name>/<member>` plus symlink (Phase 17 `plan_removal` depends on it). Mismatch raises `ChecksumMismatch` (not `ExecutorError`); smoke failure raises `ExecutorError`.

---

### `installer/executors.py` (`smoke_binary`, utility)

**Analog:** `run_output`/`CommandError` (`installer/run.py`):
```python
except subprocess.CalledProcessError as exc:
    raise CommandError(cmd, exc.returncode, detail=(exc.stderr or "").strip()) from exc
except OSError as exc:
    raise CommandError(cmd, 127) from exc
```
Imports already present: `from installer.run import CommandError, Runner, run_output`, `ExecutorError` in the same module, `link_executable`/`replace_symlink` from `installer.atomic`. Implement per RESEARCH Pattern 4: fail on 126/127 or loader-error regex in `exc.detail`; other non-zero and timeout (124) pass.

---

### `installer/engine.py` (ladder, event-driven)

**Analog:** `install_tool` ladder; no new engine branch for digest mismatch:
```python
ctx = ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
...
        try:
            verified, handoff = _perform(tool, method, ctx)
        except ChecksumMismatch as exc:
            if checksum_policy == "fail":
                return InstallOutcome(
                    tool.id, InstallStatus.CHECKSUM_MISMATCH, method_kind=method.kind, errors=(exc,)
                )
            errors.append(exc)
        except (CommandError, executors.ExecutorError, VersionError) as exc:
            errors.append(exc)
```
Add `resolve_release=release_resolver(resolve_tag)` to `ExecContext(...)`. Manager-kind smoke: after `_perform` succeeds and `prepend_path`, only if `shutil.which(tool.cmd)` resolves, call `smoke_binary`; failure is an `ExecutorError` that falls through (inside the `try`). `InstallOutcome` gains `unverified_reason`.

---

### `installer/apps.py` (`cli_spec`, service)

**Analog:** itself (47-65):
```python
cli = method.params.get("cli")
...
name = path.name
if name in ("", "."):
    raise ExecutorError(f"cannot derive a CLI name from '{cli}'")
return cli, name
```
Change: `name = cli_name if set (validated non-empty str, no "/") else path.name`. `uninstall.py` already imports `cli_spec`, so it stays single-sourced. Test in `tests/test_apps.py`/`test_uninstall.py` with `cli_name`.

---

### `installer/status.py` (`MACOS_STUBS`, service)

**Analog:** `is_installed` (18-66). The first line `if shutil.which(tool.cmd) is not None: return True` is where the stub rule intercepts: if the resolved path is in the closed table (`/usr/bin/java` -> `/usr/libexec/java_home`, `/usr/bin/git` -> `xcode-select -p`) then run the injected probe; exit 0 -> True, else not installed with a reason. Precedent for "marker is not a PATH binary": the `detect_path` loop. Inject probe like `app_roots` (parameter default) for tests.

---

### `installer/install_ownership.py` (`_managed_download` removal)

**Analog:** itself. Delete `def _managed_download` (line 83-89) and the `"managed-download": _managed_download,` entry (376), plus the comment at line 42 mention. Gate: `! rg managed-download installer/`.

---

### `installer/verify_registry.py` (NEW; service, batch)

**Closest analogs (compose, do not duplicate):**
- Resolver: `download._resolve_target(method, ctx)` and `assets.arch_tokens`/`render_asset`.
- Release: `versions.resolve_github_release` with a per-run `functools.cache` over repo.
- Runner: `run.run_output` for `gh` calls (returns str, so the JSON is readable); `OutputRunner`.
- Archive member check: `tarfile.open(...).getnames()` / `zipfile.ZipFile(...).namelist()` (list only, never extract).
- CLI entry style: `python -m installer.verify_registry` with `--issue`, `--state PATH`, `--write`; exit codes 0 ok, 1 drift, 2 inconclusive (no `gh` issue call).
- Writer: scoped line rewrite by `[[tool]]` id block, anchor on `tier =` line for insertion, replace `verified =`/`version =`/checksum lines, then `tomllib.loads(new) == apply_edits(tomllib.loads(old), edits)` guard.
- Issue upsert: `gh label create registry-drift --force`, `gh issue list --label registry-drift --state open --json number --limit 1`, then `gh issue edit N --body-file F` or `gh issue create ... --body-file F`; asset names in code spans.
- State: JSON `{url: digest}`, default under XDG cache, `actions/cache` in CI (L-18-04).

No existing module does drift checking; the planner uses RESEARCH.md designs for structure.

---

### `.github/workflows/verify-registry.yml` (NEW)

**Analog:** `.github/workflows/ci.yml` (uses `astral-sh/setup-uv`, `make` targets). Skeleton is in RESEARCH "Workflow skeleton": `on: schedule + workflow_dispatch`, `permissions: {contents: read, issues: write}`, `GH_TOKEN: ${{ github.token }}`, cache of the state file, `make verify-registry ARGS="--issue --state ..."`. Off-peak cron minute. Never referenced from `ci.yml`.

---

### `Makefile` / `install.sh` / `scripts/container-e2e-verify.sh`

**Analog (Makefile 14-32):** every launcher is `uv run setup.py <flag>`. Per L-18-01 change `setup`, `doctor`, `fix`, `uninstall`, `guard`, `unguard` (and `run` via `setup`) to `uv run --isolated --no-dev setup.py ...`; leave `validate`/`test` untouched. Add `verify-registry` to `.PHONY` (line 2) and as a target using the `## ` help-comment form already matched by `help`:
```make
setup:  ## Launch the setup wizard (pass flags via ARGS, e.g. ARGS="--all --yes")
	uv run setup.py $(ARGS)
```
`install.sh:88`: `exec uv run setup.py "$@"` -> `exec uv run --isolated --no-dev setup.py "$@"`; update `tests/test_install_sh.py:223` literal (`"uv run setup.py --all --yes"`). Container script: `uv sync` at ~197 -> `uv sync --no-dev`; launch at ~261 same flags.

---

### Tests

**`tests/test_verify_registry_workflow.py`** (copy from `tests/test_ci_workflow.py`):
```python
ROOT = Path(__file__).resolve().parent.parent
def _load_ci() -> dict[Any, Any]:
    return cast(dict[Any, Any], yaml.safe_load(CI_WORKFLOW.read_text()))
# PyYAML parses the bare `on:` key as the boolean True (YAML 1.1), not "on".
triggers = data.get("on", data.get(True, {}))
```
Assert triggers == {schedule, workflow_dispatch}, permissions pinned, no push/commit/`gh pr` step, `ci.yml` text lacks `verify-registry`.

**`tests/test_makefile.py`** (NEW, no analog test): text-parse recipes per target; assert `--isolated` and `--no-dev` on the launcher set and absent on `validate`/`test`.

**`tests/test_download.py::fixture_runner`** (582-598): currently writes `b"member-bytes"` on extraction; change to write `#!/bin/sh\nexit 0\n` and `chmod 0o755` so real smoke passes. Add one fake-binary-exit-127 test using real shell scripts in `tmp_path`.

**`tests/test_model.py`**: add `verified = 2026-10-13` to the `_write`/`_node_registry` helpers (30+1 inline fixtures, also `tests/test_skill_lifecycle.py`). Inject `today=` for deterministic date tests.

**`tests/test_registry.py` pins to update (drawio-cli removal):** tier `user` 47 -> 46, audience `human` 34 -> 33 (`both` stays 47), cmd-duplicates -> `{}`, owner_probes pins at ~1968-1969, plus `:1118-1120, 1135-1142, 1168-1173, 1966`; `tests/test_install_ownership.py:28,111,180`. Do not reword `# Verified` comments or the phrase `no bin_dir`.

## Shared Patterns

### Error messages
**Source:** `installer/model.py` (`f"tool '{row['id']}': ..."`). Apply to every new loader check.

### Hard-fail vs fall-through
**Source:** `installer/checksums.py::ChecksumMismatch` (deliberately NOT an `ExecutorError`) and `engine.install_tool` except clauses. Digest mismatch -> `ChecksumMismatch`; smoke/permission/format issues -> `ExecutorError`. Never swap.

### Order of operations (security)
verify digest -> smoke -> atomic swap/link (`atomic.replace_symlink`, `executors.link_executable`, `download._replace_archive`).

### Command execution
**Source:** `installer/run.py::run_output` (stdin DEVNULL, new session, `CommandError` on OSError/non-zero/timeout). All new subprocess calls (smoke, `gh`) go through it; zero sudo.

### Injection for offline tests
`ExecContext` fields, `Fetch` param on `versions.py` functions, `app_roots` param on `is_installed`, `today` param on `load_tools`. All new network or host probes must be injectable the same way.

### Architecture rules (`.claude/architecture.md`)
No orphan helpers; decision logic in `installer/`, `setup.py` wiring only; no new `# noqa`/`# type: ignore`; pyright strict; `pyproject.toml`/`uv.lock` unchanged.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `installer/verify_registry.py` (writer + issue upsert + drift report) | service | batch | No drift checker or TOML line-rewriter exists; compose from the analogs above and RESEARCH Pattern 5 |
| `tests/test_makefile.py` | test | n/a | No Makefile test exists |

## Metadata

**Analog search scope:** `installer/`, `tests/`, `.github/workflows/`, `Makefile`, `install.sh`, `scripts/`
**Files scanned:** ~15 read (targeted ranges), tracked-file list checked via `git ls-files`
**Pattern extraction date:** 2026-10-15
**Not checked:** `uninstall.py`, `version_cache.py`, `version_status.py` and the container script bodies were not opened (line refs taken from RESEARCH); registry.toml entries were not re-read.
