# Registry Batch 4 (`.zip`-unlocked tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add the first tools enabled by the new `.zip` executor — deno, procs, ast-grep, jless — as pure declarative registry data (37 → 41 tools), no executor changes.

**Architecture:** Each tool is one `[[tool]]` entry in `installer/registry.toml` using the proven `github_release` + `archive = "zip"` path: per-OS asset templates with the `{arch.machine}` token (x86_64/aarch64), `member` = the binary's path inside the zip, and a `brew` fallback. Resolution tests in `tests/test_registry.py` pin each tool. No changes to `installer/` code.

**Tech Stack:** TOML registry, `tomllib` loader, pytest. Gates: ruff, pyright (strict), bandit, vulture, shellcheck; 100% coverage.

**Non-negotiables:** English only. No gate bypass. One coherent commit. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Verification evidence (live releases, 2026-06-10)

All asset names and zip layouts were confirmed against the current GitHub release (`gh api .../releases/latest` + `curl … | unzip -l`):

- **deno** `denoland/deno` tag `v2.8.2` → `deno-x86_64-unknown-linux-gnu.zip`, `deno-aarch64-unknown-linux-gnu.zip`, `deno-x86_64-apple-darwin.zip`, `deno-aarch64-apple-darwin.zip`. Zip contains a single `deno` at root. All 4 platforms. (asset has no version token.)
- **procs** `dalance/procs` tag `v0.14.11` → `procs-v0.14.11-{x86_64,aarch64}-linux.zip`, `procs-v0.14.11-{x86_64,aarch64}-mac.zip`. Zip contains a single `procs` at root. All 4 platforms. (asset uses `v{ver}`.)
- **ast-grep** `ast-grep/ast-grep` tag `0.43.0` → `app-{x86_64,aarch64}-unknown-linux-gnu.zip`, `app-{x86_64,aarch64}-apple-darwin.zip`. Zip contains `sg` AND `ast-grep`; we install `ast-grep` (the `sg` short alias collides with the system `sg`/setgroups tool). All 4 platforms. (asset has no version token.)
- **jless** `PaulJuliusMartinez/jless` tag `v0.9.0` → `jless-v0.9.0-{x86_64,aarch64}-apple-darwin.zip`, `jless-v0.9.0-x86_64-unknown-linux-gnu.zip`. **No aarch64-linux asset** → arm64 Linux falls through to brew. Zip contains a single `jless` at root. (asset uses `v{ver}`.)

Deferred (verified unsuitable for the current executor):
- **bun** — assets use the `x64` token (`bun-linux-x64.zip`); needs the not-yet-added `x64` arch token.
- **fnm** — irregular naming (`fnm-linux.zip` for amd64 but `fnm-arm64.zip` for arm64; no shared arch-token template).
- **broot** — ships one 56 MB combined multi-platform zip (`<target>/broot`, no `x86_64-apple-darwin`); our whole-archive `unzip` would dump every platform's binary. Needs selective zip extraction.

---

## Task 1: Add the four tools and their resolution tests

**Files:**
- Modify: `installer/registry.toml` (append four `[[tool]]` entries)
- Modify: `tests/test_registry.py` (add resolution tests; bump the count assertion 37 → 41)

- [ ] **Step 1: Update the count test to expect 41 (write the failing assertion first)**

In `tests/test_registry.py`, change `test_registry_has_thirty_seven_unique_tools_and_cmds`:

```python
def test_registry_has_forty_one_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 41
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))
```

(Rename the function so the name matches the new count; keep it the only place asserting the total.)

- [ ] **Step 2: Add the four resolution tests**

Append to `tests/test_registry.py`:

```python
def test_zip_runtime_and_tools_resolve_with_archive_zip() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    expected = {
        "deno": (
            "deno-{arch.machine}-unknown-linux-gnu.zip",
            "deno-{arch.machine}-apple-darwin.zip",
            "deno",
        ),
        "procs": (
            "procs-v{ver}-{arch.machine}-linux.zip",
            "procs-v{ver}-{arch.machine}-mac.zip",
            "procs",
        ),
        "ast-grep": (
            "app-{arch.machine}-unknown-linux-gnu.zip",
            "app-{arch.machine}-apple-darwin.zip",
            "ast-grep",
        ),
        "jless": (
            "jless-v{ver}-{arch.machine}-unknown-linux-gnu.zip",
            "jless-v{ver}-{arch.machine}-apple-darwin.zip",
            "jless",
        ),
    }
    for tool_id, (linux_asset, macos_asset, member) in expected.items():
        lin = resolve_methods(tools[tool_id], linux)
        mac = resolve_methods(tools[tool_id], macos)
        assert [m.kind for m in lin] == ["github_release", "brew"], tool_id
        assert [m.kind for m in mac] == ["github_release", "brew"], tool_id
        assert lin[0].params["archive"] == "zip", tool_id
        assert lin[0].params["asset"] == linux_asset, tool_id
        assert mac[0].params["asset"] == macos_asset, tool_id
        assert lin[0].params["member"] == member, tool_id
        assert "strip" not in lin[0].params, tool_id  # zip ignores strip


def test_ast_grep_cmd_is_ast_grep_not_sg() -> None:
    ast = next(t for t in load_tools(REGISTRY) if t.id == "ast-grep")
    assert ast.cmd == "ast-grep"  # the bundled `sg` alias collides with the system tool


def test_deno_is_the_lone_runtime_category() -> None:
    runtimes = [t.id for t in load_tools(REGISTRY) if t.category == "runtime"]
    assert runtimes == ["deno"]
```

- [ ] **Step 3: Run the tests, confirm they FAIL**

Run: `uv run pytest tests/test_registry.py -q`
Expected: FAIL — the count test expects 41 (still 37); the new tests can't find `deno`/`procs`/`ast-grep`/`jless`.

- [ ] **Step 4: Append the four tool entries to `installer/registry.toml`**

Add at the end of the file:

```toml
[[tool]]
id = "deno"
name = "Deno"
category = "runtime"
cmd = "deno"
priority = "P2"
audience = "both"
desc = "Secure runtime for JavaScript and TypeScript"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "denoland/deno"
asset = "deno-{arch.machine}-unknown-linux-gnu.zip"
member = "deno"
archive = "zip"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "denoland/deno"
asset = "deno-{arch.machine}-apple-darwin.zip"
member = "deno"
archive = "zip"
[[tool.method]]
kind = "brew"
formula = "deno"

[[tool]]
id = "procs"
name = "procs"
category = "sysinfo"
cmd = "procs"
priority = "P3"
audience = "both"
desc = "A modern replacement for ps written in Rust"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "dalance/procs"
asset = "procs-v{ver}-{arch.machine}-linux.zip"
member = "procs"
archive = "zip"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "dalance/procs"
asset = "procs-v{ver}-{arch.machine}-mac.zip"
member = "procs"
archive = "zip"
[[tool.method]]
kind = "brew"
formula = "procs"

[[tool]]
id = "ast-grep"
name = "ast-grep"
category = "search"
cmd = "ast-grep"
priority = "P3"
audience = "both"
desc = "Fast structural search, lint, and rewrite tool for code"
# The zip bundles both `sg` and `ast-grep`; we install `ast-grep` (the `sg`
# short alias collides with the system setgroups tool).
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "ast-grep/ast-grep"
asset = "app-{arch.machine}-unknown-linux-gnu.zip"
member = "ast-grep"
archive = "zip"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "ast-grep/ast-grep"
asset = "app-{arch.machine}-apple-darwin.zip"
member = "ast-grep"
archive = "zip"
[[tool.method]]
kind = "brew"
formula = "ast-grep"

[[tool]]
id = "jless"
name = "jless"
category = "data"
cmd = "jless"
priority = "P3"
audience = "both"
desc = "A command-line JSON viewer"
# No aarch64-linux asset upstream; arm64 Linux falls through to brew.
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "PaulJuliusMartinez/jless"
asset = "jless-v{ver}-{arch.machine}-unknown-linux-gnu.zip"
member = "jless"
archive = "zip"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "PaulJuliusMartinez/jless"
asset = "jless-v{ver}-{arch.machine}-apple-darwin.zip"
member = "jless"
archive = "zip"
[[tool.method]]
kind = "brew"
formula = "jless"
```

- [ ] **Step 5: Run the tests, confirm they PASS**

Run: `uv run pytest tests/test_registry.py -q`
Expected: PASS — count is 41, all four tools resolve `["github_release", "brew"]` on linux and macos with `archive = "zip"` and the verified asset templates, ast-grep cmd is `ast-grep`, deno is the lone `runtime`.

Also confirm the existing stranding guard still passes:
Run: `uv run pytest tests/test_registry.py::test_every_tool_resolves_at_least_one_method_on_each_platform -q`
Expected: PASS (every new tool has a brew fallback on all platforms).

- [ ] **Step 6: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates green; coverage 100%.

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add deno, procs, ast-grep, jless on the .zip path (registry 37->41)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Document the new tools

**Files:**
- Modify: `README.md` (the "Available tools" table)

- [ ] **Step 1: Update the README catalog**

In `README.md`'s "Available tools" table:
- Add `ast-grep` to the `search` row.
- Add `procs` to the `sysinfo` row.
- Add `jless` to the `data` row.
- Add a new `runtime` row: `| runtime | `deno` |`.

Keep the table's existing column alignment style (it does not need to be perfectly padded — match the surrounding rows reasonably).

- [ ] **Step 2: Validate and commit**

Run: `make validate && make test`
Expected: green (README is not gated by tests, but run to be safe).

```bash
git add README.md
git commit -m "docs: list deno, procs, ast-grep, jless in the tool catalog

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final check

- `make validate && make test` green at 100% on the final tree.
- Registry has 41 unique tools and 41 unique cmds.
- Update `roadmap-status.md` memory: Batch 4 done (deno/procs/ast-grep/jless); bun/fnm/broot remain deferred with their specific blockers.
