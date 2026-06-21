# Catalog Dependencies & Shell Tweaks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inter-tool dependency resolution + a `node` (pnpm) install method to the installer, and four curated, separately-toggleable shell-tweak bundles to the Policies tab — both as pure-core additions through existing seams.

**Architecture:** Two independent workstreams. **B (Shell Tweaks)** mirrors the pip/npm ban exactly: a new `installer/tweaks.py` defines curated `TweakBundle`s written as per-bundle marker blocks into `~/.myshellrc` via `shellrc.apply_block`/`strip_block`, surfaced as generic `Policy` rows through a new `tweak_policy` factory — **zero Policies-screen changes**. **A (Dependencies)** adds `"node"` to the method taxonomy (`pnpm add -g <npm_pkg>`, `npm_pkg` carried in `method.params`), a pure cycle-safe resolver in `installer/deps.py` (transitive drag-in + deps-first topological order + unavailable-skip), wired into `run_wizard`, then a full-catalog audit, the uninstall reverse-dependency warning, and README.

**Tech Stack:** Python 3.12, uv, pytest (+pytest-asyncio for Textual screens), Textual 8.x, ruff/pyright-strict/bandit/vulture. 100% coverage on `installer/`; `setup.py` is the untested IO boundary.

**Sequencing:** Workstream B first (Tasks B1 → B2), then Workstream A (Tasks A1 → A10). These map to the PRD's phases: B1↔B1, B2↔B2; A1–A3 ↔ PRD A1; A4–A5 ↔ PRD A2 (resolver); A6–A7 ↔ PRD A3 (node install); A8–A10 ↔ PRD A4 (audit + UI + docs). Each task ends green on `make validate && make test`.

**Non-negotiables (from CLAUDE.md):** English only; 100% coverage on new `installer/` code; pyright strict, no suppressions; coherent commits; never bare `npm`/`pip`; E2E sandboxes `HOME` via `monkeypatch.setenv("HOME", tmp_path)`.

---

## File Structure

**Workstream B**
- Create `installer/tweaks.py` — `TweakBundle`, curated `BUNDLES`, per-bundle markers, `tweak_block`/`write_tweak`/`remove_tweak`/`tweak_present`, `applicable_bundles(platform)`. Pure; depends only on `shellrc` + `platform`.
- Modify `installer/policy.py` — add `tweak_policy(bundle, *, rc_path)` factory parallel to `ban_policy`.
- Modify `setup.py` (IO boundary) — extend the `PolicyInputs.policies` list with `applicable_bundles`.
- Create `tests/test_tweaks.py`, `tests/test_policy_tweaks.py` (unit), and extend `tests/test_policies_e2e.py` (headless screen toggle).

**Workstream A**
- Modify `installer/model.py` — add `"node"` to `METHOD_KINDS`; validate `node` methods carry `npm_pkg`.
- Modify `installer/resolve.py` — rank + applicability for `"node"`.
- Modify `installer/executors.py` — `_node` executor (`pnpm add -g`).
- Create `installer/deps.py` — `Resolution`, `DependencyCycleError`, `resolve_dependencies(...)`, `requires_integrity_errors(...)`.
- Modify `installer/app.py` — call the resolver inside `run_wizard`; render the drag-in/warnings notice.
- Modify `installer/render.py` — `render_dependency_notice(...)`.
- Modify `installer/uninstall.py` — `reverse_dependencies(tools)` helper + a `reverse_deps` param on `classify_tools` that folds a "required by …" note into `ToolRow.hint` (the Uninstall detail bar already renders `hint`, so no screen change).
- Modify `installer/registry.toml` — `mmdc` node tool + the full-catalog audit data.
- Modify `README.md` — document the `node` kind, `requires`, drag-in, reverse-dep warning, and tweak bundles.
- Create/extend `tests/test_deps.py`, `tests/test_executors.py`, `tests/test_model.py`, `tests/test_resolve.py`, `tests/test_registry.py`, `tests/test_app.py`, `tests/test_render.py`, `tests/test_uninstall.py`, and a node-install E2E.

---

# Workstream B — Shell Tweak Bundles

## Task B1: Tweak core + curated bundles

**Files:**
- Create: `installer/tweaks.py`
- Test: `tests/test_tweaks.py`

- [ ] **Step 1: Write the failing test for bundle definitions + block shape**

Create `tests/test_tweaks.py`:

```python
import shutil
import subprocess
from pathlib import Path

from installer.platform import Platform
from installer.tweaks import (
    BUNDLES,
    TweakBundle,
    applicable_bundles,
    remove_tweak,
    tweak_block,
    tweak_present,
    write_tweak,
)


def _bundle(bundle_id: str) -> TweakBundle:
    return next(b for b in BUNDLES if b.id == bundle_id)


def test_four_bundles_with_stable_ids() -> None:
    assert [b.id for b in BUNDLES] == ["docker", "countdown", "claude-skip", "apt-upgrade"]


def test_block_is_marker_delimited_around_body() -> None:
    bundle = _bundle("claude-skip")
    block = tweak_block(bundle)
    assert block.startswith("# >>> tools-installer tweak:claude-skip >>>\n")
    assert block.endswith("\n# <<< tools-installer tweak:claude-skip <<<")
    assert bundle.body in block


def test_countdown_uses_printf_not_echo_ne() -> None:
    body = _bundle("countdown").body
    assert "printf" in body
    assert "echo -ne" not in body


def test_docker_body_has_all_three_helpers() -> None:
    body = _bundle("docker").body
    assert "docker-ps()" in body
    assert "alias docker-stats=" in body
    assert "alias docker-memory='docker-stats'" in body


def test_every_block_is_valid_posix_sh() -> None:
    # `sh -n` parses without executing; every body must be syntactically valid
    # (the guaranteed-present shell). bash/zsh are checked when available below.
    for bundle in BUNDLES:
        result = subprocess.run(["sh", "-c", f"set -- ; {bundle.body}\n:"], capture_output=True)
        assert result.returncode == 0, f"{bundle.id}: {result.stderr!r}"


def test_blocks_parse_in_bash_and_zsh_when_present(tmp_path: Path) -> None:
    for shell in ("bash", "zsh"):
        binary = shutil.which(shell)
        if binary is None:
            continue
        for bundle in BUNDLES:
            script = tmp_path / f"{bundle.id}.{shell}"
            script.write_text(bundle.body + "\n")
            result = subprocess.run([binary, "-n", str(script)], capture_output=True)
            assert result.returncode == 0, f"{shell} {bundle.id}: {result.stderr!r}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tweaks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.tweaks'`.

- [ ] **Step 3: Write `installer/tweaks.py`**

```python
"""Curated, cross-shell tweak bundles written into ~/.myshellrc as marker blocks.

Mirrors installer.guards' ban exactly: each bundle is one idempotent,
marker-delimited block managed through shellrc.apply_block / strip_block. Bodies
are POSIX (identical in bash and zsh); wait_time uses printf so its escape
sequences behave the same across sh/bash/zsh. Bundles are curated in code (like
guards.BANNED), each surfaced as its own Policy via installer.policy.tweak_policy.
Every block lands in the same ~/.myshellrc the ban uses, so existing shell
sourcing covers it with no extra wiring.
"""

from dataclasses import dataclass
from pathlib import Path

from installer.platform import Platform
from installer.shellrc import apply_block, strip_block


@dataclass(frozen=True)
class TweakBundle:
    """One curated shell snippet. `platforms` is the set of allowed Platform.os
    keys (empty = all); `body` is the snippet with no markers and no trailing
    newline (the block machinery adds them)."""

    id: str
    label: str
    description: str
    platforms: tuple[str, ...]
    body: str


# Raw strings so backslash escapes survive verbatim into the shell file:
# the docker `\t` are Go-template tabs consumed by docker (not shell escapes),
# the sed `\.`/`\[` are regex escapes, and wait_time's `\033`/apt's `\n` must
# reach printf/tr literally.
_DOCKER_BODY = r"""docker-ps() {
    watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | sed "s/0\.0\.0\.0://g; s/\[::\]://g; s|/tcp||g; s|/udp||g"'
}
alias docker-stats='docker stats --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"'
alias docker-memory='docker-stats'"""

_COUNTDOWN_BODY = r"""wait_time() {
    secs=${1:-0}
    while [ "$secs" -gt 0 ]; do
        printf '    WAIT %s\033[0K\r' "$secs"
        sleep 1
        secs=$((secs - 1))
    done
    printf '\033[0K\r'
}"""

_CLAUDE_BODY = "alias claude='claude --dangerously-skip-permissions'"

_APT_BODY = r"""alias apt-upgrade='sudo apt install --only-upgrade $(apt list --upgradeable 2>/dev/null | grep -v "Listing" | cut -d/ -f1 | tr "\n" " ")'"""

# apt-upgrade is gated to Linux (offered on Linux, absent on macOS) per the PRD;
# the alias only errors if actually run on a non-apt distro.
_LINUX = ("debian", "arch", "fedora")

BUNDLES: tuple[TweakBundle, ...] = (
    TweakBundle(
        "docker",
        "Docker shortcuts",
        "docker-ps (live table), docker-stats, docker-memory (needs `watch`)",
        (),
        _DOCKER_BODY,
    ),
    TweakBundle(
        "countdown",
        "Countdown helper",
        "wait_time <secs> — a portable terminal countdown",
        (),
        _COUNTDOWN_BODY,
    ),
    TweakBundle(
        "claude-skip",
        "claude skip-permissions",
        "alias claude='claude --dangerously-skip-permissions'",
        (),
        _CLAUDE_BODY,
    ),
    TweakBundle(
        "apt-upgrade",
        "apt selective upgrade",
        "alias apt-upgrade — upgrade only packages that have updates (Linux)",
        _LINUX,
        _APT_BODY,
    ),
)


def _markers(bundle_id: str) -> tuple[str, str]:
    return (
        f"# >>> tools-installer tweak:{bundle_id} >>>",
        f"# <<< tools-installer tweak:{bundle_id} <<<",
    )


def tweak_block(bundle: TweakBundle) -> str:
    """Marker-delimited block (no trailing newline, like shellrc/guards blocks)."""
    begin, end = _markers(bundle.id)
    return f"{begin}\n{bundle.body}\n{end}"


def write_tweak(bundle: TweakBundle, rc_path: Path) -> None:
    """Idempotently write the bundle's block into rc_path, preserving the rest."""
    begin, end = _markers(bundle.id)
    existing = rc_path.read_text() if rc_path.exists() else ""
    rc_path.write_text(apply_block(existing, tweak_block(bundle), begin=begin, end=end))


def remove_tweak(bundle: TweakBundle, rc_path: Path) -> None:
    """Strip the bundle's block. A missing file or absent block is a no-op."""
    if not rc_path.exists():
        return
    begin, end = _markers(bundle.id)
    original = rc_path.read_text()
    stripped = strip_block(original, begin, end)
    if stripped != original:
        rc_path.write_text(stripped)


def tweak_present(bundle: TweakBundle, rc_path: Path) -> bool:
    """True when rc_path exists and carries the bundle's begin marker."""
    if not rc_path.exists():
        return False
    begin, _ = _markers(bundle.id)
    return begin in rc_path.read_text().split("\n")


def applicable_bundles(platform: Platform) -> tuple[TweakBundle, ...]:
    """Bundles offered on this platform (empty `platforms` = every platform)."""
    return tuple(b for b in BUNDLES if not b.platforms or platform.os in b.platforms)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tweaks.py -q`
Expected: PASS.

- [ ] **Step 5: Add idempotency + gating tests**

Append to `tests/test_tweaks.py`:

```python
def test_write_then_present_then_remove_roundtrip(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("countdown")
    assert tweak_present(bundle, rc) is False
    write_tweak(bundle, rc)
    assert tweak_present(bundle, rc) is True
    assert "wait_time()" in rc.read_text()
    remove_tweak(bundle, rc)
    assert tweak_present(bundle, rc) is False
    assert "wait_time()" not in rc.read_text()


def test_re_enable_does_not_duplicate(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    bundle = _bundle("claude-skip")
    write_tweak(bundle, rc)
    write_tweak(bundle, rc)
    assert rc.read_text().count("# >>> tools-installer tweak:claude-skip >>>") == 1


def test_toggling_one_bundle_leaves_another_and_user_content_intact(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    rc.write_text("export EDITOR=vim\n")
    write_tweak(_bundle("docker"), rc)
    write_tweak(_bundle("countdown"), rc)
    remove_tweak(_bundle("docker"), rc)
    text = rc.read_text()
    assert "export EDITOR=vim" in text          # user content untouched
    assert "wait_time()" in text                # the other bundle untouched
    assert "docker-ps()" not in text            # only docker removed


def test_remove_on_missing_file_is_noop(tmp_path: Path) -> None:
    remove_tweak(_bundle("docker"), tmp_path / "nope")  # must not raise


def _platform(os_name: str) -> Platform:
    return Platform(os=os_name, arch="arm64", immutable=False, has_brew=False)


def test_apt_upgrade_offered_on_linux_absent_on_macos() -> None:
    linux_ids = [b.id for b in applicable_bundles(_platform("debian"))]
    macos_ids = [b.id for b in applicable_bundles(_platform("macos"))]
    assert "apt-upgrade" in linux_ids
    assert "apt-upgrade" not in macos_ids
    # The cross-platform bundles are always present.
    assert {"docker", "countdown", "claude-skip"} <= set(macos_ids)
```

- [ ] **Step 6: Run to verify all pass**

Run: `uv run pytest tests/test_tweaks.py -q`
Expected: PASS.

- [ ] **Step 7: Validate + commit**

Run: `make validate && uv run pytest tests/test_tweaks.py -q`
Expected: all gates pass, tests green.

```bash
git add installer/tweaks.py tests/test_tweaks.py
git commit -m "$(printf 'feat: curated cross-shell tweak bundles core\n\nFour POSIX bundles (docker/countdown/claude-skip/apt-upgrade) as per-bundle\nmarker blocks reusing shellrc.apply_block/strip_block; wait_time uses printf\nfor bash/zsh parity; apt-upgrade gated to Linux.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task B2: `tweak_policy` factory + Policies-tab wiring

**Files:**
- Modify: `installer/policy.py`
- Modify: `setup.py:186-196` (the `PolicyInputs(...)` block) and its imports
- Test: `tests/test_policy_tweaks.py` (new), `tests/test_policies_e2e.py` (extend)

- [ ] **Step 1: Write the failing test for `tweak_policy`**

Create `tests/test_policy_tweaks.py`:

```python
from pathlib import Path

import pytest

from installer.policy import Policy, PolicyResult, tweak_policy
from installer.tweaks import BUNDLES


def _bundle(bundle_id: str):
    return next(b for b in BUNDLES if b.id == bundle_id)


def test_tweak_policy_metadata_and_id_namespacing(tmp_path: Path) -> None:
    policy = tweak_policy(_bundle("docker"), rc_path=tmp_path / ".myshellrc")
    assert isinstance(policy, Policy)
    assert policy.id == "tweak:docker"          # namespaced so it never collides with "ban"
    assert policy.label == "Docker shortcuts"
    assert "docker-ps" in policy.description


def test_tweak_policy_inactive_then_active_after_apply(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    assert tweak_policy(_bundle("countdown"), rc_path=rc).active is False
    tweak_policy(_bundle("countdown"), rc_path=rc).apply()
    # active is read at construction, so build a fresh policy to observe the change.
    assert tweak_policy(_bundle("countdown"), rc_path=rc).active is True


def test_apply_writes_block_and_returns_result(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    result = tweak_policy(_bundle("countdown"), rc_path=rc).apply()
    assert isinstance(result, PolicyResult)
    assert "wait_time()" in rc.read_text()
    assert result.layers[0].name == "Countdown helper"
    assert str(rc) in result.layers[0].detail
    assert result.reload_hint is not None and "hash -r" in result.reload_hint
    assert result.warning is None


def test_remove_strips_block(tmp_path: Path) -> None:
    rc = tmp_path / ".myshellrc"
    policy = tweak_policy(_bundle("claude-skip"), rc_path=rc)
    policy.apply()
    result = policy.remove()
    assert "claude --dangerously-skip-permissions" not in rc.read_text()
    assert "cleared" in result.layers[0].detail


def test_remove_is_idempotent_on_clean_machine(tmp_path: Path) -> None:
    result = tweak_policy(_bundle("docker"), rc_path=tmp_path / ".myshellrc").remove()
    assert isinstance(result, PolicyResult)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_policy_tweaks.py -q`
Expected: FAIL — `ImportError: cannot import name 'tweak_policy'`.

- [ ] **Step 3: Add `tweak_policy` to `installer/policy.py`**

Add this import near the top of `installer/policy.py` (after the `guards` import block):

```python
from installer.tweaks import TweakBundle, remove_tweak, tweak_present, write_tweak
```

Add at the end of `installer/policy.py`:

```python
def tweak_policy(bundle: TweakBundle, *, rc_path: Path) -> Policy:
    """A curated shell-tweak bundle as a Policy, parallel to ban_policy.

    apply writes the bundle's marker block into rc_path; remove strips it. `active`
    is "the bundle's block is present in rc_path". Idempotent (reuses tweaks'
    block machinery). The id is namespaced `tweak:<id>` so it never collides with
    the ban or another bundle in the Policies tab.
    """

    def _apply() -> PolicyResult:
        write_tweak(bundle, rc_path)
        return PolicyResult(
            layers=(PolicyLayer(bundle.label, f"written to {_display_path(rc_path)}"),),
            reload_hint=_RELOAD_HINT,
            warning=None,
        )

    def _remove() -> PolicyResult:
        remove_tweak(bundle, rc_path)
        return PolicyResult(
            layers=(PolicyLayer(bundle.label, f"cleared from {_display_path(rc_path)}"),),
            reload_hint=_RELOAD_HINT,
            warning=None,
        )

    return Policy(
        id=f"tweak:{bundle.id}",
        label=bundle.label,
        description=bundle.description,
        active=tweak_present(bundle, rc_path),
        apply=_apply,
        remove=_remove,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_policy_tweaks.py tests/test_policy.py -q`
Expected: PASS (the ban tests still pass — no behavior changed there).

- [ ] **Step 5: Extend the headless Policies E2E with a tweak toggle**

First inspect the existing harness to mirror it exactly:

Run: `sed -n '1,60p' tests/test_policies_e2e.py`

Append a test that drives the real `PoliciesScreen` with a tweak policy under a sandboxed HOME. Adapt the screen-construction/pilot boilerplate to match what `sed` showed (the host app + `run_test` pattern already used in that file); the assertions below are the contract:

```python
import pytest

from installer.policy import tweak_policy
from installer.tweaks import BUNDLES
from installer.wizard_app import PoliciesScreen, PolicyInputs


def _countdown():
    return next(b for b in BUNDLES if b.id == "countdown")


@pytest.mark.asyncio
async def test_policies_screen_toggles_a_tweak_bundle_live(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = tmp_path / ".myshellrc"
    inputs = PolicyInputs(policies=[tweak_policy(_countdown(), rc_path=rc)])
    screen = PoliciesScreen(inputs)
    app = _host_app(screen)  # use the same host-app helper the file already defines
    async with app.run_test() as pilot:
        await pilot.pause()
        assert screen.active_state["tweak:countdown"] is False
        await pilot.press("enter")          # toggle the (only, focused) policy on
        await pilot.pause()
        assert screen.active_state["tweak:countdown"] is True
        assert "wait_time()" in rc.read_text()
        await pilot.press("enter")          # toggle off
        await pilot.pause()
        assert "wait_time()" not in rc.read_text()
```

If the existing file builds the host app inline rather than via a helper, build it the same inline way instead of `_host_app(screen)` — the point is to drive the real `PoliciesScreen` through `run_test`, asserting `screen.active_state["tweak:countdown"]` and the on-disk block.

- [ ] **Step 6: Run the E2E**

Run: `uv run pytest tests/test_policies_e2e.py -q`
Expected: PASS.

- [ ] **Step 7: Wire the bundles into `setup.py` (untested IO boundary)**

In `setup.py`, extend the existing imports:

```python
from installer.policy import ban_policy, tweak_policy
from installer.tweaks import applicable_bundles
```

Replace the `policy_inputs = PolicyInputs(...)` block (currently `setup.py:186-196`) with:

```python
    policy_inputs = PolicyInputs(
        policies=[
            ban_policy(
                shim_dir=_DEFAULT_BIN_DIR,
                apply_rc_paths=_ban_rc_paths(link_mode),
                remove_rc_paths=_all_ban_rc_paths(),
                path_value=os.environ.get("PATH", ""),
                which=shutil.which,
            ),
            *(tweak_policy(bundle, rc_path=_MYSHELLRC) for bundle in applicable_bundles(platform)),
        ]
    )
```

All tweaks target `_MYSHELLRC` (the same file as the ban). The `PoliciesScreen` renders `Policy` instances generically — no screen code changes.

- [ ] **Step 8: Smoke-check the wiring renders**

Run: `printf 'q\n' | uv run python setup.py --guard 2>/dev/null; echo "exit=$?"`

This opens the Policies view and immediately quits. Expected: exits cleanly (the app composes the ban + tweak rows without error). If it errors on composition, the policy ids likely collided — confirm each `tweak:<id>` is unique.

- [ ] **Step 9: Validate + commit**

Run: `make validate && make test`
Expected: all gates pass; full suite green at 100% coverage.

```bash
git add installer/policy.py setup.py tests/test_policy_tweaks.py tests/test_policies_e2e.py
git commit -m "$(printf 'feat: shell-tweak bundles as toggleable policies\n\ntweak_policy factory parallel to ban_policy; setup.py adds one Policy per\napplicable_bundles(platform), all targeting ~/.myshellrc. Policies screen\nrenders them generically — no screen changes.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

**Workstream B is complete: four discoverable, separately-toggleable tweak bundles; the ban is unaffected.**

---

# Workstream A — Tool Dependencies & Node-Package Installs

> **Design note (refines the PRD wording):** the PRD says "Add `npm_pkg: str = ""` to `Tool`". Executors only ever receive a `Method` (`engine._perform` → `executors.execute(method, runner)`), and every other method-specific datum (`url`, `formula`, `cask`, `bin_dir`, `asset`) lives in `method.params`. So `npm_pkg` is carried as a **method param**, not a `Tool` field — this avoids threading `Tool` through `engine`/`download`/`apps`. `Tool.requires` stays a `Tool` field (already present). No new `Tool` field is added.

## Task A1: Model & registry — the `node` method kind

**Files:**
- Modify: `installer/model.py:7-18` (`METHOD_KINDS`) and `load_tools`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_model.py`:

```python
def test_node_kind_parses_with_npm_pkg(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "mmdc"
category = "diagram"
cmd = "mmdc"
requires = ["pnpm"]
[[tool.method]]
kind = "node"
npm_pkg = "@mermaid-js/mermaid-cli"
""",
    )
    tools = load_tools(manifest)
    method = tools[0].methods[0]
    assert method.kind == "node"
    assert method.params["npm_pkg"] == "@mermaid-js/mermaid-cli"


def test_node_method_without_npm_pkg_is_a_config_error(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path,
        """
[[tool]]
id = "broken"
category = "diagram"
[[tool.method]]
kind = "node"
""",
    )
    with pytest.raises(ValueError, match="node.*npm_pkg"):
        load_tools(manifest)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_model.py -k node -q`
Expected: FAIL — `unknown method kind 'node'`.

- [ ] **Step 3: Add `"node"` to the taxonomy + validate `npm_pkg`**

In `installer/model.py`, add `"node"` to `METHOD_KINDS` (place it after `"script"`):

```python
METHOD_KINDS = (
    "script",
    "node",
    "github_release",
    "tarball",
    "app",
    "dnf",
    "apt",
    "pacman",
    "rpm_ostree",
    "brew",
    "cask",
)
```

In `load_tools`, immediately after `params = {k: v for k, v in entry.items() if k not in ("kind", "os", "arch")}` and before `methods.append(...)`, add:

```python
            if kind == "node":
                npm_pkg = params.get("npm_pkg")
                if not isinstance(npm_pkg, str) or not npm_pkg:
                    raise ValueError(
                        f"tool '{row['id']}': method 'node' requires a non-empty 'npm_pkg'"
                    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_model.py -q`
Expected: PASS.

- [ ] **Step 5: Validate + commit**

Run: `make validate && uv run pytest tests/test_model.py -q`

```bash
git add installer/model.py tests/test_model.py
git commit -m "$(printf 'feat: node method kind with npm_pkg validation\n\nAdd node to METHOD_KINDS; load_tools rejects a node method missing npm_pkg.\nnpm_pkg rides in method.params (executors only see Method).\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A2: Resolver applicability + ranking for `node`

**Files:**
- Modify: `installer/resolve.py:8-19` (`_RANK`) and `_applies`
- Test: `tests/test_resolve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resolve.py`:

```python
def test_node_is_userspace_ranked_before_brew():
    platform = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    tool = _tool("brew", "node")
    assert [m.kind for m in resolve_methods(tool, platform)] == ["node", "brew"]


def test_node_applies_on_every_platform():
    for os_name in ("debian", "arch", "fedora", "macos"):
        platform = Platform(os=os_name, arch="amd64", immutable=False, has_brew=False)
        assert [m.kind for m in resolve_methods(_tool("node"), platform)] == ["node"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_resolve.py -k node -q`
Expected: FAIL — `KeyError: 'node'` (in the `_RANK` sort).

- [ ] **Step 3: Rank + applicability**

In `installer/resolve.py`, add `"node": 20` to `_RANK` (next to `github_release`):

```python
_RANK = {
    "script": 10,
    "node": 20,
    "github_release": 20,
    "tarball": 20,
    "app": 20,
    "dnf": 30,
    "apt": 30,
    "pacman": 30,
    "rpm_ostree": 35,
    "brew": 40,
    "cask": 40,
}
```

In `_applies`, add `"node"` to the always-applicable userspace tuple:

```python
    if kind in ("script", "node", "github_release", "tarball", "app"):
        return True
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_resolve.py -q`
Expected: PASS.

- [ ] **Step 5: Validate + commit**

```bash
git add installer/resolve.py tests/test_resolve.py
git commit -m "$(printf 'feat: rank node as a userspace install method\n\nnode ranks alongside github_release (before brew) and applies on every\nplatform.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A3: Node executor (`pnpm add -g`)

**Files:**
- Modify: `installer/executors.py:80-87` (`EXECUTORS`)
- Test: `tests/test_executors.py`

- [ ] **Step 1: Write the failing test**

First check the runner-capture pattern this file already uses:

Run: `sed -n '1,40p' tests/test_executors.py`

Append a test using the same recording-runner style the file establishes:

```python
def test_node_runs_pnpm_add_global_never_bare_npm():
    calls: list[list[str]] = []
    method = Method(kind="node", params={"npm_pkg": "@mermaid-js/mermaid-cli"})
    execute(method, calls.append)
    assert calls == [["pnpm", "add", "-g", "@mermaid-js/mermaid-cli"]]
    assert all("npm" != arg for call in calls for arg in call[:1])  # never bare `npm`


def test_node_without_npm_pkg_raises_executor_error():
    with pytest.raises(ExecutorError, match="npm_pkg"):
        execute(Method(kind="node", params={}), lambda _cmd: None)
```

Ensure the test file imports `Method`, `execute`, `ExecutorError`, and `pytest` (mirror the existing imports shown by `sed`).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_executors.py -k node -q`
Expected: FAIL — `no executor for method kind 'node'`.

- [ ] **Step 3: Add the `_node` executor**

In `installer/executors.py`, add after `_script`:

```python
def _node(method: Method, runner: Runner) -> None:
    # pnpm only — bare npm is banned. `add -g` installs the package's CLI globally.
    runner(["pnpm", "add", "-g", require_str(method, "npm_pkg")])
```

Register it in `EXECUTORS` (after `"script": _script,`):

```python
    "node": _node,
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_executors.py -q`
Expected: PASS.

- [ ] **Step 5: Validate + commit**

```bash
git add installer/executors.py tests/test_executors.py
git commit -m "$(printf 'feat: node executor installs via pnpm add -g\n\nReads npm_pkg from method.params; never invokes bare npm.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A4: Pure dependency resolver

**Files:**
- Create: `installer/deps.py`
- Test: `tests/test_deps.py`

This is the core. The resolver: (1) computes the transitive closure of `selected` over `requires`; (2) drops any branch whose required tool is **unavailable on the platform and not already installed**, warning and skipping every dependent of it; (3) returns a stable, **deps-first** order with a cycle detector that raises `DependencyCycleError`.

- [ ] **Step 1: Write the failing tests (closure + drag-in + diamond + order)**

Create `tests/test_deps.py`:

```python
import pytest

from installer.deps import DependencyCycleError, Resolution, resolve_dependencies
from installer.model import Method, Tool


def _tool(tool_id: str, *requires: str) -> Tool:
    return Tool(
        id=tool_id,
        name=tool_id,
        category="c",
        cmd=tool_id,
        methods=(Method(kind="node", params={"npm_pkg": f"@x/{tool_id}"}),),
        requires=tuple(requires),
    )


def _resolve(selected, catalog, *, available_ids=None, installed_ids=()):
    ids = {t.id for t in catalog} if available_ids is None else set(available_ids)
    return resolve_dependencies(
        selected,
        catalog,
        available=lambda t: t.id in ids,
        is_installed=lambda t: t.id in set(installed_ids),
    )


def test_no_requires_returns_selection_unchanged() -> None:
    a, b = _tool("a"), _tool("b")
    result = _resolve([a, b], [a, b])
    assert isinstance(result, Resolution)
    assert [t.id for t in result.order] == ["a", "b"]
    assert result.dragged_in == ()
    assert result.warnings == ()


def test_missing_dependency_is_dragged_in() -> None:
    pnpm = _tool("pnpm")
    mmdc = _tool("mmdc", "pnpm")
    result = _resolve([mmdc], [mmdc, pnpm])
    assert "pnpm" in result.dragged_in
    assert [t.id for t in result.order] == ["pnpm", "mmdc"]  # dependency first


def test_already_installed_dependency_is_not_dragged_in() -> None:
    pnpm = _tool("pnpm")
    mmdc = _tool("mmdc", "pnpm")
    result = _resolve([mmdc], [mmdc, pnpm], installed_ids=["pnpm"])
    assert result.dragged_in == ()
    assert [t.id for t in result.order] == ["mmdc"]


def test_transitive_chain_orders_deepest_first() -> None:
    a = _tool("a", "b")
    b = _tool("b", "c")
    c = _tool("c")
    result = _resolve([a], [a, b, c])
    assert [t.id for t in result.order] == ["c", "b", "a"]


def test_diamond_installs_shared_dep_once_before_dependents() -> None:
    d = _tool("d")
    b = _tool("b", "d")
    c = _tool("c", "d")
    a = _tool("a", "b", "c")
    order = [t.id for t in _resolve([a], [a, b, c, d]).order]
    assert order.index("d") < order.index("b") < order.index("a")
    assert order.index("d") < order.index("c") < order.index("a")
    assert order.count("d") == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_deps.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'installer.deps'`.

- [ ] **Step 3: Write `installer/deps.py` (closure + topo order)**

```python
"""Pure dependency resolution: transitive drag-in + deps-first topological order.

Mirrors uzkit's engine (with_required / order_for_install) but adds two things
the PRD requires: a cycle is REPORTED (DependencyCycleError), not silently
broken; and a dependency that is unavailable on this platform (and not already
installed) is dropped with a warning, skipping every tool that transitively
needs it. Availability and install-state are injected so the module stays pure
and terminal-free.
"""

from collections.abc import Callable
from dataclasses import dataclass

from installer.model import Tool


class DependencyCycleError(ValueError):
    """A `requires` cycle was found — a registry/config error, never a hang."""


@dataclass(frozen=True)
class Resolution:
    """order: deps-first install order. dragged_in: ids auto-added (not selected).
    warnings: human-readable notices (drag-ins, and skipped unavailable deps)."""

    order: tuple[Tool, ...]
    dragged_in: tuple[str, ...]
    warnings: tuple[str, ...]


def resolve_dependencies(
    selected: list[Tool],
    catalog: list[Tool],
    *,
    available: Callable[[Tool], bool],
    is_installed: Callable[[Tool], bool],
) -> Resolution:
    """Expand `selected` with its transitive `requires`, order deps-first, and
    drop branches blocked by an unavailable dependency.

    `selected` is consumed in its given order; pass it pre-sorted (e.g. by
    priority) and independents keep that order — a dependency is only ever moved
    earlier than a tool that needs it.
    """
    by_id = {t.id: t for t in catalog}
    selected_ids = {t.id for t in selected}

    # 1. Transitive closure over requires, preserving first-seen order.
    wanted: list[Tool] = []
    seen: set[str] = set()
    warnings: list[str] = []

    def collect(tool: Tool) -> None:
        if tool.id in seen:
            return
        seen.add(tool.id)
        wanted.append(tool)
        for dep_id in tool.requires:
            dep = by_id.get(dep_id)
            if dep is None:
                warnings.append(f"{tool.id} requires unknown tool '{dep_id}' — ignored")
                continue
            collect(dep)

    for tool in selected:
        collect(tool)

    # 2. Identify blocked tools: a dep that is unavailable here AND not installed
    #    cannot be provided; it and every (transitive) dependent are skipped.
    blocked: set[str] = set()

    def is_blocked(tool: Tool) -> bool:
        if tool.id in blocked:
            return True
        unsatisfiable = not available(tool) and not is_installed(tool)
        dep_blocked = any(
            (dep := by_id.get(dep_id)) is not None and is_blocked(dep)
            for dep_id in tool.requires
        )
        if unsatisfiable or dep_blocked:
            blocked.add(tool.id)
            return True
        return False

    for tool in wanted:
        if is_blocked(tool):
            if not available(tool) and not is_installed(tool):
                warnings.append(f"{tool.id} is not available on this platform — skipped")
            else:
                warnings.append(f"{tool.id} skipped — a dependency is unavailable")

    runnable = [t for t in wanted if t.id not in blocked]

    # 3. Deps-first topological sort over `runnable`, cycle-detecting.
    ordered: list[Tool] = []
    placed: set[str] = set()
    visiting: set[str] = set()
    runnable_ids = {t.id for t in runnable}

    def visit(tool: Tool) -> None:
        if tool.id in placed:
            return
        if tool.id in visiting:
            raise DependencyCycleError(f"dependency cycle involving '{tool.id}'")
        visiting.add(tool.id)
        for dep_id in tool.requires:
            if dep_id in runnable_ids:
                visit(by_id[dep_id])
        visiting.discard(tool.id)
        placed.add(tool.id)
        ordered.append(tool)

    for tool in runnable:
        visit(tool)

    dragged_in = tuple(t.id for t in ordered if t.id not in selected_ids)
    return Resolution(order=tuple(ordered), dragged_in=dragged_in, warnings=tuple(warnings))
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_deps.py -q`
Expected: PASS.

- [ ] **Step 5: Add the cycle + unavailable-skip + unknown-id tests**

Append to `tests/test_deps.py`:

```python
def test_cycle_raises_config_error_not_hang() -> None:
    a = _tool("a", "b")
    b = _tool("b", "a")
    with pytest.raises(DependencyCycleError):
        _resolve([a], [a, b])


def test_unavailable_dependency_skips_dependent_with_warning() -> None:
    dep = _tool("dep")
    user = _tool("user", "dep")
    # dep is in the catalog but not available on this platform and not installed.
    result = _resolve([user], [user, dep], available_ids=["user"])
    assert [t.id for t in result.order] == []          # both skipped
    assert any("not available" in w for w in result.warnings)


def test_unavailable_but_installed_dependency_is_fine() -> None:
    dep = _tool("dep")
    user = _tool("user", "dep")
    result = _resolve(
        [user], [user, dep], available_ids=["user"], installed_ids=["dep"]
    )
    # dep already installed → not blocked, not re-installed, user proceeds.
    assert [t.id for t in result.order] == ["user"]
    assert result.warnings == ()


def test_unknown_required_id_warns_and_continues() -> None:
    user = _tool("user", "ghost")
    result = _resolve([user], [user])
    assert [t.id for t in result.order] == ["user"]
    assert any("unknown tool 'ghost'" in w for w in result.warnings)
```

- [ ] **Step 6: Run to verify all pass**

Run: `uv run pytest tests/test_deps.py -q`
Expected: PASS.

- [ ] **Step 7: Validate + commit**

Run: `make validate && uv run pytest tests/test_deps.py -q`

```bash
git add installer/deps.py tests/test_deps.py
git commit -m "$(printf 'feat: pure cycle-safe dependency resolver\n\nTransitive drag-in, deps-first topological order, cycle DETECTION (raises\nDependencyCycleError), and unavailable-dependency skip-with-warning.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A5: Registry-integrity guard for `requires`

**Files:**
- Modify: `installer/deps.py` (add `requires_integrity_errors`)
- Test: `tests/test_deps.py` (unit) + `tests/test_registry.py` (real registry)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_deps.py`:

```python
from installer.deps import requires_integrity_errors


def test_integrity_flags_unknown_requires_id() -> None:
    good = _tool("good")
    bad = _tool("bad", "ghost")
    errors = requires_integrity_errors([good, bad])
    assert any("bad" in e and "ghost" in e for e in errors)


def test_integrity_clean_catalog_has_no_errors() -> None:
    a = _tool("a", "b")
    b = _tool("b")
    assert requires_integrity_errors([a, b]) == []
```

Append to `tests/test_registry.py` (this guards the shipped data; check the file's existing import of the real registry path and reuse it):

```python
from installer.deps import requires_integrity_errors


def test_shipped_registry_requires_all_resolve() -> None:
    tools = load_tools(_REGISTRY)  # reuse the module-level registry path/loader
    assert requires_integrity_errors(tools) == []


def test_shipped_node_tools_require_pnpm() -> None:
    tools = load_tools(_REGISTRY)
    for tool in tools:
        if any(m.kind == "node" for m in tool.methods):
            assert "pnpm" in tool.requires, f"{tool.id}: node tool must require pnpm"
```

If `tests/test_registry.py` does not already expose `_REGISTRY`/`load_tools`, add the same imports it uses elsewhere (`from installer.model import load_tools` and the registry path constant the other tests in that file use — confirm with `sed -n '1,20p' tests/test_registry.py`).

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_deps.py -k integrity tests/test_registry.py -q`
Expected: FAIL — `cannot import name 'requires_integrity_errors'`.

- [ ] **Step 3: Add `requires_integrity_errors` to `installer/deps.py`**

```python
def requires_integrity_errors(catalog: list[Tool]) -> list[str]:
    """Every `requires` id must resolve to a real catalog tool. Returns a list of
    human-readable errors (empty = clean). Used by a registry-integrity test so a
    typo'd dependency id fails CI instead of shipping a broken install."""
    ids = {t.id for t in catalog}
    errors: list[str] = []
    for tool in catalog:
        for dep_id in tool.requires:
            if dep_id not in ids:
                errors.append(f"tool '{tool.id}' requires unknown tool '{dep_id}'")
    return errors
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_deps.py tests/test_registry.py -q`
Expected: PASS (the shipped registry currently has no `requires`, so it is trivially clean).

- [ ] **Step 5: Validate + commit**

```bash
git add installer/deps.py tests/test_deps.py tests/test_registry.py
git commit -m "$(printf 'feat: registry-integrity guard for requires ids\n\nrequires_integrity_errors + tests asserting every shipped requires resolves\nand every node tool requires pnpm.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A6: Wire the resolver into the install flow

**Files:**
- Modify: `installer/render.py` (add `render_dependency_notice`)
- Modify: `installer/app.py:113-132` (`run_wizard`)
- Test: `tests/test_render.py`, `tests/test_app.py`

- [ ] **Step 1: Write the failing render test**

Append to `tests/test_render.py` (mirror how the file builds a capturing `Console` — check `sed -n '1,30p' tests/test_render.py`):

```python
from installer.render import render_dependency_notice


def test_render_dependency_notice_shows_dragged_in_and_warnings() -> None:
    console = _console()  # the file's capturing-Console helper (StringIO-backed)
    render_dependency_notice(("pnpm",), ("foo is not available on this platform — skipped",), console)
    out = _text(console)
    assert "pnpm" in out
    assert "not available" in out


def test_render_dependency_notice_silent_when_nothing_to_say() -> None:
    console = _console()
    render_dependency_notice((), (), console)
    assert _text(console).strip() == ""
```

Use the same console-capture helpers the existing tests in `test_render.py` use (e.g. a `Console(file=io.StringIO())` plus reading `.getvalue()`); name them to match that file.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_render.py -k dependency -q`
Expected: FAIL — `cannot import name 'render_dependency_notice'`.

- [ ] **Step 3: Add `render_dependency_notice` to `installer/render.py`**

```python
def render_dependency_notice(
    dragged_in: tuple[str, ...],
    warnings: tuple[str, ...],
    console: Console,
) -> None:
    """Announce auto-added dependencies and any skip warnings. Silent when both
    are empty so the common no-dependency case prints nothing."""
    if dragged_in:
        console.print(
            f"[cyan]Added dependencies:[/] {', '.join(dragged_in)} "
            "(required by your selection)."
        )
    for warning in warnings:
        console.print(f"[yellow]⚠ {warning}[/]")
```

Match the file's existing `Console` import and print style (it already imports `rich`'s `Console` and uses markup — confirm via the top of `installer/render.py`).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_render.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing `run_wizard` test**

Append to `tests/test_app.py` (reuse the harness the file already has for `run_wizard` — a stub prompter, a recording install, a fake platform; confirm via `grep -n "def run_wizard\|run_wizard(" tests/test_app.py` and mirror an existing test):

```python
from installer.model import Method, Tool


def _node_tool(tool_id: str, *requires: str) -> Tool:
    return Tool(
        id=tool_id, name=tool_id, category="c", cmd=tool_id,
        methods=(Method(kind="node", params={"npm_pkg": f"@x/{tool_id}"}),),
        requires=tuple(requires),
    )


def test_run_wizard_installs_dependencies_before_dependents() -> None:
    mmdc = _node_tool("mmdc", "pnpm")
    pnpm = _node_tool("pnpm")
    catalog = [mmdc, pnpm]
    installed_order: list[str] = []

    def record_install(tool, platform, runner, resolve_tag, *, checksum_policy="fail"):
        installed_order.append(tool.id)
        return InstallOutcome(tool.id, "installed", method_kind="node")

    # select only mmdc; pnpm must be dragged in and installed FIRST.
    summary = run_wizard(
        catalog,
        _PLATFORM,                       # a node-applicable Platform (reuse the file's fixture)
        _prompter(select=["mmdc"]),      # the file's prompter stub returning these ids
        _console(),
        _options(yes=True),
        install=record_install,
        installed=lambda t: False,
        select_catalog=lambda tools: ["mmdc"],
    )
    assert installed_order == ["pnpm", "mmdc"]
    assert summary is not None
```

Adapt `_PLATFORM`, `_prompter`, `_console`, `_options`, and the `InstallOutcome` import to the names already present in `tests/test_app.py`. The behavioral contract is: selecting only `mmdc` installs `pnpm` then `mmdc`.

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_app.py -k dependencies_before -q`
Expected: FAIL — `pnpm` is not installed / wrong order (the resolver is not wired in yet).

- [ ] **Step 7: Wire the resolver into `run_wizard`**

In `installer/app.py`, add imports:

```python
from installer.deps import resolve_dependencies
from installer.render import render_dependency_notice
from installer.resolve import resolve_methods
```

Replace the body of `run_wizard` from the `selected is None` guard through `run_installs(...)` (currently `app.py:114-128`) with:

```python
    if selected is None:
        return None
    resolution = resolve_dependencies(
        order_for_install(selected),
        tools,
        available=lambda tool: bool(resolve_methods(tool, platform)),
        is_installed=installed,
    )
    render_dependency_notice(resolution.dragged_in, resolution.warnings, console)
    ordered = list(resolution.order)
    statuses = audit(ordered, installed)
    render_audit(statuses, console)
    if not options.yes and not prompter.confirm("Install the selected tools?"):
        return None
    outcomes = run_installs(
        ordered,
        platform,
        runner,
        resolve_tag,
        install,
        on_mismatch=None if options.yes else on_mismatch,
    )
```

This drops the now-redundant standalone `ordered = order_for_install(selected)` line — priority order is preserved because `order_for_install(selected)` is passed *into* the resolver, whose topological pass only moves a dependency earlier than its dependent. A registry cycle would raise `DependencyCycleError` here, but the shipped registry is guarded against cycles by the A5 integrity tests and the audit, so no runtime handling is added (the trusted-registry contract, same as elsewhere).

- [ ] **Step 8: Run to verify it passes + no regressions**

Run: `uv run pytest tests/test_app.py -q`
Expected: PASS. If a pre-existing test asserted the old `audit(selected, ...)` ordering, update it to expect the resolved order (deps-first) — the resolver is now the single source of install order.

- [ ] **Step 9: Validate + commit**

Run: `make validate && make test`

```bash
git add installer/app.py installer/render.py tests/test_app.py tests/test_render.py
git commit -m "$(printf 'feat: resolve dependencies in the install flow\n\nrun_wizard drags in required tools and installs deps-first via the resolver;\nrender_dependency_notice surfaces drag-ins and skip warnings.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A7: `mmdc` registry entry + node-install E2E

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_node_install_e2e.py` (new)

- [ ] **Step 1: Verify the npm package + bin name (live)**

Run: `curl -fsSL https://registry.npmjs.org/@mermaid-js/mermaid-cli/latest | head -c 400; echo`
Expected: JSON naming `@mermaid-js/mermaid-cli` with a `bin` entry for `mmdc`. Confirm the package name exactly before declaring it (prior registry batches were live-verified the same way).

- [ ] **Step 2: Write the failing E2E test**

Create `tests/test_node_install_e2e.py`:

```python
import pytest

from installer.engine import install_tool
from installer.model import Tool, load_tools
from installer.platform import Platform

_REGISTRY = "installer/registry.toml"


def _platform() -> Platform:
    return Platform(os="debian", arch="amd64", immutable=False, has_brew=False)


def _by_id(tool_id: str) -> Tool:
    return next(t for t in load_tools(_REGISTRY) if t.id == tool_id)


def test_mmdc_is_a_node_tool_requiring_pnpm() -> None:
    mmdc = _by_id("mmdc")
    assert mmdc.requires == ("pnpm",)
    node_methods = [m for m in mmdc.methods if m.kind == "node"]
    assert node_methods and node_methods[0].params["npm_pkg"] == "@mermaid-js/mermaid-cli"


def test_installing_mmdc_runs_pnpm_add_global_no_bare_npm(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    calls: list[list[str]] = []
    # not-installed → the node method runs; a recording runner captures argv.
    monkeypatch.setattr("installer.engine.is_installed", lambda _tool: False)
    outcome = install_tool(_by_id("mmdc"), _platform(), runner=calls.append)
    assert outcome.status == "installed"
    assert ["pnpm", "add", "-g", "@mermaid-js/mermaid-cli"] in calls
    assert not any(call[:1] == ["npm"] for call in calls)  # never bare npm
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_node_install_e2e.py -q`
Expected: FAIL — `StopIteration` (no `mmdc` tool yet).

- [ ] **Step 4: Add `mmdc` to `installer/registry.toml`**

First confirm the `diagram` category exists; if not, add a `[[category]]` block. Run: `grep -n 'id = "diagram"' installer/registry.toml || echo "ADD diagram category"`. If missing, add near the other category blocks:

```toml
[[category]]
id = "diagram"
desc = "Diagram and chart generators"
```

Then add the tool (place it with the other tools, alphabetical-ish by id is fine):

```toml
[[tool]]
id = "mmdc"
name = "Mermaid CLI"
category = "diagram"
cmd = "mmdc"
priority = "P2"
audience = "both"
desc = "Render Mermaid diagrams to SVG/PNG/PDF from the command line"
requires = ["pnpm"]
[[tool.method]]
kind = "node"
npm_pkg = "@mermaid-js/mermaid-cli"
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_node_install_e2e.py tests/test_registry.py -q`
Expected: PASS (`mmdc` exists, requires `pnpm`, integrity still clean since `pnpm` is a real catalog id).

- [ ] **Step 6: Manual real-install verification (documented, not CI)**

This proves the user-acceptance criterion. On a machine with `pnpm` on PATH:

Run: `make setup ARGS="--categories diagram --yes"` then `mmdc --version`
Expected: `pnpm` is dragged in (if missing) and installed first, then `mmdc`, and `mmdc --version` prints a version. Record the result in the commit body. (CI keeps the recording-runner test above; a real network install is not run in CI.)

- [ ] **Step 7: Validate + commit**

Run: `make validate && make test`

```bash
git add installer/registry.toml tests/test_node_install_e2e.py
git commit -m "$(printf 'feat: add mmdc as the proving node tool\n\nmmdc installs via pnpm add -g @mermaid-js/mermaid-cli, dragging in pnpm.\nE2E asserts the pnpm argv (no bare npm); manual real-install verified.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A8: Uninstall reverse-dependency warning

**Files:**
- Modify: `installer/uninstall.py` (`reverse_dependencies` helper + `reverse_deps` param on `classify_tools`)
- Modify: `setup.py:167` (pass `reverse_deps` into `classify_tools`)
- Test: `tests/test_uninstall.py`

The Uninstall detail bar renders `ToolRow.hint` (`wizard_app.py` builds each entry's `detail=row.hint`). So the reverse-dependency warning is surfaced by folding a "required by …" note into the hint inside `classify_tools` — **no `UninstallScreen` change** and the warn-but-allow contract is preserved (the row stays removable; it just shows who needs it).

- [ ] **Step 1: Write the failing pure-helper test**

Append to `tests/test_uninstall.py` (this file already imports `Tool`/`Method`/`Platform` — reuse them; add a local `_dep_tool` factory):

```python
from installer.uninstall import classify_tools, reverse_dependencies


def _dep_tool(tool_id: str, *requires: str) -> Tool:
    return Tool(
        id=tool_id, name=tool_id, category="c", cmd=tool_id,
        methods=(Method(kind="node", params={"npm_pkg": f"@x/{tool_id}"}),),
        requires=tuple(requires),
    )


def test_reverse_dependencies_maps_dep_to_its_dependents() -> None:
    rev = reverse_dependencies([_dep_tool("mmdc", "pnpm"), _dep_tool("other", "pnpm"), _dep_tool("pnpm")])
    assert sorted(rev["pnpm"]) == ["mmdc", "other"]
    assert "mmdc" not in rev


def test_reverse_dependencies_empty_when_no_requires() -> None:
    assert reverse_dependencies([_dep_tool("a"), _dep_tool("b")]) == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_uninstall.py -k reverse -q`
Expected: FAIL — `cannot import name 'reverse_dependencies'`.

- [ ] **Step 3: Add `reverse_dependencies` to `installer/uninstall.py`**

```python
def reverse_dependencies(tools: list[Tool]) -> dict[str, list[str]]:
    """Map each tool id to the ids of tools that declare it in `requires`.

    Used by the Uninstall view to warn (but allow) when removing a tool others
    depend on — never a cascade or a block. Ids with no dependents are omitted."""
    rev: dict[str, list[str]] = {}
    for tool in tools:
        for dep_id in tool.requires:
            rev.setdefault(dep_id, []).append(tool.id)
    return rev
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_uninstall.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing `classify_tools` hint test**

Append to `tests/test_uninstall.py`:

```python
def test_classify_appends_required_by_note_to_hint() -> None:
    pnpm = Tool(id="pnpm", name="pnpm", category="pkg-mgr", cmd="pnpm",
                methods=(Method(kind="script", params={"url": "https://x"}),))
    mmdc = _dep_tool("mmdc", "pnpm")
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    rows = classify_tools(
        [pnpm, mmdc], Path("/tmp/bin"),
        installed={"pnpm": True, "mmdc": False},
        platform=platform,
        which=lambda _cmd: None,
        reverse_deps={"pnpm": ["mmdc"]},
    )
    pnpm_row = next(r for r in rows if r.tool.id == "pnpm")
    mmdc_row = next(r for r in rows if r.tool.id == "mmdc")
    assert "required by mmdc" in pnpm_row.hint   # pnpm is needed by mmdc
    assert "required by" not in mmdc_row.hint     # mmdc needs nothing here


def test_classify_without_reverse_deps_leaves_hint_unchanged() -> None:
    pnpm = Tool(id="pnpm", name="pnpm", category="pkg-mgr", cmd="pnpm",
                methods=(Method(kind="script", params={"url": "https://x"}),))
    platform = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    rows = classify_tools([pnpm], Path("/tmp/bin"), installed={"pnpm": True}, platform=platform, which=lambda _cmd: None)
    assert "required by" not in rows[0].hint
```

Ensure `Path` is imported in the test module (it is — `plan_uninstall` tests already use it; otherwise add `from pathlib import Path`).

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_uninstall.py -k required_by -q`
Expected: FAIL — `classify_tools() got an unexpected keyword argument 'reverse_deps'`.

- [ ] **Step 7: Add the `reverse_deps` param to `classify_tools`**

In `installer/uninstall.py`, change the dataclass import to include `replace`:

```python
from dataclasses import dataclass, replace
```

Add a keyword-only param to `classify_tools` (after `which`):

```python
    which: Callable[[str], str | None] = shutil.which,
    reverse_deps: dict[str, list[str]] | None = None,
) -> list[ToolRow]:
```

Then, just before `return rows`, fold the note into each affected row's hint:

```python
    if reverse_deps:
        rows = [
            replace(row, hint=f"{row.hint} · required by {', '.join(reverse_deps[row.tool.id])}")
            if reverse_deps.get(row.tool.id)
            else row
            for row in rows
        ]
    return rows
```

- [ ] **Step 8: Run to verify it passes**

Run: `uv run pytest tests/test_uninstall.py -q`
Expected: PASS (existing `classify_tools` tests still pass — the new param defaults to `None`, a no-op).

- [ ] **Step 9: Wire reverse-deps in `setup.py` (untested boundary)**

In `setup.py` `_build_app`, add `from installer.uninstall import reverse_dependencies` to the existing uninstall imports, and pass the data into the existing `classify_tools` call (`setup.py:167`):

```python
    rows = classify_tools(
        tools,
        _DEFAULT_BIN_DIR,
        installed=installed,
        platform=platform,
        reverse_deps=reverse_dependencies(tools),
    )
```

- [ ] **Step 10: Validate + commit**

Run: `make validate && make test`

```bash
git add installer/uninstall.py setup.py tests/test_uninstall.py
git commit -m "$(printf 'feat: warn (but allow) on uninstalling a required tool\n\nreverse_dependencies + a classify_tools reverse_deps param that folds a\n"required by ..." note into the row hint the Uninstall detail bar already\nrenders. No screen change; no cascade, no block.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A9: Full-catalog dependency audit

**Files:**
- Modify: `installer/registry.toml` (add `requires` / `node` data where verified)
- The A5 integrity tests + A7 E2E guard the result.

This is the long pole: confirm, tool by tool, whether any catalog tool needs another catalog tool at install time, or is itself a node-package CLI. The mechanism (A1–A8) is already proven on `mmdc`; this task seeds real data.

- [ ] **Step 1: Enumerate the catalog**

Run: `uv run python -c "from installer.model import load_tools; [print(t.id, t.category, [m.kind for m in t.methods]) for t in load_tools('installer/registry.toml')]"`
Expected: ~49 tools printed with their method kinds.

- [ ] **Step 2: Audit each tool for inter-tool dependencies**

For every tool, decide whether it requires another *catalog* tool to be present at install time. The catalog is overwhelmingly standalone Rust/Go single-binary downloads (github_release/script/brew), which have **no** inter-tool install dependencies — record those as "no requires" (the default; no change). The realistic candidates:
- Node-package CLIs → `requires = ["pnpm"]` + a `node` method (see Step 3).
- Anything that genuinely shells out to another catalog tool *to install* (verify case-by-case; do not invent dependencies — a runtime soft-dependency like `docker-ps` needing `watch` is NOT an install `requires`).

Produce an audit note in the commit body listing, per tool, "no install dep" or the dependency found, so the pass is auditable. **Do not add a `requires` you did not verify** — a wrong `requires` ships a broken install (PRD risk A).

- [ ] **Step 3: Identify node-package candidates and add them (live-verified)**

For each tool that is genuinely an npm-package CLI (not already a binary release we install), convert/add a `node` method, verifying the package name and bin against npm exactly as in Task A7 Step 1:

Run (per candidate): `curl -fsSL https://registry.npmjs.org/<pkg>/latest | python -c "import sys,json; d=json.load(sys.stdin); print(d['name'], list(d.get('bin',{})))"`

Add the verified entry as:

```toml
[[tool.method]]
kind = "node"
npm_pkg = "<verified package name>"
```

with `requires = ["pnpm"]` on the tool. If the audit finds that `mmdc` is the only clear node candidate in the current catalog, that is a valid outcome — record it explicitly in the commit body rather than padding with unverified entries (YAGNI; the mechanism already ships).

- [ ] **Step 4: Re-run the integrity + E2E guards**

Run: `uv run pytest tests/test_registry.py tests/test_node_install_e2e.py tests/test_deps.py -q`
Expected: PASS — every `requires` resolves, every node tool requires `pnpm`, no cycles.

- [ ] **Step 5: Full validate + commit**

Run: `make validate && make test`

```bash
git add installer/registry.toml
git commit -m "$(printf 'feat: full-catalog dependency audit\n\nLive-verified every catalog tool for inter-tool deps and node-package\ncandidates; seeded requires/node where confirmed (audit notes below).\n\n<paste the per-tool audit summary here>\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task A10: README documentation

**Files:**
- Modify: `README.md`
- Test: none (docs) — but run `make validate` (markdown is part of the tree the gate sees).

- [ ] **Step 1: Locate the right sections**

Run: `grep -n "^#\|pip/npm ban\|Policies\|registry\|method" README.md | head -40`
Identify where install methods, the registry/method kinds, and the Policies/ban content are documented.

- [ ] **Step 2: Document Workstream A**

Add, near the install-methods/registry documentation:
- the `node` kind (`pnpm add -g <npm_pkg>`; never bare npm) and that node tools declare `requires = ["pnpm"]`;
- `requires` as an inter-tool dependency list and **auto drag-in** (selecting a tool pulls in and installs its missing dependencies first, with a printed notice);
- the catalog detail bar's `requires:` line;
- the uninstall **reverse-dependency warning** (warn-but-allow, no cascade).

- [ ] **Step 3: Document Workstream B**

Add, near the pip/npm-ban / Policies documentation:
- the four tweak bundles (Docker shortcuts, countdown `wait_time`, `claude` skip-permissions, Linux-only `apt-upgrade`), what each provides, and the `watch` soft-dependency note for `docker-ps`;
- that each is an independent toggle in the Policies tab, written as its own marker block into `~/.myshellrc`, and takes effect in a new shell.

- [ ] **Step 4: Validate + commit**

Run: `make validate`

```bash
git add README.md
git commit -m "$(printf 'docs: document node deps, drag-in, and tweak bundles\n\nREADME covers the node kind, requires/auto-drag-in, the uninstall\nreverse-dependency warning, and the four toggleable tweak bundles.\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Final verification

- [ ] **Run the whole gate on the final tree**

Run: `make validate && make test`
Expected: ruff/format/pyright/bandit/vulture/shellcheck all clean; full pytest suite green at **100% coverage** on `installer/`.

- [ ] **Confirm the acceptance criteria** (PRD §Acceptance Criteria + spec): node install via `pnpm add -g` with no bare npm; `mmdc` drags in `pnpm`; deps install before dependents; a synthetic cycle raises `DependencyCycleError`; an unavailable dependency warns and skips its dependent; the catalog detail bar shows `requires:`; uninstall warns-but-allows on reverse deps; every shipped `requires` resolves; each applicable bundle is a toggle writing exactly one idempotent block into `~/.myshellrc`; `apt-upgrade` is Linux-only; `wait_time` uses `printf`; bundles parse under `sh -n` (and bash/zsh when present).
