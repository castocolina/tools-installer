# Phase 24: Onboarding through the skill and e2e - Pattern Map

**Mapped:** 2026-11-08
**Files analyzed:** 27 new/modified
**Analogs found:** 25 / 27 (all analog paths verified git-tracked: installer/, scripts/, tests/, .claude/skills/)

Line numbers are from the tree at mapping time. 23.1/23.2 edits shift lines: re-anchor on the symbol or heading named, not on the number.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/cargo_distrobox.py` (new) | service (multi-step executor) | file-I/O + subprocess, try/finally | `installer/download.py` (`_replace_raw`, `install_download`, `mkdtemp`/`finally` at :381-411) | role-match |
| `installer/model.py` (`METHOD_KINDS`, `METHOD_PARAMS`, load validation) | model/config | request-response (load-time validation) | same file, `github_release` + `script` entries (:26-102), `if kind ==` chain (:561-700) | exact |
| `installer/resolve.py` (`_RANK`, `_applies`, `_rejection`, `_method_short`, `unavailable_reason`) | service (single switch) | transform | same file, `brew`/`rpm_ostree` clauses (:38-127) | exact |
| `installer/platform.py` (`has_distrobox`, `has_podman`) | model | transform | its own `has_brew` field + `detect()` | exact |
| `installer/download.py` (`artifact_paths` branch) | utility | transform | same function, `script` branch (:330-340) and raw branch (:310-311) | exact |
| `installer/engine.py` (`_perform`, `_manager_method`) | service | request-response | same file (:37-40, :129-148) | exact |
| `installer/update.py` (`_update_installer_owned`) | service | request-response | same function (:419-431) | exact |
| `installer/version_status.py` (`github_repo`, has_* refresh, `_tuning_fact`) | service | request-response | same file `github_repo` (:275-286); `replace(self._platform, has_brew=...)` sites | exact |
| `installer/ownership.py` (`_INSTALLER_KINDS`, labels) | config | transform | same file (kind tuple + label dict) | exact |
| `installer/desktop_entry.py` (new) | utility (pure render) | transform | `terminal_shell._safe_executable` + `zshenv_block` (:122-129, :310) | role-match |
| `installer/terminal_shell.py` (alacritty + herdr branches, revert, injected reload runner) | service | file-I/O (guarded region) | same file kitty/WezTerm branches (:529-564), `_revert_terminal_shells` (:445-466) | exact |
| `installer/post_install.py` (new keybindings tuning action) | service | file-I/O | same file `_tune_omz_plugins` / `_tune_agent` / `apply_install_tuning` (:212-310) | exact |
| `installer/postinstall.py` (`_HERDR_TARGETS`, `HOST_CATALOG_IDS`, D-27 status probe, sidebar hook) | service (hook pair) | event-driven (register/unregister) | same file `_herdr_register`/`_codegraph_register`/`HookPair` (:146-256) | exact |
| `installer/app.py` (`_after_removal` terminal branch) | service | event-driven | same function (:679-705) | exact |
| `installer/agent_settings.py` (nested TOML key writer, Pitfall 4) | utility | file-I/O | its own `_guarded`/`_insert_toml`/`_toml_remove` (not re-read; see RESEARCH Pitfall 4) | role-match |
| `installer/uninstall.py` (best-effort `rmdir` of empty ancestors, Q7) | service | file-I/O | its own `remove_paths` | exact |
| `installer/registry.toml` (herdr entry) | config | n/a | `yq` raw `github_release` entry (:490-510) | exact |
| `installer/registry.toml` (alacritty rewrite + `config_paths`) | config | n/a | current alacritty entry (:2936-2963); `copilot` for `post_install` (:1665-1692) | exact |
| `.claude/skills/tool-onboarding/SKILL.md` | doc | n/a | itself (`### 4b.` heading, TUNE-04 rule text) | exact |
| `docs/catalog-unsupported-tools.md` | doc | n/a | itself | exact |
| `scripts/container-e2e-verify.sh` (`--distro`, rerun gate, nested target) | utility (harness) | batch | itself: `record_fedora_release`, `install_root_prereqs`, `accumulate_summaries`, `cmd_pass2` | exact |
| `tests/test_cargo_distrobox.py` (new) | test | fake-runner | `tests/test_download.py` / `tests/test_executors.py` fake-runner style | role-match |
| `tests/test_desktop_entry.py` (new) | test | transform | any pure-module test (e.g. `tests/test_terminal_shell.py` region tests) | role-match |
| `tests/test_container_e2e_receipts.py` (extend) | test | bash-extraction | itself (`_function`, `_harness`, `_summary_harness`) | exact |
| `tests/test_resolve.py`, `test_model.py`, `test_registry.py`, `test_download.py`, `test_receipts.py`, `test_uninstall.py`, `test_update.py`, `test_version_status.py`, `test_terminal_shell.py`, `test_post_install.py`, `test_postinstall.py`, `test_session.py`, `test_app.py`, `test_docs.py` (extend) | test | n/a | each file itself | exact |
| `24-UAT.md`, `24-SKILL-JUDGE.md` (new) | doc | n/a | `23.2-UAT.md` / 23.2 VERIFICATION in `.planning/phases/23.2-*` | exact |

## Pattern Assignments

### `installer/model.py` - new kind `cargo_distrobox` (model, load-time validation)

**Analog:** same file, `METHOD_KINDS`/`METHOD_PARAMS` (:26-102) and `KIND_PACKAGE_PARAM` (:104).

Add the kind and a closed key set (ordering/style as existing):
```python
METHOD_KINDS = ("script", "node", ..., "cask")          # :26-41  -> append "cargo_distrobox"
METHOD_PARAMS: dict[str, frozenset[str]] = {            # :44
    "github_release": frozenset({"repo", "asset", "checksum", "member", "strip", "raw",
                                 "archive", "bin_name", "bin_dir", "smoke_argv"}),
    ...
    "cask": frozenset({"cask", "app", "min_os_version", "smoke_argv"}),
}
# new: "cargo_distrobox": frozenset({"repo", "image", "packages", "artifacts", "smoke_argv"})
```
Unknown-key rejection is automatic at `:574` (`unknown = set(params) - METHOD_PARAMS[kind]`). Put the `artifacts` (non-empty list of `{box, host}` tables; `box` relative, no `..`; `host` under `~/.local`, `~/.config`, `~/.terminfo`), `image`, `repo` slug and package-name checks in the `if kind == ...` chain (:583-700): copy the shape of the `script` `paths` validation there. `packages` follows `executors._opt_pkg_list` (a closed list of strings; empty allowed). Add the kind to the `kind in KIND_PACKAGE_PARAM` consumers only if a package param applies (it does not: do not add).

---

### `installer/resolve.py` - one switch (service, transform)

**Analog:** same file. Excerpts to extend (:13-28, :53-76, :90-104, :119-126):
```python
_RANK = {"script": 10, "host_setup": 15, "github_release": 20, ..., "dnf": 30, "apt": 30,
         "pacman": 30, "rpm_ostree": 35, "brew": 40, "cask": 40}
# new: "cargo_distrobox": 25
```
```python
# _applies, after the unconditional-True tuple (:53-63) and before brew (:64):
if kind == "cargo_distrobox":
    return platform.has_distrobox and platform.has_podman
```
```python
# _rejection mirrors _applies clause order (:101-104); add before the native fallback:
kind = method.kind
if kind == "cargo_distrobox":
    return "tools"
if kind == "rpm_ostree" or (kind in _NATIVE_OS and platform.immutable):
    return "immutable"
```
`_method_short` (:119) gains `if category == "tools": return "needs distrobox and podman"`. `unavailable_reason` (:129-139) joins shorts with `"; "`: dedupe with `dict.fromkeys` so three native kinds do not repeat "immutable host". The `os`/`arch` gates at the top of `_applies` already make macOS UNAVAILABLE when the method lists `os = [debian, fedora, arch]`. The existing parity test (`tests/test_resolve.py`) pins `_applies`/`_rejection` order: extend it.

**Platform facts re-read each pass:** copy the `replace(self._platform, has_brew=self._which("brew") is not None)` sites in `installer/version_status.py` (two sites, ~:1438 and ~:1605) and add the two new fields; `platform.py` gets `has_distrobox: bool = False`, `has_podman: bool = False` next to `has_brew`, set in `detect()` via `shutil.which`.

---

### `installer/download.py` - `artifact_paths` branch (utility, transform)

**Analog:** same function (:284-341). Script branch is the model for "declared list -> Artifacts":
```python
if method.kind == "script":
    declared = method.params.get("paths")
    if not isinstance(declared, list):
        return ()
    found: list[Artifact] = []
    for entry in cast(list[str], declared):
        path = expand_script_token(entry)
        if path is not None:
            found.append(Artifact(Path(path), "tree" if entry.endswith("/") else "leaf"))
    return tuple(found)
```
New branch: for each `artifacts[i]["host"]` return `Artifact(Path(host).expanduser(), "file")` for the binary (the one whose name equals the tool cmd / first entry) and `"leaf"` for entry, icon, terminfo files (leaf is type-only so a user's edit to the entry does not turn the receipt BROKEN). `Artifact.kind` is `Literal["dir","link","file","tree","leaf"]` (:281). `receipts.record` and `uninstall._receipt_proof` read this one formula: no change there.

---

### `installer/cargo_distrobox.py` (new; service, multi-step executor with guaranteed cleanup)

**Analog:** `installer/download.py` placement + cleanup (`_replace_raw` :478-488, tempdir/`finally` :381-411, `ExecContext` :54). Staging swap recipe to copy:
```python
def _replace_raw(link: Path, asset_path: Path, *, smoke_argv: Sequence[str] | None = None) -> None:
    new = staged_sibling(link, NEW_SUFFIX)
    try:
        shutil.copy2(asset_path, new)
        new.chmod(0o755)
        if smoke_argv is not None:
            smoke_binary(new, smoke_argv)
        os.replace(new, link)
    except Exception:
        new.unlink(missing_ok=True)
        raise
```
For several artifacts: stage every `.new` sibling first, smoke only the binary, then `os.replace` all; on part-way failure restore from `.old` (reduced `_replace_archive` :491+). Old receipt stays until the last swap succeeds.

**Wiring, copy the dispatch shape** (executor is called with an `ExecContext`, not `executors.execute`, because it needs `resolve_release`):
```python
# installer/engine.py:139-148
if method.kind in download.DOWNLOAD_KINDS:
    reason = download.install_download(method, ctx)
    return reason is None, reason, ()
if method.kind in apps.APP_KINDS:
    reason = apps.install_app(method, ctx.runner)
    return reason is None, reason, ()
...
# add: if method.kind == "cargo_distrobox": reason = cargo_distrobox.install(method, ctx) ...
```
```python
# installer/engine.py:37-40 -- the new kind must be excluded or it gets a PATH smoke after install
def _manager_method(method: Method) -> bool:
    if method.kind in download.DOWNLOAD_KINDS or method.kind in apps.APP_KINDS:
        return False
    return method.kind not in _HANDOFF_KINDS      # add the kind here (or to _HANDOFF-like exclusion)
```
```python
# installer/update.py:419-431 -- same ExecContext construction for the update branch
if method.kind in download.DOWNLOAD_KINDS:
    result = download.update_download(method, ExecContext(runner=runner, platform=platform,
                                      resolve_release=release_resolver(resolve_tag)))
    return result.warnings
# add: if method.kind == "cargo_distrobox": return cargo_distrobox.update(method, ctx)  (rebuild + swap + re-record)
```
**Version source:** `installer/version_status.py:275-286` skips every kind but `github_release`:
```python
for method in resolve_methods(tool, platform):
    if method.kind != "github_release":
        continue
    repo = method.params.get("repo")
    if isinstance(repo, str) and repo:
        return method, repo
```
Accept `cargo_distrobox` too (its `repo` is the same slug shape). Guard the adoption path (~:1309, assumes `resolve_target`/`raw`) by kind.

**Replaceable-callable seam for `podman image exists`:** follow the module-level replaceable precedent `launch_puppeteer` (`installer/executors.py:356-358`), e.g. `image_exists: Callable[[str], bool]`; tests monkeypatch it (sandbox forbids real `podman`).

**Runner conventions:** `Runner = Callable[[list[str]], None]` (`installer/run.py:18`), no timeout/env: use argv prefixes `timeout --kill-after=10 <s>` and `env XDG_CACHE_HOME=<tmp>/cache` (RESEARCH Pattern 1, Pitfall 7). Argv recipe, box name `f"ti-cargo-{tool}-{os.getpid()}-{secrets.token_hex(4)}"`, the `try/finally` order (`distrobox rm --force --rm-home`, then `podman rmi` only if the run pulled the image, never `--force`, then `shutil.rmtree(tmp, ignore_errors=True)`) and tag validation (`^[A-Za-z0-9._-]+$`, not leading `-`, `--` before the URL) are in 24-RESEARCH.md Pattern 1 and Code Examples: copy from there; no repo analog exists for the argv.

---

### `installer/registry.toml` - herdr entry (config)

**Analog:** `yq` (:490-510), a raw `github_release` per OS:
```toml
[[tool]]
id = "yq"
category = "data"
cmd = "yq"
audience = "ai"
tier = "user"
verified = 2026-11-03
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "mikefarah/yq"
asset = "yq_linux_{arch.deb}"
member = "yq"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "mikefarah/yq"
asset = "yq_darwin_{arch.deb}"
```
herdr: `repo = "herdrdev/herdr"`, `asset = "herdr-linux-{arch.machine}"` / `"herdr-macos-{arch.machine}"`, `member = "herdr"`, `raw = true`, `audience = "both"`, `tier = "user"`, `postinstall = "herdr-integration"`, `config_paths = ["~/.config/herdr", "~/.local/state/herdr"]`, no `checksum` (API digests apply). Add a `# Verified` comment recording the Q8 fail-safe drift (`herdr update` self-replace).

**Copilot** (:1665-1692) is the model for `post_install = ["..."]` plus `recommends`; an `audience = "both"` tool with a hook uses `postinstall = "<hook-name>"` like codegraph's entry.

### `installer/registry.toml` - alacritty entry rewrite

**Analog:** current entry (:2936-2963) keeps `id/name/category/cmd/tier/owner_probes`; replace the comment at :2925-2934 ("Distrobox is not a method kind"), keep the three native methods after the new `cargo_distrobox` method (mutable no-tools hosts fall to the native MANUAL handoff), add `config_paths = ["~/.config/alacritty"]`, `post_install = ["<new terminal tuning action>"]`. Derived method shape (repo/image/packages/artifacts with `~/.terminfo/a/alacritty{,-direct}`) is in 24-RESEARCH.md "Registry entry shape".

---

### `installer/desktop_entry.py` (new; utility, transform)

**Analog:** `terminal_shell._safe_executable` (:122-129) for path posture; single-purpose pure-module precedent (`zshenv_block` :310). Copy:
```python
def _safe_executable(path: str | None) -> str | None:
    if path is None:
        return None
    if not path or not Path(path).is_absolute():
        raise TerminalShellError("discovered executable path must be absolute")
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        raise TerminalShellError("discovered executable path contains a control character")
    return path
```
Raise a module error on relative/control-character paths; quote `Exec`/`TryExec` per the Desktop Entry rule (RESEARCH Pitfall 12, A4 assumed); write through `atomic_write_text` (see `installer/atomic.py`). Pure function `render(binary: Path, icon: Path) -> str`; no I/O in the renderer so tests are golden-text.

---

### `installer/terminal_shell.py` - Alacritty and herdr branches (service, guarded region)

**Analog:** kitty/WezTerm branches in `sync_terminal_shells` (:529-564) and helpers `_marker`/`_replace_owned_region` (:79-119), `_write_if_changed` (:292), `_remove_if_owned` (:250), `_revert_terminal_shells` (:445-466). Core copy (kitty):
```python
if _safe_executable(lookup("kitty")) is None:
    skipped.append("kitty unavailable")
else:
    config_path = _kitty_config_path(home, environ)
    updated = _replace_owned_region(
        _read_text(config_path), "kitty",
        f"shell {shlex.join((zsh_path, '-l'))}\nenv SHELL={zsh_path}",
    )
    if _write_if_changed(config_path, updated, write=write):
        drifted.append("kitty")
    configured.append("kitty")
    paths.append(("kitty", config_path))
```
Alacritty: same gate on `lookup("alacritty")`; config path is the first existing of the three XDG locations (shape of `_wezterm_config_path` :146); region name `"alacritty"` (shell only: `[terminal.shell]` table form + guarded `[env]`); TOML guard = parse content OUTSIDE the region with `tomllib`, on conflict write nothing and add `warnings.append("alacritty: partial: you already define terminal.shell")` (WezTerm's `warnings.append("wezterm: unsupported return shape")` at :559 is the shape); after the write `tomllib.loads` and restore the old text on failure. Keybindings use a second region name `"alacritty-keys"` (separate marker text) written by post_install, NOT here (D-23).

Revert: extend `_revert_terminal_shells` the way kitty/wezterm are removed (:458-463): `_remove_if_owned(alacritty_path, "alacritty")` (+ `"alacritty-keys"` for the removal-of-tool path). `_remove_if_owned` leaves an empty file, hence the `config_paths` entry.

herdr: gate on both `herdr` and zsh via `_safe_executable(lookup(...))`; absent-only `terminal.default_shell` through the nested-key TOML writer (see `agent_settings` row); ledger entry; reload via an injected runner parameter on `sync_terminal_shells` (23.1 forbids a real `herdr` in unit tests). Branch-removal on tool removal goes through `app._after_removal`.

---

### `installer/post_install.py` - Alacritty keybindings tuning action (service, file-I/O)

**Analog:** `_tune_omz_plugins` (:212-227) for "write once, skip when recorded, one-line refusal", and the dispatcher/table (:281-310):
```python
POST_INSTALL_HOOKS: dict[str, PostInstallAction] = {
    "set_login_shell": _set_login_shell, ..., "apply_agent_tuning": _apply_agent_tuning,
}
def apply_install_tuning(tool, platform, *, skip_recorded):
    for name in tool.post_install:
        if name == "apply_agent_tuning": ...
        elif name == "set_omz_plugins":
            produced = _tune_omz_plugins(skip_recorded=skip_recorded)
            lines.extend(produced.lines); refused = refused or produced.refused
```
Add (1) the action name to `model.POST_INSTALL_ACTIONS` (:125-133), (2) a `_tune_terminal(...)` returning `PostInstallOutput(lines, refused=reason)`, (3) an `_apply_...` wrapper with `skip_recorded=False`, (4) an `elif name == ...` branch in `apply_install_tuning`, (5) a pending-fact branch in `version_status._tuning_fact` (:~652) and the matching `session._install_tuning_step`, (6) a revert in `app._after_removal`. The "written once" record has no analog for a file region: copy the Konsole state-file precedent in `terminal_shell.py` (`terminal-shell-konsole-default` under `_xdg_data_home`, :141) as `terminal-tuning-alacritty`, written after the region and deleted on removal. Use `terminal_shell._replace_owned_region(content, "alacritty-keys", body)` for the region body and the guard from the Alacritty branch above.

---

### `installer/postinstall.py` - herdr hook extension (service, event-driven)

**Analog:** same file. Extend the map and the host ids, keep the `HookPair` shape:
```python
HOST_CATALOG_IDS: dict[str, str] = {"claude": "claude", "codex": "codex", "opencode": "opencode",
                                    "cursor": "cursor-agent"}               # :29-34 -> add pi, copilot
_HERDR_TARGETS: Mapping[str, str] = {"claude": "claude", "codex": "codex",
                                     "opencode": "opencode", "cursor": "cursor"}   # :196-201
def _herdr_register(method, runner, harnesses):                              # :204-216
    binary = _resolve_binary(method, "herdr")
    done, failures = [], []
    for harness in harnesses:
        try:
            runner([binary, "integration", "install", _HERDR_TARGETS[harness]])
        except CommandError as exc:
            failures.append(f"{harness}: {command_error_line(exc)}")
        else:
            done.append(harness)
    return tuple(done), "; ".join(failures) or None
def _herdr_unregister(binary, harnesses):                                    # :219-220
    return tuple((binary, "integration", "uninstall", _HERDR_TARGETS[h]) for h in harnesses)
```
D-21: add pi, copilot, kilo, kimi, qwen, devin, grok, hermes, `factory-droid -> droid`; comment the omitted `antigravity`/`gemini-cli`. D-27: before each install run a read-only status probe (a query callable seam, since `Runner` returns `None`; regex in RESEARCH "Integration status parse") and only append to `done` hosts that were `not installed`/`needs repair`; a `current` host goes to the warning/"user-owned" text. Sidebar/plugin hook (D-12): a second `HookPair` entry (`targets=None`, `register=...`, `unregister=...`) in `POSTINSTALL_HOOKS` (:246-256), shaped like `tealdeer-cache`'s `targets=None` pair but with an `unregister`; first try `herdr plugin install castocolina/herdr-setup/plugins/workspace-here --ref <sha> --yes` (verify-first task, RESEARCH Q4). Note `_HOST_CATALOG_IDS` is consumed by `session._resync_hooks` (:454-): no code change needed there once the dict grows.

---

### `installer/app.py` - `_after_removal` terminal branch (service)

**Analog:** same function (:679-705); add a branch in the existing style:
```python
if tool.id == "zsh" and platform_os != "macos":
    owned = [p for p in extra_policies if p.id == "desktop-shell" and policy_owned(p)]
    parts.append(sweep_policies(owned))
```
New: `if tool.id in ("alacritty", "herdr"):` call a `terminal_shell` revert helper (strip both Alacritty regions + the tuning state file; remove only the ledgered herdr key if still the written value), append its `SweepResult(...)` to `parts`. Order requirement (D-28): herdr unregisters happen in `removal_plan -> _hook_undo` BEFORE `_after_removal` reverts ledger keys; assert it in a unit test.

---

### `installer/agent_settings.py` - nested TOML keys (utility, file-I/O) (no exact analog)

Existing writer supports only top-level bare keys with str/bool (`_toml_key` raises on `len(key_path) != 1`, `_toml_value` str/bool). Reuse its `_guarded` pattern (parse whole new text with `tomllib`, compare to the expected dict, roll back on mismatch) and extend `_insert_toml`/`_toml_remove` to header-aware insert (after an existing `[a.b]` header, or a new table appended). Never a second header. See RESEARCH Pitfall 4. Match quality role-match only: read the file at plan time for the exact signatures.

---

### `scripts/container-e2e-verify.sh` - `--distro` table and rerun gate (harness, batch)

**Analog:** itself. Current hardcodes to table-ize:
```bash
CONTAINER_NAME="tools-installer-e2e"     # :15  (per-distro name: avoid colliding with a running e2e)
IMAGE="fedora:latest"                    # :16
record_fedora_release() { local release; release="$(exec_root cat /etc/fedora-release)"; printf 'FEDORA_RELEASE=%s\n' "$release"; }   # :117-121
install_root_prereqs() { exec_root dnf install -y @development-tools procps-ng curl file git tar which sudo ca-certificates python3 nodejs chromium; }   # :123-130
```
Replace with `case "$DISTRO" in fedora|debian|arch)` setting `IMAGE`, a `distro_release_record`, and `install_root_prereqs` branches; parse `--distro` in `main()` (:1084-1097) before dispatch and thread it through `cmd_bootstrap/pass1/pass2/all`. Everything else stays shared (D-14/D-31). Constants must remain `^NAME=value$` single-token lines and logic top-level functions, because the host test extracts them by regex (`_constant`, `_function`).

**Rerun gate (D-25):** `accumulate_summaries` (:400-444) accumulates from `PARSE_*` but omits REPAIRED, RECONFIGURED, REINSTALLED:
```bash
ACC_INSTALLED=$((ACC_INSTALLED + PARSE_INSTALLED)) ... ACC_CRASHED=$((ACC_CRASHED + PARSE_CRASHED))
sed -nE 's/^[^ ]+ +([^ ]+) +manual — (see the setup steps in the log|you run: .*)$/\1/p' "$file" >>"$ACC_MANUAL_NAMES_FILE" || true
```
Add three counters (also reset in `cmd_pass2`'s step-1/3 resets :983-987, :1047-1051, and in `_summary_harness` in the test), persist pass 1's sorted-unique manual set to `$PHASE_DIR/pass1-manual.txt` (`ACC_MANUAL_NAMES_FILE` is a `mktemp` deleted today), and a new top-level `rerun_step_ok` function: fail on installed/updated/reconfigured/repaired/reinstalled > 0, and on manual set != pass 1 set. Step 1 in `cmd_pass2` (:988-1002) calls `install_step_ok` then prints `TRACER_RERUN_OK`; add the new gate between them with its own `TRACER_RERUN_UNEXPECTED ...` line (copy the `TRACER_RERUN_INCOMPLETE` printf shape :994-996). Empty-ancestor leftovers (Pitfall 6) are caught by `new_leftovers`/`assert_no_leftovers` (:648-720). Nested-podman target (D-18): a separate `cmd_nested` (or `--target nested`) subcommand, outer `ct run` with `--device /dev/fuse --security-opt label=disable`, removed in a `trap ... EXIT` exactly like `cmd_all` (:1075-1082).

### `tests/test_container_e2e_receipts.py` - harness tests (test, bash-extraction)

**Analog:** itself. Pattern to copy for every new bash function (`rerun_step_ok`, the distro table functions):
```python
def _function(name, text=None):            # :65-70
    match = re.search(rf"^{name}\(\) \{{.*?\n\}}\n", body, re.MULTILINE | re.DOTALL)
def _summary_harness(*names):              # :133-152  extracts SUMMARY_RE + functions, zeroes ACC_* counters
def _summary_run(script, scratch, transcript, command):   # :155-170  writes transcript fixture, runs, prints ACC state
def _run(script, scratch, *, path="/usr/bin:/bin"):       # :173-197  script as a file, HOME=scratch, 30 s timeout
```
Add the three new `ACC_*` initializers to `_summary_harness`'s block (:143-151) and a new test per D-25 case: skipped-only passes, same manual set passes, a manual row not in pass 1 fails, any installed/updated/reconfigured/repaired/reinstalled row fails, empty distro table entry fails. Existing wiring tests (`test_receipt_checks_are_wired_into_the_passes` :460, `test_every_install_step_uses_the_one_gate` :453) show how to assert a function is invoked from `cmd_pass2` by text.

---

### `.claude/skills/tool-onboarding/SKILL.md` (doc)

Anchor on `### 4b.` (do not rely on line numbers; today the false paragraph is `:118-123`). Keep the existing TUNE-04 rule text verbatim (`rg -n "Policies"` shows it at ~:184, 186, 228, 229). Fix line ~57 ("skill packs are not catalog entries since 23.1") and ~134 so `rg -n -i "skill.pack|skill_lifecycle"` finds nothing; update the §7 terminal bullet (~:159-162). Add one example per lifecycle param (`paths`, `remove`, `update`, `writable_prefix`, `config_paths`) and a `cargo_distrobox` row. Test: extend `tests/test_docs.py` (which scans `docs/**/*.md` and the skill).

---

## Shared Patterns

### Guarded config write with rollback
**Source:** `installer/terminal_shell.py` `_replace_owned_region` (:83-119), `_write_if_changed` (:292), `agent_settings._guarded`
**Apply to:** Alacritty shell region, Alacritty keybindings region, herdr `default_shell`, herdr rows/`row_gap`. Pattern: read, splice only the owned span, `tomllib.loads` the whole result, write atomically only if changed, restore on failure; a conflict outside the region means write nothing and surface `≈ partial: you already define X`.

### Receipt/removal authority is one formula
**Source:** `installer/download.py:284` `artifact_paths`; consumers `receipts.record`, `uninstall._receipt_proof`, `uninstall.remove_paths`
**Apply to:** cargo_distrobox artifacts (binary `file`, others `leaf`), herdr raw binary. Never add a second path list for removal.

### Safe executable / no sudo / argv lists
**Source:** `terminal_shell._safe_executable` (:122); AST tests `tests/test_executors.py:148` and `tests/test_model.py:1851` reject argv lists starting `sudo|pkexec|doas`
**Apply to:** `cargo_distrobox.py`, `desktop_entry.py`, every new hook argv. No `sh -c` with data, no `shell=True`.

### Seams, not real binaries, in unit tests
**Source:** `launch_puppeteer` replaceable callable (`installer/executors.py:356-358`); 23.1 sandbox `tests/sandbox.py` forbids `cargo git curl podman docker systemctl` and the new tools
**Apply to:** `image_exists`, herdr status probe, `herdr server reload-config` runner, `desktop-file-validate`/`infocmp` (container step only). Use fake executables under `tmp_path`.

### Hook pair + receipt.hooks
**Source:** `installer/postinstall.py:236-256` (`HookPair`, `POSTINSTALL_HOOKS`), `session._resync_hooks` (:454)
**Apply to:** herdr integrations and the sidebar hook.

### Install tuning, never a Policies row
**Source:** 23.2 TUNE-04 text in SKILL.md; `post_install.apply_install_tuning` (:291-310)
**Apply to:** Alacritty keybindings, herdr tuning. `setup.py` Policies stays at 7 rows.

## No Analog Found

| File / part | Role | Data Flow | Reason |
|---|---|---|---|
| `distrobox`/`podman` argv, box lifecycle in `cargo_distrobox.py` | executor | subprocess | No distrobox/podman code exists; use 24-RESEARCH.md Pattern 1 (source-verified flags) |
| Nested-podman e2e target in `container-e2e-verify.sh` | harness | batch | No nested container target exists; feasibility is an unverified spike (RESEARCH Q6) |
| Nested-key TOML insert (`agent_settings`) | utility | file-I/O | Writer supports top-level str/bool only (Pitfall 4) |
| Written-once record for a file region | state file | file-I/O | Closest is the Konsole default state file; adapt it |

## Metadata

**Analog search scope:** `installer/`, `scripts/`, `tests/test_container_e2e_receipts.py`, `installer/registry.toml`, `.claude/skills/tool-onboarding/`
**Files scanned:** ~14 read (full or ranged), 1 scratch grep script (`p24-grep.sh`)
**Tracked-source gate:** all named analogs are under tracked trees (`installer/`, `scripts/`, `tests/`); no `.gsd/capabilities` mirror paths used
**Pattern extraction date:** 2026-11-08
