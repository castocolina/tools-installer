# Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP - Pattern Map

**Mapped:** 2026-11-21
**Files analyzed:** 17 (new or modified)
**Analogs found:** 16 / 17 (all paths below are git-tracked source; excerpts read this session)

Note: the brief named a phase-30 directory; the real directory is this one. Line numbers refer to the working tree at mapping time.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `installer/registry.toml` xcode-clt | config (detect-only entry) | request-response | `oh-my-zsh` (600-625) + `gnu-bash` detect_path (651-672) | role-match |
| `installer/registry.toml` aws-cli | config (script + brew) | request-response | `uv` (63-90) | exact |
| `installer/registry.toml` bruno | config (raw tarball per arch + cask) | file-I/O | `ghostty` (3208-3246) | exact |
| `installer/registry.toml` gh-stack | config (script, fixed argv) | request-response | `uv` paths/update + `herdr-app` tree path (3296) | partial |
| `installer/registry.toml` playwright-mcp | config (bun + hook) | request-response | `pi` (3404-3429), `mmdc` (2795-2812), codegraph hook (1807) | exact |
| `installer/model.py` (script keys `install`, `handoff`, `prefer`; HANDOFF_NAMES; POSTINSTALL_HOOK_NAMES) | model/validator | transform | `METHOD_PARAMS["script"]` (45-62), `remove`/`update` loop (802-811), `ELEVATION_COMMANDS` (549-560) | exact |
| `installer/executors.py` (`_script` argv branch, `needs_manual` handoff table) | service | request-response | `_script` (475-495), `needs_manual` (753-773) | exact |
| `installer/resolve.py` (per-method sort key) | utility | transform | `_RANK` + `resolve_methods` (15-31, 96-99) | exact |
| `installer/ownership.py`, `installer/update.py`, uninstall plan (Xcode refusal, MANAGED row) | service | request-response | `update_refusal` (`update.py` ~343-355, 502-506); `ownership.py:829-849` | role-match |
| `installer/agent_settings.py` (MCP file map, `apply_mcp_server`, revert acceptance) | service | file-I/O | `apply_value` (1055-1078), `AGENT_FORMATS` (613-621) | exact |
| `installer/postinstall.py` (`playwright-mcp-register` HookPair) | service/hook | event-driven | `HookPair` + `POSTINSTALL_HOOKS` (531-570), `register_hooks` (641-675) | exact |
| `installer/app.py` `_after_removal` (MCP revert) | controller | event-driven | `_after_removal` sweep (620-640) | exact |
| `installer/session.py` + `model.py` ConfigStepKind (Claude env consent step) | model/step | request-response | `ConfigStepKind` (`model.py:308-314`), `_run_step` (`session.py:363-380`) | role-match |
| `scripts/container-e2e-verify.sh` (`cmd_aws_cli`, `cmd_playwright_mcp`, GENERIC_SKIP_TOOLS) | script | batch | `cmd_herdr_app` (3088-3118), `cmd_ghostty` (3050) | exact |
| `tests/e2e_aws_cli_driver.py`, `tests/e2e_playwright_mcp_driver.py` | test driver | batch | `tests/e2e_herdr_app_driver.py` (verdict fns 85-112; main 658-692), `tests/e2e_ghostty_driver.py` | exact |
| `tests/test_container_e2e_aws_cli.py`, `..._playwright_mcp.py` | test | request-response | `tests/test_container_e2e_herdr_app.py` (388-412, 1228-1233) | exact |
| `tests/test_registry.py`, `test_resolve.py`, `test_executors.py`, `test_model.py`, `test_agent_settings.py`, `test_postinstall.py`, `tests/conftest.py` stubs | test | request-response | pins listed in RESEARCH "Registry touch list"; `no_wezterm_show_keys` (`conftest.py:125-133`) | exact |

## Pattern Assignments

### xcode-clt entry (config, detect-only)

**Analog:** `installer/registry.toml` oh-my-zsh 600-625 and gnu-bash 651-672 (absolute `detect_path`).

```toml
[[tool]]
id = "gnu-bash"
cmd = "gnu-bash"            # a probe name nothing creates
...
[[tool.method]]
kind = "brew"
formula = "bash"
os = ["macos"]
detect_path = "/opt/homebrew/bin/bash"
```
oh-my-zsh shows the script method with `detect_path` plus a `# Verified <date>:` comment placed directly above the key it justifies. Use the RESEARCH Entry 1 body (script, `os=["macos"]`, `detect_path=/Library/Developer/CommandLineTools/usr/bin/git`, `writable_prefix`, new `handoff = "xcode-clt"`, no `url`). Test pins: add id to `MACOS_ONLY` (`tests/test_registry.py:800`), a `SCRIPT_LIFECYCLE_DATA` stanza (`:2987-3036`).

### aws-cli entry (config, script before brew)

**Analog:** `installer/registry.toml:63-90` (uv).
```toml
[[tool.method]]
kind = "script"
url = "https://astral.sh/uv/install.sh"
shell = "sh"
bin_dir = "~/.local/bin"
env = { UV_NO_MODIFY_PATH = "1" }
# Verified 2026-11-04: ... `paths` is the two binaries. `update` is `uv self update` ...
paths = ["~/.local/bin/uv", "~/.local/bin/uvx"]
update = ["uv", "self", "update"]
[[tool.method]]
kind = "brew"
formula = "uv"
```
Copy this shape; add `prefer = true`, the env pin `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION = "false"`, `requires = ["unzip"]`, no `config_paths`.

### bruno entry (config, per-arch raw tarball + cask)

**Analog:** `installer/registry.toml:3224-3246` (ghostty).
```toml
[[tool.method]]
kind = "tarball"
os = ["debian", "fedora"]
arch = ["amd64"]
url = ".../v{ver}/Ghostty-{ver}-x86_64.AppImage"
version = "1.4.0"
sha256 = "..."
member = "ghostty"
raw = true
desktop = "com.mitchellh.ghostty"
```
Copy per-arch pairing with Bruno URLs/digests from RESEARCH Entry 3; `desktop` only if the owner amends D-08. Cask method: copy any existing `kind = "cask"` method with `app = "Bruno.app"`.

### gh-stack entry (config)

**Analog:** uv `paths`/`update` (above) and herdr-app tree path (`registry.toml:3296` onward; trailing `/` accepted by `_script_paths_refusal`, `model.py:584`). Use RESEARCH Entry 4 body; `install` is the new key.

### playwright-mcp entry (config, bun + hook)

**Analog:** pi (3404-3429) and mmdc (2795-2812).
```toml
requires = ["bun"]
[[tool.method]]
kind = "bun"
npm_pkg = "@earendil-works/pi-coding-agent"
min_node = "22.19.0"
```
mmdc adds `versions = { puppeteer = "^25" }` (pin map form). Hook declaration copies codegraph's `postinstall = "codegraph-mcp-register"` (`registry.toml:1807`). Add the name to `POSTINSTALL_HOOK_NAMES` (`model.py:21-23`) and `test_only_codegraph_tealdeer_and_herdr_declare_a_postinstall_hook` (`tests/test_registry.py:2243-2251`).

### `installer/model.py` (validator)

**Analog:** same file.
```python
# METHOD_PARAMS["script"] (45-62): add "install", "handoff", "prefer" to the frozenset
# remove/update loop (802-811) - extend the key tuple with "install":
if kind == "script":
    for key in ("remove", "update"):
        if key in params and (
            not _is_argv(params[key], lambda token: _script_token_ok(token) is None)
            or _elevation_head(params[key]) is not None
        ):
            raise ValueError(
                f"tool '{row['id']}': method 'script' key '{key}' "
                f"{_script_refusal(params[key])}"
            )
```
`ELEVATION_COMMANDS = frozenset({"sudo", "pkexec", "doas"})` (551). Layering precedent for a duplicated closed-name set: `model.py:16-23`. Add the closed `HANDOFF_NAMES` the same way; refuse `handoff` with `url/shell/env/args/install/update/remove/paths`; refuse `prefer` unless the tool also declares a `brew` method.

### `installer/executors.py`

**Analog:** same file. `_script` (475-495) ends with `runner(["sh", "-c", script])`; add at the top an `install` list branch that runs `runner([str(t) for t in install])` and returns (no shell). `needs_manual` (753-773) returns `ManualHandoff(f"{why}; you run: \`{command}\`", command)`; add the handoff-name branch BEFORE the `writable_prefix` test (unconditional, R2) reading a code-owned `_HANDOFF_COMMANDS` table beside `_MANUAL_COMMANDS`. Never pass `xcode-select` as a runner argv.

### `installer/resolve.py`

**Analog:** same file (15-31, 96-99). Keep `_RANK` untouched; replace the lambda with a `_sort_key` returning 0 for `m.params.get("prefer") is True`, else `_RANK[m.kind]` (RESEARCH Pattern 3). Pinned tests stay valid (`tests/test_resolve.py:959-985, 1008-1018`; `tests/test_ownership.py:1620-1660`).

### `installer/update.py` / ownership / uninstall (Xcode)

**Analog:** `update_refusal` (bun exact-pin refusal, `update.py:343-355`, returns an `unsupported` status with a detail string). Add a hand-off method refusal there. Ownership already yields `owner="installer"` for a url-less script (`ownership.py:829-849`); uninstall group is MANAGED with empty argv (`version_status.py:2022-2034`). Tests: `tests/test_update.py`, `tests/test_version_status.py -k xcode`.

### `installer/agent_settings.py` (MCP writer)

**Analog:** `apply_value` (1055-1078).
```python
if (agent, setting) not in DYNAMIC_KEYS:
    raise ValueError(f"{agent} {setting} is not a dynamic setting")
(path,) = DYNAMIC_KEYS[(agent, setting)]
return _apply_keys(agent, setting, (SettingKey(path, value),),
    home=home, platform_os=platform_os, environ=environ, skip_recorded=False)
```
Add `apply_mcp_server` with a per-agent MCP-file map (RESEARCH "Per-host MCP files"); allow-list the file and key path in `_agent_files` and `_revert_once` the way `DYNAMIC_KEYS` does. Absent-only insert gives `set_by_you` for an existing `playwright` entry. `AGENT_FORMATS` (613-621) already holds claude json, codex toml, opencode jsonc, cursor-agent json, copilot jsonc. Codex needs its own `[mcp_servers.playwright]` table (Pitfall 6).

### `installer/postinstall.py` (hook)

**Analog:** `POSTINSTALL_HOOKS` (555-570) and `HookPair` (531-553): `HookPair(targets=..., register=..., settled=...)` with `unregister=None` is tolerated (`unregister_hosts`, 580-582). `register_hooks` (641-675) records hosts through `receipts.record_hooks`. Targets map harness id to ledger id (`cursor` to `cursor-agent`, `HOST_CATALOG_IDS`, 40-47). Register function signature: `(method, runner, harnesses) -> HookOutcome` (see `_tealdeer_cache`, 518-528).

### `installer/app.py` `_after_removal`

**Analog:** app.py 620-640. Existing branch:
```python
if tool.id in receipts.CONFIG_AGENTS:
    reverted, kept, warnings = _revert_settings((tool.id,), platform_os=platform_os)
    parts.append(SweepResult(warnings=warnings, settings_reverted=reverted, settings_kept=kept))
```
Add a sibling branch for `playwright-mcp` calling the MCP revert for each recorded host.

### Container targets

**Analog:** `cmd_herdr_app` (`scripts/container-e2e-verify.sh:3088-3118`): option loop with `--keep-image`, `LANDING_CONTAINER_NAME="tools-installer-e2e-<x>-$$"`, `LANDING_DRIVER_MODULE=tests.e2e_<x>_driver`, `PHASE_DIR=$REPO_ROOT/.e2e-artifacts/container-<x>`, `trap landing_teardown EXIT`, `landing_note_image; landing_bootstrap; landing_stage ...; landing_step lifecycle lifecycle || failed=1`. Wire in `main` case (3148 `herdr-app) cmd_herdr_app "$@" ;;`) and `usage()` (line 54). `GENERIC_SKIP_TOOLS=herdr-app` (333) is pinned by `tests/test_container_e2e_herdr_app.py:1228-1233`; edit both together if bruno or playwright-mcp are skipped. `tests/test_shell_scripts_path.py:511-541` `CLASSIFIED` lines shift when usage grows.

### Drivers and host tests

**Analog:** `tests/e2e_herdr_app_driver.py`: pure verdict fns return `TRACER_..._OK` or `verdict(prefix, "; ".join(problems))` (89-110); `accepts`/`main` refuse outside the container (658-692); `_HANDLERS` dict. Host tests: `test_the_verbs_and_the_refusal_outside_the_container` (`tests/test_container_e2e_herdr_app.py:392-407`) and a pinned-orders test. Capture child output through files (Pitfall 11, `run_version`).

### conftest stubs

**Analog:** `tests/conftest.py:125-133`:
```python
@pytest.fixture(autouse=True)
def no_wezterm_show_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(path: Path) -> str | None:
        del path
        return None
    monkeypatch.setattr(terminal_keys, "wezterm_show_keys", unavailable)
```
Any new probe seam (Flatpak Chrome path check, bunx resolver) gets a module-level function and an autouse stub like this.

### Elevation tests

**Analog:** `tests/test_executors.py:151-175`: change `for key in ("remove", "update")` to include `"install"`; extend the AST literal test (`_ELEVATION_WORDS`) with `xcode-select` and `softwareupdate` as first element, plus a text check that `xcode-select --install` occurs only in the hand-off table.

## Shared Patterns

- **Closed names, never strings:** registry names an action; code owns the text (`.claude/architecture.md:337-342`; `model.py:16-23` duplicated name set).
- **Argv validation:** `_is_argv(..., _script_token_ok)` plus `_elevation_head(...) is None` for every argv-valued key.
- **Merge-safe config writes:** `agent_settings._apply_once/_revert_once` (absent-only, `set_by_you`, `CHANGED_WHILE_WRITING`).
- **`# Verified <date>:` comments** directly above the key they justify (uv 77-82, oh-my-zsh 613-621).
- **Test-first in one commit; targeted pytest (`--no-cov -q`)**; pins in RESEARCH "Registry touch list" (counts 89 to 94, tiers, audiences, `_FIRST_METHOD`, lifecycle stanzas).
- **Reachability:** wire any new `installer/*.py` in the same commit (`tests/test_reachability.py`).

## No Analog Found

| File | Role | Reason |
|---|---|---|
| MCP-server file revert for a bun tool | service | No MCP writer exists; hook undo is argv-only and cannot fire for a bun receipt (R10). Use RESEARCH Pattern 4 on the ledger. |

## Metadata

**Analog search scope:** `installer/`, `scripts/container-e2e-verify.sh`, `tests/`, `installer/registry.toml`
**Files read:** about 12 targeted ranges; RESEARCH (full) and CONTEXT
**Pattern extraction date:** 2026-11-21
