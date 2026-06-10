# SP1: Script-Installer Tier (bun, pnpm, fnm) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add bun, pnpm, fnm as `script`-method tools (registry 41 → 44), using their official installers on the ladder's top step, with per-OS `bin_dir`s wired into `~/.myshellrc` and brew fallbacks. No `installer/` code changes.

**Architecture:** Pure declarative registry data. Each tool is one `[[tool]]` entry whose `script` method(s) run the official installer (`url` + `shell`) and declare a `bin_dir` so the existing platform-aware `collect_bin_dirs` adds it to the managed PATH block. The priority ladder already orders `script` (10) before `brew` (40). All install dirs and brew formulae were verified live (see the design spec).

**Tech Stack:** TOML registry, `tomllib`, pytest. Gates: ruff, pyright (strict), bandit, vulture, shellcheck; 100% coverage.

**Non-negotiables:** English only. No gate bypass. One coherent commit. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Verified facts (live, 2026-06-10) — use verbatim

- **bun** `https://bun.sh/install` (`bash`), binary `~/.bun/bin/bun`, same on both OS. brew core `bun`.
- **pnpm** `https://get.pnpm.io/install.sh` (`sh`), PNPM_HOME default Linux `~/.local/share/pnpm`, macOS `~/Library/pnpm`. brew core `pnpm`.
- **fnm** `https://fnm.vercel.app/install` (`bash`), Linux dir `~/.local/share/fnm`; macOS installer brew-delegates → use brew there. brew core `fnm`.

Categories: bun → `runtime`, fnm → `runtime` (joining deno), pnpm → `pkg-mgr` (joining uv, brew).

---

## Reference: the existing `script` tool shape (uv)

```toml
[[tool.method]]
kind = "script"
url = "https://astral.sh/uv/install.sh"
shell = "sh"
bin_dir = "~/.local/bin"
```

`resolve_methods(tool, platform)` returns methods in ladder order and applies each
method's `os` filter (a method with no `os` applies on every platform).

---

## Task 1: Add bun, pnpm, fnm and their resolution tests

**Files:**
- Modify: `installer/registry.toml` (append three `[[tool]]` entries)
- Modify: `tests/test_registry.py` (bump count 41 → 44; update the runtime-category test; add a script-tier test)

- [ ] **Step 1: Update the count and runtime-category tests (failing first)**

In `tests/test_registry.py`, rename `test_registry_has_forty_one_unique_tools_and_cmds` → and set 44:

```python
def test_registry_has_forty_four_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 44
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))
```

Replace `test_deno_is_the_lone_runtime_category` with (bun and fnm now join the category):

```python
def test_runtime_category_members() -> None:
    runtimes = sorted(t.id for t in load_tools(REGISTRY) if t.category == "runtime")
    assert runtimes == ["bun", "deno", "fnm"]
```

- [ ] **Step 2: Add the script-tier resolution test**

Append to `tests/test_registry.py`:

```python
def test_script_installer_tier_resolves_script_then_brew() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)

    # bun: one script method (no os filter) applies on both platforms, then brew.
    for platform in (linux, macos):
        bun = resolve_methods(tools["bun"], platform)
        assert [m.kind for m in bun] == ["script", "brew"]
        assert bun[0].params["url"] == "https://bun.sh/install"
        assert bun[0].params["shell"] == "bash"
        assert bun[0].params["bin_dir"] == "~/.bun/bin"

    # pnpm: per-OS bin_dir (PNPM_HOME differs by platform), then brew.
    pnpm_linux = resolve_methods(tools["pnpm"], linux)
    pnpm_macos = resolve_methods(tools["pnpm"], macos)
    assert [m.kind for m in pnpm_linux] == ["script", "brew"]
    assert [m.kind for m in pnpm_macos] == ["script", "brew"]
    assert pnpm_linux[0].params["url"] == "https://get.pnpm.io/install.sh"
    assert pnpm_linux[0].params["shell"] == "sh"
    assert pnpm_linux[0].params["bin_dir"] == "~/.local/share/pnpm"
    assert pnpm_macos[0].params["bin_dir"] == "~/Library/pnpm"

    # fnm: script on Linux, brew-only on macOS (its installer brew-delegates there).
    fnm_linux = resolve_methods(tools["fnm"], linux)
    assert [m.kind for m in fnm_linux] == ["script", "brew"]
    assert fnm_linux[0].params["url"] == "https://fnm.vercel.app/install"
    assert fnm_linux[0].params["shell"] == "bash"
    assert fnm_linux[0].params["bin_dir"] == "~/.local/share/fnm"
    assert [m.kind for m in resolve_methods(tools["fnm"], macos)] == ["brew"]
```

- [ ] **Step 3: Run the tests, confirm FAIL**

Run: `uv run pytest tests/test_registry.py -q`
Expected: FAIL — count is 41 not 44; runtime members test fails; the three tools don't exist.

- [ ] **Step 4: Append the three entries to `installer/registry.toml`**

Append to the END of the file (exact strings):

```toml
[[tool]]
id = "bun"
name = "Bun"
category = "runtime"
cmd = "bun"
priority = "P2"
audience = "both"
desc = "Fast all-in-one JavaScript runtime and toolkit"
[[tool.method]]
kind = "script"
url = "https://bun.sh/install"
shell = "bash"
bin_dir = "~/.bun/bin"
[[tool.method]]
kind = "brew"
formula = "bun"

[[tool]]
id = "pnpm"
name = "pnpm"
category = "pkg-mgr"
cmd = "pnpm"
priority = "P2"
audience = "both"
desc = "Fast, disk-space-efficient Node.js package manager"
[[tool.method]]
kind = "script"
os = ["debian", "arch", "fedora"]
url = "https://get.pnpm.io/install.sh"
shell = "sh"
bin_dir = "~/.local/share/pnpm"
[[tool.method]]
kind = "script"
os = ["macos"]
url = "https://get.pnpm.io/install.sh"
shell = "sh"
bin_dir = "~/Library/pnpm"
[[tool.method]]
kind = "brew"
formula = "pnpm"

[[tool]]
id = "fnm"
name = "fnm"
category = "runtime"
cmd = "fnm"
priority = "P2"
audience = "both"
desc = "Fast and simple Node.js version manager"
# macOS: the official installer delegates to Homebrew, so install via brew there.
[[tool.method]]
kind = "script"
os = ["debian", "arch", "fedora"]
url = "https://fnm.vercel.app/install"
shell = "bash"
bin_dir = "~/.local/share/fnm"
[[tool.method]]
kind = "brew"
formula = "fnm"
```

- [ ] **Step 5: Run the tests, confirm PASS**

Run: `uv run pytest tests/test_registry.py -q`
Expected: PASS — count 44, runtime = [bun, deno, fnm], script tier resolves as specified. The existing stranding guard `test_every_tool_resolves_at_least_one_method_on_each_platform` still passes (every new tool has a brew fallback on all platforms, and fnm resolves brew on macOS).

- [ ] **Step 6: Validate, test, commit**

Run: `make validate && make test`
Expected: all gates green; coverage 100%.

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add bun, pnpm, fnm via official installers (registry 41->44)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Document the new tools

**Files:**
- Modify: `README.md` (the "Available tools" table)

- [ ] **Step 1: Update the catalog**

In `README.md`'s "Available tools" table:
- Add `pnpm` to the `pkg-mgr` row (now `uv`, Homebrew (opt-in), `pnpm`).
- Add `bun` and `fnm` to the `runtime` row (now `deno`, `bun`, `fnm`).

- [ ] **Step 2: Validate and commit**

Run: `make validate && make test`
Expected: green.

```bash
git add README.md
git commit -m "docs: list bun, pnpm, fnm in the tool catalog

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final check

- `make validate && make test` green at 100% on the final tree.
- Registry has 44 unique tools and 44 unique cmds.
- Update `roadmap-status.md` memory: SP1 done (bun/pnpm/fnm via `script`); SP2 (link-mode preference) and SP3 (dup-cleaning + post-install doctor verify) still pending.
