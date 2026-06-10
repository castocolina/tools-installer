# Registry Expansion — Batch 2 (Verified CLI Tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the registry from 14 to 25 tools by adding 11 more verified AI-dev CLIs, reusing the already-working download path (no executor changes).

**Architecture:** Pure declarative data. The opt+symlink extraction, raw-binary path, OS-split methods, and raw-tag URL handling all already exist (Batch 1). Each new tool is `github_release` (OS-split linux/macOS) + `brew`, except `direnv` which is a `raw` per-OS binary. Native package managers remain deferred. Every asset template, `strip`, and `member` was verified against live GitHub releases on 2026-06-10.

**Tech Stack:** Python 3.11+, uv, tomllib, pytest (100% coverage gate), ruff/pyright-strict/bandit/vulture.

---

## Verified Release Facts (ground truth — live releases, 2026-06-10)

`{ver}` = release tag with any leading `v` stripped. Arch tokens: amd64 → machine=`x86_64`, deb=`amd64`, suffix=`x86_64`; arm64 → machine=`aarch64`, deb=`arm64`, suffix=`arm64`.

| tool | repo | cmd | linux asset | macOS asset | strip | member | raw | brew |
|---|---|---|---|---|---|---|---|---|
| starship | starship/starship | starship | `starship-{arch.machine}-unknown-linux-musl.tar.gz` | `starship-{arch.machine}-apple-darwin.tar.gz` | 0 | starship | no | starship |
| direnv | direnv/direnv | direnv | `direnv.linux-{arch.deb}` | `direnv.darwin-{arch.deb}` | — | direnv | **yes** | direnv |
| just | casey/just | just | `just-{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `just-{ver}-{arch.machine}-apple-darwin.tar.gz` | 0 | just | no | just |
| ruff | astral-sh/ruff | ruff | `ruff-{arch.machine}-unknown-linux-musl.tar.gz` | `ruff-{arch.machine}-apple-darwin.tar.gz` | 1 | ruff | no | ruff |
| dust | bootandy/dust | dust | `dust-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `dust-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | dust | no | dust |
| hyperfine | sharkdp/hyperfine | hyperfine | `hyperfine-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz` | `hyperfine-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | hyperfine | no | hyperfine |
| bottom | ClementTsang/bottom | btm | `bottom_{arch.machine}-unknown-linux-musl.tar.gz` | `bottom_{arch.machine}-apple-darwin.tar.gz` | 0 | btm | no | bottom |
| gum | charmbracelet/gum | gum | `gum_{ver}_Linux_{arch.suffix}.tar.gz` | `gum_{ver}_Darwin_{arch.suffix}.tar.gz` | 1 | gum | no | gum |
| glow | charmbracelet/glow | glow | `glow_{ver}_Linux_{arch.suffix}.tar.gz` | `glow_{ver}_Darwin_{arch.suffix}.tar.gz` | 1 | glow | no | glow |
| xh | ducaale/xh | xh | `xh-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `xh-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | xh | no | xh |
| difftastic | Wilfred/difftastic | difft | `difft-{arch.machine}-unknown-linux-gnu.tar.gz` | `difft-{arch.machine}-apple-darwin.tar.gz` | 0 | difft | no | difftastic |

**Per-tool notes (do not "simplify"):**
- `starship`/`bottom` (musl) and `ruff` (musl), `difftastic`/`hyperfine` (gnu) embed **no version** in the asset name. `dust` embeds `-v{ver}-`; `just`/`xh` embed `-{ver}-` (no `v`).
- `just`/`ruff`/`bottom`/`difftastic` ship **bare** tags (no leading `v`); `starship`/`dust`/`hyperfine`/`gum`/`glow`/`xh`/`direnv` ship `v`-tags. The resolver handles both — do not encode it here.
- `hyperfine` uses **gnu** (its aarch64-linux has no musl); `difftastic` uses **gnu** (same reason). `dust` uses musl (both arches available).
- `dust` has **no aarch64 macOS asset** (Intel-mac x86_64 only) → Apple-Silicon-Mac dust falls through to brew. Acceptable (engine fallback).
- `bottom`'s binary is `btm`; `difftastic`'s binary is `difft` — `cmd` and `member` differ from the tool `id`.
- `gum`/`glow` use `{arch.suffix}` (`Linux_x86_64` / `Darwin_arm64`); their tarballs nest under a versioned dir → `strip = 1`.
- `direnv` is a single raw binary per OS (`raw = true`, no `strip`).

---

## File Structure
- `installer/registry.toml` — **modify**: append 11 `[[tool]]` entries.
- `tests/test_registry.py` — **modify**: add per-platform resolution tests.
- `README.md` — **modify**: extend the "Available tools" table.
- memory `roadmap-status.md` — **modify**: record Batch 2.

---

## Task 1: Add starship, direnv, just, ruff, dust, hyperfine

**Files:** Modify `installer/registry.toml`; Test `tests/test_registry.py`.

- [ ] **Step 1: Append these six tools to `installer/registry.toml`:**

```toml
[[tool]]
id = "starship"
name = "starship"
category = "shell"
cmd = "starship"
priority = "P1"
audience = "both"
desc = "The minimal, blazing-fast, customizable prompt for any shell"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "starship/starship"
asset = "starship-{arch.machine}-unknown-linux-musl.tar.gz"
member = "starship"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "starship/starship"
asset = "starship-{arch.machine}-apple-darwin.tar.gz"
member = "starship"
strip = 0
[[tool.method]]
kind = "brew"
formula = "starship"

[[tool]]
id = "direnv"
name = "direnv"
category = "shell"
cmd = "direnv"
priority = "P1"
audience = "both"
desc = "Per-directory environment variables, loaded on cd"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "direnv/direnv"
asset = "direnv.linux-{arch.deb}"
member = "direnv"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "direnv/direnv"
asset = "direnv.darwin-{arch.deb}"
member = "direnv"
raw = true
[[tool.method]]
kind = "brew"
formula = "direnv"

[[tool]]
id = "just"
name = "just"
category = "dev"
cmd = "just"
priority = "P1"
audience = "both"
desc = "A handy command runner for project-specific tasks"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "casey/just"
asset = "just-{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "just"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "casey/just"
asset = "just-{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "just"
strip = 0
[[tool.method]]
kind = "brew"
formula = "just"

[[tool]]
id = "ruff"
name = "ruff"
category = "dev"
cmd = "ruff"
priority = "P1"
audience = "both"
desc = "An extremely fast Python linter and formatter"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "astral-sh/ruff"
asset = "ruff-{arch.machine}-unknown-linux-musl.tar.gz"
member = "ruff"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "astral-sh/ruff"
asset = "ruff-{arch.machine}-apple-darwin.tar.gz"
member = "ruff"
strip = 1
[[tool.method]]
kind = "brew"
formula = "ruff"

[[tool]]
id = "dust"
name = "dust"
category = "sysinfo"
cmd = "dust"
priority = "P2"
audience = "both"
desc = "A more intuitive version of du (disk usage)"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "bootandy/dust"
asset = "dust-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "dust"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "bootandy/dust"
asset = "dust-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "dust"
strip = 1
[[tool.method]]
kind = "brew"
formula = "dust"

[[tool]]
id = "hyperfine"
name = "hyperfine"
category = "dev"
cmd = "hyperfine"
priority = "P2"
audience = "both"
desc = "A command-line benchmarking tool"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "sharkdp/hyperfine"
asset = "hyperfine-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
member = "hyperfine"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "sharkdp/hyperfine"
asset = "hyperfine-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "hyperfine"
strip = 1
[[tool.method]]
kind = "brew"
formula = "hyperfine"
```

- [ ] **Step 2: Add resolution tests to `tests/test_registry.py`:**

```python
def test_direnv_is_raw_per_os_download() -> None:
    direnv = next(t for t in load_tools(REGISTRY) if t.id == "direnv")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    lin = resolve_methods(direnv, linux)[0]
    mac = resolve_methods(direnv, macos)[0]
    assert lin.params == {"repo": "direnv/direnv", "asset": "direnv.linux-{arch.deb}",
                          "member": "direnv", "raw": True}
    assert mac.params["asset"] == "direnv.darwin-{arch.deb}"
    assert "strip" not in lin.params and "strip" not in mac.params


def test_hyperfine_linux_uses_gnu_and_strips() -> None:
    hf = next(t for t in load_tools(REGISTRY) if t.id == "hyperfine")
    linux = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    method = resolve_methods(hf, linux)[0]
    assert method.params["asset"] == "hyperfine-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
    assert method.params["strip"] == 1


def test_starship_and_just_resolve_download_then_brew() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    for tool_id in ("starship", "just", "ruff", "dust"):
        kinds = [m.kind for m in resolve_methods(tools[tool_id], macos)]
        assert kinds == ["github_release", "brew"], tool_id
```

- [ ] **Step 3: Run `make validate && make test`; both must pass at 100% coverage.**

- [ ] **Step 4: Commit:**
```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add starship, direnv, just, ruff, dust and hyperfine"
```

---

## Task 2: Add bottom, gum, glow, xh, difftastic

**Files:** Modify `installer/registry.toml`; Test `tests/test_registry.py`.

- [ ] **Step 1: Append these five tools to `installer/registry.toml`:**

```toml
[[tool]]
id = "bottom"
name = "bottom"
category = "sysinfo"
cmd = "btm"
priority = "P2"
audience = "both"
desc = "A customizable cross-platform graphical process/system monitor"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "ClementTsang/bottom"
asset = "bottom_{arch.machine}-unknown-linux-musl.tar.gz"
member = "btm"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "ClementTsang/bottom"
asset = "bottom_{arch.machine}-apple-darwin.tar.gz"
member = "btm"
strip = 0
[[tool.method]]
kind = "brew"
formula = "bottom"

[[tool]]
id = "gum"
name = "gum"
category = "shell"
cmd = "gum"
priority = "P2"
audience = "both"
desc = "A tool for glamorous shell scripts"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "charmbracelet/gum"
asset = "gum_{ver}_Linux_{arch.suffix}.tar.gz"
member = "gum"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "charmbracelet/gum"
asset = "gum_{ver}_Darwin_{arch.suffix}.tar.gz"
member = "gum"
strip = 1
[[tool.method]]
kind = "brew"
formula = "gum"

[[tool]]
id = "glow"
name = "glow"
category = "view"
cmd = "glow"
priority = "P2"
audience = "both"
desc = "Render markdown on the command line"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "charmbracelet/glow"
asset = "glow_{ver}_Linux_{arch.suffix}.tar.gz"
member = "glow"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "charmbracelet/glow"
asset = "glow_{ver}_Darwin_{arch.suffix}.tar.gz"
member = "glow"
strip = 1
[[tool.method]]
kind = "brew"
formula = "glow"

[[tool]]
id = "xh"
name = "xh"
category = "net"
cmd = "xh"
priority = "P2"
audience = "both"
desc = "A friendly and fast tool for sending HTTP requests"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "ducaale/xh"
asset = "xh-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "xh"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "ducaale/xh"
asset = "xh-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "xh"
strip = 1
[[tool.method]]
kind = "brew"
formula = "xh"

[[tool]]
id = "difftastic"
name = "difftastic"
category = "git"
cmd = "difft"
priority = "P2"
audience = "both"
desc = "A structural diff that understands syntax"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "Wilfred/difftastic"
asset = "difft-{arch.machine}-unknown-linux-gnu.tar.gz"
member = "difft"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "Wilfred/difftastic"
asset = "difft-{arch.machine}-apple-darwin.tar.gz"
member = "difft"
strip = 0
[[tool.method]]
kind = "brew"
formula = "difftastic"
```

- [ ] **Step 2: Add resolution tests to `tests/test_registry.py`:**

```python
def test_bottom_and_difftastic_cmd_differs_from_member_binary() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    bottom = tools["bottom"]
    difft = tools["difftastic"]
    assert bottom.cmd == "btm"
    assert difft.cmd == "difft"
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    assert resolve_methods(bottom, linux)[0].params["member"] == "btm"
    assert resolve_methods(difft, linux)[0].params["member"] == "difft"


def test_charm_tools_use_suffix_arch_token_and_strip() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    for tool_id, os_word in (("gum", "Linux"), ("glow", "Linux")):
        method = resolve_methods(tools[tool_id], linux)[0]
        assert method.params["asset"] == f"{tool_id}_{{ver}}_{os_word}_{{arch.suffix}}.tar.gz"
        assert method.params["strip"] == 1


def test_registry_has_twenty_five_unique_tools() -> None:
    ids = [t.id for t in load_tools(REGISTRY)]
    assert len(ids) == len(set(ids))
    assert len(ids) == 25
    cmds = [t.cmd for t in load_tools(REGISTRY)]
    assert len(cmds) == len(set(cmds))  # no two tools claim the same command
```

- [ ] **Step 3: Run `make validate && make test`; both must pass at 100% coverage.**

- [ ] **Step 4: Commit:**
```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add bottom, gum, glow, xh and difftastic"
```

---

## Task 3: Update docs

**Files:** Modify `README.md`; Modify memory `roadmap-status.md`.

- [ ] **Step 1: Extend the README "Available tools" table** to include the new categories/tools: shell (`starship`, `direnv`, `gum`), dev (`just`, `ruff`, `hyperfine`), sysinfo (`bottom`/btm, `dust`), net (`xh`), and add `glow` to view and `difftastic`/difft to git. Keep the existing rows. Describe only what exists.

- [ ] **Step 2: Update the roadmap memory** (`/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`): record Batch 2 (registry 14→25; the 11 tools; note direnv is raw, dust has no aarch64-mac asset, hyperfine/difftastic use gnu; no executor changes needed — reused Batch 1's path). Under deferred, add: zip-only tools not yet supported (fnm, procs, ast-grep need a `.zip` extractor); tokei (no clean binary assets).

- [ ] **Step 3: Commit (README only; memory is outside the repo):**
```bash
git add README.md
git commit -m "docs: document the batch 2 tool catalog"
```

---

## Self-Review (completed by plan author)
- **Spec coverage:** 11 tools added across Tasks 1–2; docs in Task 3. Every asset/strip/member/raw value transcribed from the Verified Release Facts table. ✓
- **Placeholder scan:** No TBDs; all values are concrete literals verified against live releases. ✓
- **Type consistency:** All methods follow the existing `Method` shape (`kind`/`os`/params). `raw` tools omit `strip`; `bottom`/`difftastic` use `cmd`/`member` distinct from `id`. The count test (25) matches 14 existing + 11 new. ✓
- **No executor changes:** Confirmed — every shape (os-split github_release, raw, strip, gnu/musl) is already supported by the Batch 1 executor. ✓
